"""Selection, grouping, alignment and distribution helpers.

Executed in the shared ``main_window.py`` global namespace by ``legacy_updates.apply_legacy_updates``.
"""

from __future__ import annotations

def _compat_0336(self):
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

def _compat_0710(self, item):
    if _compat_0713(item):
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
    if _compat_0715 is not None:
        return _compat_0715(self, item)

def _compat_0711(self):
    # Apply normal filtering first, then explicitly include BODY_GRAPHIC as BODY.
    if _compat_0714 is not None:
        try:
            _compat_0714(self)
        except Exception:
            pass
    try:
        for item in self.scene.items():
            if _compat_0713(item):
                _compat_0710(self, item)
    except Exception:
        pass

def _compat_0364(self):
    try:
        return {id(getattr(i, 'model', None)) for i in self.scene.selectedItems() if getattr(i, 'model', None) is not None}
    except Exception:
        return set()

def _compat_0371(self):
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

def _compat_0366(self, sig=None):
    sig = list(sig or _compat_0371(self) or getattr(self, '_compat_0372', []) or [])
    self._compat_0372 = sig
    def run():
        try: _compat_0368(self, sig)
        except Exception: pass
    try: QTimer.singleShot(0, run)
    except Exception: run()

def _compat_0387(self):
    try:
        mode = self.selection_mode_combo.currentText() if hasattr(self, 'selection_mode_combo') else None
    except Exception:
        mode = None
    try:
        enabled = dict(getattr(self, 'selection_enabled', {}) or {})
    except Exception:
        enabled = {}
    return mode, enabled

def _compat_0382(self, state):
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

def _compat_0381(self, sig=None, filter_state=None, force_body=False, refresh=True):
    def run():
        try:
            if filter_state is not None:
                _compat_0382(self, filter_state)
            body_before = force_body or any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in (sig or []))
            if body_before:
                _compat_0386(self)
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

def _compat_0388(self, work, force_body=False):
    sig = _compat_0371(self) if '_compat_0371' in globals() else []
    filter_state = _compat_0387(self)
    try:
        return work()
    finally:
        _compat_0381(self, sig=sig, filter_state=filter_state, force_body=force_body)

def _compat_0391(self):
    try:
        items = list(self.scene.selectedItems())
    except Exception:
        return []
    out = []
    for it in items:
        k = _compat_0392(it)
        if k in ('BODY', 'PIN', 'GRAPHIC') and getattr(it, 'model', None) is not None:
            out.append(it)
    return out

def _compat_0397(self):
    """Show common selected line style/width, or <Multiple> on mismatches.

    This is display-only. Signals are blocked so the Selectable mode and the
    selected objects are not changed just because the panel is being updated.
    """
    if not hasattr(self, 'line_style') or not hasattr(self, 'line_width'):
        return
    items = _compat_0391(self)
    if not items:
        return
    style_val, style_same = _compat_0390([_compat_0393(i, 'line_style') for i in items])
    width_val, width_same = _compat_0390([_compat_0393(i, 'line_width') for i in items])
    try:
        self.line_style.blockSignals(True)
        idx = self.line_style.findText(_compat_0051)
        if style_same and style_val is not None:
            if idx >= 0:
                self.line_style.removeItem(idx)
            self.line_style.setCurrentText(str(style_val))
        else:
            if idx < 0:
                self.line_style.insertItem(0, _compat_0051)
            self.line_style.setCurrentText(_compat_0051)
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
            self.line_width.setSpecialValueText(_compat_0051)
            self.line_width.setValue(0.0)
    except Exception:
        pass
    finally:
        try: self.line_width.blockSignals(False)
        except Exception: pass

def _compat_0394(self):
    mode_state = _compat_0387(self) if '_compat_0387' in globals() else None
    try:
        if _compat_0396 is not None:
            _compat_0396(self)
        else:
            self.refresh_properties()
    except Exception as e:
        try: self.statusBar().showMessage(f'Selection update failed: {e}', 4000)
        except Exception: pass
    finally:
        if mode_state is not None and '_compat_0382' in globals():
            _compat_0382(self, mode_state)
        _compat_0397(self)

