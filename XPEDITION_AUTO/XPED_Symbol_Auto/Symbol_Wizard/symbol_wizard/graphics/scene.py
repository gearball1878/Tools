from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import QGraphicsScene
from symbol_wizard.rules.grid import PX_PER_INCH

# ISO A formats represented in landscape inches, rounded from mm.
SHEET_INCHES = {
    'A0': (46.81, 33.11),
    'A1': (33.11, 23.39),
    'A2': (23.39, 16.54),
    'A3': (16.54, 11.69),
    'A4': (11.69, 8.27),
    'A5': (8.27, 5.83),
}


def sheet_rect_for(fmt: str) -> QRectF:
    w_in, h_in = SHEET_INCHES.get(fmt, SHEET_INCHES['A3'])
    w = w_in * PX_PER_INCH
    h = h_in * PX_PER_INCH
    # The sheet preview is centered on scene origin. By default every new symbol body is also centered here.
    return QRectF(-w / 2, -h / 2, w, h)


def usable_rect_for(fmt: str) -> QRectF:
    full = sheet_rect_for(fmt)
    usable_w = full.width() * 0.40
    usable_h = full.height() * 0.80
    return QRectF(-usable_w / 2, -usable_h / 2, usable_w, usable_h)


class SymbolScene(QGraphicsScene):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setSceneRect(-6000, -6000, 12000, 12000)

    @property
    def grid_px(self):
        return self.window.symbol.grid_inch * PX_PER_INCH

    def drawBackground(self, painter: QPainter, rect):
        super().drawBackground(painter, rect)
        g = max(2, self.grid_px)
        left = int(rect.left() // g) * g
        top = int(rect.top() // g) * g
        painter.save()
        painter.setPen(QPen(QColor(225, 225, 225), 0))
        x = left
        while x < rect.right():
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            x += g
        y = top
        while y < rect.bottom():
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += g
        # Origin axes: symbol origin. New bodies are centered on this point by default.
        painter.setPen(QPen(QColor(150, 150, 150), 0))
        painter.drawLine(QPointF(rect.left(), 0), QPointF(rect.right(), 0))
        painter.drawLine(QPointF(0, rect.top()), QPointF(0, rect.bottom()))
        painter.restore()

    def drawForeground(self, painter: QPainter, rect):
        super().drawForeground(painter, rect)
        fmt = getattr(self.window.symbol, 'sheet_format', 'A3')
        full = sheet_rect_for(fmt)
        usable = usable_rect_for(fmt)
        painter.save()
        painter.setPen(QPen(QColor(170, 170, 210), 0, Qt.DashLine))
        painter.drawRect(full)
        painter.setPen(QPen(QColor(210, 120, 120), 0, Qt.DashDotLine))
        painter.drawRect(usable)
        painter.setPen(QPen(QColor(120, 120, 120), 0))
        painter.drawEllipse(QPointF(0, 0), 5, 5)
        painter.setFont(QFont('Arial', 10))
        painter.drawText(full.adjusted(8, 8, -8, -8), Qt.AlignTop | Qt.AlignLeft, f'{fmt} preview - symbol origin / default body center')
        painter.drawText(usable.adjusted(8, 8, -8, -8), Qt.AlignTop | Qt.AlignLeft, 'max symbol area: 40% W / 80% H')
        painter.restore()
