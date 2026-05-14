def snap(value: float, grid: float) -> float:
    if grid <= 0:
        return value
    return round(value / grid) * grid


def snap_half(value: float, grid: float) -> float:
    if grid <= 0:
        return value
    return round(value / (grid / 2.0)) * (grid / 2.0)
