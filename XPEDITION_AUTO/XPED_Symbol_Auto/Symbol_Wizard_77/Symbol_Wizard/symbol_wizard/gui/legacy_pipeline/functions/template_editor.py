"""Template editor parity and template-specific helpers.

Executed in the shared ``main_window.py`` global namespace by ``legacy_updates.apply_legacy_updates``.
"""

from __future__ import annotations

def _compat_0318(self, unit=None):
    try:
        if unit is None:
            for u in getattr(self.symbol, 'units', []) or []:
                if hasattr(u, '_body_group_transform'):
                    delattr(u, '_body_group_transform')
        elif hasattr(unit, '_body_group_transform'):
            delattr(unit, '_body_group_transform')
    except Exception:
        pass

def _compat_0320(self):
    name = self.current_template_key()
    if not name:
        return
    self._loading_template = True
    self.unit = self.main.load_template_unit(name); self.symbol.units = [self.unit]
    try: self.unit.body.attributes['TEMPLATE_GRAPHICS_AS_BODY'] = '1'
    except Exception: pass
    try: self._lock_template_body_graphics(self.unit)
    except Exception: pass
    try: _compat_0324(self, self.unit, getattr(self.symbol, 'origin', OriginMode.CENTER.value))
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

def _compat_0402(self, deg):
    self.set_tool(DrawTool.SELECT.value)
    try: self.push_undo_state()
    except Exception: pass
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    _compat_0400(self, u)
    if _compat_0404(self):
        _compat_0335(self, 'rotate', float(deg))
    else:
        for it in self.scene.selectedItems():
            if hasattr(it, 'rotate_by'):
                it.rotate_by(float(deg))
        try: self.schedule_scene_refresh()
        except Exception: self.rebuild_scene()
    self.dirty = True

def _compat_0553(self, unit=None):
    # Do not silently renormalize on every rebuild. Origin placement is handled
    # explicitly by Origin Reset / template import. Rebuild must not undo a
    # user transform or shift imported body graphics.
    try:
        u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
        if u is not None:
            if _compat_0551(self, u):
                try: _compat_0334(self, u)
                except Exception: pass
    except Exception:
        pass

def _compat_0685(self, deg):
    _compat_0682(self, 'rotate', float(deg))

def _compat_0072(self, event):
    # Clicking imported/template BODY artwork in Symbol Wizard selects the logical
    # BODY item so canvas handles (including scale) operate exactly like Symbol 1.
    try:
        if (getattr(getattr(self, 'model', None), 'locked_to_body', False)
                and not getattr(self.window, 'is_template_editor', False)
                and event.button() == Qt.LeftButton):
            cands = _compat_0712(self.window) if '_compat_0712' in globals() else []
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
    if _compat_0075 is not None:
        return _compat_0075(self, event)

def _compat_0383(self, deg):
    return _compat_0388(self, lambda: _compat_0378(self, deg), force_body=bool(self._selected_body_active()))

def _compat_0422(self, deg):
    body_active = _compat_0420(self)
    body = getattr(getattr(self, 'current_unit', None), 'body', None)
    try:
        before = float(getattr(body, 'rotation', 0.0) or 0.0) if (body_active and body is not None) else None
    except Exception:
        before = 0.0
    result = None
    if _compat_0421 is not None:
        result = _compat_0421(self, deg)
    if body_active:
        _compat_0423(self, deg, before)
        try: self.dirty = True
        except Exception: pass
        # Rebuild the property panel asynchronously so the dropdown shows the
        # new value, while preserving the BODY selection/filter state.
        try:
            sig = _compat_0371(self) if '_compat_0371' in globals() else []
            fs = _compat_0387(self) if '_compat_0387' in globals() else None
            if '_compat_0414' in globals():
                QTimer.singleShot(0, lambda: _compat_0414(self, sig=sig, fs=fs, refresh_panel=True))
            elif '_compat_0381' in globals():
                QTimer.singleShot(0, lambda: _compat_0381(self, sig=sig, filter_state=fs, force_body=True, refresh=True))
            else:
                QTimer.singleShot(0, self.refresh_properties)
        except Exception:
            try: self.refresh_properties()
            except Exception: pass
    return result

def _compat_0439(self, gr):
    try:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body','template_body','imported_body')
    except Exception:
        return False

def _compat_0465(gr):
    try:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body','template_body','imported_body')
    except Exception:
        return False

def _compat_0487(gr):
    try:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body', 'template_body', 'imported_body', 'body_graphic')
    except Exception:
        return False

def _compat_0512(gr):
    try:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body', 'template_body', 'imported_body', 'body_graphic')
    except Exception:
        return False

def _compat_0531(gr):
    try:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body', 'template_body', 'imported_body', 'body_graphic')
    except Exception:
        return False

def _compat_0574(gr):
    try:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body', 'template_body', 'imported_body', 'body_graphic')
    except Exception:
        return False

def _compat_0599(self):
    try: self.update_current_unit_canvas_positions()
    except Exception:
        try: self.schedule_scene_refresh()
        except Exception: pass
    try: _compat_0595(self)
    except Exception: pass
    try: _compat_0598(self)
    except Exception: pass
    try: self.refresh_properties()
    except Exception: pass
    try: self.rebuild_tree()
    except Exception: pass
    try: self.scene.update(); self.view.viewport().update()
    except Exception: pass

def _compat_0598(self):
    gid = _compat_0591(self)
    if not gid:
        _compat_0563(self)
        return
    models = _compat_0590(self, expand_groups=True)
    if len(models) < 2:
        _compat_0563(self)
        return
    rect = _compat_0588(self, models)
    if rect is None or not rect.isValid():
        _compat_0563(self)
        return
    try:
        pad = max(3.0, float(getattr(self, 'grid_px', 20)) * 0.15)
        rect = rect.adjusted(-pad, -pad, pad, pad)
    except Exception:
        pass
    item = getattr(self, '_compat_0569', None)
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
            self._compat_0569 = item
        item.setRect(rect)
        item.show()
    except Exception:
        pass

def _compat_0586(self, deg):
    try:
        if self._selected_body_active():
            return _compat_0583(self, deg) if _compat_0583 else None
    except Exception:
        pass
    if _compat_0561(self, deg):
        return None
    if _compat_0583:
        return _compat_0583(self, deg)

def _compat_0585(self):
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

def _compat_0201(self):
    try:
        if hasattr(self, 'sync_active_symbol_combo'):
            return self.sync_active_symbol_combo()
    except Exception:
        pass
    combo = getattr(self, 'active_symbol_combo', None)
    if combo is None:
        return
    combo.blockSignals(True)
    try:
        combo.clear()
        for idx, sym in enumerate(getattr(self.library, 'symbols', []) or []):
            combo.addItem(_compat_0217(sym, idx), idx)
        if getattr(self.library, 'symbols', None):
            combo.setCurrentIndex(max(0, min(getattr(self.library, 'current_symbol_index', 0), combo.count() - 1)))
        combo.setEnabled(bool(getattr(self.library, 'symbols', []) or []))
    finally:
        combo.blockSignals(False)

def _compat_0234(self):
    try:
        if hasattr(self, 'sync_active_split_part_controls'):
            return self.sync_active_split_part_controls()
    except Exception:
        pass
    combo = getattr(self, 'active_split_part_combo', None)
    if combo is None:
        return
    combo.blockSignals(True)
    try:
        combo.clear()
        if not _compat_0231(self):
            combo.addItem('No split part', -1)
            combo.setEnabled(False)
            for name in ('prev_split_part_button', 'next_split_part_button'):
                b = getattr(self, name, None)
                if b is not None:
                    b.setEnabled(False)
            return
        units = list(getattr(self.symbol, 'units', []) or [])
        for idx, unit in enumerate(units):
            combo.addItem(_compat_0251(unit, idx), idx)
        if units:
            self.current_unit_index = max(0, min(getattr(self, 'current_unit_index', 0), len(units) - 1))
            combo.setCurrentIndex(self.current_unit_index)
        combo.setEnabled(len(units) > 0)
        for name in ('prev_split_part_button', 'next_split_part_button'):
            b = getattr(self, name, None)
            if b is not None:
                b.setEnabled(len(units) > 1)
    finally:
        combo.blockSignals(False)

