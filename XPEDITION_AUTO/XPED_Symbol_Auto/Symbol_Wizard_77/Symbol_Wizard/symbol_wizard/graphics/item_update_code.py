"""Canonical item method update source.

This file contains the active item-behaviour layer that used to be appended
directly to ``graphics/items.py``.  It is executed only against temporary
shadow classes by ``item_updates.apply_item_updates``; the real item classes
receive exactly one final implementation per method.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Liebherr v56: move grouped user graphics as one object.
# ---------------------------------------------------------------------------
try:
    _compat_0459 = GraphicItem.__init__
    _compat_0460 = GraphicItem.update_model_pos

    def _compat_0457(self, model, window):
        _compat_0459(self, model, window)
        try:
            self._compat_0466 = (float(getattr(model, 'x', 0.0) or 0.0), float(getattr(model, 'y', 0.0) or 0.0))
        except Exception:
            self._compat_0466 = (0.0, 0.0)

    def _compat_0456(gr):
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

    def _compat_0458(gr):
        try:
            role = str(getattr(gr, 'graphic_role', '') or '').lower()
            return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body', 'template_body', 'imported_body')
        except Exception:
            return False

    def _compat_0461(self):
        if getattr(self.window, '_compat_0463', False):
            return _compat_0460(self)
        old = getattr(self, '_compat_0466', None)
        _compat_0460(self)
        try:
            new = (float(getattr(self.model, 'x', 0.0) or 0.0), float(getattr(self.model, 'y', 0.0) or 0.0))
        except Exception:
            return
        if old is None:
            self._compat_0466 = new
            return
        dx, dy = new[0] - old[0], new[1] - old[1]
        self._compat_0466 = new
        if abs(dx) < 1e-12 and abs(dy) < 1e-12:
            return
        gid = _compat_0456(self.model)
        if not gid or not _compat_0458(self.model):
            return
        try:
            self.window._compat_0463 = True
            unit = getattr(self.window, 'current_unit', None)
            graphics = list(getattr(unit, 'graphics', []) or [])
            for gr in graphics:
                if gr is self.model:
                    continue
                if _compat_0456(gr) == gid and _compat_0458(gr):
                    gr.x = float(getattr(gr, 'x', 0.0) or 0.0) + dx
                    gr.y = float(getattr(gr, 'y', 0.0) or 0.0) + dy
            gpx = float(getattr(self.window, 'grid_px', 1.0) or 1.0)
            try:
                scene_items = list(self.scene().items()) if self.scene() else []
            except Exception:
                scene_items = []
            for it in scene_items:
                try:
                    if it is self or getattr(it, 'data', lambda *_: None)(0) != 'GRAPHIC':
                        continue
                    gr = getattr(it, 'model', None)
                    if gr is not None and _compat_0456(gr) == gid and _compat_0458(gr):
                        it.setPos(float(getattr(gr, 'x', 0.0) or 0.0) * gpx, -float(getattr(gr, 'y', 0.0) or 0.0) * gpx)
                        it._compat_0466 = (float(getattr(gr, 'x', 0.0) or 0.0), float(getattr(gr, 'y', 0.0) or 0.0))
                except Exception:
                    pass
        finally:
            try:
                self.window._compat_0463 = False
            except Exception:
                pass

    GraphicItem.__init__ = _compat_0457
    GraphicItem.update_model_pos = _compat_0461
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v58: grouped graphics are highlighted as one logical object.
# ---------------------------------------------------------------------------
try:
    _compat_0506 = GraphicItem.paint

    def _compat_0502(model):
        try:
            gid = str(getattr(model, 'group_id', '') or '')
            if gid:
                return gid
            role = str(getattr(model, 'graphic_role', '') or '')
            if role.startswith('user_graphic_group:'):
                return role.split(':', 1)[1]
        except Exception:
            pass
        return ''

    def _compat_0503(item, gid):
        out = []
        try:
            unit = getattr(item.window, 'current_unit', None)
            for gr in list(getattr(unit, 'graphics', []) or []):
                if _compat_0502(gr) == gid:
                    out.append(gr)
        except Exception:
            pass
        return out

    def _compat_0504(item, gid):
        try:
            scene = item.scene()
            if scene is None:
                return True
            selected = []
            for it in scene.selectedItems():
                try:
                    if getattr(it, 'data', lambda *_: None)(0) == 'GRAPHIC' and _compat_0502(getattr(it, 'model', None)) == gid:
                        selected.append(it)
                except Exception:
                    pass
            return not selected or selected[0] is item
        except Exception:
            return True

    def _compat_0500(self, painter, gid):
        models = _compat_0503(self, gid)
        if not models:
            return
        g = self.window.grid_px
        boxes = []
        for gr in models:
            try:
                x = float(getattr(gr, 'x', 0.0) or 0.0)
                y = float(getattr(gr, 'y', 0.0) or 0.0)
                w = float(getattr(gr, 'w', 0.0) or 0.0)
                h = float(getattr(gr, 'h', 0.0) or 0.0)
                x2 = x + w; y2 = y - h
                boxes.append((min(x, x2), min(y, y2), max(x, x2), max(y, y2)))
            except Exception:
                pass
        if not boxes:
            return
        minx = min(b[0] for b in boxes); miny = min(b[1] for b in boxes)
        maxx = max(b[2] for b in boxes); maxy = max(b[3] for b in boxes)
        # model -> scene: scene_x=x*g, scene_y=-y*g
        pts_scene = [QPointF(minx*g, -maxy*g), QPointF(maxx*g, -maxy*g), QPointF(maxx*g, -miny*g), QPointF(minx*g, -miny*g)]
        pts_local = [self.mapFromScene(p) for p in pts_scene]
        painter.save()
        painter.setPen(QPen(QColor(80, 80, 80), 1, Qt.DashLine))
        painter.setBrush(QBrush(Qt.NoBrush))
        if len(pts_local) == 4:
            path = QPainterPath(pts_local[0])
            for p in pts_local[1:]:
                path.lineTo(p)
            path.closeSubpath()
            painter.drawPath(path)
            # One set of handles at group bbox corners.
            s = g * self.handle_size_factor
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            for p in pts_local:
                painter.drawRect(QRectF(p.x()-s/2, p.y()-s/2, s, s))
            cx = sum(p.x() for p in pts_local)/4.0; cy = sum(p.y() for p in pts_local)/4.0
            painter.drawEllipse(QRectF(cx-s/2, cy-s/2 - 2*s, s, s))
        painter.restore()

    def _compat_0505(self, painter, option, widget=None):
        gid = _compat_0502(getattr(self, 'model', None))
        if not gid:
            return _compat_0506(self, painter, option, widget)
        # Draw the graphic geometry without its individual selection handles.
        was_selected = False
        try:
            was_selected = self.isSelected()
            if was_selected:
                self.setSelected(False)
            _compat_0506(self, painter, option, widget)
        finally:
            try:
                if was_selected:
                    self.setSelected(True)
            except Exception:
                pass
        # Then draw exactly one group highlight for the selected group.
        if was_selected and _compat_0504(self, gid):
            _compat_0500(self, painter, gid)

    GraphicItem.paint = _compat_0505
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v59: paint grouped graphics as one highlighted logical object.
# Individual group members still draw their geometry, but never their own
# selection handles; exactly one group bounding box is drawn for the selection.
# ---------------------------------------------------------------------------
try:
    def _compat_0534(model):
        try:
            gid = str(getattr(model, 'group_id', '') or '')
            if gid:
                return gid
            role = str(getattr(model, 'graphic_role', '') or '')
            if role.startswith('user_graphic_group:'):
                return role.split(':', 1)[1]
        except Exception:
            pass
        return ''

    def _compat_0532(self, painter):
        g, m = self.window.grid_px, self.model
        painter.setPen(pen_for(m.style.stroke, m.style.line_width, m.style.line_style, g))
        painter.setBrush(QBrush(rgb(m.style.fill)) if m.style.fill else QBrush(Qt.NoBrush))
        if m.shape in ('line', 'arc'):
            ctrl_x = getattr(m, 'ctrl_x', None); ctrl_y = getattr(m, 'ctrl_y', None)
            if ctrl_x is not None and ctrl_y is not None:
                path = QPainterPath(QPointF(0, 0))
                path.quadTo(QPointF(float(ctrl_x) * g, -float(ctrl_y) * g), QPointF(m.w * g, -m.h * g))
                painter.drawPath(path)
            else:
                r = float(getattr(m, 'curve_radius', 0.0) or 0.0)
                if abs(r) > 1e-9:
                    path = QPainterPath(QPointF(0, 0))
                    path.quadTo(QPointF(m.w * g / 2, m.h * g / 2 - r * g), QPointF(m.w * g, m.h * g))
                    painter.drawPath(path)
                else:
                    painter.drawLine(QPointF(0, 0), QPointF(m.w * g, m.h * g))
        elif m.shape == 'rect':
            painter.drawRect(QRectF(0, 0, m.w * g, m.h * g))
        elif m.shape in ('ellipse', 'circle'):
            painter.drawEllipse(QRectF(0, 0, m.w * g, m.h * g))

    def _compat_0535(self, gid):
        boxes = []
        try:
            unit = getattr(self.window, 'current_unit', None)
            for gr in list(getattr(unit, 'graphics', []) or []):
                if _compat_0534(gr) != gid:
                    continue
                x = float(getattr(gr, 'x', 0.0) or 0.0); y = float(getattr(gr, 'y', 0.0) or 0.0)
                w = float(getattr(gr, 'w', 0.0) or 0.0); h = float(getattr(gr, 'h', 0.0) or 0.0)
                x2 = x + w; y2 = y - h
                boxes.append((min(x, x2), min(y, y2), max(x, x2), max(y, y2), gr))
        except Exception:
            pass
        return boxes

    def _compat_0536(self, gid):
        try:
            # Prefer the first selected item of the group in scene order. This
            # avoids drawing the group bbox multiple times when all members are
            # selected as one logical object.
            selected = []
            for it in self.scene().selectedItems():
                try:
                    if getattr(it, 'data', lambda *_: None)(0) == 'GRAPHIC' and _compat_0534(getattr(it, 'model', None)) == gid:
                        selected.append(it)
                except Exception:
                    pass
            return bool(selected) and selected[0] is self
        except Exception:
            return True

    def _compat_0533(self, painter, gid):
        boxes = _compat_0535(self, gid)
        if not boxes:
            return
        minx = min(b[0] for b in boxes); miny = min(b[1] for b in boxes)
        maxx = max(b[2] for b in boxes); maxy = max(b[3] for b in boxes)
        g = self.window.grid_px
        # model -> scene: scene_x = x*g, scene_y = -y*g
        corners_scene = [QPointF(minx*g, -maxy*g), QPointF(maxx*g, -maxy*g), QPointF(maxx*g, -miny*g), QPointF(minx*g, -miny*g)]
        corners = [self.mapFromScene(p) for p in corners_scene]
        painter.save()
        painter.setPen(QPen(QColor(80, 80, 80), 1, Qt.DashLine))
        painter.setBrush(QBrush(Qt.NoBrush))
        path = QPainterPath(corners[0])
        for p in corners[1:]:
            path.lineTo(p)
        path.closeSubpath()
        painter.drawPath(path)
        s = g * self.handle_size_factor
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        for p in corners:
            painter.drawRect(QRectF(p.x()-s/2, p.y()-s/2, s, s))
        cx = sum(p.x() for p in corners) / 4.0
        cy = sum(p.y() for p in corners) / 4.0
        painter.drawEllipse(QRectF(cx - s/2, cy - 2.2*s, s, s))
        painter.restore()

    def _compat_0528(self, painter, option, widget=None):
        gid = _compat_0534(getattr(self, 'model', None))
        if not gid:
            return _compat_0506(self, painter, option, widget) if '_compat_0506' in globals() else None
        _compat_0532(self, painter)
        try:
            group_selected = any(
                getattr(it, 'data', lambda *_: None)(0) == 'GRAPHIC' and _compat_0534(getattr(it, 'model', None)) == gid and it.isSelected()
                for it in self.scene().items()
            )
        except Exception:
            group_selected = self.isSelected()
        if group_selected and _compat_0536(self, gid):
            _compat_0533(self, painter, gid)

    GraphicItem.paint = _compat_0528
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v68: natural single-graphic transforms.
# - Rotate / Flip use one stable local transform point: selected object's lower-left.
# - Canvas resize handles work in scene direction after rotation/flip: the opposite
#   handle becomes the temporary resize origin and the dragged handle follows the
#   mouse direction on the edit grid.
# - Geometry dimensions are snapped to the edit grid with a minimum of one edit grid.
# ---------------------------------------------------------------------------
try:
    _compat_0611 = GraphicItem.mousePressEvent
    _compat_0610 = GraphicItem.mouseMoveEvent
except Exception:
    _compat_0611 = None
    _compat_0610 = None


def _compat_0602(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)


def _compat_0601(win):
    try:
        return max(1e-9, float(getattr(win, 'edit_grid_px', 0.0) or 0.0))
    except Exception:
        return 1.0


def _compat_0618(win, value):
    step = _compat_0601(win)
    try:
        return snap(float(value), step)
    except Exception:
        return round(float(value) / step) * step


def _compat_0619(win, p):
    return QPointF(_compat_0618(win, p.x()), _compat_0618(win, p.y()))


def _compat_0608(item):
    # Use raw model geometry, not boundingRect(), because boundingRect contains
    # selection/handle margins.  The transform origin must be geometric lower-left.
    g = item.window.grid_px
    w = _compat_0602(getattr(item.model, 'w', 0.0), 0.0) * g
    h = _compat_0602(getattr(item.model, 'h', 0.0), 0.0) * g
    return QRectF(0.0, 0.0, w, h).normalized()


def _compat_0603(self):
    def f(name, default):
        try:
            return float(getattr(self.model, name, default) or default)
        except Exception:
            return default
    sx, sy, rot = f('scale_x', 1.0), f('scale_y', 1.0), f('rotation', 0.0)
    self.model.scale_x, self.model.scale_y, self.model.rotation = sx, sy, rot
    try:
        r = _compat_0608(self)
        # Stable object origin for rotate/flip: lower-left of the actual object.
        self.setTransformOriginPoint(r.bottomLeft())
    except Exception:
        pass
    self.setTransform(QTransform().scale(sx, sy))
    self.setRotation(rot)


def _compat_0607(item):
    r = _compat_0608(item)
    return {
        'tl': QPointF(r.left(), r.top()),
        'tr': QPointF(r.right(), r.top()),
        'bl': QPointF(r.left(), r.bottom()),
        'br': QPointF(r.right(), r.bottom()),
        'l': QPointF(r.left(), r.center().y()),
        'r': QPointF(r.right(), r.center().y()),
        't': QPointF(r.center().x(), r.top()),
        'b': QPointF(r.center().x(), r.bottom()),
    }


def _compat_0609(handle):
    return {
        'tl': 'br', 'tr': 'bl', 'bl': 'tr', 'br': 'tl',
        'l': 'r', 'r': 'l', 't': 'b', 'b': 't',
    }.get(handle, '')


def _compat_0605(self, event):
    if event.button() == Qt.LeftButton and self.isSelected():
        try:
            # Rotation remains original behaviour, but with lower-left transform origin.
            if _rotation_handle(self._rect(), self.window.grid_px * self.rotate_handle_factor).contains(event.pos()):
                return _compat_0611(self, event)
            h = _hit_handle(self._handles(), event.pos())
            if h and str(getattr(self.model, 'shape', '') or '') not in ('line', 'arc'):
                pts = _compat_0607(self)
                anchor_name = _compat_0609(h)
                anchor_local = pts.get(anchor_name, QPointF(0, 0))
                self._compat_0617 = h
                self._compat_0614 = anchor_name
                self._compat_0613 = QPointF(anchor_local)
                self._compat_0615 = self.mapToScene(anchor_local)
                self._compat_0616 = {
                    'x': _compat_0602(getattr(self.model, 'x', 0.0), 0.0),
                    'y': _compat_0602(getattr(self.model, 'y', 0.0), 0.0),
                    'w': _compat_0602(getattr(self.model, 'w', 0.0), 0.0),
                    'h': _compat_0602(getattr(self.model, 'h', 0.0), 0.0),
                    'sx': _compat_0602(getattr(self.model, 'scale_x', 1.0), 1.0),
                    'sy': _compat_0602(getattr(self.model, 'scale_y', 1.0), 1.0),
                    'rot': _compat_0602(getattr(self.model, 'rotation', 0.0), 0.0),
                }
                event.accept(); return
        except Exception:
            pass
    return _compat_0611(self, event)


def _compat_0604(self, event):
    if getattr(self, '_compat_0617', None) and getattr(self, '_compat_0616', None) is not None:
        try:
            win = self.window
            g = float(win.grid_px)
            min_px = max(_compat_0601(win), 1e-9)
            hname = str(self._compat_0617)
            anchor_local = QPointF(self._compat_0613)
            anchor_scene = QPointF(self._compat_0615)
            mouse_scene = _compat_0619(win, event.scenePos())
            mouse_local = self.mapFromScene(mouse_scene)

            # Build the new local rectangle from a fixed opposite handle/edge and
            # the dragged mouse point.  Because mouse_local is obtained through the
            # current item transform, dragging in scene direction remains natural
            # even after rotation or axis mirroring.
            l = 0.0; t = 0.0
            r = _compat_0602(getattr(self.model, 'w', 0.0), 0.0) * g
            b = _compat_0602(getattr(self.model, 'h', 0.0), 0.0) * g

            # Use the anchor coordinate for the fixed side(s).
            if hname in ('l', 'tl', 'bl'):
                r = anchor_local.x(); l = mouse_local.x()
            elif hname in ('r', 'tr', 'br'):
                l = anchor_local.x(); r = mouse_local.x()
            else:
                l = 0.0; r = _compat_0602(getattr(self.model, 'w', 0.0), 0.0) * g

            if hname in ('t', 'tl', 'tr'):
                b = anchor_local.y(); t = mouse_local.y()
            elif hname in ('b', 'bl', 'br'):
                t = anchor_local.y(); b = mouse_local.y()
            else:
                t = 0.0; b = _compat_0602(getattr(self.model, 'h', 0.0), 0.0) * g

            # Snap size to edit grid and enforce one edit-grid minimum.  Edge
            # handles resize exactly one axis; corner handles resize both axes.
            left = min(l, r); right = max(l, r)
            top = min(t, b); bottom = max(t, b)
            new_w = max(min_px, _compat_0618(win, right - left))
            new_h = max(min_px, _compat_0618(win, bottom - top))

            # Preserve the side under the fixed anchor after size snapping.
            if hname in ('l', 'tl', 'bl'):
                right = anchor_local.x(); left = right - new_w
            elif hname in ('r', 'tr', 'br'):
                left = anchor_local.x(); right = left + new_w
            else:
                # Center untouched dimension around the old local rect.
                old = _compat_0608(self)
                left = old.left(); right = old.right()
                new_w = max(min_px, abs(right - left))

            if hname in ('t', 'tl', 'tr'):
                bottom = anchor_local.y(); top = bottom - new_h
            elif hname in ('b', 'bl', 'br'):
                top = anchor_local.y(); bottom = top + new_h
            else:
                old = _compat_0608(self)
                top = old.top(); bottom = old.bottom()
                new_h = max(min_px, abs(bottom - top))

            # Shift local origin to the new upper-left, then compensate scene pos
            # so the temporary resize origin stays exactly where it was.
            new_origin_scene = self.mapToScene(QPointF(left, top))
            self.prepareGeometryChange()
            self.model.w = new_w / g
            self.model.h = new_h / g
            self.model.x = new_origin_scene.x() / g
            self.model.y = -new_origin_scene.y() / g
            self.setPos(new_origin_scene)
            self.apply_transform_from_model()

            new_anchor_local = QPointF(anchor_local.x() - left, anchor_local.y() - top)
            new_anchor_scene = self.mapToScene(new_anchor_local)
            delta = anchor_scene - new_anchor_scene
            final_pos = self.pos() + delta
            # Final item origin is snapped as well; this keeps model geometry on
            # the edit grid while the dragged size is already edit-grid aligned.
            final_pos = _compat_0619(win, final_pos)
            self.setPos(final_pos)
            self.model.x = final_pos.x() / g
            self.model.y = -final_pos.y() / g

            try:
                win.notify_canvas_model_changed()
            except Exception:
                win.live_refresh()
            self.update(); event.accept(); return
        except Exception:
            # Never crash during resize; fall back to previous implementation.
            try:
                self._compat_0617 = None
            except Exception:
                pass
    return _compat_0610(self, event)


def _compat_0606(self, event):
    try:
        self._compat_0617 = None
        self._compat_0616 = None
        self._compat_0613 = None
        self._compat_0615 = None
    except Exception:
        pass
    return _compat_0612(self, event)

try:
    _compat_0612 = GraphicItem.mouseReleaseEvent
    GraphicItem.apply_transform_from_model = _compat_0603
    GraphicItem.mousePressEvent = _compat_0605
    GraphicItem.mouseMoveEvent = _compat_0604
    GraphicItem.mouseReleaseEvent = _compat_0606
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v69: smoother / natural single-graphic canvas scaling.
# v68 already fixed rotate/flip pivot. This patch replaces only handle-resize:
# - all resize maths are evaluated in the frozen local coordinate system from
#   mouse press, not in the continuously changing item transform -> no jitter.
# - the dragged size is snapped to the edit grid; the fixed opposite handle is
#   preserved exactly (no secondary snapping that fights the mouse).
# - resize cursors are chosen from the transformed handle direction, so after
#   rotate/flip the cursor/arrow direction remains visually natural.
# ---------------------------------------------------------------------------
try:
    _compat_0627 = GraphicItem.mousePressEvent
    _compat_0626 = GraphicItem.mouseMoveEvent
    _compat_0628 = GraphicItem.mouseReleaseEvent
    _compat_0625 = GraphicItem.hoverMoveEvent
except Exception:
    _compat_0627 = None
    _compat_0626 = None
    _compat_0628 = None
    _compat_0625 = None


def _compat_0636(win, value):
    step = _compat_0601(win)
    try:
        v = abs(float(value))
    except Exception:
        v = 0.0
    return max(step, _compat_0618(win, v))


def _compat_0620(item, h):
    """Return a cursor that matches the handle's visual scene direction."""
    if not h:
        return Qt.ArrowCursor
    if h == 'rot':
        return Qt.CrossCursor
    try:
        r = _compat_0608(item)
        c = r.center()
        pts = _compat_0607(item)
        p = pts.get(h, c)
        # For corner handles use the center->corner diagonal; for edge handles
        # use the center->edge normal. Map through the full item transform so
        # rotation and negative scale/flips are represented visually.
        sc = item.mapToScene(c)
        sp = item.mapToScene(p)
        dx = sp.x() - sc.x(); dy = sp.y() - sc.y()
        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return _cursor_for_handle(h)
        import math
        ang = (math.degrees(math.atan2(dy, dx)) + 180.0) % 180.0
        # 0/180 horizontal, 90 vertical, 45 and 135 diagonals.
        if ang < 22.5 or ang >= 157.5:
            return Qt.SizeHorCursor
        if 67.5 <= ang < 112.5:
            return Qt.SizeVerCursor
        if 22.5 <= ang < 67.5:
            return Qt.SizeFDiagCursor
        return Qt.SizeBDiagCursor
    except Exception:
        return _cursor_for_handle(h)


