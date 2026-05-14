from __future__ import annotations
import math
from PySide6.QtCore import QPointF, QRectF, Qt, QEvent
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QTransform, QTextCursor, QCursor, QPainterPath, QTextOption, QFontMetricsF
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
            self.window.update_attribute_items_for_unit()
        self._last_model_pos = (self.model.x, self.model.y)

    def _handles(self):
        return _corner_handles(self.rect(), self.window.grid_px * self.handle_size_factor)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if self.isSelected():
            painter.save()
            painter.setPen(QPen(QColor(40, 40, 40), 1))
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            for r in self._handles().values():
                painter.drawRect(r)
            painter.drawEllipse(_rotation_handle(self.rect(), self.window.grid_px * self.rotate_handle_factor))
            painter.restore()

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
            self.model.rotation = (round((self._rotate_start_model + delta) / 15.0) * 15.0) % 360
            self.apply_transform_from_model()
            self.window.live_refresh()
            event.accept(); return
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
        painter.setFont(QFont(m.number_font.family, max(6, int(g * m.number_font.size_grid * .45))))
        if m.visible_number:
            painter.drawText(QRectF(min(x1, x2), -.85 * g, abs(x2 - x1), .5 * g), Qt.AlignCenter, m.number)
        # Pin name and pin function are independent display attributes.
        # If both are visible, both are shown; if only one is visible, only that
        # value is shown. This keeps Template/Wizard visibility controls honest.
        parts = []
        if m.visible_name and str(m.name or '').strip():
            parts.append(m.name)
        if m.visible_function and str(m.function or '').strip():
            parts.append(m.function)
        label = ' / '.join([x for x in parts if x])
        if label:
            painter.setPen(pen_for(m.label_font.color, m.line_width, m.line_style, g))
            painter.setFont(QFont(m.label_font.family, max(8, int(g * m.label_font.size_grid * .45))))
            if m.side == PinSide.LEFT.value:
                painter.drawText(QRectF(.25 * g, -.35 * g, 6 * g, .7 * g), Qt.AlignVCenter | Qt.AlignLeft, label)
            else:
                painter.drawText(QRectF(-6.25 * g, -.35 * g, 6 * g, .7 * g), Qt.AlignVCenter | Qt.AlignRight, label)
        if self.isSelected():
            painter.setPen(QPen(QColor(80, 80, 80), 1, Qt.DashLine))
            painter.drawRect(self.boundingRect())
            s = self.window.grid_px * self.handle_size_factor
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            for r in _corner_handles(self.boundingRect(), s).values():
                painter.drawRect(r)
            painter.drawEllipse(_rotation_handle(self.boundingRect(), self.window.grid_px * self.rotate_handle_factor))

    def mousePressEvent(self, event):
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
            self.window.live_refresh()
            event.accept(); return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._rotating = False
        super().mouseReleaseEvent(event)

    def update_model_pos(self):
        g = self.window.grid_px
        self.model.x = self.pos().x() / g
        self.model.y = -self.pos().y() / g

    def scale_selected(self, factor):
        # Pin length is always quantized to full grid units.
        self.model.length = max(1.0, round(self.model.length * factor))
        self.update()


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

    def itemChange(self, change, value):
        # Text/attribute objects are positioned by their selected grid anchor
        # (left/center/right x upper/center/lower).  The anchor point, not the
        # item top-left, must snap to the grid.
        if change == QGraphicsItem.ItemPositionChange and self.scene():
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
        if m.shape == 'line':
            r = float(getattr(m, 'curve_radius', 0.0) or 0.0)
            if abs(r) > 1e-9:
                path = QPainterPath(QPointF(0, 0))
                path.quadTo(QPointF(m.w * g / 2, m.h * g / 2 - r * g), QPointF(m.w * g, m.h * g))
                painter.drawPath(path)
            else:
                painter.drawLine(QPointF(0, 0), QPointF(m.w * g, m.h * g))
        elif m.shape == 'rect':
            painter.drawRect(QRectF(0, 0, m.w * g, m.h * g))
        elif m.shape == 'ellipse':
            painter.drawEllipse(QRectF(0, 0, m.w * g, m.h * g))
        if self.isSelected():
            painter.save()
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
            self.window.live_refresh()
            event.accept(); return
        if self._resizing and self._resize_start is not None:
            g = self.window.grid_px
            p = QPointF(snap(event.scenePos().x(), g), snap(event.scenePos().y(), g))
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