def _compat_0250(self, direction):
    try:
        if hasattr(self, 'step_active_split_part'):
            return self.step_active_split_part(direction)
        if not _compat_0231(self):
            return
        units = list(getattr(self.symbol, 'units', []) or [])
        if not units:
            return
        self.current_unit_index = (int(getattr(self, 'current_unit_index', 0)) + int(direction)) % len(units)
        self.rebuild_workspace(units=True, canvas=True, scene=True, tree=True, pins=True, names=True)
        _compat_0234(self)
    except Exception:
        pass

def _compat_0220(self):
    self.push_undo_state()
    is_split = _compat_0231(self)
    if not is_split:
        QMessageBox.information(self, 'Split Symbol', 'Units can only be created in split symbols. Please create a New Split Symbol.')
        return
    current = self.current_unit
    new_body = copy.deepcopy(getattr(current, 'body', SymbolBodyModel()))
    try:
        new_body.attribute_texts = copy.deepcopy(getattr(current.body, 'attribute_texts', {}) or {})
    except Exception:
        pass
    new_unit = SymbolUnitModel(name=f'{self.symbol.name}_{len(self.symbol.units) + 1}', body=new_body)
    self.symbol.units.append(new_unit)
    try:
        self.symbol.kind = SymbolKind.SPLIT.value
        self.symbol.is_split = True
    except Exception:
        pass
    self.current_unit_index = len(self.symbol.units) - 1
    self.rebuild_workspace(units=True, canvas=True, scene=True, tree=True, pins=True, names=True)
    _compat_0234(self)

def _compat_0229(self, i):
    if i < 0:
        return
    if i == getattr(self, 'current_unit_index', 0):
        _compat_0234(self)
        return
    self.current_unit_index = i
    self.rebuild_workspace(units=False, canvas=True, scene=True, tree=True, pins=True, names=True)
    _compat_0234(self)

def _compat_0988(self, unit=None):
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

def _compat_1023(self):
    try:
        for t in getattr(getattr(self, 'unit', None), 'texts', []) or []:
            setattr(t, '_is_attribute_text', False)
            setattr(t, '_attribute_key', '')
    except Exception:
        pass
    return _compat_1019(self)

def _compat_1040(self):
    try:
        free = _compat_1039(self)
        if free:
            return {id(it.model) for it in free}
    except Exception:
        pass
    return _compat_1037(self)

def _compat_1065(self):
    try:
        u = _compat_1068(self)
        for t in getattr(u, 'texts', []) or []:
            setattr(t, '_is_attribute_text', False)
            setattr(t, '_attribute_key', '')
    except Exception:
        pass
    return _compat_1054(self)

def _compat_1061(self, deg):
    items = _compat_1064(self, allow_active=True)
    if items:
        self.set_tool(DrawTool.SELECT.value)
        self.push_undo_state()
        for it in items:
            try: it.rotate_by(float(deg))
            except Exception: pass
        _compat_1060(self, items)
        self.dirty = True
        return None
    return _compat_1055(self, deg)

def _compat_1073(self):
    try: _compat_1072(getattr(self, 'unit', None)); _compat_1072(getattr(self, 'current_unit', None)); _compat_1072(getattr(self, 'library', None))
    except Exception: pass
    return _compat_1070(self)

def _compat_1129(self, key):
    if _compat_1131 is None:
        return SymbolUnitModel(name=str(key or 'Template'))
    unit = _compat_1131(self, key)
    try:
        if str(key or '').strip() not in ('', '<NONE>', 'None', 'NONE'):
            unit = _compat_1130(unit, 'template')
            # Keep existing helper migration in sync when available.
            try: self._lock_template_body_graphics(unit)
            except Exception: pass
    except Exception:
        pass
    return unit

def _template_editor_block_widget_tree_signals(widget):
    try:
        widget.blockSignals(True)
    except Exception:
        pass
    try:
        children = list(widget.findChildren(QWidget))
    except Exception:
        children = []
    for child in children:
        try:
            child.blockSignals(True)
        except Exception:
            pass

def _template_editor_clear_form_safely(self):
    """Clear the Template Editor property form without firing stale editor callbacks.

    Rebuilding the form while a spin box, combo box or line edit still has focus
    can emit late value/editing signals from widgets that are about to be deleted.
    Those callbacks used to schedule another refresh in the middle of the current
    refresh and could leave the side panel empty.  Block the old widget tree
    first, then remove the rows atomically.
    """
    try:
        form = getattr(self, 'form', None)
        if form is None:
            return False
        roles = []
        try:
            roles = [QFormLayout.LabelRole, QFormLayout.FieldRole, QFormLayout.SpanningRole]
        except Exception:
            roles = []
        if roles:
            for row in range(form.rowCount()):
                for role in roles:
                    try:
                        item = form.itemAt(row, role)
                    except Exception:
                        item = None
                    widget = item.widget() if item is not None else None
                    if widget is not None:
                        _template_editor_block_widget_tree_signals(widget)
        else:
            try:
                side = getattr(self, 'props_scroll', None)
                if side is not None and side.widget() is not None:
                    _template_editor_block_widget_tree_signals(side.widget())
            except Exception:
                pass
        while form.rowCount():
            form.removeRow(0)
        return True
    except Exception:
        return False

def _template_editor_property_rows(self):
    try:
        form = getattr(self, 'form', None)
        return int(form.rowCount()) if form is not None else 0
    except Exception:
        return 0

def _template_editor_render_empty_panel_if_needed(self):
    """Repair guard for refresh paths that aborted after clearing the form."""
    try:
        if _template_editor_property_rows(self) > 0:
            return
        form = getattr(self, 'form', None)
        if form is None:
            return
        selected = []
        try:
            selected = list(self.scene.selectedItems())
        except Exception:
            selected = []
        if len(selected) == 1 and getattr(selected[0], 'data', lambda *_: None)(0) == 'GRAPHIC':
            try:
                _compat_0884(self)
                if _template_editor_property_rows(self) > 0:
                    return
            except Exception:
                pass
        if len(selected) == 1:
            item = selected[0]
            kind = getattr(item, 'data', lambda *_: 'OBJECT')(0) or 'OBJECT'
            form.addRow(QLabel(f'<b>{kind}</b>'))
            form.addRow(QLabel('Property panel refresh was deferred while the editor widget had focus. Select the item again if controls do not reappear.'))
        elif len(selected) > 1:
            form.addRow(QLabel(f'{len(selected)} objects selected'))
        else:
            form.addRow(QLabel('No selection. Template canvas is independent from the Symbol Wizard.'))
    except Exception:
        pass

def _compat_1144(self):
    return _template_editor_clear_form_safely(self)

def _compat_1145(self):
    if not _compat_1144(self):
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

def _compat_1155(self, deg):
    if _compat_1146(self, 'rotate', deg):
        return None
    if _compat_1153 is not None:
        return _compat_1153(self, deg)
    return None

def _compat_0755(unit) -> bool:
    try:
        attrs = getattr(getattr(unit, 'body', None), 'attributes', {}) or {}
        return any(str(attrs.get(k, '0')) == '1' for k in (
            'MENTOR_GRAPHICS_AS_BODY', 'MENTOR_HAS_BODY', 'MENTOR_BODY_GRAPHICS_LOCKED', 'TEMPLATE_GRAPHICS_AS_BODY'
        ))
    except Exception:
        return False

def _compat_0744(unit):
    try:
        if unit is None:
            return unit
        _compat_0753(unit, 0.1)
        _compat_0740(unit)
    except Exception:
        pass
    return unit

def _compat_0742(self, key: str):
    unit = _compat_0746(self, key) if _compat_0746 is not None else SymbolUnitModel(name=str(key or 'Template'))
    return _compat_0744(unit)

def _compat_0741(self, key: str):
    units = _compat_0745(self, key) if _compat_0745 is not None else []
    try:
        return [_compat_0744(u) for u in (units or [])]
    except Exception:
        return units

def _compat_0780(self, key: str):
    unit = _compat_0789(self, key) if _compat_0789 is not None else SymbolUnitModel(name=str(key or 'Template'))
    try:
        _compat_0800(self, unit, move_owned_text=False)
    except Exception:
        pass
    return unit

def _compat_0779(self, key: str):
    units = _compat_0788(self, key) if _compat_0788 is not None else []
    try:
        for u in units or []:
            _compat_0800(self, u, move_owned_text=False)
    except Exception:
        pass
    return units

