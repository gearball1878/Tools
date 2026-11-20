"""Requirement, relation and assessment editing.

Explicit callbacks keep project state in the page controller.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from .requirements_presentation import SPECIFICATION_LEVEL_LABELS, REQUIREMENT_LEVEL_LABELS, LAYER_CHOICE_LABELS, SOLUTION_BINDING_LABELS, SOURCE_KIND_LABELS, CONFLICT_STATUS_LABELS, CONFLICT_RESOLUTION_LABELS
from copy import deepcopy
import json
from nicegui import ui
from .requirement_profiles import category_options, eligible_parents
from .models import EcadRequirement, FulfillmentAssessment, ModelRelation, Observation, EngineeringConflict, EngineeringConflictResolution, EngineeringConflictStatus, RequirementCategory, RequirementClassification, RequirementEcadRelevance, RequirementDerivation, RequirementLevel, RequirementLink, RequirementMaturity, RequirementOrigin, RequirementPriority, RequirementSpecificationLevel, RequirementSolutionBinding, RequirementSourceKind, RequirementRelation, RequirementTargetType, utc_now
from .traceability import add_relation, criteria, project_objects, review_assessment
from .requirements_service import delete_requirement, next_requirement_identifier
from .requirements_layers import validate_parent_links

@dataclass(frozen=True)
class RequirementsEditUiViews:
    requirement_dialog: Callable[..., Any]
    engineering_conflict_dialog: Callable[..., Any]
    allocation_dialog: Callable[..., Any]
    confirm_requirement_delete: Callable[..., Any]
    relation_dialog: Callable[..., Any]
    observation_dialog: Callable[..., Any]
    assessment_dialog: Callable[..., Any]


def create_requirements_edit_ui(
    *,
    clear_selection,
    package,
    reset,
    save,
    selection,
    view_relation,
) -> RequirementsEditUiViews:
    def relation_dialog(requirement: EcadRequirement) -> None:
        targets = {f"{kind}|{identifier}": f"{kind}: {getattr(obj, 'title', getattr(obj, 'name', identifier))}"
                   for kind, group in project_objects(package()).items()
                   for identifier, obj in group.items()}
        with ui.dialog() as dialog, ui.card().classes("w-[660px] max-w-[95vw] p-5 gap-3"):
            ui.label("Gespeicherte Beziehung anlegen").classes("text-lg font-bold")
            kind = ui.select({"allocated_to": "Zugeordnet zu", "observed_at": "Beobachtet an",
                              "inferred_from": "Erschlossen aus", "technical_interface": "Technische Schnittstelle",
                              "dependency": "Abhängigkeit", "governed_by": "Geregelt durch",
                              "verified_by": "Geprüft durch", "derived_from": "Abgeleitet aus"},
                             value="allocated_to", label="Beziehungstyp").classes("w-full")
            origin = ui.select(targets, value=f"Requirement|{requirement.id}", with_input=True,
                               label="Ausgangsobjekt").classes("w-full")
            target = ui.select(targets, with_input=True, label="Zielobjekt").classes("w-full")
            rationale = ui.textarea("Begründung / Rolle", placeholder="Welche konkrete Beziehung ist nachgewiesen?").classes("w-full")
            role = ui.input("Rolle / Richtung (optional)").classes("w-full")
            source = ui.input("Quelle / Fundstelle").classes("w-full")
            def apply() -> None:
                if not target.value or not origin.value:
                    ui.notify("Beide Endpunkte auswählen", type="warning"); return
                typ, identifier = target.value.split("|", 1)
                source_typ, source_identifier = origin.value.split("|", 1)
                relation = ModelRelation(kind=kind.value, source_type=source_typ, source_id=source_identifier,
                    target_type=typ, target_id=identifier, rationale=rationale.value or "", role=role.value or "",
                    source_locator=source.value or "")
                try: add_relation(package(), relation)
                except ValueError as error:
                    ui.notify(str(error), type="warning"); return
                if save("Beziehung gespeichert"):
                    dialog.close(); view_relation(relation.id)
            ui.button("Beziehung speichern", on_click=apply).props("no-caps")
        dialog.open()

    def observation_dialog(requirement: EcadRequirement) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[620px] max-w-[95vw] p-5 gap-3"):
            ui.label("Bestandsbefund dokumentieren").classes("text-lg font-bold")
            kind = ui.select(["Component", "Net", "Behavior", "Measurement", "Other"], value="Component", label="Art").classes("w-full")
            title = ui.input("Beobachtung").classes("w-full")
            description = ui.textarea("Beobachtetes Verhalten / Zustand").classes("w-full")
            locator = ui.input("Fundstelle / RefDes / Messreport").classes("w-full")
            rationale = ui.textarea("Warum stützt dieser Befund die Anforderung?").classes("w-full")
            def apply() -> None:
                if not (title.value or "").strip() or not (rationale.value or "").strip():
                    ui.notify("Befund und Begründung angeben", type="warning"); return
                observation = Observation(kind=kind.value,title=title.value.strip(),
                    description=description.value or "",source_locator=locator.value or "")
                package().observations.append(observation)
                relation = ModelRelation(kind="inferred_from",source_type="Requirement",source_id=requirement.id,
                    target_type="Observation",target_id=observation.id,rationale=rationale.value.strip(),
                    source_locator=locator.value or "")
                add_relation(package(),relation)
                requirement.observation_ids.append(observation.id)
                if save("Bestandsbefund zugeordnet"):
                    dialog.close(); view_relation(relation.id)
            ui.button("Befund speichern", on_click=apply).props("no-caps")
        dialog.open()

    def assessment_dialog(requirement: EcadRequirement) -> None:
        options = {real.id: real.name for real in package().technical_realizations}
        if not options:
            ui.notify("Zuerst eine technische Realisierung anlegen.", type="warning"); return
        with ui.dialog() as dialog, ui.card().classes("w-[690px] max-w-[95vw] p-5 gap-3"):
            ui.label("Technische Erfüllung bewerten").classes("text-lg font-bold")
            real = ui.select(options, label="Realisierung", value=next(iter(options))).classes("w-full")
            variants = {item.id: {variant.id: variant.name for variant in item.variants}
                        for item in package().technical_realizations}
            variant = ui.select(variants.get(real.value, {}), label="Variante (optional)").classes("w-full")
            def update_variants(event: Any) -> None:
                variant.options = variants.get(event.value, {})
                variant.value = None
                variant.update()
            real.on_value_change(update_variants)
            result = ui.select({"Draft":"Entwurf", "Passed":"Kriterien erfüllt", "Failed":"Kriterien nicht erfüllt"},
                               value="Draft", label="Ergebnis").classes("w-full")
            inputs = {criterion: ui.select({"Open":"Offen", "Passed":"Erfüllt", "Failed":"Nicht erfüllt"},
                       value="Open", label=criterion).classes("w-full") for criterion in criteria(requirement)}
            rationale = ui.textarea("Bewertung und Begründung").classes("w-full")
            evidence = ui.input("Ergebnisbeleg / Fundstelle").classes("w-full")
            def apply() -> None:
                assessment = FulfillmentAssessment(requirement_id=requirement.id, realization_id=real.value,
                    variant_id=variant.value,
                    result=result.value, criteria_results={key: inp.value for key,inp in inputs.items()},
                    rationale=rationale.value or "", evidence_reference=evidence.value or "")
                try: review_assessment(package(), assessment)
                except ValueError as error:
                    ui.notify(str(error), type="warning"); return
                package().fulfillment_assessments.append(assessment)
                if save("Erfüllungsbewertung gespeichert"): dialog.close()
            ui.button("Bewertung speichern", on_click=apply).props("no-caps")
        dialog.open()

    def requirement_dialog(
        requirement: EcadRequirement | None = None,
        *,
        initial_target_type: RequirementTargetType | None = None,
        initial_target_id: str | None = None,
        initial_target_name: str = "",
    ) -> None:
        current = requirement or EcadRequirement(
            title="", text="",
            origin=RequirementOrigin.DERIVED if initial_target_id else RequirementOrigin.MANUAL,
            specification_level=RequirementSpecificationLevel.DESIGN_SPECIFICATION,
            requirement_level=RequirementLevel.TECHNICAL if initial_target_id else RequirementLevel.SYSTEM,
            source_kind=(
                RequirementSourceKind.ENGINEERING_DERIVATION
                if initial_target_id else RequirementSourceKind.INTERNAL_MANUAL
            ),
        )
        is_new = requirement is None
        with ui.dialog() as dialog, ui.card().classes("w-[920px] max-w-[96vw] max-h-[94vh] overflow-auto p-6 gap-4"):
            from .help_ui import mask_help
            mask_help(dialog,'requirements',requirement,mask='Requirement bearbeiten')
            ui.label("Requirement bearbeiten" if requirement else "Requirement hinzufügen").classes("text-xl font-bold")
            if initial_target_id:
                ui.label(
                    f"Architekturobjekt {initial_target_name}: Formuliere hier nur eine tatsächlich begründete Anforderung. "
                    "Alternativ im Architektur-Inspektor bestehendes Requirement oder Designentscheidung verknüpfen."
                ).classes("text-sm text-amber-900 bg-amber-50 border rounded p-3")
            with ui.row().classes("w-full gap-3"):
                requirement_level = ui.select(
                    {**LAYER_CHOICE_LABELS, **({current.requirement_level.value: REQUIREMENT_LEVEL_LABELS[current.requirement_level.value]}
                                              if current.requirement_level.value not in LAYER_CHOICE_LABELS else {})},
                    value=current.requirement_level.value,
                    label="Anforderungsebene",
                ).classes("grow")
                solution_binding = ui.select(
                    SOLUTION_BINDING_LABELS,
                    value=current.solution_binding.value,
                    label="Lösungsbindung",
                ).classes("grow")
                source_kind = ui.select(
                    SOURCE_KIND_LABELS,
                    value=current.source_kind.value,
                    label="Quellart",
                ).classes("grow")
            with ui.row().classes("w-full gap-3"):
                classification = ui.select(
                    [item.value for item in RequirementClassification],
                    value=current.classification.value,
                    label="Disziplin",
                ).classes("grow")
                category = ui.select(
                    category_options(current.classification),
                    value=current.category.value,
                    label="Kategorie",
                ).classes("grow")
                priority = ui.select([item.value for item in RequirementPriority], value=current.priority.value, label="Priorität").classes("grow")
                maturity = ui.select([item.value for item in RequirementMaturity], value=current.maturity.value, label="Reifegrad").classes("grow")
            origin = ui.select({item.value: item.value for item in RequirementOrigin},
                               value=current.origin.value, label="Herkunft / Entstehung").classes("w-full")
            relevance = ui.select(
                [item.value for item in RequirementEcadRelevance],
                value=current.ecad_relevance.value,
                label="ECAD-Relevanz",
            ).classes("w-full")
            ecad_coupling=ui.checkbox('Expliziter Bezug zu HW / ECAD',value=current.classification in {RequirementClassification.SYSTEM,RequirementClassification.HARDWARE} or (bool(requirement) and current.ecad_relevance!=RequirementEcadRelevance.NOT_APPLICABLE))
            specification_level = ui.select(
                SPECIFICATION_LEVEL_LABELS,
                value=current.specification_level.value,
                label="Vertragliche Ebene",
            ).classes("w-full")
            ui.label(
                "Anforderungsebene, Disziplin und Prüfstatus sind unabhängig. Technische Arbeit darf bereits "
                "vor der fachlichen Freigabe beginnen; offene Ableitungen bleiben als Lücke sichtbar."
            ).classes("text-xs text-slate-500")
            with ui.row().classes("w-full gap-3"):
                identifier = ui.input(
                    "Interne ID",
                    value=current.identifier or next_requirement_identifier(
                        package(), current.classification, current.category
                    ),
                ).props("readonly outlined").classes("w-48")
                external_id = ui.input(
                    "Externe Quell-ID",
                    value=current.external_id,
                    placeholder="Optional, z. B. LHE-042",
                ).classes("w-56")
                title = ui.input("Titel", value=current.title, placeholder="Kurzer eindeutiger Titel").classes("grow")
            if is_new:
                def update_identifier(_=None) -> None:
                    identifier.value = next_requirement_identifier(
                        package(),
                        RequirementClassification(classification.value),
                        RequirementCategory(category.value),
                    )
                    identifier.update()
                classification.on_value_change(update_identifier)
                category.on_value_change(update_identifier)
                ui.label("Die interne ID wird aus Klassifizierung und Kategorie gebildet und bleibt danach stabil.").classes("text-xs text-slate-500")
            text = ui.textarea("Anforderung", value=current.text).classes("w-full").props("autogrow outlined")
            parent_options = {
                item.id: f"{item.identifier or item.id[:10]} · {item.title}"
                for item in package().requirements if item.id != current.id
            }
            parent_requirements = ui.select(
                parent_options,
                value=list(current.parent_requirement_ids),
                label="Übergeordnete Requirements / Ableitung aus",
                multiple=True,
                with_input=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            required_disciplines = ui.select(
                {
                    item.value: item.value
                    for item in RequirementClassification
                    if item != RequirementClassification.SYSTEM
                },
                value=[item.value for item in current.required_disciplines],
                label="Erforderliche fachliche Ableitungen",
                multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            satisfaction_strategy = ui.textarea(
                "Geplante Erfüllungsstrategie",
                value=current.satisfaction_strategy,
                placeholder="Welche Realisierungsanforderungen oder Umsetzungsobjekte sollen die Anforderung abdecken?",
            ).props("autogrow outlined").classes("w-full")
            direct_satisfaction = ui.textarea(
                "Begründung einer direkten Erfüllung (nur Ausnahmefall)",
                value=current.direct_satisfaction_justification,
                placeholder="Nur verwenden, wenn ein Systemrequirement ohne weitere Realisierungsanforderung direkt erfüllt wird.",
            ).props("autogrow outlined").classes("w-full")
            from .property_schema import applicable,selection_options
            attribute_values=deepcopy(current.requirement_attributes)
            attribute_inputs={}
            def collect_requirement_attributes():
                for key,(field,definition) in attribute_inputs.items():
                    value=field.value
                    if definition.data_type in {'json','list'} and not definition.selection_source or definition.data_type=='number' and isinstance(value,str):value=json.loads(value) if value else None
                    attribute_values[key]=value if value!='' else None
            @ui.refreshable
            def discipline_attributes():
                attribute_inputs.clear()
                draft=current.model_copy(deep=True);draft.classification=RequirementClassification(classification.value)
                with ui.expansion('Fachliche Anforderungsattribute',icon='tune',value=False).classes('w-full border rounded-lg'):
                    for definition in applicable(package().property_definitions,draft,'requirement_attributes'):
                        value=attribute_values.get(definition.key)
                        if definition.selection_source or definition.choices:
                            options=selection_options(definition,draft,package())
                            for entry in (value if isinstance(value,list) else [value]):
                                if isinstance(entry,str):options.setdefault(entry,entry+' (Bestandswert prüfen)')
                            field=ui.select(options,value=value,label=definition.label,multiple=definition.data_type=='list',clearable=True).props('use-input use-chips' if definition.data_type=='list' else 'use-input').classes('w-full')
                        elif definition.data_type=='number' and not isinstance(value,dict):field=ui.number(definition.label+(f' [{definition.unit}]' if definition.unit else ''),value=value).classes('w-full')
                        elif definition.data_type=='boolean':field=ui.select({True:'Ja',False:'Nein'},value=value,label=definition.label,clearable=True).classes('w-full')
                        elif definition.data_type in {'json','list'} or isinstance(value,dict):
                            field=ui.textarea(definition.label+' · JSON / Wertebereich',value=json.dumps(value,ensure_ascii=False) if value is not None else '').classes('w-full')
                        else:field=ui.input(definition.label,value=value or '').classes('w-full')
                        ui.label(definition.description).classes('text-xs text-slate-600')
                        attribute_inputs[definition.key]=(field,definition)
            discipline_attributes()
            def update_requirement_profile(_=None):
                try:collect_requirement_attributes()
                except (ValueError,TypeError):ui.notify('Fachliche Werte vor dem Disziplinwechsel prüfen.',type='warning');return
                options=category_options(classification.value)
                if category.value not in options:options[category.value]=str(category.value)+' · für diese Disziplin prüfen'
                category.options=options;category.update()
                draft=current.model_copy(deep=True);draft.classification=RequirementClassification(classification.value);draft.requirement_level=RequirementLevel(requirement_level.value)
                parents={r.id:f'{r.identifier} · {r.title}' for r in eligible_parents(package(),draft)}
                parents.update({i:parent_options.get(i,i)+' · Ableitung prüfen' for i in parent_requirements.value or [] if i not in parents})
                parent_requirements.options=parents;parent_requirements.update()
                foreign=classification.value not in {'System','Hardware'}
                ecad_coupling.set_visibility(foreign)
                relevance.set_visibility(not foreign or bool(ecad_coupling.value))
                direct_satisfaction.set_visibility(requirement_level.value==RequirementLevel.SYSTEM.value)
                required_disciplines.set_visibility(requirement_level.value!=RequirementLevel.DISCIPLINE.value)
                discipline_attributes.refresh()
            def discipline_changed(_=None):
                if classification.value not in {'System','Hardware'}:ecad_coupling.value=False;ecad_coupling.update()
                update_requirement_profile()
            classification.on_value_change(discipline_changed)
            requirement_level.on_value_change(update_requirement_profile)
            ecad_coupling.on_value_change(update_requirement_profile)
            update_requirement_profile()
            rationale = ui.textarea("Begründung / Ableitung", value=current.rationale).classes("w-full").props("autogrow outlined")
            acceptance = ui.textarea("Akzeptanzkriterien", value=current.acceptance_criteria).classes("w-full").props("autogrow outlined")
            with ui.row().classes("w-full gap-3"):
                owner = ui.input("Verantwortlich", value=current.owner).classes("grow")
                change_authority = ui.input("Änderungsfreigabe", value=current.change_authority).classes("grow")
            customer_decision=ui.select({'Open':'Offen','Accepted':'Angenommen','Rejected':'Abgelehnt'},value=current.customer_decision,label='Kundenentscheidung (L1)').classes('w-full')
            def decision_visibility(_=None):customer_decision.set_visibility(requirement_level.value==RequirementLevel.CUSTOMER.value)
            requirement_level.on_value_change(decision_visibility);decision_visibility()
            review_decision = ui.input("Prüfentscheidung / Begründung", value=current.review_decision).classes("w-full")
            standards_required = ui.checkbox(
                "Dieses Requirement benötigt eine normative oder standardbezogene Absicherung",
                value=current.standards_required,
            )
            standard_hints = ui.input(
                "Erwartete Normen / Standards",
                value=", ".join(current.standard_hints),
                placeholder="z. B. IEC 61000-4-2, USB 3.2, IPC-2221",
            ).classes("w-full")
            standard_gap_note = ui.input(
                "Offener Normenhinweis",
                value=current.standard_gap_note,
                placeholder="Was muss noch identifiziert oder beschafft werden?",
            ).classes("w-full")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply() -> None:
                    if not (title.value or "").strip() or not (text.value or "").strip():
                        ui.notify("Titel und Anforderungstext dürfen nicht leer sein.", type="warning")
                        return
                    normalized_external_id = (external_id.value or "").strip().casefold()
                    if normalized_external_id and any(
                        item.id != current.id and item.external_id.strip().casefold() == normalized_external_id
                        for item in package().requirements
                    ):
                        ui.notify("Die externe Requirement-ID ist bereits vergeben.", type="warning")
                        return
                    previous_links = list(requirement.parent_requirement_ids) if requirement else []
                    previous_level = requirement.requirement_level if requirement else None
                    previous_classification = requirement.classification if requirement else None
                    target = requirement.model_copy(deep=True) if requirement else EcadRequirement(
                        title=title.value.strip(), text=text.value.strip(), origin=RequirementOrigin.MANUAL
                    )
                    target.classification = RequirementClassification(classification.value)
                    target.category = RequirementCategory(category.value)
                    if target.category.value not in category_options(target.classification):
                        ui.notify('Bitte eine Kategorie wählen, die zur Disziplin passt.',type='warning');return
                    if is_new:
                        target.identifier = next_requirement_identifier(
                            package(), target.classification, target.category
                        )
                    target.external_id = (external_id.value or "").strip()
                    target.title = title.value.strip()
                    target.text = text.value.strip()
                    target.priority = RequirementPriority(priority.value)
                    target.maturity = RequirementMaturity(maturity.value)
                    target.ecad_relevance = RequirementEcadRelevance(relevance.value) if target.classification in {RequirementClassification.SYSTEM,RequirementClassification.HARDWARE} or ecad_coupling.value else RequirementEcadRelevance.NOT_APPLICABLE
                    target.specification_level = RequirementSpecificationLevel(specification_level.value)
                    target.requirement_level = RequirementLevel(requirement_level.value)
                    target.origin = RequirementOrigin(origin.value)
                    target.review_decision = review_decision.value or ""
                    target.customer_decision = customer_decision.value
                    if target.customer_decision=='Rejected' and not target.review_decision.strip():
                        ui.notify('Eine Ablehnung benötigt eine Begründung.',type='warning');return
                    target.solution_binding = RequirementSolutionBinding(solution_binding.value)
                    target.source_kind = RequirementSourceKind(source_kind.value)
                    selected_parents = list(dict.fromkeys(parent_requirements.value or []))
                    target.parent_requirement_ids = selected_parents
                    if set(selected_parents)-{r.id for r in eligible_parents(package(),target)}:
                        ui.notify('Übergeordnete Requirements müssen auf einer höheren Anforderungsebene liegen.',type='warning');return
                    try:
                        collect_requirement_attributes()
                        from .requirement_profiles import validate_selection
                        valid=applicable(package().property_definitions,target,'requirement_attributes')
                        target.requirement_attributes={d.key:attribute_values.get(d.key) for d in valid}
                        for d in valid:
                            value=target.requirement_attributes[d.key]
                            if value!=current.requirement_attributes.get(d.key):validate_selection(d,target,package(),value)
                        retained={k:v for k,v in attribute_values.items() if v is not None and k not in target.requirement_attributes}
                        if retained:target.attributes.setdefault('legacyPropertyValues',{})['requirement_attributes']=retained
                    except (ValueError,TypeError) as error:ui.notify(str(error),type='negative');return
                    target.required_disciplines = [
                        RequirementClassification(item)
                        for item in (required_disciplines.value or [])
                    ]
                    target.satisfaction_strategy = satisfaction_strategy.value or ""
                    target.direct_satisfaction_justification = direct_satisfaction.value or ""
                    target.owner = owner.value or ""
                    target.change_authority = change_authority.value or ""
                    target.standards_required = bool(standards_required.value)
                    target.standard_hints = [
                        item.strip() for item in (standard_hints.value or "").split(",") if item.strip()
                    ]
                    target.standard_gap_note = (standard_gap_note.value or "").strip()
                    target.rationale = rationale.value or ""
                    target.acceptance_criteria = acceptance.value or ""
                    if (not requirement or previous_links != selected_parents
                            or previous_level != target.requirement_level
                            or previous_classification != target.classification):
                        try:
                            validate_parent_links(package(), target, selected_parents)
                        except ValueError as error:
                            ui.notify(str(error), type="warning", close_button=True)
                            return
                    if requirement is None:
                        package().requirements.append(target)
                        if initial_target_type and initial_target_id:
                            package().requirement_links.append(RequirementLink(
                                requirement_id=target.id,
                                target_type=initial_target_type,
                                target_id=initial_target_id,
                                relation=RequirementRelation.ALLOCATED_TO,
                                rationale="Aus der technischen Architektur als Pflichtenheft-Kandidat abgeleitet.",
                            ))
                    else:
                        package().requirements = [target if item.id == target.id else item
                                                  for item in package().requirements]
                    package().requirement_derivations = [
                        item for item in package().requirement_derivations
                        if item.derived_requirement_id != target.id
                    ]
                    for parent_id in target.parent_requirement_ids:
                        package().requirement_derivations.append(RequirementDerivation(
                            source_requirement_id=parent_id,
                            derived_requirement_id=target.id,
                            rationale=target.rationale,
                            approved=target.maturity == RequirementMaturity.APPROVED,
                        ))
                    clear_selection(); selection["requirement_id"] = target.id
                    dialog.close(); save("Requirement gespeichert")

                ui.button("Speichern", icon="save", on_click=apply).props("no-caps")
        dialog.open()

    def engineering_conflict_dialog(
        conflict: EngineeringConflict | None = None,
        initial_requirement_id: str | None = None,
    ) -> None:
        current = conflict or EngineeringConflict(
            title="",
            requirement_ids=[initial_requirement_id] if initial_requirement_id else [],
        )
        requirement_options = {
            item.id: f"{item.identifier or item.external_id or item.id[:12]} · {item.title}"
            for item in package().requirements
        }
        target_options: dict[str, str] = {"": "Kein konkretes Umsetzungsobjekt"}
        for domain in package().domains:
            target_options[f"{RequirementTargetType.DOMAIN.value}|{domain.id}"] = f"Domain · {domain.name}"
            for element in domain.elements:
                target_options[f"{RequirementTargetType.ELEMENT.value}|{element.id}"] = (
                    f"Architecture Element · {domain.name} / {element.name}"
                )
        for signal in package().signals:
            target_options[f"{RequirementTargetType.SIGNAL.value}|{signal.id}"] = f"Signal / Interface · {signal.name}"
        for connection in package().connections:
            target_options[f"{RequirementTargetType.CONNECTION.value}|{connection.id}"] = f"Verbindung · {connection.name}"
        for component in package().components:
            target_options[f"{RequirementTargetType.COMPONENT.value}|{component.id}"] = f"Komponente · {component.name}"
        current_target = (
            f"{current.target_type.value}|{current.target_id}"
            if current.target_type and current.target_id else ""
        )
        with ui.dialog() as dialog, ui.card().classes("w-[780px] max-w-[96vw] p-6 gap-4"):
            ui.label("Umsetzungskonflikt bearbeiten" if conflict else "Umsetzungskonflikt erfassen").classes("text-xl font-bold")
            ui.label(
                "Ein Konflikt ändert weder Requirement noch Architektur automatisch. Die fachliche Entscheidung bleibt nachvollziehbar im Projekt erhalten."
            ).classes("text-sm text-blue-900 bg-blue-50 border border-blue-200 rounded-lg p-3")
            title = ui.input("Titel", value=current.title, placeholder="z. B. Leistungsaufnahme mit Bauraum nicht erreichbar").classes("w-full")
            requirements = ui.select(
                requirement_options,
                value=list(current.requirement_ids),
                label="Betroffene Requirements",
                multiple=True,
                with_input=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            target = ui.select(
                target_options,
                value=current_target,
                label="Betroffenes Umsetzungsobjekt (optional)",
                with_input=True,
            ).classes("w-full")
            description = ui.textarea("Abweichung / Kollision", value=current.description).props("outlined autogrow").classes("w-full")
            with ui.row().classes("w-full gap-3"):
                cause = ui.textarea("Ursache", value=current.cause).props("outlined autogrow").classes("grow")
                impact = ui.textarea("Auswirkung", value=current.impact).props("outlined autogrow").classes("grow")
            with ui.row().classes("w-full gap-3"):
                status = ui.select(
                    CONFLICT_STATUS_LABELS,
                    value=current.status.value,
                    label="Status",
                ).classes("grow")
                resolution = ui.select(
                    CONFLICT_RESOLUTION_LABELS,
                    value=current.resolution.value,
                    label="Entscheidung",
                ).classes("grow")
            resolution_note = ui.textarea(
                "Entscheidung und Begründung",
                value=current.resolution_note,
            ).props("outlined autogrow").classes("w-full")
            with ui.row().classes("w-full justify-between"):
                if conflict:
                    def remove() -> None:
                        package().engineering_conflicts = [
                            item for item in package().engineering_conflicts if item.id != conflict.id
                        ]
                        dialog.close(); save("Umsetzungskonflikt gelöscht")
                    ui.button("Löschen", icon="delete_outline", on_click=remove).props("flat no-caps color=negative")
                else:
                    ui.space()
                with ui.row().classes("gap-2"):
                    ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                    def apply() -> None:
                        if not (title.value or "").strip() or not requirements.value:
                            ui.notify("Titel und mindestens ein betroffenes Requirement sind erforderlich.", type="warning")
                            return
                        selected_status = EngineeringConflictStatus(status.value)
                        selected_resolution = EngineeringConflictResolution(resolution.value)
                        if selected_status in {
                            EngineeringConflictStatus.RESOLVED,
                            EngineeringConflictStatus.ACCEPTED_DEVIATION,
                        } and selected_resolution == EngineeringConflictResolution.UNDECIDED:
                            ui.notify("Für einen abgeschlossenen Konflikt ist eine Entscheidung erforderlich.", type="warning")
                            return
                        target_type = None
                        target_id = None
                        if target.value:
                            target_type_value, target_id = str(target.value).split("|", 1)
                            target_type = RequirementTargetType(target_type_value)
                        item = conflict or EngineeringConflict(title=title.value.strip())
                        item.title = title.value.strip()
                        item.requirement_ids = list(requirements.value or [])
                        item.target_type = target_type
                        item.target_id = target_id
                        item.description = description.value or ""
                        item.cause = cause.value or ""
                        item.impact = impact.value or ""
                        item.status = selected_status
                        item.resolution = selected_resolution
                        item.resolution_note = resolution_note.value or ""
                        item.resolved_at = (
                            utc_now()
                            if selected_status in {
                                EngineeringConflictStatus.RESOLVED,
                                EngineeringConflictStatus.ACCEPTED_DEVIATION,
                            }
                            else None
                        )
                        if conflict is None:
                            package().engineering_conflicts.append(item)
                        dialog.close(); save("Umsetzungskonflikt gespeichert")

                    ui.button("Speichern", icon="save", on_click=apply).props("no-caps")
        dialog.open()

    def allocation_dialog(requirement: EcadRequirement) -> None:
        options: dict[str, str] = {}
        type_lookup: dict[str, RequirementTargetType] = {}
        for domain in package().domains:
            key = f"Domain|{domain.id}"; options[key] = f"Domain · {domain.name}"; type_lookup[key] = RequirementTargetType.DOMAIN
            for element in domain.elements:
                key = f"ArchitectureElement|{element.id}"; options[key] = f"AE · {domain.name} / {element.name}"; type_lookup[key] = RequirementTargetType.ELEMENT
        for signal in package().signals:
            key = f"ArchitectureSignal|{signal.id}"; options[key] = f"Interface/Signal · {signal.name}"; type_lookup[key] = RequirementTargetType.SIGNAL
        for component in package().components:
            key = f"Component|{component.id}"; options[key] = f"Komponente · {component.name}"; type_lookup[key] = RequirementTargetType.COMPONENT
        from .property_schema import KIND_LABELS
        from .requirement_graph import allocation_edges
        for kind,group in project_objects(package()).items():
            typ='TechnicalRealization' if kind=='Realization' else kind
            try:target_type=RequirementTargetType(typ)
            except ValueError:continue
            if target_type==RequirementTargetType.VERIFICATION_CASE:continue
            for oid,obj in group.items():
                key=typ+'|'+oid;options[key]=KIND_LABELS.get(typ,typ)+' · '+getattr(obj,'name',getattr(obj,'title',oid));type_lookup[key]=target_type
        existing = [
            f"{item.target_type.value}|{item.target_id}"
            for item in package().requirement_links if item.requirement_id == requirement.id
        ]
        existing=sorted({('TechnicalRealization' if kind=='Realization' else kind)+'|'+oid for rid,kind,oid in allocation_edges(package()) if rid==requirement.id} & set(options))
        with ui.dialog() as dialog, ui.card().classes("w-[650px] max-w-[95vw] p-6 gap-4"):
            ui.label("Requirement zuordnen").classes("text-xl font-bold")
            ui.label(requirement.title).classes("font-medium")
            targets = ui.select(options, value=existing, label="Architektur- und Komponentenobjekte", multiple=True).props("use-chips outlined options-dense").classes("w-full")
            relation = ui.select([item.value for item in RequirementRelation if item!=RequirementRelation.VERIFIED_BY], value=RequirementRelation.ALLOCATED_TO.value, label="Beziehung für neue Zuordnungen").classes("w-full")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply() -> None:
                    old_relations = {
                        (item.target_type, item.target_id): item.relation
                        for item in package().requirement_links if item.requirement_id == requirement.id
                    }
                    chosen=set(targets.value or [])
                    package().requirement_links = [item for item in package().requirement_links if item.requirement_id != requirement.id or item.relation==RequirementRelation.VERIFIED_BY]
                    for kind,group in project_objects(package()).items():
                        typ='TechnicalRealization' if kind=='Realization' else kind
                        for oid,obj in group.items():
                            key=typ+'|'+oid
                            if key in options and key not in chosen and hasattr(obj,'requirement_ids'):
                                obj.requirement_ids=[rid for rid in obj.requirement_ids if rid!=requirement.id]
                    package().model_relations=[r for r in package().model_relations if not (
                        r.kind=='allocated_to' and r.source_id==requirement.id and
                        ('TechnicalRealization' if r.target_type=='Realization' else r.target_type)+'|'+r.target_id not in chosen)]
                    for value in targets.value or []:
                        target_type = type_lookup[value]
                        target_id = value.split("|", 1)[1]
                        package().requirement_links.append(RequirementLink(
                            requirement_id=requirement.id,
                            target_type=target_type,
                            target_id=target_id,
                            relation=old_relations.get((target_type, target_id), RequirementRelation(relation.value)),
                        ))
                    dialog.close(); save("Requirement-Zuordnungen gespeichert")

                ui.button("Zuordnungen speichern", icon="link", on_click=apply).props("no-caps")
        dialog.open()

    def confirm_requirement_delete(requirement: EcadRequirement) -> None:
        link_count = sum(item.requirement_id == requirement.id for item in package().requirement_links)
        standard_count = sum(
            item.requirement_id == requirement.id for item in package().requirement_standard_links
        )
        verification_count = sum(
            requirement.id in item.requirement_ids for item in package().verification_cases
        )
        with ui.dialog() as dialog, ui.card().classes("w-[520px] p-6 gap-4"):
            ui.label("System-Requirement löschen?").classes("text-xl font-bold")
            ui.label(requirement.title).classes("font-medium")
            ui.label(
                f"Dabei werden {link_count} Architektur-/Komponentenzuordnung(en), "
                f"{standard_count} Normenbezug/Bezüge und die Zuordnung in "
                f"{verification_count} Verifikationsfall/-fällen entfernt. "
                "Verifikationsfälle ohne verbleibendes Requirement werden ebenfalls gelöscht; "
                "Architekturobjekte bleiben bestehen."
            ).classes("text-sm text-slate-600")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")
                def apply() -> None:
                    delete_requirement(package(), requirement.id)
                    reset(); dialog.close(); save("System-Requirement gelöscht")
                ui.button("Löschen", icon="delete", on_click=apply).props("color=negative no-caps")
        dialog.open()


    return RequirementsEditUiViews(
        requirement_dialog=requirement_dialog,
        engineering_conflict_dialog=engineering_conflict_dialog,
        allocation_dialog=allocation_dialog,
        confirm_requirement_delete=confirm_requirement_delete,
        relation_dialog=relation_dialog,
        observation_dialog=observation_dialog,
        assessment_dialog=assessment_dialog,
    )
