from __future__ import annotations

import re

from .bus_content import BusContentTemplates
from .models import ArchitecturePackage, ArchitectureSignal, Connection, ConnectionEndpoint, EndpointRole, InterfaceDefinition, InterfaceMemberDefinition, InterfacePort, Direction, Signal, SignalType


GENERATED_SIGNAL_KEY = "architectureSignalId"


def _counter_store(package: ArchitecturePackage) -> dict[str, int]:
    counters = package.project.properties.setdefault("interfaceInstanceCounters", {})
    if not isinstance(counters, dict):
        counters = {}
        package.project.properties["interfaceInstanceCounters"] = counters
    return counters


def _counter_key(template_name: str, kind: str) -> str:
    normalized_kind = "Port" if str(kind).casefold() == "port" else "Link"
    return f"{template_name}:{normalized_kind}"


def register_interface_index(
    package: ArchitecturePackage,
    template_name: str,
    kind: str,
    index: int,
) -> None:
    counters = _counter_store(package)
    key = _counter_key(template_name, kind)
    counters[key] = max(int(counters.get(key, 0) or 0), int(index))


def next_interface_index(
    package: ArchitecturePackage,
    templates: BusContentTemplates,
    template_name: str,
    kind: str,
) -> int:
    resolved = templates.resolve_interface_template(template_name) or template_name
    existing_names = (
        [signal.name for signal in package.signals]
        if str(kind).casefold() == "link"
        else [
            port.name
            for element in _all_elements(package)
            for port in element.ports
        ]
    )
    detected = templates.next_index(existing_names, resolved, kind)
    counters = _counter_store(package)
    key = _counter_key(resolved, kind)
    index = max(detected, int(counters.get(key, 0) or 0) + 1)
    counters[key] = index
    return index


def _instance_index(
    templates: BusContentTemplates,
    template_name: str,
    kind: str,
    instance_name: str,
) -> int | None:
    resolved = templates.resolve_interface_template(template_name) or template_name
    normalized_kind = "Port" if str(kind).casefold() == "port" else "Link"
    if "[Link/Port]" in resolved:
        prefix, suffix = resolved.split("[Link/Port]", 1)
        pattern = re.compile(
            r"^" + re.escape(prefix + normalized_kind + "_") + r"(\d+)" + re.escape(suffix) + r"$",
            flags=re.IGNORECASE,
        )
    else:
        pattern = re.compile(
            r"^" + re.escape(resolved.strip(" _-") + f"_{normalized_kind}_") + r"(\d+)$",
            flags=re.IGNORECASE,
        )
    match = pattern.match(instance_name)
    return int(match.group(1)) if match else None


def _definition_pattern(package: ArchitecturePackage, signal: ArchitectureSignal) -> str:
    explicit_pattern = str(signal.properties.get("namingPattern") or "").strip()
    if explicit_pattern:
        return explicit_pattern
    if signal.interface_definition_id:
        project_template = next((
            item for item in package.interface_templates
            if item.id == signal.interface_definition_id
        ), None)
        if project_template:
            return project_template.name
        definition = next((
            item for item in package.interface_definitions
            if item.id == signal.interface_definition_id
        ), None)
        if definition:
            return definition.name
    return str(signal.properties.get("template") or signal.port_type or signal.name)


