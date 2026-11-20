from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from sysml2_arch_builder.model import (
    ArchitectureModel,
    ConnectionType,
    NetReferenceDirection,
    PortType,
    stable_net_id,
    stable_ref_id,
)
from xped_auto.json_validator import JSONValidator


def _architecture_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in {"", "nan", "none"} else text


def _snapshot_domains(data: dict[str, Any]) -> Iterable[tuple[str, Any, Any, dict[str, Any]]]:
    for domain_name, raw_domain in data.items():
        domain_scm = domain_arch = None
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


def _port_type(category: str) -> tuple[PortType, dict[str, Any]]:
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
    return PortType.BIDI, attrs


class ArchJsonWriter:
    """Write the native architecture contract used by GUI, Reader and COM.

    Forward handoff: an ``ArchitectureModel`` is validated and written for
    ``ArchJsonReader``. Reverse handoff: a compact Xpedition snapshot is mapped
    back into the same model; Xpedition SCM IDs remain isolated in
    ``attributes['xpedScmId']`` while architecture IDs stay the model IDs.
    """

    def __init__(self, model: ArchitectureModel | dict[str, Any]) -> None:
        if isinstance(model, ArchitectureModel):
            self.model = model
        elif isinstance(model, dict):
            JSONValidator().validate_data(model)
            self.model = ArchitectureModel.from_dict(model)
        else:
            raise TypeError("ArchJsonWriter requires ArchitectureModel or architecture JSON data.")
        self.model.validate()

    def to_dict(self) -> dict[str, Any]:
        data = self.model.to_dict()
        JSONValidator().validate_data(data)
        return data

    def write_architecture_json(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return target

    @classmethod
    def from_xpedition_snapshot(
        cls,
        snapshot: dict[str, Any],
        *,
        architecture_name: str = "Xpedition_Import",
    ) -> "ArchJsonWriter":
        """Create architecture JSON from ``gather_design_info`` COM output."""
        if not isinstance(snapshot, dict):
            raise ValueError("Expected an Xpedition snapshot object.")

        model = ArchitectureModel(architecture_name)
        nets: dict[str, dict[str, Any]] = {}
        for domain_name, domain_scm, domain_arch, ae_map in _snapshot_domains(snapshot):
            domain = model.add_domain(domain_name)
            domain_id = _architecture_id(domain_arch)
            if domain_id:
                domain.id = domain_id
            domain.attributes["xpedScmId"] = domain_scm or ""

            for ae_name, raw_ae in ae_map.items():
                values = raw_ae if isinstance(raw_ae, list) else []
                ae_scm = values[0] if values else None
                ae_arch = _architecture_id(values[1]) if len(values) > 1 and not isinstance(values[1], dict) else None
                ae = model.add_arch_element(domain_name, str(ae_name))
                if ae_arch:
                    ae.id = str(ae_arch)
                ae.attributes["xpedScmId"] = ae_scm or ""
                if len(values) > 2 and not isinstance(values[2], dict):
                    ae.attributes["systemFunction"] = values[2]
                pin_container = next(
                    (item.get("Pins") for item in values if isinstance(item, dict) and "Pins" in item),
                    {},
                ) or {}
                component_container = next(
                    (item for item in values if isinstance(item, dict) and ("Components" in item or "Blocks" in item)),
                    None,
                )
                if component_container:
                    ae.attributes["xpedComponents"] = component_container

                ae_path = f"{domain_name}.{ae_name}"
                for category, pins in pin_container.items():
                    if not isinstance(pins, dict):
                        continue
                    for pin_name, raw_pin in pins.items():
                        pin_scm = pin_arch = None
                        net_map: dict[str, Any] = {}
                        if isinstance(raw_pin, list):
                            pin_scm = raw_pin[0] if raw_pin else None
                            pin_arch = _architecture_id(raw_pin[1]) if len(raw_pin) > 1 and not isinstance(raw_pin[1], dict) else None
                            net_map = raw_pin[2] if len(raw_pin) > 2 and isinstance(raw_pin[2], dict) else {}
                        elif isinstance(raw_pin, dict):
                            net_map = raw_pin

                        port_type, attrs = _port_type(str(category))
                        attrs["xpedScmId"] = pin_scm or ""
                        port = ae.add_port(str(pin_name), port_type, attrs)
                        if pin_arch:
                            port.id = str(pin_arch)

                        for net_name, raw_net in net_map.items():
                            net_scm = net_arch = None
                            if isinstance(raw_net, list):
                                net_scm = raw_net[0] if raw_net else None
                                net_arch = _architecture_id(raw_net[1]) if len(raw_net) > 1 else None
                            key = str(net_arch or stable_net_id(str(net_name)))
                            net = nets.setdefault(
                                key,
                                {
                                    "name": str(net_name),
                                    "type": ConnectionType.BUS if str(category) == "Interface" else ConnectionType.NET,
                                    "scm": net_scm or "",
                                    "endpoints": [],
                                },
                            )
                            endpoint = (ae_path, str(pin_name), port_type)
                            if endpoint not in net["endpoints"]:
                                net["endpoints"].append(endpoint)

        for net_id, net in nets.items():
            for block_path, port_name, port_type in net["endpoints"]:
                direction = NetReferenceDirection.BIDI
                if port_type == PortType.IN:
                    direction = NetReferenceDirection.IN
                elif port_type == PortType.OUT:
                    direction = NetReferenceDirection.OUT
                reference = model.add_net_reference(
                    net["name"],
                    net["type"],
                    block_path,
                    port_name,
                    direction,
                    {"xpedScmId": net["scm"]},
                )
                reference.id = stable_ref_id(f"{net_id}:{block_path}:{port_name}")
                reference.net_id = net_id
                reference.attributes["netId"] = net_id

        model.validate()
        return cls(model)
