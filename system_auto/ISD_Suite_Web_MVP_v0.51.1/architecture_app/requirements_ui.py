from __future__ import annotations
from .help_ui import HelpContext
from .requirements_presentation import format_assistant_entry_for_copy
from .requirements_presentation import COMPONENT_LIFECYCLE_LABELS as COMPONENT_LIFECYCLE_LABELS, SOURCE_ACCESS_LABELS as SOURCE_ACCESS_LABELS, SPECIFICATION_LEVEL_LABELS as SPECIFICATION_LEVEL_LABELS, REQUIREMENT_LEVEL_LABELS as REQUIREMENT_LEVEL_LABELS, SOLUTION_BINDING_LABELS as SOLUTION_BINDING_LABELS, SOURCE_KIND_LABELS as SOURCE_KIND_LABELS, COVERAGE_LABELS as COVERAGE_LABELS, VERIFICATION_STATE_LABELS as VERIFICATION_STATE_LABELS, CONFLICT_STATUS_LABELS as CONFLICT_STATUS_LABELS


from dataclasses import dataclass
import json
from typing import Any, Callable
from urllib.parse import urlparse, parse_qs

from nicegui import run, ui

from .analysis_queue import DocumentAnalysisQueue
from .ai_provider import OpenAIRequirementProvider
from .architecture_catalog import ArchitectureCatalog
from .attachment_store import attachment_is_available, delete_attachment, read_attachment
from .bus_content import BusContentTemplates
from .identity import show_sha_identity
from .models import ArchitecturePackage, AIReviewStatus, CandidateReviewStatus, ComponentRepresentation, ConnectionType, DocumentAnalysisStage, DesignMaturity, DesignComponent, EcadRequirement, EngineeringConflictStatus, InterfaceClass, InterfaceRequirement, ProposalStatus, RequirementClassification, RequirementEcadRelevance, RequirementCoverageStatus, RequirementLevel, RequirementLink, RequirementMaturity, RequirementSolutionBinding, RequirementVerificationState, RequirementRelation, RequirementTargetType, RealizationProvenance, SignalType, SourceDocument, StandardApplicability, StandardReference, TechnicalSourceAccess, TechnicalSourceOwner, TechnicalRealization, TechnicalRealizationStatus, TestDefinitionStatus, TestExecutionStatus, RequirementStandardLink, VerificationCase, VerificationMethod, utc_now
from .traceability import evidence_status, project_objects, test_has_evidence, trace_path
from .requirements_service import add_document_analysis, compile_architecture_proposal, compile_detected_document_analysis, create_architecture_proposal, delete_interface_requirement, delete_standard, delete_verification_case, interface_catalog_names, next_verification_identifier, requirement_traceability_status, requirement_traceability_index, defined_test_requirement_ids, is_test_defined, synchronize_verification_status
from .requirements_layers import LAYERS, build_layer_view, build_solution_graph, derivation_edges, effective_layer






















@dataclass
class RequirementsViews:
    navigator: Callable[[str], None]
    overview_workspace: Callable[[], None]
    documents_workspace: Callable[[], None]
    requirements_workspace: Callable[[], None]
    standards_workspace: Callable[[], None]
    inspector: Callable[[], None]
    refresh: Callable[..., None]
    reset: Callable[[], None]
    select_requirement: Callable[[str], None]
    select_realization: Callable[[str], None]
    edit_realization: Callable[..., None]
    create_requirement_for_target: Callable[..., None]
    open_ai_assistant: Callable[[], None]
    job_status: Callable[..., None]
    record_navigation: Callable[[], None]
    component_details: Callable[..., None]
    edit_function_element: Callable[..., None]
    select_architecture: Callable[..., None]
    edit_component: Callable[..., None]
    help_context: Callable[..., Any]