def _compat_0621(self, event):
    try:
        if self.isSelected():
            h = 'rot' if _rotation_handle(self._rect(), self.window.grid_px * self.rotate_handle_factor).contains(event.pos()) else _hit_handle(self._handles(), event.pos())
            self.setCursor(QCursor(_compat_0620(self, h)) if h else QCursor(Qt.ArrowCursor))
            return QGraphicsItem.hoverMoveEvent(self, event)
    except Exception:
        pass
    return _compat_0625(self, event)


def _compat_0623(self, event):
    if event.button() == Qt.LeftButton and self.isSelected():
        try:
            if _rotation_handle(self._rect(), self.window.grid_px * self.rotate_handle_factor).contains(event.pos()):
                return _compat_0627(self, event)
            h = _hit_handle(self._handles(), event.pos())
            if h and str(getattr(self.model, 'shape', '') or '') not in ('line', 'arc'):
                pts = _compat_0607(self)
                anchor_name = _compat_0609(h)
                anchor_local = QPointF(pts.get(anchor_name, QPointF(0, 0)))
                st = self.sceneTransform()
                inv, ok = st.inverted()
                if not ok:
                    return _compat_0627(self, event)
                self._compat_0635 = h
                self._compat_0630 = anchor_name
                self._compat_0629 = QPointF(anchor_local)
                self._compat_0631 = self.mapToScene(anchor_local)
                self._compat_0632 = inv
                self._compat_0634 = st
                self._compat_0633 = {
                    'x': _compat_0602(getattr(self.model, 'x', 0.0), 0.0),
                    'y': _compat_0602(getattr(self.model, 'y', 0.0), 0.0),
                    'w': _compat_0602(getattr(self.model, 'w', 0.0), 0.0),
                    'h': _compat_0602(getattr(self.model, 'h', 0.0), 0.0),
                    'sx': _compat_0602(getattr(self.model, 'scale_x', 1.0), 1.0),
                    'sy': _compat_0602(getattr(self.model, 'scale_y', 1.0), 1.0),
                    'rot': _compat_0602(getattr(self.model, 'rotation', 0.0), 0.0),
                    'pos': QPointF(self.pos()),
                }
                event.accept(); return
        except Exception:
            pass
    return _compat_0627(self, event)


def _compat_0622(self, event):
    if getattr(self, '_compat_0635', None) and getattr(self, '_compat_0633', None) is not None:
        try:
            win = self.window
            g = float(win.grid_px)
            hname = str(self._compat_0635)
            start = dict(self._compat_0633)
            anchor_local = QPointF(self._compat_0629)
            anchor_scene = QPointF(self._compat_0631)
            inv = self._compat_0632

            # Mouse in the unchanged local coordinate system from press time.
            # Do not scene-snap the mouse: only snap the resulting size.  This
            # avoids the two competing quantizers that caused the visible shake.
            mouse_local = inv.map(event.scenePos())
            old_w = max(1e-9, _compat_0602(start.get('w'), 0.0) * g)
            old_h = max(1e-9, _compat_0602(start.get('h'), 0.0) * g)
            old_left, old_top, old_right, old_bottom = 0.0, 0.0, old_w, old_h

            # Start with the old rect and only replace the axes controlled by
            # the active handle.
            left, right = old_left, old_right
            top, bottom = old_top, old_bottom
            if hname in ('l', 'tl', 'bl'):
                right = anchor_local.x()
                new_w = _compat_0636(win, right - mouse_local.x())
                left = right - new_w
            elif hname in ('r', 'tr', 'br'):
                left = anchor_local.x()
                new_w = _compat_0636(win, mouse_local.x() - left)
                right = left + new_w
            else:
                new_w = old_w

            if hname in ('t', 'tl', 'tr'):
                bottom = anchor_local.y()
                new_h = _compat_0636(win, bottom - mouse_local.y())
                top = bottom - new_h
            elif hname in ('b', 'bl', 'br'):
                top = anchor_local.y()
                new_h = _compat_0636(win, mouse_local.y() - top)
                bottom = top + new_h
            else:
                new_h = old_h

            # Restore the start transform before applying the newly computed
            # rect. This makes every mouse move absolute from the press state,
            # not cumulative from the previous frame.
            self.prepareGeometryChange()
            self.model.x = start['x']; self.model.y = start['y']
            self.model.w = max(_compat_0601(win), float(new_w)) / g
            self.model.h = max(_compat_0601(win), float(new_h)) / g
            self.model.scale_x = start['sx']; self.model.scale_y = start['sy']; self.model.rotation = start['rot']
            self.setPos(start['pos'])
            self.apply_transform_from_model()

            # Move the item origin to the transformed new upper-left and then
            # compensate so the fixed opposite handle remains exactly in place.
            start_transform = self._compat_0634
            new_origin_scene = start_transform.map(QPointF(left, top))
            self.setPos(new_origin_scene)
            self.model.x = new_origin_scene.x() / g
            self.model.y = -new_origin_scene.y() / g
            self.apply_transform_from_model()

            new_anchor_local = QPointF(anchor_local.x() - left, anchor_local.y() - top)
            new_anchor_scene = self.mapToScene(new_anchor_local)
            delta = anchor_scene - new_anchor_scene
            final_pos = self.pos() + delta
            self.setPos(final_pos)
            self.model.x = final_pos.x() / g
            self.model.y = -final_pos.y() / g

            try:
                win.notify_canvas_model_changed()
            except Exception:
                try: win.live_refresh()
                except Exception: pass
            self.update(); event.accept(); return
        except Exception:
            try:
                self._compat_0635 = None
            except Exception:
                pass
    return _compat_0626(self, event)


def _compat_0624(self, event):
    try:
        self._compat_0635 = None
        self._compat_0633 = None
        self._compat_0629 = None
        self._compat_0631 = None
        self._compat_0632 = None
        self._compat_0634 = None
    except Exception:
        pass
    return _compat_0628(self, event)

try:
    GraphicItem.hoverMoveEvent = _compat_0621
    GraphicItem.mousePressEvent = _compat_0623
    GraphicItem.mouseMoveEvent = _compat_0622
    GraphicItem.mouseReleaseEvent = _compat_0624
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v70: natural line endpoint scaling.
# v69 fixed rectangle/ellipse handle scaling. Lines need a separate path because
# their handles are endpoints, not bbox corners.  Endpoint resize is now done in
# the frozen local coordinate system from mouse press, the opposite endpoint is
# held exactly in scene coordinates, and the dragged endpoint is snapped to the
# edit grid. This keeps line scaling natural after rotate/flip/negative scales.
# ---------------------------------------------------------------------------
try:
    _compat_0662 = GraphicItem.mousePressEvent
    _compat_0661 = GraphicItem.mouseMoveEvent
    _compat_0663 = GraphicItem.mouseReleaseEvent
    _compat_0660 = GraphicItem.hoverMoveEvent
except Exception:
    _compat_0662 = None
    _compat_0661 = None
    _compat_0663 = None
    _compat_0660 = None


def _compat_0647(item):
    g = float(item.window.grid_px)
    return {
        'start': QPointF(0.0, 0.0),
        'end': QPointF(_compat_0602(getattr(item.model, 'w', 0.0), 0.0) * g,
                       _compat_0602(getattr(item.model, 'h', 0.0), 0.0) * g),
    }


def _compat_0651(win, vx, vy):
    """Keep line length at least one edit-grid step while preserving direction."""
    import math
    min_len = max(_compat_0601(win), 1e-9)
    length = math.hypot(float(vx), float(vy))
    if length >= min_len:
        return float(vx), float(vy)
    if length < 1e-9:
        return min_len, 0.0
    f = min_len / length
    return float(vx) * f, float(vy) * f


