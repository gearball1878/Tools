from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

from xped_auto.arch_json_reader import ArchJsonReader
from xped_auto.discovery import discover_xpedition_installations, xpedition_unavailable_reason


def _existing_file(value: str, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"{label} does not exist: {path}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and optionally run auto_schem from a SysML architecture JSON.")
    parser.add_argument("--architecture-json", required=True, help="versioned JSON from the SysML architecture GUI")
    parser.add_argument("--project", required=True, help="Xpedition .prj file")
    parser.add_argument("--bus-content", help="target busconts.ini; defaults next to the project")
    parser.add_argument("--interface-template", default=str(Path(__file__).resolve().parents[1] / "Interface_Template_File.json"))
    parser.add_argument("--project-name")
    parser.add_argument("--apply", action="store_true", help="actually open and modify the Xpedition project")
    args = parser.parse_args()

    source = _existing_file(args.architecture_json, "Architecture JSON")
    project = _existing_file(args.project, "Xpedition project")
    template = _existing_file(args.interface_template, "Interface template")
    # Explicit handoff boundary: schema + model validation completes before any
    # installation discovery or COM process can run.
    architecture = ArchJsonReader(source)
    bus_content = Path(args.bus_content).expanduser().resolve() if args.bus_content else project.with_name("busconts.ini")

    summary = {
        "architecture_json": str(source),
        "source_format": architecture.source_format,
        "architecture": architecture.system,
        "domains": len(architecture.get_domain_names(architecture.system)),
        "architecture_elements": sum(
            len(architecture.get_ae_names_for_domain(architecture.system, domain))
            for domain in architecture.get_domain_names(architecture.system)
        ),
        "project": str(project),
        "bus_content": str(bus_content),
        "interface_template": str(template),
        "mode": "apply" if args.apply else "dry-run",
    }
    import json
    print(json.dumps(summary, indent=2))
    if not args.apply:
        print("Dry-run only. Add --apply to invoke Xpedition COM automation.")
        return
    installations = discover_xpedition_installations()
    unavailable_reason = xpedition_unavailable_reason(installations)
    if unavailable_reason:
        raise RuntimeError(unavailable_reason)

    script = Path(__file__).resolve().parent / "auto_scheme" / "auto_scheme.py"
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