def _compat_0885(self):
    xs, ys = [], []
    for gr in getattr(_compat_0854(self), 'graphics', []) or []:
        b = _compat_0858(gr)
        xs.extend([b['left'], b['right']])
        ys.extend([b['bottom'], b['top']])
    if xs and ys:
        return (min(xs), min(ys), max(xs), max(ys))
    body = getattr(_compat_0854(self), 'body', None)
    if body is not None:
        try:
            return (float(body.x), float(body.y) - float(body.height), float(body.x) + float(body.width), float(body.y))
        except Exception:
            pass
    return (0.0, 0.0, 0.0, 0.0)

def _compat_0855(self, items, axis):
    graphics = _compat_0860(items)
    if len(graphics) < 3:
        try:
            self.statusBar().showMessage('Select at least three graphic objects to distribute.', 3000)
        except Exception:
            pass
        return
    bounds = {g: _compat_0858(g) for g in graphics}
    key = 'cx' if axis == 'h' else 'cy'
    ordered = sorted(graphics, key=lambda g: bounds[g][key], reverse=(axis != 'h'))
    start = bounds[ordered[0]][key]
    end = bounds[ordered[-1]][key]
    step = 0.0 if len(ordered) <= 1 else (end - start) / (len(ordered) - 1)
    self.push_undo_state()
    self._selection_restore_ids = {id(g) for g in graphics}
    for idx, g in enumerate(ordered):
        target = start + idx * step
        if axis == 'h':
            _compat_0871(self, g, target - bounds[g]['cx'], 0.0)
        else:
            _compat_0871(self, g, 0.0, target - bounds[g]['cy'])
    try:
        self.update_current_unit_canvas_positions()
        self.refresh_properties()
    except Exception:
        try:
            self.rebuild_scene()
        except Exception:
            pass

def _compat_0886(self, items):
    self.form.addRow('Line width', self._dbl(float(_compat_0853(self, items, 'line_width', 0.03) or 0.03), lambda v, its=items: _compat_0882(self, its, 'line_width', float(v)), .01, 1, .01))
    try:
        self.form.addRow('Line style', self._combo([''] + [x.value for x in LineStyle], _compat_0853(self, items, 'line_style', ''), lambda v, its=items: v and _compat_0882(self, its, 'line_style', v)))
    except Exception:
        pass
    if all(getattr(i.model, 'shape', '') in ('line', 'arc') for i in items):
        self.form.addRow('Curve radius', self._dbl(float(_compat_0853(self, items, 'curve_radius', 0.0) or 0.0), lambda v, its=items: _compat_0881(self, its, 'curve_radius', float(v)), -100, 100, .1))
    self.form.addRow('Color', self._color_button_row('Stroke RGB', _compat_0853(self, items, 'stroke', (0, 0, 0)) or (0, 0, 0), lambda _checked=False, its=items: _compat_0851(self, its)))
    row = QWidget(); lay = QHBoxLayout(row); lay.setContentsMargins(0, 0, 0, 0)
    for label, mode in [('Align L', 'left'), ('Align R', 'right'), ('Align Top', 'top'), ('Align Bottom', 'bottom')]:
        b = QPushButton(label); b.clicked.connect(lambda _checked=False, its=items, m=mode: _compat_0849(self, its, m)); lay.addWidget(b)
    self.form.addRow('Arrange', row)
    row2 = QWidget(); lay2 = QHBoxLayout(row2); lay2.setContentsMargins(0, 0, 0, 0)
    for label, axis in [('Distribute H', 'h'), ('Distribute V', 'v')]:
        b = QPushButton(label); b.clicked.connect(lambda _checked=False, its=items, ax=axis: _compat_0855(self, its, ax)); lay2.addWidget(b)
    self.form.addRow('Distribute', row2)

def _compat_0884(self):
    try:
        if not hasattr(self, 'form') or self.form is None:
            return
        sel = self.scene.selectedItems()
        if len(sel) > 1 and all(getattr(i, 'data', lambda *_: None)(0) == 'GRAPHIC' for i in sel):
            _template_editor_clear_form_safely(self)
            self.form.addRow(QLabel(f'<b>Multi-Edit: {len(sel)} graphic objects</b>'))
            _compat_0886(self, sel)
            return
        if len(sel) == 1 and getattr(sel[0], 'data', lambda *_: None)(0) == 'GRAPHIC':
            item = sel[0]
            m = item.model
            _template_editor_clear_form_safely(self)
            self.form.addRow(QLabel('<b>GRAPHIC</b>'))
            step = float(getattr(self, 'edit_grid_step', 1.0) or 1.0)
            self.form.addRow('Shape', self._combo(['line', 'rect', 'ellipse'], getattr(m, 'shape', 'rect'), lambda v, model=m: self._set_graphic_shape_and_refresh(model, v) if hasattr(self, '_set_graphic_shape_and_refresh') else self._set(model, 'shape', v)))
            self.form.addRow('X', self._dbl(getattr(m, 'x', 0.0), lambda v, model=m: self._set(model, 'x', _compat_0850(self, _compat_0883(self, v))), -500, 500, step))
            self.form.addRow('Y', self._dbl(getattr(m, 'y', 0.0), lambda v, model=m: self._set(model, 'y', _compat_0850(self, _compat_0883(self, v))), -500, 500, step))
            self.form.addRow('Width', self._dbl(getattr(m, 'w', 1.0), lambda v, model=m: self._set(model, 'w', _compat_0850(self, _compat_0883(self, v))), -500, 500, step))
            self.form.addRow('Height', self._dbl(getattr(m, 'h', 1.0), lambda v, model=m: self._set(model, 'h', _compat_0850(self, _compat_0883(self, v))), -500, 500, step))
            if getattr(m, 'shape', '') in ('line', 'arc'):
                self.form.addRow('Curve radius', self._dbl(getattr(m, 'curve_radius', 0.0), lambda v, model=m: self._set(model, 'curve_radius', float(v)), -100, 100, .1))
            self.form.addRow('Line width', self._dbl(getattr(m.style, 'line_width', 0.03), lambda v, style=m.style: self._set(style, 'line_width', float(v)), .01, 1, .01))
            try:
                self.form.addRow('Line style', self._combo([x.value for x in LineStyle], getattr(m.style, 'line_style', LineStyle.SOLID.value), lambda v, style=m.style: self._set(style, 'line_style', v)))
            except Exception:
                pass
            self.form.addRow('Rotation [deg]', self._dbl(getattr(m, 'rotation', 0.0), lambda v, model=m: self._set(model, 'rotation', float(v)), -360, 360, 15))
            self.form.addRow('Color', self._color_button_row('Stroke RGB', getattr(m.style, 'stroke', (0, 0, 0)), lambda _checked=False, style=m.style: self.color_model(style, 'stroke')))
            return
    except Exception:
        pass
    if _compat_0877 is not None:
        return _compat_0877(self)

def _compat_0867(unit):
    try:
        if unit is None or getattr(unit, 'body', None) is None:
            return unit
        attrs = getattr(unit.body, 'attributes', None)
        if attrs is None:
            unit.body.attributes = {}
            attrs = unit.body.attributes
        attrs['TEMPLATE_GRAPHICS_AS_BODY'] = '1'
        attrs['MENTOR_GRAPHICS_AS_BODY'] = '1'
        attrs['MENTOR_BODY_GRAPHICS_LOCKED'] = '1'
        attrs['MENTOR_DISABLE_AUTO_DOCK'] = '1'
        for g in getattr(unit, 'graphics', []) or []:
            try:
                g.locked_to_body = True
                g.graphic_role = 'template_body'
                if str(getattr(g, 'mentor_raw', '') or '') == '__USER_GRAPHIC__':
                    g.mentor_raw = ''
            except Exception:
                pass
        for p in getattr(unit, 'pins', []) or []:
            try:
                p.auto_dock = False
            except Exception:
                pass
    except Exception:
        pass
    return unit

def _compat_0865(self, key):
    unit = _compat_0873(self, key) if _compat_0873 is not None else SymbolUnitModel(name=str(key or 'Template'))
    try:
        if str(key or '').strip() not in ('', '<NONE>', 'None', 'NONE'):
            unit = _compat_0867(unit)
            try:
                self._lock_template_body_graphics(unit)
            except Exception:
                pass
    except Exception:
        pass
    return unit

