from __future__ import annotations
import copy
import csv
import json
from pathlib import Path
from dataclasses import asdict
from PySide6.QtCore import Qt, QTimer, QRectF, QEvent, QObject
from PySide6.QtGui import QAction, QColor, QKeySequence, QFontDatabase
from PySide6.QtWidgets import *

from symbol_wizard.models.document import *
from symbol_wizard.rules.grid import PX_PER_INCH, duplicate_pin_numbers, next_pin_number
from symbol_wizard.rules.placement import create_auto_pin
from symbol_wizard.graphics.scene import SymbolScene, SHEET_INCHES, sheet_rect_for
from symbol_wizard.graphics.view import SymbolView
from symbol_wizard.graphics.items import BodyItem, PinItem, TextItem, GraphicItem, pen_for
from symbol_wizard.io.json_store import save_library, load_library, save_symbol, load_symbol
from symbol_wizard.io.mentor_sym import import_mentor_sym, export_mentor_sym


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
        self.templates = parent.available_templates()
        self.unit = copy.deepcopy(next(iter(self.templates.values()), SymbolUnitModel()))
        self.draw_tool = DrawTool.SELECT.value
        self.default_color = (0, 0, 0)
        self.symbol = SymbolModel(name='Template Editor', units=[self.unit])
        self._format_guide_offset = (0.0, 0.0)
        self.current_unit_index = 0
        self.scene = SymbolScene(self)
        self.view = SymbolView(self.scene, self)
        self.clipboard = []
        self.clipboard_is_cut = False
        self.undo_stack = []
        self.redo_stack = []
        self.max_history = 10
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
        self.load_selected_template()

    @property
    def current_unit(self):
        return self.unit

    @property
    def grid_px(self):
        return self.symbol.grid_inch * PX_PER_INCH

    def scene_to_grid_x(self, x): return round(x / self.grid_px)
    def scene_to_grid_y(self, y): return round(-y / self.grid_px)

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
        self.template_combo = QComboBox(); self.template_combo.addItems(sorted(self.templates.keys()))
        self.template_combo.currentTextChanged.connect(self.request_template_change)
        self.template_combo.activated.connect(lambda _idx: self.request_template_change(self.template_combo.currentText()))
        top.addWidget(QLabel('Template:')); top.addWidget(self.template_combo, 1)
        self.rename_edit = QLineEdit(); top.addWidget(QLabel('Name / Save as:')); top.addWidget(self.rename_edit, 1)
        save_btn = QPushButton('Save Template'); save_btn.clicked.connect(lambda _checked=False: self.save_template())
        top.addWidget(save_btn)
        layout.addLayout(top)
        tools = QHBoxLayout()
        self.tool_buttons = {}
        for tool, label in [(DrawTool.SELECT, 'Select/Edit'), (DrawTool.PIN_LEFT, 'Pin L'), (DrawTool.PIN_RIGHT, 'Pin R'), (DrawTool.TEXT, 'Text'), (DrawTool.LINE, 'Line'), (DrawTool.RECT, 'Rect'), (DrawTool.ELLIPSE, 'Ellipse')]:
            b = QPushButton(label); b.setCheckable(True); b.clicked.connect(lambda _, t=tool.value: self.set_tool(t))
            tools.addWidget(b); self.tool_buttons[tool.value] = b
        self.tool_buttons[self.draw_tool].setChecked(True)
        for label, fn in [('Select All', self.select_all_canvas), ('Undo', self.undo), ('Redo', self.redo)]:
            b = QPushButton(label); b.clicked.connect(fn); tools.addWidget(b)
        tools.addStretch(); layout.addLayout(tools)
        tools = QHBoxLayout()
        for label, fn in [('⟲ 15°', lambda: self.rotate_selected(-15)), ('⟳ 15°', lambda: self.rotate_selected(15)), ('Flip H', self.flip_selected_horizontal), ('Flip V', self.flip_selected_vertical)]:
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

    def set_tool(self, t):
        self.draw_tool = t
        for k, b in self.tool_buttons.items(): b.setChecked(k == t)
        self.view.setDragMode(QGraphicsView.RubberBandDrag if t == DrawTool.SELECT.value else QGraphicsView.NoDrag)

    def push_undo_state(self):
        self.dirty = True
        self.undo_stack.append(copy.deepcopy(self.unit))
        if len(self.undo_stack) > self.max_history: self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        self.set_tool(DrawTool.SELECT.value)
        if not self.undo_stack: return
        self.set_tool(DrawTool.SELECT.value)
        self.redo_stack.append(copy.deepcopy(self.unit)); self.unit = self.undo_stack.pop(); self.symbol.units=[self.unit]; self.rebuild_scene()
    def redo(self):
        self.set_tool(DrawTool.SELECT.value)
        if not self.redo_stack: return
        self.set_tool(DrawTool.SELECT.value)
        self.undo_stack.append(copy.deepcopy(self.unit)); self.unit = self.redo_stack.pop(); self.symbol.units=[self.unit]; self.rebuild_scene()

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
        """Stable serializable state used to detect unsaved template edits."""
        try:
            return asdict(self.unit)
        except Exception:
            return copy.deepcopy(self.unit)

    def _template_has_unsaved_changes(self) -> bool:
        """Detect changes even when a canvas operation did not mark dirty."""
        if bool(getattr(self, 'dirty', False)):
            return True
        try:
            return getattr(self, '_clean_template_snapshot', None) is not None and self._template_state() != self._clean_template_snapshot
        except Exception:
            return bool(getattr(self, 'dirty', False))

    def _ask_save_if_dirty(self) -> bool:
        """Return True when the pending action may continue."""
        if not (getattr(self, 'dirty', False) or self._template_has_unsaved_changes()):
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
        name = self.template_combo.currentText()
        if not name: return
        self._loading_template = True
        self.unit = copy.deepcopy(self.templates[name]); self.symbol.units=[self.unit]
        if hasattr(self, 'origin_combo'):
            self.origin_combo.blockSignals(True)
            self.origin_combo.setCurrentText(getattr(self.symbol, 'origin', OriginMode.CENTER.value))
            self.origin_combo.blockSignals(False)
        self.rename_edit.setText(name)
        self._current_template_name = name
        self._clean_template_snapshot = self._template_state()
        self.dirty = False
        self._loading_template = False
        self.rebuild_scene()

    def save_template(self, show_message=True):
        name = self.rename_edit.text().strip() or self.template_combo.currentText() or 'Template'
        self.templates[name] = copy.deepcopy(self.unit)
        if hasattr(self.main, 'merge_save_template_to_file'):
            self.main.merge_save_template_to_file(name, self.unit)
            self.main.symbol_templates.clear()
        if hasattr(self.main, 'apply_template_style_to_matching_symbols'):
            self.main.apply_template_style_to_matching_symbols(name, self.unit)
        if self.template_combo.findText(name) < 0:
            self.template_combo.addItem(name)
        self.template_combo.blockSignals(True)
        self.template_combo.setCurrentText(name)
        self.template_combo.blockSignals(False)
        self._current_template_name = name
        self._clean_template_snapshot = self._template_state()
        self.dirty = False
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
            self.form.addRow('Width [grid]', self._dbl(m.width, lambda v: self._set(m, 'width', max(1.0, round(float(v)))), 1, 500, 1))
            self.form.addRow('Height [grid]', self._dbl(m.height, lambda v: self._set(m, 'height', max(1.0, round(float(v)))), 1, 500, 1))
            self.form.addRow('Line style', self._combo([x.value for x in LineStyle], getattr(m, 'line_style', LineStyle.SOLID.value), lambda v: self._set(m, 'line_style', v)))
            self.form.addRow('Line width', self._dbl(getattr(m, 'line_width', 0.03), lambda v: self._set(m, 'line_width', float(v)), .01, 1, .01))
            self.form.addRow('Rotation [deg]', self._dbl(getattr(m, 'rotation', 0), lambda v: self._set(m, 'rotation', v), -360, 360, 15))
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
        w=QComboBox(); w.addItems(items); w.setCurrentText(str(val)); w.currentTextChanged.connect(fn); return w
    def _check(self, value, fn):
        w=QCheckBox(); w.setChecked(bool(value)); w.toggled.connect(fn); return w
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
            tm = b.attribute_texts.get(key)
            if tm is None:
                tm = TextModel(text=default_text, x=default_x, y=default_y,
                               font_family=font.family, font_size_grid=font.size_grid, color=font.color)
                tm.h_align = default_h
                tm.v_align = default_v
                b.attribute_texts[key] = tm
            tm.text = default_text
            if not getattr(tm, 'font_family', ''):
                tm.font_family = font.family
            if not getattr(tm, 'font_size_grid', 0):
                tm.font_size_grid = font.size_grid
            if not getattr(tm, 'color', None):
                tm.color = font.color
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

    def origin_mode_changed(self, mode: str):
        self.reset_origin_to_selected_anchor(mode)

    def reset_origin_to_selected_anchor(self, mode: str | None = None):
        mode = mode or (self.origin_combo.currentText() if hasattr(self, 'origin_combo') else OriginMode.CENTER.value)
        body = self.unit.body
        ax, ay = self.body_anchor_point(body, mode)
        old_mode = getattr(self.symbol, 'origin', OriginMode.CENTER.value)
        if abs(ax) < 1e-9 and abs(ay) < 1e-9 and old_mode == mode:
            return
        self.push_undo_state()
        self.symbol.origin = mode
        body.x -= ax
        body.y -= ay
        for p in self.unit.pins:
            p.x -= ax; p.y -= ay
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
        self.dock_pins_to_body(self.unit)
        self.rebuild_scene()

    def add_pin(self, side, x=None, y=None):
        self.push_undo_state(); p=PinModel(number=self._unique_pin_number(), side=side, name=self._unique_pin_name('PIN'), function='')
        p.x = x if x is not None else (self.unit.body.x if side == PinSide.LEFT.value else self.unit.body.x + self.unit.body.width)
        p.y = y if y is not None else self.unit.body.y - 1 - len(self.unit.pins)
        self.unit.pins.append(p); self.dock_pins_to_body(self.unit); self.rebuild_scene()
    def add_graphic(self, tool, x, y):
        self.push_undo_state(); shape={DrawTool.LINE.value:'line',DrawTool.RECT.value:'rect',DrawTool.ELLIPSE.value:'ellipse'}[tool]
        self.unit.graphics.append(GraphicModel(shape=shape, x=x, y=y, w=2, h=0 if shape=='line' else 2)); self.rebuild_scene()
    def select_model_after_rebuild(self, model): pass
    def new_body(self): self.push_undo_state(); self.unit.body=SymbolBodyModel(); self.rebuild_scene()
    def delete_body(self): self.push_undo_state(); self.unit.body.width=0.01; self.unit.body.height=0.01; self.rebuild_scene()
    def select_all_canvas(self):
        self.set_tool(DrawTool.SELECT.value)
        for item in self.scene.items():
            kind = item.data(0)
            filter_kind = 'TEXT' if kind in ('ATTR_REF_DES', 'ATTR_BODY') else kind
            if kind in ('BODY','PIN','TEXT','ATTR_REF_DES','ATTR_BODY','GRAPHIC') and self.selection_enabled.get(filter_kind, True): item.setSelected(True)
        self.refresh_properties()
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
            elif kind=='GRAPHIC': self.unit.graphics.append(m)
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

    def rebuild_tree(self): pass
    def rebuild_pin_table(self): pass



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        install_no_wheel_value_filter(self)
        self.library = LibraryModel()
        self.current_unit_index = 0
        self.draw_tool = DrawTool.SELECT.value
        self.clipboard: list[tuple[str, object]] = []
        self.clipboard_is_cut = False
        self.undo_stack: list[LibraryModel] = []
        self.redo_stack: list[LibraryModel] = []
        self.max_history = 10
        self._history_guard = False
        self.dirty = False
        self._dirty_symbol_index: int | None = None
        self._clean_symbol_snapshot: SymbolModel | None = None
        self.symbol_templates: dict[str, SymbolUnitModel] = {}
        self.suspend = False
        self._selection_restore_ids: set[int] = set()
        self.default_color = (0, 0, 0)
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
        return self.symbol.grid_inch * PX_PER_INCH

    def scene_to_grid_x(self, x):
        return round(x / self.grid_px)

    def scene_to_grid_y(self, y):
        return round(-y / self.grid_px)

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
        single_layout.addWidget(QLabel('Symbols'))
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
            ('Import Mentor Symbol .sym', self.import_mentor_symbol, None),
            ('Export Current Mentor Symbol .sym', self.export_current_mentor_symbol, None),
            ('Import PINMUX CSV', self.import_pinmux_csv, None),
            ('---', None, None),
            ('Exit', self.close, None),
        ]
        for label, fn, sc in entries:
            if label == '---':
                file_menu.addSeparator(); continue
            a = QAction(label, self)
            a.triggered.connect(fn)
            if sc:
                a.setShortcut(QKeySequence(sc))
            file_menu.addAction(a)

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

        tools_menu = mb.addMenu('&Tools')
        a = QAction('Edit Symbol Templates', self)
        a.triggered.connect(self.edit_symbol_templates)
        tools_menu.addAction(a)
        tools_menu.addSeparator()
        a = QAction('Validate Pins', self)
        a.triggered.connect(self.validate_pins)
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
            ('⟲ 15°', lambda: self.rotate_selected(-15)),
            ('⟳ 15°', lambda: self.rotate_selected(15)),
            ('Flip H', self.flip_selected_horizontal),
            ('Flip V', self.flip_selected_vertical),
            ('Scale +', lambda: self.scale_selected(1.1)),
            ('Scale -', lambda: self.scale_selected(1 / 1.1)),
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

