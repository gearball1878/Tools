"""Revision-aware source editing and document links.

Explicit callbacks keep project state in the page controller.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from .requirements_presentation import SOURCE_TYPE_LABELS, SOURCE_CHANNEL_LABELS, SOURCE_ACCESS_LABELS, SOURCE_STATUS_LABELS, CLAIM_STATUS_LABELS
from urllib.parse import urlparse
from nicegui import events, ui
from .attachment_store import attachment_is_available, delete_attachment, read_attachment, store_attachment
from .document_ingestion import extract_document
from .models import EvidenceClaimStatus, TechnicalSource, TechnicalSourceAccess, TechnicalSourceChannel, TechnicalSourceOwner, TechnicalSourceStatus, TechnicalSourceType, utc_now
from .requirements_service import delete_technical_source

@dataclass(frozen=True)
class TechnicalSourcesUiViews:
    owner_sources: Callable[..., Any]
    download_technical_source: Callable[..., Any]
    technical_source_dialog: Callable[..., Any]
    confirm_technical_source_delete: Callable[..., Any]
    render_technical_sources: Callable[..., Any]


def create_technical_sources_ui(
    *,
    package,
    save,
) -> TechnicalSourcesUiViews:
    def owner_sources(
        owner_type: TechnicalSourceOwner,
        owner_id: str,
    ) -> list[TechnicalSource]:
        return sorted(
            (
                item for item in package().technical_sources
                if item.owner_type == owner_type and item.owner_id == owner_id
            ),
            key=lambda item: (item.source_type.value, item.title.casefold()),
        )

    def download_technical_source(source: TechnicalSource) -> None:
        try:
            content = read_attachment(package().project.id, source.attachment_path)
        except (FileNotFoundError, ValueError) as error:
            ui.notify(str(error), type="warning", close_button=True)
            return
        ui.download(
            content,
            source.attachment_file_name or "document.bin",
            media_type=source.attachment_media_type or "application/octet-stream",
        )

    def technical_source_dialog(
        owner_type: TechnicalSourceOwner,
        owner_id: str,
        owner_title: str,
        source: TechnicalSource | None = None,
    ) -> None:
        current = source or TechnicalSource(
            owner_type=owner_type,
            owner_id=owner_id,
            title="",
            external_reference="new",
        )
        pending_attachment: dict[str, Any] = {}
        with ui.dialog() as dialog, ui.card().classes("w-[820px] max-w-[96vw] p-6 gap-4"):
            ui.label("Technische Quelle bearbeiten" if source else "Technische Quelle hinzufügen").classes("text-xl font-bold")
            ui.label(owner_title).classes("text-sm font-medium text-slate-600")
            with ui.row().classes("w-full gap-3"):
                title = ui.input(
                    "Titel",
                    value=current.title,
                    placeholder="z. B. Datenblatt Rev. C oder ISO-Portal-Eintrag",
                ).classes("grow")
                source_type = ui.select(
                    SOURCE_TYPE_LABELS,
                    value=current.source_type.value,
                    label="Quellentyp",
                ).classes("w-56")
            with ui.row().classes("w-full gap-3"):
                channel = ui.select(
                    SOURCE_CHANNEL_LABELS,
                    value=current.channel.value,
                    label="Zugriffskanal",
                ).classes("grow")
                access = ui.select(
                    SOURCE_ACCESS_LABELS,
                    value=current.access.value,
                    label="Zugriff",
                ).classes("grow")
                status = ui.select(
                    SOURCE_STATUS_LABELS,
                    value=current.status.value,
                    label="Quellenstatus",
                ).classes("grow")
                claim_status = ui.select(
                    CLAIM_STATUS_LABELS,
                    value=current.claim_status.value,
                    label="Aussagekraft",
                ).classes("grow")
            with ui.row().classes("w-full gap-3"):
                provider = ui.input(
                    "Anbieter / Portal / Repository",
                    value=current.provider,
                    placeholder="IEC, ISO, Hersteller, Distributor, PLM …",
                ).classes("grow")
                external_reference = ui.input(
                    "Externe ID / Dokumentnummer / Connector-Key",
                    value=current.external_reference if source else "",
                    placeholder="Optional",
                ).classes("grow")
                revision = ui.input("Revision / Ausgabe", value=current.revision).classes("w-40")
            with ui.row().classes('w-full gap-3'):
                document_date=ui.input('Dokumentdatum',value=current.document_date).classes('grow')
                release_status=ui.select(['Entwurf','Zur Prüfung','Freigegeben','Ersetzt','Gesperrt'],value=current.release_status or None,label='Dokumentfreigabe',clearable=True).classes('grow')
            evidence_locator = ui.input(
                "Fundstelle / Abschnitt",
                value=current.evidence_locator,
                placeholder="z. B. Kapitel 8.3, Tabelle 17 oder Seite 42",
            ).classes("w-full")
            url = ui.input(
                "URL",
                value=current.url,
                placeholder="https://… (öffentlich, Login, Lizenzportal oder interner Webdienst)",
            ).classes("w-full")
            linked_requirements = ui.select(
                {
                    item.id: f"{item.identifier or item.id[:12]} · {item.title}"
                    for item in package().requirements
                },
                value=list(current.requirement_ids),
                label="Belegte Requirements",
                multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            linked_interfaces = ui.select(
                {item.id: item.name for item in package().interface_requirements},
                value=list(current.interface_requirement_ids),
                label="Spezifizierte / belegte Interfaces",
                multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            referenced_standards = ui.select(
                {
                    item.id: f"{item.designation} · {item.title}" if item.title else item.designation
                    for item in package().standards
                },
                value=list(current.referenced_standard_ids),
                label="Im Dokument genannte Normen / Standards",
                multiple=True,
            ).props("use-chips outlined options-dense").classes("w-full")
            notes = ui.textarea("Hinweise / Geltungsbereich", value=current.notes).props("outlined autogrow").classes("w-full")

            @ui.refreshable
            def attachment_status() -> None:
                if pending_attachment:
                    ui.label(
                        f"Ausgewählt: {pending_attachment['name']} · {len(pending_attachment['content']):,} Bytes".replace(",", ".")
                    ).classes("text-sm text-emerald-800")
                elif current.attachment_file_name:
                    available = attachment_is_available(package().project.id, current.attachment_path)
                    ui.label(
                        f"Hinterlegt: {current.attachment_file_name}"
                        + ("" if available else " · in diesem Projektordner nicht verfügbar")
                    ).classes("text-sm " + ("text-slate-700" if available else "text-amber-800"))
                else:
                    ui.label("Kein lokales Dokument hinterlegt.").classes("subtle")

            async def handle_attachment_upload(event: events.UploadEventArguments) -> None:
                content = await event.file.read()
                if not content:
                    ui.notify("Das ausgewählte Dokument ist leer.", type="warning")
                    return
                pending_attachment.clear()
                pending_attachment.update(
                    name=getattr(event.file, "name", "document.bin"),
                    media_type=getattr(event.file, "content_type", "") or "",
                    content=content,
                )
                attachment_status.refresh()

            ui.upload(
                label="Datenblatt, Application Note oder anderes Dokument hinterlegen",
                on_upload=handle_attachment_upload,
                auto_upload=True,
                max_files=1,
                max_file_size=50 * 1024 * 1024,
            ).props(
                'accept=".pdf,.docx,.txt,.md,.csv,.xlsx,.zip,.step,.stp,.iges,.igs,.dxf,.png,.jpg,.jpeg"'
            ).classes("w-full")
            attachment_status()
            ui.label(
                "Geschützte Inhalte nur hochladen, wenn die Lizenz beziehungsweise NDA dies erlaubt. "
                "Zugangsdaten und Tokens gehören nicht in URL, externe ID oder Notizen."
            ).classes("text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-3")

            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply() -> None:
                    normalized_title = (title.value or "").strip()
                    normalized_url = (url.value or "").strip()
                    normalized_reference = (external_reference.value or "").strip()
                    if not normalized_title:
                        ui.notify("Der Titel der technischen Quelle ist erforderlich.", type="warning")
                        return
                    if normalized_url:
                        parsed = urlparse(normalized_url)
                        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                            ui.notify("Die URL muss mit http:// oder https:// beginnen.", type="warning")
                            return
                    if not (normalized_url or normalized_reference or pending_attachment or current.attachment_path):
                        ui.notify(
                            "Hinterlege mindestens eine URL, externe Referenz oder Dokumentdatei.",
                            type="warning",
                        )
                        return
                    target = source or TechnicalSource(
                        owner_type=owner_type,
                        owner_id=owner_id,
                        title=normalized_title,
                        external_reference=normalized_reference or "pending",
                    )
                    old_attachment_path = target.attachment_path
                    target.owner_type = owner_type
                    target.owner_id = owner_id
                    target.title = normalized_title
                    target.source_type = TechnicalSourceType(source_type.value)
                    target.channel = TechnicalSourceChannel(channel.value)
                    target.provider = (provider.value or "").strip()
                    target.external_reference = normalized_reference
                    target.url = normalized_url
                    target.access = TechnicalSourceAccess(access.value)
                    target.status = TechnicalSourceStatus(status.value)
                    target.claim_status = EvidenceClaimStatus(claim_status.value)
                    target.revision = (revision.value or "").strip()
                    target.document_date=document_date.value or ''
                    target.release_status=release_status.value or ''
                    target.evidence_locator = (evidence_locator.value or "").strip()
                    target.requirement_ids = list(linked_requirements.value or [])
                    target.interface_requirement_ids = list(linked_interfaces.value or [])
                    target.referenced_standard_ids = list(referenced_standards.value or [])
                    target.notes = notes.value or ""
                    target.last_checked_at = utc_now()
                    new_attachment_path = ""
                    if pending_attachment:
                        try:
                            stored = store_attachment(
                                package().project.id,
                                target.id,
                                pending_attachment["name"],
                                pending_attachment["content"],
                                pending_attachment["media_type"],
                            )
                        except (OSError, ValueError) as error:
                            ui.notify(f"Dokument konnte nicht hinterlegt werden: {error}", type="negative")
                            return
                        target.attachment_file_name = stored.file_name
                        target.attachment_media_type = stored.media_type
                        target.attachment_path = stored.relative_path
                        target.attachment_size = stored.size
                        target.checksum_sha256 = stored.checksum_sha256
                        try:
                            extracted=extract_document(pending_attachment['content'],pending_attachment['name'],pending_attachment['media_type'])
                            target.extracted_content='\n\n'.join(s.locator+'\n'+s.text for s in extracted.sections)
                        except (ValueError,TypeError):target.extracted_content=''
                        new_attachment_path = stored.relative_path
                    if source is None:
                        package().technical_sources.append(target)
                    if save("Technische Quelle gespeichert"):
                        dialog.close()
                        if old_attachment_path and old_attachment_path != target.attachment_path:
                            try:
                                delete_attachment(package().project.id, old_attachment_path)
                            except ValueError:
                                pass
                    elif new_attachment_path and new_attachment_path != old_attachment_path:
                        try:
                            delete_attachment(package().project.id, new_attachment_path)
                        except ValueError:
                            pass

                ui.button("Quelle speichern", icon="save", on_click=apply).props("no-caps")
        dialog.open()

    def confirm_technical_source_delete(source: TechnicalSource) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[520px] max-w-[94vw] p-6 gap-4"):
            ui.label("Technische Quelle löschen?").classes("text-xl font-bold")
            ui.label(source.title).classes("font-medium")
            ui.label(
                "Quellenmetadaten und eine gegebenenfalls lokal hinterlegte Datei werden entfernt. "
                "Norm, Komponente und Requirements bleiben bestehen."
            ).classes("text-sm text-slate-600")
            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")

                def apply() -> None:
                    stored_path = source.attachment_path
                    delete_technical_source(package(), source.id)
                    if save("Technische Quelle gelöscht"):
                        if stored_path:
                            try:
                                delete_attachment(package().project.id, stored_path)
                            except ValueError:
                                pass
                        dialog.close()

                ui.button("Löschen", icon="delete", on_click=apply).props("color=negative no-caps")
        dialog.open()

    def render_technical_sources(
        owner_type: TechnicalSourceOwner,
        owner_id: str,
        owner_title: str,
    ) -> None:
        sources = owner_sources(owner_type, owner_id)
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(f"Technische Quellen & Dokumente ({len(sources)})").classes("font-bold")
            ui.button(
                "Quelle hinzufügen",
                icon="add_link",
                on_click=lambda: technical_source_dialog(owner_type, owner_id, owner_title),
            ).props("flat dense no-caps")
        if not sources:
            ui.label(
                "Noch keine Webquelle, Portalreferenz, API-/Connector-ID oder lokale Dokumentdatei hinterlegt."
            ).classes("subtle")
        for source_item in sources:
            status_color = (
                "green-2" if source_item.status == TechnicalSourceStatus.VERIFIED
                else "red-2" if source_item.status == TechnicalSourceStatus.UNAVAILABLE
                else "blue-1"
            )
            with ui.card().classes("w-full p-3 gap-2 border"):
                with ui.row().classes("w-full items-start gap-2"):
                    ui.icon("description" if source_item.attachment_path else "link", color="primary")
                    with ui.column().classes("gap-0 grow min-w-0"):
                        ui.label(source_item.title).classes("font-medium")
                        detail = " · ".join(
                            item for item in [
                                SOURCE_TYPE_LABELS.get(source_item.source_type.value, source_item.source_type.value),
                                source_item.provider,
                                source_item.revision,
                                source_item.external_reference,
                            ] if item
                        )
                        if detail:
                            ui.label(detail).classes("text-xs text-slate-600")
                    ui.badge(
                        SOURCE_ACCESS_LABELS.get(source_item.access.value, source_item.access.value),
                        color="amber-1" if source_item.access != TechnicalSourceAccess.PUBLIC else "grey-3",
                    ).props("text-color=grey-9")
                    ui.badge(
                        SOURCE_STATUS_LABELS.get(source_item.status.value, source_item.status.value),
                        color=status_color,
                    ).props("text-color=grey-9")
                    ui.badge(
                        CLAIM_STATUS_LABELS.get(source_item.claim_status.value, source_item.claim_status.value),
                        color=(
                            "green-2" if source_item.claim_status == EvidenceClaimStatus.DESIGN_VERIFIED
                            else "amber-2" if source_item.claim_status == EvidenceClaimStatus.MANUFACTURER_CLAIM
                            else "grey-3"
                        ),
                    ).props("text-color=grey-9")
                if source_item.evidence_locator:
                    ui.label(f"Fundstelle: {source_item.evidence_locator}").classes("text-xs font-mono text-slate-600")
                relation_parts = [
                    f"{len(source_item.requirement_ids)} Requirement(s)" if source_item.requirement_ids else "",
                    f"{len(source_item.interface_requirement_ids)} Interface(s)" if source_item.interface_requirement_ids else "",
                    f"{len(source_item.referenced_standard_ids)} Standardreferenz(en)" if source_item.referenced_standard_ids else "",
                ]
                if any(relation_parts):
                    ui.label(" · ".join(item for item in relation_parts if item)).classes("text-xs text-slate-600")
                if source_item.notes:
                    ui.label(source_item.notes).classes("text-sm text-slate-700")
                with ui.row().classes("w-full items-center gap-2"):
                    if source_item.url:
                        ui.link("Online öffnen", source_item.url, new_tab=True).classes("text-sm")
                    if source_item.attachment_path:
                        available = attachment_is_available(package().project.id, source_item.attachment_path)
                        ui.button(
                            "Dokument herunterladen" if available else "Dokument lokal nicht verfügbar",
                            icon="download" if available else "cloud_off",
                            on_click=lambda _, item=source_item: download_technical_source(item),
                        ).props("flat dense no-caps").set_enabled(available)
                    ui.space()
                    ui.button(
                        icon="edit",
                        on_click=lambda _, item=source_item: technical_source_dialog(
                            owner_type, owner_id, owner_title, item
                        ),
                    ).props("flat round dense").tooltip("Quelle bearbeiten")
                    ui.button(
                        icon="delete_outline",
                        on_click=lambda _, item=source_item: confirm_technical_source_delete(item),
                    ).props("flat round dense color=negative").tooltip("Quelle löschen")


    return TechnicalSourcesUiViews(
        owner_sources=owner_sources,
        download_technical_source=download_technical_source,
        technical_source_dialog=technical_source_dialog,
        confirm_technical_source_delete=confirm_technical_source_delete,
        render_technical_sources=render_technical_sources,
    )
