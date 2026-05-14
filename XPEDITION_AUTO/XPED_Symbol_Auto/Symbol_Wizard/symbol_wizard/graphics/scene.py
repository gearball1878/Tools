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


def _anchored_rect(width: float, height: float, origin: str) -> QRectF:
    # Scene coordinates: +x is right, +y is down.  The crosshair is always the
    # symbol origin at scene (0, 0).  The guide rectangle is shifted depending on
    # the selected origin so the expected drawing direction is visible:
    # top-left -> right/down, bottom-left -> right/up, center -> around origin, etc.
    if origin == 'top_left':
        return QRectF(0, 0, width, height)
    if origin == 'top_right':
        return QRectF(-width, 0, width, height)
    if origin == 'bottom_left':
        return QRectF(0, -height, width, height)
    if origin == 'bottom_right':
        return QRectF(-width, -height, width, height)
    return QRectF(-width / 2, -height / 2, width, height)


def guide_rects_for_origin(fmt: str, origin: str) -> tuple[QRectF, QRectF]:
    """Return (blue sheet, red recommended area) for the selected origin.

    The red recommended drawing area is always geometrically centered inside
    the blue sheet preview.  The selected origin determines which point of the
    red area lies on the canvas origin/crosshair, because this is the direction
    in which the symbol will be drawn:

    * top_left:     origin at red top-left, symbol grows right/down
    * top_right:    origin at red top-right, symbol grows left/down
    * bottom_left:  origin at red bottom-left, symbol grows right/up
    * bottom_right: origin at red bottom-right, symbol grows left/up
    * center:       origin at red center, symbol grows around the origin

    Both rectangles are orientation guides only; they never clip or rescale
    the symbol geometry.
    """
    w_in, h_in = SHEET_INCHES.get(fmt, SHEET_INCHES['A3'])
    sheet_w = w_in * PX_PER_INCH
    sheet_h = h_in * PX_PER_INCH
    red_w = sheet_w * 0.40
    red_h = sheet_h * 0.80

    # First place the red area according to the selected origin anchor.
    usable = _anchored_rect(red_w, red_h, origin)

    # Then place the blue sheet around the red area's center.  This guarantees
    # that red is ALWAYS centered inside blue, independent of the origin mode.
    c = usable.center()
    full = QRectF(c.x() - sheet_w / 2.0, c.y() - sheet_h / 2.0, sheet_w, sheet_h)
    return full, usable


def sheet_rect_for_origin(fmt: str, origin: str) -> QRectF:
    return guide_rects_for_origin(fmt, origin)[0]


def usable_rect_for_origin(fmt: str, origin: str) -> QRectF:
    return guide_rects_for_origin(fmt, origin)[1]


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
        origin = getattr(self.window.symbol, 'origin', 'center')
        full = sheet_rect_for_origin(fmt, origin)
        usable = usable_rect_for_origin(fmt, origin)
        dx, dy = getattr(self.window, '_format_guide_offset', (0.0, 0.0))
        full.translate(dx, dy)
        usable.translate(dx, dy)
        painter.save()
        painter.setPen(QPen(QColor(170, 170, 210), 0, Qt.DashLine))
        painter.drawRect(full)
        painter.setPen(QPen(QColor(210, 120, 120), 0, Qt.DashDotLine))
        painter.drawRect(usable)
        painter.setPen(QPen(QColor(120, 120, 120), 0))
        painter.drawEllipse(QPointF(0, 0), 5, 5)
        painter.setFont(QFont('Arial', 10))
        painter.drawText(full.adjusted(8, 8, -8, -8), Qt.AlignTop | Qt.AlignLeft, f'{fmt} preview - origin guide: {origin}')
        painter.drawText(usable.adjusted(8, 8, -8, -8), Qt.AlignTop | Qt.AlignLeft, 'recommended symbol area: 40% W / 80% H (guide only)')
        painter.restore()
