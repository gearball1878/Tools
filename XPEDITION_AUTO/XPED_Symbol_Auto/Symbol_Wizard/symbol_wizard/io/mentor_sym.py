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


MENTOR_PIN_PALETTE = {
    "IN": (0, 80, 220),
    "OUT": (220, 0, 0),
    "BIDI": (160, 0, 180),
    "BI": (160, 0, 180),
    "POWER": (230, 120, 0),
    "GROUND": (0, 150, 0),
    "ANALOG": (0, 150, 170),
    "PASSIVE": (0, 0, 0),
}

def _pin_color_for_type(pin_type: str) -> tuple[int, int, int]:
    return MENTOR_PIN_PALETTE.get((pin_type or "").strip().upper(), (0, 0, 0))


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


def _numeric_tokens_for_grid_detection(text: str) -> list[int]:
    vals: list[int] = []
    coord_tags = {"D", "U", "b", "T", "P", "L", "A", "l", "c", "a"}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("|"):
            # TVRNT/variant rows are not part of the 0° master geometry.
            continue
        parts = line.split()
        if not parts or parts[0] not in coord_tags:
            continue
        # Coordinates and sizes in Mentor ASCII are integer-like fields before
        # free text/property payload. Keeping all numeric fields is sufficient
        # for scale detection because both coordinate systems use characteristic
        # multiples (10 vs 254000/127000).
        for tok in parts[1:8]:
            try:
                v = int(float(tok))
            except Exception:
                continue
            if abs(v) > 0:
                vals.append(abs(v))
    return vals


def _detect_mentor_grid_unit(text: str, path: Path | None = None) -> float:
    """Detect native units per Wizard 0.100 inch grid for Mentor master geometry.

    Xpedition/Liebherr libraries may use two notations:
    - compact symbols, e.g. FPGA split parts: 10 native units = 1 grid
    - database-unit symbols, e.g. classic passives: 254000 native units = 1 grid

    The Z record alone is not enough: both examples use `Z 10`.  Therefore the
    importer detects the actual unit scale from 0° master geometry.  Half-grid
    coordinates such as 127000 are intentionally preserved as 0.5 grid.
    """
    vals = _numeric_tokens_for_grid_detection(text)
    if not vals:
        return 10.0
    # Strong signal for Liebherr/Mentor DB units: 127000/254000 based geometry or
    # six-digit coordinate magnitudes. Restricting to master rows avoids TVRNT
    # variants influencing the decision.
    hits_254 = sum(1 for v in vals if v % 127000 == 0 or v % 254000 == 0)
    large_vals = sum(1 for v in vals if v >= 127000)
    hits_10 = sum(1 for v in vals if v % 10 == 0 and v < 10000)
    stem = (Path(path).stem.lower() if path else "")
    passive_hint = bool(re.search(r"(^|[_\-])(wid|res|r|widerstand)([_\-]|$)", stem))
    if passive_hint or (large_vals >= 3 and hits_254 >= max(3, hits_10)):
        return 254000.0
    return 10.0


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


_STYLE_BLACK = StyleModel(stroke=(0, 0, 0), fill=None, line_width=0.03, line_style="solid")


def _graphic_line_from_points(points: list[tuple[float, float]], z: float, raw: str = "") -> list[GraphicModel]:
    """Convert Mentor l/polyline master geometry to Wizard line graphics."""
    out: list[GraphicModel] = []
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        out.append(GraphicModel(
            shape="line",
            x=_to_grid(x1, z), y=_to_grid(y1, z),
            w=_to_grid(x2 - x1, z), h=_to_grid(y1 - y2, z),
            mentor_raw=raw,
            style=StyleModel(stroke=(0, 0, 0), fill=None, line_width=0.03, line_style="solid"),
        ))
    return out


def _graphic_rect_from_mentor(x1: float, y1: float, x2: float, y2: float, z: float, raw: str = "") -> GraphicModel:
    left, right = min(x1, x2), max(x1, x2)
    bottom, top = min(y1, y2), max(y1, y2)
    return GraphicModel(
        shape="rect", x=_to_grid(left, z), y=_to_grid(top, z),
        w=_to_grid(right - left, z), h=_to_grid(top - bottom, z),
        mentor_raw=raw,
        style=StyleModel(stroke=(0, 0, 0), fill=None, line_width=0.03, line_style="solid"),
    )


def _graphic_circle_from_mentor(cx: float, cy: float, r: float, z: float, raw: str = "") -> GraphicModel:
    return GraphicModel(
        shape="ellipse", x=_to_grid(cx - r, z), y=_to_grid(cy + r, z),
        w=_to_grid(2 * r, z), h=_to_grid(2 * r, z),
        mentor_raw=raw,
        style=StyleModel(stroke=(0, 0, 0), fill=None, line_width=0.03, line_style="solid"),
    )


def _graphic_arc_from_mentor(x1: float, y1: float, cx: float, cy: float, x2: float, y2: float, z: float, raw: str = "") -> GraphicModel:
    """Mentor `a` rows are imported as quadratic-curve graphics.

    The existing Wizard line object already supports curved lines.  We preserve
    the exact 0° master start/control/end geometry by storing the control point
    relative to the start point, instead of flattening arcs into straight lines.
    """
    return GraphicModel(
        shape="arc",
        x=_to_grid(x1, z), y=_to_grid(y1, z),
        w=_to_grid(x2 - x1, z), h=_to_grid(y2 - y1, z),
        ctrl_x=_to_grid(cx - x1, z), ctrl_y=_to_grid(cy - y1, z),
        mentor_raw=raw,
        style=StyleModel(stroke=(0, 0, 0), fill=None, line_width=0.03, line_style="solid"),
    )


