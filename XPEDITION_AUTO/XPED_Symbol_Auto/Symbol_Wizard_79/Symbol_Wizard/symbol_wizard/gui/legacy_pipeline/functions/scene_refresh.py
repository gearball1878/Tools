"""Scene rebuild, property refresh and canvas synchronization helpers.

Executed in the shared ``main_window.py`` global namespace by ``legacy_updates.apply_legacy_updates``.
"""

from __future__ import annotations

def _compat_1237(orig):
    def wrapper(self, *args, **kwargs):
        try:
            # Keep logical BODY equal to graphics extents before drawing in both editors.
            _compat_1239(self, self.current_unit)
        except Exception:
            pass
        return orig(self, *args, **kwargs)
    return wrapper

def _compat_0325(orig):
    def wrapper(self, *args, **kwargs):
        try: _compat_0334(self, getattr(self, 'current_unit', None) or getattr(self, 'unit', None))
        except Exception: pass
        return orig(self, *args, **kwargs)
    return wrapper

def _compat_0401(orig):
    def wrapper(self, *args, **kwargs):
        try:
            _compat_0400(self, getattr(self, 'current_unit', None) or getattr(self, 'unit', None))
        except Exception:
            pass
        return orig(self, *args, **kwargs)
    return wrapper

def _compat_0717(self):
    # If several BODY_GRAPHIC primitives became selected by rubber-band or stale
    # restore ids, collapse them to one logical BODY before building the panel.
    try:
        selected = list(self.scene.selectedItems())
        bg = [i for i in selected if _compat_0713(i)]
        if len(bg) > 1 and len(bg) == len(selected):
            self.scene.blockSignals(True)
            self.scene.clearSelection()
            bg[0].setSelected(True)
            self.scene.blockSignals(False)
    except Exception:
        try: self.scene.blockSignals(False)
        except Exception: pass
    if _compat_0716 is not None:
        return _compat_0716(self)

def _compat_0341(self):
    return self.delete_all_symbols()

def _compat_0358(self, ids=None):
    ids = set(ids or _compat_0364(self) or getattr(self, '_selection_restore_ids', set()) or [])
    def run():
        try: _compat_0361(self, ids)
        except Exception: pass
        try: self.refresh_properties()
        except RuntimeError: pass
        except Exception: pass
    try: QTimer.singleShot(0, run)
    except Exception: run()

def _compat_0413(self):
    # TemplateEditorDialog must fall back to its own native property renderer,
    # not to the MainWindow refresh captured in the shared legacy stream.
    # Otherwise property-widget edits clear the form and then fail on
    # MainWindow-only state such as self.library, leaving the right panel blank.
    if getattr(self, 'is_template_editor', False):
        base_refresh = globals().get('_template_editor_base_refresh_properties')
        if base_refresh is not None:
            try:
                return base_refresh(self)
            except Exception as exc:
                try:
                    if hasattr(self, 'clear_properties') and self.clear_properties():
                        self.form.addRow(QLabel(f'Property panel update failed: {exc}'))
                except Exception:
                    pass
                return None
    r = None
    if _compat_0411 is not None:
        r = _compat_0411(self)
    try:
        k = _compat_0412(self)
        if k:
            self._compat_0410 = k
    except Exception:
        pass
    return r

def _compat_0524(self):
    out = []
    try: items = list(self.scene.items()) if getattr(self, 'scene', None) else []
    except Exception: items = []
    for it in items:
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None and _compat_0531(it.model):
                out.append(it)
        except Exception:
            pass
    return out

def _compat_0542(self):
    # Collapse selected members of the same graphic group into a single logical
    # property view. This prevents the old "N objects selected" panel for groups.
    try:
        selected = [i for i in self.scene.selectedItems()]
        graphic_items = [i for i in selected if i.data(0) == 'GRAPHIC' and getattr(i, 'model', None) is not None]
        gids = {_compat_0527(i.model) for i in graphic_items if _compat_0527(i.model)}
        if graphic_items and len(gids) == 1 and len(graphic_items) == len(selected):
            _compat_0548(self)
            models = _compat_0546(self, expand_groups=True)
            b = _compat_0530(models)
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
    if _compat_0539:
        return _compat_0539(self)

