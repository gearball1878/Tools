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
        ports=[
            p("VIN_24V", "VIN 24V", "power", voltage="24V", constraint_class="PWR_IN"),
            p("GND", "GND", "ground", constraint_class="GND"),
            p("VOUT_CORE", "VOUT Core", "power", voltage="0.8V", current_max_A=80, constraint_class="PWR_CORE"),
        ],
        attributes={
            "domain": "Power",
            "owner": "PowerDesign",
            "asil_relevant": True,
            "thermal_budget_W": 25,
        },
        children=[
            Block(
                id="PSU_THOR_Core_Voltage_1",
                name="THOR Core Voltage Rail 1",
                level=2,
                ports=[
                    p("VIN", "VIN", "power", voltage="12V"),
                    p("GND", "GND", "ground"),
                    p("VOUT", "VOUT", "power", voltage="0.8V", current_max_A=80),
                ],
                attributes={
                    "rail": "VDD_CPU",
                    "voltage": "0.8V",
                    "current_max_A": 80,
                    "ecad_sheet": "PSU_THOR_CORE",
                },
                children=[
                    Block(
                        id="CFG_PSU_THOR_Core_Voltage_1",
                        name="Configuration: feedback / enable / sequencing",
                        level=3,
                        ports=[
                            p("FB", "FB", "analog", constraint_class="ANALOG_FB"),
                            p("EN", "EN", "in", constraint_class="CTRL"),
                            p("PGOOD", "PGOOD", "out", constraint_class="STATUS"),
                        ],
                        attributes={"purpose": "external functional components configure the rail"},
                        children=[
                            Block(
                                id="OBJ_Buck_Controller_Reusable_1",
                                name="Reusable Buck Controller Instance",
                                level=4,
                                ports=[
                                    p("VIN", "VIN", "power"),
                                    p("SW", "SW", "analog"),
                                    p("FB", "FB", "analog"),
                                    p("EN", "EN", "in"),
                                    p("PGOOD", "PGOOD", "out"),
                                ],
                                attributes={
                                    "object_type": "buck_controller",
                                    "library": "power.lib",
                                    "reuse": True,
                                    "preferred_vendor": "tbd",
                                },
                            ),
                            Block(
                                id="OBJ_Feedback_Divider_Reusable_1",
                                name="Reusable Feedback Divider Instance",
                                level=4,
                                ports=[
                                    p("VOUT_SENSE", "VOUT Sense", "analog"),
                                    p("FB_OUT", "FB Out", "analog"),
                                ],
                                attributes={
                                    "object_type": "resistor_divider",
                                    "reuse": True,
                                    "tolerance_percent": 0.1,
                                },
                            ),
                        ],
                    )
                ],
            )
        ],
    )

    som = Block(
        id="SoM",
        name="THOR SoM",
        level=1,
        ports=[
            p("VIN_CORE", "VIN Core", "power", voltage="0.8V", constraint_class="PWR_CORE"),
            p("GND", "GND", "ground"),
            p("SAFETY_SPI", "Safety SPI", "bidi", protocol="SPI", constraint_class="SPI"),
        ],
        attributes={"domain": "Compute", "processor_family": "THOR"},
    )

    safety = Block(
        id="SafetyMicro",
        name="Safety Micro",
        level=1,
        ports=[
            p("VIN_3V3", "VIN 3V3", "power", voltage="3.3V"),
            p("GND", "GND", "ground"),
            p("SPI_TO_SOM", "SPI to SoM", "bidi", protocol="SPI"),
        ],
        attributes={"domain": "Safety", "asil_relevance": "high"},
    )

    return Design(
        id="THOR_ECAD_ARCH",
        name="THOR ECAD Architecture with readable draw.io attributes",
        domains=[psu_thor, som, safety],
        attributes={"project": "Liebherr THOR SoM ECAD Design"},
        connections=[
            Connection(
                id="NET_PSU_THOR_CORE_TO_SOM",
                name="PWR_THOR_CORE",
                type="net",
                source="PSU_THOR.VOUT_CORE",
                target="SoM.VIN_CORE",
                attributes={"constraint_class": "PWR_CORE", "voltage": "0.8V", "current_max_A": 80},
            ),
            Connection(
                id="BUS_SOM_TO_SAFETY_SPI",
                name="SAFETY_SPI",
                type="bus",
                source="SoM.SAFETY_SPI",
                target="SafetyMicro.SPI_TO_SOM",
                attributes={"protocol": "SPI", "width": 4, "constraint_class": "SPI"},
            ),
            Connection(
                id="NET_BUCK_FB",
                name="BUCK_FB",
                type="net",
                source="OBJ_Feedback_Divider_Reusable_1.FB_OUT",
                target="OBJ_Buck_Controller_Reusable_1.FB",
                attributes={"constraint_class": "ANALOG_FB"},
            ),
        ],
    )


if __name__ == "__main__":
    design = build_design()
    out_dir = Path(__file__).resolve().parent

    DrawioRenderer(design).render(out_dir / "thor_readable_attributes.drawio")
    (out_dir / "thor_readable_attributes.json").write_text(design.to_json(), encoding="utf-8")

    print("Created thor_readable_attributes.drawio")
    print("Created thor_readable_attributes.json")
