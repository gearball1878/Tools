from __future__ import annotations

"""Mentor/Xpedition symbol translation layer.

This module provides a small, deliberately isolated bridge between Mentor
``.sym`` files and the Symbol Wizard internal JSON/data model.  The exporter
writes a deterministic ASCII ``.sym`` representation that keeps all internal
model information round-trippable.  The importer can read this round-trip
format and also contains a tolerant best-effort parser for simple Mentor-like
ASCII symbol files containing PIN/ATTR/TEXT/GRAPHIC records.

The goal is to keep all Mentor-specific parsing/writing out of the UI code.
When a stricter customer-specific .sym dialect is required, extend this module
only; the rest of the tool should continue to work with SymbolModel objects.
"""

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from symbol_wizard.models.document import (
    FontModel,
    GraphicModel,
    PinModel,
    StyleModel,
    SymbolBodyModel,
    SymbolKind,
    SymbolModel,
    SymbolUnitModel,
    TextModel,
    to_dict,
)
from symbol_wizard.io.json_store import _symbol

MAGIC = "# SYMBOL_WIZARD_MENTOR_SYM_V1"


def _safe_name(path: str | Path) -> str:
    return Path(path).stem or "ImportedSymbol"


def _json_payload(line: str) -> dict[str, Any] | None:
    try:
        _tag, payload = line.split("\t", 1)
        return json.loads(payload)
    except Exception:
        return None


