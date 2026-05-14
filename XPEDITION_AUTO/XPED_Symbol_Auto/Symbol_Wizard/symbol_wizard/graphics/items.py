from __future__ import annotations
from PySide6.QtCore import QPointF, QRectF, Qt, QEvent
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QTransform, QTextCursor, QPainterPath
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem
from symbol_wizard.models.document import PinSide, LineStyle
from symbol_wizard.rules.grid import snap


def rgb(c):
    return QColor(*c)


def pen_for(color, width_grid, style, grid_px):
    p = QPen(rgb(color), max(1, width_grid * grid_px))
    p.setStyle({
        LineStyle.SOLID.value: Qt.SolidLine,
        LineStyle.DASH.value: Qt.DashLine,
        LineStyle.DOT.value: Qt.DotLine,
        LineStyle.DASH_DOT.value: Qt.DashDotLine,
    }.get(style, Qt.SolidLine))
    return p


def qfont_for(family, size_px):
    """Create a canvas font from an already grid-derived pixel height."""
    try:
        px = float(size_px)
    except (TypeError, ValueError):
        px = 12.0
    font = QFont(family or 'Arial')
    font.setPixelSize(max(1, int(round(px))))
    return font


def qfont_from_grid(font_model, grid_px):
    """Return a font whose visible size follows the active grid.

    font_model.size_grid is authoritative: 0.9 means about 90% of one
    grid pitch, independent of OS DPI/point-size settings. size_pt is kept
    synchronized as a compatibility/export field but is not used for canvas
    sizing.
    """
    try:
        sg = float(getattr(font_model, 'size_grid', 0.9) or 0.9)
    except (TypeError, ValueError):
        sg = 0.9
    px = float(grid_px) * sg * 1.28
    try:
        font_model.size_pt = round(px, 2)
    except Exception:
        pass
    return qfont_for(getattr(font_model, 'family', 'Arial'), px)


class TransformMixin:
    handle_size_factor = .22

    def apply_transform_from_model(self):
        def f(name, default):
            try:
                return float(getattr(self.model, name, default) or default)
            except (TypeError, ValueError):
                return default
        sx, sy, rot = f('scale_x', 1.0), f('scale_y', 1.0), f('rotation', 0.0)
        self.model.scale_x, self.model.scale_y, self.model.rotation = sx, sy, rot
        self.setTransform(QTransform().scale(sx, sy))
        self.setRotation(rot)

    def common_flags(self):
        self.setAcceptHoverEvents(True)
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
            | QGraphicsItem.ItemIsFocusable
        )

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            g = self.scene().grid_px
            return QPointF(snap(value.x(), g), snap(value.y(), g))
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.update_model_pos()
            # Do not rebuild the scene while dragging; this keeps canvas editing smooth.
            self.scene().window.live_refresh()
        return super().itemChange(change, value)

    def update_model_pos(self):
        pass

    def rotate_by(self, deg):
        try:
            cur = float(getattr(self.model, 'rotation', 0.0) or 0.0)
        except (TypeError, ValueError):
            cur = 0.0
        self.model.rotation = (cur + float(deg)) % 360
        self.setRotation(float(self.model.rotation))
        self.update()

    def scale_selected(self, factor):
        if hasattr(self.model, 'font_size_pt'):
            self.model.font_size_pt = max(1.0, self.model.font_size_pt * factor)
            self.model.font_size_grid = round(self.model.font_size_pt / 7.2, 3)
            self.setFont(qfont_for(self.model.font_family, self.model.font_size_pt))
        elif hasattr(self.model, 'length'):
            self.model.length = max(.1, self.model.length * factor)
        self.update()


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


