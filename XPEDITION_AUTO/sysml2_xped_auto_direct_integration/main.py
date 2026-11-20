from __future__ import annotations

import argparse
import json
from pathlib import Path

from sysml2_arch_builder.model import ArchitectureModel, ConnectionType, NetReferenceDirection
from sysml2_arch_builder.exporters import SysML2Exporter, DrawioExporter, BusContentsIniExporter
from sysml2_arch_builder.bus_content import BusContentTemplates
from sysml2_arch_builder.xped_adapter import load_xped_json, save_xped_exchange, validate_xped_exchange


def create_demo(template_path: Path) -> ArchitectureModel:
    model = ArchitectureModel("Generic_Architecture")
    model.add_domain("SOM")
    model.add_domain("ETH")
    model.add_arch_element("SOM", "Host_Block")
    model.add_arch_element("ETH", "Peripheral_Block")
    model.set_block_host("SOM.Host_Block", True)
    templates = BusContentTemplates(template_path)
    inst = templates.generate_interfaces("SPI_[Link/Port]", 1, 1, "Link")[0]
    model.add_interface_reference("SOM.Host_Block", inst.name, ConnectionType.BUS, NetReferenceDirection.BIDI, inst.signals, extra_attributes={"family": "interface"})
    model.add_interface_reference("ETH.Peripheral_Block", inst.name, ConnectionType.BUS, NetReferenceDirection.BIDI, inst.signals, extra_attributes={"family": "interface"})
    return model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--out", default="out")
    parser.add_argument("--xped-export", metavar="BUILDER_JSON", help="convert builder JSON to the xped_auto exchange format")
    parser.add_argument("--xped-import", metavar="XPED_JSON", help="convert an exchange JSON or Xpedition snapshot to builder JSON")
    parser.add_argument("--manifest", help="optional bridge map used for stable IDs")
    parser.add_argument("--system-name", help="system name for compact Xpedition snapshots")
    args = parser.parse_args()
    selected = sum(bool(value) for value in (args.gui, args.demo, args.xped_export, args.xped_import))
    if selected > 1:
        parser.error("choose only one of --gui, --demo, --xped-export, or --xped-import")
    if args.gui:
        from sysml2_arch_builder.gui import run_gui
        run_gui()
        return
    if args.demo:
        out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
        model = create_demo(Path(__file__).resolve().parent / "Interface_Template_File.json")
        base = out / model.name
        model.save_json(base.with_suffix(".json"))
        SysML2Exporter(model).save(base.with_suffix(".sysml"))
        DrawioExporter(model).save(base.with_suffix(".drawio"))
        BusContentsIniExporter(model).save(out / "busconts.ini")
        print(f"Generated demo files in {out}")
        return
    if args.xped_export:
        model = ArchitectureModel.load_json(args.xped_export)
        target = Path(args.out)
        if target.suffix.lower() != ".json":
            target = target / f"{model.name}.xped.json"
        exchange, mapping, report = save_xped_exchange(model, target, args.manifest)
        errors = validate_xped_exchange(json.loads(exchange.read_text(encoding="utf-8")))
        if errors:
            raise ValueError("Generated Xpedition exchange is invalid:\n- " + "\n- ".join(errors))
        print(f"Xpedition exchange: {exchange}")
        print(f"ID map: {mapping}")
        for warning in report.warnings:
            print(f"Warning: {warning}")
        return
    if args.xped_import:
        model, report = load_xped_json(args.xped_import, args.manifest, args.system_name)
        target = Path(args.out)
        if target.suffix.lower() != ".json":
            target = target / f"{model.name}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        model.save_json(target)
        print(f"Builder JSON: {target}")
        for warning in report.warnings:
            print(f"Warning: {warning}")
        return
    parser.print_help()


if __name__ == "__main__":
    main()
