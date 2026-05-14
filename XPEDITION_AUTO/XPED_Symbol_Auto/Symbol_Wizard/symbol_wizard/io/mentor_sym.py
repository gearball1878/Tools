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
            pin_palette=dict(MENTOR_PIN_PALETTE),
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
    """Export a SymbolModel to native Mentor/Xpedition/DxDesigner ASCII.

    This writes the same family of files as the customer supplied reference ZIP:
    ``V/K/F/D/Y/Z/i/U/b/T/P/L/A/E`` records.  Split handling happens in
    :func:`export_mentor_symbol_bundle`; this function writes the unit(s) it is
    given into one Mentor part file.  Because normal Xpedition ASCII symbols do
    not carry RGB object colors, colors are intentionally not emitted.
    """
    p = Path(path)
    unit = symbol.units[0] if symbol.units else SymbolUnitModel(name=p.name)
    p.write_text(_export_xpedition_ascii_part(symbol, unit, p.stem), encoding='utf-8', newline='')


def _fmt_num(v: float) -> str:
    iv = int(round(v))
    return str(iv)


def _mentor_pintype(value: str) -> str:
    v = (value or '').strip().upper()
    if v == 'BIDI':
        return 'BI'
    if v == 'PASSIVE':
        return 'BI'
    return v or 'BI'


def _mentor_text_align(h_align: str, v_align: str = 'center') -> int:
    h = (h_align or '').lower()
    if h == 'center':
        return 5
    if h == 'right':
        return 8
    return 2


def _mentor_font_size_grid_to_ascii(size_grid: float, fallback: int = 10) -> int:
    try:
        # Wizard font sizes are stored in grid units.  The reference files use
        # 10 for pin labels and 20 for headers; this mapping keeps the same
        # visual proportions for imported/exported parts.
        return max(1, int(round(float(size_grid) * 18)))
    except Exception:
        return fallback


def _safe_mentor_name(name: str, default: str = 'symbol') -> str:
    value = re.sub(r'[^A-Za-z0-9_.-]+', '_', str(name or default)).strip('_')
    return value or default


def _source_part_stem(unit: SymbolUnitModel, fallback: str) -> str:
    raw = Path(unit.name or fallback).name
    if raw.lower().endswith(MENTOR_TEXT_SUFFIXES) or re.search(r'\.\d+$', raw):
        return Path(raw).stem
    return _safe_mentor_name(raw or fallback)


