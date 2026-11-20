"""Hierarchical signal-flow shapes; component library pin types stay untouched."""
from __future__ import annotations
import re


def member_direction(template, member):
    direction = member.direction.value
    if member.properties.get('directionReviewed') or direction in {'in','out','passive'}:
        return direction
    token = (member.template_member_key or member.name).upper()
    family = template.upper()
    # Only unambiguous standard roles are resolved from a bound template.
    suffix = re.split(r'[_\]]',token)[-1].rstrip('#')
    if family.startswith('SPI_'):
        if suffix=='MISO': return 'in'
        if suffix in {'MOSI','SCLK','SCK','CLK'} or re.fullmatch(r'CS\d*',suffix): return 'out'
    if family.startswith('UART_'):
        if suffix in {'RX','CTS'}: return 'in'
        if suffix in {'TX','RTS'}: return 'out'
    if family.startswith('I2C_') and suffix in {'SCL','SDA'}: return 'inout'
    if family.startswith('PWM_') and re.fullmatch(r'OUT\d*',suffix): return 'out'
    return None


def hierarchical_mapping(package, signal, role):
    directions = []
    template = signal.catalog_template if signal.catalog_status=='Bound' else ''
    definition = next((d for d in package.interface_definitions if d.id == signal.interface_definition_id),None)
    for member in signal.bus_contents:
        direction = member_direction(template,member)
        if direction is None and definition:
            pattern = next((d for d in definition.members if d.name_pattern == member.template_member_key),None)
            if pattern and pattern.properties.get('pinMappingStatus') in {'Reviewed','Explicit'}:
                direction = pattern.direction_from_host.value
        directions.append(direction)
    if signal.connection_type.value=='Net' and not directions:
        direction = signal.properties.get('directionFromHost')
        if direction in {'in','out','inout','passive'}: directions=[direction]
    if signal.connection_type.value=='Net' and (not directions or any(d is None for d in directions)):
        if signal.signal_type.value in {'Clock','Reset','Control','Status'} and signal.catalog_status=='Bound': directions=['out']
    if not directions or any(d is None for d in directions): return 'passive','Offen: Signalrichtung prüfen'
    if set(directions)=={'passive'}: return 'passive','Explizit passiv'
    if role=='Mixed' or 'inout' in directions or len(set(directions))>1: return 'bidirectional','Aus Mitgliedssignalen'
    direction = directions[0]
    if direction=='out': return ('output' if role=='Host' else 'input'),'Aus Mitgliedssignalen'
    if direction=='in': return ('input' if role=='Host' else 'output'),'Aus Mitgliedssignalen'
    return 'passive','Offen: Signalrichtung prüfen'
