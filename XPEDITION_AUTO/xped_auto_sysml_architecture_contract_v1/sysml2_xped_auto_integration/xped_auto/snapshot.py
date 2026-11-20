from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from xped_auto.arch_json_writer import ArchJsonWriter


def main() -> None:
    parser = argparse.ArgumentParser(description="Read an Xpedition project into a compact JSON snapshot.")
    parser.add_argument("--project", required=True, help="Xpedition .prj file")
    parser.add_argument("--out", required=True, help="snapshot JSON file")
    parser.add_argument("--architecture-out", help="optional native SysML2 Architecture Builder JSON")
    parser.add_argument("--system-name", help="architecture name used with --architecture-out")
    parser.add_argument("--progid", default="ViewDraw.Application")
    args = parser.parse_args()

    if os.name != "nt":
        raise RuntimeError("Xpedition COM automation can only run on Windows.")
    project = Path(args.project).expanduser().resolve()
    if not project.is_file():
        raise ValueError(f"Xpedition project does not exist: {project}")
    target = Path(args.out).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

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
        snapshot = gather_design_info().get_blocks(application, design)
        target.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Xpedition snapshot: {target}")
        if args.architecture_out:
            architecture_target = Path(args.architecture_out).expanduser().resolve()
            architecture_target.parent.mkdir(parents=True, exist_ok=True)
            writer = ArchJsonWriter.from_xpedition_snapshot(
                snapshot,
                architecture_name=args.system_name or project.stem,
            )
            writer.write_architecture_json(architecture_target)
            print(f"Architecture JSON: {architecture_target}")
    finally:
        try:
            if opened:
                connect.close_project()
        finally:
            connect.cleanup_com()


if __name__ == "__main__":
    main()