def ensure_builtin_interface_definition(
    package: ArchitecturePackage,
    templates: BusContentTemplates,
    template_name: str,
) -> InterfaceDefinition:
    resolved = templates.resolve_interface_template(template_name)
    if resolved is None:
        raise ValueError(f"Unbekannte Interfacevorlage: {template_name}")
    existing = next((
        item for item in package.interface_definitions
        if item.id == resolved or item.name.casefold() == resolved.casefold()
    ), None)
    member_patterns = templates.raw_interface_members(resolved)
    aliases = [
        alias for alias, target in templates.interface_aliases().items()
        if target == resolved
    ]
    members = [
        InterfaceMemberDefinition(
            name_pattern=pattern,
            direction_from_host=Direction.INOUT,
            host_pin_type="BI",
            participant_pin_type="BI",
            active_low=pattern.endswith("#") or pattern.endswith("_N"),
            properties={"pinMappingStatus": "To Review"},
        )
        for pattern in member_patterns
    ]
    if existing is None:
        existing = InterfaceDefinition(
            id=resolved,
            name=resolved,
            version=1,
            family="Interface",
            port_type=templates.template_base(resolved),
            source="Interface_Template_File.json",
            aliases=aliases,
            members=members,
        )
        package.interface_definitions.append(existing)
    else:
        existing.id = resolved
        existing.name = resolved
        existing.version = max(1, existing.version)
        existing.port_type = templates.template_base(resolved)
        existing.source = existing.source or "Interface_Template_File.json"
        existing.aliases = list(dict.fromkeys([*existing.aliases, *aliases]))
        if not existing.members or all(
            item.properties.get("migratedFrom") == "signals" for item in existing.members
        ):
            existing.members = members
    package.interface_definitions = [
        item for item in package.interface_definitions
        if item is existing or not (
            item.name.casefold() == resolved.casefold()
            or item.id == f"interface:{resolved}"
        )
    ]
    return existing


def migrate_interface_link_model(
    package: ArchitecturePackage,
    templates: BusContentTemplates,
) -> bool:
    """Normalize template-backed interfaces without materializing implementation port signals."""
    changed = False
    for signal in package.signals:
        if signal.properties.get("manualDefinitionOverride"):
            continue
        candidates = [
            signal.interface_definition_id or "",
            str(signal.properties.get("template") or ""),
            signal.port_type,
            signal.name,
        ]
        resolved = next((
            value for candidate in candidates
            if (value := templates.resolve_interface_template(candidate)) is not None
        ), None)
        if resolved is None:
            if signal.signal_type == SignalType.INTERFACE:
                signal.properties["interfaceTemplateUnresolved"] = True
            continue
        definition = ensure_builtin_interface_definition(package, templates, resolved)
        existing_index = _instance_index(templates, resolved, "Link", signal.name)
        index = existing_index or signal.instance_index
        if not index:
            index = next_interface_index(package, templates, resolved, "Link")
        register_interface_index(package, resolved, "Link", index)
        canonical_name = templates.canonical_instance_name(resolved, "Link", index)
        previous_name = signal.name
        if signal.name != canonical_name:
            signal.properties.setdefault("legacyName", signal.name)
            signal.name = canonical_name
            changed = True
        member_count = signal.properties.get("memberCount", 1)
        if len(templates.raw_interface_members(resolved)) == 1 and len(signal.bus_contents) > 1:
            member_count = max(int(member_count), len(signal.bus_contents))
        instance = templates.interface_signals(resolved, index, "Link", int(member_count))
        if len(instance.signals) > 1 and len(templates.raw_interface_members(resolved)) == 1:
            signal.properties["memberCount"] = len(instance.signals)
        selected = signal.properties.get("selectedMemberKeys")
        if selected is not None:
            if not isinstance(selected, list) or not selected or not all(
                isinstance(item, str) and item in instance.member_keys for item in selected
            ) or len(set(selected)) != len(selected):
                raise ValueError(f"Ungültige Mitgliedsauswahl für {signal.name}")
            instance.signals = [name for name, key in zip(instance.signals, instance.member_keys)
                                if key in selected]
            instance.member_keys = [key for key in instance.member_keys if key in selected]
        existing_by_key = {
            member.template_member_key: member
            for member in signal.bus_contents
            if member.template_member_key
        }
        existing_by_suffix: dict[str, Signal] = {}
        for member in signal.bus_contents:
            suffix = member.name
            if previous_name and suffix.casefold().startswith(previous_name.casefold()):
                suffix = suffix[len(previous_name):]
            signature = re.sub(r"[^a-z0-9]+", "", suffix.casefold())
            if signature:
                existing_by_suffix.setdefault(signature, member)
        normalized_members: list[Signal] = []
        for position, (name, member_key) in enumerate(zip(instance.signals, instance.member_keys)):
            member = existing_by_key.get(member_key)
            if member is None:
                raw_suffix = member_key.split("[Link/Port]", 1)[-1]
                signature = re.sub(r"[^a-z0-9]+", "", raw_suffix.casefold())
                member = existing_by_suffix.get(signature)
            if member is None:
                member = Signal(name=name)
            if member.name != name or member.template_member_key != member_key:
                changed = True
            member.name = name
            member.template_member_key = member_key
            member.active_low = member.active_low or name.endswith("#") or name.endswith("_N")
            member.properties.setdefault("pinMappingStatus", "To Review")
            normalized_members.append(member)
        if len(normalized_members) != len(signal.bus_contents):
            changed = True
        signal.bus_contents = normalized_members
        signal.signal_type = SignalType.INTERFACE
        signal.port_type = definition.port_type
        signal.interface_definition_id = definition.id
        signal.interface_definition_version = definition.version
        signal.interface_kind = "Link"
        signal.instance_index = index
        signal.catalog_family = "Interface"
        signal.catalog_template = resolved
        signal.catalog_status = "Bound"
        signal.properties["template"] = resolved
        signal.properties["interfaceTemplateUnresolved"] = False
        signal.properties["portSignalsMaterialized"] = False
        package.schema_version = "isd-suite/v3"
    return changed


