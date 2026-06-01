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
