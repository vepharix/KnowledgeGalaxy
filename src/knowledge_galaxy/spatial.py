from __future__ import annotations

import math
import random
from itertools import combinations
from typing import Iterable

from .spatial_schema import (
    DependencyEdge,
    HierarchyEdge,
    Relatedness,
    ResearchField,
    SpatialConfig,
)


Pair = tuple[str, str]
Point3 = tuple[float, float, float]


def canonical_pair(left: str, right: str) -> Pair:
    return (left, right) if left < right else (right, left)


def compute_transitive_membership(
    fields: Iterable[ResearchField],
    edges: Iterable[HierarchyEdge],
) -> dict[Pair, float]:
    """Return max-product H path strengths M(A, B)."""
    ids = [field.id for field in fields]
    index = {field_id: i for i, field_id in enumerate(ids)}
    count = len(ids)
    strength = [[0.0 for _ in range(count)] for _ in range(count)]
    for i in range(count):
        strength[i][i] = 1.0
    for edge in edges:
        i = index[edge.broader]
        j = index[edge.narrower]
        strength[i][j] = max(strength[i][j], edge.value)

    for k in range(count):
        for i in range(count):
            if strength[i][k] == 0.0:
                continue
            for j in range(count):
                candidate = strength[i][k] * strength[k][j]
                if candidate > strength[i][j]:
                    strength[i][j] = candidate

    return {
        (left, right): strength[index[left]][index[right]]
        for left in ids
        for right in ids
        if left != right and strength[index[left]][index[right]] > 0.0
    }


def compute_scope(
    fields: Iterable[ResearchField],
    membership: dict[Pair, float],
) -> dict[str, dict[str, float]]:
    ids = [field.id for field in fields]
    denominator = math.log1p(max(len(ids) - 1, 1))
    result: dict[str, dict[str, float]] = {}
    for field_id in ids:
        scope = sum(value for (broader, _), value in membership.items() if broader == field_id)
        result[field_id] = {
            "scope": scope,
            "normalized": math.log1p(scope) / denominator if denominator else 0.0,
        }
    return result


def dependency_values(edges: Iterable[DependencyEdge]) -> dict[tuple[str, str], float]:
    return {(edge.foundation, edge.dependent): edge.value for edge in edges}


def relatedness_values(relations: Iterable[Relatedness]) -> dict[Pair, float]:
    return {canonical_pair(item.left, item.right): item.value for item in relations}


def compute_dependency_depth(
    fields: Iterable[ResearchField],
    edges: Iterable[DependencyEdge],
    eta: float,
) -> dict[str, dict[str, float]]:
    ids = [field.id for field in fields]
    index = {field_id: i for i, field_id in enumerate(ids)}
    count = len(ids)
    matrix = [[0.0 for _ in range(count)] for _ in range(count)]
    rhs = [0.0 for _ in range(count)]
    for i in range(count):
        matrix[i][i] = eta

    # Weighted least squares for sqrt(D_ij) * (-q_i + q_j) = sqrt(D_ij).
    for edge in edges:
        i = index[edge.foundation]
        j = index[edge.dependent]
        weight = edge.value
        matrix[i][i] += weight
        matrix[j][j] += weight
        matrix[i][j] -= weight
        matrix[j][i] -= weight
        rhs[i] -= weight
        rhs[j] += weight

    raw = _solve_linear_system(matrix, rhs)
    low = min(raw)
    high = max(raw)
    spread = high - low
    normalized = [(value - low) / spread if spread > 1e-12 else 0.0 for value in raw]
    return {
        field_id: {"raw": raw[index[field_id]], "normalized": normalized[index[field_id]]}
        for field_id in ids
    }


def compute_geometric_affinity(
    fields: Iterable[ResearchField],
    dependencies: Iterable[DependencyEdge],
    relatedness: Iterable[Relatedness],
    dependency_affinity_lambda: float,
) -> dict[Pair, dict[str, float]]:
    ids = [field.id for field in fields]
    dependency = dependency_values(dependencies)
    related = relatedness_values(relatedness)
    result: dict[Pair, dict[str, float]] = {}
    for left, right in combinations(ids, 2):
        pair = canonical_pair(left, right)
        r_value = related.get(pair, 0.0)
        dependency_affinity = (
            dependency.get((left, right), 0.0) + dependency.get((right, left), 0.0)
        ) / 2.0
        geometric = min(1.0, max(0.0, r_value + dependency_affinity_lambda * dependency_affinity))
        result[pair] = {
            "relatedness": r_value,
            "dependencyAffinity": dependency_affinity,
            "geometricAffinity": geometric,
        }
    return result


