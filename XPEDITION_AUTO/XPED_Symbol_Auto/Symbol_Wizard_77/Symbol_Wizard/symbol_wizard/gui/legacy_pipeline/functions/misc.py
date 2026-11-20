"""Remaining compatibility helpers that do not yet have a stable domain home.

Executed in the shared ``main_window.py`` global namespace by ``legacy_updates.apply_legacy_updates``.
"""

from __future__ import annotations

def _compat_1238(x, y, cx, cy, deg):
    if abs(float(deg or 0.0)) < 1e-12:
        return float(x), float(y)
    a = math.radians(float(deg or 0.0))
    ca, sa = math.cos(a), math.sin(a)
    dx, dy = float(x) - float(cx), float(y) - float(cy)
    return cx + ca*dx - sa*dy, cy + sa*dx + ca*dy

def _compat_0314(self, v):
    try:
        v = round(float(v), 9)
        return 0.0 if abs(v) < 1e-9 else v
    except Exception:
        return v

def _compat_0322(A, B):
    a, b, c, d = A; e, f, g, h = B
    return (a*e + b*g, a*f + b*h, c*e + d*g, c*f + d*h)

def _compat_0321(M):
    a, b, c, d = M
    return math.degrees(math.atan2(c, a))

def _compat_0332(M):
    a, b, c, d = M
    return max(1e-9, math.hypot(a, c))

def _compat_0333(M):
    a, b, c, d = M
    return max(1e-9, math.hypot(b, d))

def _compat_0308(M, x, y):
    a, b, c, d = M
    return (a*float(x) + b*float(y), c*float(x) + d*float(y))

def _compat_0327(px, py, cx, cy, deg):
    a = math.radians(float(deg or 0.0)); ca, sa = math.cos(a), math.sin(a)
    dx, dy = float(px) - float(cx), float(py) - float(cy)
    return (cx + ca*dx - sa*dy, cy + sa*dx + ca*dy)

def _compat_0552(self, v):
    try:
        v = round(float(v), 9)
        return 0.0 if abs(v) < 1e-9 else v
    except Exception:
        return v

def _compat_0637(self, v):
    try:
        v = round(float(v), 9)
        return 0.0 if abs(v) < 1e-9 else v
    except Exception:
        return v

def _compat_0340(self, v):
    try:
        return self._clean_float(v)
    except Exception:
        try: return round(float(v), 6)
        except Exception: return v

def _compat_0390(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None, False
    first = vals[0]
    return first, all(v == first for v in vals)

def _compat_0575(self, model):
    for it in _compat_0567(self):
        try:
            if it.model is model:
                return it
        except Exception:
            pass
    return None

def _compat_0985(self, v):
    try:
        v = round(float(v), 9)
        return 0.0 if abs(v) < 1e-9 else v
    except Exception:
        return v

def _compat_1075(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)

def _compat_1138(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)

def _compat_1136(v, lo, hi):
    lo, hi = min(lo, hi), max(lo, hi)
    return max(lo, min(hi, v))

def _compat_1160(self, v):
    try:
        return self._clean_float(v)
    except Exception:
        try: return round(float(v), 9)
        except Exception: return v

def _compat_1172(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)

def _compat_1171(self, v):
    try:
        return self._clean_float(v)
    except Exception:
        try:
            v = round(float(v), 9)
            return 0.0 if abs(v) < 1e-9 else v
        except Exception:
            return v

def _compat_1183(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)

def _compat_1182(self, v):
    try:
        return self._clean_float(v)
    except Exception:
        try:
            v = round(float(v), 9)
            return 0.0 if abs(v) < 1e-9 else v
        except Exception:
            return v

def _compat_1185(self, x, y, old_box, new_box):
    ox, oy, ow, oh = old_box
    nx, ny, nw, nh = new_box
    ow = max(abs(float(ow)), 1e-12)
    oh = max(abs(float(oh)), 1e-12)
    sx = float(nw) / ow
    sy = float(nh) / oh
    return (
        _compat_1182(self, float(nx) + (float(x) - float(ox)) * sx),
        _compat_1182(self, float(ny) - (float(oy) - float(y)) * sy),
    )

def _compat_0720(self, v):
    try:
        v = round(float(v), 9)
        return 0.0 if abs(v) < 1e-9 else v
    except Exception:
        return v

def _compat_0737(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)

def _compat_0736(self, v):
    try:
        v = round(float(v), 9)
        return 0.0 if abs(v) < 1e-9 else v
    except Exception:
        return v

def _compat_0743(self, x, y, old_box, new_box):
    ox, oy, ow, oh = old_box
    nx, ny, nw, nh = new_box
    ow = max(abs(float(ow)), 1e-12)
    oh = max(abs(float(oh)), 1e-12)
    sx = float(nw) / ow
    sy = float(nh) / oh
    return (_compat_0736(self, float(nx) + (float(x) - float(ox)) * sx),
            _compat_0736(self, float(ny) - (float(oy) - float(y)) * sy))

def _compat_0758(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)

def _compat_0757(self, v):
    try:
        v = round(float(v), 9)
        return 0.0 if abs(v) < 1e-9 else v
    except Exception:
        return v

def _compat_0760(self, x, y, old_box, new_box):
    ox, oy, ow, oh = old_box
    nx, ny, nw, nh = new_box
    ow = max(abs(float(ow)), 1e-12)
    oh = max(abs(float(oh)), 1e-12)
    sx = float(nw) / ow
    sy = float(nh) / oh
    return (_compat_0757(self, float(nx) + (float(x) - float(ox)) * sx),
            _compat_0757(self, float(ny) - (float(oy) - float(y)) * sy))

def _compat_0738(v, step=None):
    try:
        x = float(v)
        if step and step > 0:
            x = round(x / step) * step
        x = round(x, 6)
        return 0.0 if abs(x) < 1e-9 else x
    except Exception:
        return v

def _compat_0777(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)

def _compat_0775(v):
    try:
        v = round(float(v), 9)
        return 0.0 if abs(v) < 1e-9 else v
    except Exception:
        return v

def _compat_0816(v):
    try:
        v = round(float(v), 9)
        return 0.0 if abs(v) < 1e-9 else v
    except Exception:
        return v

def _compat_0850(self, value):
    try:
        value = float(value)
        if abs(value - round(value)) < 1e-9:
            return float(round(value))
        return round(value, 6)
    except Exception:
        return value

def _compat_1196(win):
    try: return win.current_unit()
    except Exception:
        try: return win.unit
        except Exception: return None
