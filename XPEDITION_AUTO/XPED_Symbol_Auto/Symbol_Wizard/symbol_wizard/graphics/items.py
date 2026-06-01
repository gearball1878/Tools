from __future__ import annotations
import math
from PySide6.QtCore import QPointF, QRectF, Qt, QEvent
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QTransform, QTextCursor, QCursor, QPainterPath, QTextOption, QFontMetricsF, QPainterPathStroker
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem, QApplication
from symbol_wizard.models.document import PinSide, LineStyle
from symbol_wizard.rules.grid import snap


def rgb(c):
    return QColor(*c)


def mentor_pin_color(pin_type):
    return {
        'IN': (0, 80, 220), 'OUT': (220, 0, 0),
        'BIDI': (160, 0, 180), 'BI': (160, 0, 180),
        'POWER': (230, 120, 0), 'GROUND': (0, 150, 0),
        'ANALOG': (0, 150, 170), 'PASSIVE': (0, 0, 0),
    }.get(str(pin_type or '').upper(), (0, 0, 0))

def is_default_black(color):
    try:
        return tuple(color) == (0, 0, 0)
    except Exception:
        return True

def pen_for(color, width_grid, style, grid_px):
    p = QPen(rgb(color), max(1, width_grid * grid_px))
    p.setStyle({
        LineStyle.SOLID.value: Qt.SolidLine,
        LineStyle.DASH.value: Qt.DashLine,
        LineStyle.DOT.value: Qt.DotLine,
        LineStyle.DASH_DOT.value: Qt.DashDotLine,
    }.get(style, Qt.SolidLine))
    return p


class TransformMixin:
    handle_size_factor = .32
    rotate_handle_factor = .32

    def apply_transform_from_model(self):
        def f(name, default):
            try:
                return float(getattr(self.model, name, default) or default)
            except (TypeError, ValueError):
                return default
        sx, sy, rot = f('scale_x', 1.0), f('scale_y', 1.0), f('rotation', 0.0)
        self.model.scale_x, self.model.scale_y, self.model.rotation = sx, sy, rot
        try:
            br = self.boundingRect()
            self.setTransformOriginPoint(br.center())
        except Exception:
            pass
        self.setTransform(QTransform().scale(sx, sy))
        self.setRotation(rot)

    def flip_horizontal(self):
        self.model.scale_x = -float(getattr(self.model, 'scale_x', 1.0) or 1.0)
        self.apply_transform_from_model()
        self.update()

    def flip_vertical(self):
        self.model.scale_y = -float(getattr(self.model, 'scale_y', 1.0) or 1.0)
        self.apply_transform_from_model()
        self.update()

    def common_flags(self):
        self.setAcceptHoverEvents(True)
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
            | QGraphicsItem.ItemIsFocusable
        )

    def itemChange(self, change, value):
        # Imported Mentor BODY primitives are one locked geometric BODY group.
        # They must never be individually grid-snapped by QGraphicsItem while
        # the logical BodyItem moves the group; otherwise lines/arcs drift apart.
        if getattr(getattr(self, 'model', None), 'locked_to_body', False):
            if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
                self.update_model_pos()
            return super().itemChange(change, value)
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            win = self.scene().window
            # In the Template Editor, moving an item directly on the canvas must
            # create an undo snapshot before Qt applies the new position.  Many
            # item classes do not have their own mousePress undo hook, so this
            # central hook covers Body, Pin, Text and Graphic moves consistently.
            try:
                if (getattr(win, 'is_template_editor', False)
                        and not getattr(win, '_loading_template', False)
                        and not getattr(win, '_restoring_undo_redo', False)
                        and (QApplication.mouseButtons() & Qt.LeftButton)
                        and not getattr(self, '_undo_state_pushed_for_drag', False)):
                    win.push_undo_state()
                    self._undo_state_pushed_for_drag = True
            except Exception:
                pass
            snap_enabled = not bool(getattr(win, 'template_snap_check', None) and not win.template_snap_check.isChecked())
            if snap_enabled:
                # Use the active edit grid in the normal Symbol Wizard as well.
                # This keeps copied/pasted pins on the same raster that the user is
                # currently editing with (0.100/0.050/0.025 inch). Locked imported
                # BODY primitives bypass this branch above.
                g = float(getattr(win, 'edit_grid_px', self.scene().grid_px) or self.scene().grid_px)
                return QPointF(snap(value.x(), g), snap(value.y(), g))
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.update_model_pos()
            # Do not rebuild the scene while dragging; this keeps canvas editing smooth.
            try:
                self.scene().window.notify_canvas_model_changed()
            except Exception:
                self.scene().window.live_refresh()
        return super().itemChange(change, value)

    def update_model_pos(self):
        pass

    def rotate_by(self, deg):
        try:
            cur = float(getattr(self.model, 'rotation', 0.0) or 0.0)
        except (TypeError, ValueError):
            cur = 0.0
        self.model.rotation = (round((cur + float(deg)) / 15.0) * 15.0) % 360
        self.apply_transform_from_model()
        self.update()

    def scale_selected(self, factor):
        if hasattr(self.model, 'font_size_grid'):
            self.model.font_size_grid = max(.1, self.model.font_size_grid * factor)
            g = self.scene().grid_px
            self.setFont(QFont(self.model.font_family, max(6, int(g * self.model.font_size_grid * .45))))
        elif hasattr(self.model, 'length'):
            self.model.length = max(.1, self.model.length * factor)
        self.update()

    def scale_by(self, factor):
        """Public toolbar-compatible scale hook for transformable items."""
        return self.scale_selected(factor)


def _corner_handles(rect: QRectF, s: float):
    return {
        'tl': QRectF(rect.left() - s / 2, rect.top() - s / 2, s, s),
        'tr': QRectF(rect.right() - s / 2, rect.top() - s / 2, s, s),
        'bl': QRectF(rect.left() - s / 2, rect.bottom() - s / 2, s, s),
        'br': QRectF(rect.right() - s / 2, rect.bottom() - s / 2, s, s),
        'l': QRectF(rect.left() - s / 2, rect.center().y() - s / 2, s, s),
        'r': QRectF(rect.right() - s / 2, rect.center().y() - s / 2, s, s),
        't': QRectF(rect.center().x() - s / 2, rect.top() - s / 2, s, s),
        'b': QRectF(rect.center().x() - s / 2, rect.bottom() - s / 2, s, s),
    }


def _hit_handle(handles, pos):
    for name, r in handles.items():
        if r.contains(pos):
            return name
    return None

def _cursor_for_handle(name):
    if name in ('l', 'r'):
        return Qt.SizeHorCursor
    if name in ('t', 'b'):
        return Qt.SizeVerCursor
    if name in ('tl', 'br'):
        return Qt.SizeFDiagCursor
    if name in ('tr', 'bl'):
        return Qt.SizeBDiagCursor
    if name == 'rot':
        return Qt.CrossCursor
    return Qt.ArrowCursor

def _rotation_handle(rect: QRectF, s: float):
    return QRectF(rect.center().x() - s / 2, rect.top() - 1.8 * s, s, s)

def _angle_from(center: QPointF, p: QPointF):
    return math.degrees(math.atan2(p.y() - center.y(), p.x() - center.x()))


def _hit_tolerance_px(window, factor: float = 0.26, minimum: float = 10.0) -> float:
    """Comfort hit width for selecting thin canvas objects.

    Painting stays unchanged; only QGraphicsItem.shape() becomes slightly
    larger so pins/lines/text are easier to click on dense grids.
    """
    try:
        return max(float(minimum), float(getattr(window, 'grid_px', 40.0) or 40.0) * float(factor))
    except Exception:
        return float(minimum)


