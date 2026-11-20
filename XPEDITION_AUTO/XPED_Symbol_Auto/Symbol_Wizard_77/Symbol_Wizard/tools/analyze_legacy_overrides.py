from __future__ import annotations

"""Analyze the structured legacy compatibility pipeline.

The historical journal is no longer loaded at runtime.  This tool reports the
canonical target list plus the size of the structured active files under
``symbol_wizard/gui/legacy_pipeline``.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE_DIR = ROOT / "symbol_wizard" / "gui" / "legacy_pipeline"
TARGETS_PATH = PIPELINE_DIR / "targets.py"
DEFINITION_PATHS = tuple(
    path for path in sorted((PIPELINE_DIR / "functions").glob("*.py"))
    if path.name != "__init__.py"
)
PIPELINE_PATH = PIPELINE_DIR / "pipeline.py"
REPORT_PATH = ROOT / "docs" / "legacy_active_layer_analysis.md"
PATCHED_CLASS_NAMES = {"MainWindow", "TemplateEditorDialog", "GraphicItem", "TextItem"}


def _literal_targets(tree: ast.Module) -> list[tuple[str, str]]:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "CANONICAL_PATCH_TARGETS":
                    value = ast.literal_eval(node.value)
                    return [(str(cls), str(attr)) for cls, attr in value]
    return []


def _count_direct_class_assignments(tree: ast.Module) -> int:
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                    if target.value.id in PATCHED_CLASS_NAMES:
                        count += 1
    return count


def _count_helper_calls(tree: ast.Module, helper_name: str) -> int:
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == helper_name:
            count += 1
    return count


def analyze() -> dict[str, object]:
    targets_source = TARGETS_PATH.read_text(encoding="utf-8")
    definition_sources = [(path, path.read_text(encoding="utf-8")) for path in DEFINITION_PATHS]
    pipeline_source = PIPELINE_PATH.read_text(encoding="utf-8")

    targets_tree = ast.parse(targets_source)
    definition_trees = [(path, ast.parse(source)) for path, source in definition_sources]
    pipeline_tree = ast.parse(pipeline_source)
    targets = _literal_targets(targets_tree)

    return {
        "targets_lines": len(targets_source.splitlines()),
        "definitions_lines": sum(len(source.splitlines()) for _, source in definition_sources),
        "definition_files": [(str(path.relative_to(ROOT)), len(source.splitlines())) for path, source in definition_sources],
        "pipeline_lines": len(pipeline_source.splitlines()),
        "targets": targets,
        "definition_functions": sum(1 for _, tree in definition_trees for node in tree.body if isinstance(node, ast.FunctionDef)),
        "pipeline_functions": sum(1 for node in pipeline_tree.body if isinstance(node, ast.FunctionDef)),
        "direct_class_assignments": _count_direct_class_assignments(pipeline_tree),
        "helper_assignments": _count_helper_calls(pipeline_tree, "_legacy_assign"),
        "helper_captures": _count_helper_calls(pipeline_tree, "_legacy_capture"),
    }


def write_markdown() -> None:
    data = analyze()
    targets: list[tuple[str, str]] = data["targets"]  # type: ignore[assignment]
    by_class: dict[str, list[str]] = {}
    for class_name, attr_name in targets:
        by_class.setdefault(class_name, []).append(attr_name)

    lines: list[str] = []
    lines.append("# Legacy active layer analysis")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Target manifest: `{TARGETS_PATH.relative_to(ROOT)}`")
    lines.append("- Function definitions:")
    for path, line_count in data["definition_files"]:  # type: ignore[index]
        lines.append(f"  - `{path}`: **{line_count}** lines")
    lines.append(f"- Shadow composition pipeline: `{PIPELINE_PATH.relative_to(ROOT)}`")
    lines.append(f"- Target manifest lines: **{data['targets_lines']}**")
    lines.append(f"- Total definition lines: **{data['definitions_lines']}**")
    lines.append(f"- Pipeline lines: **{data['pipeline_lines']}**")
    lines.append(f"- Active function definitions: **{data['definition_functions']}**")
    lines.append(f"- Pipeline helper assignments: **{data['helper_assignments']}**")
    lines.append(f"- Pipeline helper captures: **{data['helper_captures']}**")
    lines.append(f"- Remaining direct shadow assignments: **{data['direct_class_assignments']}**")
    lines.append(f"- Canonical real-class targets: **{len(targets)}**")
    lines.append("")
    lines.append("## Targets by class")
    lines.append("")
    for class_name in sorted(by_class):
        attrs = sorted(set(by_class[class_name]))
        lines.append(f"### {class_name}")
        lines.append("")
        for attr in attrs:
            lines.append(f"- `{attr}`")
        lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    write_markdown()
