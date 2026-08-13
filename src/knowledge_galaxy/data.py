from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DataValidationError(ValueError):
    """Raised when a research input violates the thin-slice contract."""


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise DataValidationError(f"{path}: top-level JSON value must be an object")
    return value


def validate_dataset(dataset: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    entities = dataset.get("entities")
    sources = dataset.get("sources")
    if not isinstance(entities, list) or not entities:
        return ["entities must be a non-empty list"]
    if not isinstance(sources, list):
        return ["sources must be a list"]

    source_ids = _unique_ids(sources, "source", errors)
    entity_ids = _unique_ids(entities, "entity", errors)
    allowed_roles = {
        "math_concept",
        "theorem_structure_method",
        "theoretical_physics_boundary",
    }
    for index, entity in enumerate(entities):
        prefix = f"entities[{index}]"
        if not isinstance(entity, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in (
            "id",
            "nameEn",
            "nameZh",
            "publicDefinitionEn",
            "sampleRole",
            "sourceRefs",
            "granularityNote",
            "status",
        ):
            if not entity.get(field):
                errors.append(f"{prefix}.{field} is required")
        if entity.get("sampleRole") not in allowed_roles:
            errors.append(f"{prefix}.sampleRole is not an allowed sampling role")
        refs = entity.get("sourceRefs", [])
        if not isinstance(refs, list):
            errors.append(f"{prefix}.sourceRefs must be a list")
        else:
            for ref in refs:
                if ref not in source_ids:
                    errors.append(f"{prefix}.sourceRefs contains unknown source {ref!r}")
        if not isinstance(entity.get("definitionMayBeSentExternally"), bool):
            errors.append(f"{prefix}.definitionMayBeSentExternally must be boolean")
        disciplines = entity.get("disciplines")
        if not isinstance(disciplines, list) or not disciplines:
            errors.append(f"{prefix}.disciplines must be a non-empty list")

    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            continue
        for field in ("id", "title", "url", "license", "usage", "accessedAt"):
            if not source.get(field):
                errors.append(f"sources[{index}].{field} is required")
    if len(entity_ids) != len(entities):
        errors.append("every entity must have a unique id")
    return errors


def validate_anchors(anchors: dict[str, Any], entity_ids: set[str]) -> list[str]:
    errors: list[str] = []
    triplets = anchors.get("triplets")
    if not isinstance(triplets, list) or not triplets:
        return ["triplets must be a non-empty list"]
    for index, triplet in enumerate(triplets):
        if not isinstance(triplet, dict):
            errors.append(f"triplets[{index}] must be an object")
            continue
        ids = [triplet.get(key) for key in ("query", "closer", "farther")]
        if len(set(ids)) != 3:
            errors.append(f"triplets[{index}] must reference three distinct entities")
        for key, value in zip(("query", "closer", "farther"), ids):
            if value not in entity_ids:
                errors.append(f"triplets[{index}].{key} references unknown entity {value!r}")
        if not triplet.get("rationaleZh"):
            errors.append(f"triplets[{index}].rationaleZh is required")
    return errors


def validate_files(dataset_path: Path, anchors_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    dataset = load_json(dataset_path)
    anchors = load_json(anchors_path)
    errors = validate_dataset(dataset)
    entity_ids = {item.get("id") for item in dataset.get("entities", []) if isinstance(item, dict)}
    errors.extend(validate_anchors(anchors, entity_ids))
    if errors:
        raise DataValidationError("\n".join(f"- {error}" for error in errors))
    return dataset, anchors


def _unique_ids(items: list[Any], label: str, errors: list[str]) -> set[str]:
    ids: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not item.get("id"):
            errors.append(f"{label}[{index}].id is required")
            continue
        item_id = item["id"]
        if item_id in ids:
            errors.append(f"duplicate {label} id: {item_id}")
        ids.add(item_id)
    return ids