def _compat_0433(self):
    try:
        return [i for i in self.scene.selectedItems() if getattr(i, 'data', lambda *_: None)(0) not in ('SELECTION_HANDLE', 'HIGHLIGHT')]
    except Exception:
        return []

def _compat_0448(self):
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

def _compat_0436(gr):
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

def _compat_0437(self):
    selected = []
    gids = set()
    for it in _compat_0448(self):
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None and _compat_0439(self, it.model):
                selected.append(it.model)
                gid = _compat_0436(it.model)
                if gid:
                    gids.add(gid)
        except Exception:
            pass
    if not selected:
        return []
    models = []
    for gr in list(getattr(getattr(self, 'current_unit', None), 'graphics', []) or []):
        try:
            if not _compat_0439(self, gr):
                continue
            if gr in selected or (_compat_0436(gr) and _compat_0436(gr) in gids):
                if gr not in models:
                    models.append(gr)
        except Exception:
            pass
    return models

def _compat_0476(self):
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

def _compat_0455(gr):
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

def _compat_0475(self, expand_groups=True):
    selected = []
    gids = set()
    for it in _compat_0476(self):
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None and _compat_0465(it.model):
                selected.append(it.model)
                gid = _compat_0455(it.model)
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
            if not _compat_0465(gr):
                continue
            if gr in selected or (_compat_0455(gr) and _compat_0455(gr) in gids):
                if gr not in out:
                    out.append(gr)
        except Exception:
            pass
    return out

def _compat_0452(self):
    try:
        if getattr(self, '_compat_0462', False):
            return
        self._compat_0462 = True
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

def _compat_0480(gr):
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

def _compat_0493(self, expand_groups=True):
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
            if gr is None or not _compat_0487(gr):
                continue
            if gr not in selected:
                selected.append(gr)
            gid = _compat_0480(gr)
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
            if not _compat_0487(gr):
                continue
            gid = _compat_0480(gr)
            if gr in selected or (gid and gid in gids):
                if gr not in out:
                    out.append(gr)
        except Exception:
            pass
    return out

def _compat_0483(graphics):
    boxes = [_compat_0481(g) for g in graphics]
    if not boxes:
        return None
    return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)

def _compat_0484(self):
    models = _compat_0493(self, expand_groups=False)
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
    import uuid as _compat_0497
    gid = 'G' + _compat_0497.uuid4().hex[:8]
    for gr in models:
        _compat_0494(gr, gid)
    try:
        self.dirty = True
        self.rebuild_tree()
        self.refresh_properties()
        self.update_current_unit_canvas_positions()
        self.statusBar().showMessage(f'Grafikgruppe erstellt: {len(models)} Objekte.', 4000)
    except Exception:
        pass

def _compat_0496(self):
    models = _compat_0493(self, expand_groups=True)
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
        _compat_0494(gr, '')
    try:
        self.dirty = True
        self.rebuild_tree()
        self.refresh_properties()
        self.update_current_unit_canvas_positions()
        self.statusBar().showMessage('Grafikgruppe aufgehoben.', 4000)
    except Exception:
        pass

def _compat_0501(gr):
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

def _compat_0518(self, expand_groups=True):
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
            if gr is None or not _compat_0512(gr):
                continue
            if gr not in selected:
                selected.append(gr)
            gid = _compat_0501(gr)
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
            if not _compat_0512(gr):
                continue
            gid = _compat_0501(gr)
            if gr in selected or (gid and gid in gids):
                if gr not in out:
                    out.append(gr)
        except Exception:
            pass
    return out

def _compat_0508(graphics):
    boxes = [_compat_0499(g) for g in graphics]
    if not boxes:
        return None
    return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)

def _compat_0509(self):
    models = _compat_0518(self, expand_groups=False)
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
    import uuid as _compat_0522
    gid = 'G' + _compat_0522.uuid4().hex[:8]
    for gr in models:
        _compat_0519(gr, gid)
    try:
        self.dirty = True
        self.update_current_unit_canvas_positions()
        self.rebuild_tree()
        self.refresh_properties()
        self.statusBar().showMessage(f'Grafikgruppe erstellt: {len(models)} Objekte.', 4000)
    except Exception:
        pass

