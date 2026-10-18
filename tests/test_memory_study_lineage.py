"""Literal/development checks for the frozen L contract, never a winner ranking."""
from dataclasses import fields, replace
import math
import unittest
from unittest.mock import patch

from tools.memory_study.common import json_bytes
from tools.memory_study.lineage import (
    ArchiveReplay, AssessedQuery, Case, Event, IncrementalView, METHODS, Query,
    evaluate, load_cases, permute, run,
)


def observe(id="a", receipt=0, *, turn=1, value=True, key="open", **scope):
    return Event(id, "observe", receipt, event_turn=turn,
                 payload=(("key", key), ("value", value)), **scope)


def derive(id="c", receipt=1, proofs=(("a",),), **scope):
    return Event(id, "derive", receipt, payload=(("claim", id), ("proofs", proofs)), **scope)


class LineageTests(unittest.TestCase):
    def test_unsupported_fixture_version_is_rejected_without_fallback(self):
        with patch("tools.memory_study.lineage.Path.read_text",
                   return_value='{"protocol":"memory-study-v1","cases":[]}'):
            with self.assertRaisesRegex(ValueError, "unsupported"):
                load_cases()

    def test_literal_independent_expectations_and_primary_agreement(self):
        cases = load_cases()
        self.assertEqual(len(cases), 12)
        self.assertEqual(sum(len(c.assessments) for c in cases), 32)
        for case in cases:
            for passes in (1, 4, 16):
                with self.subTest(case=case.name, passes=passes):
                    replay, answers = evaluate(case, "archive_replay", passes)
                    view, cached = evaluate(case, "incremental_view", passes)
                    self.assertEqual(replay["mismatches"], 0)
                    self.assertEqual(view["mismatches"], 0)
                    self.assertEqual(answers, cached)
                    self.assertEqual(replay["queries"], len(case.assessments) * passes)

    def test_visible_objects_have_no_assessor_fields(self):
        forbidden = {"expected", "after", "rebuild", "assessor_worlds", "old_location_matches"}
        self.assertFalse(forbidden & {f.name for f in fields(Event)})
        self.assertFalse(forbidden & {f.name for f in fields(Query)})
        for case in load_cases():
            self.assertTrue(all(isinstance(a, AssessedQuery) for a in case.assessments))
            for event in case.events:
                self.assertFalse(forbidden & set(dict(event.payload)))

    def test_replay_identity_and_first_receipt(self):
        for cls in (ArchiveReplay, IncrementalView):
            method = cls()
            original = observe()
            method.ingest(original)
            method.ingest(replace(original, receipt_index=1))
            self.assertEqual(method.archive, [original])
            self.assertEqual(method.query(Query("archive_count")), 1)
            with self.assertRaisesRegex(ValueError, "semantic payload"):
                method.ingest(observe(receipt=2, value=False))

    def test_input_bounds_cycles_and_single_claim_creation(self):
        for cls in (ArchiveReplay, IncrementalView):
            with self.subTest(method=cls.__name__):
                method = cls()
                method.ingest(observe())
                method.ingest(replace(observe(), receipt_index=5))
                with self.assertRaisesRegex(ValueError, "receipt index"):
                    method.ingest(observe("b", 4))
                with self.assertRaisesRegex(ValueError, "Boolean"):
                    method.ingest(replace(observe("b", 6), payload=(("key", "x"), ("value", 1))))
                method.ingest(derive("c", 6))
                with self.assertRaisesRegex(ValueError, "new claim ID"):
                    method.ingest(Event("new", "derive", 7,
                                        payload=(("claim", "c"), ("proofs", (("a",),)))))
                with self.assertRaisesRegex(ValueError, "cyclic"):
                    method.ingest(derive("cycle", 7, (("cycle",),)))
                with self.assertRaisesRegex(ValueError, "four immutable premises"):
                    method.ingest(derive("large", 7, (("a",) * 5,)))
                sources = cls()
                for index in range(16):
                    sources.ingest(observe(str(index), index, key=str(index)))
                with self.assertRaisesRegex(ValueError, "source/claim budget"):
                    sources.ingest(observe("overflow", 16))
                archive = cls()
                for index in range(64):
                    archive.ingest(Event(str(index), "effect", index,
                                         payload=(("command", "x"), ("outcome", "unknown"))))
                with self.assertRaisesRegex(ValueError, "archive budget"):
                    archive.ingest(Event("overflow", "effect", 64,
                                         payload=(("command", "x"), ("outcome", "unknown"))))
                self.assertTrue(archive.query(Query("historical", id="0")))

    def test_frontier_future_unknown_conflict_dispute_no_fallback(self):
        for cls in (ArchiveReplay, IncrementalView):
            method = cls()
            method.ingest(observe(turn=3, value=False))
            method.ingest(observe("b", 1, turn=5))
            self.assertIs(method.query(Query("current_value", key="open", turn=4)), False)
            self.assertIs(method.query(Query("current_value", key="open", turn=5)), True)
            method.ingest(Event("x", "dispute_source", 2, payload=(("source", "b"),)))
            self.assertIsNone(method.query(Query("current_value", key="open")))
            self.assertFalse(method.query(Query("source_eligible", id="a")))
            method.ingest(observe("d", 3, turn=5, value=False))
            self.assertIsNone(method.query(Query("current_value", key="open")))
            method.ingest(observe("e", 4, turn=None))
            self.assertIsNone(method.query(Query("current_value", key="open", turn=2)))

    def test_alternate_and_nested_dependency_refresh(self):
        for cls in (ArchiveReplay, IncrementalView):
            method = cls()
            method.ingest(observe(key="a"))
            method.ingest(observe("b", 1, key="b"))
            method.ingest(derive("c", 2, (("a",), ("b",))))
            method.ingest(derive("d", 3, (("c",),)))
            self.assertTrue(method.query(Query("supported", id="d")))
            method.ingest(Event("x", "dispute_source", 4, payload=(("source", "a"),)))
            self.assertTrue(method.query(Query("supported", id="d")))
            method.ingest(Event("y", "dispute_source", 5, payload=(("source", "b"),)))
            self.assertFalse(method.query(Query("supported", id="d")))
            method.rebuild()
            self.assertFalse(method.query(Query("supported", id="d")))
            self.assertTrue(method.query(Query("historical", id="c")))

    def test_entity_scope_and_explicit_effect_status(self):
        for cls in (ArchiveReplay, IncrementalView):
            method = cls()
            method.ingest(observe(entity="other"))
            self.assertIsNone(method.query(Query("current_value", key="open")))
            self.assertFalse(method.query(Query("source_eligible", id="a")))
            self.assertTrue(method.query(Query("source_eligible", id="a", entity="other")))
            self.assertEqual(method.query(Query("effect", command="move")), "unknown")
            method.ingest(Event("e1", "effect", 1,
                                payload=(("command", "move"), ("outcome", "confirmed"))))
            self.assertEqual(method.query(Query("effect", command="move")), "confirmed")
            method.ingest(Event("e2", "effect", 2,
                                payload=(("command", "move"), ("outcome", "unknown"))))
            method.rebuild()
            self.assertEqual(method.query(Query("effect", command="move", turn=999)), "unknown")

    def test_permutation_rules_and_final_queries_only(self):
        for seed in (0, 1, 7):
            for literal in load_cases():
                variant = permute(literal, seed)
                self.assertEqual([e.event_id for e in literal.events if e.kind != "observe"],
                                 [e.event_id for e in variant.events if e.kind != "observe"])
                self.assertEqual([e.receipt_index for e in variant.events], list(range(len(variant.events))))
                self.assertTrue(all(a.after == len(variant.events) - 1 for a in variant.assessments))
                self.assertEqual([a.expected for a in variant.assessments],
                                 [a.expected for a in literal.assessments
                                  if a.after == len(literal.events) - 1])
                self.assertEqual(variant, permute(literal, seed))
                self.assertEqual(evaluate(variant, "archive_replay", 1)[0]["mismatches"], 0)
                self.assertEqual(evaluate(variant, "incremental_view", 1)[0]["mismatches"], 0)

    def test_negative_controls_are_observable(self):
        cases = {case.name: case for case in load_cases()}
        witnesses = {"no_deduplication": "duplicate", "no_valid_time": "changed_and_delayed",
                     "no_alternate_proofs": "alternate_proof", "no_scope": "session_alias",
                     "no_retirement_on_rebuild": "retirement_rebuild"}
        for ablation, name in witnesses.items():
            with self.subTest(ablation=ablation):
                metrics, _ = evaluate(cases[name], "diagnostic_" + ablation, 1)
                self.assertGreater(metrics["mismatches"], 0)
        self.assertGreater(evaluate(cases["retirement_rebuild"],
                                   "diagnostic_no_retirement_on_rebuild", 1)[0]["resurrection"], 0)

    def test_hand_counted_replay_work_and_storage(self):
        method = ArchiveReplay()
        event = observe()
        method.ingest(event)
        self.assertTrue(method.query(Query("source_eligible", id="a")))
        self.assertEqual(method.count["update_event_inspections"], 1)
        self.assertEqual(method.count["update_index_operations"], 2)
        self.assertEqual(method.count["query_archive_inspections"], 1)
        self.assertEqual(method.count["query_source_inspections"], 2)
        # Two replay index writes (source/property) and one answer lookup.
        self.assertEqual(method.count["query_index_operations"], 3)
        self.assertEqual(method.storage()["archive_bytes"], json_bytes([{
            "event_id": "a", "kind": "observe", "receipt_index": 0, "session": "s1",
            "frame": "f1", "entity": "door", "event_turn": 1,
            "payload": (("key", "open"), ("value", True))}]))

    def test_metadata_queries_use_existing_identity_state_and_effect_avoids_empty_cache(self):
        for cls in (ArchiveReplay, IncrementalView):
            method = cls()
            method.ingest(observe())
            self.assertEqual(method.query(Query("archive_count")), 1)
            self.assertTrue(method.query(Query("historical", id="a")))
            self.assertEqual(method.count["query_archive_inspections"], 0)
            self.assertEqual(method.count["query_index_operations"], 2)
        incremental = IncrementalView()
        self.assertEqual(incremental.query(Query("effect", command="move")), "unknown")
        self.assertEqual(incremental.caches, {})
        self.assertEqual(incremental.frontiers, {})
        self.assertEqual(incremental.count["query_index_operations"], 1)

    def test_reverse_edge_invalidation_and_rebuild_costs(self):
        method = IncrementalView()
        method.ingest(observe())
        method.ingest(derive())
        method.ingest(derive("d", 2, (("c",),)))
        self.assertTrue(method.query(Query("supported", id="d")))
        method.ingest(Event("x", "dispute_source", 3, payload=(("source", "a"),)))
        self.assertEqual(method.count["update_dependency_traversals"], 2)
        self.assertEqual(method.count["update_cache_invalidations"], 4)
        self.assertFalse(method.query(Query("supported", id="d")))
        method.rebuild()
        self.assertEqual(method.count["rebuild_event_inspections"], 4)
        self.assertEqual(method.count["rebuild_index_operations"], 7)
        self.assertFalse(method.query(Query("supported", id="d")))

    def test_row_contract_and_seed_aggregates(self):
        rows = run((0,))
        self.assertEqual(len(rows), 12 * 2 * 3 * len(METHODS) + 1)
        self.assertEqual(rows, run((0,)))
        for row in rows:
            self.assertEqual(set(row), {"suite", "seed", "condition", "method", "metrics"})
            self.assertEqual(row["suite"], "L")
            self.assertEqual(row["seed"], 0)
            self.assertTrue(all(isinstance(v, (int, float)) and math.isfinite(v)
                                for v in row["metrics"].values()))
            if row["method"] != "identification_control":
                m = row["metrics"]
                self.assertEqual(m["correct"] + m["mismatches"], m["queries"])
                self.assertLessEqual(m["archive_records"], 64)
        self.assertEqual(rows[-1]["metrics"]["unique_identity_available"], 0)


if __name__ == "__main__":
    unittest.main()