def migrate_signal_template_bindings(
    package: ArchitecturePackage,
    templates: BusContentTemplates,
) -> bool:
    """Make the shared template catalog binding explicit for every architecture connection."""
    changed = False
    family_names = {item.casefold(): item for item in templates.families()}
    for signal in package.signals:
        if signal.properties.get("manualDefinitionOverride"):
            continue
        if signal.signal_type == SignalType.INTERFACE and signal.interface_definition_id:
            family = "Interface"
            built_in_template = templates.resolve_interface_template(
                signal.catalog_template
                or str(signal.properties.get("template") or "")
                or signal.interface_definition_id
            )
            project_definition = next((
                item for item in [*package.interface_templates, *package.interface_definitions]
                if item.id == signal.interface_definition_id
            ), None)
            template_name = built_in_template or (
                project_definition.name if project_definition is not None else ""
            )
        else:
            raw_family = signal.catalog_family or str(signal.properties.get("family") or "")
            family = family_names.get(raw_family.casefold(), raw_family.title())
            template_name = signal.catalog_template or str(signal.properties.get("template") or "")
        bound = bool(
            template_name
            and (
                templates.is_catalog_binding(family, template_name)
                or (family == "Interface" and signal.interface_definition_id)
            )
        )
        status = "Bound" if bound else "LegacyUnbound"
        if signal.catalog_family != (family if bound else signal.catalog_family):
            signal.catalog_family = family
            changed = True
        if bound and signal.catalog_template != template_name:
            signal.catalog_template = template_name
            changed = True
        if signal.catalog_status != status:
            signal.catalog_status = status
            changed = True
        if signal.connection_type.value == "Net":
            signal.properties["portNamingRule"] = "SignalName1to1"
    return changed


def _signal_type_from_port(port: InterfacePort) -> SignalType:
    value = port.port_type.casefold()
    if "power" in value:
        return SignalType.POWER
    if "analog" in value:
        return SignalType.ANALOG
    if "clock" in value:
        return SignalType.CLOCK
    if "reset" in value:
        return SignalType.RESET
    if "memory" in value:
        return SignalType.MEMORY
    if any(token in value for token in ("interface", "spi", "i2c", "uart", "ethernet", "can", "usb")):
        return SignalType.INTERFACE
    return SignalType.DIGITAL