def _compat_0864(self, key):
    units = _compat_0872(self, key) if _compat_0872 is not None else []
    try:
        return [_compat_0867(u) for u in (units or [])]
    except Exception:
        return units

def _compat_0897(unit):
    vals = []
    try:
        b = unit.body
        for attr in ('x', 'y', 'width', 'height'):
            vals.append(getattr(b, attr, None))
        for t in (getattr(b, 'attribute_texts', {}) or {}).values():
            vals.extend([getattr(t, 'x', None), getattr(t, 'y', None), getattr(t, 'font_size_grid', None)])
    except Exception:
        pass
    for p in getattr(unit, 'pins', []) or []:
        for attr in ('x', 'y', 'length', 'mentor_x1', 'mentor_y1', 'mentor_x2', 'mentor_y2', 'label_x', 'label_y', 'number_x', 'number_y'):
            vals.append(getattr(p, attr, None))
    for t in getattr(unit, 'texts', []) or []:
        vals.extend([getattr(t, 'x', None), getattr(t, 'y', None), getattr(t, 'font_size_grid', None)])
    for g in getattr(unit, 'graphics', []) or []:
        for attr in ('x', 'y', 'w', 'h', 'ctrl_x', 'ctrl_y', 'curve_radius'):
            vals.append(getattr(g, attr, None))
    out = []
    for v in vals:
        try:
            if v is None:
                continue
            f = float(v)
            if math.isfinite(f):
                out.append(f)
        except Exception:
            pass
    return out

def _compat_0895(unit):
    vals = _compat_0897(unit)
    attrs = getattr(getattr(unit, 'body', None), 'attributes', {}) or {}
    mentor_like = str(attrs.get('MENTOR_GRID_UNIT', '')).strip() not in ('', '10', '10.0')
    if not vals:
        return '0.100"'
    candidates = [(1.0, '0.100"'), (0.5, '0.050"'), (0.25, '0.025"'), (0.1, '0.010"'), (0.05, '0.005"'), (0.03, '0.003"')]
    for step, text in candidates:
        if all(abs((v / step) - round(v / step)) < 1e-6 for v in vals):
            if mentor_like and step > 0.1:
                return '0.010"'
            return text
    return '0.010"' if mentor_like else '0.003"'

def _compat_0888(self):
    combo = getattr(self, 'template_grid_combo', None)
    if combo is None:
        return
    try:
        existing = {combo.itemText(i) for i in range(combo.count())}
        for text in _compat_0067:
            if text not in existing:
                combo.addItem(text)
                existing.add(text)
    except Exception:
        pass

def _compat_0893(self):
    try:
        _compat_0888(self)
        target = _compat_0895(getattr(self, 'unit', None))
        combo = getattr(self, 'template_grid_combo', None)
        if combo is not None:
            combo.blockSignals(True)
            combo.setCurrentText(target)
            combo.blockSignals(False)
        self.set_template_edit_grid(target)
    except Exception:
        pass

def _compat_pin_model_from_object(obj):
    if obj is None:
        return None
    try:
        if isinstance(obj, PinModel):
            return obj
    except Exception:
        pass
    try:
        if all(hasattr(obj, name) for name in ('number', 'side', 'length', 'pin_type')):
            return obj
    except Exception:
        pass
    try:
        if obj.data(0) == 'PIN':
            return getattr(obj, 'model', None)
    except RuntimeError:
        return None
    except Exception:
        return None
    return None


def _compat_pin_models_from_objects(objects, require_all=False):
    source = list(objects or [])
    pins = []
    for obj in source:
        pin = _compat_pin_model_from_object(obj)
        if pin is not None:
            pins.append(pin)
    if require_all and source and len(pins) != len(source):
        return []
    result = []
    seen = set()
    for pin in pins:
        ident = id(pin)
        if ident not in seen:
            result.append(pin)
            seen.add(ident)
    return result


def _compat_commit_line_edit(self, value, callback, force_first_commit=False):
    if hasattr(self, '_commit_line_edit'):
        try:
            return self._commit_line_edit(value, callback, force_first_commit=force_first_commit)
        except Exception:
            pass
    w = QLineEdit(str(value))
    w._symbol_wizard_last_committed = str(value)
    w._symbol_wizard_force_first_commit = bool(force_first_commit)
    w._symbol_wizard_commit_count = 0
    def commit(widget=w):
        text = widget.text()
        first_forced = bool(getattr(widget, '_symbol_wizard_force_first_commit', False)) and int(getattr(widget, '_symbol_wizard_commit_count', 0) or 0) == 0
        if not first_forced and getattr(widget, '_symbol_wizard_last_committed', None) == text:
            try: widget.clearFocus()
            except Exception: pass
            return
        widget._symbol_wizard_last_committed = text
        widget._symbol_wizard_commit_count = int(getattr(widget, '_symbol_wizard_commit_count', 0) or 0) + 1
        callback(text)
        try: widget.clearFocus()
        except Exception: pass
    w.returnPressed.connect(commit)
    w.editingFinished.connect(commit)
    return w


def _compat_0896(self, pins):
    pin_models = _compat_pin_models_from_objects(pins, require_all=False)
    self.form.addRow(QLabel(f'<b>Multi-Edit: {len(pin_models)} PINs</b>'))
    fn = _compat_commit_line_edit(self, '', lambda text, models=tuple(pin_models): self._set_selected_pins_attr(models, 'function', text), force_first_commit=True)
    fn.setPlaceholderText('Set Pin Function for all selected pins')
    self.form.addRow('Pin Function', fn)
    for label, attr in [('Show Number', 'visible_number'), ('Show Name', 'visible_name'), ('Show Function', 'visible_function')]:
        cb = self._multi_pin_visibility_checkbox(pin_models, attr)
        self.form.addRow(label, cb)
    step = max(0.01, float(getattr(self, 'edit_grid_step', 1.0) or 1.0))
    current_len = float(self._common_pin_value(pin_models, 'length', 1.0) or 1.0)
    self.form.addRow('Pin Length [grid]', self._dbl(current_len, lambda v, models=tuple(pin_models): self._set_selected_pins_attr(models, 'length', max(step, _compat_0850(self, _compat_0883(self, v)))), 0.01, 100, step))
    try:
        self.form.addRow('Pin Style', self._combo([''] + [x.value for x in LineStyle], self._common_pin_value(pin_models, 'line_style', ''), lambda v, models=tuple(pin_models): v and self._set_selected_pins_attr(models, 'line_style', v)))
    except Exception:
        pass
    self.form.addRow('Pin Width', self._dbl(float(self._common_pin_value(pin_models, 'line_width', 0.03) or 0.03), lambda v, models=tuple(pin_models): self._set_selected_pins_attr(models, 'line_width', float(v)), .01, 1, .01))
    self.form.addRow('Color', self._color_button_row('Color RGB', self._common_pin_value(pin_models, 'color', (0, 0, 0)) or (0, 0, 0), lambda _checked=False, models=tuple(pin_models): self.color_selected_pins(models)))

