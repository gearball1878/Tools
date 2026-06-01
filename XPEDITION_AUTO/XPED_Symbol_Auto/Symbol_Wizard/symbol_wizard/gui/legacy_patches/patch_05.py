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
