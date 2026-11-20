from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from sysml2_arch_builder.xped_adapter import normalize_for_auto_schem, validate_xped_exchange


def _existing_file(value: str, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"{label} does not exist: {path}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and optionally run auto_schem from a SysML architecture JSON.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--architecture-json", help="native JSON from the SysML2 Architecture Builder (preferred)")
    source_group.add_argument("--exchange-json", help="internal xped_auto exchange JSON (compatibility input)")
    parser.add_argument("--project", required=True, help="Xpedition .prj file")
    parser.add_argument("--bus-content", help="target busconts.ini; defaults next to the project")
    parser.add_argument("--interface-template", default=str(Path(__file__).resolve().parents[1] / "Interface_Template_File.json"))
    parser.add_argument("--project-name")
    parser.add_argument("--apply", action="store_true", help="actually open and modify the Xpedition project")
    args = parser.parse_args()

    source = _existing_file(args.architecture_json or args.exchange_json, "Architecture JSON")
    project = _existing_file(args.project, "Xpedition project")
    template = _existing_file(args.interface_template, "Interface template")
    data = json.loads(source.read_text(encoding="utf-8"))
    normalized, _manifest, report, source_format = normalize_for_auto_schem(data, system_name=source.stem)
    errors = validate_xped_exchange(normalized)
    if errors:
        raise ValueError("Invalid exchange JSON:\n- " + "\n- ".join(errors))
    bus_content = Path(args.bus_content).expanduser().resolve() if args.bus_content else project.with_name("busconts.ini")

    summary = {
        "architecture_json": str(source),
        "source_format": source_format,
        "systems": len(normalized),
        "domains": sum(len(system.get("System Blocks", [])) for system in normalized),
        "project": str(project),
        "bus_content": str(bus_content),
        "interface_template": str(template),
        "mode": "apply" if args.apply else "dry-run",
    }
    print(json.dumps(summary, indent=2))
    for warning in report.warnings:
        print(f"Warning: {warning}")
    if not args.apply:
        print("Dry-run only. Add --apply to invoke Xpedition COM automation.")
        return
    if os.name != "nt":
        raise RuntimeError("Xpedition COM automation can only run on Windows.")

    script = Path(__file__).resolve().parent / "legacy" / "auto_scheme" / "auto_scheme.py"
    command = [
        sys.executable,
        str(script),
        "--architecture-json", str(source),
        "--project", str(project),
        "--bus-content", str(bus_content),
        "--interface-template", str(template),
    ]
    if args.project_name:
        command.extend(["--project-name", args.project_name])
    subprocess.run(command, check=True, cwd=script.parent)


if __name__ == "__main__":
    main()
