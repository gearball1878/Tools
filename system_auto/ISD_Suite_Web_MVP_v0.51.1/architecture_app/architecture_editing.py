"""Validate typed architecture entry masks on a project candidate.

The UI supplies object-specific fields; JSON is the internal serialization
boundary. Existing identities, definitions and connector bindings are retained.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from .bus_content import BusContentTemplates
from .models import ArchitectureElement, ArchitecturePackage, ArchitectureSignal, Connection, Domain, InterfacePort, Signal, SignalEndpoint
from .topology import synchronize_signal_topology


def find_architecture_object(package: ArchitecturePackage, object_id: str) -> BaseModel | None:
    direct = package.find_domain(object_id)
    if direct:
        return direct
    found = package.find_element(object_id)
    if found:
        return found[1]
    found_port = package.find_port(object_id)
    if found_port:
        return found_port[2]
    found_signal = package.find_architecture_signal(object_id)
    if found_signal:
        return found_signal
    for signal in package.signals:
        for member in signal.bus_contents:
            if member.id == object_id:
                return member
    found_member = package.find_signal(object_id)
    if found_member:
        return found_member[3]
    connection = next((item for item in package.connections if item.id == object_id), None)
    if connection:
        return connection
    for field_name in ArchitecturePackage.model_fields:
        values = getattr(package, field_name)
        if isinstance(values, list):
            for item in values:
                if isinstance(item, BaseModel) and getattr(item, "id", None) == object_id:
                    return item
                # Variants and source evidence can be nested one level below
                # the main object. Their own IDs remain immutable as well.
                if isinstance(item, BaseModel):
                    for child_name in type(item).model_fields:
                        children = getattr(item, child_name)
                        if isinstance(children, list):
                            for child in children:
                                if isinstance(child, BaseModel) and getattr(child, "id", None) == object_id:
                                    return child
    return None


def object_json(package: ArchitecturePackage, object_id: str) -> str:
    obj = find_architecture_object(package, object_id)
    if obj is None:
        raise ValueError("Das Architekturobjekt existiert nicht mehr.")
    return json.dumps(obj.model_dump(mode="json"), ensure_ascii=False, indent=2)


def _immutable_ids(original: Any, edited: Any, location: str = "Objekt") -> None:
    if isinstance(original, dict) and isinstance(edited, dict):
        if "id" in original and edited.get("id") != original["id"]:
            raise ValueError(f"Die Objekt-ID von {location} darf nicht geändert werden.")
        for key in ('nativeScmUuid', 'nativeSheetName', 'kicadPinUuid', 'architectureSignalId', 'generatedBy'):
            if key in original and edited.get(key) != original[key]:
                raise ValueError(f"Die technische Zuordnung {location}.{key} ist geschützt.")
        for key in original.keys() & edited.keys():
            _immutable_ids(original[key], edited[key], f"{location}.{key}")
    elif isinstance(original, list) and isinstance(edited, list):
        if any(isinstance(item, dict) and "id" in item for item in original):
            old_ids = [item.get("id") for item in original if isinstance(item, dict)]
            new_ids = [item.get("id") for item in edited if isinstance(item, dict)]
            kept_before = [identifier for identifier in old_ids if identifier in new_ids]
            kept_after = [identifier for identifier in new_ids if identifier in old_ids]
            if kept_before != kept_after or (len(old_ids) == len(new_ids) and old_ids != new_ids):
                raise ValueError(
                    f"Die Objekt-IDs bestehender Objekte oder ihre Reihenfolge in {location} "
                    "dürfen nicht geändert werden."
                )
            existing = {item["id"]: item for item in original if isinstance(item, dict) and "id" in item}
            for index, item in enumerate(edited):
                if isinstance(item, dict) and item.get("id") in existing:
                    _immutable_ids(existing[item["id"]], item, f"{location}[{index}]")
        else:
            for index, (before, after) in enumerate(zip(original, edited)):
                _immutable_ids(before, after, f"{location}[{index}]")


def _replace_object(package: ArchitecturePackage, object_id: str, new: BaseModel) -> None:
    for index, domain in enumerate(package.domains):
        if domain.id == object_id:
            package.domains[index] = new
            return
        for element_index, element in enumerate(domain.elements):
            if element.id == object_id:
                domain.elements[element_index] = new
                return
            for port_index, port in enumerate(element.ports):
                if port.id == object_id:
                    element.ports[port_index] = new
                    return
                for member_index, member in enumerate(port.signals):
                    if member.id == object_id:
                        port.signals[member_index] = new
                        return
    for index, signal in enumerate(package.signals):
        if signal.id == object_id:
            package.signals[index] = new
            return
        for member_index, member in enumerate(signal.bus_contents):
            if member.id == object_id:
                signal.bus_contents[member_index] = new
                return
    for index, connection in enumerate(package.connections):
        if connection.id == object_id:
            package.connections[index] = new
            return
    for field_name in ArchitecturePackage.model_fields:
        values = getattr(package, field_name)
        if not isinstance(values, list):
            continue
        for index, item in enumerate(values):
            if isinstance(item, BaseModel) and getattr(item, "id", None) == object_id:
                values[index] = new
                return
            if isinstance(item, BaseModel):
                for child_name in type(item).model_fields:
                    children = getattr(item, child_name)
                    if not isinstance(children, list):
                        continue
                    for child_index, child in enumerate(children):
                        if isinstance(child, BaseModel) and getattr(child, "id", None) == object_id:
                            children[child_index] = new
                            return
    raise ValueError("Das Architekturobjekt existiert nicht mehr.")


def _reconcile_managed_port(
    package: ArchitecturePackage, old: InterfacePort, new: InterfacePort,
) -> ArchitectureSignal | None:
    signal_id = old.interface_link_id or old.properties.get("architectureSignalId")
    signal = package.find_architecture_signal(str(signal_id or ""))
    if signal is None:
        return None
    owner = package.find_port(new.id)
    if not owner:
        raise ValueError("Der bearbeitete Port hat kein Architecture Element.")
    if new.name != old.name:
        # A HW port is named after its net, including buses. Renaming a bound
        # port therefore renames the shared architecture net at every endpoint.
        signal.name = new.name
        if signal.connection_type.value == "Net" and len(signal.bus_contents) == 1:
            signal.bus_contents[0].name = new.name
        signal.properties["manualDefinitionOverride"] = True
        signal.catalog_status = "Customized"
    if new.port_type != old.port_type:
        new.properties["manualPortType"] = new.port_type
    if new.side != old.side:
        new.properties["manualSide"] = new.side
    if new.connection_type != old.connection_type:
        signal.connection_type = new.connection_type
        signal.properties["manualDefinitionOverride"] = True
        signal.catalog_status = "Customized"
    if new.role != old.role:
        raise ValueError('Die Rolle eines verbundenen Ports wird aus der Topologie abgeleitet. Host oder Teilnehmer über die Topologie ändern.')
    if new.signals != old.signals:
        new.properties["manualPortSignals"] = True
    return signal


def _reconcile_managed_connection(
    package: ArchitecturePackage, old: Connection, new: Connection,
) -> ArchitectureSignal | None:
    signal = package.find_architecture_signal(old.signal_id or "")
    if signal is None or new.signal_id != old.signal_id:
        return None
    if new.name != old.name:
        signal.name = new.name
        if signal.connection_type.value == "Net" and len(signal.bus_contents) == 1:
            signal.bus_contents[0].name = new.name
        signal.properties["manualDefinitionOverride"] = True
        signal.catalog_status = "Customized"
    signal.description = new.description
    signal.connection_type = new.connection_type
    if new.connection_type != old.connection_type:
        signal.properties["manualDefinitionOverride"] = True
        signal.catalog_status = "Customized"
    if new.endpoints != old.endpoints:
        if len(new.endpoints) < 2:
            raise ValueError("Eine Verbindung benötigt einen Host und mindestens einen Teilnehmer.")
        signal.source = SignalEndpoint(element_id=new.endpoints[0].element_id)
        signal.sinks = [SignalEndpoint(element_id=item.element_id) for item in new.endpoints[1:]]
    return signal


def update_architecture_object(
    package: ArchitecturePackage,
    object_id: str,
    document: str,
    templates: BusContentTemplates,
) -> ArchitecturePackage:
    """Return a validated new package; never mutate the caller's instance."""
    original = find_architecture_object(package, object_id)
    if original is None:
        raise ValueError("Das Architekturobjekt existiert nicht mehr.")
    try:
        edited = json.loads(document)
    except json.JSONDecodeError as error:
        raise ValueError(f"Ungültiges JSON in Zeile {error.lineno}: {error.msg}") from error
    if not isinstance(edited, dict):
        raise ValueError("Das Objekt muss ein JSON-Objekt bleiben.")
    original_data = original.model_dump(mode="json")
    if set(edited) != set(original_data):
        added = sorted(set(edited) - set(original_data))
        missing = sorted(set(original_data) - set(edited))
        raise ValueError(f"Objektfelder beibehalten. Neu: {added}; fehlend: {missing}.")
    _immutable_ids(original_data, edited)
    def protect_schema(before,after):
        if isinstance(before,dict) and isinstance(after,dict):
            for scope in ('requirement_attributes','realization_attributes'):
                if scope in before and set(before[scope]) != set(after.get(scope,{})):
                    raise ValueError('Attributdefinitionen nur im Property Manager hinzufügen oder löschen; Werte können geleert werden.')
            for key in before.keys() & after.keys():protect_schema(before[key],after[key])
        elif isinstance(before,list) and isinstance(after,list):
            index={v.get('id'):v for v in before if isinstance(v,dict) and v.get('id')}
            for v in after:
                if isinstance(v,dict) and v.get('id') in index:protect_schema(index[v['id']],v)
    protect_schema(original_data,edited)
    if isinstance(original,InterfacePort) and original.role!=edited.get('role') and (original.interface_link_id or any(any(e.port_id==original.id for e in c.endpoints) for c in package.connections)):
        raise ValueError('Die Rolle eines verbundenen Ports wird aus der Topologie abgeleitet.')
    replacement = type(original).model_validate(edited)
    working = package.model_copy(deep=True)
    _replace_object(working, object_id, replacement)
    from .traceability import project_objects,remove_deleted_references
    before={i for group in project_objects(package).values() for i in group}
    after={i for group in project_objects(working).values() for i in group}
    remove_deleted_references(working,before-after)
    # Validate references before topology materialization accesses endpoint IDs.
    ArchitecturePackage.model_validate(working.export_dict())

    if isinstance(original, ArchitectureSignal):
        signal = working.find_architecture_signal(object_id)
        assert signal is not None
        normative = {
            "name", "signal_type", "port_type", "connection_type", "bus_contents",
            "interface_definition_id", "interface_definition_version", "interface_kind",
            "instance_index", "catalog_family", "catalog_template", "catalog_status",
        }
        if any(original_data[key] != edited[key] for key in normative):
            signal.properties["manualDefinitionOverride"] = True
            if signal.catalog_status == "Bound":
                signal.catalog_status = "Customized"
        synchronize_signal_topology(working, signal, templates)
    elif isinstance(original, InterfacePort):
        managed = _reconcile_managed_port(working, original, replacement)
        if managed:
            synchronize_signal_topology(working, managed, templates)
    elif isinstance(original, (Domain, ArchitectureElement)):
        for domain in working.domains:
            for element in domain.elements:
                for port in element.ports:
                    before = package.find_port(port.id)
                    if before and before[2].model_dump(mode="json") != port.model_dump(mode="json"):
                        managed = _reconcile_managed_port(working, before[2], port)
                        if managed:
                            synchronize_signal_topology(working, managed, templates)
    elif isinstance(original, Connection):
        managed = _reconcile_managed_connection(working, original, replacement)
        if managed:
            synchronize_signal_topology(working, managed, templates)
    elif isinstance(original, Signal):
        parent = next((signal for signal in working.signals
                       if any(member.id == object_id for member in signal.bus_contents)), None)
        if parent:
            parent.properties["manualDefinitionOverride"] = True
            parent.catalog_status = "Customized"
            synchronize_signal_topology(working, parent, templates)
    # Cross-object constraints are checked after all projections have completed.
    return ArchitecturePackage.model_validate(working.export_dict())