def _compat_0567(self):
    out = []
    try: items = list(self.scene.items()) if getattr(self, 'scene', None) else []
    except Exception: items = []
    for it in items:
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None and _compat_0574(it.model):
                out.append(it)
        except Exception:
            pass
    return out

def _compat_0588(self, models):
    rect = None
    for gr in models:
        it = _compat_0575(self, gr)
        if it is None:
            continue
        try:
            r = it.sceneBoundingRect()
            rect = QRectF(r) if rect is None else rect.united(r)
        except Exception:
            pass
    return rect

def _compat_0211(self):
    if not hasattr(self, 'unit_tabs'):
        return
    self.unit_tabs.blockSignals(True)
    try:
        self.unit_tabs.clear()
        if not getattr(self.library, 'symbols', []) or not _compat_0231(self):
            self.current_unit_index = 0
            self.unit_tabs.setEnabled(False)
            if hasattr(self, 'add_unit_button'):
                self.add_unit_button.setEnabled(False)
            return
        for u in self.symbol.units:
            self.unit_tabs.addTab(QWidget(), u.name)
        self.current_unit_index = max(0, min(self.current_unit_index, len(self.symbol.units) - 1))
        self.unit_tabs.setCurrentIndex(self.current_unit_index)
        self.unit_tabs.setEnabled(True)
        if hasattr(self, 'add_unit_button'):
            self.add_unit_button.setEnabled(True)
    finally:
        self.unit_tabs.blockSignals(False)
    try:
        self.update_name_editors()
    except Exception:
        pass

def _compat_0210(self):
    _compat_0207(self)
    _compat_0201(self)

def _compat_0209(self):
    _compat_0206(self)
    try:
        _compat_0201(self)
        # When no symbols or a single symbol is active, no split-part tabs should remain.
        if not getattr(self.library, 'symbols', []) or not _compat_0231(self):
            self.rebuild_unit_tabs()
    except Exception:
        pass

def _compat_0214(self):
    if getattr(self, '_property_refresh_pending', False):
        return
    self._property_refresh_pending = True
    def _do():
        self._property_refresh_pending = False
        try:
            self.refresh_properties()
        except Exception:
            pass
    _compat_0035.singleShot(25, _do)

def _compat_0199(self):
    # During multi/group drag the view handles all visual movement and commits once.
    if getattr(self, '_group_drag_visual_only', False) or getattr(self, '_suspend_heavy_canvas_sync', False):
        try:
            self.live_refresh()
        except Exception:
            pass
        return
    try:
        self.live_refresh()
    except Exception:
        pass
    try:
        self.schedule_property_refresh()
    except Exception:
        pass

def _compat_0245(self, *, scene=True, tree=True, pins=True, units=True, canvas=True, names=False):
    old_updates = None
    try:
        old_updates = self.updatesEnabled()
        self.setUpdatesEnabled(False)
    except Exception:
        pass
    try:
        if canvas:
            self.rebuild_canvas_tabs()
        if units:
            self.rebuild_unit_tabs()
        if scene:
            self.rebuild_scene()
        if tree:
            self.rebuild_tree()
            pins = False
        if pins:
            self.rebuild_pin_table()
        if names:
            self.update_name_editors()
        try:
            _compat_0234(self)
        except Exception:
            pass
    finally:
        try:
            self.setUpdatesEnabled(True if old_updates is None else old_updates)
            self.update()
        except Exception:
            pass

def _compat_0243(self):
    old_updates = None
    try:
        old_updates = self.updatesEnabled()
        self.setUpdatesEnabled(False)
    except Exception:
        pass
    try:
        _compat_0239(self)
        _compat_0234(self)
    finally:
        try:
            self.setUpdatesEnabled(True if old_updates is None else old_updates)
            self.update()
        except Exception:
            pass

def _compat_0244(self):
    _compat_0240(self)
    try:
        _compat_0234(self)
    except Exception:
        pass

def _compat_0233(self):
    if getattr(self, '_fast_drag_active', False) or getattr(self, '_suspend_heavy_canvas_sync', False):
        try:
            if hasattr(self, 'view'):
                self.view.viewport().update()
        except Exception:
            pass
        return
    return _compat_0238(self)

