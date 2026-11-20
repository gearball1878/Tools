"""QGraphicsItem/TextItem behaviour helpers.

Executed in the shared ``main_window.py`` global namespace by ``legacy_updates.apply_legacy_updates``.
"""

from __future__ import annotations

def _compat_1033(it):
    try:
        return (getattr(it, 'data', lambda *_: None)(0) == 'TEXT'
                and getattr(it, 'model', None) is not None
                and not bool(getattr(it.model, '_is_attribute_text', False)))
    except Exception:
        return False

def _compat_1039(self):
    try:
        return [it for it in self.scene.selectedItems() if _compat_1033(it)]
    except Exception:
        return []

def _compat_1042(self, factor):
    try:
        f = float(factor)
    except Exception:
        f = 1.0
    try:
        step = float(getattr(self.window, '_edit_grid_step', lambda: 0.1)())
    except Exception:
        step = 0.1
    cur = float(getattr(self.model, 'font_size_grid', 0.75) or 0.75)
    new = max(step, round((cur * f) / step) * step)
    self.model.font_size_grid = new
    try:
        self.apply_text_from_model()
    except Exception:
        self.apply_transform_from_model(); self.update()

def _compat_1048(it):
    try:
        return (getattr(it, 'data', lambda *_: None)(0) == 'TEXT'
                and getattr(it, 'model', None) is not None
                and not bool(getattr(it.model, '_is_attribute_text', False)))
    except Exception:
        return False

def _compat_1045(win, model):
    try:
        for it in win.scene.items():
            if _compat_1048(it) and getattr(it, 'model', None) is model:
                return it
    except Exception:
        pass
    return None

def _compat_1064(win, allow_active=True):
    items = []
    try:
        items = [it for it in win.scene.selectedItems() if _compat_1048(it)]
    except Exception:
        items = []
    if items:
        try:
            win._compat_1043 = getattr(items[0], 'model', None)
        except Exception:
            pass
        return items
    if allow_active:
        try:
            m = getattr(win, '_compat_1043', None)
            it = _compat_1045(win, m)
            if it is not None:
                return [it]
        except Exception:
            pass
    return []

def _compat_1060(win, items):
    for it in items:
        try:
            it.apply_text_from_model()
            it.setSelected(True)
            it.update()
        except Exception:
            try: it.update()
            except Exception: pass
    try:
        win.scene.update(); win.view.viewport().update()
    except Exception:
        pass
    try:
        win.refresh_properties()
    except Exception:
        pass

def _compat_1072(obj, seen=None):
    if seen is None:
        seen = set()
    oid = id(obj)
    if oid in seen:
        return
    seen.add(oid)
    try:
        d = getattr(obj, '__dict__', None)
        if isinstance(d, dict):
            for k in list(d.keys()):
                if k in ('_window_ref','window','scene','view','_qt_item','_graphics_item'):
                    try: delattr(obj, k)
                    except Exception: d.pop(k, None)
            for v in list(d.values()):
                _compat_1072(v, seen)
        elif isinstance(obj, dict):
            for v in list(obj.values()): _compat_1072(v, seen)
        elif isinstance(obj, (list, tuple, set)):
            for v in list(obj): _compat_1072(v, seen)
    except Exception:
        pass