class BodyItem(TransformMixin, QGraphicsRectItem):
    def __init__(self, model, window):
        self.model = model
        self.window = window
        self._resizing = None
        self._rotating = False
        self._resize_anchor_scene = None
        self._resize_start = None
        self._rotating = False
        self._rotate_start_angle = 0.0
        self._rotate_start_model = 0.0
        self._rotate_center_scene = QPointF()
        self._last_model_pos = (model.x, model.y)
        g = window.grid_px
        super().__init__(0, 0, model.width * g, model.height * g)
        self.setPos(model.x * g, -model.y * g)
        self.setPen(pen_for(model.color, model.line_width, model.line_style, g))
        self.setBrush(QBrush(Qt.NoBrush))
        self.common_flags()
        self.setData(0, 'BODY')
        self.apply_transform_from_model()

    def update_model_pos(self):
        g = self.window.grid_px
        old_x, old_y = self._last_model_pos
        self.model.x = self.pos().x() / g
        self.model.y = -self.pos().y() / g
        dx, dy = self.model.x - old_x, self.model.y - old_y
        if abs(dx) > 1e-9 or abs(dy) > 1e-9:
            self.window.move_current_unit_group(dx, dy, source_body=self.model)
            self.window.update_current_unit_canvas_positions()
        self._last_model_pos = (self.model.x, self.model.y)

    def _handles(self):
        return _corner_handles(self.rect(), self.window.grid_px * self.handle_size_factor)

    def paint(self, painter, option, widget=None):
        # Native Mentor imports use imported primitives as visible BODY.  In the
        # Symbol Wizard the body is a non-editable logical anchor, but it should
        # still be visually recognizable.  Therefore draw only a lightweight
        # highlight frame there.  In the Template Editor the body remains fully
        # editable and gets the normal handles.
        graphics_as_body = False
        try:
            attrs = getattr(self.model, 'attributes', {}) or {}
            graphics_as_body = str(attrs.get('MENTOR_GRAPHICS_AS_BODY', '0')) == '1'
        except Exception:
            pass
        if graphics_as_body:
            # Imported/template symbols behave like internally created symbols,
            # but their visible BODY is the imported artwork itself.  Do not draw
            # a proxy rectangle.  When selected, show only lightweight corner /
            # rotation handles so the user sees the BODY selection without
            # mistaking a helper frame for real geometry.
            if self.isSelected():
                painter.save()
                painter.setPen(QPen(QColor(0, 150, 170), 1))
                painter.setBrush(QBrush(QColor(255, 255, 255)))
                for r in self._handles().values():
                    painter.drawRect(r)
                painter.drawEllipse(_rotation_handle(self.rect(), self.window.grid_px * self.rotate_handle_factor))
                painter.restore()
            return
        super().paint(painter, option, widget)
        if self.isSelected():
            painter.save()
            painter.setPen(QPen(QColor(0, 150, 170) if graphics_as_body else QColor(40, 40, 40), 1))
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            for r in self._handles().values():
                painter.drawRect(r)
            painter.drawEllipse(_rotation_handle(self.rect(), self.window.grid_px * self.rotate_handle_factor))
            painter.restore()

    def shape(self):
        path = QPainterPath()
        path.addRect(self.rect())
        stroker = QPainterPathStroker()
        stroker.setWidth(_hit_tolerance_px(self.window, 0.22, 9.0))
        return path.united(stroker.createStroke(path))

    def hoverMoveEvent(self, event):
        if self.isSelected():
            h = 'rot' if _rotation_handle(self.rect(), self.window.grid_px * self.rotate_handle_factor).contains(event.pos()) else _hit_handle(self._handles(), event.pos())
            self.setCursor(QCursor(_cursor_for_handle(h)) if h else QCursor(Qt.ArrowCursor))
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.unsetCursor()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        self._undo_state_pushed_for_drag = False
        if self.isSelected() and event.button() == Qt.LeftButton:
            # Body move/resize/rotate changes multiple attached objects (pins, texts, graphics,
            # body attributes).  Save the state before Qt starts moving the item so Ctrl+Z
            # restores the complete pre-move group state.
            try:
                self.window.push_undo_state()
                self._undo_state_pushed_for_drag = True
            except Exception:
                pass
        if self.isSelected():
            if _rotation_handle(self.rect(), self.window.grid_px * self.rotate_handle_factor).contains(event.pos()):
                self._rotating = True
                self._rotate_center_scene = self.mapToScene(self.boundingRect().center())
                self._rotate_start_angle = _angle_from(self._rotate_center_scene, event.scenePos())
                self._rotate_start_model = float(getattr(self.model, 'rotation', 0.0) or 0.0)
                event.accept(); return
            h = _hit_handle(self._handles(), event.pos())
            if h:
                self._resizing = h
                self._resize_start = {
                    'x': float(self.model.x),
                    'y': float(self.model.y),
                    'w': float(self.model.width),
                    'h': float(self.model.height),
                    'pins': [(p, float(p.x), float(p.y), float(p.length)) for p in self.window.current_unit.pins],
                    'texts': [(t, float(t.x), float(t.y)) for t in self.window.current_unit.texts],
                    'attributes': [(t, float(t.x), float(t.y)) for t in getattr(self.window.current_unit.body, 'attribute_texts', {}).values()],
                    'graphics': [(gr, float(gr.x), float(gr.y), float(gr.w), float(gr.h)) for gr in self.window.current_unit.graphics],
                }
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if getattr(self, '_rotating', False):
            delta = _angle_from(self._rotate_center_scene, event.scenePos()) - self._rotate_start_angle
            target = (round((self._rotate_start_model + delta) / 90.0) * 90.0) % 360
            step = target - float(getattr(self.model, 'rotation', 0.0) or 0.0)
            if abs(step) > 180:
                step -= 360 if step > 0 else -360
            if abs(step) > 1e-9:
                try:
                    self.window._transform_unit_as_body_group('rotate', step, refresh=False)
                    self.window.update_current_unit_canvas_positions()
                except Exception:
                    self.model.rotation = target
                    self.apply_transform_from_model()
            try:
                self.window.notify_canvas_model_changed()
            except Exception:
                self.window.live_refresh()
            event.accept(); return
        if self._resizing and self._resize_start is not None:
            g = self.window.grid_px
            p = QPointF(snap(event.scenePos().x(), self.window.edit_grid_px), snap(event.scenePos().y(), self.window.edit_grid_px))
            st = self._resize_start

            left = st['x'] * g
            top = -st['y'] * g
            right = left + st['w'] * g
            bottom = top + st['h'] * g

            # Edge handles resize exactly one axis. Corner handles resize both axes.
            if self._resizing in ('l', 'tl', 'bl'):
                left = p.x()
            if self._resizing in ('r', 'tr', 'br'):
                right = p.x()
            if self._resizing in ('t', 'tl', 'tr'):
                top = p.y()
            if self._resizing in ('b', 'bl', 'br'):
                bottom = p.y()

            min_size = g
            if right < left:
                left, right = right, left
            if bottom < top:
                top, bottom = bottom, top
            if right - left < min_size:
                if self._resizing in ('l', 'tl', 'bl'):
                    left = right - min_size
                else:
                    right = left + min_size
            if bottom - top < min_size:
                if self._resizing in ('t', 'tl', 'tr'):
                    top = bottom - min_size
                else:
                    bottom = top + min_size

            old = (self.model.x, self.model.y, self.model.width, self.model.height)
            new_x = left / g
            new_y = -top / g
            new_w = (right - left) / g
            new_h = (bottom - top) / g

            self.prepareGeometryChange()
            self.setPos(left, top)
            self.setRect(0, 0, new_w * g, new_h * g)
            self.model.x, self.model.y, self.model.width, self.model.height = new_x, new_y, new_w, new_h
            self._last_model_pos = (new_x, new_y)

            self.window.scale_current_unit_children_from_body_resize(st, self.model)
            self.window.update_current_unit_canvas_positions()
            try:
                self.window.notify_canvas_model_changed()
            except Exception:
                self.window.live_refresh()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._undo_state_pushed_for_drag = False
        self._resizing = None
        self._resize_anchor_scene = None
        self._resize_start = None
        self.window.enforce_symbol_size_limit(silent=True)
        self.window.update_current_unit_canvas_positions()
        self.window.update_attribute_items_for_unit()
        self.window.rebuild_tree()
        self.window.rebuild_pin_table()
        self.scene().update()
        try:
            self.window.refresh_properties()
        except Exception:
            pass
        super().mouseReleaseEvent(event)

    def rotate_by(self, deg):
        try:
            self.window._transform_unit_as_body_group('rotate', deg)
        except Exception:
            super().rotate_by(deg)

    def flip_horizontal(self):
        try:
            self.window._transform_unit_as_body_group('flip_h')
        except Exception:
            super().flip_horizontal()

    def flip_vertical(self):
        try:
            self.window._transform_unit_as_body_group('flip_v')
        except Exception:
            super().flip_vertical()

    def scale_selected(self, factor):
        try:
            self.window._transform_unit_as_body_group('scale', factor)
        except Exception:
            st = {
                'x': float(self.model.x), 'y': float(self.model.y),
                'w': float(self.model.width), 'h': float(self.model.height),
                'pins': [(p, float(p.x), float(p.y), float(p.length)) for p in self.window.current_unit.pins],
                'texts': [(t, float(t.x), float(t.y)) for t in self.window.current_unit.texts],
                'attributes': [(t, float(t.x), float(t.y)) for t in getattr(self.window.current_unit.body, 'attribute_texts', {}).values()],
                'graphics': [(gr, float(gr.x), float(gr.y), float(gr.w), float(gr.h)) for gr in self.window.current_unit.graphics],
            }
            self.model.width = max(1, round(self.model.width * factor))
            self.model.height = max(1, round(self.model.height * factor))
            g = self.window.grid_px
            self.setRect(0, 0, self.model.width * g, self.model.height * g)
            self.window.scale_current_unit_children_from_body_resize(st, self.model)
            self.window.update_current_unit_canvas_positions()
        self.window.update_attribute_items_for_unit()
        try:
            self.window.refresh_properties()
        except Exception:
            pass
        self.update()


class PinItem(TransformMixin, QGraphicsItem):
    def __init__(self, model, window):
        super().__init__()
        self.model = model
        self.window = window
        g = window.grid_px
        self.setPos(model.x * g, -model.y * g)
        self.common_flags()
        self.setData(0, 'PIN')
        self.apply_transform_from_model()

    def boundingRect(self):
        # Keep a generous repaint area for labels/handles, but do not use this
        # rectangle as the mouse hit area.  shape() below is intentionally tight
        # so pins do not block selection of nearby body/text/graphic objects.
        g = self.window.grid_px
        return QRectF(-6 * g, -1.6 * g, 12 * g, 3.2 * g)

    def shape(self):
        g = self.window.grid_px
        L = float(getattr(self.model, 'length', 1.0) or 1.0) * g
        m = self.model
        if m.side == PinSide.LEFT.value:
            p1, p2 = QPointF(-L, 0), QPointF(0, 0)
        elif m.side == PinSide.TOP.value:
            p1, p2 = QPointF(0, -L), QPointF(0, 0)
        elif m.side == PinSide.BOTTOM.value:
            p1, p2 = QPointF(0, L), QPointF(0, 0)
        else:
            p1, p2 = QPointF(0, 0), QPointF(L, 0)
        path = QPainterPath(p1)
        path.lineTo(p2)
        # Comfortable hit boxes for thin pin geometry. Labels are painted by the pin
        # but do not make the pin selection area huge.
        s = max(10.0, 0.34 * g)
        path.addRect(QRectF(p1.x() - s/2, p1.y() - s/2, s, s))
        path.addRect(QRectF(p2.x() - s/2, p2.y() - s/2, s, s))
        if bool(getattr(m, 'inverted', False)):
            r = max(4.0, .20 * g)
            bx = (-r if m.side == PinSide.LEFT.value else (r if m.side == PinSide.RIGHT.value else 0))
            by = (0 if m.side in (PinSide.LEFT.value, PinSide.RIGHT.value) else (-r if m.side == PinSide.TOP.value else r))
            path.addEllipse(QPointF(bx, by), r, r)
        stroker = QPainterPathStroker()
        stroker.setWidth(_hit_tolerance_px(self.window, 0.30, 12.0))
        return stroker.createStroke(path).united(path)

    def paint(self, painter, option, widget=None):
        g, m = self.window.grid_px, self.model
        L = m.length * g
        line_color = m.color
        # Native Mentor/Xpedition symbols usually do not store RGB colors.
        # In the Wizard UI they are colored semantically from PINTYPE while
        # the native .sym export remains colorless/standard Mentor.
        try:
            if getattr(self.window.symbol, 'template_name', '') == 'mentor_native_origin' and is_default_black(line_color):
                line_color = mentor_pin_color(getattr(m, 'pin_type', ''))
        except Exception:
            pass
        painter.setPen(pen_for(line_color, m.line_width, m.line_style, g))
        painter.setBrush(QBrush(Qt.NoBrush))
        if m.side == PinSide.LEFT.value:
            x1, y1, x2, y2 = -L, 0, 0, 0
        elif m.side == PinSide.TOP.value:
            x1, y1, x2, y2 = 0, -L, 0, 0
        elif m.side == PinSide.BOTTOM.value:
            x1, y1, x2, y2 = 0, L, 0, 0
        else:
            x1, y1, x2, y2 = 0, 0, L, 0
        painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        if m.inverted:
            r = .18 * g
            painter.drawEllipse(QPointF((-r if m.side == PinSide.LEFT.value else (r if m.side == PinSide.RIGHT.value else 0)), (0 if m.side in (PinSide.LEFT.value, PinSide.RIGHT.value) else (-r if m.side == PinSide.TOP.value else r))), r, r)
        num_color = getattr(m.number_font, 'color', (0, 0, 0))
        try:
            if getattr(self.window.symbol, 'template_name', '') == 'mentor_native_origin' and is_default_black(num_color):
                num_color = line_color
        except Exception:
            pass
        painter.setPen(pen_for(num_color, m.line_width, m.line_style, g))
        painter.setFont(QFont(m.number_font.family, max(6, int(g * m.number_font.size_grid * .45))))
        def _qt_align(h, v):
            ha = {'left': Qt.AlignLeft, 'center': Qt.AlignHCenter, 'right': Qt.AlignRight}.get(str(h or '').lower(), Qt.AlignHCenter)
            va = {'upper': Qt.AlignTop, 'center': Qt.AlignVCenter, 'lower': Qt.AlignBottom}.get(str(v or '').lower(), Qt.AlignVCenter)
            return ha | va
        def _draw_anchored_text(text, ax, ay, w_grid, h_grid, align, font_model):
            # ax/ay are model-grid coordinates in the symbol coordinate system.
            # Convert to this pin item's local painter coordinates.
            lx = (float(ax) - float(m.x)) * g
            ly = -(float(ay) - float(m.y)) * g
            rect = QRectF(lx - w_grid * g / 2, ly - h_grid * g / 2, w_grid * g, h_grid * g)
            painter.drawText(rect, align, str(text))
        if m.visible_number:
            if getattr(m, 'number_x', None) is not None and getattr(m, 'number_y', None) is not None:
                _draw_anchored_text(m.number, m.number_x, m.number_y, 4.5, 1.1, _qt_align(getattr(m, 'number_h_align', 'center'), getattr(m, 'number_v_align', 'center')), m.number_font)
            else:
                painter.drawText(QRectF(min(x1, x2) - .4*g, min(y1, y2) - .85 * g, max(abs(x2 - x1), .8*g), max(abs(y2-y1), .5*g)), Qt.AlignCenter, m.number)
        # Pin name and pin function are independent display attributes.
        # If Mentor-native label coordinates are present, draw exactly at the imported anchor.
        parts = []
        if m.visible_name and str(m.name or '').strip():
            parts.append(m.name)
        if m.visible_function and str(m.function or '').strip():
            parts.append(m.function)
        label = ' / '.join([x for x in parts if x])
        if label:
            label_color = getattr(m.label_font, 'color', (0, 0, 0))
            try:
                if getattr(self.window.symbol, 'template_name', '') == 'mentor_native_origin' and is_default_black(label_color):
                    label_color = line_color
            except Exception:
                pass
            painter.setPen(pen_for(label_color, m.line_width, m.line_style, g))
            painter.setFont(QFont(m.label_font.family, max(8, int(g * m.label_font.size_grid * .45))))
            if getattr(m, 'label_x', None) is not None and getattr(m, 'label_y', None) is not None:
                _draw_anchored_text(label, m.label_x, m.label_y, 7.5, 1.1, _qt_align(getattr(m, 'label_h_align', 'center'), getattr(m, 'label_v_align', 'center')), m.label_font)
            elif m.side == PinSide.LEFT.value:
                painter.drawText(QRectF(.25 * g, -.35 * g, 6 * g, .7 * g), Qt.AlignVCenter | Qt.AlignLeft, label)
            elif m.side == PinSide.TOP.value:
                painter.drawText(QRectF(-3 * g, .15 * g, 6 * g, .7 * g), Qt.AlignCenter, label)
            elif m.side == PinSide.BOTTOM.value:
                painter.drawText(QRectF(-3 * g, -.85 * g, 6 * g, .7 * g), Qt.AlignCenter, label)
            else:
                painter.drawText(QRectF(-6.25 * g, -.35 * g, 6 * g, .7 * g), Qt.AlignVCenter | Qt.AlignRight, label)
        # Draw imported/custom visible pin attributes as children of the pin.
        # They use absolute symbol anchors converted into this pin item's local
        # coordinate space, so dragging the pin keeps attributes attached.
        for key, tm in (getattr(m, 'attribute_texts', {}) or {}).items():
            try:
                if not (getattr(m, 'visible_attributes', {}) or {}).get(key, False):
                    continue
                text = getattr(tm, 'text', '') or f'{key}: {(getattr(m, 'attributes', {}) or {}).get(key, '')}'
                painter.setPen(pen_for(getattr(tm, 'color', (0, 0, 0)), getattr(m, 'line_width', 0.03), getattr(m, 'line_style', 'solid'), g))
                painter.setFont(QFont(getattr(tm, 'font_family', 'Arial'), max(6, int(g * float(getattr(tm, 'font_size_grid', .45) or .45) * .45))))
                _draw_anchored_text(text, tm.x, tm.y, 8.0, 1.1, _qt_align(getattr(tm, 'h_align', 'left'), getattr(tm, 'v_align', 'center')), getattr(m, 'label_font', None))
            except Exception:
                pass
        if self.isSelected():
            painter.setPen(QPen(QColor(80, 80, 80), 1, Qt.DashLine))
            painter.drawRect(self.boundingRect())
            s = self.window.grid_px * self.handle_size_factor
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            for r in _corner_handles(self.boundingRect(), s).values():
                painter.drawRect(r)
            painter.drawEllipse(_rotation_handle(self.boundingRect(), self.window.grid_px * self.rotate_handle_factor))

    def mousePressEvent(self, event):
        self._undo_state_pushed_for_drag = False
        if self.isSelected() and event.button() == Qt.LeftButton:
            try:
                self.window.push_undo_state()
                self._undo_state_pushed_for_drag = True
            except Exception:
                pass
        if self.isSelected() and _rotation_handle(self.boundingRect(), self.window.grid_px * self.rotate_handle_factor).contains(event.pos()):
            self._rotating = True
            self._rotate_center_scene = self.mapToScene(self.boundingRect().center())
            self._rotate_start_angle = _angle_from(self._rotate_center_scene, event.scenePos())
            self._rotate_start_model = float(getattr(self.model, 'rotation', 0.0) or 0.0)
            event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if getattr(self, '_rotating', False):
            delta = _angle_from(self._rotate_center_scene, event.scenePos()) - self._rotate_start_angle
            self.model.rotation = (round((self._rotate_start_model + delta) / 15.0) * 15.0) % 360
            self.apply_transform_from_model()
            try:
                self.window.notify_canvas_model_changed()
            except Exception:
                self.window.live_refresh()
            event.accept(); return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._undo_state_pushed_for_drag = False
        self._rotating = False
        super().mouseReleaseEvent(event)

    def update_model_pos(self):
        g = self.window.grid_px
        old_x, old_y = float(self.model.x), float(self.model.y)
        self.model.x = self.pos().x() / g
        self.model.y = -self.pos().y() / g
        dx, dy = float(self.model.x) - old_x, float(self.model.y) - old_y
        if abs(dx) > 1e-9 or abs(dy) > 1e-9:
            # Loose docking: a user drag intentionally detaches the pin from the
            # automatic BODY edge. Programmatic moves (scene rebuild/body resize)
            # keep the existing docking state.
            try:
                if QApplication.mouseButtons() & Qt.LeftButton:
                    self.model.auto_dock = False
            except Exception:
                pass
            for ax_name, ay_name in (('label_x', 'label_y'), ('number_x', 'number_y')):
                if getattr(self.model, ax_name, None) is not None and getattr(self.model, ay_name, None) is not None:
                    setattr(self.model, ax_name, float(getattr(self.model, ax_name)) + dx)
                    setattr(self.model, ay_name, float(getattr(self.model, ay_name)) + dy)
            for tm in (getattr(self.model, 'attribute_texts', {}) or {}).values():
                try:
                    tm.x = float(tm.x) + dx
                    tm.y = float(tm.y) + dy
                except Exception:
                    pass

    def scale_selected(self, factor):
        # Pin length is quantized to the active edit grid so copied/imported
        # pins can be edited at the same raster as the current workspace.
        try:
            step = self.window._edit_grid_step() if hasattr(self.window, '_edit_grid_step') else 1.0
        except Exception:
            step = 1.0
        try:
            value = float(self.model.length) * float(factor)
            self.model.length = max(step, round(value / step) * step)
        except Exception:
            self.model.length = max(1.0, round(self.model.length * factor))
        self.apply_transform_from_model()
        self.update()

    def scale_by(self, factor):
        return self.scale_selected(factor)


