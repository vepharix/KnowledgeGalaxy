from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from knowledge_galaxy.alignment import load_math_dataset, to_graph_input
from knowledge_galaxy.alignment.adapter import alignment_report
from knowledge_galaxy.alignment.validation import validate_math_dataset, verify_source_files
from knowledge_galaxy.cli import main
from knowledge_galaxy.export import snapshot_to_dict
from knowledge_galaxy.graph_engine.build import build_graph
from knowledge_galaxy.graph_engine.models import GraphConfiguration


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/mathematics"


class AlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = load_math_dataset(DATA)

    def test_sample_covers_conditional_many_to_many_mapping(self):
        dataset = self.dataset
        self.assertEqual(len(dataset.nodes), 20)
        self.assertEqual(len(dataset.declarations), 21)
        self.assertEqual(len(dataset.mappings), 22)
        by_node = {node.id: [m for m in dataset.mappings if m.node_id == node.id] for node in dataset.nodes}
        module, vector = by_node["module"][0], by_node["vector_space"][0]
        self.assertEqual(module.declaration_id, vector.declaration_id)
        self.assertNotEqual(module.conditions, vector.conditions)
        self.assertEqual({m.role for m in by_node["derivative"]}, {"variant", "value_operator"})
        self.assertEqual(len(by_node["continuity"]), 3)
        self.assertEqual(by_node["algebra"], [])
        self.assertIn("RingHom.id K", " ".join(by_node["linear_map"][0].conditions))
        self.assertEqual({m.role for m in by_node["random_variable"]}, {"context", "defining_expression"})
        self.assertEqual(alignment_report(dataset)["formalVerification"], "not_run")

    def test_candidates_unknown_and_indirect_assertions_are_not_graph_edges(self):
        graph = to_graph_input(self.dataset)
        self.assertEqual((len(graph.hierarchy), len(graph.dependencies), len(graph.relatedness)), (17, 11, 38))
        pairs = {(d.foundation, d.dependent) for d in graph.dependencies}
        self.assertNotIn(("topological_space", "derivative"), pairs)
        self.assertNotIn(("topological_space", "metric_space"), pairs)
        self.assertNotIn(("measurable_space", "random_variable"), pairs)
        self.assertNotIn(("group", "random_variable"), {(r.left, r.right) for r in graph.relatedness})
        unknown = [a for a in self.dataset.assertions if a.value is None]
        self.assertEqual(len(unknown), 2)
        # No R is inferred just by adding a D, and no declaration count becomes a weight.
        subset = replace(self.dataset, assertions=tuple(a for a in self.dataset.assertions if a.kind == "D"))
        self.assertEqual(to_graph_input(subset).relatedness, ())

    def test_mapping_and_file_maintenance_do_not_change_layout_or_brightness(self):
        dataset = self.dataset
        extra = replace(dataset.mappings[0], id="extra-related-lemma", role="related_result")
        moved = replace(dataset.declarations[0], path="Mathlib/Algebra/Group/Renamed.lean")
        changed = replace(dataset, declarations=(moved, *dataset.declarations[1:]),
                          mappings=(*dataset.mappings, extra))
        original_graph = to_graph_input(dataset)
        new_graph = to_graph_input(changed)
        self.assertEqual(original_graph, new_graph)
        config = GraphConfiguration(optimization_steps=25, density_grid_size=3)
        original, modified = build_graph(original_graph, config), build_graph(new_graph, config)
        self.assertEqual(original.coordinates, modified.coordinates)
        self.assertEqual(original.nodes, modified.nodes)

    def test_adapter_preserves_semantic_kind_in_export_without_visual_rules(self):
        config = GraphConfiguration(optimization_steps=25, density_grid_size=3)
        payload = snapshot_to_dict(build_graph(to_graph_input(self.dataset), config))
        node = next(n for n in payload["nodes"] if n["id"] == "chain_rule")
        self.assertEqual(node["semanticKind"], "result")
        self.assertIn("concepts", payload["interpretationBoundary"]["entity"])
        self.assertTrue(payload["diagnostics"]["coordinateFinite"])
        self.assertFalse(any(key in node for key in ("color", "material", "radius", "brightness")))

    def test_cycles_are_reported_instead_of_silently_repaired(self):
        direct = next(a for a in self.dataset.assertions if a.kind == "D" and a.dependency_extent == "direct")
        reverse = replace(direct, id="cycle", source=direct.target, target=direct.source)
        with self.assertRaisesRegex(ValueError, "D contains cycle"):
            to_graph_input(replace(self.dataset, assertions=(*self.dataset.assertions, reverse)))
        h = next(a for a in self.dataset.assertions if a.kind == "H")
        with self.assertRaisesRegex(ValueError, "H contains cycle"):
            to_graph_input(replace(self.dataset, assertions=(*self.dataset.assertions, replace(h, id="h-cycle", source=h.target, target=h.source))))

    def test_duplicate_symmetric_R_is_rejected(self):
        r = next(a for a in self.dataset.assertions if a.kind == "R" and a.status == "curated")
        reverse = replace(r, id="duplicate-r", source=r.target, target=r.source)
        with self.assertRaisesRegex(ValueError, "duplicate curated relation"):
            validate_math_dataset(replace(self.dataset, assertions=(*self.dataset.assertions, reverse)))

    def test_unknown_values_cannot_be_curated_or_replaced_with_zero_implicitly(self):
        item = next(a for a in self.dataset.assertions if a.value is None)
        promoted = replace(item, status="curated")
        with self.assertRaisesRegex(ValueError, "cannot be unknown"):
            validate_math_dataset(replace(self.dataset, assertions=(*self.dataset.assertions, replace(promoted, id="promoted"))))

    def test_source_and_mapping_contract_rejects_invalid_inputs(self):
        dataset = self.dataset
        cases = [
            replace(dataset, sources=(replace(dataset.sources[0], revision="master"),)),
            replace(dataset, declarations=(replace(dataset.declarations[0], path="../secret.lean"), *dataset.declarations[1:])),
            replace(dataset, mappings=(replace(dataset.mappings[0], conditions=()), *dataset.mappings[1:])),
            replace(dataset, mappings=(replace(dataset.mappings[0], declaration_id="unknown"), *dataset.mappings[1:])),
            replace(dataset, mappings=(replace(dataset.mappings[0], review_status="lean_verified"), *dataset.mappings[1:])),
            replace(dataset, mappings=(replace(dataset.mappings[0], role="unconditional_equivalence"), *dataset.mappings[1:])),
            replace(dataset, assertions=(replace(dataset.assertions[0], value=float("nan")), *dataset.assertions[1:])),
            replace(dataset, assertions=(replace(dataset.assertions[0], value=True), *dataset.assertions[1:])),
            replace(dataset, assertions=(replace(dataset.assertions[0], evidence_kind="module_import"), *dataset.assertions[1:])),
        ]
        for case in cases:
            with self.subTest(case=case.schema_version), self.assertRaises(ValueError):
                validate_math_dataset(case)

    def test_offline_source_check_detects_content_and_locator_drift(self):
        raw = b"class Group (G : Type*) where\n  mul : G -> G -> G\n"
        sha = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        declaration = replace(self.dataset.declarations[0], blob_sha=sha, line_start=1, line_end=1,
                              signature_excerpt="class Group (G : Type*) where")
        dataset = replace(self.dataset, declarations=(declaration,))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / declaration.path
            target.parent.mkdir(parents=True)
            target.write_bytes(raw)
            self.assertEqual(verify_source_files(dataset, root), 1)
            with self.assertRaisesRegex(ValueError, "excerpt mismatch"):
                verify_source_files(replace(dataset, declarations=(replace(declaration, line_start=2, line_end=2),)), root)
            target.write_bytes(raw + b"-- changed\n")
            with self.assertRaisesRegex(ValueError, "blob mismatch"):
                verify_source_files(dataset, root)

    def test_json_loader_rejects_string_conditions_and_obsolete_fields(self):
        files = {p.name: json.loads(p.read_text()) for p in DATA.glob("*.json")}
        for mutation in ("conditions", "obsolete"):
            with tempfile.TemporaryDirectory() as temp:
                changed = copy.deepcopy(files)
                if mutation == "conditions":
                    changed["mappings.json"]["mappings"][0]["conditions"] = "Field K"
                else:
                    changed["manifest.json"]["geometricAffinity"] = 0.5
                for name, value in changed.items():
                    (Path(temp) / name).write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_math_dataset(Path(temp))

    def test_build_math_cli_exports_real_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            snapshot = Path(temp) / "galaxy.json"
            viewer_data = Path(temp) / "galaxy-data.js"
            self.assertEqual(main(["build-math", "--dataset", str(DATA), "--snapshot", str(snapshot), "--viewer-data", str(viewer_data)]), 0)
            payload = json.loads(snapshot.read_text())
            self.assertEqual(len(payload["nodes"]), 20)
            self.assertEqual(payload["metadata"]["dataset"], "mathematics")
            self.assertEqual(len(payload["formalAlignment"]["mappings"]), 22)
            self.assertIn(self.dataset.sources[0].revision, payload["formalAlignment"]["declarations"][0]["url"])
            self.assertIsNone(next(a["value"] for a in payload["formalAlignment"]["assertions"] if a["id"] == "R:group:random_variable:relation"))
            self.assertIn('window.KNOWLEDGE_GALAXY_SNAPSHOT = ', viewer_data.read_text())


if __name__ == "__main__":
    unittest.main()
