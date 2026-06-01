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
        for tool, label in [(DrawTool.SELECT, 'Select/Edit'), (DrawTool.PIN_LEFT, 'Pin L'), (DrawTool.PIN_RIGHT, 'Pin R'), (DrawTool.TEXT, 'Text'), (DrawTool.LINE, 'Line'), (DrawTool.RECT, 'Rect'), (DrawTool.ELLIPSE, 'Ellipse')]:
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



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        install_no_wheel_value_filter(self)
        self._autosave_path = Path.home() / '.symbol_wizard_autosave.json'
        self.library = self._load_autosave_library()
        self.current_unit_index = 0
        self.draw_tool = DrawTool.SELECT.value
        self.clipboard: list[tuple[str, object]] = []
        self.clipboard_is_cut = False
        self.undo_stack: list[LibraryModel] = []
        self.redo_stack: list[LibraryModel] = []
        self.max_history = 100
        self._history_guard = False
        self.dirty = False
        self._dirty_symbol_index: int | None = None
        self._clean_symbol_snapshot: SymbolModel | None = None
        self.symbol_templates: dict[str, SymbolUnitModel] = {}
        self.suspend = False
        self._selection_restore_ids: set[int] = set()
        self.default_color = (0, 0, 0)
        self.edit_grid_inch = 0.100
        self._refresh_visual_only = False
        self._format_guide_offset = (0.0, 0.0)
        self.selection_enabled = {'BODY': True, 'PIN': True, 'TEXT': True, 'GRAPHIC': True}
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self._scheduled_refresh)
        self.scene = SymbolScene(self)
        self.view = SymbolView(self.scene, self)
        self.setWindowTitle('Symbol Wizard')
        self.resize(1600, 980)
        self._build_ui()
        self.rebuild_all()
        if self.library.symbols:
            QTimer.singleShot(0, self.zoom_to_fit_symbol)


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
        """Throttle property-panel updates caused by live canvas edits."""
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
        """Called by canvas items after move/resize/rotate/scale without rebuilding the scene."""
        try:
            self.live_refresh()
        except Exception:
            pass
        self.schedule_property_refresh()

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
        # Base logical grid for stored JSON coordinates, normally 0.100 inch.
        return self.symbol.grid_inch * PX_PER_INCH

    @property
    def edit_grid_px(self) -> float:
        return float(getattr(self, 'edit_grid_inch', self.symbol.grid_inch) or self.symbol.grid_inch) * PX_PER_INCH

    @property
    def edit_grid_step(self) -> float:
        base = float(getattr(self.symbol, 'grid_inch', 0.100) or 0.100)
        edit = float(getattr(self, 'edit_grid_inch', base) or base)
        if edit <= 0:
            return 1.0
        return max(0.01, edit / base)

    def snap_grid_value(self, v):
        step = self.edit_grid_step
        return round(float(v) / step) * step

    def scene_to_grid_x(self, x):
        return self.snap_grid_value(x / self.grid_px)

    def scene_to_grid_y(self, y):
        return self.snap_grid_value(-y / self.grid_px)

    def _font_families(self):
        try:
            return QFontDatabase.families()
        except Exception:
            return ['Arial', 'Calibri', 'Times New Roman', 'Courier New']

    def _font_combo(self, value, fn):
        w = QComboBox(); w.addItems(self._font_families()); w.setEditable(True); w.setCurrentText(str(value)); w.currentTextChanged.connect(fn); return w

    def _unique_pin_name(self, base='PIN', unit=None):
        unit = unit or self.current_unit
        existing = {str(p.name) for p in unit.pins}
        root = str(base or 'PIN').strip() or 'PIN'
        if root not in existing:
            return root
        i = 2
        while f'{root}_{i}' in existing:
            i += 1
        return f'{root}_{i}'

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self._menu()
        self._ribbon()

        self.single_tabs = QTabWidget()
        self.single_tabs.currentChanged.connect(lambda i: self.change_symbol_from_tab(SymbolKind.SINGLE.value, i))
        self.single_tabs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.single_tabs.customContextMenuRequested.connect(lambda pos: self.symbol_tab_context_menu(SymbolKind.SINGLE.value, self.single_tabs, pos))
        self.split_tabs = QTabWidget()
        self.split_tabs.currentChanged.connect(lambda i: self.change_symbol_from_tab(SymbolKind.SPLIT.value, i))
        self.split_tabs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.split_tabs.customContextMenuRequested.connect(lambda pos: self.symbol_tab_context_menu(SymbolKind.SPLIT.value, self.split_tabs, pos))

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

        self.split_pin_table = self._create_pin_overview_table()

        self.split_object_tree = QTreeWidget()
        self.split_object_tree.setHeaderLabels(['Object', 'Info'])
        self.split_object_tree.itemClicked.connect(self.tree_clicked)

        single_page = QWidget()
        single_layout = QVBoxLayout(single_page)
        single_top = QWidget(); single_top_layout = QVBoxLayout(single_top); single_top_layout.setContentsMargins(0, 0, 0, 0)
        single_top_layout.addWidget(QLabel('Symbols'))
        single_top_layout.addWidget(self.single_tabs)
        single_top_layout.addWidget(QLabel('Pins of selected single symbol'))
        single_top_layout.addWidget(self.single_pin_table, 2)
        single_bottom = QWidget(); single_bottom_layout = QVBoxLayout(single_bottom); single_bottom_layout.setContentsMargins(0, 0, 0, 0)
        single_bottom_layout.addWidget(QLabel('Object Tree'))
        single_bottom_layout.addWidget(self.object_tree)
        self.single_left_splitter = QSplitter(Qt.Vertical)
        self.single_left_splitter.addWidget(single_top)
        self.single_left_splitter.addWidget(single_bottom)
        self.single_left_splitter.setSizes([360, 220])
        single_layout.addWidget(self.single_left_splitter)

        split_page = QWidget()
        split_layout = QVBoxLayout(split_page)
        split_top = QWidget(); split_top_layout = QVBoxLayout(split_top); split_top_layout.setContentsMargins(0, 0, 0, 0)
        split_top_layout.addWidget(QLabel('Split Symbols'))
        split_top_layout.addWidget(self.split_tabs)
        split_top_layout.addWidget(QLabel('Units / Split Parts'))
        split_top_layout.addWidget(self.unit_tabs)
        split_top_layout.addWidget(self.add_unit_button)
        info = QLabel('Verification for split symbols is performed across all units as one symbol.')
        info.setWordWrap(True)
        split_top_layout.addWidget(info)
        split_top_layout.addWidget(QLabel('Pins of selected split part'))
        split_top_layout.addWidget(self.split_pin_table, 2)
        split_bottom = QWidget(); split_bottom_layout = QVBoxLayout(split_bottom); split_bottom_layout.setContentsMargins(0, 0, 0, 0)
        split_bottom_layout.addWidget(QLabel('Object Tree'))
        split_bottom_layout.addWidget(self.split_object_tree, 2)
        self.split_left_splitter = QSplitter(Qt.Vertical)
        self.split_left_splitter.addWidget(split_top)
        self.split_left_splitter.addWidget(split_bottom)
        self.split_left_splitter.setSizes([420, 220])
        split_layout.addWidget(self.split_left_splitter)

        left_tabs = QTabWidget()
        left_tabs.currentChanged.connect(self.left_workspace_changed)
        self.left_tabs = left_tabs
        left_tabs.addTab(single_page, 'Symbols')
        left_tabs.addTab(split_page, 'Split Symbols')

        self.props = QWidget()
        self.form = QFormLayout(self.props)
        self.form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
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
        self.scene.selectionChanged.connect(self.on_scene_selection_changed)

    def _create_pin_overview_table(self):
        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(['Pin Number', 'Pin Name', 'Pin Function', 'Pin Type', 'Side', 'Inverted'])

        # Use delegates instead of setCellWidget(). This prevents the old bug where
        # cell text and combo boxes were painted on top of each other.
        table.setItemDelegateForColumn(3, PinComboDelegate([x.value for x in PinType], table))
        table.setItemDelegateForColumn(4, PinComboDelegate([x.value for x in PinSide], table))
        table.setItemDelegateForColumn(5, PinComboDelegate(['yes', 'no'], table))

        table.cellChanged.connect(self.pin_table_changed)
        table.cellClicked.connect(self.pin_table_clicked)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        table.setWordWrap(False)
        table.horizontalHeader().setStretchLastSection(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(26)
        return table

    def _autosize_table(self, table: QTableWidget):
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        minimums = {0: 100, 1: 110, 2: 130, 3: 120, 4: 105, 5: 110}
        for col in range(table.columnCount()):
            table.setColumnWidth(col, max(table.columnWidth(col) + 24, minimums.get(col, 90)))

    def _fill_pin_table(self, table: QTableWidget, rows):
        table.blockSignals(True)
        table.clearSelection()
        table.clearContents()
        table.setRowCount(0)
        table.setRowCount(len(rows))
        for r, (si, ui, pi, pin) in enumerate(rows):
            values = [pin.number, pin.name, pin.function, pin.pin_type, pin.side, 'yes' if pin.inverted else 'no']
            for c, v in enumerate(values):
                it = QTableWidgetItem(str(v))
                it.setData(Qt.UserRole, (si, ui, pi, c))
                it.setData(Qt.EditRole, str(v))
                it.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                table.setItem(r, c, it)
            self._install_pin_table_combo(table, r, 3, [x.value for x in PinType], pin.pin_type)
            self._install_pin_table_combo(table, r, 4, [x.value for x in PinSide], pin.side)
            self._install_pin_table_combo(table, r, 5, ['yes', 'no'], 'yes' if pin.inverted else 'no')
        self._autosize_table(table)
        table.blockSignals(False)
        table.viewport().update()

    def _install_pin_table_combo(self, table: QTableWidget, row: int, col: int, values: list[str], current: str):
        combo = QComboBox(table)
        combo.addItems(values)
        combo.setCurrentText(str(current))
        combo.currentTextChanged.connect(lambda v, t=table, r=row, c=col: self.pin_table_widget_changed(t, r, c, v))
        table.setCellWidget(row, col, combo)

    def pin_table_widget_changed(self, table: QTableWidget, r: int, c: int, value: str):
        it = table.item(r, c) or table.item(r, 0)
        if not it:
            return
        if table.item(r, c):
            old = table.blockSignals(True)
            table.item(r, c).setText(value)
            table.item(r, c).setData(Qt.EditRole, value)
            table.blockSignals(old)
        self._commit_pin_table_value(table, r, c)

    def open_split_pin_manager(self):
        dlg = SplitPinManagerDialog(self)
        dlg.exec()

    def _menu(self):
        mb = self.menuBar()
        file_menu = mb.addMenu('&File')

        def add_action(menu, label, fn, sc=None):
            a = QAction(label, self)
            a.triggered.connect(fn)
            if sc:
                a.setShortcut(QKeySequence(sc))
            menu.addAction(a)
            return a

        new_menu = file_menu.addMenu('New')
        add_action(new_menu, 'New Single Symbol', self.new_single_symbol, 'Ctrl+N')
        add_action(new_menu, 'New Split Symbol', self.new_split_symbol, 'Ctrl+Shift+N')

        project_menu = file_menu.addMenu('Project / JSON')
        add_action(project_menu, 'Open Library JSON', self.open_library, 'Ctrl+O')
        add_action(project_menu, 'Save Current Symbol JSON', self.save_current_symbol, 'Ctrl+S')
        add_action(project_menu, 'Save All Symbols JSON', self.save_all_symbols, 'Ctrl+Shift+S')
        add_action(project_menu, 'Import Symbol JSON', self.import_symbol)

        import_menu = file_menu.addMenu('Import')
        add_action(import_menu, 'Mentor Single Symbol (.sym/.1)', self.import_mentor_symbol)
        add_action(import_menu, 'Mentor Split Symbol ZIP', self.import_mentor_symbol)
        add_action(import_menu, 'PINMUX CSV', self.import_pinmux_csv)

        export_menu = file_menu.addMenu('Export')
        add_action(export_menu, 'Mentor Single/Split Symbol', self.export_current_mentor_symbol)

        file_menu.addSeparator()
        add_action(file_menu, 'Exit', self.close)

        edit_menu = mb.addMenu('&Edit')
        for label, fn, sc in [
            ('Undo', self.undo, 'Ctrl+Z'),
            ('Redo', self.redo, 'Ctrl+Y'),
            ('---', None, None),
            ('Select All Canvas Objects', self.select_all_canvas, 'Ctrl+A'),
            ('Copy', self.copy_selected, 'Ctrl+C'),
            ('Cut', self.cut_selected, 'Ctrl+X'),
            ('Paste', self.paste_selected, 'Ctrl+V'),
            ('Delete', self.delete_selected, 'Del'),
        ]:
            if label == '---':
                edit_menu.addSeparator(); continue
            a = QAction(label, self)
            a.triggered.connect(fn)
            if sc:
                a.setShortcut(QKeySequence(sc))
            edit_menu.addAction(a)


        # Ctrl+Z/Ctrl+Y are assigned only once via the Edit menu actions.
        # Do not install additional QShortcut objects here: Qt reports
        # 'Ambiguous shortcut overload' when the menu QAction and an application
        # shortcut both own the same key sequence.

        edit_menu.addSeparator()
        a = QAction('Delete Current Symbol / Split Symbol', self)
        a.triggered.connect(self.delete_current_symbol)
        edit_menu.addAction(a)
        a = QAction('Clear Canvas', self)
        a.triggered.connect(self.clear_canvas)
        edit_menu.addAction(a)

        tools_menu = mb.addMenu('&Tools')
        a = QAction('Edit Symbol Templates', self)
        a.triggered.connect(self.edit_symbol_templates)
        tools_menu.addAction(a)
        tools_menu.addSeparator()
        a = QAction('Validate Pins', self)
        a.triggered.connect(self.validate_pins)
        tools_menu.addAction(a)
        a = QAction('Split Pin Manager / Multi-Edit Pins', self)
        a.triggered.connect(self.open_split_pin_manager)
        tools_menu.addAction(a)

        view_menu = mb.addMenu('&View')
        for label, fn, sc in [
            ('Zoom to Fit Symbol', self.zoom_to_fit_symbol, 'Ctrl+F'),
            ('Zoom to Fit Sheet', self.zoom_to_fit_sheet, 'Ctrl+Shift+F'),
            ('---', None, None),
            ('Refresh Canvas', self.rebuild_scene, 'F5'),
        ]:
            if label == '---':
                view_menu.addSeparator(); continue
            a = QAction(label, self)
            a.triggered.connect(fn)
            if sc:
                a.setShortcut(QKeySequence(sc))
            view_menu.addAction(a)

        help_menu = mb.addMenu('&Help')
        a = QAction('How To', self)
        a.triggered.connect(self.show_how_to)
        help_menu.addAction(a)
        a = QAction('Class Model', self)
        a.triggered.connect(self.show_class_model)
        help_menu.addAction(a)
        a = QAction('About Symbol Wizard', self)
        a.triggered.connect(self.show_about_dialog)
        help_menu.addAction(a)

    def _ribbon(self):
        """Create permanently visible, grouped edit ribbons.

        The previous single-toolbar layout was too wide and Qt moved actions into
        the overflow menu.  The editor controls are now split into several fixed
        toolbars on separate rows so all edit buttons remain visible.
        """
        def make_bar(title: str) -> QToolBar:
            bar = QToolBar(title)
            bar.setObjectName(title.replace(' ', '_'))
            bar.setMovable(False)
            bar.setFloatable(False)
            self.addToolBar(bar)
            return bar

        # --- Draw tools -------------------------------------------------
        draw_tb = make_bar('Draw Tools')
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
            draw_tb.addAction(a)
            self.tool_buttons[tool.value] = a
        self.tool_buttons[self.draw_tool].setChecked(True)
        draw_tb.addSeparator()
        draw_tb.addWidget(QLabel('Selectable:'))
        self.selection_mode_combo = QComboBox()
        self.selection_mode_combo.addItems(['ALL', 'BODY', 'PIN', 'TEXT', 'GRAPHIC', 'Custom'])
        self.selection_mode_combo.currentTextChanged.connect(self.set_selection_mode)
        self.selection_mode_combo.activated.connect(lambda *_: self.set_selection_mode(self.selection_mode_combo.currentText()))
        draw_tb.addWidget(self.selection_mode_combo)
        self.selection_custom_checks = {}
        self.selection_custom_actions = {}
        for kind in ('BODY', 'PIN', 'TEXT', 'GRAPHIC'):
            cb = QCheckBox(kind)
            cb.setChecked(True)
            cb.setVisible(False)
            cb.toggled.connect(lambda checked, k=kind: self.set_selection_enabled(k, checked))
            self.selection_custom_checks[kind] = cb
            action = draw_tb.addWidget(cb)
            action.setVisible(False)
            self.selection_custom_actions[kind] = action
        self.set_selection_mode(self.selection_mode_combo.currentText())

        # --- Symbol setup -----------------------------------------------
        self.addToolBarBreak()
        setup_tb = make_bar('Symbol Setup')
        # Symbol names and split-part names are changed via the tab context menus.
        # The former Unit/Part edit field was intentionally removed from the ribbon.
        self.symbol_name_edit = None
        self.unit_name_edit = QLineEdit()
        self.unit_name_edit.setVisible(False)
        self.unit_name_edit.editingFinished.connect(self.apply_unit_name_from_edit)

        setup_tb.addWidget(QLabel('Grid inch:'))
        self.grid_spin = QDoubleSpinBox()
        self.grid_spin.setRange(.05, .5)
        self.grid_spin.setSingleStep(.05)
        self.grid_spin.setDecimals(3)
        self.grid_spin.valueChanged.connect(self.set_grid)
        setup_tb.addWidget(self.grid_spin)

        setup_tb.addWidget(QLabel('Edit grid:'))
        self.edit_grid_combo = QComboBox()
        self.edit_grid_combo.addItems(['0.100"', '0.050"', '0.025"'])
        self.edit_grid_combo.setCurrentText('0.100"')
        self.edit_grid_combo.currentTextChanged.connect(self.set_edit_grid)
        setup_tb.addWidget(self.edit_grid_combo)

        setup_tb.addWidget(QLabel('Format:'))
        self.format_combo = QComboBox()
        self.format_combo.addItems([x.value for x in SheetFormat])
        self.format_combo.currentTextChanged.connect(self.set_sheet_format)
        setup_tb.addWidget(self.format_combo)

        zoom_btn = QPushButton('Zoom Fit')
        zoom_btn.clicked.connect(self.zoom_to_fit_symbol)
        setup_tb.addWidget(zoom_btn)
        setup_tb.addWidget(QLabel('Origin:'))
        self.origin_combo = QComboBox()
        self.origin_combo.addItems([x.value for x in OriginMode])
        self.origin_combo.setCurrentText(self.symbol.origin)
        self.origin_combo.currentTextChanged.connect(self.origin_mode_changed)
        setup_tb.addWidget(self.origin_combo)
        origin_btn = QPushButton('Origin Reset')
        origin_btn.clicked.connect(self.reset_origin_to_selected_anchor)
        setup_tb.addWidget(origin_btn)

        # --- Style controls ---------------------------------------------
        self.addToolBarBreak()
        style_tb = make_bar('Style')
        style_tb.addWidget(QLabel('Line:'))
        self.line_style = QComboBox()
        self.line_style.addItems([x.value for x in LineStyle])
        style_tb.addWidget(self.line_style)
        style_tb.addWidget(QLabel('Width grid:'))
        self.line_width = QDoubleSpinBox()
        self.line_width.setRange(.01, 1)
        self.line_width.setSingleStep(.01)
        self.line_width.setValue(.03)
        style_tb.addWidget(self.line_width)
        self.line_style.currentTextChanged.connect(self.apply_line_defaults)
        self.line_width.valueChanged.connect(self.apply_line_defaults)

        color = QPushButton('RGB')
        color.clicked.connect(self.pick_default_color)
        style_tb.addWidget(color)

        # --- Transform controls -----------------------------------------
        transform_tb = make_bar('Transform')
        for label, fn in [
            ('⟲ 90°', lambda: self.rotate_selected(-90)),
            ('⟳ 90°', lambda: self.rotate_selected(90)),
            ('Flip H', self.flip_selected_horizontal),
            ('Flip V', self.flip_selected_vertical),
            ('Scale +', lambda: self.scale_selected_grid(1)),
            ('Scale -', lambda: self.scale_selected_grid(-1)),
            ('Clear Canvas', self.clear_canvas),
        ]:
            b = QPushButton(label)
            b.clicked.connect(fn)
            transform_tb.addWidget(b)

        # --- Pin group edit ---------------------------------------------
        self.addToolBarBreak()
        pin_tb = make_bar('Selected Pin Actions')
        pin_tb.addWidget(QLabel('Selected Pins:'))
        self.selected_pin_side_combo = QComboBox()
        self.selected_pin_side_combo.addItems([x.value for x in PinSide])
        pin_tb.addWidget(self.selected_pin_side_combo)
        b = QPushButton('Assign Side')
        b.clicked.connect(lambda: self.set_selected_pins_side(self.selected_pin_side_combo.currentText()))
        pin_tb.addWidget(b)
        b = QPushButton('Distribute Vertical')
        b.clicked.connect(self.distribute_selected_pins_vertical)
        pin_tb.addWidget(b)

        # Help/About remain available from the Help menu only.
        # They are intentionally not duplicated in the ribbon.

    def show_how_to(self):
        dlg = QDialog(self)
        dlg.setWindowTitle('How To - Symbol Wizard')
        dlg.resize(920, 760)
        layout = QVBoxLayout(dlg)
        browser = QTextBrowser(dlg)
        browser.setOpenExternalLinks(True)
        browser.setMarkdown(self._how_to_markdown())
        layout.addWidget(browser, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close, dlg)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)
        dlg.exec()

    def show_class_model(self):
        dlg = QDialog(self)
        dlg.setWindowTitle('Class Model - Symbol Wizard')
        dlg.resize(980, 820)
        layout = QVBoxLayout(dlg)
        browser = QTextBrowser(dlg)
        browser.setOpenExternalLinks(False)
        browser.setMarkdown(self._class_model_markdown())
        layout.addWidget(browser, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close, dlg)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)
        dlg.exec()

    def _class_model_markdown(self):
        return """# Symbol Wizard - Klassenmodell

Dieses Klassenmodell beschreibt die wichtigsten Daten-, UI-, Grafik- und Import/Export-Klassen des Tools. Es ist als Architekturübersicht gedacht und ergänzt das HowTo.

## 1. Architekturüberblick

```text
LibraryModel
└── SymbolModel [single | split]
    └── SymbolUnitModel [eine Unit / ein Split-Part]
        ├── SymbolBodyModel
        ├── PinModel[]
        ├── TextModel[]
        └── GraphicModel[]

MainWindow
├── SymbolScene / SymbolView
├── PropertiesPanel
├── SplitPinManagerDialog
├── TemplateEditorDialog
└── Import/Export Services
```

Die wichtigste Trennung ist:

- **Model-Klassen** speichern die Symbolsemantik.
- **Graphics-Klassen** rendern und editieren diese Modelle im Canvas.
- **GUI-Klassen** stellen Werkzeuge, Dialoge, Menüs und Properties bereit.
- **IO-Klassen** lesen und schreiben JSON sowie Mentor/Xpedition ASCII.
- **Rules-Klassen** enthalten Grid-, Placement- und Validierungslogik.

## 2. Datenmodell

### LibraryModel

Root-Container der Anwendung.

| Feld / Methode | Bedeutung |
|---|---|
| `symbols: list[SymbolModel]` | alle geladenen Symbole |
| `current_symbol_index` | aktives Symbol |
| `add_symbol()` | neues Single- oder Split-Symbol erzeugen |
| `current_symbol()` | aktives Symbol sicher zurückgeben |
| `unique_symbol_name()` | eindeutige neue Namen erzeugen |
| `unique_import_name()` | Importkonflikte vermeiden |

### SymbolModel

Ein komplettes Symbol oder Split-Symbol.

| Feld | Bedeutung |
|---|---|
| `name` | Symbolname |
| `kind` | `single` oder `split` |
| `is_split` | Legacy-Kompatibilität für Split-Symbole |
| `grid_inch` | Arbeitsraster, z. B. `0.100` inch |
| `sheet_format` | A0 bis A5 |
| `origin` | Origin-Modus |
| `template_name` | genutztes Template / Importmodus |
| `units` | Symbolteile / Split-Parts |

### SymbolUnitModel

Eine logische Unit. Bei Mentor-Split-Symbolen entspricht eine Unit genau einer Datei im ZIP.

| Feld | Bedeutung |
|---|---|
| `name` | Unit-/Split-Part-Name |
| `body` | Symbolkörper |
| `pins` | Pins der Unit |
| `texts` | normale Texte |
| `graphics` | Linien, Rechtecke, Ellipsen |

### SymbolBodyModel

Grafischer und semantischer Hauptkörper einer Unit.

| Feld | Bedeutung |
|---|---|
| `x`, `y`, `width`, `height` | Body-Geometrie |
| `color`, `line_width`, `line_style` | Body-Darstellung |
| `attributes` | Symbolattribute, z. B. `RefDes`, `Value`, `Package` |
| `visible_attributes` | Sichtbarkeit der Body-Attribute |
| `attribute_texts` | persistente Positionen der Attributtexte |
| `attribute_font`, `refdes_font` | Fonts für Attribute und RefDes |
| `refdes_align`, `body_attr_align` | Ausrichtung |

### PinModel

Semantisches Pinmodell. Es ist die wichtigste Klasse für Mentor-Kompatibilität.

| Feld | Bedeutung |
|---|---|
| `number` | physikalische Pin-/Ballnummer |
| `name` | sichtbarer Pinname |
| `function` | Pin-Funktion / Signalbeschreibung |
| `pin_type` | `IN`, `OUT`, `BIDI`, `POWER`, `GROUND`, `ANALOG`, ... |
| `side` | `left` oder `right` |
| `x`, `y`, `length` | Pin-Anker und Länge im Wizard-Modell |
| `inverted` | invertierter Pin |
| `visible_number` | Pin Number anzeigen |
| `visible_name` | Pin Name anzeigen |
| `visible_function` | Pin Function anzeigen |
| `number_font`, `label_font` | Fonts für Nummer und Label/Funktion |
| `attributes` | zusätzliche sichtbare/unsichtbare Pinattribute |
| `visible_attributes` | Sichtbarkeit zusätzlicher Pinattribute |

Mentor-Export nutzt daraus u. a.:

```text
P ...
L ... <pin.name>
A ... #=<pin.number>
A ... PINTYPE=<pin.pin_type>
A ... PINFUNCTION=<pin.function>   ; unsichtbar
```

### TextModel

Normale Texte und Textattribute im Symbol.

| Feld | Bedeutung |
|---|---|
| `text` | Textinhalt |
| `x`, `y` | Textanker |
| `font_family`, `font_size_grid` | Font |
| `color` | Textfarbe |
| `h_align`, `v_align` | Ausrichtung |
| `wrap_text` | mehrzeiliger Umbruch |

### GraphicModel

Grafische Zusatzobjekte.

| Feld | Bedeutung |
|---|---|
| `shape` | `line`, `rect`, `ellipse`, ... |
| `x`, `y`, `w`, `h` | Geometrie |
| `curve_radius` | Rundung / Kurvenradius |
| `style` | Stroke, Fill, Line Width, Line Style |

### TransformModel

Basisklasse für transformierbare Modelle.

| Feld | Bedeutung |
|---|---|
| `rotation` | Rotation in Grad |
| `scale_x`, `scale_y` | Skalierung |

### FontModel

Gemeinsames Fontmodell.

| Feld | Bedeutung |
|---|---|
| `family` | Fontfamilie |
| `size_grid` | Größe in Grid-Einheiten |
| `color` | RGB-Farbe |

### StyleModel

Gemeinsames Linien-/Füllmodell.

| Feld | Bedeutung |
|---|---|
| `stroke` | Linienfarbe |
| `fill` | Füllfarbe oder `None` |
| `line_width` | Linienbreite in Grid-Einheiten |
| `line_style` | solid, dash, dot, dash_dot |

## 3. Enumerations

| Enum | Werte / Zweck |
|---|---|
| `PinType` | IN, OUT, BIDI, PASSIVE, POWER, GROUND, ANALOG |
| `PinSide` | left, right |
| `OriginMode` | bottom_left, bottom_right, center, top_left, top_right |
| `DrawTool` | select, pin_left, pin_right, text, line, rect, ellipse |
| `SymbolKind` | single, split |
| `SheetFormat` | A0, A1, A2, A3, A4, A5 |
| `LineStyle` | solid, dash, dot, dash_dot |
| `TextHAlign` | left, center, right |
| `TextVAlign` | upper, center, lower |

## 4. GUI-Klassen

### MainWindow

Zentrale Anwendungsklasse.

Aufgaben:

- Menüstruktur und Ribbon aufbauen
- Symbol-/Unit-/Canvas-Tabs verwalten
- Zeichenwerkzeuge steuern
- Undo/Redo, Copy/Paste, Delete
- Import/Export auslösen
- Properties, Pin-Tabelle und Objektbaum synchronisieren
- Canvas neu aufbauen
- Autosave/Restore verwalten
- Help/HowTo/Klassenmodell anzeigen

### PropertiesPanel

Eigenschaftseditor rechts im Hauptfenster.

Aufgaben:

- ausgewählte Objekte lesen
- editierbare Felder anzeigen
- Änderungen ins Modell zurückschreiben
- Body-, Pin-, Text- und Grafikattribute bearbeiten

### SplitPinManagerDialog

Zentrales Multi-Edit-Fenster für Pins.

Aufgaben:

- alle Pins eines Single- oder Split-Symbols tabellarisch anzeigen
- spaltenweise Filter unter den Spaltenüberschriften anbieten
- Bool-Filter für `Show #`, `Show Name`, `Show Function`, `Inverted`
- Sortieren, Markieren, Doppelklick-Navigation
- Bulk-Edit für Sichtbarkeit, Inverted und Pin Function

### TemplateEditorDialog

Editor für wiederverwendbare Symboltemplates.

Aufgaben:

- Template-Body, Pins, Texte und Grafiken bearbeiten
- nur bei echten Änderungen Save-Prompt auslösen
- Template-Daten für neue Symbole bereitstellen

### PinComboDelegate

Qt-Delegate für Dropdown-Zellen in Pin-Tabellen.

Aufgaben:

- ComboBox nur während der Bearbeitung erzeugen
- doppelte Textdarstellung vermeiden
- saubere Darstellung für Pin-Typen oder Bool-Felder

### NoWheelOnValueWidgets

Globaler Eventfilter.

Aufgaben:

- verhindert versehentliche Wertänderungen per Mausrad in ComboBoxen und SpinBoxen
- Scrollen in Panels bleibt möglich

## 5. Grafik-/Canvas-Klassen

### SymbolScene

QGraphicsScene für das aktive Symbol.

Aufgaben:

- Sheet-/Formatrahmen und Zeichenbereich rendern
- Origin und Grid darstellen
- Body-, Pin-, Text- und Grafikitems verwalten
- Selektion und Geometrieänderungen an MainWindow melden

### SymbolView

QGraphicsView für die Scene.

Aufgaben:

- Zoom, Pan, Viewport-Darstellung
- Maus-/Keyboard-Interaktion weiterreichen
- Canvas angenehm navigierbar machen

### TransformMixin

Gemeinsame Transformationslogik für Canvas-Items.

Aufgaben:

- Rotation, Skalierung und Flip anwenden
- Modell und grafisches Item synchron halten

### BodyItem

Grafische Darstellung von `SymbolBodyModel`.

Aufgaben:

- Body-Rechteck rendern
- Body verschieben/skalieren
- Attribute und RefDes passend positionieren

### PinItem

Grafische Darstellung von `PinModel`.

Aufgaben:

- Pinlinie, Pin Number, Pin Name und Pin Function zeichnen
- Pinfarben nach PinType-Palette darstellen
- Pinanker auf Grid halten
- Inverted-Status visualisieren

### TextItem

Grafische Darstellung von `TextModel`.

Aufgaben:

- Textanker und Ausrichtung rendern
- Fontgröße, Farbe, Rotation und Umbruch anwenden

### GraphicItem

Grafische Darstellung von `GraphicModel`.

Aufgaben:

- Linien, Rechtecke und Ellipsen zeichnen
- Style, Breite, Fill und Transformation anwenden

## 6. Import-/Export-Klassen und Funktionen

### json_store

Funktionen:

| Funktion | Zweck |
|---|---|
| `save_library()` | komplette Library als JSON speichern |
| `load_library()` | Library JSON laden |
| `save_symbol()` | einzelnes Symbol speichern |
| `load_symbol()` | einzelnes Symbol laden |

### mentor_sym

Funktionen:

| Funktion | Zweck |
|---|---|
| `import_mentor_sym()` | einzelne `.sym/.1` oder Split-ZIP importieren |
| `export_mentor_sym()` | Single-Datei oder Split-ZIP exportieren |
| `_import_native_single()` | natives Mentor-ASCII parsen |
| `_export_native_unit()` | eine Unit als Mentor-ASCII schreiben |
| `_mentor_key_id()` | stabile CRC32-basierte `K`-ID erzeugen |
| `_mentor_revision_timestamp()` | Mentor-Zeitstempel `H:MM:SS_M-D-YY` erzeugen |

Mentor-Split-Regel:

- Split Import: ZIP-Datei, jede Datei = eine `SymbolUnitModel`
- Split Export: eine ZIP-Datei, jede Unit = eine `.1` Datei
- Single Import/Export: eine einzelne `.sym` oder `.1` Datei

## 7. Rules-Klassen / Logikmodule

### grid.py

Aufgaben:

- Grid-Konstanten wie `PX_PER_INCH`
- Pin-Validierung, z. B. doppelte Pin-Nummern
- nächste freie Pin-Nummer bestimmen

### placement.py

Aufgaben:

- automatische Pin-Erzeugung
- Standardpositionen für neue Pins
- Platzierungsregeln relativ zum Body

## 8. Typische Datenflüsse

### Wizard JSON laden

```text
JSON file
→ json_store.load_library/load_symbol
→ LibraryModel / SymbolModel
→ MainWindow.rebuild_all()
→ SymbolScene + PropertiesPanel + Pin-Tabellen
```

### Mentor Split ZIP importieren

```text
ZIP
→ import_mentor_sym()
→ jede Datei parsen
→ SymbolUnitModel pro Datei
→ SymbolModel(kind='split')
→ Canvas/Pin Manager
```

### Mentor Split ZIP exportieren

```text
SymbolModel(kind='split')
→ export_mentor_sym()
→ jede Unit durch _export_native_unit()
→ ZIP mit einer .1 Datei pro Unit
```

### Pin im Split Pin Manager ändern

```text
SplitPinManagerDialog
→ PinModel ändern
→ MainWindow.mark_dirty()
→ rebuild_scene/rebuild_pin_table
→ optional Mentor Export
```

## 9. Mentor-relevante Designregeln

- Mentor-Dateien enthalten normalerweise keine RGB-Farben; Pinfarben sind Wizard-UI-Palette.
- Elektrisch entscheidend sind Pin-Ankerkoordinaten.
- `PinModel.number` wird als `#=` exportiert.
- `PinModel.pin_type` wird als `PINTYPE=` exportiert.
- `PinModel.function` wird als unsichtbares `PINFUNCTION=` exportiert.
- Zusätzliche `PinModel.attributes` können als unsichtbare `A`-Records exportiert werden.
- Split-Symbole kommen und gehen als ZIP.
- Einzelne Symbole kommen und gehen als einzelne Dateien.

## 10. Erweiterungspunkte

| Bereich | Erweiterung |
|---|---|
| Pinmodell | weitere Pinattribute, Diffpair, Swapgroup, Bank |
| Mentor Export | zusätzliche native `A`-/`U`-Records |
| Split Pin Manager | weitere Bulk-Edit-Felder |
| Templates | Firmenstandards, Body-Stile, Attributlayouts |
| Validation | ERC-Regeln, Bankregeln, DDR-/Diffpair-Prüfung |
| UI | weitere Filter, Farbschemata, Theme-Unterstützung |

"""

    def show_about_dialog(self):
        QMessageBox.about(
            self,
            'About Symbol Wizard',
            'Symbol Wizard\n\n'
            'A grid-based editor for creating and maintaining Xpedition symbol definitions, templates, pins, text attributes, and graphic objects.\n\n'
            'Editor: Christian Hopper\n'
            'Company: QAVION Consulting GmbH\n'
            'Customer: Liebherr Electronics and Drives\n'
            'Year: 2026'
        )

    def _how_to_markdown(self):
        return """# Symbol Wizard - How To Guide

## 1. Purpose

Symbol Wizard is a grid-based editor for creating, editing, validating, importing, and exporting electronic symbols for Xpedition/Mentor-oriented workflows. It supports both single symbols and split symbols with multiple units/parts.

The main design goals are:

- consistent grid-based symbol construction
- reliable pin and attribute management
- Mentor/Xpedition ASCII import/export
- split-symbol handling through ZIP archives
- reusable templates
- fast multi-edit workflows for large FPGA symbols

## 2. Main Window Overview

The window is divided into three areas:

- **Left workspace**: symbol lists, split-symbol units, pin overview, and object tree.
- **Center canvas**: graphical editor with grid, sheet/format preview, origin, body, pins, text, attributes, and graphics.
- **Right properties panel**: properties for the selected object or selection.

The ribbon contains drawing tools, grid/sheet/origin settings, style controls, transform controls, and pin actions.

## 3. File Menu Structure

The **File** menu is grouped by workflow.

### New

- **New Symbol** creates a single symbol.
- **New Split Symbol** creates a split symbol with one or more units.

### Project / JSON

- **Open Library JSON** loads a previously saved Wizard library.
- **Save Current Symbol JSON** saves only the active symbol.
- **Save All Symbols JSON** saves the complete library.
- **Import Symbol JSON** imports one Wizard JSON symbol into the current library.

### Mentor Import

- **Import Mentor Single Symbol** imports one `.sym` or `.1` Mentor/Xpedition ASCII file as a single symbol.
- **Import Mentor Split ZIP** imports a ZIP archive as one split symbol. Each Mentor file in the ZIP becomes one split part/unit.

### Mentor Export

- **Export Mentor Single Symbol** exports the current single symbol as one native Mentor ASCII file.
- **Export Mentor Split ZIP** exports the current split symbol as a ZIP archive. Each split part/unit is written as one native Mentor ASCII file.

### Other Imports

- **Import PINMUX CSV** imports pin data from a CSV file.

## 4. Single Symbols and Split Symbols

A **single symbol** is one graphical symbol file.

A **split symbol** is one logical component split into multiple units/parts. Split-symbol validation is performed across all units, because pin numbers must be unique across the complete component.

For Mentor/Xpedition workflows:

- Split symbols are imported and exported as `.zip` files.
- Every file inside the ZIP is one split part/unit.
- Single symbols are imported and exported as one `.sym` or `.1` file.

## 5. Grid, Sheet Format, Drawing Area, and Origin

Use **Grid inch** to define the working grid. Mentor symbols commonly use a 10 mil internal grid (`Z 10`) with pin anchors on grid coordinates.

Use **Format** to show A0/A1/A2/A3/A4/A5 sheet guides. The canvas shows the sheet/format frame and the drawing/usable region so symbols can be checked visually against the selected format.

Use **Zoom Fit** to fit the current symbol and sheet preview into the view.

### Origin behavior

Imported symbols are initially aligned to the selected origin by the **body itself**, not by pins, labels, or stray graphics. This keeps the body placement predictable.

For native Mentor/Xpedition symbols, the Wizard preserves the Mentor coordinate origin. The Mentor origin is the symbol placement origin from the `.sym/.1` file. The body may start at an offset such as `b 30 30 ...`; this is normal for Mentor symbols. Pin electrical anchors remain the most important grid points.

## 6. Creating and Editing Objects

Use the draw tools:

- **Select/Edit**: select and edit existing objects.
- **Pin L / Pin R**: create left- or right-oriented pins.
- **Text**: create plain text.
- **Line, Rect, Ellipse**: create graphic objects.

The **Selectable** dropdown limits selection to specific object types. This helps when editing dense symbols.

Objects can be moved, resized, rotated, flipped, scaled, copied, pasted, and deleted. Deleting a symbol, split symbol, split part, or all symbols asks for confirmation because the changes are destructive.

## 7. Body Editing

The body is the main symbol container. Its size, position, style, line width, and attributes can be edited from the properties panel.

When the body moves or is resized, related pins, text, graphics, and body attributes are kept consistent with the body.

The body does not have to lie on the same visual offset as pins. For Mentor compatibility, the important electrical rule is that **pin connection points** stay on the Mentor grid.

## 8. Pin Editing

Pins can be edited from:

- the canvas
- the left pin overview
- the object tree
- the properties panel
- the Split Pin Manager

Common pin fields are:

- **Pin Number**: physical pin / ball number
- **Pin Name**: visible logical label
- **Pin Function**: functional signal description
- **Pin Type**: electrical type, e.g. `IN`, `OUT`, `BIDI/BI`, `POWER`, `GROUND`, `ANALOG`
- **Side**: left/right/top/bottom placement direction
- **Inverted**: pin inversion flag
- **Show #**, **Show Name**, **Show Function**: visibility controls

Pin Name and Pin Function are independent. If both are visible, both may be shown in the Wizard.

## 9. Pin Colors

Mentor `.sym/.1` files normally do not store RGB object colors. The Wizard therefore colors pins semantically by pin type for editing clarity:

- `IN` = blue
- `OUT` = red
- `BIDI` / `BI` = violet
- `POWER` = orange
- `GROUND` = green
- `ANALOG` = cyan
- `PASSIVE` / unknown = black

These are Wizard UI colors. Native Mentor export does not write RGB colors unless a future format extension explicitly supports it.

## 10. Split Pin Manager / Multi-Edit Pins

Open **Tools → Split Pin Manager / Multi-Edit Pins** to view and edit all pins of the current symbol or split symbol in one table.

### Table features

- Shows all pins across all split units.
- Supports marking rows for later bulk operations.
- Supports sorting by clicking column headers.
- Double-click a pin row to jump to that pin on the canvas.
- Use **Marked only** to display only marked pins.

### Embedded column filters

Filters are integrated directly into the table as the first row below the column headers.

Text columns use text filters:

- Unit
- Pin Number
- Pin Name
- Pin Function
- Type

Boolean columns use dropdown filters:

- **Inverted**: `All`, `Inverted`, `Not inverted`
- **Show #**: `All`, `Shown`, `Hidden`
- **Show Name**: `All`, `Shown`, `Hidden`
- **Show Function**: `All`, `Shown`, `Hidden`

The global filter searches across unit, pin number, pin name, pin function, type, and state. Global and column filters are combined.

Use **Clear filters** to remove all active filters.

### Bulk-edit display attributes

The bulk area at the bottom can apply changes to:

- marked pins
- currently filtered pins
- all pins

Bulk-edit fields include:

- **Show #**: `Unchanged`, `Show`, `Hide`
- **Show Name**: `Unchanged`, `Show`, `Hide`
- **Show Function**: `Unchanged`, `Show`, `Hide`
- **Inverted**: `Unchanged`, `Inverted`, `Not inverted`

### Bulk-edit Pin Function text

The Pin Function Text controls allow mass-editing of the actual Pin Function value:

- `Unchanged`: leave existing function values untouched
- `Set to text`: write the entered text to all target pins
- `Clear`: clear the function text
- `Copy from Pin Name`: copy each pin name into its pin function
- `Copy from Pin Number`: copy each pin number into its pin function

## 11. Mentor/Xpedition Import

Mentor ASCII files use records such as:

- `V` version
- `K` internal key / ID
- `|R` timestamp
- `F` symbol type
- `D` drawing bounds
- `Y`, `Z`, `i` metadata/grid/object count
- `U` symbol/body attributes
- `b` body rectangle
- `T` text
- `P` pin geometry
- `L` pin label
- `A` object/pin attributes
- `E` end marker

During import, the Wizard reads pins, pin labels, pin numbers, pin types, symbol attributes, texts, and geometry. Mentor colors are not read because they are normally not encoded in the `.sym/.1` file.

Imported Mentor split ZIPs are treated as one split symbol, with each file becoming one unit.

## 12. Mentor/Xpedition Export

The Mentor exporter writes native ASCII records in Mentor style.

For split symbols:

- one ZIP is written
- every split unit becomes one `.1`/symbol file inside the ZIP

For single symbols:

- one `.sym`/`.1` file is written

Export behavior:

- `K` ID is generated dynamically/stably from the symbol/unit name.
- `|R` timestamp is generated in Mentor-style format `H:MM:SS_M-D-YY`.
- Pin number is exported as `#=<pin number>`.
- Pin type is exported as `PINTYPE=<type>`.
- Pin label is exported as the native `L` record.
- Pin Function is additionally exported as an invisible pin attribute at the same coordinates as the pin name label:

```text
A <PinName-X> <PinName-Y> <size> <rotation> <alignment> 0 PINFUNCTION=<pin.function>
```

Additional invisible pin attributes stored on the pin model can also be exported as native `A` records.

## 13. Invisible Attributes

Mentor supports visible and invisible attributes.

- `U` records are symbol/body attributes.
- `A` records are object or pin attributes.

The Wizard uses this for metadata such as `PINFUNCTION`, pin type, pin number, and custom pin metadata. Invisible attributes can be preserved without changing the visible drawing.

## 14. Text and Attribute Anchors

Text and attributes use anchor-based placement. The green anchor point is the grid reference.

Horizontal modes:

- Left
- Center
- Right

Vertical modes:

- Upper
- Center
- Lower

The same anchor logic applies to normal text and attributes.

## 15. Alignment, Distribution, and Transformations

Multi-selection operations use anchor positions where possible so text and attributes remain grid-aligned.

Transform tools include:

- rotate clockwise/counter-clockwise
- flip horizontal / vertical
- scale up / down
- color changes for selected objects

## 16. Template Editor

Open **Tools → Edit Symbol Templates** to edit reusable templates.

The template editor supports:

- body editing
- pins
- text
- graphics
- body attributes
- copy/cut/paste/select all
- undo/redo
- grid-based placement

A save prompt appears only when the current template has actually changed. Simply selecting or viewing a template should not trigger a save prompt.

## 17. Autosave and Restore

The Wizard can restore the last working state on startup. The autosaved workspace should be stored in the user configuration area, not inside the installation ZIP. This avoids permission problems and prevents temporary session data from being shipped with releases.

Recommended paths:

- Windows: `%APPDATA%/SymbolWizard/`
- Linux: `~/.config/SymbolWizard/`
- macOS: `~/Library/Application Support/SymbolWizard/`

## 18. Validation

Use **Tools → Validate Pins** to check pin consistency.

Validation includes:

- duplicate pin numbers
- duplicate pin names
- split-symbol-wide uniqueness checks
- incomplete or inconsistent pin data

For split symbols, validation runs across all units because the complete component must have unique physical pins.

## 19. PINMUX CSV Import

Use **File → Import PINMUX CSV** to import pin data from a CSV file.

Expected columns:

```csv
Pin Name|Pin Type|Pin Function|Pin Number
VDD|POWER||1
PA0|BIDI|ADC_IN0|A1
```

Supported separators include comma, semicolon, pipe, and tab.

## 20. Keyboard Shortcuts

- **Ctrl + A**: select all canvas objects
- **Ctrl + C**: copy selected objects
- **Ctrl + X**: cut selected objects
- **Ctrl + V**: paste copied objects
- **Ctrl + Z**: undo
- **Ctrl + Y**: redo
- **Delete**: delete selected objects
- **Delete Current Symbol / Split Symbol**: delete the active symbol, including all split parts if it is a split symbol
- **Delete All Symbols**: clear the complete current symbol project/library after confirmation
- **Ctrl + S**: save current symbol JSON
- **Ctrl + Shift + S**: save all symbols JSON
- **Ctrl + O**: open library JSON
- **Ctrl + F**: zoom to fit
- **F5**: refresh canvas

## 21. Recommended Mentor Workflow

1. Import Mentor single symbol or split ZIP.
2. Check the origin and body placement.
3. Verify that pin anchors lie on the expected grid.
4. Use Split Pin Manager for filtering, marking, and bulk edits.
5. Adjust Pin Function visibility or text if needed.
6. Validate pins.
7. Export as Mentor single file or split ZIP.
8. Re-import into Mentor/Xpedition and verify pin connectivity.

## 22. Klassenmodell

Unter **Help → Class Model** ist ein vollständiges Klassenmodell des Tools verfügbar. Es beschreibt Datenmodell, GUI-Klassen, Canvas-Klassen, Import/Export-Schicht, Rules-Module und die wichtigsten Datenflüsse.

## 23. About

**Editor:** Christian Hopper  
**Company:** QAVION Consulting GmbH  
**Customer:** Liebherr Electronics and Drives  
**Year:** 2026

"""

    # ------------------------------------------------------------------ Rebuilds
    def rebuild_all(self):
        if not self.library.symbols:
            self.rebuild_symbol_tabs()
            self.rebuild_canvas_tabs()
            self.scene.clear()
            self.rebuild_tree()
            self.rebuild_pin_table()
            self.refresh_properties()
            self.statusBar().showMessage('No symbol loaded. Use File > New Symbol, New Split Symbol, Open, or Import.', 4000)
            return
        self.rebuild_symbol_tabs()
        self.rebuild_canvas_tabs()
        self.rebuild_unit_tabs()
        self.rebuild_scene()
        self.rebuild_tree()
        self.rebuild_pin_table()
        self.grid_spin.blockSignals(True)
        self.grid_spin.setValue(self.symbol.grid_inch)
        self.grid_spin.blockSignals(False)
        self._sync_edit_grid_combo_to_symbol()
        self.format_combo.blockSignals(True)
        self.format_combo.setCurrentText(getattr(self.symbol, 'sheet_format', SheetFormat.A3.value))
        self.format_combo.blockSignals(False)
        if hasattr(self, 'origin_combo'):
            self.origin_combo.blockSignals(True)
            self.origin_combo.setCurrentText(getattr(self.symbol, 'origin', OriginMode.CENTER.value))
            self.origin_combo.blockSignals(False)
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
        if not self.library.symbols:
            self.canvas_tabs.addTab(current_widget, 'No Symbol')
            self.canvas_tabs.blockSignals(False)
            return
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

    def update_name_editors(self):
        if getattr(self, 'symbol_name_edit', None) is not None:
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
        self.set_format_guide_to_active_origin()

        body_attrs = getattr(u.body, 'attributes', {}) or {}
        graphics_as_body = str(body_attrs.get('MENTOR_GRAPHICS_AS_BODY', '0')) == '1' or str(body_attrs.get('MENTOR_BODY_GRAPHICS_LOCKED', '0')) == '1' or str(body_attrs.get('MENTOR_HAS_BODY', '0')) == '1'
        self._lock_template_body_graphics(u)
        # First consolidation step: imported/template BODY artwork uses the same
        # coordinate contract as the native <NONE>/Symbol 1 body.  The chosen
        # OriginMode anchor of the real BODY graphics is placed on canvas (0,0);
        # pins/texts/attributes/user graphics are moved by the exact same delta.
        if graphics_as_body:
            self._normalize_unit_body_anchor_to_symbol_origin(u)

        self.dock_pins_to_body(u)

        # Always add the logical BODY item.  For imported/template symbols
        # the visible BODY is still the real imported artwork, but this item is
        # the same interaction/handle surface used by native Symbol 1.  Its
        # paint() method suppresses the proxy rectangle for Mentor/template
        # bodies and draws only selection handles when selected.  This keeps
        # canvas scaling unified without reintroducing a visible helper frame.
        body_item = BodyItem(u.body, self)
        if graphics_as_body:
            body_item.setZValue(0.05)
            body_item.setBrush(QBrush(Qt.NoBrush))
            try:
                body_item.setData(0, 'BODY')
            except Exception:
                pass
        self.apply_item_selectability(body_item)
        self.scene.addItem(body_item)
        self._restore_or_select_item(body_item, selected_ids)

        self.add_attribute_text_items(u)
        for g in u.graphics:
            item = GraphicItem(g, self)
            self.apply_item_selectability(item)
            if getattr(g, 'locked_to_body', False) and graphics_as_body and not getattr(self, 'is_template_editor', False):
                # This primitive is part of the BODY artwork.  It remains a real
                # GraphicItem for painting, but selection is redirected to BODY
                # semantics. It is never movable/editable as a separate graphic.
                item.setData(0, 'BODY_GRAPHIC')
                item._body_model = u.body
                # BODY-owned artwork is highlight/paint only. It is not a
                # selection object; the logical BodyItem owns selection and
                # handles. This keeps imports/templates identical to Symbol 1.
                item.setFlag(QGraphicsItem.ItemIsSelectable, False)
                item.setFlag(QGraphicsItem.ItemIsMovable, False)
                item.setFlag(QGraphicsItem.ItemIsFocusable, False)
                try:
                    item.setAcceptedMouseButtons(Qt.NoButton)
                except Exception:
                    pass
                item.setZValue(0.2)
            elif not getattr(g, 'locked_to_body', False):
                self._restore_or_select_item(item, selected_ids)
            else:
                if not getattr(self, 'is_template_editor', False):
                    item.setZValue(0.2)
                    try:
                        item.setAcceptedMouseButtons(Qt.NoButton)
                    except Exception:
                        pass
            self.scene.addItem(item)
        for p in u.pins:
            item = PinItem(p, self)
            self.apply_item_selectability(item)
            self.scene.addItem(item)
            self._restore_or_select_item(item, selected_ids)
        for t in u.texts:
            item = TextItem(t, self)
            self.apply_item_selectability(item)
            self.scene.addItem(item)
            self._restore_or_select_item(item, selected_ids)
        self.scene.update()
        self.scene.blockSignals(False)
        self.refresh_properties()

    def select_model_after_rebuild(self, model):
        self._selection_restore_ids = {id(model)}

    def add_attribute_text_items(self, u: SymbolUnitModel):
        b = u.body
        if not hasattr(b, 'attribute_texts') or b.attribute_texts is None:
            b.attribute_texts = {}

        def attr_model(key: str, default_text: str, default_x: float, default_y: float, font, default_h='left', default_v='upper'):
            tm = _text_model_from_any(b.attribute_texts.get(key), default_text, default_x, default_y, font, default_h, default_v)
            b.attribute_texts[key] = tm
            # Attribute content is generated; geometry/font/alignment are persistent and user-editable.
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
            tm = attr_model('RefDes', (ref if str(ref).strip() else 'RefDes'), b.x, b.y + 1, b.refdes_font, getattr(b, 'refdes_align', 'left'), 'lower')
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
                    text_item = QTreeWidgetItem([t.text[:30], f'{t.font_family} {t.font_size_grid:g}'])
                    text_item.setData(0, Qt.UserRole, ('single_text', si, ui, ti))
                    texts.addChild(text_item)

                graphics = QTreeWidgetItem(['Graphics', str(len(u.graphics))])
                unit_item.addChild(graphics)
                for gi, g in enumerate(u.graphics):
                    gr_item = QTreeWidgetItem([g.shape, f'{g.w:g} x {g.h:g}'])
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
                text = QTreeWidgetItem([t.text[:30], f'{t.font_family} {t.font_size_grid:g}'])
                text.setData(0, Qt.UserRole, ('text', ui, ti))
                texts.addChild(text)
            graphics = QTreeWidgetItem(['Graphics', str(len(u.graphics))])
            unit.addChild(graphics)
            for gi, g in enumerate(u.graphics):
                gr = QTreeWidgetItem([g.shape, f'{g.w:g} x {g.h:g}'])
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

    def on_scene_selection_changed(self):
        # Repaint immediately when selection handles appear/disappear; this prevents stale handle artefacts.
        try:
            self.scene.invalidate(self.scene.sceneRect())
            self.scene.update(self.scene.sceneRect())
            self.view.viewport().update()
        except Exception:
            pass
        self.refresh_properties()

    def _property_editor_has_focus(self):
        fw = QApplication.focusWidget()
        if fw is None:
            return False
        try:
            return self.props is not None and (fw is self.props or self.props.isAncestorOf(fw))
        except Exception:
            return False

    def clear_properties(self):
        if not hasattr(self, 'form') or self.form is None:
            return False
        while self.form.rowCount():
            self.form.removeRow(0)
        return True

    def refresh_properties(self):
        if not self.clear_properties():
            return
        if not self.library.symbols:
            self.form.addRow(QLabel('No symbol loaded'))
            return
        selected = [i for i in self.scene.selectedItems()]
        if not selected:
            self.form.addRow(QLabel('No selection'))
            return
        if len(selected) > 1:
            self.form.addRow(QLabel(f'{len(selected)} objects selected'))
            pins = [i for i in selected if i.data(0) == 'PIN']
            text_like = [i for i in selected if i.data(0) in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY')]
            if len(pins) == len(selected):
                self.form.addRow(QLabel(f'<b>Multi-Edit: {len(pins)} PINs</b>'))
                fn = QLineEdit('')
                fn.setPlaceholderText('Set Pin Function for all selected pins')
                fn.returnPressed.connect(lambda editor=fn, items=pins: self.set_selected_pins_attr(items, 'function', editor.text()))
                self.form.addRow('Pin Function', fn)
                for label, attr in [('Show Number', 'visible_number'), ('Show Name', 'visible_name'), ('Show Function', 'visible_function')]:
                    cb = self._multi_pin_visibility_checkbox(pins, attr)
                    self.form.addRow(label, cb)
                self.form.addRow('Pin Length [grid]', self._dbl(float(self._common_pin_value(pins, 'length', 1.0) or 1.0), lambda v, items=pins: self.set_selected_pins_attr(items, 'length', max(1.0, round(float(v)))), 1, 100, 1))
                self.form.addRow('Pin Style', self._combo([''] + [x.value for x in LineStyle], self._common_pin_value(pins, 'line_style', ''), lambda v, items=pins: v and self.set_selected_pins_attr(items, 'line_style', v)))
                self.form.addRow('Pin Width', self._dbl(float(self._common_pin_value(pins, 'line_width', 0.03) or 0.03), lambda v, items=pins: self.set_selected_pins_attr(items, 'line_width', float(v)), .01, 1, .01))
                self.form.addRow('Color', self._color_button_row('Color RGB', self._common_pin_value(pins, 'color', (0, 0, 0)) or (0, 0, 0), lambda _checked=False, items=pins: self.color_selected_pins(items)))
            elif len(text_like) == len(selected):
                self.form.addRow(QLabel(f'<b>Multi-Edit: {len(text_like)} text objects</b>'))
                self.multi_text_props(text_like)
            elif len([i for i in selected if i.data(0) == 'GRAPHIC']) == len(selected):
                graphics = [i for i in selected if i.data(0) == 'GRAPHIC']
                self.form.addRow(QLabel(f'<b>Multi-Edit: {len(graphics)} graphic objects</b>'))
                self.form.addRow('Line width', self._dbl(float(self._common_graphic_value(graphics, 'line_width', 0.03) or 0.03), lambda v, items=graphics: self.set_selected_graphics_style(items, 'line_width', float(v)), .01, 1, .01))
                if all(getattr(i.model, 'shape', '') == 'line' for i in graphics):
                    self.form.addRow('Curve radius', self._dbl(float(self._common_model_value(graphics, 'curve_radius', 0.0) or 0.0), lambda v, items=graphics: self.set_selected_graphics_attr(items, 'curve_radius', float(v)), -100, 100, .1))
            else:
                self.form.addRow(QLabel('Multi-edit is only available for PIN-only, TEXT/ATTRIBUTE-only or GRAPHIC-only selections.'))
            return
        item = selected[0]
        kind = item.data(0)
        if kind == 'BODY_GRAPHIC':
            kind = 'BODY'
            class _BodyProxy:
                pass
            _bp = _BodyProxy(); _bp.model = getattr(item, '_body_model', self.current_unit.body)
            item_for_props = _bp
        else:
            item_for_props = item
        self.form.addRow(QLabel(f'Selected: {kind}'))
        if kind == 'BODY': self.body_props(item_for_props)
        elif kind == 'PIN': self.pin_props(item)
        elif kind in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY'): self.text_props(item)
        elif kind == 'GRAPHIC': self.graphic_props(item)

    def rebuild_props(self):
        """Compatibility wrapper for older callbacks: rebuild the property panel."""
        return self.refresh_properties()

    def _line(self, value, fn):
        w = QLineEdit(str(value))
        # Commit text edits only with Enter. This prevents live rebuilds while typing.
        w.returnPressed.connect(lambda widget=w: fn(widget.text()))
        return w

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
        w.setSingleStep(step)
        w.setDecimals(3)
        w.setKeyboardTracking(False)
        w.setValue(float(value))
        w.valueChanged.connect(fn)
        return w

    def _combo(self, items, val, fn):
        w = QComboBox()
        w.addItems(items)
        w.setCurrentText(str(val))
        w.currentTextChanged.connect(fn)
        return w

    def _check(self, value, fn):
        w = QCheckBox()
        w.setChecked(bool(value))
        w.toggled.connect(fn)
        return w

    def _color_button_row(self, button_text, color, callback):
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        btn = QPushButton(button_text)
        btn.clicked.connect(callback)
        swatch = QFrame()
        swatch.setFixedSize(24, 18)
        swatch.setFrameShape(QFrame.Box)
        r, g, b = color or (0, 0, 0)
        swatch.setStyleSheet(f'background-color: rgb({int(r)}, {int(g)}, {int(b)}); border: 1px solid #555;')
        lay.addWidget(btn)
        lay.addWidget(swatch)
        lay.addStretch(1)
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
            elif k == 'BODY':
                # BODY style is visible through body-owned graphics for imported/template bodies.
                # Keep the logical BODY style and all locked BODY primitives in sync.
                m.color = tuple(color)
                for gr in self._body_owned_graphics(m):
                    st = getattr(gr, 'style', None)
                    if st is not None:
                        st.stroke = tuple(color)
            elif k in ('PIN', 'TEXT', 'ATTR_REF_DES', 'ATTR_BODY'):
                m.color = color
                if hasattr(it, 'apply_text_from_model'):
                    it.apply_text_from_model()
                if k in ('ATTR_REF_DES', 'ATTR_BODY'):
                    self._sync_body_font_from_attribute_text(it)
        self.dirty = True
        self.update_current_unit_canvas_positions()
        self.schedule_scene_refresh(visual_only=True)

    def _sync_body_font_from_attribute_text(self, item):
        m = getattr(item, 'model', None)
        if m is None or item.data(0) not in ('ATTR_REF_DES', 'ATTR_BODY'):
            return
        body = self.current_unit.body
        target = body.refdes_font if item.data(0) == 'ATTR_REF_DES' else body.attribute_font
        target.family = m.font_family
        target.size_grid = m.font_size_grid
        target.color = m.color

    def _apply_body_font_to_attribute_texts(self, font, refdes=False):
        body = self.current_unit.body
        keys = ['RefDes'] if refdes else [k for k in body.attributes.keys() if k != 'RefDes']
        for key in keys:
            tm = body.attribute_texts.get(key) if getattr(body, 'attribute_texts', None) else None
            if tm is not None:
                tm.font_family = str(_font_value(font, 'family', 'Arial'))
                tm.font_size_grid = float(_font_value(font, 'size_grid', 0.75))
                tm.color = tuple(_font_value(font, 'color', (0, 0, 0)))

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

    def _body_attr_sync_targets(self, body=None):
        """Return BODY models that should receive BODY-attribute edits.

        For split symbols the BODY-attribute section is intentionally global:
        editing attribute values, visibility or attribute fonts in the active
        part updates the same BODY attributes in every split part.  This is
        model-only for inactive parts, so it avoids expensive scene rebuilds.
        Geometry (x/y/width/height, pins, graphics, plain texts) stays local.
        """
        body = body or self.current_unit.body
        try:
            if self.symbol.kind == SymbolKind.SPLIT.value and len(self.symbol.units) > 1:
                return [u.body for u in self.symbol.units if getattr(u, 'body', None) is not None]
        except Exception:
            pass
        return [body]

    def _sync_body_attribute_text_models(self, body: SymbolBodyModel, key: str | None = None):
        """Keep cached attribute text models in sync without repainting inactive units."""
        if getattr(body, 'attribute_texts', None) is None:
            body.attribute_texts = {}
        keys = [key] if key is not None else list(body.attributes.keys())
        for k in keys:
            if k not in body.attributes:
                continue
            tm = body.attribute_texts.get(k)
            if tm is None:
                continue
            tm.text = str(body.attributes.get(k, '')) if k == 'RefDes' else f'{k}: {body.attributes.get(k, "")}'
            font = body.refdes_font if k == 'RefDes' else body.attribute_font
            tm.font_family = str(_font_value(font, 'family', 'Arial'))
            tm.font_size_grid = float(_font_value(font, 'size_grid', 0.75))
            tm.color = tuple(_font_value(font, 'color', (0, 0, 0)))

    def _copy_font_values(self, src: FontModel, dst: FontModel):
        dst.family = src.family
        dst.size_grid = src.size_grid
        dst.color = src.color

    def _is_split_body_attr_sync_active(self) -> bool:
        try:
            return self.symbol.kind == SymbolKind.SPLIT.value and len(self.symbol.units) > 1
        except Exception:
            return False

    def body_props(self, item):
        m = item.model
        head = QLabel('<b>BODY</b>')
        self.form.addRow(head)
        self.form.addRow('Width [grid]', self._dbl(m.width, lambda v, body=m: self._set_body_width_grid(body, float(v)), .01, 300, self._edit_grid_step()))
        self.form.addRow('Height [grid]', self._dbl(m.height, lambda v, body=m: self._set_body_height_grid(body, float(v)), .01, 300, self._edit_grid_step()))
        self.form.addRow('Line style', self._combo([x.value for x in LineStyle], m.line_style, lambda v, body=m: self.set_body_visual_attr(body, 'line_style', v)))
        self.form.addRow('Line width', self._dbl(m.line_width, lambda v, body=m: self.set_body_visual_attr(body, 'line_width', float(v)), .01, 1, .01))
        self.transform_props(m)
        self.form.addRow('Color', self._color_button_row('Color RGB', m.color, lambda _checked=False, body=m: self.color_body_model(body)))
        self.form.addRow(QLabel('<b>BODY-Attribute</b>'))
        if self._is_split_body_attr_sync_active():
            sync_info = QLabel('Split sync active: BODY attribute values, visibility and fonts are applied to all split parts.')
            sync_info.setWordWrap(True)
            self.form.addRow(sync_info)
        self.font_props('RefDes font', m.refdes_font, refresh_attrs=True)
        self.font_props('Attribute font', m.attribute_font, refresh_attrs=True)
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
            # BODY attributes can be removed by right click directly on the attribute row.
            # The row is used instead of the label widget because QFormLayout internally
            # owns/creates the label and is not reliable as a context-menu target.
            row.setContextMenuPolicy(Qt.CustomContextMenu)
            row.customContextMenuRequested.connect(lambda pos, body=m, key=k, widget=row: self.body_attribute_context_menu(body, key, widget, pos))
            cb.setContextMenuPolicy(Qt.CustomContextMenu)
            cb.customContextMenuRequested.connect(lambda pos, body=m, key=k, widget=cb: self.body_attribute_context_menu(body, key, widget, pos))
            ed.setContextMenuPolicy(Qt.CustomContextMenu)
            ed.customContextMenuRequested.connect(lambda pos, body=m, key=k, widget=ed: self.body_attribute_context_menu(body, key, widget, pos))
            self.form.addRow(k, row)
        add_attr_btn = QPushButton('Add Attribute')
        add_attr_btn.clicked.connect(lambda _checked=False, body=m: self.add_body_attribute_dialog(body))
        self.form.addRow('', add_attr_btn)


    def body_attribute_context_menu(self, body, key, widget, pos):
        menu = QMenu(self)
        delete_action = QAction('Delete Attribute', self)
        delete_action.triggered.connect(lambda _checked=False, b=body, k=key: self.delete_body_attribute(b, k))
        menu.addAction(delete_action)
        try:
            menu.exec(widget.mapToGlobal(pos))
        except Exception:
            menu.exec(QCursor.pos())

    def delete_body_attribute(self, body, key):
        if body is None or not key:
            return
        attrs = getattr(body, 'attributes', {}) or {}
        if key not in attrs:
            return
        protected = {'REFDES', 'REF_DES'}
        if str(key).strip().upper() in protected:
            QMessageBox.information(self, 'Delete Attribute', f'Das Pflichtattribut "{key}" kann nicht gelöscht werden.')
            return
        res = QMessageBox.question(
            self,
            'Delete Attribute',
            f'Attribut "{key}" löschen?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res != QMessageBox.Yes:
            return
        self.push_undo_state()
        for target in self._body_attr_sync_targets(body):
            try:
                if getattr(target, 'attributes', None) is not None:
                    target.attributes.pop(key, None)
                if getattr(target, 'visible_attributes', None) is not None:
                    target.visible_attributes.pop(key, None)
                if getattr(target, 'attribute_texts', None) is not None:
                    target.attribute_texts.pop(key, None)
            except Exception:
                pass
        try:
            self.update_attribute_items_for_unit()
        except Exception:
            pass
        try:
            self.rebuild_tree()
        except Exception:
            pass
        try:
            self.refresh_properties()
        except Exception:
            pass
        try:
            self.schedule_scene_refresh(visual_only=True)
        except Exception:
            pass

    def add_body_attribute_dialog(self, body):
        dlg = QDialog(self)
        dlg.setWindowTitle('Add BODY Attribute')
        layout = QFormLayout(dlg)
        name_edit = QLineEdit()
        value_edit = QLineEdit()
        visible_cb = QCheckBox('visible')
        visible_cb.setChecked(True)
        layout.addRow('Name', name_edit)
        layout.addRow('Value', value_edit)
        layout.addRow('Visibility', visible_cb)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addRow(buttons)

        def accept_if_valid():
            name = name_edit.text().strip()
            if not name:
                QMessageBox.warning(dlg, 'Attribute', 'Bitte einen Attributnamen eingeben.')
                return
            if name in (getattr(body, 'attributes', {}) or {}):
                QMessageBox.warning(dlg, 'Attribute', f'Das Attribut "{name}" existiert bereits.')
                return
            dlg.accept()

        buttons.accepted.connect(accept_if_valid)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.Accepted:
            return
        name = name_edit.text().strip()
        value = value_edit.text()
        visible = visible_cb.isChecked()
        self.push_undo_state()
        for target in self._body_attr_sync_targets(body):
            if getattr(target, 'attributes', None) is None:
                target.attributes = {}
            if getattr(target, 'visible_attributes', None) is None:
                target.visible_attributes = {}
            target.attributes[name] = value
            target.visible_attributes[name] = visible
            if getattr(target, 'attribute_texts', None) is None:
                target.attribute_texts = {}
            # Let the normal attribute layout create/show the text item on rebuild.
            self._sync_body_attribute_text_models(target, name)
        self.update_attribute_items_for_unit()
        self.rebuild_tree()
        self.refresh_properties()
        self.schedule_scene_refresh(visual_only=True)


    def pin_props(self, item):
        m = item.model
        self.form.addRow(QLabel('<b>PIN</b>'))
        for label, attr in [('Pin Number', 'number'), ('Pin Name', 'name'), ('Pin Function', 'function')]:
            self.form.addRow(label, self._line(getattr(m, attr), lambda v, a=attr: self.set_pin_attr(m, a, v)))
        self.form.addRow('Pin Type', self._combo([x.value for x in PinType], m.pin_type, lambda v: self.set_pin_attr(m, 'pin_type', v)))
        self.form.addRow('Side', self._combo([x.value for x in PinSide], m.side, lambda v: self.set_pin_attr(m, 'side', v)))
        inv = QCheckBox(); inv.setChecked(m.inverted); inv.toggled.connect(lambda v: self.set_pin_attr(m, 'inverted', v)); self.form.addRow('Inverted', inv)
        self.form.addRow(QLabel('<b>PIN Attributes</b>'))
        for label, attr in [('Show Number', 'visible_number'), ('Show Name', 'visible_name'), ('Show Function', 'visible_function')]:
            cb = QCheckBox(); cb.setChecked(getattr(m, attr)); cb.toggled.connect(lambda v, a=attr: self.set_pin_attr(m, a, v)); self.form.addRow(label, cb)
        self.form.addRow('Length [grid]', self._dbl(m.length, lambda v: self.set_pin_length(m, v), 1, 100, 1))
        self.form.addRow('Line style', self._combo([x.value for x in LineStyle], m.line_style, lambda v: self.set_pin_attr(m, 'line_style', v)))
        self.form.addRow('Line width', self._dbl(m.line_width, lambda v: self.set_pin_attr(m, 'line_width', v), .01, 1, .01))
        self.font_props('Pin number font', m.number_font)
        self.font_props('Pin label font', m.label_font)
        self.form.addRow('Color', self._color_button_row('Color RGB', m.color, lambda: self.color_model(m)))
        custom_attrs = getattr(m, 'attributes', {}) or {}
        if custom_attrs:
            self.form.addRow(QLabel('<b>Custom Pin Attributes</b>'))
            for k in sorted(custom_attrs.keys()):
                row=QWidget(); l=QHBoxLayout(row); l.setContentsMargins(0,0,0,0)
                cb=QCheckBox('visible'); cb.setChecked((getattr(m, 'visible_attributes', {}) or {}).get(k, False))
                ed=QLineEdit(str(custom_attrs.get(k, '')))
                cb.toggled.connect(lambda v, key=k, pin=m: self.set_pin_custom_attr_visible(pin, key, v))
                ed.editingFinished.connect(lambda key=k, pin=m, e=ed: self.set_pin_custom_attr_value(pin, key, e.text()))
                l.addWidget(cb); l.addWidget(ed); self.form.addRow(k, row)

    def text_props(self, item):
        m = item.model
        is_attr = item.data(0) in ('ATTR_REF_DES', 'ATTR_BODY') or bool(getattr(m, '_is_attribute_text', False))
        line = self._line(m.text, lambda v: self.set_text_attr(item, 'text', v)) if is_attr else self._plain_text_editor(m.text, lambda v: self.set_text_attr(item, 'text', v))
        if is_attr:
            line.setReadOnly(True)
            line.setToolTip('Attribute text content is driven by the owning object attribute value.')
        self.form.addRow('Text', line)
        self.form.addRow('Font', self._font_combo(m.font_family, lambda v: self.set_text_attr(item, 'font_family', v)))
        self.form.addRow('Size grid', self._dbl(m.font_size_grid, lambda v: self.set_text_attr(item, 'font_size_grid', v), .1, 5, .1))
        self.form.addRow('Horizontal grid anchor', self._combo(['left','center','right'], getattr(m, 'h_align', 'left'), lambda v: self.set_text_attr(item, 'h_align', v)))
        self.form.addRow('Vertical grid anchor', self._combo(['upper','center','lower'], getattr(m, 'v_align', 'upper'), lambda v: self.set_text_attr(item, 'v_align', v)))
        if is_attr:
            self.form.addRow('Wrap text', self._check(getattr(m, 'wrap_text', False), lambda v: self.set_text_attr(item, 'wrap_text', v)))
        else:
            self.form.addRow('Line break', QLabel('Shift+Enter in canvas / text field'))
        self.form.addRow('Rotation [deg]', self._dbl(getattr(m, 'rotation', 0), lambda v: self.set_text_attr(item, 'rotation', v), -360, 360, 15))
        self.form.addRow('Color', self._color_button_row('Color RGB', m.color, lambda: self.color_text_item(item)))

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

    def multi_text_props(self, items):
        self.form.addRow('Font', self._font_combo(self._common_model_value(items, 'font_family', ''), lambda v, its=items: self.set_selected_text_attr(its, 'font_family', v)))
        self.form.addRow('Size grid', self._dbl(float(self._common_model_value(items, 'font_size_grid', 1.0) or 1.0), lambda v, its=items: self.set_selected_text_attr(its, 'font_size_grid', v), .1, 5, .1))
        self.form.addRow('Horizontal grid anchor', self._combo(['', 'left','center','right'], self._common_model_value(items, 'h_align', ''), lambda v, its=items: v and self.set_selected_text_attr(its, 'h_align', v)))
        self.form.addRow('Vertical grid anchor', self._combo(['', 'upper','center','lower'], self._common_model_value(items, 'v_align', ''), lambda v, its=items: v and self.set_selected_text_attr(its, 'v_align', v)))
        self.form.addRow('Wrap text', self._check(bool(self._common_model_value(items, 'wrap_text', False)), lambda v, its=items: self.set_selected_text_attr(its, 'wrap_text', v)))
        self.form.addRow('Rotation [deg]', self._dbl(float(self._common_model_value(items, 'rotation', 0) or 0), lambda v, its=items: self.set_selected_text_attr(its, 'rotation', v), -360, 360, 15))
        row = QWidget(); lay = QHBoxLayout(row); lay.setContentsMargins(0,0,0,0)
        for label, fn in [('Align L', lambda _checked=False, its=items: self.align_text_objects(its, 'left')), ('Align R', lambda _checked=False, its=items: self.align_text_objects(its, 'right')), ('Align Top', lambda _checked=False, its=items: self.align_text_objects(its, 'upper')), ('Align Bottom', lambda _checked=False, its=items: self.align_text_objects(its, 'lower'))]:
            b=QPushButton(label); b.clicked.connect(fn); lay.addWidget(b)
        self.form.addRow('Arrange', row)
        row2 = QWidget(); lay2 = QHBoxLayout(row2); lay2.setContentsMargins(0,0,0,0)
        for label, fn in [('Distribute H', lambda _checked=False, its=items: self.distribute_text_objects(its, 'h')), ('Distribute V', lambda _checked=False, its=items: self.distribute_text_objects(its, 'v'))]:
            b=QPushButton(label); b.clicked.connect(fn); lay2.addWidget(b)
        self.form.addRow('Distribute', row2)
        self.form.addRow('Color', self._color_button_row('Color RGB', self._common_model_value(items, 'color', (0, 0, 0)) or (0, 0, 0), lambda _checked=False, its=items: self.color_selected_text(its)))

    def graphic_props(self, item):
        m = item.model
        self.form.addRow('Shape', self._combo(['line', 'rect', 'ellipse'], m.shape, lambda v: self.set_and_refresh(m, 'shape', v)))
        self.form.addRow('Width [grid]', self._dbl(m.w, lambda v: self.set_and_refresh(m, 'w', round(float(v))), -100, 300, 1))
        self.form.addRow('Height [grid]', self._dbl(m.h, lambda v: self.set_and_refresh(m, 'h', round(float(v))), -100, 300, 1))
        self.form.addRow('Line style', self._combo([x.value for x in LineStyle], m.style.line_style, lambda v: self.set_style(m, 'line_style', v)))
        self.form.addRow('Line width', self._dbl(m.style.line_width, lambda v: self.set_style(m, 'line_width', v), .01, 1, .01))
        if m.shape == 'line':
            self.form.addRow('Curve radius', self._dbl(getattr(m, 'curve_radius', 0), lambda v: self.set_and_refresh(m, 'curve_radius', v), -100, 100, .1))
        self.form.addRow('Rotation [deg]', self._dbl(getattr(m, 'rotation', 0), lambda v: self.set_and_refresh(m, 'rotation', v), -360, 360, 15))
        self.form.addRow('Color', self._color_button_row('Stroke RGB', m.style.stroke, lambda: self.color_model(m.style, 'stroke')))

    def font_props(self, title, f, refresh_attrs=False):
        self.form.addRow(QLabel(title))
        self.form.addRow('Family', self._font_combo(f.family, lambda v: self.set_font_attr(f, 'family', v, refresh_attrs)))
        self.form.addRow('Size [grid]', self._dbl(f.size_grid, lambda v: self.set_font_attr(f, 'size_grid', v, refresh_attrs), .1, 5, .1))
        self.form.addRow('Font color', self._color_button_row('Font Color RGB', f.color, lambda: self.color_font(f, refresh_attrs)))

    def transform_props(self, m):
        def _set_rotation(v, model=m):
            try:
                if model is self.current_unit.body:
                    target = (round(float(v) / 90.0) * 90.0) % 360.0
                    current = float(getattr(model, 'rotation', 0.0) or 0.0) % 360.0
                    delta = target - current
                    if abs(delta) > 180.0:
                        delta -= 360.0 if delta > 0 else -360.0
                    self.push_undo_state()
                    self._transform_unit_as_body_group('rotate', delta)
                else:
                    self.set_and_refresh(model, 'rotation', v)
            except Exception:
                self.set_and_refresh(model, 'rotation', v)
        self.form.addRow('Rotation [deg]', self._dbl(getattr(m, 'rotation', 0), _set_rotation, -360, 360, 90))

    # ------------------------------------------------------------------ Model updates
    def set_font_attr(self, f, a, v, refresh_attrs=False):
        self.push_undo_state()
        setattr(f, a, v)
        if refresh_attrs:
            body = self.current_unit.body
            refdes = (f is body.refdes_font)
            attr_font = (f is body.attribute_font)
            if refdes or attr_font:
                targets = self._body_attr_sync_targets(body)
                for tb in targets:
                    target_font = tb.refdes_font if refdes else tb.attribute_font
                    self._copy_font_values(f, target_font)
                    self._sync_body_attribute_text_models(tb, 'RefDes' if refdes else None)
                # Only the active split part is repainted now. Inactive parts use the
                # updated model values when they become active, avoiding global redraws.
                self.update_attribute_items_for_unit()
            else:
                setattr(f, a, v)
        self.schedule_scene_refresh()

    def color_font(self, f, refresh_attrs=False):
        self.push_undo_state()
        c = QColorDialog.getColor(QColor(*f.color), self)
        if c.isValid():
            f.color = (c.red(), c.green(), c.blue())
            if refresh_attrs:
                body = self.current_unit.body
                refdes = (f is body.refdes_font)
                attr_font = (f is body.attribute_font)
                if refdes or attr_font:
                    targets = self._body_attr_sync_targets(body)
                    for tb in targets:
                        target_font = tb.refdes_font if refdes else tb.attribute_font
                        self._copy_font_values(f, target_font)
                        self._sync_body_attribute_text_models(tb, 'RefDes' if refdes else None)
                    self.update_attribute_items_for_unit()
            self.schedule_scene_refresh()

    def set_and_refresh(self, m, a, v):
        self.push_undo_state()
        if a == 'rotation':
            v = (round(float(v) / 15.0) * 15.0) % 360
        setattr(m, a, v)
        self.update_current_unit_canvas_positions()
        self.schedule_scene_refresh(visual_only=True)

    def set_style(self, m, a, v):
        self.push_undo_state()
        setattr(m.style, a, v)
        self.schedule_scene_refresh()

    def set_body_dim(self, item, a, v):
        self.push_undo_state()
        st = {
            'x': float(item.model.x), 'y': float(item.model.y),
            'w': float(item.model.width), 'h': float(item.model.height),
            'pins': [(p, float(p.x), float(p.y), float(p.length)) for p in self.current_unit.pins],
            'texts': [(t, float(t.x), float(t.y)) for t in self.current_unit.texts],
            'attributes': [(t, float(t.x), float(t.y)) for t in getattr(self.current_unit.body, 'attribute_texts', {}).values()],
            'graphics': [(gr, float(gr.x), float(gr.y), float(gr.w), float(gr.h)) for gr in self.current_unit.graphics],
        }
        setattr(item.model, a, float(v))
        self.scale_current_unit_children_from_body_resize(st, item.model)
        self.enforce_symbol_size_limit()
        self.update_current_unit_canvas_positions()
        self.schedule_scene_refresh(visual_only=True)

    def set_attr_vis(self, m, k, v):
        self.push_undo_state()
        for body in self._body_attr_sync_targets(m):
            if k not in body.attributes:
                body.attributes[k] = m.attributes.get(k, '')
            body.visible_attributes[k] = bool(v)
            self._sync_body_attribute_text_models(body, k)
        self.update_attribute_items_for_unit()
        self.rebuild_tree()
        self.schedule_scene_refresh(visual_only=True)

    def set_attr_val(self, m, k, v):
        self.push_undo_state()
        for body in self._body_attr_sync_targets(m):
            body.attributes[k] = v
            if k not in body.visible_attributes:
                body.visible_attributes[k] = m.visible_attributes.get(k, False)
            self._sync_body_attribute_text_models(body, k)
        self.update_attribute_items_for_unit()
        self.rebuild_tree()
        self.schedule_scene_refresh(visual_only=True)

    def _apply_multi_pin_visibility_choice(self, pin_items, attr, index):
        # 0 = unchanged, 1 = hidden/False, 2 = visible/True
        if int(index) == 0:
            return
        self.set_selected_pins_attr(pin_items, attr, int(index) == 2)

    def _apply_multi_pin_visibility_state(self, pin_items, attr, state):
        # Backward-compatible handler for older tristate widgets. PySide may pass
        # either an int or a Qt.CheckState enum, so compare defensively.
        value = getattr(state, 'value', state)
        if value == getattr(Qt.CheckState.PartiallyChecked, 'value', 1) or value == 1:
            return
        self.set_selected_pins_attr(pin_items, attr, value == getattr(Qt.CheckState.Checked, 'value', 2) or value == 2)

    def set_selected_pins_attr(self, pin_items, attr, value):
        pins = [getattr(i, 'model', None) for i in pin_items if getattr(i, 'model', None) is not None and i.data(0) == 'PIN']
        if not pins or len(pins) != len(pin_items):
            return
        if attr not in ('function', 'visible_number', 'visible_name', 'visible_function', 'length', 'line_style', 'line_width', 'color'):
            return
        self.push_undo_state()
        selected_ids = {id(p) for p in pins}
        for p in pins:
            setattr(p, attr, value)
        self._selection_restore_ids = selected_ids
        self.schedule_scene_refresh()


    def set_selected_graphics_style(self, graphic_items, attr, value):
        graphics = [getattr(i, 'model', None) for i in graphic_items if getattr(i, 'model', None) is not None and i.data(0) == 'GRAPHIC']
        if not graphics or len(graphics) != len(graphic_items) or attr not in ('line_width', 'line_style'):
            return
        self.push_undo_state()
        self._selection_restore_ids = {id(g) for g in graphics}
        for g in graphics:
            setattr(g.style, attr, value)
        self.update_current_unit_canvas_positions()
        self.schedule_scene_refresh(visual_only=True)

    def set_selected_graphics_attr(self, graphic_items, attr, value):
        graphics = [getattr(i, 'model', None) for i in graphic_items if getattr(i, 'model', None) is not None and i.data(0) == 'GRAPHIC']
        if not graphics or len(graphics) != len(graphic_items):
            return
        self.push_undo_state()
        self._selection_restore_ids = {id(g) for g in graphics}
        for g in graphics:
            setattr(g, attr, value)
        self.update_current_unit_canvas_positions()
        self.schedule_scene_refresh(visual_only=True)

    def color_selected_pins(self, items):
        current = self._common_pin_value(items, 'color', (0, 0, 0)) or (0, 0, 0)
        c = QColorDialog.getColor(QColor(*current), self)
        if not c.isValid():
            return
        self.set_selected_pins_attr(items, 'color', (c.red(), c.green(), c.blue()))

    def set_pin_attr(self, m, a, v):
        self.push_undo_state()
        setattr(m, a, v)
        if a == 'side':
            self.dock_pins_to_body(self.current_unit)
        dup = duplicate_pin_numbers(self.symbol)
        if dup:
            self.statusBar().showMessage('Duplicate pin number(s): ' + ', '.join(dup), 8000)
        self.schedule_scene_refresh()

    def set_pin_custom_attr_visible(self, pin, key, visible):
        self.push_undo_state()
        if not hasattr(pin, 'visible_attributes') or pin.visible_attributes is None:
            pin.visible_attributes = {}
        if not hasattr(pin, 'attribute_texts') or pin.attribute_texts is None:
            pin.attribute_texts = {}
        pin.visible_attributes[key] = bool(visible)
        if visible and key not in pin.attribute_texts:
            val = (getattr(pin, 'attributes', {}) or {}).get(key, '')
            pin.attribute_texts[key] = TextModel(text=f'{key}: {val}' if str(val).strip() else str(key), x=pin.x, y=pin.y - 1, font_size_grid=.45)
        self.dirty = True
        self.schedule_scene_refresh()

    def set_pin_custom_attr_value(self, pin, key, value):
        self.push_undo_state()
        if not hasattr(pin, 'attributes') or pin.attributes is None:
            pin.attributes = {}
        pin.attributes[key] = value
        tm = (getattr(pin, 'attribute_texts', {}) or {}).get(key)
        if tm is not None:
            tm.text = f'{key}: {value}' if str(value).strip() else str(key)
        self.dirty = True
        self.schedule_scene_refresh()

    def set_pin_length(self, m, v):
        self.push_undo_state()
        # Pin length is always an integer grid multiple.
        m.length = max(1.0, round(float(v)))
        self.schedule_scene_refresh()

    def set_text_attr(self, item, a, v):
        if a == 'text' and (item.data(0) in ('ATTR_REF_DES', 'ATTR_BODY') or bool(getattr(item.model, '_is_attribute_text', False))):
            return
        self.push_undo_state()
        if a == 'rotation':
            v = (round(float(v) / 15.0) * 15.0) % 360
        setattr(item.model, a, v)
        if a in ('h_align', 'v_align'):
            self._snap_text_anchor_to_grid(item)
        if a in ('font_family', 'font_size_grid', 'color'):
            self._sync_body_font_from_attribute_text(item)
        if hasattr(item, 'apply_text_from_model'):
            item.apply_text_from_model()
        elif a == 'text':
            item.setPlainText(v)
        self.schedule_scene_refresh(visual_only=True)

    def set_selected_text_attr(self, items, attr, value):
        models = [getattr(i, 'model', None) for i in items if i.data(0) in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY')]
        if not models or len(models) != len(items):
            return
        if attr == 'text':
            return
        self.push_undo_state()
        if attr == 'rotation':
            value = (round(float(value) / 15.0) * 15.0) % 360
        selected_ids = {id(m) for m in models}
        for item in items:
            setattr(item.model, attr, value)
            if attr in ('h_align', 'v_align'):
                self._snap_text_anchor_to_grid(item)
            if attr in ('font_family', 'font_size_grid', 'color'):
                self._sync_body_font_from_attribute_text(item)
            if hasattr(item, 'apply_text_from_model'):
                item.apply_text_from_model()
        self._selection_restore_ids = selected_ids
        self.schedule_scene_refresh(visual_only=True)

    def color_text_item(self, item):
        self.push_undo_state()
        c = QColorDialog.getColor(QColor(*item.model.color), self)
        if c.isValid():
            item.model.color = (c.red(), c.green(), c.blue())
            self._sync_body_font_from_attribute_text(item)
            if hasattr(item, 'apply_text_from_model'):
                item.apply_text_from_model()
            self.schedule_scene_refresh(visual_only=True)

    def color_selected_text(self, items):
        c = QColorDialog.getColor(QColor(0, 0, 0), self)
        if not c.isValid():
            return
        self.push_undo_state()
        value = (c.red(), c.green(), c.blue())
        for item in items:
            if item.data(0) in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY'):
                item.model.color = value
                self._sync_body_font_from_attribute_text(item)
                if hasattr(item, 'apply_text_from_model'):
                    item.apply_text_from_model()
        self.schedule_scene_refresh(visual_only=True)

    def color_model(self, m, attr='color'):
        self.push_undo_state()
        c = QColorDialog.getColor(QColor(*getattr(m, attr)), self)
        if c.isValid():
            setattr(m, attr, (c.red(), c.green(), c.blue()))
            self.schedule_scene_refresh()

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
                    self.view.viewport().update()
                elif hasattr(self, 'scene'):
                    self.scene.update()
            except Exception:
                pass
        QTimer.singleShot(0, _do)
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
                item.setPen(pen_for(model.color, model.line_width, model.line_style, g))
                if hasattr(item, 'apply_transform_from_model'):
                    item.apply_transform_from_model()
            elif kind == 'PIN':
                item.setPos(model.x * g, -model.y * g)
                if hasattr(item, 'apply_transform_from_model'):
                    item.apply_transform_from_model()
            elif kind in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY'):
                if hasattr(item, 'apply_text_from_model'):
                    item.apply_text_from_model()
                else:
                    item.setPos(model.x * g, -model.y * g)
            elif kind == 'GRAPHIC':
                item.setPos(model.x * g, -model.y * g)
                if hasattr(item, 'apply_transform_from_model'):
                    item.apply_transform_from_model()
            item.update()
        self.scene.update()
        self.view.viewport().update()

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
        self.view.viewport().update()

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

        grid = float(getattr(getattr(self, 'symbol', None), 'grid_inch', 1.0) or getattr(self, 'grid_inch', 1.0) or 1.0)
        def sg(v):
            return round(float(v) / grid) * grid

        for p, px, py, plen in start_state.get('pins', []):
            # Pins stay docked to the selected side; Y follows body height scaling.
            p.x = body.x if p.side == PinSide.LEFT.value else body.x + body.width
            p.y = sg(body.y + (py - old_y) * sy)
            p.length = max(.5, sg(plen * max(abs(sx), .1)))
        for t, tx, ty in start_state.get('texts', []):
            t.x = sg(body.x + (tx - old_x) * sx)
            t.y = sg(body.y + (ty - old_y) * sy)
        for t, tx, ty in start_state.get('attributes', []):
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
        if self._refresh_visual_only:
            self.update_current_unit_canvas_positions()
            self.update_attribute_items_for_unit()
            if not self._property_editor_has_focus():
                self.refresh_properties()
        else:
            self.rebuild_scene()
            self.rebuild_tree()
            self.rebuild_pin_table()
        self._refresh_visual_only = False

    # ------------------------------------------------------------------ Grouping / constraints

    def _move_pin_owned_texts(self, pin, dx: float, dy: float):
        for ax_name, ay_name in (('label_x', 'label_y'), ('number_x', 'number_y')):
            if getattr(pin, ax_name, None) is not None and getattr(pin, ay_name, None) is not None:
                setattr(pin, ax_name, float(getattr(pin, ax_name)) + dx)
                setattr(pin, ay_name, float(getattr(pin, ay_name)) + dy)
        for tm in (getattr(pin, 'attribute_texts', {}) or {}).values():
            try:
                tm.x = float(tm.x) + dx
                tm.y = float(tm.y) + dy
            except Exception:
                pass

    def move_current_unit_group(self, dx: float, dy: float, source_body=None):
        u = self.current_unit
        # Manual body moves establish a new local base for later transforms.
        self._invalidate_body_group_transform_cache(u)
        # Body is the anchor. When it moves, all user-owned objects in this unit follow.
        for p in u.pins:
            p.x += dx
            p.y += dy
            self._move_pin_owned_texts(p, dx, dy)
        for t in u.texts:
            t.x += dx
            t.y += dy
        for t in getattr(u.body, 'attribute_texts', {}).values():
            t.x += dx
            t.y += dy
        for g in u.graphics:
            g.x += dx
            g.y += dy

    def dock_pins_to_body(self, u: SymbolUnitModel):
        b = u.body
        attrs = getattr(b, 'attributes', {}) or {}
        # Mentor-native imports already contain exact pin endpoints.  Re-docking
        # during every scene rebuild would move left/right/top/bottom pins to a
        # generated bounding box and destroy the imported placement.
        if str(attrs.get('MENTOR_DISABLE_AUTO_DOCK', '0')) == '1' or str(attrs.get('MENTOR_GRAPHICS_AS_BODY', '0')) == '1':
            return
        for p in u.pins:
            if p.side == PinSide.LEFT.value:
                p.x = b.x
            elif p.side == PinSide.RIGHT.value:
                p.x = b.x + b.width
            elif p.side == PinSide.TOP.value:
                p.y = b.y
            elif p.side == PinSide.BOTTOM.value:
                p.y = b.y - b.height

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
            for t in getattr(u.body, 'attribute_texts', {}).values():
                xs.append(t.x); ys.append(t.y)
            for g in u.graphics:
                xs.extend([g.x, g.x + g.w]); ys.extend([g.y, g.y - g.h])
        if not xs:
            return 0, 0, 1, 1
        return min(xs), min(ys), max(xs), max(ys)

    def enforce_symbol_size_limit(self, silent=False):
        # Never auto-scale imported or edited symbols.  The sheet/usable-area preview
        # is only an orientation guide; it must not change the user's geometry.
        return True

    # ------------------------------------------------------------------ Actions
    def set_tool(self, t):
        self.draw_tool = t
        for k, a in self.tool_buttons.items():
            a.setChecked(k == t)
        self.view.setDragMode(QGraphicsView.RubberBandDrag if t == DrawTool.SELECT.value else QGraphicsView.NoDrag)

    def pick_default_color(self):
        current = self._current_color_for_selection() if hasattr(self, '_current_color_for_selection') else self.default_color
        c = QColorDialog.getColor(QColor(*current), self)
        if c.isValid():
            self.apply_color_to_selected((c.red(), c.green(), c.blue()))

    def apply_line_defaults(self):
        """Apply toolbar line style/width to every selected graphical object.

        This is intentionally selection-wide and type tolerant:
        - BODY updates the logical body and all imported/template graphics that
          visually form that body.
        - GRAPHIC updates its stroke style.
        - PIN updates its pin line style/width.
        Text/attributes are ignored here; their color is handled by the RGB
        button via apply_color_to_selected().
        """
        selected = list(self.scene.selectedItems()) if hasattr(self, 'scene') else []
        if not selected:
            return
        style = self.line_style.currentText()
        width = float(self.line_width.value())
        changed = False
        self.push_undo_state()
        self._selection_restore_ids = self._capture_selection_ids()
        for it in selected:
            k = it.data(0)
            m = getattr(it, 'model', None)
            if m is None:
                continue
            if k == 'PIN':
                m.line_style = style
                m.line_width = width
                changed = True
            elif k == 'GRAPHIC':
                st = getattr(m, 'style', None)
                if st is not None:
                    st.line_style = style
                    st.line_width = width
                    changed = True
            elif k == 'BODY':
                m.line_style = style
                m.line_width = width
                # Imported/template bodies are rendered by locked GraphicModel primitives.
                # Apply style to those real body graphics as well.
                for gr in self._body_owned_graphics(m):
                    st = getattr(gr, 'style', None)
                    if st is not None:
                        st.line_style = style
                        st.line_width = width
                changed = True
        if changed:
            self.dirty = True
            self.update_current_unit_canvas_positions()
            self.schedule_scene_refresh(visual_only=True)

    def add_pin(self, side, x=None, y=None):
        self.push_undo_state()
        p = create_auto_pin(self.symbol, self.current_unit, side)
        p.name = self._unique_pin_name(getattr(p, 'name', 'PIN'))
        if x is not None: p.x = x
        if y is not None: p.y = y
        # Keep the docking side strict; y may be edited freely.
        p.x = self.current_unit.body.x if side == PinSide.LEFT.value else self.current_unit.body.x + self.current_unit.body.width
        self.current_unit.pins.append(p)
        self.validate_pins(silent=True)
        self.select_model_after_rebuild(p)
        self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()

    def add_graphic(self, tool, x, y):
        self.push_undo_state()
        shape = {DrawTool.LINE.value: 'line', DrawTool.RECT.value: 'rect', DrawTool.ELLIPSE.value: 'ellipse'}[tool]
        if shape == 'line':
            # Lines are inserted initially as straight horizontal grid-aligned segments of length 2.
            model = GraphicModel(shape=shape, x=x, y=y, w=2.0, h=0.0, style=StyleModel(stroke=self.default_color, line_width=self.line_width.value(), line_style=self.line_style.currentText()))
        else:
            model = GraphicModel(shape=shape, x=x, y=y, style=StyleModel(stroke=self.default_color, line_width=self.line_width.value(), line_style=self.line_style.currentText()))
        model.locked_to_body = False
        model.graphic_role = 'user_graphic'
        model.mentor_raw = '__USER_GRAPHIC__'
        self.current_unit.graphics.append(model)
        self.select_model_after_rebuild(model)
        self.rebuild_scene(); self.rebuild_tree()

    def _edit_grid_step(self):
        try:
            return max(0.001, float(getattr(self, 'edit_grid_step', None) or self.edit_grid.value() or self.grid_inch))
        except Exception:
            return 1.0

    def _shift_current_unit_all(self, dx: float, dy: float):
        """Shift BODY and every child by the same delta.

        Used after non-center-origin resize/scale to keep the selected origin
        exactly at its designated grid position.  This prevents text/attributes
        drifting away from imported BODY graphics after repeated transforms.
        """
        u = self.current_unit
        b = u.body
        b.x = self._clean_float(float(b.x) + dx)
        b.y = self._clean_float(float(b.y) + dy)
        for p in getattr(u, 'pins', []) or []:
            p.x = self._clean_float(float(p.x) + dx)
            p.y = self._clean_float(float(p.y) + dy)
            self._move_pin_owned_texts(p, dx, dy)
        for t in getattr(u, 'texts', []) or []:
            t.x = self._clean_float(float(t.x) + dx)
            t.y = self._clean_float(float(t.y) + dy)
        for t in (getattr(b, 'attribute_texts', {}) or {}).values():
            try:
                t.x = self._clean_float(float(t.x) + dx)
                t.y = self._clean_float(float(t.y) + dy)
            except Exception:
                pass
        for gr in getattr(u, 'graphics', []) or []:
            gr.x = self._clean_float(float(gr.x) + dx)
            gr.y = self._clean_float(float(gr.y) + dy)

    def _body_owned_graphics(self, body=None):
        out=[]
        for gr in getattr(self.current_unit, 'graphics', []) or []:
            if getattr(gr, 'locked_to_body', False) or str(getattr(gr, 'graphic_role', '')).lower() in ('body','template_body','imported_body'):
                out.append(gr)
        return out

    def set_body_visual_attr(self, body, attr, value):
        """Edit BODY visual style for normal and imported/template bodies.

        Imported symbols often render the visible BODY through locked GraphicModel
        primitives.  BODY style edits therefore have to be propagated to those
        primitives as well; otherwise the property panel appears to do nothing.
        """
        if attr not in ('line_style', 'line_width', 'color'):
            return
        self.push_undo_state()
        setattr(body, attr, value)
        for gr in self._body_owned_graphics(body):
            st = getattr(gr, 'style', None)
            if st is None:
                continue
            if attr == 'line_style':
                st.line_style = value
            elif attr == 'line_width':
                st.line_width = float(value)
            elif attr == 'color':
                st.stroke = tuple(value)
        self.dirty = True
        self.update_current_unit_canvas_positions()
        self.schedule_scene_refresh(visual_only=True)

    def color_body_model(self, body):
        c = QColorDialog.getColor(QColor(*getattr(body, 'color', (0,0,0))), self)
        if c.isValid():
            self.set_body_visual_attr(body, 'color', (c.red(), c.green(), c.blue()))

    def _symbol_group_pivot_grid(self):
        """Return the logical symbol origin used for BODY-group transforms.

        The origin selector (center/top_left/bottom_left/...) is handled when the
        origin is reset: the selected BODY anchor is translated onto the symbol
        origin crosshair.  After that point the transform pivot must remain the
        fixed logical symbol origin (0, 0).  Recomputing the pivot from the
        already-transformed BODY bounds/corners is exactly what made imported
        symbols walk away for non-center origins during repeated flip/scale/rotate.

        Therefore all BODY-group operations use the stable symbol origin.
        """
        return (0.0, 0.0)

    def _body_center_grid(self, body=None):
        b = body or self.current_unit.body
        return (float(b.x) + float(b.width) / 2.0, float(b.y) - float(b.height) / 2.0)

    def _set_body_center_grid(self, body, cx, cy):
        body.x = float(cx) - float(body.width) / 2.0
        body.y = float(cy) + float(body.height) / 2.0

    def _graphic_center_grid(self, gr):
        return (float(gr.x) + float(getattr(gr, 'w', 0.0) or 0.0) / 2.0,
                float(gr.y) - float(getattr(gr, 'h', 0.0) or 0.0) / 2.0)

    def _set_graphic_center_grid(self, gr, cx, cy):
        gr.x = float(cx) - float(getattr(gr, 'w', 0.0) or 0.0) / 2.0
        gr.y = float(cy) + float(getattr(gr, 'h', 0.0) or 0.0) / 2.0

    def _clean_float(self, v):
        try:
            v = round(float(v), 9)
            return 0.0 if abs(v) < 1e-9 else v
        except Exception:
            return v

    def _rot_point(self, x, y, cx, cy, deg):
        a = math.radians(float(deg))
        dx, dy = float(x) - cx, float(y) - cy
        return (self._clean_float(cx + math.cos(a) * dx - math.sin(a) * dy),
                self._clean_float(cy + math.sin(a) * dx + math.cos(a) * dy))

    def _scale_point(self, x, y, cx, cy, factor):
        return (self._clean_float(cx + (float(x) - cx) * float(factor)),
                self._clean_float(cy + (float(y) - cy) * float(factor)))

    def _flip_point(self, x, y, cx, cy, horizontal=True):
        return (self._clean_float((2 * cx - float(x)) if horizontal else float(x)),
                self._clean_float(float(y) if horizontal else (2 * cy - float(y))))

    def _add_rotation(self, obj, deg):
        try:
            obj.rotation = self._clean_float((float(getattr(obj, 'rotation', 0.0) or 0.0) + float(deg)) % 360.0)
        except Exception:
            pass

    def _scale_font_model(self, font, factor):
        try:
            font.size_grid = max(0.1, float(getattr(font, 'size_grid', 0.75) or 0.75) * float(factor))
        except Exception:
            pass

    def _transform_pin_anchors(self, p, point_fn, rotate_deg=None, scale_factor=None, flip_horizontal=None):
        for ax, ay in (('label_x', 'label_y'), ('number_x', 'number_y')):
            if getattr(p, ax, None) is not None and getattr(p, ay, None) is not None:
                nx, ny = point_fn(float(getattr(p, ax)), float(getattr(p, ay)))
                setattr(p, ax, nx); setattr(p, ay, ny)
        for tm in (getattr(p, 'attribute_texts', {}) or {}).values():
            try:
                tm.x, tm.y = point_fn(float(tm.x), float(tm.y))
                # Pin attribute text follows the pin position but does not rotate.
                if False and rotate_deg is not None:
                    self._add_rotation(tm, rotate_deg)
                if scale_factor is not None:
                    tm.font_size_grid = max(0.1, float(getattr(tm, 'font_size_grid', 0.55) or 0.55) * float(scale_factor))
                if False and flip_horizontal is not None:
                    r = float(getattr(tm, 'rotation', 0.0) or 0.0)
                    tm.rotation = self._clean_float((-r) % 360.0 if flip_horizontal else (180.0 - r) % 360.0)
            except Exception:
                pass

    def _transform_body_attribute_texts(self, body, point_fn, rotate_deg=None, scale_factor=None, flip_horizontal=None):
        for tm in (getattr(body, 'attribute_texts', {}) or {}).values():
            try:
                tm.x, tm.y = point_fn(float(tm.x), float(tm.y))
                # Body attribute text follows BODY position but does not rotate.
                if False and rotate_deg is not None:
                    self._add_rotation(tm, rotate_deg)
                if scale_factor is not None:
                    tm.font_size_grid = max(0.1, float(getattr(tm, 'font_size_grid', 0.75) or 0.75) * float(scale_factor))
                if False and flip_horizontal is not None:
                    r = float(getattr(tm, 'rotation', 0.0) or 0.0)
                    tm.rotation = self._clean_float((-r) % 360.0 if flip_horizontal else (180.0 - r) % 360.0)
            except Exception:
                pass

    def _body_group_objects(self, unit=None):
        u = unit or self.current_unit
        b = u.body
        return b, list(getattr(u, 'pins', []) or []), list(getattr(u, 'texts', []) or []), list((getattr(b, 'attribute_texts', {}) or {}).values()), list(getattr(u, 'graphics', []) or [])

    def _snap_to_edit_grid(self, value, minimum=0.01):
        """Snap a model-space value to the current edit-grid multiple."""
        try:
            step = self._edit_grid_step()
        except Exception:
            step = 1.0
        try:
            v = round(float(value) / step) * step
        except Exception:
            v = float(minimum)
        return max(float(minimum), self._clean_float(v))

    def _set_body_width_grid(self, body, value):
        """Set BODY width through a group X-scale, snapped to edit-grid."""
        new_w = self._snap_to_edit_grid(value, 0.01)
        old_w = max(1e-9, float(getattr(body, 'width', new_w) or new_w))
        if abs(new_w - old_w) < 1e-9:
            return
        self.push_undo_state()
        self._selection_restore_ids = self._capture_selection_ids()
        self._transform_unit_as_body_group('scale_x_to', new_w)
        self.dirty = True
        QTimer.singleShot(0, self.refresh_properties)

    def _set_body_height_grid(self, body, value):
        """Set BODY height through a group Y-scale, snapped to edit-grid."""
        new_h = self._snap_to_edit_grid(value, 0.01)
        old_h = max(1e-9, float(getattr(body, 'height', new_h) or new_h))
        if abs(new_h - old_h) < 1e-9:
            return
        self.push_undo_state()
        self._selection_restore_ids = self._capture_selection_ids()
        self._transform_unit_as_body_group('scale_y_to', new_h)
        self.dirty = True
        QTimer.singleShot(0, self.refresh_properties)

    def _set_body_rotation_90(self, body, value):
        """Rotate BODY group only to absolute 0/90/180/270 degrees."""
        try:
            target = (round(float(value) / 90.0) * 90.0) % 360.0
        except Exception:
            target = 0.0
        current = float(getattr(body, 'rotation', 0.0) or 0.0) % 360.0
        delta = target - current
        if delta > 180.0:
            delta -= 360.0
        elif delta < -180.0:
            delta += 360.0
        if abs(delta) < 1e-9:
            return
        self.push_undo_state()
        self._selection_restore_ids = self._capture_selection_ids()
        self._transform_unit_as_body_group('rotate', delta)
        body.rotation = target
        self.dirty = True
        QTimer.singleShot(0, self.refresh_properties)

    # ----------------------------- Drift-free BODY group transform core
    def _mat_mul(self, A, B):
        """2x2 matrix multiplication for BODY-group transforms."""
        a,b,c,d = A; e,f,g,h = B
        return (a*e + b*g, a*f + b*h, c*e + d*g, c*f + d*h)

    def _mat_apply(self, M, x, y, px, py):
        a,b,c,d = M
        dx, dy = float(x) - float(px), float(y) - float(py)
        return (self._clean_float(px + a*dx + b*dy),
                self._clean_float(py + c*dx + d*dy))

    def _mat_col_angle(self, M):
        a,b,c,d = M
        return math.degrees(math.atan2(c, a))

    def _mat_x_scale(self, M):
        a,b,c,d = M
        return max(1e-9, math.hypot(a, c))

    def _mat_y_scale(self, M):
        a,b,c,d = M
        return max(1e-9, math.hypot(b, d))

    def _invalidate_body_group_transform_cache(self, unit=None):
        """Drop the drift-free transform base after manual edits/import changes.

        The cache is intentionally transient and is never persisted.  The next
        BODY transform will capture a fresh local-coordinate base from the
        current visible model.
        """
        try:
            u = unit or self.current_unit
            if hasattr(u, '_body_group_transform'):
                delattr(u, '_body_group_transform')
        except Exception:
            pass



    def _body_graphics_for_unit(self, unit=None):
        u = unit or self.current_unit
        out = []
        for gr in getattr(u, 'graphics', []) or []:
            role = str(getattr(gr, 'graphic_role', '') or '').lower()
            if getattr(gr, 'locked_to_body', False) or role in ('body', 'template_body', 'imported_body'):
                out.append(gr)
        return out

    def _unit_translate_all_objects(self, unit, dx: float, dy: float):
        if abs(dx) < 1e-12 and abs(dy) < 1e-12:
            return
        b = unit.body
        b.x = self._clean_float(float(b.x) + dx)
        b.y = self._clean_float(float(b.y) + dy)
        for gr in getattr(unit, 'graphics', []) or []:
            gr.x = self._clean_float(float(gr.x) + dx)
            gr.y = self._clean_float(float(gr.y) + dy)
        for p in getattr(unit, 'pins', []) or []:
            p.x = self._clean_float(float(p.x) + dx)
            p.y = self._clean_float(float(p.y) + dy)
            self._move_pin_owned_texts(p, dx, dy)
        for t in getattr(unit, 'texts', []) or []:
            t.x = self._clean_float(float(t.x) + dx)
            t.y = self._clean_float(float(t.y) + dy)
        for t in (getattr(b, 'attribute_texts', {}) or {}).values():
            try:
                t.x = self._clean_float(float(t.x) + dx)
                t.y = self._clean_float(float(t.y) + dy)
            except Exception:
                pass

    def _body_bounds_grid_for_origin(self, unit=None):
        u = unit or self.current_unit
        b = u.body
        body_graphics = self._body_graphics_for_unit(u)
        xs, ys = [], []
        if body_graphics:
            for gr in body_graphics:
                gx = float(getattr(gr, 'x', 0.0) or 0.0)
                gy = float(getattr(gr, 'y', 0.0) or 0.0)
                gw = float(getattr(gr, 'w', 0.0) or 0.0)
                gh = float(getattr(gr, 'h', 0.0) or 0.0)
                # For this first consolidation step we intentionally use the real
                # model endpoints/top-left extents, not pin/text/attribute extents.
                xs.extend([gx, gx + gw])
                ys.extend([gy, gy - gh])
        if not xs or not ys:
            xs.extend([float(b.x), float(b.x) + float(b.width)])
            ys.extend([float(b.y), float(b.y) - float(b.height)])
        minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
        return (self._clean_float(minx), self._clean_float(miny), self._clean_float(maxx), self._clean_float(maxy))

    def _anchor_from_bounds(self, bounds, mode=None):
        minx, miny, maxx, maxy = bounds
        mode = str(mode or getattr(self.symbol, 'origin', OriginMode.CENTER.value) or OriginMode.CENTER.value)
        if mode == OriginMode.BOTTOM_LEFT.value:
            return minx, miny
        if mode == OriginMode.BOTTOM_RIGHT.value:
            return maxx, miny
        if mode == OriginMode.TOP_LEFT.value:
            return minx, maxy
        if mode == OriginMode.TOP_RIGHT.value:
            return maxx, maxy
        return (minx + maxx) / 2.0, (miny + maxy) / 2.0

    def _sync_body_model_to_body_bounds_only(self, unit=None):
        u = unit or self.current_unit
        b = u.body
        minx, miny, maxx, maxy = self._body_bounds_grid_for_origin(u)
        if maxx - minx > 1e-9 and maxy - miny > 1e-9:
            b.x = self._clean_float(minx)
            b.y = self._clean_float(maxy)
            b.width = self._clean_float(maxx - minx)
            b.height = self._clean_float(maxy - miny)

    def _normalize_unit_body_anchor_to_symbol_origin(self, unit=None):
        """Make imported/template units follow the same coordinate contract as Symbol 1.

        BODY bounds are derived only from BODY graphics (or the native BODY rect
        when there are no BODY graphics).  The selected OriginMode says which
        point of those BODY bounds lies at canvas coordinate 0/0.  Pins, texts,
        body attributes and user graphics are translated by the same delta, so
        all dependencies stay rigid.
        """
        u = unit or self.current_unit
        self._sync_body_model_to_body_bounds_only(u)
        ax, ay = self._anchor_from_bounds(self._body_bounds_grid_for_origin(u))
        dx, dy = self._clean_float(-ax), self._clean_float(-ay)
        if abs(dx) > 1e-9 or abs(dy) > 1e-9:
            self._unit_translate_all_objects(u, dx, dy)
            self._sync_body_model_to_body_bounds_only(u)
            self._invalidate_body_group_transform_cache(u)

    def _sync_imported_body_model_to_body_graphics(self, unit=None):
        """Compatibility wrapper: imported/template BODY graphics define BODY bounds.

        Previous revisions sometimes treated this as a separate proxy rectangle.
        This step keeps the model congruent with the real BODY graphics only; no
        pins/text/attributes are included in BODY bounds.
        """
        try:
            self._sync_body_model_to_body_bounds_only(unit or self.current_unit)
        except Exception:
            pass

    def _body_group_capture_base(self, unit=None):
        """Capture one immutable base state for the complete symbol part.

        Critical rule: the complete BODY group is stored as local coordinates
        relative to the selected BODY origin anchor.  The transform destination
        is the logical symbol origin (normally 0/0).  This makes imported
        symbols behave like internally created <NONE> symbols: even if an
        imported template arrived with its BODY anchor away from the crosshair,
        the first transform normalizes the complete group as one rigid object
        instead of rotating/scaling individual world coordinates.
        """
        u = unit or self.current_unit
        # Imported/template BODY graphics are the real BODY.  Normalize them to
        # the same coordinate contract as the native Symbol 1/<NONE> body before
        # capturing the immutable local-coordinate base.
        self._normalize_unit_body_anchor_to_symbol_origin(u)
        b = u.body
        mode = getattr(self.symbol, 'origin', OriginMode.CENTER.value)
        # All BODY-group transforms use the fixed logical symbol origin.
        # The selected OriginMode only defines how the BODY is initially aligned
        # to the 0/0 crosshair. After that, rotate/scale/flip must never
        # recalculate a new anchor from transformed bounds, otherwise pins,
        # attributes and texts drift for non-center origins.
        ax, ay = self._symbol_group_pivot_grid()
        px, py = ax, ay
        base = {
            'pivot': (float(px), float(py)),
            'anchor': (float(ax), float(ay)),
            'origin_mode': mode,
            'body': {
                'x': float(b.x), 'y': float(b.y), 'w': float(b.width), 'h': float(b.height),
                'rot': float(getattr(b, 'rotation', 0.0) or 0.0),
                'scale_x': float(getattr(b, 'scale_x', 1.0) or 1.0),
                'scale_y': float(getattr(b, 'scale_y', 1.0) or 1.0),
            },
            'pins': [], 'texts': [], 'body_attrs': [], 'graphics': []
        }
        for p in getattr(u, 'pins', []) or []:
            pd = {
                'obj': p,
                'x': float(p.x), 'y': float(p.y),
                'length': float(getattr(p, 'length', 1.0) or 1.0),
                'rot': float(getattr(p, 'rotation', 0.0) or 0.0),
                'scale_x': float(getattr(p, 'scale_x', 1.0) or 1.0),
                'scale_y': float(getattr(p, 'scale_y', 1.0) or 1.0),
                'number_font_size': float(getattr(getattr(p, 'number_font', None), 'size_grid', 0.45) or 0.45),
                'label_font_size': float(getattr(getattr(p, 'label_font', None), 'size_grid', 0.55) or 0.55),
                'label': None, 'number': None, 'attrs': []
            }
            if getattr(p, 'label_x', None) is not None and getattr(p, 'label_y', None) is not None:
                pd['label'] = (float(p.label_x), float(p.label_y))
            if getattr(p, 'number_x', None) is not None and getattr(p, 'number_y', None) is not None:
                pd['number'] = (float(p.number_x), float(p.number_y))
            for key, tm in (getattr(p, 'attribute_texts', {}) or {}).items():
                try:
                    pd['attrs'].append((key, tm, float(tm.x), float(tm.y), float(getattr(tm, 'rotation', 0.0) or 0.0), float(getattr(tm, 'font_size_grid', 0.55) or 0.55)))
                except Exception:
                    pass
            base['pins'].append(pd)
        for t in getattr(u, 'texts', []) or []:
            try:
                base['texts'].append({'obj': t, 'x': float(t.x), 'y': float(t.y), 'rot': float(getattr(t, 'rotation', 0.0) or 0.0), 'font': float(getattr(t, 'font_size_grid', .75) or .75)})
            except Exception:
                pass
        for key, t in (getattr(b, 'attribute_texts', {}) or {}).items():
            try:
                base['body_attrs'].append({'key': key, 'obj': t, 'x': float(t.x), 'y': float(t.y), 'rot': float(getattr(t, 'rotation', 0.0) or 0.0), 'font': float(getattr(t, 'font_size_grid', .75) or .75)})
            except Exception:
                pass
        for gr in getattr(u, 'graphics', []) or []:
            try:
                base['graphics'].append({
                    'obj': gr,
                    'x': float(gr.x), 'y': float(gr.y),
                    'w': float(getattr(gr, 'w', 0.0) or 0.0),
                    'h': float(getattr(gr, 'h', 0.0) or 0.0),
                    'rot': float(getattr(gr, 'rotation', 0.0) or 0.0),
                    'scale_x': float(getattr(gr, 'scale_x', 1.0) or 1.0),
                    'scale_y': float(getattr(gr, 'scale_y', 1.0) or 1.0),
                    'ctrl_x': getattr(gr, 'ctrl_x', None),
                    'ctrl_y': getattr(gr, 'ctrl_y', None),
                    'curve_radius': float(getattr(gr, 'curve_radius', 0.0) or 0.0),
                })
            except Exception:
                pass
        u._body_group_transform = {'base': base, 'M': (1.0, 0.0, 0.0, 1.0)}
        return u._body_group_transform

    def _body_group_state(self, unit=None):
        u = unit or self.current_unit
        st = getattr(u, '_body_group_transform', None)
        if not isinstance(st, dict) or 'base' not in st or 'M' not in st:
            st = self._body_group_capture_base(u)
        else:
            # If the user changed origin mode, rebuild the local-coordinate base.
            try:
                if st['base'].get('origin_mode') != getattr(self.symbol, 'origin', OriginMode.CENTER.value):
                    st = self._body_group_capture_base(u)
            except Exception:
                st = self._body_group_capture_base(u)
        return st

    def _apply_body_group_matrix_from_base(self, st, refresh=True):
        base = st['base']; M = st['M']; px, py = base['pivot']
        ax, ay = base.get('pivot', (0.0, 0.0))
        def app(x, y):
            # Apply the accumulated matrix strictly around the fixed logical
            # symbol origin. The base coordinates are already world/model
            # coordinates relative to that origin; do not normalize through a
            # BODY-bound anchor here. This makes rotate, flip and scale act like
            # one rigid object for BODY + pins + texts + attributes + graphics.
            a,bm,c,d = M
            dx, dy = float(x) - float(px), float(y) - float(py)
            return (self._clean_float(px + a*dx + bm*dy),
                    self._clean_float(py + c*dx + d*dy))
        u = self.current_unit; b = u.body
        bs = base['body']
        sx_abs = self._mat_x_scale(M)
        sy_abs = self._mat_y_scale(M)
        font_factor = max(0.1, (abs(sx_abs) + abs(sy_abs)) / 2.0)

        # BODY from immutable base: center transformed, dimensions derived from matrix.
        bx, by, bw, bh = bs['x'], bs['y'], bs['w'], bs['h']
        bc_x, bc_y = bx + bw/2.0, by - bh/2.0
        ncx, ncy = app(bc_x, bc_y)
        b.width = self._clean_float(max(0.01, bw * sx_abs))
        b.height = self._clean_float(max(0.01, bh * sy_abs))
        b.rotation = self._clean_float((bs['rot'] + self._mat_col_angle(M)) % 360.0)
        b.scale_x = bs.get('scale_x', 1.0)
        b.scale_y = bs.get('scale_y', 1.0)
        self._set_body_center_grid(b, ncx, ncy)

        # Graphics: centers are transformed from base.  Geometry uses the absolute
        # matrix scale.  Rotation comes from the matrix angle.  This keeps imported
        # body artwork and user graphics as real geometry, without proxy frames.
        for gd in base.get('graphics', []):
            gr = gd['obj']
            gcx, gcy = gd['x'] + gd['w']/2.0, gd['y'] - gd['h']/2.0
            ngcx, ngcy = app(gcx, gcy)
            gr.w = self._clean_float(gd['w'] * sx_abs)
            gr.h = self._clean_float(gd['h'] * sy_abs)
            gr.rotation = self._clean_float((gd['rot'] + self._mat_col_angle(M)) % 360.0)
            gr.scale_x = gd.get('scale_x', 1.0)
            gr.scale_y = gd.get('scale_y', 1.0)
            if gd.get('ctrl_x') is not None:
                # Control points are local vectors; transform them by matrix without pivot.
                a,bm,c,d = M
                gr.ctrl_x = self._clean_float(a*float(gd['ctrl_x']) + bm*float(gd.get('ctrl_y') or 0.0))
            if gd.get('ctrl_y') is not None:
                a,bm,c,d = M
                gr.ctrl_y = self._clean_float(c*float(gd.get('ctrl_x') or 0.0) + d*float(gd['ctrl_y']))
            try:
                gr.curve_radius = self._clean_float(gd.get('curve_radius', 0.0) * font_factor)
            except Exception:
                pass
            self._set_graphic_center_grid(gr, ngcx, ngcy)

        # After transforming real BODY graphics, the logical BODY bounds must be
        # recomputed from those graphics. This prevents a separate proxy BODY from
        # diverging from the drawn object. Native <NONE> bodies have no locked
        # graphics, so their BODY rect remains the transformed native body above.
        if self._body_graphics_for_unit(u):
            self._sync_body_model_to_body_bounds_only(u)

        # Pins: endpoint anchors follow the group.  The pin item itself may rotate
        # through model.rotation, so visual pin direction stays attached to BODY.
        for pd in base.get('pins', []):
            p = pd['obj']
            p.x, p.y = app(pd['x'], pd['y'])
            p.rotation = self._clean_float((pd['rot'] + self._mat_col_angle(M)) % 360.0)
            p.scale_x = pd.get('scale_x', 1.0)
            p.scale_y = pd.get('scale_y', 1.0)
            p.length = self._clean_float(max(0.1, pd['length'] * font_factor))
            if pd.get('label') is not None:
                p.label_x, p.label_y = app(pd['label'][0], pd['label'][1])
            if pd.get('number') is not None:
                p.number_x, p.number_y = app(pd['number'][0], pd['number'][1])
            try:
                p.number_font.size_grid = max(0.1, self._clean_float(pd.get('number_font_size', 0.45) * font_factor))
            except Exception:
                pass
            try:
                p.label_font.size_grid = max(0.1, self._clean_float(pd.get('label_font_size', 0.55) * font_factor))
            except Exception:
                pass
            for key, tm, tx, ty, trot, tf in pd.get('attrs', []):
                try:
                    tm.x, tm.y = app(tx, ty)
                    # Text moves with the group but remains readable: no rotate/mirror.
                    tm.rotation = trot
                    tm.font_size_grid = max(0.1, self._clean_float(tf * font_factor))
                except Exception:
                    pass

        # Free texts and BODY attributes: position follows exactly, glyphs are not
        # rotated or mirrored, per requested Xpedition-like behaviour.
        for td in base.get('texts', []):
            t = td['obj']
            t.x, t.y = app(td['x'], td['y'])
            t.rotation = td['rot']
            t.font_size_grid = max(0.1, self._clean_float(td['font'] * font_factor))
        for td in base.get('body_attrs', []):
            t = td['obj']
            t.x, t.y = app(td['x'], td['y'])
            t.rotation = td['rot']
            t.font_size_grid = max(0.1, self._clean_float(td['font'] * font_factor))

        # Normalize tiny float noise only.  Do not apply a corrective offset; the
        # immutable base + matrix is exactly what prevents accumulating drift.
        for obj in [b] + list(getattr(u, 'pins', []) or []) + list(getattr(u, 'texts', []) or []) + list(getattr(u, 'graphics', []) or []) + list((getattr(b, 'attribute_texts', {}) or {}).values()):
            for attr in ('x','y','width','height','w','h','rotation','scale_x','scale_y'):
                if hasattr(obj, attr):
                    try: setattr(obj, attr, self._clean_float(getattr(obj, attr)))
                    except Exception: pass
        if refresh:
            # Do NOT regenerate BODY attribute text items during a group transform.
            # Regeneration recalculates default positions from BODY bounds for
            # imported/templates and breaks the local BODY-group transform.
            # The TextItem instances already reference the transformed TextModel
            # objects, so updating their canvas positions is sufficient and keeps
            # attributes rigidly attached to the group.
            self.update_current_unit_canvas_positions()
            self.rebuild_tree(); self.rebuild_pin_table()

    def _transform_unit_as_body_group(self, op, value=None, refresh=True):
        """Drift-free BODY-group transform.

        The complete split part/symbol is handled as one logical object.  A
        transient immutable base is captured once, then an accumulated 2x2 matrix
        is applied from that base after each operation.  Therefore repeated
        rotations/scales/flips with any OriginMode cannot walk pins, attributes,
        texts or imported BODY graphics away from each other.
        """
        st = self._body_group_state(self.current_unit)
        M = st.get('M', (1.0,0.0,0.0,1.0))
        if op == 'rotate':
            deg = float(value or 0.0)
            # Rotate CW/CCW around the active symbol origin by the requested
            # angle. Do not snap here; the toolbar buttons define the step.
            if abs(deg) < 1e-9:
                return
            a = math.radians(deg)
            Op = (math.cos(a), -math.sin(a), math.sin(a), math.cos(a))
            st['M'] = self._mat_mul(Op, M)
        elif op in ('scale', 'scale_x_to', 'scale_y_to'):
            # Scale to edit-grid multiples.  scale_x_to/scale_y_to are absolute
            # BODY sizes; scale is relative to the current rendered size.
            cur_w = max(1e-9, float(getattr(self.current_unit.body, 'width', 1.0) or 1.0))
            cur_h = max(1e-9, float(getattr(self.current_unit.body, 'height', 1.0) or 1.0))
            if op == 'scale_x_to':
                sx = self._snap_to_edit_grid(float(value), 0.01) / cur_w
                sy = 1.0
            elif op == 'scale_y_to':
                sx = 1.0
                sy = self._snap_to_edit_grid(float(value), 0.01) / cur_h
            else:
                f = float(value or 1.0)
                # Compute the snapped target from the current rendered dimensions.
                sx = self._snap_to_edit_grid(cur_w * f, 0.01) / cur_w
                sy = self._snap_to_edit_grid(cur_h * f, 0.01) / cur_h
            Op = (sx, 0.0, 0.0, sy)
            st['M'] = self._mat_mul(Op, M)
        elif op == 'flip_h':
            st['M'] = self._mat_mul((-1.0,0.0,0.0,1.0), M)
        elif op == 'flip_v':
            st['M'] = self._mat_mul((1.0,0.0,0.0,-1.0), M)
        else:
            return
        self._apply_body_group_matrix_from_base(st, refresh=refresh)
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
        self.clipboard = []
        for it in self.scene.selectedItems():
            if it.data(0) in ('PIN', 'TEXT', 'GRAPHIC', 'BODY'):
                self.clipboard.append((it.data(0), copy.deepcopy(it.model)))
        if self.clipboard:
            self.statusBar().showMessage(f'Copied {len(self.clipboard)} object(s).', 2500)

    def cut_selected(self):
        self.set_tool(DrawTool.SELECT.value)
        self.clipboard = []
        for it in self.scene.selectedItems():
            if it.data(0) in ('PIN', 'TEXT', 'GRAPHIC', 'BODY'):
                self.clipboard.append((it.data(0), copy.deepcopy(it.model)))
        self.clipboard_is_cut = True
        self.delete_selected()

    def paste_selected(self):
        self.set_tool(DrawTool.SELECT.value)
        self.push_undo_state()
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
                # Copy creates unique pin numbers and names; cut/paste keeps them.
                if not getattr(self, 'clipboard_is_cut', False):
                    m.number = next_pin_number(existing_pins)
                    existing_pins.append(m.number)
                    m.name = self._unique_pin_name(getattr(m, 'name', 'PIN'))
                self.current_unit.pins.append(m)
                pasted_models.append(m)
            elif kind == 'TEXT':
                self.current_unit.texts.append(m)
                pasted_models.append(m)
            elif kind == 'GRAPHIC':
                m.locked_to_body = False
                m.graphic_role = 'user_graphic'
                m.mentor_raw = '__USER_GRAPHIC__'
                self.current_unit.graphics.append(m)
                pasted_models.append(m)
            elif kind == 'BODY':
                self.current_unit.body = m
                pasted_models.append(m)
        self.dock_pins_to_body(self.current_unit)
        self.clipboard_is_cut = False
        self._selection_restore_ids = {id(m) for m in pasted_models}
        self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()

    def delete_selected(self):
        self.set_tool(DrawTool.SELECT.value)
        self.push_undo_state()
        sel = [i for i in self.scene.selectedItems() if i.data(0) in ('PIN', 'TEXT', 'GRAPHIC')]
        if not sel: return
        u = self.current_unit
        for it in sel:
            if it.data(0) == 'PIN': u.pins = [p for p in u.pins if p is not it.model]
            elif it.data(0) == 'TEXT': u.texts = [t for t in u.texts if t is not it.model]
            elif it.data(0) == 'GRAPHIC': u.graphics = [g for g in u.graphics if g is not it.model]
        self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()

    def _total_pin_count(self, symbol=None):
        symbol = symbol or self.symbol
        try:
            return sum(len(getattr(u, 'pins', []) or []) for u in getattr(symbol, 'units', []) or [])
        except Exception:
            return 0

    def validate_pins(self, silent=False):
        """Validate all pins and report counts plus a detailed error list."""
        total_pins = self._total_pin_count(self.symbol)
        units = list(getattr(self.symbol, 'units', []) or [])
        unit_count = len(units)

        number_occ = {}
        name_occ = {}
        empty_numbers = []
        empty_names = []
        for ui, u in enumerate(units, start=1):
            unit_name = str(getattr(u, 'name', '') or f'Unit {ui}')
            for pi, p in enumerate(getattr(u, 'pins', []) or [], start=1):
                number = str(getattr(p, 'number', '') or '').strip()
                name = str(getattr(p, 'name', '') or '').strip()
                pin_desc = f'{unit_name} / Pin {pi}: number="{number}", name="{name}"'
                if number:
                    number_occ.setdefault(number, []).append(pin_desc)
                else:
                    empty_numbers.append(pin_desc)
                if name:
                    name_occ.setdefault(name, []).append(pin_desc)
                else:
                    empty_names.append(pin_desc)

        duplicate_numbers = {k: v for k, v in number_occ.items() if len(v) > 1}
        duplicate_names = {k: v for k, v in name_occ.items() if len(v) > 1}
        ok = not duplicate_numbers and not duplicate_names
        if silent:
            return ok

        details = []
        if duplicate_numbers:
            details.append('Doppelte Pinnummern:')
            for number, entries in sorted(duplicate_numbers.items(), key=lambda kv: kv[0]):
                details.append(f'  Pinnummer {number}:')
                details.extend('    - ' + e for e in entries)
        if duplicate_names:
            if details:
                details.append('')
            details.append('Doppelte Pinnamen:')
            for name, entries in sorted(duplicate_names.items(), key=lambda kv: kv[0].lower()):
                details.append(f'  Pinname {name}:')
                details.extend('    - ' + e for e in entries)
        warnings = []
        if empty_numbers:
            warnings.append(f'Pins ohne Pinnummer: {len(empty_numbers)}')
        if empty_names:
            warnings.append(f'Pins ohne Pinname: {len(empty_names)}')
        if warnings:
            if details:
                details.append('')
            details.append('Hinweise / Warnungen:')
            details.extend('  - ' + w for w in warnings)

        summary = f'Pins gesamt: {total_pins}\nUnits/Parts: {unit_count}'
        box = QMessageBox(self)
        box.setWindowTitle('Pin validation')
        box.setIcon(QMessageBox.Information if ok else QMessageBox.Warning)
        if ok:
            box.setText(summary + '\n\nKeine doppelten Pinnummern oder Pinnamen gefunden.')
        else:
            box.setText(summary + '\n\nEs wurden Pin-Fehler gefunden, die behoben werden müssen.')
            box.setInformativeText('Details öffnen, um die betroffenen Pins je Unit/Part zu sehen.')
        if details:
            box.setDetailedText('\n'.join(details))
        box.exec()
        return ok

    def _current_unit_bounds_grid(self):
        u = self.current_unit
        xs, ys = [], []
        b = u.body
        xs.extend([b.x, b.x + b.width]); ys.extend([b.y, b.y - b.height])
        for p in u.pins:
            xs.extend([p.x - p.length, p.x + p.length]); ys.append(p.y)
        for t in u.texts:
            xs.append(t.x); ys.append(t.y)
        for t in getattr(u.body, 'attribute_texts', {}).values():
            xs.append(t.x); ys.append(t.y)
        for g in u.graphics:
            xs.extend([g.x, g.x + g.w]); ys.extend([g.y, g.y - g.h])
        if not xs:
            return 0.0, 0.0, 0.0, 0.0
        return min(xs), min(ys), max(xs), max(ys)

    def _origin_anchor_from_bounds(self, bounds, mode: str):
        x0, y0, x1, y1 = bounds
        mapping = {
            OriginMode.TOP_LEFT.value: (x0, y1),
            OriginMode.TOP_RIGHT.value: (x1, y1),
            OriginMode.BOTTOM_LEFT.value: (x0, y0),
            OriginMode.BOTTOM_RIGHT.value: (x1, y0),
            OriginMode.CENTER.value: ((x0 + x1) / 2.0, (y0 + y1) / 2.0),
        }
        return mapping.get(mode, mapping[OriginMode.CENTER.value])

    def set_format_guide_to_active_origin(self):
        """Refresh the sheet/recommended-area guide for the active origin.

        The guide is now purely origin-driven: the crosshair is the selected
        symbol origin, the red recommended drawing area is anchored at that
        origin according to the selected direction, and the blue sheet preview is
        centered around the red area.  No symbol bounds are used here, so the
        guide can never cause late autoscaling, recentering, or split-unit global
        movement.
        """
        self._format_guide_offset = (0.0, 0.0)
        if hasattr(self, 'scene'):
            self.scene.update()

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


    def _text_items_only(self, items):
        return [i for i in items if i.data(0) in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY') and getattr(i, 'model', None) is not None]

    def _snap_text_anchor_to_grid(self, item):
        if getattr(item, 'model', None) is None:
            return
        item.model.x = round(float(getattr(item.model, 'x', 0.0) or 0.0))
        item.model.y = round(float(getattr(item.model, 'y', 0.0) or 0.0))

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
    def pin_table_changed(self, r, c):
        table = self.sender()
        if self.suspend or not isinstance(table, QTableWidget):
            return
        self._commit_pin_table_value(table, r, c)

    def _commit_pin_table_value(self, table: QTableWidget, r: int, c: int):
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
        self.push_undo_state()
        if col == 0:
            p.number = val
        elif col == 1:
            p.name = val
        elif col == 2:
            p.function = val
        elif col == 3:
            p.pin_type = val
        elif col == 4:
            p.side = val if val in [x.value for x in PinSide] else p.side
        elif col == 5:
            p.inverted = val.lower() in ('1', 'true', 'yes', 'ja', 'x')
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
        # Switching between Symbols and Split Symbols must be immediate: no discard prompt.
        kind = SymbolKind.SINGLE.value if idx == 0 else SymbolKind.SPLIT.value
        indices = self._symbol_indices(kind)
        if not indices:
            self.rebuild_canvas_tabs(); self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()
            return
        tabs = self.single_tabs if kind == SymbolKind.SINGLE.value else self.split_tabs
        tab_index = max(0, tabs.currentIndex())
        tab_index = min(tab_index, len(indices) - 1)
        self.library.current_symbol_index = indices[tab_index]
        self.current_unit_index = 0
        self.rebuild_canvas_tabs(); self.rebuild_unit_tabs(); self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()
        self.update_name_editors()

    def change_symbol_from_canvas_tab(self, tab_index: int):
        # Switching between already-created symbols never discards edits.
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
        target_index = indices[tab_index]
        self.library.current_symbol_index = target_index
        self.current_unit_index = 0
        self.rebuild_canvas_tabs(); self.rebuild_unit_tabs(); self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()
        self.update_name_editors()
        self.grid_spin.blockSignals(True); self.grid_spin.setValue(self.symbol.grid_inch); self.grid_spin.blockSignals(False)
        self._sync_edit_grid_combo_to_symbol()
        self.format_combo.blockSignals(True); self.format_combo.setCurrentText(getattr(self.symbol, 'sheet_format', SheetFormat.A3.value)); self.format_combo.blockSignals(False)

    def change_unit(self, i):
        if i < 0: return
        self.current_unit_index = i
        self.rebuild_canvas_tabs(); self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table(); self.update_name_editors()

    def new_single_symbol(self):
        spec = self.ask_new_symbol_template(SymbolKind.SINGLE.value)
        if spec is None:
            return
        name, template_name = spec
        self.push_undo_state()
        s = self.library.add_symbol(name or 'Symbol', SymbolKind.SINGLE.value)
        s.name = self.library.unique_import_name(name or s.name)
        s.template_name = template_name
        s.units = [self.load_template_unit(template_name)]
        s.units[0].name = 'Unit A'
        self.normalize_symbol_origins_for_import(s)
        self.current_unit_index = 0
        self.rebuild_all()

    def new_split_symbol(self):
        spec = self.ask_new_symbol_template(SymbolKind.SPLIT.value)
        if spec is None:
            return
        name, template_name = spec
        self.push_undo_state()
        s = self.library.add_symbol(name or 'Split Symbol', SymbolKind.SPLIT.value)
        s.name = self.library.unique_import_name(name or s.name)
        s.template_name = template_name
        split_units = self.load_split_template_units(template_name)
        if split_units:
            s.units = split_units
        else:
            base = self.load_template_unit(template_name)
            s.units = [copy.deepcopy(base), copy.deepcopy(base)]
        self.normalize_symbol_origins_for_import(s)
        for i, u in enumerate(s.units, start=1):
            u.name = f'{s.name}_{i}'
        self.current_unit_index = 0
        self.rebuild_all()

    def add_unit(self):
        self.push_undo_state()
        if self.symbol.kind != SymbolKind.SPLIT.value:
            QMessageBox.information(self, 'Split Symbol', 'Units can only be created in split symbols. Please create a New Split Symbol.')
            return
        self.symbol.units.append(SymbolUnitModel(name=f'{self.symbol.name}_{len(self.symbol.units) + 1}'))
        self.current_unit_index = len(self.symbol.units) - 1
        self.rebuild_canvas_tabs(); self.rebuild_unit_tabs(); self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()

    def set_grid(self, v):
        self.push_undo_state()
        self.symbol.grid_inch = v
        # Keep edit grid valid against the new base grid.
        if getattr(self, 'edit_grid_inch', v) > v:
            self.edit_grid_inch = v
        self.rebuild_scene()

    def set_edit_grid(self, text):
        try:
            self.edit_grid_inch = float(str(text).replace('"', '').strip())
        except Exception:
            self.edit_grid_inch = float(getattr(self.symbol, 'grid_inch', 0.100) or 0.100)
        self.scene.update()

    def _current_symbol_has_half_grid_geometry(self):
        try:
            values = []
            for u in self.symbol.units:
                b = u.body
                values.extend([b.x, b.y, b.width, b.height])
                for p in u.pins:
                    values.extend([p.x, p.y, p.length])
                for t in u.texts:
                    values.extend([t.x, t.y, t.font_size_grid])
                for t in (getattr(u.body, 'attribute_texts', {}) or {}).values():
                    values.extend([t.x, t.y, t.font_size_grid])
                for g in u.graphics:
                    values.extend([g.x, g.y, g.w, g.h])
            return any(abs(float(v) * 2 - round(float(v) * 2)) < 1e-6 and abs(float(v) - round(float(v))) > 1e-6 for v in values)
        except Exception:
            return False

    def _sync_edit_grid_combo_to_symbol(self):
        if not hasattr(self, 'edit_grid_combo'):
            return
        target = '0.050"' if self._current_symbol_has_half_grid_geometry() else '0.100"'
        self.edit_grid_combo.blockSignals(True)
        self.edit_grid_combo.setCurrentText(target)
        self.edit_grid_combo.blockSignals(False)
        self.set_edit_grid(target)

    def set_sheet_format(self, fmt):
        self.push_undo_state()
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


    # ------------------------------------------------------------------ History / template editing / canvas helpers
    def push_undo_state(self):
        if self._history_guard:
            return
        if not self.dirty:
            self._dirty_symbol_index = self.library.current_symbol_index
            self._clean_symbol_snapshot = copy.deepcopy(self.symbol)
        self.undo_stack.append(copy.deepcopy(self.library))
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.dirty = True

    def _restore_active_symbol_and_unit_after_history(self, previous_symbol_index: int, previous_unit_index: int, previous_unit_name: str | None):
        """Keep the visible split part stable after undo/redo.

        Older history handling always reset current_unit_index to 0, which made
        Ctrl+Z/Ctrl+Y jump to the first split part.  The history snapshot itself
        already contains the current library state; this helper only restores the
        user's active focus as far as the restored model still allows it.
        """
        if not self.library.symbols:
            self.library.current_symbol_index = 0
            self.current_unit_index = 0
            return
        self.library.current_symbol_index = max(0, min(previous_symbol_index, len(self.library.symbols) - 1))
        units = self.library.symbols[self.library.current_symbol_index].units
        if not units:
            self.current_unit_index = 0
            return
        if previous_unit_name:
            for idx, unit in enumerate(units):
                if unit.name == previous_unit_name:
                    self.current_unit_index = idx
                    return
        self.current_unit_index = max(0, min(previous_unit_index, len(units) - 1))

    def undo(self):
        self.set_tool(DrawTool.SELECT.value)
        if not self.undo_stack:
            self.statusBar().showMessage('Undo-Historie ist leer.', 2000)
            return
        prev_symbol_index = self.library.current_symbol_index
        prev_unit_index = self.current_unit_index
        prev_unit_name = None
        try:
            prev_unit_name = self.library.symbols[prev_symbol_index].units[prev_unit_index].name
        except Exception:
            pass
        self._history_guard = True
        self.redo_stack.append(copy.deepcopy(self.library))
        self.library = self.undo_stack.pop()
        self._restore_active_symbol_and_unit_after_history(prev_symbol_index, prev_unit_index, prev_unit_name)
        self._history_guard = False
        self.rebuild_all()

    def redo(self):
        self.set_tool(DrawTool.SELECT.value)
        if not self.redo_stack:
            self.statusBar().showMessage('Redo-Historie ist leer.', 2000)
            return
        prev_symbol_index = self.library.current_symbol_index
        prev_unit_index = self.current_unit_index
        prev_unit_name = None
        try:
            prev_unit_name = self.library.symbols[prev_symbol_index].units[prev_unit_index].name
        except Exception:
            pass
        self._history_guard = True
        self.undo_stack.append(copy.deepcopy(self.library))
        self.library = self.redo_stack.pop()
        self._restore_active_symbol_and_unit_after_history(prev_symbol_index, prev_unit_index, prev_unit_name)
        self._history_guard = False
        self.rebuild_all()

    def confirm_discard_if_dirty(self) -> bool:
        if not self.dirty:
            return True
        res = QMessageBox.question(
            self,
            'Discard changes?',
            'The current symbol has changes. Do you really want to choose a new template and discard these changes?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res != QMessageBox.Yes:
            return False
        if self._clean_symbol_snapshot is not None and self._dirty_symbol_index is not None and 0 <= self._dirty_symbol_index < len(self.library.symbols):
            self.library.symbols[self._dirty_symbol_index] = copy.deepcopy(self._clean_symbol_snapshot)
        self.dirty = False
        self._dirty_symbol_index = None
        self._clean_symbol_snapshot = None
        self.undo_stack.clear(); self.redo_stack.clear()
        return True

    def select_all_canvas(self):
        self.set_tool(DrawTool.SELECT.value)
        for item in self.scene.items():
            kind = item.data(0)
            filter_kind = 'TEXT' if kind in ('ATTR_REF_DES', 'ATTR_BODY') else kind
            if filter_kind in ('BODY', 'PIN', 'TEXT', 'GRAPHIC') and self.selection_enabled.get(filter_kind, True):
                item.setSelected(True)
        self.refresh_properties()

    def reset_origin_to_body_center(self):
        self.reset_origin_to_selected_anchor(OriginMode.CENTER.value)

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
        """BODY origin anchor in grid coordinates, respecting BODY rotation.

        Imported/template bodies may already have a rotation.  Non-center
        anchors must be taken from the rotated visual BODY, otherwise every
        reset/transform uses the wrong corner and pins/attributes drift.
        """
        try:
            raw_x, raw_y = self.body_anchor_point(body, mode)
            rot = float(getattr(body, 'rotation', 0.0) or 0.0)
            if mode == OriginMode.CENTER.value or abs(rot) < 1e-9:
                return (raw_x, raw_y)
            cx, cy = self._body_center_grid(body)
            return self._rot_point(raw_x, raw_y, cx, cy, rot)
        except Exception:
            return self.body_anchor_point(body, mode)

    def shift_unit_geometry(self, unit: SymbolUnitModel, dx: float, dy: float):
        unit.body.x += dx
        unit.body.y += dy
        for p in unit.pins:
            p.x += dx; p.y += dy
            for ax_name, ay_name in (('label_x', 'label_y'), ('number_x', 'number_y')):
                if getattr(p, ax_name, None) is not None:
                    setattr(p, ax_name, getattr(p, ax_name) + dx)
                if getattr(p, ay_name, None) is not None:
                    setattr(p, ay_name, getattr(p, ay_name) + dy)
        for t in unit.texts:
            t.x += dx; t.y += dy
        for t in getattr(unit.body, 'attribute_texts', {}).values():
            t.x += dx; t.y += dy
        for g in unit.graphics:
            g.x += dx; g.y += dy

    def normalize_unit_origin(self, unit: SymbolUnitModel, mode: str):
        # Put the selected origin anchor of exactly this unit at grid (0, 0).
        # The red format guide is drawn relative to that origin, depending on the
        # selected origin mode.  This keeps split-parts independent and prevents
        # global origin-reset side effects.
        ax, ay = self.body_anchor_point_oriented(unit.body, mode)
        if abs(ax) > 1e-9 or abs(ay) > 1e-9:
            self.shift_unit_geometry(unit, -ax, -ay)
        self.dock_pins_to_body(unit)

    def normalize_symbol_origins_for_import(self, symbol: SymbolModel):
        mode = getattr(symbol, 'origin', OriginMode.CENTER.value) or OriginMode.CENTER.value
        if mode not in [x.value for x in OriginMode]:
            mode = OriginMode.CENTER.value
            symbol.origin = mode
        for unit in symbol.units:
            self.normalize_unit_origin(unit, mode)

    def origin_mode_changed(self, mode: str):
        # Changing the anchor selection immediately re-aligns the current canvas.
        self.reset_origin_to_selected_anchor(mode)

    def reset_origin_to_selected_anchor(self, mode: str | None = None):
        mode = mode or (self.origin_combo.currentText() if hasattr(self, 'origin_combo') else OriginMode.CENTER.value)
        old_mode = getattr(self.symbol, 'origin', OriginMode.CENTER.value)
        ax, ay = self.body_anchor_point_oriented(self.current_unit.body, mode)
        # Even if the mode is unchanged, the same command is useful after the body was moved accidentally:
        # it pulls the chosen body anchor back to the canvas origin.
        if abs(ax) < 1e-9 and abs(ay) < 1e-9 and old_mode == mode:
            return
        self.push_undo_state()
        self.symbol.origin = mode
        # Symbol Editor: Origin Reset is intentionally global for split symbols.
        # Each split part is reset independently to the same selected anchor, so
        # body-attached pins/text/graphics/body attributes keep their local layout
        # while every unit receives a consistent zero point.
        units = list(getattr(self.symbol, 'units', []) or [self.current_unit])
        if getattr(self.symbol, 'kind', None) != SymbolKind.SPLIT.value:
            units = [self.current_unit]
        for unit in units:
            uax, uay = self.body_anchor_point_oriented(unit.body, mode)
            if abs(uax) > 1e-9 or abs(uay) > 1e-9:
                self.shift_unit_geometry(unit, -uax, -uay)
            self.dock_pins_to_body(unit)
        if hasattr(self, 'origin_combo'):
            self.origin_combo.blockSignals(True)
            self.origin_combo.setCurrentText(mode)
            self.origin_combo.blockSignals(False)
        self.set_format_guide_to_active_origin()
        self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()
        self.statusBar().showMessage(f'Origin auf {mode} global nachgezogen.', 3000)

    def unit_tab_context_menu(self, pos):
        # Context menu for split-part tabs in the Units / Split Parts row.
        if self.symbol.kind != SymbolKind.SPLIT.value:
            return
        tab = self.unit_tabs.tabBar().tabAt(pos)
        if tab < 0 or tab >= len(self.symbol.units):
            return
        menu = QMenu(self.unit_tabs)
        menu.addAction('Rename Split Part', lambda t=tab: self.rename_split_part_from_tab(t))
        menu.addAction('Delete Split Part', lambda t=tab: self.delete_split_part_from_tab(t))
        menu.exec(self.unit_tabs.mapToGlobal(pos))

    def rename_split_part_from_tab(self, tab_index: int):
        if self.symbol.kind != SymbolKind.SPLIT.value:
            return
        if tab_index < 0 or tab_index >= len(self.symbol.units):
            return
        old = self.symbol.units[tab_index].name
        name, ok = QInputDialog.getText(self, 'Rename Split Part', 'New split-part name:', text=old)
        name = name.strip() if ok else ''
        if not name or name == old:
            return
        existing = {u.name for i, u in enumerate(self.symbol.units) if i != tab_index}
        if name in existing:
            QMessageBox.warning(self, 'Rename Split Part', f'A split part named "{name}" already exists.')
            return
        self.push_undo_state()
        self.symbol.units[tab_index].name = name
        self.current_unit_index = tab_index
        self.rebuild_unit_tabs(); self.rebuild_canvas_tabs(); self.rebuild_tree(); self.rebuild_pin_table(); self.update_name_editors()

    def delete_split_part_from_tab(self, tab_index: int):
        if self.symbol.kind != SymbolKind.SPLIT.value:
            return
        if tab_index < 0 or tab_index >= len(self.symbol.units):
            return
        if len(self.symbol.units) <= 1:
            QMessageBox.warning(self, 'Delete Split Part', 'The last split part cannot be deleted.')
            return
        name = self.symbol.units[tab_index].name
        if QMessageBox.question(self, 'Delete Split Part', f'Delete split part \"{name}\"?\n\nAll changes in this split part will be lost.', QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.push_undo_state()
        del self.symbol.units[tab_index]
        self.current_unit_index = max(0, min(tab_index, len(self.symbol.units) - 1))
        self.rebuild_canvas_tabs(); self.rebuild_unit_tabs(); self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table(); self.update_name_editors()

    def symbol_tab_context_menu(self, kind: str, tabs: QTabWidget, pos):
        tab = tabs.tabBar().tabAt(pos)
        if tab < 0:
            return
        menu = QMenu(tabs)
        menu.addAction('Rename Symbol', lambda: self.rename_symbol_from_tab(kind, tab))
        menu.addAction('Delete Symbol', lambda: self.delete_symbol_from_tab(kind, tab))
        menu.exec(tabs.mapToGlobal(pos))

    def delete_current_symbol(self):
        """Delete the currently active top-level symbol, independent of single/split kind."""
        if not self.library.symbols:
            QMessageBox.information(self, 'Delete Symbol', 'There is no symbol to delete.')
            return
        self.delete_symbol_by_index(self.library.current_symbol_index)

    def delete_all_symbols(self):
        """Delete all single symbols and split symbols in the current library/project."""
        count = len(self.library.symbols)
        if count <= 0:
            QMessageBox.information(self, 'Delete All Symbols', 'There are no symbols to delete.')
            return
        split_count = sum(1 for s in self.library.symbols if s.kind == SymbolKind.SPLIT.value)
        single_count = count - split_count
        msg = (
            f'Delete ALL symbols in the current project?\n\n'
            f'This removes {single_count} single symbol(s) and {split_count} split symbol(s), including all split parts, pins, bodies, graphics and attributes.\n\n'
            f'All unsaved changes will be lost.'
        )
        if QMessageBox.question(self, 'Delete All Symbols', msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.push_undo_state()
        self.library.symbols.clear()
        self.library.current_symbol_index = 0
        self.current_unit_index = 0
        self.rebuild_all()

    def delete_symbol_by_index(self, symbol_index: int):
        if symbol_index < 0 or symbol_index >= len(self.library.symbols):
            return
        symbol = self.library.symbols[symbol_index]
        kind_label = 'split symbol' if symbol.kind == SymbolKind.SPLIT.value else 'symbol'
        extra = ''
        if symbol.kind == SymbolKind.SPLIT.value:
            extra = f'\nThis also deletes all {len(symbol.units)} split part(s).'
        if QMessageBox.question(
            self,
            'Delete Symbol',
            f'Delete {kind_label} "{symbol.name}"?{extra}\n\nAll changes in this {kind_label} will be lost.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        self.push_undo_state()
        del self.library.symbols[symbol_index]
        if self.library.symbols:
            self.library.current_symbol_index = max(0, min(symbol_index, len(self.library.symbols) - 1))
        else:
            self.library.current_symbol_index = 0
        self.current_unit_index = 0
        self.rebuild_all()

    def delete_symbol_from_tab(self, kind: str, tab_index: int):
        indices = self._symbol_indices(kind)
        if tab_index < 0 or tab_index >= len(indices):
            return
        self.delete_symbol_by_index(indices[tab_index])

    def rename_symbol_from_tab(self, kind: str, tab_index: int):
        indices = self._symbol_indices(kind)
        if tab_index < 0 or tab_index >= len(indices):
            return
        si = indices[tab_index]
        old = self.library.symbols[si].name
        name, ok = QInputDialog.getText(self, 'Rename Symbol', 'Neuer Symbolname:', text=old)
        if ok and name.strip():
            self.library.current_symbol_index = si
            self.rename_current_symbol(name.strip())

    def edit_symbol_templates(self):
        dlg = TemplateEditorDialog(self)
        dlg.exec()
        self.symbol_templates.update(dlg.templates)
        self.invalidate_template_cache()
        self.rebuild_all()
        return

    def edit_symbol_templates_legacy(self):
        dlg = QDialog(self)
        dlg.setWindowTitle('Edit Symbol Templates')
        dlg.resize(780, 620)
        layout = QVBoxLayout(dlg)
        info = QLabel('Dieses Werkzeug speichert die aktuell visiblee Unit als Template und kann Body, Pins und visiblee Attribute auf das aktuelle Symbol anwenden. Bestehende manuelle Geometrie/Pins bleiben beim reinen Attribut-/Style-Update erhalten.')
        info.setWordWrap(True)
        layout.addWidget(info)
        top = QHBoxLayout()
        name = QComboBox(); name.setEditable(True)
        base_names = sorted(set(self.symbol_templates.keys()) | {self.symbol.name, 'IC', 'Connector', 'Discrete', 'Power'})
        name.addItems(base_names)
        name.setCurrentText(self.symbol.name)
        top.addWidget(QLabel('Template:')); top.addWidget(name, 1)
        layout.addLayout(top)
        tabs = QTabWidget(); layout.addWidget(tabs, 1)
        body_page = QWidget(); body_form = QFormLayout(body_page)
        bw = QDoubleSpinBox(); bw.setRange(0, 500); bw.setDecimals(2); bw.setValue(self.current_unit.body.width)
        bh = QDoubleSpinBox(); bh.setRange(0, 500); bh.setDecimals(2); bh.setValue(self.current_unit.body.height)
        bx = QDoubleSpinBox(); bx.setRange(-500, 500); bx.setDecimals(2); bx.setValue(self.current_unit.body.x)
        by = QDoubleSpinBox(); by.setRange(-500, 500); by.setDecimals(2); by.setValue(self.current_unit.body.y)
        body_form.addRow('Body X', bx); body_form.addRow('Body Y', by); body_form.addRow('Body Width (0 = delete body)', bw); body_form.addRow('Body Height (0 = delete body)', bh)
        tabs.addTab(body_page, 'Body')
        pin_page = QWidget(); pin_layout = QVBoxLayout(pin_page)
        pin_table = QTableWidget(0, 6); pin_table.setHorizontalHeaderLabels(['Number', 'Name', 'Function', 'Type', 'Side', 'Inverted'])
        pin_table.setItemDelegateForColumn(3, PinComboDelegate([x.value for x in PinType], pin_table))
        pin_table.setItemDelegateForColumn(4, PinComboDelegate([x.value for x in PinSide], pin_table))
        pin_table.setItemDelegateForColumn(5, PinComboDelegate(['yes', 'no'], pin_table))
        pin_layout.addWidget(pin_table)
        pin_buttons = QHBoxLayout(); add_btn = QPushButton('Pin +'); del_btn = QPushButton('Pin -')
        pin_buttons.addWidget(add_btn); pin_buttons.addWidget(del_btn); pin_buttons.addStretch(); pin_layout.addLayout(pin_buttons)
        tabs.addTab(pin_page, 'Pins')
        def fill_template_pins(unit):
            pin_table.setRowCount(len(unit.pins))
            for r, p in enumerate(unit.pins):
                for c, v in enumerate([p.number, p.name, p.function, p.pin_type, p.side, 'yes' if p.inverted else 'no']):
                    pin_table.setItem(r, c, QTableWidgetItem(str(v)))
            pin_table.resizeColumnsToContents()
        fill_template_pins(self.current_unit)
        def add_template_pin():
            r = pin_table.rowCount(); pin_table.insertRow(r)
            vals = [str(r + 1), 'PIN', 'FUNC', PinType.BIDI.value, PinSide.LEFT.value, 'no']
            for c, v in enumerate(vals): pin_table.setItem(r, c, QTableWidgetItem(v))
        def del_template_pin():
            for r in sorted({i.row() for i in pin_table.selectedIndexes()}, reverse=True): pin_table.removeRow(r)
        add_btn.clicked.connect(add_template_pin); del_btn.clicked.connect(del_template_pin)
        attr_page = QWidget(); attr_layout = QVBoxLayout(attr_page)
        attr_table = QTableWidget(0, 3); attr_table.setHorizontalHeaderLabels(['Attribut', 'Wert', 'Sichtbar'])
        attr_layout.addWidget(attr_table)
        ar = 0
        for k, v in self.current_unit.body.attributes.items():
            attr_table.insertRow(ar)
            attr_table.setItem(ar, 0, QTableWidgetItem(k)); attr_table.setItem(ar, 1, QTableWidgetItem(v))
            attr_table.setItem(ar, 2, QTableWidgetItem('yes' if self.current_unit.body.visible_attributes.get(k, False) else 'no'))
            ar += 1
        attr_table.resizeColumnsToContents()
        tabs.addTab(attr_page, 'Displayed Attributes')
        opts = QGroupBox('Anwenden')
        opts_l = QHBoxLayout(opts)
        apply_body = QCheckBox('Apply body'); apply_body.setChecked(True)
        apply_pins = QCheckBox('Apply/replace pins'); apply_pins.setChecked(False)
        apply_attrs = QCheckBox('Apply attributes'); apply_attrs.setChecked(True)
        opts_l.addWidget(apply_body); opts_l.addWidget(apply_pins); opts_l.addWidget(apply_attrs)
        layout.addWidget(opts)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        def unit_from_dialog():
            u = copy.deepcopy(self.current_unit)
            u.body.x, u.body.y, u.body.width, u.body.height = bx.value(), by.value(), bw.value(), bh.value()
            pins = []
            for r in range(pin_table.rowCount()):
                pin = PinModel(
                    number=pin_table.item(r,0).text() if pin_table.item(r,0) else str(r+1),
                    name=pin_table.item(r,1).text() if pin_table.item(r,1) else 'PIN',
                    function=pin_table.item(r,2).text() if pin_table.item(r,2) else '',
                    pin_type=pin_table.item(r,3).text() if pin_table.item(r,3) else PinType.BIDI.value,
                    side=pin_table.item(r,4).text() if pin_table.item(r,4) else PinSide.LEFT.value,
                    inverted=(pin_table.item(r,5).text().lower() in ('yes','true','1','ja')) if pin_table.item(r,5) else False,
                )
                pin.y = u.body.y - 1 - r
                pins.append(pin)
            u.pins = pins
            attrs, vis = {}, {}
            for r in range(attr_table.rowCount()):
                k = attr_table.item(r,0).text() if attr_table.item(r,0) else ''
                if not k: continue
                attrs[k] = attr_table.item(r,1).text() if attr_table.item(r,1) else ''
                vis[k] = (attr_table.item(r,2).text().lower() in ('yes','true','1','ja')) if attr_table.item(r,2) else False
            u.body.attributes = attrs; u.body.visible_attributes = vis
            return u
        def apply_template(close=False):
            self.push_undo_state()
            tmpl = unit_from_dialog()
            self.symbol_templates[name.currentText()] = copy.deepcopy(tmpl)
            self.merge_save_template_to_file(name.currentText(), tmpl)
            cur = self.current_unit
            if apply_body.isChecked():
                old_body = cur.body
                cur.body = copy.deepcopy(tmpl.body)
                cur.body.attributes = old_body.attributes
                cur.body.visible_attributes = old_body.visible_attributes
                if tmpl.body.width <= 0 or tmpl.body.height <= 0:
                    cur.body.width = cur.body.height = 0.01
            if apply_attrs.isChecked():
                cur.body.attributes = copy.deepcopy(tmpl.body.attributes)
                cur.body.visible_attributes = copy.deepcopy(tmpl.body.visible_attributes)
            if apply_pins.isChecked():
                cur.pins = copy.deepcopy(tmpl.pins)
            self.dock_pins_to_body(cur)
            self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()
            if close: dlg.accept()
        buttons.button(QDialogButtonBox.Apply).clicked.connect(lambda: apply_template(False))
        buttons.accepted.connect(lambda: apply_template(True))
        buttons.rejected.connect(dlg.reject)
        dlg.exec()


    # ------------------------------------------------------------------ Template handling
    def project_root_path(self):
        """Return the real Symbol_Wizard project root independent of cwd/start script.

        Expected release layout:
            Symbol_Wizard/
              symbol_wizard/gui/main_window.py
              symbol_wizard/symbol_types/symbol_types.json
              symbol_wizard/symbol_templates/

        Older builds sometimes started the GUI from a different working directory,
        so relying on Path.cwd() made the Template Editor silently miss templates.
        This resolver walks upward from this file and selects the first directory
        that looks like the Symbol_Wizard root.
        """
        here = Path(__file__).resolve()
        for candidate in here.parents:
            # Current proven GUI path: Symbol_Wizard/symbol_types.json.
            # Keep this as the primary project root marker because the Template
            # Editor in the deployed app already resolves the catalog there.
            if (candidate / 'symbol_types.json').exists() and (candidate / 'symbol_wizard').is_dir():
                return candidate
            if (candidate / 'symbol_wizard' / 'symbol_types' / 'symbol_types.json').exists():
                return candidate
            if (candidate / 'symbol_wizard').is_dir() and (candidate / 'main.py').exists():
                return candidate
        return Path(__file__).resolve().parents[2]

    def symbol_types_path(self):
        """Central symbol type catalog path used by New Symbol and Template Editor.

        Primary deployed GUI path:
            Symbol_Wizard/symbol_types.json

        Package-local copies are accepted as fallbacks only.
        """
        root = self.project_root_path()
        candidates = [
            # This is the path confirmed by the running GUI.
            root / 'symbol_types.json',
            Path.cwd() / 'symbol_types.json',
            Path.cwd() / 'Symbol_Wizard' / 'symbol_types.json',
            # fallbacks for package-local/dev layouts
            root / 'symbol_wizard' / 'symbol_types' / 'symbol_types.json',
            Path.cwd() / 'symbol_wizard' / 'symbol_types' / 'symbol_types.json',
            Path.cwd() / 'Symbol_Wizard' / 'symbol_wizard' / 'symbol_types' / 'symbol_types.json',
            root / 'symbol_types' / 'symbol_types.json',
            root / 'symbol_wizard' / 'symbol_types.json',
            Path.cwd() / 'symbol_types' / 'symbol_types.json',
        ]
        for c in candidates:
            if c.exists():
                return c
        # Return the expected primary path so error messages point to the place
        # users can fix directly.
        return root / 'symbol_types.json'

    def invalidate_template_cache(self):
        """Drop cached template catalogues after saving/importing templates.

        Template access can scan thousands of generated Mentor templates.  The UI
        calls available_templates() from several places, therefore we cache the
        parsed catalogue and only invalidate it when template files change or an
        editor explicitly saves a template.
        """
        for attr in ('_external_template_cache_key', '_external_template_cache',
                     '_external_split_template_cache', '_available_template_cache'):
            try:
                if hasattr(self, attr):
                    delattr(self, attr)
            except Exception:
                pass

    def symbol_templates_dir(self):
        """Directory for future split-out template JSON files.

        Stage 1 still loads resistor templates from symbol_types.json, but keeping
        this path central prevents the GUI from looking in a stale folder.
        """
        return self.project_root_path() / 'symbol_wizard' / 'symbol_templates'


    def _template_manifest_path(self):
        return self.symbol_templates_dir() / '.template_manifest.json'

    def _normalize_template_manifest(self, data: dict) -> dict:
        """Repair and canonicalize the metadata-only template manifest."""
        try:
            templates_in = data.get('templates') or {}
            if not isinstance(templates_in, dict):
                return data

            def leaf_name(value: str) -> str:
                leaf = str(value or '').replace('\\', '/').split('/')[-1].strip()
                return leaf or str(value or '').strip()

            templates = {}
            for key, meta in templates_in.items():
                meta = dict(meta or {})
                part = str(meta.get('partition') or '').strip()
                if not part:
                    parts = [x.strip() for x in str(key).replace('\\','/').split('/') if x.strip()]
                    part = parts[0] if len(parts) >= 2 else ''
                name = leaf_name(meta.get('name') or key)
                if part and name.upper() == part.upper():
                    name = leaf_name(key)
                canonical = f'{part} / {name}' if part and part != name else name
                meta['name'] = name
                meta['partition'] = part
                templates[canonical] = meta
            data['templates'] = templates

            def is_large_ic_partition(name: str) -> bool:
                n = str(name or '').upper().replace('-', '_')
                exclude = ('RELAIS','RELAY','DIODE','FET','TRANS','THYR','TRIAC','IGBT','OPTO','IND_','FILTER','DROSSEL','UEBTR','WIDERSTAND','KONDENSATOR','CAP','STECKER','CONNECTOR','ZUBEHOER','GND','BORDER','INFO','TESTPUNKT')
                if any(t in n for t in exclude):
                    return False
                tokens = ('CONTROLLER','PROZESSOR','PROCESSOR','CPU','SOC','FPGA','CPLD','DSP','ASIC','MCU','MPU','PMIC','BGA','LOGIK','LOGIC','MULTIFUNKTIONS','MUTLIFUNKTIONS','MULTIFUNCTION','VERSTAERKER_IC','AMPLIFIER_IC')
                return any(t in n for t in tokens)

            def base_from_name(name: str):
                leaf = leaf_name(name)
                leaf = re.sub(r'\.(sym|json)$', '', leaf, flags=re.IGNORECASE)
                leaf = re.sub(r'\.\d{1,3}$', '', leaf)
                chunks = re.split(r'[_-]+', leaf)
                if len(chunks) >= 2 and len(chunks[0]) >= 5 and re.search(r'\d', chunks[0]):
                    return chunks[0]
                m = re.match(r'^(?P<base>.+?)[_-](?:\d{1,3}[a-z]?|[A-Z]|PWR|POWER|SUPPLY|GND[A-Z]?|VDD|VSS|VCC|PS_POWER|VCCINT_VCU|GPIO|BANK\d*|ADC|DAC|USB|PCIE|ETH|DDR|IO|CORE|CTRL|CONTROL)$', leaf, flags=re.IGNORECASE)
                if m and len(m.group('base')) >= 3:
                    return m.group('base')
                return None

            groups = {}
            for key, meta in templates.items():
                part = str((meta or {}).get('partition') or '')
                name = str((meta or {}).get('name') or key.split(' / ')[-1])
                if not is_large_ic_partition(part):
                    continue
                base = base_from_name(name)
                if not base:
                    continue
                gk = f'Split Symbols / {part} / {base}'
                groups.setdefault(gk, []).append(key)

            def sort_key(k):
                nm = leaf_name(k)
                nm0 = re.sub(r'\.\d{1,3}$', '', nm)
                tail = re.split(r'[_-]+', nm0)[-1].lower()
                m = re.search(r'[._-](\d{1,3})([a-zA-Z]?)(?:\.\d+)?$', nm)
                if m:
                    suffix = (m.group(2) or '').lower()
                    suffix_ord = (ord(suffix) - 96) if suffix else 0
                    return (0, int(m.group(1)), suffix_ord, nm.lower())
                order = ['control','ctrl','core','bank','gpio','io','ddr','mem','usb','pcie','sata','eth','rgmii','phy','adc','dac','ps','power','pwr','supply','gnd','vss','vdd','vccint','vcu']
                for i, token in enumerate(order, start=1):
                    if token in tail or token in nm.lower():
                        return (1, i, nm.lower())
                return (2, 9999, nm.lower())

            split_templates = {}
            for gk, keys in groups.items():
                unique = sorted(set(keys), key=sort_key)
                if len(unique) >= 2:
                    split_templates[gk] = unique
            data['split_templates'] = split_templates
        except Exception:
            pass
        return data

    def load_template_manifest(self) -> dict:
        """Fast metadata-only template index.

        This avoids unpickling/parsing thousands of SymbolUnitModel objects when
        merely opening the New Symbol dialog or the Template Editor.  The manifest
        contains only keys and file positions; concrete template units are loaded
        lazily only for the selected template.
        """
        root = self.symbol_templates_dir()
        mf = self._template_manifest_path()
        try:
            files_sig = tuple(sorted((str(fp.relative_to(root)), fp.stat().st_mtime_ns, fp.stat().st_size)
                                     for fp in root.rglob('*.json') if not fp.name.startswith('.')))
        except Exception:
            files_sig = tuple()
        cache_key = ('manifest-v1', files_sig)
        if getattr(self, '_template_manifest_cache_key', None) == cache_key:
            return getattr(self, '_template_manifest_cache', {}) or {'templates': {}, 'split_templates': {}}
        try:
            if mf.exists():
                data = json.loads(mf.read_text(encoding='utf-8'))
                if isinstance(data, dict) and 'templates' in data:
                    data = self._normalize_template_manifest(data)
                    try:
                        mf.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
                    except Exception:
                        pass
                    self._template_manifest_cache_key = cache_key
                    self._template_manifest_cache = data
                    return data
        except Exception:
            pass
        # Fallback: build a small manifest from file names only.  A full release
        # ships .template_manifest.json, so this path should only be used in dev.
        data = {'version': 1, 'templates': {}, 'split_templates': {}}
        try:
            for fp in sorted(root.rglob('*.json')):
                if fp.name.startswith('.'):
                    continue
                try:
                    payload = json.loads(fp.read_text(encoding='utf-8'))
                except Exception:
                    continue
                entries = payload if isinstance(payload, list) else [payload]
                rel = fp.relative_to(root).with_suffix('')
                parts = list(rel.parts)
                part = parts[1] if parts and parts[0] == 'mentor_known' and len(parts) >= 2 else (parts[-2] if len(parts) >= 2 else rel.name)
                for i, entry in enumerate(entries):
                    if not isinstance(entry, dict):
                        continue
                    entry_name = str(entry.get('template_name') or entry.get('name') or rel.name).strip() or rel.name
                    key = f'{part} / {entry_name}' if part and part != entry_name else entry_name
                    data['templates'][key] = {'file': str(fp.relative_to(root)).replace('\\\\','/'), 'index': i, 'name': entry_name, 'partition': part}
            data = self._normalize_template_manifest(data)
            try:
                mf.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
            except Exception:
                pass
        except Exception:
            pass
        self._template_manifest_cache_key = cache_key
        self._template_manifest_cache = data
        return data

    def available_template_keys(self, split_only: bool = False) -> list[str]:
        keys = []
        # symbol_types.json keys are usually small; use the already parsed cache if present.
        try:
            data = json.loads(self.symbol_types_path().read_text(encoding='utf-8'))
            for type_name, type_def in (data.get('types') or {}).items():
                subs = type_def.get('subtypes') or {}
                if subs:
                    for subtype_name in subs.keys():
                        keys.append(f'{type_name} / {subtype_name}')
                else:
                    keys.append(str(type_name))
        except Exception:
            pass
        manifest = self.load_template_manifest()
        mkeys = list((manifest.get('templates') or {}).keys())
        if split_only:
            split_keys = list((manifest.get('split_templates') or {}).keys())
            keys.extend(split_keys)
            keys.extend([k for k in mkeys if k.startswith('IC /') or k.startswith('Digital IC /')])
            # Generic/passive single-symbol templates do not belong in the
            # split-symbol creation dialog.  A deliberate empty start is offered
            # by the special <NONE> template instead.
            keys = [k for k in keys if not str(k).startswith('Passive') and ' / Passive' not in str(k)]
            keys.append('<NONE>')
        else:
            keys.extend(mkeys)
        if not keys:
            keys.extend(self.builtin_resistor_templates().keys())
        return sorted(set(keys), key=str.lower)

    def _unit_from_payload_fast(self, payload: dict) -> SymbolUnitModel | None:
        try:
            src = payload.get('unit', payload) if isinstance(payload, dict) else payload
            body_src = src.get('body', {}) if isinstance(src, dict) else {}
            bd = {k: v for k, v in dict(body_src).items() if k in SymbolBodyModel.__dataclass_fields__}
            bd['attribute_font'] = _coerce_font_model(bd.get('attribute_font'), .75)
            bd['refdes_font'] = _coerce_font_model(bd.get('refdes_font'), .9)
            if isinstance(bd.get('attribute_texts'), dict):
                bd['attribute_texts'] = {str(k): _text_model_from_any(v, str(k), 0.0, 0.0, bd['attribute_font']) for k, v in bd.get('attribute_texts', {}).items()}
            body = SymbolBodyModel(**bd)
            pins = []
            for pd in (src.get('pins', []) or src.get('default_pins', []) or []):
                pd = dict(pd)
                pd['number_font'] = _coerce_font_model(pd.get('number_font'), .45)
                pd['label_font'] = _coerce_font_model(pd.get('label_font'), .55)
                if isinstance(pd.get('attribute_texts'), dict):
                    pd['attribute_texts'] = {str(k): _text_model_from_any(v, str(k), 0.0, 0.0, pd['label_font']) for k, v in pd.get('attribute_texts', {}).items()}
                pins.append(PinModel(**{k:v for k,v in pd.items() if k in PinModel.__dataclass_fields__}))
            texts = [TextModel(**dict(t)) for t in (src.get('texts', []) or []) if isinstance(t, dict)]
            graphics = []
            for gd in (src.get('graphics', []) or []):
                if not isinstance(gd, dict):
                    continue
                gd = dict(gd); style = gd.pop('style', None)
                g = GraphicModel(**{k:v for k,v in gd.items() if k in GraphicModel.__dataclass_fields__})
                if isinstance(style, dict):
                    g.style = StyleModel(**style)
                graphics.append(g)
            # Templates imported from Mentor/Xpedition store their visible body as
            # graphic primitives.  Normalize old generated template JSON here:
            # those primitives are Body-owned in the Symbol Wizard, but still
            # individually editable in the Template Editor.
            try:
                attrs = getattr(body, 'attributes', {}) or {}
                if (str(attrs.get('MENTOR_GRAPHICS_AS_BODY', '0')) == '1'
                        or str(attrs.get('MENTOR_BODY_GRAPHICS_LOCKED', '0')) == '1'
                        or str(attrs.get('MENTOR_HAS_BODY', '0')) == '1'
                        or str(attrs.get('TEMPLATE_GRAPHICS_AS_BODY', '0')) == '1'):
                    for _g in graphics:
                        _g.locked_to_body = True
            except Exception:
                pass
            unit = SymbolUnitModel(name=str(src.get('name', payload.get('name', 'Template'))), body=body, pins=pins, texts=texts, graphics=graphics)
            self._lock_template_body_graphics(unit)
            return unit
        except Exception:
            return None

    def _blank_template_unit(self, name: str = '<NONE>') -> SymbolUnitModel:
        """Minimal internal body used when the user explicitly selects no template."""
        body = SymbolBodyModel(width=10.0, height=8.0)
        try:
            body.attributes = {'RefDes': '?', 'Part Name': name if name != '<NONE>' else '', 'VALUE': 'VALUE', 'Package': 'BAUFORM', 'CLASS': ''}
            body.visible_attributes = {'RefDes': True, 'Part Name': True, 'VALUE': True, 'Package': True, 'CLASS': True}
        except Exception:
            pass
        return SymbolUnitModel(name=name if name and name != '<NONE>' else 'Unit A', body=body, pins=[], texts=[], graphics=[])

    def load_template_unit(self, key: str) -> SymbolUnitModel:
        """Load one concrete template by key, lazily and with a small LRU cache."""
        key = str(key or '').strip()
        if key in ('<NONE>', 'None', 'NONE', ''):
            return self._blank_template_unit('<NONE>')
        lru = getattr(self, '_template_unit_lru', None)
        if lru is None:
            lru = {}
            self._template_unit_lru = lru
        if key in lru:
            return copy.deepcopy(lru[key])
        # First try external manifest, then symbol_types, then already-added runtime templates.
        manifest = self.load_template_manifest()
        meta = (manifest.get('templates') or {}).get(key)
        if meta:
            root = self.symbol_templates_dir()
            fp = root / meta.get('file', '')
            try:
                part_cache = getattr(self, '_template_file_json_cache', None)
                if part_cache is None:
                    part_cache = {}
                    self._template_file_json_cache = part_cache
                rel = str(meta.get('file',''))
                data = part_cache.get(rel)
                if data is None:
                    data = json.loads(fp.read_text(encoding='utf-8'))
                    # Keep only a few partition files in memory.
                    if len(part_cache) > 3:
                        part_cache.clear()
                    part_cache[rel] = data
                entries = data if isinstance(data, list) else [data]
                idx = int(meta.get('index', 0) or 0)
                if 0 <= idx < len(entries):
                    unit = self._unit_from_payload_fast(entries[idx])
                    if unit is not None:
                        unit.name = str(meta.get('name') or key.split(' / ')[-1])
                        self._lock_template_body_graphics(unit)
                        if len(lru) > 64:
                            lru.clear()
                        lru[key] = copy.deepcopy(unit)
                        return unit
            except Exception:
                pass
        try:
            if key in self.symbol_templates:
                return copy.deepcopy(self.symbol_templates[key])
        except Exception:
            pass
        try:
            all_small = self.load_symbol_type_templates()
            if key in all_small:
                return copy.deepcopy(all_small[key])
        except Exception:
            pass
        return SymbolUnitModel(name=key or 'Template')

    def load_split_template_units(self, key: str) -> list[SymbolUnitModel]:
        key = str(key or '').strip()
        if key in ('<NONE>', 'None', 'NONE', ''):
            return [self._blank_template_unit('<NONE>')]
        manifest = self.load_template_manifest()
        keys = (manifest.get('split_templates') or {}).get(key) or []
        if keys:
            units = []
            for k in keys:
                u = self.load_template_unit(k)
                if u is not None and (getattr(u, 'pins', None) or getattr(u, 'graphics', None) or getattr(u, 'texts', None)):
                    units.append(self._lock_template_body_graphics(u))
            return units
        split_units = (getattr(self, '_external_split_templates', {}) or {}).get(key)
        if split_units:
            return [copy.deepcopy(u) for u in split_units]
        return []

    def load_external_template_files(self) -> dict[str, SymbolUnitModel]:
        """Load optional templates from Symbol_Wizard/symbol_templates/**/*.json.

        This is intentionally additive.  The lean resistor stage works without
        external files, but if a template JSON is placed there later the Template
        Editor will immediately see it. Supported shapes:
          - a single SymbolUnitModel-like dict with body/pins/graphics/texts
          - a dict with {name, unit}
          - a list of the above
        """
        result: dict[str, SymbolUnitModel] = {}
        split_groups: dict[str, list[SymbolUnitModel]] = {}
        root = self.symbol_templates_dir()
        if not root.exists():
            self._external_split_templates = {}
            return result

        try:
            files = tuple(sorted((str(fp.relative_to(root)), fp.stat().st_mtime_ns, fp.stat().st_size) for fp in root.rglob('*.json')))
        except Exception:
            files = tuple()
        # Path independent cache key: a release ZIP can contain a ready-made
        # index and still validate after extraction into another directory.
        cache_key = ('template-index-v5-pin-count-split-base', files)
        if getattr(self, '_external_template_cache_key', None) == cache_key:
            self._external_split_templates = getattr(self, '_external_split_template_cache', {}) or {}
            return getattr(self, '_external_template_cache', {}) or {}

        # Persistent on-disk template index.  The Mentor-derived template catalog
        # contains thousands of entries; reparsing every JSON file when opening
        # the Template Editor or New Split Symbol dialog makes the UI feel slow.
        # The cache key contains relative path + mtime + size, so it is rebuilt
        # automatically after template generation/import/save.
        index_file = root / '.template_index_cache.pickle'
        try:
            if index_file.exists():
                with index_file.open('rb') as fh:
                    cached = pickle.load(fh)
                if cached.get('cache_key') == cache_key:
                    self._external_split_templates = cached.get('split_templates', {}) or {}
                    self._external_template_cache_key = cache_key
                    self._external_template_cache = cached.get('templates', {}) or {}
                    self._external_split_template_cache = cached.get('split_templates', {}) or {}
                    return self._external_template_cache
        except Exception:
            # Corrupt or incompatible cache: ignore and rebuild below.
            pass

        def is_large_ic_partition(name: str) -> bool:
            """Return True for partitions where logical multi-part ICs are expected.

            Split detection is intentionally limited to IC/controller/logic style
            partitions to avoid treating relay contacts, diodes, passives or
            connectors as split symbols.
            """
            n = str(name or '').upper().replace('-', '_')
            exclude = (
                'RELAIS', 'RELAY', 'DIODE', 'FET', 'TRANS', 'THYR', 'TRIAC',
                'IGBT', 'OPTO', 'IND_', 'FILTER', 'DROSSEL', 'UEBTR',
                'WIDERSTAND', 'KONDENSATOR', 'CAP', 'STECKER', 'CONNECTOR',
                'ZUBEHOER', 'GND', 'BORDER', 'INFO', 'TESTPUNKT',
            )
            if any(t in n for t in exclude):
                return False
            tokens = (
                'CONTROLLER', 'PROZESSOR', 'PROCESSOR', 'CPU', 'SOC', 'FPGA',
                'CPLD', 'DSP', 'ASIC', 'MCU', 'MPU', 'PMIC', 'BGA',
                'LOGIK', 'LOGIC', 'MULTIFUNKTIONS', 'MUTLIFUNKTIONS', 'MULTIFUNCTION',
                'VERSTAERKER_IC', 'AMPLIFIER_IC',
            )
            return any(t in n for t in tokens)

        def template_partition_from_path(fp: Path) -> str:
            """Derive the user-facing partition name for generated Mentor templates.

            Generated files are stored as symbol_templates/mentor_known/<PARTITION>.json.
            The Template Editor should show <PARTITION> as level 1 and the actual
            symbol/template name as level 2.
            """
            try:
                rel = fp.relative_to(root).with_suffix('')
                parts = list(rel.parts)
                if parts and parts[0] == 'mentor_known' and len(parts) >= 2:
                    return parts[-1]
                if len(parts) >= 2:
                    return parts[-2]
                return rel.name
            except Exception:
                return fp.stem

        def split_base_from_name(name: str):
            """Infer a logical split-symbol base from a Mentor symbol name.

            Mentor libraries often do not use only .1/.2 for split parts.  Large
            devices are commonly split as e.g. IMX6Q_CONTROL, IMX6Q_DDRx32,
            IMX6Q_POWER, A3P1000_144_BANK0, 88Q5030_01/02/POWER, etc.  This
            normalizer groups those entries by the stable device prefix while
            still ignoring ordinary single symbols.
            """
            raw = str(name or '').strip()
            leaf = raw.split('/')[-1].strip()
            leaf = re.sub(r'\.(sym|json)$', '', leaf, flags=re.IGNORECASE)
            leaf = re.sub(r'\.\d{1,3}$', '', leaf)  # Mentor view suffix
            s = leaf.strip()
            if len(s) < 4:
                return None, None

            # Remove only file/view suffix for display but keep enough
            # semantic name for grouping.  Many Mentor files are part-like
            # names ending in .1 but split views are encoded with _01/_02,
            # _PWR/_ADC, -1/-2 or RX/TX style suffixes.

            # Explicit multipart suffixes / functional pages.
            suffix_words = (
                'CONTROL', 'CTRL', 'PWR', 'POWER', 'SUPPLY', 'SUP', 'VDD', 'VSS', 'VCC', 'GND',
                'GPIO', 'IO', 'PORT', r'BANK\d*', 'JTAG', 'TEST', 'CFG', 'CONFIG', 'CONF',
                'CORE', 'ANA', 'ANALOG', 'DIG', 'DIGITAL', 'ADC', 'DAC', 'A2D', 'D2A',
                'DDR', r'DDRX\d+', 'MEM', 'RAM', 'FLASH', 'SDRAM',
                'USB', 'PCIE', 'PCIe', 'SATA', 'SDHC', 'EIM', 'RGMII', 'ETH', 'ENET', 'PHY',
                'MIPI', 'CSI', 'DSI', 'DISP', 'HDMI', 'LVDS', 'SERDES',
                'SPI', 'I2C', 'CAN', 'LIN', 'UART', 'RX', 'TX', 'RXD', 'TXD',
                'PLL', 'CLK', 'CLOCK', 'OSC', 'MISC', 'NC'
            )
            suffix_re = r'(?:' + '|'.join(suffix_words) + r')(?:[_-]?(?:\d+|[A-Z]))?'
            m = re.match(rf'^(?P<base>.+?)[_-](?P<part>{suffix_re})$', s, flags=re.IGNORECASE)
            if m and len(m.group('base')) >= 3:
                return m.group('base'), m.group('part')

            # Numeric/letter pages often used in IC partitions: foo_01, foo-2, foo_A.
            m = re.match(r'^(?P<base>.+?)[_-](?P<part>\d{1,3}|[A-Z])$', s, flags=re.IGNORECASE)
            if m and len(m.group('base')) >= 3:
                return m.group('base'), m.group('part')

            # Fallback for names like TM4-1.
            m = re.match(r'^(?P<base>[A-Za-z][A-Za-z0-9]{2,})-(?P<part>\d{1,3})$', s)
            if m:
                return m.group('base'), m.group('part')

            # Broader library heuristic for IC partitions: if the name has at
            # least two '_' separated chunks, group by a stable leading prefix.
            # This catches pairs such as arinc429_rxd/arinc429_txd,
            # 14stage_bincount_01/_02 and lpa0110_adc/_pwr while staying
            # restricted to the large-IC partitions by the caller.
            chunks = re.split(r'[_-]+', s)
            # Large FPGA/SoC symbols are often split into many bank/power pages as
            # <device>_<page>.1.  The page token may itself contain underscores
            # (e.g. PS_POWER or VCCINT_VCU), so grouping by all chunks except the
            # last loses pages.  When the first chunk looks like a concrete device
            # code/package, use it as stable split base.  This fixes devices such
            # as XCZU3EGSFVC784B where 20 library pages must become one template.
            if len(chunks) >= 2 and len(chunks[0]) >= 5 and re.search(r'\d', chunks[0]):
                tail = '_'.join(chunks[1:])
                if re.match(r'^[A-Za-z0-9_+-]{1,32}$', tail):
                    return chunks[0], tail
            if len(chunks) >= 2 and len(chunks[0]) >= 3:
                last = chunks[-1]
                if re.match(r'^(?:\d{1,3}|[A-Z]|[A-Z]{2,6}\d*)$', last, re.IGNORECASE):
                    return '_'.join(chunks[:-1]), last
                if len(chunks) >= 3:
                    return '_'.join(chunks[:-1]), last
            return None, None

        def unit_from_payload(payload: dict) -> SymbolUnitModel | None:
            try:
                src = payload.get('unit', payload) if isinstance(payload, dict) else payload
                body_src = src.get('body', {}) if isinstance(src, dict) else {}
                bd = {k: v for k, v in dict(body_src).items() if k in SymbolBodyModel.__dataclass_fields__}
                bd['attribute_font'] = _coerce_font_model(bd.get('attribute_font'), .75)
                bd['refdes_font'] = _coerce_font_model(bd.get('refdes_font'), .9)
                if isinstance(bd.get('attribute_texts'), dict):
                    bd['attribute_texts'] = {
                        str(k): _text_model_from_any(v, str(k), 0.0, 0.0, bd['attribute_font'])
                        for k, v in bd.get('attribute_texts', {}).items()
                    }
                body = SymbolBodyModel(**bd)

                pins = []
                for pd in (src.get('pins', []) or []):
                    pd = dict(pd)
                    pd['number_font'] = _coerce_font_model(pd.get('number_font'), .45)
                    pd['label_font'] = _coerce_font_model(pd.get('label_font'), .55)
                    if isinstance(pd.get('attribute_texts'), dict):
                        pd['attribute_texts'] = {
                            str(k): _text_model_from_any(v, str(k), 0.0, 0.0, pd['label_font'])
                            for k, v in pd.get('attribute_texts', {}).items()
                        }
                    pins.append(PinModel(**pd))

                texts = [TextModel(**dict(t)) for t in (src.get('texts', []) or [])]
                graphics = []
                for gd in (src.get('graphics', []) or []):
                    gd = dict(gd)
                    style = gd.pop('style', None)
                    g = GraphicModel(**gd)
                    if isinstance(style, dict):
                        g.style = StyleModel(**style)
                    graphics.append(g)
                # Templates imported from Mentor/Xpedition store their visible body as
                # graphic primitives. Normalize old generated template JSON here:
                # those primitives are Body-owned in the Symbol Wizard, but still
                # individually editable in the Template Editor.
                try:
                    attrs = getattr(body, 'attributes', {}) or {}
                    if str(attrs.get('MENTOR_GRAPHICS_AS_BODY', '0')) == '1' or str(attrs.get('MENTOR_BODY_GRAPHICS_LOCKED', '0')) == '1':
                        for _g in graphics:
                            _g.locked_to_body = True
                except Exception:
                    pass
                return SymbolUnitModel(name=str(src.get('name', payload.get('name', 'Template'))), body=body, pins=pins, texts=texts, graphics=graphics)
            except Exception:
                return None

        for fp in sorted(root.rglob('*.json')):
            try:
                data = json.loads(fp.read_text(encoding='utf-8'))
            except Exception:
                continue
            entries = data if isinstance(data, list) else [data]
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                unit = unit_from_payload(entry)
                if unit is None:
                    continue
                rel = fp.relative_to(root).with_suffix('').as_posix()
                entry_name = str(entry.get('template_name') or entry.get('name') or Path(rel).name).strip() or Path(rel).name
                part_name = template_partition_from_path(fp)
                # Two-stage Template Editor selection: Partition -> Symbol.  Generated
                # Mentor libraries therefore use the library partition as level 1 and
                # the imported symbol name as level 2.
                name = f'{part_name} / {entry_name}' if part_name and part_name != entry_name else entry_name
                result[name] = unit

                # Split-template detection for large IC partitions only.
                # Mentor split parts usually share the same base name and only differ
                # by a trailing .1/.2/.3 (or _1/-1). Keep the original part entries,
                # but add one grouped template under "Split Symbols" so New Split
                # Symbol can instantiate all parts instead of duplicating one unit.
                if is_large_ic_partition(part_name):
                    base, part_no = split_base_from_name(entry_name)
                    if base:
                        group_key = f'Split Symbols / {part_name} / {base}'
                        # Keep the original Mentor part name on the unit.  This is
                        # later used for stable part ordering and for Template
                        # Editor display of split-template parts.
                        try:
                            unit.name = entry_name
                        except Exception:
                            pass
                        split_groups.setdefault(group_key, []).append(copy.deepcopy(unit))
        grouped = {}
        for group_key, units in split_groups.items():
            if len(units) < 2:
                continue
            def _part_sort(u):
                nm = str(getattr(u, 'name', '') or '')
                # stable human order: numeric pages first, then functional pages
                m = re.search(r'[._-](\d{1,3})([a-zA-Z]?)(?:\.\d+)?$', nm)
                if m:
                    suffix = (m.group(2) or '').lower()
                    suffix_ord = (ord(suffix) - 96) if suffix else 0
                    return (0, int(m.group(1)), suffix_ord, nm.lower())
                order = ['control','ctrl','core','bank','gpio','io','ddr','mem','usb','pcie','sata','eth','rgmii','phy','adc','dac','power','pwr','supply','gnd','vss','vdd']
                low = nm.lower()
                for i, token in enumerate(order, start=1):
                    if token in low:
                        return (1, i, low)
                return (2, 9999, low)
            units = sorted(units, key=_part_sort)
            grouped[group_key] = units
            first = copy.deepcopy(units[0])
            try:
                first.name = group_key.split(' / ')[-1]
                first.body.attributes['MENTOR_SPLIT_TEMPLATE'] = '1'
                first.body.attributes['MENTOR_SPLIT_PARTS'] = str(len(units))
                first.body.visible_attributes['MENTOR_SPLIT_TEMPLATE'] = False
                first.body.visible_attributes['MENTOR_SPLIT_PARTS'] = False
            except Exception:
                pass
            result[group_key] = first
        self._external_split_templates = grouped
        try:
            self._external_template_cache_key = cache_key
            self._external_template_cache = result
            self._external_split_template_cache = grouped
            with index_file.open('wb') as fh:
                pickle.dump({
                    'cache_key': cache_key,
                    'templates': result,
                    'split_templates': grouped,
                }, fh, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            pass
        return result

    def unit_from_template_def(self, type_name: str, subtype_name: str | None, data: dict) -> SymbolUnitModel:
        type_def = data['types'][type_name]
        sub_def = (type_def.get('subtypes') or {}).get(subtype_name or '', {}) if subtype_name else {}
        body_def = copy.deepcopy(type_def.get('body') or {})
        body_def.update(sub_def.get('body') or {})
        w = float(body_def.get('width', type_def.get('body', {}).get('width', 16)))
        h = float(body_def.get('height', type_def.get('body', {}).get('height', 24)))
        body = SymbolBodyModel(x=float(body_def.get('x', -w/2)), y=float(body_def.get('y', h/2)), width=w, height=h)
        for attr in ('color', 'line_width', 'line_style', 'refdes_align', 'body_attr_align', 'rotation', 'scale_x', 'scale_y'):
            if attr in body_def:
                setattr(body, attr, body_def[attr])
        if isinstance(body_def.get('attribute_font'), dict):
            body.attribute_font = FontModel(**body_def['attribute_font'])
        if isinstance(body_def.get('refdes_font'), dict):
            body.refdes_font = FontModel(**body_def['refdes_font'])
        if isinstance(body_def.get('attribute_texts'), dict):
            body.attribute_texts = {
                str(k): (v if isinstance(v, TextModel) else TextModel(**dict(v)))
                for k, v in body_def.get('attribute_texts', {}).items()
                if isinstance(v, (dict, TextModel))
            }
        attrs = []
        visible_from_source = {}

        def add_attr_entry(entry):
            """Accept plain names and imported .sym-style attribute dictionaries.

            .sym imports may provide attributes as dictionaries containing a name and
            a visibility flag. In that case the visibility from the source file wins.
            For plain names, visibility is resolved later from body.visible_attributes.
            """
            if isinstance(entry, dict):
                name = (entry.get('name') or entry.get('attribute') or entry.get('key') or entry.get('label') or '').strip()
                if not name:
                    return
                if name not in attrs:
                    attrs.append(name)
                if any(k in entry for k in ('visible', 'visibility', 'displayed', 'show')):
                    raw = entry.get('visible', entry.get('visibility', entry.get('displayed', entry.get('show'))))
                    visible_from_source[name] = str(raw).strip().lower() not in ('0', 'false', 'no', 'off', 'hidden', '')
                return
            name = str(entry).strip()
            if name and name not in attrs:
                attrs.append(name)

        for a in data.get('global_attributes', []):
            add_attr_entry(a)
        for a in type_def.get('attributes', []):
            add_attr_entry(a)
        for a in sub_def.get('attributes', []):
            add_attr_entry(a)
        if isinstance(body_def.get('attributes'), dict):
            for a in body_def['attributes'].keys():
                add_attr_entry(a)
        elif isinstance(body_def.get('attributes'), list):
            for a in body_def['attributes']:
                add_attr_entry(a)

        prefix = sub_def.get('prefix', type_def.get('prefix', '?'))
        body.attributes = {a: '' for a in attrs}
        if isinstance(body_def.get('attributes'), dict):
            body.attributes.update(copy.deepcopy(body_def.get('attributes') or {}))
        body.attributes.setdefault('RefDes', f'{prefix}?')
        if not body.attributes.get('RefDes'):
            body.attributes['RefDes'] = f'{prefix}?'
        if 'RefDes' not in attrs:
            attrs.insert(0, 'RefDes')

        # Visibility belongs to the source/template. Do not force Package/Value/RefDes
        # visible after a .sym/template import; preserve the source visibility exactly
        # when present. For legacy definitions without visibility data, keep the old
        # practical defaults.
        explicit_vis = body_def.get('visible_attributes')
        if isinstance(explicit_vis, dict):
            body.visible_attributes = {a: False for a in attrs}
            body.visible_attributes.update({str(k): bool(v) for k, v in copy.deepcopy(explicit_vis).items()})
        elif visible_from_source:
            body.visible_attributes = {a: visible_from_source.get(a, False) for a in attrs}
        else:
            body.visible_attributes = {a: a in ('RefDes', 'Value', 'Package') for a in attrs}
        pins = []
        pin_defs = sub_def.get('default_pins') or type_def.get('default_pins', []) or []
        for idx, pd in enumerate(pin_defs, start=1):
            d = copy.deepcopy(pd)
            pin = PinModel(
                number=str(d.get('number', idx)), name=str(d.get('name', 'PIN')),
                function=str(d.get('function', d.get('name', ''))),
                pin_type=str(d.get('pin_type', d.get('type', PinType.BIDI.value))), side=str(d.get('side', PinSide.LEFT.value)),
                inverted=bool(d.get('inverted', False)),
                x=float(d.get('x', 0.0)), y=float(d.get('y', 0.0)), length=float(d.get('length', 2.0)),
            )
            for attr in ('color', 'visible_number', 'visible_name', 'visible_function', 'line_width', 'line_style', 'rotation', 'scale_x', 'scale_y'):
                if attr in d:
                    setattr(pin, attr, d[attr])
            if isinstance(d.get('attributes'), dict):
                pin.attributes = copy.deepcopy(d.get('attributes') or {})
            if isinstance(d.get('visible_attributes'), dict):
                pin.visible_attributes = copy.deepcopy(d.get('visible_attributes') or {})
            pins.append(pin)
        count = int(sub_def.get('pins', 0) or 0)
        if count and len(pins) < count:
            for i in range(len(pins) + 1, count + 1):
                pins.append(PinModel(number=str(i), name=f'PIN{i}', function='', pin_type=PinType.PASSIVE.value, side=PinSide.LEFT.value if i % 2 else PinSide.RIGHT.value))
        u = SymbolUnitModel(name=(subtype_name or type_name), body=body, pins=pins)
        # Restore optional template graphics/texts saved by the canvas template editor.
        for gd in sub_def.get('graphics', type_def.get('graphics', [])) or []:
            style = gd.get('style') if isinstance(gd, dict) else None
            g = GraphicModel(**{k: v for k, v in dict(gd).items() if k != 'style'})
            if isinstance(style, dict): g.style = StyleModel(**style)
            u.graphics.append(g)
        for td in sub_def.get('texts', type_def.get('texts', [])) or []:
            u.texts.append(TextModel(**dict(td)))
        # Distribute pins only when the template did not store explicit coordinates.
        if not any(abs(getattr(p, 'x', 0.0)) > 1e-9 or abs(getattr(p, 'y', 0.0)) > 1e-9 for p in u.pins):
            left = [p for p in u.pins if p.side == PinSide.LEFT.value]
            right = [p for p in u.pins if p.side == PinSide.RIGHT.value]
            for group, side in ((left, PinSide.LEFT.value), (right, PinSide.RIGHT.value)):
                n = max(1, len(group))
                for i, pin in enumerate(group, start=1):
                    pin.x = body.x if side == PinSide.LEFT.value else body.x + body.width
                    pin.y = body.y - (body.height * i / (n + 1))
        return u


    def builtin_resistor_templates(self) -> dict[str, SymbolUnitModel]:
        """Last-resort built-in templates for the first lean template stage.

        This makes the Template Editor usable even when symbol_types.json is
        misplaced, malformed, filtered out, or not deployed.  The geometry is the
        0° Liebherr/Mentor wid.1 master view normalized with
        254000 Mentor units = 1 Wizard grid = 0.100 inch.
        """
        body = SymbolBodyModel(
            x=1.5,
            y=1.5,
            width=3.0,
            height=1.0,
            color=(0, 0, 0),
            line_width=0.03,
            line_style=LineStyle.SOLID.value,
            refdes_align='center',
            body_attr_align='center',
        )
        body.attributes = {
            'RefDes': '?',
            'PART_NAME': 'TNR_LEG',
            '@XYCOORD': '',
            'LEON_Link': '',
            'DEVICE': 'Artikelcode',
            'VALUE': 'VALUE',
            'CASE': 'BAUFORM',
            'CLASS': '',
            'FORWARD_PCB': '1',
            'MENTOR_GRID_UNIT': '254000',
        }
        body.visible_attributes = {
            'RefDes': True,
            'PART_NAME': False,
            '@XYCOORD': False,
            'LEON_Link': False,
            'DEVICE': False,
            'VALUE': True,
            'CASE': True,
            'CLASS': False,
            'FORWARD_PCB': False,
            'MENTOR_GRID_UNIT': False,
        }
        body.attribute_texts = {
            'RefDes': TextModel(text='?', x=3.0, y=2.5, font_size_grid=1.0, h_align=TextHAlign.CENTER.value),
            'VALUE': TextModel(text='VALUE', x=3.0, y=-0.4, font_size_grid=0.75, h_align=TextHAlign.CENTER.value),
            'CASE': TextModel(text='CASE=BAUFORM', x=1.0, y=-1.2, font_size_grid=0.65),
        }
        pins = [
            PinModel(number='1', name='N1', function='N1', pin_type=PinType.ANALOG.value, side=PinSide.LEFT.value,
                     x=0.0, y=1.0, length=1.5, visible_number=False, visible_name=False, visible_function=False,
                     attributes={'PINTYPE': 'ANALOG'}, visible_attributes={'PINTYPE': False}),
            PinModel(number='2', name='N2', function='N2', pin_type=PinType.ANALOG.value, side=PinSide.RIGHT.value,
                     x=6.0, y=1.0, length=1.5, visible_number=False, visible_name=False, visible_function=False,
                     attributes={'PINTYPE': 'ANALOG'}, visible_attributes={'PINTYPE': False}),
        ]
        unit = SymbolUnitModel(name='Resistor', body=body, pins=pins, texts=[], graphics=[])
        return {'Passive / Resistor': unit}

    def load_symbol_type_templates(self) -> dict[str, SymbolUnitModel]:
        path = self.symbol_types_path()
        templates = {}
        if path and path.exists():
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                for type_name, type_def in (data.get('types') or {}).items():
                    subtypes = type_def.get('subtypes') or {}
                    if not subtypes:
                        templates[type_name] = self.unit_from_template_def(type_name, None, data)
                    # For types with subtypes, only the concrete subtype is edited/selected.
                    for subtype_name in subtypes.keys():
                        try:
                            templates[f'{type_name} / {subtype_name}'] = self.unit_from_template_def(type_name, subtype_name, data)
                        except Exception as item_exc:
                            self.statusBar().showMessage(f'Template {type_name}/{subtype_name} konnte nicht geladen werden: {item_exc}', 6000)
            except Exception as exc:
                self.statusBar().showMessage(f'symbol_types.json konnte nicht geladen werden: {exc}', 6000)
        if not templates:
            templates.update(self.builtin_resistor_templates())
            self.statusBar().showMessage('Template-Fallback aktiv: Passive / Resistor', 6000)
        return templates

    def available_templates(self, split_only: bool = False) -> dict[str, SymbolUnitModel]:
        """Return the template catalogue without expensive deep-copy storms.

        Older builds deep-copied the complete catalogue on every dialog open.
        With several thousand Mentor templates this made both "New Symbol" and
        the Template Editor slow.  The catalogue itself is treated as read-only;
        selected units are deep-copied only when they are actually instantiated or
        edited.
        """
        cache_key = (bool(split_only), id(self.symbol_templates), len(self.symbol_templates))
        cache = getattr(self, '_available_template_cache', {}) or {}
        if cache_key in cache:
            return cache[cache_key]

        base_key = ('all', id(self.symbol_templates), len(self.symbol_templates))
        if base_key in cache:
            templates = cache[base_key]
        else:
            templates = self.load_symbol_type_templates()
            templates.update(self.load_external_template_files())
            templates.update(self.symbol_templates)
            if not templates:
                templates.update(self.builtin_resistor_templates())
            cache[base_key] = templates

        if split_only:
            split_map = getattr(self, '_external_split_templates', {}) or {}
            filtered = {k: v for k, v in templates.items()
                        if k in split_map
                        or k == 'IC' or k.startswith('IC /')
                        or k.startswith('Digital IC /')
                        or k.startswith('Split Symbols /')}
            for k, units in split_map.items():
                if units and k not in filtered:
                    filtered[k] = units[0]
            templates = filtered

        cache[cache_key] = templates
        self._available_template_cache = cache
        return templates


    def apply_template_style_to_matching_symbols(self, template_name: str, tmpl: SymbolUnitModel):
        """Update style/attribute definitions for symbols created from a template.

        Geometry and existing pins stay untouched, as requested. Only non-destructive
        style fields and the attribute catalogue/visibility are refreshed.
        """
        changed = False
        for sym in self.library.symbols:
            if getattr(sym, 'template_name', '') != template_name:
                continue
            for u in sym.units:
                u.body.color = tmpl.body.color
                u.body.line_width = tmpl.body.line_width
                u.body.line_style = tmpl.body.line_style
                u.body.attribute_font = copy.deepcopy(tmpl.body.attribute_font)
                u.body.refdes_font = copy.deepcopy(tmpl.body.refdes_font)
                for key, val in tmpl.body.attributes.items():
                    u.body.attributes.setdefault(key, val)
                for key, val in tmpl.body.visible_attributes.items():
                    u.body.visible_attributes[key] = val
            changed = True
        if changed:
            self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()

    def _template_key_parts_for_dialog(self, key: str):
        """Return (partition, symbol) for two-stage template selection.

        Split templates use keys like "Split Symbols / <Mentor partition> / <base>".
        In the dialog this becomes partition "Split Symbols / <Mentor partition>"
        and symbol "<base>" so all grouped split templates are visible without a
        huge flat list.
        """
        key = str(key or '').strip()
        if key == '<NONE>':
            return '<NONE>', '<NONE>'
        if ' / ' not in key:
            return 'General', key or 'Template'
        parts = [p.strip() for p in key.split(' / ') if p.strip()]
        if len(parts) >= 3 and parts[0] == 'Split Symbols':
            return ' / '.join(parts[:-1]), parts[-1]
        return parts[0] or 'General', ' / '.join(parts[1:]) or key

    def _template_key_from_dialog_parts(self, partition: str, symbol: str):
        partition = str(partition or '').strip()
        symbol = str(symbol or '').strip()
        if partition == '<NONE>' or symbol == '<NONE>':
            return '<NONE>'
        if not partition or partition == 'General':
            return symbol
        return f'{partition} / {symbol}' if symbol else partition

    def ask_new_symbol_template(self, kind: str):
        template_keys = self.available_template_keys(split_only=(kind == SymbolKind.SPLIT.value))
        dlg = QDialog(self)
        dlg.setWindowTitle('Neues Split-Symbol anlegen' if kind == SymbolKind.SPLIT.value else 'Neues Symbol anlegen')
        layout = QFormLayout(dlg)

        partition_combo = QComboBox(); partition_combo.setEditable(False)
        symbol_combo = QComboBox(); symbol_combo.setEditable(False)
        filter_edit = QLineEdit(); filter_edit.setPlaceholderText('Filter...')
        name_edit = QLineEdit(); name_edit.setMaxLength(24)

        def parts_for(key):
            return self._template_key_parts_for_dialog(key)
        def full_key(part, sym):
            return self._template_key_from_dialog_parts(part, sym)

        by_partition: dict[str, list[str]] = {}
        for key in sorted(template_keys):
            if kind == SymbolKind.SPLIT.value and str(key).startswith('Passive'):
                continue
            part, sym = parts_for(key)
            if kind == SymbolKind.SPLIT.value and part.startswith('Passive'):
                continue
            by_partition.setdefault(part, []).append(sym)

        partitions = sorted(by_partition.keys()) or ['<NONE>']
        # For split-symbol creation, put the empty template and grouped Mentor
        # split templates first. Passive single-symbol templates are suppressed.
        if kind == SymbolKind.SPLIT.value:
            partitions = sorted(partitions, key=lambda p: (0 if p == '<NONE>' else (1 if p.startswith('Split Symbols') else 2), p.lower()))
        partition_combo.addItems(partitions)

        def rebuild_symbols():
            part = partition_combo.currentText().strip()
            needle = filter_edit.text().strip().lower()
            symbols = by_partition.get(part, [])
            if needle:
                symbols = [x for x in symbols if needle in x.lower() or needle in full_key(part, x).lower()]
            symbol_combo.blockSignals(True)
            symbol_combo.clear(); symbol_combo.addItems(sorted(symbols, key=str.lower))
            symbol_combo.blockSignals(False)
            update_default_name()

        def update_default_name():
            if not name_edit.text().strip():
                txt = symbol_combo.currentText().strip() or partition_combo.currentText().split('/')[-1].strip()
                if txt == '<NONE>':
                    txt = 'Split_Symbol' if kind == SymbolKind.SPLIT.value else 'Symbol'
                base = txt.replace(' ', '_') or ('Split_Symbol' if kind == SymbolKind.SPLIT.value else 'Symbol')
                # Avoid trailing .1-style suffixes in the symbol name suggestion.
                base = re.sub(r'[._-]\d{1,3}$', '', base)
                name_edit.setPlaceholderText(base[:24])

        partition_combo.currentTextChanged.connect(lambda *_: rebuild_symbols())
        filter_edit.textChanged.connect(lambda *_: rebuild_symbols())
        symbol_combo.currentTextChanged.connect(lambda *_: update_default_name())
        rebuild_symbols()

        layout.addRow('Partition', partition_combo)
        layout.addRow('Template', symbol_combo)
        layout.addRow('Filter', filter_edit)
        layout.addRow('Symbolname', name_edit)
        if kind == SymbolKind.SPLIT.value:
            split_count = len((self.load_template_manifest().get('split_templates') or {}))
            hint_text = f'{split_count} erkannte Mentor-Split-Templates sind als Vorschläge verfügbar. Auswahl ist zweistufig: Partition → Symbol.'
        else:
            hint_text = 'Auswahl ist zweistufig: Partition → Symbol.'
        hint = QLabel(hint_text + '\nSymbolname: 3 bis 24 Zeichen.')
        hint.setWordWrap(True); layout.addRow('', hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addRow(buttons)

        def accept_if_valid():
            n = name_edit.text().strip() or name_edit.placeholderText().strip()
            if len(n) < 3 or len(n) > 24:
                QMessageBox.warning(dlg, 'Symbolname', 'Bitte einen Symbolnamen mit 3 bis 24 Zeichen eingeben.')
                return
            if not symbol_combo.currentText().strip():
                QMessageBox.warning(dlg, 'Template', 'Bitte ein Template auswählen.')
                return
            name_edit.setText(n)
            dlg.accept()

        buttons.accepted.connect(accept_if_valid); buttons.rejected.connect(dlg.reject)
        if dlg.exec() == QDialog.Accepted:
            return name_edit.text().strip(), full_key(partition_combo.currentText(), symbol_combo.currentText())
        return None


    def unit_to_template_payload(self, unit: SymbolUnitModel) -> dict:
        body = copy.deepcopy(asdict(unit.body))
        attrs = list(unit.body.attributes.keys())
        body['attributes'] = copy.deepcopy(unit.body.attributes)
        body['visible_attributes'] = copy.deepcopy(unit.body.visible_attributes)
        return {
            'attributes': attrs,
            'body': body,
            'default_pins': [copy.deepcopy(asdict(p)) for p in unit.pins],
            'graphics': [copy.deepcopy(asdict(g)) for g in unit.graphics],
            'texts': [copy.deepcopy(asdict(t)) for t in unit.texts],
        }

    def merge_save_template_to_file(self, template_name: str, unit: SymbolUnitModel):
        """Persist a template edit to the source that the Template Editor loaded.

        External Mentor-derived templates live under symbol_wizard/symbol_templates
        and are loaded through the manifest.  Earlier builds always wrote edited
        templates into symbol_types.json; on reload the external manifest entry won
        again, so the user saw the old geometry.  This method now updates the
        manifest-backed JSON entry in place when possible and falls back to
        symbol_types.json only for built-in/non-external templates.
        """
        def _write_external_manifest_entry() -> bool:
            try:
                manifest = self.load_template_manifest()
                meta = (manifest.get('templates') or {}).get(template_name)
                if not meta:
                    return False
                root = self.symbol_templates_dir()
                fp = root / str(meta.get('file') or '')
                if not fp.exists():
                    return False
                data = json.loads(fp.read_text(encoding='utf-8'))
                entries = data if isinstance(data, list) else [data]
                idx = int(meta.get('index', 0) or 0)
                if idx < 0 or idx >= len(entries):
                    return False

                unit_copy = copy.deepcopy(unit)
                try:
                    self.normalize_unit_origin(unit_copy, getattr(self.symbol, 'origin', OriginMode.CENTER.value))
                except Exception:
                    pass
                try:
                    unit_copy.body.attributes['TEMPLATE_GRAPHICS_AS_BODY'] = '1'
                except Exception:
                    pass
                for _g in getattr(unit_copy, 'graphics', []) or []:
                    try:
                        _g.locked_to_body = True
                    except Exception:
                        pass

                old = entries[idx] if isinstance(entries[idx], dict) else {}
                entry = dict(old)
                entry['name'] = str(meta.get('name') or template_name.split(' / ')[-1])
                entry['template_name'] = template_name
                entry['unit'] = copy.deepcopy(asdict(unit_copy))
                entries[idx] = entry
                fp.write_text(json.dumps(entries if isinstance(data, list) else entries[0], ensure_ascii=False, indent=2), encoding='utf-8')

                # Drop stale caches so the next load sees the new JSON immediately.
                for attr in ('_template_file_json_cache', '_template_unit_lru', '_template_manifest_cache', '_template_manifest_cache_key'):
                    try:
                        if hasattr(self, attr):
                            delattr(self, attr)
                    except Exception:
                        pass
                self.symbol_templates.clear()
                return True
            except Exception:
                return False

        if _write_external_manifest_entry():
            return

        path = self.symbol_types_path()
        if not path:
            return
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            data = {'global_attributes': [], 'types': {}}
        data.setdefault('types', {})
        unit_copy = copy.deepcopy(unit)
        try:
            self.normalize_unit_origin(unit_copy, getattr(self.symbol, 'origin', OriginMode.CENTER.value))
        except Exception:
            pass
        payload = self.unit_to_template_payload(unit_copy)
        if ' / ' in template_name:
            type_name, subtype_name = [x.strip() for x in template_name.split(' / ', 1)]
            t = data['types'].setdefault(type_name, {'prefix': '?', 'subtypes': {}})
            t.setdefault('subtypes', {})
            sub = t['subtypes'].setdefault(subtype_name, {})
            sub.update({k: copy.deepcopy(v) for k, v in payload.items() if k != 'default_pins'})
            sub['default_pins'] = payload['default_pins']
            if 'body' not in t and 'body' in payload:
                t['body'] = copy.deepcopy(payload['body'])
        else:
            t = data['types'].setdefault(template_name, {'prefix': '?', 'subtypes': {}})
            t.update(copy.deepcopy(payload))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        self.symbol_templates.clear()


    # ------------------------------------------------------------------ File IO
    def save_current_symbol(self):
        if not self.validate_pins(): return
        p, _ = QFileDialog.getSaveFileName(self, 'Save Current Symbol JSON', self.symbol.name + '.json', 'JSON (*.json)')
        if p:
            save_symbol(p, self.symbol)
            self.dirty = False
            self._dirty_symbol_index = None
            self._clean_symbol_snapshot = None

    def save_all_symbols(self):
        for s in self.library.symbols:
            d = duplicate_pin_numbers(s)
            if d:
                QMessageBox.warning(self, 'Pin validation', f'{s.name}: doppelte Pinnummern: ' + ', '.join(d))
                return
        p, _ = QFileDialog.getSaveFileName(self, 'Save All Symbols JSON', 'symbol_library.json', 'JSON (*.json)')
        if p:
            save_library(p, self.library)
            self.dirty = False
            self._dirty_symbol_index = None
            self._clean_symbol_snapshot = None

    def open_library(self):
        p, _ = QFileDialog.getOpenFileName(self, 'Open Library JSON', '', 'JSON (*.json)')
        if p:
            self.library = load_library(p)
            for s in self.library.symbols:
                if not getattr(s, 'kind', None):
                    s.kind = SymbolKind.SPLIT.value if getattr(s, 'is_split', False) else SymbolKind.SINGLE.value
            self.current_unit_index = 0
            self.dirty = False
            self.undo_stack.clear(); self.redo_stack.clear()
            self.rebuild_all()

    def import_symbol(self):
        p, _ = QFileDialog.getOpenFileName(self, 'Import Symbol JSON', '', 'JSON (*.json)')
        if not p: return
        s = load_symbol(p)
        # Imported symbols keep their source scale.  Only their local origin is
        # normalised per unit so each split part can be edited independently and
        # starts in the correct drawing direction for the selected origin mode.
        self.normalize_symbol_origins_for_import(s)
        s.name = self.library.unique_import_name(s.name)
        self.library.symbols.append(s)
        self.library.current_symbol_index = len(self.library.symbols) - 1
        self.current_unit_index = 0
        self.rebuild_all()

    def import_mentor_symbol(self):
        p, _ = QFileDialog.getOpenFileName(self, 'Import Mentor Symbol', '', 'Mentor Symbol (*.sym *.1 *.zip);;Mentor Split ZIP (*.zip);;All Files (*)')
        if not p:
            return
        try:
            symbols = import_mentor_symbols(p)
        except Exception as exc:
            QMessageBox.critical(self, 'Import Mentor Symbol .sym', f'Die Mentor Symboldatei konnte nicht importiert werden:\n{exc}')
            return
        imported = 0
        for s in symbols:
            # Imported symbols are initially aligned by the BODY anchor, never by pins or other elements.
            self.normalize_symbol_origins_for_import(s)
            s.name = self.library.unique_import_name(s.name)
            self.library.symbols.append(s)
            imported += 1
        self.library.current_symbol_index = len(self.library.symbols) - 1
        self.current_unit_index = 0
        self.dirty = True
        self.undo_stack.clear(); self.redo_stack.clear()
        self.rebuild_all()
        self.statusBar().showMessage(f'Mentor Import abgeschlossen: {imported} Symbol(e) aus {Path(p).name}', 5000)

    def export_current_mentor_symbol(self):
        if not self.validate_pins():
            return
        is_split = bool(getattr(self.symbol, 'is_split', False) or getattr(self.symbol, 'kind', '') == 'split' or len(getattr(self.symbol, 'units', []) or []) > 1)
        default_name = (self.symbol.name or 'symbol').replace(' ', '_') + ('.zip' if is_split else '.sym')
        p, _ = QFileDialog.getSaveFileName(self, 'Export Current Mentor Symbol', default_name, 'Mentor Split ZIP (*.zip);;Mentor Symbol (*.sym *.1);;All Files (*)')
        if not p:
            return
        try:
            export_mentor_sym(p, self.symbol)
        except Exception as exc:
            QMessageBox.critical(self, 'Export Mentor Symbol .sym', f'Die Mentor Symboldatei konnte nicht exportiert werden:\n{exc}')
            return
        self.statusBar().showMessage(f'Mentor Symbol exportiert: {Path(p).name}', 5000)

# ---------------------------------------------------------------------------
# Liebherr transform/origin model patch
# ---------------------------------------------------------------------------
# Canonical rule used by both Symbol Wizard and Template Editor:
#   BODY bounds are derived only from BODY graphics (locked/template/imported
#   primitives; in Template Editor all template graphics are Body graphics).
#   Pins, texts and attributes are attached to BODY but never expand BODY bounds.
#   All transforms use a stable BODY-origin anchor and immutable local offsets.

def _lh_is_body_graphic(self, gr):
    try:
        if getattr(self, 'is_template_editor', False):
            return True
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        marker = str(getattr(gr, 'mentor_raw', '') or '')
        return bool(getattr(gr, 'locked_to_body', False) or role in ('body','template_body','imported_body') or marker != '__USER_GRAPHIC__' and role != 'user_graphic')
    except Exception:
        return False


def _lh_rot_pt(x, y, cx, cy, deg):
    if abs(float(deg or 0.0)) < 1e-12:
        return float(x), float(y)
    a = math.radians(float(deg or 0.0))
    ca, sa = math.cos(a), math.sin(a)
    dx, dy = float(x) - float(cx), float(y) - float(cy)
    return cx + ca*dx - sa*dy, cy + sa*dx + ca*dy


def _lh_graphic_points(self, gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    shape = str(getattr(gr, 'shape', '') or '')
    if shape in ('line', 'arc'):
        pts = [(x, y), (x+w, y-h)]
        cx, cy = x + w/2.0, y - h/2.0
        # Include quadratic control point / curve apex so arc BODY bounds are not too small.
        ctrl_x = getattr(gr, 'ctrl_x', None); ctrl_y = getattr(gr, 'ctrl_y', None)
        if ctrl_x is not None and ctrl_y is not None:
            pts.append((x + float(ctrl_x), y - float(ctrl_y)))
        else:
            cr = float(getattr(gr, 'curve_radius', 0.0) or 0.0)
            if abs(cr) > 1e-12:
                pts.append((x + w/2.0, y - h/2.0 + cr))
    else:
        x2 = x + w; y2 = y - h
        pts = [(x, y), (x2, y), (x2, y2), (x, y2)]
        cx, cy = x + w/2.0, y - h/2.0
    rot = float(getattr(gr, 'rotation', 0.0) or 0.0)
    sx = float(getattr(gr, 'scale_x', 1.0) or 1.0)
    sy = float(getattr(gr, 'scale_y', 1.0) or 1.0)
    out = []
    for px, py in pts:
        # Approximate item scale around center in model coordinates.
        qx = cx + (px - cx) * sx
        qy = cy + (py - cy) * sy
        out.append(_lh_rot_pt(qx, qy, cx, cy, rot))
    return out


def _lh_body_graphics(self, unit=None):
    u = unit or self.current_unit
    return [g for g in (getattr(u, 'graphics', []) or []) if _lh_is_body_graphic(self, g)]


def _lh_body_graphics_bounds(self, unit=None):
    u = unit or self.current_unit
    gs = _lh_body_graphics(self, u)
    if not gs:
        return None
    pts = []
    for gr in gs:
        pts.extend(_lh_graphic_points(self, gr))
    if not pts:
        return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    minx, maxx = min(xs), max(xs); miny, maxy = min(ys), max(ys)
    if maxx - minx < 1e-9 or maxy - miny < 1e-9:
        return None
    return (minx, maxy, maxx - minx, maxy - miny)  # x,y,width,height with y=top


def _lh_sync_body_model_to_body_graphics(self, unit=None):
    u = unit or self.current_unit
    b = getattr(u, 'body', None)
    if b is None:
        return
    bounds = _lh_body_graphics_bounds(self, u)
    if bounds is None:
        return
    x, y, w, h = bounds
    b.x = self._clean_float(x) if hasattr(self, '_clean_float') else x
    b.y = self._clean_float(y) if hasattr(self, '_clean_float') else y
    b.width = self._clean_float(max(0.01, w)) if hasattr(self, '_clean_float') else max(0.01, w)
    b.height = self._clean_float(max(0.01, h)) if hasattr(self, '_clean_float') else max(0.01, h)
    # The logical BODY rotation is represented by actual graphics; keep proxy angle neutral.
    # Internally-created <NONE> bodies have no body graphics and keep their own rotation.
    try:
        if _lh_body_graphics(self, u):
            b.rotation = 0.0
    except Exception:
        pass


def _lh_shift_unit_geometry(self, unit, dx, dy):
    unit.body.x += dx; unit.body.y += dy
    for p in getattr(unit, 'pins', []) or []:
        p.x += dx; p.y += dy
        for ax_name, ay_name in (('label_x', 'label_y'), ('number_x', 'number_y')):
            if getattr(p, ax_name, None) is not None:
                setattr(p, ax_name, getattr(p, ax_name) + dx)
            if getattr(p, ay_name, None) is not None:
                setattr(p, ay_name, getattr(p, ay_name) + dy)
        for tm in (getattr(p, 'attribute_texts', {}) or {}).values():
            try: tm.x += dx; tm.y += dy
            except Exception: pass
    for t in getattr(unit, 'texts', []) or []:
        t.x += dx; t.y += dy
    for t in (getattr(unit.body, 'attribute_texts', {}) or {}).values():
        t.x += dx; t.y += dy
    for g in getattr(unit, 'graphics', []) or []:
        g.x += dx; g.y += dy
    try:
        self._invalidate_body_group_transform_cache(unit)
    except Exception:
        pass


def _lh_anchor_for_unit(self, unit, mode=None):
    mode = mode or getattr(self.symbol, 'origin', OriginMode.CENTER.value)
    _lh_sync_body_model_to_body_graphics(self, unit)
    return self.body_anchor_point(unit.body, mode)


def _lh_normalize_unit_origin(self, unit, mode):
    # BODY bounds from graphics only; pins/text/attributes are attached but excluded.
    _lh_sync_body_model_to_body_graphics(self, unit)
    ax, ay = self.body_anchor_point(unit.body, mode)
    if abs(ax) > 1e-9 or abs(ay) > 1e-9:
        _lh_shift_unit_geometry(self, unit, -ax, -ay)
    _lh_sync_body_model_to_body_graphics(self, unit)


def _lh_dock_pins_to_body(self, u):
    # Axis docking is only valid for unrotated internal <NONE>-style bodies.
    # Imported/template bodies already carry native pin anchors and must not be
    # re-docked to an axis-aligned proxy rectangle on every rebuild.
    try:
        if _lh_body_graphics(self, u):
            return
        if abs(float(getattr(u.body, 'rotation', 0.0) or 0.0)) > 1e-9:
            return
    except Exception:
        pass
    b = u.body
    for p in getattr(u, 'pins', []) or []:
        if p.side == PinSide.LEFT.value:
            p.x = b.x
        elif p.side == PinSide.RIGHT.value:
            p.x = b.x + b.width
        elif p.side == PinSide.TOP.value:
            p.y = b.y
        elif p.side == PinSide.BOTTOM.value:
            p.y = b.y - b.height


def _lh_capture_body_group_base(self, unit=None):
    u = unit or self.current_unit
    _lh_sync_body_model_to_body_graphics(self, u)
    b = u.body
    mode = getattr(self.symbol, 'origin', OriginMode.CENTER.value)
    ax, ay = self.body_anchor_point(b, mode)
    base = {
        'pivot': (float(ax), float(ay)), 'anchor': (float(ax), float(ay)), 'origin_mode': mode,
        'has_body_graphics': bool(_lh_body_graphics(self, u)),
        'body': {'x': float(b.x), 'y': float(b.y), 'w': float(b.width), 'h': float(b.height),
                 'rot': float(getattr(b, 'rotation', 0.0) or 0.0),
                 'sx': float(getattr(b, 'scale_x', 1.0) or 1.0), 'sy': float(getattr(b, 'scale_y', 1.0) or 1.0)},
        'pins': [], 'texts': [], 'body_attrs': [], 'graphics': []
    }
    for p in getattr(u, 'pins', []) or []:
        pd = {'obj': p, 'x': float(p.x), 'y': float(p.y), 'length': float(getattr(p, 'length', 1.0) or 1.0),
              'rot': float(getattr(p, 'rotation', 0.0) or 0.0), 'label': None, 'number': None, 'attrs': [],
              'nfs': float(getattr(getattr(p, 'number_font', None), 'size_grid', 0.45) or 0.45),
              'lfs': float(getattr(getattr(p, 'label_font', None), 'size_grid', 0.55) or 0.55)}
        if getattr(p, 'label_x', None) is not None and getattr(p, 'label_y', None) is not None:
            pd['label'] = (float(p.label_x), float(p.label_y))
        if getattr(p, 'number_x', None) is not None and getattr(p, 'number_y', None) is not None:
            pd['number'] = (float(p.number_x), float(p.number_y))
        for key, tm in (getattr(p, 'attribute_texts', {}) or {}).items():
            try: pd['attrs'].append((key, tm, float(tm.x), float(tm.y), float(getattr(tm, 'rotation', 0.0) or 0.0), float(getattr(tm, 'font_size_grid', 0.55) or 0.55)))
            except Exception: pass
        base['pins'].append(pd)
    for t in getattr(u, 'texts', []) or []:
        try: base['texts'].append({'obj': t, 'x': float(t.x), 'y': float(t.y), 'rot': float(getattr(t, 'rotation', 0.0) or 0.0), 'font': float(getattr(t, 'font_size_grid', .75) or .75)})
        except Exception: pass
    for key, t in (getattr(b, 'attribute_texts', {}) or {}).items():
        try: base['body_attrs'].append({'key': key, 'obj': t, 'x': float(t.x), 'y': float(t.y), 'rot': float(getattr(t, 'rotation', 0.0) or 0.0), 'font': float(getattr(t, 'font_size_grid', .75) or .75)})
        except Exception: pass
    for gr in getattr(u, 'graphics', []) or []:
        try:
            base['graphics'].append({'obj': gr, 'x': float(gr.x), 'y': float(gr.y), 'w': float(getattr(gr,'w',0.0) or 0.0), 'h': float(getattr(gr,'h',0.0) or 0.0),
                'rot': float(getattr(gr, 'rotation', 0.0) or 0.0), 'sx': float(getattr(gr, 'scale_x', 1.0) or 1.0), 'sy': float(getattr(gr, 'scale_y', 1.0) or 1.0),
                'ctrl_x': getattr(gr, 'ctrl_x', None), 'ctrl_y': getattr(gr, 'ctrl_y', None), 'curve_radius': float(getattr(gr, 'curve_radius', 0.0) or 0.0)})
        except Exception: pass
    u._body_group_transform = {'base': base, 'M': (1.0, 0.0, 0.0, 1.0)}
    return u._body_group_transform


def _lh_apply_matrix_from_base(self, st, refresh=True):
    base = st['base']; M = st.get('M', (1.0,0.0,0.0,1.0)); ax, ay = base['anchor']
    def clean(v):
        try: return self._clean_float(v)
        except Exception: return float(v)
    def app(x, y):
        a,b,c,d = M; dx, dy = float(x)-ax, float(y)-ay
        return clean(ax + a*dx + b*dy), clean(ay + c*dx + d*dy)
    def linear_vec(x, y):
        a,b,c,d = M
        return clean(a*float(x) + b*float(y)), clean(c*float(x) + d*float(y))
    def angle():
        try: return self._mat_col_angle(M)
        except Exception:
            a,b,c,d = M; return math.degrees(math.atan2(c,a))
    def sx_abs():
        a,b,c,d = M; return max(1e-9, math.hypot(a,c))
    def sy_abs():
        a,b,c,d = M; return max(1e-9, math.hypot(b,d))
    u = self.current_unit; b = u.body
    sxv, syv = sx_abs(), sy_abs(); font_factor = max(0.1, (abs(sxv)+abs(syv))/2.0)
    # Transform real graphics first.  For imported/template BODYs these graphics
    # ARE the visible BODY; afterwards the logical BODY bounds are resynced from them.
    for gd in base.get('graphics', []):
        gr = gd['obj']
        gr.x, gr.y = app(gd['x'], gd['y'])
        gr.w, gr.h = linear_vec(gd['w'], gd['h'])
        gr.rotation = clean((gd.get('rot',0.0) + angle()) % 360.0)
        gr.scale_x = gd.get('sx', 1.0); gr.scale_y = gd.get('sy', 1.0)
        if gd.get('ctrl_x') is not None and gd.get('ctrl_y') is not None:
            gr.ctrl_x, gr.ctrl_y = linear_vec(gd['ctrl_x'], gd['ctrl_y'])
        try: gr.curve_radius = clean(gd.get('curve_radius', 0.0) * font_factor)
        except Exception: pass
    # Internal <NONE> body with no body graphics is transformed as its own rectangle.
    if not base.get('has_body_graphics'):
        bs = base['body']
        cx, cy = bs['x'] + bs['w']/2.0, bs['y'] - bs['h']/2.0
        ncx, ncy = app(cx, cy)
        b.width = clean(max(0.01, bs['w'] * sxv)); b.height = clean(max(0.01, bs['h'] * syv))
        b.rotation = clean((bs.get('rot', 0.0) + angle()) % 360.0)
        try: self._set_body_center_grid(b, ncx, ncy)
        except Exception:
            b.x = ncx - b.width/2.0; b.y = ncy + b.height/2.0
    else:
        _lh_sync_body_model_to_body_graphics(self, u)
    # Attached objects follow the same anchor-local mapping.  Text glyphs remain
    # readable: positions move rigidly, rotations are not mirrored/rotated.
    for pd in base.get('pins', []):
        p = pd['obj']; p.x, p.y = app(pd['x'], pd['y'])
        p.rotation = clean((pd.get('rot',0.0) + angle()) % 360.0)
        p.length = clean(max(0.1, pd.get('length',1.0) * font_factor))
        if pd.get('label') is not None: p.label_x, p.label_y = app(*pd['label'])
        if pd.get('number') is not None: p.number_x, p.number_y = app(*pd['number'])
        try: p.number_font.size_grid = max(0.1, clean(pd.get('nfs', .45) * font_factor))
        except Exception: pass
        try: p.label_font.size_grid = max(0.1, clean(pd.get('lfs', .55) * font_factor))
        except Exception: pass
        for key, tm, tx, ty, trot, tf in pd.get('attrs', []):
            try:
                tm.x, tm.y = app(tx, ty); tm.rotation = trot; tm.font_size_grid = max(0.1, clean(tf * font_factor))
            except Exception: pass
    for td in base.get('texts', []):
        t = td['obj']; t.x, t.y = app(td['x'], td['y']); t.rotation = td.get('rot', 0.0); t.font_size_grid = max(0.1, clean(td.get('font', .75) * font_factor))
    for td in base.get('body_attrs', []):
        t = td['obj']; t.x, t.y = app(td['x'], td['y']); t.rotation = td.get('rot', 0.0); t.font_size_grid = max(0.1, clean(td.get('font', .75) * font_factor))
    try: self._invalidate_body_group_transform_cache(None) if False else None
    except Exception: pass
    if refresh:
        try: self.update_current_unit_canvas_positions()
        except Exception: self.rebuild_scene()
        try: self.rebuild_tree(); self.rebuild_pin_table()
        except Exception: pass


def _lh_body_group_state(self, unit=None):
    u = unit or self.current_unit
    st = getattr(u, '_body_group_transform', None)
    if not isinstance(st, dict) or 'base' not in st or 'M' not in st:
        st = _lh_capture_body_group_base(self, u)
    else:
        try:
            if st['base'].get('origin_mode') != getattr(self.symbol, 'origin', OriginMode.CENTER.value):
                st = _lh_capture_body_group_base(self, u)
        except Exception:
            st = _lh_capture_body_group_base(self, u)
    return st


def _lh_transform_unit_as_body_group(self, op, value=None, refresh=True):
    st = _lh_body_group_state(self, self.current_unit)
    M = st.get('M', (1.0,0.0,0.0,1.0))
    if op == 'rotate':
        deg = round(float(value or 0.0) / 90.0) * 90.0
        if abs(deg) < 1e-9: return
        a = math.radians(deg); Op = (math.cos(a), -math.sin(a), math.sin(a), math.cos(a))
    elif op in ('scale','scale_x_to','scale_y_to'):
        cur_w = max(1e-9, float(getattr(self.current_unit.body, 'width', 1.0) or 1.0))
        cur_h = max(1e-9, float(getattr(self.current_unit.body, 'height', 1.0) or 1.0))
        try: snapv = self._snap_to_edit_grid
        except Exception: snapv = lambda v, mn=0.01: max(mn, float(v))
        if op == 'scale_x_to': sx, sy = snapv(float(value), 0.01) / cur_w, 1.0
        elif op == 'scale_y_to': sx, sy = 1.0, snapv(float(value), 0.01) / cur_h
        else:
            f = float(value or 1.0); sx, sy = snapv(cur_w*f, 0.01)/cur_w, snapv(cur_h*f, 0.01)/cur_h
        Op = (sx, 0.0, 0.0, sy)
    elif op == 'flip_h':
        Op = (-1.0, 0.0, 0.0, 1.0)
    elif op == 'flip_v':
        Op = (1.0, 0.0, 0.0, -1.0)
    else:
        return
    try: st['M'] = self._mat_mul(Op, M)
    except Exception:
        a,b,c,d = Op; e,f,g,h = M; st['M'] = (a*e+b*g, a*f+b*h, c*e+d*g, c*f+d*h)
    _lh_apply_matrix_from_base(self, st, refresh=refresh)


def _lh_reset_origin_to_selected_anchor(self, mode=None):
    mode = mode or (self.origin_combo.currentText() if hasattr(self, 'origin_combo') else OriginMode.CENTER.value)
    if mode not in [x.value for x in OriginMode]: mode = OriginMode.CENTER.value
    try: self.push_undo_state()
    except Exception: pass
    self.symbol.origin = mode
    units = list(getattr(self.symbol, 'units', []) or [self.current_unit]) if not getattr(self, 'is_template_editor', False) else [self.current_unit]
    if not getattr(self, 'is_template_editor', False) and getattr(self.symbol, 'kind', None) != SymbolKind.SPLIT.value:
        units = [self.current_unit]
    for u in units:
        _lh_normalize_unit_origin(self, u, mode)
    if hasattr(self, 'origin_combo'):
        try:
            self.origin_combo.blockSignals(True); self.origin_combo.setCurrentText(mode); self.origin_combo.blockSignals(False)
        except Exception: pass
    try: self.set_format_guide_to_active_origin()
    except Exception: pass
    try: self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()
    except Exception: self.rebuild_scene()


def _lh_load_selected_template(self):
    name = self.current_template_key()
    if not name: return
    self._loading_template = True
    self.unit = self.main.load_template_unit(name); self.symbol.units=[self.unit]
    try: self.unit.body.attributes['TEMPLATE_GRAPHICS_AS_BODY'] = '1'
    except Exception: pass
    try: self._lock_template_body_graphics(self.unit)
    except Exception: pass
    # On opening the Template Editor, the BODY graphics are normalized to the
    # active origin immediately.  Pins/text/attributes keep their offsets and are
    # not allowed to redefine BODY extents.
    try: _lh_normalize_unit_origin(self, self.unit, getattr(self.symbol, 'origin', OriginMode.CENTER.value))
    except Exception: pass
    if hasattr(self, 'origin_combo'):
        self.origin_combo.blockSignals(True); self.origin_combo.setCurrentText(getattr(self.symbol, 'origin', OriginMode.CENTER.value)); self.origin_combo.blockSignals(False)
    try: self.rename_edit.setText(self._split_template_key(name)[1])
    except Exception: pass
    try: self._sync_template_grid_combo_to_unit()
    except Exception: pass
    self._current_template_name = name
    self.rebuild_scene()
    try: self._capture_clean_template_snapshot()
    except Exception: pass
    self._loading_template = False


def _lh_normalize_symbol_origins_for_import(self, symbol):
    mode = getattr(symbol, 'origin', OriginMode.CENTER.value) or OriginMode.CENTER.value
    if mode not in [x.value for x in OriginMode]:
        mode = OriginMode.CENTER.value; symbol.origin = mode
    for unit in getattr(symbol, 'units', []) or []:
        _lh_normalize_unit_origin(self, unit, mode)


def _lh_rebuild_scene_wrapper(orig):
    def wrapper(self, *args, **kwargs):
        try:
            # Keep logical BODY equal to graphics extents before drawing in both editors.
            _lh_sync_body_model_to_body_graphics(self, self.current_unit)
        except Exception:
            pass
        return orig(self, *args, **kwargs)
    return wrapper

# Install monkey patches on both editors.  The classes are already defined at
# this point, so existing UI code resolves the corrected methods dynamically.
try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._sync_imported_body_model_to_body_graphics = _lh_sync_body_model_to_body_graphics
        _cls._body_graphics_bounds = _lh_body_graphics_bounds
        _cls.shift_unit_geometry = _lh_shift_unit_geometry
        _cls.normalize_unit_origin = _lh_normalize_unit_origin
        _cls.normalize_symbol_origins_for_import = _lh_normalize_symbol_origins_for_import
        _cls.dock_pins_to_body = _lh_dock_pins_to_body
        _cls._body_group_capture_base = _lh_capture_body_group_base
        _cls._body_group_state = _lh_body_group_state
        _cls._apply_body_group_matrix_from_base = _lh_apply_matrix_from_base
        _cls._transform_unit_as_body_group = _lh_transform_unit_as_body_group
        _cls.reset_origin_to_selected_anchor = _lh_reset_origin_to_selected_anchor
    TemplateEditorDialog.load_selected_template = _lh_load_selected_template
    MainWindow.rebuild_scene = _lh_rebuild_scene_wrapper(MainWindow.rebuild_scene)
    TemplateEditorDialog.rebuild_scene = _lh_rebuild_scene_wrapper(TemplateEditorDialog.rebuild_scene)
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr final origin/transform normalization patch
# ---------------------------------------------------------------------------
# Rules:
#   * Canvas (0,0) is the only transform pivot.
#   * OriginMode only determines which BODY-graphics anchor is placed on (0,0)
#     when a template/symbol/origin is normalized.
#   * BODY extents are calculated from BODY graphics only. Pins/text/attributes
#     are attached to the body, but never define the BODY bounds.
#   * Rotate/flip/scale transform one rigid symbol group around (0,0). Text
#     positions move with the group, but glyphs remain readable (no mirror/rotate).

try:
    _LH_ORIGIN_VALUES = [x.value for x in OriginMode]
except Exception:
    _LH_ORIGIN_VALUES = ['center', 'bottom_left', 'bottom_right', 'top_left', 'top_right']


def _lh2_clean(self, v):
    try:
        v = round(float(v), 9)
        return 0.0 if abs(v) < 1e-9 else v
    except Exception:
        return v


def _lh2_mat_mul(A, B):
    a, b, c, d = A; e, f, g, h = B
    return (a*e + b*g, a*f + b*h, c*e + d*g, c*f + d*h)


def _lh2_mat_angle(M):
    a, b, c, d = M
    return math.degrees(math.atan2(c, a))


def _lh2_sx(M):
    a, b, c, d = M
    return max(1e-9, math.hypot(a, c))


def _lh2_sy(M):
    a, b, c, d = M
    return max(1e-9, math.hypot(b, d))


def _lh2_apply_pt(M, x, y):
    a, b, c, d = M
    return (a*float(x) + b*float(y), c*float(x) + d*float(y))


def _lh2_is_body_graphic(self, gr):
    try:
        if getattr(self, 'is_template_editor', False):
            return True
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        raw = str(getattr(gr, 'mentor_raw', '') or '')
        if getattr(gr, 'locked_to_body', False):
            return True
        if role in ('body', 'template_body', 'imported_body'):
            return True
        if role == 'user_graphic' or raw == '__USER_GRAPHIC__':
            return False
        # Mentor/imported graphics without explicit user marker are BODY artwork.
        return True
    except Exception:
        return False


def _lh2_body_graphics(self, unit=None):
    u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    return [g for g in (getattr(u, 'graphics', []) or []) if _lh2_is_body_graphic(self, g)] if u else []


def _lh2_rot_local(px, py, cx, cy, deg):
    a = math.radians(float(deg or 0.0)); ca, sa = math.cos(a), math.sin(a)
    dx, dy = float(px) - float(cx), float(py) - float(cy)
    return (cx + ca*dx - sa*dy, cy + sa*dx + ca*dy)


def _lh2_graphic_points(self, gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    shape = str(getattr(gr, 'shape', '') or '')
    if shape in ('line', 'arc'):
        pts = [(x, y), (x + w, y - h)]
        cx, cy = x + w / 2.0, y - h / 2.0
        ctrl_x = getattr(gr, 'ctrl_x', None); ctrl_y = getattr(gr, 'ctrl_y', None)
        if ctrl_x is not None and ctrl_y is not None:
            try: pts.append((x + float(ctrl_x), y - float(ctrl_y)))
            except Exception: pass
        else:
            cr = float(getattr(gr, 'curve_radius', 0.0) or 0.0)
            if abs(cr) > 1e-12:
                pts.append((x + w / 2.0, y - h / 2.0 + cr))
    else:
        pts = [(x, y), (x + w, y), (x + w, y - h), (x, y - h)]
        cx, cy = x + w / 2.0, y - h / 2.0
    sx = float(getattr(gr, 'scale_x', 1.0) or 1.0)
    sy = float(getattr(gr, 'scale_y', 1.0) or 1.0)
    rot = float(getattr(gr, 'rotation', 0.0) or 0.0)
    out = []
    for px, py in pts:
        qx = cx + (px - cx) * sx
        qy = cy + (py - cy) * sy
        out.append(_lh2_rot_local(qx, qy, cx, cy, rot))
    return out


def _lh2_body_graphics_bounds(self, unit=None):
    pts = []
    for gr in _lh2_body_graphics(self, unit):
        pts.extend(_lh2_graphic_points(self, gr))
    if not pts:
        return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    minx, maxx = min(xs), max(xs); miny, maxy = min(ys), max(ys)
    if maxx - minx < 1e-9 or maxy - miny < 1e-9:
        return None
    return (minx, maxy, maxx - minx, maxy - miny)


def _lh2_sync_body_model_to_body_graphics(self, unit=None):
    u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    b = getattr(u, 'body', None) if u else None
    if b is None:
        return
    bounds = _lh2_body_graphics_bounds(self, u)
    if bounds is None:
        return
    x, y, w, h = bounds
    b.x = _lh2_clean(self, x); b.y = _lh2_clean(self, y)
    b.width = _lh2_clean(self, max(0.01, w)); b.height = _lh2_clean(self, max(0.01, h))
    # Imported/template BODY rotation lives in graphics, not in a proxy body box.
    b.rotation = 0.0


def _lh2_anchor_from_body_bounds(self, body, mode):
    mode = mode if mode in _LH_ORIGIN_VALUES else OriginMode.CENTER.value
    x = float(getattr(body, 'x', 0.0) or 0.0)
    y = float(getattr(body, 'y', 0.0) or 0.0)
    w = float(getattr(body, 'width', 0.0) or 0.0)
    h = float(getattr(body, 'height', 0.0) or 0.0)
    if mode == OriginMode.BOTTOM_LEFT.value:
        return x, y - h
    if mode == OriginMode.BOTTOM_RIGHT.value:
        return x + w, y - h
    if mode == OriginMode.TOP_LEFT.value:
        return x, y
    if mode == OriginMode.TOP_RIGHT.value:
        return x + w, y
    return x + w/2.0, y - h/2.0


def _lh2_shift_text_model(tm, dx, dy):
    try:
        tm.x = float(tm.x) + dx; tm.y = float(tm.y) + dy
    except Exception:
        pass


def _lh2_shift_unit_geometry(self, unit, dx, dy):
    b = getattr(unit, 'body', None)
    if b is not None:
        b.x = _lh2_clean(self, float(b.x) + dx); b.y = _lh2_clean(self, float(b.y) + dy)
    for gr in getattr(unit, 'graphics', []) or []:
        gr.x = _lh2_clean(self, float(gr.x) + dx); gr.y = _lh2_clean(self, float(gr.y) + dy)
    for p in getattr(unit, 'pins', []) or []:
        p.x = _lh2_clean(self, float(p.x) + dx); p.y = _lh2_clean(self, float(p.y) + dy)
        if getattr(p, 'label_x', None) is not None: p.label_x = _lh2_clean(self, float(p.label_x) + dx)
        if getattr(p, 'label_y', None) is not None: p.label_y = _lh2_clean(self, float(p.label_y) + dy)
        if getattr(p, 'number_x', None) is not None: p.number_x = _lh2_clean(self, float(p.number_x) + dx)
        if getattr(p, 'number_y', None) is not None: p.number_y = _lh2_clean(self, float(p.number_y) + dy)
        for tm in (getattr(p, 'attribute_texts', {}) or {}).values():
            _lh2_shift_text_model(tm, dx, dy)
    for tm in getattr(unit, 'texts', []) or []:
        _lh2_shift_text_model(tm, dx, dy)
    for tm in (getattr(getattr(unit, 'body', None), 'attribute_texts', {}) or {}).values():
        _lh2_shift_text_model(tm, dx, dy)
    try: _lh2_sync_body_model_to_body_graphics(self, unit)
    except Exception: pass
    try:
        if hasattr(unit, '_body_group_transform'):
            delattr(unit, '_body_group_transform')
    except Exception:
        pass


def _lh2_normalize_unit_origin(self, unit, mode):
    # Move the selected BODY anchor to canvas origin. Only BODY graphics define
    # the body bounds; attached objects are shifted by the exact same delta.
    _lh2_sync_body_model_to_body_graphics(self, unit)
    b = getattr(unit, 'body', None)
    if b is None:
        return
    ax, ay = _lh2_anchor_from_body_bounds(self, b, mode)
    if abs(ax) > 1e-9 or abs(ay) > 1e-9:
        _lh2_shift_unit_geometry(self, unit, -ax, -ay)
    _lh2_sync_body_model_to_body_graphics(self, unit)


def _lh2_capture_base(self, unit=None):
    u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    _lh2_sync_body_model_to_body_graphics(self, u)
    b = u.body
    base = {
        'unit_id': id(u),
        'origin_mode': getattr(self.symbol, 'origin', OriginMode.CENTER.value),
        'pivot': (0.0, 0.0),
        'has_body_graphics': bool(_lh2_body_graphics(self, u)),
        'body': {'x': float(b.x), 'y': float(b.y), 'w': float(b.width), 'h': float(b.height), 'rot': float(getattr(b, 'rotation', 0.0) or 0.0)},
        'graphics': [], 'pins': [], 'texts': [], 'body_attrs': []
    }
    for gr in getattr(u, 'graphics', []) or []:
        base['graphics'].append({
            'obj': gr, 'shape': str(getattr(gr, 'shape', '') or ''),
            'x': float(getattr(gr, 'x', 0.0) or 0.0), 'y': float(getattr(gr, 'y', 0.0) or 0.0),
            'w': float(getattr(gr, 'w', 0.0) or 0.0), 'h': float(getattr(gr, 'h', 0.0) or 0.0),
            'rot': float(getattr(gr, 'rotation', 0.0) or 0.0),
            'sx': float(getattr(gr, 'scale_x', 1.0) or 1.0), 'sy': float(getattr(gr, 'scale_y', 1.0) or 1.0),
            'ctrl_x': getattr(gr, 'ctrl_x', None), 'ctrl_y': getattr(gr, 'ctrl_y', None),
            'curve_radius': float(getattr(gr, 'curve_radius', 0.0) or 0.0),
        })
    for p in getattr(u, 'pins', []) or []:
        pd = {'obj': p, 'x': float(p.x), 'y': float(p.y), 'length': float(getattr(p, 'length', 1.0) or 1.0),
              'rot': float(getattr(p, 'rotation', 0.0) or 0.0), 'side': getattr(p, 'side', ''),
              'label': None, 'number': None, 'attrs': [],
              'nfs': float(getattr(getattr(p, 'number_font', None), 'size_grid', 0.45) or 0.45),
              'lfs': float(getattr(getattr(p, 'label_font', None), 'size_grid', 0.55) or 0.55)}
        if getattr(p, 'label_x', None) is not None and getattr(p, 'label_y', None) is not None:
            pd['label'] = (float(p.label_x), float(p.label_y))
        if getattr(p, 'number_x', None) is not None and getattr(p, 'number_y', None) is not None:
            pd['number'] = (float(p.number_x), float(p.number_y))
        for key, tm in (getattr(p, 'attribute_texts', {}) or {}).items():
            try: pd['attrs'].append((key, tm, float(tm.x), float(tm.y), float(getattr(tm, 'rotation', 0.0) or 0.0), float(getattr(tm, 'font_size_grid', 0.55) or 0.55)))
            except Exception: pass
        base['pins'].append(pd)
    for tm in getattr(u, 'texts', []) or []:
        try: base['texts'].append({'obj': tm, 'x': float(tm.x), 'y': float(tm.y), 'rot': float(getattr(tm, 'rotation', 0.0) or 0.0), 'font': float(getattr(tm, 'font_size_grid', .75) or .75)})
        except Exception: pass
    for key, tm in (getattr(b, 'attribute_texts', {}) or {}).items():
        try: base['body_attrs'].append({'key': key, 'obj': tm, 'x': float(tm.x), 'y': float(tm.y), 'rot': float(getattr(tm, 'rotation', 0.0) or 0.0), 'font': float(getattr(tm, 'font_size_grid', .75) or .75)})
        except Exception: pass
    u._body_group_transform = {'base': base, 'M': (1.0, 0.0, 0.0, 1.0)}
    return u._body_group_transform


def _lh2_body_group_state(self, unit=None):
    u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    st = getattr(u, '_body_group_transform', None)
    mode = getattr(self.symbol, 'origin', OriginMode.CENTER.value)
    if not isinstance(st, dict) or 'base' not in st or 'M' not in st or st['base'].get('unit_id') != id(u) or st['base'].get('origin_mode') != mode:
        st = _lh2_capture_base(self, u)
    return st


def _lh2_graphic_set_from_base(self, gd, M):
    gr = gd['obj']; shape = gd.get('shape') or str(getattr(gr, 'shape', '') or '')
    sxv, syv = _lh2_sx(M), _lh2_sy(M)
    ang = _lh2_mat_angle(M)
    clean = lambda v: _lh2_clean(self, v)
    if shape in ('line', 'arc'):
        x1, y1 = _lh2_apply_pt(M, gd['x'], gd['y'])
        x2, y2 = _lh2_apply_pt(M, gd['x'] + gd['w'], gd['y'] - gd['h'])
        gr.x, gr.y = clean(x1), clean(y1)
        gr.w, gr.h = clean(x2 - x1), clean(y1 - y2)
        gr.rotation = 0.0; gr.scale_x = 1.0; gr.scale_y = 1.0
        if gd.get('ctrl_x') is not None and gd.get('ctrl_y') is not None:
            cx, cy = _lh2_apply_pt(M, gd['x'] + float(gd['ctrl_x']), gd['y'] - float(gd['ctrl_y']))
            gr.ctrl_x, gr.ctrl_y = clean(cx - x1), clean(y1 - cy)
        try:
            gr.curve_radius = clean(float(gd.get('curve_radius', 0.0) or 0.0) * max(sxv, syv))
        except Exception:
            pass
    else:
        cx, cy = gd['x'] + gd['w'] / 2.0, gd['y'] - gd['h'] / 2.0
        ncx, ncy = _lh2_apply_pt(M, cx, cy)
        gr.w = clean(abs(gd['w']) * sxv); gr.h = clean(abs(gd['h']) * syv)
        gr.x = clean(ncx - gr.w / 2.0); gr.y = clean(ncy + gr.h / 2.0)
        # Rect/ellipse orientation is represented by item rotation. Mirror is
        # represented with scale signs so the visual object is transformed, while
        # text objects are deliberately not mirrored.
        gr.rotation = clean((float(gd.get('rot', 0.0) or 0.0) + ang) % 360.0)
        # Detect reflection roughly by determinant sign. Use one negative scale
        # to mirror the graphic without adding a proxy frame.
        a, b, c, d = M; det = a*d - b*c
        gr.scale_x = -float(gd.get('sx', 1.0) or 1.0) if det < 0 else float(gd.get('sx', 1.0) or 1.0)
        gr.scale_y = float(gd.get('sy', 1.0) or 1.0)


def _lh2_apply_body_group_matrix_from_base(self, st, refresh=True):
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    if u is None:
        return
    base = st['base']; M = st.get('M', (1.0, 0.0, 0.0, 1.0))
    clean = lambda v: _lh2_clean(self, v)
    sxv, syv = _lh2_sx(M), _lh2_sy(M)
    font_factor = max(0.1, (abs(sxv) + abs(syv)) / 2.0)
    angle = _lh2_mat_angle(M)

    # Real graphics first. For imported/templates, BODY is the body graphics.
    for gd in base.get('graphics', []):
        _lh2_graphic_set_from_base(self, gd, M)

    b = u.body
    if not base.get('has_body_graphics'):
        # Internal <NONE> body as a real body object.
        bs = base['body']
        cx, cy = bs['x'] + bs['w']/2.0, bs['y'] - bs['h']/2.0
        ncx, ncy = _lh2_apply_pt(M, cx, cy)
        b.width = clean(max(0.01, abs(bs['w']) * sxv)); b.height = clean(max(0.01, abs(bs['h']) * syv))
        b.x = clean(ncx - b.width / 2.0); b.y = clean(ncy + b.height / 2.0)
        b.rotation = clean((bs.get('rot', 0.0) + angle) % 360.0)
    else:
        _lh2_sync_body_model_to_body_graphics(self, u)

    # Attached pins/text/attrs follow the same rigid group matrix around (0,0).
    for pd in base.get('pins', []):
        p = pd['obj']; nx, ny = _lh2_apply_pt(M, pd['x'], pd['y'])
        p.x, p.y = clean(nx), clean(ny)
        # Pin line orientation follows the symbol; pin text remains readable.
        p.rotation = clean((pd.get('rot', 0.0) + angle) % 360.0)
        p.length = clean(max(0.1, float(pd.get('length', 1.0) or 1.0) * font_factor))
        if pd.get('label') is not None:
            lx, ly = _lh2_apply_pt(M, *pd['label']); p.label_x, p.label_y = clean(lx), clean(ly)
        if pd.get('number') is not None:
            nx, ny = _lh2_apply_pt(M, *pd['number']); p.number_x, p.number_y = clean(nx), clean(ny)
        try: p.number_font.size_grid = max(0.1, clean(pd.get('nfs', .45) * font_factor))
        except Exception: pass
        try: p.label_font.size_grid = max(0.1, clean(pd.get('lfs', .55) * font_factor))
        except Exception: pass
        for key, tm, tx, ty, trot, tf in pd.get('attrs', []):
            try:
                qx, qy = _lh2_apply_pt(M, tx, ty); tm.x, tm.y = clean(qx), clean(qy)
                tm.rotation = trot  # readable: do not rotate/mirror glyphs
                tm.scale_x = 1.0; tm.scale_y = 1.0
                tm.font_size_grid = max(0.1, clean(tf * font_factor))
            except Exception:
                pass
    for td in base.get('texts', []):
        t = td['obj']; qx, qy = _lh2_apply_pt(M, td['x'], td['y'])
        t.x, t.y = clean(qx), clean(qy); t.rotation = td.get('rot', 0.0); t.scale_x = 1.0; t.scale_y = 1.0
        t.font_size_grid = max(0.1, clean(td.get('font', .75) * font_factor))
    for td in base.get('body_attrs', []):
        t = td['obj']; qx, qy = _lh2_apply_pt(M, td['x'], td['y'])
        t.x, t.y = clean(qx), clean(qy); t.rotation = td.get('rot', 0.0); t.scale_x = 1.0; t.scale_y = 1.0
        t.font_size_grid = max(0.1, clean(td.get('font', .75) * font_factor))

    if refresh:
        try:
            self.update_current_unit_canvas_positions()
        except Exception:
            try: self.rebuild_scene()
            except Exception: pass
        try:
            self.rebuild_tree(); self.rebuild_pin_table()
        except Exception:
            pass


def _lh2_snap_edit(self, v, mn=0.01):
    try:
        return self._snap_to_edit_grid(v, mn)
    except Exception:
        try:
            step = self._edit_grid_step()
            return max(mn, round(float(v) / step) * step)
        except Exception:
            return max(mn, float(v))


def _lh2_transform_unit_as_body_group(self, op, value=None, refresh=True):
    st = _lh2_body_group_state(self, getattr(self, 'current_unit', None) or getattr(self, 'unit', None))
    M = st.get('M', (1.0, 0.0, 0.0, 1.0))
    if op == 'rotate':
        deg = round(float(value or 0.0) / 90.0) * 90.0
        if abs(deg) < 1e-9:
            return
        a = math.radians(deg)
        Op = (math.cos(a), -math.sin(a), math.sin(a), math.cos(a))
    elif op == 'flip_h':
        # Mirror at y-axis of canvas coordinate system, origin stays (0,0).
        Op = (-1.0, 0.0, 0.0, 1.0)
    elif op == 'flip_v':
        # Mirror at x-axis of canvas coordinate system, origin stays (0,0).
        Op = (1.0, 0.0, 0.0, -1.0)
    elif op in ('scale', 'scale_x_to', 'scale_y_to'):
        u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
        _lh2_sync_body_model_to_body_graphics(self, u)
        cur_w = max(1e-9, float(getattr(u.body, 'width', 1.0) or 1.0))
        cur_h = max(1e-9, float(getattr(u.body, 'height', 1.0) or 1.0))
        if op == 'scale_x_to':
            sx, sy = _lh2_snap_edit(self, float(value), 0.01) / cur_w, 1.0
        elif op == 'scale_y_to':
            sx, sy = 1.0, _lh2_snap_edit(self, float(value), 0.01) / cur_h
        else:
            f = float(value or 1.0)
            sx = _lh2_snap_edit(self, cur_w * f, 0.01) / cur_w
            sy = _lh2_snap_edit(self, cur_h * f, 0.01) / cur_h
        Op = (sx, 0.0, 0.0, sy)
    else:
        return
    st['M'] = _lh2_mat_mul(Op, M)
    _lh2_apply_body_group_matrix_from_base(self, st, refresh=refresh)


def _lh2_reset_origin_to_selected_anchor(self, mode=None):
    mode = mode or (self.origin_combo.currentText() if hasattr(self, 'origin_combo') else OriginMode.CENTER.value)
    if mode not in _LH_ORIGIN_VALUES:
        mode = OriginMode.CENTER.value
    try: self.push_undo_state()
    except Exception: pass
    self.symbol.origin = mode
    units = [getattr(self, 'current_unit', None) or getattr(self, 'unit', None)]
    if not getattr(self, 'is_template_editor', False) and getattr(self.symbol, 'kind', None) == SymbolKind.SPLIT.value:
        units = list(getattr(self.symbol, 'units', []) or units)
    for u in [x for x in units if x is not None]:
        _lh2_normalize_unit_origin(self, u, mode)
    if hasattr(self, 'origin_combo'):
        try:
            self.origin_combo.blockSignals(True); self.origin_combo.setCurrentText(mode); self.origin_combo.blockSignals(False)
        except Exception: pass
    try: self.set_format_guide_to_active_origin()
    except Exception: pass
    try: self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()
    except Exception:
        try: self.rebuild_scene()
        except Exception: pass


def _lh2_normalize_symbol_origins_for_import(self, symbol):
    mode = getattr(symbol, 'origin', OriginMode.CENTER.value) or OriginMode.CENTER.value
    if mode not in _LH_ORIGIN_VALUES:
        mode = OriginMode.CENTER.value; symbol.origin = mode
    for u in getattr(symbol, 'units', []) or []:
        _lh2_normalize_unit_origin(self, u, mode)


def _lh2_invalidate_body_group_transform_cache(self, unit=None):
    try:
        if unit is None:
            for u in getattr(self.symbol, 'units', []) or []:
                if hasattr(u, '_body_group_transform'):
                    delattr(u, '_body_group_transform')
        elif hasattr(unit, '_body_group_transform'):
            delattr(unit, '_body_group_transform')
    except Exception:
        pass


def _lh2_body_owned_graphics(self, body):
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    return _lh2_body_graphics(self, u)


def _lh2_set_body_visual_attr(self, body, attr, value):
    if attr not in ('line_style', 'line_width', 'color'):
        return
    try: self.push_undo_state()
    except Exception: pass
    setattr(body, attr, value)
    for gr in _lh2_body_owned_graphics(self, body):
        st = getattr(gr, 'style', None)
        if st is None: continue
        if attr == 'line_style': st.line_style = value
        elif attr == 'line_width': st.line_width = float(value)
        elif attr == 'color': st.stroke = tuple(value)
    try: _lh2_invalidate_body_group_transform_cache(self, getattr(self, 'current_unit', None) or getattr(self, 'unit', None))
    except Exception: pass
    try: self.update_current_unit_canvas_positions()
    except Exception: pass
    try: self.schedule_scene_refresh(visual_only=True)
    except Exception: self.rebuild_scene()


def _lh2_color_body_model(self, body):
    c = QColorDialog.getColor(QColor(*getattr(body, 'color', (0,0,0))), self)
    if c.isValid():
        _lh2_set_body_visual_attr(self, body, 'color', (c.red(), c.green(), c.blue()))


def _lh2_load_selected_template(self):
    name = self.current_template_key()
    if not name:
        return
    self._loading_template = True
    self.unit = self.main.load_template_unit(name); self.symbol.units = [self.unit]
    try: self.unit.body.attributes['TEMPLATE_GRAPHICS_AS_BODY'] = '1'
    except Exception: pass
    try: self._lock_template_body_graphics(self.unit)
    except Exception: pass
    try: _lh2_normalize_unit_origin(self, self.unit, getattr(self.symbol, 'origin', OriginMode.CENTER.value))
    except Exception: pass
    if hasattr(self, 'origin_combo'):
        try:
            self.origin_combo.blockSignals(True); self.origin_combo.setCurrentText(getattr(self.symbol, 'origin', OriginMode.CENTER.value)); self.origin_combo.blockSignals(False)
        except Exception: pass
    try: self.rename_edit.setText(self._split_template_key(name)[1])
    except Exception: pass
    try: self._sync_template_grid_combo_to_unit()
    except Exception: pass
    self._current_template_name = name
    self.rebuild_scene()
    try: self._capture_clean_template_snapshot()
    except Exception: pass
    self._loading_template = False


def _lh2_rebuild_scene_wrapper(orig):
    def wrapper(self, *args, **kwargs):
        try: _lh2_sync_body_model_to_body_graphics(self, getattr(self, 'current_unit', None) or getattr(self, 'unit', None))
        except Exception: pass
        return orig(self, *args, **kwargs)
    return wrapper

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._sync_imported_body_model_to_body_graphics = _lh2_sync_body_model_to_body_graphics
        _cls._body_graphics_bounds = _lh2_body_graphics_bounds
        _cls._body_graphics = _lh2_body_graphics
        _cls.shift_unit_geometry = _lh2_shift_unit_geometry
        _cls.normalize_unit_origin = _lh2_normalize_unit_origin
        _cls.normalize_symbol_origins_for_import = _lh2_normalize_symbol_origins_for_import
        _cls._invalidate_body_group_transform_cache = _lh2_invalidate_body_group_transform_cache
        _cls._body_owned_graphics = _lh2_body_owned_graphics
        _cls._body_group_capture_base = _lh2_capture_base
        _cls._body_group_state = _lh2_body_group_state
        _cls._apply_body_group_matrix_from_base = _lh2_apply_body_group_matrix_from_base
        _cls._transform_unit_as_body_group = _lh2_transform_unit_as_body_group
        _cls.reset_origin_to_selected_anchor = _lh2_reset_origin_to_selected_anchor
        _cls.set_body_visual_attr = _lh2_set_body_visual_attr
        _cls.color_body_model = _lh2_color_body_model
    TemplateEditorDialog.load_selected_template = _lh2_load_selected_template
    MainWindow.rebuild_scene = _lh2_rebuild_scene_wrapper(MainWindow.rebuild_scene)
    TemplateEditorDialog.rebuild_scene = _lh2_rebuild_scene_wrapper(TemplateEditorDialog.rebuild_scene)
except Exception:
    pass


# ---------------------------------------------------------------------------
# Liebherr step: imported BODY artwork is the BODY, no proxy rectangle
# ---------------------------------------------------------------------------
def _lh3_selected_body_active(self):
    try:
        return any(getattr(i, 'data', lambda *_: None)(0) in ('BODY', 'BODY_GRAPHIC') for i in self.scene.selectedItems())
    except Exception:
        return False

def _lh3_capture_selection_ids(self):
    ids = set()
    try:
        for i in self.scene.selectedItems():
            if getattr(i, 'data', lambda *_: None)(0) == 'BODY_GRAPHIC':
                bm = getattr(i, '_body_model', None)
                if bm is not None:
                    ids.add(id(bm)); continue
            m = getattr(i, 'model', None)
            if m is not None:
                ids.add(id(m))
    except Exception:
        pass
    return ids

try:
    MainWindow._selected_body_active = _lh3_selected_body_active
    MainWindow._capture_selection_ids = _lh3_capture_selection_ids
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr step 2: imported/template BODY graphics use the native Symbol-1
# BODY transform pipeline.  If a unit has BODY graphics, mark them as the BODY
# before scene construction, select BODY through the artwork, and route rotate /
# flip / scale to the real graphics + all attached objects.
# ---------------------------------------------------------------------------
def _lh4_unit_has_imported_body_artwork(self, unit=None):
    u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    if u is None:
        return False
    try:
        return bool(_lh2_body_graphics(self, u))
    except Exception:
        try:
            return any(getattr(g, 'locked_to_body', False) for g in (getattr(u, 'graphics', []) or []))
        except Exception:
            return False


def _lh4_prepare_graphics_as_body(self, unit=None):
    u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    if u is None or getattr(u, 'body', None) is None:
        return
    if not _lh4_unit_has_imported_body_artwork(self, u):
        return
    attrs = getattr(u.body, 'attributes', None)
    if attrs is None:
        try:
            u.body.attributes = {}; attrs = u.body.attributes
        except Exception:
            return
    # This is only a semantic marker for the renderer/property panel.  It does
    # not create a proxy rectangle.  BODY bounds remain derived from graphics.
    attrs['MENTOR_GRAPHICS_AS_BODY'] = '1'
    attrs['MENTOR_BODY_GRAPHICS_LOCKED'] = '1'
    for g in getattr(u, 'graphics', []) or []:
        try:
            if _lh2_is_body_graphic(self, g):
                g.locked_to_body = True
                if not str(getattr(g, 'graphic_role', '') or ''):
                    g.graphic_role = 'imported_body'
        except Exception:
            pass
    try:
        _lh2_sync_body_model_to_body_graphics(self, u)
    except Exception:
        pass


def _lh4_selected_body_active(self):
    try:
        for i in self.scene.selectedItems():
            k = getattr(i, 'data', lambda *_: None)(0)
            if k in ('BODY', 'BODY_GRAPHIC'):
                return True
            m = getattr(i, 'model', None)
            if m is not None and _lh2_is_body_graphic(self, m):
                return True
    except Exception:
        pass
    return False


def _lh4_rotate_selected(self, deg):
    self.set_tool(DrawTool.SELECT.value)
    try: self.push_undo_state()
    except Exception: pass
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    _lh4_prepare_graphics_as_body(self, u)
    if _lh4_selected_body_active(self):
        _lh2_transform_unit_as_body_group(self, 'rotate', float(deg))
    else:
        for it in self.scene.selectedItems():
            if hasattr(it, 'rotate_by'):
                it.rotate_by(float(deg))
        try: self.schedule_scene_refresh()
        except Exception: self.rebuild_scene()
    self.dirty = True


def _lh4_flip_selected_horizontal(self):
    self.set_tool(DrawTool.SELECT.value)
    try: self.push_undo_state()
    except Exception: pass
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    _lh4_prepare_graphics_as_body(self, u)
    if _lh4_selected_body_active(self):
        _lh2_transform_unit_as_body_group(self, 'flip_h')
    else:
        for it in self.scene.selectedItems():
            if hasattr(it, 'flip_horizontal'):
                it.flip_horizontal()
        try: self.schedule_scene_refresh()
        except Exception: self.rebuild_scene()
    self.dirty = True


def _lh4_flip_selected_vertical(self):
    self.set_tool(DrawTool.SELECT.value)
    try: self.push_undo_state()
    except Exception: pass
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    _lh4_prepare_graphics_as_body(self, u)
    if _lh4_selected_body_active(self):
        _lh2_transform_unit_as_body_group(self, 'flip_v')
    else:
        for it in self.scene.selectedItems():
            if hasattr(it, 'flip_vertical'):
                it.flip_vertical()
        try: self.schedule_scene_refresh()
        except Exception: self.rebuild_scene()
    self.dirty = True


def _lh4_scale_selected(self, factor):
    self.set_tool(DrawTool.SELECT.value)
    try: self.push_undo_state()
    except Exception: pass
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    _lh4_prepare_graphics_as_body(self, u)
    if _lh4_selected_body_active(self):
        _lh2_transform_unit_as_body_group(self, 'scale', float(factor))
    else:
        for it in self.scene.selectedItems():
            if hasattr(it, 'scale_by'):
                it.scale_by(float(factor))
            elif hasattr(it, 'scale_selected'):
                it.scale_selected(float(factor))
        try: self.schedule_scene_refresh()
        except Exception: self.rebuild_scene()
    self.dirty = True


def _lh4_rebuild_scene_wrapper(orig):
    def wrapper(self, *args, **kwargs):
        try:
            _lh4_prepare_graphics_as_body(self, getattr(self, 'current_unit', None) or getattr(self, 'unit', None))
        except Exception:
            pass
        return orig(self, *args, **kwargs)
    return wrapper

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._unit_has_imported_body_artwork = _lh4_unit_has_imported_body_artwork
        _cls._prepare_graphics_as_body = _lh4_prepare_graphics_as_body
        _cls._selected_body_active = _lh4_selected_body_active
        _cls.rotate_selected = _lh4_rotate_selected
        _cls.flip_selected_horizontal = _lh4_flip_selected_horizontal
        _cls.flip_selected_vertical = _lh4_flip_selected_vertical
        _cls.scale_selected = _lh4_scale_selected
    MainWindow.rebuild_scene = _lh4_rebuild_scene_wrapper(MainWindow.rebuild_scene)
    TemplateEditorDialog.rebuild_scene = _lh4_rebuild_scene_wrapper(TemplateEditorDialog.rebuild_scene)
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr final transform fix: BODY graphics are transformed as real objects;
# Flip H/V use canvas axes; text is only moved, never mirrored/rotated.
# This override deliberately avoids the old proxy/base-stack path.
# ---------------------------------------------------------------------------
def _lh5_clean(self, v):
    try:
        v = round(float(v), 9)
        return 0.0 if abs(v) < 1e-9 else v
    except Exception:
        return v


def _lh5_apply_op_point(op, x, y):
    x = float(x); y = float(y)
    typ = op[0]
    if typ == 'rotate':
        deg = float(op[1])
        # Only 90° steps are allowed here. Use exact matrices to avoid drift.
        d = int(round(deg / 90.0)) % 4
        if d == 0: return x, y
        if d == 1: return -y, x
        if d == 2: return -x, -y
        return y, -x
    if typ == 'flip_h':      # mirror at Y-axis: x -> -x
        return -x, y
    if typ == 'flip_v':      # mirror at X-axis: y -> -y
        return x, -y
    if typ == 'scale':
        sx, sy = float(op[1]), float(op[2])
        return x * sx, y * sy
    return x, y


def _lh5_transform_angle(angle, op):
    """Transform a non-text object's orientation angle by the operation."""
    try:
        a = float(angle or 0.0)
    except Exception:
        a = 0.0
    typ = op[0]
    if typ == 'rotate':
        return (a + float(op[1])) % 360.0
    if typ == 'flip_h':
        return (180.0 - a) % 360.0
    if typ == 'flip_v':
        return (-a) % 360.0
    return a % 360.0


def _lh5_text_readable(tm):
    """Text must stay readable: no negative scale and no transform rotation."""
    try: tm.scale_x = 1.0
    except Exception: pass
    try: tm.scale_y = 1.0
    except Exception: pass
    # Keep already user-defined text rotation if it exists, but never add flip/rotate.
    try:
        r = float(getattr(tm, 'rotation', 0.0) or 0.0)
        # Imported pin/body attribute labels in this tool are expected horizontal.
        # Normalize accidental 180/negative mirror rotations back to a readable 0°.
        if abs((r % 360.0) - 180.0) < 1e-6 or abs((r % 360.0) - 360.0) < 1e-6:
            tm.rotation = 0.0
    except Exception:
        pass


def _lh5_transform_text_model(self, tm, op, font_factor=1.0):
    if tm is None: return
    try:
        tm.x, tm.y = (_lh5_clean(self, v) for v in _lh5_apply_op_point(op, tm.x, tm.y))
    except Exception:
        pass
    _lh5_text_readable(tm)
    try:
        tm.font_size_grid = max(0.1, _lh5_clean(self, float(getattr(tm, 'font_size_grid', 0.75) or 0.75) * float(font_factor)))
    except Exception:
        pass


def _lh5_transform_graphic(self, gr, op):
    if gr is None: return
    shape = str(getattr(gr, 'shape', '') or '')
    try:
        if shape in ('line', 'arc'):
            x1, y1 = float(gr.x), float(gr.y)
            x2, y2 = float(gr.x) + float(getattr(gr, 'w', 0.0) or 0.0), float(gr.y) - float(getattr(gr, 'h', 0.0) or 0.0)
            nx1, ny1 = _lh5_apply_op_point(op, x1, y1)
            nx2, ny2 = _lh5_apply_op_point(op, x2, y2)
            old_ctrl_x, old_ctrl_y = getattr(gr, 'ctrl_x', None), getattr(gr, 'ctrl_y', None)
            gr.x, gr.y = _lh5_clean(self, nx1), _lh5_clean(self, ny1)
            gr.w, gr.h = _lh5_clean(self, nx2 - nx1), _lh5_clean(self, ny1 - ny2)
            gr.rotation = 0.0
            gr.scale_x = 1.0; gr.scale_y = 1.0
            if old_ctrl_x is not None and old_ctrl_y is not None:
                try:
                    cx, cy = _lh5_apply_op_point(op, x1 + float(old_ctrl_x), y1 - float(old_ctrl_y))
                    gr.ctrl_x = _lh5_clean(self, cx - nx1)
                    gr.ctrl_y = _lh5_clean(self, ny1 - cy)
                except Exception:
                    pass
            # curve_radius is a local distance; keep sign under rotation, mirror it under one-axis flips.
            try:
                if op[0] in ('flip_h', 'flip_v'):
                    gr.curve_radius = _lh5_clean(self, -float(getattr(gr, 'curve_radius', 0.0) or 0.0))
                elif op[0] == 'scale':
                    gr.curve_radius = _lh5_clean(self, float(getattr(gr, 'curve_radius', 0.0) or 0.0) * max(abs(float(op[1])), abs(float(op[2]))))
            except Exception:
                pass
        else:
            # Rect/ellipse/circle: transform center and orientation.  Keep glyph-free geometry mirrored/rotated.
            x = float(getattr(gr, 'x', 0.0) or 0.0); y = float(getattr(gr, 'y', 0.0) or 0.0)
            w = float(getattr(gr, 'w', 0.0) or 0.0); h = float(getattr(gr, 'h', 0.0) or 0.0)
            cx, cy = x + w/2.0, y - h/2.0
            ncx, ncy = _lh5_apply_op_point(op, cx, cy)
            if op[0] == 'scale':
                w, h = abs(w * float(op[1])), abs(h * float(op[2]))
            # For 90° rotations keep model w/h and use model.rotation. This matches GraphicItem.
            gr.x, gr.y = _lh5_clean(self, ncx - w/2.0), _lh5_clean(self, ncy + h/2.0)
            gr.w, gr.h = _lh5_clean(self, w), _lh5_clean(self, h)
            gr.rotation = _lh5_clean(self, _lh5_transform_angle(getattr(gr, 'rotation', 0.0), op))
            gr.scale_x = float(getattr(gr, 'scale_x', 1.0) or 1.0)
            gr.scale_y = float(getattr(gr, 'scale_y', 1.0) or 1.0)
            if op[0] == 'flip_h':
                gr.scale_x = -gr.scale_x
            elif op[0] == 'flip_v':
                gr.scale_y = -gr.scale_y
    except Exception:
        pass


def _lh5_transform_body_rect(self, b, op):
    if b is None: return
    try:
        x, y, w, h = float(b.x), float(b.y), float(b.width), float(b.height)
        cx, cy = x + w/2.0, y - h/2.0
        ncx, ncy = _lh5_apply_op_point(op, cx, cy)
        if op[0] == 'scale':
            w, h = abs(w * float(op[1])), abs(h * float(op[2]))
        b.x, b.y = _lh5_clean(self, ncx - w/2.0), _lh5_clean(self, ncy + h/2.0)
        b.width, b.height = _lh5_clean(self, max(0.01, w)), _lh5_clean(self, max(0.01, h))
        b.rotation = _lh5_clean(self, _lh5_transform_angle(getattr(b, 'rotation', 0.0), op))
        if op[0] == 'flip_h':
            b.scale_x = -float(getattr(b, 'scale_x', 1.0) or 1.0)
        elif op[0] == 'flip_v':
            b.scale_y = -float(getattr(b, 'scale_y', 1.0) or 1.0)
    except Exception:
        pass


def _lh5_body_graphics(self, unit):
    try:
        return _lh2_body_graphics(self, unit)
    except Exception:
        out=[]
        for g in getattr(unit, 'graphics', []) or []:
            role = str(getattr(g, 'graphic_role', '') or '').lower()
            raw = str(getattr(g, 'mentor_raw', '') or '')
            if getattr(g, 'locked_to_body', False) or role in ('body','template_body','imported_body') or (raw != '__USER_GRAPHIC__' and role != 'user_graphic'):
                out.append(g)
        return out


def _lh5_transform_unit_as_body_group(self, op_name, value=None, refresh=True):
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    if u is None or getattr(u, 'body', None) is None:
        return
    # Build exact operation around the canvas origin (0,0).
    if op_name == 'rotate':
        deg = round(float(value or 0.0) / 90.0) * 90.0
        if abs(deg) < 1e-9: return
        op = ('rotate', deg)
    elif op_name == 'flip_h':
        op = ('flip_h',)
    elif op_name == 'flip_v':
        op = ('flip_v',)
    elif op_name in ('scale', 'scale_x_to', 'scale_y_to'):
        try: _lh2_sync_body_model_to_body_graphics(self, u)
        except Exception: pass
        cur_w = max(1e-9, float(getattr(u.body, 'width', 1.0) or 1.0))
        cur_h = max(1e-9, float(getattr(u.body, 'height', 1.0) or 1.0))
        try: snap = self._snap_to_edit_grid
        except Exception: snap = lambda vv, mn=0.01: max(mn, float(vv))
        if op_name == 'scale_x_to':
            sx = float(snap(float(value), 0.01)) / cur_w; sy = 1.0
        elif op_name == 'scale_y_to':
            sx = 1.0; sy = float(snap(float(value), 0.01)) / cur_h
        else:
            f = float(value or 1.0)
            sx = float(snap(cur_w * f, 0.01)) / cur_w
            sy = float(snap(cur_h * f, 0.01)) / cur_h
        op = ('scale', sx, sy)
    else:
        return
    font_factor = 1.0
    if op[0] == 'scale':
        font_factor = max(0.1, (abs(float(op[1])) + abs(float(op[2]))) / 2.0)

    # BODY: imported/template graphics are the BODY. Internal <NONE> uses BodyModel.
    body_graphics = _lh5_body_graphics(self, u)
    if body_graphics:
        for gr in body_graphics:
            _lh5_transform_graphic(self, gr, op)
        try: _lh2_sync_body_model_to_body_graphics(self, u)
        except Exception:
            try: self._sync_body_model_to_body_bounds_only(u)
            except Exception: pass
        # Keep logical proxy rotation neutral for imported artwork; visual rotation is in graphics.
        try: u.body.rotation = 0.0
        except Exception: pass
    else:
        _lh5_transform_body_rect(self, u.body, op)

    # User/free graphics are attached to the symbol too, but not part of BODY bounds.
    for gr in getattr(u, 'graphics', []) or []:
        if gr not in body_graphics:
            _lh5_transform_graphic(self, gr, op)

    # Pins and pin-owned text.
    for p in getattr(u, 'pins', []) or []:
        try:
            p.x, p.y = (_lh5_clean(self, v) for v in _lh5_apply_op_point(op, p.x, p.y))
            p.rotation = _lh5_clean(self, _lh5_transform_angle(getattr(p, 'rotation', 0.0), op))
            if op[0] == 'scale':
                p.length = max(0.1, _lh5_clean(self, float(getattr(p, 'length', 1.0) or 1.0) * font_factor))
        except Exception: pass
        for ax, ay in (('label_x','label_y'), ('number_x','number_y')):
            if getattr(p, ax, None) is not None and getattr(p, ay, None) is not None:
                try:
                    nx, ny = _lh5_apply_op_point(op, getattr(p, ax), getattr(p, ay))
                    setattr(p, ax, _lh5_clean(self, nx)); setattr(p, ay, _lh5_clean(self, ny))
                except Exception: pass
        for tm in (getattr(p, 'attribute_texts', {}) or {}).values():
            _lh5_transform_text_model(self, tm, op, font_factor)
        try:
            if op[0] == 'scale':
                p.number_font.size_grid = max(0.1, _lh5_clean(self, float(getattr(p.number_font, 'size_grid', .45) or .45) * font_factor))
                p.label_font.size_grid = max(0.1, _lh5_clean(self, float(getattr(p.label_font, 'size_grid', .55) or .55) * font_factor))
        except Exception: pass

    for tm in getattr(u, 'texts', []) or []:
        _lh5_transform_text_model(self, tm, op, font_factor)
    for tm in (getattr(u.body, 'attribute_texts', {}) or {}).values():
        _lh5_transform_text_model(self, tm, op, font_factor)

    # Transformation is now directly applied; stale accumulated base would reapply old geometry.
    try:
        if hasattr(u, '_body_group_transform'):
            delattr(u, '_body_group_transform')
    except Exception: pass
    if refresh:
        try: self.update_current_unit_canvas_positions()
        except Exception:
            try: self.rebuild_scene()
            except Exception: pass
        try: self.rebuild_tree(); self.rebuild_pin_table()
        except Exception: pass


def _lh5_normalize_noop(self, unit=None):
    # Do not silently renormalize on every rebuild. Origin placement is handled
    # explicitly by Origin Reset / template import. Rebuild must not undo a
    # user transform or shift imported body graphics.
    try:
        u = unit or getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
        if u is not None:
            if _lh5_body_graphics(self, u):
                try: _lh2_sync_body_model_to_body_graphics(self, u)
                except Exception: pass
    except Exception:
        pass

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._transform_unit_as_body_group = _lh5_transform_unit_as_body_group
        _cls._normalize_unit_body_anchor_to_symbol_origin = _lh5_normalize_noop
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr transform correction v6
# ---------------------------------------------------------------------------
# Finalized rules for imported/template BODY symbols:
# - BODY artwork is the real BODY, not a proxy rectangle.
# - Rotate is baked into the actual BODY graphics around canvas origin (0,0).
# - Flip H mirrors at the canvas Y-axis, Flip V mirrors at the canvas X-axis.
# - Pin geometry follows via side remapping so pin text remains readable.
# - Text/attributes/pin labels move with the group but glyphs are never rotated
#   or mirrored.
# - Scaling target dimensions are snapped to the edit grid.

def _lh6_clean(self, v):
    try:
        v = round(float(v), 9)
        return 0.0 if abs(v) < 1e-9 else v
    except Exception:
        return v


def _lh6_pt(op, x, y):
    x = float(x); y = float(y)
    if op[0] == 'rotate':
        d = int(round(float(op[1]) / 90.0)) % 4
        if d == 0: return x, y
        if d == 1: return -y, x
        if d == 2: return -x, -y
        return y, -x
    if op[0] == 'flip_h':
        return -x, y
    if op[0] == 'flip_v':
        return x, -y
    if op[0] == 'scale':
        return x * float(op[1]), y * float(op[2])
    return x, y


def _lh6_side(side, op):
    s = str(side or '')
    if s not in (PinSide.LEFT.value, PinSide.RIGHT.value, PinSide.TOP.value, PinSide.BOTTOM.value):
        return s
    if op[0] == 'flip_h':
        return {PinSide.LEFT.value: PinSide.RIGHT.value, PinSide.RIGHT.value: PinSide.LEFT.value}.get(s, s)
    if op[0] == 'flip_v':
        return {PinSide.TOP.value: PinSide.BOTTOM.value, PinSide.BOTTOM.value: PinSide.TOP.value}.get(s, s)
    if op[0] == 'rotate':
        d = int(round(float(op[1]) / 90.0)) % 4
        ccw = {
            PinSide.RIGHT.value: PinSide.TOP.value,
            PinSide.TOP.value: PinSide.LEFT.value,
            PinSide.LEFT.value: PinSide.BOTTOM.value,
            PinSide.BOTTOM.value: PinSide.RIGHT.value,
        }
        for _ in range(d):
            s = ccw.get(s, s)
    return s


def _lh6_text_readable(tm):
    try: tm.rotation = 0.0
    except Exception: pass
    try: tm.scale_x = 1.0
    except Exception: pass
    try: tm.scale_y = 1.0
    except Exception: pass


def _lh6_move_text(self, tm, op, font_factor=1.0):
    if tm is None:
        return
    try:
        nx, ny = _lh6_pt(op, tm.x, tm.y)
        tm.x, tm.y = _lh6_clean(self, nx), _lh6_clean(self, ny)
    except Exception:
        pass
    _lh6_text_readable(tm)
    try:
        if op[0] == 'scale':
            tm.font_size_grid = max(0.1, _lh6_clean(self, float(getattr(tm, 'font_size_grid', 0.75) or 0.75) * float(font_factor)))
    except Exception:
        pass


def _lh6_graphic_corners(g):
    x = float(getattr(g, 'x', 0.0) or 0.0)
    y = float(getattr(g, 'y', 0.0) or 0.0)
    w = float(getattr(g, 'w', 0.0) or 0.0)
    h = float(getattr(g, 'h', 0.0) or 0.0)
    return [(x, y), (x + w, y), (x + w, y - h), (x, y - h)]


def _lh6_transform_graphic(self, g, op):
    if g is None:
        return
    shape = str(getattr(g, 'shape', '') or '')
    clean = lambda v: _lh6_clean(self, v)
    try:
        if shape in ('line', 'arc'):
            x1 = float(getattr(g, 'x', 0.0) or 0.0); y1 = float(getattr(g, 'y', 0.0) or 0.0)
            x2 = x1 + float(getattr(g, 'w', 0.0) or 0.0)
            y2 = y1 - float(getattr(g, 'h', 0.0) or 0.0)
            nx1, ny1 = _lh6_pt(op, x1, y1); nx2, ny2 = _lh6_pt(op, x2, y2)
            ctrl_x, ctrl_y = getattr(g, 'ctrl_x', None), getattr(g, 'ctrl_y', None)
            g.x, g.y = clean(nx1), clean(ny1)
            g.w, g.h = clean(nx2 - nx1), clean(ny1 - ny2)
            g.rotation = 0.0; g.scale_x = 1.0; g.scale_y = 1.0
            if ctrl_x is not None and ctrl_y is not None:
                try:
                    cx, cy = _lh6_pt(op, x1 + float(ctrl_x), y1 - float(ctrl_y))
                    g.ctrl_x, g.ctrl_y = clean(cx - nx1), clean(ny1 - cy)
                except Exception:
                    pass
            try:
                if op[0] in ('flip_h', 'flip_v'):
                    g.curve_radius = clean(-float(getattr(g, 'curve_radius', 0.0) or 0.0))
                elif op[0] == 'scale':
                    g.curve_radius = clean(float(getattr(g, 'curve_radius', 0.0) or 0.0) * max(abs(float(op[1])), abs(float(op[2]))))
            except Exception:
                pass
        else:
            # Bake rect/ellipse/circle transformations into coordinates instead
            # of relying on a proxy item rotation.  For 90° rotations the real
            # BODY extents become the transformed extents directly.
            pts = [_lh6_pt(op, px, py) for px, py in _lh6_graphic_corners(g)]
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            minx, maxx = min(xs), max(xs); miny, maxy = min(ys), max(ys)
            g.x, g.y = clean(minx), clean(maxy)
            g.w, g.h = clean(maxx - minx), clean(maxy - miny)
            g.rotation = 0.0; g.scale_x = 1.0; g.scale_y = 1.0
    except Exception:
        pass


def _lh6_snap_target(self, value, mn=0.01):
    try:
        step = float(self._edit_grid_step())
        if step <= 0: step = float(getattr(self, 'edit_grid_inch', 0.1) or 0.1)
        return max(float(mn), round(float(value) / step) * step)
    except Exception:
        try: return self._snap_to_edit_grid(value, mn)
        except Exception: return max(float(mn), float(value))


def _lh6_transform_unit_as_body_group(self, op_name, value=None, refresh=True):
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    if u is None or getattr(u, 'body', None) is None:
        return
    try: _lh4_prepare_graphics_as_body(self, u)
    except Exception: pass
    try: _lh2_sync_body_model_to_body_graphics(self, u)
    except Exception: pass

    if op_name == 'rotate':
        deg = round(float(value or 0.0) / 90.0) * 90.0
        if abs(deg) < 1e-9:
            return
        op = ('rotate', deg)
    elif op_name == 'flip_h':
        op = ('flip_h',)
    elif op_name == 'flip_v':
        op = ('flip_v',)
    elif op_name in ('scale', 'scale_x_to', 'scale_y_to'):
        cur_w = max(1e-9, float(getattr(u.body, 'width', 1.0) or 1.0))
        cur_h = max(1e-9, float(getattr(u.body, 'height', 1.0) or 1.0))
        if op_name == 'scale_x_to':
            target_w = _lh6_snap_target(self, float(value), 0.01); sx, sy = target_w / cur_w, 1.0
        elif op_name == 'scale_y_to':
            target_h = _lh6_snap_target(self, float(value), 0.01); sx, sy = 1.0, target_h / cur_h
        else:
            f = float(value or 1.0)
            target_w = _lh6_snap_target(self, cur_w * f, 0.01)
            target_h = _lh6_snap_target(self, cur_h * f, 0.01)
            sx, sy = target_w / cur_w, target_h / cur_h
        op = ('scale', sx, sy)
    else:
        return

    font_factor = 1.0
    if op[0] == 'scale':
        font_factor = max(0.1, (abs(float(op[1])) + abs(float(op[2]))) / 2.0)

    body_graphics = []
    try: body_graphics = list(_lh2_body_graphics(self, u))
    except Exception: body_graphics = []

    if body_graphics:
        for g in body_graphics:
            _lh6_transform_graphic(self, g, op)
        try: _lh2_sync_body_model_to_body_graphics(self, u)
        except Exception: pass
        try: u.body.rotation = 0.0; u.body.scale_x = 1.0; u.body.scale_y = 1.0
        except Exception: pass
    else:
        # Internal <NONE>-style body: transform its own rectangle exactly.
        try:
            b = u.body
            pts = [_lh6_pt(op, b.x, b.y), _lh6_pt(op, b.x + b.width, b.y), _lh6_pt(op, b.x + b.width, b.y - b.height), _lh6_pt(op, b.x, b.y - b.height)]
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            b.x, b.y = _lh6_clean(self, min(xs)), _lh6_clean(self, max(ys))
            b.width, b.height = _lh6_clean(self, max(xs)-min(xs)), _lh6_clean(self, max(ys)-min(ys))
            b.rotation = 0.0; b.scale_x = 1.0; b.scale_y = 1.0
        except Exception:
            pass

    for g in getattr(u, 'graphics', []) or []:
        if g not in body_graphics:
            _lh6_transform_graphic(self, g, op)

    for p in getattr(u, 'pins', []) or []:
        try:
            p.x, p.y = (_lh6_clean(self, v) for v in _lh6_pt(op, p.x, p.y))
            p.side = _lh6_side(getattr(p, 'side', ''), op)
            # Pin side now carries geometry. Keep item rotation neutral so pin
            # number/name/function are painted readable by PinItem.
            p.rotation = 0.0; p.scale_x = 1.0; p.scale_y = 1.0
            if op[0] == 'scale':
                p.length = max(0.1, _lh6_clean(self, float(getattr(p, 'length', 1.0) or 1.0) * font_factor))
        except Exception:
            pass
        for ax, ay in (('label_x', 'label_y'), ('number_x', 'number_y')):
            if getattr(p, ax, None) is not None and getattr(p, ay, None) is not None:
                try:
                    nx, ny = _lh6_pt(op, getattr(p, ax), getattr(p, ay))
                    setattr(p, ax, _lh6_clean(self, nx)); setattr(p, ay, _lh6_clean(self, ny))
                except Exception: pass
        for tm in (getattr(p, 'attribute_texts', {}) or {}).values():
            _lh6_move_text(self, tm, op, font_factor)
        try:
            if op[0] == 'scale':
                p.number_font.size_grid = max(0.1, _lh6_clean(self, float(getattr(p.number_font, 'size_grid', .45) or .45) * font_factor))
                p.label_font.size_grid = max(0.1, _lh6_clean(self, float(getattr(p.label_font, 'size_grid', .55) or .55) * font_factor))
        except Exception:
            pass

    for tm in getattr(u, 'texts', []) or []:
        _lh6_move_text(self, tm, op, font_factor)
    for tm in (getattr(u.body, 'attribute_texts', {}) or {}).values():
        _lh6_move_text(self, tm, op, font_factor)

    try:
        if hasattr(u, '_body_group_transform'):
            delattr(u, '_body_group_transform')
    except Exception: pass
    if refresh:
        # Rebuild after BODY graphic transformations so QGraphicsItems cannot
        # retain stale proxy/rotation state.
        try: self.rebuild_scene()
        except Exception:
            try: self.update_current_unit_canvas_positions()
            except Exception: pass
        try: self.rebuild_tree(); self.rebuild_pin_table()
        except Exception: pass

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._transform_unit_as_body_group = _lh6_transform_unit_as_body_group
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v7: route BODY transform buttons to the current transform backend.
# Previous wrappers still called the old _lh2_transform_unit_as_body_group
# directly, so imported BODY graphics stayed unchanged while pins/text moved.
# Keep Symbol-1 behaviour for native BODYs, but always transform through
# self._transform_unit_as_body_group, which is overridden by the latest backend.
# ---------------------------------------------------------------------------
def _lh7_selected_body_or_body_graphic(self):
    try:
        for it in self.scene.selectedItems():
            k = getattr(it, 'data', lambda *_: None)(0)
            if k in ('BODY', 'BODY_GRAPHIC'):
                return True
            m = getattr(it, 'model', None)
            if m is not None:
                try:
                    if _lh2_is_body_graphic(self, m):
                        return True
                except Exception:
                    if getattr(m, 'locked_to_body', False) or str(getattr(m, 'graphic_role', '') or '').lower() in ('body','template_body','imported_body'):
                        return True
    except Exception:
        pass
    return False


def _lh7_do_body_transform(self, op_name, value=None):
    try:
        self.set_tool(DrawTool.SELECT.value)
    except Exception:
        pass
    try:
        self.push_undo_state()
    except Exception:
        pass
    u = getattr(self, 'current_unit', None) or getattr(self, 'unit', None)
    try:
        _lh4_prepare_graphics_as_body(self, u)
    except Exception:
        pass
    if _lh7_selected_body_or_body_graphic(self):
        fn = getattr(self, '_transform_unit_as_body_group', None)
        if callable(fn):
            fn(op_name, value)
        else:
            _lh6_transform_unit_as_body_group(self, op_name, value)
    else:
        # Keep existing behaviour for explicitly selected standalone objects.
        try:
            for it in self.scene.selectedItems():
                if op_name == 'rotate' and hasattr(it, 'rotate_by'):
                    it.rotate_by(float(value or 0.0))
                elif op_name == 'flip_h' and hasattr(it, 'flip_horizontal'):
                    it.flip_horizontal()
                elif op_name == 'flip_v' and hasattr(it, 'flip_vertical'):
                    it.flip_vertical()
                elif op_name == 'scale' and hasattr(it, 'scale_by'):
                    it.scale_by(float(value or 1.0))
        except Exception:
            pass
        try:
            self.rebuild_scene()
        except Exception:
            try: self.schedule_scene_refresh()
            except Exception: pass
    try:
        self.dirty = True
    except Exception:
        pass


def _lh7_rotate_selected(self, deg):
    _lh7_do_body_transform(self, 'rotate', float(deg))


def _lh7_flip_selected_horizontal(self):
    # Flip H = mirror at canvas Y-axis: x -> -x.
    _lh7_do_body_transform(self, 'flip_h', None)


def _lh7_flip_selected_vertical(self):
    # Flip V = mirror at canvas X-axis: y -> -y.
    _lh7_do_body_transform(self, 'flip_v', None)


def _lh7_scale_selected(self, factor):
    _lh7_do_body_transform(self, 'scale', float(factor))

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._selected_body_active = _lh7_selected_body_or_body_graphic
        _cls.rotate_selected = _lh7_rotate_selected
        _cls.flip_selected_horizontal = _lh7_flip_selected_horizontal
        _cls.flip_selected_vertical = _lh7_flip_selected_vertical
        _cls.scale_selected = _lh7_scale_selected
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v8: normalize direction semantics globally.
# User convention:
#   Rotate CW  = clockwise around canvas origin (0,0):       (x,y) -> ( y,-x)
#   Rotate CCW = counter-clockwise around canvas origin:      (x,y) -> (-y, x)
#   Flip H     = mirror at the HORIZONTAL axis (X-axis):      (x,y) -> ( x,-y)
#   Flip V     = mirror at the VERTICAL axis (Y-axis):        (x,y) -> (-x, y)
# Text glyphs remain readable; only positions are transformed by _lh6_move_text.
# This intentionally redefines _lh6_pt/_lh6_side after v7 because the transform
# backend resolves these globals at call time.
# ---------------------------------------------------------------------------
def _lh6_pt(op, x, y):
    x = float(x); y = float(y)
    if op[0] == 'rotate':
        # Positive angle is clockwise in the Symbol Wizard UI.
        d = int(round(float(op[1]) / 90.0)) % 4
        if d == 0:
            return x, y
        if d == 1:      # 90° CW
            return y, -x
        if d == 2:
            return -x, -y
        return -y, x    # 90° CCW
    if op[0] == 'flip_h':
        # Flip H means mirror at the horizontal X-axis.
        return x, -y
    if op[0] == 'flip_v':
        # Flip V means mirror at the vertical Y-axis.
        return -x, y
    if op[0] == 'scale':
        return x * float(op[1]), y * float(op[2])
    return x, y


def _lh6_side(side, op):
    s = str(side or '')
    valid = (PinSide.LEFT.value, PinSide.RIGHT.value, PinSide.TOP.value, PinSide.BOTTOM.value)
    if s not in valid:
        return s
    if op[0] == 'flip_h':
        # Mirror at X-axis: top/bottom swap, left/right stay.
        return {PinSide.TOP.value: PinSide.BOTTOM.value,
                PinSide.BOTTOM.value: PinSide.TOP.value}.get(s, s)
    if op[0] == 'flip_v':
        # Mirror at Y-axis: left/right swap, top/bottom stay.
        return {PinSide.LEFT.value: PinSide.RIGHT.value,
                PinSide.RIGHT.value: PinSide.LEFT.value}.get(s, s)
    if op[0] == 'rotate':
        d = int(round(float(op[1]) / 90.0)) % 4
        cw = {
            PinSide.RIGHT.value: PinSide.BOTTOM.value,
            PinSide.BOTTOM.value: PinSide.LEFT.value,
            PinSide.LEFT.value: PinSide.TOP.value,
            PinSide.TOP.value: PinSide.RIGHT.value,
        }
        for _ in range(d):
            s = cw.get(s, s)
    return s


def _lh8_flip_selected_horizontal(self):
    # Flip H = mirror at horizontal X-axis.
    _lh7_do_body_transform(self, 'flip_h', None)


def _lh8_flip_selected_vertical(self):
    # Flip V = mirror at vertical Y-axis.
    _lh7_do_body_transform(self, 'flip_v', None)

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.flip_selected_horizontal = _lh8_flip_selected_horizontal
        _cls.flip_selected_vertical = _lh8_flip_selected_vertical
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v9: imported BODY artwork must always remain selectable as BODY.
# After several rebuild/transform/filter cycles BODY_GRAPHIC items could keep an
# old selectable state or be ignored by Ctrl+A because BODY_GRAPHIC is not part
# of the public selection filter.  Treat BODY_GRAPHIC as BODY everywhere in the
# Symbol Wizard selection layer while still preventing primitive editing.
# ---------------------------------------------------------------------------
def _lh9_is_body_graphic_item(item):
    try:
        return getattr(item, 'data', lambda *_: None)(0) == 'BODY_GRAPHIC'
    except Exception:
        return False


def _lh9_body_item_candidates(self):
    try:
        items = list(self.scene.items())
    except Exception:
        return []
    body_items = []
    body_graphics = []
    for it in items:
        try:
            k = it.data(0)
        except Exception:
            continue
        if k == 'BODY':
            body_items.append(it)
        elif k == 'BODY_GRAPHIC':
            body_graphics.append(it)
    # Prefer a real BODY item for native Symbol 1; otherwise use one visible
    # BODY_GRAPHIC primitive as the click/selection representative for imported
    # artwork bodies.  All BODY_GRAPHIC primitives still paint the body, but the
    # selection model exposes exactly one logical BODY to the user.
    return body_items or body_graphics


def _lh9_select_logical_body(self):
    try:
        candidates = _lh9_body_item_candidates(self)
        if not candidates:
            return False
        self.scene.blockSignals(True)
        self.scene.clearSelection()
        candidates[0].setSelected(True)
        self.scene.blockSignals(False)
        self.refresh_properties()
        return True
    except Exception:
        try: self.scene.blockSignals(False)
        except Exception: pass
        return False


try:
    _lh9_prev_apply_item_selectability = MainWindow.apply_item_selectability
except Exception:
    _lh9_prev_apply_item_selectability = None


def _lh9_apply_item_selectability(self, item):
    if _lh9_is_body_graphic_item(item):
        selectable = bool(getattr(self, 'selection_enabled', {}).get('BODY', True))
        try: item.setFlag(QGraphicsItem.ItemIsSelectable, selectable)
        except Exception: pass
        # BODY artwork is selectable as the logical BODY, but never movable as a
        # separate primitive in the Symbol Wizard.  Transforms are routed through
        # the BODY group backend.
        try: item.setFlag(QGraphicsItem.ItemIsMovable, False)
        except Exception: pass
        try: item.setAcceptedMouseButtons(Qt.AllButtons if selectable else Qt.NoButton)
        except Exception: pass
        try:
            if not selectable:
                item.setSelected(False)
        except Exception: pass
        try: item.setZValue(0.2)
        except Exception: pass
        return
    if _lh9_prev_apply_item_selectability is not None:
        return _lh9_prev_apply_item_selectability(self, item)


try:
    _lh9_prev_apply_filter = MainWindow._apply_selection_filter_to_scene
except Exception:
    _lh9_prev_apply_filter = None


def _lh9_apply_selection_filter_to_scene(self):
    # Apply normal filtering first, then explicitly include BODY_GRAPHIC as BODY.
    if _lh9_prev_apply_filter is not None:
        try:
            _lh9_prev_apply_filter(self)
        except Exception:
            pass
    try:
        for item in self.scene.items():
            if _lh9_is_body_graphic_item(item):
                _lh9_apply_item_selectability(self, item)
    except Exception:
        pass


try:
    _lh9_prev_select_all_canvas = MainWindow.select_all_canvas
except Exception:
    _lh9_prev_select_all_canvas = None


def _lh9_select_all_canvas(self):
    try: self.set_tool(DrawTool.SELECT.value)
    except Exception: pass
    # With Selectable=BODY, Ctrl+A must select the logical BODY even when the
    # body is represented only by imported graphics and no BodyItem exists.
    if bool(getattr(self, 'selection_enabled', {}).get('BODY', True)) and not any(
        bool(getattr(self, 'selection_enabled', {}).get(k, False)) for k in ('PIN', 'TEXT', 'GRAPHIC')
    ):
        if _lh9_select_logical_body(self):
            return
    try:
        self.scene.clearSelection()
        selected_body_rep = False
        for item in self.scene.items():
            kind = item.data(0)
            filter_kind = 'TEXT' if kind in ('ATTR_REF_DES', 'ATTR_BODY') else ('BODY' if kind == 'BODY_GRAPHIC' else kind)
            if filter_kind in ('BODY', 'PIN', 'TEXT', 'GRAPHIC') and self.selection_enabled.get(filter_kind, True):
                # Body graphics represent one logical BODY. Select just one
                # representative to avoid multi-edit/property-panel confusion.
                if kind == 'BODY_GRAPHIC':
                    if selected_body_rep:
                        item.setSelected(False)
                        continue
                    selected_body_rep = True
                item.setSelected(True)
        self.refresh_properties()
    except Exception:
        if _lh9_prev_select_all_canvas is not None:
            return _lh9_prev_select_all_canvas(self)


try:
    _lh9_prev_refresh_properties = MainWindow.refresh_properties
except Exception:
    _lh9_prev_refresh_properties = None


def _lh9_refresh_properties(self):
    # If several BODY_GRAPHIC primitives became selected by rubber-band or stale
    # restore ids, collapse them to one logical BODY before building the panel.
    try:
        selected = list(self.scene.selectedItems())
        bg = [i for i in selected if _lh9_is_body_graphic_item(i)]
        if len(bg) > 1 and len(bg) == len(selected):
            self.scene.blockSignals(True)
            self.scene.clearSelection()
            bg[0].setSelected(True)
            self.scene.blockSignals(False)
    except Exception:
        try: self.scene.blockSignals(False)
        except Exception: pass
    if _lh9_prev_refresh_properties is not None:
        return _lh9_prev_refresh_properties(self)


try:
    _lh9_prev_selected_body_active = MainWindow._selected_body_active
except Exception:
    _lh9_prev_selected_body_active = None


def _lh9_selected_body_active(self):
    try:
        for it in self.scene.selectedItems():
            if getattr(it, 'data', lambda *_: None)(0) in ('BODY', 'BODY_GRAPHIC'):
                return True
            m = getattr(it, 'model', None)
            if m is not None and (getattr(m, 'locked_to_body', False) or str(getattr(m, 'graphic_role', '') or '').lower() in ('body', 'template_body', 'imported_body')):
                return True
    except Exception:
        pass
    if _lh9_prev_selected_body_active is not None:
        try: return bool(_lh9_prev_selected_body_active(self))
        except Exception: pass
    return False


try:
    MainWindow.apply_item_selectability = _lh9_apply_item_selectability
    MainWindow._apply_selection_filter_to_scene = _lh9_apply_selection_filter_to_scene
    MainWindow.select_all_canvas = _lh9_select_all_canvas
    MainWindow.refresh_properties = _lh9_refresh_properties
    MainWindow._selected_body_active = _lh9_selected_body_active
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v10: canvas BODY scale without scaling pins + BODY graphic selection.
# Baseline: Symbol_Wizard_39.  BODY resize/Scale +/- changes the BODY geometry
# only. Pins are re-docked and snapped to the edit grid, but pin length, pin font
# sizes and text glyphs are not scaled.  Imported/template BODY graphics are the
# real BODY and are scaled directly; no proxy rectangle is introduced.
# ---------------------------------------------------------------------------
def _lh10_edit_grid_step(self):
    try:
        return max(0.001, float(getattr(self, 'edit_grid_step', None) or self.edit_grid.value() or self.grid_inch))
    except Exception:
        try: return max(0.001, float(getattr(self, 'grid_inch', 1.0) or 1.0))
        except Exception: return 1.0


def _lh10_snap_edit(self, v):
    step = _lh10_edit_grid_step(self)
    try: return self._clean_float(round(float(v) / step) * step)
    except Exception: return v


def _lh10_body_graphics(self, unit=None):
    u = unit or getattr(self, 'current_unit', None)
    out = []
    for gr in getattr(u, 'graphics', []) or []:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        raw = str(getattr(gr, 'mentor_raw', '') or '')
        if getattr(gr, 'locked_to_body', False) or role in ('body', 'template_body', 'imported_body') or (raw != '__USER_GRAPHIC__' and role != 'user_graphic'):
            out.append(gr)
    return out


def _lh10_graphic_points(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    # GraphicItem uses model endpoint (x+w, y-h) in grid coordinates.
    return (x, y, x + w, y - h)


def _lh10_body_graphics_bounds(self, unit=None):
    gs = _lh10_body_graphics(self, unit)
    if not gs:
        b = (unit or self.current_unit).body
        return (float(b.x), float(b.y), float(b.width), float(b.height))
    xs, ys = [], []
    for gr in gs:
        x1, y1, x2, y2 = _lh10_graphic_points(gr)
        xs.extend([x1, x2]); ys.extend([y1, y2])
        try:
            if getattr(gr, 'ctrl_x', None) is not None and getattr(gr, 'ctrl_y', None) is not None:
                xs.append(x1 + float(gr.ctrl_x)); ys.append(y1 - float(gr.ctrl_y))
        except Exception:
            pass
    left, right = min(xs), max(xs)
    bottom, top = min(ys), max(ys)
    return (self._clean_float(left), self._clean_float(top), self._clean_float(max(0.01, right-left)), self._clean_float(max(0.01, top-bottom)))


def _lh10_sync_body_to_body_graphics(self, unit=None):
    u = unit or self.current_unit
    gs = _lh10_body_graphics(self, u)
    if not gs:
        return
    x, y, w, h = _lh10_body_graphics_bounds(self, u)
    b = u.body
    b.x, b.y, b.width, b.height = x, y, w, h


def _lh10_move_pin_owned_texts_safe(self, pin, dx, dy):
    try:
        self._move_pin_owned_texts(pin, dx, dy)
    except Exception:
        for ax, ay in (('label_x','label_y'), ('number_x','number_y')):
            if getattr(pin, ax, None) is not None and getattr(pin, ay, None) is not None:
                try:
                    setattr(pin, ax, float(getattr(pin, ax)) + dx)
                    setattr(pin, ay, float(getattr(pin, ay)) + dy)
                except Exception: pass
        for tm in (getattr(pin, 'attribute_texts', {}) or {}).values():
            try: tm.x, tm.y = float(tm.x) + dx, float(tm.y) + dy
            except Exception: pass


def _lh10_redock_pins_after_body_scale(self, start_state, body):
    old_x = float(start_state.get('x', body.x)); old_y = float(start_state.get('y', body.y))
    old_w = max(float(start_state.get('w', body.width)), 1e-9)
    old_h = max(float(start_state.get('h', body.height)), 1e-9)
    new_x, new_y = float(body.x), float(body.y)
    new_w, new_h = max(float(body.width), 1e-9), max(float(body.height), 1e-9)
    sx, sy = new_w / old_w, new_h / old_h

    def sxpos(px): return _lh10_snap_edit(self, new_x + (float(px) - old_x) * sx)
    def sypos(py): return _lh10_snap_edit(self, new_y - (old_y - float(py)) * sy)

    for p, px, py, plen in start_state.get('pins', []) or []:
        ox, oy = float(getattr(p, 'x', px)), float(getattr(p, 'y', py))
        side = getattr(p, 'side', '')
        if side == PinSide.LEFT.value:
            nx, ny = new_x, sypos(py)
        elif side == PinSide.RIGHT.value:
            nx, ny = new_x + new_w, sypos(py)
        elif side == PinSide.TOP.value:
            nx, ny = sxpos(px), new_y
        elif side == PinSide.BOTTOM.value:
            nx, ny = sxpos(px), new_y - new_h
        else:
            nx, ny = sxpos(px), sypos(py)
        nx, ny = _lh10_snap_edit(self, nx), _lh10_snap_edit(self, ny)
        p.x, p.y = nx, ny
        # Critical: BODY scale must not scale pins.  Length stays as authored.
        try: p.length = max(0.1, float(plen))
        except Exception: pass
        _lh10_move_pin_owned_texts_safe(self, p, nx - ox, ny - oy)


def _lh10_scale_body_graphics_to(self, unit, old_bounds, new_bounds):
    gs = _lh10_body_graphics(self, unit)
    if not gs:
        return
    ox, oy, ow, oh = old_bounds
    nx, ny, nw, nh = new_bounds
    ow, oh = max(float(ow), 1e-9), max(float(oh), 1e-9)
    sx, sy = float(nw) / ow, float(nh) / oh
    def map_pt(x, y):
        # x relative from left; y relative downward from top.
        return (self._clean_float(nx + (float(x) - ox) * sx),
                self._clean_float(ny - (oy - float(y)) * sy))
    for gr in gs:
        x1, y1, x2, y2 = _lh10_graphic_points(gr)
        nx1, ny1 = map_pt(x1, y1)
        nx2, ny2 = map_pt(x2, y2)
        gr.x, gr.y = nx1, ny1
        gr.w = self._clean_float(nx2 - nx1)
        gr.h = self._clean_float(ny1 - ny2)
        try:
            if getattr(gr, 'ctrl_x', None) is not None:
                gr.ctrl_x = self._clean_float(float(gr.ctrl_x) * sx)
            if getattr(gr, 'ctrl_y', None) is not None:
                gr.ctrl_y = self._clean_float(float(gr.ctrl_y) * sy)
        except Exception:
            pass
    _lh10_sync_body_to_body_graphics(self, unit)


def _lh10_scale_body_only_to(self, new_w, new_h, refresh=True):
    """Resize BODY to edit-grid dimensions without scaling pins/text glyphs."""
    u = self.current_unit; b = u.body
    old_bounds = _lh10_body_graphics_bounds(self, u) if _lh10_body_graphics(self, u) else (float(b.x), float(b.y), float(b.width), float(b.height))
    old_x, old_y, old_w, old_h = old_bounds
    new_w = max(_lh10_edit_grid_step(self), _lh10_snap_edit(self, new_w))
    new_h = max(_lh10_edit_grid_step(self), _lh10_snap_edit(self, new_h))
    start = {
        'x': old_x, 'y': old_y, 'w': old_w, 'h': old_h,
        'pins': [(p, float(p.x), float(p.y), float(getattr(p, 'length', 1.0) or 1.0)) for p in getattr(u, 'pins', []) or []],
        'texts': [(t, float(t.x), float(t.y)) for t in getattr(u, 'texts', []) or []],
        'attributes': [(t, float(t.x), float(t.y)) for t in (getattr(b, 'attribute_texts', {}) or {}).values()],
        'graphics': [(gr, float(gr.x), float(gr.y), float(getattr(gr, 'w', 0.0) or 0.0), float(getattr(gr, 'h', 0.0) or 0.0)) for gr in getattr(u, 'graphics', []) or [] if gr not in _lh10_body_graphics(self, u)],
    }
    # Keep the authored top-left anchor. This matches canvas drag-resize behaviour.
    new_bounds = (old_x, old_y, new_w, new_h)
    if _lh10_body_graphics(self, u):
        _lh10_scale_body_graphics_to(self, u, old_bounds, new_bounds)
    else:
        b.x, b.y, b.width, b.height = old_x, old_y, new_w, new_h
    _lh10_redock_pins_after_body_scale(self, start, b)
    # Non-pin text/user graphics are repositioned proportionally to stay attached,
    # but their font size/visual scale is intentionally unchanged.
    sx, sy = new_w / max(old_w, 1e-9), new_h / max(old_h, 1e-9)
    def map_pos(x, y): return (_lh10_snap_edit(self, old_x + (float(x)-old_x)*sx), _lh10_snap_edit(self, old_y - (old_y-float(y))*sy))
    for t, tx, ty in start.get('texts', []) or []:
        t.x, t.y = map_pos(tx, ty)
    for t, tx, ty in start.get('attributes', []) or []:
        t.x, t.y = map_pos(tx, ty)
    for gr, gx, gy, gw, gh in start.get('graphics', []) or []:
        gr.x, gr.y = map_pos(gx, gy)
        # user graphics are not the BODY; keep their own dimensions unchanged.
        gr.w, gr.h = gw, gh
    # Body transform base is invalid after geometry edit.
    try: delattr(u, '_body_group_transform')
    except Exception: pass
    if refresh:
        self.update_current_unit_canvas_positions()
        self.update_attribute_items_for_unit()
        self.rebuild_tree(); self.rebuild_pin_table()
        try: self.refresh_properties()
        except Exception: pass
        try: self.view.viewport().update()
        except Exception: pass


def _lh10_scale_current_unit_children_from_body_resize(self, start_state, body):
    """Canvas BODY handle resize: scale BODY graphics only; pins stay grid/length."""
    u = self.current_unit
    old_bounds = (float(start_state.get('x', body.x)), float(start_state.get('y', body.y)),
                  max(float(start_state.get('w', body.width)), 1e-9), max(float(start_state.get('h', body.height)), 1e-9))
    new_w = _lh10_snap_edit(self, float(body.width))
    new_h = _lh10_snap_edit(self, float(body.height))
    body.width, body.height = max(_lh10_edit_grid_step(self), new_w), max(_lh10_edit_grid_step(self), new_h)
    new_bounds = (float(body.x), float(body.y), float(body.width), float(body.height))
    if _lh10_body_graphics(self, u):
        _lh10_scale_body_graphics_to(self, u, old_bounds, new_bounds)
    _lh10_redock_pins_after_body_scale(self, start_state, body)
    # Texts/body attributes follow the body proportionally; glyphs are not scaled.
    ox, oy, ow, oh = old_bounds; nx, ny, nw, nh = new_bounds
    sx, sy = nw / max(ow, 1e-9), nh / max(oh, 1e-9)
    def map_pos(x, y): return (_lh10_snap_edit(self, nx + (float(x)-ox)*sx), _lh10_snap_edit(self, ny - (oy-float(y))*sy))
    for t, tx, ty in start_state.get('texts', []) or []:
        t.x, t.y = map_pos(tx, ty)
    for t, tx, ty in start_state.get('attributes', []) or []:
        t.x, t.y = map_pos(tx, ty)
    # User graphics are separate objects: move anchor only, do not scale their size.
    body_graphics = set(_lh10_body_graphics(self, u))
    for gr, gx, gy, gw, gh in start_state.get('graphics', []) or []:
        if gr in body_graphics:
            continue
        gr.x, gr.y = map_pos(gx, gy)
        gr.w, gr.h = gw, gh
    try: delattr(u, '_body_group_transform')
    except Exception: pass


try:
    _lh10_prev_transform_unit_as_body_group = MainWindow._transform_unit_as_body_group
except Exception:
    _lh10_prev_transform_unit_as_body_group = None


def _lh10_transform_unit_as_body_group(self, op, value=None, refresh=True):
    # Only scale BODY geometry for Scale +/- and BODY width/height edits.  Rotate
    # and Flip remain true group transforms.
    if op in ('scale', 'scale_x_to', 'scale_y_to'):
        b = self.current_unit.body
        cur_w, cur_h = float(getattr(b, 'width', 1.0) or 1.0), float(getattr(b, 'height', 1.0) or 1.0)
        if op == 'scale_x_to':
            new_w, new_h = float(value), cur_h
        elif op == 'scale_y_to':
            new_w, new_h = cur_w, float(value)
        else:
            f = float(value or 1.0)
            new_w, new_h = cur_w * f, cur_h * f
        return _lh10_scale_body_only_to(self, new_w, new_h, refresh=refresh)
    if _lh10_prev_transform_unit_as_body_group is not None:
        return _lh10_prev_transform_unit_as_body_group(self, op, value, refresh)


try:
    _lh10_prev_graphic_mouse_press = GraphicItem.mousePressEvent
except Exception:
    _lh10_prev_graphic_mouse_press = None


def _lh10_graphic_mouse_press(self, event):
    # Clicking imported/template BODY artwork in Symbol Wizard selects the logical
    # BODY item so canvas handles (including scale) operate exactly like Symbol 1.
    try:
        if (getattr(getattr(self, 'model', None), 'locked_to_body', False)
                and not getattr(self.window, 'is_template_editor', False)
                and event.button() == Qt.LeftButton):
            cands = _lh9_body_item_candidates(self.window) if '_lh9_body_item_candidates' in globals() else []
            body_items = [i for i in cands if getattr(i, 'data', lambda *_: None)(0) == 'BODY']
            target = body_items[0] if body_items else (cands[0] if cands else self)
            try: self.window.scene.clearSelection()
            except Exception: pass
            target.setSelected(True)
            try: self.window.refresh_properties()
            except Exception: pass
            event.accept()
            return
    except Exception:
        pass
    if _lh10_prev_graphic_mouse_press is not None:
        return _lh10_prev_graphic_mouse_press(self, event)


try:
    MainWindow.scale_current_unit_children_from_body_resize = _lh10_scale_current_unit_children_from_body_resize
    MainWindow._transform_unit_as_body_group = _lh10_transform_unit_as_body_group
    MainWindow._lh10_scale_body_only_to = _lh10_scale_body_only_to
    MainWindow._lh10_sync_body_to_body_graphics = _lh10_sync_body_to_body_graphics
    GraphicItem.mousePressEvent = _lh10_graphic_mouse_press
except Exception:
    pass

# ---------------------------------------------------------------------------
# SW39 retry fix: unify BODY style/scale handling for Symbol1/import/templates.
# - Property-panel BODY width/height and toolbar Scale +/- use one safe path.
# - Canvas BODY handle resize uses the same path for imported/template graphics.
# - BODY graphics are detected by role/lock/mentor flags, not by proxy frame.
# - Pins are never scaled; they are redocked/snapped to edit grid and keep length.
# - Line style/width apply to all selected graphical objects; RGB applies to all.
# ---------------------------------------------------------------------------

def _sw39_edit_step(self):
    try:
        return max(0.001, float(getattr(self, 'edit_grid_step', 0) or self.edit_grid.value() or self.grid_inch or 1.0))
    except Exception:
        return 1.0


def _sw39_clean(self, v):
    try:
        v = round(float(v), 9)
        return 0.0 if abs(v) < 1e-9 else v
    except Exception:
        return v


def _sw39_snap(self, v):
    step = _sw39_edit_step(self)
    try:
        return _sw39_clean(self, round(float(v) / step) * step)
    except Exception:
        return float(v)


def _sw39_is_imported_or_template_body(self, unit=None):
    try:
        u = unit or self.current_unit
        b = u.body
        attrs = getattr(b, 'attributes', {}) or {}
        flags = ('MENTOR_GRAPHICS_AS_BODY', 'TEMPLATE_GRAPHICS_AS_BODY', 'MENTOR_HAS_BODY')
        if any(str(attrs.get(k, '0')).strip().upper() in ('1', 'TRUE', 'YES') for k in flags):
            return True
        return any(getattr(g, 'locked_to_body', False) or str(getattr(g, 'graphic_role', '')).lower() in ('body','template_body','imported_body') for g in getattr(u, 'graphics', []) or [])
    except Exception:
        return False


def _sw39_body_graphics(self, unit=None):
    """Return real graphics that visually form the BODY.

    Imported/template symbols must not have a proxy rectangle.  The imported
    primitives themselves are the BODY.  User-added graphics stay separate and
    therefore are excluded.
    """
    try:
        u = unit or self.current_unit
        imported = _sw39_is_imported_or_template_body(self, u)
        out = []
        for g in getattr(u, 'graphics', []) or []:
            role = str(getattr(g, 'graphic_role', '')).lower()
            raw = str(getattr(g, 'mentor_raw', '') or '')
            if raw == '__USER_GRAPHIC__' or role == 'user_graphic':
                continue
            if imported or getattr(g, 'locked_to_body', False) or role in ('body','template_body','imported_body'):
                out.append(g)
        return out
    except Exception:
        return []

# Override legacy global helper used by the previous patch, if present.
try:
    _lh10_body_graphics = _sw39_body_graphics
except Exception:
    pass


def _sw39_graphic_bounds(g):
    x = float(getattr(g, 'x', 0.0) or 0.0)
    y = float(getattr(g, 'y', 0.0) or 0.0)
    w = float(getattr(g, 'w', 0.0) or 0.0)
    h = float(getattr(g, 'h', 0.0) or 0.0)
    xs = [x, x + w]
    ys = [y, y - h]
    try:
        if getattr(g, 'shape', '') == 'ellipse':
            pass
    except Exception:
        pass
    return min(xs), min(ys), max(xs), max(ys)


def _sw39_body_graphics_bounds(self, unit=None):
    gs = _sw39_body_graphics(self, unit)
    if not gs:
        b = (unit or self.current_unit).body
        return (float(b.x), float(b.y), float(b.width), float(b.height))
    mins = [_sw39_graphic_bounds(g) for g in gs]
    xmin = min(v[0] for v in mins); ymin = min(v[1] for v in mins)
    xmax = max(v[2] for v in mins); ymax = max(v[3] for v in mins)
    # Body model uses top-left y and positive height downward in this tool.
    return (_sw39_clean(self, xmin), _sw39_clean(self, ymax), _sw39_clean(self, xmax - xmin), _sw39_clean(self, ymax - ymin))

try:
    _lh10_body_graphics_bounds = _sw39_body_graphics_bounds
except Exception:
    pass


def _sw39_sync_body_to_real_graphics(self, unit=None):
    u = unit or self.current_unit
    try:
        x, y, w, h = _sw39_body_graphics_bounds(self, u)
        u.body.x, u.body.y, u.body.width, u.body.height = x, y, max(_sw39_edit_step(self), w), max(_sw39_edit_step(self), h)
    except Exception:
        pass


def _sw39_scale_graphics_to_bounds(self, unit, old_bounds, new_bounds):
    gs = _sw39_body_graphics(self, unit)
    if not gs:
        return
    ox, oy, ow, oh = old_bounds
    nx, ny, nw, nh = new_bounds
    ow, oh = max(float(ow), 1e-9), max(float(oh), 1e-9)
    sx, sy = float(nw) / ow, float(nh) / oh
    for g in gs:
        gx = float(getattr(g, 'x', 0.0) or 0.0)
        gy = float(getattr(g, 'y', 0.0) or 0.0)
        gw = float(getattr(g, 'w', 0.0) or 0.0)
        gh = float(getattr(g, 'h', 0.0) or 0.0)
        # map top-left anchor and dimensions; keep sign of w/h.
        g.x = _sw39_clean(self, nx + (gx - ox) * sx)
        g.y = _sw39_clean(self, ny - (oy - gy) * sy)
        g.w = _sw39_clean(self, gw * sx)
        g.h = _sw39_clean(self, gh * sy)
        try:
            if getattr(g, 'ctrl_x', None) is not None:
                g.ctrl_x = _sw39_clean(self, float(g.ctrl_x) * sx)
            if getattr(g, 'ctrl_y', None) is not None:
                g.ctrl_y = _sw39_clean(self, float(g.ctrl_y) * sy)
        except Exception:
            pass
    _sw39_sync_body_to_real_graphics(self, unit)


def _sw39_move_pin_owned_texts(self, pin, dx, dy):
    try:
        self._move_pin_owned_texts(pin, dx, dy)
        return
    except Exception:
        pass
    for ax, ay in (('label_x','label_y'), ('number_x','number_y')):
        try:
            if getattr(pin, ax, None) is not None and getattr(pin, ay, None) is not None:
                setattr(pin, ax, _sw39_clean(self, float(getattr(pin, ax)) + dx))
                setattr(pin, ay, _sw39_clean(self, float(getattr(pin, ay)) + dy))
        except Exception:
            pass
    for tm in (getattr(pin, 'attribute_texts', {}) or {}).values():
        try:
            tm.x = _sw39_clean(self, float(tm.x) + dx)
            tm.y = _sw39_clean(self, float(tm.y) + dy)
        except Exception:
            pass


def _sw39_redock_pins_to_scaled_body(self, unit, start, old_bounds, new_bounds):
    ox, oy, ow, oh = old_bounds
    nx, ny, nw, nh = new_bounds
    sx, sy = float(nw) / max(float(ow), 1e-9), float(nh) / max(float(oh), 1e-9)
    for p, px, py, plen in start.get('pins', []) or []:
        old_px, old_py = float(getattr(p, 'x', px)), float(getattr(p, 'y', py))
        side = getattr(p, 'side', '')
        # Pins must remain on edit-grid and keep their authored length.  Only the
        # docking coordinate follows the resized BODY.
        if side == PinSide.LEFT.value:
            tx = nx; ty = ny - (oy - float(py)) * sy
        elif side == PinSide.RIGHT.value:
            tx = nx + nw; ty = ny - (oy - float(py)) * sy
        elif side == PinSide.TOP.value:
            tx = nx + (float(px) - ox) * sx; ty = ny
        elif side == PinSide.BOTTOM.value:
            tx = nx + (float(px) - ox) * sx; ty = ny - nh
        else:
            tx = nx + (float(px) - ox) * sx; ty = ny - (oy - float(py)) * sy
        p.x = _sw39_snap(self, tx)
        p.y = _sw39_snap(self, ty)
        try:
            p.length = float(plen)
        except Exception:
            pass
        _sw39_move_pin_owned_texts(self, p, p.x - old_px, p.y - old_py)


def _sw39_capture_resize_state(self, unit=None):
    u = unit or self.current_unit
    b = u.body
    return {
        'x': float(b.x), 'y': float(b.y), 'w': float(b.width), 'h': float(b.height),
        'pins': [(p, float(p.x), float(p.y), float(getattr(p, 'length', 1.0) or 1.0)) for p in getattr(u, 'pins', []) or []],
        'texts': [(t, float(t.x), float(t.y)) for t in getattr(u, 'texts', []) or []],
        'attributes': [(t, float(t.x), float(t.y)) for t in (getattr(b, 'attribute_texts', {}) or {}).values()],
        'graphics': [(g, float(g.x), float(g.y), float(getattr(g, 'w', 0.0) or 0.0), float(getattr(g, 'h', 0.0) or 0.0)) for g in getattr(u, 'graphics', []) or [] if g not in _sw39_body_graphics(self, u)],
    }


def _sw39_resize_body_geometry(self, new_w=None, new_h=None, refresh=True):
    if getattr(self, '_sw39_resizing_body', False):
        return
    self._sw39_resizing_body = True
    try:
        u = self.current_unit
        b = u.body
        step = _sw39_edit_step(self)
        old_bounds = _sw39_body_graphics_bounds(self, u)
        ox, oy, ow, oh = old_bounds
        new_w = max(step, _sw39_snap(self, ow if new_w is None else new_w))
        new_h = max(step, _sw39_snap(self, oh if new_h is None else new_h))
        start = _sw39_capture_resize_state(self, u)
        # Keep the current BODY top-left anchor. Origin handling is done by Origin Reset;
        # resize itself is deterministic and edit-grid based.
        new_bounds = (ox, oy, new_w, new_h)
        if _sw39_body_graphics(self, u):
            _sw39_scale_graphics_to_bounds(self, u, old_bounds, new_bounds)
        else:
            b.x, b.y, b.width, b.height = ox, oy, new_w, new_h
        # BODY scale does not scale pins. It only redocks them to the new edge/grid.
        _sw39_redock_pins_to_scaled_body(self, u, start, old_bounds, (b.x, b.y, b.width, b.height))
        # Attached non-pin texts/attributes follow position proportionally; glyph size is unchanged.
        nx, ny, nw, nh = float(b.x), float(b.y), float(b.width), float(b.height)
        sx, sy = nw / max(ow, 1e-9), nh / max(oh, 1e-9)
        def map_pos(x, y):
            return (_sw39_snap(self, nx + (float(x)-ox)*sx), _sw39_snap(self, ny - (oy-float(y))*sy))
        for t, tx, ty in start.get('texts', []) or []:
            t.x, t.y = map_pos(tx, ty)
        for t, tx, ty in start.get('attributes', []) or []:
            t.x, t.y = map_pos(tx, ty)
        for g, gx, gy, gw, gh in start.get('graphics', []) or []:
            g.x, g.y = map_pos(gx, gy)
            g.w, g.h = gw, gh
        try:
            if hasattr(u, '_body_group_transform'):
                delattr(u, '_body_group_transform')
        except Exception:
            pass
        self.dirty = True
    finally:
        self._sw39_resizing_body = False
    if refresh:
        try: self.update_current_unit_canvas_positions()
        except Exception: pass
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.rebuild_tree(); self.rebuild_pin_table()
        except Exception: pass
        try: self.refresh_properties()
        except Exception: pass
        try: self.schedule_scene_refresh(visual_only=True)
        except Exception:
            try: self.scene.update()
            except Exception: pass


def _sw39_set_body_width_grid(self, body, value):
    try:
        new_w = max(_sw39_edit_step(self), _sw39_snap(self, float(value)))
        cur_w = float(getattr(self.current_unit.body, 'width', new_w) or new_w)
        if abs(new_w - cur_w) < 1e-9:
            return
        self.push_undo_state()
        self._selection_restore_ids = self._capture_selection_ids()
        _sw39_resize_body_geometry(self, new_w=new_w, new_h=None, refresh=True)
    except Exception as e:
        try: self.statusBar().showMessage(f'BODY width update failed: {e}', 4000)
        except Exception: pass


def _sw39_set_body_height_grid(self, body, value):
    try:
        new_h = max(_sw39_edit_step(self), _sw39_snap(self, float(value)))
        cur_h = float(getattr(self.current_unit.body, 'height', new_h) or new_h)
        if abs(new_h - cur_h) < 1e-9:
            return
        self.push_undo_state()
        self._selection_restore_ids = self._capture_selection_ids()
        _sw39_resize_body_geometry(self, new_w=None, new_h=new_h, refresh=True)
    except Exception as e:
        try: self.statusBar().showMessage(f'BODY height update failed: {e}', 4000)
        except Exception: pass


def _sw39_transform_unit_as_body_group(self, op, value=None, refresh=True):
    if op in ('scale', 'scale_x_to', 'scale_y_to'):
        b = self.current_unit.body
        cur_w = float(getattr(b, 'width', 1.0) or 1.0)
        cur_h = float(getattr(b, 'height', 1.0) or 1.0)
        if op == 'scale_x_to':
            return _sw39_resize_body_geometry(self, new_w=float(value), new_h=None, refresh=refresh)
        if op == 'scale_y_to':
            return _sw39_resize_body_geometry(self, new_w=None, new_h=float(value), refresh=refresh)
        f = float(value or 1.0)
        return _sw39_resize_body_geometry(self, new_w=cur_w * f, new_h=cur_h * f, refresh=refresh)
    # Delegate rotate/flip to the already working Symbol1-like implementation.
    try:
        return _sw39_prev_transform_unit_as_body_group(self, op, value, refresh)
    except Exception:
        if '_lh10_prev_transform_unit_as_body_group' in globals() and _lh10_prev_transform_unit_as_body_group is not None:
            return _lh10_prev_transform_unit_as_body_group(self, op, value, refresh)

try:
    _sw39_prev_transform_unit_as_body_group = MainWindow._transform_unit_as_body_group
except Exception:
    _sw39_prev_transform_unit_as_body_group = None


def _sw39_scale_selected_grid(self, direction: int):
    self.set_tool(DrawTool.SELECT.value)
    if self._selected_body_active():
        step = _sw39_edit_step(self)
        b = self.current_unit.body
        self.push_undo_state()
        self._selection_restore_ids = self._capture_selection_ids()
        _sw39_resize_body_geometry(self, float(b.width) + direction * step, float(b.height) + direction * step, refresh=True)
    else:
        # Keep old behavior for non-BODY graphics.
        try: return _sw39_prev_scale_selected_grid(self, direction)
        except Exception: return self.scale_selected(1.0 + (0.1 if direction > 0 else -0.1))

try:
    _sw39_prev_scale_selected_grid = MainWindow.scale_selected_grid
except Exception:
    _sw39_prev_scale_selected_grid = None


def _sw39_scale_current_unit_children_from_body_resize(self, start_state, body):
    # Canvas handle resize. BodyItem has already changed body.x/y/width/height;
    # use that as requested target and apply the exact same resize pipeline to
    # the real BODY graphics. This enables canvas scaling for imported/template bodies.
    try:
        u = self.current_unit
        old_bounds = (float(start_state.get('x', body.x)), float(start_state.get('y', body.y)),
                      max(float(start_state.get('w', body.width)), 1e-9), max(float(start_state.get('h', body.height)), 1e-9))
        new_w = max(_sw39_edit_step(self), _sw39_snap(self, float(body.width)))
        new_h = max(_sw39_edit_step(self), _sw39_snap(self, float(body.height)))
        new_bounds = (_sw39_snap(self, float(body.x)), _sw39_snap(self, float(body.y)), new_w, new_h)
        if _sw39_body_graphics(self, u):
            _sw39_scale_graphics_to_bounds(self, u, old_bounds, new_bounds)
        else:
            body.x, body.y, body.width, body.height = new_bounds
        _sw39_redock_pins_to_scaled_body(self, u, start_state, old_bounds, (body.x, body.y, body.width, body.height))
        ox, oy, ow, oh = old_bounds; nx, ny, nw, nh = float(body.x), float(body.y), float(body.width), float(body.height)
        sx, sy = nw / max(ow, 1e-9), nh / max(oh, 1e-9)
        def map_pos(x, y):
            return (_sw39_snap(self, nx + (float(x)-ox)*sx), _sw39_snap(self, ny - (oy-float(y))*sy))
        for t, tx, ty in start_state.get('texts', []) or []:
            t.x, t.y = map_pos(tx, ty)
        for t, tx, ty in start_state.get('attributes', []) or []:
            t.x, t.y = map_pos(tx, ty)
        body_graphics = set(_sw39_body_graphics(self, u))
        for gr, gx, gy, gw, gh in start_state.get('graphics', []) or []:
            if gr in body_graphics:
                continue
            gr.x, gr.y = map_pos(gx, gy)
            gr.w, gr.h = gw, gh
        self.dirty = True
    except Exception as e:
        try: self.statusBar().showMessage(f'Canvas BODY scale failed: {e}', 4000)
        except Exception: pass


def _sw39_apply_line_defaults(self):
    selected = list(self.scene.selectedItems()) if hasattr(self, 'scene') else []
    if not selected:
        return
    style = self.line_style.currentText()
    width = float(self.line_width.value())
    self.push_undo_state()
    changed = False
    for it in selected:
        k = it.data(0); m = getattr(it, 'model', None)
        if m is None: continue
        if k == 'BODY':
            m.line_style = style; m.line_width = width; changed = True
            for gr in _sw39_body_graphics(self, self.current_unit):
                st = getattr(gr, 'style', None)
                if st is not None:
                    st.line_style = style; st.line_width = width
        elif k == 'GRAPHIC':
            st = getattr(m, 'style', None)
            if st is not None:
                st.line_style = style; st.line_width = width; changed = True
        elif k == 'PIN':
            m.line_style = style; m.line_width = width; changed = True
    if changed:
        self.dirty = True
        try: self.update_current_unit_canvas_positions()
        except Exception: pass
        self.schedule_scene_refresh(visual_only=True)


def _sw39_set_body_visual_attr(self, body, attr, value):
    if attr not in ('line_style', 'line_width', 'color'):
        return
    self.push_undo_state()
    setattr(body, attr, tuple(value) if attr == 'color' else value)
    for gr in _sw39_body_graphics(self, self.current_unit):
        st = getattr(gr, 'style', None)
        if st is None: continue
        if attr == 'line_style': st.line_style = value
        elif attr == 'line_width': st.line_width = float(value)
        elif attr == 'color': st.stroke = tuple(value)
    self.dirty = True
    try: self.update_current_unit_canvas_positions()
    except Exception: pass
    self.schedule_scene_refresh(visual_only=True)


def _sw39_apply_color_to_selected(self, color):
    selected = list(self.scene.selectedItems()) if hasattr(self, 'scene') else []
    if not selected:
        self.default_color = tuple(color); return
    self.push_undo_state()
    for it in selected:
        k = it.data(0); m = getattr(it, 'model', None)
        if m is None: continue
        if k == 'BODY':
            m.color = tuple(color)
            for gr in _sw39_body_graphics(self, self.current_unit):
                st = getattr(gr, 'style', None)
                if st is not None: st.stroke = tuple(color)
        elif k == 'GRAPHIC':
            st = getattr(m, 'style', None)
            if st is not None: st.stroke = tuple(color)
        elif k in ('PIN', 'TEXT', 'ATTR_REF_DES', 'ATTR_BODY'):
            try: m.color = tuple(color)
            except Exception: pass
            if k in ('ATTR_REF_DES', 'ATTR_BODY'):
                try: self._sync_body_font_from_attribute_text(it)
                except Exception: pass
    self.dirty = True
    try: self.update_current_unit_canvas_positions()
    except Exception: pass
    self.schedule_scene_refresh(visual_only=True)

try:
    MainWindow._body_owned_graphics = lambda self, body=None: _sw39_body_graphics(self, self.current_unit)
    MainWindow._set_body_width_grid = _sw39_set_body_width_grid
    MainWindow._set_body_height_grid = _sw39_set_body_height_grid
    MainWindow._transform_unit_as_body_group = _sw39_transform_unit_as_body_group
    MainWindow.scale_selected_grid = _sw39_scale_selected_grid
    MainWindow.scale_current_unit_children_from_body_resize = _sw39_scale_current_unit_children_from_body_resize
    MainWindow.apply_line_defaults = _sw39_apply_line_defaults
    MainWindow.set_body_visual_attr = _sw39_set_body_visual_attr
    MainWindow.apply_color_to_selected = _sw39_apply_color_to_selected
except Exception:
    pass


# ---------------------------------------------------------------------------
# Liebherr v44: BODY scaling from *_30 behavior, with pins kept unscaled.
# - Only BODY resize / Scale +/- is overridden here.
# - Rotate and flip continue to use the existing *_43 implementation.
# - Imported/template BODY primitives are scaled as one BODY shape; pins are
#   only re-docked to the new BODY edges and keep length/font/shape.
# - Adds the user-facing Clear Canvas alias for deleting all symbols.
# ---------------------------------------------------------------------------
def _lh44_clean(self, v):
    try:
        return self._clean_float(v)
    except Exception:
        try: return round(float(v), 6)
        except Exception: return v


def _lh44_edit_step(self):
    for name in ('edit_grid_step', 'grid_inch'):
        try:
            v = getattr(self, name, None)
            if v is not None:
                return max(0.001, float(v))
        except Exception:
            pass
    try:
        return max(0.001, float(self.edit_grid.value()))
    except Exception:
        return 1.0


def _lh44_snap(self, v):
    step = _lh44_edit_step(self)
    try: return _lh44_clean(self, round(float(v) / step) * step)
    except Exception: return float(v)


def _lh44_is_body_graphic(self, gr):
    try:
        # In the template editor the drawn graphics define the template BODY.
        if getattr(self, 'is_template_editor', False):
            return True
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        marker = str(getattr(gr, 'mentor_raw', '') or '')
        if role == 'user_graphic' or marker == '__USER_GRAPHIC__':
            return False
        return bool(getattr(gr, 'locked_to_body', False) or role in ('body', 'template_body', 'imported_body') or marker)
    except Exception:
        return False


def _lh44_body_graphics(self, unit=None):
    u = unit or getattr(self, 'current_unit', None)
    return [g for g in (getattr(u, 'graphics', []) or []) if _lh44_is_body_graphic(self, g)]


def _lh44_graphic_points(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    shape = str(getattr(gr, 'shape', '') or '')
    if shape in ('line', 'arc', 'curve'):
        pts = [(x, y), (x + w, y - h)]
        cx = getattr(gr, 'ctrl_x', None); cy = getattr(gr, 'ctrl_y', None)
        if cx is not None and cy is not None:
            pts.append((x + float(cx), y - float(cy)))
        else:
            cr = float(getattr(gr, 'curve_radius', 0.0) or 0.0)
            if abs(cr) > 1e-12:
                pts.append((x + w / 2.0, y - h / 2.0 + cr))
    else:
        pts = [(x, y), (x + w, y), (x + w, y - h), (x, y - h)]
    return pts


def _lh44_body_bounds(self, unit=None):
    u = unit or self.current_unit
    gs = _lh44_body_graphics(self, u)
    if not gs:
        b = u.body
        return (float(b.x), float(b.y), float(b.width), float(b.height))
    pts = []
    for g in gs:
        pts.extend(_lh44_graphic_points(g))
    if not pts:
        b = u.body
        return (float(b.x), float(b.y), float(b.width), float(b.height))
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return (_lh44_clean(self, min(xs)), _lh44_clean(self, max(ys)),
            _lh44_clean(self, max(0.01, max(xs) - min(xs))),
            _lh44_clean(self, max(0.01, max(ys) - min(ys))))


def _lh44_sync_body_to_graphics(self, unit=None):
    u = unit or self.current_unit
    if not _lh44_body_graphics(self, u):
        return
    x, y, w, h = _lh44_body_bounds(self, u)
    u.body.x, u.body.y, u.body.width, u.body.height = x, y, w, h
    try: u.body.rotation = 0.0
    except Exception: pass


def _lh44_scale_body_graphics_to(self, unit, old_bounds, new_bounds):
    gs = _lh44_body_graphics(self, unit)
    if not gs: return
    ox, oy, ow, oh = old_bounds; nx, ny, nw, nh = new_bounds
    sx = float(nw) / max(float(ow), 1e-9); sy = float(nh) / max(float(oh), 1e-9)
    def mp(x, y):
        return (_lh44_clean(self, nx + (float(x) - ox) * sx),
                _lh44_clean(self, ny - (oy - float(y)) * sy))
    for g in gs:
        x = float(getattr(g, 'x', 0.0) or 0.0); y = float(getattr(g, 'y', 0.0) or 0.0)
        w = float(getattr(g, 'w', 0.0) or 0.0); h = float(getattr(g, 'h', 0.0) or 0.0)
        x1, y1 = mp(x, y); x2, y2 = mp(x + w, y - h)
        g.x, g.y = x1, y1
        g.w, g.h = _lh44_clean(self, x2 - x1), _lh44_clean(self, y1 - y2)
        try:
            if getattr(g, 'ctrl_x', None) is not None: g.ctrl_x = _lh44_clean(self, float(g.ctrl_x) * sx)
            if getattr(g, 'ctrl_y', None) is not None: g.ctrl_y = _lh44_clean(self, float(g.ctrl_y) * sy)
            if getattr(g, 'curve_radius', None) is not None: g.curve_radius = _lh44_clean(self, float(g.curve_radius) * ((abs(sx)+abs(sy))/2.0))
        except Exception: pass
    _lh44_sync_body_to_graphics(self, unit)


def _lh44_move_pin_texts(self, pin, dx, dy):
    try:
        self._move_pin_owned_texts(pin, dx, dy); return
    except Exception:
        pass
    for ax, ay in (('label_x','label_y'), ('number_x','number_y')):
        try:
            if getattr(pin, ax, None) is not None and getattr(pin, ay, None) is not None:
                setattr(pin, ax, _lh44_clean(self, float(getattr(pin, ax)) + dx))
                setattr(pin, ay, _lh44_clean(self, float(getattr(pin, ay)) + dy))
        except Exception: pass
    for tm in (getattr(pin, 'attribute_texts', {}) or {}).values():
        try:
            tm.x = _lh44_clean(self, float(tm.x) + dx); tm.y = _lh44_clean(self, float(tm.y) + dy)
        except Exception: pass


def _lh44_capture_resize_state(self, unit=None):
    u = unit or self.current_unit; b = u.body
    return {
        'pins': [(p, float(p.x), float(p.y), float(getattr(p, 'length', 1.0) or 1.0)) for p in getattr(u, 'pins', []) or []],
        'texts': [(t, float(t.x), float(t.y)) for t in getattr(u, 'texts', []) or []],
        'attributes': [(t, float(t.x), float(t.y)) for t in (getattr(b, 'attribute_texts', {}) or {}).values()],
        'graphics': [(g, float(g.x), float(g.y), float(getattr(g, 'w', 0.0) or 0.0), float(getattr(g, 'h', 0.0) or 0.0)) for g in getattr(u, 'graphics', []) or [] if g not in _lh44_body_graphics(self, u)],
    }


def _lh44_redock_pins(self, unit, start, old_bounds, new_bounds):
    ox, oy, ow, oh = old_bounds; nx, ny, nw, nh = new_bounds
    sx = float(nw) / max(float(ow), 1e-9); sy = float(nh) / max(float(oh), 1e-9)
    for p, px, py, plen in start.get('pins', []) or []:
        old_px, old_py = float(getattr(p, 'x', px)), float(getattr(p, 'y', py))
        side = getattr(p, 'side', '')
        if side == PinSide.LEFT.value:
            tx, ty = nx, ny - (oy - py) * sy
        elif side == PinSide.RIGHT.value:
            tx, ty = nx + nw, ny - (oy - py) * sy
        elif side == PinSide.TOP.value:
            tx, ty = nx + (px - ox) * sx, ny
        elif side == PinSide.BOTTOM.value:
            tx, ty = nx + (px - ox) * sx, ny - nh
        else:
            tx, ty = nx + (px - ox) * sx, ny - (oy - py) * sy
        p.x, p.y = _lh44_snap(self, tx), _lh44_snap(self, ty)
        try: p.length = float(plen)
        except Exception: pass
        _lh44_move_pin_texts(self, p, p.x - old_px, p.y - old_py)


def _lh44_resize_body_geometry(self, new_w=None, new_h=None, refresh=True, anchor_bounds=None):
    if getattr(self, '_lh44_resizing_body', False): return
    self._lh44_resizing_body = True
    try:
        u = self.current_unit; b = u.body
        old_bounds = anchor_bounds or _lh44_body_bounds(self, u)
        ox, oy, ow, oh = old_bounds
        step = _lh44_edit_step(self)
        new_w = max(step, _lh44_snap(self, ow if new_w is None else new_w))
        new_h = max(step, _lh44_snap(self, oh if new_h is None else new_h))
        start = _lh44_capture_resize_state(self, u)
        new_bounds = (ox, oy, new_w, new_h)
        if _lh44_body_graphics(self, u):
            _lh44_scale_body_graphics_to(self, u, old_bounds, new_bounds)
        else:
            b.x, b.y, b.width, b.height = ox, oy, new_w, new_h
        _lh44_redock_pins(self, u, start, old_bounds, (b.x, b.y, b.width, b.height))
        nx, ny, nw, nh = float(b.x), float(b.y), float(b.width), float(b.height)
        sx = nw / max(float(ow), 1e-9); sy = nh / max(float(oh), 1e-9)
        def map_pos(x, y): return (_lh44_snap(self, nx + (float(x)-ox)*sx), _lh44_snap(self, ny - (oy-float(y))*sy))
        for t, tx, ty in start.get('texts', []) or []: t.x, t.y = map_pos(tx, ty)
        for t, tx, ty in start.get('attributes', []) or []: t.x, t.y = map_pos(tx, ty)
        for g, gx, gy, gw, gh in start.get('graphics', []) or []:
            g.x, g.y = map_pos(gx, gy); g.w, g.h = gw, gh
        try:
            if hasattr(u, '_body_group_transform'): delattr(u, '_body_group_transform')
        except Exception: pass
        self.dirty = True
    finally:
        self._lh44_resizing_body = False
    if refresh:
        try: self.update_current_unit_canvas_positions()
        except Exception: pass
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.rebuild_tree(); self.rebuild_pin_table()
        except Exception: pass
        try: self.refresh_properties()
        except Exception: pass
        try: self.schedule_scene_refresh(visual_only=True)
        except Exception:
            try: self.scene.update()
            except Exception: pass


def _lh44_set_body_width_grid(self, body, value):
    try:
        new_w = max(_lh44_edit_step(self), _lh44_snap(self, float(value)))
        cur_w = float(getattr(self.current_unit.body, 'width', new_w) or new_w)
        if abs(new_w - cur_w) < 1e-9: return
        self.push_undo_state(); self._selection_restore_ids = self._capture_selection_ids()
        _lh44_resize_body_geometry(self, new_w=new_w, new_h=None, refresh=True)
    except Exception as e:
        try: self.statusBar().showMessage(f'BODY width update failed: {e}', 4000)
        except Exception: pass


def _lh44_set_body_height_grid(self, body, value):
    try:
        new_h = max(_lh44_edit_step(self), _lh44_snap(self, float(value)))
        cur_h = float(getattr(self.current_unit.body, 'height', new_h) or new_h)
        if abs(new_h - cur_h) < 1e-9: return
        self.push_undo_state(); self._selection_restore_ids = self._capture_selection_ids()
        _lh44_resize_body_geometry(self, new_w=None, new_h=new_h, refresh=True)
    except Exception as e:
        try: self.statusBar().showMessage(f'BODY height update failed: {e}', 4000)
        except Exception: pass


def _lh44_transform_unit_as_body_group(self, op, value=None, refresh=True):
    if op in ('scale', 'scale_x_to', 'scale_y_to'):
        b = self.current_unit.body
        cur_w = float(getattr(b, 'width', 1.0) or 1.0); cur_h = float(getattr(b, 'height', 1.0) or 1.0)
        if op == 'scale_x_to': return _lh44_resize_body_geometry(self, new_w=float(value), new_h=None, refresh=refresh)
        if op == 'scale_y_to': return _lh44_resize_body_geometry(self, new_w=None, new_h=float(value), refresh=refresh)
        f = float(value or 1.0)
        return _lh44_resize_body_geometry(self, new_w=cur_w * f, new_h=cur_h * f, refresh=refresh)
    if _lh44_prev_transform_unit_as_body_group is not None:
        return _lh44_prev_transform_unit_as_body_group(self, op, value, refresh)


def _lh44_scale_selected_grid(self, direction: int):
    self.set_tool(DrawTool.SELECT.value)
    if self._selected_body_active():
        b = self.current_unit.body; step = _lh44_edit_step(self)
        self.push_undo_state(); self._selection_restore_ids = self._capture_selection_ids()
        _lh44_resize_body_geometry(self, float(b.width) + direction * step, float(b.height) + direction * step, refresh=True)
    else:
        if _lh44_prev_scale_selected_grid is not None:
            return _lh44_prev_scale_selected_grid(self, direction)
        return self.scale_selected(1.0 + (0.1 if direction > 0 else -0.1))


def _lh44_scale_current_unit_children_from_body_resize(self, start_state, body):
    try:
        old_bounds = (float(start_state.get('x', body.x)), float(start_state.get('y', body.y)),
                      max(float(start_state.get('w', body.width)), 1e-9), max(float(start_state.get('h', body.height)), 1e-9))
        _lh44_resize_body_geometry(self, new_w=float(body.width), new_h=float(body.height), refresh=True, anchor_bounds=old_bounds)
    except Exception as e:
        try: self.statusBar().showMessage(f'Canvas BODY scale failed: {e}', 4000)
        except Exception: pass


def _lh44_clear_canvas(self):
    return self.delete_all_symbols()


try:
    _lh44_prev_transform_unit_as_body_group = MainWindow._transform_unit_as_body_group
except Exception:
    _lh44_prev_transform_unit_as_body_group = None
try:
    _lh44_prev_scale_selected_grid = MainWindow.scale_selected_grid
except Exception:
    _lh44_prev_scale_selected_grid = None
try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._body_owned_graphics = lambda self, body=None: _lh44_body_graphics(self, self.current_unit)
        _cls._set_body_width_grid = _lh44_set_body_width_grid
        _cls._set_body_height_grid = _lh44_set_body_height_grid
        _cls._transform_unit_as_body_group = _lh44_transform_unit_as_body_group
        _cls.scale_selected_grid = _lh44_scale_selected_grid
        _cls.scale_current_unit_children_from_body_resize = _lh44_scale_current_unit_children_from_body_resize
        _cls.clear_canvas = _lh44_clear_canvas
except Exception:
    pass


# --- LH45 stability patch -------------------------------------------------
# Keep the property panel on the current selection during toolbar/property edits,
# avoid synchronous property-panel rebuilds from editor signals, and ensure BODY
# resize never scales pin length/font data.
def _lh45_selected_model_ids(self):
    try:
        return {id(getattr(i, 'model', None)) for i in self.scene.selectedItems() if getattr(i, 'model', None) is not None}
    except Exception:
        return set()


def _lh45_restore_selection(self, ids=None):
    ids = set(ids or getattr(self, '_selection_restore_ids', set()) or [])
    if not ids:
        return
    try:
        self.scene.blockSignals(True)
        for it in self.scene.items():
            try:
                it.setSelected(id(getattr(it, 'model', None)) in ids)
            except Exception:
                pass
    finally:
        try: self.scene.blockSignals(False)
        except Exception: pass
    try: self.view.viewport().update()
    except Exception: pass


def _lh45_deferred_refresh(self, ids=None):
    ids = set(ids or _lh45_selected_model_ids(self) or getattr(self, '_selection_restore_ids', set()) or [])
    def run():
        try: _lh45_restore_selection(self, ids)
        except Exception: pass
        try: self.refresh_properties()
        except RuntimeError: pass
        except Exception: pass
    try: QTimer.singleShot(0, run)
    except Exception: run()


def _lh45_capture_resize_state(self, unit=None):
    u = unit or self.current_unit; b = u.body
    pins = []
    for p in getattr(u, 'pins', []) or []:
        pins.append((p, float(p.x), float(p.y), float(getattr(p, 'length', 1.0) or 1.0),
                     float(getattr(getattr(p, 'number_font', None), 'size_grid', 0.45) or 0.45),
                     float(getattr(getattr(p, 'label_font', None), 'size_grid', 0.55) or 0.55)))
    return {
        'pins': pins,
        'texts': [(t, float(t.x), float(t.y)) for t in getattr(u, 'texts', []) or []],
        'attributes': [(t, float(t.x), float(t.y)) for t in (getattr(b, 'attribute_texts', {}) or {}).values()],
        'graphics': [(g, float(g.x), float(g.y), float(getattr(g, 'w', 0.0) or 0.0), float(getattr(g, 'h', 0.0) or 0.0)) for g in getattr(u, 'graphics', []) or [] if g not in _lh44_body_graphics(self, u)],
    }


def _lh45_redock_pins(self, unit, start, old_bounds, new_bounds):
    ox, oy, ow, oh = old_bounds; nx, ny, nw, nh = new_bounds
    sx = float(nw) / max(float(ow), 1e-9); sy = float(nh) / max(float(oh), 1e-9)
    for rec in start.get('pins', []) or []:
        p, px, py, plen = rec[:4]
        num_size = rec[4] if len(rec) > 4 else None
        lab_size = rec[5] if len(rec) > 5 else None
        old_px, old_py = float(getattr(p, 'x', px)), float(getattr(p, 'y', py))
        side = getattr(p, 'side', '')
        if side == PinSide.LEFT.value:
            tx, ty = nx, ny - (oy - py) * sy
        elif side == PinSide.RIGHT.value:
            tx, ty = nx + nw, ny - (oy - py) * sy
        elif side == PinSide.TOP.value:
            tx, ty = nx + (px - ox) * sx, ny
        elif side == PinSide.BOTTOM.value:
            tx, ty = nx + (px - ox) * sx, ny - nh
        else:
            tx, ty = nx + (px - ox) * sx, ny - (oy - py) * sy
        p.x, p.y = _lh44_snap(self, tx), _lh44_snap(self, ty)
        # Critical: pins are docked/repositioned to the BODY, but the pin itself
        # is never scaled. Keep length and label/number fonts exactly as before.
        try: p.length = float(plen)
        except Exception: pass
        try:
            if num_size is not None: p.number_font.size_grid = float(num_size)
        except Exception: pass
        try:
            if lab_size is not None: p.label_font.size_grid = float(lab_size)
        except Exception: pass
        _lh44_move_pin_texts(self, p, p.x - old_px, p.y - old_py)


def _lh45_resize_body_geometry(self, new_w=None, new_h=None, refresh=True, anchor_bounds=None):
    if getattr(self, '_lh44_resizing_body', False): return
    keep_ids = set(getattr(self, '_selection_restore_ids', set()) or _lh45_selected_model_ids(self))
    self._lh44_resizing_body = True
    try:
        u = self.current_unit; b = u.body
        old_bounds = anchor_bounds or _lh44_body_bounds(self, u)
        ox, oy, ow, oh = old_bounds
        step = _lh44_edit_step(self)
        new_w = max(step, _lh44_snap(self, ow if new_w is None else new_w))
        new_h = max(step, _lh44_snap(self, oh if new_h is None else new_h))
        start = _lh45_capture_resize_state(self, u)
        new_bounds = (ox, oy, new_w, new_h)
        if _lh44_body_graphics(self, u):
            _lh44_scale_body_graphics_to(self, u, old_bounds, new_bounds)
        else:
            b.x, b.y, b.width, b.height = ox, oy, new_w, new_h
        _lh45_redock_pins(self, u, start, old_bounds, (b.x, b.y, b.width, b.height))
        nx, ny, nw, nh = float(b.x), float(b.y), float(b.width), float(b.height)
        sx = nw / max(float(ow), 1e-9); sy = nh / max(float(oh), 1e-9)
        def map_pos(x, y): return (_lh44_snap(self, nx + (float(x)-ox)*sx), _lh44_snap(self, ny - (oy-float(y))*sy))
        for t, tx, ty in start.get('texts', []) or []: t.x, t.y = map_pos(tx, ty)
        for t, tx, ty in start.get('attributes', []) or []: t.x, t.y = map_pos(tx, ty)
        for g, gx, gy, gw, gh in start.get('graphics', []) or []:
            g.x, g.y = map_pos(gx, gy); g.w, g.h = gw, gh
        try:
            if hasattr(u, '_body_group_transform'): delattr(u, '_body_group_transform')
        except Exception: pass
        self.dirty = True
    finally:
        self._lh44_resizing_body = False
    if refresh:
        try: self.update_current_unit_canvas_positions()
        except Exception: pass
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.rebuild_tree(); self.rebuild_pin_table()
        except Exception: pass
        try: self.schedule_scene_refresh(visual_only=True)
        except Exception:
            try: self.scene.update()
            except Exception: pass
        _lh45_deferred_refresh(self, keep_ids)


def _lh45_set_body_width_grid(self, body, value):
    try:
        keep_ids = _lh45_selected_model_ids(self) or {id(body)}
        new_w = max(_lh44_edit_step(self), _lh44_snap(self, float(value)))
        cur_w = float(getattr(self.current_unit.body, 'width', new_w) or new_w)
        if abs(new_w - cur_w) < 1e-9: return
        self.push_undo_state(); self._selection_restore_ids = keep_ids
        _lh45_resize_body_geometry(self, new_w=new_w, new_h=None, refresh=True)
    except Exception as e:
        try: self.statusBar().showMessage(f'BODY width update failed: {e}', 4000)
        except Exception: pass


def _lh45_set_body_height_grid(self, body, value):
    try:
        keep_ids = _lh45_selected_model_ids(self) or {id(body)}
        new_h = max(_lh44_edit_step(self), _lh44_snap(self, float(value)))
        cur_h = float(getattr(self.current_unit.body, 'height', new_h) or new_h)
        if abs(new_h - cur_h) < 1e-9: return
        self.push_undo_state(); self._selection_restore_ids = keep_ids
        _lh45_resize_body_geometry(self, new_w=None, new_h=new_h, refresh=True)
    except Exception as e:
        try: self.statusBar().showMessage(f'BODY height update failed: {e}', 4000)
        except Exception: pass


def _lh45_transform_unit_as_body_group(self, op, value=None, refresh=True):
    if op in ('scale', 'scale_x_to', 'scale_y_to'):
        b = self.current_unit.body
        cur_w = float(getattr(b, 'width', 1.0) or 1.0); cur_h = float(getattr(b, 'height', 1.0) or 1.0)
        if op == 'scale_x_to': return _lh45_resize_body_geometry(self, new_w=float(value), new_h=None, refresh=refresh)
        if op == 'scale_y_to': return _lh45_resize_body_geometry(self, new_w=None, new_h=float(value), refresh=refresh)
        f = float(value or 1.0)
        return _lh45_resize_body_geometry(self, new_w=cur_w * f, new_h=cur_h * f, refresh=refresh)
    if _lh44_prev_transform_unit_as_body_group is not None:
        keep_ids = _lh45_selected_model_ids(self)
        r = _lh44_prev_transform_unit_as_body_group(self, op, value, refresh)
        _lh45_deferred_refresh(self, keep_ids)
        return r


def _lh45_scale_selected_grid(self, direction: int):
    self.set_tool(DrawTool.SELECT.value)
    if self._selected_body_active():
        b = self.current_unit.body; step = _lh44_edit_step(self)
        keep_ids = _lh45_selected_model_ids(self) or {id(b)}
        self.push_undo_state(); self._selection_restore_ids = keep_ids
        _lh45_resize_body_geometry(self, float(b.width) + direction * step, float(b.height) + direction * step, refresh=True)
    else:
        if _lh44_prev_scale_selected_grid is not None:
            keep_ids = _lh45_selected_model_ids(self)
            r = _lh44_prev_scale_selected_grid(self, direction)
            _lh45_deferred_refresh(self, keep_ids)
            return r
        return self.scale_selected(1.0 + (0.1 if direction > 0 else -0.1))


def _lh45_scale_current_unit_children_from_body_resize(self, start_state, body):
    try:
        keep_ids = _lh45_selected_model_ids(self) or {id(body)}
        self._selection_restore_ids = keep_ids
        old_bounds = (float(start_state.get('x', body.x)), float(start_state.get('y', body.y)),
                      max(float(start_state.get('w', body.width)), 1e-9), max(float(start_state.get('h', body.height)), 1e-9))
        _lh45_resize_body_geometry(self, new_w=float(body.width), new_h=float(body.height), refresh=True, anchor_bounds=old_bounds)
    except Exception as e:
        try: self.statusBar().showMessage(f'Canvas BODY scale failed: {e}', 4000)
        except Exception: pass


def _lh45_set_safe(self, m, a, v):
    keep_ids = _lh45_selected_model_ids(self) or {id(m)}
    try: self.push_undo_state()
    except Exception: pass
    self._selection_restore_ids = keep_ids
    try:
        if a == 'rotation': v = (round(float(v) / 15.0) * 15.0) % 360
        setattr(m, a, v)
        self.dirty = True
        self.update_current_unit_canvas_positions()
    except Exception as e:
        try: self.statusBar().showMessage(f'Property update failed: {e}', 4000)
        except Exception: pass
    _lh45_deferred_refresh(self, keep_ids)

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._set_body_width_grid = _lh45_set_body_width_grid
        _cls._set_body_height_grid = _lh45_set_body_height_grid
        _cls._transform_unit_as_body_group = _lh45_transform_unit_as_body_group
        _cls.scale_selected_grid = _lh45_scale_selected_grid
        _cls.scale_current_unit_children_from_body_resize = _lh45_scale_current_unit_children_from_body_resize
        _cls._set = _lh45_set_safe
except Exception:
    pass

# --- LH46 robustness patch -------------------------------------------------
# Fixes:
# - Property panel spinbox arrow buttons / combo / checkbox callbacks are guarded
#   against stale Qt widgets and do not synchronously rebuild the panel.
# - Toolbar Scale +/- and property edits restore the exact current selection view
#   instead of switching to a multi-selection message.
# - BODY scaling restores only the BODY selection and never selects pins/body-owned
#   helper graphics as a side effect.

def _lh46_selected_signature(self):
    sig = []
    try:
        for it in self.scene.selectedItems():
            kind = it.data(0)
            model = getattr(it, 'model', None)
            body_model = getattr(it, '_body_model', None)
            sig.append((str(kind), id(model) if model is not None else None, id(body_model) if body_model is not None else None))
    except Exception:
        pass
    return sig


def _lh46_restore_selection_signature(self, sig=None):
    sig = list(sig or getattr(self, '_lh46_selection_signature', []) or [])
    model_ids = {s[1] for s in sig if s[1] is not None}
    body_ids = {s[2] for s in sig if s[2] is not None}
    body_was_selected = any(s[0] in ('BODY', 'BODY_GRAPHIC') for s in sig)
    selected_one_body = False
    try:
        self.scene.blockSignals(True)
        for it in self.scene.items():
            try: it.setSelected(False)
            except Exception: pass
        # BODY can be represented by a generated BODY item or by one body-owned
        # graphic item. Select exactly one visual BODY representative so the
        # property panel stays on "Selected: BODY" and never flips to multi-edit.
        if body_was_selected:
            preferred = None
            for it in self.scene.items():
                try:
                    kind = it.data(0)
                    m = getattr(it, 'model', None)
                    bm = getattr(it, '_body_model', None)
                    if kind == 'BODY' and (id(m) in model_ids or m is getattr(self.current_unit, 'body', None)):
                        preferred = it; break
                    if kind == 'BODY_GRAPHIC' and (id(bm) in body_ids or bm is getattr(self.current_unit, 'body', None)) and preferred is None:
                        preferred = it
                except Exception:
                    pass
            if preferred is not None:
                try: preferred.setSelected(True); selected_one_body = True
                except Exception: pass
        if not selected_one_body:
            for it in self.scene.items():
                try:
                    m = getattr(it, 'model', None)
                    if m is not None and id(m) in model_ids:
                        it.setSelected(True)
                except Exception:
                    pass
    finally:
        try: self.scene.blockSignals(False)
        except Exception: pass
    try: self.view.viewport().update()
    except Exception: pass


def _lh46_deferred_restore_only(self, sig=None):
    sig = list(sig or _lh46_selected_signature(self) or getattr(self, '_lh46_selection_signature', []) or [])
    self._lh46_selection_signature = sig
    def run():
        try: _lh46_restore_selection_signature(self, sig)
        except Exception: pass
    try: QTimer.singleShot(0, run)
    except Exception: run()


def _lh46_dbl(self, value, fn, lo=-999, hi=999, step=.1):
    w = QDoubleSpinBox()
    w.setRange(lo, hi)
    w.setSingleStep(step)
    w.setDecimals(3)
    w.setKeyboardTracking(False)
    try: w.setValue(float(value))
    except Exception: w.setValue(0.0)
    def safe(v):
        try:
            sig = _lh46_selected_signature(self)
            self._lh46_selection_signature = sig
            fn(float(v))
            _lh46_deferred_restore_only(self, sig)
        except RuntimeError:
            pass
        except Exception as e:
            try: self.statusBar().showMessage(f'Property update failed: {e}', 4000)
            except Exception: pass
    w.valueChanged.connect(safe)
    return w


def _lh46_combo(self, items, val, fn):
    w = QComboBox(); w.addItems(items); w.setCurrentText(str(val))
    def safe(v):
        try:
            sig = _lh46_selected_signature(self); self._lh46_selection_signature = sig
            fn(v)
            _lh46_deferred_restore_only(self, sig)
        except RuntimeError:
            pass
        except Exception as e:
            try: self.statusBar().showMessage(f'Property update failed: {e}', 4000)
            except Exception: pass
    w.currentTextChanged.connect(safe)
    return w


def _lh46_check(self, value, fn):
    w = QCheckBox(); w.setChecked(bool(value))
    def safe(v):
        try:
            sig = _lh46_selected_signature(self); self._lh46_selection_signature = sig
            fn(bool(v))
            _lh46_deferred_restore_only(self, sig)
        except RuntimeError:
            pass
        except Exception as e:
            try: self.statusBar().showMessage(f'Property update failed: {e}', 4000)
            except Exception: pass
    w.toggled.connect(safe)
    return w


def _lh46_set_safe(self, m, a, v):
    sig = _lh46_selected_signature(self) or getattr(self, '_lh46_selection_signature', [])
    try: self.push_undo_state()
    except Exception: pass
    try:
        if a == 'rotation': v = (round(float(v) / 15.0) * 15.0) % 360
        setattr(m, a, v)
        self.dirty = True
        try: self.update_current_unit_canvas_positions()
        except Exception: pass
        try: self.schedule_scene_refresh(visual_only=True)
        except Exception:
            try: self.scene.update()
            except Exception: pass
    except Exception as e:
        try: self.statusBar().showMessage(f'Property update failed: {e}', 4000)
        except Exception: pass
    _lh46_deferred_restore_only(self, sig)


def _lh46_resize_body_geometry(self, new_w=None, new_h=None, refresh=True, anchor_bounds=None):
    sig = _lh46_selected_signature(self) or getattr(self, '_lh46_selection_signature', [])
    # Reuse the LH45 geometry implementation, but afterwards force exact BODY
    # selection restore and deliberately avoid rebuilding the property panel.
    r = _lh45_resize_body_geometry(self, new_w=new_w, new_h=new_h, refresh=refresh, anchor_bounds=anchor_bounds)
    _lh46_deferred_restore_only(self, sig)
    return r


def _lh46_transform_unit_as_body_group(self, op, value=None, refresh=True):
    sig = _lh46_selected_signature(self)
    if op in ('scale', 'scale_x_to', 'scale_y_to'):
        b = self.current_unit.body
        cur_w = float(getattr(b, 'width', 1.0) or 1.0); cur_h = float(getattr(b, 'height', 1.0) or 1.0)
        if op == 'scale_x_to': r = _lh46_resize_body_geometry(self, new_w=float(value), new_h=None, refresh=refresh)
        elif op == 'scale_y_to': r = _lh46_resize_body_geometry(self, new_w=None, new_h=float(value), refresh=refresh)
        else:
            f = float(value or 1.0); r = _lh46_resize_body_geometry(self, new_w=cur_w * f, new_h=cur_h * f, refresh=refresh)
        _lh46_deferred_restore_only(self, sig)
        return r
    if _lh44_prev_transform_unit_as_body_group is not None:
        r = _lh44_prev_transform_unit_as_body_group(self, op, value, refresh)
        _lh46_deferred_restore_only(self, sig)
        return r


def _lh46_scale_selected_grid(self, direction: int):
    sig = _lh46_selected_signature(self)
    try: self.set_tool(DrawTool.SELECT.value)
    except Exception: pass
    if self._selected_body_active():
        b = self.current_unit.body; step = _lh44_edit_step(self)
        try: self.push_undo_state()
        except Exception: pass
        r = _lh46_resize_body_geometry(self, float(b.width) + direction * step, float(b.height) + direction * step, refresh=True)
        _lh46_deferred_restore_only(self, sig)
        return r
    try:
        if _lh44_prev_scale_selected_grid is not None:
            r = _lh44_prev_scale_selected_grid(self, direction)
        else:
            r = self.scale_selected(1.0 + (0.1 if direction > 0 else -0.1))
    finally:
        _lh46_deferred_restore_only(self, sig)
    return r


def _lh46_scale_current_unit_children_from_body_resize(self, start_state, body):
    sig = _lh46_selected_signature(self) or getattr(self, '_lh46_selection_signature', [])
    try:
        old_bounds = (float(start_state.get('x', body.x)), float(start_state.get('y', body.y)),
                      max(float(start_state.get('w', body.width)), 1e-9), max(float(start_state.get('h', body.height)), 1e-9))
        return _lh46_resize_body_geometry(self, new_w=float(body.width), new_h=float(body.height), refresh=True, anchor_bounds=old_bounds)
    except Exception as e:
        try: self.statusBar().showMessage(f'Canvas BODY scale failed: {e}', 4000)
        except Exception: pass
    finally:
        _lh46_deferred_restore_only(self, sig)

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._dbl = _lh46_dbl
        _cls._combo = _lh46_combo
        _cls._check = _lh46_check
        _cls._set = _lh46_set_safe
        _cls._transform_unit_as_body_group = _lh46_transform_unit_as_body_group
        _cls.scale_selected_grid = _lh46_scale_selected_grid
        _cls.scale_current_unit_children_from_body_resize = _lh46_scale_current_unit_children_from_body_resize
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v47: keep Selectable/selection/property panel stable and make all
# property widgets crash-safe.
# ---------------------------------------------------------------------------

def _lh47_selection_filter_state(self):
    try:
        mode = self.selection_mode_combo.currentText() if hasattr(self, 'selection_mode_combo') else None
    except Exception:
        mode = None
    try:
        enabled = dict(getattr(self, 'selection_enabled', {}) or {})
    except Exception:
        enabled = {}
    return mode, enabled


def _lh47_restore_selection_filter_state(self, state):
    mode, enabled = state or (None, {})
    try:
        if enabled:
            self.selection_enabled.update(enabled)
    except Exception:
        pass
    try:
        if mode is not None and hasattr(self, 'selection_mode_combo'):
            self.selection_mode_combo.blockSignals(True)
            self.selection_mode_combo.setCurrentText(mode)
            self.selection_mode_combo.blockSignals(False)
    except Exception:
        try: self.selection_mode_combo.blockSignals(False)
        except Exception: pass
    try:
        if mode == 'Custom' and hasattr(self, 'selection_custom_checks'):
            for k, cb in self.selection_custom_checks.items():
                cb.blockSignals(True); cb.setChecked(bool(self.selection_enabled.get(k, False))); cb.blockSignals(False)
        elif hasattr(self, 'selection_custom_checks'):
            for k, cb in self.selection_custom_checks.items():
                cb.blockSignals(True); cb.setChecked(bool(self.selection_enabled.get(k, False))); cb.blockSignals(False)
    except Exception:
        pass


def _lh47_is_body_like_item(it):
    try:
        if it.data(0) in ('BODY', 'BODY_GRAPHIC'):
            return True
        m = getattr(it, 'model', None)
        return bool(m is not None and (getattr(m, 'locked_to_body', False) or str(getattr(m, 'graphic_role', '') or '').lower() in ('body','template_body','imported_body')))
    except Exception:
        return False


def _lh47_select_one_logical_body(self):
    try:
        preferred = None
        fallback = None
        cur_body = getattr(getattr(self, 'current_unit', None), 'body', None)
        for it in list(self.scene.items()):
            try:
                k = it.data(0)
                if k == 'BODY' and (getattr(it, 'model', None) is cur_body or preferred is None):
                    preferred = it
                    if getattr(it, 'model', None) is cur_body:
                        break
                elif k == 'BODY_GRAPHIC' and fallback is None:
                    fallback = it
            except Exception:
                pass
        target = preferred or fallback
        if target is None:
            return False
        self.scene.blockSignals(True)
        try:
            for it in self.scene.items():
                try: it.setSelected(False)
                except Exception: pass
            target.setSelected(True)
        finally:
            self.scene.blockSignals(False)
        try: self.view.viewport().update()
        except Exception: pass
        return True
    except Exception:
        try: self.scene.blockSignals(False)
        except Exception: pass
        return False


def _lh47_restore_selection_after_action(self, sig=None, filter_state=None, force_body=False, refresh=True):
    def run():
        try:
            if filter_state is not None:
                _lh47_restore_selection_filter_state(self, filter_state)
            body_before = force_body or any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in (sig or []))
            if body_before:
                _lh47_select_one_logical_body(self)
            elif sig:
                try:
                    ids = {s[1] for s in sig if len(s) > 1 and s[1] is not None}
                    self.scene.blockSignals(True)
                    for it in self.scene.items():
                        try: it.setSelected(False)
                        except Exception: pass
                    for it in self.scene.items():
                        try:
                            if id(getattr(it, 'model', None)) in ids:
                                it.setSelected(True)
                        except Exception:
                            pass
                finally:
                    try: self.scene.blockSignals(False)
                    except Exception: pass
            if refresh:
                try: self.refresh_properties()
                except Exception: pass
        except Exception as e:
            try: self.statusBar().showMessage(f'Selection restore failed: {e}', 3000)
            except Exception: pass
    try: QTimer.singleShot(0, run)
    except Exception: run()


def _lh47_with_selection_stable(self, work, force_body=False):
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    filter_state = _lh47_selection_filter_state(self)
    try:
        return work()
    finally:
        _lh47_restore_selection_after_action(self, sig=sig, filter_state=filter_state, force_body=force_body)


try:
    _lh47_prev_rotate_selected = MainWindow.rotate_selected
    _lh47_prev_flip_selected_horizontal = MainWindow.flip_selected_horizontal
    _lh47_prev_flip_selected_vertical = MainWindow.flip_selected_vertical
    _lh47_prev_scale_selected_grid = MainWindow.scale_selected_grid
    _lh47_prev_scale_selected = MainWindow.scale_selected
except Exception:
    _lh47_prev_rotate_selected = _lh47_prev_flip_selected_horizontal = _lh47_prev_flip_selected_vertical = None
    _lh47_prev_scale_selected_grid = _lh47_prev_scale_selected = None


def _lh47_rotate_selected(self, deg):
    return _lh47_with_selection_stable(self, lambda: _lh47_prev_rotate_selected(self, deg), force_body=bool(self._selected_body_active()))


def _lh47_flip_selected_horizontal(self):
    return _lh47_with_selection_stable(self, lambda: _lh47_prev_flip_selected_horizontal(self), force_body=bool(self._selected_body_active()))


def _lh47_flip_selected_vertical(self):
    return _lh47_with_selection_stable(self, lambda: _lh47_prev_flip_selected_vertical(self), force_body=bool(self._selected_body_active()))


def _lh47_scale_selected_grid(self, direction:int):
    def work():
        # Pins must never be geometrically scaled. If BODY is part of the current
        # selection, route exclusively through BODY resize/redock. If only pins
        # are selected, Scale +/- is a no-op for them.
        try:
            if self._selected_body_active():
                return _lh47_prev_scale_selected_grid(self, direction)
            selected = list(self.scene.selectedItems())
            if selected and all(getattr(i, 'data', lambda *_: None)(0) == 'PIN' for i in selected):
                try: self.statusBar().showMessage('Pins are not scaled by Scale +/-; edit pin length explicitly.', 2500)
                except Exception: pass
                return None
        except Exception:
            pass
        return _lh47_prev_scale_selected_grid(self, direction)
    return _lh47_with_selection_stable(self, work, force_body=bool(self._selected_body_active()))


def _lh47_scale_selected(self, factor):
    def work():
        try:
            if self._selected_body_active():
                return _lh47_prev_scale_selected(self, factor)
            selected = list(self.scene.selectedItems())
            if selected and all(getattr(i, 'data', lambda *_: None)(0) == 'PIN' for i in selected):
                try: self.statusBar().showMessage('Pins are not scaled; edit pin length explicitly.', 2500)
                except Exception: pass
                return None
        except Exception:
            pass
        return _lh47_prev_scale_selected(self, factor)
    return _lh47_with_selection_stable(self, work, force_body=bool(self._selected_body_active()))


# More conservative property widgets: no synchronous form rebuild from inside
# the editor signal, and no signal during initial value population.
def _lh47_dbl(self, value, fn, lo=-999, hi=999, step=.1):
    w = QDoubleSpinBox()
    w.setRange(lo, hi); w.setSingleStep(step); w.setDecimals(3); w.setKeyboardTracking(False)
    w.blockSignals(True)
    try: w.setValue(float(value))
    except Exception: w.setValue(0.0)
    w.blockSignals(False)
    def safe(v):
        sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
        fs = _lh47_selection_filter_state(self)
        def do():
            try:
                fn(float(v))
            except RuntimeError:
                return
            except Exception as e:
                try: self.statusBar().showMessage(f'Property update failed: {e}', 5000)
                except Exception: pass
            finally:
                _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in sig), refresh=False)
        try: QTimer.singleShot(0, do)
        except Exception: do()
    w.valueChanged.connect(safe)
    return w


def _lh47_combo(self, items, val, fn):
    w = QComboBox(); w.blockSignals(True); w.addItems([str(x) for x in items]); w.setCurrentText(str(val)); w.blockSignals(False)
    def safe(v):
        sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
        fs = _lh47_selection_filter_state(self)
        def do():
            try: fn(v)
            except RuntimeError: return
            except Exception as e:
                try: self.statusBar().showMessage(f'Property update failed: {e}', 5000)
                except Exception: pass
            finally:
                _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in sig), refresh=False)
        try: QTimer.singleShot(0, do)
        except Exception: do()
    w.currentTextChanged.connect(safe)
    return w


def _lh47_check(self, value, fn):
    w = QCheckBox(); w.blockSignals(True); w.setChecked(bool(value)); w.blockSignals(False)
    def safe(v):
        sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
        fs = _lh47_selection_filter_state(self)
        def do():
            try: fn(bool(v))
            except RuntimeError: return
            except Exception as e:
                try: self.statusBar().showMessage(f'Property update failed: {e}', 5000)
                except Exception: pass
            finally:
                _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in sig), refresh=False)
        try: QTimer.singleShot(0, do)
        except Exception: do()
    w.toggled.connect(safe)
    return w


def _lh47_set_safe(self, m, a, v):
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    fs = _lh47_selection_filter_state(self)
    try: self.push_undo_state()
    except Exception: pass
    try:
        if a == 'rotation':
            v = (round(float(v) / 15.0) * 15.0) % 360
        setattr(m, a, v)
        self.dirty = True
        try: self.update_current_unit_canvas_positions()
        except Exception: pass
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.scene.update()
        except Exception: pass
        try: self.view.viewport().update()
        except Exception: pass
    except Exception as e:
        try: self.statusBar().showMessage(f'Property update failed: {e}', 5000)
        except Exception: pass
    _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in sig), refresh=False)


try:
    _lh47_prev_set_attr_vis = MainWindow._set_attr_vis
    _lh47_prev_set_attr_val = MainWindow._set_attr_val
except Exception:
    _lh47_prev_set_attr_vis = _lh47_prev_set_attr_val = None


def _lh47_set_attr_vis(self, key, val):
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    fs = _lh47_selection_filter_state(self)
    try:
        self.push_undo_state()
        self.current_unit.body.visible_attributes[key] = bool(val)
        self.dirty = True
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.scene.update(); self.view.viewport().update()
        except Exception: pass
    except Exception as e:
        try: self.statusBar().showMessage(f'Attribute update failed: {e}', 5000)
        except Exception: pass
    _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in sig), refresh=False)


def _lh47_set_attr_val(self, key, val):
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    fs = _lh47_selection_filter_state(self)
    try:
        self.push_undo_state()
        self.current_unit.body.attributes[key] = str(val)
        self.dirty = True
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.scene.update(); self.view.viewport().update()
        except Exception: pass
    except Exception as e:
        try: self.statusBar().showMessage(f'Attribute update failed: {e}', 5000)
        except Exception: pass
    _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in sig), refresh=False)


try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls._dbl = _lh47_dbl
        _cls._combo = _lh47_combo
        _cls._check = _lh47_check
        _cls._set = _lh47_set_safe
        _cls.rotate_selected = _lh47_rotate_selected
        _cls.flip_selected_horizontal = _lh47_flip_selected_horizontal
        _cls.flip_selected_vertical = _lh47_flip_selected_vertical
        _cls.scale_selected_grid = _lh47_scale_selected_grid
        _cls.scale_selected = _lh47_scale_selected
    MainWindow._set_attr_vis = _lh47_set_attr_vis
    MainWindow._set_attr_val = _lh47_set_attr_val
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v48 rebuilt: keep the Selectable view absolutely stable and sync
# the global line controls with the current graphical selection.
# ---------------------------------------------------------------------------

_LH48_MULTIPLE = '<Multiple>'


def _lh48_kind(item):
    try:
        k = item.data(0)
    except Exception:
        k = None
    if k in ('BODY_GRAPHIC',):
        return 'BODY'
    return k


def _lh48_graphical_selected_items(self):
    try:
        items = list(self.scene.selectedItems())
    except Exception:
        return []
    out = []
    for it in items:
        k = _lh48_kind(it)
        if k in ('BODY', 'PIN', 'GRAPHIC') and getattr(it, 'model', None) is not None:
            out.append(it)
    return out


def _lh48_line_value(item, attr):
    m = getattr(item, 'model', None)
    if m is None:
        return None
    k = _lh48_kind(item)
    try:
        if k == 'GRAPHIC':
            st = getattr(m, 'style', None)
            return getattr(st, attr, None)
        return getattr(m, attr, None)
    except Exception:
        return None


def _lh48_common(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None, False
    first = vals[0]
    return first, all(v == first for v in vals)


def _lh48_sync_style_toolbar_to_selection(self):
    """Show common selected line style/width, or <Multiple> on mismatches.

    This is display-only. Signals are blocked so the Selectable mode and the
    selected objects are not changed just because the panel is being updated.
    """
    if not hasattr(self, 'line_style') or not hasattr(self, 'line_width'):
        return
    items = _lh48_graphical_selected_items(self)
    if not items:
        return
    style_val, style_same = _lh48_common([_lh48_line_value(i, 'line_style') for i in items])
    width_val, width_same = _lh48_common([_lh48_line_value(i, 'line_width') for i in items])
    try:
        self.line_style.blockSignals(True)
        idx = self.line_style.findText(_LH48_MULTIPLE)
        if style_same and style_val is not None:
            if idx >= 0:
                self.line_style.removeItem(idx)
            self.line_style.setCurrentText(str(style_val))
        else:
            if idx < 0:
                self.line_style.insertItem(0, _LH48_MULTIPLE)
            self.line_style.setCurrentText(_LH48_MULTIPLE)
    except Exception:
        pass
    finally:
        try: self.line_style.blockSignals(False)
        except Exception: pass
    try:
        self.line_width.blockSignals(True)
        if width_same and width_val is not None:
            self.line_width.setMinimum(0.01)
            self.line_width.setSpecialValueText('')
            self.line_width.setValue(float(width_val))
        else:
            self.line_width.setMinimum(0.0)
            self.line_width.setSpecialValueText(_LH48_MULTIPLE)
            self.line_width.setValue(0.0)
    except Exception:
        pass
    finally:
        try: self.line_width.blockSignals(False)
        except Exception: pass


try:
    _lh48_prev_on_scene_selection_changed = MainWindow.on_scene_selection_changed
except Exception:
    _lh48_prev_on_scene_selection_changed = None


def _lh48_on_scene_selection_changed(self):
    mode_state = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    try:
        if _lh48_prev_on_scene_selection_changed is not None:
            _lh48_prev_on_scene_selection_changed(self)
        else:
            self.refresh_properties()
    except Exception as e:
        try: self.statusBar().showMessage(f'Selection update failed: {e}', 4000)
        except Exception: pass
    finally:
        if mode_state is not None and '_lh47_restore_selection_filter_state' in globals():
            _lh47_restore_selection_filter_state(self, mode_state)
        _lh48_sync_style_toolbar_to_selection(self)


try:
    _lh48_prev_apply_line_defaults = MainWindow.apply_line_defaults
except Exception:
    _lh48_prev_apply_line_defaults = None


def _lh48_apply_line_defaults(self):
    # The placeholder is not a real line style. It appears only when selected
    # objects have different values. Ignore it until the user chooses a real one.
    try:
        if hasattr(self, 'line_style') and self.line_style.currentText() == _LH48_MULTIPLE:
            return
        if hasattr(self, 'line_width') and float(self.line_width.value()) <= 0.0:
            return
    except Exception:
        return
    mode_state = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    try:
        if _lh48_prev_apply_line_defaults is not None:
            return _lh48_prev_apply_line_defaults(self)
    except Exception as e:
        try: self.statusBar().showMessage(f'Line style update failed: {e}', 5000)
        except Exception: pass
    finally:
        if mode_state is not None and '_lh47_restore_selection_filter_state' in globals():
            _lh47_restore_selection_filter_state(self, mode_state)
        if '_lh47_restore_selection_after_action' in globals():
            _lh47_restore_selection_after_action(self, sig=sig, filter_state=mode_state, force_body=any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in sig), refresh=False)
        try: QTimer.singleShot(0, lambda: _lh48_sync_style_toolbar_to_selection(self))
        except Exception: pass


try:
    _lh48_prev_set_attr_vis = MainWindow._set_attr_vis
    _lh48_prev_set_attr_val = MainWindow._set_attr_val
except Exception:
    _lh48_prev_set_attr_vis = _lh48_prev_set_attr_val = None


def _lh48_set_attr_vis(self, key, val):
    mode_state = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    try:
        self.push_undo_state()
        self.current_unit.body.visible_attributes[key] = bool(val)
        self.dirty = True
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.scene.update(); self.view.viewport().update()
        except Exception: pass
    except Exception as e:
        try: self.statusBar().showMessage(f'Attribute update failed: {e}', 5000)
        except Exception: pass
    finally:
        if mode_state is not None and '_lh47_restore_selection_filter_state' in globals():
            _lh47_restore_selection_filter_state(self, mode_state)
        if '_lh47_restore_selection_after_action' in globals():
            _lh47_restore_selection_after_action(self, sig=sig, filter_state=mode_state, force_body=any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in sig), refresh=False)


def _lh48_set_attr_val(self, key, val):
    mode_state = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    try:
        self.push_undo_state()
        self.current_unit.body.attributes[key] = str(val)
        self.dirty = True
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.scene.update(); self.view.viewport().update()
        except Exception: pass
    except Exception as e:
        try: self.statusBar().showMessage(f'Attribute update failed: {e}', 5000)
        except Exception: pass
    finally:
        if mode_state is not None and '_lh47_restore_selection_filter_state' in globals():
            _lh47_restore_selection_filter_state(self, mode_state)
        if '_lh47_restore_selection_after_action' in globals():
            _lh47_restore_selection_after_action(self, sig=sig, filter_state=mode_state, force_body=any(str(s[0]) in ('BODY','BODY_GRAPHIC') for s in sig), refresh=False)


try:
    MainWindow.on_scene_selection_changed = _lh48_on_scene_selection_changed
    MainWindow.apply_line_defaults = _lh48_apply_line_defaults
    MainWindow._set_attr_vis = _lh48_set_attr_vis
    MainWindow._set_attr_val = _lh48_set_attr_val
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v50: BODY property edits must never leave the BODY selection view.
# ---------------------------------------------------------------------------

def _lh50_property_panel_kind(self):
    """Return the currently displayed property panel kind, e.g. BODY.

    This is deliberately independent from the live scene selection because some
    body-attribute updates temporarily recreate ATTR_* items and Qt can emit a
    transient multi-selection.  The user's visible context is the authoritative
    context for property widget callbacks.
    """
    try:
        if not hasattr(self, 'form') or self.form is None or self.form.rowCount() <= 0:
            return None
        item = self.form.itemAt(0, QFormLayout.LabelRole) or self.form.itemAt(0, QFormLayout.FieldRole)
        w = item.widget() if item is not None else None
        txt = w.text() if hasattr(w, 'text') else ''
        if isinstance(txt, str) and txt.startswith('Selected:'):
            return txt.split(':', 1)[1].strip().upper()
    except Exception:
        pass
    return getattr(self, '_lh50_last_property_kind', None)

try:
    _lh50_prev_refresh_properties = MainWindow.refresh_properties
except Exception:
    _lh50_prev_refresh_properties = None

def _lh50_refresh_properties(self):
    r = None
    if _lh50_prev_refresh_properties is not None:
        r = _lh50_prev_refresh_properties(self)
    try:
        k = _lh50_property_panel_kind(self)
        if k:
            self._lh50_last_property_kind = k
    except Exception:
        pass
    return r


def _lh50_body_context(self, sig=None):
    try:
        if str(_lh50_property_panel_kind(self) or '').upper() == 'BODY':
            return True
    except Exception:
        pass
    try:
        return any(str(s[0]) in ('BODY', 'BODY_GRAPHIC') for s in (sig or []))
    except Exception:
        return False


def _lh50_restore_body_or_signature(self, sig=None, fs=None, refresh_panel=True):
    force_body = _lh50_body_context(self, sig)
    def run():
        try:
            if fs is not None and '_lh47_restore_selection_filter_state' in globals():
                _lh47_restore_selection_filter_state(self, fs)
            if force_body and '_lh47_select_one_logical_body' in globals():
                _lh47_select_one_logical_body(self)
            elif sig and '_lh46_restore_selection_signature' in globals():
                _lh46_restore_selection_signature(self, sig)
            if refresh_panel:
                try: _lh50_refresh_properties(self)
                except Exception: pass
            try:
                if '_lh48_sync_style_toolbar_to_selection' in globals():
                    _lh48_sync_style_toolbar_to_selection(self)
            except Exception:
                pass
        except Exception as e:
            try: self.statusBar().showMessage(f'Selection restore failed: {e}', 4000)
            except Exception: pass
    try: QTimer.singleShot(0, run)
    except Exception: run()

# Capture the BODY view before a property widget can trigger transient scene changes.
def _lh50_dbl(self, value, fn, lo=-999, hi=999, step=.1):
    w = QDoubleSpinBox(); w.setRange(lo, hi); w.setSingleStep(step); w.setDecimals(3); w.setKeyboardTracking(False)
    try:
        w.blockSignals(True); w.setValue(float(value)); w.blockSignals(False)
    except Exception:
        try: w.blockSignals(True); w.setValue(0.0); w.blockSignals(False)
        except Exception: pass
    def safe(v):
        sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
        fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
        body_ctx = _lh50_body_context(self, sig)
        def do():
            try: fn(float(v))
            except RuntimeError: return
            except Exception as e:
                try: self.statusBar().showMessage(f'Property update failed: {e}', 5000)
                except Exception: pass
            finally:
                if body_ctx: self._lh50_last_property_kind = 'BODY'
                _lh50_restore_body_or_signature(self, sig=sig, fs=fs, refresh_panel=True)
        try: QTimer.singleShot(0, do)
        except Exception: do()
    w.valueChanged.connect(safe)
    return w


def _lh50_combo(self, items, val, fn):
    w = QComboBox(); w.blockSignals(True); w.addItems([str(x) for x in items]); w.setCurrentText(str(val)); w.blockSignals(False)
    def safe(v):
        # Ignore display-only mismatch marker.
        if str(v) == globals().get('_LH48_MULTIPLE', '<Multiple>'):
            return
        sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
        fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
        body_ctx = _lh50_body_context(self, sig)
        def do():
            try: fn(v)
            except RuntimeError: return
            except Exception as e:
                try: self.statusBar().showMessage(f'Property update failed: {e}', 5000)
                except Exception: pass
            finally:
                if body_ctx: self._lh50_last_property_kind = 'BODY'
                _lh50_restore_body_or_signature(self, sig=sig, fs=fs, refresh_panel=True)
        try: QTimer.singleShot(0, do)
        except Exception: do()
    w.currentTextChanged.connect(safe)
    return w


def _lh50_check(self, value, fn):
    w = QCheckBox(); w.blockSignals(True); w.setChecked(bool(value)); w.blockSignals(False)
    def safe(v):
        sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
        fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
        body_ctx = _lh50_body_context(self, sig)
        def do():
            try: fn(bool(v))
            except RuntimeError: return
            except Exception as e:
                try: self.statusBar().showMessage(f'Property update failed: {e}', 5000)
                except Exception: pass
            finally:
                if body_ctx: self._lh50_last_property_kind = 'BODY'
                _lh50_restore_body_or_signature(self, sig=sig, fs=fs, refresh_panel=True)
        try: QTimer.singleShot(0, do)
        except Exception: do()
    w.toggled.connect(safe)
    return w


def _lh50_set_safe(self, m, a, v):
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    body_ctx = _lh50_body_context(self, sig)
    try: self.push_undo_state()
    except Exception: pass
    try:
        if a == 'rotation': v = (round(float(v) / 15.0) * 15.0) % 360
        setattr(m, a, v); self.dirty = True
        try: self.update_current_unit_canvas_positions()
        except Exception: pass
        try: self.scene.update(); self.view.viewport().update()
        except Exception: pass
    except Exception as e:
        try: self.statusBar().showMessage(f'Property update failed: {e}', 5000)
        except Exception: pass
    if body_ctx: self._lh50_last_property_kind = 'BODY'
    _lh50_restore_body_or_signature(self, sig=sig, fs=fs, refresh_panel=True)


def _lh50_set_attr_vis(self, key, val):
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    body_ctx = _lh50_body_context(self, sig)
    try:
        try: self.scene.blockSignals(True)
        except Exception: pass
        self.push_undo_state()
        self.current_unit.body.visible_attributes[key] = bool(val)
        self.dirty = True
        try: self.update_attribute_items_for_unit()
        except Exception: pass
    except Exception as e:
        try: self.statusBar().showMessage(f'Attribute update failed: {e}', 5000)
        except Exception: pass
    finally:
        try: self.scene.blockSignals(False)
        except Exception: pass
        if body_ctx: self._lh50_last_property_kind = 'BODY'
        _lh50_restore_body_or_signature(self, sig=sig, fs=fs, refresh_panel=True)


def _lh50_set_attr_val(self, key, val):
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    body_ctx = _lh50_body_context(self, sig)
    try:
        try: self.scene.blockSignals(True)
        except Exception: pass
        self.push_undo_state()
        self.current_unit.body.attributes[key] = str(val)
        self.dirty = True
        try: self.update_attribute_items_for_unit()
        except Exception: pass
    except Exception as e:
        try: self.statusBar().showMessage(f'Attribute update failed: {e}', 5000)
        except Exception: pass
    finally:
        try: self.scene.blockSignals(False)
        except Exception: pass
        if body_ctx: self._lh50_last_property_kind = 'BODY'
        _lh50_restore_body_or_signature(self, sig=sig, fs=fs, refresh_panel=True)

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.refresh_properties = _lh50_refresh_properties
        _cls._dbl = _lh50_dbl
        _cls._combo = _lh50_combo
        _cls._check = _lh50_check
        _cls._set = _lh50_set_safe
    MainWindow._set_attr_vis = _lh50_set_attr_vis
    MainWindow._set_attr_val = _lh50_set_attr_val
except Exception:
    pass


# ---------------------------------------------------------------------------
# Liebherr v51: BODY-owned highlight graphics are paint-only; BODY rotation is
# a 0/90/180/270 dropdown and stays synced with CW/CCW.
# ---------------------------------------------------------------------------

def _lh51_select_one_logical_body(self):
    """Select exactly the real logical BodyItem, never BODY_GRAPHIC artwork."""
    try:
        cur_body = getattr(getattr(self, 'current_unit', None), 'body', None)
        target = None
        for it in list(self.scene.items()):
            try:
                if it.data(0) == 'BODY' and (getattr(it, 'model', None) is cur_body or target is None):
                    target = it
                    if getattr(it, 'model', None) is cur_body:
                        break
            except Exception:
                pass
        if target is None:
            return False
        self.scene.blockSignals(True)
        try:
            for it in self.scene.items():
                try: it.setSelected(False)
                except Exception: pass
            target.setSelected(True)
        finally:
            self.scene.blockSignals(False)
        try: self.scene.update(); self.view.viewport().update()
        except Exception: pass
        return True
    except Exception:
        try: self.scene.blockSignals(False)
        except Exception: pass
        return False


def _lh51_body_rotation_combo(self, body):
    vals = ['0°', '90°', '180°', '270°']
    try:
        cur = int(round(float(getattr(body, 'rotation', 0.0) or 0.0) / 90.0) * 90) % 360
    except Exception:
        cur = 0
    w = QComboBox(); w.blockSignals(True); w.addItems(vals); w.setCurrentText(f'{cur}°'); w.blockSignals(False)
    def safe(txt):
        try:
            target = float(str(txt).replace('°','').strip()) % 360.0
        except Exception:
            return
        sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
        fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
        def do():
            try:
                current = float(getattr(body, 'rotation', 0.0) or 0.0) % 360.0
                delta = target - current
                if abs(delta) > 180.0:
                    delta -= 360.0 if delta > 0 else -360.0
                if abs(delta) > 1e-9:
                    try: self.push_undo_state()
                    except Exception: pass
                    self._transform_unit_as_body_group('rotate', delta)
                    try: body.rotation = target
                    except Exception: pass
                    self.dirty = True
            except Exception as e:
                try: self.statusBar().showMessage(f'BODY rotation failed: {e}', 5000)
                except Exception: pass
            finally:
                try: self._lh50_last_property_kind = 'BODY'
                except Exception: pass
                if '_lh50_restore_body_or_signature' in globals():
                    _lh50_restore_body_or_signature(self, sig=sig, fs=fs, refresh_panel=True)
                elif '_lh47_restore_selection_after_action' in globals():
                    _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=True, refresh=True)
        try: QTimer.singleShot(0, do)
        except Exception: do()
    w.currentTextChanged.connect(safe)
    return w


def _lh51_transform_props(self, m):
    try:
        if m is getattr(getattr(self, 'current_unit', None), 'body', None):
            self.form.addRow('Rotation [deg]', _lh51_body_rotation_combo(self, m))
            return
    except Exception:
        pass
    # non-BODY fallback stays as before
    self.form.addRow('Rotation [deg]', self._dbl(getattr(m, 'rotation', 0), lambda v, model=m: self.set_and_refresh(model, 'rotation', v), -360, 360, 15))

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.transform_props = _lh51_transform_props
    # Override previous helper so all restore paths avoid BODY_GRAPHIC selection.
    globals()['_lh47_select_one_logical_body'] = _lh51_select_one_logical_body
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v52: synchronize toolbar CW/CCW BODY rotation with BODY property
# dropdown (0/90/180/270).  The geometric transform stays untouched; only the
# logical BODY rotation attribute is updated after toolbar rotation so the
# property panel reflects the actual last 90° operation.
# ---------------------------------------------------------------------------
try:
    _lh52_prev_rotate_selected = MainWindow.rotate_selected
except Exception:
    _lh52_prev_rotate_selected = None


def _lh52_body_selected_for_rotation(self):
    try:
        return bool(self._selected_body_active())
    except Exception:
        try:
            return any(getattr(i, 'data', lambda *_: None)(0) == 'BODY' for i in self.scene.selectedItems())
        except Exception:
            return False


def _lh52_sync_body_rotation_after_toolbar(self, deg, before_rotation):
    try:
        body = getattr(getattr(self, 'current_unit', None), 'body', None)
        if body is None:
            return
        # Keep the UI representation constrained to the four valid values.
        # Toolbar buttons are 90° steps; non-90 values are snapped defensively.
        step = int(round(float(deg or 0.0) / 90.0)) * 90
        before = int(round(float(before_rotation or 0.0) / 90.0)) * 90
        body.rotation = float((before + step) % 360)
        try: self._lh50_last_property_kind = 'BODY'
        except Exception: pass
    except Exception:
        pass


def _lh52_rotate_selected(self, deg):
    body_active = _lh52_body_selected_for_rotation(self)
    body = getattr(getattr(self, 'current_unit', None), 'body', None)
    try:
        before = float(getattr(body, 'rotation', 0.0) or 0.0) if (body_active and body is not None) else None
    except Exception:
        before = 0.0
    result = None
    if _lh52_prev_rotate_selected is not None:
        result = _lh52_prev_rotate_selected(self, deg)
    if body_active:
        _lh52_sync_body_rotation_after_toolbar(self, deg, before)
        try: self.dirty = True
        except Exception: pass
        # Rebuild the property panel asynchronously so the dropdown shows the
        # new value, while preserving the BODY selection/filter state.
        try:
            sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
            fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
            if '_lh50_restore_body_or_signature' in globals():
                QTimer.singleShot(0, lambda: _lh50_restore_body_or_signature(self, sig=sig, fs=fs, refresh_panel=True))
            elif '_lh47_restore_selection_after_action' in globals():
                QTimer.singleShot(0, lambda: _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=True, refresh=True))
            else:
                QTimer.singleShot(0, self.refresh_properties)
        except Exception:
            try: self.refresh_properties()
            except Exception: pass
    return result

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.rotate_selected = _lh52_rotate_selected
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v53: Scale +/- for inserted/free GRAPHIC objects.
# Previous fallback looked for a non-existent scale_by() method, therefore
# pasted/drawn graphics did not react to the toolbar.  Scale regular GRAPHIC
# models directly around their own center, snap endpoints to the edit grid and
# keep BODY/pin protection plus selection restoration intact.
# ---------------------------------------------------------------------------
try:
    _lh53_prev_scale_selected_grid = MainWindow.scale_selected_grid
    _lh53_prev_scale_selected = MainWindow.scale_selected
except Exception:
    _lh53_prev_scale_selected_grid = None
    _lh53_prev_scale_selected = None


def _lh53_edit_step(self):
    try:
        return max(float(self._edit_grid_step()), 1e-9)
    except Exception:
        try:
            return max(float(getattr(self, 'edit_grid_px', 0.0) or 0.0) / max(float(getattr(self, 'grid_px', 1.0) or 1.0), 1e-9), 1e-9)
        except Exception:
            return 0.1


def _lh53_snap(self, v):
    try:
        return float(self._snap_to_edit_grid(float(v), _lh53_edit_step(self)))
    except Exception:
        try:
            step = _lh53_edit_step(self)
            return round(float(v) / step) * step
        except Exception:
            return float(v)


def _lh53_graphic_points(gr):
    try:
        return _lh10_graphic_points(gr)
    except Exception:
        x = float(getattr(gr, 'x', 0.0) or 0.0)
        y = float(getattr(gr, 'y', 0.0) or 0.0)
        w = float(getattr(gr, 'w', 0.0) or 0.0)
        h = float(getattr(gr, 'h', 0.0) or 0.0)
        return (x, y, x + w, y - h)


def _lh53_scale_graphic_model(self, gr, factor):
    x1, y1, x2, y2 = _lh53_graphic_points(gr)
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    f = max(0.05, float(factor))
    nx1 = _lh53_snap(self, cx + (x1 - cx) * f)
    ny1 = _lh53_snap(self, cy + (y1 - cy) * f)
    nx2 = _lh53_snap(self, cx + (x2 - cx) * f)
    ny2 = _lh53_snap(self, cy + (y2 - cy) * f)
    # Avoid collapsing non-zero geometry after snapping.
    step = _lh53_edit_step(self)
    if abs(x2 - x1) > 1e-12 and abs(nx2 - nx1) < step:
        nx1, nx2 = _lh53_snap(self, cx - step / 2.0), _lh53_snap(self, cx + step / 2.0)
    if abs(y2 - y1) > 1e-12 and abs(ny2 - ny1) < step:
        ny1, ny2 = _lh53_snap(self, cy - step / 2.0), _lh53_snap(self, cy + step / 2.0)
    gr.x = nx1
    gr.y = ny1
    gr.w = nx2 - nx1
    gr.h = ny1 - ny2
    try:
        if getattr(gr, 'ctrl_x', None) is not None:
            gr.ctrl_x = float(gr.ctrl_x) * f
        if getattr(gr, 'ctrl_y', None) is not None:
            gr.ctrl_y = float(gr.ctrl_y) * f
        if getattr(gr, 'curve_radius', None) not in (None, 0, 0.0):
            gr.curve_radius = float(gr.curve_radius) * f
    except Exception:
        pass


def _lh53_selected_items(self):
    try:
        return [i for i in self.scene.selectedItems() if getattr(i, 'data', lambda *_: None)(0) not in ('SELECTION_HANDLE', 'HIGHLIGHT')]
    except Exception:
        return []


def _lh53_has_regular_graphics(self, items):
    for it in items:
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None and not bool(getattr(it.model, 'locked_to_body', False)):
                return True
        except Exception:
            pass
    return False


def _lh53_apply_scale_to_non_body_selection(self, factor):
    changed = False
    for it in _lh53_selected_items(self):
        try:
            kind = it.data(0)
            if kind == 'GRAPHIC' and getattr(it, 'model', None) is not None and not bool(getattr(it.model, 'locked_to_body', False)):
                _lh53_scale_graphic_model(self, it.model, factor)
                changed = True
            elif kind in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY') and hasattr(it, 'scale_selected'):
                it.scale_selected(float(factor)); changed = True
            elif kind == 'PIN':
                # Pins must not be scaled by Scale +/-.
                continue
        except Exception as e:
            try: self.statusBar().showMessage(f'Scale failed: {e}', 5000)
            except Exception: pass
    if changed:
        try: self.update_current_unit_canvas_positions()
        except Exception:
            try: self.schedule_scene_refresh()
            except Exception: pass
        try: self.update_attribute_items_for_unit()
        except Exception: pass
        try: self.rebuild_tree(); self.rebuild_pin_table()
        except Exception: pass
        try: self.refresh_properties()
        except Exception: pass
        try: self.view.viewport().update()
        except Exception: pass
    return changed


def _lh53_scale_selected(self, factor):
    try:
        if self._selected_body_active():
            return _lh53_prev_scale_selected(self, factor) if _lh53_prev_scale_selected else None
    except Exception:
        pass
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    try:
        self.set_tool(DrawTool.SELECT.value)
        self.push_undo_state()
        changed = _lh53_apply_scale_to_non_body_selection(self, float(factor))
        if not changed and _lh53_prev_scale_selected is not None:
            return _lh53_prev_scale_selected(self, factor)
        self.dirty = bool(changed) or getattr(self, 'dirty', False)
    finally:
        try:
            _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=False, refresh=False)
        except Exception:
            pass


def _lh53_scale_selected_grid(self, direction:int):
    try:
        if self._selected_body_active():
            return _lh53_prev_scale_selected_grid(self, direction) if _lh53_prev_scale_selected_grid else None
    except Exception:
        pass
    items = _lh53_selected_items(self)
    # Regular inserted/drawn graphics get a real geometry scale. Pins stay excluded.
    if _lh53_has_regular_graphics(self, items) or any(getattr(i, 'data', lambda *_: None)(0) in ('TEXT','ATTR_REF_DES','ATTR_BODY') for i in items):
        return _lh53_scale_selected(self, 1.0 + (0.1 if int(direction) > 0 else -0.1))
    if _lh53_prev_scale_selected_grid is not None:
        return _lh53_prev_scale_selected_grid(self, direction)

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.scale_selected = _lh53_scale_selected
        _cls.scale_selected_grid = _lh53_scale_selected_grid
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v55: robust proportional grid scaling for GRAPHIC selections plus
# lightweight graphic grouping.
# ---------------------------------------------------------------------------
# Rules:
# - Scale +/- on GRAPHIC selections changes geometry proportionally around the
#   selected graphic/group center.
# - One toolbar step equals one current edit-grid increment on the dominant
#   dimension; the minimum rendered dominant dimension is one edit-grid step.
# - Pins are never included.
# - BODY selections keep using the proven Symbol-1 BODY transform path.  Imported
#   and template BODY artwork is treated as BODY artwork and therefore follows
#   the same canvas scaling method.
# - A graphic group is a shared group id on user graphics. Selecting/scaling one
#   member scales the whole group as one logical object. Ungroup clears that id.

try:
    _lh55_prev_scale_selected_grid = MainWindow.scale_selected_grid
    _lh55_prev_scale_selected = MainWindow.scale_selected
except Exception:
    _lh55_prev_scale_selected_grid = None
    _lh55_prev_scale_selected = None


def _lh55_step(self):
    try:
        return max(float(self._edit_grid_step()), 1e-9)
    except Exception:
        try:
            txt = str(getattr(self, 'edit_grid_combo', None).currentText()).replace('"','').strip()
            return max(float(txt), 1e-9)
        except Exception:
            return 0.1


def _lh55_snap(self, v):
    try:
        return float(self._snap_to_edit_grid(float(v), _lh55_step(self)))
    except Exception:
        st = _lh55_step(self)
        try: return round(float(v) / st) * st
        except Exception: return float(v)


def _lh55_selected_real_items(self):
    out = []
    for it in list(getattr(self, 'scene', None).selectedItems() if getattr(self, 'scene', None) else []):
        try:
            k = it.data(0)
            if k in ('SELECTION_HANDLE', 'HIGHLIGHT', 'BODY_GRAPHIC'):
                continue
            out.append(it)
        except Exception:
            pass
    return out


def _lh55_is_user_graphic(self, gr):
    try:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body','template_body','imported_body')
    except Exception:
        return False


def _lh55_graphic_group_id(gr):
    try:
        gid = getattr(gr, 'group_id', '') or ''
    except Exception:
        gid = ''
    if not gid:
        try:
            role = str(getattr(gr, 'graphic_role', '') or '')
            if role.startswith('user_graphic_group:'):
                gid = role.split(':', 1)[1]
        except Exception:
            pass
    return str(gid or '')


def _lh55_set_graphic_group_id(gr, gid):
    try: setattr(gr, 'group_id', str(gid or ''))
    except Exception: pass
    try:
        gr.graphic_role = ('user_graphic_group:' + str(gid)) if gid else 'user_graphic'
    except Exception: pass


def _lh55_graphic_models_from_selection(self):
    selected = []
    gids = set()
    for it in _lh55_selected_real_items(self):
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None and _lh55_is_user_graphic(self, it.model):
                selected.append(it.model)
                gid = _lh55_graphic_group_id(it.model)
                if gid:
                    gids.add(gid)
        except Exception:
            pass
    if not selected:
        return []
    models = []
    for gr in list(getattr(getattr(self, 'current_unit', None), 'graphics', []) or []):
        try:
            if not _lh55_is_user_graphic(self, gr):
                continue
            if gr in selected or (_lh55_graphic_group_id(gr) and _lh55_graphic_group_id(gr) in gids):
                if gr not in models:
                    models.append(gr)
        except Exception:
            pass
    return models


def _lh55_graphic_endpoints(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    return x, y, x + w, y - h


def _lh55_model_points(gr):
    x1, y1, x2, y2 = _lh55_graphic_endpoints(gr)
    shape = str(getattr(gr, 'shape', '') or '').lower()
    pts = [(x1, y1), (x2, y2)]
    if shape not in ('line','arc'):
        pts += [(x1, y2), (x2, y1)]
    try:
        if getattr(gr, 'ctrl_x', None) is not None and getattr(gr, 'ctrl_y', None) is not None:
            pts.append((x1 + float(gr.ctrl_x), y1 - float(gr.ctrl_y)))
    except Exception:
        pass
    return pts


def _lh55_graphics_bounds(graphics):
    pts = []
    for gr in graphics:
        pts.extend(_lh55_model_points(gr))
    if not pts:
        return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _lh55_scale_point(self, px, py, cx, cy, factor):
    return _lh55_snap(self, cx + (float(px) - cx) * factor), _lh55_snap(self, cy + (float(py) - cy) * factor)


def _lh55_scale_graphics_by_grid_step(self, direction):
    graphics = _lh55_graphic_models_from_selection(self)
    if not graphics:
        return False
    b = _lh55_graphics_bounds(graphics)
    if not b:
        return False
    minx, miny, maxx, maxy = b
    st = _lh55_step(self)
    cur_w = abs(maxx - minx)
    cur_h = abs(maxy - miny)
    dominant = max(cur_w, cur_h, st)
    new_dom = max(st, dominant + (st if int(direction) > 0 else -st))
    factor = new_dom / dominant if dominant > 1e-12 else 1.0
    if abs(factor - 1.0) < 1e-12:
        return False
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    try: self.push_undo_state()
    except Exception: pass
    for gr in graphics:
        x1, y1, x2, y2 = _lh55_graphic_endpoints(gr)
        nx1, ny1 = _lh55_scale_point(self, x1, y1, cx, cy, factor)
        nx2, ny2 = _lh55_scale_point(self, x2, y2, cx, cy, factor)
        # Prevent collapse after snapping.  Preserve direction signs as far as possible.
        if abs(x2 - x1) > 1e-12 and abs(nx2 - nx1) < st:
            sgn = 1.0 if (x2 - x1) >= 0 else -1.0
            nx1 = _lh55_snap(self, (nx1 + nx2) / 2.0 - sgn * st / 2.0)
            nx2 = _lh55_snap(self, (nx1 + nx2) / 2.0 + sgn * st / 2.0)
        if abs(y2 - y1) > 1e-12 and abs(ny2 - ny1) < st:
            sgn = 1.0 if (y2 - y1) >= 0 else -1.0
            ny1 = _lh55_snap(self, (ny1 + ny2) / 2.0 - sgn * st / 2.0)
            ny2 = _lh55_snap(self, (ny1 + ny2) / 2.0 + sgn * st / 2.0)
        # Control point is absolute during transformation, then stored relative
        # to the new start point using the model's y-down h/ctrl_y convention.
        cabs = None
        try:
            if getattr(gr, 'ctrl_x', None) is not None and getattr(gr, 'ctrl_y', None) is not None:
                cabs = (x1 + float(gr.ctrl_x), y1 - float(gr.ctrl_y))
        except Exception:
            cabs = None
        gr.x = nx1
        gr.y = ny1
        gr.w = nx2 - nx1
        gr.h = ny1 - ny2
        if cabs is not None:
            ncx, ncy = _lh55_scale_point(self, cabs[0], cabs[1], cx, cy, factor)
            try:
                gr.ctrl_x = ncx - nx1
                gr.ctrl_y = ny1 - ncy
            except Exception:
                pass
        try:
            if getattr(gr, 'curve_radius', None) not in (None, 0, 0.0):
                gr.curve_radius = float(gr.curve_radius) * factor
        except Exception:
            pass
    try:
        self.dirty = True
        self.update_current_unit_canvas_positions()
    except Exception:
        try: self.schedule_scene_refresh()
        except Exception: pass
    try: self.refresh_properties()
    except Exception: pass
    try: self.view.viewport().update()
    except Exception: pass
    return True


def _lh55_scale_selected_grid(self, direction:int):
    try:
        if self._selected_body_active():
            return _lh55_prev_scale_selected_grid(self, direction) if _lh55_prev_scale_selected_grid else None
    except Exception:
        pass
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    try:
        if _lh55_scale_graphics_by_grid_step(self, direction):
            return None
        if _lh55_prev_scale_selected_grid is not None:
            return _lh55_prev_scale_selected_grid(self, direction)
    finally:
        try: _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=False, refresh=False)
        except Exception: pass


def _lh55_scale_selected(self, factor):
    # Keep direct/legacy callers safe: convert relative factor to one grid step
    # direction for GRAPHIC selections. BODY path remains untouched.
    try:
        if self._selected_body_active():
            return _lh55_prev_scale_selected(self, factor) if _lh55_prev_scale_selected else None
    except Exception:
        pass
    return _lh55_scale_selected_grid(self, 1 if float(factor) >= 1.0 else -1)


def _lh55_group_selected_graphics(self):
    models = []
    for it in _lh55_selected_real_items(self):
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None and _lh55_is_user_graphic(self, it.model):
                if it.model not in models:
                    models.append(it.model)
        except Exception:
            pass
    if len(models) < 2:
        try: self.statusBar().showMessage('Bitte mindestens zwei Grafikobjekte zum Gruppieren auswählen.', 3500)
        except Exception: pass
        return
    try: self.push_undo_state()
    except Exception: pass
    import uuid as _lh55_uuid
    gid = 'G' + _lh55_uuid.uuid4().hex[:8]
    for gr in models:
        _lh55_set_graphic_group_id(gr, gid)
    try: self.dirty = True; self.refresh_properties(); self.rebuild_tree()
    except Exception: pass
    try: self.statusBar().showMessage(f'Grafikgruppe erstellt ({len(models)} Objekte).', 3500)
    except Exception: pass


def _lh55_ungroup_selected_graphics(self):
    models = _lh55_graphic_models_from_selection(self)
    if not models:
        return
    try: self.push_undo_state()
    except Exception: pass
    for gr in models:
        _lh55_set_graphic_group_id(gr, '')
    try: self.dirty = True; self.refresh_properties(); self.rebuild_tree()
    except Exception: pass
    try: self.statusBar().showMessage('Grafikgruppe aufgehoben.', 3500)
    except Exception: pass

try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.scale_selected = _lh55_scale_selected
        _cls.scale_selected_grid = _lh55_scale_selected_grid
    MainWindow.group_selected_graphics = _lh55_group_selected_graphics
    MainWindow.ungroup_selected_graphics = _lh55_ungroup_selected_graphics
except Exception:
    pass

# Add Group/Ungroup buttons to the Transform toolbar without touching the
# existing toolbar construction semantics.
try:
    _lh55_prev_toolbar = MainWindow._toolbar
    def _lh55_toolbar(self):
        _lh55_prev_toolbar(self)
        try:
            tb = self.addToolBar('Graphic Group')
            b = QPushButton('Group Graphics'); b.clicked.connect(self.group_selected_graphics); tb.addWidget(b)
            b = QPushButton('Ungroup'); b.clicked.connect(self.ungroup_selected_graphics); tb.addWidget(b)
        except Exception:
            pass
    MainWindow._toolbar = _lh55_toolbar
except Exception:
    pass


# ---------------------------------------------------------------------------
# Liebherr v56: corrected GRAPHIC scale/group behavior.
# ---------------------------------------------------------------------------
# Fixes after v55:
# - Scale + on a 3x3 graphic rectangle becomes 4x4 at the same center.
# - Scale - is proportional, grid-snapped, and never collapses below one edit-grid.
# - Graphic groups are accessible from Edit menu and shortcuts in addition to the
#   toolbar, and group ids are persisted on GraphicModel.group_id.
# - Selecting one member of a group makes Scale/Move operate on the complete group.

try:
    _lh56_prev_scale_selected_grid = MainWindow.scale_selected_grid
    _lh56_prev_scale_selected = MainWindow.scale_selected
except Exception:
    _lh56_prev_scale_selected_grid = None
    _lh56_prev_scale_selected = None


def _lh56_step(self):
    try:
        return max(float(self._edit_grid_step()), 1e-9)
    except Exception:
        return 0.1


def _lh56_increment(self):
    # The UI properties are expressed in grid units. For toolbar Scale +/- the
    # expected interaction is one grid unit per click (3x3 -> 4x4), while the
    # resulting coordinates are still snapped to the active edit grid.
    try:
        return max(1.0, _lh56_step(self))
    except Exception:
        return 1.0


def _lh56_snap(self, v):
    st = _lh56_step(self)
    try:
        return float(self._snap_to_edit_grid(float(v), st))
    except Exception:
        try:
            return round(float(v) / st) * st
        except Exception:
            return float(v)


def _lh56_selected_real_items(self):
    items = []
    try:
        raw = list(self.scene.selectedItems())
    except Exception:
        raw = []
    for it in raw:
        try:
            if it.data(0) in ('SELECTION_HANDLE', 'HIGHLIGHT', 'BODY_GRAPHIC'):
                continue
            items.append(it)
        except Exception:
            pass
    return items


def _lh56_is_user_graphic(gr):
    try:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body','template_body','imported_body')
    except Exception:
        return False


def _lh56_gid(gr):
    try:
        gid = str(getattr(gr, 'group_id', '') or '')
        if gid:
            return gid
        role = str(getattr(gr, 'graphic_role', '') or '')
        if role.startswith('user_graphic_group:'):
            return role.split(':', 1)[1]
    except Exception:
        pass
    return ''


def _lh56_set_gid(gr, gid):
    gid = str(gid or '')
    try:
        gr.group_id = gid
    except Exception:
        pass
    try:
        gr.graphic_role = ('user_graphic_group:' + gid) if gid else 'user_graphic'
    except Exception:
        pass


def _lh56_selected_graphic_models(self, expand_groups=True):
    selected = []
    gids = set()
    for it in _lh56_selected_real_items(self):
        try:
            if it.data(0) == 'GRAPHIC' and getattr(it, 'model', None) is not None and _lh56_is_user_graphic(it.model):
                selected.append(it.model)
                gid = _lh56_gid(it.model)
                if gid:
                    gids.add(gid)
        except Exception:
            pass
    if not selected:
        return []
    if not expand_groups:
        return selected
    out = []
    try:
        graphics = list(getattr(self.current_unit, 'graphics', []) or [])
    except Exception:
        graphics = []
    for gr in graphics:
        try:
            if not _lh56_is_user_graphic(gr):
                continue
            if gr in selected or (_lh56_gid(gr) and _lh56_gid(gr) in gids):
                if gr not in out:
                    out.append(gr)
        except Exception:
            pass
    return out


def _lh56_points(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    x2 = x + w
    y2 = y - h
    pts = [(x, y), (x2, y2)]
    if str(getattr(gr, 'shape', '') or '').lower() not in ('line', 'arc'):
        pts.extend([(x, y2), (x2, y)])
    try:
        if getattr(gr, 'ctrl_x', None) is not None and getattr(gr, 'ctrl_y', None) is not None:
            pts.append((x + float(gr.ctrl_x), y - float(gr.ctrl_y)))
    except Exception:
        pass
    return pts


def _lh56_bounds(graphics):
    pts = []
    for gr in graphics:
        pts.extend(_lh56_points(gr))
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _lh56_scale_point(self, px, py, cx, cy, factor):
    return _lh56_snap(self, cx + (float(px) - cx) * factor), _lh56_snap(self, cy + (float(py) - cy) * factor)


def _lh56_apply_graphic_scale(self, direction:int):
    graphics = _lh56_selected_graphic_models(self, expand_groups=True)
    if not graphics:
        return False
    b = _lh56_bounds(graphics)
    if not b:
        return False
    minx, miny, maxx, maxy = b
    cur_w = abs(maxx - minx)
    cur_h = abs(maxy - miny)
    dominant = max(cur_w, cur_h, _lh56_step(self))
    inc = _lh56_increment(self)
    new_dom = max(_lh56_step(self), dominant + (inc if int(direction) > 0 else -inc))
    factor = new_dom / dominant if dominant > 1e-12 else 1.0
    if abs(factor - 1.0) < 1e-12:
        return False
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    try:
        self.push_undo_state()
    except Exception:
        pass
    min_dim = _lh56_step(self)
    for gr in graphics:
        x = float(getattr(gr, 'x', 0.0) or 0.0)
        y = float(getattr(gr, 'y', 0.0) or 0.0)
        w = float(getattr(gr, 'w', 0.0) or 0.0)
        h = float(getattr(gr, 'h', 0.0) or 0.0)
        x2, y2 = x + w, y - h
        ctrl_abs = None
        try:
            if getattr(gr, 'ctrl_x', None) is not None and getattr(gr, 'ctrl_y', None) is not None:
                ctrl_abs = (x + float(gr.ctrl_x), y - float(gr.ctrl_y))
        except Exception:
            ctrl_abs = None
        nx1, ny1 = _lh56_scale_point(self, x, y, cx, cy, factor)
        nx2, ny2 = _lh56_scale_point(self, x2, y2, cx, cy, factor)
        nw = nx2 - nx1
        nh = ny1 - ny2
        # Keep every non-zero axis at least one edit-grid step. This is what
        # prevents Width from becoming 0/0.5 unexpectedly after snapping.
        if abs(w) > 1e-12 and abs(nw) < min_dim:
            sgn = 1.0 if w >= 0 else -1.0
            gcx = (nx1 + nx2) / 2.0
            nx1 = _lh56_snap(self, gcx - sgn * min_dim / 2.0)
            nx2 = _lh56_snap(self, gcx + sgn * min_dim / 2.0)
            nw = nx2 - nx1
        if abs(h) > 1e-12 and abs(nh) < min_dim:
            sgn = 1.0 if h >= 0 else -1.0
            gcy = (ny1 + ny2) / 2.0
            ny1 = _lh56_snap(self, gcy + sgn * min_dim / 2.0)
            ny2 = _lh56_snap(self, gcy - sgn * min_dim / 2.0)
            nh = ny1 - ny2
        gr.x, gr.y, gr.w, gr.h = nx1, ny1, nw, nh
        if ctrl_abs is not None:
            ncx, ncy = _lh56_scale_point(self, ctrl_abs[0], ctrl_abs[1], cx, cy, factor)
            try:
                gr.ctrl_x = ncx - nx1
                gr.ctrl_y = ny1 - ncy
            except Exception:
                pass
        try:
            if getattr(gr, 'curve_radius', None) not in (None, 0, 0.0):
                gr.curve_radius = float(gr.curve_radius) * factor
        except Exception:
            pass
    try:
        self.dirty = True
        self.update_current_unit_canvas_positions()
    except Exception:
        try:
            self.schedule_scene_refresh()
        except Exception:
            pass
    try:
        self.refresh_properties()
    except Exception:
        pass
    try:
        self.rebuild_tree()
    except Exception:
        pass
    try:
        self.view.viewport().update()
    except Exception:
        pass
    return True


def _lh56_scale_selected_grid(self, direction:int):
    try:
        if self._selected_body_active():
            return _lh56_prev_scale_selected_grid(self, direction) if _lh56_prev_scale_selected_grid else None
    except Exception:
        pass
    sig = _lh46_selected_signature(self) if '_lh46_selected_signature' in globals() else []
    fs = _lh47_selection_filter_state(self) if '_lh47_selection_filter_state' in globals() else None
    try:
        if _lh56_apply_graphic_scale(self, int(direction)):
            return None
        if _lh56_prev_scale_selected_grid:
            return _lh56_prev_scale_selected_grid(self, direction)
    finally:
        try:
            _lh47_restore_selection_after_action(self, sig=sig, filter_state=fs, force_body=False, refresh=False)
        except Exception:
            pass


def _lh56_scale_selected(self, factor):
    try:
        if self._selected_body_active():
            return _lh56_prev_scale_selected(self, factor) if _lh56_prev_scale_selected else None
    except Exception:
        pass
    try:
        return _lh56_scale_selected_grid(self, 1 if float(factor) >= 1.0 else -1)
    except Exception:
        return _lh56_scale_selected_grid(self, 1)


def _lh56_group_selected_graphics(self):
    models = _lh56_selected_graphic_models(self, expand_groups=False)
    if len(models) < 2:
        try:
            self.statusBar().showMessage('Mindestens zwei Grafikobjekte auswählen, dann Edit > Group Graphics.', 4000)
        except Exception:
            pass
        return
    try:
        self.push_undo_state()
    except Exception:
        pass
    import uuid as _lh56_uuid
    gid = 'G' + _lh56_uuid.uuid4().hex[:8]
    for gr in models:
        _lh56_set_gid(gr, gid)
    try:
        self.dirty = True
        self.rebuild_tree()
        self.refresh_properties()
        self.update_current_unit_canvas_positions()
    except Exception:
        pass
    try:
        self.statusBar().showMessage(f'Grafikgruppe erstellt: {len(models)} Objekte.', 3500)
    except Exception:
        pass


def _lh56_ungroup_selected_graphics(self):
    models = _lh56_selected_graphic_models(self, expand_groups=True)
    if not models:
        return
    try:
        self.push_undo_state()
    except Exception:
        pass
    for gr in models:
        _lh56_set_gid(gr, '')
    try:
        self.dirty = True
        self.rebuild_tree()
        self.refresh_properties()
        self.update_current_unit_canvas_positions()
    except Exception:
        pass
    try:
        self.statusBar().showMessage('Grafikgruppe aufgehoben.', 3500)
    except Exception:
        pass


def _lh56_add_group_actions(self):
    try:
        if getattr(self, '_lh56_group_actions_added', False):
            return
        self._lh56_group_actions_added = True
        # Menu bar action is deliberately used, because a hidden/overflowed
        # toolbar button is easy to miss on small screens.
        edit_menu = None
        try:
            for act in self.menuBar().actions():
                if str(act.text()).replace('&','').lower() == 'edit':
                    edit_menu = act.menu(); break
        except Exception:
            edit_menu = None
        if edit_menu is None:
            edit_menu = self.menuBar().addMenu('&Edit')
        edit_menu.addSeparator()
        a = QAction('Group Graphics', self)
        a.setShortcut(QKeySequence('Ctrl+G'))
        a.triggered.connect(self.group_selected_graphics)
        edit_menu.addAction(a)
        self.addAction(a)
        a = QAction('Ungroup Graphics', self)
        a.setShortcut(QKeySequence('Ctrl+Shift+G'))
        a.triggered.connect(self.ungroup_selected_graphics)
        edit_menu.addAction(a)
        self.addAction(a)
    except Exception:
        pass


try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.scale_selected = _lh56_scale_selected
        _cls.scale_selected_grid = _lh56_scale_selected_grid
        _cls.group_selected_graphics = _lh56_group_selected_graphics
        _cls.ungroup_selected_graphics = _lh56_ungroup_selected_graphics
    _lh56_prev_menus = MainWindow._menus
    def _lh56_menus(self):
        _lh56_prev_menus(self)
        _lh56_add_group_actions(self)
    MainWindow._menus = _lh56_menus
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v57: definitive user-graphic scaling and visible grouping controls.
# ---------------------------------------------------------------------------
# This patch intentionally sits at the very end of the module so it wins over
# older v53/v55/v56 compatibility patches above.

def _lh57_grid_step(self):
    try:
        return max(float(self._edit_grid_step()), 1e-9)
    except Exception:
        try:
            txt = str(self.edit_grid_combo.currentText()).replace('"', '').strip()
            return max(float(txt), 1e-9)
        except Exception:
            return 1.0


def _lh57_scale_increment(self):
    # Toolbar Scale +/- is deliberately a visible grid-size operation.  A 3x3
    # rectangle becomes 4x4, not 3.05x3.05 on small edit-grid settings.
    return max(1.0, _lh57_grid_step(self))


def _lh57_snap(self, v):
    st = _lh57_grid_step(self)
    try:
        return float(self._snap_to_edit_grid(float(v), st))
    except Exception:
        return round(float(v) / st) * st


def _lh57_gid(gr):
    try:
        gid = str(getattr(gr, 'group_id', '') or '')
        if gid:
            return gid
        role = str(getattr(gr, 'graphic_role', '') or '')
        if role.startswith('user_graphic_group:'):
            return role.split(':', 1)[1]
    except Exception:
        pass
    return ''


def _lh57_set_gid(gr, gid):
    gid = str(gid or '')
    try:
        gr.group_id = gid
    except Exception:
        pass
    try:
        gr.graphic_role = ('user_graphic_group:' + gid) if gid else 'user_graphic'
    except Exception:
        pass


def _lh57_is_user_graphic(gr):
    try:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body', 'template_body', 'imported_body', 'body_graphic')
    except Exception:
        return False


def _lh57_selected_graphics(self, expand_groups=True):
    selected = []
    gids = set()
    try:
        items = list(self.scene.selectedItems()) if getattr(self, 'scene', None) else []
    except Exception:
        items = []
    for it in items:
        try:
            if it.data(0) != 'GRAPHIC':
                continue
            gr = getattr(it, 'model', None)
            if gr is None or not _lh57_is_user_graphic(gr):
                continue
            if gr not in selected:
                selected.append(gr)
            gid = _lh57_gid(gr)
            if gid:
                gids.add(gid)
        except Exception:
            pass
    if not selected:
        return []
    if not expand_groups:
        return selected
    out = []
    try:
        all_graphics = list(getattr(getattr(self, 'current_unit', None), 'graphics', []) or [])
    except Exception:
        all_graphics = []
    for gr in all_graphics:
        try:
            if not _lh57_is_user_graphic(gr):
                continue
            gid = _lh57_gid(gr)
            if gr in selected or (gid and gid in gids):
                if gr not in out:
                    out.append(gr)
        except Exception:
            pass
    return out


def _lh57_graphic_bbox(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    x2 = x + w
    y2 = y - h
    return min(x, x2), min(y, y2), max(x, x2), max(y, y2)


def _lh57_group_bbox(graphics):
    boxes = [_lh57_graphic_bbox(g) for g in graphics]
    if not boxes:
        return None
    return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)


def _lh57_apply_graphics_scale(self, direction):
    graphics = _lh57_selected_graphics(self, expand_groups=True)
    if not graphics:
        return False
    bbox = _lh57_group_bbox(graphics)
    if not bbox:
        return False
    minx, miny, maxx, maxy = bbox
    cur_w = maxx - minx
    cur_h = maxy - miny
    inc = _lh57_scale_increment(self)
    min_size = _lh57_grid_step(self)
    dominant = max(abs(cur_w), abs(cur_h), min_size)
    new_dominant = dominant + (inc if int(direction) > 0 else -inc)
    new_dominant = max(min_size, new_dominant)
    factor = new_dominant / dominant if dominant > 1e-12 else 1.0
    if abs(factor - 1.0) < 1e-12:
        return True

    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0
    try:
        self.push_undo_state()
    except Exception:
        pass

    for gr in graphics:
        x = float(getattr(gr, 'x', 0.0) or 0.0)
        y = float(getattr(gr, 'y', 0.0) or 0.0)
        w = float(getattr(gr, 'w', 0.0) or 0.0)
        h = float(getattr(gr, 'h', 0.0) or 0.0)

        # Object center in model coordinates.  For graphics, h grows downward on
        # screen, therefore center-y is y - h/2.
        gcx = x + w / 2.0
        gcy = y - h / 2.0
        ngcx = _lh57_snap(self, cx + (gcx - cx) * factor)
        ngcy = _lh57_snap(self, cy + (gcy - cy) * factor)

        shape = str(getattr(gr, 'shape', '') or '').lower()
        if shape in ('line', 'arc'):
            nw = _lh57_snap(self, w * factor)
            nh = _lh57_snap(self, h * factor)
            # A purely vertical/horizontal line may legitimately have one zero
            # axis.  Only keep the non-zero/originally dominant axis alive.
            if abs(w) > 1e-12 and abs(nw) < min_size:
                nw = min_size if w >= 0 else -min_size
            if abs(h) > 1e-12 and abs(nh) < min_size:
                nh = min_size if h >= 0 else -min_size
            gr.x = _lh57_snap(self, ngcx - nw / 2.0)
            gr.y = _lh57_snap(self, ngcy + nh / 2.0)
            gr.w = nw
            gr.h = nh
            try:
                if getattr(gr, 'ctrl_x', None) is not None:
                    gr.ctrl_x = _lh57_snap(self, float(gr.ctrl_x) * factor)
                if getattr(gr, 'ctrl_y', None) is not None:
                    gr.ctrl_y = _lh57_snap(self, float(gr.ctrl_y) * factor)
                if getattr(gr, 'curve_radius', None) not in (None, 0, 0.0):
                    gr.curve_radius = _lh57_snap(self, float(gr.curve_radius) * factor)
            except Exception:
                pass
        else:
            sign_w = -1.0 if w < 0 else 1.0
            sign_h = -1.0 if h < 0 else 1.0
            nw_abs = max(min_size, abs(w) * factor)
            nh_abs = max(min_size, abs(h) * factor)
            nw = sign_w * _lh57_snap(self, nw_abs)
            nh = sign_h * _lh57_snap(self, nh_abs)
            # Snap can round small values down; enforce once more.
            if abs(nw) < min_size:
                nw = sign_w * min_size
            if abs(nh) < min_size:
                nh = sign_h * min_size
            gr.w = nw
            gr.h = nh
            gr.x = _lh57_snap(self, ngcx - nw / 2.0)
            gr.y = _lh57_snap(self, ngcy + nh / 2.0)

    try:
        self.dirty = True
    except Exception:
        pass
    try:
        self.update_current_unit_canvas_positions()
    except Exception:
        try:
            self.schedule_scene_refresh()
        except Exception:
            pass
    try:
        self.refresh_properties()
    except Exception:
        pass
    try:
        self.rebuild_tree()
    except Exception:
        pass
    try:
        self.view.viewport().update()
    except Exception:
        pass
    return True


def _lh57_group_selected_graphics(self):
    models = _lh57_selected_graphics(self, expand_groups=False)
    if len(models) < 2:
        try:
            QMessageBox.information(self, 'Group Graphics', 'Bitte mindestens zwei Grafikobjekte auswählen.')
        except Exception:
            pass
        return
    try:
        self.push_undo_state()
    except Exception:
        pass
    import uuid as _lh57_uuid
    gid = 'G' + _lh57_uuid.uuid4().hex[:8]
    for gr in models:
        _lh57_set_gid(gr, gid)
    try:
        self.dirty = True
        self.rebuild_tree()
        self.refresh_properties()
        self.update_current_unit_canvas_positions()
        self.statusBar().showMessage(f'Grafikgruppe erstellt: {len(models)} Objekte.', 4000)
    except Exception:
        pass


def _lh57_ungroup_selected_graphics(self):
    models = _lh57_selected_graphics(self, expand_groups=True)
    if not models:
        try:
            QMessageBox.information(self, 'Ungroup Graphics', 'Keine Grafikgruppe ausgewählt.')
        except Exception:
            pass
        return
    try:
        self.push_undo_state()
    except Exception:
        pass
    for gr in models:
        _lh57_set_gid(gr, '')
    try:
        self.dirty = True
        self.rebuild_tree()
        self.refresh_properties()
        self.update_current_unit_canvas_positions()
        self.statusBar().showMessage('Grafikgruppe aufgehoben.', 4000)
    except Exception:
        pass


def _lh57_install_group_ui(self):
    if getattr(self, '_lh57_group_ui_installed', False):
        return
    self._lh57_group_ui_installed = True
    try:
        edit_menu = None
        for act in self.menuBar().actions():
            if str(act.text()).replace('&', '').lower() == 'edit':
                edit_menu = act.menu()
                break
        if edit_menu is None:
            edit_menu = self.menuBar().addMenu('&Edit')
        edit_menu.addSeparator()
        a_group = QAction('Group Graphics', self)
        a_group.setShortcut(QKeySequence('Ctrl+G'))
        a_group.triggered.connect(self.group_selected_graphics)
        edit_menu.addAction(a_group)
        self.addAction(a_group)
        a_ungroup = QAction('Ungroup Graphics', self)
        a_ungroup.setShortcut(QKeySequence('Ctrl+Shift+G'))
        a_ungroup.triggered.connect(self.ungroup_selected_graphics)
        edit_menu.addAction(a_ungroup)
        self.addAction(a_ungroup)
    except Exception:
        pass
    try:
        tb = self.addToolBar('Graphic Group')
        btn = QPushButton('Group Graphics')
        btn.setToolTip('Ausgewählte Grafikobjekte gruppieren (Ctrl+G)')
        btn.clicked.connect(self.group_selected_graphics)
        tb.addWidget(btn)
        btn = QPushButton('Ungroup')
        btn.setToolTip('Grafikgruppe aufheben (Ctrl+Shift+G)')
        btn.clicked.connect(self.ungroup_selected_graphics)
        tb.addWidget(btn)
    except Exception:
        pass


try:
    _lh57_prev_scale_selected_grid = MainWindow.scale_selected_grid
    _lh57_prev_scale_selected = MainWindow.scale_selected
except Exception:
    _lh57_prev_scale_selected_grid = None
    _lh57_prev_scale_selected = None


def _lh57_scale_selected_grid(self, direction:int):
    try:
        if self._selected_body_active():
            return _lh57_prev_scale_selected_grid(self, direction) if _lh57_prev_scale_selected_grid else None
    except Exception:
        pass
    if _lh57_apply_graphics_scale(self, int(direction)):
        return None
    if _lh57_prev_scale_selected_grid:
        return _lh57_prev_scale_selected_grid(self, direction)


def _lh57_scale_selected(self, factor):
    try:
        if self._selected_body_active():
            return _lh57_prev_scale_selected(self, factor) if _lh57_prev_scale_selected else None
    except Exception:
        pass
    direction = 1
    try:
        direction = 1 if float(factor) >= 1.0 else -1
    except Exception:
        direction = 1
    return _lh57_scale_selected_grid(self, direction)


try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.scale_selected_grid = _lh57_scale_selected_grid
        _cls.scale_selected = _lh57_scale_selected
        _cls.group_selected_graphics = _lh57_group_selected_graphics
        _cls.ungroup_selected_graphics = _lh57_ungroup_selected_graphics
        _old_init = _cls.__init__
        def _new_init(self, *args, __old_init=_old_init, **kwargs):
            __old_init(self, *args, **kwargs)
            try:
                _lh57_install_group_ui(self)
            except Exception:
                pass
        _cls.__init__ = _new_init
except Exception:
    pass

# ---------------------------------------------------------------------------
# Liebherr v58: BODY-identical graphic/group scaling around own origin.
# ---------------------------------------------------------------------------
# User rule:
# - Single GRAPHIC scales like BODY, but around the graphic's own origin/center.
# - A graphic group is one logical object. Its origin is the center of the
#   maximum x/y bounding box of all group members.
# - Scale +/- changes the logical object's width and height by one visible grid
#   unit, snapped to Edit grid, with minimum one Edit-grid step.
# - Selection highlight for a group is a single bounding rectangle.

try:
    _lh58_prev_scale_selected_grid = MainWindow.scale_selected_grid
    _lh58_prev_scale_selected = MainWindow.scale_selected
except Exception:
    _lh58_prev_scale_selected_grid = None
    _lh58_prev_scale_selected = None


def _lh58_grid_step(self):
    try:
        return max(float(self._edit_grid_step()), 1e-9)
    except Exception:
        return 0.05


def _lh58_visible_increment(self):
    # BODY toolbar scaling in this tool is a visible grid-size operation. Keep
    # the same interaction for graphics: 3x3 -> 4x4 while still snapping to the
    # active Edit grid.
    try:
        return max(1.0, _lh58_grid_step(self))
    except Exception:
        return 1.0


def _lh58_snap(self, v):
    st = _lh58_grid_step(self)
    try:
        return float(self._snap_to_edit_grid(float(v), st))
    except Exception:
        return round(float(v) / st) * st


def _lh58_gid(gr):
    try:
        gid = str(getattr(gr, 'group_id', '') or '')
        if gid:
            return gid
        role = str(getattr(gr, 'graphic_role', '') or '')
        if role.startswith('user_graphic_group:'):
            return role.split(':', 1)[1]
    except Exception:
        pass
    return ''


def _lh58_set_gid(gr, gid):
    gid = str(gid or '')
    try:
        gr.group_id = gid
    except Exception:
        pass
    try:
        gr.graphic_role = ('user_graphic_group:' + gid) if gid else 'user_graphic'
    except Exception:
        pass


def _lh58_is_user_graphic(gr):
    try:
        role = str(getattr(gr, 'graphic_role', '') or '').lower()
        return (not bool(getattr(gr, 'locked_to_body', False))) and role not in ('body', 'template_body', 'imported_body', 'body_graphic')
    except Exception:
        return False


def _lh58_selected_graphics(self, expand_groups=True):
    selected = []
    gids = set()
    try:
        items = list(self.scene.selectedItems()) if getattr(self, 'scene', None) else []
    except Exception:
        items = []
    for it in items:
        try:
            if it.data(0) != 'GRAPHIC':
                continue
            gr = getattr(it, 'model', None)
            if gr is None or not _lh58_is_user_graphic(gr):
                continue
            if gr not in selected:
                selected.append(gr)
            gid = _lh58_gid(gr)
            if gid:
                gids.add(gid)
        except Exception:
            pass
    if not selected:
        return []
    if not expand_groups:
        return selected
    out = []
    try:
        all_graphics = list(getattr(getattr(self, 'current_unit', None), 'graphics', []) or [])
    except Exception:
        all_graphics = []
    for gr in all_graphics:
        try:
            if not _lh58_is_user_graphic(gr):
                continue
            gid = _lh58_gid(gr)
            if gr in selected or (gid and gid in gids):
                if gr not in out:
                    out.append(gr)
        except Exception:
            pass
    return out


def _lh58_bbox(gr):
    x = float(getattr(gr, 'x', 0.0) or 0.0)
    y = float(getattr(gr, 'y', 0.0) or 0.0)
    w = float(getattr(gr, 'w', 0.0) or 0.0)
    h = float(getattr(gr, 'h', 0.0) or 0.0)
    x2 = x + w
    y2 = y - h
    return min(x, x2), min(y, y2), max(x, x2), max(y, y2)


def _lh58_group_bbox(graphics):
    boxes = [_lh58_bbox(g) for g in graphics]
    if not boxes:
        return None
    return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)


def _lh58_apply_graphics_scale(self, direction:int):
    graphics = _lh58_selected_graphics(self, expand_groups=True)
    if not graphics:
        return False
    b = _lh58_group_bbox(graphics)
    if not b:
        return False
    minx, miny, maxx, maxy = b
    cur_w = max(0.0, maxx - minx)
    cur_h = max(0.0, maxy - miny)
    min_size = _lh58_grid_step(self)
    inc = _lh58_visible_increment(self)

    # BODY-like: width and height are stepped independently, then snapped.  This
    # guarantees a selected 3x3 rectangle becomes 4x4 and stays centered.
    target_w = max(min_size, _lh58_snap(self, cur_w + (inc if int(direction) > 0 else -inc)))
    target_h = max(min_size, _lh58_snap(self, cur_h + (inc if int(direction) > 0 else -inc)))
    sx = target_w / cur_w if cur_w > 1e-12 else 1.0
    sy = target_h / cur_h if cur_h > 1e-12 else 1.0
    if abs(sx - 1.0) < 1e-12 and abs(sy - 1.0) < 1e-12:
        return True

    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0
    try:
        self.push_undo_state()
    except Exception:
        pass

    for gr in graphics:
        x = float(getattr(gr, 'x', 0.0) or 0.0)
        y = float(getattr(gr, 'y', 0.0) or 0.0)
        w = float(getattr(gr, 'w', 0.0) or 0.0)
        h = float(getattr(gr, 'h', 0.0) or 0.0)
        shape = str(getattr(gr, 'shape', '') or '').lower()

        # Transform the object's own center relative to the selected logical
        # origin. For one object this origin is its own bbox center; for a group
        # it is the group's maximum x/y bbox center.
        gcx = x + w / 2.0
        gcy = y - h / 2.0
        ngcx = _lh58_snap(self, cx + (gcx - cx) * sx)
        ngcy = _lh58_snap(self, cy + (gcy - cy) * sy)

        nw = _lh58_snap(self, w * sx)
        nh = _lh58_snap(self, h * sy)
        if shape not in ('line', 'arc'):
            sw = -1.0 if w < 0 else 1.0
            sh = -1.0 if h < 0 else 1.0
            if abs(nw) < min_size:
                nw = sw * min_size
            if abs(nh) < min_size:
                nh = sh * min_size
        else:
            # Lines may be exactly vertical or horizontal. Preserve legitimate
            # zero axes, but never collapse an originally non-zero axis.
            if abs(w) > 1e-12 and abs(nw) < min_size:
                nw = (1.0 if w >= 0 else -1.0) * min_size
            if abs(h) > 1e-12 and abs(nh) < min_size:
                nh = (1.0 if h >= 0 else -1.0) * min_size
            try:
                if getattr(gr, 'ctrl_x', None) is not None:
                    gr.ctrl_x = _lh58_snap(self, float(gr.ctrl_x) * sx)
                if getattr(gr, 'ctrl_y', None) is not None:
                    gr.ctrl_y = _lh58_snap(self, float(gr.ctrl_y) * sy)
                if getattr(gr, 'curve_radius', None) not in (None, 0, 0.0):
                    gr.curve_radius = _lh58_snap(self, float(gr.curve_radius) * sy)
            except Exception:
                pass

        gr.w = nw
        gr.h = nh
        gr.x = _lh58_snap(self, ngcx - nw / 2.0)
        gr.y = _lh58_snap(self, ngcy + nh / 2.0)

    try:
        self.dirty = True
    except Exception:
        pass
    try:
        self.update_current_unit_canvas_positions()
    except Exception:
        try:
            self.schedule_scene_refresh()
        except Exception:
            pass
    try:
        self.refresh_properties()
    except Exception:
        pass
    try:
        self.rebuild_tree()
    except Exception:
        pass
    try:
        self.view.viewport().update()
    except Exception:
        pass
    return True


def _lh58_scale_selected_grid(self, direction:int):
    try:
        if self._selected_body_active():
            return _lh58_prev_scale_selected_grid(self, direction) if _lh58_prev_scale_selected_grid else None
    except Exception:
        pass
    if _lh58_apply_graphics_scale(self, int(direction)):
        return None
    if _lh58_prev_scale_selected_grid:
        return _lh58_prev_scale_selected_grid(self, direction)


def _lh58_scale_selected(self, factor):
    try:
        if self._selected_body_active():
            return _lh58_prev_scale_selected(self, factor) if _lh58_prev_scale_selected else None
    except Exception:
        pass
    try:
        direction = 1 if float(factor) >= 1.0 else -1
    except Exception:
        direction = 1
    return _lh58_scale_selected_grid(self, direction)


def _lh58_group_selected_graphics(self):
    models = _lh58_selected_graphics(self, expand_groups=False)
    if len(models) < 2:
        try:
            QMessageBox.information(self, 'Group Graphics', 'Bitte mindestens zwei eingefügte Grafikobjekte auswählen.')
        except Exception:
            pass
        return
    try:
        self.push_undo_state()
    except Exception:
        pass
    import uuid as _lh58_uuid
    gid = 'G' + _lh58_uuid.uuid4().hex[:8]
    for gr in models:
        _lh58_set_gid(gr, gid)
    try:
        self.dirty = True
        self.update_current_unit_canvas_positions()
        self.rebuild_tree()
        self.refresh_properties()
        self.statusBar().showMessage(f'Grafikgruppe erstellt: {len(models)} Objekte.', 4000)
    except Exception:
        pass


def _lh58_ungroup_selected_graphics(self):
    models = _lh58_selected_graphics(self, expand_groups=True)
    if not models:
        try:
            QMessageBox.information(self, 'Ungroup Graphics', 'Keine Grafikgruppe ausgewählt.')
        except Exception:
            pass
        return
    try:
        self.push_undo_state()
    except Exception:
        pass
    for gr in models:
        _lh58_set_gid(gr, '')
    try:
        self.dirty = True
        self.update_current_unit_canvas_positions()
        self.rebuild_tree()
        self.refresh_properties()
        self.statusBar().showMessage('Grafikgruppe aufgehoben.', 4000)
    except Exception:
        pass


def _lh58_install_group_ui(self):
    if getattr(self, '_lh58_group_ui_installed', False):
        return
    self._lh58_group_ui_installed = True
    try:
        edit_menu = None
        for act in self.menuBar().actions():
            if str(act.text()).replace('&', '').lower() == 'edit':
                edit_menu = act.menu()
                break
        if edit_menu is None:
            edit_menu = self.menuBar().addMenu('&Edit')
        edit_menu.addSeparator()
        a_group = QAction('Group Graphics', self)
        a_group.setShortcut(QKeySequence('Ctrl+G'))
        a_group.triggered.connect(self.group_selected_graphics)
        edit_menu.addAction(a_group)
        self.addAction(a_group)
        a_ungroup = QAction('Ungroup Graphics', self)
        a_ungroup.setShortcut(QKeySequence('Ctrl+Shift+G'))
        a_ungroup.triggered.connect(self.ungroup_selected_graphics)
        edit_menu.addAction(a_ungroup)
        self.addAction(a_ungroup)
    except Exception:
        pass
    try:
        tb = self.addToolBar('Graphic Group')
        btn = QPushButton('Group Graphics')
        btn.setToolTip('Ausgewählte eingefügte Grafikobjekte gruppieren (Ctrl+G)')
        btn.clicked.connect(self.group_selected_graphics)
        tb.addWidget(btn)
        btn = QPushButton('Ungroup Graphics')
        btn.setToolTip('Grafikgruppe aufheben (Ctrl+Shift+G)')
        btn.clicked.connect(self.ungroup_selected_graphics)
        tb.addWidget(btn)
    except Exception:
        pass


try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _cls.scale_selected_grid = _lh58_scale_selected_grid
        _cls.scale_selected = _lh58_scale_selected
        _cls.group_selected_graphics = _lh58_group_selected_graphics
        _cls.ungroup_selected_graphics = _lh58_ungroup_selected_graphics
        _old_init = _cls.__init__
        def _lh58_new_init(self, *args, __old_init=_old_init, **kwargs):
            __old_init(self, *args, **kwargs)
            try:
                _lh58_install_group_ui(self)
            except Exception:
                pass
        _cls.__init__ = _lh58_new_init
except Exception:
    pass