class BodyItem(TransformMixin, QGraphicsRectItem):
    def __init__(self, model, window):
        self.model = model
        self.window = window
        self._resizing = None
        self._resize_anchor_scene = None
        self._resize_start = None
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
            self.window.update_attribute_items_for_unit()
        self._last_model_pos = (self.model.x, self.model.y)

    def _handles(self):
        return _corner_handles(self.rect(), self.window.grid_px * self.handle_size_factor)

    def paint(self, painter, option, widget=None):
        painter.save()
        painter.setPen(pen_for(self.model.color, self.model.line_width, self.model.line_style, self.window.grid_px))
        painter.setBrush(QBrush(Qt.NoBrush))
        rect = self.rect()
        shape = getattr(self.model, 'body_shape', 'rect') or 'rect'
        if shape == 'resistor':
            y = rect.center().y(); w = rect.width(); h = rect.height(); x0 = rect.left(); step = w / 8.0
            pts = [QPointF(x0, y), QPointF(x0+step, rect.top()), QPointF(x0+2*step, rect.bottom()), QPointF(x0+3*step, rect.top()), QPointF(x0+4*step, rect.bottom()), QPointF(x0+5*step, rect.top()), QPointF(x0+6*step, rect.bottom()), QPointF(x0+7*step, rect.top()), QPointF(rect.right(), y)]
            for a, b in zip(pts, pts[1:]): painter.drawLine(a, b)
        elif shape == 'capacitor':
            cx = rect.center().x(); gap = rect.width() * .12
            painter.drawLine(QPointF(cx-gap, rect.top()), QPointF(cx-gap, rect.bottom()))
            painter.drawLine(QPointF(cx+gap, rect.top()), QPointF(cx+gap, rect.bottom()))
        elif shape == 'inductor':
            n = 4; seg = rect.width()/n
            for i in range(n):
                painter.drawArc(QRectF(rect.left()+i*seg, rect.top(), seg, rect.height()), 0, 180*16)
        elif shape == 'diode':
            path = QPainterPath(); path.moveTo(rect.left(), rect.bottom()); path.lineTo(rect.left(), rect.top()); path.lineTo(rect.right()*0.75+rect.left()*0.25, rect.center().y()); path.closeSubpath(); painter.drawPath(path)
            x = rect.right()*0.75+rect.left()*0.25; painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        elif shape == 'battery':
            cx = rect.center().x(); painter.drawLine(QPointF(cx-rect.width()*.18, rect.top()), QPointF(cx-rect.width()*.18, rect.bottom()))
            painter.drawLine(QPointF(cx+rect.width()*.18, rect.top()+rect.height()*.2), QPointF(cx+rect.width()*.18, rect.bottom()-rect.height()*.2))
        elif shape == 'transformer':
            painter.drawLine(QPointF(rect.center().x()-rect.width()*.06, rect.top()), QPointF(rect.center().x()-rect.width()*.06, rect.bottom()))
            painter.drawLine(QPointF(rect.center().x()+rect.width()*.06, rect.top()), QPointF(rect.center().x()+rect.width()*.06, rect.bottom()))
            for side in (-1, 1):
                x0 = rect.center().x() + side*rect.width()*.15
                for i in range(4):
                    painter.drawArc(QRectF(x0 + side*i*rect.width()*.08 - rect.width()*.04, rect.top()+i*rect.height()/4, rect.width()*.08, rect.height()/4), 90*16 if side<0 else -90*16, 180*16)
        elif shape == 'transistor':
            painter.drawEllipse(rect); painter.drawLine(rect.center(), QPointF(rect.right(), rect.top()+rect.height()*.25)); painter.drawLine(rect.center(), QPointF(rect.right(), rect.bottom()-rect.height()*.25)); painter.drawLine(QPointF(rect.left(), rect.center().y()), rect.center())
        elif shape == 'fuse':
            painter.drawLine(QPointF(rect.left(), rect.center().y()), QPointF(rect.right(), rect.center().y()))
            painter.drawRoundedRect(rect.adjusted(rect.width()*.2, 0, -rect.width()*.2, 0), rect.height()*.25, rect.height()*.25)
        elif shape == 'connector':
            painter.drawRect(rect); r = min(rect.width(), rect.height())*.08
            count = max(2, int(rect.height() / max(1, self.window.grid_px*2)))
            for i in range(count):
                y = rect.top() + (i+1)*rect.height()/(count+1); painter.drawEllipse(QPointF(rect.center().x(), y), r, r)
        elif shape == 'opamp':
            path = QPainterPath(); path.moveTo(rect.left(), rect.top()); path.lineTo(rect.left(), rect.bottom()); path.lineTo(rect.right(), rect.center().y()); path.closeSubpath(); painter.drawPath(path)
        elif shape == 'circle':
            painter.drawEllipse(rect)
        else:
            painter.drawRect(rect)
        painter.restore()
        if self.isSelected():
            painter.save()
            painter.setPen(QPen(QColor(40, 40, 40), 1))
            painter.setBrush(QBrush(QColor(40, 40, 40)))
            for r in self._handles().values():
                painter.drawRect(r)
            painter.restore()

    def mousePressEvent(self, event):
        if self.isSelected():
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
                    'graphics': [(gr, float(gr.x), float(gr.y), float(gr.w), float(gr.h)) for gr in self.window.current_unit.graphics],
                }
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing and self._resize_start is not None:
            g = self.window.grid_px
            p = QPointF(snap(event.scenePos().x(), g), snap(event.scenePos().y(), g))
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
            self.window.update_attribute_items_for_unit()
            self.window.live_refresh()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._resizing = None
        self._resize_anchor_scene = None
        self._resize_start = None
        self.window.enforce_symbol_size_limit(silent=True)
        self.window.update_current_unit_canvas_positions()
        self.window.update_attribute_items_for_unit()
        self.window.rebuild_tree()
        self.window.rebuild_pin_table()
        self.scene().update()
        super().mouseReleaseEvent(event)

    def scale_selected(self, factor):
        st = {
            'x': float(self.model.x), 'y': float(self.model.y),
            'w': float(self.model.width), 'h': float(self.model.height),
            'pins': [(p, float(p.x), float(p.y), float(p.length)) for p in self.window.current_unit.pins],
            'texts': [(t, float(t.x), float(t.y)) for t in self.window.current_unit.texts],
            'graphics': [(gr, float(gr.x), float(gr.y), float(gr.w), float(gr.h)) for gr in self.window.current_unit.graphics],
        }
        self.model.width = max(1, round(self.model.width * factor))
        self.model.height = max(1, round(self.model.height * factor))
        g = self.window.grid_px
        self.setRect(0, 0, self.model.width * g, self.model.height * g)
        self.window.scale_current_unit_children_from_body_resize(st, self.model)
        self.window.update_current_unit_canvas_positions()
        self.window.update_attribute_items_for_unit()
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
        g = self.window.grid_px
        return QRectF(-6 * g, -1.2 * g, 12 * g, 2.4 * g)

    def paint(self, painter, option, widget=None):
        g, m = self.window.grid_px, self.model
        L = m.length * g
        painter.setPen(pen_for(m.color, m.line_width, m.line_style, g))
        painter.setBrush(QBrush(Qt.NoBrush))
        x1, x2 = (-L, 0) if m.side == PinSide.LEFT.value else (0, L)
        painter.drawLine(QPointF(x1, 0), QPointF(x2, 0))
        if m.inverted:
            r = .18 * g
            painter.drawEllipse(QPointF((-r if m.side == PinSide.LEFT.value else r), 0), r, r)
        painter.setPen(pen_for(m.number_font.color, m.line_width, m.line_style, g))
        painter.setFont(qfont_from_grid(m.number_font, g))
        if m.visible_number:
            painter.drawText(QRectF(min(x1, x2), -.85 * g, abs(x2 - x1), .5 * g), Qt.AlignCenter, m.number)
        # Display rule: if a dedicated function exists, show function; otherwise show pin name.
        # Visibility flags can still hide either part explicitly.
        has_function = bool(str(m.function or '').strip())
        parts = []
        if has_function:
            if m.visible_function: parts.append(m.function)
        else:
            if m.visible_name: parts.append(m.name)
        label = ' / '.join([x for x in parts if x])
        if label:
            painter.setPen(pen_for(m.label_font.color, m.line_width, m.line_style, g))
            painter.setFont(qfont_from_grid(m.label_font, g))
            if m.side == PinSide.LEFT.value:
                painter.drawText(QRectF(.25 * g, -.35 * g, 6 * g, .7 * g), Qt.AlignVCenter | Qt.AlignLeft, label)
            else:
                painter.drawText(QRectF(-6.25 * g, -.35 * g, 6 * g, .7 * g), Qt.AlignVCenter | Qt.AlignRight, label)
        if self.isSelected():
            painter.setPen(QPen(QColor(80, 80, 80), 1, Qt.DashLine))
            painter.drawRect(self.boundingRect())

    def update_model_pos(self):
        g = self.window.grid_px
        self.model.x = self.pos().x() / g
        self.model.y = -self.pos().y() / g

    def rotate_by(self, deg):
        # Pins rotate only in 90° steps. Side still defines left/right docking.
        try:
            cur = float(getattr(self.model, 'rotation', 0.0) or 0.0)
        except (TypeError, ValueError):
            cur = 0.0
        self.model.rotation = (round((cur + float(deg)) / 90.0) * 90) % 360
        self.model.scale_x = 1.0
        self.model.scale_y = 1.0
        self.setRotation(float(self.model.rotation))
        self.setTransform(QTransform())
        self.update()

    def scale_selected(self, factor):
        # Pin length is always quantized to full grid units.
        self.model.length = max(1.0, round(self.model.length * factor))
        self.update()


