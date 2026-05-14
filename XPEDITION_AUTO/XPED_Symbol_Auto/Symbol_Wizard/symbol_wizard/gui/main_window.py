from __future__ import annotations
import copy
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QKeySequence
from PySide6.QtWidgets import *
from symbol_wizard.models.document import *
from symbol_wizard.rules.grid import PX_PER_INCH, duplicate_pin_numbers
from symbol_wizard.rules.placement import create_auto_pin
from symbol_wizard.graphics.scene import SymbolScene
from symbol_wizard.graphics.view import SymbolView
from symbol_wizard.graphics.items import BodyItem, PinItem, TextItem, GraphicItem, rgb, pen_for
from symbol_wizard.io.json_store import save_library, load_library, save_symbol, load_symbol

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.library=LibraryModel(); self.current_unit_index=0; self.draw_tool=DrawTool.SELECT.value; self.clipboard=None; self.suspend=False
        self.scene=SymbolScene(self); self.view=SymbolView(self.scene,self); self.setWindowTitle('Symbol Wizard'); self.resize(1500,950)
        self._build_ui(); self.rebuild_all()
    @property
    def symbol(self): return self.library.current_symbol()
    @property
    def current_unit(self): return self.symbol.units[self.current_unit_index]
    @property
    def grid_px(self): return self.symbol.grid_inch*PX_PER_INCH
    def scene_to_grid_x(self,x): return round(x/self.grid_px)
    def scene_to_grid_y(self,y): return round(-y/self.grid_px)

    def _build_ui(self):
        self._menu(); self._ribbon()
        self.symbol_tabs=QTabWidget(); self.symbol_tabs.currentChanged.connect(self.change_symbol)
        self.unit_tabs=QTabWidget(); self.unit_tabs.currentChanged.connect(self.change_unit)
        self.object_tree=QTreeWidget(); self.object_tree.setHeaderLabels(['Object','Info']); self.object_tree.itemClicked.connect(self.tree_clicked)
        self.pin_table=QTableWidget(0,5); self.pin_table.setHorizontalHeaderLabels(['Unit','Number','Name','Function','Type']); self.pin_table.cellChanged.connect(self.pin_table_changed)
        left_tabs=QTabWidget(); symtab=QWidget(); lay=QVBoxLayout(symtab); lay.addWidget(QLabel('Symbols')); lay.addWidget(self.symbol_tabs); lay.addWidget(QLabel('Units / Split Symbols')); lay.addWidget(self.unit_tabs); lay.addWidget(QLabel('Symbol object tree')); lay.addWidget(self.object_tree); left_tabs.addTab(symtab,'Symbols')
        left_tabs.addTab(self.pin_table,'Pins')
        split_info=QTextEdit(); split_info.setReadOnly(True); split_info.setPlainText('Split Symbol Ansicht: Jeder Symbol-Reiter kann mehrere Units enthalten. Pins müssen innerhalb des gesamten Symbols eindeutig sein.'); left_tabs.addTab(split_info,'Split Symbols')
        self.props=QWidget(); self.form=QFormLayout(self.props)
        splitter=QSplitter(); splitter.addWidget(left_tabs); splitter.addWidget(self.view); splitter.addWidget(self.props); splitter.setSizes([330,850,360]); self.setCentralWidget(splitter)
        self.scene.selectionChanged.connect(self.refresh_properties)
    def _menu(self):
        mb=self.menuBar(); file=mb.addMenu('&File')
        acts=[('New Symbol',self.new_symbol,'Ctrl+N'),('Open Library JSON',self.open_library,'Ctrl+O'),('Save Current Symbol JSON',self.save_current_symbol,'Ctrl+S'),('Save All Symbols JSON',self.save_all_symbols,'Ctrl+Shift+S'),('Import Symbol JSON',self.import_symbol,None),('Exit',self.close,None)]
        for name,fn,sc in acts:
            a=QAction(name,self); a.triggered.connect(fn); 
            if sc: a.setShortcut(QKeySequence(sc))
            file.addAction(a)
        edit=mb.addMenu('&Edit')
        for name,fn,sc in [('Copy',self.copy_selected,'Ctrl+C'),('Paste',self.paste_selected,'Ctrl+V'),('Delete',self.delete_selected,'Del'),('Validate Pins',self.validate_pins,None)]:
            a=QAction(name,self); a.triggered.connect(fn); 
            if sc: a.setShortcut(QKeySequence(sc))
            edit.addAction(a)
        view=mb.addMenu('&View'); a=QAction('Refresh',self); a.triggered.connect(self.rebuild_all); view.addAction(a)
    def _ribbon(self):
        tb=QToolBar('Draw Ribbon'); self.addToolBar(tb)
        self.tool_buttons={}
        for tool,label in [(DrawTool.SELECT,'Select/Edit'),(DrawTool.PIN_LEFT,'Pin L'),(DrawTool.PIN_RIGHT,'Pin R'),(DrawTool.TEXT,'Text'),(DrawTool.LINE,'Line'),(DrawTool.RECT,'Rect'),(DrawTool.ELLIPSE,'Ellipse')]:
            a=QAction(label,self); a.setCheckable(True); a.triggered.connect(lambda checked,t=tool.value:self.set_tool(t)); tb.addAction(a); self.tool_buttons[tool.value]=a
        self.tool_buttons[self.draw_tool].setChecked(True); tb.addSeparator()
        tb.addWidget(QLabel('Grid inch:')); self.grid_spin=QDoubleSpinBox(); self.grid_spin.setRange(.05,.5); self.grid_spin.setSingleStep(.05); self.grid_spin.setDecimals(3); self.grid_spin.valueChanged.connect(self.set_grid); tb.addWidget(self.grid_spin)
        tb.addWidget(QLabel(' Line:')); self.line_style=QComboBox(); self.line_style.addItems([x.value for x in LineStyle]); tb.addWidget(self.line_style)
        tb.addWidget(QLabel(' Width grid:')); self.line_width=QDoubleSpinBox(); self.line_width.setRange(.01,1); self.line_width.setSingleStep(.01); self.line_width.setValue(.03); tb.addWidget(self.line_width)
        self.line_style.currentTextChanged.connect(self.apply_line_defaults); self.line_width.valueChanged.connect(self.apply_line_defaults)
        color=QPushButton('RGB'); color.clicked.connect(self.pick_default_color); tb.addWidget(color); self.default_color=(0,0,0)
    def set_tool(self,t):
        self.draw_tool=t
        for k,a in self.tool_buttons.items(): a.setChecked(k==t)
        self.view.setDragMode(QGraphicsView.RubberBandDrag if t==DrawTool.SELECT.value else QGraphicsView.NoDrag)
    def pick_default_color(self):
        c=QColorDialog.getColor(QColor(*self.default_color),self)
        if c.isValid(): self.default_color=(c.red(),c.green(),c.blue()); self.apply_line_defaults()

    def rebuild_all(self): self.rebuild_symbol_tabs(); self.rebuild_unit_tabs(); self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table(); self.grid_spin.setValue(self.symbol.grid_inch)
    def rebuild_symbol_tabs(self):
        self.symbol_tabs.blockSignals(True); self.symbol_tabs.clear()
        for s in self.library.symbols: self.symbol_tabs.addTab(QWidget(),s.name)
        self.symbol_tabs.setCurrentIndex(self.library.current_symbol_index); self.symbol_tabs.blockSignals(False)
    def rebuild_unit_tabs(self):
        self.unit_tabs.blockSignals(True); self.unit_tabs.clear()
        for u in self.symbol.units: self.unit_tabs.addTab(QWidget(),u.name)
        self.current_unit_index=min(self.current_unit_index,len(self.symbol.units)-1); self.unit_tabs.setCurrentIndex(self.current_unit_index); self.unit_tabs.blockSignals(False)
    def rebuild_scene(self):
        self.scene.clear(); u=self.current_unit; self.scene.addItem(BodyItem(u.body,self))
        # visible body attributes rendered as editable text decorations
        self.add_attribute_text_items(u)
        for g in u.graphics: self.scene.addItem(GraphicItem(g,self))
        for p in u.pins: self.scene.addItem(PinItem(p,self))
        for t in u.texts: self.scene.addItem(TextItem(t,self))
        self.scene.update()
    def add_attribute_text_items(self,u):
        b=u.body; g=self.grid_px; x=b.x*g; y=-b.y*g; w=b.width*g; h=b.height*g
        ref=b.attributes.get('RefDes','')
        if b.visible_attributes.get('RefDes',False) and ref:
            txt=TextItem(TextModel(ref,b.x,b.y+1, font_size_grid=min(.9,1.0), color=b.color),self); txt.setFlag(QGraphicsItem.ItemIsMovable,False); txt.setData(0,'ATTR_REF_DES'); self.scene.addItem(txt)
        row=1
        for k,v in b.attributes.items():
            if k=='RefDes' or not b.visible_attributes.get(k,False) or not v: continue
            txt=TextItem(TextModel(f'{k}: {v}', b.x, b.y-b.height-row, font_size_grid=.75, color=b.color),self); txt.setFlag(QGraphicsItem.ItemIsMovable,False); txt.setData(0,'ATTR_BODY'); self.scene.addItem(txt); row+=1
    def rebuild_tree(self):
        self.object_tree.clear(); root=QTreeWidgetItem([self.symbol.name,'Symbol']); self.object_tree.addTopLevelItem(root)
        for ui,u in enumerate(self.symbol.units):
            unit=QTreeWidgetItem([u.name,'Unit']); unit.setData(0,Qt.UserRole,('unit',ui,None)); root.addChild(unit)
            body=QTreeWidgetItem(['Body',f'{u.body.width} x {u.body.height}']); body.setData(0,Qt.UserRole,('body',ui,None)); unit.addChild(body)
            attrs=QTreeWidgetItem(['Attributes','Body']); unit.addChild(attrs)
            for k,v in u.body.attributes.items(): attrs.addChild(QTreeWidgetItem([k,('visible: ' if u.body.visible_attributes.get(k,False) else 'hidden: ')+v]))
            pins=QTreeWidgetItem(['Pins',str(len(u.pins))]); unit.addChild(pins)
            for i,p in enumerate(u.pins):
                it=QTreeWidgetItem([p.number,f'{p.name} / {p.function}']); it.setData(0,Qt.UserRole,('pin',ui,i)); pins.addChild(it)
            texts=QTreeWidgetItem(['Text',str(len(u.texts))]); unit.addChild(texts)
            for i,t in enumerate(u.texts): it=QTreeWidgetItem([t.text,'Text']); it.setData(0,Qt.UserRole,('text',ui,i)); texts.addChild(it)
            gr=QTreeWidgetItem(['Graphics',str(len(u.graphics))]); unit.addChild(gr)
            for i,gg in enumerate(u.graphics): it=QTreeWidgetItem([gg.shape,f'{gg.w}x{gg.h}']); it.setData(0,Qt.UserRole,('graphic',ui,i)); gr.addChild(it)
        self.object_tree.expandAll()
    def rebuild_pin_table(self):
        self.suspend=True; self.pin_table.setRowCount(0)
        for ui,u in enumerate(self.symbol.units):
            for pi,p in enumerate(u.pins):
                r=self.pin_table.rowCount(); self.pin_table.insertRow(r)
                for c,val in enumerate([u.name,p.number,p.name,p.function,p.pin_type]):
                    it=QTableWidgetItem(val); it.setData(Qt.UserRole,(ui,pi,c)); self.pin_table.setItem(r,c,it)
        self.suspend=False
    def refresh_properties(self):
        while self.form.rowCount(): self.form.removeRow(0)
        sel=[i for i in self.scene.selectedItems() if i.data(0) not in ('ATTR_BODY','ATTR_REF_DES')]
        if not sel: self.form.addRow(QLabel('No selection')); return
        item=sel[0]; kind=item.data(0); self.form.addRow(QLabel(f'Selected: {kind}'))
        if kind=='BODY': self.body_props(item)
        elif kind=='PIN': self.pin_props(item)
        elif kind=='TEXT': self.text_props(item)
        elif kind=='GRAPHIC': self.graphic_props(item)
    def _line(self,val,fn): w=QLineEdit(str(val)); w.textChanged.connect(fn); return w
    def _dbl(self,val,fn,mi=-999,ma=999,step=.1): w=QDoubleSpinBox(); w.setRange(mi,ma); w.setSingleStep(step); w.setValue(float(val)); w.valueChanged.connect(fn); return w
    def _combo(self,items,val,fn): w=QComboBox(); w.addItems(items); w.setCurrentText(val); w.currentTextChanged.connect(fn); return w
    def body_props(self,item):
        m=item.model; self.form.addRow('Width [grid]',self._dbl(m.width,lambda v:self.set_body_dim(item,'width',v),1,300)); self.form.addRow('Height [grid]',self._dbl(m.height,lambda v:self.set_body_dim(item,'height',v),1,300))
        self.form.addRow('Line style',self._combo([x.value for x in LineStyle],m.line_style,lambda v:self.set_and_refresh(m,'line_style',v))); self.form.addRow('Line width',self._dbl(m.line_width,lambda v:self.set_and_refresh(m,'line_width',v),.01,1,.01))
        for k in list(m.attributes.keys()):
            row=QWidget(); l=QHBoxLayout(row); l.setContentsMargins(0,0,0,0); cb=QCheckBox('visible'); cb.setChecked(m.visible_attributes.get(k,False)); ed=QLineEdit(m.attributes.get(k,'')); cb.toggled.connect(lambda v,key=k:self.set_attr_vis(m,key,v)); ed.textChanged.connect(lambda v,key=k:self.set_attr_val(m,key,v)); l.addWidget(cb); l.addWidget(ed); self.form.addRow(k,row)
        b=QPushButton('Color RGB'); b.clicked.connect(lambda:self.color_model(m)); self.form.addRow('Color',b)
    def pin_props(self,item):
        m=item.model
        for label,attr in [('Pin Number','number'),('Pin Name','name'),('Pin Function','function')]: self.form.addRow(label,self._line(getattr(m,attr),lambda v,a=attr:self.set_pin_attr(m,a,v)))
        self.form.addRow('Pin Type',self._combo([x.value for x in PinType],m.pin_type,lambda v:self.set_pin_attr(m,'pin_type',v)))
        self.form.addRow('Side',self._combo([x.value for x in PinSide],m.side,lambda v:self.set_pin_attr(m,'side',v)))
        inv=QCheckBox(); inv.setChecked(m.inverted); inv.toggled.connect(lambda v:self.set_pin_attr(m,'inverted',v)); self.form.addRow('Inverted',inv)
        for label,attr in [('Show Number','visible_number'),('Show Name','visible_name'),('Show Function','visible_function')]: cb=QCheckBox(); cb.setChecked(getattr(m,attr)); cb.toggled.connect(lambda v,a=attr:self.set_pin_attr(m,a,v)); self.form.addRow(label,cb)
        self.form.addRow('Line style',self._combo([x.value for x in LineStyle],m.line_style,lambda v:self.set_pin_attr(m,'line_style',v))); self.form.addRow('Line width',self._dbl(m.line_width,lambda v:self.set_pin_attr(m,'line_width',v),.01,1,.01))
        b=QPushButton('Color RGB'); b.clicked.connect(lambda:self.color_model(m)); self.form.addRow('Color',b)
    def text_props(self,item):
        m=item.model; self.form.addRow('Text',self._line(m.text,lambda v:self.set_text_attr(item,'text',v))); self.form.addRow('Font',self._line(m.font_family,lambda v:self.set_text_attr(item,'font_family',v))); self.form.addRow('Size grid',self._dbl(m.font_size_grid,lambda v:self.set_text_attr(item,'font_size_grid',v),.1,5,.1)); b=QPushButton('Color RGB'); b.clicked.connect(lambda:self.color_model(m)); self.form.addRow('Color',b)
    def graphic_props(self,item):
        m=item.model; self.form.addRow('Shape',self._combo(['line','rect','ellipse'],m.shape,lambda v:self.set_and_refresh(m,'shape',v))); self.form.addRow('Width [grid]',self._dbl(m.w,lambda v:self.set_and_refresh(m,'w',v),-100,300)); self.form.addRow('Height [grid]',self._dbl(m.h,lambda v:self.set_and_refresh(m,'h',v),-100,300)); self.form.addRow('Line style',self._combo([x.value for x in LineStyle],m.style.line_style,lambda v:self.set_style(m,'line_style',v))); self.form.addRow('Line width',self._dbl(m.style.line_width,lambda v:self.set_style(m,'line_width',v),.01,1,.01)); b=QPushButton('Stroke RGB'); b.clicked.connect(lambda:self.color_model(m.style,'stroke')); self.form.addRow('Color',b)
    def set_and_refresh(self,m,a,v): setattr(m,a,v); self.rebuild_scene(); self.rebuild_tree()
    def set_style(self,m,a,v): setattr(m.style,a,v); self.rebuild_scene(); self.rebuild_tree()
    def set_body_dim(self,item,a,v): setattr(item.model,a,v); self.rebuild_scene(); self.rebuild_tree()
    def set_attr_vis(self,m,k,v): m.visible_attributes[k]=v; self.rebuild_scene(); self.rebuild_tree()
    def set_attr_val(self,m,k,v): m.attributes[k]=v; self.rebuild_scene(); self.rebuild_tree()
    def set_pin_attr(self,m,a,v):
        setattr(m,a,v); d=duplicate_pin_numbers(self.symbol)
        if d: self.statusBar().showMessage('Duplicate pin number(s): '+', '.join(d),8000)
        self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()
    def set_text_attr(self,item,a,v): setattr(item.model,a,v); self.rebuild_scene(); self.rebuild_tree()
    def color_model(self,m,attr='color'):
        c=QColorDialog.getColor(QColor(*getattr(m,attr)),self)
        if c.isValid(): setattr(m,attr,(c.red(),c.green(),c.blue())); self.rebuild_scene(); self.rebuild_tree()
    def live_refresh(self):
        self.rebuild_tree(); self.rebuild_pin_table()
    def apply_line_defaults(self):
        for it in self.scene.selectedItems():
            if it.data(0)=='PIN': it.model.line_style=self.line_style.currentText(); it.model.line_width=self.line_width.value(); it.model.color=self.default_color
            if it.data(0)=='GRAPHIC': it.model.style.line_style=self.line_style.currentText(); it.model.style.line_width=self.line_width.value(); it.model.style.stroke=self.default_color
            if it.data(0)=='BODY': it.model.line_style=self.line_style.currentText(); it.model.line_width=self.line_width.value(); it.model.color=self.default_color
        self.rebuild_scene(); self.rebuild_tree()
    def add_pin(self,side,x=None,y=None):
        p=create_auto_pin(self.symbol,self.current_unit,side)
        if x is not None: p.x=x
        if y is not None: p.y=y
        self.current_unit.pins.append(p); self.validate_pins(silent=True); self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()
    def add_graphic(self,tool,x,y):
        shape={DrawTool.LINE.value:'line',DrawTool.RECT.value:'rect',DrawTool.ELLIPSE.value:'ellipse'}[tool]
        self.current_unit.graphics.append(GraphicModel(shape=shape,x=x,y=y,style=StyleModel(stroke=self.default_color,line_width=self.line_width.value(),line_style=self.line_style.currentText())))
        self.rebuild_scene(); self.rebuild_tree()
    def copy_selected(self):
        sel=[i for i in self.scene.selectedItems() if i.data(0) in ('PIN','TEXT','GRAPHIC','BODY')]
        if not sel: return
        it=sel[0]; self.clipboard=(it.data(0),copy.deepcopy(it.model)); self.statusBar().showMessage('Copied '+it.data(0),2000)
    def paste_selected(self):
        if not self.clipboard: return
        kind,m=self.clipboard; m=copy.deepcopy(m)
        if hasattr(m,'x'): m.x+=1
        if hasattr(m,'y'): m.y-=1
        if kind=='PIN': m.number=self.next_free_pin_number(); self.current_unit.pins.append(m)
        elif kind=='TEXT': self.current_unit.texts.append(m)
        elif kind=='GRAPHIC': self.current_unit.graphics.append(m)
        elif kind=='BODY': self.current_unit.body=m
        self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()
    def next_free_pin_number(self):
        from symbol_wizard.rules.grid import next_pin_number
        return next_pin_number([p.number for u in self.symbol.units for p in u.pins])
    def delete_selected(self):
        sel=[i for i in self.scene.selectedItems() if i.data(0) in ('PIN','TEXT','GRAPHIC')]
        if not sel: return
        it=sel[0]; u=self.current_unit
        if it.data(0)=='PIN': u.pins=[p for p in u.pins if p is not it.model]
        elif it.data(0)=='TEXT': u.texts=[t for t in u.texts if t is not it.model]
        elif it.data(0)=='GRAPHIC': u.graphics=[g for g in u.graphics if g is not it.model]
        self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()
    def validate_pins(self,silent=False):
        dup=duplicate_pin_numbers(self.symbol)
        if dup and not silent: QMessageBox.warning(self,'Pin validation','Doppelte Pinnummern im Symbol sind verboten: '+', '.join(dup))
        elif not dup and not silent: QMessageBox.information(self,'Pin validation','Keine doppelten Pinnummern gefunden.')
        return not dup
    def pin_table_changed(self,r,c):
        if self.suspend: return
        it=self.pin_table.item(r,c); ui,pi,col=it.data(Qt.UserRole); p=self.symbol.units[ui].pins[pi]; val=it.text()
        if col==1: p.number=val
        elif col==2: p.name=val
        elif col==3: p.function=val
        elif col==4: p.pin_type=val
        self.validate_pins(silent=True); self.rebuild_scene(); self.rebuild_tree()
    def tree_clicked(self,item,col):
        data=item.data(0,Qt.UserRole)
        if not data: return
        kind,ui,idx=data; self.current_unit_index=ui; self.rebuild_unit_tabs(); self.rebuild_scene()
    def change_symbol(self,i):
        if i<0: return
        self.library.current_symbol_index=i; self.current_unit_index=0; self.rebuild_unit_tabs(); self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table(); self.grid_spin.setValue(self.symbol.grid_inch)
    def change_unit(self,i):
        if i<0: return
        self.current_unit_index=i; self.rebuild_scene(); self.rebuild_tree(); self.rebuild_pin_table()
    def new_symbol(self):
        base='Symbol'; self.library.add_symbol(base); self.current_unit_index=0; self.rebuild_all()
    def set_grid(self,v): self.symbol.grid_inch=v; self.rebuild_scene()
    def save_current_symbol(self):
        if not self.validate_pins(): return
        p,_=QFileDialog.getSaveFileName(self,'Save Current Symbol JSON',self.symbol.name+'.json','JSON (*.json)')
        if p: save_symbol(p,self.symbol)
    def save_all_symbols(self):
        for s in self.library.symbols:
            d=duplicate_pin_numbers(s)
            if d: QMessageBox.warning(self,'Pin validation',f'{s.name}: doppelte Pinnummern: '+', '.join(d)); return
        p,_=QFileDialog.getSaveFileName(self,'Save All Symbols JSON','symbol_library.json','JSON (*.json)')
        if p: save_library(p,self.library)
    def open_library(self):
        p,_=QFileDialog.getOpenFileName(self,'Open Library JSON','','JSON (*.json)')
        if p: self.library=load_library(p); self.current_unit_index=0; self.rebuild_all()
    def import_symbol(self):
        p,_=QFileDialog.getOpenFileName(self,'Import Symbol JSON','','JSON (*.json)')
        if not p: return
        s=load_symbol(p); existing={x.name for x in self.library.symbols}; base=s.name; i=2
        while s.name in existing: s.name=f'{base}_{i}'; i+=1
        self.library.symbols.append(s); self.library.current_symbol_index=len(self.library.symbols)-1; self.current_unit_index=0; self.rebuild_all()
