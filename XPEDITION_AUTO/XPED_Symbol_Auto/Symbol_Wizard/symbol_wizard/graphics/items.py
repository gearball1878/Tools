from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QTransform
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem
from symbol_wizard.models.document import PinSide, LineStyle
from symbol_wizard.rules.grid import snap

def rgb(c): return QColor(*c)
def pen_for(color, width_grid, style, grid_px):
    p=QPen(rgb(color), max(1, width_grid*grid_px))
    p.setStyle({LineStyle.SOLID.value:Qt.SolidLine,LineStyle.DASH.value:Qt.DashLine,LineStyle.DOT.value:Qt.DotLine,LineStyle.DASH_DOT.value:Qt.DashDotLine}.get(style,Qt.SolidLine))
    return p

class TransformMixin:
    handle_size_factor=.22
    def apply_transform_from_model(self):
        # Be defensive: older files or wrongly constructed dataclasses may contain
        # strings in transform fields. Qt requires float values here.
        try:
            sx = float(getattr(self.model, 'scale_x', 1.0) or 1.0)
        except (TypeError, ValueError):
            sx = 1.0
        try:
            sy = float(getattr(self.model, 'scale_y', 1.0) or 1.0)
        except (TypeError, ValueError):
            sy = 1.0
        try:
            rot = float(getattr(self.model, 'rotation', 0.0) or 0.0)
        except (TypeError, ValueError):
            rot = 0.0
        self.model.scale_x = sx
        self.model.scale_y = sy
        self.model.rotation = rot
        self.setTransform(QTransform().scale(sx, sy))
        self.setRotation(rot)
    def common_flags(self):
        self.setAcceptHoverEvents(True)
        self.setFlags(QGraphicsItem.ItemIsMovable|QGraphicsItem.ItemIsSelectable|QGraphicsItem.ItemSendsGeometryChanges|QGraphicsItem.ItemIsFocusable)
    def itemChange(self,change,value):
        if change==QGraphicsItem.ItemPositionChange and self.scene():
            g=self.scene().grid_px; return QPointF(snap(value.x(),g), snap(value.y(),g))
        if change==QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.update_model_pos(); self.scene().window.live_refresh()
        return super().itemChange(change,value)
    def update_model_pos(self): pass
    def rotate_by(self, deg):
        try:
            current = float(getattr(self.model, 'rotation', 0.0) or 0.0)
        except (TypeError, ValueError):
            current = 0.0
        self.model.rotation = (current + float(deg)) % 360
        self.setRotation(float(self.model.rotation))
        self.update()
    def scale_selected(self,factor):
        # Generic fallback: real size-aware items override this.
        if hasattr(self.model,'font_size_grid'):
            self.model.font_size_grid=max(.1,self.model.font_size_grid*factor)
            g=self.scene().grid_px; self.setFont(QFont(self.model.font_family,max(6,int(g*self.model.font_size_grid*.45))))
        elif hasattr(self.model,'length'):
            self.model.length=max(.1,self.model.length*factor)
        self.update()

class BodyItem(TransformMixin,QGraphicsRectItem):
    def __init__(self,model,window):
        self.model=model; self.window=window; self._resizing=False; g=window.grid_px
        super().__init__(0,0,model.width*g,model.height*g); self.setPos(model.x*g,-model.y*g)
        self.setPen(pen_for(model.color,model.line_width,model.line_style,g)); self.setBrush(QBrush(Qt.NoBrush))
        self.common_flags(); self.setData(0,'BODY'); self.apply_transform_from_model()
    def update_model_pos(self):
        g=self.window.grid_px; self.model.x=self.pos().x()/g; self.model.y=-self.pos().y()/g
    def handle_rect(self):
        r=self.rect(); s=self.window.grid_px*self.handle_size_factor
        return QRectF(r.right()-s,r.bottom()-s,s,s)
    def paint(self,painter,option,widget=None):
        super().paint(painter,option,widget)
        if self.isSelected():
            painter.save(); painter.setBrush(QBrush(QColor(40,40,40))); painter.setPen(QPen(QColor(40,40,40),1)); painter.drawRect(self.handle_rect()); painter.restore()
    def mousePressEvent(self,event):
        if self.isSelected() and self.handle_rect().contains(event.pos()): self._resizing=True; event.accept(); return
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self._resizing:
            g=self.window.grid_px
            w=max(g, snap(event.pos().x(),g)); h=max(g, snap(event.pos().y(),g))
            self.model.width=w/g; self.model.height=h/g; self.setRect(0,0,w,h); self.scene().window.live_refresh(); self.update(); return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event): self._resizing=False; super().mouseReleaseEvent(event)
    def scale_selected(self,factor):
        self.model.width=max(1,self.model.width*factor); self.model.height=max(1,self.model.height*factor)
        g=self.window.grid_px; self.setRect(0,0,self.model.width*g,self.model.height*g); self.update()

