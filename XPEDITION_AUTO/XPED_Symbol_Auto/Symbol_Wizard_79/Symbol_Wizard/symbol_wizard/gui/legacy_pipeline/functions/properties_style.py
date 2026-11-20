"""Property panel, color, style, text and attribute helpers.

Executed in the shared ``main_window.py`` global namespace by ``legacy_updates.apply_legacy_updates``.
"""

from __future__ import annotations

def _compat_0329(tm, dx, dy):
    try:
        tm.x = float(tm.x) + dx; tm.y = float(tm.y) + dy
    except Exception:
        pass

def _compat_0317(self, gd, M):
    gr = gd['obj']; shape = gd.get('shape') or str(getattr(gr, 'shape', '') or '')
    sxv, syv = _compat_0332(M), _compat_0333(M)
    ang = _compat_0321(M)
    clean = lambda v: _compat_0314(self, v)
    if shape in ('line', 'arc'):
        x1, y1 = _compat_0308(M, gd['x'], gd['y'])
        x2, y2 = _compat_0308(M, gd['x'] + gd['w'], gd['y'] - gd['h'])
        gr.x, gr.y = clean(x1), clean(y1)
        gr.w, gr.h = clean(x2 - x1), clean(y1 - y2)
        gr.rotation = 0.0; gr.scale_x = 1.0; gr.scale_y = 1.0
        if gd.get('ctrl_x') is not None and gd.get('ctrl_y') is not None:
            cx, cy = _compat_0308(M, gd['x'] + float(gd['ctrl_x']), gd['y'] - float(gd['ctrl_y']))
            gr.ctrl_x, gr.ctrl_y = clean(cx - x1), clean(y1 - cy)
        try:
            gr.curve_radius = clean(float(gd.get('curve_radius', 0.0) or 0.0) * max(sxv, syv))
        except Exception:
            pass
    else:
        cx, cy = gd['x'] + gd['w'] / 2.0, gd['y'] - gd['h'] / 2.0
        ncx, ncy = _compat_0308(M, cx, cy)
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

def _compat_0554(tm):
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

def _compat_0643(tm):
    try: tm.rotation = 0.0
    except Exception: pass
    try: tm.scale_x = 1.0
    except Exception: pass
    try: tm.scale_y = 1.0
    except Exception: pass

def _compat_0639(self, tm, op, font_factor=1.0):
    if tm is None:
        return
    try:
        nx, ny = _compat_0640(op, tm.x, tm.y)
        tm.x, tm.y = _compat_0637(self, nx), _compat_0637(self, ny)
    except Exception:
        pass
    _compat_0643(tm)
    try:
        if op[0] == 'scale':
            tm.font_size_grid = max(0.1, _compat_0637(self, float(getattr(tm, 'font_size_grid', 0.75) or 0.75) * float(font_factor)))
    except Exception:
        pass

def _compat_0638(g):
    x = float(getattr(g, 'x', 0.0) or 0.0)
    y = float(getattr(g, 'y', 0.0) or 0.0)
    w = float(getattr(g, 'w', 0.0) or 0.0)
    h = float(getattr(g, 'h', 0.0) or 0.0)
    return [(x, y), (x + w, y), (x + w, y - h), (x, y - h)]

def _compat_0393(item, attr):
    m = getattr(item, 'model', None)
    if m is None:
        return None
    k = _compat_0392(item)
    try:
        if k == 'GRAPHIC':
            st = getattr(m, 'style', None)
            return getattr(st, attr, None)
        return getattr(m, attr, None)
    except Exception:
        return None

def _compat_0389(self):
    # The placeholder is not a real line style. It appears only when selected
    # objects have different values. Ignore it until the user chooses a real one.
    try:
        if hasattr(self, 'line_style') and self.line_style.currentText() == _compat_0051:
            return
        if hasattr(self, 'line_width') and float(self.line_width.value()) <= 0.0:
            return
    except Exception:
        return
    mode_state = _compat_0387(self) if '_compat_0387' in globals() else None
    sig = _compat_0371(self) if '_compat_0371' in globals() else []
    try:
        if _compat_0395 is not None:
            return _compat_0395(self)
    except Exception as e:
        try: self.statusBar().showMessage(f'Line style update failed: {e}', 5000)
        except Exception: pass
    finally:
        if mode_state is not None and '_compat_0382' in globals():
            _compat_0382(self, mode_state)
        if '_compat_0381' in globals():
            _compat_0381(self, sig=sig, filter_state=mode_state, force_body=any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in sig), refresh=False)
        try: QTimer.singleShot(0, lambda: _compat_0397(self))
        except Exception: pass