class TextItem(TransformMixin, QGraphicsTextItem):
    def __init__(self, model, window):
        self.model = model
        self.window = window
        super().__init__(model.text)
        try:
            self.document().setDocumentMargin(0)
        except Exception:
            pass
        self.common_flags()
        # Text remains movable/selectable in edit mode. Text editing starts only on double click.
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        self.setData(0, 'TEXT')
        self._rotating = False
        self.apply_text_from_model()

    def shape(self):
        path = super().shape()
        try:
            pad = _hit_tolerance_px(self.window, 0.18, 8.0)
            br = self._visual_text_rect().adjusted(-pad, -pad, pad, pad)
            padded = QPainterPath()
            padded.addRect(br)
            return path.united(padded)
        except Exception:
            return path

    def itemChange(self, change, value):
        # Text/attribute objects are positioned by their selected grid anchor
        # (left/center/right x upper/center/lower).  The anchor point, not the
        # item top-left, must snap to the grid.
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            if bool(getattr(self.scene().window, 'template_snap_check', None) and not self.scene().window.template_snap_check.isChecked()):
                return super().itemChange(change, value)
            g = self.scene().grid_px
            try:
                off = self._text_anchor_offset()
                anchor = QPointF(value.x() + off.x(), value.y() + off.y())
                snapped_anchor = QPointF(snap(anchor.x(), g), snap(anchor.y(), g))
                return snapped_anchor - off
            except Exception:
                return QPointF(snap(value.x(), g), snap(value.y(), g))
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.update_model_pos()
            try:
                self.scene().window.notify_canvas_model_changed()
            except Exception:
                self.scene().window.live_refresh()
        return super().itemChange(change, value)

    def _visual_text_rect(self):
        """Tight local text rectangle used for grid anchoring.

        QGraphicsTextItem/document sizes contain layout slack, especially on
        the right edge.  Using font metrics for the actual lines makes
        right-aligned text end exactly at the selected grid line and makes
        lower alignment use the visual bottom instead of the item top.
        """
        try:
            fm = QFontMetricsF(self.font())
            text = str(getattr(self.model, 'text', '') or '')
            lines = text.split('\n') or ['']
            width = max((fm.horizontalAdvance(line) for line in lines), default=0.0)
            height = max(fm.height(), fm.lineSpacing() * len(lines))
            return QRectF(0, 0, width, height)
        except Exception:
            return self.boundingRect()

    def _text_anchor_offset(self):
        """Return the local visual point that must sit on model.x/model.y."""
        br = self._visual_text_rect()
        h = getattr(self.model, 'h_align', 'left')
        v = getattr(self.model, 'v_align', 'upper')
        if h == 'center':
            ox = br.center().x()
        elif h == 'right':
            ox = br.right()
        else:
            ox = br.left()
        if v == 'center':
            oy = br.center().y()
        elif v == 'lower':
            oy = br.bottom()
        else:
            oy = br.top()
        return QPointF(ox, oy)

    def _aligned_scene_pos(self):
        g = self.window.grid_px
        anchor = QPointF(self.model.x * g, -self.model.y * g)
        return anchor - self._text_anchor_offset()

    def apply_text_from_model(self):
        g = self.window.grid_px
        self.setPlainText(str(getattr(self.model, 'text', '')))
        self.setDefaultTextColor(rgb(self.model.color))
        self.setFont(QFont(self.model.font_family, max(6, int(g * self.model.font_size_grid * .45))))
        try:
            self.document().setDocumentMargin(0)
            opt = self.document().defaultTextOption()
            opt.setWrapMode(QTextOption.WordWrap if bool(getattr(self.model, 'wrap_text', False)) else QTextOption.NoWrap)
            self.document().setDefaultTextOption(opt)
            self.setTextWidth(-1 if not bool(getattr(self.model, 'wrap_text', False)) else max(self.window.grid_px, self.boundingRect().width()))
            self.adjustSize()
        except Exception:
            pass
        self.setPos(self._aligned_scene_pos())
        self.apply_transform_from_model()
        self.update()

    def _model_pos_from_item_pos(self):
        g = self.window.grid_px
        anchor = self.pos() + self._text_anchor_offset()
        # Store the logical anchor on full grid coordinates.  This keeps the
        # green anchor marker and all alignment permutations exactly on grid
        # lines, independent of the visual width/height of the text.
        if hasattr(self.window, 'snap_grid_value'):
            self.model.x = self.window.snap_grid_value(anchor.x() / g)
            self.model.y = self.window.snap_grid_value(-anchor.y() / g)
        else:
            self.model.x = round(anchor.x() / g)
            self.model.y = round(-anchor.y() / g)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if self.isSelected():
            # Text objects show a thin text selection rectangle plus the active
            # grid anchor.  The green marker has 9 possible positions inside the
            # text box: left/center/right x upper/center/lower.
            painter.save()
            painter.setPen(QPen(QColor(80, 80, 80), 1, Qt.DashLine))
            painter.setBrush(QBrush(Qt.NoBrush))
            painter.drawRect(self._visual_text_rect())
            anchor = self._text_anchor_offset()
            s = max(4.0, self.window.grid_px * 0.12)
            painter.setPen(QPen(QColor(0, 130, 0), 1))
            painter.setBrush(QBrush(QColor(0, 180, 0)))
            painter.drawRect(QRectF(anchor.x() - s / 2, anchor.y() - s / 2, s, s))
            painter.restore()

    def mouseDoubleClickEvent(self, event):
        if self.data(0) in ('ATTR_REF_DES', 'ATTR_BODY') or bool(getattr(self.model, '_is_attribute_text', False)):
            event.accept()
            return
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFocus(Qt.MouseFocusReason)
        cursor = self.textCursor()
        cursor.select(QTextCursor.Document)
        self.setTextCursor(cursor)
        event.accept()

    def keyPressEvent(self, event):
        if self.textInteractionFlags() != Qt.NoTextInteraction and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                QGraphicsTextItem.keyPressEvent(self, event)
                event.accept()
                return
            if not (self.data(0) in ('ATTR_REF_DES', 'ATTR_BODY') or bool(getattr(self.model, '_is_attribute_text', False))):
                self.model.text = self.toPlainText()
            self.setTextInteractionFlags(Qt.NoTextInteraction)
            self.clearFocus()
            try:
                self.scene().window.notify_canvas_model_changed()
            except Exception:
                self.scene().window.live_refresh()
            event.accept()
            return
        if self.textInteractionFlags() != Qt.NoTextInteraction:
            # Prevent canvas shortcuts such as E/R rotation while typing.
            QGraphicsTextItem.keyPressEvent(self, event)
            event.accept()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, e):
        # When the user clicks out of a canvas text item, commit the text and
        # immediately return the item to normal canvas-object mode so it can be
        # selected, moved, copied and transformed again.
        if not (self.data(0) in ('ATTR_REF_DES', 'ATTR_BODY') or bool(getattr(self.model, '_is_attribute_text', False))):
            self.model.text = self.toPlainText()
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        self.common_flags()
        self.scene().window.live_refresh()
        super().focusOutEvent(e)

    def update_model_pos(self):
        self._model_pos_from_item_pos()
        if not (self.data(0) in ('ATTR_REF_DES', 'ATTR_BODY') or bool(getattr(self.model, '_is_attribute_text', False))):
            self.model.text = self.toPlainText()



