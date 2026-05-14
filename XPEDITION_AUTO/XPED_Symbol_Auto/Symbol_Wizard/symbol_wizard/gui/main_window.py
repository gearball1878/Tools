from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGraphicsItem,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from symbol_wizard.config import APP_NAME, PX_PER_INCH
from symbol_wizard.graphics.items import GraphicObjectItem, PinItem, SymbolBodyItem, TextGraphicsItem
from symbol_wizard.graphics.scene import SymbolGraphicsScene
from symbol_wizard.graphics.view import SymbolGraphicsView
from symbol_wizard.gui.properties_panel import PropertiesPanel
from symbol_wizard.io.json_store import load_document, save_document
from symbol_wizard.models.document import (
    GraphicObjectModel,
    GraphicType,
    OriginMode,
    PinModel,
    PinSide,
    SymbolBodyModel,
    SymbolDocumentModel,
    SymbolUnitModel,
    TextModel,
)
from symbol_wizard.rules.placement import create_default_pin


class SymbolEditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.document = SymbolDocumentModel()
        self.current_unit_index = 0
        self.clipboard_payload = None
        self.scene = SymbolGraphicsScene(self)
        self.view = SymbolGraphicsView(self.scene)
        self.unit_tabs = QTabWidget()
        self.object_tree = QTreeWidget()
        self.pin_table = QTableWidget()
        self.left_tabs = QTabWidget()
        self.properties_panel = PropertiesPanel(self)

        self.setWindowTitle(APP_NAME)
        self.resize(1500, 900)
        self._build_ui()
        self.rebuild_tabs()
        self.rebuild_scene()

    @property
    def current_unit(self) -> SymbolUnitModel:
        return self.document.units[self.current_unit_index]

    def _build_ui(self):
        self._build_menu()
        self._build_toolbar()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self.left_tabs)
        self._build_left_tabs()

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.addWidget(self.view)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Properties"))
        right_layout.addWidget(self.properties_panel)
        right_layout.addStretch()

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(center)
        splitter.addWidget(right)
        splitter.setSizes([330, 900, 320])
        self.setCentralWidget(splitter)

        self.scene.selectionChanged.connect(self.refresh_properties)

    def _build_menu(self):
        menu = self.menuBar()
        file_menu = menu.addMenu("File")
        edit_menu = menu.addMenu("Edit")
        insert_menu = menu.addMenu("Insert")
        view_menu = menu.addMenu("View")

        self._menu_action(file_menu, "New Project", self.new_document, QKeySequence.New)
        self._menu_action(file_menu, "New Symbol", self.add_unit, "Ctrl+Shift+N")
        file_menu.addSeparator()
        self._menu_action(file_menu, "Open JSON...", self.load_json, QKeySequence.Open)
        self._menu_action(file_menu, "Save JSON...", self.save_json, QKeySequence.Save)
        file_menu.addSeparator()
        self._menu_action(file_menu, "Exit", self.close, QKeySequence.Quit)

        self._menu_action(edit_menu, "Copy", self.copy_selected, QKeySequence.Copy)
        self._menu_action(edit_menu, "Paste", self.paste_selected, QKeySequence.Paste)
        self._menu_action(edit_menu, "Delete Selected", self.delete_selected, QKeySequence.Delete)

        self._menu_action(insert_menu, "Pin Left", lambda: self.add_pin(PinSide.LEFT.value))
        self._menu_action(insert_menu, "Pin Right", lambda: self.add_pin(PinSide.RIGHT.value))
        self._menu_action(insert_menu, "Text", self.add_text)
        self._menu_action(insert_menu, "Line", self.add_line)
        self._menu_action(insert_menu, "Rectangle", self.add_rect)
        self._menu_action(insert_menu, "Ellipse", self.add_ellipse)

        self._menu_action(view_menu, "Refresh Object Tree", self.refresh_side_panels)

    def _menu_action(self, menu, text, callback, shortcut=None):
        action = QAction(text, self)
        action.triggered.connect(callback)
        if shortcut:
            action.setShortcut(shortcut)
        menu.addAction(action)
        return action

    def _build_toolbar(self):
        toolbar = QToolBar("Quick Tools")
        self.addToolBar(toolbar)
        self._add_action(toolbar, "New Symbol", self.add_unit)
        self._add_action(toolbar, "Save JSON", self.save_json)
        self._add_action(toolbar, "Load JSON", self.load_json)
        toolbar.addSeparator()
        self._add_action(toolbar, "Copy", self.copy_selected)
        self._add_action(toolbar, "Paste", self.paste_selected)
        self._add_action(toolbar, "Delete", self.delete_selected)
        toolbar.addSeparator()
        toolbar.addWidget(QLabel("Grid inch:"))
        self.grid_spin = QDoubleSpinBox()
        self.grid_spin.setRange(0.05, 0.5)
        self.grid_spin.setSingleStep(0.05)
        self.grid_spin.setDecimals(3)
        self.grid_spin.setValue(self.document.grid_inch)
        self.grid_spin.valueChanged.connect(self.set_grid)
        toolbar.addWidget(self.grid_spin)
        toolbar.addWidget(QLabel(" Origin:"))
        self.origin_combo = QComboBox()
        self.origin_combo.addItems([m.value for m in OriginMode])
        self.origin_combo.setCurrentText(self.document.origin)
        self.origin_combo.currentTextChanged.connect(self.set_origin)
        toolbar.addWidget(self.origin_combo)

    def _add_action(self, toolbar: QToolBar, text: str, callback):
        action = QAction(text, self)
        action.triggered.connect(callback)
        toolbar.addAction(action)

    def _build_left_tabs(self):
        units_page = QWidget(); units_layout = QVBoxLayout(units_page)
        units_layout.addWidget(QLabel("Units / Split Symbols"))
        units_layout.addWidget(self.unit_tabs)
        units_layout.addWidget(QLabel("Objects in selected Unit"))
        self.object_tree.setHeaderLabels(["Object", "Details"])
        self.object_tree.itemClicked.connect(self.tree_item_clicked)
        units_layout.addWidget(self.object_tree)

        pin_page = QWidget(); pin_layout = QVBoxLayout(pin_page)
        pin_layout.addWidget(QLabel("Pins in selected Unit"))
        self.pin_table.setColumnCount(6)
        self.pin_table.setHorizontalHeaderLabels(["Number", "Name", "Function", "Type", "Side", "Inverted"])
        self.pin_table.cellClicked.connect(self.pin_table_clicked)
        pin_layout.addWidget(self.pin_table)

        insert_page = QWidget(); insert_layout = QVBoxLayout(insert_page)
        insert_layout.addWidget(QLabel("Zeichenobjekte nachträglich einfügen"))
        for title, callback in [
            ("Symbol Body ersetzen", self.add_body),
            ("Pin links", lambda: self.add_pin(PinSide.LEFT.value)),
            ("Pin rechts", lambda: self.add_pin(PinSide.RIGHT.value)),
            ("Textfeld", self.add_text),
            ("Linie", self.add_line),
            ("Rechteck", self.add_rect),
            ("Ellipse/Kreis", self.add_ellipse),
        ]:
            btn = QPushButton(title)
            btn.clicked.connect(callback)
            insert_layout.addWidget(btn)
        insert_layout.addStretch()

        self.left_tabs.addTab(units_page, "Units / Tree")
        self.left_tabs.addTab(pin_page, "Pins")
        self.left_tabs.addTab(insert_page, "Insert")

    def refresh_properties(self):
        self.properties_panel.refresh()

    def refresh_after_model_change(self):
        self.properties_panel.refresh()
        self.refresh_side_panels()

    def refresh_side_panels(self):
        self.refresh_object_tree()
        self.refresh_pin_table()

    def rebuild_tabs(self):
        try:
            self.unit_tabs.currentChanged.disconnect()
        except RuntimeError:
            pass
        self.unit_tabs.clear()
        for unit in self.document.units:
            self.unit_tabs.addTab(QWidget(), unit.name)
        self.unit_tabs.setCurrentIndex(self.current_unit_index)
        self.unit_tabs.currentChanged.connect(self.set_current_unit)

    def set_current_unit(self, index: int):
        if index < 0:
            return
        self.current_unit_index = index
        self.rebuild_scene()

    def rebuild_scene(self):
        self.scene.clear()
        unit = self.current_unit
        self.scene.addItem(SymbolBodyItem(unit.body, self))
        for graphic in unit.graphics:
            self.scene.addItem(GraphicObjectItem(graphic, self))
        for pin in unit.pins:
            self.scene.addItem(PinItem(pin, self))
        for text in unit.texts:
            self.scene.addItem(TextGraphicsItem(text, self))
        self.scene.update()
        self.refresh_properties()
        self.refresh_side_panels()

    def refresh_object_tree(self):
        self.object_tree.clear()
        unit = self.current_unit
        root = QTreeWidgetItem([unit.name, "Symbol"])
        self.object_tree.addTopLevelItem(root)
        body = QTreeWidgetItem(["Body", f"{unit.body.width:g} x {unit.body.height:g}"])
        body.setData(0, Qt.UserRole, ("BODY", None))
        root.addChild(body)
        attrs = QTreeWidgetItem(["Attributes", f"{len(unit.body.attributes)} total"])
        root.addChild(attrs)
        for key, value in unit.body.attributes.items():
            visible = "visible" if key in unit.body.visible_attributes else "hidden"
            attrs.addChild(QTreeWidgetItem([key, f"{value} ({visible})"]))
        pins = QTreeWidgetItem(["Pins", str(len(unit.pins))])
        root.addChild(pins)
        for idx, pin in enumerate(unit.pins):
            item = QTreeWidgetItem([f"Pin {pin.number}", f"{pin.name} / {pin.function}"])
            item.setData(0, Qt.UserRole, ("PIN", idx))
            pins.addChild(item)
        texts = QTreeWidgetItem(["Text", str(len(unit.texts))])
        root.addChild(texts)
        for idx, text in enumerate(unit.texts):
            item = QTreeWidgetItem([f"Text {idx + 1}", text.text])
            item.setData(0, Qt.UserRole, ("TEXT", idx))
            texts.addChild(item)
        graphics = QTreeWidgetItem(["Graphics", str(len(unit.graphics))])
        root.addChild(graphics)
        for idx, graphic in enumerate(unit.graphics):
            item = QTreeWidgetItem([f"{graphic.graphic_type} {idx + 1}", f"x={graphic.x:g}, y={graphic.y:g}"])
            item.setData(0, Qt.UserRole, ("GRAPHIC", idx))
            graphics.addChild(item)
        self.object_tree.expandAll()

    def refresh_pin_table(self):
        unit = self.current_unit
        self.pin_table.setRowCount(len(unit.pins))
        for row, pin in enumerate(unit.pins):
            values = [pin.number, pin.name, pin.function, pin.pin_type, pin.side, "yes" if pin.inverted else "no"]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.pin_table.setItem(row, col, item)
        self.pin_table.resizeColumnsToContents()

    def tree_item_clicked(self, item: QTreeWidgetItem, column: int):
        payload = item.data(0, Qt.UserRole)
        if not payload:
            return
        self.select_model_item(payload[0], payload[1])

    def pin_table_clicked(self, row: int, column: int):
        self.select_model_item("PIN", row)

    def select_model_item(self, kind: str, index):
        self.scene.clearSelection()
        for item in self.scene.items():
            item_kind = item.data(0)
            if kind == "BODY" and item_kind == "SYMBOL_BODY":
                item.setSelected(True); self.view.centerOn(item); return
            if kind == "PIN" and item_kind == "PIN" and item.model is self.current_unit.pins[index]:
                item.setSelected(True); self.view.centerOn(item); return
            if kind == "TEXT" and item_kind == "TEXT" and item.model is self.current_unit.texts[index]:
                item.setSelected(True); self.view.centerOn(item); return
            if kind == "GRAPHIC" and item_kind == "GRAPHIC" and item.model is self.current_unit.graphics[index]:
                item.setSelected(True); self.view.centerOn(item); return

    def new_document(self):
        self.document = SymbolDocumentModel()
        self.current_unit_index = 0
        self.grid_spin.setValue(self.document.grid_inch)
        self.origin_combo.setCurrentText(self.document.origin)
        self.rebuild_tabs()
        self.rebuild_scene()

    def add_body(self):
        self.current_unit.body = SymbolBodyModel()
        self.rebuild_scene()

    def add_pin(self, side: str):
        self.current_unit.pins.append(create_default_pin(self.current_unit, side))
        self.rebuild_scene()

    def add_text(self):
        self.current_unit.texts.append(TextModel(text="Text", x=2.0, y=-2.0))
        self.rebuild_scene()

    def add_line(self):
        self.current_unit.graphics.append(GraphicObjectModel(graphic_type=GraphicType.LINE.value, x=2.0, y=2.0, x2=8.0, y2=2.0))
        self.rebuild_scene()

    def add_rect(self):
        self.current_unit.graphics.append(GraphicObjectModel(graphic_type=GraphicType.RECT.value, x=2.0, y=2.0, width=4.0, height=2.0))
        self.rebuild_scene()

    def add_ellipse(self):
        self.current_unit.graphics.append(GraphicObjectModel(graphic_type=GraphicType.ELLIPSE.value, x=2.0, y=2.0, width=3.0, height=3.0))
        self.rebuild_scene()

    def add_unit(self):
        self.document.units.append(SymbolUnitModel(name=f"Symbol {len(self.document.units) + 1}"))
        self.current_unit_index = len(self.document.units) - 1
        self.rebuild_tabs()
        self.rebuild_scene()

    def delete_selected(self):
        selected = self.scene.selectedItems()
        if not selected:
            return
        unit = self.current_unit
        for item in selected:
            kind = item.data(0)
            if kind == "PIN":
                unit.pins = [p for p in unit.pins if p is not item.model]
            elif kind == "TEXT":
                unit.texts = [t for t in unit.texts if t is not item.model]
            elif kind == "GRAPHIC":
                unit.graphics = [g for g in unit.graphics if g is not item.model]
            elif kind == "SYMBOL_BODY":
                QMessageBox.information(self, "Symbolbody", "Der Symbolbody wird im MVP nicht gelöscht, sondern über 'Symbol Body ersetzen' ersetzt.")
        self.rebuild_scene()

    def copy_selected(self):
        selected = self.scene.selectedItems()
        if not selected:
            return
        payload = []
        for item in selected:
            kind = item.data(0)
            if kind in {"PIN", "TEXT", "GRAPHIC"}:
                payload.append((kind, deepcopy(item.model)))
            elif kind == "SYMBOL_BODY":
                payload.append((kind, deepcopy(item.model)))
        self.clipboard_payload = payload

    def paste_selected(self):
        if not self.clipboard_payload:
            return
        unit = self.current_unit
        offset = 1.0
        for kind, model in deepcopy(self.clipboard_payload):
            if hasattr(model, "x"):
                model.x += offset
            if hasattr(model, "y"):
                model.y += offset
            if isinstance(model, GraphicObjectModel) and model.graphic_type == GraphicType.LINE.value:
                model.x2 += offset
                model.y2 += offset
            if kind == "PIN" and isinstance(model, PinModel):
                unit.pins.append(model)
            elif kind == "TEXT" and isinstance(model, TextModel):
                unit.texts.append(model)
            elif kind == "GRAPHIC" and isinstance(model, GraphicObjectModel):
                unit.graphics.append(model)
            elif kind == "SYMBOL_BODY" and isinstance(model, SymbolBodyModel):
                unit.body = model
        self.rebuild_scene()

    def set_grid(self, value: float):
        self.document.grid_inch = value
        self.rebuild_scene()

    def set_origin(self, value: str):
        self.document.origin = value

    def resize_body(self, item: SymbolBodyItem, width=None, height=None):
        if width is not None:
            item.model.width = width
        if height is not None:
            item.model.height = height
        grid_px = self.document.grid_inch * PX_PER_INCH
        item.setRect(0, 0, item.model.width * grid_px, item.model.height * grid_px)
        item.update()
        self.refresh_side_panels()

    def set_text_value(self, item: TextGraphicsItem, value: str):
        item.model.text = value
        item.setPlainText(value)
        self.refresh_side_panels()

    def set_text_font(self, item: TextGraphicsItem, family=None, size=None):
        if family is not None:
            item.model.font_family = family
        if size is not None:
            item.model.font_size_grid = size
        grid_px = self.document.grid_inch * PX_PER_INCH
        item.setFont(QFont(item.model.font_family, max(6, int(grid_px * item.model.font_size_grid * 0.45))))

    def save_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Symbol JSON", "symbol.json", "JSON (*.json)")
        if path:
            save_document(path, self.document)

    def load_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Symbol JSON", "", "JSON (*.json)")
        if not path:
            return
        self.document = load_document(path)
        self.current_unit_index = 0
        self.grid_spin.setValue(self.document.grid_inch)
        self.origin_combo.setCurrentText(self.document.origin)
        self.rebuild_tabs()
        self.rebuild_scene()