Symbol Wizard is a grid-based editor for creating, editing, validating, and exporting electrical symbols for Xpedition-oriented workflows. It combines symbol body editing, pin management, template handling, text and attribute placement, graphical object editing, and validation in one application.

The editor is designed around a fixed grid. Most object positions, alignments, increments, and body-related transformations are intended to snap to this grid so that generated symbols remain consistent and reproducible.

## 2. Main Window Overview

The main window contains three primary areas:

- **Left workspace**: symbol lists, split-symbol units, pin overview tables, and the object tree.
- **Center canvas**: the graphical symbol editor with grid, body, pins, text, attributes, and graphics.
- **Right properties panel**: context-sensitive settings for the selected object or selected objects.

The ribbon at the top contains drawing tools, setup controls, style controls, transformation tools, pin actions, and this Help section.

## 3. Creating Symbols

Use **File > New Symbol** to create a regular symbol. Use **File > New Split Symbol** to create a split symbol with multiple units or parts. For split symbols, each unit can be edited separately while validation still checks the full symbol across all units.

Symbol names are shown as tabs. You can switch between symbols using the symbol tabs or canvas tabs. Existing symbols can be renamed from the symbol tab context menu.

## 4. Grid and Sheet Setup

Use **Grid inch** to define the grid size. The grid is the central reference for body size, object placement, text anchors, pin placement, and many transformations.

