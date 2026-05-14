from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsView
from symbol_wizard.models.document import DrawTool, GraphicModel, PinSide, TextModel

class SymbolView(QGraphicsView):
    def __init__(self, scene, window):
        super().__init__(scene); self.window=window
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setFocusPolicy(Qt.StrongFocus)
    def wheelEvent(self,event):
        if event.modifiers() & Qt.ControlModifier:
            factor=1.08 if event.angleDelta().y()>0 else 1/1.08
            for it in self.scene().selectedItems():
                if hasattr(it,'scale_selected'):
                    it.scale_selected(factor)
            self.window.schedule_scene_refresh(visual_only=True)
            event.accept(); return
        self.scale(1.15 if event.angleDelta().y()>0 else 1/1.15, 1.15 if event.angleDelta().y()>0 else 1/1.15)
    def keyPressEvent(self,event):
        selected=self.scene().selectedItems()
        if selected:
            if event.key() in (Qt.Key_R, Qt.Key_E):
                step=15 if not (event.modifiers() & Qt.ShiftModifier) else 90
                for it in selected:
                    if hasattr(it,'rotate_by'): it.rotate_by(step)
                self.window.schedule_scene_refresh(visual_only=True); return
            if event.key() in (Qt.Key_Q,):
                step=-15 if not (event.modifiers() & Qt.ShiftModifier) else -90
                for it in selected:
                    if hasattr(it,'rotate_by'): it.rotate_by(step)
                self.window.schedule_scene_refresh(visual_only=True); return
            if event.key() in (Qt.Key_Plus, Qt.Key_Equal):
                for it in selected:
                    if hasattr(it,'scale_selected'): it.scale_selected(1.1)
                self.window.schedule_scene_refresh(visual_only=True); return
            if event.key() in (Qt.Key_Minus,):
                for it in selected:
                    if hasattr(it,'scale_selected'): it.scale_selected(1/1.1)
                self.window.schedule_scene_refresh(visual_only=True); return
        super().keyPressEvent(event)
    def mousePressEvent(self,event):
        tool=self.window.draw_tool
        if event.button()==Qt.LeftButton and tool!=DrawTool.SELECT.value:
            p=self.mapToScene(event.position().toPoint())
            gx=self.window.scene_to_grid_x(p.x()); gy=self.window.scene_to_grid_y(p.y())
            if tool==DrawTool.PIN_LEFT.value: self.window.add_pin(PinSide.LEFT.value, x=gx, y=gy)
            elif tool==DrawTool.PIN_RIGHT.value: self.window.add_pin(PinSide.RIGHT.value, x=gx, y=gy)
            elif tool==DrawTool.TEXT.value:
                m = TextModel(x=gx, y=gy)
                self.window.current_unit.texts.append(m)
                self.window.select_model_after_rebuild(m)
                self.window.rebuild_scene()
            elif tool in (DrawTool.LINE.value, DrawTool.RECT.value, DrawTool.ELLIPSE.value): self.window.add_graphic(tool, gx, gy)
            return
        super().mousePressEvent(event)
