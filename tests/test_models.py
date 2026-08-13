from __future__ import annotations

import unittest

from knowledge_galaxy.evaluate import evaluate_anchors, largest_disagreements
from knowledge_galaxy.models import default_models, pair_scores_from_dense_embeddings, score


class ModelTests(unittest.TestCase):
    def test_local_models_produce_symmetric_bounded_scores(self) -> None:
        texts = {"z": "smooth manifold", "a": "smooth map", "m": "loop group"}
        for model in default_models():
            scores = model.fit_pair_scores(texts)
            self.assertEqual(len(scores), 3)
            self.assertEqual(score(scores, "z", "a"), score(scores, "a", "z"))
            self.assertTrue(all(0.0 <= value <= 1.0 for value in scores.values()))

    def test_dense_embeddings_do_not_depend_on_input_id_sort_order(self) -> None:
        scores = pair_scores_from_dense_embeddings(
            ["z", "a", "m"],
            [[1.0, 0.0], [0.8, 0.2], [0.0, 1.0]],
        )
        self.assertGreater(score(scores, "z", "a"), score(scores, "z", "m"))

    def test_anchor_evaluation_and_disagreement(self) -> None:
        anchors = [{"query": "a", "closer": "b", "farther": "c", "rationaleZh": "test"}]
        first = {("a", "b"): 0.9, ("a", "c"): 0.1, ("b", "c"): 0.2}
        second = {("a", "b"): 0.4, ("a", "c"): 0.3, ("b", "c"): 0.2}
        evaluation = evaluate_anchors(first, anchors)
        self.assertEqual(evaluation["passed"], 1)
        disagreements = largest_disagreements({"first": first, "second": second})
        self.assertEqual((disagreements[0]["left"], disagreements[0]["right"]), ("a", "b"))


if __name__ == "__main__":
    unittest.main()
