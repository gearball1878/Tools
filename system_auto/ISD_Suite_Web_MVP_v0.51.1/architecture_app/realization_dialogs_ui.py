"""Component, functional element and realization editing.

Explicit callbacks keep project state in the page controller.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from .requirements_presentation import COMPONENT_REPRESENTATION_LABELS, COMPONENT_LIFECYCLE_LABELS
from nicegui import ui
from .attachment_store import delete_attachment
from .identity import show_sha_identity
from .models import ComponentRequirement, ComponentDecisionType, ComponentLifecycle, ComponentRepresentation, ComponentVerification, ComponentRoleInRealization, DesignComponent, RequirementLink, RequirementRelation, RequirementTargetType, RealizationComponentRole, RealizationProvenance, SolutionVariant, SolutionVariantStatus, SubstitutionPolicy, TechnicalSourceOwner, TechnicalRealization, TechnicalRealizationStatus
from .requirements_service import delete_component, delete_technical_realization, synchronize_realization_architecture_attribute

@dataclass(frozen=True)
class RealizationDialogsUiViews:
    component_dialog: Callable[..., Any]
    component_details: Callable[..., Any]
    qualification_dialog: Callable[..., Any]
    function_element_dialog: Callable[..., Any]
    component_requirement_dialog: Callable[..., Any]
    realization_variant_dialog: Callable[..., Any]
    realization_dialog: Callable[..., Any]
    confirm_component_delete: Callable[..., Any]
    confirm_realization_delete: Callable[..., Any]


def create_realization_dialogs_ui(
    *,
    clear_selection,
    owner_sources,
    package,
    page_state,
    render_technical_sources,
    reset,
    save,
    selection,
) -> RealizationDialogsUiViews:
    def component_dialog(
        component: DesignComponent | None = None,
        initial_requirement_id: str | None = None,
        initial_system_defining: bool | None = None,
    ) -> None:
        current = component or DesignComponent(
            name="",
            requirement_ids=[initial_requirement_id] if initial_requirement_id else [],
            system_defining=initial_system_defining,
        )
        requirement_options = {item.id: f"{item.identifier or item.external_id or item.id[:12]} · {item.title}" for item in package().requirements}
        component_need_options = {
            item.id: f"{item.component_role or 'Komponente'} · {item.name}"
            for item in package().component_requirements
        }
        interface_options = {
            item.id: f"{item.name} · {item.protocol or item.family}"
            for item in package().interface_requirements
        }
        with ui.dialog() as dialog, ui.card().classes("w-[1000px] max-w-[96vw] max-h-[92vh] overflow-auto p-6 gap-4"):
            from .help_ui import mask_help
            mask_help(dialog,'hardware_realizations',component,mask='Bauteil bearbeiten')
            ui.label("Komponente / A-Part bearbeiten" if component else "Komponente / A-Part hinzufügen").classes("text-xl font-bold")
            representation = ui.select(
                COMPONENT_REPRESENTATION_LABELS,
                value=current.representation.value,
                label="Ausprägung",
            ).classes("w-full")
            ui.label(
                "Eine logische Komponente beschreibt zunächst eine Funktion. Ein physikalisches Bauteil besitzt eine konkrete Herstellerteilenummer."
            ).classes("text-xs text-slate-500")
            with ui.row().classes("w-full gap-3"):
                name = ui.input("Bezeichnung", value=current.name, placeholder="z. B. Processing SoC").classes("grow")
                component_type = ui.input("Komponententyp", value=current.component_type).classes("grow")
                quantity = ui.number("Anzahl", value=current.quantity, min=1, precision=0).classes("w-28")
            with ui.row().classes("w-full gap-3"):
                manufacturer = ui.input("Hersteller", value=current.manufacturer, placeholder="z. B. Analog Devices").classes("grow")
                mpn = ui.input("Herstellerteilenummer", value=current.manufacturer_part_number, placeholder="Exakte MPN").classes("grow")
                package_name = ui.input("Gehäuse / Package", value=current.package_name, placeholder="z. B. LQFP-64").classes("grow")
            with ui.row().classes("w-full gap-3"):
                supplier = ui.input("Bevorzugter Lieferant", value=current.supplier).classes("grow")
                supplier_part_number = ui.input("Lieferanten-Bestellnummer", value=current.supplier_part_number).classes("grow")
                lifecycle = ui.select(
                    COMPONENT_LIFECYCLE_LABELS,
                    value=current.lifecycle.value,
                    label="Lifecycle",
                ).classes("grow")
            legacy_reference = ui.input(
                "Legacy-ECAD-Reference (nur Redesign / Vergleich)",
                value=current.legacy_ecad_reference,
                placeholder="Optionaler früherer RefDes; bei Neuentwicklung leer",
            ).classes("w-full")
            with ui.row().classes('w-full gap-3'):
                part_revision=ui.input('Bauteilrevision',value=current.part_revision).classes('grow')
                defining=ui.select({'open':'Noch bewerten','yes':'Systemdefinierend','no':'Detailbauteil'},value='open' if current.system_defining is None else 'yes' if current.system_defining else 'no',label='Bedeutung für das System').classes('grow')
            defining_reason=ui.textarea('Beitrag zum System / Begründung',value=current.system_defining_reason).props('autogrow').classes('w-full')
            alternatives=ui.select({c.id:f'{c.name} · {c.manufacturer_part_number or "MPN offen"}' for c in package().components if c.id!=current.id},value=current.alternative_component_ids,multiple=True,label='Alternative Bauteilobjekte').props('use-input use-chips').classes('w-full')
            with ui.row().classes("w-full gap-3"):
                decision = ui.select([item.value for item in ComponentDecisionType], value=current.decision_type.value, label="Entscheidung").classes("grow")
                verification = ui.select([item.value for item in ComponentVerification], value=current.verification.value, label="Verifikation").classes("grow")
                provenance = ui.select(
                    [item.value for item in RealizationProvenance],
                    value=current.provenance.value,
                    label="Herkunft",
                ).classes("grow")
                substitution = ui.select(
                    [item.value for item in SubstitutionPolicy],
                    value=current.substitution_policy.value,
                    label="Substitution",
                ).classes("grow")
            requirement_ids = ui.select(
                requirement_options,
                value=list(current.requirement_ids),
                label="Begründende Requirements",
                multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            component_requirement_ids = ui.select(
                component_need_options,
                value=list(current.component_requirement_ids),
                label="Technische Komponentenanforderungen",
                multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            interface_requirement_ids = ui.select(
                interface_options,
                value=list(current.interface_requirement_ids),
                label="Verwendete / bereitgestellte frühe Interfaces",
                multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            interface_hints = ui.input("Erwartete Interfaces", value=", ".join(current.interface_hints), placeholder="SPI, Ethernet, DDR").classes("w-full")
            qualification = ui.textarea(
                "Eignungsmatrix",
                value="\n".join(f"{key}: {value}" for key, value in current.qualification.items()),
                placeholder="Performance: Erfüllt · Datenblatt S. 12\nLeistungsaufnahme: Unklar · Nachweis fehlt",
            ).props("outlined autogrow").classes("w-full")
            ui.label("Eine Zeile je Kriterium im Format „Kriterium: Bewertung und Nachweis“.").classes("text-xs text-slate-500")
            rationale = ui.textarea("Begründung / Auswahlkriterien", value=current.rationale).classes("w-full").props("autogrow outlined")
            description = ui.textarea("Beschreibung", value=current.description).classes("w-full").props("autogrow outlined")
            from .property_inputs import custom_inputs
            apply_attributes=custom_inputs(package(),current,include_system=True)
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply() -> None:
                    if not (name.value or "").strip():
                        ui.notify("Die Komponentenbezeichnung darf nicht leer sein.", type="warning")
                        return
                    selected_representation = ComponentRepresentation(representation.value)
                    target = component.model_copy(deep=True) if component else DesignComponent(name=name.value.strip())
                    try:apply_attributes(target)
                    except (ValueError,TypeError) as error:ui.notify(str(error),type='negative');return
                    target.name = name.value.strip()
                    target.component_type = (component_type.value or "Generic Component").strip()
                    target.quantity = max(1, int(quantity.value or 1))
                    target.manufacturer = (manufacturer.value or "").strip()
                    target.manufacturer_part_number = (mpn.value or "").strip()
                    target.legacy_ecad_reference = (legacy_reference.value or "").strip()
                    target.part_revision=part_revision.value or ''
                    target.system_defining=None if defining.value=='open' else defining.value=='yes'
                    target.system_defining_reason=defining_reason.value or ''
                    target.alternative_component_ids=list(alternatives.value or [])
                    target.representation = selected_representation
                    target.lifecycle = ComponentLifecycle(lifecycle.value)
                    target.package_name = (package_name.value or "").strip()
                    target.supplier = (supplier.value or "").strip()
                    target.supplier_part_number = (supplier_part_number.value or "").strip()
                    target.decision_type = ComponentDecisionType(decision.value)
                    target.verification = ComponentVerification(verification.value)
                    target.provenance = RealizationProvenance(provenance.value)
                    target.substitution_policy = SubstitutionPolicy(substitution.value)
                    target.requirement_ids = list(requirement_ids.value or [])
                    target.mandated_by_requirement_ids = (
                        list(target.requirement_ids)
                        if target.provenance == RealizationProvenance.MANDATED
                        else []
                    )
                    target.component_requirement_ids = list(component_requirement_ids.value or [])
                    target.interface_requirement_ids = list(interface_requirement_ids.value or [])
                    target.interface_hints = [item.strip() for item in (interface_hints.value or "").split(",") if item.strip()]
                    parsed_qualification: dict[str, str] = {}
                    for line in (qualification.value or "").splitlines():
                        if not line.strip():
                            continue
                        key, separator, value = line.partition(":")
                        if not separator or not key.strip() or not value.strip():
                            ui.notify(f"Ungültige Eignungsmatrix-Zeile: {line}", type="warning")
                            return
                        parsed_qualification[key.strip()] = value.strip()
                    target.qualification = parsed_qualification
                    target.rationale = rationale.value or ""
                    target.description = description.value or ""
                    if component is None:
                        package().components.append(target)
                    else:package().components=[target if c.id==target.id else c for c in package().components]
                    for interface in package().interface_requirements:
                        interface.component_ids = [
                            value for value in interface.component_ids if value != target.id
                        ]
                    for interface_id in target.interface_requirement_ids:
                        linked_interface = next(
                            (item for item in package().interface_requirements if item.id == interface_id),
                            None,
                        )
                        if linked_interface and target.id not in linked_interface.component_ids:
                            linked_interface.component_ids.append(target.id)
                    package().requirement_links = [
                        item for item in package().requirement_links
                        if not (item.target_type == RequirementTargetType.COMPONENT and item.target_id == target.id)
                    ]
                    for requirement_id in target.requirement_ids:
                        package().requirement_links.append(RequirementLink(
                            requirement_id=requirement_id,
                            target_type=RequirementTargetType.COMPONENT,
                            target_id=target.id,
                            relation=RequirementRelation.SATISFIED_BY,
                        ))
                    clear_selection(); selection["component_id"] = target.id
                    dialog.close(); save("Komponentenentscheidung gespeichert")

                ui.button("Speichern", icon="save", on_click=apply).props("no-caps")
        dialog.open()

    def component_details(component):
        from .realization_service import standard_comparison
        with ui.dialog() as dialog,ui.card().classes('w-[1120px] max-w-[97vw] max-h-[94vh] overflow-auto p-6 gap-4'):
            with ui.row().classes('w-full items-center'):
                ui.label(component.name).classes('text-2xl font-bold grow')
                ui.button('Bearbeiten',icon='edit',on_click=lambda:component_dialog(component)).props('outline no-caps')
                ui.button('Schließen',icon='close',on_click=dialog.close).props('flat no-caps')
            show_sha_identity(component.id)
            with ui.row().classes('w-full gap-4'):
                for title,value in [('Hersteller',component.manufacturer),('MPN',component.manufacturer_part_number),('Bauteilrevision',component.part_revision),('Gehäuse',component.package_name)]:
                    with ui.column().classes('grow bg-slate-50 rounded p-3'):
                        ui.label(title).classes('text-xs text-slate-600');ui.label(value or 'Offen').classes('font-semibold')
            ui.label(component.description or component.rationale or 'Beschreibung offen.')
            ui.label('Systembeitrag: '+(component.system_defining_reason or 'Noch bewerten.')).classes('text-sm')
            if component.properties.get('ecadPresence') in {'Missing','DNP'}:
                ui.label('ECAD-Bestand: entfernt' if component.properties['ecadPresence']=='Missing' else 'ECAD-Bestand: nicht bestückt (DNP)').classes('text-sm text-amber-900')
            with ui.expansion('Alternative Bauteile',icon='compare_arrows',value=True).classes('w-full border rounded-lg'):
                for identifier in component.alternative_component_ids:
                    alternative=package().find_component(identifier)
                    if alternative:ui.button(f'{alternative.name} · {alternative.manufacturer_part_number or "MPN offen"} · {alternative.decision_type.value}',on_click=lambda _,c=alternative:component_details(c)).props('flat no-caps')
                if not component.alternative_component_ids:ui.label('Alternativen noch offen.').classes('text-sm')
            render_technical_sources(TechnicalSourceOwner.COMPONENT,component.id,component.name)
            from .attribute_spaces import render_attribute_spaces
            with ui.expansion('Anforderungs- und Realisierungsattribute',icon='tune').classes('w-full border rounded-lg'):
                render_attribute_spaces(component,save,package=package())
                from .technical_values_ui import render_technical_values
                render_technical_values(package,save,component)
            with ui.expansion('Normen und Bauteilqualifikation',icon='gavel',value=True).classes('w-full border rounded-lg'):
                context_requirements = {rid for r in package().technical_realizations
                    if any(role.component_id == component.id for v in r.variants for role in v.component_roles)
                    for rid in r.requirement_ids}
                for row in standard_comparison(package(),component,context_requirements):
                    with ui.card().classes('w-full shadow-none border p-3'):
                        ui.label(row['designation']+' · Ausgabe '+(row['edition'] or 'Offen')).classes('font-semibold')
                        ui.badge(row['result']);ui.label(row['scope'] or 'Geltungsbereich offen.').classes('text-sm')
                        if row['gap']:ui.label(row['gap']).classes('text-xs text-amber-900')
                        ui.button('Qualifikation bearbeiten',icon='edit',on_click=lambda _,sid=row['standard_id']:qualification_dialog(component,sid)).props('flat no-caps')
                ui.button('Normenbezug hinzufügen',icon='add',on_click=lambda:qualification_dialog(component)).props('outline no-caps')
                ui.label('Bauteilqualifikation und Systemverifikation werden getrennt bewertet.').classes('text-xs text-slate-600')
        dialog.open()

    def qualification_dialog(component,standard_id=None):
        from .models import ComponentStandardClaim
        claim=next((c for c in component.standard_claims if c.standard_id==standard_id),None)
        with ui.dialog() as dialog,ui.card().classes('w-[850px] max-w-[95vw] max-h-[92vh] overflow-auto p-6'):
            ui.label('Bauteilqualifikation · '+component.name).classes('text-xl font-bold')
            standard=ui.select({s.id:s.designation+' · '+(s.edition or 'Ausgabe offen') for s in package().standards},value=standard_id,label='Norm und konkrete Ausgabe').props('use-input').classes('w-full')
            result=ui.select(['Offen','Erfüllt','Teilweise erfüllt','Nicht erfüllt'],value=claim.result if claim else 'Offen',label='Bewertung').classes('w-full')
            scope=ui.textarea('Geltungsbereich / Betriebsbedingungen',value=claim.scope if claim else '').classes('w-full')
            evidence=ui.select({s.id:s.title+' · '+(s.revision or 'Revision offen') for s in owner_sources(TechnicalSourceOwner.COMPONENT,component.id)},value=claim.evidence_source_ids if claim else [],multiple=True,label='Revisionsbezogene Belege für dieses Bauteil').props('use-chips use-input').classes('w-full')
            rationale=ui.textarea('Begründung und Fundstellen',value=claim.rationale if claim else '').classes('w-full')
            def accept():
                if not standard.value:ui.notify('Norm auswählen.',type='warning');return
                updated=component.model_copy(deep=True)
                from .realization_service import record_qualification
                qualification=record_qualification(package(),updated,ComponentStandardClaim(standard_id=standard.value,result=result.value,scope=scope.value or '',evidence_source_ids=list(evidence.value or []),rationale=rationale.value or ''))
                updated.standard_claims=[c for c in updated.standard_claims if c.standard_id not in {standard_id,standard.value}]+[qualification]
                before=package().components;package().components=[updated if c.id==component.id else c for c in before]
                if save('Bauteilqualifikation gespeichert'):dialog.close()
                else:package().components=before
            ui.button('Bewertung speichern',icon='save',on_click=accept)
            ui.button('Abbrechen',on_click=dialog.close).props('flat')
        dialog.open()

    def function_element_dialog(element=None):
        from .models import FunctionElement
        current=element or FunctionElement(name='')
        with ui.dialog() as dialog,ui.card().classes('w-[950px] max-w-[96vw] max-h-[93vh] overflow-auto p-6 gap-3'):
            from .help_ui import mask_help
            mask_help(dialog,'architecture',element,mask='Funktions Element bearbeiten')
            ui.label('Funktions Element (FE) bearbeiten' if element else 'Funktions Element (FE) anlegen').classes('text-xl font-bold')
            if element:show_sha_identity(element.id)
            name=ui.input('Name',value=current.name).classes('w-full')
            description=ui.textarea('Funktionsbeschreibung',value=current.description).props('autogrow').classes('w-full')
            discipline=ui.select({'hardware':'Hardware','software':'Software / Firmware','mechanical':'Mechanik'},value=current.discipline,label='FE-Disziplin').classes('w-full')
            if current.source_block_uuid:discipline.disable()
            references=ui.column().classes('w-full')
            controls={}
            def refresh_references(clear=False):
                references.clear();d=discipline.value
                parents=[e for dom in package().domains for e in dom.elements] if d=='hardware' else package().software_architecture_elements if d=='software' else package().mechanical_architecture_elements
                reals=package().technical_realizations if d=='hardware' else package().software_components if d=='software' else package().mechanical_components
                allowed={'hardware':{'EHW_IF'},'software':{'SW_IF','FW_IF'},'mechanical':{'MECH_IF'}}[d]
                with references:
                    controls['ae']=ui.select({e.id:e.name for e in parents},value=None if clear else current.architecture_element_id,label='Zugehöriges Architekturelement',clearable=True).props('use-input').classes('w-full')
                    controls['dependencies']=ui.select({f.id:f.name for f in package().function_elements if f.id!=current.id and f.discipline==d},value=[] if clear else current.dependency_ids,multiple=True,label='Abhängige Funktions Elemente').props('use-input use-chips').classes('w-full')
                    controls['signals']=ui.select({s.id:s.name for s in package().signals} if d=='hardware' else {},value=[] if clear else current.interface_signal_ids,multiple=True,label='HW-Netze / Busse').props('use-input use-chips').classes('w-full');controls['signals'].set_visibility(d=='hardware')
                    controls['interfaces']=ui.select({i.id:i.name for i in package().interface_requirements if i.interface_class.value in allowed},value=[] if clear else current.interface_requirement_ids,multiple=True,label='Funktionale Schnittstellen').props('use-input use-chips').classes('w-full')
                    controls['reals']=ui.select({r.id:r.name for r in reals},value=[] if clear else current.realization_ids,multiple=True,label='Implementierungen / Variantencontainer').props('use-input use-chips').classes('w-full')
            discipline.on_value_change(lambda _:refresh_references(True));refresh_references()
            def requirement_choices():
                allowed={'hardware':{'System','Hardware'},'software':{'System','Software','Firmware'},'mechanical':{'System','Mechanik'}}[discipline.value]
                result={r.id:r.identifier+' · '+r.title for r in package().requirements if r.classification.value in allowed}
                for r in package().requirements:
                    if r.id in current.requirement_ids:result.setdefault(r.id,r.identifier+' · '+r.title+' (Bestandszuordnung)')
                return result
            requirements=ui.select(requirement_choices(),value=current.requirement_ids,multiple=True,label='Anforderungen').props('use-input use-chips').classes('w-full')
            discipline.on_value_change(lambda _:requirements.set_options(requirement_choices(),value=[]))
            if element:
                ui.label('ECAD-Quelle: '+(current.source_sheet or 'Manuell')+' · '+(current.source_revision or 'Revision offen')).classes('text-xs text-slate-600')
            from .property_inputs import custom_inputs
            apply_custom=custom_inputs(package(),current,include_system=True)
            def accept():
                if not (name.value or '').strip():ui.notify('FE-Name fehlt.',type='warning');return
                updated=current.model_copy(deep=True);updated.name=name.value.strip();updated.description=description.value or '';updated.discipline=discipline.value;updated.architecture_element_id=controls['ae'].value;updated.dependency_ids=list(controls['dependencies'].value or []);updated.interface_signal_ids=list(controls['signals'].value or []);updated.interface_requirement_ids=list(controls['interfaces'].value or []);updated.realization_ids=list(controls['reals'].value or []);updated.requirement_ids=list(requirements.value or [])
                try:apply_custom(updated)
                except (ValueError,TypeError) as e:ui.notify(str(e),type='negative');return
                before=package().function_elements;package().function_elements=[f for f in before if f.id!=updated.id]+[updated]
                if save('Funktions Element gespeichert'):dialog.close()
                else:package().function_elements=before
            ui.button('FE speichern',icon='save',on_click=accept)
            if element:
                def remove():
                    from .realization_service import delete_function_element
                    with ui.dialog() as confirmation,ui.card().classes('w-[600px] max-w-[94vw] p-5'):
                        ui.label('FE löschen · '+element.name).classes('text-xl font-bold')
                        ui.label('Das FE und seine Zuordnungen werden entfernt. Bauteile und Dokumente bleiben im Projektkatalog erhalten.')
                        def perform():
                            before=page_state.package;candidate=before.model_copy(deep=True)
                            delete_function_element(candidate,element.id);page_state.package=candidate
                            if save('Funktions Element gelöscht'):confirmation.close();dialog.close();clear_selection()
                            else:page_state.package=before
                        ui.button('FE löschen',icon='delete',on_click=perform).props('color=negative')
                        ui.button('Abbrechen',on_click=confirmation.close).props('flat')
                    confirmation.open()
                ui.button('FE löschen',icon='delete_outline',on_click=remove).props('outline color=negative')
            ui.button('Abbrechen',on_click=dialog.close).props('flat')
        dialog.open()

    def component_requirement_dialog(component_requirement: ComponentRequirement | None = None) -> None:
        current = component_requirement or ComponentRequirement(name="")
        requirement_options = {
            item.id: f"{item.identifier or item.id[:12]} · {item.title}"
            for item in package().requirements
        }
        with ui.dialog() as dialog, ui.card().classes("w-[760px] max-w-[96vw] p-6 gap-4"):
            ui.label(
                "Komponentenanforderung bearbeiten"
                if component_requirement else "Komponentenanforderung hinzufügen"
            ).classes("text-xl font-bold")
            with ui.row().classes("w-full gap-3"):
                name = ui.input(
                    "Bezeichnung", value=current.name,
                    placeholder="z. B. Rechenplattform für Bildverarbeitung",
                ).classes("grow")
                role = ui.input(
                    "Logische Komponentenrolle", value=current.component_role,
                    placeholder="z. B. Processing SoC",
                ).classes("grow")
            requirement_ids = ui.select(
                requirement_options,
                value=list(current.requirement_ids),
                label="Abgeleitet aus Requirements",
                multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            criteria = ui.textarea(
                "Messbare Auswahlkriterien",
                value="\n".join(f"{key}: {value}" for key, value in current.criteria.items()),
                placeholder="Rechenleistung: mindestens 20 GOPS\nLeistungsaufnahme: maximal 8 W",
            ).props("outlined autogrow").classes("w-full")
            rationale = ui.textarea(
                "Begründung / Ableitung", value=current.rationale,
            ).props("outlined autogrow").classes("w-full")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply() -> None:
                    normalized_name = (name.value or "").strip()
                    if not normalized_name:
                        ui.notify("Die Bezeichnung ist erforderlich.", type="warning")
                        return
                    parsed: dict[str, str] = {}
                    for line in (criteria.value or "").splitlines():
                        if not line.strip():
                            continue
                        key, separator, value = line.partition(":")
                        if not separator or not key.strip() or not value.strip():
                            ui.notify(f"Ungültige Kriterienzeile: {line}", type="warning")
                            return
                        parsed[key.strip()] = value.strip()
                    target = component_requirement or ComponentRequirement(name=normalized_name)
                    target.name = normalized_name
                    target.component_role = (role.value or "").strip()
                    target.requirement_ids = list(requirement_ids.value or [])
                    target.criteria = parsed
                    target.rationale = rationale.value or ""
                    if component_requirement is None:
                        package().component_requirements.append(target)
                    dialog.close(); save("Komponentenanforderung gespeichert")

                ui.button("Speichern", icon="save", on_click=apply).props("no-caps")
        dialog.open()

    def realization_variant_dialog(
        realization: TechnicalRealization,
        variant: SolutionVariant | None = None,
    ) -> None:
        current = variant or SolutionVariant(name="")
        component_options = {
            item.id: (
                f"{item.name} · {item.manufacturer} {item.manufacturer_part_number}".strip(" ·")
                if item.manufacturer_part_number else f"{item.name} · generisch"
            )
            for item in package().components
        }
        a_part = [item.component_id for item in current.component_roles if item.role == ComponentRoleInRealization.A_PART]
        b_parts = [
            item.component_id for item in current.component_roles
            if item.role == ComponentRoleInRealization.B_PART
        ]
        interface_options = {item.id: item.name for item in package().interface_requirements}
        software_options = {
            item.id: f"{item.name}{' · ' + item.version if item.version else ''}"
            for item in package().software_components
        }
        standard_options = {
            item.id: f"{item.designation} · {item.title}" if item.title else item.designation
            for item in package().standards
        }
        parameter_text = "\n".join(f"{key}={value}" for key, value in current.technical_parameters.items())
        with ui.dialog() as dialog, ui.card().classes("w-[900px] max-w-[97vw] p-6 gap-4"):
            from .help_ui import mask_help
            mask_help(dialog,'hardware_realizations',realization,mask='Variante bearbeiten')
            ui.label("Lösungsvariante bearbeiten" if variant else "Lösungsvariante hinzufügen").classes("text-xl font-bold")
            ui.label(realization.name).classes("subtle")
            with ui.row().classes("w-full gap-3"):
                name = ui.input("Name der Variante", value=current.name, placeholder="z. B. Ethernet-PHY mit externer Isolation").classes("grow")
                status = ui.select(
                    [item.value for item in SolutionVariantStatus],
                    value=current.status.value,
                    label="Bewertung",
                ).classes("w-48")
            ui.label("Komponentenrollen gelten nur innerhalb dieser Realisierung.").classes("text-xs text-blue-700")
            a_part_id = ui.select(
                component_options,
                value=a_part,
                label="Kernbauteile · designentscheidende Technologie",
                multiple=True,
                clearable=True,
            ).props("outlined options-dense").classes("w-full")
            b_part_ids = ui.select(
                component_options,
                value=b_parts,
                label="B-Komponenten · erforderliche Unterstützung",
                multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            software_component_ids = ui.select(
                software_options,
                value=list(current.software_component_ids),
                label="Verbindliche oder verwendete Software-/Firmwarekomponenten",
                multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            interface_ids = ui.select(
                interface_options,
                value=list(current.interface_requirement_ids),
                label="Verwendete frühe Interfaces",
                multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            standard_ids = ui.select(
                standard_options,
                value=list(current.standard_ids),
                label="Anzuwendende Normen / Standards",
                multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            parameters = ui.textarea(
                "Technische Parameter · eine Zeile je Schlüssel=Wert",
                value=parameter_text,
                placeholder="Versorgung=3,3 V\nDatenrate=>= 100 Mbit/s",
            ).props("autogrow outlined").classes("w-full")
            rationale = ui.textarea("Technische Begründung", value=current.rationale).props("autogrow outlined").classes("w-full")
            assumptions = ui.textarea(
                "Annahmen · eine Zeile je Annahme", value="\n".join(current.assumptions)
            ).props("autogrow outlined").classes("w-full")
            open_questions = ui.textarea(
                "Offene Fragen · eine Zeile je Frage", value="\n".join(current.open_questions)
            ).props("autogrow outlined").classes("w-full")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply_variant() -> None:
                    if not (name.value or "").strip():
                        ui.notify("Die Lösungsvariante benötigt einen Namen.", type="warning")
                        return
                    if set(a_part_id.value or []) & set(b_part_ids.value or []):
                        ui.notify("Eine Komponente kann in derselben Variante nicht A- und B-Komponente sein.", type="warning")
                        return
                    parsed_parameters: dict[str, str] = {}
                    for line in (parameters.value or "").splitlines():
                        if not line.strip():
                            continue
                        key, separator, value = line.partition("=")
                        if not separator or not key.strip() or not value.strip():
                            ui.notify("Technische Parameter bitte als Schlüssel=Wert eingeben.", type="warning")
                            return
                        parsed_parameters[key.strip()] = value.strip()
                    target = variant or current
                    target.name = (name.value or "").strip()
                    target.status = SolutionVariantStatus(status.value)
                    target.component_roles = []
                    for core_id in a_part_id.value or []:
                        target.component_roles.append(RealizationComponentRole(
                            component_id=core_id,
                            role=ComponentRoleInRealization.A_PART,
                            purpose="Designentscheidende Kernkomponente",
                        ))
                    target.component_roles.extend(
                        RealizationComponentRole(
                            component_id=item,
                            role=ComponentRoleInRealization.B_PART,
                            purpose="Erforderliche unterstützende Komponente",
                        )
                        for item in (b_part_ids.value or [])
                    )
                    target.interface_requirement_ids = list(interface_ids.value or [])
                    target.software_component_ids = list(software_component_ids.value or [])
                    target.standard_ids = list(standard_ids.value or [])
                    target.technical_parameters = parsed_parameters
                    target.rationale = rationale.value or ""
                    target.assumptions = [item.strip() for item in (assumptions.value or "").splitlines() if item.strip()]
                    target.open_questions = [item.strip() for item in (open_questions.value or "").splitlines() if item.strip()]
                    if variant is None:
                        realization.variants.append(target)
                    if target.status == SolutionVariantStatus.SELECTED:
                        realization.selected_variant_id = target.id
                        realization.status = TechnicalRealizationStatus.SELECTED
                        for item in realization.variants:
                            if item.id != target.id and item.status == SolutionVariantStatus.SELECTED:
                                item.status = SolutionVariantStatus.CANDIDATE
                    elif realization.selected_variant_id == target.id:
                        realization.selected_variant_id = None
                        if realization.status == TechnicalRealizationStatus.SELECTED:
                            realization.status = TechnicalRealizationStatus.IN_REVIEW
                    synchronize_realization_architecture_attribute(package(), realization)
                    dialog.close(); save("Lösungsvariante gespeichert")

                ui.button("Variante speichern", icon="save", on_click=apply_variant).props("no-caps")
        dialog.open()

    def realization_dialog(
        realization: TechnicalRealization | None = None,
        initial_requirement_id: str | None = None,
    ) -> None:
        current = realization or TechnicalRealization(
            name="",
            requirement_ids=[initial_requirement_id] if initial_requirement_id else [],
        )
        requirement_options = {
            item.id: f"{item.identifier or item.id[:12]} · {item.title}"
            for item in package().requirements
        }
        element_options = {
            element.id: f"{domain.name} / {element.name}"
            for domain in package().domains for element in domain.elements
        }
        with ui.dialog() as dialog, ui.card().classes("w-[920px] max-w-[97vw] max-h-[94vh] overflow-auto p-6 gap-4"):
            from .help_ui import mask_help
            mask_help(dialog,'hardware_realizations',realization,mask='Technische Realisierung bearbeiten')
            ui.label("Technische Realisierung bearbeiten" if realization else "Technische Realisierung anlegen").classes("text-xl font-bold")
            ui.label(
                "Diese Ebene verbindet technische Requirements mit einer hardwarenahen Lösung, ohne das generische Architecture Element umzubenennen."
            ).classes("text-sm text-slate-600")
            with ui.row().classes("w-full gap-3"):
                name = ui.input("Name", value=current.name, placeholder="z. B. Galvanisch getrennte CAN-Kommunikation").classes("grow")
                status = ui.select(
                    [item.value for item in TechnicalRealizationStatus],
                    value=current.status.value,
                    label="Status",
                ).classes("w-48")
                provenance = ui.select(
                    [item.value for item in RealizationProvenance],
                    value=current.provenance.value,
                    label="Herkunft",
                ).classes("w-44")
            generic_function = ui.input(
                "Generische Hardwarefunktion / AE-Rolle",
                value=current.generic_function,
                placeholder="z. B. CAN Physical Layer",
            ).classes("w-full")
            requirement_ids = ui.select(
                requirement_options,
                value=list(current.requirement_ids),
                label="Begründende Requirements",
                multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            architecture_element_id = ui.select(
                element_options,
                value=current.architecture_element_id,
                label="Generischem Architecture Element zuordnen (optional)",
                clearable=True,
            ).props("outlined options-dense").classes("w-full")
            function_element_id = ui.select(
                {f.id: f.name for f in package().function_elements},
                value=current.function_element_id, label='Funktions Element (optional)', clearable=True,
            ).props('use-input outlined').classes('w-full')
            rationale = ui.textarea("Begründung / Designlogik", value=current.rationale).props("autogrow outlined").classes("w-full")
            with ui.expansion(
                f"Lösungsvarianten ({len(current.variants)})",
                icon="account_tree", value=True,
            ).classes("w-full border rounded-lg"):
                if len(current.variants) < 2:
                    ui.label(
                        "Alternativenprüfung offen: für Neuentwicklung und Redesign mindestens eine "
                        "vergleichbare zweite Variante mit MPN und Quellen untersuchen."
                    ).classes("text-xs text-amber-900 bg-amber-50 border rounded p-2")
                for variant_item in current.variants:
                    with ui.row().classes("w-full items-center gap-2 border-b py-2"):
                        ui.icon("radio_button_checked" if current.selected_variant_id == variant_item.id else "radio_button_unchecked", color="primary")
                        with ui.column().classes("gap-0 grow"):
                            ui.label(variant_item.name).classes("font-semibold")
                            a_count = sum(item.role == ComponentRoleInRealization.A_PART for item in variant_item.component_roles)
                            b_count = sum(item.role == ComponentRoleInRealization.B_PART for item in variant_item.component_roles)
                            ui.label(f"{a_count} A-Komponente · {b_count} B-Komponente(n) · {len(variant_item.interface_requirement_ids)} Interface(s)").classes("subtle")
                        ui.badge(variant_item.status.value, color="green-1" if current.selected_variant_id == variant_item.id else "grey-3").props("text-color=grey-9")
                        ui.button(icon="edit", on_click=lambda _, item=variant_item: realization_variant_dialog(current, item)).props("flat round dense")
                        def remove_variant(item=variant_item) -> None:
                            current.variants = [value for value in current.variants if value.id != item.id]
                            if current.selected_variant_id == item.id:
                                current.selected_variant_id = None
                                current.status = TechnicalRealizationStatus.IN_REVIEW
                            synchronize_realization_architecture_attribute(package(), current)
                            save("Lösungsvariante entfernt")
                            dialog.close()
                        ui.button(icon="delete_outline", on_click=remove_variant).props("flat round dense color=negative")
                ui.button(
                    "Lösungsvariante hinzufügen", icon="add",
                    on_click=lambda: realization_variant_dialog(current),
                ).props("flat dense no-caps")
            from .property_inputs import custom_inputs
            apply_attributes=custom_inputs(package(),current,include_system=True)
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply_realization() -> None:
                    if not (name.value or "").strip() or not (generic_function.value or "").strip():
                        ui.notify("Name und generische Hardwarefunktion sind erforderlich.", type="warning")
                        return
                    if not requirement_ids.value and not function_element_id.value:
                        ui.notify("Ein begründendes Requirement oder ein FE ist erforderlich.", type="warning")
                        return
                    selected_status = TechnicalRealizationStatus(status.value)
                    if selected_status == TechnicalRealizationStatus.SELECTED and not current.selected_variant_id:
                        ui.notify("Für den Status Selected muss eine Lösungsvariante ausgewählt sein.", type="warning")
                        return
                    try:apply_attributes(current)
                    except (ValueError,TypeError) as error:ui.notify(str(error),type='negative');return
                    current.name = (name.value or "").strip()
                    current.generic_function = (generic_function.value or "").strip()
                    current.requirement_ids = list(requirement_ids.value or [])
                    current.architecture_element_id = architecture_element_id.value or None
                    current.function_element_id = function_element_id.value or None
                    current.status = selected_status
                    current.provenance = RealizationProvenance(provenance.value)
                    current.rationale = rationale.value or ""
                    if realization is None and current not in package().technical_realizations:
                        package().technical_realizations.append(current)
                    package().requirement_links = [
                        item for item in package().requirement_links
                        if not (
                            item.target_type == RequirementTargetType.TECHNICAL_REALIZATION
                            and item.target_id == current.id
                        )
                    ]
                    package().requirement_links.extend(
                        RequirementLink(
                            requirement_id=requirement_id,
                            target_type=RequirementTargetType.TECHNICAL_REALIZATION,
                            target_id=current.id,
                            relation=RequirementRelation.SATISFIED_BY,
                        )
                        for requirement_id in dict.fromkeys(current.requirement_ids)
                    )
                    synchronize_realization_architecture_attribute(package(), current)
                    dialog.close(); save("Technische Realisierung gespeichert")

                ui.button("Speichern", icon="save", on_click=apply_realization).props("no-caps")
        dialog.open()

    def confirm_component_delete(component: DesignComponent) -> None:
        stored_paths = [
            item.attachment_path
            for item in owner_sources(TechnicalSourceOwner.COMPONENT, component.id)
            if item.attachment_path
        ]
        with ui.dialog() as dialog, ui.card().classes("w-[500px] p-6 gap-4"):
            ui.label("Komponentenentscheidung löschen?").classes("text-xl font-bold")
            ui.label(
                "Zugeordnete AE und Requirements bleiben bestehen. Die Komponentenentscheidung, ihre Links, "
                "technischen Quellen und lokal hinterlegten Dokumente werden entfernt."
            ).classes("text-sm text-slate-600")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")
                def apply() -> None:
                    delete_component(package(), component.id)
                    reset()
                    if save("Komponentenentscheidung gelöscht"):
                        for stored_path in stored_paths:
                            try:
                                delete_attachment(package().project.id, stored_path)
                            except ValueError:
                                pass
                        dialog.close()
                ui.button("Löschen", icon="delete", on_click=apply).props("color=negative no-caps")
        dialog.open()

    def confirm_realization_delete(realization: TechnicalRealization) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[560px] max-w-[94vw] p-6 gap-4"):
            ui.label("Technische Realisierung löschen?").classes("text-xl font-bold")
            ui.label(realization.name).classes("font-semibold")
            ui.label(
                "Varianten und die Referenz am Architecture Element werden entfernt. Requirements, Komponenten und Interfaces bleiben erhalten."
            ).classes("text-sm text-slate-600")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")
                def remove() -> None:
                    delete_technical_realization(package(), realization.id)
                    clear_selection(); dialog.close(); save("Technische Realisierung gelöscht")
                ui.button("Löschen", icon="delete_outline", on_click=remove).props("color=negative no-caps")
        dialog.open()


    return RealizationDialogsUiViews(
        component_dialog=component_dialog,
        component_details=component_details,
        qualification_dialog=qualification_dialog,
        function_element_dialog=function_element_dialog,
        component_requirement_dialog=component_requirement_dialog,
        realization_variant_dialog=realization_variant_dialog,
        realization_dialog=realization_dialog,
        confirm_component_delete=confirm_component_delete,
        confirm_realization_delete=confirm_realization_delete,
    )
