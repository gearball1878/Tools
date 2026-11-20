"""Apply canonical updates for `view.py` classes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_PATCHED_CLASS_NAMES = ('SymbolView',)

CANONICAL_TARGETS = (
    ('SymbolView', '__init__'),
    ('SymbolView', '_rubber_band_changed'),
    ('SymbolView', 'drawForeground'),
    ('SymbolView', 'keyPressEvent'),
    ('SymbolView', 'mouseMoveEvent'),
    ('SymbolView', 'mousePressEvent'),
    ('SymbolView', 'mouseReleaseEvent'),
)


def _make_shadow_class(name: str, real_class: type[Any]) -> type[Any]:
    return type(name, (real_class,), {"__module__": real_class.__module__})


def _exec_update_source(module_globals: dict[str, Any]) -> None:
    path = Path(__file__).with_name('view_update_code.py')
    source = path.read_text(encoding="utf-8")
    exec(compile(source, str(path), "exec"), module_globals)


def apply_view_updates(module_globals: dict[str, Any]) -> dict[str, list[str]]:
    real_classes: dict[str, type[Any]] = {}
    shadow_classes: dict[str, type[Any]] = {}
    for class_name in _PATCHED_CLASS_NAMES:
        real_class = module_globals.get(class_name)
        if isinstance(real_class, type):
            real_classes[class_name] = real_class
            shadow_classes[class_name] = _make_shadow_class(class_name, real_class)

    original_globals = {name: module_globals.get(name) for name in real_classes}
    for class_name, shadow_class in shadow_classes.items():
        module_globals[class_name] = shadow_class

    try:
        _exec_update_source(module_globals)
    finally:
        for class_name, original_value in original_globals.items():
            module_globals[class_name] = original_value

    applied: dict[str, list[str]] = {name: [] for name in real_classes}
    for class_name, attr_name in CANONICAL_TARGETS:
        real_class = real_classes.get(class_name)
        shadow_class = shadow_classes.get(class_name)
        if real_class is None or shadow_class is None or not hasattr(shadow_class, attr_name):
            continue
        setattr(real_class, attr_name, getattr(shadow_class, attr_name))
        applied.setdefault(class_name, []).append(attr_name)

    return {class_name: sorted(set(attrs)) for class_name, attrs in applied.items() if attrs}
