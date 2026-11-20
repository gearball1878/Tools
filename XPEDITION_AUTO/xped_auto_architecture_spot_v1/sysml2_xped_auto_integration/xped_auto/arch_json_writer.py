from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable

from sysml2_arch_builder.model import ArchitectureLevel, ArchitectureModel
from xped_auto.json_validator import JSONValidator


XPEDITION_ATTRIBUTES = "xpedition"
XPEDITION_UID = "uid"


def _text_id(value: Any) -> str:
    """Return a usable COM/architecture ID, rejecting empty snapshot markers."""
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none"} else text


def _com_domains(data: dict[str, Any]) -> Iterable[tuple[str, str, str, dict[str, Any]]]:
    """Decode the private in-memory result of ``gather_design_info``.

    This is deliberately not a second exchange format. The data exists only
    while the COM read is running and is immediately merged into the SPOT model.
    """
    for domain_name, raw_domain in data.items():
        if not isinstance(raw_domain, (list, tuple)) or len(raw_domain) < 3:
            yield str(domain_name), "", "", {}
            continue
        ae_map = raw_domain[2] if isinstance(raw_domain[2], dict) else {}
        yield str(domain_name), _text_id(raw_domain[0]), _text_id(raw_domain[1]), ae_map


def _set_xpedition_uid(attributes: dict[str, Any], uid: str) -> None:
    namespace = attributes.setdefault(XPEDITION_ATTRIBUTES, {})
    if not isinstance(namespace, dict):
        raise ValueError("attributes.xpedition must be an object")
    namespace[XPEDITION_UID] = uid


def _add_xpedition_net_uid(attributes: dict[str, Any], uid: str) -> None:
    """Preserve every hierarchical Xpedition instance of one architecture net."""
    namespace = attributes.setdefault(XPEDITION_ATTRIBUTES, {})
    if not isinstance(namespace, dict):
        raise ValueError("attributes.xpedition must be an object")
    uids = namespace.setdefault("uids", [])
    if not isinstance(uids, list):
        raise ValueError("attributes.xpedition.uids must be an array")
    if uid not in uids:
        uids.append(uid)


@dataclass
class BackAnnotationReport:
    """Result of merging Xpedition-owned attributes into the SPOT model."""

    annotated: dict[str, int] = field(
        default_factory=lambda: {"domains": 0, "architecture_elements": 0, "ports": 0, "nets": 0}
    )
    conflicts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"annotated": dict(self.annotated), "conflicts": list(self.conflicts)}


class BackAnnotationError(ValueError):
    """Raised when a COM object cannot be mapped to an existing SPOT object."""

    def __init__(self, report: BackAnnotationReport) -> None:
        self.report = report
        details = "\n".join(f"- {item}" for item in report.conflicts)
        super().__init__("Xpedition Back Annotation conflicts with the architecture SPOT:\n" + details)


