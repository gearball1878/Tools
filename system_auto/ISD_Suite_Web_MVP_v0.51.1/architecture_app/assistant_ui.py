"""Reviewed assistant chat and action preview.

Explicit callbacks keep project state in the page controller.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from .requirements_presentation import format_assistant_entry_for_copy
import asyncio
import json
from nicegui import run, ui
from .assistant_workflow import AssistantRequestKind, classify_assistant_request, resolve_assistant_document_ids
from .ai_provider import AIConsultationResult
from .models import AIChangeItemStatus, AIReviewStatus, DocumentAnalysisStage, ProposalStatus, utc_now
from .requirements_service import add_document_analysis, apply_ai_change_proposal, create_ai_change_proposal, create_ai_review

@dataclass(frozen=True)
class AssistantUiViews:
    open_ai_assistant: Callable[..., Any]


def create_assistant_ui(
    *,
    accept_all_proposal,
    accept_proposal,
    ai_provider,
    architecture_catalog,
    build_ai_document_context,
    builtins,
    clear_selection,
    configure_ai,
    create_safety_revision,
    document_context_available,
    filters,
    generate_proposal,
    load_ai_chat,
    load_document_context,
    package,
    page_state,
    reject_ai_review_dialog,
    reject_proposal_dialog,
    review_integration,
    save,
    selected_component,
    selected_interface,
    selected_requirement,
    selection,
    set_ai_review_status,
    set_job,
    store_ai_chat,
    update_ai_chat,
) -> AssistantUiViews:
    def open_ai_assistant() -> None:
        layout_state = {"maximized": False}
        with ui.dialog().props("position=right") as dialog:
            from .help_ui import HelpContext
            dialog._isd_help_context=HelpContext('documents',mask='KI-Assistent')
            card = ui.card().classes("ai-assistant-panel ai-assistant-normal p-0 gap-0")
            with card:
                with ui.row().classes("w-full items-center gap-3 px-5 py-4 border-b bg-slate-50"):
                    ui.icon("auto_awesome", size="30px", color="primary")
                    with ui.column().classes("gap-0 grow"):
                        ui.label("ISD KI-Assistent").classes("text-xl font-bold")
                        ui.label("Frage, Antwort und kontrollierte Aktion in einem Verlauf").classes("subtle")

                    def toggle_size() -> None:
                        layout_state["maximized"] = not layout_state["maximized"]
                        card.classes(
                            add="ai-assistant-max" if layout_state["maximized"] else "ai-assistant-normal",
                            remove="ai-assistant-normal" if layout_state["maximized"] else "ai-assistant-max",
                        )

                    ui.button(icon="open_in_full", on_click=toggle_size).props("flat round dense").tooltip("Breite umschalten")
                    ui.button(icon="close", on_click=dialog.close).props("flat round dense")

                @ui.refreshable
                def assistant_provider_status() -> None:
                    if ai_provider.is_ready:
                        with ui.row().classes("w-full items-center gap-2 px-5 py-3 bg-emerald-50 border-b"):
                            ui.icon("check_circle", color="positive")
                            ui.label(
                                f"Sofort einsatzbereit · {ai_provider.display_name} · {ai_provider.model_name}"
                            ).classes("text-sm font-medium text-emerald-900 grow")
                            ui.button(
                                "Ändern",
                                on_click=lambda: configure_ai(assistant_provider_status.refresh),
                            ).props("flat dense no-caps")
                    else:
                        with ui.row().classes("w-full items-center gap-2 px-5 py-3 bg-amber-50 border-b"):
                            ui.icon("key", color="warning")
                            ui.label(
                                "Kein KI-Provider für diese Sitzung konfiguriert."
                            ).classes("text-sm grow")
                            ui.button(
                                "Konfigurieren",
                                on_click=lambda: configure_ai(assistant_provider_status.refresh),
                            ).props("outline dense no-caps")

                assistant_provider_status()

                async def copy_assistant_text(value: str) -> None:
                    script = f"""
                    (() => {{
                      const value = {json.dumps(value)};
                      if (navigator.clipboard && window.isSecureContext) {{
                        return navigator.clipboard.writeText(value);
                      }}
                      const area = document.createElement('textarea');
                      area.value = value;
                      area.style.position = 'fixed';
                      area.style.opacity = '0';
                      document.body.appendChild(area);
                      area.focus();
                      area.select();
                      document.execCommand('copy');
                      document.body.removeChild(area);
                      return Promise.resolve();
                    }})()
                    """
                    try:
                        await ui.run_javascript(script, timeout=5.0)
                        ui.notify("Antwort kopiert", type="positive", timeout=1000)
                    except Exception as error:
                        ui.notify(f"Kopieren fehlgeschlagen: {error}", type="negative", close_button=True)

                def set_architecture_action_selected(
                    proposal_id: str,
                    action_type: str,
                    candidate_id: str,
                    selected: bool,
                ) -> None:
                    proposal = package().find_architecture_proposal(proposal_id)
                    if proposal is None or proposal.status != ProposalStatus.DRAFT:
                        return
                    candidates = {
                        "domain": proposal.domains,
                        "element": proposal.elements,
                        "interface": proposal.interfaces,
                        "system_elements": proposal.system_elements,
                        "mechanical_elements": proposal.mechanical_elements,
                        "software_elements": proposal.software_elements,
                        "function_elements": proposal.function_elements,
                    }[action_type]
                    candidate = next((item for item in candidates if item.candidate_id == candidate_id), None)
                    if candidate is None:
                        return
                    candidate.selected_for_execution = bool(selected)
                    save("Auftragsauswahl gespeichert")
                    assistant_history.refresh()

                @ui.refreshable
                def assistant_history() -> None:
                    entries: list[tuple[str, str, Any]] = []
                    entries.extend((item.created_at, "chat", item) for item in load_ai_chat())
                    entries.extend((item.created_at, "review", item) for item in package().ai_reviews)
                    entries.extend((item.created_at, "change", item) for item in package().ai_change_proposals)
                    entries.extend((item.created_at, "architecture", item) for item in package().architecture_proposals)
                    entries.sort(key=lambda item: item[0])
                    if not entries:
                        with ui.column().classes("w-full items-center text-center py-10 text-slate-500"):
                            ui.icon("forum", size="48px")
                            ui.label("Noch keine Unterhaltung in diesem Projekt.").classes("font-medium")
                            ui.label(
                                "Fragen, Antworten und vorgeschlagene Aktionen erscheinen gemeinsam hier."
                            ).classes("subtle")
                        return
                    for _, entry_type, entry in entries:
                        prompt_text = entry.prompt if entry_type != "architecture" else entry.guidance
                        if prompt_text:
                            with ui.row().classes("w-full justify-end pl-12"):
                                with ui.card().classes("assistant-user-message p-3 gap-1"):
                                    ui.label("Du").classes("text-xs font-bold text-blue-800")
                                    ui.label(prompt_text).classes("text-sm whitespace-pre-wrap")
                        with ui.row().classes("w-full justify-start pr-10"):
                            with ui.card().classes("assistant-ai-message w-full p-4 gap-3"):
                                with ui.row().classes("w-full items-center gap-2"):
                                    ui.icon("auto_awesome", size="18px", color="primary")
                                    ui.label("ISD KI-Assistent").classes("text-xs font-bold grow")
                                    copy_text = format_assistant_entry_for_copy(entry_type, entry)
                                    ui.button(
                                        icon="content_copy",
                                        on_click=lambda _, value=copy_text: copy_assistant_text(value),
                                    ).props("flat round dense").tooltip("Vollständige Antwort kopieren")
                                    status_value = getattr(entry, "status", ProposalStatus.DRAFT)
                                    status_text = (
                                        status_value.value if hasattr(status_value, "value") else str(status_value)
                                    )
                                    ui.badge(
                                        status_text,
                                        color=(
                                            "green-2" if status_text == "Accepted"
                                            else "red-2" if status_text == "Rejected"
                                            else "amber-2"
                                        ),
                                    ).props("text-color=grey-9")
                                if entry_type in {"review", "chat"}:
                                    ui.label(entry.answer).classes("text-sm leading-relaxed whitespace-pre-wrap")
                                    if entry.findings:
                                        with ui.expansion(f"Befunde ({len(entry.findings)})", icon="search").classes("w-full border rounded-lg"):
                                            for value in entry.findings:
                                                ui.label(f"• {value}").classes("text-sm")
                                    if entry.recommendations:
                                        with ui.expansion(f"Empfehlungen ({len(entry.recommendations)})", icon="lightbulb").classes("w-full border rounded-lg"):
                                            for value in entry.recommendations:
                                                ui.label(f"• {value}").classes("text-sm")
                                    if entry.open_questions:
                                        with ui.expansion(f"Offene Fragen ({len(entry.open_questions)})", icon="help_outline").classes("w-full border rounded-lg"):
                                            for value in entry.open_questions:
                                                ui.label(f"• {value}").classes("text-sm")
                                    if entry_type == "chat" and entry.status == "Draft":
                                        def accept_chat(message=entry) -> None:
                                            review = create_ai_review(
                                                package(),
                                                AIConsultationResult(
                                                    title="Übernommene KI-Reviewnotiz",
                                                    answer=message.answer,
                                                    findings=list(message.findings),
                                                    recommendations=list(message.recommendations),
                                                    open_questions=list(message.open_questions),
                                                ),
                                                message.prompt,
                                                message.provider,
                                                message.model,
                                            )
                                            review.status = AIReviewStatus.ACCEPTED
                                            review.reviewed_at = utc_now()
                                            update_ai_chat(message.id, "Accepted", review.id)
                                            save("KI-Antwort als Review-Notiz übernommen")
                                            assistant_history.refresh()

                                        def reject_chat(message=entry) -> None:
                                            update_ai_chat(message.id, "Rejected", None)
                                            assistant_history.refresh()

                                        with ui.row().classes("w-full justify-end gap-2"):
                                            ui.button(
                                                "Als Review-Notiz übernehmen", icon="check",
                                                on_click=accept_chat,
                                            ).props("flat dense no-caps")
                                            ui.button(
                                                "Verwerfen", icon="block", on_click=reject_chat,
                                            ).props("flat dense no-caps color=negative")
                                    elif entry_type == "review" and entry.status == AIReviewStatus.DRAFT:
                                        with ui.row().classes("w-full justify-end gap-2"):
                                            ui.button(
                                                "Als Review-Notiz übernehmen", icon="check",
                                                on_click=lambda _, review_id=entry.id: (
                                                    set_ai_review_status(review_id, AIReviewStatus.ACCEPTED),
                                                    assistant_history.refresh(),
                                                ),
                                            ).props("flat dense no-caps")
                                            ui.button(
                                                "Verwerfen", icon="block",
                                                on_click=lambda _, review_id=entry.id: reject_ai_review_dialog(review_id),
                                            ).props("flat dense no-caps color=negative")
                                elif entry_type == "change":
                                    ui.badge("Auftrag vorbereitet", color="blue-2").props("text-color=blue-9")
                                    ui.label(entry.answer or entry.title).classes("text-sm leading-relaxed whitespace-pre-wrap")
                                    if not entry.changes:
                                        ui.label("Keine direkt anwendbare Feldänderung erkannt.").classes("subtle")
                                    for change in entry.changes:
                                        with ui.card().classes("w-full p-3 gap-2 border"):
                                            with ui.row().classes("w-full items-center gap-2"):
                                                ui.label(
                                                    f"{change.object_type.value} · {change.object_id}"
                                                ).classes("text-xs font-mono grow")
                                                ui.badge(change.status.value, color="grey-3").props("text-color=grey-9")
                                            ui.label(change.field_name).classes("font-semibold")
                                            with ui.grid(columns=2).classes("w-full gap-2"):
                                                with ui.column().classes("gap-0 rounded bg-red-50 p-2"):
                                                    ui.label("Vorher").classes("text-xs font-bold text-red-700")
                                                    ui.label(change.before_value or "—").classes("text-sm")
                                                with ui.column().classes("gap-0 rounded bg-green-50 p-2"):
                                                    ui.label("Nachher").classes("text-xs font-bold text-green-700")
                                                    ui.label(change.after_value or "—").classes("text-sm")
                                            if change.rationale:
                                                ui.label(change.rationale).classes("subtle")
                                            if entry.status == ProposalStatus.DRAFT and change.status != AIChangeItemStatus.APPLIED:
                                                def set_change_status(
                                                    status: AIChangeItemStatus,
                                                    item=change,
                                                ) -> None:
                                                    item.status = status
                                                    save("KI-Einzeländerung bewertet")
                                                    assistant_history.refresh()
                                                with ui.row().classes("w-full justify-end gap-1"):
                                                    ui.button(
                                                        "Annehmen", icon="check",
                                                        on_click=lambda _, item=change: set_change_status(AIChangeItemStatus.ACCEPTED, item),
                                                    ).props("flat dense no-caps")
                                                    ui.button(
                                                        "Ablehnen", icon="block",
                                                        on_click=lambda _, item=change: set_change_status(AIChangeItemStatus.REJECTED, item),
                                                    ).props("flat dense no-caps color=negative")
                                    if entry.status == ProposalStatus.DRAFT and entry.changes:
                                        def apply_changes(proposal_id=entry.id) -> None:
                                            proposal = package().find_ai_change_proposal(proposal_id)
                                            if proposal is None:
                                                return
                                            if not any(
                                                item.status == AIChangeItemStatus.ACCEPTED
                                                for item in proposal.changes
                                            ):
                                                ui.notify("Es wurde noch keine Einzeländerung angenommen.", type="warning")
                                                return
                                            if not create_safety_revision(
                                                f"Vor Anwendung des KI-Änderungsvorschlags {proposal.title}"
                                            ):
                                                return
                                            try:
                                                count = apply_ai_change_proposal(package(), proposal.id)
                                            except Exception as error:
                                                ui.notify(str(error), type="negative", close_button=True)
                                                return
                                            save(f"{count} geprüfte KI-Änderung(en) angewendet")
                                            assistant_history.refresh()
                                        ui.button(
                                            "Angenommene Änderungen anwenden",
                                            icon="published_with_changes",
                                            on_click=apply_changes,
                                        ).props("no-caps").classes("self-end")
                                else:
                                    unresolved_catalog_ids = {
                                        str(item.get("candidateId", ""))
                                        for item in entry.properties.get("unresolvedCatalogBindings", [])
                                        if isinstance(item, dict)
                                    }
                                    signal_conflict_ids = {
                                        str(item.get("candidateId", ""))
                                        for item in entry.properties.get("signalNameConflicts", [])
                                        if isinstance(item, dict)
                                    }
                                    reused_signal_ids = {
                                        str(item.get("candidateId", ""))
                                        for item in entry.properties.get("reusedArchitectureSignals", [])
                                        if isinstance(item, dict)
                                    }
                                    selected_domains = sum(item.selected_for_execution for item in entry.domains)
                                    selected_elements = sum(item.selected_for_execution for item in entry.elements)
                                    selected_interfaces = sum(item.selected_for_execution for item in entry.interfaces)
                                    selected_discipline = sum(item.selected_for_execution for field in ('system_elements','mechanical_elements','software_elements','function_elements') for item in getattr(entry,field))
                                    with ui.row().classes("w-full items-center gap-2"):
                                        ui.badge("Auftrag vorbereitet", color="blue-2").props("text-color=blue-9")
                                        ui.label(
                                            f"{selected_domains}/{len(entry.domains)} Domains · "
                                            f"{selected_elements}/{len(entry.elements)} Architecture Elements · "
                                            f"{selected_interfaces}/{len(entry.interfaces)} Interfaces · {selected_discipline} System-/Fach-/FE-Elemente ausgewählt"
                                        ).classes("text-sm")
                                    ui.label(
                                        "Der Auftrag kann auch in einem bestehenden Projekt aus den vorhandenen "
                                        "Requirements und wiederverwendbaren Dokumentkontexten ausgeführt werden."
                                    ).classes("subtle")
                                    if entry.domains:
                                        with ui.expansion(
                                            f"Domains ({len(entry.domains)})", icon="folder"
                                        ).classes("w-full border rounded-lg"):
                                            for item in entry.domains:
                                                with ui.column().classes("w-full gap-1 py-1"):
                                                    with ui.row().classes("w-full items-center gap-2"):
                                                        ui.checkbox(
                                                            item.name,
                                                            value=item.selected_for_execution,
                                                            on_change=lambda event, proposal_id=entry.id, candidate_id=item.candidate_id: (
                                                                set_architecture_action_selected(
                                                                    proposal_id, "domain", candidate_id, event.value
                                                                )
                                                            ),
                                                        ).classes("grow")
                                                        ui.badge(
                                                            item.domain_type_id,
                                                            color="blue-1",
                                                        ).props("text-color=blue-9")
                                                    if item.partition_rationale:
                                                        ui.label(item.partition_rationale).classes(
                                                            "text-xs text-slate-500 pl-10"
                                                        )
                                    if entry.elements:
                                        domain_names = {item.candidate_id: item.name for item in entry.domains}
                                        with ui.expansion(
                                            f"Architecture Elements ({len(entry.elements)})", icon="memory"
                                        ).classes("w-full border rounded-lg"):
                                            for item in entry.elements:
                                                with ui.row().classes("w-full items-center gap-2"):
                                                    ui.checkbox(
                                                        item.name,
                                                        value=item.selected_for_execution,
                                                        on_change=lambda event, proposal_id=entry.id, candidate_id=item.candidate_id: (
                                                            set_architecture_action_selected(
                                                                proposal_id, "element", candidate_id, event.value
                                                            )
                                                        ),
                                                    ).classes("grow")
                                                    ui.badge(
                                                        domain_names.get(item.domain_candidate_id, "Domain offen"),
                                                        color="grey-3",
                                                    ).props("text-color=grey-9")
                                                    ui.badge(
                                                        item.role_type_id,
                                                        color="teal-1",
                                                    ).props("text-color=teal-9")
                                                if item.partition_rationale:
                                                    ui.label(item.partition_rationale).classes(
                                                        "text-xs text-slate-500 pl-10"
                                                    )
                                    if entry.interfaces:
                                        element_names = {
                                            item.candidate_id: item.name for item in entry.elements
                                        }
                                        with ui.expansion(
                                            f"Verbindungen & Signale ({len(entry.interfaces)})", icon="hub"
                                        ).classes("w-full border rounded-lg"):
                                            for item in entry.interfaces:
                                                with ui.column().classes("w-full gap-1 border-b py-2"):
                                                    with ui.row().classes("w-full items-center gap-2"):
                                                        ui.checkbox(
                                                            item.name,
                                                            value=item.selected_for_execution,
                                                            on_change=lambda event, proposal_id=entry.id, candidate_id=item.candidate_id: (
                                                                set_architecture_action_selected(
                                                                    proposal_id, "interface", candidate_id, event.value
                                                                )
                                                            ),
                                                        ).classes("grow")
                                                        ui.badge(
                                                            (
                                                                "Template-Zuordnung offen"
                                                                if item.candidate_id in unresolved_catalog_ids
                                                                else "Namens-/Topologiekonflikt"
                                                                if item.candidate_id in signal_conflict_ids
                                                                else "Vorhandenes Signal wiederverwendet"
                                                                if item.candidate_id in reused_signal_ids
                                                                else f"{item.catalog_family} · {item.interface_template or 'Template offen'}"
                                                            ),
                                                            color=(
                                                                "amber-2"
                                                                if (
                                                                    item.candidate_id in unresolved_catalog_ids
                                                                    or item.candidate_id in signal_conflict_ids
                                                                    or not item.interface_template
                                                                )
                                                                else "blue-1"
                                                                if item.candidate_id in reused_signal_ids
                                                                else "teal-1"
                                                            ),
                                                        ).props("text-color=grey-9")
                                                    endpoint_text = (
                                                        f"{element_names.get(item.host_element_candidate_id or '', 'Host offen')} → "
                                                        + ", ".join(
                                                            element_names.get(value, value)
                                                            for value in item.participant_element_candidate_ids
                                                        )
                                                    )
                                                    ui.label(endpoint_text).classes("text-xs font-medium pl-10")
                                                    if item.observed_signal_names:
                                                        ui.label(
                                                            "Beobachtet: " + ", ".join(item.observed_signal_names)
                                                        ).classes("text-xs text-slate-500 pl-10")
                                                    if item.source_locator or item.connection_evidence:
                                                        ui.label(
                                                            " · ".join(filter(None, [
                                                                item.source_locator, item.connection_evidence,
                                                            ]))
                                                        ).classes("text-xs text-slate-500 pl-10 line-clamp-2")
                                                    with ui.row().classes("pl-10 gap-1"):
                                                        ui.badge(
                                                            f"Richtung {item.direction_confidence:.0%}", color="blue-1"
                                                        ).props("text-color=blue-9")
                                                        ui.badge(
                                                            f"Topologie {item.topology_confidence:.0%}", color="blue-1"
                                                        ).props("text-color=blue-9")
                                                        if item.excluded_internal_signal_count:
                                                            ui.badge(
                                                                f"{item.excluded_internal_signal_count} interne Netze nicht übernommen",
                                                                color="grey-3",
                                                            ).props("text-color=grey-9")
                                    confirmed=entry.properties.get('confirmedScope')
                                    if confirmed:
                                        with ui.expansion('Bestätigter Umfang und Requirement-Herkunft',value=True).classes('w-full border rounded'):
                                            ui.label('Zielarchitekturen: '+', '.join(confirmed['targetViews']))
                                            for identifier in confirmed['requirementIds']:
                                                requirement=package().find_requirement(identifier)
                                                ui.label(requirement.identifier+' · '+requirement.title if requirement else 'Requirement fehlt: '+identifier)
                                            for collection in ('domains','elements','interfaces','system_elements','software_elements','mechanical_elements','function_elements'):
                                                for candidate in getattr(entry,collection):
                                                    sources=[package().find_requirement(i) for i in candidate.requirement_ids]
                                                    ui.label(candidate.name+' ← '+(', '.join(r.identifier for r in sources if r) or 'Herkunft offen')).classes('text-xs')
                                    for field,caption in [('system_elements','Systemarchitektur'),('mechanical_elements','Mechanikarchitektur'),('software_elements','Softwarearchitektur'),('function_elements','Funktions Elemente (FE)')]:
                                        candidates=getattr(entry,field)
                                        if not candidates:continue
                                        with ui.expansion(f'{caption} · {len(candidates)} Aktionen',value=True).classes('w-full border rounded-lg'):
                                            for item in candidates:
                                                if entry.status == ProposalStatus.DRAFT:
                                                    ui.checkbox(item.name,value=item.selected_for_execution,on_change=lambda e,pid=entry.id,cid=item.candidate_id,f=field:set_architecture_action_selected(pid,f,cid,e.value))
                                                else:ui.label(item.name).classes('font-semibold')
                                                if item.description:ui.label(item.description).classes('text-sm text-slate-600')
                                    if entry.open_questions:
                                        with ui.expansion(f"Offene Fragen ({len(entry.open_questions)})", icon="help_outline").classes("w-full border rounded-lg"):
                                            for value in entry.open_questions:
                                                ui.label(f"• {value}").classes("text-sm")
                                    if entry.status == ProposalStatus.DRAFT:
                                        ui.label(
                                            "Nicht ausgewählte Elemente werden nicht übernommen. Elemente einer abgewählten "
                                            "Domain werden automatisch ausgelassen."
                                        ).classes("text-xs text-slate-500")
                                        with ui.row().classes("w-full justify-end gap-2 flex-wrap"):
                                            ui.button(
                                                "Verwerfen", icon="block",
                                                on_click=lambda _, proposal_id=entry.id: reject_proposal_dialog(proposal_id),
                                            ).props("flat dense no-caps color=negative")
                                            ui.button(
                                                "Alles ausführen",
                                                icon="done_all",
                                                on_click=lambda _, proposal_id=entry.id: accept_all_proposal(proposal_id),
                                            ).props("outline dense no-caps")
                                            ui.button(
                                                "Ausgewählte Aktionen ausführen",
                                                icon="publish",
                                                on_click=lambda _, proposal_id=entry.id: accept_proposal(proposal_id),
                                            ).props("dense no-caps")

                with ui.scroll_area().classes("assistant-chat-scroll w-full grow px-5 py-4") as chat_scroll:
                    assistant_history()
                ui.timer(0.2, lambda: chat_scroll.scroll_to(percent=1), once=True)

                with ui.column().classes("w-full gap-3 px-5 py-4 border-t bg-white"):
                    current_object_id = (
                        selection["requirement_id"] or selection["component_id"]
                        or selection["standard_id"] or selection["interface_id"] or selection["realization_id"] or selection["architecture_id"]
                        or selection["document_id"] or getattr(page_state, "selected_id", None) or ""
                    )
                    with ui.row().classes("w-full gap-2 flex-wrap"):
                        if current_object_id:
                            ui.badge(f"Aktuelles Objekt · {current_object_id[:18]}", color="blue-1").props("text-color=blue-9")
                        ui.badge(f"Ansicht · {filters['section']}", color="grey-3").props("text-color=grey-9")
                        ui.badge(f"{len(package().source_documents)} Dokumente", color="grey-3").props("text-color=grey-9")
                    with ui.row().classes("w-full gap-3"):
                        mode = ui.select(
                            {
                                "auto": "Automatisch erkennen",
                                "ask": "Nur antworten",
                                "order": "Auftrag vorbereiten",
                            },
                            value="auto",
                            label="Arbeitsweise",
                        ).classes("w-56")
                        context_scope = ui.select(
                            ["Aktuelles Objekt", "Aktuelle Ansicht", "Ausgewählte Dokumente", "Gesamtes Projekt"],
                            value="Aktuelle Ansicht",
                            label="Kontext",
                        ).classes("grow")
                    selected_documents = ui.select(
                        {
                            item.id: (
                                f"{item.name} · Kontext verfügbar"
                                if document_context_available(item)
                                else f"{item.name} · Kontext fehlt"
                            )
                            for item in package().source_documents
                        },
                        value=[],
                        label="Ausgewählte Dokumente",
                        multiple=True,
                    ).props("use-chips outlined options-dense").classes("w-full")
                    prompt = ui.textarea(
                        "Nachricht",
                        placeholder=(
                            "Frage stellen oder Auftrag formulieren, z. B. „Erzeuge aus den analysierten "
                            "Dokumenten einen initialen Architektur-Arbeitsstand.“"
                        ),
                    ).props("outlined autogrow rows=3 id=isd-chat-prompt").classes("w-full")
                    running = {"value": False}
                    with ui.row().classes("items-center gap-2 text-blue-800") as busy_indicator:
                        ui.spinner("dots", size="sm")
                        ui.label("KI arbeitet · Antwort wird vorbereitet …").classes("text-sm")
                    busy_indicator.set_visibility(False)

                    async def run_prompt() -> None:
                        question = (prompt.value or "").strip()
                        if running["value"]:
                            return
                        if not ai_provider.is_ready:
                            ui.notify("Die KI ist nicht konfiguriert.", type="warning")
                            return
                        if not question:
                            ui.notify("Bitte eine Nachricht eingeben.", type="warning")
                            return
                        if context_scope.value == "Aktuelles Objekt" and not current_object_id:
                            ui.notify("Es ist kein aktuelles Objekt ausgewählt.", type="warning")
                            return
                        if context_scope.value == "Ausgewählte Dokumente" and not selected_documents.value:
                            ui.notify("Wähle mindestens ein Dokument als Kontext aus.", type="warning")
                            return
                        running["value"] = True
                        busy_indicator.set_visibility(True)
                        send_button.set_enabled(False)
                        request_kind = classify_assistant_request(question, str(mode.value or "auto"))
                        selected_document_ids = list(selected_documents.value or [])
                        explicit_document_ids = (
                            selected_document_ids
                            if context_scope.value == "Ausgewählte Dokumente"
                            else []
                        )
                        current_document_id = ""
                        if context_scope.value == "Aktuelles Objekt" and selection["document_id"]:
                            current_document_id = selection["document_id"]
                        elif context_scope.value == "Aktuelles Objekt" and selected_requirement():
                            current_document_id = selected_requirement().source_document_id or ""
                        elif context_scope.value == "Aktuelles Objekt" and selected_component():
                            current_document_id = selected_component().source_document_id or ""
                        elif context_scope.value == "Aktuelles Objekt" and selected_interface():
                            current_document_id = selected_interface().source_document_id or ""
                        elif context_scope.value == "Aktuelle Ansicht" and filters["section"] == "documents":
                            current_document_id = selection["document_id"] or ""
                        context_document_ids = resolve_assistant_document_ids(
                            question,
                            [
                                {
                                    "id": item.id,
                                    "name": item.name,
                                    "file_name": item.file_name,
                                    "profile": str(item.properties.get("analysisProfile") or "requirements"),
                                    "context_available": str(document_context_available(item)).lower(),
                                }
                                for item in package().source_documents
                            ],
                            explicit_document_ids,
                            current_document_id,
                            context_scope.value == "Gesamtes Projekt"
                            or request_kind == AssistantRequestKind.ARCHITECTURE,
                            request_kind == AssistantRequestKind.INTEGRATE,
                        )
                        document_names = [
                            item.name for item in package().source_documents
                            if item.id in set(context_document_ids)
                        ]
                        scoped_prompt = (
                            f"Kontext: {context_scope.value}"
                            + (f" ({', '.join(document_names)})" if document_names else "")
                            + f"\nNutzerfrage: {question}"
                        )
                        try:
                            set_job(
                                "KI analysiert", "Globaler Assistent",
                                f"{len(context_document_ids)} Dokumentkontext(e) · {question[:60]}"
                                if context_document_ids else question[:80],
                            )
                            document_context = await run.io_bound(
                                build_ai_document_context,
                                context_document_ids,
                                (
                                    context_scope.value in {"Ausgewählte Dokumente", "Aktuelles Objekt"}
                                    and request_kind != AssistantRequestKind.ARCHITECTURE
                                ),
                            )
                            if request_kind == AssistantRequestKind.INTEGRATE:
                                if not context_document_ids:
                                    raise ValueError(
                                        "Für diesen Integrationsauftrag wurde kein verwendbares Quelldokument gefunden."
                                    )
                                result = await run.io_bound(
                                    ai_provider.integrate_engineering_findings,
                                    package().model_copy(deep=True),
                                    scoped_prompt,
                                    document_context,
                                    architecture_catalog.ai_context(),
                                    builtins.ai_catalog_context(),
                                )
                                primary_document = next(
                                    item for item in package().source_documents
                                    if item.id == context_document_ids[0]
                                )
                                summary = add_document_analysis(
                                    package(),
                                    load_document_context(primary_document),
                                    result,
                                    ai_provider.display_name,
                                    ai_provider.model_name,
                                    scoped_prompt,
                                    DocumentAnalysisStage.TECHNICAL_DERIVATION,
                                )
                                latest = max(
                                    (
                                        item for item in package().document_analyses
                                        if item.document_id == summary.document_id
                                    ),
                                    key=lambda item: item.revision_number,
                                )
                                latest.properties["integrationSourceDocumentIds"] = context_document_ids
                                latest.properties["assistantIntegrationOrder"] = question
                                clear_selection()
                                selection["document_id"] = summary.document_id
                                selection["analysis_id"] = latest.id
                                filters["section"] = "documents"
                                if not save("KI-Integrationsvorschlag zur Prüfung gespeichert"):
                                    raise ValueError("KI-Vorschlag konnte nicht gespeichert werden")
                                preview=review_integration(latest.id)
                                store_ai_chat(prompt=question,answer="Der Integrationsvorschlag ist vorbereitet. Die ausgewählten Änderungen werden im Vorschaufenster geprüft und ausdrücklich übernommen.",provider=ai_provider.display_name,model=ai_provider.model_name,findings=[f"{len(preview.changes)} vorgeschlagene Änderungen"],recommendations=["Änderungen und Quellen im Vorschaufenster prüfen."],open_questions=list(latest.open_questions)+list(latest.conflicts))
                                set_job("Ready","KI-Integrationsvorschlag",f"{len(preview.changes)} Änderungen zur Prüfung")
                            elif request_kind == AssistantRequestKind.CHANGE:
                                result = await run.io_bound(
                                    ai_provider.propose_project_changes,
                                    package(), scoped_prompt, context_scope.value, current_object_id,
                                    document_context,
                                )
                                proposal = create_ai_change_proposal(
                                    package(), result, question, context_scope.value,
                                    ai_provider.display_name, ai_provider.model_name, current_object_id,
                                )
                                save(f"KI-Änderungsvorschlag „{proposal.title}“ gespeichert")
                                set_job("Ready", proposal.title, "Aktionen warten auf Einzelprüfung")
                            elif request_kind == AssistantRequestKind.ARCHITECTURE:
                                await generate_proposal(question, document_context)
                            else:
                                result = await run.io_bound(
                                    ai_provider.consult_project, package(), scoped_prompt, document_context, current_object_id if context_scope.value=="Aktuelles Objekt" else "",
                                )
                                store_ai_chat(
                                    prompt=question,
                                    answer=result.answer,
                                    provider=ai_provider.display_name,
                                    model=ai_provider.model_name,
                                    findings=list(result.findings),
                                    recommendations=list(result.recommendations),
                                    open_questions=list(result.open_questions),
                                )
                                set_job("Ready", result.title, "Antwort bereit")
                            prompt.value = ""
                            prompt.update()
                        except Exception as error:
                            set_job("Failed", "Globaler Assistent", str(error))
                            ui.notify(str(error), type="negative", close_button=True)
                        finally:
                            running["value"] = False
                            busy_indicator.set_visibility(False)
                            send_button.set_enabled(True)
                            assistant_history.refresh()
                            await asyncio.sleep(0.15)
                            chat_scroll.scroll_to(percent=1)

                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label(
                            "Automatisch erkennt Fragen und Aufträge. Änderungen werden erst nach Einzelprüfung und "
                            "automatischer Sicherungsrevision angewendet."
                        ).classes("text-xs text-slate-500")
                        send_button = ui.button("Senden", icon="send", on_click=run_prompt).props("no-caps id=isd-chat-submit")
                    ui.label("Enter: Senden · Umschalt + Enter: neue Zeile").classes("text-xs text-slate-500")
        dialog.open()
        ui.run_javascript("""(() => {
          const attach = (tries = 0) => {
            const area = document.querySelector('#isd-chat-prompt textarea');
            const button = document.querySelector('#isd-chat-submit');
            if (!area || !button) {
              if (tries < 25) setTimeout(() => attach(tries + 1), 100);
              return;
            }
            if (area.dataset.isdEnterHandler) return;
            area.dataset.isdEnterHandler = '1';
            area.addEventListener('keydown', event => {
              if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
                event.preventDefault();
                button.click();
              }
            });
          };
          attach();
        })()""")


    return AssistantUiViews(
        open_ai_assistant=open_ai_assistant,
    )
