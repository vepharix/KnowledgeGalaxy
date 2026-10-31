from __future__ import annotations

import json
import math
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from .models import MathDataset


DEPENDENCY_SCHEMA = "knowledge-galaxy.lean-dependencies.1"
DERIVATION_SCHEMA = "knowledge-galaxy.math-relation-candidates.1"


@dataclass(frozen=True)
class FormalDependency:
    """A declaration reference extracted from Lean, oriented prerequisite -> user."""

    source: str
    target: str
    reference_kind: str
    occurrences: int


@dataclass(frozen=True)
class DependencyExtraction:
    schema_version: str
    extractor: str
    toolchain: str
    source_revisions: tuple[tuple[str, str], ...]
    extraction_scope: str
    dependencies: tuple[FormalDependency, ...]


@dataclass(frozen=True)
class DerivationConfiguration:
    type_reference_weight: float = 1.0
    value_reference_weight: float = 0.35
    dependency_min_score: float = 0.2
    dependency_min_dominance: float = 0.6
    relatedness_min_score: float = 0.12
    relatedness_direct_weight: float = 0.35
    relatedness_prerequisite_weight: float = 0.25
    relatedness_dependent_weight: float = 0.25
    relatedness_anchor_weight: float = 0.15


ROLE_WEIGHTS = {
    "defining_expression": 1.0,
    "variant": 0.8,
    "value_operator": 0.65,
    "context": 0.5,
    "related_result": 0.4,
    "application": 0.35,
}


def load_dependency_extraction(path: Path, dataset: MathDataset) -> DependencyExtraction:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version", "extractor", "toolchain", "source_revisions",
        "extraction_scope", "dependencies",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError(f"{path}: expected exactly {sorted(expected)}")
    if not isinstance(payload["source_revisions"], dict):
        raise ValueError("source_revisions must be an object")
    if not isinstance(payload["dependencies"], list):
        raise ValueError("dependencies must be an array")
    try:
        extraction = DependencyExtraction(
            schema_version=payload["schema_version"],
            extractor=payload["extractor"],
            toolchain=payload["toolchain"],
            source_revisions=tuple(sorted(payload["source_revisions"].items())),
            extraction_scope=payload["extraction_scope"],
            dependencies=tuple(FormalDependency(**item) for item in payload["dependencies"]),
        )
    except (TypeError, KeyError) as error:
        raise ValueError(f"invalid dependency extraction: {error}") from error
    validate_dependency_extraction(extraction, dataset)
    return extraction


def validate_dependency_extraction(extraction: DependencyExtraction, dataset: MathDataset) -> None:
    if extraction.schema_version != DEPENDENCY_SCHEMA:
        raise ValueError("unsupported Lean dependency schema")
    if not all(isinstance(text, str) and text.strip() for text in (
        extraction.extractor, extraction.toolchain, extraction.extraction_scope,
    )):
        raise ValueError("dependency extraction metadata must be nonempty")
    expected_toolchains = {source.toolchain for source in dataset.sources}
    if expected_toolchains != {extraction.toolchain}:
        raise ValueError("dependency extraction toolchain does not match mathematics manifest")
    expected_revisions = {source.id: source.revision for source in dataset.sources}
    if dict(extraction.source_revisions) != expected_revisions:
        raise ValueError("dependency extraction revisions do not match mathematics manifest")
    observed: set[tuple[str, str, str]] = set()
    for edge in extraction.dependencies:
        if not all(isinstance(value, str) and value.strip() for value in (
            edge.source, edge.target, edge.reference_kind,
        )):
            raise ValueError("formal dependency names and kind must be nonempty")
        if edge.reference_kind not in {"type_reference", "value_reference"}:
            raise ValueError("formal dependency kind must be type_reference or value_reference")
        if type(edge.occurrences) is not int or edge.occurrences <= 0:
            raise ValueError("formal dependency occurrences must be a positive integer")
        key = (edge.source, edge.target, edge.reference_kind)
        if key in observed:
            raise ValueError("duplicate formal dependency")
        observed.add(key)


