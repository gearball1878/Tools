from __future__ import annotations
import copy
import csv
import json
import re
import pickle
import math
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
from symbol_wizard.graphics.items import BodyItem, PinItem, TextItem, GraphicItem, pen_for
from symbol_wizard.io.json_store import save_library, load_library, save_symbol, load_symbol
from symbol_wizard.io.mentor_sym import import_mentor_sym, import_mentor_symbols, export_mentor_sym

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
    """Global UI guard: mouse wheel scrolls panels/views only.

    QComboBox and spin box values are often changed accidentally while the user
    scrolls a long property panel. This filter blocks wheel based value changes
    for every combo/spin/dropdown in the complete tool. Values can still be
    changed via the dropdown, arrow buttons, keyboard, or direct numeric input.
    """
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and isinstance(obj, (QComboBox, QAbstractSpinBox)):
            event.ignore()
            return True
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
        self.function_edit_combo = QComboBox()
        self.function_edit_combo.addItems(['Unchanged', 'Set to text', 'Clear', 'Copy from Pin Name', 'Copy from Pin Number'])
        self.function_edit_combo.setMinimumWidth(180)
        self.function_edit_text = QLineEdit()
        self.function_edit_text.setPlaceholderText('New Pin Function')
        self.function_edit_text.setMinimumWidth(260)
        self.function_edit_text.setEnabled(False)
        self.function_edit_combo.currentTextChanged.connect(lambda text: self.function_edit_text.setEnabled(text == 'Set to text'))
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
        function_mode = self._function_edit_mode()
        function_change = function_mode != 'Unchanged'
        if not values and not function_change:
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
            if function_change:
                pin.function = self._new_function_value(pin)
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
        self.selection_enabled = {'BODY': True, 'PIN': True, 'TEXT': True, 'GRAPHIC': True}
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
        self.template_grid_combo.addItems(['0.100"', '0.050"', '0.025"'])
        self.template_grid_combo.setCurrentText('0.050"')
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
        for tool, label in [(DrawTool.SELECT, 'Select/Edit'), (DrawTool.PIN_LEFT, 'Pin L'), (DrawTool.PIN_RIGHT, 'Pin R'), (DrawTool.PIN_TOP, 'Pin T'), (DrawTool.PIN_BOTTOM, 'Pin B'), (DrawTool.TEXT, 'Text'), (DrawTool.LINE, 'Line'), (DrawTool.RECT, 'Rect'), (DrawTool.ELLIPSE, 'Ellipse')]:
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
        self.selection_mode_combo.addItems(['ALL', 'BODY', 'PIN', 'TEXT', 'GRAPHIC', 'Custom'])
        self.selection_mode_combo.currentTextChanged.connect(self.set_selection_mode)
        self.selection_mode_combo.activated.connect(lambda *_: self.set_selection_mode(self.selection_mode_combo.currentText()))
        tools.addWidget(self.selection_mode_combo)
        self.selection_custom_checks = {}
        for kind in ('BODY', 'PIN', 'TEXT', 'GRAPHIC'):
            cb = QCheckBox(kind); cb.setChecked(True); cb.setVisible(False)
            cb.toggled.connect(lambda checked, k=kind: self.set_selection_enabled(k, checked))
            self.selection_custom_checks[kind] = cb
            tools.addWidget(cb)
        self.set_selection_mode(self.selection_mode_combo.currentText())
        tools.addStretch(); layout.addLayout(tools)
        splitter = QSplitter()
        splitter.addWidget(self.view)

        # Keep the property panel usable for symbols/templates with many attributes.
        # The form itself is placed inside a scroll area, so all dynamically generated
        # body attributes, pin settings, text settings and graphic settings remain reachable.
        side = QWidget()
        self.form = QFormLayout(side)
        self.form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self.props_scroll = QScrollArea()
        self.props_scroll.setWidgetResizable(True)
        self.props_scroll.setWidget(side)
        splitter.addWidget(self.props_scroll)
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
        except Exception:
            pass
        for _g in getattr(self.unit, 'graphics', []) or []:
            try: _g.locked_to_body = True
            except Exception: pass
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
                preview=QLabel(f'{k}: {self.unit.body.attributes.get(k, '')}' if str(self.unit.body.attributes.get(k, '')).strip() else k)
                cb.toggled.connect(lambda v, key=k: self._set_attr_vis(key, v))
                l.addWidget(cb); l.addWidget(preview); self.form.addRow(k, row)
            return
        item = sel[0]; kind = item.data(0); m = item.model
        self.form.addRow(QLabel(f'<b>{kind}</b>'))
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
            for k in sorted((getattr(m, 'attributes', {}) or {}).keys()):
                row=QWidget(); l=QHBoxLayout(row); l.setContentsMargins(0,0,0,0)
                cb=QCheckBox('visible'); cb.setChecked((getattr(m, 'visible_attributes', {}) or {}).get(k, False))
                ed=QLineEdit(str((getattr(m, 'attributes', {}) or {}).get(k, '')))
                cb.toggled.connect(lambda v, key=k, model=m: self._set_pin_custom_attr_visible(model, key, v))
                ed.editingFinished.connect(lambda key=k, model=m, e=ed: self._set_pin_custom_attr_value(model, key, e.text()))
                l.addWidget(cb); l.addWidget(ed); self.form.addRow(k, row)
        elif kind in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY'):
            is_attr = kind in ('ATTR_REF_DES', 'ATTR_BODY') or bool(getattr(m, '_is_attribute_text', False))
            line = self._line(m.text, lambda v, item=item: self._set_text_item_attr(item, 'text', v)) if is_attr else self._plain_text_editor(m.text, lambda v, item=item: self._set_text_item_attr(item, 'text', v))
            if is_attr:
                line.setReadOnly(True)
                line.setToolTip('Attribute text content is driven by the owning object attribute value.')
            self.form.addRow('Text', line)
            self.form.addRow('Font', self._font_combo(m.font_family, lambda v, item=item: self._set_text_item_attr(item, 'font_family', v)))
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
            pin.attribute_texts[key] = TextModel(text=f'{key}: {pin.attributes.get(key, '')}' if str(pin.attributes.get(key, '')).strip() else str(key), x=pin.x, y=pin.y - 1, font_size_grid=.45)
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

    def rebuild_props(self):
        """Compatibility wrapper for older callbacks: rebuild the property panel."""
        return self.refresh_properties()

    def _line(self, value, fn):
        w=QLineEdit(str(value)); w.returnPressed.connect(lambda widget=w: fn(widget.text())); return w
    def _plain_text_editor(self, value, fn):
        w = QTextEdit(str(value))
        w.setAcceptRichText(False)
        w.setFixedHeight(72)
        old_key_press = w.keyPressEvent
        def key_press(event, editor=w):
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
                fn(editor.toPlainText())
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
        pins = [getattr(i, 'model', None) for i in pin_items if getattr(i, 'model', None) is not None and i.data(0) == 'PIN']
        values = [bool(getattr(p, attr, False)) for p in pins]
        cb = QCheckBox()
        cb.setTristate(True)
        if values and all(values):
            cb.setCheckState(Qt.Checked)
        elif values and not any(values):
            cb.setCheckState(Qt.Unchecked)
        else:
            cb.setCheckState(Qt.PartiallyChecked)
        cb.stateChanged.connect(lambda state, a=attr, items=pin_items: self._apply_multi_pin_visibility_state(items, a, state))
        return cb

    def _common_model_value(self, items, attr, default=''):
        vals = [getattr(getattr(i, 'model', None), attr, default) for i in items if getattr(i, 'model', None) is not None]
        if not vals:
            return default
        first = vals[0]
        return first if all(v == first for v in vals) else default



    def _common_pin_value(self, items, attr, default=''):
        vals = [getattr(getattr(i, 'model', None), attr, default) for i in items if getattr(i, 'model', None) is not None and i.data(0) == 'PIN']
        if not vals:
            return default
        first = vals[0]
        return first if all(v == first for v in vals) else default

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
        for label, fn in [('Align L', lambda _checked=False, its=items: self.align_text_objects(its, 'left')), ('Align R', lambda _checked=False, its=items: self.align_text_objects(its, 'right')), ('Align Top', lambda _checked=False, its=items: self.align_text_objects(its, 'upper')), ('Align Bottom', lambda _checked=False, its=items: self.align_text_objects(its, 'lower'))]:
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

    def _set_selected_pins_attr(self, pin_items, attr, value):
        pins = [getattr(i, 'model', None) for i in pin_items if getattr(i, 'model', None) is not None and i.data(0) == 'PIN']
        if not pins or len(pins) != len(pin_items): return
        if attr not in ('function', 'visible_number', 'visible_name', 'visible_function', 'length', 'line_style', 'line_width', 'color'): return
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
        filter_kind = 'TEXT' if kind in ('ATTR_REF_DES', 'ATTR_BODY') else kind
        selectable = self.selection_enabled.get(filter_kind, True)
        # BODY remains selectable/movable in the Symbol Wizard because it is the
        # logical object that owns template/import graphics, pins and attributes.
        # Only its body-owned graphic primitives are locked there; primitive
        # editing stays restricted to the Template Editor.
        # Imported Mentor/template body graphics are a single locked body group in the Symbol Wizard.
        # They are only editable in the Template Editor.
        if kind == 'GRAPHIC' and getattr(getattr(item, 'model', None), 'locked_to_body', False) and not getattr(self, 'is_template_editor', False):
            selectable = False
        item.setFlag(QGraphicsItem.ItemIsSelectable, selectable)
        # Attribute text is content-locked but can still be moved/rotated/font-aligned when TEXT is selectable.
        item.setFlag(QGraphicsItem.ItemIsMovable, selectable)
        try:
            item.setAcceptedMouseButtons(Qt.AllButtons if selectable else Qt.NoButton)
        except Exception:
            pass
        if not selectable:
            item.setSelected(False)
        z = {'BODY': 0, 'GRAPHIC': 1, 'TEXT': 2, 'ATTR_REF_DES': 2, 'ATTR_BODY': 2, 'PIN': 3}.get(kind, -1)
        item.setZValue(z)

    def _apply_selection_filter_to_scene(self):
        """Apply the current object-type selection filter to all canvas items.

        This is used by both preset modes and Custom mode. It also forcibly
        deselects objects that are no longer selectable, which prevents stale
        selections after switching filters or after a rubber-band selection.
        """
        for item in self.scene.items():
            if item.data(0) in self.selection_enabled or item.data(0) in ('ATTR_REF_DES', 'ATTR_BODY'):
                self.apply_item_selectability(item)
                filter_kind = 'TEXT' if item.data(0) in ('ATTR_REF_DES', 'ATTR_BODY') else item.data(0)
                if not self.selection_enabled.get(filter_kind, True):
                    item.setSelected(False)

    def set_selection_mode(self, mode):
        custom = (mode == 'Custom')
        if hasattr(self, 'selection_custom_checks'):
            for kind, cb in self.selection_custom_checks.items():
                cb.setVisible(custom)
                # QToolBar.addWidget wraps widgets in QWidgetAction; changing
                # only the checkbox visibility is not enough on some Qt styles.
                if hasattr(self, 'selection_custom_actions') and kind in self.selection_custom_actions:
                    self.selection_custom_actions[kind].setVisible(custom)
        if mode == 'Custom':
            # In Custom mode, the checkboxes are authoritative.  Do not leave
            # the scene in the previous preset state; re-apply the currently
            # checked custom flags immediately.
            if hasattr(self, 'selection_custom_checks'):
                for kind, cb in self.selection_custom_checks.items():
                    self.selection_enabled[kind] = cb.isChecked()
            self._apply_selection_filter_to_scene()
            self.refresh_properties()
            return
        for kind in ('BODY', 'PIN', 'TEXT', 'GRAPHIC'):
            self.selection_enabled[kind] = (mode == 'ALL' or mode == kind)
            if hasattr(self, 'selection_custom_checks'):
                self.selection_custom_checks[kind].blockSignals(True)
                self.selection_custom_checks[kind].setChecked(self.selection_enabled[kind])
                self.selection_custom_checks[kind].blockSignals(False)
        self._apply_selection_filter_to_scene()
        self.refresh_properties()

    def set_selection_enabled(self, kind, checked):
        self.selection_enabled[kind] = bool(checked)
        if hasattr(self, 'selection_mode_combo') and self.selection_mode_combo.currentText() != 'Custom':
            self.selection_mode_combo.blockSignals(True)
            self.selection_mode_combo.setCurrentText('Custom')
            self.selection_mode_combo.blockSignals(False)
            if hasattr(self, 'selection_custom_checks'):
                for kind, cb in self.selection_custom_checks.items():
                    cb.setVisible(True)
                    if hasattr(self, 'selection_custom_actions') and kind in self.selection_custom_actions:
                        self.selection_custom_actions[kind].setVisible(True)
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
        for item in self.scene.items():
            kind = item.data(0)
            filter_kind = 'TEXT' if kind in ('ATTR_REF_DES', 'ATTR_BODY') else kind
            if (kind in ('PIN','TEXT','ATTR_REF_DES','ATTR_BODY','GRAPHIC','BODY')) and not (kind == 'GRAPHIC' and getattr(getattr(item, 'model', None), 'locked_to_body', False) and not getattr(self, 'is_template_editor', False)) and self.selection_enabled.get(filter_kind, True): item.setSelected(True)
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
        filter_kind = 'TEXT' if kind in ('ATTR_REF_DES', 'ATTR_BODY') else kind
        selectable = self.selection_enabled.get(filter_kind, True)
        # BODY remains selectable/movable in the Symbol Wizard because it is the
        # logical object that owns template/import graphics, pins and attributes.
        # Only its body-owned graphic primitives are locked there; primitive
        # editing stays restricted to the Template Editor.
        # Imported Mentor/template body graphics are a single locked body group in the Symbol Wizard.
        # They are only editable in the Template Editor.
        if kind == 'GRAPHIC' and getattr(getattr(item, 'model', None), 'locked_to_body', False) and not getattr(self, 'is_template_editor', False):
            selectable = False
        item.setFlag(QGraphicsItem.ItemIsSelectable, selectable)
        # Attribute text is content-locked but can still be moved/rotated/font-aligned when TEXT is selectable.
        item.setFlag(QGraphicsItem.ItemIsMovable, selectable)
        try:
            item.setAcceptedMouseButtons(Qt.AllButtons if selectable else Qt.NoButton)
        except Exception:
            pass
        if not selectable:
            item.setSelected(False)
        z = {'BODY': 0, 'GRAPHIC': 1, 'TEXT': 2, 'ATTR_REF_DES': 2, 'ATTR_BODY': 2, 'PIN': 3}.get(kind, -1)
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
        elif mode == 'right':
            target = round(max(r['right'] for r in rects.values()))
            for i in txt:
                i.model.h_align = 'right'; i.model.x = target; i.apply_text_from_model()
        elif mode == 'upper':
            target = round(max(r['top'] for r in rects.values()))
            for i in txt:
                i.model.v_align = 'upper'; i.model.y = target; i.apply_text_from_model()
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