def _compat_0246(self):
    if getattr(self, '_fast_drag_active', False) or getattr(self, '_suspend_heavy_canvas_sync', False):
        return
    return _compat_0241(self)

def _compat_1020(self):
    try:
        for t in getattr(getattr(self, 'current_unit', None), 'texts', []) or []:
            setattr(t, '_is_attribute_text', False)
            setattr(t, '_attribute_key', '')
    except Exception:
        pass
    return _compat_1017(self)

def _compat_1059(self):
    try:
        u = _compat_1068(self)
        for t in getattr(u, 'texts', []) or []:
            setattr(t, '_is_attribute_text', False)
            setattr(t, '_attribute_key', '')
    except Exception:
        pass
    return _compat_1053(self)

def _compat_1133(self, *args, **kwargs):
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
                    _compat_1130(u, 'template')
            except Exception:
                pass
    except Exception:
        pass
    if _compat_1132 is not None:
        return _compat_1132(self, *args, **kwargs)

def _compat_0832(self):
    # Large symbols/multi-select should not rebuild the property panel on every
    # mouse-move.  Coalesce updates into a short idle window.
    if getattr(self, '_property_refresh_pending', False):
        return
    self._property_refresh_pending = True
    def _do():
        self._property_refresh_pending = False
        try:
            if not self._property_editor_has_focus():
                self.refresh_properties()
        except Exception:
            pass
    try:
        QTimer.singleShot(120, _do)
    except Exception:
        if _compat_0827 is not None:
            _compat_0827(self)

def _compat_0819(self):
    # Visual update + delayed properties + auto-scroll.  Avoid tree/pin-table
    # rebuilds during interactive mouse movement.
    try:
        self.live_refresh()
    except Exception:
        pass
    try:
        _compat_0832(self)
    except Exception:
        pass
    try:
        _compat_0818(self)
    except Exception:
        pass

def _compat_0841(self):
    try:
        self.live_refresh()
    except Exception:
        pass
    try:
        self.schedule_property_refresh()
    except Exception:
        pass

def _compat_0840(self):
    # Coalesce viewport repaints aggressively for large symbols and multi-select
    # drags.  A full scene rebuild is still performed on mouse release by the
    # existing item logic where needed.
    if getattr(self, '_live_refresh_pending', False):
        return
    self._live_refresh_pending = True
    def _do():
        self._live_refresh_pending = False
        try:
            if hasattr(self, 'view'):
                self.view.viewport().update()
            elif hasattr(self, 'scene'):
                self.scene.update()
        except Exception:
            pass
    try:
        QTimer.singleShot(33, _do)
    except Exception:
        if _compat_0843 is not None:
            _compat_0843(self)

def _compat_1215(win):
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

def _compat_1210(self):
    restore_gid = getattr(self, '_compat_1213', '') or ''
    if not restore_gid:
        try:
            sg = _compat_1216(self)
            restore_gid = getattr(sg, 'group_id', '') if sg is not None else ''
        except Exception:
            restore_gid = ''
    if _compat_1207:
        _compat_1207(self)
    try:
        _compat_1201(self)
        for gid, models in _compat_1200(self).items():
            proxy = _V80GroupGraphicItem(self, gid, models)
            self.scene.addItem(proxy)
            if gid == restore_gid:
                proxy.setSelected(True)
        self._compat_1213 = ''
    except Exception as e:
        try: self.statusBar().showMessage(f'Group proxy error: {e}', 5000)
        except Exception: pass

def _compat_1211(self):
    try:
        gi = _compat_1216(self)
        if gi is not None and hasattr(self, 'form') and self.form is not None:
            while self.form.rowCount(): self.form.removeRow(0)
            self.form.addRow(_V80QLabel('<b>Selected: GRAPHIC</b>'))
            self.form.addRow(_V80QLabel('Grouped object'))
            self.form.addRow(_V80QLabel('Verhält sich wie ein einzelnes Grafikobjekt.'))
            return
    except Exception:
        pass
    return _compat_1208(self) if _compat_1208 else None