def _compat_0653(self, event):
    if event.button() == Qt.LeftButton and self.isSelected():
        try:
            if str(getattr(self.model, 'shape', '') or '') == 'line':
                # Rotation handle stays on the existing v68/v69 path.
                if _rotation_handle(self._rect(), self.window.grid_px * self.rotate_handle_factor).contains(event.pos()):
                    return _compat_0662(self, event)
                h = _hit_handle(self._handles(), event.pos())
                if h in ('start', 'end'):
                    st = self.sceneTransform()
                    inv, ok = st.inverted()
                    if not ok:
                        return _compat_0662(self, event)
                    pts = _compat_0647(self)
                    fixed = 'end' if h == 'start' else 'start'
                    self._compat_0655 = h
                    self._compat_0648 = fixed
                    self._compat_0659 = st
                    self._compat_0656 = inv
                    self._compat_0649 = self.mapToScene(pts[fixed])
                    self._compat_0658 = self.mapToScene(pts['start'])
                    self._compat_0646 = self.mapToScene(pts['end'])
                    self._compat_0657 = {
                        'x': _compat_0602(getattr(self.model, 'x', 0.0), 0.0),
                        'y': _compat_0602(getattr(self.model, 'y', 0.0), 0.0),
                        'w': _compat_0602(getattr(self.model, 'w', 0.0), 0.0),
                        'h': _compat_0602(getattr(self.model, 'h', 0.0), 0.0),
                        'sx': _compat_0602(getattr(self.model, 'scale_x', 1.0), 1.0),
                        'sy': _compat_0602(getattr(self.model, 'scale_y', 1.0), 1.0),
                        'rot': _compat_0602(getattr(self.model, 'rotation', 0.0), 0.0),
                        'pos': QPointF(self.pos()),
                    }
                    event.accept(); return
        except Exception:
            pass
    return _compat_0662(self, event)


def _compat_0652(self, event):
    if getattr(self, '_compat_0655', None) and getattr(self, '_compat_0657', None) is not None:
        try:
            win = self.window
            g = float(win.grid_px)
            hname = str(self._compat_0655)
            start = dict(self._compat_0657)
            inv = self._compat_0656
            start_transform = self._compat_0659
            old_end_local = QPointF(start['w'] * g, start['h'] * g)

            # The mouse target is snapped in scene coordinates so line endpoints
            # land exactly on the visible edit grid.
            mouse_scene = _compat_0619(win, event.scenePos())
            mouse_local = inv.map(mouse_scene)

            self.prepareGeometryChange()
            self.model.scale_x = start['sx']; self.model.scale_y = start['sy']; self.model.rotation = start['rot']
            self.model.x = start['x']; self.model.y = start['y']
            self.setPos(QPointF(start['pos']))
            self.apply_transform_from_model()

            if hname == 'end':
                # Keep local start as object origin, change only endpoint vector.
                vx, vy = _compat_0651(win, mouse_local.x(), mouse_local.y())
                self.model.w = vx / g
                self.model.h = vy / g
                self.setPos(QPointF(start['pos']))
                self.model.x = start['x']; self.model.y = start['y']
                self.apply_transform_from_model()
                # Correct any transform-origin side effect so the fixed start
                # endpoint is exactly where it was at mouse press.
                fixed_now = self.mapToScene(QPointF(0.0, 0.0))
                delta = self._compat_0649 - fixed_now
            else:
                # Move object origin to the new start point in the frozen local
                # frame. Endpoint vector becomes old_end - new_start.
                vx = old_end_local.x() - mouse_local.x()
                vy = old_end_local.y() - mouse_local.y()
                vx, vy = _compat_0651(win, vx, vy)
                new_origin_scene = start_transform.map(QPointF(old_end_local.x() - vx, old_end_local.y() - vy))
                self.model.w = vx / g
                self.model.h = vy / g
                self.setPos(new_origin_scene)
                self.model.x = new_origin_scene.x() / g
                self.model.y = -new_origin_scene.y() / g
                self.apply_transform_from_model()
                fixed_now = self.mapToScene(QPointF(self.model.w * g, self.model.h * g))
                delta = self._compat_0649 - fixed_now

            if abs(delta.x()) > 1e-9 or abs(delta.y()) > 1e-9:
                final_pos = self.pos() + delta
                self.setPos(final_pos)
                self.model.x = final_pos.x() / g
                self.model.y = -final_pos.y() / g

            try:
                win.notify_canvas_model_changed()
            except Exception:
                try: win.live_refresh()
                except Exception: pass
            self.update(); event.accept(); return
        except Exception:
            try:
                self._compat_0655 = None
            except Exception:
                pass
    return _compat_0661(self, event)


def _compat_0654(self, event):
    try:
        self._compat_0655 = None
        self._compat_0657 = None
        self._compat_0649 = None
        self._compat_0659 = None
        self._compat_0656 = None
    except Exception:
        pass
    return _compat_0663(self, event)


def _compat_0650(self, event):
    try:
        if self.isSelected() and str(getattr(self.model, 'shape', '') or '') == 'line':
            h = 'rot' if _rotation_handle(self._rect(), self.window.grid_px * self.rotate_handle_factor).contains(event.pos()) else _hit_handle(self._handles(), event.pos())
            if h in ('start', 'end'):
                # Endpoint handles should feel like dragging along the visible
                # line direction; horizontal/vertical/diagonal cursor is chosen
                # from the transformed line vector.
                pts = _compat_0647(self)
                a = self.mapToScene(pts['start']); b = self.mapToScene(pts['end'])
                import math
                ang = (math.degrees(math.atan2(b.y() - a.y(), b.x() - a.x())) + 180.0) % 180.0
                if ang < 22.5 or ang >= 157.5: cur = Qt.SizeHorCursor
                elif 67.5 <= ang < 112.5: cur = Qt.SizeVerCursor
                elif 22.5 <= ang < 67.5: cur = Qt.SizeFDiagCursor
                else: cur = Qt.SizeBDiagCursor
                self.setCursor(QCursor(cur)); return QGraphicsItem.hoverMoveEvent(self, event)
    except Exception:
        pass
    return _compat_0660(self, event)

try:
    GraphicItem.mousePressEvent = _compat_0653
    GraphicItem.mouseMoveEvent = _compat_0652
    GraphicItem.mouseReleaseEvent = _compat_0654
    GraphicItem.hoverMoveEvent = _compat_0650
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v71: curved line scaling + robust plain text editing/selection.
# - Curved lines keep their visible curvature ratio when an endpoint is scaled.
# - Curve-radius handle works in frozen local coordinates and snaps to edit grid.
# - Plain TEXT focus/commit is null-scene safe and does not trigger crashes when
#   the view refreshes while editing or after selecting another object.
# ---------------------------------------------------------------------------
try:
    _compat_0675 = GraphicItem.mousePressEvent
    _compat_0674 = GraphicItem.mouseMoveEvent
    _compat_0676 = GraphicItem.mouseReleaseEvent
except Exception:
    _compat_0675 = None
    _compat_0674 = None
    _compat_0676 = None


def _compat_0671(w, h, g):
    try:
        return math.hypot(float(w) * float(g), float(h) * float(g))
    except Exception:
        return 0.0


def _compat_0679(win, value):
    try:
        step = win._edit_grid_step() if hasattr(win, '_edit_grid_step') else 0.5
        step = max(0.001, float(step or 0.001))
    except Exception:
        step = 0.5
    try:
        return round(float(value) / step) * step
    except Exception:
        return float(value or 0.0)


def _compat_0666(self, event):
    if event.button() == Qt.LeftButton and self.isSelected():
        try:
            if str(getattr(self.model, 'shape', '') or '') == 'line':
                h = _hit_handle(self._handles(), event.pos())
                if h == 'curve':
                    st = self.sceneTransform()
                    inv, ok = st.inverted()
                    if not ok:
                        return _compat_0675(self, event)
                    self._compat_0668 = True
                    self._compat_0669 = inv
                    self._compat_0670 = {
                        'curve_radius': _compat_0602(getattr(self.model, 'curve_radius', 0.0), 0.0),
                        'w': _compat_0602(getattr(self.model, 'w', 0.0), 0.0),
                        'h': _compat_0602(getattr(self.model, 'h', 0.0), 0.0),
                    }
                    event.accept(); return
        except Exception:
            pass
    return _compat_0675(self, event)


def _compat_0665(self, event):
    # Dedicated curve handle: use the frozen local frame from press time.  This
    # prevents the curve apex from jumping when the line is rotated/flipped.
    if getattr(self, '_compat_0668', False):
        try:
            win = self.window
            g = float(win.grid_px)
            inv = self._compat_0669
            p = inv.map(event.scenePos())
            w = _compat_0602(getattr(self.model, 'w', 0.0), 0.0) * g
            h = _compat_0602(getattr(self.model, 'h', 0.0), 0.0) * g
            mid_y = h / 2.0
            cr = (mid_y - p.y()) / g
            self.model.curve_radius = _compat_0679(win, cr)
            try:
                win.notify_canvas_model_changed()
            except Exception:
                try: win.live_refresh()
                except Exception: pass
            self.update(); event.accept(); return
        except Exception:
            try: self._compat_0668 = False
            except Exception: pass
    return _compat_0674(self, event)


def _compat_0667(self, event):
    try:
        self._compat_0668 = False
        self._compat_0669 = None
        self._compat_0670 = None
    except Exception:
        pass
    return _compat_0676(self, event)

try:
    GraphicItem.mousePressEvent = _compat_0666
    GraphicItem.mouseMoveEvent = _compat_0665
    GraphicItem.mouseReleaseEvent = _compat_0667
except Exception:
    pass

# Patch v70 endpoint scaling to keep the curved-line apex proportional.  The
# existing v70 handler already handles natural endpoint direction; this wrapper
# records the old line length/curve before the handler, then applies the same
# uniform endpoint scale to curve_radius afterwards.
try:
    _compat_0673 = GraphicItem.mouseMoveEvent

    def _compat_0672(self, event):
        if getattr(self, '_compat_0655', None) and getattr(self, '_compat_0657', None) is not None:
            try:
                g = float(self.window.grid_px)
                old_w = _compat_0602(getattr(self, ' _unused', 0.0), 0.0)
                start = dict(getattr(self, '_compat_0657', {}) or {})
                old_len = _compat_0671(start.get('w', 0.0), start.get('h', 0.0), g)
                old_curve = _compat_0602(getattr(self.model, 'curve_radius', 0.0), 0.0)
                res = _compat_0673(self, event)
                new_len = _compat_0671(getattr(self.model, 'w', 0.0), getattr(self.model, 'h', 0.0), g)
                if old_len > 1e-9 and abs(old_curve) > 1e-12:
                    self.model.curve_radius = _compat_0679(self.window, old_curve * (new_len / old_len))
                    try:
                        self.window.notify_canvas_model_changed()
                    except Exception:
                        try: self.window.live_refresh()
                        except Exception: pass
                    self.update()
                return res
            except Exception:
                pass
        return _compat_0673(self, event)

    GraphicItem.mouseMoveEvent = _compat_0672
except Exception:
    pass

# Plain text robustness: commit safely and keep canvas object mode.  The old
# handlers assumed scene/window always exists during focus changes; after a live
# refresh that is not always true and plain text could get stuck or crash.
try:
    _compat_0677 = TextItem.focusOutEvent
    _compat_0678 = TextItem.keyPressEvent

    def _compat_0664(self):
        try:
            if not (self.data(0) in ('ATTR_REF_DES', 'ATTR_BODY') or bool(getattr(self.model, '_is_attribute_text', False))):
                self.model.text = self.toPlainText()
        except Exception:
            pass
        try:
            self.setTextInteractionFlags(Qt.NoTextInteraction)
            self.common_flags()
        except Exception:
            pass
        try:
            sc = self.scene()
            if sc is not None and hasattr(sc, 'window'):
                sc.window.notify_canvas_model_changed()
        except Exception:
            try:
                sc = self.scene()
                if sc is not None and hasattr(sc, 'window'):
                    sc.window.live_refresh()
            except Exception:
                pass

    def _compat_0681(self, event):
        try:
            if self.textInteractionFlags() != Qt.NoTextInteraction and event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
                _compat_0664(self)
                self.clearFocus()
                event.accept(); return
        except Exception:
            pass
        return _compat_0678(self, event)

    def _compat_0680(self, event):
        try:
            _compat_0664(self)
        except Exception:
            pass
        try:
            return QGraphicsTextItem.focusOutEvent(self, event)
        except Exception:
            return None

    TextItem.keyPressEvent = _compat_0681
    TextItem.focusOutEvent = _compat_0680
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v85: use the natural graphic resize behaviour for BODY handles.
# The BODY is still the logical owner of pins/attributes/imported body graphics,
# but its canvas handle scaling now uses the same frozen-local-coordinate resize
# model as GraphicItem v69:
#   - resize direction follows the mouse after rotate/flip,
#   - dimensions snap to the edit grid with minimum one edit grid,
#   - the opposite handle remains fixed during the drag,
#   - child objects are scaled once from the immutable press-state so pins do
#     not get cumulatively scaled.
# ---------------------------------------------------------------------------
try:
    _compat_0703 = BodyItem.apply_transform_from_model
    _compat_0704 = BodyItem.hoverMoveEvent
    _compat_0706 = BodyItem.mousePressEvent
    _compat_0705 = BodyItem.mouseMoveEvent
    _compat_0707 = BodyItem.mouseReleaseEvent
except Exception:
    _compat_0703 = None
    _compat_0704 = None
    _compat_0706 = None
    _compat_0705 = None
    _compat_0707 = None


def _compat_0697(item):
    g = float(getattr(item.window, 'grid_px', 1.0) or 1.0)
    w = _compat_0602(getattr(item.model, 'width', 0.0), 0.0) * g
    h = _compat_0602(getattr(item.model, 'height', 0.0), 0.0) * g
    return QRectF(0.0, 0.0, w, h).normalized()


def _compat_0691(self):
    def f(name, default):
        try:
            return float(getattr(self.model, name, default) or default)
        except Exception:
            return default
    sx, sy, rot = f('scale_x', 1.0), f('scale_y', 1.0), f('rotation', 0.0)
    self.model.scale_x, self.model.scale_y, self.model.rotation = sx, sy, rot
    try:
        # Same stable pivot convention as graphics: lower-left of the object.
        # This keeps rotate/flip fixed at one deterministic BODY origin.
        r = _compat_0697(self)
        self.setTransformOriginPoint(r.bottomLeft())
    except Exception:
        pass
    self.setTransform(QTransform().scale(sx, sy))
    self.setRotation(rot)


def _compat_0692(item):
    r = _compat_0697(item)
    return {
        'tl': QPointF(r.left(), r.top()),
        'tr': QPointF(r.right(), r.top()),
        'bl': QPointF(r.left(), r.bottom()),
        'br': QPointF(r.right(), r.bottom()),
        'l': QPointF(r.left(), r.center().y()),
        'r': QPointF(r.right(), r.center().y()),
        't': QPointF(r.center().x(), r.top()),
        'b': QPointF(r.center().x(), r.bottom()),
    }


def _compat_0693(self, event):
    try:
        if self.isSelected():
            h = 'rot' if _rotation_handle(self.rect(), self.window.grid_px * self.rotate_handle_factor).contains(event.pos()) else _hit_handle(self._handles(), event.pos())
            self.setCursor(QCursor(_compat_0620(self, h)) if h else QCursor(Qt.ArrowCursor))
            return QGraphicsRectItem.hoverMoveEvent(self, event)
    except Exception:
        pass
    return _compat_0704(self, event)


