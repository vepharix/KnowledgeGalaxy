from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from .adapter import alignment_report, to_graph_input
from .assessment import assess_layout_stability
from .audit import audit_math_dataset
from .derivation import DERIVATION_SCHEMA
from .export import alignment_to_dict
from .models import MathDataset
from .validation import validate_math_dataset
from ..export import snapshot_to_dict
from ..graph_engine.build import build_graph
from ..graph_engine.models import GraphConfiguration


RELEASE_MANIFEST_SCHEMA = "knowledge-galaxy.math-release-manifest.1"
RELEASE_REPORT_SCHEMA = "knowledge-galaxy.math-release-report.1"


def load_release_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version", "release_id", "title", "status", "dataset_schema",
        "source_revisions", "expected_counts", "layout", "assessment", "boundaries",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError(f"{path}: release manifest must contain exactly {sorted(required)}")
    if payload["schema_version"] != RELEASE_MANIFEST_SCHEMA:
        raise ValueError("unsupported mathematics release manifest schema")
    if payload["status"] != "research_preview":
        raise ValueError("v0.1 release status must remain research_preview")
    if not isinstance(payload["boundaries"], list) or not payload["boundaries"] or not all(
        isinstance(item, str) and item.strip() for item in payload["boundaries"]
    ):
        raise ValueError("release boundaries must be a nonempty string array")
    return payload


