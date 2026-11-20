"""Apply canonical QGraphics item method updates.

The original project appended many historical item patches directly to
``graphics/items.py``.  This module composes those updates on temporary shadow
classes and then copies only the final canonical method for each target back to
the real runtime classes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer

_PATCHED_CLASS_NAMES = (
    "TransformMixin",
    "BodyItem",
    "PinItem",
    "TextItem",
    "GraphicItem",
)

ITEM_CANONICAL_TARGETS = (
    ('TransformMixin', 'itemChange'),
    ('BodyItem', 'apply_transform_from_model'),
    ('BodyItem', 'hoverMoveEvent'),
    ('BodyItem', 'mouseMoveEvent'),
    ('BodyItem', 'mousePressEvent'),
    ('BodyItem', 'mouseReleaseEvent'),
    ('BodyItem', 'paint'),
    ('PinItem', 'paint'),
    ('PinItem', 'scale_by'),
    ('PinItem', 'scale_selected'),
    ('PinItem', 'shape'),
    ('PinItem', 'update_model_pos'),
    ('TextItem', 'focusOutEvent'),
    ('TextItem', 'keyPressEvent'),
    ('TextItem', 'paint'),
    ('TextItem', 'shape'),
    ('GraphicItem', '__init__'),
    ('GraphicItem', '_handles'),
    ('GraphicItem', 'apply_transform_from_model'),
    ('GraphicItem', 'handle_size_factor'),
    ('GraphicItem', 'hoverMoveEvent'),
    ('GraphicItem', 'mouseMoveEvent'),
    ('GraphicItem', 'mousePressEvent'),
    ('GraphicItem', 'mouseReleaseEvent'),
    ('GraphicItem', 'paint'),
    ('GraphicItem', 'rotate_handle_factor'),
    ('GraphicItem', 'scale_by'),
    ('GraphicItem', 'scale_selected'),
    ('GraphicItem', 'update'),
    ('GraphicItem', 'update_model_pos'),
)


def _left_plain_click(event: Any) -> bool:
    try:
        if event.button() != Qt.LeftButton:
            return False
        return not bool(event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier))
    except Exception:
        return False


def _single_select_before_mouse_press(item: Any, event: Any) -> None:
    """Collapse a current multi-selection to the clicked item.

    Historical item mousePress handlers often keep the existing multi-selection
    alive until the user manually deselects everything.  This wrapper is
    installed after the canonical compatibility methods, so it is the final
    selection behaviour for BODY, PIN, TEXT and GRAPHIC items.
    """
    try:
        if not _left_plain_click(event):
            return
        scene = item.scene()
        if scene is None:
            return
        selected = list(scene.selectedItems())
        if len(selected) <= 1:
            return
        scene.blockSignals(True)
        try:
            for other in selected:
                if other is not item:
                    try:
                        other.setSelected(False)
                    except Exception:
                        pass
            try:
                item.setSelected(True)
            except Exception:
                pass
        finally:
            scene.blockSignals(False)
        win = getattr(item, 'window', None) or getattr(scene, 'window', None)
        if win is not None and hasattr(win, 'refresh_properties'):
            QTimer.singleShot(0, win.refresh_properties)
    except Exception:
        pass


def _install_single_select_mouse_wrappers(real_classes: dict[str, type[Any]]) -> None:
    for class_name in ('BodyItem', 'PinItem', 'TextItem', 'GraphicItem'):
        cls = real_classes.get(class_name)
        if cls is None or not hasattr(cls, 'mousePressEvent'):
            continue
        previous = getattr(cls, 'mousePressEvent')
        if getattr(previous, '_symbol_wizard_single_select_wrapper', False):
            continue
        def mouse_press(self, event, __prev=previous):
            _single_select_before_mouse_press(self, event)
            return __prev(self, event)
        mouse_press._symbol_wizard_single_select_wrapper = True
        setattr(cls, 'mousePressEvent', mouse_press)


def _make_shadow_class(name: str, real_class: type[Any]) -> type[Any]:
    return type(name, (real_class,), {"__module__": real_class.__module__})


def _exec_item_update_source(items_globals: dict[str, Any]) -> None:
    path = Path(__file__).with_name("item_update_code.py")
    source = path.read_text(encoding="utf-8")
    exec(compile(source, str(path), "exec"), items_globals)


def apply_item_updates(items_globals: dict[str, Any]) -> dict[str, list[str]]:
    """Apply final item method implementations once per class/method."""
    real_classes: dict[str, type[Any]] = {}
    shadow_classes: dict[str, type[Any]] = {}
    for class_name in _PATCHED_CLASS_NAMES:
        real_class = items_globals.get(class_name)
        if isinstance(real_class, type):
            real_classes[class_name] = real_class
            shadow_classes[class_name] = _make_shadow_class(class_name, real_class)

    original_globals = {name: items_globals.get(name) for name in real_classes}
    for class_name, shadow_class in shadow_classes.items():
        items_globals[class_name] = shadow_class

    try:
        _exec_item_update_source(items_globals)
    finally:
        for class_name, original_value in original_globals.items():
            items_globals[class_name] = original_value

    applied: dict[str, list[str]] = {name: [] for name in real_classes}
    for class_name, attr_name in ITEM_CANONICAL_TARGETS:
        real_class = real_classes.get(class_name)
        shadow_class = shadow_classes.get(class_name)
        if real_class is None or shadow_class is None or not hasattr(shadow_class, attr_name):
            continue
        setattr(real_class, attr_name, getattr(shadow_class, attr_name))
        applied.setdefault(class_name, []).append(attr_name)

    _install_single_select_mouse_wrappers(real_classes)

    return {class_name: sorted(set(attrs)) for class_name, attrs in applied.items()}
