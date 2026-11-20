from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from xped_auto.arch_json_reader import ArchJsonReader
from xped_auto.arch_json_writer import ArchJsonWriter
from xped_auto.discovery import discover_xpedition_installations, xpedition_unavailable_reason


def _existing_file(value: str, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"{label} does not exist: {path}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Back-annotate Xpedition UIDs into the existing SysML architecture SPOT JSON."
    )
    parser.add_argument("--architecture-json", required=True, help="existing sysml2-architecture/v1 SPOT resource")
    parser.add_argument("--project", required=True, help="Xpedition .prj file")
    parser.add_argument(
        "--write-back",
        action="store_true",
        help="atomically update --architecture-json; without this flag the SPOT remains unchanged",
    )
    parser.add_argument("--progid", default="ViewDraw.Application")
    args = parser.parse_args()

    if os.name != "nt":
        raise RuntimeError("Xpedition COM automation can only run on Windows.")
    source = _existing_file(args.architecture_json, "Architecture SPOT JSON")
    project = _existing_file(args.project, "Xpedition project")
    if project.suffix.lower() != ".prj":
        raise ValueError(f"Expected an Xpedition .prj file: {project}")

    reason = xpedition_unavailable_reason(discover_xpedition_installations())
    if reason:
        raise RuntimeError(reason)

    # Validate and load the SPOT before any COM object is opened. The result of
    # gather_design_info is private in-memory transfer data, never a second JSON.
    architecture = ArchJsonReader(source)
    writer = ArchJsonWriter(architecture.model)

    auto_scheme_root = Path(__file__).resolve().parent / "auto_scheme"
    if str(auto_scheme_root) not in sys.path:
        sys.path.insert(0, str(auto_scheme_root))

    from auto_sch_base import asbc_connect  # type: ignore
    from gather_design_info import gather_design_info  # type: ignore

    connect = asbc_connect(args.progid, str(project))
    connect.init_com()
    opened = False
    try:
        application = connect.connect_to_application()
        connect.open_project()
        opened = True
        design = application.GetProjectData().GetiCDBDesignRootBlock(application.GetActiveDesign())
        com_data = gather_design_info().get_blocks(application, design)
        report = writer.apply_xpedition_back_annotation(com_data, project=project, strict=True)
        if args.write_back:
            writer.write_architecture_json(source)
    finally:
        try:
            if opened:
                connect.close_project()
        finally:
            connect.cleanup_com()

    result = {
        "architecture_json": str(source),
        "project": str(project),
        "mode": "write-back" if args.write_back else "validation-only",
        **report.to_dict(),
    }
    print(json.dumps(result, indent=2))
    if not args.write_back:
        print("SPOT unchanged. Add --write-back to persist the Back Annotation.")


if __name__ == "__main__":
    main()
