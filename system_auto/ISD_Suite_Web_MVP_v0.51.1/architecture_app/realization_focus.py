"""Context projection of existing hardware objects, without duplicated records."""
from dataclasses import dataclass
from .realization_context_ui import realization_context
from .realization_service import core_component_ids

CONTEXTS = {'architecture': 'Architektur', 'parts': 'Parts', 'requirements': 'Requirements', 'ecad': 'ECAD'}


def direct_requirements(package, target_ids):
    """Direct allocations only; never traverse derivation or architecture ownership."""
    from .requirement_graph import allocation_edges
    target_ids = set(target_ids)
    ids = {rid for rid, _, target in allocation_edges(package) if target in target_ids}
    return [r for r in package.requirements if r.id in ids]


def focus_projection(package, scope_id=None, focus_id=None):
    aes = {e.id: e for d in package.domains for e in d.elements}
    domains = {d.id: d for d in package.domains}
    fes = {f.id: f for f in package.function_elements if f.discipline == 'hardware'}
    reals = {r.id: r for r in package.technical_realizations}
    owners = {}; functions = {}; part_owners = {}; part_reals = {}
    for r in reals.values():
        ids, fs = realization_context(package, r)
        active = next((v for v in r.variants if v.id == r.selected_variant_id), None)
        ids = set(ids) | (set(active.architecture_element_ids) if active else set())
        owners[r.id] = ids; functions[r.id] = {f.id for f in fs}
        if active:
            for identifier in core_component_ids(package, active):
                part_owners.setdefault(identifier, set()).update(ids)
                part_reals.setdefault(identifier, set()).add(r.id)
    for allocation in package.component_allocations:
        part_owners.setdefault(allocation.component_id, set()).add(allocation.element_id)
    core_ids = {c.id for c in package.components if c.system_defining is True} | set(part_reals)
    parts = {c.id: c for c in package.components if c.id in core_ids and c.system_defining is not False}
    selected_aes = set(aes)
    selected_fes = set(fes)
    selected_reals = set(reals)
    selected_parts = set(parts)
    if scope_id:
        selected_aes = ({e.id for e in domains[scope_id].elements} if scope_id in domains else
                        {scope_id} if scope_id in aes else
                        {fes[scope_id].architecture_element_id} - {None} if scope_id in fes else set())
        selected_fes = ({scope_id} if scope_id in fes else
                        {i for i, f in fes.items() if f.architecture_element_id in selected_aes})
        selected_reals = {i for i in reals if (functions[i] & selected_fes if scope_id in fes else owners[i] & selected_aes or functions[i] & selected_fes)}
        selected_parts = {i for i in parts if part_reals.get(i, set()) & selected_reals or (scope_id not in fes and part_owners.get(i, set()) & selected_aes)}
    if focus_id in selected_aes or focus_id in selected_fes or focus_id in domains and (not scope_id or scope_id == focus_id):
        return focus_projection(package, focus_id)
    # A focal object keeps one dossier across all presentation contexts.
    if focus_id in reals or focus_id in parts or any(r.id == focus_id for r in package.requirements):
        focal_reals = ({focus_id} if focus_id in reals else part_reals.get(focus_id, set()) if focus_id in parts else set())
        if focus_id not in reals and focus_id not in parts:
            focal_parts = {i for i in selected_parts if any(r.id == focus_id for r in direct_requirements(package, {i}))}
            focal_reals = {i for i in selected_reals if any(r.id == focus_id for r in direct_requirements(package, {i}))} | {i for c in focal_parts for i in part_reals.get(c, set())}
        selected_reals &= focal_reals
        selected_aes = ({i for r in selected_reals for i in owners[r]} | part_owners.get(focus_id, set())) & selected_aes
        selected_fes = {i for r in selected_reals for i in functions[r]} & selected_fes
        selected_parts = {i for i in selected_parts if part_reals.get(i, set()) & selected_reals or i == focus_id or (focus_id not in reals and focus_id not in parts and i in focal_parts)}
    requirements = direct_requirements(package, selected_fes | selected_reals | selected_parts)
    architecture = [d for d in package.domains if (not scope_id and not focus_id) or d.id == scope_id or any(e.id in selected_aes for e in d.elements)]
    architecture += [aes[i] for i in aes if i in selected_aes] + [fes[i] for i in fes if i in selected_fes]
    return {'architecture': architecture, 'parts': [parts[i] for i in parts if i in selected_parts],
            'requirements': requirements, 'realizations': [reals[i] for i in reals if i in selected_reals],
            'owners': part_owners, 'part_realizations': part_reals, 'realization_owners': owners,
            'realization_functions': functions}


@dataclass
class RealizationFocus:
    context: str = 'architecture'
    selected_id: str | None = None
    focus_id: str | None = None
    scope_id: str | None = None
    project_id: str | None = None
    query: str = ''

    def reconcile(self, package):
        if self.project_id != package.project.id:
            self.project_id = package.project.id
            self.selected_id = self.scope_id = self.focus_id = None
            self.query = ''
        objects = focus_objects(package)
        if self.selected_id not in objects: self.selected_id = None
        if self.focus_id not in objects: self.focus_id = None
        if self.scope_id not in scope_options(package): self.scope_id = None

    def select(self, identifier, package=None):
        self.selected_id = identifier
        if package is not None:
            projection = focus_projection(package, self.scope_id, self.focus_id)
            # Inspecting a linked item does not replace the dossier's focal object.
            related = {o.id for key in ('architecture', 'parts', 'requirements', 'realizations') for o in projection[key]}
            if self.focus_id is None or identifier not in related or any(r.id == identifier for r in package.technical_realizations):
                self.focus_id = identifier

    def change_context(self, context):
        if context not in CONTEXTS: raise ValueError('Unbekannter Realisierungskontext')
        self.context = context


def focus_objects(package):
    return {o.id: o for o in [*package.domains, *(e for d in package.domains for e in d.elements),
        *(f for f in package.function_elements if f.discipline == 'hardware'),
        *package.technical_realizations, *package.components, *package.requirements]}


def scope_options(package):
    options = {'': 'Gesamtes HW-Projekt'}
    for domain in package.domains:
        options[domain.id] = 'Domäne · ' + domain.name
        options.update({e.id: 'AE · ' + domain.name + ' / ' + e.name for e in domain.elements})
    options.update({f.id: 'FE · ' + f.name for f in package.function_elements if f.discipline == 'hardware'})
    return options
