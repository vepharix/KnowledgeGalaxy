from __future__ import annotations

import math

from .models import (
    DepthMetric,
    GraphDiagnostics,
    LayoutPair,
    LossComponents,
    Point3,
)
from .regions import squared_distance


def radial_distances(positions: dict[str, Point3]) -> dict[str, float]:
    count = len(positions)
    centroid = tuple(
        sum(point[axis] for point in positions.values()) / count
        for axis in range(3)
    )
    return {
        field_id: math.sqrt(squared_distance(point, centroid))
        for field_id, point in positions.items()
    }


def pair_distance(left: Point3, right: Point3) -> float:
    return math.sqrt(squared_distance(left, right))


def build_diagnostics(
    field_ids: tuple[str, ...],
    depth: dict[str, DepthMetric],
    actual_radii: dict[str, float],
    target_radii: dict[str, float],
    layout_pairs: tuple[LayoutPair, ...],
    coordinates: dict[str, Point3],
    loss: LossComponents,
    trace: tuple[dict[str, float], ...],
) -> GraphDiagnostics:
    return GraphDiagnostics(
        loss=loss,
        optimization_trace=trace,
        depth_radius_pearson=_pearson(
            [depth[field_id].normalized for field_id in field_ids],
            [actual_radii[field_id] for field_id in field_ids],
        ),
        target_radius_mean_absolute_error=(
            sum(
                abs(actual_radii[field_id] - target_radii[field_id])
                for field_id in field_ids
            )
            / len(field_ids)
        ),
        minimum_pair_distance=min(
            pair.actual_distance
            for pair in layout_pairs
            if pair.actual_distance is not None
        ),
        coordinate_finite=all(
            math.isfinite(value)
            for point in coordinates.values()
            for value in point
        ),
    )


def _pearson(left: list[float], right: list[float]) -> float:
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_variance = sum((value - left_mean) ** 2 for value in left)
    right_variance = sum((value - right_mean) ** 2 for value in right)
    denominator = math.sqrt(left_variance * right_variance)
    return numerator / denominator if denominator > 1e-15 else 0.0