class ArchJsonWriter:
    """Persist and back-annotate the single SysML architecture resource.

    Forward handoff::

        ArchitectureModel -> schema validation -> the SPOT JSON -> ArchJsonReader

    Reverse handoff::

        Xpedition COM -> private in-memory data -> existing objects selected
        by Architecture UID -> ``attributes.xpedition`` in the same SPOT JSON

    Xpedition never creates architecture objects or architecture IDs. A missing
    or unknown Architecture UID is a conflict and leaves the model unchanged.
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
        """Atomically replace the SPOT JSON after full validation."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n"
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary.write(payload)
                temporary_name = temporary.name
            os.replace(temporary_name, target)
        finally:
            if temporary_name and Path(temporary_name).exists():
                Path(temporary_name).unlink()
        return target

    def apply_xpedition_back_annotation(
        self,
        com_data: dict[str, Any],
        *,
        project: str | Path | None = None,
        timestamp: str | None = None,
        strict: bool = True,
    ) -> BackAnnotationReport:
        """Merge Xpedition UIDs into existing architecture objects.

        Matching is exclusively by the ``Architecture UID`` stored in
        Xpedition. Names are diagnostic context only. The operation is
        transactional: with ``strict=True`` any mismatch raises
        :class:`BackAnnotationError` without changing ``self.model``.
        """
        if not isinstance(com_data, dict):
            raise TypeError("Xpedition COM data must be an object.")

        candidate = deepcopy(self.model)
        report = BackAnnotationReport()
        block_by_id: dict[str, Any] = {}
        port_by_id: dict[str, Any] = {}
        net_objects_by_id: dict[str, list[Any]] = {}

        for block, _path in candidate.walk_blocks():
            if block.id in block_by_id:
                report.conflicts.append(f"Duplicate architecture block ID {block.id!r} in SPOT.")
            block_by_id[block.id] = block
            for port in block.ports:
                if port.id in port_by_id:
                    report.conflicts.append(f"Duplicate architecture port ID {port.id!r} in SPOT.")
                port_by_id[port.id] = port
        for connection in candidate.connections:
            net_objects_by_id.setdefault(connection.net_id, []).append(connection)
        for reference in candidate.net_references:
            net_objects_by_id.setdefault(reference.net_id, []).append(reference)

        seen: dict[str, set[str]] = {"block": set(), "port": set(), "net": set()}

        def annotate(
            kind: str,
            architecture_id: str,
            xpedition_uid: str,
            target: Any | None,
            context: str,
            count_key: str,
        ) -> None:
            if not architecture_id:
                report.conflicts.append(f"{context}: missing Architecture UID in Xpedition.")
                return
            if not xpedition_uid:
                report.conflicts.append(f"{context}: missing Xpedition COM UID.")
                return
            if architecture_id in seen[kind]:
                report.conflicts.append(f"{context}: duplicate Architecture UID {architecture_id!r} in Xpedition.")
                return
            seen[kind].add(architecture_id)
            if target is None:
                report.conflicts.append(
                    f"{context}: Architecture UID {architecture_id!r} does not exist in the SPOT resource."
                )
                return
            _set_xpedition_uid(target.attributes, xpedition_uid)
            report.annotated[count_key] += 1

        for domain_name, domain_uid, domain_arch_id, ae_map in _com_domains(com_data):
            domain = block_by_id.get(domain_arch_id)
            if domain is not None and domain.level != ArchitectureLevel.DOMAIN:
                domain = None
            annotate(
                "block", domain_arch_id, domain_uid, domain, f"Domain {domain_name!r}", "domains"
            )

            for ae_name, raw_ae in ae_map.items():
                values = raw_ae if isinstance(raw_ae, (list, tuple)) else []
                ae_uid = _text_id(values[0]) if values else ""
                ae_arch_id = _text_id(values[1]) if len(values) > 1 else ""
                ae = block_by_id.get(ae_arch_id)
                if ae is not None and ae.level != ArchitectureLevel.ARCH_ELEMENT:
                    ae = None
                annotate(
                    "block",
                    ae_arch_id,
                    ae_uid,
                    ae,
                    f"Architecture Element {domain_name}.{ae_name}",
                    "architecture_elements",
                )

                pin_container = next(
                    (item.get("Pins") for item in values if isinstance(item, dict) and "Pins" in item),
                    {},
                ) or {}
                for category, pins in pin_container.items():
                    if not isinstance(pins, dict):
                        report.conflicts.append(
                            f"Architecture Element {domain_name}.{ae_name}: invalid pin category {category!r}."
                        )
                        continue
                    for pin_name, raw_pin in pins.items():
                        pin_values = raw_pin if isinstance(raw_pin, (list, tuple)) else []
                        pin_uid = _text_id(pin_values[0]) if pin_values else ""
                        pin_arch_id = _text_id(pin_values[1]) if len(pin_values) > 1 else ""
                        annotate(
                            "port",
                            pin_arch_id,
                            pin_uid,
                            port_by_id.get(pin_arch_id),
                            f"Port {domain_name}.{ae_name}.{pin_name}",
                            "ports",
                        )

                        net_map = pin_values[2] if len(pin_values) > 2 and isinstance(pin_values[2], dict) else {}
                        for net_name, raw_net in net_map.items():
                            net_values = raw_net if isinstance(raw_net, (list, tuple)) else []
                            net_uid = _text_id(net_values[0]) if net_values else ""
                            net_arch_id = _text_id(net_values[1]) if len(net_values) > 1 else ""
                            if net_arch_id in seen["net"]:
                                # One architecture net may have several COM net
                                # instances on hierarchical Xpedition sheets.
                                targets = net_objects_by_id.get(net_arch_id, [])
                                if not net_uid:
                                    report.conflicts.append(f"Net {net_name!r}: missing Xpedition COM UID.")
                                    continue
                                for target in targets:
                                    _add_xpedition_net_uid(target.attributes, net_uid)
                                continue
                            targets = net_objects_by_id.get(net_arch_id, [])
                            if not net_arch_id:
                                report.conflicts.append(f"Net {net_name!r}: missing Architecture UID in Xpedition.")
                                continue
                            if not net_uid:
                                report.conflicts.append(f"Net {net_name!r}: missing Xpedition COM UID.")
                                continue
                            seen["net"].add(net_arch_id)
                            if not targets:
                                report.conflicts.append(
                                    f"Net {net_name!r}: Architecture UID {net_arch_id!r} does not exist in the SPOT resource."
                                )
                                continue
                            for target in targets:
                                _add_xpedition_net_uid(target.attributes, net_uid)
                            report.annotated["nets"] += 1

        if strict and report.conflicts:
            raise BackAnnotationError(report)

        annotation_time = timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        metadata = candidate.attributes.setdefault(XPEDITION_ATTRIBUTES, {})
        if not isinstance(metadata, dict):
            report.conflicts.append("$.attributes.xpedition must be an object.")
            if strict:
                raise BackAnnotationError(report)
            metadata = {}
            candidate.attributes[XPEDITION_ATTRIBUTES] = metadata
        metadata["lastBackAnnotationUtc"] = annotation_time
        if project is not None:
            metadata["project"] = str(project)

        candidate.validate()
        JSONValidator().validate_data(candidate.to_dict(), source="back-annotated architecture")
        self.model = candidate
        return report