def _compat_0894(self):
    try:
        if not hasattr(self, 'form') or self.form is None:
            return
        sel = list(self.scene.selectedItems())
        if len(sel) > 1:
            _template_editor_clear_form_safely(self)
            self.form.addRow(QLabel(f'{len(sel)} objects selected'))
            pins = [i for i in sel if i.data(0) == 'PIN']
            text_like = [i for i in sel if i.data(0) in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY')]
            graphics = [i for i in sel if i.data(0) == 'GRAPHIC']
            if len(pins) == len(sel):
                _compat_0896(self, pins)
            elif len(text_like) == len(sel):
                self.form.addRow(QLabel(f'<b>Multi-Edit: {len(text_like)} text objects</b>'))
                self._template_multi_text_props(text_like)
            elif len(graphics) == len(sel):
                self.form.addRow(QLabel(f'<b>Multi-Edit: {len(graphics)} graphic objects</b>'))
                _compat_0886(self, graphics)
            else:
                self.form.addRow(QLabel('Multi-edit is only available for PIN-only, TEXT/ATTRIBUTE-only or GRAPHIC-only selections.'))
            return
    except Exception:
        pass
    if _compat_0892 is not None:
        return _compat_0892(self)

def _compat_0903(self, m, a, v):
    try:
        self.push_undo_state()
        self._selection_restore_ids = {id(m)}
        if a == 'rotation':
            v = (round(float(v) / 15.0) * 15.0) % 360
        elif a in ('x', 'y', 'w', 'h') and hasattr(m, 'shape'):
            try:
                snap_box = getattr(self, 'template_snap_check', None)
                snap_enabled = True if snap_box is None else bool(snap_box.isChecked())
            except Exception:
                snap_enabled = True
            if snap_enabled:
                try:
                    value = _compat_0883(self, float(v))
                except Exception:
                    value = float(v)
                if a in ('w', 'h'):
                    try:
                        step = abs(float(getattr(self, 'edit_grid_step', 0.05) or 0.05))
                    except Exception:
                        step = 0.05
                    sign = -1.0 if value < 0.0 else 1.0
                    value = sign * max(step, abs(value))
                v = _compat_0850(self, value)
        setattr(m, a, v)
        old_defer = bool(getattr(self, '_defer_property_refresh', False))
        old_suspend = bool(getattr(self, '_suspend_heavy_canvas_sync', False))
        self._defer_property_refresh = True
        self._suspend_heavy_canvas_sync = True
        try:
            self.update_current_unit_canvas_positions()
        except Exception:
            try:
                self.rebuild_scene()
            except Exception:
                pass
        finally:
            self._defer_property_refresh = old_defer
            self._suspend_heavy_canvas_sync = old_suspend
        try:
            self.dirty = True
        except Exception:
            pass
    except Exception:
        pass

def _compat_0906(self, m, v):
    try:
        _compat_0903(self, m, 'shape', v)
    except Exception:
        pass

def _compat_0909(self, item, attr, value):
    try:
        if item.data(0) in ('ATTR_REF_DES', 'ATTR_BODY') and attr == 'text':
            return
        self.push_undo_state()
        self._selection_restore_ids = {id(item.model)}
        if attr == 'rotation':
            value = (round(float(value) / 15.0) * 15.0) % 360
        setattr(item.model, attr, value)
        if attr in ('h_align', 'v_align') and hasattr(self, '_snap_text_anchor_to_grid'):
            self._snap_text_anchor_to_grid(item)
        if hasattr(item, 'apply_text_from_model'):
            item.apply_text_from_model()
        elif attr == 'text':
            item.setPlainText(value)
        self.update_current_unit_canvas_positions()
    except Exception:
        pass

def _compat_0908(self, pin_items, attr, value):
    try:
        pins = _compat_pin_models_from_objects(pin_items, require_all=False)
        if not pins:
            try:
                pins = _compat_pin_models_from_objects(self.scene.selectedItems(), require_all=False)
            except Exception:
                pins = []
        if not pins:
            return
        if attr not in ('function', 'visible_number', 'visible_name', 'visible_function', 'length', 'line_style', 'line_width', 'color', 'pin_type'):
            return
        self.push_undo_state()
        self._selection_restore_ids = {id(p) for p in pins}
        for p in pins:
            setattr(p, attr, value)
        try:
            self.update_current_unit_canvas_positions()
        except Exception:
            try:
                self.scene.update()
                self.view.viewport().update()
            except Exception:
                pass
    except Exception:
        pass

def _compat_0907(self, m, v):
    try:
        self.push_undo_state()
        self._selection_restore_ids = {id(m)}
        m.side = v
        try:
            self.dock_pins_to_body(self.unit)
        except Exception:
            pass
        self.update_current_unit_canvas_positions()
    except Exception:
        pass

def _compat_0900(self, m, attr='color'):
    try:
        current = getattr(m, attr, (0, 0, 0)) or (0, 0, 0)
        c = QColorDialog.getColor(QColor(*current), self)
        if not c.isValid():
            return
        self.push_undo_state()
        setattr(m, attr, (c.red(), c.green(), c.blue()))
        self.update_current_unit_canvas_positions()
    except Exception:
        pass

def _compat_0902(self, item):
    try:
        current = getattr(item.model, 'color', (0, 0, 0)) or (0, 0, 0)
        c = QColorDialog.getColor(QColor(*current), self)
        if not c.isValid():
            return
        self.push_undo_state()
        item.model.color = (c.red(), c.green(), c.blue())
        if hasattr(item, 'apply_text_from_model'):
            item.apply_text_from_model()
        self.update_current_unit_canvas_positions()
    except Exception:
        pass

def _compat_0901(self, items):
    try:
        current = self._common_model_value(items, 'color', (0, 0, 0)) or (0, 0, 0)
        c = QColorDialog.getColor(QColor(*current), self)
        if not c.isValid():
            return
        self.push_undo_state()
        value = (c.red(), c.green(), c.blue())
        self._selection_restore_ids = {id(i.model) for i in items if getattr(i, 'model', None) is not None}
        for item in items:
            if item.data(0) in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY'):
                item.model.color = value
                if hasattr(item, 'apply_text_from_model'):
                    item.apply_text_from_model()
        self.update_current_unit_canvas_positions()
    except Exception:
        pass

def _compat_0905(self, body, value):
    try:
        new_w = _compat_0850(self, _compat_0883(self, value))
        old_w = max(1e-9, float(getattr(body, 'width', new_w) or new_w))
        if abs(new_w - old_w) < 1e-9:
            return
        self.push_undo_state()
        self._selection_restore_ids = self._capture_selection_ids()
        if hasattr(self, '_transform_unit_as_body_group'):
            self._transform_unit_as_body_group('scale_x_to', new_w)
        else:
            body.width = max(0.01, float(new_w))
        self.dirty = True
        self.update_current_unit_canvas_positions()
    except Exception:
        pass

def _compat_0904(self, body, value):
    try:
        new_h = _compat_0850(self, _compat_0883(self, value))
        old_h = max(1e-9, float(getattr(body, 'height', new_h) or new_h))
        if abs(new_h - old_h) < 1e-9:
            return
        self.push_undo_state()
        self._selection_restore_ids = self._capture_selection_ids()
        if hasattr(self, '_transform_unit_as_body_group'):
            self._transform_unit_as_body_group('scale_y_to', new_h)
        else:
            body.height = max(0.01, float(new_h))
        self.dirty = True
        self.update_current_unit_canvas_positions()
    except Exception:
        pass

def _compat_0917(self):
    try:
        return {
            id(getattr(i, 'model', None))
            for i in self.scene.selectedItems()
            if getattr(i, 'model', None) is not None
        }
    except Exception:
        return set()

def _compat_0913(self):
    try:
        fw = QApplication.focusWidget()
        panel = getattr(self, 'props_scroll', None)
        if fw is None or panel is None:
            return False
        return fw is panel or panel.isAncestorOf(fw)
    except Exception:
        return False

def _compat_0915(self, ids):
    ids = set(ids or set())
    if not ids:
        return False
    restored = False
    try:
        self.scene.blockSignals(True)
        for it in list(self.scene.items()):
            try:
                model = getattr(it, 'model', None)
                want = model is not None and id(model) in ids
                if it.isSelected() != want:
                    it.setSelected(want)
                restored = restored or want
            except Exception:
                pass
    finally:
        try:
            self.scene.blockSignals(False)
        except Exception:
            pass
    try:
        if restored:
            self.scene.update()
            self.view.viewport().update()
    except Exception:
        pass
    return restored

def _compat_0914(self):
    try:
        ids = _compat_0917(self)
        if ids:
            self._compat_0912 = set(ids)
        elif _compat_0913(self):
            remembered = set(getattr(self, '_compat_0912', set()) or set())
            if remembered and _compat_0915(self, remembered):
                # The panel is already showing the remembered context.  Do not
                # clear/recreate it while a property widget has focus.
                return
            if remembered:
                return
    except Exception:
        pass
    if _compat_0910 is not None:
        return _compat_0910(self)

def _compat_0916(self):
    try:
        if _compat_0913(self):
            ids = _compat_0917(self)
            if ids:
                self._compat_0912 = set(ids)
            try:
                self.scene.update()
                self.view.viewport().update()
            except Exception:
                pass
            return
    except Exception:
        pass
    if _compat_0911 is not None:
        return _compat_0911(self)

def _compat_0920(self):
    try:
        splitter = getattr(self, 'template_splitter', None)
        if splitter is not None:
            return splitter
        panel = getattr(self, 'props_scroll', None)
        parent = panel.parentWidget() if panel is not None else None
        while parent is not None:
            if hasattr(parent, 'sizes') and hasattr(parent, 'setSizes') and hasattr(parent, 'setCollapsible'):
                self.template_splitter = parent
                return parent
            parent = parent.parentWidget()
    except Exception:
        pass
    return None

def _compat_0921(self):
    try:
        panel = getattr(self, 'props_scroll', None)
        if panel is not None:
            try:
                panel.setMinimumWidth(max(320, int(panel.minimumWidth())))
            except Exception:
                panel.setMinimumWidth(320)
            panel.setVisible(True)
            try:
                panel.show()
            except Exception:
                pass

        splitter = _compat_0920(self)
        if splitter is None:
            return
        try:
            splitter.setCollapsible(0, False)
            splitter.setCollapsible(1, False)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 0)
        except Exception:
            pass

        try:
            sizes = list(splitter.sizes())
            if len(sizes) >= 2 and sizes[1] < 280:
                total = sum(sizes) or splitter.width() or 1170
                panel_width = 320
                if total < 760:
                    panel_width = max(280, int(total * 0.35))
                canvas_width = max(360, total - panel_width)
                splitter.setSizes([canvas_width, panel_width])
        except Exception:
            pass
    except Exception:
        pass