def desired_distance(geometric_affinity: float, config: SpatialConfig) -> float:
    return config.distance_min + (config.distance_max - config.distance_min) * (
        1.0 - geometric_affinity
    ) ** config.distance_gamma


def target_radius(normalized_dependency_depth: float, config: SpatialConfig) -> float:
    return config.radius_min + (config.radius_max - config.radius_min) * normalized_dependency_depth


def optimize_layout(
    fields: Iterable[ResearchField],
    dependency_depth: dict[str, dict[str, float]],
    affinities: dict[Pair, dict[str, float]],
    config: SpatialConfig,
) -> tuple[dict[str, Point3], dict[str, float], list[dict[str, float]]]:
    """Optimize v0 coordinates. Hierarchy is intentionally absent from this signature."""
    ids = [field.id for field in fields]
    count = len(ids)
    rng = random.Random(config.seed)
    average_radius = (config.radius_min + config.radius_max) / 2.0
    positions = []
    for _ in ids:
        direction = _random_unit_vector(rng)
        scale = average_radius * (0.55 + 0.35 * rng.random())
        positions.append([component * scale for component in direction])
    _recenter(positions)

    first_moment = [[0.0, 0.0, 0.0] for _ in ids]
    second_moment = [[0.0, 0.0, 0.0] for _ in ids]
    targets = [target_radius(dependency_depth[field_id]["normalized"], config) for field_id in ids]
    pair_inputs = []
    for i, j in combinations(range(count), 2):
        affinity = affinities[canonical_pair(ids[i], ids[j])]["geometricAffinity"]
        pair_inputs.append(
            (
                i,
                j,
                affinity ** config.affinity_beta,
                desired_distance(affinity, config),
            )
        )

    trace: list[dict[str, float]] = []
    checkpoints = {0, config.optimization_steps - 1}
    checkpoints.update(range(249, config.optimization_steps, 250))
    for step in range(1, config.optimization_steps + 1):
        gradients, components = _loss_and_gradient(positions, pair_inputs, targets, config)
        _clip_gradients(gradients, config.gradient_clip)
        beta1_power = config.adam_beta1**step
        beta2_power = config.adam_beta2**step
        for i in range(count):
            for axis in range(3):
                gradient = gradients[i][axis]
                first_moment[i][axis] = (
                    config.adam_beta1 * first_moment[i][axis]
                    + (1.0 - config.adam_beta1) * gradient
                )
                second_moment[i][axis] = (
                    config.adam_beta2 * second_moment[i][axis]
                    + (1.0 - config.adam_beta2) * gradient * gradient
                )
                corrected_first = first_moment[i][axis] / (1.0 - beta1_power)
                corrected_second = second_moment[i][axis] / (1.0 - beta2_power)
                positions[i][axis] -= config.learning_rate * corrected_first / (
                    math.sqrt(corrected_second) + config.adam_epsilon
                )
        _recenter(positions)
        if step - 1 in checkpoints:
            trace.append({"step": float(step), **components})

    _, final_components = _loss_and_gradient(positions, pair_inputs, targets, config)
    coordinates = {field_id: tuple(positions[i]) for i, field_id in enumerate(ids)}
    return coordinates, final_components, trace


def compute_hierarchy_regions(
    fields: Iterable[ResearchField],
    membership: dict[Pair, float],
    positions: dict[str, Point3],
    config: SpatialConfig,
) -> dict[str, object]:
    ids = [field.id for field in fields]
    regions: dict[str, dict[str, object]] = {}
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

    grid_points = _density_grid(positions.values(), config.hierarchy_sigma, config.density_grid_size)
    active_indices: dict[str, set[int]] = {}
    for broader, region in regions.items():
        members = region["members"]
        assert isinstance(members, dict)
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
            "A node lying inside a sampled hierarchy region is geometric overlap only and does not create H."
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
        membership * math.exp(-_squared_distance(point, positions[field_id]) / denominator)
        for field_id, membership in members.items()
    )


