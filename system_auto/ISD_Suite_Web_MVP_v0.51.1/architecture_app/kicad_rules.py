"""KiCad net-class projection for component-free SPOT connectivity designs.

Routing dimensions are exported only when they are explicitly present in SPOT.
The schematic palette is a visual classification, not a PCB manufacturing rule.
"""
from __future__ import annotations

import hashlib
import json
import re


_PALETTE = {
    "Bus": (238, 180, 24),
    "Power": (212, 49, 49),
    "Analog": (37, 139, 76),
    "Differential": (37, 139, 76),
    "Clock": (123, 62, 180),
    "RF": (222, 109, 32),
    "Digital": (50, 92, 186),
}
_DIMENSIONS = {
    "clearanceMm": "clearance",
    "trackWidthMm": "track_width",
    "viaDiameterMm": "via_diameter",
    "viaDrillMm": "via_drill",
    "diffPairWidthMm": "diff_pair_width",
    "diffPairGapMm": "diff_pair_gap",
    "diffPairViaGapMm": "diff_pair_via_gap",
}


def _rule_data(signal) -> dict:
    scoped = getattr(signal, "realization_attributes", {})
    values = scoped.get("ecad", signal.attributes.get("ecad", {}))
    if not isinstance(values, dict):
        return {}
    kicad = values.get("kicad", {})
    return kicad if isinstance(kicad, dict) else {}


def _class_name(signal) -> str:
    rules = _rule_data(signal)
    explicit = getattr(signal, "realization_attributes", {}).get("netClass") or rules.get("netClass") or signal.attributes.get("netClass")
    if explicit:
        if not isinstance(explicit, str) or not re.fullmatch(r"[\w .+-]{1,64}", explicit):
            raise ValueError(f"Ungültige Netzklasse für {signal.name}")
        return explicit
    kind = "Bus" if signal.connection_type.value == "Bus" else signal.signal_type.value
    base = "ISD_" + re.sub(r"[^a-zA-Z0-9_]+", "_", kind).strip("_")
    if _settings(signal):
        suffix = hashlib.sha256(signal.id.encode("utf-8")).hexdigest()[:8]
        return f"{base}_{suffix}"
    return base


def class_for(signal) -> str:
    return _class_name(signal)


def _settings(signal) -> dict:
    raw = _rule_data(signal).get("constraints", {})
    if not isinstance(raw, dict):
        raise ValueError(f"KiCad-Constraints für {signal.name} müssen ein Objekt sein")
    unknown = set(raw) - set(_DIMENSIONS)
    if unknown:
        raise ValueError(f"Unbekannte KiCad-Constraints für {signal.name}: {', '.join(sorted(unknown))}")
    values: dict[str, float] = {}
    for key, target in _DIMENSIONS.items():
        if key in raw:
            value = raw[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value < 1000:
                raise ValueError(f"Ungültiger Constraint {key} für {signal.name}")
            values[target] = float(value)
    return values


def constraints_for(signal) -> dict[str, float]:
    return _settings(signal)


def _color(signal) -> tuple[int, int, int]:
    category = "Bus" if signal.connection_type.value == "Bus" else signal.signal_type.value
    return _PALETTE.get(category, _PALETTE["Digital"])


def _rgba(color: tuple[int, int, int]) -> str:
    return f"rgba({color[0]}, {color[1]}, {color[2]}, 1.000)"


def project_settings(signals: list, filename: str, catalog=None) -> str:
    """Project classes and per-member patterns; explicit rules only, never inferred."""
    from .netclasses import member_class
    classes={}
    for entry in catalog or []:
        classes[entry.name]={**entry.ecad_parameters,'name':entry.name,
            'priority':entry.priority if entry.priority is not None else len(classes)}
    patterns=set()
    for signal in signals:
        default=_class_name(signal)
        params=_settings(signal)
        color=_rgba(_color(signal))
        primary=member_class(signal)
        names=primary or [default]
        for name in names:
            previous=classes.setdefault(name,{'name':name,'priority':len(classes),'schematic_color':color})
            if name==names[0]:
                if any(key in previous and previous[key]!=value for key,value in params.items()):
                    raise ValueError(f'Netzklasse {name} hat widersprüchliche Constraints')
                previous.update(params)
        if signal.connection_type.value=='Bus':
            for member in signal.bus_contents:
                for name in member_class(signal,member) or names:
                    classes.setdefault(name,{'name':name,'priority':len(classes),'schematic_color':color})
                    patterns.add((member.name,name))
                    patterns.add((f'*/{member.name}',name))
        else:
            for name in names:
                patterns.add((signal.name,name))
                patterns.add((f'*/{signal.name}',name))
    fallback=classes.pop('Default',{'name':'Default','priority':2147483647})
    project={'meta':{'filename':filename,'version':1},'net_settings':{
        'meta':{'version':5},'classes':[fallback,*classes.values()],
        'netclass_patterns':[{'pattern':pattern,'netclass':name} for pattern,name in sorted(patterns)]}}
    return json.dumps(project,ensure_ascii=False,indent=2)+'\n'
