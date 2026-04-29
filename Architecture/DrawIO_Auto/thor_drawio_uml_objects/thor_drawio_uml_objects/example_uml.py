from pathlib import Path
from model import Design, Block, Port, Connection
from drawio_uml_renderer import DrawioUmlRenderer


def p(id, name, type, **attrs):
    return Port(id=id, name=name, type=type, attributes=attrs)


def build_design() -> Design:
    psu_thor = Block(
        id="PSU_THOR",
        name="PSU_THOR",
        level=1,
        stereotype="Domain",
        ports=[
            p("VIN_24V", "VIN_24V", "power", voltage="24V"),
            p("GND", "GND", "ground"),
            p("VOUT_CORE", "VOUT_CORE", "power", voltage="0.8V", current_max_A=80),
        ],
        attributes={"domain": "Power", "owner": "PowerDesign", "thermal_budget_W": 25},
        children=[
            Block(
                id="PSU_THOR_Core_Voltage_1",
                name="PSU_THOR_Core_Voltage_1",
                level=2,
                stereotype="ArchitectureElement",
                ports=[
                    p("VIN", "VIN", "power"),
                    p("GND", "GND", "ground"),
                    p("VOUT", "VOUT", "power"),
                ],
                attributes={"rail": "VDD_CPU", "voltage": "0.8V", "current_max_A": 80},
                children=[
                    Block(
                        id="CFG_PSU_THOR_Core_Voltage_1",
                        name="CFG_PSU_THOR_Core_Voltage_1",
                        level=3,
                        stereotype="Configuration",
                        ports=[
                            p("FB", "FB", "analog"),
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

    som = Block(
        id="SoM",
        name="SoM",
        level=1,
        stereotype="Domain",
        ports=[
            p("VIN_CORE", "VIN_CORE", "power", voltage="0.8V"),
            p("GND", "GND", "ground"),
            p("SAFETY_SPI", "SAFETY_SPI", "bidi", protocol="SPI"),
        ],
        attributes={"domain": "Compute", "processor_family": "THOR"},
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
        ],
        attributes={"domain": "Safety", "asil_relevance": "high"},
    )

    return Design(
        id="THOR_UML_ARCH",
        name="THOR UML Architecture",
        domains=[psu_thor, som, safety],
        attributes={"project": "Liebherr THOR SoM ECAD Design"},
        connections=[
            Connection(
                id="NET_PSU_THOR_CORE_TO_SOM",
                name="PWR_THOR_CORE",
                type="net",
                source="PSU_THOR.VOUT_CORE",
                target="SoM.VIN_CORE",
                stereotype="Net",
                attributes={"constraint_class": "PWR_CORE", "voltage": "0.8V", "current_max_A": 80},
            ),
            Connection(
                id="BUS_SOM_TO_SAFETY_SPI",
                name="SAFETY_SPI",
                type="bus",
                source="SoM.SAFETY_SPI",
                target="SafetyMicro.SPI_TO_SOM",
                stereotype="Bus",
                attributes={"protocol": "SPI", "width": 4, "constraint_class": "SPI"},
            ),
            Connection(
                id="NET_BUCK_FB",
                name="BUCK_FB",
                type="net",
                source="OBJ_Feedback_Divider_Reusable_1.FB_OUT",
                target="OBJ_Buck_Controller_Reusable_1.FB",
                stereotype="Net",
                attributes={"constraint_class": "ANALOG_FB"},
            ),
        ],
    )


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent
    design = build_design()

    DrawioUmlRenderer(design).render(out_dir / "thor_uml_objects.drawio")
    (out_dir / "thor_uml_objects.json").write_text(design.to_json(), encoding="utf-8")

    print("Created thor_uml_objects.drawio")
    print("Created thor_uml_objects.json")
