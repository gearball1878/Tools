from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import json
import uuid


class ArchitectureLevel(str, Enum):
    DOMAIN = "Level1_Domain"
    ARCH_ELEMENT = "Level2_ArchitectureElement"


class PortType(str, Enum):
    IN = "In"
    OUT = "Out"
    BIDI = "Bidi"
    POWER = "Power"
    GROUND = "Ground"
    ANALOG = "Analog"


class ConnectionType(str, Enum):
    NET = "Net"
    BUS = "Bus"


class NetReferenceDirection(str, Enum):
    IN = "In"
    OUT = "Out"
    BIDI = "Bidi"


class PortSide(str, Enum):
    AUTO = "Auto"
    LEFT = "Left"
    RIGHT = "Right"


class PowerDirection(str, Enum):
    IN = "PowerIn"
    OUT = "PowerOut"


def make_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


def stable_net_id(name: str) -> str:
    return f"NET-{uuid.uuid5(uuid.NAMESPACE_DNS, name).hex[:10].upper()}"


def stable_ref_id(name: str) -> str:
    return f"REF-{uuid.uuid5(uuid.NAMESPACE_URL, name).hex[:10].upper()}"


@dataclass
class Port:
    name: str
    port_type: PortType
    id: str = field(default_factory=lambda: make_id("PRT"))
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Block:
    name: str
    level: ArchitectureLevel
    id: str = field(default_factory=lambda: make_id("BLK"))
    kind: str = "GenericBlock"
    is_host: bool = False
    color: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    ports: list[Port] = field(default_factory=list)
    children: list["Block"] = field(default_factory=list)

    def add_port(self, name: str, port_type: PortType, attributes: dict[str, Any] | None = None) -> Port:
        existing = self.find_port(name)
        if existing:
            existing.port_type = port_type
            if attributes:
                existing.attributes.update(attributes)
            return existing
        port = Port(name=name, port_type=port_type, attributes=attributes or {})
        self.ports.append(port)
        return port

    def find_port(self, name: str) -> Optional[Port]:
        for p in self.ports:
            if p.name == name:
                return p
        return None

    def remove_port(self, port_name: str) -> None:
        self.ports = [p for p in self.ports if p.name != port_name]


@dataclass
class ConnectionEnd:
    block_path: str
    port_name: str


