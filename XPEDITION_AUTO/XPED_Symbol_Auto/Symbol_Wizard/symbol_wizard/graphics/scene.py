from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsScene
from symbol_wizard.rules.grid import PX_PER_INCH

class SymbolScene(QGraphicsScene):
    def __init__(self, window):
        super().__init__()
        self.window=window
        self.setSceneRect(-3000,-3000,6000,6000)
    @property
    def grid_px(self):
        return self.window.symbol.grid_inch*PX_PER_INCH
    def drawBackground(self,painter:QPainter,rect):
        super().drawBackground(painter,rect)
        g=self.grid_px
        left=int(rect.left()//g)*g; top=int(rect.top()//g)*g
        painter.save(); painter.setPen(QPen(QColor(225,225,225),0))
        x=left
        while x<rect.right(): painter.drawLine(QPointF(x,rect.top()),QPointF(x,rect.bottom())); x+=g
        y=top
        while y<rect.bottom(): painter.drawLine(QPointF(rect.left(),y),QPointF(rect.right(),y)); y+=g
        painter.setPen(QPen(QColor(170,170,170),0)); painter.drawLine(QPointF(rect.left(),0),QPointF(rect.right(),0)); painter.drawLine(QPointF(0,rect.top()),QPointF(0,rect.bottom()))
        painter.restore()
