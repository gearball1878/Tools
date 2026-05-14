from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple


class PinType(str, Enum):
    IN = "IN"
    OUT = "OUT"
    BIDI = "BIDI"
    POWER = "POWER"
    GROUND = "GROUND"
    ANALOG = "ANALOG"


class PinSide(str, Enum):
    LEFT = "left"
    RIGHT = "right"


class OriginMode(str, Enum):
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    CENTER = "center"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"


class GraphicType(str, Enum):
    LINE = "line"
    RECT = "rect"
    ELLIPSE = "ellipse"


@dataclass
class PinModel:
    number: str = "1"
    name: str = "PIN"
    function: str = "FUNC"
    pin_type: str = PinType.BIDI.value
    side: str = PinSide.LEFT.value
    x: float = 0.0
    y: float = 0.0
    length: float = 2.0
    inverted: bool = False
    color: Tuple[int, int, int] = (0, 0, 0)
    visible_number: bool = True
    visible_name: bool = True
    visible_function: bool = True


@dataclass
class TextModel:
    text: str = "Text"
    x: float = 0.0
    y: float = 0.0
    font_family: str = "Arial"
    font_size_grid: float = 0.9
    color: Tuple[int, int, int] = (0, 0, 0)


@dataclass
class GraphicObjectModel:
    graphic_type: str = GraphicType.RECT.value
    x: float = 2.0
    y: float = 2.0
    width: float = 4.0
    height: float = 2.0
    x2: float = 6.0
    y2: float = 2.0
    color: Tuple[int, int, int] = (0, 0, 0)
    line_width: float = 1.5


@dataclass
class SymbolBodyModel:
    x: float = 0.0
    y: float = 0.0
    width: float = 16.0
    height: float = 24.0
    color: Tuple[int, int, int] = (0, 0, 0)
    attributes: Dict[str, str] = field(default_factory=lambda: {
        "Order Code": "",
        "Package": "",
        "RefDes": "U?",
        "Value": "",
        "Frequency": "",
        "Tolerance": "",
        "Technology": "",
    })
    visible_attributes: List[str] = field(default_factory=lambda: ["RefDes", "Value", "Package"])
    refdes_align: str = "left"
    body_attr_align: str = "left"


@dataclass
class SymbolUnitModel:
    name: str = "Unit A"
    body: SymbolBodyModel = field(default_factory=SymbolBodyModel)
    pins: List[PinModel] = field(default_factory=list)
    texts: List[TextModel] = field(default_factory=list)
    graphics: List[GraphicObjectModel] = field(default_factory=list)


@dataclass
class SymbolDocumentModel:
    name: str = "NewSymbol"
    grid_inch: float = 0.100
    origin: str = OriginMode.BOTTOM_LEFT.value
    units: List[SymbolUnitModel] = field(default_factory=lambda: [SymbolUnitModel()])
