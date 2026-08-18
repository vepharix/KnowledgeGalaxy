from __future__ import annotations

import math
from dataclasses import dataclass

from .models import GraphConfiguration, LossComponents


@dataclass(frozen=True)
class ObjectivePair:
    left_index: int
    right_index: int
    weight: float
    desired_distance: float


def loss_and_gradient(
    positions: list[list[float]],
    pairs: tuple[ObjectivePair, ...],
    target_radii: list[float],
    config: GraphConfiguration,
) -> tuple[list[list[float]], LossComponents]:
    count = len(positions)
    gradients = [[0.0, 0.0, 0.0] for _ in positions]
    relatedness_loss = 0.0
    repel_loss = 0.0

    for pair in pairs:
        left = pair.left_index
        right = pair.right_index
        difference = [positions[left][axis] - positions[right][axis] for axis in range(3)]
        distance = math.sqrt(sum(value * value for value in difference))
        safe_distance = max(distance, 1e-12)
        if pair.weight > 0.0:
            residual = distance - pair.desired_distance
            relatedness_loss += pair.weight * residual * residual
            factor = 2.0 * pair.weight * residual / safe_distance
            for axis in range(3):
                value = factor * difference[axis]
                gradients[left][axis] += value
                gradients[right][axis] -= value

        repel_loss += config.repulsion_epsilon / (distance + config.repulsion_delta) ** 2
        repel_factor = (
            -2.0
            * config.repulsion_epsilon
            / ((distance + config.repulsion_delta) ** 3 * safe_distance)
        )
        for axis in range(3):
            value = config.repulsion_loss_lambda * repel_factor * difference[axis]
            gradients[left][axis] += value
            gradients[right][axis] -= value

    centroid = [sum(point[axis] for point in positions) / count for axis in range(3)]
    radial_gradients = [[0.0, 0.0, 0.0] for _ in positions]
    radial_loss = 0.0
    for index, point in enumerate(positions):
        centered = [point[axis] - centroid[axis] for axis in range(3)]
        radius = math.sqrt(sum(value * value for value in centered))
        safe_radius = max(radius, 1e-12)
        residual = radius - target_radii[index]
        radial_loss += residual * residual
        for axis in range(3):
            radial_gradients[index][axis] = 2.0 * residual * centered[axis] / safe_radius
    average_radial_gradient = [
        sum(row[axis] for row in radial_gradients) / count
        for axis in range(3)
    ]
    for index in range(count):
        for axis in range(3):
            gradients[index][axis] += config.radial_loss_lambda * (
                radial_gradients[index][axis] - average_radial_gradient[axis]
            )

    return gradients, LossComponents(
        relatedness=relatedness_loss,
        radial=radial_loss,
        repel=repel_loss,
        weighted_radial=config.radial_loss_lambda * radial_loss,
        weighted_repel=config.repulsion_loss_lambda * repel_loss,
        total=(
            relatedness_loss
            + config.radial_loss_lambda * radial_loss
            + config.repulsion_loss_lambda * repel_loss
        ),
    )
