from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from main import create_demo
from sysml2_arch_builder.model import ArchitectureModel
from sysml2_arch_builder.xped_adapter import (
    architecture_to_xped,
    legacy_exchange_to_architecture,
    load_xped_json,
    save_xped_exchange,
    validate_xped_exchange,
)


ROOT = Path(__file__).resolve().parents[1]


class XpedAdapterTest(unittest.TestCase):
    def test_builder_exchange_round_trip_preserves_source_ids_and_nets(self):
        model = create_demo(ROOT / "Interface_Template_File.json")
        original_block_ids = {path: block.id for block, path in model.walk_blocks()}
        original_port_ids = {(path, port.name): port.id for block, path in model.walk_blocks() for port in block.ports}

        exchange, manifest, report = architecture_to_xped(model)
        self.assertEqual([], validate_xped_exchange(exchange))
        self.assertEqual([], report.warnings)
        restored, restored_report = legacy_exchange_to_architecture(exchange, manifest)

        self.assertEqual([], restored_report.warnings)
        self.assertEqual(original_block_ids, {path: block.id for block, path in restored.walk_blocks()})
        self.assertEqual(original_port_ids, {(path, port.name): port.id for block, path in restored.walk_blocks() for port in block.ports})
        self.assertEqual(2, len(restored.net_references))
        self.assertEqual({"SPI_Link_1"}, {ref.name for ref in restored.net_references})
        self.assertTrue(all(ref.attributes["signals"] for ref in restored.net_references))

    def test_file_round_trip_auto_detects_legacy_exchange(self):
        model = create_demo(ROOT / "Interface_Template_File.json")
        with tempfile.TemporaryDirectory() as tmp:
            exchange_path = Path(tmp) / "demo.xped.json"
            exchange, mapping, _ = save_xped_exchange(model, exchange_path)
            restored, _ = load_xped_json(exchange, mapping)
            self.assertEqual(model.name, restored.name)
            self.assertEqual(2, len(restored.blocks))

    def test_compact_xpedition_snapshot_import(self):
        snapshot = {
            "ETH": [
                "DOMAIN-SCM",
                "{11111111-1111-1111-1111-111111111111}",
                {
                    "Switch": [
                        "AE-SCM",
                        "{22222222-2222-2222-2222-222222222222}",
                        "Networking",
                        {
                            "Pins": {
                                "Control": {
                                    "RESETn": [
                                        "PIN-SCM",
                                        "{33333333-3333-3333-3333-333333333333}",
                                        {"RESET_NET": ["NET-SCM", "{44444444-4444-4444-4444-444444444444}"]},
                                    ]
                                }
                            }
                        },
                    ]
                },
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "snapshot.json"
            source.write_text(json.dumps(snapshot), encoding="utf-8")
            model, report = load_xped_json(source, system_name="Vehicle")
        self.assertEqual([], report.warnings)
        self.assertEqual("Vehicle", model.name)
        self.assertEqual("Switch", model.blocks[0].children[0].name)
        self.assertEqual("RESET_NET", model.net_references[0].name)
        self.assertEqual("PIN-SCM", model.blocks[0].children[0].ports[0].attributes["xpedScmId"])

    def test_model_attributes_are_backward_compatible(self):
        model = ArchitectureModel.from_dict({"name": "Old", "blocks": [], "connections": [], "net_references": []})
        self.assertEqual({}, model.attributes)


if __name__ == "__main__":
    unittest.main()

