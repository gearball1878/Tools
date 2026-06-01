# ---------------------------------------------------------------------------
# Older incremental patches assigned MainWindow.refresh_properties wrappers to
# TemplateEditorDialog.  Those wrappers expect MainWindow-only members such as
# self.library and crash while opening the template editor.  The template editor
# gets an explicit, self-contained property refresher again.

def _sw94_te_clear_properties(self):
    try:
        if not hasattr(self, 'form') or self.form is None:
            return False
        while self.form.rowCount():
            self.form.removeRow(0)
        return True
    except Exception:
        return False


def _sw94_te_refresh_properties(self):
    if not _sw94_te_clear_properties(self):
        return
    try:
        sel = list(self.scene.selectedItems()) if hasattr(self, 'scene') and self.scene is not None else []
    except Exception:
        sel = []
    try:
        if len(sel) > 1:
            self.form.addRow(QLabel(f'{len(sel)} objects selected'))
            pins = [i for i in sel if i.data(0) == 'PIN']
            texts = [i for i in sel if i.data(0) in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY')]
            graphics = [i for i in sel if i.data(0) == 'GRAPHIC']
            if len(pins) == len(sel) and hasattr(self, '_set_selected_pins_attr'):
                self.form.addRow(QLabel(f'<b>Multi-Edit: {len(pins)} PINs</b>'))
                fn = QLineEdit('')
                fn.setPlaceholderText('Set Pin Function for all selected pins')
                fn.returnPressed.connect(lambda editor=fn, items=pins: self._set_selected_pins_attr(items, 'function', editor.text()))
                self.form.addRow('Pin Function', fn)
            elif len(texts) == len(sel) and hasattr(self, '_template_multi_text_props'):
                self.form.addRow(QLabel(f'<b>Multi-Edit: {len(texts)} text objects</b>'))
                self._template_multi_text_props(texts)
            elif len(graphics) == len(sel):
                self.form.addRow(QLabel(f'<b>Multi-Edit: {len(graphics)} graphic objects</b>'))
                if hasattr(self, '_common_graphic_value') and hasattr(self, '_set_selected_graphics_style'):
                    self.form.addRow('Line width', self._dbl(float(self._common_graphic_value(graphics, 'line_width', 0.03) or 0.03), lambda v, items=graphics: self._set_selected_graphics_style(items, 'line_width', float(v)), .01, 1, .01))
            else:
                self.form.addRow(QLabel('Multi-edit is only available for same-type selections.'))
            return
        if not sel:
            self.form.addRow(QLabel('No selection. Template canvas is independent from the Symbol Wizard.'))
            try:
                body = getattr(getattr(self, 'unit', None), 'body', None)
                attrs = getattr(body, 'attributes', {}) or {}
                if attrs:
                    self.form.addRow(QLabel('<b>Template Attribute Visibility</b>'))
                    for k in list(attrs.keys()):
                        row = QWidget(); l = QHBoxLayout(row); l.setContentsMargins(0,0,0,0)
                        cb = QCheckBox('visible')
                        cb.setChecked((getattr(body, 'visible_attributes', {}) or {}).get(k, False))
                        preview = QLabel((f"{k}: {attrs.get(k, '')}" if str(attrs.get(k, '')).strip() else str(k)))
                        if hasattr(self, '_set_attr_vis'):
                            cb.toggled.connect(lambda v, key=k: self._set_attr_vis(key, v))
                        l.addWidget(cb); l.addWidget(preview); self.form.addRow(k, row)
            except Exception:
                pass
            return
        item = sel[0]
        kind = item.data(0)
        m = getattr(item, 'model', None)
        self.form.addRow(QLabel(f'<b>{kind}</b>'))
        if m is None:
            return
        if kind == 'BODY':
            self.form.addRow('Width [grid]', self._dbl(getattr(m, 'width', 1.0), lambda v, model=m: self._set_body_width_grid(model, v) if hasattr(self, '_set_body_width_grid') else self._set(model, 'width', float(v)), 0.01, 500, getattr(self, 'edit_grid_step', 1)))
            self.form.addRow('Height [grid]', self._dbl(getattr(m, 'height', 1.0), lambda v, model=m: self._set_body_height_grid(model, v) if hasattr(self, '_set_body_height_grid') else self._set(model, 'height', float(v)), 0.01, 500, getattr(self, 'edit_grid_step', 1)))
            try:
                self.form.addRow('Line style', self._combo([x.value for x in LineStyle], getattr(m, 'line_style', LineStyle.SOLID.value), lambda v, model=m: self._set(model, 'line_style', v)))
            except Exception:
                pass
            self.form.addRow('Line width', self._dbl(getattr(m, 'line_width', 0.03), lambda v, model=m: self._set(model, 'line_width', float(v)), .01, 1, .01))
            self.form.addRow('Rotation [deg]', self._dbl(getattr(m, 'rotation', 0), lambda v, model=m: self._set_body_rotation_90(model, v) if hasattr(self, '_set_body_rotation_90') else self._set(model, 'rotation', float(v)), 0, 270, 90))
            try:
                self.form.addRow('Color', self._color_button_row('Color RGB', getattr(m, 'color', (0,0,0)), lambda _checked=False, model=m: self.color_model(model)))
            except Exception:
                pass
            try:
                attrs = getattr(m, 'attributes', {}) or {}
                if attrs:
                    self.form.addRow(QLabel('<b>Displayed Attributes</b>'))
                    for k in list(attrs.keys()):
                        row = QWidget(); l = QHBoxLayout(row); l.setContentsMargins(0,0,0,0)
                        cb = QCheckBox('visible'); cb.setChecked((getattr(m, 'visible_attributes', {}) or {}).get(k, False))
                        ed = QLineEdit(str(attrs.get(k, '')))
                        if hasattr(self, '_set_attr_vis'):
                            cb.toggled.connect(lambda v, key=k: self._set_attr_vis(key, v))
                        if hasattr(self, '_set_attr_val'):
                            ed.editingFinished.connect(lambda key=k, e=ed: self._set_attr_val(key, e.text()))
                        l.addWidget(cb); l.addWidget(ed); self.form.addRow(k, row)
            except Exception:
                pass
        elif kind == 'PIN':
            for lab, attr in [('Number','number'), ('Name','name'), ('Function','function')]:
                self.form.addRow(lab, self._line(getattr(m, attr, ''), lambda v, a=attr, model=m: self._set(model, a, v)))
            try: self.form.addRow('Pin Type', self._combo([x.value for x in PinType], getattr(m, 'pin_type', ''), lambda v, model=m: self._set(model, 'pin_type', v)))
            except Exception: pass
            try: self.form.addRow('Side', self._combo([x.value for x in PinSide], getattr(m, 'side', ''), lambda v, model=m: self._set_pin_side(model, v) if hasattr(self, '_set_pin_side') else self._set(model, 'side', v)))
            except Exception: pass
            inv = QCheckBox(); inv.setChecked(bool(getattr(m, 'inverted', False))); inv.toggled.connect(lambda v, model=m: self._set(model, 'inverted', v)); self.form.addRow('Inverted', inv)
            self.form.addRow('Length', self._dbl(getattr(m, 'length', 1.0), lambda v, model=m: self._set(model, 'length', float(v)), 0.5, 100))
        elif kind in ('TEXT', 'ATTR_REF_DES', 'ATTR_BODY'):
            is_attr = kind in ('ATTR_REF_DES', 'ATTR_BODY') or bool(getattr(m, '_is_attribute_text', False))
            line = self._line(getattr(m, 'text', ''), lambda v, item=item: self._set_text_item_attr(item, 'text', v)) if is_attr else self._plain_text_editor(getattr(m, 'text', ''), lambda v, item=item: self._set_text_item_attr(item, 'text', v))
            if is_attr and hasattr(line, 'setReadOnly'):
                line.setReadOnly(True)
            self.form.addRow('Text', line)
            self.form.addRow('Size grid', self._dbl(getattr(m, 'font_size_grid', 0.5), lambda v, item=item: self._set_text_item_attr(item, 'font_size_grid', float(v)), .1, 10))
            self.form.addRow('Rotation [deg]', self._dbl(getattr(m, 'rotation', 0), lambda v, item=item: self._set_text_item_attr(item, 'rotation', float(v)), -360, 360, 15))
        elif kind == 'GRAPHIC':
            self.form.addRow('Shape', self._combo(['line','rect','ellipse'], getattr(m, 'shape', 'rect'), lambda v, model=m: self._set_graphic_shape_and_refresh(model, v) if hasattr(self, '_set_graphic_shape_and_refresh') else self._set(model, 'shape', v)))
            self.form.addRow('X', self._dbl(getattr(m, 'x', 0), lambda v, model=m: self._set(model, 'x', round(float(v))), -500, 500, 1))
            self.form.addRow('Y', self._dbl(getattr(m, 'y', 0), lambda v, model=m: self._set(model, 'y', round(float(v))), -500, 500, 1))
            self.form.addRow('Width', self._dbl(getattr(m, 'w', 1), lambda v, model=m: self._set(model, 'w', round(float(v))), -500, 500, 1))
            self.form.addRow('Height', self._dbl(getattr(m, 'h', 1), lambda v, model=m: self._set(model, 'h', round(float(v))), -500, 500, 1))
            if getattr(m, 'shape', '') == 'line':
                self.form.addRow('Curve radius', self._dbl(getattr(m, 'curve_radius', 0), lambda v, model=m: self._set(model, 'curve_radius', float(v)), -100, 100, .1))
            self.form.addRow('Rotation [deg]', self._dbl(getattr(m, 'rotation', 0), lambda v, model=m: self._set(model, 'rotation', float(v)), -360, 360, 15))
    except Exception as exc:
        try:
            self.form.addRow(QLabel(f'Property panel error: {exc}'))
        except Exception:
            pass

try:
    if 'TemplateEditorDialog' in globals():
        TemplateEditorDialog.clear_properties = _sw94_te_clear_properties
        TemplateEditorDialog.refresh_properties = _sw94_te_refresh_properties
except Exception:
    pass
