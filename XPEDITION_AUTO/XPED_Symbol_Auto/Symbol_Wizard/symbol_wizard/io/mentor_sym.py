from __future__ import annotations

"""Native Mentor/Xpedition/DxDesigner ASCII symbol import/export.

Supported rules used by the Symbol Wizard Mentor bridge:
- Split symbols are imported/exported as ZIP archives; each file in the ZIP is one split part/unit.
- Single symbols are imported/exported as one `.sym`/`.1` style ASCII file.
- Coordinates stay in Mentor-native placement coordinates. The Wizard origin for Mentor symbols is
  the real Mentor origin `(0,0)` at the left/bottom pin-anchor area; no auto-centering is required.
- Mentor `.sym/.1` files do not normally carry RGB colors. The importer therefore keeps object colors
  black and uses `PINTYPE` semantically. UI palettes may color pins by type, but the native export does
  not invent Mentor color records.
- `K` IDs are generated deterministically from symbol/unit names using CRC32.
- `|R` is generated from the current timestamp in Mentor's common `H:MM:SS_M-D-YY` style.
"""

import json
import re
import zipfile
import zlib
from dataclasses import asdict
from datetime import datetime
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
)
from symbol_wizard.io.json_store import _symbol

MAGIC = "# SYMBOL_WIZARD_MENTOR_SYM_V1"
MENTOR_NATIVE_TEMPLATE = "mentor_native_origin"


def _safe_name(path: str | Path) -> str:
    return Path(path).stem or "ImportedSymbol"


def _clean_symbol_filename(name: str) -> str:
    name = (name or "symbol").strip().replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9_.\-]+", "_", name)
    return name or "symbol"


def _mentor_key_id(symbol_name: str, unit_name: str = "") -> int:
    """Stable Mentor K-ID: deterministic 31-bit CRC32, never zero."""
    seed = f"{symbol_name}|{unit_name}".encode("utf-8", "ignore")
    value = zlib.crc32(seed) & 0x7FFFFFFF
    return value or 1


def _mentor_revision_timestamp(dt: datetime | None = None) -> str:
    """Return Mentor-style timestamp, e.g. `14:07:03_5-14-26`."""
    # Do not use named time zones here: Mentor only stores a plain local timestamp
    # like `0:00:00_4-16-19`, and some deployments do not ship the IANA tz DB.
    dt = dt or datetime.now()
    return f"{dt.hour}:{dt.minute:02d}:{dt.second:02d}_{dt.month}-{dt.day}-{dt.year % 100:02d}"


def _json_payload(line: str) -> dict[str, Any] | None:
    try:
        _tag, payload = line.split("\t", 1)
        return json.loads(payload)
    except Exception:
        return None


