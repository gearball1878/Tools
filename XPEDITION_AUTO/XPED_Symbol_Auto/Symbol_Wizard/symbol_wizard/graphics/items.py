from __future__ import annotations
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QTransform
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
        if hasattr(self.model, 'font_size_grid'):
            self.model.font_size_grid = max(.1, self.model.font_size_grid * factor)
            g = self.scene().grid_px
            self.setFont(QFont(self.model.font_family, max(6, int(g * self.model.font_size_grid * .45))))
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
            self.window.schedule_scene_refresh(visual_only=True)
        self._last_model_pos = (self.model.x, self.model.y)

    def _handles(self):
        return _corner_handles(self.rect(), self.window.grid_px * self.handle_size_factor)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
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
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            g = self.window.grid_px
            r = QRectF(self.rect())
            p = event.pos()
            if 'r' in self._resizing:
                r.setRight(snap(p.x(), g))
            if 'b' in self._resizing:
                r.setBottom(snap(p.y(), g))
            if 'l' in self._resizing:
                new_left = snap(p.x(), g)
                dx_scene = new_left
                r.setLeft(new_left)
                self.moveBy(dx_scene, 0)
                r.translate(-dx_scene, 0)
            if 't' in self._resizing:
                new_top = snap(p.y(), g)
                dy_scene = new_top
                r.setTop(new_top)
                self.moveBy(0, dy_scene)
                r.translate(0, -dy_scene)
            r = r.normalized()
            w, h = max(g, r.width()), max(g, r.height())
            self.model.width, self.model.height = w / g, h / g
            self.setRect(0, 0, w, h)
            self.update_model_pos()
            self.window.dock_pins_to_body(self.window.current_unit)
            self.window.schedule_scene_refresh(visual_only=True)
            self.update()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._resizing = None
        self.window.schedule_scene_refresh()
        super().mouseReleaseEvent(event)

    def scale_selected(self, factor):
        self.model.width = max(1, self.model.width * factor)
        self.model.height = max(1, self.model.height * factor)
        g = self.window.grid_px
        self.setRect(0, 0, self.model.width * g, self.model.height * g)
        self.window.dock_pins_to_body(self.window.current_unit)
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
        painter.setFont(QFont('Arial', max(6, int(g * .28))))
        if m.visible_number:
            painter.drawText(QRectF(min(x1, x2), -.85 * g, abs(x2 - x1), .5 * g), Qt.AlignCenter, m.number)
        parts = []
        if m.visible_name: parts.append(m.name)
        if m.visible_function: parts.append(m.function)
        label = ' / '.join([x for x in parts if x])
        if label:
            painter.setFont(QFont('Arial', max(8, int(g * .35))))
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

    def scale_selected(self, factor):
        self.model.length = max(.1, self.model.length * factor)
        self.update()


class TextItem(TransformMixin, QGraphicsTextItem):
    def __init__(self, model, window):
        self.model = model
        self.window = window
        super().__init__(model.text)
        g = window.grid_px
        self.setPos(model.x * g, -model.y * g)
        self.setDefaultTextColor(rgb(model.color))
        self.setFont(QFont(model.font_family, max(6, int(g * model.font_size_grid * .45))))
        self.common_flags()
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setData(0, 'TEXT')
        self.apply_transform_from_model()

    def focusOutEvent(self, e):
        self.model.text = self.toPlainText()
        super().focusOutEvent(e)
        self.scene().window.live_refresh()

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
        g = window.grid_px
        self.setPos(model.x * g, -model.y * g)
        self.common_flags()
        self.setData(0, 'GRAPHIC')
        self.apply_transform_from_model()

    def _rect(self):
        g = self.window.grid_px
        return QRectF(0, 0, self.model.w * g, self.model.h * g).normalized()

    def boundingRect(self):
        g = self.window.grid_px
        return self._rect().adjusted(-.3 * g, -.3 * g, .3 * g, .3 * g)

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
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            g = self.window.grid_px
            p = event.pos()
            if 'r' in self._resizing:
                self.model.w = snap(p.x(), g) / g
            if 'b' in self._resizing:
                self.model.h = snap(p.y(), g) / g
            if 'l' in self._resizing:
                new_left = snap(p.x(), g)
                self.moveBy(new_left, 0)
                self.model.x = self.pos().x() / g
                self.model.w -= new_left / g
            if 't' in self._resizing:
                new_top = snap(p.y(), g)
                self.moveBy(0, new_top)
                self.model.y = -self.pos().y() / g
                self.model.h -= new_top / g
            if abs(self.model.w) < .1: self.model.w = .1
            if abs(self.model.h) < .1: self.model.h = .1
            self.prepareGeometryChange()
            self.window.schedule_scene_refresh(visual_only=True)
            self.update()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._resizing = None
        self.window.schedule_scene_refresh()
        super().mouseReleaseEvent(event)

    def update_model_pos(self):
        g = self.window.grid_px
        self.model.x = self.pos().x() / g
        self.model.y = -self.pos().y() / g

    def scale_selected(self, factor):
        self.model.w *= factor
        self.model.h *= factor
        self.prepareGeometryChange()
        self.update()