@dataclass
class Connection:
    name: str
    connection_type: ConnectionType
    source: ConnectionEnd
    target: ConnectionEnd
    id: str = field(default_factory=lambda: make_id("CON"))
    net_id: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class NetReference:
    name: str
    reference_type: ConnectionType
    end: ConnectionEnd
    direction: NetReferenceDirection = NetReferenceDirection.BIDI
    id: str = field(default_factory=lambda: make_id("REF"))
    net_id: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArchitectureModel:
    name: str = "Generic_Architecture"
    blocks: list[Block] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)
    net_references: list[NetReference] = field(default_factory=list)

    def unique_port_name(self, block_path: str, base_name: str) -> str:
        block = self.find_block(block_path)
        if block is None:
            raise ValueError(f"Block not found: {block_path}")
        existing = {p.name for p in block.ports}
        if base_name not in existing:
            return base_name
        idx = 1
        while True:
            candidate = f"{base_name}_COPY" if idx == 1 else f"{base_name}_COPY_{idx}"
            if candidate not in existing:
                return candidate
            idx += 1

    def unique_net_reference_name(self, block_path: str, base_name: str) -> str:
        existing = {r.name for r in self.net_references if r.end.block_path == block_path}
        if base_name not in existing:
            return base_name
        idx = 1
        while True:
            candidate = f"{base_name}_COPY" if idx == 1 else f"{base_name}_COPY_{idx}"
            if candidate not in existing:
                return candidate
            idx += 1

    def add_domain(self, name: str, kind: str = "Domain") -> Block:
        if any(b.name == name for b in self.blocks):
            raise ValueError(f"Domain already exists: {name}")
        color = self.domain_color(name)
        block = Block(name=name, level=ArchitectureLevel.DOMAIN, kind=kind, color=color)
        block.attributes["domainColor"] = color
        self.blocks.append(block)
        return block

    def add_arch_element(self, domain_path: str, name: str, kind: str = "ArchitectureElement") -> Block:
        domain = self.find_block(domain_path)
        if domain is None or domain.level != ArchitectureLevel.DOMAIN:
            raise ValueError("Architecture elements can only be added below a Level-1 domain")
        if any(c.name == name for c in domain.children):
            raise ValueError(f"Architecture element already exists below {domain_path}: {name}")
        block = Block(name=name, level=ArchitectureLevel.ARCH_ELEMENT, kind=kind, color=domain.color)
        block.attributes["domainColor"] = domain.color
        domain.children.append(block)
        return block

    def add_connection(self, name: str, connection_type: ConnectionType, source_block_path: str, source_port_name: str, target_block_path: str, target_port_name: str, attributes: dict[str, Any] | None = None) -> Connection:
        source_port = self.require_port(source_block_path, source_port_name)
        target_port = self.require_port(target_block_path, target_port_name)
        self._validate_connection_direction(source_port.port_type, target_port.port_type)
        con = Connection(
            name=name,
            connection_type=connection_type,
            source=ConnectionEnd(source_block_path, source_port_name),
            target=ConnectionEnd(target_block_path, target_port_name),
            net_id=stable_net_id(name),
            attributes=attributes or {},
        )
        con.attributes.setdefault("netId", con.net_id)
        self.connections.append(con)
        return con

    def has_net_reference_on_block(self, block_path: str, name: str) -> bool:
        return any(r.end.block_path == block_path and r.name == name for r in self.net_references)

    def add_net_reference(self, name: str, reference_type: ConnectionType, block_path: str, port_name: str, direction: NetReferenceDirection = NetReferenceDirection.BIDI, attributes: dict[str, Any] | None = None) -> NetReference:
        self.require_port(block_path, port_name)
        ref = NetReference(
            name=name,
            reference_type=reference_type,
            end=ConnectionEnd(block_path, port_name),
            direction=direction,
            id=stable_ref_id(name),
            net_id=stable_net_id(name),
            attributes=attributes or {},
        )
        ref.attributes.setdefault("netId", ref.net_id)
        self.net_references.append(ref)
        return ref

    def add_interface_reference(self, block_path: str, interface_name: str, connection_type: ConnectionType, direction: NetReferenceDirection, signals: list[str], port_type: PortType | None = None, extra_attributes: dict[str, Any] | None = None) -> tuple[Port, NetReference]:
        block = self.find_block(block_path)
        if block is None:
            raise ValueError(f"Block not found: {block_path}")
        attrs = extra_attributes or {}
        if port_type is None:
            port_type = self.infer_port_type(interface_name, connection_type, direction, signals, block.is_host, attrs)

        full_attrs = {
            "interfaceName": interface_name,
            "connectionType": connection_type.value,
            "signals": signals,
            "ecadSignals": signals,
            "generatedBy": "BusContentWizard",
            "netId": stable_net_id(interface_name),
        }
        full_attrs.update(attrs)

        if port_type == PortType.POWER:
            full_attrs.setdefault("powerDirection", PowerDirection.OUT.value if direction == NetReferenceDirection.OUT else PowerDirection.IN.value)

        port = block.add_port(interface_name, port_type, full_attrs)
        ref = self.add_net_reference(interface_name, connection_type, block_path, port.name, direction, full_attrs.copy())
        return port, ref

    def remove_connection(self, connection_id: str) -> None:
        self.connections = [c for c in self.connections if c.id != connection_id]

    def remove_net_reference(self, reference_id: str) -> None:
        self.net_references = [r for r in self.net_references if r.id != reference_id]

    def rename_net_reference(self, reference_id: str, new_name: str) -> None:
        for r in self.net_references:
            if r.id == reference_id:
                old_port = r.end.port_name
                block = self.find_block(r.end.block_path)
                r.name = new_name
                r.id = stable_ref_id(new_name)
                r.net_id = stable_net_id(new_name)
                r.attributes["netId"] = r.net_id
                r.attributes["interfaceName"] = new_name
                if block and block.find_port(old_port):
                    p = block.find_port(old_port)
                    p.name = new_name
                    p.attributes.update(r.attributes)
                r.end.port_name = new_name
                return
        raise ValueError(f"Net reference not found: {reference_id}")

    def set_net_reference_propagation(self, reference_id: str, propagate: bool) -> None:
        for r in self.net_references:
            if r.id == reference_id:
                r.attributes["propagateToParent"] = bool(propagate)
                # Keep corresponding port metadata synchronized.
                block = self.find_block(r.end.block_path)
                if block:
                    port = block.find_port(r.end.port_name)
                    if port:
                        port.attributes["propagateToParent"] = bool(propagate)
                return
        raise ValueError(f"Net reference not found: {reference_id}")

    def set_port_propagation(self, block_path: str, port_name: str, propagate: bool) -> None:
        """
        Bottom-up only: mark all net references connected to a given port for
        propagation to the parent/domain representation.
        """
        block = self.find_block(block_path)
        if block is None:
            raise ValueError(f"Block not found: {block_path}")

        port = block.find_port(port_name)
        if port is None:
            raise ValueError(f"Port not found: {block_path}.{port_name}")

        port.attributes["propagateToParent"] = bool(propagate)

        for ref in self.net_references:
            if ref.end.block_path == block_path and ref.end.port_name == port_name:
                ref.attributes["propagateToParent"] = bool(propagate)

    def set_net_reference_propagation_by_port(self, block_path: str, port_name: str, propagate: bool) -> None:
        self.set_port_propagation(block_path, port_name, propagate)

    def rename_block(self, block_path: str, new_name: str) -> str:
        block = self.find_block(block_path)
        if block is None:
            raise ValueError(f"Block not found: {block_path}")
        old_path = block_path
        block.name = new_name
        new_path = self._path_for_block(block)
        def update_path(path: str) -> str:
            if path == old_path:
                return new_path
            if path.startswith(old_path + "."):
                return new_path + path[len(old_path):]
            return path
        for con in self.connections:
            con.source.block_path = update_path(con.source.block_path)
            con.target.block_path = update_path(con.target.block_path)
        for ref in self.net_references:
            ref.end.block_path = update_path(ref.end.block_path)
        return new_path

    def rename_port(self, block_path: str, old_name: str, new_name: str) -> None:
        block = self.find_block(block_path)
        if not block:
            raise ValueError(f"Block not found: {block_path}")
        port = block.find_port(old_name)
        if not port:
            raise ValueError(f"Port not found: {old_name}")
        port.name = new_name
        for con in self.connections:
            if con.source.block_path == block_path and con.source.port_name == old_name:
                con.source.port_name = new_name
            if con.target.block_path == block_path and con.target.port_name == old_name:
                con.target.port_name = new_name
        for ref in self.net_references:
            if ref.end.block_path == block_path and ref.end.port_name == old_name:
                ref.end.port_name = new_name
                ref.name = new_name
                ref.net_id = stable_net_id(new_name)

    def copy_port(self, block_path: str, port_name: str, new_name: str | None = None) -> Port:
        import copy
        block = self.find_block(block_path)
        if block is None:
            raise ValueError(f"Block not found: {block_path}")
        port = block.find_port(port_name)
        if port is None:
            raise ValueError(f"Port not found: {block_path}.{port_name}")

        copied_name = new_name or self.unique_port_name(block_path, port.name)
        new_port = block.add_port(copied_name, port.port_type, copy.deepcopy(port.attributes))
        new_port.attributes["copiedFrom"] = port.name

        # Duplicate one-sided references attached to the original port, if any.
        for ref in list(self.net_references):
            if ref.end.block_path == block_path and ref.end.port_name == port_name:
                ref_name = self.unique_net_reference_name(block_path, copied_name)
                attrs = copy.deepcopy(ref.attributes)
                attrs["copiedFrom"] = ref.name
                self.add_net_reference(ref_name, ref.reference_type, block_path, copied_name, ref.direction, attrs)
        return new_port

    def copy_net_reference(self, reference_id: str, new_name: str | None = None) -> NetReference:
        import copy
        original = None
        for ref in self.net_references:
            if ref.id == reference_id:
                original = ref
                break
        if original is None:
            raise ValueError(f"Net reference not found: {reference_id}")

        block = self.find_block(original.end.block_path)
        if block is None:
            raise ValueError(f"Block not found: {original.end.block_path}")

        copied_name = new_name or self.unique_net_reference_name(original.end.block_path, original.name)
        port_name = copied_name
        if block.find_port(port_name):
            port_name = self.unique_port_name(original.end.block_path, port_name)

        src_port = block.find_port(original.end.port_name)
        attrs = copy.deepcopy(original.attributes)
        attrs["copiedFrom"] = original.name

        # Create corresponding port if needed.
        port_type = src_port.port_type if src_port else self.infer_port_type(
            copied_name, original.reference_type, original.direction, attrs.get("signals", []), block.is_host, attrs
        )
        block.add_port(port_name, port_type, copy.deepcopy(attrs))

        return self.add_net_reference(
            copied_name,
            original.reference_type,
            original.end.block_path,
            port_name,
            original.direction,
            attrs,
        )

    def copy_port_to_block(self, block_path: str, port_name: str, target_block_path: str, preserve_name: bool = True) -> Port:
        """
        Copy a port to another block. If preserve_name=True and the target does not
        already contain that port name, the original name is kept. This is intended
        for fast connection of the same bus/net reference to multiple blocks.
        """
        import copy
        source_block = self.find_block(block_path)
        target_block = self.find_block(target_block_path)
        if source_block is None:
            raise ValueError(f"Source block not found: {block_path}")
        if target_block is None:
            raise ValueError(f"Target block not found: {target_block_path}")

        port = source_block.find_port(port_name)
        if port is None:
            raise ValueError(f"Port not found: {block_path}.{port_name}")

        if preserve_name and not target_block.find_port(port.name):
            copied_name = port.name
        else:
            copied_name = self.unique_port_name(target_block_path, port.name)

        new_port = target_block.add_port(copied_name, port.port_type, copy.deepcopy(port.attributes))
        new_port.attributes["copiedFrom"] = f"{block_path}.{port_name}"

        # Copy all net references attached to the source port. If the target is a
        # different block, keep the same net/reference name unless the target block
        # already has that same reference name.
        for ref in list(self.net_references):
            if ref.end.block_path == block_path and ref.end.port_name == port_name:
                if preserve_name and not self.has_net_reference_on_block(target_block_path, ref.name):
                    ref_name = ref.name
                else:
                    ref_name = self.unique_net_reference_name(target_block_path, ref.name)
                attrs = copy.deepcopy(ref.attributes)
                attrs["copiedFrom"] = ref.name
                self.add_net_reference(ref_name, ref.reference_type, target_block_path, copied_name, ref.direction, attrs)

        return new_port

    def copy_net_reference_to_block(self, reference_id: str, target_block_path: str, preserve_name: bool = True) -> NetReference:
        """
        Copy/connect a net reference to another block. By default, the same reference
        name is preserved on the target if possible, so equal names keep the same
        netId/refId globally and act as a fast connection mechanism.
        """
        import copy
        original = None
        for ref in self.net_references:
            if ref.id == reference_id:
                original = ref
                break
        if original is None:
            raise ValueError(f"Net reference not found: {reference_id}")

        target_block = self.find_block(target_block_path)
        if target_block is None:
            raise ValueError(f"Target block not found: {target_block_path}")

        if preserve_name and not self.has_net_reference_on_block(target_block_path, original.name):
            ref_name = original.name
        else:
            ref_name = self.unique_net_reference_name(target_block_path, original.name)

        # The corresponding port should use the same name as the architectural
        # net/reference where possible.
        if preserve_name and not target_block.find_port(ref_name):
            port_name = ref_name
        else:
            port_name = self.unique_port_name(target_block_path, ref_name)

        src_block = self.find_block(original.end.block_path)
        src_port = src_block.find_port(original.end.port_name) if src_block else None
        attrs = copy.deepcopy(original.attributes)
        attrs["copiedFrom"] = original.name

        port_type = src_port.port_type if src_port else self.infer_port_type(
            ref_name, original.reference_type, original.direction, attrs.get("signals", []), target_block.is_host, attrs
        )
        target_block.add_port(port_name, port_type, copy.deepcopy(attrs))

        return self.add_net_reference(
            ref_name,
            original.reference_type,
            target_block_path,
            port_name,
            original.direction,
            attrs,
        )

    def move_block(self, block_path: str, new_parent_path: str | None) -> str:
        block = self.find_block(block_path)
        if block is None:
            raise ValueError(f"Block not found: {block_path}")
        if block.level == ArchitectureLevel.DOMAIN:
            raise ValueError("Domain blocks cannot be moved below another object.")

        new_parent = self.find_block(new_parent_path) if new_parent_path else None
        if new_parent is None or new_parent.level != ArchitectureLevel.DOMAIN:
            raise ValueError("Architecture elements can only be moved below a domain.")

        old_path = block_path
        old_parent_path, _ = block_path.rsplit(".", 1)
        old_parent = self.find_block(old_parent_path)
        if old_parent is None:
            raise ValueError(f"Old parent not found: {old_parent_path}")
        if any(c.name == block.name and c is not block for c in new_parent.children):
            raise ValueError(f"Target domain already contains a block named {block.name}")

        old_parent.children = [c for c in old_parent.children if c is not block]
        block.color = new_parent.color
        block.attributes["domainColor"] = new_parent.color
        new_parent.children.append(block)
        new_path = f"{new_parent_path}.{block.name}"

        def update_path(path: str) -> str:
            if path == old_path:
                return new_path
            if path.startswith(old_path + "."):
                return new_path + path[len(old_path):]
            return path

        for con in self.connections:
            con.source.block_path = update_path(con.source.block_path)
            con.target.block_path = update_path(con.target.block_path)
        for ref in self.net_references:
            ref.end.block_path = update_path(ref.end.block_path)
        return new_path

    def move_port(self, block_path: str, port_name: str, target_block_path: str) -> None:
        source_block = self.find_block(block_path)
        target_block = self.find_block(target_block_path)
        if source_block is None:
            raise ValueError(f"Source block not found: {block_path}")
        if target_block is None:
            raise ValueError(f"Target block not found: {target_block_path}")
        port = source_block.find_port(port_name)
        if port is None:
            raise ValueError(f"Port not found: {block_path}.{port_name}")
        if target_block.find_port(port_name):
            raise ValueError(f"Target block already has a port named {port_name}")
        source_block.ports = [p for p in source_block.ports if p is not port]
        target_block.ports.append(port)
        for con in self.connections:
            if con.source.block_path == block_path and con.source.port_name == port_name:
                con.source.block_path = target_block_path
            if con.target.block_path == block_path and con.target.port_name == port_name:
                con.target.block_path = target_block_path
        for ref in self.net_references:
            if ref.end.block_path == block_path and ref.end.port_name == port_name:
                ref.end.block_path = target_block_path

    def remove_block(self, block_path: str) -> None:
        if "." not in block_path:
            self.blocks = [b for b in self.blocks if b.name != block_path]
        else:
            parent_path, name = block_path.rsplit(".", 1)
            parent = self.find_block(parent_path)
            if parent:
                parent.children = [c for c in parent.children if c.name != name]
        self.connections = [c for c in self.connections if not c.source.block_path.startswith(block_path) and not c.target.block_path.startswith(block_path)]
        self.net_references = [r for r in self.net_references if not r.end.block_path.startswith(block_path)]

    def walk_blocks(self):
        def walk(block: Block, prefix: str):
            path = f"{prefix}.{block.name}" if prefix else block.name
            yield block, path
            for child in block.children:
                yield from walk(child, path)
        for b in self.blocks:
            yield from walk(b, "")

    def find_block(self, block_path: str) -> Optional[Block]:
        for block, path in self.walk_blocks():
            if path == block_path:
                return block
        return None

    def _path_for_block(self, target: Block) -> str:
        for block, path in self.walk_blocks():
            if block is target:
                return path
        raise ValueError("Block is not part of this model")

    def find_domain_for_path(self, block_path: str) -> Optional[Block]:
        domain_name = block_path.split(".")[0]
        return self.find_block(domain_name)

    def require_port(self, block_path: str, port_name: str) -> Port:
        block = self.find_block(block_path)
        if block is None:
            raise ValueError(f"Block not found: {block_path}")
        port = block.find_port(port_name)
        if port is None:
            raise ValueError(f"Port not found: {block_path}.{port_name}")
        return port

    def delete_port_with_references(self, block_path: str, port_name: str) -> None:
        block = self.find_block(block_path)
        if block is None:
            return
        block.remove_port(port_name)
        self.connections = [
            c for c in self.connections
            if not (c.source.block_path == block_path and c.source.port_name == port_name)
            and not (c.target.block_path == block_path and c.target.port_name == port_name)
        ]
        self.net_references = [
            r for r in self.net_references
            if not (r.end.block_path == block_path and r.end.port_name == port_name)
        ]

    def set_port_type(self, block_path: str, port_name: str, port_type: PortType) -> Port:
        port = self.require_port(block_path, port_name)
        port.port_type = port_type
        return port

    def set_port_side(self, block_path: str, port_name: str, side: PortSide) -> Port:
        port = self.require_port(block_path, port_name)
        port.attributes["sideOverride"] = side.value
        return port

    def set_power_direction(self, block_path: str, port_name: str, direction: PowerDirection) -> Port:
        port = self.require_port(block_path, port_name)
        port.attributes["powerDirection"] = direction.value
        return port

    def set_block_host(self, block_path: str, is_host: bool) -> Block:
        block = self.find_block(block_path)
        if block is None:
            raise ValueError(f"Block not found: {block_path}")

        if is_host:
            if block.level == ArchitectureLevel.DOMAIN:
                # Only one Level-1 host domain in the complete domain diagram.
                for domain in self.blocks:
                    domain.is_host = False
                    domain.attributes["isHost"] = False

            elif block.level == ArchitectureLevel.ARCH_ELEMENT:
                # Only one Level-2 host architecture element within its domain.
                domain = self.find_domain_for_path(block_path)
                if domain:
                    for child in domain.children:
                        child.is_host = False
                        child.attributes["isHost"] = False

        block.is_host = bool(is_host)
        block.attributes["isHost"] = bool(is_host)
        return block

    @staticmethod
    def infer_port_type(name: str, connection_type: ConnectionType, direction: NetReferenceDirection, signals: list[str], is_host: bool = False, attributes: dict[str, Any] | None = None) -> PortType:
        attrs = attributes or {}
        family = str(attrs.get("family", "")).lower()
        if family in {"interface", "memory"}:
            return PortType.BIDI
        if family == "control":
            return PortType.OUT if is_host else PortType.IN
        if family == "status":
            return PortType.IN if is_host else PortType.OUT
        if family == "analog":
            return PortType.ANALOG
        if family == "power":
            return PortType.POWER
        if connection_type == ConnectionType.BUS:
            return PortType.BIDI
        return {
            NetReferenceDirection.IN: PortType.IN,
            NetReferenceDirection.OUT: PortType.OUT,
            NetReferenceDirection.BIDI: PortType.BIDI,
        }[direction]

    @staticmethod
    def domain_color(name: str) -> str:
        upper = name.upper()
        palette = {
            "PSU": "#f8cecc", "POWER": "#f8cecc",
            "ETH": "#dae8fc", "ETHERNET": "#dae8fc",
            "SOM": "#d5e8d4", "SOC": "#d5e8d4",
            "RADAR": "#ffe6cc",
            "SAFETY": "#e1d5e7", "MICRO": "#e1d5e7",
            "CAM": "#fff2cc", "VIDEO": "#fff2cc",
            "AUDIO": "#f5f5f5",
        }
        for key, color in palette.items():
            if key in upper:
                return color
        colors = ["#eaf2ff", "#edf7ed", "#fff7e6", "#f3e8ff", "#e8f6f3", "#fce4ec"]
        return colors[sum(ord(c) for c in name) % len(colors)]

    def _validate_connection_direction(self, source_type: PortType, target_type: PortType) -> None:
        allowed = {
            (PortType.OUT, PortType.IN), (PortType.OUT, PortType.BIDI),
            (PortType.BIDI, PortType.IN), (PortType.BIDI, PortType.OUT), (PortType.BIDI, PortType.BIDI),
            (PortType.POWER, PortType.POWER), (PortType.OUT, PortType.POWER),
            (PortType.GROUND, PortType.GROUND),
            (PortType.ANALOG, PortType.ANALOG), (PortType.ANALOG, PortType.BIDI), (PortType.BIDI, PortType.ANALOG),
        }
        if (source_type, target_type) not in allowed:
            raise ValueError(f"Invalid connection direction: {source_type.value} -> {target_type.value}")

    def validate(self) -> None:
        block_paths = set()
        port_paths = set()
        errors: list[str] = []
        for block, path in self.walk_blocks():
            if path in block_paths:
                errors.append(f"Duplicate block path: {path}")
            block_paths.add(path)
            names = set()
            for port in block.ports:
                if port.name in names:
                    errors.append(f"Duplicate port on {path}: {port.name}")
                names.add(port.name)
                port_paths.add(f"{path}.{port.name}")
        for con in self.connections:
            if f"{con.source.block_path}.{con.source.port_name}" not in port_paths:
                errors.append(f"Connection {con.name}: source does not exist")
            if f"{con.target.block_path}.{con.target.port_name}" not in port_paths:
                errors.append(f"Connection {con.name}: target does not exist")
        for ref in self.net_references:
            if f"{ref.end.block_path}.{ref.end.port_name}" not in port_paths:
                errors.append(f"Net reference {ref.name}: port does not exist")
        if errors:
            raise ValueError("Model validation failed:\n" + "\n".join(f"- {e}" for e in errors))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ArchitectureModel":
        def port_from_dict(d: dict[str, Any]) -> Port:
            return Port(d["name"], PortType(d["port_type"]), d.get("id", make_id("PRT")), d.get("attributes", {}))
        def block_from_dict(d: dict[str, Any]) -> Block:
            return Block(
                name=d["name"], level=ArchitectureLevel(d["level"]), id=d.get("id", make_id("BLK")),
                kind=d.get("kind", "GenericBlock"), is_host=d.get("is_host", False), color=d.get("color", ""),
                attributes=d.get("attributes", {}), ports=[port_from_dict(p) for p in d.get("ports", [])],
                children=[block_from_dict(c) for c in d.get("children", [])],
            )
        def end_from_dict(d: dict[str, Any]) -> ConnectionEnd:
            return ConnectionEnd(d["block_path"], d["port_name"])
        def con_from_dict(d: dict[str, Any]) -> Connection:
            return Connection(d["name"], ConnectionType(d["connection_type"]), end_from_dict(d["source"]), end_from_dict(d["target"]), d.get("id", make_id("CON")), d.get("net_id", stable_net_id(d["name"])), d.get("attributes", {}))
        def ref_from_dict(d: dict[str, Any]) -> NetReference:
            return NetReference(d["name"], ConnectionType(d["reference_type"]), end_from_dict(d["end"]), NetReferenceDirection(d.get("direction", "Bidi")), d.get("id", make_id("REF")), d.get("net_id", stable_net_id(d["name"])), d.get("attributes", {}))
        return ArchitectureModel(data.get("name", "Generic_Architecture"), [block_from_dict(b) for b in data.get("blocks", [])], [con_from_dict(c) for c in data.get("connections", [])], [ref_from_dict(r) for r in data.get("net_references", [])])

    def save_json(self, path: str | Path) -> Path:
        p = Path(path)
        p.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return p

    @staticmethod
    def load_json(path: str | Path) -> "ArchitectureModel":
        return ArchitectureModel.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
