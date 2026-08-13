from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .data import validate_files
from .evaluate import evaluate_anchors, largest_disagreements, nearest_neighbors
from .models import PairScores, default_models, pair_scores_from_dense_embeddings


def run_experiment(
    dataset_path: Path,
    anchors_path: Path,
    external_embeddings_path: Path | None = None,
) -> dict[str, Any]:
    dataset, anchors = validate_files(dataset_path, anchors_path)
    entities = dataset["entities"]
    entity_ids = [entity["id"] for entity in entities]
    texts = {
        entity["id"]: f'{entity["nameEn"]}. {entity["publicDefinitionEn"]}'
        for entity in entities
    }
    model_scores: dict[str, PairScores] = {}
    model_metadata: dict[str, dict[str, Any]] = {}
    for model in default_models():
        model_scores[model.name] = model.fit_pair_scores(texts)
        model_metadata[model.name] = {
            "version": model.version,
            "parameters": model.parameters,
            "execution": "local",
            "inputTrack": "text",
        }

    if external_embeddings_path:
        payload = _load_external_embeddings(external_embeddings_path, entity_ids)
        name = f'external:{payload["model"]}'
        model_scores[name] = pair_scores_from_dense_embeddings(payload["entityIds"], payload["embeddings"])
        model_metadata[name] = {
            "version": payload.get("providerVersion", "unspecified"),
            "parameters": {"dimensions": len(payload["embeddings"][0])},
            "execution": "external_comparison",
            "inputTrack": "text",
        }

    runs = {}
    for name, scores in model_scores.items():
        covered_ids = sorted({entity_id for pair in scores for entity_id in pair})
        compatible_triplets = [
            triplet
            for triplet in anchors["triplets"]
            if {triplet["query"], triplet["closer"], triplet["farther"]} <= set(covered_ids)
        ]
        runs[name] = {
            **model_metadata[name],
            "coveredEntityIds": covered_ids,
            "anchorEvaluation": evaluate_anchors(scores, compatible_triplets),
            "nearestNeighbors": nearest_neighbors(scores, covered_ids),
            "pairScores": [
                {"left": left, "right": right, "score": value}
                for (left, right), value in sorted(scores.items())
            ],
        }

    return {
        "schemaVersion": "0.1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "dataset": dataset["metadata"],
        "inputDigests": {
            "datasetSha256": _sha256(dataset_path),
            "anchorsSha256": _sha256(anchors_path),
        },
        "entityCount": len(entities),
        "entityNames": {
            entity["id"]: {"en": entity["nameEn"], "zh": entity["nameZh"]}
            for entity in entities
        },
        "samplingRoles": _role_counts(entities),
        "modelRuns": runs,
        "largestDisagreements": largest_disagreements(model_scores),
        "interpretationBoundary": {
            "track": "text",
            "excluded": ["metadata", "graph_structure", "radial_position", "visual_distance"],
            "noteZh": "这些结果只比较英文名称与定义文本，不代表先修、图连接性、基础性或未来视觉距离。"
        },
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _load_external_embeddings(path: Path, expected_ids: list[str]) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    supplied_ids = payload.get("entityIds")
    if not isinstance(supplied_ids, list) or not supplied_ids:
        raise ValueError("external embedding file requires a non-empty entityIds list")
    if len(set(supplied_ids)) != len(supplied_ids) or not set(supplied_ids) <= set(expected_ids):
        raise ValueError("external embedding entityIds must be a unique subset of dataset ids")
    if not payload.get("model") or not isinstance(payload.get("embeddings"), list):
        raise ValueError("external embedding file requires model and embeddings")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _role_counts(entities: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entity in entities:
        role = entity["sampleRole"]
        counts[role] = counts.get(role, 0) + 1
    return counts
