from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from knowledge_galaxy.alignment import create_math_release, load_math_dataset, load_release_manifest
from knowledge_galaxy.cli import main


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/mathematics"
MANIFEST = DATA / "release-v0.1.json"


class MathematicsReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = load_math_dataset(DATA)
        cls.manifest = load_release_manifest(MANIFEST)

    def lightweight_manifest(self) -> dict:
        manifest = copy.deepcopy(self.manifest)
        manifest["layout"]["optimization_steps"] = 20
        manifest["assessment"] = {"seeds": [1, 2], "steps": 10}
        return manifest

    def test_release_is_reproducible_research_preview_with_explicit_gates(self):
        first, report = create_math_release(self.dataset, self.lightweight_manifest())
        second, _ = create_math_release(self.dataset, self.lightweight_manifest())
        self.assertEqual(first["nodes"], second["nodes"])
        self.assertEqual(len(first["nodes"]), 80)
        self.assertEqual((len(first["H"]), len(first["D"]), len(first["R"])), (84, 78, 209))
        self.assertEqual(first["release"]["status"], "research_preview")
        self.assertFalse(report["publicScientificClaimReady"])
        self.assertEqual(report["graphInputDigest"], first["release"]["graphInputDigest"])
        statuses = {item["name"]: item["status"] for item in report["gates"]}
        self.assertEqual(statuses["dataset_contract"], "pass")
        self.assertEqual(statuses["source_bytes_and_locators"], "pending")
        self.assertEqual(statuses["independent_mathematical_expert_review"], "pending")
        serialized = json.dumps(first)
        self.assertNotIn("geometricAffinity", serialized)
        self.assertNotIn('"G"', serialized)

    def test_release_refuses_manifest_count_drift(self):
        manifest = self.lightweight_manifest()
        manifest["expected_counts"]["nodes"] += 1
        with self.assertRaisesRegex(ValueError, "counts do not match"):
            create_math_release(self.dataset, manifest)

    def test_release_keeps_lean_candidates_partial_and_separate(self):
        candidates = {
            "schemaVersion": "knowledge-galaxy.math-relation-candidates.1",
            "experiment": "test-partial-lean-evidence",
            "input": {"formalDependencyCount": 3},
            "coverage": {"selectedNodes": 2, "mappedNodes": 2, "unmappedNodes": []},
            "relations": {
                "H": [],
                "D": [{"source": "group", "target": "subgroup"}],
                "R": [{"source": "group", "target": "subgroup"}],
            },
        }
        _, report = create_math_release(self.dataset, self.lightweight_manifest(), lean_candidates=candidates)
        scope = report["formalCandidateScope"]
        self.assertEqual(scope["mappedSelectedNodes"], 2)
        self.assertEqual((scope["candidateD"], scope["candidateR"]), (1, 1))
        self.assertIn("still use curated", scope["interpretation"])

    def test_release_cli_writes_snapshot_report_and_viewer_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = self.lightweight_manifest()
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            snapshot, report, viewer = root / "snapshot.json", root / "report.json", root / "galaxy-data.js"
            code = main([
                "release-math", "--dataset", str(DATA), "--manifest", str(manifest_path),
                "--snapshot", str(snapshot), "--report", str(report), "--viewer-data", str(viewer),
            ])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(snapshot.read_text(encoding="utf-8"))["release"]["id"], "mathematics-galaxy-v0.1")
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["releaseStatus"], "research_preview")
            self.assertIn("window.KNOWLEDGE_GALAXY_SNAPSHOT", viewer.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