def migrate_legacy_signal_catalog(package: ArchitecturePackage) -> bool:
    """Lift v0.4 port-contained signals into the central architecture catalog."""
    if package.signals:
        return False

    changed = False
    used_names: set[str] = set()

    def unique_name(preferred: str) -> str:
        base = preferred.strip() or "Signal"
        candidate = base
        suffix = 2
        while candidate.casefold() in used_names:
            candidate = f"{base}_{suffix}"
            suffix += 1
        used_names.add(candidate.casefold())
        return candidate

    for connection in list(package.connections):
        if connection.signal_id or not connection.endpoints:
            continue
        source_lookup = package.find_port(connection.endpoints[0].port_id)
        if source_lookup is None:
            continue
        source_port = source_lookup[2]
        members = [member.model_copy(deep=True) for member in source_port.signals]
        for member in members:
            member.source = None
            member.sinks = []
        signal = ArchitectureSignal(
            name=unique_name(connection.name or source_port.name),
            signal_type=_signal_type_from_port(source_port),
            connection_type=connection.connection_type,
            source={"element_id": connection.endpoints[0].element_id, "pin_type": "BI"},
            sinks=[{"element_id": endpoint.element_id, "pin_type": "BI"} for endpoint in connection.endpoints[1:]],
            bus_contents=members,
            properties={"migratedFrom": "PortSignals"},
        )
        package.signals.append(signal)
        for index, endpoint in enumerate(connection.endpoints):
            lookup = package.find_port(endpoint.port_id)
            if lookup:
                port = lookup[2]
                port.signals = []
                port.properties.update({
                    GENERATED_SIGNAL_KEY: signal.id,
                    "generatedBy": "SignalTopology",
                    "topologyRole": "Source" if index == 0 else "Sink",
                })
        connection.signal_id = signal.id
        changed = True

    for element in _all_elements(package):
        for port in list(element.ports):
            if not port.signals:
                continue
            members = [member.model_copy(deep=True) for member in port.signals]
            for member in members:
                member.source = None
                member.sinks = []
            signal = ArchitectureSignal(
                name=unique_name(port.name),
                signal_type=_signal_type_from_port(port),
                connection_type=port.connection_type,
                source={"element_id": element.id, "pin_type": "BI"} if port.role == "Host" else None,
                sinks=[{"element_id": element.id, "pin_type": "BI"}] if port.role == "Participant" else [],
                bus_contents=members,
                properties={"migratedFrom": "PortSignals"},
            )
            package.signals.append(signal)
            port.signals = []
            port.properties.update({
                GENERATED_SIGNAL_KEY: signal.id,
                "generatedBy": "SignalTopology",
                "topologyRole": "Source" if port.role == "Host" else "Sink",
            })
            changed = True

    if changed:
        synchronize_all_topologies(package)
    return changed


def _all_elements(package: ArchitecturePackage):
    for domain in package.domains:
        for element in domain.elements:
            yield element


def remove_signal_topology(package: ArchitecturePackage, signal_id: str) -> None:
    removed_port_ids: set[str] = set()
    for element in _all_elements(package):
        retained = []
        for port in element.ports:
            if port.properties.get(GENERATED_SIGNAL_KEY) == signal_id:
                removed_port_ids.add(port.id)
            else:
                retained.append(port)
        element.ports = retained
    package.connections = [
        connection for connection in package.connections
        if connection.signal_id != signal_id
        and not any(endpoint.port_id in removed_port_ids for endpoint in connection.endpoints)
    ]


