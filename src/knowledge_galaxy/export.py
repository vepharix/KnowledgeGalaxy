from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .graph_engine.models import GraphSnapshot


def snapshot_to_dict(snapshot: GraphSnapshot) -> dict[str, Any]:
    source = snapshot.source
    nodes = []
    for field in source.fields:
        metrics = snapshot.nodes[field.id]
        coordinate = snapshot.coordinates[field.id]
        nodes.append(
            {
                "id": field.id,
                "name": field.name,
                "nameZh": field.name_zh,
                "description": field.description,
                "emergenceTime": field.emergence_time,
                "coordinate": {"x": coordinate[0], "y": coordinate[1], "z": coordinate[2]},
                "dependencyDepthRaw": metrics.dependency_depth.raw,
                "dependencyDepthNormalized": metrics.dependency_depth.normalized,
                "targetRadius": metrics.target_radius,
                "actualRadius": metrics.actual_radius,
                "scopeRaw": metrics.scope.raw,
                "scopeNormalized": metrics.scope.normalized,
                "connectivityRaw": metrics.connectivity.raw,
                "connectivityNormalized": metrics.connectivity.normalized,
            }
        )

    return {
        "schemaVersion": "knowledge-galaxy.graph.1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "metadata": source.metadata,
        "configuration": snapshot.configuration.to_dict(),
        "interpretationBoundary": {
            "entity": "Every visible node is a ResearchField.",
            "coordinates": "Coordinates are derived layout output and cannot establish H, D or R.",
            "hierarchy": "H affects membership, Scope and post-layout regions, never coordinates or node size.",
            "dependency": "D affects dependency depth, target radius and connectivity, never pair distance.",
            "relatedness": "R alone controls desired pair distance and relatedness-loss weight.",
            "connectivity": "Connectivity controls diagnostic node size and is absent from coordinate optimization.",
            "emergenceTime": "Emergence time is metadata and is absent from the current layout.",
        },
        "nodes": nodes,
        "H": [
            {
                "broader": edge.broader,
                "narrower": edge.narrower,
                "value": edge.value,
                "provenance": edge.provenance,
            }
            for edge in source.hierarchy
        ],
        "transitiveMembership": [
            {"broader": broader, "narrower": narrower, "value": value}
            for (broader, narrower), value in sorted(snapshot.transitive_membership.items())
        ],
        "hierarchyMembers": snapshot.hierarchy_members,
        "D": [
            {
                "foundation": edge.foundation,
                "dependent": edge.dependent,
                "value": edge.value,
                "provenance": edge.provenance,
            }
            for edge in source.dependencies
        ],
        "R": [
            {
                "left": min(relation.left, relation.right),
                "right": max(relation.left, relation.right),
                "value": relation.value,
                "provenance": relation.provenance,
            }
            for relation in source.relatedness
        ],
        "layoutPairs": [
            {
                "left": pair.left,
                "right": pair.right,
                "relatedness": pair.relatedness,
                "weight": pair.weight,
                "desiredDistance": pair.desired_distance,
                "actualDistance": pair.actual_distance,
            }
            for pair in snapshot.layout_pairs
        ],
        "hierarchyRegions": snapshot.hierarchy_regions,
        "diagnostics": {
            "loss": snapshot.diagnostics.loss.to_dict(),
            "optimizationTrace": snapshot.diagnostics.optimization_trace,
            "depthRadiusPearson": snapshot.diagnostics.depth_radius_pearson,
            "targetRadiusMeanAbsoluteError": (
                snapshot.diagnostics.target_radius_mean_absolute_error
            ),
            "minimumPairDistance": snapshot.diagnostics.minimum_pair_distance,
            "coordinateFinite": snapshot.diagnostics.coordinate_finite,
        },
    }


def write_diagnostic_data(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"window.KNOWLEDGE_GALAXY_SNAPSHOT = {encoded};\n",
        encoding="utf-8",
    )
