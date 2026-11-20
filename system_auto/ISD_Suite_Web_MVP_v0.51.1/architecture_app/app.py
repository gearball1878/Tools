from __future__ import annotations
from .ai_ui import open_ai_configuration

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from nicegui import app, events, ui
from pydantic import ValidationError

from . import __version__
from .ai_provider import build_ai_provider
from .analysis_queue import DocumentAnalysisQueue
from .architecture_catalog import ArchitectureCatalog
from .attachment_store import delete_project_attachments
from .bus_content import BusContentTemplates
from .credentials import AICredentialStore
from .deletion import delete_object, deletion_impact
from .diagram import architecture_svg
from .hardware_topology import block_port_visible
from .architecture_pdf import export_architecture_pdf
from .requirements_exchange_ui import open_requirements_exchange_dialog
from .development_ui import create_development_views
from .system_architecture import create_architecture_views
from .attribute_spaces import render_attribute_spaces
from .ecad_ui import open_ecad_dialog
from .help_ui import open_help_dialog
from .identity import show_sha_identity
from .models import ArchitectureElement, ArchitecturePackage, ArchitectureSignal, Connection, Domain, InterfacePort, ProjectWorkflow, Signal, SignalEndpoint, SignalType, demo_package, utc_now
from .repository import ArchitectureRepository, VersionConflict
from .project_import_ui import open_project_import_dialog
from .package_preparation import prepare_package as prepare_saved_package
from .requirements_ui import create_requirements_views
from .topology import synchronize_signal_topology
from .xpedition_adapter import export_buscontents_text


PIN_TYPES = ["IN", "OUT", "BI", "POWER", "GROUND", "ANALOG", "OCL", "OEM", "TRI", "TERMINAL"]
COLOR_PALETTE = [
    ("#2563EB", "Königsblau"),
    ("#0F9F77", "Smaragd"),
    ("#7C3AED", "Violett"),
    ("#D97706", "Orange"),
    ("#BE123C", "Karmin"),
    ("#0E7490", "Türkis"),
    ("#475569", "Schiefer"),
    ("#DB2777", "Magenta"),
    ("#65A30D", "Limette"),
    ("#4F46E5", "Indigo"),
    ("#B45309", "Bernstein"),
    ("#0369A1", "Ozeanblau"),
    ("#DC2626", "Rot"),
    ("#0F766E", "Teal"),
    ("#9333EA", "Purpur"),
    ("#A16207", "Ocker"),
    ("#0891B2", "Cyan"),
    ("#15803D", "Waldgrün"),
    ("#EA580C", "Rotorange"),
    ("#334155", "Graphit"),
    ("#C026D3", "Pink"),
    ("#4D7C0F", "Oliv"),
    ("#6D4C41", "Braun"),
    ("#6B21A8", "Aubergine"),
]


@dataclass
class PageState:
    package: ArchitecturePackage
    version: int
    selected_id: str | None = None
    navigator_search_id: str | None = None
    canvas_mode: str = "architecture"
    focus_domain_id: str | None = None
    collapsed_domain_ids: set[str] = field(default_factory=set)
    collapsed_element_ids: set[str] = field(default_factory=set)
    expanded_navigator_domain_ids: set[str] = field(default_factory=set)
    expanded_navigator_element_ids: set[str] = field(default_factory=set)
    signal_types: set[str] = field(default_factory=lambda: {item.value for item in SignalType})
    topology_signal_id: str | None = None
    topology_source_id: str | None = None
    topology_sink_ids: set[str] = field(default_factory=set)
    topology_participant_query: str = ""
    topology_expanded_domain_ids: set[str] = field(default_factory=set)
    canvas_assignment_phase: str | None = None
    workspace_tab: str = "architecture"


repository = ArchitectureRepository()
PROJECT_ROOT = Path(__file__).resolve().parents[1]
bus_templates = BusContentTemplates(PROJECT_ROOT / "Interface_Template_File.json")
architecture_catalog = ArchitectureCatalog(PROJECT_ROOT / "Architecture_Catalog.json")
ai_provider = build_ai_provider()
credential_store = AICredentialStore(repository)
credential_store.configure_provider(ai_provider)
analysis_queue = DocumentAnalysisQueue(
    repository, ai_provider, bus_templates, architecture_catalog,
)
app.add_static_files("/xped-static", str(PROJECT_ROOT / "vendor"))
TOOL_DOCUMENTATION_URL = "/isd-suite-tooldokumentation"
TOOL_DOCUMENTATION_PATH = PROJECT_ROOT / "docs" / "HANDBUCH_ISD_SUITE.md"


def prepare_package(package: ArchitecturePackage) -> None:
    prepare_saved_package(package, bus_templates, architecture_catalog)