def _compat_0521(self):
    models = _compat_0518(self, expand_groups=True)
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
        _compat_0519(gr, '')
    try:
        self.dirty = True
        self.update_current_unit_canvas_positions()
        self.rebuild_tree()
        self.refresh_properties()
        self.statusBar().showMessage('Grafikgruppe aufgehoben.', 4000)
    except Exception:
        pass

def _compat_0527(gr):
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

def _compat_0545(self):
    out = []
    try: items = list(self.scene.selectedItems()) if getattr(self, 'scene', None) else []
    except Exception: items = []
    for it in items:
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None and _compat_0531(it.model):
                out.append(it)
        except Exception:
            pass
    return out

def _compat_0546(self, expand_groups=True):
    selected = []
    gids = set()
    for it in _compat_0545(self):
        gr = it.model
        if gr not in selected:
            selected.append(gr)
        gid = _compat_0527(gr)
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
            gid = _compat_0527(gr)
            if gr in selected or (gid and gid in gids):
                if _compat_0531(gr) and gr not in out:
                    out.append(gr)
        except Exception:
            pass
    return out

def _compat_0530(models):
    boxes = [_compat_0526(g) for g in models]
    if not boxes: return None
    return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)

def _compat_0548(self):
    """A graphics group is one logical object: selecting one member selects all
    members, while the property panel/paint code presents one group."""
    if getattr(self, '_compat_0549', False):
        return
    selected = _compat_0545(self)
    gids = {_compat_0527(it.model) for it in selected if _compat_0527(it.model)}
    if not gids:
        return
    try:
        self._compat_0549 = True
        self.scene.blockSignals(True)
        for it in _compat_0524(self):
            try:
                if _compat_0527(it.model) in gids:
                    it.setSelected(True)
            except Exception:
                pass
    finally:
        try: self.scene.blockSignals(False)
        except Exception: pass
        self._compat_0549 = False

def _compat_0537(self):
    try: _compat_0548(self)
    except Exception: pass
    if _compat_0538:
        return _compat_0538(self)
    try: self.refresh_properties()
    except Exception: pass

def _compat_0566(gr):
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

def _compat_0589(self):
    out = []
    try: items = list(self.scene.selectedItems()) if getattr(self, 'scene', None) else []
    except Exception: items = []
    for it in items:
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None and _compat_0574(it.model):
                out.append(it)
        except Exception:
            pass
    return out

def _compat_0590(self, expand_groups=True):
    selected = []
    gids = set()
    for it in _compat_0589(self):
        gr = it.model
        if gr not in selected:
            selected.append(gr)
        gid = _compat_0566(gr)
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
            gid = _compat_0566(gr)
            if _compat_0574(gr) and (gr in selected or (gid and gid in gids)) and gr not in out:
                out.append(gr)
        except Exception:
            pass
    return out

def _compat_0591(self):
    gids = set()
    for it in _compat_0589(self):
        gid = _compat_0566(it.model)
        if gid:
            gids.add(gid)
        else:
            return ''
    return next(iter(gids)) if len(gids) == 1 else ''

def _compat_0595(self):
    if getattr(self, '_compat_0596', False):
        return
    selected = _compat_0589(self)
    gids = {_compat_0566(it.model) for it in selected if _compat_0566(it.model)}
    if not gids:
        _compat_0598(self)
        return
    try:
        self._compat_0596 = True
        self.scene.blockSignals(True)
        for it in _compat_0567(self):
            gid = _compat_0566(it.model)
            if gid in gids:
                it.setSelected(True)
    finally:
        try: self.scene.blockSignals(False)
        except Exception: pass
        self._compat_0596 = False
    _compat_0598(self)

def _compat_0563(self):
    try:
        item = getattr(self, '_compat_0569', None)
        if item is not None and getattr(self, 'scene', None) is not None:
            self.scene.removeItem(item)
    except Exception:
        pass
    self._compat_0569 = None

def _compat_0570(self):
    models = _compat_0590(self, expand_groups=False)
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
    import uuid as _compat_0600
    gid = 'G' + _compat_0600.uuid4().hex[:8]
    for gr in clean:
        _compat_0592(gr, gid)
    try:
        self.dirty = True
        self.scene.blockSignals(True)
        for it in _compat_0567(self):
            it.setSelected(_compat_0566(it.model) == gid)
    finally:
        try: self.scene.blockSignals(False)
        except Exception: pass
    _compat_0599(self)
    try: self.statusBar().showMessage(f'Grafikgruppe erstellt: {len(clean)} Objekte als 1 Objekt.', 4000)
    except Exception: pass

