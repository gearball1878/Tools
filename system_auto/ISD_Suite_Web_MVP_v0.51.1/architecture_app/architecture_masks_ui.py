"""Typed hardware architecture input masks.

Explicit callbacks keep project state in the page controller.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
import json
from nicegui import ui
from pydantic import ValidationError
from .architecture_editing import move_architecture_element, move_architecture_port, update_architecture_object
from .bus_content import InterfaceInstance
from .architecture_bindings_ui import binding_inputs
from .models import ArchitectureElement, ArchitectureSignal, Connection, ConnectionEndpoint, ConnectionType, Direction, Domain, EndpointRole, InterfaceDefinition, InterfacePort, ProjectInterfaceTemplate, Signal, SignalType
from .signal_naming import normalize_generated_signal
from .requirements_service import interface_catalog_names
from .topology import ensure_builtin_interface_definition, next_interface_index

@dataclass(frozen=True)
class ArchitectureMasksUiViews:
    add_domain_dialog: Callable[..., Any]
    add_element_dialog: Callable[..., Any]
    add_port_dialog: Callable[..., Any]
    edit_architecture_signal_dialog: Callable[..., Any]
    edit_member_dialog: Callable[..., Any]
    edit_domain_dialog: Callable[..., Any]
    edit_element_dialog: Callable[..., Any]
    edit_port_dialog: Callable[..., Any]
    edit_connection_dialog: Callable[..., Any]
    connection_endpoint_choices: Callable[..., Any]
    endpoint_label: Callable[..., Any]


def create_architecture_masks_ui(
    *,
    COLOR_PALETTE,
    PIN_TYPES,
    architecture_catalog,
    bus_templates,
    color_palette,
    hierarchy_name_is_available,
    save,
    state,
) -> ArchitectureMasksUiViews:
    def add_domain_dialog() -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[600px] max-w-[94vw]"):
            ui.label("Domain hinzufügen").classes("text-xl font-bold")
            name = ui.input("Name", placeholder="z. B. Kommunikation").classes("w-full")
            domain_type = ui.select(
                architecture_catalog.domain_type_options(),
                value="GEN.OTHER",
                label="Technischer Domain Type",
                with_input=True,
            ).classes("w-full").props("use-input options-dense")
            initial_color = COLOR_PALETTE[len(state.package.domains) % len(COLOR_PALETTE)][0]
            color = color_palette(initial_color)
            description = ui.input("Beschreibung").classes("w-full")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat")
                def create() -> None:
                    value = (name.value or "").strip()
                    if not value:
                        ui.notify("Der Domainname darf nicht leer sein.", type="warning")
                        return
                    if not hierarchy_name_is_available(value):
                        ui.notify("Der Name wird bereits von einer Domain oder einem Architecture Element verwendet.", type="warning")
                        return
                    selected_type = architecture_catalog.resolve_domain_type(
                        domain_type.value or "GEN.OTHER"
                    )
                    domain = Domain(
                        name=value,
                        technical_name=architecture_catalog.allocate_domain_name(
                            state.package, selected_type,
                        ),
                        domain_type_id=selected_type,
                        technical_domain_ids=architecture_catalog.normalize_domain_type_ids(
                            [], selected_type,
                        ),
                        color=color["value"],
                        description=description.value,
                    )
                    state.package.domains.append(domain)
                    state.expanded_navigator_domain_ids.add(domain.id)
                    state.selected_id = domain.id
                    dialog.close(); save("Domain hinzugefügt")
                ui.button("Hinzufügen", on_click=create)
        dialog.open()

    def add_element_dialog(domain: Domain | None = None) -> None:
        if not state.package.domains:
            ui.notify("Lege zuerst eine Domain an.", type="warning")
            return
        parent_options = {item.id: item.name for item in state.package.domains}
        initial_parent = domain.id if domain else state.package.domains[0].id
        with ui.dialog() as dialog, ui.card().classes("w-[600px] max-w-[94vw]"):
            ui.label("Architecture Element hinzufügen").classes("text-xl font-bold")
            parent = ui.select(parent_options, value=initial_parent, label="Parent Domain").classes("w-full")
            name = ui.input("Name", placeholder="z. B. Sensor Interface").classes("w-full")
            role_type = ui.select(
                architecture_catalog.role_type_options(),
                value="GEN.FUNCTION_BLOCK",
                label="Generische AE-Rolle",
                with_input=True,
            ).classes("w-full").props("use-input options-dense")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat")
                def create() -> None:
                    target_domain = state.package.find_domain(parent.value)
                    if target_domain is None:
                        ui.notify("Bitte eine Parent Domain auswählen.", type="warning"); return
                    value = (name.value or "").strip()
                    if not value:
                        ui.notify("Der Name des Architecture Elements darf nicht leer sein.", type="warning")
                        return
                    if not hierarchy_name_is_available(value):
                        ui.notify("Der Name wird bereits von einer Domain oder einem Architecture Element verwendet.", type="warning")
                        return
                    selected_role = architecture_catalog.resolve_role_type(
                        role_type.value or "GEN.FUNCTION_BLOCK"
                    )
                    element = ArchitectureElement(
                        name=value,
                        technical_name=architecture_catalog.allocate_element_name(
                            state.package, selected_role,
                        ),
                        role_type_id=selected_role,
                        technical_domain_ids=architecture_catalog.normalize_domain_type_ids(
                            [], target_domain.domain_type_id,
                        ),
                    )
                    target_domain.elements.append(element)
                    state.expanded_navigator_domain_ids.add(target_domain.id)
                    state.expanded_navigator_element_ids.add(element.id)
                    state.selected_id = element.id
                    dialog.close(); save("Architecture Element hinzugefügt")
                ui.button("Hinzufügen", on_click=create)
        dialog.open()

    def add_port_dialog(_element: ArchitectureElement | None = None) -> None:
        """Create central, tool-neutral signal and interface definitions."""
        with ui.dialog() as dialog, ui.card().classes("w-[720px] max-w-[95vw]"):
            with ui.row().classes("w-full items-center"):
                ui.label("Interface oder Signal anlegen").classes("text-xl font-bold grow")
                ui.badge("Vorlagengebunden", color="blue-1").props("text-color=blue-9")
            ui.label(
                "Interfaces und Einzelsignale werden ausschließlich aus dem gemeinsamen Template-Katalog erzeugt. "
                "Ports und Verbindungen entstehen anschließend aus der Topologie."
            ).classes("subtle")

            with ui.row().classes("w-full gap-3"):
                family = ui.select(bus_templates.families(), value="Interface", label="Familie").classes("grow")
            with ui.column().classes("w-full rounded-xl border p-4 bg-slate-50 gap-3"):
                interface_options = interface_catalog_names(state.package, bus_templates)
                interface_template = ui.select(
                    interface_options,
                    value=interface_options[0] if interface_options else None,
                    label="Interface-Vorlage",
                ).classes("w-full")
                with ui.row().classes("w-full gap-3") as interface_index_row:
                    amount = ui.number("Anzahl Links", value=1, min=1, max=99, precision=0).classes("grow")
                    ui.label(
                        "Die Link-Nummer wird automatisch und dauerhaft vergeben. "
                        "Architekturports entstehen aus der Host-/Teilnehmerzuordnung."
                    ).classes("subtle grow")
                member_count = ui.number(
                    "Signale je Link", value=1, min=1, max=256, precision=0,
                ).classes("w-full")
                ui.label("Bei einer einadrigen Vorlage wird das Mitglied als IO0, IO1 … bzw. OUT0, OUT1 … erzeugt.").classes("subtle")

                semantic_description = ui.textarea(
                    "Semantische Beschreibung (optional)",
                    placeholder="Fachliche Bedeutung im Projekt; kein Bestandteil des Namens",
                ).props("outlined autogrow").classes("w-full")

                domain_bus = ui.select(bus_templates.bus_templates_for_family("Control"), value=bus_templates.bus_templates_for_family("Control")[0], label="Busgruppe").classes("w-full")
                signal_template = ui.select(bus_templates.control_signal_templates(), value=bus_templates.control_signal_templates()[0], label="Signalvorlage").classes("w-full")

                analog_bus = ui.select(bus_templates.analog_bus_templates(), value=bus_templates.analog_bus_templates()[0], label="Analog-Bus").classes("w-full")
                analog_signal = ui.select(bus_templates.analog_signal_templates(), value=bus_templates.analog_signal_templates()[0], label="Analogsignal").classes("w-full")

                voltage_type = ui.select(bus_templates.voltage_signal_templates(), value=bus_templates.voltage_signal_templates()[0], label="Versorgungstyp").classes("w-full")

                with ui.row().classes("w-full gap-3") as shared_details:
                    technical_domain = ui.select(bus_templates.domains(), value=bus_templates.domains()[0], label="Technische Domain").classes("grow")
                    additional_info = ui.input("Zusatz", value="Device").classes("grow")
                    voltage_frequency = ui.input("Spannung / Frequenz", placeholder="z. B. 3V3 oder 25MHz").classes("grow")

                memory_technology = ui.select(bus_templates.memory_technologies(), value=bus_templates.memory_technologies()[0], label="Speichertechnologie").classes("w-full")
                memory_subtechnology = ui.select([], label="Untertechnologie").classes("w-full")
                with ui.row().classes("w-full gap-3") as memory_details:
                    memory_config = ui.select(bus_templates.memory_configurations(), label="Konfiguration").classes("grow")
                    host_device = ui.input("Host-Kennung", value="Host").classes("grow")
                    memory_amount = ui.number("Anzahl Devices", value=1, min=1, max=16, precision=0).classes("grow")

                with ui.row().classes("w-full gap-3"):
                    default_direction = ui.select([x.value for x in Direction], value="inout", label="Initiale Signalrichtung").classes("grow")
                    default_pin_type = ui.select(PIN_TYPES, value="BI", label="ECAD Pin Type (Adapterzuordnung)", with_input=True).classes("grow")
                with ui.row().classes("w-full"):
                    active_low = ui.checkbox("Active Low")
                    differential = ui.checkbox("Differentiell", value=True)

            def update_memory_options() -> None:
                options = bus_templates.memory_subtechnologies(memory_technology.value)
                memory_subtechnology.options = options
                memory_subtechnology.value = options[0] if options else None
                memory_subtechnology.update()

            def update_family() -> None:
                current = family.value
                is_interface = current == "Interface"
                is_control_status = current in {"Control", "Status"}
                is_analog = current == "Analog"
                is_power = current == "Power"
                is_memory = current == "Memory"
                interface_template.set_visibility(is_interface)
                interface_index_row.set_visibility(is_interface)
                update_member_count()
                domain_bus.set_visibility(is_control_status)
                signal_template.set_visibility(is_control_status)
                analog_bus.set_visibility(is_analog)
                analog_signal.set_visibility(is_analog)
                voltage_type.set_visibility(is_power)
                shared_details.set_visibility(is_control_status or is_analog or is_power or is_memory)
                memory_technology.set_visibility(is_memory)
                memory_subtechnology.set_visibility(is_memory)
                memory_details.set_visibility(is_memory)
                active_low.set_visibility(is_control_status)
                differential.set_visibility(is_analog)
                if current == "Control":
                    domain_bus.options = bus_templates.bus_templates_for_family("Control")
                    signal_template.options = bus_templates.control_signal_templates()
                elif current == "Status":
                    domain_bus.options = bus_templates.bus_templates_for_family("Status")
                    signal_template.options = bus_templates.status_signal_templates()
                if is_control_status:
                    domain_bus.value = domain_bus.options[0]
                    signal_template.value = signal_template.options[0]
                    domain_bus.update(); signal_template.update()

            def update_member_count() -> None:
                selected = interface_template.value
                project_template = next((item for item in state.package.interface_templates
                                         if not item.deprecated and item.name == selected), None)
                count = (len(project_template.members) if project_template else
                         len(bus_templates.raw_interface_members(selected)) if selected else 0)
                member_count.set_visibility(family.value == "Interface" and count == 1)

            family.on_value_change(lambda _: update_family())
            interface_template.on_value_change(lambda _: update_member_count())
            memory_technology.on_value_change(lambda _: update_memory_options())
            update_memory_options(); update_family()

            def make_architecture_signals(instance: InterfaceInstance, family_name: str) -> list[ArchitectureSignal]:
                members = [Signal(
                    name=signal_name,
                    direction=Direction(default_direction.value),
                    pin_type=default_pin_type.value,
                    active_low=bool(active_low.value or "#" in signal_name),
                    template_member_key=(
                        instance.member_keys[index]
                        if index < len(instance.member_keys) else ""
                    ),
                    properties={"family": instance.family, "template": instance.template_name},
                ) for index, signal_name in enumerate(instance.signals)]
                type_map = {
                    "Interface": SignalType.INTERFACE,
                    "Control": SignalType.CONTROL,
                    "Status": SignalType.STATUS,
                    "Analog": SignalType.DIFFERENTIAL if len(members) > 1 else SignalType.ANALOG,
                    "Power": SignalType.POWER,
                    "Memory": SignalType.MEMORY,
                }
                common_properties = {
                        "family": instance.family,
                        "template": instance.template_name,
                        "busContentName": instance.name,
                        "generatedBy": "InterfaceSignalWizard",
                }
                if family_name == "Interface" and len(instance.member_keys) > 1:
                    template_members = (bus_templates.raw_interface_members(instance.template_name)
                                        if instance.template_name in bus_templates.interface_templates() else [])
                    if len(template_members) == 1:
                        common_properties["memberCount"] = len(instance.member_keys)
                if family_name in {"Interface", "Memory"}:
                    return [ArchitectureSignal(
                        name=instance.name,
                        signal_type=type_map[family_name],
                        connection_type=ConnectionType.BUS,
                        bus_contents=members,
                        description=semantic_description.value or "",
                        interface_kind="Link" if family_name == "Interface" else None,
                        instance_index=instance.index if family_name == "Interface" else None,
                        catalog_family=family_name,
                        catalog_template=instance.template_name,
                        catalog_status="Bound",
                        attributes={"xpedArchId": "", "xpedScmId": ""},
                        properties=common_properties,
                    )]
                return [ArchitectureSignal(
                    name=member.name,
                    signal_type=type_map[family_name],
                    connection_type=ConnectionType.NET,
                    bus_contents=[member],
                    description=semantic_description.value or "",
                    catalog_family=family_name,
                    catalog_template=instance.template_name,
                    catalog_status="Bound",
                    attributes={"xpedArchId": "", "xpedScmId": ""},
                    properties=common_properties,
                ) for member in members]

            def create() -> None:
                try:
                    current = family.value
                    instances: list[InterfaceInstance]
                    selected_project_template: ProjectInterfaceTemplate | None = None
                    if current == "Interface":
                        selected_project_template = next((
                            item for item in state.package.interface_templates
                            if not item.deprecated and item.name == interface_template.value
                        ), None)
                        if selected_project_template:
                            instances = []
                            for _ in range(int(amount.value)):
                                index = next_interface_index(
                                    state.package,
                                    bus_templates,
                                    selected_project_template.name,
                                    "Link",
                                )
                                instance_name = bus_templates.canonical_instance_name(
                                    selected_project_template.name, "Link", index,
                                )
                                member_patterns = [member.name_pattern for member in selected_project_template.members]
                                if len(member_patterns) == 1:
                                    member_patterns, _ = bus_templates._vector_members(
                                        member_patterns, int(member_count.value))
                                signal_names = [
                                    pattern
                                    .replace("{interface}", instance_name)
                                    .replace("[Link/Port]", f"Link_{index}")
                                    for pattern in member_patterns
                                ]
                                instances.append(InterfaceInstance(
                                    instance_name,
                                    signal_names,
                                    selected_project_template.name,
                                    index,
                                    "Link",
                                    "interface",
                                    member_patterns,
                                ))
                        else:
                            instances = []
                            for _ in range(int(amount.value)):
                                index = next_interface_index(
                                    state.package, bus_templates, interface_template.value, "Link",
                                )
                                instances.append(bus_templates.interface_signals(
                                    interface_template.value, index, "Link",
                                    int(member_count.value) if len(bus_templates.raw_interface_members(interface_template.value)) == 1 else 1,
                                ))
                    elif current in {"Control", "Status"}:
                        instances = [bus_templates.control_status_instance(current, domain_bus.value, signal_template.value, additional_info.value, voltage_frequency.value, active_low.value)]
                    elif current == "Analog":
                        instances = [bus_templates.analog_instance(analog_bus.value, analog_signal.value, technical_domain.value, additional_info.value, differential.value, voltage_frequency.value)]
                    elif current == "Power":
                        instances = [bus_templates.power_instance(voltage_type.value, technical_domain.value, additional_info.value, voltage_frequency.value)]
                    else:
                        instances = bus_templates.memory_instances(memory_technology.value, memory_subtechnology.value, technical_domain.value, host_device.value, int(memory_amount.value), memory_config.value or "")

                    existing = {signal.name.casefold() for signal in state.package.signals}
                    created: list[ArchitectureSignal] = []
                    renamed: list[tuple[str, str]] = []
                    for instance in instances:
                        generated = make_architecture_signals(instance, current)
                        for item in generated:
                            renamed.extend(normalize_generated_signal(item))
                        if selected_project_template and generated:
                            generated[0].signal_type = selected_project_template.signal_type
                            generated[0].connection_type = selected_project_template.connection_type
                            generated[0].port_type = selected_project_template.port_type
                            generated[0].interface_definition_id = selected_project_template.id
                            generated[0].interface_definition_version = selected_project_template.version
                            generated[0].properties["projectTemplateId"] = selected_project_template.id
                            if len(selected_project_template.members) == 1 and len(generated[0].bus_contents) > 1:
                                generated[0].properties["memberCount"] = len(generated[0].bus_contents)
                            for member, definition in zip(
                                generated[0].bus_contents,
                                selected_project_template.members * len(generated[0].bus_contents),
                            ):
                                member.direction = definition.direction_from_host
                                member.pin_type = definition.host_pin_type
                                member.active_low = definition.active_low
                                member.description = definition.description
                                member.properties["participantPinType"] = definition.participant_pin_type
                        elif current == "Interface" and generated:
                            definition = ensure_builtin_interface_definition(
                                state.package, bus_templates, instance.template_name,
                            )
                            generated[0].port_type = definition.port_type
                            generated[0].interface_definition_id = definition.id
                            generated[0].interface_definition_version = definition.version
                        for signal in generated:
                            if signal.name.casefold() in existing:
                                raise ValueError(f"Der Signalname {signal.name!r} existiert bereits.")
                            existing.add(signal.name.casefold()); created.append(signal)
                        if selected_project_template and not any(
                            item.id == selected_project_template.id
                            for item in state.package.interface_definitions
                        ):
                            state.package.interface_definitions.append(InterfaceDefinition(
                                id=selected_project_template.id,
                                name=selected_project_template.name,
                                version=selected_project_template.version,
                                family=selected_project_template.family,
                                port_type=selected_project_template.port_type,
                                source="ProjectInterfaceTemplate",
                                aliases=list(selected_project_template.aliases),
                                members=[
                                    item.model_copy(deep=True)
                                    for item in selected_project_template.members
                                ],
                                description=selected_project_template.description,
                            ))
                    state.package.signals.extend(created)
                    state.selected_id = created[-1].id
                    dialog.close(); save(f"{len(created)} Signaldefinition(en) hinzugefügt")
                    if renamed:
                        ui.notify("Redundante Signalnamen bereinigt: " + ", ".join(
                            f"{before} → {after}" for before, after in renamed[:5]
                        ), type="info")
                except Exception as error:
                    ui.notify(str(error), type="negative", close_button=True)

            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat")
                ui.button("Zum Signalkatalog hinzufügen", icon="playlist_add", on_click=create)
        dialog.open()

    def edit_architecture_signal_dialog(signal: ArchitectureSignal) -> None:
        template_bound = signal.catalog_status == "Bound" or bool(
            signal.signal_type == SignalType.INTERFACE and signal.interface_definition_id
        )
        member_text = "\n".join(
            f"{member.name} | {member.direction.value} | {member.pin_type} | "
            f"{'true' if member.active_low else 'false'}"
            for member in signal.bus_contents
        )
        with ui.dialog() as dialog, ui.card().classes("w-[760px] max-w-[96vw] p-6 gap-4"):
            from .help_ui import mask_help
            mask_help(dialog,'hardware',signal,mask='Netz-/Busdefinition bearbeiten')
            ui.label("Signal- oder Interfacedefinition bearbeiten").classes("text-xl font-bold")
            with ui.row().classes("w-full items-center gap-2"):
                ui.badge(
                    signal.catalog_family or "Nicht klassifiziert",
                    color="blue-1" if template_bound else "amber-2",
                ).props("text-color=grey-9")
                ui.label(
                    signal.catalog_template or "Keine gültige Template-Bindung"
                ).classes("text-sm font-mono")
                ui.badge(
                    "Kataloggebunden" if template_bound else "Altbestand · Zuordnung offen",
                    color="green-2" if template_bound else "amber-2",
                ).props("text-color=grey-9")
            with ui.row().classes("w-full gap-3"):
                name = ui.input("Name", value=signal.name).classes("grow")
                port_type = ui.input("Fachlicher Port Type", value=signal.port_type).classes("grow")
            with ui.row().classes("w-full gap-3"):
                signal_type = ui.select(
                    [item.value for item in SignalType],
                    value=signal.signal_type.value,
                    label="Signaltyp",
                ).classes("grow")
                connection_type = ui.select(
                    [item.value for item in ConnectionType],
                    value=signal.connection_type.value,
                    label="Netz oder Bus",
                ).classes("grow")
            description = ui.textarea("Beschreibung", value=signal.description).props("outlined autogrow").classes("w-full")
            netclass = ui.select({c.name:c.name for c in state.package.net_classes}, value=signal.realization_attributes.get("netClass"),label="Bus-Standardklasse" if signal.connection_type==ConnectionType.BUS else "Netzklasse",clearable=True).props("use-input").classes("w-full")
            members = ui.textarea(
                "Mitgliedssignale",
                value=member_text,
                placeholder="DATA | inout | BI | false\nRESET_N | in | IN | true",
            ).props("outlined rows=8").classes("w-full font-mono")
            if template_bound:
                ui.label(
                    "Änderungen an einer kataloggebundenen Definition machen diese zur "
                    "projektspezifischen Anpassung. ID und Referenzen bleiben erhalten."
                ).classes("text-xs text-blue-700 bg-blue-50 border border-blue-200 rounded-lg p-2")
            ui.label(
                "Format: Name | Richtung (in/out/inout/passive) | ECAD Pin Type | Active Low (true/false). "
                "Bei einem Einzelsignal ist genau eine Zeile üblich."
            ).classes("text-xs text-slate-500")
            apply_bindings = binding_inputs(state.package,signal)
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")
                def apply() -> None:
                    new_name = (name.value or "").strip()
                    if not new_name or any(
                        item.id != signal.id and item.name.casefold() == new_name.casefold()
                        for item in state.package.signals
                    ):
                        ui.notify("Der Name muss im Gesamtsystem eindeutig sein.", type="warning")
                        return
                    parsed_members: list[Signal] = []
                    existing_by_name = {item.name.casefold(): item for item in signal.bus_contents}
                    seen_names: set[str] = set()
                    try:
                        for line in (members.value or "").splitlines():
                            if not line.strip():
                                continue
                            fields = [item.strip() for item in line.split("|")]
                            if len(fields) != 4:
                                raise ValueError(f"Ungültige Mitgliedszeile: {line}")
                            member_name = fields[0]
                            key = member_name.casefold()
                            if not member_name or key in seen_names:
                                raise ValueError(f"Doppelter oder leerer Mitgliedsname: {member_name or '—'}")
                            seen_names.add(key)
                            active_value = fields[3].casefold()
                            if active_value not in {"true", "false", "ja", "nein", "1", "0"}:
                                raise ValueError(f"Active Low muss true oder false sein: {line}")
                            previous_member = existing_by_name.get(key)
                            if previous_member and previous_member.id in {item.id for item in parsed_members}:
                                previous_member = None
                            if previous_member is None and len(parsed_members) < len(signal.bus_contents):
                                candidate_member = signal.bus_contents[len(parsed_members)]
                                if candidate_member.id not in {item.id for item in parsed_members}:
                                    previous_member = candidate_member
                            member = (previous_member.model_copy(deep=True)
                                      if previous_member else Signal(name=member_name))
                            member.name = member_name
                            member.direction = Direction(fields[1].casefold())
                            if previous_member is None or member.direction!=previous_member.direction:
                                member.properties["directionReviewed"] = True
                            member.pin_type = fields[2] or "BI"
                            member.active_low = active_value in {"true", "ja", "1"}
                            parsed_members.append(member)
                    except ValueError as error:
                        ui.notify(str(error), type="negative", close_button=True)
                        return
                    if not parsed_members:
                        ui.notify("Mindestens ein Mitgliedssignal ist erforderlich.", type="warning")
                        return
                    document = signal.model_dump(mode="json")
                    from .netclasses import set_assignment
                    draft_signal=signal.model_copy(deep=True)
                    set_assignment(draft_signal,netclass.value,'Explizite Auswahl')
                    document['realization_attributes']=draft_signal.realization_attributes
                    document['attributes']=draft_signal.attributes
                    document.update(
                        name=new_name,
                        port_type=(port_type.value or "").strip(),
                        signal_type=SignalType(signal_type.value).value,
                        connection_type=ConnectionType(connection_type.value).value,
                        description=description.value or "",
                        bus_contents=[item.model_dump(mode="json") for item in parsed_members],
                    )
                    previous = state.package
                    try:
                        state.package = update_architecture_object(
                            state.package, signal.id, json.dumps(document), bus_templates,
                        )
                        state.package=apply_bindings(state.package)
                        if not save("Signal- oder Interfacedefinition aktualisiert"):
                            state.package = previous
                            return
                    except (ValueError, ValidationError) as error:
                        state.package = previous
                        ui.notify(str(error), type="negative", close_button=True)
                        return
                    state.selected_id = signal.id
                    dialog.close()
                ui.button("Speichern", icon="save", on_click=apply).props("no-caps")
                pass
        dialog.open()

    def edit_member_dialog(member):
        with ui.dialog() as dialog, ui.card().classes('w-[650px] max-w-[94vw] p-5 gap-3'):
            from .help_ui import mask_help
            mask_help(dialog,'hardware',member,mask='Busmitglied bearbeiten')
            ui.label('Busmitglied bearbeiten').classes('text-xl font-bold')
            name = ui.input('Netzname', value=member.name).classes('w-full')
            description = ui.textarea('Beschreibung', value=member.description).classes('w-full')
            direction = ui.select({v.value:v.value for v in Direction},value=member.direction.value,label='Signalrichtung aus Sicht des Hosts').classes('w-full')
            reviewed = ui.checkbox('Signalrichtung geprüft',value=bool(member.properties.get('directionReviewed')))
            netclass = ui.select({c.name:c.name for c in state.package.net_classes},value=member.realization_attributes.get('netClass'),label='Eigene Netzklasse (leer: vom Bus)',clearable=True).props('use-input').classes('w-full')
            apply_bindings = binding_inputs(state.package,member)
            def accept():
                document = member.model_dump(mode='json')
                document.update(name=name.value,description=description.value or '',direction=direction.value)
                document['properties']['directionReviewed']=bool(reviewed.value or direction.value!=member.direction.value)
                from .netclasses import set_assignment
                draft_member=member.model_copy(deep=True)
                set_assignment(draft_member,netclass.value,'Explizite Auswahl')
                document['realization_attributes']=draft_member.realization_attributes
                document['attributes']=draft_member.attributes
                previous=state.package
                try:
                    state.package=update_architecture_object(previous,member.id,json.dumps(document),bus_templates)
                    state.package=apply_bindings(state.package)
                    if not save('Busmitglied gespeichert'):state.package=previous;return
                    dialog.close()
                except (ValueError,ValidationError) as error:
                    state.package=previous;ui.notify(str(error),type='negative')
            ui.button('Speichern',on_click=accept)
            ui.button('Abbrechen',on_click=dialog.close).props('flat')
        dialog.open()

    def edit_domain_dialog(domain: Domain) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[620px] max-w-[94vw]"):
            from .help_ui import mask_help
            mask_help(dialog,'hardware',domain,mask='Domäne bearbeiten')
            ui.label("Domain konfigurieren").classes("text-xl font-bold")
            ui.label(domain.id).classes("text-xs text-slate-500")
            name = ui.input("Name", value=domain.name).classes("w-full")
            task = ui.textarea("Aufgabe / Verantwortung", value=domain.requirement_attributes.get("function") or "").classes("w-full")
            technical_name = ui.input("Technischer ECAD-Key", value=domain.technical_name).classes("w-full font-mono")
            domain_type = ui.select(
                architecture_catalog.domain_type_options(),
                value=domain.domain_type_id,
                label="Technischer Domain Type",
                with_input=True,
            ).classes("w-full").props("use-input options-dense")
            ui.label(
                "Der technische Key bleibt bei einer fachlichen Umbenennung stabil."
            ).classes("subtle")
            color = color_palette(domain.color)
            description = ui.textarea("Beschreibung", value=domain.description).classes("w-full")
            ui.label(f"{len(domain.elements)} Architecture Elements").classes("subtle")
            apply_bindings = binding_inputs(state.package,domain)
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat")
                def apply() -> None:
                    value = (name.value or "").strip()
                    if not value:
                        ui.notify("Der Domainname darf nicht leer sein.", type="warning")
                        return
                    if not hierarchy_name_is_available(value, domain.id):
                        ui.notify("Der Name wird bereits von einer Domain oder einem Architecture Element verwendet.", type="warning")
                        return
                    document = domain.model_dump(mode="json")
                    document["requirement_attributes"]["function"] = task.value or None
                    document.update(
                        name=value,
                        technical_name=str(technical_name.value or "").strip(),
                        domain_type_id=architecture_catalog.resolve_domain_type(domain_type.value or "GEN.OTHER"),
                        color=color["value"], description=str(description.value or ""),
                    )
                    previous = state.package
                    try:
                        state.package = update_architecture_object(
                            previous, domain.id, json.dumps(document), bus_templates,
                        )
                        state.package=apply_bindings(state.package)
                        if not save("Domain aktualisiert"):
                            state.package = previous
                            return
                    except (ValueError, ValidationError) as error:
                        state.package = previous
                        ui.notify(f"Domain nicht übernommen: {error}", type="negative", close_button=True)
                        return
                    dialog.close()
                ui.button("Übernehmen", on_click=apply)
                pass
        dialog.open()

    def edit_element_dialog(domain: Domain, element: ArchitectureElement) -> None:
        parent_options = {item.id: item.name for item in state.package.domains}
        with ui.dialog() as dialog, ui.card().classes("w-[620px] max-w-[94vw]"):
            from .help_ui import mask_help
            mask_help(dialog,'hardware',element,mask='AE bearbeiten')
            ui.label("Architecture Element konfigurieren").classes("text-xl font-bold")
            ui.label(element.id).classes("text-xs text-slate-500")
            parent = ui.select(parent_options, value=domain.id, label="Parent Domain").classes("w-full")
            name = ui.input("Name", value=element.name).classes("w-full")
            task = ui.textarea("Aufgabe / Verantwortung", value=element.requirement_attributes.get("function") or "").classes("w-full")
            technical_name = ui.input("Technischer ECAD-Key", value=element.technical_name).classes("w-full font-mono")
            role_type = ui.select(
                architecture_catalog.role_type_options(),
                value=element.role_type_id,
                label="Generische AE-Rolle",
                with_input=True,
            ).classes("w-full").props("use-input options-dense")
            description = ui.textarea("Beschreibung", value=element.description).classes("w-full")
            ui.label(f"{len(element.ports)} Interface-Ports").classes("subtle")
            apply_bindings = binding_inputs(state.package,element)
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat")
                def apply() -> None:
                    target = state.package.find_domain(parent.value)
                    if target is None:
                        ui.notify("Bitte eine Parent Domain auswählen.", type="warning"); return
                    value = (name.value or "").strip()
                    if not value:
                        ui.notify("Der Name des Architecture Elements darf nicht leer sein.", type="warning")
                        return
                    if not hierarchy_name_is_available(value, element.id):
                        ui.notify("Der Name wird bereits von einer Domain oder einem Architecture Element verwendet.", type="warning")
                        return
                    document = element.model_dump(mode="json")
                    document["requirement_attributes"]["function"] = task.value or None
                    document.update(
                        name=value,
                        technical_name=str(technical_name.value or "").strip(),
                        role_type_id=architecture_catalog.resolve_role_type(role_type.value or "GEN.FUNCTION_BLOCK"),
                        description=str(description.value or ""),
                    )
                    previous = state.package
                    try:
                        candidate = update_architecture_object(
                            previous, element.id, json.dumps(document), bus_templates,
                        )
                        if target.id != domain.id:
                            candidate = move_architecture_element(candidate, element.id, target.id)
                        state.package = apply_bindings(candidate)
                        if not save("Architecture Element aktualisiert"):
                            state.package = previous
                            return
                    except (ValueError, ValidationError) as error:
                        state.package = previous
                        ui.notify(f"Architecture Element nicht übernommen: {error}", type="negative", close_button=True)
                        return
                    dialog.close()
                ui.button("Übernehmen", on_click=apply)
                pass
        dialog.open()

    def edit_port_dialog(domain: Domain, element: ArchitectureElement, port: InterfacePort) -> None:
        managed = state.package.find_architecture_signal(
            str(port.interface_link_id or port.properties.get("architectureSignalId") or "")
        )
        bound = managed or next((c for c in state.package.connections if any(e.port_id==port.id for e in c.endpoints)),None)
        element_options = {
            item.id: f"{d.name} / {item.name}"
            for d in state.package.domains for item in d.elements
        }
        with ui.dialog() as dialog, ui.card().classes("w-[640px] max-w-[95vw] p-5 gap-3"):
            from .help_ui import mask_help
            mask_help(dialog,'hardware',port,mask='Port bearbeiten')
            ui.label("Architekturport bearbeiten").classes("text-xl font-bold")
            ui.input("Unveränderliche Objekt-ID", value=port.id).props("readonly outlined dense").classes("w-full")
            if managed:
                ui.label(
                    "Dieser Port gehört zu einem Signal. Änderungen an Name, Rolle und Netzart "
                    "werden mit Signal und Verbindung abgestimmt."
                ).classes("text-sm text-blue-800")
            parent = ui.select(
                element_options, value=element.id, label="Parent Architecture Element",
            ).classes("w-full")
            name = ui.input("Portname", value=port.name).classes("w-full")
            if managed: name.disable()
            # Port types are extensible through project templates and imports.
            # NiceGUI rejects an initial select value absent from its options,
            # which previously prevented this entire dialog from opening.

            role = ui.select(
                {"":"Offen", "Host":"Host", "Participant":"Teilnehmer"}, value=port.role, label="Rolle aus Topologie" if bound else "Vorläufige Rolle",
            ).classes("w-full")
            if bound:
                role.disable()
            ui.label('Host rechts · Teilnehmer links. Elektrische Pintypen werden aus den Signalen abgeleitet.').classes('text-xs')
            description = ui.textarea(
                "Beschreibung", value=port.description,
            ).props("outlined autogrow").classes("w-full")
            from .property_inputs import custom_inputs
            apply_custom=custom_inputs(state.package,port,include_system=True)
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply() -> None:
                    if not (name.value or "").strip():
                        ui.notify("Portname darf nicht leer sein.", type="warning")
                        return
                    document = port.model_dump(mode="json")
                    document.update(
                        name=name.value.strip(), port_type=port.port_type,
                        role=str(role.value or ""), side="Auto",
                        connection_type=port.connection_type.value,
                        description=str(description.value or ""),
                    )
                    previous = state.package
                    try:
                        candidate = update_architecture_object(
                            previous, port.id, json.dumps(document), bus_templates,
                        )
                        if parent.value != element.id:
                            candidate = move_architecture_port(
                                candidate, port.id, str(parent.value), bus_templates,
                            )
                        apply_custom(candidate.find_port(port.id)[2])
                        state.package = candidate
                        if not save("Architekturport aktualisiert"):
                            state.package = previous
                            return
                    except (ValueError, ValidationError) as error:
                        state.package = previous
                        ui.notify(f"Port nicht übernommen: {error}", type="negative", close_button=True)
                        return
                    state.selected_id = port.id
                    dialog.close()

                ui.button("Übernehmen", on_click=apply).props("no-caps")
                pass
        dialog.open()

    def connection_endpoint_choices() -> dict[str, tuple[str, str]]:
        return {
            f"{domain.name} / {element.name} / {port.name}": (element.id, port.id)
            for domain in state.package.domains for element in domain.elements for port in element.ports
        }

    def endpoint_label(endpoint: ConnectionEndpoint) -> str:
        for label, ids in connection_endpoint_choices().items():
            if ids == (endpoint.element_id, endpoint.port_id):
                return label
        return "Unbekannter Endpunkt"

    def edit_connection_dialog(connection: Connection) -> None:
        choices = connection_endpoint_choices()
        managed_signal = state.package.find_architecture_signal(connection.signal_id or "")
        host_labels = [label for label, ids in choices.items()
                       if managed_signal or state.package.find_port(ids[1])[2].role == "Host"]
        participant_labels = [label for label, ids in choices.items()
                              if managed_signal or state.package.find_port(ids[1])[2].role == "Participant"]
        if not host_labels or not participant_labels:
            ui.notify("Für eine Interface-Verbindung werden ein Host und mindestens ein Participant benötigt.", type="warning"); return
        current_source = endpoint_label(connection.endpoints[0]) if connection.endpoints else None
        current_targets = [endpoint_label(endpoint) for endpoint in connection.endpoints[1:]]
        with ui.dialog() as dialog, ui.card().classes("w-[620px]"):
            from .help_ui import mask_help
            mask_help(dialog,'hardware',connection,mask='Verbindung bearbeiten')
            ui.label("Verbindung konfigurieren").classes("text-xl font-bold")
            ui.label(connection.id).classes("text-xs text-slate-500")
            name = ui.input("Name", value=connection.name).classes("w-full")
            connection_type = ui.select([x.value for x in ConnectionType], value=connection.connection_type.value, label="Verbindungsart").classes("w-full")
            if managed_signal:ui.button('Netzklasse bearbeiten',on_click=lambda:(dialog.close(),edit_architecture_signal_dialog(managed_signal))).props('outline no-caps')
            description = ui.textarea("Beschreibung", value=connection.description).classes("w-full")
            source = ui.select(host_labels, value=current_source, label="Host").classes("w-full")
            destination = ui.select(participant_labels, value=current_targets, label="Teilnehmer", multiple=True).classes("w-full").props("use-chips")
            from .property_inputs import custom_inputs
            apply_custom=custom_inputs(state.package,connection,include_system=True)
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat")
                def apply() -> None:
                    participant_values = list(destination.value or [])
                    if not source.value or not participant_values:
                        ui.notify("Host und mindestens ein Participant werden benötigt.", type="warning"); return
                    source_ids = choices[source.value]
                    document = connection.model_dump(mode="json")
                    document.update(
                        name=str(name.value or "").strip() or connection.name,
                        description=str(description.value or ""),
                        connection_type=str(connection_type.value),
                        endpoints=[
                            ConnectionEndpoint(element_id=source_ids[0], port_id=source_ids[1], role=EndpointRole.HOST).model_dump(mode="json"),
                            *(ConnectionEndpoint(element_id=choices[label][0], port_id=choices[label][1], role=EndpointRole.PARTICIPANT).model_dump(mode="json") for label in participant_values),
                        ],
                    )
                    previous = state.package
                    try:
                        state.package = update_architecture_object(
                            previous, connection.id, json.dumps(document), bus_templates,
                        )
                        apply_custom(next(c for c in state.package.connections if c.id==connection.id))
                        if not save("Verbindung aktualisiert"):
                            state.package = previous
                            return
                    except (ValueError, ValidationError) as error:
                        state.package = previous
                        ui.notify(f"Verbindung nicht übernommen: {error}", type="negative", close_button=True)
                        return
                    dialog.close()
                ui.button("Übernehmen", on_click=apply)
                pass
        dialog.open()


    return ArchitectureMasksUiViews(
        add_domain_dialog=add_domain_dialog,
        add_element_dialog=add_element_dialog,
        add_port_dialog=add_port_dialog,
        edit_architecture_signal_dialog=edit_architecture_signal_dialog,
        edit_member_dialog=edit_member_dialog,
        edit_domain_dialog=edit_domain_dialog,
        edit_element_dialog=edit_element_dialog,
        edit_port_dialog=edit_port_dialog,
        edit_connection_dialog=edit_connection_dialog,
        connection_endpoint_choices=connection_endpoint_choices,
        endpoint_label=endpoint_label,
    )