def build_page() -> None:
    analysis_queue.ensure_started()
    projects = repository.list_projects()
    if projects:
        package, version = repository.load_project(projects[0].id)
    else:
        package, version = repository.create_project(demo_package())
    prepare_package(package)
    state = PageState(package=package, version=version)
    state.workspace_tab = (
        "overview"
        if package.project.workflow_mode != ProjectWorkflow.MANUAL
        else "architecture"
    )
    state.expanded_navigator_domain_ids = {domain.id for domain in state.package.domains}
    state.expanded_navigator_element_ids = {
        element.id for domain in state.package.domains for element in domain.elements
    }

    ui.colors(primary="#174EA6", secondary="#0F9F77", accent="#7C3AED", positive="#16875B", negative="#C8324A")
    from .ui_assets import install_ui_assets
    install_ui_assets()

    def color_palette(initial_color: str) -> dict[str, str]:
        """Render an accessible swatch palette without exposing hex values in the UI."""
        available_colors = list(COLOR_PALETTE)
        if initial_color not in {value for value, _label in available_colors}:
            available_colors.append((initial_color, "Bestehende Farbe"))
        selected_color = {"value": initial_color}

        def choose_color(value: str) -> None:
            selected_color["value"] = value
            palette_view.refresh()

        @ui.refreshable
        def palette_view() -> None:
            ui.label("Farbe auswählen").classes("text-sm font-medium text-slate-700")
            with ui.element("div").classes("color-palette w-full"):
                for value, label in available_colors:
                    is_selected = selected_color["value"] == value
                    selected_class = " color-swatch-selected" if is_selected else ""
                    with ui.element("button").props(
                        f'type="button" aria-label="{label}"'
                    ).classes(f"color-swatch{selected_class}").style(
                        f"background-color:{value}"
                    ).on("click", lambda _, color_value=value: choose_color(color_value)):
                        if is_selected:
                            ui.icon("check", size="20px")
        palette_view()
        return selected_color

    def hierarchy_name_is_available(value: str, exclude_id: str | None = None) -> bool:
        normalized = value.strip().casefold()
        if not normalized:
            return False
        for domain in state.package.domains:
            if domain.id != exclude_id and domain.name.casefold() == normalized:
                return False
            for element in domain.elements:
                if element.id != exclude_id and element.name.casefold() == normalized:
                    return False
        return True

    def save(
        reason: str = "Änderung gespeichert",
        refresh_canvas: bool = True,
        refresh_requirements: bool = True,
        notify_user: bool = True,
    ) -> bool:
        try:
            prepare_package(state.package)
            validated = ArchitecturePackage.model_validate(state.package.export_dict())
            state.version = repository.save_project(validated, state.version)
            state.package = validated
            save_status.set_text(f"Gespeichert · Stand {state.version}")
            if notify_user:
                ui.notify(reason, type="positive", timeout=1200)
            if refresh_canvas:
                refresh_all()
            elif refresh_requirements:
                revisions_view.refresh()
                requirements_views.refresh()
                development_views.refresh()
            return True
        except VersionConflict as error:
            ui.notify(str(error), type="warning", close_button=True)
        except (ValidationError, ValueError) as error:
            ui.notify(f"Validierung fehlgeschlagen: {error}", type="negative", close_button=True)
        return False

    def switch_project(project_id: str) -> None:
        state.package, state.version = repository.load_project(project_id)
        prepare_package(state.package)
        state.selected_id = None
        state.navigator_search_id = None
        state.canvas_mode = "architecture"
        state.focus_domain_id = None
        state.collapsed_domain_ids.clear()
        state.collapsed_element_ids.clear()
        state.expanded_navigator_domain_ids = {domain.id for domain in state.package.domains}
        state.expanded_navigator_element_ids = {
            element.id for domain in state.package.domains for element in domain.elements
        }
        state.signal_types = {item.value for item in SignalType}
        state.topology_signal_id = None
        state.topology_source_id = None
        state.topology_sink_ids.clear()
        state.topology_participant_query = ""
        state.topology_expanded_domain_ids.clear()
        state.canvas_assignment_phase = None
        requirements_views.reset()
        development_views.reset()
        if topology_drawer.value:
            topology_drawer.toggle()
        apply_workflow_mode(prefer_requirements=True)
        refresh_all()
        requirements_views.record_navigation()

    def show_imported_project(imported: ArchitecturePackage, imported_version: int) -> None:
            state.package, state.version = imported, imported_version
            prepare_package(state.package)
            state.selected_id = None
            state.navigator_search_id = None
            state.canvas_mode = "architecture"
            state.focus_domain_id = None
            state.collapsed_domain_ids.clear()
            state.collapsed_element_ids.clear()
            state.expanded_navigator_domain_ids = {domain.id for domain in state.package.domains}
            state.expanded_navigator_element_ids = {
                element.id for domain in state.package.domains for element in domain.elements
            }
            state.signal_types = {item.value for item in SignalType}
            state.topology_signal_id = None
            state.topology_source_id = None
            state.topology_sink_ids.clear()
            state.topology_participant_query = ""
            state.topology_expanded_domain_ids.clear()
            state.canvas_assignment_phase = None
            requirements_views.reset()
            development_views.reset()
            if topology_drawer.value:
                topology_drawer.toggle()
            apply_workflow_mode(prefer_requirements=True)
            refresh_all()
    def import_json_dialog() -> None:
        open_project_import_dialog(
            repository, state.package.project.id, state.version, show_imported_project,
        )

    def export_json() -> None:
        payload = json.dumps(state.package.export_dict(), indent=2, ensure_ascii=False).encode("utf-8")
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in state.package.project.name)
        ui.download(payload, f"{safe}_project_v{state.version:03d}.json", media_type="application/json")

    def export_pdf() -> None:
        from .architecture_pdf import ARCHITECTURE_LABELS
        with ui.dialog() as dialog,ui.card().classes('w-[650px] max-w-[95vw] p-6 gap-4'):
            ui.label('Architektur als PDF exportieren').classes('text-xl font-bold')
            choices=ui.select(ARCHITECTURE_LABELS,value=[architecture_views.current_discipline()],multiple=True,label='Architekturen').props('use-chips').classes('w-full')
            ui.label('Jede gewählte Architektur erhält eigene Seiten, Titel, Legende und Beziehungen.').classes('text-sm')
            ui.button('Alle Architekturen auswählen',on_click=lambda:choices.set_value(list(ARCHITECTURE_LABELS))).props('flat')
            def download():
                if not choices.value:ui.notify('Mindestens eine Architektur auswählen',type='warning');return
                export_selected_pdf(choices.value);dialog.close()
            ui.button('Abbrechen',on_click=dialog.close).props('flat')
            ui.button('PDF exportieren',icon='picture_as_pdf',on_click=download)
        dialog.open()

    def export_selected_pdf(views) -> None:
        try:
            payload = export_architecture_pdf(state.package, state.version,views)
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in state.package.project.name)
            ui.download(payload, f"{safe}_architecture_v{state.version:03d}.pdf", media_type="application/pdf")
        except ModuleNotFoundError as error:
            ui.notify(
                f"PDF-Export: Python-Paket {error.name or 'reportlab'} fehlt. "
                "Bitte start_windows.bat erneut ausführen oder in der verwendeten "
                "Python-Umgebung 'python -m pip install -r requirements.txt' aufrufen.",
                type="negative", close_button=True,
            )
        except Exception as error:
            ui.notify(f"PDF-Export fehlgeschlagen: {error}", type="negative", close_button=True)

    def requirements_exchange_dialog() -> None:
        open_requirements_exchange_dialog(state, create_safety_revision, save)

    def export_buscontents() -> None:
        content = export_buscontents_text(state.package, bus_templates)
        ui.download(content.encode("utf-8"), "busconts.ini", media_type="text/plain")

    def ecad_connector_dialog() -> None:
        opened_version = state.version
        opened_project = state.package.project.id
        def commit_ecad(updated: ArchitecturePackage, reason: str) -> bool:
            if state.version != opened_version or state.package.project.id != opened_project:
                ui.notify("Das Projekt wurde seit dem Öffnen des ECAD-Dialogs geändert. Bitte schließen und erneut einlesen.",
                          type="warning", close_button=True)
                return False
            previous = state.package
            state.package = updated
            if save(reason):
                return True
            state.package = previous
            return False
        open_ecad_dialog(state.package, commit_ecad)





    def create_project_dialog() -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[560px] max-w-[94vw] p-6 gap-4"):
            ui.label("Neues Systemprojekt anlegen").classes("text-xl font-bold")
            name = ui.input("Name", placeholder="Name").classes("w-full")
            ui.label("Der Name ist erforderlich und muss innerhalb der ISD Suite eindeutig sein.").classes("text-xs text-slate-500")
            ui.label("Arbeitsweise festlegen").classes("text-sm font-semibold text-slate-700")
            workflow_mode = ui.radio(
                {
                    ProjectWorkflow.MANUAL.value: "Direkt mit HW-/ECAD-Architektur beginnen",
                    ProjectWorkflow.REQUIREMENTS.value: "Integrierte Systementwicklung mit Requirements",
                    ProjectWorkflow.REDESIGN.value: "Redesign eines bestehenden Systems",
                    ProjectWorkflow.STUDY.value: "Architekturstudie / Prototyp",
                },
                value=ProjectWorkflow.MANUAL.value,
            ).classes("w-full")
            ui.label(
                "Requirements sind optional. Der Redesign-Modus behandelt Schaltplan, BOM und Netzliste als "
                "As-Is-Evidenz. Alle Entwicklungsräume und der JSON-Export bleiben in jedem Modus nutzbar."
            ).classes("text-xs text-slate-500")
            use_demo = ui.checkbox("Mit Beispielarchitektur starten", value=False)
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat")
                def create() -> None:
                    names = [p.name for p in repository.list_projects()]
                    project_name = (name.value or "").strip()
                    if not project_name:
                        ui.notify("Bitte einen Namen für das neue Systemprojekt eingeben.", type="warning")
                        return
                    if project_name.casefold() in {item.casefold() for item in names}:
                        ui.notify("Ein Systemprojekt mit diesem Namen existiert bereits.", type="warning")
                        return
                    new_package = demo_package(project_name) if use_demo.value else ArchitecturePackage()
                    new_package.project.name = project_name
                    new_package.project.workflow_mode = ProjectWorkflow(workflow_mode.value)
                    if new_package.project.workflow_mode != ProjectWorkflow.MANUAL:
                        new_package.schema_version = "isd-suite/v3"
                    new_package.project.attributes["electronicsArchitectureMaturity"] = "Working"
                    state.package, state.version = repository.create_project(new_package)
                    state.selected_id = None
                    requirements_views.reset()
                    development_views.reset()
                    dialog.close()
                    apply_workflow_mode(prefer_requirements=True)
                    refresh_all()
                    requirements_views.record_navigation()
                ui.button("Projekt anlegen", on_click=create)
        dialog.open()

    def ai_configuration_dialog(on_changed: Callable[[], None] | None = None) -> None:
        open_ai_configuration(ai_provider, credential_store, requirements_views.refresh, on_changed)

    def admin_pin_dialog() -> None:
        pin_is_set = repository.admin_pin_is_set()
        with ui.dialog() as dialog, ui.card().classes("w-[500px] max-w-[92vw] p-6 gap-4"):
            ui.label("Admin-PIN verwalten").classes("text-xl font-bold")
            ui.label(
                "Die Admin-PIN schützt das vollständige Löschen von Architekturprojekten. "
                "Sie wird lokal und nur als gesicherter Hash in der Anwendungsdatenbank gespeichert."
            ).classes("text-sm text-slate-600 leading-relaxed")
            current_pin = ui.input(
                "Aktuelle Admin-PIN",
                password=True,
                password_toggle_button=True,
            ).classes("w-full")
            if pin_is_set:
                ui.label("Anfangs-PIN: 0000. Bei einer Änderung muss die aktuelle PIN eingegeben werden.").classes("text-xs text-amber-800")
            new_pin = ui.input(
                "Neue Admin-PIN",
                password=True,
                password_toggle_button=True,
            ).classes("w-full")
            confirmation = ui.input(
                "Neue Admin-PIN wiederholen",
                password=True,
                password_toggle_button=True,
            ).classes("w-full")
            ui.label(
                "Die neue PIN benötigt mindestens vier Zeichen. Eine PIN kann nicht entfernt werden."
            ).classes("text-xs text-slate-500")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply_pin() -> None:
                    if (new_pin.value or "") != (confirmation.value or ""):
                        ui.notify("Die neue Admin-PIN und ihre Wiederholung stimmen nicht überein.", type="warning")
                        return
                    try:
                        repository.set_admin_pin(
                            current_pin.value or "",
                            new_pin.value or "",
                        )
                    except (PermissionError, ValueError) as error:
                        ui.notify(str(error), type="negative", close_button=True)
                        return
                    dialog.close()
                    ui.notify(
                        "Admin-PIN gespeichert",
                        type="positive",
                    )

                ui.button("PIN übernehmen", icon="shield", on_click=apply_pin).props("no-caps")
        dialog.open()

    def delete_project_dialog() -> None:
        project_id = state.package.project.id
        project_name = state.package.project.name
        revision_count = len(repository.list_revisions(project_id))
        with ui.dialog() as dialog, ui.card().classes("w-[540px] max-w-[92vw] p-6 gap-4"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("warning", size="34px", color="negative")
                with ui.column().classes("gap-0"):
                    ui.label("Systemprojekt endgültig löschen?").classes("text-xl font-bold")
                    ui.label(project_name).classes("text-base font-semibold text-red-700")
            ui.label(
                "Das vollständige Projekt einschließlich aller Architekturobjekte und Revisionen wird gelöscht. "
                "Diese Aktion kann in der Anwendung nicht rückgängig gemacht werden."
            ).classes("text-sm text-slate-700 leading-relaxed")
            ui.label(f"Mit dem Projekt werden {revision_count} gespeicherte Revisionen entfernt.").classes("text-sm text-slate-600")
            admin_pin = ui.input(
                "Admin-PIN",
                password=True,
                password_toggle_button=True,
            ).classes("w-full")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def delete_project() -> None:
                    try:
                        repository.delete_project(project_id, admin_pin.value if admin_pin else "")
                    except (PermissionError, KeyError) as error:
                        ui.notify(str(error), type="negative", close_button=True)
                        return
                    try:
                        delete_project_attachments(project_id)
                    except (OSError, ValueError) as error:
                        ui.notify(
                            f"Projekt gelöscht; lokale Dokumentablage konnte nicht vollständig bereinigt werden: {error}",
                            type="warning",
                            close_button=True,
                        )
                    remaining = repository.list_projects()
                    if remaining:
                        next_project_id = remaining[0].id
                    else:
                        replacement = ArchitecturePackage()
                        replacement.project.name = "Neues Systemprojekt"
                        replacement, _version = repository.create_project(replacement)
                        next_project_id = replacement.project.id
                    dialog.close()
                    switch_project(next_project_id)
                    ui.notify(f"Architektur „{project_name}“ gelöscht", type="positive")

                ui.button(
                    "Projekt endgültig löschen",
                    icon="delete_forever",
                    on_click=delete_project,
                ).props("color=negative no-caps")
        dialog.open()

    def create_revision_dialog() -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[460px]"):
            ui.label("Revision festhalten").classes("text-xl font-bold")
            label = ui.input("Beschreibung", placeholder="z. B. Schnittstellenreview abgeschlossen").classes("w-full")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat")
                def create() -> None:
                    number = repository.create_revision(state.package.project.id, label.value)
                    dialog.close()
                    ui.notify(f"Revision {number} erstellt", type="positive")
                    revisions_view.refresh()
                ui.button("Revision erstellen", on_click=create)
        dialog.open()





    def apply_signal_topology(
        signal: ArchitectureSignal,
        source_id: str | None,
        sink_ids: list[str],
        source_pin_type: str | None = None,
        sink_pin_type: str | None = None,
        reason: str = "Signaltopologie aktualisiert",
    ) -> bool:
        element_labels = {
            element.id: f"{domain.name} / {element.name}"
            for domain in state.package.domains for element in domain.elements
        }
        sink_ids = sorted(
            dict.fromkeys(sink_ids),
            key=lambda element_id: element_labels.get(element_id, element_id).casefold(),
        )
        if source_id and source_id in sink_ids:
            ui.notify("Ein Architecture Element kann nicht gleichzeitig Host und Teilnehmer sein.", type="warning")
            return False
        previous_sink_types = {endpoint.element_id: endpoint.pin_type for endpoint in signal.sinks}
        signal.source = SignalEndpoint(
            element_id=source_id,
            pin_type=source_pin_type or (signal.source.pin_type if signal.source else "OUT"),
        ) if source_id else None
        signal.sinks = [SignalEndpoint(
            element_id=element_id,
            pin_type=sink_pin_type or previous_sink_types.get(element_id, "IN"),
        ) for element_id in sink_ids]
        synchronize_signal_topology(state.package, signal, bus_templates)
        state.selected_id = signal.id
        return save(reason)

    def topology_element_options() -> dict[str, str]:
        return {
            element.id: f"{domain.name} / {element.name}"
            for domain in state.package.domains for element in domain.elements
        }

    def load_topology_draft(signal: ArchitectureSignal) -> None:
        state.topology_signal_id = signal.id
        state.topology_source_id = signal.source.element_id if signal.source else None
        state.topology_sink_ids = {endpoint.element_id for endpoint in signal.sinks}
        state.topology_participant_query = ""
        involved_element_ids = set(state.topology_sink_ids)
        if state.topology_source_id:
            involved_element_ids.add(state.topology_source_id)
        involved_domain_ids = {
            domain.id
            for domain in state.package.domains
            if any(element.id in involved_element_ids for element in domain.elements)
        }
        if len(state.package.domains) <= 4:
            involved_domain_ids = {domain.id for domain in state.package.domains}
        elif not involved_domain_ids and state.package.domains:
            involved_domain_ids.add(state.package.domains[0].id)
        state.topology_expanded_domain_ids = involved_domain_ids
        state.canvas_assignment_phase = None

    def close_topology_drawer() -> None:
        state.canvas_assignment_phase = None
        if topology_drawer.value:
            topology_drawer.toggle()
        canvas_view.refresh()

    def start_canvas_assignment() -> None:
        current = state.package.find_architecture_signal(state.topology_signal_id or "")
        if current is None:
            return
        state.canvas_assignment_phase = "host" if not state.topology_source_id else "participants"
        state.canvas_mode = "architecture"
        state.selected_id = current.id
        state.collapsed_domain_ids.clear()
        state.collapsed_element_ids.clear()
        topology_drawer_view.refresh()
        canvas_view.refresh()

    def finish_canvas_assignment() -> None:
        state.canvas_assignment_phase = None
        topology_drawer_view.refresh()
        canvas_view.refresh()

    @ui.refreshable
    def topology_selection_summary() -> None:
        host_count = 1 if state.topology_source_id else 0
        sink_count = len(state.topology_sink_ids)
        complete = bool(host_count and sink_count)
        status = f"{host_count} Host · {sink_count} Teilnehmer"
        ui.badge(status, color="green-1" if complete else "orange-1").props(
            "text-color=green-9" if complete else "text-color=orange-10"
        )

    @ui.refreshable
    def topology_participant_chips() -> None:
        if not state.topology_sink_ids:
            ui.label("Noch keine Teilnehmer ausgewählt").classes("subtle")
            return
        with ui.row().classes("w-full gap-1"):
            for element_id in sorted(
                state.topology_sink_ids,
                key=lambda item: topology_element_options().get(item, item).casefold(),
            ):
                label = topology_element_options().get(element_id, element_id)
                with ui.row().classes("topology-chip items-center gap-1 px-2 py-1"):
                    ui.label(label).classes("text-xs")
                    def remove_participant(_=None, object_id=element_id) -> None:
                        state.topology_sink_ids.discard(object_id)
                        topology_participant_chips.refresh()
                        topology_participant_list.refresh()
                        topology_selection_summary.refresh()
                        if state.canvas_assignment_phase:
                            canvas_view.refresh()
                    ui.button(icon="close", on_click=remove_participant).props("flat round dense size=xs")

    def set_domain_participants(domain: Domain, selected: bool) -> None:
        element_ids = {element.id for element in domain.elements if element.id != state.topology_source_id}
        if selected:
            state.topology_sink_ids.update(element_ids)
        else:
            state.topology_sink_ids.difference_update(element_ids)
        topology_participant_chips.refresh()
        topology_participant_list.refresh()
        topology_selection_summary.refresh()
        if state.canvas_assignment_phase:
            canvas_view.refresh()

    def clear_all_participants() -> None:
        state.topology_sink_ids.clear()
        topology_participant_chips.refresh()
        topology_participant_list.refresh()
        topology_selection_summary.refresh()
        if state.canvas_assignment_phase:
            canvas_view.refresh()

    @ui.refreshable
    def topology_participant_list() -> None:
        query = state.topology_participant_query.casefold().strip()
        visible_count = 0
        for domain in state.package.domains:
            matching_elements = [
                element for element in domain.elements
                if not query or query in f"{domain.name} {element.name} {element.kind}".casefold()
            ]
            if not matching_elements:
                continue
            visible_count += len(matching_elements)
            domain_expansion = ui.expansion(
                f"{domain.name} ({len(matching_elements)})",
                icon="domain",
                value=bool(query) or domain.id in state.topology_expanded_domain_ids,
            ).classes("topology-domain w-full")
            def remember_domain_expansion(event, domain_id=domain.id) -> None:
                if event.value:
                    state.topology_expanded_domain_ids.add(domain_id)
                else:
                    state.topology_expanded_domain_ids.discard(domain_id)
            domain_expansion.on_value_change(remember_domain_expansion)
            with domain_expansion:
                with ui.row().classes("w-full justify-end gap-1"):
                    ui.button(
                        "Alle",
                        on_click=lambda _, item=domain: set_domain_participants(item, True),
                    ).props("flat dense no-caps")
                    ui.button(
                        "Keine",
                        on_click=lambda _, item=domain: set_domain_participants(item, False),
                    ).props("flat dense no-caps")
                for element in matching_elements:
                    is_host = element.id == state.topology_source_id
                    checkbox = ui.checkbox(
                        element.name,
                        value=element.id in state.topology_sink_ids,
                    ).classes("topology-participant w-full px-3 py-1")
                    if is_host:
                        checkbox.set_enabled(False)
                        checkbox.tooltip("Das AE ist bereits als Host gewählt.")
                    def change_participant(event, object_id=element.id) -> None:
                        if event.value and object_id != state.topology_source_id:
                            state.topology_sink_ids.add(object_id)
                        else:
                            state.topology_sink_ids.discard(object_id)
                        topology_participant_chips.refresh()
                        topology_selection_summary.refresh()
                        if state.canvas_assignment_phase:
                            canvas_view.refresh()
                    checkbox.on_value_change(change_participant)
        if not visible_count:
            ui.label("Keine passenden Architecture Elements gefunden.").classes("subtle py-4")

    @ui.refreshable
    def topology_drawer_view() -> None:
        current = state.package.find_architecture_signal(state.topology_signal_id or "")
        with ui.column().classes("w-full h-full min-h-0 gap-0"):
            with ui.row().classes("w-full items-center px-5 py-4 bg-white border-b"):
                with ui.column().classes("gap-0 grow"):
                    ui.label("Topologie zuweisen").classes("text-xl font-bold")
                    ui.label("Ein Host, beliebig viele Teilnehmer").classes("subtle")
                ui.button(icon="close", on_click=close_topology_drawer).props("flat round")
            if current is None:
                with ui.column().classes("grow items-center justify-center p-6"):
                    ui.icon("account_tree", size="48px").classes("text-slate-300")
                    ui.label("Wähle ein Signal im Signalkatalog aus.").classes("subtle")
                return

            signal_options = {
                item.id: f"{item.signal_type.value} · {item.name}"
                for item in sorted(state.package.signals, key=lambda item: (item.signal_type.value, item.name.casefold()))
            }
            element_options = topology_element_options()
            with ui.column().classes("w-full px-5 pt-4 gap-3"):
                signal_select = ui.select(
                    signal_options,
                    value=current.id,
                    label="Signal",
                    with_input=True,
                ).classes("w-full").props("outlined dense options-dense")
                def change_topology_signal(event) -> None:
                    selected_signal = state.package.find_architecture_signal(event.value or "")
                    if selected_signal:
                        load_topology_draft(selected_signal)
                        state.selected_id = selected_signal.id
                        topology_drawer_view.refresh()
                        hierarchy_view.refresh()
                        inspector_view.refresh()
                        canvas_view.refresh()
                signal_select.on_value_change(change_topology_signal)
                with ui.row().classes("w-full items-center"):
                    with ui.column().classes("gap-0 grow"):
                        ui.label(current.name).classes("text-lg font-bold")
                        ui.label(f"{current.signal_type.value} · {current.connection_type.value}").classes("subtle")
                    topology_selection_summary()
                if state.canvas_assignment_phase:
                    phase_label = "Host auswählen" if state.canvas_assignment_phase == "host" else "Teilnehmer auswählen"
                    with ui.row().classes("assignment-help w-full items-center px-3 py-2"):
                        ui.icon("ads_click")
                        ui.label(f"Canvas-Modus aktiv: {phase_label}").classes("font-medium grow")
                        ui.button("Beenden", on_click=finish_canvas_assignment).props("flat dense no-caps")

                ui.label("1 · Host").classes("font-bold text-blue-9")
                host_select = ui.select(
                    element_options,
                    value=state.topology_source_id,
                    label="Host / Source",
                    with_input=True,
                ).classes("w-full").props("clearable outlined dense options-dense")
                def change_topology_host(event) -> None:
                    state.topology_source_id = event.value
                    if event.value:
                        state.topology_sink_ids.discard(event.value)
                    topology_participant_list.refresh()
                    topology_participant_chips.refresh()
                    topology_selection_summary.refresh()
                    if state.canvas_assignment_phase:
                        state.canvas_assignment_phase = "participants"
                        canvas_view.refresh()
                host_select.on_value_change(change_topology_host)

                with ui.row().classes("w-full items-end gap-2"):
                    participant_search = ui.input(
                        "Teilnehmer suchen",
                        value=state.topology_participant_query,
                        placeholder="Domain oder AE …",
                    ).classes("grow").props("outlined dense clearable")
                    def update_participant_query(event) -> None:
                        state.topology_participant_query = event.value or ""
                        topology_participant_list.refresh()
                    participant_search.on_value_change(update_participant_query)
                    ui.button(
                        icon="remove_done",
                        on_click=clear_all_participants,
                    ).props("outline round dense").tooltip("Alle Teilnehmer entfernen")
                with ui.column().classes("w-full max-h-28 overflow-auto"):
                    topology_participant_chips()

            with ui.scroll_area().classes("grow w-full min-h-0 px-5 py-3"):
                topology_participant_list()

            with ui.column().classes("w-full px-5 py-3 gap-2 bg-white border-t"):
                with ui.expansion("ECAD Pin Types / Adapterzuordnung", icon="tune").classes("w-full border rounded-lg"):
                    with ui.row().classes("w-full gap-2"):
                        source_pin = ui.select(
                            PIN_TYPES,
                            value=current.source.pin_type if current.source else "OUT",
                            label="Host",
                            with_input=True,
                        ).classes("grow")
                        sink_pin = ui.select(
                            PIN_TYPES,
                            value=current.sinks[0].pin_type if current.sinks else "IN",
                            label="Teilnehmer",
                            with_input=True,
                        ).classes("grow")
                with ui.row().classes("w-full items-center gap-2"):
                    ui.button("Im Canvas zuweisen", icon="ads_click", on_click=start_canvas_assignment).props("outline no-caps")
                    ui.space()
                    ui.button("Verwerfen", on_click=close_topology_drawer).props("flat no-caps")
                    def apply_drawer_topology(go_to_next: bool = False) -> None:
                        signal_id = current.id
                        source_id = state.topology_source_id
                        sink_ids = sorted(state.topology_sink_ids)
                        source_pin_type = source_pin.value
                        sink_pin_type = sink_pin.value
                        if not apply_signal_topology(
                            current,
                            source_id,
                            sink_ids,
                            source_pin_type,
                            sink_pin_type,
                        ):
                            return
                        state.canvas_assignment_phase = None
                        if go_to_next:
                            next_signal = next(
                                (
                                    item for item in state.package.signals
                                    if item.id != signal_id and not (item.source and item.sinks)
                                ),
                                None,
                            )
                            if next_signal:
                                load_topology_draft(next_signal)
                                state.selected_id = next_signal.id
                                topology_drawer_view.refresh()
                                hierarchy_view.refresh()
                                inspector_view.refresh()
                                return
                        connection = next(
                            (item for item in state.package.connections if item.signal_id == signal_id),
                            None,
                        )
                        state.selected_id = connection.id if connection else signal_id
                        state.canvas_mode = "selection" if connection else "architecture"
                        topology_drawer_view.refresh()
                        hierarchy_view.refresh()
                        inspector_view.refresh()
                        canvas_view.refresh()
                    ui.button("Speichern", icon="save", on_click=lambda: apply_drawer_topology(False)).props("outline no-caps")
                    ui.button("Speichern & weiter", icon="navigate_next", on_click=lambda: apply_drawer_topology(True)).props("no-caps")

    def open_topology_drawer(signal: ArchitectureSignal) -> None:
        if not topology_element_options():
            ui.notify("Es sind noch keine Architecture Elements vorhanden.", type="warning")
            return
        load_topology_draft(signal)
        state.selected_id = signal.id
        topology_drawer_view.refresh()
        hierarchy_view.refresh()
        inspector_view.refresh()
        if not topology_drawer.value:
            topology_drawer.toggle()

    def add_connection_dialog() -> None:
        signal_options = {signal.id: f"{signal.signal_type.value} / {signal.name}" for signal in state.package.signals}
        if not signal_options:
            ui.notify("Lege zuerst ein Signal oder Interface im Interface-/Signal-Wizard an.", type="warning")
            return
        preferred_id = state.selected_id if state.selected_id in signal_options else None
        if preferred_id is None:
            incomplete = next((item for item in state.package.signals if not (item.source and item.sinks)), None)
            preferred_id = incomplete.id if incomplete else next(iter(signal_options))
        selected_signal = state.package.find_architecture_signal(preferred_id)
        if selected_signal:
            open_topology_drawer(selected_signal)

    def edit_object_dialog(object_id: str) -> None:
        from .architecture_editing import find_architecture_object
        obj = find_architecture_object(state.package, object_id)
        if isinstance(obj, Domain): edit_domain_dialog(obj)
        elif isinstance(obj, ArchitectureElement):
            found = state.package.find_element(obj.id)
            edit_element_dialog(found[0], obj)
        elif isinstance(obj, InterfacePort):
            found = state.package.find_port(obj.id)
            edit_port_dialog(found[0], found[1], obj)
        elif isinstance(obj, ArchitectureSignal): edit_architecture_signal_dialog(obj)
        elif isinstance(obj, Connection): edit_connection_dialog(obj)
        elif isinstance(obj, Signal): edit_member_dialog(obj)
        else:architecture_views.edit_object(object_id)








    def handle_canvas_select(event: events.GenericEventArguments) -> None:
        args = event.args or {}
        detail = args.get("detail", args) if isinstance(args, dict) else {}
        object_id = detail.get("id") if isinstance(detail, dict) else None
        object_type = detail.get("type") if isinstance(detail, dict) else None
        if not object_id:
            return
        if state.canvas_assignment_phase:
            element_id: str | None = None
            if object_type == "element":
                element_id = object_id
            elif object_type == "port":
                port_result = state.package.find_port(object_id)
                element_id = port_result[1].id if port_result else None
            elif object_type == "domain" and state.canvas_assignment_phase == "participants":
                domain = state.package.find_domain(object_id)
                if domain:
                    candidates = {element.id for element in domain.elements if element.id != state.topology_source_id}
                    if candidates and candidates.issubset(state.topology_sink_ids):
                        state.topology_sink_ids.difference_update(candidates)
                    else:
                        state.topology_sink_ids.update(candidates)
                    topology_participant_chips.refresh()
                    topology_participant_list.refresh()
                    topology_selection_summary.refresh()
                    canvas_view.refresh()
                return
            if not element_id:
                ui.notify("Bitte ein Architecture Element oder einen seiner Ports auswählen.", type="info")
                return
            if state.canvas_assignment_phase == "host":
                state.topology_source_id = element_id
                state.topology_sink_ids.discard(element_id)
                state.canvas_assignment_phase = "participants"
                ui.notify("Host gesetzt. Jetzt Teilnehmer auswählen.", type="positive", timeout=1200)
            elif element_id == state.topology_source_id:
                ui.notify("Der Host kann nicht gleichzeitig Teilnehmer sein.", type="warning")
                return
            elif element_id in state.topology_sink_ids:
                state.topology_sink_ids.remove(element_id)
            else:
                state.topology_sink_ids.add(element_id)
            topology_drawer_view.refresh()
            canvas_view.refresh()
            return
        if object_type == "connection":
            focus_object(object_id)
            return
        state.selected_id = object_id
        hierarchy_view.refresh(); inspector_view.refresh()
        if state.canvas_mode == "selection":
            canvas_view.refresh()

    def select(object_id: str) -> None:
        state.selected_id = object_id
        hierarchy_view.refresh(); inspector_view.refresh()
        port_result = state.package.find_port(object_id)
        if port_result:
            domain, element, port = port_result
            state.collapsed_domain_ids.discard(domain.id)
            state.collapsed_element_ids.discard(element.id)
            managed = state.package.find_architecture_signal(
                str(port.interface_link_id or port.properties.get("architectureSignalId") or "")
            )
            if managed:
                state.signal_types.add(managed.signal_type.value)
            state.canvas_mode = "architecture"
            canvas_view.refresh()
            return
        signal = state.package.find_architecture_signal(object_id)
        if signal:
            # A signal selected in the navigator must be visible even if its
            # type was filtered out or its endpoint groups were folded away.
            signal_type = signal.signal_type.value
            state.signal_types.add(signal_type)
            if signal.source:
                endpoint_ids = [signal.source.element_id]
            else:
                endpoint_ids = []
            endpoint_ids.extend(item.element_id for item in signal.sinks)
            for endpoint_id in endpoint_ids:
                located = state.package.find_element(endpoint_id)
                if located:
                    state.collapsed_domain_ids.discard(located[0].id)
                    state.collapsed_element_ids.discard(located[1].id)
            state.canvas_mode = "architecture"
            canvas_view.refresh()
        elif state.canvas_mode == "selection":
            canvas_view.refresh()
        else:
            ui.run_javascript(f"window.xpedHighlightCanvas({json.dumps(object_id)})")

    def toggle_domain_collapse(domain_id: str) -> None:
        if domain_id in state.collapsed_domain_ids:
            state.collapsed_domain_ids.remove(domain_id)
        else:
            state.collapsed_domain_ids.add(domain_id)
        state.canvas_mode = "architecture"
        hierarchy_view.refresh()
        canvas_view.refresh()

    def toggle_element_collapse(element_id: str) -> None:
        if element_id in state.collapsed_element_ids:
            state.collapsed_element_ids.remove(element_id)
        else:
            state.collapsed_element_ids.add(element_id)
        if state.canvas_mode == "system":
            state.canvas_mode = "architecture"
        hierarchy_view.refresh()
        canvas_view.refresh()

    def toggle_navigator_domain(domain_id: str) -> None:
        if domain_id in state.expanded_navigator_domain_ids:
            state.expanded_navigator_domain_ids.remove(domain_id)
        else:
            state.expanded_navigator_domain_ids.add(domain_id)
        hierarchy_view.refresh()

    def toggle_navigator_element(element_id: str) -> None:
        if element_id in state.expanded_navigator_element_ids:
            state.expanded_navigator_element_ids.remove(element_id)
        else:
            state.expanded_navigator_element_ids.add(element_id)
        hierarchy_view.refresh()

    def expand_all_navigator() -> None:
        state.expanded_navigator_domain_ids = {domain.id for domain in state.package.domains}
        state.expanded_navigator_element_ids = {
            element.id for domain in state.package.domains for element in domain.elements
        }
        hierarchy_view.refresh()

    def collapse_all_navigator() -> None:
        state.expanded_navigator_domain_ids.clear()
        state.expanded_navigator_element_ids.clear()
        hierarchy_view.refresh()

    def collapse_all_domains() -> None:
        state.collapsed_domain_ids = {domain.id for domain in state.package.domains}
        state.canvas_mode = "architecture"
        canvas_view.refresh()

    def expand_all_domains() -> None:
        state.collapsed_domain_ids.clear()
        state.collapsed_element_ids.clear()
        state.canvas_mode = "architecture"
        canvas_view.refresh()

    def handle_canvas_toggle(event: events.GenericEventArguments) -> None:
        args = event.args or {}
        detail = args.get("detail", args) if isinstance(args, dict) else {}
        object_id = detail.get("id") if isinstance(detail, dict) else None
        object_type = detail.get("type") if isinstance(detail, dict) else None
        if object_type == "domain" and object_id:
            if state.canvas_mode == "system":
                state.canvas_mode = "domain"
                state.focus_domain_id = object_id
                state.collapsed_domain_ids.discard(object_id)
                hierarchy_view.refresh()
                canvas_view.refresh()
            else:
                toggle_domain_collapse(object_id)
        elif object_type == "element" and object_id:
            toggle_element_collapse(object_id)

    def clear_canvas_selection(_event: events.GenericEventArguments | None = None) -> None:
        if state.canvas_assignment_phase:
            return
        state.selected_id = None
        hierarchy_view.refresh()
        inspector_view.refresh()
        if state.canvas_mode == "selection":
            state.canvas_mode = "architecture"
            state.collapsed_domain_ids.clear()
            state.collapsed_element_ids.clear()
            canvas_view.refresh()
        else:
            ui.run_javascript("window.xpedHighlightCanvas(null)")

    def focus_object(object_id: str | None) -> None:
        if not object_id:
            clear_canvas_selection()
            return
        state.selected_id = object_id
        domain = state.package.find_domain(object_id)
        element_result = state.package.find_element(object_id)
        port_result = state.package.find_port(object_id)
        if domain:
            state.expanded_navigator_domain_ids.add(domain.id)
            state.collapsed_domain_ids.discard(domain.id)
        elif element_result:
            state.expanded_navigator_domain_ids.add(element_result[0].id)
            state.expanded_navigator_element_ids.add(element_result[1].id)
            state.collapsed_domain_ids.discard(element_result[0].id)
            state.collapsed_element_ids.discard(element_result[1].id)
        elif port_result:
            state.expanded_navigator_domain_ids.add(port_result[0].id)
            state.expanded_navigator_element_ids.add(port_result[1].id)
            state.collapsed_domain_ids.discard(port_result[0].id)
            state.collapsed_element_ids.discard(port_result[1].id)
        architecture_signal = state.package.find_architecture_signal(object_id)
        connection = next((item for item in state.package.connections if item.id == object_id), None)
        endpoint_element_ids: set[str] = set()
        if architecture_signal:
            state.signal_types.add(architecture_signal.signal_type.value)
        port_result = state.package.find_port(object_id)
        if port_result:
            signal = state.package.find_architecture_signal(
                str(port_result[2].interface_link_id or
                    port_result[2].properties.get("architectureSignalId") or "")
            )
            if signal:
                state.signal_types.add(signal.signal_type.value)
            if architecture_signal.source:
                endpoint_element_ids.add(architecture_signal.source.element_id)
            endpoint_element_ids.update(endpoint.element_id for endpoint in architecture_signal.sinks)
        if connection:
            endpoint_element_ids.update(endpoint.element_id for endpoint in connection.endpoints)
        for element_id in endpoint_element_ids:
            located = state.package.find_element(element_id)
            if located:
                state.expanded_navigator_domain_ids.add(located[0].id)
                state.expanded_navigator_element_ids.add(located[1].id)
                state.collapsed_domain_ids.discard(located[0].id)
                state.collapsed_element_ids.discard(located[1].id)
        state.canvas_mode = "selection"
        hierarchy_view.refresh()
        inspector_view.refresh()
        canvas_view.refresh()

    def handle_navigator_search(event) -> None:
        state.navigator_search_id = event.value
        if event.value:
            focus_object(event.value)
        else:
            clear_canvas_selection()

    def selected_domain() -> Domain | None:
        if not state.selected_id:
            return None
        direct = state.package.find_domain(state.selected_id)
        if direct:
            return direct
        element = state.package.find_element(state.selected_id)
        if element:
            return element[0]
        port = state.package.find_port(state.selected_id)
        if port:
            return port[0]
        architecture_signal = state.package.find_architecture_signal(state.selected_id)
        if architecture_signal and architecture_signal.source:
            source_element = state.package.find_element(architecture_signal.source.element_id)
            if source_element:
                return source_element[0]
        connection = next((item for item in state.package.connections if item.id == state.selected_id), None)
        if connection and connection.endpoints:
            source_element = state.package.find_element(connection.endpoints[0].element_id)
            if source_element:
                return source_element[0]
        signal = state.package.find_signal(state.selected_id)
        return signal[0] if signal else None

    def selected_element() -> ArchitectureElement | None:
        if not state.selected_id:
            return None
        element = state.package.find_element(state.selected_id)
        if element:
            return element[1]
        port = state.package.find_port(state.selected_id)
        if port:
            return port[1]
        signal = state.package.find_signal(state.selected_id)
        return signal[1] if signal else None


    def selected_signal() -> ArchitectureSignal | None:
        if not state.selected_id:
            return None
        return state.package.find_architecture_signal(state.selected_id)

    def add_element_in_context() -> None:
        add_element_dialog(selected_domain())

    def add_interface_in_context() -> None:
        add_port_dialog(selected_element())


    def assign_signal_in_context() -> None:
        signal = selected_signal()
        if signal is None:
            ui.notify("Bitte zuerst ein Signal auswählen.", type="warning"); return
        open_topology_drawer(signal)



    def delete_selected(object_id: str | None = None) -> bool:
        selected = object_id or state.selected_id
        if not selected:
            return False
        previous_package = state.package.model_copy(deep=True)
        previous_selected = state.selected_id
        previous_navigator_search = state.navigator_search_id
        previous_canvas_mode = state.canvas_mode
        try:
            impact = delete_object(state.package, selected)
        except KeyError as error:
            ui.notify(str(error), type="negative", close_button=True)
            return False
        state.selected_id = None
        if state.navigator_search_id == selected:
            state.navigator_search_id = None
        if state.canvas_mode == "selection":
            state.canvas_mode = "architecture"
        if save(impact.success_message):
            domain_ids = {domain.id for domain in state.package.domains}
            element_ids = {
                element.id for domain in state.package.domains for element in domain.elements
            }
            state.collapsed_domain_ids.intersection_update(domain_ids)
            state.expanded_navigator_domain_ids.intersection_update(domain_ids)
            state.collapsed_element_ids.intersection_update(element_ids)
            state.expanded_navigator_element_ids.intersection_update(element_ids)
            if state.topology_source_id not in element_ids:
                state.topology_source_id = None
            state.topology_sink_ids.intersection_update(element_ids)
            if state.topology_signal_id and not state.package.find_architecture_signal(state.topology_signal_id):
                state.topology_signal_id = None
                state.canvas_assignment_phase = None
                if topology_drawer.value:
                    topology_drawer.toggle()
            refresh_all()
            return True
        state.package = previous_package
        state.selected_id = previous_selected
        state.navigator_search_id = previous_navigator_search
        state.canvas_mode = previous_canvas_mode
        refresh_all()
        return False

    def confirm_delete_object(object_id: str | None = None, after_delete=None) -> None:
        selected = object_id or state.selected_id
        if not selected:
            ui.notify("Bitte zuerst ein Architekturobjekt auswählen.", type="warning")
            return
        impact = deletion_impact(state.package, selected)
        if impact is None:
            ui.notify("Das ausgewählte Architekturobjekt wurde nicht gefunden.", type="warning")
            return
        with ui.dialog() as dialog, ui.card().classes("w-[520px] max-w-[92vw] p-6 gap-4"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("warning", size="32px", color="negative")
                with ui.column().classes("gap-0"):
                    ui.label(f"{impact.object_type} löschen?").classes("text-xl font-bold")
                    ui.label(impact.name).classes("font-semibold text-red-700")
            ui.label(impact.summary).classes("text-sm text-slate-700 leading-relaxed")
            with ui.column().classes("w-full gap-1 rounded-lg bg-red-50 border border-red-200 p-3"):
                for detail in impact.details:
                    with ui.row().classes("items-start gap-2 no-wrap"):
                        ui.icon("remove", size="17px").classes("text-red-700 mt-0.5")
                        ui.label(detail).classes("text-sm text-red-900")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def confirm() -> None:
                    if delete_selected(selected):
                        dialog.close()
                        if after_delete:
                            after_delete()

                ui.button(
                    "Endgültig löschen",
                    icon="delete",
                    on_click=confirm,
                ).props("color=negative no-caps")
        dialog.open()

    @ui.refreshable
    def project_selector() -> None:
        options = {p.id: p.name for p in repository.list_projects()}
        ui.select(options, value=state.package.project.id, on_change=lambda e: switch_project(e.value)).classes("toolbar-select").props("dense outlined bg-color=white")

    @ui.refreshable
    def hierarchy_view() -> None:
        with ui.column().classes("w-full gap-2 p-4"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("gap-0 min-w-0"):
                    ui.label("HW / ECAD").classes("panel-heading")
                    ui.label("Domains & Architekturelemente").classes("navigator-subheading")
                with ui.button(icon="more_vert").props("flat round dense").tooltip("Navigatoraktionen"):
                    with ui.menu():
                        ui.menu_item("Alle Bereiche aufklappen", on_click=expand_all_navigator)
                        ui.menu_item("Alle Bereiche zuklappen", on_click=collapse_all_navigator)
                        ui.separator()
                        ui.menu_item("Domain hinzufügen", on_click=add_domain_dialog)
            object_options: dict[str, str] = {}
            for domain in state.package.domains:
                object_options[domain.id] = f"Domain · {domain.name}"
                for element in domain.elements:
                    object_options[element.id] = f"AE · {domain.name} / {element.name}"
                    for port in element.ports:
                        if not block_port_visible(state.package, port): continue
                        object_options[port.id] = f"Port · {domain.name} / {element.name} / {port.name}"
            for signal in state.package.signals:
                object_options[signal.id] = f"Signal · {signal.signal_type.value} / {signal.name}"
            for connection in state.package.connections:
                object_options[connection.id] = f"Verbindung · {connection.name}"
            search_value = state.navigator_search_id if state.navigator_search_id in object_options else None
            object_search = ui.select(
                object_options,
                value=search_value,
                label="Objekt suchen und fokussieren",
            ).classes("w-full").props("dense outlined clearable use-input input-debounce=0 options-dense")
            object_search.on_value_change(handle_navigator_search)
            ui.label("Nur eine Auswahl in diesem Feld verändert den Suchwert.").classes("subtle px-1")
            for domain in state.package.domains:
                selected_class = " tree-selected" if state.selected_id == domain.id else ""
                with ui.column().classes(f"tree-domain w-full p-2 gap-1{selected_class}").style(f"--domain-color:{domain.color}"):
                    with ui.row().classes("navigator-row w-full items-center px-1 py-1 no-wrap"):
                        navigator_domain_open = domain.id in state.expanded_navigator_domain_ids
                        ui.button(
                            icon="keyboard_arrow_down" if navigator_domain_open else "keyboard_arrow_right",
                            on_click=lambda _, object_id=domain.id: toggle_navigator_domain(object_id),
                        ).props("flat round dense size=sm").tooltip("Domain im Navigator auf- oder zuklappen")
                        with ui.row().classes("navigator-select tree-select-target grow min-w-0 items-center gap-2 px-1 py-1").on("click", lambda _, object_id=domain.id: select(object_id)):
                            ui.icon("domain", color=domain.color)
                            ui.label(domain.name).classes("navigator-label font-bold grow").tooltip(domain.name)
                        with ui.button(icon="more_vert").classes("navigator-actions shrink-0").props(
                            "flat round dense size=sm"
                        ).tooltip("Domainaktionen"):
                            with ui.menu():
                                ui.menu_item(
                                    "Im Canvas aufklappen" if domain.id in state.collapsed_domain_ids else "Im Canvas einklappen",
                                    on_click=lambda _, object_id=domain.id: toggle_domain_collapse(object_id),
                                )
                                ui.menu_item(
                                    "Architecture Element hinzufügen",
                                    on_click=lambda _, d=domain: add_element_dialog(d),
                                )
                    if not navigator_domain_open:
                        continue
                    for element in domain.elements:
                        cls = " tree-selected" if state.selected_id == element.id else ""
                        with ui.column().classes(f"ml-4 gap-1{cls}"):
                            with ui.row().classes("navigator-row w-full items-center px-1 py-1 no-wrap"):
                                navigator_element_open = element.id in state.expanded_navigator_element_ids
                                ui.button(
                                    icon="keyboard_arrow_down" if navigator_element_open else "keyboard_arrow_right",
                                    on_click=lambda _, object_id=element.id: toggle_navigator_element(object_id),
                                ).props("flat round dense size=sm").tooltip("Ports im Navigator auf- oder zuklappen")
                                with ui.row().classes("navigator-select tree-select-target grow min-w-0 items-center gap-2 px-1 py-1").on("click", lambda _, object_id=element.id: select(object_id)):
                                    ui.icon("memory", size="20px").classes("text-slate-500")
                                    ui.label(element.name).classes("navigator-label grow").tooltip(element.name)
                                with ui.button(icon="more_vert").classes("navigator-actions shrink-0").props(
                                    "flat round dense size=sm"
                                ).tooltip("Architecture-Element-Aktionen"):
                                    with ui.menu():
                                        ui.menu_item(
                                            "Im Canvas aufklappen" if element.id in state.collapsed_element_ids else "Im Canvas einklappen",
                                            on_click=lambda _, object_id=element.id: toggle_element_collapse(object_id),
                                        )
                                        ui.menu_item(
                                            "Interface oder Signal anlegen",
                                            on_click=add_port_dialog,
                                        )
                            if not navigator_element_open:
                                continue
                            for direction_label, direction_ports in (
                                ("Teilnehmer-Ports", [port for port in element.ports if block_port_visible(state.package, port) and (port.side == "Left" or port.role == "Participant")]),
                                ("Host-Ports", [port for port in element.ports if block_port_visible(state.package, port) and not (port.side == "Left" or port.role == "Participant")]),
                            ):
                                if not direction_ports:
                                    continue
                                ui.label(direction_label).classes("ml-5 text-xs font-bold text-slate-500")
                                for port in sorted(direction_ports, key=lambda item: (item.port_type, item.name.casefold())):
                                    pcls = " tree-selected" if state.selected_id == port.id else ""
                                    with ui.row().classes(f"ml-5 w-[calc(100%-1.25rem)] min-w-0 items-center no-wrap tree-item px-2 py-1{pcls}"):
                                        with ui.row().classes("navigator-select tree-select-target grow min-w-0 items-center no-wrap gap-2").on(
                                            "click", lambda _, object_id=port.id: select(object_id),
                                        ):
                                            ui.icon("input" if direction_label == "Teilnehmer-Ports" else "output", size="17px").classes("text-blue-600")
                                            ui.label(port.name).classes("navigator-label text-sm grow").tooltip(port.name)
                                            ui.badge(port.port_type, color="blue-1").props("text-color=blue-9").classes(
                                                "navigator-badge shrink-0"
                                            ).tooltip(port.port_type)
                                        ui.button(
                                            icon="edit",
                                            on_click=lambda _, d=domain, e=element, p=port: edit_port_dialog(d, e, p),
                                        ).props("flat round dense size=sm").tooltip("Port bearbeiten")
            ui.separator().classes("my-2")
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Signale & Interfaces").classes("panel-heading")
                ui.button(icon="add", on_click=add_port_dialog).props("flat round dense").tooltip("Interface-/Signal-Wizard")
            if not state.package.signals:
                ui.label("Noch keine Signale definiert").classes("subtle px-2")
            for signal_type in SignalType:
                typed_signals = sorted((signal for signal in state.package.signals if signal.signal_type == signal_type), key=lambda item: item.name.casefold())
                if not typed_signals:
                    continue
                with ui.expansion(
                    f"{signal_type.value} ({len(typed_signals)})",
                    icon="category",
                    value=any(item.id == state.selected_id for item in typed_signals),
                ).classes("w-full border rounded-lg"):
                    for signal in typed_signals:
                        scls = " tree-selected" if state.selected_id == signal.id else ""
                        with ui.column().classes(f"catalog-signal-card w-full p-2 gap-1{scls}"):
                            with ui.row().classes("navigator-row w-full items-center no-wrap"):
                                with ui.row().classes("navigator-select tree-select-target grow min-w-0 items-center gap-2 px-1 py-1").on("click", lambda _, object_id=signal.id: select(object_id)):
                                    ui.icon("electrical_services", size="17px").classes("text-purple-600")
                                    ui.label(signal.name).classes("navigator-label text-sm grow").tooltip(signal.name)
                                    status = f"1→{len(signal.sinks)}" if signal.source and signal.sinks else "offen"
                                    ui.badge(status, color="purple-1").props("text-color=purple-9").classes("shrink-0")
                                ui.button(icon="edit", on_click=lambda _, item=signal: open_topology_drawer(item)).props("flat round dense size=sm").classes("navigator-actions").tooltip("Host und Teilnehmer bearbeiten")
                            with ui.row().classes("w-full items-center gap-1 px-1"):
                                host_name = topology_element_options().get(signal.source.element_id, "Unbekannt") if signal.source else "Host offen"
                                ui.icon("output", size="15px").classes("text-blue-600")
                                ui.label(host_name).classes("navigator-label text-xs text-slate-600 grow").tooltip(host_name)
                                ui.icon("groups", size="15px").classes("text-emerald-600")
                                ui.label(str(len(signal.sinks))).classes("text-xs font-bold text-slate-600")
            manual_connections = [
                connection for connection in state.package.connections
                if not connection.signal_id
            ]
            if manual_connections:
                ui.separator().classes("my-2")
                with ui.expansion(
                    f"Freie Verbindungen ({len(manual_connections)})",
                    icon="hub",
                    value=any(item.id == state.selected_id for item in manual_connections),
                ).classes("w-full border rounded-lg"):
                    for connection in sorted(manual_connections, key=lambda item: item.name.casefold()):
                        cls = " tree-selected" if state.selected_id == connection.id else ""
                        with ui.row().classes(f"navigator-row w-full min-w-0 items-center no-wrap px-2 py-1{cls}"):
                            with ui.row().classes("navigator-select grow min-w-0 items-center gap-2").on(
                                "click", lambda _, object_id=connection.id: focus_object(object_id),
                            ):
                                ui.icon("device_hub", size="18px").classes("text-emerald-600")
                                ui.label(connection.name).classes("navigator-label text-sm grow").tooltip(connection.name)
                            ui.button(
                                icon="edit", on_click=lambda _, item=connection: edit_connection_dialog(item),
                            ).props("flat round dense size=sm").tooltip("Freie Verbindung bearbeiten")

    @ui.refreshable
    def canvas_view() -> None:
        stats = repository.stats(state.package)
        if state.focus_domain_id not in {domain.id for domain in state.package.domains}:
            state.focus_domain_id = state.package.domains[0].id if state.package.domains else None
        with ui.column().classes("w-full p-5 gap-4"):
            with ui.row().classes("w-full items-center gap-3"):
                with ui.column().classes("gap-0 grow"):
                    ui.label("HW-/ECAD-Arbeitsarchitektur").classes("text-2xl font-bold")
                    ui.label("Die Arbeitskopie ist ab Projektstart verfügbar und wächst aus manuellen sowie geprüften Ableitungen.").classes("subtle")
                ui.badge(
                    str(state.package.project.attributes.get("electronicsArchitectureMaturity") or "Working"),
                    color="blue-2",
                ).props("text-color=blue-9")
                ui.button(
                    "Signale & Interfaces", icon="dataset", on_click=bus_contents_dialog,
                ).props("outline no-caps")
            with ui.row().classes("workflow w-full items-center gap-2"):
                ui.label("Modell aufbauen").classes("font-bold mr-2")
                ui.button("1  Domain", icon="domain_add", on_click=add_domain_dialog).props("flat color=white").classes("workflow-step")
                ui.icon("chevron_right").classes("text-blue-200")
                ui.button("2  Architecture Element", icon="memory", on_click=add_element_in_context).props("flat color=white").classes("workflow-step")
                ui.icon("chevron_right").classes("text-blue-200")
                ui.button("3  Interface-/Signal-Wizard", icon="dataset", on_click=add_interface_in_context).props("flat color=white").classes("workflow-step")
                ui.icon("chevron_right").classes("text-blue-200")
                ui.button("4  Host / Teilnehmer", icon="account_tree", on_click=assign_signal_in_context).props("flat color=white").classes("workflow-step")
                ui.icon("chevron_right").classes("text-blue-200")
                ui.label("5  Verbindung automatisch").classes("workflow-step px-4 py-2")
            domain = selected_domain(); element = selected_element()
            context = "Keine Auswahl"
            assignment_signal = state.package.find_architecture_signal(state.topology_signal_id or "") if state.canvas_assignment_phase else None
            if assignment_signal:
                phase_text = "Host" if state.canvas_assignment_phase == "host" else "Teilnehmer"
                context = f"Canvas-Zuweisung: {assignment_signal.name} · jetzt {phase_text} auswählen"
            elif element and domain:
                context = f"Auswahl: {domain.name} / {element.name}"
            elif selected_signal():
                chosen_signal = selected_signal()
                context = (
                    f"Signal: {chosen_signal.name} · "
                    f"{len(chosen_signal.sinks)} Teilnehmer · "
                    + ("Verbindung im Canvas hervorgehoben" if chosen_signal.source and chosen_signal.sinks
                       else "Topologie noch offen")
                )
            elif domain:
                context = f"Auswahl: {domain.name}"
            ui.label(context).classes("context-bar px-3 py-2 w-full")
            with ui.row().classes("w-full items-center gap-3"):
                for key, label in [("domains", "Domains"), ("elements", "Elemente"), ("ports", "Ports"), ("signals", "Signale"), ("connections", "Verbindungen")]:
                    with ui.column().classes("metric px-4 py-2 gap-0"):
                        ui.label(str(stats[key])).classes("metric-value")
                        ui.label(label).classes("metric-label")
                ui.space()
                ui.button("ECAD-Konnektor", icon="account_tree", on_click=ecad_connector_dialog).props("outline no-caps")
                ui.button("Verbindung", icon="add", on_click=add_connection_dialog).props("outline")
            view_options = {
                "architecture": "HW-/ECAD-Architektur",
                "system": "Systemübersicht",
                "domain": "Domain-Fokus",
                "selection": "Auswahlfokus",
            }
            domain_options = {domain.id: domain.name for domain in state.package.domains}
            with ui.row().classes("canvas-viewbar w-full items-center gap-3"):
                def change_view(event) -> None:
                    state.canvas_mode = event.value
                    if state.canvas_mode == "selection" and not state.selected_id:
                        ui.notify("Für den Auswahlfokus zuerst ein Objekt auswählen.", type="warning")
                        state.canvas_mode = "architecture"
                    if state.canvas_mode == "domain":
                        contextual_domain = selected_domain()
                        if contextual_domain:
                            state.focus_domain_id = contextual_domain.id
                    canvas_view.refresh()
                view_toggle = ui.toggle(
                    view_options,
                    value=state.canvas_mode,
                    on_change=change_view,
                ).props("no-caps unelevated dense toggle-color=primary").classes("view-toggle")
                if state.canvas_assignment_phase:
                    view_toggle.props("disable")
                if state.canvas_mode == "domain" and domain_options:
                    focus_select = ui.select(domain_options, value=state.focus_domain_id, label="Fokus-Domain").classes("w-[230px]").props("dense outlined options-dense")
                    def change_focus_domain(event) -> None:
                        state.focus_domain_id = event.value
                        canvas_view.refresh()
                    focus_select.on_value_change(change_focus_domain)
                ui.space()
                filter_label = f"Signaltypen {len(state.signal_types)}/{len(SignalType)}"
                filter_checks = {}
                with ui.button(filter_label, icon="filter_alt").props("outline no-caps"):
                    with ui.menu() as signal_menu:
                        with ui.column().classes("p-3 gap-2 min-w-[340px]"):
                            ui.label("Sichtbare Signaltypen").classes("font-bold")
                            ui.label("Mehrfachauswahl für Verbindungen und Ports im Canvas.").classes("subtle")
                            with ui.grid(columns=2).classes("w-full gap-x-5 gap-y-1"):
                                for signal_type in SignalType:
                                    filter_checks[signal_type.value] = ui.checkbox(
                                        signal_type.value,
                                        value=signal_type.value in state.signal_types,
                                    ).props("dense")
                            with ui.row().classes("w-full items-center justify-between mt-2"):
                                with ui.row().classes("gap-1"):
                                    ui.button(
                                        "Alle",
                                        on_click=lambda: [checkbox.set_value(True) for checkbox in filter_checks.values()],
                                    ).props("flat dense no-caps")
                                    ui.button(
                                        "Keine",
                                        on_click=lambda: [checkbox.set_value(False) for checkbox in filter_checks.values()],
                                    ).props("flat dense no-caps")
                                def apply_signal_filter() -> None:
                                    state.signal_types = {
                                        name for name, checkbox in filter_checks.items() if checkbox.value
                                    }
                                    signal_menu.close()
                                    canvas_view.refresh()
                                ui.button("Übernehmen", icon="check", on_click=apply_signal_filter).props("dense no-caps")
                if state.canvas_mode == "architecture":
                    ui.button("Alle einklappen", icon="unfold_less", on_click=collapse_all_domains).props("flat no-caps")
                    ui.button("Alle aufklappen", icon="unfold_more", on_click=expand_all_domains).props("flat no-caps")
                if state.selected_id and state.canvas_mode != "selection":
                    def enter_selection_focus() -> None:
                        state.canvas_mode = "selection"
                        canvas_view.refresh()
                    ui.button("Auswahl fokussieren", icon="center_focus_strong", on_click=enter_selection_focus).props("outline no-caps")
            canvas = ui.html(architecture_svg(
                state.package,
                state.selected_id,
                view_mode=state.canvas_mode,
                focus_domain_id=state.focus_domain_id,
                collapsed_domain_ids=state.collapsed_domain_ids,
                collapsed_element_ids=state.collapsed_element_ids,
                signal_types=state.signal_types,
                assignment={
                    "active": bool(state.canvas_assignment_phase),
                    "signalId": state.topology_signal_id,
                    "phase": state.canvas_assignment_phase,
                    "hostElementId": state.topology_source_id,
                    "participantElementIds": sorted(state.topology_sink_ids),
                },
            ), sanitize=False).classes("diagram-card w-full")
            canvas.on("xped_select", handle_canvas_select, ["detail"])
            canvas.on("xped_toggle", handle_canvas_toggle, ["detail"])
            canvas.on("xped_clear_selection", clear_canvas_selection, ["detail"])
            canvas.on("xped_assignment_done", lambda _: finish_canvas_assignment(), ["detail"])


    @ui.refreshable
    def inspector_view() -> None:
        with ui.column().classes("w-full p-5 gap-4"):
            ui.label("Ausgewähltes Objekt").classes("panel-heading")
            selected = state.selected_id
            if not selected:
                ui.icon("touch_app", size="40px").classes("text-slate-300 mt-8 self-center")
                ui.label("Wähle ein Objekt im Navigator oder Canvas aus.").classes("subtle self-center text-center")
                return

            obj: object | None = None
            object_type = ""
            object_name = ""
            domain = state.package.find_domain(selected)
            element_result = state.package.find_element(selected)
            port_result = state.package.find_port(selected)
            architecture_signal = state.package.find_architecture_signal(selected)
            connection = next((item for item in state.package.connections if item.id == selected), None)

            if domain:
                obj, object_type, object_name = domain, "Domain", domain.name
            elif element_result:
                obj, object_type, object_name = element_result[1], "Architecture Element", element_result[1].name
            elif port_result:
                obj, object_type, object_name = port_result[2], "Port", port_result[2].name
            elif architecture_signal:
                obj, object_type, object_name = architecture_signal, "Signal / Interface", architecture_signal.name
            elif connection:
                obj, object_type, object_name = connection, "Verbindung", connection.name
            else:
                legacy_signal = state.package.find_signal(selected)
                if legacy_signal:
                    obj, object_type, object_name = legacy_signal[3], "Mitgliedssignal", legacy_signal[3].name

            if obj is None:
                ui.label("Das ausgewählte Objekt ist nicht mehr vorhanden.").classes("subtle")
                return

            show_sha_identity(obj.id, show_reference=False)
            ui.label(object_type).classes('text-xs uppercase text-blue-700')
            ui.label(object_name).classes('text-lg font-bold break-words')
            ui.label(getattr(obj,'description','') or 'Beschreibung: Offen').classes('text-sm whitespace-pre-wrap')
            ui.button('Objekt bearbeiten',icon='edit',on_click=lambda:edit_object_dialog(obj.id)).props('outline no-caps')
            ui.button(f'{object_type} löschen',icon='delete_outline',on_click=lambda:confirm_delete_object(obj.id)).props('flat color=negative no-caps')
            if architecture_signal:
                ui.button('Topologie bearbeiten',icon='account_tree',on_click=lambda:open_topology_drawer(architecture_signal)).props('outline no-caps')
            elif connection and connection.signal_id:
                linked=state.package.find_architecture_signal(connection.signal_id)
                if linked:ui.button('Topologie bearbeiten',icon='account_tree',on_click=lambda:open_topology_drawer(linked)).props('outline no-caps')
            with ui.expansion('Objektkontext',value=False).classes('w-full border rounded'):
                if element_result:ui.label('Domäne: '+element_result[0].name)
                if port_result:ui.label('AE: '+port_result[1].name)
                if connection:
                    for endpoint in connection.endpoints:
                        owner=state.package.find_element(endpoint.element_id)
                        ui.label(endpoint.role.value+': '+(owner[1].name if owner else 'Offen'))
            render_attribute_spaces(obj,save,architecture_views.attribute_space(),state.package,edit_object=edit_object_dialog)

    def property_manager_dialog():
        from .property_manager import open_property_manager
        def commit(candidate,reason):
            previous=state.package
            state.package=candidate
            if save(reason) is False:
                state.package=previous;return False
            return True
        open_property_manager(lambda:state.package,commit)

    @ui.refreshable
    def revisions_view() -> None:
        with ui.column().classes("w-full gap-2"):
            ui.label(
                "Beim Wiederherstellen wird zuerst der aktuelle Arbeitsstand automatisch gesichert. "
                "Anschließend wird der gewählte Stand als neue Revision fortgeführt."
            ).classes("text-sm text-blue-900 bg-blue-50 border border-blue-200 rounded-lg p-3")
            for revision in repository.list_revisions(state.package.project.id):
                with ui.row().classes("w-full items-center border rounded-lg px-3 py-2"):
                    ui.badge(f"R{revision.revision_number}", color="blue-2").props("text-color=blue-9")
                    with ui.column().classes("gap-0 grow"):
                        ui.label(revision.label).classes("font-medium")
                        ui.label(revision.created_at.replace("T", " ")[:19]).classes("text-xs text-slate-500")
                    def confirm_restore(item=revision) -> None:
                        with ui.dialog() as restore_dialog, ui.card().classes("w-[560px] max-w-[94vw] p-6 gap-4"):
                            ui.label(f"Revision R{item.revision_number} wiederherstellen?").classes("text-xl font-bold")
                            ui.label(item.label).classes("font-medium")
                            ui.label(
                                "Der aktuelle Arbeitsstand wird zuerst als eigene Sicherungsrevision gespeichert. "
                                f"Danach wird R{item.revision_number} geladen und ebenfalls als neue Revision dokumentiert."
                            ).classes("text-sm text-slate-600")
                            with ui.row().classes("w-full justify-end"):
                                ui.button("Abbrechen", on_click=restore_dialog.close).props("flat no-caps")
                                def restore() -> None:
                                    try:
                                        state.version = repository.restore_revision(
                                            state.package.project.id, item.id, state.version
                                        )
                                        state.package, state.version = repository.load_project(state.package.project.id)
                                    except (KeyError, VersionConflict, ValueError) as error:
                                        ui.notify(str(error), type="negative", close_button=True); return
                                    prepare_package(state.package)
                                    state.selected_id = None
                                    state.navigator_search_id = None
                                    state.topology_signal_id = None
                                    state.topology_expanded_domain_ids.clear()
                                    state.canvas_assignment_phase = None
                                    requirements_views.reset()
                                    development_views.reset()
                                    if topology_drawer.value:
                                        topology_drawer.toggle()
                                    restore_dialog.close()
                                    apply_workflow_mode(prefer_requirements=True)
                                    refresh_all()
                                    ui.notify(
                                        f"R{item.revision_number} als neuer Arbeitsstand wiederhergestellt; vorheriger Stand gesichert",
                                        type="positive",
                                    )
                                ui.button("Gesichert wiederherstellen", icon="restore", on_click=restore).props("no-caps")
                        restore_dialog.open()
                    ui.button(icon="restore", on_click=confirm_restore).props("flat round dense").tooltip("Gesichert wiederherstellen")

    def open_revision_history() -> None:
        with ui.dialog() as dialog, ui.card().classes(
            "w-[860px] max-w-[96vw] max-h-[90vh] p-6 gap-4 overflow-y-auto"
        ):
            with ui.row().classes("w-full items-center gap-3"):
                ui.icon("history", size="28px", color="primary")
                with ui.column().classes("gap-0 grow"):
                    ui.label("Revisionshistorie").classes("text-xl font-bold")
                    ui.label(
                        "Beim Wiederherstellen wird der aktuelle Arbeitsstand zuerst gesichert."
                    ).classes("subtle")
                ui.button(
                    "Revision erstellen", icon="bookmark_add", on_click=create_revision_dialog,
                ).props("outline no-caps")
                ui.button(icon="close", on_click=dialog.close).props("flat round")
            revisions_view()
        dialog.open()

    def activate_workspace_tab(workspace: str) -> None:
        target = {
            "overview": overview_tab,
            "documents": documents_tab,
            "requirements": requirements_tab,
            "architecture": architecture_tab,
            "hardware_realizations": hardware_realizations_tab,
            "mechanics": mechanics_tab,
            "software": software_tab,
            "standards": standards_tab,
        }.get(workspace, overview_tab)
        tabs.value = target
        tabs.update()
        state.workspace_tab = workspace
        contextual_navigator.refresh()
        contextual_inspector.refresh()

    def activate_architecture_tab() -> None:
        architecture_views.show_hardware()
        activate_workspace_tab("architecture")


    def activate_requirements_tab(
        requirement_id: str | None = None,
        realization_id: str | None = None,
    ) -> None:
        if requirement_id:
            requirements_views.select_requirement(requirement_id)
        elif realization_id:
            requirements_views.select_realization(realization_id)
        activate_workspace_tab("requirements")

    def create_safety_revision(label: str) -> bool:
        if not save("Arbeitsstand vor kontrollierter Übernahme gesichert", refresh_canvas=False):
            return False
        try:
            revision_number = repository.create_revision(state.package.project.id, label)
        except Exception as error:
            ui.notify(f"Sicherungsrevision konnte nicht erzeugt werden: {error}", type="negative", close_button=True)
            return False
        revisions_view.refresh()
        ui.notify(f"Sicherungsrevision R{revision_number} erstellt", type="positive", timeout=1400)
        return True

    def open_system_element(object_id):
        activate_workspace_tab("architecture")
        architecture_views.show_system(object_id)

    from .architecture_masks_ui import create_architecture_masks_ui
    architecture_masks_ui_views = create_architecture_masks_ui(
        COLOR_PALETTE=COLOR_PALETTE,
        PIN_TYPES=PIN_TYPES,
        architecture_catalog=architecture_catalog,
        bus_templates=bus_templates,
        color_palette=color_palette,
        hierarchy_name_is_available=hierarchy_name_is_available,
        save=save,
        state=state,
    )
    add_domain_dialog = architecture_masks_ui_views.add_domain_dialog
    add_element_dialog = architecture_masks_ui_views.add_element_dialog
    add_port_dialog = architecture_masks_ui_views.add_port_dialog
    edit_architecture_signal_dialog = architecture_masks_ui_views.edit_architecture_signal_dialog
    edit_member_dialog = architecture_masks_ui_views.edit_member_dialog
    edit_domain_dialog = architecture_masks_ui_views.edit_domain_dialog
    edit_element_dialog = architecture_masks_ui_views.edit_element_dialog
    edit_port_dialog = architecture_masks_ui_views.edit_port_dialog
    edit_connection_dialog = architecture_masks_ui_views.edit_connection_dialog

    from .catalog_ui import create_catalog_ui
    catalog_ui_views = create_catalog_ui(
        bus_templates=bus_templates,
        confirm_delete_object=confirm_delete_object,
        edit_architecture_signal_dialog=edit_architecture_signal_dialog,
        edit_object_dialog=edit_object_dialog,
        export_buscontents=export_buscontents,
        focus_object=focus_object,
        open_topology_drawer=open_topology_drawer,
        save=save,
        state=state,
    )
    bus_contents_dialog = catalog_ui_views.bus_contents_dialog

    requirements_views = create_requirements_views(
        state,
        save,
        lambda reason: save(reason, refresh_canvas=False),
        activate_architecture_tab,
        activate_workspace_tab,
        bus_templates,
        architecture_catalog,
        ai_provider,
        ai_configuration_dialog,
        create_safety_revision,
        lambda: repository.list_ai_chat_messages(state.package.project.id),
        lambda **values: repository.add_ai_chat_message(
            state.package.project.id, **values
        ),
        lambda message_id, status, review_id=None: repository.update_ai_chat_message(
            state.package.project.id, message_id, status, review_id
        ),
        open_help_dialog,
        analysis_queue,
        switch_project=switch_project,
        edit_all_fields=edit_object_dialog,
        open_system_element=open_system_element,
    )
    development_views = create_development_views(
        state,
        save,
        edit_all_fields=edit_object_dialog,
    )

    def refresh_architecture_shell():
        contextual_navigator.refresh()
        contextual_inspector.refresh()

    def show_hw_object(object_id):
        activate_architecture_tab()
        select(object_id)

    def open_discipline_realization(kind, object_id):
        workspace = "mechanics" if kind == "mechanical" else "software"
        activate_workspace_tab(workspace)
        development_views.select("mechanical_component" if kind == "mechanical" else "software_component", object_id)

    architecture_views = create_architecture_views(
        state, save, canvas_view, show_hw_object, refresh_architecture_shell,
        requirements_views.edit_realization, ecad_connector_dialog, open_discipline_realization, activate_requirements_tab,
        requirements_views.component_details, requirements_views.edit_function_element, requirements_views.select_architecture,
        requirements_views.edit_component,
    )

    @ui.refreshable
    def contextual_navigator() -> None:
        if state.workspace_tab in {"overview", "documents", "requirements", "standards"}:
            requirements_views.navigator(state.workspace_tab)
        elif state.workspace_tab == "architecture":
            if architecture_views.is_hardware():
                ui.label("Hardware / ECAD · " + {"requirement_attributes": "Anforderung", "realization_attributes": "Realisierung", "comparison": "Vergleich"}[architecture_views.attribute_space()]).classes("text-sm px-4 pt-2")
                hierarchy_view()
            else:
                architecture_views.navigator()
        elif state.workspace_tab == "hardware_realizations":
            architecture_views.realization_navigator()
        elif state.workspace_tab in {"mechanics", "software"}:
            development_views.navigator(state.workspace_tab)

    @ui.refreshable
    def contextual_inspector() -> None:
        if state.workspace_tab in {"overview", "documents", "requirements", "standards"}:
            requirements_views.inspector()
        elif state.workspace_tab == "architecture":
            if architecture_views.is_hardware():
                inspector_view()
            else:
                architecture_views.inspector()
        elif state.workspace_tab == "hardware_realizations":
            architecture_views.realization_inspector()
        elif state.workspace_tab in {"mechanics", "software"}:
            development_views.inspector(state.workspace_tab)

    def handle_workspace_tab(value: str) -> None:
        previous_workspace = state.workspace_tab
        label = value.name if hasattr(value, "name") else str(value)
        state.workspace_tab = {
            "Prozessübersicht": "overview",
            "Quellen & Analyse": "documents",
            "Requirements": "requirements",
            "Architektur": "architecture",
            "HW / ECAD": "hardware_realizations",
            "Mechanik / CAD": "mechanics",
            "Software / Firmware": "software",
            "Normen & Standards": "standards",
        }.get(label, "overview")
        if state.workspace_tab == "hardware_realizations":
            architecture_views.realization_activate(state.selected_id if previous_workspace == "architecture" else None)
        if state.workspace_tab != "requirements":
            ui.run_javascript(
                "document.querySelector('.workspace')?.classList.remove('isd-requirements-focus')"
            )
        contextual_navigator.refresh()
        contextual_inspector.refresh()
        requirements_views.record_navigation()

    def apply_workflow_mode(prefer_requirements: bool = False) -> None:
        requirements_enabled = state.package.project.workflow_mode != ProjectWorkflow.MANUAL
        overview_tab.set_visibility(True)
        documents_tab.set_visibility(True)
        requirements_tab.set_visibility(True)
        standards_tab.set_visibility(True)
        target = overview_tab if requirements_enabled and prefer_requirements else architecture_tab
        tabs.value = target
        tabs.update()
        state.workspace_tab = "overview" if target is overview_tab else "architecture"
        contextual_navigator.refresh()
        contextual_inspector.refresh()

    def refresh_all() -> None:
        # Each workspace updates its contents; the shared selection panels update once.
        project_selector.refresh()
        revisions_view.refresh()
        requirements_views.refresh(include_details=False)
        development_views.refresh(include_details=False)
        architecture_views.refresh(include_details=False)
        contextual_navigator.refresh()
        contextual_inspector.refresh()
        topology_drawer_view.refresh()
        save_status.set_text(f"Gespeichert · Stand {state.version}")

    def project_profile_dialog() -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[540px] max-w-[94vw] p-6 gap-4"):
            ui.label("Projektprofil").classes("text-xl font-bold")
            show_sha_identity(state.package.project.id, project=True)
            ui.label("Das Profil verändert Hinweise und Prüfungen. Requirements, Architektur und Tests bleiben in jedem Profil verfügbar.")
            choice = ui.select({ProjectWorkflow.REQUIREMENTS.value: "Lastenheft",
                                ProjectWorkflow.REDESIGN.value: "Redesign",
                                ProjectWorkflow.STUDY.value: "Studie / Prototyp",
                                ProjectWorkflow.MANUAL.value: "Direkter Architekturstart (Bestandsprofil)"},
                               value=state.package.project.workflow_mode.value, label="Startkontext").classes("w-full")
            reason = ui.input("Begründung des Profilwechsels").classes("w-full")
            def change() -> None:
                old = state.package.project.workflow_mode
                new = ProjectWorkflow(choice.value)
                if old == new:
                    dialog.close(); return
                if not (reason.value or "").strip():
                    ui.notify("Bitte den Profilwechsel begründen.", type="warning"); return
                state.package.project.profile_history.append({"at": utc_now(), "from": old.value,
                    "to": new.value, "reason": reason.value.strip()})
                state.package.project.workflow_mode = new
                if save("Projektprofil geändert"):
                    dialog.close(); refresh_all()
            ui.button("Profil ändern", on_click=change).props("no-caps")
        dialog.open()

    from .help_ui import HelpContext,register_help_context
    def active_help():
        workspace=state.workspace_tab
        if workspace=='hardware_realizations':return HelpContext(workspace,architecture_views.realization_selected(),architecture_views.realization_context())
        if workspace=='requirements':return requirements_views.help_context()
        if workspace in {'mechanics','software'}:return HelpContext(workspace,development_views.selected_object())
        if workspace=='architecture':
            obj=find_architecture_object(state.package,state.selected_id or '') if architecture_views.is_hardware() else architecture_views.selected_object()
            discipline=architecture_views.current_discipline()
            return HelpContext('hardware' if discipline=='hardware' else 'mechanics' if discipline=='mechanical' else 'software' if discipline=='software' else 'architecture',obj,architecture_views.attribute_space())
        return HelpContext(workspace)
    from .architecture_editing import find_architecture_object
    register_help_context(active_help)

    with ui.header().classes("h-[72px] px-5 items-center gap-2 no-wrap overflow-hidden"):
        ui.icon("account_tree", size="30px").classes("text-blue-200")
        with ui.column().classes("gap-0 shrink-0"):
            with ui.row().classes("items-center gap-2 no-wrap"):
                ui.label("ISD Suite").classes("app-title")
                ui.badge(f"v{__version__}", color="blue-8").props("text-color=white").classes("text-[10px]")
            ui.label("Integrated System Development").classes("text-[10px] text-blue-200 leading-none")
        ui.separator().props("vertical dark").classes("h-8")
        project_selector()
        ui.button(icon="tune", on_click=project_profile_dialog).props("flat round color=white").tooltip("Projektprofil und Wechselhistorie")
        ui.button(icon="file_download", on_click=export_json).props(
            'flat round color=white aria-label="Gesamtes Projekt als JSON exportieren"'
        ).tooltip("Gesamtes Projekt als JSON exportieren")
        ui.button(icon="file_upload", on_click=import_json_dialog).props(
            'flat round color=white aria-label="Projekt-JSON importieren"'
        ).tooltip("Projekt-JSON importieren")
        ui.button(icon="add", on_click=create_project_dialog).props("flat round color=white").tooltip("Neues Projekt")
        ui.button(icon="delete_outline", on_click=delete_project_dialog).props("flat round color=red-3").tooltip(
            "Aktuelles Systemprojekt vollständig löschen"
        )
        ui.button(icon="admin_panel_settings", on_click=admin_pin_dialog).props("flat round color=white").tooltip(
            "Admin-PIN verwalten"
        )
        ui.button(icon="key", on_click=ai_configuration_dialog).props("flat round color=white").tooltip(
            "KI-Zugang konfigurieren"
        )
        ui.button("Property Manager",icon="tune",on_click=property_manager_dialog).props("flat color=white no-caps")
        ui.button("KI-Assistent", icon="auto_awesome", on_click=requirements_views.open_ai_assistant).props("flat color=white no-caps")
        ui.button("Hilfe", icon="help_outline", on_click=lambda: open_help_dialog("overview")).props("flat color=white no-caps")
        with ui.link(target=TOOL_DOCUMENTATION_URL, new_tab=True).classes(
            "text-white flex items-center justify-center gap-1 px-2 py-2 rounded hover:bg-white/10 shrink-0"
        ).props('aria-label="Tooldokumentation öffnen" title="Tooldokumentation öffnen"'):
            ui.icon("menu_book", size="23px")
            ui.label("Doku").classes("text-sm font-medium")
        ui.space()
        requirements_views.job_status(compact=True)
        with ui.row().classes("items-center gap-1 no-wrap shrink-0"):
            save_status = ui.label(f"Gespeichert · Stand {state.version}").classes("status-pill whitespace-nowrap")
            ui.button("Revision", icon="bookmark_add", on_click=create_revision_dialog).props("flat color=white no-caps")
            ui.button(icon="history", on_click=open_revision_history).props("flat round color=white").tooltip("Revisionshistorie")

    with ui.right_drawer(value=False, fixed=False).classes("topology-drawer").props("bordered overlay width=560") as topology_drawer:
        topology_drawer_view()

    with ui.row().classes("workspace w-full no-wrap"):
        with ui.column().classes("side-panel"):
            contextual_navigator()
        ui.element("div").classes("navigator-resizer").props(
            'role="separator" aria-orientation="vertical" '
            'aria-label="Breite des Navigators anpassen" title="Navigatorbreite ziehen"'
        )
        with ui.column().classes("canvas grow"):
            with ui.tabs().classes("w-full bg-white border-b").props(
                "outside-arrows mobile-arrows dense no-caps"
            ) as tabs:
                overview_tab = ui.tab("Prozessübersicht", icon="account_tree")
                documents_tab = ui.tab("Quellen & Analyse", icon="description")
                requirements_tab = ui.tab("Requirements", icon="fact_check")
                architecture_tab = ui.tab("Architektur", icon="account_tree")
                hardware_realizations_tab = ui.tab("HW / ECAD", icon="memory")
                mechanics_tab = ui.tab("Mechanik / CAD", icon="precision_manufacturing")
                software_tab = ui.tab("Software / Firmware", icon="code")
                standards_tab = ui.tab("Normen & Standards", icon="gavel")
            tabs.on_value_change(lambda event: handle_workspace_tab(event.value))
            initial_tab = overview_tab if state.package.project.workflow_mode != ProjectWorkflow.MANUAL else architecture_tab
            with ui.tab_panels(tabs, value=initial_tab).classes("w-full bg-transparent p-0"):
                with ui.tab_panel(overview_tab).classes("p-0"):
                    with ui.row().classes("w-full items-center gap-2 px-5 py-2 border-b bg-white flex-wrap"):
                        ui.label("Projektstand").classes("font-semibold grow")
                        ui.button("Revisionen", icon="history", on_click=open_revision_history).props("outline dense no-caps")
                    requirements_views.overview_workspace()
                with ui.tab_panel(documents_tab).classes("p-0"):
                    requirements_views.documents_workspace()
                with ui.tab_panel(requirements_tab).classes("p-0"):
                    with ui.row().classes("w-full items-center gap-2 px-5 py-2 border-b bg-white"):
                        ui.label("Requirements-Austausch").classes("font-semibold grow")
                        ui.button("Importieren / exportieren", icon="import_export", on_click=requirements_exchange_dialog).props("outline dense no-caps")
                    requirements_views.requirements_workspace()
                with ui.tab_panel(architecture_tab).classes("p-0"):
                    with ui.row().classes("w-full items-center gap-2 px-5 py-2 border-b bg-white flex-wrap"):
                        ui.label("Architekturverwaltung").classes("font-semibold grow")
                        ui.button("Property Manager", icon="tune", on_click=property_manager_dialog).props("outline dense no-caps")
                        ui.button("Architektur-PDF", icon="picture_as_pdf", on_click=export_pdf).props("outline dense no-caps")
                    architecture_views.workspace()
                with ui.tab_panel(hardware_realizations_tab).classes("p-0"):
                    architecture_views.hardware_realizations()
                with ui.tab_panel(mechanics_tab).classes("p-0"):
                    development_views.mechanics_workspace()
                with ui.tab_panel(software_tab).classes("p-0"):
                    development_views.software_workspace()
                with ui.tab_panel(standards_tab).classes("p-0"):
                    requirements_views.standards_workspace()
        with ui.column().classes("inspector"):
            contextual_inspector()

    documents_tab.set_visibility(True)
    requirements_tab.set_visibility(True)
    standards_tab.set_visibility(True)
    state.workspace_tab = "overview" if initial_tab is overview_tab else "architecture"


def build_documentation_page(chapter: str = '', q: str = '') -> None:
    """The canonical manual with chapter navigation, search and deep links."""
    from .handbook import render_handbook
    ui.colors(primary='#0b4f9c', secondary='#0f766e', accent='#d97706')
    ui.add_css('body { background:#eef3f9; color:#172b44; }')
    with ui.header().classes('h-[66px] px-5 items-center gap-3 bg-slate-900'):
        ui.icon('menu_book', size='29px').classes('text-blue-200')
        ui.label('ISD Suite · Nutzerhandbuch').classes('text-lg font-bold grow')
        ui.link('Zur Anwendung', target='/').classes('text-white border border-white/50 rounded px-3 py-2')
    with ui.column().classes('w-full max-w-[1560px] mx-auto p-5'):
        render_handbook(chapter, q)


ui.page(TOOL_DOCUMENTATION_URL)(build_documentation_page)
ui.page("/")(build_page)


def run() -> None:
    ui.run(
        title="ISD Suite",
        favicon="◇",
        storage_secret=os.getenv("ISD_SUITE_STORAGE_SECRET", os.getenv("ECAD_SUITE_STORAGE_SECRET", os.getenv("XPED_AUTO_STORAGE_SECRET", "local-development-secret-change-me"))),
        host=os.getenv("ISD_SUITE_HOST", os.getenv("ECAD_SUITE_HOST", os.getenv("XPED_AUTO_HOST", "127.0.0.1"))),
        port=int(os.getenv("ISD_SUITE_PORT", os.getenv("ECAD_SUITE_PORT", os.getenv("XPED_AUTO_PORT", "8080")))),
        show=True,
        reload=False,
    )


if __name__ in {"__main__", "__mp_main__"}:
    run()
