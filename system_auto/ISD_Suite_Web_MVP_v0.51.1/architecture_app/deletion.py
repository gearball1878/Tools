from __future__ import annotations

from dataclasses import dataclass

from .models import ArchitecturePackage, ArchitectureSignal, Signal
from .topology import GENERATED_SIGNAL_KEY, remove_signal_topology, synchronize_all_topologies, synchronize_signal_topology


@dataclass(frozen=True)
class DeletionImpact:
    object_type: str
    name: str
    summary: str
    details: tuple[str, ...]
    success_message: str


def _affected_topology(package: ArchitecturePackage, element_ids: set[str]) -> tuple[int, int]:
    signal_count = sum(
        1
        for signal in package.signals
        if (signal.source and signal.source.element_id in element_ids)
        or any(sink.element_id in element_ids for sink in signal.sinks)
    )
    connection_count = sum(
        1
        for connection in package.connections
        if any(endpoint.element_id in element_ids for endpoint in connection.endpoints)
    )
    return signal_count, connection_count


def _find_bus_content_signal(
    package: ArchitecturePackage,
    object_id: str,
) -> tuple[ArchitectureSignal, Signal] | None:
    for architecture_signal in package.signals:
        for member in architecture_signal.bus_contents:
            if member.id == object_id:
                return architecture_signal, member
    return None


def deletion_impact(package: ArchitecturePackage, object_id: str) -> DeletionImpact | None:
    domain = package.find_domain(object_id)
    if domain:
        element_ids = {element.id for element in domain.elements}
        signal_count, connection_count = _affected_topology(package, element_ids)
        port_count = sum(len(element.ports) for element in domain.elements)
        return DeletionImpact(
            "Domain",
            domain.name,
            "Die Domain und alle darin enthaltenen Architecture Elements werden gelöscht.",
            (
                f"{len(domain.elements)} Architecture Elements",
                f"{port_count} Ports",
                f"Zuweisungen in {signal_count} Signalen",
                f"{connection_count} betroffene Verbindungen",
            ),
            "Domain gelöscht",
        )

    element_result = package.find_element(object_id)
    if element_result:
        _domain, element = element_result
        signal_count, connection_count = _affected_topology(package, {element.id})
        return DeletionImpact(
            "Architecture Element",
            element.name,
            "Das Architecture Element wird aus seiner Domain entfernt.",
            (
                f"{len(element.ports)} Ports",
                f"Zuweisungen in {signal_count} Signalen",
                f"{connection_count} betroffene Verbindungen",
            ),
            "Architecture Element gelöscht",
        )

    port_result = package.find_port(object_id)
    if port_result:
        _domain, element, port = port_result
        generated_signal = package.find_architecture_signal(str(port.properties.get(GENERATED_SIGNAL_KEY, "")))
        if generated_signal:
            role = "Host" if generated_signal.source and generated_signal.source.element_id == element.id else "Teilnehmer"
            details = (f"{role}-Zuweisung im Signal „{generated_signal.name}“",)
            summary = "Der abgeleitete Port und seine zugehörige Topologiezuweisung werden entfernt."
        else:
            connection_count = sum(
                1 for connection in package.connections
                if any(endpoint.port_id == port.id for endpoint in connection.endpoints)
            )
            details = (f"{len(port.signals)} enthaltene Signale", f"{connection_count} betroffene Verbindungen")
            summary = "Der Port und seine unmittelbar abhängigen Verbindungen werden entfernt."
        return DeletionImpact("Port", port.name, summary, details, "Port gelöscht")

    architecture_signal = package.find_architecture_signal(object_id)
    if architecture_signal:
        port_count = sum(
            1
            for domain in package.domains
            for element in domain.elements
            for port in element.ports
            if port.properties.get(GENERATED_SIGNAL_KEY) == architecture_signal.id
        )
        connection_count = sum(1 for item in package.connections if item.signal_id == architecture_signal.id)
        return DeletionImpact(
            "Signal / Interface",
            architecture_signal.name,
            "Die Signaldefinition und die daraus abgeleitete Topologie werden gelöscht.",
            (
                f"{len(architecture_signal.bus_contents)} Mitgliedssignale",
                f"{port_count} automatisch erzeugte Ports",
                f"{connection_count} automatisch erzeugte Verbindungen",
            ),
            "Signaldefinition gelöscht",
        )

    connection = next((item for item in package.connections if item.id == object_id), None)
    if connection:
        managed_signal = package.find_architecture_signal(connection.signal_id or "")
        if managed_signal:
            return DeletionImpact(
                "Verbindung",
                connection.name,
                "Die Verbindung sowie deren Host- und Teilnehmerzuweisungen werden entfernt.",
                (f"Die Signaldefinition „{managed_signal.name}“ bleibt im Katalog erhalten.",),
                "Verbindung und Topologiezuweisung gelöscht",
            )
        return DeletionImpact(
            "Verbindung",
            connection.name,
            "Die manuell angelegte Verbindung wird gelöscht.",
            (f"{len(connection.endpoints)} Endpunkte",),
            "Verbindung gelöscht",
        )

    legacy_signal = package.find_signal(object_id)
    if legacy_signal:
        return DeletionImpact(
            "Port-Signal",
            legacy_signal[3].name,
            "Das ältere, direkt im Port gespeicherte Signal wird gelöscht.",
            (f"Port: {legacy_signal[2].name}",),
            "Port-Signal gelöscht",
        )

    bus_content = _find_bus_content_signal(package, object_id)
    if bus_content:
        architecture_signal, member = bus_content
        return DeletionImpact(
            "Mitgliedssignal",
            member.name,
            "Das Einzelsignal wird aus der Interface- oder Signaldefinition entfernt.",
            (f"Interface: {architecture_signal.name}",),
            "Mitgliedssignal gelöscht",
        )
    return None


