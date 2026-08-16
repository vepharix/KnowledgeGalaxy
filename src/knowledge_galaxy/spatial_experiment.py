from __future__ import annotations

import hashlib
import html
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .spatial import (
    canonical_pair,
    compute_dependency_depth,
    compute_geometric_affinity,
    compute_hierarchy_regions,
    compute_scope,
    compute_transitive_membership,
    desired_distance,
    optimize_layout,
    radial_distances,
    target_radius,
)
from .spatial_schema import SpatialConfig, load_spatial_fixture


def run_spatial_experiment(
    fixture_path: Path,
    config: SpatialConfig | None = None,
) -> dict[str, Any]:
    config = config or SpatialConfig()
    fixture = load_spatial_fixture(fixture_path)
    membership = compute_transitive_membership(fixture.fields, fixture.hierarchy)
    scope = compute_scope(fixture.fields, membership)
    depth = compute_dependency_depth(
        fixture.fields,
        fixture.dependencies,
        config.dependency_regularization_eta,
    )
    affinities = compute_geometric_affinity(
        fixture.fields,
        fixture.dependencies,
        fixture.relatedness,
        config.dependency_affinity_lambda,
    )
    coordinates, losses, trace = optimize_layout(fixture.fields, depth, affinities, config)
    regions = compute_hierarchy_regions(fixture.fields, membership, coordinates, config)
    radii = radial_distances(coordinates)
    target_radii = {
        field.id: target_radius(depth[field.id]["normalized"], config)
        for field in fixture.fields
    }

    nodes = []
    for field in fixture.fields:
        nodes.append(
            {
                "id": field.id,
                "name": field.name,
                "description": field.description,
                "emergenceTime": field.emergence_time,
                "coordinate": {
                    "x": coordinates[field.id][0],
                    "y": coordinates[field.id][1],
                    "z": coordinates[field.id][2],
                },
                "scope": scope[field.id]["scope"],
                "scopeNormalized": scope[field.id]["normalized"],
                "dependencyDepth": depth[field.id]["raw"],
                "dependencyDepthNormalized": depth[field.id]["normalized"],
                "targetRadius": target_radii[field.id],
                "actualRadius": radii[field.id],
            }
        )

    geometric_pairs = []
    for pair, values in sorted(affinities.items()):
        geometric_pairs.append(
            {
                "left": pair[0],
                "right": pair[1],
                "R": values["relatedness"],
                "dependencyAffinity": values["dependencyAffinity"],
                "G": values["geometricAffinity"],
                "desiredDistance": desired_distance(values["geometricAffinity"], config),
                "actualDistance": _distance(coordinates[pair[0]], coordinates[pair[1]]),
            }
        )

    return {
        "schemaVersion": "research-field-spatial.1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "fixture": fixture.metadata,
        "fixtureSha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        "interpretationBoundary": {
            "entity": "Every node is a ResearchField in this experiment.",
            "coordinates": "Coordinates are derived visual-layout output, not hierarchy or semantic facts.",
            "hierarchy": "H affects Scope and post-layout density regions only; it is absent from coordinate optimization.",
            "emergenceTime": "Emergence time is preserved as metadata and is not read by the optimizer.",
        },
        "configuration": config.to_dict(),
        "nodes": nodes,
        "H": [
            {
                "broader": edge.broader,
                "narrower": edge.narrower,
                "value": edge.value,
                "provenance": edge.provenance,
            }
            for edge in fixture.hierarchy
        ],
        "transitiveMembership": [
            {"broader": broader, "narrower": narrower, "value": value}
            for (broader, narrower), value in sorted(membership.items())
        ],
        "D": [
            {
                "foundation": edge.foundation,
                "dependent": edge.dependent,
                "value": edge.value,
                "provenance": edge.provenance,
            }
            for edge in fixture.dependencies
        ],
        "R": [
            {
                "left": min(item.left, item.right),
                "right": max(item.left, item.right),
                "value": item.value,
                "provenance": item.provenance,
            }
            for item in fixture.relatedness
        ],
        "G": geometric_pairs,
        "hierarchyRegions": regions,
        "diagnostics": {
            "loss": losses,
            "optimizationTrace": trace,
            "depthRadiusPearson": _pearson(
                [depth[field.id]["normalized"] for field in fixture.fields],
                [radii[field.id] for field in fixture.fields],
            ),
            "targetRadiusMeanAbsoluteError": sum(
                abs(radii[field.id] - target_radii[field.id]) for field in fixture.fields
            )
            / len(fixture.fields),
            "minimumPairDistance": min(
                item["actualDistance"] for item in geometric_pairs
            ),
            "coordinateFinite": all(
                math.isfinite(value)
                for point in coordinates.values()
                for value in point
            ),
        },
    }


