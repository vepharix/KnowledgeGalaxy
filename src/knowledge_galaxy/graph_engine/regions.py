from __future__ import annotations

import math
from collections.abc import Iterable
from itertools import combinations
from typing import Any

from ..domain.models import ResearchField
from .models import GraphConfiguration, Pair, Point3


def compute_hierarchy_regions(
    fields: Iterable[ResearchField],
    membership: dict[Pair, float],
    positions: dict[str, Point3],
    config: GraphConfiguration,
) -> dict[str, Any]:
    ids = [field.id for field in fields]
    regions: dict[str, dict[str, Any]] = {}
    for broader in ids:
        members = {
            narrower: value
            for (candidate, narrower), value in membership.items()
            if candidate == broader
        }
        if not members:
            continue
        densities = {
            field_id: hierarchy_density(
                positions[field_id],
                members,
                positions,
                config.hierarchy_sigma,
            )
            for field_id in ids
        }
        regions[broader] = {
            "tau": config.hierarchy_threshold,
            "sigma": config.hierarchy_sigma,
            "members": members,
            "densityAtNodes": densities,
            "insideNodeIds": sorted(
                field_id
                for field_id, density in densities.items()
                if density >= config.hierarchy_threshold
            ),
        }

    grid_points = _density_grid(
        positions.values(),
        config.hierarchy_sigma,
        config.density_grid_size,
    )
    active_indices: dict[str, set[int]] = {}
    for broader, region in regions.items():
        members = region["members"]
        active = {
            index
            for index, point in enumerate(grid_points)
            if hierarchy_density(point, members, positions, config.hierarchy_sigma)
            >= config.hierarchy_threshold
        }
        active_indices[broader] = active
        region["activeGridPoints"] = len(active)
        region["activeGridFraction"] = len(active) / len(grid_points) if grid_points else 0.0

    overlaps = []
    for left, right in combinations(sorted(active_indices), 2):
        overlap = len(active_indices[left] & active_indices[right])
        if overlap:
            overlaps.append({"left": left, "right": right, "overlapGridPoints": overlap})
    overlaps.sort(key=lambda item: (-item["overlapGridPoints"], item["left"], item["right"]))
    return {
        "representation": "Gaussian descendant density sampled on a shared diagnostic grid",
        "gridPointCount": len(grid_points),
        "regions": regions,
        "overlaps": overlaps,
        "interpretationBoundary": (
            "A node inside a sampled hierarchy region is geometric overlap only and does not create H."
        ),
    }


def hierarchy_density(
    point: Point3,
    members: dict[str, float],
    positions: dict[str, Point3],
    sigma: float,
) -> float:
    denominator = 2.0 * sigma * sigma
    return sum(
        strength * math.exp(-squared_distance(point, positions[field_id]) / denominator)
        for field_id, strength in members.items()
    )


def squared_distance(left: Point3, right: Point3) -> float:
    return sum((left[axis] - right[axis]) ** 2 for axis in range(3))


def _density_grid(
    points: Iterable[Point3],
    padding: float,
    grid_size: int,
) -> list[Point3]:
    values = list(points)
    axes = []
    for axis in range(3):
        low = min(point[axis] for point in values) - 2.0 * padding
        high = max(point[axis] for point in values) + 2.0 * padding
        step = (high - low) / max(grid_size - 1, 1)
        axes.append([low + step * index for index in range(grid_size)])
    return [(x, y, z) for x in axes[0] for y in axes[1] for z in axes[2]]
