from __future__ import annotations
from copy import deepcopy
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QBrush
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QGraphicsScene, QGraphicsView, QGraphicsRectItem, QGraphicsItem,
    QGraphicsLineItem, QGraphicsEllipseItem, QDoubleSpinBox, QFormLayout,
    QWidget, QSplitter, QMessageBox
)
from symbol_wizard.rules.grid import PX_PER_INCH, snap
from symbol_wizard.templates.symbol_types import load_config, save_config, deep_merge, type_names, subtype_names

class GridScene(QGraphicsScene):
    def __init__(self, grid_inch=0.1):
        super().__init__(-3000, -3000, 6000, 6000)
        self.grid_px = grid_inch * PX_PER_INCH
    def drawBackground(self, painter, rect):
        g = self.grid_px
        painter.save()
        painter.setPen(QPen(QColor(225,225,225), 0))
        x = int(rect.left()//g)*g
        while x < rect.right():
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom())); x += g
        y = int(rect.top()//g)*g
        while y < rect.bottom():
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y)); y += g
        painter.setPen(QPen(QColor(150,150,150), 0))
        painter.drawLine(QPointF(rect.left(), 0), QPointF(rect.right(), 0))
        painter.drawLine(QPointF(0, rect.top()), QPointF(0, rect.bottom()))
        painter.restore()

class TemplateItemMixin:
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            g = self.scene().grid_px
            return QPointF(snap(value.x(), g), snap(value.y(), g))
        return super().itemChange(change, value)
    def flags_common(self):
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)

class TemplateBodyItem(TemplateItemMixin, QGraphicsRectItem):
    def __init__(self, template, scene):
        self.template = template
        body = template.setdefault('body', {})
        w, h = float(body.get('width', 16)), float(body.get('height', 24))
        g = scene.grid_px
        super().__init__(0, 0, w*g, h*g)
        self.setPos(float(body.get('x', -w/2))*g, -float(body.get('y', h/2))*g)
        self.setPen(QPen(QColor(0,0,0), 2)); self.setBrush(QBrush(Qt.NoBrush)); self.flags_common()
        self.setData(0, 'body')
    def sync(self):
        g = self.scene().grid_px; r = self.rect()
        self.template.setdefault('body', {})['x'] = self.pos().x()/g
        self.template.setdefault('body', {})['y'] = -self.pos().y()/g
        self.template.setdefault('body', {})['width'] = max(1, round(r.width()/g*2)/2)
        self.template.setdefault('body', {})['height'] = max(1, round(r.height()/g*2)/2)

class TemplateGraphicItem(TemplateItemMixin, QGraphicsItem):
    def __init__(self, graphic, scene):
        super().__init__(); self.graphic = graphic; g = scene.grid_px
        self.setPos(float(graphic.get('x',0))*g, -float(graphic.get('y',0))*g)
        self.flags_common(); self.setData(0, 'graphic')
    def boundingRect(self):
        g=self.scene().grid_px; w=float(self.graphic.get('w',2))*g; h=float(self.graphic.get('h',0))*g
        return QRectF(0,0,w,h).normalized().adjusted(-.25*g,-.25*g,.25*g,.25*g)
    def paint(self, painter, option, widget=None):
        g=self.scene().grid_px; w=float(self.graphic.get('w',2))*g; h=float(self.graphic.get('h',0))*g; shape=self.graphic.get('shape','line')
        painter.setPen(QPen(QColor(0,0,0), 2)); painter.setBrush(QBrush(Qt.NoBrush))
        if shape=='rect': painter.drawRect(QRectF(0,0,w,h))
        elif shape=='ellipse': painter.drawEllipse(QRectF(0,0,w,h))
        else: painter.drawLine(QPointF(0,0), QPointF(w,h))
        if self.isSelected(): painter.drawRect(self.boundingRect())
    def sync(self):
        g=self.scene().grid_px; self.graphic['x']=self.pos().x()/g; self.graphic['y']=-self.pos().y()/g

