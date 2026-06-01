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