def create_requirements_views(
    page_state: Any,
    save: Callable[[str], bool],
    save_metadata: Callable[[str], bool] | None,
    switch_to_architecture: Callable[[], None],
    switch_workspace: Callable[[str], None],
    builtins: BusContentTemplates,
    architecture_catalog: ArchitectureCatalog,
    ai_provider: OpenAIRequirementProvider,
    configure_ai: Callable[..., None],
    create_safety_revision: Callable[[str], bool],
    load_ai_chat: Callable[[], list[Any]],
    store_ai_chat: Callable[..., Any],
    update_ai_chat: Callable[[int, str, str | None], None],
    open_help: Callable[[str], None],
    analysis_queue: DocumentAnalysisQueue,
    switch_project: Callable[[str], None] | None = None,
    edit_all_fields: Callable[[str], None] | None = None,
    open_system_element: Callable[[str], None] | None = None,
) -> RequirementsViews:
    save_architecture = save
    save = save_metadata or save
    selection: dict[str, str | None] = {
        "requirement_id": None,
        "relation_id": None,
        "component_id": None,
        "document_id": None,
        "analysis_id": None,
        "standard_id": None,
        "verification_id": None,
        "interface_id": None,
        "realization_id": None,
        "mechanical_component_id": None,
        "software_component_id": None,
        "ai_review_id": None,
        "architecture_id": None,
    }
    filters: dict[str, str] = {
        "query": "",
        "classification": "All",
        "requirement_level": "All",
        "v_focus": "",
        "v_scope": "__auto__",
        "specification_level": "All",
        "category": "All",
        "coverage": "All",
        "allocation": "All",
        "standards": "All",
        "maturity": "All",
        "priority": "All",
        "relevance": "All",
        "document": "All",
        "sort": "ID",
        "page": "1",
        "section": "system",
        "workflow_path": "all",
        "signal_query": "",
        "signal_type": "All",
        "solution_query": "",
    }
    class NavigationFilters(dict):
        callback: Callable[[], None] | None = None
        def update(self, *args: Any, **kwargs: Any) -> None:
            before = dict(self)
            super().update(*args, **kwargs)
            if self != before and self.callback:
                self.callback()
        def __setitem__(self, key: str, value: str) -> None:
            changed = self.get(key) != value
            super().__setitem__(key, value)
            if changed and self.callback:
                self.callback()
    filters = NavigationFilters(filters)
    import_jobs: dict[str, dict[str, Any]] = {}
    import_batch: dict[str, Any] = {
        "common_guidance": "",
        "use_ai": ai_provider.is_ready,
        "running": False,
        "total": 0,
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "current_index": 0,
        "current_name": "",
        "project_changed": False,
    }
    ai_job: dict[str, str] = {"status": "Idle", "label": "", "detail": ""}

    @ui.refreshable
    def job_status(compact: bool = False) -> None:
        active_document_job = analysis_queue.repository.active_ai_document_job(
            package().project.id
        )
        visible_status = ai_job["status"]
        visible_label = ai_job["label"]
        visible_detail = ai_job["detail"]
        if active_document_job is not None:
            visible_status = "KI analysiert" if active_document_job.status == "Running" else "KI wartet"
            visible_label = active_document_job.file_name
            visible_detail = active_document_job.detail
        full_status = " · ".join(
            item for item in [visible_status, visible_label, visible_detail] if item
        )
        if compact:
            if visible_status == "Idle":
                return
            status_classes = "bg-green-100 text-green-900" if visible_status == "Ready" else (
                "bg-red-100 text-red-900" if visible_status == "Failed"
                else "bg-blue-100 text-blue-900"
            )
            label = "KI bereit" if visible_status == "Ready" else (
                "KI-Fehler" if visible_status == "Failed" else "KI läuft"
            )
            with ui.row().classes(
                f"items-center gap-1 no-wrap shrink-0 rounded-full px-2 py-1 max-w-[112px] overflow-hidden {status_classes}"
            ) as compact_status:
                if visible_status not in {"Ready", "Failed"}:
                    ui.spinner(size="15px", color="primary")
                ui.label(label).classes("text-xs font-semibold whitespace-nowrap")
            if full_status:
                compact_status.tooltip(full_status)
            return
        if visible_status in {"Idle", "Ready"}:
            if visible_status == "Ready" and visible_label:
                ui.badge(f"KI bereit · {visible_label}", color="green-2").props("text-color=green-9")
            return
        if visible_status == "Failed":
            ui.badge(f"KI-Fehler · {visible_label}", color="red-2").props("text-color=red-9")
            return
        with ui.row().classes("items-center gap-2 rounded-full bg-blue-50 border border-blue-200 px-3 py-1"):
            ui.spinner(size="18px", color="primary")
            ui.label(f"{visible_status} · {visible_label}").classes("text-xs font-semibold text-blue-900")
            if visible_detail:
                ui.label(visible_detail).classes("text-xs text-blue-700")

    ui.timer(1.0, job_status.refresh)

    def set_job(status: str, label: str = "", detail: str = "") -> None:
        ai_job.update(status=status, label=label, detail=detail)
        job_status.refresh()

    def package() -> ArchitecturePackage:
        return page_state.package

    def selected_requirement() -> EcadRequirement | None:
        return package().find_requirement(selection["requirement_id"] or "")

    def selected_component() -> DesignComponent | None:
        return package().find_component(selection["component_id"] or "")

    def selected_standard() -> StandardReference | None:
        return package().find_standard(selection["standard_id"] or "")

    def selected_verification() -> VerificationCase | None:
        return package().find_verification_case(selection["verification_id"] or "")

    def selected_interface() -> InterfaceRequirement | None:
        return next(
            (item for item in package().interface_requirements if item.id == selection["interface_id"]),
            None,
        )

    def selected_realization() -> TechnicalRealization | None:
        return package().find_technical_realization(selection["realization_id"] or "")

    def selected_mechanical_component():
        return package().find_mechanical_component(selection["mechanical_component_id"] or "")

    def selected_software_component():
        return package().find_software_component(selection["software_component_id"] or "")





    def clear_selection() -> None:
        for key in selection:
            selection[key] = None

    restoring_navigation = False

    def remember_navigation() -> None:
        if restoring_navigation:
            return
        payload = json.dumps({"project": package().project.id, "tab": page_state.workspace_tab,
            "focus": selection["requirement_id"], "detail": selection["relation_id"],
            "selection": selection, "filters": filters}, ensure_ascii=False)
        ui.run_javascript("{const v=" + json.dumps(payload) + ";clearTimeout(window.__isdNavTimer);"
            "window.__isdNavTimer=setTimeout(()=>{const u=new URL(location.href);"
            "if(u.searchParams.get('isd')===v)return;u.searchParams.set('isd',v);"
            "history.pushState({},'',u)},60)}")

    def restore_navigation(event: Any) -> None:
        nonlocal restoring_navigation
        try:
            query = str(event.args or "")
            encoded = parse_qs(query.lstrip("?")).get("isd", [""])[0]
            data = json.loads(encoded) if encoded else {}
            restoring_navigation = True
            if data.get("project") != package().project.id:
                if switch_project is None or not data.get("project"):
                    return
                switch_project(str(data["project"]))
            if data.get("tab") and data["tab"] != page_state.workspace_tab:
                switch_workspace(str(data["tab"]))
            valid = {item.id for item in package().requirements}
            clear_selection()
            if data.get("focus") in valid:
                selection["requirement_id"] = data["focus"]
            object_types = {"component_id": "Component", "realization_id": "Realization",
                            "mechanical_component_id": "MechanicalComponent",
                            "software_component_id": "SoftwareComponent",
                            "standard_id": "Standard", "verification_id": "VerificationCase",
                            "document_id": "SourceDocument", "interface_id": "InterfaceRequirement"}
            known_objects = project_objects(package())
            saved_selection = data.get("selection") or {}
            for key, kind in object_types.items():
                identifier = saved_selection.get(key)
                if identifier in known_objects.get(kind, {}):
                    selection[key] = identifier
            relation_ids = {rel.id for rel in package().model_relations}
            if data.get("detail") in relation_ids:
                selection["relation_id"] = data["detail"]
            filters.update({key: value for key, value in data.get("filters", {}).items()
                            if key in filters and isinstance(value, str)})
            requirements_workspace.refresh(); inspector.refresh()
        except (ValueError, TypeError, AttributeError):
            return
        finally:
            restoring_navigation = False

    ui.on("isd-nav-restore", restore_navigation)
    filters.callback = remember_navigation
    def edge_event(event: Any) -> None:
        identifier = str(event.args or "")
        if any(rel.id == identifier for rel in package().model_relations):
            view_relation(identifier)
    ui.on("isd-edge-view", edge_event)
    ui.add_body_html("<script>window.addEventListener('popstate',()=>emitEvent('isd-nav-restore',location.search));"
                     "window.addEventListener('load',()=>setTimeout(()=>emitEvent('isd-nav-restore',location.search),800));</script>")

    def select_requirement(requirement_id: str) -> None:
        clear_selection(); selection["requirement_id"] = requirement_id
        if filters.get('display_mode')=='chain':filters.update(graph_focus='req:'+requirement_id,v_focus='')
        remember_navigation()
        contextual_navigator.refresh("requirements"); requirements_workspace.refresh(); inspector.refresh()

    def view_relation(relation_id: str) -> None:
        # Reading an edge does not change the selected graph object.
        selection["relation_id"] = relation_id
        remember_navigation()
        inspector.refresh()




    def select_component(component_id: str) -> None:
        clear_selection(); selection["component_id"] = component_id
        remember_navigation()
        requirements_workspace.refresh(); inspector.refresh()

    def select_mechanical_component(component_id: str) -> None:
        clear_selection(); selection["mechanical_component_id"] = component_id
        remember_navigation()
        requirements_workspace.refresh(); inspector.refresh()

    def select_software_component(component_id: str) -> None:
        clear_selection(); selection["software_component_id"] = component_id
        remember_navigation()
        requirements_workspace.refresh(); inspector.refresh()

    def select_document(document_id: str) -> None:
        clear_selection(); selection["document_id"] = document_id
        filters["section"] = "documents"
        contextual_navigator.refresh("documents"); documents_workspace.refresh(); inspector.refresh()

    def select_standard(standard_id: str) -> None:
        clear_selection(); selection["standard_id"] = standard_id
        remember_navigation()
        contextual_navigator.refresh("standards"); standards_workspace.refresh(); inspector.refresh()

    def select_verification(verification_id: str) -> None:
        clear_selection(); selection["verification_id"] = verification_id
        remember_navigation()
        requirements_workspace.refresh(); inspector.refresh()

    def select_interface(interface_id: str) -> None:
        clear_selection(); selection["interface_id"] = interface_id
        filters["section"] = "interfaces"
        requirements_workspace.refresh(); inspector.refresh()

    def select_realization(realization_id: str) -> None:
        clear_selection(); selection["realization_id"] = realization_id
        filters["section"] = "realizations"
        requirements_workspace.refresh(); inspector.refresh()

    def reset() -> None:
        clear_selection()
        filters.update(
            query="",
            classification="All",
            requirement_level="All",
            v_focus="",
            v_scope="__auto__",
            specification_level="All",
            category="All",
            coverage="All",
            allocation="All",
            standards="All",
            maturity="All",
            priority="All",
            relevance="All",
            document="All",
            sort="ID",
            page="1",
            section="workflow",
            workflow_path="all",
            signal_query="",
            signal_type="All",
        )







    def review_integration(analysis_id):
        from .reviewed_delta import integration_preview,apply_integration_preview
        from .annotation_review import open_annotation_review
        preview=integration_preview(package(),analysis_id,builtins)
        def accept_delta(resolved,indices):
            if not create_safety_revision('Vor Übernahme des KI-Integrationsvorschlags'):return False
            previous=page_state.package
            page_state.package=apply_integration_preview(package(),resolved)
            if save('Geprüfte KI-Änderungen übernommen'):return True
            page_state.package=previous;return False
        open_annotation_review(package(),preview,accept_delta,title='KI-Integration · Änderungen prüfen')
        return preview

    def select_architecture(identifier):
        if package().find_interface_requirement(identifier):
            select_interface(identifier);return
        clear_selection();selection['architecture_id']=identifier
        refresh();switch_workspace('requirements')




    def interface_requirement_dialog(interface: InterfaceRequirement | None = None) -> None:
        current = interface or InterfaceRequirement(name="")
        requirement_options = {
            item.id: f"{item.identifier or item.id[:12]} · {item.title}"
            for item in package().requirements
        }
        component_options = {
            item.id: item.name for item in package().components
        }
        standard_options = {
            item.id: f"{item.designation} · {item.title}" if item.title else item.designation
            for item in package().standards
        }
        layer_options = {
            item.id: f"{item.interface_class.value} · {item.name}"
            for item in package().interface_requirements if item.id != current.id
        }
        with ui.dialog() as dialog, ui.card().classes("w-[900px] max-w-[97vw] p-6 gap-4"):
            ui.label(
                "Interface-Prototyp bearbeiten" if interface else "Interface-Prototyp hinzufügen"
            ).classes("text-xl font-bold")
            ui.label(
                "Das frühe Interface ist noch nicht an konkrete Architecture Elements gebunden und kann sowohl aus Requirements als auch aus einer Komponentenentscheidung entstehen."
            ).classes("text-sm text-slate-600")
            with ui.row().classes("w-full gap-3"):
                name = ui.input("Name", value=current.name, placeholder="z. B. Service Ethernet").classes("grow")
                interface_class = ui.select(
                    {item.value: item.value for item in InterfaceClass},
                    value=current.interface_class.value,
                    label="Schnittstellenklasse",
                ).classes("w-40")
                family = ui.input("Familie", value=current.family).classes("grow")
                protocol = ui.input("Protokoll", value=current.protocol).classes("grow")
            with ui.row().classes("w-full gap-3"):
                port_type = ui.input("Port Type", value=current.port_type).classes("grow")
                signal_type = ui.select(
                    [item.value for item in SignalType], value=current.signal_type.value,
                    label="Signaltyp",
                ).classes("grow")
                connection_type = ui.select(
                    [item.value for item in ConnectionType], value=current.connection_type.value,
                    label="Verbindungstyp",
                ).classes("grow")
                maturity = ui.select(
                    [item.value for item in RequirementMaturity], value=current.maturity.value,
                    label="Reifegrad",
                ).classes("grow")
            with ui.row().classes("w-full gap-3"):
                provider = ui.input("Provider / Quelle", value=current.provider or current.host_role).classes("grow")
                consumer = ui.input(
                    "Consumer / Teilnehmer", value=current.consumer or ", ".join(current.participant_roles),
                ).classes("grow")
            with ui.row().classes("w-full gap-3"):
                host_role = ui.input("Host-/Quellenrolle", value=current.host_role).classes("grow")
                participant_roles = ui.input(
                    "Teilnehmerrollen", value=", ".join(current.participant_roles),
                ).classes("grow")
                topology = ui.input("Topologie", value=current.topology).classes("grow")
            with ui.row().classes("w-full gap-3"):
                data_rate = ui.input("Datenrate", value=current.data_rate).classes("grow")
                voltage = ui.input("Spannung / Pegel", value=current.voltage).classes("grow")
                isolation = ui.input("Isolation", value=current.isolation).classes("grow")
                medium_connector = ui.input("Medium / Stecker", value=current.medium_connector).classes("grow")
            safety_redundancy = ui.input(
                "Safety / Redundanz", value=current.safety_redundancy,
            ).classes("w-full")
            with ui.row().classes("w-full gap-3"):
                physical_properties = ui.textarea(
                    "Physische Eigenschaften (Schlüssel: Wert)",
                    value="\n".join(f"{key}: {value}" for key, value in current.physical_properties.items()),
                ).props("outlined autogrow").classes("grow")
                protocol_properties = ui.textarea(
                    "Protokolleigenschaften (Schlüssel: Wert)",
                    value="\n".join(f"{key}: {value}" for key, value in current.protocol_properties.items()),
                ).props("outlined autogrow").classes("grow")
            linked_layer_ids = ui.select(
                layer_options,
                value=list(current.linked_layer_ids),
                label="Gekoppelte Schnittstellenlayer",
                multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            interface_template = ui.select(
                {name: name for name in interface_catalog_names(package(), builtins)},
                value=current.interface_template or None,
                label="Interface-/Signalvorlage",
                clearable=True,
            ).classes("w-full")
            requirement_ids = ui.select(
                requirement_options, value=list(current.requirement_ids),
                label="Begründende Requirements", multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            component_ids = ui.select(
                component_options, value=list(current.component_ids),
                label="Ableitende oder realisierende Komponenten", multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            standard_ids = ui.select(
                standard_options, value=list(current.standard_ids),
                label="Anwendbare Normen / Standards", multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            standards_required = ui.checkbox(
                "Normative Absicherung erforderlich",
                value=current.standards_required,
            )
            rationale = ui.textarea(
                "Begründung / Spezifikationsstand", value=current.rationale,
            ).props("outlined autogrow").classes("w-full")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply() -> None:
                    normalized_name = (name.value or "").strip()
                    if not normalized_name:
                        ui.notify("Der Interfacename ist erforderlich.", type="warning")
                        return
                    target = interface or InterfaceRequirement(name=normalized_name)
                    target.name = normalized_name
                    target.interface_class = InterfaceClass(interface_class.value)
                    target.family = (family.value or "Interface").strip()
                    target.protocol = (protocol.value or "").strip()
                    target.port_type = (port_type.value or "Generic Interface").strip()
                    target.signal_type = SignalType(signal_type.value)
                    target.connection_type = ConnectionType(connection_type.value)
                    target.maturity = RequirementMaturity(maturity.value)
                    target.host_role = (host_role.value or "").strip()
                    target.participant_roles = [
                        item.strip() for item in (participant_roles.value or "").split(",") if item.strip()
                    ]
                    target.topology = (topology.value or "Point-to-point").strip()
                    target.data_rate = (data_rate.value or "").strip()
                    target.voltage = (voltage.value or "").strip()
                    target.isolation = (isolation.value or "").strip()
                    target.safety_redundancy = (safety_redundancy.value or "").strip()
                    target.medium_connector = (medium_connector.value or "").strip()
                    target.provider = (provider.value or "").strip()
                    target.consumer = (consumer.value or "").strip()
                    def parse_properties(raw: str) -> dict[str, str] | None:
                        result: dict[str, str] = {}
                        for line in raw.splitlines():
                            if not line.strip():
                                continue
                            key, separator, value = line.partition(":")
                            if not separator or not key.strip() or not value.strip():
                                ui.notify(f"Ungültige Eigenschaftszeile: {line}", type="warning")
                                return None
                            result[key.strip()] = value.strip()
                        return result
                    parsed_physical = parse_properties(physical_properties.value or "")
                    parsed_protocol = parse_properties(protocol_properties.value or "")
                    if parsed_physical is None or parsed_protocol is None:
                        return
                    target.physical_properties = parsed_physical
                    target.protocol_properties = parsed_protocol
                    target.linked_layer_ids = list(linked_layer_ids.value or [])
                    target.interface_template = interface_template.value or ""
                    target.requirement_ids = list(requirement_ids.value or [])
                    target.component_ids = list(component_ids.value or [])
                    target.standard_ids = list(standard_ids.value or [])
                    target.standards_required = bool(standards_required.value)
                    target.rationale = rationale.value or ""
                    if interface is None:
                        package().interface_requirements.append(target)
                    package().requirement_links = [
                        item for item in package().requirement_links
                        if not (
                            item.target_type == RequirementTargetType.INTERFACE
                            and item.target_id == target.id
                        )
                    ]
                    package().requirement_links.extend(
                        RequirementLink(
                            requirement_id=requirement_id,
                            target_type=RequirementTargetType.INTERFACE,
                            target_id=target.id,
                            relation=RequirementRelation.DEFINES_INTERFACE,
                        )
                        for requirement_id in dict.fromkeys(target.requirement_ids)
                    )
                    for component_item in package().components:
                        component_item.interface_requirement_ids = [
                            value for value in component_item.interface_requirement_ids if value != target.id
                        ]
                    for component_id in target.component_ids:
                        linked_component = package().find_component(component_id)
                        if linked_component and target.id not in linked_component.interface_requirement_ids:
                            linked_component.interface_requirement_ids.append(target.id)
                    clear_selection(); selection["interface_id"] = target.id
                    dialog.close(); save("Interface-Prototyp gespeichert")

                ui.button("Speichern", icon="save", on_click=apply).props("no-caps")
        dialog.open()

    def standard_dialog(standard: StandardReference | None = None) -> None:
        current = standard or StandardReference(designation="")
        with ui.dialog() as dialog, ui.card().classes("w-[720px] max-w-[96vw] p-6 gap-4"):
            ui.label("Norm oder Standard bearbeiten" if standard else "Norm oder Standard hinzufügen").classes("text-xl font-bold")
            with ui.row().classes("w-full gap-3"):
                designation = ui.input("Bezeichnung", value=current.designation, placeholder="z. B. ISO 26262").classes("grow")
                organization = ui.input("Organisation", value=current.organization, placeholder="ISO, IEC, DIN, IPC …").classes("w-44")
                edition = ui.input("Ausgabe / Jahr", value=current.edition, placeholder="z. B. 2018").classes("w-36")
            title = ui.input("Titel", value=current.title, placeholder="Titel der Norm oder des Standards").classes("w-full")
            applicability = ui.select(
                [item.value for item in StandardApplicability],
                value=current.applicability.value,
                label="Geltungsstatus",
            ).classes("w-full")
            with ui.row().classes("w-full gap-3"):
                language = ui.input("Sprache", value=current.language, placeholder="z. B. DE / EN").classes("grow")
                publication_status = ui.input("Publikationsstatus", value=current.publication_status, placeholder="Aktuell / Ersetzt / Entwurf").classes("grow")
                effective_date = ui.input("Gültig seit", value=current.effective_date, placeholder="YYYY-MM-DD").classes("grow")
            with ui.row().classes("w-full gap-3"):
                external_identifier = ui.input("Externe ID / DOI", value=current.external_identifier).classes("grow")
                access_class = ui.select(
                    SOURCE_ACCESS_LABELS,
                    value=current.access_class.value,
                    label="Zugriffsklasse",
                ).classes("grow")
            description = ui.textarea("Anwendungsbereich / Begründung", value=current.description).classes("w-full").props("autogrow outlined")
            source_url = ui.input(
                "Primäre Referenz / URL",
                value=current.source_url,
                placeholder="Optional; weitere Kanäle und Dokumente werden nach dem Speichern an der Norm ergänzt",
            ).classes("w-full")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply() -> None:
                    value = (designation.value or "").strip()
                    normalized_source_url = (source_url.value or "").strip()
                    if not value:
                        ui.notify("Die Norm- oder Standardbezeichnung ist erforderlich.", type="warning")
                        return
                    if any(
                        item.id != current.id and item.designation.casefold() == value.casefold()
                        for item in package().standards
                    ):
                        ui.notify("Diese Norm oder dieser Standard ist bereits vorhanden.", type="warning")
                        return
                    if normalized_source_url:
                        parsed = urlparse(normalized_source_url)
                        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                            ui.notify("Die primäre URL muss mit http:// oder https:// beginnen.", type="warning")
                            return
                    target = standard or StandardReference(designation=value)
                    target.designation = value
                    target.organization = (organization.value or "").strip()
                    target.edition = (edition.value or "").strip()
                    target.title = (title.value or "").strip()
                    target.applicability = StandardApplicability(applicability.value)
                    target.language = (language.value or "").strip()
                    target.publication_status = (publication_status.value or "").strip()
                    target.effective_date = (effective_date.value or "").strip()
                    target.external_identifier = (external_identifier.value or "").strip()
                    target.access_class = TechnicalSourceAccess(access_class.value)
                    target.description = description.value or ""
                    target.source_url = normalized_source_url
                    if standard is None:
                        package().standards.append(target)
                    clear_selection(); selection["standard_id"] = target.id
                    dialog.close(); save("Norm oder Standard gespeichert")

                ui.button("Speichern", icon="save", on_click=apply).props("no-caps")
        dialog.open()






    def standard_link_dialog(
        requirement: EcadRequirement,
        link: RequirementStandardLink | None = None,
    ) -> None:
        if not package().standards:
            ui.notify("Lege zuerst im Reiter „Normen & Standards“ einen Eintrag an.", type="warning")
            return
        options = {
            item.id: f"{item.designation} · {item.title}" if item.title else item.designation
            for item in package().standards
        }
        with ui.dialog() as dialog, ui.card().classes("w-[620px] max-w-[95vw] p-6 gap-4"):
            ui.label("Normenbezug bearbeiten" if link else "Norm oder Standard zuordnen").classes("text-xl font-bold")
            ui.label(f"{requirement.identifier} · {requirement.title}").classes("text-sm font-medium")
            standard_id = ui.select(
                options,
                value=link.standard_id if link else next(iter(options)),
                label="Norm / Standard",
            ).classes("w-full")
            clause = ui.input("Abschnitt / Klausel", value=link.clause if link else "", placeholder="z. B. Part 5, 7.4.3").classes("w-full")
            rationale = ui.textarea("Relevanz / Begründung", value=link.rationale if link else "").classes("w-full").props("autogrow outlined")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply() -> None:
                    normalized_clause = (clause.value or "").strip()
                    if any(
                        item.id != (link.id if link else "")
                        and item.requirement_id == requirement.id
                        and item.standard_id == standard_id.value
                        and item.clause.casefold() == normalized_clause.casefold()
                        for item in package().requirement_standard_links
                    ):
                        ui.notify("Dieser Normenbezug ist bereits vorhanden.", type="warning")
                        return
                    target = link or RequirementStandardLink(
                        requirement_id=requirement.id,
                        standard_id=standard_id.value,
                    )
                    target.standard_id = standard_id.value
                    target.clause = normalized_clause
                    target.rationale = rationale.value or ""
                    if link is None:
                        package().requirement_standard_links.append(target)
                    dialog.close(); save("Normenbezug gespeichert")

                ui.button("Zuordnen", icon="link", on_click=apply).props("no-caps")
        dialog.open()

    def verification_dialog(
        verification: VerificationCase | None = None,
        initial_requirement_id: str | None = None,
    ) -> None:
        current = verification or VerificationCase(title="")
        requirement_options = {
            item.id: f"{item.identifier or item.id[:12]} · {item.title}"
            for item in package().requirements
        }
        initial_requirements = list(current.requirement_ids)
        if initial_requirement_id and initial_requirement_id not in initial_requirements:
            initial_requirements.append(initial_requirement_id)
        with ui.dialog() as dialog, ui.card().classes("w-[780px] max-w-[96vw] p-6 gap-4"):
            ui.label("Requirement-Testdefinition bearbeiten" if verification else "Requirement-Test definieren").classes("text-xl font-bold")
            ui.label(
                "Die Definition beantwortet: Wurde für das Requirement bereits ein vollständiger Test geschrieben? Die Ausführung wird getrennt geführt."
            ).classes("text-sm text-slate-600")
            with ui.row().classes("w-full gap-3"):
                ui.input(
                    "Verifikations-ID",
                    value=current.identifier or next_verification_identifier(package()),
                ).props("readonly outlined").classes("w-44")
                title = ui.input("Titel", value=current.title, placeholder="z. B. SPI-Kommunikation nachweisen").classes("grow")
            with ui.row().classes("w-full gap-3"):
                method = ui.select([item.value for item in VerificationMethod], value=current.method.value, label="Methode").classes("grow")
                definition_status = ui.select(
                    [item.value for item in TestDefinitionStatus],
                    value=current.definition_status.value,
                    label="Definitionsstatus",
                ).classes("grow")
                execution_status = ui.select(
                    [item.value for item in TestExecutionStatus],
                    value=current.execution_status.value,
                    label="Ausführungsstatus",
                ).classes("grow")
            requirement_ids = ui.select(
                requirement_options,
                value=initial_requirements,
                label="Abgedeckte Requirements",
                multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            objective = ui.textarea("Ziel / Nachweis", value=current.objective).classes("w-full").props("autogrow outlined")
            procedure = ui.textarea("Prüfverfahren / Ablauf", value=current.procedure).classes("w-full").props("autogrow outlined")
            expected_result = ui.textarea("Erwartetes Ergebnis / Akzeptanz", value=current.expected_result).classes("w-full").props("autogrow outlined")
            evidence = ui.input("Evidenz / Testreport", value=current.evidence_reference, placeholder="Datei, URL oder Report-ID").classes("w-full")
            actual_result = ui.textarea("Tatsächliches Ergebnis", value=current.actual_result).classes("w-full")
            verified_revision = ui.input("Geprüfte Revision", value=current.verified_revision).classes("w-full")
            configuration = ui.input("Konfiguration / Versuchsaufbau", value=current.configuration_reference).classes("w-full")
            confirm_current=ui.checkbox('Ergebnis gilt für den aktuellen Anforderungs- und Umsetzungsstand',value=False)
            ui.label('Nur bei bestätigter Gültigkeit wird der aktuelle Objektstand am Nachweis gespeichert. Alte Belege bleiben erhalten.').classes('text-xs text-slate-600')
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply() -> None:
                    if not (title.value or "").strip():
                        ui.notify("Der Titel des Verifikationsfalls ist erforderlich.", type="warning")
                        return
                    if not requirement_ids.value:
                        ui.notify("Mindestens ein Requirement muss abgedeckt werden.", type="warning")
                        return
                    selected_definition_status = TestDefinitionStatus(definition_status.value)
                    selected_execution_status = TestExecutionStatus(execution_status.value)
                    if selected_definition_status in {TestDefinitionStatus.DEFINED, TestDefinitionStatus.APPROVED} and (
                        not (objective.value or "").strip()
                        or not (procedure.value or "").strip()
                        or not (expected_result.value or "").strip()
                    ):
                        ui.notify("Ein definierter Test benötigt Ziel, Prüfverfahren und erwartetes Ergebnis.", type="warning")
                        return
                    if selected_execution_status != TestExecutionStatus.NOT_RUN and selected_definition_status != TestDefinitionStatus.APPROVED:
                        ui.notify("Ein Test kann erst nach freigegebener Definition ausgeführt werden.", type="warning")
                        return
                    if selected_execution_status in {TestExecutionStatus.PASSED, TestExecutionStatus.FAILED} and not (evidence.value or "").strip():
                        ui.notify("Für ein ausgeführtes Ergebnis ist eine Evidenz oder Report-ID erforderlich.", type="warning")
                        return
                    if selected_execution_status == TestExecutionStatus.PASSED and not (actual_result.value or "").strip():
                        ui.notify("Ein bestandener Test benötigt das tatsächliche Ergebnis.", type="warning"); return
                    if selected_execution_status == TestExecutionStatus.PASSED and not (verified_revision.value or "").strip():
                        ui.notify("Bitte geprüfte Revision oder Konfiguration angeben.", type="warning"); return
                    target = verification or VerificationCase(
                        identifier=next_verification_identifier(package()),
                        title=title.value.strip(),
                    )
                    target.title = title.value.strip()
                    target.method = VerificationMethod(method.value)
                    target.definition_status = selected_definition_status
                    target.execution_status = selected_execution_status
                    target.requirement_ids = list(requirement_ids.value or [])
                    target.objective = objective.value or ""
                    target.procedure = procedure.value or ""
                    target.expected_result = expected_result.value or ""
                    target.evidence_reference = (evidence.value or "").strip()
                    target.actual_result = actual_result.value or ""
                    target.verified_revision = verified_revision.value or ""
                    target.configuration_reference = configuration.value or ""
                    target.executed_at = utc_now() if selected_execution_status in {TestExecutionStatus.PASSED, TestExecutionStatus.FAILED} else None
                    synchronize_verification_status(target)
                    if selected_execution_status==TestExecutionStatus.PASSED and confirm_current.value:
                        from .traceability import record_verification
                        record_verification(package(),target)
                    if verification is None:
                        package().verification_cases.append(target)
                    package().requirement_links = [
                        item for item in package().requirement_links
                        if not (
                            item.target_type == RequirementTargetType.VERIFICATION_CASE
                            and item.target_id == target.id
                        )
                    ]
                    package().requirement_links.extend(
                        RequirementLink(
                            requirement_id=requirement_id,
                            target_type=RequirementTargetType.VERIFICATION_CASE,
                            target_id=target.id,
                            relation=RequirementRelation.VERIFIED_BY,
                        )
                        for requirement_id in dict.fromkeys(target.requirement_ids)
                    )
                    clear_selection(); selection["verification_id"] = target.id
                    dialog.close(); save("Requirement-Testdefinition gespeichert")

                ui.button("Speichern", icon="save", on_click=apply).props("no-caps")
        dialog.open()





    def confirm_standard_delete(standard: StandardReference) -> None:
        link_count = sum(item.standard_id == standard.id for item in package().requirement_standard_links)
        stored_paths = [
            item.attachment_path
            for item in owner_sources(TechnicalSourceOwner.STANDARD, standard.id)
            if item.attachment_path
        ]
        with ui.dialog() as dialog, ui.card().classes("w-[520px] p-6 gap-4"):
            ui.label("Norm oder Standard löschen?").classes("text-xl font-bold")
            ui.label(standard.designation).classes("font-medium")
            ui.label(
                f"Dabei werden {link_count} Requirement-Bezug/Bezüge sowie alle technischen Quellen "
                "und lokal hinterlegten Dokumente dieser Norm entfernt."
            ).classes("text-sm text-slate-600")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")
                def apply() -> None:
                    delete_standard(package(), standard.id)
                    reset()
                    if save("Norm oder Standard gelöscht"):
                        for stored_path in stored_paths:
                            try:
                                delete_attachment(package().project.id, stored_path)
                            except ValueError:
                                pass
                        dialog.close()
                ui.button("Löschen", icon="delete", on_click=apply).props("color=negative no-caps")
        dialog.open()

    def confirm_interface_delete(interface: InterfaceRequirement) -> None:
        stored_paths = [
            item.attachment_path
            for item in owner_sources(TechnicalSourceOwner.INTERFACE, interface.id)
            if item.attachment_path
        ]
        with ui.dialog() as dialog, ui.card().classes("w-[540px] max-w-[94vw] p-6 gap-4"):
            ui.label("Interface-Prototyp löschen?").classes("text-xl font-bold")
            ui.label(interface.name).classes("font-medium")
            ui.label(
                "Die Interface-Anforderung, ihre Komponentenbeziehungen und direkt zugeordneten technischen Quellen werden entfernt. Bereits erzeugte Architekturports und Signale bleiben bestehen."
            ).classes("text-sm text-slate-600")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply() -> None:
                    delete_interface_requirement(package(), interface.id)
                    reset()
                    if save("Interface-Prototyp gelöscht"):
                        for stored_path in stored_paths:
                            try:
                                delete_attachment(package().project.id, stored_path)
                            except ValueError:
                                pass
                        dialog.close()

                ui.button("Löschen", icon="delete", on_click=apply).props("color=negative no-caps")
        dialog.open()

    def confirm_verification_delete(verification: VerificationCase) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[520px] p-6 gap-4"):
            ui.label("Verifikationsfall löschen?").classes("text-xl font-bold")
            ui.label(f"{verification.identifier} · {verification.title}").classes("font-medium")
            ui.label("Die Requirements bleiben bestehen, verlieren jedoch diese Test- beziehungsweise Verifikationsabdeckung.").classes("text-sm text-slate-600")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")
                def apply() -> None:
                    delete_verification_case(package(), verification.id)
                    reset(); dialog.close(); save("Verifikationsfall gelöscht")
                ui.button("Löschen", icon="delete", on_click=apply).props("color=negative no-caps")
        dialog.open()



    def active_document_analysis(document_id: str):
        selected_analysis = package().find_document_analysis(selection["analysis_id"] or "")
        if selected_analysis and selected_analysis.document_id == document_id:
            return selected_analysis
        document = next((item for item in package().source_documents if item.id == document_id), None)
        if document and document.active_analysis_id:
            active = package().find_document_analysis(document.active_analysis_id)
            if active:
                return active
        analyses = [item for item in package().document_analyses if item.document_id == document_id]
        return max(analyses, key=lambda item: item.revision_number) if analyses else None

    def select_document_analysis(document_id: str, analysis_id: str) -> None:
        clear_selection()
        selection["document_id"] = document_id
        selection["analysis_id"] = analysis_id
        filters["section"] = "documents"
        documents_workspace.refresh(); inspector.refresh()

    def linked_document_requirements(document_id: str) -> list[EcadRequirement]:
        return [
            item for item in package().requirements
            if item.source_document_id == document_id
        ]

    def active_document_requirements(document_id: str) -> list[EcadRequirement]:
        return [
            item for item in linked_document_requirements(document_id)
            if item.maturity not in {
                RequirementMaturity.REJECTED,
                RequirementMaturity.OBSOLETE,
            }
            and item.ecad_relevance != RequirementEcadRelevance.BACKLOG_ONLY
        ]



    def technical_derivation_dialog(
        document: SourceDocument,
        initial_requirement_id: str | None = None,
    ) -> None:
        active_requirements = active_document_requirements(document.id)
        if not ai_provider.is_ready:
            ui.notify("Für die technische Ableitung muss die KI für diese Sitzung konfiguriert sein.", type="warning")
            configure_ai(lambda: requirements_workspace.refresh())
            return
        if not active_requirements:
            ui.notify(
                "Für dieses Dokument ist kein aktives, technisch relevantes Requirement vorhanden.",
                type="warning",
                close_button=True,
            )
            return
        if not document_context_available(document):
            ui.notify("Der gespeicherte Dokumentkontext ist nicht verfügbar.", type="negative")
            return
        options = {
            item.id: f"{item.identifier} · {item.title} [{item.maturity.value}]"
            for item in active_requirements
        }
        with ui.dialog() as dialog, ui.card().classes("w-[820px] max-w-[96vw] p-6 gap-4"):
            ui.label("Technische Ableitung starten").classes("text-xl font-bold")
            ui.label(document.name).classes("font-semibold")
            ui.label(
                "Die technische Ableitung verwendet den bereits gespeicherten Dokumentkontext und ausgewählte "
                "aktive Requirements. Der Prüfstatus ist kein technisches Start-Gate: Entwürfe bleiben klar als "
                "vorläufig gekennzeichnet. Das Dokument wird nicht erneut extrahiert."
            ).classes("text-sm text-blue-900 bg-blue-50 border border-blue-200 rounded-lg p-3")
            requirement_ids = ui.select(
                options=options,
                value=(
                    [initial_requirement_id]
                    if initial_requirement_id in options
                    else list(options)
                ),
                label="Aktive Requirements",
                multiple=True,
            ).props("outlined use-chips options-dense").classes("w-full")
            guidance = ui.textarea(
                "Technischer Fokus (optional)",
                placeholder=(
                    "Zum Beispiel: Bevorzuge galvanische Trennung, leite A-/B-Komponenten, "
                    "Interfaces, Normlücken und Requirement-Tests ab."
                ),
            ).props("outlined autogrow").classes("w-full")
            ui.label(
                "Ergebnis: vorgeschlagene Lösungen, Parts, Interfaces, Normen und Tests werden direkt "
                "mit den ausgewählten Requirements verknüpft und behalten einen sichtbaren Prüfstatus."
            ).classes("text-xs text-slate-500")

            async def derive() -> None:
                selected_ids = list(requirement_ids.value or [])
                if not selected_ids:
                    ui.notify("Wähle mindestens ein aktives Requirement aus.", type="warning")
                    return
                if not create_safety_revision(
                    f"Vor technischer KI-Ableitung für {document.name}"
                ):
                    return
                dialog.close()
                try:
                    set_job(
                        "KI leitet technisch ab",
                        document.name,
                        "A-/B-Komponenten, Interfaces, Normen und Testdefinitionen",
                    )
                    context = await run.io_bound(build_ai_document_context, [document.id], True)
                    result = await run.io_bound(
                        ai_provider.derive_technical_solution,
                        package().model_copy(deep=True),
                        selected_ids,
                        (guidance.value or "").strip(),
                        context,
                    )
                    add_document_analysis(
                        package(),
                        load_document_context(document),
                        result,
                        ai_provider.display_name,
                        ai_provider.model_name,
                        (guidance.value or "").strip(),
                        DocumentAnalysisStage.TECHNICAL_DERIVATION,
                    )
                    latest = max(
                        (item for item in package().document_analyses if item.document_id == document.id),
                        key=lambda item: item.revision_number,
                    )
                    compiled = compile_detected_document_analysis(package(), latest.id, builtins)
                    clear_selection()
                    selection["document_id"] = document.id
                    selection["analysis_id"] = latest.id
                    if not save(
                        f"Technische Ableitung für „{document.name}“ zur Prüfung bereit"
                    ):
                        raise RuntimeError("Die technische Ableitung konnte nicht gespeichert werden.")
                    set_job(
                        "Ready",
                        document.name,
                        f"{compiled.realization_count} Realisierungen · {compiled.component_count} Komponenten · "
                        f"{compiled.interface_count} Interfaces · {compiled.verification_count} Tests",
                    )
                    ui.notify("Technische Ableitung wurde mit den Requirements verknüpft.", type="positive")
                except Exception as error:
                    set_job("Failed", document.name, str(error))
                    ui.notify(f"Technische Ableitung fehlgeschlagen: {error}", type="negative", close_button=True)

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")
                ui.button("Ableitung starten", icon="engineering", on_click=derive).props("no-caps")
        dialog.open()

    async def generate_proposal(
        guidance: str = "",
        document_context: list[dict[str, object]] | None = None,
        requirement_ids: list[str] | None = None,
        target_views: list[str] | None = None,
    ) -> bool:
        if not ai_provider.is_ready:
            ui.notify("Für einen intelligenten Architekturvorschlag ist ein KI-Provider zu konfigurieren.", type="warning")
            return False
        try:
            from .architecture_scope import selected_requirements,proposal_basis,validate_result_scope
            snapshot=package().model_copy(deep=True)
            basis=proposal_basis(snapshot)
            if requirement_ids is not None:selected_requirements(snapshot,requirement_ids)
            set_job(
                "KI analysiert",
                "Architekturvorschlag",
                "Aktive ECAD-relevante Anforderungen · vorläufiger Arbeitsstand",
            )
            result = await run.io_bound(
                ai_provider.synthesize_architecture,
                snapshot,
                interface_catalog_names(package(), builtins),
                guidance,
                document_context,
                architecture_catalog.ai_context(),
                builtins.ai_catalog_context(),
                **({'requirement_ids':requirement_ids,'target_views':target_views} if requirement_ids is not None else {}),
            )
            if requirement_ids is not None:
                if proposal_basis(package())!=basis:raise ValueError('Projektstand während KI-Anfrage geändert; Vorschlag neu erzeugen.')
                validate_result_scope(result,requirement_ids,target_views or [])
            proposal = create_architecture_proposal(
                package(),
                result,
                ai_provider.display_name,
                ai_provider.model_name,
                guidance,
            )
            proposal.attributes["createdFrom"] = "AI Assistant Work Order"
            proposal.properties["designState"] = "Working"
            proposal.properties["sourceDocumentIds"] = [
                str(item.get("documentId", ""))
                for item in (document_context or [])
                if item.get("documentId")
            ]
            if requirement_ids is not None:
                proposal.properties['confirmedScope']={'requirementIds':requirement_ids,'targetViews':target_views,'basis':basis}
            clear_selection()
            filters["section"] = "proposals"
            if save(f"Architekturvorschlag „{proposal.name}“ gespeichert") is False:
                return False
            set_job("Ready", proposal.name, "Architekturvorschlag bereit zur Prüfung")
            return True
        except Exception as error:
            set_job("Failed", "Architekturvorschlag", str(error))
            ui.notify(f"Architekturvorschlag fehlgeschlagen: {error}", type="negative", close_button=True)
            return False


    def set_ai_review_status(review_id: str, status: AIReviewStatus) -> None:
        review = package().find_ai_review(review_id)
        if review is None:
            return
        review.status = status
        review.reviewed_at = utc_now()
        save(
            "KI-Analyse als Review-Notiz akzeptiert"
            if status == AIReviewStatus.ACCEPTED
            else "KI-Analyse verworfen"
            if status == AIReviewStatus.REJECTED
            else "KI-Analyse wieder geöffnet"
        )

    def reject_ai_review_dialog(review_id: str) -> None:
        review = package().find_ai_review(review_id)
        if review is None:
            return
        with ui.dialog() as dialog, ui.card().classes("w-[560px] max-w-[94vw] p-6 gap-4"):
            ui.label("KI-Analyse verwerfen?").classes("text-xl font-bold")
            ui.label(review.title).classes("font-medium")
            feedback = ui.textarea(
                "Begründung / Feedback (empfohlen)",
                value=review.review_comment,
                placeholder="Zum Beispiel: Annahme zur Diagnose ist fachlich nicht belegt.",
            ).props("outlined autogrow").classes("w-full")
            ui.label(
                "Das Feedback bleibt im SPOT-JSON erhalten und wird bei einer späteren Projektanalyse nachvollziehbar."
            ).classes("text-sm text-slate-600")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")
                def reject() -> None:
                    review.review_comment = (feedback.value or "").strip()
                    review.status = AIReviewStatus.REJECTED
                    review.reviewed_at = utc_now()
                    dialog.close()
                    save("KI-Analyse verworfen")
                ui.button("Analyse verwerfen", icon="block", on_click=reject).props("color=negative no-caps")
        dialog.open()

    def reject_proposal_dialog(proposal_id: str) -> None:
        proposal = package().find_architecture_proposal(proposal_id)
        if proposal is None:
            return
        with ui.dialog() as dialog, ui.card().classes("w-[520px] p-6 gap-4"):
            ui.label("Architekturvorschlag verwerfen?").classes("text-xl font-bold")
            ui.label(proposal.name).classes("font-medium")
            ui.label(
                "Der Vorschlag bleibt zur Nachvollziehbarkeit im SPOT-JSON erhalten, wird aber nicht in die "
                "Architektur übernommen."
            ).classes("text-sm text-slate-600")
            feedback = ui.textarea(
                "Begründung / Feedback (empfohlen)",
                value=proposal.review_comment,
                placeholder="Zum Beispiel: Domain-Zuschnitt ist zu fein; Versorgung als eigene Domain bündeln.",
            ).props("outlined autogrow").classes("w-full")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")
                def reject() -> None:
                    proposal.review_comment = (feedback.value or "").strip()
                    proposal.status = ProposalStatus.REJECTED
                    proposal.reviewed_at = utc_now()
                    dialog.close()
                    save("Architekturvorschlag verworfen")
                ui.button("Vorschlag verwerfen", icon="block", on_click=reject).props("color=negative no-caps")
        dialog.open()


    def accept_proposal(proposal_id: str) -> None:
        proposal = package().find_architecture_proposal(proposal_id)
        if proposal is None:
            return
        try:
            preview = package().model_copy(deep=True)
            preview_proposal = preview.find_architecture_proposal(proposal.id)
            if preview_proposal is None:
                raise ValueError("Der Architekturvorschlag gehört nicht zu diesem Projekt.")
            compile_architecture_proposal(
                preview, preview_proposal, builtins, architecture_catalog
            )
        except Exception as error:
            ui.notify(f"Vorschlag konnte nicht übernommen werden: {error}", type="negative", close_button=True)
            return
        if not create_safety_revision(f"Vor Übernahme des Architekturvorschlags {proposal.name}"):
            return
        summary = compile_architecture_proposal(
            package(), proposal, builtins, architecture_catalog
        )
        proposal.reviewed_at = utc_now()
        if save_architecture(
            f"Vorschlag übernommen: {summary.domain_count} Domains, {summary.element_count} AE, {summary.signal_count} Interfaces, "
            f"{summary.system_element_count} System-, {summary.mechanical_element_count} Mechanik-, {summary.software_element_count} Softwareelemente und {summary.function_element_count} FE"
        ):
            switch_to_architecture()

    def accept_all_proposal(proposal_id: str) -> None:
        proposal = package().find_architecture_proposal(proposal_id)
        if proposal is None or proposal.status != ProposalStatus.DRAFT:
            return
        for candidate in [*proposal.domains, *proposal.elements, *proposal.interfaces,
                          *proposal.system_elements, *proposal.mechanical_elements,
                          *proposal.software_elements, *proposal.function_elements]:
            candidate.selected_for_execution = True
        accept_proposal(proposal_id)

    def open_section(section: str, **filter_values: str) -> None:
        filters["section"] = section
        filters.update(filter_values)
        switch_workspace({
            "workflow": "overview",
            "system": "overview",
            "documents": "documents",
            "requirements": "requirements",
            "standards": "standards",
            "components": "requirements",
            "realizations": "requirements",
            "verification": "requirements",
            "interfaces": "requirements",
            "proposals": "architecture",
        }.get(section, "overview"))

    def system_definition_dialog() -> None:
        current = package().system_definition
        with ui.dialog() as dialog, ui.card().classes("w-[900px] max-w-[97vw] p-6 gap-4"):
            ui.label("Systemdefinition bearbeiten").classes("text-xl font-bold")
            ui.label(
                "Dieser gemeinsame Kontext führt Dokumentanalyse, Elektronik, Mechanik sowie Software und Firmware."
            ).classes("text-sm text-slate-600")
            core_idea = ui.textarea("Kernidee und Nutzen", value=current.core_idea).props("outlined autogrow").classes("w-full")
            system_boundary = ui.textarea("Systemgrenze", value=current.system_boundary).props("outlined autogrow").classes("w-full")
            primary_flow = ui.textarea("Zentraler Daten-, Energie- oder Materialfluss", value=current.primary_flow).props("outlined autogrow").classes("w-full")
            with ui.row().classes("w-full gap-3"):
                operating_locations = ui.textarea(
                    "Betriebsorte (eine Zeile je Eintrag)", value="\n".join(current.operating_locations),
                ).props("outlined autogrow").classes("grow")
                operating_scenarios = ui.textarea(
                    "Betriebsfälle (eine Zeile je Eintrag)", value="\n".join(current.operating_scenarios),
                ).props("outlined autogrow").classes("grow")
            with ui.row().classes("w-full gap-3"):
                external_systems = ui.textarea(
                    "Externe Systeme", value="\n".join(current.external_systems),
                ).props("outlined autogrow").classes("grow")
                exclusions = ui.textarea(
                    "Ausdrückliche Ausschlüsse", value="\n".join(current.exclusions),
                ).props("outlined autogrow").classes("grow")
                assumptions = ui.textarea(
                    "Offene Annahmen", value="\n".join(current.assumptions),
                ).props("outlined autogrow").classes("grow")
            maturity = ui.select(
                {item.value: item.value for item in DesignMaturity},
                value=current.maturity.value,
                label="Reifegrad",
            ).classes("w-full")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply() -> None:
                    def lines(value: str) -> list[str]:
                        return [item.strip() for item in value.splitlines() if item.strip()]

                    current.core_idea = core_idea.value or ""
                    current.system_boundary = system_boundary.value or ""
                    current.primary_flow = primary_flow.value or ""
                    current.operating_locations = lines(operating_locations.value or "")
                    current.operating_scenarios = lines(operating_scenarios.value or "")
                    current.external_systems = lines(external_systems.value or "")
                    current.exclusions = lines(exclusions.value or "")
                    current.assumptions = lines(assumptions.value or "")
                    current.maturity = DesignMaturity(maturity.value)
                    current.reviewed_at = utc_now() if current.maturity in {
                        DesignMaturity.CONFIRMED, DesignMaturity.RELEASED,
                    } else None
                    dialog.close()
                    save("Systemdefinition gespeichert")

                ui.button("Speichern", icon="save", on_click=apply).props("no-caps")
        dialog.open()


    def _requirement_parts(requirement_id: str) -> list[DesignComponent]:
        linked_ids = {
            item.target_id for item in package().requirement_links
            if item.requirement_id == requirement_id
            and item.target_type == RequirementTargetType.COMPONENT
        }
        return [
            item for item in package().components
            if requirement_id in item.requirement_ids or item.id in linked_ids
        ]


    def _requirement_standard_count(requirement_id: str) -> int:
        return sum(
            item.requirement_id == requirement_id
            for item in package().requirement_standard_links
        )

    def _requirement_target_label(link: RequirementLink) -> str:
        target: object | None = None
        if link.target_type == RequirementTargetType.DOMAIN:
            target = package().find_domain(link.target_id)
        elif link.target_type == RequirementTargetType.ELEMENT:
            result = package().find_element(link.target_id)
            target = result[1] if result else None
        elif link.target_type == RequirementTargetType.SIGNAL:
            target = package().find_architecture_signal(link.target_id)
        elif link.target_type == RequirementTargetType.CONNECTION:
            target = next(
                (item for item in package().connections if item.id == link.target_id),
                None,
            )
        elif link.target_type == RequirementTargetType.COMPONENT:
            target = package().find_component(link.target_id)
        elif link.target_type == RequirementTargetType.INTERFACE:
            target = package().find_interface_requirement(link.target_id)
        elif link.target_type == RequirementTargetType.MECHANICAL_COMPONENT:
            target = package().find_mechanical_component(link.target_id)
        elif link.target_type == RequirementTargetType.MECHANICAL_CONSTRAINT:
            target = package().find_mechanical_constraint(link.target_id)
        elif link.target_type == RequirementTargetType.SOFTWARE_COMPONENT:
            target = package().find_software_component(link.target_id)
        elif link.target_type == RequirementTargetType.SOFTWARE_WORK_ITEM:
            target = package().find_software_work_item(link.target_id)
        elif link.target_type == RequirementTargetType.TECHNICAL_REALIZATION:
            target = package().find_technical_realization(link.target_id)
        elif link.target_type == RequirementTargetType.VERIFICATION_CASE:
            target = package().find_verification_case(link.target_id)
        else:
            target=project_objects(package()).get(link.target_type.value,{}).get(link.target_id)
        return str(
            getattr(target, "name", None)
            or getattr(target, "title", None)
            or link.target_type.value
        )

    def _set_requirement_maturity(
        requirement: EcadRequirement,
        maturity: RequirementMaturity,
    ) -> None:
        requirement.maturity = maturity
        save(
            "Requirement bestätigt"
            if maturity == RequirementMaturity.APPROVED
            else "Requirement verworfen"
        )

    @ui.refreshable
    def overview_workspace() -> None:
        requirements = package().requirements
        traceability = requirement_traceability_index(package())
        approved = sum(item.maturity == RequirementMaturity.APPROVED for item in requirements)
        detected = sum(item.maturity in {
            RequirementMaturity.DETECTED, RequirementMaturity.IN_REVIEW,
        } for item in requirements)
        realization_requirements = [
            item for item in requirements
            if effective_layer(item) == RequirementLevel.DISCIPLINE
        ]
        technically_covered = sum(
            traceability[item.id].coverage
            == RequirementCoverageStatus.COVERED
            for item in requirements
        )
        with ui.column().classes("w-full p-5 gap-4 simple-workspace"):
            with ui.row().classes("w-full items-start gap-3"):
                with ui.column().classes("gap-0 grow"):
                    ui.label("Projektübersicht").classes("text-2xl font-bold")
                    ui.label(
                        "Von der Quelle über vier Requirements-Ebenen zu Lösung und Verifikation."
                    ).classes("subtle")
                ui.button(
                    "Dokument hinzufügen", icon="upload_file", on_click=document_import_dialog,
                ).props("outline no-caps")
                ui.button(
                    "Requirement anlegen", icon="add", on_click=lambda: requirement_dialog(),
                ).props("outline no-caps")
                ui.button(
                    "HW / ECAD öffnen", icon="memory", on_click=switch_to_architecture,
                ).props("no-caps")

            with ui.card().classes("w-full p-5 gap-4 border cascade-map"):
                with ui.row().classes("w-full items-center gap-3"):
                    ui.icon("account_tree", size="30px", color="primary")
                    with ui.column().classes("gap-0 grow"):
                        ui.label("Kaskadierte Systementwicklung").classes("text-xl font-bold")
                        ui.label(
                            "Quellen führen über L1 Kunde, L2 System und L3 Technik zu L4 Disziplin. "
                            "Danach folgen Realisierung, Arbeitsarchitektur und Nachweise."
                        ).classes("subtle")
                    if detected:
                        ui.badge(f"{detected} zu prüfen", color="amber-2").props("text-color=amber-10")

                with ui.row().classes("w-full justify-center items-stretch gap-3 cascade-source-row"):
                    for title, detail, icon, target in (
                        ("Quelldokumente", str(len(package().source_documents)), "folder_open", "documents"),
                        ("Dokumentanalyse", str(len(package().document_analyses)), "auto_awesome", "documents"),
                        ("Systembild", "aus Analyse", "hub", "overview"),
                        ("Vier Requirements-Layer", f"{len(requirements)} · {approved} bestätigt", "fact_check", "requirements"),
                    ):
                        with ui.button(
                            on_click=lambda _, value=target: switch_workspace(value),
                        ).props("flat no-caps").classes("cascade-step"):
                            ui.icon(icon, size="26px")
                            ui.label(title).classes("font-bold")
                            ui.label(detail).classes("text-xs text-slate-500")

                with ui.row().classes("w-full justify-center items-stretch gap-2 flex-wrap"):
                    for number, heading, value in LAYERS:
                        count = sum(effective_layer(item) == value for item in requirements)
                        with ui.button(on_click=lambda _, item=value: (
                            filters.update(requirement_level=item.value), switch_workspace("requirements")
                        )).props("flat no-caps").classes("cascade-step"):
                            ui.label(f"{number} · {heading}").classes("font-bold")
                            ui.label(f"{count} Anforderungen").classes("text-xs text-slate-600")

                with ui.row().classes("w-full justify-center"):
                    ui.icon("south", size="28px", color="primary")

                branches = [
                    ("System", {RequirementClassification.SYSTEM}, "hub", "branch-system"),
                    ("HW / ECAD", {RequirementClassification.HARDWARE}, "memory", "branch-hardware"),
                    ("Mechanik / CAD", {RequirementClassification.MECHANICS}, "precision_manufacturing", "branch-mechanics"),
                    ("Software / Firmware", {
                        RequirementClassification.SOFTWARE, RequirementClassification.FIRMWARE,
                    }, "code", "branch-software"),
                ]
                with ui.grid(columns=4).classes("w-full gap-3 discipline-tree-grid"):
                    for label, classifications, icon, css_class in branches:
                        branch_requirements = [
                            item for item in requirements if item.classification in classifications
                        ]
                        branch_approved = sum(
                            item.maturity == RequirementMaturity.APPROVED
                            for item in branch_requirements
                        )
                        with ui.button(
                            on_click=lambda _, values=classifications: (
                                filters.update(classification=(
                                    next(iter(values)).value if len(values) == 1 else "Software / Firmware"
                                )),
                                switch_workspace("requirements"),
                            ),
                        ).props("flat no-caps align=left").classes(f"discipline-branch {css_class}"):
                            with ui.row().classes("w-full items-center gap-2"):
                                ui.icon(icon, size="26px")
                                ui.label(label).classes("font-bold grow text-left")
                            ui.label(
                                f"{len(branch_requirements)} Requirements · {branch_approved} bestätigt"
                            ).classes("text-xs text-slate-600 text-left")
                            category_names = sorted({item.category.value for item in branch_requirements})
                            ui.label(
                                " · ".join(category_names[:4]) or "Noch keine Inhalte"
                            ).classes("text-xs text-slate-500 text-left line-clamp-2")

                with ui.row().classes("w-full justify-center"):
                    ui.icon("south", size="28px", color="primary")
                with ui.grid(columns=4).classes("w-full gap-3 discipline-tree-grid"):
                    for title, detail, icon, target in (
                        (
                            "L4 Disziplinanforderungen",
                            f"{len(realization_requirements)} fachlich abgeleitet",
                            "call_split",
                            "requirements",
                        ),
                        (
                            "Lösungen & Parts",
                            f"{len(package().technical_realizations)} Realisierungen · {len(package().components)} Parts",
                            "developer_board",
                            "requirements",
                        ),
                        (
                            "Arbeitsarchitektur",
                            f"{len(package().domains)} Domains · {sum(len(item.elements) for item in package().domains)} AE",
                            "account_tree",
                            "architecture",
                        ),
                        (
                            "Tests & Nachweise",
                            f"{len(defined_test_requirement_ids(package()))} Requirements mit Test",
                            "science",
                            "requirements",
                        ),
                    ):
                        with ui.button(
                            on_click=lambda _, value=target: switch_workspace(value),
                        ).props("flat no-caps align=left").classes("discipline-branch"):
                            ui.icon(icon, size="26px")
                            ui.label(title).classes("font-bold text-left")
                            ui.label(detail).classes("text-xs text-slate-600 text-left")
                ui.label(
                    f"{technically_covered} von {len(requirements)} Requirements technisch abgedeckt. "
                    "Prüfstatus und Teststatus werden davon unabhängig geführt."
                ).classes("text-xs text-slate-600")

            system = package().system_definition
            if system.core_idea.strip() or system.system_boundary.strip():
                with ui.card().classes("w-full p-4 gap-3 border system-summary-card"):
                    with ui.row().classes("w-full items-start gap-3"):
                        ui.icon("lightbulb", size="26px", color="primary")
                        with ui.column().classes("gap-0 grow"):
                            ui.label("Aus den Quellen erkanntes Systembild").classes("text-lg font-bold")
                            ui.label(system.core_idea or "Kernidee noch offen").classes("text-sm")
                        ui.badge(system.maturity.value, color="blue-1").props("text-color=blue-9")
                        ui.button(
                            "Korrigieren", icon="edit", on_click=system_definition_dialog,
                        ).props("flat dense no-caps")
                    with ui.grid(columns=3).classes("w-full gap-3 compact-system-grid"):
                        for label, value in (
                            ("Systemgrenze", system.system_boundary),
                            ("Zentraler Fluss", system.primary_flow),
                            ("Betriebsfälle", " · ".join(system.operating_scenarios)),
                        ):
                            with ui.column().classes("gap-1 rounded-lg bg-slate-50 p-3"):
                                ui.label(label).classes("text-xs font-bold uppercase text-slate-500")
                                ui.label(value or "Noch nicht erkannt").classes("text-sm")
            elif package().source_documents:
                with ui.row().classes("w-full items-center gap-3 rounded-xl border border-blue-200 bg-blue-50 p-4"):
                    ui.icon("info", color="primary")
                    ui.label(
                        "Die Systemdefinition erscheint hier, sobald eine Dokumentanalyse Kernidee und Systemgrenze erkannt hat."
                    ).classes("text-sm text-blue-900")

    @ui.refreshable
    def documents_workspace() -> None:
        documents = package().source_documents
        selected = next(
            (item for item in documents if item.id == selection["document_id"]),
            documents[0] if documents else None,
        )
        with ui.column().classes("w-full p-5 gap-4 simple-workspace"):
            with ui.row().classes("w-full items-start"):
                with ui.column().classes("gap-0 grow"):
                    ui.label("Quellen & Analyse").classes("text-2xl font-bold")
                    ui.label(
                        "Dokumente, Analyseauftrag und eine strukturierte Übersicht je Quelle."
                    ).classes("subtle")
                ui.button(
                    "Dokumente hinzufügen", icon="upload_file", on_click=document_import_dialog,
                ).props("no-caps")
            if not selected:
                with ui.column().classes("w-full items-center py-16 gap-3 text-slate-500"):
                    ui.icon("description", size="58px")
                    ui.label("Noch keine Quelldokumente vorhanden.").classes("text-lg font-bold")
                    ui.label(
                        "PDF, DOCX, TXT oder Markdown hinzufügen und pro Dokument Kontext und Analyseauftrag festlegen."
                    ).classes("text-sm")
                    ui.button(
                        "Erstes Dokument hinzufügen", icon="upload_file", on_click=document_import_dialog,
                    ).props("no-caps")
                return

            with ui.row().classes("w-full gap-2 flex-wrap document-chip-row"):
                for document in documents:
                    ui.button(
                        document.name,
                        icon="description",
                        on_click=lambda _, item=document: select_document(item.id),
                    ).props(
                        ("unelevated color=primary" if document.id == selected.id else "outline")
                        + " dense no-caps"
                    )

            analyses = sorted(
                [item for item in package().document_analyses if item.document_id == selected.id],
                key=lambda item: item.revision_number,
                reverse=True,
            )
            analysis = next(
                (item for item in analyses if item.id == selection["analysis_id"]),
                analyses[0] if analyses else None,
            )
            with ui.card().classes("w-full p-5 gap-3 border"):
                with ui.row().classes("w-full items-start gap-3"):
                    ui.icon("description", size="30px", color="primary")
                    with ui.column().classes("gap-0 grow"):
                        ui.label(selected.name).classes("text-xl font-bold")
                        ui.label(selected.file_name).classes("subtle")
                    ui.badge(selected.analysis_status.value, color="green-2").props("text-color=green-9")
                    profile_label = str(selected.properties.get("documentType") or "").strip()
                    if profile_label:
                        ui.badge(profile_label, color="blue-1").props("text-color=blue-9")
                    if document_context_available(selected):
                        ui.button(
                            "Inhalt anzeigen", icon="article",
                            on_click=lambda: open_document_context_dialog(selected),
                        ).props("outline dense no-caps")
                context_label = str(selected.properties.get("documentContext") or "").strip()
                if context_label:
                    ui.label(context_label).classes("text-sm bg-slate-50 rounded-lg p-3")
                if len(analyses) > 1:
                    with ui.row().classes("gap-2 items-center"):
                        ui.label("Analysestand:").classes("text-xs font-bold text-slate-500")
                        for item in analyses:
                            ui.button(
                                f"R{item.revision_number}",
                                on_click=lambda _, revision=item: select_document_analysis(selected.id, revision.id),
                            ).props(
                                ("unelevated color=primary" if analysis and item.id == analysis.id else "outline")
                                + " dense no-caps"
                            )

            if analysis is None:
                with ui.card().classes("w-full p-5 border border-amber-300 bg-amber-50"):
                    ui.label("Für dieses Dokument liegt noch keine strukturierte Analyse vor.").classes("font-bold")
                    ui.label("Der Dokumentkontext bleibt gespeichert und kann erneut analysiert werden.").classes("text-sm")
                return

            def review_evidence(candidate: Any, status: CandidateReviewStatus, label: str) -> None:
                candidate.review_status = status
                if status != CandidateReviewStatus.OPEN:
                    candidate.review_comment = f"Manuell {status.value}"
                save(f"Analysebefund „{label}“ auf {status.value} gesetzt")

            def mark_evidence_conflict(candidate: Any, label: str) -> None:
                message = f"Manuell markierter Analysekonflikt: {label}"
                if message not in analysis.conflicts:
                    analysis.conflicts.append(message)
                candidate.review_status = CandidateReviewStatus.OPEN
                candidate.review_comment = "Als Konflikt markiert"
                save(f"Analysebefund „{label}“ als Konflikt markiert")

            def adjust_evidence(candidate: Any, label: str) -> None:
                with ui.dialog() as evidence_dialog, ui.card().classes("w-[760px] max-w-[96vw] p-6 gap-3"):
                    ui.label("Analysebefund anpassen").classes("text-xl font-bold")
                    name_field = ui.input(
                        "Bezeichnung / beobachteter Netzname",
                        value=getattr(candidate, "name", getattr(candidate, "observed_name", label)),
                    ).props("outlined").classes("w-full")
                    locator_field = ui.input(
                        "Fundstelle", value=getattr(candidate, "source_locator", "")
                    ).props("outlined").classes("w-full")
                    detail_attribute = "connection_evidence" if hasattr(candidate, "connection_evidence") else "purpose"
                    detail_field = ui.textarea(
                        "Evidenz / Zweck", value=getattr(candidate, detail_attribute, "")
                    ).props("outlined autogrow").classes("w-full")
                    comment_field = ui.textarea(
                        "Review-Kommentar", value=getattr(candidate, "review_comment", "")
                    ).props("outlined autogrow").classes("w-full")

                    def apply_adjustment() -> None:
                        target_name = "name" if hasattr(candidate, "name") else "observed_name"
                        setattr(candidate, target_name, str(name_field.value or "").strip())
                        candidate.source_locator = str(locator_field.value or "").strip()
                        setattr(candidate, detail_attribute, str(detail_field.value or "").strip())
                        candidate.review_comment = str(comment_field.value or "").strip()
                        candidate.review_status = CandidateReviewStatus.OPEN
                        evidence_dialog.close()
                        save(f"Analysebefund „{label}“ angepasst")

                    with ui.row().classes("w-full justify-end gap-2"):
                        ui.button("Abbrechen", on_click=evidence_dialog.close).props("flat no-caps")
                        ui.button("Speichern", icon="save", on_click=apply_adjustment).props("no-caps")
                evidence_dialog.open()

            with ui.card().classes("w-full p-5 gap-4 border analysis-overview"):
                with ui.row().classes("w-full items-start gap-3"):
                    ui.icon("auto_awesome", size="28px", color="primary")
                    with ui.column().classes("gap-0 grow"):
                        ui.label(f"Analyseübersicht · R{analysis.revision_number}").classes("text-xl font-bold")
                        ui.label(
                            "Erkannte Inhalte werden in ihren Fachbereichen geprüft; diese Ansicht bleibt die dokumentbezogene Herkunft."
                        ).classes("subtle")
                    ui.badge(analysis.provider or "Analyse", color="blue-1").props("text-color=blue-9")

                system_items = [
                    ("Kernidee", analysis.system_core_idea, "lightbulb"),
                    ("Systemgrenze", analysis.system_boundary, "crop_free"),
                    ("Zentraler Fluss", analysis.primary_flow, "sync_alt"),
                    ("Betriebsfälle", " · ".join(analysis.operating_scenarios), "play_circle"),
                ]
                if any(value for _, value, _ in system_items):
                    ui.label("Systembild aus diesem Dokument").classes("analysis-section-title")
                    with ui.grid(columns=2).classes("w-full gap-3 analysis-summary-grid"):
                        for label, value, icon in system_items:
                            if not value:
                                continue
                            with ui.column().classes("analysis-summary-tile"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon(icon, size="19px", color="primary")
                                    ui.label(label).classes("font-bold text-sm")
                                ui.label(value).classes("text-sm")

                classification_groups = [
                    ("System", {RequirementClassification.SYSTEM}, "hub"),
                    ("HW / ECAD", {RequirementClassification.HARDWARE}, "memory"),
                    ("Mechanik / CAD", {RequirementClassification.MECHANICS}, "precision_manufacturing"),
                    ("Software / Firmware", {
                        RequirementClassification.SOFTWARE, RequirementClassification.FIRMWARE,
                    }, "code"),
                ]
                ui.label("Erkannte Anforderungen").classes("analysis-section-title")
                with ui.grid(columns=4).classes("w-full gap-3 discipline-analysis-grid"):
                    for label, classes, icon in classification_groups:
                        values = [item for item in analysis.requirements if item.classification in classes]
                        with ui.column().classes("analysis-count-tile"):
                            ui.icon(icon, size="23px", color="primary")
                            ui.label(label).classes("font-bold")
                            ui.label(str(len(values))).classes("text-2xl font-bold")
                            ui.label(
                                " · ".join(sorted({item.category.value for item in values})[:3])
                                or "Keine erkannt"
                            ).classes("text-xs text-slate-500 line-clamp-2")

                with ui.grid(columns=3).classes("w-full gap-3 analysis-detail-grid"):
                    analysis_groups = [
                        ("Schnittstellen", "hub", analysis.interfaces, lambda item: item.name),
                        ("Komponenten / Parts", "memory", analysis.components, lambda item: item.name),
                        (
                            "Software / Firmware",
                            "code",
                            analysis.software_components,
                            lambda item: item.name,
                        ),
                        ("Normen & Standards", "gavel", analysis.standards, lambda item: item.designation),
                        (
                            "As-Is-Architektur",
                            "account_tree",
                            analysis.architecture_elements,
                            lambda item: item.name,
                        ),
                        (
                            "AE-Verbindungen",
                            "lan",
                            analysis.architecture_interfaces,
                            lambda item: (
                                f"{item.name} · {item.catalog_family}/"
                                f"{item.interface_template or 'Template offen'} · "
                                f"{item.host_element_key or 'Host offen'} → "
                                f"{len(item.participant_element_keys)} Teilnehmer"
                            ),
                        ),
                    ]
                    for title, icon, values, label_getter in analysis_groups:
                        with ui.card().classes("w-full p-4 gap-2 border shadow-none"):
                            with ui.row().classes("w-full items-center gap-2"):
                                ui.icon(icon, color="primary")
                                ui.label(title).classes("font-bold grow")
                                ui.badge(str(len(values)), color="grey-3").props("text-color=grey-9")
                            for value in values[:6]:
                                ui.label(f"• {label_getter(value)}").classes("text-sm")
                            if len(values) > 6:
                                ui.label(f"+ {len(values) - 6} weitere").classes("subtle")
                            if not values:
                                ui.label("Keine expliziten Angaben erkannt.").classes("subtle")

                if analysis.sheet_inventory:
                    with ui.expansion(
                        f"Erkannte Schaltplanblätter ({len(analysis.sheet_inventory)})",
                        icon="view_carousel", value=True,
                    ).classes("w-full border rounded-lg"):
                        for sheet in analysis.sheet_inventory:
                            with ui.row().classes("w-full items-start gap-3 border-b py-2"):
                                ui.icon("description", color="primary")
                                with ui.column().classes("gap-0 grow"):
                                    ui.label(sheet.sheet_name).classes("font-bold")
                                    ui.label(sheet.function or "Funktion noch offen").classes("text-sm")
                                    ui.label(
                                        " · ".join(filter(None, [sheet.hierarchy_path, sheet.source_locator]))
                                    ).classes("text-xs text-slate-500")
                                ui.badge(f"{sheet.confidence:.0%}", color="grey-3").props("text-color=grey-9")

                if analysis.architecture_interfaces:
                    with ui.expansion(
                        f"AE-übergreifende Verbindungen prüfen ({len(analysis.architecture_interfaces)})",
                        icon="lan", value=True,
                    ).classes("w-full border rounded-lg"):
                        for connection in analysis.architecture_interfaces:
                            with ui.column().classes("w-full gap-1 border-b py-3"):
                                with ui.row().classes("w-full items-center gap-2"):
                                    ui.label(connection.name).classes("font-bold grow")
                                    ui.badge(connection.review_status.value, color="amber-2").props("text-color=grey-9")
                                ui.label(
                                    f"{connection.catalog_family}/{connection.interface_template or 'Template offen'} · "
                                    f"Richtung {connection.direction_confidence:.0%} · Topologie {connection.topology_confidence:.0%}"
                                ).classes("text-sm")
                                ui.label(connection.connection_evidence or connection.rationale).classes("text-sm text-slate-600")
                                ui.label(connection.source_locator or "Fundstelle offen").classes("text-xs text-slate-500")
                                with ui.row().classes("gap-2"):
                                    ui.button("Bestätigen", on_click=lambda _, item=connection: review_evidence(item, CandidateReviewStatus.ACCEPTED, item.name)).props("flat dense no-caps")
                                    ui.button("Anpassen", on_click=lambda _, item=connection: adjust_evidence(item, item.name)).props("flat dense no-caps")
                                    ui.button("Verwerfen", on_click=lambda _, item=connection: review_evidence(item, CandidateReviewStatus.REJECTED, item.name)).props("flat dense no-caps color=negative")
                                    ui.button("Als Konflikt", on_click=lambda _, item=connection: mark_evidence_conflict(item, item.name)).props("flat dense no-caps color=warning")

                if analysis.internal_nets:
                    with ui.expansion(
                        f"Interne Implementierungsnetze ({len(analysis.internal_nets)})",
                        icon="layers_clear",
                    ).classes("w-full border rounded-lg"):
                        ui.label(
                            "Diese Netze bleiben als As-Is-Evidenz erhalten und werden nicht als Architekturverbindung übernommen."
                        ).classes("text-xs text-slate-600")
                        for net in analysis.internal_nets:
                            with ui.row().classes("w-full items-start gap-3 border-b py-2"):
                                with ui.column().classes("gap-0 grow"):
                                    ui.label(net.observed_name).classes("font-mono text-sm font-bold")
                                    ui.label(net.purpose or net.exclusion_rationale).classes("text-sm")
                                    ui.label(net.source_locator).classes("text-xs text-slate-500")
                                ui.badge(net.review_status.value, color="amber-2").props("text-color=grey-9")
                                with ui.row().classes("gap-1"):
                                    ui.button("Bestätigen", on_click=lambda _, item=net: review_evidence(item, CandidateReviewStatus.ACCEPTED, item.observed_name)).props("flat dense no-caps")
                                    ui.button("Anpassen", on_click=lambda _, item=net: adjust_evidence(item, item.observed_name)).props("flat dense no-caps")
                                    ui.button("Verwerfen", on_click=lambda _, item=net: review_evidence(item, CandidateReviewStatus.REJECTED, item.observed_name)).props("flat dense no-caps color=negative")
                                    ui.button("Als Konflikt", on_click=lambda _, item=net: mark_evidence_conflict(item, item.observed_name)).props("flat dense no-caps color=warning")

                pipeline = str(selected.properties.get("analysisPipeline") or "").strip()
                if pipeline:
                    ui.label(
                        "Analyseverfahren: " + (
                            "visuelle PDF-Evidenz mit dokumentweiter Konsolidierung"
                            if pipeline == "visual-evidence+document-consolidation"
                            else "strukturierte Text-/Dateianalyse"
                        )
                    ).classes("text-xs text-slate-500")

                excluded_internal_nets = sum(
                    item.excluded_internal_signal_count
                    for item in analysis.architecture_interfaces
                )
                if excluded_internal_nets:
                    with ui.row().classes(
                        "w-full items-center gap-2 rounded-lg border border-slate-300 bg-slate-50 p-3"
                    ):
                        ui.icon("layers_clear", color="grey-7")
                        ui.label(
                            f"{excluded_internal_nets} interne Netze wurden als Implementierungsdetails erkannt "
                            "und bewusst nicht als AE-Verbindungen übernommen."
                        ).classes("text-sm text-slate-700")

                if analysis.open_questions or analysis.conflicts:
                    with ui.expansion(
                        f"Offene Punkte ({len(analysis.open_questions) + len(analysis.conflicts)})",
                        icon="help_outline", value=True,
                    ).classes("w-full border rounded-lg"):
                        for item in analysis.open_questions:
                            ui.label(f"Frage · {item}").classes("text-sm")
                        for item in analysis.conflicts:
                            ui.label(f"Konflikt · {item}").classes("text-sm text-red-700")
                with ui.row().classes("w-full justify-end"):
                    ui.button(
                        "Requirements dieses Dokuments prüfen", icon="fact_check",
                        on_click=lambda: (
                            filters.update(document=selected.id),
                            switch_workspace("requirements"),
                        ),
                    ).props("no-caps")

    @ui.refreshable
    def requirements_workspace() -> None:
        query_value = filters.get("query", "")
        maturity_value = filters.get("maturity", "All")
        decision_value = filters.get("customer_decision", "All")
        source_value = filters.get("document", "All")
        branch_value = filters.get("classification", "All")
        level_value = filters.get("requirement_level", "All")
        coverage_value = filters.get("coverage", "All")
        traceability = requirement_traceability_index(package())
        with ui.column().classes("w-full p-5 gap-4 requirements-workspace"):
            with ui.row().classes("w-full items-start"):
                with ui.column().classes("gap-0 grow"):
                    ui.label("Requirements").classes("text-2xl font-bold")
                    ui.label(
                        "Vier Anforderungsebenen und die zugehörige Lösungsebene – jedes Objekt nur einmal."
                    ).classes("subtle")
                ui.button(
                    "Requirement", icon="add", on_click=lambda: requirement_dialog(),
                ).props("no-caps")
            from .architecture_generation_ui import open_generation_dialog
            ui.button('Architektur aus Requirements erzeugen',icon='auto_awesome',on_click=lambda:open_generation_dialog(package,generate_proposal,open_ai_assistant)).props('outline no-caps')
            with ui.row().classes("w-full gap-2 items-center flex-wrap requirements-filterbar"):
                query = ui.input(
                    "Suchen", value=query_value, placeholder="ID, Titel oder Inhalt",
                ).props("dense outlined clearable debounce=300").classes("grow")
                branch = ui.select(
                    {
                        "All": "Gesamtes System",
                        RequirementClassification.SYSTEM.value: "System",
                        RequirementClassification.HARDWARE.value: "HW / ECAD",
                        RequirementClassification.MECHANICS.value: "Mechanik / CAD",
                        "Software / Firmware": "Software / Firmware",
                    },
                    value=branch_value if branch_value in {
                        "All", RequirementClassification.SYSTEM.value,
                        RequirementClassification.HARDWARE.value,
                        RequirementClassification.MECHANICS.value,
                        "Software / Firmware",
                    } else "All",
                    label="Systembereich",
                ).props("dense outlined").classes("w-48")
                maturity = ui.select(
                    {"All": "Alle Prüfstände", **{item.value: item.value for item in RequirementMaturity}},
                    value=maturity_value,
                    label="Prüfstand",
                ).props("dense outlined").classes("w-44")
                customer_decision = ui.select({'All':'Alle Kundenentscheidungen','Open':'Annahme offen','Accepted':'Angenommen','Rejected':'Abgelehnt'},value=decision_value,label='Kundenentscheidung (L1)').props('dense outlined').classes('w-52')
                source = ui.select(
                    {"All": "Alle Quellen", **{item.id: item.name for item in package().source_documents}},
                    value=(
                        source_value
                        if source_value == "All"
                        or any(item.id == source_value for item in package().source_documents)
                        else "All"
                    ),
                    label="Quelldokument",
                ).props("dense outlined options-dense").classes("w-52")
                level = ui.select(
                    {"All": "Alle Ebenen", **{
                        layer.value: f"{number} · {heading}" for number, heading, layer in LAYERS
                    }},
                    value=level_value,
                    label="Anforderungsebene",
                ).props("dense outlined").classes("w-52")
                coverage = ui.select(
                    {"All": "Alle Abdeckungen", **COVERAGE_LABELS},
                    value=coverage_value,
                    label="Technische Abdeckung",
                ).props("dense outlined").classes("w-52")

                def update_tree_filters(_=None) -> None:
                    filters.update(
                        query=query.value or "",
                        classification=branch.value or "All",
                        maturity=maturity.value or "All",
                        customer_decision=customer_decision.value or "All",
                        document=source.value or "All",
                        requirement_level=level.value or "All",
                        coverage=coverage.value or "All",
                        v_scope="__all__",
                    )
                    requirements_workspace.refresh()

                query.on_value_change(update_tree_filters)
                branch.on_value_change(update_tree_filters)
                maturity.on_value_change(update_tree_filters)
                customer_decision.on_value_change(update_tree_filters)
                source.on_value_change(update_tree_filters)
                level.on_value_change(update_tree_filters)
                coverage.on_value_change(update_tree_filters)

            def included(item: EcadRequirement) -> bool:
                haystack = f"{item.identifier} {item.external_id} {item.title} {item.text}".casefold()
                if query_value.casefold() not in haystack:
                    return False
                if maturity_value != "All" and item.maturity.value != maturity_value:
                    return False
                if decision_value != 'All':
                    from .requirements_layers import derivation_edges
                    origins=[item] if effective_layer(item).value=='Customer Requirement' else [package().find_requirement(a) for a,b in derivation_edges(package()) if b==item.id]
                    if not any(r and r.customer_decision==decision_value and effective_layer(r).value=='Customer Requirement' for r in origins):return False
                if source_value != "All" and item.source_document_id != source_value:
                    return False
                if level_value != "All" and effective_layer(item).value != level_value:
                    return False
                if (
                    coverage_value != "All"
                    and traceability[item.id].coverage.value != coverage_value
                ):
                    return False
                if branch_value == "Software / Firmware":
                    return item.classification in {
                        RequirementClassification.SOFTWARE, RequirementClassification.FIRMWARE,
                    }
                if branch_value != "All" and item.classification.value != branch_value:
                    return False
                return True

            visible_requirements = [item for item in package().requirements if included(item)]
            display_mode=filters.get('display_mode','list')
            def display_changed(event):
                mode=event.value or 'list'
                filters.update(display_mode=mode,graph_focus=('req:'+selection['requirement_id']) if mode=='chain' and selection.get('requirement_id') else '__all__',v_focus='')
                requirements_workspace.refresh()
            ui.toggle({'list':'Anforderungsliste','chain':'Anforderungskette','overview':'Gesamtübersicht'},value=display_mode,on_change=display_changed).props('no-caps')
            if display_mode=='list':
                from .requirements_navigation_ui import render_navigation
                render_navigation(package(),visible_requirements,selection.get('requirement_id'),select_requirement,select_architecture,select_realization)
                return
            if display_mode=='chain' and filters.get('graph_focus','__all__')=='__all__':
                ui.label('Requirement in der Anforderungsliste auswählen.').classes('text-slate-500')
                return
            all_requirements = {item.id: item for item in package().requirements}
            focus_id = filters.get("v_focus") or None
            if focus_id not in all_requirements:
                focus_id = None
            # One graph remains the authoritative view. In large models open
            # a directed L2 branch first; allow L3 subbranches or the whole
            # graph at any time. No object is duplicated or omitted from SPOT.
            chosen_scope = '__all__'
            scoped_visible_ids = {item.id for item in visible_requirements}
            layer_view = build_layer_view(
                package(), focus_id, visible_ids=scoped_visible_ids,
                include_inactive=True,
            )
            solution_graph = build_solution_graph(package())
            all_edges = {
                (parent, child) for parent, child in derivation_edges(package())
                if parent in all_requirements and child in all_requirements
            }
            parents_by_child: dict[str, list[str]] = {}
            children_by_parent: dict[str, list[str]] = {}
            for parent, child in all_edges:
                parents_by_child.setdefault(child, []).append(parent)
                children_by_parent.setdefault(parent, []).append(child)
            shown = [item for column in layer_view.columns for item in column]
            shown_ids = {item.id for item in shown}
            active_requirement_filter = any((
                query_value, branch_value != "All", maturity_value != "All",
                source_value != "All", level_value != "All", coverage_value != "All",
            ))
            solution_keys = solution_graph.visible_nodes(
                shown_ids if focus_id or active_requirement_filter or chosen_scope != "__all__" else None
            )
            if not focus_id and chosen_scope != "__all__":
                solution_keys |= solution_graph.unallocated
            solution_objects = {
                **{"real:" + item.id: item for item in package().technical_realizations},
                **{"part:" + item.id: item for item in package().components},
                **{"mech:" + item.id: item for item in package().mechanical_components},
                **{"sw:" + item.id: item for item in package().software_components},
            }
            architecture_kinds={'SystemDomain','SystemElement','SystemRelation','Domain','ArchitectureElement','FunctionElement','Port','ArchitectureSignal','Connection',
                                'MechanicalArchitectureElement','SoftwareArchitectureElement','DisciplineRelation','IntegrationInterface','Signal'}
            solution_objects.update({'arch:'+oid:obj for kind,group in project_objects(package()).items() if kind in architecture_kinds for oid,obj in group.items()})
            from .realization_service import core_component_ids
            core_ids={c.id for c in package().components if c.system_defining is True}
            for realization in package().technical_realizations:
                for variant in realization.variants:core_ids|=core_component_ids(package(),variant)
            solution_keys={key for key in solution_keys if not key.startswith('part:') or key[5:] in core_ids}
            from .requirements_layers import focused_graph
            full_nodes={'req:'+r.id for r in package().requirements}|set(solution_graph.nodes)
            full_edges=set(solution_graph.edges)|{('req:'+a,'req:'+b) for a,b in derivation_edges(package())}
            prefixes={'Requirement':'req:','Realization':'real:','TechnicalRealization':'real:','Component':'part:','MechanicalComponent':'mech:','SoftwareComponent':'sw:'}
            prefixes.update({kind:'arch:' for kind in architecture_kinds})
            for relation in package().model_relations:
                a=prefixes.get(relation.source_type,'')+relation.source_id;b=prefixes.get(relation.target_type,'')+relation.target_id
                full_edges.add((b,a) if relation.kind=='derived_from' else (a,b))
            graph_focus=filters.get('graph_focus','__all__')
            graph_depth=filters.get('graph_depth','chain')
            if graph_focus!='__all__':
                focused=focused_graph(full_nodes,full_edges,graph_focus,graph_depth)
                layer_view=build_layer_view(package(),visible_ids={key[4:] for key in focused if key.startswith('req:')},include_inactive=True)
                solution_keys={key for key in focused & set(solution_graph.nodes) if not key.startswith('part:') or key[5:] in core_ids}
                shown=[item for column in layer_view.columns for item in column]
                shown_ids={item.id for item in shown}
            solution_query = filters.get("solution_query", "").strip().casefold()
            if solution_query:
                matching = {
                    key for key in solution_keys
                    for item in [solution_objects[key]]
                    if solution_query in " ".join((
                        item.name, getattr(item, "manufacturer_part_number", ""),
                        getattr(item, "legacy_ecad_reference", ""),
                        getattr(item, "generic_function", ""),
                        " ".join(variant.name for variant in getattr(item, "variants", [])),
                    )).casefold()
                }
                solution_keys = matching | {
                    source for source, target in solution_graph.edges
                    if target in matching and source.startswith("real:")
                } | {
                    target for source, target in solution_graph.edges
                    if source in matching and source.startswith("real:")
                }
            detected = sum(item.maturity in {
                RequirementMaturity.DETECTED, RequirementMaturity.IN_REVIEW,
            } for item in shown)
            realization_gaps = sum(
                traceability[item.id].coverage == RequirementCoverageStatus.REALIZATION_GAP
                for item in shown
            )
            with ui.row().classes("w-full items-center gap-3 rounded-xl bg-blue-50 border border-blue-200 p-4"):
                ui.icon("account_tree", size="30px", color="primary")
                with ui.column().classes("gap-0 grow"):
                    ui.label(package().project.name).classes("text-lg font-bold")
                    mode = "in dieser Ableitungskette" if focus_id else "sichtbar"
                    ui.label(f"{len(shown)} Requirements {mode} · {detected} zu prüfen").classes("text-sm text-blue-900")
                if detected:
                    ui.badge("Review erforderlich", color="amber-2").props("text-color=amber-10")
                if realization_gaps:
                    ui.badge(f"{realization_gaps} Realisierungslücken", color="red-2").props("text-color=red-9")
            layer_numbers = {layer: number for number, _, layer in LAYERS}
            standards_by_id = {item.id: item for item in package().standards}
            links_by_requirement: dict[str, list[str]] = {}
            for link in package().requirement_standard_links:
                if link.standard_id in standards_by_id:
                    label = standards_by_id[link.standard_id].designation
                    links_by_requirement.setdefault(link.requirement_id, []).append(
                        label + (f" § {link.clause}" if link.clause else "")
                    )

            def focus_requirement(requirement_id: str) -> None:
                # A selected chain must show every connected layer, even if a
                # previous search or discipline filter would hide its parents.
                filters.update(
                    query="", classification="All", maturity="All", document="All",
                    requirement_level="All", coverage="All", v_focus=requirement_id,
                    solution_query="",
                )
                select_requirement(requirement_id)

            def relation_link(requirement_id: str, direction: str) -> None:
                related = all_requirements[requirement_id]
                short_id = related.identifier or related.external_id or related.id[:9]
                number = layer_numbers[effective_layer(related)]
                ui.button(
                    f"{number} · {short_id}",
                    icon="west" if direction == "parent" else "east",
                    on_click=lambda _, key=requirement_id: focus_requirement(key),
                ).props("flat dense no-caps align=left").classes("isd-v-link")

            all_graph_keys = {"req:" + item.id for item in shown} | solution_keys
            visible_graph_edges = sorted(
                {( "req:" + parent, "req:" + child) for parent, child in layer_view.edges}
                | solution_graph.edges,
            )
            visible_graph_edges = [
                (source, target) for source, target in visible_graph_edges
                if source in all_graph_keys and target in all_graph_keys
            ]
            graph_types = {pair: ("Ableitung" if pair[0].startswith("req:") and pair[1].startswith("req:")
                                  else "Zuordnung" if pair[0].startswith("req:") else "Lösungsbezug", "")
                           for pair in visible_graph_edges}
            graph_node_type = {"Requirement": "req", "Realization": "real", "Component": "part",
                               "MechanicalComponent": "mech", "SoftwareComponent": "sw"}
            graph_node_type.update({kind:'arch' for kind in architecture_kinds})
            for rel in package().model_relations:
                source = graph_node_type.get(rel.source_type, "") + ":" + rel.source_id
                target = graph_node_type.get(rel.target_type, "") + ":" + rel.target_id
                if rel.kind=='derived_from':source,target=target,source
                if source in all_graph_keys and target in all_graph_keys:
                    if (source,target) not in visible_graph_edges:
                        visible_graph_edges.append((source,target))
                    graph_types[(source,target)] = (rel.kind,rel.id)
            safe_key = {key: f"trace_{index}" for index, key in enumerate(sorted(all_graph_keys))}
            diagram_edges = [[safe_key[a], safe_key[b], *graph_types[(a,b)]] for a, b in visible_graph_edges]

            def solution_card(key: str) -> None:
                obj = solution_objects[key]
                kind, _, object_id = key.partition(":")
                labels = {"real": "Realisierung", "part": "Bauteil", "mech": "Mechanik", "sw": "SW / FW"}
                if kind=='arch':
                    with ui.card().classes('isd-trace-card w-full'+(' isd-v-focused' if selection.get('architecture_id')==object_id else '')).props(f'data-trace-key="{safe_key[key]}"'):
                        def show_architecture():
                            select_architecture(object_id)
                        ui.button(obj.name,on_click=show_architecture).props('flat no-caps align=left').classes('isd-trace-card-title w-full')
                        from .property_schema import KIND_LABELS
                        ui.label(KIND_LABELS.get(type(obj).__name__,type(obj).__name__)).classes('isd-trace-card-meta')
                    return
                selected = selection.get({
                    "real": "realization_id", "part": "component_id",
                    "mech": "mechanical_component_id", "sw": "software_component_id",
                }[kind]) == object_id
                handlers = {
                    "real": select_realization, "part": select_component,
                    "mech": select_mechanical_component, "sw": select_software_component,
                }
                with ui.card().classes(
                    "isd-trace-card isd-trace-solution-card w-full"
                    + (" isd-trace-orphan" if key in solution_graph.unallocated else "")
                    + (" isd-v-focused" if selected else "")
                ).props(f'data-trace-key="{safe_key[key]}"').mark('solution-object-'+object_id):
                    ui.button(obj.name, on_click=lambda _, target=object_id, action=handlers[kind]: action(target)).props(
                        "flat no-caps align=left"
                    ).classes("isd-trace-card-title w-full")
                    with ui.row().classes("w-full items-center gap-1 flex-wrap"):
                        ui.badge(labels[kind], color="teal-1").props("text-color=teal-9")
                        if kind == "real":
                            ui.badge(obj.status.value, color="grey-3").props("text-color=grey-9")
                        elif kind == "part":
                            is_existing = bool(obj.legacy_ecad_reference or obj.provenance == RealizationProvenance.OBSERVED)
                            ui.badge("Bestand" if is_existing else (
                                "Physisch" if obj.representation == ComponentRepresentation.PHYSICAL else "Logisch"
                            ), color="amber-2" if is_existing else "grey-3").props("text-color=grey-9")
                    if kind == "real":
                        ui.label(obj.generic_function or f"{len(obj.variants)} Lösungsvarianten").classes("isd-trace-card-meta")
                        if obj.variants:
                            selected_variant = next((v for v in obj.variants if v.id == obj.selected_variant_id), None)
                            ui.label("Ausgewählt: " + selected_variant.name if selected_variant else
                                     f"{len(obj.variants)} Varianten zur Auswahl").classes("isd-trace-card-meta")
                    elif kind == "part":
                        ui.label(" · ".join(value for value in (
                            obj.legacy_ecad_reference, obj.manufacturer, obj.manufacturer_part_number
                        ) if value) or obj.component_type).classes("isd-trace-card-meta")
                    elif kind == "mech":
                        ui.label(obj.kind.value).classes("isd-trace-card-meta")
                    else:
                        ui.label(obj.kind.value).classes("isd-trace-card-meta")
                    if key in solution_graph.unallocated:
                        ui.label("Zuordnung zu Requirement offen").classes("isd-trace-gap")

            with ui.card().classes("w-full p-4 gap-3 border isd-v-board"):
                with ui.row().classes("w-full items-center gap-3 flex-wrap"):
                    ui.icon("schema", size="27px", color="primary")
                    with ui.column().classes("gap-0 grow min-w-0"):
                        ui.label("Ableitung und Lösungsebene").classes("text-lg font-bold")
                        ui.label("Karte wählen: Details anzeigen. Den Abhängigkeitsfokus separat auswählen.").classes(
                            "text-sm text-slate-600"
                        )
                        ui.label("Linien: Ableitung → · Zuordnung → · technische Schnittstelle – – → · Abhängigkeit · · →. Gespeicherte Fachbeziehung anklicken: Begründung ansehen.").classes("text-xs text-slate-600")
                    if focus_id:
                        ui.button("Alle anzeigen", icon="zoom_out_map", on_click=lambda: (
                            filters.update(v_focus=""), requirements_workspace.refresh()
                        )).props("outline dense no-caps")
                    ui.button("Große Grafik", icon="fullscreen", on_click=lambda: ui.run_javascript(
                        "document.querySelector('.workspace')?.classList.add('isd-requirements-focus')"
                    )).props("outline dense no-caps").classes("isd-trace-focus-enter")
                    ui.button("Normalansicht", icon="fullscreen_exit", on_click=lambda: ui.run_javascript(
                        "document.querySelector('.workspace')?.classList.remove('isd-requirements-focus')"
                    )).props("outline dense no-caps").classes("isd-trace-focus-exit")
                    ui.button("Details", icon="open_in_new", on_click=lambda: ui.run_javascript(
                        "document.querySelector('.inspector')?.classList.add("
                        "'isd-mobile-details-open','isd-requirements-inspector-open')"
                    )).props("outline dense no-caps").classes("isd-mobile-details-btn")
                if len(package().requirements) > 35:
                    solution_search = ui.input(
                        "Realisierung / Bauteil suchen", value=filters.get("solution_query", ""),
                        placeholder="Name, RefDes oder MPN",
                    ).props("dense outlined clearable debounce=300").classes("w-72")
                    solution_search.on_value_change(lambda event: (
                        filters.update(solution_query=event.value or ""), requirements_workspace.refresh()
                    ))
                ui.label(
                    f"{len(shown)} Requirements · {len(solution_keys)} Lösungsobjekte im Ergebnis · "
                    f"{sum(key in solution_graph.unallocated for key in solution_keys)} ohne Anforderungszuordnung"
                ).classes("text-xs text-slate-600")
                focus_options={'__all__':'Gesamtes Projekt'}
                focus_options.update({'req:'+r.id:r.identifier+' · '+r.title for r in package().requirements})
                focus_options.update({key:getattr(obj,'name',key) for key,obj in solution_objects.items() if not key.startswith('part:') or key[5:] in core_ids})
                with ui.row().classes('w-full items-center gap-3'):
                    ui.select(focus_options,value=graph_focus if graph_focus in focus_options else '__all__',label='Abhängigkeitsfokus',on_change=lambda e:(filters.update(graph_focus=e.value or '__all__',v_focus='',v_scope='__all__'),requirements_workspace.refresh())).props('use-input outlined dense').classes('grow')
                    ui.select({'direct':'Direkte Beziehungen','chain':'Vollständige Kette'},value=graph_depth,label='Umfang',on_change=lambda e:(filters.update(graph_depth=e.value),requirements_workspace.refresh())).props('outlined dense').classes('w-56')
                    ui.button('Fokus zurücksetzen',icon='zoom_out_map',on_click=lambda:(filters.update(graph_focus='__all__',v_focus='',v_scope='__all__'),requirements_workspace.refresh())).props('flat no-caps')
                with ui.element("div").classes("isd-trace-viewport w-full"):
                    with ui.element("div").classes("isd-trace-stage isd-trace-board"):
                        ui.element("svg").classes("isd-trace-links").props('aria-hidden="true"')
                        ui.label(json.dumps(diagram_edges)).classes("isd-trace-data hidden")
                        lane_sizes=['300px' if column else '180px' for column in layer_view.columns]+['320px']*3
                        with ui.element("div").classes("isd-trace-grid").style('grid-template-columns:'+' '.join(lane_sizes)):
                            for index, (number, heading, _) in enumerate(LAYERS):
                                with ui.column().classes("isd-trace-lane w-full gap-3"):
                                    with ui.row().classes("isd-trace-heading w-full items-center gap-2"):
                                        ui.badge(number, color="blue-2").props("text-color=blue-9")
                                        ui.label(heading).classes("font-bold grow")
                                        ui.badge(str(len(layer_view.columns[index])), color="grey-3").props("text-color=grey-9")
                                    if not layer_view.columns[index]:
                                        ui.label("Noch keine Anforderungen auf dieser Ebene").classes("isd-v-empty")
                                    for item in layer_view.columns[index]:
                                        incoming = sorted(parents_by_child.get(item.id, []), key=lambda key: (
                                            all_requirements[key].identifier, key
                                        ))
                                        outgoing = sorted(children_by_parent.get(item.id, []), key=lambda key: (
                                            all_requirements[key].identifier, key
                                        ))
                                        trace = traceability[item.id]
                                        with ui.card().classes(
                                            "isd-trace-card w-full" + (" isd-v-focused" if item.id == focus_id else "")
                                        ).props(f'data-trace-key="{safe_key["req:" + item.id]}"'):
                                            ui.button(
                                                f"{item.identifier or item.external_id or item.id[:9]} · {item.title}",
                                                on_click=lambda _, key=item.id: select_requirement(key),
                                            ).props("flat no-caps align=left").classes("isd-trace-card-title w-full")
                                            with ui.row().classes("w-full items-center gap-1 flex-wrap"):
                                                ui.badge(item.classification.value, color="blue-1").props("text-color=blue-9")
                                                ui.badge(item.maturity.value, color="grey-3").props("text-color=grey-9")
                                            ui.label(COVERAGE_LABELS[trace.coverage.value] + " · " +
                                                     VERIFICATION_STATE_LABELS[trace.verification.value]).classes("isd-trace-card-meta")
                                            if incoming or outgoing:
                                                ui.label(f"{len(incoming)} Vorgänger · {len(outgoing)} Ableitungen").classes(
                                                    "isd-trace-card-meta"
                                                )
                                            if item.id == focus_id:
                                                for parent_id in incoming:
                                                    relation_link(parent_id, "parent")
                                                for child_id in outgoing:
                                                    relation_link(child_id, "child")
                                            if item.standards_required and not links_by_requirement.get(item.id):ui.badge('Normbezug offen',color='amber-2').props('text-color=amber-10')
                            for lane_index, (lane_title, icon_name) in enumerate((
                                ('Architekturverantwortung','account_tree'),
                                ("Technische Realisierungen", "developer_board"),
                                ("Bauteile und Module", "memory"),
                            )):
                                prefixes = ('arch:',) if lane_index==0 else ("real:",) if lane_index == 1 else ("part:", "mech:", "sw:")
                                keys = sorted((key for key in solution_keys if key.startswith(prefixes)),
                                              key=lambda key: solution_objects[key].name.casefold())
                                allocated = [key for key in keys if key not in solution_graph.unallocated]
                                unallocated = [key for key in keys if key in solution_graph.unallocated]
                                with ui.column().classes("isd-trace-lane isd-trace-solution-lane w-full gap-3"):
                                    with ui.row().classes("isd-trace-heading w-full items-center gap-2"):
                                        ui.icon(icon_name, color="teal-8")
                                        ui.label(lane_title).classes("font-bold grow")
                                        ui.badge(str(len(keys)), color="teal-1").props("text-color=teal-9")
                                    if not keys:
                                        ui.label("Keine zugeordneten Objekte für diese Ansicht").classes("isd-v-empty")
                                    if lane_index==0:
                                        interface_kinds={'InterfacePort','ArchitectureSignal','Connection','SystemRelation','DisciplineRelation','IntegrationInterface','Signal'}
                                        primary=[key for key in allocated if type(solution_objects[key]).__name__ not in interface_kinds]
                                        interfaces=[key for key in allocated if key not in primary]
                                        for key in primary:solution_card(key)
                                        if interfaces:
                                            with ui.expansion(f'Schnittstellenzuordnungen ({len(interfaces)})',value=graph_focus!='__all__').classes('w-full border rounded-lg'):
                                                for key in interfaces:solution_card(key)
                                    elif lane_index == 2 and len(allocated) > 8 and not solution_query:
                                        for prefix, group_label in (("part:", "HW-Bauteile"),
                                                                    ("mech:", "Mechanik"), ("sw:", "SW / FW")):
                                            grouped = [key for key in allocated if key.startswith(prefix)]
                                            if grouped:
                                                with ui.expansion(f"{group_label} · {len(grouped)} Objekte",
                                                                  value=False).classes("w-full border rounded-lg"):
                                                    for key in grouped:
                                                        solution_card(key)
                                    else:
                                        for key in allocated:
                                            solution_card(key)
                                    if unallocated:
                                        orphan_limit = int(filters.get("solution_orphan_limit", "12"))
                                        with ui.expansion(
                                            f"Ohne Requirement-Zuordnung ({len(unallocated)})",
                                            icon="link_off",
                                            value=bool(solution_query or filters.get("solution_orphans_open")),
                                            on_value_change=lambda event: filters.update(
                                                solution_orphans_open="1" if event.value else ""
                                            ),
                                        ).classes("isd-trace-unallocated w-full"):
                                            ui.label("Bestandsobjekte und Vorschläge ohne fachliche Zuordnung.").classes(
                                                "text-xs text-amber-900"
                                            )
                                            for key in unallocated[:orphan_limit]:
                                                solution_card(key)
                                            if len(unallocated) > orphan_limit:
                                                ui.button(
                                                    f"Weitere {min(12, len(unallocated) - orphan_limit)} anzeigen",
                                                    icon="expand_more",
                                                    on_click=lambda: (
                                                        filters.update(solution_orphan_limit=str(
                                                            int(filters.get("solution_orphan_limit", "12")) + 12
                                                        )), requirements_workspace.refresh()
                                                    ),
                                                ).props("outline dense no-caps").classes("w-full")
                if layer_view.gaps:
                    with ui.expansion(
                        f"Ableitungslücken und Ebenensprünge ({len(layer_view.gaps)})", icon="rule"
                    ).classes("w-full"):
                        for issue in layer_view.gaps:
                            ui.label(issue).classes("text-xs text-amber-900")

    @ui.refreshable
    def standards_workspace() -> None:
        query_value = filters.get("standard_query", "")
        with ui.column().classes("w-full p-5 gap-4 simple-workspace"):
            with ui.row().classes("w-full items-start"):
                with ui.column().classes("gap-0 grow"):
                    ui.label("Normen & Standards").classes("text-2xl font-bold")
                    ui.label(
                        "Geltungsbereich, Zugriff, Dokumente und Requirements-Bezug an einer Stelle."
                    ).classes("subtle")
                ui.button(
                    "Norm / Standard", icon="add", on_click=lambda: standard_dialog(),
                ).props("no-caps")
            search = ui.input(
                "Suchen", value=query_value, placeholder="Bezeichnung, Titel oder Organisation",
            ).props("dense outlined clearable debounce=300").classes("w-full")

            def update_standard_filter(event) -> None:
                filters["standard_query"] = event.value or ""
                standards_workspace.refresh()

            search.on_value_change(update_standard_filter)
            matches = [
                item for item in package().standards
                if query_value.casefold() in (
                    f"{item.designation} {item.title} {item.organization} {item.description}"
                ).casefold()
            ]
            open_gaps = [
                item for item in package().requirements
                if item.standards_required and not _requirement_standard_count(item.id)
                and item.maturity not in {RequirementMaturity.REJECTED, RequirementMaturity.OBSOLETE}
            ]
            if open_gaps:
                with ui.row().classes("w-full items-center gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4"):
                    ui.icon("warning_amber", color="warning")
                    ui.label(
                        f"{len(open_gaps)} Requirements benötigen noch einen Normen- oder Standardbezug."
                    ).classes("text-sm font-semibold grow")
                    ui.button(
                        "Requirements anzeigen", icon="fact_check",
                        on_click=lambda: (
                            filters.update(standards="Open"),
                            switch_workspace("requirements"),
                        ),
                    ).props("flat dense no-caps")
            if not matches:
                with ui.column().classes("w-full items-center py-14 text-slate-500"):
                    ui.icon("gavel", size="54px")
                    ui.label("Noch keine passenden Normen oder Standards vorhanden.")
                return
            with ui.grid(columns=2).classes("w-full gap-3 standards-grid"):
                for standard in matches:
                    links = [
                        item for item in package().requirement_standard_links
                        if item.standard_id == standard.id
                    ]
                    sources = owner_sources(TechnicalSourceOwner.STANDARD, standard.id)
                    with ui.card().classes("w-full p-4 gap-2 border standard-card").on(
                        "click", lambda _, item=standard: select_standard(item.id)
                    ):
                        with ui.row().classes("w-full items-start gap-2"):
                            ui.icon("gavel", color="primary")
                            with ui.column().classes("gap-0 grow min-w-0"):
                                ui.label(standard.designation).classes("text-lg font-bold")
                                ui.label(standard.title or "Ohne ergänzenden Titel").classes("text-sm text-slate-600")
                            ui.badge(standard.applicability.value, color="purple-1").props("text-color=purple-9")
                        ui.label(
                            f"{standard.organization or 'Organisation offen'} · {standard.edition or 'Ausgabe offen'}"
                        ).classes("text-sm")
                        ui.label(
                            f"{len(links)} Requirement-Bezug/Bezüge · {len(sources)} Zugriffskanal/-kanäle"
                        ).classes("subtle")

    @ui.refreshable
    def contextual_navigator(space: str = "overview") -> None:
        with ui.column().classes("w-full p-3 gap-3 simple-navigator"):
            ui.label({
                "overview": "PROZESSÜBERSICHT",
                "documents": "QUELLEN & ANALYSE",
                "requirements": "REQUIREMENTS",
                "standards": "NORMEN & STANDARDS",
            }.get(space, "SYSTEMENTWICKLUNG")).classes("panel-heading")
            if space == "documents":
                ui.button(
                    "Dokumente hinzufügen", icon="add", on_click=document_import_dialog,
                ).props("outline dense no-caps align=left").classes("w-full")
                for document in package().source_documents:
                    ui.button(
                        document.name, icon="description",
                        on_click=lambda _, item=document: select_document(item.id),
                    ).props("flat dense no-caps align=left").classes("w-full navigator-document")
            elif space == "requirements":
                ui.button(
                    "Requirement hinzufügen", icon="add", on_click=lambda: requirement_dialog(),
                ).props("outline dense no-caps align=left").classes("w-full")
                branches = [
                    ("System", {RequirementClassification.SYSTEM}, "hub"),
                    ("HW / ECAD", {RequirementClassification.HARDWARE}, "memory"),
                    ("Mechanik / CAD", {RequirementClassification.MECHANICS}, "precision_manufacturing"),
                    ("Software / Firmware", {
                        RequirementClassification.SOFTWARE, RequirementClassification.FIRMWARE,
                    }, "code"),
                ]
                for label, classifications, icon in branches:
                    count = sum(item.classification in classifications for item in package().requirements)
                    with ui.button(
                        on_click=lambda _, values=classifications: (
                            filters.update(classification=(
                                next(iter(values)).value if len(values) == 1 else "Software / Firmware"
                            )),
                            requirements_workspace.refresh(),
                        ),
                    ).props("flat dense no-caps align=left").classes("w-full"):
                        ui.icon(icon, size="19px")
                        ui.label(label).classes("grow text-left")
                        ui.badge(str(count), color="grey-3").props("text-color=grey-9")
                review_count = sum(item.maturity in {
                    RequirementMaturity.DETECTED, RequirementMaturity.IN_REVIEW,
                } for item in package().requirements)
                if review_count:
                    ui.separator()
                    ui.button(
                        f"Zu prüfen · {review_count}", icon="rate_review",
                        on_click=lambda: (
                            filters.update(maturity=RequirementMaturity.DETECTED.value),
                            requirements_workspace.refresh(),
                        ),
                    ).props("flat dense no-caps align=left color=warning").classes("w-full")
            elif space == "standards":
                ui.button(
                    "Norm / Standard hinzufügen", icon="add", on_click=lambda: standard_dialog(),
                ).props("outline dense no-caps align=left").classes("w-full")
                for standard in package().standards:
                    ui.button(
                        standard.designation, icon="gavel",
                        on_click=lambda _, item=standard: select_standard(item.id),
                    ).props("flat dense no-caps align=left").classes("w-full")
            else:
                ui.label("Systembereiche").classes("text-xs font-bold uppercase text-slate-500")
                for label, target, icon in (
                    ("Quellen & Analyse", "documents", "description"),
                    ("Requirements", "requirements", "fact_check"),
                    ("HW / ECAD", "architecture", "memory"),
                    ("Mechanik / CAD", "mechanics", "precision_manufacturing"),
                    ("Software / Firmware", "software", "code"),
                    ("Normen & Standards", "standards", "gavel"),
                ):
                    ui.button(
                        label, icon=icon, on_click=lambda _, value=target: switch_workspace(value),
                    ).props("flat dense no-caps align=left").classes("w-full")

    @ui.refreshable
    def inspector() -> None:
        requirement = selected_requirement()
        component = selected_component()
        standard = selected_standard()
        verification_case = selected_verification()
        interface_requirement = selected_interface()
        realization = selected_realization()
        mechanical_component = selected_mechanical_component()
        software_component = selected_software_component()
        architecture=next((group[selection['architecture_id']] for group in project_objects(package()).values() if selection.get('architecture_id') in group),None)
        document = next((item for item in package().source_documents if item.id == selection["document_id"]), None)
        with ui.column().classes("w-full p-4 gap-3" + (" isd-requirement-detail" if requirement or architecture else "")):
            with ui.row().classes("w-full items-center gap-2"):
                ui.label("DETAILS").classes("panel-heading grow")
                ui.button(icon="close", on_click=lambda: ui.run_javascript(
                    "document.querySelector('.inspector')?.classList.remove("
                    "'isd-mobile-details-open','isd-requirements-inspector-open')"
                )).props("flat round dense aria-label=Details-schließen").classes("isd-mobile-details-btn")
            complete_object = next((item for item in (
                requirement, component, standard, verification_case,
                interface_requirement, realization, mechanical_component,
                software_component, document,
                architecture,
            ) if item is not None), None)
            if complete_object is not None:
                show_sha_identity(complete_object.id)
            if complete_object is not None and edit_all_fields is not None:
                pass
            if architecture:
                from .property_schema import KIND_LABELS
                from .attribute_spaces import render_attribute_spaces
                ui.label(architecture.name).classes('text-xl font-bold')
                ui.badge(KIND_LABELS.get(type(architecture).__name__,type(architecture).__name__))
                ui.label(getattr(architecture,'description','') or 'Beschreibung offen.').classes('text-sm leading-relaxed')
                if edit_all_fields and type(architecture).__name__!='FunctionElement':
                    ui.button('Objekt bearbeiten',icon='edit',on_click=lambda:edit_all_fields(architecture.id)).props('outline no-caps')
                if type(architecture).__name__=='FunctionElement':
                    ui.button('FE bearbeiten',icon='edit',on_click=lambda:function_element_dialog(architecture)).props('outline no-caps')
                    ui.label('ECAD: '+(architecture.source_sheet or 'Manuell')+' · '+(architecture.source_revision or 'Revision offen')).classes('text-xs break-all')
                    for r in package().technical_realizations:
                        if r.function_element_id==architecture.id:ui.button('Realisierung: '+r.name,on_click=lambda _,oid=r.id:select_realization(oid)).props('flat no-caps')
                render_attribute_spaces(architecture,save,package=package(),editable=False,edit_object=edit_all_fields)
                return
            if requirement:
                if effective_layer(requirement)==RequirementLevel.CUSTOMER:
                    from .requirements_navigation_ui import decision_label
                    ui.label('Kundenentscheidung: '+decision_label(requirement)).classes('font-semibold')
                system_elements = [e for e in package().system_elements if requirement.id in e.requirement_ids]
                for system_element in system_elements:
                    if open_system_element:
                        ui.button("Systemarchitektur: " + system_element.name, icon="account_tree",
                                  on_click=lambda _, sid=system_element.id: open_system_element(sid)).props("outline dense no-caps")
                    else:
                        ui.label("Systemarchitektur: " + system_element.name).classes("text-sm")
                trace = requirement_traceability_status(package(), requirement)
                from .traceability_ui import open_chain_dialog
                ui.button('Vollständige Requirementskette',icon='account_tree',on_click=lambda:open_chain_dialog(package(),requirement,select_requirement)).props('outline no-caps')
                evidence = evidence_status(package(), requirement)
                ui.label(requirement.title).classes("text-xl font-bold")
                with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                    ui.badge(
                        REQUIREMENT_LEVEL_LABELS[requirement.requirement_level.value],
                        color="indigo-1",
                    ).props("text-color=indigo-9")
                    ui.badge(requirement.classification.value, color="purple-2").props("text-color=purple-9")
                    ui.badge(requirement.category.value, color="blue-2").props("text-color=blue-9")
                    ui.badge(requirement.maturity.value, color="green-2" if requirement.maturity == RequirementMaturity.APPROVED else "amber-2").props("text-color=grey-9")
                    ui.badge(
                        COVERAGE_LABELS[trace.coverage.value],
                        color=(
                            "green-2" if trace.coverage == RequirementCoverageStatus.COVERED
                            else "red-2" if trace.coverage in {
                                RequirementCoverageStatus.REALIZATION_GAP,
                                RequirementCoverageStatus.CONFLICT,
                            }
                            else "amber-2"
                        ),
                    ).props("text-color=grey-9")
                    ui.badge(
                        VERIFICATION_STATE_LABELS[trace.verification.value],
                        color=(
                            "green-2" if trace.verification == RequirementVerificationState.PASSED
                            else "red-2" if trace.verification == RequirementVerificationState.FAILED
                            else "blue-1"
                        ),
                    ).props("text-color=grey-9")
                with ui.card().classes("w-full border p-3 gap-1"):
                    ui.label("Fachliche Reife · " + requirement.maturity.value).classes("text-sm")
                    ui.label("Lösungszuordnung · " + evidence.allocation).classes("text-sm")
                    ui.label("Bewertete Erfüllung · " + evidence.fulfillment).classes("text-sm")
                    ui.label("Verifikation · " + {
                        'Verified':'Nachweis gültig','Stale':'Nachweis erneut prüfen',
                        'Failed':'Test fehlgeschlagen','Blocked':'Test blockiert',
                        'Test Defined':'Test definiert','No Test':'Test fehlt',
                    }.get(evidence.verification,evidence.verification)).classes("text-sm")
                    for gap in evidence.gaps:
                        ui.label("Offen: " + gap).classes("text-xs text-amber-900")
                    path = trace_path(package(), requirement.id)
                    ui.label(f"Gespeicherter Pfad: {len(path['requirements'])} Requirements · "
                             f"{len(path['realizations'])} Realisierungen · "
                             f"{len(path['components'])} HW-Parts · "
                             f"{len(path['mechanical_components'])} Mechanik · "
                             f"{len(path['software_components'])} SW/FW · "
                             f"{len(path['tests'])} Tests").classes("text-xs text-slate-600")
                    with ui.row().classes("gap-2"):
                        ui.button("Erfüllung bewerten", on_click=lambda: assessment_dialog(requirement)).props("flat dense no-caps")
                        ui.button("Beziehung anlegen", on_click=lambda: relation_dialog(requirement)).props("flat dense no-caps")
                        ui.button("Bestandsbefund", on_click=lambda: observation_dialog(requirement)).props("flat dense no-caps")
                related_relations = [rel for rel in package().model_relations
                                     if rel.source_id == requirement.id or rel.target_id == requirement.id]
                viewed = next((rel for rel in package().model_relations if rel.id == selection["relation_id"]), None)
                if viewed:
                    with ui.card().classes("w-full border-2 border-teal-400 p-3"):
                        ui.label("Beziehung ansehen · " + viewed.kind).classes("font-semibold")
                        ui.label(f"{viewed.source_type} {viewed.source_id} → {viewed.target_type} {viewed.target_id}").classes("text-xs break-all")
                        ui.label("Begründung: " + (viewed.rationale or "—")).classes("text-sm")
                        ui.label("Status / Quelle: " + viewed.status + " · " + (viewed.source_locator or "—")).classes("text-xs")
                        if viewed.target_type == "Requirement":
                            ui.button("Zielobjekt fokussieren", on_click=lambda: select_requirement(viewed.target_id)).props("flat no-caps")
                        ui.button("Beziehungsdetails schließen", on_click=lambda: (selection.update(relation_id=None), inspector.refresh())).props("flat dense no-caps")
                if related_relations:
                    with ui.expansion(f"Explizite Beziehungen ({len(related_relations)})", value=False).classes("w-full"):
                        for rel in related_relations:
                            ui.button(f"Beziehung ansehen · {rel.kind} · {rel.id[:10]}",
                                      on_click=lambda _, item=rel: view_relation(item.id)).props("flat dense no-caps")
                ui.label(requirement.text).classes("text-sm leading-relaxed")
                from .attribute_spaces import render_attribute_spaces
                with ui.expansion('Fachliche Anforderungsattribute',icon='tune').classes('w-full border rounded-lg'):
                    render_attribute_spaces(requirement,save,'requirement_attributes',package(),editable=False)
                if requirement.solution_binding == RequirementSolutionBinding.IMPLEMENTATION_MANDATE:
                    ui.label(
                        "Verbindliche Umsetzungsvorgabe: konkrete Hardware und/oder Software darf nur gemäß "
                        "Substitutionsregel geändert werden."
                    ).classes("text-sm font-semibold text-red-900 bg-red-50 border border-red-200 rounded-lg p-3")
                with ui.expansion(
                    "Traceability & Erfüllung",
                    icon="route",
                    value=True,
                ).classes("w-full border rounded-lg"):
                    ui.label(
                        f"Technische Abdeckung: {COVERAGE_LABELS[trace.coverage.value]}"
                    ).classes("text-sm font-semibold")
                    ui.label(
                        f"Verifikation: {VERIFICATION_STATE_LABELS[trace.verification.value]}"
                    ).classes("text-sm font-semibold")
                    ui.label(
                        f"{len(trace.derived_requirement_ids)} abgeleitete Requirements · "
                        f"{trace.target_count} Umsetzungsobjekte · "
                        f"{len(trace.realization_ids)} technische Realisierungen"
                    ).classes("text-sm")
                    if trace.missing_disciplines:
                        ui.label(
                            "Fehlende fachliche Ableitungen: "
                            + ", ".join(item.value for item in trace.missing_disciplines)
                        ).classes("text-sm text-red-700")
                    if trace.open_conflict_count:
                        ui.label(
                            f"{trace.open_conflict_count} offener Umsetzungskonflikt"
                        ).classes("text-sm text-red-700")
                    if requirement.satisfaction_strategy:
                        ui.label(f"Strategie: {requirement.satisfaction_strategy}").classes("text-sm")
                    if requirement.direct_satisfaction_justification:
                        ui.label(
                            f"Direkterfüllung begründet: {requirement.direct_satisfaction_justification}"
                        ).classes("text-sm text-amber-800")
                with ui.expansion("Identifikation und Herkunft", icon="fingerprint", value=False).classes("w-full border rounded-lg"):
                    ui.label(f"Interne ID: {requirement.identifier or '—'}").classes("text-sm font-mono")
                    ui.label(f"Objekt-ID: {requirement.id}").classes("text-xs break-all")
                    ui.label(f"Externe Quell-ID: {requirement.external_id or '—'}").classes("text-sm")
                    ui.label(f"Herkunft: {requirement.origin.value}").classes("text-sm")
                    ui.label(
                        f"Quellart: {SOURCE_KIND_LABELS[requirement.source_kind.value]}"
                    ).classes("text-sm")
                    ui.label(
                        f"Anforderungsebene: {REQUIREMENT_LEVEL_LABELS[requirement.requirement_level.value]}"
                    ).classes("text-sm")
                    ui.label(
                        f"Lösungsbindung: {SOLUTION_BINDING_LABELS[requirement.solution_binding.value]}"
                    ).classes("text-sm")
                    ui.label(
                        f"Vertragliche Ebene: {SPECIFICATION_LEVEL_LABELS[requirement.specification_level.value]}"
                    ).classes("text-sm font-medium")
                    ui.label(f"Disziplin: {requirement.classification.value}").classes("text-sm")
                    ui.label(f"Kategorie: {requirement.category.value}").classes("text-sm")
                    ui.label(f"Priorität: {requirement.priority.value}").classes("text-sm")
                    ui.label(f"ECAD-Relevanz: {requirement.ecad_relevance.value}").classes("text-sm")
                    ui.label(
                        "Normative Absicherung: "
                        + ("erforderlich" if requirement.standards_required else "nicht explizit gefordert")
                    ).classes("text-sm")
                    if requirement.standard_hints:
                        ui.label(f"Normhinweise: {', '.join(requirement.standard_hints)}").classes("text-sm")
                    if requirement.standard_gap_note:
                        ui.label(f"Offener Normenpunkt: {requirement.standard_gap_note}").classes("text-sm text-amber-800")
                    if requirement.source_locator:
                        ui.label(f"Quelle: {requirement.source_locator}").classes("text-sm")
                links = [item for item in package().requirement_links if item.requirement_id == requirement.id]
                incoming_derivations = [
                    item for item in package().requirement_derivations
                    if item.derived_requirement_id == requirement.id
                ]
                outgoing_derivations = [
                    item for item in package().requirement_derivations
                    if item.source_requirement_id == requirement.id
                ]
                if incoming_derivations or outgoing_derivations:
                    with ui.expansion(
                        f"Requirement-Ableitungen ({len(incoming_derivations) + len(outgoing_derivations)})",
                        icon="call_split", value=True,
                    ).classes("w-full border rounded-lg"):
                        for derivation in incoming_derivations:
                            source_requirement = package().find_requirement(derivation.source_requirement_id)
                            if source_requirement:
                                ui.button(
                                    f"Abgeleitet aus {source_requirement.identifier} · {source_requirement.title}",
                                    on_click=lambda _, item=source_requirement: select_requirement(item.id),
                                ).props("flat dense no-caps align=left").classes("w-full")
                        for derivation in outgoing_derivations:
                            target_requirement = package().find_requirement(derivation.derived_requirement_id)
                            if target_requirement:
                                ui.button(
                                    f"Leitet ab: {target_requirement.identifier} · {target_requirement.title}",
                                    on_click=lambda _, item=target_requirement: select_requirement(item.id),
                                ).props("flat dense no-caps align=left").classes("w-full")
                with ui.expansion(
                    f"Weitere Modellbeziehungen ({len(links)})",
                    icon="account_tree", value=False,
                ).classes("w-full border rounded-lg"):
                    for link in links:
                        ui.label(
                            f"{link.relation.value}: {_requirement_target_label(link)}"
                        ).classes("text-sm")
                    ui.button("Zuordnungen bearbeiten", icon="link", on_click=lambda: allocation_dialog(requirement)).props("flat dense no-caps")
                direct_part_ids = {item.id for item in _requirement_parts(requirement.id)}
                direct_target_ids = {
                    (link.target_type, link.target_id) for link in links
                    if link.relation != RequirementRelation.VERIFIED_BY
                }
                requirement_realizations = [
                    item for item in package().technical_realizations
                    if requirement.id in item.requirement_ids or
                    (RequirementTargetType.TECHNICAL_REALIZATION, item.id) in direct_target_ids
                ]
                related_parts: dict[str, tuple[Any, str, Callable[[str], None], set[str]]] = {}
                for item in package().components:
                    if item.id in direct_part_ids:
                        related_parts["part:" + item.id] = (item, "Bauteil", select_component, {"Direkt zugeordnet"})
                for item in package().mechanical_components:
                    if requirement.id in item.requirement_ids or (
                        RequirementTargetType.MECHANICAL_COMPONENT, item.id
                    ) in direct_target_ids:
                        related_parts["mech:" + item.id] = (item, "Mechanik", select_mechanical_component, {"Direkt zugeordnet"})
                for item in package().software_components:
                    if requirement.id in item.requirement_ids or (
                        RequirementTargetType.SOFTWARE_COMPONENT, item.id
                    ) in direct_target_ids:
                        related_parts["sw:" + item.id] = (item, "SW / FW", select_software_component, {"Direkt zugeordnet"})
                part_sources = {
                    "part:": (package().find_component, "Bauteil", select_component),
                    "mech:": (package().find_mechanical_component, "Mechanik", select_mechanical_component),
                    "sw:": (package().find_software_component, "SW / FW", select_software_component),
                }
                for linked_realization in requirement_realizations:
                    for variant in linked_realization.variants:
                        member_keys = (["part:" + role.component_id for role in variant.component_roles]
                                       + ["mech:" + key for key in variant.mechanical_component_ids]
                                       + ["sw:" + key for key in variant.software_component_ids])
                        for key in member_keys:
                            prefix = key.split(":", 1)[0] + ":"
                            find, label, action = part_sources[prefix]
                            item = find(key.split(":", 1)[1])
                            if item is None:
                                continue
                            if key not in related_parts:
                                related_parts[key] = (item, label, action, set())
                            related_parts[key][3].add(f"{linked_realization.name} / {variant.name}")
                with ui.expansion(
                    f"Lösungsebene · {len(requirement_realizations)} Realisierungen, "
                    f"{len(related_parts)} Bauteile / Module",
                    icon="developer_board", value=bool(requirement_realizations or related_parts),
                ).classes("w-full border rounded-lg"):
                    ui.label("Technische Realisierungen").classes("font-bold text-sm")
                    for linked_realization in requirement_realizations:
                        with ui.row().classes("w-full items-center gap-2"):
                            ui.button(
                                linked_realization.name,
                                on_click=lambda _, item=linked_realization: select_realization(item.id),
                            ).props("flat dense no-caps align=left").classes("grow")
                            ui.badge(linked_realization.status.value, color="green-1" if linked_realization.status == TechnicalRealizationStatus.SELECTED else "amber-1").props("text-color=grey-9")
                        ui.label(f"{len(linked_realization.variants)} Varianten").classes("text-xs text-slate-500")
                    if not requirement_realizations:
                        ui.label("Noch keine Realisierung verknüpft.").classes("text-xs text-slate-500")
                    ui.label("Bauteile und Module").classes("font-bold text-sm mt-2")
                    for item, label, action, sources in sorted(related_parts.values(), key=lambda entry: entry[0].name.casefold()):
                        with ui.column().classes("w-full gap-0 border-b pb-2"):
                            ui.button(item.name, on_click=lambda _, key=item.id, target=action: target(key)).props(
                                "flat dense no-caps align=left"
                            ).classes("w-full")
                            ui.label(f"{label} · " + " · ".join(sorted(sources))).classes("text-xs text-slate-600")
                            if label == "Bauteil" and (item.legacy_ecad_reference or item.manufacturer_part_number):
                                ui.label(" · ".join(value for value in (
                                    item.legacy_ecad_reference, item.manufacturer_part_number
                                ) if value)).classes("text-xs font-mono text-slate-600")
                    if not related_parts:
                        ui.label("Noch keine direkten oder über Varianten zugeordneten Bauteile.").classes(
                            "text-xs text-slate-500"
                        )
                    ui.button(
                        "Technische Realisierung ableiten", icon="add",
                        on_click=lambda: realization_dialog(initial_requirement_id=requirement.id),
                    ).props("flat dense no-caps")
                    ui.button(
                        "Bauteil verknüpfen", icon="add_link",
                        on_click=lambda: component_dialog(initial_requirement_id=requirement.id),
                    ).props("flat dense no-caps")
                    source_document = next((
                        item for item in package().source_documents
                        if item.id == requirement.source_document_id
                    ), None)
                    if (
                        source_document
                        and requirement.maturity not in {
                            RequirementMaturity.REJECTED,
                            RequirementMaturity.OBSOLETE,
                        }
                        and document_context_available(source_document)
                    ):
                        ui.button(
                            "KI-Lösung aus Quelle ableiten",
                            icon="auto_awesome",
                            on_click=lambda: technical_derivation_dialog(
                                source_document, requirement.id
                            ),
                        ).props("flat dense no-caps")
                requirement_conflicts = [
                    item for item in package().engineering_conflicts
                    if requirement.id in item.requirement_ids
                ]
                with ui.expansion(
                    f"Umsetzungskonflikte ({len(requirement_conflicts)})",
                    icon="report_problem", value=bool(requirement_conflicts),
                ).classes("w-full border rounded-lg"):
                    for conflict in requirement_conflicts:
                        with ui.row().classes("w-full items-center gap-2"):
                            ui.button(
                                conflict.title,
                                on_click=lambda _, item=conflict: engineering_conflict_dialog(item),
                            ).props("flat dense no-caps align=left").classes("grow")
                            ui.badge(
                                CONFLICT_STATUS_LABELS[conflict.status.value],
                                color="green-2" if conflict.status in {
                                    EngineeringConflictStatus.RESOLVED,
                                    EngineeringConflictStatus.ACCEPTED_DEVIATION,
                                } else "amber-2",
                            ).props("text-color=grey-9")
                    ui.button(
                        "Konflikt erfassen", icon="add",
                        on_click=lambda: engineering_conflict_dialog(initial_requirement_id=requirement.id),
                    ).props("flat dense no-caps")
                standard_links = [
                    item for item in package().requirement_standard_links
                    if item.requirement_id == requirement.id
                ]
                with ui.expansion(
                    f"Normen & Standards ({len(standard_links)})",
                    icon="gavel",
                    value=bool(standard_links),
                ).classes("w-full border rounded-lg"):
                    for standard_link in standard_links:
                        linked_standard = package().find_standard(standard_link.standard_id)
                        if linked_standard is None:
                            continue
                        with ui.row().classes("w-full items-center gap-1"):
                            ui.button(
                                f"{linked_standard.designation}{' · ' + standard_link.clause if standard_link.clause else ''}",
                                on_click=lambda _, item=linked_standard: select_standard(item.id),
                            ).props("flat dense no-caps align=left").classes("grow")
                            ui.button(
                                icon="edit",
                                on_click=lambda _, item=standard_link: standard_link_dialog(requirement, item),
                            ).props("flat round dense")
                            def unlink(link_id=standard_link.id) -> None:
                                package().requirement_standard_links = [
                                    item for item in package().requirement_standard_links if item.id != link_id
                                ]
                                save("Normenbezug entfernt")
                            ui.button(icon="link_off", on_click=unlink).props("flat round dense color=negative")
                    ui.button(
                        "Norm oder Standard zuordnen",
                        icon="add_link",
                        on_click=lambda: standard_link_dialog(requirement),
                    ).props("flat dense no-caps")
                verification_cases = [
                    item for item in package().verification_cases
                    if requirement.id in item.requirement_ids
                    and item.execution_status != TestExecutionStatus.OBSOLETE
                ]
                with ui.expansion(
                    f"Requirement-Testdefinitionen ({len(verification_cases)})",
                    icon="science",
                    value=bool(verification_cases),
                ).classes("w-full border rounded-lg"):
                    for verification in verification_cases:
                        ui.button(
                            f"{verification.identifier} · {verification.title} · Definition {verification.definition_status.value}",
                            on_click=lambda _, item=verification: select_verification(item.id),
                        ).props("flat dense no-caps align=left").classes("w-full")
                    ui.button(
                        "Requirement-Test definieren",
                        icon="add",
                        on_click=lambda: verification_dialog(initial_requirement_id=requirement.id),
                    ).props("flat dense no-caps")
                if requirement.rationale:
                    with ui.expansion("Begründung", icon="psychology").classes("w-full border rounded-lg"):
                        ui.label(requirement.rationale).classes("text-sm")
                with ui.row().classes("w-full gap-2"):
                    if requirement.maturity in {
                        RequirementMaturity.DETECTED,
                        RequirementMaturity.IN_REVIEW,
                    }:
                        ui.button(
                            "Bestätigen", icon="verified",
                            on_click=lambda: _set_requirement_maturity(
                                requirement, RequirementMaturity.APPROVED
                            ),
                        ).props("dense no-caps")
                        ui.button(
                            "Verwerfen", icon="block",
                            on_click=lambda: _set_requirement_maturity(
                                requirement, RequirementMaturity.REJECTED
                            ),
                        ).props("outline dense no-caps color=negative")
                    ui.button("Bearbeiten", icon="edit", on_click=lambda: requirement_dialog(requirement)).props("outline dense no-caps")
                    ui.button("Löschen", icon="delete_outline", on_click=lambda: confirm_requirement_delete(requirement)).props("outline dense no-caps color=negative")
            elif realization:
                ui.label(realization.name).classes("text-xl font-bold")
                if len(realization.variants) < 2:
                    ui.label("Alternativensuche offen · weitere Kandidaten mit Datenblatt-/Application-Note-Belegen prüfen.").classes("text-xs text-amber-800")
                ui.label(realization.generic_function or "Generische Funktion offen").classes("text-sm text-slate-600")
                ui.badge(realization.status.value, color="green-2" if realization.status == TechnicalRealizationStatus.SELECTED else "amber-2").props("text-color=grey-9")
                realization_requirement_ids = set(realization.requirement_ids) | {
                    link.requirement_id for link in package().requirement_links
                    if link.target_type == RequirementTargetType.TECHNICAL_REALIZATION
                    and link.target_id == realization.id
                    and link.relation != RequirementRelation.VERIFIED_BY
                }
                with ui.expansion("Begründende Requirements", icon="fact_check", value=True).classes("w-full border rounded-lg"):
                    if not realization_requirement_ids:
                        ui.label("Noch keinem Requirement zugeordnet.").classes("text-sm text-amber-800")
                    for requirement_id in sorted(realization_requirement_ids):
                        linked = package().find_requirement(requirement_id)
                        if linked:
                            ui.button(
                                f"{linked.identifier} · {linked.title}",
                                on_click=lambda _, item=linked: select_requirement(item.id),
                            ).props("flat dense no-caps align=left").classes("w-full")
                with ui.expansion(f"Lösungsvarianten ({len(realization.variants)})", icon="account_tree", value=True).classes("w-full border rounded-lg"):
                    for variant in realization.variants:
                        with ui.column().classes("w-full gap-1 border-b py-2"):
                            with ui.row().classes("w-full items-center"):
                                ui.label(variant.name).classes("font-semibold grow")
                                ui.badge(
                                    "Ausgewählt" if realization.selected_variant_id == variant.id else variant.status.value,
                                    color="green-2" if realization.selected_variant_id == variant.id else "grey-3",
                                ).props("text-color=grey-9")
                            for role in variant.component_roles:
                                from .realization_service import core_component_ids
                                if role.component_id not in core_component_ids(package(),variant):continue
                                linked_component = package().find_component(role.component_id)
                                if linked_component:
                                    ui.button(
                                        f"{role.role.value}: {linked_component.name}",
                                        on_click=lambda _, item=linked_component: select_component(item.id),
                                    ).props("flat dense no-caps align=left")
                            ui.label(f"Interfaces: {len(variant.interface_requirement_ids)} · Normen: {len(variant.standard_ids)}").classes("subtle")
                element_result = package().find_element(realization.architecture_element_id or "")
                with ui.expansion("Architekturzuordnung", icon="schema", value=True).classes("w-full border rounded-lg"):
                    if element_result:
                        ui.label(f"{element_result[0].name} / {element_result[1].name}").classes("font-semibold")
                        ui.label("Das Architecture Element bleibt generisch; die Auswahl ist als technische Referenz im Attribut gespeichert.").classes("text-sm text-slate-600")
                    else:
                        ui.label("Noch keinem Architecture Element zugeordnet.").classes("text-sm text-amber-700")
                with ui.row().classes("w-full gap-2"):
                    ui.button("Bearbeiten", icon="edit", on_click=lambda: realization_dialog(realization)).props("outline dense no-caps")
                    ui.button("Löschen", icon="delete_outline", on_click=lambda: confirm_realization_delete(realization)).props("outline dense no-caps color=negative")
            elif component:
                ui.label(component.name).classes("text-xl font-bold")
                ui.button('Bauteil, Alternativen und Nachweise öffnen',icon='open_in_new',on_click=lambda:component_details(component)).props('outline no-caps')
                with ui.row().classes("w-full gap-2"):
                    ui.badge(
                        "Physikalisches Bauteil"
                        if component.representation == ComponentRepresentation.PHYSICAL
                        else "Logische Komponente",
                        color="teal-2",
                    ).props("text-color=teal-9")
                    ui.badge(component.decision_type.value, color="purple-2").props("text-color=purple-9")
                ui.label(component.component_type).classes("text-sm")
                ui.label(" · ".join(item for item in [component.manufacturer, component.manufacturer_part_number] if item) or "Keine konkrete Herstellerkomponente").classes("text-sm text-slate-600")
                if component.legacy_ecad_reference:
                    ui.label(f"Legacy-ECAD-Reference: {component.legacy_ecad_reference}").classes("text-xs text-slate-500")
                with ui.expansion("Designentscheidung", icon="rule", value=True).classes("w-full border rounded-lg"):
                    ui.label(f"Verifikation: {component.verification.value}").classes("text-sm")
                    ui.label(f"Anzahl: {component.quantity}").classes("text-sm")
                    ui.label(
                        f"Lifecycle: {COMPONENT_LIFECYCLE_LABELS.get(component.lifecycle.value, component.lifecycle.value)}"
                    ).classes("text-sm")
                    ui.label(f"Gehäuse / Package: {component.package_name or '—'}").classes("text-sm")
                    ui.label(
                        f"Lieferant / Bestellnummer: "
                        f"{' · '.join(item for item in [component.supplier, component.supplier_part_number] if item) or '—'}"
                    ).classes("text-sm")
                    if component.rationale:
                        ui.label(component.rationale).classes("text-sm")
                component_requirement_ids = set(component.requirement_ids) | {
                    link.requirement_id for link in package().requirement_links
                    if link.target_type == RequirementTargetType.COMPONENT
                    and link.target_id == component.id
                    and link.relation != RequirementRelation.VERIFIED_BY
                }
                with ui.expansion(
                    f"Direkt zugeordnete Requirements ({len(component_requirement_ids)})",
                    icon="fact_check", value=True,
                ).classes("w-full border rounded-lg"):
                    if not component_requirement_ids:
                        ui.label("Bestand ohne Requirement-Zuordnung.").classes("text-sm text-amber-800")
                    for requirement_id in sorted(component_requirement_ids):
                        linked_requirement = package().find_requirement(requirement_id)
                        if linked_requirement:
                            ui.button(
                                f"{linked_requirement.identifier} · {linked_requirement.title}",
                                on_click=lambda _, item=linked_requirement: select_requirement(item.id),
                            ).props("flat dense no-caps align=left").classes("w-full")
                    ui.button(
                        "Requirements verknüpfen", icon="add_link",
                        on_click=lambda: component_dialog(component),
                    ).props("flat dense no-caps")
                used_in = [
                    item for item in package().technical_realizations
                    if any(role.component_id == component.id
                           for variant in item.variants for role in variant.component_roles)
                ]
                if used_in:
                    with ui.expansion(f"Verwendet in Realisierungen ({len(used_in)})",
                                      icon="developer_board", value=True).classes("w-full border rounded-lg"):
                        for linked_realization in used_in:
                            ui.button(linked_realization.name,
                                      on_click=lambda _, key=linked_realization.id: select_realization(key)).props(
                                "flat dense no-caps align=left"
                            ).classes("w-full")
                linked_component_needs = [
                    item for item in package().component_requirements
                    if item.id in component.component_requirement_ids
                ]
                with ui.expansion(
                    f"Technische Eignung ({len(linked_component_needs)} Kriteriengruppen)",
                    icon="fact_check", value=bool(linked_component_needs or component.qualification),
                ).classes("w-full border rounded-lg"):
                    for need in linked_component_needs:
                        ui.label(need.name).classes("font-semibold")
                        for key, value in need.criteria.items():
                            ui.label(f"{key}: {value}").classes("text-sm")
                    if component.qualification:
                        ui.separator()
                        ui.label("Eignungsmatrix / Nachweise").classes("font-semibold")
                        for key, value in component.qualification.items():
                            ui.label(f"{key}: {value}").classes("text-sm")
                with ui.expansion(
                    f"Datenblätter, Application Notes & Quellen ({len(owner_sources(TechnicalSourceOwner.COMPONENT, component.id))})",
                    icon="library_books",
                    value=True,
                ).classes("w-full border rounded-lg"):
                    render_technical_sources(
                        TechnicalSourceOwner.COMPONENT,
                        component.id,
                        component.name,
                    )
                linked_interfaces = [
                    item for item in package().interface_requirements
                    if item.id in component.interface_requirement_ids
                ]
                with ui.expansion(
                    f"Verwendete Interfaces ({len(linked_interfaces)})",
                    icon="hub", value=bool(linked_interfaces),
                ).classes("w-full border rounded-lg"):
                    for linked_interface in linked_interfaces:
                        ui.button(
                            linked_interface.name,
                            on_click=lambda _, item=linked_interface: select_interface(item.id),
                        ).props("flat dense no-caps align=left").classes("w-full")
                ui.button("Bearbeiten", icon="edit", on_click=lambda: component_dialog(component)).props("outline dense no-caps")
            elif mechanical_component or software_component:
                item = mechanical_component or software_component
                is_mechanical = mechanical_component is not None
                target_type = (RequirementTargetType.MECHANICAL_COMPONENT if is_mechanical
                               else RequirementTargetType.SOFTWARE_COMPONENT)
                ui.label(item.name).classes("text-xl font-bold")
                ui.badge("Mechanische Komponente" if is_mechanical else "SW-/FW-Modul",
                         color="teal-2").props("text-color=teal-9")
                ui.label(item.description or item.kind.value).classes("text-sm text-slate-600")
                assigned_ids = set(item.requirement_ids) | {
                    link.requirement_id for link in package().requirement_links
                    if link.target_type == target_type and link.target_id == item.id
                    and link.relation != RequirementRelation.VERIFIED_BY
                }
                with ui.expansion(f"Zugeordnete Requirements ({len(assigned_ids)})",
                                  icon="fact_check", value=True).classes("w-full border rounded-lg"):
                    if not assigned_ids:
                        ui.label("Bestand ohne Requirement-Zuordnung.").classes("text-sm text-amber-800")
                    for requirement_id in sorted(assigned_ids):
                        linked = package().find_requirement(requirement_id)
                        if linked:
                            ui.button(f"{linked.identifier} · {linked.title}",
                                      on_click=lambda _, key=linked.id: select_requirement(key)).props(
                                "flat dense no-caps align=left"
                            ).classes("w-full")
                ui.button("Fachbereich öffnen", icon="open_in_new", on_click=lambda: switch_workspace(
                    "mechanics" if is_mechanical else "software"
                )).props("outline dense no-caps")
            elif interface_requirement:
                ui.label(interface_requirement.name).classes("text-xl font-bold")
                with ui.row().classes("w-full gap-2 flex-wrap"):
                    ui.badge(interface_requirement.interface_class.value, color="indigo-2").props("text-color=indigo-9")
                    ui.badge(interface_requirement.family, color="blue-2").props("text-color=blue-9")
                    ui.badge(interface_requirement.topology, color="teal-2").props("text-color=teal-9")
                    ui.badge(interface_requirement.maturity.value, color="amber-2").props("text-color=grey-9")
                    if interface_requirement.standards_required and not interface_requirement.standard_ids:
                        ui.badge("Standard offen", color="red-2").props("text-color=red-9")
                ui.label(
                    f"{interface_requirement.host_role or 'Host offen'} → "
                    f"{', '.join(interface_requirement.participant_roles) or 'Teilnehmer offen'}"
                ).classes("text-sm")
                with ui.expansion("Technische Definition", icon="tune", value=True).classes("w-full border rounded-lg"):
                    for label, value in (
                        ("Protokoll", interface_requirement.protocol),
                        ("Port Type", interface_requirement.port_type),
                        ("Signaltyp", interface_requirement.signal_type.value),
                        ("Verbindung", interface_requirement.connection_type.value),
                        ("Datenrate", interface_requirement.data_rate),
                        ("Spannung / Pegel", interface_requirement.voltage),
                        ("Isolation", interface_requirement.isolation),
                        ("Safety / Redundanz", interface_requirement.safety_redundancy),
                        ("Medium / Stecker", interface_requirement.medium_connector),
                        ("Interfacevorlage", interface_requirement.interface_template),
                        ("Provider", interface_requirement.provider),
                        ("Consumer", interface_requirement.consumer),
                    ):
                        ui.label(f"{label}: {value or '—'}").classes("text-sm")
                    for label, values in (
                        ("Physische Eigenschaften", interface_requirement.physical_properties),
                        ("Protokolleigenschaften", interface_requirement.protocol_properties),
                    ):
                        if values:
                            ui.label(f"{label}: " + " · ".join(f"{key}={value}" for key, value in values.items())).classes("text-sm")
                with ui.expansion(
                    f"Gekoppelte Layer ({len(interface_requirement.linked_layer_ids)})",
                    icon="link", value=bool(interface_requirement.linked_layer_ids),
                ).classes("w-full border rounded-lg"):
                    for interface_id in interface_requirement.linked_layer_ids:
                        linked_interface = package().find_interface_requirement(interface_id)
                        if linked_interface:
                            ui.button(
                                f"{linked_interface.interface_class.value} · {linked_interface.name}",
                                on_click=lambda _, item=linked_interface: select_interface(item.id),
                            ).props("flat dense no-caps align=left").classes("w-full")
                with ui.expansion(
                    f"Begründende Requirements ({len(interface_requirement.requirement_ids)})",
                    icon="fact_check", value=True,
                ).classes("w-full border rounded-lg"):
                    for requirement_id in interface_requirement.requirement_ids:
                        linked_requirement = package().find_requirement(requirement_id)
                        if linked_requirement:
                            ui.button(
                                f"{linked_requirement.identifier} · {linked_requirement.title}",
                                on_click=lambda _, item=linked_requirement: select_requirement(item.id),
                            ).props("flat dense no-caps align=left").classes("w-full")
                with ui.expansion(
                    f"Komponenten ({len(interface_requirement.component_ids)})",
                    icon="memory", value=True,
                ).classes("w-full border rounded-lg"):
                    for component_id in interface_requirement.component_ids:
                        linked_component = package().find_component(component_id)
                        if linked_component:
                            ui.button(
                                linked_component.name,
                                on_click=lambda _, item=linked_component: select_component(item.id),
                            ).props("flat dense no-caps align=left").classes("w-full")
                with ui.expansion(
                    f"Normen & Standards ({len(interface_requirement.standard_ids)})",
                    icon="gavel", value=True,
                ).classes("w-full border rounded-lg"):
                    for standard_id in interface_requirement.standard_ids:
                        linked_standard = package().find_standard(standard_id)
                        if linked_standard:
                            ui.button(
                                linked_standard.designation,
                                on_click=lambda _, item=linked_standard: select_standard(item.id),
                            ).props("flat dense no-caps align=left").classes("w-full")
                with ui.expansion(
                    f"Technische Quellen ({len(owner_sources(TechnicalSourceOwner.INTERFACE, interface_requirement.id))})",
                    icon="library_books", value=True,
                ).classes("w-full border rounded-lg"):
                    render_technical_sources(
                        TechnicalSourceOwner.INTERFACE,
                        interface_requirement.id,
                        interface_requirement.name,
                    )
                with ui.row().classes("w-full gap-2"):
                    ui.button(
                        "Bearbeiten", icon="edit",
                        on_click=lambda: interface_requirement_dialog(interface_requirement),
                    ).props("outline dense no-caps").mark('edit-interface-'+interface_requirement.id)
                    ui.button(
                        "Löschen", icon="delete_outline",
                        on_click=lambda: confirm_interface_delete(interface_requirement),
                    ).props("outline dense no-caps color=negative")
            elif verification_case:
                ui.label(verification_case.title).classes("text-xl font-bold")
                ui.label(verification_case.identifier).classes("text-sm font-mono text-slate-600")
                with ui.row().classes("w-full gap-2"):
                    ui.badge(verification_case.method.value, color="blue-2").props("text-color=blue-9")
                    ui.badge(
                        f"Definition: {verification_case.definition_status.value}",
                        color="green-2" if is_test_defined(verification_case) else "amber-2",
                    ).props("text-color=grey-9")
                    ui.badge(
                        f"Ausführung: {verification_case.execution_status.value}",
                        color="green-2" if test_has_evidence(verification_case,package()) else "amber-2",
                    ).props("text-color=grey-9")
                if verification_case.execution_status == TestExecutionStatus.PASSED and not test_has_evidence(verification_case,package()):
                    ui.label("Nachweis erneut prüfen: Der geprüfte Stand oder der vollständige Ergebnisnachweis fehlt.").classes("text-sm text-amber-800")
                if verification_case.objective:
                    ui.label(verification_case.objective).classes("text-sm leading-relaxed")
                with ui.expansion("Abgedeckte Requirements", icon="fact_check", value=True).classes("w-full border rounded-lg"):
                    for requirement_id in verification_case.requirement_ids:
                        linked_requirement = package().find_requirement(requirement_id)
                        if linked_requirement:
                            ui.button(
                                f"{linked_requirement.identifier} · {linked_requirement.title}",
                                on_click=lambda _, item=linked_requirement: select_requirement(item.id),
                            ).props("flat dense no-caps align=left").classes("w-full")
                with ui.expansion("Prüfdefinition", icon="rule", value=True).classes("w-full border rounded-lg"):
                    ui.label(f"Verfahren: {verification_case.procedure or '—'}").classes("text-sm")
                    ui.label(f"Erwartetes Ergebnis: {verification_case.expected_result or '—'}").classes("text-sm")
                    ui.label(f"Evidenz: {verification_case.evidence_reference or '—'}").classes("text-sm")
                    ui.label(f"Tatsächliches Ergebnis: {verification_case.actual_result or '—'}").classes("text-sm")
                    ui.label(f"Geprüfte Revision / Konfiguration: {verification_case.verified_revision or '—'} / {verification_case.configuration_reference or '—'}").classes("text-sm")
                with ui.row().classes("w-full gap-2"):
                    ui.button("Bearbeiten", icon="edit", on_click=lambda: verification_dialog(verification_case)).props("outline dense no-caps")
                    ui.button("Löschen", icon="delete_outline", on_click=lambda: confirm_verification_delete(verification_case)).props("outline dense no-caps color=negative")
            elif standard:
                ui.label(standard.designation).classes("text-xl font-bold")
                if standard.title:
                    ui.label(standard.title).classes("text-sm leading-relaxed")
                ui.badge(standard.applicability.value, color="purple-2").props("text-color=purple-9")
                with ui.expansion("Normeninformation", icon="gavel", value=True).classes("w-full border rounded-lg"):
                    ui.label(f"Organisation: {standard.organization or '—'}").classes("text-sm")
                    ui.label(f"Ausgabe / Jahr: {standard.edition or '—'}").classes("text-sm")
                    ui.label(f"Sprache: {standard.language or '—'}").classes("text-sm")
                    ui.label(f"Publikationsstatus: {standard.publication_status or '—'}").classes("text-sm")
                    ui.label(f"Gültig seit: {standard.effective_date or '—'}").classes("text-sm")
                    ui.label(f"Zugriffsklasse: {SOURCE_ACCESS_LABELS.get(standard.access_class.value, standard.access_class.value)}").classes("text-sm")
                    if standard.source_url:
                        ui.link("Primäre Referenz öffnen", standard.source_url, new_tab=True).classes("text-sm")
                    else:
                        ui.label("Primäre Referenz: —").classes("text-sm")
                    if standard.description:
                        ui.label(standard.description).classes("text-sm")
                standard_links = [
                    item for item in package().requirement_standard_links
                    if item.standard_id == standard.id
                ]
                with ui.expansion(f"Verknüpfte Requirements ({len(standard_links)})", icon="fact_check", value=True).classes("w-full border rounded-lg"):
                    for link in standard_links:
                        linked_requirement = package().find_requirement(link.requirement_id)
                        if linked_requirement:
                            ui.button(
                                f"{linked_requirement.identifier} · {linked_requirement.title}{' · ' + link.clause if link.clause else ''}",
                                on_click=lambda _, item=linked_requirement: select_requirement(item.id),
                            ).props("flat dense no-caps align=left").classes("w-full")
                with ui.expansion(
                    f"Zugriffskanäle & Dokumente ({len(owner_sources(TechnicalSourceOwner.STANDARD, standard.id))})",
                    icon="source",
                    value=True,
                ).classes("w-full border rounded-lg"):
                    render_technical_sources(
                        TechnicalSourceOwner.STANDARD,
                        standard.id,
                        standard.designation,
                    )
                with ui.row().classes("w-full gap-2"):
                    ui.button("Bearbeiten", icon="edit", on_click=lambda: standard_dialog(standard)).props("outline dense no-caps")
                    ui.button("Löschen", icon="delete_outline", on_click=lambda: confirm_standard_delete(standard)).props("outline dense no-caps color=negative")
            elif document:
                ui.label(document.name).classes("text-xl font-bold")
                ui.label(document.file_name).classes("text-sm")
                ui.badge(document.analysis_status.value, color="green-2").props("text-color=green-9")
                document_type = str(document.properties.get("documentType") or "").strip()
                document_context = str(document.properties.get("documentContext") or "").strip()
                if document_type:
                    ui.badge(document_type, color="blue-1").props("text-color=blue-9")
                if document_context:
                    with ui.expansion("Rolle / Kontext", icon="assignment", value=True).classes("w-full border rounded-lg"):
                        ui.label(document_context).classes("text-sm")
                ui.badge(
                    "Extrahierter Kontext verfügbar" if document_context_available(document) else "Extrahierter Kontext nicht verfügbar",
                    color="teal-1" if document_context_available(document) else "red-1",
                ).props("text-color=teal-9" if document_context_available(document) else "text-color=red-9")
                ui.label(f"{document.character_count} Zeichen · {document.page_count or '—'} Seiten").classes("subtle")
                ui.label(f"Analyse: {document.analysis_provider} · {document.analysis_model}").classes("text-sm")
                analysis = active_document_analysis(document.id)
                if analysis:
                    if analysis.properties.get('assistantIntegrationOrder'):
                        ui.button('KI-Integrationsänderungen prüfen',icon='difference',on_click=lambda aid=analysis.id:review_integration(aid)).props('outline no-caps')
                    ui.label(
                        f"Analyse R{analysis.revision_number}: {len(analysis.requirements)} Requirements · "
                        f"{len(analysis.interfaces)} Interfaces · {len(analysis.component_needs)} Komponentenanforderungen · "
                        f"{len(analysis.components)} Komponenten/A-Parts · {len(analysis.standards)} Normen · "
                        f"{len(analysis.technical_realizations)} Realisierungen · {len(analysis.verification_cases)} Testdefinitionen"
                    ).classes("text-sm font-medium")
                    committed = sum(
                        bool(item.committed_object_id)
                        for group in (
                            analysis.requirements, analysis.interfaces, analysis.component_needs,
                            analysis.components, analysis.standards, analysis.technical_realizations,
                            analysis.verification_cases,
                        )
                        for item in group
                    )
                    ui.label(f"{committed} Kandidat(en) in das Projektmodell übernommen").classes("subtle")
                else:
                    linked_requirements = [item for item in package().requirements if item.source_document_id == document.id]
                    linked_components = [item for item in package().components if item.source_document_id == document.id]
                    ui.label(
                        f"Legacy-Ergebnis: {len(linked_requirements)} Requirements · {len(linked_components)} Komponenten"
                    ).classes("text-sm font-medium")
                if document.analysis_prompt:
                    with ui.expansion("Analyseauftrag", icon="chat").classes("w-full border rounded-lg"):
                        ui.label(document.analysis_prompt).classes("text-sm")
                if document.open_questions:
                    with ui.expansion(
                        f"Offene Fragen ({len(document.open_questions)})",
                        icon="help_outline",
                        value=True,
                    ).classes("w-full border rounded-lg"):
                        for question in document.open_questions:
                            ui.label(f"• {question}").classes("text-sm")
                ui.label(f"SHA-256: {document.checksum_sha256}").classes("text-xs break-all")
                if attachment_is_available(package().project.id, document.attachment_path):
                    ui.button(
                        "Originaldokument herunterladen", icon="download",
                        on_click=lambda: ui.download(
                            read_attachment(package().project.id, document.attachment_path),
                            document.file_name,
                            media_type=document.media_type,
                        ),
                    ).props("outline dense no-caps")
                if document_context_available(document):
                    ui.button(
                        "Inhalt & KI-Kontext anzeigen",
                        icon="article",
                        on_click=lambda: open_document_context_dialog(document),
                    ).props("outline dense no-caps")
                else:
                    ui.button(
                        "Originaldokument / Kontext nachreichen",
                        icon="attach_file",
                        on_click=lambda: document_context_recovery_dialog(document),
                    ).props("outline dense no-caps")
                ui.label("Das SPOT-JSON enthält nur das Dokumentmanifest; der Binärinhalt bleibt in der projektbezogenen Ablage.").classes("text-sm text-slate-600")
            else:
                with ui.column().classes("w-full items-center text-center py-12 text-slate-400"):
                    ui.icon("touch_app", size="52px")
                    ui.label("Wähle ein Requirement, eine technische Realisierung, ein Dokument, eine Komponente, Norm oder Testdefinition aus.")

    def refresh(*, include_details: bool = True) -> None:
        overview_workspace.refresh()
        documents_workspace.refresh()
        requirements_workspace.refresh()
        standards_workspace.refresh()
        if include_details:inspector.refresh()

    from .technical_sources_ui import create_technical_sources_ui
    technical_sources_ui_views = create_technical_sources_ui(
        package=package,
        save=save,
    )
    owner_sources = technical_sources_ui_views.owner_sources
    render_technical_sources = technical_sources_ui_views.render_technical_sources

    from .realization_dialogs_ui import create_realization_dialogs_ui
    realization_dialogs_ui_views = create_realization_dialogs_ui(
        clear_selection=clear_selection,
        owner_sources=owner_sources,
        package=package,
        page_state=page_state,
        render_technical_sources=render_technical_sources,
        reset=reset,
        save=save,
        selection=selection,
    )
    component_dialog = realization_dialogs_ui_views.component_dialog
    component_details = realization_dialogs_ui_views.component_details
    function_element_dialog = realization_dialogs_ui_views.function_element_dialog
    realization_dialog = realization_dialogs_ui_views.realization_dialog
    confirm_realization_delete = realization_dialogs_ui_views.confirm_realization_delete

    from .requirements_edit_ui import create_requirements_edit_ui
    requirements_edit_ui_views = create_requirements_edit_ui(
        clear_selection=clear_selection,
        package=package,
        reset=reset,
        save=save,
        selection=selection,
        view_relation=view_relation,
    )
    requirement_dialog = requirements_edit_ui_views.requirement_dialog
    engineering_conflict_dialog = requirements_edit_ui_views.engineering_conflict_dialog
    allocation_dialog = requirements_edit_ui_views.allocation_dialog
    confirm_requirement_delete = requirements_edit_ui_views.confirm_requirement_delete
    relation_dialog = requirements_edit_ui_views.relation_dialog
    observation_dialog = requirements_edit_ui_views.observation_dialog
    assessment_dialog = requirements_edit_ui_views.assessment_dialog

    from .document_analysis_ui import create_document_analysis_ui
    document_analysis_ui_views = create_document_analysis_ui(
        active_document_analysis=active_document_analysis,
        ai_provider=ai_provider,
        analysis_queue=analysis_queue,
        clear_selection=clear_selection,
        configure_ai=configure_ai,
        filters=filters,
        import_batch=import_batch,
        import_jobs=import_jobs,
        package=package,
        page_state=page_state,
        refresh=refresh,
        save=save,
        selection=selection,
        set_job=set_job,
    )
    document_context_available = document_analysis_ui_views.document_context_available
    load_document_context = document_analysis_ui_views.load_document_context
    build_ai_document_context = document_analysis_ui_views.build_ai_document_context
    open_document_context_dialog = document_analysis_ui_views.open_document_context_dialog
    document_import_dialog = document_analysis_ui_views.document_import_dialog
    document_context_recovery_dialog = document_analysis_ui_views.document_context_recovery_dialog

    from .assistant_ui import create_assistant_ui
    assistant_ui_views = create_assistant_ui(
        accept_all_proposal=accept_all_proposal,
        accept_proposal=accept_proposal,
        ai_provider=ai_provider,
        architecture_catalog=architecture_catalog,
        build_ai_document_context=build_ai_document_context,
        builtins=builtins,
        clear_selection=clear_selection,
        configure_ai=configure_ai,
        create_safety_revision=create_safety_revision,
        document_context_available=document_context_available,
        filters=filters,
        generate_proposal=generate_proposal,
        load_ai_chat=load_ai_chat,
        load_document_context=load_document_context,
        package=package,
        page_state=page_state,
        reject_ai_review_dialog=reject_ai_review_dialog,
        reject_proposal_dialog=reject_proposal_dialog,
        review_integration=review_integration,
        save=save,
        selected_component=selected_component,
        selected_interface=selected_interface,
        selected_requirement=selected_requirement,
        selection=selection,
        set_ai_review_status=set_ai_review_status,
        set_job=set_job,
        store_ai_chat=store_ai_chat,
        update_ai_chat=update_ai_chat,
    )
    open_ai_assistant = assistant_ui_views.open_ai_assistant

    return RequirementsViews(
        navigator=contextual_navigator,
        overview_workspace=overview_workspace,
        documents_workspace=documents_workspace,
        requirements_workspace=requirements_workspace,
        standards_workspace=standards_workspace,
        inspector=inspector,
        refresh=refresh,
        reset=reset,
        select_requirement=select_requirement,
        select_realization=select_realization,
        edit_realization=realization_dialog,
        create_requirement_for_target=requirement_dialog,
        open_ai_assistant=open_ai_assistant,
        job_status=job_status,
        record_navigation=remember_navigation,
        component_details=component_details,
        edit_function_element=function_element_dialog,
        select_architecture=select_architecture,
        edit_component=lambda component=None:component_dialog(component,initial_system_defining=True if component is None else None),
        help_context=lambda: HelpContext('requirements',next((o for group in project_objects(package()).values() for i,o in group.items() if i in {v for v in selection.values() if v}),None),filters.get('display_mode','list')),
    )

__all__ = ["RequirementsViews", "create_requirements_views", "format_assistant_entry_for_copy"]