class TemplateEditorDialog(QDialog):
    """Dedicated canvas for editing Type/Subtype templates.

    Saving uses merge semantics: only edited template keys are written, existing
    configuration keys remain intact.
    """
    def __init__(self, parent, symbol_type: str, subtype: str, apply_callback=None):
        super().__init__(parent)
        self.setWindowTitle('Template Editor')
        self.resize(1100, 760)
        self.apply_callback = apply_callback
        self.cfg = load_config(); self.template = {}
        self.scene = GridScene(getattr(parent.symbol, 'grid_inch', .1) if parent else .1)
        self.view = QGraphicsView(self.scene); self.view.setRenderHint(QPainter.Antialiasing)
        self.type_combo = QComboBox(); self.type_combo.addItems(type_names()); self.type_combo.setCurrentText(symbol_type)
        self.subtype_combo = QComboBox()
        self.type_combo.currentTextChanged.connect(self.reload_subtypes)
        self.subtype_combo.currentTextChanged.connect(self.load_template)
        self.body_w = QDoubleSpinBox(); self.body_w.setRange(1,300); self.body_w.setDecimals(3); self.body_w.setSingleStep(.5)
        self.body_h = QDoubleSpinBox(); self.body_h.setRange(1,300); self.body_h.setDecimals(3); self.body_h.setSingleStep(.5)
        self.body_w.valueChanged.connect(self.update_body_size); self.body_h.valueChanged.connect(self.update_body_size)
        side = QWidget(); fl=QFormLayout(side); fl.addRow('Type', self.type_combo); fl.addRow('Subtype', self.subtype_combo); fl.addRow('Body width [grid]', self.body_w); fl.addRow('Body height [grid]', self.body_h)
        for label, shape in [('Add Line','line'),('Add Rect','rect'),('Add Ellipse','ellipse')]:
            b=QPushButton(label); b.clicked.connect(lambda _, s=shape: self.add_graphic(s)); fl.addRow('', b)
        d=QPushButton('Delete Selected'); d.clicked.connect(self.delete_selected); fl.addRow('', d)
        save=QPushButton('Save Template (merge)'); save.clicked.connect(self.save_template); fl.addRow('', save)
        layout=QVBoxLayout(self); splitter=QSplitter(); splitter.addWidget(self.view); splitter.addWidget(side); splitter.setSizes([800,260]); layout.addWidget(splitter)
        self.reload_subtypes(symbol_type); self.subtype_combo.setCurrentText(subtype); self.load_template(subtype)
    def reload_subtypes(self, t):
        self.subtype_combo.blockSignals(True); self.subtype_combo.clear(); self.subtype_combo.addItems(subtype_names(t)); self.subtype_combo.blockSignals(False); self.load_template(self.subtype_combo.currentText())
    def _template_ref(self):
        t=self.type_combo.currentText(); st=self.subtype_combo.currentText(); return self.cfg.setdefault('types',{}).setdefault(t,{}).setdefault('subtypes',{}).setdefault(st,{})
    def load_template(self, *_):
        self.scene.clear(); ref=self._template_ref(); self.template=deepcopy(ref.get('template', {})) or {'body':{'width':16,'height':24}, 'graphics':[], 'default_pins':[]}
        self.body_item=TemplateBodyItem(self.template, self.scene); self.scene.addItem(self.body_item)
        for gr in self.template.setdefault('graphics', []): self.scene.addItem(TemplateGraphicItem(gr,self.scene))
        b=self.template.setdefault('body',{}); self.body_w.blockSignals(True); self.body_h.blockSignals(True); self.body_w.setValue(float(b.get('width',16))); self.body_h.setValue(float(b.get('height',24))); self.body_w.blockSignals(False); self.body_h.blockSignals(False)
        self.view.fitInView(self.scene.itemsBoundingRect().adjusted(-200,-200,200,200), Qt.KeepAspectRatio)
    def update_body_size(self):
        if not hasattr(self,'body_item'): return
        g=self.scene.grid_px; self.body_item.setRect(0,0,self.body_w.value()*g,self.body_h.value()*g); self.template.setdefault('body',{})['width']=self.body_w.value(); self.template.setdefault('body',{})['height']=self.body_h.value()
    def add_graphic(self, shape):
        gr={'shape':shape,'x':0,'y':0,'w':4 if shape!='line' else 3,'h':2 if shape!='line' else 0}; self.template.setdefault('graphics',[]).append(gr); self.scene.addItem(TemplateGraphicItem(gr,self.scene))
    def delete_selected(self):
        for it in list(self.scene.selectedItems()):
            if it.data(0)=='graphic':
                try: self.template.setdefault('graphics',[]).remove(it.graphic)
                except ValueError: pass
                self.scene.removeItem(it)
    def save_template(self):
        for it in self.scene.items():
            if hasattr(it,'sync'): it.sync()
        ref=self._template_ref(); ref['template']=deep_merge(ref.get('template',{}), self.template)
        save_config(self.cfg)
        if self.apply_callback: self.apply_callback(self.type_combo.currentText(), self.subtype_combo.currentText(), ref['template'])
        QMessageBox.information(self, 'Template Editor', 'Template wurde per Merge gespeichert und angewandt.')
