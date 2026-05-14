from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsScene

from symbol_wizard.config import PX_PER_INCH


class SymbolGraphicsScene(QGraphicsScene):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.setSceneRect(-2000, -2000, 4000, 4000)

    @property
    def grid_px(self) -> float:
        return self.editor.document.grid_inch * PX_PER_INCH

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect)
        grid = self.grid_px
        if grid < 4:
            return
        left = int(rect.left() // grid) * grid
        top = int(rect.top() // grid) * grid

        painter.save()
        painter.setPen(QPen(QColor(225, 225, 225), 0))
        x = left
        while x < rect.right():
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            x += grid
        y = top
        while y < rect.bottom():
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += grid

        painter.setPen(QPen(QColor(180, 180, 180), 0))
        painter.drawLine(QPointF(rect.left(), 0), QPointF(rect.right(), 0))
        painter.drawLine(QPointF(0, rect.top()), QPointF(0, rect.bottom()))
        painter.restore()
