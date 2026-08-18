from __future__ import annotations

from collections.abc import Iterable

from .models import KnowledgeGraphInput


def validate_knowledge_graph(graph: KnowledgeGraphInput) -> None:
    if not graph.fields:
        raise ValueError("Knowledge Galaxy requires at least one ResearchField")

    ids = [field.id for field in graph.fields]
    if len(ids) != len(set(ids)):
        raise ValueError("ResearchField ids must be unique")
    id_set = set(ids)
    for field in graph.fields:
        if not field.id or not field.name or not field.description:
            raise ValueError("ResearchField id, name and description are required")
        if field.name_zh is not None and not field.name_zh.strip():
            raise ValueError("ResearchField name_zh must be non-empty when supplied")

    hierarchy_pairs: set[tuple[str, str]] = set()
    for edge in graph.hierarchy:
        _validate_edge(edge.broader, edge.narrower, edge.value, edge.provenance, id_set, "H")
        pair = (edge.broader, edge.narrower)
        if pair in hierarchy_pairs:
            raise ValueError(f"duplicate hierarchy edge: {pair}")
        hierarchy_pairs.add(pair)
    _reject_hierarchy_cycles(ids, hierarchy_pairs)

    dependency_pairs: set[tuple[str, str]] = set()
    for edge in graph.dependencies:
        _validate_edge(
            edge.foundation,
            edge.dependent,
            edge.value,
            edge.provenance,
            id_set,
            "D",
        )
        pair = (edge.foundation, edge.dependent)
        if pair in dependency_pairs:
            raise ValueError(f"duplicate dependency edge: {pair}")
        dependency_pairs.add(pair)

    relatedness_pairs: set[tuple[str, str]] = set()
    for relation in graph.relatedness:
        _validate_edge(
            relation.left,
            relation.right,
            relation.value,
            relation.provenance,
            id_set,
            "R",
        )
        pair = canonical_pair(relation.left, relation.right)
        if pair in relatedness_pairs:
            raise ValueError(f"duplicate symmetric relatedness pair: {pair}")
        relatedness_pairs.add(pair)


def canonical_pair(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left < right else (right, left)


def _validate_edge(
    left: str,
    right: str,
    value: float,
    provenance: str,
    ids: set[str],
    label: str,
) -> None:
    if left == right:
        raise ValueError(f"{label} self-edges are not allowed")
    if left not in ids or right not in ids:
        raise ValueError(f"{label} references an unknown ResearchField: {(left, right)}")
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{label} value must be in [0, 1]")
    if not provenance:
        raise ValueError(f"{label} requires provenance")


def _reject_hierarchy_cycles(ids: Iterable[str], pairs: set[tuple[str, str]]) -> None:
    children = {field_id: [] for field_id in ids}
    for broader, narrower in pairs:
        children[broader].append(narrower)

    state = {field_id: 0 for field_id in children}

    def visit(field_id: str) -> None:
        if state[field_id] == 1:
            raise ValueError("H must be acyclic because it represents a strict broader-to-narrower hierarchy")
        if state[field_id] == 2:
            return
        state[field_id] = 1
        for child in children[field_id]:
            visit(child)
        state[field_id] = 2

    for field_id in children:
        visit(field_id)
