from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FormalSource:
    id: str
    repository: str
    revision: str
    toolchain: str


@dataclass(frozen=True)
class Declaration:
    id: str
    source_id: str
    name: str
    path: str
    blob_sha: str
    line_start: int
    line_end: int
    signature_excerpt: str


@dataclass(frozen=True)
class MathNode:
    id: str
    name: str
    name_zh: str
    description: str
    kind: str
    scope_note: str


@dataclass(frozen=True)
class Mapping:
    id: str
    node_id: str
    declaration_id: str
    role: str
    expression: str
    conditions: tuple[str, ...]
    caveats: tuple[str, ...]
    review_status: str
    reviewer: str
    review_note: str


@dataclass(frozen=True)
class RelationAssertion:
    id: str
    kind: str
    source: str
    target: str
    value: float | None
    status: str
    evidence_kind: str
    declaration_ids: tuple[str, ...]
    rationale: str
    reviewer: str
    dependency_extent: str | None = None


@dataclass(frozen=True)
class MathDataset:
    schema_version: str
    sources: tuple[FormalSource, ...]
    declarations: tuple[Declaration, ...]
    nodes: tuple[MathNode, ...]
    mappings: tuple[Mapping, ...]
    assertions: tuple[RelationAssertion, ...]