def export_mentor_sym(path: str | Path, symbol: SymbolModel) -> None:
    """Export a SymbolModel to a Mentor .sym bridge file.

    The file is line based and intentionally easy to diff.  Each record after
    the tag is JSON, which avoids lossy quoting issues for pin names, attribute
    values and text strings.
    """
    p = Path(path)
    lines: list[str] = [MAGIC]
    header = {
        "name": symbol.name,
        "kind": symbol.kind,
        "is_split": bool(symbol.is_split or symbol.kind == SymbolKind.SPLIT.value),
        "grid_inch": symbol.grid_inch,
        "sheet_format": symbol.sheet_format,
        "origin": symbol.origin,
        "template_name": symbol.template_name,
    }
    lines.append("SYMBOL\t" + json.dumps(header, ensure_ascii=False, separators=(",", ":")))
    for unit in symbol.units:
        lines.append("UNIT\t" + json.dumps({"name": unit.name}, ensure_ascii=False, separators=(",", ":")))
        lines.append("BODY\t" + json.dumps(asdict(unit.body), ensure_ascii=False, separators=(",", ":")))
        for pin in unit.pins:
            lines.append("PIN\t" + json.dumps(asdict(pin), ensure_ascii=False, separators=(",", ":")))
        for text in unit.texts:
            lines.append("TEXT\t" + json.dumps(asdict(text), ensure_ascii=False, separators=(",", ":")))
        for graphic in unit.graphics:
            lines.append("GRAPHIC\t" + json.dumps(asdict(graphic), ensure_ascii=False, separators=(",", ":")))
        lines.append("ENDUNIT")
    lines.append("ENDSYMBOL")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def import_mentor_sym(path: str | Path) -> SymbolModel:
    """Import a Mentor .sym file as a SymbolModel.

    Supported input:
    1. Native round-trip files written by export_mentor_sym().
    2. JSON files containing the normal Symbol Wizard symbol model.
    3. Best-effort Mentor-like ASCII with PIN/ATTR/TEXT/BODY/LINE/RECT records.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="ignore")
    stripped = text.lstrip()
    if stripped.startswith("{"):
        return _symbol(json.loads(stripped))
    if MAGIC in text[:500]:
        return _import_roundtrip(text, p)
    return _import_best_effort_ascii(text, p)


def _import_roundtrip(text: str, path: Path) -> SymbolModel:
    header: dict[str, Any] = {"name": _safe_name(path)}
    units: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("SYMBOL\t"):
            header.update(_json_payload(line) or {})
        elif line.startswith("UNIT\t"):
            if current is not None:
                units.append(current)
            payload = _json_payload(line) or {}
            current = {"name": payload.get("name", "Unit"), "pins": [], "texts": [], "graphics": []}
        elif line.startswith("BODY\t") and current is not None:
            current["body"] = _json_payload(line) or {}
        elif line.startswith("PIN\t") and current is not None:
            current.setdefault("pins", []).append(_json_payload(line) or {})
        elif line.startswith("TEXT\t") and current is not None:
            current.setdefault("texts", []).append(_json_payload(line) or {})
        elif line.startswith("GRAPHIC\t") and current is not None:
            current.setdefault("graphics", []).append(_json_payload(line) or {})
        elif line == "ENDUNIT" and current is not None:
            units.append(current)
            current = None
    if current is not None:
        units.append(current)
    d = dict(header)
    d["units"] = units or [{"name": "Unit A"}]
    if not d.get("kind"):
        d["kind"] = SymbolKind.SPLIT.value if len(d["units"]) > 1 else SymbolKind.SINGLE.value
    d["is_split"] = d.get("kind") == SymbolKind.SPLIT.value or bool(d.get("is_split"))
    return _symbol(d)


def _parse_key_values(line: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in re.findall(r"([A-Za-z_][A-Za-z0-9_\-]*)\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s,;]+)", line):
        out[key.lower()] = value.strip().strip('"\'')
    return out


def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _bool(v: Any, default: bool = True) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() not in ("0", "false", "no", "off", "hidden")


def _color_from_kv(kv: dict[str, str], default=(0, 0, 0)):
    if "color" in kv:
        parts = re.split(r"[,;/]", kv["color"])
        if len(parts) >= 3:
            try:
                return tuple(max(0, min(255, int(float(x)))) for x in parts[:3])
            except Exception:
                pass
    if all(k in kv for k in ("r", "g", "b")):
        try:
            return (int(float(kv["r"])), int(float(kv["g"])), int(float(kv["b"])))
        except Exception:
            pass
    return default


def _import_best_effort_ascii(text: str, path: Path) -> SymbolModel:
    symbol = SymbolModel(name=_safe_name(path), kind=SymbolKind.SINGLE.value, is_split=False)
    unit = symbol.units[0]
    unit.name = "Unit A"
    # Start with an empty imported body but keep safe defaults.
    unit.body.attributes.clear()
    unit.body.visible_attributes.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(('#', '//', ';')):
            continue
        upper = line.upper()
        kv = _parse_key_values(line)

        if upper.startswith(("SYMBOL", "NAME")) and "name" in kv:
            symbol.name = kv["name"] or symbol.name
            continue

        if upper.startswith(("UNIT", "PART")):
            if "name" in kv:
                unit.name = kv["name"]
            continue

        if upper.startswith("BODY"):
            b = unit.body
            b.x = _float(kv.get("x", kv.get("left")), b.x)
            b.y = _float(kv.get("y", kv.get("top")), b.y)
            b.width = _float(kv.get("width", kv.get("w")), b.width)
            b.height = _float(kv.get("height", kv.get("h")), b.height)
            b.color = _color_from_kv(kv, b.color)
            b.line_width = _float(kv.get("line_width", kv.get("width_grid")), b.line_width)
            b.line_style = kv.get("line_style", kv.get("style", b.line_style))
            continue

        if upper.startswith(("ATTR", "ATTRIBUTE", "PROPERTY")):
            name = kv.get("name") or kv.get("key") or kv.get("attr")
            value = kv.get("value") or kv.get("val") or ""
            if not name:
                m = re.match(r"(?:ATTR|ATTRIBUTE|PROPERTY)\s+([^\s=]+)\s*(?:=|:)\s*(.*)$", line, re.I)
                if m:
                    name, value = m.group(1), m.group(2).strip().strip('"')
            if name:
                unit.body.attributes[str(name)] = str(value)
                unit.body.visible_attributes[str(name)] = _bool(kv.get("visible"), True)
            continue

        if upper.startswith("PIN"):
            # Supports either key=value records or simple positional: PIN number name side x y length type
            if kv:
                number = kv.get("number", kv.get("num", kv.get("pin", "")))
                name = kv.get("name", kv.get("signal", number or "PIN"))
                side = kv.get("side", "left").lower()
                if side not in ("left", "right"):
                    side = "right" if side.startswith("r") else "left"
                pin = PinModel(
                    number=str(number or len(unit.pins) + 1),
                    name=str(name or "PIN"),
                    function=str(kv.get("function", kv.get("func", ""))),
                    pin_type=str(kv.get("type", kv.get("pin_type", "BIDI"))).upper(),
                    side=side,
                    x=_float(kv.get("x"), 0.0),
                    y=_float(kv.get("y"), 0.0),
                    length=_float(kv.get("length", kv.get("len")), 3.0),
                    inverted=_bool(kv.get("inverted"), False),
                    color=_color_from_kv(kv, (0, 0, 0)),
                    visible_number=_bool(kv.get("visible_number"), True),
                    visible_name=_bool(kv.get("visible_name"), True),
                    visible_function=_bool(kv.get("visible_function"), False),
                )
                unit.pins.append(pin)
            else:
                parts = line.split()
                if len(parts) >= 3:
                    unit.pins.append(PinModel(number=parts[1], name=parts[2], side=(parts[3].lower() if len(parts) > 3 and parts[3].lower() in ("left", "right") else "left")))
            continue

        if upper.startswith("TEXT"):
            txt = kv.get("text") or kv.get("value")
            if txt is None:
                m = re.match(r"TEXT\s+(.+)$", line, re.I)
                txt = m.group(1).strip().strip('"') if m else "Text"
            unit.texts.append(TextModel(
                text=str(txt),
                x=_float(kv.get("x"), 0.0),
                y=_float(kv.get("y"), 0.0),
                font_family=kv.get("font", kv.get("font_family", "Arial")),
                font_size_grid=_float(kv.get("size", kv.get("font_size_grid")), 0.9),
                color=_color_from_kv(kv, (0, 0, 0)),
                h_align=kv.get("h_align", kv.get("align", "left")),
                v_align=kv.get("v_align", "upper"),
            ))
            continue

        if upper.startswith(("LINE", "RECT", "ELLIPSE", "GRAPHIC")):
            shape = "line"
            if upper.startswith("RECT"):
                shape = "rect"
            elif upper.startswith("ELLIPSE"):
                shape = "ellipse"
            elif "shape" in kv:
                shape = kv["shape"].lower()
            unit.graphics.append(GraphicModel(
                shape=shape,
                x=_float(kv.get("x", kv.get("x1")), 0.0),
                y=_float(kv.get("y", kv.get("y1")), 0.0),
                w=_float(kv.get("w", kv.get("width", kv.get("x2"))), 2.0),
                h=_float(kv.get("h", kv.get("height", kv.get("y2"))), 2.0),
                curve_radius=_float(kv.get("curve", kv.get("curve_radius")), 0.0),
                style=StyleModel(stroke=_color_from_kv(kv, (0, 0, 0))),
            ))
            continue

    if not unit.body.attributes:
        unit.body.attributes.update({"RefDes": "?", "Value": ""})
        unit.body.visible_attributes.update({"RefDes": True, "Value": False})
    return symbol
