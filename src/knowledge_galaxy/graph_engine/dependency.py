from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ..domain.models import DependencyEdge, ResearchField
from .models import DepthMetric, GraphConfiguration


@dataclass(frozen=True)
class DependencyConstraint:
    foundation: str
    dependent: str
    weight: float
    target_difference: float = 1.0


def dependency_constraint(edge: DependencyEdge) -> DependencyConstraint:
    return DependencyConstraint(
        foundation=edge.foundation,
        dependent=edge.dependent,
        weight=edge.value,
    )


def compute_dependency_depth(
    fields: Iterable[ResearchField],
    edges: Iterable[DependencyEdge],
    eta: float,
) -> dict[str, DepthMetric]:
    ids = [field.id for field in fields]
    index = {field_id: position for position, field_id in enumerate(ids)}
    count = len(ids)
    matrix = [[0.0 for _ in range(count)] for _ in range(count)]
    rhs = [0.0 for _ in range(count)]
    for position in range(count):
        matrix[position][position] = eta

    for edge in edges:
        constraint = dependency_constraint(edge)
        foundation = index[constraint.foundation]
        dependent = index[constraint.dependent]
        weight = constraint.weight
        target = constraint.target_difference
        matrix[foundation][foundation] += weight
        matrix[dependent][dependent] += weight
        matrix[foundation][dependent] -= weight
        matrix[dependent][foundation] -= weight
        rhs[foundation] -= weight * target
        rhs[dependent] += weight * target

    raw = _solve_linear_system(matrix, rhs)
    low = min(raw)
    high = max(raw)
    spread = high - low
    normalized = [
        (value - low) / spread if spread > 1e-12 else 0.0
        for value in raw
    ]
    return {
        field_id: DepthMetric(
            raw=raw[index[field_id]],
            normalized=normalized[index[field_id]],
        )
        for field_id in ids
    }


def target_radius(normalized_depth: float, config: GraphConfiguration) -> float:
    return config.radius_min + (config.radius_max - config.radius_min) * normalized_depth


def _solve_linear_system(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    count = len(rhs)
    augmented = [matrix[row][:] + [rhs[row]] for row in range(count)]
    for column in range(count):
        pivot = max(range(column, count), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-14:
            raise ValueError("dependency depth system is singular; eta must be positive")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        pivot_value = augmented[column][column]
        for entry in range(column, count + 1):
            augmented[column][entry] /= pivot_value
        for row in range(count):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0.0:
                continue
            for entry in range(column, count + 1):
                augmented[row][entry] -= factor * augmented[column][entry]
    return [augmented[row][count] for row in range(count)]
