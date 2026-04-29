from pathlib import Path
from model import Design, Block, Port, Connection
from drawio_renderer import DrawioRenderer


def p(id, name, type, **attrs):
    return Port(id=id, name=name, type=type, attributes=attrs)


def build_design() -> Design:
    psu_thor = Block(
        id="PSU_THOR",
        name="PSU THOR",
        level=1,
        ports=[p("VIN_24V", "VIN 24V", "power", voltage="24V"),
               p("GND", "GND", "ground"),
               p("VOUT_CORE", "VOUT Core", "power", voltage="0.8V")],
        attributes={"domain": "Power", "owner": "PowerDesign"},
        children=[
            Block(
                id="PSU_THOR_Core_Voltage_1",
                name="THOR Core Voltage Rail 1",
                level=2,
                ports=[p("VIN", "VIN", "power"), p("GND", "GND", "ground"), p("VOUT", "VOUT", "power")],
                attributes={"rail": "VDD_CPU", "voltage": "0.8V", "current_max_A": 80},
                children=[
                    Block(
                        id="CFG_PSU_THOR_Core_Voltage_1",
                        name="Configuration: feedback / enable / sequencing",
                        level=3,
                        ports=[p("FB", "FB", "analog"), p("EN", "EN", "in"), p("PGOOD", "PGOOD", "out")],
                        attributes={"purpose": "connect external functional components for configuration"},
                        children=[
                            Block(
                                id="OBJ_Buck_Controller_Reusable_1",
                                name="Reusable Buck Controller Instance",
                                level=4,
                                ports=[p("VIN", "VIN", "power"), p("SW", "SW", "analog"), p("FB", "FB", "analog"),
                                       p("EN", "EN", "in"), p("PGOOD", "PGOOD", "out")],
                                attributes={"object_type": "buck_controller", "library": "power.lib", "reuse": True},
                            ),
                            Block(
                                id="OBJ_Feedback_Divider_Reusable_1",
                                name="Reusable Feedback Divider Instance",
                                level=4,
                                ports=[p("VOUT_SENSE", "VOUT Sense", "analog"), p("FB_OUT", "FB Out", "analog")],
                                attributes={"object_type": "resistor_divider", "reuse": True},
                            ),
                        ],
                    )
                ],
            )
        ],
    )

    psu_eth = Block(
        id="PSU_ETH",
        name="PSU Ethernet",
        level=1,
        ports=[p("VIN_12V", "VIN 12V", "power"), p("GND", "GND", "ground"), p("VDDIO_ETH", "VDDIO ETH", "power")],
        attributes={"domain": "Power"},
        children=[
            Block(
                id="PSU_ETH_VDDIO_1",
                name="Ethernet VDDIO Rail 1",
                level=2,
                ports=[p("VIN", "VIN", "power"), p("GND", "GND", "ground"), p("VOUT", "VOUT", "power")],
                attributes={"rail": "VDDIO_ETH", "voltage": "1.8V"},
            )
        ],
    )

    som = Block(
        id="SoM",
        name="THOR SoM",
        level=1,
        ports=[p("VIN_CORE", "VIN Core", "power"), p("GND", "GND", "ground"),
               p("ETH_XFI0", "ETH XFI0", "bidi"), p("SAFETY_SPI", "Safety SPI", "bidi")],
        attributes={"domain": "Compute"},
        children=[
            Block(
                id="SoM_Compute_Core_1",
                name="Compute Core 1",
                level=2,
                ports=[p("VIN_CORE", "VIN Core", "power"), p("XFI0", "XFI0", "bidi"), p("SPI0", "SPI0", "bidi")],
                attributes={"processor": "NVIDIA_THOR"},
                children=[
                    Block(
                        id="CFG_SoM_Boot_1",
                        name="Configuration: boot straps / EEPROM",
                        level=3,
                        ports=[p("I2C", "I2C", "bidi"), p("BOOTMODE", "Boot Mode", "in")],
                        children=[
                            Block(
                                id="OBJ_EEPROM_Reusable_1",
                                name="Reusable EEPROM Instance",
                                level=4,
                                ports=[p("VCC", "VCC", "power"), p("GND", "GND", "ground"), p("I2C", "I2C", "bidi")],
                                attributes={"object_type": "i2c_eeprom", "reuse": True},
                            )
                        ],
                    )
                ],
            )
        ],
    )

    safety = Block(
        id="SafetyMicro",
        name="Safety Micro",
        level=1,
        ports=[p("VIN_3V3", "VIN 3V3", "power"), p("GND", "GND", "ground"), p("SPI_TO_SOM", "SPI to SoM", "bidi")],
        attributes={"domain": "Safety"},
        children=[
            Block(
                id="SafetyMicro_Core_1",
                name="Safety Micro Core 1",
                level=2,
                ports=[p("VDD", "VDD", "power"), p("SPI", "SPI", "bidi"), p("RESET_OUT", "Reset Out", "out")],
                attributes={"asil_relevance": "high"},
            )
        ],
    )

    radar = Block(
        id="Radar",
        name="Radar",
        level=1,
        ports=[p("VIN_12V", "VIN 12V", "power"), p("GND", "GND", "ground"), p("ETH_DATA", "Ethernet Data", "bidi")],
        attributes={"domain": "Sensor"},
        children=[
            Block(
                id="Radar_Frontend_1",
                name="Radar Frontend 1",
                level=2,
                ports=[p("VIN", "VIN", "power"), p("IF_ANALOG", "IF Analog", "analog"), p("ETH_DATA", "ETH Data", "bidi")],
                attributes={"sensor_type": "surround_radar"},
            )
        ],
    )

    return Design(
        id="THOR_ECAD_ARCH",
        name="THOR ECAD 4-Level Architecture",
        domains=[psu_thor, psu_eth, som, safety, radar],
        attributes={"project": "Liebherr THOR SoM ECAD Design"},
        connections=[
            Connection(id="NET_PSU_THOR_CORE_TO_SOM", name="PWR_THOR_CORE", type="net",
                       source="PSU_THOR.VOUT_CORE", target="SoM.VIN_CORE",
                       attributes={"constraint_class": "PWR_CORE"}),
            Connection(id="BUS_SOM_TO_SAFETY_SPI", name="SAFETY_SPI", type="bus",
                       source="SoM.SAFETY_SPI", target="SafetyMicro.SPI_TO_SOM",
                       attributes={"protocol": "SPI", "width": 4, "constraint_class": "SPI"}),
            Connection(id="BUS_SOM_TO_RADAR_ETH", name="RADAR_ETH", type="bus",
                       source="SoM.ETH_XFI0", target="Radar.ETH_DATA",
                       attributes={"protocol": "Ethernet", "constraint_class": "ETH"}),
            Connection(id="NET_BUCK_FB", name="BUCK_FB", type="net",
                       source="OBJ_Feedback_Divider_Reusable_1.FB_OUT", target="OBJ_Buck_Controller_Reusable_1.FB",
                       attributes={"constraint_class": "ANALOG_FB"}),
            Connection(id="BUS_BOOT_EEPROM_I2C", name="BOOT_EEPROM_I2C", type="bus",
                       source="CFG_SoM_Boot_1.I2C", target="OBJ_EEPROM_Reusable_1.I2C",
                       attributes={"protocol": "I2C", "width": 2, "constraint_class": "I2C"}),
        ],
    )


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent
    design = build_design()

    drawio_file = out_dir / "thor_4level_topdown.drawio"
    json_file = out_dir / "thor_4level_topdown.json"

    DrawioRenderer(design).render(drawio_file)
    json_file.write_text(design.to_json(), encoding="utf-8")

    print(f"Created: {drawio_file}")
    print(f"Created: {json_file}")
