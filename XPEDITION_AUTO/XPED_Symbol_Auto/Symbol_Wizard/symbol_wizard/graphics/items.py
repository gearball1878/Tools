from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPen, QBrush
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem

from symbol_wizard.config import PX_PER_INCH
from symbol_wizard.models.document import GraphicObjectModel, GraphicType, PinSide, PinModel, SymbolBodyModel, TextModel
from symbol_wizard.rules.grid import snap


def rgb_to_qcolor(rgb) -> QColor:
    return QColor(rgb[0], rgb[1], rgb[2])


def qcolor_to_rgb(color: QColor):
    return (color.red(), color.green(), color.blue())


class SnapMixin:
    model = None

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            editor = self.scene().editor
            grid_px = editor.document.grid_inch * PX_PER_INCH
            return QPointF(snap(value.x(), grid_px), snap(value.y(), grid_px))
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.update_model_from_item()
            self.scene().editor.refresh_after_model_change()
        return super().itemChange(change, value)

    def update_model_from_item(self):
        pass


class SymbolBodyItem(SnapMixin, QGraphicsRectItem):
    def __init__(self, model: SymbolBodyModel, editor):
        self.model = model
        self.editor = editor
        grid_px = editor.document.grid_inch * PX_PER_INCH
        super().__init__(0, 0, model.width * grid_px, model.height * grid_px)
        self.setPos(model.x * grid_px, -model.y * grid_px)
        self.setPen(QPen(rgb_to_qcolor(model.color), 2))
        self.setBrush(QBrush(Qt.NoBrush))
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setData(0, "SYMBOL_BODY")

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        grid_px = self.editor.document.grid_inch * PX_PER_INCH
        painter.setPen(QPen(rgb_to_qcolor(self.model.color), 1))

        refdes = self.model.attributes.get("RefDes", "")
        if "RefDes" in self.model.visible_attributes and refdes:
            font_px = min(grid_px * 0.9, PX_PER_INCH * 0.100)
            painter.setFont(QFont("Arial", max(6, int(font_px * 0.45))))
            rect = QRectF(0, -1.2 * grid_px, self.rect().width(), grid_px)
            align = Qt.AlignBottom | (Qt.AlignLeft if self.model.refdes_align == "left" else Qt.AlignRight)
            painter.drawText(rect, align, refdes)

        visible = [k for k in self.model.visible_attributes if k != "RefDes" and self.model.attributes.get(k, "")]
        if visible:
            painter.setFont(QFont("Arial", max(6, int(grid_px * 0.35))))
            y = self.rect().height() + 0.2 * grid_px
            for key in visible:
                text = self.model.attributes.get(key, "")
                rect = QRectF(0, y, self.rect().width(), grid_px)
                align = Qt.AlignTop | (Qt.AlignLeft if self.model.body_attr_align == "left" else Qt.AlignRight)
                painter.drawText(rect, align, text)
                y += grid_px

    def update_model_from_item(self):
        grid_px = self.editor.document.grid_inch * PX_PER_INCH
        self.model.x = self.pos().x() / grid_px
        self.model.y = -self.pos().y() / grid_px


class PinItem(SnapMixin, QGraphicsItem):
    def __init__(self, model: PinModel, editor):
        super().__init__()
        self.model = model
        self.editor = editor
        grid_px = editor.document.grid_inch * PX_PER_INCH
        self.setPos(model.x * grid_px, -model.y * grid_px)
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setData(0, "PIN")

    def boundingRect(self) -> QRectF:
        grid_px = self.editor.document.grid_inch * PX_PER_INCH
        return QRectF(-4 * grid_px, -1.5 * grid_px, 8 * grid_px, 3 * grid_px)

    def paint(self, painter, option, widget=None):
        grid_px = self.editor.document.grid_inch * PX_PER_INCH
        length_px = self.model.length * grid_px
        painter.setPen(QPen(rgb_to_qcolor(self.model.color), 2))
        painter.setBrush(QBrush(Qt.NoBrush))

        if self.model.side == PinSide.LEFT.value:
            x1, x2 = -length_px, 0
            circle_x = -0.18 * grid_px
        else:
            x1, x2 = 0, length_px
            circle_x = 0.18 * grid_px

        painter.drawLine(QPointF(x1, 0), QPointF(x2, 0))
        if self.model.inverted:
            painter.drawEllipse(QPointF(circle_x, 0), 0.18 * grid_px, 0.18 * grid_px)

        if self.model.visible_number:
            painter.setFont(QFont("Arial", max(6, int(grid_px * 0.28))))
            painter.drawText(QRectF(min(x1, x2), -0.85 * grid_px, abs(x2 - x1), 0.5 * grid_px), Qt.AlignCenter, self.model.number)

        label_parts = []
        if self.model.visible_name:
            label_parts.append(self.model.name)
        if self.model.visible_function:
            label_parts.append(self.model.function)
        label = " / ".join([p for p in label_parts if p])
        if label:
            painter.setFont(QFont("Arial", max(8, int(grid_px * 0.35))))
            if self.model.side == PinSide.LEFT.value:
                label_rect = QRectF(0.25 * grid_px, -0.35 * grid_px, 5 * grid_px, 0.7 * grid_px)
                align = Qt.AlignVCenter | Qt.AlignLeft
            else:
                label_rect = QRectF(-5.25 * grid_px, -0.35 * grid_px, 5 * grid_px, 0.7 * grid_px)
                align = Qt.AlignVCenter | Qt.AlignRight
            painter.drawText(label_rect, align, label)

    def update_model_from_item(self):
        grid_px = self.editor.document.grid_inch * PX_PER_INCH
        self.model.x = self.pos().x() / grid_px
        self.model.y = -self.pos().y() / grid_px