def _compat_0597(self):
    models = _compat_0590(self, expand_groups=True)
    if not models:
        try: QMessageBox.information(self, 'Ungroup Graphics', 'Keine Grafikgruppe ausgewählt.')
        except Exception: pass
        return
    try: self.push_undo_state()
    except Exception: pass
    for gr in models:
        _compat_0592(gr, '')
    try: self.dirty = True
    except Exception: pass
    _compat_0563(self)
    _compat_0599(self)
    try: self.statusBar().showMessage('Grafikgruppe aufgehoben.', 4000)
    except Exception: pass

def _compat_0578(self):
    try: _compat_0595(self)
    except Exception: pass
    try:
        return _compat_0538(self) if '_compat_0538' in globals() and _compat_0538 else self.refresh_properties()
    except Exception:
        try: self.refresh_properties()
        except Exception: pass

def _compat_0218(self, combo_index):
    try:
        if hasattr(self, 'set_active_symbol_from_combo_index'):
            return self.set_active_symbol_from_combo_index(combo_index)
        combo = getattr(self, 'active_symbol_combo', None)
        if combo is None or combo_index < 0:
            return
        symbol_index = combo.itemData(combo_index)
        if symbol_index is None:
            symbol_index = combo_index
        symbol_index = int(symbol_index)
        if symbol_index < 0 or symbol_index >= len(self.library.symbols):
            return
        if symbol_index == self.library.current_symbol_index:
            return
        self.library.current_symbol_index = symbol_index
        self.current_unit_index = 0
        self.rebuild_all()
    except Exception:
        pass

def _compat_0249(self, combo_index):
    try:
        if hasattr(self, 'set_active_split_part_from_combo_index'):
            return self.set_active_split_part_from_combo_index(combo_index)
        combo = getattr(self, 'active_split_part_combo', None)
        if combo is None or combo_index < 0 or not _compat_0231(self):
            return
        unit_index = combo.itemData(combo_index)
        unit_index = combo_index if unit_index is None else int(unit_index)
        if unit_index < 0 or unit_index >= len(self.symbol.units):
            return
        if unit_index == self.current_unit_index:
            return
        self.current_unit_index = unit_index
        self.rebuild_workspace(units=True, canvas=True, scene=True, tree=True, pins=True, names=True)
        try:
            self.sync_symbol_controls()
        except Exception:
            pass
    except Exception:
        pass

def _compat_0980(self, color):
    selected = list(self.scene.selectedItems()) if hasattr(self, 'scene') else []
    if not selected:
        self.default_color = tuple(color); return
    self.push_undo_state()
    for it in selected:
        k = it.data(0); m = getattr(it, 'model', None)
        if m is None: continue
        if k == 'BODY':
            m.color = tuple(color)
            for gr in _compat_0982(self, self.current_unit):
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

def _compat_1011(self):
    try:
        return [getattr(it, 'model', None) for it in self.scene.selectedItems()
                if getattr(it, 'data', lambda *_: None)(0) == 'GRAPHIC'
                and getattr(it, 'model', None) is not None]
    except Exception:
        return []

def _compat_1031(self, model):
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

def _compat_1034(self):
    try:
        free_txt = _compat_1039(self)
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
    if _compat_1036:
        return _compat_1036(self)
    try:
        self.refresh_properties()
    except Exception:
        pass

def _compat_1032(self):
    try:
        free = _compat_1039(self)
        if free:
            return {id(it.model) for it in free}
    except Exception:
        pass
    return _compat_1035(self)

def _compat_1044(win):
    try:
        txt = [it for it in win.scene.selectedItems() if _compat_1048(it)]
        if not txt:
            # If another real object is selected, the remembered text is no longer active.
            real = [it for it in win.scene.selectedItems() if getattr(it, 'data', lambda *_: None)(0) in ('BODY','PIN','GRAPHIC','ATTR_REF_DES','ATTR_BODY')]
            if real:
                win._compat_1043 = None
            return
        win._compat_1043 = getattr(txt[0], 'model', None)
        win.scene.blockSignals(True)
        try:
            for it in list(win.scene.selectedItems()):
                if not _compat_1048(it):
                    it.setSelected(False)
        finally:
            win.scene.blockSignals(False)
    except Exception:
        try: win.scene.blockSignals(False)
        except Exception: pass

