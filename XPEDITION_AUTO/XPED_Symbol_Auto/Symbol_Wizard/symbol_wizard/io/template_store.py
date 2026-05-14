from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict
from symbol_wizard.models.document import SymbolUnitModel, SymbolBodyModel, PinModel, FontModel

DEFAULT_TYPES: Dict[str, Any] = {
  "IC": {"prefix":"U", "subtypes": {"Generic IC": {"body":{"width":16,"height":24}, "attributes":["RefDes","Package","Order Code","Value"], "pins":[]},
                                      "SoC": {"body":{"width":20,"height":30}, "attributes":["RefDes","Package","Order Code","Value","Frequency","Technology"], "pins":[]},
                                      "SoM": {"body":{"width":24,"height":32}, "attributes":["RefDes","Package","Order Code","Value","Technology"], "pins":[]}}},
  "R": {"prefix":"R", "subtypes": {"Resistor": {"body":{"width":6,"height":2}, "attributes":["RefDes","Value","Order Code","Package","Tolerance","Power"], "pins":[{"number":"1","name":"1","function":"","pin_type":"BIDI","side":"left","x":-3,"y":0},{"number":"2","name":"2","function":"","pin_type":"BIDI","side":"right","x":3,"y":0}]},
                                  "Shunt": {"body":{"width":8,"height":3}, "attributes":["RefDes","Value","Order Code","Package","Tolerance","Power"], "pins":[{"number":"1","name":"1","function":"","pin_type":"BIDI","side":"left","x":-4,"y":0},{"number":"2","name":"2","function":"","pin_type":"BIDI","side":"right","x":4,"y":0}]}}},
  "C": {"prefix":"C", "subtypes": {"Kerko": {"body":{"width":4,"height":4}, "attributes":["RefDes","Value","Order Code","Package","Voltage","Dielectric"], "pins":[{"number":"1","name":"1","function":"","pin_type":"BIDI","side":"left","x":-2,"y":0},{"number":"2","name":"2","function":"","pin_type":"BIDI","side":"right","x":2,"y":0}]},
                                  "Elko": {"body":{"width":5,"height":5}, "attributes":["RefDes","Value","Order Code","Package","Voltage","Polarity"], "pins":[{"number":"1","name":"PLUS","function":"+","pin_type":"POWER","side":"left","x":-2,"y":0},{"number":"2","name":"MINUS","function":"-","pin_type":"GROUND","side":"right","x":2,"y":0}]},
                                  "Tantal": {"body":{"width":5,"height":5}, "attributes":["RefDes","Value","Order Code","Package","Voltage","Polarity"], "pins":[]}}},
  "L": {"prefix":"L", "subtypes": {"Inductor": {"body":{"width":6,"height":3}, "attributes":["RefDes","Value","Order Code","Package","Current","DCR"], "pins":[{"number":"1","name":"1","function":"","pin_type":"BIDI","side":"left","x":-3,"y":0},{"number":"2","name":"2","function":"","pin_type":"BIDI","side":"right","x":3,"y":0}]},
                                  "Choke": {"body":{"width":8,"height":4}, "attributes":["RefDes","Value","Order Code","Package","Current","DCR"], "pins":[]},
                                  "Transformer": {"body":{"width":10,"height":8}, "attributes":["RefDes","Value","Order Code","Package","Turns Ratio","Isolation"], "pins":[]}}},
  "D": {"prefix":"D", "subtypes": {"Diode": {"body":{"width":5,"height":3}, "attributes":["RefDes","Value","Order Code","Package","Voltage","Current"], "pins":[{"number":"1","name":"A","function":"ANODE","pin_type":"ANALOG","side":"left","x":-2,"y":0},{"number":"2","name":"K","function":"CATHODE","pin_type":"ANALOG","side":"right","x":2,"y":0}]}, "TVS": {"body":{"width":5,"height":4}, "attributes":["RefDes","Value","Order Code","Package","Voltage","Power"], "pins":[]}}},
  "Q": {"prefix":"Q", "subtypes": {"FET": {"body":{"width":6,"height":8}, "attributes":["RefDes","Order Code","Package","Vds","RdsOn","Qg"], "pins":[{"number":"G","name":"G","function":"GATE","pin_type":"IN","side":"left","x":-3,"y":0},{"number":"D","name":"D","function":"DRAIN","pin_type":"ANALOG","side":"right","x":3,"y":2},{"number":"S","name":"S","function":"SOURCE","pin_type":"ANALOG","side":"right","x":3,"y":-2}]},
                                  "Bipolar Transistor": {"body":{"width":6,"height":8}, "attributes":["RefDes","Order Code","Package","Vce","Ic","hFE"], "pins":[]}}},
  "X": {"prefix":"X", "subtypes": {"Quartz": {"body":{"width":6,"height":4}, "attributes":["RefDes","Frequency","Order Code","Package","Load Capacitance"], "pins":[{"number":"1","name":"X1","function":"","pin_type":"ANALOG","side":"left","x":-3,"y":0},{"number":"2","name":"X2","function":"","pin_type":"ANALOG","side":"right","x":3,"y":0}]},
                                  "Oscillator": {"body":{"width":8,"height":6}, "attributes":["RefDes","Frequency","Order Code","Package","Voltage"], "pins":[]}}},
  "J": {"prefix":"J", "subtypes": {"Connector": {"body":{"width":10,"height":20}, "attributes":["RefDes","Order Code","Package","Pitch","Positions"], "pins":[]}}},
  "F": {"prefix":"F", "subtypes": {"Fuse": {"body":{"width":6,"height":3}, "attributes":["RefDes","Value","Order Code","Package","Current","Voltage"], "pins":[]}}},
  "BAT": {"prefix":"BT", "subtypes": {"Battery": {"body":{"width":5,"height":7}, "attributes":["RefDes","Value","Order Code","Package","Voltage","Capacity"], "pins":[]}}},
  "VAR": {"prefix":"RV", "subtypes": {"Varistor": {"body":{"width":6,"height":4}, "attributes":["RefDes","Value","Order Code","Package","Voltage","Energy"], "pins":[]}}}
}


