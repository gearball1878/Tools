from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
import json
import uuid

from .model import (
    ArchitectureLevel,
    ArchitectureModel,
    Block,
    ConnectionType,
    NetReferenceDirection,
    Port,
    PortType,
    stable_net_id,
    stable_ref_id,
)


BRIDGE_FORMAT = "sysml2-xped-auto-map/v1"
_GUID_NAMESPACE = uuid.UUID("0d661df2-3ef6-48c5-a138-073f048888db")


@dataclass
class ConversionReport:
    warnings: list[str] = field(default_factory=list)

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, data: Any) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _first(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def _is_guid(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        uuid.UUID(value.strip("{}"))
    except (ValueError, AttributeError):
        return False
    return True


def _guid(value: Any, kind: str, path: str) -> str:
    if _is_guid(value):
        return "{" + str(uuid.UUID(str(value).strip("{}"))).upper() + "}"
    seed = f"{kind}:{value or path}"
    return "{" + str(uuid.uuid5(_GUID_NAMESPACE, seed)).upper() + "}"


def _hex_to_xped(color: str | None) -> str:
    value = (color or "#FFFFFF").strip()
    if value.lower().startswith("0x"):
        return value
    if value.startswith("#"):
        return "0x" + value[1:].upper()
    return "0x" + value.upper()


def _xped_to_hex(color: Any) -> str:
    value = str(color or "#FFFFFF").strip()
    if value.lower().startswith("0x"):
        return "#" + value[2:].upper()
    return value if value.startswith("#") else "#" + value.upper()


def _direction_to_xped(port: Port) -> str:
    if port.port_type == PortType.IN:
        return "in"
    if port.port_type == PortType.OUT:
        return "out"
    if port.port_type == PortType.POWER:
        return "out" if port.attributes.get("powerDirection") == "PowerOut" else "in"
    return "inout"


def _category_to_xped(port: Port, report: ConversionReport) -> str:
    explicit = port.attributes.get("xpedPortCategory")
    if explicit in {"PowerIn", "PowerOut", "Control", "Status", "Interface", "Analog", "Undefined"}:
        return explicit
    if port.port_type == PortType.IN:
        return "Control"
    if port.port_type == PortType.OUT:
        return "Status"
    if port.port_type == PortType.BIDI:
        return "Interface"
    if port.port_type == PortType.POWER:
        return "PowerOut" if port.attributes.get("powerDirection") == "PowerOut" else "PowerIn"
    if port.port_type == PortType.ANALOG:
        return "Analog"
    report.warn("Ground ports are represented as PowerIn because legacy xped_auto has no Ground category.")
    return "PowerIn"


def _category_to_port_type(category: str, direction: str | None = None) -> tuple[PortType, dict[str, Any]]:
    attrs: dict[str, Any] = {"xpedPortCategory": category}
    if category == "PowerOut":
        attrs["powerDirection"] = "PowerOut"
        return PortType.POWER, attrs
    if category in {"Power", "PowerIn"}:
        attrs["powerDirection"] = "PowerIn"
        return PortType.POWER, attrs
    if category == "Control":
        return PortType.IN, attrs
    if category == "Status":
        return PortType.OUT, attrs
    if category == "Analog":
        return PortType.ANALOG, attrs
    if direction == "in":
        return PortType.IN, attrs
    if direction == "out":
        return PortType.OUT, attrs
    return PortType.BIDI, attrs


def _endpoint_index(model: ArchitectureModel) -> dict[tuple[str, str], tuple[Block, Port]]:
    result: dict[tuple[str, str], tuple[Block, Port]] = {}
    for block, path in model.walk_blocks():
        for port in block.ports:
            result[(path, port.name)] = (block, port)
    return result


def _net_groups(model: ArchitectureModel) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}

    def add(net_id: str, name: str, con_type: ConnectionType, endpoint: tuple[str, str], attrs: dict[str, Any]) -> None:
        key = net_id or stable_net_id(name)
        group = groups.setdefault(key, {"name": name, "types": set(), "endpoints": [], "attributes": {}})
        group["types"].add(con_type.value)
        if endpoint not in group["endpoints"]:
            group["endpoints"].append(endpoint)
        group["attributes"].update(attrs or {})

    for con in model.connections:
        add(con.net_id, con.name, con.connection_type, (con.source.block_path, con.source.port_name), con.attributes)
        add(con.net_id, con.name, con.connection_type, (con.target.block_path, con.target.port_name), con.attributes)
    for ref in model.net_references:
        add(ref.net_id, ref.name, ref.reference_type, (ref.end.block_path, ref.end.port_name), ref.attributes)
    return groups


def architecture_to_xped(model: ArchitectureModel) -> tuple[list[dict[str, Any]], dict[str, Any], ConversionReport]:
    """Convert a builder model to the legacy JSON contract consumed by xped_auto."""
    model.validate()
    report = ConversionReport()
    manifest: dict[str, Any] = {"format": BRIDGE_FORMAT, "model_name": model.name, "ids": {}, "nets": {}}
    endpoint_index = _endpoint_index(model)
    groups = _net_groups(model)
    endpoint_nets: dict[tuple[str, str], list[tuple[str, dict[str, Any]]]] = {}
    for net_id, group in groups.items():
        for endpoint in group["endpoints"]:
            endpoint_nets.setdefault(endpoint, []).append((net_id, group))

    def remember(guid: str, kind: str, source_id: str, path: str) -> None:
        manifest["ids"][guid] = {"kind": kind, "source_id": source_id, "path": path}

    system_arch_id = _guid(model.attributes.get("xpedArchId"), "system", model.name)
    remember(system_arch_id, "system", str(model.attributes.get("sourceId", model.name)), model.name)
    system: dict[str, Any] = {
        "System Name": model.name,
        "System Arch ID": system_arch_id,
        "System Variants": _as_list(model.attributes.get("variants")),
        "System Ports": _as_list(model.attributes.get("xpedSystemPorts")),
        "System Blocks": [],
        "System Functions": _as_list(model.attributes.get("xpedSystemFunctions")),
        "Xped Auto Bridge Format": BRIDGE_FORMAT,
    }

    for domain in model.blocks:
        if domain.level != ArchitectureLevel.DOMAIN:
            report.warn(f"Top-level block {domain.name!r} is not a domain and was skipped.")
            continue
        domain_path = domain.name
        domain_arch_id = _guid(domain.attributes.get("xpedArchId"), "domain", domain_path)
        remember(domain_arch_id, "domain", domain.id, domain_path)
        module: dict[str, Any] = {
            "Module Name": domain.name,
            "Module Arch ID": domain_arch_id,
            "Module SCM ID": domain.attributes.get("xpedScmId", ""),
            "Module Color": _hex_to_xped(domain.color),
            "Module Variants": _as_list(domain.attributes.get("variants")),
            "Module Ports": [],
            "Module Blocks": [],
            "Module Functions": _as_list(domain.attributes.get("xpedFunctions")),
            "Xped Auto Source ID": domain.id,
            "Xped Auto Source Attributes": domain.attributes,
        }
        for port in domain.ports:
            port_path = f"{domain_path}.{port.name}"
            port_arch_id = _guid(port.attributes.get("xpedArchId"), "domain-port", port_path)
            remember(port_arch_id, "domain-port", port.id, port_path)
            module["Module Ports"].append({
                "Module Port Name": port.name,
                "Module Port Arch ID": port_arch_id,
                "Module Port SCM ID": port.attributes.get("xpedScmId", ""),
                "Module Port Direction": _direction_to_xped(port),
                "Module Port Variants": _as_list(port.attributes.get("variants")),
                "Xped Auto Source ID": port.id,
                "Xped Auto Source Attributes": port.attributes,
            })

        for ae in domain.children:
            ae_path = f"{domain_path}.{ae.name}"
            ae_arch_id = _guid(ae.attributes.get("xpedArchId"), "ae", ae_path)
            remember(ae_arch_id, "ae", ae.id, ae_path)
            ae_dict: dict[str, Any] = {
                "AE Name": ae.name,
                "AE CustName": ae.attributes.get("customerName", ""),
                "AE Arch ID": ae_arch_id,
                "AE SCM ID": ae.attributes.get("xpedScmId", ""),
                "AE Color": _hex_to_xped(ae.color or domain.color),
                "AE Power Modes": _as_list(ae.attributes.get("powerModes")),
                "AE Class": ae.attributes.get("xpedClass", ae.kind),
                "AE Variants": _as_list(ae.attributes.get("variants")),
                "AE Ports": [],
                "AE Components": _as_list(ae.attributes.get("xpedComponents")),
                "AE Functions": _as_list(ae.attributes.get("xpedFunctions")),
                "Xped Auto Source ID": ae.id,
                "Xped Auto Source Attributes": ae.attributes,
            }
            for port in ae.ports:
                port_path = f"{ae_path}.{port.name}"
                port_arch_id = _guid(port.attributes.get("xpedArchId"), "ae-port", port_path)
                remember(port_arch_id, "ae-port", port.id, port_path)
                cons: list[dict[str, Any]] = []
                for net_id, net in endpoint_nets.get((ae_path, port.name), []):
                    net_guid = _guid(net["attributes"].get("xpedArchId"), "net", net_id)
                    manifest["nets"].setdefault(net_guid, {
                        "source_id": net_id,
                        "name": net["name"],
                        "endpoints": [list(item) for item in net["endpoints"]],
                    })
                    connected = []
                    for endpoint in net["endpoints"]:
                        if endpoint == (ae_path, port.name):
                            continue
                        target = endpoint_index.get(endpoint)
                        if target is None:
                            report.warn(f"Net {net['name']!r} references missing endpoint {endpoint[0]}.{endpoint[1]}.")
                            continue
                        target_block, target_port = target
                        target_kind = "domain-port" if target_block.level == ArchitectureLevel.DOMAIN else "ae-port"
                        target_arch_id = _guid(target_port.attributes.get("xpedArchId"), target_kind, f"{endpoint[0]}.{endpoint[1]}")
                        connected.append({
                            "Connected Port Arch ID": target_arch_id,
                            "Connected Port SCM ID": target_port.attributes.get("xpedScmId", ""),
                            "Connector Arch ID": net_guid,
                        })
                    cons.append({
                        "Con Name": net["name"],
                        "Connectivity": connected,
                        "Con SCM ID": net["attributes"].get("xpedScmId", ""),
                        "Con Type": "Bus" if "Bus" in net["types"] else "Net",
                        "Xped Auto Net ID": net_id,
                        "Xped Auto Signals": _as_list(net["attributes"].get("signals") or port.attributes.get("signals")),
                        "Xped Auto Source Attributes": net["attributes"],
                    })
                ae_dict["AE Ports"].append({
                    "AE Port Name": port.name,
                    "AE Port Arch ID": port_arch_id,
                    "AE Port SCM ID": port.attributes.get("xpedScmId", ""),
                    "AE Port Direction": _direction_to_xped(port),
                    "AE Port Type": _category_to_xped(port, report),
                    "AE Port Variants": _as_list(port.attributes.get("variants")),
                    "AE Port Cons": cons,
                    "Xped Auto Source ID": port.id,
                    "Xped Auto Source Type": port.port_type.value,
                    "Xped Auto Source Attributes": port.attributes,
                })
            if ae.children:
                report.warn(f"Children below architecture element {ae_path!r} are not supported by legacy xped_auto and were preserved only in attributes.")
                ae_dict["Xped Auto Nested Children"] = [child.name for child in ae.children]
            module["Module Blocks"].append(ae_dict)
        system["System Blocks"].append(module)
    return [system], manifest, report


def save_xped_exchange(model: ArchitectureModel, exchange_path: str | Path, manifest_path: str | Path | None = None) -> tuple[Path, Path, ConversionReport]:
    data, manifest, report = architecture_to_xped(model)
    exchange = _write_json(exchange_path, data)
    if manifest_path:
        mapping = Path(manifest_path)
    elif exchange.name.endswith(".xped.json"):
        mapping = exchange.with_name(exchange.name[: -len(".xped.json")] + ".xped-map.json")
    else:
        mapping = exchange.with_suffix(".xped-map.json")
    _write_json(mapping, manifest)
    return exchange, mapping, report


def _manifest_source_id(manifest: dict[str, Any] | None, guid: Any, fallback: str) -> str:
    if manifest and guid in manifest.get("ids", {}):
        return str(manifest["ids"][guid].get("source_id") or fallback)
    return fallback


def _merge_attrs(source: Any, **values: Any) -> dict[str, Any]:
    attrs = dict(source) if isinstance(source, dict) else {}
    for key, value in values.items():
        if value not in (None, "", []):
            attrs[key] = value
    return attrs


def _add_net_references(model: ArchitectureModel, nets: dict[str, dict[str, Any]]) -> None:
    for key, net in nets.items():
        name = net["name"]
        net_id = str(net.get("source_id") or stable_net_id(name))
        con_type = ConnectionType.BUS if net.get("type") == "Bus" else ConnectionType.NET
        for block_path, port_name, direction, attrs in net["endpoints"]:
            ref_attrs = _merge_attrs(attrs, xpedArchId=net.get("arch_id"), xpedScmId=net.get("scm_id"), signals=net.get("signals", []))
            ref = model.add_net_reference(name, con_type, block_path, port_name, direction, ref_attrs)
            ref.id = stable_ref_id(f"{key}:{block_path}:{port_name}")
            ref.net_id = net_id
            ref.attributes["netId"] = net_id


def legacy_exchange_to_architecture(data: list[dict[str, Any]], manifest: dict[str, Any] | None = None) -> tuple[ArchitectureModel, ConversionReport]:
    """Convert the EA/Xpedition exchange contract back to the builder model."""
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise ValueError("Expected the legacy Xpedition exchange format (non-empty JSON array).")
    report = ConversionReport()
    if len(data) > 1:
        report.warn("The builder supports one system; only the first exchange system was imported.")
    system = data[0]
    model = ArchitectureModel(str(system.get("System Name") or "Imported_Architecture"))
    model.attributes = {
        "xpedArchId": system.get("System Arch ID", ""),
        "variants": _as_list(system.get("System Variants")),
        "xpedSystemPorts": _as_list(system.get("System Ports")),
        "xpedSystemFunctions": _as_list(system.get("System Functions")),
    }
    nets: dict[str, dict[str, Any]] = {}
    for module in _as_list(system.get("System Blocks")):
        if not isinstance(module, dict):
            continue
        name = str(module.get("Module Name") or "Domain")
        domain = model.add_domain(name)
        domain.id = _manifest_source_id(manifest, module.get("Module Arch ID"), str(module.get("Xped Auto Source ID") or domain.id))
        domain.color = _xped_to_hex(module.get("Module Color"))
        domain.attributes = _merge_attrs(
            module.get("Xped Auto Source Attributes"),
            domainColor=domain.color,
            xpedArchId=module.get("Module Arch ID"),
            xpedScmId=module.get("Module SCM ID"),
            variants=_as_list(module.get("Module Variants")),
            xpedFunctions=_as_list(module.get("Module Functions")),
        )
        for item in _as_list(module.get("Module Ports")):
            if not isinstance(item, dict):
                continue
            ptype, attrs = _category_to_port_type("Interface", item.get("Module Port Direction"))
            attrs = _merge_attrs(item.get("Xped Auto Source Attributes"), **attrs, xpedArchId=item.get("Module Port Arch ID"), xpedScmId=item.get("Module Port SCM ID"), variants=_as_list(item.get("Module Port Variants")))
            port = domain.add_port(str(item.get("Module Port Name") or "Port"), ptype, attrs)
            port.id = _manifest_source_id(manifest, item.get("Module Port Arch ID"), str(item.get("Xped Auto Source ID") or port.id))

        for item in _as_list(module.get("Module Blocks")):
            if not isinstance(item, dict):
                continue
            ae_name = str(item.get("AE Name") or "ArchitectureElement")
            ae = model.add_arch_element(domain.name, ae_name, str(item.get("AE Class") or "ArchitectureElement"))
            ae.id = _manifest_source_id(manifest, item.get("AE Arch ID"), str(item.get("Xped Auto Source ID") or ae.id))
            ae.color = _xped_to_hex(item.get("AE Color") or domain.color)
            ae.attributes = _merge_attrs(
                item.get("Xped Auto Source Attributes"),
                domainColor=ae.color,
                customerName=item.get("AE CustName"),
                xpedArchId=item.get("AE Arch ID"),
                xpedScmId=item.get("AE SCM ID"),
                powerModes=_as_list(item.get("AE Power Modes")),
                xpedClass=item.get("AE Class"),
                variants=_as_list(item.get("AE Variants")),
                xpedComponents=_as_list(item.get("AE Components")),
                xpedFunctions=_as_list(item.get("AE Functions")),
            )
            ae_path = f"{domain.name}.{ae.name}"
            for pitem in _as_list(item.get("AE Ports")):
                if not isinstance(pitem, dict):
                    continue
                category = str(pitem.get("AE Port Type") or "Interface")
                ptype, generated_attrs = _category_to_port_type(category, pitem.get("AE Port Direction"))
                source_type = pitem.get("Xped Auto Source Type")
                if source_type:
                    try:
                        ptype = PortType(source_type)
                    except ValueError:
                        report.warn(f"Unknown source port type {source_type!r} on {ae_path}.")
                attrs = _merge_attrs(
                    pitem.get("Xped Auto Source Attributes"),
                    **generated_attrs,
                    xpedArchId=pitem.get("AE Port Arch ID"),
                    xpedScmId=pitem.get("AE Port SCM ID"),
                    variants=_as_list(pitem.get("AE Port Variants")),
                )
                port_name = str(pitem.get("AE Port Name") or "Port")
                port = ae.add_port(port_name, ptype, attrs)
                port.id = _manifest_source_id(manifest, pitem.get("AE Port Arch ID"), str(pitem.get("Xped Auto Source ID") or port.id))
                for con in _as_list(pitem.get("AE Port Cons")):
                    if not isinstance(con, dict):
                        continue
                    con_name = str(con.get("Con Name") or "NoNet")
                    con_type = str(con.get("Con Type") or "Net")
                    arch_ids = [entry.get("Connector Arch ID") for entry in _as_list(con.get("Connectivity")) if isinstance(entry, dict) and entry.get("Connector Arch ID")]
                    arch_id = arch_ids[0] if arch_ids else None
                    key = str(arch_id or con.get("Xped Auto Net ID") or f"{con_type}:{con_name}")
                    mapped = manifest.get("nets", {}).get(arch_id, {}) if manifest and arch_id else {}
                    net = nets.setdefault(key, {
                        "name": con_name,
                        "type": con_type,
                        "arch_id": arch_id,
                        "scm_id": con.get("Con SCM ID"),
                        "source_id": mapped.get("source_id") or con.get("Xped Auto Net ID"),
                        "signals": _as_list(con.get("Xped Auto Signals")),
                        "endpoints": [],
                    })
                    direction = NetReferenceDirection.BIDI
                    raw_direction = pitem.get("AE Port Direction")
                    if raw_direction == "in":
                        direction = NetReferenceDirection.IN
                    elif raw_direction == "out":
                        direction = NetReferenceDirection.OUT
                    endpoint = (ae_path, port_name, direction, con.get("Xped Auto Source Attributes") or {})
                    if endpoint not in net["endpoints"]:
                        net["endpoints"].append(endpoint)
    _add_net_references(model, nets)
    model.validate()
    return model, report


def _snapshot_domains(data: dict[str, Any]) -> Iterable[tuple[str, Any, Any, dict[str, Any]]]:
    for domain_name, raw_domain in data.items():
        domain_scm = None
        domain_arch = None
        ae_map: dict[str, Any] = {}
        if isinstance(raw_domain, list) and len(raw_domain) >= 3 and isinstance(raw_domain[2], dict):
            domain_scm, domain_arch, ae_map = raw_domain[0], raw_domain[1], raw_domain[2]
        elif isinstance(raw_domain, list):
            for item in raw_domain:
                if isinstance(item, dict):
                    ae_map.update(item)
        elif isinstance(raw_domain, dict):
            ae_map = raw_domain
        yield str(domain_name), domain_scm, domain_arch, ae_map


def xped_snapshot_to_architecture(data: dict[str, Any], system_name: str = "Xpedition_Import", manifest: dict[str, Any] | None = None) -> tuple[ArchitectureModel, ConversionReport]:
    """Import the compact JSON produced by legacy gather_design_info.py."""
    if not isinstance(data, dict):
        raise ValueError("Expected an Xpedition design snapshot JSON object.")
    report = ConversionReport()
    model = ArchitectureModel(system_name)
    nets: dict[str, dict[str, Any]] = {}
    for domain_name, domain_scm, domain_arch, ae_map in _snapshot_domains(data):
        domain = model.add_domain(domain_name)
        domain.id = _manifest_source_id(manifest, domain_arch, domain.id)
        domain.attributes.update({"xpedScmId": domain_scm or "", "xpedArchId": domain_arch or ""})
        for ae_name, raw_ae in ae_map.items():
            values = raw_ae if isinstance(raw_ae, list) else []
            ae_scm = values[0] if values else None
            ae_arch = values[1] if len(values) > 1 and _is_guid(values[1]) else None
            ae = model.add_arch_element(domain_name, str(ae_name))
            ae.id = _manifest_source_id(manifest, ae_arch, ae.id)
            ae.attributes.update({"xpedScmId": ae_scm or "", "xpedArchId": ae_arch or ""})
            if len(values) > 2 and not isinstance(values[2], dict):
                ae.attributes["systemFunction"] = values[2]
            elif len(values) > 1 and not isinstance(values[1], dict) and not _is_guid(values[1]):
                ae.attributes["systemFunction"] = values[1]
            pin_container = next((item.get("Pins") for item in values if isinstance(item, dict) and "Pins" in item), {}) or {}
            component_container = next((item for item in values if isinstance(item, dict) and ("Components" in item or "Blocks" in item)), {})
            if component_container:
                ae.attributes["xpedComponents"] = component_container
            ae_path = f"{domain_name}.{ae_name}"
            for category, pins in pin_container.items():
                if not isinstance(pins, dict):
                    continue
                for pin_name, raw_pin in pins.items():
                    pin_scm = pin_arch = None
                    net_map: dict[str, Any] = {}
                    if isinstance(raw_pin, list) and len(raw_pin) >= 3 and isinstance(raw_pin[2], dict):
                        pin_scm, pin_arch, net_map = raw_pin[0], raw_pin[1], raw_pin[2]
                    elif isinstance(raw_pin, dict):
                        net_map = raw_pin
                    ptype, attrs = _category_to_port_type(str(category))
                    attrs.update({"xpedScmId": pin_scm or "", "xpedArchId": pin_arch or ""})
                    port = ae.add_port(str(pin_name), ptype, attrs)
                    port.id = _manifest_source_id(manifest, pin_arch, port.id)
                    for net_name, raw_net in net_map.items():
                        net_scm = net_arch = None
                        if isinstance(raw_net, list):
                            net_scm = raw_net[0] if raw_net else None
                            net_arch = raw_net[1] if len(raw_net) > 1 and _is_guid(raw_net[1]) else None
                        key = str(net_arch or net_name)
                        mapped = manifest.get("nets", {}).get(net_arch, {}) if manifest and net_arch else {}
                        net = nets.setdefault(key, {
                            "name": str(net_name),
                            "type": "Bus" if str(category) == "Interface" else "Net",
                            "arch_id": net_arch,
                            "scm_id": net_scm,
                            "source_id": mapped.get("source_id"),
                            "signals": [],
                            "endpoints": [],
                        })
                        direction = NetReferenceDirection.BIDI
                        if ptype == PortType.IN:
                            direction = NetReferenceDirection.IN
                        elif ptype == PortType.OUT:
                            direction = NetReferenceDirection.OUT
                        net["endpoints"].append((ae_path, str(pin_name), direction, {}))
    _add_net_references(model, nets)
    model.validate()
    return model, report


def load_xped_json(path: str | Path, manifest_path: str | Path | None = None, system_name: str | None = None) -> tuple[ArchitectureModel, ConversionReport]:
    data = _read_json(path)
    manifest = _read_json(manifest_path) if manifest_path and Path(manifest_path).exists() else None
    if isinstance(data, list):
        return legacy_exchange_to_architecture(data, manifest)
    return xped_snapshot_to_architecture(data, system_name or Path(path).stem, manifest)


def validate_xped_exchange(data: Any) -> list[str]:
    """Small dependency-free structural validation for generated exchange JSON."""
    errors: list[str] = []
    if not isinstance(data, list) or not data:
        return ["root must be a non-empty array"]
    for si, system in enumerate(data):
        if not isinstance(system, dict):
            errors.append(f"system[{si}] must be an object")
            continue
        for field_name in ("System Name", "System Blocks", "System Ports", "System Functions"):
            if field_name not in system:
                errors.append(f"system[{si}] is missing {field_name}")
        for mi, module in enumerate(_as_list(system.get("System Blocks"))):
            if not isinstance(module, dict) or not module.get("Module Name"):
                errors.append(f"system[{si}].modules[{mi}] has no Module Name")
                continue
            for ai, ae in enumerate(_as_list(module.get("Module Blocks"))):
                if not isinstance(ae, dict) or not ae.get("AE Name"):
                    errors.append(f"system[{si}].modules[{mi}].aes[{ai}] has no AE Name")
                    continue
                for pi, port in enumerate(_as_list(ae.get("AE Ports"))):
                    if not isinstance(port, dict) or not port.get("AE Port Name"):
                        errors.append(f"system[{si}].modules[{mi}].aes[{ai}].ports[{pi}] has no AE Port Name")
                    elif port.get("AE Port Direction") not in {"in", "out", "inout"}:
                        errors.append(f"port {port.get('AE Port Name')} has invalid direction")
    return errors