Use **Format** to select the sheet format. Use **Zoom Fit** to fit the current symbol into the view.

## 5. Origin Handling

The **Origin** selector defines how the symbol origin is interpreted. Use **Origin Reset** to reset the origin based on the selected anchor. When the body origin changes, attached objects such as pins, plain text, graphics, and body attributes are moved consistently with the body.

This is especially important for templates because template body attributes must stay attached in the same way as pins, text, and graphic objects.

## 6. Drawing and Selecting Objects

Use the draw tools to create objects on the canvas:

- **Select/Edit**: select and modify existing objects.
- **Pin L / Pin R**: create left- or right-oriented pins.
- **Text**: create plain text objects.
- **Line, Rect, Ellipse**: create graphic objects.

The **Selectable** control limits which object types can be selected. This is useful when editing dense symbols where text, pins, body, and graphics overlap.

## 7. Body Editing

The body represents the main symbol container. Body size is edited with width and height fields. Increment/decrement buttons for body and graphic object size use the grid step. If a non-grid value is needed, type the numeric value directly into the field.

Body color and rotation belong to the body properties. Body color can also be changed through a global multi-selection color operation when the body is selected.

When the body is moved or scaled, attached objects must follow consistently. This includes pins, plain texts, graphic objects, symbol attributes, and template body attributes.

## 8. Pin Editing

Pins can be edited either in the canvas, the object tree, or the pin tables. The pin overview table supports editing of:

- Pin number
- Pin name
- Pin function
- Pin type
- Side
- Inverted state

Use **Selected Pin Actions** to assign sides or distribute selected pins vertically.

Use **Tools > Validate Pins** to check the pin configuration. Validation includes checks for duplicate pin numbers and duplicate pin names.

## 9. Text and Attribute Editing

Plain text and generated attributes use the same grid-anchor concept. Each text object has a horizontal and vertical anchor combination. The green anchor point represents the exact grid anchor used for placement.

Horizontal anchor modes:

- **Left**: the green point is on a vertical grid line at the left side of the text; the text grows to the right.
- **Center**: the green point is on a vertical grid line at the horizontal center of the text.
- **Right**: the green point is on a vertical grid line at the right side of the text; the text grows to the left.

Vertical anchor modes:

- **Upper**: the green point is on a horizontal grid line at the upper edge of the text.
- **Center**: the green point is on a horizontal grid line at the vertical center of the text.
- **Lower**: the green point is on a horizontal grid line at the lower edge of the text.

All nine combinations are supported: upper-left, upper-center, upper-right, center-left, center-center, center-right, lower-left, lower-center, and lower-right. The same behavior applies to plain text and attributes.

