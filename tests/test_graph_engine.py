from __future__ import annotations

import inspect
import json
import math
import tempfile
import unittest
from pathlib import Path

from knowledge_galaxy.domain.io import load_knowledge_graph
from knowledge_galaxy.domain.models import (
    DependencyEdge,
    HierarchyEdge,
    KnowledgeGraphInput,
    Relatedness,
    ResearchField,
)
from knowledge_galaxy.domain.validation import validate_knowledge_graph
from knowledge_galaxy.export import snapshot_to_dict, write_diagnostic_data
from knowledge_galaxy.graph_engine.build import build_graph
from knowledge_galaxy.graph_engine.connectivity import (
    compute_connectivity,
    compute_pair_connectivity,
)
from knowledge_galaxy.graph_engine.dependency import (
    compute_dependency_depth,
    dependency_constraint,
    target_radius,
)
from knowledge_galaxy.graph_engine.hierarchy import (
    compute_scope,
    compute_transitive_membership,
)
from knowledge_galaxy.graph_engine.layout import optimize_layout
from knowledge_galaxy.graph_engine.models import GraphConfiguration
from knowledge_galaxy.graph_engine.relatedness import (
    build_layout_pairs,
    desired_distance,
    relatedness_values,
)


ROOT = Path(__file__).resolve().parents[1]
FIELDS_PATH = ROOT / "data/fields.json"
RELATIONS_PATH = ROOT / "data/relations.json"
VIEWER_INDEX = ROOT / "apps/diagnostic-viewer/index.html"
VIEWER_SCRIPT = ROOT / "apps/diagnostic-viewer/app.js"
PROVENANCE = "unit-test-assumption"


class GraphEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fields = tuple(
            ResearchField(field_id, field_id.upper(), f"Description of {field_id}")
            for field_id in ("a", "b", "c", "d")
        )

    def test_current_data_loads_with_reviewed_field_set(self) -> None:
        graph = load_knowledge_graph(FIELDS_PATH, RELATIONS_PATH)
        ids = {field.id for field in graph.fields}
        self.assertEqual(len(ids), 150)
        self.assertTrue(
            {
                "mathematics",
                "machine-learning",
                "large-language-models",
                "network-science",
                "climate-science",
                "bioinformatics",
                "cognitive-science",
                "computational-social-science",
                "formal-sciences",
                "natural-sciences",
                "social-sciences",
                "humanities",
                "engineering",
                "health-sciences",
                "logic",
                "calculus",
                "astronomy",
                "environmental-science",
                "public-health",
                "ethics",
                "graph-theory",
                "distributed-systems",
                "particle-physics",
                "organic-chemistry",
                "genomics",
                "oncology",
                "biomedical-engineering",
                "archaeology",
                "finance",
            }
            <= ids
        )
        self.assertEqual(len(graph.hierarchy), 205)
        self.assertEqual(len(graph.dependencies), 314)
        self.assertEqual(len(graph.relatedness), 492)
        self.assertTrue(all(field.name_zh for field in graph.fields))
        related_nodes = {
            field_id
            for relation in graph.relatedness
            for field_id in (relation.left, relation.right)
        }
        self.assertEqual(related_nodes, ids)
        for relation in (*graph.hierarchy, *graph.dependencies, *graph.relatedness):
            self.assertIn("assumption", relation.provenance)
            self.assertNotIn("curated-v0", relation.provenance)

    def test_relatedness_is_symmetric_but_dependency_remains_directed(self) -> None:
        relations = (Relatedness("b", "a", 0.7, PROVENANCE),)
        values = relatedness_values(relations)
        self.assertEqual(values[("a", "b")], 0.7)
        dependencies = (DependencyEdge("a", "b", 0.8, PROVENANCE),)
        directed = {(edge.foundation, edge.dependent): edge.value for edge in dependencies}
        self.assertEqual(directed[("a", "b")], 0.8)
        self.assertNotIn(("b", "a"), directed)

    def test_hierarchy_uses_max_product_and_scope_is_derived(self) -> None:
        hierarchy = (
            HierarchyEdge("a", "b", 0.8, PROVENANCE),
            HierarchyEdge("b", "c", 0.5, PROVENANCE),
            HierarchyEdge("a", "c", 0.3, PROVENANCE),
        )
        membership = compute_transitive_membership(self.fields, hierarchy)
        self.assertAlmostEqual(membership[("a", "c")], 0.4)
        scope = compute_scope(self.fields, membership)
        self.assertAlmostEqual(scope["a"].raw, 1.2)
        self.assertGreater(scope["a"].normalized, scope["b"].normalized)

    def test_hierarchy_cycles_are_rejected(self) -> None:
        graph = self._graph(
            hierarchy=(
                HierarchyEdge("a", "b", 1.0, PROVENANCE),
                HierarchyEdge("b", "a", 1.0, PROVENANCE),
            )
        )
        with self.assertRaisesRegex(ValueError, "acyclic"):
            validate_knowledge_graph(graph)

    def test_dependency_depth_and_target_radius_increase_along_chain(self) -> None:
        dependencies = (
            DependencyEdge("a", "b", 1.0, PROVENANCE),
            DependencyEdge("b", "c", 1.0, PROVENANCE),
            DependencyEdge("c", "d", 1.0, PROVENANCE),
        )
        depth = compute_dependency_depth(self.fields, dependencies, eta=0.1)
        normalized = [depth[field_id].normalized for field_id in ("a", "b", "c", "d")]
        self.assertEqual(normalized, sorted(normalized))
        config = GraphConfiguration()
        radii = [target_radius(value, config) for value in normalized]
        self.assertEqual(radii, sorted(radii))
        self.assertGreater(radii[-1], radii[0])

    def test_dependency_strength_changes_weight_not_target_layer_difference(self) -> None:
        weak = dependency_constraint(DependencyEdge("a", "b", 0.2, PROVENANCE))
        strong = dependency_constraint(DependencyEdge("a", "b", 0.9, PROVENANCE))
        self.assertEqual(weak.target_difference, 1.0)
        self.assertEqual(strong.target_difference, 1.0)
        self.assertLess(weak.weight, strong.weight)

    def test_dependency_changes_depth_but_not_relatedness_pair_targets(self) -> None:
        relations = (Relatedness("a", "b", 0.75, PROVENANCE),)
        config = GraphConfiguration()
        pairs = build_layout_pairs(self.fields, relations, config)
        weak = compute_dependency_depth(
            self.fields,
            (
                DependencyEdge("a", "b", 0.2, PROVENANCE),
                DependencyEdge("b", "c", 0.9, PROVENANCE),
            ),
            0.15,
        )
        strong = compute_dependency_depth(
            self.fields,
            (
                DependencyEdge("a", "b", 0.9, PROVENANCE),
                DependencyEdge("b", "c", 0.9, PROVENANCE),
            ),
            0.15,
        )
        self.assertNotEqual(weak["a"].raw, strong["a"].raw)
        self.assertEqual(pairs, build_layout_pairs(self.fields, relations, config))
        self.assertNotIn("dependencies", inspect.signature(build_layout_pairs).parameters)

    def test_relatedness_changes_pair_targets_but_not_dependency_depth(self) -> None:
        config = GraphConfiguration()
        dependencies = (DependencyEdge("a", "b", 0.8, PROVENANCE),)
        depth = compute_dependency_depth(self.fields, dependencies, 0.15)
        low = build_layout_pairs(
            self.fields,
            (Relatedness("a", "b", 0.2, PROVENANCE),),
            config,
        )
        high = build_layout_pairs(
            self.fields,
            (Relatedness("a", "b", 0.8, PROVENANCE),),
            config,
        )
        low_pair = next(pair for pair in low if (pair.left, pair.right) == ("a", "b"))
        high_pair = next(pair for pair in high if (pair.left, pair.right) == ("a", "b"))
        self.assertGreater(low_pair.desired_distance, high_pair.desired_distance)
        self.assertLess(low_pair.weight, high_pair.weight)
        self.assertEqual(depth, compute_dependency_depth(self.fields, dependencies, 0.15))
        self.assertGreater(desired_distance(0.2, config), desired_distance(0.8, config))

    def test_connectivity_uses_symmetric_max_without_double_counting(self) -> None:
        dependencies = (
            DependencyEdge("a", "b", 0.8, PROVENANCE),
            DependencyEdge("b", "a", 0.4, PROVENANCE),
        )
        relations = (Relatedness("a", "b", 0.7, PROVENANCE),)
        pair_strength = compute_pair_connectivity(self.fields, dependencies, relations)
        self.assertEqual(pair_strength[("a", "b")], 0.8)
        metrics = compute_connectivity(self.fields, dependencies, relations)
        self.assertEqual(metrics["a"].raw, 0.8)
        self.assertEqual(metrics["b"].raw, 0.8)

    def test_connectivity_is_monotone_when_a_new_neighbor_is_added(self) -> None:
        first = compute_connectivity(
            self.fields,
            (),
            (Relatedness("a", "b", 0.5, PROVENANCE),),
        )
        second = compute_connectivity(
            self.fields,
            (),
            (
                Relatedness("a", "b", 0.5, PROVENANCE),
                Relatedness("a", "c", 0.4, PROVENANCE),
            ),
        )
        self.assertGreaterEqual(second["a"].raw, first["a"].raw)

    def test_hierarchy_changes_scope_and_regions_but_not_layout_or_connectivity(self) -> None:
        dependencies = (
            DependencyEdge("a", "b", 0.9, PROVENANCE),
            DependencyEdge("b", "c", 0.8, PROVENANCE),
        )
        relations = (
            Relatedness("a", "b", 0.7, PROVENANCE),
            Relatedness("b", "c", 0.8, PROVENANCE),
        )
        first = self._graph(
            hierarchy=(HierarchyEdge("a", "b", 1.0, PROVENANCE),),
            dependencies=dependencies,
            relatedness=relations,
        )
        second = self._graph(
            hierarchy=(
                HierarchyEdge("a", "b", 1.0, PROVENANCE),
                HierarchyEdge("a", "c", 1.0, PROVENANCE),
            ),
            dependencies=dependencies,
            relatedness=relations,
        )
        config = GraphConfiguration(seed=11, optimization_steps=100, density_grid_size=3)
        first_snapshot = build_graph(first, config)
        second_snapshot = build_graph(second, config)
        self.assertEqual(first_snapshot.coordinates, second_snapshot.coordinates)
        self.assertEqual(
            {field_id: node.connectivity for field_id, node in first_snapshot.nodes.items()},
            {field_id: node.connectivity for field_id, node in second_snapshot.nodes.items()},
        )
        self.assertNotEqual(first_snapshot.nodes["a"].scope, second_snapshot.nodes["a"].scope)
        self.assertNotEqual(first_snapshot.hierarchy_regions, second_snapshot.hierarchy_regions)
        self.assertNotIn("hierarchy", inspect.signature(optimize_layout).parameters)

    def test_fixed_seed_is_reproducible_and_coordinates_are_finite(self) -> None:
        graph = self._graph(
            dependencies=(
                DependencyEdge("a", "b", 0.9, PROVENANCE),
                DependencyEdge("b", "c", 0.8, PROVENANCE),
            ),
            relatedness=(
                Relatedness("a", "b", 0.7, PROVENANCE),
                Relatedness("b", "c", 0.8, PROVENANCE),
                Relatedness("c", "d", 0.5, PROVENANCE),
            ),
        )
        config = GraphConfiguration(seed=19, optimization_steps=180, density_grid_size=3)
        first = build_graph(graph, config)
        second = build_graph(graph, config)
        self.assertEqual(first.coordinates, second.coordinates)
        self.assertTrue(all(math.isfinite(value) for point in first.coordinates.values() for value in point))

    def test_display_metadata_does_not_affect_coordinates(self) -> None:
        dated_fields = tuple(
            ResearchField(field.id, field.name, field.description, str(1900 + index))
            for index, field in enumerate(self.fields)
        )
        localized_fields = tuple(
            ResearchField(field.id, field.name, field.description, None, f"领域 {index}")
            for index, field in enumerate(self.fields)
        )
        relations = (Relatedness("a", "b", 0.7, PROVENANCE),)
        config = GraphConfiguration(seed=31, optimization_steps=100, density_grid_size=3)
        undated = build_graph(self._graph(relatedness=relations), config)
        dated = build_graph(
            KnowledgeGraphInput(dated_fields, (), (), relations),
            config,
        )
        localized = build_graph(
            KnowledgeGraphInput(localized_fields, (), (), relations),
            config,
        )
        self.assertEqual(undated.coordinates, dated.coordinates)
        self.assertEqual(undated.coordinates, localized.coordinates)

    def test_diagnostic_viewer_uses_output_coordinates_and_connectivity_size(self) -> None:
        script = VIEWER_SCRIPT.read_text(encoding="utf-8")
        index = VIEWER_INDEX.read_text(encoding="utf-8")
        radius_function = script[script.index("function nodeRadius"):script.index("function nodeColor")]
        self.assertIn("connectivityNormalized", radius_function)
        self.assertNotIn("scopeNormalized", radius_function)
        self.assertIn("node.coordinate", script)
        self.assertIn("camera.distance - rotated.z", script)
        self.assertIn("camera.pitch + dy", script)
        self.assertIn('id="show-labels"', index)
        self.assertIn('id="use-chinese-names"', index)
        self.assertIn("function displayName", script)
        self.assertIn("node.nameZh", script)
        self.assertIn('id="auto-rotate"', index)
        hierarchy_source = (ROOT / "src/knowledge_galaxy/graph_engine/hierarchy.py").read_text(encoding="utf-8").lower()
        for visual_term in ("palette", "rgb", "hex", "material"):
            self.assertNotIn(visual_term, hierarchy_source)

    def test_end_to_end_data_and_direct_viewer(self) -> None:
        graph = load_knowledge_graph(FIELDS_PATH, RELATIONS_PATH)
        snapshot = build_graph(
            graph,
            GraphConfiguration(seed=7, optimization_steps=100, density_grid_size=3),
        )
        payload = snapshot_to_dict(snapshot)
        self.assertEqual(len(payload["nodes"]), 150)
        self.assertTrue(payload["H"])
        self.assertTrue(payload["D"])
        self.assertTrue(payload["R"])
        self.assertTrue(payload["layoutPairs"])
        self.assertTrue(payload["hierarchyRegions"]["regions"])
        self.assertTrue(payload["diagnostics"]["coordinateFinite"])
        for node in payload["nodes"]:
            self.assertIn("coordinate", node)
            self.assertIn("nameZh", node)
            self.assertIn("scopeRaw", node)
            self.assertIn("dependencyDepthRaw", node)
            self.assertIn("connectivityRaw", node)

        with tempfile.TemporaryDirectory() as directory:
            data_script = Path(directory) / "galaxy-data.js"
            write_diagnostic_data(data_script, payload)
            source = data_script.read_text(encoding="utf-8")
            encoded = source.removeprefix("window.KNOWLEDGE_GALAXY_SNAPSHOT = ").removesuffix(";\n")
            loaded = json.loads(encoded)
            html = VIEWER_INDEX.read_text(encoding="utf-8")
            self.assertEqual(loaded["nodes"][0]["coordinate"], payload["nodes"][0]["coordinate"])
            self.assertIn("Diagnostic Viewer", html)
            self.assertIn("galaxy-data.js", html)
            self.assertIn("app.js", html)

    def _graph(
        self,
        hierarchy: tuple[HierarchyEdge, ...] = (),
        dependencies: tuple[DependencyEdge, ...] = (),
        relatedness: tuple[Relatedness, ...] = (),
    ) -> KnowledgeGraphInput:
        return KnowledgeGraphInput(
            fields=self.fields,
            hierarchy=hierarchy,
            dependencies=dependencies,
            relatedness=relatedness,
        )


if __name__ == "__main__":
    unittest.main()
