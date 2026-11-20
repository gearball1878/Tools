"""Pin docking, grid, snapping and pin-table helpers.

Executed in the shared ``main_window.py`` global namespace by ``legacy_updates.apply_legacy_updates``.
"""

from __future__ import annotations

def _compat_1234(self, u):
    # Axis docking is only valid for unrotated internal <NONE>-style bodies.
    # Imported/template bodies already carry native pin anchors and must not be
    # re-docked to an axis-aligned proxy rectangle on every rebuild.
    try:
        if _compat_1230(self, u):
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

def _compat_0313(self, unit=None):
    u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    _compat_0334(self, u)
    b = u.body
    base = {
        'unit_id': id(u),
        'origin_mode': getattr(self.symbol, 'origin', OriginMode.CENTER.value),
        'pivot': (0.0, 0.0),
        'has_body_graphics': bool(_compat_0309(self, u)),
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

def _compat_0331(self, v, mn=0.01):
    try:
        return self._snap_to_edit_grid(v, mn)
    except Exception:
        try:
            step = self._edit_grid_step()
            return max(mn, round(float(v) / step) * step)
        except Exception:
            return max(mn, float(v))

def _compat_0642(self, value, mn=0.01):
    try:
        step = float(self._edit_grid_step())
        if step <= 0: step = float(getattr(self, 'edit_grid_inch', 0.1) or 0.1)
        return max(float(mn), round(float(value) / step) * step)
    except Exception:
        try: return self._snap_to_edit_grid(value, mn)
        except Exception: return max(float(mn), float(value))

def _compat_0641(side, op):
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

def _compat_0071(self):
    try:
        return max(0.001, float(getattr(self, 'edit_grid_step', None) or self.edit_grid.value() or self.grid_inch))
    except Exception:
        try: return max(0.001, float(getattr(self, 'grid_inch', 1.0) or 1.0))
        except Exception: return 1.0

def _compat_0081(self, v):
    step = _compat_0071(self)
    try: return self._clean_float(round(float(v) / step) * step)
    except Exception: return v

def _compat_0074(self, pin, dx, dy):
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

def _compat_0077(self, start_state, body):
    old_x = float(start_state.get('x', body.x)); old_y = float(start_state.get('y', body.y))
    old_w = max(float(start_state.get('w', body.width)), 1e-9)
    old_h = max(float(start_state.get('h', body.height)), 1e-9)
    new_x, new_y = float(body.x), float(body.y)
    new_w, new_h = max(float(body.width), 1e-9), max(float(body.height), 1e-9)
    sx, sy = new_w / old_w, new_h / old_h

    def sxpos(px): return _compat_0081(self, new_x + (float(px) - old_x) * sx)
    def sypos(py): return _compat_0081(self, new_y - (old_y - float(py)) * sy)

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
        nx, ny = _compat_0081(self, nx), _compat_0081(self, ny)
        p.x, p.y = nx, ny
        # Critical: BODY scale must not scale pins.  Length stays as authored.
        try: p.length = max(0.1, float(plen))
        except Exception: pass
        _compat_0074(self, p, nx - ox, ny - oy)

def _compat_0342(self):
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

def _compat_0354(self, v):
    step = _compat_0342(self)
    try: return _compat_0340(self, round(float(v) / step) * step)
    except Exception: return float(v)

def _compat_0345(self, pin, dx, dy):
    try:
        self._move_pin_owned_texts(pin, dx, dy); return
    except Exception:
        pass
    for ax, ay in (('label_x','label_y'), ('number_x','number_y')):
        try:
            if getattr(pin, ax, None) is not None and getattr(pin, ay, None) is not None:
                setattr(pin, ax, _compat_0340(self, float(getattr(pin, ax)) + dx))
                setattr(pin, ay, _compat_0340(self, float(getattr(pin, ay)) + dy))
        except Exception: pass
    for tm in (getattr(pin, 'attribute_texts', {}) or {}).values():
        try:
            tm.x = _compat_0340(self, float(tm.x) + dx); tm.y = _compat_0340(self, float(tm.y) + dy)
        except Exception: pass

def _compat_0348(self, unit, start, old_bounds, new_bounds):
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
        p.x, p.y = _compat_0354(self, tx), _compat_0354(self, ty)
        try: p.length = float(plen)
        except Exception: pass
        _compat_0345(self, p, p.x - old_px, p.y - old_py)

def _compat_0353(self, direction: int):
    self.set_tool(DrawTool.SELECT.value)
    if self._selected_body_active():
        b = self.current_unit.body; step = _compat_0342(self)
        self.push_undo_state(); self._selection_restore_ids = self._capture_selection_ids()
        _compat_0349(self, float(b.width) + direction * step, float(b.height) + direction * step, refresh=True)
    else:
        if _compat_0346 is not None:
            return _compat_0346(self, direction)
        return self.scale_selected(1.0 + (0.1 if direction > 0 else -0.1))

def _compat_0359(self, unit, start, old_bounds, new_bounds):
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
        p.x, p.y = _compat_0354(self, tx), _compat_0354(self, ty)
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
        _compat_0345(self, p, p.x - old_px, p.y - old_py)

def _compat_0363(self, direction: int):
    self.set_tool(DrawTool.SELECT.value)
    if self._selected_body_active():
        b = self.current_unit.body; step = _compat_0342(self)
        keep_ids = _compat_0364(self) or {id(b)}
        self.push_undo_state(); self._selection_restore_ids = keep_ids
        _compat_0360(self, float(b.width) + direction * step, float(b.height) + direction * step, refresh=True)
    else:
        if _compat_0346 is not None:
            keep_ids = _compat_0364(self)
            r = _compat_0346(self, direction)
            _compat_0358(self, keep_ids)
            return r
        return self.scale_selected(1.0 + (0.1 if direction > 0 else -0.1))

def _compat_0370(self, direction: int):
    sig = _compat_0371(self)
    try: self.set_tool(DrawTool.SELECT.value)
    except Exception: pass
    if self._selected_body_active():
        b = self.current_unit.body; step = _compat_0342(self)
        try: self.push_undo_state()
        except Exception: pass
        r = _compat_0367(self, float(b.width) + direction * step, float(b.height) + direction * step, refresh=True)
        _compat_0366(self, sig)
        return r
    try:
        if _compat_0346 is not None:
            r = _compat_0346(self, direction)
        else:
            r = self.scale_selected(1.0 + (0.1 if direction > 0 else -0.1))
    finally:
        _compat_0366(self, sig)
    return r

def _compat_0385(self, direction:int):
    def work():
        # Pins must never be geometrically scaled. If BODY is part of the current
        # selection, route exclusively through BODY resize/redock. If only pins
        # are selected, Scale +/- is a no-op for them.
        try:
            if self._selected_body_active():
                return _compat_0380(self, direction)
            selected = list(self.scene.selectedItems())
            if selected and all(getattr(i, 'data', lambda *_: None)(0) == 'PIN' for i in selected):
                try: self.statusBar().showMessage('Pins are not scaled by Scale +/-; edit pin length explicitly.', 2500)
                except Exception: pass
                return None
        except Exception:
            pass
        return _compat_0380(self, direction)
    return _compat_0388(self, work, force_body=bool(self._selected_body_active()))

def _compat_0425(self):
    try:
        return max(float(self._edit_grid_step()), 1e-9)
    except Exception:
        try:
            return max(float(getattr(self, 'edit_grid_px', 0.0) or 0.0) / max(float(getattr(self, 'grid_px', 1.0) or 1.0), 1e-9), 1e-9)
        except Exception:
            return 0.1

def _compat_0434(self, v):
    try:
        return float(self._snap_to_edit_grid(float(v), _compat_0425(self)))
    except Exception:
        try:
            step = _compat_0425(self)
            return round(float(v) / step) * step
        except Exception:
            return float(v)

def _compat_0432(self, direction:int):
    try:
        if self._selected_body_active():
            return _compat_0429(self, direction) if _compat_0429 else None
    except Exception:
        pass
    items = _compat_0433(self)
    # Regular inserted/drawn graphics get a real geometry scale. Pins stay excluded.
    if _compat_0427(self, items) or any(getattr(i, 'data', lambda *_: None)(0) in ('TEXT','ATTR_REF_DES','ATTR_BODY') for i in items):
        return _compat_0431(self, 1.0 + (0.1 if int(direction) > 0 else -0.1))
    if _compat_0429 is not None:
        return _compat_0429(self, direction)

def _compat_0450(self):
    try:
        return max(float(self._edit_grid_step()), 1e-9)
    except Exception:
        try:
            txt = str(getattr(self, 'edit_grid_combo', None).currentText()).replace('"','').strip()
            return max(float(txt), 1e-9)
        except Exception:
            return 0.1

def _compat_0449(self, v):
    try:
        return float(self._snap_to_edit_grid(float(v), _compat_0450(self)))
    except Exception:
        st = _compat_0450(self)
        try: return round(float(v) / st) * st
        except Exception: return float(v)

def _compat_0444(self, direction):
    graphics = _compat_0437(self)
    if not graphics:
        return False
    b = _compat_0438(graphics)
    if not b:
        return False
    minx, miny, maxx, maxy = b
    st = _compat_0450(self)
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
        x1, y1, x2, y2 = _compat_0435(gr)
        nx1, ny1 = _compat_0445(self, x1, y1, cx, cy, factor)
        nx2, ny2 = _compat_0445(self, x2, y2, cx, cy, factor)
        # Prevent collapse after snapping.  Preserve direction signs as far as possible.
        if abs(x2 - x1) > 1e-12 and abs(nx2 - nx1) < st:
            sgn = 1.0 if (x2 - x1) >= 0 else -1.0
            nx1 = _compat_0449(self, (nx1 + nx2) / 2.0 - sgn * st / 2.0)
            nx2 = _compat_0449(self, (nx1 + nx2) / 2.0 + sgn * st / 2.0)
        if abs(y2 - y1) > 1e-12 and abs(ny2 - ny1) < st:
            sgn = 1.0 if (y2 - y1) >= 0 else -1.0
            ny1 = _compat_0449(self, (ny1 + ny2) / 2.0 - sgn * st / 2.0)
            ny2 = _compat_0449(self, (ny1 + ny2) / 2.0 + sgn * st / 2.0)
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
            ncx, ncy = _compat_0445(self, cabs[0], cabs[1], cx, cy, factor)
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

def _compat_0447(self, direction:int):
    try:
        if self._selected_body_active():
            return _compat_0442(self, direction) if _compat_0442 else None
    except Exception:
        pass
    sig = _compat_0371(self) if '_compat_0371' in globals() else []
    fs = _compat_0387(self) if '_compat_0387' in globals() else None
    try:
        if _compat_0444(self, direction):
            return None
        if _compat_0442 is not None:
            return _compat_0442(self, direction)
    finally:
        try: _compat_0381(self, sig=sig, filter_state=fs, force_body=False, refresh=False)
        except Exception: pass

def _compat_0478(self):
    try:
        return max(float(self._edit_grid_step()), 1e-9)
    except Exception:
        return 0.1

def _compat_0464(self):
    # The UI properties are expressed in grid units. For toolbar Scale +/- the
    # expected interaction is one grid unit per click (3x3 -> 4x4), while the
    # resulting coordinates are still snapped to the active edit grid.
    try:
        return max(1.0, _compat_0478(self))
    except Exception:
        return 1.0

def _compat_0477(self, v):
    st = _compat_0478(self)
    try:
        return float(self._snap_to_edit_grid(float(v), st))
    except Exception:
        try:
            return round(float(v) / st) * st
        except Exception:
            return float(v)

def _compat_0474(self, direction:int):
    try:
        if self._selected_body_active():
            return _compat_0471(self, direction) if _compat_0471 else None
    except Exception:
        pass
    sig = _compat_0371(self) if '_compat_0371' in globals() else []
    fs = _compat_0387(self) if '_compat_0387' in globals() else None
    try:
        if _compat_0453(self, int(direction)):
            return None
        if _compat_0471:
            return _compat_0471(self, direction)
    finally:
        try:
            _compat_0381(self, sig=sig, filter_state=fs, force_body=False, refresh=False)
        except Exception:
            pass

def _compat_0482(self):
    try:
        return max(float(self._edit_grid_step()), 1e-9)
    except Exception:
        try:
            txt = str(self.edit_grid_combo.currentText()).replace('"', '').strip()
            return max(float(txt), 1e-9)
        except Exception:
            return 1.0

def _compat_0495(self, v):
    st = _compat_0482(self)
    try:
        return float(self._snap_to_edit_grid(float(v), st))
    except Exception:
        return round(float(v) / st) * st

def _compat_0492(self, direction:int):
    try:
        if self._selected_body_active():
            return _compat_0489(self, direction) if _compat_0489 else None
    except Exception:
        pass
    if _compat_0479(self, int(direction)):
        return None
    if _compat_0489:
        return _compat_0489(self, direction)

def _compat_0507(self):
    try:
        return max(float(self._edit_grid_step()), 1e-9)
    except Exception:
        return 0.05

def _compat_0523(self):
    # BODY toolbar scaling in this tool is a visible grid-size operation. Keep
    # the same interaction for graphics: 3x3 -> 4x4 while still snapping to the
    # active Edit grid.
    try:
        return max(1.0, _compat_0507(self))
    except Exception:
        return 1.0

def _compat_0520(self, v):
    st = _compat_0507(self)
    try:
        return float(self._snap_to_edit_grid(float(v), st))
    except Exception:
        return round(float(v) / st) * st

def _compat_0517(self, direction:int):
    try:
        if self._selected_body_active():
            return _compat_0515(self, direction) if _compat_0515 else None
    except Exception:
        pass
    if _compat_0498(self, int(direction)):
        return None
    if _compat_0515:
        return _compat_0515(self, direction)

def _compat_0529(self):
    try: return max(1e-9, float(self._edit_grid_step()))
    except Exception: return 0.05

def _compat_0547(self, value):
    st = _compat_0529(self)
    try: return float(self._snap_to_edit_grid(float(value), st))
    except Exception: return round(float(value) / st) * st

def _compat_0544(self, direction:int):
    try:
        if self._selected_body_active():
            return _compat_0541(self, direction) if _compat_0541 else None
    except Exception:
        pass
    if _compat_0525(self, int(direction)):
        return None
    if _compat_0541:
        return _compat_0541(self, direction)

def _compat_0568(self):
    try: return max(1e-9, float(self._edit_grid_step()))
    except Exception: return 0.05

def _compat_0594(self, value):
    st = _compat_0568(self)
    try: return float(self._snap_to_edit_grid(float(value), st))
    except Exception: return round(float(value) / st) * st

def _compat_0579(self, models):
    # Use the model-space maximum x/y box as stable transformation origin. This
    # keeps the origin stable across refreshes; the visual outline is computed
    # separately from the live QGraphicsItem scene bounding boxes.
    b = _compat_0576(models)
    if not b:
        return 0.0, 0.0
    minx, miny, maxx, maxy = b
    return (minx + maxx) / 2.0, (miny + maxy) / 2.0

def _compat_0587(self, direction:int):
    try:
        if self._selected_body_active():
            return _compat_0584(self, direction) if _compat_0584 else None
    except Exception:
        pass
    if _compat_0562(self, direction):
        return None
    if _compat_0584:
        return _compat_0584(self, direction)

def _compat_0251(unit, idx):
    try:
        pin_count = len(getattr(unit, 'pins', []) or [])
        return f'{idx + 1}: {getattr(unit, "name", f"Part {idx + 1}")}  ({pin_count} pins)'
    except Exception:
        return f'{idx + 1}: Part {idx + 1}'

def _compat_0304(self):
    if not hasattr(self, 'edit_grid_combo'):
        return
    try:
        existing = {self.edit_grid_combo.itemText(i) for i in range(self.edit_grid_combo.count())}
        for text in ['0.100"', '0.050"', '0.025"', '0.010"', '0.005"', '0.003"']:
            if text not in existing:
                self.edit_grid_combo.addItem(text)
                existing.add(text)
        self.edit_grid_combo.blockSignals(True)
        self.edit_grid_combo.setCurrentText('0.100"')
    finally:
        try:
            self.edit_grid_combo.blockSignals(False)
        except Exception:
            pass
    try:
        self.set_edit_grid('0.100"')
    except Exception:
        self.edit_grid_inch = 0.100

def _compat_0301(self, text):
    result = _compat_0300(self, text)
    try:
        # Avoid accidental sub-pixel defaults from old autosync patches.
        if not getattr(self, '_allow_fine_auto_grid', False) and str(text).strip() in ('', 'auto'):
            self.edit_grid_inch = 0.100
    except Exception:
        pass
    return result

def _compat_0986(self):
    try:
        return max(0.001, float(getattr(self, 'edit_grid_step', 0) or self.edit_grid.value() or self.grid_inch or 1.0))
    except Exception:
        return 1.0

def _compat_0999(self, v):
    step = _compat_0986(self)
    try:
        return _compat_0985(self, round(float(v) / step) * step)
    except Exception:
        return float(v)

def _compat_0989(self, pin, dx, dy):
    try:
        self._move_pin_owned_texts(pin, dx, dy)
        return
    except Exception:
        pass
    for ax, ay in (('label_x','label_y'), ('number_x','number_y')):
        try:
            if getattr(pin, ax, None) is not None and getattr(pin, ay, None) is not None:
                setattr(pin, ax, _compat_0985(self, float(getattr(pin, ax)) + dx))
                setattr(pin, ay, _compat_0985(self, float(getattr(pin, ay)) + dy))
        except Exception:
            pass
    for tm in (getattr(pin, 'attribute_texts', {}) or {}).values():
        try:
            tm.x = _compat_0985(self, float(tm.x) + dx)
            tm.y = _compat_0985(self, float(tm.y) + dy)
        except Exception:
            pass

def _compat_0992(self, unit, start, old_bounds, new_bounds):
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
        p.x = _compat_0999(self, tx)
        p.y = _compat_0999(self, ty)
        try:
            p.length = float(plen)
        except Exception:
            pass
        _compat_0989(self, p, p.x - old_px, p.y - old_py)

def _compat_0997(self, direction: int):
    self.set_tool(DrawTool.SELECT.value)
    if self._selected_body_active():
        step = _compat_0986(self)
        b = self.current_unit.body
        self.push_undo_state()
        self._selection_restore_ids = self._capture_selection_ids()
        _compat_0993(self, float(b.width) + direction * step, float(b.height) + direction * step, refresh=True)
    else:
        # Keep old behavior for non-BODY graphics.
        try: return _compat_0990(self, direction)
        except Exception: return self.scale_selected(1.0 + (0.1 if direction > 0 else -0.1))

def _compat_1067(win, items, direction):
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
    _compat_1060(win, items)

def _compat_1063(self, direction:int):
    items = _compat_1064(self, allow_active=True)
    if items:
        self.set_tool(DrawTool.SELECT.value)
        self.push_undo_state()
        _compat_1067(self, items, direction)
        self.dirty = True
        return None
    return _compat_1056(self, direction)

def _compat_1074(self):
    try:
        return max(1e-9, float(self._edit_grid_step()))
    except Exception:
        try:
            return max(1e-9, float(getattr(getattr(self, 'symbol', None), 'grid_inch', 0.1) or 0.1))
        except Exception:
            return 0.1

def _compat_1081(self, v):
    step = _compat_1074(self)
    try:
        return round(float(v) / step) * step
    except Exception:
        return float(v)

def _compat_1077(p, old_px, old_py, new_px, new_py):
    dx = float(new_px) - float(old_px)
    dy = float(new_py) - float(old_py)
    try:
        if getattr(p, 'label_x', None) is not None:
            p.label_x = _compat_1075(p.label_x) + dx
        if getattr(p, 'label_y', None) is not None:
            p.label_y = _compat_1075(p.label_y) + dy
        if getattr(p, 'number_x', None) is not None:
            p.number_x = _compat_1075(p.number_x) + dx
        if getattr(p, 'number_y', None) is not None:
            p.number_y = _compat_1075(p.number_y) + dy
        for tm in (getattr(p, 'attribute_texts', {}) or {}).values():
            try:
                tm.x = _compat_1075(tm.x) + dx
                tm.y = _compat_1075(tm.y) + dy
            except Exception:
                pass
    except Exception:
        pass

def _compat_1079(self, start_state, body):
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
                old_pos[entry[0]] = (_compat_1075(entry[1]), _compat_1075(entry[2]))
    except Exception:
        pass
    bx = _compat_1075(getattr(body, 'x', 0.0))
    by = _compat_1075(getattr(body, 'y', 0.0))
    bw = max(_compat_1074(self), abs(_compat_1075(getattr(body, 'width', 0.0))))
    bh = max(_compat_1074(self), abs(_compat_1075(getattr(body, 'height', 0.0))))
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
            old_px, old_py = old_pos.get(p, (_compat_1075(getattr(p, 'x', x)), _compat_1075(getattr(p, 'y', y))))
            nx, ny = _compat_1081(self, x), _compat_1081(self, y)
            p.x, p.y = nx, ny
            _compat_1077(p, old_px, old_py, nx, ny)

    def place_horizontal(group, y):
        n = len(group)
        if n <= 0:
            return
        for i, p in enumerate(group):
            if n == 1:
                x = cx
            else:
                x = bx + ((i + 1) * bw / (n + 1))
            old_px, old_py = old_pos.get(p, (_compat_1075(getattr(p, 'x', x)), _compat_1075(getattr(p, 'y', y))))
            nx, ny = _compat_1081(self, x), _compat_1081(self, y)
            p.x, p.y = nx, ny
            _compat_1077(p, old_px, old_py, nx, ny)

    place_vertical(left, bx)
    place_vertical(right, bx + bw)
    place_horizontal(top, by)
    place_horizontal(bottom, by - bh)

def _compat_1082(pin, old_bounds):
    try:
        ox, oy, ow, oh = old_bounds
        px = _compat_1075(getattr(pin, 'x', 0.0))
        py = _compat_1075(getattr(pin, 'y', 0.0))
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

def _compat_1083(self, start_state, body):
    try:
        pins = list(getattr(getattr(self, 'current_unit', None), 'pins', []) or [])
    except Exception:
        pins = []
    if not pins:
        return
    old_x = _compat_1075((start_state or {}).get('x', getattr(body, 'x', 0.0)))
    old_y = _compat_1075((start_state or {}).get('y', getattr(body, 'y', 0.0)))
    old_w = max(_compat_1074(self), abs(_compat_1075((start_state or {}).get('w', getattr(body, 'width', 1.0)), 1.0)))
    old_h = max(_compat_1074(self), abs(_compat_1075((start_state or {}).get('h', getattr(body, 'height', 1.0)), 1.0)))
    old_bounds = (old_x, old_y, old_w, old_h)
    old_pos = {}
    try:
        for entry in (start_state or {}).get('pins', []) or []:
            if len(entry) >= 3:
                old_pos[entry[0]] = (_compat_1075(entry[1]), _compat_1075(entry[2]))
    except Exception:
        pass

    bx = _compat_1075(getattr(body, 'x', 0.0))
    by = _compat_1075(getattr(body, 'y', 0.0))
    bw = max(_compat_1074(self), abs(_compat_1075(getattr(body, 'width', 0.0))))
    bh = max(_compat_1074(self), abs(_compat_1075(getattr(body, 'height', 0.0))))
    left_x, right_x = bx, bx + bw
    top_y, bottom_y = by, by - bh
    cx, cy = bx + bw / 2.0, by - bh / 2.0

    groups = {PinSide.LEFT.value: [], PinSide.RIGHT.value: [], PinSide.TOP.value: [], PinSide.BOTTOM.value: []}
    for p in pins:
        groups.setdefault(_compat_1082(p, old_bounds), []).append(p)

    # Stable order prevents pins from crossing when the BODY is scaled.
    groups[PinSide.LEFT.value].sort(key=lambda p: -_compat_1075(old_pos.get(p, (getattr(p, 'x', 0.0), getattr(p, 'y', 0.0)))[1]))
    groups[PinSide.RIGHT.value].sort(key=lambda p: -_compat_1075(old_pos.get(p, (getattr(p, 'x', 0.0), getattr(p, 'y', 0.0)))[1]))
    groups[PinSide.TOP.value].sort(key=lambda p: _compat_1075(old_pos.get(p, (getattr(p, 'x', 0.0), getattr(p, 'y', 0.0)))[0]))
    groups[PinSide.BOTTOM.value].sort(key=lambda p: _compat_1075(old_pos.get(p, (getattr(p, 'x', 0.0), getattr(p, 'y', 0.0)))[0]))

    def place_vertical(group, x, side_value):
        n = len(group)
        if n <= 0:
            return
        for i, p in enumerate(group):
            y = cy if n == 1 else by - ((i + 1) * bh / (n + 1))
            old_px, old_py = old_pos.get(p, (_compat_1075(getattr(p, 'x', x)), _compat_1075(getattr(p, 'y', y))))
            nx, ny = _compat_1081(self, x), _compat_1081(self, y)
            try: p.side = side_value
            except Exception: pass
            p.x, p.y = nx, ny
            _compat_1077(p, old_px, old_py, nx, ny)

    def place_horizontal(group, y, side_value):
        n = len(group)
        if n <= 0:
            return
        for i, p in enumerate(group):
            x = cx if n == 1 else bx + ((i + 1) * bw / (n + 1))
            old_px, old_py = old_pos.get(p, (_compat_1075(getattr(p, 'x', x)), _compat_1075(getattr(p, 'y', y))))
            nx, ny = _compat_1081(self, x), _compat_1081(self, y)
            try: p.side = side_value
            except Exception: pass
            p.x, p.y = nx, ny
            _compat_1077(p, old_px, old_py, nx, ny)

    place_vertical(groups.get(PinSide.LEFT.value, []), left_x, PinSide.LEFT.value)
    place_vertical(groups.get(PinSide.RIGHT.value, []), right_x, PinSide.RIGHT.value)
    place_horizontal(groups.get(PinSide.TOP.value, []), top_y, PinSide.TOP.value)
    place_horizontal(groups.get(PinSide.BOTTOM.value, []), bottom_y, PinSide.BOTTOM.value)

def _compat_1094(side):
    s = str(side or '').lower()
    valid = {PinSide.LEFT.value, PinSide.RIGHT.value, PinSide.TOP.value, PinSide.BOTTOM.value}
    return s if s in valid else ''

def _compat_1086(pin, bounds):
    try:
        x, y, w, h = bounds
        px = _compat_1075(getattr(pin, 'x', 0.0))
        py = _compat_1075(getattr(pin, 'y', 0.0))
        candidates = [
            (abs(px - x), PinSide.LEFT.value),
            (abs(px - (x + w)), PinSide.RIGHT.value),
            (abs(py - y), PinSide.TOP.value),
            (abs(py - (y - h)), PinSide.BOTTOM.value),
        ]
        return sorted(candidates, key=lambda t: t[0])[0][1]
    except Exception:
        return PinSide.LEFT.value

def _compat_1090(pin, old_bounds):
    # Keep metadata stable.  Previous versions over-inferred the side from the
    # temporary old geometry, which could make pins jump to another side during
    # resize/import normalization.
    return _compat_1094(getattr(pin, 'side', '')) or _compat_1086(pin, old_bounds)

def _compat_1089(start_state):
    old_pos = {}
    try:
        for entry in (start_state or {}).get('pins', []) or []:
            if len(entry) >= 3:
                old_pos[entry[0]] = (_compat_1075(entry[1]), _compat_1075(entry[2]))
    except Exception:
        pass
    return old_pos

def _compat_1091(self, start_state, body):
    try:
        pins = list(getattr(getattr(self, 'current_unit', None), 'pins', []) or [])
    except Exception:
        pins = []
    if not pins:
        return

    step = _compat_1074(self)
    ox = _compat_1075((start_state or {}).get('x', getattr(body, 'x', 0.0)))
    oy = _compat_1075((start_state or {}).get('y', getattr(body, 'y', 0.0)))
    ow = max(step, abs(_compat_1075((start_state or {}).get('w', getattr(body, 'width', 1.0)), 1.0)))
    oh = max(step, abs(_compat_1075((start_state or {}).get('h', getattr(body, 'height', 1.0)), 1.0)))
    old_bounds = (ox, oy, ow, oh)
    nx = _compat_1075(getattr(body, 'x', ox))
    ny = _compat_1075(getattr(body, 'y', oy))
    nw = max(step, abs(_compat_1075(getattr(body, 'width', ow), ow)))
    nh = max(step, abs(_compat_1075(getattr(body, 'height', oh), oh)))

    old_pos = _compat_1089(start_state)
    groups = {PinSide.LEFT.value: [], PinSide.RIGHT.value: [], PinSide.TOP.value: [], PinSide.BOTTOM.value: []}
    for p in pins:
        groups.setdefault(_compat_1090(p, old_bounds), []).append(p)

    # Keep visual order from the immutable start state.
    groups[PinSide.LEFT.value].sort(key=lambda p: -old_pos.get(p, (_compat_1075(getattr(p, 'x', 0.0)), _compat_1075(getattr(p, 'y', 0.0))))[1])
    groups[PinSide.RIGHT.value].sort(key=lambda p: -old_pos.get(p, (_compat_1075(getattr(p, 'x', 0.0)), _compat_1075(getattr(p, 'y', 0.0))))[1])
    groups[PinSide.TOP.value].sort(key=lambda p: old_pos.get(p, (_compat_1075(getattr(p, 'x', 0.0)), _compat_1075(getattr(p, 'y', 0.0))))[0])
    groups[PinSide.BOTTOM.value].sort(key=lambda p: old_pos.get(p, (_compat_1075(getattr(p, 'x', 0.0)), _compat_1075(getattr(p, 'y', 0.0))))[0])

    def _clamp01(v):
        try: return max(0.0, min(1.0, float(v)))
        except Exception: return 0.5

    def place_lr(group, side_value, x_edge):
        n = len(group)
        if not n:
            return
        for i, p in enumerate(group):
            old_px, old_py = old_pos.get(p, (_compat_1075(getattr(p, 'x', x_edge)), _compat_1075(getattr(p, 'y', ny - nh/2.0))))
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
            px = _compat_1081(self, x_edge)
            py = _compat_1081(self, ny - t * nh)
            try: p.side = side_value
            except Exception: pass
            p.x, p.y = px, py
            _compat_1077(p, old_px, old_py, px, py)

    def place_tb(group, side_value, y_edge):
        n = len(group)
        if not n:
            return
        for i, p in enumerate(group):
            old_px, old_py = old_pos.get(p, (_compat_1075(getattr(p, 'x', nx + nw/2.0)), _compat_1075(getattr(p, 'y', y_edge))))
            if n == 1:
                t = 0.5
            else:
                t = _clamp01((old_px - ox) / max(1e-9, ow))
                if t <= 0.02 or t >= 0.98:
                    t = (i + 1) / (n + 1)
            px = _compat_1081(self, nx + t * nw)
            py = _compat_1081(self, y_edge)
            try: p.side = side_value
            except Exception: pass
            p.x, p.y = px, py
            _compat_1077(p, old_px, old_py, px, py)

    place_lr(groups.get(PinSide.LEFT.value, []), PinSide.LEFT.value, nx)
    place_lr(groups.get(PinSide.RIGHT.value, []), PinSide.RIGHT.value, nx + nw)
    place_tb(groups.get(PinSide.TOP.value, []), PinSide.TOP.value, ny)
    place_tb(groups.get(PinSide.BOTTOM.value, []), PinSide.BOTTOM.value, ny - nh)

def _compat_1100(start_state):
    mp = {}
    try:
        for entry in (start_state or {}).get('pins', []) or []:
            if len(entry) >= 3:
                mp[entry[0]] = (_compat_1075(entry[1]), _compat_1075(entry[2]))
    except Exception:
        pass
    return mp

def _compat_1099(pin, old_outline):
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
        px = _compat_1075(getattr(pin, 'x', 0.0))
        py = _compat_1075(getattr(pin, 'y', 0.0))
        cand = [(abs(px-left), PinSide.LEFT.value), (abs(px-right), PinSide.RIGHT.value), (abs(py-top), PinSide.TOP.value), (abs(py-bottom), PinSide.BOTTOM.value)]
        return min(cand, key=lambda t: t[0])[1]
    except Exception:
        return PinSide.LEFT.value

def _compat_1097(self, start_state, body):
    unit = _compat_1101(self)
    if unit is None:
        return
    pins = list(getattr(unit, 'pins', []) or [])
    if not pins:
        return
    step = _compat_1074(self)
    old_x = _compat_1075((start_state or {}).get('x', getattr(body, 'x', 0.0)))
    old_y = _compat_1075((start_state or {}).get('y', getattr(body, 'y', 0.0)))
    old_w = max(step, abs(_compat_1075((start_state or {}).get('w', getattr(body, 'width', 1.0)), 1.0)))
    old_h = max(step, abs(_compat_1075((start_state or {}).get('h', getattr(body, 'height', 1.0)), 1.0)))
    old_outline = (old_x, old_y, old_x + old_w, old_y - old_h)
    left, top, right, bottom = _compat_1102(self, unit, body)
    left = _compat_1081(self, left); right = _compat_1081(self, right)
    top = _compat_1081(self, top); bottom = _compat_1081(self, bottom)
    height = max(step, abs(top - bottom))
    width = max(step, abs(right - left))
    old_pos = _compat_1100(start_state)

    groups = {PinSide.LEFT.value: [], PinSide.RIGHT.value: [], PinSide.TOP.value: [], PinSide.BOTTOM.value: []}
    for p in pins:
        groups.setdefault(_compat_1099(p, old_outline), []).append(p)

    groups[PinSide.LEFT.value].sort(key=lambda p: -old_pos.get(p, (_compat_1075(getattr(p, 'x', left)), _compat_1075(getattr(p, 'y', (top+bottom)/2.0))))[1])
    groups[PinSide.RIGHT.value].sort(key=lambda p: -old_pos.get(p, (_compat_1075(getattr(p, 'x', right)), _compat_1075(getattr(p, 'y', (top+bottom)/2.0))))[1])
    groups[PinSide.TOP.value].sort(key=lambda p: old_pos.get(p, (_compat_1075(getattr(p, 'x', (left+right)/2.0)), _compat_1075(getattr(p, 'y', top))))[0])
    groups[PinSide.BOTTOM.value].sort(key=lambda p: old_pos.get(p, (_compat_1075(getattr(p, 'x', (left+right)/2.0)), _compat_1075(getattr(p, 'y', bottom))))[0])

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
            old_px, old_py = old_pos.get(p, (_compat_1075(getattr(p, 'x', x_edge)), _compat_1075(getattr(p, 'y', (top + bottom) / 2.0))))
            if n == 1:
                t = 0.5
            else:
                t = _ratio((old_y - old_py) / max(1e-9, old_h))
                # If the imported pin was not meaningfully placed on the old body
                # outline, fall back to clean, centered distribution.
                if t <= 0.01 or t >= 0.99:
                    t = (i + 1) / (n + 1)
            px = _compat_1081(self, x_edge)
            py = _compat_1081(self, top - t * height)
            try:
                p.side = side_value
            except Exception:
                pass
            p.x, p.y = px, py
            _compat_1077(p, old_px, old_py, px, py)

    def _place_horizontal_side(group, side_value, y_edge):
        n = len(group)
        if not n:
            return
        for i, p in enumerate(group):
            old_px, old_py = old_pos.get(p, (_compat_1075(getattr(p, 'x', (left + right) / 2.0)), _compat_1075(getattr(p, 'y', y_edge))))
            if n == 1:
                t = 0.5
            else:
                t = _ratio((old_px - old_x) / max(1e-9, old_w))
                if t <= 0.01 or t >= 0.99:
                    t = (i + 1) / (n + 1)
            px = _compat_1081(self, left + t * width)
            py = _compat_1081(self, y_edge)
            try:
                p.side = side_value
            except Exception:
                pass
            p.x, p.y = px, py
            _compat_1077(p, old_px, old_py, px, py)

    _place_vertical_side(groups.get(PinSide.LEFT.value, []), PinSide.LEFT.value, left)
    _place_vertical_side(groups.get(PinSide.RIGHT.value, []), PinSide.RIGHT.value, right)
    _place_horizontal_side(groups.get(PinSide.TOP.value, []), PinSide.TOP.value, top)
    _place_horizontal_side(groups.get(PinSide.BOTTOM.value, []), PinSide.BOTTOM.value, bottom)

def _compat_1095(self, unit):
    # Public docking helper: no MENTOR_* early return.  It anchors to the visible
    # body outline when body graphics exist, otherwise to the model body rectangle.
    try:
        b = getattr(unit, 'body', None)
        if b is None:
            return
        st = {
            'x': _compat_1075(getattr(b, 'x', 0.0)),
            'y': _compat_1075(getattr(b, 'y', 0.0)),
            'w': _compat_1075(getattr(b, 'width', 1.0), 1.0),
            'h': _compat_1075(getattr(b, 'height', 1.0), 1.0),
            'pins': [(p, _compat_1075(getattr(p, 'x', 0.0)), _compat_1075(getattr(p, 'y', 0.0)), _compat_1075(getattr(p, 'length', 1.0), 1.0)) for p in (getattr(unit, 'pins', []) or [])],
        }
        # Temporarily expose unit for dialogs that do not use current_unit.
        old_current = getattr(self, 'current_unit', None)
        try:
            if old_current is None:
                self.current_unit = unit
            _compat_1097(self, st, b)
        finally:
            if old_current is None and hasattr(self, 'current_unit'):
                try: delattr(self, 'current_unit')
                except Exception: pass
    except Exception:
        pass

def _compat_1112(self, v):
    try:
        return _compat_1081(self, v)
    except Exception:
        try:
            step = float(getattr(self, 'edit_grid', 1.0) or 1.0)
            return round(float(v) / step) * step
        except Exception:
            return float(v)

def _compat_1114(self):
    try:
        return max(1e-9, _compat_1074(self))
    except Exception:
        return 1.0

def _compat_1113(self, body=None):
    u = _compat_1116(self)
    if u is None:
        return {}
    b = body or getattr(u, 'body', None)
    if b is None:
        return {}
    outline = _compat_1117(self, u, b)
    return {
        'x': _compat_1075(getattr(b, 'x', 0.0)),
        'y': _compat_1075(getattr(b, 'y', 0.0)),
        'w': max(_compat_1114(self), abs(_compat_1075(getattr(b, 'width', 1.0), 1.0))),
        'h': max(_compat_1114(self), abs(_compat_1075(getattr(b, 'height', 1.0), 1.0))),
        'outline': outline,
        'pins': [(p, _compat_1075(getattr(p, 'x', 0.0)), _compat_1075(getattr(p, 'y', 0.0)), _compat_1075(getattr(p, 'length', 1.0), 1.0), str(getattr(p, 'side', '') or '')) for p in getattr(u, 'pins', []) or []],
        'texts': [(t, _compat_1075(getattr(t, 'x', 0.0)), _compat_1075(getattr(t, 'y', 0.0))) for t in getattr(u, 'texts', []) or []],
        'attributes': [(t, _compat_1075(getattr(t, 'x', 0.0)), _compat_1075(getattr(t, 'y', 0.0))) for t in (getattr(getattr(u, 'body', None), 'attribute_texts', {}) or {}).values()],
        'graphics': [(gr, _compat_1075(getattr(gr, 'x', 0.0)), _compat_1075(getattr(gr, 'y', 0.0)), _compat_1075(getattr(gr, 'w', 0.0)), _compat_1075(getattr(gr, 'h', 0.0))) for gr in getattr(u, 'graphics', []) or []],
    }

def _compat_1111(pin, old_outline, stored_side=None):
    try:
        s = str(stored_side or getattr(pin, 'side', '') or '').lower()
        if s in (PinSide.LEFT.value, PinSide.RIGHT.value, PinSide.TOP.value, PinSide.BOTTOM.value):
            return s
    except Exception:
        pass
    try:
        l, t, r, b = old_outline
        px = _compat_1075(getattr(pin, 'x', 0.0)); py = _compat_1075(getattr(pin, 'y', 0.0))
        return min([(abs(px-l), PinSide.LEFT.value), (abs(px-r), PinSide.RIGHT.value), (abs(py-t), PinSide.TOP.value), (abs(py-b), PinSide.BOTTOM.value)], key=lambda z: z[0])[1]
    except Exception:
        return PinSide.LEFT.value

def _compat_1109(self, start_state, body):
    u = _compat_1116(self)
    if u is None:
        return
    pins = list(getattr(u, 'pins', []) or [])
    if not pins:
        return
    step = _compat_1114(self)
    old_outline = (start_state or {}).get('outline') or _compat_1108(body)
    old_l, old_t, old_r, old_b = old_outline
    old_w = max(step, abs(old_r - old_l)); old_h = max(step, abs(old_t - old_b))
    new_l, new_t, new_r, new_b = _compat_1117(self, u, body)
    new_l = _compat_1112(self, new_l); new_r = _compat_1112(self, new_r)
    new_t = _compat_1112(self, new_t); new_b = _compat_1112(self, new_b)
    new_w = max(step, abs(new_r - new_l)); new_h = max(step, abs(new_t - new_b))

    # PinModel/dataclass instances are not hashable in some builds.
    # Use the runtime identity as a stable key for this resize/rebuild pass.
    old_pos = {}
    old_side = {}
    for row in (start_state or {}).get('pins', []) or []:
        try:
            p = row[0]
            k = id(p)
            old_pos[k] = (_compat_1075(row[1]), _compat_1075(row[2]))
            old_side[k] = row[4] if len(row) > 4 else str(getattr(p, 'side', '') or '')
        except Exception:
            pass

    for p in pins:
        k = id(p)
        opx, opy = old_pos.get(k, (_compat_1075(getattr(p, 'x', 0.0)), _compat_1075(getattr(p, 'y', 0.0))))
        side = _compat_1111(p, old_outline, old_side.get(k))
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
        px = _compat_1112(self, px); py = _compat_1112(self, py)
        try: p.side = side
        except Exception: pass
        p.x, p.y = px, py
        # Pin length and labels/text offsets are preserved; only their owner pin
        # moves to the new outline location.
        try: _compat_1077(p, opx, opy, px, py)
        except Exception: pass

def _compat_1105(self, unit):
    if unit is None or getattr(unit, 'body', None) is None:
        return
    old_unit = None
    try:
        old_unit = getattr(self, 'current_unit', None)
        self.current_unit = unit
    except Exception:
        pass
    try:
        st = _compat_1113(self, unit.body)
        _compat_1109(self, st, unit.body)
    finally:
        try:
            if old_unit is not None:
                self.current_unit = old_unit
        except Exception:
            pass

def _compat_1125(pin, old_outline, stored_side=None):
    # Geometry wins over possibly stale imported/template side metadata.  This
    # prevents right-side imported pins from being redocked to the left side.
    try:
        l, t, r, b = old_outline
        px = _compat_1075(getattr(pin, 'x', 0.0)); py = _compat_1075(getattr(pin, 'y', 0.0))
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

def _compat_1126(self, body=None):
    u = _compat_1116(self)
    if u is None:
        return {}
    b = body or getattr(u, 'body', None)
    if b is None:
        return {}
    outline = _compat_1128(self, u, b)
    return {
        'x': _compat_1075(getattr(b, 'x', 0.0)),
        'y': _compat_1075(getattr(b, 'y', 0.0)),
        'w': max(_compat_1114(self), abs(_compat_1075(getattr(b, 'width', 1.0), 1.0))),
        'h': max(_compat_1114(self), abs(_compat_1075(getattr(b, 'height', 1.0), 1.0))),
        'outline': outline,
        'pins': [(p, _compat_1075(getattr(p, 'x', 0.0)), _compat_1075(getattr(p, 'y', 0.0)), _compat_1075(getattr(p, 'length', 1.0), 1.0), str(getattr(p, 'side', '') or '')) for p in getattr(u, 'pins', []) or []],
        'texts': [(t, _compat_1075(getattr(t, 'x', 0.0)), _compat_1075(getattr(t, 'y', 0.0))) for t in getattr(u, 'texts', []) or []],
        'attributes': [(t, _compat_1075(getattr(t, 'x', 0.0)), _compat_1075(getattr(t, 'y', 0.0))) for t in (getattr(getattr(u, 'body', None), 'attribute_texts', {}) or {}).values()],
        'graphics': [(gr, _compat_1075(getattr(gr, 'x', 0.0)), _compat_1075(getattr(gr, 'y', 0.0)), _compat_1075(getattr(gr, 'w', 0.0)), _compat_1075(getattr(gr, 'h', 0.0))) for gr in getattr(u, 'graphics', []) or []],
    }

def _compat_1123(self, start_state, body):
    u = _compat_1116(self)
    if u is None:
        return
    pins = list(getattr(u, 'pins', []) or [])
    if not pins:
        return
    step = _compat_1114(self)
    old_outline = (start_state or {}).get('outline') or _compat_1108(body)
    old_l, old_t, old_r, old_b = old_outline
    old_w = max(step, abs(old_r - old_l)); old_h = max(step, abs(old_t - old_b))
    new_l, new_t, new_r, new_b = _compat_1128(self, u, body)
    new_l = _compat_1112(self, new_l); new_r = _compat_1112(self, new_r)
    new_t = _compat_1112(self, new_t); new_b = _compat_1112(self, new_b)
    new_w = max(step, abs(new_r - new_l)); new_h = max(step, abs(new_t - new_b))
    old_pos = {}; old_side = {}
    for row in (start_state or {}).get('pins', []) or []:
        try:
            p = row[0]; k = id(p)
            old_pos[k] = (_compat_1075(row[1]), _compat_1075(row[2]))
            old_side[k] = row[4] if len(row) > 4 else str(getattr(p, 'side', '') or '')
        except Exception:
            pass
    for p in pins:
        k = id(p)
        opx, opy = old_pos.get(k, (_compat_1075(getattr(p, 'x', 0.0)), _compat_1075(getattr(p, 'y', 0.0))))
        # Use a lightweight temporary view with the old position for geometric
        # side detection; the pin object may already have moved during drag.
        try:
            old_px, old_py = getattr(p, 'x', None), getattr(p, 'y', None)
            p.x, p.y = opx, opy
            side = _compat_1125(p, old_outline, old_side.get(k))
            p.x, p.y = old_px, old_py
        except Exception:
            side = _compat_1125(p, old_outline, old_side.get(k))
        if side == PinSide.RIGHT.value:
            ratio = max(0.0, min(1.0, (old_t - opy) / old_h)); px, py = new_r, new_t - ratio * new_h
        elif side == PinSide.TOP.value:
            ratio = max(0.0, min(1.0, (opx - old_l) / old_w)); px, py = new_l + ratio * new_w, new_t
        elif side == PinSide.BOTTOM.value:
            ratio = max(0.0, min(1.0, (opx - old_l) / old_w)); px, py = new_l + ratio * new_w, new_b
        else:
            side = PinSide.LEFT.value
            ratio = max(0.0, min(1.0, (old_t - opy) / old_h)); px, py = new_l, new_t - ratio * new_h
        px = _compat_1112(self, px); py = _compat_1112(self, py)
        try: p.side = side
        except Exception: pass
        p.x, p.y = px, py
        try: _compat_1077(p, opx, opy, px, py)
        except Exception: pass

def _compat_1120(self, unit):
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
        st = _compat_1126(self, unit.body)
        _compat_1123(self, st, unit.body)
    finally:
        if can_restore:
            try: self.current_unit = old_unit
            except Exception: pass

def _compat_1143(win, v):
    try:
        return win.snap_grid_value(v)
    except Exception:
        try:
            step = win._edit_grid_step()
            return round(float(v) / step) * step
        except Exception:
            return round(float(v))

def _compat_1142(win, unit, x, y):
    b = getattr(unit, 'body', None)
    if b is None:
        return PinSide.LEFT.value
    l, t, r, bot = _compat_1135(win, unit, b)
    x = _compat_1138(x); y = _compat_1138(y)
    distances = {
        PinSide.LEFT.value: abs(x - l),
        PinSide.RIGHT.value: abs(x - r),
        PinSide.TOP.value: abs(y - t),
        PinSide.BOTTOM.value: abs(y - bot),
    }
    return min(distances.items(), key=lambda kv: kv[1])[0]

def _compat_1139(win, unit, pin, x=None, y=None, side=None, move_owned_text=True):
    b = getattr(unit, 'body', None)
    if b is None:
        return
    l, t, r, bot = _compat_1135(win, unit, b)
    side = side or getattr(pin, 'side', PinSide.LEFT.value) or PinSide.LEFT.value
    old_x, old_y = _compat_1138(getattr(pin, 'x', 0.0)), _compat_1138(getattr(pin, 'y', 0.0))
    cx = _compat_1138(x, old_x)
    cy = _compat_1138(y, old_y)
    if side == PinSide.RIGHT.value:
        nx, ny = r, _compat_1136(cy, bot, t)
    elif side == PinSide.TOP.value:
        nx, ny = _compat_1136(cx, l, r), t
    elif side == PinSide.BOTTOM.value:
        nx, ny = _compat_1136(cx, l, r), bot
    else:
        side = PinSide.LEFT.value
        nx, ny = l, _compat_1136(cy, bot, t)
    nx, ny = _compat_1143(win, nx), _compat_1143(win, ny)
    try:
        pin.side = side
        pin.x = nx
        pin.y = ny
    except Exception:
        return
    if move_owned_text:
        try:
            win._move_pin_owned_texts(pin, nx - old_x, ny - old_y)
        except Exception:
            try:
                _compat_1077(pin, old_x, old_y, nx, ny)
            except Exception:
                pass

def _compat_1134(self, side=None, x=None, y=None):
    self.push_undo_state()
    unit = self.current_unit
    if side is None:
        side = _compat_1142(self, unit, x if x is not None else 0.0, y if y is not None else 0.0)
    p = create_auto_pin(self.symbol, unit, side)
    p.name = self._unique_pin_name(getattr(p, 'name', 'PIN'))
    p.auto_dock = True
    _compat_1139(self, unit, p, x, y, side, move_owned_text=False)
    unit.pins.append(p)
    self.validate_pins(silent=True)
    self.select_model_after_rebuild(p)
    self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()

def _compat_1137(self, unit):
    if unit is None or getattr(unit, 'body', None) is None:
        return
    for p in list(getattr(unit, 'pins', []) or []):
        if not bool(getattr(p, 'auto_dock', True)):
            continue
        _compat_1139(self, unit, p, getattr(p, 'x', 0.0), getattr(p, 'y', 0.0), getattr(p, 'side', PinSide.LEFT.value), move_owned_text=True)

def _compat_1141(self, m, a, v):
    if _compat_1140 is not None:
        _compat_1140(self, m, a, v)
    else:
        setattr(m, a, v)
    if a == 'auto_dock' and bool(v):
        try:
            _compat_1139(self, self.current_unit, m, getattr(m, 'x', 0.0), getattr(m, 'y', 0.0), getattr(m, 'side', PinSide.LEFT.value), move_owned_text=True)
            self.schedule_scene_refresh(visual_only=True)
        except Exception:
            pass

def _compat_1179(self, v):
    try:
        return self._snap_to_edit_grid(float(v), 0.0)
    except Exception:
        try:
            step = max(1e-9, float(self._edit_grid_step()))
            return round(float(v) / step) * step
        except Exception:
            return float(v)

def _compat_1174(pin):
    try:
        return bool(getattr(pin, 'auto_dock', True))
    except Exception:
        return True

def _compat_1176(self, pin, px, py, plen, body):
    # Manual/loose pins stay where the user put them.
    if not _compat_1174(pin):
        pin.x = _compat_1171(self, px)
        pin.y = _compat_1171(self, py)
        pin.length = max(0.1, _compat_1171(self, plen))
        return
    side = str(getattr(pin, 'side', '') or '').lower()
    if side == PinSide.LEFT.value:
        pin.x = _compat_1171(self, float(body.x))
        pin.y = _compat_1171(self, py)
    elif side == PinSide.RIGHT.value:
        pin.x = _compat_1171(self, float(body.x) + float(body.width))
        pin.y = _compat_1171(self, py)
    elif side == PinSide.TOP.value:
        pin.x = _compat_1171(self, px)
        pin.y = _compat_1171(self, float(body.y))
    elif side == PinSide.BOTTOM.value:
        pin.x = _compat_1171(self, px)
        pin.y = _compat_1171(self, float(body.y) - float(body.height))
    else:
        pin.x = _compat_1171(self, px)
        pin.y = _compat_1171(self, py)
    # Pin length is not scaled by BODY resize. It remains the authored pin
    # length on the edit grid, just like Symbol 1 behaviour.
    pin.length = max(0.1, _compat_1171(self, plen))

def _compat_1195(self):
    try:
        return max(0.001, float(self._edit_grid_step()))
    except Exception:
        return 1.0

def _compat_1194(self, v):
    try:
        step = _compat_1195(self)
        return round(float(v) / step) * step
    except Exception:
        return float(v)

def _compat_1187(pin):
    try:
        return not bool(getattr(pin, 'auto_dock', True))
    except Exception:
        return False

def _compat_1186(self, pin, old_x, old_y, new_x, new_y):
    dx = float(new_x) - float(old_x)
    dy = float(new_y) - float(old_y)
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return
    try:
        self._move_pin_owned_texts(pin, dx, dy)
    except Exception:
        for ax_name, ay_name in (('label_x', 'label_y'), ('number_x', 'number_y')):
            try:
                if getattr(pin, ax_name, None) is not None:
                    setattr(pin, ax_name, _compat_1182(self, float(getattr(pin, ax_name)) + dx))
                if getattr(pin, ay_name, None) is not None:
                    setattr(pin, ay_name, _compat_1182(self, float(getattr(pin, ay_name)) + dy))
            except Exception:
                pass

def _compat_1192(self, pin, px, py, plen, body):
    old_px = float(getattr(pin, 'x', px) or px)
    old_py = float(getattr(pin, 'y', py) or py)
    if _compat_1187(pin):
        nx, ny = _compat_1182(self, px), _compat_1182(self, py)
    else:
        side = str(getattr(pin, 'side', '') or '').lower()
        if side == PinSide.LEFT.value:
            nx, ny = float(body.x), py
        elif side == PinSide.RIGHT.value:
            nx, ny = float(body.x) + float(body.width), py
        elif side == PinSide.TOP.value:
            nx, ny = px, float(body.y)
        elif side == PinSide.BOTTOM.value:
            nx, ny = px, float(body.y) - float(body.height)
        else:
            nx, ny = px, py
        nx, ny = _compat_1182(self, nx), _compat_1182(self, ny)
    pin.x = nx
    pin.y = ny
    pin.length = max(0.1, _compat_1182(self, plen))
    _compat_1186(self, pin, old_px, old_py, nx, ny)

def _compat_1184(self, entry, old_box, new_box):
    gr = entry[0]
    gx, gy, gw, gh = map(float, entry[1:5])
    ctrl_x = entry[5] if len(entry) > 5 else getattr(gr, 'ctrl_x', None)
    ctrl_y = entry[6] if len(entry) > 6 else getattr(gr, 'ctrl_y', None)
    curve_radius = entry[7] if len(entry) > 7 else getattr(gr, 'curve_radius', None)
    rotation = entry[8] if len(entry) > 8 else getattr(gr, 'rotation', 0.0)
    scale_x = entry[9] if len(entry) > 9 else getattr(gr, 'scale_x', 1.0)
    scale_y = entry[10] if len(entry) > 10 else getattr(gr, 'scale_y', 1.0)

    ax, ay = _compat_1185(self, gx, gy, old_box, new_box)
    ex, ey = _compat_1185(self, gx + gw, gy - gh, old_box, new_box)
    gr.x = _compat_1182(self, _compat_1194(self, ax))
    gr.y = _compat_1182(self, _compat_1194(self, ay))
    gr.w = _compat_1182(self, _compat_1194(self, ex - ax))
    gr.h = _compat_1182(self, _compat_1194(self, ay - ey))
    try:
        gr.rotation = rotation
        gr.scale_x = scale_x
        gr.scale_y = scale_y
    except Exception:
        pass

    try:
        if ctrl_x is not None and ctrl_y is not None:
            cx_abs = gx + float(ctrl_x)
            cy_abs = gy - float(ctrl_y)
            ncx, ncy = _compat_1185(self, cx_abs, cy_abs, old_box, new_box)
            gr.ctrl_x = _compat_1182(self, _compat_1194(self, ncx - gr.x))
            gr.ctrl_y = _compat_1182(self, _compat_1194(self, gr.y - ncy))
    except Exception:
        pass

    try:
        if curve_radius is not None:
            sx = abs(float(new_box[2]) / max(abs(float(old_box[2])), 1e-12))
            sy = abs(float(new_box[3]) / max(abs(float(old_box[3])), 1e-12))
            gr.curve_radius = _compat_1182(self, float(curve_radius or 0.0) * max(sx, sy))
    except Exception:
        pass

def _compat_0732(self):
    try:
        return max(0.001, float(getattr(self, 'edit_grid_step', 0) or self.edit_grid.value() or getattr(self, 'grid_inch', 1.0) or 1.0))
    except Exception:
        return 1.0

def _compat_0730(self, v):
    try:
        s = _compat_0732(self)
        return _compat_0720(self, round(float(v) / s) * s)
    except Exception:
        return _compat_0720(self, v)

def _compat_0731(graphics_snapshot):
    out = {}
    for rec in graphics_snapshot or []:
        try:
            gr = rec[0]
            out[gr] = rec
        except Exception:
            pass
    return out

def _compat_0721(gr, rec=None):
    """Return frozen graphic state as a uniform tuple.

    Tuple layout: gr,x,y,w,h,ctrl_x,ctrl_y,curve_radius,rotation,scale_x,scale_y
    Older snapshots may only contain gr,x,y,w,h.  Missing values are read once
    from the current model as a fallback, not during repeated scaling.
    """
    if rec is None:
        rec = (gr, float(getattr(gr, 'x', 0.0) or 0.0), float(getattr(gr, 'y', 0.0) or 0.0),
               float(getattr(gr, 'w', 0.0) or 0.0), float(getattr(gr, 'h', 0.0) or 0.0))
    x = float(rec[1]); y = float(rec[2]); w = float(rec[3]); h = float(rec[4])
    cx = rec[5] if len(rec) > 5 else getattr(gr, 'ctrl_x', None)
    cy = rec[6] if len(rec) > 6 else getattr(gr, 'ctrl_y', None)
    cr = rec[7] if len(rec) > 7 else getattr(gr, 'curve_radius', None)
    rot = rec[8] if len(rec) > 8 else getattr(gr, 'rotation', 0.0)
    scx = rec[9] if len(rec) > 9 else getattr(gr, 'scale_x', 1.0)
    scy = rec[10] if len(rec) > 10 else getattr(gr, 'scale_y', 1.0)
    return gr, x, y, w, h, cx, cy, cr, rot, scx, scy

def _compat_0724(self, pin, dx, dy):
    try:
        return self._move_pin_owned_texts(pin, dx, dy)
    except Exception:
        pass
    for ax, ay in (('label_x', 'label_y'), ('number_x', 'number_y')):
        try:
            if getattr(pin, ax, None) is not None and getattr(pin, ay, None) is not None:
                setattr(pin, ax, _compat_0720(self, float(getattr(pin, ax)) + dx))
                setattr(pin, ay, _compat_0720(self, float(getattr(pin, ay)) + dy))
        except Exception:
            pass
    for tm in (getattr(pin, 'attribute_texts', {}) or {}).values():
        try:
            tm.x = _compat_0720(self, float(tm.x) + dx)
            tm.y = _compat_0720(self, float(tm.y) + dy)
        except Exception:
            pass

def _compat_0726(self, start_state, old_bounds, new_bounds):
    for p, px, py, plen in start_state.get('pins', []) or []:
        try:
            old_px = float(getattr(p, 'x', px)); old_py = float(getattr(p, 'y', py))
            side = str(getattr(p, 'side', '') or '')
            auto_dock = bool(getattr(p, 'auto_dock', True))
            if auto_dock and side == PinSide.LEFT.value:
                nx, ny = new_bounds[0], _compat_0723(self, old_bounds, new_bounds, px, py)[1]
            elif auto_dock and side == PinSide.RIGHT.value:
                nx, ny = new_bounds[0] + new_bounds[2], _compat_0723(self, old_bounds, new_bounds, px, py)[1]
            elif auto_dock and side == PinSide.TOP.value:
                nx, ny = _compat_0723(self, old_bounds, new_bounds, px, py)[0], new_bounds[1]
            elif auto_dock and side == PinSide.BOTTOM.value:
                nx, ny = _compat_0723(self, old_bounds, new_bounds, px, py)[0], new_bounds[1] - new_bounds[3]
            else:
                nx, ny = _compat_0723(self, old_bounds, new_bounds, px, py)
            p.x = _compat_0730(self, nx)
            p.y = _compat_0730(self, ny)
            p.length = float(plen)
            _compat_0724(self, p, p.x - old_px, p.y - old_py)
        except Exception:
            pass

def _compat_0754(self):
    try:
        s = getattr(self, 'edit_grid_step', None)
        if callable(s):
            s = s()
        return max(0.001, float(s or 1.0))
    except Exception:
        return 1.0

def _compat_0752(self, v):
    try:
        step = _compat_0754(self)
        return _compat_0736(self, round(float(v) / step) * step)
    except Exception:
        return _compat_0736(self, v)

def _compat_0748(self, pin, old_x, old_y, new_x, new_y):
    dx = float(new_x) - float(old_x)
    dy = float(new_y) - float(old_y)
    try:
        self._move_pin_owned_texts(pin, dx, dy)
        return
    except Exception:
        pass
    for ax, ay in (('label_x', 'label_y'), ('number_x', 'number_y')):
        try:
            if getattr(pin, ax, None) is not None and getattr(pin, ay, None) is not None:
                setattr(pin, ax, _compat_0736(self, float(getattr(pin, ax)) + dx))
                setattr(pin, ay, _compat_0736(self, float(getattr(pin, ay)) + dy))
        except Exception:
            pass
    for tm in (getattr(pin, 'attribute_texts', {}) or {}).values():
        try:
            tm.x = _compat_0736(self, float(tm.x) + dx)
            tm.y = _compat_0736(self, float(tm.y) + dy)
        except Exception:
            pass

def _compat_0751(self, direction: int):
    self.set_tool(DrawTool.SELECT.value)
    if self._selected_body_active():
        step = _compat_0754(self)
        b = self.current_unit.body
        self.push_undo_state()
        return _compat_0747(self, new_w=float(b.width) + int(direction) * step, new_h=float(b.height) + int(direction) * step, refresh=True)
    # Leave individual pin/text/graphic behaviour untouched.
    try:
        return _compat_1167(self, direction)
    except Exception:
        try:
            return self.scale_selected(1.0 + (0.1 if direction > 0 else -0.1))
        except Exception:
            return None

def _compat_0770(self):
    try:
        s = getattr(self, 'edit_grid_step', None)
        if callable(s):
            s = s()
        return max(0.001, float(s or 1.0))
    except Exception:
        return 1.0

def _compat_0769(self, v):
    try:
        step = _compat_0770(self)
        return _compat_0757(self, round(float(v) / step) * step)
    except Exception:
        return _compat_0757(self, v)

def _compat_0763(self, pin, old_x, old_y, new_x, new_y):
    dx = float(new_x) - float(old_x)
    dy = float(new_y) - float(old_y)
    try:
        self._move_pin_owned_texts(pin, dx, dy)
        return
    except Exception:
        pass
    for ax, ay in (('label_x', 'label_y'), ('number_x', 'number_y')):
        try:
            if getattr(pin, ax, None) is not None and getattr(pin, ay, None) is not None:
                setattr(pin, ax, _compat_0757(self, float(getattr(pin, ax)) + dx))
                setattr(pin, ay, _compat_0757(self, float(getattr(pin, ay)) + dy))
        except Exception:
            pass
    for tm in (getattr(pin, 'attribute_texts', {}) or {}).values():
        try:
            tm.x = _compat_0757(self, float(tm.x) + dx)
            tm.y = _compat_0757(self, float(tm.y) + dy)
        except Exception:
            pass

def _compat_0768(self, body, value):
    self.push_undo_state()
    return _compat_0762(self, new_w=float(value), new_h=None, refresh=True)

def _compat_0767(self, body, value):
    self.push_undo_state()
    return _compat_0762(self, new_w=None, new_h=float(value), refresh=True)

def _compat_0766(self, direction: int):
    self.set_tool(DrawTool.SELECT.value)
    if self._selected_body_active():
        b = self.current_unit.body
        step = _compat_0770(self)
        self.push_undo_state()
        return _compat_0762(self, new_w=float(b.width) + int(direction) * step, new_h=float(b.height) + int(direction) * step, refresh=True)
    try:
        return _compat_0751(self, direction)
    except Exception:
        return None

def _compat_0753(unit, step=0.1):
    """Clean imported template coordinates to a stable sub-grid.

    The old template generator stores Mentor coordinates already converted to
    Symbol-Wizard grid units.  Do not rescale them again.  Only remove binary
    floating point noise and keep tenth-grid detail needed by Mentor arcs/circles.
    """
    try:
        b = unit.body
        for attr in ('x', 'y', 'width', 'height', 'rotation', 'scale_x', 'scale_y'):
            if hasattr(b, attr):
                setattr(b, attr, _compat_0738(getattr(b, attr), step if attr in ('x','y','width','height') else None))
        for tm in (getattr(b, 'attribute_texts', {}) or {}).values():
            for attr in ('x', 'y'):
                if hasattr(tm, attr):
                    setattr(tm, attr, _compat_0738(getattr(tm, attr), step))
    except Exception:
        pass
    for p in getattr(unit, 'pins', []) or []:
        for attr in ('x', 'y', 'length', 'mentor_x1', 'mentor_y1', 'mentor_x2', 'mentor_y2', 'label_x', 'label_y', 'number_x', 'number_y'):
            try:
                if hasattr(p, attr) and getattr(p, attr) is not None:
                    setattr(p, attr, _compat_0738(getattr(p, attr), step))
            except Exception:
                pass
        for tm in (getattr(p, 'attribute_texts', {}) or {}).values():
            try:
                tm.x = _compat_0738(tm.x, step); tm.y = _compat_0738(tm.y, step)
            except Exception:
                pass
    for t in getattr(unit, 'texts', []) or []:
        for attr in ('x', 'y'):
            try:
                setattr(t, attr, _compat_0738(getattr(t, attr), step))
            except Exception:
                pass
    for g in getattr(unit, 'graphics', []) or []:
        for attr in ('x', 'y', 'w', 'h', 'ctrl_x', 'ctrl_y', 'curve_radius'):
            try:
                if hasattr(g, attr) and getattr(g, attr) is not None:
                    setattr(g, attr, _compat_0738(getattr(g, attr), step))
            except Exception:
                pass
    return unit

def _compat_0740(unit):
    """Hide non-native generated labels that collide with passive body artwork.

    If a Mentor template has no stored L-record label anchor, the current PinItem
    fallback paints the generated name/function at the pin endpoint.  That is fine
    for rectangular IC bodies, but wrong for passive graphic symbols whose artwork
    itself occupies the pin centerline.  These labels were not native geometry, so
    hiding them restores the clean template raster while retaining pin numbers and
    editable model data.
    """
    try:
        if not _compat_0755(unit):
            return unit
        pins = list(getattr(unit, 'pins', []) or [])
        graphics = list(getattr(unit, 'graphics', []) or [])
        if not pins or len(pins) > 6:
            return unit
        if any(_compat_0739(p) for p in pins):
            return unit
        shapes = {str(getattr(g, 'shape', '') or '').lower() for g in graphics}
        pin_types = {str(getattr(p, 'pin_type', '') or '').upper() for p in pins}
        passive_like = bool(shapes.intersection({'arc', 'ellipse', 'circle'})) or pin_types.issubset({'ANALOG', 'PASSIVE', 'BIDI', 'BI', ''})
        if not passive_like:
            return unit
        for p in pins:
            try:
                p.visible_name = False
                p.visible_function = False
                p.visible_number = True
                # Mark for diagnostics only; exporter/model fields remain unchanged.
                if getattr(p, 'attributes', None) is None:
                    p.attributes = {}
                p.attributes.setdefault('WIZARD_LABELS_HIDDEN_BY_TEMPLATE_GRID_NORMALIZER', '1')
                if getattr(p, 'visible_attributes', None) is None:
                    p.visible_attributes = {}
                p.visible_attributes['WIZARD_LABELS_HIDDEN_BY_TEMPLATE_GRID_NORMALIZER'] = False
            except Exception:
                pass
    except Exception:
        pass
    return unit

def _compat_0771(self):
    try:
        combo = getattr(self, 'edit_grid_combo', None)
        if combo is None:
            return
        existing = {combo.itemText(i) for i in range(combo.count())}
        wanted = ['0.100"', '0.050"', '0.025"', '0.010"', '0.005"', '0.003"']
        for text in wanted:
            if text not in existing:
                combo.addItem(text)
                existing.add(text)
    except Exception:
        pass

def _compat_0782(self):
    """Return the dedicated pin-anchor raster in model units.

    The raster is intentionally independent from graphic/vector detail.  The
    default 0.1 model unit matches Mentor tenth-grid templates such as coils,
    while still being exact enough for drawing and editing pins.
    """
    candidates = []
    try:
        candidates.append(getattr(self.symbol, 'pin_grid_step', None))
    except Exception:
        pass
    try:
        candidates.append((getattr(self.current_unit.body, 'attributes', {}) or {}).get('PIN_GRID_STEP'))
    except Exception:
        pass
    for c in candidates:
        try:
            f = float(c)
            if f > 0:
                return f
        except Exception:
            pass
    return _compat_0053

def _compat_0799(self, value):
    step = _compat_0782(self)
    try:
        return _compat_0775(round(float(value) / step) * step)
    except Exception:
        return _compat_0775(value)

def _compat_0798(self, x, y):
    return _compat_0799(self, x), _compat_0799(self, y)

def _compat_0797(self, pin, move_owned_text=False):
    if pin is None:
        return pin
    ox, oy = _compat_0777(getattr(pin, 'x', 0.0)), _compat_0777(getattr(pin, 'y', 0.0))
    nx, ny = _compat_0798(self, ox, oy)
    try:
        pin.x = nx
        pin.y = ny
        pin.pin_grid_step = _compat_0782(self)
    except Exception:
        return pin
    dx, dy = nx - ox, ny - oy
    if move_owned_text and (abs(dx) > 1e-12 or abs(dy) > 1e-12):
        try:
            self._move_pin_owned_texts(pin, dx, dy)
        except Exception:
            pass
    # If the import already has absolute label/number anchors, keep them on the
    # same electrical raster as the pin.  Generated fallback labels without
    # anchors are unaffected.
    for ax, ay in (('label_x', 'label_y'), ('number_x', 'number_y')):
        try:
            if getattr(pin, ax, None) is not None and getattr(pin, ay, None) is not None:
                setattr(pin, ax, _compat_0799(self, getattr(pin, ax)))
                setattr(pin, ay, _compat_0799(self, getattr(pin, ay)))
        except Exception:
            pass
    return pin

def _compat_0800(self, unit=None, move_owned_text=False):
    try:
        unit = unit or self.current_unit
    except Exception:
        return unit
    for p in list(getattr(unit, 'pins', []) or []):
        _compat_0797(self, p, move_owned_text=move_owned_text)
    return unit

def _compat_0774(self, side=None, x=None, y=None):
    result = _compat_0785(self, side, x, y) if _compat_0785 is not None else None
    try:
        _compat_0800(self, self.current_unit, move_owned_text=False)
        self.update_current_unit_canvas_positions()
    except Exception:
        pass
    return result

def _compat_0776(self, unit):
    if _compat_0786 is not None:
        _compat_0786(self, unit)
    return _compat_0800(self, unit, move_owned_text=False)

def _compat_0796(self, m, a, v):
    result = _compat_0793(self, m, a, v) if _compat_0793 is not None else setattr(m, a, v)
    if a in ('x', 'y', 'side', 'auto_dock', 'length'):
        try:
            _compat_0797(self, m, move_owned_text=False)
            self.schedule_scene_refresh(visual_only=True)
        except Exception:
            pass
    return result

def _compat_0807(pin_type):
    return _compat_0054.get(str(pin_type or '').strip().upper(), (0, 0, 0))

def _compat_0803(pin, pin_type=None):
    if pin is None:
        return pin
    try:
        if pin_type is None:
            pin_type = getattr(pin, 'pin_type', '')
        color = tuple(_compat_0807(pin_type))
        pin.color = color
        if getattr(pin, 'number_font', None) is not None:
            pin.number_font.color = color
        if getattr(pin, 'label_font', None) is not None:
            pin.label_font.color = color
        if getattr(pin, 'attributes', None) is None:
            pin.attributes = {}
        pin.attributes['PINTYPE'] = str(pin_type or '')
    except Exception:
        pass
    return pin

def _compat_0813(self, m, a, v):
    result = _compat_0811(self, m, a, v) if _compat_0811 is not None else setattr(m, a, v)
    if a == 'pin_type':
        try:
            _compat_0803(m, v)
            self._selection_restore_ids = {id(m)}
            self.update_current_unit_canvas_positions()
            self.rebuild_pin_table()
            self.rebuild_tree()
            self.refresh_properties()
            self.schedule_scene_refresh(visual_only=True)
        except Exception:
            pass
    return result

def _compat_0805(self, table, r, c):
    pin = None
    is_type_col = False
    try:
        it = table.item(r, c) or table.item(r, 0)
        if it is not None:
            si, ui, pi, col = it.data(Qt.UserRole)
            is_type_col = (int(col) == 3 or int(c) == 3)
            sym = self.library.symbols[si]
            pin = sym.units[ui].pins[pi]
    except Exception:
        pin = None
    result = _compat_0809(self, table, r, c) if _compat_0809 is not None else None
    if is_type_col and pin is not None:
        try:
            _compat_0803(pin)
            self._selection_restore_ids = {id(pin)}
            self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table(); self.refresh_properties()
        except Exception:
            pass
    return result

def _compat_0814(self, pin_items, attr, value):
    if attr == 'pin_type':
        if hasattr(self, '_pin_models_from_objects'):
            pins = self._pin_models_from_objects(pin_items, require_all=False)
        else:
            pins = []
            for item in list(pin_items or []):
                try:
                    if item.data(0) == 'PIN':
                        model = getattr(item, 'model', None)
                        if model is not None:
                            pins.append(model)
                except RuntimeError:
                    continue
                except Exception:
                    continue
        if not pins:
            return
        self.push_undo_state()
        self._selection_restore_ids = {id(p) for p in pins}
        for p in pins:
            p.pin_type = value
            _compat_0803(p, value)
        self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table(); self.refresh_properties()
        return
    if hasattr(self, '_pin_models_from_objects'):
        pin_items = tuple(self._pin_models_from_objects(pin_items, require_all=False)) or pin_items
    return _compat_0812(self, pin_items, attr, value) if _compat_0812 is not None else None

def _compat_0802(self, side=None, x=None, y=None):
    result = _compat_0808(self, side, x, y) if _compat_0808 is not None else None
    try:
        # Color the newly created/selected pin semantically as well.
        for p in getattr(self.current_unit, 'pins', []) or []:
            if not getattr(p, '_compat_0804', False):
                _compat_0803(p)
                p._compat_0804 = True
        self.update_current_unit_canvas_positions()
    except Exception:
        pass
    return result

def _compat_0817(self):
    """Active edit grid in model units."""
    try:
        step = float(getattr(self, 'edit_grid_step'))
    except Exception:
        try:
            base = float(getattr(self.symbol, 'grid_inch', 0.100) or 0.100)
            edit = float(getattr(self, 'edit_grid_inch', base) or base)
            step = edit / base if base > 0 else 1.0
        except Exception:
            step = 1.0
    return max(_compat_0055, float(step))

def _compat_0838(self, value):
    step = _compat_0817(self)
    try:
        return _compat_0816(round(float(value) / step) * step)
    except Exception:
        return _compat_0816(value)

def _compat_0836(self, x, y):
    return _compat_0838(self, x), _compat_0838(self, y)

def _compat_0821(self):
    # Pin grid is now deliberately the visible/current Edit Grid.  This makes
    # pin insertion, drag, copy/paste and redocking predictable for drawing.
    return _compat_0817(self)

def _compat_0820(self):
    try:
        return max(1e-9, float(self.grid_px) * _compat_0821(self))
    except Exception:
        return 1.0

def _compat_0835(self, pin, move_owned_text=False):
    if pin is None:
        return pin
    try:
        ox, oy = float(getattr(pin, 'x', 0.0) or 0.0), float(getattr(pin, 'y', 0.0) or 0.0)
        nx, ny = _compat_0836(self, ox, oy)
        pin.x, pin.y = nx, ny
        pin.pin_grid_step = _compat_0821(self)
        dx, dy = nx - ox, ny - oy
        if move_owned_text and (abs(dx) > 1e-12 or abs(dy) > 1e-12):
            try:
                self._move_pin_owned_texts(pin, dx, dy)
            except Exception:
                pass
        for ax, ay in (('label_x', 'label_y'), ('number_x', 'number_y')):
            try:
                if getattr(pin, ax, None) is not None and getattr(pin, ay, None) is not None:
                    setattr(pin, ax, _compat_0838(self, getattr(pin, ax)))
                    setattr(pin, ay, _compat_0838(self, getattr(pin, ay)))
            except Exception:
                pass
    except Exception:
        pass
    return pin

def _compat_0837(self, unit=None, move_owned_text=False):
    try:
        unit = unit or self.current_unit
    except Exception:
        return unit
    for pin in list(getattr(unit, 'pins', []) or []):
        _compat_0835(self, pin, move_owned_text=move_owned_text)
    return unit

def _compat_0822(body):
    return {
        PinSide.LEFT.value: float(getattr(body, 'x', 0.0) or 0.0),
        PinSide.RIGHT.value: float(getattr(body, 'x', 0.0) or 0.0) + float(getattr(body, 'width', 0.0) or 0.0),
        PinSide.TOP.value: float(getattr(body, 'y', 0.0) or 0.0),
        PinSide.BOTTOM.value: float(getattr(body, 'y', 0.0) or 0.0) - float(getattr(body, 'height', 0.0) or 0.0),
    }

def _compat_0830(self, start_state, body):
    """Restore pin slots after BODY resize.

    The graphics/text vector scaling routine may update the whole group.  Pins
    are then corrected from the frozen start-state: auto-docked pins attach to
    the new BODY edge, but keep their original vertical/horizontal slot and
    length.  Loose pins are not moved by BODY resize.
    """
    try:
        pin_rows = list(start_state.get('pins', []) or [])
    except Exception:
        pin_rows = []
    if not pin_rows:
        return
    edges = _compat_0822(body)
    for row in pin_rows:
        try:
            pin, start_x, start_y, start_len = row[:4]
        except Exception:
            continue
        if pin is None:
            continue
        old_x = float(getattr(pin, 'x', 0.0) or 0.0)
        old_y = float(getattr(pin, 'y', 0.0) or 0.0)
        side = str(getattr(pin, 'side', PinSide.LEFT.value) or PinSide.LEFT.value)
        auto_dock = bool(getattr(pin, 'auto_dock', True))
        if not auto_dock:
            target_x, target_y = float(start_x), float(start_y)
        elif side == PinSide.RIGHT.value:
            target_x, target_y = edges[PinSide.RIGHT.value], float(start_y)
        elif side == PinSide.TOP.value:
            target_x, target_y = float(start_x), edges[PinSide.TOP.value]
        elif side == PinSide.BOTTOM.value:
            target_x, target_y = float(start_x), edges[PinSide.BOTTOM.value]
        else:
            pin.side = PinSide.LEFT.value
            target_x, target_y = edges[PinSide.LEFT.value], float(start_y)
        target_x, target_y = _compat_0836(self, target_x, target_y)
        pin.x, pin.y = target_x, target_y
        # BODY resize must not stretch pins or change their spacing.
        try:
            pin.length = float(start_len)
        except Exception:
            pass
        try:
            pin.pin_grid_step = _compat_0821(self)
        except Exception:
            pass
        dx, dy = target_x - old_x, target_y - old_y
        if abs(dx) > 1e-12 or abs(dy) > 1e-12:
            try:
                self._move_pin_owned_texts(pin, dx, dy)
            except Exception:
                pass

def _compat_0834(self, m, a, v):
    result = _compat_0828(self, m, a, v) if _compat_0828 is not None else setattr(m, a, v)
    if a in ('x', 'y', 'side', 'auto_dock', 'length'):
        try:
            _compat_0835(self, m, move_owned_text=False)
            self._selection_restore_ids = {id(m)}
            self.update_current_unit_canvas_positions()
            self.schedule_scene_refresh(visual_only=True)
        except Exception:
            pass
    return result

def _compat_0815(self, side=None, x=None, y=None):
    # Coordinates from the canvas are snapped to the same edit grid that is shown
    # to the user.  The underlying loose-docking helper still selects the BODY
    # edge based on the mouse position.
    if x is not None:
        x = _compat_0838(self, x)
    if y is not None:
        y = _compat_0838(self, y)
    result = _compat_0824(self, side, x, y) if _compat_0824 is not None else None
    try:
        for p in getattr(self.current_unit, 'pins', []) or []:
            _compat_0835(self, p, move_owned_text=False)
        self.update_current_unit_canvas_positions()
    except Exception:
        pass
    return result

def _compat_0883(self, value):
    try:
        return self.snap_grid_value(float(value))
    except Exception:
        try:
            step = float(getattr(self, 'edit_grid_step', 1.0) or 1.0)
            return round(float(value) / step) * step
        except Exception:
            return float(value)

def _compat_0848(self, tool, x, y, w=None, h=None):
    unit = _compat_0854(self)
    if unit is None:
        return
    try:
        shape = {DrawTool.LINE.value: 'line', DrawTool.RECT.value: 'rect', DrawTool.ELLIPSE.value: 'ellipse'}[tool]
    except Exception:
        return
    self.push_undo_state()
    x = _compat_0850(self, _compat_0883(self, x))
    y = _compat_0850(self, _compat_0883(self, y))
    if w is None or h is None:
        w = 2.0
        h = 0.0 if shape == 'line' else 2.0
    else:
        w = _compat_0850(self, _compat_0883(self, w))
        h = _compat_0850(self, _compat_0883(self, h))
        if shape != 'line':
            w = max(0.01, abs(float(w)))
            h = max(0.01, abs(float(h)))
    if shape == 'line' and abs(float(w)) < 1e-9 and abs(float(h)) < 1e-9:
        w, h = 2.0, 0.0
    model = GraphicModel(shape=shape, x=x, y=y, w=w, h=h, style=_compat_0861(self))
    model.locked_to_body = False
    model.graphic_role = 'user_graphic'
    model.mentor_raw = '__USER_GRAPHIC__'
    try:
        unit.graphics.append(model)
    except Exception:
        return
    try:
        self.select_model_after_rebuild(model)
    except Exception:
        try:
            self._selection_restore_ids = {id(model)}
        except Exception:
            pass
    try:
        self.rebuild_scene()
    except Exception:
        pass
    try:
        self.rebuild_tree()
    except Exception:
        pass
    try:
        self.rebuild_pin_table()
    except Exception:
        pass

def _compat_0871(self, g, dx, dy):
    try:
        g.x = _compat_0850(self, _compat_0883(self, float(g.x) + dx))
        g.y = _compat_0850(self, _compat_0883(self, float(g.y) + dy))
    except Exception:
        pass

def _compat_1223(action):
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

def _compat_1228(widget):
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

def _compat_1227(self):
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
                    if _compat_1223(action):
                        remove_toolbar = True
                        try: tb.removeAction(action)
                        except Exception: pass
                    try:
                        w = tb.widgetForAction(action)
                        if w is not None and _compat_1228(w):
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
                    if _compat_1223(action):
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
            if _compat_1223(action):
                try: self.removeAction(action)
                except Exception: pass
    except Exception:
        pass

def _compat_1224(self, *args, **kwargs):
    try:
        self.statusBar().showMessage('Grouping ist in dieser Version deaktiviert.', 3000)
    except Exception:
        pass
    return None