def config_path() -> Path:
    return Path(__file__).resolve().parents[2] / 'symbol_types.json'


def deep_merge(old, new):
    if isinstance(old, dict) and isinstance(new, dict):
        out = dict(old)
        for k, v in new.items():
            out[k] = deep_merge(out.get(k), v) if k in out else v
        return out
    return new if new is not None else old


def load_templates() -> Dict[str, Any]:
    p = config_path()
    if not p.exists():
        p.write_text(json.dumps(DEFAULT_TYPES, indent=2), encoding='utf-8')
        return json.loads(json.dumps(DEFAULT_TYPES))
    try:
        return deep_merge(DEFAULT_TYPES, json.loads(p.read_text(encoding='utf-8')))
    except Exception:
        return json.loads(json.dumps(DEFAULT_TYPES))


def save_templates(data: Dict[str, Any]):
    config_path().write_text(json.dumps(data, indent=2), encoding='utf-8')


def template_to_unit(symbol_type: str, subtype: str, templates=None) -> SymbolUnitModel:
    data = templates or load_templates()
    t = data.get(symbol_type, {})
    sub = t.get('subtypes', {}).get(subtype) or next(iter(t.get('subtypes', {}).values()), {})
    body_data = sub.get('body', {})
    body = SymbolBodyModel()
    body.width = float(body_data.get('width', body.width))
    body.height = float(body_data.get('height', body.height))
    body.x = -body.width/2
    body.y = body.height/2
    attrs = ['RefDes','Package','Order Code','Value'] + [a for a in sub.get('attributes', []) if a not in ('RefDes','Package','Order Code','Value')]
    prefix = t.get('prefix', 'U')
    body.attributes = {a: '' for a in attrs}
    body.attributes['RefDes'] = prefix + '?'
    body.visible_attributes = {a: a in ('RefDes','Package','Value') for a in attrs}
    unit = SymbolUnitModel(name='Unit A', body=body)
    for pd in sub.get('pins', []):
        p = PinModel()
        for k, v in pd.items():
            if hasattr(p, k): setattr(p, k, v)
        unit.pins.append(p)
    return unit


def unit_to_template(unit: SymbolUnitModel, existing_subtemplate=None) -> Dict[str, Any]:
    old = existing_subtemplate or {}
    attrs = list(unit.body.attributes.keys())
    new = {
        'body': {'width': unit.body.width, 'height': unit.body.height, 'line_width': unit.body.line_width, 'line_style': unit.body.line_style},
        'attributes': attrs,
        'pins': [asdict(p) for p in unit.pins],
        'graphics': [asdict(g) for g in unit.graphics],
        'texts': [asdict(t) for t in unit.texts],
    }
    return deep_merge(old, new)
