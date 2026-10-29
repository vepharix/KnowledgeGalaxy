from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Declaration, FormalSource, Mapping, MathDataset, MathNode, RelationAssertion
from .validation import validate_math_dataset


def _records(root: Path, filename: str, key: str) -> list[dict[str, Any]]:
    payload = json.loads((root / filename).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != {key}:
        raise ValueError(f"{filename}: expected only '{key}'")
    if not isinstance(payload[key], list) or not all(isinstance(x, dict) for x in payload[key]):
        raise ValueError(f"{filename}: '{key}' must be a list of objects")
    return payload[key]


def _tuples(item: dict[str, Any], *keys: str) -> dict[str, Any]:
    result = dict(item)
    for key in keys:
        if not isinstance(item[key], list):
            raise ValueError(f"{key} must be a JSON array")
        result[key] = tuple(item[key])
    return result


def load_math_dataset(root: Path) -> MathDataset:
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "sources"}:
            raise ValueError("manifest.json: expected schema_version and sources")
        dataset = MathDataset(
            schema_version=manifest["schema_version"],
            sources=tuple(FormalSource(**x) for x in manifest["sources"]),
            declarations=tuple(Declaration(**x) for x in _records(root, "declarations.json", "declarations")),
            nodes=tuple(MathNode(**x) for x in _records(root, "nodes.json", "nodes")),
            mappings=tuple(Mapping(**_tuples(x, "conditions", "caveats"))
                           for x in _records(root, "mappings.json", "mappings")),
            assertions=tuple(RelationAssertion(**_tuples(x, "declaration_ids"))
                             for x in _records(root, "assertions.json", "assertions")),
        )
        validate_math_dataset(dataset)
        return dataset
    except (KeyError, TypeError) as error:
        raise ValueError(f"invalid mathematics dataset: {error}") from error