## 10. Text Alignment and Distribution

When multiple text objects or attributes are selected, alignment uses the grid anchor. For example, aligning left moves the selected objects so their left anchors lie on the same vertical grid line. Aligning right uses the right anchor. Center alignment uses the center anchor.

Vertical alignment works the same way using horizontal grid lines:

- Upper aligns upper anchors.
- Center aligns center anchors.
- Lower aligns lower anchors.

Distribution keeps selected objects evenly spaced. For text objects, distribution is based on their anchor positions, not only their bounding rectangles. This avoids visible drift from the grid.

## 11. Text Wrapping

Plain text normally does not wrap automatically. A manual line break can be inserted with **Shift + Enter** when editing text. Attribute text can optionally support wrapping depending on the attribute settings. The default behavior is no wrapping.

## 12. Graphic Objects

Graphic objects include lines, rectangles, ellipses, and other shape variants. Shape-specific properties are displayed when the shape type is changed. For example, changing a graphic object shape immediately refreshes the available property fields for that shape.

Graphic object width and height spinbox increments follow the grid. Non-grid values can still be entered manually.

## 13. Color Handling

Color can be set on individual objects in their properties. The ribbon RGB control can also be used as a multi-selection color command. When multiple objects are selected, changing color applies to all supported selected objects, including:

- Body
- Pins
- Plain text
- Attributes
- Graphic objects

The selected color is synchronized with the active selection wherever possible.

## 14. Rotation and Transformations

Use the transform buttons to rotate selected objects by 15 degrees clockwise or counter-clockwise. Flip operations mirror selected objects horizontally or vertically. Scale operations change selected object dimensions.

Pins, graphics, body, text, and attributes should retain their changed transformation values instead of briefly changing and reverting.

## 15. Template Editor

Use **Tools > Edit Symbol Templates** to open the template editor. The template editor provides a canvas-based editor for reusable symbol templates. It supports the same core editing concepts as the main Symbol Wizard:

- Grid-based placement
- Origin handling
- Body editing
- Pins
- Plain text
- Graphics
- Body attributes
- Multi-selection operations
- Undo and redo
- Copy, cut, paste, and select all

If a template has unsaved changes, a save prompt is shown when closing the template editor or switching to another template.

## 16. Keyboard Shortcuts

The main editor supports common shortcuts:

- **Ctrl + A**: select all canvas objects
- **Ctrl + C**: copy selected objects
- **Ctrl + X**: cut selected objects
- **Ctrl + V**: paste copied objects
- **Ctrl + Z**: undo
- **Ctrl + Y**: redo
- **Delete**: delete selected objects
- **Ctrl + S**: save current symbol JSON
- **Ctrl + Shift + S**: save all symbols JSON
- **Ctrl + O**: open library JSON
- **Ctrl + F**: zoom to fit symbol
- **F5**: refresh canvas

The template editor also supports the same essential edit shortcuts for template work.

## 17. Saving and Loading

Use **File > Save Current Symbol JSON** to save the active symbol. Use **File > Save All Symbols JSON** to save the full library. Use **File > Open Library JSON** to load a saved library. Individual symbol JSON files can also be imported.

Template changes are managed through the template editor. Save prompts appear when necessary to prevent accidental loss of template edits.

## 18. Pinmux Import

Use **File > Import PINMUX CSV** to import pin information from a CSV file. After importing, review the pin table and run **Validate Pins** to detect duplicate numbers, duplicate names, or inconsistent pin data.

## 19. Recommended Workflow

1. Create or open a symbol library.
2. Set grid and sheet format.
3. Create or choose a suitable body/template.
4. Add pins and assign pin metadata.
5. Add plain text, attributes, and graphics.
6. Align text and attributes with the grid anchor system.
7. Use multi-select alignment and distribution for consistent placement.
8. Validate pins before export or delivery.
9. Save the current symbol or full library.

