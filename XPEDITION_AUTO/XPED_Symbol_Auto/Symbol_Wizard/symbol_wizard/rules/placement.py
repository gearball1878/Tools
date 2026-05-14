from symbol_wizard.models.document import PinModel, PinSide, PinType, SymbolUnitModel


def min_pin_spacing_grid(pin_type: str) -> float:
    if pin_type in (PinType.POWER.value, PinType.GROUND.value):
        return 1.0
    return 2.0


def next_pin_position(unit: SymbolUnitModel, side: str) -> tuple[float, float]:
    body = unit.body
    pins_on_side = [p for p in unit.pins if p.side == side]
    y = body.y + 2.0
    if pins_on_side:
        last = max(pins_on_side, key=lambda p: p.y)
        y = last.y + min_pin_spacing_grid(last.pin_type)
    x = body.x if side == PinSide.LEFT.value else body.x + body.width
    return x, y


def create_default_pin(unit: SymbolUnitModel, side: str) -> PinModel:
    x, y = next_pin_position(unit, side)
    return PinModel(
        number=str(len(unit.pins) + 1),
        name="PIN",
        function="FUNC",
        pin_type=PinType.BIDI.value,
        side=side,
        x=x,
        y=y,
        length=2.0,
    )
