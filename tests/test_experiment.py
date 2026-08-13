from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from knowledge_galaxy.experiment import run_experiment
from knowledge_galaxy.external import request_external_embeddings
from knowledge_galaxy.report import render_report


ROOT = Path(__file__).resolve().parents[1]


class ExperimentTests(unittest.TestCase):
    def test_end_to_end_local_run_and_report(self) -> None:
        result = run_experiment(
            ROOT / "data/sample/entities.json",
            ROOT / "data/sample/anchors.json",
        )
        self.assertEqual(set(result["modelRuns"]), {"word_tfidf", "char_tfidf"})
        self.assertEqual(result["entityCount"], 19)
        self.assertTrue(result["largestDisagreements"])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.html"
            render_report(result, output)
            text = output.read_text(encoding="utf-8")
            self.assertIn("<!doctype html>", text)
            self.assertIn("最大模型分歧", text)

    def test_external_embedding_file_may_cover_only_math_subset(self) -> None:
        payload = {
            "model": "fake",
            "providerVersion": "test",
            "entityIds": ["metric-space", "topological-space", "manifold"],
            "embeddings": [[1, 0], [0.8, 0.2], [0.7, 0.3]],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "embeddings.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = run_experiment(
                ROOT / "data/sample/entities.json",
                ROOT / "data/sample/anchors.json",
                path,
            )
        self.assertIn("external:fake", result["modelRuns"])
        self.assertEqual(result["modelRuns"]["external:fake"]["coveredEntityIds"], sorted(payload["entityIds"]))

    def test_external_call_requires_explicit_permission_before_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "explicit"):
                request_external_embeddings(
                    ROOT / "data/sample/entities.json",
                    Path(directory) / "out.json",
                    "https://example.invalid/v1/embeddings",
                    "fake",
                    "MISSING_TEST_KEY",
                    False,
                )


if __name__ == "__main__":
    unittest.main()
