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
import zipfile
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from symbol_wizard.models.document import (
    FontModel,
    GraphicModel,
    PinModel,
    StyleModel,
    SymbolBodyModel,
    SymbolKind,
    PinType,
    SymbolModel,
    SymbolUnitModel,
    TextModel,
    to_dict,
)
from symbol_wizard.io.json_store import _symbol

MAGIC = "# SYMBOL_WIZARD_MENTOR_SYM_V1"

MENTOR_TEXT_SUFFIXES = ('.sym', '.1', '.2', '.3', '.4', '.5')


def is_split_mentor_container(path: str | Path) -> bool:
    """Return True when *path* is a zip container used for Mentor split parts."""
    return Path(path).suffix.lower() == '.zip'


def _mentor_part_sort_key(name: str) -> tuple[str, int, str]:
    stem = Path(name).stem
    m = re.search(r'^(.*?)(?:[_-](\d+))?(?:\.\d+)?$', stem)
    if not m:
        return (stem, 10**9, name)
    base = m.group(1) or stem
    num = int(m.group(2)) if m.group(2) is not None else -1
    return (base, num, name)


def _mentor_files_in_zip(zf: zipfile.ZipFile) -> list[str]:
    names = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        suffix = Path(info.filename).suffix.lower()
        base = Path(info.filename).name
        if base.startswith('.'):
            continue
        if suffix in MENTOR_TEXT_SUFFIXES or re.search(r'\.\d+$', base):
            names.append(info.filename)
    return sorted(names, key=_mentor_part_sort_key)


def import_mentor_symbol_file(path: str | Path) -> SymbolModel:
    """Import exactly one Mentor part file as one SymbolModel with one unit."""
    return import_mentor_sym(path)


def import_mentor_symbol_bundle(path: str | Path) -> SymbolModel:
    """Import Mentor symbols using the project convention.

    * A single .sym/.1 file is one normal symbol.
    * A .zip file is one split symbol; every Mentor symbol file inside becomes
      one split unit/part, ordered naturally by its file name.
    """
    p = Path(path)
    if p.suffix.lower() != '.zip':
        s = import_mentor_symbol_file(p)
        s.kind = SymbolKind.SINGLE.value if len(s.units) <= 1 else SymbolKind.SPLIT.value
        s.is_split = s.kind == SymbolKind.SPLIT.value
        return s
    with zipfile.ZipFile(p, 'r') as zf:
        names = _mentor_files_in_zip(zf)
        if not names:
            raise ValueError('ZIP enthält keine Mentor .sym/.1 Symbol-Dateien.')
        units: list[SymbolUnitModel] = []
        symbol_name = Path(names[0]).stem
        common_attrs: dict[str, str] = {}
        visible_attrs: dict[str, bool] = {}
        grid = 0.1
        sheet = 'A3'
        origin = 'center'
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            for idx, name in enumerate(names, start=1):
                out = tmpdir / Path(name).name
                out.write_bytes(zf.read(name))
                part = import_mentor_symbol_file(out)
                if idx == 1:
                    symbol_name = _base_symbol_name_from_part(part.name)
                    grid = part.grid_inch
                    sheet = part.sheet_format
                    origin = part.origin
                    if part.units:
                        common_attrs = dict(part.units[0].body.attributes)
                        visible_attrs = dict(part.units[0].body.visible_attributes)
                for u in part.units:
                    u.name = Path(name).name
                    # Split-level attributes stay consistent across all parts.
                    if common_attrs:
                        merged = dict(common_attrs)
                        merged.update(u.body.attributes)
                        u.body.attributes = merged
                    if visible_attrs:
                        vv = dict(visible_attrs)
                        vv.update(u.body.visible_attributes)
                        u.body.visible_attributes = vv
                    units.append(u)
        return SymbolModel(
            name=symbol_name,
            kind=SymbolKind.SPLIT.value,
            is_split=True,
            grid_inch=grid,
            sheet_format=sheet,
            origin=origin,
            units=units,
        )


def export_mentor_symbol_bundle(path: str | Path, symbol: SymbolModel) -> None:
    """Export Mentor symbols using the project convention.

    Split symbols are always written as .zip where each unit is one part file.
    Single symbols are written as one .sym file.
    """
    p = Path(path)
    is_split = bool(symbol.kind == SymbolKind.SPLIT.value or symbol.is_split or len(symbol.units) > 1)
    if not is_split:
        if p.suffix.lower() == '.zip':
            p = p.with_suffix('.sym')
        export_mentor_sym(p, symbol)
        return
    if p.suffix.lower() != '.zip':
        p = p.with_suffix('.zip')
    with zipfile.ZipFile(p, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        used: set[str] = set()
        for idx, unit in enumerate(symbol.units, start=1):
            part_name = _unit_part_filename(symbol.name, unit.name, idx, used)
            part_symbol = SymbolModel(
                name=Path(part_name).stem,
                kind=SymbolKind.SINGLE.value,
                is_split=False,
                grid_inch=symbol.grid_inch,
                sheet_format=symbol.sheet_format,
                origin=symbol.origin,
                template_name=symbol.template_name,
                units=[unit],
            )
            with tempfile.TemporaryDirectory() as td:
                tmp = Path(td) / part_name
                export_mentor_sym(tmp, part_symbol)
                zf.write(tmp, arcname=part_name)


def _base_symbol_name_from_part(name: str) -> str:
    # Common Mentor split-part names look like xczu3egsfvc784b_24 or name_24.1.
    stem = Path(name).stem
    return re.sub(r'[_-]\d+$', '', stem) or stem


def _unit_part_filename(symbol_name: str, unit_name: str, index: int, used: set[str]) -> str:
    raw = Path(unit_name or '').name
    if raw.lower().endswith(MENTOR_TEXT_SUFFIXES) or re.search(r'\.\d+$', raw):
        name = raw
    else:
        safe_unit = re.sub(r'[^A-Za-z0-9_.-]+', '_', unit_name or str(index)).strip('_')
        safe_symbol = re.sub(r'[^A-Za-z0-9_.-]+', '_', symbol_name or 'symbol').strip('_')
        name = f'{safe_symbol}_{safe_unit or index}.sym'
    if not (name.lower().endswith(MENTOR_TEXT_SUFFIXES) or re.search(r'\.\d+$', name)):
        name += '.sym'
    base = name
    counter = 2
    while name in used:
        stem = Path(base).stem
        suffix = ''.join(Path(base).suffixes) or '.sym'
        name = f'{stem}_{counter}{suffix}'
        counter += 1
    used.add(name)
    return name


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


def _normalize_pin_type(value: str) -> str:
    v = (value or '').strip().upper()
    mapping = {'BI': 'BIDI', 'BIDIR': 'BIDI', 'BIDIRECTIONAL': 'BIDI', 'GND': 'GROUND', 'PWR': 'POWER'}
    v = mapping.get(v, v)
    allowed = {x.value for x in PinType}
    return v if v in allowed else PinType.BIDI.value


def _import_best_effort_ascii(text: str, path: Path) -> SymbolModel:
    # Prefer the real DxDesigner/Xpedition ASCII parser when the file uses the
    # compact V/K/D/P/L/A/b/T records.  These records do not carry explicit
    # colors; black is therefore intentional and comes from the Wizard theme.
    if re.search(r'(?m)^P\s+\d+\s+', text) and re.search(r'(?m)^D\s+', text):
        return _import_xpedition_ascii(text, path)

    symbol = SymbolModel(name=_safe_name(path), kind=SymbolKind.SINGLE.value, is_split=False)
    unit = symbol.units[0]
    unit.name = Path(path).name
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
                    pin_type=_normalize_pin_type(str(kv.get("type", kv.get("pin_type", "BIDI")))),
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


def _mentor_align_h(code: str | int) -> str:
    try:
        c = int(code)
    except Exception:
        c = 0
    if c in (5, 6):
        return 'center'
    if c in (8, 9):
        return 'right'
    return 'left'


def _mentor_align_v(code: str | int) -> str:
    try:
        c = int(code)
    except Exception:
        c = 0
    if c in (5, 6):
        return 'center'
    if c in (2, 3, 8, 9):
        return 'center'
    return 'upper'


def _import_xpedition_ascii(text: str, path: Path) -> SymbolModel:
    name = _safe_name(path)
    d_box: tuple[float, float, float, float] | None = None
    rects: list[tuple[float, float, float, float]] = []
    attrs: dict[str, str] = {}
    attr_visible: dict[str, bool] = {}
    texts_raw: list[tuple[float, float, float, float, str, str]] = []
    pins_raw: dict[str, dict[str, Any]] = {}
    last_pin_id: str | None = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line == 'E':
            continue
        if line.startswith('K '):
            parts = line.split(maxsplit=2)
            if len(parts) >= 3:
                name = parts[2].strip() or name
            continue
        parts = line.split()
        tag = parts[0] if parts else ''
        if tag == 'D' and len(parts) >= 5:
            d_box = (_float(parts[1]), _float(parts[2]), _float(parts[3]), _float(parts[4]))
            continue
        if tag == 'b' and len(parts) >= 5:
            rects.append((_float(parts[1]), _float(parts[2]), _float(parts[3]), _float(parts[4])))
            continue
        if tag == 'U' and len(parts) >= 8:
            payload = ' '.join(parts[7:])
            if '=' in payload:
                key, value = payload.split('=', 1)
                key = key.strip()
                value = value.strip()
                if key.upper() == 'REFDES':
                    key = 'RefDes'
                    value = 'U?' if value in ('', '?') else value
                elif key.upper() in ('DEVICE', 'PART_NAME'):
                    # DEVICE/PART_NAME are useful, but Value is the Wizard's primary body attribute.
                    attrs[key] = value
                    attr_visible[key] = parts[6] not in ('0',)
                    continue
                attrs[key] = value
                attr_visible[key] = parts[6] not in ('0',)
            continue
        if tag == 'T' and len(parts) >= 7:
            x = _float(parts[1]); y = _float(parts[2]); size = _float(parts[3]); rot = _float(parts[4])
            align = parts[5]
            txt = ' '.join(parts[6:])
            texts_raw.append((x, y, size, rot, align, txt))
            continue
        if tag == 'P' and len(parts) >= 9:
            pid = parts[1]
            x1, y1, x2, y2 = map(_float, parts[2:6])
            side_code = parts[7]
            side = 'right' if side_code == '3' or x1 > x2 else 'left'
            pins_raw[pid] = {'id': pid, 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'side': side, 'name': f'PIN_{pid}', 'number': pid, 'pin_type': 'BIDI'}
            last_pin_id = pid
            continue
        if tag == 'L' and len(parts) >= 10 and last_pin_id and last_pin_id in pins_raw:
            pins_raw[last_pin_id]['name'] = ' '.join(parts[9:])
            continue
        if tag == 'A' and len(parts) >= 8:
            payload = ' '.join(parts[7:])
            if '=' not in payload:
                continue
            key, value = payload.split('=', 1)
            key = key.strip().upper(); value = value.strip()
            # Attributes usually immediately follow their P/L record. Associate
            # them by nearest pin endpoint as a safe fallback.
            target = last_pin_id
            if target not in pins_raw:
                continue
            if key == '#':
                pins_raw[target]['number'] = value
            elif key == 'PINTYPE':
                pins_raw[target]['pin_type'] = _normalize_pin_type(value)
            continue

    if d_box is None:
        d_box = (0.0, 0.0, 100.0, 100.0)
    min_x = min(d_box[0], d_box[2])
    max_x = max(d_box[0], d_box[2])
    min_y = min(d_box[1], d_box[3])
    max_y = max(d_box[1], d_box[3])
    width_raw = max(1.0, max_x - min_x)
    height_raw = max(1.0, max_y - min_y)
    # Scale source coordinates into Wizard grid units.  Xpedition symbol files
    # normally use 10 mil grid units while the Wizard uses 0.1 inch grid units.
    # The visible Mentor samples are compact FPGA symbols; this scale preserves
    # the proven import shape from the conversation.
    scale = 20.0 / width_raw if width_raw else 0.05
    height_grid = height_raw * scale
    width_grid = width_raw * scale

    def tx(x: float) -> float:
        return (x - min_x) * scale - width_grid / 2.0

    def ty(y: float) -> float:
        return (y - min_y) * scale - height_grid / 2.0

    unit = SymbolUnitModel(name=Path(path).name)
    unit.body = SymbolBodyModel(x=-width_grid/2.0, y=height_grid/2.0, width=width_grid, height=height_grid)
    unit.body.attributes.clear(); unit.body.visible_attributes.clear()
    unit.body.attributes.update({
        'RefDes': attrs.pop('RefDes', 'U?'),
        'Value': attrs.get('DEVICE') or attrs.get('PART_NAME') or name,
    })
    unit.body.visible_attributes.update({'RefDes': True, 'Value': True})
    for k, v in attrs.items():
        unit.body.attributes[k] = v
        unit.body.visible_attributes[k] = attr_visible.get(k, False)

    # Preserve non-body text, but suppress REFDES/property U records; they are body attributes.
    for x, y, size, rot, align, txt in texts_raw:
        unit.texts.append(TextModel(
            text=txt,
            x=tx(x),
            y=ty(y),
            rotation=rot,
            font_family='Arial',
            font_size_grid=max(0.35, size * scale * 0.45),
            color=(0, 0, 0),
            h_align=_mentor_align_h(align),
            v_align=_mentor_align_v(align),
        ))

    for rx1, ry1, rx2, ry2 in rects:
        x1, x2 = sorted((tx(rx1), tx(rx2)))
        y1, y2 = sorted((ty(ry1), ty(ry2)), reverse=True)
        unit.graphics.append(GraphicModel(shape='rect', x=x1, y=y1, w=(x2-x1), h=abs(y1-y2), style=StyleModel(stroke=(0,0,0))))

    for pr in sorted(pins_raw.values(), key=lambda p: int(p['id']) if str(p['id']).isdigit() else 0):
        side = pr['side']
        sx = pr['x1'] if side == 'left' else pr['x1']
        sy = pr['y1']
        length = max(0.5, abs(pr['x2'] - pr['x1']) * scale)
        pin = PinModel(
            number=str(pr.get('number') or pr['id']),
            name=str(pr.get('name') or pr.get('number') or pr['id']),
            function=str(pr.get('name') or ''),
            pin_type=_normalize_pin_type(str(pr.get('pin_type') or 'BIDI')),
            side=side,
            x=tx(sx),
            y=ty(sy),
            length=length,
            color=(0, 0, 0),
            visible_number=True,
            visible_name=True,
            visible_function=False,
        )
        unit.pins.append(pin)

    symbol = SymbolModel(
        name=name,
        kind=SymbolKind.SINGLE.value,
        is_split=False,
        grid_inch=0.1,
        origin='center',
        units=[unit],
    )
    return symbol
