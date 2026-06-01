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
