from __future__ import annotations

import math
from dataclasses import replace
from itertools import combinations

from .adapter import to_graph_input
from .audit import audit_math_dataset
from .models import MathDataset
from ..graph_engine.build import build_graph
from ..graph_engine.models import GraphConfiguration
from ..export import snapshot_to_dict


def _pearson(a: list[float], b: list[float]) -> float | None:
    if len(a) < 2:
        return None
    am, bm = sum(a) / len(a), sum(b) / len(b)
    numerator = sum((x - am) * (y - bm) for x, y in zip(a, b))
    scale = math.sqrt(sum((x - am) ** 2 for x in a) * sum((y - bm) ** 2 for y in b))
    return numerator / scale if scale else None


def assess_layout_stability(dataset: MathDataset, seeds: tuple[int, ...], steps: int = 600, radius_scale: float = 1.0) -> dict:
    if len(seeds) < 2 or len(set(seeds)) != len(seeds) or steps <= 0 or not math.isfinite(radius_scale) or radius_scale <= 0:
        raise ValueError("assessment requires distinct seeds (at least two) and positive steps")
    graph = to_graph_input(dataset)
    ids = sorted(n.id for n in dataset.nodes)
    if len(ids) < 3:
        raise ValueError("assessment requires at least three nodes")
    k = min(5, len(ids) - 1)
    base = GraphConfiguration(optimization_steps=steps, density_grid_size=3)
    radius_max = base.radius_min + (base.radius_max - base.radius_min) * radius_scale
    snapshots = [build_graph(graph, replace(base, seed=seed, radius_max=radius_max)) for seed in seeds]
    neighborhoods = [{node: set(sorted((x for x in ids if x != node), key=lambda x: (math.dist(s.coordinates[node], s.coordinates[x]), x))[:k]) for node in ids} for s in snapshots]
    comparisons = []
    scores = {node: [] for node in ids}
    provided_pairs = sorted(tuple(sorted((r.left, r.right))) for r in graph.relatedness if r.value > 0)
    for i, j in combinations(range(len(seeds)), 2):
        overlap = [len(neighborhoods[i][node] & neighborhoods[j][node]) / len(neighborhoods[i][node] | neighborhoods[j][node]) for node in ids]
        for node, value in zip(ids, overlap):
            scores[node].append(value)
        distance_vectors = [[math.dist(s.coordinates[a], s.coordinates[b]) for a, b in combinations(ids, 2)] for s in (snapshots[i], snapshots[j])]
        provided_vectors = [[math.dist(s.coordinates[a], s.coordinates[b]) for a, b in provided_pairs] for s in (snapshots[i], snapshots[j])]
        comparisons.append({"seeds": [seeds[i], seeds[j]], "meanNeighborJaccard": sum(overlap) / len(overlap),
                            "minimumNeighborJaccard": min(overlap), "pairwiseDistancePearson": _pearson(*distance_vectors),
                            "providedRDistancePearson": _pearson(*provided_vectors),
                            "leastStableNodes": sorted([
                                {"id": node, "neighborJaccard": value,
                                 "firstNeighbors": sorted(neighborhoods[i][node]), "secondNeighbors": sorted(neighborhoods[j][node])}
                                for node, value in zip(ids, overlap)
                            ], key=lambda item: (item["neighborJaccard"], item["id"]))[:10]})
    relation_counts = {node: sum(r.value > 0 and node in (r.left, r.right) for r in graph.relatedness) for node in ids}
    kinds = {n.id: n.kind for n in dataset.nodes}
    return {
        "schemaVersion": "knowledge-galaxy.layout-assessment.1", "stepsPerSeed": steps,
        "graphInputDigest": audit_math_dataset(dataset)["graphInputDigest"],
        "radiusSpanFraction": radius_scale,
        "neighborCount": k, "comparisons": comparisons,
        "leastStableNodes": sorted([
            {"id": node, "kind": kinds[node], "meanNeighborJaccard": sum(values) / len(values),
             "minimumNeighborJaccard": min(values), "providedPositiveRNeighbors": relation_counts[node]}
            for node, values in scores.items()
        ], key=lambda item: (item["meanNeighborJaccard"], item["id"]))[:20],
        "runs": [{"seed": seed, "loss": s.diagnostics.loss.to_dict(), "coordinateFinite": s.diagnostics.coordinate_finite,
                  "depthRadiusPearson": s.diagnostics.depth_radius_pearson} for seed, s in zip(seeds, snapshots)],
        "interpretation": "Exploratory fixed-budget multi-seed assessment; does not establish convergence, semantic correctness, or stability under future graph growth. Distance and neighborhood comparisons are invariant to rigid rotation/reflection.",
    }


def assess_radius_scale_tradeoffs(dataset: MathDataset, fractions: tuple[float, ...], steps: int = 600, seed: int = 20260816) -> dict:
    if not fractions or len(set(fractions)) != len(fractions) or any(not math.isfinite(x) or x <= 0 for x in fractions) or steps <= 0:
        raise ValueError("radius assessment requires distinct positive finite scales and positive steps")
    graph = to_graph_input(dataset)
    base = GraphConfiguration(seed=seed, optimization_steps=steps, density_grid_size=3)
    span = base.radius_max - base.radius_min
    runs = []
    for fraction in fractions:
        config = replace(base, radius_max=base.radius_min + span * fraction)
        snapshot = build_graph(graph, config)
        audit = audit_math_dataset(dataset, snapshot_to_dict(snapshot))
        runs.append({
            "radiusSpanFraction": fraction, "radiusMax": config.radius_max,
            "providedRWeightedDistanceRMSE": audit["layout"]["providedRWeightedDistanceRMSE"],
            "providedRNormalizedStress": audit["layout"]["providedRNormalizedStress"],
            "incompatibleTargetPairs": audit["layout"]["radialDistanceTargetConflicts"]["count"],
            "targetRadiusMAE": snapshot.diagnostics.target_radius_mean_absolute_error,
            "targetRadiusMAEOverSpan": snapshot.diagnostics.target_radius_mean_absolute_error / (span * fraction),
            "minimumPairDistance": snapshot.diagnostics.minimum_pair_distance,
            "depthRadiusPearson": snapshot.diagnostics.depth_radius_pearson,
            "weightedRepulsionLoss": snapshot.diagnostics.loss.weighted_repel,
            "coordinateFinite": snapshot.diagnostics.coordinate_finite,
        })
    return {
        "schemaVersion": "knowledge-galaxy.radius-scale-assessment.1",
        "graphInputDigest": audit_math_dataset(dataset)["graphInputDigest"],
        "seed": seed, "stepsPerScale": steps, "baseConfiguration": base.to_dict(), "runs": runs,
        "interpretation": "Controlled fixed-budget comparison: only radius_max changes. Reports distance fit, radial error and crowding together; no configuration is selected or written back. Removing pairwise radius-distance conflicts does not prove global geometric feasibility.",
    }
