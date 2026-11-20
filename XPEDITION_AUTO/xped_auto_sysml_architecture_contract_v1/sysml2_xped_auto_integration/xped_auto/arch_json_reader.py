from __future__ import annotations

from pathlib import Path
from typing import Any

from sysml2_arch_builder.model import ArchitectureModel, ConnectionType, Port, PortType
from xped_auto.json_validator import ArchitectureJSONValidationError, JSONValidator


def _port_direction(port: Port) -> str:
    if port.port_type == PortType.IN:
        return "in"
    if port.port_type == PortType.OUT:
        return "out"
    if port.port_type == PortType.POWER:
        return "out" if port.attributes.get("powerDirection") == "PowerOut" else "in"
    return "inout"


def _port_category(port: Port) -> str:
    explicit = port.attributes.get("xpedPortCategory")
    if explicit in {"PowerIn", "PowerOut", "Control", "Status", "Interface", "Analog", "Undefined"}:
        return str(explicit)
    if port.port_type == PortType.IN:
        return "Control"
    if port.port_type == PortType.OUT:
        return "Status"
    if port.port_type == PortType.BIDI:
        return "Interface"
    if port.port_type == PortType.ANALOG:
        return "Analog"
    if port.port_type == PortType.POWER:
        return "PowerOut" if port.attributes.get("powerDirection") == "PowerOut" else "PowerIn"
    # Xpedition has no separate Ground block-pin category. The electrical port
    # type remains in the architecture JSON; only schematic placement uses this
    # fallback category.
    return "PowerIn"