def _compat_0922(self):
    result = None
    try:
        if _compat_0918 is not None:
            result = _compat_0918(self)
    finally:
        _compat_0921(self)
    return result

def _compat_0923(self):
    result = None
    try:
        if _compat_0919 is not None:
            result = _compat_0919(self)
    finally:
        _compat_0921(self)
        try:
            QTimer.singleShot(0, lambda dlg=self: _compat_0921(dlg))
        except Exception:
            pass
    return result

def _compat_0924(item):
    try:
        return item.data(0)
    except Exception:
        return None

def _compat_0925(kind, item=None):
    # Legacy-equivalent mapping: return 'ATTRIBUTES' if kind in ('ATTR_REF_DES', 'ATTR_BODY') else kind
    try:
        if item is not None:
            return selection_filter_kind_for_item(item)
    except Exception:
        pass
    return selection_filter_kind(kind)

def _compat_0929(item):
    try:
        return (_compat_0924(item) in ('BODY', 'PIN', 'TEXT', 'ATTR_REF_DES', 'ATTR_BODY', 'GRAPHIC')
                and getattr(item, 'model', None) is not None)
    except Exception:
        return False

def _compat_0941(self):
    try:
        return [item for item in self.scene.selectedItems() if _compat_0929(item)]
    except Exception:
        return []

def _compat_0940(self):
    return {id(getattr(item, 'model', None)) for item in _compat_0941(self) if getattr(item, 'model', None) is not None}

def _compat_0934(self, ids):
    ids = set(ids or set())
    if not ids:
        return False
    restored = False
    try:
        self.scene.blockSignals(True)
        for item in list(self.scene.items()):
            try:
                model = getattr(item, 'model', None)
                want = model is not None and id(model) in ids
                if item.isSelected() != want:
                    item.setSelected(want)
                restored = restored or want
            except Exception:
                pass
    finally:
        try:
            self.scene.blockSignals(False)
        except Exception:
            pass
    try:
        self.scene.update()
        self.view.viewport().update()
    except Exception:
        pass
    return restored

def _compat_0932(self):
    try:
        return bool(_compat_0913(self))
    except Exception:
        try:
            fw = QApplication.focusWidget()
            panel = getattr(self, 'props_scroll', None)
            return fw is not None and panel is not None and (fw is panel or panel.isAncestorOf(fw))
        except Exception:
            return False

def _compat_0930(self):
    try:
        _compat_0921(self)
    except Exception:
        pass

def _compat_0933(self, focused=False):
    try:
        if focused:
            return
        if getattr(self, '_suspend_heavy_canvas_sync', False):
            return
        view = getattr(self, 'view', None)
        if view is not None and getattr(view, '_compat_0098', False):
            return
        self.refresh_properties()
    except Exception:
        pass
    finally:
        _compat_0930(self)

def _compat_0931(self):
    try:
        ids = _compat_0940(self)
        focused = _compat_0932(self)
        if ids:
            self._compat_0912 = set(ids)
            self._selection_restore_ids = set(ids)
        elif focused:
            remembered = set(getattr(self, '_compat_0912', set()) or set())
            if remembered and _compat_0934(self, remembered):
                _compat_0930(self)
                return
        try:
            self.view.viewport().update()
        except Exception:
            pass
        _compat_0933(self, focused=focused)
    except Exception:
        try:
            self.refresh_properties()
        except Exception:
            pass
    finally:
        _compat_0930(self)

def _compat_0938(self):
    try:
        self.set_tool(DrawTool.SELECT.value)
    except Exception:
        pass
    try:
        mode = self.selection_mode_combo.currentText() if hasattr(self, 'selection_mode_combo') else 'ALL'
        if mode == 'ALL':
            self.selection_enabled = default_selection_enabled()
    except Exception:
        pass
    selected_ids = set()
    try:
        self.scene.blockSignals(True)
        for item in list(self.scene.items()):
            try:
                kind = _compat_0924(item)
                if kind in ('GROUP_SELECTION', 'BODY_GRAPHIC', 'SELECTION_HANDLE', 'HIGHLIGHT'):
                    item.setSelected(False)
                    continue
                fk = _compat_0925(kind, item)
                selectable = _compat_0929(item) and fk in SELECTION_FILTER_KEYS and is_selection_enabled_for_item(item, getattr(self, 'selection_enabled', {}))
                if selectable:
                    try:
                        self.apply_item_selectability(item)
                    except Exception:
                        pass
                    item.setFlag(QGraphicsItem.ItemIsSelectable, True)
                    item.setSelected(True)
                    model = getattr(item, 'model', None)
                    if model is not None:
                        selected_ids.add(id(model))
                else:
                    item.setSelected(False)
            except Exception:
                pass
    finally:
        try:
            self.scene.blockSignals(False)
        except Exception:
            pass
    try:
        self._compat_0912 = set(selected_ids)
        self._selection_restore_ids = set(selected_ids)
        self.refresh_properties()
        self.scene.update()
        self.view.viewport().update()
    except Exception:
        pass
    _compat_0930(self)

def _compat_0939(self):
    try:
        selected = _compat_0941(self)
    except Exception:
        return False
    if not selected:
        return False
    kinds = [_compat_0924(item) for item in selected]
    relevant = [kind for kind in kinds if kind in ('BODY', 'PIN', 'TEXT', 'ATTR_REF_DES', 'ATTR_BODY', 'GRAPHIC')]
    if not relevant:
        return False
    # Match the newer Symbol Wizard behavior: BODY group transforms only for a
    # pure BODY selection. Mixed selections stay object-local.
    return all(kind == 'BODY' for kind in relevant)

def _compat_0926(self, selected_ids):
    try:
        self._selection_restore_ids = set(selected_ids or set())
        self._compat_0912 = set(selected_ids or set())
        self.dirty = True
    except Exception:
        pass
    try:
        self.update_current_unit_canvas_positions()
    except Exception:
        try:
            self.schedule_scene_refresh()
        except Exception:
            try:
                self.scene.update()
                self.view.viewport().update()
            except Exception:
                pass
    _compat_0934(self, selected_ids)
    try:
        self.schedule_property_refresh()
    except Exception:
        pass
    _compat_0930(self)

def _compat_0935(self, deg):
    self.set_tool(DrawTool.SELECT.value)
    selected = _compat_0941(self)
    if not selected:
        return
    self.push_undo_state()
    selected_ids = {id(getattr(item, 'model', None)) for item in selected if getattr(item, 'model', None) is not None}
    if _compat_0939(self):
        self._selection_restore_ids = set(selected_ids)
        self._transform_unit_as_body_group('rotate', float(deg))
        _compat_0934(self, selected_ids)
    else:
        for item in selected:
            try:
                if hasattr(item, 'rotate_by'):
                    item.rotate_by(float(deg))
            except Exception:
                pass
        _compat_0926(self, selected_ids)
    self.dirty = True

