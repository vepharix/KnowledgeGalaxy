"""Evidence and layout checks. Reports concerns without rewriting knowledge inputs."""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, deque
from itertools import combinations

from .adapter import to_graph_input
from .models import MathDataset
from ..graph_engine.dependency import compute_dependency_depth, target_radius
from ..graph_engine.models import GraphConfiguration
from ..graph_engine.relatedness import desired_distance, relatedness_weight


def _components(ids: list[str], pairs: list[tuple[str, str]]) -> list[list[str]]:
    neighbors = {node: set() for node in ids}
    for a, b in pairs:
        neighbors[a].add(b)
        neighbors[b].add(a)
    remaining = set(ids)
    groups = []
    while remaining:
        queue = [min(remaining)]
        found = set(queue)
        for node in queue:
            for other in sorted(neighbors[node] - found):
                found.add(other)
                queue.append(other)
        remaining -= found
        groups.append(sorted(found))
    return sorted(groups, key=lambda x: (-len(x), x))


def _graph_signature(nodes: list[str], hierarchy: list[tuple], dependencies: list[tuple], relatedness: list[tuple]) -> str:
    payload = [sorted(nodes), sorted(hierarchy), sorted(dependencies), sorted(relatedness)]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _alternative_path(children: dict[str, list[str]], start: str, end: str) -> list[str] | None:
    queue = deque([[start]])
    seen = {start}
    while queue:
        path = queue.popleft()
        for node in children[path[-1]]:
            if path[-1] == start and node == end:
                continue
            if node == end:
                return [*path, node]
            if node not in seen:
                seen.add(node)
                queue.append([*path, node])
    return None