class GraphicItem(TransformMixin, QGraphicsItem):
    def __init__(self, model, window):
        super().__init__()
        self.model = model
        self.window = window
        self._resizing = None
        self._rotating = False
        self._resize_anchor_scene = None
        self._resize_start = None
        self._rotating = False
        self._rotate_start_angle = 0.0
        self._rotate_start_model = 0.0
        self._rotate_center_scene = QPointF()
        g = window.grid_px
        self.setPos(model.x * g, -model.y * g)
        self.common_flags()
        self.setData(0, 'GRAPHIC')
        if getattr(model, 'locked_to_body', False) and not getattr(window, 'is_template_editor', False):
            # Imported/template BODY primitives are paint/highlight only in the
            # Symbol Wizard. They must never become real selected objects; the
            # logical BodyItem is the only selected item. This prevents the
            # property panel from switching to "2 objects selected".
            self.setFlag(QGraphicsItem.ItemIsMovable, False)
            self.setFlag(QGraphicsItem.ItemIsSelectable, False)
            self.setFlag(QGraphicsItem.ItemIsFocusable, False)
            self.setAcceptedMouseButtons(Qt.NoButton)
            self.setAcceptHoverEvents(False)
        self.apply_transform_from_model()

    def _raw_rect(self):
        g = self.window.grid_px
        return QRectF(0, 0, self.model.w * g, self.model.h * g)

    def _rect(self):
        r = self._raw_rect().normalized()
        if getattr(self.model, 'shape', '') == 'line':
            g = self.window.grid_px
            cr = float(getattr(self.model, 'curve_radius', 0.0) or 0.0) * g
            if cr > 0:
                r.setTop(min(r.top(), self.model.h * g / 2 - cr))
            elif cr < 0:
                r.setBottom(max(r.bottom(), self.model.h * g / 2 - cr))
        if r.width() < 1:
            r.adjust(-.5, 0, .5, 0)
        if r.height() < 1:
            r.adjust(0, -.5, 0, .5)
        return r

    def boundingRect(self):
        g = self.window.grid_px
        return self._rect().adjusted(-.35 * g, -.35 * g, .35 * g, .35 * g)

    def shape(self):
        g = self.window.grid_px
        m = self.model
        path = QPainterPath()
        try:
            if m.shape in ('line', 'arc'):
                ctrl_x = getattr(m, 'ctrl_x', None)
                ctrl_y = getattr(m, 'ctrl_y', None)
                path.moveTo(QPointF(0, 0))
                if ctrl_x is not None and ctrl_y is not None:
                    path.quadTo(QPointF(float(ctrl_x) * g, -float(ctrl_y) * g), QPointF(m.w * g, -m.h * g))
                else:
                    r = float(getattr(m, 'curve_radius', 0.0) or 0.0)
                    if abs(r) > 1e-9:
                        path.quadTo(QPointF(m.w * g / 2, m.h * g / 2 - r * g), QPointF(m.w * g, m.h * g))
                    else:
                        path.lineTo(QPointF(m.w * g, m.h * g))
            elif m.shape == 'rect':
                path.addRect(QRectF(0, 0, m.w * g, m.h * g))
            elif m.shape in ('ellipse', 'circle'):
                path.addEllipse(QRectF(0, 0, m.w * g, m.h * g))
            else:
                path.addRect(self._rect())
            stroker = QPainterPathStroker()
            stroker.setWidth(_hit_tolerance_px(self.window, 0.24, 10.0))
            return path.united(stroker.createStroke(path))
        except Exception:
            return super().shape() if hasattr(super(), 'shape') else path

    def _handles(self):
        g = self.window.grid_px
        s = g * self.handle_size_factor
        if self.model.shape == 'line':
            return {
                'start': QRectF(-s/2, -s/2, s, s),
                'end': QRectF(self.model.w*g - s/2, self.model.h*g - s/2, s, s),
                'curve': QRectF(self.model.w*g/2 - s/2, self.model.h*g/2 - float(getattr(self.model, 'curve_radius', 0.0))*g - s/2, s, s),
            }
        return _corner_handles(self._rect(), s)

    def paint(self, painter, option, widget=None):
        g, m = self.window.grid_px, self.model
        painter.setPen(pen_for(m.style.stroke, m.style.line_width, m.style.line_style, g))
        painter.setBrush(QBrush(rgb(m.style.fill)) if m.style.fill else QBrush(Qt.NoBrush))
        if m.shape in ('line', 'arc'):
            ctrl_x = getattr(m, 'ctrl_x', None)
            ctrl_y = getattr(m, 'ctrl_y', None)
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
        selected_for_highlight = self.isSelected()
        # Grouped user graphics are highlighted by one shared group outline in
        # MainWindow. Individual child handles would make the group look like
        # multiple objects and can also interfere with selection/pivot logic.
        try:
            _gid = str(getattr(self.model, 'group_id', '') or '')
            _role = str(getattr(self.model, 'graphic_role', '') or '')
            if (not getattr(self.model, 'locked_to_body', False)) and (_gid or _role.startswith('user_graphic_group:')):
                selected_for_highlight = False
        except Exception:
            pass
        if getattr(self.model, 'locked_to_body', False) and not getattr(self.window, 'is_template_editor', False):
            try:
                selected_for_highlight = selected_for_highlight or any(
                    getattr(i, 'data', lambda *_: None)(0) == 'BODY' and i.isSelected()
                    for i in self.scene().items()
                )
            except Exception:
                pass
        if selected_for_highlight:
            painter.save()
            if getattr(self.model, 'locked_to_body', False) and not getattr(self.window, 'is_template_editor', False):
                # BODY selection highlight on the real artwork only. No proxy
                # bounding rectangle / helper frame is drawn.
                painter.setPen(QPen(QColor(0, 150, 170), max(1, int(0.08 * g)), Qt.DashLine))
                painter.setBrush(QBrush(Qt.NoBrush))
                if m.shape in ('line', 'arc'):
                    if 'path' in locals():
                        painter.drawPath(path)
                    else:
                        painter.drawLine(QPointF(0, 0), QPointF(m.w * g, m.h * g))
                elif m.shape == 'rect':
                    painter.drawRect(QRectF(0, 0, m.w * g, m.h * g))
                elif m.shape in ('ellipse', 'circle'):
                    painter.drawEllipse(QRectF(0, 0, m.w * g, m.h * g))
            elif (not getattr(self.model, 'locked_to_body', False) or getattr(self.window, 'is_template_editor', False)):
                painter.setPen(QPen(QColor(80, 80, 80), 1, Qt.DashLine))
                painter.drawRect(self._rect())
                painter.setBrush(QBrush(QColor(255, 255, 255)))
                for r in self._handles().values():
                    painter.drawRect(r)
                painter.drawEllipse(_rotation_handle(self._rect(), self.window.grid_px * self.rotate_handle_factor))
            painter.restore()

    def hoverMoveEvent(self, event):
        if self.isSelected():
            h = 'rot' if _rotation_handle(self._rect(), self.window.grid_px * self.rotate_handle_factor).contains(event.pos()) else _hit_handle(self._handles(), event.pos())
            self.setCursor(QCursor(_cursor_for_handle(h)) if h else QCursor(Qt.ArrowCursor))
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.unsetCursor()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        # Template Editor graphics need their own undo hook.  Resize/rotate
        # handles do not always trigger ItemPositionChange, and a normal move
        # can start before the item becomes selected, so relying only on the
        # TransformMixin itemChange hook leaves GraphicModel edits out of the
        # undo stack.  Save exactly one pre-edit snapshot on mouse press.
        self._undo_state_pushed_for_drag = False
        if event.button() == Qt.LeftButton:
            try:
                if (getattr(self.window, 'is_template_editor', False)
                        and not getattr(self.window, '_loading_template', False)
                        and not getattr(self.window, '_restoring_undo_redo', False)):
                    self.window.push_undo_state()
                    self._undo_state_pushed_for_drag = True
                    try:
                        self._undo_state_at_graphic_press = self.window._unit_state_for_undo(self.window.undo_stack[-1])
                    except Exception:
                        self._undo_state_at_graphic_press = None
            except Exception:
                pass
        if self.isSelected():
            if _rotation_handle(self._rect(), self.window.grid_px * self.rotate_handle_factor).contains(event.pos()):
                self._rotating = True
                self._rotate_center_scene = self.mapToScene(self._rect().center())
                self._rotate_start_angle = _angle_from(self._rotate_center_scene, event.scenePos())
                self._rotate_start_model = float(getattr(self.model, 'rotation', 0.0) or 0.0)
                event.accept(); return
            h = _hit_handle(self._handles(), event.pos())
            if h:
                self._resizing = h
                g = self.window.grid_px
                self._resize_start = {
                    'x': float(self.model.x), 'y': float(self.model.y),
                    'w': float(self.model.w), 'h': float(self.model.h),
                }
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if getattr(self, '_rotating', False):
            delta = _angle_from(self._rotate_center_scene, event.scenePos()) - self._rotate_start_angle
            self.model.rotation = (round((self._rotate_start_model + delta) / 15.0) * 15.0) % 360
            self.apply_transform_from_model()
            try:
                self.window.notify_canvas_model_changed()
            except Exception:
                self.window.live_refresh()
            event.accept(); return
        if self._resizing and self._resize_start is not None:
            g = self.window.grid_px
            p = QPointF(snap(event.scenePos().x(), self.window.edit_grid_px), snap(event.scenePos().y(), self.window.edit_grid_px))
            st = self._resize_start
            left = st['x'] * g
            top = -st['y'] * g
            right = left + st['w'] * g
            bottom = top + st['h'] * g

            # Line endpoints are edited directly; the middle handle changes only curve radius and is intentionally not grid-snapped.
            if self.model.shape == 'line':
                raw = event.scenePos()
                if self._resizing == 'start':
                    old_end_x = left + st['w'] * g; old_end_y = top + st['h'] * g
                    left = p.x(); top = p.y(); right = old_end_x; bottom = old_end_y
                elif self._resizing == 'end':
                    right = p.x(); bottom = p.y()
                elif self._resizing == 'curve':
                    mid_y = top + (st['h'] * g) / 2
                    self.model.curve_radius = (mid_y - raw.y()) / g
                    self.window.live_refresh(); self.update(); event.accept(); return
            else:
                # Edge handles are one-dimensional only; corners are true 2D resize.
                if self._resizing in ('l', 'tl', 'bl'):
                    left = p.x()
                if self._resizing in ('r', 'tr', 'br'):
                    right = p.x()
                if self._resizing in ('t', 'tl', 'tr'):
                    top = p.y()
                if self._resizing in ('b', 'bl', 'br'):
                    bottom = p.y()

            if self.model.shape != 'line':
                min_size = g * .25
                if right < left:
                    left, right = right, left
                if bottom < top:
                    top, bottom = bottom, top
                if right - left < min_size:
                    if self._resizing in ('l', 'tl', 'bl'):
                        left = right - min_size
                    else:
                        right = left + min_size
                if bottom - top < min_size:
                    if self._resizing in ('t', 'tl', 'tr'):
                        top = bottom - min_size
                    else:
                        bottom = top + min_size

            self.prepareGeometryChange()
            self.setPos(left, top)
            self.model.x = left / g
            self.model.y = -top / g
            self.model.w = (right - left) / g
            self.model.h = (bottom - top) / g
            try:
                self.window.notify_canvas_model_changed()
            except Exception:
                self.window.live_refresh()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # If the user only clicked/selected a graphic, do not leave a dirty
        # undo entry behind.  For real graphic edits (move/resize/rotate/curve)
        # the current template state differs from the saved pre-edit state and
        # the undo snapshot is kept.
        try:
            if getattr(self, '_undo_state_pushed_for_drag', False) and getattr(self.window, 'is_template_editor', False):
                before = getattr(self, '_undo_state_at_graphic_press', None)
                after = self.window._template_state() if hasattr(self.window, '_template_state') else None
                if before is not None and after == before and getattr(self.window, 'undo_stack', None):
                    self.window.undo_stack.pop()
                    self.window.dirty = self.window.is_template_dirty() if hasattr(self.window, 'is_template_dirty') else False
        except Exception:
            pass
        self._undo_state_pushed_for_drag = False
        self._undo_state_at_graphic_press = None
        self._resizing = None
        self._resize_anchor_scene = None
        self._resize_start = None
        self.window.enforce_symbol_size_limit(silent=True)
        self.window.rebuild_tree()
        self.scene().update()
        super().mouseReleaseEvent(event)

    def update_model_pos(self):
        g = self.window.grid_px
        self.model.x = self.pos().x() / g
        self.model.y = -self.pos().y() / g

    def _snap_graphic_dimension(self, value, step):
        """Snap a graphic dimension to the edit grid without collapsing to 0."""
        try:
            step = max(0.001, float(step or 0.001))
        except Exception:
            step = 0.5
        sign = -1.0 if float(value or 0.0) < 0 else 1.0
        mag = abs(float(value or 0.0))
        snapped = round(mag / step) * step
        if snapped < step:
            snapped = step
        return sign * snapped

    def scale_by(self, factor):
        """Scale this graphic in-place around its own model-space center.

        Toolbar Scale +/- is intentionally object-local for user graphics: it
        must not move the object to the origin, must not collapse width/height
        to 0, and must not involve pins or BODY-group scaling.  The center is
        preserved while width/height are snapped to the active edit grid.
        """
        try:
            factor = float(factor)
        except Exception:
            factor = 1.0
        if abs(factor) < 1e-9:
            return
        step = 0.5
        try:
            step = self.window._edit_grid_step() if hasattr(self.window, '_edit_grid_step') else 0.5
        except Exception:
            step = 0.5

        old_w = float(getattr(self.model, 'w', 0.0) or 0.0)
        old_h = float(getattr(self.model, 'h', 0.0) or 0.0)
        old_x = float(getattr(self.model, 'x', 0.0) or 0.0)
        old_y = float(getattr(self.model, 'y', 0.0) or 0.0)

        # In model coordinates graphics are stored with x/y at the visual top-left;
        # positive h extends downward on screen, i.e. toward smaller model y.
        cx = old_x + old_w / 2.0
        cy = old_y - old_h / 2.0

        new_w = self._snap_graphic_dimension(old_w * factor, step)
        new_h = self._snap_graphic_dimension(old_h * factor, step)

        self.prepareGeometryChange()
        self.model.w = new_w
        self.model.h = new_h
        self.model.x = cx - new_w / 2.0
        self.model.y = cy + new_h / 2.0
        g = self.window.grid_px
        self.setPos(self.model.x * g, -self.model.y * g)
        try:
            self.window.notify_canvas_model_changed()
        except Exception:
            try:
                self.window.live_refresh()
            except Exception:
                pass
        self.update()

    def scale_selected(self, factor):
        self.scale_by(factor)