class TextItem(TransformMixin, QGraphicsTextItem):
    def __init__(self, model, window):
        self.model = model
        self.window = window
        super().__init__(model.text)
        g = window.grid_px
        self.setPos(model.x * g, -model.y * g)
        self.setDefaultTextColor(rgb(model.color))
        self.setFont(qfont_for(model.font_family, model.font_size_pt))
        self.common_flags()
        # Text remains movable/selectable in edit mode. Text editing starts only on double click.
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        self.setData(0, 'TEXT')
        self.apply_transform_from_model()

    def mouseDoubleClickEvent(self, event):
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFocus(Qt.MouseFocusReason)
        cursor = self.textCursor()
        cursor.select(QTextCursor.Document)
        self.setTextCursor(cursor)
        event.accept()

    def keyPressEvent(self, event):
        if self.textInteractionFlags() != Qt.NoTextInteraction and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.model.text = self.toPlainText()
            self.setTextInteractionFlags(Qt.NoTextInteraction)
            self.clearFocus()
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
        # Commit current text and return to movable/selectable canvas mode.
        self.model.text = self.toPlainText()
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        super().focusOutEvent(e)

    def update_model_pos(self):
        g = self.window.grid_px
        self.model.x = self.pos().x() / g
        self.model.y = -self.pos().y() / g
        self.model.text = self.toPlainText()