def _compat_0700(self):
    win = self.window
    unit = getattr(win, 'current_unit', None)
    body = self.model
    return {
        'x': _compat_0602(getattr(body, 'x', 0.0), 0.0),
        'y': _compat_0602(getattr(body, 'y', 0.0), 0.0),
        'w': _compat_0602(getattr(body, 'width', 0.0), 0.0),
        'h': _compat_0602(getattr(body, 'height', 0.0), 0.0),
        'sx': _compat_0602(getattr(body, 'scale_x', 1.0), 1.0),
        'sy': _compat_0602(getattr(body, 'scale_y', 1.0), 1.0),
        'rot': _compat_0602(getattr(body, 'rotation', 0.0), 0.0),
        'pos': QPointF(self.pos()),
        'pins': [(p, float(getattr(p, 'x', 0.0)), float(getattr(p, 'y', 0.0)), float(getattr(p, 'length', 0.0))) for p in getattr(unit, 'pins', [])],
        'texts': [(t, float(getattr(t, 'x', 0.0)), float(getattr(t, 'y', 0.0))) for t in getattr(unit, 'texts', [])],
        'attributes': [(t, float(getattr(t, 'x', 0.0)), float(getattr(t, 'y', 0.0))) for t in getattr(getattr(unit, 'body', None), 'attribute_texts', {}).values()],
        'graphics': [(gr, float(getattr(gr, 'x', 0.0)), float(getattr(gr, 'y', 0.0)), float(getattr(gr, 'w', 0.0)), float(getattr(gr, 'h', 0.0))) for gr in getattr(unit, 'graphics', [])],
    }


def _compat_0695(self, event):
    if event.button() == Qt.LeftButton and self.isSelected():
        try:
            if _rotation_handle(self.rect(), self.window.grid_px * self.rotate_handle_factor).contains(event.pos()):
                return _compat_0706(self, event)
            h = _hit_handle(self._handles(), event.pos())
            if h:
                try:
                    self.window.push_undo_state()
                    self._undo_state_pushed_for_drag = True
                except Exception:
                    pass
                st = self.sceneTransform()
                inv, ok = st.inverted()
                if not ok:
                    return _compat_0706(self, event)
                pts = _compat_0692(self)
                anchor_name = _compat_0609(h)
                anchor_local = QPointF(pts.get(anchor_name, QPointF(0, 0)))
                self._compat_0698 = h
                self._compat_0689 = anchor_name
                self._compat_0688 = QPointF(anchor_local)
                self._compat_0690 = self.mapToScene(anchor_local)
                self._compat_0699 = inv
                self._compat_0702 = st
                self._compat_0701 = _compat_0700(self)
                event.accept(); return
        except Exception:
            pass
    return _compat_0706(self, event)


def _compat_0694(self, event):
    if getattr(self, '_compat_0698', None) and getattr(self, '_compat_0701', None) is not None:
        try:
            win = self.window
            g = float(win.grid_px)
            hname = str(self._compat_0698)
            start = dict(self._compat_0701)
            anchor_local = QPointF(self._compat_0688)
            anchor_scene = QPointF(self._compat_0690)
            inv = self._compat_0699
            mouse_local = inv.map(event.scenePos())

            old_w = max(1e-9, _compat_0602(start.get('w'), 0.0) * g)
            old_h = max(1e-9, _compat_0602(start.get('h'), 0.0) * g)
            left, right = 0.0, old_w
            top, bottom = 0.0, old_h

            if hname in ('l', 'tl', 'bl'):
                right = anchor_local.x()
                new_w = _compat_0636(win, right - mouse_local.x())
                left = right - new_w
            elif hname in ('r', 'tr', 'br'):
                left = anchor_local.x()
                new_w = _compat_0636(win, mouse_local.x() - left)
                right = left + new_w
            else:
                new_w = old_w

            if hname in ('t', 'tl', 'tr'):
                bottom = anchor_local.y()
                new_h = _compat_0636(win, bottom - mouse_local.y())
                top = bottom - new_h
            elif hname in ('b', 'bl', 'br'):
                top = anchor_local.y()
                new_h = _compat_0636(win, mouse_local.y() - top)
                bottom = top + new_h
            else:
                new_h = old_h

            # Rebuild BODY from the immutable drag-start state, then apply the
            # new geometry absolutely. Children are also recalculated from that
            # same immutable snapshot, avoiding cumulative scaling drift.
            body = self.model
            self.prepareGeometryChange()
            body.x = start['x']; body.y = start['y']
            body.width = max(_compat_0601(win), float(new_w)) / g
            body.height = max(_compat_0601(win), float(new_h)) / g
            body.scale_x = start['sx']; body.scale_y = start['sy']; body.rotation = start['rot']
            self.setPos(QPointF(start['pos']))
            self.setRect(0.0, 0.0, body.width * g, body.height * g)
            self.apply_transform_from_model()

            new_origin_scene = self._compat_0702.map(QPointF(left, top))
            self.setPos(new_origin_scene)
            body.x = new_origin_scene.x() / g
            body.y = -new_origin_scene.y() / g
            self.apply_transform_from_model()

            new_anchor_local = QPointF(anchor_local.x() - left, anchor_local.y() - top)
            new_anchor_scene = self.mapToScene(new_anchor_local)
            delta = anchor_scene - new_anchor_scene
            final_pos = self.pos() + delta
            self.setPos(final_pos)
            body.x = final_pos.x() / g
            body.y = -final_pos.y() / g
            self._last_model_pos = (body.x, body.y)

            try:
                win.scale_current_unit_children_from_body_resize(start, body)
                win.update_current_unit_canvas_positions()
                win.update_attribute_items_for_unit()
            except Exception:
                pass
            try:
                win.notify_canvas_model_changed()
            except Exception:
                try: win.live_refresh()
                except Exception: pass
            self.update(); event.accept(); return
        except Exception:
            try:
                self._compat_0698 = None
            except Exception:
                pass
    return _compat_0705(self, event)


def _compat_0696(self, event):
    try:
        self._compat_0698 = None
        self._compat_0701 = None
        self._compat_0688 = None
        self._compat_0690 = None
        self._compat_0699 = None
        self._compat_0702 = None
    except Exception:
        pass
    return _compat_0707(self, event)

try:
    BodyItem.apply_transform_from_model = _compat_0691
    BodyItem.hoverMoveEvent = _compat_0693
    BodyItem.mousePressEvent = _compat_0695
    BodyItem.mouseMoveEvent = _compat_0694
    BodyItem.mouseReleaseEvent = _compat_0696
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v97: robust proportional graphic scaling for all graphic shapes.
# ---------------------------------------------------------------------------
# Scale +/- on graphics must preserve the authored structure of the object:
# - line endpoint vectors stay vectors
# - quadratic control points / curved line radius scale with the object
# - rect/ellipse/circle keep their local geometry centered
# - no object jumps to the body origin
try:
    _compat_1165 = GraphicItem.scale_by
except Exception:
    _compat_1165 = None


def _compat_1170(self, value, step):
    try:
        step = max(0.001, float(step or 0.001))
        value = float(value or 0.0)
    except Exception:
        step = 0.5
        value = 0.0
    sign = -1.0 if value < 0 else 1.0
    mag = abs(value)
    snapped = round(mag / step) * step
    if snapped < step:
        snapped = step
    try:
        return self.window._clean_float(sign * snapped)
    except Exception:
        return sign * snapped


def _compat_1162(self, factor):
    try:
        factor = float(factor)
    except Exception:
        factor = 1.0
    if abs(factor) < 1e-9:
        return
    try:
        step = self.window._edit_grid_step() if hasattr(self.window, '_edit_grid_step') else 0.5
    except Exception:
        step = 0.5

    m = self.model
    old_x = float(getattr(m, 'x', 0.0) or 0.0)
    old_y = float(getattr(m, 'y', 0.0) or 0.0)
    old_w = float(getattr(m, 'w', 0.0) or 0.0)
    old_h = float(getattr(m, 'h', 0.0) or 0.0)

    # Model convention: x/y is the top-left/line-start anchor, h extends down in
    # screen space, therefore the model-space center is y - h/2.
    cx = old_x + old_w / 2.0
    cy = old_y - old_h / 2.0

    new_w = _compat_1170(self, old_w * factor, step)
    new_h = _compat_1170(self, old_h * factor, step)

    self.prepareGeometryChange()
    m.x = cx - new_w / 2.0
    m.y = cy + new_h / 2.0
    m.w = new_w
    m.h = new_h

    # Preserve curved-line/arc structure.  ctrl_x/ctrl_y are local vectors from
    # the anchor; curve_radius is a local vertical offset from the line midpoint.
    try:
        if getattr(m, 'ctrl_x', None) is not None:
            m.ctrl_x = float(m.ctrl_x) * factor
        if getattr(m, 'ctrl_y', None) is not None:
            m.ctrl_y = float(m.ctrl_y) * factor
        if getattr(m, 'curve_radius', None) is not None:
            m.curve_radius = float(getattr(m, 'curve_radius', 0.0) or 0.0) * factor
    except Exception:
        pass

    try:
        g = self.window.grid_px
        self.setPos(m.x * g, -m.y * g)
        self.apply_transform_from_model()
    except Exception:
        pass
    try:
        self.window.notify_canvas_model_changed()
    except Exception:
        try: self.window.live_refresh()
        except Exception: pass
    self.update()

try:
    GraphicItem.scale_by = _compat_1162
    GraphicItem.scale_selected = lambda self, factor: _compat_1162(self, factor)
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v99: stable BODY canvas resize preview/commit.
# ---------------------------------------------------------------------------
# The v85 canvas resize path already uses an immutable press-state for BODY
# dimensions.  However graphic curve parameters (ctrl_x/ctrl_y/curve_radius)
# were not part of that immutable snapshot, so repeated mouseMove previews could
# still read already-mutated curve data and visually distort mixed graphics while
# dragging.  This patch extends the BODY snapshot and forces one final full
# workspace sync on release while keeping the BODY selected.
try:
    _compat_1190 = _compat_0700
except Exception:
    _compat_1190 = None


def _compat_0700(self):
    win = self.window
    unit = getattr(win, 'current_unit', None)
    body = self.model
    graphics = []
    try:
        for gr in getattr(unit, 'graphics', []) or []:
            graphics.append((
                gr,
                float(getattr(gr, 'x', 0.0)),
                float(getattr(gr, 'y', 0.0)),
                float(getattr(gr, 'w', 0.0)),
                float(getattr(gr, 'h', 0.0)),
                getattr(gr, 'ctrl_x', None),
                getattr(gr, 'ctrl_y', None),
                getattr(gr, 'curve_radius', None),
                float(getattr(gr, 'rotation', 0.0) or 0.0),
                float(getattr(gr, 'scale_x', 1.0) or 1.0),
                float(getattr(gr, 'scale_y', 1.0) or 1.0),
            ))
    except Exception:
        pass
    return {
        'x': _compat_0602(getattr(body, 'x', 0.0), 0.0),
        'y': _compat_0602(getattr(body, 'y', 0.0), 0.0),
        'w': _compat_0602(getattr(body, 'width', 0.0), 0.0),
        'h': _compat_0602(getattr(body, 'height', 0.0), 0.0),
        'sx': _compat_0602(getattr(body, 'scale_x', 1.0), 1.0),
        'sy': _compat_0602(getattr(body, 'scale_y', 1.0), 1.0),
        'rot': _compat_0602(getattr(body, 'rotation', 0.0), 0.0),
        'pos': QPointF(self.pos()),
        'pins': [(p, float(getattr(p, 'x', 0.0)), float(getattr(p, 'y', 0.0)), float(getattr(p, 'length', 0.0))) for p in getattr(unit, 'pins', []) or []],
        'texts': [(t, float(getattr(t, 'x', 0.0)), float(getattr(t, 'y', 0.0))) for t in getattr(unit, 'texts', []) or []],
        'attributes': [(t, float(getattr(t, 'x', 0.0)), float(getattr(t, 'y', 0.0))) for t in getattr(getattr(unit, 'body', None), 'attribute_texts', {}).values()],
        'graphics': graphics,
    }

try:
    _compat_1188 = BodyItem.mouseMoveEvent
except Exception:
    _compat_1188 = None


def _compat_1180(self, event):
    # Use the v85 implementation, but suppress expensive attribute regeneration
    # during mouseMove.  Attribute text models are still transformed by the
    # immutable snapshot in scale_current_unit_children_from_body_resize(); the
    # full scene is rebuilt on release.  This avoids transient canvas distortion
    # and stale half-updated items while dragging a BODY handle.
    if getattr(self, '_compat_0698', None) and getattr(self, '_compat_0701', None) is not None:
        win = getattr(self, 'window', None)
        old_update_attrs = getattr(win, 'update_attribute_items_for_unit', None) if win is not None else None
        if old_update_attrs is not None:
            try:
                setattr(win, 'update_attribute_items_for_unit', lambda *a, **k: None)
                return _compat_0694(self, event)
            finally:
                try:
                    setattr(win, 'update_attribute_items_for_unit', old_update_attrs)
                except Exception:
                    pass
    if _compat_1188 is not None:
        return _compat_1188(self, event)
    return QGraphicsRectItem.mouseMoveEvent(self, event)

try:
    _compat_1189 = BodyItem.mouseReleaseEvent
except Exception:
    _compat_1189 = None


def _compat_1181(self, event):
    win = getattr(self, 'window', None)
    body = getattr(self, 'model', None)
    was_body_resize = bool(getattr(self, '_compat_0698', None))
    selected_id = id(body) if body is not None else None
    result = None
    if _compat_1189 is not None:
        result = _compat_1189(self, event)
    else:
        result = QGraphicsRectItem.mouseReleaseEvent(self, event)
    if was_body_resize and win is not None:
        try:
            if selected_id is not None:
                win._selection_restore_ids = {selected_id}
            # Final authoritative sync: rebuild all canvas items from the model,
            # then refresh tables/properties. This is intentionally deferred until
            # after Qt has finished the mouse-release event.
            def _final_sync():
                try:
                    if selected_id is not None:
                        win._selection_restore_ids = {selected_id}
                    win.rebuild_scene()
                    win.rebuild_tree()
                    win.rebuild_pin_table()
                    win.refresh_properties()
                    if hasattr(win, 'view'):
                        win.view.viewport().update()
                except Exception:
                    try:
                        win.update_current_unit_canvas_positions()
                    except Exception:
                        pass
            try:
                from PySide6.QtCore import QTimer as _QTimer
                _QTimer.singleShot(0, _final_sync)
            except Exception:
                _final_sync()
        except Exception:
            pass
    return result

try:
    BodyItem.mouseMoveEvent = _compat_1180
    BodyItem.mouseReleaseEvent = _compat_1181
except Exception:
    pass

# ---------------------------------------------------------------------------
# SW102 graphics refresh safety: external BODY vector scaling changes GraphicModel
# w/h/curve data from MainWindow.  Let Qt know the bounding rect may change before
# repainting the existing item during live canvas resize.
# ---------------------------------------------------------------------------
try:
    _compat_0761 = GraphicItem.update
except Exception:
    _compat_0761 = None

def _compat_0759(self, *args, **kwargs):
    try:
        self.prepareGeometryChange()
    except Exception:
        pass
    if _compat_0761 is not None:
        return _compat_0761(self, *args, **kwargs)
    try:
        return QGraphicsItem.update(self, *args, **kwargs)
    except Exception:
        return None

try:
    GraphicItem.update = _compat_0759
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v106: use dedicated pin raster for pin canvas edits
# ---------------------------------------------------------------------------
# Pin anchors are electrical edit objects and must snap to the dedicated pin
# raster, not to arbitrary graphic/vector/grid settings.  Other item classes keep
# using the active edit grid.

try:
    _compat_0794 = TransformMixin.itemChange
except Exception:
    _compat_0794 = None


def _compat_0781(item):
    try:
        win = item.scene().window
        return float(getattr(win, 'pin_grid_px', 0.0) or 0.0)
    except Exception:
        return 0.0