# ---------------------------------------------------------------------------
# Liebherr v56: move grouped user graphics as one object.
# ---------------------------------------------------------------------------
try:
    _lh56_graphicitem_prev_init = GraphicItem.__init__
    _lh56_graphicitem_prev_update_model_pos = GraphicItem.update_model_pos

    def _lh56_graphicitem_init(self, model, window):
        _lh56_graphicitem_prev_init(self, model, window)
        try:
            self._lh56_last_model_pos = (float(getattr(model, 'x', 0.0) or 0.0), float(getattr(model, 'y', 0.0) or 0.0))
        except Exception:
            self._lh56_last_model_pos = (0.0, 0.0)

    def _lh56_graphicitem_gid(gr):
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

    def _lh56_graphicitem_is_user(gr):
        try:
            role = str(getattr(gr, 'graphic_role', '') or '').lower()
            return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body', 'template_body', 'imported_body')
        except Exception:
            return False

    def _lh56_graphicitem_update_model_pos(self):
        if getattr(self.window, '_lh56_group_move_active', False):
            return _lh56_graphicitem_prev_update_model_pos(self)
        old = getattr(self, '_lh56_last_model_pos', None)
        _lh56_graphicitem_prev_update_model_pos(self)
        try:
            new = (float(getattr(self.model, 'x', 0.0) or 0.0), float(getattr(self.model, 'y', 0.0) or 0.0))
        except Exception:
            return
        if old is None:
            self._lh56_last_model_pos = new
            return
        dx, dy = new[0] - old[0], new[1] - old[1]
        self._lh56_last_model_pos = new
        if abs(dx) < 1e-12 and abs(dy) < 1e-12:
            return
        gid = _lh56_graphicitem_gid(self.model)
        if not gid or not _lh56_graphicitem_is_user(self.model):
            return
        try:
            self.window._lh56_group_move_active = True
            unit = getattr(self.window, 'current_unit', None)
            graphics = list(getattr(unit, 'graphics', []) or [])
            for gr in graphics:
                if gr is self.model:
                    continue
                if _lh56_graphicitem_gid(gr) == gid and _lh56_graphicitem_is_user(gr):
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
                    if gr is not None and _lh56_graphicitem_gid(gr) == gid and _lh56_graphicitem_is_user(gr):
                        it.setPos(float(getattr(gr, 'x', 0.0) or 0.0) * gpx, -float(getattr(gr, 'y', 0.0) or 0.0) * gpx)
                        it._lh56_last_model_pos = (float(getattr(gr, 'x', 0.0) or 0.0), float(getattr(gr, 'y', 0.0) or 0.0))
                except Exception:
                    pass
        finally:
            try:
                self.window._lh56_group_move_active = False
            except Exception:
                pass

    GraphicItem.__init__ = _lh56_graphicitem_init
    GraphicItem.update_model_pos = _lh56_graphicitem_update_model_pos
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v58: grouped graphics are highlighted as one logical object.
# ---------------------------------------------------------------------------
try:
    _lh58_graphic_prev_paint = GraphicItem.paint

    def _lh58_graphic_gid(model):
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

    def _lh58_graphic_group_models(item, gid):
        out = []
        try:
            unit = getattr(item.window, 'current_unit', None)
            for gr in list(getattr(unit, 'graphics', []) or []):
                if _lh58_graphic_gid(gr) == gid:
                    out.append(gr)
        except Exception:
            pass
        return out

    def _lh58_graphic_is_group_leader(item, gid):
        try:
            scene = item.scene()
            if scene is None:
                return True
            selected = []
            for it in scene.selectedItems():
                try:
                    if getattr(it, 'data', lambda *_: None)(0) == 'GRAPHIC' and _lh58_graphic_gid(getattr(it, 'model', None)) == gid:
                        selected.append(it)
                except Exception:
                    pass
            return not selected or selected[0] is item
        except Exception:
            return True

    def _lh58_draw_group_highlight(self, painter, gid):
        models = _lh58_graphic_group_models(self, gid)
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

    def _lh58_graphic_paint(self, painter, option, widget=None):
        gid = _lh58_graphic_gid(getattr(self, 'model', None))
        if not gid:
            return _lh58_graphic_prev_paint(self, painter, option, widget)
        # Draw the graphic geometry without its individual selection handles.
        was_selected = False
        try:
            was_selected = self.isSelected()
            if was_selected:
                self.setSelected(False)
            _lh58_graphic_prev_paint(self, painter, option, widget)
        finally:
            try:
                if was_selected:
                    self.setSelected(True)
            except Exception:
                pass
        # Then draw exactly one group highlight for the selected group.
        if was_selected and _lh58_graphic_is_group_leader(self, gid):
            _lh58_draw_group_highlight(self, painter, gid)

    GraphicItem.paint = _lh58_graphic_paint
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v59: paint grouped graphics as one highlighted logical object.
# Individual group members still draw their geometry, but never their own
# selection handles; exactly one group bounding box is drawn for the selection.
# ---------------------------------------------------------------------------
try:
    def _lh59_item_gid(model):
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

    def _lh59_item_draw_geometry(self, painter):
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

    def _lh59_item_group_boxes(self, gid):
        boxes = []
        try:
            unit = getattr(self.window, 'current_unit', None)
            for gr in list(getattr(unit, 'graphics', []) or []):
                if _lh59_item_gid(gr) != gid:
                    continue
                x = float(getattr(gr, 'x', 0.0) or 0.0); y = float(getattr(gr, 'y', 0.0) or 0.0)
                w = float(getattr(gr, 'w', 0.0) or 0.0); h = float(getattr(gr, 'h', 0.0) or 0.0)
                x2 = x + w; y2 = y - h
                boxes.append((min(x, x2), min(y, y2), max(x, x2), max(y, y2), gr))
        except Exception:
            pass
        return boxes

    def _lh59_item_is_group_paint_leader(self, gid):
        try:
            # Prefer the first selected item of the group in scene order. This
            # avoids drawing the group bbox multiple times when all members are
            # selected as one logical object.
            selected = []
            for it in self.scene().selectedItems():
                try:
                    if getattr(it, 'data', lambda *_: None)(0) == 'GRAPHIC' and _lh59_item_gid(getattr(it, 'model', None)) == gid:
                        selected.append(it)
                except Exception:
                    pass
            return bool(selected) and selected[0] is self
        except Exception:
            return True

    def _lh59_item_draw_group_highlight(self, painter, gid):
        boxes = _lh59_item_group_boxes(self, gid)
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

    def _lh59_graphic_paint(self, painter, option, widget=None):
        gid = _lh59_item_gid(getattr(self, 'model', None))
        if not gid:
            return _lh58_graphic_prev_paint(self, painter, option, widget) if '_lh58_graphic_prev_paint' in globals() else None
        _lh59_item_draw_geometry(self, painter)
        try:
            group_selected = any(
                getattr(it, 'data', lambda *_: None)(0) == 'GRAPHIC' and _lh59_item_gid(getattr(it, 'model', None)) == gid and it.isSelected()
                for it in self.scene().items()
            )
        except Exception:
            group_selected = self.isSelected()
        if group_selected and _lh59_item_is_group_paint_leader(self, gid):
            _lh59_item_draw_group_highlight(self, painter, gid)

    GraphicItem.paint = _lh59_graphic_paint
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
    _lh68_prev_graphic_mouse_press = GraphicItem.mousePressEvent
    _lh68_prev_graphic_mouse_move = GraphicItem.mouseMoveEvent
except Exception:
    _lh68_prev_graphic_mouse_press = None
    _lh68_prev_graphic_mouse_move = None