def _compat_0927(self):
    self.set_tool(DrawTool.SELECT.value)
    selected = _compat_0941(self)
    if not selected:
        return
    self.push_undo_state()
    selected_ids = {id(getattr(item, 'model', None)) for item in selected if getattr(item, 'model', None) is not None}
    if _compat_0939(self):
        self._selection_restore_ids = set(selected_ids)
        self._transform_unit_as_body_group('flip_h')
        _compat_0934(self, selected_ids)
    else:
        for item in selected:
            try:
                if hasattr(item, 'flip_horizontal'):
                    item.flip_horizontal()
            except Exception:
                pass
        _compat_0926(self, selected_ids)
    self.dirty = True

def _compat_0928(self):
    self.set_tool(DrawTool.SELECT.value)
    selected = _compat_0941(self)
    if not selected:
        return
    self.push_undo_state()
    selected_ids = {id(getattr(item, 'model', None)) for item in selected if getattr(item, 'model', None) is not None}
    if _compat_0939(self):
        self._selection_restore_ids = set(selected_ids)
        self._transform_unit_as_body_group('flip_v')
        _compat_0934(self, selected_ids)
    else:
        for item in selected:
            try:
                if hasattr(item, 'flip_vertical'):
                    item.flip_vertical()
            except Exception:
                pass
        _compat_0926(self, selected_ids)
    self.dirty = True

def _compat_0937(self, direction: int):
    self.set_tool(DrawTool.SELECT.value)
    if _compat_0939(self):
        try:
            step = self._edit_grid_step()
            body = self.current_unit.body
            new_w = max(step, self._snap_to_edit_grid(float(body.width) + int(direction) * step, step))
            new_h = max(step, self._snap_to_edit_grid(float(body.height) + int(direction) * step, step))
            self.push_undo_state()
            selected_ids = _compat_0940(self)
            self._selection_restore_ids = set(selected_ids)
            self._transform_unit_as_body_group('scale_x_to', new_w, refresh=False)
            self._transform_unit_as_body_group('scale_y_to', new_h, refresh=True)
            _compat_0934(self, selected_ids)
            self.dirty = True
            QTimer.singleShot(0, self.refresh_properties)
            return
        except Exception:
            pass
    return _compat_0936(self, 1.0 + (0.1 if int(direction) > 0 else -0.1))

def _compat_0936(self, factor):
    self.set_tool(DrawTool.SELECT.value)
    selected = _compat_0941(self)
    if not selected:
        return
    self.push_undo_state()
    selected_ids = {id(getattr(item, 'model', None)) for item in selected if getattr(item, 'model', None) is not None}
    if _compat_0939(self):
        self._selection_restore_ids = set(selected_ids)
        self._transform_unit_as_body_group('scale', float(factor))
        _compat_0934(self, selected_ids)
    else:
        for item in selected:
            try:
                if hasattr(item, 'scale_by'):
                    item.scale_by(float(factor))
            except Exception:
                pass
        _compat_0926(self, selected_ids)
    self.dirty = True

def _compat_0961(self):
    return _template_editor_clear_form_safely(self)

def _compat_0966(self):
    try:
        ids = _compat_0940(self)
        if ids:
            return set(ids)
    except Exception:
        pass
    try:
        ids = set(getattr(self, '_compat_0912', set()) or set())
        if ids:
            return ids
    except Exception:
        pass
    try:
        return set(getattr(self, '_selection_restore_ids', set()) or set())
    except Exception:
        return set()

def _compat_0974(self, ids):
    ids = set(ids or set())
    if not ids:
        return
    try:
        self._selection_restore_ids = set(ids)
        self._compat_0912 = set(ids)
    except Exception:
        pass
    try:
        _compat_0934(self, ids)
    except Exception:
        pass
    try:
        _compat_0921(self)
    except Exception:
        pass

def _compat_0971(self):
    try:
        self._compat_0954 = True
        self._compat_0955 = _compat_0966(self)
    except Exception:
        pass

def _compat_0975(self):
    try:
        return [item for item in self.scene.selectedItems() if _compat_0929(item)]
    except Exception:
        return []

def _compat_0970(items):
    counts = {'BODY': 0, 'PIN': 0, 'TEXT': 0, 'ATTRIBUTES': 0, 'GRAPHIC': 0}
    for item in items:
        kind = _compat_0924(item)
        fk = _compat_0925(kind)
        if fk in counts:
            counts[fk] += 1
    return counts

def _compat_0967(items):
    counts = _compat_0970(items)
    parts = []
    for key in ('BODY', 'PIN', 'TEXT', 'ATTRIBUTES', 'GRAPHIC'):
        if counts.get(key, 0):
            parts.append(f'{key}: {counts[key]}')
    return ' / '.join(parts)

def _compat_0959(self, items):
    ids = _compat_0966(self)
    try:
        color = self._current_color_for_selection() if hasattr(self, '_current_color_for_selection') else getattr(self, 'default_color', (0, 0, 0))
        c = QColorDialog.getColor(QColor(*color), self)
        if not c.isValid():
            return
        value = (c.red(), c.green(), c.blue())
        self.push_undo_state()
        for item in list(items or []):
            try:
                model = getattr(item, 'model', None)
                if model is None:
                    continue
                kind = item.data(0)
                if kind == 'GRAPHIC':
                    model.style.stroke = value
                elif kind in ('BODY', 'PIN', 'TEXT', 'ATTR_REF_DES', 'ATTR_BODY'):
                    model.color = value
                    if hasattr(item, 'apply_text_from_model'):
                        item.apply_text_from_model()
            except Exception:
                pass
        self.dirty = True
        try:
            self.update_current_unit_canvas_positions()
        except Exception:
            try:
                self.scene.update()
                self.view.viewport().update()
            except Exception:
                pass
    finally:
        _compat_0974(self, ids)

def _compat_0956(self, items):
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    for label, callback in (
        ('Rot -90', lambda _checked=False: self.rotate_selected(-90)),
        ('Rot +90', lambda _checked=False: self.rotate_selected(90)),
        ('Flip H', lambda _checked=False: self.flip_selected_horizontal()),
        ('Flip V', lambda _checked=False: self.flip_selected_vertical()),
    ):
        btn = QPushButton(label)
        btn.clicked.connect(callback)
        lay.addWidget(btn)
    return row

def _compat_0962(self):
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    for label, callback in (
        ('Copy', lambda _checked=False: self.copy_selected()),
        ('Cut', lambda _checked=False: self.cut_selected()),
        ('Delete', lambda _checked=False: self.delete_selected()),
    ):
        btn = QPushButton(label)
        btn.clicked.connect(callback)
        lay.addWidget(btn)
    return row

def _compat_0960(self, items):
    ids = {id(getattr(item, 'model', None)) for item in items if getattr(item, 'model', None) is not None}
    self._compat_0912 = set(ids)
    self._selection_restore_ids = set(ids)
    self.form.addRow(QLabel(f'{len(items)} objects selected'))
    counts = _compat_0967(items)
    if counts:
        self.form.addRow(QLabel(counts))
    self.form.addRow(QLabel('<b>Selection</b>'))
    self.form.addRow('Transform', _compat_0956(self, items))
    self.form.addRow('Edit', _compat_0962(self))
    self.form.addRow('Color', self._color_button_row('Color RGB', self._current_color_for_selection() if hasattr(self, '_current_color_for_selection') else getattr(self, 'default_color', (0, 0, 0)), lambda _checked=False, its=list(items): _compat_0959(self, its)))

    pins = []
    text_like = []
    graphics = []
    for i in items:
        try:
            kind = i.data(0)
        except RuntimeError:
            continue
        except Exception:
            continue
        if kind == 'PIN':
            pins.append(i)
        elif kind in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY'):
            text_like.append(i)
        elif kind == 'GRAPHIC':
            graphics.append(i)

    if pins:
        try:
            _compat_0896(self, pins)
        except Exception:
            pass
    if text_like:
        try:
            self.form.addRow(QLabel(f'<b>Multi-Edit: {len(text_like)} text objects</b>'))
            self._template_multi_text_props(text_like)
        except Exception:
            pass
    if graphics:
        try:
            self.form.addRow(QLabel(f'<b>Multi-Edit: {len(graphics)} graphic objects</b>'))
            _compat_0886(self, graphics)
        except Exception:
            pass
    _compat_0971(self)



