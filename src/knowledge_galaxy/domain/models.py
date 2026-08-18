from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ResearchField:
    id: str
    name: str
    description: str
    emergence_time: str | None = None


@dataclass(frozen=True)
class HierarchyEdge:
    broader: str
    narrower: str
    value: float
    provenance: str


@dataclass(frozen=True)
class DependencyEdge:
    foundation: str
    dependent: str
    value: float
    provenance: str


@dataclass(frozen=True)
class Relatedness:
    left: str
    right: str
    value: float
    provenance: str


@dataclass(frozen=True)
class KnowledgeGraphInput:
    fields: tuple[ResearchField, ...]
    hierarchy: tuple[HierarchyEdge, ...]
    dependencies: tuple[DependencyEdge, ...]
    relatedness: tuple[Relatedness, ...]
    metadata: dict[str, Any] = field(default_factory=dict)