def _export_xpedition_ascii_part(symbol: SymbolModel, unit: SymbolUnitModel, part_stem: str) -> str:
    # Native Mentor sample uses 0.1 inch Wizard grid -> 20 ASCII coordinate
    # units and 2 grid pin length -> 40 ASCII units.  For symbols that were
    # imported from the sample this recreates the same compact form; for newly
    # drawn Wizard symbols it still produces valid, grid-aligned Xpedition ASCII.
    raw_per_grid = 20.0
    pin_len_default = 30.0
    margin = 30.0

    body = unit.body
    # If this unit was imported from native Xpedition ASCII, the source body
    # rectangle is stored as a rect graphic.  Use that rectangle to recover the
    # original 30-unit Mentor margins and avoid exporting a second duplicate box.
    body_rect_graphic = next((g for g in unit.graphics if (g.shape or '').lower() == 'rect' and abs(float(g.w)) > 4 and abs(float(g.h)) > 4), None)
    if body_rect_graphic is not None:
        raw_per_grid = 300.0 / max(1.0, abs(float(body_rect_graphic.w)))
    left_pins = [pin for pin in unit.pins if (pin.side or '').lower() != 'right']
    right_pins = [pin for pin in unit.pins if (pin.side or '').lower() == 'right']

    # Body rectangle.  The reference format draws pin stubs outside the body:
    # left pins 0->30, body 30->W-30, right pins W->W-30.
    body_w = max(4.0, float(getattr(body, 'width', 18.0) or 18.0))
    body_h = max(4.0, float(getattr(body, 'height', 10.0) or 10.0))
    raw_w = max(120.0, round(body_w * raw_per_grid / 10.0) * 10.0)
    raw_h = max(100.0, round(body_h * raw_per_grid / 10.0) * 10.0)

    # Ensure enough height for all pins if the user built a very dense unit.
    max_side_count = max(len(left_pins), len(right_pins), 1)
    min_h_for_pins = margin * 2 + max_side_count * 20
    raw_h = max(raw_h, float(min_h_for_pins))
    raw_w = max(raw_w, 360.0)

    if body_rect_graphic is not None:
        raw_w = max(120.0, abs(float(body_rect_graphic.w)) * raw_per_grid + 2 * margin)
        raw_h = max(float(min_h_for_pins), abs(float(body_rect_graphic.h)) * raw_per_grid + 2 * margin)

    box_x1 = margin
    box_x2 = raw_w - margin
    box_y1 = margin
    box_y2 = raw_h - margin

    # Map Wizard y positions to Mentor y positions where useful.  If all pins
    # are on regular Wizard rows this preserves their order.  Otherwise fallback
    # to deterministic top-down placement per side.
    all_pin_y = [float(pin.y) for pin in unit.pins]
    if all_pin_y:
        min_y, max_y = min(all_pin_y), max(all_pin_y)
    else:
        min_y, max_y = -1.0, 1.0
    span_y = max(1e-6, max_y - min_y)

    def pin_y_from_model(pin: PinModel, index: int, side_count: int) -> int:
        # Imported symbols often have exact y values.  Use them when they produce
        # sane in-body coordinates; otherwise row-pack top-down in 20-unit pitch.
        y = raw_h - margin - 20 - ((float(pin.y) - min_y) / span_y) * max(20.0, raw_h - 100.0)
        if not (margin + 10 <= y <= raw_h - margin - 10) or side_count > 1 and span_y < 0.01:
            y = raw_h - margin - 20 - index * 20
        return int(round(y / 10.0) * 10)

    lines: list[str] = []
    name = _source_part_stem(unit, part_stem or symbol.name)
    lines.append('V 53')
    # Use a deterministic key instead of current time, so exports are diffable.
    key = abs(hash((symbol.name, unit.name, len(unit.pins)))) % 2_000_000_000
    lines.append(f'K {key} {name}')
    lines.append('|R 0:00:00_4-16-19')
    lines.append('F Case')
    lines.append(f'D 0 {_fmt_num(raw_h)} {_fmt_num(raw_w)} 0')
    lines.append('Y 1')
    lines.append('Z 10')
    lines.append(f'i {len(unit.pins) + 1}')

    attrs = dict(getattr(body, 'attributes', {}) or {})
    visible = dict(getattr(body, 'visible_attributes', {}) or {})
    refdes = attrs.get('REFDES', attrs.get('RefDes', 'U?')) or 'U?'
    if str(refdes).strip() == '?':
        refdes = 'U?'
    lines.append(f'U {_fmt_num(raw_w/2)} {_fmt_num(raw_h-8)} 16 0 5 3 REFDES={refdes.replace("U?", "?") if refdes == "U?" else refdes}')

    # Emit the Mentor-style standard attributes first.  These are the fields the
    # reference ZIP carries and they make exported parts usable in the existing
    # library flow.  Additional Wizard attributes are appended afterwards.
    standard = [
        ('CASE', attrs.get('CASE', 'BAUFORM'), 30, 0, 10, 0, 3, 3),
        ('CLASS', attrs.get('CLASS', ''), 80, 20, 10, 0, 3, 3),
        ('PART_NAME', attrs.get('PART_NAME', attrs.get('Part Name', attrs.get('Value', 'TNR_LEG'))), 30, 20, 10, 0, 3, 3),
        ('@XYCOORD', attrs.get('@XYCOORD', ''), 30, 20, 25400, 0, 3, 0),
        ('LEON_Link', attrs.get('LEON_Link', ''), 30, 20, 25400, 0, 3, 0),
        ('DEVICE', attrs.get('DEVICE', attrs.get('Device', attrs.get('Value', symbol.name))), 30, 20, 10, 0, 3, 0),
        ('TYPE', attrs.get('TYPE', attrs.get('Type', 'TYPE')), 30, 10, 10, 0, 3, 3),
        ('FORWARD_PCB', attrs.get('FORWARD_PCB', '1'), 0, 0, 10, 0, 1, 0),
    ]
    emitted = {'REFDES', 'RefDes'}
    for key_name, val, x, y, size, rot, align, vis in standard:
        lines.append(f'U {x} {y} {size} {rot} {align} {vis} {key_name}={val}')
        emitted.add(key_name)
    for key_name, val in attrs.items():
        if key_name in emitted or key_name in {'Value', 'Package', 'Technology', 'Order Code', 'Frequency', 'Tolerance'}:
            continue
        vis = '3' if visible.get(key_name, False) else '0'
        lines.append(f'U 30 20 10 0 3 {vis} {key_name}={val}')

    lines.append(f'b {_fmt_num(box_x1)} {_fmt_num(box_y1)} {_fmt_num(box_x2)} {_fmt_num(box_y2)}')

    title = attrs.get('Value') or attrs.get('DEVICE') or attrs.get('PART_NAME') or symbol.name
    # For native imports the visible title/page labels are already stored as T
    # records in unit.texts.  Only synthesize a title for symbols that do not
    # have any explicit text objects.
    if title and not unit.texts:
        lines.append(f'T {_fmt_num(raw_w/2)} {_fmt_num(raw_h-28)} 20 0 5 {title}')

    # Preserve user texts.  Title-like duplicate texts are harmless but avoid
    # duplicating an exact title at nearly the same top position.
    for text in unit.texts:
        if not str(text.text).strip():
            continue
        x = raw_w/2 + float(text.x) * raw_per_grid
        y = raw_h/2 - float(text.y) * raw_per_grid
        if abs(x - raw_w/2) < 8 and abs(y - (raw_h-28)) < 25 and str(text.text) == str(title):
            continue
        size = _mentor_font_size_grid_to_ascii(text.font_size_grid, 10)
        rot = 1 if abs(float(getattr(text, 'rotation', 0.0) or 0.0)) in (90.0, 270.0) else 0
        align = _mentor_text_align(text.h_align, text.v_align)
        lines.append(f'T {_fmt_num(x)} {_fmt_num(y)} {size} {rot} {align} {text.text}')

    # Graphics: output rectangles and simple lines in the same ASCII family.
    for graphic in unit.graphics:
        if graphic is body_rect_graphic:
            continue
        shape = (graphic.shape or 'line').lower()
        x1 = raw_w/2 + float(graphic.x) * raw_per_grid
        y1 = raw_h/2 - float(graphic.y) * raw_per_grid
        x2 = x1 + float(graphic.w) * raw_per_grid
        y2 = y1 + float(graphic.h) * raw_per_grid
        if shape == 'rect':
            lines.append(f'b {_fmt_num(min(x1,x2))} {_fmt_num(min(y1,y2))} {_fmt_num(max(x1,x2))} {_fmt_num(max(y1,y2))}')
        else:
            lines.append(f'l 2 {_fmt_num(x1)} {_fmt_num(y1)} {_fmt_num(x2)} {_fmt_num(y2)}')

    # Pins are sorted by side and y to produce stable reference-like output.
    ordered: list[PinModel] = []
    ordered.extend(sorted(left_pins, key=lambda p: (-float(p.y), str(p.number), str(p.name))))
    ordered.extend(sorted(right_pins, key=lambda p: (-float(p.y), str(p.number), str(p.name))))

    side_counts = {'left': len(left_pins), 'right': len(right_pins)}
    side_index = {'left': 0, 'right': 0}
    for pid, pin in enumerate(ordered, start=1):
        side = 'right' if (pin.side or '').lower() == 'right' else 'left'
        idx = side_index[side]
        side_index[side] += 1
        y = pin_y_from_model(pin, idx, side_counts[side])
        if side == 'right':
            x1, x2 = raw_w, raw_w - pin_len_default
            side_code = 3
            label_x = x2 - 5
            label_align = 8
            num_x = x2 + 10
            num_align = 3
            type_x = raw_w + 5
            type_align = 2
        else:
            x1, x2 = 0, pin_len_default
            side_code = 2
            label_x = x2 + 5
            label_align = 2
            num_x = x2 - 5
            num_align = 9
            type_x = -5 if _mentor_pintype(pin.pin_type) == 'BI' else 10
            type_align = 8 if type_x < 0 else 2
        pin_name = str(pin.name or pin.function or pin.number or f'PIN_{pid}')
        pin_number = str(pin.number or pid)
        ptype = _mentor_pintype(pin.pin_type)
        lines.append(f'P {pid} {_fmt_num(x1)} {_fmt_num(y)} {_fmt_num(x2)} {_fmt_num(y)} 0 {side_code} 0')
        lines.append(f'L {_fmt_num(label_x)} {_fmt_num(y)} 10 0 {label_align} 0 1 0 {pin_name}')
        lines.append(f'A {_fmt_num(num_x)} {_fmt_num(y)} 8 0 {num_align} 3 #={pin_number}')
        lines.append(f'A {_fmt_num(type_x)} {_fmt_num(y)} 10 0 {type_align} 0 PINTYPE={ptype}')

    lines.append('E')
    return '\r\n'.join(lines) + '\r\n'


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


