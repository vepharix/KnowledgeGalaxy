from __future__ import annotations

import math
from collections.abc import Iterable

from ..domain.models import HierarchyEdge, ResearchField
from .models import Pair, ScopeMetric


def compute_transitive_membership(
    fields: Iterable[ResearchField],
    edges: Iterable[HierarchyEdge],
) -> dict[Pair, float]:
    """Compute the maximum-product broader-to-narrower path strength."""
    ids = [field.id for field in fields]
    index = {field_id: position for position, field_id in enumerate(ids)}
    count = len(ids)
    strength = [[0.0 for _ in range(count)] for _ in range(count)]
    for position in range(count):
        strength[position][position] = 1.0
    for edge in edges:
        broader = index[edge.broader]
        narrower = index[edge.narrower]
        strength[broader][narrower] = max(strength[broader][narrower], edge.value)

    for intermediate in range(count):
        for start in range(count):
            if strength[start][intermediate] == 0.0:
                continue
            for end in range(count):
                candidate = strength[start][intermediate] * strength[intermediate][end]
                if candidate > strength[start][end]:
                    strength[start][end] = candidate

    return {
        (broader, narrower): strength[index[broader]][index[narrower]]
        for broader in ids
        for narrower in ids
        if broader != narrower and strength[index[broader]][index[narrower]] > 0.0
    }


def compute_scope(
    fields: Iterable[ResearchField],
    membership: dict[Pair, float],
) -> dict[str, ScopeMetric]:
    ids = [field.id for field in fields]
    denominator = math.log1p(max(len(ids) - 1, 1))
    result: dict[str, ScopeMetric] = {}
    for field_id in ids:
        raw = sum(
            value
            for (broader, _), value in membership.items()
            if broader == field_id
        )
        result[field_id] = ScopeMetric(
            raw=raw,
            normalized=math.log1p(raw) / denominator if denominator else 0.0,
        )
    return result


def compute_member_sets(
    fields: Iterable[ResearchField],
    membership: dict[Pair, float],
) -> dict[str, tuple[str, ...]]:
    return {
        field.id: tuple(
            sorted(
                narrower
                for (broader, narrower), value in membership.items()
                if broader == field.id and value > 0.0
            )
        )
        for field in fields
    }
