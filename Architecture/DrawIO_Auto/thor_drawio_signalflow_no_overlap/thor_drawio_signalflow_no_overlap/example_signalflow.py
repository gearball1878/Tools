from pathlib import Path
from model import Design, Block, Port, Signal
from drawio_signalflow_renderer import DrawioSignalFlowRenderer


def p(id, name, type, **attrs):
    return Port(id=id, name=name, type=type, attributes=attrs)


def sig(id, name, type, endpoints, **attrs):
    return Signal(
        id=id,
        name=name,
        type=type,
        stereotype="Bus" if type == "bus" else "Net",
        endpoints=endpoints,
        attributes=attrs,
    )


def build_design() -> Design:
    psu_thor = Block(
        id="PSU_THOR",
        name="PSU_THOR",
        level=1,
        stereotype="Domain",
        ports=[
            p("VIN_24V", "VIN_24V", "power", voltage="24V", constraint_class="PWR_IN"),
            p("GND", "GND", "ground", constraint_class="GND"),
            p("VOUT_CORE", "VOUT_CORE", "power", voltage="0.8V", current_max_A=80, constraint_class="PWR_CORE"),
        ],
        attributes={"domain": "Power", "owner": "PowerDesign", "thermal_budget_W": 25},
        children=[
            Block(
                id="PSU_THOR_Core_Voltage_1",
                name="PSU_THOR_Core_Voltage_1",
                level=2,
                stereotype="ArchitectureElement",
                ports=[
                    p("VIN", "VIN", "power", voltage="12V"),
                    p("GND", "GND", "ground"),
                    p("VOUT", "VOUT", "power", voltage="0.8V", current_max_A=80),
                    p("EN", "EN", "in", constraint_class="CTRL"),
                    p("PGOOD", "PGOOD", "out", constraint_class="STATUS"),
                ],
                attributes={"rail": "VDD_CPU", "voltage": "0.8V", "current_max_A": 80},
                children=[
                    Block(
                        id="CFG_PSU_THOR_Core_Voltage_1",
                        name="CFG_PSU_THOR_Core_Voltage_1",
                        level=3,
                        stereotype="Configuration",
                        ports=[
                            p("VIN", "VIN", "power"),
                            p("GND", "GND", "ground"),
                            p("VOUT_SENSE", "VOUT_SENSE", "analog"),
                            p("FB", "FB", "analog", constraint_class="ANALOG_FB"),
                            p("EN", "EN", "in"),
                            p("PGOOD", "PGOOD", "out"),
                        ],
                        attributes={"purpose": "configure buck regulator instance"},
                        children=[
                            Block(
                                id="OBJ_Buck_Controller_Reusable_1",
                                name="OBJ_Buck_Controller_Reusable_1",
                                level=4,
                                stereotype="ReusableFunctionalInstance",
                                ports=[
                                    p("VIN", "VIN", "power"),
                                    p("GND", "GND", "ground"),
                                    p("SW", "SW", "analog"),
                                    p("FB", "FB", "analog"),
                                    p("EN", "EN", "in"),
                                    p("PGOOD", "PGOOD", "out"),
                                ],
                                attributes={"object_type": "buck_controller", "library": "power.lib", "reuse": True},
                            ),
                            Block(
                                id="OBJ_Feedback_Divider_Reusable_1",
                                name="OBJ_Feedback_Divider_Reusable_1",
                                level=4,
                                stereotype="ReusableFunctionalInstance",
                                ports=[
                                    p("VOUT_SENSE", "VOUT_SENSE", "analog"),
                                    p("GND", "GND", "ground"),
                                    p("FB_OUT", "FB_OUT", "analog"),
                                ],
                                attributes={"object_type": "resistor_divider", "tolerance_percent": 0.1, "reuse": True},
                            ),
                        ],
                    )
                ],
            )
        ],
    )

    psu_eth = Block(
        id="PSU_ETH",
        name="PSU_ETH",
        level=1,
        stereotype="Domain",
        ports=[
            p("VIN_12V", "VIN_12V", "power", voltage="12V"),
            p("GND", "GND", "ground"),
            p("VDDIO_ETH", "VDDIO_ETH", "power", voltage="1.8V"),
        ],
        attributes={"domain": "Power", "owner": "PowerDesign"},
        children=[
            Block(
                id="PSU_ETH_VDDIO_1",
                name="PSU_ETH_VDDIO_1",
                level=2,
                stereotype="ArchitectureElement",
                ports=[
                    p("VIN", "VIN", "power", voltage="12V"),
                    p("GND", "GND", "ground"),
                    p("VOUT", "VOUT", "power", voltage="1.8V"),
                ],
                attributes={"rail": "VDDIO_ETH", "voltage": "1.8V"},
            )
        ],
    )

    som = Block(
        id="SoM",
        name="SoM",
        level=1,
        stereotype="Domain",
        ports=[
            p("VIN_CORE", "VIN_CORE", "power", voltage="0.8V"),
            p("VIN_ETH_IO", "VIN_ETH_IO", "power", voltage="1.8V"),
            p("GND", "GND", "ground"),
            p("SAFETY_SPI", "SAFETY_SPI", "bidi", protocol="SPI", width=4),
            p("RADAR_ETH", "RADAR_ETH", "bidi", protocol="Ethernet"),
        ],
        attributes={"domain": "Compute", "processor_family": "THOR"},
        children=[
            Block(
                id="SoM_Compute_Core_1",
                name="SoM_Compute_Core_1",
                level=2,
                stereotype="ArchitectureElement",
                ports=[
                    p("VIN_CORE", "VIN_CORE", "power"),
                    p("GND", "GND", "ground"),
                    p("SPI0", "SPI0", "bidi", protocol="SPI"),
                    p("ETH0", "ETH0", "bidi", protocol="Ethernet"),
                    p("BOOT_I2C", "BOOT_I2C", "bidi", protocol="I2C"),
                ],
                attributes={"processor": "NVIDIA_THOR"},
                children=[
                    Block(
                        id="CFG_SoM_Boot_1",
                        name="CFG_SoM_Boot_1",
                        level=3,
                        stereotype="Configuration",
                        ports=[
                            p("VCC", "VCC", "power"),
                            p("GND", "GND", "ground"),
                            p("I2C", "I2C", "bidi"),
                            p("BOOTMODE", "BOOTMODE", "in"),
                        ],
                        attributes={"purpose": "boot straps and EEPROM configuration"},
                        children=[
                            Block(
                                id="OBJ_EEPROM_Reusable_1",
                                name="OBJ_EEPROM_Reusable_1",
                                level=4,
                                stereotype="ReusableFunctionalInstance",
                                ports=[
                                    p("VCC", "VCC", "power"),
                                    p("GND", "GND", "ground"),
                                    p("I2C", "I2C", "bidi"),
                                    p("WP", "WP", "in"),
                                ],
                                attributes={"object_type": "i2c_eeprom", "library": "memory.lib", "reuse": True},
                            )
                        ],
                    )
                ],
            )
        ],
    )

    safety = Block(
        id="SafetyMicro",
        name="SafetyMicro",
        level=1,
        stereotype="Domain",
        ports=[
            p("VIN_3V3", "VIN_3V3", "power", voltage="3.3V"),
            p("GND", "GND", "ground"),
            p("SPI_TO_SOM", "SPI_TO_SOM", "bidi", protocol="SPI"),
            p("RESET_OUT", "RESET_OUT", "out"),
        ],
        attributes={"domain": "Safety", "asil_relevance": "high"},
    )

    radar = Block(
        id="Radar",
        name="Radar",
        level=1,
        stereotype="Domain",
        ports=[
            p("VIN_12V", "VIN_12V", "power", voltage="12V"),
            p("GND", "GND", "ground"),
            p("ETH_DATA", "ETH_DATA", "bidi", protocol="Ethernet"),
        ],
        attributes={"domain": "Sensor", "sensor_type": "surround_radar"},
    )

    return Design(
        id="THOR_SIGNALFLOW_ARCH",
        name="THOR UML Signalflow Architecture",
        domains=[psu_thor, psu_eth, som, safety, radar],
        attributes={"project": "Liebherr THOR SoM ECAD Design"},
        signals=[
            sig("NET_PSU_THOR_CORE_TO_SOM", "PWR_THOR_CORE", "net",
                ["PSU_THOR.VOUT_CORE", "SoM.VIN_CORE"],
                constraint_class="PWR_CORE", voltage="0.8V", current_max_A=80),

            sig("NET_PSU_ETH_VDDIO_TO_SOM", "PWR_ETH_IO", "net",
                ["PSU_ETH.VDDIO_ETH", "SoM.VIN_ETH_IO"],
                constraint_class="PWR_ETH_IO", voltage="1.8V"),

            sig("BUS_SOM_TO_SAFETY_SPI", "SAFETY_SPI", "bus",
                ["SoM.SAFETY_SPI", "SafetyMicro.SPI_TO_SOM"],
                protocol="SPI", width=4, constraint_class="SPI"),

            sig("BUS_SOM_TO_RADAR_ETH", "RADAR_ETH", "bus",
                ["SoM.RADAR_ETH", "Radar.ETH_DATA"],
                protocol="Ethernet", constraint_class="ETH"),

            sig("NET_L2_PSU_THOR_VOUT_TO_CFG", "VDD_CPU_CFG", "net",
                ["PSU_THOR_Core_Voltage_1.VOUT", "CFG_PSU_THOR_Core_Voltage_1.VOUT_SENSE"],
                constraint_class="PWR_CORE_SENSE"),

            sig("NET_BUCK_FB", "BUCK_FB", "net",
                ["OBJ_Feedback_Divider_Reusable_1.FB_OUT", "OBJ_Buck_Controller_Reusable_1.FB"],
                constraint_class="ANALOG_FB"),

            sig("NET_BUCK_EN", "BUCK_EN", "net",
                ["CFG_PSU_THOR_Core_Voltage_1.EN", "OBJ_Buck_Controller_Reusable_1.EN"],
                constraint_class="CTRL"),

            sig("NET_BUCK_PGOOD", "BUCK_PGOOD", "net",
                ["OBJ_Buck_Controller_Reusable_1.PGOOD", "CFG_PSU_THOR_Core_Voltage_1.PGOOD"],
                constraint_class="STATUS"),

            sig("BUS_BOOT_EEPROM_I2C", "BOOT_EEPROM_I2C", "bus",
                ["CFG_SoM_Boot_1.I2C", "OBJ_EEPROM_Reusable_1.I2C"],
                protocol="I2C", width=2, constraint_class="I2C"),
        ],
    )


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent
    design = build_design()

    DrawioSignalFlowRenderer(design).render(out_dir / "thor_uml_signalflow_no_overlap.drawio")
    (out_dir / "thor_uml_signalflow_no_overlap.json").write_text(design.to_json(), encoding="utf-8")

    print("Created thor_uml_signalflow_no_overlap.drawio")
    print("Created thor_uml_signalflow_no_overlap.json")