def _compat_0801(self, change, value):
    try:
        if change == QGraphicsItem.ItemPositionChange and self.scene() and self.data(0) == 'PIN':
            win = self.scene().window
            if bool(getattr(win, 'template_snap_check', None) and not win.template_snap_check.isChecked()):
                return super(TransformMixin, self).itemChange(change, value)
            g = _compat_0781(self) or float(getattr(win, 'edit_grid_px', self.scene().grid_px) or self.scene().grid_px)
            return QPointF(snap(value.x(), g), snap(value.y(), g))
    except Exception:
        pass
    if _compat_0794 is not None:
        return _compat_0794(self, change, value)
    return super(TransformMixin, self).itemChange(change, value)


try:
    TransformMixin.itemChange = _compat_0801
except Exception:
    pass


try:
    _compat_0791 = PinItem.update_model_pos
except Exception:
    _compat_0791 = None


def _compat_0784(self):
    g = self.window.grid_px
    old_x, old_y = float(self.model.x), float(self.model.y)
    raw_x = self.pos().x() / g
    raw_y = -self.pos().y() / g
    try:
        self.model.x = self.window.snap_pin_value(raw_x)
        self.model.y = self.window.snap_pin_value(raw_y)
        self.model.pin_grid_step = getattr(self.window, 'pin_grid_step', 0.1)
    except Exception:
        self.model.x = raw_x
        self.model.y = raw_y
    dx, dy = float(self.model.x) - old_x, float(self.model.y) - old_y
    if abs(dx) > 1e-9 or abs(dy) > 1e-9:
        try:
            if QApplication.mouseButtons() & Qt.LeftButton:
                self.model.auto_dock = False
        except Exception:
            pass
        for ax_name, ay_name in (('label_x', 'label_y'), ('number_x', 'number_y')):
            if getattr(self.model, ax_name, None) is not None and getattr(self.model, ay_name, None) is not None:
                try:
                    setattr(self.model, ax_name, self.window.snap_pin_value(float(getattr(self.model, ax_name)) + dx))
                    setattr(self.model, ay_name, self.window.snap_pin_value(float(getattr(self.model, ay_name)) + dy))
                except Exception:
                    setattr(self.model, ax_name, float(getattr(self.model, ax_name)) + dx)
                    setattr(self.model, ay_name, float(getattr(self.model, ay_name)) + dy)
        for tm in (getattr(self.model, 'attribute_texts', {}) or {}).values():
            try:
                tm.x = self.window.snap_pin_value(float(tm.x) + dx)
                tm.y = self.window.snap_pin_value(float(tm.y) + dy)
            except Exception:
                try:
                    tm.x = float(tm.x) + dx
                    tm.y = float(tm.y) + dy
                except Exception:
                    pass


try:
    PinItem.update_model_pos = _compat_0784
except Exception:
    pass


try:
    _compat_0790 = PinItem.scale_selected
except Exception:
    _compat_0790 = None


def _compat_0783(self, factor):
    try:
        step = float(getattr(self.window, 'pin_grid_step', 0.1) or 0.1)
    except Exception:
        step = 0.1
    try:
        value = float(self.model.length) * float(factor)
        self.model.length = max(step, round(value / step) * step)
    except Exception:
        self.model.length = max(step, float(getattr(self.model, 'length', step) or step))
    self.apply_transform_from_model()
    self.update()


try:
    PinItem.scale_selected = _compat_0783
    PinItem.scale_by = _compat_0783
except Exception:
    pass

# -----------------------------------------------------------------------------
# Liebherr v109: pin movement uses active Edit Grid and keeps view in focus
# -----------------------------------------------------------------------------
# v106 introduced a dedicated electrical pin raster.  For drawing/editing the
# user requested the visible Edit Grid to be authoritative.  This patch keeps
# PinItem snapping on that grid and asks the MainWindow to auto-scroll selected
# items during drags.

try:
    _compat_0829 = TransformMixin.itemChange
except Exception:
    _compat_0829 = None


def _compat_0839(self, change, value):
    if change == QGraphicsItem.ItemPositionChange and self.scene():
        try:
            win = self.scene().window
            if getattr(self, 'data', lambda *_: None)(0) == 'PIN':
                g = float(getattr(win, 'edit_grid_px', 0.0) or getattr(win, 'pin_grid_px', 0.0) or self.scene().grid_px)
                return QPointF(snap(value.x(), g), snap(value.y(), g))
        except Exception:
            pass
    result = _compat_0829(self, change, value) if _compat_0829 is not None else super(TransformMixin, self).itemChange(change, value)
    if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
        try:
            self.scene().window.notify_canvas_model_changed()
        except Exception:
            pass
    return result

try:
    TransformMixin.itemChange = _compat_0839
except Exception:
    pass

try:
    _compat_0825 = PinItem.update_model_pos
except Exception:
    _compat_0825 = None


def _compat_0823(self):
    old_x = float(getattr(self.model, 'x', 0.0) or 0.0)
    old_y = float(getattr(self.model, 'y', 0.0) or 0.0)
    if _compat_0825 is not None:
        _compat_0825(self)
    try:
        win = self.window
        nx = win.snap_pin_value(getattr(self.model, 'x', old_x))
        ny = win.snap_pin_value(getattr(self.model, 'y', old_y))
        dx, dy = nx - float(getattr(self.model, 'x', old_x) or 0.0), ny - float(getattr(self.model, 'y', old_y) or 0.0)
        self.model.x, self.model.y = nx, ny
        if abs(dx) > 1e-12 or abs(dy) > 1e-12:
            try:
                win._move_pin_owned_texts(self.model, dx, dy)
            except Exception:
                pass
        self.model.pin_grid_step = getattr(win, 'pin_grid_step', None)
    except Exception:
        pass

try:
    PinItem.update_model_pos = _compat_0823
except Exception:
    pass

# -----------------------------------------------------------------------------
# Liebherr v110: more comfortable hit zones for PIN and TEXT selection
# -----------------------------------------------------------------------------
# Thin pins and small text objects were too hard to click in dense symbols.  The
# paint geometry is unchanged; only QGraphicsItem.shape() is widened for hit
# testing.  This keeps the drawing accurate while making selection more robust.

try:
    _compat_0844 = PinItem.shape
except Exception:
    _compat_0844 = None


def _compat_0842(self):
    try:
        g = float(getattr(self.window, 'grid_px', 50.0) or 50.0)
        L = float(getattr(self.model, 'length', 1.0) or 1.0) * g
        side = str(getattr(self.model, 'side', PinSide.RIGHT.value) or PinSide.RIGHT.value)
        if side == PinSide.LEFT.value:
            p1, p2 = QPointF(-L, 0), QPointF(0, 0)
        elif side == PinSide.TOP.value:
            p1, p2 = QPointF(0, -L), QPointF(0, 0)
        elif side == PinSide.BOTTOM.value:
            p1, p2 = QPointF(0, L), QPointF(0, 0)
        else:
            p1, p2 = QPointF(0, 0), QPointF(L, 0)
        path = QPainterPath(p1)
        path.lineTo(p2)
        # Larger endpoint boxes make the electrical anchor easy to grab without
        # visually changing the pin.
        endpoint = max(18.0, 0.46 * g)
        path.addRect(QRectF(p1.x() - endpoint / 2, p1.y() - endpoint / 2, endpoint, endpoint))
        path.addRect(QRectF(p2.x() - endpoint / 2, p2.y() - endpoint / 2, endpoint, endpoint))
        if bool(getattr(self.model, 'inverted', False)):
            r = max(6.0, .24 * g)
            bx = (-r if side == PinSide.LEFT.value else (r if side == PinSide.RIGHT.value else 0))
            by = (0 if side in (PinSide.LEFT.value, PinSide.RIGHT.value) else (-r if side == PinSide.TOP.value else r))
            path.addEllipse(QPointF(bx, by), r, r)
        stroker = QPainterPathStroker()
        stroker.setWidth(max(18.0, 0.46 * g))
        return stroker.createStroke(path).united(path)
    except Exception:
        if _compat_0844 is not None:
            return _compat_0844(self)
        return QGraphicsItem.shape(self)

try:
    PinItem.shape = _compat_0842
except Exception:
    pass

try:
    _compat_0845 = TextItem.shape
except Exception:
    _compat_0845 = None


def _compat_0846(self):
    try:
        g = float(getattr(self.window, 'grid_px', 50.0) or 50.0)
        tol = max(14.0, 0.28 * g)
        r = self._visual_text_rect().adjusted(-tol, -tol, tol, tol)
        path = QPainterPath()
        path.addRect(r)
        # The green anchor is often what the user tries to grab; include it in
        # the selectable area as well.
        a = self._text_anchor_offset()
        s = max(tol, 0.32 * g)
        path.addRect(QRectF(a.x() - s / 2, a.y() - s / 2, s, s))
        return path
    except Exception:
        if _compat_0845 is not None:
            return _compat_0845(self)
        return QGraphicsTextItem.shape(self)

try:
    TextItem.shape = _compat_0846
except Exception:
    pass


# -----------------------------------------------------------------------------
# Liebherr v114: fast multi-selection paint + comfortable hit zones
# -----------------------------------------------------------------------------
# Avoid changing selection state inside paint().  During multi-selection the view
# draws one shared group frame; items draw only their normal geometry.

def _compat_0117(window):
    try:
        return len([i for i in window.scene.selectedItems() if i.data(0) in ('BODY','PIN','TEXT','ATTR_REF_DES','ATTR_BODY','GRAPHIC')]) > 1
    except Exception:
        return False

try:
    _compat_0094 = TransformMixin.itemChange
except Exception:
    _compat_0094 = None

def _compat_0128(self, change, value):
    try:
        win = self.scene().window if self.scene() is not None else None
        if win is not None and getattr(win, '_group_drag_visual_only', False):
            if change in (QGraphicsItem.ItemPositionChange, QGraphicsItem.ItemPositionHasChanged):
                return QGraphicsItem.itemChange(self, change, value)
    except Exception:
        pass
    if _compat_0094 is not None:
        return _compat_0094(self, change, value)
    return QGraphicsItem.itemChange(self, change, value)

try:
    TransformMixin.itemChange = _compat_0128
except Exception:
    pass

try:
    _compat_0085 = BodyItem.paint
    def _compat_0095(self, painter, option, widget=None):
        if _compat_0117(self.window) and self.isSelected():
            try:
                # Draw the real body geometry only.  The shared group frame is
                # drawn by SymbolView.drawForeground().
                graphics_as_body = False
                try:
                    attrs = getattr(self.model, 'attributes', {}) or {}
                    graphics_as_body = str(attrs.get('MENTOR_GRAPHICS_AS_BODY', '0')) == '1'
                except Exception:
                    pass
                if not graphics_as_body:
                    QGraphicsRectItem.paint(self, painter, option, widget)
                return
            except Exception:
                pass
        return _compat_0085(self, painter, option, widget)
    BodyItem.paint = _compat_0095
except Exception:
    pass

try:
    _compat_0092 = TextItem.paint
    def _compat_0126(self, painter, option, widget=None):
        if _compat_0117(self.window) and self.isSelected():
            QGraphicsTextItem.paint(self, painter, option, widget)
            return
        return _compat_0092(self, painter, option, widget)
    TextItem.paint = _compat_0126
except Exception:
    pass

try:
    _compat_0086 = GraphicItem.paint
    def _compat_0105(self, painter, option, widget=None):
        if _compat_0117(self.window) and self.isSelected():
            g, m = self.window.grid_px, self.model
            painter.setPen(pen_for(m.style.stroke, m.style.line_width, m.style.line_style, g))
            painter.setBrush(QBrush(rgb(m.style.fill)) if m.style.fill else QBrush(Qt.NoBrush))
            if m.shape in ('line', 'arc'):
                ctrl_x = getattr(m, 'ctrl_x', None); ctrl_y = getattr(m, 'ctrl_y', None)
                if ctrl_x is not None and ctrl_y is not None:
                    path = QPainterPath(QPointF(0, 0))
                    path.quadTo(QPointF(float(ctrl_x) * g, -float(ctrl_y) * g), QPointF(m.w * g, -m.h * g))
                    painter.drawPath(path)
                else:
                    r = float(getattr(m, 'curve_radius', 0.0) or 0.0)
                    if abs(r) > 1e-9:
                        path = QPainterPath(QPointF(0, 0))
                        path.quadTo(QPointF(m.w * g / 2, m.h * g / 2 - r * g), QPointF(m.w * g, m.h * g))
                        painter.drawPath(path)
                    else:
                        painter.drawLine(QPointF(0, 0), QPointF(m.w * g, m.h * g))
            elif m.shape == 'rect':
                painter.drawRect(QRectF(0, 0, m.w * g, m.h * g))
            elif m.shape in ('ellipse', 'circle'):
                painter.drawEllipse(QRectF(0, 0, m.w * g, m.h * g))
            return
        return _compat_0086(self, painter, option, widget)
    GraphicItem.paint = _compat_0105
except Exception:
    pass

try:
    _compat_0090 = PinItem.paint
    def _compat_0118(self, painter, option, widget=None):
        if _compat_0117(self.window) and self.isSelected():
            # Geometry-only pin paint, no individual selection rectangle/handles.
            g, m = self.window.grid_px, self.model
            L = m.length * g
            line_color = getattr(m, 'color', (0,0,0))
            try:
                if getattr(self.window.symbol, 'template_name', '') == 'mentor_native_origin' and is_default_black(line_color):
                    line_color = mentor_pin_color(getattr(m, 'pin_type', ''))
            except Exception:
                pass
            painter.setPen(pen_for(line_color, m.line_width, m.line_style, g))
            painter.setBrush(QBrush(Qt.NoBrush))
            if m.side == PinSide.LEFT.value:
                x1,y1,x2,y2 = -L,0,0,0
            elif m.side == PinSide.TOP.value:
                x1,y1,x2,y2 = 0,-L,0,0
            elif m.side == PinSide.BOTTOM.value:
                x1,y1,x2,y2 = 0,L,0,0
            else:
                x1,y1,x2,y2 = 0,0,L,0
            painter.drawLine(QPointF(x1,y1), QPointF(x2,y2))
            if getattr(m, 'inverted', False):
                r=.18*g
                painter.drawEllipse(QPointF((-r if m.side == PinSide.LEFT.value else (r if m.side == PinSide.RIGHT.value else 0)), (0 if m.side in (PinSide.LEFT.value, PinSide.RIGHT.value) else (-r if m.side == PinSide.TOP.value else r))), r, r)
            def _qt_align(h, v):
                ha={'left':Qt.AlignLeft,'center':Qt.AlignHCenter,'right':Qt.AlignRight}.get(str(h or '').lower(), Qt.AlignHCenter)
                va={'upper':Qt.AlignTop,'center':Qt.AlignVCenter,'lower':Qt.AlignBottom}.get(str(v or '').lower(), Qt.AlignVCenter)
                return ha|va
            def _draw_anchored_text(text, ax, ay, w_grid, h_grid, align):
                lx=(float(ax)-float(m.x))*g; ly=-(float(ay)-float(m.y))*g
                painter.drawText(QRectF(lx-w_grid*g/2, ly-h_grid*g/2, w_grid*g, h_grid*g), align, str(text))
            painter.setFont(QFont(m.number_font.family, max(6, int(g*m.number_font.size_grid*.45))))
            painter.setPen(pen_for(getattr(m.number_font, 'color', line_color), m.line_width, m.line_style, g))
            if getattr(m, 'visible_number', False):
                if getattr(m, 'number_x', None) is not None and getattr(m, 'number_y', None) is not None:
                    _draw_anchored_text(m.number, m.number_x, m.number_y, 4.5, 1.1, _qt_align(getattr(m,'number_h_align','center'), getattr(m,'number_v_align','center')))
                else:
                    painter.drawText(QRectF(min(x1,x2)-.4*g, min(y1,y2)-.85*g, max(abs(x2-x1),.8*g), max(abs(y2-y1),.5*g)), Qt.AlignCenter, str(m.number))
            parts=[]
            if getattr(m, 'visible_name', False) and str(getattr(m,'name','') or '').strip(): parts.append(m.name)
            if getattr(m, 'visible_function', False) and str(getattr(m,'function','') or '').strip(): parts.append(m.function)
            label=' / '.join(parts)
            if label:
                painter.setFont(QFont(m.label_font.family, max(8, int(g*m.label_font.size_grid*.45))))
                painter.setPen(pen_for(getattr(m.label_font, 'color', line_color), m.line_width, m.line_style, g))
                if getattr(m, 'label_x', None) is not None and getattr(m, 'label_y', None) is not None:
                    _draw_anchored_text(label, m.label_x, m.label_y, 7.5, 1.1, _qt_align(getattr(m,'label_h_align','center'), getattr(m,'label_v_align','center')))
                elif m.side == PinSide.LEFT.value:
                    painter.drawText(QRectF(.25*g, -.35*g, 6*g, .7*g), Qt.AlignVCenter|Qt.AlignLeft, label)
                elif m.side == PinSide.TOP.value:
                    painter.drawText(QRectF(-3*g, .15*g, 6*g, .7*g), Qt.AlignCenter, label)
                elif m.side == PinSide.BOTTOM.value:
                    painter.drawText(QRectF(-3*g, -.85*g, 6*g, .7*g), Qt.AlignCenter, label)
                else:
                    painter.drawText(QRectF(-6.25*g, -.35*g, 6*g, .7*g), Qt.AlignVCenter|Qt.AlignRight, label)
            return
        return _compat_0090(self, painter, option, widget)
    PinItem.paint = _compat_0118
