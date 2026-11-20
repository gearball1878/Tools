"""JSON project import dialog. Persistence and validation stay in the repository."""
from __future__ import annotations

from typing import Callable

from nicegui import events, ui
from pydantic import ValidationError

from .models import ArchitecturePackage, ProjectWorkflow
from .project_import import WORKFLOW_LABELS
from .repository import ArchitectureRepository, VersionConflict


def open_project_import_dialog(
    repository: ArchitectureRepository,
    current_project_id: str,
    current_version: int,
    show_imported_project: Callable[[ArchitecturePackage, int], None],
) -> None:
    pending: dict[str, bytes] = {"data": b""}
    with ui.dialog() as dialog, ui.card().classes("w-[650px] max-w-[92vw] p-6 gap-4"):
        ui.label("Projekt-JSON importieren").classes("dialog-title")
        ui.label(
            "1 · JSON-Datei auswählen und prüfen. 2 · Startkontext des importierten "
            "Projekts festlegen. 3 · Übernahmeart wählen."
        ).classes("text-sm text-slate-600 leading-relaxed")
        workflow_choice = ui.select(
            WORKFLOW_LABELS,
            value=None,
            label="Startkontext des importierten Projekts (Pflichtfeld)",
        ).props('outlined options-dense').classes("w-full")
        ui.label(
            "Der gewählte Typ gilt auch beim Import als Revision. Quelldaten und "
            "Requirements bleiben erhalten."
        ).classes("text-xs text-slate-600")

        @ui.refreshable
        def import_preview() -> None:
            if not pending["data"]:
                return
            try:
                candidate = repository.preview_project_import(pending["data"])
                ui.label(f"Datei geprüft: {candidate.project.name}").classes("font-semibold")
                ui.label(
                    f"Startkontext in der Datei: {WORKFLOW_LABELS[candidate.project.workflow_mode.value]}"
                ).classes("text-sm text-slate-600")
                ui.label(
                    f"{len(candidate.requirements)} Requirements · {len(candidate.domains)} Domains · "
                    f"{len(candidate.technical_realizations)} technische Realisierungen"
                ).classes("text-sm")
                if candidate.source_documents:
                    ui.label(
                        "Originaldokumente sind nur verfügbar, wenn ihre Anhänge lokal vorhanden sind."
                    ).classes("text-xs text-amber-800")

                def commit(current_project: bool) -> None:
                    if not workflow_choice.value:
                        ui.notify("Bitte zuerst einen Projekttyp auswählen.", type="warning")
                        return
                    try:
                        workflow = ProjectWorkflow(workflow_choice.value)
                        if current_project:
                            imported, version = repository.import_into_project(
                                current_project_id, pending["data"], current_version,
                                workflow=workflow,
                            )
                        else:
                            imported, version = repository.import_project(
                                pending["data"], workflow=workflow,
                            )
                        show_imported_project(imported, version)
                        dialog.close()
                        ui.notify(
                            "JSON als neuer Revisionsstand importiert" if current_project else
                            "JSON als neues Projekt importiert", type="positive",
                        )
                    except (ValueError, KeyError, VersionConflict, ValidationError) as error:
                        ui.notify(f"Import fehlgeschlagen: {error}", type="negative", close_button=True)

                with ui.row().classes("w-full gap-2 flex-wrap"):
                    ui.button(
                        "In dieses Projekt als Revision", icon="history",
                        on_click=lambda: commit(True),
                    ).props("no-caps").bind_enabled_from(workflow_choice, "value", bool)
                    ui.button(
                        "Als neues Projekt", icon="create_new_folder",
                        on_click=lambda: commit(False),
                    ).props("outline no-caps").bind_enabled_from(workflow_choice, "value", bool)
            except (ValueError, ValidationError) as error:
                ui.label(f"Datei ungültig: {error}").classes("text-sm text-red-700")

        async def handle_upload(event: events.UploadEventArguments) -> None:
            pending["data"] = await event.file.read()
            import_preview.refresh()

        ui.upload(
            label="JSON-Datei auswählen", on_upload=handle_upload, auto_upload=True,
        ).props('accept=".json,application/json" max-files=1').classes("w-full")
        import_preview()
        with ui.row().classes("w-full justify-end"):
            ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")
    dialog.open()
