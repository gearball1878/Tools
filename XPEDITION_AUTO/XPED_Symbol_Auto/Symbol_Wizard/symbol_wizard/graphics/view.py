from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsView
from symbol_wizard.models.document import DrawTool, GraphicModel, PinSide, TextModel

class SymbolView(QGraphicsView):
    def __init__(self, scene, window):
        super().__init__(scene); self.window=window
        self.setRenderHint(QPainter.Antialiasing); self.setDragMode(QGraphicsView.RubberBandDrag); self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
    def wheelEvent(self,event):
        self.scale(1.15 if event.angleDelta().y()>0 else 1/1.15, 1.15 if event.angleDelta().y()>0 else 1/1.15)
    def mousePressEvent(self,event):
        tool=self.window.draw_tool
        if event.button()==Qt.LeftButton and tool!=DrawTool.SELECT.value:
            p=self.mapToScene(event.position().toPoint())
            gx=self.window.scene_to_grid_x(p.x()); gy=self.window.scene_to_grid_y(p.y())
            if tool==DrawTool.PIN_LEFT.value: self.window.add_pin(PinSide.LEFT.value, x=gx, y=gy)
            elif tool==DrawTool.PIN_RIGHT.value: self.window.add_pin(PinSide.RIGHT.value, x=gx, y=gy)
            elif tool==DrawTool.TEXT.value: self.window.current_unit.texts.append(TextModel(x=gx,y=gy)); self.window.rebuild_scene()
            elif tool in (DrawTool.LINE.value, DrawTool.RECT.value, DrawTool.ELLIPSE.value): self.window.add_graphic(tool, gx, gy)
            return
        super().mousePressEvent(event)
