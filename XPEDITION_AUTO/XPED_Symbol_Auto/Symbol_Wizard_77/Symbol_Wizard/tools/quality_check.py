"""Run dependency-light quality checks for Symbol Wizard.

The script intentionally uses only the Python standard library so it can run in
minimal environments before PySide6 is installed. It verifies that the source
compiles and that bundled JSON templates are syntactically valid.
"""

from __future__ import annotations

import compileall
import json
import tarfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = [ROOT / "symbol_wizard"]
JSON_DIRS = [ROOT / "symbol_wizard" / "symbol_templates", ROOT / "symbol_wizard" / "symbol_types"]
TEMPLATE_ARCHIVES = [ROOT / "symbol_wizard" / "symbol_templates" / "mentor_known_templates.tar.xz"]


def check_compile() -> bool:
    return all(compileall.compile_dir(str(path), quiet=1) for path in SOURCE_DIRS)


def check_json_files() -> list[Path]:
    invalid: list[Path] = []
    for base in JSON_DIRS:
        for path in sorted(base.rglob("*.json")):
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                invalid.append(path)
    return invalid



def check_template_archives() -> list[str]:
    invalid: list[str] = []
    for archive in TEMPLATE_ARCHIVES:
        if not archive.exists():
            continue
        try:
            with tarfile.open(archive, "r:xz") as tf:
                for member in tf.getmembers():
                    if not member.isfile() or not member.name.endswith(".json"):
                        continue
                    fh = tf.extractfile(member)
                    if fh is None:
                        invalid.append(f"{archive.relative_to(ROOT)}:{member.name}")
                        continue
                    try:
                        json.loads(fh.read().decode("utf-8"))
                    except Exception:
                        invalid.append(f"{archive.relative_to(ROOT)}:{member.name}")
        except Exception:
            invalid.append(str(archive.relative_to(ROOT)))
    return invalid

def main() -> int:
    ok = True
    if not check_compile():
        print("Python compilation check failed.", file=sys.stderr)
        ok = False

    invalid_json = check_json_files()
    if invalid_json:
        print("Invalid JSON files:", file=sys.stderr)
        for path in invalid_json:
            print(f" - {path.relative_to(ROOT)}", file=sys.stderr)
        ok = False

    invalid_archives = check_template_archives()
    if invalid_archives:
        print("Invalid template archive JSON entries:", file=sys.stderr)
        for name in invalid_archives:
            print(f" - {name}", file=sys.stderr)
        ok = False

    if ok:
        print("Quality checks passed: Python source compiles and JSON/template-archive assets are valid.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
