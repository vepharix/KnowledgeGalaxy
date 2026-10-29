from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path, PurePosixPath

from .models import MathDataset


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _unique(items: tuple, label: str) -> set[str]:
    ids = [x.id for x in items]
    _require(all(_text(x) for x in ids), f"{label}: nonempty ids required")
    _require(len(ids) == len(set(ids)), f"{label}: duplicate id")
    return set(ids)


def _has_cycle(pairs: list[tuple[str, str]]) -> bool:
    children: dict[str, list[str]] = {}
    for a, b in pairs:
        children.setdefault(a, []).append(b)
    state: dict[str, int] = {}

    def visit(node: str) -> bool:
        if state.get(node) == 1:
            return True
        if state.get(node) == 2:
            return False
        state[node] = 1
        if any(visit(child) for child in children.get(node, [])):
            return True
        state[node] = 2
        return False

    return any(visit(node) for node in list(children))


def validate_math_dataset(dataset: MathDataset) -> None:
    _require(dataset.schema_version == "knowledge-galaxy.math-alignment.1", "unsupported alignment schema")
    source_ids = _unique(dataset.sources, "sources")
    declaration_ids = _unique(dataset.declarations, "declarations")
    node_ids = _unique(dataset.nodes, "nodes")
    _unique(dataset.mappings, "mappings")
    _unique(dataset.assertions, "assertions")
    _require(bool(node_ids), "nodes: at least one node required")
    for source in dataset.sources:
        _require(source.repository == "https://github.com/leanprover-community/mathlib4", "unsupported formal source")
        _require(isinstance(source.revision, str) and bool(re.fullmatch(r"[0-9a-f]{40}", source.revision)), "source revision must be immutable SHA")
        _require(_text(source.toolchain), "source toolchain required")
    for declaration in dataset.declarations:
        _require(declaration.source_id in source_ids, "unknown declaration source")
        _require(_text(declaration.name) and _text(declaration.signature_excerpt), "declaration name and excerpt required")
        path = PurePosixPath(declaration.path)
        _require(not path.is_absolute() and ".." not in path.parts and declaration.path.startswith("Mathlib/") and declaration.path.endswith(".lean"), "unsafe declaration path")
        _require(bool(re.fullmatch(r"[0-9a-f]{40}", declaration.blob_sha)), "declaration blob SHA required")
        _require(type(declaration.line_start) is int and type(declaration.line_end) is int and 1 <= declaration.line_start <= declaration.line_end, "invalid source line range")
        _require(len(declaration.signature_excerpt.split("\n")) == declaration.line_end - declaration.line_start + 1, "excerpt line count mismatch")
    for node in dataset.nodes:
        _require(node.kind in {"field", "concept", "result"}, "invalid node kind")
        _require(all(_text(x) for x in (node.name, node.name_zh, node.description, node.scope_note)), "node metadata required")
    mapped: set[str] = set()
    for mapping in dataset.mappings:
        _require(mapping.node_id in node_ids and mapping.declaration_id in declaration_ids, "unknown mapping endpoint")
        _require(mapping.role in {"defining_expression", "variant", "value_operator", "related_result", "application", "context"}, "invalid mapping role")
        _require(mapping.review_status in {"candidate", "source_checked", "semantic_assessed"}, "invalid mapping review status")
        _require(all(_text(x) for x in (mapping.expression, mapping.reviewer, mapping.review_note)), "mapping expression and review required")
        _require(bool(mapping.conditions) and all(_text(x) for x in (*mapping.conditions, *mapping.caveats)), "mapping conditions must be explicit")
        mapped.add(mapping.node_id)
    _require(all(n.kind == "field" or n.id in mapped for n in dataset.nodes), "non-field node missing mapping")
    observed_pairs: set[tuple[str, str, str]] = set()
    active: dict[str, list[tuple[str, str]]] = {"H": [], "D": []}
    for assertion in dataset.assertions:
        _require(assertion.kind in {"H", "D", "R"}, "invalid relation kind")
        _require(assertion.source in node_ids and assertion.target in node_ids and assertion.source != assertion.target, "invalid assertion endpoints")
        _require(assertion.status in {"candidate", "curated", "rejected"}, "invalid assertion status")
        _require(assertion.evidence_kind in {"manual_classification", "curriculum_prerequisite", "definition_reference", "proof_reference", "module_import", "semantic_assessment"}, "invalid evidence kind")
        _require(all(_text(x) for x in (assertion.rationale, assertion.reviewer)), "assertion rationale and reviewer required")
        _require(set(assertion.declaration_ids) <= declaration_ids, "unknown assertion declaration")
        _require(assertion.value is None or (type(assertion.value) in {float, int} and math.isfinite(assertion.value) and 0 <= assertion.value <= 1), "assertion value must be null or finite in [0, 1]")
        if assertion.kind == "D":
            _require(assertion.dependency_extent in {"direct", "indirect", "unspecified"}, "D requires dependency extent")
        else:
            _require(assertion.dependency_extent is None, "only D has dependency extent")
        if assertion.status != "curated":
            continue
        _require(assertion.value is not None, "curated assertion cannot be unknown")
        _require(assertion.evidence_kind != "module_import", "module imports cannot directly establish curated relations")
        pair = tuple(sorted((assertion.source, assertion.target))) if assertion.kind == "R" else (assertion.source, assertion.target)
        key = (assertion.kind, *pair)
        _require(key not in observed_pairs, "duplicate curated relation")
        observed_pairs.add(key)
        if assertion.kind == "H" or (assertion.kind == "D" and assertion.dependency_extent == "direct"):
            if assertion.value > 0:
                active[assertion.kind].append((assertion.source, assertion.target))
    _require(not _has_cycle(active["H"]), "curated H contains cycle")
    _require(not _has_cycle(active["D"]), "direct D contains cycle; review aggregation before layout")


def verify_source_files(dataset: MathDataset, root: Path) -> int:
    """Verify pinned file bytes and exact excerpts. This does not run Lean."""
    checked: dict[str, list[str]] = {}
    expected: dict[str, str] = {}
    for declaration in dataset.declarations:
        _require(expected.setdefault(declaration.path, declaration.blob_sha) == declaration.blob_sha, "inconsistent source blobs for path")
        if declaration.path not in checked:
            path = (root / declaration.path).resolve()
            _require(path.is_relative_to(root.resolve()), "source path escapes root")
            raw = path.read_bytes()
            sha = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            _require(sha == declaration.blob_sha, f"source blob mismatch: {declaration.path}")
            checked[declaration.path] = raw.decode("utf-8").splitlines()
        lines = checked[declaration.path]
        excerpt = "\n".join(lines[declaration.line_start - 1:declaration.line_end])
        _require(excerpt == declaration.signature_excerpt, f"source excerpt mismatch: {declaration.id}")
    return len(dataset.declarations)
