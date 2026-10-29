from __future__ import annotations

import copy
import hashlib
import io
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from knowledge_galaxy.alignment import load_math_dataset, to_graph_input
from knowledge_galaxy.alignment.audit import audit_math_dataset
from knowledge_galaxy.alignment.assessment import assess_layout_stability, assess_radius_scale_tradeoffs
from knowledge_galaxy.alignment.models import Declaration, FormalSource, MathDataset, MathNode, RelationAssertion
from knowledge_galaxy.alignment.sources import prepare_source_files
from knowledge_galaxy.export import snapshot_to_dict
from knowledge_galaxy.graph_engine.build import build_graph
from knowledge_galaxy.graph_engine.models import GraphConfiguration


def toy_dataset():
    nodes = tuple(MathNode(n, n, n, "test node", "field", "test only") for n in "abc")
    def edge(kind, a, b, value):
        return RelationAssertion(kind+a+b, kind, a, b, value, "curated", "semantic_assessment", (),
                                 "test assumption", "test", "direct" if kind == "D" else None)
    assertions = (edge("D", "a", "b", .9), edge("D", "b", "c", .9), edge("D", "a", "c", .9), edge("R", "a", "b", .8))
    return MathDataset("knowledge-galaxy.math-alignment.1", (), (), nodes, (), assertions)


class MathAuditTests(unittest.TestCase):
    def test_audit_exposes_shortcuts_and_unassessed_pairs_without_mutation(self):
        dataset = toy_dataset()
        before = to_graph_input(dataset)
        report = audit_math_dataset(dataset)
        self.assertEqual(report["dependency"]["directEdgesWithAlternativePaths"],
                         [{"foundation": "a", "dependent": "c", "alternativePath": ["a", "b", "c"]}])
        self.assertGreater(report["dependency"]["weightedDepthResidualRMSE"], 0)
        self.assertEqual(report["evidence"]["pairsWithoutCuratedR"], 2)
        self.assertEqual(report["structure"]["nodesWithoutRelatedness"], ["c"])
        self.assertEqual(to_graph_input(dataset), before)

    def test_stale_layout_is_rejected_and_proximity_does_not_create_R(self):
        dataset = toy_dataset()
        snapshot = snapshot_to_dict(build_graph(to_graph_input(dataset), GraphConfiguration(optimization_steps=10, density_grid_size=3)))
        result = audit_math_dataset(dataset, snapshot)
        self.assertEqual(len(result["layout"]["closestPairsWithoutCuratedPositiveR"]), 2)
        self.assertEqual(len(snapshot["R"]), 1)
        conflict = result["layout"]["radialDistanceTargetConflicts"]
        self.assertEqual(conflict["count"], 1)
        self.assertGreater(conflict["largestGaps"][0]["incompatibilityGap"], 0)
        self.assertEqual(conflict["radiusScaleProbe"][-1]["incompatiblePositiveRPairs"], conflict["count"])
        stale = copy.deepcopy(snapshot)
        stale["D"][0]["value"] = .1
        with self.assertRaisesRegex(ValueError, "inputs differ"):
            audit_math_dataset(dataset, stale)
        broken = copy.deepcopy(snapshot)
        broken["nodes"][0]["coordinate"]["x"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite"):
            audit_math_dataset(dataset, broken)

    def test_multiseed_assessment_is_reproducible_and_keeps_semantics(self):
        dataset = toy_dataset()
        report = assess_layout_stability(dataset, (4, 5), steps=5)
        self.assertEqual(report, assess_layout_stability(dataset, (4, 5), steps=5))
        self.assertTrue(all(run["coordinateFinite"] for run in report["runs"]))
        for comparison in report["comparisons"]:
            self.assertTrue(0 <= comparison["meanNeighborJaccard"] <= 1)
        with self.assertRaisesRegex(ValueError, "distinct seeds"):
            assess_layout_stability(dataset, (4, 4))

    def test_full_catalog_has_connected_R_and_explicit_mapping_boundaries(self):
        dataset = load_math_dataset(Path(__file__).resolve().parents[1] / "data/mathematics")
        report = audit_math_dataset(dataset)
        self.assertEqual(report["counts"]["nodeKinds"], {"field": 9, "concept": 66, "result": 5})
        self.assertEqual(len(report["structure"]["relatednessComponents"]), 1)
        self.assertEqual(report["evidence"]["unmappedNonFields"], [])
        self.assertEqual(set(report["evidence"]["contextOnlyNodes"]), {"function", "binary_relation", "probability_space"})
        no_d = set(report["structure"]["nodesWithoutDependencyEvidence"])
        self.assertEqual(no_d, {n.id for n in dataset.nodes if n.kind == "field"})
        series = next(m for m in dataset.mappings if m.node_id == "series")
        summability = next(m for m in dataset.mappings if m.node_id == "summability")
        self.assertEqual(series.declaration_id, "Filter.Tendsto")
        self.assertEqual(summability.declaration_id, "Summable")
        declaration = next(d for d in dataset.declarations if d.id == "Summable")
        self.assertIn("to_additive", declaration.generated_from)
        self.assertEqual({s.id for s in dataset.sources}, {"mathlib", "lean-core"})

    def test_radius_trial_preserves_dataset_and_records_multiple_tradeoffs(self):
        dataset = toy_dataset()
        before = to_graph_input(dataset)
        report = assess_radius_scale_tradeoffs(dataset, (.25, 1.0), steps=5)
        self.assertEqual(to_graph_input(dataset), before)
        self.assertEqual(len(report["runs"]), 2)
        self.assertLessEqual(report["runs"][0]["incompatibleTargetPairs"], report["runs"][1]["incompatibleTargetPairs"])
        self.assertTrue(all("providedRNormalizedStress" in run and "targetRadiusMAEOverSpan" in run and "minimumPairDistance" in run for run in report["runs"]))
        with self.assertRaisesRegex(ValueError, "finite scales"):
            assess_radius_scale_tradeoffs(dataset, (float("nan"),))

    def test_source_preparation_pins_bytes_reuses_cache_and_rejects_bad_downloads(self):
        raw = b"def testAnchor := True\n"
        sha = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        source = FormalSource("mathlib", "https://github.com/leanprover-community/mathlib4", "1"*40, "test")
        declaration = Declaration("testAnchor", "mathlib", "testAnchor", "Mathlib/Test.lean", sha, 1, 1, "def testAnchor := True")
        dataset = replace(toy_dataset(), sources=(source,), declarations=(declaration,))
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp)
            with patch("knowledge_galaxy.alignment.sources.urlopen", return_value=io.BytesIO(raw)) as request:
                report = prepare_source_files(dataset, destination)
                self.assertEqual(report["downloadedFiles"], 1)
                self.assertIn("/" + "1"*40 + "/", request.call_args.args[0])
            with patch("knowledge_galaxy.alignment.sources.urlopen") as request:
                self.assertEqual(prepare_source_files(dataset, destination)["downloadedFiles"], 0)
                request.assert_not_called()
        with tempfile.TemporaryDirectory() as temp:
            with patch("knowledge_galaxy.alignment.sources.urlopen", return_value=io.BytesIO(b"wrong revision")):
                with self.assertRaisesRegex(ValueError, "blob mismatch"):
                    prepare_source_files(dataset, Path(temp))
                self.assertFalse((Path(temp) / "Mathlib/Test.lean").exists())


if __name__ == "__main__":
    unittest.main()
