from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from nicegui import ui

from .identity import show_sha_identity
from .attribute_spaces import render_attribute_spaces
from .integration_ui import render_integration_panel
from .technical_values_ui import render_technical_values
from .models import DesignMaturity, InterfaceClass, InterfaceRequirement, MechanicalComponent, MechanicalComponentKind, MechanicalConstraint, MechanicalConstraintKind, RequirementClassification, RequirementLink, RequirementMaturity, RequirementPriority, RequirementRelation, RequirementTargetType, RealizationProvenance, SoftwareComponent, SoftwareComponentKind, SoftwareDomain, SoftwareWorkItem, SubstitutionPolicy, WorkItemStatus
from .requirements_service import delete_interface_requirement
from .traceability import project_objects


@dataclass
class DevelopmentViews:
    mechanics_workspace: Callable[[], None]
    software_workspace: Callable[[], None]
    navigator: Callable[[str], None]
    inspector: Callable[[str], None]
    refresh: Callable[..., None]
    reset: Callable[[], None]
    select: Callable[[str, str], None]
    selected_object: Callable[..., Any]


def create_development_views(
    page_state: Any,
    save: Callable[..., bool],
    edit_all_fields: Callable[[str], None] | None = None,
) -> DevelopmentViews:
    selection: dict[str, str | None] = {"kind": None, "id": None}
    view_state = {"space": "mechanics"}

    def package():
        return page_state.package

    def lines(value: str) -> list[str]:
        return [item.strip() for item in value.splitlines() if item.strip()]

    def parse_properties(value: str) -> dict[str, str] | None:
        result: dict[str, str] = {}
        for line in value.splitlines():
            if not line.strip():
                continue
            key, separator, item_value = line.partition(":")
            if not separator or not key.strip() or not item_value.strip():
                ui.notify(f"Ungültige Eigenschaftszeile: {line}", type="warning")
                return None
            result[key.strip()] = item_value.strip()
        return result

    def requirement_options(*classifications: RequirementClassification) -> dict[str, str]:
        allowed = set(classifications)
        return {
            item.id: f"{item.identifier or item.id[:10]} · {item.title}"
            for item in package().requirements
            if not allowed or item.classification in allowed
        }

    def element_options() -> dict[str, str]:
        return {
            element.id: f"{domain.name} · {element.name}"
            for domain in package().domains
            for element in domain.elements
        }

    def _sync_requirement_links(
        target_type: RequirementTargetType,
        target_id: str,
        requirement_ids: list[str],
        relation: RequirementRelation = RequirementRelation.SATISFIED_BY,
    ) -> None:
        package().requirement_links = [
            item for item in package().requirement_links
            if not (item.target_type == target_type and item.target_id == target_id)
        ]
        package().requirement_links.extend(
            RequirementLink(
                requirement_id=requirement_id,
                target_type=target_type,
                target_id=target_id,
                relation=relation,
            )
            for requirement_id in dict.fromkeys(requirement_ids)
        )

    def selected_object() -> object | None:
        object_id = selection["id"]
        if not object_id:
            return None
        finders = {
            "mechanical_component": package().find_mechanical_component,
            "mechanical_constraint": package().find_mechanical_constraint,
            "software_component": package().find_software_component,
            "software_work_item": package().find_software_work_item,
            "interface": package().find_interface_requirement,
        }
        if selection['kind']=='function_element':return next((f for f in package().function_elements if f.id==object_id),None)
        finder = finders.get(selection["kind"] or "")
        return finder(object_id) if finder else None

    def select(kind: str, object_id: str) -> None:
        selection.update(kind=kind, id=object_id)
        navigator_view.refresh(view_state["space"])
        inspector_view.refresh(view_state["space"])

    def reset() -> None:
        selection.update(kind=None, id=None)

    def confirm_delete(title: str, message: str, apply_delete: Callable[[], None]) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[520px] max-w-[94vw] p-6 gap-4"):
            ui.label(title).classes("text-xl font-bold")
            ui.label(message).classes("text-sm text-slate-600")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply() -> None:
                    from .traceability import project_objects,remove_deleted_references
                    before={oid for items in project_objects(package()).values() for oid in items}
                    apply_delete()
                    after={oid for items in project_objects(package()).values() for oid in items}
                    remove_deleted_references(package(),before-after)
                    reset()
                    dialog.close()
                    save("Objekt gelöscht")

                ui.button("Löschen", icon="delete_outline", on_click=apply).props("color=negative no-caps")
        dialog.open()

    def mechanical_component_dialog(component: MechanicalComponent | None = None) -> None:
        current = component.model_copy(deep=True) if component else MechanicalComponent(name="")
        parent_options = {
            item.id: item.name for item in package().mechanical_components if item.id != current.id
        }
        document_options = {item.id: item.name for item in package().source_documents}
        with ui.dialog() as dialog, ui.card().classes("w-[900px] max-w-[97vw] p-6 gap-4"):
            from .help_ui import mask_help
            mask_help(dialog,'mechanics',component,mask='Mechanikteil bearbeiten')
            ui.label("Mechanikkomponente bearbeiten" if component else "Mechanikkomponente hinzufügen").classes("text-xl font-bold")
            with ui.row().classes("w-full gap-3"):
                name = ui.input("Name", value=current.name, placeholder="z. B. Aluminiumgehäuse").classes("grow")
                kind = ui.select(
                    {item.value: item.value for item in MechanicalComponentKind},
                    value=current.kind.value, label="Typ",
                ).classes("grow")
                maturity = ui.select(
                    {item.value: item.value for item in DesignMaturity},
                    value=current.maturity.value, label="Reifegrad",
                ).classes("grow")
            parent_id = ui.select(parent_options, value=current.parent_component_id, label="Übergeordnete Baugruppe", clearable=True).classes("w-full")
            with ui.expansion('CAD / PLM / eingesetztes Teil',value=False).classes('w-full border rounded'):
                part_fields={key:ui.input(label,value=getattr(current,key)).classes('w-full') for key,label in [
                    ('part_number','Teilenummer / MPN'),('manufacturer','Hersteller'),('revision','Teilrevision'),
                    ('cad_reference','CAD-Modell / Zeichnung'),('cad_revision','CAD-Revision'),('plm_reference','PLM / ERP-Referenz')]}
                alternatives=ui.select({c.id:c.name for c in package().mechanical_components if c.id!=current.id},value=current.alternative_component_ids,multiple=True,label='Alternative Teile / Baugruppen').props('use-input use-chips').classes('w-full')
                analyses=ui.textarea('Berechnungen / Simulationen (je Zeile eine Referenz)',value='\n'.join(current.analysis_references)).classes('w-full')
            with ui.row().classes("w-full gap-3"):
                material = ui.input("Material", value=current.material).classes("grow")
                dimensions = ui.input("Abmessungen / Bauraum", value=current.dimensions).classes("grow")
                mass = ui.input("Masse", value=current.mass).classes("grow")
                protection = ui.input("Schutzart", value=current.protection_rating).classes("grow")
            with ui.row().classes("w-full gap-3"):
                cooling_method = ui.input("Kühlverfahren", value=current.cooling_method).classes("grow")
                power_dissipation = ui.input("Abzuführende Verlustleistung", value=current.power_dissipation).classes("grow")
                temperature_range = ui.input("Temperaturbereich", value=current.temperature_range).classes("grow")
            with ui.row().classes("w-full gap-3"):
                pcb_constraints = ui.textarea(
                    "PCB-Kopplung (Schlüssel: Wert)",
                    value="\n".join(f"{key}: {value}" for key, value in current.pcb_constraints.items()),
                ).props("outlined autogrow").classes("grow")
                parameters = ui.textarea(
                    "Weitere Eckdaten (Schlüssel: Wert)",
                    value="\n".join(f"{key}: {value}" for key, value in current.parameters.items()),
                ).props("outlined autogrow").classes("grow")
            requirement_ids = ui.select(
                requirement_options(RequirementClassification.SYSTEM, RequirementClassification.MECHANICS, RequirementClassification.HARDWARE),
                value=list(current.requirement_ids), label="Begründende Requirements", multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            source_ids = ui.select(
                document_options, value=list(current.source_document_ids),
                label="Quelldokumente / Nachweise", multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            description = ui.textarea("Beschreibung", value=current.description).props("outlined autogrow").classes("w-full")
            from .property_inputs import custom_inputs
            apply_attributes=custom_inputs(package(),current,include_system=True)
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply() -> None:
                    normalized_name = (name.value or "").strip()
                    if not normalized_name:
                        ui.notify("Der Name ist erforderlich.", type="warning")
                        return
                    parsed_pcb = parse_properties(pcb_constraints.value or "")
                    parsed_parameters = parse_properties(parameters.value or "")
                    if parsed_pcb is None or parsed_parameters is None:
                        return
                    try:apply_attributes(current)
                    except (ValueError,TypeError) as error:ui.notify(str(error),type='negative');return
                    current.name = normalized_name
                    current.kind = MechanicalComponentKind(kind.value)
                    current.maturity = DesignMaturity(maturity.value)
                    current.parent_component_id = parent_id.value or None
                    for key,field in part_fields.items():setattr(current,key,(field.value or '').strip())
                    current.alternative_component_ids=list(alternatives.value or [])
                    current.analysis_references=[line.strip() for line in (analyses.value or '').splitlines() if line.strip()]
                    current.material = (material.value or "").strip()
                    current.dimensions = (dimensions.value or "").strip()
                    current.mass = (mass.value or "").strip()
                    current.protection_rating = (protection.value or "").strip()
                    current.cooling_method = (cooling_method.value or "").strip()
                    current.power_dissipation = (power_dissipation.value or "").strip()
                    current.temperature_range = (temperature_range.value or "").strip()
                    current.pcb_constraints = parsed_pcb
                    current.parameters = parsed_parameters
                    current.requirement_ids = list(requirement_ids.value or [])
                    current.source_document_ids = list(source_ids.value or [])
                    current.description = description.value or ""
                    before=package().model_copy(deep=True)
                    package().mechanical_components=[c for c in package().mechanical_components if c.id!=current.id]+[current]
                    _sync_requirement_links(
                        RequirementTargetType.MECHANICAL_COMPONENT, current.id, current.requirement_ids,
                    )
                    selection.update(kind="mechanical_component", id=current.id)
                    if save("Mechanikkomponente gespeichert") is False:
                        for field in type(before).model_fields:setattr(package(),field,getattr(before,field))
                        return
                    dialog.close()

                ui.button("Speichern", icon="save", on_click=apply).props("no-caps")
        dialog.open()

    def mechanical_constraint_dialog(constraint: MechanicalConstraint | None = None) -> None:
        current = constraint or MechanicalConstraint(name="")
        with ui.dialog() as dialog, ui.card().classes("w-[820px] max-w-[97vw] p-6 gap-4"):
            ui.label("Mechanische Randbedingung bearbeiten" if constraint else "Mechanische Randbedingung hinzufügen").classes("text-xl font-bold")
            with ui.row().classes("w-full gap-3"):
                name = ui.input("Name", value=current.name, placeholder="z. B. Maximale Bauhöhe Oberseite").classes("grow")
                kind = ui.select(
                    {item.value: item.value for item in MechanicalConstraintKind},
                    value=current.kind.value, label="Kategorie",
                ).classes("grow")
                maturity = ui.select(
                    {item.value: item.value for item in DesignMaturity},
                    value=current.maturity.value, label="Reifegrad",
                ).classes("grow")
            statement = ui.textarea("Randbedingung", value=current.statement).props("outlined autogrow").classes("w-full")
            with ui.row().classes("w-full gap-3"):
                value = ui.input("Wert", value=current.value).classes("grow")
                unit = ui.input("Einheit", value=current.unit).classes("w-32")
                component_id = ui.select(
                    {item.id: item.name for item in package().mechanical_components},
                    value=current.mechanical_component_id, label="Mechanikkomponente", clearable=True,
                ).classes("grow")
                element_id = ui.select(
                    element_options(), value=current.architecture_element_id,
                    label="HW-/ECAD-Bezug", clearable=True,
                ).classes("grow")
            requirement_ids = ui.select(
                requirement_options(RequirementClassification.SYSTEM, RequirementClassification.MECHANICS, RequirementClassification.HARDWARE),
                value=list(current.requirement_ids), label="Begründende Requirements", multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            rationale = ui.textarea("Begründung", value=current.rationale).props("outlined autogrow").classes("w-full")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply() -> None:
                    if not (name.value or "").strip() or not (statement.value or "").strip():
                        ui.notify("Name und Randbedingung sind erforderlich.", type="warning")
                        return
                    current.name = name.value.strip()
                    current.kind = MechanicalConstraintKind(kind.value)
                    current.statement = statement.value.strip()
                    current.value = (value.value or "").strip()
                    current.unit = (unit.value or "").strip()
                    current.maturity = DesignMaturity(maturity.value)
                    current.mechanical_component_id = component_id.value or None
                    current.architecture_element_id = element_id.value or None
                    current.requirement_ids = list(requirement_ids.value or [])
                    current.rationale = rationale.value or ""
                    if constraint is None:
                        package().mechanical_constraints.append(current)
                    _sync_requirement_links(
                        RequirementTargetType.MECHANICAL_CONSTRAINT, current.id, current.requirement_ids,
                    )
                    selection.update(kind="mechanical_constraint", id=current.id)
                    dialog.close()
                    save("Mechanische Randbedingung gespeichert")

                ui.button("Speichern", icon="save", on_click=apply).props("no-caps")
        dialog.open()

    def layer_interface_dialog(
        interface_class: InterfaceClass,
        interface: InterfaceRequirement | None = None,
    ) -> None:
        current = interface or InterfaceRequirement(name="", interface_class=interface_class)
        compatible_classes = {
            InterfaceClass.MECHANICAL: {InterfaceClass.MECHANICAL, InterfaceClass.ELECTRONIC},
            InterfaceClass.SOFTWARE: {InterfaceClass.SOFTWARE, InterfaceClass.ELECTRONIC},
            InterfaceClass.FIRMWARE: {InterfaceClass.FIRMWARE, InterfaceClass.ELECTRONIC},
            InterfaceClass.ELECTRONIC: set(InterfaceClass),
        }[interface_class]
        linked_options = {
            item.id: f"{item.interface_class.value} · {item.name}"
            for item in package().interface_requirements
            if item.id != current.id and item.interface_class in compatible_classes
        }
        with ui.dialog() as dialog, ui.card().classes("w-[860px] max-w-[97vw] p-6 gap-4"):
            ui.label("Schnittstelle bearbeiten" if interface else "Schnittstelle hinzufügen").classes("text-xl font-bold")
            ui.badge(interface_class.value, color="indigo-1").props("text-color=indigo-9")
            with ui.row().classes("w-full gap-3"):
                name = ui.input("Name", value=current.name).classes("grow")
                family = ui.input("Familie", value=current.family).classes("grow")
                maturity = ui.select(
                    {item.value: item.value for item in RequirementMaturity},
                    value=current.maturity.value, label="Reifegrad",
                ).classes("grow")
            with ui.row().classes("w-full gap-3"):
                provider = ui.input("Provider / Quelle", value=current.provider or current.host_role).classes("grow")
                consumer = ui.input("Consumer / Teilnehmer", value=current.consumer or ", ".join(current.participant_roles)).classes("grow")
                carrier = ui.input("Träger / Kopplung", value=current.medium_connector).classes("grow")
            with ui.row().classes("w-full gap-3"):
                physical = ui.textarea(
                    "Physische Eigenschaften (Schlüssel: Wert)",
                    value="\n".join(f"{key}: {value}" for key, value in current.physical_properties.items()),
                ).props("outlined autogrow").classes("grow")
                protocol = ui.textarea(
                    "Protokolleigenschaften (Schlüssel: Wert)",
                    value="\n".join(f"{key}: {value}" for key, value in current.protocol_properties.items()),
                ).props("outlined autogrow").classes("grow")
            linked_ids = ui.select(
                linked_options, value=list(current.linked_layer_ids),
                label="Gekoppelte Layer", multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            relevant_classes = (
                (RequirementClassification.SYSTEM, RequirementClassification.MECHANICS, RequirementClassification.HARDWARE)
                if interface_class == InterfaceClass.MECHANICAL
                else (RequirementClassification.SYSTEM, RequirementClassification.SOFTWARE, RequirementClassification.FIRMWARE, RequirementClassification.HARDWARE)
            )
            requirement_ids = ui.select(
                requirement_options(*relevant_classes), value=list(current.requirement_ids),
                label="Begründende Requirements", multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            rationale = ui.textarea("Begründung / Spezifikationsstand", value=current.rationale).props("outlined autogrow").classes("w-full")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply() -> None:
                    normalized_name = (name.value or "").strip()
                    physical_values = parse_properties(physical.value or "")
                    protocol_values = parse_properties(protocol.value or "")
                    if not normalized_name:
                        ui.notify("Der Name ist erforderlich.", type="warning")
                        return
                    if physical_values is None or protocol_values is None:
                        return
                    current.name = normalized_name
                    current.interface_class = interface_class
                    current.family = (family.value or "Interface").strip()
                    current.maturity = RequirementMaturity(maturity.value)
                    current.provider = (provider.value or "").strip()
                    current.consumer = (consumer.value or "").strip()
                    current.host_role = current.provider
                    current.participant_roles = lines((consumer.value or "").replace(",", "\n"))
                    current.medium_connector = (carrier.value or "").strip()
                    current.physical_properties = physical_values
                    current.protocol_properties = protocol_values
                    current.linked_layer_ids = list(linked_ids.value or [])
                    current.requirement_ids = list(requirement_ids.value or [])
                    current.rationale = rationale.value or ""
                    if interface is None:
                        package().interface_requirements.append(current)
                    _sync_requirement_links(RequirementTargetType.INTERFACE, current.id, current.requirement_ids)
                    selection.update(kind="interface", id=current.id)
                    dialog.close()
                    save("Schnittstelle gespeichert")

                ui.button("Speichern", icon="save", on_click=apply).props("no-caps")
        dialog.open()

    def software_component_dialog(component: SoftwareComponent | None = None) -> None:
        current = component.model_copy(deep=True) if component else SoftwareComponent(name="")
        parent_options = {
            item.id: item.name for item in package().software_components if item.id != current.id
        }
        interface_options = {
            item.id: f"{item.interface_class.value} · {item.name}"
            for item in package().interface_requirements
            if item.interface_class in {InterfaceClass.SOFTWARE, InterfaceClass.FIRMWARE, InterfaceClass.ELECTRONIC}
        }
        with ui.dialog() as dialog, ui.card().classes("w-[900px] max-w-[97vw] p-6 gap-4"):
            from .help_ui import mask_help
            mask_help(dialog,'software',component,mask='SW/FW-Komponente bearbeiten')
            ui.label("Software-/Firmwarekomponente bearbeiten" if component else "Software-/Firmwarekomponente hinzufügen").classes("text-xl font-bold")
            with ui.row().classes("w-full gap-3"):
                name = ui.input("Name", value=current.name).classes("grow")
                domain = ui.select(
                    {item.value: item.value for item in SoftwareDomain},
                    value=current.domain.value, label="Domäne",
                ).classes("grow")
                kind = ui.select(
                    {item.value: item.value for item in SoftwareComponentKind},
                    value=current.kind.value, label="Typ",
                ).classes("grow")
                maturity = ui.select(
                    {item.value: item.value for item in DesignMaturity},
                    value=current.maturity.value, label="Reifegrad",
                ).classes("grow")
            with ui.row().classes("w-full gap-3"):
                parent_id = ui.select(parent_options, value=current.parent_component_id, label="Übergeordnete Komponente", clearable=True).classes("grow")
                deployment_id = ui.select(element_options(), value=current.deployment_element_id, label="Deployment auf Elektronik-AE", clearable=True).classes("grow")
            with ui.row().classes("w-full gap-3"):
                runtime = ui.input("Runtime / Betriebssystem", value=current.runtime).classes("grow")
                version = ui.input("Version", value=current.version).classes("w-40")
                repository_url = ui.input("Repository", value=current.repository_url).classes("grow")
            with ui.expansion('Code / Package / Build',value=False).classes('w-full border rounded'):
                code_fields={key:ui.input(label,value=getattr(current,key)).classes('w-full') for key,label in [
                    ('code_path','Codepfad / Modulpfad'),('commit','Commit / Tag'),('package_id','Package-Kennung'),
                    ('build_id','Build-ID'),('artifact_url','Build- / Firmwareartefakt') ]}
                dependencies=ui.select({c.id:c.name for c in package().software_components if c.id!=current.id},value=current.dependency_ids,multiple=True,label='Verwendete Packages / Komponenten').props('use-input use-chips').classes('w-full')
                included=ui.select({c.id:c.name for c in package().software_components if c.id!=current.id},value=current.included_component_ids,multiple=True,label='Build- / Firmwarebestandteile').props('use-input use-chips').classes('w-full')
                config=ui.textarea('Implementierungskonfiguration (Schlüssel: Wert)',value='\n'.join(f'{k}: {v}' for k,v in current.configuration.items())).props('autogrow').classes('w-full')
                def update_kind():
                    for key in ('package_id',):code_fields[key].set_visibility(kind.value in {'Package','Library'})
                    for key in ('build_id','artifact_url'):code_fields[key].set_visibility(kind.value in {'Build','Firmware Image','Bootloader','Firmware Module'})
                    included.set_visibility(kind.value in {'Build','Firmware Image','Platform'})
                kind.on_value_change(lambda _:update_kind());update_kind()
            with ui.row().classes("w-full gap-3"):
                provenance = ui.select(
                    {item.value: item.value for item in RealizationProvenance},
                    value=current.provenance.value,
                    label="Herkunft",
                ).classes("grow")
                substitution = ui.select(
                    {item.value: item.value for item in SubstitutionPolicy},
                    value=current.substitution_policy.value,
                    label="Substitution",
                ).classes("grow")
            requirement_ids = ui.select(
                requirement_options(RequirementClassification.SYSTEM, RequirementClassification.SOFTWARE, RequirementClassification.FIRMWARE, RequirementClassification.HARDWARE),
                value=list(current.requirement_ids), label="Begründende Requirements", multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            interface_ids = ui.select(
                interface_options, value=list(current.interface_requirement_ids),
                label="Verwendete Protokolle / Physical Layer", multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            description = ui.textarea("Verantwortung und Beschreibung", value=current.description).props("outlined autogrow").classes("w-full")
            from .property_inputs import custom_inputs
            apply_attributes=custom_inputs(package(),current,include_system=True)
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply() -> None:
                    if not (name.value or "").strip():
                        ui.notify("Der Name ist erforderlich.", type="warning")
                        return
                    try:apply_attributes(current)
                    except ValueError as error:ui.notify(str(error),type='negative');return
                    current.name = name.value.strip()
                    current.domain = SoftwareDomain(domain.value)
                    current.kind = SoftwareComponentKind(kind.value)
                    current.maturity = DesignMaturity(maturity.value)
                    current.parent_component_id = parent_id.value or None
                    current.deployment_element_id = deployment_id.value or None
                    current.runtime = (runtime.value or "").strip()
                    current.version = (version.value or "").strip()
                    current.repository_url = (repository_url.value or "").strip()
                    for key,field in code_fields.items():setattr(current,key,(field.value or '').strip())
                    current.dependency_ids=list(dependencies.value or []);current.included_component_ids=list(included.value or [])
                    parsed_config=parse_properties(config.value or '')
                    if parsed_config is None:return
                    current.configuration=parsed_config
                    current.provenance = RealizationProvenance(provenance.value)
                    current.substitution_policy = SubstitutionPolicy(substitution.value)
                    current.requirement_ids = list(requirement_ids.value or [])
                    current.mandated_by_requirement_ids = (
                        list(current.requirement_ids)
                        if current.provenance == RealizationProvenance.MANDATED
                        else []
                    )
                    current.interface_requirement_ids = list(interface_ids.value or [])
                    current.description = description.value or ""
                    before=package().model_copy(deep=True)
                    package().software_components=[c for c in package().software_components if c.id!=current.id]+[current]
                    _sync_requirement_links(
                        RequirementTargetType.SOFTWARE_COMPONENT, current.id, current.requirement_ids,
                    )
                    selection.update(kind="software_component", id=current.id)
                    if save("Software-/Firmwarekomponente gespeichert") is False:
                        for field in type(before).model_fields:setattr(package(),field,getattr(before,field))
                        return
                    dialog.close()

                ui.button("Speichern", icon="save", on_click=apply).props("no-caps")
        dialog.open()

    def work_item_dialog(work_item: SoftwareWorkItem | None = None) -> None:
        current = work_item or SoftwareWorkItem(title="")
        with ui.dialog() as dialog, ui.card().classes("w-[820px] max-w-[97vw] p-6 gap-4"):
            ui.label("Arbeitspaket bearbeiten" if work_item else "Arbeitspaket hinzufügen").classes("text-xl font-bold")
            title = ui.input("Titel", value=current.title).classes("w-full")
            with ui.row().classes("w-full gap-3"):
                domain = ui.select(
                    {item.value: item.value for item in SoftwareDomain}, value=current.domain.value, label="Domäne",
                ).classes("grow")
                status = ui.select(
                    {item.value: item.value for item in WorkItemStatus}, value=current.status.value, label="Status",
                ).classes("grow")
                priority = ui.select(
                    {item.value: item.value for item in RequirementPriority}, value=current.priority.value, label="Priorität",
                ).classes("grow")
            requirement_ids = ui.select(
                requirement_options(RequirementClassification.SYSTEM, RequirementClassification.SOFTWARE, RequirementClassification.FIRMWARE),
                value=list(current.requirement_ids), label="Requirements", multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            component_ids = ui.select(
                {item.id: item.name for item in package().software_components},
                value=list(current.component_ids), label="Betroffene Komponenten", multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            verification_ids = ui.select(
                {item.id: f"{item.identifier} · {item.title}" for item in package().verification_cases},
                value=list(current.verification_case_ids), label="Verifikationsdefinitionen", multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            description = ui.textarea("Beschreibung", value=current.description).props("outlined autogrow").classes("w-full")
            acceptance = ui.textarea("Akzeptanzkriterien", value=current.acceptance_criteria).props("outlined autogrow").classes("w-full")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply() -> None:
                    if not (title.value or "").strip():
                        ui.notify("Der Titel ist erforderlich.", type="warning")
                        return
                    current.title = title.value.strip()
                    current.domain = SoftwareDomain(domain.value)
                    current.status = WorkItemStatus(status.value)
                    current.priority = RequirementPriority(priority.value)
                    current.requirement_ids = list(requirement_ids.value or [])
                    current.component_ids = list(component_ids.value or [])
                    current.verification_case_ids = list(verification_ids.value or [])
                    current.description = description.value or ""
                    current.acceptance_criteria = acceptance.value or ""
                    if work_item is None:
                        package().software_work_items.append(current)
                    _sync_requirement_links(
                        RequirementTargetType.SOFTWARE_WORK_ITEM,
                        current.id,
                        current.requirement_ids,
                        RequirementRelation.ALLOCATED_TO,
                    )
                    selection.update(kind="software_work_item", id=current.id)
                    dialog.close()
                    save("Software-Arbeitspaket gespeichert")

                ui.button("Speichern", icon="save", on_click=apply).props("no-caps")
        dialog.open()

    def delete_mechanical_component(component: MechanicalComponent) -> None:
        def apply() -> None:
            package().mechanical_components.remove(component)
            for child in package().mechanical_components:
                if child.parent_component_id == component.id:
                    child.parent_component_id = None
            for constraint in package().mechanical_constraints:
                if constraint.mechanical_component_id == component.id:
                    constraint.mechanical_component_id = None
            for realization in package().technical_realizations:
                for variant in realization.variants:
                    variant.mechanical_component_ids=[i for i in variant.mechanical_component_ids if i!=component.id]
            package().requirement_links = [
                item for item in package().requirement_links
                if not (item.target_type == RequirementTargetType.MECHANICAL_COMPONENT and item.target_id == component.id)
            ]

        confirm_delete("Mechanikkomponente löschen?", component.name, apply)

    def delete_mechanical_constraint(constraint: MechanicalConstraint) -> None:
        def apply() -> None:
            package().mechanical_constraints.remove(constraint)
            package().requirement_links = [
                item for item in package().requirement_links
                if not (item.target_type == RequirementTargetType.MECHANICAL_CONSTRAINT and item.target_id == constraint.id)
            ]

        confirm_delete("Randbedingung löschen?", constraint.name, apply)

    def delete_software_component(component: SoftwareComponent) -> None:
        def apply() -> None:
            package().software_components.remove(component)
            for child in package().software_components:
                if child.parent_component_id == component.id:
                    child.parent_component_id = None
            for work_item in package().software_work_items:
                work_item.component_ids = [item for item in work_item.component_ids if item != component.id]
            for realization in package().technical_realizations:
                for variant in realization.variants:
                    variant.software_component_ids = [
                        item for item in variant.software_component_ids
                        if item != component.id
                    ]
            package().requirement_links = [
                item for item in package().requirement_links
                if not (item.target_type == RequirementTargetType.SOFTWARE_COMPONENT and item.target_id == component.id)
            ]

        confirm_delete("Software-/Firmwarekomponente löschen?", component.name, apply)

    def delete_work_item(work_item: SoftwareWorkItem) -> None:
        def apply() -> None:
            package().software_work_items.remove(work_item)
            package().requirement_links = [
                item for item in package().requirement_links
                if not (item.target_type == RequirementTargetType.SOFTWARE_WORK_ITEM and item.target_id == work_item.id)
            ]

        confirm_delete("Arbeitspaket löschen?", work_item.title, apply)

    def delete_interface(interface: InterfaceRequirement) -> None:
        confirm_delete(
            "Schnittstelle löschen?",
            f"{interface.interface_class.value} · {interface.name}",
            lambda: delete_interface_requirement(package(), interface.id),
        )

    def metric(value: int, label: str) -> None:
        with ui.card().classes("metric p-3"):
            ui.label(str(value)).classes("metric-value")
            ui.label(label).classes("metric-label")

    def interface_cards(classes: set[InterfaceClass]) -> None:
        interfaces = [item for item in package().interface_requirements if item.interface_class in classes]
        if not interfaces:
            with ui.column().classes("w-full items-center py-10 text-slate-500"):
                ui.icon("hub", size="48px")
                ui.label("Noch keine passenden Schnittstellen vorhanden.")
            return
        for interface in sorted(interfaces, key=lambda item: (item.interface_class.value, item.name.casefold())):
            with ui.card().classes("w-full p-4 gap-2 border development-card").on(
                "click", lambda _, item=interface: select("interface", item.id),
            ):
                with ui.row().classes("w-full items-center gap-2"):
                    ui.badge(interface.interface_class.value, color="indigo-1").props("text-color=indigo-9")
                    ui.label(interface.name).classes("font-bold grow")
                    ui.badge(interface.maturity.value, color="amber-1").props("text-color=grey-9")
                    ui.button(
                        icon="edit", on_click=lambda _, item=interface: (layer_interface_dialog(item.interface_class, item)
                        ),
                    ).props("flat round dense")
                    ui.button(
                        icon="delete_outline", on_click=lambda _, item=interface: (delete_interface(item)
                        ),
                    ).props("flat round dense color=negative")
                ui.label(
                    f"{interface.provider or interface.host_role or 'Provider offen'} → "
                    f"{interface.consumer or ', '.join(interface.participant_roles) or 'Consumer offen'}"
                ).classes("text-sm")
                ui.label(
                    f"{len(interface.requirement_ids)} Requirements · {len(interface.linked_layer_ids)} gekoppelte Layer"
                ).classes("subtle")

    def component_architecture_context(component,discipline):
        from .comparison_ui import source_dialog
        from .traceability import canonical_kind
        p=package()
        owners=p.software_architecture_elements if discipline=='software' else p.mechanical_architecture_elements
        functions=[f for f in p.function_elements if f.discipline==discipline and component.id in f.realization_ids]
        owner_ids={a.id for a in owners if component.id in a.realization_ids}
        owner_ids.update(f.architecture_element_id for f in functions if f.architecture_element_id)
        for relation in p.model_relations:
            if relation.kind=='realized_by' and relation.target_id==component.id:
                owner_ids.add(relation.source_id)
                if canonical_kind(relation.source_type)=='FunctionElement':
                    f=next((f for f in p.function_elements if f.id==relation.source_id and f.discipline==discipline),None)
                    if f and f.id not in {v.id for v in functions}:functions.append(f)
        matched=[a for a in owners if a.id in owner_ids]
        ui.label('Architektur → konkrete Umsetzung').classes('text-xs uppercase text-blue-700')
        for a in matched:ui.button('Architektur: '+a.name,on_click=lambda _,i=a.id:source_dialog(package(),i)).props('flat dense no-caps')
        for f in functions:ui.button('Realisiert FE: '+f.name,on_click=lambda _,i=f.id:select('function_element',i)).props('flat dense no-caps')
        if not matched and not functions:ui.label('Architekturzuordnung: Offen').classes('text-xs text-slate-500')

    def render_function_elements(discipline):
        functions=[f for f in package().function_elements if f.discipline==discipline]
        if functions:
            with ui.expansion('Funktions Elemente und ihre Umsetzung',value=True).classes('w-full border rounded'):
                for fe in functions:
                    ui.button('FE · '+fe.name,on_click=lambda _,i=fe.id:select('function_element',i)).props('flat no-caps')
                    ui.label(fe.description).classes('text-sm')
                    reals=package().software_components if discipline=='software' else package().mechanical_components
                    with ui.expansion('Implementierungen',value=False).classes('w-full'):
                        for real in reals:
                            if real.id in fe.realization_ids:ui.button('Implementierung: '+real.name,on_click=lambda _,i=real.id,d=discipline:select('software_component' if d=='software' else 'mechanical_component',i)).props('outline dense no-caps')

    @ui.refreshable
    def mechanics_workspace() -> None:
        mechanical_interfaces = [
            item for item in package().interface_requirements
            if item.interface_class == InterfaceClass.MECHANICAL
        ]
        thermal_constraints = [
            item for item in package().mechanical_constraints
            if item.kind == MechanicalConstraintKind.THERMAL
        ]
        with ui.column().classes("w-full p-4 gap-4"):
            render_integration_panel(package,save,"mechanical")
            render_function_elements("mechanical")
            with ui.row().classes("w-full items-center gap-2"):
                with ui.column().classes("gap-0 grow"):
                    ui.label("Mechanik / CAD").classes("text-2xl font-bold")
                    ui.label("Gehäuse, Kühlung, Bauraum und PCB-Kopplung systematisch bewerten.").classes("subtle")
                ui.button("Komponente", icon="add", on_click=mechanical_component_dialog).props("outline no-caps")
                ui.button("Randbedingung", icon="add", on_click=mechanical_constraint_dialog).props("outline no-caps")
                ui.button(
                    "MECH_IF", icon="add_link",
                    on_click=lambda: layer_interface_dialog(InterfaceClass.MECHANICAL),
                ).props("no-caps")
            with ui.row().classes("w-full gap-3"):
                metric(len(package().mechanical_components), "Komponenten")
                metric(len(package().mechanical_constraints), "Randbedingungen")
                metric(len(mechanical_interfaces), "Mechanische Interfaces")
                metric(len(thermal_constraints), "Thermische Punkte")
                metric(sum(bool(item.pcb_constraints) for item in package().mechanical_components), "PCB-Kopplungen")
            with ui.tabs().classes("w-full bg-white border rounded-lg") as tabs:
                components_tab = ui.tab("Komponenten", icon="precision_manufacturing")
                constraints_tab = ui.tab("Randbedingungen", icon="straighten")
                interfaces_tab = ui.tab("Mechanische Interfaces", icon="link")
                thermal_tab = ui.tab("Thermik & PCB-Kopplung", icon="device_thermostat")
            with ui.tab_panels(tabs, value=components_tab).classes("w-full bg-transparent p-0"):
                with ui.tab_panel(components_tab).classes("p-0 pt-3"):
                    if not package().mechanical_components:
                        with ui.column().classes("w-full items-center py-12 text-slate-500"):
                            ui.icon("precision_manufacturing", size="54px")
                            ui.label("Noch keine mechanischen Komponenten angelegt.")
                            ui.button("Erste Komponente anlegen", icon="add", on_click=mechanical_component_dialog).props("no-caps")
                    for component in package().mechanical_components:
                        with ui.card().classes("w-full p-4 gap-2 border development-card").on(
                            "click", lambda _, item=component: select("mechanical_component", item.id),
                        ):
                            with ui.row().classes("w-full items-center gap-2"):
                                ui.icon("precision_manufacturing", color="positive")
                                ui.label(component.name).classes("font-bold grow")
                                ui.badge(component.kind.value, color="green-1").props("text-color=green-9")
                                ui.badge(component.maturity.value, color="blue-1").props("text-color=blue-9")
                                ui.button(icon="edit", on_click=lambda _, item=component: (mechanical_component_dialog(item))).props("flat round dense")
                                ui.button(icon="delete_outline", on_click=lambda _, item=component: (delete_mechanical_component(item))).props("flat round dense color=negative")
                            component_architecture_context(component,"mechanical")
                            ui.label(component.description or "Noch ohne Beschreibung").classes("text-sm")
                            ui.label(
                                " · ".join(filter(None, [component.dimensions, component.material, component.mass, component.temperature_range])) or "Eckdaten noch offen"
                            ).classes("subtle")
                with ui.tab_panel(constraints_tab).classes("p-0 pt-3"):
                    if not package().mechanical_constraints:
                        ui.label("Noch keine mechanischen Randbedingungen angelegt.").classes("subtle py-10")
                    for constraint in package().mechanical_constraints:
                        with ui.card().classes("w-full p-4 gap-2 border development-card").on(
                            "click", lambda _, item=constraint: select("mechanical_constraint", item.id),
                        ):
                            with ui.row().classes("w-full items-center gap-2"):
                                ui.badge(constraint.kind.value, color="orange-1").props("text-color=orange-9")
                                ui.label(constraint.name).classes("font-bold grow")
                                ui.label(f"{constraint.value} {constraint.unit}".strip()).classes("font-mono")
                                ui.button(icon="edit", on_click=lambda _, item=constraint: (mechanical_constraint_dialog(item))).props("flat round dense")
                                ui.button(icon="delete_outline", on_click=lambda _, item=constraint: (delete_mechanical_constraint(item))).props("flat round dense color=negative")
                            ui.label(constraint.statement).classes("text-sm")
                with ui.tab_panel(interfaces_tab).classes("p-0 pt-3"):
                    interface_cards({InterfaceClass.MECHANICAL})
                with ui.tab_panel(thermal_tab).classes("p-0 pt-3"):
                    with ui.grid(columns=2).classes("w-full gap-3 development-grid-two"):
                        with ui.card().classes("w-full p-4 gap-3 border"):
                            ui.label("Thermische Bilanz").classes("text-lg font-bold")
                            for component in package().mechanical_components:
                                if component.power_dissipation or component.cooling_method or component.temperature_range:
                                    ui.label(component.name).classes("font-semibold")
                                    ui.label(
                                        " · ".join(filter(None, [component.power_dissipation, component.cooling_method, component.temperature_range]))
                                    ).classes("text-sm")
                            if not any(item.power_dissipation or item.cooling_method for item in package().mechanical_components):
                                ui.label("Noch keine thermischen Eckdaten erfasst.").classes("subtle")
                        with ui.card().classes("w-full p-4 gap-3 border"):
                            ui.label("Übergabe an HW / ECAD").classes("text-lg font-bold")
                            for component in package().mechanical_components:
                                if component.pcb_constraints:
                                    ui.label(component.name).classes("font-semibold")
                                    ui.label(" · ".join(f"{key}: {value}" for key, value in component.pcb_constraints.items())).classes("text-sm")
                            if not any(item.pcb_constraints for item in package().mechanical_components):
                                ui.label("Noch keine PCB-Outlines, Keep-outs oder Höhenzonen definiert.").classes("subtle")

    @ui.refreshable
    def software_workspace() -> None:
        logical_interfaces = [
            item for item in package().interface_requirements
            if item.interface_class in {InterfaceClass.SOFTWARE, InterfaceClass.FIRMWARE}
        ]
        deployed = [item for item in package().software_components if item.deployment_element_id]
        with ui.column().classes("w-full p-4 gap-4"):
            render_integration_panel(package,save,"software")
            render_function_elements("software")
            with ui.row().classes("w-full items-center gap-2"):
                with ui.column().classes("gap-0 grow"):
                    ui.label("Software / Firmware").classes("text-2xl font-bold")
                    ui.label("Komponenten, Protokolle, Deployment, Backlog und Tests mit dem Systemmodell verbinden.").classes("subtle")
                ui.button("Komponente", icon="add", on_click=software_component_dialog).props("outline no-caps")
                ui.button("Arbeitspaket", icon="add_task", on_click=work_item_dialog).props("outline no-caps")
                with ui.button_group():
                    ui.button("SW_IF", on_click=lambda: layer_interface_dialog(InterfaceClass.SOFTWARE)).props("no-caps")
                    ui.button("FW_IF", on_click=lambda: layer_interface_dialog(InterfaceClass.FIRMWARE)).props("no-caps")
            with ui.row().classes("w-full gap-3"):
                metric(sum(item.domain == SoftwareDomain.SOFTWARE for item in package().software_components), "Software")
                metric(sum(item.domain == SoftwareDomain.FIRMWARE for item in package().software_components), "Firmware")
                metric(sum(item.domain == SoftwareDomain.HDL for item in package().software_components), "HDL")
                metric(len(logical_interfaces), "Protokollinterfaces")
                metric(len(deployed), "Deployments")
                metric(sum(item.status != WorkItemStatus.DONE for item in package().software_work_items), "Backlog offen")
            with ui.tabs().classes("w-full bg-white border rounded-lg") as tabs:
                architecture_tab = ui.tab("Komponenten", icon="account_tree")
                protocols_tab = ui.tab("Protokolle & APIs", icon="sync_alt")
                deployment_tab = ui.tab("Deployment", icon="developer_board")
                backlog_tab = ui.tab("Backlog & Tests", icon="view_kanban")
            with ui.tab_panels(tabs, value=architecture_tab).classes("w-full bg-transparent p-0"):
                with ui.tab_panel(architecture_tab).classes("p-0 pt-3"):
                    if not package().software_components:
                        with ui.column().classes("w-full items-center py-12 text-slate-500"):
                            ui.icon("code", size="54px")
                            ui.label("Noch keine Software-, Firmware- oder HDL-Komponenten angelegt.")
                            ui.button("Erste Komponente anlegen", icon="add", on_click=software_component_dialog).props("no-caps")
                    for domain in SoftwareDomain:
                        components = [item for item in package().software_components if item.domain == domain]
                        if not components:
                            continue
                        ui.label(domain.value).classes("panel-heading mt-2")
                        for component in components:
                            with ui.card().classes("w-full p-4 gap-2 border development-card").on(
                                "click", lambda _, item=component: select("software_component", item.id),
                            ):
                                with ui.row().classes("w-full items-center gap-2"):
                                    ui.icon("memory_alt" if domain == SoftwareDomain.FIRMWARE else "code", color="primary")
                                    ui.label(component.name).classes("font-bold grow")
                                    ui.badge(component.kind.value, color="purple-1").props("text-color=purple-9")
                                    ui.badge(component.maturity.value, color="blue-1").props("text-color=blue-9")
                                    ui.button(icon="edit", on_click=lambda _, item=component: (software_component_dialog(item))).props("flat round dense")
                                    ui.button(icon="delete_outline", on_click=lambda _, item=component: (delete_software_component(item))).props("flat round dense color=negative")
                                component_architecture_context(component,"software")
                                ui.label(component.description or "Noch ohne Beschreibung").classes("text-sm")
                                ui.label(
                                    f"{len(component.requirement_ids)} Requirements · {len(component.interface_requirement_ids)} Interfaces · "
                                    + ("Deployment zugeordnet" if component.deployment_element_id else "Deployment offen")
                                ).classes("subtle")
                with ui.tab_panel(protocols_tab).classes("p-0 pt-3"):
                    interface_cards({InterfaceClass.SOFTWARE, InterfaceClass.FIRMWARE})
                with ui.tab_panel(deployment_tab).classes("p-0 pt-3"):
                    if not package().software_components:
                        ui.label("Noch keine deploybaren Komponenten vorhanden.").classes("subtle py-10")
                    for component in package().software_components:
                        target = package().find_element(component.deployment_element_id) if component.deployment_element_id else None
                        with ui.card().classes("w-full p-4 border"):
                            with ui.row().classes("w-full items-center gap-2"):
                                ui.label(component.name).classes("font-bold grow")
                                ui.icon("arrow_forward")
                                ui.label(
                                    f"{target[0].name} · {target[1].name}" if target else "Deployment-Ziel offen"
                                ).classes("text-sm" if target else "text-sm text-amber-800")
                                ui.button("Zuordnen", icon="link", on_click=lambda _, item=component: software_component_dialog(item)).props("flat dense no-caps")
                with ui.tab_panel(backlog_tab).classes("p-0 pt-3"):
                    if not package().software_work_items:
                        ui.label("Noch keine Arbeitspakete aus Requirements abgeleitet.").classes("subtle py-10")
                    for work_item in package().software_work_items:
                        with ui.card().classes("w-full p-4 gap-2 border development-card").on(
                            "click", lambda _, item=work_item: select("software_work_item", item.id),
                        ):
                            with ui.row().classes("w-full items-center gap-2"):
                                ui.badge(work_item.domain.value, color="purple-1").props("text-color=purple-9")
                                ui.label(work_item.title).classes("font-bold grow")
                                ui.badge(work_item.status.value, color="green-1" if work_item.status == WorkItemStatus.DONE else "amber-1").props("text-color=grey-9")
                                ui.badge(work_item.priority.value, color="red-1" if work_item.priority == RequirementPriority.CRITICAL else "grey-3").props("text-color=grey-9")
                                ui.button(icon="edit", on_click=lambda _, item=work_item: (work_item_dialog(item))).props("flat round dense")
                                ui.button(icon="delete_outline", on_click=lambda _, item=work_item: (delete_work_item(item))).props("flat round dense color=negative")
                            ui.label(work_item.description or "Noch ohne Beschreibung").classes("text-sm")
                            ui.label(
                                f"{len(work_item.requirement_ids)} Requirements · {len(work_item.verification_case_ids)} Tests"
                            ).classes("subtle")

    @ui.refreshable
    def navigator_view(space: str = "mechanics") -> None:
        with ui.column().classes("w-full p-3 gap-3"):
            discipline="mechanical" if space=="mechanics" else "software"
            for fe in package().function_elements:
                if fe.discipline==discipline:ui.button("FE · "+fe.name,icon="widgets",on_click=lambda _,i=fe.id:select("function_element",i)).props("flat dense no-caps").classes("w-full")
            if space == "mechanics":
                ui.label("MECHANIK / CAD").classes("panel-heading")
                for component in package().mechanical_components:
                    ui.button(
                        component.name, icon="precision_manufacturing",
                        on_click=lambda _, item=component: select("mechanical_component", item.id),
                    ).props("flat dense no-caps align=left").classes("w-full")
                if package().mechanical_constraints:
                    ui.label("RANDBEDINGUNGEN").classes("panel-heading mt-2")
                    for constraint in package().mechanical_constraints:
                        ui.button(
                            constraint.name, icon="straighten",
                            on_click=lambda _, item=constraint: select("mechanical_constraint", item.id),
                        ).props("flat dense no-caps align=left").classes("w-full")
            elif space == "software":
                ui.label("SOFTWARE / FIRMWARE").classes("panel-heading")
                for domain in SoftwareDomain:
                    items = [item for item in package().software_components if item.domain == domain]
                    if not items:
                        continue
                    ui.label(domain.value).classes("text-xs font-bold text-slate-500 uppercase")
                    for component in items:
                        ui.button(
                            component.name, icon="code",
                            on_click=lambda _, item=component: select("software_component", item.id),
                        ).props("flat dense no-caps align=left").classes("w-full")
                if package().software_work_items:
                    ui.label("BACKLOG").classes("panel-heading mt-2")
                    for work_item in package().software_work_items:
                        ui.button(
                            work_item.title, icon="task_alt",
                            on_click=lambda _, item=work_item: select("software_work_item", item.id),
                        ).props("flat dense no-caps align=left").classes("w-full")
    @ui.refreshable
    def inspector_view(space: str = "mechanics") -> None:
        obj = selected_object()
        with ui.column().classes("w-full p-4 gap-3"):
            ui.label("AUSGEWÄHLTES ENTWICKLUNGSOBJEKT").classes("panel-heading")
            if obj is None:
                with ui.column().classes("w-full items-center text-center py-12 text-slate-400"):
                    ui.icon("touch_app", size="48px")
                    ui.label("Wähle ein Objekt im Navigator oder Arbeitsbereich aus.")
                return
            show_sha_identity(obj.id)
            if edit_all_fields is not None:
                pass
            if type(obj).__name__=='FunctionElement':
                ui.label('FE · '+obj.name).classes('text-xl font-bold')
                if edit_all_fields:ui.button('FE bearbeiten',icon='edit',on_click=lambda:edit_all_fields(obj.id)).props('outline no-caps')
                render_attribute_spaces(obj,save,package=package())
                from .realization_focus import direct_requirements
                with ui.expansion('Direkt verknüpfte Requirements',value=False).classes('w-full'):
                    for req in direct_requirements(package(),{obj.id,*obj.realization_ids}):ui.label(req.identifier+' · '+req.title)
            elif isinstance(obj, MechanicalComponent):
                ui.label(obj.name).classes("text-xl font-bold")
                ui.badge(obj.kind.value, color="green-1").props("text-color=green-9")
                ui.label(obj.description or "—").classes("text-sm")
                for label, value in (
                    ("Reifegrad", obj.maturity.value), ("Teilenummer",obj.part_number),("CAD",obj.cad_reference),("CAD-Revision",obj.cad_revision),("PLM / ERP",obj.plm_reference), ("Material", obj.material),
                    ("Abmessungen", obj.dimensions), ("Masse", obj.mass),
                    ("Schutzart", obj.protection_rating), ("Kühlung", obj.cooling_method),
                    ("Verlustleistung", obj.power_dissipation), ("Temperatur", obj.temperature_range),
                ):
                    ui.label(f"{label}: {value or '—'}").classes("text-sm")
                ui.label(f"Requirements: {len(obj.requirement_ids)} · Quellen: {len(obj.source_document_ids)}").classes("subtle")
                ui.button("Bearbeiten", icon="edit", on_click=lambda: mechanical_component_dialog(obj)).props("outline no-caps")
            elif isinstance(obj, MechanicalConstraint):
                ui.label(obj.name).classes("text-xl font-bold")
                ui.badge(obj.kind.value, color="orange-1").props("text-color=orange-9")
                ui.label(obj.statement).classes("text-sm")
                ui.label(f"Wert: {obj.value or '—'} {obj.unit}".strip()).classes("text-sm")
                ui.label(f"Requirements: {len(obj.requirement_ids)}").classes("subtle")
                ui.button("Bearbeiten", icon="edit", on_click=lambda: mechanical_constraint_dialog(obj)).props("outline no-caps")
            elif isinstance(obj, SoftwareComponent):
                ui.label(obj.name).classes("text-xl font-bold")
                with ui.row().classes("gap-2"):
                    ui.badge(obj.domain.value, color="purple-1").props("text-color=purple-9")
                    ui.badge(obj.kind.value, color="blue-1").props("text-color=blue-9")
                    ui.badge(obj.provenance.value, color="teal-1").props("text-color=teal-9")
                    ui.badge(obj.substitution_policy.value, color="amber-1").props("text-color=grey-9")
                ui.label(obj.description or "—").classes("text-sm")
                ui.label(f"Runtime: {obj.runtime or '—'}").classes("text-sm")
                ui.label(f"Version: {obj.version or '—'}").classes("text-sm")
                target = package().find_element(obj.deployment_element_id) if obj.deployment_element_id else None
                ui.label(
                    "Deployment: " + (f"{target[0].name} · {target[1].name}" if target else "offen")
                ).classes("text-sm")
                ui.label(f"Requirements: {len(obj.requirement_ids)} · Interfaces: {len(obj.interface_requirement_ids)}").classes("subtle")
                ui.button("Bearbeiten", icon="edit", on_click=lambda: software_component_dialog(obj)).props("outline no-caps").mark("edit-software-"+obj.id)
            elif isinstance(obj, SoftwareWorkItem):
                ui.label(obj.title).classes("text-xl font-bold")
                with ui.row().classes("gap-2"):
                    ui.badge(obj.domain.value, color="purple-1").props("text-color=purple-9")
                    ui.badge(obj.status.value, color="amber-1").props("text-color=grey-9")
                ui.label(obj.description or "—").classes("text-sm")
                ui.label(f"Akzeptanz: {obj.acceptance_criteria or '—'}").classes("text-sm")
                ui.label(f"Requirements: {len(obj.requirement_ids)} · Tests: {len(obj.verification_case_ids)}").classes("subtle")
                ui.button("Bearbeiten", icon="edit", on_click=lambda: work_item_dialog(obj)).props("outline no-caps")
            elif isinstance(obj, InterfaceRequirement):
                ui.label(obj.name).classes("text-xl font-bold")
                ui.badge(obj.interface_class.value, color="indigo-1").props("text-color=indigo-9")
                ui.label(f"{obj.provider or obj.host_role or 'Provider offen'} → {obj.consumer or ', '.join(obj.participant_roles) or 'Consumer offen'}").classes("text-sm")
                ui.label(f"Träger / Kopplung: {obj.medium_connector or '—'}").classes("text-sm")
                if obj.physical_properties:
                    ui.label("Physisch: " + " · ".join(f"{key}={value}" for key, value in obj.physical_properties.items())).classes("text-sm")
                if obj.protocol_properties:
                    ui.label("Protokoll: " + " · ".join(f"{key}={value}" for key, value in obj.protocol_properties.items())).classes("text-sm")
                ui.label(f"Requirements: {len(obj.requirement_ids)} · Gekoppelte Layer: {len(obj.linked_layer_ids)}").classes("subtle")
                ui.button("Bearbeiten", icon="edit", on_click=lambda: layer_interface_dialog(obj.interface_class, obj)).props("outline no-caps")

            if isinstance(obj, (MechanicalComponent, SoftwareComponent)):
                ui.badge("Realisierung", color="teal")
                system_names = [e.name for a in package().architecture_allocations if a.target_id == obj.id
                                for e in package().system_elements if e.id == a.system_element_id]
                ui.label("Systembezug: " + (", ".join(system_names) or "Zuordnung offen")).classes("text-sm")
                render_attribute_spaces(obj, save, "realization_attributes", package())
                if isinstance(obj,(SoftwareComponent,MechanicalComponent)):
                    render_technical_values(package,save,obj)
                    for fe in package().function_elements:
                        if obj.id in fe.realization_ids:
                                                ui.button("FE: "+fe.name,on_click=lambda _,i=fe.id:select("function_element",i)).props("flat no-caps")

    def navigator(space: str) -> None:
        view_state["space"] = space
        navigator_view(space)

    def inspector(space: str) -> None:
        view_state["space"] = space
        inspector_view(space)

    def refresh(*, include_details: bool = True) -> None:
        mechanics_workspace.refresh()
        software_workspace.refresh()
        if include_details:
            navigator_view.refresh(view_state["space"])
            inspector_view.refresh(view_state["space"])

    return DevelopmentViews(
        mechanics_workspace=mechanics_workspace,
        software_workspace=software_workspace,
        navigator=navigator,
        inspector=inspector,
        refresh=refresh,
        reset=reset,
        select=select,
        selected_object=lambda:next((o for group in project_objects(package()).values() for i,o in group.items() if i==selection['id']),None),
    )
