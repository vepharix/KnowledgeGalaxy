from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from knowledge_galaxy.alignment import load_math_dataset
from knowledge_galaxy.alignment.adapter import derived_candidates_to_graph_input
from knowledge_galaxy.alignment.derivation import (
    DEPENDENCY_SCHEMA,
    DependencyExtraction,
    DerivationConfiguration,
    FormalDependency,
    compare_with_curated_baseline,
    derive_relation_candidates,
    load_dependency_extraction,
    load_node_selection,
)
from knowledge_galaxy.cli import main


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/mathematics"


class RelationDerivationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = load_math_dataset(DATA)
        cls.revisions = tuple(sorted((source.id, source.revision) for source in cls.dataset.sources))
        cls.toolchain = cls.dataset.sources[0].toolchain

    def extraction(self, *edges: FormalDependency) -> DependencyExtraction:
        return DependencyExtraction(
            schema_version=DEPENDENCY_SCHEMA,
            extractor="test Lean.Environment traversal",
            toolchain=self.toolchain,
            source_revisions=self.revisions,
            extraction_scope="synthetic test fixture",
            dependencies=tuple(edges),
        )

    def test_formal_reference_direction_becomes_candidate_D(self):
        report = derive_relation_candidates(
            self.dataset,
            self.extraction(FormalDependency("Module", "LinearMap", "type_reference", 1)),
        )
        pairs = {(item["source"], item["target"]) for item in report["relations"]["D"]}
        self.assertIn(("module", "linear_map"), pairs)
        self.assertIn(("vector_space", "linear_map"), pairs)
        self.assertNotIn(("linear_map", "module"), pairs)
        self.assertEqual(report["relations"]["H"], [])
        self.assertTrue(all(item["status"] == "candidate" for item in report["relations"]["D"]))

    def test_R_is_symmetric_by_construction_and_kept_separate_from_D(self):
        report = derive_relation_candidates(
            self.dataset,
            self.extraction(FormalDependency("Module", "LinearMap", "type_reference", 1)),
        )
        related = report["relations"]["R"]
        pairs = [(item["source"], item["target"]) for item in related]
        self.assertTrue(all(left < right for left, right in pairs))
        self.assertEqual(len(pairs), len(set(pairs)))
        shared_anchor = next(item for item in related if (item["source"], item["target"]) == ("module", "vector_space"))
        self.assertGreater(shared_anchor["components"]["sharedAnchors"], 0)
        self.assertNotIn("dependencyExtent", shared_anchor)

    def test_type_reference_is_stronger_than_value_reference(self):
        config = DerivationConfiguration(dependency_min_score=0, relatedness_min_score=0)
        type_report = derive_relation_candidates(
            self.dataset,
            self.extraction(FormalDependency("Module", "LinearMap", "type_reference", 1)),
            config,
        )
        value_report = derive_relation_candidates(
            self.dataset,
            self.extraction(FormalDependency("Module", "LinearMap", "value_reference", 1)),
            config,
        )
        def score(report: dict) -> float:
            return next(item["score"] for item in report["relations"]["D"]
                        if item["source"] == "module" and item["target"] == "linear_map")
        self.assertGreater(score(type_report), score(value_report))

    def test_ubiquitous_formal_source_is_downweighted(self):
        config = DerivationConfiguration(dependency_min_score=0, relatedness_min_score=0)
        focused = self.extraction(FormalDependency("Ring", "Module", "type_reference", 1))
        hub = self.extraction(
            FormalDependency("Ring", "Module", "type_reference", 1),
            *(FormalDependency("Ring", f"Unmapped.Helper{index}", "type_reference", 1) for index in range(20)),
        )
        def score(extraction: DependencyExtraction) -> float:
            report = derive_relation_candidates(self.dataset, extraction, config)
            return next(item["score"] for item in report["relations"]["D"]
                        if item["source"] == "ring" and item["target"] == "module")
        self.assertGreater(score(focused), score(hub))

    def test_loader_rejects_unpinned_or_mismatched_extraction(self):
        payload = {
            "schema_version": DEPENDENCY_SCHEMA,
            "extractor": "test",
            "toolchain": self.toolchain,
            "source_revisions": dict(self.revisions),
            "extraction_scope": "test",
            "dependencies": [{
                "source": "Module", "target": "LinearMap",
                "reference_kind": "type_reference", "occurrences": 1,
            }],
        }
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "dependencies.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(len(load_dependency_extraction(path, self.dataset).dependencies), 1)
            payload["source_revisions"]["mathlib"] = "0" * 40
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "revisions do not match"):
                load_dependency_extraction(path, self.dataset)

    def test_cli_writes_review_report_without_changing_dataset(self):
        payload = {
            "schema_version": DEPENDENCY_SCHEMA,
            "extractor": "test",
            "toolchain": self.toolchain,
            "source_revisions": dict(self.revisions),
            "extraction_scope": "test",
            "dependencies": [{
                "source": "Module", "target": "LinearMap",
                "reference_kind": "type_reference", "occurrences": 1,
            }],
        }
        with tempfile.TemporaryDirectory() as temp:
            dependency_path = Path(temp) / "dependencies.json"
            output_path = Path(temp) / "derived.json"
            dependency_path.write_text(json.dumps(payload), encoding="utf-8")
            result = main([
                "derive-math-relations", "--dataset", str(DATA),
                "--formal-dependencies", str(dependency_path), "--output", str(output_path),
            ])
            self.assertEqual(result, 0)
            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(report["schemaVersion"], "knowledge-galaxy.math-relation-candidates.1")
            self.assertGreater(len(report["relations"]["D"]), 0)
            self.assertTrue(all(item["status"] == "candidate" for item in report["relations"]["D"]))

    def test_node_selection_limits_relations_and_compares_with_baseline(self):
        experiment, selected = load_node_selection(DATA / "phase1-nodes.json", self.dataset)
        self.assertEqual(experiment, "lean-linear-algebra-relations-v1")
        report = derive_relation_candidates(
            self.dataset,
            self.extraction(
                FormalDependency("Module", "LinearMap", "type_reference", 1),
                FormalDependency("LinearMap", "LinearMap.ker", "type_reference", 1),
            ),
            selected_node_ids=selected,
        )
        endpoints = {
            node_id
            for kind in ("D", "R")
            for relation in report["relations"][kind]
            for node_id in (relation["source"], relation["target"])
        }
        self.assertLessEqual(endpoints, selected)
        self.assertEqual(report["coverage"]["selectedNodes"], len(selected))
        comparison = compare_with_curated_baseline(self.dataset, report, selected)
        self.assertIn("D", comparison)
        self.assertIn("candidateOnly", comparison["D"])

    def test_derived_candidate_graph_is_explicitly_small_and_has_no_H(self):
        experiment, selected = load_node_selection(DATA / "phase1-nodes.json", self.dataset)
        report = derive_relation_candidates(
            self.dataset,
            self.extraction(
                FormalDependency("Module", "LinearMap", "type_reference", 1),
                FormalDependency("LinearMap", "LinearMap.ker", "type_reference", 1),
            ),
            selected_node_ids=selected,
        )
        report["experiment"] = experiment
        graph = derived_candidates_to_graph_input(self.dataset, report, selected)
        self.assertEqual({field.id for field in graph.fields}, selected)
        self.assertEqual(graph.hierarchy, ())
        self.assertGreater(len(graph.dependencies), 0)
        self.assertGreater(len(graph.relatedness), 0)
        self.assertIn("uncurated", graph.metadata["relationPolicy"])

        invalid = json.loads(json.dumps(report))
        invalid["relations"]["H"] = [{
            "kind": "H", "source": "module", "target": "linear_map",
            "score": 1.0, "status": "candidate",
        }]
        with self.assertRaisesRegex(ValueError, "must not generate hierarchy"):
            derived_candidates_to_graph_input(self.dataset, invalid, selected)


if __name__ == "__main__":
    unittest.main()
