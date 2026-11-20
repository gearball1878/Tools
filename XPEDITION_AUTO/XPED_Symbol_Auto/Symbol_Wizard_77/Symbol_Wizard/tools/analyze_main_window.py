from __future__ import annotations

"""Create a method inventory for the MainWindow god-object.

This is intentionally static and uses only the standard library so it can run
without PySide6. It helps plan the next extraction step without changing GUI
behaviour.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW_PATH = ROOT / "symbol_wizard" / "gui" / "main_window.py"
REPORT_PATH = ROOT / "docs" / "main_window_method_inventory.md"

CATEGORIES: list[tuple[str, tuple[str, ...]]] = [
    ("Lifecycle / setup", ("__init__", "_build", "_menus", "_toolbar", "_ribbon", "closeEvent", "autosave", "workspace", "tabs")),
    ("Grid / coordinates", ("grid", "snap", "scene_to", "edit_grid", "pin_grid")),
    ("Scene rebuild / refresh", ("rebuild", "refresh", "scene", "canvas", "schedule", "notify", "select_model_after")),
    ("Selection / grouping", ("select", "selection", "group", "ungroup", "align", "distribute")),
    ("BODY / transform", ("body", "transform", "rotate", "flip", "scale", "origin", "geometry", "move_current")),
    ("Pins", ("pin", "pins", "dock")),
    ("Properties / style", ("prop", "attr", "color", "style", "font", "line", "text", "combo", "check", "dbl", "set_")),
    ("Import / export / templates", ("import", "export", "mentor", "template", "load", "save", "json", "csv")),
]


def _category(name: str) -> str:
    lower = name.lower()
    for category, markers in CATEGORIES:
        if any(marker.lower() in lower for marker in markers):
            return category
    return "Other / utility"


def analyze() -> dict[str, object]:
    source = MAIN_WINDOW_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MainWindow")
    methods = [node for node in cls.body if isinstance(node, ast.FunctionDef)]
    by_category: dict[str, list[ast.FunctionDef]] = {}
    for method in methods:
        by_category.setdefault(_category(method.name), []).append(method)
    return {"source": source, "class": cls, "methods": methods, "by_category": by_category}


def write_markdown() -> None:
    data = analyze()
    cls: ast.ClassDef = data["class"]  # type: ignore[assignment]
    methods: list[ast.FunctionDef] = data["methods"]  # type: ignore[assignment]
    by_category: dict[str, list[ast.FunctionDef]] = data["by_category"]  # type: ignore[assignment]

    lines: list[str] = []
    lines.append("# MainWindow Method Inventory")
    lines.append("")
    lines.append("This static inventory is used to plan further extraction of `symbol_wizard/gui/main_window.py` without changing behaviour.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- File: `{MAIN_WINDOW_PATH.relative_to(ROOT)}`")
    lines.append(f"- `MainWindow` class span: lines **{cls.lineno}-{cls.end_lineno}**")
    lines.append(f"- Class size: **{cls.end_lineno - cls.lineno + 1}** lines")
    lines.append(f"- Methods: **{len(methods)}**")
    lines.append("")
    lines.append("## Categories")
    lines.append("")
    lines.append("| Category | Methods | Lines |")
    lines.append("|---|---:|---:|")
    for category in sorted(by_category):
        entries = by_category[category]
        line_count = sum(method.end_lineno - method.lineno + 1 for method in entries)
        lines.append(f"| {category} | {len(entries)} | {line_count} |")
    lines.append("")
    lines.append("## Method map")
    lines.append("")
    for category in sorted(by_category):
        lines.append(f"### {category}")
        lines.append("")
        for method in sorted(by_category[category], key=lambda m: m.lineno):
            line_count = method.end_lineno - method.lineno + 1
            lines.append(f"- `{method.name}` — lines {method.lineno}-{method.end_lineno} ({line_count} lines)")
        lines.append("")
    lines.append("## Suggested next extraction order")
    lines.append("")
    lines.append("1. Extract pure grid/coordinate helpers first; they are low risk and easy to test without Qt interaction.")
    lines.append("2. Extract BODY/transform and pin docking into service modules only after adding focused roundtrip tests.")
    lines.append("3. Extract property panel and selection code into GUI controllers after the legacy domain modules have been migrated.")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    write_markdown()
