import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from symbol_wizard.models.document import GraphicObjectModel, OriginMode, PinModel, SymbolBodyModel, SymbolDocumentModel, SymbolUnitModel, TextModel


def document_to_dict(document: SymbolDocumentModel) -> dict[str, Any]:
    return asdict(document)


def document_from_dict(data: dict[str, Any]) -> SymbolDocumentModel:
    doc = SymbolDocumentModel(name=data.get("name", "NewSymbol"), grid_inch=data.get("grid_inch", 0.100), origin=data.get("origin", OriginMode.BOTTOM_LEFT.value), units=[])
    for unit_data in data.get("units", []):
        body = SymbolBodyModel(**unit_data.get("body", {}))
        pins = [PinModel(**p) for p in unit_data.get("pins", [])]
        texts = [TextModel(**t) for t in unit_data.get("texts", [])]
        graphics = [GraphicObjectModel(**g) for g in unit_data.get("graphics", [])]
        doc.units.append(SymbolUnitModel(name=unit_data.get("name", "Unit"), body=body, pins=pins, texts=texts, graphics=graphics))
    if not doc.units:
        doc.units.append(SymbolUnitModel())
    return doc


def save_document(path: str | Path, document: SymbolDocumentModel) -> None:
    Path(path).write_text(json.dumps(document_to_dict(document), indent=2), encoding="utf-8")


def load_document(path: str | Path) -> SymbolDocumentModel:
    return document_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
