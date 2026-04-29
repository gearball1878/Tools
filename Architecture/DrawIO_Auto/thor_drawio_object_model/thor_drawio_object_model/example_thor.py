from pathlib import Path
from model import Design, Block, Port, Connection
from drawio_renderer import DrawioRenderer


def build_design() -> Design:
    camera = Block(
        name="Camera_Module",
        label="Camera Module",
        description="External camera module",
        ports=[
            Port("VIN", "power", side="left", voltage="12V"),
            Port("GND", "ground", side="left"),
            Port("CSI_OUT", "output", side="right", protocol="CSI2_DPHY", constraint_class="CSI2_DPHY"),
        ],
    )

    power = Block(
        name="Power_Input",
        label="Power Input",
        ports=[
            Port("VIN_24V", "power", side="left", voltage="24V"),
            Port("GND_IN", "ground", side="left"),
            Port("VOUT_12V", "power", side="right", voltage="12V"),
            Port("GND", "ground", side="right"),
        ],
    )

    thor = Block(
        name="THOR_SoM",
        label="THOR SoM",
        description="Hierarchical SoM block",
        ports=[
            Port("VIN_12V", "power", side="left", voltage="12V"),
            Port("GND", "ground", side="left"),
            Port("CSI_IN0", "input", side="left", protocol="CSI2_DPHY", constraint_class="CSI2_DPHY"),
            Port("XFI0", "bidirectional", side="right", protocol="XFI", constraint_class="10G_XFI"),
        ],
        children=[
            Block(
                name="CPU",
                label="CPU / NVIDIA SoC",
                ports=[
                    Port("VDD_CPU", "power", side="left", voltage="0.8V"),
                    Port("CAM_AXI", "input", side="right", protocol="AXI_STREAM"),
                    Port("ETH_XFI0", "bidirectional", side="right", protocol="XFI"),
                ],
            ),
            Block(
                name="PMIC",
                label="PMIC",
                ports=[
                    Port("VIN_12V", "power", side="left", voltage="12V"),
                    Port("VDD_CPU", "power", side="right", voltage="0.8V"),
                    Port("PGOOD", "output", side="right"),
                ],
            ),
            Block(
                name="CSI_Bridge",
                label="CSI / GMSL Bridge",
                ports=[
                    Port("CSI_IN0", "input", side="left", protocol="CSI2_DPHY", constraint_class="CSI2_DPHY"),
                    Port("AXI_STREAM", "output", side="right", protocol="AXI_STREAM"),
                ],
            ),
            Block(
                name="ETH_MAC",
                label="Ethernet MAC",
                ports=[
                    Port("XFI0", "bidirectional", side="right", protocol="XFI", constraint_class="10G_XFI"),
                ],
            ),
        ],
    )

    phy = Block(
        name="Ethernet_PHY",
        label="10G Ethernet PHY",
        ports=[
            Port("XFI", "bidirectional", side="left", protocol="XFI", constraint_class="10G_XFI"),
            Port("MDI", "analog", side="right", protocol="10GBASE-T"),
        ],
    )

    return Design(
        name="THOR hierarchical object model example",
        root_blocks=[camera, power, thor, phy],
        connections=[
            Connection(
                name="CAM_Link_01",
                type="bus",
                source="Camera_Module.CSI_OUT",
                target="THOR_SoM.CSI_IN0",
                protocol="CSI2_DPHY",
                width=4,
                constraint_class="CSI2_DPHY",
            ),
            Connection(
                name="PWR_12V",
                type="net",
                source="Power_Input.VOUT_12V",
                target="THOR_SoM.VIN_12V",
                constraint_class="PWR_12V",
            ),
            Connection(
                name="GND",
                type="net",
                source="Power_Input.GND",
                target="THOR_SoM.GND",
                constraint_class="GND",
            ),
            Connection(
                name="XFI_Link_01",
                type="bus",
                source="THOR_SoM.XFI0",
                target="Ethernet_PHY.XFI",
                protocol="XFI",
                width=4,
                constraint_class="10G_XFI",
            ),
            Connection(
                name="Internal_CSI_To_Bridge",
                type="bus",
                source="THOR_SoM.CSI_IN0",
                target="THOR_SoM.CSI_Bridge.CSI_IN0",
                protocol="CSI2_DPHY",
                width=4,
                constraint_class="CSI2_DPHY",
            ),
            Connection(
                name="Internal_AXI_Video",
                type="bus",
                source="THOR_SoM.CSI_Bridge.AXI_STREAM",
                target="THOR_SoM.CPU.CAM_AXI",
                protocol="AXI_STREAM",
                width=32,
            ),
            Connection(
                name="Internal_VDD_CPU",
                type="net",
                source="THOR_SoM.PMIC.VDD_CPU",
                target="THOR_SoM.CPU.VDD_CPU",
                constraint_class="PWR_CORE",
            ),
            Connection(
                name="Internal_XFI0",
                type="bus",
                source="THOR_SoM.ETH_MAC.XFI0",
                target="THOR_SoM.CPU.ETH_XFI0",
                protocol="XFI",
                width=4,
                constraint_class="10G_XFI",
            ),
        ],
    )


if __name__ == "__main__":
    design = build_design()

    out_dir = Path(__file__).resolve().parent
    drawio_file = out_dir / "thor_hierarchical_object_model.drawio"
    json_file = out_dir / "thor_hierarchical_object_model.json"

    DrawioRenderer(design).render(drawio_file)
    json_file.write_text(design.to_json(), encoding="utf-8")

    print(f"Created: {drawio_file}")
    print(f"Created: {json_file}")
