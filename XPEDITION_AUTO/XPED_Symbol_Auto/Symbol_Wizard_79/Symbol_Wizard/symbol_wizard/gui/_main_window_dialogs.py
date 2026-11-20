from __future__ import annotations
import copy
import csv
import json
import re
import pickle
import math
import tarfile
from pathlib import Path
from dataclasses import asdict
from PySide6.QtCore import Qt, QTimer, QRectF, QEvent, QObject
from PySide6.QtGui import QAction, QColor, QKeySequence, QFontDatabase, QPen, QBrush, QCursor, QShortcut
from PySide6.QtWidgets import *

from symbol_wizard.models.document import *
from symbol_wizard.rules.grid import PX_PER_INCH, duplicate_pin_numbers, next_pin_number
from symbol_wizard.rules.placement import create_auto_pin
from symbol_wizard.graphics.scene import SymbolScene, SHEET_INCHES, sheet_rect_for
from symbol_wizard.graphics.view import SymbolView
from symbol_wizard.graphics.items import BodyItem, PinItem, TextItem, GraphicItem, pen_for, mentor_pin_color
from symbol_wizard.io.json_store import save_library, load_library, save_symbol, load_symbol
from symbol_wizard.io.mentor_sym import import_mentor_sym, import_mentor_symbols, export_mentor_sym
from symbol_wizard.gui.selection_filter import (
    SELECTION_FILTER_KEYS,
    SELECTION_MODE_ITEMS,
    SELECTABLE_ITEM_KINDS,
    default_selection_enabled,
    normalize_selection_enabled,
    selection_filter_kind,
    selection_filter_kind_for_item,
    selection_flags_for_mode,
    is_selection_enabled_for_item,
)

def _font_value(font, key: str, default):
    """Read FontModel or JSON dict font values uniformly."""
    if isinstance(font, dict):
        return font.get(key, default)
    return getattr(font, key, default)


def _coerce_font_model(font, default_size=0.75):
    """Return a FontModel even when templates were restored from plain dicts."""
    if isinstance(font, FontModel):
        return font
    if isinstance(font, dict):
        return FontModel(
            family=str(font.get('family', 'Arial')),
            size_grid=float(font.get('size_grid', default_size)),
            color=tuple(font.get('color', (0, 0, 0)))
        )
    return FontModel(size_grid=default_size)


def _text_model_from_any(value, default_text: str, default_x: float, default_y: float, font, default_h='left', default_v='upper'):
    """Return a TextModel even when template JSON restored models as dicts.

    Template records are persisted via dataclasses.asdict().  After JSON load,
    FontModel/TextModel entries are plain dicts.  The editor normalizes them
    lazily here so the Template Editor can load old and new template files.
    """
    family = str(_font_value(font, 'family', 'Arial'))
    size_grid = float(_font_value(font, 'size_grid', 0.75))
    color = tuple(_font_value(font, 'color', (0, 0, 0)))
    if isinstance(value, TextModel):
        tm = value
    elif isinstance(value, dict):
        tm = TextModel(
            text=str(value.get('text', default_text)),
            x=float(value.get('x', default_x)),
            y=float(value.get('y', default_y)),
            font_family=str(value.get('font_family', family)),
            font_size_grid=float(value.get('font_size_grid', size_grid)),
            color=tuple(value.get('color', color))
        )
        tm.h_align = str(value.get('h_align', default_h))
        tm.v_align = str(value.get('v_align', default_v))
        tm.wrap_text = bool(value.get('wrap_text', False))
        # Preserve common transform fields if present.
        for name in ('rotation', 'scale_x', 'scale_y'):
            if name in value:
                try:
                    setattr(tm, name, value[name])
                except Exception:
                    pass
    else:
        tm = TextModel(text=default_text, x=default_x, y=default_y,
                       font_family=family, font_size_grid=size_grid, color=color)
        tm.h_align = default_h
        tm.v_align = default_v
    return tm


class NoWheelOnValueWidgets(QObject):
    """Global UI guard for value widgets.

    QComboBox and spin box values are often changed accidentally while the user
    scrolls a long property panel. This filter blocks wheel based value changes
    for every combo/spin/dropdown in the complete tool.  It also makes Return /
    Enter finish property editing consistently: the editor commits its value via
    the normal Qt signal path and then loses focus, so the canvas returns to
    normal Select/Edit mode instead of keeping a text cursor/spinbox editor
    active.
    """
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and isinstance(obj, (QComboBox, QAbstractSpinBox)):
            event.ignore()
            return True
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if isinstance(obj, QAbstractSpinBox):
                try:
                    obj.interpretText()
                except Exception:
                    pass
                QTimer.singleShot(0, obj.clearFocus)
                return False
            if isinstance(obj, QLineEdit):
                QTimer.singleShot(0, obj.clearFocus)
                return False
        return False


def install_no_wheel_value_filter(owner):
    app = QApplication.instance()
    if app is None:
        return
    filt = getattr(app, '_symbol_wizard_no_wheel_value_filter', None)
    if filt is None:
        filt = NoWheelOnValueWidgets(app)
        app.installEventFilter(filt)
        app._symbol_wizard_no_wheel_value_filter = filt
    owner._no_wheel_value_filter = filt


class PinComboDelegate(QStyledItemDelegate):
    """Dropdown delegate for pin table cells without persistent cell widgets.

    This avoids Qt rendering text underneath always-visible QComboBox widgets.
    The cell is painted as a combo box, but the editor widget only exists while
    the user edits the cell.
    """
    def __init__(self, values: list[str], parent=None):
        super().__init__(parent)
        try:
            self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
            self.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing, False)
            self.viewport().setAttribute(Qt.WA_StaticContents, False)
        except Exception:
            pass
        self.values = values

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.addItems(self.values)
        combo.setFrame(False)
        combo.activated.connect(lambda *_: self.commitData.emit(combo))
        combo.activated.connect(lambda *_: self.closeEditor.emit(combo, QAbstractItemDelegate.NoHint))
        return combo

    def setEditorData(self, editor, index):
        value = str(index.data(Qt.EditRole) or index.data(Qt.DisplayRole) or '')
        i = editor.findText(value)
        editor.setCurrentIndex(i if i >= 0 else 0)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    def paint(self, painter, option, index):
        # Paint a clean combo look and do NOT call the default item painter,
        # otherwise some Qt styles draw the text twice.
        opt = QStyleOptionComboBox()
        opt.rect = option.rect.adjusted(1, 1, -1, -1)
        opt.currentText = str(index.data(Qt.DisplayRole) or '')
        opt.state = option.state
        opt.editable = False
        widget = option.widget
        style = widget.style() if widget else QApplication.style()
        style.drawComplexControl(QStyle.CC_ComboBox, opt, painter, widget)
        style.drawControl(QStyle.CE_ComboBoxLabel, opt, painter, widget)




class SplitPinManagerDialog(QDialog):
    """Pin overview and bulk visibility editor for complete split symbols.

    The dialog intentionally works on the semantic pin model, not on the current
    canvas selection.  It can therefore edit all pins of all split-parts at once.
    """
    COL_MARK = 0
    COL_UNIT = 1
    COL_NUMBER = 2
    COL_NAME = 3
    COL_FUNCTION = 4
    COL_TYPE = 5
    COL_INVERTED = 6
    COL_SHOW_NUMBER = 7
    COL_SHOW_NAME = 8
    COL_SHOW_FUNCTION = 9

    def __init__(self, parent: 'MainWindow'):
        super().__init__(parent)
        self.main = parent
        self.symbol = parent.symbol
        self._loading = False
        self.setWindowTitle('Split Pin Manager')
        self.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)
        self.setWindowFlag(Qt.WindowCloseButtonHint, True)
        self.resize(1200, 720)
        self._build_ui()
        self.reload()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel('All pins of the current symbol / split symbol')
        title.setStyleSheet('font-weight: bold;')
        layout.addWidget(title)
        self.pin_count_label = QLabel('Gesamtpins: 0')
        self.pin_count_label.setStyleSheet('color: #555;')
        layout.addWidget(self.pin_count_label)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel('Global filter'))
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText('Search across unit, number, name, function and type')
        self.filter_edit.textChanged.connect(self.apply_filter)
        filter_row.addWidget(self.filter_edit, 1)
        self.only_marked = QCheckBox('Marked only')
        self.only_marked.stateChanged.connect(self.apply_filter)
        filter_row.addWidget(self.only_marked)
        clear_filters = QPushButton('Clear filters')
        clear_filters.clicked.connect(self.clear_filters)
        filter_row.addWidget(clear_filters)
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(['Mark', 'Unit', 'Pin Number', 'Pin Name', 'Pin Function', 'Type', 'Inverted', 'Show #', 'Show Name', 'Show Function'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        # Sorting is handled manually so the embedded filter row always stays
        # directly below the column headers.
        self.table.setSortingEnabled(False)
        self._sort_column = None
        self._sort_reverse = False
        self.table.horizontalHeader().sectionClicked.connect(self._sort_by_column)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.cellChanged.connect(self.cell_changed)
        self.table.cellDoubleClicked.connect(self.goto_pin_from_cell)
        try:
            self.table.itemSelectionChanged.connect(self._update_count_label)
        except Exception:
            pass
        self.column_filters = {}
        layout.addWidget(self.table, 1)

        mark_row = QHBoxLayout()
        for label, slot in [
            ('Mark selected rows', self.mark_selected_rows),
            ('Mark filtered rows', self.mark_filtered_rows),
            ('Clear marks', self.clear_marks),
        ]:
            b = QPushButton(label); b.clicked.connect(slot); mark_row.addWidget(b)
        mark_hint = QLabel('Double-click a table row to jump to that pin.')
        mark_hint.setStyleSheet('color: #666;')
        mark_row.addWidget(mark_hint)
        mark_row.addStretch(1)
        layout.addLayout(mark_row)

        bulk_box = QGroupBox('Bulk edit pins')
        bulk_outer = QVBoxLayout(bulk_box)
        bulk_outer.setContentsMargins(8, 8, 8, 8)
        bulk_outer.setSpacing(8)

        visibility_row = QHBoxLayout()
        visibility_row.setSpacing(12)
        self.show_number_combo = self._tri_combo()
        self.show_name_combo = self._tri_combo()
        self.show_function_combo = self._tri_combo()
        self.inverted_combo = self._tri_combo(on_text='Inverted', off_text='Not inverted')

        def add_bulk_pair(target_layout, label_text, combo):
            pair = QHBoxLayout()
            pair.setContentsMargins(0, 0, 0, 0)
            pair.setSpacing(4)
            lbl = QLabel(label_text)
            lbl.setMinimumWidth(82)
            combo.setMinimumWidth(120)
            pair.addWidget(lbl)
            pair.addWidget(combo)
            container = QWidget()
            container.setLayout(pair)
            target_layout.addWidget(container)

        add_bulk_pair(visibility_row, 'Show #', self.show_number_combo)
        add_bulk_pair(visibility_row, 'Show Name', self.show_name_combo)
        add_bulk_pair(visibility_row, 'Show Function', self.show_function_combo)
        add_bulk_pair(visibility_row, 'Inverted', self.inverted_combo)
        visibility_row.addStretch(1)
        bulk_outer.addLayout(visibility_row)

        function_row = QHBoxLayout()
        function_row.setSpacing(8)
        self.pin_type_edit_combo = QComboBox()
        self.pin_type_edit_combo.addItems(['Unchanged'] + [x.value for x in PinType])
        self.pin_type_edit_combo.setMinimumWidth(120)
        self.function_edit_combo = QComboBox()
        self.function_edit_combo.addItems(['Unchanged', 'Set to text', 'Clear', 'Copy from Pin Name', 'Copy from Pin Number'])
        self.function_edit_combo.setMinimumWidth(180)
        self.function_edit_text = QLineEdit()
        self.function_edit_text.setPlaceholderText('New Pin Function')
        self.function_edit_text.setMinimumWidth(260)
        self.function_edit_text.setEnabled(False)
        self.function_edit_combo.currentTextChanged.connect(lambda text: self.function_edit_text.setEnabled(text == 'Set to text'))
        function_row.addWidget(QLabel('Pin Type'))
        function_row.addWidget(self.pin_type_edit_combo)
        function_row.addSpacing(10)
        function_row.addWidget(QLabel('Pin Function Text'))
        function_row.addWidget(self.function_edit_combo)
        function_row.addWidget(self.function_edit_text, 1)
        function_row.addSpacing(10)
        for label, slot in [
            ('Apply to marked', self.apply_bulk_marked),
            ('Apply to filtered', self.apply_bulk_filtered),
            ('Apply to all pins', self.apply_bulk_all),
        ]:
            b = QPushButton(label); b.clicked.connect(slot); function_row.addWidget(b)
        bulk_outer.addLayout(function_row)

        font_row = QHBoxLayout()
        font_row.setSpacing(8)
        self.number_font_family_combo = QComboBox(); self.number_font_family_combo.addItem('Unchanged')
        self.label_font_family_combo = QComboBox(); self.label_font_family_combo.addItem('Unchanged')
        for combo in (self.number_font_family_combo, self.label_font_family_combo):
            combo.addItems(QFontDatabase.families())
            combo.setMinimumWidth(160)
        self.number_font_size_spin = QDoubleSpinBox(); self.number_font_size_spin.setRange(0.0, 5.0); self.number_font_size_spin.setDecimals(3); self.number_font_size_spin.setSingleStep(0.05); self.number_font_size_spin.setSuffix(' grid'); self.number_font_size_spin.setSpecialValueText('<multiple>')
        self.label_font_size_spin = QDoubleSpinBox(); self.label_font_size_spin.setRange(0.0, 5.0); self.label_font_size_spin.setDecimals(3); self.label_font_size_spin.setSingleStep(0.05); self.label_font_size_spin.setSuffix(' grid'); self.label_font_size_spin.setSpecialValueText('<multiple>')
        self._font_bulk_dirty = {'number_family': False, 'label_family': False, 'number_size': False, 'label_size': False}
        self.number_font_family_combo.currentTextChanged.connect(lambda *_: self._font_bulk_dirty.__setitem__('number_family', True))
        self.label_font_family_combo.currentTextChanged.connect(lambda *_: self._font_bulk_dirty.__setitem__('label_family', True))
        self.number_font_size_spin.valueChanged.connect(lambda *_: self._font_bulk_dirty.__setitem__('number_size', True))
        self.label_font_size_spin.valueChanged.connect(lambda *_: self._font_bulk_dirty.__setitem__('label_size', True))
        font_row.addWidget(QLabel('Number font'))
        font_row.addWidget(self.number_font_family_combo)
        font_row.addWidget(QLabel('Size [grid]'))
        font_row.addWidget(self.number_font_size_spin)
        font_row.addSpacing(10)
        font_row.addWidget(QLabel('Name/Function font'))
        font_row.addWidget(self.label_font_family_combo)
        font_row.addWidget(QLabel('Size [grid]'))
        font_row.addWidget(self.label_font_size_spin)
        font_row.addStretch(1)
        bulk_outer.addLayout(font_row)
        layout.addWidget(bulk_box)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _setup_filter_row(self):
        """Embed per-column filters as the first table row below the headers."""
        self.column_filters = {}
        placeholders = {
            self.COL_MARK: '',
            self.COL_UNIT: 'Filter Unit',
            self.COL_NUMBER: 'Filter #',
            self.COL_NAME: 'Filter Name',
            self.COL_FUNCTION: 'Filter Function',
            self.COL_TYPE: 'Filter Type',
            self.COL_INVERTED: 'yes/no',
            self.COL_SHOW_NUMBER: 'show/hide',
            self.COL_SHOW_NAME: 'show/hide',
            self.COL_SHOW_FUNCTION: 'show/hide',
        }
        # Row 0 is reserved for filters and is never a pin row.
        if self.table.rowCount() == 0:
            self.table.insertRow(0)
        self.table.setRowHeight(0, 28)
        for col in range(10):
            item = QTableWidgetItem('')
            item.setFlags(Qt.NoItemFlags)
            self.table.setItem(0, col, item)
            if col == self.COL_MARK:
                continue
            if col in (self.COL_INVERTED, self.COL_SHOW_NUMBER, self.COL_SHOW_NAME, self.COL_SHOW_FUNCTION):
                combo = QComboBox()
                combo.setFrame(False)
                if col == self.COL_INVERTED:
                    combo.addItems(['All', 'Inverted', 'Not inverted'])
                else:
                    combo.addItems(['All', 'Shown', 'Hidden'])
                combo.currentTextChanged.connect(lambda *_: self.apply_filter())
                self.column_filters[col] = combo
                self.table.setCellWidget(0, col, combo)
            else:
                edit = QLineEdit()
                edit.setPlaceholderText(placeholders.get(col, ''))
                edit.setClearButtonEnabled(True)
                edit.setFrame(False)
                edit.setContentsMargins(2, 0, 2, 0)
                edit.textChanged.connect(self.apply_filter)
                self.column_filters[col] = edit
                self.table.setCellWidget(0, col, edit)

    def _is_filter_row(self, row):
        return row == 0


    def _common_font_value_for_all_pins(self, font_attr, attr):
        vals = []
        for _ui, _pi, _unit, pin in self._all_pin_rows():
            font = getattr(pin, font_attr, None)
            if font is not None:
                vals.append(getattr(font, attr, None))
        if not vals:
            return '<multiple>'
        first = vals[0]
        return first if all(v == first for v in vals) else '<multiple>'

    def _sync_bulk_font_defaults(self):
        if not hasattr(self, 'number_font_family_combo'):
            return
        self._font_bulk_dirty = {'number_family': False, 'label_family': False, 'number_size': False, 'label_size': False}
        for combo, font_attr in ((self.number_font_family_combo, 'number_font'), (self.label_font_family_combo, 'label_font')):
            combo.blockSignals(True)
            value = self._common_font_value_for_all_pins(font_attr, 'family')
            if value == '<multiple>' and combo.findText('<multiple>') < 0:
                combo.insertItem(0, '<multiple>')
            combo.setCurrentText(str(value if value else 'Arial'))
            combo.blockSignals(False)
        for spin, font_attr in ((self.number_font_size_spin, 'number_font'), (self.label_font_size_spin, 'label_font')):
            spin.blockSignals(True)
            value = self._common_font_value_for_all_pins(font_attr, 'size_grid')
            try:
                spin.setValue(0.0 if value == '<multiple>' else float(value))
            except Exception:
                spin.setValue(0.0)
            spin.blockSignals(False)

    def _tri_combo(self, on_text='Show', off_text='Hide'):
        c = QComboBox()
        c.addItems(['Unchanged', on_text, off_text])
        return c

    def _all_pin_rows(self):
        rows = []
        for ui, unit in enumerate(self.symbol.units):
            for pi, pin in enumerate(unit.pins):
                rows.append((ui, pi, unit, pin))
        return rows

    def reload(self):
        self._loading = True
        self.table.setRowCount(0)
        self._setup_filter_row()

        rows = self._all_pin_rows()
        if self._sort_column is not None:
            def key_fn(entry):
                _ui, _pi, unit, pin = entry
                values = {
                    self.COL_MARK: '',
                    self.COL_UNIT: unit.name,
                    self.COL_NUMBER: pin.number,
                    self.COL_NAME: pin.name,
                    self.COL_FUNCTION: pin.function,
                    self.COL_TYPE: pin.pin_type,
                    self.COL_INVERTED: 'yes' if pin.inverted else 'no',
                    self.COL_SHOW_NUMBER: 'yes' if pin.visible_number else 'no',
                    self.COL_SHOW_NAME: 'yes' if pin.visible_name else 'no',
                    self.COL_SHOW_FUNCTION: 'yes' if pin.visible_function else 'no',
                }
                return str(values.get(self._sort_column, '')).lower()
            rows = sorted(rows, key=key_fn, reverse=self._sort_reverse)

        for ui, pi, unit, pin in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            values = ['', unit.name, pin.number, pin.name, pin.function, pin.pin_type, 'yes' if pin.inverted else 'no', '', '', '']
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, (ui, pi))
                if c in (self.COL_MARK, self.COL_INVERTED, self.COL_SHOW_NUMBER, self.COL_SHOW_NAME, self.COL_SHOW_FUNCTION):
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Unchecked)
                else:
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.table.setItem(r, c, item)
            self.table.item(r, self.COL_INVERTED).setCheckState(Qt.Checked if pin.inverted else Qt.Unchecked)
            self.table.item(r, self.COL_SHOW_NUMBER).setCheckState(Qt.Checked if pin.visible_number else Qt.Unchecked)
            self.table.item(r, self.COL_SHOW_NAME).setCheckState(Qt.Checked if pin.visible_name else Qt.Unchecked)
            self.table.item(r, self.COL_SHOW_FUNCTION).setCheckState(Qt.Checked if pin.visible_function else Qt.Unchecked)
        self.table.resizeColumnsToContents()
        minimums = {0: 70, 1: 160, 2: 120, 3: 240, 4: 240, 5: 90, 6: 90, 7: 85, 8: 110, 9: 125}
        for c, w in minimums.items():
            self.table.setColumnWidth(c, max(self.table.columnWidth(c), w))
        self._loading = False
        self.apply_filter()
        self._sync_bulk_font_defaults()

    def _sort_by_column(self, col):
        # Keep the embedded filter row fixed and sort only data rows by reloading
        # the semantic pin model in the requested order.
        if col == self.COL_MARK:
            return
        if self._sort_column == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = col
            self._sort_reverse = False
        self.reload()

    def _pin_for_item(self, item):
        if item is None:
            return None
        ui, pi = item.data(Qt.UserRole)
        try:
            return self.symbol.units[ui].pins[pi]
        except Exception:
            return None

    def _row_pin(self, row):
        item = self.table.item(row, self.COL_UNIT)
        return self._pin_for_item(item)

    def _row_unit_pin_indices(self, row):
        item = self.table.item(row, self.COL_UNIT)
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def cell_changed(self, row, col):
        if self._loading or self._is_filter_row(row) or col not in (self.COL_INVERTED, self.COL_SHOW_NUMBER, self.COL_SHOW_NAME, self.COL_SHOW_FUNCTION):
            return
        pin = self._row_pin(row)
        if pin is None:
            return
        attr = {
            self.COL_INVERTED: 'inverted',
            self.COL_SHOW_NUMBER: 'visible_number',
            self.COL_SHOW_NAME: 'visible_name',
            self.COL_SHOW_FUNCTION: 'visible_function',
        }[col]
        value = self.table.item(row, col).checkState() == Qt.Checked
        self.main.push_undo_state()
        setattr(pin, attr, value)
        self.main.rebuild_scene(); self.main.rebuild_pin_table(); self.main.refresh_properties()

    def _row_text(self, row):
        parts = []
        for c in (self.COL_UNIT, self.COL_NUMBER, self.COL_NAME, self.COL_FUNCTION, self.COL_TYPE, self.COL_INVERTED):
            item = self.table.item(row, c)
            parts.append(item.text().lower() if item else '')
        return ' '.join(parts)

    def _is_marked(self, row):
        item = self.table.item(row, self.COL_MARK)
        return bool(item and item.checkState() == Qt.Checked)

    def _visible_rows(self):
        return [r for r in range(1, self.table.rowCount()) if not self.table.isRowHidden(r)]

    def _cell_text(self, row, col):
        item = self.table.item(row, col)
        if not item:
            return ''
        if col in (self.COL_MARK, self.COL_INVERTED, self.COL_SHOW_NUMBER, self.COL_SHOW_NAME, self.COL_SHOW_FUNCTION):
            return 'yes' if item.checkState() == Qt.Checked else 'no'
        return item.text().lower()

    def _update_count_label(self):
        """Show total/filtered/marked/selected counts for the complete symbol."""
        try:
            total = max(0, self.table.rowCount() - 1)
            filtered = len([r for r in range(1, self.table.rowCount()) if not self.table.isRowHidden(r)])
            marked = len([r for r in range(1, self.table.rowCount()) if self._is_marked(r)])
            selected = len({i.row() for i in self.table.selectedItems() if i.row() > 0})
            units_count = len(getattr(self.symbol, 'units', []) or [])
            self.pin_count_label.setText(
                f'Pins gesamt: {total}  |  gefiltert: {filtered}  |  markiert: {marked}  |  ausgewählt: {selected}  |  Units/Parts: {units_count}'
            )
        except Exception:
            pass

    def clear_filters(self):
        self.filter_edit.clear()
        for widget in getattr(self, 'column_filters', {}).values():
            if isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
            else:
                widget.clear()
        self.only_marked.setChecked(False)
        self.apply_filter()

    def apply_filter(self):
        text = self.filter_edit.text().strip().lower()
        marked_only = self.only_marked.isChecked()
        column_terms = []
        bool_terms = []
        for col, widget in getattr(self, 'column_filters', {}).items():
            if isinstance(widget, QComboBox):
                choice = widget.currentText().strip().lower()
                if choice and choice != 'all':
                    bool_terms.append((col, choice))
            else:
                term = widget.text().strip().lower()
                if term:
                    column_terms.append((col, term))
        for r in range(self.table.rowCount()):
            if self._is_filter_row(r):
                self.table.setRowHidden(r, False)
                continue
            text_ok = not text or text in self._row_text(r)
            column_ok = all(term in self._cell_text(r, col) for col, term in column_terms)
            for col, choice in bool_terms:
                cell = self._cell_text(r, col)
                if col == self.COL_INVERTED:
                    expected = 'yes' if choice == 'inverted' else 'no'
                else:
                    expected = 'yes' if choice == 'shown' else 'no'
                if cell != expected:
                    column_ok = False
                    break
            marked_ok = not marked_only or self._is_marked(r)
            filter_ok = text_ok and column_ok
            ok = filter_ok and marked_ok
            self.table.setRowHidden(r, not ok)
        self._update_count_label()

    def mark_selected_rows(self):
        self._loading = True
        for item in self.table.selectedItems():
            r = item.row()
            if self._is_filter_row(r):
                continue
            mark = self.table.item(r, self.COL_MARK)
            if mark:
                mark.setCheckState(Qt.Checked)
        self._loading = False
        self.apply_filter()

    def mark_filtered_rows(self):
        self._loading = True
        for r in self._visible_rows():
            mark = self.table.item(r, self.COL_MARK)
            if mark:
                mark.setCheckState(Qt.Checked)
        self._loading = False
        self.apply_filter()

    def clear_marks(self):
        self._loading = True
        for r in range(1, self.table.rowCount()):
            mark = self.table.item(r, self.COL_MARK)
            if mark:
                mark.setCheckState(Qt.Unchecked)
        self._loading = False
        self.apply_filter()

    def _bulk_values(self):
        values = {}
        mapping = [
            (self.show_number_combo, 'visible_number', 'Show', 'Hide'),
            (self.show_name_combo, 'visible_name', 'Show', 'Hide'),
            (self.show_function_combo, 'visible_function', 'Show', 'Hide'),
            (self.inverted_combo, 'inverted', 'Inverted', 'Not inverted'),
        ]
        for combo, attr, on_text, off_text in mapping:
            text = combo.currentText()
            if text == on_text:
                values[attr] = True
            elif text == off_text:
                values[attr] = False
        return values

    def _function_edit_mode(self):
        try:
            return self.function_edit_combo.currentText()
        except Exception:
            return 'Unchanged'

    def _pin_type_edit_value(self):
        try:
            value = self.pin_type_edit_combo.currentText().strip()
        except Exception:
            return None
        if not value or value == 'Unchanged':
            return None
        valid = {x.value for x in PinType}
        return value if value in valid else None

    def _sync_pin_type_metadata(self, pin, pin_type=None):
        if pin is None:
            return
        try:
            ptype = str(pin_type if pin_type is not None else getattr(pin, 'pin_type', '') or '')
            if getattr(pin, 'attributes', None) is None:
                pin.attributes = {}
            pin.attributes['PINTYPE'] = ptype
            color = tuple(mentor_pin_color(ptype))
            pin.color = color
            for font_attr in ('number_font', 'label_font'):
                font = getattr(pin, font_attr, None)
                if font is not None:
                    font.color = color
        except Exception:
            pass

    def _new_function_value(self, pin):
        mode = self._function_edit_mode()
        if mode == 'Set to text':
            return self.function_edit_text.text()
        if mode == 'Clear':
            return ''
        if mode == 'Copy from Pin Name':
            return pin.name
        if mode == 'Copy from Pin Number':
            return pin.number
        return None

    def _apply_bulk_to_rows(self, rows):
        values = self._bulk_values()
        pin_type_value = self._pin_type_edit_value()
        pin_type_change = pin_type_value is not None
        function_mode = self._function_edit_mode()
        function_change = function_mode != 'Unchanged'
        number_family = self.number_font_family_combo.currentText().strip() if hasattr(self, 'number_font_family_combo') else '<multiple>'
        label_family = self.label_font_family_combo.currentText().strip() if hasattr(self, 'label_font_family_combo') else '<multiple>'
        number_size = self.number_font_size_spin.value() if hasattr(self, 'number_font_size_spin') else 0.0
        label_size = self.label_font_size_spin.value() if hasattr(self, 'label_font_size_spin') else 0.0
        dirty = getattr(self, '_font_bulk_dirty', {})
        font_change = any(bool(dirty.get(k)) for k in ('number_family', 'label_family', 'number_size', 'label_size'))
        if not values and not function_change and not pin_type_change and not font_change:
            return
        pins = []
        for r in rows:
            pin = self._row_pin(r)
            if pin is not None:
                pins.append(pin)
        if not pins:
            return
        self.main.push_undo_state()
        for pin in pins:
            for attr, value in values.items():
                setattr(pin, attr, value)
            if pin_type_change:
                pin.pin_type = pin_type_value
                self._sync_pin_type_metadata(pin, pin_type_value)
            if function_change:
                pin.function = self._new_function_value(pin)
            if dirty.get('number_family') and number_family not in ('', 'Unchanged', '<multiple>'):
                pin.number_font.family = number_family
            if dirty.get('label_family') and label_family not in ('', 'Unchanged', '<multiple>'):
                pin.label_font.family = label_family
            if dirty.get('number_size') and number_size > 0.0:
                pin.number_font.size_grid = float(number_size)
            if dirty.get('label_size') and label_size > 0.0:
                pin.label_font.size_grid = float(label_size)
        self.reload()
        self.main.rebuild_scene(); self.main.rebuild_pin_table(); self.main.refresh_properties()

    def apply_bulk_marked(self):
        self._apply_bulk_to_rows([r for r in range(1, self.table.rowCount()) if self._is_marked(r)])

    def apply_bulk_filtered(self):
        self._apply_bulk_to_rows(self._visible_rows())

    def apply_bulk_all(self):
        self._apply_bulk_to_rows(list(range(1, self.table.rowCount())))

    def goto_pin_from_cell(self, row, col):
        if self._is_filter_row(row):
            return
        self._goto_row(row)

    def goto_selected_pin(self):
        rows = sorted({i.row() for i in self.table.selectedItems()})
        if rows:
            self._goto_row(rows[0])

    def _goto_row(self, row):
        data = self._row_unit_pin_indices(row)
        if not data:
            return
        ui, pi = data
        self.main.current_unit_index = ui
        self.main.rebuild_unit_tabs(); self.main.rebuild_scene(); self.main.rebuild_tree(); self.main.rebuild_pin_table()
        try:
            self.main.select_model_in_scene(self.symbol.units[ui].pins[pi])
        except Exception:
            pass


