from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

CONFIG_FILE = Path(__file__).with_name('symbol_types.json')
GLOBAL_ATTRIBUTES = ['RefDes', 'Package', 'Order Code', 'Value']

DEFAULT_CONFIG: Dict[str, Any] = {
  'global_attributes': GLOBAL_ATTRIBUTES,
  'types': {
    'R': {'refdes_prefix':'R', 'attributes':['Resistance','Tolerance','Power','Temperature Coefficient'], 'subtypes':{'Generic Resistor':{}, 'Shunt':{'attributes':['Resistance','Tolerance','Power','Current Rating']}, 'Varistor':{'attributes':['Voltage Rating','Energy','Clamping Voltage']}}},
    'L': {'refdes_prefix':'L', 'attributes':['Inductance','Current Rating','DCR','Tolerance'], 'subtypes':{'Inductor':{}, 'Choke':{'attributes':['Inductance','Current Rating','DCR','Common Mode']}, 'Transformer':{'refdes_prefix':'T','attributes':['Turns Ratio','Power','Isolation Voltage','Frequency']}}},
    'C': {'refdes_prefix':'C', 'attributes':['Capacitance','Tolerance','Voltage Rating','Dielectric'], 'subtypes':{'Kerko':{'attributes':['Capacitance','Tolerance','Voltage Rating','Dielectric','Package']}, 'Elko':{'attributes':['Capacitance','Voltage Rating','Ripple Current','ESR','Polarity']}, 'Tantal':{'attributes':['Capacitance','Voltage Rating','ESR','Polarity']}}},
    'Oscillator': {'refdes_prefix':'X', 'attributes':['Frequency','Stability','Voltage','Output Type'], 'subtypes':{'XO':{}, 'VCXO':{'attributes':['Frequency','Pull Range','Stability','Voltage']}, 'TCXO':{'attributes':['Frequency','Stability','Temperature Range']}}},
    'Quartz': {'refdes_prefix':'Y', 'attributes':['Frequency','Load Capacitance','ESR','Tolerance'], 'subtypes':{'2 Pin Quartz':{}, '4 Pin Quartz':{}}},
    'IC': {'refdes_prefix':'U', 'attributes':['Technology','Frequency','Supply Voltage','Manufacturer'], 'subtypes':{'Generic IC':{}, 'OpAmp':{'attributes':['Supply Voltage','Bandwidth','Slew Rate','Channels']}, 'ADC':{'attributes':['Resolution','Sample Rate','Interface','Reference Voltage']}}},
    'SoC': {'refdes_prefix':'U', 'attributes':['Core','Frequency','Memory','Package','Voltage'], 'subtypes':{'MCU':{}, 'MPU':{}, 'Wireless SoC':{'attributes':['Radio','Frequency Band','Flash','RAM','Package']}}},
    'SoM': {'refdes_prefix':'U', 'attributes':['Processor','Memory','Storage','Interfaces'], 'subtypes':{'Generic SoM':{}, 'Compute Module':{}}},
    'FET': {'refdes_prefix':'Q', 'attributes':['Vds','Id','RdsOn','Gate Charge'], 'subtypes':{'NMOS':{}, 'PMOS':{}, 'Dual MOSFET':{}}},
    'Bipolar Transistor': {'refdes_prefix':'Q', 'attributes':['Vceo','Ic','hFE','Power'], 'subtypes':{'NPN':{}, 'PNP':{}, 'Darlington':{}}},
    'Diode': {'refdes_prefix':'D', 'attributes':['Vr','If','Vf','Package'], 'subtypes':{'Signal Diode':{}, 'Schottky':{}, 'Zener':{'attributes':['Zener Voltage','Power','Tolerance']}, 'LED':{'attributes':['Color','If','Vf','Luminous Intensity']}}},
    'Connector': {'refdes_prefix':'J', 'attributes':['Positions','Pitch','Gender','Mounting'], 'subtypes':{'Header':{}, 'Socket':{}, 'USB':{'attributes':['USB Type','Speed','Mounting']}, 'Board-to-Board':{}}},
    'Fuse': {'refdes_prefix':'F', 'attributes':['Current Rating','Voltage Rating','Trip Characteristic'], 'subtypes':{'Fuse':{}, 'PTC':{}, 'eFuse':{'refdes_prefix':'U','attributes':['Current Limit','Voltage Rating','Package']}}},
    'Battery': {'refdes_prefix':'BT', 'attributes':['Voltage','Capacity','Chemistry'], 'subtypes':{'Cell':{}, 'Battery Pack':{}, 'Supercap':{'refdes_prefix':'C','attributes':['Capacitance','Voltage Rating','ESR']}}}
  }
}

def ensure_config() -> None:
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding='utf-8')

def load_config() -> Dict[str, Any]:
    ensure_config()
    try:
        return json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_config(cfg: Dict[str, Any]) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding='utf-8')

def deep_merge(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(old or {})
    for k, v in (new or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def type_names():
    return sorted(load_config().get('types', {}).keys())

def subtype_names(t: str):
    cfg = load_config()
    return sorted(cfg.get('types', {}).get(t, {}).get('subtypes', {}).keys()) or ['Generic']

def effective_profile(t: str, st: str) -> Dict[str, Any]:
    cfg = load_config()
    base = cfg.get('types', {}).get(t, {})
    sub = base.get('subtypes', {}).get(st, {})
    attrs = []
    for a in cfg.get('global_attributes', GLOBAL_ATTRIBUTES) + base.get('attributes', []) + sub.get('attributes', []):
        if a not in attrs:
            attrs.append(a)
    return {
        'refdes_prefix': sub.get('refdes_prefix', base.get('refdes_prefix', 'U')),
        'attributes': attrs,
        'template': deep_merge(base.get('template', {}), sub.get('template', {})),
    }