def _import_native_single(text: str, path: Path) -> SymbolModel:
    unit_name = _safe_name(path)
    symbol_name = unit_name
    # `Z` is kept as metadata in the Mentor file, but it does not reliably
    # describe the real coordinate unit system.  Use the detected native units
    # per Wizard grid for every imported coordinate/font/graphic.
    z_file = 10.0
    z = _detect_mentor_grid_unit(text, path)
    d_top = 0.0
    body = SymbolBodyModel()
    body.attributes.clear()
    body.visible_attributes.clear()
    pins_tmp: dict[int, dict[str, Any]] = {}
    texts: list[TextModel] = []
    graphics: list[GraphicModel] = []
    mentor_raw_unknown: list[str] = []
    body_box_seen = False

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line == "E":
            continue
        # Use only the 0° master representation. Mentor TVRNT lines are historical
        # orientation/transform variants and are intentionally ignored on import.
        if line.startswith("|TVRNT"):
            continue
        parts = line.split()
        tag = parts[0]
        try:
            if tag == "K" and len(parts) >= 3:
                unit_name = parts[2]
                symbol_name = _common_device_name(symbol_name, unit_name)
            elif tag == "Z" and len(parts) >= 2:
                z_file = float(parts[1]) or 10.0
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
                rect_g = _graphic_rect_from_mentor(x1, y1, x2, y2, z, line)
                if not body_box_seen:
                    # The first master box remains the editable body. Additional boxes are
                    # imported as true graphics so templates from the Liebherr library keep
                    # their original geometry.
                    body.x = rect_g.x
                    body.y = rect_g.y
                    body.width = rect_g.w
                    body.height = rect_g.h
                    body_box_seen = True
                else:
                    graphics.append(rect_g)
            elif tag == "l" and len(parts) >= 6:
                # Mentor line/polyline: l <point-count> x1 y1 x2 y2 [x3 y3 ...]
                try:
                    npts = int(float(parts[1]))
                    nums = [float(v) for v in parts[2:2 + 2 * npts]]
                    pts = list(zip(nums[0::2], nums[1::2]))
                    graphics.extend(_graphic_line_from_points(pts, z, line))
                except Exception:
                    mentor_raw_unknown.append(line)
            elif tag == "c" and len(parts) >= 4:
                cx, cy, r = map(float, parts[1:4])
                graphics.append(_graphic_circle_from_mentor(cx, cy, abs(r), z, line))
            elif tag == "a" and len(parts) >= 7:
                x1, y1, cx, cy, x2, y2 = map(float, parts[1:7])
                graphics.append(_graphic_arc_from_mentor(x1, y1, cx, cy, x2, y2, z, line))
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
                elif '=' in attr:
                    an, av = attr.split('=', 1)
                    pins_tmp[pid].setdefault('attributes', {})[an] = av
                    pins_tmp[pid].setdefault('visible_attributes', {})[an] = parts[6] != '0'
                    if an.upper() in ('FUNCTION', 'PIN_FUNCTION', 'PINFUNCTION'):
                        pins_tmp[pid]['function'] = av
            elif tag.startswith('|') or tag == 'Q':
                # Style/font/border records are retained as raw metadata for later
                # export/debugging. TVRNT is excluded above by design.
                if tag not in ('|A',):
                    mentor_raw_unknown.append(line)
        except Exception:
            mentor_raw_unknown.append(line)
            continue

    if not body.attributes:
        body.attributes.update({"RefDes": "U?", "Value": symbol_name})
        body.visible_attributes.update({"RefDes": True, "Value": True})
    else:
        body.attributes.setdefault("RefDes", "U?")
        body.attributes.setdefault("Value", symbol_name.upper())
        body.visible_attributes.setdefault("RefDes", True)
        body.visible_attributes.setdefault("Value", True)

    pins = []
    for k in sorted(pins_tmp):
        payload = pins_tmp[k]
        pmodel = PinModel(**payload)
        col = _pin_color_for_type(pmodel.pin_type)
        pmodel.color = col
        pmodel.number_font.color = col
        pmodel.label_font.color = col
        pins.append(pmodel)
    if not body_box_seen:
        body.x = 0.0; body.y = 0.0; body.width = 0.0; body.height = 0.0
        body.attributes["MENTOR_HAS_BODY"] = "0"
        body.visible_attributes["MENTOR_HAS_BODY"] = False
    else:
        body.attributes["MENTOR_HAS_BODY"] = "1"
        body.visible_attributes["MENTOR_HAS_BODY"] = False
    # Store detected import scale for diagnostics/template debugging.
    body.attributes.setdefault("MENTOR_GRID_UNIT", str(int(z) if float(z).is_integer() else z))
    body.visible_attributes.setdefault("MENTOR_GRID_UNIT", False)
    unit = SymbolUnitModel(name=unit_name, body=body, pins=pins, texts=texts, graphics=graphics, mentor_raw_unknown=mentor_raw_unknown)
    symbol = SymbolModel(name=symbol_name, kind=SymbolKind.SINGLE.value, is_split=False, grid_inch=0.100, origin="bottom_left", units=[unit])
    symbol.template_name = MENTOR_NATIVE_TEMPLATE
    return symbol


def _unit_extents(unit: SymbolUnitModel, z: float = 10.0) -> tuple[int, int, int, int]:
    xs: list[int] = []
    ys: list[int] = []
    b = unit.body
    has_body = str((getattr(b, "attributes", {}) or {}).get("MENTOR_HAS_BODY", "1")) != "0"
    if has_body or abs(float(getattr(b, "width", 0) or 0)) > 1e-9 or abs(float(getattr(b, "height", 0) or 0)) > 1e-9:
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
        if str(getattr(g, 'shape', '')).lower() in ('line',):
            ys += [_to_mentor(g.y, z), _to_mentor(g.y - g.h, z)]
        else:
            ys += [_to_mentor(g.y, z), _to_mentor(g.y + g.h, z), _to_mentor(g.y - g.h, z)]
        if getattr(g, 'ctrl_x', None) is not None and getattr(g, 'ctrl_y', None) is not None:
            xs.append(_to_mentor(g.x + float(g.ctrl_x or 0), z))
            ys.append(_to_mentor(g.y + float(g.ctrl_y or 0), z))
    if not xs:
        return 0, 100, 100, 0
    left = min(xs)
    right = max(xs)
    bottom = min(ys)
    top = max(ys)
    return left, top, right, bottom


