from PySide6.QtGui import QFont, QPen
from PySide6.QtWidgets import QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit, QPushButton, QWidget

from symbol_wizard.config import PX_PER_INCH
from symbol_wizard.graphics.items import GraphicObjectItem, PinItem, SymbolBodyItem, TextGraphicsItem, qcolor_to_rgb, rgb_to_qcolor
from symbol_wizard.models.document import GraphicType, PinSide, PinType, SymbolBodyModel


class PropertiesPanel(QWidget):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.layout = QFormLayout(self)
        self.show_empty()

    def clear(self):
        while self.layout.rowCount():
            self.layout.removeRow(0)

    def show_empty(self):
        self.clear()
        self.layout.addRow(QLabel("No selection"))

    def refresh(self):
        selected = self.editor.scene.selectedItems()
        if not selected:
            self.show_empty()
            return
        item = selected[0]
        kind = item.data(0)
        self.clear()
        self.layout.addRow(QLabel(f"Selected: {kind}"))
        if kind == "PIN":
            self._pin(item)
        elif kind == "SYMBOL_BODY":
            self._body(item)
        elif kind == "TEXT":
            self._text(item)
        elif kind == "GRAPHIC":
            self._graphic(item)

    def _set_attr(self, model, attr: str, value, item):
        setattr(model, attr, value)
        item.update()
        self.editor.refresh_side_panels()

    def _pin(self, item: PinItem):
        model = item.model
        for label, attr in [("Pin Number", "number"), ("Pin Name", "name"), ("Pin Function", "function")]:
            line = QLineEdit(getattr(model, attr))
            line.textChanged.connect(lambda v, a=attr: self._set_attr(model, a, v, item))
            self.layout.addRow(label, line)

        pin_type = QComboBox()
        pin_type.addItems([p.value for p in PinType])
        pin_type.setCurrentText(model.pin_type)
        pin_type.currentTextChanged.connect(lambda v: self._set_attr(model, "pin_type", v, item))
        self.layout.addRow("Pin Type", pin_type)

        side = QComboBox()
        side.addItems([s.value for s in PinSide])
        side.setCurrentText(model.side)
        side.currentTextChanged.connect(lambda v: self._set_attr(model, "side", v, item))
        self.layout.addRow("Side", side)

        inverted = QCheckBox()
        inverted.setChecked(model.inverted)
        inverted.toggled.connect(lambda v: self._set_attr(model, "inverted", v, item))
        self.layout.addRow("Inverted", inverted)

        for label, attr in [("Show Number", "visible_number"), ("Show Name", "visible_name"), ("Show Function", "visible_function")]:
            cb = QCheckBox()
            cb.setChecked(getattr(model, attr))
            cb.toggled.connect(lambda v, a=attr: self._set_attr(model, a, v, item))
            self.layout.addRow(label, cb)

        self._color_button(model, item)

    def _body(self, item: SymbolBodyItem):
        model = item.model
        width = QDoubleSpinBox(); width.setRange(1, 200); width.setValue(model.width)
        width.valueChanged.connect(lambda v: self.editor.resize_body(item, width=v))
        self.layout.addRow("Width [grid]", width)

        height = QDoubleSpinBox(); height.setRange(1, 200); height.setValue(model.height)
        height.valueChanged.connect(lambda v: self.editor.resize_body(item, height=v))
        self.layout.addRow("Height [grid]", height)

        ref_align = QComboBox(); ref_align.addItems(["left", "right"]); ref_align.setCurrentText(model.refdes_align)
        ref_align.currentTextChanged.connect(lambda v: self._set_attr(model, "refdes_align", v, item))
        self.layout.addRow("RefDes Align", ref_align)

        body_align = QComboBox(); body_align.addItems(["left", "right"]); body_align.setCurrentText(model.body_attr_align)
        body_align.currentTextChanged.connect(lambda v: self._set_attr(model, "body_attr_align", v, item))
        self.layout.addRow("Body Attr Align", body_align)

        for attr_name in list(model.attributes.keys()):
            line = QLineEdit(model.attributes.get(attr_name, ""))
            line.textChanged.connect(lambda v, a=attr_name: self._set_body_attribute(item, a, v))
            visible = QCheckBox("visible")
            visible.setChecked(attr_name in model.visible_attributes)
            visible.toggled.connect(lambda checked, a=attr_name: self._set_body_visibility(item, a, checked))
            row = QWidget(); row_layout = QFormLayout(row); row_layout.setContentsMargins(0, 0, 0, 0); row_layout.addRow(line, visible)
            self.layout.addRow(attr_name, row)

        self._color_button(model, item)

    def _text(self, item: TextGraphicsItem):
        model = item.model
        text = QLineEdit(model.text)
        text.textChanged.connect(lambda v: self.editor.set_text_value(item, v))
        self.layout.addRow("Text", text)

        font = QLineEdit(model.font_family)
        font.textChanged.connect(lambda v: self.editor.set_text_font(item, family=v))
        self.layout.addRow("Font", font)

        size = QDoubleSpinBox(); size.setRange(0.1, 5.0); size.setSingleStep(0.1); size.setValue(model.font_size_grid)
        size.valueChanged.connect(lambda v: self.editor.set_text_font(item, size=v))
        self.layout.addRow("Size [grid]", size)
        self._color_button(model, item)

    def _graphic(self, item: GraphicObjectItem):
        model = item.model
        kind = QComboBox(); kind.addItems([g.value for g in GraphicType]); kind.setCurrentText(model.graphic_type)
        kind.currentTextChanged.connect(lambda v: self._set_attr(model, "graphic_type", v, item))
        self.layout.addRow("Graphic Type", kind)
        for label, attr in [("Width", "width"), ("Height", "height"), ("X2", "x2"), ("Y2", "y2")]:
            spin = QDoubleSpinBox(); spin.setRange(-200, 200); spin.setValue(getattr(model, attr)); spin.setSingleStep(0.5)
            spin.valueChanged.connect(lambda v, a=attr: self._set_attr(model, a, v, item))
            self.layout.addRow(f"{label} [grid]", spin)
        self._color_button(model, item)

    def _set_body_attribute(self, item: SymbolBodyItem, key: str, value: str):
        item.model.attributes[key] = value
        item.update()
        self.editor.refresh_side_panels()

    def _set_body_visibility(self, item: SymbolBodyItem, key: str, checked: bool):
        attrs = item.model.visible_attributes
        if checked and key not in attrs:
            attrs.append(key)
        elif not checked and key in attrs:
            attrs.remove(key)
        item.update()
        self.editor.refresh_side_panels()

    def _color_button(self, model, item):
        btn = QPushButton("Choose RGB Color")
        btn.clicked.connect(lambda: self.choose_color(model, item))
        self.layout.addRow("Color", btn)

    def choose_color(self, model, item):
        color = QColorDialog.getColor(rgb_to_qcolor(model.color), self)
        if not color.isValid():
            return
        model.color = qcolor_to_rgb(color)
        if isinstance(item, SymbolBodyItem):
            item.setPen(QPen(color, 2))
        elif isinstance(item, TextGraphicsItem):
            item.setDefaultTextColor(color)
        item.update()
        self.editor.refresh_side_panels()
