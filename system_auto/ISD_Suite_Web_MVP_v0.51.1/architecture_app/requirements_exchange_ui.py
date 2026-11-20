"""Requirements interchange dialog with preview and transactional model validation."""
from __future__ import annotations

from typing import Callable, Protocol

from nicegui import events, ui

from .models import ArchitecturePackage
from .requirements_exchange import FIELDS, PROFILES, apply_import, detected_columns, exchange_limitations, export_requirements, parse_requirements, preview_import


class ExchangeState(Protocol):
    package: ArchitecturePackage


def open_requirements_exchange_dialog(
    state: ExchangeState,
    create_safety_revision: Callable[[str], bool],
    save: Callable[[str], bool],
) -> None:
        upload_state: dict[str, object] = {"data": b"", "filename": ""}
        with ui.dialog() as dialog, ui.card().classes("w-[760px] max-w-[95vw] p-6 gap-4"):
            ui.label("Requirements austauschen").classes("text-xl font-bold")
            ui.label("SPOT-JSON bleibt führend. Importe werden vor der Übernahme geprüft und sichern den bisherigen Stand als Revision.").classes("text-sm text-slate-600")
            profile = ui.select(PROFILES, value="generic", label="Austauschprofil").classes("w-full")
            for notice in exchange_limitations(state.package):
                ui.label(notice).classes("text-xs text-amber-900")
            ui.label("DOORS, Polarion und Jama sind Feldvorlagen; vor Produktivübernahme das konkrete Zieltool-Profil prüfen.").classes("text-xs text-slate-600")
            with ui.row().classes("w-full gap-2 flex-wrap"):
                for suffix in ("reqif", "xlsx", "csv", "docx", "pdf"):
                    def download(fmt: str = suffix) -> None:
                        try:
                            content = export_requirements(state.package, fmt, str(profile.value))
                            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in state.package.project.name)
                            ui.download(content, f"{safe}_requirements.{fmt}")
                        except Exception as error:
                            ui.notify(f"Export fehlgeschlagen: {error}", type="negative")
                    ui.button(suffix.upper(), icon="download", on_click=download).props("outline dense no-caps")
            ui.separator()
            ui.label("Import in das aktuelle Systemprojekt").classes("font-semibold")
            mapping_text = ui.textarea(
                "Optionales Spaltenmapping (je Zeile: Originalspalte = Zielfeld)",
                placeholder="Objektkennung = identifier\nBeschreibung = text",
            ).props("outlined rows=2").classes("w-full")
            ui.label("Zielfelder: " + ", ".join(FIELDS)).classes("text-xs text-slate-500")
            @ui.refreshable
            def preview_area() -> None:
                data = upload_state["data"]
                if not data:
                    return
                try:
                    mappings: dict[str, str] = {}
                    for line in str(mapping_text.value or "").splitlines():
                        if "=" in line:
                            column, field = (part.strip() for part in line.split("=", 1))
                            if field not in FIELDS:
                                raise ValueError(f"Unbekanntes Zielfeld: {field}")
                            mappings[column] = field
                    rows = parse_requirements(data, str(upload_state["filename"]), mappings)
                    preview = preview_import(state.package, rows)
                    ui.label("Quellspalten: " + ", ".join(detected_columns(data, str(upload_state["filename"])))).classes("text-xs text-slate-600")
                    ui.label(f"{len(rows)} Zeilen · {preview.new_count} neu · {len(preview.duplicates)} Dubletten · {len(preview.issues)} fehlerhaft").classes("font-semibold")
                    for issue in (preview.issues + preview.duplicates)[:12]:
                        ui.label(issue).classes("text-xs text-amber-800")
                    with ui.scroll_area().classes("w-full max-h-40 border rounded p-2"):
                        for row in rows[:12]:
                            ui.label(f"{row.get('identifier') or row.get('external_id') or '—'} · {row.get('title') or row.get('text', '')[:90]}").classes("text-sm")
                    def commit() -> None:
                        if not preview.new_count:
                            ui.notify("Keine neuen gültigen Anforderungen vorhanden.", type="warning")
                            return
                        current_preview = preview_import(state.package, rows)
                        if current_preview.accepted_indices != preview.accepted_indices:
                            preview_area.refresh()
                            ui.notify("Das Projekt hat sich geändert. Bitte die aktualisierte Vorschau prüfen.", type="warning")
                            return
                        if not create_safety_revision("Vor Requirements-Import"):
                            return
                        candidate = state.package.model_copy(deep=True)
                        try:
                            count = apply_import(candidate, current_preview, str(profile.value))
                            old_package = state.package
                            state.package = ArchitecturePackage.model_validate(candidate.export_dict())
                            if save(f"{count} Requirements importiert"):
                                dialog.close()
                            else:
                                state.package = old_package
                        except Exception as error:
                            if "old_package" in locals():
                                state.package = old_package
                            ui.notify(f"Import fehlgeschlagen: {error}", type="negative")
                    ui.button("Geprüfte Anforderungen übernehmen", icon="publish", on_click=commit).props("no-caps")
                except Exception as error:
                    ui.label(str(error)).classes("text-red-700 text-sm")
            async def uploaded(event: events.UploadEventArguments) -> None:
                upload_state["data"] = await event.file.read()
                upload_state["filename"] = event.file.name
                preview_area.refresh()
            ui.upload(label="ReqIF, CSV, XLSX oder DOCX wählen", on_upload=uploaded, auto_upload=True).props('accept=".reqif,.reqifz,.csv,.xlsx,.docx" max-files=1').classes("w-full")
            ui.button("Vorschau mit Mapping aktualisieren", on_click=preview_area.refresh).props("flat no-caps")
            preview_area()
            ui.button("Schließen", on_click=dialog.close).props("flat no-caps")
        dialog.open()