def render_spatial_svg(result: dict[str, Any], output_path: Path) -> None:
    width = 1500
    height = 980
    margin = 90
    nodes = result["nodes"]
    projected = {}
    for node in nodes:
        coordinate = node["coordinate"]
        projected[node["id"]] = _project(
            (coordinate["x"], coordinate["y"], coordinate["z"])
        )
    min_u = min(value[0] for value in projected.values())
    max_u = max(value[0] for value in projected.values())
    min_v = min(value[1] for value in projected.values())
    max_v = max(value[1] for value in projected.values())
    scale = min(
        (width - 2 * margin) / max(max_u - min_u, 1e-9),
        (height - 2 * margin) / max(max_v - min_v, 1e-9),
    )

    def screen(field_id: str) -> tuple[float, float, float]:
        u, v, depth = projected[field_id]
        return (
            margin + (u - min_u) * scale,
            height - margin - (v - min_v) * scale,
            depth,
        )

    field_screen = {node["id"]: screen(node["id"]) for node in nodes}
    lines = []
    for pair in result["G"]:
        if pair["G"] < 0.68:
            continue
        left = field_screen[pair["left"]]
        right = field_screen[pair["right"]]
        opacity = 0.10 + 0.35 * pair["G"]
        lines.append(
            f'<line x1="{left[0]:.1f}" y1="{left[1]:.1f}" x2="{right[0]:.1f}" '
            f'y2="{right[1]:.1f}" stroke="#577487" stroke-opacity="{opacity:.3f}" '
            f'stroke-width="{0.5 + 2.2 * pair["G"]:.2f}" />'
        )

    node_by_id = {node["id"]: node for node in nodes}
    circles = []
    labels = []
    for field_id, (x, y, depth_order) in sorted(
        field_screen.items(), key=lambda item: item[1][2]
    ):
        node = node_by_id[field_id]
        normalized_depth = node["dependencyDepthNormalized"]
        red = round(48 + 190 * normalized_depth)
        green = round(125 - 45 * normalized_depth)
        blue = round(180 - 100 * normalized_depth)
        radius = 5.0 + 8.0 * node["scopeNormalized"]
        circles.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" '
            f'fill="rgb({red},{green},{blue})" stroke="#ffffff" stroke-width="1.8">'
            f'<title>{html.escape(node["name"])} | q={normalized_depth:.3f} | '
            f'r={node["actualRadius"]:.3f}</title></circle>'
        )
        labels.append(
            f'<text x="{x + radius + 4:.1f}" y="{y + 4:.1f}" '
            f'font-size="13" fill="#162126">{html.escape(node["name"])}</text>'
        )

    document = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="#f5f8f8" />
<text x="55" y="45" font-family="system-ui, sans-serif" font-size="25" font-weight="650" fill="#162126">New Synapse — first deterministic 3D experiment</text>
<text x="55" y="70" font-family="system-ui, sans-serif" font-size="13" fill="#607078">Color: dependency depth (blue inner → red outer); size: derived hierarchy Scope; lines: G ≥ 0.68. SVG is a 2D camera projection of 3D coordinates.</text>
<g>{''.join(lines)}</g>
<g>{''.join(circles)}</g>
<g font-family="system-ui, sans-serif">{''.join(labels)}</g>
<g transform="translate(55 900)" font-family="system-ui, sans-serif">
  <circle cx="10" cy="10" r="7" fill="rgb(48,125,180)"/><text x="23" y="15" font-size="13">low dependency depth / target inner region</text>
  <circle cx="340" cy="10" r="7" fill="rgb(238,80,80)"/><text x="353" y="15" font-size="13">high dependency depth / target outer region</text>
</g>
</svg>'''
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")


def _project(point: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = point
    azimuth = math.radians(-35.0)
    elevation = math.radians(25.0)
    horizontal = x * math.cos(azimuth) - y * math.sin(azimuth)
    away = x * math.sin(azimuth) + y * math.cos(azimuth)
    vertical = away * math.cos(elevation) - z * math.sin(elevation)
    depth = away * math.sin(elevation) + z * math.cos(elevation)
    return horizontal, vertical, depth


def _distance(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return math.sqrt(sum((left[axis] - right[axis]) ** 2 for axis in range(3)))


def _pearson(left: list[float], right: list[float]) -> float:
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_variance = sum((value - left_mean) ** 2 for value in left)
    right_variance = sum((value - right_mean) ** 2 for value in right)
    denominator = math.sqrt(left_variance * right_variance)
    return numerator / denominator if denominator > 1e-15 else 0.0
