from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Tuple

class PinType(str, Enum):
    IN='IN'; OUT='OUT'; BIDI='BIDI'; PASSIVE='PASSIVE'; POWER='POWER'; GROUND='GROUND'; ANALOG='ANALOG'
class PinSide(str, Enum):
    LEFT='left'; RIGHT='right'
class OriginMode(str, Enum):
    BOTTOM_LEFT='bottom_left'; BOTTOM_RIGHT='bottom_right'; CENTER='center'; TOP_LEFT='top_left'; TOP_RIGHT='top_right'
class DrawTool(str, Enum):
    SELECT='select'; PIN_LEFT='pin_left'; PIN_RIGHT='pin_right'; TEXT='text'; LINE='line'; RECT='rect'; ELLIPSE='ellipse'
class SymbolKind(str, Enum):
    SINGLE='single'; SPLIT='split'
class SheetFormat(str, Enum):
    A0='A0'; A1='A1'; A2='A2'; A3='A3'; A4='A4'; A5='A5'
class LineStyle(str, Enum):
    SOLID='solid'; DASH='dash'; DOT='dot'; DASH_DOT='dash_dot'

class TextHAlign(str, Enum):
    LEFT='left'; CENTER='center'; RIGHT='right'
class TextVAlign(str, Enum):
    UPPER='upper'; CENTER='center'; LOWER='lower'


@dataclass
class FontModel:
    family: str='Arial'
    size_grid: float=0.75
    color: Tuple[int,int,int]=(0,0,0)

@dataclass
class TransformModel:
    rotation: float=0.0
    scale_x: float=1.0
    scale_y: float=1.0

@dataclass
class StyleModel:
    stroke: Tuple[int,int,int]=(0,0,0)
    fill: Tuple[int,int,int]|None=None
    line_width: float=0.03
    line_style: str=LineStyle.SOLID.value

@dataclass
class GraphicModel(TransformModel):
    shape: str='line'
    x: float=0.0; y: float=0.0; w: float=2.0; h: float=2.0
    curve_radius: float=0.0
    style: StyleModel=field(default_factory=StyleModel)

@dataclass
class PinModel(TransformModel):
    number: str='1'; name: str='PIN'; function: str='FUNC'
    pin_type: str=PinType.BIDI.value; side: str=PinSide.LEFT.value
    x: float=0.0; y: float=0.0; length: float=2.0
    inverted: bool=False; color: Tuple[int,int,int]=(0,0,0)
    visible_number: bool=True; visible_name: bool=True; visible_function: bool=True
    line_width: float=0.03; line_style: str=LineStyle.SOLID.value
    number_font: FontModel=field(default_factory=lambda: FontModel(size_grid=0.45))
    label_font: FontModel=field(default_factory=lambda: FontModel(size_grid=0.55))

@dataclass
class TextModel(TransformModel):
    text: str='Text'; x: float=0.0; y: float=0.0
    font_family: str='Arial'; font_size_grid: float=0.9; color: Tuple[int,int,int]=(0,0,0)
    h_align: str=TextHAlign.LEFT.value; v_align: str=TextVAlign.UPPER.value
    wrap_text: bool=False

@dataclass
class SymbolBodyModel(TransformModel):
    # Default body placement: body center is the symbol origin (0, 0).
    # With the internal coordinate convention y points upward and the body rectangle
    # extends downward from (x, y), therefore x=-width/2 and y=height/2.
    x: float=-8.0; y: float=12.0; width: float=16.0; height: float=24.0
    color: Tuple[int,int,int]=(0,0,0); line_width: float=0.03; line_style: str=LineStyle.SOLID.value
    attribute_font: FontModel=field(default_factory=lambda: FontModel(size_grid=0.75))
    refdes_font: FontModel=field(default_factory=lambda: FontModel(size_grid=0.9))
    attributes: Dict[str,str]=field(default_factory=lambda:{'Order Code':'','Package':'','RefDes':'U?','Value':'','Frequency':'','Tolerance':'','Technology':''})
    visible_attributes: Dict[str,bool]=field(default_factory=lambda:{'Order Code':False,'Package':True,'RefDes':True,'Value':True,'Frequency':False,'Tolerance':False,'Technology':False})
    # Persistent placement/formatting model for displayed attribute text in the canvas.
    # The text itself is generated from attributes and is content-locked in the UI.
    attribute_texts: Dict[str, TextModel]=field(default_factory=dict)
    refdes_align: str='left'; body_attr_align: str='left'

@dataclass
class SymbolUnitModel:
    name: str='Unit A'
    body: SymbolBodyModel=field(default_factory=SymbolBodyModel)
    pins: List[PinModel]=field(default_factory=list)
    texts: List[TextModel]=field(default_factory=list)
    graphics: List[GraphicModel]=field(default_factory=list)

@dataclass
class SymbolModel:
    name: str='Symbol 1'
    kind: str=SymbolKind.SINGLE.value
    is_split: bool=False  # legacy compatibility; kind is authoritative
    grid_inch: float=0.100
    sheet_format: str=SheetFormat.A3.value
    origin: str=OriginMode.CENTER.value
    template_name: str=''
    units: List[SymbolUnitModel]=field(default_factory=lambda:[SymbolUnitModel()])

@dataclass
class LibraryModel:
    symbols: List[SymbolModel]=field(default_factory=lambda:[SymbolModel()])
    current_symbol_index: int=0

    def unique_symbol_name(self, base='Symbol') -> str:
        existing={s.name for s in self.symbols}
        i=1
        candidate=f'{base} {i}'
        while candidate in existing:
            i+=1
            candidate=f'{base} {i}'
        return candidate

    def unique_import_name(self, desired: str) -> str:
        existing={s.name for s in self.symbols}
        if desired not in existing:
            return desired
        i=2
        while f'{desired}_{i}' in existing:
            i+=1
        return f'{desired}_{i}'

    def add_symbol(self, base='Symbol', kind: str=SymbolKind.SINGLE.value) -> SymbolModel:
        name=self.unique_symbol_name(base)
        s=SymbolModel(name=name, kind=kind, is_split=(kind==SymbolKind.SPLIT.value))
        self.symbols.append(s)
        self.current_symbol_index=len(self.symbols)-1
        return s

    def current_symbol(self) -> SymbolModel:
        if not self.symbols:
            self.symbols.append(SymbolModel())
            self.current_symbol_index=0
        self.current_symbol_index=max(0,min(self.current_symbol_index,len(self.symbols)-1))
        return self.symbols[self.current_symbol_index]

def to_dict(obj):
    return asdict(obj)
