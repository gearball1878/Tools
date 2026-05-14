import json
from pathlib import Path
from symbol_wizard.models.document import *

def _font(d, size=.75):
    return FontModel(**d) if isinstance(d, dict) else FontModel(size_grid=size)
def _style(d): return StyleModel(**d) if isinstance(d, dict) else StyleModel()
def _graphic(d):
    d = _coerce_transform(d)
    d['style'] = _style(d.get('style', {}))
    return GraphicModel(**d)
def _coerce_transform(d):
    d = dict(d or {})
    for key, default in [('rotation', 0.0), ('scale_x', 1.0), ('scale_y', 1.0)]:
        try:
            d[key] = float(d.get(key, default) or default)
        except (TypeError, ValueError):
            d[key] = default
    return d

def _pin(d):
    d=_coerce_transform(d)
    d['number_font']=_font(d.get('number_font', {}), .45)
    d['label_font']=_font(d.get('label_font', {}), .55)
    return PinModel(**d)
def _text(d): return TextModel(**_coerce_transform(d))
def _body(d):
    d=_coerce_transform(d)
    d['attribute_font']=_font(d.get('attribute_font', {}), .75)
    d['refdes_font']=_font(d.get('refdes_font', {}), .9)
    return SymbolBodyModel(**d)
def _unit(d):
    return SymbolUnitModel(name=d.get('name','Unit'), body=_body(d.get('body',{})), pins=[_pin(x) for x in d.get('pins',[])], texts=[_text(x) for x in d.get('texts',[])], graphics=[_graphic(x) for x in d.get('graphics',[])])
def _symbol(d):
    kind=d.get('kind')
    if not kind:
        kind=SymbolKind.SPLIT.value if d.get('is_split', False) else SymbolKind.SINGLE.value
    return SymbolModel(name=d.get('name','Symbol'), kind=kind, is_split=(kind==SymbolKind.SPLIT.value), grid_inch=d.get('grid_inch',0.1), sheet_format=d.get('sheet_format', SheetFormat.A3.value), origin=d.get('origin','bottom_left'), units=[_unit(x) for x in d.get('units',[]) ] or [SymbolUnitModel()])

def save_library(path, library: LibraryModel):
    Path(path).write_text(json.dumps(to_dict(library), indent=2), encoding='utf-8')

def load_library(path) -> LibraryModel:
    d=json.loads(Path(path).read_text(encoding='utf-8'))
    return LibraryModel(symbols=[_symbol(x) for x in d.get('symbols',[]) ] or [SymbolModel()], current_symbol_index=d.get('current_symbol_index',0))

def save_symbol(path, symbol: SymbolModel):
    Path(path).write_text(json.dumps(to_dict(symbol), indent=2), encoding='utf-8')

def load_symbol(path) -> SymbolModel:
    return _symbol(json.loads(Path(path).read_text(encoding='utf-8')))