class TemplateEditorDialog(QDialog):
    """Independent canvas-based editor for reusable symbol templates."""
    def __init__(self, parent: 'MainWindow'):
        super().__init__(parent)
        try:
            self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
            self.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing, False)
            self.viewport().setAttribute(Qt.WA_StaticContents, False)
        except Exception:
            pass
        install_no_wheel_value_filter(self)
        self.main = parent
        self.is_template_editor = True
        self.template_keys = parent.available_template_keys(False)
        self.templates = {k: None for k in self.template_keys}
        if not self.templates and hasattr(parent, 'builtin_resistor_templates'):
            self.templates = parent.builtin_resistor_templates()
        if not self.templates:
            QMessageBox.warning(
                self,
                'Templates not found',
                'Es wurden keine Templates geladen. Erwarteter Katalog:\n' + str(parent.symbol_types_path()) +
                '\n\nBitte prüfen, ob die Datei existiert und gültiges JSON enthält.'
            )
        self.unit = parent.load_template_unit(next(iter(self.templates.keys()), 'Passive / Resistor')) if self.templates else SymbolUnitModel()
        self.draw_tool = DrawTool.SELECT.value
        self.default_color = (0, 0, 0)
        self.symbol = SymbolModel(name='Template Editor', units=[self.unit])
        # Keep the template's logical grid at 0.100" by default, but allow
        # a finer edit/snap grid.  Liebherr/Mentor passive symbols often use
        # half-grid geometry (e.g. body edges at 0.5 grid while pin anchors
        # stay on 1.0 grid).
        self.symbol.grid_inch = float(getattr(self.symbol, 'grid_inch', 0.1) or 0.1)
        self.edit_grid_inch = 0.05
        self._format_guide_offset = (0.0, 0.0)
        self.current_unit_index = 0
        self.scene = SymbolScene(self)
        self.view = SymbolView(self.scene, self)
        self.clipboard = []
        self.clipboard_is_cut = False
        self.undo_stack = []
        self.redo_stack = []
        self.max_history = 200
        self.dirty = False
        self._loading_template = False
        self._reverting_template_combo = False
        self._current_template_name = None
        self._clean_template_snapshot = None
        self.selection_enabled = selection_flags_for_mode('ALL')
        self._selection_restore_ids: set[int] = set()
        self.setWindowTitle('Edit Symbol Templates')
        self.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)
        self.setWindowFlag(Qt.WindowCloseButtonHint, True)
        self._loading_template = False
        self._current_template_name = None
        self._clean_template_snapshot = None
        self.resize(1200, 800)
        self._build_ui()
        self.rebuild_template_partition_combos()
        if hasattr(self, 'template_combo') and self.template_combo.count() > 0:
            self.load_selected_template()

    @property
    def current_unit(self):
        return self.unit

    @property
    def grid_px(self):
        # Base logical grid used by the JSON model.  Coordinates are stored
        # in 0.100" grid units unless the symbol itself says otherwise.
        return self.symbol.grid_inch * PX_PER_INCH

    @property
    def edit_grid_px(self):
        return float(getattr(self, 'edit_grid_inch', self.symbol.grid_inch) or self.symbol.grid_inch) * PX_PER_INCH

    @property
    def edit_grid_step(self):
        base = float(getattr(self.symbol, 'grid_inch', 0.1) or 0.1)
        edit = float(getattr(self, 'edit_grid_inch', base) or base)
        if edit <= 0:
            return 1.0
        return max(0.01, edit / base)

    def snap_grid_value(self, v):
        step = self.edit_grid_step
        return round(float(v) / step) * step

    def scene_to_grid_x(self, x): return self.snap_grid_value(x / self.grid_px)
    def scene_to_grid_y(self, y): return self.snap_grid_value(-y / self.grid_px)

    def _font_families(self):
        try:
            return QFontDatabase.families()
        except Exception:
            return ['Arial', 'Calibri', 'Times New Roman', 'Courier New']

    def _font_combo(self, value, fn):
        w = QComboBox(); w.addItems(self._font_families()); w.setEditable(True); w.setCurrentText(str(value)); w.currentTextChanged.connect(fn); return w

    def _unique_pin_name(self, base='PIN'):
        existing = {str(p.name) for p in self.unit.pins}
        root = str(base or 'PIN').strip() or 'PIN'
        if root not in existing:
            return root
        i = 2
        while f'{root}_{i}' in existing:
            i += 1
        return f'{root}_{i}'

    def _unique_pin_number(self):
        existing = [str(p.number) for p in self.unit.pins]
        return next_pin_number(existing)


    def _load_autosave_library(self) -> LibraryModel:
        try:
            if getattr(self, '_autosave_path', None) and self._autosave_path.exists():
                lib = load_library(self._autosave_path)
                if lib.symbols:
                    return lib
        except Exception:
            pass
        return LibraryModel()

    def _save_autosave_library(self) -> None:
        try:
            if getattr(self, '_autosave_path', None):
                save_library(self._autosave_path, self.library)
        except Exception:
            pass

    def closeEvent(self, event):
        self._save_autosave_library()
        event.accept()

    def schedule_property_refresh(self):
        """Template canvas model change throttle for live property-panel sync."""
        if getattr(self, '_property_refresh_pending', False):
            return
        self._property_refresh_pending = True
        def _do():
            self._property_refresh_pending = False
            try:
                self.refresh_properties()
            except Exception:
                pass
        QTimer.singleShot(0, _do)

    def notify_canvas_model_changed(self):
        try:
            self.live_refresh()
        except Exception:
            pass
        self.schedule_property_refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.partition_combo = QComboBox(); self.partition_combo.setEditable(True)
        self.partition_combo.currentTextChanged.connect(self.on_partition_changed)
        self.template_combo = QComboBox()
        self.template_combo.currentTextChanged.connect(self.request_template_change)
        self.template_combo.activated.connect(lambda _idx: self.request_template_change(self.current_template_key()))
        top.addWidget(QLabel('Partition:')); top.addWidget(self.partition_combo, 1)
        top.addWidget(QLabel('Symbol:')); top.addWidget(self.template_combo, 1)
        self.rename_edit = QLineEdit(); top.addWidget(QLabel('Save symbol as:')); top.addWidget(self.rename_edit, 1)
        save_btn = QPushButton('Save Template'); save_btn.clicked.connect(lambda _checked=False: self.save_template())
        top.addWidget(save_btn)
        layout.addLayout(top)

        grid_row = QHBoxLayout()
        grid_row.addWidget(QLabel('Template grid:'))
        self.template_grid_combo = QComboBox()
        self.template_grid_combo.addItems(['0.100"', '0.050"', '0.025"', '0.010"', '0.005"', '0.003"'])
        self.template_grid_combo.setCurrentText('0.100"')
        self.template_grid_combo.currentTextChanged.connect(self.set_template_edit_grid)
        grid_row.addWidget(self.template_grid_combo)
        grid_row.addWidget(QLabel('Snap:'))
        self.template_snap_check = QCheckBox('On')
        self.template_snap_check.setChecked(True)
        self.template_snap_check.toggled.connect(lambda _checked: self.scene.update())
        grid_row.addWidget(self.template_snap_check)
        grid_row.addWidget(QLabel('Base symbol grid remains 0.100"; fine grid is only for edit/snap.'))
        analyze_btn = QPushButton('Analyze Geometry')
        analyze_btn.setToolTip('Prüft Body-Grafik, Pin-Andockpunkte und Rasterlage, ohne das Template zu ändern.')
        analyze_btn.clicked.connect(self.analyze_template_geometry)
        grid_row.addWidget(analyze_btn)
        optimize_btn = QPushButton('Optimize Pin Docking')
        optimize_btn.setToolTip('Optional: Pin-Anker auf die nächste Body-Kante legen. Grafik bleibt unverändert.')
        optimize_btn.clicked.connect(self.optimize_template_pin_docking)
        grid_row.addWidget(optimize_btn)
        grid_row.addStretch()
        layout.addLayout(grid_row)

        tools = QHBoxLayout()
        self.tool_buttons = {}
        for tool, label in [(DrawTool.SELECT, 'Select/Edit'), (DrawTool.PIN, 'Pin'), (DrawTool.TEXT, 'Text'), (DrawTool.LINE, 'Line'), (DrawTool.RECT, 'Rect'), (DrawTool.ELLIPSE, 'Ellipse')]:
            b = QPushButton(label); b.setCheckable(True); b.clicked.connect(lambda _, t=tool.value: self.set_tool(t))
            tools.addWidget(b); self.tool_buttons[tool.value] = b
        self.tool_buttons[self.draw_tool].setChecked(True)
        for label, fn in [('Select All', self.select_all_canvas), ('Undo', self.undo), ('Redo', self.redo)]:
            b = QPushButton(label); b.clicked.connect(fn); tools.addWidget(b)

        # Template Editor has its own shortcuts.  Do not rely on keyPressEvent
        # only, because focus can be inside QGraphicsView, QLineEdit, QComboBox
        # or a spinbox.  WidgetWithChildrenShortcut keeps Ctrl+Z/Ctrl+Y local
        # to this dialog and avoids conflicts with the main Symbol Wizard.
        self._template_shortcuts = []
        for seq, fn in ((QKeySequence.Undo, self.undo), (QKeySequence.Redo, self.redo),
                        (QKeySequence('Ctrl+Shift+Z'), self.redo)):
            sc = QShortcut(seq, self)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)
            self._template_shortcuts.append(sc)

        tools.addStretch(); layout.addLayout(tools)
        tools = QHBoxLayout()
        for label, fn in [('⟲ 90°', lambda: self.rotate_selected(-90)), ('⟳ 90°', lambda: self.rotate_selected(90)), ('Flip H', self.flip_selected_horizontal), ('Flip V', self.flip_selected_vertical)]:
            b = QPushButton(label); b.clicked.connect(fn); tools.addWidget(b)
        tools.addWidget(QLabel('Origin:'))
        self.origin_combo = QComboBox()
        self.origin_combo.addItems([x.value for x in OriginMode])
        self.origin_combo.setCurrentText(getattr(self.symbol, 'origin', OriginMode.CENTER.value))
        self.origin_combo.currentTextChanged.connect(self.origin_mode_changed)
        tools.addWidget(self.origin_combo)
        origin_btn = QPushButton('Origin Reset')
        origin_btn.clicked.connect(lambda _checked=False: self.reset_origin_to_selected_anchor())
        tools.addWidget(origin_btn)
        tools.addWidget(QLabel('Selectable:'))
        self.selection_mode_combo = QComboBox()
        self.selection_mode_combo.addItems(list(SELECTION_MODE_ITEMS))
        self.selection_mode_combo.currentTextChanged.connect(self.set_selection_mode)
        self.selection_mode_combo.activated.connect(lambda *_: self.set_selection_mode(self.selection_mode_combo.currentText()))
        tools.addWidget(self.selection_mode_combo)
        self.selection_custom_checks = {}
        for kind in SELECTION_FILTER_KEYS:
            cb = QCheckBox(kind); cb.setChecked(True); cb.setVisible(False)
            cb.toggled.connect(lambda checked, k=kind: self.set_selection_enabled(k, checked))
            self.selection_custom_checks[kind] = cb
            tools.addWidget(cb)
        self.set_selection_mode(self.selection_mode_combo.currentText())
        tools.addStretch(); layout.addLayout(tools)
        splitter = QSplitter()
        self.template_splitter = splitter
        splitter.addWidget(self.view)

        # Keep the property panel usable for symbols/templates with many attributes.
        # The form itself is placed inside a scroll area, so all dynamically generated
        # body attributes, pin settings, text settings and graphic settings remain reachable.
        side = QWidget()
        self.form = QFormLayout(side)
        self.form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self.props_scroll = QScrollArea()
        self.props_scroll.setWidgetResizable(True)
        self.props_scroll.setMinimumWidth(320)
        self.props_scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.props_scroll.setWidget(side)
        splitter.addWidget(self.props_scroll)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([850, 300])
        layout.addWidget(splitter, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.scene.selectionChanged.connect(self.on_scene_selection_changed)

    def _split_template_key(self, key: str):
        key = str(key or '').strip()
        if ' / ' in key:
            parts = [p.strip() for p in key.split(' / ') if p.strip()]
            if len(parts) >= 3 and parts[0] == 'Split Symbols':
                return ' / '.join(parts[:-1]), parts[-1]
            return parts[0] or 'General', ' / '.join(parts[1:]) or key
        return 'General', key or 'Template'

    def current_template_key(self):
        part = self.partition_combo.currentText().strip() if hasattr(self, 'partition_combo') else ''
        sym = self.template_combo.currentText().strip() if hasattr(self, 'template_combo') else ''
        if not part or part == 'General':
            return sym
        return f'{part} / {sym}' if sym else part

    def rebuild_template_partition_combos(self, select_key: str | None = None):
        select_key = select_key or getattr(self, '_current_template_name', None) or next(iter(sorted(self.templates.keys())), '')
        partitions = sorted({self._split_template_key(k)[0] for k in self.templates.keys()}) or ['General']
        part, sym = self._split_template_key(select_key)
        if part not in partitions:
            part = partitions[0]
        self.partition_combo.blockSignals(True)
        self.partition_combo.clear(); self.partition_combo.addItems(partitions); self.partition_combo.setCurrentText(part)
        self.partition_combo.blockSignals(False)
        self.rebuild_template_symbol_combo(part, sym)

    def rebuild_template_symbol_combo(self, partition: str, select_symbol: str | None = None):
        symbols = []
        for k in sorted(self.templates.keys()):
            p, name = self._split_template_key(k)
            if p == partition:
                symbols.append(name)
        if not symbols and partition == 'General':
            symbols = sorted(self.templates.keys())
        self.template_combo.blockSignals(True)
        self.template_combo.clear(); self.template_combo.addItems(symbols)
        if select_symbol and self.template_combo.findText(select_symbol) >= 0:
            self.template_combo.setCurrentText(select_symbol)
        self.template_combo.blockSignals(False)

    def on_partition_changed(self, partition: str):
        if getattr(self, '_loading_template', False) or getattr(self, '_reverting_template_combo', False):
            return
        old = getattr(self, '_current_template_name', None)
        if old is not None and not self._ask_save_if_dirty():
            self.rebuild_template_partition_combos(old)
            return
        self.rebuild_template_symbol_combo(partition)
        self.load_selected_template()

    def set_template_edit_grid(self, text):
        try:
            self.edit_grid_inch = float(str(text).replace('\"', '').strip())
        except Exception:
            self.edit_grid_inch = 0.05
        try:
            self.scene.update()
            self.view.viewport().update()
        except Exception:
            pass

    def _template_has_half_grid_geometry(self):
        def frac(v):
            try:
                return abs(float(v) - round(float(v))) > 1e-6
            except Exception:
                return False
        b = getattr(self.unit, 'body', None)
        if b and any(frac(getattr(b, a, 0)) for a in ('x', 'y', 'width', 'height')):
            return True
        for p in getattr(self.unit, 'pins', []):
            if any(frac(getattr(p, a, 0)) for a in ('x', 'y', 'length')):
                return True
        for t in list(getattr(self.unit, 'texts', [])) + list(getattr(getattr(self.unit, 'body', None), 'attribute_texts', {}).values()):
            if any(frac(getattr(t, a, 0)) for a in ('x', 'y')):
                return True
        for g in getattr(self.unit, 'graphics', []):
            if any(frac(getattr(g, a, 0)) for a in ('x', 'y', 'w', 'h')):
                return True
        return False

    def _sync_template_grid_combo_to_unit(self):
        # If the template already contains half-grid or quarter-grid geometry,
        # choose a fine edit grid automatically.  The user can still override it.
        target = '0.050"' if self._template_has_half_grid_geometry() else '0.100"'
        try:
            self.template_grid_combo.blockSignals(True)
            self.template_grid_combo.setCurrentText(target)
            self.template_grid_combo.blockSignals(False)
            self.set_template_edit_grid(target)
        except Exception:
            pass

    def _template_graphic_bounds(self):
        """Return body-artwork bounds in model grid coordinates.

        Imported/native templates can have an invisible logical body rectangle
        plus separate graphic primitives. For geometry quality checks the pins
        should dock to the visible artwork, not necessarily to the logical rect.
        """
        xs, ys = [], []
        for gr in getattr(self.unit, 'graphics', []) or []:
            try:
                x = float(getattr(gr, 'x', 0.0) or 0.0)
                y = float(getattr(gr, 'y', 0.0) or 0.0)
                w = float(getattr(gr, 'w', 0.0) or 0.0)
                h = float(getattr(gr, 'h', 0.0) or 0.0)
                if str(getattr(gr, 'shape', '')).lower() in ('line', 'arc'):
                    xs.extend([x, x + w])
                    ys.extend([y, y + h])
                    cx = getattr(gr, 'ctrl_x', None); cy = getattr(gr, 'ctrl_y', None)
                    if cx is not None and cy is not None:
                        xs.append(x + float(cx)); ys.append(y + float(cy))
                else:
                    xs.extend([x, x + w])
                    ys.extend([y, y - h])
            except Exception:
                continue
        if xs and ys:
            return (min(xs), min(ys), max(xs), max(ys))
        b = getattr(self.unit, 'body', None)
        if b:
            try:
                return (float(b.x), float(b.y) - float(b.height), float(b.x) + float(b.width), float(b.y))
            except Exception:
                pass
        return (0.0, 0.0, 0.0, 0.0)

    def _nearest_body_edge_point(self, x, y, bounds=None):
        if bounds is None:
            bounds = self._template_graphic_bounds()
        left, bottom, right, top = bounds
        candidates = [
            (left, min(max(y, bottom), top), 'left'),
            (right, min(max(y, bottom), top), 'right'),
            (min(max(x, left), right), top, 'top'),
            (min(max(x, left), right), bottom, 'bottom'),
        ]
        def d2(c):
            return (float(x) - c[0]) ** 2 + (float(y) - c[1]) ** 2
        return min(candidates, key=d2)

    def analyze_template_geometry(self):
        bounds = self._template_graphic_bounds()
        left, bottom, right, top = bounds
        pins = list(getattr(self.unit, 'pins', []) or [])
        issues = []
        for p in pins:
            try:
                x, y = float(p.x), float(p.y)
                nx, ny, edge = self._nearest_body_edge_point(x, y, bounds)
                dist = ((x - nx) ** 2 + (y - ny) ** 2) ** 0.5
                side = str(getattr(p, 'side', '')).lower()
                if dist > 0.15:
                    issues.append(f'Pin {getattr(p, "number", "?")} / {getattr(p, "name", "")}: Anker {x:g},{y:g} liegt {dist:.2f} Grid von der sichtbaren Body-Kante entfernt.')
                elif edge and side and edge != side:
                    issues.append(f'Pin {getattr(p, "number", "?")} / {getattr(p, "name", "")}: Side={side}, nächste sichtbare Kante={edge}.')
            except Exception:
                continue
        frac = []
        def _frac(v):
            try: return abs(float(v) - round(float(v))) > 1e-6
            except Exception: return False
        for p in pins:
            if _frac(getattr(p, 'x', 0)) or _frac(getattr(p, 'y', 0)):
                frac.append(f'Pin {getattr(p, "number", "?")}')
        msg = [
            f'Template: {self.current_template_key()}',
            f'Sichtbare Body-Bounds: x={left:g}..{right:g}, y={bottom:g}..{top:g}',
            f'Pins: {len(pins)}',
        ]
        if frac:
            msg.append('Pins mit Zwischenraster: ' + ', '.join(frac[:20]) + (' ...' if len(frac) > 20 else ''))
        if issues:
            msg.append('\nAuffälligkeiten:')
            msg.extend('• ' + x for x in issues[:40])
            if len(issues) > 40:
                msg.append(f'• ... {len(issues)-40} weitere')
        else:
            msg.append('\nKeine offensichtlichen Pin-/Body-Andockprobleme gefunden.')
        QMessageBox.information(self, 'Template Geometry Analysis', '\n'.join(msg))

    def optimize_template_pin_docking(self):
        pins = list(getattr(self.unit, 'pins', []) or [])
        if not pins:
            QMessageBox.information(self, 'Optimize Pin Docking', 'Dieses Template enthält keine Pins.')
            return
        ans = QMessageBox.question(
            self,
            'Optimize Pin Docking',
            'Pin-Anker auf die nächste sichtbare Body-Kante legen?\n\nDie Body-Grafik wird nicht verändert. Diese Funktion ist bewusst optional, weil einige Library-Symbole absichtlich so aufgebaut sein können.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ans != QMessageBox.Yes:
            return
        self.push_undo_state()
        bounds = self._template_graphic_bounds()
        changed = 0
        for p in pins:
            try:
                x, y = float(p.x), float(p.y)
                nx, ny, edge = self._nearest_body_edge_point(x, y, bounds)
                if ((x - nx) ** 2 + (y - ny) ** 2) ** 0.5 > 0.05:
                    dx, dy = nx - x, ny - y
                    p.x, p.y = nx, ny
                    try:
                        p.side = edge
                    except Exception:
                        pass
                    for ax_name, ay_name in (('label_x', 'label_y'), ('number_x', 'number_y')):
                        if getattr(p, ax_name, None) is not None and getattr(p, ay_name, None) is not None:
                            setattr(p, ax_name, float(getattr(p, ax_name)) + dx)
                            setattr(p, ay_name, float(getattr(p, ay_name)) + dy)
                    for tm in (getattr(p, 'attribute_texts', {}) or {}).values():
                        try:
                            tm.x = float(tm.x) + dx
                            tm.y = float(tm.y) + dy
                        except Exception:
                            pass
                    changed += 1
            except Exception:
                continue
        self.rebuild_scene()
        QMessageBox.information(self, 'Optimize Pin Docking', f'{changed} Pin-Anker angepasst.')

    def set_tool(self, t):
        self.draw_tool = t
        for k, b in self.tool_buttons.items(): b.setChecked(k == t)
        self.view.setDragMode(QGraphicsView.RubberBandDrag if t == DrawTool.SELECT.value else QGraphicsView.NoDrag)

    def push_undo_state(self):
        if getattr(self, '_loading_template', False) or getattr(self, '_restoring_undo_redo', False):
            return
        # Store the complete template unit BEFORE every real edit.
        # Important: the clean snapshot after loading must NOT suppress the first
        # undo entry.  The previous implementation compared against
        # _last_undo_state, which is initialized from the freshly loaded template;
        # therefore the very first edit often produced no undo snapshot and the
        # Template Editor Undo/Redo buttons appeared dead.
        try:
            state = self._template_state()
            if self.undo_stack:
                last_unit = self.undo_stack[-1]
                last_state = self._unit_state_for_undo(last_unit)
                if last_state == state:
                    self.dirty = True
                    return
            self._last_undo_state = copy.deepcopy(state)
        except Exception:
            pass
        self.dirty = True
        self.undo_stack.append(copy.deepcopy(self.unit))
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def _restore_template_unit_from_history(self, unit):
        self._restoring_undo_redo = True
        try:
            self.unit = copy.deepcopy(unit)
            self.symbol.units = [self.unit]
            try:
                self._lock_template_body_graphics(self.unit)
            except Exception:
                pass
            self._selection_restore_ids = set()
            self.rebuild_scene()
            self.dirty = self._template_has_unsaved_changes()
            try:
                self._last_undo_state = self._template_state()
            except Exception:
                pass
        finally:
            self._restoring_undo_redo = False

    def undo(self):
        self.set_tool(DrawTool.SELECT.value)
        if not self.undo_stack:
            return
        current = copy.deepcopy(self.unit)
        previous = self.undo_stack.pop()
        self.redo_stack.append(current)
        self._restore_template_unit_from_history(previous)

    def redo(self):
        self.set_tool(DrawTool.SELECT.value)
        if not self.redo_stack:
            return
        current = copy.deepcopy(self.unit)
        nxt = self.redo_stack.pop()
        self.undo_stack.append(current)
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
        self._restore_template_unit_from_history(nxt)

    def rotate_selected(self, deg):
        self.push_undo_state()
        for it in self.scene.selectedItems():
            if hasattr(it, 'rotate_by'):
                it.rotate_by(deg)
        self.live_refresh()

    def flip_selected_horizontal(self):
        self.push_undo_state()
        for it in self.scene.selectedItems():
            if hasattr(it, 'flip_horizontal'):
                it.flip_horizontal()
        self.live_refresh()

    def flip_selected_vertical(self):
        self.push_undo_state()
        for it in self.scene.selectedItems():
            if hasattr(it, 'flip_vertical'):
                it.flip_vertical()
        self.live_refresh()

    def _template_state(self):
        """Stable serializable state used to detect real unsaved template edits.

        QGraphicsScene rebuilds may transiently normalize dataclass/dict/font objects.
        Store a deterministic JSON-compatible representation, otherwise merely
        opening/viewing a template can look dirty and trigger a false save prompt.
        """
        def _norm(v):
            if hasattr(v, '__dataclass_fields__'):
                return _norm(asdict(v))
            if isinstance(v, dict):
                return {str(k): _norm(v[k]) for k in sorted(v.keys(), key=str)}
            if isinstance(v, (list, tuple)):
                return [_norm(x) for x in v]
            if isinstance(v, float):
                return round(v, 9)
            return v
        try:
            return _norm(self.unit)
        except Exception:
            try:
                return json.loads(json.dumps(asdict(self.unit), sort_keys=True, default=str))
            except Exception:
                return repr(self.unit)

    def _capture_clean_template_snapshot(self):
        self._clean_template_snapshot = self._template_state()
        self.dirty = False
        self.undo_stack.clear()
        self.redo_stack.clear()
        try:
            self._last_undo_state = self._template_state()
        except Exception:
            self._last_undo_state = None

    def _template_has_unsaved_changes(self) -> bool:
        """Detect real template content changes by comparing with the saved snapshot."""
        if getattr(self, '_loading_template', False):
            return False
        try:
            snap = getattr(self, '_clean_template_snapshot', None)
            return snap is not None and self._template_state() != snap
        except Exception:
            return bool(getattr(self, 'dirty', False))

    def is_template_dirty(self) -> bool:
        """Compatibility wrapper used by undo/redo and older template-editor code."""
        return self._template_has_unsaved_changes()

    def _ask_save_if_dirty(self) -> bool:
        """Return True when the pending action may continue."""
        if not self._template_has_unsaved_changes():
            self.dirty = False
            return True
        ans = QMessageBox.question(
            self,
            'Save Changes?',
            'Das aktuelle Template wurde geändert. Änderungen speichern?',
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes,
        )
        if ans == QMessageBox.Cancel:
            return False
        if ans == QMessageBox.Yes:
            self.save_template(show_message=False)
        else:
            self._clean_template_snapshot = self._template_state()
            self.dirty = False
        return True

    def request_template_change(self, name):
        if getattr(self, '_loading_template', False) or getattr(self, '_reverting_template_combo', False):
            return
        old = getattr(self, '_current_template_name', None)
        if old is None:
            self.load_selected_template()
            return
        name = self.current_template_key()
        if name == old:
            return
        if not self._ask_save_if_dirty():
            self._reverting_template_combo = True
            try:
                self.template_combo.blockSignals(True)
                self.template_combo.setCurrentText(old)
                self.template_combo.blockSignals(False)
            finally:
                self._reverting_template_combo = False
            return
        self.load_selected_template()

    def load_selected_template(self):
        name = self.current_template_key()
        if not name: return
        self._loading_template = True
        self.unit = self.main.load_template_unit(name); self.symbol.units=[self.unit]
        # Template graphics remain Body-owned.  They are individually editable only
        # because this is the Template Editor; when the same template is used in the
        # Symbol Wizard, the graphics are selected/moved only through the Body.
        try:
            self.unit.body.attributes['TEMPLATE_GRAPHICS_AS_BODY'] = '1'
        except Exception:
            pass
        self._lock_template_body_graphics(self.unit)
        if hasattr(self, 'origin_combo'):
            self.origin_combo.blockSignals(True)
            self.origin_combo.setCurrentText(getattr(self.symbol, 'origin', OriginMode.CENTER.value))
            self.origin_combo.blockSignals(False)
        self.rename_edit.setText(self._split_template_key(name)[1])
        if hasattr(self, 'template_grid_combo'):
            self._sync_template_grid_combo_to_unit()
        self._current_template_name = name
        self.rebuild_scene()
        # Rebuild may normalize attribute/text/font helper models. Snapshot only
        # after the scene has been built, so viewing a template is never treated
        # as an edit.
        self._capture_clean_template_snapshot()
        self._loading_template = False

    def save_template(self, show_message=True):
        part = self.partition_combo.currentText().strip() if hasattr(self, 'partition_combo') else ''
        sym_name = self.rename_edit.text().strip() or self.template_combo.currentText() or 'Template'
        name = f'{part} / {sym_name}' if part and part != 'General' else sym_name
        # Every graphic primitive stored by the Template Editor is part of the
        # template Body.  The Template Editor may edit the primitives individually;
        # the Symbol Wizard must treat them as one Body-owned graphic group.
        try:
            self.unit.body.attributes['TEMPLATE_GRAPHICS_AS_BODY'] = '1'
            self.unit.body.attributes['MENTOR_GRAPHICS_AS_BODY'] = '1'
            self.unit.body.attributes['MENTOR_BODY_GRAPHICS_LOCKED'] = '1'
            self.unit.body.attributes['MENTOR_DISABLE_AUTO_DOCK'] = '1'
        except Exception:
            pass
        for _g in getattr(self.unit, 'graphics', []) or []:
            try:
                _g.locked_to_body = True
                _g.graphic_role = 'template_body'
                if str(getattr(_g, 'mentor_raw', '') or '') == '__USER_GRAPHIC__':
                    _g.mentor_raw = ''
            except Exception:
                pass
        for _p in getattr(self.unit, 'pins', []) or []:
            try:
                _p.auto_dock = False
            except Exception:
                pass
        self.templates[name] = copy.deepcopy(self.unit)
        if hasattr(self.main, 'merge_save_template_to_file'):
            self.main.merge_save_template_to_file(name, self.unit)
            self.main.symbol_templates.clear()
            if hasattr(self.main, 'invalidate_template_cache'):
                self.main.invalidate_template_cache()
        if hasattr(self.main, 'apply_template_style_to_matching_symbols'):
            self.main.apply_template_style_to_matching_symbols(name, self.unit)
        self.rebuild_template_partition_combos(name)
        self._current_template_name = name
        self._capture_clean_template_snapshot()
        self.main.rebuild_all()
        if show_message:
            QMessageBox.information(self, 'Template', f'Template "{name}" saved.')

    
    def keyPressEvent(self, event):
        try:
            if event.modifiers() & Qt.ControlModifier:
                if event.key() == Qt.Key_V:
                    self.paste_selected(); return
                if event.key() == Qt.Key_C:
                    self.copy_selected(); return
                if event.key() == Qt.Key_X:
                    self.cut_selected(); return
                if event.key() == Qt.Key_A:
                    self.select_all_canvas(); return
                if event.key() == Qt.Key_Z:
                    self.undo(); return
                if event.key() == Qt.Key_Y:
                    self.redo(); return
        except Exception:
            pass
        super().keyPressEvent(event)
    def closeEvent(self, event):
        if not self._ask_save_if_dirty():
            event.ignore(); return
        event.accept()

    def reject(self):
        if not self._ask_save_if_dirty():
            return
        super().reject()

    def done(self, r):
        if r == QDialog.Rejected and not self._ask_save_if_dirty():
            return
        super().done(r)

    def rebuild_scene(self):
        selected_ids = self._selection_restore_ids or self._capture_selection_ids()
        self._selection_restore_ids = set()
        self.scene.blockSignals(True); self.scene.clear()
        if self.unit.body and self.unit.body.width > 0 and self.unit.body.height > 0:
            item = BodyItem(self.unit.body, self); self.apply_item_selectability(item); self.scene.addItem(item); self._restore_item_selection(item, selected_ids)
        self.add_attribute_text_items(self.unit)
        for g in self.unit.graphics:
            item = GraphicItem(g, self); self.apply_item_selectability(item); self.scene.addItem(item); self._restore_item_selection(item, selected_ids)
        for p in self.unit.pins:
            item = PinItem(p, self); self.apply_item_selectability(item); self.scene.addItem(item); self._restore_item_selection(item, selected_ids)
        for t in self.unit.texts:
            item = TextItem(t, self); self.apply_item_selectability(item); self.scene.addItem(item); self._restore_item_selection(item, selected_ids)
        self.scene.blockSignals(False); self.scene.update(); self.refresh_properties()

    def on_scene_selection_changed(self):
        try:
            self.view.viewport().update()
        except Exception:
            pass
        self.refresh_properties()

    def refresh_properties(self):
        if not hasattr(self, 'form') or self.form is None:
            return
        if hasattr(self, 'clear_properties'):
            self.clear_properties()
        else:
            while self.form.rowCount(): self.form.removeRow(0)
        sel = self.scene.selectedItems()
        if len(sel) > 1:
            self.form.addRow(QLabel(f'{len(sel)} objects selected'))
            pins = [i for i in sel if i.data(0) == 'PIN']
            if len(pins) == len(sel):
                self.form.addRow(QLabel(f'<b>Multi-Edit: {len(pins)} PINs</b>'))
                fn = QLineEdit('')
                fn.setPlaceholderText('Set Pin Function for all selected pins')
                fn.returnPressed.connect(lambda editor=fn, items=pins: self._set_selected_pins_attr(items, 'function', editor.text()))
                self.form.addRow('Pin Function', fn)
                for label, attr in [('Show Number', 'visible_number'), ('Show Name', 'visible_name'), ('Show Function', 'visible_function')]:
                    cb = self._multi_pin_visibility_checkbox(pins, attr)
                    self.form.addRow(label, cb)
                self.form.addRow('Pin Length [grid]', self._dbl(float(self._common_pin_value(pins, 'length', 1.0) or 1.0), lambda v, items=pins: self._set_selected_pins_attr(items, 'length', max(1.0, round(float(v)))), 1, 100, 1))
                self.form.addRow('Pin Style', self._combo([''] + [x.value for x in LineStyle], self._common_pin_value(pins, 'line_style', ''), lambda v, items=pins: v and self._set_selected_pins_attr(items, 'line_style', v)))
                self.form.addRow('Pin Width', self._dbl(float(self._common_pin_value(pins, 'line_width', 0.03) or 0.03), lambda v, items=pins: self._set_selected_pins_attr(items, 'line_width', float(v)), .01, 1, .01))
                self.form.addRow('Color', self._color_button_row('Color RGB', self._common_pin_value(pins, 'color', (0, 0, 0)) or (0, 0, 0), lambda _checked=False, items=pins: self.color_selected_pins(items)))
                self._template_multi_pin_font_props(pins)
            else:
                text_like = [i for i in sel if i.data(0) in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY')]
                graphics = [i for i in sel if i.data(0) == 'GRAPHIC']
                if len(text_like) == len(sel):
                    self.form.addRow(QLabel(f'<b>Multi-Edit: {len(text_like)} text objects</b>'))
                    self._template_multi_text_props(text_like)
                elif len(graphics) == len(sel):
                    self.form.addRow(QLabel(f'<b>Multi-Edit: {len(graphics)} graphic objects</b>'))
                    self.form.addRow('Line width', self._dbl(float(self._common_graphic_value(graphics, 'line_width', 0.03) or 0.03), lambda v, items=graphics: self._set_selected_graphics_style(items, 'line_width', float(v)), .01, 1, .01))
                else:
                    self.form.addRow(QLabel('Multi-edit is only available for PIN-only, TEXT/ATTRIBUTE-only or GRAPHIC-only selections.'))
            return
        if not sel:
            self.form.addRow(QLabel('No selection. Template canvas is independent from the Symbol Wizard.'))
            self.form.addRow(QLabel('<b>Template Attribute Visibility</b>'))
            for k in list(self.unit.body.attributes.keys()):
                row=QWidget(); l=QHBoxLayout(row); l.setContentsMargins(0,0,0,0)
                cb=QCheckBox('visible'); cb.setChecked(self.unit.body.visible_attributes.get(k, False))
                preview=QLabel(f"{k}: {self.unit.body.attributes.get(k, '')}" if str(self.unit.body.attributes.get(k, '')).strip() else k)
                cb.toggled.connect(lambda v, key=k: self._set_attr_vis(key, v))
                l.addWidget(cb); l.addWidget(preview); self.form.addRow(k, row)
            return
        item = sel[0]; kind = item.data(0); m = item.model
        self.form.addRow(self._selection_title_label(kind, item))
        if kind == 'BODY':
            # BODY settings must work for imported bodies exactly like for
            # internally generated <NONE> bodies.  Width/height are snapped to
            # the current edit-grid and scale the complete BODY group; rotation
            # is restricted to 90° steps from 0°.
            self.form.addRow('Width [grid]', self._dbl(m.width, lambda v, model=m: self._set_body_width_grid(model, v), 0.01, 500, self.edit_grid_step))
            self.form.addRow('Height [grid]', self._dbl(m.height, lambda v, model=m: self._set_body_height_grid(model, v), 0.01, 500, self.edit_grid_step))
            self.form.addRow('Line style', self._combo([x.value for x in LineStyle], getattr(m, 'line_style', LineStyle.SOLID.value), lambda v: self._set(m, 'line_style', v)))
            self.form.addRow('Line width', self._dbl(getattr(m, 'line_width', 0.03), lambda v: self._set(m, 'line_width', float(v)), .01, 1, .01))
            self.form.addRow('Rotation [deg]', self._dbl(getattr(m, 'rotation', 0), lambda v, model=m: self._set_body_rotation_90(model, v), 0, 270, 90))
            self.form.addRow('Color', self._color_button_row('Color RGB', getattr(m, 'color', (0, 0, 0)), lambda _checked=False, model=m: self.color_model(model)))
            self.form.addRow(QLabel('<b>Displayed Attributes</b>'))
            for k in list(m.attributes.keys()):
                row=QWidget(); l=QHBoxLayout(row); l.setContentsMargins(0,0,0,0)
                cb=QCheckBox('visible'); cb.setChecked(m.visible_attributes.get(k, False)); ed=QLineEdit(m.attributes.get(k,''))
                cb.toggled.connect(lambda v, key=k: self._set_attr_vis(key, v)); ed.textChanged.connect(lambda *_: setattr(self, 'dirty', True)); ed.editingFinished.connect(lambda key=k, e=ed: self._set_attr_val(key, e.text()))
                l.addWidget(cb); l.addWidget(ed); self.form.addRow(k, row)
        elif kind == 'PIN':
            for lab, attr in [('Number', 'number'), ('Name', 'name'), ('Function', 'function')]: self.form.addRow(lab, self._line(getattr(m, attr), lambda v, a=attr: self._set(m, a, v)))
            self.form.addRow('Pin Type', self._combo([x.value for x in PinType], m.pin_type, lambda v: self._set(m, 'pin_type', v)))
            self.form.addRow('Side', self._combo([x.value for x in PinSide], m.side, lambda v: self._set_pin_side(m, v)))
            inv=QCheckBox(); inv.setChecked(m.inverted); inv.toggled.connect(lambda v: self._set(m, 'inverted', v)); self.form.addRow('Inverted', inv)
            self.form.addRow(QLabel('<b>PIN Attributes</b>'))
            for label, attr in [('Show Number', 'visible_number'), ('Show Name', 'visible_name'), ('Show Function', 'visible_function')]:
                cb = QCheckBox(); cb.setChecked(getattr(m, attr)); cb.toggled.connect(lambda v, a=attr: self._set(m, a, v)); self.form.addRow(label, cb)
            self.form.addRow('Length', self._dbl(m.length, lambda v: self._set(m, 'length', v), 0.5, 100))
            self.form.addRow('Color', self._color_button_row('Color RGB', getattr(m, 'color', (0, 0, 0)), lambda _checked=False, model=m: self.color_model(model)))
            self.form.addRow('Number font', self._font_combo(m.number_font.family, lambda v: self._set(m.number_font, 'family', v)))
            self.form.addRow('Label font', self._font_combo(m.label_font.family, lambda v: self._set(m.label_font, 'family', v)))
            # Custom/imported pin attributes are owned by this pin, not by the body.
            self.form.addRow(QLabel('<b>Custom Pin Attributes</b>'))
            for k in sorted((getattr(m, 'attributes', {}) or {}).keys()):
                if str(k).upper() in {'#','NAME','PIN / FUNC','PINTYPE'}:
                    continue
                row=QWidget(); l=QHBoxLayout(row); l.setContentsMargins(0,0,0,0)
                cb=QCheckBox('visible'); cb.setChecked((getattr(m, 'visible_attributes', {}) or {}).get(k, False))
                ed=QLineEdit(str((getattr(m, 'attributes', {}) or {}).get(k, '')))
                cb.toggled.connect(lambda v, key=k, model=m: self._set_pin_custom_attr_visible(model, key, v))
                ed.returnPressed.connect(lambda key=k, model=m, e=ed: self._set_pin_custom_attr_value(model, key, e.text()))
                ed.editingFinished.connect(lambda key=k, model=m, e=ed: self._set_pin_custom_attr_value(model, key, e.text()))
                l.addWidget(cb); l.addWidget(ed)
                row.setContextMenuPolicy(Qt.CustomContextMenu)
                row.customContextMenuRequested.connect(lambda pos, pin=m, key=k, widget=row: self._pin_attribute_context_menu(pin, key, widget, pos))
                cb.setContextMenuPolicy(Qt.CustomContextMenu)
                cb.customContextMenuRequested.connect(lambda pos, pin=m, key=k, widget=cb: self._pin_attribute_context_menu(pin, key, widget, pos))
                ed.setContextMenuPolicy(Qt.CustomContextMenu)
                ed.customContextMenuRequested.connect(lambda pos, pin=m, key=k, widget=ed: self._pin_attribute_context_menu(pin, key, widget, pos))
                self.form.addRow(k, row)
            add_pin_attr_btn = QPushButton('Add Pin Attribute')
            add_pin_attr_btn.clicked.connect(lambda _checked=False, pin=m: self._add_pin_attribute_dialog(pin))
            self.form.addRow('', add_pin_attr_btn)
        elif kind in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY'):
            is_attr = kind in ('ATTR_REF_DES', 'ATTR_BODY') or bool(getattr(m, '_is_attribute_text', False))
            line = self._line(m.text, lambda v, item=item: self._set_text_item_attr(item, 'text', v)) if is_attr else self._plain_text_editor(m.text, lambda v, item=item: self._set_text_item_attr(item, 'text', v))
            if is_attr:
                line.setReadOnly(True)
                line.setToolTip('Attribute text content is driven by the owning object attribute value.')
            self.form.addRow('Text content', line)
            self.form.addRow('Font', self._font_combo(m.font_family, lambda v, item=item: self._set_text_item_attr(item, 'font_family', v)))
            self.form.addRow('Style', self._text_style_row(m, lambda a, v, it=item: self._set_text_item_attr(it, a, v)))
            self.form.addRow('Size grid', self._dbl(m.font_size_grid, lambda v, item=item: self._set_text_item_attr(item, 'font_size_grid', v), .1, 10))
            self.form.addRow('Horizontal grid anchor', self._combo(['left','center','right'], getattr(m, 'h_align', 'left'), lambda v, item=item: self._set_text_item_attr(item, 'h_align', v)))
            self.form.addRow('Vertical grid anchor', self._combo(['upper','center','lower'], getattr(m, 'v_align', 'upper'), lambda v, item=item: self._set_text_item_attr(item, 'v_align', v)))
            if is_attr:
                self.form.addRow('Wrap text', self._check(getattr(m, 'wrap_text', False), lambda v, item=item: self._set_text_item_attr(item, 'wrap_text', v)))
            else:
                self.form.addRow('Line break', QLabel('Shift+Enter in canvas / text field'))
            self.form.addRow('Rotation [deg]', self._dbl(getattr(m, 'rotation', 0), lambda v, item=item: self._set_text_item_attr(item, 'rotation', v), -360, 360, 15))
            self.form.addRow('Color', self._color_button_row('Color RGB', getattr(m, 'color', (0, 0, 0)), lambda _checked=False, item=item: self.color_text_item(item)))
        elif kind == 'GRAPHIC':
            self.form.addRow('Shape', self._combo(['line','rect','ellipse'], m.shape, lambda v, model=m: self._set_graphic_shape_and_refresh(model, v)))
            self.form.addRow('X', self._dbl(m.x, lambda v: self._set(m, 'x', round(float(v))), -500, 500, 1))
            self.form.addRow('Y', self._dbl(m.y, lambda v: self._set(m, 'y', round(float(v))), -500, 500, 1))
            self.form.addRow('Width', self._dbl(m.w, lambda v: self._set(m, 'w', round(float(v))), -500, 500, 1))
            self.form.addRow('Height', self._dbl(m.h, lambda v: self._set(m, 'h', round(float(v))), -500, 500, 1))
            if m.shape == 'line':
                self.form.addRow('Curve radius', self._dbl(getattr(m, 'curve_radius', 0), lambda v: self._set(m, 'curve_radius', v), -100, 100, .1))
            self.form.addRow('Rotation [deg]', self._dbl(getattr(m, 'rotation', 0), lambda v: self._set(m, 'rotation', v), -360, 360, 15))
            self.form.addRow('Color', self._color_button_row('Stroke RGB', getattr(m.style, 'stroke', (0, 0, 0)), lambda _checked=False, style=m.style: self.color_model(style, 'stroke')))

    def _set_pin_custom_attr_visible(self, pin, key, visible):
        self.push_undo_state()
        pin.visible_attributes[key] = bool(visible)
        if bool(visible) and key not in getattr(pin, 'attribute_texts', {}):
            if not hasattr(pin, 'attribute_texts') or pin.attribute_texts is None:
                pin.attribute_texts = {}
            pin.attribute_texts[key] = TextModel(text=f"{key}: {pin.attributes.get(key, '')}" if str(pin.attributes.get(key, '')).strip() else str(key), x=pin.x, y=pin.y - 1, font_size_grid=.45)
        self.dirty = True
        self.rebuild_scene()

    def _set_pin_custom_attr_value(self, pin, key, value):
        self.push_undo_state()
        pin.attributes[key] = value
        tm = (getattr(pin, 'attribute_texts', {}) or {}).get(key)
        if tm is not None:
            tm.text = f'{key}: {value}' if str(value).strip() else str(key)
        self.dirty = True
        self.rebuild_scene()

    def _add_pin_attribute_dialog(self, pin):
        dlg = QDialog(self)
        dlg.setWindowTitle('Add Pin Attribute')
        layout = QFormLayout(dlg)
        name_edit = QLineEdit(); value_edit = QLineEdit(); visible_cb = QCheckBox('visible'); visible_cb.setChecked(True)
        layout.addRow('Name', name_edit); layout.addRow('Value', value_edit); layout.addRow('Visibility', visible_cb)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); layout.addRow(buttons)
        def accept_if_valid():
            name = name_edit.text().strip()
            if not name:
                QMessageBox.warning(dlg, 'Pin Attribute', 'Bitte einen Attributnamen eingeben.'); return
            if name in (getattr(pin, 'attributes', {}) or {}):
                QMessageBox.warning(dlg, 'Pin Attribute', f'Das Attribut "{name}" existiert bereits.'); return
            dlg.accept()
        buttons.accepted.connect(accept_if_valid); buttons.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.Accepted:
            return
        name = name_edit.text().strip(); value = value_edit.text(); visible = visible_cb.isChecked()
        self.push_undo_state()
        if getattr(pin, 'attributes', None) is None: pin.attributes = {}
        if getattr(pin, 'visible_attributes', None) is None: pin.visible_attributes = {}
        if getattr(pin, 'attribute_texts', None) is None: pin.attribute_texts = {}
        pin.attributes[name] = value; pin.visible_attributes[name] = visible
        if visible:
            pin.attribute_texts[name] = TextModel(text=f'{name}: {value}' if str(value).strip() else str(name), x=pin.x, y=pin.y - 1, font_size_grid=.45)
        self._selection_restore_ids = {id(pin)}
        self.update_current_unit_canvas_positions()
        QTimer.singleShot(0, self.refresh_properties)

    def _delete_pin_attribute(self, pin, key):
        if key not in (getattr(pin, 'attributes', {}) or {}):
            return
        self.push_undo_state()
        try: pin.attributes.pop(key, None)
        except Exception: pass
        try: pin.visible_attributes.pop(key, None)
        except Exception: pass
        try: pin.attribute_texts.pop(key, None)
        except Exception: pass
        self._selection_restore_ids = {id(pin)}
        self.update_current_unit_canvas_positions()
        QTimer.singleShot(0, self.refresh_properties)

    def _pin_attribute_context_menu(self, pin, key, widget, pos):
        menu = QMenu(self)
        delete_action = QAction('Delete Pin Attribute', self)
        delete_action.triggered.connect(lambda _checked=False, p=pin, k=key: self._delete_pin_attribute(p, k))
        menu.addAction(delete_action)
        try: menu.exec(widget.mapToGlobal(pos))
        except Exception: menu.exec(QCursor.pos())

    def rebuild_props(self):
        """Compatibility wrapper for older callbacks: rebuild the property panel."""
        return self.refresh_properties()

    def _pin_model_from_object(self, obj):
        if obj is None:
            return None
        try:
            if isinstance(obj, PinModel):
                return obj
        except Exception:
            pass
        try:
            if all(hasattr(obj, name) for name in ('number', 'side', 'length', 'pin_type')):
                return obj
        except Exception:
            pass
        try:
            if obj.data(0) == 'PIN':
                return getattr(obj, 'model', None)
        except RuntimeError:
            return None
        except Exception:
            return None
        return None

    def _pin_models_from_objects(self, objects, require_all=False):
        source = list(objects or [])
        pins = []
        for obj in source:
            model = self._pin_model_from_object(obj)
            if model is not None:
                pins.append(model)
        if require_all and source and len(pins) != len(source):
            return []
        result = []
        seen = set()
        for pin in pins:
            ident = id(pin)
            if ident not in seen:
                result.append(pin)
                seen.add(ident)
        return result

    def _selected_pin_models(self):
        try:
            pins = self._pin_models_from_objects(self.scene.selectedItems())
            if pins:
                return pins
        except Exception:
            pass
        ids = set(getattr(self, '_selection_restore_ids', set()) or set())
        try:
            return [p for p in getattr(self.unit, 'pins', []) or [] if id(p) in ids]
        except Exception:
            return []

    def _commit_line_edit(self, value, fn, force_first_commit=False):
        w = QLineEdit(str(value))
        w._symbol_wizard_last_committed = str(value)
        w._symbol_wizard_force_first_commit = bool(force_first_commit)
        w._symbol_wizard_commit_count = 0
        def commit(widget=w):
            text = widget.text()
            first_forced = bool(getattr(widget, '_symbol_wizard_force_first_commit', False)) and int(getattr(widget, '_symbol_wizard_commit_count', 0) or 0) == 0
            if not first_forced and getattr(widget, '_symbol_wizard_last_committed', None) == text:
                try: widget.clearFocus()
                except Exception: pass
                return
            widget._symbol_wizard_last_committed = text
            widget._symbol_wizard_commit_count = int(getattr(widget, '_symbol_wizard_commit_count', 0) or 0) + 1
            fn(text)
            try: widget.clearFocus()
            except Exception: pass
        w.returnPressed.connect(commit)
        w.editingFinished.connect(commit)
        return w


    def _selection_title_label(self, kind, item=None):
        pretty = {
            'BODY': 'Body',
            'PIN': 'Pin',
            'TEXT': 'Plain Text',
            'ATTR_REF_DES': 'Attribute Text',
            'ATTR_BODY': 'Attribute Text',
            'GRAPHIC': 'Graphic',
        }.get(kind, str(kind).replace('_', ' ').title())
        details = ''
        model = getattr(item, 'model', None)
        if kind == 'TEXT' and model is not None:
            try:
                preview = str(getattr(model, 'text', '') or '').strip().replace('\n', ' ')
                if preview:
                    details = f'<br><span style="color:#666; font-size:10px;">{preview[:48]}</span>'
            except Exception:
                pass
        label = QLabel(f'<div style="font-size:14px;"><b>{pretty}</b>{details}</div>')
        label.setTextFormat(Qt.RichText)
        return label

    def _text_style_row(self, model_or_items, setter, multi=False):
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        items = list(model_or_items or []) if multi else []
        for title, attr in [('Bold', 'bold'), ('Italic', 'italic'), ('Underline', 'underline')]:
            cb = QCheckBox(title)
            if multi:
                cb.setTristate(True)
                vals = [bool(getattr(getattr(i, 'model', None), attr, False)) for i in items if getattr(i, 'model', None) is not None]
                if vals and all(v is True for v in vals):
                    cb.setCheckState(Qt.Checked)
                elif vals and all(v is False for v in vals):
                    cb.setCheckState(Qt.Unchecked)
                else:
                    cb.setCheckState(Qt.PartiallyChecked)
                def on_state_changed(state, a=attr):
                    if state == Qt.PartiallyChecked or state == getattr(Qt.CheckState.PartiallyChecked, 'value', 1):
                        return
                    setter(a, state == Qt.Checked or state == getattr(Qt.CheckState.Checked, 'value', 2))
                cb.stateChanged.connect(on_state_changed)
            else:
                cb.setChecked(bool(getattr(model_or_items, attr, False)))
                cb.toggled.connect(lambda v, a=attr: setter(a, v))
            lay.addWidget(cb)
        lay.addStretch(1)
        return row

    def _line(self, value, fn):
        return self._commit_line_edit(value, fn)
    def _plain_text_editor(self, value, fn):
        w = QTextEdit(str(value))
        w.setAcceptRichText(False)
        w.setFixedHeight(72)
        w._symbol_wizard_last_committed = str(value)
        old_key_press = w.keyPressEvent
        def commit(editor=w):
            text = editor.toPlainText()
            if getattr(editor, '_symbol_wizard_last_committed', None) != text:
                editor._symbol_wizard_last_committed = text
                fn(text)
            try: editor.clearFocus()
            except Exception: pass
        def key_press(event, editor=w):
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
                commit(editor)
                event.accept()
                return
            old_key_press(event)
        w.keyPressEvent = key_press
        return w
    def _dbl(self, value, fn, lo=-999, hi=999, step=.1):
        w = QDoubleSpinBox()
        w.setRange(lo, hi)
        w.setDecimals(3)
        w.setSingleStep(step)
        w.setKeyboardTracking(False)
        # Setting the initial value must not trigger model writes while the
        # property panel is still being rebuilt.
        w.blockSignals(True)
        w.setValue(float(value))
        w.blockSignals(False)
        w.valueChanged.connect(lambda v: fn(float(v)))
        return w
    def _combo(self, items, val, fn):
        w = QComboBox()
        w.blockSignals(True)
        w.addItems(items)
        w.setCurrentText(str(val))
        w.blockSignals(False)
        # Defer model writes until the combo has finished processing its own
        # signal. This avoids editor destruction/re-entrancy crashes in the
        # property panel for imported/template symbols.
        w.currentTextChanged.connect(lambda v, cb=fn: QTimer.singleShot(0, lambda val=v: cb(val)))
        return w
    def _check(self, value, fn):
        w = QCheckBox()
        w.blockSignals(True)
        w.setChecked(bool(value))
        w.blockSignals(False)
        w.toggled.connect(lambda v, cb=fn: QTimer.singleShot(0, lambda val=bool(v): cb(val)))
        return w
    def _color_button_row(self, button_text, color, callback):
        row = QWidget(); lay = QHBoxLayout(row); lay.setContentsMargins(0, 0, 0, 0)
        btn = QPushButton(button_text); btn.clicked.connect(callback)
        swatch = QFrame(); swatch.setFixedSize(24, 18); swatch.setFrameShape(QFrame.Box)
        r, g, b = color or (0, 0, 0)
        swatch.setStyleSheet(f'background-color: rgb({int(r)}, {int(g)}, {int(b)}); border: 1px solid #555;')
        lay.addWidget(btn); lay.addWidget(swatch); lay.addStretch(1)
        return row

    def _current_color_for_selection(self):
        selected = list(self.scene.selectedItems()) if hasattr(self, 'scene') else []
        colors = []
        for it in selected:
            m = getattr(it, 'model', None)
            if m is None:
                continue
            k = it.data(0)
            if k == 'GRAPHIC':
                colors.append(getattr(getattr(m, 'style', None), 'stroke', (0, 0, 0)))
            else:
                colors.append(getattr(m, 'color', (0, 0, 0)))
        if colors and all(c == colors[0] for c in colors):
            return colors[0]
        return getattr(self, 'default_color', (0, 0, 0))

    def apply_color_to_selected(self, color):
        selected = list(self.scene.selectedItems()) if hasattr(self, 'scene') else []
        if not selected:
            self.default_color = color
            return
        self.push_undo_state()
        self._selection_restore_ids = {id(getattr(i, 'model', None)) for i in selected if getattr(i, 'model', None) is not None}
        for it in selected:
            m = getattr(it, 'model', None)
            if m is None:
                continue
            k = it.data(0)
            if k == 'GRAPHIC':
                m.style.stroke = color
            elif k in ('BODY', 'PIN', 'TEXT', 'ATTR_REF_DES', 'ATTR_BODY'):
                m.color = color
                if hasattr(it, 'apply_text_from_model'):
                    it.apply_text_from_model()
        self.update_current_unit_canvas_positions()
        self.refresh_properties()
    def _multi_pin_visibility_checkbox(self, pin_items, attr):
        pins = self._pin_models_from_objects(pin_items, require_all=False)
        values = [bool(getattr(p, attr, False)) for p in pins]
        cb = QCheckBox()
        cb.setTristate(True)
        cb.blockSignals(True)
        if values and all(values):
            cb.setCheckState(Qt.Checked)
        elif values and not any(values):
            cb.setCheckState(Qt.Unchecked)
        else:
            cb.setCheckState(Qt.PartiallyChecked)
        cb.blockSignals(False)
        cb.stateChanged.connect(lambda state, a=attr, models=tuple(pins): self._apply_multi_pin_visibility_state(models, a, state))
        return cb

    def _common_model_value(self, items, attr, default=''):
        vals = [getattr(getattr(i, 'model', None), attr, default) for i in items if getattr(i, 'model', None) is not None]
        if not vals:
            return default
        first = vals[0]
        return first if all(v == first for v in vals) else default



    def _common_pin_value(self, items, attr, default=''):
        vals = [getattr(pin, attr, default) for pin in self._pin_models_from_objects(items, require_all=False)]
        if not vals:
            return default
        first = vals[0]
        return first if all(v == first for v in vals) else default

    def _common_pin_font_value(self, pins, font_attr, attr, default=''):
        vals = []
        for pin in self._pin_models_from_objects(pins, require_all=False):
            font = getattr(pin, font_attr, None)
            if font is not None:
                vals.append(getattr(font, attr, default))
        if not vals:
            return default
        first = vals[0]
        return first if all(v == first for v in vals) else '<multiple>'

    def _pin_font_combo(self, pins, font_attr, attr, callback):
        value = self._common_pin_font_value(pins, font_attr, attr, '')
        w = QComboBox()
        w.setEditable(True)
        w.blockSignals(True)
        if value == '<multiple>':
            w.addItem('<multiple>')
        for fam in self._font_families():
            if w.findText(fam) < 0:
                w.addItem(fam)
        w.setCurrentText(str(value if value else 'Arial'))
        w.blockSignals(False)
        def commit(value=None, box=w):
            text = str(value if value is not None else box.currentText()).strip()
            if not text or text == '<multiple>':
                return
            QTimer.singleShot(0, lambda txt=text: callback(txt))
        # currentTextChanged fires while the combo is rebuilding; defer the
        # model write so Qt does not destroy the active editor mid-signal.
        w.activated.connect(lambda *_: commit())
        try:
            w.lineEdit().editingFinished.connect(commit)
        except Exception:
            pass
        return w

    def _pin_font_size_spin(self, pins, font_attr, callback):
        value = self._common_pin_font_value(pins, font_attr, 'size_grid', '<multiple>')
        w = QDoubleSpinBox()
        w.setRange(0.0, 5.0)
        w.setDecimals(3)
        w.setSingleStep(0.05)
        w.setSuffix(' grid')
        w.setSpecialValueText('<multiple>')
        w.setKeyboardTracking(False)
        w.blockSignals(True)
        try:
            w.setValue(0.0 if value == '<multiple>' else float(value))
        except Exception:
            w.setValue(0.0)
        w.blockSignals(False)
        def commit(v):
            try:
                val = float(v)
            except Exception:
                return
            if val <= 0.0:
                return
            QTimer.singleShot(0, lambda value=val: callback(value))
        w.valueChanged.connect(commit)
        return w

    def _template_multi_pin_font_props(self, pin_items):
        pins = tuple(self._pin_models_from_objects(pin_items, require_all=False))
        if not pins:
            return
        self.form.addRow(QLabel('<b>PIN Attribute Fonts</b>'))
        self.form.addRow('Number font', self._pin_font_combo(pins, 'number_font', 'family', lambda v, models=pins: self._set_selected_pins_font_attr(models, 'number_font', 'family', v)))
        self.form.addRow('Number size [grid]', self._pin_font_size_spin(pins, 'number_font', lambda v, models=pins: self._set_selected_pins_font_attr(models, 'number_font', 'size_grid', float(v))))
        current = self._common_pin_font_value(pins, 'number_font', 'color', (0, 0, 0))
        self.form.addRow('Number color', self._color_button_row('Number Font RGB', (0,0,0) if current == '<multiple>' else (current or (0,0,0)), lambda _checked=False, models=pins: self._color_selected_pin_font(models, 'number_font')))
        self.form.addRow('Name/Function font', self._pin_font_combo(pins, 'label_font', 'family', lambda v, models=pins: self._set_selected_pins_font_attr(models, 'label_font', 'family', v)))
        self.form.addRow('Name/Function size [grid]', self._pin_font_size_spin(pins, 'label_font', lambda v, models=pins: self._set_selected_pins_font_attr(models, 'label_font', 'size_grid', float(v))))
        current = self._common_pin_font_value(pins, 'label_font', 'color', (0, 0, 0))
        self.form.addRow('Name/Function color', self._color_button_row('Label Font RGB', (0,0,0) if current == '<multiple>' else (current or (0,0,0)), lambda _checked=False, models=pins: self._color_selected_pin_font(models, 'label_font')))

    def _common_graphic_value(self, items, attr, default=''):
        vals = []
        for i in items:
            m = getattr(i, 'model', None)
            if m is None or i.data(0) != 'GRAPHIC':
                continue
            if attr in ('line_style', 'line_width'):
                vals.append(getattr(m.style, attr, default))
            else:
                vals.append(getattr(m, attr, default))
        if not vals:
            return default
        first = vals[0]
        return first if all(v == first for v in vals) else default

    def _template_multi_text_props(self, items):
        self.form.addRow('Font', self._font_combo(self._common_model_value(items, 'font_family', ''), lambda v, its=items: self._set_selected_text_attr(its, 'font_family', v)))
        def _multi_style_set(attr, value, its=items):
            self._set_selected_text_attr(its, attr, bool(value))
        self.form.addRow('Style', self._text_style_row(items, _multi_style_set, multi=True))
        self.form.addRow('Size grid', self._dbl(float(self._common_model_value(items, 'font_size_grid', 1.0) or 1.0), lambda v, its=items: self._set_selected_text_attr(its, 'font_size_grid', v), .1, 10, .1))
        self.form.addRow('Horizontal grid anchor', self._combo(['', 'left','center','right'], self._common_model_value(items, 'h_align', ''), lambda v, its=items: v and self._set_selected_text_attr(its, 'h_align', v)))
        self.form.addRow('Vertical grid anchor', self._combo(['', 'upper','center','lower'], self._common_model_value(items, 'v_align', ''), lambda v, its=items: v and self._set_selected_text_attr(its, 'v_align', v)))
        attr_items = [i for i in items if i.data(0) in ('ATTR_REF_DES', 'ATTR_BODY') or bool(getattr(getattr(i, 'model', None), '_is_attribute_text', False))]
        plain_items = [i for i in items if i.data(0) == 'TEXT' and i not in attr_items]
        if attr_items:
            self.form.addRow('Wrap text', self._check(bool(self._common_model_value(attr_items, 'wrap_text', False)), lambda v, its=attr_items: self._set_selected_text_attr(its, 'wrap_text', v)))
        if plain_items:
            self.form.addRow('Line break', QLabel('Plain text: Shift+Enter in canvas / text field'))
        self.form.addRow('Rotation [deg]', self._dbl(float(self._common_model_value(items, 'rotation', 0) or 0), lambda v, its=items: self._set_selected_text_attr(its, 'rotation', v), -360, 360, 15))
        self.form.addRow('Color', self._color_button_row('Color RGB', self._common_model_value(items, 'color', (0, 0, 0)) or (0, 0, 0), lambda _checked=False, its=items: self.color_selected_text(its)))
        row = QWidget(); lay = QHBoxLayout(row); lay.setContentsMargins(0,0,0,0)
        for label, fn in [('Align L', lambda _checked=False, its=items: self.align_text_objects(its, 'left')), ('Align C', lambda _checked=False, its=items: self.align_text_objects(its, 'center')), ('Align R', lambda _checked=False, its=items: self.align_text_objects(its, 'right')), ('Align Top', lambda _checked=False, its=items: self.align_text_objects(its, 'upper')), ('Align Mid', lambda _checked=False, its=items: self.align_text_objects(its, 'middle')), ('Align Bottom', lambda _checked=False, its=items: self.align_text_objects(its, 'lower'))]:
            b=QPushButton(label); b.clicked.connect(fn); lay.addWidget(b)
        self.form.addRow('Arrange', row)
        row2 = QWidget(); lay2 = QHBoxLayout(row2); lay2.setContentsMargins(0,0,0,0)
        for label, fn in [('Distribute H', lambda _checked=False, its=items: self.distribute_text_objects(its, 'h')), ('Distribute V', lambda _checked=False, its=items: self.distribute_text_objects(its, 'v'))]:
            b=QPushButton(label); b.clicked.connect(fn); lay2.addWidget(b)
        self.form.addRow('Distribute', row2)

    def pick_default_color(self):
        current = self._current_color_for_selection() if hasattr(self, '_current_color_for_selection') else self.default_color
        c = QColorDialog.getColor(QColor(*current), self)
        if c.isValid():
            self.apply_color_to_selected((c.red(), c.green(), c.blue()))

    def color_model(self, m, attr='color'):
        current = getattr(m, attr, (0, 0, 0)) or (0, 0, 0)
        c = QColorDialog.getColor(QColor(*current), self)
        if not c.isValid():
            return
        self.push_undo_state()
        setattr(m, attr, (c.red(), c.green(), c.blue()))
        self.update_current_unit_canvas_positions(); self.refresh_properties()

    def color_text_item(self, item):
        self.push_undo_state()
        c = QColorDialog.getColor(QColor(*getattr(item.model, 'color', (0, 0, 0))), self)
        if c.isValid():
            item.model.color = (c.red(), c.green(), c.blue())
            if hasattr(item, 'apply_text_from_model'):
                item.apply_text_from_model()
            self.update_current_unit_canvas_positions(); self.refresh_properties()

    def color_selected_text(self, items):
        current = self._common_model_value(items, 'color', (0, 0, 0)) or (0, 0, 0)
        c = QColorDialog.getColor(QColor(*current), self)
        if not c.isValid():
            return
        self.push_undo_state()
        value = (c.red(), c.green(), c.blue())
        self._selection_restore_ids = {id(i.model) for i in items if getattr(i, 'model', None) is not None}
        for item in items:
            if item.data(0) in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY'):
                item.model.color = value
                if hasattr(item, 'apply_text_from_model'):
                    item.apply_text_from_model()
        self.update_current_unit_canvas_positions(); self.refresh_properties()

    def color_selected_pins(self, items):
        current = self._common_pin_value(items, 'color', (0, 0, 0)) or (0, 0, 0)
        c = QColorDialog.getColor(QColor(*current), self)
        if not c.isValid():
            return
        value = (c.red(), c.green(), c.blue())
        self._set_selected_pins_attr(items, 'color', value)

    def _set_text_item_attr(self, item, attr, value):
        if item.data(0) in ('ATTR_REF_DES', 'ATTR_BODY') and attr == 'text':
            return
        self.push_undo_state()
        self._selection_restore_ids = {id(item.model)}
        if attr == 'rotation':
            value = (round(float(value) / 15.0) * 15.0) % 360
        setattr(item.model, attr, value)
        if attr in ('h_align', 'v_align'):
            self._snap_text_anchor_to_grid(item)
        if hasattr(item, 'apply_text_from_model'):
            item.apply_text_from_model()
        elif attr == 'text':
            item.setPlainText(value)
        self.update_current_unit_canvas_positions()

    def _set_selected_text_attr(self, items, attr, value):
        models = [getattr(i, 'model', None) for i in items if i.data(0) in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY')]
        if not models or len(models) != len(items) or attr == 'text':
            return
        self.push_undo_state()
        if attr == 'rotation':
            value = (round(float(value) / 15.0) * 15.0) % 360
        self._selection_restore_ids = {id(m) for m in models}
        for item in items:
            setattr(item.model, attr, value)
            if attr in ('h_align', 'v_align'):
                self._snap_text_anchor_to_grid(item)
            if hasattr(item, 'apply_text_from_model'):
                item.apply_text_from_model()
        self.update_current_unit_canvas_positions()
    def _set(self, m, a, v):
        self.push_undo_state()
        self._selection_restore_ids = {id(m)}
        if a == 'rotation':
            v = (round(float(v) / 15.0) * 15.0) % 360
        setattr(m, a, v)
        # Do not rebuild the whole scene synchronously from spin-box arrows or
        # combo-box signals.  Qt can otherwise destroy the editor widget while
        # it is still handling its own signal, which caused crashes in the
        # Template Editor BODY width/height/rotation controls.
        self.update_current_unit_canvas_positions()
        QTimer.singleShot(0, self.refresh_properties)

    def _set_graphic_shape_and_refresh(self, m, v):
        # Shape-specific controls (e.g. curve radius for lines) must appear
        # after the dropdown changes, but deferred so the combo signal can
        # finish safely.
        self._set(m, 'shape', v)
    def _set_pin_side(self, m, v):
        self.push_undo_state(); self._selection_restore_ids={id(m)}; m.side=v; self.dock_pins_to_body(self.unit); self.rebuild_scene()
    def _apply_multi_pin_visibility_choice(self, pin_items, attr, index):
        # 0 = unchanged, 1 = hidden/False, 2 = visible/True
        if int(index) == 0:
            return
        self._set_selected_pins_attr(pin_items, attr, int(index) == 2)

    def _apply_multi_pin_visibility_state(self, pin_items, attr, state):
        # Backward-compatible handler for older tristate widgets. PySide may pass
        # either an int or a Qt.CheckState enum, so compare defensively.
        value = getattr(state, 'value', state)
        if value == getattr(Qt.CheckState.PartiallyChecked, 'value', 1) or value == 1:
            return
        self._set_selected_pins_attr(pin_items, attr, value == getattr(Qt.CheckState.Checked, 'value', 2) or value == 2)

    def _set_selected_pins_font_attr(self, pin_items, font_attr, attr, value):
        pins = self._pin_models_from_objects(pin_items, require_all=False)
        if not pins or font_attr not in ('number_font', 'label_font') or attr not in ('family', 'size_grid', 'color'):
            return
        self.push_undo_state(); self._selection_restore_ids = {id(p) for p in pins}
        for pin in pins:
            font = getattr(pin, font_attr, None)
            if font is not None:
                setattr(font, attr, value)
        self.rebuild_scene(); self.refresh_properties()

    def _color_selected_pin_font(self, pin_items, font_attr):
        current = self._common_pin_font_value(pin_items, font_attr, 'color', (0, 0, 0)) or (0, 0, 0)
        c = QColorDialog.getColor(QColor(*current), self)
        if not c.isValid():
            return
        self._set_selected_pins_font_attr(pin_items, font_attr, 'color', (c.red(), c.green(), c.blue()))

    def _set_selected_pins_attr(self, pin_items, attr, value):
        pins = self._pin_models_from_objects(pin_items, require_all=False)
        if not pins:
            pins = self._selected_pin_models()
        if not pins: return
        if attr not in ('function', 'visible_number', 'visible_name', 'visible_function', 'length', 'line_style', 'line_width', 'color', 'pin_type'): return
        self.push_undo_state(); self._selection_restore_ids={id(p) for p in pins}
        for p in pins: setattr(p, attr, value)
        self.rebuild_scene()

    def _set_selected_graphics_style(self, graphic_items, attr, value):
        graphics = [getattr(i, 'model', None) for i in graphic_items if getattr(i, 'model', None) is not None and i.data(0) == 'GRAPHIC']
        if not graphics or len(graphics) != len(graphic_items) or attr not in ('line_width', 'line_style'):
            return
        self.push_undo_state(); self._selection_restore_ids = {id(g) for g in graphics}
        for g in graphics:
            setattr(g.style, attr, value)
        self.update_current_unit_canvas_positions()
        self.refresh_properties()

    def _set_attr_vis(self, key, val):
        self.push_undo_state()
        self._selection_restore_ids = self._capture_selection_ids()
        self.unit.body.visible_attributes[key] = bool(val)
        self.update_attribute_items_for_unit()
        QTimer.singleShot(0, self.refresh_properties)

    def _set_attr_val(self, key, val):
        self.push_undo_state()
        self._selection_restore_ids = self._capture_selection_ids()
        self.unit.body.attributes[key] = val
        self.update_attribute_items_for_unit()
        QTimer.singleShot(0, self.refresh_properties)



    def _body_graphics_are_locked(self, unit) -> bool:
        """True when a unit's graphics originate from a template/Mentor body.

        In the normal Symbol Wizard these graphic primitives are the visible BODY,
        not standalone user graphics.  They may only be edited in the Template
        Editor.  This is especially important for split-symbol templates loaded
        through the fast manifest path, where older cached JSON still contains
        locked_to_body=false on the primitive records.
        """
        try:
            attrs = getattr(getattr(unit, 'body', None), 'attributes', {}) or {}
            if str(attrs.get('MENTOR_GRAPHICS_AS_BODY', '0')) == '1':
                return True
            if str(attrs.get('MENTOR_BODY_GRAPHICS_LOCKED', '0')) == '1':
                return True
            if str(attrs.get('MENTOR_HAS_BODY', '0')) == '1':
                return True
            if str(attrs.get('TEMPLATE_GRAPHICS_AS_BODY', '0')) == '1':
                return True
        except Exception:
            pass
        return False

    def _lock_template_body_graphics(self, unit):
        """Normalize template/import body artwork without locking user graphics.

        A unit may contain two different graphic classes:
        - template_body: artwork from Template Editor / Mentor import; it is the BODY
          in the Symbol Wizard and is not individually selectable there.
        - user_graphic: graphic objects drawn later in the Symbol Wizard; these stay
          normal selectable/editable GRAPHIC objects.

        Older templates only had body-level flags such as TEMPLATE_GRAPHICS_AS_BODY.
        For those legacy records, unmarked graphics are migrated to template_body.
        User-created graphics are explicitly marked when created/pasted and are
        therefore never re-locked by this migration.
        """
        try:
            if self._body_graphics_are_locked(unit):
                for _g in getattr(unit, 'graphics', []) or []:
                    try:
                        role = str(getattr(_g, 'graphic_role', '') or '')
                        marker = str(getattr(_g, 'mentor_raw', '') or '')
                        if role == 'user_graphic' or marker == '__USER_GRAPHIC__':
                            _g.graphic_role = 'user_graphic'
                            _g.locked_to_body = False
                        else:
                            _g.graphic_role = 'template_body'
                            _g.locked_to_body = True
                    except Exception:
                        pass
        except Exception:
            pass
        return unit

    def _capture_selection_ids(self):
        return {id(getattr(i, 'model', None)) for i in self.scene.selectedItems() if getattr(i, 'model', None) is not None}

    def _restore_item_selection(self, item, selected_ids):
        model = getattr(item, 'model', None)
        if model is not None and id(model) in selected_ids:
            item.setSelected(True)

    def apply_item_selectability(self, item):
        kind = item.data(0)
        filter_kind = selection_filter_kind_for_item(item)
        selectable = is_selection_enabled_for_item(item, self.selection_enabled)
        # Imported Mentor/template body graphics are a single locked body group in the Symbol Wizard.
        # They are only editable in the Template Editor.
        if kind == 'GRAPHIC' and getattr(getattr(item, 'model', None), 'locked_to_body', False) and not getattr(self, 'is_template_editor', False):
            selectable = False
        item.setFlag(QGraphicsItem.ItemIsSelectable, selectable)
        # Attribute text is content-locked but can still be moved/rotated/font-aligned when ATTRIBUTES is selectable.
        item.setFlag(QGraphicsItem.ItemIsMovable, selectable)
        try:
            item.setAcceptedMouseButtons(Qt.AllButtons if selectable else Qt.NoButton)
        except Exception:
            pass
        if not selectable:
            item.setSelected(False)
        z = {'BODY': 0, 'BODY_GRAPHIC': 0, 'GRAPHIC': 1, 'TEXT': 2, 'ATTR_REF_DES': 2, 'ATTR_BODY': 2, 'PIN': 3}.get(kind, -1)
        item.setZValue(z)

    def _apply_selection_filter_to_scene(self):
        """Apply the current object-type selection filter to all canvas items."""
        self.selection_enabled = normalize_selection_enabled(getattr(self, 'selection_enabled', None))
        for item in self.scene.items():
            filter_kind = selection_filter_kind_for_item(item)
            if filter_kind in SELECTION_FILTER_KEYS:
                self.apply_item_selectability(item)
                if not is_selection_enabled_for_item(item, self.selection_enabled):
                    item.setSelected(False)

    def set_selection_mode(self, mode):
        mode = str(mode or 'ALL')
        custom = (mode == 'Custom')
        if hasattr(self, 'selection_custom_checks'):
            for kind, cb in self.selection_custom_checks.items():
                cb.setVisible(custom)
                # QToolBar.addWidget wraps widgets in QWidgetAction; changing
                # only the checkbox visibility is not enough on some Qt styles.
                if hasattr(self, 'selection_custom_actions') and kind in self.selection_custom_actions:
                    self.selection_custom_actions[kind].setVisible(custom)
        if mode == 'Custom':
            if hasattr(self, 'selection_custom_checks'):
                for kind, cb in self.selection_custom_checks.items():
                    self.selection_enabled[kind] = cb.isChecked()
            self.selection_enabled = normalize_selection_enabled(getattr(self, 'selection_enabled', None))
            self._apply_selection_filter_to_scene()
            self.refresh_properties()
            return
        self.selection_enabled.update(selection_flags_for_mode(mode))
        if hasattr(self, 'selection_custom_checks'):
            for kind, cb in self.selection_custom_checks.items():
                cb.blockSignals(True)
                cb.setChecked(bool(self.selection_enabled.get(kind, False)))
                cb.blockSignals(False)
        self._apply_selection_filter_to_scene()
        self.refresh_properties()

    def set_selection_enabled(self, kind, checked):
        self.selection_enabled = normalize_selection_enabled(getattr(self, 'selection_enabled', None))
        self.selection_enabled[kind] = bool(checked)
        if hasattr(self, 'selection_mode_combo') and self.selection_mode_combo.currentText() != 'Custom':
            self.selection_mode_combo.blockSignals(True)
            self.selection_mode_combo.setCurrentText('Custom')
            self.selection_mode_combo.blockSignals(False)
            if hasattr(self, 'selection_custom_checks'):
                for key, cb in self.selection_custom_checks.items():
                    cb.setVisible(True)
                    if hasattr(self, 'selection_custom_actions') and key in self.selection_custom_actions:
                        self.selection_custom_actions[key].setVisible(True)
        self._apply_selection_filter_to_scene()
        self.refresh_properties()

    def add_attribute_text_items(self, u):
        """Create selectable, transformable and persistent text items for body attributes.

        Attribute texts are owned by BODY. Their coordinates are stored in
        body.attribute_texts so they can be moved/aligned manually and still stay
        attached when BODY is resized or scaled.
        """
        b = u.body

        def attr_model(key: str, default_text: str, default_x: float, default_y: float, font, default_h='left', default_v='upper'):
            tm = _text_model_from_any(b.attribute_texts.get(key), default_text, default_x, default_y, font, default_h, default_v)
            b.attribute_texts[key] = tm
            tm.text = default_text
            if not getattr(tm, 'font_family', ''):
                tm.font_family = str(_font_value(font, 'family', 'Arial'))
            if not getattr(tm, 'font_size_grid', 0):
                tm.font_size_grid = float(_font_value(font, 'size_grid', 0.75))
            if not getattr(tm, 'color', None):
                tm.color = tuple(_font_value(font, 'color', (0, 0, 0)))
            tm._is_attribute_text = True
            tm._attribute_key = key
            return tm

        ref = b.attributes.get('RefDes', '')
        if b.visible_attributes.get('RefDes', False):
            label = ref if str(ref).strip() else 'RefDes'
            tm = attr_model('RefDes', label, b.x, b.y + 1, b.refdes_font, getattr(b, 'refdes_align', 'left'), 'lower')
            txt = TextItem(tm, self)
            txt.setData(0, 'ATTR_REF_DES')
            self.apply_item_selectability(txt)
            self.scene.addItem(txt)

        row = 1
        for k, v in b.attributes.items():
            if k == 'RefDes' or not b.visible_attributes.get(k, False):
                continue
            label = f'{k}: {v}' if str(v).strip() else str(k)
            tm = attr_model(str(k), label, b.x, b.y - b.height - row, b.attribute_font, getattr(b, 'body_attr_align', 'left'), 'upper')
            txt = TextItem(tm, self)
            txt.setData(0, 'ATTR_BODY')
            self.apply_item_selectability(txt)
            self.scene.addItem(txt)
            row += 1

    def body_anchor_point(self, body: SymbolBodyModel, mode: str):
        mapping = {
            OriginMode.TOP_LEFT.value: (body.x, body.y),
            OriginMode.TOP_RIGHT.value: (body.x + body.width, body.y),
            OriginMode.BOTTOM_LEFT.value: (body.x, body.y - body.height),
            OriginMode.BOTTOM_RIGHT.value: (body.x + body.width, body.y - body.height),
            OriginMode.CENTER.value: (body.x + body.width / 2, body.y - body.height / 2),
        }
        return mapping.get(mode, mapping[OriginMode.CENTER.value])

    def body_anchor_point_oriented(self, body: SymbolBodyModel, mode: str):
        """BODY anchor in grid coordinates, respecting BODY rotation.

        The model stores BODY x/y/width/height as an unrotated rectangle and
        rotation separately.  For non-center origins the visual anchor is the
        rotated corner, not the raw rectangle corner.  Using this value as
        transform pivot prevents drift when origins other than center are used.
        """
        try:
            raw_x, raw_y = self.body_anchor_point(body, mode)
            if mode == OriginMode.CENTER.value:
                return (raw_x, raw_y)
            rot = float(getattr(body, 'rotation', 0.0) or 0.0)
            if abs(rot) < 1e-9:
                return (raw_x, raw_y)
            cx, cy = self._body_center_grid(body)
            return self._rot_point(raw_x, raw_y, cx, cy, rot)
        except Exception:
            return self.body_anchor_point(body, mode)

    def origin_mode_changed(self, mode: str):
        self.reset_origin_to_selected_anchor(mode)

    def reset_origin_to_selected_anchor(self, mode: str | None = None):
        mode = mode or (self.origin_combo.currentText() if hasattr(self, 'origin_combo') else OriginMode.CENTER.value)
        self._sync_imported_body_model_to_body_graphics(self.unit)
        body = self.unit.body
        ax, ay = self.body_anchor_point_oriented(body, mode)
        old_mode = getattr(self.symbol, 'origin', OriginMode.CENTER.value)
        if abs(ax) < 1e-9 and abs(ay) < 1e-9 and old_mode == mode:
            return
        self.push_undo_state()
        self.symbol.origin = mode
        body.x -= ax
        body.y -= ay
        for p in self.unit.pins:
            p.x -= ax; p.y -= ay
            try: self._move_pin_owned_texts(p, -ax, -ay)
            except Exception: pass
        for t in self.unit.texts:
            t.x -= ax; t.y -= ay
        for t in getattr(self.unit.body, 'attribute_texts', {}).values():
            t.x -= ax; t.y -= ay
        for g in self.unit.graphics:
            g.x -= ax; g.y -= ay
        if hasattr(self, 'origin_combo'):
            self.origin_combo.blockSignals(True)
            self.origin_combo.setCurrentText(mode)
            self.origin_combo.blockSignals(False)
        self._invalidate_body_group_transform_cache(self.unit)
        self.dock_pins_to_body(self.unit)
        self.rebuild_scene()

    def add_pin(self, side, x=None, y=None):
        self.push_undo_state(); p=PinModel(number=self._unique_pin_number(), side=side, name=self._unique_pin_name('PIN'), function='')
        p.x = x if x is not None else (self.unit.body.x if side == PinSide.LEFT.value else self.unit.body.x + self.unit.body.width)
        p.y = y if y is not None else self.unit.body.y - 1 - len(self.unit.pins)
        self.unit.pins.append(p); self.dock_pins_to_body(self.unit); self.rebuild_scene()
    def add_graphic(self, tool, x, y):
        self.push_undo_state(); shape={DrawTool.LINE.value:'line',DrawTool.RECT.value:'rect',DrawTool.ELLIPSE.value:'ellipse'}[tool]
        model = GraphicModel(shape=shape, x=x, y=y, w=2, h=0 if shape=='line' else 2)
        model.locked_to_body = False; model.graphic_role = 'user_graphic'; model.mentor_raw = '__USER_GRAPHIC__'
        self.unit.graphics.append(model); self.rebuild_scene()
    def select_model_after_rebuild(self, model): pass
    def new_body(self): self.push_undo_state(); self.unit.body=SymbolBodyModel(); self.rebuild_scene()
    def delete_body(self): self.push_undo_state(); self.unit.body.width=0.01; self.unit.body.height=0.01; self.rebuild_scene()
    def select_all_canvas(self):
        self.set_tool(DrawTool.SELECT.value)
        self.selection_enabled = normalize_selection_enabled(getattr(self, 'selection_enabled', None))
        for item in self.scene.items():
            if is_selection_enabled_for_item(item, self.selection_enabled):
                item.setSelected(True)
            else:
                item.setSelected(False)
        self.refresh_properties()

    def _selected_body_active(self):
        try:
            return any(getattr(i, 'data', lambda *_: None)(0) == 'BODY' for i in self.scene.selectedItems())
        except Exception:
            return False

    def rotate_selected(self, deg):
        """Rotate selected objects. If BODY is selected, transform the whole current
        symbol/split part as one rigid group (BODY + pins + attributes + texts +
        graphics). This keeps imported symbols behaving like internally created
        <NONE> symbols and avoids proxy-frame transforms.
        """
        self.set_tool(DrawTool.SELECT.value)
        self.push_undo_state()
        if self._selected_body_active():
            self._transform_unit_as_body_group('rotate', float(deg))
        else:
            for it in self.scene.selectedItems():
                if hasattr(it, 'rotate_by'):
                    it.rotate_by(float(deg))
            self.schedule_scene_refresh()
        self.dirty = True

    def flip_selected_horizontal(self):
        self.set_tool(DrawTool.SELECT.value)
        self.push_undo_state()
        if self._selected_body_active():
            self._transform_unit_as_body_group('flip_h')
        else:
            for it in self.scene.selectedItems():
                if hasattr(it, 'flip_horizontal'):
                    it.flip_horizontal()
            self.schedule_scene_refresh()
        self.dirty = True

    def flip_selected_vertical(self):
        self.set_tool(DrawTool.SELECT.value)
        self.push_undo_state()
        if self._selected_body_active():
            self._transform_unit_as_body_group('flip_v')
        else:
            for it in self.scene.selectedItems():
                if hasattr(it, 'flip_vertical'):
                    it.flip_vertical()
            self.schedule_scene_refresh()
        self.dirty = True

    def scale_selected_grid(self, direction: int):
        """Scale selected BODY by one edit-grid step in width and height.

        The toolbar Scale +/- buttons should be deterministic and grid based,
        not a free 1.1 factor.  When BODY is selected we resize to the next
        edit-grid multiple; otherwise we fall back to the previous item-level
        factor behaviour for non-body graphics.
        """
        self.set_tool(DrawTool.SELECT.value)
        step = self._edit_grid_step()
        if self._selected_body_active():
            body = self.current_unit.body
            new_w = max(step, self._snap_to_edit_grid(float(body.width) + direction * step, step))
            new_h = max(step, self._snap_to_edit_grid(float(body.height) + direction * step, step))
            self.push_undo_state()
            self._selection_restore_ids = self._capture_selection_ids()
            self._transform_unit_as_body_group('scale_x_to', new_w, refresh=False)
            self._transform_unit_as_body_group('scale_y_to', new_h, refresh=True)
            self.dirty = True
            QTimer.singleShot(0, self.refresh_properties)
        else:
            self.scale_selected(1.0 + (0.1 if direction > 0 else -0.1))

    def scale_selected(self, factor):
        self.set_tool(DrawTool.SELECT.value)
        self.push_undo_state()
        if self._selected_body_active():
            self._transform_unit_as_body_group('scale', float(factor))
        else:
            # Fallback for non-body selections: keep existing item-level behaviour if present.
            for it in self.scene.selectedItems():
                if hasattr(it, 'scale_by'):
                    it.scale_by(float(factor))
            self.schedule_scene_refresh()
        self.dirty = True

    def copy_selected(self):
        self.set_tool(DrawTool.SELECT.value)
        self.clipboard_is_cut = False
        self.clipboard=[(i.data(0), copy.deepcopy(i.model)) for i in self.scene.selectedItems() if i.data(0) in ('BODY','PIN','TEXT','GRAPHIC')]
    def cut_selected(self):
        self.set_tool(DrawTool.SELECT.value)
        self.clipboard=[(i.data(0), copy.deepcopy(i.model)) for i in self.scene.selectedItems() if i.data(0) in ('BODY','PIN','TEXT','GRAPHIC')]
        self.clipboard_is_cut = True
        self.delete_selected()

    def paste_selected(self):
        self.set_tool(DrawTool.SELECT.value)
        self.push_undo_state()
        for kind, src in self.clipboard:
            m = copy.deepcopy(src)
            if hasattr(m,'x'): m.x += 1
            if hasattr(m,'y'): m.y -= 1
            if kind=='PIN':
                if not getattr(self, 'clipboard_is_cut', False):
                    m.number = self._unique_pin_number()
                    m.name = self._unique_pin_name(getattr(m, 'name', 'PIN'))
                self.unit.pins.append(m)
            elif kind=='TEXT': self.unit.texts.append(m)
            elif kind=='GRAPHIC':
                m.locked_to_body = False; m.graphic_role = 'user_graphic'; m.mentor_raw = '__USER_GRAPHIC__'
                self.unit.graphics.append(m)
            elif kind=='BODY': self.unit.body=m
        self.clipboard_is_cut = False
        self.rebuild_scene()
    def delete_selected(self):
        self.set_tool(DrawTool.SELECT.value)
        self.push_undo_state()
        for it in list(self.scene.selectedItems()):
            if it.data(0)=='PIN': self.unit.pins=[p for p in self.unit.pins if p is not it.model]
            elif it.data(0)=='TEXT': self.unit.texts=[t for t in self.unit.texts if t is not it.model]
            elif it.data(0)=='GRAPHIC': self.unit.graphics=[g for g in self.unit.graphics if g is not it.model]
            elif it.data(0)=='BODY': self.unit.body.width=0.01; self.unit.body.height=0.01
        self.rebuild_scene()
    def live_refresh(self):
        """Lightweight canvas refresh used during dragging/resizing.

        This intentionally avoids rebuilding the tree, pin table or property
        panel on every mouse-move.  The split part is still logically grouped
        through the model, but the canvas items stay flat in the scene for
        much better edit performance with large split symbols.
        """
        if getattr(self, '_live_refresh_pending', False):
            return
        self._live_refresh_pending = True
        def _do():
            self._live_refresh_pending = False
            try:
                if hasattr(self, 'view'):
                    self.scene.invalidate(self.scene.sceneRect())
                    self.scene.invalidate(self.scene.sceneRect())
                    self.view.viewport().update()
                elif hasattr(self, 'scene'):
                    self.scene.update()
            except Exception:
                pass
        QTimer.singleShot(0, _do)
    def dock_pins_to_body(self, u):
        b=u.body
        for p in u.pins: p.x = b.x if p.side == PinSide.LEFT.value else b.x + b.width

    def scale_current_unit_children_from_body_resize(self, st, body):
        self._invalidate_body_group_transform_cache(self.unit)
        """Attach all body-owned/near-body objects to BODY while resizing in the template editor.

        Pins remain docked to the BODY edge. Plain text, graphics and displayed
        symbol attributes are moved proportionally with the BODY, exactly like in
        the Symbol Wizard canvas.
        """
        old_x = float(st.get('x', body.x)); old_y = float(st.get('y', body.y))
        old_w = max(float(st.get('w', body.width)), 1e-9)
        old_h = max(float(st.get('h', body.height)), 1e-9)
        sx = float(body.width) / old_w
        sy = float(body.height) / old_h
        grid = float(getattr(self, 'grid_inch', 1.0) or 1.0)
        def sg(v):
            return round(float(v) / grid) * grid
        for p, px, py, plen in st.get('pins', []):
            p.x = body.x if p.side == PinSide.LEFT.value else body.x + body.width
            p.y = sg(body.y + (py - old_y) * sy)
            p.length = max(grid, sg(plen * max(abs(sx), .1)))
        for t, tx, ty in st.get('texts', []):
            t.x = sg(body.x + (tx - old_x) * sx)
            t.y = sg(body.y + (ty - old_y) * sy)
        for t, tx, ty in st.get('attributes', []):
            t.x = sg(body.x + (tx - old_x) * sx)
            t.y = sg(body.y + (ty - old_y) * sy)
        for gr, gx, gy, gw, gh in st.get('graphics', []):
            gr.x = sg(body.x + (gx - old_x) * sx)
            gr.y = sg(body.y + (gy - old_y) * sy)
            gr.w = sg(gw * sx)
            gr.h = sg(gh * sy)
        self.dock_pins_to_body(self.unit)

    def update_current_unit_canvas_positions(self):
        g = self.grid_px
        for item in self.scene.items():
            model = getattr(item, 'model', None)
            if model is None:
                continue
            kind = item.data(0)
            if kind == 'BODY':
                item.setPos(model.x * g, -model.y * g)
                item.setRect(0, 0, model.width * g, model.height * g)
                try:
                    item.setPen(pen_for(model.color, model.line_width, model.line_style, g))
                except Exception:
                    pass
                if hasattr(item, 'apply_transform_from_model'):
                    item.apply_transform_from_model()
            elif kind in ('PIN', 'TEXT', 'ATTR_REF_DES', 'ATTR_BODY', 'GRAPHIC'):
                if hasattr(item, 'apply_text_from_model') and kind in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY'):
                    item.apply_text_from_model()
                else:
                    item.setPos(model.x * g, -model.y * g)
                    if hasattr(item, 'apply_transform_from_model'):
                        item.apply_transform_from_model()
            item.update()
        self.scene.update()
        self.view.viewport().update()

    def update_attribute_items_for_unit(self):
        selected_ids = self._capture_selection_ids()
        for item in list(self.scene.items()):
            if item.data(0) in ('ATTR_REF_DES', 'ATTR_BODY'):
                self.scene.removeItem(item)
        self.add_attribute_text_items(self.unit)
        for item in self.scene.items():
            model = getattr(item, 'model', None)
            if model is not None and id(model) in selected_ids:
                item.setSelected(True)
        self.scene.update()
        self.view.viewport().update()

    def enforce_symbol_size_limit(self, silent=False): return True

    def apply_item_selectability(self, item):
        kind = item.data(0)
        filter_kind = selection_filter_kind_for_item(item)
        selectable = is_selection_enabled_for_item(item, self.selection_enabled)
        # Imported Mentor/template body graphics are a single locked body group in the Symbol Wizard.
        # They are only editable in the Template Editor.
        if kind == 'GRAPHIC' and getattr(getattr(item, 'model', None), 'locked_to_body', False) and not getattr(self, 'is_template_editor', False):
            selectable = False
        item.setFlag(QGraphicsItem.ItemIsSelectable, selectable)
        # Attribute text is content-locked but can still be moved/rotated/font-aligned when ATTRIBUTES is selectable.
        item.setFlag(QGraphicsItem.ItemIsMovable, selectable)
        try:
            item.setAcceptedMouseButtons(Qt.AllButtons if selectable else Qt.NoButton)
        except Exception:
            pass
        if not selectable:
            item.setSelected(False)
        z = {'BODY': 0, 'BODY_GRAPHIC': 0, 'GRAPHIC': 1, 'TEXT': 2, 'ATTR_REF_DES': 2, 'ATTR_BODY': 2, 'PIN': 3}.get(kind, -1)
        item.setZValue(z)

    def move_current_unit_group(self, dx: float, dy: float, source_body=None):
        # Template canvas mirrors the Wizard: moving the body moves all template-owned objects with it.
        for p in self.unit.pins:
            p.x += dx; p.y += dy
        for t in self.unit.texts:
            t.x += dx; t.y += dy
        for t in getattr(self.unit.body, 'attribute_texts', {}).values():
            t.x += dx; t.y += dy
        for g in self.unit.graphics:
            g.x += dx; g.y += dy

    def _text_items_only(self, items):
        return [i for i in items if i.data(0) in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY') and getattr(i, 'model', None) is not None]

    def _snap_text_anchor_to_grid(self, item):
        if getattr(item, 'model', None) is None:
            return
        item.model.x = self.snap_grid_value(float(getattr(item.model, 'x', 0.0) or 0.0))
        item.model.y = self.snap_grid_value(float(getattr(item.model, 'y', 0.0) or 0.0))

    def _text_rect_grid(self, item):
        # Prefer the same tight visual rectangle that TextItem uses for the
        # anchor marker.  This avoids Qt document-margin slack and makes right
        # and lower alignment exact.
        g = self.grid_px
        try:
            r = item.mapRectToScene(item._visual_text_rect())
        except Exception:
            r = item.sceneBoundingRect()
        return {
            'left': r.left() / g,
            'right': r.right() / g,
            'top': -r.top() / g,
            'bottom': -r.bottom() / g,
            'center_x': (r.left() + r.right()) / (2.0 * g),
            'center_y': -(r.top() + r.bottom()) / (2.0 * g),
            'width': max(0.0, r.width() / g),
            'height': max(0.0, r.height() / g),
        }

    def _place_text_left(self, item, left):
        item.model.h_align = 'left'
        item.model.x = round(left)

    def _place_text_right(self, item, right):
        item.model.h_align = 'right'
        item.model.x = round(right)

    def _place_text_top(self, item, top):
        item.model.v_align = 'upper'
        item.model.y = round(top)

    def _place_text_bottom(self, item, bottom):
        item.model.v_align = 'lower'
        item.model.y = round(bottom)

    def align_text_objects(self, items, mode):
        txt = self._text_items_only(items)
        if len(txt) < 2:
            try:
                self.statusBar().showMessage('Select at least two text/attribute objects.', 3000)
            except Exception:
                pass
            return
        self.push_undo_state()
        rects = {i: self._text_rect_grid(i) for i in txt}
        if mode == 'left':
            target = round(min(r['left'] for r in rects.values()))
            for i in txt:
                i.model.h_align = 'left'; i.model.x = target; i.apply_text_from_model()
        elif mode == 'center':
            target = round(sum(r['center_x'] for r in rects.values()) / max(1, len(rects)))
            for i in txt:
                i.model.h_align = 'center'; i.model.x = target; i.apply_text_from_model()
        elif mode == 'right':
            target = round(max(r['right'] for r in rects.values()))
            for i in txt:
                i.model.h_align = 'right'; i.model.x = target; i.apply_text_from_model()
        elif mode == 'upper':
            target = round(max(r['top'] for r in rects.values()))
            for i in txt:
                i.model.v_align = 'upper'; i.model.y = target; i.apply_text_from_model()
        elif mode == 'middle':
            target = round(sum(r['center_y'] for r in rects.values()) / max(1, len(rects)))
            for i in txt:
                i.model.v_align = 'center'; i.model.y = target; i.apply_text_from_model()
        elif mode == 'lower':
            target = round(min(r['bottom'] for r in rects.values()))
            for i in txt:
                i.model.v_align = 'lower'; i.model.y = target; i.apply_text_from_model()
        self._selection_restore_ids = {id(i.model) for i in txt}
        try:
            self.schedule_scene_refresh(visual_only=True)
        except Exception:
            self.update_current_unit_canvas_positions(); self.refresh_properties()

    def distribute_text_objects(self, items, axis):
        txt = self._text_items_only(items)
        if len(txt) < 3:
            try:
                self.statusBar().showMessage('Select at least three text/attribute objects to distribute.', 3000)
            except Exception:
                pass
            return
        self.push_undo_state()
        if axis == 'h':
            txt = sorted(txt, key=lambda i: float(getattr(i.model, 'x', 0.0) or 0.0))
            start = round(float(getattr(txt[0].model, 'x', 0.0) or 0.0))
            end = round(float(getattr(txt[-1].model, 'x', 0.0) or 0.0))
            step = 0 if len(txt) == 1 else round((end - start) / (len(txt) - 1))
            for idx, i in enumerate(txt):
                i.model.x = start + idx * step
                i.apply_text_from_model()
        else:
            txt = sorted(txt, key=lambda i: float(getattr(i.model, 'y', 0.0) or 0.0), reverse=True)
            start = round(float(getattr(txt[0].model, 'y', 0.0) or 0.0))
            end = round(float(getattr(txt[-1].model, 'y', 0.0) or 0.0))
            step = 0 if len(txt) == 1 else round((start - end) / (len(txt) - 1))
            for idx, i in enumerate(txt):
                i.model.y = start - idx * step
                i.apply_text_from_model()
        self._selection_restore_ids = {id(i.model) for i in txt}
        try:
            self.schedule_scene_refresh(visual_only=True)
        except Exception:
            self.update_current_unit_canvas_positions(); self.refresh_properties()

    def rebuild_tree(self): pass
    def rebuild_pin_table(self): pass



class AttributeProfileManagerDialog(QDialog):
    """Self-explanatory profile editor for global PinType and PartType attributes.

    The JSON schema remains deliberately simple and extensible:

    {
      "version": 1,
      "core_part_attributes": [{"name": "Package", "value": "", "visible": true, "required": false, "description": "..."}],
      "part_types": {"RELAY": {"attributes": [...] }},
      "pin_types": {"POWER": {"attributes": [...] }}
    }
    """

    TABLE_HEADERS = ['Attribute', 'Default Value', 'Visible', 'Required', 'Description']

    def __init__(self, parent):
        super().__init__(parent)
        self.main = parent
        self.setWindowTitle('Attribute Profile Manager')
        self.resize(1180, 760)
        self.data = self._normalize_profiles(parent.load_attribute_profiles())
        self._current_pin_type = None
        self._current_part_type = None
        self._build_ui()
        self._load_all_controls()

    def _normalize_profiles(self, data):
        base = self.main.load_attribute_profiles() if not isinstance(data, dict) else dict(data)
        base.setdefault('version', 1)
        base.setdefault('core_part_attributes', [])
        base.setdefault('base_part_classes', {})
        base.setdefault('part_types', {})
        base.setdefault('pin_types', {})
        base['base_part_classes'].setdefault('DEFAULT', {'attributes': []})
        for ptype in [p.value for p in PinType]:
            base['pin_types'].setdefault(ptype, {'attributes': []})
        for section in [base.get('core_part_attributes', [])]:
            self._normalize_attr_list(section)
        for group in list((base.get('base_part_classes') or {}).values()) + list((base.get('pin_types') or {}).values()) + list((base.get('part_types') or {}).values()):
            group.setdefault('attributes', [])
            self._normalize_attr_list(group['attributes'])
        return base

    def _normalize_attr_list(self, attrs):
        for attr in attrs or []:
            if not isinstance(attr, dict):
                continue
            attr.setdefault('name', '')
            attr.setdefault('value', '')
            attr.setdefault('visible', False)
            attr.setdefault('required', False)
            attr.setdefault('description', '')
            attr.setdefault('locked', False)
            if str(attr.get('name', '')).strip() in {'RefDes', 'CLASS'}:
                attr['locked'] = True
                if str(attr.get('name', '')).strip() == 'RefDes':
                    attr['visible'] = True
                    attr['required'] = True

    def _build_ui(self):
        root = QVBoxLayout(self)

        title = QLabel('<h2 style="margin:0;">Attribute Profile Manager</h2>')
        subtitle = QLabel(
            'Define reusable attribute profiles for DRC checks, exports and metadata consistency. '
            'PinType attributes are selected by pin type. BODY attributes are split into global core attributes and part-type-specific attributes.'
        )
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self._build_pin_tab()
        self._build_body_tab()

        buttons = QHBoxLayout()
        for label, slot, tip in [
            ('Load from current symbol', self.load_from_current_symbol, 'Merge attributes from the currently opened symbol into the profile editor.'),
            ('Apply to current symbol', self.apply_to_current_symbol, 'Overwrite/update the current symbol attributes from these profiles.'),
            ('Import JSON', self.import_json, 'Load a complete attribute profile JSON file.'),
            ('Export JSON', self.export_json, 'Export the complete attribute profile JSON file.'),
            ('Save profiles', self.save_profiles, 'Save profiles as the project default.'),
        ]:
            b = QPushButton(label)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            buttons.addWidget(b)
        buttons.addStretch(1)
        close = QPushButton('Close')
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        root.addLayout(buttons)

    def _build_pin_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        help_lbl = QLabel(
            '<b>PinType Attributes</b><br>'
            'Choose a pin type, then define metadata attributes that belong to that electrical pin type. '
            'Examples: POWER -> Max Voltage / Power Rating, GROUND -> Ground Domain. '
            'These attributes are global and can later be used by DRC or other metaprocesses.'
        )
        help_lbl.setWordWrap(True)
        lay.addWidget(help_lbl)
        top = QHBoxLayout()
        top.addWidget(QLabel('Pin Type:'))
        self.pin_type_combo = QComboBox()
        self.pin_type_combo.addItems([p.value for p in PinType])
        self.pin_type_combo.currentTextChanged.connect(self._pin_type_changed)
        top.addWidget(self.pin_type_combo)
        top.addStretch(1)
        lay.addLayout(top)
        self.pin_attr_table = self._make_attr_table()
        lay.addWidget(self.pin_attr_table, 1)
        row = QHBoxLayout()
        for label, slot in [
            ('Add PinType Attribute', self.add_pin_attribute),
            ('Delete selected', lambda: self.delete_selected_rows(self.pin_attr_table)),
            ('Export this PinType', self.export_current_pin_type),
            ('Import/Replace this PinType', self.import_current_pin_type),
        ]:
            b = QPushButton(label)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.tabs.addTab(tab, 'PinType Attributes')

    def _build_body_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        help_lbl = QLabel(
            '<b>BODY / Part Attributes</b><br>'
            '<b>Core attributes</b> are the smallest common denominator for all parts, e.g. Package or Datasheet-Link. '
            '<b>PartType attributes</b> are selected by component type and contain type-specific metadata. '
            'Component classes / part types can be derived from the current symbol library and the template library used by the Template Editor.'
        )
        help_lbl.setWordWrap(True)
        lay.addWidget(help_lbl)
        splitter = QSplitter(Qt.Horizontal)
        lay.addWidget(splitter, 1)

        core_box = QGroupBox('Core BODY Attributes - valid for all symbols')
        core_lay = QVBoxLayout(core_box)
        self.core_attr_table = self._make_attr_table()
        core_lay.addWidget(self.core_attr_table, 1)
        base_label = QLabel('<b>BODY Base Classes</b><br>Optional reusable attribute sets between global Core attributes and concrete PartTypes.')
        base_label.setWordWrap(True)
        core_lay.addWidget(base_label)
        base_selector = QHBoxLayout()
        base_selector.addWidget(QLabel('Base class:'))
        self.base_class_combo = QComboBox()
        self.base_class_combo.setEditable(True)
        self.base_class_combo.currentTextChanged.connect(self._base_class_changed)
        base_selector.addWidget(self.base_class_combo, 1)
        core_lay.addLayout(base_selector)
        self.base_attr_table = self._make_attr_table()
        self.base_attr_table.setMaximumHeight(210)
        core_lay.addWidget(self.base_attr_table)
        base_buttons = QHBoxLayout()
        for label, slot in [
            ('Add Base Attribute', self.add_base_attribute),
            ('Delete selected', lambda: self.delete_selected_rows(self.base_attr_table)),
            ('Delete Base Class', self.delete_current_base_class),
        ]:
            b = QPushButton(label)
            b.clicked.connect(slot)
            base_buttons.addWidget(b)
        base_buttons.addStretch(1)
        core_lay.addLayout(base_buttons)
        core_buttons = QHBoxLayout()
        for label, slot in [
            ('Add Core Attribute', self.add_core_attribute),
            ('Delete selected', lambda: self.delete_selected_rows(self.core_attr_table)),
        ]:
            b = QPushButton(label)
            b.clicked.connect(slot)
            core_buttons.addWidget(b)
        core_buttons.addStretch(1)
        core_lay.addLayout(core_buttons)
        splitter.addWidget(core_box)

        part_box = QGroupBox('PartType-specific BODY Attributes')
        part_lay = QVBoxLayout(part_box)
        selector = QHBoxLayout()
        selector.addWidget(QLabel('Component class / Part type:'))
        self.part_type_combo = QComboBox()
        self.part_type_combo.setEditable(True)
        self.part_type_combo.currentTextChanged.connect(self._part_type_changed)
        selector.addWidget(self.part_type_combo, 1)
        selector.addWidget(QLabel('Base class:'))
        self.part_base_class_combo = QComboBox()
        self.part_base_class_combo.setEditable(True)
        self.part_base_class_combo.setToolTip('Optional BODY base class applied between Core attributes and this PartType profile.')
        self.part_base_class_combo.currentTextChanged.connect(self._part_base_class_changed)
        selector.addWidget(self.part_base_class_combo, 1)
        derive = QPushButton('Derive profiles from library')
        derive.setToolTip('Scan current/custom symbols and the Template Editor library, classify component classes and add suggested attributes.')
        derive.clicked.connect(self.derive_part_types_from_library)
        selector.addWidget(derive)
        part_lay.addLayout(selector)
        self.part_attr_table = self._make_attr_table()
        part_lay.addWidget(self.part_attr_table, 1)
        part_buttons = QHBoxLayout()
        for label, slot in [
            ('Add PartType Attribute', self.add_part_attribute),
            ('Delete selected', lambda: self.delete_selected_rows(self.part_attr_table)),
            ('Delete PartType Profile', self.delete_current_part_type),
            ('Export this PartType', self.export_current_part_type),
            ('Import/Replace this PartType', self.import_current_part_type),
        ]:
            b = QPushButton(label)
            b.clicked.connect(slot)
            part_buttons.addWidget(b)
        part_buttons.addStretch(1)
        part_lay.addLayout(part_buttons)
        splitter.addWidget(part_box)
        splitter.setSizes([520, 620])
        self.tabs.addTab(tab, 'BODY / PartType Attributes')

    def _make_attr_table(self):
        table = QTableWidget(0, len(self.TABLE_HEADERS))
        table.setHorizontalHeaderLabels(self.TABLE_HEADERS)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)
        return table

    def _add_attr_row(self, table, attr=None):
        attr = attr or {}
        r = table.rowCount()
        table.insertRow(r)
        name_item = QTableWidgetItem(str(attr.get('name', '')))
        if bool(attr.get('locked', False)):
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            name_item.setToolTip('Core attribute: cannot be renamed or deleted.')
            name_item.setBackground(QBrush(QColor(235, 235, 235)))
            name_item.setData(Qt.UserRole, True)
        table.setItem(r, 0, name_item)
        value_item = QTableWidgetItem(str(attr.get('value', '')))
        if bool(attr.get('locked', False)):
            value_item.setToolTip('Core attribute. Value can be edited, but the attribute cannot be deleted.')
        table.setItem(r, 1, value_item)
        for col, key in [(2, 'visible'), (3, 'required')]:
            item = QTableWidgetItem('')
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if bool(attr.get(key, False)) else Qt.Unchecked)
            table.setItem(r, col, item)
        table.setItem(r, 4, QTableWidgetItem(str(attr.get('description', ''))))

    def _table_to_attrs(self, table):
        attrs = []
        seen = set()
        for r in range(table.rowCount()):
            name = table.item(r, 0).text().strip() if table.item(r, 0) else ''
            if not name or name in seen:
                continue
            seen.add(name)
            attrs.append({
                'name': name,
                'value': table.item(r, 1).text() if table.item(r, 1) else '',
                'visible': bool(table.item(r, 2) and table.item(r, 2).checkState() == Qt.Checked),
                'required': bool(table.item(r, 3) and table.item(r, 3).checkState() == Qt.Checked),
                'description': table.item(r, 4).text() if table.item(r, 4) else '',
                'locked': bool(table.item(r, 0) and table.item(r, 0).data(Qt.UserRole)),
            })
        return attrs

    def _load_attrs_into_table(self, table, attrs):
        table.setRowCount(0)
        for attr in attrs or []:
            self._add_attr_row(table, attr if isinstance(attr, dict) else {'name': str(attr)})
        table.resizeColumnsToContents()

    def _load_all_controls(self):
        self._load_attrs_into_table(self.core_attr_table, self.data.get('core_part_attributes', []))
        self._refresh_base_class_combo()
        current_base = self.base_class_combo.currentText() if hasattr(self, 'base_class_combo') else 'DEFAULT'
        self._current_base_class = current_base or 'DEFAULT'
        if hasattr(self, 'base_attr_table'):
            self._load_attrs_into_table(self.base_attr_table, ((self.data.get('base_part_classes') or {}).get(self._current_base_class) or {}).get('attributes', []))
        current_pin = self.pin_type_combo.currentText() or PinType.IN.value
        self._current_pin_type = current_pin
        self._load_attrs_into_table(self.pin_attr_table, ((self.data.get('pin_types') or {}).get(current_pin) or {}).get('attributes', []))
        self._refresh_part_type_combo()
        current_part = self.part_type_combo.currentText() or 'DEFAULT'
        self._current_part_type = current_part
        self._load_attrs_into_table(self.part_attr_table, ((self.data.get('part_types') or {}).get(current_part) or {}).get('attributes', []))

    def _refresh_base_class_combo(self):
        if not hasattr(self, 'base_class_combo'):
            return
        current = self.base_class_combo.currentText() or 'DEFAULT'
        base_classes = sorted(set(['DEFAULT']) | set((self.data.get('base_part_classes') or {}).keys()))
        self.base_class_combo.blockSignals(True)
        self.base_class_combo.clear()
        self.base_class_combo.addItems(base_classes)
        self.base_class_combo.setCurrentText(current if current in base_classes else 'DEFAULT')
        self.base_class_combo.blockSignals(False)
        if hasattr(self, 'part_base_class_combo'):
            part_current = self.part_base_class_combo.currentText() or 'DEFAULT'
            self.part_base_class_combo.blockSignals(True)
            self.part_base_class_combo.clear()
            self.part_base_class_combo.addItems(base_classes)
            self.part_base_class_combo.setCurrentText(part_current if part_current in base_classes else 'DEFAULT')
            self.part_base_class_combo.blockSignals(False)

    def _save_current_base_class_profile(self):
        base = getattr(self, '_current_base_class', None) or (self.base_class_combo.currentText().strip() if hasattr(self, 'base_class_combo') else 'DEFAULT') or 'DEFAULT'
        if base:
            self.data.setdefault('base_part_classes', {}).setdefault(base, {'attributes': []})['attributes'] = self._table_to_attrs(self.base_attr_table)

    def _base_class_changed(self, base):
        if getattr(self, '_current_base_class', None) is not None:
            self._save_current_base_class_profile()
        base = (base or 'DEFAULT').strip() or 'DEFAULT'
        self._current_base_class = base
        self.data.setdefault('base_part_classes', {}).setdefault(base, {'attributes': []})
        self._load_attrs_into_table(self.base_attr_table, ((self.data.get('base_part_classes') or {}).get(base) or {}).get('attributes', []))

    def _part_base_class_changed(self, base):
        part = getattr(self, '_current_part_type', None) or (self.part_type_combo.currentText().strip() if hasattr(self, 'part_type_combo') else 'DEFAULT') or 'DEFAULT'
        self.data.setdefault('part_types', {}).setdefault(part, {'attributes': []})['base_class'] = (base or 'DEFAULT').strip() or 'DEFAULT'

    def _refresh_part_type_combo(self):
        current = self.part_type_combo.currentText() if hasattr(self, 'part_type_combo') else ''
        part_types = sorted(set(['DEFAULT']) | set((self.data.get('part_types') or {}).keys()) | set(self._discover_part_types()))
        self.part_type_combo.blockSignals(True)
        self.part_type_combo.clear()
        self.part_type_combo.addItems(part_types)
        if current:
            self.part_type_combo.setCurrentText(current)
        self.part_type_combo.blockSignals(False)
        self._refresh_base_class_combo()

    def _clean_template_attr_value(self, value):
        text = str(value or '').strip()
        if text in {'', '?', 'TYPE', 'VALUE', 'CLASS'}:
            return ''
        return text

    def _part_class_from_attrs(self, attrs, fallback='DEFAULT'):
        attrs = attrs or {}
        for key in ('CLASS', 'Part Type', 'PARTTYPE', 'TYPE'):
            value = self._clean_template_attr_value(attrs.get(key, ''))
            if value:
                return value
        return str(fallback or 'DEFAULT').strip() or 'DEFAULT'

    def _attr_record_from_body_attr(self, name, value='', visible=False, description='Derived from template/custom library.'):
        name = str(name).strip()
        locked = name in {'RefDes', 'CLASS'}
        return {
            'name': name,
            'value': '' if name == 'CLASS' else str(value or ''),
            'visible': True if name in {'RefDes', 'CLASS'} else bool(visible),
            'required': True if name in {'RefDes', 'CLASS'} else False,
            'locked': locked,
            'description': description if not locked else ('Reference designator. Cannot be deleted.' if name == 'RefDes' else 'Component class used for profile selection. Cannot be deleted.'),
        }

    def _core_attribute_names(self):
        names = set()
        for attr in self.data.get('core_part_attributes', []) or []:
            if isinstance(attr, dict):
                name = str(attr.get('name', '')).strip()
                if name:
                    names.add(name)
        names.update({'RefDes', 'CLASS'})
        return names

    def _profile_key(self, name):
        return str(name or '').strip().casefold()

    def _merge_attr_record(self, existing, incoming):
        result = dict(existing or {})
        for key, value in (incoming or {}).items():
            if key in {'visible', 'required', 'locked'}:
                result[key] = bool(result.get(key, False) or value)
            elif key == 'value':
                if not str(result.get('value', '')).strip() and str(value or '').strip():
                    result[key] = value
                else:
                    result.setdefault(key, result.get(key, ''))
            elif key == 'description':
                if not str(result.get('description', '')).strip() and str(value or '').strip():
                    result[key] = value
            else:
                result.setdefault(key, value)
        if str(result.get('name', '')).strip() in {'RefDes', 'CLASS'}:
            result['locked'] = True
            result['required'] = True
            result['visible'] = True
        return result

    def _append_or_merge_attrs(self, target, attrs):
        by_key = {self._profile_key(a.get('name')): idx for idx, a in enumerate(target) if isinstance(a, dict) and a.get('name')}
        for attr in attrs or []:
            if not isinstance(attr, dict):
                continue
            name = str(attr.get('name', '')).strip()
            if not name:
                continue
            key = self._profile_key(name)
            if key in by_key:
                target[by_key[key]] = self._merge_attr_record(target[by_key[key]], attr)
            else:
                target.append(dict(attr))
                by_key[key] = len(target) - 1

    def _prune_core_attrs_from_part_profiles(self, data=None):
        data = data or self.data
        core_names = {self._profile_key(a.get('name')) for a in (data.get('core_part_attributes') or []) if isinstance(a, dict)}
        core_names.update({self._profile_key('RefDes'), self._profile_key('CLASS')})
        for group in (data.get('part_types') or {}).values():
            attrs = group.get('attributes', []) if isinstance(group, dict) else []
            group['attributes'] = [a for a in attrs if not (isinstance(a, dict) and self._profile_key(a.get('name')) in core_names)]
        return data

    def _load_bundled_liebherr_profile_seed(self):
        """Load profile seed derived from the full uploaded Liebherr SymbolLibs package."""
        path = Path(__file__).resolve().parent.parent / 'attribute_profiles_liebherr_symbol_libs.json'
        try:
            if path.exists():
                payload = json.loads(path.read_text(encoding='utf-8'))
                return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}
        return {}

    def _merge_bundled_seed_into_discovery(self, profiles, core_records):
        seed = self._load_bundled_liebherr_profile_seed()
        if not isinstance(seed, dict) or not seed:
            return profiles, core_records, 0
        self._append_or_merge_attrs(core_records, seed.get('core_part_attributes', []) or [])
        core_keys = {self._profile_key(a.get('name')) for a in core_records if isinstance(a, dict)}
        merged_parts = 0
        for part, group in (seed.get('part_types') or {}).items():
            part = str(part or '').strip() or 'DEFAULT'
            attrs = group.get('attributes', []) if isinstance(group, dict) else []
            bucket = profiles.setdefault(part, {})
            before = len(bucket)
            for attr in attrs or []:
                if not isinstance(attr, dict):
                    continue
                name = str(attr.get('name', '')).strip()
                if not name or self._profile_key(name) in core_keys:
                    continue
                existing_name = None
                for candidate in bucket.keys():
                    if self._profile_key(candidate) == self._profile_key(name):
                        existing_name = candidate
                        break
                if existing_name is not None:
                    bucket[existing_name] = self._merge_attr_record(bucket[existing_name], attr)
                else:
                    bucket[name] = dict(attr)
            if len(bucket) > before:
                merged_parts += 1
        return profiles, core_records, merged_parts

    def _discover_library_part_profiles(self):
        profiles = {}
        total_bodies = 0
        part_seen = {}
        attr_counts = {}
        attr_part_sets = {}
        attr_values = {}
        attr_visible = {}

        def note_global_attr(name, value='', visible=False, part='DEFAULT'):
            nonlocal total_bodies
            name = str(name).strip()
            if not name or name.startswith('MENTOR_'):
                return
            attr_counts[name] = attr_counts.get(name, 0) + 1
            attr_part_sets.setdefault(name, set()).add(str(part or 'DEFAULT'))
            attr_values.setdefault(name, {})[str(value or '')] = attr_values.setdefault(name, {}).get(str(value or ''), 0) + 1
            if visible:
                attr_visible[name] = attr_visible.get(name, 0) + 1

        def add_body(attrs, visible=None, fallback='DEFAULT'):
            nonlocal total_bodies
            attrs = attrs or {}
            visible = visible or {}
            part = self._part_class_from_attrs(attrs, fallback)
            total_bodies += 1
            part_seen[part] = part_seen.get(part, 0) + 1
            bucket = profiles.setdefault(part, {})
            for name, value in attrs.items():
                name = str(name).strip()
                if not name or name.startswith('MENTOR_'):
                    continue
                val = self._clean_template_attr_value(value)
                is_visible = bool(visible.get(name, False))
                note_global_attr(name, val, is_visible, part)
                if name in {'RefDes', 'CLASS'}:
                    continue
                record = bucket.setdefault(name, self._attr_record_from_body_attr(name, val, is_visible))
                if not record.get('value') and val:
                    record['value'] = val
                record['visible'] = bool(record.get('visible', False) or is_visible)

        # Current/custom library in memory.
        try:
            for symbol in getattr(getattr(self.main, 'library', None), 'symbols', []) or []:
                for unit in getattr(symbol, 'units', []) or []:
                    body = getattr(unit, 'body', None)
                    if body is not None:
                        add_body(getattr(body, 'attributes', {}) or {}, getattr(body, 'visible_attributes', {}) or {}, getattr(symbol, 'name', 'DEFAULT'))
        except Exception:
            pass

        # Template library used by the Template Editor, including the compressed release archive.
        base = Path(__file__).resolve().parent.parent / 'symbol_templates'
        archive = base / 'mentor_known_templates.tar.xz'
        try:
            if archive.exists():
                with tarfile.open(archive, 'r:xz') as tf:
                    for member in tf.getmembers():
                        if not member.isfile() or not member.name.endswith('.json'):
                            continue
                        fallback = Path(member.name).stem
                        try:
                            handle = tf.extractfile(member)
                            if handle is None:
                                continue
                            payload = json.loads(handle.read().decode('utf-8'))
                        except Exception:
                            continue
                        entries = payload if isinstance(payload, list) else [payload]
                        for entry in entries:
                            unit = (entry or {}).get('unit', {}) if isinstance(entry, dict) else {}
                            body = unit.get('body', {}) if isinstance(unit, dict) else {}
                            if isinstance(body, dict):
                                add_body(body.get('attributes', {}) or {}, body.get('visible_attributes', {}) or {}, fallback)
        except Exception:
            pass

        part_count = max(1, len(part_seen))
        existing_core = self._core_attribute_names()
        core_names = {str(n).strip() for n in existing_core if str(n).strip()}
        # Promote attributes that are library-wide.  This covers the true common
        # denominator from the full Template Editor library and prevents those
        # names from being duplicated under PartType-specific profiles.
        for name, count in attr_counts.items():
            body_ratio = count / max(1, total_bodies)
            part_ratio = len(attr_part_sets.get(name, set())) / part_count
            if body_ratio >= 0.75 or part_ratio >= 0.75:
                core_names.add(name)

        core_records = []
        for name in sorted(core_names, key=lambda x: (x not in {'RefDes', 'CLASS'}, x.casefold())):
            vals = attr_values.get(name, {})
            value = ''
            if vals:
                # Pick a useful placeholder/default when there is one, otherwise
                # keep the core value empty so it can be filled per symbol.
                value = max(vals.items(), key=lambda kv: kv[1])[0]
                if self._clean_template_attr_value(value) == '':
                    value = ''
            visible = bool(attr_visible.get(name, 0) >= max(1, attr_counts.get(name, 0)) * 0.25)
            core_records.append(self._attr_record_from_body_attr(name, value, visible, 'Common BODY attribute derived from the full Template Editor library.'))

        profiles, core_records, seed_part_count = self._merge_bundled_seed_into_discovery(profiles, core_records)

        core_keys = {self._profile_key(a.get('name')) for a in core_records}
        for bucket in profiles.values():
            for name in list(bucket.keys()):
                if self._profile_key(name) in core_keys:
                    bucket.pop(name, None)

        self._last_discovered_core_attrs = core_records
        self._last_discovered_body_count = total_bodies
        self._last_discovered_part_count = len(set(part_seen) | set(profiles))
        self._last_seed_part_count = seed_part_count
        return {part: list(attrs.values()) for part, attrs in profiles.items() if attrs}

    def _discover_part_types(self):
        return set(self._discover_library_part_profiles().keys())

    def _save_current_pin_profile(self):
        ptype = self._current_pin_type or self.pin_type_combo.currentText()
        if ptype:
            self.data.setdefault('pin_types', {}).setdefault(ptype, {'attributes': []})['attributes'] = self._table_to_attrs(self.pin_attr_table)

    def _save_current_part_profile(self):
        part = self._current_part_type or self.part_type_combo.currentText().strip() or 'DEFAULT'
        if part:
            group = self.data.setdefault('part_types', {}).setdefault(part, {'attributes': []})
            group['attributes'] = self._table_to_attrs(self.part_attr_table)
            if hasattr(self, 'part_base_class_combo'):
                group['base_class'] = (self.part_base_class_combo.currentText() or 'DEFAULT').strip() or 'DEFAULT'

    def _save_core_profile(self):
        self.data['core_part_attributes'] = self._table_to_attrs(self.core_attr_table)
        if hasattr(self, 'base_attr_table'):
            self._save_current_base_class_profile()

    def _pin_type_changed(self, ptype):
        if self._current_pin_type is not None:
            self._save_current_pin_profile()
        self._current_pin_type = ptype
        self._load_attrs_into_table(self.pin_attr_table, ((self.data.get('pin_types') or {}).get(ptype) or {}).get('attributes', []))

    def _part_type_changed(self, part):
        if self._current_part_type is not None:
            self._save_current_part_profile()
        part = (part or 'DEFAULT').strip() or 'DEFAULT'
        self._current_part_type = part
        group = self.data.setdefault('part_types', {}).setdefault(part, {'attributes': []})
        if hasattr(self, 'part_base_class_combo'):
            self.part_base_class_combo.blockSignals(True)
            self.part_base_class_combo.setCurrentText(str(group.get('base_class') or 'DEFAULT'))
            self.part_base_class_combo.blockSignals(False)
        self._load_attrs_into_table(self.part_attr_table, group.get('attributes', []))

    def collect_data(self):
        self._save_core_profile()
        self._save_current_pin_profile()
        self._save_current_part_profile()
        result = self._normalize_profiles(self.data)
        self._prune_core_attrs_from_part_profiles(result)
        # Drop empty base profiles except DEFAULT when no attributes exist.
        result['base_part_classes'] = {k: v for k, v in (result.get('base_part_classes') or {}).items() if (v.get('attributes') or []) or k == 'DEFAULT'}
        # Drop empty part profiles except DEFAULT when no attributes or base class exist.
        result['part_types'] = {k: v for k, v in (result.get('part_types') or {}).items() if (v.get('attributes') or []) or (v.get('base_class') and v.get('base_class') != 'DEFAULT') or k == 'DEFAULT'}
        return result

    def add_pin_attribute(self):
        self._add_attr_row(self.pin_attr_table, {'name': 'NEW_ATTRIBUTE', 'value': '', 'visible': False, 'required': False, 'description': ''})

    def add_core_attribute(self):
        self._add_attr_row(self.core_attr_table, {'name': 'NEW_ATTRIBUTE', 'value': '', 'visible': True, 'required': False, 'description': 'Common attribute for all parts.'})

    def add_part_attribute(self):
        self._add_attr_row(self.part_attr_table, {'name': 'NEW_ATTRIBUTE', 'value': '', 'visible': False, 'required': False, 'description': 'Part-type-specific attribute.'})

    def add_base_attribute(self):
        self._add_attr_row(self.base_attr_table, {'name': 'NEW_ATTRIBUTE', 'value': '', 'visible': False, 'required': False, 'description': 'BODY base-class attribute.'})

    def delete_current_base_class(self):
        base = (self.base_class_combo.currentText() or '').strip() or 'DEFAULT'
        if base == 'DEFAULT':
            QMessageBox.information(self, 'BODY Base Class', 'DEFAULT base class cannot be deleted; clear its rows instead.')
            return
        if QMessageBox.question(self, 'Delete BODY Base Class', f'Delete base class "{base}"?') != QMessageBox.Yes:
            return
        self.data.get('base_part_classes', {}).pop(base, None)
        for group in (self.data.get('part_types') or {}).values():
            if isinstance(group, dict) and group.get('base_class') == base:
                group['base_class'] = 'DEFAULT'
        self._current_base_class = None
        self._refresh_base_class_combo()
        self._base_class_changed(self.base_class_combo.currentText() or 'DEFAULT')

    def delete_selected_rows(self, table):
        rows = sorted({idx.row() for idx in table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        skipped = []
        for r in rows:
            item = table.item(r, 0)
            name = item.text().strip() if item else ''
            if bool(item and item.data(Qt.UserRole)) or name == 'RefDes':
                skipped.append(name or 'locked attribute')
                continue
            table.removeRow(r)
        if skipped:
            QMessageBox.information(self, 'Core Attribute', 'The following core attributes cannot be deleted: ' + ', '.join(skipped))

    def delete_current_part_type(self):
        part = (self.part_type_combo.currentText() or '').strip() or 'DEFAULT'
        if part == 'DEFAULT':
            QMessageBox.information(self, 'PartType Profile', 'DEFAULT profile cannot be deleted; clear its rows instead.')
            return
        if QMessageBox.question(self, 'Delete PartType Profile', f'Delete profile "{part}"?') != QMessageBox.Yes:
            return
        self.data.get('part_types', {}).pop(part, None)
        self._current_part_type = None
        self._refresh_part_type_combo()
        self._part_type_changed(self.part_type_combo.currentText() or 'DEFAULT')

    def derive_part_types_from_library(self):
        profiles = self._discover_library_part_profiles()
        core_target = self.data.setdefault('core_part_attributes', [])
        self._append_or_merge_attrs(core_target, getattr(self, '_last_discovered_core_attrs', []))
        for part, attrs in profiles.items():
            target = self.data.setdefault('part_types', {}).setdefault(part, {'attributes': []})['attributes']
            self._append_or_merge_attrs(target, attrs)
        self._prune_core_attrs_from_part_profiles(self.data)
        self._load_attrs_into_table(self.core_attr_table, self.data.get('core_part_attributes', []))
        self._refresh_base_class_combo()
        if hasattr(self, 'base_attr_table'):
            current_base = self.base_class_combo.currentText() or 'DEFAULT'
            self._load_attrs_into_table(self.base_attr_table, ((self.data.get('base_part_classes') or {}).get(current_base) or {}).get('attributes', []))
        self._refresh_part_type_combo()
        current_part = self.part_type_combo.currentText() or 'DEFAULT'
        self._load_attrs_into_table(self.part_attr_table, ((self.data.get('part_types') or {}).get(current_part) or {}).get('attributes', []))
        core_count = len(self.data.get('core_part_attributes', []) or [])
        seed_count = int(getattr(self, '_last_seed_part_count', 0) or 0)
        msg = (f'Derived {len(profiles)} component classes / part types from the current, Template Editor and bundled Liebherr SymbolLibs profiles.\n'
               f'Added/merged {seed_count} rich PartType profile(s) from the full SymbolLibs scan.\n'
               f'Core BODY Attributes now contain {core_count} common attributes and are removed from PartType-specific profiles.')
        QMessageBox.information(self, 'Attribute Profiles', msg)

    def load_from_current_symbol(self):
        data = self.collect_data()
        for unit in getattr(self.main.symbol, 'units', []) or []:
            body = getattr(unit, 'body', None)
            if body is not None:
                attrs = getattr(body, 'attributes', {}) or {}
                part = self._part_class_from_attrs(attrs, 'DEFAULT')
                target = data.setdefault('part_types', {}).setdefault(part, {'attributes': []})['attributes']
                existing = {a.get('name') for a in target if isinstance(a, dict)}
                core_keys = {self._profile_key(a.get('name')) for a in (data.get('core_part_attributes') or []) if isinstance(a, dict)}
                for name, value in attrs.items():
                    if self._profile_key(name) in core_keys:
                        continue
                    if name not in existing:
                        target.append({'name': name, 'value': value, 'visible': (getattr(body, 'visible_attributes', {}) or {}).get(name, False), 'required': False, 'description': 'Loaded from current symbol.'})
            for pin in getattr(unit, 'pins', []) or []:
                ptype = str(getattr(pin, 'pin_type', '') or 'BIDI')
                target = data.setdefault('pin_types', {}).setdefault(ptype, {'attributes': []})['attributes']
                existing = {a.get('name') for a in target if isinstance(a, dict)}
                for name, value in (getattr(pin, 'attributes', {}) or {}).items():
                    if str(name).upper() in {'#','NAME','PIN / FUNC','PINTYPE'}:
                        continue
                    if name not in existing:
                        target.append({'name': name, 'value': value, 'visible': (getattr(pin, 'visible_attributes', {}) or {}).get(name, False), 'required': False, 'description': 'Loaded from current symbol.'})
        self.data = self._normalize_profiles(data)
        self._current_pin_type = None
        self._current_part_type = None
        self._load_all_controls()

    def save_profiles(self):
        self.data = self.collect_data()
        self.main.save_attribute_profiles(self.data)
        QMessageBox.information(self, 'Attribute Profiles', 'Profiles saved as project defaults.')

    def apply_to_current_symbol(self):
        self.data = self.collect_data()
        self.main.save_attribute_profiles(self.data)
        self.main.apply_attribute_profiles_to_current_symbol(self.data)
        QMessageBox.information(self, 'Attribute Profiles', 'Current symbol was updated from the profiles.')

    def import_json(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import Attribute Profile JSON', '', 'JSON (*.json)')
        if not path:
            return
        try:
            self.data = self._normalize_profiles(json.loads(Path(path).read_text(encoding='utf-8')))
            self._current_pin_type = None
            self._current_part_type = None
            self._load_all_controls()
        except Exception as exc:
            QMessageBox.warning(self, 'Import Attribute Profiles', str(exc))

    def export_json(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Export Attribute Profile JSON', 'attribute_profiles.json', 'JSON (*.json)')
        if not path:
            return
        Path(path).write_text(json.dumps(self.collect_data(), indent=2, ensure_ascii=False), encoding='utf-8')

    def export_current_pin_type(self):
        self._save_current_pin_profile()
        ptype = self.pin_type_combo.currentText()
        path, _ = QFileDialog.getSaveFileName(self, f'Export {ptype} PinType JSON', f'pin_type_{ptype}.json', 'JSON (*.json)')
        if not path:
            return
        payload = {'version': 1, 'pin_types': {ptype: self.data.get('pin_types', {}).get(ptype, {'attributes': []})}}
        Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')

    def import_current_pin_type(self):
        ptype = self.pin_type_combo.currentText()
        path, _ = QFileDialog.getOpenFileName(self, f'Import/Replace {ptype} PinType JSON', '', 'JSON (*.json)')
        if not path:
            return
        try:
            payload = json.loads(Path(path).read_text(encoding='utf-8'))
            attrs = (((payload.get('pin_types') or {}).get(ptype) or {}).get('attributes')
                     if isinstance(payload, dict) else None)
            if attrs is None and isinstance(payload, dict):
                attrs = payload.get('attributes')
            if not isinstance(attrs, list):
                raise ValueError('Expected JSON with {"attributes": [...]} or {"pin_types": {"%s": {"attributes": [...]}}}.' % ptype)
            self.data.setdefault('pin_types', {}).setdefault(ptype, {'attributes': []})['attributes'] = attrs
            self._load_attrs_into_table(self.pin_attr_table, attrs)
        except Exception as exc:
            QMessageBox.warning(self, 'Import PinType Profile', str(exc))

    def export_current_part_type(self):
        self._save_current_part_profile()
        part = self.part_type_combo.currentText().strip() or 'DEFAULT'
        path, _ = QFileDialog.getSaveFileName(self, f'Export {part} PartType JSON', f'part_type_{part}.json', 'JSON (*.json)')
        if not path:
            return
        payload = {'version': 1, 'part_types': {part: self.data.get('part_types', {}).get(part, {'attributes': []})}}
        Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')

    def import_current_part_type(self):
        part = self.part_type_combo.currentText().strip() or 'DEFAULT'
        path, _ = QFileDialog.getOpenFileName(self, f'Import/Replace {part} PartType JSON', '', 'JSON (*.json)')
        if not path:
            return
        try:
            payload = json.loads(Path(path).read_text(encoding='utf-8'))
            attrs = (((payload.get('part_types') or {}).get(part) or {}).get('attributes')
                     if isinstance(payload, dict) else None)
            if attrs is None and isinstance(payload, dict):
                attrs = payload.get('attributes')
            if not isinstance(attrs, list):
                raise ValueError('Expected JSON with {"attributes": [...]} or {"part_types": {"%s": {"attributes": [...]}}}.' % part)
            self.data.setdefault('part_types', {}).setdefault(part, {'attributes': []})['attributes'] = attrs
            self._load_attrs_into_table(self.part_attr_table, attrs)
        except Exception as exc:
            QMessageBox.warning(self, 'Import PartType Profile', str(exc))