def _mentor_text_align(h_align: str) -> int:
    return {"center": 5, "right": 8}.get((h_align or "left").lower(), 2)


def _export_grid_unit_for(unit: SymbolUnitModel, symbol: SymbolModel | None = None) -> float:
    """Native Mentor units per Wizard 0.100 inch grid for export.

    XCZ/split-style symbols use 10 units/grid. Classic Liebherr/Mentor symbols
    such as wid.1 use 254000 units/grid and may place geometry on half-grid
    coordinates.  Imported templates carry MENTOR_GRID_UNIT as hidden metadata.
    """
    candidates = []
    try:
        candidates.append((getattr(unit.body, 'attributes', {}) or {}).get('MENTOR_GRID_UNIT'))
    except Exception:
        pass
    try:
        candidates.append((getattr(symbol.units[0].body, 'attributes', {}) or {}).get('MENTOR_GRID_UNIT'))
    except Exception:
        pass
    for v in candidates:
        try:
            f = float(v)
            if f > 0:
                return f
        except Exception:
            continue
    return 10.0


def _export_native_unit(symbol: SymbolModel, unit: SymbolUnitModel, index: int, total: int) -> str:
    z = _export_grid_unit_for(unit, symbol)
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
    value = attrs.get("Value") or attrs.get("DEVICE") or attrs.get("VALUE") or symbol.name
    package = attrs.get("Package") or attrs.get("CASE") or "BAUFORM"
    attr_texts = getattr(unit.body, "attribute_texts", {}) or {}

    # Compact XCZ-style exports keep the established legacy attribute layout.
    # DB-unit symbols/templates (e.g. wid.1, MENTOR_GRID_UNIT=254000) use their
    # own 0° master attribute positions converted back with the same scale.
    if abs(float(z) - 10.0) < 1e-9:
        ref_t = attr_texts.get("RefDes")
        if ref_t:
            rx, ry, rs = _to_mentor(ref_t.x, z), _to_mentor(ref_t.y, z), max(1, _to_mentor(ref_t.font_size_grid, z))
        else:
            rx = _to_mentor(unit.body.x + unit.body.width / 2, z)
            ry = _to_mentor(unit.body.y + 1.0, z)
            rs = 16
        lines.append(f"U {rx} {ry} {rs} 0 5 3 REFDES={refdes if str(refdes).startswith('U') else refdes}")
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
    else:
        name_map = {"RefDes": "REFDES", "Package": "CASE", "Value": "DEVICE", "Part Name": "PART_NAME"}
        visible = getattr(unit.body, "visible_attributes", {}) or {}
        # Ensure the core attributes exist and preserve their visible placement when possible.
        core_order = ["RefDes", "PART_NAME", "@XYCOORD", "LEON_Link", "DEVICE", "VALUE", "CASE", "CLASS", "FORWARD_PCB"]
        ordered = []
        for k in core_order:
            if k in attrs and k not in ordered:
                ordered.append(k)
        for k in attrs:
            if k not in ordered and k != "MENTOR_GRID_UNIT":
                ordered.append(k)
        for k in ordered:
            if k == "MENTOR_GRID_UNIT":
                continue
            mentor_name = name_map.get(k, k)
            val = attrs.get(k, "")
            tm = attr_texts.get(k) or attr_texts.get(mentor_name)
            if tm:
                x = _to_mentor(tm.x, z); y = _to_mentor(tm.y, z); size = max(1, _to_mentor(tm.font_size_grid, z))
                align = _mentor_text_align(getattr(tm, 'h_align', 'left'))
                vis = 3 if visible.get(k, False) or visible.get(mentor_name, False) else 0
            else:
                # Invisible/default attributes sit near the original wid.1 placeholder position.
                x = _to_mentor(1.0, z); y = _to_mentor(-1.0, z); size = max(1, _to_mentor(1.0, z))
                align = 3; vis = 3 if visible.get(k, False) or visible.get(mentor_name, False) else 0
            lines.append(f"U {x} {y} {size} 0 {align} {vis} {mentor_name}={val}")

    b = unit.body
    has_body = str((getattr(b, "attributes", {}) or {}).get("MENTOR_HAS_BODY", "1")) != "0"
    if has_body and (abs(float(getattr(b, "width", 0) or 0)) > 1e-9 or abs(float(getattr(b, "height", 0) or 0)) > 1e-9):
        bx1 = _to_mentor(b.x, z); by_top = _to_mentor(b.y, z)
        bx2 = _to_mentor(b.x + b.width, z); by_bottom = _to_mentor(b.y - b.height, z)
        lines.append(f"b {bx1} {by_bottom} {bx2} {by_top}")

    # Export true graphic primitives from the 0° master geometry.  The editable
    # body box is written above; additional Mentor boxes/lines/circles/arcs live
    # in unit.graphics and are emitted here.
    for gobj in getattr(unit, 'graphics', []) or []:
        shape = str(getattr(gobj, 'shape', '') or '').lower()
        if shape == 'rect':
            x1 = _to_mentor(gobj.x, z); y_top = _to_mentor(gobj.y, z)
            x2 = _to_mentor(gobj.x + gobj.w, z); y_bottom = _to_mentor(gobj.y - gobj.h, z)
            lines.append(f"b {x1} {y_bottom} {x2} {y_top}")
        elif shape in ('ellipse', 'circle'):
            cx = _to_mentor(gobj.x + gobj.w / 2, z)
            cy = _to_mentor(gobj.y - gobj.h / 2, z)
            r = max(1, int(round((_to_mentor(abs(gobj.w), z) + _to_mentor(abs(gobj.h), z)) / 4)))
            lines.append(f"c {cx} {cy} {r}")
        elif shape in ('line', 'arc'):
            x1 = _to_mentor(gobj.x, z); y1 = _to_mentor(gobj.y, z)
            if shape == 'arc' or (getattr(gobj, 'ctrl_x', None) is not None and getattr(gobj, 'ctrl_y', None) is not None):
                x2 = _to_mentor(gobj.x + gobj.w, z); y2 = _to_mentor(gobj.y + gobj.h, z)
                cx = _to_mentor(gobj.x + float(getattr(gobj, 'ctrl_x', 0) or 0), z)
                cy = _to_mentor(gobj.y + float(getattr(gobj, 'ctrl_y', 0) or 0), z)
                lines.append(f"a {x1} {y1} {cx} {cy} {x2} {y2}")
            else:
                x2 = _to_mentor(gobj.x + gobj.w, z); y2 = _to_mentor(gobj.y - gobj.h, z)
                lines.append(f"l 2 {x1} {y1} {x2} {y2}")

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
        # Export pin function separately from pin name. Mentor treats these as
        # independent pin attributes; visibility 0 keeps the symbol native-clean.
        if str(getattr(pin, 'function', '') or '').strip() and str(pin.function) != str(pin.name):
            lines.append(f"A {ax_type} {y} 10 0 {atype_align} 0 PINFUNCTION={pin.function}")
        # Preserve additional invisible/custom pin attributes when present.
        for an, av in sorted((getattr(pin, 'attributes', {}) or {}).items()):
            if str(an).upper() in ('#', 'PINTYPE', 'PINFUNCTION', 'FUNCTION', 'PIN_FUNCTION'):
                continue
            vis = 3 if (getattr(pin, 'visible_attributes', {}) or {}).get(an, False) else 0
            lines.append(f"A {ax_type} {y} 10 0 {atype_align} {vis} {an}={av}")

    lines.append("E")
    return "\n".join(lines) + "\n"


# Backward-compatible helper parser for non-native key=value records is intentionally removed from
# the default import path. Native Mentor ASCII is now the authoritative interchange format.