except Exception:
    pass

# More forgiving hit zones for text and pins.  These affect mouse selection and rubberband selection.
try:
    _compat_0093 = TextItem.shape
    def _compat_0127(self):
        try:
            path = _compat_0093(self)
        except Exception:
            path = QPainterPath(); path.addRect(self.boundingRect())
        try:
            rect = self._visual_text_rect().adjusted(-14, -10, 14, 10)
            p = QPainterPath(); p.addRect(rect)
            return path.united(p)
        except Exception:
            return path
    TextItem.shape = _compat_0127
except Exception:
    pass

try:
    _compat_0091 = PinItem.shape
    def _compat_0119(self):
        try:
            path = _compat_0091(self)
        except Exception:
            path = QPainterPath(); path.addRect(self.boundingRect())
        try:
            stroker = QPainterPathStroker(); stroker.setWidth(_hit_tolerance_px(self.window, 0.42, 16.0))
            return stroker.createStroke(path).united(path)
        except Exception:
            return path
    PinItem.shape = _compat_0119
except Exception:
    pass

# -----------------------------------------------------------------------------
# Liebherr v116: suppress individual selection visuals during multi-select
# -----------------------------------------------------------------------------
# A multi-selection is represented by SymbolView's shared group frame.  Individual
# item selection frames/handles must not reappear after drag/rotate/flip/other
# operations.  These wrappers paint selected items as normal geometry whenever
# more than one canvas item is selected.
try:
    from PySide6.QtWidgets import QStyle as _compat_0020, QStyleOptionGraphicsItem as _compat_0021
except Exception:
    _compat_0020 = None
    _compat_0021 = None


def _compat_0178(window):
    try:
        return len([i for i in window.scene.selectedItems() if i.data(0) in ('BODY', 'PIN', 'TEXT', 'ATTR_REF_DES', 'ATTR_BODY', 'GRAPHIC')]) > 1
    except Exception:
        return False


def _compat_0190(option):
    try:
        if _compat_0021 is not None:
            opt = _compat_0021(option)
            if _compat_0020 is not None:
                opt.state &= ~_compat_0020.State_Selected
            return opt
    except Exception:
        pass
    try:
        if _compat_0020 is not None:
            option.state &= ~_compat_0020.State_Selected
    except Exception:
        pass
    return option

try:
    _compat_0180 = BodyItem.paint
    def _compat_0157(self, painter, option, widget=None):
        if _compat_0178(self.window) and self.isSelected():
            return _compat_0180(self, painter, _compat_0190(option), widget)
        return _compat_0180(self, painter, option, widget)
    BodyItem.paint = _compat_0157
except Exception:
    pass

try:
    _compat_0183 = TextItem.paint
    def _compat_0189(self, painter, option, widget=None):
        if _compat_0178(self.window) and self.isSelected():
            return _compat_0183(self, painter, _compat_0190(option), widget)
        return _compat_0183(self, painter, option, widget)
    TextItem.paint = _compat_0189
except Exception:
    pass

try:
    _compat_0182 = PinItem.paint
    def _compat_0179(self, painter, option, widget=None):
        if _compat_0178(self.window) and self.isSelected():
            return _compat_0182(self, painter, _compat_0190(option), widget)
        return _compat_0182(self, painter, option, widget)
    PinItem.paint = _compat_0179
except Exception:
    pass

try:
    _compat_0181 = GraphicItem.paint
    def _compat_0166(self, painter, option, widget=None):
        if _compat_0178(self.window) and self.isSelected():
            return _compat_0181(self, painter, _compat_0190(option), widget)
        return _compat_0181(self, painter, option, widget)
    GraphicItem.paint = _compat_0166
except Exception:
    pass


# -----------------------------------------------------------------------------
# Liebherr v120: reliable multi-select item paint suppression
# -----------------------------------------------------------------------------
try:
    from PySide6.QtWidgets import QStyleOptionGraphicsItem as _compat_0034, QStyle as _compat_0033
except Exception:
    _compat_0034 = None
    _compat_0033 = None


def _compat_0198(win):
    try:
        return len([i for i in win.scene.selectedItems() if i.data(0) in ('BODY','PIN','TEXT','ATTR_REF_DES','ATTR_BODY','GRAPHIC')]) > 1
    except Exception:
        return False


def _compat_0219(option):
    try:
        opt = _compat_0034(option) if _compat_0034 is not None else option
        if _compat_0033 is not None:
            opt.state &= ~_compat_0033.State_Selected
        return opt
    except Exception:
        return option

for _cls_name in ('BodyItem','PinItem','TextItem','GraphicItem'):
    try:
        _cls = globals().get(_cls_name)
        _prev = getattr(_cls, 'paint')
        def _make(prev):
            def _paint(self, painter, option, widget=None):
                try:
                    if getattr(self, 'window', None) is not None and self.isSelected() and _compat_0198(self.window):
                        return prev(self, painter, _compat_0219(option), widget)
                except Exception:
                    pass
                return prev(self, painter, option, widget)
            return _paint
        setattr(_cls, 'paint', _make(_prev))
    except Exception:
        pass

# -----------------------------------------------------------------------------
# Liebherr v121: high-performance BODY/group drag for large symbols
# -----------------------------------------------------------------------------
# Moving a large symbol by dragging the BODY used to update the data model,
# properties and dependent canvas items on every mouse move.  For FPGA/split
# symbols this is too expensive.  This layer uses a preview drag path: visible
# items move on screen during the drag, and the model is committed once on
# mouse release.
try:
    import time as _compat_0043
    from PySide6.QtWidgets import QGraphicsItem as _compat_0038
except Exception:
    pass


def _compat_0252(window):
    ids = set()
    try:
        u = window.current_unit
        ids.add(id(u.body))
        ids.update(id(p) for p in getattr(u, 'pins', []) or [])
        ids.update(id(t) for t in getattr(u, 'texts', []) or [])
        ids.update(id(g) for g in getattr(u, 'graphics', []) or [])
        ids.update(id(t) for t in (getattr(u.body, 'attribute_texts', {}) or {}).values())
    except Exception:
        pass
    return ids


def _compat_0230(body_item):
    out = []
    try:
        win = body_item.window
        wanted = _compat_0252(win)
        for it in list(body_item.scene().items()):
            m = getattr(it, 'model', None)
            if m is not None and id(m) in wanted:
                out.append({'item': it, 'model': m, 'pos': it.pos(), 'selected': it.isSelected()})
    except Exception:
        pass
    return out


def _compat_0232(body_item, event):
    try:
        if _rotation_handle(body_item.rect(), body_item.window.grid_px * body_item.rotate_handle_factor).contains(event.pos()):
            return True
        if _hit_handle(body_item._handles(), event.pos()):
            return True
    except Exception:
        pass
    return False


def _compat_0248(win, active: bool):
    for name in ('_fast_drag_active', '_group_drag_visual_only', '_suspend_heavy_canvas_sync'):
        try:
            setattr(win, name, bool(active))
        except Exception:
            pass
    try:
        if hasattr(win, 'view'):
            # A fast update mode is enough while dragging; the scene is synced on release.
            from PySide6.QtWidgets import QGraphicsView as _View
            win.view.setViewportUpdateMode(_View.BoundingRectViewportUpdate if active else _View.SmartViewportUpdate)
            from PySide6.QtGui import QPainter as _Painter
            win.view.setRenderHint(_Painter.Antialiasing, not active)
    except Exception:
        pass


try:
    _compat_0236 = BodyItem.mousePressEvent
    _compat_0235 = BodyItem.mouseMoveEvent
    _compat_0237 = BodyItem.mouseReleaseEvent

    def _compat_0227(self, event):
        try:
            if (event.button() == Qt.LeftButton and self.isSelected()
                    and not _compat_0232(self, event)
                    and not getattr(self.window, 'is_template_editor', False)):
                # BODY drag moves the complete current unit as one symbol, but only
                # commits to the model once on mouse release.
                try:
                    self.window.push_undo_state()
                except Exception:
                    pass
                self._compat_0221 = True
                self._compat_0225 = QPointF(event.scenePos())
                self._compat_0222 = QPointF(0, 0)
                self._compat_0223 = 0.0
                self._compat_0224 = _compat_0230(self)
                _compat_0248(self.window, True)
                try:
                    self.scene().blockSignals(True)
                except Exception:
                    pass
                event.accept()
                return
        except Exception:
            pass
        return _compat_0236(self, event)

    def _compat_0226(self, event):
        if getattr(self, '_compat_0221', False):
            try:
                delta = event.scenePos() - self._compat_0225
                now = _compat_0043.monotonic()
                last = getattr(self, '_compat_0223', 0.0) or 0.0
                last_delta = getattr(self, '_compat_0222', QPointF(0, 0))
                # Throttle preview updates to about 60 FPS and ignore tiny motion.
                if (now - last) >= 0.014 or abs(delta.x() - last_delta.x()) + abs(delta.y() - last_delta.y()) >= 8:
                    self._compat_0223 = now
                    self._compat_0222 = QPointF(delta)
                    try:
                        self.window._group_drag_visual_only = True
                        for rec in getattr(self, '_compat_0224', []) or []:
                            try:
                                rec['item'].setPos(rec['pos'] + delta)
                            except Exception:
                                pass
                    finally:
                        self.window._group_drag_visual_only = True
                    try:
                        self.window.view.viewport().update()
                    except Exception:
                        pass
                event.accept()
                return
            except Exception:
                event.accept(); return
        return _compat_0235(self, event)

    def _compat_0228(self, event):
        if getattr(self, '_compat_0221', False):
            records = list(getattr(self, '_compat_0224', []) or [])
            try:
                delta = event.scenePos() - getattr(self, '_compat_0225', QPointF(event.scenePos()))
                g = float(getattr(self.window, 'grid_px', 1.0) or 1.0)
                dxg = delta.x() / g
                dyg = -delta.y() / g
                # Reset preview positions first; then commit the model once.
                try:
                    self.window._group_drag_visual_only = True
                    for rec in records:
                        try:
                            rec['item'].setPos(rec['pos'])
                        except Exception:
                            pass
                finally:
                    pass
                try:
                    if hasattr(self.window, '_invalidate_body_group_transform_cache'):
                        self.window._invalidate_body_group_transform_cache(self.window.current_unit)
                except Exception:
                    pass
                try:
                    if hasattr(self.window, '_shift_current_unit_all'):
                        self.window._shift_current_unit_all(dxg, dyg)
                    else:
                        self.model.x += dxg; self.model.y += dyg
                        self.window.move_current_unit_group(dxg, dyg, source_body=self.model)
                except Exception:
                    self.model.x += dxg; self.model.y += dyg
                wanted = {id(rec.get('model')) for rec in records if rec.get('model') is not None and rec.get('selected')}
                self.window._selection_restore_ids = wanted
            finally:
                self._compat_0221 = False
                self._compat_0224 = []
                try:
                    self.scene().blockSignals(False)
                except Exception:
                    pass
                _compat_0248(self.window, False)
                try:
                    self.window.update_current_unit_canvas_positions()
                    for it in self.scene().items():
                        m = getattr(it, 'model', None)
                        if m is not None and id(m) in wanted:
                            it.setSelected(True)
                    self.window.schedule_property_refresh()
                    self.scene().update()
                    self.window.view.viewport().update()
                except Exception:
                    pass
            event.accept()
            return
        return _compat_0237(self, event)

    BodyItem.mousePressEvent = _compat_0227
    BodyItem.mouseMoveEvent = _compat_0226
    BodyItem.mouseReleaseEvent = _compat_0228
except Exception:
    pass

# -----------------------------------------------------------------------------
# Liebherr v122: coherent high-performance BODY drag
# -----------------------------------------------------------------------------
# The v121 preview path moved canvas items visually and committed the model once
# on release.  That was fast, but for large symbols with BODY-bound text/pins/
# graphics it could visually desynchronise during the drag.  This replacement
# keeps the BODY group coherent: the complete current unit is translated in the
# model in throttled edit-grid increments, and the canvas items are refreshed from
# that single model state.  Heavy side panels stay suspended until mouse release.
try:
    import time as _compat_0044
except Exception:
    _compat_0044 = None

try:
    _compat_0263 = BodyItem.mousePressEvent
    _compat_0262 = BodyItem.mouseMoveEvent
    _compat_0264 = BodyItem.mouseReleaseEvent
except Exception:
    _compat_0263 = _compat_0262 = _compat_0264 = None


def _compat_0261(body_item, event):
    try:
        if _rotation_handle(body_item.rect(), body_item.window.grid_px * body_item.rotate_handle_factor).contains(event.pos()):
            return True
        if _hit_handle(body_item._handles(), event.pos()):
            return True
    except Exception:
        pass
    return False


def _compat_0265(win, active: bool):
    for name in ('_fast_drag_active', '_suspend_heavy_canvas_sync'):
        try:
            setattr(win, name, bool(active))
        except Exception:
            pass
    # Do not set _group_drag_visual_only here: this path intentionally updates
    # the model coherently.  Heavy UI sync is suspended by the two flags above.
    try:
        if hasattr(win, 'view'):
            from PySide6.QtWidgets import QGraphicsView as _View
            from PySide6.QtGui import QPainter as _Painter
            win.view.setViewportUpdateMode(_View.BoundingRectViewportUpdate if active else _View.SmartViewportUpdate)
            win.view.setRenderHint(_Painter.Antialiasing, not active)
    except Exception:
        pass


def _compat_0267(win, dxg, dyg):
    try:
        step = float(win._edit_grid_step() if hasattr(win, '_edit_grid_step') else 1.0) or 1.0
    except Exception:
        step = 1.0
    try:
        return (round(float(dxg) / step) * step, round(float(dyg) / step) * step)
    except Exception:
        return (float(dxg), float(dyg))


