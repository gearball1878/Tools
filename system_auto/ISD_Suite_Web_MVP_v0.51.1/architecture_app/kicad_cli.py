"""Batch entry point for the integrated KiCad adapter.

Usage: python -m architecture_app.kicad_cli project.json design.zip
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .kicad_connector import KiCadConnector
from .models import ArchitecturePackage


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a KiCad connectivity schematic from SPOT JSON")
    parser.add_argument("spot", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    package = ArchitecturePackage.model_validate(json.loads(args.spot.read_text(encoding="utf-8")))
    adapter = KiCadConnector()
    review = adapter.forward_preview(package)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(adapter.forward_archive(package))
    print(f"{args.output}: {len(package.domains)} Domains, "
          f"{sum(len(d.elements) for d in package.domains)} AEs, "
          f"{len(package.signals)} Links; {len(review.warnings)} Hinweise")


if __name__ == "__main__":
    main()