def audit_math_dataset(dataset: MathDataset, snapshot: dict | None = None) -> dict:
    graph = to_graph_input(dataset)
    ids = [n.id for n in dataset.nodes]
    d_pairs = [(d.foundation, d.dependent) for d in graph.dependencies if d.value > 0]
    r_pairs = [(r.left, r.right) for r in graph.relatedness if r.value > 0]
    d_nodes = {x for pair in d_pairs for x in pair}
    r_nodes = {x for pair in r_pairs for x in pair}
    children = {node: [] for node in ids}
    for a, b in d_pairs:
        children[a].append(b)
    shortcuts = []
    for a, b in d_pairs:
        path = _alternative_path(children, a, b)
        if path:
            shortcuts.append({"foundation": a, "dependent": b, "alternativePath": path})

    h = [(e.broader, e.narrower, float(e.value)) for e in graph.hierarchy]
    d = [(e.foundation, e.dependent, float(e.value)) for e in graph.dependencies]
    r = [(*sorted((e.left, e.right)), float(e.value)) for e in graph.relatedness]
    signature = _graph_signature(ids, h, d, r)
    eta = GraphConfiguration().dependency_regularization_eta
    if snapshot is not None:
        if not isinstance(snapshot, dict) or not {"nodes", "H", "D", "R", "configuration"} <= snapshot.keys():
            raise ValueError("snapshot must contain nodes, H, D, R and configuration")
        snapshot_nodes = snapshot["nodes"]
        snapshot_ids = [n["id"] for n in snapshot_nodes]
        actual = _graph_signature(snapshot_ids,
            [(e["broader"], e["narrower"], float(e["value"])) for e in snapshot["H"]],
            [(e["foundation"], e["dependent"], float(e["value"])) for e in snapshot["D"]],
            [(*sorted((e["left"], e["right"])), float(e["value"])) for e in snapshot["R"]])
        if actual != signature:
            raise ValueError("snapshot graph inputs differ from current mathematics dataset")
        eta = snapshot["configuration"]["dependency_regularization_eta"]
        if type(eta) not in {int, float} or not math.isfinite(eta) or eta <= 0:
            raise ValueError("invalid snapshot dependency regularization")

    depth = compute_dependency_depth(graph.fields, graph.dependencies, eta)
    residuals = [{"foundation": a, "dependent": b, "weight": weight,
                  "depthDifference": depth[b].raw - depth[a].raw,
                  "residual": depth[b].raw - depth[a].raw - 1} for a, b, weight in d]
    residuals.sort(key=lambda e: (-abs(e["residual"]), e["foundation"], e["dependent"]))
    total_weight = sum(e["weight"] for e in residuals)
    regularization_probe = []
    for probe_eta in (eta / 10, eta, eta * 10):
        probe = depth if probe_eta == eta else compute_dependency_depth(graph.fields, graph.dependencies, probe_eta)
        regularization_probe.append({
            "eta": probe_eta,
            "rawDepthRange": max(m.raw for m in probe.values()) - min(m.raw for m in probe.values()),
            "weightedResidualRMSE": math.sqrt(sum(weight * (probe[b].raw - probe[a].raw - 1) ** 2 for a, b, weight in d) / total_weight) if total_weight else None,
        })
    mapped = {m.node_id for m in dataset.mappings}
    substantive = {m.node_id for m in dataset.mappings if m.role not in {"context", "application"}}
    total_pairs = len(ids) * (len(ids) - 1) // 2
    report = {
        "schemaVersion": "knowledge-galaxy.math-audit.1",
        "graphInputDigest": signature,
        "counts": {"nodes": len(ids), "nodeKinds": dict(Counter(n.kind for n in dataset.nodes)),
                   "H": len(h), "D": len(d), "R": len(r)},
        "evidence": {
            "unmappedNonFields": [n.id for n in dataset.nodes if n.kind != "field" and n.id not in mapped],
            "contextOnlyNodes": [n.id for n in dataset.nodes if n.kind != "field" and n.id in mapped and n.id not in substantive],
            "mappingReviewStates": dict(Counter(m.review_status for m in dataset.mappings)),
            "relationEvidenceKinds": dict(Counter(a.evidence_kind for a in dataset.assertions if a.status == "curated")),
            "unknownAssertions": [a.id for a in dataset.assertions if a.value is None],
            "curatedRPairFraction": len(r) / total_pairs if total_pairs else 0,
            "pairsWithoutCuratedR": total_pairs - len(r),
            "interpretation": "Missing R is unassessed, not evidence of unrelatedness. Manual weights are uncalibrated assumptions.",
        },
        "structure": {
            "relatednessComponents": _components(ids, r_pairs),
            "dependencyComponents": _components(ids, d_pairs),
            "nodesWithoutRelatedness": sorted(set(ids) - r_nodes),
            "nodesWithoutDependencyEvidence": sorted(set(ids) - d_nodes),
        },
        "dependency": {
            "regularizationEta": eta,
            "regularizationProbe": regularization_probe,
            "directEdgesWithAlternativePaths": shortcuts,
            "weightedDepthResidualRMSE": math.sqrt(sum(e["weight"] * e["residual"] ** 2 for e in residuals) / total_weight) if total_weight else None,
            "largestDepthResiduals": residuals[:12],
            "nonIncreasingDepthEdges": [e for e in residuals if e["weight"] > 0 and e["depthDifference"] <= 0],
            "interpretation": "Acyclicity does not guarantee all unit depth differences can hold simultaneously. No edge is removed by this audit.",
        },
        "formalVerification": "not_run",
    }
    if snapshot is not None:
        positions = {}
        for node in snapshot["nodes"]:
            point = tuple(node["coordinate"][axis] for axis in ("x", "y", "z"))
            if not all(type(value) in {float, int} and math.isfinite(value) for value in point):
                raise ValueError("snapshot coordinates must be finite numbers")
            positions[node["id"]] = point
        distances = {(a, b): math.dist(positions[a], positions[b]) for a, b in combinations(sorted(ids), 2)}
        provided = {tuple(sorted(pair)) for pair in r_pairs}
        unsupported = [{"left": a, "right": b, "distance": value} for (a, b), value in distances.items() if (a, b) not in provided]
        unsupported.sort(key=lambda e: (e["distance"], e["left"], e["right"]))
        configuration = snapshot["configuration"]
        if not isinstance(configuration, dict) or not all(type(v) in {int, float} and math.isfinite(v) for v in configuration.values()):
            raise ValueError("invalid snapshot configuration values")
        try:
            config = GraphConfiguration(**configuration)
        except TypeError as error:
            raise ValueError("invalid snapshot configuration fields") from error
        if not (0 < config.distance_min <= config.distance_max and config.distance_gamma > 0 and config.relatedness_beta > 0):
            raise ValueError("invalid snapshot relatedness configuration")
        if not (0 <= config.radius_min <= config.radius_max):
            raise ValueError("invalid snapshot radial configuration")
        distance_residuals = []
        target_conflicts = []
        for relation in graph.relatedness:
            if relation.value <= 0:
                continue
            pair = tuple(sorted((relation.left, relation.right)))
            target = desired_distance(relation.value, config)
            distance_residuals.append({"left": pair[0], "right": pair[1], "R": relation.value,
                "weight": relatedness_weight(relation.value, config), "actualDistance": distances[pair],
                "desiredDistance": target, "residual": distances[pair] - target})
            radial_bound = abs(target_radius(depth[pair[0]].normalized, config) - target_radius(depth[pair[1]].normalized, config))
            if radial_bound > target + 1e-9:
                target_conflicts.append({"left": pair[0], "right": pair[1], "R": relation.value,
                    "desiredDistance": target, "minimumDistanceFromTargetRadii": radial_bound,
                    "incompatibilityGap": radial_bound - target})
        distance_weight = sum(e["weight"] for e in distance_residuals)
        weighted_error = sum(e["weight"] * e["residual"] ** 2 for e in distance_residuals)
        normalization = sum(e["weight"] * e["desiredDistance"] ** 2 for e in distance_residuals)
        distance_residuals.sort(key=lambda e: (-abs(e["residual"]), e["left"], e["right"]))
        target_conflicts.sort(key=lambda e: (-e["incompatibilityGap"], e["left"], e["right"]))
        radius_probe = []
        for fraction in (.25, .5, 1.0):
            span = (config.radius_max - config.radius_min) * fraction
            gaps = [span * abs(depth[e["left"]].normalized - depth[e["right"]].normalized) - e["desiredDistance"] for e in distance_residuals]
            radius_probe.append({"radiusSpanFraction": fraction, "radiusMax": config.radius_min + span,
                "incompatiblePositiveRPairs": sum(gap > 1e-9 for gap in gaps), "maximumGap": max([0.0, *gaps])})
        report["layout"] = {
            "minimumPairDistance": min(distances.values(), default=None),
            "providedRWeightedDistanceRMSE": math.sqrt(weighted_error / distance_weight) if distance_weight else None,
            "providedRNormalizedStress": math.sqrt(weighted_error / normalization) if normalization else None,
            "largestProvidedRDistanceResiduals": distance_residuals[:12],
            "radialDistanceTargetConflicts": {"count": len(target_conflicts), "largestGaps": target_conflicts[:12],
                "radiusScaleProbe": radius_probe,
                "interpretation": "By the reverse triangle inequality, exact target radii require pair distance at least their absolute difference. These pairs cannot meet both targets exactly; the optimizer trades off soft losses. The probe changes no input, configuration or coordinates."},
            "closestPairsWithoutCuratedPositiveR": unsupported[:12],
            "interpretation": "Geometric neighbors without a provided positive R require review; proximity does not create a knowledge relation.",
        }
    return report
