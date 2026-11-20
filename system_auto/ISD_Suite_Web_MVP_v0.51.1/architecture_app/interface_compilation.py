"""Shared catalog naming, interface members and requirement allocations."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from .architecture_catalog import ArchitectureCatalog
from .bus_content import BusContentTemplates
from .models import ArchitecturePackage, ConnectionType, Direction, ProjectInterfaceTemplate, RequirementLink, RequirementRelation, RequirementTargetType, Signal, SignalType
from .topology import ensure_builtin_interface_definition

DOMAIN_COLORS = (
    "#2563EB", "#0F9F77", "#7C3AED", "#D97706", "#BE123C", "#0E7490",
    "#475569", "#DB2777", "#65A30D", "#4F46E5", "#B45309", "#0369A1",
)


DEFAULT_ARCHITECTURE_CATALOG = ArchitectureCatalog(
    Path(__file__).resolve().parents[1] / "Architecture_Catalog.json"
)


@dataclass(frozen=True)
class CompilationSummary:
    domain_count: int
    element_count: int
    signal_count: int
    allocation_count: int
    system_element_count: int = 0
    mechanical_element_count: int = 0
    software_element_count: int = 0
    function_element_count: int = 0


def _unique_hierarchy_name(package: ArchitecturePackage, preferred: str) -> str:
    used = {
        item.name.casefold()
        for domain in package.domains
        for item in [domain, *domain.elements]
    }
    base = preferred.strip() or "Architecture Element"
    candidate = base
    suffix = 2
    while candidate.casefold() in used:
        candidate = f"{base} ({suffix})"
        suffix += 1
    return candidate


def _project_template(package: ArchitecturePackage, value: str) -> ProjectInterfaceTemplate | None:
    query = value.strip().casefold()
    if not query:
        return None
    for template in package.interface_templates:
        keys = {template.id.casefold(), template.name.casefold(), *(item.casefold() for item in template.aliases)}
        if query in keys:
            return template
    return None


def _members_for_interface(
    package: ArchitecturePackage,
    builtins: BusContentTemplates,
    template_value: str,
    interface_name: str,
) -> tuple[list[Signal], str | None, int | None, bool]:
    project_template = _project_template(package, template_value)
    if project_template:
        link_port_token = builtins._replacement_from_instance(
            project_template.name, interface_name,
        ) or "Link_1"
        members = [
            Signal(
                name=(
                    member.name_pattern
                    .replace("{interface}", interface_name)
                    .replace("[Link/Port]", link_port_token)
                    .strip()
                    or interface_name
                ),
                direction=member.direction_from_host,
                pin_type=member.host_pin_type,
                active_low=member.active_low,
                template_member_key=member.name_pattern,
                description=member.description,
                properties={
                    "participantPinType": member.participant_pin_type,
                    "interfaceDefinitionId": project_template.id,
                    "interfaceDefinitionVersion": project_template.version,
                },
            )
            for member in project_template.members
        ]
        return members, project_template.id, project_template.version, False
    builtin = builtins.resolve_interface_template(template_value)
    if builtin:
        instance = builtins.named_interface_signals(builtin, interface_name)
        definition = ensure_builtin_interface_definition(package, builtins, builtin)
        members = [
            Signal(
                name=name,
                direction=Direction.INOUT,
                pin_type="BI",
                active_low=name.endswith("#") or name.endswith("_N"),
                template_member_key=instance.member_keys[index],
                properties={"template": builtin, "pinMappingStatus": "To Review"},
            )
            for index, name in enumerate(instance.signals)
        ]
        return members, definition.id, definition.version, False
    # Keep an unresolved logical link reviewable without inventing a fake
    # one-member electrical bus. A template assignment can materialize the
    # standardized members later.
    return [], None, None, True


def _interface_metadata(
    package: ArchitecturePackage,
    builtins: BusContentTemplates,
    template_value: str,
    proposed_port_type: str,
    proposed_signal_type: SignalType,
    proposed_connection_type: ConnectionType,
) -> tuple[str, SignalType, ConnectionType]:
    project_template = _project_template(package, template_value)
    if project_template:
        return (
            project_template.port_type,
            project_template.signal_type,
            project_template.connection_type,
        )
    builtin = builtins.resolve_interface_template(template_value)
    if builtin:
        inferred_port_type = builtin.replace("_[Link/Port]", "").replace("[Link/Port]", "").strip(" _-")
        port_type = proposed_port_type.strip()
        if not port_type or port_type.casefold() == "generic interface":
            port_type = inferred_port_type or "Interface"
        return port_type, SignalType.INTERFACE, ConnectionType.BUS
    return (
        proposed_port_type.strip() or proposed_signal_type.value,
        proposed_signal_type,
        proposed_connection_type,
    )


def _add_requirement_links(
    package: ArchitecturePackage,
    requirement_ids: list[str],
    target_type: RequirementTargetType,
    target_id: str,
    relation: RequirementRelation = RequirementRelation.SATISFIED_BY,
) -> None:
    valid = {item.id for item in package.requirements}
    existing = {(item.requirement_id, item.target_type, item.target_id) for item in package.requirement_links}
    for requirement_id in requirement_ids:
        key = (requirement_id, target_type, target_id)
        if requirement_id in valid and key not in existing:
            package.requirement_links.append(RequirementLink(
                requirement_id=requirement_id,
                target_type=target_type,
                target_id=target_id,
                relation=relation,
            ))
            existing.add(key)

