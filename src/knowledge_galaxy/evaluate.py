from __future__ import annotations

from typing import Any

from .models import PairScores, score


def evaluate_anchors(
    scores: PairScores, triplets: list[dict[str, Any]]
) -> dict[str, Any]:
    cases = []
    for triplet in triplets:
        closer_score = score(scores, triplet["query"], triplet["closer"])
        farther_score = score(scores, triplet["query"], triplet["farther"])
        cases.append(
            {
                **triplet,
                "closerScore": closer_score,
                "fartherScore": farther_score,
                "margin": closer_score - farther_score,
                "passed": closer_score > farther_score,
            }
        )
    passed = sum(case["passed"] for case in cases)
    return {
        "passed": passed,
        "total": len(cases),
        "accuracy": passed / len(cases) if cases else None,
        "cases": cases,
    }


def largest_disagreements(
    model_scores: dict[str, PairScores], limit: int = 12
) -> list[dict[str, Any]]:
    if len(model_scores) < 2:
        return []
    pair_sets = [set(scores) for scores in model_scores.values()]
    common_pairs = set.intersection(*pair_sets)
    rows = []
    for left, right in common_pairs:
        values = {name: scores[(left, right)] for name, scores in model_scores.items()}
        rows.append(
            {
                "left": left,
                "right": right,
                "scores": values,
                "spread": max(values.values()) - min(values.values()),
            }
        )
    return sorted(rows, key=lambda row: (-row["spread"], row["left"], row["right"]))[:limit]


def nearest_neighbors(
    scores: PairScores, entity_ids: list[str], count: int = 3
) -> dict[str, list[dict[str, float | str]]]:
    return {
        entity_id: [
            {"id": other, "score": value}
            for other, value in sorted(
                (
                    (other, score(scores, entity_id, other))
                    for other in entity_ids
                    if other != entity_id
                ),
                key=lambda item: (-item[1], item[0]),
            )[:count]
        ]
        for entity_id in entity_ids
    }