class GraphicItem(TransformMixin, QGraphicsItem):
    def __init__(self, model, window):
        super().__init__()
        self.model = model
        self.window = window
        self._resizing = None
        self._resize_anchor_scene = None
        self._resize_start = None
        g = window.grid_px
        self.setPos(model.x * g, -model.y * g)
        self.common_flags()
        self.setData(0, 'GRAPHIC')
        self.apply_transform_from_model()

    def _raw_rect(self):
        g = self.window.grid_px
        return QRectF(0, 0, self.model.w * g, self.model.h * g)

    def _rect(self):
        r = self._raw_rect().normalized()
        if r.width() < 1:
            r.adjust(-.5, 0, .5, 0)
        if r.height() < 1:
            r.adjust(0, -.5, 0, .5)
        return r

    def boundingRect(self):
        g = self.window.grid_px
        return self._rect().adjusted(-.35 * g, -.35 * g, .35 * g, .35 * g)

    def _handles(self):
        return _corner_handles(self._rect(), self.window.grid_px * self.handle_size_factor)

    def paint(self, painter, option, widget=None):
        g, m = self.window.grid_px, self.model
        painter.setPen(pen_for(m.style.stroke, m.style.line_width, m.style.line_style, g))
        painter.setBrush(QBrush(rgb(m.style.fill)) if m.style.fill else QBrush(Qt.NoBrush))
        if m.shape == 'line':
            painter.drawLine(QPointF(0, 0), QPointF(m.w * g, m.h * g))
        elif m.shape == 'rect':
            painter.drawRect(QRectF(0, 0, m.w * g, m.h * g))
        elif m.shape == 'ellipse':
            painter.drawEllipse(QRectF(0, 0, m.w * g, m.h * g))
        if self.isSelected():
            painter.save()
            painter.setPen(QPen(QColor(80, 80, 80), 1, Qt.DashLine))
            painter.drawRect(self._rect())
            painter.setBrush(QBrush(QColor(40, 40, 40)))
            painter.setPen(QPen(QColor(40, 40, 40), 1))
            for r in self._handles().values():
                painter.drawRect(r)
            painter.restore()

    def mousePressEvent(self, event):
        if self.isSelected():
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
        if self._resizing and self._resize_start is not None:
            g = self.window.grid_px
            p = QPointF(snap(event.scenePos().x(), g), snap(event.scenePos().y(), g))
            st = self._resize_start
            left = st['x'] * g
            top = -st['y'] * g
            right = left + st['w'] * g
            bottom = top + st['h'] * g

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
            self.window.live_refresh()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
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

    def scale_selected(self, factor):
        self.model.w = round(self.model.w * factor * 2) / 2
        self.model.h = round(self.model.h * factor * 2) / 2
        self.prepareGeometryChange()
        self.update()


class OriginItem(QGraphicsItem):
    """Movable symbol origin marker. Coordinates are stored in grid units on SymbolModel."""
    def __init__(self, symbol, window):
        super().__init__()
        self.symbol = symbol
        self.window = window
        g = window.grid_px
        self.setPos(float(getattr(symbol, 'origin_x', 0.0)) * g, -float(getattr(symbol, 'origin_y', 0.0)) * g)
        self.setZValue(10000)
        self.setAcceptHoverEvents(True)
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setData(0, 'ORIGIN')

    def boundingRect(self):
        return QRectF(-12, -12, 24, 24)

    def paint(self, painter, option, widget=None):
        painter.save()
        painter.setPen(QPen(QColor(20, 120, 220), 2))
        painter.setBrush(QBrush(QColor(20, 120, 220, 60)))
        painter.drawLine(QPointF(-10, 0), QPointF(10, 0))
        painter.drawLine(QPointF(0, -10), QPointF(0, 10))
        painter.drawEllipse(QPointF(0, 0), 5, 5)
        painter.restore()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            g = self.scene().grid_px
            return QPointF(snap(value.x(), g), snap(value.y(), g))
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            g = self.scene().grid_px
            self.symbol.origin_x = self.pos().x() / g
            self.symbol.origin_y = -self.pos().y() / g
            self.symbol.origin = 'custom'
            self.scene().window.scene.update()
        return super().itemChange(change, value)