def create_math_release(
    dataset: MathDataset,
    manifest: dict[str, Any],
    *,
    lean_candidates: dict[str, Any] | None = None,
    source_declarations_verified: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_math_dataset(dataset)
    _validate_manifest_against_dataset(dataset, manifest)
    graph = to_graph_input(dataset)
    layout = manifest["layout"]
    assessment = manifest["assessment"]
    config = replace(
        GraphConfiguration(),
        seed=_positive_int(layout, "seed"),
        optimization_steps=_positive_int(layout, "optimization_steps"),
    )
    snapshot = build_graph(graph, config)
    snapshot_payload = snapshot_to_dict(snapshot)
    snapshot_payload["formalAlignment"] = alignment_to_dict(dataset)
    audit = audit_math_dataset(dataset, snapshot_payload)
    stability = assess_layout_stability(
        dataset,
        tuple(_distinct_positive_ints(assessment, "seeds", minimum=2)),
        _positive_int(assessment, "steps"),
    )
    candidate_summary = _candidate_summary(lean_candidates, dataset) if lean_candidates else None
    gates = _release_gates(
        dataset,
        snapshot_payload,
        audit,
        stability,
        candidate_summary,
        source_declarations_verified,
    )
    report = {
        "schemaVersion": RELEASE_REPORT_SCHEMA,
        "releaseId": manifest["release_id"],
        "title": manifest["title"],
        "releaseStatus": manifest["status"],
        "publicScientificClaimReady": False,
        "graphInputDigest": audit["graphInputDigest"],
        "counts": audit["counts"],
        "alignment": alignment_report(dataset),
        "formalCandidateScope": candidate_summary,
        "gates": gates,
        "audit": audit,
        "stability": stability,
        "boundaries": list(manifest["boundaries"]),
        "interpretation": (
            "A reproducible project research preview. Passing engineering gates does not "
            "convert curated H/D/R values into objective measurements or expert consensus."
        ),
    }
    snapshot_payload["release"] = {
        "id": manifest["release_id"],
        "title": manifest["title"],
        "status": manifest["status"],
        "graphInputDigest": audit["graphInputDigest"],
        "publicScientificClaimReady": False,
        "gateSummary": _gate_counts(gates),
        "boundaries": list(manifest["boundaries"]),
    }
    return snapshot_payload, report


def _validate_manifest_against_dataset(dataset: MathDataset, manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != RELEASE_MANIFEST_SCHEMA:
        raise ValueError("unsupported mathematics release manifest schema")
    if manifest.get("dataset_schema") != dataset.schema_version:
        raise ValueError("release manifest dataset schema does not match")
    revisions = {source.id: source.revision for source in dataset.sources}
    if manifest.get("source_revisions") != revisions:
        raise ValueError("release manifest source revisions do not match")
    graph = to_graph_input(dataset)
    actual = {
        "nodes": len(dataset.nodes),
        "declarations": len(dataset.declarations),
        "mappings": len(dataset.mappings),
        "H": len(graph.hierarchy),
        "D": len(graph.dependencies),
        "R": len(graph.relatedness),
    }
    if manifest.get("expected_counts") != actual:
        raise ValueError(f"release manifest counts do not match dataset: {actual}")
    if manifest.get("status") != "research_preview":
        raise ValueError("release status must remain research_preview")


def _candidate_summary(report: dict[str, Any], dataset: MathDataset) -> dict[str, Any]:
    if report.get("schemaVersion") != DERIVATION_SCHEMA:
        raise ValueError("release Lean candidate report has unsupported schema")
    relations = report.get("relations")
    if not isinstance(relations, dict) or relations.get("H") != []:
        raise ValueError("release Lean candidate report must not derive H")
    known = {node.id for node in dataset.nodes}
    for kind in ("D", "R"):
        for item in relations.get(kind, []):
            if item.get("source") not in known or item.get("target") not in known:
                raise ValueError("release Lean candidate endpoint is outside mathematics dataset")
    coverage = report.get("coverage", {})
    return {
        "experiment": report.get("experiment"),
        "selectedNodes": coverage.get("selectedNodes"),
        "mappedSelectedNodes": coverage.get("mappedNodes"),
        "formalDependencies": report.get("input", {}).get("formalDependencyCount"),
        "candidateD": len(relations.get("D", [])),
        "candidateR": len(relations.get("R", [])),
        "baselineComparison": report.get("baselineComparison"),
        "interpretation": "Partial candidate evidence only; release coordinates still use curated direct D and curated H/R.",
    }


def _release_gates(
    dataset: MathDataset,
    snapshot: dict[str, Any],
    audit: dict[str, Any],
    stability: dict[str, Any],
    candidate_summary: dict[str, Any] | None,
    source_declarations_verified: int | None,
) -> list[dict[str, Any]]:
    evidence = audit["evidence"]
    structure = audit["structure"]
    conflicts = audit["layout"]["radialDistanceTargetConflicts"]["count"]
    minimum_jaccard = min(item["minimumNeighborJaccard"] for item in stability["comparisons"])
    gates = [
        _gate("dataset_contract", "pass", "Dataset schemas, endpoints, relation directions and acyclicity validate."),
        _gate("non_field_mapping_coverage", "pass" if not evidence["unmappedNonFields"] else "fail", evidence["unmappedNonFields"]),
        _gate("relatedness_connectivity", "pass" if len(structure["relatednessComponents"]) == 1 and not structure["nodesWithoutRelatedness"] else "fail", {
            "components": len(structure["relatednessComponents"]),
            "nodesWithoutRelatedness": structure["nodesWithoutRelatedness"],
        }),
        _gate("finite_coordinates", "pass" if snapshot["diagnostics"]["coordinateFinite"] else "fail", snapshot["diagnostics"]["coordinateFinite"]),
        _gate("source_bytes_and_locators", "pass" if source_declarations_verified == len(dataset.declarations) else "pending", {
            "verifiedDeclarations": source_declarations_verified,
            "expectedDeclarations": len(dataset.declarations),
        }),
        _gate("lean_candidate_coverage", "warning" if candidate_summary else "pending", candidate_summary or "No real Lean candidate report attached."),
        _gate("radial_distance_compatibility", "warning" if conflicts else "pass", {"incompatiblePositiveRPairs": conflicts}),
        _gate("multi_seed_local_stability", "warning" if minimum_jaccard < 0.5 else "pass", {"minimumFiveNeighborJaccard": minimum_jaccard}),
        _gate("independent_mathematical_expert_review", "pending", "No independent expert review has been recorded."),
        _gate("real_browser_visual_acceptance", "pending", "WebGL code and DOM contracts are tested; visual acceptance remains manual."),
    ]
    if any(item["status"] == "fail" for item in gates):
        raise ValueError("mathematics release has failed required gates")
    return gates


def _gate(name: str, status: str, detail: Any) -> dict[str, Any]:
    return {"name": name, "status": status, "detail": detail}


def _gate_counts(gates: list[dict[str, Any]]) -> dict[str, int]:
    return {status: sum(item["status"] == status for item in gates) for status in ("pass", "warning", "pending", "fail")}


def _positive_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if type(value) is not int or value <= 0:
        raise ValueError(f"release {key} must be a positive integer")
    return value


def _distinct_positive_ints(payload: dict[str, Any], key: str, minimum: int) -> list[int]:
    values = payload.get(key)
    if not isinstance(values, list) or len(values) < minimum or len(values) != len(set(values)) or any(type(value) is not int or value <= 0 for value in values):
        raise ValueError(f"release {key} must contain distinct positive integers")
    return values
