PX_PER_INCH = 960.0

def snap(value: float, grid_px: float) -> float:
    return round(value / grid_px) * grid_px if grid_px else value

def next_pin_number(existing: list[str]) -> str:
    nums=[]
    for n in existing:
        try: nums.append(int(str(n)))
        except ValueError: pass
    i=(max(nums)+1) if nums else 1
    while str(i) in existing: i+=1
    return str(i)

def duplicate_pin_numbers(symbol) -> list[str]:
    seen=set(); dup=[]
    for unit in symbol.units:
        for p in unit.pins:
            n=str(p.number).strip()
            if not n: continue
            if n in seen and n not in dup: dup.append(n)
            seen.add(n)
    return dup