def _detach_elements(package: ArchitecturePackage, element_ids: set[str]) -> None:
    for signal in package.signals:
        if signal.source and signal.source.element_id in element_ids:
            signal.source = None
        signal.sinks = [sink for sink in signal.sinks if sink.element_id not in element_ids]
    for domain in package.domains:
        for element in domain.elements:
            for port in element.ports:
                for signal in port.signals:
                    if signal.source and signal.source.element_id in element_ids:
                        signal.source = None
                    signal.sinks = [sink for sink in signal.sinks if sink.element_id not in element_ids]
    package.connections = [
        connection for connection in package.connections
        if not any(endpoint.element_id in element_ids for endpoint in connection.endpoints)
    ]


def _remove_traceability_targets(package: ArchitecturePackage, target_ids: set[str]) -> None:
    """Remove links whose architecture target disappeared, but keep requirements."""
    if not target_ids:
        return
    package.requirement_links = [
        link for link in package.requirement_links if link.target_id not in target_ids
    ]
    package.component_allocations = [
        allocation for allocation in package.component_allocations
        if allocation.element_id not in target_ids
    ]
    for conflict in package.engineering_conflicts:
        if conflict.target_id in target_ids:
            conflict.target_type = None
            conflict.target_id = None
    for realization in package.technical_realizations:
        if realization.architecture_element_id in target_ids:
            realization.architecture_element_id = None
    for fe in package.function_elements:
        if fe.architecture_element_id in target_ids:fe.architecture_element_id=None
        fe.interface_signal_ids=[i for i in fe.interface_signal_ids if i not in target_ids]


def delete_object(package: ArchitecturePackage, object_id: str) -> DeletionImpact:
    from .traceability import project_objects,remove_deleted_references
    before={oid for items in project_objects(package).values() for oid in items}
    result=_delete_object(package,object_id)
    after={oid for items in project_objects(package).values() for oid in items}
    remove_deleted_references(package,before-after)
    return result


def _delete_object(package: ArchitecturePackage, object_id: str) -> DeletionImpact:
    impact = deletion_impact(package, object_id)
    if impact is None:
        raise KeyError(f"Architekturobjekt nicht gefunden: {object_id}")

    architecture_signal = package.find_architecture_signal(object_id)
    if architecture_signal:
        removed_ids = {
            architecture_signal.id,
            *(item.id for item in package.connections if item.signal_id == architecture_signal.id),
        }
        remove_signal_topology(package, architecture_signal.id)
        package.signals.remove(architecture_signal)
        _remove_traceability_targets(package, removed_ids)
        return impact

    domain = package.find_domain(object_id)
    if domain:
        element_ids = {element.id for element in domain.elements}
        removed_ids = {
            domain.id,
            *element_ids,
            *(
                item.id for item in package.connections
                if any(endpoint.element_id in element_ids for endpoint in item.endpoints)
            ),
        }
        _detach_elements(package, element_ids)
        package.domains.remove(domain)
        synchronize_all_topologies(package)
        _remove_traceability_targets(package, removed_ids)
        return impact

    element_result = package.find_element(object_id)
    if element_result:
        domain, element = element_result
        removed_ids = {
            element.id,
            *(
                item.id for item in package.connections
                if any(endpoint.element_id == element.id for endpoint in item.endpoints)
            ),
        }
        _detach_elements(package, {element.id})
        domain.elements.remove(element)
        synchronize_all_topologies(package)
        _remove_traceability_targets(package, removed_ids)
        return impact

    port_result = package.find_port(object_id)
    if port_result:
        _domain, element, port = port_result
        removed_connection_ids = {
            item.id for item in package.connections
            if any(endpoint.port_id == port.id for endpoint in item.endpoints)
        }
        generated_signal = package.find_architecture_signal(str(port.properties.get(GENERATED_SIGNAL_KEY, "")))
        if generated_signal:
            if generated_signal.source and generated_signal.source.element_id == element.id:
                generated_signal.source = None
            generated_signal.sinks = [sink for sink in generated_signal.sinks if sink.element_id != element.id]
            synchronize_signal_topology(package, generated_signal)
        else:
            package.connections = [
                connection for connection in package.connections
                if not any(endpoint.port_id == port.id for endpoint in connection.endpoints)
            ]
            element.ports.remove(port)
        _remove_traceability_targets(package, removed_connection_ids)
        return impact

    connection = next((item for item in package.connections if item.id == object_id), None)
    if connection:
        managed_signal = package.find_architecture_signal(connection.signal_id or "")
        if managed_signal:
            managed_signal.source = None
            managed_signal.sinks = []
            synchronize_signal_topology(package, managed_signal)
        else:
            package.connections.remove(connection)
        _remove_traceability_targets(package, {connection.id})
        return impact

    legacy_signal = package.find_signal(object_id)
    if legacy_signal:
        legacy_signal[2].signals.remove(legacy_signal[3])
        return impact

    bus_content = _find_bus_content_signal(package, object_id)
    if bus_content:
        bus_content[0].bus_contents.remove(bus_content[1])
        return impact

    raise KeyError(f"Architekturobjekt nicht gefunden: {object_id}")
