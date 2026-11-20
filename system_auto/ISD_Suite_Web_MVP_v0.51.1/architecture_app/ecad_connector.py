"""Tool-independent entry points for explicitly initiated ECAD annotations."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .models import ArchitecturePackage


@dataclass
class AnnotationChange:
    object_id: str
    field: str
    before: object
    after: object
    status: str = "ready"  # ready, conflict, unsupported
    detail: str = ""


@dataclass
class AnnotationPreview:
    direction: str
    changes: list[AnnotationChange] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def can_apply(self) -> bool:
        return not any(item.status != "ready" for item in self.changes)


class EcadConnector(Protocol):
    name: str

    def forward_preview(self, package: ArchitecturePackage) -> AnnotationPreview: ...
    def forward_archive(self, package: ArchitecturePackage) -> bytes: ...
    def backward_preview(self, package: ArchitecturePackage, archive: bytes) -> AnnotationPreview: ...
    def backward_apply(self, package: ArchitecturePackage, preview: AnnotationPreview) -> ArchitecturePackage: ...


_CONNECTORS: dict[str, EcadConnector] = {}


def register(connector: EcadConnector) -> None:
    _CONNECTORS[connector.name] = connector


def connector_for(name: str) -> EcadConnector:
    return _CONNECTORS[name]