def _compat_0266(win, dxg, dyg):
    """Translate the complete visible/current unit as one logical symbol."""
    try:
        if hasattr(win, '_invalidate_body_group_transform_cache'):
            win._invalidate_body_group_transform_cache(win.current_unit)
    except Exception:
        pass
    try:
        if hasattr(win, '_shift_current_unit_all'):
            win._shift_current_unit_all(dxg, dyg)
        else:
            win.current_unit.body.x += dxg
            win.current_unit.body.y += dyg
            win.move_current_unit_group(dxg, dyg, source_body=win.current_unit.body)
    except Exception:
        try:
            win.current_unit.body.x += dxg
            win.current_unit.body.y += dyg
        except Exception:
            pass


def _compat_0259(self, event):
    try:
        if (event.button() == Qt.LeftButton and self.isSelected()
                and not _compat_0261(self, event)
                and not getattr(self.window, 'is_template_editor', False)):
            try:
                self.window.push_undo_state()
            except Exception:
                pass
            self._compat_0253 = True
            self._compat_0257 = QPointF(event.scenePos())
            self._compat_0254 = (0.0, 0.0)
            self._compat_0255 = 0.0
            self._compat_0256 = {
                id(getattr(i, 'model', None)) for i in self.scene().selectedItems()
                if getattr(i, 'model', None) is not None
            }
            _compat_0265(self.window, True)
            try:
                self.scene().blockSignals(True)
            except Exception:
                pass
            event.accept()
            return
    except Exception:
        pass
    if _compat_0263 is not None:
        return _compat_0263(self, event)
    return QGraphicsRectItem.mousePressEvent(self, event)


def _compat_0258(self, event):
    if getattr(self, '_compat_0253', False):
        try:
            g = float(getattr(self.window, 'grid_px', 1.0) or 1.0)
            scene_delta = event.scenePos() - getattr(self, '_compat_0257', QPointF(event.scenePos()))
            target_dxg, target_dyg = _compat_0267(self.window, scene_delta.x() / g, -scene_delta.y() / g)
            last_dxg, last_dyg = getattr(self, '_compat_0254', (0.0, 0.0))
            inc_dxg, inc_dyg = target_dxg - last_dxg, target_dyg - last_dyg
            now = _compat_0044.monotonic() if _compat_0044 is not None else 0.0
            last_t = getattr(self, '_compat_0255', 0.0) or 0.0
            # Coherent model refresh is more expensive than pure preview, so limit
            # it to about 30 fps, but always process meaningful grid movement.
            moved = abs(inc_dxg) > 1e-12 or abs(inc_dyg) > 1e-12
            if moved and ((now - last_t) >= 0.030 or abs(inc_dxg) + abs(inc_dyg) >= 0.5):
                self._compat_0255 = now
                self._compat_0254 = (target_dxg, target_dyg)
                _compat_0266(self.window, inc_dxg, inc_dyg)
                try:
                    self.window.update_current_unit_canvas_positions()
                except Exception:
                    pass
                try:
                    self.scene().update()
                    self.window.view.viewport().update()
                except Exception:
                    pass
            event.accept()
            return
        except Exception:
            event.accept()
            return
    if _compat_0262 is not None:
        return _compat_0262(self, event)
    return QGraphicsRectItem.mouseMoveEvent(self, event)


def _compat_0260(self, event):
    if getattr(self, '_compat_0253', False):
        try:
            # Apply any final unprocessed snap delta once.
            g = float(getattr(self.window, 'grid_px', 1.0) or 1.0)
            scene_delta = event.scenePos() - getattr(self, '_compat_0257', QPointF(event.scenePos()))
            target_dxg, target_dyg = _compat_0267(self.window, scene_delta.x() / g, -scene_delta.y() / g)
            last_dxg, last_dyg = getattr(self, '_compat_0254', (0.0, 0.0))
            inc_dxg, inc_dyg = target_dxg - last_dxg, target_dyg - last_dyg
            if abs(inc_dxg) > 1e-12 or abs(inc_dyg) > 1e-12:
                _compat_0266(self.window, inc_dxg, inc_dyg)
            self.window._selection_restore_ids = set(getattr(self, '_compat_0256', set()) or {id(self.model)})
        finally:
            self._compat_0253 = False
            self._compat_0257 = None
            self._compat_0254 = (0.0, 0.0)
            try:
                self.scene().blockSignals(False)
            except Exception:
                pass
            _compat_0265(self.window, False)
            try:
                self.window.update_current_unit_canvas_positions()
                # Restore selection without forcing individual sync during drag.
                wanted = set(getattr(self.window, '_selection_restore_ids', set()) or [])
                for it in self.scene().items():
                    m = getattr(it, 'model', None)
                    if m is not None and id(m) in wanted:
                        it.setSelected(True)
                self.window.schedule_property_refresh()
                self.scene().update()
                self.window.view.viewport().update()
            except Exception:
                pass
        event.accept()
        return
    if _compat_0264 is not None:
        return _compat_0264(self, event)
    return QGraphicsRectItem.mouseReleaseEvent(self, event)

try:
    BodyItem.mousePressEvent = _compat_0259
    BodyItem.mouseMoveEvent = _compat_0258
    BodyItem.mouseReleaseEvent = _compat_0260
except Exception:
    pass

# -----------------------------------------------------------------------------
# Liebherr v123: coherent fast BODY drag via temporary scene group
# -----------------------------------------------------------------------------
# v122 kept BODY-bound objects coherent by updating the model during mouseMove.
# That is correct but still too expensive for large split parts.  This final
# interaction layer uses a temporary QGraphicsItemGroup during BODY drag:
#   - the whole visible current unit is moved by one scene group only,
#   - no model/property/tree/pin-table updates happen during mouseMove,
#   - on mouseRelease the group is restored and exactly one model translation is
#     committed through the existing _shift_current_unit_all() path.
# This keeps pins, attributes, texts and graphics visually attached to BODY while
# preserving the existing model semantics.
try:
    import time as _compat_0047
    from PySide6.QtWidgets import QGraphicsView as _compat_0045
    from PySide6.QtGui import QPainter as _compat_0046
except Exception:
    _compat_0047 = None

try:
    _compat_0284 = BodyItem.mousePressEvent
    _compat_0283 = BodyItem.mouseMoveEvent
    _compat_0285 = BodyItem.mouseReleaseEvent
except Exception:
    _compat_0284 = _compat_0283 = _compat_0285 = None


def _compat_0282(body_item, event):
    try:
        if _rotation_handle(body_item.rect(), body_item.window.grid_px * body_item.rotate_handle_factor).contains(event.pos()):
            return True
        if _hit_handle(body_item._handles(), event.pos()):
            return True
    except Exception:
        pass
    return False


def _compat_0288(body_item):
    records = []
    try:
        win = body_item.window
        u = win.current_unit
        wanted = {id(getattr(u, 'body', None))}
        wanted.update(id(p) for p in getattr(u, 'pins', []) or [])
        wanted.update(id(t) for t in getattr(u, 'texts', []) or [])
        wanted.update(id(g) for g in getattr(u, 'graphics', []) or [])
        wanted.update(id(t) for t in (getattr(getattr(u, 'body', None), 'attribute_texts', {}) or {}).values())
        for it in list(body_item.scene().items()):
            m = getattr(it, 'model', None)
            if m is not None and id(m) in wanted:
                # Only group top-level visual items.  Child items follow their
                # parent automatically and must not be added separately.
                try:
                    if it.parentItem() is not None:
                        continue
                except Exception:
                    pass
                records.append({'item': it, 'model': m, 'pos': QPointF(it.pos()), 'selected': bool(it.isSelected())})
    except Exception:
        pass
    # Stable z/order is not critical for dragging, but adding BODY first helps
    # keep the mouse grabber predictable.
    try:
        records.sort(key=lambda r: 0 if r.get('item') is body_item else 1)
    except Exception:
        pass
    return records


def _compat_0286(win, active: bool):
    try:
        win._fast_drag_active = bool(active)
        win._group_drag_visual_only = bool(active)
        win._suspend_heavy_canvas_sync = bool(active)
        win._defer_property_refresh = bool(active)
    except Exception:
        pass
    try:
        view = getattr(win, 'view', None)
        if view is not None:
            view.setViewportUpdateMode(_compat_0045.BoundingRectViewportUpdate if active else _compat_0045.SmartViewportUpdate)
            view.setRenderHint(_compat_0046.Antialiasing, not active)
    except Exception:
        pass


def _compat_0287(win, scene_delta):
    try:
        g = float(getattr(win, 'grid_px', 1.0) or 1.0)
    except Exception:
        g = 1.0
    try:
        step = float(win._edit_grid_step() if hasattr(win, '_edit_grid_step') else 1.0) or 1.0
    except Exception:
        step = 1.0
    try:
        dxg = round((float(scene_delta.x()) / g) / step) * step
        dyg = round((-float(scene_delta.y()) / g) / step) * step
        return QPointF(dxg * g, -dyg * g), dxg, dyg
    except Exception:
        return QPointF(scene_delta), float(scene_delta.x()) / g, -float(scene_delta.y()) / g


def _compat_0268(body_item, event):
    try:
        scene = body_item.scene()
        win = body_item.window
        records = _compat_0288(body_item)
        if not scene or not win or not records:
            return False
        try:
            win.push_undo_state()
        except Exception:
            pass
        selected_ids = {id(r['model']) for r in records if r.get('selected') and r.get('model') is not None}
        if not selected_ids:
            selected_ids = {id(body_item.model)}
        items = [r['item'] for r in records]
        # Temporarily suppress itemChange/model update hooks while creating and
        # moving the group.  This is the essential performance win.
        _compat_0286(win, True)
        try:
            scene.blockSignals(True)
        except Exception:
            pass
        group = scene.createItemGroup(items)
        group.setFlag(QGraphicsItem.ItemIsSelectable, False)
        group.setFlag(QGraphicsItem.ItemIsMovable, False)
        group.setZValue(10000)
        body_item._compat_0269 = True
        body_item._compat_0270 = group
        body_item._compat_0275 = records
        body_item._compat_0277 = QPointF(event.scenePos())
        body_item._compat_0271 = QPointF(group.pos())
        body_item._compat_0273 = QPointF(0, 0)
        body_item._compat_0272 = (0.0, 0.0)
        body_item._compat_0274 = 0.0
        body_item._compat_0276 = selected_ids
        event.accept()
        return True
    except Exception:
        try:
            _compat_0286(body_item.window, False)
        except Exception:
            pass
        return False


def _compat_0279(self, event):
    try:
        if (event.button() == Qt.LeftButton and self.isSelected()
                and not _compat_0282(self, event)
                and not getattr(self.window, 'is_template_editor', False)):
            if _compat_0268(self, event):
                return
    except Exception:
        pass
    if _compat_0284 is not None:
        return _compat_0284(self, event)
    return QGraphicsRectItem.mousePressEvent(self, event)


def _compat_0278(self, event):
    if getattr(self, '_compat_0269', False):
        try:
            group = getattr(self, '_compat_0270', None)
            if group is None:
                event.accept(); return
            raw_delta = event.scenePos() - getattr(self, '_compat_0277', QPointF(event.scenePos()))
            scene_delta, dxg, dyg = _compat_0287(self.window, raw_delta)
            now = _compat_0047.monotonic() if _compat_0047 is not None else 0.0
            last_t = getattr(self, '_compat_0274', 0.0) or 0.0
            last_delta = getattr(self, '_compat_0273', QPointF(0, 0))
            # Move one group only.  Allow a low frame rate on massive symbols,
            # but never skip visible grid-step changes.
            changed = abs(scene_delta.x() - last_delta.x()) + abs(scene_delta.y() - last_delta.y()) > 0.5
            if changed and ((now - last_t) >= 0.016 or abs(scene_delta.x() - last_delta.x()) + abs(scene_delta.y() - last_delta.y()) >= 12):
                self._compat_0274 = now
                self._compat_0273 = QPointF(scene_delta)
                self._compat_0272 = (dxg, dyg)
                group.setPos(getattr(self, '_compat_0271', QPointF(0, 0)) + scene_delta)
                try:
                    self.window.view.viewport().update()
                except Exception:
                    pass
            event.accept()
            return
        except Exception:
            event.accept(); return
    if _compat_0283 is not None:
        return _compat_0283(self, event)
    return QGraphicsRectItem.mouseMoveEvent(self, event)


def _compat_0281(self, event=None, cancel=False):
    group = getattr(self, '_compat_0270', None)
    records = list(getattr(self, '_compat_0275', []) or [])
    win = getattr(self, 'window', None)
    scene = self.scene()
    dxg = dyg = 0.0
    try:
        if not cancel and event is not None:
            raw_delta = event.scenePos() - getattr(self, '_compat_0277', QPointF(event.scenePos()))
            _scene_delta, dxg, dyg = _compat_0287(win, raw_delta)
        elif not cancel:
            dxg, dyg = getattr(self, '_compat_0272', (0.0, 0.0))
        # Reset preview group to its original scene transform before ungrouping;
        # the real movement is committed to the model below exactly once.
        if group is not None:
            try:
                group.setPos(getattr(self, '_compat_0271', QPointF(0, 0)))
            except Exception:
                pass
            try:
                scene.destroyItemGroup(group)
            except Exception:
                pass
        if not cancel and (abs(dxg) > 1e-12 or abs(dyg) > 1e-12):
            try:
                if hasattr(win, '_invalidate_body_group_transform_cache'):
                    win._invalidate_body_group_transform_cache(win.current_unit)
            except Exception:
                pass
            try:
                if hasattr(win, '_shift_current_unit_all'):
                    win._shift_current_unit_all(dxg, dyg)
                else:
                    win.current_unit.body.x += dxg
                    win.current_unit.body.y += dyg
                    win.move_current_unit_group(dxg, dyg, source_body=win.current_unit.body)
            except Exception:
                try:
                    win.current_unit.body.x += dxg
                    win.current_unit.body.y += dyg
                except Exception:
                    pass
        try:
            win._selection_restore_ids = set()
        except Exception:
            pass
    finally:
        try:
            if '_compat_0303' in globals():
                _compat_0303(self)
        except Exception:
            pass
        self._compat_0269 = False
        self._compat_0270 = None
        self._compat_0275 = []
        try:
            scene.blockSignals(False)
        except Exception:
            pass
        try:
            _compat_0286(win, False)
        except Exception:
            pass
        try:
            # Rebuild once from the committed model after BODY group-preview
            # drag.  This restores BODY-owned attributes and clears stale Qt
            # selection/group state left by QGraphicsItemGroup.  Use an impossible
            # id sentinel first because rebuild_scene() falls back to the current
            # scene selection when the restore-id set is empty.
            body_model = getattr(self, 'model', None)
            win._selection_restore_ids = {-1}
            win.rebuild_scene()
            try:
                for it in list(win.scene.items()):
                    if getattr(it, 'data', lambda *_: None)(0) == 'BODY' and getattr(it, 'model', None) is body_model:
                        it.setSelected(True)
                    else:
                        try:
                            it.setSelected(False)
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                win._selection_restore_ids = set()
            except Exception:
                pass
            try:
                win._compat_0410 = None
            except Exception:
                pass
            try:
                win.refresh_properties()
            except Exception:
                pass
            scene.update()
            win.view.viewport().update()
        except Exception:
            pass


def _compat_0280(self, event):
    if getattr(self, '_compat_0269', False):
        _compat_0281(self, event, cancel=False)
        event.accept()
        return
    if _compat_0285 is not None:
        return _compat_0285(self, event)
    return QGraphicsRectItem.mouseReleaseEvent(self, event)

try:
    BodyItem.mousePressEvent = _compat_0279
    BodyItem.mouseMoveEvent = _compat_0278
    BodyItem.mouseReleaseEvent = _compat_0280