def _compat_0412(self):
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
    return getattr(self, '_compat_0410', None)

def _compat_0409(self, value, fn, lo=-999, hi=999, step=.1):
    w = QDoubleSpinBox(); w.setRange(lo, hi); w.setSingleStep(step); w.setDecimals(3); w.setKeyboardTracking(False)
    try:
        w.blockSignals(True); w.setValue(float(value)); w.blockSignals(False)
    except Exception:
        try: w.blockSignals(True); w.setValue(0.0); w.blockSignals(False)
        except Exception: pass
    def safe(v):
        sig = _compat_0371(self) if '_compat_0371' in globals() else []
        fs = _compat_0387(self) if '_compat_0387' in globals() else None
        body_ctx = _compat_0406(self, sig)
        def do():
            try: fn(float(v))
            except RuntimeError: return
            except Exception as e:
                try: self.statusBar().showMessage(f'Property update failed: {e}', 5000)
                except Exception: pass
            finally:
                if body_ctx: self._compat_0410 = 'BODY'
                _compat_0414(self, sig=sig, fs=fs, refresh_panel=True)
        try: QTimer.singleShot(0, do)
        except Exception: do()
    w.valueChanged.connect(safe)
    return w

def _compat_0408(self, items, val, fn):
    w = QComboBox(); w.blockSignals(True); w.addItems([str(x) for x in items]); w.setCurrentText(str(val)); w.blockSignals(False)
    def safe(v):
        # Ignore display-only mismatch marker.
        if str(v) == globals().get('_compat_0051', '<Multiple>'):
            return
        sig = _compat_0371(self) if '_compat_0371' in globals() else []
        fs = _compat_0387(self) if '_compat_0387' in globals() else None
        body_ctx = _compat_0406(self, sig)
        def do():
            try: fn(v)
            except RuntimeError: return
            except Exception as e:
                try: self.statusBar().showMessage(f'Property update failed: {e}', 5000)
                except Exception: pass
            finally:
                if body_ctx: self._compat_0410 = 'BODY'
                _compat_0414(self, sig=sig, fs=fs, refresh_panel=True)
        try: QTimer.singleShot(0, do)
        except Exception: do()
    w.currentTextChanged.connect(safe)
    return w

def _compat_0407(self, value, fn):
    w = QCheckBox(); w.blockSignals(True); w.setChecked(bool(value)); w.blockSignals(False)
    def safe(v):
        sig = _compat_0371(self) if '_compat_0371' in globals() else []
        fs = _compat_0387(self) if '_compat_0387' in globals() else None
        body_ctx = _compat_0406(self, sig)
        def do():
            try: fn(bool(v))
            except RuntimeError: return
            except Exception as e:
                try: self.statusBar().showMessage(f'Property update failed: {e}', 5000)
                except Exception: pass
            finally:
                if body_ctx: self._compat_0410 = 'BODY'
                _compat_0414(self, sig=sig, fs=fs, refresh_panel=True)
        try: QTimer.singleShot(0, do)
        except Exception: do()
    w.toggled.connect(safe)
    return w

def _compat_0417(self, m, a, v):
    sig = _compat_0371(self) if '_compat_0371' in globals() else []
    fs = _compat_0387(self) if '_compat_0387' in globals() else None
    body_ctx = _compat_0406(self, sig)
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
    if body_ctx: self._compat_0410 = 'BODY'
    _compat_0414(self, sig=sig, fs=fs, refresh_panel=True)

def _compat_0416(self, key, val):
    sig = _compat_0371(self) if '_compat_0371' in globals() else []
    fs = _compat_0387(self) if '_compat_0387' in globals() else None
    body_ctx = _compat_0406(self, sig)
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
        if body_ctx: self._compat_0410 = 'BODY'
        _compat_0414(self, sig=sig, fs=fs, refresh_panel=True)

def _compat_0415(self, key, val):
    sig = _compat_0371(self) if '_compat_0371' in globals() else []
    fs = _compat_0387(self) if '_compat_0387' in globals() else None
    body_ctx = _compat_0406(self, sig)
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
        if body_ctx: self._compat_0410 = 'BODY'
        _compat_0414(self, sig=sig, fs=fs, refresh_panel=True)

