from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import mimetypes
from pathlib import Path
import re
import shutil

from .repository import default_data_dir


MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024
COMPACT_ID_HASH_LENGTH = 24
COMPACT_FILE_HASH_LENGTH = 24


@dataclass(frozen=True)
class StoredAttachment:
    file_name: str
    media_type: str
    relative_path: str
    size: int
    checksum_sha256: str


def attachment_root() -> Path:
    root = default_data_dir() / "attachments"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_segment(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    normalized = normalized.strip(" ._")
    return (normalized or fallback)[:160]


def _compact_id_segment(value: str, prefix: str) -> str:
    """Return a stable, short directory name for Windows-safe storage paths."""
    digest = sha256(value.encode("utf-8", errors="replace")).hexdigest()
    return f"{prefix}-{digest[:COMPACT_ID_HASH_LENGTH]}"


def _compact_file_name(file_name: str, checksum_sha256: str) -> str:
    suffix = re.sub(r"[^a-z0-9.]", "", Path(file_name).suffix.casefold())[:16]
    if suffix and not suffix.startswith("."):
        suffix = f".{suffix}"
    return f"f-{checksum_sha256[:COMPACT_FILE_HASH_LENGTH]}{suffix}"


def _resolved_attachment_path(relative_path: str, project_id: str | None = None) -> Path:
    root = attachment_root().resolve()
    parts = Path(relative_path).parts
    if project_id is not None:
        valid_project_segments = {
            _safe_segment(project_id, "project"),  # legacy layout through v0.26.0
            _compact_id_segment(project_id, "p"),
        }
        if not parts or parts[0] not in valid_project_segments:
            raise ValueError("Das Dokument gehört nicht zum aktuellen Projekt.")
    candidate = (root / relative_path).resolve()
    if candidate == root or root not in candidate.parents:
        raise ValueError("Ungültiger Dokumentpfad.")
    return candidate


def store_attachment(
    project_id: str,
    source_id: str,
    file_name: str,
    data: bytes,
    media_type: str = "",
) -> StoredAttachment:
    if not data:
        raise ValueError("Das Dokument ist leer.")
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise ValueError("Das Dokument überschreitet die maximale Größe von 50 MiB.")
    safe_name = _safe_segment(Path(file_name).name, "document.bin")
    checksum = sha256(data).hexdigest()
    relative = Path(
        _compact_id_segment(project_id, "p"),
        _compact_id_segment(source_id, "s"),
        _compact_file_name(safe_name, checksum),
    )
    destination = _resolved_attachment_path(relative.as_posix())
    temporary = destination.with_suffix(destination.suffix + ".part")
    for attempt in range(2):
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            temporary.write_bytes(data)
            temporary.replace(destination)
            break
        except FileNotFoundError:
            if attempt:
                raise
    resolved_media_type = media_type.strip() or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
    return StoredAttachment(
        file_name=safe_name,
        media_type=resolved_media_type,
        relative_path=relative.as_posix(),
        size=len(data),
        checksum_sha256=checksum,
    )


def attachment_is_available(project_id: str, relative_path: str) -> bool:
    if not relative_path.strip():
        return False
    try:
        return _resolved_attachment_path(relative_path, project_id).is_file()
    except ValueError:
        return False


def read_attachment(project_id: str, relative_path: str) -> bytes:
    path = _resolved_attachment_path(relative_path, project_id)
    if not path.is_file():
        raise FileNotFoundError("Das hinterlegte Dokument ist lokal nicht verfügbar.")
    return path.read_bytes()


def delete_attachment(project_id: str, relative_path: str) -> None:
    if not relative_path.strip():
        return
    path = _resolved_attachment_path(relative_path, project_id)
    if path.is_file():
        path.unlink()
    root = attachment_root().resolve()
    parent = path.parent
    while parent != root and root in parent.parents:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def delete_project_attachments(project_id: str) -> None:
    root = attachment_root().resolve()
    project_segments = {
        _safe_segment(project_id, "project"),
        _compact_id_segment(project_id, "p"),
    }
    for segment in project_segments:
        project_path = (root / segment).resolve()
        if root not in project_path.parents:
            raise ValueError("Ungültiger Projekt-Dokumentpfad.")
        if project_path.is_dir():
            shutil.rmtree(project_path)