def export_mentor_sym(path: str | Path, symbol: SymbolModel) -> None:
    """Export Mentor symbol.

    Split symbols are always written as a ZIP archive, with each unit as one native
    Xpedition/DxDesigner ASCII part file. Single symbols are written as one native file.
    """
    p = Path(path)
    is_split = bool(symbol.is_split or symbol.kind == SymbolKind.SPLIT.value or len(symbol.units) > 1)
    if is_split:
        if p.suffix.lower() != ".zip":
            p = p.with_suffix(".zip")
        with zipfile.ZipFile(p, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for idx, unit in enumerate(symbol.units):
                unit_name = unit.name or f"{symbol.name}_{idx + 1}"
                filename = _clean_symbol_filename(unit_name)
                if not filename.lower().endswith((".1", ".sym")):
                    filename += ".1"
                zf.writestr(filename, _export_native_unit(symbol, unit, idx, len(symbol.units)))
    else:
        p.write_text(_export_native_unit(symbol, symbol.units[0], 0, 1), encoding="utf-8")


def import_mentor_sym(path: str | Path) -> SymbolModel:
    """Import single Mentor file or split ZIP."""
    p = Path(path)
    if p.suffix.lower() == ".zip":
        return _import_mentor_zip(p)
    text = p.read_text(encoding="utf-8", errors="ignore")
    stripped = text.lstrip()
    if stripped.startswith("{"):
        s = _symbol(json.loads(stripped))
        s.template_name = MENTOR_NATIVE_TEMPLATE
        return s
    if MAGIC in text[:500]:
        s = _import_roundtrip(text, p)
        s.template_name = MENTOR_NATIVE_TEMPLATE
        return s
    s = _import_native_single(text, p)
    s.template_name = MENTOR_NATIVE_TEMPLATE
    return s


def _import_mentor_zip(path: Path) -> SymbolModel:
    units: list[SymbolUnitModel] = []
    symbol_name = path.stem
    with zipfile.ZipFile(path, "r") as zf:
        names = [n for n in zf.namelist() if not n.endswith("/") and not Path(n).name.startswith(".")]
        names.sort(key=lambda n: _natural_sort_key(Path(n).name))
        for n in names:
            try:
                text = zf.read(n).decode("utf-8", errors="ignore")
            except Exception:
                continue
            part_symbol = _import_native_single(text, Path(n))
            if part_symbol.name and symbol_name == path.stem:
                # First useful unit name usually carries the device prefix.
                symbol_name = _common_device_name(symbol_name, part_symbol.name)
            units.extend(part_symbol.units)
    if not units:
        raise ValueError("ZIP enthält keine lesbaren Mentor Symbolparts.")
    s = SymbolModel(name=symbol_name, kind=SymbolKind.SPLIT.value, is_split=True, origin="bottom_left", units=units)
    s.grid_inch = 0.100
    s.template_name = MENTOR_NATIVE_TEMPLATE
    return s


def _natural_sort_key(name: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def _common_device_name(fallback: str, unit_name: str) -> str:
    # xczu3egsfvc784b_24.1 -> XCZU3EGSFVC784 when possible, otherwise fallback.
    stem = Path(unit_name).stem
    m = re.match(r"(.+?)(?:b)?_[A-Za-z0-9]+$", stem, re.I)
    return (m.group(1).upper() if m else fallback) or fallback


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
    d["origin"] = "bottom_left"
    return _symbol(d)


def _to_grid(v: float, z: float) -> float:
    return float(v) / float(z or 10.0)


def _to_mentor(v: float, z: float) -> int:
    return int(round(float(v) * float(z or 10.0)))


def _align_from_code(code: str | int | None) -> str:
    c = str(code or "")
    if c in ("5", "6", "7"):
        return "center"
    if c in ("8", "9"):
        return "right"
    return "left"


def _pin_type_to_wizard(v: str) -> str:
    t = (v or "BIDI").strip().upper()
    if t in ("BI", "BIDIR", "BIDIRECTIONAL"):
        return "BIDI"
    return t or "BIDI"


def _pin_type_to_mentor(v: str) -> str:
    t = (v or "BIDI").strip().upper()
    if t == "BIDI":
        return "BI"
    return t


def _import_native_single(text: str, path: Path) -> SymbolModel:
    unit_name = _safe_name(path)
    symbol_name = unit_name
    z = 10.0
    d_top = 0.0
    body = SymbolBodyModel()
    body.attributes.clear()
    body.visible_attributes.clear()
    pins_tmp: dict[int, dict[str, Any]] = {}
    texts: list[TextModel] = []
    graphics: list[GraphicModel] = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line == "E":
            continue
        parts = line.split()
        tag = parts[0]
        try:
            if tag == "K" and len(parts) >= 3:
                unit_name = parts[2]
                symbol_name = _common_device_name(symbol_name, unit_name)
            elif tag == "Z" and len(parts) >= 2:
                z = float(parts[1]) or 10.0
            elif tag == "D" and len(parts) >= 5:
                d_top = max(float(parts[2]), float(parts[4]), d_top)
            elif tag == "U" and len(parts) >= 8:
                prop = " ".join(parts[7:])
                if "=" in prop:
                    name, value = prop.split("=", 1)
                    mapped = {"REFDES": "RefDes", "DEVICE": "Value", "PART_NAME": "Part Name", "CASE": "Package"}.get(name, name)
                    body.attributes[mapped] = value
                    body.visible_attributes[mapped] = parts[6] != "0"
                    if name == "REFDES":
                        body.attribute_texts["RefDes"] = TextModel(
                            text=value or "?", x=_to_grid(float(parts[1]), z), y=_to_grid(float(parts[2]), z),
                            font_size_grid=_to_grid(float(parts[3]), z), h_align=_align_from_code(parts[5]), v_align="upper"
                        )
            elif tag == "b" and len(parts) >= 5:
                x1, y1, x2, y2 = map(float, parts[1:5])
                left, right = min(x1, x2), max(x1, x2)
                bottom, top = min(y1, y2), max(y1, y2)
                body.x = _to_grid(left, z)
                body.y = _to_grid(top, z)
                body.width = _to_grid(right - left, z)
                body.height = _to_grid(top - bottom, z)
            elif tag == "T" and len(parts) >= 7:
                text_value = " ".join(parts[6:])
                texts.append(TextModel(
                    text=text_value,
                    x=_to_grid(float(parts[1]), z),
                    y=_to_grid(float(parts[2]), z),
                    font_size_grid=_to_grid(float(parts[3]), z),
                    h_align=_align_from_code(parts[5]),
                    v_align="upper",
                ))
            elif tag == "P" and len(parts) >= 9:
                pid = int(parts[1])
                x1, y1, x2, y2 = map(float, parts[2:6])
                side_code = parts[7]
                side = "right" if side_code == "3" or x1 > x2 else "left"
                edge_x = x2 if side == "left" else x2
                length = abs(x2 - x1) or abs(y2 - y1) or z * 3
                pins_tmp[pid] = {
                    "number": str(pid), "name": f"PIN{pid}", "function": f"PIN{pid}",
                    "pin_type": "BIDI", "side": side,
                    "x": _to_grid(edge_x, z), "y": _to_grid(y1, z), "length": _to_grid(length, z),
                }
            elif tag == "L" and len(parts) >= 10 and pins_tmp:
                # Pin label follows the most recently declared pin in native files.
                pid = max(pins_tmp)
                label = " ".join(parts[9:])
                pins_tmp[pid]["name"] = label
                pins_tmp[pid]["function"] = label
            elif tag == "A" and len(parts) >= 8 and pins_tmp:
                attr = " ".join(parts[7:])
                pid = max(pins_tmp)
                if attr.startswith("#="):
                    pins_tmp[pid]["number"] = attr[2:]
                elif attr.upper().startswith("PINTYPE="):
                    pins_tmp[pid]["pin_type"] = _pin_type_to_wizard(attr.split("=", 1)[1])
        except Exception:
            continue

    if not body.attributes:
        body.attributes.update({"RefDes": "U?", "Value": symbol_name})
        body.visible_attributes.update({"RefDes": True, "Value": True})
    else:
        body.attributes.setdefault("RefDes", "U?")
        body.attributes.setdefault("Value", symbol_name.upper())
        body.visible_attributes.setdefault("RefDes", True)
        body.visible_attributes.setdefault("Value", True)

    pins = [PinModel(**pins_tmp[k]) for k in sorted(pins_tmp)]
    unit = SymbolUnitModel(name=unit_name, body=body, pins=pins, texts=texts, graphics=graphics)
    symbol = SymbolModel(name=symbol_name, kind=SymbolKind.SINGLE.value, is_split=False, grid_inch=0.100, origin="bottom_left", units=[unit])
    symbol.template_name = MENTOR_NATIVE_TEMPLATE
    return symbol


def _unit_extents(unit: SymbolUnitModel, z: float = 10.0) -> tuple[int, int, int, int]:
    xs: list[int] = []
    ys: list[int] = []
    b = unit.body
    xs += [_to_mentor(b.x, z), _to_mentor(b.x + b.width, z)]
    ys += [_to_mentor(b.y, z), _to_mentor(b.y - b.height, z)]
    for p in unit.pins:
        edge = _to_mentor(p.x, z)
        length = _to_mentor(p.length, z)
        if p.side == "right":
            xs += [edge, edge + length]
        else:
            xs += [edge - length, edge]
        ys.append(_to_mentor(p.y, z))
    for t in unit.texts:
        xs.append(_to_mentor(t.x, z)); ys.append(_to_mentor(t.y, z))
    for t in getattr(unit.body, "attribute_texts", {}).values():
        xs.append(_to_mentor(t.x, z)); ys.append(_to_mentor(t.y, z))
    for g in unit.graphics:
        xs += [_to_mentor(g.x, z), _to_mentor(g.x + g.w, z)]
        ys += [_to_mentor(g.y, z), _to_mentor(g.y - g.h, z)]
    if not xs:
        return 0, 100, 100, 0
    left = min(xs)
    right = max(xs)
    bottom = min(ys)
    top = max(ys)
    return left, top, right, bottom


def _mentor_text_align(h_align: str) -> int:
    return {"center": 5, "right": 8}.get((h_align or "left").lower(), 2)


def _export_native_unit(symbol: SymbolModel, unit: SymbolUnitModel, index: int, total: int) -> str:
    z = 10.0
    unit_name = unit.name or (symbol.name if total == 1 else f"{symbol.name}_{index + 1}")
    key_id = _mentor_key_id(symbol.name, unit_name)
    left, top, right, bottom = _unit_extents(unit, z)
    # Keep the real Mentor origin inside the drawing extent.
    left = min(left, 0)
    bottom = min(bottom, 0)
    # Add a small native text margin similar to Mentor generators, but keep origin at (0,0).
    top = max(top, _to_mentor(unit.body.y, z) + 18)
    lines: list[str] = [
        "V 53",
        f"K {key_id} {unit_name}",
        f"|R {_mentor_revision_timestamp()}",
        "F Case",
        f"D {left} {top} {right} {bottom}",
        "Y 1",
        "Z 10",
        f"i {len(unit.pins) + 1}",
    ]

    attrs = dict(getattr(unit.body, "attributes", {}) or {})
    refdes = attrs.get("RefDes") or attrs.get("REFDES") or "U?"
    value = attrs.get("Value") or attrs.get("DEVICE") or symbol.name
    package = attrs.get("Package") or attrs.get("CASE") or "BAUFORM"
    attr_texts = getattr(unit.body, "attribute_texts", {}) or {}
    ref_t = attr_texts.get("RefDes")
    if ref_t:
        rx, ry, rs = _to_mentor(ref_t.x, z), _to_mentor(ref_t.y, z), max(1, _to_mentor(ref_t.font_size_grid, z))
    else:
        rx = _to_mentor(unit.body.x + unit.body.width / 2, z)
        ry = _to_mentor(unit.body.y + 1.0, z)
        rs = 16
    lines.append(f"U {rx} {ry} {rs} 0 5 3 REFDES={refdes if str(refdes).startswith('U') else refdes}")
    # Corporate/default attributes compatible with the shown Mentor examples.
    default_u = [
        ("CASE", package, 30, 0, 10, 0, 3, 3),
        ("CLASS", attrs.get("CLASS", ""), 80, 20, 10, 0, 3, 3),
        ("PART_NAME", attrs.get("Part Name", attrs.get("PART_NAME", "TNR_LEG")), 30, 20, 10, 0, 3, 3),
        ("@XYCOORD", attrs.get("@XYCOORD", ""), 30, 20, 25400, 0, 3, 0),
        ("LEON_Link", attrs.get("LEON_Link", ""), 30, 20, 25400, 0, 3, 0),
        ("DEVICE", value, 30, 20, 10, 0, 3, 0),
        ("TYPE", attrs.get("TYPE", "TYPE"), 30, 10, 10, 0, 3, 3),
        ("FORWARD_PCB", attrs.get("FORWARD_PCB", "1"), 0, 0, 10, 0, 1, 0),
    ]
    for name, val, x, y, size, rot, align, vis in default_u:
        lines.append(f"U {x} {y} {size} {rot} {align} {vis} {name}={val}")

    b = unit.body
    bx1 = _to_mentor(b.x, z); by_top = _to_mentor(b.y, z)
    bx2 = _to_mentor(b.x + b.width, z); by_bottom = _to_mentor(b.y - b.height, z)
    lines.append(f"b {bx1} {by_bottom} {bx2} {by_top}")

    for t in unit.texts:
        tx = _to_mentor(t.x, z); ty = _to_mentor(t.y, z); ts = max(1, _to_mentor(t.font_size_grid, z))
        align = _mentor_text_align(t.h_align)
        lines.append(f"T {tx} {ty} {ts} 0 {align} {t.text}")

    for idx, pin in enumerate(unit.pins, start=1):
        edge = _to_mentor(pin.x, z)
        y = _to_mentor(pin.y, z)
        length = max(1, _to_mentor(pin.length, z))
        if pin.side == "right":
            x1, x2, side_code = edge + length, edge, 3
            lx, lalign = edge - 5, 8
            ax_num, anum_align = edge + 10, 3
            ax_type, atype_align = edge + length, 2
        else:
            x1, x2, side_code = edge - length, edge, 2
            lx, lalign = edge + 5, 2
            ax_num, anum_align = edge - 10, 9
            ax_type, atype_align = edge - length, 8
        lines.append(f"P {idx} {x1} {y} {x2} {y} 0 {side_code} 0")
        lines.append(f"L {lx} {y} 10 0 {lalign} 0 1 0 {pin.name}")
        lines.append(f"A {ax_num} {y} 8 0 {anum_align} 3 #={pin.number}")
        lines.append(f"A {ax_type} {y} 10 0 {atype_align} 0 PINTYPE={_pin_type_to_mentor(pin.pin_type)}")

    lines.append("E")
    return "\n".join(lines) + "\n"


# Backward-compatible helper parser for non-native key=value records is intentionally removed from
# the default import path. Native Mentor ASCII is now the authoritative interchange format.
