from __future__ import annotations

import math
import random
from collections.abc import Iterable

from ..domain.models import ResearchField
from .dependency import target_radius
from .models import DepthMetric, GraphConfiguration, LayoutPair, LossComponents, Point3
from .objective import ObjectivePair, loss_and_gradient


def optimize_layout(
    fields: Iterable[ResearchField],
    dependency_depth: dict[str, DepthMetric],
    layout_pairs: tuple[LayoutPair, ...],
    config: GraphConfiguration,
) -> tuple[dict[str, Point3], LossComponents, tuple[dict[str, float], ...]]:
    """Optimize coordinates from D-derived radii and R-derived pair constraints."""
    ids = [field.id for field in fields]
    index = {field_id: position for position, field_id in enumerate(ids)}
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
    targets = [
        target_radius(dependency_depth[field_id].normalized, config)
        for field_id in ids
    ]
    objective_pairs = tuple(
        ObjectivePair(
            left_index=index[pair.left],
            right_index=index[pair.right],
            weight=pair.weight,
            desired_distance=pair.desired_distance,
        )
        for pair in layout_pairs
    )

    trace = []
    checkpoints = {0, config.optimization_steps - 1}
    checkpoints.update(range(249, config.optimization_steps, 250))
    for step in range(1, config.optimization_steps + 1):
        gradients, components = loss_and_gradient(positions, objective_pairs, targets, config)
        _clip_gradients(gradients, config.gradient_clip)
        beta1_power = config.adam_beta1**step
        beta2_power = config.adam_beta2**step
        for position in range(len(ids)):
            for axis in range(3):
                gradient = gradients[position][axis]
                first_moment[position][axis] = (
                    config.adam_beta1 * first_moment[position][axis]
                    + (1.0 - config.adam_beta1) * gradient
                )
                second_moment[position][axis] = (
                    config.adam_beta2 * second_moment[position][axis]
                    + (1.0 - config.adam_beta2) * gradient * gradient
                )
                corrected_first = first_moment[position][axis] / (1.0 - beta1_power)
                corrected_second = second_moment[position][axis] / (1.0 - beta2_power)
                positions[position][axis] -= config.learning_rate * corrected_first / (
                    math.sqrt(corrected_second) + config.adam_epsilon
                )
        _recenter(positions)
        if step - 1 in checkpoints:
            trace.append({"step": float(step), **components.to_dict()})

    _, final_components = loss_and_gradient(positions, objective_pairs, targets, config)
    coordinates = {
        field_id: tuple(positions[index[field_id]])
        for field_id in ids
    }
    return coordinates, final_components, tuple(trace)


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
