from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal, Any
import json


PortType = Literal["in", "out", "bidi", "power", "ground", "analog"]
ConnectionType = Literal["net", "bus"]
BlockLevel = Literal[1, 2, 3, 4]


@dataclass
class Port:
    id: str
    name: str
    type: PortType
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Block:
    id: str
    name: str
    level: BlockLevel
    stereotype: str
    ports: list[Port] = field(default_factory=list)
    children: list["Block"] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


@dataclass
class Connection:
    id: str
    name: str
    type: ConnectionType
    source: str  # BLOCK_ID.PORT_ID
    target: str  # BLOCK_ID.PORT_ID
    stereotype: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Design:
    id: str
    name: str
    domains: list[Block] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    def walk_blocks(self):
        for domain in self.domains:
            yield from domain.walk()

    def find_block(self, block_id: str) -> Block:
        for block in self.walk_blocks():
            if block.id == block_id:
                return block
        raise KeyError(f"Block not found: {block_id}")

    def find_port_ref(self, ref: str) -> tuple[Block, Port]:
        block_id, port_id = ref.split(".", 1)
        block = self.find_block(block_id)
        for port in block.ports:
            if port.id == port_id:
                return block, port
        raise KeyError(f"Port not found: {ref}")

    def direct_children_of(self, parent: Block | None) -> list[Block]:
        return self.domains if parent is None else parent.children

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent, ensure_ascii=False)
