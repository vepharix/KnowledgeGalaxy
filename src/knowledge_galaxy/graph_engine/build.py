from __future__ import annotations

from ..domain.models import KnowledgeGraphInput
from .connectivity import compute_connectivity
from .dependency import compute_dependency_depth, target_radius
from .diagnostics import build_diagnostics, pair_distance, radial_distances
from .hierarchy import compute_member_sets, compute_scope, compute_transitive_membership
from .layout import optimize_layout
from .models import GraphConfiguration, GraphSnapshot, LayoutPair, NodeMetrics
from .regions import compute_hierarchy_regions
from .relatedness import build_layout_pairs


def build_graph(
    graph: KnowledgeGraphInput,
    config: GraphConfiguration | None = None,
) -> GraphSnapshot:
    """Run the graph engine without rendering or input-source assumptions."""
    config = config or GraphConfiguration()
    membership = compute_transitive_membership(graph.fields, graph.hierarchy)
    scope = compute_scope(graph.fields, membership)
    hierarchy_members = compute_member_sets(graph.fields, membership)
    depth = compute_dependency_depth(
        graph.fields,
        graph.dependencies,
        config.dependency_regularization_eta,
    )
    connectivity = compute_connectivity(graph.fields, graph.dependencies, graph.relatedness)
    layout_pairs = build_layout_pairs(graph.fields, graph.relatedness, config)
    coordinates, loss, trace = optimize_layout(graph.fields, depth, layout_pairs, config)
    actual_radii = radial_distances(coordinates)
    target_radii = {
        field.id: target_radius(depth[field.id].normalized, config)
        for field in graph.fields
    }
    measured_pairs = tuple(
        LayoutPair(
            left=pair.left,
            right=pair.right,
            relatedness=pair.relatedness,
            weight=pair.weight,
            desired_distance=pair.desired_distance,
            actual_distance=pair_distance(coordinates[pair.left], coordinates[pair.right]),
        )
        for pair in layout_pairs
    )
    regions = compute_hierarchy_regions(graph.fields, membership, coordinates, config)
    nodes = {
        field.id: NodeMetrics(
            scope=scope[field.id],
            dependency_depth=depth[field.id],
            target_radius=target_radii[field.id],
            actual_radius=actual_radii[field.id],
            connectivity=connectivity[field.id],
        )
        for field in graph.fields
    }
    diagnostics = build_diagnostics(
        tuple(field.id for field in graph.fields),
        depth,
        actual_radii,
        target_radii,
        measured_pairs,
        coordinates,
        loss,
        trace,
    )
    return GraphSnapshot(
        source=graph,
        configuration=config,
        transitive_membership=membership,
        hierarchy_members=hierarchy_members,
        nodes=nodes,
        coordinates=coordinates,
        layout_pairs=measured_pairs,
        hierarchy_regions=regions,
        diagnostics=diagnostics,
    )
