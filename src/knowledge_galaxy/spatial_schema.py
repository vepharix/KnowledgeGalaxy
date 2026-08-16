from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
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
class SpatialConfig:
    seed: int = 20260816
    dependency_regularization_eta: float = 0.15
    dependency_affinity_lambda: float = 0.70
    distance_min: float = 0.8
    distance_max: float = 7.0
    distance_gamma: float = 1.35
    affinity_beta: float = 1.4
    radius_min: float = 1.1
    radius_max: float = 5.8
    radial_loss_lambda: float = 1.8
    repulsion_loss_lambda: float = 0.12
    repulsion_epsilon: float = 1.0
    repulsion_delta: float = 0.12
    learning_rate: float = 0.025
    optimization_steps: int = 3500
    gradient_clip: float = 8.0
    adam_beta1: float = 0.9
    adam_beta2: float = 0.999
    adam_epsilon: float = 1e-8
    hierarchy_sigma: float = 1.15
    hierarchy_threshold: float = 0.55
    density_grid_size: int = 11

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


@dataclass(frozen=True)
class SpatialFixture:
    metadata: dict[str, Any]
    fields: tuple[ResearchField, ...]
    hierarchy: tuple[HierarchyEdge, ...]
    dependencies: tuple[DependencyEdge, ...]
    relatedness: tuple[Relatedness, ...]


def load_spatial_fixture(path: Path) -> SpatialFixture:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("spatial fixture must be a JSON object")

    fields = tuple(
        ResearchField(
            id=item["id"],
            name=item["name"],
            description=item["description"],
            emergence_time=item.get("emergence_time"),
        )
        for item in payload.get("fields", [])
    )
    hierarchy = tuple(
        HierarchyEdge(
            broader=item["broader"],
            narrower=item["narrower"],
            value=float(item["value"]),
            provenance=item["provenance"],
        )
        for item in payload.get("hierarchy", [])
    )
    dependencies = tuple(
        DependencyEdge(
            foundation=item["foundation"],
            dependent=item["dependent"],
            value=float(item["value"]),
            provenance=item["provenance"],
        )
        for item in payload.get("dependencies", [])
    )
    relatedness = tuple(
        Relatedness(
            left=item["left"],
            right=item["right"],
            value=float(item["value"]),
            provenance=item["provenance"],
        )
        for item in payload.get("relatedness", [])
    )
    fixture = SpatialFixture(
        metadata=payload.get("metadata", {}),
        fields=fields,
        hierarchy=hierarchy,
        dependencies=dependencies,
        relatedness=relatedness,
    )
    validate_spatial_fixture(fixture)
    return fixture


def validate_spatial_fixture(fixture: SpatialFixture) -> None:
    if not fixture.fields:
        raise ValueError("spatial fixture requires at least one ResearchField")
    ids = [field.id for field in fixture.fields]
    if len(ids) != len(set(ids)):
        raise ValueError("ResearchField ids must be unique")
    id_set = set(ids)
    for field in fixture.fields:
        if not field.id or not field.name or not field.description:
            raise ValueError("ResearchField id, name and description are required")

    seen_hierarchy: set[tuple[str, str]] = set()
    for edge in fixture.hierarchy:
        _validate_edge(edge.broader, edge.narrower, edge.value, edge.provenance, id_set, "H")
        pair = (edge.broader, edge.narrower)
        if pair in seen_hierarchy:
            raise ValueError(f"duplicate hierarchy edge: {pair}")
        seen_hierarchy.add(pair)

    seen_dependencies: set[tuple[str, str]] = set()
    for edge in fixture.dependencies:
        _validate_edge(edge.foundation, edge.dependent, edge.value, edge.provenance, id_set, "D")
        pair = (edge.foundation, edge.dependent)
        if pair in seen_dependencies:
            raise ValueError(f"duplicate dependency edge: {pair}")
        seen_dependencies.add(pair)

    seen_relatedness: set[tuple[str, str]] = set()
    for relation in fixture.relatedness:
        _validate_edge(relation.left, relation.right, relation.value, relation.provenance, id_set, "R")
        pair = tuple(sorted((relation.left, relation.right)))
        if pair in seen_relatedness:
            raise ValueError(f"duplicate symmetric relatedness pair: {pair}")
        seen_relatedness.add(pair)


def _validate_edge(
    left: str,
    right: str,
    value: float,
    provenance: str,
    ids: set[str],
    label: str,
) -> None:
    if left == right:
        raise ValueError(f"{label} self-edges are not allowed")
    if left not in ids or right not in ids:
        raise ValueError(f"{label} references an unknown ResearchField: {(left, right)}")
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{label} value must be in [0, 1]")
    if not provenance:
        raise ValueError(f"{label} requires provenance")
