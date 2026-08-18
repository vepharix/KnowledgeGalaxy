from __future__ import annotations

import math
from collections.abc import Iterable
from itertools import combinations

from ..domain.models import DependencyEdge, Relatedness, ResearchField
from ..domain.validation import canonical_pair
from .models import ConnectivityMetric, Pair


def compute_pair_connectivity(
    fields: Iterable[ResearchField],
    dependencies: Iterable[DependencyEdge],
    relatedness: Iterable[Relatedness],
) -> dict[Pair, float]:
    ids = [field.id for field in fields]
    pair_strength = {canonical_pair(left, right): 0.0 for left, right in combinations(ids, 2)}
    for relation in relatedness:
        pair = canonical_pair(relation.left, relation.right)
        pair_strength[pair] = max(pair_strength[pair], relation.value)
    for edge in dependencies:
        pair = canonical_pair(edge.foundation, edge.dependent)
        pair_strength[pair] = max(pair_strength[pair], edge.value)
    return pair_strength


def compute_connectivity(
    fields: Iterable[ResearchField],
    dependencies: Iterable[DependencyEdge],
    relatedness: Iterable[Relatedness],
) -> dict[str, ConnectivityMetric]:
    ids = [field.id for field in fields]
    raw = {field_id: 0.0 for field_id in ids}
    for (left, right), value in compute_pair_connectivity(
        fields,
        dependencies,
        relatedness,
    ).items():
        raw[left] += value
        raw[right] += value
    maximum = max(raw.values(), default=0.0)
    denominator = math.log1p(maximum)
    return {
        field_id: ConnectivityMetric(
            raw=value,
            normalized=math.log1p(value) / denominator if denominator > 0.0 else 0.0,
        )
        for field_id, value in raw.items()
    }
