from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path


MAX_DOCUMENT_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class DocumentSection:
    locator: str
    text: str


@dataclass(frozen=True)
class ExtractedDocument:
    file_name: str
    media_type: str
    checksum_sha256: str
    sections: tuple[DocumentSection, ...]
    page_count: int | None = None

    @property
    def character_count(self) -> int:
        return sum(len(section.text) for section in self.sections)


DOCUMENT_CONTEXT_SCHEMA = "ecad-document-context/v1"


def serialize_document_context(document: ExtractedDocument) -> bytes:
    """Create a reusable local text context without repeating an AI analysis."""
    payload = {
        "schemaVersion": DOCUMENT_CONTEXT_SCHEMA,
        "fileName": document.file_name,
        "mediaType": document.media_type,
        "sourceChecksumSha256": document.checksum_sha256,
        "pageCount": document.page_count,
        "sections": [
            {"locator": section.locator, "text": section.text}
            for section in document.sections
        ],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def deserialize_document_context(data: bytes) -> ExtractedDocument:
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Der gespeicherte Dokumentkontext ist beschädigt.") from error
    if payload.get("schemaVersion") != DOCUMENT_CONTEXT_SCHEMA:
        raise ValueError("Der gespeicherte Dokumentkontext verwendet ein unbekanntes Format.")
    sections = tuple(
        DocumentSection(str(item.get("locator", "Abschnitt")), str(item.get("text", "")))
        for item in payload.get("sections", [])
        if isinstance(item, dict) and str(item.get("text", "")).strip()
    )
    if not sections:
        raise ValueError("Der gespeicherte Dokumentkontext enthält keinen Text.")
    return ExtractedDocument(
        file_name=str(payload.get("fileName", "document")),
        media_type=str(payload.get("mediaType", "text/plain")),
        checksum_sha256=str(payload.get("sourceChecksumSha256", "")),
        sections=sections,
        page_count=payload.get("pageCount"),
    )


def format_document_context(
    document: ExtractedDocument,
    *,
    max_characters: int | None = None,
) -> tuple[str, bool]:
    """Format traceable sections for an AI prompt and report truncation."""
    chunks: list[str] = []
    used = 0
    truncated = False
    for section in document.sections:
        block = f"[{section.locator}]\n{section.text.strip()}"
        if max_characters is not None and used + len(block) > max_characters:
            remaining = max_characters - used
            if remaining > 80:
                chunks.append(block[:remaining].rstrip() + "\n[… Kontext gekürzt …]")
            truncated = True
            break
        chunks.append(block)
        used += len(block) + 2
    return "\n\n".join(chunks), truncated


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Die Textdatei konnte nicht dekodiert werden.")


def _text_sections(text: str) -> tuple[DocumentSection, ...]:
    chunks = [item.strip() for item in text.replace("\r\n", "\n").split("\n\n") if item.strip()]
    if not chunks and text.strip():
        chunks = [text.strip()]
    return tuple(DocumentSection(f"Abschnitt {index}", chunk) for index, chunk in enumerate(chunks, start=1))


def _extract_pdf(data: bytes) -> tuple[tuple[DocumentSection, ...], int]:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError("Für PDF-Dokumente muss das Paket pypdf installiert sein.") from error
    reader = PdfReader(BytesIO(data))
    extracted_pages: list[DocumentSection] = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            extracted_pages.append(DocumentSection(f"Seite {index}", text))
    sections = tuple(extracted_pages)
    if not sections:
        raise ValueError("Das PDF enthält keinen extrahierbaren Text. Gescannte PDFs benötigen später eine OCR-/Vision-Erweiterung.")
    return sections, len(reader.pages)


def _extract_docx(data: bytes) -> tuple[DocumentSection, ...]:
    try:
        from docx import Document
    except ImportError as error:
        raise RuntimeError("Für DOCX-Dokumente muss das Paket python-docx installiert sein.") from error
    document = Document(BytesIO(data))
    sections: list[DocumentSection] = []
    heading = "Dokumentanfang"
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            sections.append(DocumentSection(heading, "\n".join(buffer).strip()))
            buffer.clear()

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        if paragraph.style and paragraph.style.name.casefold().startswith("heading"):
            flush()
            heading = text
        else:
            buffer.append(text)
    flush()
    if not sections:
        raise ValueError("Das DOCX enthält keinen auswertbaren Text.")
    return tuple(sections)


def extract_document(data: bytes, file_name: str, media_type: str = "") -> ExtractedDocument:
    if not data:
        raise ValueError("Das Dokument ist leer.")
    if len(data) > MAX_DOCUMENT_BYTES:
        raise ValueError("Das Dokument überschreitet die maximale Größe von 20 MiB.")
    suffix = Path(file_name).suffix.casefold()
    resolved_media_type = media_type or "application/octet-stream"
    page_count: int | None = None
    if suffix == ".pdf" or resolved_media_type == "application/pdf":
        sections, page_count = _extract_pdf(data)
        resolved_media_type = "application/pdf"
    elif suffix == ".docx" or "wordprocessingml" in resolved_media_type:
        sections = _extract_docx(data)
        resolved_media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif (
        suffix in {".txt", ".md", ".markdown", ".csv", ".tsv", ".net", ".xml", ".json"}
        or resolved_media_type.startswith("text/")
        or resolved_media_type in {"application/json", "application/xml"}
    ):
        sections = _text_sections(_decode_text(data))
        resolved_media_type = {
            ".md": "text/markdown",
            ".markdown": "text/markdown",
            ".csv": "text/csv",
            ".tsv": "text/tab-separated-values",
            ".xml": "application/xml",
            ".json": "application/json",
        }.get(suffix, "text/plain")
    else:
        raise ValueError(
            "Unterstützt werden PDF, DOCX, TXT, Markdown, CSV, TSV, textuelle Netzlisten, XML und JSON."
        )
    if not sections:
        raise ValueError("Das Dokument enthält keinen auswertbaren Text.")
    return ExtractedDocument(
        file_name=file_name,
        media_type=resolved_media_type,
        checksum_sha256=sha256(data).hexdigest(),
        sections=sections,
        page_count=page_count,
    )
