from __future__ import annotations

from ..domain.models import DependencyEdge, HierarchyEdge, KnowledgeGraphInput, Relatedness, ResearchField
from ..domain.validation import validate_knowledge_graph
from .models import MathDataset
from .validation import validate_math_dataset
from .derivation import DERIVATION_SCHEMA


def to_graph_input(dataset: MathDataset) -> KnowledgeGraphInput:
    """Explicit compatibility projection; source node kinds remain in metadata."""
    validate_math_dataset(dataset)
    hierarchy, dependencies, relatedness = [], [], []
    for item in dataset.assertions:
        if item.status != "curated" or item.value is None:
            continue
        provenance = f"mathematics-curated-assumption:{item.id}; {item.evidence_kind}; {item.rationale}"
        if item.kind == "H":
            hierarchy.append(HierarchyEdge(item.source, item.target, item.value, provenance))
        elif item.kind == "D" and item.dependency_extent == "direct":
            dependencies.append(DependencyEdge(item.source, item.target, item.value, provenance))
        elif item.kind == "R":
            relatedness.append(Relatedness(item.source, item.target, item.value, provenance))
    graph = KnowledgeGraphInput(
        fields=tuple(ResearchField(n.id, n.name, n.description, name_zh=n.name_zh) for n in dataset.nodes),
        hierarchy=tuple(hierarchy), dependencies=tuple(dependencies), relatedness=tuple(relatedness),
        metadata={
            "dataset": "mathematics",
            "nodeKinds": {n.id: n.kind for n in dataset.nodes},
            "entityInterpretation": "Mathematical fields, concepts and selected results projected into the existing ResearchField transport type; semantic kinds are retained in nodeKinds.",
            "relationPolicy": "Only curated H/R and curated direct D enter layout; unknown, candidate and indirect relations are excluded. Values are curator assumptions, not measurements or expert consensus.",
            "formalSources": [{"id": s.id, "repository": s.repository, "revision": s.revision, "toolchain": s.toolchain} for s in dataset.sources],
        },
    )
    validate_knowledge_graph(graph)
    return graph


def alignment_report(dataset: MathDataset) -> dict:
    graph = to_graph_input(dataset)
    mapped = {m.node_id for m in dataset.mappings}
    return {
        "schemaVersion": dataset.schema_version,
        "nodes": len(dataset.nodes), "declarations": len(dataset.declarations),
        "mappings": len(dataset.mappings),
        "unmappedFields": [n.id for n in dataset.nodes if n.id not in mapped],
        "graphRelations": {"H": len(graph.hierarchy), "D": len(graph.dependencies), "R": len(graph.relatedness)},
        "excludedAssertions": [a.id for a in dataset.assertions if a.status != "curated" or a.value is None or (a.kind == "D" and a.dependency_extent != "direct")],
        "mappingReview": {status: sum(m.review_status == status for m in dataset.mappings) for status in ("candidate", "source_checked", "semantic_assessed")},
        "formalVerification": "not_run",
    }


def derived_candidates_to_graph_input(
    dataset: MathDataset,
    report: dict,
    selected_node_ids: set[str],
) -> KnowledgeGraphInput:
    """Create an explicitly experimental graph from Lean-derived candidates."""

    validate_math_dataset(dataset)
    if report.get("schemaVersion") != DERIVATION_SCHEMA:
        raise ValueError("unsupported derived relation candidate schema")
    relations = report.get("relations")
    if not isinstance(relations, dict) or set(relations) != {"H", "D", "R"}:
        raise ValueError("derived relation report must contain H, D and R arrays")
    if relations["H"] != []:
        raise ValueError("Lean declaration references must not generate hierarchy H")
    known = {node.id for node in dataset.nodes}
    if not selected_node_ids or not selected_node_ids <= known:
        raise ValueError("derived experiment nodes must be a nonempty dataset subset")

    dependencies: list[DependencyEdge] = []
    relatedness: list[Relatedness] = []
    for kind, target in (("D", dependencies), ("R", relatedness)):
        if not isinstance(relations[kind], list):
            raise ValueError(f"derived {kind} candidates must be an array")
        for item in relations[kind]:
            if not isinstance(item, dict) or item.get("kind") != kind or item.get("status") != "candidate":
                raise ValueError(f"invalid derived {kind} candidate")
            source, destination, score = item.get("source"), item.get("target"), item.get("score")
            if source not in selected_node_ids or destination not in selected_node_ids:
                raise ValueError("derived relation endpoint escapes selected node experiment")
            if type(score) not in {float, int} or not 0 <= score <= 1:
                raise ValueError("derived relation score must be in [0, 1]")
            provenance = (
                f"lean-derived-candidate:{report.get('experiment', 'unnamed')}; "
                f"not curated; components={item.get('components', {})}"
            )
            if kind == "D":
                target.append(DependencyEdge(source, destination, score, provenance))
            else:
                target.append(Relatedness(source, destination, score, provenance))

    graph = KnowledgeGraphInput(
        fields=tuple(
            ResearchField(node.id, node.name, node.description, name_zh=node.name_zh)
            for node in dataset.nodes if node.id in selected_node_ids
        ),
        hierarchy=(),
        dependencies=tuple(dependencies),
        relatedness=tuple(relatedness),
        metadata={
            "dataset": "mathematics-lean-derived-experiment",
            "experiment": report.get("experiment"),
            "nodeKinds": {
                node.id: node.kind for node in dataset.nodes if node.id in selected_node_ids
            },
            "relationPolicy": (
                "Diagnostic layout from uncurated Lean-derived D/R candidates. "
                "H is intentionally absent and coordinates are not semantic validation."
            ),
            "formalInput": report.get("input", {}),
        },
    )
    validate_knowledge_graph(graph)
    return graph