def _lh68_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)


def _lh68_edit_grid_px(win):
    try:
        return max(1e-9, float(getattr(win, 'edit_grid_px', 0.0) or 0.0))
    except Exception:
        return 1.0


def _lh68_snap_px(win, value):
    step = _lh68_edit_grid_px(win)
    try:
        return snap(float(value), step)
    except Exception:
        return round(float(value) / step) * step


def _lh68_snap_scene_point(win, p):
    return QPointF(_lh68_snap_px(win, p.x()), _lh68_snap_px(win, p.y()))


def _lh68_local_rect(item):
    # Use raw model geometry, not boundingRect(), because boundingRect contains
    # selection/handle margins.  The transform origin must be geometric lower-left.
    g = item.window.grid_px
    w = _lh68_float(getattr(item.model, 'w', 0.0), 0.0) * g
    h = _lh68_float(getattr(item.model, 'h', 0.0), 0.0) * g
    return QRectF(0.0, 0.0, w, h).normalized()


def _lh68_graphic_apply_transform_from_model(self):
    def f(name, default):
        try:
            return float(getattr(self.model, name, default) or default)
        except Exception:
            return default
    sx, sy, rot = f('scale_x', 1.0), f('scale_y', 1.0), f('rotation', 0.0)
    self.model.scale_x, self.model.scale_y, self.model.rotation = sx, sy, rot
    try:
        r = _lh68_local_rect(self)
        # Stable object origin for rotate/flip: lower-left of the actual object.
        self.setTransformOriginPoint(r.bottomLeft())
    except Exception:
        pass
    self.setTransform(QTransform().scale(sx, sy))
    self.setRotation(rot)


def _lh68_handle_points(item):
    r = _lh68_local_rect(item)
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


def _lh68_opposite_handle(handle):
    return {
        'tl': 'br', 'tr': 'bl', 'bl': 'tr', 'br': 'tl',
        'l': 'r', 'r': 'l', 't': 'b', 'b': 't',
    }.get(handle, '')


def _lh68_graphic_mouse_press(self, event):
    if event.button() == Qt.LeftButton and self.isSelected():
        try:
            # Rotation remains original behaviour, but with lower-left transform origin.
            if _rotation_handle(self._rect(), self.window.grid_px * self.rotate_handle_factor).contains(event.pos()):
                return _lh68_prev_graphic_mouse_press(self, event)
            h = _hit_handle(self._handles(), event.pos())
            if h and str(getattr(self.model, 'shape', '') or '') not in ('line', 'arc'):
                pts = _lh68_handle_points(self)
                anchor_name = _lh68_opposite_handle(h)
                anchor_local = pts.get(anchor_name, QPointF(0, 0))
                self._lh68_resizing = h
                self._lh68_resize_anchor_name = anchor_name
                self._lh68_resize_anchor_local = QPointF(anchor_local)
                self._lh68_resize_anchor_scene = self.mapToScene(anchor_local)
                self._lh68_resize_start = {
                    'x': _lh68_float(getattr(self.model, 'x', 0.0), 0.0),
                    'y': _lh68_float(getattr(self.model, 'y', 0.0), 0.0),
                    'w': _lh68_float(getattr(self.model, 'w', 0.0), 0.0),
                    'h': _lh68_float(getattr(self.model, 'h', 0.0), 0.0),
                    'sx': _lh68_float(getattr(self.model, 'scale_x', 1.0), 1.0),
                    'sy': _lh68_float(getattr(self.model, 'scale_y', 1.0), 1.0),
                    'rot': _lh68_float(getattr(self.model, 'rotation', 0.0), 0.0),
                }
                event.accept(); return
        except Exception:
            pass
    return _lh68_prev_graphic_mouse_press(self, event)


def _lh68_graphic_mouse_move(self, event):
    if getattr(self, '_lh68_resizing', None) and getattr(self, '_lh68_resize_start', None) is not None:
        try:
            win = self.window
            g = float(win.grid_px)
            min_px = max(_lh68_edit_grid_px(win), 1e-9)
            hname = str(self._lh68_resizing)
            anchor_local = QPointF(self._lh68_resize_anchor_local)
            anchor_scene = QPointF(self._lh68_resize_anchor_scene)
            mouse_scene = _lh68_snap_scene_point(win, event.scenePos())
            mouse_local = self.mapFromScene(mouse_scene)

            # Build the new local rectangle from a fixed opposite handle/edge and
            # the dragged mouse point.  Because mouse_local is obtained through the
            # current item transform, dragging in scene direction remains natural
            # even after rotation or axis mirroring.
            l = 0.0; t = 0.0
            r = _lh68_float(getattr(self.model, 'w', 0.0), 0.0) * g
            b = _lh68_float(getattr(self.model, 'h', 0.0), 0.0) * g

            # Use the anchor coordinate for the fixed side(s).
            if hname in ('l', 'tl', 'bl'):
                r = anchor_local.x(); l = mouse_local.x()
            elif hname in ('r', 'tr', 'br'):
                l = anchor_local.x(); r = mouse_local.x()
            else:
                l = 0.0; r = _lh68_float(getattr(self.model, 'w', 0.0), 0.0) * g

            if hname in ('t', 'tl', 'tr'):
                b = anchor_local.y(); t = mouse_local.y()
            elif hname in ('b', 'bl', 'br'):
                t = anchor_local.y(); b = mouse_local.y()
            else:
                t = 0.0; b = _lh68_float(getattr(self.model, 'h', 0.0), 0.0) * g

            # Snap size to edit grid and enforce one edit-grid minimum.  Edge
            # handles resize exactly one axis; corner handles resize both axes.
            left = min(l, r); right = max(l, r)
            top = min(t, b); bottom = max(t, b)
            new_w = max(min_px, _lh68_snap_px(win, right - left))
            new_h = max(min_px, _lh68_snap_px(win, bottom - top))

            # Preserve the side under the fixed anchor after size snapping.
            if hname in ('l', 'tl', 'bl'):
                right = anchor_local.x(); left = right - new_w
            elif hname in ('r', 'tr', 'br'):
                left = anchor_local.x(); right = left + new_w
            else:
                # Center untouched dimension around the old local rect.
                old = _lh68_local_rect(self)
                left = old.left(); right = old.right()
                new_w = max(min_px, abs(right - left))

            if hname in ('t', 'tl', 'tr'):
                bottom = anchor_local.y(); top = bottom - new_h
            elif hname in ('b', 'bl', 'br'):
                top = anchor_local.y(); bottom = top + new_h
            else:
                old = _lh68_local_rect(self)
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
            final_pos = _lh68_snap_scene_point(win, final_pos)
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
                self._lh68_resizing = None
            except Exception:
                pass
    return _lh68_prev_graphic_mouse_move(self, event)


def _lh68_graphic_mouse_release(self, event):
    try:
        self._lh68_resizing = None
        self._lh68_resize_start = None
        self._lh68_resize_anchor_local = None
        self._lh68_resize_anchor_scene = None
    except Exception:
        pass
    return _lh68_prev_graphic_mouse_release(self, event)

try:
    _lh68_prev_graphic_mouse_release = GraphicItem.mouseReleaseEvent
    GraphicItem.apply_transform_from_model = _lh68_graphic_apply_transform_from_model
    GraphicItem.mousePressEvent = _lh68_graphic_mouse_press
    GraphicItem.mouseMoveEvent = _lh68_graphic_mouse_move
    GraphicItem.mouseReleaseEvent = _lh68_graphic_mouse_release
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
    _lh69_prev_graphic_mouse_press = GraphicItem.mousePressEvent
    _lh69_prev_graphic_mouse_move = GraphicItem.mouseMoveEvent
    _lh69_prev_graphic_mouse_release = GraphicItem.mouseReleaseEvent
    _lh69_prev_graphic_hover_move = GraphicItem.hoverMoveEvent
except Exception:
    _lh69_prev_graphic_mouse_press = None
    _lh69_prev_graphic_mouse_move = None
    _lh69_prev_graphic_mouse_release = None
    _lh69_prev_graphic_hover_move = None


def _lh69_snap_len_px(win, value):
    step = _lh68_edit_grid_px(win)
    try:
        v = abs(float(value))
    except Exception:
        v = 0.0
    return max(step, _lh68_snap_px(win, v))


def _lh69_cursor_for_handle(item, h):
    """Return a cursor that matches the handle's visual scene direction."""
    if not h:
        return Qt.ArrowCursor
    if h == 'rot':
        return Qt.CrossCursor
    try:
        r = _lh68_local_rect(item)
        c = r.center()
        pts = _lh68_handle_points(item)
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


def _lh69_graphic_hover_move(self, event):
    try:
        if self.isSelected():
            h = 'rot' if _rotation_handle(self._rect(), self.window.grid_px * self.rotate_handle_factor).contains(event.pos()) else _hit_handle(self._handles(), event.pos())
            self.setCursor(QCursor(_lh69_cursor_for_handle(self, h)) if h else QCursor(Qt.ArrowCursor))
            return QGraphicsItem.hoverMoveEvent(self, event)
    except Exception:
        pass
    return _lh69_prev_graphic_hover_move(self, event)


def _lh69_graphic_mouse_press(self, event):
    if event.button() == Qt.LeftButton and self.isSelected():
        try:
            if _rotation_handle(self._rect(), self.window.grid_px * self.rotate_handle_factor).contains(event.pos()):
                return _lh69_prev_graphic_mouse_press(self, event)
            h = _hit_handle(self._handles(), event.pos())
            if h and str(getattr(self.model, 'shape', '') or '') not in ('line', 'arc'):
                pts = _lh68_handle_points(self)
                anchor_name = _lh68_opposite_handle(h)
                anchor_local = QPointF(pts.get(anchor_name, QPointF(0, 0)))
                st = self.sceneTransform()
                inv, ok = st.inverted()
                if not ok:
                    return _lh69_prev_graphic_mouse_press(self, event)
                self._lh69_resizing = h
                self._lh69_resize_anchor_name = anchor_name
                self._lh69_resize_anchor_local_start = QPointF(anchor_local)
                self._lh69_resize_anchor_scene = self.mapToScene(anchor_local)
                self._lh69_resize_scene_to_start_local = inv
                self._lh69_resize_start_transform = st
                self._lh69_resize_start = {
                    'x': _lh68_float(getattr(self.model, 'x', 0.0), 0.0),
                    'y': _lh68_float(getattr(self.model, 'y', 0.0), 0.0),
                    'w': _lh68_float(getattr(self.model, 'w', 0.0), 0.0),
                    'h': _lh68_float(getattr(self.model, 'h', 0.0), 0.0),
                    'sx': _lh68_float(getattr(self.model, 'scale_x', 1.0), 1.0),
                    'sy': _lh68_float(getattr(self.model, 'scale_y', 1.0), 1.0),
                    'rot': _lh68_float(getattr(self.model, 'rotation', 0.0), 0.0),
                    'pos': QPointF(self.pos()),
                }
                event.accept(); return
        except Exception:
            pass
    return _lh69_prev_graphic_mouse_press(self, event)


