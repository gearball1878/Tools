from __future__ import annotations

import json
import tarfile
from pathlib import Path


def test_mentor_template_archive_replaces_loose_partition_json_files() -> None:
    root = Path(__file__).resolve().parents[1] / "symbol_wizard" / "symbol_templates"
    archive = root / "mentor_known_templates.tar.xz"
    manifest = root / ".template_manifest.json"

    assert archive.exists()
    assert manifest.exists()
    assert not list((root / "mentor_known").glob("*.json")) if (root / "mentor_known").exists() else True

    data = json.loads(manifest.read_text(encoding="utf-8"))
    referenced = {str(meta.get("file") or "").replace("\\", "/") for meta in (data.get("templates") or {}).values()}
    referenced = {name for name in referenced if name.startswith("mentor_known/") and name.endswith(".json")}
    assert referenced

    with tarfile.open(archive, "r:xz") as tf:
        archived = {m.name.replace("\\", "/") for m in tf.getmembers() if m.isfile()}

    assert referenced <= archived
