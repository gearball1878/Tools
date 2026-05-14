from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsView
from symbol_wizard.models.document import DrawTool, GraphicModel, PinSide, TextModel


class SymbolView(QGraphicsView):
    def __init__(self, scene, window):
        super().__init__(scene)
        self.window = window
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return

        mods = event.modifiers()
        if mods & Qt.ControlModifier:
            # Ctrl + mouse wheel: cursor-centered zoom.
            self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
            factor = 1.15 if delta > 0 else 1 / 1.15
            self.scale(factor, factor)
            event.accept()
            return

        if mods & Qt.ShiftModifier:
            # Shift + mouse wheel: horizontal pan.
            bar = self.horizontalScrollBar()
            bar.setValue(bar.value() - delta)
            event.accept()
            return

        # Plain mouse wheel: vertical pan.
        bar = self.verticalScrollBar()
        bar.setValue(bar.value() - delta)
        event.accept()

    def keyPressEvent(self, event):
        focus_item = self.scene().focusItem()
        if focus_item is not None and hasattr(focus_item, 'textInteractionFlags') and focus_item.textInteractionFlags() != Qt.NoTextInteraction:
            super().keyPressEvent(event)
            return
        selected = self.scene().selectedItems()
        if selected:
            if event.key() in (Qt.Key_R, Qt.Key_E):
                step = 15 if not (event.modifiers() & Qt.ShiftModifier) else 90
                for it in selected:
                    if hasattr(it, 'rotate_by'):
                        it.rotate_by(step)
                self.window.live_refresh()
                return
            if event.key() in (Qt.Key_Q,):
                step = -15 if not (event.modifiers() & Qt.ShiftModifier) else -90
                for it in selected:
                    if hasattr(it, 'rotate_by'):
                        it.rotate_by(step)
                self.window.live_refresh()
                return
            if event.key() in (Qt.Key_Plus, Qt.Key_Equal):
                for it in selected:
                    if hasattr(it, 'scale_selected'):
                        it.scale_selected(1.1)
                self.window.enforce_symbol_size_limit(silent=True)
                self.window.live_refresh()
                return
            if event.key() in (Qt.Key_Minus,):
                for it in selected:
                    if hasattr(it, 'scale_selected'):
                        it.scale_selected(1 / 1.1)
                self.window.enforce_symbol_size_limit(silent=True)
                self.window.live_refresh()
                return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        tool = self.window.draw_tool
        if event.button() == Qt.LeftButton and tool != DrawTool.SELECT.value:
            p = self.mapToScene(event.position().toPoint())
            gx = self.window.scene_to_grid_x(p.x())
            gy = self.window.scene_to_grid_y(p.y())
            if tool == DrawTool.PIN_LEFT.value:
                self.window.add_pin(PinSide.LEFT.value, x=gx, y=gy)
            elif tool == DrawTool.PIN_RIGHT.value:
                self.window.add_pin(PinSide.RIGHT.value, x=gx, y=gy)
            elif tool == DrawTool.TEXT.value:
                m = TextModel(x=gx, y=gy)
                self.window.current_unit.texts.append(m)
                self.window.select_model_after_rebuild(m)
                self.window.rebuild_scene()
                self.window.rebuild_tree()
            elif tool in (DrawTool.LINE.value, DrawTool.RECT.value, DrawTool.ELLIPSE.value):
                self.window.add_graphic(tool, gx, gy)
            event.accept()
            return
        super().mousePressEvent(event)
