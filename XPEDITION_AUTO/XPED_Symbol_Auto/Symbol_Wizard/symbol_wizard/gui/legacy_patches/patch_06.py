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
