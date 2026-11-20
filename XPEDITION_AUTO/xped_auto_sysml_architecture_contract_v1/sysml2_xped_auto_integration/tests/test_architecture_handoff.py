from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from main import create_demo
from sysml2_arch_builder.model import ARCHITECTURE_FORMAT, ArchitectureModel
from xped_auto.arch_json_reader import ArchJsonReader
from xped_auto.arch_json_writer import ArchJsonWriter
from xped_auto.json_validator import ArchitectureJSONValidationError, JSONValidator


ROOT = Path(__file__).resolve().parents[1]


class ArchitectureHandoffTest(unittest.TestCase):
    def setUp(self):
        self.model = create_demo(ROOT / "Interface_Template_File.json")

    def test_writer_emits_versioned_schema_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = ArchJsonWriter(self.model).write_architecture_json(Path(tmp) / "architecture.json")
            data = JSONValidator().load_and_validate(target)
        self.assertEqual(ARCHITECTURE_FORMAT, data["format"])
        self.assertEqual(self.model.name, data["name"])

    def test_reader_exposes_sysml_objects_to_auto_schem(self):
        reader = ArchJsonReader(self.model)
        self.assertEqual(ARCHITECTURE_FORMAT, reader.source_format)
        self.assertEqual(["SOM", "ETH"], reader.get_domain_names(self.model.name))
        self.assertEqual(["Host_Block"], reader.get_ae_names_for_domain(self.model.name, "SOM"))
        self.assertEqual(["SPI_Link_1"], reader.get_pin_names_for_ae(self.model.name, "SOM", "Host_Block"))
        self.assertEqual(["SPI_Link_1"], list(reader.get_pins_of_type_for_ae(self.model.name, "SOM", "Host_Block", "Interface")))
        self.assertEqual(["SPI_Link_1"], reader.get_net_names_for_pin_of_ae(self.model.name, "SOM", "Host_Block", "SPI_Link_1"))
        net = reader.get_nets_for_pin_of_ae(self.model.name, "SOM", "Host_Block", "SPI_Link_1")["SPI_Link_1"]
        self.assertEqual("Bus", net[2])
        self.assertTrue(net[1].startswith("NET-"))

    def test_reader_rejects_old_list_exchange_format(self):
        with self.assertRaises(ArchitectureJSONValidationError):
            ArchJsonReader([{"System Name": "Legacy"}])  # type: ignore[arg-type]

    def test_schema_rejects_missing_handoff_fields(self):
        broken = self.model.to_dict()
        del broken["blocks"][0]["id"]
        with self.assertRaises(ArchitectureJSONValidationError) as caught:
            JSONValidator().validate_data(broken, source="test")
        self.assertIn("$.blocks[0]", str(caught.exception))

    def test_model_loader_rejects_unversioned_json(self):
        with self.assertRaises(ValueError):
            ArchitectureModel.from_dict({"name": "Old", "blocks": []})

    def test_xpedition_snapshot_returns_native_architecture(self):
        snapshot = {
            "ETH": [
                "DOMAIN-SCM",
                "DOMAIN-ARCH",
                {
                    "Switch": [
                        "AE-SCM",
                        "AE-ARCH",
                        "Networking",
                        {
                            "Pins": {
                                "Control": {
                                    "RESETn": [
                                        "PIN-SCM",
                                        "PIN-ARCH",
                                        {"RESET_NET": ["NET-SCM", "NET-ARCH"]},
                                    ]
                                }
                            }
                        },
                    ]
                },
            ]
        }
        writer = ArchJsonWriter.from_xpedition_snapshot(snapshot, architecture_name="Vehicle")
        reader = ArchJsonReader(writer.model)
        self.assertEqual(["ETH"], reader.get_domain_names("Vehicle"))
        self.assertEqual("AE-ARCH", reader.get_arch_id_for_ae("Vehicle", "ETH", "Switch"))
        self.assertEqual(["RESET_NET"], reader.get_net_names_for_pin_of_ae("Vehicle", "ETH", "Switch", "RESETn"))

    def test_runner_dry_run_validates_without_com(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            architecture = ArchJsonWriter(self.model).write_architecture_json(root / "architecture.json")
            project = root / "Project.prj"
            project.write_text("test", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "xped_auto.runner",
                    "--architecture-json",
                    str(architecture),
                    "--project",
                    str(project),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
        summary = json.loads(completed.stdout.split("Dry-run only.", 1)[0])
        self.assertEqual(2, summary["domains"])
        self.assertEqual(2, summary["architecture_elements"])


if __name__ == "__main__":
    unittest.main()
