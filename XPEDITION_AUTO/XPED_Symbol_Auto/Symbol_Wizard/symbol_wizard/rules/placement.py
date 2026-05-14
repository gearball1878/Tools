from .grid import next_pin_number
from symbol_wizard.models.document import PinModel, PinSide, PinType


def all_pin_numbers(symbol):
    return [p.number for u in symbol.units for p in u.pins]


def pin_spacing_grid(pin_type: str) -> float:
    return 1.0 if pin_type in (PinType.POWER.value, PinType.GROUND.value) else 2.0


def create_auto_pin(symbol, unit, side: str, pin_type: str = PinType.BIDI.value) -> PinModel:
    body = unit.body
    same_side = [p for p in unit.pins if p.side == side]
    number = next_pin_number(all_pin_numbers(symbol))
    y = body.y + 2.0
    if same_side:
        # Continue below the lowest pin using the new pin's type-specific spacing.
        lowest = min(p.y for p in same_side)
        y = lowest - pin_spacing_grid(pin_type)
    x = body.x if side == PinSide.LEFT.value else body.x + body.width
    return PinModel(number=number, side=side, x=x, y=y, pin_type=pin_type)
