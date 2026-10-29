from __future__ import annotations

from ..domain.models import DependencyEdge, HierarchyEdge, KnowledgeGraphInput, Relatedness, ResearchField
from ..domain.validation import validate_knowledge_graph
from .models import MathDataset
from .validation import validate_math_dataset


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