class TextGraphicsItem(SnapMixin, QGraphicsTextItem):
    def __init__(self, model: TextModel, editor):
        self.model = model
        self.editor = editor
        super().__init__(model.text)
        grid_px = editor.document.grid_inch * PX_PER_INCH
        self.setPos(model.x * grid_px, -model.y * grid_px)
        self.setDefaultTextColor(rgb_to_qcolor(model.color))
        self.setFont(QFont(model.font_family, max(6, int(grid_px * model.font_size_grid * 0.45))))
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setData(0, "TEXT")

    def focusOutEvent(self, event):
        self.model.text = self.toPlainText()
        super().focusOutEvent(event)

    def update_model_from_item(self):
        grid_px = self.editor.document.grid_inch * PX_PER_INCH
        self.model.x = self.pos().x() / grid_px
        self.model.y = -self.pos().y() / grid_px
        self.model.text = self.toPlainText()


class GraphicObjectItem(SnapMixin, QGraphicsItem):
    def __init__(self, model: GraphicObjectModel, editor):
        super().__init__()
        self.model = model
        self.editor = editor
        grid_px = editor.document.grid_inch * PX_PER_INCH
        self.setPos(model.x * grid_px, -model.y * grid_px)
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setData(0, "GRAPHIC")

    def boundingRect(self) -> QRectF:
        grid_px = self.editor.document.grid_inch * PX_PER_INCH
        w = max(0.5, self.model.width) * grid_px
        h = max(0.5, self.model.height) * grid_px
        if self.model.graphic_type == GraphicType.LINE.value:
            x2 = (self.model.x2 - self.model.x) * grid_px
            y2 = -(self.model.y2 - self.model.y) * grid_px
            return QRectF(min(0, x2) - 10, min(0, y2) - 10, abs(x2) + 20, abs(y2) + 20)
        return QRectF(-5, -5, w + 10, h + 10)

    def paint(self, painter, option, widget=None):
        grid_px = self.editor.document.grid_inch * PX_PER_INCH
        painter.setPen(QPen(rgb_to_qcolor(self.model.color), self.model.line_width))
        painter.setBrush(QBrush(Qt.NoBrush))
        if self.model.graphic_type == GraphicType.LINE.value:
            x2 = (self.model.x2 - self.model.x) * grid_px
            y2 = -(self.model.y2 - self.model.y) * grid_px
            painter.drawLine(QPointF(0, 0), QPointF(x2, y2))
        elif self.model.graphic_type == GraphicType.ELLIPSE.value:
            painter.drawEllipse(QRectF(0, 0, self.model.width * grid_px, self.model.height * grid_px))
        else:
            painter.drawRect(QRectF(0, 0, self.model.width * grid_px, self.model.height * grid_px))

    def update_model_from_item(self):
        grid_px = self.editor.document.grid_inch * PX_PER_INCH
        dx = self.pos().x() / grid_px - self.model.x
        dy = -self.pos().y() / grid_px - self.model.y
        self.model.x += dx
        self.model.y += dy
        if self.model.graphic_type == GraphicType.LINE.value:
            self.model.x2 += dx
            self.model.y2 += dy
