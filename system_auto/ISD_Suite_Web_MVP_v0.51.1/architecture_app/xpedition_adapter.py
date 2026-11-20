from __future__ import annotations

from .bus_content import BusContentTemplates
from .models import ArchitecturePackage


def buscontent_groups(
    package: ArchitecturePackage,
    templates: BusContentTemplates,
) -> dict[str, list[str]]:
    """Materialize Xpedition Link and Port bus contents from the generic SPOT model."""
    grouped: dict[str, list[str]] = {
        signal.name: [member.name for member in signal.bus_contents] or [signal.name]
        for signal in package.signals
    }
    for domain in package.domains:
        for element in domain.elements:
            for port in element.ports:
                group = str(port.properties.get("busContentName") or port.name)
                generated_members: list[str] = []
                project_template = next((
                    item for item in package.interface_templates
                    if item.id == port.interface_definition_id
                ), None)
                if project_template:
                    token = templates._replacement_from_instance(
                        project_template.name, port.name,
                    ) or "Port_1"
                    generated_members = [
                        member.name_pattern
                        .replace("{interface}", port.name)
                        .replace("[Link/Port]", token)
                        for member in project_template.members
                    ]
                elif port.interface_definition_id:
                    resolved = templates.resolve_interface_template(
                        port.interface_definition_id
                    )
                    if resolved:
                        generated_members = templates.named_interface_signals(
                            resolved, port.name,
                        ).signals
                grouped.setdefault(group, generated_members)
                # Compatibility for projects predating the architecture-level
                # Link/Port separation.
                for signal in port.signals:
                    if signal.name not in grouped[group]:
                        grouped[group].append(signal.name)
    return grouped


def export_buscontents_text(
    package: ArchitecturePackage,
    templates: BusContentTemplates,
) -> str:
    grouped = buscontent_groups(package, templates)
    content = "\n".join(
        f"{name} {','.join(signals)}" for name, signals in grouped.items()
    )
    return content + ("\n" if content else "")
