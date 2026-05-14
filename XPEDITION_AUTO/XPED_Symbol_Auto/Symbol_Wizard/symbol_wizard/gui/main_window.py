from __future__ import annotations
import copy
import csv
import re
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QAction, QColor, QKeySequence, QFontDatabase
from PySide6.QtWidgets import *
from symbol_wizard.config import load_symbol_type_config

from symbol_wizard.models.document import *
from symbol_wizard.rules.grid import PX_PER_INCH, duplicate_pin_numbers, next_pin_number
from symbol_wizard.rules.placement import create_auto_pin
from symbol_wizard.graphics.scene import SymbolScene, SHEET_INCHES, sheet_rect_for
from symbol_wizard.graphics.view import SymbolView
from symbol_wizard.graphics.items import BodyItem, PinItem, TextItem, GraphicItem, OriginItem
from symbol_wizard.io.json_store import save_library, load_library, save_symbol, load_symbol


class ComboBoxDelegate(QStyledItemDelegate):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.items = [str(x) for x in items]

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.addItems(self.items)
        combo.setEditable(False)
        return combo

    def setEditorData(self, editor, index):
        value = str(index.data(Qt.EditRole) or index.data(Qt.DisplayRole) or '')
        i = editor.findText(value)
        editor.setCurrentIndex(max(0, i))

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.EditRole)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.library = LibraryModel()
        self.current_unit_index = 0
        self.draw_tool = DrawTool.SELECT.value
        self.clipboard: list[tuple[str, object]] = []
        self.suspend = False
        self._selection_restore_ids: set[int] = set()
        self.default_color = (0, 0, 0)
        self._refresh_visual_only = False
        self.body_edit = False
        self.symbol_type_config = load_symbol_type_config()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self._scheduled_refresh)
        self.scene = SymbolScene(self)
        self.view = SymbolView(self.scene, self)
        self.setWindowTitle('Symbol Wizard')
        self.resize(1600, 980)
        self._build_ui()
        self.rebuild_all()

    @property
    def symbol(self) -> SymbolModel:
        return self.library.current_symbol()

    @property
    def current_unit(self) -> SymbolUnitModel:
        if not self.symbol.units:
            self.symbol.units.append(SymbolUnitModel())
        self.current_unit_index = max(0, min(self.current_unit_index, len(self.symbol.units) - 1))
        return self.symbol.units[self.current_unit_index]

    @property
    def grid_px(self) -> float:
        return self.symbol.grid_inch * PX_PER_INCH

    def scene_to_grid_x(self, x):
        return round(x / self.grid_px)

    def scene_to_grid_y(self, y):
        return round(-y / self.grid_px)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self._menu()
        self._ribbon()

        self.single_tabs = QTabWidget()
        self.single_tabs.currentChanged.connect(lambda i: self.change_symbol_from_tab(SymbolKind.SINGLE.value, i))
        self.single_tabs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.single_tabs.customContextMenuRequested.connect(lambda pos: self.symbol_tab_context_menu(SymbolKind.SINGLE.value, pos))
        self.split_tabs = QTabWidget()
        self.split_tabs.currentChanged.connect(lambda i: self.change_symbol_from_tab(SymbolKind.SPLIT.value, i))
        self.split_tabs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.split_tabs.customContextMenuRequested.connect(lambda pos: self.symbol_tab_context_menu(SymbolKind.SPLIT.value, pos))

        # Pin overview for the Symbols workspace. The complete object hierarchy stays
        # in the lower Object Tree; the upper area is now a compact pin table.
        self.single_pin_table = self._create_pin_overview_table()

        self.unit_tabs = QTabWidget()
        self.unit_tabs.currentChanged.connect(self.change_unit)
        self.unit_tabs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.unit_tabs.customContextMenuRequested.connect(self.unit_tab_context_menu)
        self.add_unit_button = QPushButton('Add Unit / Split Part')
        self.add_unit_button.clicked.connect(self.add_unit)

        self.object_tree = QTreeWidget()
        self.object_tree.setHeaderLabels(['Object', 'Info'])
        self.object_tree.itemClicked.connect(self.tree_clicked)
        self.object_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.object_tree.customContextMenuRequested.connect(lambda pos: self.tree_context_menu(self.object_tree, pos))

        self.split_pin_table = self._create_pin_overview_table()

        self.split_object_tree = QTreeWidget()
        self.split_object_tree.setHeaderLabels(['Object', 'Info'])
        self.split_object_tree.itemClicked.connect(self.tree_clicked)
        self.split_object_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.split_object_tree.customContextMenuRequested.connect(lambda pos: self.tree_context_menu(self.split_object_tree, pos))

        single_page = QWidget()
        single_layout = QVBoxLayout(single_page)
        single_layout.addWidget(QLabel('Single Symbols'))
        single_layout.addWidget(self.single_tabs)
        single_layout.addWidget(QLabel('Pins of selected single symbol'))
        single_layout.addWidget(self.single_pin_table, 2)
        single_layout.addWidget(QLabel('Object Tree'))
        single_layout.addWidget(self.object_tree)

        split_page = QWidget()
        split_layout = QVBoxLayout(split_page)
        split_layout.addWidget(QLabel('Split Symbols'))
        split_layout.addWidget(self.split_tabs)
        split_layout.addWidget(QLabel('Units / Split Parts'))
        split_layout.addWidget(self.unit_tabs)
        split_layout.addWidget(self.add_unit_button)
        info = QLabel('Verification for split symbols is performed across all units as one symbol.')
        info.setWordWrap(True)
        split_layout.addWidget(info)
        split_layout.addWidget(QLabel('Pins of selected split part'))
        split_layout.addWidget(self.split_pin_table, 2)
        split_layout.addWidget(QLabel('Object Tree'))
        split_layout.addWidget(self.split_object_tree, 2)

        left_tabs = QTabWidget()
        left_tabs.currentChanged.connect(self.left_workspace_changed)
        self.left_tabs = left_tabs
        left_tabs.addTab(single_page, 'Symbols')
        left_tabs.addTab(split_page, 'Split Symbols')

        self.props = QWidget()
        self.form = QFormLayout(self.props)
        self.props_scroll = QScrollArea()
        self.props_scroll.setWidgetResizable(True)
        self.props_scroll.setWidget(self.props)

        self.canvas_tabs = QTabWidget()
        self.canvas_tabs.currentChanged.connect(self.change_symbol_from_canvas_tab)
        self.canvas_tabs.addTab(self.view, self.symbol.name)

        splitter = QSplitter()
        splitter.addWidget(left_tabs)
        splitter.addWidget(self.canvas_tabs)
        splitter.addWidget(self.props_scroll)
        splitter.setSizes([360, 900, 380])
        self.setCentralWidget(splitter)
        self.scene.selectionChanged.connect(self.refresh_properties)

    def _create_pin_overview_table(self):
        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(['Pin Number', 'Pin Name', 'Pin Function', 'Pin Type', 'Side', 'Inverted'])
        table.cellChanged.connect(self.pin_table_changed)
        table.cellClicked.connect(self.pin_table_clicked)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.horizontalHeader().setStretchLastSection(False)
        table.verticalHeader().setVisible(False)
        return table

    def _autosize_table(self, table: QTableWidget):
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        for col in range(table.columnCount()):
            table.setColumnWidth(col, max(table.columnWidth(col) + 18, 90))

    def _fill_pin_table(self, table: QTableWidget, rows):
        """Fill the pin table with editable columns and stable dropdown widgets.

        The first three columns are normal text cells. Pin Type, Side and
        Inverted are QComboBox cell widgets only; no underlying text item is
        installed in those cells, preventing Qt text/widget overpainting.
        """
        table.blockSignals(True)
        self.suspend = True
        # Remove old widgets explicitly before clearing, otherwise Qt can keep
        # stale editors around on some Windows/PySide combinations.
        for rr in range(table.rowCount()):
            for cc in range(table.columnCount()):
                w = table.cellWidget(rr, cc)
                if w is not None:
                    table.removeCellWidget(rr, cc)
                    w.deleteLater()
        table.clearContents()
        table.setRowCount(len(rows))
        pin_types = [x.value for x in PinType]
        sides = [x.value for x in PinSide]
        for r, (si, ui, pi, pin) in enumerate(rows):
            values = [pin.number, pin.name, pin.function]
            for c, v in enumerate(values):
                it = QTableWidgetItem(str(v))
                it.setData(Qt.UserRole, (si, ui, pi, c))
                it.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                table.setItem(r, c, it)

            meta = (si, ui, pi)
            cb_type = QComboBox(table)
            cb_type.addItems(pin_types)
            cb_type.setCurrentText(pin.pin_type if pin.pin_type in pin_types else PinType.BIDI.value)
            cb_type.setProperty('pin_meta', meta)
            cb_type.currentTextChanged.connect(lambda v, m=meta: self.pin_table_combo_changed(m, 3, v))
            table.setCellWidget(r, 3, cb_type)

            cb_side = QComboBox(table)
            cb_side.addItems(sides)
            cb_side.setCurrentText(pin.side if pin.side in sides else PinSide.LEFT.value)
            cb_side.setProperty('pin_meta', meta)
            cb_side.currentTextChanged.connect(lambda v, m=meta: self.pin_table_combo_changed(m, 4, v))
            table.setCellWidget(r, 4, cb_side)

            cb_inv = QComboBox(table)
            cb_inv.addItems(['no', 'yes'])
            cb_inv.setCurrentText('yes' if pin.inverted else 'no')
            cb_inv.setProperty('pin_meta', meta)
            cb_inv.currentTextChanged.connect(lambda v, m=meta: self.pin_table_combo_changed(m, 5, v))
            table.setCellWidget(r, 5, cb_inv)
        self.suspend = False
        table.blockSignals(False)
        self._autosize_table(table)

    def _menu(self):
        mb = self.menuBar()
        file_menu = mb.addMenu('&File')
        entries = [
            ('New Symbol', self.new_single_symbol, 'Ctrl+N'),
            ('New Split Symbol', self.new_split_symbol, 'Ctrl+Shift+N'),
            ('Open Library JSON', self.open_library, 'Ctrl+O'),
            ('Save Current Symbol JSON', self.save_current_symbol, 'Ctrl+S'),
            ('Save All Symbols JSON', self.save_all_symbols, 'Ctrl+Shift+S'),
            ('Import Symbol JSON', self.import_symbol, None),
            ('Import PINMUX CSV', self.import_pinmux_csv, None),
            ('Exit', self.close, None),
        ]
        for label, fn, sc in entries:
            a = QAction(label, self)
            a.triggered.connect(fn)
            if sc:
                a.setShortcut(QKeySequence(sc))
            file_menu.addAction(a)

        edit_menu = mb.addMenu('&Edit')
        for label, fn, sc in [
            ('Copy', self.copy_selected, 'Ctrl+C'),
            ('Paste', self.paste_selected, 'Ctrl+V'),
            ('Delete', self.delete_selected, 'Del'),
            ('Validate Pins', self.validate_pins, None),
        ]:
            a = QAction(label, self)
            a.triggered.connect(fn)
            if sc:
                a.setShortcut(QKeySequence(sc))
            edit_menu.addAction(a)

        view_menu = mb.addMenu('&View')
        for label, fn, sc in [
            ('Zoom to Fit Symbol', self.zoom_to_fit_symbol, 'Ctrl+F'),
            ('Zoom to Fit Sheet', self.zoom_to_fit_sheet, 'Ctrl+Shift+F'),
            ('Refresh Canvas', self.rebuild_scene, 'F5'),
        ]:
            a = QAction(label, self)
            a.triggered.connect(fn)
            if sc:
                a.setShortcut(QKeySequence(sc))
            view_menu.addAction(a)

    def _ribbon(self):
        tb = QToolBar('Draw Ribbon')
        self.addToolBar(tb)
        self.tool_buttons = {}
        for tool, label in [
            (DrawTool.SELECT, 'Select/Edit'),
            (DrawTool.PIN_LEFT, 'Pin L'),
            (DrawTool.PIN_RIGHT, 'Pin R'),
            (DrawTool.TEXT, 'Text'),
            (DrawTool.LINE, 'Line'),
            (DrawTool.RECT, 'Rect'),
            (DrawTool.ELLIPSE, 'Ellipse'),
        ]:
            a = QAction(label, self)
            a.setCheckable(True)
            a.triggered.connect(lambda checked, t=tool.value: self.set_tool(t))
            tb.addAction(a)
            self.tool_buttons[tool.value] = a
        self.tool_buttons[self.draw_tool].setChecked(True)
        tb.addSeparator()

        tb.addWidget(QLabel('Grid inch:'))
        self.grid_spin = QDoubleSpinBox()
        self.grid_spin.setRange(.05, .5)
        self.grid_spin.setSingleStep(.05)
        self.grid_spin.setDecimals(3)
        self.grid_spin.valueChanged.connect(self.set_grid)
        tb.addWidget(self.grid_spin)

        tb.addWidget(QLabel('Format:'))
        self.format_combo = QComboBox()
        self.format_combo.addItems([x.value for x in SheetFormat])
        self.format_combo.currentTextChanged.connect(self.set_sheet_format)
        tb.addWidget(self.format_combo)

        tb.addWidget(QLabel('Origo:'))
        self.origin_combo = QComboBox()
        self.origin_combo.addItems([x.value for x in OriginMode])
        self.origin_combo.currentTextChanged.connect(self.set_origin_mode)
        tb.addWidget(self.origin_combo)

        zoom_btn = QPushButton('Zoom Fit')
        zoom_btn.clicked.connect(self.zoom_to_fit_symbol)
        tb.addWidget(zoom_btn)

        tb.addSeparator()
        tb.addWidget(QLabel('Select filter:'))
        self.select_filter_combo = QComboBox()
        self.select_filter_combo.addItems(['All', 'Body', 'Pins', 'Graphics', 'Text'])
        self.select_filter_combo.currentTextChanged.connect(self.apply_canvas_select_filter)
        tb.addWidget(self.select_filter_combo)

        self.body_edit_button = QPushButton('Body Edit: OFF')
        self.body_edit_button.setCheckable(True)
        self.body_edit_button.toggled.connect(self.set_body_edit_mode)
        tb.addWidget(self.body_edit_button)

        tb.addSeparator()
        tb.addWidget(QLabel('Style target:'))
        self.style_target_combo = QComboBox()
        self.style_target_combo.addItems(['Selection', 'Body', 'Pins', 'Graphics'])
        self.style_target_combo.currentTextChanged.connect(self.update_style_controls_from_target)
        tb.addWidget(self.style_target_combo)
        tb.addWidget(QLabel('Line:'))
        self.line_style = QComboBox()
        self.line_style.addItems([x.value for x in LineStyle])
        tb.addWidget(self.line_style)
        tb.addWidget(QLabel('Width grid:'))
        self.line_width = QDoubleSpinBox()
        self.line_width.setRange(.01, 1)
        self.line_width.setSingleStep(.01)
        self.line_width.setValue(.03)
        tb.addWidget(self.line_width)
        self.line_style.currentTextChanged.connect(self.apply_line_defaults)
        self.line_width.valueChanged.connect(self.apply_line_defaults)

        color = QPushButton('RGB')
        color.clicked.connect(self.pick_default_color)
        tb.addWidget(color)
        tb.addSeparator()
        tb.addWidget(QLabel('Symbol Name:'))
        self.symbol_name_edit = QLineEdit()
        self.symbol_name_edit.setMinimumWidth(180)
        self.symbol_name_edit.editingFinished.connect(self.apply_symbol_name_from_edit)
        tb.addWidget(self.symbol_name_edit)

        tb.addWidget(QLabel('Type:'))
        self.symbol_type_combo = QComboBox()
        self.symbol_type_combo.addItems(sorted(self.symbol_type_config.get('types', {}).keys()))
        self.symbol_type_combo.currentTextChanged.connect(self.symbol_type_changed)
        tb.addWidget(self.symbol_type_combo)
        tb.addWidget(QLabel('Subtype:'))
        self.symbol_subtype_combo = QComboBox()
        self.symbol_subtype_combo.currentTextChanged.connect(self.symbol_subtype_changed)
        tb.addWidget(self.symbol_subtype_combo)

        tb.addWidget(QLabel('Unit/Part:'))
        self.unit_name_edit = QLineEdit()
        self.unit_name_edit.setMinimumWidth(140)
        self.unit_name_edit.editingFinished.connect(self.apply_unit_name_from_edit)
        tb.addWidget(self.unit_name_edit)

        tb.addSeparator()

        for label, fn in [
            ('⟲ 90°', lambda: self.rotate_selected(-90)),
            ('⟳ 90°', lambda: self.rotate_selected(90)),
        ]:
            b = QPushButton(label)
            b.clicked.connect(fn)
            tb.addWidget(b)

        for label, fn in [('Mirror X', lambda: self.mirror_selected('x')), ('Mirror Y', lambda: self.mirror_selected('y'))]:
            b = QPushButton(label)
            b.clicked.connect(fn)
            tb.addWidget(b)

        tb.addSeparator()
        tb.addWidget(QLabel('Selected Pins:'))
        self.selected_pin_side_combo = QComboBox()
        self.selected_pin_side_combo.addItems([x.value for x in PinSide])
        tb.addWidget(self.selected_pin_side_combo)
        b = QPushButton('Assign Side')
        b.clicked.connect(lambda: self.set_selected_pins_side(self.selected_pin_side_combo.currentText()))
        tb.addWidget(b)
        b = QPushButton('Distribute Vertical')
        b.clicked.connect(self.distribute_selected_pins_vertical)
        tb.addWidget(b)

    # ------------------------------------------------------------------ Rebuilds
    def rebuild_all(self):
        # Font sizes are grid-derived. Sync before rebuilding the scene so
        # generated attribute/RefDes text items use the current grid size.
        self.sync_font_points_to_grid()
        self.rebuild_symbol_tabs()
        self.rebuild_canvas_tabs()
        self.rebuild_unit_tabs()
        self.rebuild_scene()
        self.rebuild_tree()
        self.rebuild_pin_table()
        self.grid_spin.blockSignals(True)
        self.grid_spin.setValue(self.symbol.grid_inch)
        self.grid_spin.blockSignals(False)
        self.origin_combo.blockSignals(True)
        self.origin_combo.setCurrentText(getattr(self.symbol, 'origin', OriginMode.CENTER.value))
        self.origin_combo.blockSignals(False)
        self.format_combo.blockSignals(True)
        self.format_combo.setCurrentText(getattr(self.symbol, 'sheet_format', SheetFormat.A3.value))
        self.format_combo.blockSignals(False)
        self.update_symbol_type_controls()
        self.update_name_editors()
        self.left_tabs.setCurrentIndex(1 if self.symbol.kind == SymbolKind.SPLIT.value else 0)

    def _symbol_indices(self, kind: str):
        return [i for i, s in enumerate(self.library.symbols) if s.kind == kind]

    def rebuild_symbol_tabs(self):
        self.single_tabs.blockSignals(True)
        self.split_tabs.blockSignals(True)
        self.single_tabs.clear()
        self.split_tabs.clear()
        for idx in self._symbol_indices(SymbolKind.SINGLE.value):
            self.single_tabs.addTab(QWidget(), self.library.symbols[idx].name)
        for idx in self._symbol_indices(SymbolKind.SPLIT.value):
            self.split_tabs.addTab(QWidget(), self.library.symbols[idx].name)
        cur = self.library.current_symbol_index
        single_indices = self._symbol_indices(SymbolKind.SINGLE.value)
        split_indices = self._symbol_indices(SymbolKind.SPLIT.value)
        if cur in single_indices:
            self.single_tabs.setCurrentIndex(single_indices.index(cur))
        if cur in split_indices:
            self.split_tabs.setCurrentIndex(split_indices.index(cur))
        self.single_tabs.blockSignals(False)
        self.split_tabs.blockSignals(False)

    def canvas_label_for_symbol(self, symbol: SymbolModel, index: int) -> str:
        """Label for the canvas tab. Split symbols show the active split part."""
        if symbol.kind == SymbolKind.SPLIT.value:
            ui = self.current_unit_index if index == self.library.current_symbol_index else 0
            if symbol.units:
                ui = max(0, min(ui, len(symbol.units) - 1))
                return f'{symbol.name}.{symbol.units[ui].name}'
        return symbol.name

    def rebuild_canvas_tabs(self):
        """Top-level canvas tabs. Each symbol gets its own canvas tab name; switching changes the model shown in the canvas."""
        if not hasattr(self, 'canvas_tabs'):
            return
        self.canvas_tabs.blockSignals(True)
        current_widget = self.view
        # Remove all tabs without deleting the view widget.
        while self.canvas_tabs.count():
            self.canvas_tabs.removeTab(0)
        for idx, s in enumerate(self.library.symbols):
            self.canvas_tabs.addTab(current_widget if self.canvas_tabs.count() == self.library.current_symbol_index else QWidget(), self.canvas_label_for_symbol(s, idx))
        # Make sure the real canvas widget is placed at the current symbol index.
        cur = self.library.current_symbol_index
        for i in range(self.canvas_tabs.count()):
            if self.canvas_tabs.widget(i) is current_widget and i != cur:
                self.canvas_tabs.removeTab(i)
                self.canvas_tabs.insertTab(i, QWidget(), self.canvas_label_for_symbol(self.library.symbols[i], i))
                break
        if self.canvas_tabs.widget(cur) is not current_widget:
            self.canvas_tabs.removeTab(cur)
            self.canvas_tabs.insertTab(cur, current_widget, self.canvas_label_for_symbol(self.symbol, cur))
        self.canvas_tabs.setCurrentIndex(cur)
        self.canvas_tabs.blockSignals(False)

    def update_symbol_type_controls(self):
        if not hasattr(self, 'symbol_type_combo'):
            return
        types = self.symbol_type_config.get('types', {})
        self.symbol_type_combo.blockSignals(True)
        self.symbol_subtype_combo.blockSignals(True)
        if self.symbol_type_combo.count() == 0:
            self.symbol_type_combo.addItems(sorted(types.keys()))
        typ = getattr(self.symbol, 'symbol_type', 'IC')
        if typ not in types and types:
            typ = sorted(types.keys())[0]
            self.symbol.symbol_type = typ
        self.symbol_type_combo.setCurrentText(typ)
        self.populate_subtypes_for_type(typ)
        self.symbol_subtype_combo.setCurrentText(getattr(self.symbol, 'symbol_subtype', ''))
        self.symbol_subtype_combo.blockSignals(False)
        self.symbol_type_combo.blockSignals(False)

    def populate_subtypes_for_type(self, typ: str):
        self.symbol_subtype_combo.clear()
        data = self.symbol_type_config.get('types', {}).get(typ, {})
        subtypes = data.get('subtypes', {})
        names = list(subtypes.keys()) or ['Generic']
        self.symbol_subtype_combo.addItems(names)

    def symbol_type_changed(self, typ: str):
        if self.suspend or not typ:
            return
        self.symbol.symbol_type = typ
        self.populate_subtypes_for_type(typ)
        subtype = self.symbol_subtype_combo.currentText() or 'Generic'
        self.symbol.symbol_subtype = subtype
        self.apply_symbol_template(typ, subtype)

    def symbol_subtype_changed(self, subtype: str):
        if self.suspend or not subtype:
            return
        typ = self.symbol_type_combo.currentText() or getattr(self.symbol, 'symbol_type', 'IC')
        self.symbol.symbol_type = typ
        self.symbol.symbol_subtype = subtype
        self.apply_symbol_template(typ, subtype)

    def _profile_for(self, typ: str, subtype: str):
        types = self.symbol_type_config.get('types', {})
        data = dict(types.get(typ, {}))
        subdata = data.get('subtypes', {}).get(subtype, {}) or {}
        return data, subdata

    def apply_symbol_template(self, typ: str, subtype: str, reset_pins: bool = False):
        data, subdata = self._profile_for(typ, subtype)
        if not data:
            return
        for u in self.symbol.units:
            body = u.body
            body_tpl = dict(data.get('body', {}) or {})
            body_tpl.update(subdata.get('body', {}) or {})
            old_w, old_h = body.width, body.height
            body.width = float(body_tpl.get('width', body.width))
            body.height = float(body_tpl.get('height', body.height))
            body.body_shape = str(body_tpl.get('shape', getattr(body, 'body_shape', 'rect')))
            body.x = -body.width / 2.0
            body.y = body.height / 2.0
            global_attrs = self.symbol_type_config.get('global_attributes', ['RefDes', 'Package', 'Order Code', 'Value'])
            attrs = []
            attrs.extend(global_attrs)
            attrs.extend(data.get('attributes', []))
            attrs.extend(subdata.get('attributes', []))
            clean_attrs = []
            for a in attrs:
                if a not in clean_attrs:
                    clean_attrs.append(a)
            prefix = subdata.get('prefix', data.get('prefix', 'U'))
            old_refdes = body.attributes.get('RefDes', '')
            existing = dict(body.attributes)
            body.attributes = {a: existing.get(a, '') for a in clean_attrs}
            body.attributes['RefDes'] = old_refdes or f'{prefix}?'
            self.update_refdes_prefix(body, prefix)
            body.visible_attributes = {a: (a in global_attrs) for a in clean_attrs}
            body.visible_attributes['RefDes'] = True
            # Keep existing pins unless there are none or caller requests template replacement.
            if reset_pins or not u.pins:
                u.pins.clear()
                pins = list(data.get('default_pins', []))
                # 4-pin crystal shortcut if subtype declares pins=4.
                if typ == 'Quartz' and int(subdata.get('pins', 2)) == 4:
                    pins = [
                        {'number':'1','name':'XTAL1','type':'PASSIVE','side':'left'},
                        {'number':'2','name':'GND','type':'GROUND','side':'left'},
                        {'number':'3','name':'XTAL2','type':'PASSIVE','side':'right'},
                        {'number':'4','name':'GND_2','type':'GROUND','side':'right'},
                    ]
                for i, pd in enumerate(pins):
                    side = pd.get('side', 'left')
                    x = body.x if side == 'left' else body.x + body.width
                    y = body.y - 2 - i * 2
                    u.pins.append(PinModel(
                        number=str(pd.get('number', i + 1)),
                        name=str(pd.get('name', f'PIN{i+1}')),
                        function=str(pd.get('function', pd.get('name', f'PIN{i+1}'))),
                        pin_type=str(pd.get('type', 'BIDI')),
                        side=side,
                        x=x,
                        y=y,
                    ))
            self.dock_pins_to_body(u)
            self.ensure_unique_pin_names(self.symbol)
        self.rebuild_scene()
        self.rebuild_tree()
        self.rebuild_pin_table()
        self.refresh_properties()
    def update_name_editors(self):
        if hasattr(self, 'symbol_name_edit'):
            self.symbol_name_edit.blockSignals(True)
            self.symbol_name_edit.setText(self.symbol.name)
            self.symbol_name_edit.blockSignals(False)
        if hasattr(self, 'unit_name_edit'):
            self.unit_name_edit.blockSignals(True)
            self.unit_name_edit.setText(self.current_unit.name)
            self.unit_name_edit.setEnabled(self.symbol.kind == SymbolKind.SPLIT.value)
            self.unit_name_edit.blockSignals(False)

    def apply_symbol_name_from_edit(self):
        name = self.symbol_name_edit.text().strip() or self.symbol.name
        self.rename_current_symbol(name)

    def apply_unit_name_from_edit(self):
        if self.symbol.kind != SymbolKind.SPLIT.value:
            return
        base = self.unit_name_edit.text().strip() or self.current_unit.name
        self.current_unit.name = base
        self.rebuild_unit_tabs()
        self.rebuild_canvas_tabs()
        self.rebuild_tree()
        self.update_name_editors()

    def rename_current_symbol(self, desired: str):
        cur = self.library.current_symbol_index
        existing = {s.name for i, s in enumerate(self.library.symbols) if i != cur}
        name = desired
        if name in existing:
            i = 2
            while f'{name}_{i}' in existing:
                i += 1
            name = f'{name}_{i}'
        self.symbol.name = name
        if self.symbol.kind == SymbolKind.SPLIT.value:
            # Split parts use the symbol name plus running suffix.
            for i, u in enumerate(self.symbol.units, start=1):
                u.name = f'{name}_{i}'
        self.rebuild_symbol_tabs()
        self.rebuild_canvas_tabs()
        self.rebuild_unit_tabs()
        self.rebuild_canvas_tabs()
        self.rebuild_tree()
        self.update_name_editors()

    def rebuild_unit_tabs(self):
        self.unit_tabs.blockSignals(True)
        self.unit_tabs.clear()
        for u in self.symbol.units:
            self.unit_tabs.addTab(QWidget(), u.name)
        self.current_unit_index = max(0, min(self.current_unit_index, len(self.symbol.units) - 1))
        self.unit_tabs.setCurrentIndex(self.current_unit_index)
        self.unit_tabs.setEnabled(self.symbol.kind == SymbolKind.SPLIT.value)
        self.add_unit_button.setEnabled(self.symbol.kind == SymbolKind.SPLIT.value)
        self.unit_tabs.blockSignals(False)
        self.update_name_editors()

    def _capture_selection_ids(self):
        ids = set()
        for item in self.scene.selectedItems():
            model = getattr(item, 'model', None)
            if model is not None:
                ids.add(id(model))
        return ids

    def _restore_or_select_item(self, item, selected_ids):
        model = getattr(item, 'model', None)
        if model is not None and id(model) in selected_ids:
            item.setSelected(True)

    def rebuild_scene(self):
        selected_ids = self._selection_restore_ids or self._capture_selection_ids()
        self._selection_restore_ids = set()
        self.scene.blockSignals(True)
        self.scene.clear()
        u = self.current_unit
        self.dock_pins_to_body(u)

        body_item = BodyItem(u.body, self)
        self.scene.addItem(body_item)
        self._restore_or_select_item(body_item, selected_ids)

        origin_item = OriginItem(self.symbol, self)
        self.scene.addItem(origin_item)

        self.add_attribute_text_items(u)
        for g in u.graphics:
            item = GraphicItem(g, self)
            self.scene.addItem(item)
            self._restore_or_select_item(item, selected_ids)
        for p in u.pins:
            item = PinItem(p, self)
            self.scene.addItem(item)
            self._restore_or_select_item(item, selected_ids)
        for t in u.texts:
            item = TextItem(t, self)
            self.scene.addItem(item)
            self._restore_or_select_item(item, selected_ids)
        self.apply_canvas_select_filter()
        self.scene.update()
        self.scene.blockSignals(False)
        self.refresh_properties()

    def select_model_after_rebuild(self, model):
        self._selection_restore_ids = {id(model)}

    def add_attribute_text_items(self, u: SymbolUnitModel):
        b = u.body
        ref = b.attributes.get('RefDes', '')
        if b.visible_attributes.get('RefDes', False) and ref:
            # RefDes is handled like all other body attributes: same font family,
            # same grid-relative font size and same font color. It is positioned
            # at the top body edge, but no longer has a separate font model that
            # can get out of sync with the attribute controls.
            txt = TextItem(TextModel(
                text=ref,
                x=b.x,
                y=b.y + 1,
                font_family=b.attribute_font.family,
                font_size_pt=b.attribute_font.size_pt,
                font_size_grid=b.attribute_font.size_grid,
                color=b.attribute_font.color,
            ), self)
            txt.setFlag(QGraphicsItem.ItemIsMovable, False)
            txt.setData(0, 'ATTR_REF_DES')
            self.scene.addItem(txt)
        row = 1
        for k, v in b.attributes.items():
            if k == 'RefDes' or not b.visible_attributes.get(k, False) or not v:
                continue
            txt = TextItem(TextModel(text=f'{k}: {v}', x=b.x, y=b.y - b.height - row, font_family=b.attribute_font.family, font_size_pt=b.attribute_font.size_pt, font_size_grid=b.attribute_font.size_grid, color=b.attribute_font.color), self)
            txt.setFlag(QGraphicsItem.ItemIsMovable, False)
            txt.setData(0, 'ATTR_BODY')
            self.scene.addItem(txt)
            row += 1

    def rebuild_tree(self):
        # Upper left areas show only pin tables; lower areas keep the object hierarchy.
        self._populate_current_object_tree(self.object_tree)
        if hasattr(self, 'split_object_tree'):
            self._populate_current_object_tree(self.split_object_tree)
        self.rebuild_pin_table()

    def _populate_single_symbol_tree(self):
        """Tree for the Symbols workspace: single symbols with their pins and objects."""
        tree = self.single_symbol_tree
        tree.clear()
        for si, symbol in enumerate(self.library.symbols):
            if symbol.kind != SymbolKind.SINGLE.value:
                continue
            sym_item = QTreeWidgetItem([symbol.name, 'Single Symbol'])
            sym_item.setData(0, Qt.UserRole, ('symbol', si, None))
            tree.addTopLevelItem(sym_item)
            for ui, u in enumerate(symbol.units):
                unit_item = QTreeWidgetItem([u.name, 'Symbol Body / Unit'])
                unit_item.setData(0, Qt.UserRole, ('single_unit', si, ui))
                sym_item.addChild(unit_item)

                body = QTreeWidgetItem(['Body', f'{u.body.width:g} x {u.body.height:g}'])
                body.setData(0, Qt.UserRole, ('single_body', si, ui))
                unit_item.addChild(body)

                attrs = QTreeWidgetItem(['Attributes', 'Body'])
                unit_item.addChild(attrs)
                for k, v in u.body.attributes.items():
                    attrs.addChild(QTreeWidgetItem([k, f'{v} / visible={u.body.visible_attributes.get(k, False)}']))

                pins = QTreeWidgetItem(['Pins', str(len(u.pins))])
                unit_item.addChild(pins)
                for pi, pin in enumerate(u.pins):
                    pin_item = QTreeWidgetItem([f'Pin {pin.number}', f'{pin.name} | {pin.function} | {pin.pin_type} | {pin.side}'])
                    pin_item.setData(0, Qt.UserRole, ('single_pin', si, ui, pi))
                    pins.addChild(pin_item)

                texts = QTreeWidgetItem(['Text', str(len(u.texts))])
                unit_item.addChild(texts)
                for ti, t in enumerate(u.texts):
                    text_item = QTreeWidgetItem([t.text[:30], f'{t.font_family} {getattr(t, 'font_size_pt', 7.2):g} pt'])
                    text_item.setData(0, Qt.UserRole, ('single_text', si, ui, ti))
                    texts.addChild(text_item)

                graphics = QTreeWidgetItem(['Graphics', str(len(u.graphics))])
                unit_item.addChild(graphics)
                for gi, g in enumerate(u.graphics):
                    gr_item = QTreeWidgetItem([g.shape, f'{g.w:g} x {g.h:g}' + (' / body' if getattr(g, 'body_attached', False) else '')])
                    gr_item.setData(0, Qt.UserRole, ('single_graphic', si, ui, gi))
                    graphics.addChild(gr_item)
        tree.expandAll()
        tree.resizeColumnToContents(0)
        tree.resizeColumnToContents(1)

    def _populate_current_object_tree(self, tree: QTreeWidget):
        tree.clear()
        root = QTreeWidgetItem([self.symbol.name, 'Split Symbol' if self.symbol.kind == SymbolKind.SPLIT.value else 'Single Symbol'])
        tree.addTopLevelItem(root)
        for ui, u in enumerate(self.symbol.units):
            unit = QTreeWidgetItem([u.name, 'Unit / Symbol Part'])
            unit.setData(0, Qt.UserRole, ('unit', ui, None))
            root.addChild(unit)
            body = QTreeWidgetItem(['Body', f'{u.body.width:g} x {u.body.height:g}'])
            body.setData(0, Qt.UserRole, ('body', ui, None))
            unit.addChild(body)
            attrs = QTreeWidgetItem(['Attributes', 'Body'])
            unit.addChild(attrs)
            for k, v in u.body.attributes.items():
                att = QTreeWidgetItem([k, f'{v} / visible={u.body.visible_attributes.get(k, False)}'])
                attrs.addChild(att)
            pins = QTreeWidgetItem(['Pins', str(len(u.pins))])
            unit.addChild(pins)
            for pi, p in enumerate(u.pins):
                pin = QTreeWidgetItem([f'Pin {p.number}', f'{p.name} | {p.function} | {p.pin_type} | {p.side}'])
                pin.setData(0, Qt.UserRole, ('pin', ui, pi))
                pins.addChild(pin)
            texts = QTreeWidgetItem(['Text', str(len(u.texts))])
            unit.addChild(texts)
            for ti, t in enumerate(u.texts):
                text = QTreeWidgetItem([t.text[:30], f'{t.font_family} {getattr(t, 'font_size_pt', 7.2):g} pt'])
                text.setData(0, Qt.UserRole, ('text', ui, ti))
                texts.addChild(text)
            graphics = QTreeWidgetItem(['Graphics', str(len(u.graphics))])
            unit.addChild(graphics)
            for gi, g in enumerate(u.graphics):
                gr = QTreeWidgetItem([g.shape, f'{g.w:g} x {g.h:g}' + (' / body' if getattr(g, 'body_attached', False) else '')])
                gr.setData(0, Qt.UserRole, ('graphic', ui, gi))
                graphics.addChild(gr)
        tree.expandAll()
        tree.resizeColumnToContents(0)
        tree.resizeColumnToContents(1)

    def _populate_split_symbol_tree(self):
        tree = self.split_symbol_tree
        tree.clear()
        for si, symbol in enumerate(self.library.symbols):
            if symbol.kind != SymbolKind.SPLIT.value:
                continue
            sym_item = QTreeWidgetItem([symbol.name, 'Split Symbol'])
            sym_item.setData(0, Qt.UserRole, ('symbol', si, None))
            tree.addTopLevelItem(sym_item)
            for ui, u in enumerate(symbol.units):
                unit_item = QTreeWidgetItem([u.name, f'{len(u.pins)} pins'])
                unit_item.setData(0, Qt.UserRole, ('split_unit', si, ui))
                sym_item.addChild(unit_item)
                for pi, pin in enumerate(u.pins):
                    pin_item = QTreeWidgetItem([f'Pin {pin.number}', f'{pin.name} | {pin.function} | {pin.pin_type} | {pin.side}'])
                    pin_item.setData(0, Qt.UserRole, ('split_pin', si, ui, pi))
                    unit_item.addChild(pin_item)
        tree.expandAll()
        tree.resizeColumnToContents(0)
        tree.resizeColumnToContents(1)

    def rebuild_pin_table(self):
        # Single Symbols: show pins of the currently selected single symbol only.
        if hasattr(self, 'single_pin_table'):
            rows = []
            if self.symbol.kind == SymbolKind.SINGLE.value:
                si = self.library.current_symbol_index
                for ui, u in enumerate(self.symbol.units):
                    for pi, pin in enumerate(u.pins):
                        rows.append((si, ui, pi, pin))
            self._fill_pin_table(self.single_pin_table, rows)

        # Split Symbols: show only pins of the currently selected split part.
        if hasattr(self, 'split_pin_table'):
            rows = []
            if self.symbol.kind == SymbolKind.SPLIT.value and self.symbol.units:
                si = self.library.current_symbol_index
                ui = max(0, min(self.current_unit_index, len(self.symbol.units) - 1))
                for pi, pin in enumerate(self.symbol.units[ui].pins):
                    rows.append((si, ui, pi, pin))
            self._fill_pin_table(self.split_pin_table, rows)

    # ------------------------------------------------------------------ Properties
    def clear_properties(self):
        while self.form.rowCount():
            self.form.removeRow(0)

    def refresh_properties(self):
        self.clear_properties()
        selected = [i for i in self.scene.selectedItems() if i.data(0) not in ('ATTR_REF_DES', 'ATTR_BODY')]
        if not selected:
            self.form.addRow(QLabel('No selection'))
            return
        if len(selected) > 1:
            self.form.addRow(QLabel(f'{len(selected)} objects selected'))
            pins = [i for i in selected if i.data(0) == 'PIN']
            if pins:
                self.form.addRow(QLabel(f'{len(pins)} selected pin(s)'))
                side = QComboBox(); side.addItems([x.value for x in PinSide])
                self.form.addRow('Pin Side', side)
                ptype = QComboBox(); ptype.addItems([x.value for x in PinType])
                self.form.addRow('Pin Type', ptype)
                func = QLineEdit('')
                self.form.addRow('Pin Function', func)
                length = self._dbl(2.0, lambda v: None, 1, 100, 1)
                self.form.addRow('Length [grid]', length)
                b = QPushButton('Apply geometry/function/type to selected pins')
                b.clicked.connect(lambda: self.apply_pin_bulk_to_selected(side.currentText(), ptype.currentText(), func.text(), length.value()))
                self.form.addRow('', b)
                b = QPushButton('Apply first selected pin geometry/function to ALL pins')
                b.clicked.connect(self.apply_first_selected_pin_to_all)
                self.form.addRow('', b)
                b = QPushButton('Distribute selected pins vertically')
                b.clicked.connect(self.distribute_selected_pins_vertical)
                self.form.addRow('', b)
            return
        item = selected[0]
        kind = item.data(0)
        self.form.addRow(QLabel(f'Selected: {kind}'))
        if kind == 'BODY': self.body_props(item)
        elif kind == 'PIN': self.pin_props(item)
        elif kind == 'TEXT': self.text_props(item)
        elif kind == 'GRAPHIC': self.graphic_props(item)

    def _line(self, value, fn):
        w = QLineEdit(str(value))
        # Commit text edits only with Enter. This prevents live rebuilds while typing.
        w.returnPressed.connect(lambda widget=w: fn(widget.text()))
        return w

    def _dbl(self, value, fn, lo=-999, hi=999, step=.1):
        w = QDoubleSpinBox()
        w.setRange(lo, hi)
        w.setSingleStep(step)
        w.setDecimals(3)
        w.setValue(float(value))
        w.valueChanged.connect(fn)
        return w

    def _combo(self, items, val, fn):
        w = QComboBox()
        w.addItems(items)
        w.setCurrentText(str(val))
        w.currentTextChanged.connect(fn)
        return w

    def font_family_combo(self, val, fn):
        w = QComboBox()
        families = list(QFontDatabase.families())
        preferred = ['Arial', 'Calibri', 'Segoe UI', 'Tahoma', 'Verdana', 'Times New Roman', 'Courier New']
        ordered = []
        for f in preferred + families:
            if f and f not in ordered:
                ordered.append(f)
        w.addItems(ordered)
        if val in ordered:
            w.setCurrentText(val)
        w.currentTextChanged.connect(fn)
        return w

    def body_props(self, item):
        m = item.model

        body_group = QGroupBox('Body')
        body_form = QFormLayout(body_group)
        body_form.addRow('Width [grid]', self._dbl(m.width, lambda v: self.set_body_dim(item, 'width', v), 1, 300, 1))
        body_form.addRow('Height [grid]', self._dbl(m.height, lambda v: self.set_body_dim(item, 'height', v), 1, 300, 1))
        body_form.addRow('Line style', self._combo([x.value for x in LineStyle], m.line_style, lambda v: self.set_and_refresh(m, 'line_style', v)))
        body_form.addRow('Line width [grid]', self._dbl(m.line_width, lambda v: self.set_and_refresh(m, 'line_width', v), .01, 1, .01))
        body_form.addRow('Body shape', self._combo(['rect','resistor','capacitor','inductor','diode','battery','transformer','transistor','fuse','connector','opamp','circle','custom'], getattr(m, 'body_shape', 'rect'), lambda v: self.set_and_refresh(m, 'body_shape', v)))
        eb = QPushButton('Enable Body Edit Mode')
        eb.clicked.connect(lambda: self.set_body_edit_mode(True))
        body_form.addRow('', eb)
        ab = QPushButton('Attach selected graphics to body')
        ab.clicked.connect(self.attach_selected_graphics_to_body)
        body_form.addRow('', ab)
        body_form.addRow('Rotation [deg]', self.rotation_combo(getattr(m, 'rotation', 0), lambda v: self.set_and_refresh(m, 'rotation', float(v))))
        b = QPushButton('Body Line Color RGB')
        b.clicked.connect(lambda: self.color_model(m))
        body_form.addRow('Color', b)
        self.form.addRow(body_group)

        attr_group = QGroupBox('Attributes')
        attr_outer = QVBoxLayout(attr_group)
        attr_font_row = QFormLayout()
        attr_font_row.addRow('Font family', self.font_family_combo(m.attribute_font.family, lambda v: self.set_font_attr(m.attribute_font, 'family', v, True)))
        attr_font_row.addRow('Font size [grid]', self._dbl(getattr(m.attribute_font, 'size_grid', 0.9), lambda v: self.set_font_attr(m.attribute_font, 'size_grid', v, True), .1, 5, .1))
        fb = QPushButton('Font Color RGB')
        fb.clicked.connect(lambda: self.color_font(m.attribute_font, True))
        attr_font_row.addRow('Font color', fb)
        attr_outer.addLayout(attr_font_row)

        attr_scroll = QScrollArea()
        attr_scroll.setWidgetResizable(True)
        attr_scroll.setMinimumHeight(220)
        attr_widget = QWidget()
        attr_form = QFormLayout(attr_widget)
        for k in list(m.attributes.keys()):
            row = QWidget()
            l = QHBoxLayout(row)
            l.setContentsMargins(0, 0, 0, 0)
            cb = QCheckBox('visible')
            cb.setChecked(m.visible_attributes.get(k, False))
            ed = QLineEdit(m.attributes.get(k, ''))
            cb.toggled.connect(lambda v, key=k: self.set_attr_vis(m, key, v))
            ed.returnPressed.connect(lambda key=k, editor=ed: self.set_attr_val(m, key, editor.text()))
            l.addWidget(cb)
            l.addWidget(ed)
            attr_form.addRow(k, row)
        attr_scroll.setWidget(attr_widget)
        attr_outer.addWidget(attr_scroll)
        self.form.addRow(attr_group)
    def pin_props(self, item):
        m = item.model
        for label, attr in [('Pin Number', 'number'), ('Pin Name', 'name'), ('Pin Function', 'function')]:
            self.form.addRow(label, self._line(getattr(m, attr), lambda v, a=attr: self.set_pin_attr(m, a, v)))
        self.form.addRow('Pin Type', self._combo([x.value for x in PinType], m.pin_type, lambda v: self.set_pin_attr(m, 'pin_type', v)))
        self.form.addRow('Side', self._combo([x.value for x in PinSide], m.side, lambda v: self.set_pin_attr(m, 'side', v)))
        inv = QCheckBox(); inv.setChecked(m.inverted); inv.toggled.connect(lambda v: self.set_pin_attr(m, 'inverted', v)); self.form.addRow('Inverted', inv)
        for label, attr in [('Show Number', 'visible_number'), ('Show Name', 'visible_name'), ('Show Function', 'visible_function')]:
            cb = QCheckBox(); cb.setChecked(getattr(m, attr)); cb.toggled.connect(lambda v, a=attr: self.set_pin_attr(m, a, v)); self.form.addRow(label, cb)
        self.form.addRow('Length [grid]', self._dbl(m.length, lambda v: self.set_pin_length(m, v), 1, 100, 1))
        self.form.addRow('Rotation [deg]', self.rotation_combo(getattr(m, 'rotation', 0), lambda v: self.set_pin_attr(m, 'rotation', float(v))))
        self.form.addRow('Line style', self._combo([x.value for x in LineStyle], m.line_style, lambda v: self.set_pin_attr(m, 'line_style', v)))
        self.form.addRow('Line width', self._dbl(m.line_width, lambda v: self.set_pin_attr(m, 'line_width', v), .01, 1, .01))
        self.font_props('Pin number font', m.number_font)
        self.font_props('Pin label font', m.label_font)
        b = QPushButton('Color RGB'); b.clicked.connect(lambda: self.color_model(m)); self.form.addRow('Color', b)
        b = QPushButton('Apply this pin geometry/function to ALL pins')
        b.clicked.connect(lambda: self.apply_pin_model_to_all(m))
        self.form.addRow('', b)

    def text_props(self, item):
        m = item.model
        self.form.addRow('Text', self._line(m.text, lambda v: self.set_text_attr(item, 'text', v)))
        self.form.addRow('Font', self.font_family_combo(m.font_family, lambda v: self.set_text_attr(item, 'font_family', v)))
        self.form.addRow('Size [grid]', self._dbl(getattr(m, 'font_size_grid', 0.9), lambda v: self.set_text_attr(item, 'font_size_grid', v), .1, 5, .1))
        self.transform_props(m)
        b = QPushButton('Color RGB'); b.clicked.connect(lambda: self.color_model(m)); self.form.addRow('Color', b)

    def graphic_props(self, item):
        m = item.model
        self.form.addRow('Shape', self._combo(['line', 'rect', 'ellipse'], m.shape, lambda v: self.set_and_refresh(m, 'shape', v)))
        self.form.addRow('Width [grid]', self._dbl(m.w, lambda v: self.set_and_refresh(m, 'w', v), -100, 300))
        self.form.addRow('Height [grid]', self._dbl(m.h, lambda v: self.set_and_refresh(m, 'h', v), -100, 300))
        self.form.addRow('Line style', self._combo([x.value for x in LineStyle], m.style.line_style, lambda v: self.set_style(m, 'line_style', v)))
        self.form.addRow('Line width', self._dbl(m.style.line_width, lambda v: self.set_style(m, 'line_width', v), .01, 1, .01))
        self.transform_props(m)
        b = QPushButton('Stroke RGB'); b.clicked.connect(lambda: self.color_model(m.style, 'stroke')); self.form.addRow('Color', b)

    def font_props(self, title, f, refresh_attrs=False):
        self.form.addRow(QLabel(title))
        self.form.addRow('Family', self.font_family_combo(f.family, lambda v: self.set_font_attr(f, 'family', v, refresh_attrs)))
        self.form.addRow('Size [grid]', self._dbl(getattr(f, 'size_grid', 0.9), lambda v: self.set_font_attr(f, 'size_grid', v, refresh_attrs), .1, 5, .1))
        b = QPushButton('Font Color RGB')
        b.clicked.connect(lambda: self.color_font(f, refresh_attrs))
        self.form.addRow('Font color', b)

    def transform_props(self, m):
        self.form.addRow('Rotation [deg]', self.rotation_combo(getattr(m, 'rotation', 0), lambda v: self.set_and_refresh(m, 'rotation', float(v))))

    def rotation_combo(self, value, fn):
        combo = QComboBox()
        vals = ['0', '90', '180', '270']
        combo.addItems(vals)
        combo.setCurrentText(str(int(round(float(value) / 90.0) * 90) % 360))
        combo.currentTextChanged.connect(fn)
        return combo

    # ------------------------------------------------------------------ Canvas selection / body edit / bulk pins
    def set_body_edit_mode(self, enabled: bool):
        self.body_edit = bool(enabled)
        if hasattr(self, 'body_edit_button'):
            self.body_edit_button.blockSignals(True)
            self.body_edit_button.setChecked(self.body_edit)
            self.body_edit_button.setText('Body Edit: ON' if self.body_edit else 'Body Edit: OFF')
            self.body_edit_button.blockSignals(False)
        if self.body_edit:
            self.set_tool(DrawTool.SELECT.value)
            self.statusBar().showMessage('Body Edit Mode: newly drawn graphics are attached to the body.', 6000)

    def apply_canvas_select_filter(self, *_):
        if not hasattr(self, 'select_filter_combo'):
            return
        filt = self.select_filter_combo.currentText()
        allowed = {
            'All': {'BODY', 'PIN', 'GRAPHIC', 'TEXT', 'ORIGIN'},
            'Body': {'BODY', 'ORIGIN'},
            'Pins': {'PIN'},
            'Graphics': {'GRAPHIC'},
            'Text': {'TEXT'},
        }.get(filt, {'BODY', 'PIN', 'GRAPHIC', 'TEXT', 'ORIGIN'})
        for it in self.scene.items():
            kind = it.data(0)
            if kind in ('ATTR_REF_DES', 'ATTR_BODY'):
                it.setFlag(QGraphicsItem.ItemIsSelectable, False)
                it.setFlag(QGraphicsItem.ItemIsMovable, False)
                continue
            selectable = kind in allowed
            it.setFlag(QGraphicsItem.ItemIsSelectable, selectable)
            if not selectable and it.isSelected():
                it.setSelected(False)
        self.scene.update()

    def attach_selected_graphics_to_body(self):
        changed = False
        for it in self.scene.selectedItems():
            if it.data(0) == 'GRAPHIC':
                it.model.body_attached = True
                changed = True
        if changed:
            self.current_unit.body.body_shape = 'custom'
            self.rebuild_tree()
            self.schedule_scene_refresh()
            self.statusBar().showMessage('Selected graphics attached to body.', 5000)

    def iter_symbol_pins(self, symbol=None):
        symbol = symbol or self.symbol
        for u in symbol.units:
            for p in u.pins:
                yield u, p

    def apply_pin_bulk_to_selected(self, side: str, pin_type: str, function: str, length: float):
        selected = [it for it in self.scene.selectedItems() if it.data(0) == 'PIN']
        for it in selected:
            p = it.model
            p.side = side
            p.pin_type = pin_type
            if function.strip():
                p.function = function.strip()
            p.length = max(1.0, round(float(length)))
        self.dock_pins_to_body(self.current_unit)
        self.validate_pins(silent=True)
        self.schedule_scene_refresh()

    def apply_pin_model_to_all(self, ref_pin: PinModel):
        for u, p in self.iter_symbol_pins(self.symbol):
            if p is ref_pin:
                continue
            p.function = ref_pin.function
            p.pin_type = ref_pin.pin_type
            p.side = ref_pin.side
            p.length = ref_pin.length
            p.rotation = (round(float(getattr(ref_pin, 'rotation', 0.0)) / 90.0) * 90) % 360
            p.inverted = ref_pin.inverted
            p.line_style = ref_pin.line_style
            p.line_width = ref_pin.line_width
            p.color = ref_pin.color
            p.visible_number = ref_pin.visible_number
            p.visible_name = ref_pin.visible_name
            p.visible_function = ref_pin.visible_function
            p.number_font = copy.deepcopy(ref_pin.number_font)
            p.label_font = copy.deepcopy(ref_pin.label_font)
            self.dock_pins_to_body(u)
        self.validate_pins(silent=True)
        self.schedule_scene_refresh()

    def apply_first_selected_pin_to_all(self):
        pins = [it for it in self.scene.selectedItems() if it.data(0) == 'PIN']
        if not pins:
            return
        self.apply_pin_model_to_all(pins[0].model)

    def update_refdes_prefix(self, body: SymbolBodyModel, prefix: str):
        prefix = str(prefix or 'U')
        cur = str(body.attributes.get('RefDes', '') or '')
        m = re.match(r'^([A-Za-z]+)(.*)$', cur)
        suffix = m.group(2) if m else '?'
        if suffix == '':
            suffix = '?'
        body.attributes['RefDes'] = f'{prefix}{suffix}'

    # ------------------------------------------------------------------ Model updates
    def set_font_attr(self, f, a, v, refresh_attrs=False):
        if a == 'size_pt':
            v = float(v)
            f.size_pt = v
            f.size_grid = round(v / 7.2, 3)
        elif a == 'size_grid':
            v = float(v)
            f.size_grid = v
            f.size_pt = self.grid_font_pt(v)
        else:
            setattr(f, a, v)
        if refresh_attrs:
            # Body-owned attribute/RefDes texts are generated items, so they
            # must be regenerated after font changes instead of only repainting.
            self.update_attribute_items_for_unit()
        self.schedule_scene_refresh()

    def color_font(self, f, refresh_attrs=False):
        c = QColorDialog.getColor(QColor(*f.color), self)
        if c.isValid():
            f.color = (c.red(), c.green(), c.blue())
            if refresh_attrs:
                self.update_attribute_items_for_unit()
            self.schedule_scene_refresh()

    def set_and_refresh(self, m, a, v):
        setattr(m, a, v)
        self.schedule_scene_refresh()

    def set_style(self, m, a, v):
        setattr(m.style, a, v)
        self.schedule_scene_refresh()

    def set_body_dim(self, item, a, v):
        st = {
            'x': float(item.model.x), 'y': float(item.model.y),
            'w': float(item.model.width), 'h': float(item.model.height),
            'pins': [(p, float(p.x), float(p.y), float(p.length)) for p in self.current_unit.pins],
            'texts': [(t, float(t.x), float(t.y)) for t in self.current_unit.texts],
            'graphics': [(gr, float(gr.x), float(gr.y), float(gr.w), float(gr.h)) for gr in self.current_unit.graphics],
        }
        setattr(item.model, a, round(float(v) * 2) / 2)
        self.scale_current_unit_children_from_body_resize(st, item.model)
        self.enforce_symbol_size_limit()
        self.schedule_scene_refresh()

    def set_attr_vis(self, m, k, v):
        m.visible_attributes[k] = v
        self.sync_font_points_to_grid()
        self.update_attribute_items_for_unit()
        self.rebuild_tree()
        self.scene.update()

    def set_attr_val(self, m, k, v):
        m.attributes[k] = v
        # Attribute text is generated from the body attribute model. Keep font
        # points derived from the active grid before regenerating these locked
        # text items so RefDes changes are visible immediately and at the
        # correct size.
        self.sync_font_points_to_grid()
        self.update_attribute_items_for_unit()
        self.rebuild_tree()
        self.scene.update()

    def set_pin_attr(self, m, a, v):
        if a == 'rotation':
            try:
                v = (round(float(v) / 90.0) * 90) % 360
            except (TypeError, ValueError):
                v = 0.0
        setattr(m, a, v)
        if a == 'name':
            self.ensure_unique_pin_names(self.symbol)
        if a == 'side':
            self.dock_pins_to_body(self.current_unit)
        dup = duplicate_pin_numbers(self.symbol)
        if dup:
            self.statusBar().showMessage('Duplicate pin number(s): ' + ', '.join(dup), 8000)
        self.schedule_scene_refresh()

    def set_pin_length(self, m, v):
        # Pin length is always an integer grid multiple.
        m.length = max(1.0, round(float(v)))
        m.scale_x = 1.0
        m.scale_y = 1.0
        self.schedule_scene_refresh()

    def set_text_attr(self, item, a, v):
        if a == 'font_size_pt':
            v = float(v)
            item.model.font_size_pt = v
            item.model.font_size_grid = round(v / max(1.0, float(self.grid_px) * 1.28), 3)
            from symbol_wizard.graphics.items import qfont_for
            item.setFont(qfont_for(item.model.font_family, item.model.font_size_pt))
        elif a == 'font_size_grid':
            v = float(v)
            item.model.font_size_grid = v
            item.model.font_size_pt = self.grid_font_pt(v)
            from symbol_wizard.graphics.items import qfont_for
            item.setFont(qfont_for(item.model.font_family, item.model.font_size_pt))
        else:
            setattr(item.model, a, v)
            if a == 'text':
                item.setPlainText(v)
            if a == 'font_family':
                from symbol_wizard.graphics.items import qfont_for
                item.setFont(qfont_for(item.model.font_family, getattr(item.model, 'font_size_pt', 7.2)))
        self.schedule_scene_refresh()

    def color_model(self, m, attr='color'):
        c = QColorDialog.getColor(QColor(*getattr(m, attr)), self)
        if c.isValid():
            setattr(m, attr, (c.red(), c.green(), c.blue()))
            self.schedule_scene_refresh()

    def live_refresh(self):
        self.rebuild_tree()
        self.rebuild_pin_table()

    def update_current_unit_canvas_positions(self):
        """Update existing QGraphicsItems from their models without rebuilding the scene."""
        g = self.grid_px
        for item in self.scene.items():
            model = getattr(item, 'model', None)
            if model is None:
                continue
            kind = item.data(0)
            if kind == 'BODY':
                item.setPos(model.x * g, -model.y * g)
                item.setRect(0, 0, model.width * g, model.height * g)
                item.setPen(item.pen().__class__(QColor(*model.color), max(1, model.line_width * g)))
            elif kind == 'PIN':
                model.scale_x = 1.0
                model.scale_y = 1.0
                try:
                    model.rotation = (round(float(getattr(model, 'rotation', 0.0) or 0.0) / 90.0) * 90) % 360
                except (TypeError, ValueError):
                    model.rotation = 0.0
                item.setRotation(float(model.rotation))
                item.setTransform(item.transform().__class__())
                item.setPos(model.x * g, -model.y * g)
            elif kind == 'TEXT':
                item.setPos(model.x * g, -model.y * g)
                try:
                    from symbol_wizard.graphics.items import qfont_for
                    item.setFont(qfont_for(model.font_family, getattr(model, 'font_size_pt', 7.2)))
                except Exception:
                    pass
            elif kind == 'GRAPHIC':
                item.setPos(model.x * g, -model.y * g)
            item.update()
        self.scene.update()

    def update_attribute_items_for_unit(self):
        """Regenerate body-owned attribute text only; keeps normal objects selected and avoids stale text remnants."""
        selected_ids = self._capture_selection_ids()
        for item in list(self.scene.items()):
            if item.data(0) in ('ATTR_REF_DES', 'ATTR_BODY'):
                self.scene.removeItem(item)
        self.add_attribute_text_items(self.current_unit)
        for item in self.scene.items():
            model = getattr(item, 'model', None)
            if model is not None and id(model) in selected_ids:
                item.setSelected(True)
        self.scene.update()

    def scale_current_unit_children_from_body_resize(self, start_state: dict, body: SymbolBodyModel):
        """Keep pins/text/graphics grouped with body while resizing.

        Side handles modify one dimension only. Corner handles modify both dimensions.
        Positions are snapped because the body resize itself is snapped to the grid.
        """
        old_x = float(start_state.get('x', body.x)); old_y = float(start_state.get('y', body.y))
        old_w = max(float(start_state.get('w', body.width)), 1e-9)
        old_h = max(float(start_state.get('h', body.height)), 1e-9)
        sx = float(body.width) / old_w
        sy = float(body.height) / old_h

        def sg(v):
            return round(v * 2) / 2

        for p, px, py, plen in start_state.get('pins', []):
            # Pins stay docked to the selected side; Y follows body height scaling.
            p.x = body.x if p.side == PinSide.LEFT.value else body.x + body.width
            p.y = sg(body.y + (py - old_y) * sy)
            p.length = max(.5, sg(plen * max(abs(sx), .1)))
        for t, tx, ty in start_state.get('texts', []):
            t.x = sg(body.x + (tx - old_x) * sx)
            t.y = sg(body.y + (ty - old_y) * sy)
        for gr, gx, gy, gw, gh in start_state.get('graphics', []):
            gr.x = sg(body.x + (gx - old_x) * sx)
            gr.y = sg(body.y + (gy - old_y) * sy)
            gr.w = sg(gw * sx)
            gr.h = sg(gh * sy)

    def schedule_scene_refresh(self, visual_only=False):
        # Keep selected canvas objects selected during deferred refreshes.
        self._selection_restore_ids = self._capture_selection_ids()
        self._refresh_visual_only = bool(visual_only)
        self.refresh_timer.start(35 if visual_only else 80)

    def _scheduled_refresh(self):
        self.enforce_symbol_size_limit(silent=True)
        # Full rebuild is needed after property/model changes. Selection is restored by model id.
        self.rebuild_scene()
        self.rebuild_tree()
        self.rebuild_pin_table()
        self._refresh_visual_only = False
        self.body_edit = False
        self.symbol_type_config = load_symbol_type_config()

    # ------------------------------------------------------------------ Grouping / constraints
    def move_current_unit_group(self, dx: float, dy: float, source_body=None):
        u = self.current_unit
        # Body is the anchor. When it moves, all user-owned objects in this unit follow.
        for p in u.pins:
            p.x += dx
            p.y += dy
        for t in u.texts:
            t.x += dx
            t.y += dy
        for g in u.graphics:
            g.x += dx
            g.y += dy

    def dock_pins_to_body(self, u: SymbolUnitModel):
        b = u.body
        for p in u.pins:
            p.x = b.x if p.side == PinSide.LEFT.value else b.x + b.width

    def symbol_bounds_grid(self, symbol: SymbolModel | None = None):
        symbol = symbol or self.symbol
        xs, ys = [], []
        for u in symbol.units:
            b = u.body
            xs.extend([b.x, b.x + b.width])
            ys.extend([b.y, b.y - b.height])
            for p in u.pins:
                xs.extend([p.x - p.length, p.x + p.length])
                ys.append(p.y)
            for t in u.texts:
                xs.append(t.x); ys.append(t.y)
            for g in u.graphics:
                xs.extend([g.x, g.x + g.w]); ys.extend([g.y, g.y - g.h])
        if not xs:
            return 0, 0, 1, 1
        return min(xs), min(ys), max(xs), max(ys)

    def enforce_symbol_size_limit(self, silent=False):
        fmt = getattr(self.symbol, 'sheet_format', SheetFormat.A3.value)
        w_in, h_in = SHEET_INCHES.get(fmt, SHEET_INCHES['A3'])
        max_w_grid = (w_in * .40) / self.symbol.grid_inch
        max_h_grid = (h_in * .80) / self.symbol.grid_inch
        x0, y0, x1, y1 = self.symbol_bounds_grid()
        cur_w, cur_h = abs(x1 - x0), abs(y1 - y0)
        if cur_w <= max_w_grid and cur_h <= max_h_grid:
            return True
        scale = min(max_w_grid / max(cur_w, .01), max_h_grid / max(cur_h, .01))
        if scale <= 0 or scale >= 1:
            return True
        for u in self.symbol.units:
            u.body.width = max(1, u.body.width * scale)
            u.body.height = max(1, u.body.height * scale)
            for p in u.pins:
                p.y = u.body.y + (p.y - u.body.y) * scale
                p.length = max(.5, p.length * scale)
            for t in u.texts:
                t.x = u.body.x + (t.x - u.body.x) * scale
                t.y = u.body.y + (t.y - u.body.y) * scale
            for g in u.graphics:
                g.x = u.body.x + (g.x - u.body.x) * scale
                g.y = u.body.y + (g.y - u.body.y) * scale
                g.w *= scale; g.h *= scale
            self.dock_pins_to_body(u)
        if not silent:
            self.statusBar().showMessage(f'Symbol scaled to fit {fmt} 40% width / 80% height limit.', 8000)
        return False

    # ------------------------------------------------------------------ Actions
    def set_tool(self, t):
        self.draw_tool = t
        for k, a in self.tool_buttons.items():
            a.setChecked(k == t)
        self.view.setDragMode(QGraphicsView.RubberBandDrag if t == DrawTool.SELECT.value else QGraphicsView.NoDrag)

    def pick_default_color(self):
        c = QColorDialog.getColor(QColor(*self.default_color), self)
        if c.isValid():
            self.default_color = (c.red(), c.green(), c.blue())
            self.apply_line_defaults()

    def update_style_controls_from_target(self):
        target = self.style_target_combo.currentText() if hasattr(self, 'style_target_combo') else 'Selection'
        model = None
        if target == 'Body':
            model = self.current_unit.body
            style = getattr(model, 'line_style', None); width = getattr(model, 'line_width', None)
        elif target == 'Pins' and self.current_unit.pins:
            model = self.current_unit.pins[0]
            style = getattr(model, 'line_style', None); width = getattr(model, 'line_width', None)
        elif target == 'Graphics' and self.current_unit.graphics:
            model = self.current_unit.graphics[0].style
            style = getattr(model, 'line_style', None); width = getattr(model, 'line_width', None)
        elif self.scene.selectedItems():
            it = self.scene.selectedItems()[0]
            if it.data(0) == 'GRAPHIC':
                model = it.model.style; style = model.line_style; width = model.line_width
            else:
                model = it.model; style = getattr(model, 'line_style', None); width = getattr(model, 'line_width', None)
        else:
            return
        self.line_style.blockSignals(True); self.line_width.blockSignals(True)
        if style:
            self.line_style.setCurrentText(style)
        if width is not None:
            self.line_width.setValue(float(width))
        self.line_style.blockSignals(False); self.line_width.blockSignals(False)

    def apply_line_defaults(self):
        style = self.line_style.currentText(); width = self.line_width.value(); color = self.default_color
        target = self.style_target_combo.currentText() if hasattr(self, 'style_target_combo') else 'Selection'
        if target == 'Selection':
            targets = self.scene.selectedItems()
            for it in targets:
                if it.data(0) == 'PIN':
                    it.model.line_style = style; it.model.line_width = width; it.model.color = color
                elif it.data(0) == 'GRAPHIC':
                    it.model.style.line_style = style; it.model.style.line_width = width; it.model.style.stroke = color
                elif it.data(0) == 'BODY':
                    it.model.line_style = style; it.model.line_width = width; it.model.color = color
        elif target == 'Body':
            for u in self.symbol.units:
                u.body.line_style = style; u.body.line_width = width; u.body.color = color
        elif target == 'Pins':
            for u, p in self.iter_symbol_pins(self.symbol):
                p.line_style = style; p.line_width = width; p.color = color
        elif target == 'Graphics':
            for u in self.symbol.units:
                for gr in u.graphics:
                    gr.style.line_style = style; gr.style.line_width = width; gr.style.stroke = color
        self.schedule_scene_refresh()

    def add_pin(self, side, x=None, y=None):
        p = create_auto_pin(self.symbol, self.current_unit, side)
        if x is not None: p.x = x
        if y is not None: p.y = y
        # Keep the docking side strict; y may be edited freely.
        p.x = self.current_unit.body.x if side == PinSide.LEFT.value else self.current_unit.body.x + self.current_unit.body.width
        self.current_unit.pins.append(p)
        self.validate_pins(silent=True)
        self.select_model_after_rebuild(p)
        self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()

    def add_graphic(self, tool, x, y):
        shape = {DrawTool.LINE.value: 'line', DrawTool.RECT.value: 'rect', DrawTool.ELLIPSE.value: 'ellipse'}[tool]
        if shape == 'line':
            # Linien werden initial gerade eingefügt: horizontal, auf Raster, Länge 2 Grid.
            model = GraphicModel(shape=shape, x=x, y=y, w=2.0, h=0.0, style=StyleModel(stroke=self.default_color, line_width=self.line_width.value(), line_style=self.line_style.currentText()))
        else:
            model = GraphicModel(shape=shape, x=x, y=y, style=StyleModel(stroke=self.default_color, line_width=self.line_width.value(), line_style=self.line_style.currentText()))
        if getattr(self, 'body_edit', False):
            model.body_attached = True
            self.current_unit.body.body_shape = 'custom'
        self.current_unit.graphics.append(model)
        self.select_model_after_rebuild(model)
        self.rebuild_scene(); self.rebuild_tree()

    def rotate_selected(self, deg):
        for it in self.scene.selectedItems():
            if hasattr(it, 'rotate_by'):
                it.rotate_by(deg)
        self.schedule_scene_refresh(visual_only=True)

    def scale_selected(self, factor):
        for it in self.scene.selectedItems():
            if hasattr(it, 'scale_selected'):
                it.scale_selected(factor)
        self.enforce_symbol_size_limit(silent=True)
        self.schedule_scene_refresh(visual_only=True)

    def mirror_selected(self, axis: str):
        # Simple grid-aware mirror around the current body/origin.
        body = self.current_unit.body
        cx = body.x + body.width / 2
        cy = body.y + body.height / 2
        for it in self.scene.selectedItems():
            m = getattr(it, 'model', None)
            if m is None or not hasattr(m, 'x') or not hasattr(m, 'y'):
                continue
            if axis == 'x':
                m.x = round(cx - (m.x - cx))
            else:
                m.y = round(cy - (m.y - cy))
            if it.data(0) == 'PIN':
                m.side = PinSide.RIGHT.value if m.side == PinSide.LEFT.value else PinSide.LEFT.value
        self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()

    def copy_selected(self):
        self.clipboard = []
        for it in self.scene.selectedItems():
            if it.data(0) in ('PIN', 'TEXT', 'GRAPHIC', 'BODY'):
                self.clipboard.append((it.data(0), copy.deepcopy(it.model)))
        if self.clipboard:
            self.statusBar().showMessage(f'Copied {len(self.clipboard)} object(s).', 2500)

    def paste_selected(self):
        if not self.clipboard:
            return
        existing_pins = [p.number for u in self.symbol.units for p in u.pins]
        pasted_models = []
        for kind, src in self.clipboard:
            m = copy.deepcopy(src)
            if hasattr(m, 'x'):
                m.x += 1
            if hasattr(m, 'y'):
                m.y -= 1
            if kind == 'PIN':
                # Doppelte Pinnummern bleiben verboten; Kopien bekommen automatisch freie Nummern.
                m.number = next_pin_number(existing_pins)
                existing_pins.append(m.number)
                self.current_unit.pins.append(m)
                self.ensure_unique_pin_names(self.symbol)
                pasted_models.append(m)
            elif kind == 'TEXT':
                self.current_unit.texts.append(m)
                pasted_models.append(m)
            elif kind == 'GRAPHIC':
                self.current_unit.graphics.append(m)
                pasted_models.append(m)
            elif kind == 'BODY':
                self.current_unit.body = m
                pasted_models.append(m)
        self.dock_pins_to_body(self.current_unit)
        self._selection_restore_ids = {id(m) for m in pasted_models}
        self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()

    def delete_selected(self):
        sel = [i for i in self.scene.selectedItems() if i.data(0) in ('PIN', 'TEXT', 'GRAPHIC')]
        if not sel: return
        u = self.current_unit
        for it in sel:
            if it.data(0) == 'PIN': u.pins = [p for p in u.pins if p is not it.model]
            elif it.data(0) == 'TEXT': u.texts = [t for t in u.texts if t is not it.model]
            elif it.data(0) == 'GRAPHIC': u.graphics = [g for g in u.graphics if g is not it.model]
        self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()

    def ensure_unique_pin_names(self, symbol: SymbolModel):
        used = set()
        for u in symbol.units:
            for p in u.pins:
                base = (p.name or 'PIN').strip() or 'PIN'
                name = base
                i = 2
                while name in used:
                    name = f'{base}_{i}'
                    i += 1
                p.name = name
                used.add(name)

    def validate_pins(self, silent=False):
        dup = duplicate_pin_numbers(self.symbol)
        if dup and not silent:
            QMessageBox.warning(self, 'Pin validation', 'Doppelte Pinnummern im Symbol sind verboten: ' + ', '.join(dup))
        elif not dup and not silent:
            QMessageBox.information(self, 'Pin validation', 'Keine doppelten Pinnummern gefunden.')
        return not dup

    def zoom_to_fit_symbol(self):
        items = [i for i in self.scene.items() if i.data(0) not in ('ATTR_REF_DES', 'ATTR_BODY')]
        if not items:
            return
        rect = QRectF()
        for i in items:
            rect = rect.united(i.sceneBoundingRect()) if not rect.isNull() else i.sceneBoundingRect()
        self.view.fitInView(rect.adjusted(-80, -80, 80, 80), Qt.KeepAspectRatio)

    def zoom_to_fit_sheet(self):
        rect = sheet_rect_for(getattr(self.symbol, 'sheet_format', 'A3'))
        self.view.fitInView(rect.adjusted(-100, -100, 100, 100), Qt.KeepAspectRatio)

    def selected_pin_items(self):
        return [it for it in self.scene.selectedItems() if it.data(0) == 'PIN']

    def set_selected_pins_side(self, side: str):
        pins = self.selected_pin_items()
        if not pins:
            self.statusBar().showMessage('No pins selected.', 2500)
            return
        body = self.current_unit.body
        for it in pins:
            it.model.side = side
            it.model.x = body.x if side == PinSide.LEFT.value else body.x + body.width
        self._selection_restore_ids = {id(it.model) for it in pins}
        self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()

    def distribute_selected_pins_vertical(self):
        pins = self.selected_pin_items()
        if len(pins) < 2:
            self.statusBar().showMessage('Select at least two pins to distribute.', 3000)
            return
        models = [it.model for it in pins]
        # Use the upper-most selected pin as anchor and then apply type-specific spacing.
        models.sort(key=lambda p: p.y, reverse=True)
        y = round(models[0].y * 2) / 2
        for idx, pin in enumerate(models):
            pin.y = y
            if idx < len(models) - 1:
                spacing = self.pin_spacing_grid(models[idx + 1])
                y -= spacing
        self.dock_pins_to_body(self.current_unit)
        self._selection_restore_ids = {id(p) for p in models}
        self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()

    def pin_spacing_grid(self, pin: PinModel) -> float:
        return 1.0 if pin.pin_type in (PinType.POWER.value, PinType.GROUND.value) else 2.0

    def select_model_in_scene(self, model):
        self.scene.clearSelection()
        self.current_unit_index = max(0, min(self.current_unit_index, len(self.symbol.units)-1))
        for it in self.scene.items():
            if getattr(it, 'model', None) is model:
                it.setSelected(True)
                self.view.centerOn(it)
                break
        self.refresh_properties()

    # ------------------------------------------------------------------ Navigation / tables
    def pin_table_combo_changed(self, meta, col, value):
        if self.suspend:
            return
        si, ui, pi = meta
        if si >= len(self.library.symbols):
            return
        sym = self.library.symbols[si]
        if ui >= len(sym.units) or pi >= len(sym.units[ui].pins):
            return
        p = sym.units[ui].pins[pi]
        if col == 3:
            allowed = [x.value for x in PinType]
            if value in allowed:
                p.pin_type = value
        elif col == 4:
            allowed = [x.value for x in PinSide]
            if value in allowed:
                p.side = value
                # Keep pin docked on selected side.
                body = sym.units[ui].body
                p.x = body.x if p.side == PinSide.LEFT.value else body.x + body.width
        elif col == 5:
            p.inverted = str(value).lower() in ('1', 'true', 'yes', 'ja', 'x')
        self.validate_pins(silent=True)
        if si == self.library.current_symbol_index:
            self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()

    def pin_table_changed(self, r, c):
        table = self.sender()
        if self.suspend or not isinstance(table, QTableWidget):
            return
        if c >= 3:
            return
        it = table.item(r, c)
        if not it:
            return
        si, ui, pi, col = it.data(Qt.UserRole)
        if si >= len(self.library.symbols):
            return
        sym = self.library.symbols[si]
        if ui >= len(sym.units) or pi >= len(sym.units[ui].pins):
            return
        p = sym.units[ui].pins[pi]
        val = it.text().strip()
        if col == 0:
            p.number = val
        elif col == 1:
            p.name = val
            self.ensure_unique_pin_names(sym)
        elif col == 2:
            p.function = val
        elif col == 3:
            p.pin_type = val if val in [x.value for x in PinType] else p.pin_type
        elif col == 4:
            p.side = val if val in [x.value for x in PinSide] else p.side
        elif col == 5:
            p.inverted = str(val).lower() in ('1', 'true', 'yes', 'ja', 'x')
        self.validate_pins(silent=True)
        if si == self.library.current_symbol_index:
            self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()

    def pin_table_clicked(self, r, c):
        table = self.sender()
        if not isinstance(table, QTableWidget):
            return
        it = table.item(r, 0)
        if not it:
            return
        si, ui, pi, _ = it.data(Qt.UserRole)
        self.library.current_symbol_index = si
        self.current_unit_index = ui
        self.rebuild_symbol_tabs(); self.rebuild_canvas_tabs(); self.rebuild_unit_tabs(); self.rebuild_scene(); self.rebuild_tree(); self.update_name_editors()
        self.select_model_in_scene(self.symbol.units[ui].pins[pi])

    def symbol_tab_context_menu(self, kind: str, pos):
        tabs = self.single_tabs if kind == SymbolKind.SINGLE.value else self.split_tabs
        tab_index = tabs.tabBar().tabAt(pos)
        indices = self._symbol_indices(kind)
        if tab_index < 0 or tab_index >= len(indices):
            return
        symbol_index = indices[tab_index]
        menu = QMenu(self)
        act_delete = menu.addAction('Delete Symbol')
        act = menu.exec(tabs.mapToGlobal(pos))
        if act == act_delete:
            self.delete_symbol_at(symbol_index)

    def unit_tab_context_menu(self, pos):
        tab_index = self.unit_tabs.tabBar().tabAt(pos)
        if tab_index < 0:
            return
        menu = QMenu(self)
        act_delete = menu.addAction('Delete Unit / Split Part')
        act = menu.exec(self.unit_tabs.mapToGlobal(pos))
        if act == act_delete:
            self.delete_unit_at(tab_index)

    def tree_context_menu(self, tree: QTreeWidget, pos):
        item = tree.itemAt(pos)
        if item is None:
            return
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        menu = QMenu(self)
        action = None
        if data[0] == 'symbol':
            action = menu.addAction('Delete Symbol')
        elif data[0] in ('single_unit', 'split_unit'):
            action = menu.addAction('Delete Unit / Split Part')
        elif data[0] in ('single_pin', 'split_pin'):
            action = menu.addAction('Delete Pin')
        elif data[0] in ('text', 'graphic'):
            action = menu.addAction('Delete Object')
        if action is None:
            return
        chosen = menu.exec(tree.mapToGlobal(pos))
        if chosen != action:
            return
        kind = data[0]
        if kind == 'symbol':
            self.delete_symbol_at(data[1])
        elif kind in ('single_unit', 'split_unit'):
            self.library.current_symbol_index = data[1]
            self.delete_unit_at(data[2])
        elif kind in ('single_pin', 'split_pin'):
            self.library.current_symbol_index = data[1]
            self.delete_pin_at(data[1], data[2], data[3])
        elif kind == 'text':
            ui, ti = data[1], data[2]
            if ui < len(self.symbol.units) and ti < len(self.symbol.units[ui].texts):
                self.symbol.units[ui].texts.pop(ti)
            self.rebuild_scene(); self.rebuild_tree()
        elif kind == 'graphic':
            ui, gi = data[1], data[2]
            if ui < len(self.symbol.units) and gi < len(self.symbol.units[ui].graphics):
                self.symbol.units[ui].graphics.pop(gi)
            self.rebuild_scene(); self.rebuild_tree()

    def delete_symbol_at(self, symbol_index: int):
        if len(self.library.symbols) <= 1:
            QMessageBox.information(self, 'Delete Symbol', 'Das letzte Symbol kann nicht gelöscht werden.')
            return
        sym = self.library.symbols[symbol_index]
        if QMessageBox.question(self, 'Delete Symbol', f'Symbol "{sym.name}" wirklich löschen?') != QMessageBox.Yes:
            return
        self.library.symbols.pop(symbol_index)
        self.library.current_symbol_index = max(0, min(self.library.current_symbol_index, len(self.library.symbols) - 1))
        self.current_unit_index = 0
        self.rebuild_all()

    def delete_unit_at(self, unit_index: int):
        sym = self.symbol
        if len(sym.units) <= 1:
            QMessageBox.information(self, 'Delete Unit', 'Die letzte Unit / der letzte Split Part kann nicht gelöscht werden.')
            return
        if unit_index < 0 or unit_index >= len(sym.units):
            return
        name = sym.units[unit_index].name
        if QMessageBox.question(self, 'Delete Unit', f'Unit / Split Part "{name}" wirklich löschen?') != QMessageBox.Yes:
            return
        sym.units.pop(unit_index)
        self.current_unit_index = max(0, min(self.current_unit_index, len(sym.units) - 1))
        self.rebuild_all()

    def delete_pin_at(self, si: int, ui: int, pi: int):
        if si >= len(self.library.symbols):
            return
        sym = self.library.symbols[si]
        if ui >= len(sym.units) or pi >= len(sym.units[ui].pins):
            return
        pin = sym.units[ui].pins[pi]
        if QMessageBox.question(self, 'Delete Pin', f'Pin {pin.number} / {pin.name} wirklich löschen?') != QMessageBox.Yes:
            return
        sym.units[ui].pins.pop(pi)
        self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()

    def tree_clicked(self, item, col):
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        kind = data[0]
        if kind == 'symbol':
            self.library.current_symbol_index = data[1]
            self.current_unit_index = 0
            self.rebuild_all()
            return
        if kind in ('split_unit', 'single_unit'):
            _, si, ui = data
            self.library.current_symbol_index = si
            self.current_unit_index = ui
            self.rebuild_all()
            return
        if kind in ('single_body',):
            _, si, ui = data
            self.library.current_symbol_index = si
            self.current_unit_index = ui
            self.rebuild_all()
            self.select_model_in_scene(self.symbol.units[ui].body)
            return
        if kind in ('split_pin', 'single_pin'):
            _, si, ui, pi = data
            self.library.current_symbol_index = si
            self.current_unit_index = ui
            self.rebuild_all()
            self.select_model_in_scene(self.symbol.units[ui].pins[pi])
            return
        if kind in ('single_text',):
            _, si, ui, ti = data
            self.library.current_symbol_index = si
            self.current_unit_index = ui
            self.rebuild_all()
            self.select_model_in_scene(self.symbol.units[ui].texts[ti])
            return
        if kind in ('single_graphic',):
            _, si, ui, gi = data
            self.library.current_symbol_index = si
            self.current_unit_index = ui
            self.rebuild_all()
            self.select_model_in_scene(self.symbol.units[ui].graphics[gi])
            return
        _, ui, idx = data
        self.current_unit_index = ui
        self.rebuild_unit_tabs()
        self.rebuild_scene()
        u = self.current_unit
        if kind == 'body':
            self.select_model_in_scene(u.body)
        elif kind == 'pin' and idx is not None:
            self.select_model_in_scene(u.pins[idx])
        elif kind == 'text' and idx is not None:
            self.select_model_in_scene(u.texts[idx])
        elif kind == 'graphic' and idx is not None:
            self.select_model_in_scene(u.graphics[idx])

    def left_workspace_changed(self, idx):
        # 0 = single, 1 = split. Pins are part of the respective hierarchy trees.
        if idx == 0 and self.symbol.kind != SymbolKind.SINGLE.value and self._symbol_indices(SymbolKind.SINGLE.value):
            self.change_symbol_from_tab(SymbolKind.SINGLE.value, 0)
        elif idx == 1 and self.symbol.kind != SymbolKind.SPLIT.value and self._symbol_indices(SymbolKind.SPLIT.value):
            self.change_symbol_from_tab(SymbolKind.SPLIT.value, self.split_tabs.currentIndex())

    def change_symbol_from_canvas_tab(self, tab_index: int):
        if tab_index < 0 or tab_index >= len(self.library.symbols):
            return
        if tab_index == self.library.current_symbol_index:
            return
        self.library.current_symbol_index = tab_index
        self.current_unit_index = 0
        self.rebuild_all()

    def change_symbol_from_tab(self, kind: str, tab_index: int):
        if tab_index < 0: return
        indices = self._symbol_indices(kind)
        if tab_index >= len(indices): return
        self.library.current_symbol_index = indices[tab_index]
        self.current_unit_index = 0
        self.rebuild_canvas_tabs(); self.rebuild_unit_tabs(); self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()
        self.update_name_editors()
        self.grid_spin.blockSignals(True); self.grid_spin.setValue(self.symbol.grid_inch); self.grid_spin.blockSignals(False)
        self.format_combo.blockSignals(True); self.format_combo.setCurrentText(getattr(self.symbol, 'sheet_format', SheetFormat.A3.value)); self.format_combo.blockSignals(False)

    def change_unit(self, i):
        if i < 0: return
        self.current_unit_index = i
        self.rebuild_canvas_tabs(); self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table(); self.update_name_editors()

    def new_single_symbol(self):
        self.library.add_symbol('Symbol', SymbolKind.SINGLE.value)
        self.current_unit_index = 0
        self.apply_symbol_template(getattr(self.symbol, 'symbol_type', 'IC'), getattr(self.symbol, 'symbol_subtype', 'Generic IC'))
        self.rebuild_all()

    def new_split_symbol(self):
        s = self.library.add_symbol('Split Symbol', SymbolKind.SPLIT.value)
        s.units = [SymbolUnitModel(name=f'{s.name}_1'), SymbolUnitModel(name=f'{s.name}_2')]
        self.current_unit_index = 0
        self.apply_symbol_template(getattr(self.symbol, 'symbol_type', 'IC'), getattr(self.symbol, 'symbol_subtype', 'Generic IC'))
        self.rebuild_all()

    def add_unit(self):
        if self.symbol.kind != SymbolKind.SPLIT.value:
            QMessageBox.information(self, 'Split Symbol', 'Units können nur in Split Symbols angelegt werden. Bitte lege ein New Split Symbol an.')
            return
        self.symbol.units.append(SymbolUnitModel(name=f'{self.symbol.name}_{len(self.symbol.units) + 1}'))
        self.current_unit_index = len(self.symbol.units) - 1
        self.rebuild_canvas_tabs(); self.rebuild_unit_tabs(); self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()


    def grid_font_pt(self, size_grid=0.9):
        """Return the canvas pixel font size for a grid-relative text height.

        A value of 0.9 means the visible text should be about 90% of one
        grid cell. Qt's pixelSize represents the em box, while the visible
        capital height is smaller, therefore a small compensation factor is
        applied. This keeps RefDes and all body attributes tied directly to
        the active grid instead of to OS point-size/DPI settings.
        """
        try:
            sg = float(size_grid)
        except (TypeError, ValueError):
            sg = 0.9
        return round(float(self.grid_px) * sg * 1.28, 2)

    def sync_font_points_to_grid(self):
        def sync_font(f):
            if not f:
                return
            if not getattr(f, 'size_grid', None):
                f.size_grid = 0.9
            f.size_pt = self.grid_font_pt(f.size_grid)
        for sym in self.library.symbols:
            old_symbol = getattr(self, '_sync_symbol_backup', None)
            for u in sym.units:
                sync_font(u.body.attribute_font)
                sync_font(u.body.refdes_font)
                for p in u.pins:
                    sync_font(p.number_font)
                    sync_font(p.label_font)
                for t in u.texts:
                    if not getattr(t, 'font_size_grid', None):
                        t.font_size_grid = 0.9
                    t.font_size_pt = round(float(sym.grid_inch) * 72.0 * float(t.font_size_grid), 2)

    def set_origin_mode(self, mode: str):
        self.symbol.origin = mode or OriginMode.CENTER.value
        self.place_origin_by_mode(self.symbol.origin)
        self.rebuild_scene()

    def place_origin_by_mode(self, mode: str):
        b = self.current_unit.body
        positions = {
            OriginMode.CENTER.value: (b.x + b.width/2, b.y - b.height/2),
            OriginMode.BOTTOM_LEFT.value: (b.x, b.y - b.height),
            OriginMode.BOTTOM_RIGHT.value: (b.x + b.width, b.y - b.height),
            OriginMode.TOP_LEFT.value: (b.x, b.y),
            OriginMode.TOP_RIGHT.value: (b.x + b.width, b.y),
        }
        if mode in positions:
            self.symbol.origin_x, self.symbol.origin_y = positions[mode]

    def set_grid(self, v):
        self.symbol.grid_inch = v
        self.sync_font_points_to_grid()
        self.rebuild_scene()

    def set_sheet_format(self, fmt):
        self.symbol.sheet_format = fmt
        self.enforce_symbol_size_limit()
        self.scene.update()
        self.schedule_scene_refresh()

    def import_pinmux_csv(self):
        p, _ = QFileDialog.getOpenFileName(self, 'Import PINMUX CSV', '', 'CSV (*.csv);;Text (*.txt);;All Files (*)')
        if not p:
            return
        imported = 0
        errors = []
        existing = [pin.number for unit in self.symbol.units for pin in unit.pins]
        try:
            with open(p, newline='', encoding='utf-8-sig') as f:
                sample = f.read(4096)
                f.seek(0)
                dialect = csv.Sniffer().sniff(sample, delimiters=',;|\t') if sample.strip() else csv.excel
                reader = csv.DictReader(f, dialect=dialect)
                # Accepted headers: Pin Name | Pin Type | Pin Function | Pin Number
                normalized = {h.strip().lower().replace(' ', '_'): h for h in (reader.fieldnames or [])}
                def get(row, key):
                    h = normalized.get(key)
                    return (row.get(h, '') if h else '').strip()
                required = ['pin_name', 'pin_type', 'pin_function', 'pin_number']
                if not all(k in normalized for k in required):
                    QMessageBox.warning(self, 'PINMUX CSV', 'Erwartete Header: Pin Name | Pin Type | Pin Function | Pin Number')
                    return
                for row_no, row in enumerate(reader, start=2):
                    number = get(row, 'pin_number')
                    name = get(row, 'pin_name')
                    pin_type = (get(row, 'pin_type') or PinType.BIDI.value).upper()
                    function = get(row, 'pin_function')
                    if not number:
                        errors.append(f'Zeile {row_no}: Pin Number fehlt')
                        continue
                    if number in existing:
                        errors.append(f'Zeile {row_no}: doppelte Pin Number {number}')
                        continue
                    if pin_type not in [x.value for x in PinType]:
                        pin_type = PinType.BIDI.value
                    side = PinSide.RIGHT.value if pin_type in (PinType.OUT.value, PinType.POWER.value) else PinSide.LEFT.value
                    pin = create_auto_pin(self.symbol, self.current_unit, side)
                    pin.number = number
                    pin.name = name or function or number
                    pin.function = function
                    pin.pin_type = pin_type
                    # If no dedicated function exists, show name; otherwise show function.
                    pin.visible_name = not bool(function)
                    pin.visible_function = bool(function)
                    self.current_unit.pins.append(pin)
                    existing.append(number)
                    imported += 1
        except Exception as exc:
            QMessageBox.critical(self, 'PINMUX CSV', f'Import fehlgeschlagen:\n{exc}')
            return
        self.dock_pins_to_body(self.current_unit)
        self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()
        msg = f'{imported} Pins importiert.'
        if errors:
            msg += '\n\nNicht importiert:\n' + '\n'.join(errors[:20])
        QMessageBox.information(self, 'PINMUX CSV Import', msg)

    # ------------------------------------------------------------------ File IO
    def save_current_symbol(self):
        if not self.validate_pins(): return
        p, _ = QFileDialog.getSaveFileName(self, 'Save Current Symbol JSON', self.symbol.name + '.json', 'JSON (*.json)')
        if p: save_symbol(p, self.symbol)

    def save_all_symbols(self):
        for s in self.library.symbols:
            d = duplicate_pin_numbers(s)
            if d:
                QMessageBox.warning(self, 'Pin validation', f'{s.name}: doppelte Pinnummern: ' + ', '.join(d))
                return
        p, _ = QFileDialog.getSaveFileName(self, 'Save All Symbols JSON', 'symbol_library.json', 'JSON (*.json)')
        if p: save_library(p, self.library)

    def open_library(self):
        p, _ = QFileDialog.getOpenFileName(self, 'Open Library JSON', '', 'JSON (*.json)')
        if p:
            self.library = load_library(p)
            for s in self.library.symbols:
                if not getattr(s, 'kind', None):
                    s.kind = SymbolKind.SPLIT.value if getattr(s, 'is_split', False) else SymbolKind.SINGLE.value
            self.current_unit_index = 0
            self.rebuild_all()

    def import_symbol(self):
        p, _ = QFileDialog.getOpenFileName(self, 'Import Symbol JSON', '', 'JSON (*.json)')
        if not p: return
        s = load_symbol(p)
        s.name = self.library.unique_import_name(s.name)
        self.library.symbols.append(s)
        self.library.current_symbol_index = len(self.library.symbols) - 1
        self.current_unit_index = 0
        self.rebuild_all()
