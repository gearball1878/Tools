"""Conservative text geometry audit for generated KiCad pages."""
from __future__ import annotations

from .kicad_readback import _children, parse_sexpr


PAPER_SIZE = {"A0": (1189, 841), "A1": (841, 594),
              "A2": (594, 420), "A3": (420, 297), "A4": (297, 210)}


def audit_page_bounds(files: dict[str, str]) -> list[str]:
    problems = []
    for filename, content in files.items():
        if not filename.endswith(".kicad_sch"):
            continue
        tree = parse_sexpr(content)
        paper = _children(tree, "paper")[0][1]
        page_width, page_height = PAPER_SIZE[paper]
        sheet_boxes = []
        for sheet in _children(tree, "sheet"):
            at, size = _children(sheet, "at")[0], _children(sheet, "size")[0]
            x0, y0 = float(at[1]), float(at[2])
            x1, y1 = x0 + float(size[1]), y0 + float(size[2])
            if x0 < 0 or y0 < 0 or x1 > page_width or y1 > page_height:
                problems.append(f"{filename}: Sheet außerhalb des Blatts")
            for u0, v0, u1, v1 in sheet_boxes:
                if min(x1, u1) - max(x0, u0) > 0.1 and min(y1, v1) - max(y0, v0) > 0.1:
                    problems.append(f"{filename}: Hierarchieblöcke überlappen")
            sheet_boxes.append((x0, y0, x1, y1))
        for kind in ("wire", "bus", "label", "hierarchical_label", "global_label", "text"):
            for item in _children(tree, kind):
                coords = (_children(_children(item, "pts")[0], "xy") if kind in {"wire", "bus"}
                          else [_children(item, "at")[0]])
                for point in coords:
                    x, y = float(point[1]), float(point[2])
                    if x < 0 or y < 0 or x > page_width or y > page_height:
                        problems.append(f"{filename}: {kind} außerhalb des Blatts")
                if kind in {"wire", "bus"} and len(coords) == 2:
                    a, b = [(float(p[1]), float(p[2])) for p in coords]
                    if abs(a[1] - b[1]) < 0.001:
                        for x0, y0, x1, y1 in sheet_boxes:
                            if y0 + 0.1 < a[1] < y1 - 0.1 and min(max(a[0], b[0]), x1) - max(min(a[0], b[0]), x0) > 0.1:
                                problems.append(f"{filename}: Leitung kreuzt einen Hierarchieblock")
    return problems


def audit_text_collisions(files: dict[str, str]) -> list[str]:
    problems: list[str] = []
    for filename, content in files.items():
        if not filename.endswith(".kicad_sch"):
            continue
        page = parse_sexpr(content)
        boxes = []
        for kind in ("text", "label", "hierarchical_label", "global_label"):
            for item in _children(page, kind):
                effects = _children(item, "effects")
                if effects and _children(effects[0], "hide"):
                    continue
                font = _children(effects[0], "font") if effects else []
                dimensions = _children(font[0], "size") if font else []
                size = float(dimensions[0][1]) if dimensions else 1.0
                at = _children(item, "at")[0]
                x, y = float(at[1]), float(at[2])
                angle = int(float(at[3])) if len(at) > 3 else 0
                width = len(str(item[1])) * size * 0.78
                justify = _children(effects[0], "justify") if effects else []
                align = justify[0][1] if justify and len(justify[0]) > 1 else "center"
                if kind != "text":
                    align = "right" if angle == 180 else "left"
                x0 = x if align == "left" else x - width if align == "right" else x - width / 2
                # A local label sits above its wire; other text is centered on its anchor.
                y0 = y - size if kind == "label" else y - size * 0.5
                boxes.append((str(item[1]), x0, y0, x0 + width, y0 + size))
        # Sheet-pin text is rendered by KiCad and must count in the audit too.
        for sheet in _children(page, "sheet"):
            for pin in _children(sheet, "pin"):
                effects = _children(pin, "effects")
                if not effects or _children(effects[0], "hide"):
                    continue
                font = _children(effects[0], "font")
                dimensions = _children(font[0], "size") if font else []
                size = float(dimensions[0][1]) if dimensions else 1.0
                at = _children(pin, "at")[0]
                x, y = float(at[1]), float(at[2])
                justification = _children(effects[0], "justify")
                side = justification[0][1] if justification else "center"
                width = len(str(pin[1])) * size * 0.78
                x0 = x if side == "left" else x - width if side == "right" else x - width / 2
                boxes.append((str(pin[1]), x0, y - size / 2, x0 + width, y + size / 2))
        for i, (a, x0, y0, x1, y1) in enumerate(boxes):
            for b, u0, v0, u1, v1 in boxes[i + 1:]:
                if min(x1, u1) - max(x0, u0) > 0.25 and min(y1, v1) - max(y0, v0) > 0.25:
                    problems.append(f"{filename}: {a} / {b}")
    return problems
