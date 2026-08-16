from __future__ import annotations

import inspect
import math
import tempfile
import unittest
from pathlib import Path

from knowledge_galaxy.spatial import (
    canonical_pair,
    compute_dependency_depth,
    compute_geometric_affinity,
    compute_hierarchy_regions,
    compute_scope,
    compute_transitive_membership,
    desired_distance,
    optimize_layout,
    relatedness_values,
    target_radius,
)
from knowledge_galaxy.spatial_schema import (
    DependencyEdge,
    HierarchyEdge,
    Relatedness,
    ResearchField,
    SpatialConfig,
    load_spatial_fixture,
)
from knowledge_galaxy.spatial_experiment import render_spatial_svg, run_spatial_experiment


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data/first_experiment/fixture.json"
PROVENANCE = "unit-test-assumption"


class SpatialModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fields = tuple(
            ResearchField(field_id, field_id.upper(), f"Description of {field_id}")
            for field_id in ("a", "b", "c", "d")
        )

    def test_fixture_loads_with_required_research_fields(self) -> None:
        fixture = load_spatial_fixture(FIXTURE)
        ids = {field.id for field in fixture.fields}
        self.assertGreaterEqual(len(ids), 15)
        self.assertTrue(
            {
                "mathematics",
                "linear-algebra",
                "probability-theory",
                "statistics",
                "optimization",
                "computer-science",
                "artificial-intelligence",
                "machine-learning",
                "deep-learning",
                "natural-language-processing",
                "computer-vision",
                "transformer-models",
                "large-language-models",
            }
            <= ids
        )

    def test_relatedness_is_symmetric_but_dependency_can_be_asymmetric(self) -> None:
        relations = (Relatedness("a", "b", 0.7, PROVENANCE),)
        values = relatedness_values(relations)
        self.assertEqual(
            values[canonical_pair("a", "b")],
            values[canonical_pair("b", "a")],
        )
        dependencies = (DependencyEdge("a", "b", 0.8, PROVENANCE),)
        affinity = compute_geometric_affinity(self.fields, dependencies, relations, 0.7)
        self.assertEqual(affinity[("a", "b")]["dependencyAffinity"], 0.4)
        directed = {(edge.foundation, edge.dependent): edge.value for edge in dependencies}
        self.assertEqual(directed[("a", "b")], 0.8)
        self.assertNotIn(("b", "a"), directed)

    def test_transitive_membership_uses_max_product_and_scope_is_derived(self) -> None:
        hierarchy = (
            HierarchyEdge("a", "b", 0.8, PROVENANCE),
            HierarchyEdge("b", "c", 0.5, PROVENANCE),
            HierarchyEdge("a", "c", 0.3, PROVENANCE),
        )
        membership = compute_transitive_membership(self.fields, hierarchy)
        self.assertAlmostEqual(membership[("a", "c")], 0.4)
        scope = compute_scope(self.fields, membership)
        self.assertAlmostEqual(scope["a"]["scope"], 1.2)
        self.assertGreater(scope["a"]["normalized"], scope["b"]["normalized"])

    def test_dependency_depth_and_target_radius_increase_along_chain(self) -> None:
        dependencies = (
            DependencyEdge("a", "b", 1.0, PROVENANCE),
            DependencyEdge("b", "c", 1.0, PROVENANCE),
            DependencyEdge("c", "d", 1.0, PROVENANCE),
        )
        depth = compute_dependency_depth(self.fields, dependencies, eta=0.1)
        normalized = [depth[field_id]["normalized"] for field_id in ("a", "b", "c", "d")]
        self.assertEqual(normalized, sorted(normalized))
        config = SpatialConfig()
        radii = [target_radius(value, config) for value in normalized]
        self.assertEqual(radii, sorted(radii))
        self.assertGreater(radii[-1], radii[0])

    def test_increasing_affinity_decreases_desired_distance(self) -> None:
        config = SpatialConfig()
        self.assertGreater(desired_distance(0.2, config), desired_distance(0.8, config))

    def test_geometric_overlap_does_not_create_hierarchy(self) -> None:
        fields = self.fields[:3]
        hierarchy = (HierarchyEdge("a", "b", 1.0, PROVENANCE),)
        membership = compute_transitive_membership(fields, hierarchy)
        positions = {"a": (3.0, 0.0, 0.0), "b": (0.0, 0.0, 0.0), "c": (0.0, 0.0, 0.0)}
        regions = compute_hierarchy_regions(
            fields,
            membership,
            positions,
            SpatialConfig(density_grid_size=3),
        )
        self.assertIn("c", regions["regions"]["a"]["insideNodeIds"])
        self.assertNotIn(("a", "c"), membership)

    def test_hierarchy_changes_scope_but_is_absent_from_coordinate_optimizer(self) -> None:
        self.assertNotIn("hierarchy", inspect.signature(optimize_layout).parameters)
        first_membership = compute_transitive_membership(
            self.fields,
            (HierarchyEdge("a", "b", 1.0, PROVENANCE),),
        )
        second_membership = compute_transitive_membership(
            self.fields,
            (HierarchyEdge("a", "b", 1.0, PROVENANCE), HierarchyEdge("a", "c", 1.0, PROVENANCE)),
        )
        self.assertNotEqual(
            compute_scope(self.fields, first_membership),
            compute_scope(self.fields, second_membership),
        )

    def test_fixed_seed_is_reproducible_and_coordinates_are_finite(self) -> None:
        dependencies = (
            DependencyEdge("a", "b", 0.9, PROVENANCE),
            DependencyEdge("b", "c", 0.8, PROVENANCE),
        )
        relations = (
            Relatedness("a", "b", 0.7, PROVENANCE),
            Relatedness("b", "c", 0.8, PROVENANCE),
            Relatedness("c", "d", 0.5, PROVENANCE),
        )
        config = SpatialConfig(seed=19, optimization_steps=350, density_grid_size=3)
        depth = compute_dependency_depth(self.fields, dependencies, config.dependency_regularization_eta)
        affinity = compute_geometric_affinity(
            self.fields,
            dependencies,
            relations,
            config.dependency_affinity_lambda,
        )
        first, _, _ = optimize_layout(self.fields, depth, affinity, config)
        second, _, _ = optimize_layout(self.fields, depth, affinity, config)
        self.assertEqual(first, second)
        self.assertTrue(all(math.isfinite(value) for point in first.values() for value in point))

    def test_emergence_time_does_not_affect_coordinates(self) -> None:
        dated = tuple(
            ResearchField(field.id, field.name, field.description, str(1900 + index))
            for index, field in enumerate(self.fields)
        )
        config = SpatialConfig(seed=31, optimization_steps=120, density_grid_size=3)
        depth = {field.id: {"raw": 0.0, "normalized": index / 3} for index, field in enumerate(self.fields)}
        affinity = compute_geometric_affinity(self.fields, (), (), config.dependency_affinity_lambda)
        undated_coordinates, _, _ = optimize_layout(self.fields, depth, affinity, config)
        dated_coordinates, _, _ = optimize_layout(dated, depth, affinity, config)
        self.assertEqual(undated_coordinates, dated_coordinates)

    def test_end_to_end_result_contains_required_outputs_and_svg(self) -> None:
        result = run_spatial_experiment(
            FIXTURE,
            SpatialConfig(seed=7, optimization_steps=120, density_grid_size=3),
        )
        self.assertEqual(len(result["nodes"]), 24)
        self.assertTrue(result["H"])
        self.assertTrue(result["D"])
        self.assertTrue(result["R"])
        self.assertTrue(result["G"])
        self.assertTrue(result["transitiveMembership"])
        self.assertTrue(result["hierarchyRegions"]["regions"])
        self.assertTrue(result["diagnostics"]["coordinateFinite"])
        for node in result["nodes"]:
            self.assertIn("coordinate", node)
            self.assertIn("scope", node)
            self.assertIn("dependencyDepth", node)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "spatial.svg"
            render_spatial_svg(result, output)
            text = output.read_text(encoding="utf-8")
            self.assertIn("<svg", text)
            self.assertIn("Large Language Models", text)


if __name__ == "__main__":
    unittest.main()
