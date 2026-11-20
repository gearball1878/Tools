"""Shared block visibility rules; global returns keep their SPOT identity."""
import re


def is_global_ground(signal):
    if signal.connection_type.value != 'Net':
        return False
    # Exact ground names only: GND_SENSE and power-return measurements are signals.
    return bool(re.fullmatch(r'(?:GND|GROUND|[APDS]GND|(?:ISO|ISOLATED|CHASSIS|PE|SIGNAL|ANALOG|DIGITAL|POWER)_?(?:GND|GROUND)|(?:GND|GROUND)_[0-9]+)', signal.name.upper()))



def block_port_visible(package, port):
    identifier = port.interface_link_id or port.properties.get('architectureSignalId')
    signal = package.find_architecture_signal(identifier or '')
    return not is_global_ground(signal or port)


def domain_role(package, domain_id, signal):
    domain = package.find_domain(domain_id)
    ids = {e.id for e in domain.elements} if domain else set()
    return 'Host' if signal.source and signal.source.element_id in ids else 'Participant'
