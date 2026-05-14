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
        self._resize_anchor_scene = None
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
                scene_rect = self.mapRectToScene(self.rect())
                opposite = {
                    'tl': scene_rect.bottomRight(), 'tr': scene_rect.bottomLeft(),
                    'bl': scene_rect.topRight(), 'br': scene_rect.topLeft(),
                    'l': QPointF(scene_rect.right(), scene_rect.center().y()),
                    'r': QPointF(scene_rect.left(), scene_rect.center().y()),
                    't': QPointF(scene_rect.center().x(), scene_rect.bottom()),
                    'b': QPointF(scene_rect.center().x(), scene_rect.top()),
                }
                self._resize_anchor_scene = opposite[h]
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing and self._resize_anchor_scene is not None:
            g = self.window.grid_px
            p = event.scenePos()
            p = QPointF(snap(p.x(), g), snap(p.y(), g))
            a = self._resize_anchor_scene
            old_x, old_y = self.model.x, self.model.y

            if self._resizing in ('l', 'r'):
                top = self.sceneBoundingRect().top()
                bottom = self.sceneBoundingRect().bottom()
                left, right = sorted([a.x(), p.x()])
            elif self._resizing in ('t', 'b'):
                left = self.sceneBoundingRect().left()
                right = self.sceneBoundingRect().right()
                top, bottom = sorted([a.y(), p.y()])
            else:
                left, right = sorted([a.x(), p.x()])
                top, bottom = sorted([a.y(), p.y()])

            min_size = g
            if right - left < min_size:
                if p.x() < a.x():
                    left = right - min_size
                else:
                    right = left + min_size
            if bottom - top < min_size:
                if p.y() < a.y():
                    top = bottom - min_size
                else:
                    bottom = top + min_size

            self.prepareGeometryChange()
            self.setPos(left, top)
            self.setRect(0, 0, right - left, bottom - top)
            self.model.x = left / g
            self.model.y = -top / g
            self.model.width = (right - left) / g
            self.model.height = (bottom - top) / g
            dx, dy = self.model.x - old_x, self.model.y - old_y
            if abs(dx) > 1e-9 or abs(dy) > 1e-9:
                self.window.move_current_unit_group(dx, dy, source_body=self.model)
            self._last_model_pos = (self.model.x, self.model.y)
            self.window.dock_pins_to_body(self.window.current_unit)
            self.window.live_refresh()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._resizing = None
        self._resize_anchor_scene = None
        self.window.enforce_symbol_size_limit(silent=True)
        self.window.rebuild_tree()
        self.window.rebuild_pin_table()
        self.scene().update()
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
        # Text remains movable/selectable in edit mode. Text editing starts only on double click.
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        self.setData(0, 'TEXT')
        self.apply_transform_from_model()

    def mouseDoubleClickEvent(self, event):
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFocus(Qt.MouseFocusReason)
        cursor = self.textCursor()
        cursor.select(cursor.WordUnderCursor)
        self.setTextCursor(cursor)
        event.accept()

    def focusOutEvent(self, e):
        self.model.text = self.toPlainText()
        self.setTextInteractionFlags(Qt.NoTextInteraction)
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
        self._resize_anchor_scene = None
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
                scene_rect = self.mapRectToScene(self._rect())
                opposite = {
                    'tl': scene_rect.bottomRight(), 'tr': scene_rect.bottomLeft(),
                    'bl': scene_rect.topRight(), 'br': scene_rect.topLeft(),
                    'l': QPointF(scene_rect.right(), scene_rect.center().y()),
                    'r': QPointF(scene_rect.left(), scene_rect.center().y()),
                    't': QPointF(scene_rect.center().x(), scene_rect.bottom()),
                    'b': QPointF(scene_rect.center().x(), scene_rect.top()),
                }
                self._resize_anchor_scene = opposite[h]
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing and self._resize_anchor_scene is not None:
            g = self.window.grid_px
            p = event.scenePos()
            p = QPointF(snap(p.x(), g), snap(p.y(), g))
            a = self._resize_anchor_scene
            cur = self.sceneBoundingRect()
            if self._resizing in ('l', 'r'):
                top, bottom = cur.top(), cur.bottom()
                left, right = sorted([a.x(), p.x()])
            elif self._resizing in ('t', 'b'):
                left, right = cur.left(), cur.right()
                top, bottom = sorted([a.y(), p.y()])
            else:
                left, right = sorted([a.x(), p.x()])
                top, bottom = sorted([a.y(), p.y()])

            # Lines may be perfectly horizontal or vertical; other shapes keep a small visible size.
            min_size = 0 if self.model.shape == 'line' else g * .25
            if right - left < min_size:
                right = left + min_size
            if bottom - top < min_size:
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
        self.window.enforce_symbol_size_limit(silent=True)
        self.window.rebuild_tree()
        self.scene().update()
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

