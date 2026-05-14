from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem, QGraphicsEllipseItem
from symbol_wizard.models.document import PinSide, LineStyle
from symbol_wizard.rules.grid import PX_PER_INCH, snap

def rgb(c): return QColor(*c)
def pen_for(color, width_grid, style, grid_px):
    p=QPen(rgb(color), max(1, width_grid*grid_px))
    p.setStyle({LineStyle.SOLID.value:Qt.SolidLine,LineStyle.DASH.value:Qt.DashLine,LineStyle.DOT.value:Qt.DotLine,LineStyle.DASH_DOT.value:Qt.DashDotLine}.get(style,Qt.SolidLine))
    return p
class SnapMixin:
    def itemChange(self,change,value):
        if change==QGraphicsItem.ItemPositionChange and self.scene():
            g=self.scene().grid_px; return QPointF(snap(value.x(),g), snap(value.y(),g))
        if change==QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.update_model(); self.scene().window.live_refresh()
        return super().itemChange(change,value)
    def update_model(self): pass
class BodyItem(SnapMixin,QGraphicsRectItem):
    def __init__(self,model,window):
        self.model=model; self.window=window; g=window.grid_px
        super().__init__(0,0,model.width*g,model.height*g); self.setPos(model.x*g,-model.y*g)
        self.setPen(pen_for(model.color,model.line_width,model.line_style,g)); self.setBrush(QBrush(Qt.NoBrush))
        self.setFlags(QGraphicsItem.ItemIsMovable|QGraphicsItem.ItemIsSelectable|QGraphicsItem.ItemSendsGeometryChanges); self.setData(0,'BODY')
    def update_model(self):
        g=self.window.grid_px; self.model.x=self.pos().x()/g; self.model.y=-self.pos().y()/g
class PinItem(SnapMixin,QGraphicsItem):
    def __init__(self,model,window):
        super().__init__(); self.model=model; self.window=window; g=window.grid_px; self.setPos(model.x*g,-model.y*g)
        self.setFlags(QGraphicsItem.ItemIsMovable|QGraphicsItem.ItemIsSelectable|QGraphicsItem.ItemSendsGeometryChanges); self.setData(0,'PIN')
    def boundingRect(self):
        g=self.window.grid_px; return QRectF(-6*g,-1.2*g,12*g,2.4*g)
    def paint(self,painter,option,widget=None):
        g=self.window.grid_px; m=self.model; L=m.length*g; painter.setPen(pen_for(m.color,m.line_width,m.line_style,g)); painter.setBrush(QBrush(Qt.NoBrush))
        x1,x2=(-L,0) if m.side==PinSide.LEFT.value else (0,L); painter.drawLine(QPointF(x1,0),QPointF(x2,0))
        if m.inverted:
            r=.18*g; painter.drawEllipse(QPointF((-r if m.side==PinSide.LEFT.value else r),0),r,r)
        painter.setFont(QFont('Arial',max(6,int(g*.28))))
        if m.visible_number: painter.drawText(QRectF(min(x1,x2),-.85*g,abs(x2-x1),.5*g),Qt.AlignCenter,m.number)
        parts=[]
        if m.visible_name: parts.append(m.name)
        if m.visible_function: parts.append(m.function)
        label=' / '.join([x for x in parts if x])
        if label:
            painter.setFont(QFont('Arial',max(8,int(g*.35))))
            if m.side==PinSide.LEFT.value: painter.drawText(QRectF(.25*g,-.35*g,6*g,.7*g),Qt.AlignVCenter|Qt.AlignLeft,label)
            else: painter.drawText(QRectF(-6.25*g,-.35*g,6*g,.7*g),Qt.AlignVCenter|Qt.AlignRight,label)
    def update_model(self):
        g=self.window.grid_px; self.model.x=self.pos().x()/g; self.model.y=-self.pos().y()/g
class TextItem(SnapMixin,QGraphicsTextItem):
    def __init__(self,model,window):
        self.model=model; self.window=window; super().__init__(model.text); g=window.grid_px; self.setPos(model.x*g,-model.y*g)
        self.setDefaultTextColor(rgb(model.color)); self.setFont(QFont(model.font_family,max(6,int(g*model.font_size_grid*.45))))
        self.setFlags(QGraphicsItem.ItemIsMovable|QGraphicsItem.ItemIsSelectable|QGraphicsItem.ItemSendsGeometryChanges|QGraphicsItem.ItemIsFocusable); self.setTextInteractionFlags(Qt.TextEditorInteraction); self.setData(0,'TEXT')
    def focusOutEvent(self,e): self.model.text=self.toPlainText(); super().focusOutEvent(e); self.scene().window.live_refresh()
    def update_model(self):
        g=self.window.grid_px; self.model.x=self.pos().x()/g; self.model.y=-self.pos().y()/g; self.model.text=self.toPlainText()
class GraphicItem(SnapMixin,QGraphicsItem):
    def __init__(self,model,window):
        super().__init__(); self.model=model; self.window=window; g=window.grid_px; self.setPos(model.x*g,-model.y*g)
        self.setFlags(QGraphicsItem.ItemIsMovable|QGraphicsItem.ItemIsSelectable|QGraphicsItem.ItemSendsGeometryChanges); self.setData(0,'GRAPHIC')
    def boundingRect(self):
        g=self.window.grid_px; return QRectF(-.2*g,-.2*g,self.model.w*g+.4*g,self.model.h*g+.4*g)
    def paint(self,painter,option,widget=None):
        g=self.window.grid_px; m=self.model; painter.setPen(pen_for(m.style.stroke,m.style.line_width,m.style.line_style,g)); painter.setBrush(QBrush(rgb(m.style.fill)) if m.style.fill else QBrush(Qt.NoBrush))
        if m.shape=='line': painter.drawLine(QPointF(0,0),QPointF(m.w*g,m.h*g))
        elif m.shape=='rect': painter.drawRect(QRectF(0,0,m.w*g,m.h*g))
        elif m.shape=='ellipse': painter.drawEllipse(QRectF(0,0,m.w*g,m.h*g))
    def update_model(self):
        g=self.window.grid_px; self.model.x=self.pos().x()/g; self.model.y=-self.pos().y()/g
