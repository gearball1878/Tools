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
from xped_auto.arch_json_writer import ArchJsonWriter, BackAnnotationError
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

    def _xpedition_com_data(self):
        domains = {domain.name: domain for domain in self.model.blocks}
        som_ae = domains["SOM"].children[0]
        eth_ae = domains["ETH"].children[0]
        som_pin = som_ae.ports[0]
        eth_pin = eth_ae.ports[0]
        net_id = self.model.net_references[0].net_id
        return {
            "SOM": [
                "XD-DOMAIN-SOM", domains["SOM"].id,
                {"Host_Block": [
                    "XD-AE-HOST", som_ae.id, "",
                    {"Pins": {"Interface": {
                        som_pin.name: ["XD-PIN-HOST", som_pin.id, {som_pin.name: ["XD-NET-SPI", net_id]}]
                    }}}
                ]},
            ],
            "ETH": [
                "XD-DOMAIN-ETH", domains["ETH"].id,
                {"Peripheral_Block": [
                    "XD-AE-PERIPHERAL", eth_ae.id, "",
                    {"Pins": {"Interface": {
                        eth_pin.name: ["XD-PIN-PERIPHERAL", eth_pin.id, {eth_pin.name: ["XD-NET-SPI-ETH", net_id]}]
                    }}}
                ]},
            ],
        }

    def test_back_annotation_updates_attributes_on_same_spot_objects(self):
        original_ids = {
            "blocks": [block.id for block, _ in self.model.walk_blocks()],
            "ports": [port.id for block, _ in self.model.walk_blocks() for port in block.ports],
            "nets": [reference.net_id for reference in self.model.net_references],
        }
        writer = ArchJsonWriter(self.model)
        report = writer.apply_xpedition_back_annotation(
            self._xpedition_com_data(),
            project=r"C:\\project\\Vehicle.prj",
            timestamp="2026-08-05T12:00:00Z",
        )
        annotated = writer.model
        self.assertEqual({"domains": 2, "architecture_elements": 2, "ports": 2, "nets": 1}, report.annotated)
        self.assertEqual([], report.conflicts)
        self.assertEqual(original_ids["blocks"], [block.id for block, _ in annotated.walk_blocks()])
        self.assertEqual(original_ids["ports"], [port.id for block, _ in annotated.walk_blocks() for port in block.ports])
        self.assertEqual(original_ids["nets"], [reference.net_id for reference in annotated.net_references])
        self.assertEqual("XD-DOMAIN-SOM", annotated.blocks[0].attributes["xpedition"]["uid"])
        self.assertEqual("XD-PIN-HOST", annotated.blocks[0].children[0].ports[0].attributes["xpedition"]["uid"])
        self.assertEqual(
            ["XD-NET-SPI", "XD-NET-SPI-ETH"],
            annotated.net_references[0].attributes["xpedition"]["uids"],
        )
        self.assertEqual("2026-08-05T12:00:00Z", annotated.attributes["xpedition"]["lastBackAnnotationUtc"])

        # Reader consumes the annotations from that same model in the next
        # Forward Annotation; there is no external ID map.
        reader = ArchJsonReader(annotated)
        self.assertEqual("XD-DOMAIN-SOM", reader.get_domains(annotated.name)["SOM"]["xpedition_id"])
        pin = reader.get_pins_of_type_for_ae(annotated.name, "SOM", "Host_Block", "Interface")["SPI_Link_1"]
        self.assertEqual("XD-PIN-HOST", pin["xpedition_id"])

    def test_back_annotation_conflict_is_atomic(self):
        before = self.model.to_dict()
        broken = self._xpedition_com_data()
        broken["SOM"][1] = "UNKNOWN-BLOCK-ID"
        writer = ArchJsonWriter(self.model)
        with self.assertRaises(BackAnnotationError):
            writer.apply_xpedition_back_annotation(broken)
        self.assertEqual(before, writer.model.to_dict())

    def test_schema_rejects_legacy_xpedition_attribute(self):
        broken = self.model.to_dict()
        broken["blocks"][0]["attributes"]["xpedScmId"] = "legacy"
        with self.assertRaises(ArchitectureJSONValidationError):
            JSONValidator().validate_data(broken)

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
