# ---------------------------------------------------------------------------
# Liebherr transform/origin model patch
# ---------------------------------------------------------------------------
# Canonical rule used by both Symbol Wizard and Template Editor:
#   BODY bounds are derived only from BODY graphics (locked/template/imported
#   primitives; in Template Editor all template graphics are Body graphics).
#   Pins, texts and attributes are attached to BODY but never expand BODY bounds.
#   All transforms use a stable BODY-origin anchor and immutable local offsets.

def _lh_is_body_graphic(self, gr):
    try:
        if getattr(self, 'is_template_editor', False):
            return True
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        marker = str(getattr(gr, 'mentor_raw', '') or '')
        return bool(getattr(gr, 'locked_to_body', False) or role in ('body','template_body','imported_body') or marker != '__USER_GRAPHIC__' and role != 'user_graphic')
    except Exception:
        return False


def _lh_rot_pt(x, y, cx, cy, deg):
    if abs(float(deg or 0.0)) < 1e-12:
        return float(x), float(y)
    a = math.radians(float(deg or 0.0))
    ca, sa = math.cos(a), math.sin(a)
    dx, dy = float(x) - float(cx), float(y) - float(cy)
    return cx + ca*dx - sa*dy, cy + sa*dx + ca*dy


def _lh_graphic_points(self, gr):
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
        out.append(_lh_rot_pt(qx, qy, cx, cy, rot))
    return out


def _lh_body_graphics(self, unit=None):
    u = unit or self.current_unit
    return [g for g in (getattr(u, 'graphics', []) or []) if _lh_is_body_graphic(self, g)]


def _lh_body_graphics_bounds(self, unit=None):
    u = unit or self.current_unit
    gs = _lh_body_graphics(self, u)
    if not gs:
        return None
    pts = []
    for gr in gs:
        pts.extend(_lh_graphic_points(self, gr))
    if not pts:
        return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    minx, maxx = min(xs), max(xs); miny, maxy = min(ys), max(ys)
    if maxx - minx < 1e-9 or maxy - miny < 1e-9:
        return None
    return (minx, maxy, maxx - minx, maxy - miny)  # x,y,width,height with y=top


def _lh_sync_body_model_to_body_graphics(self, unit=None):
    u = unit or self.current_unit
    b = getattr(u, 'body', None)
    if b is None:
        return
    bounds = _lh_body_graphics_bounds(self, u)
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
        if _lh_body_graphics(self, u):
            b.rotation = 0.0
    except Exception:
        pass


def _lh_shift_unit_geometry(self, unit, dx, dy):
    unit.body.x += dx; unit.body.y += dy
    for p in getattr(unit, 'pins', []) or []:
        p.x += dx; p.y += dy
        for ax_name, ay_name in (('label_x', 'label_y'), ('number_x', 'number_y')):
            if getattr(p, ax_name, None) is not None:
                setattr(p, ax_name, getattr(p, ax_name) + dx)
            if getattr(p, ay_name, None) is not None:
                setattr(p, ay_name, getattr(p, ay_name) + dy)
        for tm in (getattr(p, 'attribute_texts', {}) or {}).values():
            try: tm.x += dx; tm.y += dy
            except Exception: pass
    for t in getattr(unit, 'texts', []) or []:
        t.x += dx; t.y += dy
    for t in (getattr(unit.body, 'attribute_texts', {}) or {}).values():
        t.x += dx; t.y += dy
    for g in getattr(unit, 'graphics', []) or []:
        g.x += dx; g.y += dy
    try:
        self._invalidate_body_group_transform_cache(unit)
    except Exception:
        pass


def _lh_anchor_for_unit(self, unit, mode=None):
    mode = mode or getattr(self.symbol, 'origin', OriginMode.CENTER.value)
    _lh_sync_body_model_to_body_graphics(self, unit)
    return self.body_anchor_point(unit.body, mode)


def _lh_normalize_unit_origin(self, unit, mode):
    # BODY bounds from graphics only; pins/text/attributes are attached but excluded.
    _lh_sync_body_model_to_body_graphics(self, unit)
    ax, ay = self.body_anchor_point(unit.body, mode)
    if abs(ax) > 1e-9 or abs(ay) > 1e-9:
        _lh_shift_unit_geometry(self, unit, -ax, -ay)
    _lh_sync_body_model_to_body_graphics(self, unit)


def _lh_dock_pins_to_body(self, u):
    # Axis docking is only valid for unrotated internal <NONE>-style bodies.
    # Imported/template bodies already carry native pin anchors and must not be
    # re-docked to an axis-aligned proxy rectangle on every rebuild.
    try:
        if _lh_body_graphics(self, u):
            return
        if abs(float(getattr(u.body, 'rotation', 0.0) or 0.0)) > 1e-9:
            return
    except Exception:
        pass
    b = u.body
    for p in getattr(u, 'pins', []) or []:
        if p.side == PinSide.LEFT.value:
            p.x = b.x
        elif p.side == PinSide.RIGHT.value:
            p.x = b.x + b.width
        elif p.side == PinSide.TOP.value:
            p.y = b.y
        elif p.side == PinSide.BOTTOM.value:
            p.y = b.y - b.height


def _lh_capture_body_group_base(self, unit=None):
    u = unit or self.current_unit
    _lh_sync_body_model_to_body_graphics(self, u)
    b = u.body
    mode = getattr(self.symbol, 'origin', OriginMode.CENTER.value)
    ax, ay = self.body_anchor_point(b, mode)
    base = {
        'pivot': (float(ax), float(ay)), 'anchor': (float(ax), float(ay)), 'origin_mode': mode,
        'has_body_graphics': bool(_lh_body_graphics(self, u)),
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


def _lh_apply_matrix_from_base(self, st, refresh=True):
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
        _lh_sync_body_model_to_body_graphics(self, u)
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


def _lh_body_group_state(self, unit=None):
    u = unit or self.current_unit
    st = getattr(u, '_body_group_transform', None)
    if not isinstance(st, dict) or 'base' not in st or 'M' not in st:
        st = _lh_capture_body_group_base(self, u)
    else:
        try:
            if st['base'].get('origin_mode') != getattr(self.symbol, 'origin', OriginMode.CENTER.value):
                st = _lh_capture_body_group_base(self, u)
        except Exception:
            st = _lh_capture_body_group_base(self, u)
    return st


def _lh_transform_unit_as_body_group(self, op, value=None, refresh=True):
    st = _lh_body_group_state(self, self.current_unit)
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
    _lh_apply_matrix_from_base(self, st, refresh=refresh)


def _lh_reset_origin_to_selected_anchor(self, mode=None):
    mode = mode or (self.origin_combo.currentText() if hasattr(self, 'origin_combo') else OriginMode.CENTER.value)
    if mode not in [x.value for x in OriginMode]: mode = OriginMode.CENTER.value
    try: self.push_undo_state()
    except Exception: pass
    self.symbol.origin = mode
    units = list(getattr(self.symbol, 'units', []) or [self.current_unit]) if not getattr(self, 'is_template_editor', False) else [self.current_unit]
    if not getattr(self, 'is_template_editor', False) and getattr(self.symbol, 'kind', None) != SymbolKind.SPLIT.value:
        units = [self.current_unit]
    for u in units:
        _lh_normalize_unit_origin(self, u, mode)
    if hasattr(self, 'origin_combo'):
        try:
            self.origin_combo.blockSignals(True); self.origin_combo.setCurrentText(mode); self.origin_combo.blockSignals(False)
        except Exception: pass
    try: self.set_format_guide_to_active_origin()
    except Exception: pass
    try: self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()
    except Exception: self.rebuild_scene()


def _lh_load_selected_template(self):
    name = self.current_template_key()
    if not name: return
    self._loading_template = True
    self.unit = self.main.load_template_unit(name); self.symbol.units=[self.unit]
    try: self.unit.body.attributes['TEMPLATE_GRAPHICS_AS_BODY'] = '1'
    except Exception: pass
    try: self._lock_template_body_graphics(self.unit)
    except Exception: pass
    # On opening the Template Editor, the BODY graphics are normalized to the
    # active origin immediately.  Pins/text/attributes keep their offsets and are
    # not allowed to redefine BODY extents.
    try: _lh_normalize_unit_origin(self, self.unit, getattr(self.symbol, 'origin', OriginMode.CENTER.value))
    except Exception: pass
    if hasattr(self, 'origin_combo'):
        self.origin_combo.blockSignals(True); self.origin_combo.setCurrentText(getattr(self.symbol, 'origin', OriginMode.CENTER.value)); self.origin_combo.blockSignals(False)
    try: self.rename_edit.setText(self._split_template_key(name)[1])
    except Exception: pass
    try: self._sync_template_grid_combo_to_unit()
    except Exception: pass
    self._current_template_name = name
    self.rebuild_scene()
    try: self._capture_clean_template_snapshot()
    except Exception: pass
    self._loading_template = False


def _lh_normalize_symbol_origins_for_import(self, symbol):
    mode = getattr(symbol, 'origin', OriginMode.CENTER.value) or OriginMode.CENTER.value
    if mode not in [x.value for x in OriginMode]:
        mode = OriginMode.CENTER.value; symbol.origin = mode
    for unit in getattr(symbol, 'units', []) or []:
        _lh_normalize_unit_origin(self, unit, mode)


def _lh_rebuild_scene_wrapper(orig):
    def wrapper(self, *args, **kwargs):
        try:
            # Keep logical BODY equal to graphics extents before drawing in both editors.
            _lh_sync_body_model_to_body_graphics(self, self.current_unit)
        except Exception:
            pass
        return orig(self, *args, **kwargs)
    return wrapper

# Install monkey patches on both editors.  The classes are already defined at
# this point, so existing UI code resolves the corrected methods dynamically.
try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._sync_imported_body_model_to_body_graphics = _lh_sync_body_model_to_body_graphics
        _cls._body_graphics_bounds = _lh_body_graphics_bounds
        _cls.shift_unit_geometry = _lh_shift_unit_geometry
        _cls.normalize_unit_origin = _lh_normalize_unit_origin
        _cls.normalize_symbol_origins_for_import = _lh_normalize_symbol_origins_for_import
        _cls.dock_pins_to_body = _lh_dock_pins_to_body
        _cls._body_group_capture_base = _lh_capture_body_group_base
        _cls._body_group_state = _lh_body_group_state
        _cls._apply_body_group_matrix_from_base = _lh_apply_matrix_from_base
        _cls._transform_unit_as_body_group = _lh_transform_unit_as_body_group
        _cls.reset_origin_to_selected_anchor = _lh_reset_origin_to_selected_anchor
    TemplateEditorDialog.load_selected_template = _lh_load_selected_template
    MainWindow.rebuild_scene = _lh_rebuild_scene_wrapper(MainWindow.rebuild_scene)
    TemplateEditorDialog.rebuild_scene = _lh_rebuild_scene_wrapper(TemplateEditorDialog.rebuild_scene)
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr final origin/transform normalization patch
# ---------------------------------------------------------------------------
# Rules:
#   * Canvas (0,0) is the only transform pivot.
#   * OriginMode only determines which BODY-graphics anchor is placed on (0,0)
#     when a template/symbol/origin is normalized.
#   * BODY extents are calculated from BODY graphics only. Pins/text/attributes
#     are attached to the body, but never define the BODY bounds.
#   * Rotate/flip/scale transform one rigid symbol group around (0,0). Text
#     positions move with the group, but glyphs remain readable (no mirror/rotate).

try:
    _LH_ORIGIN_VALUES = [x.value for x in OriginMode]
except Exception:
    _LH_ORIGIN_VALUES = ['center', 'bottom_left', 'bottom_right', 'top_left', 'top_right']


def _lh2_clean(self, v):
    try:
        v = round(float(v), 9)
        return 0.0 if abs(v) < 1e-9 else v
    except Exception:
        return v


def _lh2_mat_mul(A, B):
    a, b, c, d = A; e, f, g, h = B
    return (a*e + b*g, a*f + b*h, c*e + d*g, c*f + d*h)


def _lh2_mat_angle(M):
    a, b, c, d = M
    return math.degrees(math.atan2(c, a))


def _lh2_sx(M):
    a, b, c, d = M
    return max(1e-9, math.hypot(a, c))


def _lh2_sy(M):
    a, b, c, d = M
    return max(1e-9, math.hypot(b, d))


def _lh2_apply_pt(M, x, y):
    a, b, c, d = M
    return (a*float(x) + b*float(y), c*float(x) + d*float(y))


def _lh2_is_body_graphic(self, gr):
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


def _lh2_body_graphics(self, unit=None):
    u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    return [g for g in (getattr(u, 'graphics', []) or []) if _lh2_is_body_graphic(self, g)] if u else []


def _lh2_rot_local(px, py, cx, cy, deg):
    a = math.radians(float(deg or 0.0)); ca, sa = math.cos(a), math.sin(a)
    dx, dy = float(px) - float(cx), float(py) - float(cy)
    return (cx + ca*dx - sa*dy, cy + sa*dx + ca*dy)


def _lh2_graphic_points(self, gr):
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
        out.append(_lh2_rot_local(qx, qy, cx, cy, rot))
    return out


def _lh2_body_graphics_bounds(self, unit=None):
    pts = []
    for gr in _lh2_body_graphics(self, unit):
        pts.extend(_lh2_graphic_points(self, gr))
    if not pts:
        return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    minx, maxx = min(xs), max(xs); miny, maxy = min(ys), max(ys)
    if maxx - minx < 1e-9 or maxy - miny < 1e-9:
        return None
    return (minx, maxy, maxx - minx, maxy - miny)


def _lh2_sync_body_model_to_body_graphics(self, unit=None):
    u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    b = getattr(u, 'body', None) if u else None
    if b is None:
        return
    bounds = _lh2_body_graphics_bounds(self, u)
    if bounds is None:
        return
    x, y, w, h = bounds
    b.x = _lh2_clean(self, x); b.y = _lh2_clean(self, y)
    b.width = _lh2_clean(self, max(0.01, w)); b.height = _lh2_clean(self, max(0.01, h))
    # Imported/template BODY rotation lives in graphics, not in a proxy body box.
    b.rotation = 0.0


def _lh2_anchor_from_body_bounds(self, body, mode):
    mode = mode if mode in _LH_ORIGIN_VALUES else OriginMode.CENTER.value
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


def _lh2_shift_text_model(tm, dx, dy):
    try:
        tm.x = float(tm.x) + dx; tm.y = float(tm.y) + dy
    except Exception:
        pass


def _lh2_shift_unit_geometry(self, unit, dx, dy):
    b = getattr(unit, 'body', None)
    if b is not None:
        b.x = _lh2_clean(self, float(b.x) + dx); b.y = _lh2_clean(self, float(b.y) + dy)
    for gr in getattr(unit, 'graphics', []) or []:
        gr.x = _lh2_clean(self, float(gr.x) + dx); gr.y = _lh2_clean(self, float(gr.y) + dy)
    for p in getattr(unit, 'pins', []) or []:
        p.x = _lh2_clean(self, float(p.x) + dx); p.y = _lh2_clean(self, float(p.y) + dy)
        if getattr(p, 'label_x', None) is not None: p.label_x = _lh2_clean(self, float(p.label_x) + dx)
        if getattr(p, 'label_y', None) is not None: p.label_y = _lh2_clean(self, float(p.label_y) + dy)
        if getattr(p, 'number_x', None) is not None: p.number_x = _lh2_clean(self, float(p.number_x) + dx)
        if getattr(p, 'number_y', None) is not None: p.number_y = _lh2_clean(self, float(p.number_y) + dy)
        for tm in (getattr(p, 'attribute_texts', {}) or {}).values():
            _lh2_shift_text_model(tm, dx, dy)
    for tm in getattr(unit, 'texts', []) or []:
        _lh2_shift_text_model(tm, dx, dy)
    for tm in (getattr(getattr(unit, 'body', None), 'attribute_texts', {}) or {}).values():
        _lh2_shift_text_model(tm, dx, dy)
    try: _lh2_sync_body_model_to_body_graphics(self, unit)
    except Exception: pass
    try:
        if hasattr(unit, '_body_group_transform'):
            delattr(unit, '_body_group_transform')
    except Exception:
        pass


def _lh2_normalize_unit_origin(self, unit, mode):
    # Move the selected BODY anchor to canvas origin. Only BODY graphics define
    # the body bounds; attached objects are shifted by the exact same delta.
    _lh2_sync_body_model_to_body_graphics(self, unit)
    b = getattr(unit, 'body', None)
    if b is None:
        return
    ax, ay = _lh2_anchor_from_body_bounds(self, b, mode)
    if abs(ax) > 1e-9 or abs(ay) > 1e-9:
        _lh2_shift_unit_geometry(self, unit, -ax, -ay)
    _lh2_sync_body_model_to_body_graphics(self, unit)


def _lh2_capture_base(self, unit=None):
    u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    _lh2_sync_body_model_to_body_graphics(self, u)
    b = u.body
    base = {
        'unit_id': id(u),
        'origin_mode': getattr(self.symbol, 'origin', OriginMode.CENTER.value),
        'pivot': (0.0, 0.0),
        'has_body_graphics': bool(_lh2_body_graphics(self, u)),
        'body': {'x': float(b.x), 'y': float(b.y), 'w': float(b.width), 'h': float(b.height), 'rot': float(getattr(b, 'rotation', 0.0) or 0.0)},
        'graphics': [], 'pins': [], 'texts': [], 'body_attrs': []
    }
    for gr in getattr(u, 'graphics', []) or []:
        base['graphics'].append({
            'obj': gr, 'shape': str(getattr(gr, 'shape', '') or ''),
            'x': float(getattr(gr, 'x', 0.0) or 0.0), 'y': float(getattr(gr, 'y', 0.0) or 0.0),
            'w': float(getattr(gr, 'w', 0.0) or 0.0), 'h': float(getattr(gr, 'h', 0.0) or 0.0),
            'rot': float(getattr(gr, 'rotation', 0.0) or 0.0),
            'sx': float(getattr(gr, 'scale_x', 1.0) or 1.0), 'sy': float(getattr(gr, 'scale_y', 1.0) or 1.0),
            'ctrl_x': getattr(gr, 'ctrl_x', None), 'ctrl_y': getattr(gr, 'ctrl_y', None),
            'curve_radius': float(getattr(gr, 'curve_radius', 0.0) or 0.0),
        })
    for p in getattr(u, 'pins', []) or []:
        pd = {'obj': p, 'x': float(p.x), 'y': float(p.y), 'length': float(getattr(p, 'length', 1.0) or 1.0),
              'rot': float(getattr(p, 'rotation', 0.0) or 0.0), 'side': getattr(p, 'side', ''),
              'label': None, 'number': None, 'attrs': [],
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
    for tm in getattr(u, 'texts', []) or []:
        try: base['texts'].append({'obj': tm, 'x': float(tm.x), 'y': float(tm.y), 'rot': float(getattr(tm, 'rotation', 0.0) or 0.0), 'font': float(getattr(tm, 'font_size_grid', .75) or .75)})
        except Exception: pass
    for key, tm in (getattr(b, 'attribute_texts', {}) or {}).items():
        try: base['body_attrs'].append({'key': key, 'obj': tm, 'x': float(tm.x), 'y': float(tm.y), 'rot': float(getattr(tm, 'rotation', 0.0) or 0.0), 'font': float(getattr(tm, 'font_size_grid', .75) or .75)})
        except Exception: pass
    u._body_group_transform = {'base': base, 'M': (1.0, 0.0, 0.0, 1.0)}
    return u._body_group_transform


def _lh2_body_group_state(self, unit=None):
    u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    st = getattr(u, '_body_group_transform', None)
    mode = getattr(self.symbol, 'origin', OriginMode.CENTER.value)
    if not isinstance(st, dict) or 'base' not in st or 'M' not in st or st['base'].get('unit_id') != id(u) or st['base'].get('origin_mode') != mode:
        st = _lh2_capture_base(self, u)
    return st


def _lh2_graphic_set_from_base(self, gd, M):
    gr = gd['obj']; shape = gd.get('shape') or str(getattr(gr, 'shape', '') or '')
    sxv, syv = _lh2_sx(M), _lh2_sy(M)
    ang = _lh2_mat_angle(M)
    clean = lambda v: _lh2_clean(self, v)
    if shape in ('line', 'arc'):
        x1, y1 = _lh2_apply_pt(M, gd['x'], gd['y'])
        x2, y2 = _lh2_apply_pt(M, gd['x'] + gd['w'], gd['y'] - gd['h'])
        gr.x, gr.y = clean(x1), clean(y1)
        gr.w, gr.h = clean(x2 - x1), clean(y1 - y2)
        gr.rotation = 0.0; gr.scale_x = 1.0; gr.scale_y = 1.0
        if gd.get('ctrl_x') is not None and gd.get('ctrl_y') is not None:
            cx, cy = _lh2_apply_pt(M, gd['x'] + float(gd['ctrl_x']), gd['y'] - float(gd['ctrl_y']))
            gr.ctrl_x, gr.ctrl_y = clean(cx - x1), clean(y1 - cy)
        try:
            gr.curve_radius = clean(float(gd.get('curve_radius', 0.0) or 0.0) * max(sxv, syv))
        except Exception:
            pass
    else:
        cx, cy = gd['x'] + gd['w'] / 2.0, gd['y'] - gd['h'] / 2.0
        ncx, ncy = _lh2_apply_pt(M, cx, cy)
        gr.w = clean(abs(gd['w']) * sxv); gr.h = clean(abs(gd['h']) * syv)
        gr.x = clean(ncx - gr.w / 2.0); gr.y = clean(ncy + gr.h / 2.0)
        # Rect/ellipse orientation is represented by item rotation. Mirror is
        # represented with scale signs so the visual object is transformed, while
        # text objects are deliberately not mirrored.
        gr.rotation = clean((float(gd.get('rot', 0.0) or 0.0) + ang) % 360.0)
        # Detect reflection roughly by determinant sign. Use one negative scale
        # to mirror the graphic without adding a proxy frame.
        a, b, c, d = M; det = a*d - b*c
        gr.scale_x = -float(gd.get('sx', 1.0) or 1.0) if det < 0 else float(gd.get('sx', 1.0) or 1.0)
        gr.scale_y = float(gd.get('sy', 1.0) or 1.0)


def _lh2_apply_body_group_matrix_from_base(self, st, refresh=True):
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    if u is None:
        return
    base = st['base']; M = st.get('M', (1.0, 0.0, 0.0, 1.0))
    clean = lambda v: _lh2_clean(self, v)
    sxv, syv = _lh2_sx(M), _lh2_sy(M)
    font_factor = max(0.1, (abs(sxv) + abs(syv)) / 2.0)
    angle = _lh2_mat_angle(M)

    # Real graphics first. For imported/templates, BODY is the body graphics.
    for gd in base.get('graphics', []):
        _lh2_graphic_set_from_base(self, gd, M)

    b = u.body
    if not base.get('has_body_graphics'):
        # Internal <NONE> body as a real body object.
        bs = base['body']
        cx, cy = bs['x'] + bs['w']/2.0, bs['y'] - bs['h']/2.0
        ncx, ncy = _lh2_apply_pt(M, cx, cy)
        b.width = clean(max(0.01, abs(bs['w']) * sxv)); b.height = clean(max(0.01, abs(bs['h']) * syv))
        b.x = clean(ncx - b.width / 2.0); b.y = clean(ncy + b.height / 2.0)
        b.rotation = clean((bs.get('rot', 0.0) + angle) % 360.0)
    else:
        _lh2_sync_body_model_to_body_graphics(self, u)

    # Attached pins/text/attrs follow the same rigid group matrix around (0,0).
    for pd in base.get('pins', []):
        p = pd['obj']; nx, ny = _lh2_apply_pt(M, pd['x'], pd['y'])
        p.x, p.y = clean(nx), clean(ny)
        # Pin line orientation follows the symbol; pin text remains readable.
        p.rotation = clean((pd.get('rot', 0.0) + angle) % 360.0)
        p.length = clean(max(0.1, float(pd.get('length', 1.0) or 1.0) * font_factor))
        if pd.get('label') is not None:
            lx, ly = _lh2_apply_pt(M, *pd['label']); p.label_x, p.label_y = clean(lx), clean(ly)
        if pd.get('number') is not None:
            nx, ny = _lh2_apply_pt(M, *pd['number']); p.number_x, p.number_y = clean(nx), clean(ny)
        try: p.number_font.size_grid = max(0.1, clean(pd.get('nfs', .45) * font_factor))
        except Exception: pass
        try: p.label_font.size_grid = max(0.1, clean(pd.get('lfs', .55) * font_factor))
        except Exception: pass
        for key, tm, tx, ty, trot, tf in pd.get('attrs', []):
            try:
                qx, qy = _lh2_apply_pt(M, tx, ty); tm.x, tm.y = clean(qx), clean(qy)
                tm.rotation = trot  # readable: do not rotate/mirror glyphs
                tm.scale_x = 1.0; tm.scale_y = 1.0
                tm.font_size_grid = max(0.1, clean(tf * font_factor))
            except Exception:
                pass
    for td in base.get('texts', []):
        t = td['obj']; qx, qy = _lh2_apply_pt(M, td['x'], td['y'])
        t.x, t.y = clean(qx), clean(qy); t.rotation = td.get('rot', 0.0); t.scale_x = 1.0; t.scale_y = 1.0
        t.font_size_grid = max(0.1, clean(td.get('font', .75) * font_factor))
    for td in base.get('body_attrs', []):
        t = td['obj']; qx, qy = _lh2_apply_pt(M, td['x'], td['y'])
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


def _lh2_snap_edit(self, v, mn=0.01):
    try:
        return self._snap_to_edit_grid(v, mn)
    except Exception:
        try:
            step = self._edit_grid_step()
            return max(mn, round(float(v) / step) * step)
        except Exception:
            return max(mn, float(v))


def _lh2_transform_unit_as_body_group(self, op, value=None, refresh=True):
    st = _lh2_body_group_state(self, getattr(self, 'current_unit', None) or getattr(self, 'unit', None))
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
        _lh2_sync_body_model_to_body_graphics(self, u)
        cur_w = max(1e-9, float(getattr(u.body, 'width', 1.0) or 1.0))
        cur_h = max(1e-9, float(getattr(u.body, 'height', 1.0) or 1.0))
        if op == 'scale_x_to':
            sx, sy = _lh2_snap_edit(self, float(value), 0.01) / cur_w, 1.0
        elif op == 'scale_y_to':
            sx, sy = 1.0, _lh2_snap_edit(self, float(value), 0.01) / cur_h
        else:
            f = float(value or 1.0)
            sx = _lh2_snap_edit(self, cur_w * f, 0.01) / cur_w
            sy = _lh2_snap_edit(self, cur_h * f, 0.01) / cur_h
        Op = (sx, 0.0, 0.0, sy)
    else:
        return
    st['M'] = _lh2_mat_mul(Op, M)
    _lh2_apply_body_group_matrix_from_base(self, st, refresh=refresh)


def _lh2_reset_origin_to_selected_anchor(self, mode=None):
    mode = mode or (self.origin_combo.currentText() if hasattr(self, 'origin_combo') else OriginMode.CENTER.value)
    if mode not in _LH_ORIGIN_VALUES:
        mode = OriginMode.CENTER.value
    try: self.push_undo_state()
    except Exception: pass
    self.symbol.origin = mode
    units = [getattr(self, 'current_unit', None) or getattr(self, 'unit', None)]
    if not getattr(self, 'is_template_editor', False) and getattr(self.symbol, 'kind', None) == SymbolKind.SPLIT.value:
        units = list(getattr(self.symbol, 'units', []) or units)
    for u in [x for x in units if x is not None]:
        _lh2_normalize_unit_origin(self, u, mode)
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


def _lh2_normalize_symbol_origins_for_import(self, symbol):
    mode = getattr(symbol, 'origin', OriginMode.CENTER.value) or OriginMode.CENTER.value
    if mode not in _LH_ORIGIN_VALUES:
        mode = OriginMode.CENTER.value; symbol.origin = mode
    for u in getattr(symbol, 'units', []) or []:
        _lh2_normalize_unit_origin(self, u, mode)


def _lh2_invalidate_body_group_transform_cache(self, unit=None):
    try:
        if unit is None:
            for u in getattr(self.symbol, 'units', []) or []:
                if hasattr(u, '_body_group_transform'):
                    delattr(u, '_body_group_transform')
        elif hasattr(unit, '_body_group_transform'):
            delattr(unit, '_body_group_transform')
    except Exception:
        pass


def _lh2_body_owned_graphics(self, body):
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    return _lh2_body_graphics(self, u)


def _lh2_set_body_visual_attr(self, body, attr, value):
    if attr not in ('line_style', 'line_width', 'color'):
        return
    try: self.push_undo_state()
    except Exception: pass
    setattr(body, attr, value)
    for gr in _lh2_body_owned_graphics(self, body):
        st = getattr(gr, 'style', None)
        if st is None: continue
        if attr == 'line_style': st.line_style = value
        elif attr == 'line_width': st.line_width = float(value)
        elif attr == 'color': st.stroke = tuple(value)
    try: _lh2_invalidate_body_group_transform_cache(self, getattr(self, 'current_unit', None) or getattr(self, 'unit', None))
    except Exception: pass
    try: self.update_current_unit_canvas_positions()
    except Exception: pass
    try: self.schedule_scene_refresh(visual_only=True)
    except Exception: self.rebuild_scene()


def _lh2_color_body_model(self, body):
    c = QColorDialog.getColor(QColor(*getattr(body, 'color', (0,0,0))), self)
    if c.isValid():
        _lh2_set_body_visual_attr(self, body, 'color', (c.red(), c.green(), c.blue()))


def _lh2_load_selected_template(self):
    name = self.current_template_key()
    if not name:
        return
    self._loading_template = True
    self.unit = self.main.load_template_unit(name); self.symbol.units = [self.unit]
    try: self.unit.body.attributes['TEMPLATE_GRAPHICS_AS_BODY'] = '1'
    except Exception: pass
    try: self._lock_template_body_graphics(self.unit)
    except Exception: pass
    try: _lh2_normalize_unit_origin(self, self.unit, getattr(self.symbol, 'origin', OriginMode.CENTER.value))
    except Exception: pass
    if hasattr(self, 'origin_combo'):
        try:
            self.origin_combo.blockSignals(True); self.origin_combo.setCurrentText(getattr(self.symbol, 'origin', OriginMode.CENTER.value)); self.origin_combo.blockSignals(False)
        except Exception: pass
    try: self.rename_edit.setText(self._split_template_key(name)[1])
    except Exception: pass
    try: self._sync_template_grid_combo_to_unit()
    except Exception: pass
    self._current_template_name = name
    self.rebuild_scene()
    try: self._capture_clean_template_snapshot()
    except Exception: pass
    self._loading_template = False


def _lh2_rebuild_scene_wrapper(orig):
    def wrapper(self, *args, **kwargs):
        try: _lh2_sync_body_model_to_body_graphics(self, getattr(self, 'current_unit', None) or getattr(self, 'unit', None))
        except Exception: pass
        return orig(self, *args, **kwargs)
    return wrapper

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._sync_imported_body_model_to_body_graphics = _lh2_sync_body_model_to_body_graphics
        _cls._body_graphics_bounds = _lh2_body_graphics_bounds
        _cls._body_graphics = _lh2_body_graphics
        _cls.shift_unit_geometry = _lh2_shift_unit_geometry
        _cls.normalize_unit_origin = _lh2_normalize_unit_origin
        _cls.normalize_symbol_origins_for_import = _lh2_normalize_symbol_origins_for_import
        _cls._invalidate_body_group_transform_cache = _lh2_invalidate_body_group_transform_cache
        _cls._body_owned_graphics = _lh2_body_owned_graphics
        _cls._body_group_capture_base = _lh2_capture_base
        _cls._body_group_state = _lh2_body_group_state
        _cls._apply_body_group_matrix_from_base = _lh2_apply_body_group_matrix_from_base
        _cls._transform_unit_as_body_group = _lh2_transform_unit_as_body_group
        _cls.reset_origin_to_selected_anchor = _lh2_reset_origin_to_selected_anchor
        _cls.set_body_visual_attr = _lh2_set_body_visual_attr
        _cls.color_body_model = _lh2_color_body_model
    TemplateEditorDialog.load_selected_template = _lh2_load_selected_template
    MainWindow.rebuild_scene = _lh2_rebuild_scene_wrapper(MainWindow.rebuild_scene)
    TemplateEditorDialog.rebuild_scene = _lh2_rebuild_scene_wrapper(TemplateEditorDialog.rebuild_scene)
except Exception:
    pass


# ---------------------------------------------------------------------------
# Liebherr step: imported BODY artwork is the BODY, no proxy rectangle
# ---------------------------------------------------------------------------
def _lh3_selected_body_active(self):
    try:
        return any(getattr(i, 'data', lambda *_: None)(0) in ('BODY', 'BODY_GRAPHIC') for i in self.scene.selectedItems())
    except Exception:
        return False

def _lh3_capture_selection_ids(self):
    ids = set()
    try:
        for i in self.scene.selectedItems():
            if getattr(i, 'data', lambda *_: None)(0) == 'BODY_GRAPHIC':
                bm = getattr(i, '_body_model', None)
                if bm is not None:
                    ids.add(id(bm)); continue
            m = getattr(i, 'model', None)
            if m is not None:
                ids.add(id(m))
    except Exception:
        pass
    return ids

try:
    MainWindow._selected_body_active = _lh3_selected_body_active
    MainWindow._capture_selection_ids = _lh3_capture_selection_ids
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr step 2: imported/template BODY graphics use the native Symbol-1
# BODY transform pipeline.  If a unit has BODY graphics, mark them as the BODY
# before scene construction, select BODY through the artwork, and route rotate /
# flip / scale to the real graphics + all attached objects.
# ---------------------------------------------------------------------------
def _lh4_unit_has_imported_body_artwork(self, unit=None):
    u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    if u is None:
        return False
    try:
        return bool(_lh2_body_graphics(self, u))
    except Exception:
        try:
            return any(getattr(g, 'locked_to_body', False) for g in (getattr(u, 'graphics', []) or []))
        except Exception:
            return False


def _lh4_prepare_graphics_as_body(self, unit=None):
    u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    if u is None or getattr(u, 'body', None) is None:
        return
    if not _lh4_unit_has_imported_body_artwork(self, u):
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
            if _lh2_is_body_graphic(self, g):
                g.locked_to_body = True
                if not str(getattr(g, 'graphic_role', '') or ''):
                    g.graphic_role = 'imported_body'
        except Exception:
            pass
    try:
        _lh2_sync_body_model_to_body_graphics(self, u)
    except Exception:
        pass


def _lh4_selected_body_active(self):
    try:
        for i in self.scene.selectedItems():
            k = getattr(i, 'data', lambda *_: None)(0)
            if k in ('BODY', 'BODY_GRAPHIC'):
                return True
            m = getattr(i, 'model', None)
            if m is not None and _lh2_is_body_graphic(self, m):
                return True
    except Exception:
        pass
    return False


def _lh4_rotate_selected(self, deg):
    self.set_tool(DrawTool.SELECT.value)
    try: self.push_undo_state()
    except Exception: pass
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    _lh4_prepare_graphics_as_body(self, u)
    if _lh4_selected_body_active(self):
        _lh2_transform_unit_as_body_group(self, 'rotate', float(deg))
    else:
        for it in self.scene.selectedItems():
            if hasattr(it, 'rotate_by'):
                it.rotate_by(float(deg))
        try: self.schedule_scene_refresh()
        except Exception: self.rebuild_scene()
    self.dirty = True


def _lh4_flip_selected_horizontal(self):
    self.set_tool(DrawTool.SELECT.value)
    try: self.push_undo_state()
    except Exception: pass
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    _lh4_prepare_graphics_as_body(self, u)
    if _lh4_selected_body_active(self):
        _lh2_transform_unit_as_body_group(self, 'flip_h')
    else:
        for it in self.scene.selectedItems():
            if hasattr(it, 'flip_horizontal'):
                it.flip_horizontal()
        try: self.schedule_scene_refresh()
        except Exception: self.rebuild_scene()
    self.dirty = True


def _lh4_flip_selected_vertical(self):
    self.set_tool(DrawTool.SELECT.value)
    try: self.push_undo_state()
    except Exception: pass
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    _lh4_prepare_graphics_as_body(self, u)
    if _lh4_selected_body_active(self):
        _lh2_transform_unit_as_body_group(self, 'flip_v')
    else:
        for it in self.scene.selectedItems():
            if hasattr(it, 'flip_vertical'):
                it.flip_vertical()
        try: self.schedule_scene_refresh()
        except Exception: self.rebuild_scene()
    self.dirty = True


def _lh4_scale_selected(self, factor):
    self.set_tool(DrawTool.SELECT.value)
    try: self.push_undo_state()
    except Exception: pass
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    _lh4_prepare_graphics_as_body(self, u)
    if _lh4_selected_body_active(self):
        _lh2_transform_unit_as_body_group(self, 'scale', float(factor))
    else:
        for it in self.scene.selectedItems():
            if hasattr(it, 'scale_by'):
                it.scale_by(float(factor))
            elif hasattr(it, 'scale_selected'):
                it.scale_selected(float(factor))
        try: self.schedule_scene_refresh()
        except Exception: self.rebuild_scene()
    self.dirty = True


def _lh4_rebuild_scene_wrapper(orig):
    def wrapper(self, *args, **kwargs):
        try:
            _lh4_prepare_graphics_as_body(self, getattr(self, 'current_unit', None) or getattr(self, 'unit', None))
        except Exception:
            pass
        return orig(self, *args, **kwargs)
    return wrapper

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._unit_has_imported_body_artwork = _lh4_unit_has_imported_body_artwork
        _cls._prepare_graphics_as_body = _lh4_prepare_graphics_as_body
        _cls._selected_body_active = _lh4_selected_body_active
        _cls.rotate_selected = _lh4_rotate_selected
        _cls.flip_selected_horizontal = _lh4_flip_selected_horizontal
        _cls.flip_selected_vertical = _lh4_flip_selected_vertical
        _cls.scale_selected = _lh4_scale_selected
    MainWindow.rebuild_scene = _lh4_rebuild_scene_wrapper(MainWindow.rebuild_scene)
    TemplateEditorDialog.rebuild_scene = _lh4_rebuild_scene_wrapper(TemplateEditorDialog.rebuild_scene)
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr final transform fix: BODY graphics are transformed as real objects;
# Flip H/V use canvas axes; text is only moved, never mirrored/rotated.
# This override deliberately avoids the old proxy/base-stack path.
# ---------------------------------------------------------------------------
def _lh5_clean(self, v):
    try:
        v = round(float(v), 9)
        return 0.0 if abs(v) < 1e-9 else v
    except Exception:
        return v


def _lh5_apply_op_point(op, x, y):
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


def _lh5_transform_angle(angle, op):
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


def _lh5_text_readable(tm):
    """Text must stay readable: no negative scale and no transform rotation."""
    try: tm.scale_x = 1.0
    except Exception: pass
    try: tm.scale_y = 1.0
    except Exception: pass
    # Keep already user-defined text rotation if it exists, but never add flip/rotate.
    try:
        r = float(getattr(tm, 'rotation', 0.0) or 0.0)
        # Imported pin/body attribute labels in this tool are expected horizontal.
        # Normalize accidental 180/negative mirror rotations back to a readable 0°.
        if abs((r % 360.0) - 180.0) < 1e-6 or abs((r % 360.0) - 360.0) < 1e-6:
            tm.rotation = 0.0
    except Exception:
        pass


def _lh5_transform_text_model(self, tm, op, font_factor=1.0):
    if tm is None: return
    try:
        tm.x, tm.y = (_lh5_clean(self, v) for v in _lh5_apply_op_point(op, tm.x, tm.y))
    except Exception:
        pass
    _lh5_text_readable(tm)
    try:
        tm.font_size_grid = max(0.1, _lh5_clean(self, float(getattr(tm, 'font_size_grid', 0.75) or 0.75) * float(font_factor)))
    except Exception:
        pass


def _lh5_transform_graphic(self, gr, op):
    if gr is None: return
    shape = str(getattr(gr, 'shape', '') or '')
    try:
        if shape in ('line', 'arc'):
            x1, y1 = float(gr.x), float(gr.y)
            x2, y2 = float(gr.x) + float(getattr(gr, 'w', 0.0) or 0.0), float(gr.y) - float(getattr(gr, 'h', 0.0) or 0.0)
            nx1, ny1 = _lh5_apply_op_point(op, x1, y1)
            nx2, ny2 = _lh5_apply_op_point(op, x2, y2)
            old_ctrl_x, old_ctrl_y = getattr(gr, 'ctrl_x', None), getattr(gr, 'ctrl_y', None)
            gr.x, gr.y = _lh5_clean(self, nx1), _lh5_clean(self, ny1)
            gr.w, gr.h = _lh5_clean(self, nx2 - nx1), _lh5_clean(self, ny1 - ny2)
            gr.rotation = 0.0
            gr.scale_x = 1.0; gr.scale_y = 1.0
            if old_ctrl_x is not None and old_ctrl_y is not None:
                try:
                    cx, cy = _lh5_apply_op_point(op, x1 + float(old_ctrl_x), y1 - float(old_ctrl_y))
                    gr.ctrl_x = _lh5_clean(self, cx - nx1)
                    gr.ctrl_y = _lh5_clean(self, ny1 - cy)
                except Exception:
                    pass
            # curve_radius is a local distance; keep sign under rotation, mirror it under one-axis flips.
            try:
                if op[0] in ('flip_h', 'flip_v'):
                    gr.curve_radius = _lh5_clean(self, -float(getattr(gr, 'curve_radius', 0.0) or 0.0))
                elif op[0] == 'scale':
                    gr.curve_radius = _lh5_clean(self, float(getattr(gr, 'curve_radius', 0.0) or 0.0) * max(abs(float(op[1])), abs(float(op[2]))))
            except Exception:
                pass
        else:
            # Rect/ellipse/circle: transform center and orientation.  Keep glyph-free geometry mirrored/rotated.
            x = float(getattr(gr, 'x', 0.0) or 0.0); y = float(getattr(gr, 'y', 0.0) or 0.0)
            w = float(getattr(gr, 'w', 0.0) or 0.0); h = float(getattr(gr, 'h', 0.0) or 0.0)
            cx, cy = x + w/2.0, y - h/2.0
            ncx, ncy = _lh5_apply_op_point(op, cx, cy)
            if op[0] == 'scale':
                w, h = abs(w * float(op[1])), abs(h * float(op[2]))
            # For 90° rotations keep model w/h and use model.rotation. This matches GraphicItem.
            gr.x, gr.y = _lh5_clean(self, ncx - w/2.0), _lh5_clean(self, ncy + h/2.0)
            gr.w, gr.h = _lh5_clean(self, w), _lh5_clean(self, h)
            gr.rotation = _lh5_clean(self, _lh5_transform_angle(getattr(gr, 'rotation', 0.0), op))
            gr.scale_x = float(getattr(gr, 'scale_x', 1.0) or 1.0)
            gr.scale_y = float(getattr(gr, 'scale_y', 1.0) or 1.0)
            if op[0] == 'flip_h':
                gr.scale_x = -gr.scale_x
            elif op[0] == 'flip_v':
                gr.scale_y = -gr.scale_y
    except Exception:
        pass


def _lh5_transform_body_rect(self, b, op):
    if b is None: return
    try:
        x, y, w, h = float(b.x), float(b.y), float(b.width), float(b.height)
        cx, cy = x + w/2.0, y - h/2.0
        ncx, ncy = _lh5_apply_op_point(op, cx, cy)
        if op[0] == 'scale':
            w, h = abs(w * float(op[1])), abs(h * float(op[2]))
        b.x, b.y = _lh5_clean(self, ncx - w/2.0), _lh5_clean(self, ncy + h/2.0)
        b.width, b.height = _lh5_clean(self, max(0.01, w)), _lh5_clean(self, max(0.01, h))
        b.rotation = _lh5_clean(self, _lh5_transform_angle(getattr(b, 'rotation', 0.0), op))
        if op[0] == 'flip_h':
            b.scale_x = -float(getattr(b, 'scale_x', 1.0) or 1.0)
        elif op[0] == 'flip_v':
            b.scale_y = -float(getattr(b, 'scale_y', 1.0) or 1.0)
    except Exception:
        pass


def _lh5_body_graphics(self, unit):
    try:
        return _lh2_body_graphics(self, unit)
    except Exception:
        out=[]
        for g in getattr(unit, 'graphics', []) or []:
            role = str(getattr(g, 'graphic_role', '') or '').lower()
            raw = str(getattr(g, 'mentor_raw', '') or '')
            if getattr(g, 'locked_to_body', False) or role in ('body','template_body','imported_body') or (raw != '__USER_GRAPHIC__' and role != 'user_graphic'):
                out.append(g)
        return out


def _lh5_transform_unit_as_body_group(self, op_name, value=None, refresh=True):
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
        try: _lh2_sync_body_model_to_body_graphics(self, u)
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
    body_graphics = _lh5_body_graphics(self, u)
    if body_graphics:
        for gr in body_graphics:
            _lh5_transform_graphic(self, gr, op)
        try: _lh2_sync_body_model_to_body_graphics(self, u)
        except Exception:
            try: self._sync_body_model_to_body_bounds_only(u)
            except Exception: pass
        # Keep logical proxy rotation neutral for imported artwork; visual rotation is in graphics.
        try: u.body.rotation = 0.0
        except Exception: pass
    else:
        _lh5_transform_body_rect(self, u.body, op)

    # User/free graphics are attached to the symbol too, but not part of BODY bounds.
    for gr in getattr(u, 'graphics', []) or []:
        if gr not in body_graphics:
            _lh5_transform_graphic(self, gr, op)

    # Pins and pin-owned text.
    for p in getattr(u, 'pins', []) or []:
        try:
            p.x, p.y = (_lh5_clean(self, v) for v in _lh5_apply_op_point(op, p.x, p.y))
            p.rotation = _lh5_clean(self, _lh5_transform_angle(getattr(p, 'rotation', 0.0), op))
            if op[0] == 'scale':
                p.length = max(0.1, _lh5_clean(self, float(getattr(p, 'length', 1.0) or 1.0) * font_factor))
        except Exception: pass
        for ax, ay in (('label_x','label_y'), ('number_x','number_y')):
            if getattr(p, ax, None) is not None and getattr(p, ay, None) is not None:
                try:
                    nx, ny = _lh5_apply_op_point(op, getattr(p, ax), getattr(p, ay))
                    setattr(p, ax, _lh5_clean(self, nx)); setattr(p, ay, _lh5_clean(self, ny))
                except Exception: pass
        for tm in (getattr(p, 'attribute_texts', {}) or {}).values():
            _lh5_transform_text_model(self, tm, op, font_factor)
        try:
            if op[0] == 'scale':
                p.number_font.size_grid = max(0.1, _lh5_clean(self, float(getattr(p.number_font, 'size_grid', .45) or .45) * font_factor))
                p.label_font.size_grid = max(0.1, _lh5_clean(self, float(getattr(p.label_font, 'size_grid', .55) or .55) * font_factor))
        except Exception: pass

    for tm in getattr(u, 'texts', []) or []:
        _lh5_transform_text_model(self, tm, op, font_factor)
    for tm in (getattr(u.body, 'attribute_texts', {}) or {}).values():
        _lh5_transform_text_model(self, tm, op, font_factor)

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


def _lh5_normalize_noop(self, unit=None):
    # Do not silently renormalize on every rebuild. Origin placement is handled
    # explicitly by Origin Reset / template import. Rebuild must not undo a
    # user transform or shift imported body graphics.
    try:
        u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
        if u is not None:
            if _lh5_body_graphics(self, u):
                try: _lh2_sync_body_model_to_body_graphics(self, u)
                except Exception: pass
    except Exception:
        pass

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._transform_unit_as_body_group = _lh5_transform_unit_as_body_group
        _cls._normalize_unit_body_anchor_to_symbol_origin = _lh5_normalize_noop
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr transform correction v6
# ---------------------------------------------------------------------------
# Finalized rules for imported/template BODY symbols:
# - BODY artwork is the real BODY, not a proxy rectangle.
# - Rotate is baked into the actual BODY graphics around canvas origin (0,0).
# - Flip H mirrors at the canvas Y-axis, Flip V mirrors at the canvas X-axis.
# - Pin geometry follows via side remapping so pin text remains readable.
# - Text/attributes/pin labels move with the group but glyphs are never rotated
#   or mirrored.
# - Scaling target dimensions are snapped to the edit grid.

def _lh6_clean(self, v):
    try:
        v = round(float(v), 9)
        return 0.0 if abs(v) < 1e-9 else v
    except Exception:
        return v


def _lh6_pt(op, x, y):
    x = float(x); y = float(y)
    if op[0] == 'rotate':
        d = int(round(float(op[1]) / 90.0)) % 4
        if d == 0: return x, y
        if d == 1: return -y, x
        if d == 2: return -x, -y
        return y, -x
    if op[0] == 'flip_h':
        return -x, y
    if op[0] == 'flip_v':
        return x, -y
    if op[0] == 'scale':
        return x * float(op[1]), y * float(op[2])
    return x, y


def _lh6_side(side, op):
    s = str(side or '')
    if s not in (PinSide.LEFT.value, PinSide.RIGHT.value, PinSide.TOP.value, PinSide.BOTTOM.value):
        return s
    if op[0] == 'flip_h':
        return {PinSide.LEFT.value: PinSide.RIGHT.value, PinSide.RIGHT.value: PinSide.LEFT.value}.get(s, s)
    if op[0] == 'flip_v':
        return {PinSide.TOP.value: PinSide.BOTTOM.value, PinSide.BOTTOM.value: PinSide.TOP.value}.get(s, s)
    if op[0] == 'rotate':
        d = int(round(float(op[1]) / 90.0)) % 4
        ccw = {
            PinSide.RIGHT.value: PinSide.TOP.value,
            PinSide.TOP.value: PinSide.LEFT.value,
            PinSide.LEFT.value: PinSide.BOTTOM.value,
            PinSide.BOTTOM.value: PinSide.RIGHT.value,
        }
        for _ in range(d):
            s = ccw.get(s, s)
    return s


def _lh6_text_readable(tm):
    try: tm.rotation = 0.0
    except Exception: pass
    try: tm.scale_x = 1.0
    except Exception: pass
    try: tm.scale_y = 1.0
    except Exception: pass


def _lh6_move_text(self, tm, op, font_factor=1.0):
    if tm is None:
        return
    try:
        nx, ny = _lh6_pt(op, tm.x, tm.y)
        tm.x, tm.y = _lh6_clean(self, nx), _lh6_clean(self, ny)
    except Exception:
        pass
    _lh6_text_readable(tm)
    try:
        if op[0] == 'scale':
            tm.font_size_grid = max(0.1, _lh6_clean(self, float(getattr(tm, 'font_size_grid', 0.75) or 0.75) * float(font_factor)))
    except Exception:
        pass


def _lh6_graphic_corners(g):
    x = float(getattr(g, 'x', 0.0) or 0.0)
    y = float(getattr(g, 'y', 0.0) or 0.0)
    w = float(getattr(g, 'w', 0.0) or 0.0)
    h = float(getattr(g, 'h', 0.0) or 0.0)
    return [(x, y), (x + w, y), (x + w, y - h), (x, y - h)]


def _lh6_transform_graphic(self, g, op):
    if g is None:
        return
    shape = str(getattr(g, 'shape', '') or '')
    clean = lambda v: _lh6_clean(self, v)
    try:
        if shape in ('line', 'arc'):
            x1 = float(getattr(g, 'x', 0.0) or 0.0); y1 = float(getattr(g, 'y', 0.0) or 0.0)
            x2 = x1 + float(getattr(g, 'w', 0.0) or 0.0)
            y2 = y1 - float(getattr(g, 'h', 0.0) or 0.0)
            nx1, ny1 = _lh6_pt(op, x1, y1); nx2, ny2 = _lh6_pt(op, x2, y2)
            ctrl_x, ctrl_y = getattr(g, 'ctrl_x', None), getattr(g, 'ctrl_y', None)
            g.x, g.y = clean(nx1), clean(ny1)
            g.w, g.h = clean(nx2 - nx1), clean(ny1 - ny2)
            g.rotation = 0.0; g.scale_x = 1.0; g.scale_y = 1.0
            if ctrl_x is not None and ctrl_y is not None:
                try:
                    cx, cy = _lh6_pt(op, x1 + float(ctrl_x), y1 - float(ctrl_y))
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
            pts = [_lh6_pt(op, px, py) for px, py in _lh6_graphic_corners(g)]
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            minx, maxx = min(xs), max(xs); miny, maxy = min(ys), max(ys)
            g.x, g.y = clean(minx), clean(maxy)
            g.w, g.h = clean(maxx - minx), clean(maxy - miny)
            g.rotation = 0.0; g.scale_x = 1.0; g.scale_y = 1.0
    except Exception:
        pass


def _lh6_snap_target(self, value, mn=0.01):
    try:
        step = float(self._edit_grid_step())
        if step <= 0: step = float(getattr(self, 'edit_grid_inch', 0.1) or 0.1)
        return max(float(mn), round(float(value) / step) * step)
    except Exception:
        try: return self._snap_to_edit_grid(value, mn)
        except Exception: return max(float(mn), float(value))


def _lh6_transform_unit_as_body_group(self, op_name, value=None, refresh=True):
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    if u is None or getattr(u, 'body', None) is None:
        return
    try: _lh4_prepare_graphics_as_body(self, u)
    except Exception: pass
    try: _lh2_sync_body_model_to_body_graphics(self, u)
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
            target_w = _lh6_snap_target(self, float(value), 0.01); sx, sy = target_w / cur_w, 1.0
        elif op_name == 'scale_y_to':
            target_h = _lh6_snap_target(self, float(value), 0.01); sx, sy = 1.0, target_h / cur_h
        else:
            f = float(value or 1.0)
            target_w = _lh6_snap_target(self, cur_w * f, 0.01)
            target_h = _lh6_snap_target(self, cur_h * f, 0.01)
            sx, sy = target_w / cur_w, target_h / cur_h
        op = ('scale', sx, sy)
    else:
        return

    font_factor = 1.0
    if op[0] == 'scale':
        font_factor = max(0.1, (abs(float(op[1])) + abs(float(op[2]))) / 2.0)

    body_graphics = []
    try: body_graphics = list(_lh2_body_graphics(self, u))
    except Exception: body_graphics = []

    if body_graphics:
        for g in body_graphics:
            _lh6_transform_graphic(self, g, op)
        try: _lh2_sync_body_model_to_body_graphics(self, u)
        except Exception: pass
        try: u.body.rotation = 0.0; u.body.scale_x = 1.0; u.body.scale_y = 1.0
        except Exception: pass
    else:
        # Internal <NONE>-style body: transform its own rectangle exactly.
        try:
            b = u.body
            pts = [_lh6_pt(op, b.x, b.y), _lh6_pt(op, b.x + b.width, b.y), _lh6_pt(op, b.x + b.width, b.y - b.height), _lh6_pt(op, b.x, b.y - b.height)]
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            b.x, b.y = _lh6_clean(self, min(xs)), _lh6_clean(self, max(ys))
            b.width, b.height = _lh6_clean(self, max(xs)-min(xs)), _lh6_clean(self, max(ys)-min(ys))
            b.rotation = 0.0; b.scale_x = 1.0; b.scale_y = 1.0
        except Exception:
            pass

    for g in getattr(u, 'graphics', []) or []:
        if g not in body_graphics:
            _lh6_transform_graphic(self, g, op)

    for p in getattr(u, 'pins', []) or []:
        try:
            p.x, p.y = (_lh6_clean(self, v) for v in _lh6_pt(op, p.x, p.y))
            p.side = _lh6_side(getattr(p, 'side', ''), op)
            # Pin side now carries geometry. Keep item rotation neutral so pin
            # number/name/function are painted readable by PinItem.
            p.rotation = 0.0; p.scale_x = 1.0; p.scale_y = 1.0
            if op[0] == 'scale':
                p.length = max(0.1, _lh6_clean(self, float(getattr(p, 'length', 1.0) or 1.0) * font_factor))
        except Exception:
            pass
        for ax, ay in (('label_x', 'label_y'), ('number_x', 'number_y')):
            if getattr(p, ax, None) is not None and getattr(p, ay, None) is not None:
                try:
                    nx, ny = _lh6_pt(op, getattr(p, ax), getattr(p, ay))
                    setattr(p, ax, _lh6_clean(self, nx)); setattr(p, ay, _lh6_clean(self, ny))
                except Exception: pass
        for tm in (getattr(p, 'attribute_texts', {}) or {}).values():
            _lh6_move_text(self, tm, op, font_factor)
        try:
            if op[0] == 'scale':
                p.number_font.size_grid = max(0.1, _lh6_clean(self, float(getattr(p.number_font, 'size_grid', .45) or .45) * font_factor))
                p.label_font.size_grid = max(0.1, _lh6_clean(self, float(getattr(p.label_font, 'size_grid', .55) or .55) * font_factor))
        except Exception:
            pass

    for tm in getattr(u, 'texts', []) or []:
        _lh6_move_text(self, tm, op, font_factor)
    for tm in (getattr(u.body, 'attribute_texts', {}) or {}).values():
        _lh6_move_text(self, tm, op, font_factor)

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

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._transform_unit_as_body_group = _lh6_transform_unit_as_body_group
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v7: route BODY transform buttons to the current transform backend.
# Previous wrappers still called the old _lh2_transform_unit_as_body_group
# directly, so imported BODY graphics stayed unchanged while pins/text moved.
# Keep Symbol-1 behaviour for native BODYs, but always transform through
# self._transform_unit_as_body_group, which is overridden by the latest backend.
# ---------------------------------------------------------------------------
def _lh7_selected_body_or_body_graphic(self):
    try:
        for it in self.scene.selectedItems():
            k = getattr(it, 'data', lambda *_: None)(0)
            if k in ('BODY', 'BODY_GRAPHIC'):
                return True
            m = getattr(it, 'model', None)
            if m is not None:
                try:
                    if _lh2_is_body_graphic(self, m):
                        return True
                except Exception:
                    if getattr(m, 'locked_to_body', False) or str(getattr(m, 'graphic_role', '') or '').lower() in ('body','template_body','imported_body'):
                        return True
    except Exception:
        pass
    return False


def _lh7_do_body_transform(self, op_name, value=None):
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
        _lh4_prepare_graphics_as_body(self, u)
    except Exception:
        pass
    if _lh7_selected_body_or_body_graphic(self):
        fn = getattr(self, '_transform_unit_as_body_group', None)
        if callable(fn):
            fn(op_name, value)
        else:
            _lh6_transform_unit_as_body_group(self, op_name, value)
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


def _lh7_rotate_selected(self, deg):
    _lh7_do_body_transform(self, 'rotate', float(deg))


def _lh7_flip_selected_horizontal(self):
    # Flip H = mirror at canvas Y-axis: x -> -x.
    _lh7_do_body_transform(self, 'flip_h', None)


def _lh7_flip_selected_vertical(self):
    # Flip V = mirror at canvas X-axis: y -> -y.
    _lh7_do_body_transform(self, 'flip_v', None)


def _lh7_scale_selected(self, factor):
    _lh7_do_body_transform(self, 'scale', float(factor))

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._selected_body_active = _lh7_selected_body_or_body_graphic
        _cls.rotate_selected = _lh7_rotate_selected
        _cls.flip_selected_horizontal = _lh7_flip_selected_horizontal
        _cls.flip_selected_vertical = _lh7_flip_selected_vertical
        _cls.scale_selected = _lh7_scale_selected
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v8: normalize direction semantics globally.
# User convention:
#   Rotate CW  = clockwise around canvas origin (0,0):       (x,y) -> ( y,-x)
#   Rotate CCW = counter-clockwise around canvas origin:      (x,y) -> (-y, x)
#   Flip H     = mirror at the HORIZONTAL axis (X-axis):      (x,y) -> ( x,-y)
#   Flip V     = mirror at the VERTICAL axis (Y-axis):        (x,y) -> (-x, y)
# Text glyphs remain readable; only positions are transformed by _lh6_move_text.
# This intentionally redefines _lh6_pt/_lh6_side after v7 because the transform
# backend resolves these globals at call time.
# ---------------------------------------------------------------------------
def _lh6_pt(op, x, y):
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


def _lh6_side(side, op):
    s = str(side or '')
    valid = (PinSide.LEFT.value, PinSide.RIGHT.value, PinSide.TOP.value, PinSide.BOTTOM.value)
    if s not in valid:
        return s
    if op[0] == 'flip_h':
        # Mirror at X-axis: top/bottom swap, left/right stay.
        return {PinSide.TOP.value: PinSide.BOTTOM.value,
                PinSide.BOTTOM.value: PinSide.TOP.value}.get(s, s)
    if op[0] == 'flip_v':
        # Mirror at Y-axis: left/right swap, top/bottom stay.
        return {PinSide.LEFT.value: PinSide.RIGHT.value,
                PinSide.RIGHT.value: PinSide.LEFT.value}.get(s, s)
    if op[0] == 'rotate':
        d = int(round(float(op[1]) / 90.0)) % 4
        cw = {
            PinSide.RIGHT.value: PinSide.BOTTOM.value,
            PinSide.BOTTOM.value: PinSide.LEFT.value,
            PinSide.LEFT.value: PinSide.TOP.value,
            PinSide.TOP.value: PinSide.RIGHT.value,
        }
        for _ in range(d):
            s = cw.get(s, s)
    return s


def _lh8_flip_selected_horizontal(self):
    # Flip H = mirror at horizontal X-axis.
    _lh7_do_body_transform(self, 'flip_h', None)


def _lh8_flip_selected_vertical(self):
    # Flip V = mirror at vertical Y-axis.
    _lh7_do_body_transform(self, 'flip_v', None)

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.flip_selected_horizontal = _lh8_flip_selected_horizontal
        _cls.flip_selected_vertical = _lh8_flip_selected_vertical
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v9: imported BODY artwork must always remain selectable as BODY.
# After several rebuild/transform/filter cycles BODY_GRAPHIC items could keep an
# old selectable state or be ignored by Ctrl+A because BODY_GRAPHIC is not part
# of the public selection filter.  Treat BODY_GRAPHIC as BODY everywhere in the
# Symbol Wizard selection layer while still preventing primitive editing.
# ---------------------------------------------------------------------------
def _lh9_is_body_graphic_item(item):
    try:
        return getattr(item, 'data', lambda *_: None)(0) == 'BODY_GRAPHIC'
    except Exception:
        return False


def _lh9_body_item_candidates(self):
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


def _lh9_select_logical_body(self):
    try:
        candidates = _lh9_body_item_candidates(self)
        if not candidates:
            return False
        self.scene.blockSignals(True)
        self.scene.clearSelection()
        candidates[0].setSelected(True)
        self.scene.blockSignals(False)
        self.refresh_properties()
        return True
    except Exception:
        try: self.scene.blockSignals(False)
        except Exception: pass
        return False


try:
    _lh9_prev_apply_item_selectability = MainWindow.apply_item_selectability
except Exception:
    _lh9_prev_apply_item_selectability = None


def _lh9_apply_item_selectability(self, item):
    if _lh9_is_body_graphic_item(item):
        selectable = bool(getattr(self, 'selection_enabled', {}).get('BODY', True))
        try: item.setFlag(QGraphicsItem.ItemIsSelectable, selectable)
        except Exception: pass
        # BODY artwork is selectable as the logical BODY, but never movable as a
        # separate primitive in the Symbol Wizard.  Transforms are routed through
        # the BODY group backend.
        try: item.setFlag(QGraphicsItem.ItemIsMovable, False)
        except Exception: pass
        try: item.setAcceptedMouseButtons(Qt.AllButtons if selectable else Qt.NoButton)
        except Exception: pass
        try:
            if not selectable:
                item.setSelected(False)
        except Exception: pass
        try: item.setZValue(0.2)
        except Exception: pass
        return
    if _lh9_prev_apply_item_selectability is not None:
        return _lh9_prev_apply_item_selectability(self, item)


try:
    _lh9_prev_apply_filter = MainWindow._apply_selection_filter_to_scene
except Exception:
    _lh9_prev_apply_filter = None


def _lh9_apply_selection_filter_to_scene(self):
    # Apply normal filtering first, then explicitly include BODY_GRAPHIC as BODY.
    if _lh9_prev_apply_filter is not None:
        try:
            _lh9_prev_apply_filter(self)
        except Exception:
            pass
    try:
        for item in self.scene.items():
            if _lh9_is_body_graphic_item(item):
                _lh9_apply_item_selectability(self, item)
    except Exception:
        pass


try:
    _lh9_prev_select_all_canvas = MainWindow.select_all_canvas
except Exception:
    _lh9_prev_select_all_canvas = None


def _lh9_select_all_canvas(self):
    try: self.set_tool(DrawTool.SELECT.value)
    except Exception: pass
    # With Selectable=BODY, Ctrl+A must select the logical BODY even when the
    # body is represented only by imported graphics and no BodyItem exists.
    if bool(getattr(self, 'selection_enabled', {}).get('BODY', True)) and not any(
        bool(getattr(self, 'selection_enabled', {}).get(k, False)) for k in ('PIN', 'TEXT', 'GRAPHIC')
    ):
        if _lh9_select_logical_body(self):
            return
    try:
        self.scene.clearSelection()
        selected_body_rep = False
        for item in self.scene.items():
            kind = item.data(0)
            filter_kind = 'TEXT' if kind in ('ATTR_REF_DES', 'ATTR_BODY') else ('BODY' if kind == 'BODY_GRAPHIC' else kind)
            if filter_kind in ('BODY', 'PIN', 'TEXT', 'GRAPHIC') and self.selection_enabled.get(filter_kind, True):
                # Body graphics represent one logical BODY. Select just one
                # representative to avoid multi-edit/property-panel confusion.
                if kind == 'BODY_GRAPHIC':
                    if selected_body_rep:
                        item.setSelected(False)
                        continue
                    selected_body_rep = True
                item.setSelected(True)
        self.refresh_properties()
    except Exception:
        if _lh9_prev_select_all_canvas is not None:
            return _lh9_prev_select_all_canvas(self)


try:
    _lh9_prev_refresh_properties = MainWindow.refresh_properties
except Exception:
    _lh9_prev_refresh_properties = None


def _lh9_refresh_properties(self):
    # If several BODY_GRAPHIC primitives became selected by rubber-band or stale
    # restore ids, collapse them to one logical BODY before building the panel.
    try:
        selected = list(self.scene.selectedItems())
        bg = [i for i in selected if _lh9_is_body_graphic_item(i)]
        if len(bg) > 1 and len(bg) == len(selected):
            self.scene.blockSignals(True)
            self.scene.clearSelection()
            bg[0].setSelected(True)
            self.scene.blockSignals(False)
    except Exception:
        try: self.scene.blockSignals(False)
        except Exception: pass
    if _lh9_prev_refresh_properties is not None:
        return _lh9_prev_refresh_properties(self)


try:
    _lh9_prev_selected_body_active = MainWindow._selected_body_active
except Exception:
    _lh9_prev_selected_body_active = None


def _lh9_selected_body_active(self):
    try:
        for it in self.scene.selectedItems():
            if getattr(it, 'data', lambda *_: None)(0) in ('BODY', 'BODY_GRAPHIC'):
                return True
            m = getattr(it, 'model', None)
            if m is not None and (getattr(m, 'locked_to_body', False) or str(getattr(m, 'graphic_role', '') or '').lower() in ('body', 'template_body', 'imported_body')):
                return True
    except Exception:
        pass
    if _lh9_prev_selected_body_active is not None:
        try: return bool(_lh9_prev_selected_body_active(self))
        except Exception: pass
    return False


try:
    MainWindow.apply_item_selectability = _lh9_apply_item_selectability
    MainWindow._apply_selection_filter_to_scene = _lh9_apply_selection_filter_to_scene
    MainWindow.select_all_canvas = _lh9_select_all_canvas
    MainWindow.refresh_properties = _lh9_refresh_properties
    MainWindow._selected_body_active = _lh9_selected_body_active
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v10: canvas BODY scale without scaling pins + BODY graphic selection.
# Baseline: Symbol_Wizard_39.  BODY resize/Scale +/- changes the BODY geometry
# only. Pins are re-docked and snapped to the edit grid, but pin length, pin font
# sizes and text glyphs are not scaled.  Imported/template BODY graphics are the
# real BODY and are scaled directly; no proxy rectangle is introduced.
# ---------------------------------------------------------------------------
def _lh10_edit_grid_step(self):
    try:
        return max(0.001, float(getattr(self, 'edit_grid_step', None) or self.edit_grid.value() or self.grid_inch))
    except Exception:
        try: return max(0.001, float(getattr(self, 'grid_inch', 1.0) or 1.0))
        except Exception: return 1.0


def _lh10_snap_edit(self, v):
    step = _lh10_edit_grid_step(self)
    try: return self._clean_float(round(float(v) / step) * step)
    except Exception: return v


def _lh10_body_graphics(self, unit=None):
    u = unit or getattr(self, 'current_unit', None)
    out = []
    for gr in getattr(u, 'graphics', []) or []:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        raw = str(getattr(gr, 'mentor_raw', '') or '')
        if getattr(gr, 'locked_to_body', False) or role in ('body', 'template_body', 'imported_body') or (raw != '__USER_GRAPHIC__' and role != 'user_graphic'):
            out.append(gr)
    return out


def _lh10_graphic_points(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    # GraphicItem uses model endpoint (x+w, y-h) in grid coordinates.
    return (x, y, x + w, y - h)


def _lh10_body_graphics_bounds(self, unit=None):
    gs = _lh10_body_graphics(self, unit)
    if not gs:
        b = (unit or self.current_unit).body
        return (float(b.x), float(b.y), float(b.width), float(b.height))
    xs, ys = [], []
    for gr in gs:
        x1, y1, x2, y2 = _lh10_graphic_points(gr)
        xs.extend([x1, x2]); ys.extend([y1, y2])
        try:
            if getattr(gr, 'ctrl_x', None) is not None and getattr(gr, 'ctrl_y', None) is not None:
                xs.append(x1 + float(gr.ctrl_x)); ys.append(y1 - float(gr.ctrl_y))
        except Exception:
            pass
    left, right = min(xs), max(xs)
    bottom, top = min(ys), max(ys)
    return (self._clean_float(left), self._clean_float(top), self._clean_float(max(0.01, right-left)), self._clean_float(max(0.01, top-bottom)))


def _lh10_sync_body_to_body_graphics(self, unit=None):
    u = unit or self.current_unit
    gs = _lh10_body_graphics(self, u)
    if not gs:
        return
    x, y, w, h = _lh10_body_graphics_bounds(self, u)
    b = u.body
    b.x, b.y, b.width, b.height = x, y, w, h


def _lh10_move_pin_owned_texts_safe(self, pin, dx, dy):
    try:
        self._move_pin_owned_texts(pin, dx, dy)
    except Exception:
        for ax, ay in (('label_x','label_y'), ('number_x','number_y')):
            if getattr(pin, ax, None) is not None and getattr(pin, ay, None) is not None:
                try:
                    setattr(pin, ax, float(getattr(pin, ax)) + dx)
                    setattr(pin, ay, float(getattr(pin, ay)) + dy)
                except Exception: pass
        for tm in (getattr(pin, 'attribute_texts', {}) or {}).values():
            try: tm.x, tm.y = float(tm.x) + dx, float(tm.y) + dy
            except Exception: pass


def _lh10_redock_pins_after_body_scale(self, start_state, body):
    old_x = float(start_state.get('x', body.x)); old_y = float(start_state.get('y', body.y))
    old_w = max(float(start_state.get('w', body.width)), 1e-9)
    old_h = max(float(start_state.get('h', body.height)), 1e-9)
    new_x, new_y = float(body.x), float(body.y)
    new_w, new_h = max(float(body.width), 1e-9), max(float(body.height), 1e-9)
    sx, sy = new_w / old_w, new_h / old_h

    def sxpos(px): return _lh10_snap_edit(self, new_x + (float(px) - old_x) * sx)
    def sypos(py): return _lh10_snap_edit(self, new_y - (old_y - float(py)) * sy)

    for p, px, py, plen in start_state.get('pins', []) or []:
        ox, oy = float(getattr(p, 'x', px)), float(getattr(p, 'y', py))
        side = getattr(p, 'side', '')
        if side == PinSide.LEFT.value:
            nx, ny = new_x, sypos(py)
        elif side == PinSide.RIGHT.value:
            nx, ny = new_x + new_w, sypos(py)
        elif side == PinSide.TOP.value:
            nx, ny = sxpos(px), new_y
        elif side == PinSide.BOTTOM.value:
            nx, ny = sxpos(px), new_y - new_h
        else:
            nx, ny = sxpos(px), sypos(py)
        nx, ny = _lh10_snap_edit(self, nx), _lh10_snap_edit(self, ny)
        p.x, p.y = nx, ny
        # Critical: BODY scale must not scale pins.  Length stays as authored.
        try: p.length = max(0.1, float(plen))
        except Exception: pass
        _lh10_move_pin_owned_texts_safe(self, p, nx - ox, ny - oy)


def _lh10_scale_body_graphics_to(self, unit, old_bounds, new_bounds):
    gs = _lh10_body_graphics(self, unit)
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
        x1, y1, x2, y2 = _lh10_graphic_points(gr)
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
    _lh10_sync_body_to_body_graphics(self, unit)


def _lh10_scale_body_only_to(self, new_w, new_h, refresh=True):
    """Resize BODY to edit-grid dimensions without scaling pins/text glyphs."""
    u = self.current_unit; b = u.body
    old_bounds = _lh10_body_graphics_bounds(self, u) if _lh10_body_graphics(self, u) else (float(b.x), float(b.y), float(b.width), float(b.height))
    old_x, old_y, old_w, old_h = old_bounds
    new_w = max(_lh10_edit_grid_step(self), _lh10_snap_edit(self, new_w))
    new_h = max(_lh10_edit_grid_step(self), _lh10_snap_edit(self, new_h))
    start = {
        'x': old_x, 'y': old_y, 'w': old_w, 'h': old_h,
        'pins': [(p, float(p.x), float(p.y), float(getattr(p, 'length', 1.0) or 1.0)) for p in getattr(u, 'pins', []) or []],
        'texts': [(t, float(t.x), float(t.y)) for t in getattr(u, 'texts', []) or []],
        'attributes': [(t, float(t.x), float(t.y)) for t in (getattr(b, 'attribute_texts', {}) or {}).values()],
        'graphics': [(gr, float(gr.x), float(gr.y), float(getattr(gr, 'w', 0.0) or 0.0), float(getattr(gr, 'h', 0.0) or 0.0)) for gr in getattr(u, 'graphics', []) or [] if gr not in _lh10_body_graphics(self, u)],
    }
    # Keep the authored top-left anchor. This matches canvas drag-resize behaviour.
    new_bounds = (old_x, old_y, new_w, new_h)
    if _lh10_body_graphics(self, u):
        _lh10_scale_body_graphics_to(self, u, old_bounds, new_bounds)
    else:
        b.x, b.y, b.width, b.height = old_x, old_y, new_w, new_h
    _lh10_redock_pins_after_body_scale(self, start, b)
    # Non-pin text/user graphics are repositioned proportionally to stay attached,
    # but their font size/visual scale is intentionally unchanged.
    sx, sy = new_w / max(old_w, 1e-9), new_h / max(old_h, 1e-9)
    def map_pos(x, y): return (_lh10_snap_edit(self, old_x + (float(x)-old_x)*sx), _lh10_snap_edit(self, old_y - (old_y-float(y))*sy))
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


def _lh10_scale_current_unit_children_from_body_resize(self, start_state, body):
    """Canvas BODY handle resize: scale BODY graphics only; pins stay grid/length."""
    u = self.current_unit
    old_bounds = (float(start_state.get('x', body.x)), float(start_state.get('y', body.y)),
                  max(float(start_state.get('w', body.width)), 1e-9), max(float(start_state.get('h', body.height)), 1e-9))
    new_w = _lh10_snap_edit(self, float(body.width))
    new_h = _lh10_snap_edit(self, float(body.height))
    body.width, body.height = max(_lh10_edit_grid_step(self), new_w), max(_lh10_edit_grid_step(self), new_h)
    new_bounds = (float(body.x), float(body.y), float(body.width), float(body.height))
    if _lh10_body_graphics(self, u):
        _lh10_scale_body_graphics_to(self, u, old_bounds, new_bounds)
    _lh10_redock_pins_after_body_scale(self, start_state, body)
    # Texts/body attributes follow the body proportionally; glyphs are not scaled.
    ox, oy, ow, oh = old_bounds; nx, ny, nw, nh = new_bounds
    sx, sy = nw / max(ow, 1e-9), nh / max(oh, 1e-9)
    def map_pos(x, y): return (_lh10_snap_edit(self, nx + (float(x)-ox)*sx), _lh10_snap_edit(self, ny - (oy-float(y))*sy))
    for t, tx, ty in start_state.get('texts', []) or []:
        t.x, t.y = map_pos(tx, ty)
    for t, tx, ty in start_state.get('attributes', []) or []:
        t.x, t.y = map_pos(tx, ty)
    # User graphics are separate objects: move anchor only, do not scale their size.
    body_graphics = set(_lh10_body_graphics(self, u))
    for gr, gx, gy, gw, gh in start_state.get('graphics', []) or []:
        if gr in body_graphics:
            continue
        gr.x, gr.y = map_pos(gx, gy)
        gr.w, gr.h = gw, gh
    try: delattr(u, '_body_group_transform')
    except Exception: pass


try:
    _lh10_prev_transform_unit_as_body_group = MainWindow._transform_unit_as_body_group
except Exception:
    _lh10_prev_transform_unit_as_body_group = None


def _lh10_transform_unit_as_body_group(self, op, value=None, refresh=True):
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
        return _lh10_scale_body_only_to(self, new_w, new_h, refresh=refresh)
    if _lh10_prev_transform_unit_as_body_group is not None:
        return _lh10_prev_transform_unit_as_body_group(self, op, value, refresh)


try:
    _lh10_prev_graphic_mouse_press = GraphicItem.mousePressEvent
except Exception:
    _lh10_prev_graphic_mouse_press = None


def _lh10_graphic_mouse_press(self, event):
    # Clicking imported/template BODY artwork in Symbol Wizard selects the logical
    # BODY item so canvas handles (including scale) operate exactly like Symbol 1.
    try:
        if (getattr(getattr(self, 'model', None), 'locked_to_body', False)
                and not getattr(self.window, 'is_template_editor', False)
                and event.button() == Qt.LeftButton):
            cands = _lh9_body_item_candidates(self.window) if '_lh9_body_item_candidates' in globals() else []
            body_items = [i for i in cands if getattr(i, 'data', lambda *_: None)(0) == 'BODY']
            target = body_items[0] if body_items else (cands[0] if cands else self)
            try: self.window.scene.clearSelection()
            except Exception: pass
            target.setSelected(True)
            try: self.window.refresh_properties()
            except Exception: pass
            event.accept()
            return
    except Exception:
        pass
    if _lh10_prev_graphic_mouse_press is not None:
        return _lh10_prev_graphic_mouse_press(self, event)


try:
    MainWindow.scale_current_unit_children_from_body_resize = _lh10_scale_current_unit_children_from_body_resize
    MainWindow._transform_unit_as_body_group = _lh10_transform_unit_as_body_group
    MainWindow._lh10_scale_body_only_to = _lh10_scale_body_only_to
    MainWindow._lh10_sync_body_to_body_graphics = _lh10_sync_body_to_body_graphics
    GraphicItem.mousePressEvent = _lh10_graphic_mouse_press
except Exception:
    pass

# ---------------------------------------------------------------------------
# SW39 retry fix: unify BODY style/scale handling for Symbol1/import/templates.
# - Property-panel BODY width/height and toolbar Scale +/- use one safe path.
# - Canvas BODY handle resize uses the same path for imported/template graphics.
# - BODY graphics are detected by role/lock/mentor flags, not by proxy frame.
# - Pins are never scaled; they are redocked/snapped to edit grid and keep length.
# - Line style/width apply to all selected graphical objects; RGB applies to all.
# ---------------------------------------------------------------------------

def _sw39_edit_step(self):
    try:
        return max(0.001, float(getattr(self, 'edit_grid_step', 0) or self.edit_grid.value() or self.grid_inch or 1.0))
    except Exception:
        return 1.0


def _sw39_clean(self, v):
    try:
        v = round(float(v), 9)
        return 0.0 if abs(v) < 1e-9 else v
    except Exception:
        return v


def _sw39_snap(self, v):
    step = _sw39_edit_step(self)
    try:
        return _sw39_clean(self, round(float(v) / step) * step)
    except Exception:
        return float(v)


def _sw39_is_imported_or_template_body(self, unit=None):
    try:
        u = unit or self.current_unit
        b = u.body
        attrs = getattr(b, 'attributes', {}) or {}
        flags = ('MENTOR_GRAPHICS_AS_BODY', 'TEMPLATE_GRAPHICS_AS_BODY', 'MENTOR_HAS_BODY')
        if any(str(attrs.get(k, '0')).strip().upper() in ('1', 'TRUE', 'YES') for k in flags):
            return True
        return any(getattr(g, 'locked_to_body', False) or str(getattr(g, 'graphic_role', '')).lower() in ('body','template_body','imported_body') for g in getattr(u, 'graphics', []) or [])
    except Exception:
        return False


def _sw39_body_graphics(self, unit=None):
    """Return real graphics that visually form the BODY.

    Imported/template symbols must not have a proxy rectangle.  The imported
    primitives themselves are the BODY.  User-added graphics stay separate and
    therefore are excluded.
    """
    try:
        u = unit or self.current_unit
        imported = _sw39_is_imported_or_template_body(self, u)
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

# Override legacy global helper used by the previous patch, if present.
try:
    _lh10_body_graphics = _sw39_body_graphics
except Exception:
    pass


def _sw39_graphic_bounds(g):
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


def _sw39_body_graphics_bounds(self, unit=None):
    gs = _sw39_body_graphics(self, unit)
    if not gs:
        b = (unit or self.current_unit).body
        return (float(b.x), float(b.y), float(b.width), float(b.height))
    mins = [_sw39_graphic_bounds(g) for g in gs]
    xmin = min(v[0] for v in mins); ymin = min(v[1] for v in mins)
    xmax = max(v[2] for v in mins); ymax = max(v[3] for v in mins)
    # Body model uses top-left y and positive height downward in this tool.
    return (_sw39_clean(self, xmin), _sw39_clean(self, ymax), _sw39_clean(self, xmax - xmin), _sw39_clean(self, ymax - ymin))

try:
    _lh10_body_graphics_bounds = _sw39_body_graphics_bounds
except Exception:
    pass


def _sw39_sync_body_to_real_graphics(self, unit=None):
    u = unit or self.current_unit
    try:
        x, y, w, h = _sw39_body_graphics_bounds(self, u)
        u.body.x, u.body.y, u.body.width, u.body.height = x, y, max(_sw39_edit_step(self), w), max(_sw39_edit_step(self), h)
    except Exception:
        pass


def _sw39_scale_graphics_to_bounds(self, unit, old_bounds, new_bounds):
    gs = _sw39_body_graphics(self, unit)
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
        g.x = _sw39_clean(self, nx + (gx - ox) * sx)
        g.y = _sw39_clean(self, ny - (oy - gy) * sy)
        g.w = _sw39_clean(self, gw * sx)
        g.h = _sw39_clean(self, gh * sy)
        try:
            if getattr(g, 'ctrl_x', None) is not None:
                g.ctrl_x = _sw39_clean(self, float(g.ctrl_x) * sx)
            if getattr(g, 'ctrl_y', None) is not None:
                g.ctrl_y = _sw39_clean(self, float(g.ctrl_y) * sy)
        except Exception:
            pass
    _sw39_sync_body_to_real_graphics(self, unit)


def _sw39_move_pin_owned_texts(self, pin, dx, dy):
    try:
        self._move_pin_owned_texts(pin, dx, dy)
        return
    except Exception:
        pass
    for ax, ay in (('label_x','label_y'), ('number_x','number_y')):
        try:
            if getattr(pin, ax, None) is not None and getattr(pin, ay, None) is not None:
                setattr(pin, ax, _sw39_clean(self, float(getattr(pin, ax)) + dx))
                setattr(pin, ay, _sw39_clean(self, float(getattr(pin, ay)) + dy))
        except Exception:
            pass
    for tm in (getattr(pin, 'attribute_texts', {}) or {}).values():
        try:
            tm.x = _sw39_clean(self, float(tm.x) + dx)
            tm.y = _sw39_clean(self, float(tm.y) + dy)
        except Exception:
            pass


def _sw39_redock_pins_to_scaled_body(self, unit, start, old_bounds, new_bounds):
    ox, oy, ow, oh = old_bounds
    nx, ny, nw, nh = new_bounds
    sx, sy = float(nw) / max(float(ow), 1e-9), float(nh) / max(float(oh), 1e-9)
    for p, px, py, plen in start.get('pins', []) or []:
        old_px, old_py = float(getattr(p, 'x', px)), float(getattr(p, 'y', py))
        side = getattr(p, 'side', '')
        # Pins must remain on edit-grid and keep their authored length.  Only the
        # docking coordinate follows the resized BODY.
        if side == PinSide.LEFT.value:
            tx = nx; ty = ny - (oy - float(py)) * sy
        elif side == PinSide.RIGHT.value:
            tx = nx + nw; ty = ny - (oy - float(py)) * sy
        elif side == PinSide.TOP.value:
            tx = nx + (float(px) - ox) * sx; ty = ny
        elif side == PinSide.BOTTOM.value:
            tx = nx + (float(px) - ox) * sx; ty = ny - nh
        else:
            tx = nx + (float(px) - ox) * sx; ty = ny - (oy - float(py)) * sy
        p.x = _sw39_snap(self, tx)
        p.y = _sw39_snap(self, ty)
        try:
            p.length = float(plen)
        except Exception:
            pass
        _sw39_move_pin_owned_texts(self, p, p.x - old_px, p.y - old_py)


def _sw39_capture_resize_state(self, unit=None):
    u = unit or self.current_unit
    b = u.body
    return {
        'x': float(b.x), 'y': float(b.y), 'w': float(b.width), 'h': float(b.height),
        'pins': [(p, float(p.x), float(p.y), float(getattr(p, 'length', 1.0) or 1.0)) for p in getattr(u, 'pins', []) or []],
        'texts': [(t, float(t.x), float(t.y)) for t in getattr(u, 'texts', []) or []],
        'attributes': [(t, float(t.x), float(t.y)) for t in (getattr(b, 'attribute_texts', {}) or {}).values()],
        'graphics': [(g, float(g.x), float(g.y), float(getattr(g, 'w', 0.0) or 0.0), float(getattr(g, 'h', 0.0) or 0.0)) for g in getattr(u, 'graphics', []) or [] if g not in _sw39_body_graphics(self, u)],
    }


def _sw39_resize_body_geometry(self, new_w=None, new_h=None, refresh=True):
    if getattr(self, '_sw39_resizing_body', False):
        return
    self._sw39_resizing_body = True
    try:
        u = self.current_unit
        b = u.body
        step = _sw39_edit_step(self)
        old_bounds = _sw39_body_graphics_bounds(self, u)
        ox, oy, ow, oh = old_bounds
        new_w = max(step, _sw39_snap(self, ow if new_w is None else new_w))
        new_h = max(step, _sw39_snap(self, oh if new_h is None else new_h))
        start = _sw39_capture_resize_state(self, u)
        # Keep the current BODY top-left anchor. Origin handling is done by Origin Reset;
        # resize itself is deterministic and edit-grid based.
        new_bounds = (ox, oy, new_w, new_h)
        if _sw39_body_graphics(self, u):
            _sw39_scale_graphics_to_bounds(self, u, old_bounds, new_bounds)
        else:
            b.x, b.y, b.width, b.height = ox, oy, new_w, new_h
        # BODY scale does not scale pins. It only redocks them to the new edge/grid.
        _sw39_redock_pins_to_scaled_body(self, u, start, old_bounds, (b.x, b.y, b.width, b.height))
        # Attached non-pin texts/attributes follow position proportionally; glyph size is unchanged.
        nx, ny, nw, nh = float(b.x), float(b.y), float(b.width), float(b.height)
        sx, sy = nw / max(ow, 1e-9), nh / max(oh, 1e-9)
        def map_pos(x, y):
            return (_sw39_snap(self, nx + (float(x)-ox)*sx), _sw39_snap(self, ny - (oy-float(y))*sy))
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
        self._sw39_resizing_body = False
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


def _sw39_set_body_width_grid(self, body, value):
    try:
        new_w = max(_sw39_edit_step(self), _sw39_snap(self, float(value)))
        cur_w = float(getattr(self.current_unit.body, 'width', new_w) or new_w)
        if abs(new_w - cur_w) < 1e-9:
            return
        self.push_undo_state()
        self._selection_restore_ids = self._capture_selection_ids()
        _sw39_resize_body_geometry(self, new_w=new_w, new_h=None, refresh=True)
    except Exception as e:
        try: self.statusBar().showMessage(f'BODY width update failed: {e}', 4000)
        except Exception: pass


def _sw39_set_body_height_grid(self, body, value):
    try:
        new_h = max(_sw39_edit_step(self), _sw39_snap(self, float(value)))
        cur_h = float(getattr(self.current_unit.body, 'height', new_h) or new_h)
        if abs(new_h - cur_h) < 1e-9:
            return
        self.push_undo_state()
        self._selection_restore_ids = self._capture_selection_ids()
        _sw39_resize_body_geometry(self, new_w=None, new_h=new_h, refresh=True)
    except Exception as e:
        try: self.statusBar().showMessage(f'BODY height update failed: {e}', 4000)
        except Exception: pass


def _sw39_transform_unit_as_body_group(self, op, value=None, refresh=True):
    if op in ('scale', 'scale_x_to', 'scale_y_to'):
        b = self.current_unit.body
        cur_w = float(getattr(b, 'width', 1.0) or 1.0)
        cur_h = float(getattr(b, 'height', 1.0) or 1.0)
        if op == 'scale_x_to':
            return _sw39_resize_body_geometry(self, new_w=float(value), new_h=None, refresh=refresh)
        if op == 'scale_y_to':
            return _sw39_resize_body_geometry(self, new_w=None, new_h=float(value), refresh=refresh)
        f = float(value or 1.0)
        return _sw39_resize_body_geometry(self, new_w=cur_w * f, new_h=cur_h * f, refresh=refresh)
    # Delegate rotate/flip to the already working Symbol1-like implementation.
    try:
        return _sw39_prev_transform_unit_as_body_group(self, op, value, refresh)
    except Exception:
        if '_lh10_prev_transform_unit_as_body_group' in globals() and _lh10_prev_transform_unit_as_body_group is not None:
            return _lh10_prev_transform_unit_as_body_group(self, op, value, refresh)

try:
    _sw39_prev_transform_unit_as_body_group = MainWindow._transform_unit_as_body_group
except Exception:
    _sw39_prev_transform_unit_as_body_group = None


def _sw39_scale_selected_grid(self, direction: int):
    self.set_tool(DrawTool.SELECT.value)
    if self._selected_body_active():
        step = _sw39_edit_step(self)
        b = self.current_unit.body
        self.push_undo_state()
        self._selection_restore_ids = self._capture_selection_ids()
        _sw39_resize_body_geometry(self, float(b.width) + direction * step, float(b.height) + direction * step, refresh=True)
    else:
        # Keep old behavior for non-BODY graphics.
        try: return _sw39_prev_scale_selected_grid(self, direction)
        except Exception: return self.scale_selected(1.0 + (0.1 if direction > 0 else -0.1))

try:
    _sw39_prev_scale_selected_grid = MainWindow.scale_selected_grid
except Exception:
    _sw39_prev_scale_selected_grid = None


def _sw39_scale_current_unit_children_from_body_resize(self, start_state, body):
    # Canvas handle resize. BodyItem has already changed body.x/y/width/height;
    # use that as requested target and apply the exact same resize pipeline to
    # the real BODY graphics. This enables canvas scaling for imported/template bodies.
    try:
        u = self.current_unit
        old_bounds = (float(start_state.get('x', body.x)), float(start_state.get('y', body.y)),
                      max(float(start_state.get('w', body.width)), 1e-9), max(float(start_state.get('h', body.height)), 1e-9))
        new_w = max(_sw39_edit_step(self), _sw39_snap(self, float(body.width)))
        new_h = max(_sw39_edit_step(self), _sw39_snap(self, float(body.height)))
        new_bounds = (_sw39_snap(self, float(body.x)), _sw39_snap(self, float(body.y)), new_w, new_h)
        if _sw39_body_graphics(self, u):
            _sw39_scale_graphics_to_bounds(self, u, old_bounds, new_bounds)
        else:
            body.x, body.y, body.width, body.height = new_bounds
        _sw39_redock_pins_to_scaled_body(self, u, start_state, old_bounds, (body.x, body.y, body.width, body.height))
        ox, oy, ow, oh = old_bounds; nx, ny, nw, nh = float(body.x), float(body.y), float(body.width), float(body.height)
        sx, sy = nw / max(ow, 1e-9), nh / max(oh, 1e-9)
        def map_pos(x, y):
            return (_sw39_snap(self, nx + (float(x)-ox)*sx), _sw39_snap(self, ny - (oy-float(y))*sy))
        for t, tx, ty in start_state.get('texts', []) or []:
            t.x, t.y = map_pos(tx, ty)
        for t, tx, ty in start_state.get('attributes', []) or []:
            t.x, t.y = map_pos(tx, ty)
        body_graphics = set(_sw39_body_graphics(self, u))
        for gr, gx, gy, gw, gh in start_state.get('graphics', []) or []:
            if gr in body_graphics:
                continue
            gr.x, gr.y = map_pos(gx, gy)
            gr.w, gr.h = gw, gh
        self.dirty = True
    except Exception as e:
        try: self.statusBar().showMessage(f'Canvas BODY scale failed: {e}', 4000)
        except Exception: pass


def _sw39_apply_line_defaults(self):
    selected = list(self.scene.selectedItems()) if hasattr(self, 'scene') else []
    if not selected:
        return
    style = self.line_style.currentText()
    width = float(self.line_width.value())
    self.push_undo_state()
    changed = False
    for it in selected:
        k = it.data(0); m = getattr(it, 'model', None)
        if m is None: continue
        if k == 'BODY':
            m.line_style = style; m.line_width = width; changed = True
            for gr in _sw39_body_graphics(self, self.current_unit):
                st = getattr(gr, 'style', None)
                if st is not None:
                    st.line_style = style; st.line_width = width
        elif k == 'GRAPHIC':
            st = getattr(m, 'style', None)
            if st is not None:
                st.line_style = style; st.line_width = width; changed = True
        elif k == 'PIN':
            m.line_style = style; m.line_width = width; changed = True
    if changed:
        self.dirty = True
        try: self.update_current_unit_canvas_positions()
        except Exception: pass
        self.schedule_scene_refresh(visual_only=True)


def _sw39_set_body_visual_attr(self, body, attr, value):
    if attr not in ('line_style', 'line_width', 'color'):
        return
    self.push_undo_state()
    setattr(body, attr, tuple(value) if attr == 'color' else value)
    for gr in _sw39_body_graphics(self, self.current_unit):
        st = getattr(gr, 'style', None)
        if st is None: continue
        if attr == 'line_style': st.line_style = value
        elif attr == 'line_width': st.line_width = float(value)
        elif attr == 'color': st.stroke = tuple(value)
    self.dirty = True
    try: self.update_current_unit_canvas_positions()
    except Exception: pass
    self.schedule_scene_refresh(visual_only=True)


def _sw39_apply_color_to_selected(self, color):
    selected = list(self.scene.selectedItems()) if hasattr(self, 'scene') else []
    if not selected:
        self.default_color = tuple(color); return
    self.push_undo_state()
    for it in selected:
        k = it.data(0); m = getattr(it, 'model', None)
        if m is None: continue
        if k == 'BODY':
            m.color = tuple(color)
            for gr in _sw39_body_graphics(self, self.current_unit):
                st = getattr(gr, 'style', None)
                if st is not None: st.stroke = tuple(color)
        elif k == 'GRAPHIC':
            st = getattr(m, 'style', None)
            if st is not None: st.stroke = tuple(color)
        elif k in ('PIN', 'TEXT', 'ATTR_REF_DES', 'ATTR_BODY'):
            try: m.color = tuple(color)
            except Exception: pass
            if k in ('ATTR_REF_DES', 'ATTR_BODY'):
                try: self._sync_body_font_from_attribute_text(it)
                except Exception: pass
    self.dirty = True
    try: self.update_current_unit_canvas_positions()
    except Exception: pass
    self.schedule_scene_refresh(visual_only=True)

try:
    MainWindow._body_owned_graphics = lambda self, body=None: _sw39_body_graphics(self, self.current_unit)
    MainWindow._set_body_width_grid = _sw39_set_body_width_grid
    MainWindow._set_body_height_grid = _sw39_set_body_height_grid
    MainWindow._transform_unit_as_body_group = _sw39_transform_unit_as_body_group
    MainWindow.scale_selected_grid = _sw39_scale_selected_grid
    MainWindow.scale_current_unit_children_from_body_resize = _sw39_scale_current_unit_children_from_body_resize
    MainWindow.apply_line_defaults = _sw39_apply_line_defaults
    MainWindow.set_body_visual_attr = _sw39_set_body_visual_attr
    MainWindow.apply_color_to_selected = _sw39_apply_color_to_selected
except Exception:
    pass


# ---------------------------------------------------------------------------
# Liebherr v44: BODY scaling from *_30 behavior, with pins kept unscaled.
# - Only BODY resize / Scale +/- is overridden here.
# - Rotate and flip continue to use the existing *_43 implementation.
# - Imported/template BODY primitives are scaled as one BODY shape; pins are
#   only re-docked to the new BODY edges and keep length/font/shape.
# - Adds the user-facing Clear Canvas alias for deleting all symbols.
# ---------------------------------------------------------------------------
def _lh44_clean(self, v):
    try:
        return self._clean_float(v)
    except Exception:
        try: return round(float(v), 6)
        except Exception: return v


def _lh44_edit_step(self):
    for name in ('edit_grid_step', 'grid_inch'):
        try:
            v = getattr(self, name, None)
            if v is not None:
                return max(0.001, float(v))
        except Exception:
            pass
    try:
        return max(0.001, float(self.edit_grid.value()))
    except Exception:
        return 1.0


def _lh44_snap(self, v):
    step = _lh44_edit_step(self)
    try: return _lh44_clean(self, round(float(v) / step) * step)
    except Exception: return float(v)


def _lh44_is_body_graphic(self, gr):
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


def _lh44_body_graphics(self, unit=None):
    u = unit or getattr(self, 'current_unit', None)
    return [g for g in (getattr(u, 'graphics', []) or []) if _lh44_is_body_graphic(self, g)]


def _lh44_graphic_points(gr):
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


def _lh44_body_bounds(self, unit=None):
    u = unit or self.current_unit
    gs = _lh44_body_graphics(self, u)
    if not gs:
        b = u.body
        return (float(b.x), float(b.y), float(b.width), float(b.height))
    pts = []
    for g in gs:
        pts.extend(_lh44_graphic_points(g))
    if not pts:
        b = u.body
        return (float(b.x), float(b.y), float(b.width), float(b.height))
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return (_lh44_clean(self, min(xs)), _lh44_clean(self, max(ys)),
            _lh44_clean(self, max(0.01, max(xs) - min(xs))),
            _lh44_clean(self, max(0.01, max(ys) - min(ys))))


def _lh44_sync_body_to_graphics(self, unit=None):
    u = unit or self.current_unit
    if not _lh44_body_graphics(self, u):
        return
    x, y, w, h = _lh44_body_bounds(self, u)
    u.body.x, u.body.y, u.body.width, u.body.height = x, y, w, h
    try: u.body.rotation = 0.0
    except Exception: pass


def _lh44_scale_body_graphics_to(self, unit, old_bounds, new_bounds):
    gs = _lh44_body_graphics(self, unit)
    if not gs: return
    ox, oy, ow, oh = old_bounds; nx, ny, nw, nh = new_bounds
    sx = float(nw) / max(float(ow), 1e-9); sy = float(nh) / max(float(oh), 1e-9)
    def mp(x, y):
        return (_lh44_clean(self, nx + (float(x) - ox) * sx),
                _lh44_clean(self, ny - (oy - float(y)) * sy))
    for g in gs:
        x = float(getattr(g, 'x', 0.0) or 0.0); y = float(getattr(g, 'y', 0.0) or 0.0)
        w = float(getattr(g, 'w', 0.0) or 0.0); h = float(getattr(g, 'h', 0.0) or 0.0)
        x1, y1 = mp(x, y); x2, y2 = mp(x + w, y - h)
        g.x, g.y = x1, y1
        g.w, g.h = _lh44_clean(self, x2 - x1), _lh44_clean(self, y1 - y2)
        try:
            if getattr(g, 'ctrl_x', None) is not None: g.ctrl_x = _lh44_clean(self, float(g.ctrl_x) * sx)
            if getattr(g, 'ctrl_y', None) is not None: g.ctrl_y = _lh44_clean(self, float(g.ctrl_y) * sy)
            if getattr(g, 'curve_radius', None) is not None: g.curve_radius = _lh44_clean(self, float(g.curve_radius) * ((abs(sx)+abs(sy))/2.0))
        except Exception: pass
    _lh44_sync_body_to_graphics(self, unit)


def _lh44_move_pin_texts(self, pin, dx, dy):
    try:
        self._move_pin_owned_texts(pin, dx, dy); return
    except Exception:
        pass
    for ax, ay in (('label_x','label_y'), ('number_x','number_y')):
        try:
            if getattr(pin, ax, None) is not None and getattr(pin, ay, None) is not None:
                setattr(pin, ax, _lh44_clean(self, float(getattr(pin, ax)) + dx))
                setattr(pin, ay, _lh44_clean(self, float(getattr(pin, ay)) + dy))
        except Exception: pass
    for tm in (getattr(pin, 'attribute_texts', {}) or {}).values():
        try:
            tm.x = _lh44_clean(self, float(tm.x) + dx); tm.y = _lh44_clean(self, float(tm.y) + dy)
        except Exception: pass


def _lh44_capture_resize_state(self, unit=None):
    u = unit or self.current_unit; b = u.body
    return {
        'pins': [(p, float(p.x), float(p.y), float(getattr(p, 'length', 1.0) or 1.0)) for p in getattr(u, 'pins', []) or []],
        'texts': [(t, float(t.x), float(t.y)) for t in getattr(u, 'texts', []) or []],
        'attributes': [(t, float(t.x), float(t.y)) for t in (getattr(b, 'attribute_texts', {}) or {}).values()],
        'graphics': [(g, float(g.x), float(g.y), float(getattr(g, 'w', 0.0) or 0.0), float(getattr(g, 'h', 0.0) or 0.0)) for g in getattr(u, 'graphics', []) or [] if g not in _lh44_body_graphics(self, u)],
    }


def _lh44_redock_pins(self, unit, start, old_bounds, new_bounds):
    ox, oy, ow, oh = old_bounds; nx, ny, nw, nh = new_bounds
    sx = float(nw) / max(float(ow), 1e-9); sy = float(nh) / max(float(oh), 1e-9)
    for p, px, py, plen in start.get('pins', []) or []:
        old_px, old_py = float(getattr(p, 'x', px)), float(getattr(p, 'y', py))
        side = getattr(p, 'side', '')
        if side == PinSide.LEFT.value:
            tx, ty = nx, ny - (oy - py) * sy
        elif side == PinSide.RIGHT.value:
            tx, ty = nx + nw, ny - (oy - py) * sy
        elif side == PinSide.TOP.value:
            tx, ty = nx + (px - ox) * sx, ny
        elif side == PinSide.BOTTOM.value:
            tx, ty = nx + (px - ox) * sx, ny - nh
        else:
            tx, ty = nx + (px - ox) * sx, ny - (oy - py) * sy
        p.x, p.y = _lh44_snap(self, tx), _lh44_snap(self, ty)
        try: p.length = float(plen)
        except Exception: pass
        _lh44_move_pin_texts(self, p, p.x - old_px, p.y - old_py)


def _lh44_resize_body_geometry(self, new_w=None, new_h=None, refresh=True, anchor_bounds=None):
    if getattr(self, '_lh44_resizing_body', False): return
    self._lh44_resizing_body = True
    try:
        u = self.current_unit; b = u.body
        old_bounds = anchor_bounds or _lh44_body_bounds(self, u)
        ox, oy, ow, oh = old_bounds
        step = _lh44_edit_step(self)
        new_w = max(step, _lh44_snap(self, ow if new_w is None else new_w))
        new_h = max(step, _lh44_snap(self, oh if new_h is None else new_h))
        start = _lh44_capture_resize_state(self, u)
        new_bounds = (ox, oy, new_w, new_h)
        if _lh44_body_graphics(self, u):
            _lh44_scale_body_graphics_to(self, u, old_bounds, new_bounds)
        else:
            b.x, b.y, b.width, b.height = ox, oy, new_w, new_h
        _lh44_redock_pins(self, u, start, old_bounds, (b.x, b.y, b.width, b.height))
        nx, ny, nw, nh = float(b.x), float(b.y), float(b.width), float(b.height)
        sx = nw / max(float(ow), 1e-9); sy = nh / max(float(oh), 1e-9)
        def map_pos(x, y): return (_lh44_snap(self, nx + (float(x)-ox)*sx), _lh44_snap(self, ny - (oy-float(y))*sy))
        for t, tx, ty in start.get('texts', []) or []: t.x, t.y = map_pos(tx, ty)
        for t, tx, ty in start.get('attributes', []) or []: t.x, t.y = map_pos(tx, ty)
        for g, gx, gy, gw, gh in start.get('graphics', []) or []:
            g.x, g.y = map_pos(gx, gy); g.w, g.h = gw, gh
        try:
            if hasattr(u, '_body_group_transform'): delattr(u, '_body_group_transform')
        except Exception: pass
        self.dirty = True
    finally:
        self._lh44_resizing_body = False
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


def _lh44_set_body_width_grid(self, body, value):
    try:
        new_w = max(_lh44_edit_step(self), _lh44_snap(self, float(value)))
        cur_w = float(getattr(self.current_unit.body, 'width', new_w) or new_w)
        if abs(new_w - cur_w) < 1e-9: return
        self.push_undo_state(); self._selection_restore_ids = self._capture_selection_ids()
        _lh44_resize_body_geometry(self, new_w=new_w, new_h=None, refresh=True)
    except Exception as e:
        try: self.statusBar().showMessage(f'BODY width update failed: {e}', 4000)
        except Exception: pass


def _lh44_set_body_height_grid(self, body, value):
    try:
        new_h = max(_lh44_edit_step(self), _lh44_snap(self, float(value)))
        cur_h = float(getattr(self.current_unit.body, 'height', new_h) or new_h)
        if abs(new_h - cur_h) < 1e-9: return
        self.push_undo_state(); self._selection_restore_ids = self._capture_selection_ids()
        _lh44_resize_body_geometry(self, new_w=None, new_h=new_h, refresh=True)
    except Exception as e:
        try: self.statusBar().showMessage(f'BODY height update failed: {e}', 4000)
        except Exception: pass


def _lh44_transform_unit_as_body_group(self, op, value=None, refresh=True):
    if op in ('scale', 'scale_x_to', 'scale_y_to'):
        b = self.current_unit.body
        cur_w = float(getattr(b, 'width', 1.0) or 1.0); cur_h = float(getattr(b, 'height', 1.0) or 1.0)
        if op == 'scale_x_to': return _lh44_resize_body_geometry(self, new_w=float(value), new_h=None, refresh=refresh)
        if op == 'scale_y_to': return _lh44_resize_body_geometry(self, new_w=None, new_h=float(value), refresh=refresh)
        f = float(value or 1.0)
        return _lh44_resize_body_geometry(self, new_w=cur_w * f, new_h=cur_h * f, refresh=refresh)
    if _lh44_prev_transform_unit_as_body_group is not None:
        return _lh44_prev_transform_unit_as_body_group(self, op, value, refresh)


def _lh44_scale_selected_grid(self, direction: int):
    self.set_tool(DrawTool.SELECT.value)
    if self._selected_body_active():
        b = self.current_unit.body; step = _lh44_edit_step(self)
        self.push_undo_state(); self._selection_restore_ids = self._capture_selection_ids()
        _lh44_resize_body_geometry(self, float(b.width) + direction * step, float(b.height) + direction * step, refresh=True)
    else:
        if _lh44_prev_scale_selected_grid is not None:
            return _lh44_prev_scale_selected_grid(self, direction)
        return self.scale_selected(1.0 + (0.1 if direction > 0 else -0.1))


def _lh44_scale_current_unit_children_from_body_resize(self, start_state, body):
    try:
        old_bounds = (float(start_state.get('x', body.x)), float(start_state.get('y', body.y)),
                      max(float(start_state.get('w', body.width)), 1e-9), max(float(start_state.get('h', body.height)), 1e-9))
        _lh44_resize_body_geometry(self, new_w=float(body.width), new_h=float(body.height), refresh=True, anchor_bounds=old_bounds)
    except Exception as e:
        try: self.statusBar().showMessage(f'Canvas BODY scale failed: {e}', 4000)
        except Exception: pass


def _lh44_clear_canvas(self):
    return self.delete_all_symbols()


try:
    _lh44_prev_transform_unit_as_body_group = MainWindow._transform_unit_as_body_group
except Exception:
    _lh44_prev_transform_unit_as_body_group = None
try:
    _lh44_prev_scale_selected_grid = MainWindow.scale_selected_grid
except Exception:
    _lh44_prev_scale_selected_grid = None
try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._body_owned_graphics = lambda self, body=None: _lh44_body_graphics(self, self.current_unit)
        _cls._set_body_width_grid = _lh44_set_body_width_grid
        _cls._set_body_height_grid = _lh44_set_body_height_grid
        _cls._transform_unit_as_body_group = _lh44_transform_unit_as_body_group
        _cls.scale_selected_grid = _lh44_scale_selected_grid
        _cls.scale_current_unit_children_from_body_resize = _lh44_scale_current_unit_children_from_body_resize
        _cls.clear_canvas = _lh44_clear_canvas
except Exception:
    pass


# --- LH45 stability patch -------------------------------------------------
# Keep the property panel on the current selection during toolbar/property edits,
# avoid synchronous property-panel rebuilds from editor signals, and ensure BODY
# resize never scales pin length/font data.
def _lh45_selected_model_ids(self):
    try:
        return {id(getattr(i, 'model', None)) for i in self.scene.selectedItems() if getattr(i, 'model', None) is not None}
    except Exception:
        return set()


def _lh45_restore_selection(self, ids=None):
    ids = set(ids or getattr(self, '_selection_restore_ids', set()) or [])
    if not ids:
        return
    try:
        self.scene.blockSignals(True)
        for it in self.scene.items():
            try:
                it.setSelected(id(getattr(it, 'model', None)) in ids)
            except Exception:
                pass
    finally:
        try: self.scene.blockSignals(False)
        except Exception: pass
    try: self.view.viewport().update()
    except Exception: pass


def _lh45_deferred_refresh(self, ids=None):
    ids = set(ids or _lh45_selected_model_ids(self) or getattr(self, '_selection_restore_ids', set()) or [])
    def run():
        try: _lh45_restore_selection(self, ids)
        except Exception: pass
        try: self.refresh_properties()
        except RuntimeError: pass
        except Exception: pass
    try: QTimer.singleShot(0, run)
    except Exception: run()


def _lh45_capture_resize_state(self, unit=None):
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
        'graphics': [(g, float(g.x), float(g.y), float(getattr(g, 'w', 0.0) or 0.0), float(getattr(g, 'h', 0.0) or 0.0)) for g in getattr(u, 'graphics', []) or [] if g not in _lh44_body_graphics(self, u)],
    }


def _lh45_redock_pins(self, unit, start, old_bounds, new_bounds):
    ox, oy, ow, oh = old_bounds; nx, ny, nw, nh = new_bounds
    sx = float(nw) / max(float(ow), 1e-9); sy = float(nh) / max(float(oh), 1e-9)
    for rec in start.get('pins', []) or []:
        p, px, py, plen = rec[:4]
        num_size = rec[4] if len(rec) > 4 else None
        lab_size = rec[5] if len(rec) > 5 else None
        old_px, old_py = float(getattr(p, 'x', px)), float(getattr(p, 'y', py))
        side = getattr(p, 'side', '')
        if side == PinSide.LEFT.value:
            tx, ty = nx, ny - (oy - py) * sy
        elif side == PinSide.RIGHT.value:
            tx, ty = nx + nw, ny - (oy - py) * sy
        elif side == PinSide.TOP.value:
            tx, ty = nx + (px - ox) * sx, ny
        elif side == PinSide.BOTTOM.value:
            tx, ty = nx + (px - ox) * sx, ny - nh
        else:
            tx, ty = nx + (px - ox) * sx, ny - (oy - py) * sy
        p.x, p.y = _lh44_snap(self, tx), _lh44_snap(self, ty)
        # Critical: pins are docked/repositioned to the BODY, but the pin itself
        # is never scaled. Keep length and label/number fonts exactly as before.
        try: p.length = float(plen)
        except Exception: pass
        try:
            if num_size is not None: p.number_font.size_grid = float(num_size)
        except Exception: pass
        try:
            if lab_size is not None: p.label_font.size_grid = float(lab_size)
        except Exception: pass
        _lh44_move_pin_texts(self, p, p.x - old_px, p.y - old_py)


def _lh45_resize_body_geometry(self, new_w=None, new_h=None, refresh=True, anchor_bounds=None):
    if getattr(self, '_lh44_resizing_body', False): return
    keep_ids = set(getattr(self, '_selection_restore_ids', set()) or _lh45_selected_model_ids(self))
    self._lh44_resizing_body = True
    try:
        u = self.current_unit; b = u.body
        old_bounds = anchor_bounds or _lh44_body_bounds(self, u)
        ox, oy, ow, oh = old_bounds
        step = _lh44_edit_step(self)
        new_w = max(step, _lh44_snap(self, ow if new_w is None else new_w))
        new_h = max(step, _lh44_snap(self, oh if new_h is None else new_h))
        start = _lh45_capture_resize_state(self, u)
        new_bounds = (ox, oy, new_w, new_h)
        if _lh44_body_graphics(self, u):
            _lh44_scale_body_graphics_to(self, u, old_bounds, new_bounds)
        else:
            b.x, b.y, b.width, b.height = ox, oy, new_w, new_h
        _lh45_redock_pins(self, u, start, old_bounds, (b.x, b.y, b.width, b.height))
        nx, ny, nw, nh = float(b.x), float(b.y), float(b.width), float(b.height)
        sx = nw / max(float(ow), 1e-9); sy = nh / max(float(oh), 1e-9)
        def map_pos(x, y): return (_lh44_snap(self, nx + (float(x)-ox)*sx), _lh44_snap(self, ny - (oy-float(y))*sy))
        for t, tx, ty in start.get('texts', []) or []: t.x, t.y = map_pos(tx, ty)
        for t, tx, ty in start.get('attributes', []) or []: t.x, t.y = map_pos(tx, ty)
        for g, gx, gy, gw, gh in start.get('graphics', []) or []:
            g.x, g.y = map_pos(gx, gy); g.w, g.h = gw, gh
        try:
            if hasattr(u, '_body_group_transform'): delattr(u, '_body_group_transform')
        except Exception: pass
        self.dirty = True
    finally:
        self._lh44_resizing_body = False
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
        _lh45_deferred_refresh(self, keep_ids)


def _lh45_set_body_width_grid(self, body, value):
    try:
        keep_ids = _lh45_selected_model_ids(self) or {id(body)}
        new_w = max(_lh44_edit_step(self), _lh44_snap(self, float(value)))
        cur_w = float(getattr(self.current_unit.body, 'width', new_w) or new_w)
        if abs(new_w - cur_w) < 1e-9: return
        self.push_undo_state(); self._selection_restore_ids = keep_ids
        _lh45_resize_body_geometry(self, new_w=new_w, new_h=None, refresh=True)
    except Exception as e:
        try: self.statusBar().showMessage(f'BODY width update failed: {e}', 4000)
        except Exception: pass


def _lh45_set_body_height_grid(self, body, value):
    try:
        keep_ids = _lh45_selected_model_ids(self) or {id(body)}
        new_h = max(_lh44_edit_step(self), _lh44_snap(self, float(value)))
        cur_h = float(getattr(self.current_unit.body, 'height', new_h) or new_h)
        if abs(new_h - cur_h) < 1e-9: return
        self.push_undo_state(); self._selection_restore_ids = keep_ids
        _lh45_resize_body_geometry(self, new_w=None, new_h=new_h, refresh=True)
    except Exception as e:
        try: self.statusBar().showMessage(f'BODY height update failed: {e}', 4000)
        except Exception: pass


def _lh45_transform_unit_as_body_group(self, op, value=None, refresh=True):
    if op in ('scale', 'scale_x_to', 'scale_y_to'):
        b = self.current_unit.body
        cur_w = float(getattr(b, 'width', 1.0) or 1.0); cur_h = float(getattr(b, 'height', 1.0) or 1.0)
        if op == 'scale_x_to': return _lh45_resize_body_geometry(self, new_w=float(value), new_h=None, refresh=refresh)
        if op == 'scale_y_to': return _lh45_resize_body_geometry(self, new_w=None, new_h=float(value), refresh=refresh)
        f = float(value or 1.0)
        return _lh45_resize_body_geometry(self, new_w=cur_w * f, new_h=cur_h * f, refresh=refresh)
    if _lh44_prev_transform_unit_as_body_group is not None:
        keep_ids = _lh45_selected_model_ids(self)
        r = _lh44_prev_transform_unit_as_body_group(self, op, value, refresh)
        _lh45_deferred_refresh(self, keep_ids)
        return r


def _lh45_scale_selected_grid(self, direction: int):
    self.set_tool(DrawTool.SELECT.value)
    if self._selected_body_active():
        b = self.current_unit.body; step = _lh44_edit_step(self)
        keep_ids = _lh45_selected_model_ids(self) or {id(b)}
        self.push_undo_state(); self._selection_restore_ids = keep_ids
        _lh45_resize_body_geometry(self, float(b.width) + direction * step, float(b.height) + direction * step, refresh=True)
    else:
        if _lh44_prev_scale_selected_grid is not None:
            keep_ids = _lh45_selected_model_ids(self)
            r = _lh44_prev_scale_selected_grid(self, direction)
            _lh45_deferred_refresh(self, keep_ids)
            return r
        return self.scale_selected(1.0 + (0.1 if direction > 0 else -0.1))


def _lh45_scale_current_unit_children_from_body_resize(self, start_state, body):
    try:
        keep_ids = _lh45_selected_model_ids(self) or {id(body)}
        self._selection_restore_ids = keep_ids
        old_bounds = (float(start_state.get('x', body.x)), float(start_state.get('y', body.y)),
                      max(float(start_state.get('w', body.width)), 1e-9), max(float(start_state.get('h', body.height)), 1e-9))
        _lh45_resize_body_geometry(self, new_w=float(body.width), new_h=float(body.height), refresh=True, anchor_bounds=old_bounds)
    except Exception as e:
        try: self.statusBar().showMessage(f'Canvas BODY scale failed: {e}', 4000)
        except Exception: pass


def _lh45_set_safe(self, m, a, v):
    keep_ids = _lh45_selected_model_ids(self) or {id(m)}
    try: self.push_undo_state()
    except Exception: pass
    self._selection_restore_ids = keep_ids
    try:
        if a == 'rotation': v = (round(float(v) / 15.0) * 15.0) % 360
        setattr(m, a, v)
        self.dirty = True
        self.update_current_unit_canvas_positions()
    except Exception as e:
        try: self.statusBar().showMessage(f'Property update failed: {e}', 4000)
        except Exception: pass
    _lh45_deferred_refresh(self, keep_ids)

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._set_body_width_grid = _lh45_set_body_width_grid
        _cls._set_body_height_grid = _lh45_set_body_height_grid
        _cls._transform_unit_as_body_group = _lh45_transform_unit_as_body_group
        _cls.scale_selected_grid = _lh45_scale_selected_grid
        _cls.scale_current_unit_children_from_body_resize = _lh45_scale_current_unit_children_from_body_resize
        _cls._set = _lh45_set_safe
except Exception:
    pass

# --- LH46 robustness patch -------------------------------------------------
# Fixes:
# - Property panel spinbox arrow buttons / combo / checkbox callbacks are guarded
#   against stale Qt widgets and do not synchronously rebuild the panel.
# - Toolbar Scale +/- and property edits restore the exact current selection view
#   instead of switching to a multi-selection message.
# - BODY scaling restores only the BODY selection and never selects pins/body-owned
#   helper graphics as a side effect.

def _lh46_selected_signature(self):
    sig = []
    try:
        for it in self.scene.selectedItems():
            kind = it.data(0)
            model = getattr(it, 'model', None)
            body_model = getattr(it, '_body_model', None)
            sig.append((str(kind), id(model) if model is not None else None, id(body_model) if body_model is not None else None))
    except Exception:
        pass
    return sig


def _lh46_restore_selection_signature(self, sig=None):
    sig = list(sig or getattr(self, '_lh46_selection_signature', []) or [])
    model_ids = {s[1] for s in sig if s[1] is not None}
    body_ids = {s[2] for s in sig if s[2] is not None}
    body_was_selected = any(s[0] in ('BODY', 'BODY_GRAPHIC') for s in sig)
    selected_one_body = False
    try:
        self.scene.blockSignals(True)
        for it in self.scene.items():
            try: it.setSelected(False)
            except Exception: pass
        # BODY can be represented by a generated BODY item or by one body-owned
        # graphic item. Select exactly one visual BODY representative so the
        # property panel stays on "Selected: BODY" and never flips to multi-edit.
        if body_was_selected:
            preferred = None
            for it in self.scene.items():
                try:
                    kind = it.data(0)
                    m = getattr(it, 'model', None)
                    bm = getattr(it, '_body_model', None)
                    if kind == 'BODY' and (id(m) in model_ids or m is getattr(self.current_unit, 'body', None)):
                        preferred = it; break
                    if kind == 'BODY_GRAPHIC' and (id(bm) in body_ids or bm is getattr(self.current_unit, 'body', None)) and preferred is None:
                        preferred = it
                except Exception:
                    pass
            if preferred is not None:
                try: preferred.setSelected(True); selected_one_body = True
                except Exception: pass
        if not selected_one_body:
            for it in self.scene.items():
                try:
                    m = getattr(it, 'model', None)
                    if m is not None and id(m) in model_ids:
                        it.setSelected(True)
                except Exception:
                    pass
    finally:
        try: self.scene.blockSignals(False)
        except Exception: pass
    try: self.view.viewport().update()
    except Exception: pass


def _lh46_deferred_restore_only(self, sig=None):
    sig = list(sig or _lh46_selected_signature(self) or getattr(self, '_lh46_selection_signature', []) or [])
    self._lh46_selection_signature = sig
    def run():
        try: _lh46_restore_selection_signature(self, sig)
        except Exception: pass
    try: QTimer.singleShot(0, run)
    except Exception: run()


def _lh46_dbl(self, value, fn, lo=-999, hi=999, step=.1):
    w = QDoubleSpinBox()
    w.setRange(lo, hi)
    w.setSingleStep(step)
    w.setDecimals(3)
    w.setKeyboardTracking(False)
    try: w.setValue(float(value))
    except Exception: w.setValue(0.0)
    def safe(v):
        try:
            sig = _lh46_selected_signature(self)
            self._lh46_selection_signature = sig
            fn(float(v))
            _lh46_deferred_restore_only(self, sig)
        except RuntimeError:
            pass
        except Exception as e:
            try: self.statusBar().showMessage(f'Property update failed: {e}', 4000)
            except Exception: pass
    w.valueChanged.connect(safe)
    return w


def _lh46_combo(self, items, val, fn):
    w = QComboBox(); w.addItems(items); w.setCurrentText(str(val))
    def safe(v):
        try:
            sig = _lh46_selected_signature(self); self._lh46_selection_signature = sig
            fn(v)
            _lh46_deferred_restore_only(self, sig)
        except RuntimeError:
            pass
        except Exception as e:
            try: self.statusBar().showMessage(f'Property update failed: {e}', 4000)
            except Exception: pass
    w.currentTextChanged.connect(safe)
    return w


def _lh46_check(self, value, fn):
    w = QCheckBox(); w.setChecked(bool(value))
    def safe(v):
        try:
            sig = _lh46_selected_signature(self); self._lh46_selection_signature = sig
            fn(bool(v))
            _lh46_deferred_restore_only(self, sig)
        except RuntimeError:
            pass
        except Exception as e:
            try: self.statusBar().showMessage(f'Property update failed: {e}', 4000)
            except Exception: pass
    w.toggled.connect(safe)
    return w


def _lh46_set_safe(self, m, a, v):
    sig = _lh46_selected_signature(self) or getattr(self, '_lh46_selection_signature', [])
    try: self.push_undo_state()
    except Exception: pass
    try:
        if a == 'rotation': v = (round(float(v) / 15.0) * 15.0) % 360
        setattr(m, a, v)
        self.dirty = True
        try: self.update_current_unit_canvas_positions()
        except Exception: pass
        try: self.schedule_scene_refresh(visual_only=True)
        except Exception:
            try: self.scene.update()
            except Exception: pass
    except Exception as e:
        try: self.statusBar().showMessage(f'Property update failed: {e}', 4000)
        except Exception: pass
    _lh46_deferred_restore_only(self, sig)


def _lh46_resize_body_geometry(self, new_w=None, new_h=None, refresh=True, anchor_bounds=None):
    sig = _lh46_selected_signature(self) or getattr(self, '_lh46_selection_signature', [])
    # Reuse the LH45 geometry implementation, but afterwards force exact BODY
    # selection restore and deliberately avoid rebuilding the property panel.
    r = _lh45_resize_body_geometry(self, new_w=new_w, new_h=new_h, refresh=refresh, anchor_bounds=anchor_bounds)
    _lh46_deferred_restore_only(self, sig)
    return r


def _lh46_transform_unit_as_body_group(self, op, value=None, refresh=True):
    sig = _lh46_selected_signature(self)
    if op in ('scale', 'scale_x_to', 'scale_y_to'):
        b = self.current_unit.body
        cur_w = float(getattr(b, 'width', 1.0) or 1.0); cur_h = float(getattr(b, 'height', 1.0) or 1.0)
        if op == 'scale_x_to': r = _lh46_resize_body_geometry(self, new_w=float(value), new_h=None, refresh=refresh)
        elif op == 'scale_y_to': r = _lh46_resize_body_geometry(self, new_w=None, new_h=float(value), refresh=refresh)
        else:
            f = float(value or 1.0); r = _lh46_resize_body_geometry(self, new_w=cur_w * f, new_h=cur_h * f, refresh=refresh)
        _lh46_deferred_restore_only(self, sig)
        return r
    if _lh44_prev_transform_unit_as_body_group is not None:
        r = _lh44_prev_transform_unit_as_body_group(self, op, value, refresh)
        _lh46_deferred_restore_only(self, sig)
        return r


def _lh46_scale_selected_grid(self, direction: int):
    sig = _lh46_selected_signature(self)
    try: self.set_tool(DrawTool.SELECT.value)
    except Exception: pass
    if self._selected_body_active():
        b = self.current_unit.body; step = _lh44_edit_step(self)
        try: self.push_undo_state()
        except Exception: pass
        r = _lh46_resize_body_geometry(self, float(b.width) + direction * step, float(b.height) + direction * step, refresh=True)
        _lh46_deferred_restore_only(self, sig)
        return r
    try:
        if _lh44_prev_scale_selected_grid is not None:
            r = _lh44_prev_scale_selected_grid(self, direction)
        else:
            r = self.scale_selected(1.0 + (0.1 if direction > 0 else -0.1))
    finally:
        _lh46_deferred_restore_only(self, sig)
    return r


def _lh46_scale_current_unit_children_from_body_resize(self, start_state, body):
    sig = _lh46_selected_signature(self) or getattr(self, '_lh46_selection_signature', [])
    try:
        old_bounds = (float(start_state.get('x', body.x)), float(start_state.get('y', body.y)),
                      max(float(start_state.get('w', body.width)), 1e-9), max(float(start_state.get('h', body.height)), 1e-9))
        return _lh46_resize_body_geometry(self, new_w=float(body.width), new_h=float(body.height), refresh=True, anchor_bounds=old_bounds)
    except Exception as e:
        try: self.statusBar().showMessage(f'Canvas BODY scale failed: {e}', 4000)
        except Exception: pass
    finally:
        _lh46_deferred_restore_only(self, sig)

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._dbl = _lh46_dbl
        _cls._combo = _lh46_combo
        _cls._check = _lh46_check
        _cls._set = _lh46_set_safe
        _cls._transform_unit_as_body_group = _lh46_transform_unit_as_body_group
        _cls.scale_selected_grid = _lh46_scale_selected_grid
        _cls.scale_current_unit_children_from_body_resize = _lh46_scale_current_unit_children_from_body_resize
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v47: keep Selectable/selection/property panel stable and make all
# property widgets crash-safe.
# ---------------------------------------------------------------------------

def _lh47_selection_filter_state(self):
    try:
        mode = self.selection_mode_combo.currentText() if hasattr(self, 'selection_mode_combo') else None
    except Exception:
        mode = None
    try:
        enabled = dict(getattr(self, 'selection_enabled', {}) or {})
    except Exception:
        enabled = {}
    return mode, enabled


def _lh47_restore_selection_filter_state(self, state):
    mode, enabled = state or (None, {})
    try:
        if enabled:
            self.selection_enabled.update(enabled)
    except Exception:
        pass
    try:
        if mode is not None and hasattr(self, 'selection_mode_combo'):
            self.selection_mode_combo.blockSignals(True)
            self.selection_mode_combo.setCurrentText(mode)
            self.selection_mode_combo.blockSignals(False)
    except Exception:
        try: self.selection_mode_combo.blockSignals(False)
        except Exception: pass
    try:
        if mode == 'Custom' and hasattr(self, 'selection_custom_checks'):
            for k, cb in self.selection_custom_checks.items():
                cb.blockSignals(True); cb.setChecked(bool(self.selection_enabled.get(k, False))); cb.blockSignals(False)
        elif hasattr(self, 'selection_custom_checks'):
            for k, cb in self.selection_custom_checks.items():
                cb.blockSignals(True); cb.setChecked(bool(self.selection_enabled.get(k, False))); cb.blockSignals(False)
    except Exception:
        pass


def _lh47_is_body_like_item(it):
    try:
        if it.data(0) in ('BODY', 'BODY_GRAPHIC'):
            return True
        m = getattr(it, 'model', None)
        return bool(m is not None and (getattr(m, 'locked_to_body', False) or str(getattr(m, 'graphic_role', '') or '').lower() in ('body','template_body','imported_body')))
    except Exception:
        return False


def _lh47_select_one_logical_body(self):
    try:
        preferred = None
        fallback = None
        cur_body = getattr(getattr(self, 'current_unit', None), 'body', None)
        for it in list(self.scene.items()):
            try:
                k = it.data(0)
                if k == 'BODY' and (getattr(it, 'model', None) is cur_body or preferred is None):
                    preferred = it
                    if getattr(it, 'model', None) is cur_body:
                        break
                elif k == 'BODY_GRAPHIC' and fallback is None:
                    fallback = it
            except Exception:
                pass
        target = preferred or fallback
        if target is None:
            return False
        self.scene.blockSignals(True)
        try:
            for it in self.scene.items():
                try: it.setSelected(False)
                except Exception: pass
            target.setSelected(True)
        finally:
            self.scene.blockSignals(False)
        try: self.view.viewport().update()
        except Exception: pass
        return True
    except Exception:
        try: self.scene.blockSignals(False)
        except Exception: pass
        return False


def _lh47_restore_selection_after_action(self, sig=None, filter_state=None, force_body=False, refresh=True):
    def run():
        try:
            if filter_state is not None:
                _lh47_restore_selection_filter_state(self, filter_state)
            body_before = force_body or any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in (sig or []))
            if body_before:
                _lh47_select_one_logical_body(self)
            elif sig:
                try:
                    ids = {s[1] for s in sig if len(s) > 1 and s[1] is not None}
                    self.scene.blockSignals(True)
                    for it in self.scene.items():
                        try: it.setSelected(False)
                        except Exception: pass
                    for it in self.scene.items():
                        try:
                            if id(getattr(it, 'model', None)) in ids:
                                it.setSelected(True)
                        except Exception:
                            pass
                finally:
                    try: self.scene.blockSignals(False)
                    except Exception: pass
            if refresh:
                try: self.refresh_properties()
                except Exception: pass
        except Exception as e:
            try: self.statusBar().showMessage(f'Selection restore failed: {e}', 3000)
            except Exception: pass
    try: QTimer.singleShot(0, run)
    except Exception: run()


def _lh47_with_selection_stable(self, work, force_body=False):
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    filter_state = _lh47_selection_filter_state(self)
    try:
        return work()
    finally:
        _lh47_restore_selection_after_action(self, sig=sig, filter_state=filter_state, force_body=force_body)


try:
    _lh47_prev_rotate_selected = MainWindow.rotate_selected
    _lh47_prev_flip_selected_horizontal = MainWindow.flip_selected_horizontal
    _lh47_prev_flip_selected_vertical = MainWindow.flip_selected_vertical
    _lh47_prev_scale_selected_grid = MainWindow.scale_selected_grid
    _lh47_prev_scale_selected = MainWindow.scale_selected
except Exception:
    _lh47_prev_rotate_selected = _lh47_prev_flip_selected_horizontal = _lh47_prev_flip_selected_vertical = None
    _lh47_prev_scale_selected_grid = _lh47_prev_scale_selected = None


def _lh47_rotate_selected(self, deg):
    return _lh47_with_selection_stable(self, lambda: _lh47_prev_rotate_selected(self, deg), force_body=bool(self._selected_body_active()))


def _lh47_flip_selected_horizontal(self):
    return _lh47_with_selection_stable(self, lambda: _lh47_prev_flip_selected_horizontal(self), force_body=bool(self._selected_body_active()))


def _lh47_flip_selected_vertical(self):
    return _lh47_with_selection_stable(self, lambda: _lh47_prev_flip_selected_vertical(self), force_body=bool(self._selected_body_active()))


def _lh47_scale_selected_grid(self, direction:int):
    def work():
        # Pins must never be geometrically scaled. If BODY is part of the current
        # selection, route exclusively through BODY resize/redock. If only pins
        # are selected, Scale +/- is a no-op for them.
        try:
            if self._selected_body_active():
                return _lh47_prev_scale_selected_grid(self, direction)
            selected = list(self.scene.selectedItems())
            if selected and all(getattr(i, 'data', lambda *_: None)(0) == 'PIN' for i in selected):
                try: self.statusBar().showMessage('Pins are not scaled by Scale +/-; edit pin length explicitly.', 2500)
                except Exception: pass
                return None
        except Exception:
            pass
        return _lh47_prev_scale_selected_grid(self, direction)
    return _lh47_with_selection_stable(self, work, force_body=bool(self._selected_body_active()))


def _lh47_scale_selected(self, factor):
    def work():
        try:
            if self._selected_body_active():
                return _lh47_prev_scale_selected(self, factor)
            selected = list(self.scene.selectedItems())
            if selected and all(getattr(i, 'data', lambda *_: None)(0) == 'PIN' for i in selected):
                try: self.statusBar().showMessage('Pins are not scaled; edit pin length explicitly.', 2500)
                except Exception: pass
                return None
        except Exception:
            pass
        return _lh47_prev_scale_selected(self, factor)
    return _lh47_with_selection_stable(self, work, force_body=bool(self._selected_body_active()))


# More conservative property widgets: no synchronous form rebuild from inside
# the editor signal, and no signal during initial value population.
def _lh47_dbl(self, value, fn, lo=-999, hi=999, step=.1):
    w = QDoubleSpinBox()
    w.setRange(lo, hi); w.setSingleStep(step); w.setDecimals(3); w.setKeyboardTracking(False)
    w.blockSignals(True)
    try: w.setValue(float(value))
    except Exception: w.setValue(0.0)
    w.blockSignals(False)
    def safe(v):
        sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
        fs = _lh47_selection_filter_state(self)
        def do():
            try:
                fn(float(v))
            except RuntimeError:
                return
            except Exception as e:
                try: self.statusBar().showMessage(f'Property update failed: {e}', 5000)
                except Exception: pass
            finally:
                _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in sig), refresh=False)
        try: QTimer.singleShot(0, do)
        except Exception: do()
    w.valueChanged.connect(safe)
    return w


def _lh47_combo(self, items, val, fn):
    w = QComboBox(); w.blockSignals(True); w.addItems([str(x) for x in items]); w.setCurrentText(str(val)); w.blockSignals(False)
    def safe(v):
        sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
        fs = _lh47_selection_filter_state(self)
        def do():
            try: fn(v)
            except RuntimeError: return
            except Exception as e:
                try: self.statusBar().showMessage(f'Property update failed: {e}', 5000)
                except Exception: pass
            finally:
                _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in sig), refresh=False)
        try: QTimer.singleShot(0, do)
        except Exception: do()
    w.currentTextChanged.connect(safe)
    return w


def _lh47_check(self, value, fn):
    w = QCheckBox(); w.blockSignals(True); w.setChecked(bool(value)); w.blockSignals(False)
    def safe(v):
        sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
        fs = _lh47_selection_filter_state(self)
        def do():
            try: fn(bool(v))
            except RuntimeError: return
            except Exception as e:
                try: self.statusBar().showMessage(f'Property update failed: {e}', 5000)
                except Exception: pass
            finally:
                _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in sig), refresh=False)
        try: QTimer.singleShot(0, do)
        except Exception: do()
    w.toggled.connect(safe)
    return w


def _lh47_set_safe(self, m, a, v):
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    fs = _lh47_selection_filter_state(self)
    try: self.push_undo_state()
    except Exception: pass
    try:
        if a == 'rotation':
            v = (round(float(v) / 15.0) * 15.0) % 360
        setattr(m, a, v)
        self.dirty = True
        try: self.update_current_unit_canvas_positions()
        except Exception: pass
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.scene.update()
        except Exception: pass
        try: self.view.viewport().update()
        except Exception: pass
    except Exception as e:
        try: self.statusBar().showMessage(f'Property update failed: {e}', 5000)
        except Exception: pass
    _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in sig), refresh=False)


try:
    _lh47_prev_set_attr_vis = MainWindow._set_attr_vis
    _lh47_prev_set_attr_val = MainWindow._set_attr_val
except Exception:
    _lh47_prev_set_attr_vis = _lh47_prev_set_attr_val = None


def _lh47_set_attr_vis(self, key, val):
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    fs = _lh47_selection_filter_state(self)
    try:
        self.push_undo_state()
        self.current_unit.body.visible_attributes[key] = bool(val)
        self.dirty = True
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.scene.update(); self.view.viewport().update()
        except Exception: pass
    except Exception as e:
        try: self.statusBar().showMessage(f'Attribute update failed: {e}', 5000)
        except Exception: pass
    _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in sig), refresh=False)


def _lh47_set_attr_val(self, key, val):
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    fs = _lh47_selection_filter_state(self)
    try:
        self.push_undo_state()
        self.current_unit.body.attributes[key] = str(val)
        self.dirty = True
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.scene.update(); self.view.viewport().update()
        except Exception: pass
    except Exception as e:
        try: self.statusBar().showMessage(f'Attribute update failed: {e}', 5000)
        except Exception: pass
    _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in sig), refresh=False)


try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._dbl = _lh47_dbl
        _cls._combo = _lh47_combo
        _cls._check = _lh47_check
        _cls._set = _lh47_set_safe
        _cls.rotate_selected = _lh47_rotate_selected
        _cls.flip_selected_horizontal = _lh47_flip_selected_horizontal
        _cls.flip_selected_vertical = _lh47_flip_selected_vertical
        _cls.scale_selected_grid = _lh47_scale_selected_grid
        _cls.scale_selected = _lh47_scale_selected
    MainWindow._set_attr_vis = _lh47_set_attr_vis
    MainWindow._set_attr_val = _lh47_set_attr_val
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v48 rebuilt: keep the Selectable view absolutely stable and sync
# the global line controls with the current graphical selection.
# ---------------------------------------------------------------------------

_LH48_MULTIPLE = '<Multiple>'


def _lh48_kind(item):
    try:
        k = item.data(0)
    except Exception:
        k = None
    if k in ('BODY_GRAPHIC',):
        return 'BODY'
    return k


def _lh48_graphical_selected_items(self):
    try:
        items = list(self.scene.selectedItems())
    except Exception:
        return []
    out = []
    for it in items:
        k = _lh48_kind(it)
        if k in ('BODY', 'PIN', 'GRAPHIC') and getattr(it, 'model', None) is not None:
            out.append(it)
    return out


def _lh48_line_value(item, attr):
    m = getattr(item, 'model', None)
    if m is None:
        return None
    k = _lh48_kind(item)
    try:
        if k == 'GRAPHIC':
            st = getattr(m, 'style', None)
            return getattr(st, attr, None)
        return getattr(m, attr, None)
    except Exception:
        return None


def _lh48_common(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None, False
    first = vals[0]
    return first, all(v == first for v in vals)


def _lh48_sync_style_toolbar_to_selection(self):
    """Show common selected line style/width, or <Multiple> on mismatches.

    This is display-only. Signals are blocked so the Selectable mode and the
    selected objects are not changed just because the panel is being updated.
    """
    if not hasattr(self, 'line_style') or not hasattr(self, 'line_width'):
        return
    items = _lh48_graphical_selected_items(self)
    if not items:
        return
    style_val, style_same = _lh48_common([_lh48_line_value(i, 'line_style') for i in items])
    width_val, width_same = _lh48_common([_lh48_line_value(i, 'line_width') for i in items])
    try:
        self.line_style.blockSignals(True)
        idx = self.line_style.findText(_LH48_MULTIPLE)
        if style_same and style_val is not None:
            if idx >= 0:
                self.line_style.removeItem(idx)
            self.line_style.setCurrentText(str(style_val))
        else:
            if idx < 0:
                self.line_style.insertItem(0, _LH48_MULTIPLE)
            self.line_style.setCurrentText(_LH48_MULTIPLE)
    except Exception:
        pass
    finally:
        try: self.line_style.blockSignals(False)
        except Exception: pass
    try:
        self.line_width.blockSignals(True)
        if width_same and width_val is not None:
            self.line_width.setMinimum(0.01)
            self.line_width.setSpecialValueText('')
            self.line_width.setValue(float(width_val))
        else:
            self.line_width.setMinimum(0.0)
            self.line_width.setSpecialValueText(_LH48_MULTIPLE)
            self.line_width.setValue(0.0)
    except Exception:
        pass
    finally:
        try: self.line_width.blockSignals(False)
        except Exception: pass


try:
    _lh48_prev_on_scene_selection_changed = MainWindow.on_scene_selection_changed
except Exception:
    _lh48_prev_on_scene_selection_changed = None


def _lh48_on_scene_selection_changed(self):
    mode_state = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    try:
        if _lh48_prev_on_scene_selection_changed is not None:
            _lh48_prev_on_scene_selection_changed(self)
        else:
            self.refresh_properties()
    except Exception as e:
        try: self.statusBar().showMessage(f'Selection update failed: {e}', 4000)
        except Exception: pass
    finally:
        if mode_state is not None and '_lh47_restore_selection_filter_state' in globals():
            _lh47_restore_selection_filter_state(self, mode_state)
        _lh48_sync_style_toolbar_to_selection(self)


try:
    _lh48_prev_apply_line_defaults = MainWindow.apply_line_defaults
except Exception:
    _lh48_prev_apply_line_defaults = None


def _lh48_apply_line_defaults(self):
    # The placeholder is not a real line style. It appears only when selected
    # objects have different values. Ignore it until the user chooses a real one.
    try:
        if hasattr(self, 'line_style') and self.line_style.currentText() == _LH48_MULTIPLE:
            return
        if hasattr(self, 'line_width') and float(self.line_width.value()) <= 0.0:
            return
    except Exception:
        return
    mode_state = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    try:
        if _lh48_prev_apply_line_defaults is not None:
            return _lh48_prev_apply_line_defaults(self)
    except Exception as e:
        try: self.statusBar().showMessage(f'Line style update failed: {e}', 5000)
        except Exception: pass
    finally:
        if mode_state is not None and '_lh47_restore_selection_filter_state' in globals():
            _lh47_restore_selection_filter_state(self, mode_state)
        if '_lh47_restore_selection_after_action' in globals():
            _lh47_restore_selection_after_action(self, sig=sig, filter_state=mode_state, force_body=any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in sig), refresh=False)
        try: QTimer.singleShot(0, lambda: _lh48_sync_style_toolbar_to_selection(self))
        except Exception: pass


try:
    _lh48_prev_set_attr_vis = MainWindow._set_attr_vis
    _lh48_prev_set_attr_val = MainWindow._set_attr_val
except Exception:
    _lh48_prev_set_attr_vis = _lh48_prev_set_attr_val = None


def _lh48_set_attr_vis(self, key, val):
    mode_state = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    try:
        self.push_undo_state()
        self.current_unit.body.visible_attributes[key] = bool(val)
        self.dirty = True
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.scene.update(); self.view.viewport().update()
        except Exception: pass
    except Exception as e:
        try: self.statusBar().showMessage(f'Attribute update failed: {e}', 5000)
        except Exception: pass
    finally:
        if mode_state is not None and '_lh47_restore_selection_filter_state' in globals():
            _lh47_restore_selection_filter_state(self, mode_state)
        if '_lh47_restore_selection_after_action' in globals():
            _lh47_restore_selection_after_action(self, sig=sig, filter_state=mode_state, force_body=any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in sig), refresh=False)


def _lh48_set_attr_val(self, key, val):
    mode_state = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    try:
        self.push_undo_state()
        self.current_unit.body.attributes[key] = str(val)
        self.dirty = True
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.scene.update(); self.view.viewport().update()
        except Exception: pass
    except Exception as e:
        try: self.statusBar().showMessage(f'Attribute update failed: {e}', 5000)
        except Exception: pass
    finally:
        if mode_state is not None and '_lh47_restore_selection_filter_state' in globals():
            _lh47_restore_selection_filter_state(self, mode_state)
        if '_lh47_restore_selection_after_action' in globals():
            _lh47_restore_selection_after_action(self, sig=sig, filter_state=mode_state, force_body=any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in sig), refresh=False)


try:
    MainWindow.on_scene_selection_changed = _lh48_on_scene_selection_changed
    MainWindow.apply_line_defaults = _lh48_apply_line_defaults
    MainWindow._set_attr_vis = _lh48_set_attr_vis
    MainWindow._set_attr_val = _lh48_set_attr_val
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v50: BODY property edits must never leave the BODY selection view.
# ---------------------------------------------------------------------------

def _lh50_property_panel_kind(self):
    """Return the currently displayed property panel kind, e.g. BODY.

    This is deliberately independent from the live scene selection because some
    body-attribute updates temporarily recreate ATTR_* items and Qt can emit a
    transient multi-selection.  The user's visible context is the authoritative
    context for property widget callbacks.
    """
    try:
        if not hasattr(self, 'form') or self.form is None or self.form.rowCount() <= 0:
            return None
        item = self.form.itemAt(0, QFormLayout.LabelRole) or self.form.itemAt(0, QFormLayout.FieldRole)
        w = item.widget() if item is not None else None
        txt = w.text() if hasattr(w, 'text') else ''
        if isinstance(txt, str) and txt.startswith('Selected:'):
            return txt.split(':', 1)[1].strip().upper()
    except Exception:
        pass
    return getattr(self, '_lh50_last_property_kind', None)

try:
    _lh50_prev_refresh_properties = MainWindow.refresh_properties
except Exception:
    _lh50_prev_refresh_properties = None

def _lh50_refresh_properties(self):
    r = None
    if _lh50_prev_refresh_properties is not None:
        r = _lh50_prev_refresh_properties(self)
    try:
        k = _lh50_property_panel_kind(self)
        if k:
            self._lh50_last_property_kind = k
    except Exception:
        pass
    return r


def _lh50_body_context(self, sig=None):
    try:
        if str(_lh50_property_panel_kind(self) or '').upper() == 'BODY':
            return True
    except Exception:
        pass
    try:
        return any(str(s[0]) in ('BODY', 'BODY_GRAPHIC') for s in (sig or []))
    except Exception:
        return False


def _lh50_restore_body_or_signature(self, sig=None, fs=None, refresh_panel=True):
    force_body = _lh50_body_context(self, sig)
    def run():
        try:
            if fs is not None and '_lh47_restore_selection_filter_state' in globals():
                _lh47_restore_selection_filter_state(self, fs)
            if force_body and '_lh47_select_one_logical_body' in globals():
                _lh47_select_one_logical_body(self)
            elif sig and '_lh46_restore_selection_signature' in globals():
                _lh46_restore_selection_signature(self, sig)
            if refresh_panel:
                try: _lh50_refresh_properties(self)
                except Exception: pass
            try:
                if '_lh48_sync_style_toolbar_to_selection' in globals():
                    _lh48_sync_style_toolbar_to_selection(self)
            except Exception:
                pass
        except Exception as e:
            try: self.statusBar().showMessage(f'Selection restore failed: {e}', 4000)
            except Exception: pass
    try: QTimer.singleShot(0, run)
    except Exception: run()

# Capture the BODY view before a property widget can trigger transient scene changes.
def _lh50_dbl(self, value, fn, lo=-999, hi=999, step=.1):
    w = QDoubleSpinBox(); w.setRange(lo, hi); w.setSingleStep(step); w.setDecimals(3); w.setKeyboardTracking(False)
    try:
        w.blockSignals(True); w.setValue(float(value)); w.blockSignals(False)
    except Exception:
        try: w.blockSignals(True); w.setValue(0.0); w.blockSignals(False)
        except Exception: pass
    def safe(v):
        sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
        fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
        body_ctx = _lh50_body_context(self, sig)
        def do():
            try: fn(float(v))
            except RuntimeError: return
            except Exception as e:
                try: self.statusBar().showMessage(f'Property update failed: {e}', 5000)
                except Exception: pass
            finally:
                if body_ctx: self._lh50_last_property_kind = 'BODY'
                _lh50_restore_body_or_signature(self, sig=sig, fs=fs, refresh_panel=True)
        try: QTimer.singleShot(0, do)
        except Exception: do()
    w.valueChanged.connect(safe)
    return w


def _lh50_combo(self, items, val, fn):
    w = QComboBox(); w.blockSignals(True); w.addItems([str(x) for x in items]); w.setCurrentText(str(val)); w.blockSignals(False)
    def safe(v):
        # Ignore display-only mismatch marker.
        if str(v) == globals().get('_LH48_MULTIPLE', '<Multiple>'):
            return
        sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
        fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
        body_ctx = _lh50_body_context(self, sig)
        def do():
            try: fn(v)
            except RuntimeError: return
            except Exception as e:
                try: self.statusBar().showMessage(f'Property update failed: {e}', 5000)
                except Exception: pass
            finally:
                if body_ctx: self._lh50_last_property_kind = 'BODY'
                _lh50_restore_body_or_signature(self, sig=sig, fs=fs, refresh_panel=True)
        try: QTimer.singleShot(0, do)
        except Exception: do()
    w.currentTextChanged.connect(safe)
    return w


def _lh50_check(self, value, fn):
    w = QCheckBox(); w.blockSignals(True); w.setChecked(bool(value)); w.blockSignals(False)
    def safe(v):
        sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
        fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
        body_ctx = _lh50_body_context(self, sig)
        def do():
            try: fn(bool(v))
            except RuntimeError: return
            except Exception as e:
                try: self.statusBar().showMessage(f'Property update failed: {e}', 5000)
                except Exception: pass
            finally:
                if body_ctx: self._lh50_last_property_kind = 'BODY'
                _lh50_restore_body_or_signature(self, sig=sig, fs=fs, refresh_panel=True)
        try: QTimer.singleShot(0, do)
        except Exception: do()
    w.toggled.connect(safe)
    return w


def _lh50_set_safe(self, m, a, v):
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    body_ctx = _lh50_body_context(self, sig)
    try: self.push_undo_state()
    except Exception: pass
    try:
        if a == 'rotation': v = (round(float(v) / 15.0) * 15.0) % 360
        setattr(m, a, v); self.dirty = True
        try: self.update_current_unit_canvas_positions()
        except Exception: pass
        try: self.scene.update(); self.view.viewport().update()
        except Exception: pass
    except Exception as e:
        try: self.statusBar().showMessage(f'Property update failed: {e}', 5000)
        except Exception: pass
    if body_ctx: self._lh50_last_property_kind = 'BODY'
    _lh50_restore_body_or_signature(self, sig=sig, fs=fs, refresh_panel=True)


def _lh50_set_attr_vis(self, key, val):
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    body_ctx = _lh50_body_context(self, sig)
    try:
        try: self.scene.blockSignals(True)
        except Exception: pass
        self.push_undo_state()
        self.current_unit.body.visible_attributes[key] = bool(val)
        self.dirty = True
        try: self.update_attribute_items_for_unit()
        except Exception: pass
    except Exception as e:
        try: self.statusBar().showMessage(f'Attribute update failed: {e}', 5000)
        except Exception: pass
    finally:
        try: self.scene.blockSignals(False)
        except Exception: pass
        if body_ctx: self._lh50_last_property_kind = 'BODY'
        _lh50_restore_body_or_signature(self, sig=sig, fs=fs, refresh_panel=True)


def _lh50_set_attr_val(self, key, val):
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    body_ctx = _lh50_body_context(self, sig)
    try:
        try: self.scene.blockSignals(True)
        except Exception: pass
        self.push_undo_state()
        self.current_unit.body.attributes[key] = str(val)
        self.dirty = True
        try: self.update_attribute_items_for_unit()
        except Exception: pass
    except Exception as e:
        try: self.statusBar().showMessage(f'Attribute update failed: {e}', 5000)
        except Exception: pass
    finally:
        try: self.scene.blockSignals(False)
        except Exception: pass
        if body_ctx: self._lh50_last_property_kind = 'BODY'
        _lh50_restore_body_or_signature(self, sig=sig, fs=fs, refresh_panel=True)

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.refresh_properties = _lh50_refresh_properties
        _cls._dbl = _lh50_dbl
        _cls._combo = _lh50_combo
        _cls._check = _lh50_check
        _cls._set = _lh50_set_safe
    MainWindow._set_attr_vis = _lh50_set_attr_vis
    MainWindow._set_attr_val = _lh50_set_attr_val
except Exception:
    pass


# ---------------------------------------------------------------------------
# Liebherr v51: BODY-owned highlight graphics are paint-only; BODY rotation is
# a 0/90/180/270 dropdown and stays synced with CW/CCW.
# ---------------------------------------------------------------------------

def _lh51_select_one_logical_body(self):
    """Select exactly the real logical BodyItem, never BODY_GRAPHIC artwork."""
    try:
        cur_body = getattr(getattr(self, 'current_unit', None), 'body', None)
        target = None
        for it in list(self.scene.items()):
            try:
                if it.data(0) == 'BODY' and (getattr(it, 'model', None) is cur_body or target is None):
                    target = it
                    if getattr(it, 'model', None) is cur_body:
                        break
            except Exception:
                pass
        if target is None:
            return False
        self.scene.blockSignals(True)
        try:
            for it in self.scene.items():
                try: it.setSelected(False)
                except Exception: pass
            target.setSelected(True)
        finally:
            self.scene.blockSignals(False)
        try: self.scene.update(); self.view.viewport().update()
        except Exception: pass
        return True
    except Exception:
        try: self.scene.blockSignals(False)
        except Exception: pass
        return False


def _lh51_body_rotation_combo(self, body):
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
        sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
        fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
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
                try: self._lh50_last_property_kind = 'BODY'
                except Exception: pass
                if '_lh50_restore_body_or_signature' in globals():
                    _lh50_restore_body_or_signature(self, sig=sig, fs=fs, refresh_panel=True)
                elif '_lh47_restore_selection_after_action' in globals():
                    _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=True, refresh=True)
        try: QTimer.singleShot(0, do)
        except Exception: do()
    w.currentTextChanged.connect(safe)
    return w


def _lh51_transform_props(self, m):
    try:
        if m is getattr(getattr(self, 'current_unit', None), 'body', None):
            self.form.addRow('Rotation [deg]', _lh51_body_rotation_combo(self, m))
            return
    except Exception:
        pass
    # non-BODY fallback stays as before
    self.form.addRow('Rotation [deg]', self._dbl(getattr(m, 'rotation', 0), lambda v, model=m: self.set_and_refresh(model, 'rotation', v), -360, 360, 15))

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.transform_props = _lh51_transform_props
    # Override previous helper so all restore paths avoid BODY_GRAPHIC selection.
    globals()['_lh47_select_one_logical_body'] = _lh51_select_one_logical_body
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v52: synchronize toolbar CW/CCW BODY rotation with BODY property
# dropdown (0/90/180/270).  The geometric transform stays untouched; only the
# logical BODY rotation attribute is updated after toolbar rotation so the
# property panel reflects the actual last 90° operation.
# ---------------------------------------------------------------------------
try:
    _lh52_prev_rotate_selected = MainWindow.rotate_selected
except Exception:
    _lh52_prev_rotate_selected = None


def _lh52_body_selected_for_rotation(self):
    try:
        return bool(self._selected_body_active())
    except Exception:
        try:
            return any(getattr(i, 'data', lambda *_: None)(0) == 'BODY' for i in self.scene.selectedItems())
        except Exception:
            return False


def _lh52_sync_body_rotation_after_toolbar(self, deg, before_rotation):
    try:
        body = getattr(getattr(self, 'current_unit', None), 'body', None)
        if body is None:
            return
        # Keep the UI representation constrained to the four valid values.
        # Toolbar buttons are 90° steps; non-90 values are snapped defensively.
        step = int(round(float(deg or 0.0) / 90.0)) * 90
        before = int(round(float(before_rotation or 0.0) / 90.0)) * 90
        body.rotation = float((before + step) % 360)
        try: self._lh50_last_property_kind = 'BODY'
        except Exception: pass
    except Exception:
        pass


def _lh52_rotate_selected(self, deg):
    body_active = _lh52_body_selected_for_rotation(self)
    body = getattr(getattr(self, 'current_unit', None), 'body', None)
    try:
        before = float(getattr(body, 'rotation', 0.0) or 0.0) if (body_active and body is not None) else None
    except Exception:
        before = 0.0
    result = None
    if _lh52_prev_rotate_selected is not None:
        result = _lh52_prev_rotate_selected(self, deg)
    if body_active:
        _lh52_sync_body_rotation_after_toolbar(self, deg, before)
        try: self.dirty = True
        except Exception: pass
        # Rebuild the property panel asynchronously so the dropdown shows the
        # new value, while preserving the BODY selection/filter state.
        try:
            sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
            fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
            if '_lh50_restore_body_or_signature' in globals():
                QTimer.singleShot(0, lambda: _lh50_restore_body_or_signature(self, sig=sig, fs=fs, refresh_panel=True))
            elif '_lh47_restore_selection_after_action' in globals():
                QTimer.singleShot(0, lambda: _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=True, refresh=True))
            else:
                QTimer.singleShot(0, self.refresh_properties)
        except Exception:
            try: self.refresh_properties()
            except Exception: pass
    return result

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.rotate_selected = _lh52_rotate_selected
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v53: Scale +/- for inserted/free GRAPHIC objects.
# Previous fallback looked for a non-existent scale_by() method, therefore
# pasted/drawn graphics did not react to the toolbar.  Scale regular GRAPHIC
# models directly around their own center, snap endpoints to the edit grid and
# keep BODY/pin protection plus selection restoration intact.
# ---------------------------------------------------------------------------
try:
    _lh53_prev_scale_selected_grid = MainWindow.scale_selected_grid
    _lh53_prev_scale_selected = MainWindow.scale_selected
except Exception:
    _lh53_prev_scale_selected_grid = None
    _lh53_prev_scale_selected = None


def _lh53_edit_step(self):
    try:
        return max(float(self._edit_grid_step()), 1e-9)
    except Exception:
        try:
            return max(float(getattr(self, 'edit_grid_px', 0.0) or 0.0) / max(float(getattr(self, 'grid_px', 1.0) or 1.0), 1e-9), 1e-9)
        except Exception:
            return 0.1


def _lh53_snap(self, v):
    try:
        return float(self._snap_to_edit_grid(float(v), _lh53_edit_step(self)))
    except Exception:
        try:
            step = _lh53_edit_step(self)
            return round(float(v) / step) * step
        except Exception:
            return float(v)


def _lh53_graphic_points(gr):
    try:
        return _lh10_graphic_points(gr)
    except Exception:
        x = float(getattr(gr, 'x', 0.0) or 0.0)
        y = float(getattr(gr, 'y', 0.0) or 0.0)
        w = float(getattr(gr, 'w', 0.0) or 0.0)
        h = float(getattr(gr, 'h', 0.0) or 0.0)
        return (x, y, x + w, y - h)


def _lh53_scale_graphic_model(self, gr, factor):
    x1, y1, x2, y2 = _lh53_graphic_points(gr)
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    f = max(0.05, float(factor))
    nx1 = _lh53_snap(self, cx + (x1 - cx) * f)
    ny1 = _lh53_snap(self, cy + (y1 - cy) * f)
    nx2 = _lh53_snap(self, cx + (x2 - cx) * f)
    ny2 = _lh53_snap(self, cy + (y2 - cy) * f)
    # Avoid collapsing non-zero geometry after snapping.
    step = _lh53_edit_step(self)
    if abs(x2 - x1) > 1e-12 and abs(nx2 - nx1) < step:
        nx1, nx2 = _lh53_snap(self, cx - step / 2.0), _lh53_snap(self, cx + step / 2.0)
    if abs(y2 - y1) > 1e-12 and abs(ny2 - ny1) < step:
        ny1, ny2 = _lh53_snap(self, cy - step / 2.0), _lh53_snap(self, cy + step / 2.0)
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


def _lh53_selected_items(self):
    try:
        return [i for i in self.scene.selectedItems() if getattr(i, 'data', lambda *_: None)(0) not in ('SELECTION_HANDLE', 'HIGHLIGHT')]
    except Exception:
        return []


def _lh53_has_regular_graphics(self, items):
    for it in items:
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None and not bool(getattr(it.model, 'locked_to_body', False)):
                return True
        except Exception:
            pass
    return False


def _lh53_apply_scale_to_non_body_selection(self, factor):
    changed = False
    for it in _lh53_selected_items(self):
        try:
            kind = it.data(0)
            if kind == 'GRAPHIC' and getattr(it, 'model', None) is not None and not bool(getattr(it.model, 'locked_to_body', False)):
                _lh53_scale_graphic_model(self, it.model, factor)
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


def _lh53_scale_selected(self, factor):
    try:
        if self._selected_body_active():
            return _lh53_prev_scale_selected(self, factor) if _lh53_prev_scale_selected else None
    except Exception:
        pass
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    try:
        self.set_tool(DrawTool.SELECT.value)
        self.push_undo_state()
        changed = _lh53_apply_scale_to_non_body_selection(self, float(factor))
        if not changed and _lh53_prev_scale_selected is not None:
            return _lh53_prev_scale_selected(self, factor)
        self.dirty = bool(changed) or getattr(self, 'dirty', False)
    finally:
        try:
            _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=False, refresh=False)
        except Exception:
            pass


def _lh53_scale_selected_grid(self, direction:int):
    try:
        if self._selected_body_active():
            return _lh53_prev_scale_selected_grid(self, direction) if _lh53_prev_scale_selected_grid else None
    except Exception:
        pass
    items = _lh53_selected_items(self)
    # Regular inserted/drawn graphics get a real geometry scale. Pins stay excluded.
    if _lh53_has_regular_graphics(self, items) or any(getattr(i, 'data', lambda *_: None)(0) in ('TEXT','ATTR_REF_DES','ATTR_BODY') for i in items):
        return _lh53_scale_selected(self, 1.0 + (0.1 if int(direction) > 0 else -0.1))
    if _lh53_prev_scale_selected_grid is not None:
        return _lh53_prev_scale_selected_grid(self, direction)

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.scale_selected = _lh53_scale_selected
        _cls.scale_selected_grid = _lh53_scale_selected_grid
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v55: robust proportional grid scaling for GRAPHIC selections plus
# lightweight graphic grouping.
# ---------------------------------------------------------------------------
# Rules:
# - Scale +/- on GRAPHIC selections changes geometry proportionally around the
#   selected graphic/group center.
# - One toolbar step equals one current edit-grid increment on the dominant
#   dimension; the minimum rendered dominant dimension is one edit-grid step.
# - Pins are never included.
# - BODY selections keep using the proven Symbol-1 BODY transform path.  Imported
#   and template BODY artwork is treated as BODY artwork and therefore follows
#   the same canvas scaling method.
# - A graphic group is a shared group id on user graphics. Selecting/scaling one
#   member scales the whole group as one logical object. Ungroup clears that id.

try:
    _lh55_prev_scale_selected_grid = MainWindow.scale_selected_grid
    _lh55_prev_scale_selected = MainWindow.scale_selected
except Exception:
    _lh55_prev_scale_selected_grid = None
    _lh55_prev_scale_selected = None


def _lh55_step(self):
    try:
        return max(float(self._edit_grid_step()), 1e-9)
    except Exception:
        try:
            txt = str(getattr(self, 'edit_grid_combo', None).currentText()).replace('"','').strip()
            return max(float(txt), 1e-9)
        except Exception:
            return 0.1


def _lh55_snap(self, v):
    try:
        return float(self._snap_to_edit_grid(float(v), _lh55_step(self)))
    except Exception:
        st = _lh55_step(self)
        try: return round(float(v) / st) * st
        except Exception: return float(v)


def _lh55_selected_real_items(self):
    out = []
    for it in list(getattr(self, 'scene', None).selectedItems() if getattr(self, 'scene', None) else []):
        try:
            k = it.data(0)
            if k in ('SELECTION_HANDLE', 'HIGHLIGHT', 'BODY_GRAPHIC'):
                continue
            out.append(it)
        except Exception:
            pass
    return out


def _lh55_is_user_graphic(self, gr):
    try:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body','template_body','imported_body')
    except Exception:
        return False


def _lh55_graphic_group_id(gr):
    try:
        gid = getattr(gr, 'group_id', '') or ''
    except Exception:
        gid = ''
    if not gid:
        try:
            role = str(getattr(gr, 'graphic_role', '') or '')
            if role.startswith('user_graphic_group:'):
                gid = role.split(':', 1)[1]
        except Exception:
            pass
    return str(gid or '')


def _lh55_set_graphic_group_id(gr, gid):
    try: setattr(gr, 'group_id', str(gid or ''))
    except Exception: pass
    try:
        gr.graphic_role = ('user_graphic_group:' + str(gid)) if gid else 'user_graphic'
    except Exception: pass


def _lh55_graphic_models_from_selection(self):
    selected = []
    gids = set()
    for it in _lh55_selected_real_items(self):
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None and _lh55_is_user_graphic(self, it.model):
                selected.append(it.model)
                gid = _lh55_graphic_group_id(it.model)
                if gid:
                    gids.add(gid)
        except Exception:
            pass
    if not selected:
        return []
    models = []
    for gr in list(getattr(getattr(self, 'current_unit', None), 'graphics', []) or []):
        try:
            if not _lh55_is_user_graphic(self, gr):
                continue
            if gr in selected or (_lh55_graphic_group_id(gr) and _lh55_graphic_group_id(gr) in gids):
                if gr not in models:
                    models.append(gr)
        except Exception:
            pass
    return models


def _lh55_graphic_endpoints(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    return x, y, x + w, y - h


def _lh55_model_points(gr):
    x1, y1, x2, y2 = _lh55_graphic_endpoints(gr)
    shape = str(getattr(gr, 'shape', '') or '').lower()
    pts = [(x1, y1), (x2, y2)]
    if shape not in ('line','arc'):
        pts += [(x1, y2), (x2, y1)]
    try:
        if getattr(gr, 'ctrl_x', None) is not None and getattr(gr, 'ctrl_y', None) is not None:
            pts.append((x1 + float(gr.ctrl_x), y1 - float(gr.ctrl_y)))
    except Exception:
        pass
    return pts


def _lh55_graphics_bounds(graphics):
    pts = []
    for gr in graphics:
        pts.extend(_lh55_model_points(gr))
    if not pts:
        return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _lh55_scale_point(self, px, py, cx, cy, factor):
    return _lh55_snap(self, cx + (float(px) - cx) * factor), _lh55_snap(self, cy + (float(py) - cy) * factor)


def _lh55_scale_graphics_by_grid_step(self, direction):
    graphics = _lh55_graphic_models_from_selection(self)
    if not graphics:
        return False
    b = _lh55_graphics_bounds(graphics)
    if not b:
        return False
    minx, miny, maxx, maxy = b
    st = _lh55_step(self)
    cur_w = abs(maxx - minx)
    cur_h = abs(maxy - miny)
    dominant = max(cur_w, cur_h, st)
    new_dom = max(st, dominant + (st if int(direction) > 0 else -st))
    factor = new_dom / dominant if dominant > 1e-12 else 1.0
    if abs(factor - 1.0) < 1e-12:
        return False
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    try: self.push_undo_state()
    except Exception: pass
    for gr in graphics:
        x1, y1, x2, y2 = _lh55_graphic_endpoints(gr)
        nx1, ny1 = _lh55_scale_point(self, x1, y1, cx, cy, factor)
        nx2, ny2 = _lh55_scale_point(self, x2, y2, cx, cy, factor)
        # Prevent collapse after snapping.  Preserve direction signs as far as possible.
        if abs(x2 - x1) > 1e-12 and abs(nx2 - nx1) < st:
            sgn = 1.0 if (x2 - x1) >= 0 else -1.0
            nx1 = _lh55_snap(self, (nx1 + nx2) / 2.0 - sgn * st / 2.0)
            nx2 = _lh55_snap(self, (nx1 + nx2) / 2.0 + sgn * st / 2.0)
        if abs(y2 - y1) > 1e-12 and abs(ny2 - ny1) < st:
            sgn = 1.0 if (y2 - y1) >= 0 else -1.0
            ny1 = _lh55_snap(self, (ny1 + ny2) / 2.0 - sgn * st / 2.0)
            ny2 = _lh55_snap(self, (ny1 + ny2) / 2.0 + sgn * st / 2.0)
        # Control point is absolute during transformation, then stored relative
        # to the new start point using the model's y-down h/ctrl_y convention.
        cabs = None
        try:
            if getattr(gr, 'ctrl_x', None) is not None and getattr(gr, 'ctrl_y', None) is not None:
                cabs = (x1 + float(gr.ctrl_x), y1 - float(gr.ctrl_y))
        except Exception:
            cabs = None
        gr.x = nx1
        gr.y = ny1
        gr.w = nx2 - nx1
        gr.h = ny1 - ny2
        if cabs is not None:
            ncx, ncy = _lh55_scale_point(self, cabs[0], cabs[1], cx, cy, factor)
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
        try: self.schedule_scene_refresh()
        except Exception: pass
    try: self.refresh_properties()
    except Exception: pass
    try: self.view.viewport().update()
    except Exception: pass
    return True


def _lh55_scale_selected_grid(self, direction:int):
    try:
        if self._selected_body_active():
            return _lh55_prev_scale_selected_grid(self, direction) if _lh55_prev_scale_selected_grid else None
    except Exception:
        pass
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    try:
        if _lh55_scale_graphics_by_grid_step(self, direction):
            return None
        if _lh55_prev_scale_selected_grid is not None:
            return _lh55_prev_scale_selected_grid(self, direction)
    finally:
        try: _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=False, refresh=False)
        except Exception: pass


def _lh55_scale_selected(self, factor):
    # Keep direct/legacy callers safe: convert relative factor to one grid step
    # direction for GRAPHIC selections. BODY path remains untouched.
    try:
        if self._selected_body_active():
            return _lh55_prev_scale_selected(self, factor) if _lh55_prev_scale_selected else None
    except Exception:
        pass
    return _lh55_scale_selected_grid(self, 1 if float(factor) >= 1.0 else -1)


def _lh55_group_selected_graphics(self):
    models = []
    for it in _lh55_selected_real_items(self):
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None and _lh55_is_user_graphic(self, it.model):
                if it.model not in models:
                    models.append(it.model)
        except Exception:
            pass
    if len(models) < 2:
        try: self.statusBar().showMessage('Bitte mindestens zwei Grafikobjekte zum Gruppieren auswählen.', 3500)
        except Exception: pass
        return
    try: self.push_undo_state()
    except Exception: pass
    import uuid as _lh55_uuid
    gid = 'G' + _lh55_uuid.uuid4().hex[:8]
    for gr in models:
        _lh55_set_graphic_group_id(gr, gid)
    try: self.dirty = True; self.refresh_properties(); self.rebuild_tree()
    except Exception: pass
    try: self.statusBar().showMessage(f'Grafikgruppe erstellt ({len(models)} Objekte).', 3500)
    except Exception: pass


def _lh55_ungroup_selected_graphics(self):
    models = _lh55_graphic_models_from_selection(self)
    if not models:
        return
    try: self.push_undo_state()
    except Exception: pass
    for gr in models:
        _lh55_set_graphic_group_id(gr, '')
    try: self.dirty = True; self.refresh_properties(); self.rebuild_tree()
    except Exception: pass
    try: self.statusBar().showMessage('Grafikgruppe aufgehoben.', 3500)
    except Exception: pass

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.scale_selected = _lh55_scale_selected
        _cls.scale_selected_grid = _lh55_scale_selected_grid
    MainWindow.group_selected_graphics = _lh55_group_selected_graphics
    MainWindow.ungroup_selected_graphics = _lh55_ungroup_selected_graphics
except Exception:
    pass

# Add Group/Ungroup buttons to the Transform toolbar without touching the
# existing toolbar construction semantics.
try:
    _lh55_prev_toolbar = MainWindow._toolbar
    def _lh55_toolbar(self):
        _lh55_prev_toolbar(self)
        try:
            tb = self.addToolBar('Graphic Group')
            b = QPushButton('Group Graphics'); b.clicked.connect(self.group_selected_graphics); tb.addWidget(b)
            b = QPushButton('Ungroup'); b.clicked.connect(self.ungroup_selected_graphics); tb.addWidget(b)
        except Exception:
            pass
    MainWindow._toolbar = _lh55_toolbar
except Exception:
    pass


# ---------------------------------------------------------------------------
# Liebherr v56: corrected GRAPHIC scale/group behavior.
# ---------------------------------------------------------------------------
# Fixes after v55:
# - Scale + on a 3x3 graphic rectangle becomes 4x4 at the same center.
# - Scale - is proportional, grid-snapped, and never collapses below one edit-grid.
# - Graphic groups are accessible from Edit menu and shortcuts in addition to the
#   toolbar, and group ids are persisted on GraphicModel.group_id.
# - Selecting one member of a group makes Scale/Move operate on the complete group.

try:
    _lh56_prev_scale_selected_grid = MainWindow.scale_selected_grid
    _lh56_prev_scale_selected = MainWindow.scale_selected
except Exception:
    _lh56_prev_scale_selected_grid = None
    _lh56_prev_scale_selected = None


def _lh56_step(self):
    try:
        return max(float(self._edit_grid_step()), 1e-9)
    except Exception:
        return 0.1


def _lh56_increment(self):
    # The UI properties are expressed in grid units. For toolbar Scale +/- the
    # expected interaction is one grid unit per click (3x3 -> 4x4), while the
    # resulting coordinates are still snapped to the active edit grid.
    try:
        return max(1.0, _lh56_step(self))
    except Exception:
        return 1.0


def _lh56_snap(self, v):
    st = _lh56_step(self)
    try:
        return float(self._snap_to_edit_grid(float(v), st))
    except Exception:
        try:
            return round(float(v) / st) * st
        except Exception:
            return float(v)


def _lh56_selected_real_items(self):
    items = []
    try:
        raw = list(self.scene.selectedItems())
    except Exception:
        raw = []
    for it in raw:
        try:
            if it.data(0) in ('SELECTION_HANDLE', 'HIGHLIGHT', 'BODY_GRAPHIC'):
                continue
            items.append(it)
        except Exception:
            pass
    return items


def _lh56_is_user_graphic(gr):
    try:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body','template_body','imported_body')
    except Exception:
        return False


def _lh56_gid(gr):
    try:
        gid = str(getattr(gr, 'group_id', '') or '')
        if gid:
            return gid
        role = str(getattr(gr, 'graphic_role', '') or '')
        if role.startswith('user_graphic_group:'):
            return role.split(':', 1)[1]
    except Exception:
        pass
    return ''


def _lh56_set_gid(gr, gid):
    gid = str(gid or '')
    try:
        gr.group_id = gid
    except Exception:
        pass
    try:
        gr.graphic_role = ('user_graphic_group:' + gid) if gid else 'user_graphic'
    except Exception:
        pass


def _lh56_selected_graphic_models(self, expand_groups=True):
    selected = []
    gids = set()
    for it in _lh56_selected_real_items(self):
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None and _lh56_is_user_graphic(it.model):
                selected.append(it.model)
                gid = _lh56_gid(it.model)
                if gid:
                    gids.add(gid)
        except Exception:
            pass
    if not selected:
        return []
    if not expand_groups:
        return selected
    out = []
    try:
        graphics = list(getattr(self.current_unit, 'graphics', []) or [])
    except Exception:
        graphics = []
    for gr in graphics:
        try:
            if not _lh56_is_user_graphic(gr):
                continue
            if gr in selected or (_lh56_gid(gr) and _lh56_gid(gr) in gids):
                if gr not in out:
                    out.append(gr)
        except Exception:
            pass
    return out


def _lh56_points(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    x2 = x + w
    y2 = y - h
    pts = [(x, y), (x2, y2)]
    if str(getattr(gr, 'shape', '') or '').lower() not in ('line', 'arc'):
        pts.extend([(x, y2), (x2, y)])
    try:
        if getattr(gr, 'ctrl_x', None) is not None and getattr(gr, 'ctrl_y', None) is not None:
            pts.append((x + float(gr.ctrl_x), y - float(gr.ctrl_y)))
    except Exception:
        pass
    return pts


def _lh56_bounds(graphics):
    pts = []
    for gr in graphics:
        pts.extend(_lh56_points(gr))
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _lh56_scale_point(self, px, py, cx, cy, factor):
    return _lh56_snap(self, cx + (float(px) - cx) * factor), _lh56_snap(self, cy + (float(py) - cy) * factor)


def _lh56_apply_graphic_scale(self, direction:int):
    graphics = _lh56_selected_graphic_models(self, expand_groups=True)
    if not graphics:
        return False
    b = _lh56_bounds(graphics)
    if not b:
        return False
    minx, miny, maxx, maxy = b
    cur_w = abs(maxx - minx)
    cur_h = abs(maxy - miny)
    dominant = max(cur_w, cur_h, _lh56_step(self))
    inc = _lh56_increment(self)
    new_dom = max(_lh56_step(self), dominant + (inc if int(direction) > 0 else -inc))
    factor = new_dom / dominant if dominant > 1e-12 else 1.0
    if abs(factor - 1.0) < 1e-12:
        return False
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    try:
        self.push_undo_state()
    except Exception:
        pass
    min_dim = _lh56_step(self)
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
        nx1, ny1 = _lh56_scale_point(self, x, y, cx, cy, factor)
        nx2, ny2 = _lh56_scale_point(self, x2, y2, cx, cy, factor)
        nw = nx2 - nx1
        nh = ny1 - ny2
        # Keep every non-zero axis at least one edit-grid step. This is what
        # prevents Width from becoming 0/0.5 unexpectedly after snapping.
        if abs(w) > 1e-12 and abs(nw) < min_dim:
            sgn = 1.0 if w >= 0 else -1.0
            gcx = (nx1 + nx2) / 2.0
            nx1 = _lh56_snap(self, gcx - sgn * min_dim / 2.0)
            nx2 = _lh56_snap(self, gcx + sgn * min_dim / 2.0)
            nw = nx2 - nx1
        if abs(h) > 1e-12 and abs(nh) < min_dim:
            sgn = 1.0 if h >= 0 else -1.0
            gcy = (ny1 + ny2) / 2.0
            ny1 = _lh56_snap(self, gcy + sgn * min_dim / 2.0)
            ny2 = _lh56_snap(self, gcy - sgn * min_dim / 2.0)
            nh = ny1 - ny2
        gr.x, gr.y, gr.w, gr.h = nx1, ny1, nw, nh
        if ctrl_abs is not None:
            ncx, ncy = _lh56_scale_point(self, ctrl_abs[0], ctrl_abs[1], cx, cy, factor)
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


def _lh56_scale_selected_grid(self, direction:int):
    try:
        if self._selected_body_active():
            return _lh56_prev_scale_selected_grid(self, direction) if _lh56_prev_scale_selected_grid else None
    except Exception:
        pass
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    try:
        if _lh56_apply_graphic_scale(self, int(direction)):
            return None
        if _lh56_prev_scale_selected_grid:
            return _lh56_prev_scale_selected_grid(self, direction)
    finally:
        try:
            _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=False, refresh=False)
        except Exception:
            pass


def _lh56_scale_selected(self, factor):
    try:
        if self._selected_body_active():
            return _lh56_prev_scale_selected(self, factor) if _lh56_prev_scale_selected else None
    except Exception:
        pass
    try:
        return _lh56_scale_selected_grid(self, 1 if float(factor) >= 1.0 else -1)
    except Exception:
        return _lh56_scale_selected_grid(self, 1)


def _lh56_group_selected_graphics(self):
    models = _lh56_selected_graphic_models(self, expand_groups=False)
    if len(models) < 2:
        try:
            self.statusBar().showMessage('Mindestens zwei Grafikobjekte auswählen, dann Edit > Group Graphics.', 4000)
        except Exception:
            pass
        return
    try:
        self.push_undo_state()
    except Exception:
        pass
    import uuid as _lh56_uuid
    gid = 'G' + _lh56_uuid.uuid4().hex[:8]
    for gr in models:
        _lh56_set_gid(gr, gid)
    try:
        self.dirty = True
        self.rebuild_tree()
        self.refresh_properties()
        self.update_current_unit_canvas_positions()
    except Exception:
        pass
    try:
        self.statusBar().showMessage(f'Grafikgruppe erstellt: {len(models)} Objekte.', 3500)
    except Exception:
        pass


def _lh56_ungroup_selected_graphics(self):
    models = _lh56_selected_graphic_models(self, expand_groups=True)
    if not models:
        return
    try:
        self.push_undo_state()
    except Exception:
        pass
    for gr in models:
        _lh56_set_gid(gr, '')
    try:
        self.dirty = True
        self.rebuild_tree()
        self.refresh_properties()
        self.update_current_unit_canvas_positions()
    except Exception:
        pass
    try:
        self.statusBar().showMessage('Grafikgruppe aufgehoben.', 3500)
    except Exception:
        pass


def _lh56_add_group_actions(self):
    try:
        if getattr(self, '_lh56_group_actions_added', False):
            return
        self._lh56_group_actions_added = True
        # Menu bar action is deliberately used, because a hidden/overflowed
        # toolbar button is easy to miss on small screens.
        edit_menu = None
        try:
            for act in self.menuBar().actions():
                if str(act.text()).replace('&','').lower() == 'edit':
                    edit_menu = act.menu(); break
        except Exception:
            edit_menu = None
        if edit_menu is None:
            edit_menu = self.menuBar().addMenu('&Edit')
        edit_menu.addSeparator()
        a = QAction('Group Graphics', self)
        a.setShortcut(QKeySequence('Ctrl+G'))
        a.triggered.connect(self.group_selected_graphics)
        edit_menu.addAction(a)
        self.addAction(a)
        a = QAction('Ungroup Graphics', self)
        a.setShortcut(QKeySequence('Ctrl+Shift+G'))
        a.triggered.connect(self.ungroup_selected_graphics)
        edit_menu.addAction(a)
        self.addAction(a)
    except Exception:
        pass


try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.scale_selected = _lh56_scale_selected
        _cls.scale_selected_grid = _lh56_scale_selected_grid
        _cls.group_selected_graphics = _lh56_group_selected_graphics
        _cls.ungroup_selected_graphics = _lh56_ungroup_selected_graphics
    _lh56_prev_menus = MainWindow._menus
    def _lh56_menus(self):
        _lh56_prev_menus(self)
        _lh56_add_group_actions(self)
    MainWindow._menus = _lh56_menus
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v57: definitive user-graphic scaling and visible grouping controls.
# ---------------------------------------------------------------------------
# This patch intentionally sits at the very end of the module so it wins over
# older v53/v55/v56 compatibility patches above.

def _lh57_grid_step(self):
    try:
        return max(float(self._edit_grid_step()), 1e-9)
    except Exception:
        try:
            txt = str(self.edit_grid_combo.currentText()).replace('"', '').strip()
            return max(float(txt), 1e-9)
        except Exception:
            return 1.0


def _lh57_scale_increment(self):
    # Toolbar Scale +/- is deliberately a visible grid-size operation.  A 3x3
    # rectangle becomes 4x4, not 3.05x3.05 on small edit-grid settings.
    return max(1.0, _lh57_grid_step(self))


def _lh57_snap(self, v):
    st = _lh57_grid_step(self)
    try:
        return float(self._snap_to_edit_grid(float(v), st))
    except Exception:
        return round(float(v) / st) * st


def _lh57_gid(gr):
    try:
        gid = str(getattr(gr, 'group_id', '') or '')
        if gid:
            return gid
        role = str(getattr(gr, 'graphic_role', '') or '')
        if role.startswith('user_graphic_group:'):
            return role.split(':', 1)[1]
    except Exception:
        pass
    return ''


def _lh57_set_gid(gr, gid):
    gid = str(gid or '')
    try:
        gr.group_id = gid
    except Exception:
        pass
    try:
        gr.graphic_role = ('user_graphic_group:' + gid) if gid else 'user_graphic'
    except Exception:
        pass


def _lh57_is_user_graphic(gr):
    try:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body', 'template_body', 'imported_body', 'body_graphic')
    except Exception:
        return False


def _lh57_selected_graphics(self, expand_groups=True):
    selected = []
    gids = set()
    try:
        items = list(self.scene.selectedItems()) if getattr(self, 'scene', None) else []
    except Exception:
        items = []
    for it in items:
        try:
            if it.data(0) != 'GRAPHIC':
                continue
            gr = getattr(it, 'model', None)
            if gr is None or not _lh57_is_user_graphic(gr):
                continue
            if gr not in selected:
                selected.append(gr)
            gid = _lh57_gid(gr)
            if gid:
                gids.add(gid)
        except Exception:
            pass
    if not selected:
        return []
    if not expand_groups:
        return selected
    out = []
    try:
        all_graphics = list(getattr(getattr(self, 'current_unit', None), 'graphics', []) or [])
    except Exception:
        all_graphics = []
    for gr in all_graphics:
        try:
            if not _lh57_is_user_graphic(gr):
                continue
            gid = _lh57_gid(gr)
            if gr in selected or (gid and gid in gids):
                if gr not in out:
                    out.append(gr)
        except Exception:
            pass
    return out


def _lh57_graphic_bbox(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    x2 = x + w
    y2 = y - h
    return min(x, x2), min(y, y2), max(x, x2), max(y, y2)


def _lh57_group_bbox(graphics):
    boxes = [_lh57_graphic_bbox(g) for g in graphics]
    if not boxes:
        return None
    return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)


def _lh57_apply_graphics_scale(self, direction):
    graphics = _lh57_selected_graphics(self, expand_groups=True)
    if not graphics:
        return False
    bbox = _lh57_group_bbox(graphics)
    if not bbox:
        return False
    minx, miny, maxx, maxy = bbox
    cur_w = maxx - minx
    cur_h = maxy - miny
    inc = _lh57_scale_increment(self)
    min_size = _lh57_grid_step(self)
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
        ngcx = _lh57_snap(self, cx + (gcx - cx) * factor)
        ngcy = _lh57_snap(self, cy + (gcy - cy) * factor)

        shape = str(getattr(gr, 'shape', '') or '').lower()
        if shape in ('line', 'arc'):
            nw = _lh57_snap(self, w * factor)
            nh = _lh57_snap(self, h * factor)
            # A purely vertical/horizontal line may legitimately have one zero
            # axis.  Only keep the non-zero/originally dominant axis alive.
            if abs(w) > 1e-12 and abs(nw) < min_size:
                nw = min_size if w >= 0 else -min_size
            if abs(h) > 1e-12 and abs(nh) < min_size:
                nh = min_size if h >= 0 else -min_size
            gr.x = _lh57_snap(self, ngcx - nw / 2.0)
            gr.y = _lh57_snap(self, ngcy + nh / 2.0)
            gr.w = nw
            gr.h = nh
            try:
                if getattr(gr, 'ctrl_x', None) is not None:
                    gr.ctrl_x = _lh57_snap(self, float(gr.ctrl_x) * factor)
                if getattr(gr, 'ctrl_y', None) is not None:
                    gr.ctrl_y = _lh57_snap(self, float(gr.ctrl_y) * factor)
                if getattr(gr, 'curve_radius', None) not in (None, 0, 0.0):
                    gr.curve_radius = _lh57_snap(self, float(gr.curve_radius) * factor)
            except Exception:
                pass
        else:
            sign_w = -1.0 if w < 0 else 1.0
            sign_h = -1.0 if h < 0 else 1.0
            nw_abs = max(min_size, abs(w) * factor)
            nh_abs = max(min_size, abs(h) * factor)
            nw = sign_w * _lh57_snap(self, nw_abs)
            nh = sign_h * _lh57_snap(self, nh_abs)
            # Snap can round small values down; enforce once more.
            if abs(nw) < min_size:
                nw = sign_w * min_size
            if abs(nh) < min_size:
                nh = sign_h * min_size
            gr.w = nw
            gr.h = nh
            gr.x = _lh57_snap(self, ngcx - nw / 2.0)
            gr.y = _lh57_snap(self, ngcy + nh / 2.0)

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


def _lh57_group_selected_graphics(self):
    models = _lh57_selected_graphics(self, expand_groups=False)
    if len(models) < 2:
        try:
            QMessageBox.information(self, 'Group Graphics', 'Bitte mindestens zwei Grafikobjekte auswählen.')
        except Exception:
            pass
        return
    try:
        self.push_undo_state()
    except Exception:
        pass
    import uuid as _lh57_uuid
    gid = 'G' + _lh57_uuid.uuid4().hex[:8]
    for gr in models:
        _lh57_set_gid(gr, gid)
    try:
        self.dirty = True
        self.rebuild_tree()
        self.refresh_properties()
        self.update_current_unit_canvas_positions()
        self.statusBar().showMessage(f'Grafikgruppe erstellt: {len(models)} Objekte.', 4000)
    except Exception:
        pass


def _lh57_ungroup_selected_graphics(self):
    models = _lh57_selected_graphics(self, expand_groups=True)
    if not models:
        try:
            QMessageBox.information(self, 'Ungroup Graphics', 'Keine Grafikgruppe ausgewählt.')
        except Exception:
            pass
        return
    try:
        self.push_undo_state()
    except Exception:
        pass
    for gr in models:
        _lh57_set_gid(gr, '')
    try:
        self.dirty = True
        self.rebuild_tree()
        self.refresh_properties()
        self.update_current_unit_canvas_positions()
        self.statusBar().showMessage('Grafikgruppe aufgehoben.', 4000)
    except Exception:
        pass


def _lh57_install_group_ui(self):
    if getattr(self, '_lh57_group_ui_installed', False):
        return
    self._lh57_group_ui_installed = True
    try:
        edit_menu = None
        for act in self.menuBar().actions():
            if str(act.text()).replace('&', '').lower() == 'edit':
                edit_menu = act.menu()
                break
        if edit_menu is None:
            edit_menu = self.menuBar().addMenu('&Edit')
        edit_menu.addSeparator()
        a_group = QAction('Group Graphics', self)
        a_group.setShortcut(QKeySequence('Ctrl+G'))
        a_group.triggered.connect(self.group_selected_graphics)
        edit_menu.addAction(a_group)
        self.addAction(a_group)
        a_ungroup = QAction('Ungroup Graphics', self)
        a_ungroup.setShortcut(QKeySequence('Ctrl+Shift+G'))
        a_ungroup.triggered.connect(self.ungroup_selected_graphics)
        edit_menu.addAction(a_ungroup)
        self.addAction(a_ungroup)
    except Exception:
        pass
    try:
        tb = self.addToolBar('Graphic Group')
        btn = QPushButton('Group Graphics')
        btn.setToolTip('Ausgewählte Grafikobjekte gruppieren (Ctrl+G)')
        btn.clicked.connect(self.group_selected_graphics)
        tb.addWidget(btn)
        btn = QPushButton('Ungroup')
        btn.setToolTip('Grafikgruppe aufheben (Ctrl+Shift+G)')
        btn.clicked.connect(self.ungroup_selected_graphics)
        tb.addWidget(btn)
    except Exception:
        pass


try:
    _lh57_prev_scale_selected_grid = MainWindow.scale_selected_grid
    _lh57_prev_scale_selected = MainWindow.scale_selected
except Exception:
    _lh57_prev_scale_selected_grid = None
    _lh57_prev_scale_selected = None


def _lh57_scale_selected_grid(self, direction:int):
    try:
        if self._selected_body_active():
            return _lh57_prev_scale_selected_grid(self, direction) if _lh57_prev_scale_selected_grid else None
    except Exception:
        pass
    if _lh57_apply_graphics_scale(self, int(direction)):
        return None
    if _lh57_prev_scale_selected_grid:
        return _lh57_prev_scale_selected_grid(self, direction)


def _lh57_scale_selected(self, factor):
    try:
        if self._selected_body_active():
            return _lh57_prev_scale_selected(self, factor) if _lh57_prev_scale_selected else None
    except Exception:
        pass
    direction = 1
    try:
        direction = 1 if float(factor) >= 1.0 else -1
    except Exception:
        direction = 1
    return _lh57_scale_selected_grid(self, direction)


try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.scale_selected_grid = _lh57_scale_selected_grid
        _cls.scale_selected = _lh57_scale_selected
        _cls.group_selected_graphics = _lh57_group_selected_graphics
        _cls.ungroup_selected_graphics = _lh57_ungroup_selected_graphics
        _old_init = _cls.__init__
        def _new_init(self, *args, __old_init=_old_init, **kwargs):
            __old_init(self, *args, **kwargs)
            try:
                _lh57_install_group_ui(self)
            except Exception:
                pass
        _cls.__init__ = _new_init
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v58: BODY-identical graphic/group scaling around own origin.
# ---------------------------------------------------------------------------
# User rule:
# - Single GRAPHIC scales like BODY, but around the graphic's own origin/center.
# - A graphic group is one logical object. Its origin is the center of the
#   maximum x/y bounding box of all group members.
# - Scale +/- changes the logical object's width and height by one visible grid
#   unit, snapped to Edit grid, with minimum one Edit-grid step.
# - Selection highlight for a group is a single bounding rectangle.

try:
    _lh58_prev_scale_selected_grid = MainWindow.scale_selected_grid
    _lh58_prev_scale_selected = MainWindow.scale_selected
except Exception:
    _lh58_prev_scale_selected_grid = None
    _lh58_prev_scale_selected = None


def _lh58_grid_step(self):
    try:
        return max(float(self._edit_grid_step()), 1e-9)
    except Exception:
        return 0.05


def _lh58_visible_increment(self):
    # BODY toolbar scaling in this tool is a visible grid-size operation. Keep
    # the same interaction for graphics: 3x3 -> 4x4 while still snapping to the
    # active Edit grid.
    try:
        return max(1.0, _lh58_grid_step(self))
    except Exception:
        return 1.0


def _lh58_snap(self, v):
    st = _lh58_grid_step(self)
    try:
        return float(self._snap_to_edit_grid(float(v), st))
    except Exception:
        return round(float(v) / st) * st


def _lh58_gid(gr):
    try:
        gid = str(getattr(gr, 'group_id', '') or '')
        if gid:
            return gid
        role = str(getattr(gr, 'graphic_role', '') or '')
        if role.startswith('user_graphic_group:'):
            return role.split(':', 1)[1]
    except Exception:
        pass
    return ''


def _lh58_set_gid(gr, gid):
    gid = str(gid or '')
    try:
        gr.group_id = gid
    except Exception:
        pass
    try:
        gr.graphic_role = ('user_graphic_group:' + gid) if gid else 'user_graphic'
    except Exception:
        pass


def _lh58_is_user_graphic(gr):
    try:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body', 'template_body', 'imported_body', 'body_graphic')
    except Exception:
        return False


def _lh58_selected_graphics(self, expand_groups=True):
    selected = []
    gids = set()
    try:
        items = list(self.scene.selectedItems()) if getattr(self, 'scene', None) else []
    except Exception:
        items = []
    for it in items:
        try:
            if it.data(0) != 'GRAPHIC':
                continue
            gr = getattr(it, 'model', None)
            if gr is None or not _lh58_is_user_graphic(gr):
                continue
            if gr not in selected:
                selected.append(gr)
            gid = _lh58_gid(gr)
            if gid:
                gids.add(gid)
        except Exception:
            pass
    if not selected:
        return []
    if not expand_groups:
        return selected
    out = []
    try:
        all_graphics = list(getattr(getattr(self, 'current_unit', None), 'graphics', []) or [])
    except Exception:
        all_graphics = []
    for gr in all_graphics:
        try:
            if not _lh58_is_user_graphic(gr):
                continue
            gid = _lh58_gid(gr)
            if gr in selected or (gid and gid in gids):
                if gr not in out:
                    out.append(gr)
        except Exception:
            pass
    return out


def _lh58_bbox(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    x2 = x + w
    y2 = y - h
    return min(x, x2), min(y, y2), max(x, x2), max(y, y2)


def _lh58_group_bbox(graphics):
    boxes = [_lh58_bbox(g) for g in graphics]
    if not boxes:
        return None
    return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)


def _lh58_apply_graphics_scale(self, direction:int):
    graphics = _lh58_selected_graphics(self, expand_groups=True)
    if not graphics:
        return False
    b = _lh58_group_bbox(graphics)
    if not b:
        return False
    minx, miny, maxx, maxy = b
    cur_w = max(0.0, maxx - minx)
    cur_h = max(0.0, maxy - miny)
    min_size = _lh58_grid_step(self)
    inc = _lh58_visible_increment(self)

    # BODY-like: width and height are stepped independently, then snapped.  This
    # guarantees a selected 3x3 rectangle becomes 4x4 and stays centered.
    target_w = max(min_size, _lh58_snap(self, cur_w + (inc if int(direction) > 0 else -inc)))
    target_h = max(min_size, _lh58_snap(self, cur_h + (inc if int(direction) > 0 else -inc)))
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
        ngcx = _lh58_snap(self, cx + (gcx - cx) * sx)
        ngcy = _lh58_snap(self, cy + (gcy - cy) * sy)

        nw = _lh58_snap(self, w * sx)
        nh = _lh58_snap(self, h * sy)
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
                    gr.ctrl_x = _lh58_snap(self, float(gr.ctrl_x) * sx)
                if getattr(gr, 'ctrl_y', None) is not None:
                    gr.ctrl_y = _lh58_snap(self, float(gr.ctrl_y) * sy)
                if getattr(gr, 'curve_radius', None) not in (None, 0, 0.0):
                    gr.curve_radius = _lh58_snap(self, float(gr.curve_radius) * sy)
            except Exception:
                pass

        gr.w = nw
        gr.h = nh
        gr.x = _lh58_snap(self, ngcx - nw / 2.0)
        gr.y = _lh58_snap(self, ngcy + nh / 2.0)

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


def _lh58_scale_selected_grid(self, direction:int):
    try:
        if self._selected_body_active():
            return _lh58_prev_scale_selected_grid(self, direction) if _lh58_prev_scale_selected_grid else None
    except Exception:
        pass
    if _lh58_apply_graphics_scale(self, int(direction)):
        return None
    if _lh58_prev_scale_selected_grid:
        return _lh58_prev_scale_selected_grid(self, direction)


def _lh58_scale_selected(self, factor):
    try:
        if self._selected_body_active():
            return _lh58_prev_scale_selected(self, factor) if _lh58_prev_scale_selected else None
    except Exception:
        pass
    try:
        direction = 1 if float(factor) >= 1.0 else -1
    except Exception:
        direction = 1
    return _lh58_scale_selected_grid(self, direction)


def _lh58_group_selected_graphics(self):
    models = _lh58_selected_graphics(self, expand_groups=False)
    if len(models) < 2:
        try:
            QMessageBox.information(self, 'Group Graphics', 'Bitte mindestens zwei eingefügte Grafikobjekte auswählen.')
        except Exception:
            pass
        return
    try:
        self.push_undo_state()
    except Exception:
        pass
    import uuid as _lh58_uuid
    gid = 'G' + _lh58_uuid.uuid4().hex[:8]
    for gr in models:
        _lh58_set_gid(gr, gid)
    try:
        self.dirty = True
        self.update_current_unit_canvas_positions()
        self.rebuild_tree()
        self.refresh_properties()
        self.statusBar().showMessage(f'Grafikgruppe erstellt: {len(models)} Objekte.', 4000)
    except Exception:
        pass


def _lh58_ungroup_selected_graphics(self):
    models = _lh58_selected_graphics(self, expand_groups=True)
    if not models:
        try:
            QMessageBox.information(self, 'Ungroup Graphics', 'Keine Grafikgruppe ausgewählt.')
        except Exception:
            pass
        return
    try:
        self.push_undo_state()
    except Exception:
        pass
    for gr in models:
        _lh58_set_gid(gr, '')
    try:
        self.dirty = True
        self.update_current_unit_canvas_positions()
        self.rebuild_tree()
        self.refresh_properties()
        self.statusBar().showMessage('Grafikgruppe aufgehoben.', 4000)
    except Exception:
        pass


def _lh58_install_group_ui(self):
    if getattr(self, '_lh58_group_ui_installed', False):
        return
    self._lh58_group_ui_installed = True
    try:
        edit_menu = None
        for act in self.menuBar().actions():
            if str(act.text()).replace('&', '').lower() == 'edit':
                edit_menu = act.menu()
                break
        if edit_menu is None:
            edit_menu = self.menuBar().addMenu('&Edit')
        edit_menu.addSeparator()
        a_group = QAction('Group Graphics', self)
        a_group.setShortcut(QKeySequence('Ctrl+G'))
        a_group.triggered.connect(self.group_selected_graphics)
        edit_menu.addAction(a_group)
        self.addAction(a_group)
        a_ungroup = QAction('Ungroup Graphics', self)
        a_ungroup.setShortcut(QKeySequence('Ctrl+Shift+G'))
        a_ungroup.triggered.connect(self.ungroup_selected_graphics)
        edit_menu.addAction(a_ungroup)
        self.addAction(a_ungroup)
    except Exception:
        pass
    try:
        tb = self.addToolBar('Graphic Group')
        btn = QPushButton('Group Graphics')
        btn.setToolTip('Ausgewählte eingefügte Grafikobjekte gruppieren (Ctrl+G)')
        btn.clicked.connect(self.group_selected_graphics)
        tb.addWidget(btn)
        btn = QPushButton('Ungroup Graphics')
        btn.setToolTip('Grafikgruppe aufheben (Ctrl+Shift+G)')
        btn.clicked.connect(self.ungroup_selected_graphics)
        tb.addWidget(btn)
    except Exception:
        pass


try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.scale_selected_grid = _lh58_scale_selected_grid
        _cls.scale_selected = _lh58_scale_selected
        _cls.group_selected_graphics = _lh58_group_selected_graphics
        _cls.ungroup_selected_graphics = _lh58_ungroup_selected_graphics
        _old_init = _cls.__init__
        def _lh58_new_init(self, *args, __old_init=_old_init, **kwargs):
            __old_init(self, *args, **kwargs)
            try:
                _lh58_install_group_ui(self)
            except Exception:
                pass
        _cls.__init__ = _lh58_new_init
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v59: real logical GRAPHIC GROUP selection + BODY-like proportional
# scaling around the local/group origin.
# ---------------------------------------------------------------------------
try:
    _lh59_prev_scale_selected_grid = MainWindow.scale_selected_grid
    _lh59_prev_scale_selected = MainWindow.scale_selected
    _lh59_prev_refresh_properties = MainWindow.refresh_properties
    _lh59_prev_on_scene_selection_changed = MainWindow.on_scene_selection_changed
except Exception:
    _lh59_prev_scale_selected_grid = None
    _lh59_prev_scale_selected = None
    _lh59_prev_refresh_properties = None
    _lh59_prev_on_scene_selection_changed = None


def _lh59_gid(gr):
    try:
        gid = str(getattr(gr, 'group_id', '') or '')
        if gid:
            return gid
        role = str(getattr(gr, 'graphic_role', '') or '')
        if role.startswith('user_graphic_group:'):
            return role.split(':', 1)[1]
    except Exception:
        pass
    return ''


def _lh59_set_gid(gr, gid):
    gid = str(gid or '')
    try: gr.group_id = gid
    except Exception: pass
    try: gr.graphic_role = ('user_graphic_group:' + gid) if gid else 'user_graphic'
    except Exception: pass


def _lh59_is_user_graphic(gr):
    try:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body', 'template_body', 'imported_body', 'body_graphic')
    except Exception:
        return False


def _lh59_grid_step(self):
    try: return max(1e-9, float(self._edit_grid_step()))
    except Exception: return 0.05


def _lh59_snap(self, value):
    st = _lh59_grid_step(self)
    try: return float(self._snap_to_edit_grid(float(value), st))
    except Exception: return round(float(value) / st) * st


def _lh59_selected_graphic_items(self):
    out = []
    try: items = list(self.scene.selectedItems()) if getattr(self, 'scene', None) else []
    except Exception: items = []
    for it in items:
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None and _lh59_is_user_graphic(it.model):
                out.append(it)
        except Exception:
            pass
    return out


def _lh59_all_graphic_items(self):
    out = []
    try: items = list(self.scene.items()) if getattr(self, 'scene', None) else []
    except Exception: items = []
    for it in items:
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None and _lh59_is_user_graphic(it.model):
                out.append(it)
        except Exception:
            pass
    return out


def _lh59_selected_graphic_models(self, expand_groups=True):
    selected = []
    gids = set()
    for it in _lh59_selected_graphic_items(self):
        gr = it.model
        if gr not in selected:
            selected.append(gr)
        gid = _lh59_gid(gr)
        if gid:
            gids.add(gid)
    if not selected:
        return []
    if not expand_groups or not gids:
        return selected
    out = []
    try: graphics = list(getattr(getattr(self, 'current_unit', None), 'graphics', []) or [])
    except Exception: graphics = []
    for gr in graphics:
        try:
            gid = _lh59_gid(gr)
            if gr in selected or (gid and gid in gids):
                if _lh59_is_user_graphic(gr) and gr not in out:
                    out.append(gr)
        except Exception:
            pass
    return out


def _lh59_bbox(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0); y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0); h = float(getattr(gr, 'h', 0.0) or 0.0)
    x2 = x + w; y2 = y - h
    return min(x, x2), min(y, y2), max(x, x2), max(y, y2)


def _lh59_group_bbox(models):
    boxes = [_lh59_bbox(g) for g in models]
    if not boxes: return None
    return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)


def _lh59_sync_group_selection(self):
    """A graphics group is one logical object: selecting one member selects all
    members, while the property panel/paint code presents one group."""
    if getattr(self, '_lh59_syncing_group_selection', False):
        return
    selected = _lh59_selected_graphic_items(self)
    gids = {_lh59_gid(it.model) for it in selected if _lh59_gid(it.model)}
    if not gids:
        return
    try:
        self._lh59_syncing_group_selection = True
        self.scene.blockSignals(True)
        for it in _lh59_all_graphic_items(self):
            try:
                if _lh59_gid(it.model) in gids:
                    it.setSelected(True)
            except Exception:
                pass
    finally:
        try: self.scene.blockSignals(False)
        except Exception: pass
        self._lh59_syncing_group_selection = False


def _lh59_on_scene_selection_changed(self):
    try: _lh59_sync_group_selection(self)
    except Exception: pass
    if _lh59_prev_on_scene_selection_changed:
        return _lh59_prev_on_scene_selection_changed(self)
    try: self.refresh_properties()
    except Exception: pass


def _lh59_group_selected_graphics(self):
    models = _lh59_selected_graphic_models(self, expand_groups=False)
    # de-duplicate by object identity
    clean = []
    for m in models:
        if m not in clean:
            clean.append(m)
    if len(clean) < 2:
        try: QMessageBox.information(self, 'Group Graphics', 'Bitte mindestens zwei eingefügte Grafikobjekte auswählen.')
        except Exception: pass
        return
    try: self.push_undo_state()
    except Exception: pass
    import uuid as _lh59_uuid
    gid = 'G' + _lh59_uuid.uuid4().hex[:8]
    for gr in clean:
        _lh59_set_gid(gr, gid)
    try:
        self.dirty = True
        self.update_current_unit_canvas_positions()
    except Exception:
        pass
    # Reselect the complete group so the user immediately sees one logical bbox.
    try:
        self.scene.blockSignals(True)
        for it in _lh59_all_graphic_items(self):
            it.setSelected(_lh59_gid(it.model) == gid)
    finally:
        try: self.scene.blockSignals(False)
        except Exception: pass
    try: self.rebuild_tree()
    except Exception: pass
    try: self.refresh_properties()
    except Exception: pass
    try: self.scene.update()
    except Exception: pass
    try: self.statusBar().showMessage(f'Grafikgruppe erstellt: {len(clean)} Objekte als 1 Objekt.', 4000)
    except Exception: pass


def _lh59_ungroup_selected_graphics(self):
    models = _lh59_selected_graphic_models(self, expand_groups=True)
    if not models:
        try: QMessageBox.information(self, 'Ungroup Graphics', 'Keine Grafikgruppe ausgewählt.')
        except Exception: pass
        return
    try: self.push_undo_state()
    except Exception: pass
    for gr in models:
        _lh59_set_gid(gr, '')
    try:
        self.dirty = True
        self.update_current_unit_canvas_positions()
        self.rebuild_tree(); self.refresh_properties(); self.scene.update()
        self.statusBar().showMessage('Grafikgruppe aufgehoben.', 4000)
    except Exception:
        pass


def _lh59_apply_graphics_scale(self, direction:int):
    models = _lh59_selected_graphic_models(self, expand_groups=True)
    if not models:
        return False
    b = _lh59_group_bbox(models)
    if not b:
        return False
    minx, miny, maxx, maxy = b
    cur_w = maxx - minx; cur_h = maxy - miny
    if cur_w <= 1e-12 and cur_h <= 1e-12:
        return False
    # BODY-like proportional toolbar scaling: one logical grid unit per click,
    # but all resulting coordinates/dimensions hit the edit grid.
    dom = max(cur_w, cur_h, _lh59_grid_step(self))
    target_dom = dom + (1.0 if int(direction) > 0 else -1.0)
    target_dom = max(_lh59_grid_step(self), _lh59_snap(self, target_dom))
    factor = target_dom / dom
    if abs(factor - 1.0) < 1e-12:
        return True
    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0
    min_dim = _lh59_grid_step(self)
    try: self.push_undo_state()
    except Exception: pass
    for gr in models:
        try:
            x = float(getattr(gr, 'x', 0.0) or 0.0); y = float(getattr(gr, 'y', 0.0) or 0.0)
            w = float(getattr(gr, 'w', 0.0) or 0.0); h = float(getattr(gr, 'h', 0.0) or 0.0)
            shape = str(getattr(gr, 'shape', '') or '').lower()
            gcx = x + w / 2.0
            gcy = y - h / 2.0
            ngcx = _lh59_snap(self, cx + (gcx - cx) * factor)
            ngcy = _lh59_snap(self, cy + (gcy - cy) * factor)
            nw = _lh59_snap(self, w * factor)
            nh = _lh59_snap(self, h * factor)
            if shape not in ('line', 'arc'):
                if abs(nw) < min_dim: nw = (1.0 if nw >= 0 else -1.0) * min_dim
                if abs(nh) < min_dim: nh = (1.0 if nh >= 0 else -1.0) * min_dim
            else:
                # Lines/arcs may be vertical or horizontal. Preserve true zero axes.
                if abs(w) > 1e-12 and abs(nw) < min_dim: nw = (1.0 if w >= 0 else -1.0) * min_dim
                if abs(h) > 1e-12 and abs(nh) < min_dim: nh = (1.0 if h >= 0 else -1.0) * min_dim
                if getattr(gr, 'ctrl_x', None) is not None:
                    gr.ctrl_x = _lh59_snap(self, float(gr.ctrl_x) * factor)
                if getattr(gr, 'ctrl_y', None) is not None:
                    gr.ctrl_y = _lh59_snap(self, float(gr.ctrl_y) * factor)
                if getattr(gr, 'curve_radius', None) not in (None, 0, 0.0):
                    gr.curve_radius = _lh59_snap(self, float(gr.curve_radius) * factor)
            gr.w = nw; gr.h = nh
            gr.x = _lh59_snap(self, ngcx - nw / 2.0)
            gr.y = _lh59_snap(self, ngcy + nh / 2.0)
        except Exception:
            pass
    try:
        self.dirty = True
        self.update_current_unit_canvas_positions()
    except Exception:
        try: self.schedule_scene_refresh()
        except Exception: pass
    try: _lh59_sync_group_selection(self)
    except Exception: pass
    try: self.refresh_properties(); self.rebuild_tree(); self.scene.update()
    except Exception: pass
    return True


def _lh59_scale_selected_grid(self, direction:int):
    try:
        if self._selected_body_active():
            return _lh59_prev_scale_selected_grid(self, direction) if _lh59_prev_scale_selected_grid else None
    except Exception:
        pass
    if _lh59_apply_graphics_scale(self, int(direction)):
        return None
    if _lh59_prev_scale_selected_grid:
        return _lh59_prev_scale_selected_grid(self, direction)


def _lh59_scale_selected(self, factor):
    try:
        if self._selected_body_active():
            return _lh59_prev_scale_selected(self, factor) if _lh59_prev_scale_selected else None
    except Exception:
        pass
    try: direction = 1 if float(factor) >= 1.0 else -1
    except Exception: direction = 1
    return _lh59_scale_selected_grid(self, direction)


def _lh59_refresh_properties(self):
    # Collapse selected members of the same graphic group into a single logical
    # property view. This prevents the old "N objects selected" panel for groups.
    try:
        selected = [i for i in self.scene.selectedItems()]
        graphic_items = [i for i in selected if i.data(0) == 'GRAPHIC' and getattr(i, 'model', None) is not None]
        gids = {_lh59_gid(i.model) for i in graphic_items if _lh59_gid(i.model)}
        if graphic_items and len(gids) == 1 and len(graphic_items) == len(selected):
            _lh59_sync_group_selection(self)
            models = _lh59_selected_graphic_models(self, expand_groups=True)
            b = _lh59_group_bbox(models)
            if self.clear_properties():
                self.form.addRow(QLabel('Selected: GRAPHIC GROUP'))
                self.form.addRow(QLabel('<b>GRAPHIC GROUP</b>'))
                if b:
                    minx, miny, maxx, maxy = b
                    self.form.addRow('Width [grid]', QLabel(f'{(maxx-minx):.3f}'.replace('.', ',')))
                    self.form.addRow('Height [grid]', QLabel(f'{(maxy-miny):.3f}'.replace('.', ',')))
                self.form.addRow(QLabel('Scale/Move/Rotate/Flip behandeln die Gruppe als 1 Objekt.'))
                self.form.addRow(QLabel('Ungroup Graphics löst die Gruppe wieder auf.'))
            return
    except Exception:
        pass
    if _lh59_prev_refresh_properties:
        return _lh59_prev_refresh_properties(self)


try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.scale_selected_grid = _lh59_scale_selected_grid
        _cls.scale_selected = _lh59_scale_selected
        _cls.group_selected_graphics = _lh59_group_selected_graphics
        _cls.ungroup_selected_graphics = _lh59_ungroup_selected_graphics
        _cls.refresh_properties = _lh59_refresh_properties
        if hasattr(_cls, 'on_scene_selection_changed'):
            _cls.on_scene_selection_changed = _lh59_on_scene_selection_changed
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v61: robust graphic-group geometry core.
# ---------------------------------------------------------------------------
# A graphic group is now handled as a single logical object for toolbar
# transforms. The group origin is the real visible bounding-box center. Scale,
# flip and rotate transform each child center relative to that origin and then
# update the child's own local transform. This avoids the old offset outline and
# pivot drift caused by mixing raw x/y/w/h boxes with selected helper graphics.

try:
    _lh61_prev_rotate_selected = MainWindow.rotate_selected
    _lh61_prev_flip_h = MainWindow.flip_selected_horizontal
    _lh61_prev_flip_v = MainWindow.flip_selected_vertical
    _lh61_prev_scale_grid = MainWindow.scale_selected_grid
    _lh61_prev_init = MainWindow.__init__
except Exception:
    _lh61_prev_rotate_selected = _lh61_prev_flip_h = _lh61_prev_flip_v = _lh61_prev_scale_grid = None
    _lh61_prev_init = None


def _lh61_gid(gr):
    try:
        gid = str(getattr(gr, 'group_id', '') or '')
        if gid:
            return gid
        role = str(getattr(gr, 'graphic_role', '') or '')
        if role.startswith('user_graphic_group:'):
            return role.split(':', 1)[1]
    except Exception:
        pass
    return ''


def _lh61_set_gid(gr, gid):
    gid = str(gid or '')
    try: gr.group_id = gid
    except Exception: pass
    try: gr.graphic_role = ('user_graphic_group:' + gid) if gid else 'user_graphic'
    except Exception: pass


def _lh61_is_user_graphic(gr):
    try:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body', 'template_body', 'imported_body', 'body_graphic')
    except Exception:
        return False


def _lh61_grid_step(self):
    try: return max(1e-9, float(self._edit_grid_step()))
    except Exception: return 0.05


def _lh61_snap(self, value):
    st = _lh61_grid_step(self)
    try: return float(self._snap_to_edit_grid(float(value), st))
    except Exception: return round(float(value) / st) * st


def _lh61_graphic_items(self):
    out = []
    try: items = list(self.scene.items()) if getattr(self, 'scene', None) else []
    except Exception: items = []
    for it in items:
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None and _lh61_is_user_graphic(it.model):
                out.append(it)
        except Exception:
            pass
    return out


def _lh61_selected_graphic_items(self):
    out = []
    try: items = list(self.scene.selectedItems()) if getattr(self, 'scene', None) else []
    except Exception: items = []
    for it in items:
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None and _lh61_is_user_graphic(it.model):
                out.append(it)
        except Exception:
            pass
    return out


def _lh61_selected_models(self, expand_groups=True):
    selected = []
    gids = set()
    for it in _lh61_selected_graphic_items(self):
        gr = it.model
        if gr not in selected:
            selected.append(gr)
        gid = _lh61_gid(gr)
        if gid:
            gids.add(gid)
    if not selected:
        return []
    if not expand_groups or not gids:
        return selected
    out = []
    try: all_models = list(getattr(getattr(self, 'current_unit', None), 'graphics', []) or [])
    except Exception: all_models = []
    for gr in all_models:
        try:
            gid = _lh61_gid(gr)
            if _lh61_is_user_graphic(gr) and (gr in selected or (gid and gid in gids)) and gr not in out:
                out.append(gr)
        except Exception:
            pass
    return out


def _lh61_selected_single_group_id(self):
    gids = set()
    for it in _lh61_selected_graphic_items(self):
        gid = _lh61_gid(it.model)
        if gid:
            gids.add(gid)
        else:
            return ''
    return next(iter(gids)) if len(gids) == 1 else ''


def _lh61_item_for_model(self, model):
    for it in _lh61_graphic_items(self):
        try:
            if it.model is model:
                return it
        except Exception:
            pass
    return None


def _lh61_scene_bbox_for_models(self, models):
    rect = None
    for gr in models:
        it = _lh61_item_for_model(self, gr)
        if it is None:
            continue
        try:
            r = it.sceneBoundingRect()
            rect = QRectF(r) if rect is None else rect.united(r)
        except Exception:
            pass
    return rect


def _lh61_model_bbox(models):
    boxes = []
    for gr in models:
        try:
            x = float(getattr(gr, 'x', 0.0) or 0.0); y = float(getattr(gr, 'y', 0.0) or 0.0)
            w = float(getattr(gr, 'w', 0.0) or 0.0); h = float(getattr(gr, 'h', 0.0) or 0.0)
            boxes.append((min(x, x + w), min(y, y - h), max(x, x + w), max(y, y - h)))
        except Exception:
            pass
    if not boxes:
        return None
    return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)


def _lh61_origin_grid(self, models):
    # Use the model-space maximum x/y box as stable transformation origin. This
    # keeps the origin stable across refreshes; the visual outline is computed
    # separately from the live QGraphicsItem scene bounding boxes.
    b = _lh61_model_bbox(models)
    if not b:
        return 0.0, 0.0
    minx, miny, maxx, maxy = b
    return (minx + maxx) / 2.0, (miny + maxy) / 2.0


def _lh61_model_center(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0); y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0); h = float(getattr(gr, 'h', 0.0) or 0.0)
    return x + w / 2.0, y - h / 2.0


def _lh61_set_model_center(gr, cx, cy):
    w = float(getattr(gr, 'w', 0.0) or 0.0); h = float(getattr(gr, 'h', 0.0) or 0.0)
    gr.x = cx - w / 2.0
    gr.y = cy + h / 2.0


def _lh61_update_scene(self):
    try: self.update_current_unit_canvas_positions()
    except Exception:
        try: self.schedule_scene_refresh()
        except Exception: pass
    try: _lh61_sync_group_selection(self)
    except Exception: pass
    try: _lh61_update_group_outline(self)
    except Exception: pass
    try: self.refresh_properties()
    except Exception: pass
    try: self.rebuild_tree()
    except Exception: pass
    try: self.scene.update(); self.view.viewport().update()
    except Exception: pass


def _lh61_sync_group_selection(self):
    if getattr(self, '_lh61_syncing_selection', False):
        return
    selected = _lh61_selected_graphic_items(self)
    gids = {_lh61_gid(it.model) for it in selected if _lh61_gid(it.model)}
    if not gids:
        _lh61_update_group_outline(self)
        return
    try:
        self._lh61_syncing_selection = True
        self.scene.blockSignals(True)
        for it in _lh61_graphic_items(self):
            gid = _lh61_gid(it.model)
            if gid in gids:
                it.setSelected(True)
    finally:
        try: self.scene.blockSignals(False)
        except Exception: pass
        self._lh61_syncing_selection = False
    _lh61_update_group_outline(self)


def _lh61_clear_group_outline(self):
    try:
        item = getattr(self, '_lh61_group_outline_item', None)
        if item is not None and getattr(self, 'scene', None) is not None:
            self.scene.removeItem(item)
    except Exception:
        pass
    self._lh61_group_outline_item = None


def _lh61_update_group_outline(self):
    gid = _lh61_selected_single_group_id(self)
    if not gid:
        _lh61_clear_group_outline(self)
        return
    models = _lh61_selected_models(self, expand_groups=True)
    if len(models) < 2:
        _lh61_clear_group_outline(self)
        return
    rect = _lh61_scene_bbox_for_models(self, models)
    if rect is None or not rect.isValid():
        _lh61_clear_group_outline(self)
        return
    try:
        pad = max(3.0, float(getattr(self, 'grid_px', 20)) * 0.15)
        rect = rect.adjusted(-pad, -pad, pad, pad)
    except Exception:
        pass
    item = getattr(self, '_lh61_group_outline_item', None)
    try:
        if item is None:
            item = QGraphicsRectItem()
            item.setData(0, 'HIGHLIGHT')
            item.setFlag(QGraphicsItem.ItemIsSelectable, False)
            item.setFlag(QGraphicsItem.ItemIsMovable, False)
            item.setAcceptedMouseButtons(Qt.NoButton)
            item.setZValue(1e6)
            pen = QPen(QColor(80, 80, 80), 1, Qt.DashLine)
            item.setPen(pen)
            item.setBrush(QBrush(Qt.NoBrush))
            self.scene.addItem(item)
            self._lh61_group_outline_item = item
        item.setRect(rect)
        item.show()
    except Exception:
        pass


def _lh61_group_selected_graphics(self):
    models = _lh61_selected_models(self, expand_groups=False)
    clean = []
    for m in models:
        if m not in clean:
            clean.append(m)
    if len(clean) < 2:
        try: QMessageBox.information(self, 'Group Graphics', 'Bitte mindestens zwei eingefügte Grafikobjekte auswählen.')
        except Exception: pass
        return
    try: self.push_undo_state()
    except Exception: pass
    import uuid as _lh61_uuid
    gid = 'G' + _lh61_uuid.uuid4().hex[:8]
    for gr in clean:
        _lh61_set_gid(gr, gid)
    try:
        self.dirty = True
        self.scene.blockSignals(True)
        for it in _lh61_graphic_items(self):
            it.setSelected(_lh61_gid(it.model) == gid)
    finally:
        try: self.scene.blockSignals(False)
        except Exception: pass
    _lh61_update_scene(self)
    try: self.statusBar().showMessage(f'Grafikgruppe erstellt: {len(clean)} Objekte als 1 Objekt.', 4000)
    except Exception: pass


def _lh61_ungroup_selected_graphics(self):
    models = _lh61_selected_models(self, expand_groups=True)
    if not models:
        try: QMessageBox.information(self, 'Ungroup Graphics', 'Keine Grafikgruppe ausgewählt.')
        except Exception: pass
        return
    try: self.push_undo_state()
    except Exception: pass
    for gr in models:
        _lh61_set_gid(gr, '')
    try: self.dirty = True
    except Exception: pass
    _lh61_clear_group_outline(self)
    _lh61_update_scene(self)
    try: self.statusBar().showMessage('Grafikgruppe aufgehoben.', 4000)
    except Exception: pass


def _lh61_apply_scale(self, direction):
    models = _lh61_selected_models(self, expand_groups=True)
    if not models:
        return False
    b = _lh61_model_bbox(models)
    if not b:
        return False
    minx, miny, maxx, maxy = b
    cur_w = maxx - minx; cur_h = maxy - miny
    dom = max(cur_w, cur_h, _lh61_grid_step(self))
    target_dom = max(_lh61_grid_step(self), _lh61_snap(self, dom + (1.0 if int(direction) > 0 else -1.0)))
    factor = target_dom / dom if dom > 1e-12 else 1.0
    if abs(factor - 1.0) < 1e-12:
        return True
    ox, oy = _lh61_origin_grid(self, models)
    min_dim = _lh61_grid_step(self)
    try: self.push_undo_state()
    except Exception: pass
    for gr in models:
        try:
            cx, cy = _lh61_model_center(gr)
            ncx = ox + (cx - ox) * factor
            ncy = oy + (cy - oy) * factor
            w = float(getattr(gr, 'w', 0.0) or 0.0); h = float(getattr(gr, 'h', 0.0) or 0.0)
            shape = str(getattr(gr, 'shape', '') or '').lower()
            nw = _lh61_snap(self, w * factor)
            nh = _lh61_snap(self, h * factor)
            if shape not in ('line', 'arc'):
                if abs(nw) < min_dim: nw = (1.0 if w >= 0 else -1.0) * min_dim
                if abs(nh) < min_dim: nh = (1.0 if h >= 0 else -1.0) * min_dim
            else:
                if abs(w) > 1e-12 and abs(nw) < min_dim: nw = (1.0 if w >= 0 else -1.0) * min_dim
                if abs(h) > 1e-12 and abs(nh) < min_dim: nh = (1.0 if h >= 0 else -1.0) * min_dim
                if getattr(gr, 'ctrl_x', None) is not None:
                    gr.ctrl_x = _lh61_snap(self, float(gr.ctrl_x) * factor)
                if getattr(gr, 'ctrl_y', None) is not None:
                    gr.ctrl_y = _lh61_snap(self, float(gr.ctrl_y) * factor)
                if getattr(gr, 'curve_radius', None) not in (None, 0, 0.0):
                    gr.curve_radius = _lh61_snap(self, float(gr.curve_radius) * factor)
            gr.w = nw; gr.h = nh
            _lh61_set_model_center(gr, ncx, ncy)
        except Exception:
            pass
    try: self.dirty = True
    except Exception: pass
    _lh61_update_scene(self)
    return True


def _lh61_apply_rotate(self, deg):
    models = _lh61_selected_models(self, expand_groups=True)
    if not models:
        return False
    ox, oy = _lh61_origin_grid(self, models)
    rad = math.radians(float(deg))
    c = math.cos(rad); s = math.sin(rad)
    try: self.push_undo_state()
    except Exception: pass
    for gr in models:
        try:
            cx, cy = _lh61_model_center(gr)
            dx, dy = cx - ox, cy - oy
            ncx = ox + dx * c - dy * s
            ncy = oy + dx * s + dy * c
            _lh61_set_model_center(gr, ncx, ncy)
            cur = float(getattr(gr, 'rotation', 0.0) or 0.0)
            gr.rotation = (round((cur + float(deg)) / 90.0) * 90.0) % 360.0
        except Exception:
            pass
    try: self.dirty = True
    except Exception: pass
    _lh61_update_scene(self)
    return True


def _lh61_apply_flip(self, horizontal=True):
    models = _lh61_selected_models(self, expand_groups=True)
    if not models:
        return False
    ox, oy = _lh61_origin_grid(self, models)
    try: self.push_undo_state()
    except Exception: pass
    for gr in models:
        try:
            cx, cy = _lh61_model_center(gr)
            if horizontal:
                ncx, ncy = ox - (cx - ox), cy
                gr.scale_x = -float(getattr(gr, 'scale_x', 1.0) or 1.0)
            else:
                ncx, ncy = cx, oy - (cy - oy)
                gr.scale_y = -float(getattr(gr, 'scale_y', 1.0) or 1.0)
            _lh61_set_model_center(gr, ncx, ncy)
        except Exception:
            pass
    try: self.dirty = True
    except Exception: pass
    _lh61_update_scene(self)
    return True


def _lh61_scale_selected_grid(self, direction:int):
    try:
        if self._selected_body_active():
            return _lh61_prev_scale_grid(self, direction) if _lh61_prev_scale_grid else None
    except Exception:
        pass
    if _lh61_apply_scale(self, direction):
        return None
    if _lh61_prev_scale_grid:
        return _lh61_prev_scale_grid(self, direction)


def _lh61_rotate_selected(self, deg):
    try:
        if self._selected_body_active():
            return _lh61_prev_rotate_selected(self, deg) if _lh61_prev_rotate_selected else None
    except Exception:
        pass
    if _lh61_apply_rotate(self, deg):
        return None
    if _lh61_prev_rotate_selected:
        return _lh61_prev_rotate_selected(self, deg)


def _lh61_flip_h(self):
    try:
        if self._selected_body_active():
            return _lh61_prev_flip_h(self) if _lh61_prev_flip_h else None
    except Exception:
        pass
    if _lh61_apply_flip(self, True):
        return None
    if _lh61_prev_flip_h:
        return _lh61_prev_flip_h(self)


def _lh61_flip_v(self):
    try:
        if self._selected_body_active():
            return _lh61_prev_flip_v(self) if _lh61_prev_flip_v else None
    except Exception:
        pass
    if _lh61_apply_flip(self, False):
        return None
    if _lh61_prev_flip_v:
        return _lh61_prev_flip_v(self)


def _lh61_remove_duplicate_group_toolbars(self):
    try:
        for tb in list(self.findChildren(QToolBar)):
            try:
                title = str(tb.windowTitle() or '')
                texts = [str(a.text() or '') for a in tb.actions()]
                if title == 'Graphic Group' or any('Group Graphics' in t or 'Ungroup' in t for t in texts):
                    self.removeToolBar(tb)
                    tb.deleteLater()
            except Exception:
                pass
    except Exception:
        pass


def _lh61_install_group_ui(self):
    if getattr(self, '_lh61_group_ui_installed', False):
        return
    self._lh61_group_ui_installed = True
    _lh61_remove_duplicate_group_toolbars(self)
    try:
        tb = self.addToolBar('Graphic Group')
        btn = QPushButton('Group Graphics')
        btn.setToolTip('Ausgewählte Grafikobjekte gruppieren (Ctrl+G)')
        btn.clicked.connect(self.group_selected_graphics)
        tb.addWidget(btn)
        btn = QPushButton('Ungroup Graphics')
        btn.setToolTip('Grafikgruppe aufheben (Ctrl+Shift+G)')
        btn.clicked.connect(self.ungroup_selected_graphics)
        tb.addWidget(btn)
    except Exception:
        pass


def _lh61_on_scene_selection_changed(self):
    try: _lh61_sync_group_selection(self)
    except Exception: pass
    try:
        return _lh59_prev_on_scene_selection_changed(self) if '_lh59_prev_on_scene_selection_changed' in globals() and _lh59_prev_on_scene_selection_changed else self.refresh_properties()
    except Exception:
        try: self.refresh_properties()
        except Exception: pass


try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.scale_selected_grid = _lh61_scale_selected_grid
        _cls.rotate_selected = _lh61_rotate_selected
        _cls.flip_selected_horizontal = _lh61_flip_h
        _cls.flip_selected_vertical = _lh61_flip_v
        _cls.group_selected_graphics = _lh61_group_selected_graphics
        _cls.ungroup_selected_graphics = _lh61_ungroup_selected_graphics
        if hasattr(_cls, 'on_scene_selection_changed'):
            _cls.on_scene_selection_changed = _lh61_on_scene_selection_changed
    if _lh61_prev_init is not None:
        def _lh61_init(self, *args, __old_init=_lh61_prev_init, **kwargs):
            __old_init(self, *args, **kwargs)
            try: _lh61_install_group_ui(self)
            except Exception: pass
        MainWindow.__init__ = _lh61_init
except Exception:
    pass

# ---------------------------------------------------------------------------
# SW72: graphic Flip-H/V axis correction + plain TEXT standalone selection/transform.
# ---------------------------------------------------------------------------
try:
    from PySide6.QtWidgets import QGraphicsItem as _SW72_QGraphicsItem
except Exception:
    _SW72_QGraphicsItem = None

def _sw72_selected_non_body_items(self):
    try:
        return [it for it in self.scene.selectedItems()
                if getattr(it, 'data', lambda *_: None)(0) != 'BODY'
                and not bool(getattr(getattr(it, 'model', None), '_is_attribute_text', False))]
    except Exception:
        return []

def _sw72_selected_graphic_models(self):
    try:
        return [getattr(it, 'model', None) for it in self.scene.selectedItems()
                if getattr(it, 'data', lambda *_: None)(0) == 'GRAPHIC'
                and getattr(it, 'model', None) is not None]
    except Exception:
        return []

try:
    _sw72_prev_flip_h = MainWindow.flip_selected_horizontal
    _sw72_prev_flip_v = MainWindow.flip_selected_vertical
    _sw72_prev_te_flip_h = TemplateEditorDialog.flip_selected_horizontal if 'TemplateEditorDialog' in globals() else None
    _sw72_prev_te_flip_v = TemplateEditorDialog.flip_selected_vertical if 'TemplateEditorDialog' in globals() else None
except Exception:
    _sw72_prev_flip_h = _sw72_prev_flip_v = _sw72_prev_te_flip_h = _sw72_prev_te_flip_v = None

def _sw72_flip_h(self):
    # For graphics the previous H/V mapping was inverted on the canvas.  Use the
    # opposite geometric axis for GRAPHIC-only/group selections while leaving BODY
    # transforms untouched. Plain TEXT falls through to the normal item-local path.
    try:
        if not self._selected_body_active() and _sw72_selected_graphic_models(self):
            if '_lh61_apply_flip' in globals() and _lh61_apply_flip(self, False):
                return None
    except Exception:
        pass
    return _sw72_prev_flip_h(self) if _sw72_prev_flip_h else None

def _sw72_flip_v(self):
    try:
        if not self._selected_body_active() and _sw72_selected_graphic_models(self):
            if '_lh61_apply_flip' in globals() and _lh61_apply_flip(self, True):
                return None
    except Exception:
        pass
    return _sw72_prev_flip_v(self) if _sw72_prev_flip_v else None

def _sw72_te_flip_h(self):
    try:
        if not self._selected_body_active() and _sw72_selected_graphic_models(self):
            if '_lh61_apply_flip' in globals() and _lh61_apply_flip(self, False):
                return None
    except Exception:
        pass
    return _sw72_prev_te_flip_h(self) if _sw72_prev_te_flip_h else None

def _sw72_te_flip_v(self):
    try:
        if not self._selected_body_active() and _sw72_selected_graphic_models(self):
            if '_lh61_apply_flip' in globals() and _lh61_apply_flip(self, True):
                return None
    except Exception:
        pass
    return _sw72_prev_te_flip_v(self) if _sw72_prev_te_flip_v else None

# Direct item-level graphic flips are also corrected for keyboard/context paths.
try:
    _sw72_old_g_flip_h = GraphicItem.flip_horizontal
    _sw72_old_g_flip_v = GraphicItem.flip_vertical
    def _sw72_graphic_flip_h(self):
        try:
            return _sw72_old_g_flip_v(self)
        except Exception:
            return None
    def _sw72_graphic_flip_v(self):
        try:
            return _sw72_old_g_flip_h(self)
        except Exception:
            return None
    GraphicItem.flip_horizontal = _sw72_graphic_flip_h
    GraphicItem.flip_vertical = _sw72_graphic_flip_v
except Exception:
    pass

# Plain TEXT must never be treated as BODY-owned attribute text.  This keeps it
# selectable/movable/rotatable/scalable as an independent canvas object.
try:
    _sw72_old_text_init = TextItem.__init__
    def _sw72_text_init(self, model, window):
        _sw72_old_text_init(self, model, window)
        try:
            if getattr(self, 'data', lambda *_: None)(0) == 'TEXT':
                setattr(self.model, '_is_attribute_text', False)
                if _SW72_QGraphicsItem is not None:
                    self.setFlag(_SW72_QGraphicsItem.ItemIsSelectable, True)
                    self.setFlag(_SW72_QGraphicsItem.ItemIsMovable, True)
                    self.setFlag(_SW72_QGraphicsItem.ItemIsFocusable, True)
        except Exception:
            pass
    TextItem.__init__ = _sw72_text_init
except Exception:
    pass

try:
    MainWindow.flip_selected_horizontal = _sw72_flip_h
    MainWindow.flip_selected_vertical = _sw72_flip_v
    if 'TemplateEditorDialog' in globals():
        TemplateEditorDialog.flip_selected_horizontal = _sw72_te_flip_h
        TemplateEditorDialog.flip_selected_vertical = _sw72_te_flip_v
except Exception:
    pass

# ---------------------------------------------------------------------------
# SW73: plain TEXT is a standalone canvas object, never part of BODY transforms.
# ---------------------------------------------------------------------------
# BODY-owned attribute texts (ATTR_REF_DES/ATTR_BODY) still follow the BODY.
# User-created plain TextModel objects in unit.texts must not be captured in the
# BODY transform base, nor scaled during BODY resize.  This prevents a plain text
# item from behaving as if it were attached to the selected BODY.
try:
    _sw73_prev_body_group_capture_base = MainWindow._body_group_capture_base
except Exception:
    _sw73_prev_body_group_capture_base = None

try:
    _sw73_prev_body_group_state = MainWindow._body_group_state
except Exception:
    _sw73_prev_body_group_state = None

try:
    _sw73_prev_scale_children_from_body_resize = MainWindow.scale_current_unit_children_from_body_resize
except Exception:
    _sw73_prev_scale_children_from_body_resize = None


def _sw73_strip_plain_texts_from_body_state(st):
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


def _sw73_body_group_capture_base(self, unit=None):
    if _sw73_prev_body_group_capture_base is None:
        return None
    st = _sw73_prev_body_group_capture_base(self, unit)
    return _sw73_strip_plain_texts_from_body_state(st)


def _sw73_body_group_state(self, unit=None):
    if _sw73_prev_body_group_state is None:
        return _sw73_body_group_capture_base(self, unit)
    st = _sw73_prev_body_group_state(self, unit)
    return _sw73_strip_plain_texts_from_body_state(st)


def _sw73_scale_current_unit_children_from_body_resize(self, start_state, body):
    # Reuse the existing BODY resize behaviour, but remove free/plain texts from
    # the resize state so they stay exactly where they are.  Attribute texts are
    # still passed via the separate 'attributes' entry.
    try:
        if isinstance(start_state, dict):
            start_state = dict(start_state)
            start_state['texts'] = []
    except Exception:
        pass
    if _sw73_prev_scale_children_from_body_resize is not None:
        return _sw73_prev_scale_children_from_body_resize(self, start_state, body)


try:
    MainWindow._body_group_capture_base = _sw73_body_group_capture_base
    MainWindow._body_group_state = _sw73_body_group_state
    MainWindow.scale_current_unit_children_from_body_resize = _sw73_scale_current_unit_children_from_body_resize
    if 'TemplateEditorDialog' in globals():
        TemplateEditorDialog._body_group_capture_base = _sw73_body_group_capture_base
        TemplateEditorDialog._body_group_state = _sw73_body_group_state
        TemplateEditorDialog.scale_current_unit_children_from_body_resize = _sw73_scale_current_unit_children_from_body_resize
except Exception:
    pass

# Make all existing/new plain text models explicitly free-standing on rebuild.
try:
    _sw73_prev_rebuild_scene = MainWindow.rebuild_scene
    def _sw73_rebuild_scene(self):
        try:
            for t in getattr(getattr(self, 'current_unit', None), 'texts', []) or []:
                setattr(t, '_is_attribute_text', False)
                setattr(t, '_attribute_key', '')
        except Exception:
            pass
        return _sw73_prev_rebuild_scene(self)
    MainWindow.rebuild_scene = _sw73_rebuild_scene
    if 'TemplateEditorDialog' in globals():
        _sw73_prev_te_rebuild_scene = TemplateEditorDialog.rebuild_scene
        def _sw73_te_rebuild_scene(self):
            try:
                for t in getattr(getattr(self, 'unit', None), 'texts', []) or []:
                    setattr(t, '_is_attribute_text', False)
                    setattr(t, '_attribute_key', '')
            except Exception:
                pass
            return _sw73_prev_te_rebuild_scene(self)
        TemplateEditorDialog.rebuild_scene = _sw73_te_rebuild_scene
except Exception:
    pass

# ---------------------------------------------------------------------------
# SW74: hard-separate plain TEXT from BODY ownership.
# ---------------------------------------------------------------------------
# Plain TEXT lives exclusively in unit.texts and must never move/rotate/flip/scale
# as a BODY child.  Only BODY attributes (ATTR_REF_DES/ATTR_BODY) and pin-owned
# attribute_texts follow their owning object.
try:
    _sw74_prev_move_current_unit_group = MainWindow.move_current_unit_group
except Exception:
    _sw74_prev_move_current_unit_group = None


def _sw74_move_current_unit_group(self, dx: float, dy: float, source_body=None):
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

try:
    MainWindow.move_current_unit_group = _sw74_move_current_unit_group
    if 'TemplateEditorDialog' in globals():
        TemplateEditorDialog.move_current_unit_group = _sw74_move_current_unit_group
except Exception:
    pass

# Remove plain texts from any already captured BODY transform state, every time.
try:
    _sw74_prev_body_group_capture_base = MainWindow._body_group_capture_base
    def _sw74_body_group_capture_base(self, unit=None):
        st = _sw74_prev_body_group_capture_base(self, unit)
        try:
            if isinstance(st, dict) and isinstance(st.get('base'), dict):
                st['base']['texts'] = []
        except Exception:
            pass
        return st
    MainWindow._body_group_capture_base = _sw74_body_group_capture_base
    if 'TemplateEditorDialog' in globals():
        TemplateEditorDialog._body_group_capture_base = _sw74_body_group_capture_base
except Exception:
    pass

try:
    _sw74_prev_body_group_state = MainWindow._body_group_state
    def _sw74_body_group_state(self, unit=None):
        st = _sw74_prev_body_group_state(self, unit)
        try:
            if isinstance(st, dict) and isinstance(st.get('base'), dict):
                st['base']['texts'] = []
        except Exception:
            pass
        return st
    MainWindow._body_group_state = _sw74_body_group_state
    if 'TemplateEditorDialog' in globals():
        TemplateEditorDialog._body_group_state = _sw74_body_group_state
except Exception:
    pass

try:
    _sw74_prev_scale_body_children = MainWindow.scale_current_unit_children_from_body_resize
    def _sw74_scale_current_unit_children_from_body_resize(self, start_state, body):
        try:
            if isinstance(start_state, dict):
                start_state = dict(start_state)
                start_state['texts'] = []
                if isinstance(start_state.get('base'), dict):
                    start_state['base'] = dict(start_state['base'])
                    start_state['base']['texts'] = []
        except Exception:
            pass
        return _sw74_prev_scale_body_children(self, start_state, body)
    MainWindow.scale_current_unit_children_from_body_resize = _sw74_scale_current_unit_children_from_body_resize
    if 'TemplateEditorDialog' in globals():
        TemplateEditorDialog.scale_current_unit_children_from_body_resize = _sw74_scale_current_unit_children_from_body_resize
except Exception:
    pass

# Newly inserted canvas TEXT should be explicitly free-standing and selected after rebuild.
try:
    _sw74_prev_select_model_after_rebuild = MainWindow.select_model_after_rebuild
    def _sw74_select_model_after_rebuild(self, model):
        try:
            if isinstance(getattr(self, '_selection_restore_ids', None), set):
                self._selection_restore_ids = {id(model)}
            else:
                self._selection_restore_ids = {id(model)}
            if hasattr(model, 'text') and hasattr(model, 'font_size_grid'):
                setattr(model, '_is_attribute_text', False)
                setattr(model, '_attribute_key', '')
        except Exception:
            pass
    MainWindow.select_model_after_rebuild = _sw74_select_model_after_rebuild
    if 'TemplateEditorDialog' in globals():
        TemplateEditorDialog.select_model_after_rebuild = _sw74_select_model_after_rebuild
except Exception:
    pass

# ---------------------------------------------------------------------------
# SW75: make plain TEXT truly standalone from BODY selection/transform.
# ---------------------------------------------------------------------------
# The remaining symptom was caused by BODY staying in the active selection when
# a free TextModel was selected/edited.  Any toolbar transform then went through
# the BODY-group path, which made the text appear BODY-linked.  Free text now
# wins the selection: BODY/attribute items are removed from selection and all
# transforms are applied only to selected free TEXT items.

def _sw75_is_free_text_item(it):
    try:
        return (getattr(it, 'data', lambda *_: None)(0) == 'TEXT'
                and getattr(it, 'model', None) is not None
                and not bool(getattr(it.model, '_is_attribute_text', False)))
    except Exception:
        return False

def _sw75_selected_free_text_items(self):
    try:
        return [it for it in self.scene.selectedItems() if _sw75_is_free_text_item(it)]
    except Exception:
        return []

try:
    _sw75_prev_on_sel = MainWindow.on_scene_selection_changed
except Exception:
    _sw75_prev_on_sel = None

def _sw75_on_scene_selection_changed(self):
    try:
        free_txt = _sw75_selected_free_text_items(self)
        if free_txt:
            # A plain text is a top-level object.  It must not share a selection
            # with BODY or BODY attribute text, otherwise BODY transforms capture it.
            self.scene.blockSignals(True)
            for it in list(self.scene.selectedItems()):
                k = getattr(it, 'data', lambda *_: None)(0)
                if k in ('BODY', 'ATTR_REF_DES', 'ATTR_BODY'):
                    it.setSelected(False)
            self.scene.blockSignals(False)
    except Exception:
        try: self.scene.blockSignals(False)
        except Exception: pass
    if _sw75_prev_on_sel:
        return _sw75_prev_on_sel(self)
    try:
        self.refresh_properties()
    except Exception:
        pass

try:
    MainWindow.on_scene_selection_changed = _sw75_on_scene_selection_changed
    if 'TemplateEditorDialog' in globals():
        _sw75_prev_te_on_sel = TemplateEditorDialog.on_scene_selection_changed
        def _sw75_te_on_scene_selection_changed(self):
            try:
                free_txt = _sw75_selected_free_text_items(self)
                if free_txt:
                    self.scene.blockSignals(True)
                    for it in list(self.scene.selectedItems()):
                        if getattr(it, 'data', lambda *_: None)(0) in ('BODY', 'ATTR_REF_DES', 'ATTR_BODY'):
                            it.setSelected(False)
                    self.scene.blockSignals(False)
            except Exception:
                try: self.scene.blockSignals(False)
                except Exception: pass
            return _sw75_prev_te_on_sel(self)
        TemplateEditorDialog.on_scene_selection_changed = _sw75_te_on_scene_selection_changed
except Exception:
    pass

# Treat BODY as active only if no free plain text is currently selected.
try:
    _sw75_prev_selected_body_active = MainWindow._selected_body_active
    def _sw75_selected_body_active(self):
        try:
            if _sw75_selected_free_text_items(self):
                return False
        except Exception:
            pass
        return _sw75_prev_selected_body_active(self)
    MainWindow._selected_body_active = _sw75_selected_body_active
    if 'TemplateEditorDialog' in globals() and hasattr(TemplateEditorDialog, '_selected_body_active'):
        _sw75_prev_te_selected_body_active = TemplateEditorDialog._selected_body_active
        def _sw75_te_selected_body_active(self):
            try:
                if _sw75_selected_free_text_items(self):
                    return False
            except Exception:
                pass
            return _sw75_prev_te_selected_body_active(self)
        TemplateEditorDialog._selected_body_active = _sw75_te_selected_body_active
except Exception:
    pass

# Clicking a free text object starts an exclusive selection unless Ctrl/Shift is held.
try:
    _sw75_prev_text_mouse_press = TextItem.mousePressEvent
    def _sw75_text_mouse_press(self, event):
        try:
            if _sw75_is_free_text_item(self) and event.button() == Qt.LeftButton:
                mods = event.modifiers()
                if not (mods & (Qt.ControlModifier | Qt.ShiftModifier)):
                    sc = self.scene()
                    if sc is not None:
                        sc.clearSelection()
                        self.setSelected(True)
        except Exception:
            pass
        return _sw75_prev_text_mouse_press(self, event)
    TextItem.mousePressEvent = _sw75_text_mouse_press
except Exception:
    pass

# Give TextItem the same toolbar entry point as GraphicItem for Scale +/- paths.
try:
    def _sw75_text_scale_by(self, factor):
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
    TextItem.scale_by = _sw75_text_scale_by
except Exception:
    pass

# Ensure property edits on BODY do not accidentally restore/carry selected text.
try:
    _sw75_prev_capture_selection_ids = MainWindow._capture_selection_ids
    def _sw75_capture_selection_ids(self):
        try:
            free = _sw75_selected_free_text_items(self)
            if free:
                return {id(it.model) for it in free}
        except Exception:
            pass
        return _sw75_prev_capture_selection_ids(self)
    MainWindow._capture_selection_ids = _sw75_capture_selection_ids
    if 'TemplateEditorDialog' in globals() and hasattr(TemplateEditorDialog, '_capture_selection_ids'):
        _sw75_prev_te_capture_selection_ids = TemplateEditorDialog._capture_selection_ids
        def _sw75_te_capture_selection_ids(self):
            try:
                free = _sw75_selected_free_text_items(self)
                if free:
                    return {id(it.model) for it in free}
            except Exception:
                pass
            return _sw75_prev_te_capture_selection_ids(self)
        TemplateEditorDialog._capture_selection_ids = _sw75_te_capture_selection_ids
except Exception:
    pass

# ---------------------------------------------------------------------------
# SW76: final hard fix for free/plain TEXT vs BODY transforms.
# ---------------------------------------------------------------------------
# A user-created TEXT object is a top-level canvas object.  It must never route
# toolbar transforms through the BODY transform path, even if BODY was selected
# before or if focus/selection temporarily changes while a toolbar button is
# clicked.  We keep an explicit active plain-text model and give plain TEXT
# exclusive transform handling.

def _sw76_unit_of(win):
    return getattr(win, 'current_unit', None) or getattr(win, 'unit', None)

def _sw76_is_plain_text_model(m):
    try:
        return (m is not None and hasattr(m, 'text') and hasattr(m, 'font_size_grid')
                and not bool(getattr(m, '_is_attribute_text', False)))
    except Exception:
        return False

def _sw76_is_plain_text_item(it):
    try:
        return (getattr(it, 'data', lambda *_: None)(0) == 'TEXT'
                and getattr(it, 'model', None) is not None
                and not bool(getattr(it.model, '_is_attribute_text', False)))
    except Exception:
        return False

def _sw76_find_plain_text_item_for_model(win, model):
    try:
        for it in win.scene.items():
            if _sw76_is_plain_text_item(it) and getattr(it, 'model', None) is model:
                return it
    except Exception:
        pass
    return None

def _sw76_selected_plain_text_items(win, allow_active=True):
    items = []
    try:
        items = [it for it in win.scene.selectedItems() if _sw76_is_plain_text_item(it)]
    except Exception:
        items = []
    if items:
        try:
            win._sw76_active_plain_text_model = getattr(items[0], 'model', None)
        except Exception:
            pass
        return items
    if allow_active:
        try:
            m = getattr(win, '_sw76_active_plain_text_model', None)
            it = _sw76_find_plain_text_item_for_model(win, m)
            if it is not None:
                return [it]
        except Exception:
            pass
    return []

def _sw76_plain_text_selection_active(win):
    try:
        return bool(_sw76_selected_plain_text_items(win, allow_active=True))
    except Exception:
        return False

# Mark new/existing unit.texts as explicit free objects before every scene rebuild.
try:
    _sw76_prev_rebuild_scene_mw = MainWindow.rebuild_scene
    def _sw76_rebuild_scene(self):
        try:
            u = _sw76_unit_of(self)
            for t in getattr(u, 'texts', []) or []:
                setattr(t, '_is_attribute_text', False)
                setattr(t, '_attribute_key', '')
        except Exception:
            pass
        return _sw76_prev_rebuild_scene_mw(self)
    MainWindow.rebuild_scene = _sw76_rebuild_scene
except Exception:
    pass

try:
    if 'TemplateEditorDialog' in globals():
        _sw76_prev_rebuild_scene_te = TemplateEditorDialog.rebuild_scene
        def _sw76_te_rebuild_scene(self):
            try:
                u = _sw76_unit_of(self)
                for t in getattr(u, 'texts', []) or []:
                    setattr(t, '_is_attribute_text', False)
                    setattr(t, '_attribute_key', '')
            except Exception:
                pass
            return _sw76_prev_rebuild_scene_te(self)
        TemplateEditorDialog.rebuild_scene = _sw76_te_rebuild_scene
except Exception:
    pass

# Plain text click = exclusive object selection.  Do not allow BODY to remain
# selected in parallel, because toolbar transforms otherwise use BODY path.
try:
    _sw76_prev_text_mouse_press = TextItem.mousePressEvent
    def _sw76_text_mouse_press(self, event):
        try:
            if _sw76_is_plain_text_item(self) and event.button() == Qt.LeftButton:
                win = getattr(self, 'window', None)
                if win is not None:
                    win._sw76_active_plain_text_model = self.model
                mods = event.modifiers()
                if not (mods & (Qt.ControlModifier | Qt.ShiftModifier)):
                    sc = self.scene()
                    if sc is not None:
                        sc.blockSignals(True)
                        try:
                            for it in list(sc.selectedItems()):
                                if it is not self:
                                    it.setSelected(False)
                            self.setSelected(True)
                        finally:
                            sc.blockSignals(False)
                        try:
                            win.refresh_properties()
                        except Exception:
                            pass
        except Exception:
            pass
        return _sw76_prev_text_mouse_press(self, event)
    TextItem.mousePressEvent = _sw76_text_mouse_press
except Exception:
    pass

# Keep selection clean after Qt emits selectionChanged.
def _sw76_clean_plain_text_selection(win):
    try:
        txt = [it for it in win.scene.selectedItems() if _sw76_is_plain_text_item(it)]
        if not txt:
            # If another real object is selected, the remembered text is no longer active.
            real = [it for it in win.scene.selectedItems() if getattr(it, 'data', lambda *_: None)(0) in ('BODY','PIN','GRAPHIC','ATTR_REF_DES','ATTR_BODY')]
            if real:
                win._sw76_active_plain_text_model = None
            return
        win._sw76_active_plain_text_model = getattr(txt[0], 'model', None)
        win.scene.blockSignals(True)
        try:
            for it in list(win.scene.selectedItems()):
                if not _sw76_is_plain_text_item(it):
                    it.setSelected(False)
        finally:
            win.scene.blockSignals(False)
    except Exception:
        try: win.scene.blockSignals(False)
        except Exception: pass

try:
    _sw76_prev_on_selection_mw = MainWindow.on_scene_selection_changed
    def _sw76_on_scene_selection_changed(self):
        _sw76_clean_plain_text_selection(self)
        return _sw76_prev_on_selection_mw(self)
    MainWindow.on_scene_selection_changed = _sw76_on_scene_selection_changed
except Exception:
    pass

try:
    if 'TemplateEditorDialog' in globals():
        _sw76_prev_on_selection_te = TemplateEditorDialog.on_scene_selection_changed
        def _sw76_te_on_scene_selection_changed(self):
            _sw76_clean_plain_text_selection(self)
            return _sw76_prev_on_selection_te(self)
        TemplateEditorDialog.on_scene_selection_changed = _sw76_te_on_scene_selection_changed
except Exception:
    pass

# BODY is never active while a free text item/model is active.
try:
    _sw76_prev_body_active_mw = MainWindow._selected_body_active
    def _sw76_selected_body_active(self):
        if _sw76_plain_text_selection_active(self):
            return False
        return _sw76_prev_body_active_mw(self)
    MainWindow._selected_body_active = _sw76_selected_body_active
except Exception:
    pass

try:
    if 'TemplateEditorDialog' in globals() and hasattr(TemplateEditorDialog, '_selected_body_active'):
        _sw76_prev_body_active_te = TemplateEditorDialog._selected_body_active
        def _sw76_te_selected_body_active(self):
            if _sw76_plain_text_selection_active(self):
                return False
            return _sw76_prev_body_active_te(self)
        TemplateEditorDialog._selected_body_active = _sw76_te_selected_body_active
except Exception:
    pass

def _sw76_refresh_text_items(win, items):
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

def _sw76_text_scale_grid(win, items, direction):
    try:
        step = float(win._edit_grid_step())
    except Exception:
        step = 0.1
    direction = 1 if int(direction) >= 0 else -1
    for it in items:
        m = getattr(it, 'model', None)
        if m is None:
            continue
        cur = float(getattr(m, 'font_size_grid', 0.75) or 0.75)
        new = max(step, round((cur + direction * step) / step) * step)
        m.font_size_grid = new
    _sw76_refresh_text_items(win, items)

try:
    _sw76_prev_rotate_mw = MainWindow.rotate_selected
    _sw76_prev_flip_h_mw = MainWindow.flip_selected_horizontal
    _sw76_prev_flip_v_mw = MainWindow.flip_selected_vertical
    _sw76_prev_scale_grid_mw = MainWindow.scale_selected_grid
    _sw76_prev_scale_mw = MainWindow.scale_selected

    def _sw76_rotate_selected(self, deg):
        items = _sw76_selected_plain_text_items(self, allow_active=True)
        if items:
            self.set_tool(DrawTool.SELECT.value)
            self.push_undo_state()
            for it in items:
                try: it.rotate_by(float(deg))
                except Exception: pass
            _sw76_refresh_text_items(self, items)
            self.dirty = True
            return None
        return _sw76_prev_rotate_mw(self, deg)

    def _sw76_flip_selected_horizontal(self):
        items = _sw76_selected_plain_text_items(self, allow_active=True)
        if items:
            self.set_tool(DrawTool.SELECT.value)
            self.push_undo_state()
            for it in items:
                try: it.flip_horizontal()
                except Exception: pass
            _sw76_refresh_text_items(self, items)
            self.dirty = True
            return None
        return _sw76_prev_flip_h_mw(self)

    def _sw76_flip_selected_vertical(self):
        items = _sw76_selected_plain_text_items(self, allow_active=True)
        if items:
            self.set_tool(DrawTool.SELECT.value)
            self.push_undo_state()
            for it in items:
                try: it.flip_vertical()
                except Exception: pass
            _sw76_refresh_text_items(self, items)
            self.dirty = True
            return None
        return _sw76_prev_flip_v_mw(self)

    def _sw76_scale_selected_grid(self, direction:int):
        items = _sw76_selected_plain_text_items(self, allow_active=True)
        if items:
            self.set_tool(DrawTool.SELECT.value)
            self.push_undo_state()
            _sw76_text_scale_grid(self, items, direction)
            self.dirty = True
            return None
        return _sw76_prev_scale_grid_mw(self, direction)

    def _sw76_scale_selected(self, factor):
        items = _sw76_selected_plain_text_items(self, allow_active=True)
        if items:
            direction = 1 if float(factor) >= 1.0 else -1
            return _sw76_scale_selected_grid(self, direction)
        return _sw76_prev_scale_mw(self, factor)

    MainWindow.rotate_selected = _sw76_rotate_selected
    MainWindow.flip_selected_horizontal = _sw76_flip_selected_horizontal
    MainWindow.flip_selected_vertical = _sw76_flip_selected_vertical
    MainWindow.scale_selected_grid = _sw76_scale_selected_grid
    MainWindow.scale_selected = _sw76_scale_selected
except Exception:
    pass

try:
    if 'TemplateEditorDialog' in globals():
        _sw76_prev_rotate_te = TemplateEditorDialog.rotate_selected
        _sw76_prev_flip_h_te = TemplateEditorDialog.flip_selected_horizontal
        _sw76_prev_flip_v_te = TemplateEditorDialog.flip_selected_vertical
        _sw76_prev_scale_grid_te = TemplateEditorDialog.scale_selected_grid
        _sw76_prev_scale_te = TemplateEditorDialog.scale_selected

        def _sw76_te_rotate_selected(self, deg):
            items = _sw76_selected_plain_text_items(self, allow_active=True)
            if items:
                self.set_tool(DrawTool.SELECT.value); self.push_undo_state()
                for it in items:
                    try: it.rotate_by(float(deg))
                    except Exception: pass
                _sw76_refresh_text_items(self, items); self.dirty = True; return None
            return _sw76_prev_rotate_te(self, deg)
        def _sw76_te_flip_selected_horizontal(self):
            items = _sw76_selected_plain_text_items(self, allow_active=True)
            if items:
                self.set_tool(DrawTool.SELECT.value); self.push_undo_state()
                for it in items:
                    try: it.flip_horizontal()
                    except Exception: pass
                _sw76_refresh_text_items(self, items); self.dirty = True; return None
            return _sw76_prev_flip_h_te(self)
        def _sw76_te_flip_selected_vertical(self):
            items = _sw76_selected_plain_text_items(self, allow_active=True)
            if items:
                self.set_tool(DrawTool.SELECT.value); self.push_undo_state()
                for it in items:
                    try: it.flip_vertical()
                    except Exception: pass
                _sw76_refresh_text_items(self, items); self.dirty = True; return None
            return _sw76_prev_flip_v_te(self)
        def _sw76_te_scale_selected_grid(self, direction:int):
            items = _sw76_selected_plain_text_items(self, allow_active=True)
            if items:
                self.set_tool(DrawTool.SELECT.value); self.push_undo_state()
                _sw76_text_scale_grid(self, items, direction); self.dirty = True; return None
            return _sw76_prev_scale_grid_te(self, direction)
        def _sw76_te_scale_selected(self, factor):
            items = _sw76_selected_plain_text_items(self, allow_active=True)
            if items:
                return _sw76_te_scale_selected_grid(self, 1 if float(factor) >= 1.0 else -1)
            return _sw76_prev_scale_te(self, factor)

        TemplateEditorDialog.rotate_selected = _sw76_te_rotate_selected
        TemplateEditorDialog.flip_selected_horizontal = _sw76_te_flip_selected_horizontal
        TemplateEditorDialog.flip_selected_vertical = _sw76_te_flip_selected_vertical
        TemplateEditorDialog.scale_selected_grid = _sw76_te_scale_selected_grid
        TemplateEditorDialog.scale_selected = _sw76_te_scale_selected
except Exception:
    pass

# v77: Runtime/UI references must never live on dataclass models, because undo/copy
# uses deepcopy and Qt/MainWindow objects are not pickleable/deepcopyable.
def _sw77_strip_runtime_refs(obj, seen=None):
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
                _sw77_strip_runtime_refs(v, seen)
        elif isinstance(obj, dict):
            for v in list(obj.values()): _sw77_strip_runtime_refs(v, seen)
        elif isinstance(obj, (list, tuple, set)):
            for v in list(obj): _sw77_strip_runtime_refs(v, seen)
    except Exception:
        pass

try:
    _sw77_prev_push_undo_mw = MainWindow.push_undo_state
    def _sw77_push_undo_state(self):
        try: _sw77_strip_runtime_refs(getattr(self, 'unit', None)); _sw77_strip_runtime_refs(getattr(self, 'current_unit', None)); _sw77_strip_runtime_refs(getattr(self, 'library', None))
        except Exception: pass
        return _sw77_prev_push_undo_mw(self)
    MainWindow.push_undo_state = _sw77_push_undo_state
except Exception:
    pass

try:
    if 'TemplateEditorDialog' in globals() and hasattr(TemplateEditorDialog, 'push_undo_state'):
        _sw77_prev_push_undo_te = TemplateEditorDialog.push_undo_state
        def _sw77_te_push_undo_state(self):
            try: _sw77_strip_runtime_refs(getattr(self, 'unit', None)); _sw77_strip_runtime_refs(getattr(self, 'current_unit', None)); _sw77_strip_runtime_refs(getattr(self, 'library', None))
            except Exception: pass
            return _sw77_prev_push_undo_te(self)
        TemplateEditorDialog.push_undo_state = _sw77_te_push_undo_state
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v80: real group graphic item.
# A graphic group is represented by one selectable GraphicItem-like proxy.  The
# proxy owns the full bounding-box hit area and delegates its exact movement,
# scaling, rotation and mirror operations to all child graphics.  Highlight
# items stay UI-only and are never part of the group selection/model.
# ---------------------------------------------------------------------------
try:
    from PySide6.QtCore import QPointF as _V80QPointF, QRectF as _V80QRectF, Qt as _V80Qt
    from PySide6.QtGui import QPen as _V80QPen, QBrush as _V80QBrush, QColor as _V80QColor, QCursor as _V80QCursor
    from PySide6.QtWidgets import QGraphicsItem as _V80QGraphicsItem, QMessageBox as _V80QMessageBox, QLabel as _V80QLabel, QToolBar as _V80QToolBar
    from symbol_wizard.graphics.items import _hit_handle as _v80_hit_handle, _corner_handles as _v80_corner_handles, _rotation_handle as _v80_rotation_handle, _cursor_for_handle as _v80_cursor_for_handle, _angle_from as _v80_angle_from
except Exception:
    pass


def _v80_step(win):
    try:
        return max(float(win._edit_grid_step()), 1e-9)
    except Exception:
        try:
            return max(float(getattr(win, 'edit_grid_px', 0.0) or 0.0) / max(float(getattr(win, 'grid_px', 1.0) or 1.0), 1e-9), 1e-9)
        except Exception:
            return 0.1


def _v80_snap(win, v):
    try:
        return float(win._snap_to_edit_grid(float(v), _v80_step(win)))
    except Exception:
        st = _v80_step(win)
        try: return round(float(v) / st) * st
        except Exception: return float(v)


def _v80_gid(gr):
    try:
        gid = str(getattr(gr, 'group_id', '') or '')
        if gid:
            return gid
        role = str(getattr(gr, 'graphic_role', '') or '')
        if role.startswith('user_graphic_group:'):
            return role.split(':', 1)[1]
    except Exception:
        pass
    return ''


def _v80_set_gid(gr, gid):
    try: gr.group_id = str(gid or '')
    except Exception: pass
    try: gr.graphic_role = ('user_graphic_group:' + str(gid)) if gid else 'user_graphic'
    except Exception: pass


def _v80_is_user_graphic(gr):
    try:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body', 'template_body', 'imported_body')
    except Exception:
        return False


def _v80_graphic_bounds(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    pts = [(x, y), (x + w, y - h)]
    try:
        if getattr(gr, 'ctrl_x', None) is not None and getattr(gr, 'ctrl_y', None) is not None:
            pts.append((x + float(gr.ctrl_x), y - float(gr.ctrl_y)))
    except Exception:
        pass
    try:
        cr = float(getattr(gr, 'curve_radius', 0.0) or 0.0)
        if abs(cr) > 1e-12:
            pts.append((x + w / 2.0, y - h / 2.0 + cr))
    except Exception:
        pass
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _v80_group_bbox(models):
    vals = [_v80_graphic_bounds(m) for m in models]
    if not vals:
        return (0.0, 0.0, 1.0, 1.0)
    return (min(v[0] for v in vals), min(v[1] for v in vals), max(v[2] for v in vals), max(v[3] for v in vals))


def _v80_current_unit(win):
    try: return win.current_unit()
    except Exception:
        try: return win.unit
        except Exception: return None


def _v80_group_map(win):
    unit = _v80_current_unit(win)
    out = {}
    for gr in list(getattr(unit, 'graphics', []) if unit is not None else []):
        try:
            if not _v80_is_user_graphic(gr):
                continue
            gid = _v80_gid(gr)
            if gid:
                out.setdefault(gid, []).append(gr)
        except Exception:
            pass
    return {k: v for k, v in out.items() if len(v) >= 1}


def _v80_scene_graphic_items(win):
    res = []
    try: items = list(win.scene.items())
    except Exception: items = []
    for it in items:
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None:
                res.append(it)
        except Exception:
            pass
    return res


def _v80_update_child_items(win, models):
    model_ids = {id(m) for m in models}
    gpx = float(getattr(win, 'grid_px', 40.0) or 40.0)
    for it in _v80_scene_graphic_items(win):
        try:
            if id(getattr(it, 'model', None)) in model_ids:
                it.prepareGeometryChange()
                it.setPos(float(it.model.x) * gpx, -float(it.model.y) * gpx)
                if hasattr(it, 'apply_transform_from_model'):
                    it.apply_transform_from_model()
                it.update()
        except Exception:
            pass
    try: win.scene.update()
    except Exception: pass


def _v80_affine_apply(models, start_states, old_bbox, new_bbox, win):
    ox0, oy0, ox1, oy1 = old_bbox
    nx0, ny0, nx1, ny1 = new_bbox
    ow = max(1e-9, ox1 - ox0); oh = max(1e-9, oy1 - oy0)
    sx = (nx1 - nx0) / ow; sy = (ny1 - ny0) / oh
    for gr, st in zip(models, start_states):
        try:
            x = st['x']; y = st['y']; w = st['w']; h = st['h']
            x2 = x + w; y2 = y - h
            gr.x = _v80_snap(win, nx0 + (x - ox0) * sx)
            gr.y = _v80_snap(win, ny0 + (y - oy0) * sy)
            ex = _v80_snap(win, nx0 + (x2 - ox0) * sx)
            ey = _v80_snap(win, ny0 + (y2 - oy0) * sy)
            gr.w = ex - gr.x
            gr.h = gr.y - ey
            if st.get('ctrl_x') is not None and st.get('ctrl_y') is not None:
                cx = nx0 + ((x + st['ctrl_x']) - ox0) * sx
                cy = ny0 + ((y - st['ctrl_y']) - oy0) * sy
                gr.ctrl_x = cx - gr.x
                gr.ctrl_y = gr.y - cy
            if st.get('curve_radius') not in (None, 0, 0.0):
                gr.curve_radius = st['curve_radius'] * ((abs(sx) + abs(sy)) / 2.0)
        except Exception:
            pass


def _v80_transform_models(models, op, value, win):
    if not models:
        return False
    x0, y0, x1, y1 = _v80_group_bbox(models)
    origin = (x0, y0)  # exact lower-left object origin, same for single/group vector object
    ox, oy = origin
    def tx_point(x, y):
        if op == 'move':
            dx, dy = value
            return x + dx, y + dy
        if op == 'flip_h':  # mirror at local Y-axis through origin: x changes
            return ox - (x - ox), y
        if op == 'flip_v':  # mirror at local X-axis through origin: y changes
            return x, oy - (y - oy)
        if op == 'rotate':
            a = math.radians(float(value))
            c, s = math.cos(a), math.sin(a)
            rx, ry = x - ox, y - oy
            return ox + rx * c - ry * s, oy + rx * s + ry * c
        if op == 'scale':
            f = float(value)
            return ox + (x - ox) * f, oy + (y - oy) * f
        return x, y
    for gr in models:
        try:
            x = float(getattr(gr, 'x', 0.0) or 0.0); y = float(getattr(gr, 'y', 0.0) or 0.0)
            w = float(getattr(gr, 'w', 0.0) or 0.0); h = float(getattr(gr, 'h', 0.0) or 0.0)
            ex, ey = x + w, y - h
            nx, ny = tx_point(x, y); nex, ney = tx_point(ex, ey)
            gr.x = _v80_snap(win, nx); gr.y = _v80_snap(win, ny)
            gr.w = _v80_snap(win, nex) - gr.x; gr.h = gr.y - _v80_snap(win, ney)
            if getattr(gr, 'ctrl_x', None) is not None and getattr(gr, 'ctrl_y', None) is not None:
                cx, cy = tx_point(x + float(gr.ctrl_x), y - float(gr.ctrl_y))
                gr.ctrl_x = cx - gr.x; gr.ctrl_y = gr.y - cy
            if op == 'scale' and getattr(gr, 'curve_radius', None) not in (None, 0, 0.0):
                gr.curve_radius = float(gr.curve_radius) * float(value)
        except Exception:
            pass
    return True


class _V80GroupGraphicItem(GraphicItem):
    """A real GraphicItem-compatible group shell with full rectangular hitbox."""
    def __init__(self, window, gid, models):
        self.group_id = gid
        self.models = list(models)
        x0, y0, x1, y1 = _v80_group_bbox(self.models)
        proxy = GraphicModel(shape='rect', x=x0, y=y1, w=max(_v80_step(window), x1-x0), h=max(_v80_step(window), y1-y0))
        proxy.graphic_role = 'group_proxy'
        proxy.group_id = gid
        proxy.style.stroke = (0, 120, 170)
        proxy.style.fill = None
        proxy.style.line_width = 0.03
        super().__init__(proxy, window)
        self.setData(0, 'GRAPHIC_GROUP')
        self.setZValue(100000)
        self.setAcceptedMouseButtons(_V80Qt.LeftButton)
        self.setFlag(_V80QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(_V80QGraphicsItem.ItemIsMovable, True)
        self.setFlag(_V80QGraphicsItem.ItemIsFocusable, True)
        self.setFlag(_V80QGraphicsItem.ItemSendsGeometryChanges, True)
        self._v80_moving = False
        self._v80_resizing = None
        self._v80_resize_start = None
        self._v80_rotating = False
        self._v80_rotate_center = _V80QPointF()
        self._v80_rotate_start = 0.0
        self._v80_last_rot = 0.0
        self._v80_sync_proxy_model()

    def _v80_sync_proxy_model(self):
        x0, y0, x1, y1 = _v80_group_bbox(self.models)
        st = _v80_step(self.window)
        self.model.x = x0
        self.model.y = y1
        self.model.w = max(st, x1 - x0)
        self.model.h = max(st, y1 - y0)
        g = float(getattr(self.window, 'grid_px', 40.0) or 40.0)
        self.prepareGeometryChange()
        self.setPos(self.model.x * g, -self.model.y * g)
        self.update()

    def paint(self, painter, option, widget=None):
        # Same visible affordance as a selected single graphic: one rectangular
        # outline, handles and rotation handle. Children draw the real artwork.
        r = self._rect()
        painter.save()
        if self.isSelected():
            painter.setPen(_V80QPen(_V80QColor(80, 80, 80), 1, _V80Qt.DashLine))
        else:
            painter.setPen(_V80QPen(_V80QColor(0, 0, 0, 0), 0))
        painter.setBrush(_V80QBrush(_V80Qt.NoBrush))
        painter.drawRect(r)
        if self.isSelected():
            painter.setBrush(_V80QBrush(_V80QColor(255, 255, 255)))
            for hr in self._handles().values():
                painter.drawRect(hr)
            painter.drawEllipse(_v80_rotation_handle(r, float(getattr(self.window, 'grid_px', 40.0) or 40.0) * self.rotate_handle_factor))
        painter.restore()

    def shape(self):
        # Full rectangle is clickable, not only child geometry.
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.addRect(self._rect())
        return path

    def hoverMoveEvent(self, event):
        if self.isSelected():
            h = 'rot' if _v80_rotation_handle(self._rect(), float(getattr(self.window, 'grid_px', 40.0) or 40.0) * self.rotate_handle_factor).contains(event.pos()) else _v80_hit_handle(self._handles(), event.pos())
            self.setCursor(_V80QCursor(_v80_cursor_for_handle(h)) if h else _V80QCursor(_V80Qt.ArrowCursor))
        else:
            self.setCursor(_V80QCursor(_V80Qt.ArrowCursor))
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == _V80Qt.LeftButton:
            try: self.window.push_undo_state()
            except Exception: pass
        if self.isSelected() and event.button() == _V80Qt.LeftButton:
            rot = _v80_rotation_handle(self._rect(), float(getattr(self.window, 'grid_px', 40.0) or 40.0) * self.rotate_handle_factor)
            if rot.contains(event.pos()):
                self._v80_rotating = True
                self._v80_rotate_center = self.mapToScene(_V80QPointF(0, self._rect().height()))
                self._v80_rotate_start = _v80_angle_from(self._v80_rotate_center, event.scenePos())
                self._v80_last_rot = 0.0
                event.accept(); return
            h = _v80_hit_handle(self._handles(), event.pos())
            if h:
                self._v80_resizing = h
                self._v80_resize_start = {
                    'bbox': _v80_group_bbox(self.models),
                    'states': [{
                        'x': float(getattr(m, 'x', 0.0) or 0.0), 'y': float(getattr(m, 'y', 0.0) or 0.0),
                        'w': float(getattr(m, 'w', 0.0) or 0.0), 'h': float(getattr(m, 'h', 0.0) or 0.0),
                        'ctrl_x': getattr(m, 'ctrl_x', None), 'ctrl_y': getattr(m, 'ctrl_y', None),
                        'curve_radius': float(getattr(m, 'curve_radius', 0.0) or 0.0),
                    } for m in self.models]
                }
                event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        g = float(getattr(self.window, 'grid_px', 40.0) or 40.0)
        if self._v80_rotating:
            delta = _v80_angle_from(self._v80_rotate_center, event.scenePos()) - self._v80_rotate_start
            step = round(delta / 15.0) * 15.0
            inc = step - self._v80_last_rot
            if abs(inc) > 1e-9:
                _v80_transform_models(self.models, 'rotate', inc, self.window)
                self._v80_last_rot = step
                _v80_update_child_items(self.window, self.models)
                self._v80_moving = True; self._v80_sync_proxy_model(); self._v80_moving = False
                try: self.window.refresh_properties()
                except Exception: pass
            event.accept(); return
        if self._v80_resizing and self._v80_resize_start:
            p = _V80QPointF(snap(event.scenePos().x(), float(getattr(self.window, 'edit_grid_px', g) or g)), snap(event.scenePos().y(), float(getattr(self.window, 'edit_grid_px', g) or g)))
            x0, y0, x1, y1 = self._v80_resize_start['bbox']
            left = x0 * g; right = x1 * g; top = -y1 * g; bottom = -y0 * g
            h = self._v80_resizing
            if h in ('l', 'tl', 'bl'): left = p.x()
            if h in ('r', 'tr', 'br'): right = p.x()
            if h in ('t', 'tl', 'tr'): top = p.y()
            if h in ('b', 'bl', 'br'): bottom = p.y()
            min_px = max(1.0, _v80_step(self.window) * g)
            if right < left: left, right = right, left
            if bottom < top: top, bottom = bottom, top
            if right - left < min_px:
                if h in ('l', 'tl', 'bl'): left = right - min_px
                else: right = left + min_px
            if bottom - top < min_px:
                if h in ('t', 'tl', 'tr'): top = bottom - min_px
                else: bottom = top + min_px
            new_bbox = (left / g, -bottom / g, right / g, -top / g)
            _v80_affine_apply(self.models, self._v80_resize_start['states'], self._v80_resize_start['bbox'], new_bbox, self.window)
            _v80_update_child_items(self.window, self.models)
            self._v80_moving = True; self._v80_sync_proxy_model(); self._v80_moving = False
            try: self.window.refresh_properties()
            except Exception: pass
            event.accept(); return
        super().mouseMoveEvent(event)

    def itemChange(self, change, value):
        if change == _V80QGraphicsItem.ItemPositionChange and self.scene():
            try:
                ep = float(getattr(self.window, 'edit_grid_px', getattr(self.window, 'grid_px', 40.0)) or 40.0)
                return _V80QPointF(snap(value.x(), ep), snap(value.y(), ep))
            except Exception:
                return value
        if change == _V80QGraphicsItem.ItemPositionHasChanged and self.scene() and not self._v80_moving and not self._v80_resizing and not self._v80_rotating:
            try:
                g = float(getattr(self.window, 'grid_px', 40.0) or 40.0)
                nx = self.pos().x() / g; ny = -self.pos().y() / g
                dx = nx - float(self.model.x); dy_top = ny - float(self.model.y)
                # model.y is top; grid y delta for all child anchors is same dy_top.
                if abs(dx) > 1e-9 or abs(dy_top) > 1e-9:
                    self._v80_moving = True
                    _v80_transform_models(self.models, 'move', (dx, dy_top), self.window)
                    _v80_update_child_items(self.window, self.models)
                    self._v80_sync_proxy_model()
                    self._v80_moving = False
                    try: self.window.notify_canvas_model_changed()
                    except Exception: pass
            except Exception:
                self._v80_moving = False
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        self._v80_resizing = None
        self._v80_resize_start = None
        self._v80_rotating = False
        self._v80_last_rot = 0.0
        try:
            self.window.dirty = True
            self.window._v80_restore_group_id = self.group_id
            self.window.rebuild_scene(); self.window.rebuild_tree(); self.window.refresh_properties()
        except Exception:
            pass
        super().mouseReleaseEvent(event)

    def scale_by(self, factor):
        _v80_transform_models(self.models, 'scale', float(factor), self.window)
        _v80_update_child_items(self.window, self.models)
        self._v80_moving = True; self._v80_sync_proxy_model(); self._v80_moving = False

    def rotate_by(self, deg):
        _v80_transform_models(self.models, 'rotate', float(deg), self.window)
        _v80_update_child_items(self.window, self.models)
        self._v80_moving = True; self._v80_sync_proxy_model(); self._v80_moving = False

    def flip_horizontal(self):
        _v80_transform_models(self.models, 'flip_h', None, self.window)
        _v80_update_child_items(self.window, self.models)
        self._v80_moving = True; self._v80_sync_proxy_model(); self._v80_moving = False

    def flip_vertical(self):
        _v80_transform_models(self.models, 'flip_v', None, self.window)
        _v80_update_child_items(self.window, self.models)
        self._v80_moving = True; self._v80_sync_proxy_model(); self._v80_moving = False

    def update_model_pos(self):
        # handled by itemChange; do not let TransformMixin write into proxy only
        return


def _v80_selected_group_item(win):
    try:
        for it in win.scene.selectedItems():
            if getattr(it, 'data', lambda *_: None)(0) == 'GRAPHIC_GROUP':
                return it
    except Exception:
        pass
    return None


def _v80_selected_graphic_models(win):
    models = []
    seen = set()
    try: items = list(win.scene.selectedItems())
    except Exception: items = []
    for it in items:
        try:
            if it.data(0) == 'GRAPHIC_GROUP':
                for m in getattr(it, 'models', []) or []:
                    if id(m) not in seen:
                        models.append(m); seen.add(id(m))
            elif it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None:
                m = it.model
                if _v80_is_user_graphic(m) and id(m) not in seen:
                    models.append(m); seen.add(id(m))
        except Exception:
            pass
    return models


def _v80_harden_children(win):
    grouped_ids = set()
    for models in _v80_group_map(win).values():
        grouped_ids.update(id(m) for m in models)
    for it in _v80_scene_graphic_items(win):
        try:
            if id(it.model) in grouped_ids:
                it.setSelected(False)
                it.setFlag(_V80QGraphicsItem.ItemIsSelectable, False)
                it.setFlag(_V80QGraphicsItem.ItemIsMovable, False)
                it.setFlag(_V80QGraphicsItem.ItemIsFocusable, False)
                it.setAcceptedMouseButtons(_V80Qt.NoButton)
            elif _v80_is_user_graphic(it.model):
                it.setFlag(_V80QGraphicsItem.ItemIsSelectable, True)
                it.setFlag(_V80QGraphicsItem.ItemIsMovable, True)
                it.setFlag(_V80QGraphicsItem.ItemIsFocusable, True)
                it.setAcceptedMouseButtons(_V80Qt.LeftButton)
        except Exception:
            pass


try:
    _v80_prev_rebuild_scene = MainWindow.rebuild_scene
except Exception:
    _v80_prev_rebuild_scene = None
try:
    _v80_prev_refresh_properties = MainWindow.refresh_properties
except Exception:
    _v80_prev_refresh_properties = None
try:
    _v80_prev_scale_grid = MainWindow.scale_selected_grid
    _v80_prev_rotate = MainWindow.rotate_selected
    _v80_prev_flip_h = MainWindow.flip_selected_horizontal
    _v80_prev_flip_v = MainWindow.flip_selected_vertical
except Exception:
    _v80_prev_scale_grid = _v80_prev_rotate = _v80_prev_flip_h = _v80_prev_flip_v = None


def _v80_rebuild_scene(self):
    restore_gid = getattr(self, '_v80_restore_group_id', '') or ''
    if not restore_gid:
        try:
            sg = _v80_selected_group_item(self)
            restore_gid = getattr(sg, 'group_id', '') if sg is not None else ''
        except Exception:
            restore_gid = ''
    if _v80_prev_rebuild_scene:
        _v80_prev_rebuild_scene(self)
    try:
        _v80_harden_children(self)
        for gid, models in _v80_group_map(self).items():
            proxy = _V80GroupGraphicItem(self, gid, models)
            self.scene.addItem(proxy)
            if gid == restore_gid:
                proxy.setSelected(True)
        self._v80_restore_group_id = ''
    except Exception as e:
        try: self.statusBar().showMessage(f'Group proxy error: {e}', 5000)
        except Exception: pass


def _v80_group_selected_graphics(self):
    models = _v80_selected_graphic_models(self)
    # If already selecting a group, keep it as one object; no nested group.
    if len(models) < 2:
        try: _V80QMessageBox.information(self, 'Group Graphics', 'Bitte mindestens zwei Grafikobjekte auswählen.')
        except Exception: pass
        return
    import uuid
    gid = 'grp_' + uuid.uuid4().hex[:10]
    try: self.push_undo_state()
    except Exception: pass
    for m in models:
        _v80_set_gid(m, gid)
    try:
        self._v80_restore_group_id = gid
        self.dirty = True
        self.rebuild_scene(); self.rebuild_tree(); self.refresh_properties()
    except Exception:
        pass


def _v80_ungroup_selected_graphics(self):
    models = _v80_selected_graphic_models(self)
    if not models:
        return
    try: self.push_undo_state()
    except Exception: pass
    for m in models:
        _v80_set_gid(m, '')
    try:
        self.dirty = True
        self.rebuild_scene(); self.rebuild_tree(); self.refresh_properties()
    except Exception:
        pass


def _v80_scale_selected_grid(self, direction:int):
    gi = _v80_selected_group_item(self)
    if gi is not None:
        try: self.push_undo_state()
        except Exception: pass
        bbox = _v80_group_bbox(gi.models)
        w = max(1e-9, bbox[2] - bbox[0]); h = max(1e-9, bbox[3] - bbox[1])
        st = _v80_step(self)
        # same grid-step behavior as a single rectangle: grow/shrink both axes
        f = min(max(st, w + (st if int(direction) > 0 else -st)) / w,
                max(st, h + (st if int(direction) > 0 else -st)) / h)
        gi.scale_by(f)
        try:
            self._v80_restore_group_id = gi.group_id
            self.dirty = True
            self.rebuild_scene(); self.rebuild_tree(); self.refresh_properties()
        except Exception: pass
        return None
    return _v80_prev_scale_grid(self, direction) if _v80_prev_scale_grid else None


def _v80_rotate_selected(self, deg):
    gi = _v80_selected_group_item(self)
    if gi is not None:
        try: self.push_undo_state()
        except Exception: pass
        gi.rotate_by(float(deg))
        try:
            self._v80_restore_group_id = gi.group_id
            self.dirty = True
            self.rebuild_scene(); self.rebuild_tree(); self.refresh_properties()
        except Exception: pass
        return None
    return _v80_prev_rotate(self, deg) if _v80_prev_rotate else None


def _v80_flip_h(self):
    gi = _v80_selected_group_item(self)
    if gi is not None:
        try: self.push_undo_state()
        except Exception: pass
        gi.flip_horizontal()
        try:
            self._v80_restore_group_id = gi.group_id
            self.dirty = True
            self.rebuild_scene(); self.rebuild_tree(); self.refresh_properties()
        except Exception: pass
        return None
    return _v80_prev_flip_h(self) if _v80_prev_flip_h else None


def _v80_flip_v(self):
    gi = _v80_selected_group_item(self)
    if gi is not None:
        try: self.push_undo_state()
        except Exception: pass
        gi.flip_vertical()
        try:
            self._v80_restore_group_id = gi.group_id
            self.dirty = True
            self.rebuild_scene(); self.rebuild_tree(); self.refresh_properties()
        except Exception: pass
        return None
    return _v80_prev_flip_v(self) if _v80_prev_flip_v else None


def _v80_refresh_properties(self):
    try:
        gi = _v80_selected_group_item(self)
        if gi is not None and hasattr(self, 'form') and self.form is not None:
            while self.form.rowCount(): self.form.removeRow(0)
            self.form.addRow(_V80QLabel('<b>Selected: GRAPHIC</b>'))
            self.form.addRow(_V80QLabel('Grouped object'))
            self.form.addRow(_V80QLabel('Verhält sich wie ein einzelnes Grafikobjekt.'))
            return
    except Exception:
        pass
    return _v80_prev_refresh_properties(self) if _v80_prev_refresh_properties else None


def _v80_remove_duplicate_group_ui(self):
    try:
        for tb in list(self.findChildren(_V80QToolBar)):
            try:
                title = str(tb.windowTitle() or '')
                texts = [str(a.text() or '') for a in tb.actions()]
                if title == 'Graphic Group' or any(('Group Graphics' in t or 'Ungroup' in t) for t in texts):
                    self.removeToolBar(tb); tb.deleteLater()
            except Exception:
                pass
    except Exception:
        pass
    try:
        edit = None
        for a in self.menuBar().actions():
            if str(a.text()).replace('&','').lower().startswith('edit'):
                edit = a.menu(); break
        if edit is not None:
            seen = set()
            for a in list(edit.actions()):
                t = str(a.text() or '')
                if 'Group Graphics' in t or 'Ungroup' in t:
                    if t in seen:
                        edit.removeAction(a)
                    seen.add(t)
    except Exception:
        pass


try:
    MainWindow.rebuild_scene = _v80_rebuild_scene
    MainWindow.group_selected_graphics = _v80_group_selected_graphics
    MainWindow.ungroup_selected_graphics = _v80_ungroup_selected_graphics
    MainWindow.scale_selected_grid = _v80_scale_selected_grid
    MainWindow.rotate_selected = _v80_rotate_selected
    MainWindow.flip_selected_horizontal = _v80_flip_h
    MainWindow.flip_selected_vertical = _v80_flip_v
    MainWindow.refresh_properties = _v80_refresh_properties
    _v80_old_init = MainWindow.__init__
    def _v80_init(self, *a, **kw):
        _v80_old_init(self, *a, **kw)
        try: _v80_remove_duplicate_group_ui(self)
        except Exception: pass
        try:
            tb = self.addToolBar('Graphic Group')
            b = QPushButton('Group Graphics'); b.clicked.connect(self.group_selected_graphics); tb.addWidget(b)
            b = QPushButton('Ungroup Graphics'); b.clicked.connect(self.ungroup_selected_graphics); tb.addWidget(b)
        except Exception: pass
    MainWindow.__init__ = _v80_init
except Exception:
    pass

# ---------------------------------------------------------------------------
# V81: real vector-group correction
# The V80 group shell was usable as a hitbox, but its bbox/transform math still
# used only a diagonal.  After flip/rotate this loses negative extents and makes
# the outline/pivot wrong.  This patch keeps the public V80 hooks but replaces
# bbox + group transforms with full-corner vector math around one stable local
# lower-left group origin.

def _v81_graphic_corners(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    return [(x, y), (x + w, y), (x, y - h), (x + w, y - h)]


def _v81_graphic_bounds(gr):
    pts = list(_v81_graphic_corners(gr))
    try:
        if getattr(gr, 'ctrl_x', None) is not None and getattr(gr, 'ctrl_y', None) is not None:
            x = float(getattr(gr, 'x', 0.0) or 0.0)
            y = float(getattr(gr, 'y', 0.0) or 0.0)
            pts.append((x + float(gr.ctrl_x), y - float(gr.ctrl_y)))
    except Exception:
        pass
    try:
        # Be conservative for curved lines: include a small radius envelope so
        # the selectable outline never cuts through the visual curve.
        cr = abs(float(getattr(gr, 'curve_radius', 0.0) or 0.0))
        if cr > 1e-12:
            x = float(getattr(gr, 'x', 0.0) or 0.0)
            y = float(getattr(gr, 'y', 0.0) or 0.0)
            w = float(getattr(gr, 'w', 0.0) or 0.0)
            h = float(getattr(gr, 'h', 0.0) or 0.0)
            pts.extend([(x + w * 0.5, y - h * 0.5 + cr), (x + w * 0.5, y - h * 0.5 - cr)])
    except Exception:
        pass
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _v81_group_bbox(models):
    vals = [_v81_graphic_bounds(m) for m in (models or [])]
    if not vals:
        return (0.0, 0.0, 1.0, 1.0)
    return (min(v[0] for v in vals), min(v[1] for v in vals), max(v[2] for v in vals), max(v[3] for v in vals))


def _v81_capture_states(models):
    out = []
    for m in models or []:
        out.append({
            'x': float(getattr(m, 'x', 0.0) or 0.0),
            'y': float(getattr(m, 'y', 0.0) or 0.0),
            'w': float(getattr(m, 'w', 0.0) or 0.0),
            'h': float(getattr(m, 'h', 0.0) or 0.0),
            'ctrl_x': getattr(m, 'ctrl_x', None),
            'ctrl_y': getattr(m, 'ctrl_y', None),
            'curve_radius': float(getattr(m, 'curve_radius', 0.0) or 0.0),
        })
    return out


def _v81_apply_states(models, states, tx, win, radius_factor=1.0):
    # Apply the same affine transform to every child's local vectors.  Only snap
    # after the common transform, so child offsets remain proportional instead of
    # drifting independently during group operations.
    for gr, st in zip(models or [], states or []):
        try:
            x = st['x']; y = st['y']; w = st['w']; h = st['h']
            p0 = tx(x, y)
            p1 = tx(x + w, y - h)
            gr.x = _v80_snap(win, p0[0]); gr.y = _v80_snap(win, p0[1])
            ex = _v80_snap(win, p1[0]); ey = _v80_snap(win, p1[1])
            gr.w = ex - gr.x; gr.h = gr.y - ey
            if st.get('ctrl_x') is not None and st.get('ctrl_y') is not None:
                cp = tx(x + float(st['ctrl_x']), y - float(st['ctrl_y']))
                gr.ctrl_x = _v80_snap(win, cp[0]) - gr.x
                gr.ctrl_y = gr.y - _v80_snap(win, cp[1])
            if st.get('curve_radius') not in (None, 0, 0.0):
                gr.curve_radius = float(st['curve_radius']) * float(radius_factor)
        except Exception:
            pass


def _v81_transform_models(models, op, value, win, bbox=None, states=None):
    models = list(models or [])
    if not models:
        return False
    bbox = bbox or _v81_group_bbox(models)
    states = states or _v81_capture_states(models)
    x0, y0, x1, y1 = bbox
    ox, oy = x0, y0  # lower-left group origin, same rule as a single graphic object
    radius_factor = 1.0
    if op == 'move':
        dx, dy = value
        def tx(x, y): return (x + dx, y + dy)
    elif op == 'flip_h':
        def tx(x, y): return (ox - (x - ox), y)
    elif op == 'flip_v':
        def tx(x, y): return (x, oy - (y - oy))
    elif op == 'rotate':
        a = math.radians(float(value)); c, s = math.cos(a), math.sin(a)
        def tx(x, y):
            rx, ry = x - ox, y - oy
            return (ox + rx * c - ry * s, oy + rx * s + ry * c)
    elif op == 'scale':
        f = float(value); radius_factor = abs(f)
        def tx(x, y): return (ox + (x - ox) * f, oy + (y - oy) * f)
    else:
        return False
    _v81_apply_states(models, states, tx, win, radius_factor=radius_factor)
    return True


def _v81_affine_apply(models, start_states, old_bbox, new_bbox, win):
    ox0, oy0, ox1, oy1 = old_bbox
    nx0, ny0, nx1, ny1 = new_bbox
    ow = max(1e-9, ox1 - ox0); oh = max(1e-9, oy1 - oy0)
    sx = (nx1 - nx0) / ow; sy = (ny1 - ny0) / oh
    radius_factor = (abs(sx) + abs(sy)) / 2.0
    def tx(x, y):
        return (nx0 + (x - ox0) * sx, ny0 + (y - oy0) * sy)
    _v81_apply_states(models, start_states, tx, win, radius_factor=radius_factor)


# Replace V80 helper functions used dynamically by the V80 proxy class.
_v80_graphic_bounds = _v81_graphic_bounds
_v80_group_bbox = _v81_group_bbox
_v80_transform_models = _v81_transform_models
_v80_affine_apply = _v81_affine_apply


# Patch the V80 proxy behavior in place so rebuild_scene keeps using the same
# class name but with corrected origin/resize-state logic.
def _v81_group_mouse_press(self, event):
    if event.button() == _V80Qt.LeftButton:
        try: self.window.push_undo_state()
        except Exception: pass
    if self.isSelected() and event.button() == _V80Qt.LeftButton:
        rot = _v80_rotation_handle(self._rect(), float(getattr(self.window, 'grid_px', 40.0) or 40.0) * self.rotate_handle_factor)
        if rot.contains(event.pos()):
            self._v80_rotating = True
            self._v80_rotate_center = self.mapToScene(_V80QPointF(0, self._rect().height()))
            self._v80_rotate_start = _v80_angle_from(self._v80_rotate_center, event.scenePos())
            self._v80_last_rot = 0.0
            self._v81_rotate_bbox = _v81_group_bbox(self.models)
            self._v81_rotate_states = _v81_capture_states(self.models)
            event.accept(); return
        h = _v80_hit_handle(self._handles(), event.pos())
        if h:
            self._v80_resizing = h
            self._v80_resize_start = {'bbox': _v81_group_bbox(self.models), 'states': _v81_capture_states(self.models)}
            event.accept(); return
    return GraphicItem.mousePressEvent(self, event)


def _v81_group_mouse_move(self, event):
    g = float(getattr(self.window, 'grid_px', 40.0) or 40.0)
    if self._v80_rotating:
        delta = _v80_angle_from(self._v80_rotate_center, event.scenePos()) - self._v80_rotate_start
        step = round(delta / 15.0) * 15.0
        if abs(step - self._v80_last_rot) > 1e-9:
            # Re-apply from original press states. This avoids cumulative rounding drift.
            _v81_transform_models(self.models, 'rotate', step, self.window,
                                  bbox=getattr(self, '_v81_rotate_bbox', None),
                                  states=getattr(self, '_v81_rotate_states', None))
            self._v80_last_rot = step
            _v80_update_child_items(self.window, self.models)
            self._v80_moving = True; self._v80_sync_proxy_model(); self._v80_moving = False
            try: self.window.refresh_properties()
            except Exception: pass
        event.accept(); return
    if self._v80_resizing and self._v80_resize_start:
        p = _V80QPointF(snap(event.scenePos().x(), float(getattr(self.window, 'edit_grid_px', g) or g)),
                        snap(event.scenePos().y(), float(getattr(self.window, 'edit_grid_px', g) or g)))
        x0, y0, x1, y1 = self._v80_resize_start['bbox']
        left = x0 * g; right = x1 * g; top = -y1 * g; bottom = -y0 * g
        h = self._v80_resizing
        if h in ('l', 'tl', 'bl'): left = p.x()
        if h in ('r', 'tr', 'br'): right = p.x()
        if h in ('t', 'tl', 'tr'): top = p.y()
        if h in ('b', 'bl', 'br'): bottom = p.y()
        min_px = max(1.0, _v80_step(self.window) * g)
        # Prevent crossing handles; keep the opposite side stable.
        if right - left < min_px:
            if h in ('l', 'tl', 'bl'): left = right - min_px
            else: right = left + min_px
        if bottom - top < min_px:
            if h in ('t', 'tl', 'tr'): top = bottom - min_px
            else: bottom = top + min_px
        new_bbox = (left / g, -bottom / g, right / g, -top / g)
        _v81_affine_apply(self.models, self._v80_resize_start['states'], self._v80_resize_start['bbox'], new_bbox, self.window)
        _v80_update_child_items(self.window, self.models)
        self._v80_moving = True; self._v80_sync_proxy_model(); self._v80_moving = False
        try: self.window.refresh_properties()
        except Exception: pass
        event.accept(); return
    return GraphicItem.mouseMoveEvent(self, event)


def _v81_group_scale_by(self, factor):
    bbox = _v81_group_bbox(self.models)
    states = _v81_capture_states(self.models)
    _v81_transform_models(self.models, 'scale', float(factor), self.window, bbox=bbox, states=states)
    _v80_update_child_items(self.window, self.models)
    self._v80_moving = True; self._v80_sync_proxy_model(); self._v80_moving = False


def _v81_group_rotate_by(self, deg):
    bbox = _v81_group_bbox(self.models)
    states = _v81_capture_states(self.models)
    _v81_transform_models(self.models, 'rotate', float(deg), self.window, bbox=bbox, states=states)
    _v80_update_child_items(self.window, self.models)
    self._v80_moving = True; self._v80_sync_proxy_model(); self._v80_moving = False


def _v81_group_flip_h(self):
    bbox = _v81_group_bbox(self.models)
    states = _v81_capture_states(self.models)
    _v81_transform_models(self.models, 'flip_h', None, self.window, bbox=bbox, states=states)
    _v80_update_child_items(self.window, self.models)
    self._v80_moving = True; self._v80_sync_proxy_model(); self._v80_moving = False


def _v81_group_flip_v(self):
    bbox = _v81_group_bbox(self.models)
    states = _v81_capture_states(self.models)
    _v81_transform_models(self.models, 'flip_v', None, self.window, bbox=bbox, states=states)
    _v80_update_child_items(self.window, self.models)
    self._v80_moving = True; self._v80_sync_proxy_model(); self._v80_moving = False


try:
    _V80GroupGraphicItem.mousePressEvent = _v81_group_mouse_press
    _V80GroupGraphicItem.mouseMoveEvent = _v81_group_mouse_move
    _V80GroupGraphicItem.scale_by = _v81_group_scale_by
    _V80GroupGraphicItem.rotate_by = _v81_group_rotate_by
    _V80GroupGraphicItem.flip_horizontal = _v81_group_flip_h
    _V80GroupGraphicItem.flip_vertical = _v81_group_flip_v
except Exception:
    pass


def _v81_remove_all_group_ui_duplicates(self):
    # Remove every old toolbar/menu occurrence and create exactly one clean entry.
    try:
        for tb in list(self.findChildren(_V80QToolBar)):
            try:
                title = str(tb.windowTitle() or '')
                texts = [str(a.text() or '') for a in tb.actions()]
                if title == 'Graphic Group' or any(('Group Graphics' in t or 'Ungroup' in t) for t in texts):
                    self.removeToolBar(tb); tb.deleteLater()
            except Exception:
                pass
    except Exception:
        pass
    try:
        edit = None
        for a in self.menuBar().actions():
            if str(a.text()).replace('&','').strip().lower().startswith('edit'):
                edit = a.menu(); break
        if edit is not None:
            for a in list(edit.actions()):
                t = str(a.text() or '')
                key = t.replace('&','').strip().lower()
                if 'group graphics' in key or 'ungroup graphics' in key:
                    edit.removeAction(a)
            a_group = QAction('Group Graphics', self); a_group.triggered.connect(self.group_selected_graphics); edit.addAction(a_group)
            a_ungroup = QAction('Ungroup Graphics', self); a_ungroup.triggered.connect(self.ungroup_selected_graphics); edit.addAction(a_ungroup)
    except Exception:
        pass
    try:
        tb = self.addToolBar('Graphic Group')
        b = QPushButton('Group Graphics'); b.clicked.connect(self.group_selected_graphics); tb.addWidget(b)
        b = QPushButton('Ungroup Graphics'); b.clicked.connect(self.ungroup_selected_graphics); tb.addWidget(b)
    except Exception:
        pass


try:
    _v81_old_init = MainWindow.__init__
    def _v81_init(self, *a, **kw):
        _v81_old_init(self, *a, **kw)
        try: _v81_remove_all_group_ui_duplicates(self)
        except Exception: pass
    MainWindow.__init__ = _v81_init
except Exception:
    pass

# ---------------------------------------------------------------------------
# V82: group transform equals single graphic transform semantics.
# A grouped selection is a vector object.  The group proxy is only the visible /
# selectable rectangular shell; all contained graphics keep local geometry and
# are transformed by moving/scaling/rotating their own model center exactly like
# standalone GraphicItem objects (rotation/scale_x/scale_y are preserved and
# updated instead of rebuilding children from one diagonal).  This prevents
# child objects from drifting apart and keeps the group outline around the real
# transformed extents.
# ---------------------------------------------------------------------------

def _v82_f(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)


def _v82_child_state(m):
    x = _v82_f(getattr(m, 'x', 0.0), 0.0)
    y = _v82_f(getattr(m, 'y', 0.0), 0.0)
    w = _v82_f(getattr(m, 'w', 0.0), 0.0)
    h = _v82_f(getattr(m, 'h', 0.0), 0.0)
    return {
        'x': x, 'y': y, 'w': w, 'h': h,
        'cx': x + w / 2.0, 'cy': y - h / 2.0,
        'rotation': _v82_f(getattr(m, 'rotation', 0.0), 0.0),
        'scale_x': _v82_f(getattr(m, 'scale_x', 1.0), 1.0),
        'scale_y': _v82_f(getattr(m, 'scale_y', 1.0), 1.0),
        'ctrl_x': getattr(m, 'ctrl_x', None),
        'ctrl_y': getattr(m, 'ctrl_y', None),
        'curve_radius': _v82_f(getattr(m, 'curve_radius', 0.0), 0.0),
    }


def _v82_capture_states(models):
    return [_v82_child_state(m) for m in (models or [])]


def _v82_set_from_center(m, cx, cy, w, h):
    m.w = float(w)
    m.h = float(h)
    m.x = float(cx) - float(w) / 2.0
    m.y = float(cy) + float(h) / 2.0


def _v82_rot_point(px, py, ox, oy, deg):
    a = math.radians(float(deg)); c = math.cos(a); s = math.sin(a)
    rx, ry = px - ox, py - oy
    return ox + rx * c - ry * s, oy + rx * s + ry * c


def _v82_graphic_bounds(gr):
    """Actual visual bbox of a GraphicModel including rotation and mirroring.

    GraphicItem uses lower-left transform origin since v68, so the model-space
    object corners must be transformed around bottom-left, not around center.
    The result is the same rectangular envelope a selected standalone graphic
    visually occupies on the canvas.
    """
    x = _v82_f(getattr(gr, 'x', 0.0), 0.0)
    y = _v82_f(getattr(gr, 'y', 0.0), 0.0)
    w = _v82_f(getattr(gr, 'w', 0.0), 0.0)
    h = _v82_f(getattr(gr, 'h', 0.0), 0.0)
    sx = _v82_f(getattr(gr, 'scale_x', 1.0), 1.0)
    sy = _v82_f(getattr(gr, 'scale_y', 1.0), 1.0)
    rot = _v82_f(getattr(gr, 'rotation', 0.0), 0.0)
    # lower-left origin in model coordinates: (x, y-h)
    ox, oy = x, y - h
    base = [(x, y), (x + w, y), (x, y - h), (x + w, y - h)]
    pts = []
    for px, py in base:
        # Convert to local lower-left, apply scale_x/scale_y like QTransform,
        # then rotate around the same point.
        lx, ly = px - ox, py - oy
        qx, qy = ox + lx * sx, oy + ly * sy
        pts.append(_v82_rot_point(qx, qy, ox, oy, rot))
    try:
        if getattr(gr, 'ctrl_x', None) is not None and getattr(gr, 'ctrl_y', None) is not None:
            px = x + _v82_f(getattr(gr, 'ctrl_x', 0.0), 0.0)
            py = y - _v82_f(getattr(gr, 'ctrl_y', 0.0), 0.0)
            lx, ly = px - ox, py - oy
            pts.append(_v82_rot_point(ox + lx * sx, oy + ly * sy, ox, oy, rot))
    except Exception:
        pass
    try:
        cr = abs(_v82_f(getattr(gr, 'curve_radius', 0.0), 0.0))
        if cr > 1e-12:
            # Conservative curve envelope: transformed midpoint +/- radius.
            for sign in (-1.0, 1.0):
                px = x + w * 0.5
                py = y - h * 0.5 + sign * cr
                lx, ly = px - ox, py - oy
                pts.append(_v82_rot_point(ox + lx * sx, oy + ly * sy, ox, oy, rot))
    except Exception:
        pass
    xs = [p[0] for p in pts] or [x]
    ys = [p[1] for p in pts] or [y]
    return (min(xs), min(ys), max(xs), max(ys))


def _v82_group_bbox(models):
    vals = [_v82_graphic_bounds(m) for m in (models or [])]
    if not vals:
        return (0.0, 0.0, 1.0, 1.0)
    return (min(v[0] for v in vals), min(v[1] for v in vals), max(v[2] for v in vals), max(v[3] for v in vals))


def _v82_apply_group_transform(models, op, value, win, bbox=None, states=None):
    models = list(models or [])
    if not models:
        return False
    states = states or _v82_capture_states(models)
    bbox = bbox or _v82_group_bbox(models)
    x0, y0, x1, y1 = bbox
    ox, oy = x0, y0  # group lower-left, identical rule to the fixed single graphic pivot
    for m, st in zip(models, states):
        try:
            cx, cy = st['cx'], st['cy']
            w, h = st['w'], st['h']
            rot = st['rotation']
            scx = st['scale_x']; scy = st['scale_y']
            radius_factor = 1.0
            if op == 'move':
                dx, dy = value
                ncx, ncy = cx + float(dx), cy + float(dy)
            elif op == 'rotate':
                deg = float(value)
                ncx, ncy = _v82_rot_point(cx, cy, ox, oy, deg)
                rot = (rot + deg) % 360.0
            elif op == 'flip_h':
                ncx, ncy = ox - (cx - ox), cy
                scx = -scx
            elif op == 'flip_v':
                ncx, ncy = cx, oy - (cy - oy)
                scy = -scy
            elif op == 'scale':
                f = float(value)
                ncx, ncy = ox + (cx - ox) * f, oy + (cy - oy) * f
                w = max(1e-9, abs(w * f)); h = max(1e-9, abs(h * f))
                radius_factor = abs(f)
                try:
                    if st.get('ctrl_x') is not None: m.ctrl_x = _v82_f(st['ctrl_x']) * f
                    if st.get('ctrl_y') is not None: m.ctrl_y = _v82_f(st['ctrl_y']) * f
                except Exception:
                    pass
            else:
                return False
            _v82_set_from_center(m, ncx, ncy, w, h)
            try: m.rotation = rot
            except Exception: pass
            try: m.scale_x = scx
            except Exception: pass
            try: m.scale_y = scy
            except Exception: pass
            try:
                if op == 'scale' and st.get('curve_radius') not in (None, 0, 0.0):
                    m.curve_radius = float(st['curve_radius']) * radius_factor
            except Exception:
                pass
        except Exception:
            pass
    return True


def _v82_affine_apply(models, start_states, old_bbox, new_bbox, win):
    """Resize group like one rectangular vector object.

    The bbox side/handle operation defines one common affine map.  Child centers
    and child dimensions are transformed by this single map; rotations and
    flips stay on the child models.  No per-child grid snapping is performed,
    because snapping children individually is exactly what made grouped geometry
    drift apart in previous builds.
    """
    ox0, oy0, ox1, oy1 = old_bbox
    nx0, ny0, nx1, ny1 = new_bbox
    ow = max(1e-9, ox1 - ox0); oh = max(1e-9, oy1 - oy0)
    sx = (nx1 - nx0) / ow
    sy = (ny1 - ny0) / oh
    for m, st in zip(models or [], start_states or []):
        try:
            cx = nx0 + (st['cx'] - ox0) * sx
            cy = ny0 + (st['cy'] - oy0) * sy
            w = max(1e-9, abs(st['w'] * sx))
            h = max(1e-9, abs(st['h'] * sy))
            _v82_set_from_center(m, cx, cy, w, h)
            try: m.rotation = st['rotation']
            except Exception: pass
            try: m.scale_x = st['scale_x'] * (1.0 if sx >= 0 else -1.0)
            except Exception: pass
            try: m.scale_y = st['scale_y'] * (1.0 if sy >= 0 else -1.0)
            except Exception: pass
            try:
                if st.get('ctrl_x') is not None: m.ctrl_x = _v82_f(st['ctrl_x']) * sx
                if st.get('ctrl_y') is not None: m.ctrl_y = _v82_f(st['ctrl_y']) * sy
                if st.get('curve_radius') not in (None, 0, 0.0):
                    m.curve_radius = float(st['curve_radius']) * ((abs(sx) + abs(sy)) / 2.0)
            except Exception:
                pass
        except Exception:
            pass


# Override all dynamic group helper functions used by the V80/V81 proxy.
try:
    _v80_graphic_bounds = _v82_graphic_bounds
    _v80_group_bbox = _v82_group_bbox
    _v80_transform_models = _v82_apply_group_transform
    _v80_affine_apply = _v82_affine_apply
    _v81_graphic_bounds = _v82_graphic_bounds
    _v81_group_bbox = _v82_group_bbox
    _v81_capture_states = _v82_capture_states
    _v81_transform_models = _v82_apply_group_transform
    _v81_affine_apply = _v82_affine_apply
except Exception:
    pass


def _v82_group_mouse_press(self, event):
    if event.button() == _V80Qt.LeftButton:
        try: self.window.push_undo_state()
        except Exception: pass
    if self.isSelected() and event.button() == _V80Qt.LeftButton:
        rot = _v80_rotation_handle(self._rect(), float(getattr(self.window, 'grid_px', 40.0) or 40.0) * self.rotate_handle_factor)
        if rot.contains(event.pos()):
            self._v80_rotating = True
            # same transform point as single graphics after v68: lower-left of proxy rect
            self._v80_rotate_center = self.mapToScene(_V80QPointF(0, self._rect().height()))
            self._v80_rotate_start = _v80_angle_from(self._v80_rotate_center, event.scenePos())
            self._v80_last_rot = 0.0
            self._v82_rotate_bbox = _v82_group_bbox(self.models)
            self._v82_rotate_states = _v82_capture_states(self.models)
            event.accept(); return
        h = _v80_hit_handle(self._handles(), event.pos())
        if h:
            self._v80_resizing = h
            self._v80_resize_start = {'bbox': _v82_group_bbox(self.models), 'states': _v82_capture_states(self.models)}
            event.accept(); return
    return GraphicItem.mousePressEvent(self, event)


def _v82_group_mouse_move(self, event):
    g = float(getattr(self.window, 'grid_px', 40.0) or 40.0)
    if getattr(self, '_v80_rotating', False):
        delta = _v80_angle_from(self._v80_rotate_center, event.scenePos()) - self._v80_rotate_start
        step = round(delta / 15.0) * 15.0
        if abs(step - self._v80_last_rot) > 1e-9:
            _v82_apply_group_transform(self.models, 'rotate', step, self.window,
                                       bbox=getattr(self, '_v82_rotate_bbox', None),
                                       states=getattr(self, '_v82_rotate_states', None))
            self._v80_last_rot = step
            _v80_update_child_items(self.window, self.models)
            self._v80_moving = True; self._v80_sync_proxy_model(); self._v80_moving = False
            try: self.window.refresh_properties()
            except Exception: pass
        event.accept(); return
    if getattr(self, '_v80_resizing', None) and getattr(self, '_v80_resize_start', None):
        p = _V80QPointF(snap(event.scenePos().x(), float(getattr(self.window, 'edit_grid_px', g) or g)),
                        snap(event.scenePos().y(), float(getattr(self.window, 'edit_grid_px', g) or g)))
        x0, y0, x1, y1 = self._v80_resize_start['bbox']
        left = x0 * g; right = x1 * g; top = -y1 * g; bottom = -y0 * g
        hname = self._v80_resizing
        if hname in ('l', 'tl', 'bl'): left = p.x()
        if hname in ('r', 'tr', 'br'): right = p.x()
        if hname in ('t', 'tl', 'tr'): top = p.y()
        if hname in ('b', 'bl', 'br'): bottom = p.y()
        min_px = max(1.0, _v80_step(self.window) * g)
        # Do not allow handle crossing; this matches current single-object min behaviour.
        if right - left < min_px:
            if hname in ('l', 'tl', 'bl'): left = right - min_px
            else: right = left + min_px
        if bottom - top < min_px:
            if hname in ('t', 'tl', 'tr'): top = bottom - min_px
            else: bottom = top + min_px
        new_bbox = (left / g, -bottom / g, right / g, -top / g)
        _v82_affine_apply(self.models, self._v80_resize_start['states'], self._v80_resize_start['bbox'], new_bbox, self.window)
        _v80_update_child_items(self.window, self.models)
        self._v80_moving = True; self._v80_sync_proxy_model(); self._v80_moving = False
        try: self.window.refresh_properties()
        except Exception: pass
        event.accept(); return
    return GraphicItem.mouseMoveEvent(self, event)


def _v82_group_scale_by(self, factor):
    bbox = _v82_group_bbox(self.models)
    states = _v82_capture_states(self.models)
    _v82_apply_group_transform(self.models, 'scale', float(factor), self.window, bbox=bbox, states=states)
    _v80_update_child_items(self.window, self.models)
    self._v80_moving = True; self._v80_sync_proxy_model(); self._v80_moving = False


def _v82_group_rotate_by(self, deg):
    bbox = _v82_group_bbox(self.models)
    states = _v82_capture_states(self.models)
    _v82_apply_group_transform(self.models, 'rotate', float(deg), self.window, bbox=bbox, states=states)
    _v80_update_child_items(self.window, self.models)
    self._v80_moving = True; self._v80_sync_proxy_model(); self._v80_moving = False


def _v82_group_flip_h(self):
    bbox = _v82_group_bbox(self.models)
    states = _v82_capture_states(self.models)
    _v82_apply_group_transform(self.models, 'flip_h', None, self.window, bbox=bbox, states=states)
    _v80_update_child_items(self.window, self.models)
    self._v80_moving = True; self._v80_sync_proxy_model(); self._v80_moving = False


def _v82_group_flip_v(self):
    bbox = _v82_group_bbox(self.models)
    states = _v82_capture_states(self.models)
    _v82_apply_group_transform(self.models, 'flip_v', None, self.window, bbox=bbox, states=states)
    _v80_update_child_items(self.window, self.models)
    self._v80_moving = True; self._v80_sync_proxy_model(); self._v80_moving = False

try:
    _V80GroupGraphicItem.mousePressEvent = _v82_group_mouse_press
    _V80GroupGraphicItem.mouseMoveEvent = _v82_group_mouse_move
    _V80GroupGraphicItem.scale_by = _v82_group_scale_by
    _V80GroupGraphicItem.rotate_by = _v82_group_rotate_by
    _V80GroupGraphicItem.flip_horizontal = _v82_group_flip_h
    _V80GroupGraphicItem.flip_vertical = _v82_group_flip_v
except Exception:
    pass


def _v82_remove_group_ui_duplicates(self):
    # One toolbar + one Edit entry pair only.
    try:
        for tb in list(self.findChildren(_V80QToolBar)):
            try:
                title = str(tb.windowTitle() or '')
                texts = [str(a.text() or '') for a in tb.actions()]
                if title == 'Graphic Group' or any(('Group Graphics' in t or 'Ungroup Graphics' in t) for t in texts):
                    self.removeToolBar(tb); tb.deleteLater()
            except Exception:
                pass
    except Exception:
        pass
    try:
        edit = None
        for a in self.menuBar().actions():
            if str(a.text()).replace('&','').strip().lower().startswith('edit'):
                edit = a.menu(); break
        if edit is not None:
            for a in list(edit.actions()):
                key = str(a.text() or '').replace('&','').strip().lower()
                if 'group graphics' in key or 'ungroup graphics' in key:
                    edit.removeAction(a)
            ag = QAction('Group Graphics', self); ag.setShortcut(QKeySequence('Ctrl+G')); ag.triggered.connect(self.group_selected_graphics); edit.addAction(ag)
            au = QAction('Ungroup Graphics', self); au.setShortcut(QKeySequence('Ctrl+Shift+G')); au.triggered.connect(self.ungroup_selected_graphics); edit.addAction(au)
    except Exception:
        pass
    try:
        tb = self.addToolBar('Graphic Group')
        b = QPushButton('Group Graphics'); b.clicked.connect(self.group_selected_graphics); tb.addWidget(b)
        b = QPushButton('Ungroup Graphics'); b.clicked.connect(self.ungroup_selected_graphics); tb.addWidget(b)
    except Exception:
        pass

try:
    _v82_old_init = MainWindow.__init__
    def _v82_init(self, *a, **kw):
        _v82_old_init(self, *a, **kw)
        try: _v82_remove_group_ui_duplicates(self)
        except Exception: pass
    MainWindow.__init__ = _v82_init
except Exception:
    pass

# ---------------------------------------------------------------------------
# V84: remove grouping feature completely from user-facing UI/commands.
# Requested: no Group/Ungroup entries in Ribbon/toolbars, Edit menu, shortcuts
# or context entry points.  Keep legacy data fields harmless, but make the
# commands inert and remove all actions after the older monkey patches finished
# building the window.
# ---------------------------------------------------------------------------
def _v84_action_is_grouping(action):
    try:
        text = str(action.text() or '').replace('&', '').strip().lower()
    except Exception:
        text = ''
    try:
        tip = str(action.toolTip() or '').lower()
    except Exception:
        tip = ''
    try:
        sc = action.shortcut().toString()
    except Exception:
        sc = ''
    blob = ' '.join([text, tip, sc]).lower()
    if sc in ('Ctrl+G', 'Ctrl+Shift+G'):
        return True
    return ('group graphics' in blob or 'ungroup graphics' in blob or
            text in ('group', 'ungroup') or 'grafikgruppe' in blob)


def _v84_widget_text_is_grouping(widget):
    try:
        txt = str(widget.text() or '').replace('&', '').strip().lower()
    except Exception:
        txt = ''
    try:
        tip = str(widget.toolTip() or '').lower()
    except Exception:
        tip = ''
    blob = (txt + ' ' + tip).lower()
    return ('group graphics' in blob or 'ungroup graphics' in blob or
            txt in ('group', 'ungroup') or 'grafikgruppe' in blob)


def _v84_remove_grouping_ui(self):
    # Remove toolbar actions/buttons and complete grouping toolbars.
    try:
        for tb in list(self.findChildren(QToolBar)):
            remove_toolbar = False
            try:
                title = str(tb.windowTitle() or '').replace('&', '').strip().lower()
                if title in ('graphic group', 'group', 'grouping') or 'graphic group' in title:
                    remove_toolbar = True
            except Exception:
                pass
            try:
                for action in list(tb.actions()):
                    if _v84_action_is_grouping(action):
                        remove_toolbar = True
                        try: tb.removeAction(action)
                        except Exception: pass
                    try:
                        w = tb.widgetForAction(action)
                        if w is not None and _v84_widget_text_is_grouping(w):
                            remove_toolbar = True
                            try: tb.removeAction(action)
                            except Exception: pass
                            try: w.deleteLater()
                            except Exception: pass
                    except Exception:
                        pass
            except Exception:
                pass
            if remove_toolbar:
                try: self.removeToolBar(tb)
                except Exception: pass
                try: tb.deleteLater()
                except Exception: pass
    except Exception:
        pass

    # Remove menu actions everywhere, especially Edit.
    try:
        def clean_menu(menu):
            try:
                for action in list(menu.actions()):
                    try:
                        sub = action.menu()
                        if sub is not None:
                            clean_menu(sub)
                    except Exception:
                        pass
                    if _v84_action_is_grouping(action):
                        try: menu.removeAction(action)
                        except Exception: pass
            except Exception:
                pass
        mb = self.menuBar()
        for top in list(mb.actions()):
            try:
                m = top.menu()
                if m is not None:
                    clean_menu(m)
            except Exception:
                pass
    except Exception:
        pass

    # Remove application/window-level shortcuts and actions.
    try:
        for action in list(self.actions()):
            if _v84_action_is_grouping(action):
                try: self.removeAction(action)
                except Exception: pass
    except Exception:
        pass


def _v84_grouping_disabled(self, *args, **kwargs):
    try:
        self.statusBar().showMessage('Grouping ist in dieser Version deaktiviert.', 3000)
    except Exception:
        pass
    return None


try:
    MainWindow.group_selected_graphics = _v84_grouping_disabled
    MainWindow.ungroup_selected_graphics = _v84_grouping_disabled
except Exception:
    pass

try:
    _v84_old_init = MainWindow.__init__
    def _v84_init(self, *args, **kwargs):
        _v84_old_init(self, *args, **kwargs)
        try:
            _v84_remove_grouping_ui(self)
        except Exception:
            pass
    MainWindow.__init__ = _v84_init
except Exception:
    pass

# ---------------------------------------------------------------------------
# SW86: BODY canvas scaling is BODY-only.
# ---------------------------------------------------------------------------
# A BODY resize must not behave like a generic vector-group scale. Only the
# BODY geometry (and imported/template graphics that are explicitly part of the
# BODY) is scaled. Pins are re-docked to the new BODY edges and vertically /
# horizontally centered/distributed. Text/attributes keep font and spacing and
# are only translated by the BODY's top-left movement delta.

def _sw86_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)


def _sw86_body_grid_step(self):
    try:
        return max(1e-9, float(self._edit_grid_step()))
    except Exception:
        try:
            return max(1e-9, float(getattr(getattr(self, 'symbol', None), 'grid_inch', 0.1) or 0.1))
        except Exception:
            return 0.1


def _sw86_snap(self, v):
    step = _sw86_body_grid_step(self)
    try:
        return round(float(v) / step) * step
    except Exception:
        return float(v)


def _sw86_is_body_graphic(g):
    try:
        role = str(getattr(g, 'graphic_role', '') or '').lower()
        return bool(getattr(g, 'locked_to_body', False)) or role in ('body', 'template_body', 'imported_body')
    except Exception:
        return False


def _sw86_move_pin_texts_keep_offsets(p, old_px, old_py, new_px, new_py):
    dx = float(new_px) - float(old_px)
    dy = float(new_py) - float(old_py)
    try:
        if getattr(p, 'label_x', None) is not None:
            p.label_x = _sw86_float(p.label_x) + dx
        if getattr(p, 'label_y', None) is not None:
            p.label_y = _sw86_float(p.label_y) + dy
        if getattr(p, 'number_x', None) is not None:
            p.number_x = _sw86_float(p.number_x) + dx
        if getattr(p, 'number_y', None) is not None:
            p.number_y = _sw86_float(p.number_y) + dy
        for tm in (getattr(p, 'attribute_texts', {}) or {}).values():
            try:
                tm.x = _sw86_float(tm.x) + dx
                tm.y = _sw86_float(tm.y) + dy
            except Exception:
                pass
    except Exception:
        pass


def _sw86_redock_pins_to_body(self, start_state, body):
    try:
        pins = list(getattr(getattr(self, 'current_unit', None), 'pins', []) or [])
    except Exception:
        pins = []
    if not pins:
        return
    left = [p for p in pins if str(getattr(p, 'side', 'left')) == PinSide.LEFT.value]
    right = [p for p in pins if str(getattr(p, 'side', 'left')) == PinSide.RIGHT.value]
    top = [p for p in pins if str(getattr(p, 'side', 'left')) == PinSide.TOP.value]
    bottom = [p for p in pins if str(getattr(p, 'side', 'left')) == PinSide.BOTTOM.value]
    old_pos = {}
    try:
        for entry in (start_state or {}).get('pins', []) or []:
            if len(entry) >= 3:
                old_pos[entry[0]] = (_sw86_float(entry[1]), _sw86_float(entry[2]))
    except Exception:
        pass
    bx = _sw86_float(getattr(body, 'x', 0.0))
    by = _sw86_float(getattr(body, 'y', 0.0))
    bw = max(_sw86_body_grid_step(self), abs(_sw86_float(getattr(body, 'width', 0.0))))
    bh = max(_sw86_body_grid_step(self), abs(_sw86_float(getattr(body, 'height', 0.0))))
    cx = bx + bw / 2.0
    cy = by - bh / 2.0

    def place_vertical(group, x):
        n = len(group)
        if n <= 0:
            return
        # One pin is exactly centered. Multiple pins are distributed symmetrically
        # inside the BODY height, without scaling pin length or text.
        for i, p in enumerate(group):
            if n == 1:
                y = cy
            else:
                y = by - ((i + 1) * bh / (n + 1))
            old_px, old_py = old_pos.get(p, (_sw86_float(getattr(p, 'x', x)), _sw86_float(getattr(p, 'y', y))))
            nx, ny = _sw86_snap(self, x), _sw86_snap(self, y)
            p.x, p.y = nx, ny
            _sw86_move_pin_texts_keep_offsets(p, old_px, old_py, nx, ny)

    def place_horizontal(group, y):
        n = len(group)
        if n <= 0:
            return
        for i, p in enumerate(group):
            if n == 1:
                x = cx
            else:
                x = bx + ((i + 1) * bw / (n + 1))
            old_px, old_py = old_pos.get(p, (_sw86_float(getattr(p, 'x', x)), _sw86_float(getattr(p, 'y', y))))
            nx, ny = _sw86_snap(self, x), _sw86_snap(self, y)
            p.x, p.y = nx, ny
            _sw86_move_pin_texts_keep_offsets(p, old_px, old_py, nx, ny)

    place_vertical(left, bx)
    place_vertical(right, bx + bw)
    place_horizontal(top, by)
    place_horizontal(bottom, by - bh)


def _sw86_scale_current_unit_children_from_body_resize(self, start_state, body):
    start_state = start_state if isinstance(start_state, dict) else {}
    old_x = _sw86_float(start_state.get('x', getattr(body, 'x', 0.0)))
    old_y = _sw86_float(start_state.get('y', getattr(body, 'y', 0.0)))
    old_w = max(1e-9, abs(_sw86_float(start_state.get('w', getattr(body, 'width', 1.0)), 1.0)))
    old_h = max(1e-9, abs(_sw86_float(start_state.get('h', getattr(body, 'height', 1.0)), 1.0)))
    new_x = _sw86_snap(self, getattr(body, 'x', old_x))
    new_y = _sw86_snap(self, getattr(body, 'y', old_y))
    new_w = max(_sw86_body_grid_step(self), _sw86_snap(self, abs(_sw86_float(getattr(body, 'width', old_w), old_w))))
    new_h = max(_sw86_body_grid_step(self), _sw86_snap(self, abs(_sw86_float(getattr(body, 'height', old_h), old_h))))
    body.x, body.y, body.width, body.height = new_x, new_y, new_w, new_h
    dx = new_x - old_x
    dy = new_y - old_y
    sx = new_w / old_w
    sy = new_h / old_h

    # Pins are never scaled. They are re-docked to the BODY edges and centered /
    # distributed on those edges.
    _sw86_redock_pins_to_body(self, start_state, body)

    # Free text is not BODY-owned. BODY attributes are only translated as a block;
    # font size, rotation and inter-line spacing remain unchanged.
    for t, tx, ty in start_state.get('texts', []) or []:
        try:
            t.x = _sw86_snap(self, _sw86_float(tx) + dx)
            t.y = _sw86_snap(self, _sw86_float(ty) + dy)
        except Exception:
            pass
    for t, tx, ty in start_state.get('attributes', []) or []:
        try:
            t.x = _sw86_snap(self, _sw86_float(tx) + dx)
            t.y = _sw86_snap(self, _sw86_float(ty) + dy)
        except Exception:
            pass

    # Only graphics explicitly belonging to the imported/template BODY are scaled.
    # User graphics remain standalone objects.
    for gr, gx, gy, gw, gh in start_state.get('graphics', []) or []:
        try:
            if not _sw86_is_body_graphic(gr):
                continue
            gr.x = _sw86_snap(self, new_x + (_sw86_float(gx) - old_x) * sx)
            gr.y = _sw86_snap(self, new_y + (_sw86_float(gy) - old_y) * sy)
            gr.w = _sw86_snap(self, _sw86_float(gw) * sx)
            gr.h = _sw86_snap(self, _sw86_float(gh) * sy)
        except Exception:
            pass


def _sw86_snapshot_body_resize_state(self, body=None):
    try:
        u = self.current_unit
        b = body or u.body
        return {
            'x': _sw86_float(getattr(b, 'x', 0.0)),
            'y': _sw86_float(getattr(b, 'y', 0.0)),
            'w': _sw86_float(getattr(b, 'width', 1.0), 1.0),
            'h': _sw86_float(getattr(b, 'height', 1.0), 1.0),
            'pins': [(p, _sw86_float(getattr(p, 'x', 0.0)), _sw86_float(getattr(p, 'y', 0.0)), _sw86_float(getattr(p, 'length', 1.0), 1.0)) for p in getattr(u, 'pins', []) or []],
            'texts': [],
            'attributes': [(t, _sw86_float(getattr(t, 'x', 0.0)), _sw86_float(getattr(t, 'y', 0.0))) for t in (getattr(getattr(u, 'body', None), 'attribute_texts', {}) or {}).values()],
            'graphics': [(gr, _sw86_float(getattr(gr, 'x', 0.0)), _sw86_float(getattr(gr, 'y', 0.0)), _sw86_float(getattr(gr, 'w', 0.0)), _sw86_float(getattr(gr, 'h', 0.0))) for gr in getattr(u, 'graphics', []) or []],
        }
    except Exception:
        return {}

try:
    _sw86_prev_transform_unit_as_body_group = MainWindow._transform_unit_as_body_group
except Exception:
    _sw86_prev_transform_unit_as_body_group = None


def _sw86_transform_unit_as_body_group(self, op, value=None, refresh=True):
    # Scale is BODY-only. Rotate/flip keep the existing stable behaviour.
    if op not in ('scale', 'scale_x_to', 'scale_y_to'):
        if _sw86_prev_transform_unit_as_body_group is not None:
            return _sw86_prev_transform_unit_as_body_group(self, op, value, refresh)
        return None
    try:
        u = self.current_unit
        body = u.body
        st = _sw86_snapshot_body_resize_state(self, body)
        old_w = max(_sw86_body_grid_step(self), _sw86_float(st.get('w', body.width), body.width))
        old_h = max(_sw86_body_grid_step(self), _sw86_float(st.get('h', body.height), body.height))
        if op == 'scale_x_to':
            new_w, new_h = max(_sw86_body_grid_step(self), _sw86_snap(self, value)), old_h
        elif op == 'scale_y_to':
            new_w, new_h = old_w, max(_sw86_body_grid_step(self), _sw86_snap(self, value))
        else:
            f = _sw86_float(value, 1.0)
            new_w = max(_sw86_body_grid_step(self), _sw86_snap(self, old_w * f))
            new_h = max(_sw86_body_grid_step(self), _sw86_snap(self, old_h * f))
        # Toolbar scale grows around BODY center to avoid directional drift.
        cx = _sw86_float(body.x) + old_w / 2.0
        cy = _sw86_float(body.y) - old_h / 2.0
        body.width = new_w; body.height = new_h
        body.x = _sw86_snap(self, cx - new_w / 2.0)
        body.y = _sw86_snap(self, cy + new_h / 2.0)
        _sw86_scale_current_unit_children_from_body_resize(self, st, body)
        if refresh:
            try: self.update_current_unit_canvas_positions()
            except Exception: pass
            try: self.update_attribute_items_for_unit()
            except Exception: pass
            try: self.schedule_scene_refresh(visual_only=True)
            except Exception: pass
        return None
    except Exception:
        if _sw86_prev_transform_unit_as_body_group is not None:
            return _sw86_prev_transform_unit_as_body_group(self, op, value, refresh)
        return None

try:
    MainWindow.scale_current_unit_children_from_body_resize = _sw86_scale_current_unit_children_from_body_resize
    MainWindow._transform_unit_as_body_group = _sw86_transform_unit_as_body_group
    if 'TemplateEditorDialog' in globals():
        TemplateEditorDialog.scale_current_unit_children_from_body_resize = _sw86_scale_current_unit_children_from_body_resize
        if hasattr(TemplateEditorDialog, '_transform_unit_as_body_group'):
            TemplateEditorDialog._transform_unit_as_body_group = _sw86_transform_unit_as_body_group
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v87: BODY canvas scaling final docking semantics
# ---------------------------------------------------------------------------
# BODY resize must edit only the BODY outline. Pins are re-docked to the new
# outline edges and text/attributes are translated by the relevant outline-edge
# delta; they are never geometrically scaled or re-spaced.  This override is
# intentionally shared by normal Symbol 1 symbols, imported Mentor symbols and
# Template Editor symbols because all of them pass through the same current_unit
# BODY resize hook.

def _sw87_pin_side_for_body_scale(pin, old_bounds):
    try:
        ox, oy, ow, oh = old_bounds
        px = _sw86_float(getattr(pin, 'x', 0.0))
        py = _sw86_float(getattr(pin, 'y', 0.0))
        left, right = ox, ox + ow
        top, bottom = oy, oy - oh
        side = str(getattr(pin, 'side', '') or '').lower()
        valid = {PinSide.LEFT.value, PinSide.RIGHT.value, PinSide.TOP.value, PinSide.BOTTOM.value}
        # Imported/native pins can carry incomplete or stale side metadata.  If
        # the old anchor is clearly closer to another outline edge, use the real
        # geometric side for the re-dock operation.
        distances = [
            (abs(px - left), PinSide.LEFT.value),
            (abs(px - right), PinSide.RIGHT.value),
            (abs(py - top), PinSide.TOP.value),
            (abs(py - bottom), PinSide.BOTTOM.value),
        ]
        distances.sort(key=lambda x: x[0])
        inferred = distances[0][1]
        if side not in valid:
            return inferred
        # Be conservative: only override existing side if it is visibly wrong.
        current_dist = {
            PinSide.LEFT.value: abs(px - left),
            PinSide.RIGHT.value: abs(px - right),
            PinSide.TOP.value: abs(py - top),
            PinSide.BOTTOM.value: abs(py - bottom),
        }.get(side, 1e9)
        if distances[0][0] + 0.25 < current_dist:
            return inferred
        return side
    except Exception:
        return str(getattr(pin, 'side', PinSide.LEFT.value) or PinSide.LEFT.value)


def _sw87_redock_pins_to_body(self, start_state, body):
    try:
        pins = list(getattr(getattr(self, 'current_unit', None), 'pins', []) or [])
    except Exception:
        pins = []
    if not pins:
        return
    old_x = _sw86_float((start_state or {}).get('x', getattr(body, 'x', 0.0)))
    old_y = _sw86_float((start_state or {}).get('y', getattr(body, 'y', 0.0)))
    old_w = max(_sw86_body_grid_step(self), abs(_sw86_float((start_state or {}).get('w', getattr(body, 'width', 1.0)), 1.0)))
    old_h = max(_sw86_body_grid_step(self), abs(_sw86_float((start_state or {}).get('h', getattr(body, 'height', 1.0)), 1.0)))
    old_bounds = (old_x, old_y, old_w, old_h)
    old_pos = {}
    try:
        for entry in (start_state or {}).get('pins', []) or []:
            if len(entry) >= 3:
                old_pos[entry[0]] = (_sw86_float(entry[1]), _sw86_float(entry[2]))
    except Exception:
        pass

    bx = _sw86_float(getattr(body, 'x', 0.0))
    by = _sw86_float(getattr(body, 'y', 0.0))
    bw = max(_sw86_body_grid_step(self), abs(_sw86_float(getattr(body, 'width', 0.0))))
    bh = max(_sw86_body_grid_step(self), abs(_sw86_float(getattr(body, 'height', 0.0))))
    left_x, right_x = bx, bx + bw
    top_y, bottom_y = by, by - bh
    cx, cy = bx + bw / 2.0, by - bh / 2.0

    groups = {PinSide.LEFT.value: [], PinSide.RIGHT.value: [], PinSide.TOP.value: [], PinSide.BOTTOM.value: []}
    for p in pins:
        groups.setdefault(_sw87_pin_side_for_body_scale(p, old_bounds), []).append(p)

    # Stable order prevents pins from crossing when the BODY is scaled.
    groups[PinSide.LEFT.value].sort(key=lambda p: -_sw86_float(old_pos.get(p, (getattr(p, 'x', 0.0), getattr(p, 'y', 0.0)))[1]))
    groups[PinSide.RIGHT.value].sort(key=lambda p: -_sw86_float(old_pos.get(p, (getattr(p, 'x', 0.0), getattr(p, 'y', 0.0)))[1]))
    groups[PinSide.TOP.value].sort(key=lambda p: _sw86_float(old_pos.get(p, (getattr(p, 'x', 0.0), getattr(p, 'y', 0.0)))[0]))
    groups[PinSide.BOTTOM.value].sort(key=lambda p: _sw86_float(old_pos.get(p, (getattr(p, 'x', 0.0), getattr(p, 'y', 0.0)))[0]))

    def place_vertical(group, x, side_value):
        n = len(group)
        if n <= 0:
            return
        for i, p in enumerate(group):
            y = cy if n == 1 else by - ((i + 1) * bh / (n + 1))
            old_px, old_py = old_pos.get(p, (_sw86_float(getattr(p, 'x', x)), _sw86_float(getattr(p, 'y', y))))
            nx, ny = _sw86_snap(self, x), _sw86_snap(self, y)
            try: p.side = side_value
            except Exception: pass
            p.x, p.y = nx, ny
            _sw86_move_pin_texts_keep_offsets(p, old_px, old_py, nx, ny)

    def place_horizontal(group, y, side_value):
        n = len(group)
        if n <= 0:
            return
        for i, p in enumerate(group):
            x = cx if n == 1 else bx + ((i + 1) * bw / (n + 1))
            old_px, old_py = old_pos.get(p, (_sw86_float(getattr(p, 'x', x)), _sw86_float(getattr(p, 'y', y))))
            nx, ny = _sw86_snap(self, x), _sw86_snap(self, y)
            try: p.side = side_value
            except Exception: pass
            p.x, p.y = nx, ny
            _sw86_move_pin_texts_keep_offsets(p, old_px, old_py, nx, ny)

    place_vertical(groups.get(PinSide.LEFT.value, []), left_x, PinSide.LEFT.value)
    place_vertical(groups.get(PinSide.RIGHT.value, []), right_x, PinSide.RIGHT.value)
    place_horizontal(groups.get(PinSide.TOP.value, []), top_y, PinSide.TOP.value)
    place_horizontal(groups.get(PinSide.BOTTOM.value, []), bottom_y, PinSide.BOTTOM.value)


def _sw87_text_delta_for_body_outline(self, tx, ty, old_bounds, new_bounds):
    ox, oy, ow, oh = old_bounds
    nx, ny, nw, nh = new_bounds
    old_left, old_right, old_top, old_bottom = ox, ox + ow, oy, oy - oh
    new_left, new_right, new_top, new_bottom = nx, nx + nw, ny, ny - nh
    old_cx, old_cy = ox + ow / 2.0, oy - oh / 2.0
    new_cx, new_cy = nx + nw / 2.0, ny - nh / 2.0
    tx = _sw86_float(tx); ty = _sw86_float(ty)
    tol = _sw86_body_grid_step(self) * 0.51
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


def _sw87_scale_current_unit_children_from_body_resize(self, start_state, body):
    start_state = start_state if isinstance(start_state, dict) else {}
    old_x = _sw86_float(start_state.get('x', getattr(body, 'x', 0.0)))
    old_y = _sw86_float(start_state.get('y', getattr(body, 'y', 0.0)))
    old_w = max(_sw86_body_grid_step(self), abs(_sw86_float(start_state.get('w', getattr(body, 'width', 1.0)), 1.0)))
    old_h = max(_sw86_body_grid_step(self), abs(_sw86_float(start_state.get('h', getattr(body, 'height', 1.0)), 1.0)))
    new_x = _sw86_snap(self, getattr(body, 'x', old_x))
    new_y = _sw86_snap(self, getattr(body, 'y', old_y))
    new_w = max(_sw86_body_grid_step(self), _sw86_snap(self, abs(_sw86_float(getattr(body, 'width', old_w), old_w))))
    new_h = max(_sw86_body_grid_step(self), _sw86_snap(self, abs(_sw86_float(getattr(body, 'height', old_h), old_h))))
    body.x, body.y, body.width, body.height = new_x, new_y, new_w, new_h
    old_bounds = (old_x, old_y, old_w, old_h)
    new_bounds = (new_x, new_y, new_w, new_h)
    sx = new_w / max(1e-9, old_w)
    sy = new_h / max(1e-9, old_h)

    # Pins: never scale length/font.  They are attached to the new outline.
    _sw87_redock_pins_to_body(self, start_state, body)

    # Texts/attributes: never scale, never alter line spacing.  Move each text
    # anchor by the delta of the outline region it belongs to.  This also covers
    # imported and template symbols because their body attributes use the same
    # TextModel anchors.
    for key in ('texts', 'attributes'):
        for t, tx, ty in start_state.get(key, []) or []:
            try:
                dx, dy = _sw87_text_delta_for_body_outline(self, tx, ty, old_bounds, new_bounds)
                t.x = _sw86_snap(self, _sw86_float(tx) + dx)
                t.y = _sw86_snap(self, _sw86_float(ty) + dy)
            except Exception:
                pass

    # BODY-owned/imported graphics form the BODY shape and are scaled with it.
    # Standalone graphics are not touched.
    for gr, gx, gy, gw, gh in start_state.get('graphics', []) or []:
        try:
            if not _sw86_is_body_graphic(gr):
                continue
            gr.x = _sw86_snap(self, new_x + (_sw86_float(gx) - old_x) * sx)
            gr.y = _sw86_snap(self, new_y + (_sw86_float(gy) - old_y) * sy)
            gr.w = max(_sw86_body_grid_step(self), _sw86_snap(self, _sw86_float(gw) * sx))
            gr.h = max(_sw86_body_grid_step(self), _sw86_snap(self, _sw86_float(gh) * sy))
        except Exception:
            pass


def _sw87_snapshot_body_resize_state(self, body=None):
    try:
        u = self.current_unit
        b = body or u.body
        return {
            'x': _sw86_float(getattr(b, 'x', 0.0)),
            'y': _sw86_float(getattr(b, 'y', 0.0)),
            'w': _sw86_float(getattr(b, 'width', 1.0), 1.0),
            'h': _sw86_float(getattr(b, 'height', 1.0), 1.0),
            'pins': [(p, _sw86_float(getattr(p, 'x', 0.0)), _sw86_float(getattr(p, 'y', 0.0)), _sw86_float(getattr(p, 'length', 1.0), 1.0)) for p in getattr(u, 'pins', []) or []],
            'texts': [(t, _sw86_float(getattr(t, 'x', 0.0)), _sw86_float(getattr(t, 'y', 0.0))) for t in getattr(u, 'texts', []) or []],
            'attributes': [(t, _sw86_float(getattr(t, 'x', 0.0)), _sw86_float(getattr(t, 'y', 0.0))) for t in (getattr(getattr(u, 'body', None), 'attribute_texts', {}) or {}).values()],
            'graphics': [(gr, _sw86_float(getattr(gr, 'x', 0.0)), _sw86_float(getattr(gr, 'y', 0.0)), _sw86_float(getattr(gr, 'w', 0.0)), _sw86_float(getattr(gr, 'h', 0.0))) for gr in getattr(u, 'graphics', []) or []],
        }
    except Exception:
        return {}


def _sw87_transform_unit_as_body_group(self, op, value=None, refresh=True):
    if op not in ('scale', 'scale_x_to', 'scale_y_to'):
        if _sw86_prev_transform_unit_as_body_group is not None:
            return _sw86_prev_transform_unit_as_body_group(self, op, value, refresh)
        return None
    try:
        u = self.current_unit
        body = u.body
        st = _sw87_snapshot_body_resize_state(self, body)
        old_w = max(_sw86_body_grid_step(self), _sw86_float(st.get('w', body.width), body.width))
        old_h = max(_sw86_body_grid_step(self), _sw86_float(st.get('h', body.height), body.height))
        if op == 'scale_x_to':
            new_w, new_h = max(_sw86_body_grid_step(self), _sw86_snap(self, value)), old_h
        elif op == 'scale_y_to':
            new_w, new_h = old_w, max(_sw86_body_grid_step(self), _sw86_snap(self, value))
        else:
            f = _sw86_float(value, 1.0)
            new_w = max(_sw86_body_grid_step(self), _sw86_snap(self, old_w * f))
            new_h = max(_sw86_body_grid_step(self), _sw86_snap(self, old_h * f))
        cx = _sw86_float(body.x) + old_w / 2.0
        cy = _sw86_float(body.y) - old_h / 2.0
        body.width = new_w; body.height = new_h
        body.x = _sw86_snap(self, cx - new_w / 2.0)
        body.y = _sw86_snap(self, cy + new_h / 2.0)
        _sw87_scale_current_unit_children_from_body_resize(self, st, body)
        if refresh:
            try: self.update_current_unit_canvas_positions()
            except Exception: pass
            try: self.update_attribute_items_for_unit()
            except Exception: pass
            try: self.schedule_scene_refresh(visual_only=True)
            except Exception: pass
        return None
    except Exception:
        if _sw86_prev_transform_unit_as_body_group is not None:
            return _sw86_prev_transform_unit_as_body_group(self, op, value, refresh)
        return None

try:
    MainWindow.scale_current_unit_children_from_body_resize = _sw87_scale_current_unit_children_from_body_resize
    MainWindow._transform_unit_as_body_group = _sw87_transform_unit_as_body_group
    MainWindow._snapshot_body_resize_state = _sw87_snapshot_body_resize_state
    if 'TemplateEditorDialog' in globals():
        TemplateEditorDialog.scale_current_unit_children_from_body_resize = _sw87_scale_current_unit_children_from_body_resize
        TemplateEditorDialog._snapshot_body_resize_state = _sw87_snapshot_body_resize_state
        if hasattr(TemplateEditorDialog, '_transform_unit_as_body_group'):
            TemplateEditorDialog._transform_unit_as_body_group = _sw87_transform_unit_as_body_group
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v88: harmonized BODY scaling pipeline
# ---------------------------------------------------------------------------
# One single rule-set for Symbol 1, imported symbols and Template Editor:
#   * BODY geometry is the only geometry that is resized.
#   * Pins are re-docked to the resized BODY outline. Their length and fonts are
#     never scaled.  The declared pin side is kept stable; geometric inference is
#     used only if the side is missing/invalid.
#   * Body attributes/plain texts are translated as blocks.  Font size and line
#     spacing are never scaled or re-spaced.
#   * BODY-owned graphics are scaled from the immutable start snapshot so there
#     is no cumulative drift while dragging canvas handles.


def _sw88_valid_pin_side(side):
    s = str(side or '').lower()
    valid = {PinSide.LEFT.value, PinSide.RIGHT.value, PinSide.TOP.value, PinSide.BOTTOM.value}
    return s if s in valid else ''


def _sw88_infer_pin_side_from_bounds(pin, bounds):
    try:
        x, y, w, h = bounds
        px = _sw86_float(getattr(pin, 'x', 0.0))
        py = _sw86_float(getattr(pin, 'y', 0.0))
        candidates = [
            (abs(px - x), PinSide.LEFT.value),
            (abs(px - (x + w)), PinSide.RIGHT.value),
            (abs(py - y), PinSide.TOP.value),
            (abs(py - (y - h)), PinSide.BOTTOM.value),
        ]
        return sorted(candidates, key=lambda t: t[0])[0][1]
    except Exception:
        return PinSide.LEFT.value


def _sw88_pin_side(pin, old_bounds):
    # Keep metadata stable.  Previous versions over-inferred the side from the
    # temporary old geometry, which could make pins jump to another side during
    # resize/import normalization.
    return _sw88_valid_pin_side(getattr(pin, 'side', '')) or _sw88_infer_pin_side_from_bounds(pin, old_bounds)


def _sw88_pin_old_pos_map(start_state):
    old_pos = {}
    try:
        for entry in (start_state or {}).get('pins', []) or []:
            if len(entry) >= 3:
                old_pos[entry[0]] = (_sw86_float(entry[1]), _sw86_float(entry[2]))
    except Exception:
        pass
    return old_pos


def _sw88_redock_pins_to_body(self, start_state, body):
    try:
        pins = list(getattr(getattr(self, 'current_unit', None), 'pins', []) or [])
    except Exception:
        pins = []
    if not pins:
        return

    step = _sw86_body_grid_step(self)
    ox = _sw86_float((start_state or {}).get('x', getattr(body, 'x', 0.0)))
    oy = _sw86_float((start_state or {}).get('y', getattr(body, 'y', 0.0)))
    ow = max(step, abs(_sw86_float((start_state or {}).get('w', getattr(body, 'width', 1.0)), 1.0)))
    oh = max(step, abs(_sw86_float((start_state or {}).get('h', getattr(body, 'height', 1.0)), 1.0)))
    old_bounds = (ox, oy, ow, oh)
    nx = _sw86_float(getattr(body, 'x', ox))
    ny = _sw86_float(getattr(body, 'y', oy))
    nw = max(step, abs(_sw86_float(getattr(body, 'width', ow), ow)))
    nh = max(step, abs(_sw86_float(getattr(body, 'height', oh), oh)))

    old_pos = _sw88_pin_old_pos_map(start_state)
    groups = {PinSide.LEFT.value: [], PinSide.RIGHT.value: [], PinSide.TOP.value: [], PinSide.BOTTOM.value: []}
    for p in pins:
        groups.setdefault(_sw88_pin_side(p, old_bounds), []).append(p)

    # Keep visual order from the immutable start state.
    groups[PinSide.LEFT.value].sort(key=lambda p: -old_pos.get(p, (_sw86_float(getattr(p, 'x', 0.0)), _sw86_float(getattr(p, 'y', 0.0))))[1])
    groups[PinSide.RIGHT.value].sort(key=lambda p: -old_pos.get(p, (_sw86_float(getattr(p, 'x', 0.0)), _sw86_float(getattr(p, 'y', 0.0))))[1])
    groups[PinSide.TOP.value].sort(key=lambda p: old_pos.get(p, (_sw86_float(getattr(p, 'x', 0.0)), _sw86_float(getattr(p, 'y', 0.0))))[0])
    groups[PinSide.BOTTOM.value].sort(key=lambda p: old_pos.get(p, (_sw86_float(getattr(p, 'x', 0.0)), _sw86_float(getattr(p, 'y', 0.0))))[0])

    def _clamp01(v):
        try: return max(0.0, min(1.0, float(v)))
        except Exception: return 0.5

    def place_lr(group, side_value, x_edge):
        n = len(group)
        if not n:
            return
        for i, p in enumerate(group):
            old_px, old_py = old_pos.get(p, (_sw86_float(getattr(p, 'x', x_edge)), _sw86_float(getattr(p, 'y', ny - nh/2.0))))
            if n == 1:
                t = 0.5
            else:
                # Preserve each pin's relative position on the side when it was
                # already on/near the old outline; otherwise use clean even side
                # distribution.  Both variants are computed from the immutable
                # start state, not cumulatively.
                t = _clamp01((oy - old_py) / max(1e-9, oh))
                if t <= 0.02 or t >= 0.98:
                    t = (i + 1) / (n + 1)
            px = _sw86_snap(self, x_edge)
            py = _sw86_snap(self, ny - t * nh)
            try: p.side = side_value
            except Exception: pass
            p.x, p.y = px, py
            _sw86_move_pin_texts_keep_offsets(p, old_px, old_py, px, py)

    def place_tb(group, side_value, y_edge):
        n = len(group)
        if not n:
            return
        for i, p in enumerate(group):
            old_px, old_py = old_pos.get(p, (_sw86_float(getattr(p, 'x', nx + nw/2.0)), _sw86_float(getattr(p, 'y', y_edge))))
            if n == 1:
                t = 0.5
            else:
                t = _clamp01((old_px - ox) / max(1e-9, ow))
                if t <= 0.02 or t >= 0.98:
                    t = (i + 1) / (n + 1)
            px = _sw86_snap(self, nx + t * nw)
            py = _sw86_snap(self, y_edge)
            try: p.side = side_value
            except Exception: pass
            p.x, p.y = px, py
            _sw86_move_pin_texts_keep_offsets(p, old_px, old_py, px, py)

    place_lr(groups.get(PinSide.LEFT.value, []), PinSide.LEFT.value, nx)
    place_lr(groups.get(PinSide.RIGHT.value, []), PinSide.RIGHT.value, nx + nw)
    place_tb(groups.get(PinSide.TOP.value, []), PinSide.TOP.value, ny)
    place_tb(groups.get(PinSide.BOTTOM.value, []), PinSide.BOTTOM.value, ny - nh)


def _sw88_outline_delta_for_anchor(self, ax, ay, old_bounds, new_bounds):
    ox, oy, ow, oh = old_bounds
    nx, ny, nw, nh = new_bounds
    old_left, old_right, old_top, old_bottom = ox, ox + ow, oy, oy - oh
    new_left, new_right, new_top, new_bottom = nx, nx + nw, ny, ny - nh
    old_cx, old_cy = ox + ow / 2.0, oy - oh / 2.0
    new_cx, new_cy = nx + nw / 2.0, ny - nh / 2.0
    ax = _sw86_float(ax); ay = _sw86_float(ay)
    tol = max(_sw86_body_grid_step(self), 1e-9) * 0.75
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


def _sw88_move_text_block(self, entries, old_bounds, new_bounds):
    entries = list(entries or [])
    if not entries:
        return
    try:
        xs = [_sw86_float(x) for _, x, _ in entries]
        ys = [_sw86_float(y) for _, _, y in entries]
        ax = (min(xs) + max(xs)) / 2.0
        ay = (min(ys) + max(ys)) / 2.0
    except Exception:
        try:
            ax, ay = _sw86_float(entries[0][1]), _sw86_float(entries[0][2])
        except Exception:
            return
    dx, dy = _sw88_outline_delta_for_anchor(self, ax, ay, old_bounds, new_bounds)
    for t, tx, ty in entries:
        try:
            t.x = _sw86_snap(self, _sw86_float(tx) + dx)
            t.y = _sw86_snap(self, _sw86_float(ty) + dy)
        except Exception:
            pass


def _sw88_scale_body_graphics(self, start_state, old_bounds, new_bounds):
    ox, oy, ow, oh = old_bounds
    nx, ny, nw, nh = new_bounds
    sx = nw / max(1e-9, ow)
    sy = nh / max(1e-9, oh)
    step = _sw86_body_grid_step(self)
    for gr, gx, gy, gw, gh in (start_state or {}).get('graphics', []) or []:
        try:
            if not _sw86_is_body_graphic(gr):
                continue
            gr.x = _sw86_snap(self, nx + (_sw86_float(gx) - ox) * sx)
            gr.y = _sw86_snap(self, ny + (_sw86_float(gy) - oy) * sy)
            gr.w = max(step, _sw86_snap(self, _sw86_float(gw) * sx))
            gr.h = max(step, _sw86_snap(self, _sw86_float(gh) * sy))
        except Exception:
            pass


def _sw88_scale_current_unit_children_from_body_resize(self, start_state, body):
    start_state = start_state if isinstance(start_state, dict) else {}
    step = _sw86_body_grid_step(self)
    old_x = _sw86_float(start_state.get('x', getattr(body, 'x', 0.0)))
    old_y = _sw86_float(start_state.get('y', getattr(body, 'y', 0.0)))
    old_w = max(step, abs(_sw86_float(start_state.get('w', getattr(body, 'width', 1.0)), 1.0)))
    old_h = max(step, abs(_sw86_float(start_state.get('h', getattr(body, 'height', 1.0)), 1.0)))
    new_x = _sw86_snap(self, getattr(body, 'x', old_x))
    new_y = _sw86_snap(self, getattr(body, 'y', old_y))
    new_w = max(step, _sw86_snap(self, abs(_sw86_float(getattr(body, 'width', old_w), old_w))))
    new_h = max(step, _sw86_snap(self, abs(_sw86_float(getattr(body, 'height', old_h), old_h))))
    body.x, body.y, body.width, body.height = new_x, new_y, new_w, new_h
    old_bounds = (old_x, old_y, old_w, old_h)
    new_bounds = (new_x, new_y, new_w, new_h)

    # Order matters: graphics define BODY shape, then pins/texts are docked to
    # the final snapped outline.
    _sw88_scale_body_graphics(self, start_state, old_bounds, new_bounds)
    _sw88_redock_pins_to_body(self, start_state, body)
    _sw88_move_text_block(self, start_state.get('attributes', []) or [], old_bounds, new_bounds)
    _sw88_move_text_block(self, start_state.get('texts', []) or [], old_bounds, new_bounds)


def _sw88_snapshot_body_resize_state(self, body=None):
    # Keep the v87 snapshot shape but ensure every call uses a plain data-only
    # dict from the current unit.  This is shared by main editor and template
    # editor, therefore imported/template symbols go through the same pipeline.
    try:
        return _sw87_snapshot_body_resize_state(self, body)
    except Exception:
        return {}


def _sw88_transform_unit_as_body_group(self, op, value=None, refresh=True):
    if op not in ('scale', 'scale_x_to', 'scale_y_to'):
        if _sw86_prev_transform_unit_as_body_group is not None:
            return _sw86_prev_transform_unit_as_body_group(self, op, value, refresh)
        return None
    try:
        u = self.current_unit
        body = u.body
        st = _sw88_snapshot_body_resize_state(self, body)
        step = _sw86_body_grid_step(self)
        old_w = max(step, _sw86_float(st.get('w', getattr(body, 'width', 1.0)), getattr(body, 'width', 1.0)))
        old_h = max(step, _sw86_float(st.get('h', getattr(body, 'height', 1.0)), getattr(body, 'height', 1.0)))
        if op == 'scale_x_to':
            new_w, new_h = max(step, _sw86_snap(self, value)), old_h
        elif op == 'scale_y_to':
            new_w, new_h = old_w, max(step, _sw86_snap(self, value))
        else:
            f = _sw86_float(value, 1.0)
            new_w = max(step, _sw86_snap(self, old_w * f))
            new_h = max(step, _sw86_snap(self, old_h * f))
        cx = _sw86_float(body.x) + old_w / 2.0
        cy = _sw86_float(body.y) - old_h / 2.0
        body.width, body.height = new_w, new_h
        body.x = _sw86_snap(self, cx - new_w / 2.0)
        body.y = _sw86_snap(self, cy + new_h / 2.0)
        _sw88_scale_current_unit_children_from_body_resize(self, st, body)
        if refresh:
            try: self.update_current_unit_canvas_positions()
            except Exception: pass
            try: self.update_attribute_items_for_unit()
            except Exception: pass
            try: self.schedule_scene_refresh(visual_only=True)
            except Exception: pass
        return None
    except Exception:
        if _sw87_transform_unit_as_body_group is not None:
            return _sw87_transform_unit_as_body_group(self, op, value, refresh)
        return None

try:
    MainWindow.scale_current_unit_children_from_body_resize = _sw88_scale_current_unit_children_from_body_resize
    MainWindow._transform_unit_as_body_group = _sw88_transform_unit_as_body_group
    MainWindow._snapshot_body_resize_state = _sw88_snapshot_body_resize_state
    if 'TemplateEditorDialog' in globals():
        TemplateEditorDialog.scale_current_unit_children_from_body_resize = _sw88_scale_current_unit_children_from_body_resize
        TemplateEditorDialog._snapshot_body_resize_state = _sw88_snapshot_body_resize_state
        if hasattr(TemplateEditorDialog, '_transform_unit_as_body_group'):
            TemplateEditorDialog._transform_unit_as_body_group = _sw88_transform_unit_as_body_group
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v89: immediate pin re-anchor for BODY resize/scale on all symbol origins
# ---------------------------------------------------------------------------
# v88 harmonized the resize path, but imported/template body graphics can have a
# visual outline that differs from the simple body.x/y/width/height rectangle.
# This patch always computes the final visible BODY outline first and anchors
# pins to that outline immediately after every canvas/ribbon BODY resize.


def _sw89_unit(self):
    try:
        return getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    except Exception:
        return None


def _sw89_graphic_bounds(g):
    try:
        x = _sw86_float(getattr(g, 'x', 0.0))
        y = _sw86_float(getattr(g, 'y', 0.0))
        w = _sw86_float(getattr(g, 'w', getattr(g, 'width', 0.0)))
        h = _sw86_float(getattr(g, 'h', getattr(g, 'height', 0.0)))
        xs = [x, x + w]
        ys = [y, y - h]
        return min(xs), max(ys), max(xs), min(ys)   # left, top, right, bottom
    except Exception:
        return None


def _sw89_visible_body_outline(self, unit, body):
    """Return left, top, right, bottom of the visible BODY outline in grid units."""
    try:
        body_graphics = [g for g in (getattr(unit, 'graphics', []) or []) if _sw86_is_body_graphic(g)]
    except Exception:
        body_graphics = []
    bounds = []
    for g in body_graphics:
        b = _sw89_graphic_bounds(g)
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
    x = _sw86_float(getattr(body, 'x', 0.0))
    y = _sw86_float(getattr(body, 'y', 0.0))
    w = abs(_sw86_float(getattr(body, 'width', 1.0), 1.0))
    h = abs(_sw86_float(getattr(body, 'height', 1.0), 1.0))
    return x, y, x + w, y - h


def _sw89_start_pin_pos(start_state):
    mp = {}
    try:
        for entry in (start_state or {}).get('pins', []) or []:
            if len(entry) >= 3:
                mp[entry[0]] = (_sw86_float(entry[1]), _sw86_float(entry[2]))
    except Exception:
        pass
    return mp


def _sw89_side_for_pin(pin, old_outline):
    # Trust explicit side first.  Imported pins sometimes have exact coordinates,
    # but after resize the user's side metadata is the stable anchor rule.
    try:
        s = str(getattr(pin, 'side', '') or '').lower()
        if s in (PinSide.LEFT.value, PinSide.RIGHT.value, PinSide.TOP.value, PinSide.BOTTOM.value):
            return s
    except Exception:
        pass
    try:
        left, top, right, bottom = old_outline
        px = _sw86_float(getattr(pin, 'x', 0.0))
        py = _sw86_float(getattr(pin, 'y', 0.0))
        cand = [(abs(px-left), PinSide.LEFT.value), (abs(px-right), PinSide.RIGHT.value), (abs(py-top), PinSide.TOP.value), (abs(py-bottom), PinSide.BOTTOM.value)]
        return min(cand, key=lambda t: t[0])[1]
    except Exception:
        return PinSide.LEFT.value


def _sw89_redock_pins_to_visible_outline(self, start_state, body):
    unit = _sw89_unit(self)
    if unit is None:
        return
    pins = list(getattr(unit, 'pins', []) or [])
    if not pins:
        return
    step = _sw86_body_grid_step(self)
    old_x = _sw86_float((start_state or {}).get('x', getattr(body, 'x', 0.0)))
    old_y = _sw86_float((start_state or {}).get('y', getattr(body, 'y', 0.0)))
    old_w = max(step, abs(_sw86_float((start_state or {}).get('w', getattr(body, 'width', 1.0)), 1.0)))
    old_h = max(step, abs(_sw86_float((start_state or {}).get('h', getattr(body, 'height', 1.0)), 1.0)))
    old_outline = (old_x, old_y, old_x + old_w, old_y - old_h)
    left, top, right, bottom = _sw89_visible_body_outline(self, unit, body)
    left = _sw86_snap(self, left); right = _sw86_snap(self, right)
    top = _sw86_snap(self, top); bottom = _sw86_snap(self, bottom)
    height = max(step, abs(top - bottom))
    width = max(step, abs(right - left))
    old_pos = _sw89_start_pin_pos(start_state)

    groups = {PinSide.LEFT.value: [], PinSide.RIGHT.value: [], PinSide.TOP.value: [], PinSide.BOTTOM.value: []}
    for p in pins:
        groups.setdefault(_sw89_side_for_pin(p, old_outline), []).append(p)

    groups[PinSide.LEFT.value].sort(key=lambda p: -old_pos.get(p, (_sw86_float(getattr(p, 'x', left)), _sw86_float(getattr(p, 'y', (top+bottom)/2.0))))[1])
    groups[PinSide.RIGHT.value].sort(key=lambda p: -old_pos.get(p, (_sw86_float(getattr(p, 'x', right)), _sw86_float(getattr(p, 'y', (top+bottom)/2.0))))[1])
    groups[PinSide.TOP.value].sort(key=lambda p: old_pos.get(p, (_sw86_float(getattr(p, 'x', (left+right)/2.0)), _sw86_float(getattr(p, 'y', top))))[0])
    groups[PinSide.BOTTOM.value].sort(key=lambda p: old_pos.get(p, (_sw86_float(getattr(p, 'x', (left+right)/2.0)), _sw86_float(getattr(p, 'y', bottom))))[0])

    def _ratio(v):
        try:
            return max(0.0, min(1.0, float(v)))
        except Exception:
            return 0.5

    def _place_vertical_side(group, side_value, x_edge):
        n = len(group)
        if not n:
            return
        for i, p in enumerate(group):
            old_px, old_py = old_pos.get(p, (_sw86_float(getattr(p, 'x', x_edge)), _sw86_float(getattr(p, 'y', (top + bottom) / 2.0))))
            if n == 1:
                t = 0.5
            else:
                t = _ratio((old_y - old_py) / max(1e-9, old_h))
                # If the imported pin was not meaningfully placed on the old body
                # outline, fall back to clean, centered distribution.
                if t <= 0.01 or t >= 0.99:
                    t = (i + 1) / (n + 1)
            px = _sw86_snap(self, x_edge)
            py = _sw86_snap(self, top - t * height)
            try:
                p.side = side_value
            except Exception:
                pass
            p.x, p.y = px, py
            _sw86_move_pin_texts_keep_offsets(p, old_px, old_py, px, py)

    def _place_horizontal_side(group, side_value, y_edge):
        n = len(group)
        if not n:
            return
        for i, p in enumerate(group):
            old_px, old_py = old_pos.get(p, (_sw86_float(getattr(p, 'x', (left + right) / 2.0)), _sw86_float(getattr(p, 'y', y_edge))))
            if n == 1:
                t = 0.5
            else:
                t = _ratio((old_px - old_x) / max(1e-9, old_w))
                if t <= 0.01 or t >= 0.99:
                    t = (i + 1) / (n + 1)
            px = _sw86_snap(self, left + t * width)
            py = _sw86_snap(self, y_edge)
            try:
                p.side = side_value
            except Exception:
                pass
            p.x, p.y = px, py
            _sw86_move_pin_texts_keep_offsets(p, old_px, old_py, px, py)

    _place_vertical_side(groups.get(PinSide.LEFT.value, []), PinSide.LEFT.value, left)
    _place_vertical_side(groups.get(PinSide.RIGHT.value, []), PinSide.RIGHT.value, right)
    _place_horizontal_side(groups.get(PinSide.TOP.value, []), PinSide.TOP.value, top)
    _place_horizontal_side(groups.get(PinSide.BOTTOM.value, []), PinSide.BOTTOM.value, bottom)


def _sw89_scale_current_unit_children_from_body_resize(self, start_state, body):
    # First run the harmonized v88 path to scale body graphics/text from the
    # immutable start snapshot.  Then re-anchor pins to the visible final outline
    # so Symbol 1, imported symbols and Template Editor symbols behave identically.
    _sw88_scale_current_unit_children_from_body_resize(self, start_state, body)
    _sw89_redock_pins_to_visible_outline(self, start_state, body)
    try:
        self.update_current_unit_canvas_positions()
    except Exception:
        pass


def _sw89_dock_pins_to_body(self, unit):
    # Public docking helper: no MENTOR_* early return.  It anchors to the visible
    # body outline when body graphics exist, otherwise to the model body rectangle.
    try:
        b = getattr(unit, 'body', None)
        if b is None:
            return
        st = {
            'x': _sw86_float(getattr(b, 'x', 0.0)),
            'y': _sw86_float(getattr(b, 'y', 0.0)),
            'w': _sw86_float(getattr(b, 'width', 1.0), 1.0),
            'h': _sw86_float(getattr(b, 'height', 1.0), 1.0),
            'pins': [(p, _sw86_float(getattr(p, 'x', 0.0)), _sw86_float(getattr(p, 'y', 0.0)), _sw86_float(getattr(p, 'length', 1.0), 1.0)) for p in (getattr(unit, 'pins', []) or [])],
        }
        # Temporarily expose unit for dialogs that do not use current_unit.
        old_current = getattr(self, 'current_unit', None)
        try:
            if old_current is None:
                self.current_unit = unit
            _sw89_redock_pins_to_visible_outline(self, st, b)
        finally:
            if old_current is None and hasattr(self, 'current_unit'):
                try: delattr(self, 'current_unit')
                except Exception: pass
    except Exception:
        pass

try:
    MainWindow.scale_current_unit_children_from_body_resize = _sw89_scale_current_unit_children_from_body_resize
    MainWindow.dock_pins_to_body = _sw89_dock_pins_to_body
    if 'TemplateEditorDialog' in globals():
        TemplateEditorDialog.scale_current_unit_children_from_body_resize = _sw89_scale_current_unit_children_from_body_resize
        TemplateEditorDialog.dock_pins_to_body = _sw89_dock_pins_to_body
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v90: final deterministic BODY resize pipeline
# ---------------------------------------------------------------------------
# BODY canvas/ribbon scaling must only resize the BODY artwork/rectangle.
# Pins are re-anchored immediately to the visible BODY outline.  Body attribute
# texts and plain texts are translated as blocks/anchors, never scaled or
# re-spaced.  The same implementation is installed for imported symbols,
# template symbols and Symbol 1.


def _sw90_snap(self, v):
    try:
        return _sw86_snap(self, v)
    except Exception:
        try:
            step = float(getattr(self, 'edit_grid', 1.0) or 1.0)
            return round(float(v) / step) * step
        except Exception:
            return float(v)


def _sw90_step(self):
    try:
        return max(1e-9, _sw86_body_grid_step(self))
    except Exception:
        return 1.0


def _sw90_unit(self):
    try:
        return getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    except Exception:
        return None


def _sw90_body_graphics(unit):
    out = []
    try:
        for g in getattr(unit, 'graphics', []) or []:
            if _sw86_is_body_graphic(g):
                out.append(g)
    except Exception:
        pass
    return out


def _sw90_rect_outline_from_body(body):
    x = _sw86_float(getattr(body, 'x', 0.0))
    y = _sw86_float(getattr(body, 'y', 0.0))
    w = abs(_sw86_float(getattr(body, 'width', 1.0), 1.0))
    h = abs(_sw86_float(getattr(body, 'height', 1.0), 1.0))
    return x, y, x + w, y - h  # left, top, right, bottom


def _sw90_graphic_outline(g):
    # Axis-aligned visible extent in model grid.  BODY artwork currently uses
    # orthogonal imported primitives; include all four corners so negative w/h
    # or previous flips cannot shrink the resulting outline.
    try:
        x = _sw86_float(getattr(g, 'x', 0.0))
        y = _sw86_float(getattr(g, 'y', 0.0))
        w = _sw86_float(getattr(g, 'w', getattr(g, 'width', 0.0)))
        h = _sw86_float(getattr(g, 'h', getattr(g, 'height', 0.0)))
        pts = [(x, y), (x + w, y), (x, y - h), (x + w, y - h)]
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        return min(xs), max(ys), max(xs), min(ys)
    except Exception:
        return None


def _sw90_visible_body_outline(self, unit, body):
    bounds = []
    for g in _sw90_body_graphics(unit):
        b = _sw90_graphic_outline(g)
        if b is not None:
            bounds.append(b)
    if bounds:
        l = min(v[0] for v in bounds); t = max(v[1] for v in bounds)
        r = max(v[2] for v in bounds); b = min(v[3] for v in bounds)
        if abs(r - l) > 1e-9 and abs(t - b) > 1e-9:
            return l, t, r, b
    return _sw90_rect_outline_from_body(body)


def _sw90_snapshot_body_resize_state(self, body=None):
    u = _sw90_unit(self)
    if u is None:
        return {}
    b = body or getattr(u, 'body', None)
    if b is None:
        return {}
    outline = _sw90_visible_body_outline(self, u, b)
    return {
        'x': _sw86_float(getattr(b, 'x', 0.0)),
        'y': _sw86_float(getattr(b, 'y', 0.0)),
        'w': max(_sw90_step(self), abs(_sw86_float(getattr(b, 'width', 1.0), 1.0))),
        'h': max(_sw90_step(self), abs(_sw86_float(getattr(b, 'height', 1.0), 1.0))),
        'outline': outline,
        'pins': [(p, _sw86_float(getattr(p, 'x', 0.0)), _sw86_float(getattr(p, 'y', 0.0)), _sw86_float(getattr(p, 'length', 1.0), 1.0), str(getattr(p, 'side', '') or '')) for p in getattr(u, 'pins', []) or []],
        'texts': [(t, _sw86_float(getattr(t, 'x', 0.0)), _sw86_float(getattr(t, 'y', 0.0))) for t in getattr(u, 'texts', []) or []],
        'attributes': [(t, _sw86_float(getattr(t, 'x', 0.0)), _sw86_float(getattr(t, 'y', 0.0))) for t in (getattr(getattr(u, 'body', None), 'attribute_texts', {}) or {}).values()],
        'graphics': [(gr, _sw86_float(getattr(gr, 'x', 0.0)), _sw86_float(getattr(gr, 'y', 0.0)), _sw86_float(getattr(gr, 'w', 0.0)), _sw86_float(getattr(gr, 'h', 0.0))) for gr in getattr(u, 'graphics', []) or []],
    }


def _sw90_apply_body_artwork_resize(self, start_state, body):
    u = _sw90_unit(self)
    if u is None:
        return
    step = _sw90_step(self)
    old_left, old_top, old_right, old_bottom = (start_state or {}).get('outline') or _sw90_rect_outline_from_body(body)
    old_w = max(step, abs(old_right - old_left))
    old_h = max(step, abs(old_top - old_bottom))
    # BodyItem has already set body.x/y/width/height during canvas resize.
    # Treat that as target logical outline for both native BODY and imported
    # BODY artwork.
    new_left = _sw90_snap(self, getattr(body, 'x', old_left))
    new_top = _sw90_snap(self, getattr(body, 'y', old_top))
    new_w = max(step, _sw90_snap(self, abs(_sw86_float(getattr(body, 'width', old_w), old_w))))
    new_h = max(step, _sw90_snap(self, abs(_sw86_float(getattr(body, 'height', old_h), old_h))))
    body.x, body.y, body.width, body.height = new_left, new_top, new_w, new_h
    sx = new_w / old_w
    sy = new_h / old_h

    # Scale only BODY-owned graphics. Standalone user graphics are untouched.
    has_body_graphics = False
    for gr, gx, gy, gw, gh in (start_state or {}).get('graphics', []) or []:
        try:
            if not _sw86_is_body_graphic(gr):
                continue
            has_body_graphics = True
            gr.x = _sw90_snap(self, new_left + (_sw86_float(gx) - old_left) * sx)
            gr.y = _sw90_snap(self, new_top + (_sw86_float(gy) - old_top) * sy)
            gr.w = max(step, _sw90_snap(self, _sw86_float(gw) * sx))
            gr.h = max(step, _sw90_snap(self, _sw86_float(gh) * sy))
        except Exception:
            pass

    if has_body_graphics:
        # Body model follows the visible artwork after snapping.
        try:
            l, t, r, btm = _sw90_visible_body_outline(self, u, body)
            body.x = _sw90_snap(self, l); body.y = _sw90_snap(self, t)
            body.width = max(step, _sw90_snap(self, r - l))
            body.height = max(step, _sw90_snap(self, t - btm))
        except Exception:
            pass


def _sw90_side_for_pin(pin, old_outline, stored_side=None):
    try:
        s = str(stored_side or getattr(pin, 'side', '') or '').lower()
        if s in (PinSide.LEFT.value, PinSide.RIGHT.value, PinSide.TOP.value, PinSide.BOTTOM.value):
            return s
    except Exception:
        pass
    try:
        l, t, r, b = old_outline
        px = _sw86_float(getattr(pin, 'x', 0.0)); py = _sw86_float(getattr(pin, 'y', 0.0))
        return min([(abs(px-l), PinSide.LEFT.value), (abs(px-r), PinSide.RIGHT.value), (abs(py-t), PinSide.TOP.value), (abs(py-b), PinSide.BOTTOM.value)], key=lambda z: z[0])[1]
    except Exception:
        return PinSide.LEFT.value


def _sw90_redock_pins(self, start_state, body):
    u = _sw90_unit(self)
    if u is None:
        return
    pins = list(getattr(u, 'pins', []) or [])
    if not pins:
        return
    step = _sw90_step(self)
    old_outline = (start_state or {}).get('outline') or _sw90_rect_outline_from_body(body)
    old_l, old_t, old_r, old_b = old_outline
    old_w = max(step, abs(old_r - old_l)); old_h = max(step, abs(old_t - old_b))
    new_l, new_t, new_r, new_b = _sw90_visible_body_outline(self, u, body)
    new_l = _sw90_snap(self, new_l); new_r = _sw90_snap(self, new_r)
    new_t = _sw90_snap(self, new_t); new_b = _sw90_snap(self, new_b)
    new_w = max(step, abs(new_r - new_l)); new_h = max(step, abs(new_t - new_b))

    # PinModel/dataclass instances are not hashable in some builds.
    # Use the runtime identity as a stable key for this resize/rebuild pass.
    old_pos = {}
    old_side = {}
    for row in (start_state or {}).get('pins', []) or []:
        try:
            p = row[0]
            k = id(p)
            old_pos[k] = (_sw86_float(row[1]), _sw86_float(row[2]))
            old_side[k] = row[4] if len(row) > 4 else str(getattr(p, 'side', '') or '')
        except Exception:
            pass

    for p in pins:
        k = id(p)
        opx, opy = old_pos.get(k, (_sw86_float(getattr(p, 'x', 0.0)), _sw86_float(getattr(p, 'y', 0.0))))
        side = _sw90_side_for_pin(p, old_outline, old_side.get(k))
        if side == PinSide.RIGHT.value:
            t = max(0.0, min(1.0, (old_t - opy) / old_h))
            px, py = new_r, new_t - t * new_h
        elif side == PinSide.TOP.value:
            t = max(0.0, min(1.0, (opx - old_l) / old_w))
            px, py = new_l + t * new_w, new_t
        elif side == PinSide.BOTTOM.value:
            t = max(0.0, min(1.0, (opx - old_l) / old_w))
            px, py = new_l + t * new_w, new_b
        else:
            side = PinSide.LEFT.value
            t = max(0.0, min(1.0, (old_t - opy) / old_h))
            px, py = new_l, new_t - t * new_h
        px = _sw90_snap(self, px); py = _sw90_snap(self, py)
        try: p.side = side
        except Exception: pass
        p.x, p.y = px, py
        # Pin length and labels/text offsets are preserved; only their owner pin
        # moves to the new outline location.
        try: _sw86_move_pin_texts_keep_offsets(p, opx, opy, px, py)
        except Exception: pass


def _sw90_text_delta(old_outline, new_outline, block_x, block_y):
    old_l, old_t, old_r, old_b = old_outline
    new_l, new_t, new_r, new_b = new_outline
    old_cx, old_cy = (old_l + old_r) / 2.0, (old_t + old_b) / 2.0
    new_cx, new_cy = (new_l + new_r) / 2.0, (new_t + new_b) / 2.0
    # Move a text block with the closest BODY outline side.  It is a pure
    # translation; no scale, no spacing and no font size changes.
    x = _sw86_float(block_x); y = _sw86_float(block_y)
    dx = (new_l - old_l) if x < old_cx else (new_r - old_r)
    dy = (new_t - old_t) if y > old_cy else (new_b - old_b)
    # If the block lies horizontally inside the body range, center translation
    # is visually cleaner. Same for vertical inside range.
    if old_l <= x <= old_r:
        dx = new_cx - old_cx
    if old_b <= y <= old_t:
        dy = new_cy - old_cy
    return dx, dy


def _sw90_move_text_block(self, entries, old_outline, new_outline):
    entries = list(entries or [])
    if not entries:
        return
    try:
        bx = (min(_sw86_float(x) for _, x, _ in entries) + max(_sw86_float(x) for _, x, _ in entries)) / 2.0
        by = (min(_sw86_float(y) for _, _, y in entries) + max(_sw86_float(y) for _, _, y in entries)) / 2.0
    except Exception:
        try: bx, by = entries[0][1], entries[0][2]
        except Exception: return
    dx, dy = _sw90_text_delta(old_outline, new_outline, bx, by)
    for t, tx, ty in entries:
        try:
            t.x = _sw90_snap(self, _sw86_float(tx) + dx)
            t.y = _sw90_snap(self, _sw86_float(ty) + dy)
        except Exception:
            pass


def _sw90_scale_current_unit_children_from_body_resize(self, start_state, body):
    if not isinstance(start_state, dict) or 'outline' not in start_state:
        start_state = _sw90_snapshot_body_resize_state(self, body)
    old_outline = start_state.get('outline') or _sw90_rect_outline_from_body(body)
    _sw90_apply_body_artwork_resize(self, start_state, body)
    new_outline = _sw90_visible_body_outline(self, _sw90_unit(self), body)
    _sw90_redock_pins(self, start_state, body)
    _sw90_move_text_block(self, start_state.get('attributes', []) or [], old_outline, new_outline)
    _sw90_move_text_block(self, start_state.get('texts', []) or [], old_outline, new_outline)
    try:
        self.update_current_unit_canvas_positions()
    except Exception:
        try: self.scene.update(); self.view.viewport().update()
        except Exception: pass


def _sw90_transform_unit_as_body_group(self, op, value=None, refresh=True):
    if op not in ('scale', 'scale_x_to', 'scale_y_to'):
        # Keep the already-good rotate/flip origin behaviour.
        try:
            return _sw86_prev_transform_unit_as_body_group(self, op, value, refresh)
        except Exception:
            return None
    u = _sw90_unit(self)
    if u is None:
        return None
    body = u.body
    st = _sw90_snapshot_body_resize_state(self, body)
    old_l, old_t, old_r, old_b = st.get('outline') or _sw90_rect_outline_from_body(body)
    old_w = max(_sw90_step(self), abs(old_r - old_l)); old_h = max(_sw90_step(self), abs(old_t - old_b))
    if op == 'scale_x_to':
        new_w = max(_sw90_step(self), _sw90_snap(self, value)); new_h = old_h
    elif op == 'scale_y_to':
        new_w = old_w; new_h = max(_sw90_step(self), _sw90_snap(self, value))
    else:
        f = _sw86_float(value, 1.0)
        new_w = max(_sw90_step(self), _sw90_snap(self, old_w * f))
        new_h = max(_sw90_step(self), _sw90_snap(self, old_h * f))
    cx, cy = (old_l + old_r) / 2.0, (old_t + old_b) / 2.0
    body.x = _sw90_snap(self, cx - new_w / 2.0)
    body.y = _sw90_snap(self, cy + new_h / 2.0)
    body.width = new_w; body.height = new_h
    _sw90_scale_current_unit_children_from_body_resize(self, st, body)
    if refresh:
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.schedule_scene_refresh(visual_only=True)
        except Exception: pass
        try: QTimer.singleShot(0, self.refresh_properties)
        except Exception: pass
    return None


def _sw90_dock_pins_to_body(self, unit):
    if unit is None or getattr(unit, 'body', None) is None:
        return
    old_unit = None
    try:
        old_unit = getattr(self, 'current_unit', None)
        self.current_unit = unit
    except Exception:
        pass
    try:
        st = _sw90_snapshot_body_resize_state(self, unit.body)
        _sw90_redock_pins(self, st, unit.body)
    finally:
        try:
            if old_unit is not None:
                self.current_unit = old_unit
        except Exception:
            pass

try:
    MainWindow._snapshot_body_resize_state = _sw90_snapshot_body_resize_state
    MainWindow.scale_current_unit_children_from_body_resize = _sw90_scale_current_unit_children_from_body_resize
    MainWindow._transform_unit_as_body_group = _sw90_transform_unit_as_body_group
    MainWindow.dock_pins_to_body = _sw90_dock_pins_to_body
    if 'TemplateEditorDialog' in globals():
        TemplateEditorDialog._snapshot_body_resize_state = _sw90_snapshot_body_resize_state
        TemplateEditorDialog.scale_current_unit_children_from_body_resize = _sw90_scale_current_unit_children_from_body_resize
        TemplateEditorDialog._transform_unit_as_body_group = _sw90_transform_unit_as_body_group
        TemplateEditorDialog.dock_pins_to_body = _sw90_dock_pins_to_body
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v92: use Symbol-1 BODY scaling pipeline for imported/templates too
# ---------------------------------------------------------------------------
# The v90 pipeline worked for the native Symbol 1 body, but imported/template
# bodies can have graphics without a fully normalized role/lock marker and pins
# with unreliable side values.  This patch makes BODY artwork detection and pin
# side anchoring geometry-driven first, so all symbol sources follow the same
# resize/reanchor path.

def _sw92_is_user_graphic(g):
    try:
        role = str(getattr(g, 'graphic_role', '') or '').lower()
        raw = str(getattr(g, 'mentor_raw', '') or '')
        return role == 'user_graphic' or raw == '__USER_GRAPHIC__'
    except Exception:
        return False


def _sw92_is_body_graphic_for_unit(self, unit, g):
    try:
        if g is None or _sw92_is_user_graphic(g):
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


def _sw92_body_graphics(self, unit):
    out = []
    try:
        for g in getattr(unit, 'graphics', []) or []:
            if _sw92_is_body_graphic_for_unit(self, unit, g):
                out.append(g)
    except Exception:
        pass
    return out


def _sw92_visible_body_outline(self, unit, body):
    bounds = []
    try:
        for g in _sw92_body_graphics(self, unit):
            b = _sw90_graphic_outline(g)
            if b is not None:
                bounds.append(b)
    except Exception:
        pass
    if bounds:
        l = min(v[0] for v in bounds); t = max(v[1] for v in bounds)
        r = max(v[2] for v in bounds); b = min(v[3] for v in bounds)
        if abs(r - l) > 1e-9 and abs(t - b) > 1e-9:
            return l, t, r, b
    return _sw90_rect_outline_from_body(body)


def _sw92_side_for_pin(pin, old_outline, stored_side=None):
    # Geometry wins over possibly stale imported/template side metadata.  This
    # prevents right-side imported pins from being redocked to the left side.
    try:
        l, t, r, b = old_outline
        px = _sw86_float(getattr(pin, 'x', 0.0)); py = _sw86_float(getattr(pin, 'y', 0.0))
        distances = [
            (abs(px - l), PinSide.LEFT.value),
            (abs(px - r), PinSide.RIGHT.value),
            (abs(py - t), PinSide.TOP.value),
            (abs(py - b), PinSide.BOTTOM.value),
        ]
        nearest_d, nearest_side = min(distances, key=lambda z: z[0])
        # Trust stored side only when the pin is not clearly closer to another
        # outline edge.  One edit-grid tolerance handles snapped imported data.
        s = str(stored_side or getattr(pin, 'side', '') or '').lower()
        step = 1.0
        if s in (PinSide.LEFT.value, PinSide.RIGHT.value, PinSide.TOP.value, PinSide.BOTTOM.value):
            side_dist = {
                PinSide.LEFT.value: abs(px - l),
                PinSide.RIGHT.value: abs(px - r),
                PinSide.TOP.value: abs(py - t),
                PinSide.BOTTOM.value: abs(py - b),
            }.get(s, nearest_d)
            if side_dist <= nearest_d + step:
                return s
        return nearest_side
    except Exception:
        try:
            s = str(stored_side or getattr(pin, 'side', '') or '').lower()
            if s in (PinSide.LEFT.value, PinSide.RIGHT.value, PinSide.TOP.value, PinSide.BOTTOM.value):
                return s
        except Exception:
            pass
        return PinSide.LEFT.value


def _sw92_snapshot_body_resize_state(self, body=None):
    u = _sw90_unit(self)
    if u is None:
        return {}
    b = body or getattr(u, 'body', None)
    if b is None:
        return {}
    outline = _sw92_visible_body_outline(self, u, b)
    return {
        'x': _sw86_float(getattr(b, 'x', 0.0)),
        'y': _sw86_float(getattr(b, 'y', 0.0)),
        'w': max(_sw90_step(self), abs(_sw86_float(getattr(b, 'width', 1.0), 1.0))),
        'h': max(_sw90_step(self), abs(_sw86_float(getattr(b, 'height', 1.0), 1.0))),
        'outline': outline,
        'pins': [(p, _sw86_float(getattr(p, 'x', 0.0)), _sw86_float(getattr(p, 'y', 0.0)), _sw86_float(getattr(p, 'length', 1.0), 1.0), str(getattr(p, 'side', '') or '')) for p in getattr(u, 'pins', []) or []],
        'texts': [(t, _sw86_float(getattr(t, 'x', 0.0)), _sw86_float(getattr(t, 'y', 0.0))) for t in getattr(u, 'texts', []) or []],
        'attributes': [(t, _sw86_float(getattr(t, 'x', 0.0)), _sw86_float(getattr(t, 'y', 0.0))) for t in (getattr(getattr(u, 'body', None), 'attribute_texts', {}) or {}).values()],
        'graphics': [(gr, _sw86_float(getattr(gr, 'x', 0.0)), _sw86_float(getattr(gr, 'y', 0.0)), _sw86_float(getattr(gr, 'w', 0.0)), _sw86_float(getattr(gr, 'h', 0.0))) for gr in getattr(u, 'graphics', []) or []],
    }


def _sw92_apply_body_artwork_resize(self, start_state, body):
    u = _sw90_unit(self)
    if u is None:
        return
    step = _sw90_step(self)
    old_left, old_top, old_right, old_bottom = (start_state or {}).get('outline') or _sw90_rect_outline_from_body(body)
    old_w = max(step, abs(old_right - old_left)); old_h = max(step, abs(old_top - old_bottom))
    new_left = _sw90_snap(self, getattr(body, 'x', old_left))
    new_top = _sw90_snap(self, getattr(body, 'y', old_top))
    new_w = max(step, _sw90_snap(self, abs(_sw86_float(getattr(body, 'width', old_w), old_w))))
    new_h = max(step, _sw90_snap(self, abs(_sw86_float(getattr(body, 'height', old_h), old_h))))
    body.x, body.y, body.width, body.height = new_left, new_top, new_w, new_h
    sx = new_w / old_w; sy = new_h / old_h
    has_body_graphics = False
    for gr, gx, gy, gw, gh in (start_state or {}).get('graphics', []) or []:
        try:
            if not _sw92_is_body_graphic_for_unit(self, u, gr):
                continue
            has_body_graphics = True
            gr.x = _sw90_snap(self, new_left + (_sw86_float(gx) - old_left) * sx)
            gr.y = _sw90_snap(self, new_top + (_sw86_float(gy) - old_top) * sy)
            gr.w = max(step, _sw90_snap(self, _sw86_float(gw) * sx))
            gr.h = max(step, _sw90_snap(self, _sw86_float(gh) * sy))
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
            l, t, r, btm = _sw92_visible_body_outline(self, u, body)
            body.x = _sw90_snap(self, l); body.y = _sw90_snap(self, t)
            body.width = max(step, _sw90_snap(self, r - l))
            body.height = max(step, _sw90_snap(self, t - btm))
        except Exception:
            pass


def _sw92_redock_pins(self, start_state, body):
    u = _sw90_unit(self)
    if u is None:
        return
    pins = list(getattr(u, 'pins', []) or [])
    if not pins:
        return
    step = _sw90_step(self)
    old_outline = (start_state or {}).get('outline') or _sw90_rect_outline_from_body(body)
    old_l, old_t, old_r, old_b = old_outline
    old_w = max(step, abs(old_r - old_l)); old_h = max(step, abs(old_t - old_b))
    new_l, new_t, new_r, new_b = _sw92_visible_body_outline(self, u, body)
    new_l = _sw90_snap(self, new_l); new_r = _sw90_snap(self, new_r)
    new_t = _sw90_snap(self, new_t); new_b = _sw90_snap(self, new_b)
    new_w = max(step, abs(new_r - new_l)); new_h = max(step, abs(new_t - new_b))
    old_pos = {}; old_side = {}
    for row in (start_state or {}).get('pins', []) or []:
        try:
            p = row[0]; k = id(p)
            old_pos[k] = (_sw86_float(row[1]), _sw86_float(row[2]))
            old_side[k] = row[4] if len(row) > 4 else str(getattr(p, 'side', '') or '')
        except Exception:
            pass
    for p in pins:
        k = id(p)
        opx, opy = old_pos.get(k, (_sw86_float(getattr(p, 'x', 0.0)), _sw86_float(getattr(p, 'y', 0.0))))
        # Use a lightweight temporary view with the old position for geometric
        # side detection; the pin object may already have moved during drag.
        try:
            old_px, old_py = getattr(p, 'x', None), getattr(p, 'y', None)
            p.x, p.y = opx, opy
            side = _sw92_side_for_pin(p, old_outline, old_side.get(k))
            p.x, p.y = old_px, old_py
        except Exception:
            side = _sw92_side_for_pin(p, old_outline, old_side.get(k))
        if side == PinSide.RIGHT.value:
            ratio = max(0.0, min(1.0, (old_t - opy) / old_h)); px, py = new_r, new_t - ratio * new_h
        elif side == PinSide.TOP.value:
            ratio = max(0.0, min(1.0, (opx - old_l) / old_w)); px, py = new_l + ratio * new_w, new_t
        elif side == PinSide.BOTTOM.value:
            ratio = max(0.0, min(1.0, (opx - old_l) / old_w)); px, py = new_l + ratio * new_w, new_b
        else:
            side = PinSide.LEFT.value
            ratio = max(0.0, min(1.0, (old_t - opy) / old_h)); px, py = new_l, new_t - ratio * new_h
        px = _sw90_snap(self, px); py = _sw90_snap(self, py)
        try: p.side = side
        except Exception: pass
        p.x, p.y = px, py
        try: _sw86_move_pin_texts_keep_offsets(p, opx, opy, px, py)
        except Exception: pass


def _sw92_scale_current_unit_children_from_body_resize(self, start_state, body):
    if not isinstance(start_state, dict) or 'outline' not in start_state:
        start_state = _sw92_snapshot_body_resize_state(self, body)
    old_outline = start_state.get('outline') or _sw90_rect_outline_from_body(body)
    _sw92_apply_body_artwork_resize(self, start_state, body)
    new_outline = _sw92_visible_body_outline(self, _sw90_unit(self), body)
    _sw92_redock_pins(self, start_state, body)
    _sw90_move_text_block(self, start_state.get('attributes', []) or [], old_outline, new_outline)
    _sw90_move_text_block(self, start_state.get('texts', []) or [], old_outline, new_outline)
    try:
        self.update_current_unit_canvas_positions()
    except Exception:
        try: self.scene.update(); self.view.viewport().update()
        except Exception: pass


def _sw92_transform_unit_as_body_group(self, op, value=None, refresh=True):
    if op not in ('scale', 'scale_x_to', 'scale_y_to'):
        try:
            return _sw86_prev_transform_unit_as_body_group(self, op, value, refresh)
        except Exception:
            return None
    u = _sw90_unit(self)
    if u is None:
        return None
    body = u.body
    st = _sw92_snapshot_body_resize_state(self, body)
    old_l, old_t, old_r, old_b = st.get('outline') or _sw90_rect_outline_from_body(body)
    old_w = max(_sw90_step(self), abs(old_r - old_l)); old_h = max(_sw90_step(self), abs(old_t - old_b))
    if op == 'scale_x_to':
        new_w = max(_sw90_step(self), _sw90_snap(self, value)); new_h = old_h
    elif op == 'scale_y_to':
        new_w = old_w; new_h = max(_sw90_step(self), _sw90_snap(self, value))
    else:
        f = _sw86_float(value, 1.0)
        new_w = max(_sw90_step(self), _sw90_snap(self, old_w * f)); new_h = max(_sw90_step(self), _sw90_snap(self, old_h * f))
    cx, cy = (old_l + old_r) / 2.0, (old_t + old_b) / 2.0
    body.x = _sw90_snap(self, cx - new_w / 2.0); body.y = _sw90_snap(self, cy + new_h / 2.0)
    body.width = new_w; body.height = new_h
    _sw92_scale_current_unit_children_from_body_resize(self, st, body)
    if refresh:
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.schedule_scene_refresh(visual_only=True)
        except Exception: pass
        try: QTimer.singleShot(0, self.refresh_properties)
        except Exception: pass
    return None


def _sw92_dock_pins_to_body(self, unit):
    if unit is None or getattr(unit, 'body', None) is None:
        return
    old_unit = None
    can_restore = False
    try:
        old_unit = getattr(self, 'current_unit', None)
        self.current_unit = unit
        can_restore = True
    except Exception:
        pass
    try:
        st = _sw92_snapshot_body_resize_state(self, unit.body)
        _sw92_redock_pins(self, st, unit.body)
    finally:
        if can_restore:
            try: self.current_unit = old_unit
            except Exception: pass

try:
    MainWindow._snapshot_body_resize_state = _sw92_snapshot_body_resize_state
    MainWindow.scale_current_unit_children_from_body_resize = _sw92_scale_current_unit_children_from_body_resize
    MainWindow._transform_unit_as_body_group = _sw92_transform_unit_as_body_group
    MainWindow.dock_pins_to_body = _sw92_dock_pins_to_body
    if 'TemplateEditorDialog' in globals():
        TemplateEditorDialog._snapshot_body_resize_state = _sw92_snapshot_body_resize_state
        TemplateEditorDialog.scale_current_unit_children_from_body_resize = _sw92_scale_current_unit_children_from_body_resize
        TemplateEditorDialog._transform_unit_as_body_group = _sw92_transform_unit_as_body_group
        TemplateEditorDialog.dock_pins_to_body = _sw92_dock_pins_to_body
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v93: TemplateEditor safety + force template/import BODY parity
# ---------------------------------------------------------------------------
# Fixes:
# - TemplateEditorDialog inherited MainWindow refresh wrappers in older patches,
#   but did not expose clear_properties(). Add the tiny compatible method so
#   opening Tools -> Symbol Templates editieren cannot crash.
# - Units loaded from template files/runtime templates are normalized with the
#   same body-owned-graphics flags as Mentor imports. This makes rebuild_scene(),
#   BodyItem selection, BODY canvas scaling and pin redocking use the same path
#   as native Symbol 1.

def _sw93_clear_properties(self):
    try:
        if not hasattr(self, 'form') or self.form is None:
            return False
        while self.form.rowCount():
            self.form.removeRow(0)
        return True
    except Exception:
        return False


def _sw93_mark_unit_as_body_graphics(unit, source='template'):
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

try:
    if 'TemplateEditorDialog' in globals():
        TemplateEditorDialog.clear_properties = _sw93_clear_properties
except Exception:
    pass

try:
    _sw93_prev_load_template_unit = MainWindow.load_template_unit
except Exception:
    _sw93_prev_load_template_unit = None


def _sw93_load_template_unit(self, key):
    if _sw93_prev_load_template_unit is None:
        return SymbolUnitModel(name=str(key or 'Template'))
    unit = _sw93_prev_load_template_unit(self, key)
    try:
        if str(key or '').strip() not in ('', '<NONE>', 'None', 'NONE'):
            unit = _sw93_mark_unit_as_body_graphics(unit, 'template')
            # Keep existing helper migration in sync when available.
            try: self._lock_template_body_graphics(unit)
            except Exception: pass
    except Exception:
        pass
    return unit

try:
    MainWindow.load_template_unit = _sw93_load_template_unit
except Exception:
    pass

# Some import paths bypass load_template_unit and append units directly. Normalize
# before every rebuild so imported/template body graphics always enter the same
# proxy/scaling path as Symbol 1.
try:
    _sw93_prev_rebuild_scene = MainWindow.rebuild_scene
except Exception:
    _sw93_prev_rebuild_scene = None


def _sw93_rebuild_scene(self, *args, **kwargs):
    try:
        units = []
        try: units = list(getattr(getattr(self, 'symbol', None), 'units', []) or [])
        except Exception: pass
        try:
            cu = getattr(self, 'current_unit', None)
            if cu is not None and cu not in units:
                units.append(cu)
        except Exception: pass
        for u in units:
            try:
                attrs = getattr(getattr(u, 'body', None), 'attributes', {}) or {}
                has_graphics = bool(getattr(u, 'graphics', []) or [])
                has_import_template_flag = any(str(attrs.get(k, '0')) == '1' for k in (
                    'TEMPLATE_GRAPHICS_AS_BODY', 'MENTOR_GRAPHICS_AS_BODY', 'MENTOR_BODY_GRAPHICS_LOCKED', 'MENTOR_HAS_BODY'))
                locked_graphics = any(bool(getattr(g, 'locked_to_body', False)) or str(getattr(g, 'graphic_role', '') or '').lower() in ('body','template_body','imported_body') for g in getattr(u, 'graphics', []) or [])
                if has_graphics and (has_import_template_flag or locked_graphics):
                    _sw93_mark_unit_as_body_graphics(u, 'template')
            except Exception:
                pass
    except Exception:
        pass
    if _sw93_prev_rebuild_scene is not None:
        return _sw93_prev_rebuild_scene(self, *args, **kwargs)

try:
    MainWindow.rebuild_scene = _sw93_rebuild_scene
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v94: hard-stop MainWindow property wrappers in TemplateEditorDialog
# ---------------------------------------------------------------------------
# Older incremental patches assigned MainWindow.refresh_properties wrappers to
# TemplateEditorDialog.  Those wrappers expect MainWindow-only members such as
# self.library and crash while opening the template editor.  The template editor
# gets an explicit, self-contained property refresher again.

def _sw94_te_clear_properties(self):
    try:
        if not hasattr(self, 'form') or self.form is None:
            return False
        while self.form.rowCount():
            self.form.removeRow(0)
        return True
    except Exception:
        return False


def _sw94_te_refresh_properties(self):
    if not _sw94_te_clear_properties(self):
        return
    try:
        sel = list(self.scene.selectedItems()) if hasattr(self, 'scene') and self.scene is not None else []
    except Exception:
        sel = []
    try:
        if len(sel) > 1:
            self.form.addRow(QLabel(f'{len(sel)} objects selected'))
            pins = [i for i in sel if i.data(0) == 'PIN']
            texts = [i for i in sel if i.data(0) in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY')]
            graphics = [i for i in sel if i.data(0) == 'GRAPHIC']
            if len(pins) == len(sel) and hasattr(self, '_set_selected_pins_attr'):
                self.form.addRow(QLabel(f'<b>Multi-Edit: {len(pins)} PINs</b>'))
                fn = QLineEdit('')
                fn.setPlaceholderText('Set Pin Function for all selected pins')
                fn.returnPressed.connect(lambda editor=fn, items=pins: self._set_selected_pins_attr(items, 'function', editor.text()))
                self.form.addRow('Pin Function', fn)
            elif len(texts) == len(sel) and hasattr(self, '_template_multi_text_props'):
                self.form.addRow(QLabel(f'<b>Multi-Edit: {len(texts)} text objects</b>'))
                self._template_multi_text_props(texts)
            elif len(graphics) == len(sel):
                self.form.addRow(QLabel(f'<b>Multi-Edit: {len(graphics)} graphic objects</b>'))
                if hasattr(self, '_common_graphic_value') and hasattr(self, '_set_selected_graphics_style'):
                    self.form.addRow('Line width', self._dbl(float(self._common_graphic_value(graphics, 'line_width', 0.03) or 0.03), lambda v, items=graphics: self._set_selected_graphics_style(items, 'line_width', float(v)), .01, 1, .01))
            else:
                self.form.addRow(QLabel('Multi-edit is only available for same-type selections.'))
            return
        if not sel:
            self.form.addRow(QLabel('No selection. Template canvas is independent from the Symbol Wizard.'))
            try:
                body = getattr(getattr(self, 'unit', None), 'body', None)
                attrs = getattr(body, 'attributes', {}) or {}
                if attrs:
                    self.form.addRow(QLabel('<b>Template Attribute Visibility</b>'))
                    for k in list(attrs.keys()):
                        row = QWidget(); l = QHBoxLayout(row); l.setContentsMargins(0,0,0,0)
                        cb = QCheckBox('visible')
                        cb.setChecked((getattr(body, 'visible_attributes', {}) or {}).get(k, False))
                        preview = QLabel((f"{k}: {attrs.get(k, '')}" if str(attrs.get(k, '')).strip() else str(k)))
                        if hasattr(self, '_set_attr_vis'):
                            cb.toggled.connect(lambda v, key=k: self._set_attr_vis(key, v))
                        l.addWidget(cb); l.addWidget(preview); self.form.addRow(k, row)
            except Exception:
                pass
            return
        item = sel[0]
        kind = item.data(0)
        m = getattr(item, 'model', None)
        self.form.addRow(QLabel(f'<b>{kind}</b>'))
        if m is None:
            return
        if kind == 'BODY':
            self.form.addRow('Width [grid]', self._dbl(getattr(m, 'width', 1.0), lambda v, model=m: self._set_body_width_grid(model, v) if hasattr(self, '_set_body_width_grid') else self._set(model, 'width', float(v)), 0.01, 500, getattr(self, 'edit_grid_step', 1)))
            self.form.addRow('Height [grid]', self._dbl(getattr(m, 'height', 1.0), lambda v, model=m: self._set_body_height_grid(model, v) if hasattr(self, '_set_body_height_grid') else self._set(model, 'height', float(v)), 0.01, 500, getattr(self, 'edit_grid_step', 1)))
            try:
                self.form.addRow('Line style', self._combo([x.value for x in LineStyle], getattr(m, 'line_style', LineStyle.SOLID.value), lambda v, model=m: self._set(model, 'line_style', v)))
            except Exception:
                pass
            self.form.addRow('Line width', self._dbl(getattr(m, 'line_width', 0.03), lambda v, model=m: self._set(model, 'line_width', float(v)), .01, 1, .01))
            self.form.addRow('Rotation [deg]', self._dbl(getattr(m, 'rotation', 0), lambda v, model=m: self._set_body_rotation_90(model, v) if hasattr(self, '_set_body_rotation_90') else self._set(model, 'rotation', float(v)), 0, 270, 90))
            try:
                self.form.addRow('Color', self._color_button_row('Color RGB', getattr(m, 'color', (0,0,0)), lambda _checked=False, model=m: self.color_model(model)))
            except Exception:
                pass
            try:
                attrs = getattr(m, 'attributes', {}) or {}
                if attrs:
                    self.form.addRow(QLabel('<b>Displayed Attributes</b>'))
                    for k in list(attrs.keys()):
                        row = QWidget(); l = QHBoxLayout(row); l.setContentsMargins(0,0,0,0)
                        cb = QCheckBox('visible'); cb.setChecked((getattr(m, 'visible_attributes', {}) or {}).get(k, False))
                        ed = QLineEdit(str(attrs.get(k, '')))
                        if hasattr(self, '_set_attr_vis'):
                            cb.toggled.connect(lambda v, key=k: self._set_attr_vis(key, v))
                        if hasattr(self, '_set_attr_val'):
                            ed.editingFinished.connect(lambda key=k, e=ed: self._set_attr_val(key, e.text()))
                        l.addWidget(cb); l.addWidget(ed); self.form.addRow(k, row)
            except Exception:
                pass
        elif kind == 'PIN':
            for lab, attr in [('Number','number'), ('Name','name'), ('Function','function')]:
                self.form.addRow(lab, self._line(getattr(m, attr, ''), lambda v, a=attr, model=m: self._set(model, a, v)))
            try: self.form.addRow('Pin Type', self._combo([x.value for x in PinType], getattr(m, 'pin_type', ''), lambda v, model=m: self._set(model, 'pin_type', v)))
            except Exception: pass
            try: self.form.addRow('Side', self._combo([x.value for x in PinSide], getattr(m, 'side', ''), lambda v, model=m: self._set_pin_side(model, v) if hasattr(self, '_set_pin_side') else self._set(model, 'side', v)))
            except Exception: pass
            inv = QCheckBox(); inv.setChecked(bool(getattr(m, 'inverted', False))); inv.toggled.connect(lambda v, model=m: self._set(model, 'inverted', v)); self.form.addRow('Inverted', inv)
            self.form.addRow('Length', self._dbl(getattr(m, 'length', 1.0), lambda v, model=m: self._set(model, 'length', float(v)), 0.5, 100))
        elif kind in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY'):
            is_attr = kind in ('ATTR_REF_DES', 'ATTR_BODY') or bool(getattr(m, '_is_attribute_text', False))
            line = self._line(getattr(m, 'text', ''), lambda v, item=item: self._set_text_item_attr(item, 'text', v)) if is_attr else self._plain_text_editor(getattr(m, 'text', ''), lambda v, item=item: self._set_text_item_attr(item, 'text', v))
            if is_attr and hasattr(line, 'setReadOnly'):
                line.setReadOnly(True)
            self.form.addRow('Text', line)
            self.form.addRow('Size grid', self._dbl(getattr(m, 'font_size_grid', 0.5), lambda v, item=item: self._set_text_item_attr(item, 'font_size_grid', float(v)), .1, 10))
            self.form.addRow('Rotation [deg]', self._dbl(getattr(m, 'rotation', 0), lambda v, item=item: self._set_text_item_attr(item, 'rotation', float(v)), -360, 360, 15))
        elif kind == 'GRAPHIC':
            self.form.addRow('Shape', self._combo(['line','rect','ellipse'], getattr(m, 'shape', 'rect'), lambda v, model=m: self._set_graphic_shape_and_refresh(model, v) if hasattr(self, '_set_graphic_shape_and_refresh') else self._set(model, 'shape', v)))
            self.form.addRow('X', self._dbl(getattr(m, 'x', 0), lambda v, model=m: self._set(model, 'x', round(float(v))), -500, 500, 1))
            self.form.addRow('Y', self._dbl(getattr(m, 'y', 0), lambda v, model=m: self._set(model, 'y', round(float(v))), -500, 500, 1))
            self.form.addRow('Width', self._dbl(getattr(m, 'w', 1), lambda v, model=m: self._set(model, 'w', round(float(v))), -500, 500, 1))
            self.form.addRow('Height', self._dbl(getattr(m, 'h', 1), lambda v, model=m: self._set(model, 'h', round(float(v))), -500, 500, 1))
            if getattr(m, 'shape', '') == 'line':
                self.form.addRow('Curve radius', self._dbl(getattr(m, 'curve_radius', 0), lambda v, model=m: self._set(model, 'curve_radius', float(v)), -100, 100, .1))
            self.form.addRow('Rotation [deg]', self._dbl(getattr(m, 'rotation', 0), lambda v, model=m: self._set(model, 'rotation', float(v)), -360, 360, 15))
    except Exception as exc:
        try:
            self.form.addRow(QLabel(f'Property panel error: {exc}'))
        except Exception:
            pass

try:
    if 'TemplateEditorDialog' in globals():
        TemplateEditorDialog.clear_properties = _sw94_te_clear_properties
        TemplateEditorDialog.refresh_properties = _sw94_te_refresh_properties
except Exception:
    pass