def radial_distances(positions: dict[str, Point3]) -> dict[str, float]:
    count = len(positions)
    centroid = tuple(
        sum(point[axis] for point in positions.values()) / count for axis in range(3)
    )
    return {
        field_id: math.sqrt(_squared_distance(point, centroid))
        for field_id, point in positions.items()
    }


def _loss_and_gradient(
    positions: list[list[float]],
    pairs: list[tuple[int, int, float, float]],
    target_radii: list[float],
    config: SpatialConfig,
) -> tuple[list[list[float]], dict[str, float]]:
    count = len(positions)
    gradients = [[0.0, 0.0, 0.0] for _ in positions]
    affinity_loss = 0.0
    repulsion_loss = 0.0

    for i, j, weight, target in pairs:
        difference = [positions[i][axis] - positions[j][axis] for axis in range(3)]
        distance = math.sqrt(sum(value * value for value in difference))
        safe_distance = max(distance, 1e-12)
        if weight > 0.0:
            residual = distance - target
            affinity_loss += weight * residual * residual
            factor = 2.0 * weight * residual / safe_distance
            for axis in range(3):
                value = factor * difference[axis]
                gradients[i][axis] += value
                gradients[j][axis] -= value

        repulsion_loss += config.repulsion_epsilon / (distance + config.repulsion_delta) ** 2
        repulsion_factor = (
            -2.0
            * config.repulsion_epsilon
            / ((distance + config.repulsion_delta) ** 3 * safe_distance)
        )
        for axis in range(3):
            value = config.repulsion_loss_lambda * repulsion_factor * difference[axis]
            gradients[i][axis] += value
            gradients[j][axis] -= value

    centroid = [sum(point[axis] for point in positions) / count for axis in range(3)]
    radial_gradients = [[0.0, 0.0, 0.0] for _ in positions]
    radial_loss = 0.0
    for i, point in enumerate(positions):
        centered = [point[axis] - centroid[axis] for axis in range(3)]
        radius = math.sqrt(sum(value * value for value in centered))
        safe_radius = max(radius, 1e-12)
        residual = radius - target_radii[i]
        radial_loss += residual * residual
        for axis in range(3):
            radial_gradients[i][axis] = 2.0 * residual * centered[axis] / safe_radius
    average_radial_gradient = [
        sum(row[axis] for row in radial_gradients) / count for axis in range(3)
    ]
    for i in range(count):
        for axis in range(3):
            gradients[i][axis] += config.radial_loss_lambda * (
                radial_gradients[i][axis] - average_radial_gradient[axis]
            )

    return gradients, {
        "affinity": affinity_loss,
        "radial": radial_loss,
        "repulsion": repulsion_loss,
        "weightedRadial": config.radial_loss_lambda * radial_loss,
        "weightedRepulsion": config.repulsion_loss_lambda * repulsion_loss,
        "total": (
            affinity_loss
            + config.radial_loss_lambda * radial_loss
            + config.repulsion_loss_lambda * repulsion_loss
        ),
    }


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


def _random_unit_vector(rng: random.Random) -> list[float]:
    while True:
        vector = [rng.gauss(0.0, 1.0) for _ in range(3)]
        length = math.sqrt(sum(value * value for value in vector))
        if length > 1e-12:
            return [value / length for value in vector]


def _recenter(positions: list[list[float]]) -> None:
    count = len(positions)
    centroid = [sum(point[axis] for point in positions) / count for axis in range(3)]
    for point in positions:
        for axis in range(3):
            point[axis] -= centroid[axis]


def _clip_gradients(gradients: list[list[float]], maximum: float) -> None:
    norm = math.sqrt(sum(value * value for row in gradients for value in row))
    if norm <= maximum:
        return
    scale = maximum / norm
    for row in gradients:
        for axis in range(3):
            row[axis] *= scale


def _squared_distance(left: Point3, right: Point3) -> float:
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
        axes.append([low + step * i for i in range(grid_size)])
    return [(x, y, z) for x in axes[0] for y in axes[1] for z in axes[2]]