class ArchJsonReader:
    """Read validated SysML architecture data for the schematic COM routines.

    Data handoff:

    ``Architecture GUI / ArchJsonWriter`` -> versioned architecture JSON ->
    ``JSONValidator`` -> ``ArchitectureModel`` -> query methods in this class ->
    ``auto_scheme`` COM calls.

    No Enterprise Architect or historical list-based exchange format is
    accepted. Query methods return small dictionaries keyed by the exact pin or
    net names used by the schematic placement code.
    """

    def __init__(self, source: str | Path | dict[str, Any] | ArchitectureModel) -> None:
        validator = JSONValidator()
        if isinstance(source, ArchitectureModel):
            data = source.to_dict()
            source_name = "ArchitectureModel"
            validator.validate_data(data, source=source_name)
            model = source
        elif isinstance(source, dict):
            data = source
            source_name = "in-memory architecture"
            validator.validate_data(data, source=source_name)
            model = ArchitectureModel.from_dict(data)
        elif isinstance(source, (str, Path)):
            source_path = Path(source)
            source_name = str(source_path)
            data = validator.load_and_validate(source_path)
            model = ArchitectureModel.from_dict(data)
        else:
            raise ArchitectureJSONValidationError(
                "Architecture input must be ArchitectureModel, a JSON object, or a JSON file path."
            )

        model.validate()
        self.source = source_name
        self.source_format = data["format"]
        self.data = data
        self.model = model
        self.system = model.name

        self._domains = {domain.name: domain for domain in model.blocks}
        self._aes: dict[str, dict[str, Any]] = {
            domain.name: {ae.name: ae for ae in domain.children} for domain in model.blocks
        }
        duplicate_aes: dict[str, list[str]] = {}
        for domain_name, aes in self._aes.items():
            for ae_name in aes:
                duplicate_aes.setdefault(ae_name, []).append(domain_name)
        collisions = {name: domains for name, domains in duplicate_aes.items() if len(domains) > 1}
        if collisions:
            detail = ", ".join(f"{name} ({'/'.join(domains)})" for name, domains in collisions.items())
            raise ValueError(f"Architecture element names must be globally unique for Xpedition: {detail}")

        self._nets_by_endpoint = self._build_net_index()
        self._pin_tables: dict[tuple[str, str], dict[str, dict[str, dict[str, Any]]]] = {}
        self._net_tables: dict[tuple[str, str, str], dict[str, list[Any]]] = {}
        self._build_tables()

    def _build_net_index(self) -> dict[tuple[str, str], dict[str, dict[str, Any]]]:
        nets: dict[str, dict[str, Any]] = {}

        def add_endpoint(
            net_id: str,
            name: str,
            net_type: ConnectionType,
            block_path: str,
            port_name: str,
            attributes: dict[str, Any],
        ) -> None:
            entry = nets.setdefault(
                net_id,
                {
                    "name": name,
                    "type": net_type.value,
                    "attributes": {},
                    "endpoints": [],
                },
            )
            if entry["name"] != name or entry["type"] != net_type.value:
                raise ValueError(f"Net ID {net_id!r} is used with inconsistent names or types.")
            entry["attributes"].update(attributes or {})
            endpoint = (block_path, port_name)
            if endpoint not in entry["endpoints"]:
                entry["endpoints"].append(endpoint)

        for connection in self.model.connections:
            add_endpoint(
                connection.net_id,
                connection.name,
                connection.connection_type,
                connection.source.block_path,
                connection.source.port_name,
                connection.attributes,
            )
            add_endpoint(
                connection.net_id,
                connection.name,
                connection.connection_type,
                connection.target.block_path,
                connection.target.port_name,
                connection.attributes,
            )
        for reference in self.model.net_references:
            add_endpoint(
                reference.net_id,
                reference.name,
                reference.reference_type,
                reference.end.block_path,
                reference.end.port_name,
                reference.attributes,
            )

        by_endpoint: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
        for net_id, net in nets.items():
            for endpoint in net["endpoints"]:
                by_endpoint.setdefault(endpoint, {})[net_id] = net
        return by_endpoint

    def _build_tables(self) -> None:
        for domain_name, aes in self._aes.items():
            for ae_name, ae in aes.items():
                pin_categories: dict[str, dict[str, dict[str, Any]]] = {}
                ae_path = f"{domain_name}.{ae_name}"
                for port in ae.ports:
                    category = _port_category(port)
                    pin_categories.setdefault(category, {})[port.name] = {
                        "architecture_id": port.id,
                        "xpedition_id": port.attributes.get("xpedScmId", ""),
                        "direction": _port_direction(port),
                        "category": category,
                    }
                    net_rows: dict[str, list[Any]] = {}
                    for net_id, net in self._nets_by_endpoint.get((ae_path, port.name), {}).items():
                        net_rows[net["name"]] = [
                            net["attributes"].get("xpedScmId", ""),
                            net_id,
                            net["type"],
                        ]
                    self._net_tables[(domain_name, ae_name, port.name)] = net_rows
                self._pin_tables[(domain_name, ae_name)] = pin_categories

    def _check_system(self, system: str | None) -> None:
        if system is not None and system != self.system:
            raise KeyError(f"Unknown system {system!r}; architecture contains {self.system!r}.")

    def _domain(self, system: str | None, domain: str):
        self._check_system(system)
        try:
            return self._domains[domain]
        except KeyError as exc:
            raise KeyError(f"Unknown domain {domain!r}.") from exc

    def _ae(self, system: str | None, domain: str, ae: str):
        self._domain(system, domain)
        try:
            return self._aes[domain][ae]
        except KeyError as exc:
            raise KeyError(f"Unknown architecture element {domain}.{ae}.") from exc

    def get_system_names(self) -> list[str]:
        return [self.system]

    def get_domains(self, system: str | None = None) -> dict[str, dict[str, Any]]:
        self._check_system(system)
        return {
            domain.name: {
                "architecture_id": domain.id,
                "xpedition_id": domain.attributes.get("xpedScmId", ""),
                "color": domain.color,
            }
            for domain in self.model.blocks
        }

    def get_domain_names(self, system: str | None = None) -> list[str]:
        self._check_system(system)
        return list(self._domains)

    def get_arch_id_for_domain(self, system: str | None, domain: str) -> str:
        return self._domain(system, domain).id

    def get_color_for_domain(self, system: str | None, domain: str) -> str:
        return self._domain(system, domain).color or "#FFFFFF"

    def get_ae_names_for_domain(self, system: str | None, domain: str) -> list[str]:
        self._domain(system, domain)
        return list(self._aes[domain])

    def get_arch_id_for_ae(self, system: str | None, domain: str, ae: str) -> str:
        return self._ae(system, domain, ae).id

    def get_system_function_of_ae(self, system: str | None, domain: str, ae: str) -> str:
        block = self._ae(system, domain, ae)
        return str(block.attributes.get("customerName") or block.attributes.get("systemFunction") or "")

    def get_color_of_ae(self, system: str | None, domain: str, ae: str) -> str:
        block = self._ae(system, domain, ae)
        return block.color or self._domain(system, domain).color or "#FFFFFF"

    def get_pins_for_ae(
        self,
        system: str | None,
        domain: str,
        ae: str,
    ) -> dict[str, dict[str, dict[str, Any]]]:
        self._ae(system, domain, ae)
        return {
            category: {name: values.copy() for name, values in pins.items()}
            for category, pins in self._pin_tables[(domain, ae)].items()
        }

    def get_pin_names_for_ae(self, system: str | None, domain: str, ae: str) -> list[str]:
        return [name for pins in self.get_pins_for_ae(system, domain, ae).values() for name in pins]

    def get_pins_of_type_for_ae(
        self,
        system: str | None,
        domain: str,
        ae: str,
        pin_type: str,
    ) -> dict[str, dict[str, Any]]:
        return self.get_pins_for_ae(system, domain, ae).get(pin_type, {})

    def get_pin_names_of_type_for_ae(
        self,
        system: str | None,
        domain: str,
        ae: str,
        pin_type: str,
    ) -> list[str]:
        return list(self.get_pins_of_type_for_ae(system, domain, ae, pin_type))

    def get_arch_id_for_pin_for_ae(
        self,
        system: str | None,
        domain: str,
        ae: str,
        pin: str,
    ) -> str:
        block = self._ae(system, domain, ae)
        port = block.find_port(pin)
        if port is None:
            raise KeyError(f"Unknown architecture port {domain}.{ae}.{pin}.")
        return port.id

    def get_nets_for_pin_of_ae(
        self,
        system: str | None,
        domain: str,
        ae: str,
        pin: str,
    ) -> dict[str, list[Any]]:
        self.get_arch_id_for_pin_for_ae(system, domain, ae, pin)
        return {name: values.copy() for name, values in self._net_tables[(domain, ae, pin)].items()}

    def get_net_names_for_pin_of_ae(
        self,
        system: str | None,
        domain: str,
        ae: str,
        pin: str,
    ) -> list[str]:
        return list(self.get_nets_for_pin_of_ae(system, domain, ae, pin))
