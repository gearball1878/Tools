"""Four-layer requirements view and safe derivation rules.

Older SPOT packages used System/Realization/Component. We display their
original values in the appropriate V-model column without rewriting history.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import ArchitecturePackage, EcadRequirement, RequirementClassification, RequirementLevel, RequirementSourceKind, RequirementSpecificationLevel


LAYERS = (
    ("L1", "Kunde / Lastenheft", RequirementLevel.CUSTOMER),
    ("L2", "System", RequirementLevel.SYSTEM),
    ("L3", "Technische Anforderungen", RequirementLevel.TECHNICAL),
    ("L4", "Disziplin: HW / Mechanik / SW / FW", RequirementLevel.DISCIPLINE),
)


def effective_layer(requirement: EcadRequirement) -> RequirementLevel:
    level = requirement.requirement_level
    if level in {RequirementLevel.REALIZATION, RequirementLevel.COMPONENT}:
        return RequirementLevel.DISCIPLINE
    if (level == RequirementLevel.SYSTEM
            and requirement.specification_level == RequirementSpecificationLevel.CUSTOMER_SPECIFICATION
            and requirement.source_kind == RequirementSourceKind.CUSTOMER_CONTRACT):
        return RequirementLevel.CUSTOMER
    return level


def _rank(requirement: EcadRequirement) -> int:
    return next(i for i, (_, _, layer) in enumerate(LAYERS) if effective_layer(requirement) == layer)


def derivation_edges(package: ArchitecturePackage) -> set[tuple[str, str]]:
    from .requirement_graph import derivation_edges as read_edges
    return read_edges(package)


def directed_requirement_scope(package: ArchitecturePackage, requirement_id: str) -> set[str]:
    """Follow the chosen requirement's ancestors and descendants, not siblings.

    A shared customer parent must not pull unrelated system branches into a
    focused view. Edges come exclusively from stored derivations.
    """
    ids = {item.id for item in package.requirements}
    if requirement_id not in ids:
        return set()
    parents: dict[str, set[str]] = {}
    children: dict[str, set[str]] = {}
    for parent, child in derivation_edges(package):
        if parent in ids and child in ids:
            parents.setdefault(child, set()).add(parent)
            children.setdefault(parent, set()).add(child)
    visible = {requirement_id}
    for adjacency in (parents, children):
        pending = [requirement_id]
        while pending:
            for related in adjacency.get(pending.pop(), ()):
                if related not in visible:
                    visible.add(related)
                    pending.append(related)
    return visible


def validate_parent_links(package: ArchitecturePackage, child: EcadRequirement,
                          parent_ids: list[str]) -> None:
    """Validate newly edited links; incomplete paths remain visible as gaps."""
    lookup = {item.id: item for item in package.requirements}
    if effective_layer(child) == RequirementLevel.CUSTOMER and parent_ids:
        raise ValueError("L1-Kundenanforderungen haben keine übergeordnete Requirement-Ebene.")
    edges = derivation_edges(package)
    edges = {edge for edge in edges if edge[1] != child.id}
    for parent_id in parent_ids:
        parent = lookup.get(parent_id)
        if parent is None or parent_id == child.id:
            raise ValueError("Ungültiges übergeordnetes Requirement.")
        if _rank(parent)>=_rank(child):raise ValueError('Ableitungen führen zu einer tieferen Ebene L1 → L2 → L3 → L4.')
        if _rank(parent) + 1 != _rank(child) and not child.rationale.strip():
            raise ValueError('Ein Ebenensprung benötigt eine Begründung am abgeleiteten Requirement.')
        edges.add((parent_id, child.id))
    # Existing legacy links may already skip levels, but cycles may never be
    # introduced by a new edit.
    children: dict[str, set[str]] = {}
    for parent_id, child_id in edges:
        children.setdefault(parent_id, set()).add(child_id)
    stack = [child.id]
    seen: set[str] = set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(children.get(current, ()))
    if any(parent_id in seen for parent_id in parent_ids):
        raise ValueError("Diese Ableitung erzeugt einen Zyklus.")
    if effective_layer(child) == RequirementLevel.DISCIPLINE and child.classification == RequirementClassification.SYSTEM:
        raise ValueError("L4 benötigt eine Fachdisziplin: Hardware, Mechanik, Software oder Firmware.")


@dataclass(frozen=True)
class LayerView:
    columns: tuple[tuple[EcadRequirement, ...], ...]
    edges: frozenset[tuple[str, str]]
    gaps: tuple[str, ...]


@dataclass(frozen=True)
class SolutionGraph:
    """Unique solution objects and their explicit links to requirements and parts.

    Node keys use ``arch:``, ``real:``, ``part:``, ``mech:`` and ``sw:`` prefixes;
    requirements use ``req:``. Only links recorded in the project are drawn.
    """

    nodes: tuple[str, ...]
    edges: frozenset[tuple[str, str]]
    unallocated: frozenset[str]

    def visible_nodes(self, requirement_ids: set[str] | None = None) -> set[str]:
        """Keep connected solutions for a filtered requirement chain."""
        if requirement_ids is None:
            return set(self.nodes)
        reached = {target for source, target in self.edges
                   if source.startswith("req:") and source[4:] in requirement_ids}
        while True:
            expanded = reached | {target for source, target in self.edges if source in reached}
            if expanded == reached:
                return reached
            reached = expanded


def build_solution_graph(package: ArchitecturePackage) -> SolutionGraph:
    """Include legacy parts even when no requirement allocation exists yet."""
    objects = (
        [("real:", item) for item in package.technical_realizations]
        + [("part:", item) for item in package.components]
        + [("mech:", item) for item in package.mechanical_components]
        + [("sw:", item) for item in package.software_components]
    )
    from .traceability import project_objects,canonical_kind
    architecture_kinds={'SystemDomain','SystemElement','SystemRelation','Domain','ArchitectureElement','FunctionElement','Port','ArchitectureSignal','Connection',
                        'MechanicalArchitectureElement','SoftwareArchitectureElement','DisciplineRelation','IntegrationInterface','Signal'}
    registry=project_objects(package)
    objects += [('arch:',obj) for kind,group in registry.items() if kind in architecture_kinds for obj in group.values()]
    nodes = tuple(prefix + item.id for prefix, item in objects)
    node_keys = set(nodes)
    requirement_keys = {"req:" + item.id for item in package.requirements}
    edges: set[tuple[str, str]] = set()
    from .requirement_graph import allocation_edges
    kinds={'Realization':'real:','TechnicalRealization':'real:','Component':'part:',
           'MechanicalComponent':'mech:','SoftwareComponent':'sw:'}
    kinds.update({kind:'arch:' for kind in architecture_kinds})
    for rid,kind,oid in allocation_edges(package):
        prefix=kinds.get(canonical_kind(kind))
        target = (prefix or "") + oid
        source = "req:" + rid
        if (prefix and source in requirement_keys and target in node_keys
                ):
            edges.add((source, target))
    for realization in package.technical_realizations:
        source = "real:" + realization.id
        if realization.architecture_element_id:
            arch='arch:'+realization.architecture_element_id
            if arch in node_keys:edges.add((arch,source))
        if realization.function_element_id:
            fe='arch:'+realization.function_element_id
            if fe in node_keys:edges.add((fe,source))
        variants=[v for v in realization.variants if not realization.selected_variant_id or v.id==realization.selected_variant_id]
        for variant in variants:
            children = (["part:" + role.component_id for role in variant.component_roles]
                        + ["mech:" + key for key in variant.mechanical_component_ids]
                        + ["sw:" + key for key in variant.software_component_ids])
            edges.update((source, child) for child in children if child in node_keys)
    for allocation in package.architecture_allocations:
        source='arch:'+allocation.system_element_id
        prefix={'hw_element':'arch:','hw_realization':'real:','mechanical':'mech:','software':'sw:',
                'mechanical_element':'arch:','software_element':'arch:'}[allocation.target_kind]
        target=prefix+allocation.target_id
        if source in node_keys and target in node_keys:edges.add((source,target))
    for fe in package.function_elements:
        if fe.architecture_element_id and 'arch:'+fe.architecture_element_id in node_keys:edges.add(('arch:'+fe.architecture_element_id,'arch:'+fe.id))
        edges.update(('arch:'+fe.id,'arch:'+i) for i in fe.dependency_ids)
    for fe in package.function_elements:
        prefix={'hardware':'real:','software':'sw:','mechanical':'mech:'}[fe.discipline]
        edges.update(('arch:'+fe.id,prefix+i) for i in fe.realization_ids if prefix+i in node_keys)
    from .integration import REFERENCE_COLLECTIONS
    for interface in package.integration_interfaces:
        for field,kind in REFERENCE_COLLECTIONS.items():
            prefix=kinds.get(kind)
            if not prefix:continue
            edges.update(('arch:'+interface.id,prefix+i) for i in getattr(interface,field) if prefix+i in node_keys)
    for relation in package.model_relations:
        if relation.kind not in {'realized_by','technical_interface','dependency','contains'}:continue
        a=kinds.get(canonical_kind(relation.source_type),'')+relation.source_id
        b=kinds.get(canonical_kind(relation.target_type),'')+relation.target_id
        if a in node_keys and b in node_keys:edges.add((a,b))
    for prefix,collection in [('mech:',package.mechanical_architecture_elements),('sw:',package.software_architecture_elements)]:
        for obj in collection:
            edges.update(('arch:'+obj.id,prefix+rid) for rid in obj.realization_ids if prefix+rid in node_keys)
    graph = SolutionGraph(nodes, frozenset(edges), frozenset())
    reached = graph.visible_nodes({item.id for item in package.requirements})
    return SolutionGraph(nodes, frozenset(edges), frozenset(node_keys - reached))


def focused_graph(nodes,edges,focus,depth='chain'):
    """Ancestors and descendants independently; never spread into sibling branches."""
    nodes=set(nodes)
    if not focus or focus=='__all__' or focus not in nodes:return nodes
    visible={focus}
    for reverse in (False,True):
        frontier={focus};seen={focus}
        while frontier:
            adjacent={a if reverse else b for a,b in edges if (b if reverse else a) in frontier}
            frontier=(adjacent & nodes)-seen;seen|=frontier
            if depth=='direct':break
        visible|=seen
    return visible


def build_layer_view(
    package: ArchitecturePackage,
    focus_id: str | None = None,
    *,
    visible_ids: set[str] | None = None,
    include_inactive: bool = False,
) -> LayerView:
    from .models import RequirementMaturity

    all_items = {item.id: item for item in package.requirements
                 if include_inactive or item.maturity not in {
                     RequirementMaturity.REJECTED, RequirementMaturity.OBSOLETE}}
    all_edges = {(a, b) for a, b in derivation_edges(package) if a in all_items and b in all_items}
    if focus_id in all_items:
        visible = directed_requirement_scope(package, focus_id) & all_items.keys()
    else:
        visible = set(all_items) if visible_ids is None else visible_ids
    items = {key: item for key, item in all_items.items() if key in visible}
    edges = {(a, b) for a, b in all_edges if a in items and b in items}
    columns = tuple(tuple(sorted((item for item in items.values() if effective_layer(item) == layer),
                                 key=lambda item: (item.identifier, item.title)))
                    for _, _, layer in LAYERS)
    gaps = []
    for item in items.values():
        if _rank(item) and not any(b == item.id and _rank(all_items[a]) == _rank(item) - 1 for a, b in all_edges):
            gaps.append(f"{item.identifier or item.title}: Ableitung aus L{_rank(item)} fehlt")
    for a, b in all_edges:
        if (a in items or b in items) and _rank(all_items[b]) != _rank(all_items[a]) + 1:
            gaps.append(f"{all_items[a].identifier or all_items[a].title} → {all_items[b].identifier or all_items[b].title}: Ebenensprung prüfen")
    return LayerView(columns, frozenset(edges), tuple(sorted(set(gaps))))