def _compat_1049(self):
    _compat_1044(self)
    return _compat_1052(self)

def _compat_0818(self):
    if getattr(self, '_keep_selection_visible_pending', False):
        return
    self._keep_selection_visible_pending = True
    def _do():
        self._keep_selection_visible_pending = False
        try:
            rect = _compat_0833(self)
            if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
                return
            # Only scroll if the selection is close to or outside the viewport.
            view_rect = self.view.mapToScene(self.view.viewport().rect()).boundingRect()
            margin = max(float(getattr(self, 'grid_px', 50.0) or 50.0) * 2.0, 80.0)
            safe = view_rect.adjusted(margin, margin, -margin, -margin)
            if not safe.contains(rect):
                self.view.ensureVisible(rect.adjusted(-margin, -margin, margin, margin), int(margin), int(margin))
        except Exception:
            pass
    try:
        QTimer.singleShot(16, _do)
    except Exception:
        pass

def _compat_0847(self):
    """Select all canvas objects according to the current Selectable mode.

    When the combo says ALL, reset the internal selection flags to all True and
    select BODY, PIN, TEXT/ATTR and GRAPHIC at once.  This avoids the old failure
    mode where a focused QGraphicsTextItem consumed Ctrl+A and only selected its
    plain text content.
    """
    try:
        self.set_tool(DrawTool.SELECT.value)
    except Exception:
        pass
    try:
        mode = self.selection_mode_combo.currentText() if hasattr(self, 'selection_mode_combo') else 'ALL'
    except Exception:
        mode = 'ALL'
    try:
        if mode == 'ALL':
            self.selection_enabled = default_selection_enabled()
    except Exception:
        pass
    selected = 0
    try:
        self.scene.blockSignals(True)
        for item in list(self.scene.items()):
            try:
                kind = item.data(0)
                if kind in ('GROUP_SELECTION', 'BODY_GRAPHIC'):
                    item.setSelected(False)
                    continue
                filter_kind = selection_filter_kind_for_item(item)
                # Legacy-equivalent mapping: filter_kind = 'ATTRIBUTES' if kind in ('ATTR_REF_DES', 'ATTR_BODY') else kind
                if filter_kind in SELECTION_FILTER_KEYS and is_selection_enabled_for_item(item, getattr(self, 'selection_enabled', {})):
                    try:
                        self.apply_item_selectability(item)
                    except Exception:
                        pass
                    item.setFlag(QGraphicsItem.ItemIsSelectable, True)
                    item.setSelected(True)
                    selected += 1
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
        self.refresh_properties()
    except Exception:
        pass
    try:
        self.scene.update(); self.view.viewport().update()
    except Exception:
        pass
    try:
        self.statusBar().showMessage(f'Selected {selected} canvas object(s).', 1800)
    except Exception:
        pass

def _compat_0882(self, graphic_items, attr, value):
    graphics = _compat_0860(graphic_items)
    if not graphics or len(graphics) != len(graphic_items or []):
        return
    if attr not in ('line_width', 'line_style', 'stroke', 'fill'):
        return
    self.push_undo_state()
    self._selection_restore_ids = {id(g) for g in graphics}
    for g in graphics:
        try:
            setattr(g.style, attr, value)
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

def _compat_0881(self, graphic_items, attr, value):
    graphics = _compat_0860(graphic_items)
    if not graphics or len(graphics) != len(graphic_items or []):
        return
    if attr not in ('curve_radius', 'rotation'):
        return
    self.push_undo_state()
    self._selection_restore_ids = {id(g) for g in graphics}
    for g in graphics:
        try:
            setattr(g, attr, value)
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

def _compat_0851(self, items):
    graphics = _compat_0860(items)
    if not graphics:
        return
    current = None
    try:
        current = self._common_graphic_value(items, 'stroke', None)
    except Exception:
        current = None
    if not current:
        current = getattr(graphics[0].style, 'stroke', (0, 0, 0)) or (0, 0, 0)
    c = QColorDialog.getColor(QColor(*current), self)
    if c.isValid():
        _compat_0882(self, items, 'stroke', (c.red(), c.green(), c.blue()))

