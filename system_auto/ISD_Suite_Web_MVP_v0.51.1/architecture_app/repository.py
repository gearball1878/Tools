from __future__ import annotations

import json
import hashlib
import os
import secrets
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import ArchitecturePackage, ProjectWorkflow, new_id, utc_now
from .project_import import select_import_workflow
from .signal_naming import normalize_architecture_names


_ADMIN_PIN_KEY = "admin_pin_hash"
_PIN_HASH_ITERATIONS = 260_000


def _encode_pin(pin: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, _PIN_HASH_ITERATIONS)
    return f"pbkdf2_sha256${_PIN_HASH_ITERATIONS}${salt.hex()}${digest.hex()}"


def _pin_matches(pin: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, iterations, salt_hex, expected_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            pin.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return secrets.compare_digest(actual.hex(), expected_hex)
    except (TypeError, ValueError):
        return False


def _migrate_duplicate_hierarchy_names(document: dict[str, Any]) -> bool:
    """Make legacy Domain/AE names globally unique before strict validation."""
    used_names: set[str] = set()
    changed = False

    def reserve_name(item: dict[str, Any], fallback: str) -> None:
        nonlocal changed
        original = item.get("name")
        base = str(original or "").strip() or fallback
        candidate = base
        suffix = 2
        while candidate.casefold() in used_names:
            candidate = f"{base} ({suffix})"
            suffix += 1
        used_names.add(candidate.casefold())
        if original != candidate:
            item["name"] = candidate
            changed = True

    domains = [item for item in document.get("domains", []) if isinstance(item, dict)]
    # Domains own the higher hierarchy level and therefore retain their names first.
    for domain in domains:
        reserve_name(domain, "Domain")
    for domain in domains:
        elements = [item for item in domain.get("elements", []) if isinstance(item, dict)]
        for element in elements:
            reserve_name(element, "Architecture Element")
    return changed


def default_data_dir() -> Path:
    configured = os.getenv(
        "ISD_SUITE_DATA_DIR",
        os.getenv("ECAD_SUITE_DATA_DIR", os.getenv("XPED_AUTO_DATA_DIR", "")),
    )
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        preferred = base / "ISD_Suite" / "data"
        previous = base / "ECAD_System_Suite" / "data"
        legacy = base / "XPED_AUTO" / "data"
        return next((item for item in (preferred, previous, legacy) if item.exists()), preferred)
    preferred = Path.home() / ".local" / "share" / "ISD_Suite"
    previous = Path.home() / ".local" / "share" / "ECAD_System_Suite"
    legacy = Path.home() / ".local" / "share" / "XPED_AUTO"
    return next((item for item in (preferred, previous, legacy) if item.exists()), preferred)


@dataclass(frozen=True)
class ProjectSummary:
    id: str
    name: str
    version: int
    updated_at: str


@dataclass(frozen=True)
class RevisionSummary:
    id: int
    revision_number: int
    label: str
    created_at: str


@dataclass(frozen=True)
class AIChatMessage:
    id: int
    project_id: str
    prompt: str
    answer: str
    provider: str
    model: str
    findings: list[str]
    recommendations: list[str]
    open_questions: list[str]
    status: str
    accepted_review_id: str | None
    created_at: str


@dataclass(frozen=True)
class AIDocumentJob:
    id: str
    batch_id: str
    project_id: str
    position: int
    file_name: str
    display_name: str
    media_type: str
    document_type: str
    document_context: str
    analysis_instructions: str
    common_guidance: str
    use_ai: bool
    status: str
    detail: str
    attachment_path: str
    context_path: str
    checksum_sha256: str
    page_count: int | None
    character_count: int
    provider: str
    model: str
    result_document_id: str | None
    attempts: int
    created_at: str
    updated_at: str
    started_at: str | None
    completed_at: str | None


class VersionConflict(RuntimeError):
    pass


class ArchitectureRepository:
    def __init__(self, database_path: Path | None = None):
        data_dir = default_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        self.database_path = database_path or data_dir / "architecture.db"
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA temp_store = MEMORY")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    document_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_name ON projects(name COLLATE NOCASE);
                CREATE INDEX IF NOT EXISTS idx_projects_updated_at ON projects(updated_at DESC);
                CREATE TABLE IF NOT EXISTS revisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    revision_number INTEGER NOT NULL,
                    label TEXT NOT NULL,
                    document_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(project_id, revision_number)
                );
                CREATE INDEX IF NOT EXISTS idx_revisions_project_number
                    ON revisions(project_id, revision_number DESC);
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ai_chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    prompt TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    provider TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    findings_json TEXT NOT NULL DEFAULT '[]',
                    recommendations_json TEXT NOT NULL DEFAULT '[]',
                    open_questions_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'Draft',
                    accepted_review_id TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ai_chat_project_created
                    ON ai_chat_messages(project_id, created_at, id);
                CREATE TABLE IF NOT EXISTS ai_document_jobs (
                    id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL DEFAULT 1,
                    file_name TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    media_type TEXT NOT NULL DEFAULT '',
                    document_type TEXT NOT NULL DEFAULT '',
                    document_context TEXT NOT NULL DEFAULT '',
                    analysis_instructions TEXT NOT NULL DEFAULT '',
                    common_guidance TEXT NOT NULL DEFAULT '',
                    use_ai INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'Preparing',
                    detail TEXT NOT NULL DEFAULT '',
                    attachment_path TEXT NOT NULL DEFAULT '',
                    context_path TEXT NOT NULL DEFAULT '',
                    checksum_sha256 TEXT NOT NULL DEFAULT '',
                    page_count INTEGER,
                    character_count INTEGER NOT NULL DEFAULT 0,
                    provider TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    result_document_id TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_ai_document_jobs_project_batch
                    ON ai_document_jobs(project_id, batch_id, position, created_at);
                CREATE INDEX IF NOT EXISTS idx_ai_document_jobs_status
                    ON ai_document_jobs(status, created_at);
            """)
            # Existing PINs are retained; only previously unconfigured
            # installations receive the documented initial PIN.
            connection.execute(
                "INSERT OR IGNORE INTO app_settings(key, value) VALUES(?, ?)",
                (_ADMIN_PIN_KEY, _encode_pin("0000")),
            )
            connection.execute("PRAGMA optimize")

    @staticmethod
    def _document_job(row: sqlite3.Row) -> AIDocumentJob:
        values = dict(row)
        values["use_ai"] = bool(values["use_ai"])
        return AIDocumentJob(**values)

    @staticmethod
    def _serialize(package: ArchitecturePackage) -> str:
        return json.dumps(package.export_dict(), ensure_ascii=False, separators=(",", ":"))

    def list_projects(self) -> list[ProjectSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, name, version, updated_at FROM projects ORDER BY updated_at DESC"
            ).fetchall()
        return [ProjectSummary(**dict(row)) for row in rows]

    def create_project(self, package: ArchitecturePackage) -> tuple[ArchitecturePackage, int]:
        package.touch()
        payload = self._serialize(package)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO projects(id, name, version, document_json, created_at, updated_at) VALUES(?, ?, 1, ?, ?, ?)",
                (package.project.id, package.project.name, payload, package.project.created_at, package.project.updated_at),
            )
            connection.execute(
                "INSERT INTO revisions(project_id, revision_number, label, document_json, created_at) VALUES(?, 1, ?, ?, ?)",
                (package.project.id, "Projekt angelegt", payload, package.project.updated_at),
            )
        return package, 1

    def admin_pin_is_set(self) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM app_settings WHERE key = ?", (_ADMIN_PIN_KEY,)
            ).fetchone()
        return bool(row and row["value"])

    def verify_admin_pin(self, pin: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM app_settings WHERE key = ?", (_ADMIN_PIN_KEY,)
            ).fetchone()
        return _pin_matches((pin or "").strip(), row["value"] if row else None)

    def set_admin_pin(self, current_pin: str, new_pin: str) -> None:
        current_value = (current_pin or "").strip()
        new_value = (new_pin or "").strip()
        if len(new_value) < 4:
            raise ValueError("Die neue Admin-PIN muss mindestens vier Zeichen enthalten.")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM app_settings WHERE key = ?", (_ADMIN_PIN_KEY,)
            ).fetchone()
            if not _pin_matches(current_value, row["value"] if row else None):
                raise PermissionError("Die aktuelle Admin-PIN ist nicht korrekt.")
            connection.execute(
                """INSERT INTO app_settings(key, value) VALUES(?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                (_ADMIN_PIN_KEY, _encode_pin(new_value)),
            )

    def delete_project(self, project_id: str, admin_pin: str = "") -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM app_settings WHERE key = ?", (_ADMIN_PIN_KEY,)
            ).fetchone()
            if not _pin_matches((admin_pin or "").strip(), row["value"] if row else None):
                raise PermissionError("Die Admin-PIN ist nicht korrekt.")
            cursor = connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            if cursor.rowcount != 1:
                raise KeyError(f"Projekt nicht gefunden: {project_id}")

    def load_project(self, project_id: str) -> tuple[ArchitecturePackage, int]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT document_json, version FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Projekt nicht gefunden: {project_id}")
            version = int(row["version"])
            document = json.loads(row["document_json"])
            names_migrated = _migrate_duplicate_hierarchy_names(document)
            package = ArchitecturePackage.model_validate(document)
            names_normalized = normalize_architecture_names(package)
            if names_migrated or names_normalized:
                package.touch()
                payload = self._serialize(package)
                ArchitecturePackage.model_validate(json.loads(payload))
                revision_number = int(connection.execute(
                    "SELECT COALESCE(MAX(revision_number), 0) + 1 FROM revisions WHERE project_id = ?",
                    (project_id,),
                ).fetchone()[0])
                connection.execute(
                    """INSERT INTO revisions(project_id, revision_number, label, document_json, created_at)
                       VALUES(?, ?, ?, ?, ?)""",
                    (project_id, revision_number, "Sicherung vor automatischer Namensbereinigung",
                     row["document_json"], package.project.updated_at),
                )
                cursor = connection.execute(
                    """UPDATE projects
                       SET version = version + 1, document_json = ?, updated_at = ?
                       WHERE id = ? AND version = ?""",
                    (payload, package.project.updated_at, project_id, version),
                )
                if cursor.rowcount != 1:
                    raise VersionConflict("Der Arbeitsstand wurde während der Namensmigration geändert.")
                version += 1
                connection.execute(
                    """INSERT INTO revisions(project_id, revision_number, label, document_json, created_at)
                       VALUES(?, ?, ?, ?, ?)""",
                    (project_id, revision_number + 1, "Automatische Namensbereinigung", payload, package.project.updated_at),
                )
        return package, version

    def save_project(self, package: ArchitecturePackage, expected_version: int) -> int:
        package.touch()
        payload = self._serialize(package)
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE projects
                   SET name = ?, version = version + 1, document_json = ?, updated_at = ?
                   WHERE id = ? AND version = ?""",
                (package.project.name, payload, package.project.updated_at, package.project.id, expected_version),
            )
            if cursor.rowcount != 1:
                raise VersionConflict("Der Arbeitsstand wurde zwischenzeitlich in einer anderen Sitzung geändert.")
            row = connection.execute("SELECT version FROM projects WHERE id = ?", (package.project.id,)).fetchone()
        return int(row["version"])

    def create_revision(self, project_id: str, label: str) -> int:
        with self._connect() as connection:
            project = connection.execute(
                "SELECT document_json FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if project is None:
                raise KeyError(project_id)
            number = int(connection.execute(
                "SELECT COALESCE(MAX(revision_number), 0) + 1 FROM revisions WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0])
            connection.execute(
                "INSERT INTO revisions(project_id, revision_number, label, document_json, created_at) VALUES(?, ?, ?, ?, ?)",
                (project_id, number, label.strip() or f"Revision {number}", project["document_json"], utc_now()),
            )
        return number

    def add_ai_chat_message(
        self,
        project_id: str,
        prompt: str,
        answer: str,
        provider: str,
        model: str,
        findings: list[str] | None = None,
        recommendations: list[str] | None = None,
        open_questions: list[str] | None = None,
    ) -> AIChatMessage:
        created_at = utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO ai_chat_messages(
                       project_id, prompt, answer, provider, model,
                       findings_json, recommendations_json, open_questions_json,
                       status, created_at
                   ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'Draft', ?)""",
                (
                    project_id,
                    prompt.strip(),
                    answer.strip(),
                    provider,
                    model,
                    json.dumps(findings or [], ensure_ascii=False),
                    json.dumps(recommendations or [], ensure_ascii=False),
                    json.dumps(open_questions or [], ensure_ascii=False),
                    created_at,
                ),
            )
            message_id = int(cursor.lastrowid)
        return AIChatMessage(
            id=message_id,
            project_id=project_id,
            prompt=prompt.strip(),
            answer=answer.strip(),
            provider=provider,
            model=model,
            findings=list(findings or []),
            recommendations=list(recommendations or []),
            open_questions=list(open_questions or []),
            status="Draft",
            accepted_review_id=None,
            created_at=created_at,
        )

    def list_ai_chat_messages(self, project_id: str) -> list[AIChatMessage]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id, project_id, prompt, answer, provider, model,
                          findings_json, recommendations_json, open_questions_json,
                          status, accepted_review_id, created_at
                   FROM ai_chat_messages
                   WHERE project_id = ?
                   ORDER BY created_at, id""",
                (project_id,),
            ).fetchall()
        return [
            AIChatMessage(
                id=int(row["id"]),
                project_id=str(row["project_id"]),
                prompt=str(row["prompt"]),
                answer=str(row["answer"]),
                provider=str(row["provider"]),
                model=str(row["model"]),
                findings=list(json.loads(row["findings_json"])),
                recommendations=list(json.loads(row["recommendations_json"])),
                open_questions=list(json.loads(row["open_questions_json"])),
                status=str(row["status"]),
                accepted_review_id=(
                    str(row["accepted_review_id"])
                    if row["accepted_review_id"] is not None else None
                ),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def update_ai_chat_message(
        self,
        project_id: str,
        message_id: int,
        status: str,
        accepted_review_id: str | None = None,
    ) -> None:
        if status not in {"Draft", "Accepted", "Rejected"}:
            raise ValueError("Ungültiger Status für eine KI-Unterhaltung.")
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE ai_chat_messages
                   SET status = ?, accepted_review_id = ?
                   WHERE id = ? AND project_id = ?""",
                (status, accepted_review_id, message_id, project_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(message_id)

    def get_app_setting(self, key: str, default: str = "") -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM app_settings WHERE key = ?", (key,)
            ).fetchone()
        return str(row["value"]) if row is not None else default

    def set_app_setting(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO app_settings(key, value) VALUES(?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                (key, value),
            )

    def delete_app_setting(self, key: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM app_settings WHERE key = ?", (key,))

    def create_ai_document_job(
        self,
        project_id: str,
        batch_id: str,
        file_name: str,
        display_name: str,
        media_type: str,
        document_type: str,
        attachment_path: str,
        checksum_sha256: str,
        job_id: str | None = None,
    ) -> AIDocumentJob:
        job_id = job_id or new_id("aijob")
        timestamp = utc_now()
        with self._connect() as connection:
            position = int(connection.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 FROM ai_document_jobs WHERE batch_id = ?",
                (batch_id,),
            ).fetchone()[0])
            connection.execute(
                """INSERT INTO ai_document_jobs(
                       id, batch_id, project_id, position, file_name, display_name,
                       media_type, document_type, attachment_path, checksum_sha256,
                       status, detail, created_at, updated_at
                   ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Preparing', ?, ?, ?)""",
                (
                    job_id,
                    batch_id,
                    project_id,
                    position,
                    file_name,
                    display_name,
                    media_type,
                    document_type,
                    attachment_path,
                    checksum_sha256,
                    "Dokument wird serverseitig eingelesen.",
                    timestamp,
                    timestamp,
                ),
            )
            row = connection.execute(
                "SELECT * FROM ai_document_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return self._document_job(row)

    def list_ai_document_jobs(
        self,
        project_id: str,
        batch_id: str | None = None,
    ) -> list[AIDocumentJob]:
        query = "SELECT * FROM ai_document_jobs WHERE project_id = ?"
        values: list[Any] = [project_id]
        if batch_id:
            query += " AND batch_id = ?"
            values.append(batch_id)
        query += " ORDER BY created_at, position"
        with self._connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [self._document_job(row) for row in rows]

    def list_ai_document_jobs_by_status(self, statuses: list[str]) -> list[AIDocumentJob]:
        if not statuses:
            return []
        placeholders = ",".join("?" for _ in statuses)
        with self._connect() as connection:
            rows = connection.execute(
                f"""SELECT * FROM ai_document_jobs
                    WHERE status IN ({placeholders})
                    ORDER BY created_at, position""",
                statuses,
            ).fetchall()
        return [self._document_job(row) for row in rows]

    def get_ai_document_job(self, job_id: str) -> AIDocumentJob:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ai_document_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        if row is None:
            raise KeyError(job_id)
        return self._document_job(row)

    def active_ai_document_batch(self, project_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT batch_id, MAX(created_at) AS newest
                   FROM ai_document_jobs
                   WHERE project_id = ? AND status NOT IN ('ReviewReady', 'Cancelled')
                   GROUP BY batch_id
                   ORDER BY newest DESC LIMIT 1""",
                (project_id,),
            ).fetchone()
        return str(row["batch_id"]) if row is not None else None

    def active_ai_document_job(self, project_id: str) -> AIDocumentJob | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM ai_document_jobs
                   WHERE project_id = ? AND status IN ('Running', 'Queued', 'Preparing')
                   ORDER BY CASE status
                       WHEN 'Running' THEN 0 WHEN 'Preparing' THEN 1 ELSE 2 END,
                       created_at, position
                   LIMIT 1""",
                (project_id,),
            ).fetchone()
        return self._document_job(row) if row is not None else None

    def update_ai_document_job(self, job_id: str, **changes: Any) -> AIDocumentJob:
        allowed = {
            "display_name", "document_type", "document_context",
            "analysis_instructions", "common_guidance", "use_ai", "status",
            "detail", "context_path", "page_count", "character_count",
            "provider", "model", "result_document_id", "started_at",
            "completed_at", "attempts",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"Nicht unterstützte Job-Felder: {', '.join(sorted(unknown))}")
        if not changes:
            return self.get_ai_document_job(job_id)
        changes["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = ?" for key in changes)
        values = [int(value) if key == "use_ai" else value for key, value in changes.items()]
        values.append(job_id)
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE ai_document_jobs SET {assignments} WHERE id = ?",
                values,
            )
            if cursor.rowcount != 1:
                raise KeyError(job_id)
            row = connection.execute(
                "SELECT * FROM ai_document_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return self._document_job(row)

    def delete_ai_document_job(self, project_id: str, job_id: str) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM ai_document_jobs WHERE id = ? AND project_id = ?",
                (job_id, project_id),
            ).fetchone()
            if row is None:
                raise KeyError(job_id)
            if row["status"] in {"Queued", "Running"}:
                raise ValueError("Ein laufender Analyseauftrag kann nicht entfernt werden.")
            connection.execute(
                "DELETE FROM ai_document_jobs WHERE id = ? AND project_id = ?",
                (job_id, project_id),
            )

    def queue_ai_document_jobs(
        self,
        project_id: str,
        batch_id: str,
        job_ids: list[str],
        use_ai: bool,
        common_guidance: str,
    ) -> int:
        if not job_ids:
            return 0
        placeholders = ",".join("?" for _ in job_ids)
        timestamp = utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                f"""UPDATE ai_document_jobs
                    SET status = 'Queued', detail = 'Wartet auf serverseitige Analyse.',
                        use_ai = ?, common_guidance = ?, updated_at = ?, completed_at = NULL
                    WHERE project_id = ? AND batch_id = ?
                      AND id IN ({placeholders})
                      AND context_path <> ''
                      AND status IN ('Ready', 'Failed')""",
                [int(use_ai), common_guidance, timestamp, project_id, batch_id, *job_ids],
            )
        return int(cursor.rowcount)

    def claim_next_ai_document_job(self) -> AIDocumentJob | None:
        timestamp = utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT id FROM ai_document_jobs
                   WHERE status = 'Queued'
                   ORDER BY created_at, position LIMIT 1"""
            ).fetchone()
            if row is None:
                return None
            job_id = str(row["id"])
            connection.execute(
                """UPDATE ai_document_jobs
                   SET status = 'Running', detail = 'Die serverseitige Analyse läuft.',
                       attempts = attempts + 1, started_at = ?, updated_at = ?
                   WHERE id = ?""",
                (timestamp, timestamp, job_id),
            )
            claimed = connection.execute(
                "SELECT * FROM ai_document_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return self._document_job(claimed)

    def requeue_interrupted_ai_document_jobs(self) -> int:
        timestamp = utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE ai_document_jobs
                   SET status = 'Queued',
                       detail = 'Nach einem Anwendungsneustart automatisch fortgesetzt.',
                       updated_at = ?
                   WHERE status = 'Running'""",
                (timestamp,),
            )
        return int(cursor.rowcount)

    def list_revisions(self, project_id: str) -> list[RevisionSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id, revision_number, label, created_at FROM revisions
                   WHERE project_id = ? ORDER BY revision_number DESC""",
                (project_id,),
            ).fetchall()
        return [RevisionSummary(**dict(row)) for row in rows]

    def restore_revision(self, project_id: str, revision_id: int, expected_version: int) -> int:
        with self._connect() as connection:
            revision = connection.execute(
                "SELECT revision_number, document_json FROM revisions WHERE id = ? AND project_id = ?",
                (revision_id, project_id),
            ).fetchone()
            if revision is None:
                raise KeyError(revision_id)
            project = connection.execute(
                "SELECT name, version, document_json, created_at FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if project is None:
                raise KeyError(project_id)
            if int(project["version"]) != expected_version:
                raise VersionConflict("Der Arbeitsstand wurde zwischenzeitlich in einer anderen Sitzung geändert.")

            document = json.loads(revision["document_json"])
            _migrate_duplicate_hierarchy_names(document)
            package = ArchitecturePackage.model_validate(document)
            package.project.id = project_id
            # The project container keeps its current identity and unique name;
            # all engineering content is restored from the selected snapshot.
            package.project.name = str(project["name"])
            package.project.created_at = str(project["created_at"])
            package.touch()
            restored_payload = self._serialize(package)
            next_revision = int(connection.execute(
                "SELECT COALESCE(MAX(revision_number), 0) + 1 FROM revisions WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0])
            connection.execute(
                """INSERT INTO revisions(project_id, revision_number, label, document_json, created_at)
                   VALUES(?, ?, ?, ?, ?)""",
                (
                    project_id,
                    next_revision,
                    f"Automatische Sicherung vor Wiederherstellung von R{int(revision['revision_number'])}",
                    project["document_json"],
                    utc_now(),
                ),
            )
            connection.execute(
                """INSERT INTO revisions(project_id, revision_number, label, document_json, created_at)
                   VALUES(?, ?, ?, ?, ?)""",
                (
                    project_id,
                    next_revision + 1,
                    f"Wiederhergestellt aus R{int(revision['revision_number'])}",
                    restored_payload,
                    package.project.updated_at,
                ),
            )
            cursor = connection.execute(
                """UPDATE projects
                   SET name = ?, version = version + 1, document_json = ?, updated_at = ?
                   WHERE id = ? AND version = ?""",
                (
                    package.project.name,
                    restored_payload,
                    package.project.updated_at,
                    project_id,
                    expected_version,
                ),
            )
            if cursor.rowcount != 1:
                raise VersionConflict("Der Arbeitsstand wurde während der Wiederherstellung geändert.")
            return expected_version + 1

    def preview_project_import(self, data: bytes) -> ArchitecturePackage:
        document = json.loads(data)
        if not isinstance(document, dict):
            raise ValueError("Die JSON-Datei muss ein Architecture Package als Objekt enthalten.")
        _migrate_duplicate_hierarchy_names(document)
        package = ArchitecturePackage.model_validate(document)
        normalize_architecture_names(package)
        return ArchitecturePackage.model_validate(package.export_dict())

    def import_project(self, data: bytes, fallback_name: str = "Importierte Architektur",
                       workflow: ProjectWorkflow | None = None) -> tuple[ArchitecturePackage, int]:
        package = self.preview_project_import(data)
        if workflow is not None:
            select_import_workflow(package, workflow)
        package.project.id = ArchitecturePackage().project.id
        base_name = package.project.name.strip() or fallback_name
        existing = {item.name.casefold() for item in self.list_projects()}
        candidate = base_name
        suffix = 2
        while candidate.casefold() in existing:
            candidate = f"{base_name} ({suffix})"
            suffix += 1
        package.project.name = candidate
        package.project.created_at = utc_now()
        package.project.updated_at = package.project.created_at
        return self.create_project(package)

    def import_into_project(self, project_id: str, data: bytes,
                            expected_version: int,
                            workflow: ProjectWorkflow | None = None) -> tuple[ArchitecturePackage, int]:
        """Validate first, then commit old and imported snapshots atomically."""
        imported = self.preview_project_import(data)
        if workflow is not None:
            select_import_workflow(imported, workflow)
        with self._connect() as connection:
            project = connection.execute(
                "SELECT name, version, document_json, created_at FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if project is None:
                raise KeyError(project_id)
            if int(project["version"]) != expected_version:
                raise VersionConflict("Der Arbeitsstand wurde zwischenzeitlich geändert. Import erneut prüfen.")
            imported.project.id = project_id
            imported.project.name = str(project["name"])
            imported.project.created_at = str(project["created_at"])
            imported.touch()
            payload = self._serialize(imported)
            # Revalidate the actual stored snapshot after replacing the
            # container identity, before touching a persisted row.
            imported = ArchitecturePackage.model_validate(json.loads(payload))
            next_number = int(connection.execute(
                "SELECT COALESCE(MAX(revision_number), 0) + 1 FROM revisions WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0])
            timestamp = utc_now()
            connection.execute(
                """INSERT INTO revisions(project_id, revision_number, label, document_json, created_at)
                   VALUES(?, ?, ?, ?, ?)""",
                (project_id, next_number, "Automatische Sicherung vor JSON-Import", project["document_json"], timestamp),
            )
            connection.execute(
                """INSERT INTO revisions(project_id, revision_number, label, document_json, created_at)
                   VALUES(?, ?, ?, ?, ?)""",
                (project_id, next_number + 1, "JSON-Import als neuer Arbeitsstand", payload, imported.project.updated_at),
            )
            cursor = connection.execute(
                """UPDATE projects SET version = version + 1, document_json = ?, updated_at = ?
                   WHERE id = ? AND version = ?""",
                (payload, imported.project.updated_at, project_id, expected_version),
            )
            if cursor.rowcount != 1:
                raise VersionConflict("Der Arbeitsstand wurde während des Imports geändert.")
        return imported, expected_version + 1

    def stats(self, package: ArchitecturePackage) -> dict[str, int]:
        elements = [element for domain in package.domains for element in domain.elements]
        ports = [port for element in elements for port in element.ports]
        legacy_signals = [signal for port in ports for signal in port.signals]
        return {
            "domains": len(package.domains),
            "elements": len(elements),
            "ports": len(ports),
            "signals": len(package.signals) if package.signals else len(legacy_signals),
            "connections": len(package.connections),
        }
