from __future__ import annotations

from collections.abc import Iterable
from itertools import combinations

from ..domain.models import Relatedness, ResearchField
from ..domain.validation import canonical_pair
from .models import GraphConfiguration, LayoutPair, Pair


def relatedness_values(relations: Iterable[Relatedness]) -> dict[Pair, float]:
    return {
        canonical_pair(relation.left, relation.right): relation.value
        for relation in relations
    }


def desired_distance(relatedness: float, config: GraphConfiguration) -> float:
    return config.distance_min + (config.distance_max - config.distance_min) * (
        1.0 - relatedness
    ) ** config.distance_gamma


def relatedness_weight(relatedness: float, config: GraphConfiguration) -> float:
    return relatedness**config.relatedness_beta


def build_layout_pairs(
    fields: Iterable[ResearchField],
    relations: Iterable[Relatedness],
    config: GraphConfiguration,
) -> tuple[LayoutPair, ...]:
    ids = [field.id for field in fields]
    values = relatedness_values(relations)
    result = []
    for left, right in combinations(ids, 2):
        pair = canonical_pair(left, right)
        value = values.get(pair, 0.0)
        result.append(
            LayoutPair(
                left=pair[0],
                right=pair[1],
                relatedness=value,
                weight=relatedness_weight(value, config),
                desired_distance=desired_distance(value, config),
            )
        )
    return tuple(result)