MENTOR_PIN_PALETTE: dict[str, tuple[int, int, int]] = {
    PinType.IN.value: (0, 84, 170),
    PinType.OUT.value: (214, 96, 0),
    PinType.BIDI.value: (128, 0, 160),
    PinType.PASSIVE.value: (0, 0, 0),
    PinType.POWER.value: (200, 0, 0),
    PinType.GROUND.value: (0, 140, 0),
    PinType.ANALOG.value: (0, 140, 160),
}


def _mentor_pin_color(pin_type: str) -> tuple[int, int, int]:
    return MENTOR_PIN_PALETTE.get(_normalize_pin_type(pin_type), (0, 0, 0))


def _snap_grid(value: float, step: float = 0.5) -> float:
    # 0.5 Wizard grid == 50 mil. This keeps Mentor 30/20 raw-unit geometry
    # visually aligned to the user's 0.100 inch grid without producing odd
    # decimals. Use step=1.0 when a strict 100 mil body frame is required.
    try:
        v = round(float(value) / step) * step
        return 0.0 if abs(v) < 1e-9 else v
    except Exception:
        return 0.0


def _snap_body_grid(value: float) -> float:
    return _snap_grid(value, 1.0)


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
        # Mentor/DxDesigner ASCII has its Y axis mirrored relative to the
        # Wizard's cartesian symbol model.  Reflect every imported object at
        # the symbol center so origin, pin rows and labels round-trip.
        return height_grid / 2.0 - (y - min_y) * scale

    unit = SymbolUnitModel(name=Path(path).name)
    unit.body = SymbolBodyModel(
        x=_snap_body_grid(-width_grid/2.0),
        y=_snap_body_grid(height_grid/2.0),
        width=max(1.0, _snap_body_grid(width_grid)),
        height=max(1.0, _snap_body_grid(height_grid)),
    )
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
            x=_snap_grid(tx(x)),
            y=_snap_grid(ty(y)),
            rotation=rot,
            font_family='Arial',
            font_size_grid=max(0.35, size * scale * 0.45),
            color=(0, 0, 0),
            h_align=_mentor_align_h(align),
            v_align=_mentor_align_v(align),
        ))

    for rx1, ry1, rx2, ry2 in rects:
        x1, x2 = sorted((_snap_grid(tx(rx1)), _snap_grid(tx(rx2))))
        y_top, y_bottom = max(_snap_grid(ty(ry1)), _snap_grid(ty(ry2))), min(_snap_grid(ty(ry1)), _snap_grid(ty(ry2)))
        unit.graphics.append(GraphicModel(shape='rect', x=x1, y=y_top, w=_snap_grid(x2-x1), h=abs(_snap_grid(y_top-y_bottom)), style=StyleModel(stroke=(0,0,0))))

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
            x=_snap_grid(tx(sx)),
            y=_snap_grid(ty(sy)),
            length=_snap_grid(length),
            color=_mentor_pin_color(str(pr.get('pin_type') or 'BIDI')),
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
        pin_palette=dict(MENTOR_PIN_PALETTE),
        units=[unit],
    )
    return symbol