def move_architecture_port(
    package: ArchitecturePackage,
    port_id: str,
    target_element_id: str,
    templates: BusContentTemplates,
) -> ArchitecturePackage:
    """Move a port while keeping its ID, connection references and signal topology."""
    working = package.model_copy(deep=True)
    source = working.find_port(port_id)
    target = working.find_element(target_element_id)
    if source is None or target is None:
        raise ValueError("Port oder Ziel-Architecture-Element nicht gefunden.")
    _, old_element, port = source
    if old_element.id == target_element_id:
        return working
    old_element.ports.remove(port)
    target[1].ports.append(port)
    signal = working.find_architecture_signal(
        str(port.interface_link_id or port.properties.get("architectureSignalId") or "")
    )
    if signal:
        if signal.source and signal.source.element_id == old_element.id:
            signal.source.element_id = target_element_id
        for sink in signal.sinks:
            if sink.element_id == old_element.id:
                sink.element_id = target_element_id
        synchronize_signal_topology(working, signal, templates)
    else:
        for connection in working.connections:
            for endpoint in connection.endpoints:
                if endpoint.port_id == port_id:
                    endpoint.element_id = target_element_id
    return ArchitecturePackage.model_validate(working.export_dict())


def move_architecture_element(
    package: ArchitecturePackage, element_id: str, target_domain_id: str,
) -> ArchitecturePackage:
    """Move an AE without changing its identifier or its connected ports."""
    working = package.model_copy(deep=True)
    source = working.find_element(element_id)
    target = working.find_domain(target_domain_id)
    if source is None or target is None:
        raise ValueError("Architecture Element oder Ziel-Domain nicht gefunden.")
    if source[0].id != target_domain_id:
        source[0].elements.remove(source[1])
        target.elements.append(source[1])
    return ArchitecturePackage.model_validate(working.export_dict())
