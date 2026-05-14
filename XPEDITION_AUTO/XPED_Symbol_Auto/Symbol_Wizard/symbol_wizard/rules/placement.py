from .grid import next_pin_number
from symbol_wizard.models.document import PinModel, PinSide, PinType

def all_pin_numbers(symbol):
    return [p.number for u in symbol.units for p in u.pins]

def create_auto_pin(symbol, unit, side: str) -> PinModel:
    body=unit.body
    same_side=[p for p in unit.pins if p.side==side]
    number=next_pin_number(all_pin_numbers(symbol))
    y=body.y+2.0+len(same_side)*2.0
    x=body.x if side==PinSide.LEFT.value else body.x+body.width
    return PinModel(number=number, side=side, x=x, y=y, pin_type=PinType.BIDI.value)