## 20. About

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
        self.dock_pins_to_body(u)

        body_item = BodyItem(u.body, self)
        self.apply_item_selectability(body_item)
        self.scene.addItem(body_item)
        self._restore_or_select_item(body_item, selected_ids)

        self.add_attribute_text_items(u)
        for g in u.graphics:
            item = GraphicItem(g, self)
            self.apply_item_selectability(item)
            self.scene.addItem(item)
            self._restore_or_select_item(item, selected_ids)
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
            tm = b.attribute_texts.get(key)
            if tm is None:
                tm = TextModel(text=default_text, x=default_x, y=default_y,
                               font_family=font.family, font_size_grid=font.size_grid, color=font.color)
                tm.h_align = default_h
                tm.v_align = default_v
                b.attribute_texts[key] = tm
            # Attribute content is generated; geometry/font/alignment are persistent and user-editable.
            tm.text = default_text
            if not getattr(tm, 'font_family', ''):
                tm.font_family = font.family
            if not getattr(tm, 'font_size_grid', 0):
                tm.font_size_grid = font.size_grid
            if not getattr(tm, 'color', None):
                tm.color = font.color
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
        self.form.addRow(QLabel(f'Selected: {kind}'))
        if kind == 'BODY': self.body_props(item)
        elif kind == 'PIN': self.pin_props(item)
        elif kind in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY'): self.text_props(item)
        elif kind == 'GRAPHIC': self.graphic_props(item)

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
            elif k in ('BODY', 'PIN', 'TEXT', 'ATTR_REF_DES', 'ATTR_BODY'):
                m.color = color
                if hasattr(it, 'apply_text_from_model'):
                    it.apply_text_from_model()
                if k in ('ATTR_REF_DES', 'ATTR_BODY'):
                    self._sync_body_font_from_attribute_text(it)
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
                tm.font_family = font.family
                tm.font_size_grid = font.size_grid
                tm.color = font.color

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
            tm.font_family = font.family
            tm.font_size_grid = font.size_grid
            tm.color = font.color

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
        self.form.addRow('Width [grid]', self._dbl(m.width, lambda v: self.set_body_dim(item, 'width', max(1.0, round(float(v)))), 1, 300, 1))
        self.form.addRow('Height [grid]', self._dbl(m.height, lambda v: self.set_body_dim(item, 'height', max(1.0, round(float(v)))), 1, 300, 1))
        self.form.addRow('Line style', self._combo([x.value for x in LineStyle], m.line_style, lambda v: self.set_and_refresh(m, 'line_style', v)))
        self.form.addRow('Line width', self._dbl(m.line_width, lambda v: self.set_and_refresh(m, 'line_width', v), .01, 1, .01))
        self.transform_props(m)
        self.form.addRow('Color', self._color_button_row('Color RGB', m.color, lambda _checked=False: self.color_model(m)))
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
            self.form.addRow(k, row)


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
        self.form.addRow('Rotation [deg]', self._dbl(getattr(m, 'rotation', 0), lambda v: self.set_and_refresh(m, 'rotation', v), -360, 360, 15))

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
    def move_current_unit_group(self, dx: float, dy: float, source_body=None):
        u = self.current_unit
        # Body is the anchor. When it moves, all user-owned objects in this unit follow.
        for p in u.pins:
            p.x += dx
            p.y += dy
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
        self.push_undo_state()
        for it in self.scene.selectedItems():
            if it.data(0) == 'PIN':
                it.model.line_style = self.line_style.currentText(); it.model.line_width = self.line_width.value(); it.model.color = self.default_color
            elif it.data(0) == 'GRAPHIC':
                it.model.style.line_style = self.line_style.currentText(); it.model.style.line_width = self.line_width.value(); it.model.style.stroke = self.default_color
            elif it.data(0) == 'BODY':
                it.model.line_style = self.line_style.currentText(); it.model.line_width = self.line_width.value(); it.model.color = self.default_color
        self.schedule_scene_refresh()

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
        self.current_unit.graphics.append(model)
        self.select_model_after_rebuild(model)
        self.rebuild_scene(); self.rebuild_tree()

    def rotate_selected(self, deg):
        self.push_undo_state()
        for it in self.scene.selectedItems():
            if hasattr(it, 'rotate_by'):
                it.rotate_by(deg)
        self.schedule_scene_refresh(visual_only=True)

    def scale_selected(self, factor):
        self.push_undo_state()
        for it in self.scene.selectedItems():
            if hasattr(it, 'scale_selected'):
                it.scale_selected(factor)
        self.enforce_symbol_size_limit(silent=True)
        self.schedule_scene_refresh(visual_only=True)

    def flip_selected_horizontal(self):
        self.push_undo_state()
        for it in self.scene.selectedItems():
            if hasattr(it, 'flip_horizontal'):
                it.flip_horizontal()
        self.schedule_scene_refresh(visual_only=True)

    def flip_selected_vertical(self):
        self.push_undo_state()
        for it in self.scene.selectedItems():
            if hasattr(it, 'flip_vertical'):
                it.flip_vertical()
        self.schedule_scene_refresh(visual_only=True)

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

    def validate_pins(self, silent=False):
        dup = duplicate_pin_numbers(self.symbol)
        name_map = {}
        dup_names = []
        try:
            for u in getattr(self.symbol, 'units', []):
                for p in getattr(u, 'pins', []):
                    n = str(getattr(p, 'name', '') or '').strip()
                    if not n:
                        continue
                    if n in name_map and n not in dup_names:
                        dup_names.append(n)
                    name_map[n] = True
        except Exception:
            pass

        msgs = []
        if dup:
            msgs.append('Doppelte Pinnummern im Symbol sind verboten: ' + ', '.join(dup))
        if dup_names:
            msgs.append('Doppelte Pinnamen im Symbol sind verboten: ' + ', '.join(dup_names))

        if msgs and not silent:
            QMessageBox.warning(self, 'Pin validation', '\n'.join(msgs))
        elif not msgs and not silent:
            QMessageBox.information(self, 'Pin validation', 'Keine doppelten Pinnummern oder Pinnamen gefunden.')
        return not msgs

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
        if tab_index != self.library.current_symbol_index and not self.confirm_discard_if_dirty():
            self.canvas_tabs.blockSignals(True); self.canvas_tabs.setCurrentIndex(self.library.current_symbol_index); self.canvas_tabs.blockSignals(False); return
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
        s.units = [copy.deepcopy(self.available_templates().get(template_name, SymbolUnitModel()))]
        s.units[0].name = 'Unit A'
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
        base = copy.deepcopy(self.available_templates(split_only=True).get(template_name, SymbolUnitModel()))
        s.units = [copy.deepcopy(base), copy.deepcopy(base)]
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
        self.rebuild_scene()

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

    def shift_unit_geometry(self, unit: SymbolUnitModel, dx: float, dy: float):
        unit.body.x += dx
        unit.body.y += dy
        for p in unit.pins:
            p.x += dx; p.y += dy
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
        ax, ay = self.body_anchor_point(unit.body, mode)
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
        ax, ay = self.body_anchor_point(self.current_unit.body, mode)
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
            uax, uay = self.body_anchor_point(unit.body, mode)
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
        if QMessageBox.question(self, 'Delete Split Part', f'Delete split part "{name}"?') != QMessageBox.Yes:
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

    def delete_symbol_from_tab(self, kind: str, tab_index: int):
        indices = self._symbol_indices(kind)
        if tab_index < 0 or tab_index >= len(indices):
            return
        si = indices[tab_index]
        name = self.library.symbols[si].name
        if len(self.library.symbols) <= 1:
            QMessageBox.warning(self, 'Delete Symbol', 'The last symbol cannot be deleted.')
            return
        if QMessageBox.question(self, 'Delete Symbol', f'Symbol "{name}" really delete?') != QMessageBox.Yes:
            return
        self.push_undo_state()
        del self.library.symbols[si]
        self.library.current_symbol_index = max(0, min(si, len(self.library.symbols)-1))
        self.current_unit_index = 0
        self.rebuild_all()

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
    def symbol_types_path(self):
        candidates = [
            Path(__file__).resolve().parents[2] / 'symbol_types.json',
            Path.cwd() / 'symbol_types.json',
            Path('/mnt/data/symbol_types.json'),
        ]
        for c in candidates:
            if c.exists():
                return c
        return None

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

    def load_symbol_type_templates(self) -> dict[str, SymbolUnitModel]:
        path = self.symbol_types_path()
        templates = {}
        if not path:
            return templates
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            for type_name, type_def in (data.get('types') or {}).items():
                subtypes = type_def.get('subtypes') or {}
                if not subtypes:
                    templates[type_name] = self.unit_from_template_def(type_name, None, data)
                # For types with subtypes, only the concrete subtype is edited/selected.
                for subtype_name in subtypes.keys():
                    templates[f'{type_name} / {subtype_name}'] = self.unit_from_template_def(type_name, subtype_name, data)
        except Exception as exc:
            self.statusBar().showMessage(f'symbol_types.json konnte nicht geladen werden: {exc}', 6000)
        return templates

    def available_templates(self, split_only: bool = False) -> dict[str, SymbolUnitModel]:
        templates = self.load_symbol_type_templates()
        templates.update(copy.deepcopy(self.symbol_templates))
        if split_only:
            return {k: v for k, v in templates.items() if k == 'IC' or k.startswith('IC /')}
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

    def ask_new_symbol_template(self, kind: str):
        templates = self.available_templates(split_only=(kind == SymbolKind.SPLIT.value))
        dlg = QDialog(self)
        dlg.setWindowTitle('Neues Symbol anlegen')
        layout = QFormLayout(dlg)
        combo = QComboBox(); combo.addItems(sorted(templates.keys()))
        name_edit = QLineEdit()
        name_edit.setMaxLength(24)
        def update_default_name():
            if not name_edit.text().strip():
                base = combo.currentText().split('/')[-1].strip().replace(' ', '_') or ('Split_Symbol' if kind == SymbolKind.SPLIT.value else 'Symbol')
                name_edit.setPlaceholderText(base[:24])
        combo.currentTextChanged.connect(lambda *_: update_default_name())
        update_default_name()
        layout.addRow('Template', combo)
        layout.addRow('Symbolname', name_edit)
        hint = QLabel('3 to 24 characters. The name is set during creation and can later be changed via Edit or the symbol tab context menu.')
        hint.setWordWrap(True); layout.addRow('', hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addRow(buttons)
        def accept_if_valid():
            n = name_edit.text().strip()
            if len(n) < 3 or len(n) > 24:
                QMessageBox.warning(dlg, 'Symbolname', 'Bitte einen Symbolnamen mit 3 bis 24 Zeichen eingeben.')
                return
            dlg.accept()
        buttons.accepted.connect(accept_if_valid); buttons.rejected.connect(dlg.reject)
        if dlg.exec() == QDialog.Accepted:
            return name_edit.text().strip(), combo.currentText()
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
        path = self.symbol_types_path()
        if not path:
            return
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            data = {'global_attributes': [], 'types': {}}
        data.setdefault('types', {})
        payload = self.unit_to_template_payload(unit)
        if ' / ' in template_name:
            type_name, subtype_name = [x.strip() for x in template_name.split(' / ', 1)]
            t = data['types'].setdefault(type_name, {'prefix': '?', 'subtypes': {}})
            t.setdefault('subtypes', {})
            sub = t['subtypes'].setdefault(subtype_name, {})
            # Merge-save: only the currently edited template fields are overwritten; all other metadata stays intact.
            sub.update({k: copy.deepcopy(v) for k, v in payload.items() if k != 'default_pins'})
            sub['default_pins'] = payload['default_pins']
            if 'body' not in t and 'body' in payload:
                t['body'] = copy.deepcopy(payload['body'])
        else:
            t = data['types'].setdefault(template_name, {'prefix': '?', 'subtypes': {}})
            t.update(copy.deepcopy(payload))
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
            s = import_mentor_sym(p)
        except Exception as exc:
            QMessageBox.critical(self, 'Import Mentor Symbol .sym', f'Die Mentor Symboldatei konnte nicht importiert werden:\n{exc}')
            return
        # Mentor-native symbols keep the real Mentor origin at (0,0); no auto-centering.
        if getattr(s, 'template_name', '') != 'mentor_native_origin':
            self.normalize_symbol_origins_for_import(s)
        s.name = self.library.unique_import_name(s.name)
        self.library.symbols.append(s)
        self.library.current_symbol_index = len(self.library.symbols) - 1
        self.current_unit_index = 0
        self.dirty = True
        self.undo_stack.clear(); self.redo_stack.clear()
        self.rebuild_all()
        self.statusBar().showMessage(f'Mentor Symbol importiert: {Path(p).name}', 5000)

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


# Mentor Pin Palette enabled
MENTOR_PIN_PALETTE = {
    "IN": "#4A90E2",
    "OUT": "#D0021B",
    "BI": "#BD10E0",
    "POWER": "#F5A623",
    "GROUND": "#7ED321",
    "ANALOG": "#50E3C2",
}

FILE_MENU_STRUCTURE = {
"Import": ["Import Mentor Single Symbol", "Import Mentor Split ZIP"],
"Export": ["Export Mentor Single Symbol", "Export Mentor Split ZIP"],
"Project": ["Open", "Save", "Save As"]
}
