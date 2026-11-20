"""BODY geometry, transform, resize, origin, rotation and scaling helpers.

Executed in the shared ``main_window.py`` global namespace by ``legacy_updates.apply_legacy_updates``.
"""

from __future__ import annotations

def _compat_1236(self, gr):
    try:
        if getattr(self, 'is_template_editor', False):
            return True
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        marker = str(getattr(gr, 'mentor_raw', '') or '')
        return bool(getattr(gr, 'locked_to_body', False) or role in ('body','template_body','imported_body') or marker != '__USER_GRAPHIC__' and role != 'user_graphic')
    except Exception:
        return False

def _compat_1235(self, gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    shape = str(getattr(gr, 'shape', '') or '')
    if shape in ('line', 'arc'):
        pts = [(x, y), (x+w, y-h)]
        cx, cy = x + w/2.0, y - h/2.0
        # Include quadratic control point / curve apex so arc BODY bounds are not too small.
        ctrl_x = getattr(gr, 'ctrl_x', None); ctrl_y = getattr(gr, 'ctrl_y', None)
        if ctrl_x is not None and ctrl_y is not None:
            pts.append((x + float(ctrl_x), y - float(ctrl_y)))
        else:
            cr = float(getattr(gr, 'curve_radius', 0.0) or 0.0)
            if abs(cr) > 1e-12:
                pts.append((x + w/2.0, y - h/2.0 + cr))
    else:
        x2 = x + w; y2 = y - h
        pts = [(x, y), (x2, y), (x2, y2), (x, y2)]
        cx, cy = x + w/2.0, y - h/2.0
    rot = float(getattr(gr, 'rotation', 0.0) or 0.0)
    sx = float(getattr(gr, 'scale_x', 1.0) or 1.0)
    sy = float(getattr(gr, 'scale_y', 1.0) or 1.0)
    out = []
    for px, py in pts:
        # Approximate item scale around center in model coordinates.
        qx = cx + (px - cx) * sx
        qy = cy + (py - cy) * sy
        out.append(_compat_1238(qx, qy, cx, cy, rot))
    return out

def _compat_1230(self, unit=None):
    u = unit or self.current_unit
    return [g for g in (getattr(u, 'graphics', []) or []) if _compat_1236(self, g)]

def _compat_1231(self, unit=None):
    u = unit or self.current_unit
    gs = _compat_1230(self, u)
    if not gs:
        return None
    pts = []
    for gr in gs:
        pts.extend(_compat_1235(self, gr))
    if not pts:
        return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    minx, maxx = min(xs), max(xs); miny, maxy = min(ys), max(ys)
    if maxx - minx < 1e-9 or maxy - miny < 1e-9:
        return None
    return (minx, maxy, maxx - minx, maxy - miny)  # x,y,width,height with y=top

def _compat_1239(self, unit=None):
    u = unit or self.current_unit
    b = getattr(u, 'body', None)
    if b is None:
        return
    bounds = _compat_1231(self, u)
    if bounds is None:
        return
    x, y, w, h = bounds
    b.x = self._clean_float(x) if hasattr(self, '_clean_float') else x
    b.y = self._clean_float(y) if hasattr(self, '_clean_float') else y
    b.width = self._clean_float(max(0.01, w)) if hasattr(self, '_clean_float') else max(0.01, w)
    b.height = self._clean_float(max(0.01, h)) if hasattr(self, '_clean_float') else max(0.01, h)
    # The logical BODY rotation is represented by actual graphics; keep proxy angle neutral.
    # Internally-created <NONE> bodies have no body graphics and keep their own rotation.
    try:
        if _compat_1230(self, u):
            b.rotation = 0.0
    except Exception:
        pass

def _compat_1233(self, unit=None):
    u = unit or self.current_unit
    _compat_1239(self, u)
    b = u.body
    mode = getattr(self.symbol, 'origin', OriginMode.CENTER.value)
    ax, ay = self.body_anchor_point(b, mode)
    base = {
        'pivot': (float(ax), float(ay)), 'anchor': (float(ax), float(ay)), 'origin_mode': mode,
        'has_body_graphics': bool(_compat_1230(self, u)),
        'body': {'x': float(b.x), 'y': float(b.y), 'w': float(b.width), 'h': float(b.height),
                 'rot': float(getattr(b, 'rotation', 0.0) or 0.0),
                 'sx': float(getattr(b, 'scale_x', 1.0) or 1.0), 'sy': float(getattr(b, 'scale_y', 1.0) or 1.0)},
        'pins': [], 'texts': [], 'body_attrs': [], 'graphics': []
    }
    for p in getattr(u, 'pins', []) or []:
        pd = {'obj': p, 'x': float(p.x), 'y': float(p.y), 'length': float(getattr(p, 'length', 1.0) or 1.0),
              'rot': float(getattr(p, 'rotation', 0.0) or 0.0), 'label': None, 'number': None, 'attrs': [],
              'nfs': float(getattr(getattr(p, 'number_font', None), 'size_grid', 0.45) or 0.45),
              'lfs': float(getattr(getattr(p, 'label_font', None), 'size_grid', 0.55) or 0.55)}
        if getattr(p, 'label_x', None) is not None and getattr(p, 'label_y', None) is not None:
            pd['label'] = (float(p.label_x), float(p.label_y))
        if getattr(p, 'number_x', None) is not None and getattr(p, 'number_y', None) is not None:
            pd['number'] = (float(p.number_x), float(p.number_y))
        for key, tm in (getattr(p, 'attribute_texts', {}) or {}).items():
            try: pd['attrs'].append((key, tm, float(tm.x), float(tm.y), float(getattr(tm, 'rotation', 0.0) or 0.0), float(getattr(tm, 'font_size_grid', 0.55) or 0.55)))
            except Exception: pass
        base['pins'].append(pd)
    for t in getattr(u, 'texts', []) or []:
        try: base['texts'].append({'obj': t, 'x': float(t.x), 'y': float(t.y), 'rot': float(getattr(t, 'rotation', 0.0) or 0.0), 'font': float(getattr(t, 'font_size_grid', .75) or .75)})
        except Exception: pass
    for key, t in (getattr(b, 'attribute_texts', {}) or {}).items():
        try: base['body_attrs'].append({'key': key, 'obj': t, 'x': float(t.x), 'y': float(t.y), 'rot': float(getattr(t, 'rotation', 0.0) or 0.0), 'font': float(getattr(t, 'font_size_grid', .75) or .75)})
        except Exception: pass
    for gr in getattr(u, 'graphics', []) or []:
        try:
            base['graphics'].append({'obj': gr, 'x': float(gr.x), 'y': float(gr.y), 'w': float(getattr(gr,'w',0.0) or 0.0), 'h': float(getattr(gr,'h',0.0) or 0.0),
                'rot': float(getattr(gr, 'rotation', 0.0) or 0.0), 'sx': float(getattr(gr, 'scale_x', 1.0) or 1.0), 'sy': float(getattr(gr, 'scale_y', 1.0) or 1.0),
                'ctrl_x': getattr(gr, 'ctrl_x', None), 'ctrl_y': getattr(gr, 'ctrl_y', None), 'curve_radius': float(getattr(gr, 'curve_radius', 0.0) or 0.0)})
        except Exception: pass
    u._body_group_transform = {'base': base, 'M': (1.0, 0.0, 0.0, 1.0)}
    return u._body_group_transform

def _compat_1229(self, st, refresh=True):
    base = st['base']; M = st.get('M', (1.0,0.0,0.0,1.0)); ax, ay = base['anchor']
    def clean(v):
        try: return self._clean_float(v)
        except Exception: return float(v)
    def app(x, y):
        a,b,c,d = M; dx, dy = float(x)-ax, float(y)-ay
        return clean(ax + a*dx + b*dy), clean(ay + c*dx + d*dy)
    def linear_vec(x, y):
        a,b,c,d = M
        return clean(a*float(x) + b*float(y)), clean(c*float(x) + d*float(y))
    def angle():
        try: return self._mat_col_angle(M)
        except Exception:
            a,b,c,d = M; return math.degrees(math.atan2(c,a))
    def sx_abs():
        a,b,c,d = M; return max(1e-9, math.hypot(a,c))
    def sy_abs():
        a,b,c,d = M; return max(1e-9, math.hypot(b,d))
    u = self.current_unit; b = u.body
    sxv, syv = sx_abs(), sy_abs(); font_factor = max(0.1, (abs(sxv)+abs(syv))/2.0)
    # Transform real graphics first.  For imported/template BODYs these graphics
    # ARE the visible BODY; afterwards the logical BODY bounds are resynced from them.
    for gd in base.get('graphics', []):
        gr = gd['obj']
        gr.x, gr.y = app(gd['x'], gd['y'])
        gr.w, gr.h = linear_vec(gd['w'], gd['h'])
        gr.rotation = clean((gd.get('rot',0.0) + angle()) % 360.0)
        gr.scale_x = gd.get('sx', 1.0); gr.scale_y = gd.get('sy', 1.0)
        if gd.get('ctrl_x') is not None and gd.get('ctrl_y') is not None:
            gr.ctrl_x, gr.ctrl_y = linear_vec(gd['ctrl_x'], gd['ctrl_y'])
        try: gr.curve_radius = clean(gd.get('curve_radius', 0.0) * font_factor)
        except Exception: pass
    # Internal <NONE> body with no body graphics is transformed as its own rectangle.
    if not base.get('has_body_graphics'):
        bs = base['body']
        cx, cy = bs['x'] + bs['w']/2.0, bs['y'] - bs['h']/2.0
        ncx, ncy = app(cx, cy)
        b.width = clean(max(0.01, bs['w'] * sxv)); b.height = clean(max(0.01, bs['h'] * syv))
        b.rotation = clean((bs.get('rot', 0.0) + angle()) % 360.0)
        try: self._set_body_center_grid(b, ncx, ncy)
        except Exception:
            b.x = ncx - b.width/2.0; b.y = ncy + b.height/2.0
    else:
        _compat_1239(self, u)
    # Attached objects follow the same anchor-local mapping.  Text glyphs remain
    # readable: positions move rigidly, rotations are not mirrored/rotated.
    for pd in base.get('pins', []):
        p = pd['obj']; p.x, p.y = app(pd['x'], pd['y'])
        p.rotation = clean((pd.get('rot',0.0) + angle()) % 360.0)
        p.length = clean(max(0.1, pd.get('length',1.0) * font_factor))
        if pd.get('label') is not None: p.label_x, p.label_y = app(*pd['label'])
        if pd.get('number') is not None: p.number_x, p.number_y = app(*pd['number'])
        try: p.number_font.size_grid = max(0.1, clean(pd.get('nfs', .45) * font_factor))
        except Exception: pass
        try: p.label_font.size_grid = max(0.1, clean(pd.get('lfs', .55) * font_factor))
        except Exception: pass
        for key, tm, tx, ty, trot, tf in pd.get('attrs', []):
            try:
                tm.x, tm.y = app(tx, ty); tm.rotation = trot; tm.font_size_grid = max(0.1, clean(tf * font_factor))
            except Exception: pass
    for td in base.get('texts', []):
        t = td['obj']; t.x, t.y = app(td['x'], td['y']); t.rotation = td.get('rot', 0.0); t.font_size_grid = max(0.1, clean(td.get('font', .75) * font_factor))
    for td in base.get('body_attrs', []):
        t = td['obj']; t.x, t.y = app(td['x'], td['y']); t.rotation = td.get('rot', 0.0); t.font_size_grid = max(0.1, clean(td.get('font', .75) * font_factor))
    try: self._invalidate_body_group_transform_cache(None) if False else None
    except Exception: pass
    if refresh:
        try: self.update_current_unit_canvas_positions()
        except Exception: self.rebuild_scene()
        try: self.rebuild_tree(); self.rebuild_pin_table()
        except Exception: pass

def _compat_1232(self, unit=None):
    u = unit or self.current_unit
    st = getattr(u, '_body_group_transform', None)
    if not isinstance(st, dict) or 'base' not in st or 'M' not in st:
        st = _compat_1233(self, u)
    else:
        try:
            if st['base'].get('origin_mode') != getattr(self.symbol, 'origin', OriginMode.CENTER.value):
                st = _compat_1233(self, u)
        except Exception:
            st = _compat_1233(self, u)
    return st

def _compat_1240(self, op, value=None, refresh=True):
    st = _compat_1232(self, self.current_unit)
    M = st.get('M', (1.0,0.0,0.0,1.0))
    if op == 'rotate':
        deg = round(float(value or 0.0) / 90.0) * 90.0
        if abs(deg) < 1e-9: return
        a = math.radians(deg); Op = (math.cos(a), -math.sin(a), math.sin(a), math.cos(a))
    elif op in ('scale','scale_x_to','scale_y_to'):
        cur_w = max(1e-9, float(getattr(self.current_unit.body, 'width', 1.0) or 1.0))
        cur_h = max(1e-9, float(getattr(self.current_unit.body, 'height', 1.0) or 1.0))
        try: snapv = self._snap_to_edit_grid
        except Exception: snapv = lambda v, mn=0.01: max(mn, float(v))
        if op == 'scale_x_to': sx, sy = snapv(float(value), 0.01) / cur_w, 1.0
        elif op == 'scale_y_to': sx, sy = 1.0, snapv(float(value), 0.01) / cur_h
        else:
            f = float(value or 1.0); sx, sy = snapv(cur_w*f, 0.01)/cur_w, snapv(cur_h*f, 0.01)/cur_h
        Op = (sx, 0.0, 0.0, sy)
    elif op == 'flip_h':
        Op = (-1.0, 0.0, 0.0, 1.0)
    elif op == 'flip_v':
        Op = (1.0, 0.0, 0.0, -1.0)
    else:
        return
    try: st['M'] = self._mat_mul(Op, M)
    except Exception:
        a,b,c,d = Op; e,f,g,h = M; st['M'] = (a*e+b*g, a*f+b*h, c*e+d*g, c*f+d*h)
    _compat_1229(self, st, refresh=refresh)

def _compat_0319(self, gr):
    try:
        if getattr(self, 'is_template_editor', False):
            return True
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        raw = str(getattr(gr, 'mentor_raw', '') or '')
        if getattr(gr, 'locked_to_body', False):
            return True
        if role in ('body', 'template_body', 'imported_body'):
            return True
        if role == 'user_graphic' or raw == '__USER_GRAPHIC__':
            return False
        # Mentor/imported graphics without explicit user marker are BODY artwork.
        return True
    except Exception:
        return False

def _compat_0309(self, unit=None):
    u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    return [g for g in (getattr(u, 'graphics', []) or []) if _compat_0319(self, g)] if u else []

def _compat_0316(self, gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    shape = str(getattr(gr, 'shape', '') or '')
    if shape in ('line', 'arc'):
        pts = [(x, y), (x + w, y - h)]
        cx, cy = x + w / 2.0, y - h / 2.0
        ctrl_x = getattr(gr, 'ctrl_x', None); ctrl_y = getattr(gr, 'ctrl_y', None)
        if ctrl_x is not None and ctrl_y is not None:
            try: pts.append((x + float(ctrl_x), y - float(ctrl_y)))
            except Exception: pass
        else:
            cr = float(getattr(gr, 'curve_radius', 0.0) or 0.0)
            if abs(cr) > 1e-12:
                pts.append((x + w / 2.0, y - h / 2.0 + cr))
    else:
        pts = [(x, y), (x + w, y), (x + w, y - h), (x, y - h)]
        cx, cy = x + w / 2.0, y - h / 2.0
    sx = float(getattr(gr, 'scale_x', 1.0) or 1.0)
    sy = float(getattr(gr, 'scale_y', 1.0) or 1.0)
    rot = float(getattr(gr, 'rotation', 0.0) or 0.0)
    out = []
    for px, py in pts:
        qx = cx + (px - cx) * sx
        qy = cy + (py - cy) * sy
        out.append(_compat_0327(qx, qy, cx, cy, rot))
    return out

def _compat_0310(self, unit=None):
    pts = []
    for gr in _compat_0309(self, unit):
        pts.extend(_compat_0316(self, gr))
    if not pts:
        return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    minx, maxx = min(xs), max(xs); miny, maxy = min(ys), max(ys)
    if maxx - minx < 1e-9 or maxy - miny < 1e-9:
        return None
    return (minx, maxy, maxx - minx, maxy - miny)

def _compat_0334(self, unit=None):
    u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    b = getattr(u, 'body', None) if u else None
    if b is None:
        return
    bounds = _compat_0310(self, u)
    if bounds is None:
        return
    x, y, w, h = bounds
    b.x = _compat_0314(self, x); b.y = _compat_0314(self, y)
    b.width = _compat_0314(self, max(0.01, w)); b.height = _compat_0314(self, max(0.01, h))
    # Imported/template BODY rotation lives in graphics, not in a proxy body box.
    b.rotation = 0.0

def _compat_0306(self, body, mode):
    mode = mode if mode in _compat_0052 else OriginMode.CENTER.value
    x = float(getattr(body, 'x', 0.0) or 0.0)
    y = float(getattr(body, 'y', 0.0) or 0.0)
    w = float(getattr(body, 'width', 0.0) or 0.0)
    h = float(getattr(body, 'height', 0.0) or 0.0)
    if mode == OriginMode.BOTTOM_LEFT.value:
        return x, y - h
    if mode == OriginMode.BOTTOM_RIGHT.value:
        return x + w, y - h
    if mode == OriginMode.TOP_LEFT.value:
        return x, y
    if mode == OriginMode.TOP_RIGHT.value:
        return x + w, y
    return x + w/2.0, y - h/2.0

def _compat_0330(self, unit, dx, dy):
    b = getattr(unit, 'body', None)
    if b is not None:
        b.x = _compat_0314(self, float(b.x) + dx); b.y = _compat_0314(self, float(b.y) + dy)
    for gr in getattr(unit, 'graphics', []) or []:
        gr.x = _compat_0314(self, float(gr.x) + dx); gr.y = _compat_0314(self, float(gr.y) + dy)
    for p in getattr(unit, 'pins', []) or []:
        p.x = _compat_0314(self, float(p.x) + dx); p.y = _compat_0314(self, float(p.y) + dy)
        if getattr(p, 'label_x', None) is not None: p.label_x = _compat_0314(self, float(p.label_x) + dx)
        if getattr(p, 'label_y', None) is not None: p.label_y = _compat_0314(self, float(p.label_y) + dy)
        if getattr(p, 'number_x', None) is not None: p.number_x = _compat_0314(self, float(p.number_x) + dx)
        if getattr(p, 'number_y', None) is not None: p.number_y = _compat_0314(self, float(p.number_y) + dy)
        for tm in (getattr(p, 'attribute_texts', {}) or {}).values():
            _compat_0329(tm, dx, dy)
    for tm in getattr(unit, 'texts', []) or []:
        _compat_0329(tm, dx, dy)
    for tm in (getattr(getattr(unit, 'body', None), 'attribute_texts', {}) or {}).values():
        _compat_0329(tm, dx, dy)
    try: _compat_0334(self, unit)
    except Exception: pass
    try:
        if hasattr(unit, '_body_group_transform'):
            delattr(unit, '_body_group_transform')
    except Exception:
        pass

def _compat_0324(self, unit, mode):
    # Move the selected BODY anchor to canvas origin. Only BODY graphics define
    # the body bounds; attached objects are shifted by the exact same delta.
    _compat_0334(self, unit)
    b = getattr(unit, 'body', None)
    if b is None:
        return
    ax, ay = _compat_0306(self, b, mode)
    if abs(ax) > 1e-9 or abs(ay) > 1e-9:
        _compat_0330(self, unit, -ax, -ay)
    _compat_0334(self, unit)

def _compat_0311(self, unit=None):
    u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    st = getattr(u, '_body_group_transform', None)
    mode = getattr(self.symbol, 'origin', OriginMode.CENTER.value)
    if not isinstance(st, dict) or 'base' not in st or 'M' not in st or st['base'].get('unit_id') != id(u) or st['base'].get('origin_mode') != mode:
        st = _compat_0313(self, u)
    return st

def _compat_0307(self, st, refresh=True):
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    if u is None:
        return
    base = st['base']; M = st.get('M', (1.0, 0.0, 0.0, 1.0))
    clean = lambda v: _compat_0314(self, v)
    sxv, syv = _compat_0332(M), _compat_0333(M)
    font_factor = max(0.1, (abs(sxv) + abs(syv)) / 2.0)
    angle = _compat_0321(M)

    # Real graphics first. For imported/templates, BODY is the body graphics.
    for gd in base.get('graphics', []):
        _compat_0317(self, gd, M)

    b = u.body
    if not base.get('has_body_graphics'):
        # Internal <NONE> body as a real body object.
        bs = base['body']
        cx, cy = bs['x'] + bs['w']/2.0, bs['y'] - bs['h']/2.0
        ncx, ncy = _compat_0308(M, cx, cy)
        b.width = clean(max(0.01, abs(bs['w']) * sxv)); b.height = clean(max(0.01, abs(bs['h']) * syv))
        b.x = clean(ncx - b.width / 2.0); b.y = clean(ncy + b.height / 2.0)
        b.rotation = clean((bs.get('rot', 0.0) + angle) % 360.0)
    else:
        _compat_0334(self, u)

    # Attached pins/text/attrs follow the same rigid group matrix around (0,0).
    for pd in base.get('pins', []):
        p = pd['obj']; nx, ny = _compat_0308(M, pd['x'], pd['y'])
        p.x, p.y = clean(nx), clean(ny)
        # Pin line orientation follows the symbol; pin text remains readable.
        p.rotation = clean((pd.get('rot', 0.0) + angle) % 360.0)
        p.length = clean(max(0.1, float(pd.get('length', 1.0) or 1.0) * font_factor))
        if pd.get('label') is not None:
            lx, ly = _compat_0308(M, *pd['label']); p.label_x, p.label_y = clean(lx), clean(ly)
        if pd.get('number') is not None:
            nx, ny = _compat_0308(M, *pd['number']); p.number_x, p.number_y = clean(nx), clean(ny)
        try: p.number_font.size_grid = max(0.1, clean(pd.get('nfs', .45) * font_factor))
        except Exception: pass
        try: p.label_font.size_grid = max(0.1, clean(pd.get('lfs', .55) * font_factor))
        except Exception: pass
        for key, tm, tx, ty, trot, tf in pd.get('attrs', []):
            try:
                qx, qy = _compat_0308(M, tx, ty); tm.x, tm.y = clean(qx), clean(qy)
                tm.rotation = trot  # readable: do not rotate/mirror glyphs
                tm.scale_x = 1.0; tm.scale_y = 1.0
                tm.font_size_grid = max(0.1, clean(tf * font_factor))
            except Exception:
                pass
    for td in base.get('texts', []):
        t = td['obj']; qx, qy = _compat_0308(M, td['x'], td['y'])
        t.x, t.y = clean(qx), clean(qy); t.rotation = td.get('rot', 0.0); t.scale_x = 1.0; t.scale_y = 1.0
        t.font_size_grid = max(0.1, clean(td.get('font', .75) * font_factor))
    for td in base.get('body_attrs', []):
        t = td['obj']; qx, qy = _compat_0308(M, td['x'], td['y'])
        t.x, t.y = clean(qx), clean(qy); t.rotation = td.get('rot', 0.0); t.scale_x = 1.0; t.scale_y = 1.0
        t.font_size_grid = max(0.1, clean(td.get('font', .75) * font_factor))

    if refresh:
        try:
            self.update_current_unit_canvas_positions()
        except Exception:
            try: self.rebuild_scene()
            except Exception: pass
        try:
            self.rebuild_tree(); self.rebuild_pin_table()
        except Exception:
            pass

def _compat_0335(self, op, value=None, refresh=True):
    st = _compat_0311(self, getattr(self, 'current_unit', None) or getattr(self, 'unit', None))
    M = st.get('M', (1.0, 0.0, 0.0, 1.0))
    if op == 'rotate':
        deg = round(float(value or 0.0) / 90.0) * 90.0
        if abs(deg) < 1e-9:
            return
        a = math.radians(deg)
        Op = (math.cos(a), -math.sin(a), math.sin(a), math.cos(a))
    elif op == 'flip_h':
        # Mirror at y-axis of canvas coordinate system, origin stays (0,0).
        Op = (-1.0, 0.0, 0.0, 1.0)
    elif op == 'flip_v':
        # Mirror at x-axis of canvas coordinate system, origin stays (0,0).
        Op = (1.0, 0.0, 0.0, -1.0)
    elif op in ('scale', 'scale_x_to', 'scale_y_to'):
        u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
        _compat_0334(self, u)
        cur_w = max(1e-9, float(getattr(u.body, 'width', 1.0) or 1.0))
        cur_h = max(1e-9, float(getattr(u.body, 'height', 1.0) or 1.0))
        if op == 'scale_x_to':
            sx, sy = _compat_0331(self, float(value), 0.01) / cur_w, 1.0
        elif op == 'scale_y_to':
            sx, sy = 1.0, _compat_0331(self, float(value), 0.01) / cur_h
        else:
            f = float(value or 1.0)
            sx = _compat_0331(self, cur_w * f, 0.01) / cur_w
            sy = _compat_0331(self, cur_h * f, 0.01) / cur_h
        Op = (sx, 0.0, 0.0, sy)
    else:
        return
    st['M'] = _compat_0322(Op, M)
    _compat_0307(self, st, refresh=refresh)

def _compat_0326(self, mode=None):
    mode = mode or (self.origin_combo.currentText() if hasattr(self, 'origin_combo') else OriginMode.CENTER.value)
    if mode not in _compat_0052:
        mode = OriginMode.CENTER.value
    try: self.push_undo_state()
    except Exception: pass
    self.symbol.origin = mode
    units = [getattr(self, 'current_unit', None) or getattr(self, 'unit', None)]
    if not getattr(self, 'is_template_editor', False) and getattr(self.symbol, 'kind', None) == SymbolKind.SPLIT.value:
        units = list(getattr(self.symbol, 'units', []) or units)
    for u in [x for x in units if x is not None]:
        _compat_0324(self, u, mode)
    if hasattr(self, 'origin_combo'):
        try:
            self.origin_combo.blockSignals(True); self.origin_combo.setCurrentText(mode); self.origin_combo.blockSignals(False)
        except Exception: pass
    try: self.set_format_guide_to_active_origin()
    except Exception: pass
    try: self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()
    except Exception:
        try: self.rebuild_scene()
        except Exception: pass
    try:
        self.view.setFocus(Qt.OtherFocusReason)
    except Exception:
        pass

def _compat_0312(self, body):
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    return _compat_0309(self, u)

def _compat_0328(self, body, attr, value):
    if attr not in ('line_style', 'line_width', 'color'):
        return
    try: self.push_undo_state()
    except Exception: pass
    setattr(body, attr, value)
    for gr in _compat_0312(self, body):
        st = getattr(gr, 'style', None)
        if st is None: continue
        if attr == 'line_style': st.line_style = value
        elif attr == 'line_width': st.line_width = float(value)
        elif attr == 'color': st.stroke = tuple(value)
    try: _compat_0318(self, getattr(self, 'current_unit', None) or getattr(self, 'unit', None))
    except Exception: pass
    try: self.update_current_unit_canvas_positions()
    except Exception: pass
    try: self.schedule_scene_refresh(visual_only=True)
    except Exception: self.rebuild_scene()

def _compat_0315(self, body):
    c = QColorDialog.getColor(QColor(*getattr(body, 'color', (0,0,0))), self)
    if c.isValid():
        _compat_0328(self, body, 'color', (c.red(), c.green(), c.blue()))

def _compat_0400(self, unit=None):
    u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    if u is None or getattr(u, 'body', None) is None:
        return
    if not _compat_0405(self, u):
        return
    attrs = getattr(u.body, 'attributes', None)
    if attrs is None:
        try:
            u.body.attributes = {}; attrs = u.body.attributes
        except Exception:
            return
    # This is only a semantic marker for the renderer/property panel.  It does
    # not create a proxy rectangle.  BODY bounds remain derived from graphics.
    attrs['MENTOR_GRAPHICS_AS_BODY'] = '1'
    attrs['MENTOR_BODY_GRAPHICS_LOCKED'] = '1'
    for g in getattr(u, 'graphics', []) or []:
        try:
            if _compat_0319(self, g):
                g.locked_to_body = True
                if not str(getattr(g, 'graphic_role', '') or ''):
                    g.graphic_role = 'imported_body'
        except Exception:
            pass
    try:
        _compat_0334(self, u)
    except Exception:
        pass

def _compat_0404(self):
    try:
        for i in self.scene.selectedItems():
            k = getattr(i, 'data', lambda *_: None)(0)
            if k in ('BODY', 'BODY_GRAPHIC'):
                return True
            m = getattr(i, 'model', None)
            if m is not None and _compat_0319(self, m):
                return True
    except Exception:
        pass
    return False

def _compat_0398(self):
    self.set_tool(DrawTool.SELECT.value)
    try: self.push_undo_state()
    except Exception: pass
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    _compat_0400(self, u)
    if _compat_0404(self):
        _compat_0335(self, 'flip_h')
    else:
        for it in self.scene.selectedItems():
            if hasattr(it, 'flip_horizontal'):
                it.flip_horizontal()
        try: self.schedule_scene_refresh()
        except Exception: self.rebuild_scene()
    self.dirty = True

def _compat_0399(self):
    self.set_tool(DrawTool.SELECT.value)
    try: self.push_undo_state()
    except Exception: pass
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    _compat_0400(self, u)
    if _compat_0404(self):
        _compat_0335(self, 'flip_v')
    else:
        for it in self.scene.selectedItems():
            if hasattr(it, 'flip_vertical'):
                it.flip_vertical()
        try: self.schedule_scene_refresh()
        except Exception: self.rebuild_scene()
    self.dirty = True

def _compat_0403(self, factor):
    self.set_tool(DrawTool.SELECT.value)
    try: self.push_undo_state()
    except Exception: pass
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    _compat_0400(self, u)
    if _compat_0404(self):
        _compat_0335(self, 'scale', float(factor))
    else:
        for it in self.scene.selectedItems():
            if hasattr(it, 'scale_by'):
                it.scale_by(float(factor))
            elif hasattr(it, 'scale_selected'):
                it.scale_selected(float(factor))
        try: self.schedule_scene_refresh()
        except Exception: self.rebuild_scene()
    self.dirty = True

def _compat_0550(op, x, y):
    x = float(x); y = float(y)
    typ = op[0]
    if typ == 'rotate':
        deg = float(op[1])
        # Only 90° steps are allowed here. Use exact matrices to avoid drift.
        d = int(round(deg / 90.0)) % 4
        if d == 0: return x, y
        if d == 1: return -y, x
        if d == 2: return -x, -y
        return y, -x
    if typ == 'flip_h':      # mirror at Y-axis: x -> -x
        return -x, y
    if typ == 'flip_v':      # mirror at X-axis: y -> -y
        return x, -y
    if typ == 'scale':
        sx, sy = float(op[1]), float(op[2])
        return x * sx, y * sy
    return x, y

def _compat_0555(angle, op):
    """Transform a non-text object's orientation angle by the operation."""
    try:
        a = float(angle or 0.0)
    except Exception:
        a = 0.0
    typ = op[0]
    if typ == 'rotate':
        return (a + float(op[1])) % 360.0
    if typ == 'flip_h':
        return (180.0 - a) % 360.0
    if typ == 'flip_v':
        return (-a) % 360.0
    return a % 360.0

def _compat_0558(self, tm, op, font_factor=1.0):
    if tm is None: return
    try:
        tm.x, tm.y = (_compat_0552(self, v) for v in _compat_0550(op, tm.x, tm.y))
    except Exception:
        pass
    _compat_0554(tm)
    try:
        tm.font_size_grid = max(0.1, _compat_0552(self, float(getattr(tm, 'font_size_grid', 0.75) or 0.75) * float(font_factor)))
    except Exception:
        pass

def _compat_0557(self, gr, op):
    if gr is None: return
    shape = str(getattr(gr, 'shape', '') or '')
    try:
        if shape in ('line', 'arc'):
            x1, y1 = float(gr.x), float(gr.y)
            x2, y2 = float(gr.x) + float(getattr(gr, 'w', 0.0) or 0.0), float(gr.y) - float(getattr(gr, 'h', 0.0) or 0.0)
            nx1, ny1 = _compat_0550(op, x1, y1)
            nx2, ny2 = _compat_0550(op, x2, y2)
            old_ctrl_x, old_ctrl_y = getattr(gr, 'ctrl_x', None), getattr(gr, 'ctrl_y', None)
            gr.x, gr.y = _compat_0552(self, nx1), _compat_0552(self, ny1)
            gr.w, gr.h = _compat_0552(self, nx2 - nx1), _compat_0552(self, ny1 - ny2)
            gr.rotation = 0.0
            gr.scale_x = 1.0; gr.scale_y = 1.0
            if old_ctrl_x is not None and old_ctrl_y is not None:
                try:
                    cx, cy = _compat_0550(op, x1 + float(old_ctrl_x), y1 - float(old_ctrl_y))
                    gr.ctrl_x = _compat_0552(self, cx - nx1)
                    gr.ctrl_y = _compat_0552(self, ny1 - cy)
                except Exception:
                    pass
            # curve_radius is a local distance; keep sign under rotation, mirror it under one-axis flips.
            try:
                if op[0] in ('flip_h', 'flip_v'):
                    gr.curve_radius = _compat_0552(self, -float(getattr(gr, 'curve_radius', 0.0) or 0.0))
                elif op[0] == 'scale':
                    gr.curve_radius = _compat_0552(self, float(getattr(gr, 'curve_radius', 0.0) or 0.0) * max(abs(float(op[1])), abs(float(op[2]))))
            except Exception:
                pass
        else:
            # Rect/ellipse/circle: transform center and orientation.  Keep glyph-free geometry mirrored/rotated.
            x = float(getattr(gr, 'x', 0.0) or 0.0); y = float(getattr(gr, 'y', 0.0) or 0.0)
            w = float(getattr(gr, 'w', 0.0) or 0.0); h = float(getattr(gr, 'h', 0.0) or 0.0)
            cx, cy = x + w/2.0, y - h/2.0
            ncx, ncy = _compat_0550(op, cx, cy)
            if op[0] == 'scale':
                w, h = abs(w * float(op[1])), abs(h * float(op[2]))
            # For 90° rotations keep model w/h and use model.rotation. This matches GraphicItem.
            gr.x, gr.y = _compat_0552(self, ncx - w/2.0), _compat_0552(self, ncy + h/2.0)
            gr.w, gr.h = _compat_0552(self, w), _compat_0552(self, h)
            gr.rotation = _compat_0552(self, _compat_0555(getattr(gr, 'rotation', 0.0), op))
            gr.scale_x = float(getattr(gr, 'scale_x', 1.0) or 1.0)
            gr.scale_y = float(getattr(gr, 'scale_y', 1.0) or 1.0)
            if op[0] == 'flip_h':
                gr.scale_x = -gr.scale_x
            elif op[0] == 'flip_v':
                gr.scale_y = -gr.scale_y
    except Exception:
        pass

def _compat_0556(self, b, op):
    if b is None: return
    try:
        x, y, w, h = float(b.x), float(b.y), float(b.width), float(b.height)
        cx, cy = x + w/2.0, y - h/2.0
        ncx, ncy = _compat_0550(op, cx, cy)
        if op[0] == 'scale':
            w, h = abs(w * float(op[1])), abs(h * float(op[2]))
        b.x, b.y = _compat_0552(self, ncx - w/2.0), _compat_0552(self, ncy + h/2.0)
        b.width, b.height = _compat_0552(self, max(0.01, w)), _compat_0552(self, max(0.01, h))
        b.rotation = _compat_0552(self, _compat_0555(getattr(b, 'rotation', 0.0), op))
        if op[0] == 'flip_h':
            b.scale_x = -float(getattr(b, 'scale_x', 1.0) or 1.0)
        elif op[0] == 'flip_v':
            b.scale_y = -float(getattr(b, 'scale_y', 1.0) or 1.0)
    except Exception:
        pass

def _compat_0551(self, unit):
    try:
        return _compat_0309(self, unit)
    except Exception:
        out=[]
        for g in getattr(unit, 'graphics', []) or []:
            role = str(getattr(g, 'graphic_role', '') or '').lower()
            raw = str(getattr(g, 'mentor_raw', '') or '')
            if getattr(g, 'locked_to_body', False) or role in ('body','template_body','imported_body') or (raw != '__USER_GRAPHIC__' and role != 'user_graphic'):
                out.append(g)
        return out

def _compat_0559(self, op_name, value=None, refresh=True):
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    if u is None or getattr(u, 'body', None) is None:
        return
    # Build exact operation around the canvas origin (0,0).
    if op_name == 'rotate':
        deg = round(float(value or 0.0) / 90.0) * 90.0
        if abs(deg) < 1e-9: return
        op = ('rotate', deg)
    elif op_name == 'flip_h':
        op = ('flip_h',)
    elif op_name == 'flip_v':
        op = ('flip_v',)
    elif op_name in ('scale', 'scale_x_to', 'scale_y_to'):
        try: _compat_0334(self, u)
        except Exception: pass
        cur_w = max(1e-9, float(getattr(u.body, 'width', 1.0) or 1.0))
        cur_h = max(1e-9, float(getattr(u.body, 'height', 1.0) or 1.0))
        try: snap = self._snap_to_edit_grid
        except Exception: snap = lambda vv, mn=0.01: max(mn, float(vv))
        if op_name == 'scale_x_to':
            sx = float(snap(float(value), 0.01)) / cur_w; sy = 1.0
        elif op_name == 'scale_y_to':
            sx = 1.0; sy = float(snap(float(value), 0.01)) / cur_h
        else:
            f = float(value or 1.0)
            sx = float(snap(cur_w * f, 0.01)) / cur_w
            sy = float(snap(cur_h * f, 0.01)) / cur_h
        op = ('scale', sx, sy)
    else:
        return
    font_factor = 1.0
    if op[0] == 'scale':
        font_factor = max(0.1, (abs(float(op[1])) + abs(float(op[2]))) / 2.0)

    # BODY: imported/template graphics are the BODY. Internal <NONE> uses BodyModel.
    body_graphics = _compat_0551(self, u)
    if body_graphics:
        for gr in body_graphics:
            _compat_0557(self, gr, op)
        try: _compat_0334(self, u)
        except Exception:
            try: self._sync_body_model_to_body_bounds_only(u)
            except Exception: pass
        # Keep logical proxy rotation neutral for imported artwork; visual rotation is in graphics.
        try: u.body.rotation = 0.0
        except Exception: pass
    else:
        _compat_0556(self, u.body, op)

    # User/free graphics are attached to the symbol too, but not part of BODY bounds.
    for gr in getattr(u, 'graphics', []) or []:
        if gr not in body_graphics:
            _compat_0557(self, gr, op)

    # Pins and pin-owned text.
    for p in getattr(u, 'pins', []) or []:
        try:
            p.x, p.y = (_compat_0552(self, v) for v in _compat_0550(op, p.x, p.y))
            p.rotation = _compat_0552(self, _compat_0555(getattr(p, 'rotation', 0.0), op))
            if op[0] == 'scale':
                p.length = max(0.1, _compat_0552(self, float(getattr(p, 'length', 1.0) or 1.0) * font_factor))
        except Exception: pass
        for ax, ay in (('label_x','label_y'), ('number_x','number_y')):
            if getattr(p, ax, None) is not None and getattr(p, ay, None) is not None:
                try:
                    nx, ny = _compat_0550(op, getattr(p, ax), getattr(p, ay))
                    setattr(p, ax, _compat_0552(self, nx)); setattr(p, ay, _compat_0552(self, ny))
                except Exception: pass
        for tm in (getattr(p, 'attribute_texts', {}) or {}).values():
            _compat_0558(self, tm, op, font_factor)
        try:
            if op[0] == 'scale':
                p.number_font.size_grid = max(0.1, _compat_0552(self, float(getattr(p.number_font, 'size_grid', .45) or .45) * font_factor))
                p.label_font.size_grid = max(0.1, _compat_0552(self, float(getattr(p.label_font, 'size_grid', .55) or .55) * font_factor))
        except Exception: pass

    for tm in getattr(u, 'texts', []) or []:
        _compat_0558(self, tm, op, font_factor)
    for tm in (getattr(u.body, 'attribute_texts', {}) or {}).values():
        _compat_0558(self, tm, op, font_factor)

    # Transformation is now directly applied; stale accumulated base would reapply old geometry.
    try:
        if hasattr(u, '_body_group_transform'):
            delattr(u, '_body_group_transform')
    except Exception: pass
    if refresh:
        try: self.update_current_unit_canvas_positions()
        except Exception:
            try: self.rebuild_scene()
            except Exception: pass
        try: self.rebuild_tree(); self.rebuild_pin_table()
        except Exception: pass

def _compat_0644(self, g, op):
    if g is None:
        return
    shape = str(getattr(g, 'shape', '') or '')
    clean = lambda v: _compat_0637(self, v)
    try:
        if shape in ('line', 'arc'):
            x1 = float(getattr(g, 'x', 0.0) or 0.0); y1 = float(getattr(g, 'y', 0.0) or 0.0)
            x2 = x1 + float(getattr(g, 'w', 0.0) or 0.0)
            y2 = y1 - float(getattr(g, 'h', 0.0) or 0.0)
            nx1, ny1 = _compat_0640(op, x1, y1); nx2, ny2 = _compat_0640(op, x2, y2)
            ctrl_x, ctrl_y = getattr(g, 'ctrl_x', None), getattr(g, 'ctrl_y', None)
            g.x, g.y = clean(nx1), clean(ny1)
            g.w, g.h = clean(nx2 - nx1), clean(ny1 - ny2)
            g.rotation = 0.0; g.scale_x = 1.0; g.scale_y = 1.0
            if ctrl_x is not None and ctrl_y is not None:
                try:
                    cx, cy = _compat_0640(op, x1 + float(ctrl_x), y1 - float(ctrl_y))
                    g.ctrl_x, g.ctrl_y = clean(cx - nx1), clean(ny1 - cy)
                except Exception:
                    pass
            try:
                if op[0] in ('flip_h', 'flip_v'):
                    g.curve_radius = clean(-float(getattr(g, 'curve_radius', 0.0) or 0.0))
                elif op[0] == 'scale':
                    g.curve_radius = clean(float(getattr(g, 'curve_radius', 0.0) or 0.0) * max(abs(float(op[1])), abs(float(op[2]))))
            except Exception:
                pass
        else:
            # Bake rect/ellipse/circle transformations into coordinates instead
            # of relying on a proxy item rotation.  For 90° rotations the real
            # BODY extents become the transformed extents directly.
            pts = [_compat_0640(op, px, py) for px, py in _compat_0638(g)]
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            minx, maxx = min(xs), max(xs); miny, maxy = min(ys), max(ys)
            g.x, g.y = clean(minx), clean(maxy)
            g.w, g.h = clean(maxx - minx), clean(maxy - miny)
            g.rotation = 0.0; g.scale_x = 1.0; g.scale_y = 1.0
    except Exception:
        pass

def _compat_0645(self, op_name, value=None, refresh=True):
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    if u is None or getattr(u, 'body', None) is None:
        return
    try: _compat_0400(self, u)
    except Exception: pass
    try: _compat_0334(self, u)
    except Exception: pass

    if op_name == 'rotate':
        deg = round(float(value or 0.0) / 90.0) * 90.0
        if abs(deg) < 1e-9:
            return
        op = ('rotate', deg)
    elif op_name == 'flip_h':
        op = ('flip_h',)
    elif op_name == 'flip_v':
        op = ('flip_v',)
    elif op_name in ('scale', 'scale_x_to', 'scale_y_to'):
        cur_w = max(1e-9, float(getattr(u.body, 'width', 1.0) or 1.0))
        cur_h = max(1e-9, float(getattr(u.body, 'height', 1.0) or 1.0))
        if op_name == 'scale_x_to':
            target_w = _compat_0642(self, float(value), 0.01); sx, sy = target_w / cur_w, 1.0
        elif op_name == 'scale_y_to':
            target_h = _compat_0642(self, float(value), 0.01); sx, sy = 1.0, target_h / cur_h
        else:
            f = float(value or 1.0)
            target_w = _compat_0642(self, cur_w * f, 0.01)
            target_h = _compat_0642(self, cur_h * f, 0.01)
            sx, sy = target_w / cur_w, target_h / cur_h
        op = ('scale', sx, sy)
    else:
        return

    font_factor = 1.0
    if op[0] == 'scale':
        font_factor = max(0.1, (abs(float(op[1])) + abs(float(op[2]))) / 2.0)

    body_graphics = []
    try: body_graphics = list(_compat_0309(self, u))
    except Exception: body_graphics = []

    if body_graphics:
        for g in body_graphics:
            _compat_0644(self, g, op)
        try: _compat_0334(self, u)
        except Exception: pass
        try: u.body.rotation = 0.0; u.body.scale_x = 1.0; u.body.scale_y = 1.0
        except Exception: pass
    else:
        # Internal <NONE>-style body: transform its own rectangle exactly.
        try:
            b = u.body
            pts = [_compat_0640(op, b.x, b.y), _compat_0640(op, b.x + b.width, b.y), _compat_0640(op, b.x + b.width, b.y - b.height), _compat_0640(op, b.x, b.y - b.height)]
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            b.x, b.y = _compat_0637(self, min(xs)), _compat_0637(self, max(ys))
            b.width, b.height = _compat_0637(self, max(xs)-min(xs)), _compat_0637(self, max(ys)-min(ys))
            b.rotation = 0.0; b.scale_x = 1.0; b.scale_y = 1.0
        except Exception:
            pass

    for g in getattr(u, 'graphics', []) or []:
        if g not in body_graphics:
            _compat_0644(self, g, op)

    for p in getattr(u, 'pins', []) or []:
        try:
            p.x, p.y = (_compat_0637(self, v) for v in _compat_0640(op, p.x, p.y))
            p.side = _compat_0641(getattr(p, 'side', ''), op)
            # Pin side now carries geometry. Keep item rotation neutral so pin
            # number/name/function are painted readable by PinItem.
            p.rotation = 0.0; p.scale_x = 1.0; p.scale_y = 1.0
            if op[0] == 'scale':
                p.length = max(0.1, _compat_0637(self, float(getattr(p, 'length', 1.0) or 1.0) * font_factor))
        except Exception:
            pass
        for ax, ay in (('label_x', 'label_y'), ('number_x', 'number_y')):
            if getattr(p, ax, None) is not None and getattr(p, ay, None) is not None:
                try:
                    nx, ny = _compat_0640(op, getattr(p, ax), getattr(p, ay))
                    setattr(p, ax, _compat_0637(self, nx)); setattr(p, ay, _compat_0637(self, ny))
                except Exception: pass
        for tm in (getattr(p, 'attribute_texts', {}) or {}).values():
            _compat_0639(self, tm, op, font_factor)
        try:
            if op[0] == 'scale':
                p.number_font.size_grid = max(0.1, _compat_0637(self, float(getattr(p.number_font, 'size_grid', .45) or .45) * font_factor))
                p.label_font.size_grid = max(0.1, _compat_0637(self, float(getattr(p.label_font, 'size_grid', .55) or .55) * font_factor))
        except Exception:
            pass

    for tm in getattr(u, 'texts', []) or []:
        _compat_0639(self, tm, op, font_factor)
    for tm in (getattr(u.body, 'attribute_texts', {}) or {}).values():
        _compat_0639(self, tm, op, font_factor)

    try:
        if hasattr(u, '_body_group_transform'):
            delattr(u, '_body_group_transform')
    except Exception: pass
    if refresh:
        # Rebuild after BODY graphic transformations so QGraphicsItems cannot
        # retain stale proxy/rotation state.
        try: self.rebuild_scene()
        except Exception:
            try: self.update_current_unit_canvas_positions()
            except Exception: pass
        try: self.rebuild_tree(); self.rebuild_pin_table()
        except Exception: pass

def _compat_0687(self):
    try:
        for it in self.scene.selectedItems():
            k = getattr(it, 'data', lambda *_: None)(0)
            if k in ('BODY', 'BODY_GRAPHIC'):
                return True
            m = getattr(it, 'model', None)
            if m is not None:
                try:
                    if _compat_0319(self, m):
                        return True
                except Exception:
                    if getattr(m, 'locked_to_body', False) or str(getattr(m, 'graphic_role', '') or '').lower() in ('body','template_body','imported_body'):
                        return True
    except Exception:
        pass
    return False

def _compat_0682(self, op_name, value=None):
    try:
        self.set_tool(DrawTool.SELECT.value)
    except Exception:
        pass
    try:
        self.push_undo_state()
    except Exception:
        pass
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    try:
        _compat_0400(self, u)
    except Exception:
        pass
    if _compat_0687(self):
        fn = getattr(self, '_transform_unit_as_body_group', None)
        if callable(fn):
            fn(op_name, value)
        else:
            _compat_0645(self, op_name, value)
    else:
        # Keep existing behaviour for explicitly selected standalone objects.
        try:
            for it in self.scene.selectedItems():
                if op_name == 'rotate' and hasattr(it, 'rotate_by'):
                    it.rotate_by(float(value or 0.0))
                elif op_name == 'flip_h' and hasattr(it, 'flip_horizontal'):
                    it.flip_horizontal()
                elif op_name == 'flip_v' and hasattr(it, 'flip_vertical'):
                    it.flip_vertical()
                elif op_name == 'scale' and hasattr(it, 'scale_by'):
                    it.scale_by(float(value or 1.0))
        except Exception:
            pass
        try:
            self.rebuild_scene()
        except Exception:
            try: self.schedule_scene_refresh()
            except Exception: pass
    try:
        self.dirty = True
    except Exception:
        pass

def _compat_0683(self):
    # Flip H = mirror at canvas Y-axis: x -> -x.
    _compat_0682(self, 'flip_h', None)

def _compat_0684(self):
    # Flip V = mirror at canvas X-axis: y -> -y.
    _compat_0682(self, 'flip_v', None)

def _compat_0686(self, factor):
    _compat_0682(self, 'scale', float(factor))

def _compat_0640(op, x, y):
    x = float(x); y = float(y)
    if op[0] == 'rotate':
        # Positive angle is clockwise in the Symbol Wizard UI.
        d = int(round(float(op[1]) / 90.0)) % 4
        if d == 0:
            return x, y
        if d == 1:      # 90° CW
            return y, -x
        if d == 2:
            return -x, -y
        return -y, x    # 90° CCW
    if op[0] == 'flip_h':
        # Flip H means mirror at the horizontal X-axis.
        return x, -y
    if op[0] == 'flip_v':
        # Flip V means mirror at the vertical Y-axis.
        return -x, y
    if op[0] == 'scale':
        return x * float(op[1]), y * float(op[2])
    return x, y

def _compat_0708(self):
    # Flip H = mirror at horizontal X-axis.
    _compat_0682(self, 'flip_h', None)

def _compat_0709(self):
    # Flip V = mirror at vertical Y-axis.
    _compat_0682(self, 'flip_v', None)

def _compat_0713(item):
    try:
        return getattr(item, 'data', lambda *_: None)(0) == 'BODY_GRAPHIC'
    except Exception:
        return False

def _compat_0712(self):
    try:
        items = list(self.scene.items())
    except Exception:
        return []
    body_items = []
    body_graphics = []
    for it in items:
        try:
            k = it.data(0)
        except Exception:
            continue
        if k == 'BODY':
            body_items.append(it)
        elif k == 'BODY_GRAPHIC':
            body_graphics.append(it)
    # Prefer a real BODY item for native Symbol 1; otherwise use one visible
    # BODY_GRAPHIC primitive as the click/selection representative for imported
    # artwork bodies.  All BODY_GRAPHIC primitives still paint the body, but the
    # selection model exposes exactly one logical BODY to the user.
    return body_items or body_graphics

def _compat_0069(self, unit=None):
    u = unit or getattr(self, 'current_unit', None)
    out = []
    for gr in getattr(u, 'graphics', []) or []:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        raw = str(getattr(gr, 'mentor_raw', '') or '')
        if getattr(gr, 'locked_to_body', False) or role in ('body', 'template_body', 'imported_body') or (raw != '__USER_GRAPHIC__' and role != 'user_graphic'):
            out.append(gr)
    return out

def _compat_0073(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    # GraphicItem uses model endpoint (x+w, y-h) in grid coordinates.
    return (x, y, x + w, y - h)

def _compat_0070(self, unit=None):
    gs = _compat_0069(self, unit)
    if not gs:
        b = (unit or self.current_unit).body
        return (float(b.x), float(b.y), float(b.width), float(b.height))
    xs, ys = [], []
    for gr in gs:
        x1, y1, x2, y2 = _compat_0073(gr)
        xs.extend([x1, x2]); ys.extend([y1, y2])
        try:
            if getattr(gr, 'ctrl_x', None) is not None and getattr(gr, 'ctrl_y', None) is not None:
                xs.append(x1 + float(gr.ctrl_x)); ys.append(y1 - float(gr.ctrl_y))
        except Exception:
            pass
    left, right = min(xs), max(xs)
    bottom, top = min(ys), max(ys)
    return (self._clean_float(left), self._clean_float(top), self._clean_float(max(0.01, right-left)), self._clean_float(max(0.01, top-bottom)))

def _compat_0082(self, unit=None):
    u = unit or self.current_unit
    gs = _compat_0069(self, u)
    if not gs:
        return
    x, y, w, h = _compat_0070(self, u)
    b = u.body
    b.x, b.y, b.width, b.height = x, y, w, h

def _compat_0078(self, unit, old_bounds, new_bounds):
    gs = _compat_0069(self, unit)
    if not gs:
        return
    ox, oy, ow, oh = old_bounds
    nx, ny, nw, nh = new_bounds
    ow, oh = max(float(ow), 1e-9), max(float(oh), 1e-9)
    sx, sy = float(nw) / ow, float(nh) / oh
    def map_pt(x, y):
        # x relative from left; y relative downward from top.
        return (self._clean_float(nx + (float(x) - ox) * sx),
                self._clean_float(ny - (oy - float(y)) * sy))
    for gr in gs:
        x1, y1, x2, y2 = _compat_0073(gr)
        nx1, ny1 = map_pt(x1, y1)
        nx2, ny2 = map_pt(x2, y2)
        gr.x, gr.y = nx1, ny1
        gr.w = self._clean_float(nx2 - nx1)
        gr.h = self._clean_float(ny1 - ny2)
        try:
            if getattr(gr, 'ctrl_x', None) is not None:
                gr.ctrl_x = self._clean_float(float(gr.ctrl_x) * sx)
            if getattr(gr, 'ctrl_y', None) is not None:
                gr.ctrl_y = self._clean_float(float(gr.ctrl_y) * sy)
        except Exception:
            pass
    _compat_0082(self, unit)

def _compat_0079(self, new_w, new_h, refresh=True):
    """Resize BODY to edit-grid dimensions without scaling pins/text glyphs."""
    u = self.current_unit; b = u.body
    old_bounds = _compat_0070(self, u) if _compat_0069(self, u) else (float(b.x), float(b.y), float(b.width), float(b.height))
    old_x, old_y, old_w, old_h = old_bounds
    new_w = max(_compat_0071(self), _compat_0081(self, new_w))
    new_h = max(_compat_0071(self), _compat_0081(self, new_h))
    start = {
        'x': old_x, 'y': old_y, 'w': old_w, 'h': old_h,
        'pins': [(p, float(p.x), float(p.y), float(getattr(p, 'length', 1.0) or 1.0)) for p in getattr(u, 'pins', []) or []],
        'texts': [(t, float(t.x), float(t.y)) for t in getattr(u, 'texts', []) or []],
        'attributes': [(t, float(t.x), float(t.y)) for t in (getattr(b, 'attribute_texts', {}) or {}).values()],
        'graphics': [(gr, float(gr.x), float(gr.y), float(getattr(gr, 'w', 0.0) or 0.0), float(getattr(gr, 'h', 0.0) or 0.0)) for gr in getattr(u, 'graphics', []) or [] if gr not in _compat_0069(self, u)],
    }
    # Keep the authored top-left anchor. This matches canvas drag-resize behaviour.
    new_bounds = (old_x, old_y, new_w, new_h)
    if _compat_0069(self, u):
        _compat_0078(self, u, old_bounds, new_bounds)
    else:
        b.x, b.y, b.width, b.height = old_x, old_y, new_w, new_h
    _compat_0077(self, start, b)
    # Non-pin text/user graphics are repositioned proportionally to stay attached,
    # but their font size/visual scale is intentionally unchanged.
    sx, sy = new_w / max(old_w, 1e-9), new_h / max(old_h, 1e-9)
    def map_pos(x, y): return (_compat_0081(self, old_x + (float(x)-old_x)*sx), _compat_0081(self, old_y - (old_y-float(y))*sy))
    for t, tx, ty in start.get('texts', []) or []:
        t.x, t.y = map_pos(tx, ty)
    for t, tx, ty in start.get('attributes', []) or []:
        t.x, t.y = map_pos(tx, ty)
    for gr, gx, gy, gw, gh in start.get('graphics', []) or []:
        gr.x, gr.y = map_pos(gx, gy)
        # user graphics are not the BODY; keep their own dimensions unchanged.
        gr.w, gr.h = gw, gh
    # Body transform base is invalid after geometry edit.
    try: delattr(u, '_body_group_transform')
    except Exception: pass
    if refresh:
        self.update_current_unit_canvas_positions()
        self.update_attribute_items_for_unit()
        self.rebuild_tree(); self.rebuild_pin_table()
        try: self.refresh_properties()
        except Exception: pass
        try: self.view.viewport().update()
        except Exception: pass

def _compat_0080(self, start_state, body):
    """Canvas BODY handle resize: scale BODY graphics only; pins stay grid/length."""
    u = self.current_unit
    old_bounds = (float(start_state.get('x', body.x)), float(start_state.get('y', body.y)),
                  max(float(start_state.get('w', body.width)), 1e-9), max(float(start_state.get('h', body.height)), 1e-9))
    new_w = _compat_0081(self, float(body.width))
    new_h = _compat_0081(self, float(body.height))
    body.width, body.height = max(_compat_0071(self), new_w), max(_compat_0071(self), new_h)
    new_bounds = (float(body.x), float(body.y), float(body.width), float(body.height))
    if _compat_0069(self, u):
        _compat_0078(self, u, old_bounds, new_bounds)
    _compat_0077(self, start_state, body)
    # Texts/body attributes follow the body proportionally; glyphs are not scaled.
    ox, oy, ow, oh = old_bounds; nx, ny, nw, nh = new_bounds
    sx, sy = nw / max(ow, 1e-9), nh / max(oh, 1e-9)
    def map_pos(x, y): return (_compat_0081(self, nx + (float(x)-ox)*sx), _compat_0081(self, ny - (oy-float(y))*sy))
    for t, tx, ty in start_state.get('texts', []) or []:
        t.x, t.y = map_pos(tx, ty)
    for t, tx, ty in start_state.get('attributes', []) or []:
        t.x, t.y = map_pos(tx, ty)
    # User graphics are separate objects: move anchor only, do not scale their size.
    body_graphics = set(_compat_0069(self, u))
    for gr, gx, gy, gw, gh in start_state.get('graphics', []) or []:
        if gr in body_graphics:
            continue
        gr.x, gr.y = map_pos(gx, gy)
        gr.w, gr.h = gw, gh
    try: delattr(u, '_body_group_transform')
    except Exception: pass

def _compat_0083(self, op, value=None, refresh=True):
    # Only scale BODY geometry for Scale +/- and BODY width/height edits.  Rotate
    # and Flip remain true group transforms.
    if op in ('scale', 'scale_x_to', 'scale_y_to'):
        b = self.current_unit.body
        cur_w, cur_h = float(getattr(b, 'width', 1.0) or 1.0), float(getattr(b, 'height', 1.0) or 1.0)
        if op == 'scale_x_to':
            new_w, new_h = float(value), cur_h
        elif op == 'scale_y_to':
            new_w, new_h = cur_w, float(value)
        else:
            f = float(value or 1.0)
            new_w, new_h = cur_w * f, cur_h * f
        return _compat_0079(self, new_w, new_h, refresh=refresh)
    if _compat_0076 is not None:
        return _compat_0076(self, op, value, refresh)

def _compat_0344(self, gr):
    try:
        # In the template editor the drawn graphics define the template BODY.
        if getattr(self, 'is_template_editor', False):
            return True
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        marker = str(getattr(gr, 'mentor_raw', '') or '')
        if role == 'user_graphic' or marker == '__USER_GRAPHIC__':
            return False
        return bool(getattr(gr, 'locked_to_body', False) or role in ('body', 'template_body', 'imported_body') or marker)
    except Exception:
        return False

def _compat_0338(self, unit=None):
    u = unit or getattr(self, 'current_unit', None)
    return [g for g in (getattr(u, 'graphics', []) or []) if _compat_0344(self, g)]

def _compat_0343(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    shape = str(getattr(gr, 'shape', '') or '')
    if shape in ('line', 'arc', 'curve'):
        pts = [(x, y), (x + w, y - h)]
        cx = getattr(gr, 'ctrl_x', None); cy = getattr(gr, 'ctrl_y', None)
        if cx is not None and cy is not None:
            pts.append((x + float(cx), y - float(cy)))
        else:
            cr = float(getattr(gr, 'curve_radius', 0.0) or 0.0)
            if abs(cr) > 1e-12:
                pts.append((x + w / 2.0, y - h / 2.0 + cr))
    else:
        pts = [(x, y), (x + w, y), (x + w, y - h), (x, y - h)]
    return pts

def _compat_0337(self, unit=None):
    u = unit or self.current_unit
    gs = _compat_0338(self, u)
    if not gs:
        b = u.body
        return (float(b.x), float(b.y), float(b.width), float(b.height))
    pts = []
    for g in gs:
        pts.extend(_compat_0343(g))
    if not pts:
        b = u.body
        return (float(b.x), float(b.y), float(b.width), float(b.height))
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return (_compat_0340(self, min(xs)), _compat_0340(self, max(ys)),
            _compat_0340(self, max(0.01, max(xs) - min(xs))),
            _compat_0340(self, max(0.01, max(ys) - min(ys))))

def _compat_0355(self, unit=None):
    u = unit or self.current_unit
    if not _compat_0338(self, u):
        return
    x, y, w, h = _compat_0337(self, u)
    u.body.x, u.body.y, u.body.width, u.body.height = x, y, w, h
    try: u.body.rotation = 0.0
    except Exception: pass

def _compat_0351(self, unit, old_bounds, new_bounds):
    gs = _compat_0338(self, unit)
    if not gs: return
    ox, oy, ow, oh = old_bounds; nx, ny, nw, nh = new_bounds
    sx = float(nw) / max(float(ow), 1e-9); sy = float(nh) / max(float(oh), 1e-9)
    def mp(x, y):
        return (_compat_0340(self, nx + (float(x) - ox) * sx),
                _compat_0340(self, ny - (oy - float(y)) * sy))
    for g in gs:
        x = float(getattr(g, 'x', 0.0) or 0.0); y = float(getattr(g, 'y', 0.0) or 0.0)
        w = float(getattr(g, 'w', 0.0) or 0.0); h = float(getattr(g, 'h', 0.0) or 0.0)
        x1, y1 = mp(x, y); x2, y2 = mp(x + w, y - h)
        g.x, g.y = x1, y1
        g.w, g.h = _compat_0340(self, x2 - x1), _compat_0340(self, y1 - y2)
        try:
            if getattr(g, 'ctrl_x', None) is not None: g.ctrl_x = _compat_0340(self, float(g.ctrl_x) * sx)
            if getattr(g, 'ctrl_y', None) is not None: g.ctrl_y = _compat_0340(self, float(g.ctrl_y) * sy)
            if getattr(g, 'curve_radius', None) is not None: g.curve_radius = _compat_0340(self, float(g.curve_radius) * ((abs(sx)+abs(sy))/2.0))
        except Exception: pass
    _compat_0355(self, unit)

def _compat_0339(self, unit=None):
    u = unit or self.current_unit; b = u.body
    return {
        'pins': [(p, float(p.x), float(p.y), float(getattr(p, 'length', 1.0) or 1.0)) for p in getattr(u, 'pins', []) or []],
        'texts': [(t, float(t.x), float(t.y)) for t in getattr(u, 'texts', []) or []],
        'attributes': [(t, float(t.x), float(t.y)) for t in (getattr(b, 'attribute_texts', {}) or {}).values()],
        'graphics': [(g, float(g.x), float(g.y), float(getattr(g, 'w', 0.0) or 0.0), float(getattr(g, 'h', 0.0) or 0.0)) for g in getattr(u, 'graphics', []) or [] if g not in _compat_0338(self, u)],
    }

def _compat_0349(self, new_w=None, new_h=None, refresh=True, anchor_bounds=None):
    if getattr(self, '_compat_0350', False): return
    self._compat_0350 = True
    try:
        u = self.current_unit; b = u.body
        old_bounds = anchor_bounds or _compat_0337(self, u)
        ox, oy, ow, oh = old_bounds
        step = _compat_0342(self)
        new_w = max(step, _compat_0354(self, ow if new_w is None else new_w))
        new_h = max(step, _compat_0354(self, oh if new_h is None else new_h))
        start = _compat_0339(self, u)
        new_bounds = (ox, oy, new_w, new_h)
        if _compat_0338(self, u):
            _compat_0351(self, u, old_bounds, new_bounds)
        else:
            b.x, b.y, b.width, b.height = ox, oy, new_w, new_h
        _compat_0348(self, u, start, old_bounds, (b.x, b.y, b.width, b.height))
        nx, ny, nw, nh = float(b.x), float(b.y), float(b.width), float(b.height)
        sx = nw / max(float(ow), 1e-9); sy = nh / max(float(oh), 1e-9)
        def map_pos(x, y): return (_compat_0354(self, nx + (float(x)-ox)*sx), _compat_0354(self, ny - (oy-float(y))*sy))
        for t, tx, ty in start.get('texts', []) or []: t.x, t.y = map_pos(tx, ty)
        for t, tx, ty in start.get('attributes', []) or []: t.x, t.y = map_pos(tx, ty)
        for g, gx, gy, gw, gh in start.get('graphics', []) or []:
            g.x, g.y = map_pos(gx, gy); g.w, g.h = gw, gh
        try:
            if hasattr(u, '_body_group_transform'): delattr(u, '_body_group_transform')
        except Exception: pass
        self.dirty = True
    finally:
        self._compat_0350 = False
    if refresh:
        try: self.update_current_unit_canvas_positions()
        except Exception: pass
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.rebuild_tree(); self.rebuild_pin_table()
        except Exception: pass
        try: self.refresh_properties()
        except Exception: pass
        try: self.schedule_scene_refresh(visual_only=True)
        except Exception:
            try: self.scene.update()
            except Exception: pass

def _compat_0356(self, op, value=None, refresh=True):
    if op in ('scale', 'scale_x_to', 'scale_y_to'):
        b = self.current_unit.body
        cur_w = float(getattr(b, 'width', 1.0) or 1.0); cur_h = float(getattr(b, 'height', 1.0) or 1.0)
        if op == 'scale_x_to': return _compat_0349(self, new_w=float(value), new_h=None, refresh=refresh)
        if op == 'scale_y_to': return _compat_0349(self, new_w=None, new_h=float(value), refresh=refresh)
        f = float(value or 1.0)
        return _compat_0349(self, new_w=cur_w * f, new_h=cur_h * f, refresh=refresh)
    if _compat_0347 is not None:
        return _compat_0347(self, op, value, refresh)

def _compat_0352(self, start_state, body):
    try:
        old_bounds = (float(start_state.get('x', body.x)), float(start_state.get('y', body.y)),
                      max(float(start_state.get('w', body.width)), 1e-9), max(float(start_state.get('h', body.height)), 1e-9))
        _compat_0349(self, new_w=float(body.width), new_h=float(body.height), refresh=True, anchor_bounds=old_bounds)
    except Exception as e:
        try: self.statusBar().showMessage(f'Canvas BODY scale failed: {e}', 4000)
        except Exception: pass

def _compat_0357(self, unit=None):
    u = unit or self.current_unit; b = u.body
    pins = []
    for p in getattr(u, 'pins', []) or []:
        pins.append((p, float(p.x), float(p.y), float(getattr(p, 'length', 1.0) or 1.0),
                     float(getattr(getattr(p, 'number_font', None), 'size_grid', 0.45) or 0.45),
                     float(getattr(getattr(p, 'label_font', None), 'size_grid', 0.55) or 0.55)))
    return {
        'pins': pins,
        'texts': [(t, float(t.x), float(t.y)) for t in getattr(u, 'texts', []) or []],
        'attributes': [(t, float(t.x), float(t.y)) for t in (getattr(b, 'attribute_texts', {}) or {}).values()],
        'graphics': [(g, float(g.x), float(g.y), float(getattr(g, 'w', 0.0) or 0.0), float(getattr(g, 'h', 0.0) or 0.0)) for g in getattr(u, 'graphics', []) or [] if g not in _compat_0338(self, u)],
    }

def _compat_0360(self, new_w=None, new_h=None, refresh=True, anchor_bounds=None):
    if getattr(self, '_compat_0350', False): return
    keep_ids = set(getattr(self, '_selection_restore_ids', set()) or _compat_0364(self))
    self._compat_0350 = True
    try:
        u = self.current_unit; b = u.body
        old_bounds = anchor_bounds or _compat_0337(self, u)
        ox, oy, ow, oh = old_bounds
        step = _compat_0342(self)
        new_w = max(step, _compat_0354(self, ow if new_w is None else new_w))
        new_h = max(step, _compat_0354(self, oh if new_h is None else new_h))
        start = _compat_0357(self, u)
        new_bounds = (ox, oy, new_w, new_h)
        if _compat_0338(self, u):
            _compat_0351(self, u, old_bounds, new_bounds)
        else:
            b.x, b.y, b.width, b.height = ox, oy, new_w, new_h
        _compat_0359(self, u, start, old_bounds, (b.x, b.y, b.width, b.height))
        nx, ny, nw, nh = float(b.x), float(b.y), float(b.width), float(b.height)
        sx = nw / max(float(ow), 1e-9); sy = nh / max(float(oh), 1e-9)
        def map_pos(x, y): return (_compat_0354(self, nx + (float(x)-ox)*sx), _compat_0354(self, ny - (oy-float(y))*sy))
        for t, tx, ty in start.get('texts', []) or []: t.x, t.y = map_pos(tx, ty)
        for t, tx, ty in start.get('attributes', []) or []: t.x, t.y = map_pos(tx, ty)
        for g, gx, gy, gw, gh in start.get('graphics', []) or []:
            g.x, g.y = map_pos(gx, gy); g.w, g.h = gw, gh
        try:
            if hasattr(u, '_body_group_transform'): delattr(u, '_body_group_transform')
        except Exception: pass
        self.dirty = True
    finally:
        self._compat_0350 = False
    if refresh:
        try: self.update_current_unit_canvas_positions()
        except Exception: pass
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.rebuild_tree(); self.rebuild_pin_table()
        except Exception: pass
        try: self.schedule_scene_refresh(visual_only=True)
        except Exception:
            try: self.scene.update()
            except Exception: pass
        _compat_0358(self, keep_ids)

def _compat_0365(self, op, value=None, refresh=True):
    if op in ('scale', 'scale_x_to', 'scale_y_to'):
        b = self.current_unit.body
        cur_w = float(getattr(b, 'width', 1.0) or 1.0); cur_h = float(getattr(b, 'height', 1.0) or 1.0)
        if op == 'scale_x_to': return _compat_0360(self, new_w=float(value), new_h=None, refresh=refresh)
        if op == 'scale_y_to': return _compat_0360(self, new_w=None, new_h=float(value), refresh=refresh)
        f = float(value or 1.0)
        return _compat_0360(self, new_w=cur_w * f, new_h=cur_h * f, refresh=refresh)
    if _compat_0347 is not None:
        keep_ids = _compat_0364(self)
        r = _compat_0347(self, op, value, refresh)
        _compat_0358(self, keep_ids)
        return r

def _compat_0362(self, start_state, body):
    try:
        keep_ids = _compat_0364(self) or {id(body)}
        self._selection_restore_ids = keep_ids
        old_bounds = (float(start_state.get('x', body.x)), float(start_state.get('y', body.y)),
                      max(float(start_state.get('w', body.width)), 1e-9), max(float(start_state.get('h', body.height)), 1e-9))
        _compat_0360(self, new_w=float(body.width), new_h=float(body.height), refresh=True, anchor_bounds=old_bounds)
    except Exception as e:
        try: self.statusBar().showMessage(f'Canvas BODY scale failed: {e}', 4000)
        except Exception: pass

def _compat_0367(self, new_w=None, new_h=None, refresh=True, anchor_bounds=None):
    sig = _compat_0371(self) or getattr(self, '_compat_0372', [])
    # Reuse the LH45 geometry implementation, but afterwards force exact BODY
    # selection restore and deliberately avoid rebuilding the property panel.
    r = _compat_0360(self, new_w=new_w, new_h=new_h, refresh=refresh, anchor_bounds=anchor_bounds)
    _compat_0366(self, sig)
    return r

def _compat_0373(self, op, value=None, refresh=True):
    sig = _compat_0371(self)
    if op in ('scale', 'scale_x_to', 'scale_y_to'):
        b = self.current_unit.body
        cur_w = float(getattr(b, 'width', 1.0) or 1.0); cur_h = float(getattr(b, 'height', 1.0) or 1.0)
        if op == 'scale_x_to': r = _compat_0367(self, new_w=float(value), new_h=None, refresh=refresh)
        elif op == 'scale_y_to': r = _compat_0367(self, new_w=None, new_h=float(value), refresh=refresh)
        else:
            f = float(value or 1.0); r = _compat_0367(self, new_w=cur_w * f, new_h=cur_h * f, refresh=refresh)
        _compat_0366(self, sig)
        return r
    if _compat_0347 is not None:
        r = _compat_0347(self, op, value, refresh)
        _compat_0366(self, sig)
        return r

def _compat_0369(self, start_state, body):
    sig = _compat_0371(self) or getattr(self, '_compat_0372', [])
    try:
        old_bounds = (float(start_state.get('x', body.x)), float(start_state.get('y', body.y)),
                      max(float(start_state.get('w', body.width)), 1e-9), max(float(start_state.get('h', body.height)), 1e-9))
        return _compat_0367(self, new_w=float(body.width), new_h=float(body.height), refresh=True, anchor_bounds=old_bounds)
    except Exception as e:
        try: self.statusBar().showMessage(f'Canvas BODY scale failed: {e}', 4000)
        except Exception: pass
    finally:
        _compat_0366(self, sig)

def _compat_0374(self):
    return _compat_0388(self, lambda: _compat_0376(self), force_body=bool(self._selected_body_active()))

def _compat_0375(self):
    return _compat_0388(self, lambda: _compat_0377(self), force_body=bool(self._selected_body_active()))

def _compat_0384(self, factor):
    def work():
        try:
            if self._selected_body_active():
                return _compat_0379(self, factor)
            selected = list(self.scene.selectedItems())
            if selected and all(getattr(i, 'data', lambda *_: None)(0) == 'PIN' for i in selected):
                try: self.statusBar().showMessage('Pins are not scaled; edit pin length explicitly.', 2500)
                except Exception: pass
                return None
        except Exception:
            pass
        return _compat_0379(self, factor)
    return _compat_0388(self, work, force_body=bool(self._selected_body_active()))

def _compat_0392(item):
    try:
        k = item.data(0)
    except Exception:
        k = None
    if k in ('BODY_GRAPHIC',):
        return 'BODY'
    return k

def _compat_0406(self, sig=None):
    try:
        if str(_compat_0412(self) or '').upper() == 'BODY':
            return True
    except Exception:
        pass
    try:
        return any(str(s[0]) in ('BODY', 'BODY_GRAPHIC') for s in (sig or []))
    except Exception:
        return False

def _compat_0414(self, sig=None, fs=None, refresh_panel=True):
    force_body = _compat_0406(self, sig)
    def run():
        try:
            if fs is not None and '_compat_0382' in globals():
                _compat_0382(self, fs)
            if force_body and '_compat_0386' in globals():
                _compat_0386(self)
            elif sig and '_compat_0368' in globals():
                _compat_0368(self, sig)
            if refresh_panel:
                try:
                    if getattr(self, 'is_template_editor', False):
                        self.refresh_properties()
                    else:
                        _compat_0413(self)
                except Exception:
                    pass
            try:
                if '_compat_0397' in globals():
                    _compat_0397(self)
            except Exception:
                pass
        except Exception as e:
            try: self.statusBar().showMessage(f'Selection restore failed: {e}', 4000)
            except Exception: pass
    try: QTimer.singleShot(0, run)
    except Exception: run()

def _compat_0418(self, body):
    vals = ['0°', '90°', '180°', '270°']
    try:
        cur = int(round(float(getattr(body, 'rotation', 0.0) or 0.0) / 90.0) * 90) % 360
    except Exception:
        cur = 0
    w = QComboBox(); w.blockSignals(True); w.addItems(vals); w.setCurrentText(f'{cur}°'); w.blockSignals(False)
    def safe(txt):
        try:
            target = float(str(txt).replace('°','').strip()) % 360.0
        except Exception:
            return
        sig = _compat_0371(self) if '_compat_0371' in globals() else []
        fs = _compat_0387(self) if '_compat_0387' in globals() else None
        def do():
            try:
                current = float(getattr(body, 'rotation', 0.0) or 0.0) % 360.0
                delta = target - current
                if abs(delta) > 180.0:
                    delta -= 360.0 if delta > 0 else -360.0
                if abs(delta) > 1e-9:
                    try: self.push_undo_state()
                    except Exception: pass
                    self._transform_unit_as_body_group('rotate', delta)
                    try: body.rotation = target
                    except Exception: pass
                    self.dirty = True
            except Exception as e:
                try: self.statusBar().showMessage(f'BODY rotation failed: {e}', 5000)
                except Exception: pass
            finally:
                try: self._compat_0410 = 'BODY'
                except Exception: pass
                if '_compat_0414' in globals():
                    _compat_0414(self, sig=sig, fs=fs, refresh_panel=True)
                elif '_compat_0381' in globals():
                    _compat_0381(self, sig=sig, filter_state=fs, force_body=True, refresh=True)
        try: QTimer.singleShot(0, do)
        except Exception: do()
    w.currentTextChanged.connect(safe)
    return w

def _compat_0419(self, m):
    try:
        if m is getattr(getattr(self, 'current_unit', None), 'body', None):
            self.form.addRow('Rotation [deg]', _compat_0418(self, m))
            return
    except Exception:
        pass
    # non-BODY fallback stays as before
    self.form.addRow('Rotation [deg]', self._dbl(getattr(m, 'rotation', 0), lambda v, model=m: self.set_and_refresh(model, 'rotation', v), -360, 360, 15))

def _compat_0420(self):
    try:
        return bool(self._selected_body_active())
    except Exception:
        try:
            return any(getattr(i, 'data', lambda *_: None)(0) == 'BODY' for i in self.scene.selectedItems())
        except Exception:
            return False

def _compat_0423(self, deg, before_rotation):
    try:
        body = getattr(getattr(self, 'current_unit', None), 'body', None)
        if body is None:
            return
        # Keep the UI representation constrained to the four valid values.
        # Toolbar buttons are 90° steps; non-90 values are snapped defensively.
        step = int(round(float(deg or 0.0) / 90.0)) * 90
        before = int(round(float(before_rotation or 0.0) / 90.0)) * 90
        body.rotation = float((before + step) % 360)
        try: self._compat_0410 = 'BODY'
        except Exception: pass
    except Exception:
        pass

def _compat_0426(gr):
    try:
        return _compat_0073(gr)
    except Exception:
        x = float(getattr(gr, 'x', 0.0) or 0.0)
        y = float(getattr(gr, 'y', 0.0) or 0.0)
        w = float(getattr(gr, 'w', 0.0) or 0.0)
        h = float(getattr(gr, 'h', 0.0) or 0.0)
        return (x, y, x + w, y - h)

def _compat_0430(self, gr, factor):
    x1, y1, x2, y2 = _compat_0426(gr)
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    f = max(0.05, float(factor))
    nx1 = _compat_0434(self, cx + (x1 - cx) * f)
    ny1 = _compat_0434(self, cy + (y1 - cy) * f)
    nx2 = _compat_0434(self, cx + (x2 - cx) * f)
    ny2 = _compat_0434(self, cy + (y2 - cy) * f)
    # Avoid collapsing non-zero geometry after snapping.
    step = _compat_0425(self)
    if abs(x2 - x1) > 1e-12 and abs(nx2 - nx1) < step:
        nx1, nx2 = _compat_0434(self, cx - step / 2.0), _compat_0434(self, cx + step / 2.0)
    if abs(y2 - y1) > 1e-12 and abs(ny2 - ny1) < step:
        ny1, ny2 = _compat_0434(self, cy - step / 2.0), _compat_0434(self, cy + step / 2.0)
    gr.x = nx1
    gr.y = ny1
    gr.w = nx2 - nx1
    gr.h = ny1 - ny2
    try:
        if getattr(gr, 'ctrl_x', None) is not None:
            gr.ctrl_x = float(gr.ctrl_x) * f
        if getattr(gr, 'ctrl_y', None) is not None:
            gr.ctrl_y = float(gr.ctrl_y) * f
        if getattr(gr, 'curve_radius', None) not in (None, 0, 0.0):
            gr.curve_radius = float(gr.curve_radius) * f
    except Exception:
        pass

def _compat_0427(self, items):
    for it in items:
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None and not bool(getattr(it.model, 'locked_to_body', False)):
                return True
        except Exception:
            pass
    return False

def _compat_0424(self, factor):
    changed = False
    for it in _compat_0433(self):
        try:
            kind = it.data(0)
            if kind == 'GRAPHIC' and getattr(it, 'model', None) is not None and not bool(getattr(it.model, 'locked_to_body', False)):
                _compat_0430(self, it.model, factor)
                changed = True
            elif kind in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY') and hasattr(it, 'scale_selected'):
                it.scale_selected(float(factor)); changed = True
            elif kind == 'PIN':
                # Pins must not be scaled by Scale +/-.
                continue
        except Exception as e:
            try: self.statusBar().showMessage(f'Scale failed: {e}', 5000)
            except Exception: pass
    if changed:
        try: self.update_current_unit_canvas_positions()
        except Exception:
            try: self.schedule_scene_refresh()
            except Exception: pass
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.rebuild_tree(); self.rebuild_pin_table()
        except Exception: pass
        try: self.refresh_properties()
        except Exception: pass
        try: self.view.viewport().update()
        except Exception: pass
    return changed

def _compat_0431(self, factor):
    try:
        if self._selected_body_active():
            return _compat_0428(self, factor) if _compat_0428 else None
    except Exception:
        pass
    sig = _compat_0371(self) if '_compat_0371' in globals() else []
    fs = _compat_0387(self) if '_compat_0387' in globals() else None
    try:
        self.set_tool(DrawTool.SELECT.value)
        self.push_undo_state()
        changed = _compat_0424(self, float(factor))
        if not changed and _compat_0428 is not None:
            return _compat_0428(self, factor)
        self.dirty = bool(changed) or getattr(self, 'dirty', False)
    finally:
        try:
            _compat_0381(self, sig=sig, filter_state=fs, force_body=False, refresh=False)
        except Exception:
            pass

def _compat_0438(graphics):
    pts = []
    for gr in graphics:
        pts.extend(_compat_0440(gr))
    if not pts:
        return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)

def _compat_0445(self, px, py, cx, cy, factor):
    return _compat_0449(self, cx + (float(px) - cx) * factor), _compat_0449(self, cy + (float(py) - cy) * factor)

def _compat_0446(self, factor):
    # Keep direct/legacy callers safe: convert relative factor to one grid step
    # direction for GRAPHIC selections. BODY path remains untouched.
    try:
        if self._selected_body_active():
            return _compat_0441(self, factor) if _compat_0441 else None
    except Exception:
        pass
    return _compat_0447(self, 1 if float(factor) >= 1.0 else -1)

def _compat_0454(graphics):
    pts = []
    for gr in graphics:
        pts.extend(_compat_0468(gr))
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)

def _compat_0472(self, px, py, cx, cy, factor):
    return _compat_0477(self, cx + (float(px) - cx) * factor), _compat_0477(self, cy + (float(py) - cy) * factor)

def _compat_0453(self, direction:int):
    graphics = _compat_0475(self, expand_groups=True)
    if not graphics:
        return False
    b = _compat_0454(graphics)
    if not b:
        return False
    minx, miny, maxx, maxy = b
    cur_w = abs(maxx - minx)
    cur_h = abs(maxy - miny)
    dominant = max(cur_w, cur_h, _compat_0478(self))
    inc = _compat_0464(self)
    new_dom = max(_compat_0478(self), dominant + (inc if int(direction) > 0 else -inc))
    factor = new_dom / dominant if dominant > 1e-12 else 1.0
    if abs(factor - 1.0) < 1e-12:
        return False
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    try:
        self.push_undo_state()
    except Exception:
        pass
    min_dim = _compat_0478(self)
    for gr in graphics:
        x = float(getattr(gr, 'x', 0.0) or 0.0)
        y = float(getattr(gr, 'y', 0.0) or 0.0)
        w = float(getattr(gr, 'w', 0.0) or 0.0)
        h = float(getattr(gr, 'h', 0.0) or 0.0)
        x2, y2 = x + w, y - h
        ctrl_abs = None
        try:
            if getattr(gr, 'ctrl_x', None) is not None and getattr(gr, 'ctrl_y', None) is not None:
                ctrl_abs = (x + float(gr.ctrl_x), y - float(gr.ctrl_y))
        except Exception:
            ctrl_abs = None
        nx1, ny1 = _compat_0472(self, x, y, cx, cy, factor)
        nx2, ny2 = _compat_0472(self, x2, y2, cx, cy, factor)
        nw = nx2 - nx1
        nh = ny1 - ny2
        # Keep every non-zero axis at least one edit-grid step. This is what
        # prevents Width from becoming 0/0.5 unexpectedly after snapping.
        if abs(w) > 1e-12 and abs(nw) < min_dim:
            sgn = 1.0 if w >= 0 else -1.0
            gcx = (nx1 + nx2) / 2.0
            nx1 = _compat_0477(self, gcx - sgn * min_dim / 2.0)
            nx2 = _compat_0477(self, gcx + sgn * min_dim / 2.0)
            nw = nx2 - nx1
        if abs(h) > 1e-12 and abs(nh) < min_dim:
            sgn = 1.0 if h >= 0 else -1.0
            gcy = (ny1 + ny2) / 2.0
            ny1 = _compat_0477(self, gcy + sgn * min_dim / 2.0)
            ny2 = _compat_0477(self, gcy - sgn * min_dim / 2.0)
            nh = ny1 - ny2
        gr.x, gr.y, gr.w, gr.h = nx1, ny1, nw, nh
        if ctrl_abs is not None:
            ncx, ncy = _compat_0472(self, ctrl_abs[0], ctrl_abs[1], cx, cy, factor)
            try:
                gr.ctrl_x = ncx - nx1
                gr.ctrl_y = ny1 - ncy
            except Exception:
                pass
        try:
            if getattr(gr, 'curve_radius', None) not in (None, 0, 0.0):
                gr.curve_radius = float(gr.curve_radius) * factor
        except Exception:
            pass
    try:
        self.dirty = True
        self.update_current_unit_canvas_positions()
    except Exception:
        try:
            self.schedule_scene_refresh()
        except Exception:
            pass
    try:
        self.refresh_properties()
    except Exception:
        pass
    try:
        self.rebuild_tree()
    except Exception:
        pass
    try:
        self.view.viewport().update()
    except Exception:
        pass
    return True

def _compat_0473(self, factor):
    try:
        if self._selected_body_active():
            return _compat_0470(self, factor) if _compat_0470 else None
    except Exception:
        pass
    try:
        return _compat_0474(self, 1 if float(factor) >= 1.0 else -1)
    except Exception:
        return _compat_0474(self, 1)

def _compat_0490(self):
    # Toolbar Scale +/- is deliberately a visible grid-size operation.  A 3x3
    # rectangle becomes 4x4, not 3.05x3.05 on small edit-grid settings.
    return max(1.0, _compat_0482(self))

def _compat_0479(self, direction):
    graphics = _compat_0493(self, expand_groups=True)
    if not graphics:
        return False
    bbox = _compat_0483(graphics)
    if not bbox:
        return False
    minx, miny, maxx, maxy = bbox
    cur_w = maxx - minx
    cur_h = maxy - miny
    inc = _compat_0490(self)
    min_size = _compat_0482(self)
    dominant = max(abs(cur_w), abs(cur_h), min_size)
    new_dominant = dominant + (inc if int(direction) > 0 else -inc)
    new_dominant = max(min_size, new_dominant)
    factor = new_dominant / dominant if dominant > 1e-12 else 1.0
    if abs(factor - 1.0) < 1e-12:
        return True

    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0
    try:
        self.push_undo_state()
    except Exception:
        pass

    for gr in graphics:
        x = float(getattr(gr, 'x', 0.0) or 0.0)
        y = float(getattr(gr, 'y', 0.0) or 0.0)
        w = float(getattr(gr, 'w', 0.0) or 0.0)
        h = float(getattr(gr, 'h', 0.0) or 0.0)

        # Object center in model coordinates.  For graphics, h grows downward on
        # screen, therefore center-y is y - h/2.
        gcx = x + w / 2.0
        gcy = y - h / 2.0
        ngcx = _compat_0495(self, cx + (gcx - cx) * factor)
        ngcy = _compat_0495(self, cy + (gcy - cy) * factor)

        shape = str(getattr(gr, 'shape', '') or '').lower()
        if shape in ('line', 'arc'):
            nw = _compat_0495(self, w * factor)
            nh = _compat_0495(self, h * factor)
            # A purely vertical/horizontal line may legitimately have one zero
            # axis.  Only keep the non-zero/originally dominant axis alive.
            if abs(w) > 1e-12 and abs(nw) < min_size:
                nw = min_size if w >= 0 else -min_size
            if abs(h) > 1e-12 and abs(nh) < min_size:
                nh = min_size if h >= 0 else -min_size
            gr.x = _compat_0495(self, ngcx - nw / 2.0)
            gr.y = _compat_0495(self, ngcy + nh / 2.0)
            gr.w = nw
            gr.h = nh
            try:
                if getattr(gr, 'ctrl_x', None) is not None:
                    gr.ctrl_x = _compat_0495(self, float(gr.ctrl_x) * factor)
                if getattr(gr, 'ctrl_y', None) is not None:
                    gr.ctrl_y = _compat_0495(self, float(gr.ctrl_y) * factor)
                if getattr(gr, 'curve_radius', None) not in (None, 0, 0.0):
                    gr.curve_radius = _compat_0495(self, float(gr.curve_radius) * factor)
            except Exception:
                pass
        else:
            sign_w = -1.0 if w < 0 else 1.0
            sign_h = -1.0 if h < 0 else 1.0
            nw_abs = max(min_size, abs(w) * factor)
            nh_abs = max(min_size, abs(h) * factor)
            nw = sign_w * _compat_0495(self, nw_abs)
            nh = sign_h * _compat_0495(self, nh_abs)
            # Snap can round small values down; enforce once more.
            if abs(nw) < min_size:
                nw = sign_w * min_size
            if abs(nh) < min_size:
                nh = sign_h * min_size
            gr.w = nw
            gr.h = nh
            gr.x = _compat_0495(self, ngcx - nw / 2.0)
            gr.y = _compat_0495(self, ngcy + nh / 2.0)

    try:
        self.dirty = True
    except Exception:
        pass
    try:
        self.update_current_unit_canvas_positions()
    except Exception:
        try:
            self.schedule_scene_refresh()
        except Exception:
            pass
    try:
        self.refresh_properties()
    except Exception:
        pass
    try:
        self.rebuild_tree()
    except Exception:
        pass
    try:
        self.view.viewport().update()
    except Exception:
        pass
    return True

def _compat_0491(self, factor):
    try:
        if self._selected_body_active():
            return _compat_0488(self, factor) if _compat_0488 else None
    except Exception:
        pass
    direction = 1
    try:
        direction = 1 if float(factor) >= 1.0 else -1
    except Exception:
        direction = 1
    return _compat_0492(self, direction)

def _compat_0498(self, direction:int):
    graphics = _compat_0518(self, expand_groups=True)
    if not graphics:
        return False
    b = _compat_0508(graphics)
    if not b:
        return False
    minx, miny, maxx, maxy = b
    cur_w = max(0.0, maxx - minx)
    cur_h = max(0.0, maxy - miny)
    min_size = _compat_0507(self)
    inc = _compat_0523(self)

    # BODY-like: width and height are stepped independently, then snapped.  This
    # guarantees a selected 3x3 rectangle becomes 4x4 and stays centered.
    target_w = max(min_size, _compat_0520(self, cur_w + (inc if int(direction) > 0 else -inc)))
    target_h = max(min_size, _compat_0520(self, cur_h + (inc if int(direction) > 0 else -inc)))
    sx = target_w / cur_w if cur_w > 1e-12 else 1.0
    sy = target_h / cur_h if cur_h > 1e-12 else 1.0
    if abs(sx - 1.0) < 1e-12 and abs(sy - 1.0) < 1e-12:
        return True

    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0
    try:
        self.push_undo_state()
    except Exception:
        pass

    for gr in graphics:
        x = float(getattr(gr, 'x', 0.0) or 0.0)
        y = float(getattr(gr, 'y', 0.0) or 0.0)
        w = float(getattr(gr, 'w', 0.0) or 0.0)
        h = float(getattr(gr, 'h', 0.0) or 0.0)
        shape = str(getattr(gr, 'shape', '') or '').lower()

        # Transform the object's own center relative to the selected logical
        # origin. For one object this origin is its own bbox center; for a group
        # it is the group's maximum x/y bbox center.
        gcx = x + w / 2.0
        gcy = y - h / 2.0
        ngcx = _compat_0520(self, cx + (gcx - cx) * sx)
        ngcy = _compat_0520(self, cy + (gcy - cy) * sy)

        nw = _compat_0520(self, w * sx)
        nh = _compat_0520(self, h * sy)
        if shape not in ('line', 'arc'):
            sw = -1.0 if w < 0 else 1.0
            sh = -1.0 if h < 0 else 1.0
            if abs(nw) < min_size:
                nw = sw * min_size
            if abs(nh) < min_size:
                nh = sh * min_size
        else:
            # Lines may be exactly vertical or horizontal. Preserve legitimate
            # zero axes, but never collapse an originally non-zero axis.
            if abs(w) > 1e-12 and abs(nw) < min_size:
                nw = (1.0 if w >= 0 else -1.0) * min_size
            if abs(h) > 1e-12 and abs(nh) < min_size:
                nh = (1.0 if h >= 0 else -1.0) * min_size
            try:
                if getattr(gr, 'ctrl_x', None) is not None:
                    gr.ctrl_x = _compat_0520(self, float(gr.ctrl_x) * sx)
                if getattr(gr, 'ctrl_y', None) is not None:
                    gr.ctrl_y = _compat_0520(self, float(gr.ctrl_y) * sy)
                if getattr(gr, 'curve_radius', None) not in (None, 0, 0.0):
                    gr.curve_radius = _compat_0520(self, float(gr.curve_radius) * sy)
            except Exception:
                pass

        gr.w = nw
        gr.h = nh
        gr.x = _compat_0520(self, ngcx - nw / 2.0)
        gr.y = _compat_0520(self, ngcy + nh / 2.0)

    try:
        self.dirty = True
    except Exception:
        pass
    try:
        self.update_current_unit_canvas_positions()
    except Exception:
        try:
            self.schedule_scene_refresh()
        except Exception:
            pass
    try:
        self.refresh_properties()
    except Exception:
        pass
    try:
        self.rebuild_tree()
    except Exception:
        pass
    try:
        self.view.viewport().update()
    except Exception:
        pass
    return True

def _compat_0516(self, factor):
    try:
        if self._selected_body_active():
            return _compat_0514(self, factor) if _compat_0514 else None
    except Exception:
        pass
    try:
        direction = 1 if float(factor) >= 1.0 else -1
    except Exception:
        direction = 1
    return _compat_0517(self, direction)

def _compat_0525(self, direction:int):
    models = _compat_0546(self, expand_groups=True)
    if not models:
        return False
    b = _compat_0530(models)
    if not b:
        return False
    minx, miny, maxx, maxy = b
    cur_w = maxx - minx; cur_h = maxy - miny
    if cur_w <= 1e-12 and cur_h <= 1e-12:
        return False
    # BODY-like proportional toolbar scaling: one logical grid unit per click,
    # but all resulting coordinates/dimensions hit the edit grid.
    dom = max(cur_w, cur_h, _compat_0529(self))
    target_dom = dom + (1.0 if int(direction) > 0 else -1.0)
    target_dom = max(_compat_0529(self), _compat_0547(self, target_dom))
    factor = target_dom / dom
    if abs(factor - 1.0) < 1e-12:
        return True
    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0
    min_dim = _compat_0529(self)
    try: self.push_undo_state()
    except Exception: pass
    for gr in models:
        try:
            x = float(getattr(gr, 'x', 0.0) or 0.0); y = float(getattr(gr, 'y', 0.0) or 0.0)
            w = float(getattr(gr, 'w', 0.0) or 0.0); h = float(getattr(gr, 'h', 0.0) or 0.0)
            shape = str(getattr(gr, 'shape', '') or '').lower()
            gcx = x + w / 2.0
            gcy = y - h / 2.0
            ngcx = _compat_0547(self, cx + (gcx - cx) * factor)
            ngcy = _compat_0547(self, cy + (gcy - cy) * factor)
            nw = _compat_0547(self, w * factor)
            nh = _compat_0547(self, h * factor)
            if shape not in ('line', 'arc'):
                if abs(nw) < min_dim: nw = (1.0 if nw >= 0 else -1.0) * min_dim
                if abs(nh) < min_dim: nh = (1.0 if nh >= 0 else -1.0) * min_dim
            else:
                # Lines/arcs may be vertical or horizontal. Preserve true zero axes.
                if abs(w) > 1e-12 and abs(nw) < min_dim: nw = (1.0 if w >= 0 else -1.0) * min_dim
                if abs(h) > 1e-12 and abs(nh) < min_dim: nh = (1.0 if h >= 0 else -1.0) * min_dim
                if getattr(gr, 'ctrl_x', None) is not None:
                    gr.ctrl_x = _compat_0547(self, float(gr.ctrl_x) * factor)
                if getattr(gr, 'ctrl_y', None) is not None:
                    gr.ctrl_y = _compat_0547(self, float(gr.ctrl_y) * factor)
                if getattr(gr, 'curve_radius', None) not in (None, 0, 0.0):
                    gr.curve_radius = _compat_0547(self, float(gr.curve_radius) * factor)
            gr.w = nw; gr.h = nh
            gr.x = _compat_0547(self, ngcx - nw / 2.0)
            gr.y = _compat_0547(self, ngcy + nh / 2.0)
        except Exception:
            pass
    try:
        self.dirty = True
        self.update_current_unit_canvas_positions()
    except Exception:
        try: self.schedule_scene_refresh()
        except Exception: pass
    try: _compat_0548(self)
    except Exception: pass
    try: self.refresh_properties(); self.rebuild_tree(); self.scene.update()
    except Exception: pass
    return True

def _compat_0543(self, factor):
    try:
        if self._selected_body_active():
            return _compat_0540(self, factor) if _compat_0540 else None
    except Exception:
        pass
    try: direction = 1 if float(factor) >= 1.0 else -1
    except Exception: direction = 1
    return _compat_0544(self, direction)

def _compat_0562(self, direction):
    models = _compat_0590(self, expand_groups=True)
    if not models:
        return False
    b = _compat_0576(models)
    if not b:
        return False
    minx, miny, maxx, maxy = b
    cur_w = maxx - minx; cur_h = maxy - miny
    dom = max(cur_w, cur_h, _compat_0568(self))
    target_dom = max(_compat_0568(self), _compat_0594(self, dom + (1.0 if int(direction) > 0 else -1.0)))
    factor = target_dom / dom if dom > 1e-12 else 1.0
    if abs(factor - 1.0) < 1e-12:
        return True
    ox, oy = _compat_0579(self, models)
    min_dim = _compat_0568(self)
    try: self.push_undo_state()
    except Exception: pass
    for gr in models:
        try:
            cx, cy = _compat_0577(gr)
            ncx = ox + (cx - ox) * factor
            ncy = oy + (cy - oy) * factor
            w = float(getattr(gr, 'w', 0.0) or 0.0); h = float(getattr(gr, 'h', 0.0) or 0.0)
            shape = str(getattr(gr, 'shape', '') or '').lower()
            nw = _compat_0594(self, w * factor)
            nh = _compat_0594(self, h * factor)
            if shape not in ('line', 'arc'):
                if abs(nw) < min_dim: nw = (1.0 if w >= 0 else -1.0) * min_dim
                if abs(nh) < min_dim: nh = (1.0 if h >= 0 else -1.0) * min_dim
            else:
                if abs(w) > 1e-12 and abs(nw) < min_dim: nw = (1.0 if w >= 0 else -1.0) * min_dim
                if abs(h) > 1e-12 and abs(nh) < min_dim: nh = (1.0 if h >= 0 else -1.0) * min_dim
                if getattr(gr, 'ctrl_x', None) is not None:
                    gr.ctrl_x = _compat_0594(self, float(gr.ctrl_x) * factor)
                if getattr(gr, 'ctrl_y', None) is not None:
                    gr.ctrl_y = _compat_0594(self, float(gr.ctrl_y) * factor)
                if getattr(gr, 'curve_radius', None) not in (None, 0, 0.0):
                    gr.curve_radius = _compat_0594(self, float(gr.curve_radius) * factor)
            gr.w = nw; gr.h = nh
            _compat_0593(gr, ncx, ncy)
        except Exception:
            pass
    try: self.dirty = True
    except Exception: pass
    _compat_0599(self)
    return True

def _compat_0561(self, deg):
    models = _compat_0590(self, expand_groups=True)
    if not models:
        return False
    ox, oy = _compat_0579(self, models)
    rad = math.radians(float(deg))
    c = math.cos(rad); s = math.sin(rad)
    try: self.push_undo_state()
    except Exception: pass
    for gr in models:
        try:
            cx, cy = _compat_0577(gr)
            dx, dy = cx - ox, cy - oy
            ncx = ox + dx * c - dy * s
            ncy = oy + dx * s + dy * c
            _compat_0593(gr, ncx, ncy)
            cur = float(getattr(gr, 'rotation', 0.0) or 0.0)
            gr.rotation = (round((cur + float(deg)) / 90.0) * 90.0) % 360.0
        except Exception:
            pass
    try: self.dirty = True
    except Exception: pass
    _compat_0599(self)
    return True

def _compat_0560(self, horizontal=True):
    models = _compat_0590(self, expand_groups=True)
    if not models:
        return False
    ox, oy = _compat_0579(self, models)
    try: self.push_undo_state()
    except Exception: pass
    for gr in models:
        try:
            cx, cy = _compat_0577(gr)
            if horizontal:
                ncx, ncy = ox - (cx - ox), cy
                gr.scale_x = -float(getattr(gr, 'scale_x', 1.0) or 1.0)
            else:
                ncx, ncy = cx, oy - (cy - oy)
                gr.scale_y = -float(getattr(gr, 'scale_y', 1.0) or 1.0)
            _compat_0593(gr, ncx, ncy)
        except Exception:
            pass
    try: self.dirty = True
    except Exception: pass
    _compat_0599(self)
    return True

def _compat_0564(self):
    try:
        if self._selected_body_active():
            return _compat_0580(self) if _compat_0580 else None
    except Exception:
        pass
    if _compat_0560(self, True):
        return None
    if _compat_0580:
        return _compat_0580(self)

def _compat_0565(self):
    try:
        if self._selected_body_active():
            return _compat_0581(self) if _compat_0581 else None
    except Exception:
        pass
    if _compat_0560(self, False):
        return None
    if _compat_0581:
        return _compat_0581(self)

def _compat_0982(self, unit=None):
    """Return real graphics that visually form the BODY.

    Imported/template symbols must not have a proxy rectangle.  The imported
    primitives themselves are the BODY.  User-added graphics stay separate and
    therefore are excluded.
    """
    try:
        u = unit or self.current_unit
        imported = _compat_0988(self, u)
        out = []
        for g in getattr(u, 'graphics', []) or []:
            role = str(getattr(g, 'graphic_role', '')).lower()
            raw = str(getattr(g, 'mentor_raw', '') or '')
            if raw == '__USER_GRAPHIC__' or role == 'user_graphic':
                continue
            if imported or getattr(g, 'locked_to_body', False) or role in ('body','template_body','imported_body'):
                out.append(g)
        return out
    except Exception:
        return []

def _compat_0987(g):
    x = float(getattr(g, 'x', 0.0) or 0.0)
    y = float(getattr(g, 'y', 0.0) or 0.0)
    w = float(getattr(g, 'w', 0.0) or 0.0)
    h = float(getattr(g, 'h', 0.0) or 0.0)
    xs = [x, x + w]
    ys = [y, y - h]
    try:
        if getattr(g, 'shape', '') == 'ellipse':
            pass
    except Exception:
        pass
    return min(xs), min(ys), max(xs), max(ys)

def _compat_0983(self, unit=None):
    gs = _compat_0982(self, unit)
    if not gs:
        b = (unit or self.current_unit).body
        return (float(b.x), float(b.y), float(b.width), float(b.height))
    mins = [_compat_0987(g) for g in gs]
    xmin = min(v[0] for v in mins); ymin = min(v[1] for v in mins)
    xmax = max(v[2] for v in mins); ymax = max(v[3] for v in mins)
    # Body model uses top-left y and positive height downward in this tool.
    return (_compat_0985(self, xmin), _compat_0985(self, ymax), _compat_0985(self, xmax - xmin), _compat_0985(self, ymax - ymin))

def _compat_1000(self, unit=None):
    u = unit or self.current_unit
    try:
        x, y, w, h = _compat_0983(self, u)
        u.body.x, u.body.y, u.body.width, u.body.height = x, y, max(_compat_0986(self), w), max(_compat_0986(self), h)
    except Exception:
        pass

def _compat_0996(self, unit, old_bounds, new_bounds):
    gs = _compat_0982(self, unit)
    if not gs:
        return
    ox, oy, ow, oh = old_bounds
    nx, ny, nw, nh = new_bounds
    ow, oh = max(float(ow), 1e-9), max(float(oh), 1e-9)
    sx, sy = float(nw) / ow, float(nh) / oh
    for g in gs:
        gx = float(getattr(g, 'x', 0.0) or 0.0)
        gy = float(getattr(g, 'y', 0.0) or 0.0)
        gw = float(getattr(g, 'w', 0.0) or 0.0)
        gh = float(getattr(g, 'h', 0.0) or 0.0)
        # map top-left anchor and dimensions; keep sign of w/h.
        g.x = _compat_0985(self, nx + (gx - ox) * sx)
        g.y = _compat_0985(self, ny - (oy - gy) * sy)
        g.w = _compat_0985(self, gw * sx)
        g.h = _compat_0985(self, gh * sy)
        try:
            if getattr(g, 'ctrl_x', None) is not None:
                g.ctrl_x = _compat_0985(self, float(g.ctrl_x) * sx)
            if getattr(g, 'ctrl_y', None) is not None:
                g.ctrl_y = _compat_0985(self, float(g.ctrl_y) * sy)
        except Exception:
            pass
    _compat_1000(self, unit)

def _compat_0984(self, unit=None):
    u = unit or self.current_unit
    b = u.body
    return {
        'x': float(b.x), 'y': float(b.y), 'w': float(b.width), 'h': float(b.height),
        'pins': [(p, float(p.x), float(p.y), float(getattr(p, 'length', 1.0) or 1.0)) for p in getattr(u, 'pins', []) or []],
        'texts': [(t, float(t.x), float(t.y)) for t in getattr(u, 'texts', []) or []],
        'attributes': [(t, float(t.x), float(t.y)) for t in (getattr(b, 'attribute_texts', {}) or {}).values()],
        'graphics': [(g, float(g.x), float(g.y), float(getattr(g, 'w', 0.0) or 0.0), float(getattr(g, 'h', 0.0) or 0.0)) for g in getattr(u, 'graphics', []) or [] if g not in _compat_0982(self, u)],
    }

def _compat_0993(self, new_w=None, new_h=None, refresh=True):
    if getattr(self, '_compat_0994', False):
        return
    self._compat_0994 = True
    try:
        u = self.current_unit
        b = u.body
        step = _compat_0986(self)
        old_bounds = _compat_0983(self, u)
        ox, oy, ow, oh = old_bounds
        new_w = max(step, _compat_0999(self, ow if new_w is None else new_w))
        new_h = max(step, _compat_0999(self, oh if new_h is None else new_h))
        start = _compat_0984(self, u)
        # Keep the current BODY top-left anchor. Origin handling is done by Origin Reset;
        # resize itself is deterministic and edit-grid based.
        new_bounds = (ox, oy, new_w, new_h)
        if _compat_0982(self, u):
            _compat_0996(self, u, old_bounds, new_bounds)
        else:
            b.x, b.y, b.width, b.height = ox, oy, new_w, new_h
        # BODY scale does not scale pins. It only redocks them to the new edge/grid.
        _compat_0992(self, u, start, old_bounds, (b.x, b.y, b.width, b.height))
        # Attached non-pin texts/attributes follow position proportionally; glyph size is unchanged.
        nx, ny, nw, nh = float(b.x), float(b.y), float(b.width), float(b.height)
        sx, sy = nw / max(ow, 1e-9), nh / max(oh, 1e-9)
        def map_pos(x, y):
            return (_compat_0999(self, nx + (float(x)-ox)*sx), _compat_0999(self, ny - (oy-float(y))*sy))
        for t, tx, ty in start.get('texts', []) or []:
            t.x, t.y = map_pos(tx, ty)
        for t, tx, ty in start.get('attributes', []) or []:
            t.x, t.y = map_pos(tx, ty)
        for g, gx, gy, gw, gh in start.get('graphics', []) or []:
            g.x, g.y = map_pos(gx, gy)
            g.w, g.h = gw, gh
        try:
            if hasattr(u, '_body_group_transform'):
                delattr(u, '_body_group_transform')
        except Exception:
            pass
        self.dirty = True
    finally:
        self._compat_0994 = False
    if refresh:
        try: self.update_current_unit_canvas_positions()
        except Exception: pass
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.rebuild_tree(); self.rebuild_pin_table()
        except Exception: pass
        try: self.refresh_properties()
        except Exception: pass
        try: self.schedule_scene_refresh(visual_only=True)
        except Exception:
            try: self.scene.update()
            except Exception: pass

def _compat_1001(self, op, value=None, refresh=True):
    if op in ('scale', 'scale_x_to', 'scale_y_to'):
        b = self.current_unit.body
        cur_w = float(getattr(b, 'width', 1.0) or 1.0)
        cur_h = float(getattr(b, 'height', 1.0) or 1.0)
        if op == 'scale_x_to':
            return _compat_0993(self, new_w=float(value), new_h=None, refresh=refresh)
        if op == 'scale_y_to':
            return _compat_0993(self, new_w=None, new_h=float(value), refresh=refresh)
        f = float(value or 1.0)
        return _compat_0993(self, new_w=cur_w * f, new_h=cur_h * f, refresh=refresh)
    # Delegate rotate/flip to the already working Symbol1-like implementation.
    try:
        return _compat_0991(self, op, value, refresh)
    except Exception:
        if '_compat_0076' in globals() and _compat_0076 is not None:
            return _compat_0076(self, op, value, refresh)

def _compat_0995(self, start_state, body):
    # Canvas handle resize. BodyItem has already changed body.x/y/width/height;
    # use that as requested target and apply the exact same resize pipeline to
    # the real BODY graphics. This enables canvas scaling for imported/template bodies.
    try:
        u = self.current_unit
        old_bounds = (float(start_state.get('x', body.x)), float(start_state.get('y', body.y)),
                      max(float(start_state.get('w', body.width)), 1e-9), max(float(start_state.get('h', body.height)), 1e-9))
        new_w = max(_compat_0986(self), _compat_0999(self, float(body.width)))
        new_h = max(_compat_0986(self), _compat_0999(self, float(body.height)))
        new_bounds = (_compat_0999(self, float(body.x)), _compat_0999(self, float(body.y)), new_w, new_h)
        if _compat_0982(self, u):
            _compat_0996(self, u, old_bounds, new_bounds)
        else:
            body.x, body.y, body.width, body.height = new_bounds
        _compat_0992(self, u, start_state, old_bounds, (body.x, body.y, body.width, body.height))
        ox, oy, ow, oh = old_bounds; nx, ny, nw, nh = float(body.x), float(body.y), float(body.width), float(body.height)
        sx, sy = nw / max(ow, 1e-9), nh / max(oh, 1e-9)
        def map_pos(x, y):
            return (_compat_0999(self, nx + (float(x)-ox)*sx), _compat_0999(self, ny - (oy-float(y))*sy))
        for t, tx, ty in start_state.get('texts', []) or []:
            t.x, t.y = map_pos(tx, ty)
        for t, tx, ty in start_state.get('attributes', []) or []:
            t.x, t.y = map_pos(tx, ty)
        body_graphics = set(_compat_0982(self, u))
        for gr, gx, gy, gw, gh in start_state.get('graphics', []) or []:
            if gr in body_graphics:
                continue
            gr.x, gr.y = map_pos(gx, gy)
            gr.w, gr.h = gw, gh
        self.dirty = True
    except Exception as e:
        try: self.statusBar().showMessage(f'Canvas BODY scale failed: {e}', 4000)
        except Exception: pass

def _compat_0998(self, body, attr, value):
    if attr not in ('line_style', 'line_width', 'color'):
        return
    self.push_undo_state()
    setattr(body, attr, tuple(value) if attr == 'color' else value)
    for gr in _compat_0982(self, self.current_unit):
        st = getattr(gr, 'style', None)
        if st is None: continue
        if attr == 'line_style': st.line_style = value
        elif attr == 'line_width': st.line_width = float(value)
        elif attr == 'color': st.stroke = tuple(value)
    self.dirty = True
    try: self.update_current_unit_canvas_positions()
    except Exception: pass
    self.schedule_scene_refresh(visual_only=True)

def _compat_1002(self):
    # For graphics the previous H/V mapping was inverted on the canvas.  Use the
    # opposite geometric axis for GRAPHIC-only/group selections while leaving BODY
    # transforms untouched. Plain TEXT falls through to the normal item-local path.
    try:
        if not self._selected_body_active() and _compat_1011(self):
            if '_compat_0560' in globals() and _compat_0560(self, False):
                return None
    except Exception:
        pass
    return _compat_1009(self) if _compat_1009 else None

def _compat_1003(self):
    try:
        if not self._selected_body_active() and _compat_1011(self):
            if '_compat_0560' in globals() and _compat_0560(self, True):
                return None
    except Exception:
        pass
    return _compat_1010(self) if _compat_1010 else None

def _compat_1004(self):
    try:
        return _compat_1007(self)
    except Exception:
        return None

def _compat_1005(self):
    try:
        return _compat_1006(self)
    except Exception:
        return None

def _compat_1022(st):
    try:
        if isinstance(st, dict):
            base = st.get('base')
            if isinstance(base, dict):
                # Only BODY attributes and pin-owned attribute_texts belong to
                # BODY/PIN transforms. Plain unit.texts are free objects.
                base['texts'] = []
        return st
    except Exception:
        return st

def _compat_1013(self, unit=None):
    if _compat_1015 is None:
        return None
    st = _compat_1015(self, unit)
    return _compat_1022(st)

def _compat_1014(self, unit=None):
    if _compat_1016 is None:
        return _compat_1013(self, unit)
    st = _compat_1016(self, unit)
    return _compat_1022(st)

def _compat_1021(self, start_state, body):
    # Reuse the existing BODY resize behaviour, but remove free/plain texts from
    # the resize state so they stay exactly where they are.  Attribute texts are
    # still passed via the separate 'attributes' entry.
    try:
        if isinstance(start_state, dict):
            start_state = dict(start_state)
            start_state['texts'] = []
    except Exception:
        pass
    if _compat_1018 is not None:
        return _compat_1018(self, start_state, body)

def _compat_1026(self, dx: float, dy: float, source_body=None):
    u = self.current_unit
    try:
        self._invalidate_body_group_transform_cache(u)
    except Exception:
        pass
    # BODY move carries pins, pin-owned texts, BODY attributes and BODY graphics.
    # It deliberately does NOT carry free/plain unit.texts.
    for p in getattr(u, 'pins', []) or []:
        p.x += dx; p.y += dy
        try: self._move_pin_owned_texts(p, dx, dy)
        except Exception: pass
    for t in (getattr(getattr(u, 'body', None), 'attribute_texts', {}) or {}).values():
        try:
            t.x += dx; t.y += dy
        except Exception:
            pass
    for g in getattr(u, 'graphics', []) or []:
        try:
            # Imported/body graphics belong to BODY. Free user graphics remain independent.
            if bool(getattr(g, 'locked_to_body', False)) or str(getattr(g, 'graphic_role', '') or '').lower() in ('body','template_body','imported_body'):
                g.x += dx; g.y += dy
        except Exception:
            pass

def _compat_1024(self, unit=None):
    st = _compat_1027(self, unit)
    try:
        if isinstance(st, dict) and isinstance(st.get('base'), dict):
            st['base']['texts'] = []
    except Exception:
        pass
    return st

def _compat_1025(self, unit=None):
    st = _compat_1028(self, unit)
    try:
        if isinstance(st, dict) and isinstance(st.get('base'), dict):
            st['base']['texts'] = []
    except Exception:
        pass
    return st

def _compat_1030(self, start_state, body):
    try:
        if isinstance(start_state, dict):
            start_state = dict(start_state)
            start_state['texts'] = []
            if isinstance(start_state.get('base'), dict):
                start_state['base'] = dict(start_state['base'])
                start_state['base']['texts'] = []
    except Exception:
        pass
    return _compat_1029(self, start_state, body)

def _compat_1046(self):
    items = _compat_1064(self, allow_active=True)
    if items:
        self.set_tool(DrawTool.SELECT.value)
        self.push_undo_state()
        for it in items:
            try: it.flip_horizontal()
            except Exception: pass
        _compat_1060(self, items)
        self.dirty = True
        return None
    return _compat_1050(self)

def _compat_1047(self):
    items = _compat_1064(self, allow_active=True)
    if items:
        self.set_tool(DrawTool.SELECT.value)
        self.push_undo_state()
        for it in items:
            try: it.flip_vertical()
            except Exception: pass
        _compat_1060(self, items)
        self.dirty = True
        return None
    return _compat_1051(self)

def _compat_1062(self, factor):
    items = _compat_1064(self, allow_active=True)
    if items:
        direction = 1 if float(factor) >= 1.0 else -1
        return _compat_1063(self, direction)
    return _compat_1057(self, factor)

def _compat_1076(g):
    try:
        role = str(getattr(g, 'graphic_role', '') or '').lower()
        return bool(getattr(g, 'locked_to_body', False)) or role in ('body', 'template_body', 'imported_body')
    except Exception:
        return False

def _compat_1080(self, start_state, body):
    start_state = start_state if isinstance(start_state, dict) else {}
    old_x = _compat_1075(start_state.get('x', getattr(body, 'x', 0.0)))
    old_y = _compat_1075(start_state.get('y', getattr(body, 'y', 0.0)))
    old_w = max(1e-9, abs(_compat_1075(start_state.get('w', getattr(body, 'width', 1.0)), 1.0)))
    old_h = max(1e-9, abs(_compat_1075(start_state.get('h', getattr(body, 'height', 1.0)), 1.0)))
    new_x = _compat_1081(self, getattr(body, 'x', old_x))
    new_y = _compat_1081(self, getattr(body, 'y', old_y))
    new_w = max(_compat_1074(self), _compat_1081(self, abs(_compat_1075(getattr(body, 'width', old_w), old_w))))
    new_h = max(_compat_1074(self), _compat_1081(self, abs(_compat_1075(getattr(body, 'height', old_h), old_h))))
    body.x, body.y, body.width, body.height = new_x, new_y, new_w, new_h
    dx = new_x - old_x
    dy = new_y - old_y
    sx = new_w / old_w
    sy = new_h / old_h

    # Pins are never scaled. They are re-docked to the BODY edges and centered /
    # distributed on those edges.
    _compat_1079(self, start_state, body)

    # Free text is not BODY-owned. BODY attributes are only translated as a block;
    # font size, rotation and inter-line spacing remain unchanged.
    for t, tx, ty in start_state.get('texts', []) or []:
        try:
            t.x = _compat_1081(self, _compat_1075(tx) + dx)
            t.y = _compat_1081(self, _compat_1075(ty) + dy)
        except Exception:
            pass
    for t, tx, ty in start_state.get('attributes', []) or []:
        try:
            t.x = _compat_1081(self, _compat_1075(tx) + dx)
            t.y = _compat_1081(self, _compat_1075(ty) + dy)
        except Exception:
            pass

    # Only graphics explicitly belonging to the imported/template BODY are scaled.
    # User graphics remain standalone objects.
    for gr, gx, gy, gw, gh in start_state.get('graphics', []) or []:
        try:
            if not _compat_1076(gr):
                continue
            gr.x = _compat_1081(self, new_x + (_compat_1075(gx) - old_x) * sx)
            gr.y = _compat_1081(self, new_y + (_compat_1075(gy) - old_y) * sy)
            gr.w = _compat_1081(self, _compat_1075(gw) * sx)
            gr.h = _compat_1081(self, _compat_1075(gh) * sy)
        except Exception:
            pass

def _compat_1085(self, tx, ty, old_bounds, new_bounds):
    ox, oy, ow, oh = old_bounds
    nx, ny, nw, nh = new_bounds
    old_left, old_right, old_top, old_bottom = ox, ox + ow, oy, oy - oh
    new_left, new_right, new_top, new_bottom = nx, nx + nw, ny, ny - nh
    old_cx, old_cy = ox + ow / 2.0, oy - oh / 2.0
    new_cx, new_cy = nx + nw / 2.0, ny - nh / 2.0
    tx = _compat_1075(tx); ty = _compat_1075(ty)
    tol = _compat_1074(self) * 0.51
    # Horizontal text tracking: text below/above the BODY follows the BODY center;
    # text clearly left/right of the BODY follows the corresponding edge.
    if tx < old_left - tol:
        dx = new_left - old_left
    elif tx > old_right + tol:
        dx = new_right - old_right
    else:
        dx = new_cx - old_cx
    # Vertical text tracking: text below/above follows the nearest outline edge;
    # text inside the BODY follows the center.  This keeps line spacing unchanged
    # while moving the whole text block naturally with the outline.
    if ty < old_bottom - tol:
        dy = new_bottom - old_bottom
    elif ty > old_top + tol:
        dy = new_top - old_top
    else:
        dy = new_cy - old_cy
    return dx, dy

def _compat_1084(self, start_state, body):
    start_state = start_state if isinstance(start_state, dict) else {}
    old_x = _compat_1075(start_state.get('x', getattr(body, 'x', 0.0)))
    old_y = _compat_1075(start_state.get('y', getattr(body, 'y', 0.0)))
    old_w = max(_compat_1074(self), abs(_compat_1075(start_state.get('w', getattr(body, 'width', 1.0)), 1.0)))
    old_h = max(_compat_1074(self), abs(_compat_1075(start_state.get('h', getattr(body, 'height', 1.0)), 1.0)))
    new_x = _compat_1081(self, getattr(body, 'x', old_x))
    new_y = _compat_1081(self, getattr(body, 'y', old_y))
    new_w = max(_compat_1074(self), _compat_1081(self, abs(_compat_1075(getattr(body, 'width', old_w), old_w))))
    new_h = max(_compat_1074(self), _compat_1081(self, abs(_compat_1075(getattr(body, 'height', old_h), old_h))))
    body.x, body.y, body.width, body.height = new_x, new_y, new_w, new_h
    old_bounds = (old_x, old_y, old_w, old_h)
    new_bounds = (new_x, new_y, new_w, new_h)
    sx = new_w / max(1e-9, old_w)
    sy = new_h / max(1e-9, old_h)

    # Pins: never scale length/font.  They are attached to the new outline.
    _compat_1083(self, start_state, body)

    # Texts/attributes: never scale, never alter line spacing.  Move each text
    # anchor by the delta of the outline region it belongs to.  This also covers
    # imported and template symbols because their body attributes use the same
    # TextModel anchors.
    for key in ('texts', 'attributes'):
        for t, tx, ty in start_state.get(key, []) or []:
            try:
                dx, dy = _compat_1085(self, tx, ty, old_bounds, new_bounds)
                t.x = _compat_1081(self, _compat_1075(tx) + dx)
                t.y = _compat_1081(self, _compat_1075(ty) + dy)
            except Exception:
                pass

    # BODY-owned/imported graphics form the BODY shape and are scaled with it.
    # Standalone graphics are not touched.
    for gr, gx, gy, gw, gh in start_state.get('graphics', []) or []:
        try:
            if not _compat_1076(gr):
                continue
            gr.x = _compat_1081(self, new_x + (_compat_1075(gx) - old_x) * sx)
            gr.y = _compat_1081(self, new_y + (_compat_1075(gy) - old_y) * sy)
            gr.w = max(_compat_1074(self), _compat_1081(self, _compat_1075(gw) * sx))
            gr.h = max(_compat_1074(self), _compat_1081(self, _compat_1075(gh) * sy))
        except Exception:
            pass

def _compat_1088(self, ax, ay, old_bounds, new_bounds):
    ox, oy, ow, oh = old_bounds
    nx, ny, nw, nh = new_bounds
    old_left, old_right, old_top, old_bottom = ox, ox + ow, oy, oy - oh
    new_left, new_right, new_top, new_bottom = nx, nx + nw, ny, ny - nh
    old_cx, old_cy = ox + ow / 2.0, oy - oh / 2.0
    new_cx, new_cy = nx + nw / 2.0, ny - nh / 2.0
    ax = _compat_1075(ax); ay = _compat_1075(ay)
    tol = max(_compat_1074(self), 1e-9) * 0.75
    if ax < old_left - tol:
        dx = new_left - old_left
    elif ax > old_right + tol:
        dx = new_right - old_right
    else:
        dx = new_cx - old_cx
    if ay < old_bottom - tol:
        dy = new_bottom - old_bottom
    elif ay > old_top + tol:
        dy = new_top - old_top
    else:
        dy = new_cy - old_cy
    return dx, dy

def _compat_1092(self, start_state, old_bounds, new_bounds):
    ox, oy, ow, oh = old_bounds
    nx, ny, nw, nh = new_bounds
    sx = nw / max(1e-9, ow)
    sy = nh / max(1e-9, oh)
    step = _compat_1074(self)
    for gr, gx, gy, gw, gh in (start_state or {}).get('graphics', []) or []:
        try:
            if not _compat_1076(gr):
                continue
            gr.x = _compat_1081(self, nx + (_compat_1075(gx) - ox) * sx)
            gr.y = _compat_1081(self, ny + (_compat_1075(gy) - oy) * sy)
            gr.w = max(step, _compat_1081(self, _compat_1075(gw) * sx))
            gr.h = max(step, _compat_1081(self, _compat_1075(gh) * sy))
        except Exception:
            pass

def _compat_1093(self, start_state, body):
    start_state = start_state if isinstance(start_state, dict) else {}
    step = _compat_1074(self)
    old_x = _compat_1075(start_state.get('x', getattr(body, 'x', 0.0)))
    old_y = _compat_1075(start_state.get('y', getattr(body, 'y', 0.0)))
    old_w = max(step, abs(_compat_1075(start_state.get('w', getattr(body, 'width', 1.0)), 1.0)))
    old_h = max(step, abs(_compat_1075(start_state.get('h', getattr(body, 'height', 1.0)), 1.0)))
    new_x = _compat_1081(self, getattr(body, 'x', old_x))
    new_y = _compat_1081(self, getattr(body, 'y', old_y))
    new_w = max(step, _compat_1081(self, abs(_compat_1075(getattr(body, 'width', old_w), old_w))))
    new_h = max(step, _compat_1081(self, abs(_compat_1075(getattr(body, 'height', old_h), old_h))))
    body.x, body.y, body.width, body.height = new_x, new_y, new_w, new_h
    old_bounds = (old_x, old_y, old_w, old_h)
    new_bounds = (new_x, new_y, new_w, new_h)

    # Order matters: graphics define BODY shape, then pins/texts are docked to
    # the final snapped outline.
    _compat_1092(self, start_state, old_bounds, new_bounds)
    _compat_1091(self, start_state, body)
    _compat_1087(self, start_state.get('attributes', []) or [], old_bounds, new_bounds)
    _compat_1087(self, start_state.get('texts', []) or [], old_bounds, new_bounds)

def _compat_1096(g):
    try:
        x = _compat_1075(getattr(g, 'x', 0.0))
        y = _compat_1075(getattr(g, 'y', 0.0))
        w = _compat_1075(getattr(g, 'w', getattr(g, 'width', 0.0)))
        h = _compat_1075(getattr(g, 'h', getattr(g, 'height', 0.0)))
        xs = [x, x + w]
        ys = [y, y - h]
        return min(xs), max(ys), max(xs), min(ys)   # left, top, right, bottom
    except Exception:
        return None

def _compat_1102(self, unit, body):
    """Return left, top, right, bottom of the visible BODY outline in grid units."""
    try:
        body_graphics = [g for g in (getattr(unit, 'graphics', []) or []) if _compat_1076(g)]
    except Exception:
        body_graphics = []
    bounds = []
    for g in body_graphics:
        b = _compat_1096(g)
        if b is not None:
            bounds.append(b)
    if bounds:
        left = min(b[0] for b in bounds)
        top = max(b[1] for b in bounds)
        right = max(b[2] for b in bounds)
        bottom = min(b[3] for b in bounds)
        # Guard against degenerate imported primitives; fall back to body rect.
        if abs(right - left) > 1e-9 and abs(top - bottom) > 1e-9:
            return left, top, right, bottom
    x = _compat_1075(getattr(body, 'x', 0.0))
    y = _compat_1075(getattr(body, 'y', 0.0))
    w = abs(_compat_1075(getattr(body, 'width', 1.0), 1.0))
    h = abs(_compat_1075(getattr(body, 'height', 1.0), 1.0))
    return x, y, x + w, y - h

def _compat_1098(self, start_state, body):
    # First run the harmonized v88 path to scale body graphics/text from the
    # immutable start snapshot.  Then re-anchor pins to the visible final outline
    # so Symbol 1, imported symbols and Template Editor symbols behave identically.
    _compat_1093(self, start_state, body)
    _compat_1097(self, start_state, body)
    try:
        self.update_current_unit_canvas_positions()
    except Exception:
        pass

def _compat_1104(unit):
    out = []
    try:
        for g in getattr(unit, 'graphics', []) or []:
            if _compat_1076(g):
                out.append(g)
    except Exception:
        pass
    return out

def _compat_1108(body):
    x = _compat_1075(getattr(body, 'x', 0.0))
    y = _compat_1075(getattr(body, 'y', 0.0))
    w = abs(_compat_1075(getattr(body, 'width', 1.0), 1.0))
    h = abs(_compat_1075(getattr(body, 'height', 1.0), 1.0))
    return x, y, x + w, y - h  # left, top, right, bottom

def _compat_1117(self, unit, body):
    bounds = []
    for g in _compat_1104(unit):
        b = _compat_1106(g)
        if b is not None:
            bounds.append(b)
    if bounds:
        l = min(v[0] for v in bounds); t = max(v[1] for v in bounds)
        r = max(v[2] for v in bounds); b = min(v[3] for v in bounds)
        if abs(r - l) > 1e-9 and abs(t - b) > 1e-9:
            return l, t, r, b
    return _compat_1108(body)

def _compat_1103(self, start_state, body):
    u = _compat_1116(self)
    if u is None:
        return
    step = _compat_1114(self)
    old_left, old_top, old_right, old_bottom = (start_state or {}).get('outline') or _compat_1108(body)
    old_w = max(step, abs(old_right - old_left))
    old_h = max(step, abs(old_top - old_bottom))
    # BodyItem has already set body.x/y/width/height during canvas resize.
    # Treat that as target logical outline for both native BODY and imported
    # BODY artwork.
    new_left = _compat_1112(self, getattr(body, 'x', old_left))
    new_top = _compat_1112(self, getattr(body, 'y', old_top))
    new_w = max(step, _compat_1112(self, abs(_compat_1075(getattr(body, 'width', old_w), old_w))))
    new_h = max(step, _compat_1112(self, abs(_compat_1075(getattr(body, 'height', old_h), old_h))))
    body.x, body.y, body.width, body.height = new_left, new_top, new_w, new_h
    sx = new_w / old_w
    sy = new_h / old_h

    # Scale only BODY-owned graphics. Standalone user graphics are untouched.
    has_body_graphics = False
    for gr, gx, gy, gw, gh in (start_state or {}).get('graphics', []) or []:
        try:
            if not _compat_1076(gr):
                continue
            has_body_graphics = True
            gr.x = _compat_1112(self, new_left + (_compat_1075(gx) - old_left) * sx)
            gr.y = _compat_1112(self, new_top + (_compat_1075(gy) - old_top) * sy)
            gr.w = max(step, _compat_1112(self, _compat_1075(gw) * sx))
            gr.h = max(step, _compat_1112(self, _compat_1075(gh) * sy))
        except Exception:
            pass

    if has_body_graphics:
        # Body model follows the visible artwork after snapping.
        try:
            l, t, r, btm = _compat_1117(self, u, body)
            body.x = _compat_1112(self, l); body.y = _compat_1112(self, t)
            body.width = max(step, _compat_1112(self, r - l))
            body.height = max(step, _compat_1112(self, t - btm))
        except Exception:
            pass

def _compat_1110(self, start_state, body):
    if not isinstance(start_state, dict) or 'outline' not in start_state:
        start_state = _compat_1113(self, body)
    old_outline = start_state.get('outline') or _compat_1108(body)
    _compat_1103(self, start_state, body)
    new_outline = _compat_1117(self, _compat_1116(self), body)
    _compat_1109(self, start_state, body)
    _compat_1107(self, start_state.get('attributes', []) or [], old_outline, new_outline)
    _compat_1107(self, start_state.get('texts', []) or [], old_outline, new_outline)
    try:
        self.update_current_unit_canvas_positions()
    except Exception:
        try: self.scene.update(); self.view.viewport().update()
        except Exception: pass

def _compat_1121(self, unit, g):
    try:
        if g is None or _compat_1122(g):
            return False
        role = str(getattr(g, 'graphic_role', '') or '').lower()
        raw = str(getattr(g, 'mentor_raw', '') or '')
        if getattr(g, 'locked_to_body', False) or role in ('body', 'template_body', 'imported_body'):
            return True
        attrs = getattr(getattr(unit, 'body', None), 'attributes', {}) or {}
        if str(attrs.get('MENTOR_GRAPHICS_AS_BODY', '0')) == '1':
            return True
        if str(attrs.get('MENTOR_BODY_GRAPHICS_LOCKED', '0')) == '1':
            return True
        if str(attrs.get('MENTOR_HAS_BODY', '0')) == '1' and raw != '__USER_GRAPHIC__':
            return True
        # Template editor/importer often restores old template body primitives
        # without role fields.  In these contexts the template unit contains the
        # body artwork as graphics; user-added graphics are explicitly marked.
        if getattr(self, 'is_template_editor', False) and raw != '__USER_GRAPHIC__':
            return True
        if raw and raw != '__USER_GRAPHIC__' and role != 'user_graphic':
            return True
    except Exception:
        pass
    return False

def _compat_1119(self, unit):
    out = []
    try:
        for g in getattr(unit, 'graphics', []) or []:
            if _compat_1121(self, unit, g):
                out.append(g)
    except Exception:
        pass
    return out

def _compat_1128(self, unit, body):
    bounds = []
    try:
        for g in _compat_1119(self, unit):
            b = _compat_1106(g)
            if b is not None:
                bounds.append(b)
    except Exception:
        pass
    if bounds:
        l = min(v[0] for v in bounds); t = max(v[1] for v in bounds)
        r = max(v[2] for v in bounds); b = min(v[3] for v in bounds)
        if abs(r - l) > 1e-9 and abs(t - b) > 1e-9:
            return l, t, r, b
    return _compat_1108(body)

def _compat_1118(self, start_state, body):
    u = _compat_1116(self)
    if u is None:
        return
    step = _compat_1114(self)
    old_left, old_top, old_right, old_bottom = (start_state or {}).get('outline') or _compat_1108(body)
    old_w = max(step, abs(old_right - old_left)); old_h = max(step, abs(old_top - old_bottom))
    new_left = _compat_1112(self, getattr(body, 'x', old_left))
    new_top = _compat_1112(self, getattr(body, 'y', old_top))
    new_w = max(step, _compat_1112(self, abs(_compat_1075(getattr(body, 'width', old_w), old_w))))
    new_h = max(step, _compat_1112(self, abs(_compat_1075(getattr(body, 'height', old_h), old_h))))
    body.x, body.y, body.width, body.height = new_left, new_top, new_w, new_h
    sx = new_w / old_w; sy = new_h / old_h
    has_body_graphics = False
    for gr, gx, gy, gw, gh in (start_state or {}).get('graphics', []) or []:
        try:
            if not _compat_1121(self, u, gr):
                continue
            has_body_graphics = True
            gr.x = _compat_1112(self, new_left + (_compat_1075(gx) - old_left) * sx)
            gr.y = _compat_1112(self, new_top + (_compat_1075(gy) - old_top) * sy)
            gr.w = max(step, _compat_1112(self, _compat_1075(gw) * sx))
            gr.h = max(step, _compat_1112(self, _compat_1075(gh) * sy))
            try:
                gr.locked_to_body = True
                if not str(getattr(gr, 'graphic_role', '') or ''):
                    gr.graphic_role = 'template_body' if getattr(self, 'is_template_editor', False) else 'imported_body'
            except Exception:
                pass
        except Exception:
            pass
    if has_body_graphics:
        try:
            l, t, r, btm = _compat_1128(self, u, body)
            body.x = _compat_1112(self, l); body.y = _compat_1112(self, t)
            body.width = max(step, _compat_1112(self, r - l))
            body.height = max(step, _compat_1112(self, t - btm))
        except Exception:
            pass

def _compat_1124(self, start_state, body):
    if not isinstance(start_state, dict) or 'outline' not in start_state:
        start_state = _compat_1126(self, body)
    old_outline = start_state.get('outline') or _compat_1108(body)
    _compat_1118(self, start_state, body)
    new_outline = _compat_1128(self, _compat_1116(self), body)
    _compat_1123(self, start_state, body)
    _compat_1107(self, start_state.get('attributes', []) or [], old_outline, new_outline)
    _compat_1107(self, start_state.get('texts', []) or [], old_outline, new_outline)
    try:
        self.update_current_unit_canvas_positions()
    except Exception:
        try: self.scene.update(); self.view.viewport().update()
        except Exception: pass

def _compat_1127(self, op, value=None, refresh=True):
    if op not in ('scale', 'scale_x_to', 'scale_y_to'):
        try:
            return _compat_1078(self, op, value, refresh)
        except Exception:
            return None
    u = _compat_1116(self)
    if u is None:
        return None
    body = u.body
    st = _compat_1126(self, body)
    old_l, old_t, old_r, old_b = st.get('outline') or _compat_1108(body)
    old_w = max(_compat_1114(self), abs(old_r - old_l)); old_h = max(_compat_1114(self), abs(old_t - old_b))
    if op == 'scale_x_to':
        new_w = max(_compat_1114(self), _compat_1112(self, value)); new_h = old_h
    elif op == 'scale_y_to':
        new_w = old_w; new_h = max(_compat_1114(self), _compat_1112(self, value))
    else:
        f = _compat_1075(value, 1.0)
        new_w = max(_compat_1114(self), _compat_1112(self, old_w * f)); new_h = max(_compat_1114(self), _compat_1112(self, old_h * f))
    cx, cy = (old_l + old_r) / 2.0, (old_t + old_b) / 2.0
    body.x = _compat_1112(self, cx - new_w / 2.0); body.y = _compat_1112(self, cy + new_h / 2.0)
    body.width = new_w; body.height = new_h
    _compat_1124(self, st, body)
    if refresh:
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.schedule_scene_refresh(visual_only=True)
        except Exception: pass
        try: QTimer.singleShot(0, self.refresh_properties)
        except Exception: pass
    return None

def _compat_1130(unit, source='template'):
    try:
        if unit is None or getattr(unit, 'body', None) is None:
            return unit
        attrs = getattr(unit.body, 'attributes', None)
        if attrs is None:
            unit.body.attributes = {}; attrs = unit.body.attributes
        # Rebuild_scene in this code base checks the Mentor flags for the
        # imported/template body proxy path. Set both the explicit template flag
        # and the generic body-graphics flags so every older code path agrees.
        attrs['TEMPLATE_GRAPHICS_AS_BODY'] = '1'
        attrs['MENTOR_GRAPHICS_AS_BODY'] = '1'
        attrs['MENTOR_BODY_GRAPHICS_LOCKED'] = '1'
        role = 'template_body' if str(source).lower().startswith('template') else 'imported_body'
        for g in getattr(unit, 'graphics', []) or []:
            try:
                marker = str(getattr(g, 'mentor_raw', '') or '')
                old_role = str(getattr(g, 'graphic_role', '') or '').lower()
                if marker == '__USER_GRAPHIC__' or old_role == 'user_graphic':
                    g.graphic_role = 'user_graphic'
                    g.locked_to_body = False
                else:
                    g.graphic_role = role
                    g.locked_to_body = True
            except Exception:
                pass
    except Exception:
        pass
    return unit

def _compat_1135(win, unit, body):
    try:
        if '_compat_1128' in globals():
            l, t, r, b = _compat_1128(win, unit, body)
            return (_compat_1143(win, l), _compat_1143(win, t), _compat_1143(win, r), _compat_1143(win, b))
    except Exception:
        pass
    l = _compat_1138(getattr(body, 'x', 0.0))
    t = _compat_1138(getattr(body, 'y', 0.0))
    r = l + _compat_1138(getattr(body, 'width', 1.0), 1.0)
    b = t - _compat_1138(getattr(body, 'height', 1.0), 1.0)
    return (_compat_1143(win, l), _compat_1143(win, t), _compat_1143(win, r), _compat_1143(win, b))

def _compat_1157(self):
    try:
        items = list(self.scene.selectedItems())
    except Exception:
        return []
    out = []
    for it in items:
        try:
            kind = it.data(0)
            if kind in ('PIN', 'TEXT', 'GRAPHIC', 'ATTR_REF_DES', 'ATTR_BODY') and getattr(it, 'model', None) is not None:
                out.append(it)
        except Exception:
            pass
    return out

def _compat_1156(self):
    """BODY group transform is active only for a pure BODY selection.

    If any PIN is selected, transforms are object-local.  This intentionally
    protects pin-only selections from accidental BODY proxy selections caused by
    overlapping hit areas.
    """
    try:
        selected = list(self.scene.selectedItems())
    except Exception:
        return False
    if not selected:
        return False
    kinds = []
    for it in selected:
        try:
            kinds.append(it.data(0))
        except Exception:
            pass
    if 'PIN' in kinds:
        return False
    body_kinds = {'BODY', 'BODY_GRAPHIC'}
    relevant = [k for k in kinds if k in body_kinds or k in ('TEXT', 'GRAPHIC', 'ATTR_REF_DES', 'ATTR_BODY')]
    return bool(relevant) and all(k in body_kinds for k in relevant)

def _compat_1146(self, op, value=None):
    items = _compat_1157(self)
    if not items:
        return False
    # Any selected PIN forces local-object mode for all selected non-BODY items.
    # This avoids rotating/flipping the BODY when the user intended pin edits.
    if not any(it.data(0) == 'PIN' for it in items):
        return False
    try:
        self.set_tool(DrawTool.SELECT.value)
    except Exception:
        pass
    try:
        self.push_undo_state()
    except Exception:
        pass
    selected_ids = {id(getattr(it, 'model', None)) for it in items if getattr(it, 'model', None) is not None}
    for it in items:
        try:
            if it.data(0) == 'PIN':
                # A manually transformed pin is intentionally detached from
                # automatic BODY redocking.
                it.model.auto_dock = False
            if op == 'rotate' and hasattr(it, 'rotate_by'):
                it.rotate_by(float(value or 0.0))
            elif op == 'flip_h' and hasattr(it, 'flip_horizontal'):
                it.flip_horizontal()
            elif op == 'flip_v' and hasattr(it, 'flip_vertical'):
                it.flip_vertical()
        except Exception:
            pass
    try:
        self._selection_restore_ids = selected_ids
        self.dirty = True
    except Exception:
        pass
    try:
        self.schedule_scene_refresh(visual_only=True)
    except Exception:
        try:
            self.update_current_unit_canvas_positions(); self.refresh_properties()
        except Exception:
            pass
    # Restore selection immediately as well; visual-only refresh may be deferred.
    try:
        for it in self.scene.items():
            m = getattr(it, 'model', None)
            if m is not None and id(m) in selected_ids:
                it.setSelected(True)
    except Exception:
        pass
    return True

def _compat_1147(self):
    if _compat_1146(self, 'flip_h'):
        return None
    if _compat_1150 is not None:
        return _compat_1150(self)
    return None

def _compat_1148(self):
    if _compat_1146(self, 'flip_v'):
        return None
    if _compat_1151 is not None:
        return _compat_1151(self)
    return None

def _compat_1161(g):
    x = float(getattr(g, 'x', 0.0) or 0.0)
    y = float(getattr(g, 'y', 0.0) or 0.0)
    w = float(getattr(g, 'w', 0.0) or 0.0)
    h = float(getattr(g, 'h', 0.0) or 0.0)
    xs = [x, x + w]
    ys = [y, y - h]
    try:
        if getattr(g, 'ctrl_x', None) is not None and getattr(g, 'ctrl_y', None) is not None:
            xs.append(x + float(g.ctrl_x))
            ys.append(y - float(g.ctrl_y))
    except Exception:
        pass
    try:
        r = float(getattr(g, 'curve_radius', 0.0) or 0.0)
        if abs(r) > 1e-12 and str(getattr(g, 'shape', '') or '') in ('line', 'arc'):
            # In GraphicItem.paint(), curve_radius is a local y offset from the
            # line midpoint. Convert that local point into model coordinates.
            xs.append(x + w / 2.0)
            ys.append(y - h / 2.0 + r)
    except Exception:
        pass
    return min(xs), min(ys), max(xs), max(ys)

def _compat_1163(self, graphics):
    gs = list(graphics or [])
    if not gs:
        return (0.0, 0.0, 1.0, 1.0)
    bds = [_compat_1161(g) for g in gs]
    xmin = min(b[0] for b in bds); ymin = min(b[1] for b in bds)
    xmax = max(b[2] for b in bds); ymax = max(b[3] for b in bds)
    return (_compat_1160(self, xmin), _compat_1160(self, ymax),
            _compat_1160(self, max(0.001, xmax - xmin)), _compat_1160(self, max(0.001, ymax - ymin)))

def _compat_1158(self, unit=None):
    try:
        return _compat_0982(self, unit)
    except Exception:
        u = unit or self.current_unit
        out = []
        for gr in getattr(u, 'graphics', []) or []:
            try:
                role = str(getattr(gr, 'graphic_role', '') or '').lower()
                raw = str(getattr(gr, 'mentor_raw', '') or '')
                if getattr(gr, 'locked_to_body', False) or role in ('body', 'template_body', 'imported_body') or (raw != '__USER_GRAPHIC__' and role != 'user_graphic'):
                    out.append(gr)
            except Exception:
                pass
        return out

def _compat_1159(self, unit=None):
    u = unit or self.current_unit
    gs = _compat_1158(self, u)
    if not gs:
        b = u.body
        return (float(b.x), float(b.y), max(0.001, float(b.width)), max(0.001, float(b.height)))
    return _compat_1163(self, gs)

def _compat_1164(self, x, y, old_bounds, new_bounds):
    ox, oy, ow, oh = old_bounds
    nx, ny, nw, nh = new_bounds
    ow = max(float(ow), 1e-12); oh = max(float(oh), 1e-12)
    sx = float(nw) / ow; sy = float(nh) / oh
    return (_compat_1160(self, float(nx) + (float(x) - float(ox)) * sx),
            _compat_1160(self, float(ny) - (float(oy) - float(y)) * sy))

def _compat_1168(self, graphics, old_bounds, new_bounds):
    ox, oy, ow, oh = old_bounds
    nx, ny, nw, nh = new_bounds
    sx = float(nw) / max(float(ow), 1e-12)
    sy = float(nh) / max(float(oh), 1e-12)
    for g in list(graphics or []):
        try:
            gx = float(getattr(g, 'x', 0.0) or 0.0)
            gy = float(getattr(g, 'y', 0.0) or 0.0)
            gw = float(getattr(g, 'w', 0.0) or 0.0)
            gh = float(getattr(g, 'h', 0.0) or 0.0)
            ax, ay = _compat_1164(self, gx, gy, old_bounds, new_bounds)
            ex, ey = _compat_1164(self, gx + gw, gy - gh, old_bounds, new_bounds)
            g.x = ax
            g.y = ay
            g.w = _compat_1160(self, ex - ax)
            g.h = _compat_1160(self, ay - ey)

            # Quadratic control point, if present, is a local vector from the
            # original anchor in model coordinates. Map the absolute control
            # point and convert it back into the new local vector.
            if getattr(g, 'ctrl_x', None) is not None and getattr(g, 'ctrl_y', None) is not None:
                cx_abs = gx + float(g.ctrl_x)
                cy_abs = gy - float(g.ctrl_y)
                ncx, ncy = _compat_1164(self, cx_abs, cy_abs, old_bounds, new_bounds)
                g.ctrl_x = _compat_1160(self, ncx - ax)
                g.ctrl_y = _compat_1160(self, ay - ncy)

            # curve_radius is the local vertical offset from the line midpoint.
            if getattr(g, 'curve_radius', None) is not None:
                g.curve_radius = _compat_1160(self, float(getattr(g, 'curve_radius', 0.0) or 0.0) * sy)
        except Exception:
            pass

def _compat_1169(self, factor):
    # Multi-selected graphics scale as one graphic group around their common
    # bounds, so the authored relative structure is preserved.  Single graphics
    # use GraphicItem.scale_by(), which is patched above for curves/control points.
    try:
        items = list(self.scene.selectedItems())
    except Exception:
        items = []
    graphics = [it for it in items if getattr(it, 'data', lambda *_: None)(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None]
    if graphics and len(graphics) == len(items):
        try:
            factor = float(factor)
        except Exception:
            factor = 1.0
        if len(graphics) == 1:
            try: graphics[0].scale_by(factor)
            except Exception: pass
            return None
        try: self.push_undo_state()
        except Exception: pass
        models = [it.model for it in graphics]
        old = _compat_1163(self, models)
        ox, oy, ow, oh = old
        cx = ox + ow / 2.0
        cy = oy - oh / 2.0
        nw = max(0.001, ow * factor)
        nh = max(0.001, oh * factor)
        new = (cx - nw / 2.0, cy + nh / 2.0, nw, nh)
        _compat_1168(self, models, old, new)
        try:
            self._selection_restore_ids = {id(m) for m in models}
            self.dirty = True
            self.update_current_unit_canvas_positions()
            self.schedule_scene_refresh(visual_only=True)
        except Exception:
            pass
        return None
    if _compat_1166 is not None:
        return _compat_1166(self, factor)
    for it in items:
        try:
            if hasattr(it, 'scale_by'):
                it.scale_by(float(factor))
        except Exception:
            pass
    return None

def _compat_1173(self, x, y, old_box, new_box):
    ox, oy, ow, oh = old_box
    nx, ny, nw, nh = new_box
    ow = max(abs(float(ow)), 1e-12)
    oh = max(abs(float(oh)), 1e-12)
    sx = float(nw) / ow
    sy = float(nh) / oh
    # Model coordinate convention: BODY y is top, positive height extends down,
    # therefore bottom is y-height.  Keep this convention explicit.
    mx = float(nx) + (float(x) - float(ox)) * sx
    my = float(ny) - (float(oy) - float(y)) * sy
    return _compat_1171(self, mx), _compat_1171(self, my)

def _compat_1178(self, gr, gx, gy, gw, gh, old_box, new_box):
    ax, ay = _compat_1173(self, gx, gy, old_box, new_box)
    ex, ey = _compat_1173(self, gx + gw, gy - gh, old_box, new_box)
    old_ctrl_x = getattr(gr, 'ctrl_x', None)
    old_ctrl_y = getattr(gr, 'ctrl_y', None)
    old_curve = getattr(gr, 'curve_radius', None)

    gr.x = ax
    gr.y = ay
    gr.w = _compat_1171(self, ex - ax)
    gr.h = _compat_1171(self, ay - ey)

    # Preserve line/arc/curve topology.  ctrl_x/ctrl_y are local vectors from
    # the graphic anchor; map the absolute control point and convert back.
    try:
        if old_ctrl_x is not None and old_ctrl_y is not None:
            cx_abs = float(gx) + float(old_ctrl_x)
            cy_abs = float(gy) - float(old_ctrl_y)
            ncx, ncy = _compat_1173(self, cx_abs, cy_abs, old_box, new_box)
            gr.ctrl_x = _compat_1171(self, ncx - ax)
            gr.ctrl_y = _compat_1171(self, ay - ncy)
    except Exception:
        pass

    try:
        if old_curve is not None:
            sx = float(new_box[2]) / max(abs(float(old_box[2])), 1e-12)
            sy = float(new_box[3]) / max(abs(float(old_box[3])), 1e-12)
            # Radius is a local offset.  For non-uniform resize use the dominant
            # local factor so arcs do not invert or collapse unpredictably.
            f = sy if abs(sy) >= abs(sx) else sx
            gr.curve_radius = _compat_1171(self, float(old_curve or 0.0) * f)
    except Exception:
        pass

def _compat_1177(self, start_state: dict, body: SymbolBodyModel):
    try:
        u = self.current_unit
    except Exception:
        if _compat_1175 is not None:
            return _compat_1175(self, start_state, body)
        return None

    old_x = _compat_1172(start_state.get('x', getattr(body, 'x', 0.0)), 0.0)
    old_y = _compat_1172(start_state.get('y', getattr(body, 'y', 0.0)), 0.0)
    old_w = max(1e-12, abs(_compat_1172(start_state.get('w', getattr(body, 'width', 1.0)), 1.0)))
    old_h = max(1e-12, abs(_compat_1172(start_state.get('h', getattr(body, 'height', 1.0)), 1.0)))

    # Snap BODY itself to the active edit grid and keep it as the only resize
    # source.  Canvas handles may create small float noise; remove it here.
    try:
        body.x = _compat_1171(self, _compat_1179(self, body.x))
        body.y = _compat_1171(self, _compat_1179(self, body.y))
        body.width = max(_compat_1172(getattr(self, 'edit_grid_step', 0.01), 0.01), _compat_1171(self, _compat_1179(self, body.width)))
        body.height = max(_compat_1172(getattr(self, 'edit_grid_step', 0.01), 0.01), _compat_1171(self, _compat_1179(self, body.height)))
    except Exception:
        pass

    new_box = (float(body.x), float(body.y), max(1e-12, float(body.width)), max(1e-12, float(body.height)))
    old_box = (old_x, old_y, old_w, old_h)

    # Pins: redock to new BODY edge, but keep their original vertical/horizontal
    # authored slot. This prevents canvas resize from walking pins up/down.
    for entry in list(start_state.get('pins', []) or []):
        try:
            p, px, py, plen = entry[:4]
            _compat_1176(self, p, float(px), float(py), float(plen), body)
        except Exception:
            pass

    # Normal texts and BODY attributes follow the BODY mapping once from the
    # immutable press-state.  This matches property Width/Height edits.
    for entry in list(start_state.get('texts', []) or []):
        try:
            t, tx, ty = entry[:3]
            t.x, t.y = _compat_1173(self, tx, ty, old_box, new_box)
        except Exception:
            pass
    for entry in list(start_state.get('attributes', []) or []):
        try:
            t, tx, ty = entry[:3]
            t.x, t.y = _compat_1173(self, tx, ty, old_box, new_box)
        except Exception:
            pass

    # Graphics: preserve actual shape topology by mapping anchor/end/control
    # points.  This covers line, rect, ellipse/circle and curved lines/arcs.
    for entry in list(start_state.get('graphics', []) or []):
        try:
            gr, gx, gy, gw, gh = entry[:5]
            _compat_1178(self, gr, float(gx), float(gy), float(gw), float(gh), old_box, new_box)
        except Exception:
            pass

    # After resizing, align BODY-owned imported/template artwork exactly to the
    # logical BODY origin.  This prevents the old helper/highlight box from
    # becoming a second geometry source.
    try:
        bgs = _compat_1158(self, u) if '_compat_1158' in globals() else []
        if bgs:
            # If these are body graphics, their combined bounds are now the BODY.
            # Move the logical BODY to their snapped outer bounds only when the
            # bounds differ by less than one edit grid; otherwise keep the user's
            # handle-defined BODY as source of truth.
            bx, by, bw, bh = _compat_1159(self, u)
            step = max(1e-9, float(self._edit_grid_step()))
            if abs(float(bx) - float(body.x)) <= step and abs(float(by) - float(body.y)) <= step:
                body.x = _compat_1171(self, _compat_1179(self, bx))
                body.y = _compat_1171(self, _compat_1179(self, by))
                body.width = max(step, _compat_1171(self, _compat_1179(self, bw)))
                body.height = max(step, _compat_1171(self, _compat_1179(self, bh)))
    except Exception:
        pass

    try:
        self._selection_restore_ids = {id(body)}
        self.dirty = True
    except Exception:
        pass
    return None

def _compat_1193(self, start_state: dict, body: SymbolBodyModel):
    try:
        old_x = _compat_1183(start_state.get('x', getattr(body, 'x', 0.0)), 0.0)
        old_y = _compat_1183(start_state.get('y', getattr(body, 'y', 0.0)), 0.0)
        old_w = max(1e-12, abs(_compat_1183(start_state.get('w', getattr(body, 'width', 1.0)), 1.0)))
        old_h = max(1e-12, abs(_compat_1183(start_state.get('h', getattr(body, 'height', 1.0)), 1.0)))

        step = _compat_1195(self)
        body.x = _compat_1182(self, _compat_1194(self, getattr(body, 'x', old_x)))
        body.y = _compat_1182(self, _compat_1194(self, getattr(body, 'y', old_y)))
        body.width = max(step, _compat_1182(self, _compat_1194(self, getattr(body, 'width', old_w))))
        body.height = max(step, _compat_1182(self, _compat_1194(self, getattr(body, 'height', old_h))))

        old_box = (old_x, old_y, old_w, old_h)
        new_box = (float(body.x), float(body.y), float(body.width), float(body.height))

        for entry in list(start_state.get('graphics', []) or []):
            try:
                if len(entry) >= 5:
                    _compat_1184(self, entry, old_box, new_box)
            except Exception:
                pass

        for entry in list(start_state.get('texts', []) or []):
            try:
                t, tx, ty = entry[:3]
                t.x, t.y = _compat_1185(self, tx, ty, old_box, new_box)
                t.x = _compat_1182(self, _compat_1194(self, t.x))
                t.y = _compat_1182(self, _compat_1194(self, t.y))
            except Exception:
                pass

        for entry in list(start_state.get('attributes', []) or []):
            try:
                t, tx, ty = entry[:3]
                t.x, t.y = _compat_1185(self, tx, ty, old_box, new_box)
                t.x = _compat_1182(self, _compat_1194(self, t.x))
                t.y = _compat_1182(self, _compat_1194(self, t.y))
            except Exception:
                pass

        for entry in list(start_state.get('pins', []) or []):
            try:
                p, px, py, plen = entry[:4]
                _compat_1192(self, p, float(px), float(py), float(plen), body)
            except Exception:
                pass

        self._selection_restore_ids = {id(body)}
        self.dirty = True
        return None
    except Exception:
        if _compat_1191 is not None:
            return _compat_1191(self, start_state, body)
        return None

def _compat_0722(self, gr, imported=False):
    try:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        raw = str(getattr(gr, 'mentor_raw', '') or '')
        if raw == '__USER_GRAPHIC__' or role == 'user_graphic':
            return False
        return bool(imported or getattr(gr, 'locked_to_body', False) or role in ('body', 'template_body', 'imported_body'))
    except Exception:
        return False

def _compat_0718(self, unit=None):
    try:
        u = unit or self.current_unit
        imported = False
        try:
            attrs = getattr(getattr(u, 'body', None), 'attributes', {}) or {}
            imported = any(str(attrs.get(k, '0')).strip().upper() in ('1', 'TRUE', 'YES') for k in (
                'MENTOR_GRAPHICS_AS_BODY', 'TEMPLATE_GRAPHICS_AS_BODY', 'MENTOR_HAS_BODY', 'MENTOR_BODY_GRAPHICS_LOCKED'
            ))
        except Exception:
            imported = False
        return [g for g in getattr(u, 'graphics', []) or [] if _compat_0722(self, g, imported)]
    except Exception:
        return []

def _compat_0723(self, old_bounds, new_bounds, x, y):
    ox, oy, ow, oh = old_bounds
    nx, ny, nw, nh = new_bounds
    ow = max(float(ow), 1e-9); oh = max(float(oh), 1e-9)
    sx = float(nw) / ow; sy = float(nh) / oh
    return (_compat_0720(self, float(nx) + (float(x) - float(ox)) * sx),
            _compat_0720(self, float(ny) - (float(oy) - float(y)) * sy))

def _compat_0729(self, rec, old_bounds, new_bounds):
    gr, x, y, w, h, ctrl_x, ctrl_y, curve_radius, rot, scx, scy = _compat_0721(rec[0], rec)
    p1 = _compat_0723(None, old_bounds, new_bounds, x, y)
    p2 = _compat_0723(None, old_bounds, new_bounds, x + w, y - h)
    gr.x = _compat_0720(None, p1[0])
    gr.y = _compat_0720(None, p1[1])
    gr.w = _compat_0720(None, p2[0] - p1[0])
    gr.h = _compat_0720(None, p1[1] - p2[1])

    # Quadratic/arc control point is a vector endpoint in the same coordinate
    # space, so map the absolute control point and convert back to local vector.
    try:
        if ctrl_x is not None and ctrl_y is not None:
            cp = _compat_0723(None, old_bounds, new_bounds, x + float(ctrl_x), y - float(ctrl_y))
            gr.ctrl_x = _compat_0720(None, cp[0] - gr.x)
            gr.ctrl_y = _compat_0720(None, gr.y - cp[1])
        else:
            gr.ctrl_x = ctrl_x
            gr.ctrl_y = ctrl_y
    except Exception:
        pass

    # curve_radius is a vertical/vector offset in this model.  Scaling with Y
    # preserves the visible arc direction and avoids cumulative curvature drift.
    try:
        if curve_radius is not None:
            ox, oy, ow, oh = old_bounds; nx, ny, nw, nh = new_bounds
            sy = float(nh) / max(float(oh), 1e-9)
            gr.curve_radius = _compat_0720(None, float(curve_radius) * sy)
    except Exception:
        pass
    try:
        gr.rotation = float(rot or 0.0)
        gr.scale_x = float(scx or 1.0)
        gr.scale_y = float(scy or 1.0)
    except Exception:
        pass

def _compat_0725(self, graphics):
    xs, ys = [], []
    for gr in graphics or []:
        try:
            x = float(getattr(gr, 'x', 0.0) or 0.0)
            y = float(getattr(gr, 'y', 0.0) or 0.0)
            w = float(getattr(gr, 'w', 0.0) or 0.0)
            h = float(getattr(gr, 'h', 0.0) or 0.0)
            xs.extend([x, x + w]); ys.extend([y, y - h])
            cx = getattr(gr, 'ctrl_x', None); cy = getattr(gr, 'ctrl_y', None)
            if cx is not None and cy is not None:
                xs.append(x + float(cx)); ys.append(y - float(cy))
        except Exception:
            pass
    if not xs or not ys:
        return None
    left, right = min(xs), max(xs)
    bottom, top = min(ys), max(ys)
    return (_compat_0720(self, left), _compat_0720(self, top), _compat_0720(self, right-left), _compat_0720(self, top-bottom))

def _compat_0733(self, unit, fallback_bounds=None):
    try:
        b = unit.body
        gs = _compat_0718(self, unit)
        bounds = _compat_0725(self, gs) if gs else None
        if bounds is None:
            bounds = fallback_bounds
        if bounds is not None:
            b.x, b.y, b.width, b.height = bounds
            b.width = max(_compat_0732(self), float(b.width))
            b.height = max(_compat_0732(self), float(b.height))
    except Exception:
        pass

def _compat_0728(self, start_state, body):
    """Authoritative canvas BODY-resize vector mapping.

    Called repeatedly during mouseMove.  It never reads already-mutated graphic
    dimensions as the next source.  Instead it maps the immutable start snapshot
    into the current BODY bounds.  That removes transient distortion while the
    mouse is moving and keeps post-scale geometry aligned.
    """
    try:
        u = self.current_unit
        old_bounds = (float(start_state.get('x', body.x)), float(start_state.get('y', body.y)),
                      max(float(start_state.get('w', body.width)), 1e-9), max(float(start_state.get('h', body.height)), 1e-9))
        new_bounds = (_compat_0730(self, float(body.x)), _compat_0730(self, float(body.y)),
                      max(_compat_0732(self), _compat_0730(self, float(body.width))),
                      max(_compat_0732(self), _compat_0730(self, float(body.height))))
        body.x, body.y, body.width, body.height = new_bounds

        body_graphics = set(_compat_0718(self, u))
        snap_index = _compat_0731(start_state.get('graphics', []))
        for gr in list(body_graphics):
            rec = snap_index.get(gr)
            if rec is not None:
                _compat_0729(self, rec, old_bounds, new_bounds)

        # If graphics define the visible body, sync the logical BODY to the real
        # transformed graphics.  Otherwise keep the requested rect from BodyItem.
        if body_graphics:
            _compat_0733(self, u, new_bounds)
            new_bounds = (float(u.body.x), float(u.body.y), float(u.body.width), float(u.body.height))
        else:
            u.body.x, u.body.y, u.body.width, u.body.height = new_bounds

        _compat_0726(self, start_state, old_bounds, new_bounds)

        # Texts and BODY attributes stay attached by position. Glyph geometry is
        # not scaled. This matches the existing Symbol-1 expectation.
        for t, tx, ty in start_state.get('texts', []) or []:
            t.x, t.y = (_compat_0730(self, _compat_0723(self, old_bounds, new_bounds, tx, ty)[0]),
                        _compat_0730(self, _compat_0723(self, old_bounds, new_bounds, tx, ty)[1]))
        for t, tx, ty in start_state.get('attributes', []) or []:
            t.x, t.y = (_compat_0730(self, _compat_0723(self, old_bounds, new_bounds, tx, ty)[0]),
                        _compat_0730(self, _compat_0723(self, old_bounds, new_bounds, tx, ty)[1]))

        # Non-body user graphics preserve their local shape and are only moved
        # as authored objects unless they were selected/resized separately.
        for rec in start_state.get('graphics', []) or []:
            try:
                gr, gx, gy, gw, gh, cx, cy, cr, rot, scx, scy = _compat_0721(rec[0], rec)
                if gr in body_graphics:
                    continue
                mapped = _compat_0723(self, old_bounds, new_bounds, gx, gy)
                gr.x, gr.y = _compat_0730(self, mapped[0]), _compat_0730(self, mapped[1])
                gr.w, gr.h = gw, gh
                gr.ctrl_x, gr.ctrl_y = cx, cy
                if cr is not None:
                    gr.curve_radius = cr
                gr.rotation = rot; gr.scale_x = scx; gr.scale_y = scy
            except Exception:
                pass

        try:
            if hasattr(u, '_body_group_transform'):
                delattr(u, '_body_group_transform')
        except Exception:
            pass
        self.dirty = True
    except Exception as e:
        try: self.statusBar().showMessage(f'Vector BODY canvas scale failed: {e}', 5000)
        except Exception: pass

def _compat_0719(self, unit=None):
    u = unit or self.current_unit
    b = u.body
    return {
        'x': float(b.x), 'y': float(b.y), 'w': float(b.width), 'h': float(b.height),
        'pins': [(p, float(getattr(p, 'x', 0.0)), float(getattr(p, 'y', 0.0)), float(getattr(p, 'length', 1.0) or 1.0)) for p in getattr(u, 'pins', []) or []],
        'texts': [(t, float(getattr(t, 'x', 0.0)), float(getattr(t, 'y', 0.0))) for t in getattr(u, 'texts', []) or []],
        'attributes': [(t, float(getattr(t, 'x', 0.0)), float(getattr(t, 'y', 0.0))) for t in (getattr(b, 'attribute_texts', {}) or {}).values()],
        'graphics': [_compat_0721(g) for g in getattr(u, 'graphics', []) or []],
    }

def _compat_0727(self, new_w=None, new_h=None, refresh=True):
    """Property/ribbon Scale +/- path using the same vector mapper as canvas."""
    try:
        u = self.current_unit; b = u.body
        start = _compat_0719(self, u)
        old_bounds = (start['x'], start['y'], max(start['w'], 1e-9), max(start['h'], 1e-9))
        w = old_bounds[2] if new_w is None else float(new_w)
        h = old_bounds[3] if new_h is None else float(new_h)
        # Keep top-left anchor stable, same as canvas BODY resize.
        b.x, b.y = old_bounds[0], old_bounds[1]
        b.width = max(_compat_0732(self), _compat_0730(self, w))
        b.height = max(_compat_0732(self), _compat_0730(self, h))
        _compat_0728(self, start, b)
        if refresh:
            try:
                self._selection_restore_ids = self._capture_selection_ids()
            except Exception:
                pass
            try: self.rebuild_scene()
            except Exception:
                try: self.update_current_unit_canvas_positions()
                except Exception: pass
            try: self.rebuild_tree(); self.rebuild_pin_table(); self.refresh_properties()
            except Exception: pass
    except Exception as e:
        try: self.statusBar().showMessage(f'BODY vector resize failed: {e}', 5000)
        except Exception: pass

def _compat_0734(self, op, value=None, refresh=True):
    if op in ('scale', 'scale_x_to', 'scale_y_to'):
        b = self.current_unit.body
        if op == 'scale_x_to':
            return _compat_0727(self, new_w=float(value), new_h=None, refresh=refresh)
        if op == 'scale_y_to':
            return _compat_0727(self, new_w=None, new_h=float(value), refresh=refresh)
        f = float(value or 1.0)
        return _compat_0727(self, new_w=float(b.width) * f, new_h=float(b.height) * f, refresh=refresh)
    try:
        return _compat_0991(self, op, value, refresh)
    except Exception:
        return None

def _compat_0750(self, entry, old_box, new_box):
    if not entry or len(entry) < 5:
        return
    gr = entry[0]
    gx = _compat_0737(entry[1]); gy = _compat_0737(entry[2])
    gw = _compat_0737(entry[3]); gh = _compat_0737(entry[4])
    ctrl_x = entry[5] if len(entry) > 5 else getattr(gr, 'ctrl_x', None)
    ctrl_y = entry[6] if len(entry) > 6 else getattr(gr, 'ctrl_y', None)
    curve_radius = entry[7] if len(entry) > 7 else getattr(gr, 'curve_radius', None)
    rotation = entry[8] if len(entry) > 8 else getattr(gr, 'rotation', 0.0)
    scale_x = entry[9] if len(entry) > 9 else getattr(gr, 'scale_x', 1.0)
    scale_y = entry[10] if len(entry) > 10 else getattr(gr, 'scale_y', 1.0)

    # Map the original start and end points as true vectors. This preserves line
    # direction, rectangle/ellipse proportions under non-uniform BODY scaling,
    # and prevents cumulative mouseMove distortion.
    x1, y1 = _compat_0743(self, gx, gy, old_box, new_box)
    x2, y2 = _compat_0743(self, gx + gw, gy - gh, old_box, new_box)
    gr.x = _compat_0752(self, x1)
    gr.y = _compat_0752(self, y1)
    gr.w = _compat_0736(self, _compat_0752(self, x2 - x1))
    gr.h = _compat_0736(self, _compat_0752(self, y1 - y2))

    # Control points are local vectors from the same anchor. Map the absolute
    # control point from the frozen start state, then convert back to local.
    try:
        if ctrl_x is not None and ctrl_y is not None:
            cx, cy = _compat_0743(self, gx + float(ctrl_x), gy - float(ctrl_y), old_box, new_box)
            gr.ctrl_x = _compat_0736(self, _compat_0752(self, cx - gr.x))
            gr.ctrl_y = _compat_0736(self, _compat_0752(self, gr.y - cy))
        else:
            gr.ctrl_x = ctrl_x
            gr.ctrl_y = ctrl_y
    except Exception:
        pass

    # Radius is a vector magnitude. Use the average absolute factor so arcs do
    # not invert or collapse when x/y factors differ.
    try:
        if curve_radius is not None:
            sx = abs(float(new_box[2]) / max(abs(float(old_box[2])), 1e-12))
            sy = abs(float(new_box[3]) / max(abs(float(old_box[3])), 1e-12))
            gr.curve_radius = _compat_0736(self, float(curve_radius or 0.0) * ((sx + sy) / 2.0))
    except Exception:
        pass
    try:
        gr.rotation = _compat_0737(rotation, 0.0)
        gr.scale_x = _compat_0737(scale_x, 1.0)
        gr.scale_y = _compat_0737(scale_y, 1.0)
    except Exception:
        pass

def _compat_0749(self, start_state: dict, body: SymbolBodyModel):
    try:
        old_x = _compat_0737(start_state.get('x', getattr(body, 'x', 0.0)))
        old_y = _compat_0737(start_state.get('y', getattr(body, 'y', 0.0)))
        old_w = max(1e-12, abs(_compat_0737(start_state.get('w', getattr(body, 'width', 1.0)), 1.0)))
        old_h = max(1e-12, abs(_compat_0737(start_state.get('h', getattr(body, 'height', 1.0)), 1.0)))

        step = _compat_0754(self)
        body.x = _compat_0752(self, getattr(body, 'x', old_x))
        body.y = _compat_0752(self, getattr(body, 'y', old_y))
        body.width = max(step, _compat_0752(self, getattr(body, 'width', old_w)))
        body.height = max(step, _compat_0752(self, getattr(body, 'height', old_h)))

        old_box = (old_x, old_y, old_w, old_h)
        new_box = (float(body.x), float(body.y), float(body.width), float(body.height))

        # All graphics inside the unit are transformed from the same immutable
        # start state. This is the same behaviour expected from Symbol 1.
        for entry in list(start_state.get('graphics', []) or []):
            try:
                _compat_0750(self, entry, old_box, new_box)
            except Exception:
                pass

        for entry in list(start_state.get('texts', []) or []):
            try:
                t, tx, ty = entry[:3]
                t.x, t.y = _compat_0743(self, tx, ty, old_box, new_box)
                t.x = _compat_0752(self, t.x)
                t.y = _compat_0752(self, t.y)
            except Exception:
                pass

        for entry in list(start_state.get('attributes', []) or []):
            try:
                t, tx, ty = entry[:3]
                t.x, t.y = _compat_0743(self, tx, ty, old_box, new_box)
                t.x = _compat_0752(self, t.x)
                t.y = _compat_0752(self, t.y)
            except Exception:
                pass

        # Pins keep their original relative slot. Docked pins are projected back
        # to the new BODY edge; loose pins are vector-mapped.
        for entry in list(start_state.get('pins', []) or []):
            try:
                p, px, py, plen = entry[:4]
                old_px, old_py = float(getattr(p, 'x', px)), float(getattr(p, 'y', py))
                mx, my = _compat_0743(self, px, py, old_box, new_box)
                side = str(getattr(p, 'side', '') or '')
                auto_dock = bool(getattr(p, 'auto_dock', True))
                if auto_dock and side == PinSide.LEFT.value:
                    nx, ny = new_box[0], my
                elif auto_dock and side == PinSide.RIGHT.value:
                    nx, ny = new_box[0] + new_box[2], my
                elif auto_dock and side == PinSide.TOP.value:
                    nx, ny = mx, new_box[1]
                elif auto_dock and side == PinSide.BOTTOM.value:
                    nx, ny = mx, new_box[1] - new_box[3]
                else:
                    nx, ny = mx, my
                p.x = _compat_0752(self, nx)
                p.y = _compat_0752(self, ny)
                p.length = float(plen)
                _compat_0748(self, p, old_px, old_py, p.x, p.y)
            except Exception:
                pass

        try:
            if hasattr(self.current_unit, '_body_group_transform'):
                delattr(self.current_unit, '_body_group_transform')
        except Exception:
            pass
        self._selection_restore_ids = {id(body)}
        self.dirty = True
    except Exception as exc:
        try:
            self.statusBar().showMessage(f'BODY vector scale failed: {exc}', 6000)
        except Exception:
            pass
        try:
            return _compat_1193(self, start_state, body)
        except Exception:
            return None

def _compat_0735(self, unit=None):
    u = unit or self.current_unit
    b = u.body
    graphics = []
    for gr in getattr(u, 'graphics', []) or []:
        try:
            graphics.append((
                gr,
                float(getattr(gr, 'x', 0.0) or 0.0),
                float(getattr(gr, 'y', 0.0) or 0.0),
                float(getattr(gr, 'w', 0.0) or 0.0),
                float(getattr(gr, 'h', 0.0) or 0.0),
                getattr(gr, 'ctrl_x', None),
                getattr(gr, 'ctrl_y', None),
                getattr(gr, 'curve_radius', None),
                float(getattr(gr, 'rotation', 0.0) or 0.0),
                float(getattr(gr, 'scale_x', 1.0) or 1.0),
                float(getattr(gr, 'scale_y', 1.0) or 1.0),
            ))
        except Exception:
            pass
    return {
        'x': float(getattr(b, 'x', 0.0) or 0.0),
        'y': float(getattr(b, 'y', 0.0) or 0.0),
        'w': float(getattr(b, 'width', 1.0) or 1.0),
        'h': float(getattr(b, 'height', 1.0) or 1.0),
        'pins': [(p, float(getattr(p, 'x', 0.0) or 0.0), float(getattr(p, 'y', 0.0) or 0.0), float(getattr(p, 'length', 1.0) or 1.0)) for p in getattr(u, 'pins', []) or []],
        'texts': [(t, float(getattr(t, 'x', 0.0) or 0.0), float(getattr(t, 'y', 0.0) or 0.0)) for t in getattr(u, 'texts', []) or []],
        'attributes': [(t, float(getattr(t, 'x', 0.0) or 0.0), float(getattr(t, 'y', 0.0) or 0.0)) for t in (getattr(b, 'attribute_texts', {}) or {}).values()],
        'graphics': graphics,
    }

def _compat_0747(self, new_w=None, new_h=None, refresh=True):
    u = self.current_unit
    b = u.body
    start = _compat_0735(self, u)
    if new_w is not None:
        b.width = max(_compat_0754(self), _compat_0752(self, new_w))
    if new_h is not None:
        b.height = max(_compat_0754(self), _compat_0752(self, new_h))
    _compat_0749(self, start, b)
    if refresh:
        try:
            self._selection_restore_ids = {id(b)}
            self.rebuild_scene()
            self.rebuild_tree()
            self.rebuild_pin_table()
            self.refresh_properties()
            if hasattr(self, 'view'):
                self.view.viewport().update()
        except Exception:
            try:
                self.update_current_unit_canvas_positions()
            except Exception:
                pass

def _compat_0765(self, entry, old_box, new_box):
    if not entry or len(entry) < 5:
        return
    gr = entry[0]
    gx = _compat_0758(entry[1]); gy = _compat_0758(entry[2])
    gw = _compat_0758(entry[3]); gh = _compat_0758(entry[4])
    ctrl_x = entry[5] if len(entry) > 5 else getattr(gr, 'ctrl_x', None)
    ctrl_y = entry[6] if len(entry) > 6 else getattr(gr, 'ctrl_y', None)
    curve_radius = entry[7] if len(entry) > 7 else getattr(gr, 'curve_radius', None)
    rotation = entry[8] if len(entry) > 8 else getattr(gr, 'rotation', 0.0)
    scale_x = entry[9] if len(entry) > 9 else getattr(gr, 'scale_x', 1.0)
    scale_y = entry[10] if len(entry) > 10 else getattr(gr, 'scale_y', 1.0)

    # Use the graphic's authored anchor and opposite endpoint/corner as vectors.
    # Do not snap each primitive endpoint: independent snapping is exactly what
    # destroys the inner vector geometry of imported/template artwork.
    x1, y1 = _compat_0760(self, gx, gy, old_box, new_box)
    x2, y2 = _compat_0760(self, gx + gw, gy - gh, old_box, new_box)
    gr.x = _compat_0757(self, x1)
    gr.y = _compat_0757(self, y1)
    gr.w = _compat_0757(self, x2 - x1)
    gr.h = _compat_0757(self, y1 - y2)

    # GraphicItem.paint() interprets ctrl as QPointF(ctrl_x, -ctrl_y), hence the
    # absolute model-space control point is (x + ctrl_x, y + ctrl_y).
    try:
        if ctrl_x is not None and ctrl_y is not None:
            cx, cy = _compat_0760(self, gx + float(ctrl_x), gy + float(ctrl_y), old_box, new_box)
            gr.ctrl_x = _compat_0757(self, cx - gr.x)
            gr.ctrl_y = _compat_0757(self, cy - gr.y)
        else:
            gr.ctrl_x = ctrl_x
            gr.ctrl_y = ctrl_y
    except Exception:
        pass

    try:
        if curve_radius is not None:
            sx = abs(float(new_box[2]) / max(abs(float(old_box[2])), 1e-12))
            sy = abs(float(new_box[3]) / max(abs(float(old_box[3])), 1e-12))
            # Keep sign, scale by geometric mean for curved line offset.  This
            # behaves like a vector magnitude without flipping the arc.
            factor = (sx * sy) ** 0.5
            gr.curve_radius = _compat_0757(self, float(curve_radius or 0.0) * factor)
    except Exception:
        pass
    try:
        gr.rotation = _compat_0758(rotation, 0.0)
        gr.scale_x = _compat_0758(scale_x, 1.0)
        gr.scale_y = _compat_0758(scale_y, 1.0)
    except Exception:
        pass

def _compat_0764(self, start_state: dict, body: SymbolBodyModel):
    try:
        old_x = _compat_0758(start_state.get('x', getattr(body, 'x', 0.0)))
        old_y = _compat_0758(start_state.get('y', getattr(body, 'y', 0.0)))
        old_w = max(1e-12, abs(_compat_0758(start_state.get('w', getattr(body, 'width', 1.0)), 1.0)))
        old_h = max(1e-12, abs(_compat_0758(start_state.get('h', getattr(body, 'height', 1.0)), 1.0)))

        step = _compat_0770(self)
        body.x = _compat_0769(self, getattr(body, 'x', old_x))
        body.y = _compat_0769(self, getattr(body, 'y', old_y))
        body.width = max(step, _compat_0769(self, getattr(body, 'width', old_w)))
        body.height = max(step, _compat_0769(self, getattr(body, 'height', old_h)))

        old_box = (old_x, old_y, old_w, old_h)
        new_box = (float(body.x), float(body.y), float(body.width), float(body.height))

        for entry in list(start_state.get('graphics', []) or []):
            try:
                _compat_0765(self, entry, old_box, new_box)
            except Exception:
                pass

        # Texts and BODY attributes are anchors.  They may snap to the edit grid;
        # their glyph shapes are not scaled during BODY resize.
        for entry in list(start_state.get('texts', []) or []):
            try:
                t, tx, ty = entry[:3]
                t.x, t.y = _compat_0760(self, tx, ty, old_box, new_box)
                t.x = _compat_0769(self, t.x)
                t.y = _compat_0769(self, t.y)
            except Exception:
                pass

        for entry in list(start_state.get('attributes', []) or []):
            try:
                t, tx, ty = entry[:3]
                t.x, t.y = _compat_0760(self, tx, ty, old_box, new_box)
                t.x = _compat_0769(self, t.x)
                t.y = _compat_0769(self, t.y)
            except Exception:
                pass

        for entry in list(start_state.get('pins', []) or []):
            try:
                p, px, py, plen = entry[:4]
                old_px, old_py = float(getattr(p, 'x', px)), float(getattr(p, 'y', py))
                side = str(getattr(p, 'side', '') or '')
                auto_dock = bool(getattr(p, 'auto_dock', True))
                # Slot values are computed from the immutable start BODY.  Docked
                # pins are reprojected to the new edge; loose pins are vector-mapped.
                if auto_dock and side in (PinSide.LEFT.value, PinSide.RIGHT.value):
                    slot = (old_y - float(py)) / old_h
                    ny = float(body.y) - slot * float(body.height)
                    nx = float(body.x) if side == PinSide.LEFT.value else float(body.x) + float(body.width)
                elif auto_dock and side in (PinSide.TOP.value, PinSide.BOTTOM.value):
                    slot = (float(px) - old_x) / old_w
                    nx = float(body.x) + slot * float(body.width)
                    ny = float(body.y) if side == PinSide.TOP.value else float(body.y) - float(body.height)
                else:
                    nx, ny = _compat_0760(self, px, py, old_box, new_box)
                p.x = _compat_0769(self, nx)
                p.y = _compat_0769(self, ny)
                p.length = float(plen)
                _compat_0763(self, p, old_px, old_py, p.x, p.y)
            except Exception:
                pass

        try:
            if hasattr(self.current_unit, '_body_group_transform'):
                delattr(self.current_unit, '_body_group_transform')
        except Exception:
            pass
        self._selection_restore_ids = {id(body)}
        self.dirty = True
    except Exception as exc:
        try:
            self.statusBar().showMessage(f'BODY vector scale failed: {exc}', 6000)
        except Exception:
            pass
        try:
            return _compat_0749(self, start_state, body)
        except Exception:
            return None

def _compat_0756(self, unit=None):
    u = unit or self.current_unit
    b = u.body
    graphics = []
    for gr in getattr(u, 'graphics', []) or []:
        try:
            graphics.append((
                gr,
                float(getattr(gr, 'x', 0.0) or 0.0),
                float(getattr(gr, 'y', 0.0) or 0.0),
                float(getattr(gr, 'w', 0.0) or 0.0),
                float(getattr(gr, 'h', 0.0) or 0.0),
                getattr(gr, 'ctrl_x', None),
                getattr(gr, 'ctrl_y', None),
                getattr(gr, 'curve_radius', None),
                float(getattr(gr, 'rotation', 0.0) or 0.0),
                float(getattr(gr, 'scale_x', 1.0) or 1.0),
                float(getattr(gr, 'scale_y', 1.0) or 1.0),
            ))
        except Exception:
            pass
    return {
        'x': float(getattr(b, 'x', 0.0) or 0.0),
        'y': float(getattr(b, 'y', 0.0) or 0.0),
        'w': float(getattr(b, 'width', 1.0) or 1.0),
        'h': float(getattr(b, 'height', 1.0) or 1.0),
        'pins': [(p, float(getattr(p, 'x', 0.0) or 0.0), float(getattr(p, 'y', 0.0) or 0.0), float(getattr(p, 'length', 1.0) or 1.0)) for p in getattr(u, 'pins', []) or []],
        'texts': [(t, float(getattr(t, 'x', 0.0) or 0.0), float(getattr(t, 'y', 0.0) or 0.0)) for t in getattr(u, 'texts', []) or []],
        'attributes': [(t, float(getattr(t, 'x', 0.0) or 0.0), float(getattr(t, 'y', 0.0) or 0.0)) for t in (getattr(b, 'attribute_texts', {}) or {}).values()],
        'graphics': graphics,
    }

def _compat_0762(self, new_w=None, new_h=None, refresh=True):
    u = self.current_unit
    b = u.body
    start = _compat_0756(self, u)
    if new_w is not None:
        b.width = max(_compat_0770(self), _compat_0769(self, new_w))
    if new_h is not None:
        b.height = max(_compat_0770(self), _compat_0769(self, new_h))
    _compat_0764(self, start, b)
    if refresh:
        try:
            self._selection_restore_ids = {id(b)}
            self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table(); self.refresh_properties()
            if hasattr(self, 'view'):
                self.view.viewport().update()
        except Exception:
            try:
                self.update_current_unit_canvas_positions()
            except Exception:
                pass

def _compat_0739(pin) -> bool:
    try:
        return getattr(pin, 'label_x', None) is not None and getattr(pin, 'label_y', None) is not None
    except Exception:
        return False

def _compat_0795(self, start_state, body):
    result = _compat_0792(self, start_state, body) if _compat_0792 is not None else None
    try:
        _compat_0800(self, self.current_unit, move_owned_text=False)
    except Exception:
        pass
    return result

def _compat_0831(self, start_state, body):
    # Keep the current working vector-scaling path for graphics/texts, then
    # correct pins from their frozen start-state so BODY resizing feels stable.
    result = None
    if _compat_0826 is not None:
        result = _compat_0826(self, start_state, body)
    else:
        result = None
    try:
        _compat_0830(self, start_state or {}, body)
    except Exception:
        pass
    return result

def _compat_0858(g):
    try:
        x = float(getattr(g, 'x', 0.0) or 0.0)
        y = float(getattr(g, 'y', 0.0) or 0.0)
        w = float(getattr(g, 'w', 0.0) or 0.0)
        h = float(getattr(g, 'h', 0.0) or 0.0)
        sh = str(getattr(g, 'shape', '') or '').lower()
        xs = [x, x + w]
        if sh == 'line' and getattr(g, 'ctrl_x', None) is None and getattr(g, 'ctrl_y', None) is None:
            ys = [y, y - h]
        elif sh in ('line', 'arc'):
            ys = [y, y + h]
            cx = getattr(g, 'ctrl_x', None)
            cy = getattr(g, 'ctrl_y', None)
            if cx is not None and cy is not None:
                xs.append(x + float(cx))
                ys.append(y + float(cy))
        else:
            ys = [y, y - h]
        return {'left': min(xs), 'right': max(xs), 'top': max(ys), 'bottom': min(ys),
                'cx': (min(xs) + max(xs)) / 2.0, 'cy': (min(ys) + max(ys)) / 2.0}
    except Exception:
        return {'left': 0.0, 'right': 0.0, 'top': 0.0, 'bottom': 0.0, 'cx': 0.0, 'cy': 0.0}

def _compat_1197(self):
    gi = _compat_1216(self)
    if gi is not None:
        try: self.push_undo_state()
        except Exception: pass
        gi.flip_horizontal()
        try:
            self._compat_1213 = gi.group_id
            self.dirty = True
            self.rebuild_scene(); self.rebuild_tree(); self.refresh_properties()
        except Exception: pass
        return None
    return _compat_1205(self) if _compat_1205 else None

def _compat_1198(self):
    gi = _compat_1216(self)
    if gi is not None:
        try: self.push_undo_state()
        except Exception: pass
        gi.flip_vertical()
        try:
            self._compat_1213 = gi.group_id
            self.dirty = True
            self.rebuild_scene(); self.rebuild_tree(); self.refresh_properties()
        except Exception: pass
        return None
    return _compat_1206(self) if _compat_1206 else None

# ---------------------------------------------------------------------------
# Canonical readable-text handling for BODY, free text and pin attributes.
# ---------------------------------------------------------------------------
def _canonical_unique_text_models(models):
    out = []
    seen = set()
    for model in models:
        try:
            if model is None:
                continue
            ident = id(model)
            if ident in seen:
                continue
            seen.add(ident)
            out.append(model)
        except Exception:
            pass
    return out


def _canonical_pin_attribute_text_models(pin):
    try:
        return list((getattr(pin, 'attribute_texts', {}) or {}).values())
    except Exception:
        return []


def _canonical_unit_text_models_for_flip(unit):
    models = []
    try:
        models.extend(list(getattr(unit, 'texts', []) or []))
    except Exception:
        pass
    try:
        body = getattr(unit, 'body', None)
        models.extend(list((getattr(body, 'attribute_texts', {}) or {}).values()))
    except Exception:
        pass
    try:
        for pin in list(getattr(unit, 'pins', []) or []):
            models.extend(_canonical_pin_attribute_text_models(pin))
    except Exception:
        pass
    return _canonical_unique_text_models(models)


def _canonical_selected_text_models_for_flip(self, selected_items):
    models = []
    for item in selected_items:
        try:
            kind = item.data(0)
        except Exception:
            kind = None
        try:
            if kind in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY'):
                models.append(getattr(item, 'model', None))
            elif kind == 'PIN':
                models.extend(_canonical_pin_attribute_text_models(getattr(item, 'model', None)))
            elif kind == 'BODY':
                unit = getattr(self, 'current_unit', None)
                models.extend(_canonical_unit_text_models_for_flip(unit))
        except Exception:
            pass
    return _canonical_unique_text_models(models)


def _canonical_swap_h_align(value):
    v = str(value or '').lower()
    if v == 'left':
        return 'right'
    if v == 'right':
        return 'left'
    return value


def _canonical_swap_v_align(value):
    v = str(value or '').lower()
    if v == 'upper':
        return 'lower'
    if v == 'lower':
        return 'upper'
    return value


def _canonical_selected_pins_for_flip(self, selected_items):
    pins = []
    seen = set()
    for item in selected_items:
        try:
            if item.data(0) != 'PIN':
                continue
            pin = getattr(item, 'model', None)
        except Exception:
            pin = None
        if pin is None:
            continue
        ident = id(pin)
        if ident in seen:
            continue
        seen.add(ident)
        pins.append(pin)
    return pins


def _canonical_unit_pins_for_flip(unit):
    try:
        return list(getattr(unit, 'pins', []) or [])
    except Exception:
        return []


def _canonical_record_text_anchor_state(models):
    records = []
    for model in _canonical_unique_text_models(models):
        try:
            sx = float(getattr(model, 'scale_x', 1.0) or 1.0)
        except Exception:
            sx = 1.0
        try:
            sy = float(getattr(model, 'scale_y', 1.0) or 1.0)
        except Exception:
            sy = 1.0
        records.append((
            model,
            getattr(model, 'h_align', None),
            getattr(model, 'v_align', None),
            sx,
            sy,
        ))
    return records


def _canonical_record_pin_anchor_state(pins):
    records = []
    seen = set()
    for pin in pins:
        if pin is None:
            continue
        ident = id(pin)
        if ident in seen:
            continue
        seen.add(ident)
        records.append((
            pin,
            getattr(pin, 'label_h_align', None),
            getattr(pin, 'label_v_align', None),
            getattr(pin, 'number_h_align', None),
            getattr(pin, 'number_v_align', None),
        ))
    return records


def _canonical_apply_text_anchor_only(records, axis):
    """Keep text upright and mirror only its grid anchor/alignment.

    Older compatibility layers used negative TextModel.scale_x/scale_y to make
    text follow BODY or split-part mirrors.  For the Symbol Wizard and Mentor
    workflows this is wrong: glyphs must remain readable.  The mirror operation
    is represented by the text anchor position plus the anchor alignment only.
    """
    for model, before_h, before_v, before_x, before_y in records:
        try:
            current_x = float(getattr(model, 'scale_x', before_x) or before_x or 1.0)
        except Exception:
            current_x = before_x or 1.0
        try:
            current_y = float(getattr(model, 'scale_y', before_y) or before_y or 1.0)
        except Exception:
            current_y = before_y or 1.0
        try:
            model.scale_x = abs(current_x)
            model.scale_y = abs(current_y)
        except Exception:
            pass
        try:
            if axis == 'horizontal':
                current_h = getattr(model, 'h_align', before_h)
                if current_h == before_h:
                    model.h_align = _canonical_swap_h_align(before_h or 'left')
            else:
                current_v = getattr(model, 'v_align', before_v)
                if current_v == before_v:
                    model.v_align = _canonical_swap_v_align(before_v or 'upper')
        except Exception:
            pass


def _canonical_apply_pin_anchor_only(records, axis):
    """Mirror the pin label/number grid anchors without mirroring label glyphs."""
    for pin, label_h, label_v, number_h, number_v in records:
        try:
            if axis == 'horizontal':
                if getattr(pin, 'label_h_align', label_h) == label_h:
                    pin.label_h_align = _canonical_swap_h_align(label_h or 'center')
                if getattr(pin, 'number_h_align', number_h) == number_h:
                    pin.number_h_align = _canonical_swap_h_align(number_h or 'center')
            else:
                if getattr(pin, 'label_v_align', label_v) == label_v:
                    pin.label_v_align = _canonical_swap_v_align(label_v or 'center')
                if getattr(pin, 'number_v_align', number_v) == number_v:
                    pin.number_v_align = _canonical_swap_v_align(number_v or 'center')
        except Exception:
            pass


def _canonical_flip_with_text_anchor_only(self, previous_flip, axis, *args, **kwargs):
    try:
        selected_items = list(self.scene.selectedItems()) if getattr(self, 'scene', None) is not None else []
    except Exception:
        selected_items = []
    try:
        body_mode = bool(self._selected_body_active())
    except Exception:
        body_mode = any(getattr(item, 'data', lambda *_: None)(0) == 'BODY' for item in selected_items)
    try:
        unit = getattr(self, 'current_unit', None)
    except Exception:
        unit = None
    if body_mode:
        text_models = _canonical_unit_text_models_for_flip(unit)
        pins = _canonical_unit_pins_for_flip(unit)
    else:
        text_models = _canonical_selected_text_models_for_flip(self, selected_items)
        pins = _canonical_selected_pins_for_flip(self, selected_items)
    text_records = _canonical_record_text_anchor_state(text_models)
    pin_records = _canonical_record_pin_anchor_state(pins)
    result = None
    if previous_flip is not None:
        result = previous_flip(self, *args, **kwargs)
    _canonical_apply_text_anchor_only(text_records, axis)
    _canonical_apply_pin_anchor_only(pin_records, axis)
    if text_records or pin_records:
        try:
            inv = getattr(self, '_invalidate_body_group_transform_cache', None)
            if callable(inv):
                inv()
        except Exception:
            pass
        try:
            self.update_current_unit_canvas_positions()
        except Exception:
            try:
                self.rebuild_scene()
            except Exception:
                pass
        try:
            self.refresh_properties()
        except Exception:
            pass
        try:
            self.dirty = True
        except Exception:
            pass
    return result

