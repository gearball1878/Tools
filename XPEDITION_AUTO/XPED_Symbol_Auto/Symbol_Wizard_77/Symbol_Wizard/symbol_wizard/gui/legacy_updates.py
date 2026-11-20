"""Apply the structured canonical Symbol Wizard update layer.

The historical patch journal has been reduced and split into a deterministic
shadow-class pipeline:

1. ``legacy_pipeline.functions/*`` defines the active functions by domain.
2. ``legacy_pipeline.pipeline`` composes the wrapper chain on shadow classes.
3. only ``CANONICAL_PATCH_TARGETS`` are copied once to the real runtime classes.

The real GUI classes are therefore not repeatedly patched by historical
intermediate implementations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .legacy_pipeline.targets import CANONICAL_PATCH_TARGETS

_PATCHED_CLASS_NAMES = (
    "MainWindow",
    "TemplateEditorDialog",
    "GraphicItem",
    "TextItem",
)

_DEFINITION_FILES = (
    Path(__file__).with_name("legacy_pipeline") / "functions" / "body_transform.py",
    Path(__file__).with_name("legacy_pipeline") / "functions" / "pin_grid.py",
    Path(__file__).with_name("legacy_pipeline") / "functions" / "selection_grouping.py",
    Path(__file__).with_name("legacy_pipeline") / "functions" / "scene_refresh.py",
    Path(__file__).with_name("legacy_pipeline") / "functions" / "properties_style.py",
    Path(__file__).with_name("legacy_pipeline") / "functions" / "template_editor.py",
    Path(__file__).with_name("legacy_pipeline") / "functions" / "graphics_items.py",
    Path(__file__).with_name("legacy_pipeline") / "functions" / "ui_actions.py",
    Path(__file__).with_name("legacy_pipeline") / "functions" / "import_export.py",
    Path(__file__).with_name("legacy_pipeline") / "functions" / "misc.py",
)

_COMPOSITION_FILES = (
    Path(__file__).with_name("legacy_pipeline") / "pipeline.py",
)


def _make_shadow_class(name: str, real_class: type[Any]) -> type[Any]:
    """Create a temporary subclass for composing the legacy pipeline."""
    return type(name, (real_class,), {"__module__": real_class.__module__})


def _legacy_capture(owner: type[Any], attr_name: str) -> Any | None:
    """Capture a method from a shadow class, preserving old patch semantics."""
    try:
        return getattr(owner, attr_name)
    except Exception:
        return None


def _legacy_assign(owner: type[Any], attr_name: str, value: Any) -> None:
    """Assign a method to a shadow class, preserving old patch semantics."""
    try:
        setattr(owner, attr_name, value)
    except Exception:
        pass


def _legacy_assign_expr(owner: type[Any], attr_name: str, factory: Any) -> None:
    """Evaluate and assign a shadow method/property under old try/except semantics."""
    try:
        setattr(owner, attr_name, factory())
    except Exception:
        pass


def _exec_pipeline_file(path: Path, globals_dict: dict[str, Any]) -> None:
    source = path.read_text(encoding="utf-8")
    exec(compile(source, str(path), "exec"), globals_dict)


def apply_legacy_updates(main_window_globals: dict[str, Any]) -> dict[str, list[str]]:
    """Apply canonical legacy updates and return copied attributes by class."""
    real_classes: dict[str, type[Any]] = {}
    shadow_classes: dict[str, type[Any]] = {}
    for class_name in _PATCHED_CLASS_NAMES:
        real_class = main_window_globals.get(class_name)
        if isinstance(real_class, type):
            real_classes[class_name] = real_class
            shadow_classes[class_name] = _make_shadow_class(class_name, real_class)

    original_globals = {name: main_window_globals.get(name) for name in real_classes}
    # Keep the native TemplateEditorDialog property renderer available for
    # compatibility fallbacks.  Some historical refresh wrappers were captured
    # from MainWindow and, when invoked for the Template Editor, clear the panel
    # before failing on MainWindow-only state.  The value intentionally remains
    # in the executed module globals because compatibility functions resolve it
    # at runtime through their __globals__ dictionary.
    template_editor_class = real_classes.get("TemplateEditorDialog")
    if template_editor_class is not None:
        main_window_globals.setdefault(
            "_template_editor_base_refresh_properties",
            getattr(template_editor_class, "refresh_properties", None),
        )
    helper_globals = {
        "_legacy_capture": _legacy_capture,
        "_legacy_assign": _legacy_assign,
        "_legacy_assign_expr": _legacy_assign_expr,
    }
    for class_name, shadow_class in shadow_classes.items():
        main_window_globals[class_name] = shadow_class
    main_window_globals.update(helper_globals)

    try:
        for path in (*_DEFINITION_FILES, *_COMPOSITION_FILES):
            _exec_pipeline_file(path, main_window_globals)
    finally:
        for class_name, original_value in original_globals.items():
            main_window_globals[class_name] = original_value
        for helper_name in helper_globals:
            main_window_globals.pop(helper_name, None)

    applied: dict[str, list[str]] = {name: [] for name in real_classes}
    for class_name, attr_name in CANONICAL_PATCH_TARGETS:
        real_class = real_classes.get(class_name)
        shadow_class = shadow_classes.get(class_name)
        if real_class is None or shadow_class is None:
            continue
        if not hasattr(shadow_class, attr_name):
            continue
        setattr(real_class, attr_name, getattr(shadow_class, attr_name))
        applied.setdefault(class_name, []).append(attr_name)

    return {class_name: sorted(set(attrs)) for class_name, attrs in applied.items() if attrs}
