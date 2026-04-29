from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal, Optional
import json


PortType = Literal["power", "ground", "input", "output", "bidirectional", "analog"]
ConnectionType = Literal["net", "bus"]


@dataclass
class Port:
    name: str
    type: PortType
    side: Literal["left", "right", "top", "bottom"] = "left"
    voltage: Optional[str] = None
    protocol: Optional[str] = None
    constraint_class: Optional[str] = None
    description: Optional[str] = None

    def fqid(self, block_path: str) -> str:
        return f"{block_path}.{self.name}"


@dataclass
class Block:
    name: str
    label: Optional[str] = None
    ref: Optional[str] = None
    description: Optional[str] = None
    ports: list[Port] = field(default_factory=list)
    children: list["Block"] = field(default_factory=list)

    def walk(self, parent_path: str = ""):
        path = f"{parent_path}.{self.name}" if parent_path else self.name
        yield path, self
        for child in self.children:
            yield from child.walk(path)

    def find_port(self, fq_port: str) -> tuple[str, Port]:
        """
        fq_port example:
            THOR_SoM.CSI_IN0
            THOR_SoM.CSI_Bridge.CSI_IN0
        """
        block_path, port_name = fq_port.rsplit(".", 1)
        for path, block in self.walk():
            if path == block_path:
                for port in block.ports:
                    if port.name == port_name:
                        return path, port
        raise KeyError(f"Port not found: {fq_port}")

    def to_dict(self):
        return asdict(self)


@dataclass
class Connection:
    name: str
    type: ConnectionType
    source: str
    target: str
    protocol: Optional[str] = None
    width: Optional[int] = None
    constraint_class: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class Design:
    name: str
    root_blocks: list[Block] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)

    def walk_blocks(self):
        for block in self.root_blocks:
            yield from block.walk()

    def find_port(self, fq_port: str) -> tuple[str, Port]:
        for block in self.root_blocks:
            try:
                return block.find_port(fq_port)
            except KeyError:
                pass
        raise KeyError(f"Port not found: {fq_port}")

    def to_dict(self):
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
