from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Read an Xpedition project into a compact JSON snapshot.")
    parser.add_argument("--project", required=True, help="Xpedition .prj file")
    parser.add_argument("--out", required=True, help="snapshot JSON file")
    parser.add_argument("--progid", default="ViewDraw.Application")
    args = parser.parse_args()

    if os.name != "nt":
        raise RuntimeError("Xpedition COM automation can only run on Windows.")
    project = Path(args.project).expanduser().resolve()
    if not project.is_file():
        raise ValueError(f"Xpedition project does not exist: {project}")
    target = Path(args.out).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    legacy_root = Path(__file__).resolve().parent / "legacy"
    auto_scheme_root = legacy_root / "auto_scheme"
    for item in (legacy_root, auto_scheme_root):
        if str(item) not in sys.path:
            sys.path.insert(0, str(item))

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
    finally:
        try:
            if opened:
                connect.close_project()
        finally:
            connect.cleanup_com()


if __name__ == "__main__":
    main()
