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
