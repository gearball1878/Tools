from __future__ import annotations

import argparse
from pathlib import Path

from sysml2_arch_builder.model import ArchitectureModel, ConnectionType, NetReferenceDirection
from sysml2_arch_builder.exporters import SysML2Exporter, DrawioExporter, BusContentsIniExporter
from sysml2_arch_builder.bus_content import BusContentTemplates


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
    args = parser.parse_args()
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
        BusContentsIniExporter(model).save(out / f"{model.name}_buscontents.ini")
        print(f"Generated demo files in {out}")
        return
    parser.print_help()


if __name__ == "__main__":
    main()