def _lh69_graphic_mouse_move(self, event):
    if getattr(self, '_lh69_resizing', None) and getattr(self, '_lh69_resize_start', None) is not None:
        try:
            win = self.window
            g = float(win.grid_px)
            hname = str(self._lh69_resizing)
            start = dict(self._lh69_resize_start)
            anchor_local = QPointF(self._lh69_resize_anchor_local_start)
            anchor_scene = QPointF(self._lh69_resize_anchor_scene)
            inv = self._lh69_resize_scene_to_start_local

            # Mouse in the unchanged local coordinate system from press time.
            # Do not scene-snap the mouse: only snap the resulting size.  This
            # avoids the two competing quantizers that caused the visible shake.
            mouse_local = inv.map(event.scenePos())
            old_w = max(1e-9, _lh68_float(start.get('w'), 0.0) * g)
            old_h = max(1e-9, _lh68_float(start.get('h'), 0.0) * g)
            old_left, old_top, old_right, old_bottom = 0.0, 0.0, old_w, old_h

            # Start with the old rect and only replace the axes controlled by
            # the active handle.
            left, right = old_left, old_right
            top, bottom = old_top, old_bottom
            if hname in ('l', 'tl', 'bl'):
                right = anchor_local.x()
                new_w = _lh69_snap_len_px(win, right - mouse_local.x())
                left = right - new_w
            elif hname in ('r', 'tr', 'br'):
                left = anchor_local.x()
                new_w = _lh69_snap_len_px(win, mouse_local.x() - left)
                right = left + new_w
            else:
                new_w = old_w

            if hname in ('t', 'tl', 'tr'):
                bottom = anchor_local.y()
                new_h = _lh69_snap_len_px(win, bottom - mouse_local.y())
                top = bottom - new_h
            elif hname in ('b', 'bl', 'br'):
                top = anchor_local.y()
                new_h = _lh69_snap_len_px(win, mouse_local.y() - top)
                bottom = top + new_h
            else:
                new_h = old_h

            # Restore the start transform before applying the newly computed
            # rect. This makes every mouse move absolute from the press state,
            # not cumulative from the previous frame.
            self.prepareGeometryChange()
            self.model.x = start['x']; self.model.y = start['y']
            self.model.w = max(_lh68_edit_grid_px(win), float(new_w)) / g
            self.model.h = max(_lh68_edit_grid_px(win), float(new_h)) / g
            self.model.scale_x = start['sx']; self.model.scale_y = start['sy']; self.model.rotation = start['rot']
            self.setPos(start['pos'])
            self.apply_transform_from_model()

            # Move the item origin to the transformed new upper-left and then
            # compensate so the fixed opposite handle remains exactly in place.
            start_transform = self._lh69_resize_start_transform
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
                self._lh69_resizing = None
            except Exception:
                pass
    return _lh69_prev_graphic_mouse_move(self, event)


def _lh69_graphic_mouse_release(self, event):
    try:
        self._lh69_resizing = None
        self._lh69_resize_start = None
        self._lh69_resize_anchor_local_start = None
        self._lh69_resize_anchor_scene = None
        self._lh69_resize_scene_to_start_local = None
        self._lh69_resize_start_transform = None
    except Exception:
        pass
    return _lh69_prev_graphic_mouse_release(self, event)

try:
    GraphicItem.hoverMoveEvent = _lh69_graphic_hover_move
    GraphicItem.mousePressEvent = _lh69_graphic_mouse_press
    GraphicItem.mouseMoveEvent = _lh69_graphic_mouse_move
    GraphicItem.mouseReleaseEvent = _lh69_graphic_mouse_release
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
    _lh70_prev_graphic_mouse_press = GraphicItem.mousePressEvent
    _lh70_prev_graphic_mouse_move = GraphicItem.mouseMoveEvent
    _lh70_prev_graphic_mouse_release = GraphicItem.mouseReleaseEvent
    _lh70_prev_graphic_hover_move = GraphicItem.hoverMoveEvent
except Exception:
    _lh70_prev_graphic_mouse_press = None
    _lh70_prev_graphic_mouse_move = None
    _lh70_prev_graphic_mouse_release = None
    _lh70_prev_graphic_hover_move = None


def _lh70_line_endpoint_points(item):
    g = float(item.window.grid_px)
    return {
        'start': QPointF(0.0, 0.0),
        'end': QPointF(_lh68_float(getattr(item.model, 'w', 0.0), 0.0) * g,
                       _lh68_float(getattr(item.model, 'h', 0.0), 0.0) * g),
    }


def _lh70_line_min_vector(win, vx, vy):
    """Keep line length at least one edit-grid step while preserving direction."""
    import math
    min_len = max(_lh68_edit_grid_px(win), 1e-9)
    length = math.hypot(float(vx), float(vy))
    if length >= min_len:
        return float(vx), float(vy)
    if length < 1e-9:
        return min_len, 0.0
    f = min_len / length
    return float(vx) * f, float(vy) * f


def _lh70_line_mouse_press(self, event):
    if event.button() == Qt.LeftButton and self.isSelected():
        try:
            if str(getattr(self.model, 'shape', '') or '') == 'line':
                # Rotation handle stays on the existing v68/v69 path.
                if _rotation_handle(self._rect(), self.window.grid_px * self.rotate_handle_factor).contains(event.pos()):
                    return _lh70_prev_graphic_mouse_press(self, event)
                h = _hit_handle(self._handles(), event.pos())
                if h in ('start', 'end'):
                    st = self.sceneTransform()
                    inv, ok = st.inverted()
                    if not ok:
                        return _lh70_prev_graphic_mouse_press(self, event)
                    pts = _lh70_line_endpoint_points(self)
                    fixed = 'end' if h == 'start' else 'start'
                    self._lh70_line_resizing = h
                    self._lh70_line_fixed_name = fixed
                    self._lh70_line_start_transform = st
                    self._lh70_line_scene_to_start_local = inv
                    self._lh70_line_fixed_scene = self.mapToScene(pts[fixed])
                    self._lh70_line_start_scene = self.mapToScene(pts['start'])
                    self._lh70_line_end_scene = self.mapToScene(pts['end'])
                    self._lh70_line_start = {
                        'x': _lh68_float(getattr(self.model, 'x', 0.0), 0.0),
                        'y': _lh68_float(getattr(self.model, 'y', 0.0), 0.0),
                        'w': _lh68_float(getattr(self.model, 'w', 0.0), 0.0),
                        'h': _lh68_float(getattr(self.model, 'h', 0.0), 0.0),
                        'sx': _lh68_float(getattr(self.model, 'scale_x', 1.0), 1.0),
                        'sy': _lh68_float(getattr(self.model, 'scale_y', 1.0), 1.0),
                        'rot': _lh68_float(getattr(self.model, 'rotation', 0.0), 0.0),
                        'pos': QPointF(self.pos()),
                    }
                    event.accept(); return
        except Exception:
            pass
    return _lh70_prev_graphic_mouse_press(self, event)


def _lh70_line_mouse_move(self, event):
    if getattr(self, '_lh70_line_resizing', None) and getattr(self, '_lh70_line_start', None) is not None:
        try:
            win = self.window
            g = float(win.grid_px)
            hname = str(self._lh70_line_resizing)
            start = dict(self._lh70_line_start)
            inv = self._lh70_line_scene_to_start_local
            start_transform = self._lh70_line_start_transform
            old_end_local = QPointF(start['w'] * g, start['h'] * g)

            # The mouse target is snapped in scene coordinates so line endpoints
            # land exactly on the visible edit grid.
            mouse_scene = _lh68_snap_scene_point(win, event.scenePos())
            mouse_local = inv.map(mouse_scene)

            self.prepareGeometryChange()
            self.model.scale_x = start['sx']; self.model.scale_y = start['sy']; self.model.rotation = start['rot']
            self.model.x = start['x']; self.model.y = start['y']
            self.setPos(QPointF(start['pos']))
            self.apply_transform_from_model()

            if hname == 'end':
                # Keep local start as object origin, change only endpoint vector.
                vx, vy = _lh70_line_min_vector(win, mouse_local.x(), mouse_local.y())
                self.model.w = vx / g
                self.model.h = vy / g
                self.setPos(QPointF(start['pos']))
                self.model.x = start['x']; self.model.y = start['y']
                self.apply_transform_from_model()
                # Correct any transform-origin side effect so the fixed start
                # endpoint is exactly where it was at mouse press.
                fixed_now = self.mapToScene(QPointF(0.0, 0.0))
                delta = self._lh70_line_fixed_scene - fixed_now
            else:
                # Move object origin to the new start point in the frozen local
                # frame. Endpoint vector becomes old_end - new_start.
                vx = old_end_local.x() - mouse_local.x()
                vy = old_end_local.y() - mouse_local.y()
                vx, vy = _lh70_line_min_vector(win, vx, vy)
                new_origin_scene = start_transform.map(QPointF(old_end_local.x() - vx, old_end_local.y() - vy))
                self.model.w = vx / g
                self.model.h = vy / g
                self.setPos(new_origin_scene)
                self.model.x = new_origin_scene.x() / g
                self.model.y = -new_origin_scene.y() / g
                self.apply_transform_from_model()
                fixed_now = self.mapToScene(QPointF(self.model.w * g, self.model.h * g))
                delta = self._lh70_line_fixed_scene - fixed_now

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
                self._lh70_line_resizing = None
            except Exception:
                pass
    return _lh70_prev_graphic_mouse_move(self, event)


def _lh70_line_mouse_release(self, event):
    try:
        self._lh70_line_resizing = None
        self._lh70_line_start = None
        self._lh70_line_fixed_scene = None
        self._lh70_line_start_transform = None
        self._lh70_line_scene_to_start_local = None
    except Exception:
        pass
    return _lh70_prev_graphic_mouse_release(self, event)


def _lh70_line_hover_move(self, event):
    try:
        if self.isSelected() and str(getattr(self.model, 'shape', '') or '') == 'line':
            h = 'rot' if _rotation_handle(self._rect(), self.window.grid_px * self.rotate_handle_factor).contains(event.pos()) else _hit_handle(self._handles(), event.pos())
            if h in ('start', 'end'):
                # Endpoint handles should feel like dragging along the visible
                # line direction; horizontal/vertical/diagonal cursor is chosen
                # from the transformed line vector.
                pts = _lh70_line_endpoint_points(self)
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
    return _lh70_prev_graphic_hover_move(self, event)

try:
    GraphicItem.mousePressEvent = _lh70_line_mouse_press
    GraphicItem.mouseMoveEvent = _lh70_line_mouse_move
    GraphicItem.mouseReleaseEvent = _lh70_line_mouse_release
    GraphicItem.hoverMoveEvent = _lh70_line_hover_move
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
    _lh71_prev_mouse_press = GraphicItem.mousePressEvent
    _lh71_prev_mouse_move = GraphicItem.mouseMoveEvent
    _lh71_prev_mouse_release = GraphicItem.mouseReleaseEvent
except Exception:
    _lh71_prev_mouse_press = None
    _lh71_prev_mouse_move = None
    _lh71_prev_mouse_release = None


def _lh71_line_len_px(w, h, g):
    try:
        return math.hypot(float(w) * float(g), float(h) * float(g))
    except Exception:
        return 0.0


def _lh71_snap_grid_units(win, value):
    try:
        step = win._edit_grid_step() if hasattr(win, '_edit_grid_step') else 0.5
        step = max(0.001, float(step or 0.001))
    except Exception:
        step = 0.5
    try:
        return round(float(value) / step) * step
    except Exception:
        return float(value or 0.0)


def _lh71_curve_mouse_press(self, event):
    if event.button() == Qt.LeftButton and self.isSelected():
        try:
            if str(getattr(self.model, 'shape', '') or '') == 'line':
                h = _hit_handle(self._handles(), event.pos())
                if h == 'curve':
                    st = self.sceneTransform()
                    inv, ok = st.inverted()
                    if not ok:
                        return _lh71_prev_mouse_press(self, event)
                    self._lh71_curve_resizing = True
                    self._lh71_curve_scene_to_start_local = inv
                    self._lh71_curve_start = {
                        'curve_radius': _lh68_float(getattr(self.model, 'curve_radius', 0.0), 0.0),
                        'w': _lh68_float(getattr(self.model, 'w', 0.0), 0.0),
                        'h': _lh68_float(getattr(self.model, 'h', 0.0), 0.0),
                    }
                    event.accept(); return
        except Exception:
            pass
    return _lh71_prev_mouse_press(self, event)