def derive_relation_candidates(
    dataset: MathDataset,
    extraction: DependencyExtraction,
    config: DerivationConfiguration | None = None,
    selected_node_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Aggregate a declaration graph into reviewable D/R candidates.

    The result deliberately does not create H and does not mutate assertions.  It is an
    evidence report for review, not a second graph ontology or an automatic truth source.
    """

    validate_dependency_extraction(extraction, dataset)
    config = config or DerivationConfiguration()
    _validate_configuration(config)
    all_node_ids = {node.id for node in dataset.nodes}
    if selected_node_ids is None:
        selected_node_ids = all_node_ids
    elif not selected_node_ids or not selected_node_ids <= all_node_ids:
        raise ValueError("selected mathematics nodes must be a nonempty subset of the dataset")
    declaration_names = {declaration.id: declaration.name for declaration in dataset.declarations}
    declaration_nodes: dict[str, list[tuple[str, float, str]]] = {}
    node_anchors: dict[str, dict[str, float]] = {}
    accepted_statuses = {"source_checked", "semantic_assessed"}
    for mapping in dataset.mappings:
        if mapping.node_id not in selected_node_ids:
            continue
        if mapping.review_status not in accepted_statuses:
            continue
        name = declaration_names[mapping.declaration_id]
        weight = ROLE_WEIGHTS[mapping.role]
        declaration_nodes.setdefault(name, []).append((mapping.node_id, weight, mapping.id))
        node_anchors.setdefault(mapping.node_id, {})[name] = max(
            weight, node_anchors.setdefault(mapping.node_id, {}).get(name, 0.0)
        )

    distinct_dependents: dict[str, set[str]] = {}
    for edge in extraction.dependencies:
        distinct_dependents.setdefault(edge.source, set()).add(edge.target)

    directional: dict[tuple[str, str], float] = {}
    support: dict[tuple[str, str], list[dict[str, Any]]] = {}
    prerequisites: dict[str, dict[str, float]] = {}
    dependents: dict[str, dict[str, float]] = {}
    kind_weights = {
        "type_reference": config.type_reference_weight,
        "value_reference": config.value_reference_weight,
    }
    used_edges = 0
    for edge in extraction.dependencies:
        source_nodes = declaration_nodes.get(edge.source, ())
        target_nodes = declaration_nodes.get(edge.target, ())
        if not source_nodes and not target_nodes:
            continue
        used_edges += 1
        hub_factor = 1.0 / math.sqrt(1.0 + math.log1p(len(distinct_dependents[edge.source])))
        occurrence_factor = 1.0 + math.log1p(edge.occurrences - 1)
        formal_weight = kind_weights[edge.reference_kind] * hub_factor * occurrence_factor
        for node, mapping_weight, _ in target_nodes:
            _add_feature(prerequisites, node, edge.source, formal_weight * mapping_weight)
        for node, mapping_weight, _ in source_nodes:
            _add_feature(dependents, node, edge.target, formal_weight * mapping_weight)
        for source_node, source_weight, source_mapping in source_nodes:
            for target_node, target_weight, target_mapping in target_nodes:
                if source_node == target_node:
                    continue
                pair = (source_node, target_node)
                contribution = formal_weight * source_weight * target_weight
                directional[pair] = directional.get(pair, 0.0) + contribution
                support.setdefault(pair, []).append({
                    "sourceDeclaration": edge.source,
                    "targetDeclaration": edge.target,
                    "referenceKind": edge.reference_kind,
                    "occurrences": edge.occurrences,
                    "sourceMapping": source_mapping,
                    "targetMapping": target_mapping,
                    "contribution": contribution,
                })

    dependencies: list[dict[str, Any]] = []
    unordered_directional = {tuple(sorted(pair)) for pair in directional}
    for left, right in sorted(unordered_directional):
        forward = directional.get((left, right), 0.0)
        reverse = directional.get((right, left), 0.0)
        total = forward + reverse
        if total <= 0:
            continue
        if forward >= reverse:
            source, target, raw, opposing = left, right, forward, reverse
        else:
            source, target, raw, opposing = right, left, reverse, forward
        dominance = raw / total
        score = _saturate(raw) * dominance
        if dominance < config.dependency_min_dominance or score < config.dependency_min_score:
            continue
        dependencies.append({
            "kind": "D",
            "source": source,
            "target": target,
            "score": score,
            "status": "candidate",
            "dependencyExtent": "unspecified",
            "components": {
                "formalReference": _saturate(raw),
                "opposingReference": _saturate(opposing),
                "directionDominance": dominance,
            },
            "support": sorted(
                support.get((source, target), []),
                key=lambda item: (-item["contribution"], item["sourceDeclaration"], item["targetDeclaration"]),
            ),
        })

    relatedness: list[dict[str, Any]] = []
    mapped_nodes = sorted(node_anchors)
    for left, right in combinations(mapped_nodes, 2):
        direct = _saturate(directional.get((left, right), 0.0) + directional.get((right, left), 0.0))
        shared_prerequisites = _weighted_jaccard(prerequisites.get(left, {}), prerequisites.get(right, {}))
        shared_dependents = _weighted_jaccard(dependents.get(left, {}), dependents.get(right, {}))
        shared_anchors = _weighted_jaccard(node_anchors[left], node_anchors[right])
        score = (
            config.relatedness_direct_weight * direct
            + config.relatedness_prerequisite_weight * shared_prerequisites
            + config.relatedness_dependent_weight * shared_dependents
            + config.relatedness_anchor_weight * shared_anchors
        )
        if score < config.relatedness_min_score:
            continue
        relatedness.append({
            "kind": "R",
            "source": left,
            "target": right,
            "score": score,
            "status": "candidate",
            "components": {
                "directFormalConnection": direct,
                "sharedPrerequisites": shared_prerequisites,
                "sharedDependents": shared_dependents,
                "sharedAnchors": shared_anchors,
            },
            "support": {
                "directDeclarationEdges": sorted(
                    support.get((left, right), []) + support.get((right, left), []),
                    key=lambda item: (-item["contribution"], item["sourceDeclaration"], item["targetDeclaration"]),
                ),
                "sharedPrerequisiteDeclarations": _shared_feature_names(
                    prerequisites.get(left, {}), prerequisites.get(right, {})
                ),
                "sharedDependentDeclarations": _shared_feature_names(
                    dependents.get(left, {}), dependents.get(right, {})
                ),
                "sharedAnchorDeclarations": _shared_feature_names(node_anchors[left], node_anchors[right]),
            },
        })

    return {
        "schemaVersion": DERIVATION_SCHEMA,
        "input": {
            "dependencySchema": extraction.schema_version,
            "extractor": extraction.extractor,
            "toolchain": extraction.toolchain,
            "sourceRevisions": dict(extraction.source_revisions),
            "extractionScope": extraction.extraction_scope,
            "formalDependencyCount": len(extraction.dependencies),
            "formalDependenciesTouchingMappedDeclarations": used_edges,
        },
        "policy": {
            "relationBoundary": "Only D and symmetric R candidates are derived. H is not inferred from declaration references.",
            "reviewBoundary": "All results are candidates; they do not enter layout until separately reviewed.",
            "direction": "A referenced declaration is oriented toward the declaration whose type or value contains it.",
            "hubControl": "Widely reused source declarations are downweighted by distinct dependent count.",
            "mappingStatuses": sorted(accepted_statuses),
        },
        "configuration": {
            "typeReferenceWeight": config.type_reference_weight,
            "valueReferenceWeight": config.value_reference_weight,
            "dependencyMinScore": config.dependency_min_score,
            "dependencyMinDominance": config.dependency_min_dominance,
            "relatednessMinScore": config.relatedness_min_score,
            "relatednessWeights": {
                "direct": config.relatedness_direct_weight,
                "sharedPrerequisites": config.relatedness_prerequisite_weight,
                "sharedDependents": config.relatedness_dependent_weight,
                "sharedAnchors": config.relatedness_anchor_weight,
            },
            "mappingRoleWeights": ROLE_WEIGHTS,
        },
        "coverage": {
            "selectedNodes": len(selected_node_ids),
            "mappedNodes": len(mapped_nodes),
            "unmappedNodes": sorted(node_id for node_id in selected_node_ids if node_id not in node_anchors),
        },
        "relations": {
            "D": dependencies,
            "R": relatedness,
            "H": [],
        },
    }


def load_node_selection(path: Path, dataset: MathDataset) -> tuple[str, set[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = {"experiment", "purpose", "nodes"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError(f"{path}: expected exactly {sorted(expected)}")
    if not isinstance(payload["experiment"], str) or not payload["experiment"].strip():
        raise ValueError("node selection experiment name is required")
    if not isinstance(payload["purpose"], str) or not payload["purpose"].strip():
        raise ValueError("node selection purpose is required")
    if not isinstance(payload["nodes"], list) or not all(
        isinstance(node_id, str) and node_id.strip() for node_id in payload["nodes"]
    ):
        raise ValueError("node selection must contain a JSON array of node ids")
    selected = set(payload["nodes"])
    if len(selected) != len(payload["nodes"]):
        raise ValueError("node selection contains duplicate ids")
    known = {node.id for node in dataset.nodes}
    unknown = sorted(selected - known)
    if unknown:
        raise ValueError(f"node selection contains unknown ids: {unknown}")
    if len(selected) < 2:
        raise ValueError("node selection requires at least two nodes")
    return payload["experiment"], selected


def compare_with_curated_baseline(
    dataset: MathDataset,
    report: dict[str, Any],
    selected_node_ids: set[str],
) -> dict[str, Any]:
    """Compare candidates with the current curated fixture without calling it ground truth."""

    curated_d = {
        (item.source, item.target)
        for item in dataset.assertions
        if item.kind == "D" and item.status == "curated" and item.value is not None
        and item.dependency_extent == "direct"
        and item.source in selected_node_ids and item.target in selected_node_ids
    }
    curated_r = {
        tuple(sorted((item.source, item.target)))
        for item in dataset.assertions
        if item.kind == "R" and item.status == "curated" and item.value is not None
        and item.source in selected_node_ids and item.target in selected_node_ids
    }
    candidate_d = {(item["source"], item["target"]) for item in report["relations"]["D"]}
    candidate_r = {
        tuple(sorted((item["source"], item["target"]))) for item in report["relations"]["R"]
    }
    return {
        "interpretation": (
            "Overlap with the current human-curated experimental baseline; this is not expert-validated ground truth."
        ),
        "D": _pair_comparison(curated_d, candidate_d),
        "R": _pair_comparison(curated_r, candidate_r),
    }


def _pair_comparison(
    baseline: set[tuple[str, str]],
    candidates: set[tuple[str, str]],
) -> dict[str, Any]:
    overlap = baseline & candidates
    return {
        "baselineCount": len(baseline),
        "candidateCount": len(candidates),
        "overlapCount": len(overlap),
        "candidatePrecisionAgainstBaseline": len(overlap) / len(candidates) if candidates else None,
        "baselineRecall": len(overlap) / len(baseline) if baseline else None,
        "overlap": [list(pair) for pair in sorted(overlap)],
        "candidateOnly": [list(pair) for pair in sorted(candidates - baseline)],
        "baselineOnly": [list(pair) for pair in sorted(baseline - candidates)],
    }


def _validate_configuration(config: DerivationConfiguration) -> None:
    values = tuple(config.__dict__.values())
    if not all(type(value) in {float, int} and math.isfinite(value) and value >= 0 for value in values):
        raise ValueError("derivation configuration values must be finite and nonnegative")
    relatedness_sum = (
        config.relatedness_direct_weight + config.relatedness_prerequisite_weight
        + config.relatedness_dependent_weight + config.relatedness_anchor_weight
    )
    if not math.isclose(relatedness_sum, 1.0):
        raise ValueError("relatedness component weights must sum to one")
    if config.dependency_min_dominance > 1 or config.dependency_min_score > 1 or config.relatedness_min_score > 1:
        raise ValueError("candidate thresholds must be in [0, 1]")


def _add_feature(features: dict[str, dict[str, float]], node: str, name: str, value: float) -> None:
    vector = features.setdefault(node, {})
    vector[name] = vector.get(name, 0.0) + value


def _weighted_jaccard(left: dict[str, float], right: dict[str, float]) -> float:
    keys = set(left) | set(right)
    if not keys:
        return 0.0
    denominator = sum(max(left.get(key, 0.0), right.get(key, 0.0)) for key in keys)
    if denominator == 0:
        return 0.0
    return sum(min(left.get(key, 0.0), right.get(key, 0.0)) for key in keys) / denominator


def _shared_feature_names(left: dict[str, float], right: dict[str, float]) -> list[str]:
    return sorted(set(left) & set(right))


def _saturate(value: float) -> float:
    return 1.0 - math.exp(-value)
