"""Mentor import/export, pinmux and template loading helpers.

Executed in the shared ``main_window.py`` global namespace by ``legacy_updates.apply_legacy_updates``.
"""

from __future__ import annotations

def _compat_0323(self, symbol):
    mode = getattr(symbol, 'origin', OriginMode.CENTER.value) or OriginMode.CENTER.value
    if mode not in _compat_0052:
        mode = OriginMode.CENTER.value; symbol.origin = mode
    for u in getattr(symbol, 'units', []) or []:
        _compat_0324(self, u, mode)

def _compat_0405(self, unit=None):
    u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    if u is None:
        return False
    try:
        return bool(_compat_0309(self, u))
    except Exception:
        try:
            return any(getattr(g, 'locked_to_body', False) for g in (getattr(u, 'graphics', []) or []))
        except Exception:
            return False

def _compat_1122(g):
    try:
        role = str(getattr(g, 'graphic_role', '') or '').lower()
        raw = str(getattr(g, 'mentor_raw', '') or '')
        return role == 'user_graphic' or raw == '__USER_GRAPHIC__'
    except Exception:
        return False

def _compat_0778(self):
    # Keep the original dialog/workflow, then normalize all imported pins in the
    # active library.  This is intentionally broad and harmless: already-clean
    # pins remain unchanged.
    result = _compat_0787(self) if _compat_0787 is not None else None
    try:
        for s in getattr(self.library, 'symbols', []) or []:
            for u in getattr(s, 'units', []) or []:
                _compat_0800(self, u, move_owned_text=False)
        self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table(); self.refresh_properties()
    except Exception:
        pass
    return result

def _compat_0806(self):
    result = _compat_0810(self) if _compat_0810 is not None else None
    try:
        for u in getattr(self.symbol, 'units', []) or []:
            for p in getattr(u, 'pins', []) or []:
                _compat_0803(p)
        self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()
    except Exception:
        pass
    return result