def _template_editor_render_single_text_props(self, item):
    """Render Template Editor single-text properties with Symbol Wizard parity.

    The historical Template Editor refresh chain had a reduced text panel
    (text/size/rotation only).  This explicit renderer keeps single text edit
    behavior aligned with MainWindow.text_props: content, font, style,
    anchors, wrap/line-break hint, rotation and color.
    """
    try:
        if hasattr(self, 'clear_properties'):
            self.clear_properties()
        else:
            while self.form.rowCount():
                self.form.removeRow(0)
    except Exception:
        pass
    try:
        kind = item.data(0)
    except Exception:
        kind = 'TEXT'
    m = getattr(item, 'model', None)
    if m is None:
        try:
            self.form.addRow(QLabel('No text model.'))
        except Exception:
            pass
        return
    try:
        if hasattr(self, '_selection_title_label'):
            self.form.addRow(self._selection_title_label(kind, item))
        else:
            self.form.addRow(QLabel(f'<b>{kind}</b>'))
    except Exception:
        pass
    is_attr = kind in ('ATTR_REF_DES', 'ATTR_BODY') or bool(getattr(m, '_is_attribute_text', False))
    try:
        line = self._line(getattr(m, 'text', ''), lambda v, item=item: self._set_text_item_attr(item, 'text', v)) if is_attr else self._plain_text_editor(getattr(m, 'text', ''), lambda v, item=item: self._set_text_item_attr(item, 'text', v))
        if is_attr and hasattr(line, 'setReadOnly'):
            line.setReadOnly(True)
            try:
                line.setToolTip('Attribute text content is driven by the owning object attribute value.')
            except Exception:
                pass
        self.form.addRow('Text content', line)
    except Exception:
        pass
    try:
        self.form.addRow('Font', self._font_combo(getattr(m, 'font_family', 'Arial'), lambda v, item=item: self._set_text_item_attr(item, 'font_family', v)))
    except Exception:
        pass
    try:
        if hasattr(self, '_text_style_row'):
            self.form.addRow('Style', self._text_style_row(m, lambda a, v, it=item: self._set_text_item_attr(it, a, v)))
        else:
            row = QWidget(); lay = QHBoxLayout(row); lay.setContentsMargins(0,0,0,0)
            for title, attr in [('Bold', 'bold'), ('Italic', 'italic'), ('Underline', 'underline')]:
                cb = QCheckBox(title); cb.setChecked(bool(getattr(m, attr, False)))
                cb.toggled.connect(lambda v, a=attr, it=item: self._set_text_item_attr(it, a, v))
                lay.addWidget(cb)
            lay.addStretch(1)
            self.form.addRow('Style', row)
    except Exception:
        pass
    try:
        self.form.addRow('Size grid', self._dbl(getattr(m, 'font_size_grid', 0.9), lambda v, item=item: self._set_text_item_attr(item, 'font_size_grid', float(v)), .1, 10, .1))
    except Exception:
        pass
    try:
        self.form.addRow('Horizontal grid anchor', self._combo(['left','center','right'], getattr(m, 'h_align', 'left'), lambda v, item=item: self._set_text_item_attr(item, 'h_align', v)))
    except Exception:
        pass
    try:
        self.form.addRow('Vertical grid anchor', self._combo(['upper','center','lower'], getattr(m, 'v_align', 'upper'), lambda v, item=item: self._set_text_item_attr(item, 'v_align', v)))
    except Exception:
        pass
    try:
        if is_attr:
            self.form.addRow('Wrap text', self._check(getattr(m, 'wrap_text', False), lambda v, item=item: self._set_text_item_attr(item, 'wrap_text', v)))
        else:
            self.form.addRow('Line break', QLabel('Shift+Enter in canvas / text field'))
    except Exception:
        pass
    try:
        self.form.addRow('Rotation [deg]', self._dbl(getattr(m, 'rotation', 0), lambda v, item=item: self._set_text_item_attr(item, 'rotation', float(v)), -360, 360, 15))
    except Exception:
        pass
    try:
        self.form.addRow('Color', self._color_button_row('Color RGB', getattr(m, 'color', (0, 0, 0)), lambda _checked=False, item=item: self.color_text_item(item)))
    except Exception:
        pass

def _compat_0973(self):
    if getattr(self, '_template_property_refresh_active', False):
        return
    self._template_property_refresh_active = True
    try:
        try:
            focused = _compat_0932(self)
            if focused and getattr(self, '_compat_0954', False):
                ids = set(getattr(self, '_compat_0955', set()) or set())
                if ids:
                    _compat_0974(self, ids)
                    _template_editor_render_empty_panel_if_needed(self)
                    return
        except Exception:
            pass
        try:
            items = _compat_0975(self)
            if len(items) > 1:
                if not _compat_0961(self):
                    _template_editor_render_empty_panel_if_needed(self)
                    return
                _compat_0960(self, items)
                _compat_0921(self)
                _template_editor_render_empty_panel_if_needed(self)
                return
            if len(items) == 1:
                try:
                    kind = items[0].data(0)
                except Exception:
                    kind = None
                if kind in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY'):
                    _template_editor_render_single_text_props(self, items[0])
                    _compat_0921(self)
                    _template_editor_render_empty_panel_if_needed(self)
                    return
            try:
                self._compat_0954 = False
            except Exception:
                pass
        except Exception:
            pass
        if _compat_0949 is not None:
            result = _compat_0949(self)
            try:
                _compat_0921(self)
            except Exception:
                pass
            _template_editor_render_empty_panel_if_needed(self)
            return result
    finally:
        self._template_property_refresh_active = False
        try:
            _compat_0921(self)
        except Exception:
            pass
        _template_editor_render_empty_panel_if_needed(self)

def _compat_0972(self, fn, *args, **kwargs):
    ids = _compat_0966(self)
    try:
        return fn(self, *args, **kwargs)
    finally:
        _compat_0974(self, ids)

def _compat_0978(self, pin_items, attr, value):
    pins = _compat_pin_models_from_objects(pin_items, require_all=False)
    if not pins:
        try:
            pins = _compat_pin_models_from_objects(self.scene.selectedItems(), require_all=False)
        except Exception:
            pins = []
    if not pins:
        return None
    if _compat_0952 is None:
        return None
    return _compat_0972(self, _compat_0952, tuple(pins), attr, value)

def _compat_0979(self, items, attr, value):
    if _compat_0953 is None:
        return None
    return _compat_0972(self, _compat_0953, items, attr, value)

def _compat_0977(self, items, attr, value):
    if _compat_0951 is None:
        return None
    return _compat_0972(self, _compat_0951, items, attr, value)

def _compat_0976(self, items, attr, value):
    if _compat_0950 is None:
        return None
    return _compat_0972(self, _compat_0950, items, attr, value)

def _compat_0965(self, items):
    if _compat_0946 is None:
        return None
    return _compat_0972(self, _compat_0946, items)

def _compat_0964(self, items):
    if _compat_0945 is None:
        return None
    return _compat_0972(self, _compat_0945, items)

def _compat_0963(self, items):
    if _compat_0944 is None:
        return None
    return _compat_0972(self, _compat_0944, items)

def _compat_0958(self, items, mode):
    if _compat_0943 is None:
        return None
    return _compat_0972(self, _compat_0943, items, mode)

def _compat_0969(self, items, axis):
    if _compat_0948 is None:
        return None
    return _compat_0972(self, _compat_0948, items, axis)

def _compat_0957(self, items, mode):
    if _compat_0942 is None:
        return None
    return _compat_0972(self, _compat_0942, items, mode)

def _compat_0968(self, items, axis):
    if _compat_0947 is None:
        return None
    return _compat_0972(self, _compat_0947, items, axis)

def _compat_1203(gr):
    try:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body', 'template_body', 'imported_body')
    except Exception:
        return False

def _compat_1214(self, deg):
    gi = _compat_1216(self)
    if gi is not None:
        try: self.push_undo_state()
        except Exception: pass
        gi.rotate_by(float(deg))
        try:
            self._compat_1213 = gi.group_id
            self.dirty = True
            self.rebuild_scene(); self.rebuild_tree(); self.refresh_properties()
        except Exception: pass
        return None
    return _compat_1209(self, deg) if _compat_1209 else None

def _compat_1212(self):
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