def _compat_0435(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    return x, y, x + w, y - h

def _compat_0440(gr):
    x1, y1, x2, y2 = _compat_0435(gr)
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

def _compat_0468(gr):
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

def _compat_0494(gr, gid):
    gid = str(gid or '')
    try:
        gr.group_id = gid
    except Exception:
        pass
    try:
        gr.graphic_role = ('user_graphic_group:' + gid) if gid else 'user_graphic'
    except Exception:
        pass

def _compat_0481(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    x2 = x + w
    y2 = y - h
    return min(x, x2), min(y, y2), max(x, x2), max(y, y2)

def _compat_0519(gr, gid):
    gid = str(gid or '')
    try:
        gr.group_id = gid
    except Exception:
        pass
    try:
        gr.graphic_role = ('user_graphic_group:' + gid) if gid else 'user_graphic'
    except Exception:
        pass

def _compat_0499(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    x2 = x + w
    y2 = y - h
    return min(x, x2), min(y, y2), max(x, x2), max(y, y2)

def _compat_0526(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0); y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0); h = float(getattr(gr, 'h', 0.0) or 0.0)
    x2 = x + w; y2 = y - h
    return min(x, x2), min(y, y2), max(x, x2), max(y, y2)

def _compat_0592(gr, gid):
    gid = str(gid or '')
    try: gr.group_id = gid
    except Exception: pass
    try: gr.graphic_role = ('user_graphic_group:' + gid) if gid else 'user_graphic'
    except Exception: pass

def _compat_0576(models):
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

def _compat_0577(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0); y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0); h = float(getattr(gr, 'h', 0.0) or 0.0)
    return x + w / 2.0, y - h / 2.0

def _compat_0593(gr, cx, cy):
    w = float(getattr(gr, 'w', 0.0) or 0.0); h = float(getattr(gr, 'h', 0.0) or 0.0)
    gr.x = cx - w / 2.0
    gr.y = cy + h / 2.0

def _compat_0217(sym, index):
    try:
        units = list(getattr(sym, 'units', []) or [])
        is_split = (
            getattr(sym, 'kind', '') == SymbolKind.SPLIT.value
            or bool(getattr(sym, 'is_split', False))
            or len(units) > 1
        )
        kind = 'Split' if is_split else 'Single'
        return f'{index + 1}: {getattr(sym, "name", "Symbol")} [{kind}]'
    except Exception:
        return f'{index + 1}: Symbol'

def _compat_0231(self):
    try:
        if hasattr(self, 'is_split_symbol_model'):
            return bool(getattr(self.library, 'symbols', None)) and self.is_split_symbol_model(self.symbol)
        units = list(getattr(self.symbol, 'units', []) or [])
        return bool(getattr(self.library, 'symbols', None)) and (
            getattr(self.symbol, 'kind', '') == SymbolKind.SPLIT.value
            or bool(getattr(self.symbol, 'is_split', False))
            or len(units) > 1
        )
    except Exception:
        return False

def _compat_0981(self):
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
            for gr in _compat_0982(self, self.current_unit):
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

def _compat_1012(self, model, window):
    _compat_1008(self, model, window)
    try:
        if getattr(self, 'data', lambda *_: None)(0) == 'TEXT':
            setattr(self.model, '_is_attribute_text', False)
            if _compat_0068 is not None:
                self.setFlag(_compat_0068.ItemIsSelectable, True)
                self.setFlag(_compat_0068.ItemIsMovable, True)
                self.setFlag(_compat_0068.ItemIsFocusable, True)
    except Exception:
        pass

def _compat_1041(self, event):
    try:
        if _compat_1033(self) and event.button() == Qt.LeftButton:
            mods = event.modifiers()
            if not (mods & (Qt.ControlModifier | Qt.ShiftModifier)):
                sc = self.scene()
                if sc is not None:
                    sc.clearSelection()
                    self.setSelected(True)
    except Exception:
        pass
    return _compat_1038(self, event)

def _compat_1068(win):
    return getattr(win, 'current_unit', None) or getattr(win, 'unit', None)

def _compat_1066(self, event):
    try:
        if _compat_1048(self) and event.button() == Qt.LeftButton:
            win = getattr(self, 'window', None)
            if win is not None:
                win._compat_1043 = self.model
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
    return _compat_1058(self, event)

def _compat_1071(self):
    try: _compat_1072(getattr(self, 'unit', None)); _compat_1072(getattr(self, 'current_unit', None)); _compat_1072(getattr(self, 'library', None))
    except Exception: pass
    return _compat_1069(self)

def _compat_1087(self, entries, old_bounds, new_bounds):
    entries = list(entries or [])
    if not entries:
        return
    try:
        xs = [_compat_1075(x) for _, x, _ in entries]
        ys = [_compat_1075(y) for _, _, y in entries]
        ax = (min(xs) + max(xs)) / 2.0
        ay = (min(ys) + max(ys)) / 2.0
    except Exception:
        try:
            ax, ay = _compat_1075(entries[0][1]), _compat_1075(entries[0][2])
        except Exception:
            return
    dx, dy = _compat_1088(self, ax, ay, old_bounds, new_bounds)
    for t, tx, ty in entries:
        try:
            t.x = _compat_1081(self, _compat_1075(tx) + dx)
            t.y = _compat_1081(self, _compat_1075(ty) + dy)
        except Exception:
            pass

def _compat_1101(self):
    try:
        return getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    except Exception:
        return None

def _compat_1116(self):
    try:
        return getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    except Exception:
        return None

def _compat_1106(g):
    # Axis-aligned visible extent in model grid.  BODY artwork currently uses
    # orthogonal imported primitives; include all four corners so negative w/h
    # or previous flips cannot shrink the resulting outline.
    try:
        x = _compat_1075(getattr(g, 'x', 0.0))
        y = _compat_1075(getattr(g, 'y', 0.0))
        w = _compat_1075(getattr(g, 'w', getattr(g, 'width', 0.0)))
        h = _compat_1075(getattr(g, 'h', getattr(g, 'height', 0.0)))
        pts = [(x, y), (x + w, y), (x, y - h), (x + w, y - h)]
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        return min(xs), max(ys), max(xs), min(ys)
    except Exception:
        return None

def _compat_1115(old_outline, new_outline, block_x, block_y):
    old_l, old_t, old_r, old_b = old_outline
    new_l, new_t, new_r, new_b = new_outline
    old_cx, old_cy = (old_l + old_r) / 2.0, (old_t + old_b) / 2.0
    new_cx, new_cy = (new_l + new_r) / 2.0, (new_t + new_b) / 2.0
    # Move a text block with the closest BODY outline side.  It is a pure
    # translation; no scale, no spacing and no font size changes.
    x = _compat_1075(block_x); y = _compat_1075(block_y)
    dx = (new_l - old_l) if x < old_cx else (new_r - old_r)
    dy = (new_t - old_t) if y > old_cy else (new_b - old_b)
    # If the block lies horizontally inside the body range, center translation
    # is visually cleaner. Same for vertical inside range.
    if old_l <= x <= old_r:
        dx = new_cx - old_cx
    if old_b <= y <= old_t:
        dy = new_cy - old_cy
    return dx, dy

def _compat_1107(self, entries, old_outline, new_outline):
    entries = list(entries or [])
    if not entries:
        return
    try:
        bx = (min(_compat_1075(x) for _, x, _ in entries) + max(_compat_1075(x) for _, x, _ in entries)) / 2.0
        by = (min(_compat_1075(y) for _, _, y in entries) + max(_compat_1075(y) for _, _, y in entries)) / 2.0
    except Exception:
        try: bx, by = entries[0][1], entries[0][2]
        except Exception: return
    dx, dy = _compat_1115(old_outline, new_outline, bx, by)
    for t, tx, ty in entries:
        try:
            t.x = _compat_1112(self, _compat_1075(tx) + dx)
            t.y = _compat_1112(self, _compat_1075(ty) + dy)
        except Exception:
            pass

def _compat_0854(self):
    try:
        return self.current_unit
    except Exception:
        return getattr(self, 'unit', None)

def _compat_0861(self):
    try:
        return StyleModel(
            stroke=getattr(self, 'default_color', (0, 0, 0)),
            line_width=float(self.line_width.value()),
            line_style=str(self.line_style.currentText()),
        )
    except Exception:
        return StyleModel()

def _compat_0860(items):
    out = []
    for item in items or []:
        try:
            if item.data(0) == 'GRAPHIC' and getattr(item, 'model', None) is not None:
                out.append(item.model)
        except Exception:
            pass
    return out

def _compat_0853(self, items, attr, default=''):
    vals = []
    for item in items or []:
        try:
            m = item.model
            if item.data(0) != 'GRAPHIC':
                continue
            if attr in ('line_width', 'line_style', 'stroke', 'fill'):
                vals.append(getattr(m.style, attr, default))
            else:
                vals.append(getattr(m, attr, default))
        except Exception:
            pass
    if not vals:
        return default
    first = vals[0]
    return first if all(v == first for v in vals) else default
