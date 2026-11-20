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
    x = body.x
    if side == PinSide.RIGHT.value:
        x = body.x + body.width
    elif side == PinSide.TOP.value:
        x = body.x + 2.0
        y = body.y
    elif side == PinSide.BOTTOM.value:
        x = body.x + 2.0
        y = body.y - body.height
    if same_side:
        # Continue along the selected side using the new pin's type-specific spacing.
        spacing = pin_spacing_grid(pin_type)
        if side in (PinSide.LEFT.value, PinSide.RIGHT.value):
            lowest = min(p.y for p in same_side)
            y = lowest - spacing
        else:
            rightmost = max(p.x for p in same_side)
            x = rightmost + spacing
    return PinModel(number=number, side=side, x=x, y=y, pin_type=pin_type)
