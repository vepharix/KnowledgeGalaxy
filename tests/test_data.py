from __future__ import annotations

import copy
import unittest
from pathlib import Path

from knowledge_galaxy.data import load_json, validate_anchors, validate_dataset, validate_files


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/sample/entities.json"
ANCHORS = ROOT / "data/sample/anchors.json"


class DataValidationTests(unittest.TestCase):
    def test_sample_files_are_valid_and_match_thin_slice_quota(self) -> None:
        dataset, anchors = validate_files(DATASET, ANCHORS)
        roles: dict[str, int] = {}
        for entity in dataset["entities"]:
            roles[entity["sampleRole"]] = roles.get(entity["sampleRole"], 0) + 1
        self.assertEqual(len(dataset["entities"]), 19)
        self.assertEqual(
            roles,
            {
                "math_concept": 13,
                "theorem_structure_method": 4,
                "theoretical_physics_boundary": 2,
            },
        )
        self.assertEqual(len(anchors["triplets"]), 8)

    def test_unknown_source_is_rejected(self) -> None:
        dataset = copy.deepcopy(load_json(DATASET))
        dataset["entities"][0]["sourceRefs"] = ["missing"]
        self.assertTrue(any("unknown source" in error for error in validate_dataset(dataset)))

    def test_unknown_anchor_entity_is_rejected(self) -> None:
        anchors = copy.deepcopy(load_json(ANCHORS))
        anchors["triplets"][0]["closer"] = "missing"
        ids = {item["id"] for item in load_json(DATASET)["entities"]}
        self.assertTrue(any("unknown entity" in error for error in validate_anchors(anchors, ids)))


if __name__ == "__main__":
    unittest.main()