except Exception:
    pass

# -----------------------------------------------------------------------------
# Liebherr v124: restore auto-scroll for BODY group-preview drag
# -----------------------------------------------------------------------------
# The v123 QGraphicsItemGroup preview keeps large BODY drags coherent and fast,
# but the view no longer scrolled at the viewport edge.  This layer keeps the
# same group-preview model and adds edge-scroll plus timer-driven drag updates.
try:
    from PySide6.QtCore import QTimer as _compat_0050, QPointF as _compat_0049
    from PySide6.QtGui import QCursor as _compat_0048
except Exception:
    _compat_0050 = None


def _compat_0289(body_item):
    try:
        view = getattr(getattr(body_item, 'window', None), 'view', None)
        if view is None:
            return None
        vp = view.viewport().mapFromGlobal(_compat_0048.pos())
        return view.mapToScene(vp)
    except Exception:
        return None


def _compat_0305(body_item, scene_pos=None):
    try:
        if not getattr(body_item, '_compat_0269', False):
            return False
        group = getattr(body_item, '_compat_0270', None)
        if group is None:
            return False
        if scene_pos is None:
            scene_pos = _compat_0289(body_item)
        if scene_pos is None:
            return False
        raw_delta = scene_pos - getattr(body_item, '_compat_0277', _compat_0049(scene_pos))
        scene_delta, dxg, dyg = _compat_0287(body_item.window, raw_delta)
        last_delta = getattr(body_item, '_compat_0273', _compat_0049(0, 0))
        changed = abs(scene_delta.x() - last_delta.x()) + abs(scene_delta.y() - last_delta.y()) > 0.25
        if changed:
            body_item._compat_0273 = _compat_0049(scene_delta)
            body_item._compat_0272 = (dxg, dyg)
            group.setPos(getattr(body_item, '_compat_0271', _compat_0049(0, 0)) + scene_delta)
            try:
                body_item.window.view.viewport().update()
            except Exception:
                pass
        return changed
    except Exception:
        return False


def _compat_0295(body_item, pos=None):
    try:
        if not getattr(body_item, '_compat_0269', False):
            return False
        view = getattr(getattr(body_item, 'window', None), 'view', None)
        if view is None:
            return False
        if pos is None:
            pos = view.viewport().mapFromGlobal(_compat_0048.pos())
        vp = view.viewport().rect()
        edge = 48
        max_step = 7
        dx = dy = 0
        if pos.x() < vp.left() + edge:
            dx = -max(1, int((vp.left() + edge - pos.x()) / edge * max_step))
        elif pos.x() > vp.right() - edge:
            dx = max(1, int((pos.x() - (vp.right() - edge)) / edge * max_step))
        if pos.y() < vp.top() + edge:
            dy = -max(1, int((vp.top() + edge - pos.y()) / edge * max_step))
        elif pos.y() > vp.bottom() - edge:
            dy = max(1, int((pos.y() - (vp.bottom() - edge)) / edge * max_step))
        changed = False
        if dx:
            bar = view.horizontalScrollBar(); old = bar.value(); bar.setValue(old + dx); changed = changed or (bar.value() != old)
        if dy:
            bar = view.verticalScrollBar(); old = bar.value(); bar.setValue(old + dy); changed = changed or (bar.value() != old)
        if changed:
            _compat_0305(body_item)
            try:
                view.viewport().update()
            except Exception:
                pass
        return changed
    except Exception:
        return False


def _compat_0302(body_item):
    try:
        if _compat_0050 is None:
            return
        timer = getattr(body_item, '_compat_0294', None)
        if timer is None:
            parent = getattr(getattr(body_item, 'window', None), 'view', None)
            timer = _compat_0050(parent)
            timer.setInterval(16)
            timer.timeout.connect(lambda bi=body_item: _compat_0290(bi))
            body_item._compat_0294 = timer
        if not timer.isActive():
            timer.start()
    except Exception:
        pass


def _compat_0303(body_item):
    try:
        timer = getattr(body_item, '_compat_0294', None)
        if timer is not None and timer.isActive():
            timer.stop()
        if timer is not None:
            try:
                timer.timeout.disconnect()
            except Exception:
                pass
            try:
                timer.deleteLater()
            except Exception:
                pass
        body_item._compat_0294 = None
    except Exception:
        pass


def _compat_0296(body_item):
    try:
        if not getattr(body_item, '_compat_0269', False):
            return False
        if QApplication.mouseButtons() & Qt.LeftButton:
            return False
        _compat_0305(body_item)
        _compat_0303(body_item)
        _compat_0281(body_item, event=None, cancel=False)
        return True
    except Exception:
        return False


def _compat_0290(body_item):
    if _compat_0296(body_item):
        return
    _compat_0305(body_item)
    _compat_0295(body_item)

try:
    _compat_0298 = BodyItem.mousePressEvent
    _compat_0297 = BodyItem.mouseMoveEvent
    _compat_0299 = BodyItem.mouseReleaseEvent

    def _compat_0292(self, event):
        ret = _compat_0298(self, event)
        try:
            if getattr(self, '_compat_0269', False):
                _compat_0302(self)
        except Exception:
            pass
        return ret

    def _compat_0291(self, event):
        if getattr(self, '_compat_0269', False):
            try:
                _compat_0305(self, event.scenePos())
                view = getattr(self.window, 'view', None)
                if view is not None:
                    _compat_0295(self, view.mapFromScene(event.scenePos()).toPoint())
                event.accept()
                return
            except Exception:
                pass
        return _compat_0297(self, event)

    def _compat_0293(self, event):
        try:
            _compat_0303(self)
        except Exception:
            pass
        return _compat_0299(self, event)

    BodyItem.mousePressEvent = _compat_0292
    BodyItem.mouseMoveEvent = _compat_0291
    BodyItem.mouseReleaseEvent = _compat_0293
except Exception:
    pass

# -----------------------------------------------------------------------------
# Liebherr v126: smaller graphic edit markers for fine template geometry
# -----------------------------------------------------------------------------
# Graphic handles used to be sized in fixed scene/grid units, so they became
# visually huge when editing small Mentor-native details at high zoom.  Keep BODY,
# PIN and TEXT handles as-is, but make GRAPHIC handles roughly screen-sized.

def _compat_0891(item):
    try:
        view = getattr(getattr(item, 'window', None), 'view', None)
        if view is None:
            return 1.0
        tr = view.transform()
        return max(0.001, abs(float(tr.m11())), abs(float(tr.m22())))
    except Exception:
        return 1.0


def _compat_0889(item):
    try:
        scale = _compat_0891(item)
        desired = 6.0 / scale
        minimum = 3.0 / scale
        grid_cap = max(0.2, float(getattr(getattr(item, 'window', None), 'grid_px', 9.6)) * 0.18)
        return max(minimum, min(desired, grid_cap))
    except Exception:
        try:
            return float(item.window.grid_px) * 0.12
        except Exception:
            return 2.0


def _compat_0890(self):
    g = self.window.grid_px
    s = _compat_0889(self)
    if str(getattr(self.model, 'shape', '') or '') == 'line':
        return {
            'start': QRectF(-s / 2, -s / 2, s, s),
            'end': QRectF(self.model.w * g - s / 2, self.model.h * g - s / 2, s, s),
            'curve': QRectF(
                self.model.w * g / 2 - s / 2,
                self.model.h * g / 2 - float(getattr(self.model, 'curve_radius', 0.0)) * g - s / 2,
                s,
                s,
            ),
        }
    return _corner_handles(self._rect(), s)


try:
    GraphicItem.handle_size_factor = 0.10
    GraphicItem.rotate_handle_factor = 0.06
    GraphicItem._handles = _compat_0890
except Exception:
    pass

# ---------------------------------------------------------------------------
# Canonical editor snapping for graphics and locked template primitives.
# ---------------------------------------------------------------------------
try:
    _canonical_previous_item_change_for_snap = TransformMixin.itemChange
except Exception:
    _canonical_previous_item_change_for_snap = None


def _canonical_window_snap_enabled(window):
    try:
        snap_box = getattr(window, 'template_snap_check', None)
        if snap_box is not None:
            return bool(snap_box.isChecked())
    except Exception:
        pass
    return True


def _canonical_edit_grid_px(window, scene=None):
    for name in ('edit_grid_px', 'pin_grid_px', 'grid_px'):
        try:
            value = float(getattr(window, name, 0.0) or 0.0)
            if value > 1e-9:
                return value
        except Exception:
            pass
    try:
        return float(getattr(scene, 'grid_px', 1.0) or 1.0)
    except Exception:
        return 1.0


def _canonical_edit_grid_step(window):
    try:
        fn = getattr(window, '_edit_grid_step', None)
        if callable(fn):
            value = float(fn() or 0.0)
            if value > 1e-9:
                return value
    except Exception:
        pass
    for name in ('edit_grid_inch', 'grid_inch'):
        try:
            value = float(getattr(window, name, 0.0) or 0.0)
            if value > 1e-9:
                return value
        except Exception:
            pass
    return 0.1


def _canonical_snap_grid_value(window, value):
    try:
        fn = getattr(window, 'snap_grid_value', None)
        if callable(fn):
            return float(fn(float(value)))
    except Exception:
        pass
    try:
        step = _canonical_edit_grid_step(window)
        return round(float(value) / step) * step
    except Exception:
        return float(value)


def _canonical_snap_graphic_dimension(window, value):
    try:
        step = max(0.001, _canonical_edit_grid_step(window))
        sign = -1.0 if float(value or 0.0) < 0.0 else 1.0
        mag = abs(float(value or 0.0))
        snapped = round(mag / step) * step
        if snapped < step:
            snapped = step
        return sign * snapped
    except Exception:
        return value


def _canonical_snap_item_change(self, change, value):
    try:
        scene = self.scene()
        window = getattr(scene, 'window', None) if scene is not None else None
        if window is not None and getattr(window, '_group_drag_visual_only', False):
            if change in (QGraphicsItem.ItemPositionChange, QGraphicsItem.ItemPositionHasChanged):
                return QGraphicsItem.itemChange(self, change, value)
        if change == QGraphicsItem.ItemPositionChange and scene is not None and window is not None:
            if _canonical_window_snap_enabled(window):
                kind = getattr(self, 'data', lambda *_: None)(0)
                model = getattr(self, 'model', None)
                locked = bool(getattr(model, 'locked_to_body', False))
                # In the Template Editor, imported BODY graphics are editable template
                # primitives and must snap like normal graphics.  In the Symbol Wizard
                # they remain locked to the BODY item and keep the historical bypass.
                should_snap = (not locked) or bool(getattr(window, 'is_template_editor', False)) or kind in ('PIN', 'TEXT', 'GRAPHIC', 'BODY')
                if should_snap:
                    g = _canonical_edit_grid_px(window, scene)
                    value = QPointF(snap(float(value.x()), g), snap(float(value.y()), g))
    except Exception:
        pass
    if _canonical_previous_item_change_for_snap is not None:
        return _canonical_previous_item_change_for_snap(self, change, value)
    return QGraphicsItem.itemChange(self, change, value)

try:
    TransformMixin.itemChange = _canonical_snap_item_change
except Exception:
    pass

try:
    _canonical_previous_graphic_update_model_pos = GraphicItem.update_model_pos
except Exception:
    _canonical_previous_graphic_update_model_pos = None


def _canonical_graphic_update_model_pos(self):
    if getattr(self, '_canonical_snapping_model_pos', False):
        if _canonical_previous_graphic_update_model_pos is not None:
            return _canonical_previous_graphic_update_model_pos(self)
        return None
    result = None
    if _canonical_previous_graphic_update_model_pos is not None:
        result = _canonical_previous_graphic_update_model_pos(self)
    try:
        window = getattr(self, 'window', None)
        if window is not None and _canonical_window_snap_enabled(window):
            model = getattr(self, 'model', None)
            if model is not None:
                x0 = float(getattr(model, 'x', 0.0) or 0.0)
                y0 = float(getattr(model, 'y', 0.0) or 0.0)
                x1 = _canonical_snap_grid_value(window, x0)
                y1 = _canonical_snap_grid_value(window, y0)
                if abs(x1 - x0) > 1e-9 or abs(y1 - y0) > 1e-9:
                    model.x = x1
                    model.y = y1
                    try:
                        self._canonical_snapping_model_pos = True
                        g = float(getattr(window, 'grid_px', 1.0) or 1.0)
                        self.setPos(x1 * g, -y1 * g)
                    finally:
                        self._canonical_snapping_model_pos = False
    except Exception:
        pass
    return result

try:
    GraphicItem.update_model_pos = _canonical_graphic_update_model_pos
except Exception:
    pass

# -----------------------------------------------------------------------------
# Final Template Editor GRAPHIC position snapping.
# -----------------------------------------------------------------------------
# Imported template BODY graphics are locked to the body in the normal Symbol
# Wizard, but they are directly editable objects inside the Template Editor.  The
# historical locked-to-body guard bypassed TransformMixin.itemChange before the
# edit-grid snap was applied, so dragged rectangles could end up at values such
# as -2.979 instead of the active 0.050" grid.  This final wrapper runs before
# the legacy guard and snaps Template Editor GRAPHIC positions whenever Snap is
# enabled.
try:
    _final_template_graphic_item_change_previous = TransformMixin.itemChange

    def _final_template_graphic_snap_item_change(self, change, value):
        try:
            if change == QGraphicsItem.ItemPositionChange and self.scene() is not None:
                win = getattr(self.scene(), 'window', None)
                if (getattr(win, 'is_template_editor', False)
                        and getattr(self, 'data', lambda *_: None)(0) == 'GRAPHIC'):
                    snap_check = getattr(win, 'template_snap_check', None)
                    snap_enabled = not bool(snap_check is not None and not snap_check.isChecked())
                    if snap_enabled:
                        g = float(getattr(win, 'edit_grid_px', self.scene().grid_px) or self.scene().grid_px)
                        return QPointF(snap(value.x(), g), snap(value.y(), g))
        except Exception:
            pass
        return _final_template_graphic_item_change_previous(self, change, value)

    TransformMixin.itemChange = _final_template_graphic_snap_item_change
except Exception:
    pass


# -----------------------------------------------------------------------------
# Canonical runtime fix: every BODY drag must create an undo snapshot.
# -----------------------------------------------------------------------------
# Some earlier BODY mousePress implementations saved undo only when the item was
# already selected before the click.  A click-drag that first selected the BODY
# and then moved it could therefore mutate the model without a history entry.
# Keep the existing final handler, but add one post-handler safeguard: if no undo
# snapshot was pushed by the handler, push one before Qt starts the drag move.
try:
    _canonical_body_mouse_press_before_undo = BodyItem.mousePressEvent

    def _canonical_body_mouse_press_with_undo(self, event):
        win = getattr(self, 'window', None)
        before = None
        try:
            if win is not None and hasattr(win, 'undo_stack'):
                before = len(win.undo_stack)
        except Exception:
            before = None
        result = _canonical_body_mouse_press_before_undo(self, event)
        try:
            is_left = event.button() == Qt.LeftButton
        except Exception:
            is_left = False
        if is_left and win is not None:
            try:
                after = len(win.undo_stack) if hasattr(win, 'undo_stack') else None
                if (before is not None and after == before
                        and not getattr(win, '_loading_template', False)
                        and not getattr(win, '_restoring_undo_redo', False)
                        and not getattr(self, '_undo_state_pushed_for_drag', False)):
                    win.push_undo_state()
                    self._undo_state_pushed_for_drag = True
            except Exception:
                pass
        return result

    BodyItem.mousePressEvent = _canonical_body_mouse_press_with_undo
except Exception:
    pass
