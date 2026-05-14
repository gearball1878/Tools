from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsView, QMenu
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


    def contextMenuEvent(self, event):
        self.window.set_tool(DrawTool.SELECT.value)
        menu = QMenu(self)
        menu.addAction('Select All', self.window.select_all_canvas)
        menu.addAction('Copy', self.window.copy_selected)
        menu.addAction('Cut', self.window.cut_selected)
        menu.addAction('Paste', self.window.paste_selected)
        menu.addSeparator()
        menu.addAction('Rotate CCW 15°', lambda: self.window.rotate_selected(-15))
        menu.addAction('Rotate CW 15°', lambda: self.window.rotate_selected(15))
        menu.addAction('Flip Horizontal', self.window.flip_selected_horizontal)
        menu.addAction('Flip Vertical', self.window.flip_selected_vertical)
        align_menu = menu.addMenu('Alignment')
        h_menu = align_menu.addMenu('Horizontal')
        for lab, val in [('Left', 'left'), ('Center', 'center'), ('Right', 'right')]:
            h_menu.addAction(lab, lambda checked=False, v=val: self.window.set_selected_text_alignment(h_align=v))
        v_menu = align_menu.addMenu('Vertical')
        for lab, val in [('Upper', 'upper'), ('Center', 'center'), ('Lower', 'lower')]:
            v_menu.addAction(lab, lambda checked=False, v=val: self.window.set_selected_text_alignment(v_align=v))
        menu.addSeparator()
        menu.addAction('Undo', self.window.undo)
        menu.addAction('Redo', self.window.redo)
        menu.addSeparator()
        menu.addAction('Delete', self.window.delete_selected)
        menu.exec(event.globalPos())
        event.accept()

    def keyPressEvent(self, event):
        focus_item = self.scene().focusItem()
        if focus_item is not None and hasattr(focus_item, 'textInteractionFlags') and focus_item.textInteractionFlags() != Qt.NoTextInteraction:
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key_Escape:
            self.window.set_tool(DrawTool.SELECT.value); event.accept(); return
        if event.key() == Qt.Key_Delete:
            self.window.set_tool(DrawTool.SELECT.value); self.window.delete_selected(); event.accept(); return
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_A:
                self.window.set_tool(DrawTool.SELECT.value); self.window.select_all_canvas(); event.accept(); return
            if event.key() == Qt.Key_C:
                self.window.set_tool(DrawTool.SELECT.value); self.window.copy_selected(); event.accept(); return
            if event.key() == Qt.Key_X:
                self.window.set_tool(DrawTool.SELECT.value); self.window.cut_selected(); event.accept(); return
            if event.key() == Qt.Key_Z:
                self.window.set_tool(DrawTool.SELECT.value); self.window.undo(); event.accept(); return
            if event.key() == Qt.Key_Y:
                self.window.set_tool(DrawTool.SELECT.value); self.window.redo(); event.accept(); return
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
        # Right and middle mouse button return the canvas to Select/Edit mode.
        # Right mouse still opens the context menu through contextMenuEvent.
        if event.button() == Qt.MiddleButton:
            self.window.set_tool(DrawTool.SELECT.value)
            event.accept()
            return
        if event.button() == Qt.RightButton:
            self.window.set_tool(DrawTool.SELECT.value)
            event.accept()
            return

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
