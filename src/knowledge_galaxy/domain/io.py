from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import (
    DependencyEdge,
    HierarchyEdge,
    KnowledgeGraphInput,
    Relatedness,
    ResearchField,
)
from .validation import validate_knowledge_graph


def load_knowledge_graph(fields_path: Path, relations_path: Path) -> KnowledgeGraphInput:
    fields_payload = _read_object(fields_path)
    relations_payload = _read_object(relations_path)

    graph = KnowledgeGraphInput(
        fields=tuple(
            ResearchField(
                id=item["id"],
                name=item["name"],
                description=item["description"],
                emergence_time=item.get("emergence_time"),
                name_zh=item.get("name_zh"),
            )
            for item in fields_payload.get("fields", [])
        ),
        hierarchy=tuple(
            HierarchyEdge(
                broader=item["broader"],
                narrower=item["narrower"],
                value=float(item["value"]),
                provenance=item["provenance"],
            )
            for item in relations_payload.get("H", [])
        ),
        dependencies=tuple(
            DependencyEdge(
                foundation=item["foundation"],
                dependent=item["dependent"],
                value=float(item["value"]),
                provenance=item["provenance"],
            )
            for item in relations_payload.get("D", [])
        ),
        relatedness=tuple(
            Relatedness(
                left=item["left"],
                right=item["right"],
                value=float(item["value"]),
                provenance=item["provenance"],
            )
            for item in relations_payload.get("R", [])
        ),
        metadata={
            **fields_payload.get("metadata", {}),
            "relations": relations_payload.get("metadata", {}),
        },
    )
    validate_knowledge_graph(graph)
    return graph


def _read_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload
