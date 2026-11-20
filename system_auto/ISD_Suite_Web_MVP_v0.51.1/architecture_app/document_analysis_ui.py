"""Document upload, extraction context and recovery.

Explicit callbacks keep project state in the page controller.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from .requirements_presentation import MAX_AI_DOCUMENT_CONTEXT_CHARACTERS, MAX_AI_CHARACTERS_PER_DOCUMENT, MAX_DOCUMENT_PREVIEW_CHARACTERS
from hashlib import sha256
from nicegui import events, run, ui
from .analysis_queue import JOB_STATUS_LABELS
from .attachment_store import attachment_is_available, read_attachment, store_attachment
from .document_ingestion import ExtractedDocument, deserialize_document_context, extract_document, format_document_context, serialize_document_context
from .models import SourceDocument
from .requirements_service import recover_document_context_metadata, validate_document_context_recovery

@dataclass(frozen=True)
class DocumentAnalysisUiViews:
    document_context_available: Callable[..., Any]
    load_document_context: Callable[..., Any]
    build_ai_document_context: Callable[..., Any]
    open_document_context_dialog: Callable[..., Any]
    document_import_dialog: Callable[..., Any]
    document_context_recovery_dialog: Callable[..., Any]


def create_document_analysis_ui(
    *,
    active_document_analysis,
    ai_provider,
    analysis_queue,
    clear_selection,
    configure_ai,
    filters,
    import_batch,
    import_jobs,
    package,
    page_state,
    refresh,
    save,
    selection,
    set_job,
) -> DocumentAnalysisUiViews:
    def document_context_available(source: SourceDocument) -> bool:
        return bool(
            attachment_is_available(package().project.id, source.context_path)
            or attachment_is_available(package().project.id, source.attachment_path)
        )

    def load_document_context(source: SourceDocument) -> ExtractedDocument:
        project_id = package().project.id
        if attachment_is_available(project_id, source.context_path):
            context_bytes = read_attachment(project_id, source.context_path)
            if (
                source.context_checksum_sha256
                and sha256(context_bytes).hexdigest() != source.context_checksum_sha256
            ):
                raise ValueError(f"Der gespeicherte Kontext von „{source.name}“ hat eine ungültige Prüfsumme.")
            context = deserialize_document_context(context_bytes)
            if context.checksum_sha256 and context.checksum_sha256 != source.checksum_sha256:
                raise ValueError(f"Der gespeicherte Kontext von „{source.name}“ gehört nicht zum Originaldokument.")
            return context
        if attachment_is_available(project_id, source.attachment_path):
            return extract_document(
                read_attachment(project_id, source.attachment_path),
                source.file_name,
                source.media_type,
            )
        raise FileNotFoundError(
            f"Für „{source.name}“ ist weder ein extrahierter Kontext noch das Originaldokument lokal verfügbar."
        )

    def build_ai_document_context(
        document_ids: list[str],
        strict: bool = True,
    ) -> list[dict[str, object]]:
        selected_sources = [
            item for item in package().source_documents if item.id in set(document_ids)
        ]
        if not selected_sources:
            return []
        per_document_limit = min(
            MAX_AI_CHARACTERS_PER_DOCUMENT,
            max(6_000, MAX_AI_DOCUMENT_CONTEXT_CHARACTERS // len(selected_sources)),
        )
        remaining = MAX_AI_DOCUMENT_CONTEXT_CHARACTERS
        result: list[dict[str, object]] = []
        unavailable: list[str] = []
        for source in selected_sources:
            if remaining <= 0:
                break
            try:
                extracted = load_document_context(source)
            except (FileNotFoundError, ValueError, RuntimeError) as error:
                unavailable.append(source.name)
                if not strict:
                    result.append({
                        "documentId": source.id,
                        "name": source.name,
                        "fileName": source.file_name,
                        "contentAvailable": False,
                        "contextError": str(error),
                    })
                continue
            content, truncated = format_document_context(
                extracted,
                max_characters=min(per_document_limit, remaining),
            )
            remaining -= len(content)
            result.append({
                "documentId": source.id,
                "name": source.name,
                "fileName": source.file_name,
                "sourceChecksumSha256": source.checksum_sha256,
                "sectionCount": len(extracted.sections),
                "content": content,
                "truncated": truncated,
                "analysisProfile": str(source.properties.get("analysisProfile") or ""),
                "analysisPipeline": str(source.properties.get("analysisPipeline") or ""),
                "persistedAnalysis": (
                    {
                        "analysisId": analysis.id,
                        "revision": analysis.revision_number,
                        "sheetInventory": [item.model_dump(mode="json") for item in analysis.sheet_inventory],
                        "components": [item.model_dump(mode="json") for item in analysis.components],
                        "technicalRealizations": [
                            item.model_dump(mode="json") for item in analysis.technical_realizations
                        ],
                        "architectureDomains": [
                            item.model_dump(mode="json") for item in analysis.architecture_domains
                        ],
                        "architectureElements": [
                            item.model_dump(mode="json") for item in analysis.architecture_elements
                        ],
                        "architectureInterfaces": [
                            item.model_dump(mode="json") for item in analysis.architecture_interfaces
                        ],
                        "internalNets": [item.model_dump(mode="json") for item in analysis.internal_nets],
                        "openQuestions": analysis.open_questions,
                        "conflicts": analysis.conflicts,
                    }
                    if (analysis := active_document_analysis(source.id)) is not None
                    else None
                ),
            })
        if unavailable and strict:
            raise ValueError(
                "Dokumentkontext lokal nicht verfügbar: " + ", ".join(unavailable)
            )
        return result

    def open_document_context_dialog(source: SourceDocument) -> None:
        try:
            extracted = load_document_context(source)
            preview, truncated = format_document_context(
                extracted,
                max_characters=MAX_DOCUMENT_PREVIEW_CHARACTERS,
            )
            full_text, _ = format_document_context(extracted)
        except (FileNotFoundError, ValueError, RuntimeError) as error:
            ui.notify(str(error), type="warning", close_button=True)
            return
        with ui.dialog() as dialog, ui.card().classes("w-[1000px] max-w-[97vw] h-[90vh] p-0 gap-0"):
            with ui.row().classes("w-full items-center gap-3 px-5 py-4 border-b bg-slate-50"):
                ui.icon("article", size="28px", color="primary")
                with ui.column().classes("gap-0 grow min-w-0"):
                    ui.label(source.name).classes("text-xl font-bold")
                    ui.label(
                        f"{len(extracted.sections)} Abschnitte · {extracted.character_count:,} Zeichen · lokal wiederverwendbarer KI-Kontext".replace(",", ".")
                    ).classes("subtle")
                ui.button(
                    icon="download",
                    on_click=lambda: ui.download(
                        full_text.encode("utf-8"),
                        f"{source.name}_Kontext.txt",
                        media_type="text/plain",
                    ),
                ).props("flat round dense").tooltip("Extrahierten Kontext herunterladen")
                ui.button(icon="close", on_click=dialog.close).props("flat round dense")
            with ui.column().classes("w-full grow min-h-0 p-5 gap-3"):
                ui.label(
                    "Dieser Text wurde beim Import extrahiert und kann für weitere KI-Fragen verwendet werden, ohne das Dokument erneut analysieren zu lassen."
                ).classes("text-sm text-blue-900 bg-blue-50 border border-blue-200 rounded-lg p-3")
                if truncated:
                    ui.label(
                        "Die Bildschirmvorschau ist aus Performancegründen gekürzt. Der Download enthält den vollständigen extrahierten Kontext."
                    ).classes("text-xs text-amber-800")
                ui.textarea("Extrahierter Dokumentinhalt", value=preview).props(
                    "readonly outlined rows=24"
                ).classes("w-full grow document-context-preview")
        dialog.open()

    def document_import_dialog() -> None:
        analysis_queue.ensure_started()
        job_repository = analysis_queue.repository
        project_id = package().project.id
        batch_id = (
            job_repository.active_ai_document_batch(project_id)
            or analysis_queue.new_batch_id()
        )
        import_jobs.clear()
        import_batch.update({
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
            "started": False,
        })

        def synchronize_jobs() -> None:
            summary = analysis_queue.batch_summary(project_id, batch_id)
            import_jobs.clear()
            for item in summary["jobs"]:
                import_jobs[item.id] = {
                    "id": item.id,
                    "name": item.file_name,
                    "display_name": item.display_name,
                    "document_type": item.document_type,
                    "document_context": item.document_context,
                    "analysis_instructions": item.analysis_instructions,
                    "status": JOB_STATUS_LABELS.get(item.status, item.status),
                    "raw_status": item.status,
                    "detail": item.detail,
                    "media_type": item.media_type,
                    "extracted": item.context_path or None,
                    "result_document_id": item.result_document_id,
                    "attempts": item.attempts,
                }
            running_job = next(
                (item for item in summary["jobs"] if item.status == "Running"), None
            )
            import_batch.update({
                "common_guidance": next(
                    (item.common_guidance for item in summary["jobs"] if item.common_guidance),
                    import_batch["common_guidance"],
                ),
                "use_ai": next(
                    (item.use_ai for item in summary["jobs"]),
                    import_batch["use_ai"],
                ),
                "running": summary["running"],
                "total": summary["total"],
                "processed": summary["processed"],
                "succeeded": summary["succeeded"],
                "failed": summary["failed"],
                "current_index": running_job.position if running_job else 0,
                "current_name": running_job.file_name if running_job else "",
                "project_changed": bool(summary["succeeded"]),
                "started": any(
                    item.attempts > 0 or item.status in {"Queued", "Running", "ReviewReady"}
                    for item in summary["jobs"]
                ),
            })

        synchronize_jobs()
        dialog_controls: dict[str, Any] = {}
        with ui.dialog() as dialog, ui.card().classes(
            "w-[920px] max-w-[96vw] max-h-[92vh] overflow-y-auto p-6 gap-4"
        ):
            ui.label("Anforderungsdokumente importieren und analysieren").classes("text-xl font-bold")
            ui.label(
                "Bis zu 20 Dokumente können gemeinsam ausgewählt werden: PDF, DOCX, TXT, Markdown, "
                "CSV/TSV-BOM, textuelle Netzlisten, XML oder JSON. "
                "Die Dateien werden zunächst nur eingelesen. Danach können Name, Dokumentart, Kontext und "
                "Analyseauftrag für jedes Dokument einzeln ergänzt werden. Erst der Analyse-Button startet die KI. "
                "Nach der Analyse bleibt jedes Dokument unter „Dokumente & Analysen“ sichtbar. "
                "Das Originaldokument wird nicht in das SPOT-JSON eingebettet."
            ).classes("text-sm text-slate-600")
            with ui.row().classes("w-full items-center gap-2 text-xs font-semibold text-slate-600"):
                ui.badge("1 · Dateien auswählen", color="blue-1").props("text-color=blue-9")
                ui.icon("arrow_forward", size="16px")
                ui.badge("2 · Angaben je Dokument", color="blue-1").props("text-color=blue-9")
                ui.icon("arrow_forward", size="16px")
                ui.badge("3 · Analyse starten", color="blue-1").props("text-color=blue-9")
            use_ai = ui.checkbox(
                "Mit konfigurierter KI analysieren",
                value=bool(import_batch["use_ai"] and ai_provider.is_ready),
            )
            use_ai.set_enabled(ai_provider.is_ready and not import_batch["running"])

            def update_batch_ai_mode(value: Any) -> None:
                import_batch["use_ai"] = bool(value)
                for item in job_repository.list_ai_document_jobs(project_id, batch_id):
                    if item.status in {"Ready", "Failed"}:
                        job_repository.update_ai_document_job(item.id, use_ai=bool(value))

            use_ai.on_value_change(lambda event: update_batch_ai_mode(event.value))
            analysis_prompt = ui.textarea(
                "Gemeinsamer Analyseauftrag für alle Dokumente (optional)",
                value=str(import_batch["common_guidance"]),
                placeholder=(
                    "Zum Beispiel: Achte besonders auf feste Bauteilvorgaben, mechanische Randbedingungen "
                    "und sicherheitsrelevante Anforderungen."
                ),
            ).props("outlined autogrow").classes("w-full")

            def update_common_guidance(value: Any) -> None:
                text = str(value or "")
                import_batch["common_guidance"] = text
                for item in job_repository.list_ai_document_jobs(project_id, batch_id):
                    if item.status in {"Ready", "Failed"}:
                        job_repository.update_ai_document_job(item.id, common_guidance=text)

            analysis_prompt.on_value_change(lambda event: update_common_guidance(event.value))

            def sync_import_ai_state() -> None:
                import_batch["use_ai"] = ai_provider.is_ready
                use_ai.value = bool(import_batch["use_ai"])
                use_ai.set_enabled(ai_provider.is_ready and not import_batch["running"])
                use_ai.update()
                import_ai_status.refresh()

            @ui.refreshable
            def import_ai_status() -> None:
                if ai_provider.is_ready:
                    ui.label(
                        f"Sofort einsatzbereit: {ai_provider.display_name} · {ai_provider.model_name}"
                    ).classes("text-sm text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-lg p-3")
                else:
                    with ui.row().classes("w-full items-center gap-2 text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-3"):
                        ui.label(
                            "Kein KI-Zugang konfiguriert. Ohne Konfiguration wird die lokale Regelanalyse verwendet."
                        ).classes("grow")
                        ui.button(
                            "Jetzt konfigurieren",
                            icon="key",
                            on_click=lambda: configure_ai(sync_import_ai_state),
                        ).props("outline dense no-caps")

            import_ai_status()

            from .analysis_profiles import profile_options, suggest_analysis_profile
            document_types = profile_options()

            def update_import_job(job_key: str, field: str, value: Any) -> None:
                job = import_jobs.get(job_key)
                if job is not None:
                    job[field] = value
                    job_repository.update_ai_document_job(job_key, **{field: value})

            def remove_import_job(job_key: str) -> None:
                job = import_jobs.get(job_key)
                if job is None or job.get("raw_status") in {"Queued", "Running"}:
                    return
                analysis_queue.delete_job(project_id, job_key)
                synchronize_jobs()
                import_status.refresh()

            async def trigger_import_analysis() -> None:
                await analyze_import_jobs()

            @ui.refreshable
            def import_status() -> None:
                synchronize_jobs()
                if not import_jobs:
                    ui.label(
                        "Noch keine Datei ausgewählt. Eine Auswahl startet noch keine KI-Analyse."
                    ).classes("subtle")
                    return
                with ui.column().classes("w-full gap-2"):
                    if import_batch["total"] and import_batch["started"]:
                        with ui.card().classes(
                            "w-full p-4 gap-2 border border-blue-200 bg-blue-50"
                            if import_batch["running"]
                            else "w-full p-4 gap-2 border border-slate-200 bg-slate-50"
                        ):
                            with ui.row().classes("w-full items-center gap-2"):
                                if import_batch["running"]:
                                    ui.spinner(size="20px", color="primary")
                                    ui.label(
                                        f"Dokument {import_batch['current_index']} von {import_batch['total']} wird analysiert"
                                    ).classes("font-semibold text-blue-900")
                                    ui.label(str(import_batch["current_name"])).classes(
                                        "grow text-sm text-blue-800 truncate"
                                    )
                                else:
                                    ui.icon("task_alt", color="positive")
                                    ui.label("Importserie abgeschlossen").classes("font-semibold")
                            ui.linear_progress(
                                value=(import_batch["processed"] / import_batch["total"])
                                if import_batch["total"] else 0,
                                show_value=False,
                            ).classes("w-full")
                            ui.label(
                                f"{import_batch['processed']}/{import_batch['total']} verarbeitet · "
                                f"{import_batch['succeeded']} erfolgreich · {import_batch['failed']} fehlgeschlagen"
                            ).classes("text-xs text-slate-600")
                    for job_key, job in import_jobs.items():
                        color = {
                            "Wird eingelesen": "blue-2",
                            "Bereit zur Analyse": "amber-2",
                            "Wartet auf Analyse": "grey-4",
                            "Wird analysiert": "blue-2",
                            "Zur Prüfung bereit": "green-2",
                            "Fehlgeschlagen": "red-2",
                        }.get(job["status"], "grey-4")
                        with ui.card().classes("w-full p-4 gap-3 border"):
                            with ui.row().classes("w-full items-center"):
                                ui.icon("description", color="primary")
                                ui.label(job["name"]).classes("font-medium grow")
                                ui.badge(job["status"], color=color).props("text-color=grey-9")
                                remove_button = ui.button(
                                    icon="close",
                                    on_click=lambda key=job_key: remove_import_job(key),
                                ).props("flat round dense").tooltip("Aus dieser Importserie entfernen")
                                remove_button.set_enabled(not import_batch["running"])
                            if job.get("detail"):
                                ui.label(job["detail"]).classes(
                                    "text-xs text-red-700" if job["status"] == "Fehlgeschlagen"
                                    else "text-xs text-slate-600"
                                )
                            if job.get("raw_status") == "Failed" and not job.get("extracted"):
                                ui.button(
                                    "Einlesen erneut versuchen",
                                    icon="replay",
                                    on_click=lambda _, key=job_key: (
                                        analysis_queue.retry_preparation(key),
                                        refresh_import_status(),
                                    ),
                                ).props("outline dense no-caps")

                            if (
                                job.get("extracted") is not None
                                and job.get("raw_status") in {"Ready", "Failed"}
                            ):
                                with ui.row().classes("w-full gap-3 items-start"):
                                    display_name = ui.input(
                                        "Anzeigename",
                                        value=job["display_name"],
                                    ).props("outlined dense").classes("grow")
                                    document_type = ui.select(
                                        document_types,
                                        value=job["document_type"],
                                        label="Analyseprofil",
                                    ).props("outlined dense options-dense").classes("w-[310px]")
                                document_context = ui.textarea(
                                    "Rolle / Kontext des Dokuments (optional)",
                                    value=job["document_context"],
                                    placeholder=(
                                        "Zum Beispiel: Verbindliches Kundenlastenheft, Kapitel 5 ersetzt die ältere Spezifikation; "
                                        "Begriffe ECU und Controller sind synonym."
                                    ),
                                ).props("outlined autogrow").classes("w-full")
                                analysis_instructions = ui.textarea(
                                    "Analyseauftrag nur für dieses Dokument (optional)",
                                    value=job["analysis_instructions"],
                                    placeholder=(
                                        "Zum Beispiel: Extrahiere nur Schnittstellen- und Spannungsanforderungen; "
                                        "Tabellen im Anhang haben Vorrang."
                                    ),
                                ).props("outlined autogrow").classes("w-full")
                                display_name.on_value_change(
                                    lambda event, key=job_key: update_import_job(key, "display_name", event.value)
                                )
                                document_type.on_value_change(
                                    lambda event, key=job_key: update_import_job(key, "document_type", event.value)
                                )
                                document_context.on_value_change(
                                    lambda event, key=job_key: update_import_job(key, "document_context", event.value)
                                )
                                analysis_instructions.on_value_change(
                                    lambda event, key=job_key: update_import_job(key, "analysis_instructions", event.value)
                                )
                                for field in (display_name, document_type, document_context, analysis_instructions):
                                    field.set_enabled(not import_batch["running"])

                    ready_jobs = [
                        job for job in import_jobs.values()
                        if job.get("extracted") is not None
                        and job["status"] in {"Bereit zur Analyse", "Fehlgeschlagen"}
                    ]
                    running = bool(import_batch["running"]) or any(
                        job["status"] == "Wird eingelesen" for job in import_jobs.values()
                    )
                    with ui.row().classes("w-full justify-end items-center gap-3 pt-2"):
                        ui.label(
                            f"{len(ready_jobs)} Dokument(e) bereit"
                        ).classes("text-sm text-slate-600")
                        start_button = ui.button(
                            "Konfigurierte Dokumente analysieren",
                            icon="psychology",
                            on_click=trigger_import_analysis,
                        ).props("no-caps")
                        start_button.set_enabled(bool(ready_jobs) and not running)

            def refresh_import_status() -> None:
                try:
                    import_status.refresh()
                except RuntimeError:
                    # The queue owns its state. A closed client must not abort the
                    # remaining documents in a running multi-document analysis.
                    pass

            def set_import_controls_enabled(enabled: bool) -> None:
                use_ai.set_enabled(enabled and ai_provider.is_ready)
                analysis_prompt.set_enabled(enabled)
                upload_control = dialog_controls.get("upload")
                if upload_control is not None:
                    upload_control.set_enabled(enabled)
                for name in ("close", "results"):
                    control = dialog_controls.get(name)
                    if control is not None:
                        control.set_enabled(True)

            async def handle_upload(event: events.UploadEventArguments) -> None:
                if import_batch["running"]:
                    ui.notify("Während der Analyse können keine weiteren Dokumente ergänzt werden.", type="warning")
                    return
                file_name = getattr(event.file, "name", "requirements.txt")
                try:
                    content = await event.file.read()
                    created_job = await analysis_queue.submit_upload(
                        project_id=project_id,
                        batch_id=batch_id,
                        file_name=file_name,
                        content=content,
                        media_type=getattr(event.file, "content_type", "") or "",
                        document_type=suggest_analysis_profile(
                            file_name, getattr(event.file, "content_type", "") or ""
                        ),
                    )
                    job_repository.update_ai_document_job(
                        created_job.id,
                        common_guidance=str(import_batch["common_guidance"] or ""),
                        use_ai=bool(import_batch["use_ai"]),
                    )
                    synchronize_jobs()
                except Exception as error:
                    ui.notify(
                        f"Dokument „{file_name}“ konnte nicht dauerhaft übernommen werden: {error}",
                        type="negative",
                        close_button=True,
                    )
                finally:
                    refresh_import_status()

            async def analyze_import_jobs() -> None:
                synchronize_jobs()
                pending_ids = [
                    key for key, job in import_jobs.items()
                    if job.get("extracted") is not None
                    and job.get("raw_status") in {"Ready", "Failed"}
                ]
                try:
                    queued = analysis_queue.queue_batch(
                        project_id=project_id,
                        batch_id=batch_id,
                        job_ids=pending_ids,
                        use_ai=bool(import_batch["use_ai"]),
                        common_guidance=str(import_batch["common_guidance"] or ""),
                    )
                except ValueError as error:
                    ui.notify(str(error), type="warning")
                    return
                if not queued:
                    ui.notify("Es ist kein vorbereitetes Dokument zur Analyse vorhanden.", type="warning")
                    return
                synchronize_jobs()
                set_import_controls_enabled(False)
                refresh_import_status()
                ui.notify(
                    f"{queued} Dokument(e) wurden an den serverseitigen Analyse-Worker übergeben. "
                    "Der Browser kann jetzt geschlossen oder neu geladen werden.",
                    type="positive",
                    close_button=True,
                )

            upload_control = ui.upload(
                label="Dokumente auswählen",
                on_upload=handle_upload,
                auto_upload=True,
                multiple=True,
                max_file_size=20 * 1024 * 1024,
                max_total_size=200 * 1024 * 1024,
                max_files=20,
            ).props(
                'accept=".pdf,.docx,.txt,.md,.markdown,.csv,.tsv,.net,.xml,.json,text/plain,text/markdown,text/csv,application/pdf,application/json,application/xml"'
            ).classes("w-full")
            import_status()

            poll_state: dict[str, tuple[Any, ...]] = {"signature": ()}

            def poll_import_jobs() -> None:
                jobs = job_repository.list_ai_document_jobs(project_id, batch_id)
                signature = tuple(
                    (item.id, item.status, item.detail) for item in jobs
                )
                if signature == poll_state["signature"]:
                    return
                poll_state["signature"] = signature
                synchronize_jobs()
                set_import_controls_enabled(not import_batch["running"])
                refresh_import_status()
                if jobs and all(item.status in {"ReviewReady", "Failed"} for item in jobs):
                    succeeded = sum(item.status == "ReviewReady" for item in jobs)
                    failed = sum(item.status == "Failed" for item in jobs)
                    set_job(
                        "Ready" if succeeded else "Failed",
                        f"{succeeded}/{len(jobs)} Dokumente",
                        f"Serverseitige Dokumentserie abgeschlossen · {failed} fehlgeschlagen",
                    )

            poll_timer = ui.timer(0.75, poll_import_jobs)

            def close_import_dialog() -> None:
                poll_timer.cancel()
                dialog.close()
                synchronize_jobs()
                completed = [
                    job for job in import_jobs.values()
                    if job.get("raw_status") == "ReviewReady"
                ]
                if completed:
                    page_state.package, page_state.version = job_repository.load_project(project_id)
                    filters["section"] = "documents"
                    clear_selection()
                    selection["document_id"] = completed[-1].get("result_document_id")
                    refresh()

            with ui.row().classes("w-full justify-end"):
                close_button = ui.button("Schließen", on_click=close_import_dialog).props("flat no-caps")
                results_button = ui.button(
                    "Schließen und Ergebnisse anzeigen",
                    on_click=close_import_dialog,
                ).props("no-caps")
            dialog_controls.update({
                "upload": upload_control,
                "close": close_button,
                "results": results_button,
            })
            set_import_controls_enabled(not import_batch["running"])
        dialog.open()

    def document_context_recovery_dialog(source: SourceDocument) -> None:
        recovery_state = {"status": "Wartet auf Originaldokument", "detail": ""}
        with ui.dialog() as dialog, ui.card().classes("w-[760px] max-w-[96vw] p-6 gap-4"):
            ui.label("Originaldokument und KI-Kontext nachreichen").classes("text-xl font-bold")
            ui.label(source.name).classes("font-semibold")
            ui.label(
                "Dieser Legacy-Schritt erzeugt ausschließlich den lokalen Dokumentkontext. "
                "Es wird keine KI aufgerufen, keine neue Analyse angelegt und kein Requirement verändert."
            ).classes("text-sm text-blue-900 bg-blue-50 border border-blue-200 rounded-lg p-3")
            with ui.column().classes("w-full gap-1 rounded-lg border bg-slate-50 p-3"):
                ui.label(f"Erwartete Datei: {source.file_name or source.name}").classes("text-sm font-medium")
                ui.label(f"Erwartete SHA-256: {source.checksum_sha256}").classes("text-xs font-mono break-all text-slate-600")
                ui.label(
                    "Die Datei wird nur akzeptiert, wenn ihre SHA-256-Prüfsumme exakt mit dem ursprünglichen Manifest übereinstimmt."
                ).classes("text-xs text-slate-500")

            @ui.refreshable
            def recovery_status() -> None:
                color = "green-2" if recovery_state["status"] == "Kontext verfügbar" else (
                    "red-2" if recovery_state["status"] == "Fehlgeschlagen" else "blue-1"
                )
                with ui.row().classes("w-full items-center gap-2"):
                    if recovery_state["status"] == "Wird geprüft und extrahiert":
                        ui.spinner(size="18px")
                    ui.badge(recovery_state["status"], color=color).props("text-color=grey-9")
                    if recovery_state["detail"]:
                        ui.label(recovery_state["detail"]).classes("text-sm text-slate-600")

            async def recover(event: events.UploadEventArguments) -> None:
                file_name = getattr(event.file, "name", source.file_name or "requirements.bin")
                media_type = getattr(event.file, "content_type", "") or source.media_type
                try:
                    recovery_state.update(
                        status="Wird geprüft und extrahiert",
                        detail="Prüfsumme, Text und Struktur werden lokal verarbeitet",
                    )
                    recovery_status.refresh()
                    set_job("Dokumentkontext wird rekonstruiert", source.name, "Ohne KI-Analyse")
                    content = await event.file.read()
                    extracted = await run.io_bound(extract_document, content, file_name, media_type)
                    validate_document_context_recovery(source, extracted)
                    stored_document = store_attachment(
                        package().project.id,
                        source.id,
                        file_name,
                        content,
                        media_type,
                    )
                    context_bytes = serialize_document_context(extracted)
                    stored_context = store_attachment(
                        package().project.id,
                        source.id,
                        f"{file_name}.ecad-context.json",
                        context_bytes,
                        "application/json",
                    )
                    summary = recover_document_context_metadata(
                        package(),
                        source.id,
                        extracted,
                        attachment_path=stored_document.relative_path,
                        attachment_size=stored_document.size,
                        context_path=stored_context.relative_path,
                        context_checksum_sha256=stored_context.checksum_sha256,
                    )
                    if not save(f"Dokumentkontext für „{source.name}“ ohne KI wiederhergestellt"):
                        raise RuntimeError("Der wiederhergestellte Dokumentkontext konnte nicht gespeichert werden.")
                    recovery_state.update(
                        status="Kontext verfügbar",
                        detail=(
                            f"{summary.section_count} Abschnitte · {summary.character_count:,} Zeichen"
                        ).replace(",", "."),
                    )
                    set_job("Ready", source.name, "Dokumentkontext ohne KI wiederhergestellt")
                    recovery_status.refresh()
                    ui.notify(
                        "Originaldokument und Kontext wurden verifiziert nachgereicht. Es wurde keine KI-Analyse ausgeführt.",
                        type="positive",
                        close_button=True,
                    )
                    dialog.close()
                except Exception as error:
                    recovery_state.update(status="Fehlgeschlagen", detail=str(error))
                    set_job("Failed", source.name, str(error))
                    recovery_status.refresh()
                    ui.notify(f"Kontext konnte nicht nachgereicht werden: {error}", type="negative", close_button=True)

            recovery_status()
            ui.upload(
                label="Ursprüngliches Dokument auswählen",
                on_upload=recover,
                auto_upload=True,
                multiple=False,
                max_file_size=20 * 1024 * 1024,
            ).props(
                'accept=".pdf,.docx,.txt,.md,text/plain,text/markdown,application/pdf"'
            ).classes("w-full")
            with ui.row().classes("w-full justify-end"):
                ui.button("Schließen", on_click=dialog.close).props("flat no-caps")
        dialog.open()


    return DocumentAnalysisUiViews(
        document_context_available=document_context_available,
        load_document_context=load_document_context,
        build_ai_document_context=build_ai_document_context,
        open_document_context_dialog=open_document_context_dialog,
        document_import_dialog=document_import_dialog,
        document_context_recovery_dialog=document_context_recovery_dialog,
    )