def _lh71_curve_mouse_move(self, event):
    # Dedicated curve handle: use the frozen local frame from press time.  This
    # prevents the curve apex from jumping when the line is rotated/flipped.
    if getattr(self, '_lh71_curve_resizing', False):
        try:
            win = self.window
            g = float(win.grid_px)
            inv = self._lh71_curve_scene_to_start_local
            p = inv.map(event.scenePos())
            w = _lh68_float(getattr(self.model, 'w', 0.0), 0.0) * g
            h = _lh68_float(getattr(self.model, 'h', 0.0), 0.0) * g
            mid_y = h / 2.0
            cr = (mid_y - p.y()) / g
            self.model.curve_radius = _lh71_snap_grid_units(win, cr)
            try:
                win.notify_canvas_model_changed()
            except Exception:
                try: win.live_refresh()
                except Exception: pass
            self.update(); event.accept(); return
        except Exception:
            try: self._lh71_curve_resizing = False
            except Exception: pass
    return _lh71_prev_mouse_move(self, event)


def _lh71_curve_mouse_release(self, event):
    try:
        self._lh71_curve_resizing = False
        self._lh71_curve_scene_to_start_local = None
        self._lh71_curve_start = None
    except Exception:
        pass
    return _lh71_prev_mouse_release(self, event)

try:
    GraphicItem.mousePressEvent = _lh71_curve_mouse_press
    GraphicItem.mouseMoveEvent = _lh71_curve_mouse_move
    GraphicItem.mouseReleaseEvent = _lh71_curve_mouse_release
except Exception:
    pass

# Patch v70 endpoint scaling to keep the curved-line apex proportional.  The
# existing v70 handler already handles natural endpoint direction; this wrapper
# records the old line length/curve before the handler, then applies the same
# uniform endpoint scale to curve_radius afterwards.
try:
    _lh71_prev_line_move = GraphicItem.mouseMoveEvent

    def _lh71_line_mouse_move_keep_curve(self, event):
        if getattr(self, '_lh70_line_resizing', None) and getattr(self, '_lh70_line_start', None) is not None:
            try:
                g = float(self.window.grid_px)
                old_w = _lh68_float(getattr(self, ' _unused', 0.0), 0.0)
                start = dict(getattr(self, '_lh70_line_start', {}) or {})
                old_len = _lh71_line_len_px(start.get('w', 0.0), start.get('h', 0.0), g)
                old_curve = _lh68_float(getattr(self.model, 'curve_radius', 0.0), 0.0)
                res = _lh71_prev_line_move(self, event)
                new_len = _lh71_line_len_px(getattr(self.model, 'w', 0.0), getattr(self.model, 'h', 0.0), g)
                if old_len > 1e-9 and abs(old_curve) > 1e-12:
                    self.model.curve_radius = _lh71_snap_grid_units(self.window, old_curve * (new_len / old_len))
                    try:
                        self.window.notify_canvas_model_changed()
                    except Exception:
                        try: self.window.live_refresh()
                        except Exception: pass
                    self.update()
                return res
            except Exception:
                pass
        return _lh71_prev_line_move(self, event)

    GraphicItem.mouseMoveEvent = _lh71_line_mouse_move_keep_curve
except Exception:
    pass

# Plain text robustness: commit safely and keep canvas object mode.  The old
# handlers assumed scene/window always exists during focus changes; after a live
# refresh that is not always true and plain text could get stuck or crash.
try:
    _lh71_prev_text_focus_out = TextItem.focusOutEvent
    _lh71_prev_text_key_press = TextItem.keyPressEvent

    def _lh71_commit_plain_text(self):
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

    def _lh71_text_key_press(self, event):
        try:
            if self.textInteractionFlags() != Qt.NoTextInteraction and event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
                _lh71_commit_plain_text(self)
                self.clearFocus()
                event.accept(); return
        except Exception:
            pass
        return _lh71_prev_text_key_press(self, event)

    def _lh71_text_focus_out(self, event):
        try:
            _lh71_commit_plain_text(self)
        except Exception:
            pass
        try:
            return QGraphicsTextItem.focusOutEvent(self, event)
        except Exception:
            return None

    TextItem.keyPressEvent = _lh71_text_key_press
    TextItem.focusOutEvent = _lh71_text_focus_out
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
    _lh85_prev_body_apply_transform = BodyItem.apply_transform_from_model
    _lh85_prev_body_hover_move = BodyItem.hoverMoveEvent
    _lh85_prev_body_mouse_press = BodyItem.mousePressEvent
    _lh85_prev_body_mouse_move = BodyItem.mouseMoveEvent
    _lh85_prev_body_mouse_release = BodyItem.mouseReleaseEvent
except Exception:
    _lh85_prev_body_apply_transform = None
    _lh85_prev_body_hover_move = None
    _lh85_prev_body_mouse_press = None
    _lh85_prev_body_mouse_move = None
    _lh85_prev_body_mouse_release = None


def _lh85_body_rect(item):
    g = float(getattr(item.window, 'grid_px', 1.0) or 1.0)
    w = _lh68_float(getattr(item.model, 'width', 0.0), 0.0) * g
    h = _lh68_float(getattr(item.model, 'height', 0.0), 0.0) * g
    return QRectF(0.0, 0.0, w, h).normalized()


def _lh85_body_apply_transform_from_model(self):
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
        r = _lh85_body_rect(self)
        self.setTransformOriginPoint(r.bottomLeft())
    except Exception:
        pass
    self.setTransform(QTransform().scale(sx, sy))
    self.setRotation(rot)


def _lh85_body_handle_points(item):
    r = _lh85_body_rect(item)
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


def _lh85_body_hover_move(self, event):
    try:
        if self.isSelected():
            h = 'rot' if _rotation_handle(self.rect(), self.window.grid_px * self.rotate_handle_factor).contains(event.pos()) else _hit_handle(self._handles(), event.pos())
            self.setCursor(QCursor(_lh69_cursor_for_handle(self, h)) if h else QCursor(Qt.ArrowCursor))
            return QGraphicsRectItem.hoverMoveEvent(self, event)
    except Exception:
        pass
    return _lh85_prev_body_hover_move(self, event)


def _lh85_body_snapshot(self):
    win = self.window
    unit = getattr(win, 'current_unit', None)
    body = self.model
    return {
        'x': _lh68_float(getattr(body, 'x', 0.0), 0.0),
        'y': _lh68_float(getattr(body, 'y', 0.0), 0.0),
        'w': _lh68_float(getattr(body, 'width', 0.0), 0.0),
        'h': _lh68_float(getattr(body, 'height', 0.0), 0.0),
        'sx': _lh68_float(getattr(body, 'scale_x', 1.0), 1.0),
        'sy': _lh68_float(getattr(body, 'scale_y', 1.0), 1.0),
        'rot': _lh68_float(getattr(body, 'rotation', 0.0), 0.0),
        'pos': QPointF(self.pos()),
        'pins': [(p, float(getattr(p, 'x', 0.0)), float(getattr(p, 'y', 0.0)), float(getattr(p, 'length', 0.0))) for p in getattr(unit, 'pins', [])],
        'texts': [(t, float(getattr(t, 'x', 0.0)), float(getattr(t, 'y', 0.0))) for t in getattr(unit, 'texts', [])],
        'attributes': [(t, float(getattr(t, 'x', 0.0)), float(getattr(t, 'y', 0.0))) for t in getattr(getattr(unit, 'body', None), 'attribute_texts', {}).values()],
        'graphics': [(gr, float(getattr(gr, 'x', 0.0)), float(getattr(gr, 'y', 0.0)), float(getattr(gr, 'w', 0.0)), float(getattr(gr, 'h', 0.0))) for gr in getattr(unit, 'graphics', [])],
    }


def _lh85_body_mouse_press(self, event):
    if event.button() == Qt.LeftButton and self.isSelected():
        try:
            if _rotation_handle(self.rect(), self.window.grid_px * self.rotate_handle_factor).contains(event.pos()):
                return _lh85_prev_body_mouse_press(self, event)
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
                    return _lh85_prev_body_mouse_press(self, event)
                pts = _lh85_body_handle_points(self)
                anchor_name = _lh68_opposite_handle(h)
                anchor_local = QPointF(pts.get(anchor_name, QPointF(0, 0)))
                self._lh85_body_resizing = h
                self._lh85_body_anchor_name = anchor_name
                self._lh85_body_anchor_local_start = QPointF(anchor_local)
                self._lh85_body_anchor_scene = self.mapToScene(anchor_local)
                self._lh85_body_scene_to_start_local = inv
                self._lh85_body_start_transform = st
                self._lh85_body_start = _lh85_body_snapshot(self)
                event.accept(); return
        except Exception:
            pass
    return _lh85_prev_body_mouse_press(self, event)


def _lh85_body_mouse_move(self, event):
    if getattr(self, '_lh85_body_resizing', None) and getattr(self, '_lh85_body_start', None) is not None:
        try:
            win = self.window
            g = float(win.grid_px)
            hname = str(self._lh85_body_resizing)
            start = dict(self._lh85_body_start)
            anchor_local = QPointF(self._lh85_body_anchor_local_start)
            anchor_scene = QPointF(self._lh85_body_anchor_scene)
            inv = self._lh85_body_scene_to_start_local
            mouse_local = inv.map(event.scenePos())

            old_w = max(1e-9, _lh68_float(start.get('w'), 0.0) * g)
            old_h = max(1e-9, _lh68_float(start.get('h'), 0.0) * g)
            left, right = 0.0, old_w
            top, bottom = 0.0, old_h

            if hname in ('l', 'tl', 'bl'):
                right = anchor_local.x()
                new_w = _lh69_snap_len_px(win, right - mouse_local.x())
                left = right - new_w
            elif hname in ('r', 'tr', 'br'):
                left = anchor_local.x()
                new_w = _lh69_snap_len_px(win, mouse_local.x() - left)
                right = left + new_w
            else:
                new_w = old_w

            if hname in ('t', 'tl', 'tr'):
                bottom = anchor_local.y()
                new_h = _lh69_snap_len_px(win, bottom - mouse_local.y())
                top = bottom - new_h
            elif hname in ('b', 'bl', 'br'):
                top = anchor_local.y()
                new_h = _lh69_snap_len_px(win, mouse_local.y() - top)
                bottom = top + new_h
            else:
                new_h = old_h

            # Rebuild BODY from the immutable drag-start state, then apply the
            # new geometry absolutely. Children are also recalculated from that
            # same immutable snapshot, avoiding cumulative scaling drift.
            body = self.model
            self.prepareGeometryChange()
            body.x = start['x']; body.y = start['y']
            body.width = max(_lh68_edit_grid_px(win), float(new_w)) / g
            body.height = max(_lh68_edit_grid_px(win), float(new_h)) / g
            body.scale_x = start['sx']; body.scale_y = start['sy']; body.rotation = start['rot']
            self.setPos(QPointF(start['pos']))
            self.setRect(0.0, 0.0, body.width * g, body.height * g)
            self.apply_transform_from_model()

            new_origin_scene = self._lh85_body_start_transform.map(QPointF(left, top))
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
                self._lh85_body_resizing = None
            except Exception:
                pass
    return _lh85_prev_body_mouse_move(self, event)


def _lh85_body_mouse_release(self, event):
    try:
        self._lh85_body_resizing = None
        self._lh85_body_start = None
        self._lh85_body_anchor_local_start = None
        self._lh85_body_anchor_scene = None
        self._lh85_body_scene_to_start_local = None
        self._lh85_body_start_transform = None
    except Exception:
        pass
    return _lh85_prev_body_mouse_release(self, event)

try:
    BodyItem.apply_transform_from_model = _lh85_body_apply_transform_from_model
    BodyItem.hoverMoveEvent = _lh85_body_hover_move
    BodyItem.mousePressEvent = _lh85_body_mouse_press
    BodyItem.mouseMoveEvent = _lh85_body_mouse_move
    BodyItem.mouseReleaseEvent = _lh85_body_mouse_release
except Exception:
    pass