class PinItem(TransformMixin,QGraphicsItem):
    def __init__(self,model,window):
        super().__init__(); self.model=model; self.window=window; g=window.grid_px; self.setPos(model.x*g,-model.y*g)
        self.common_flags(); self.setData(0,'PIN'); self.apply_transform_from_model()
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
        if self.isSelected():
            painter.setPen(QPen(QColor(80,80,80),1,Qt.DashLine)); painter.drawRect(self.boundingRect())
    def update_model_pos(self):
        g=self.window.grid_px; self.model.x=self.pos().x()/g; self.model.y=-self.pos().y()/g
    def scale_selected(self,factor): self.model.length=max(.1,self.model.length*factor); self.update()

class TextItem(TransformMixin,QGraphicsTextItem):
    def __init__(self,model,window):
        self.model=model; self.window=window; super().__init__(model.text); g=window.grid_px; self.setPos(model.x*g,-model.y*g)
        self.setDefaultTextColor(rgb(model.color)); self.setFont(QFont(model.font_family,max(6,int(g*model.font_size_grid*.45))))
        self.common_flags(); self.setTextInteractionFlags(Qt.TextEditorInteraction); self.setData(0,'TEXT'); self.apply_transform_from_model()
    def focusOutEvent(self,e): self.model.text=self.toPlainText(); super().focusOutEvent(e); self.scene().window.live_refresh()
    def update_model_pos(self):
        g=self.window.grid_px; self.model.x=self.pos().x()/g; self.model.y=-self.pos().y()/g; self.model.text=self.toPlainText()

class GraphicItem(TransformMixin,QGraphicsItem):
    def __init__(self,model,window):
        super().__init__(); self.model=model; self.window=window; self._resizing=False; g=window.grid_px; self.setPos(model.x*g,-model.y*g)
        self.common_flags(); self.setData(0,'GRAPHIC'); self.apply_transform_from_model()
    def boundingRect(self):
        g=self.window.grid_px; return QRectF(-.2*g,-.2*g,self.model.w*g+.4*g,self.model.h*g+.4*g).normalized()
    def handle_rect(self):
        g=self.window.grid_px; s=g*self.handle_size_factor; w=self.model.w*g; h=self.model.h*g
        return QRectF(w-s,h-s,s,s)
    def paint(self,painter,option,widget=None):
        g=self.window.grid_px; m=self.model; painter.setPen(pen_for(m.style.stroke,m.style.line_width,m.style.line_style,g)); painter.setBrush(QBrush(rgb(m.style.fill)) if m.style.fill else QBrush(Qt.NoBrush))
        if m.shape=='line': painter.drawLine(QPointF(0,0),QPointF(m.w*g,m.h*g))
        elif m.shape=='rect': painter.drawRect(QRectF(0,0,m.w*g,m.h*g))
        elif m.shape=='ellipse': painter.drawEllipse(QRectF(0,0,m.w*g,m.h*g))
        if self.isSelected():
            painter.save(); painter.setPen(QPen(QColor(80,80,80),1,Qt.DashLine)); painter.drawRect(QRectF(0,0,m.w*g,m.h*g).normalized()); painter.setBrush(QBrush(QColor(40,40,40))); painter.setPen(QPen(QColor(40,40,40),1)); painter.drawRect(self.handle_rect()); painter.restore()
    def mousePressEvent(self,event):
        if self.isSelected() and self.handle_rect().contains(event.pos()): self._resizing=True; event.accept(); return
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self._resizing:
            g=self.window.grid_px; self.model.w=snap(event.pos().x(),g)/g; self.model.h=snap(event.pos().y(),g)/g; self.prepareGeometryChange(); self.scene().window.live_refresh(); self.update(); return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event): self._resizing=False; super().mouseReleaseEvent(event)
    def update_model_pos(self):
        g=self.window.grid_px; self.model.x=self.pos().x()/g; self.model.y=-self.pos().y()/g
    def scale_selected(self,factor):
        self.model.w*=factor; self.model.h*=factor; self.prepareGeometryChange(); self.update()