def _compat_0849(self, items, mode):
    graphics = _compat_0860(items)
    if len(graphics) < 2:
        try:
            self.statusBar().showMessage('Select at least two graphic objects.', 3000)
        except Exception:
            pass
        return
    bounds = {g: _compat_0858(g) for g in graphics}
    if mode == 'left':
        target = min(b['left'] for b in bounds.values())
        delta = lambda b: (target - b['left'], 0.0)
    elif mode == 'right':
        target = max(b['right'] for b in bounds.values())
        delta = lambda b: (target - b['right'], 0.0)
    elif mode == 'top':
        target = max(b['top'] for b in bounds.values())
        delta = lambda b: (0.0, target - b['top'])
    else:
        target = min(b['bottom'] for b in bounds.values())
        delta = lambda b: (0.0, target - b['bottom'])
    self.push_undo_state()
    self._selection_restore_ids = {id(g) for g in graphics}
    for g in graphics:
        dx, dy = delta(bounds[g])
        _compat_0871(self, g, dx, dy)
    try:
        self.update_current_unit_canvas_positions()
        self.refresh_properties()
    except Exception:
        try:
            self.rebuild_scene()
        except Exception:
            pass

def _compat_0899(self, graphic_items, attr, value):
    graphics = _compat_0860(graphic_items)
    if not graphics or len(graphics) != len(graphic_items or []):
        return
    if attr not in ('line_width', 'line_style', 'stroke', 'fill'):
        return
    self.push_undo_state()
    self._selection_restore_ids = {id(g) for g in graphics}
    for g in graphics:
        try:
            setattr(g.style, attr, value)
        except Exception:
            pass
    try:
        self.update_current_unit_canvas_positions()
    except Exception:
        try:
            self.scene.update()
            self.view.viewport().update()
        except Exception:
            pass

def _compat_0898(self, graphic_items, attr, value):
    graphics = _compat_0860(graphic_items)
    if not graphics or len(graphics) != len(graphic_items or []):
        return
    if attr not in ('curve_radius', 'rotation'):
        return
    self.push_undo_state()
    self._selection_restore_ids = {id(g) for g in graphics}
    for g in graphics:
        try:
            setattr(g, attr, value)
        except Exception:
            pass
    try:
        self.update_current_unit_canvas_positions()
    except Exception:
        try:
            self.scene.update()
            self.view.viewport().update()
        except Exception:
            pass

def _compat_1199(gr):
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

def _compat_1200(win):
    unit = _compat_1196(win)
    out = {}
    for gr in list(getattr(unit, 'graphics', []) if unit is not None else []):
        try:
            if not _compat_1203(gr):
                continue
            gid = _compat_1199(gr)
            if gid:
                out.setdefault(gid, []).append(gr)
        except Exception:
            pass
    return {k: v for k, v in out.items() if len(v) >= 1}

def _compat_1216(win):
    try:
        for it in win.scene.selectedItems():
            if getattr(it, 'data', lambda *_: None)(0) == 'GRAPHIC_GROUP':
                return it
    except Exception:
        pass
    return None

def _compat_1201(win):
    grouped_ids = set()
    for models in _compat_1200(win).values():
        grouped_ids.update(id(m) for m in models)
    for it in _compat_1215(win):
        try:
            if id(it.model) in grouped_ids:
                it.setSelected(False)
                it.setFlag(_V80QGraphicsItem.ItemIsSelectable, False)
                it.setFlag(_V80QGraphicsItem.ItemIsMovable, False)
                it.setFlag(_V80QGraphicsItem.ItemIsFocusable, False)
                it.setAcceptedMouseButtons(_V80Qt.NoButton)
            elif _compat_1203(it.model):
                it.setFlag(_V80QGraphicsItem.ItemIsSelectable, True)
                it.setFlag(_V80QGraphicsItem.ItemIsMovable, True)
                it.setFlag(_V80QGraphicsItem.ItemIsFocusable, True)
                it.setAcceptedMouseButtons(_V80Qt.LeftButton)
        except Exception:
            pass

def _compat_1219(self):
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

def _compat_1222(self):
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