def synchronize_signal_topology(
    package: ArchitecturePackage,
    signal: ArchitectureSignal,
    templates: BusContentTemplates | None = None,
) -> None:
    desired: dict[str, str] = {}
    if signal.source:
        desired[signal.source.element_id] = "Host"
    for sink in signal.sinks:
        desired[sink.element_id] = "Participant"

    existing: dict[str, InterfacePort] = {}
    obsolete_ids: set[str] = set()
    for element in _all_elements(package):
        matching = [
            port for port in element.ports
            if port.properties.get(GENERATED_SIGNAL_KEY) == signal.id
            or port.interface_link_id == signal.id
        ]
        if element.id not in desired:
            obsolete_ids.update(port.id for port in matching)
            element.ports = [port for port in element.ports if port not in matching]
            continue
        if matching:
            existing[element.id] = matching[0]
            obsolete_ids.update(port.id for port in matching[1:])
            element.ports = [port for port in element.ports if port not in matching[1:]]

    if obsolete_ids:
        package.connections = [
            connection for connection in package.connections
            if connection.signal_id == signal.id
            or not any(endpoint.port_id in obsolete_ids for endpoint in connection.endpoints)
        ]

    for element in _all_elements(package):
        role = desired.get(element.id)
        if role is None:
            continue
        port = existing.get(element.id)
        if port is None:
            port = InterfacePort(name=signal.name)
            element.ports.append(port)
            existing[element.id] = port
        is_individual_signal = signal.connection_type.value == "Net"
        # HW architecture boundaries carry the attached net/bus name. Functional
        # Port instances belong to the later FE layer inside the schematic.
        port.name = signal.name
        # Signal type controls filtering and visualization.  The explicit port
        # type retains the actual functional interface (for example SPI or
        # RGMII) independently of ECAD-tool-specific pin types.
        port.port_type = str(port.properties.get("manualPortType") or signal.port_type or signal.signal_type.value)
        port.interface_definition_id = signal.interface_definition_id
        port.interface_definition_version = signal.interface_definition_version
        port.interface_link_id = signal.id
        port.role = role
        port.connection_type = signal.connection_type
        port.side = "Right" if role == "Host" else "Left"
        # Member signals below an architecture port belong to the later ECAD
        # implementation. The architecture stores only the abstract boundary.
        if not port.properties.get("manualPortSignals"):
            port.signals = []
        port.properties.update({
            GENERATED_SIGNAL_KEY: signal.id,
            "generatedBy": "SignalTopology",
            "topologyRole": "Source" if role == "Host" else "Sink",
            "portSignalsMaterialized": False,
            "portNamingRule": (
                "SignalName1to1" if is_individual_signal else "BusName1to1"
            ),
        })

    managed = [connection for connection in package.connections if connection.signal_id == signal.id]
    if signal.source is None or not signal.sinks:
        package.connections = [connection for connection in package.connections if connection.signal_id != signal.id]
        return

    source_port = existing[signal.source.element_id]
    endpoints = [ConnectionEndpoint(
        element_id=signal.source.element_id,
        port_id=source_port.id,
        role=EndpointRole.SOURCE,
    )]
    endpoints.extend(ConnectionEndpoint(
        element_id=sink.element_id,
        port_id=existing[sink.element_id].id,
        role=EndpointRole.SINK,
    ) for sink in signal.sinks)
    connection = managed[0] if managed else Connection(name=signal.name, signal_id=signal.id)
    connection.name = signal.name
    connection.signal_id = signal.id
    connection.interface_link_id = signal.id
    connection.interface_definition_id = signal.interface_definition_id
    connection.interface_definition_version = signal.interface_definition_version
    connection.connection_type = signal.connection_type
    connection.endpoints = endpoints
    connection.description = signal.description
    connection.properties.update({
        "generatedBy": "SignalTopology",
        GENERATED_SIGNAL_KEY: signal.id,
        "interfaceKind": signal.interface_kind or (
            "Link" if signal.signal_type == SignalType.INTERFACE else "Net"
        ),
    })
    package.connections = [item for item in package.connections if item.signal_id != signal.id]
    package.connections.append(connection)


def synchronize_all_topologies(
    package: ArchitecturePackage,
    templates: BusContentTemplates | None = None,
) -> None:
    known = {signal.id for signal in package.signals}
    for signal in package.signals:
        synchronize_signal_topology(package, signal, templates)
    stale = {
        str(port.properties.get(GENERATED_SIGNAL_KEY))
        for element in _all_elements(package)
        for port in element.ports
        if port.properties.get(GENERATED_SIGNAL_KEY) and port.properties.get(GENERATED_SIGNAL_KEY) not in known
    }
    for signal_id in stale:
        remove_signal_topology(package, signal_id)
