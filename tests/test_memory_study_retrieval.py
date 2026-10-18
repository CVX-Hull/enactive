"""Literal/development checks of frozen C semantics, never method rankings."""
import json
import math
import sqlite3
import unittest
from unittest.mock import Mock, patch

from tools.memory_study import retrieval as c
from tools.memory_study.common import json_bytes, rng


def record(index, *, operation="open", outcome="allow", **kwargs):
    return c.Record(f"r{index:02d}", index, kwargs.pop("session", "s1"),
                    kwargs.pop("context", "room0"), operation,
                    kwargs.pop("target", "door0"), outcome, **kwargs)


class GeneratorTests(unittest.TestCase):
    def test_generator_shape_pairing_availability_and_rendering(self):
        records, assessor = c.generate(3)
        paired, paired_assessor = c.generate(3, all_allow=True, rare_unavailable=True,
                                            distractor_sessions=True)
        self.assertEqual(assessor, paired_assessor)
        self.assertEqual(len(records), 64)
        self.assertEqual([r.id for r in records], [f"r{i:02d}" for i in range(64)])
        self.assertEqual([r.receipt_index for r in records], list(range(64)))
        self.assertEqual([r.key for r in records], [r.key for r in paired])
        self.assertEqual(records[0].key, assessor.rare_key)
        self.assertEqual(records[63].key, assessor.updated_key)
        self.assertNotIn(assessor.rare_key, [r.key for r in records[1:]])
        self.assertIn(assessor.updated_key, [r.key for r in records[1:63]])
        self.assertEqual([r.receipt_index for r in records if not r.available], [11, 22, 33, 44, 55])
        self.assertEqual({r.outcome for r in paired}, {"allow"})
        self.assertFalse(paired[0].available)
        self.assertEqual([r.receipt_index for r in paired if r.session == "s2"],
                         list(range(5, 64, 5)))
        self.assertEqual(records, c.generate(3)[0])
        self.assertEqual(record(0).body,
                         "session s1 context room0 operation open target door0 outcome allow")
        self.assertTrue(paired[5].body.startswith("session s2 "))

    def test_update_is_uniform_over_sorted_distinct_keys_not_record_multiplicity(self):
        choices = []

        def choose(sequence):
            choices.append(tuple(sequence))
            return sequence[(len(choices) - 1) % len(sequence)]

        random = Mock()
        random.choice.side_effect = choose
        with patch.object(c, "rng", return_value=random) as factory:
            records, _ = c.generate(1)
        factory.assert_called_once_with(1, "C")
        self.assertEqual(choices[0], tuple(sorted(c.KEYS)))
        self.assertEqual(choices[-1], tuple(sorted({r.key for r in records[1:63]})))
        self.assertEqual(len(choices), 64)
        self.assertLess(len(choices[-1]), 62)

    def test_visible_serialization_contains_no_assessor_or_hidden_query_identity(self):
        records, assessor = c.generate(0)
        self.assertEqual(set(c.payload(records[0])), {
            "id", "receipt_index", "session", "context", "operation", "target",
            "outcome", "available", "body"})
        self.assertEqual(set(assessor.__dict__), {"rare_key", "updated_key"})
        query = c.Query("room0", None, "door0")
        self.assertEqual(query.__dict__, {"context": "room0", "operation": None,
                                          "target": "door0", "session": "s1"})


class AnswerAndRetrievalTests(unittest.TestCase):
    def test_exact_scans_every_row_and_answerer_checks_scope_availability_and_time(self):
        records = (record(0), record(1, outcome="block"), record(2, available=False),
                   record(3, session="s2"), record(4, target="door1"))
        query = c.Query("room0", "open", "door0")
        result = c.exact(records, query)
        self.assertEqual(result.records, (records[1],))
        self.assertEqual(result.retrieval_records_scanned, 5)
        self.assertEqual(c.answer(records, query), "block")
        self.assertIsNone(c.answer(records[2:], query))
        self.assertIsNone(c.answer(records, c.Query("room1", "open", "door0")))

    def test_masked_requires_both_operations_and_consensus(self):
        query = c.Query("room0", None, "door0")
        opening = record(0)
        closing = record(1, operation="close")
        self.assertIsNone(c.answer((opening,), query))
        self.assertEqual(c.answer((opening, closing), query), "allow")
        self.assertIsNone(c.answer((opening, record(2, operation="close", outcome="block")), query))
        self.assertEqual(len(c.exact((opening, closing), query).records), 2)

    def test_recent_and_reservoir_filter_before_budget_and_are_reproducible(self):
        records = (record(0), record(1), record(2), record(3, available=False),
                   record(4, session="s2"))
        query = c.Query("room0", "open", "door0")
        self.assertEqual(c.recent(records, query, 2).records, (records[2], records[1]))
        sample = c.reservoir(records, query, 2, rng(2, "C-reservoir:literal"))
        self.assertEqual(sample, c.reservoir(records, query, 2, rng(2, "C-reservoir:literal")))
        self.assertEqual(len(sample.records), 2)
        self.assertTrue(all(r in records[:3] for r in sample.records))
        self.assertEqual(sample.retrieval_records_scanned, 5)


class FTS5Tests(unittest.TestCase):
    def test_canonical_schema_query_ties_hard_prefilter_and_whole_index(self):
        records = (record(0), record(1), record(2, available=False),
                   record(3, session="s2"), record(4, operation="close"))
        index = c.FTSArchive(records)
        self.addCleanup(index.close)
        query = c.Query("room0", "open", "door0")
        self.assertEqual(c.match_expression(query), '"room0" OR "open" OR "door0"')
        self.assertEqual(c.match_expression(c.Query("room0", None, "door0")),
                         '"room0" OR "door0"')
        self.assertEqual(index.connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='search'").fetchone()[0], c.FTS_SCHEMA)
        self.assertEqual(index.connection.execute("SELECT count(*) FROM search").fetchone()[0], 5)
        result = index.retrieve(query, 1)
        self.assertEqual(result.records, (records[1],))
        self.assertEqual(result.eligible_match_candidates_ranked, 3)
        masked = index.retrieve(c.Query("room0", None, "door0"), 8)
        self.assertEqual(masked.records, (records[4], records[1], records[0]))
        self.assertEqual(index.database_bytes, len(index.connection.serialize()))
        self.assertGreater(index.database_bytes, 0)

    def test_record_id_breaks_equal_receipt_rank_ties(self):
        first = record(0)
        second = c.Record("a", 0, "s1", "room0", "open", "door0", "allow")
        index = c.FTSArchive((first, second))
        self.addCleanup(index.close)
        self.assertEqual(index.retrieve(c.Query("room0", "open", "door0"), 2).records,
                         (second, first))

    def test_backend_failure_is_explicit_and_not_a_fallback(self):
        connection = Mock()
        connection.execute.side_effect = sqlite3.OperationalError("no such module: fts5")
        with patch.object(c.sqlite3, "connect", return_value=connection):
            with self.assertRaisesRegex(RuntimeError, "requires SQLite FTS5"):
                c.FTSArchive((record(0),))
        connection.close.assert_called_once()


class CompactionAndAccountingTests(unittest.TestCase):
    def test_majority_tie_latest_and_filtered_lineage_idempotence(self):
        records = (record(0), record(1), record(2, outcome="block"),
                   record(3, outcome="block", available=False), record(4, session="s2"))
        summary = c.majority(records)
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0].outcome, "allow")
        self.assertEqual(summary[0].source_ids, ("r00", "r01", "r02"))
        for depth in c.DEPTHS:
            result, work = c.compact(records, depth, "majority")
            self.assertEqual(result, summary)
            self.assertEqual(work, 5 + depth - 1)
        tie = c.majority((record(0), record(1, outcome="block")))
        self.assertEqual(tie[0].outcome, "block")
        self.assertEqual(c.majority(summary), summary)

    def test_progressive_truncation_starts_raw_and_removes_oldest_to_empty(self):
        records = tuple(record(i, available=i % 2 == 0) for i in range(8))
        self.assertEqual(c.compact(records, 1, "truncation"), (records[4:], 8))
        self.assertEqual(c.compact(records, 2, "truncation"), (records[6:], 12))
        self.assertEqual(c.compact(records, 4, "truncation"), ((), 15))
        self.assertEqual(c.compact(records, 8, "truncation"), ((), 15))
        with self.assertRaises(ValueError):
            c.compact(records, 1, "other")

    def test_storage_context_work_and_source_versus_semantic_recall(self):
        records = (record(0), record(1), record(2, outcome="block"))
        summary = c.majority(records)
        storage = c._storage(summary, archive=False, projection_work=3)
        self.assertEqual(storage["retained_records"], 1)
        self.assertEqual(storage["archive_records"], 0)
        self.assertEqual(storage["archive_record_bytes"], 0)
        self.assertEqual(storage["fts_document_rows_constructed"], 0)
        self.assertEqual(storage["metadata_rows_constructed"], 0)
        self.assertEqual(storage["retained_record_bytes"],
                         json_bytes([c.payload(summary[0], lineage=False)]))
        self.assertEqual(storage["lineage_entries"], 3)
        self.assertEqual(storage["lineage_bytes"], json_bytes({summary[0].id: ("r00", "r01", "r02")}))
        metrics = {}
        query = c.Query("room0", "open", "door0")
        c._score(metrics, c.exact(summary, query), query, "block", (records[-1],), "updated")
        self.assertEqual(metrics["latest_source_lineage_recalled"], 1)
        self.assertEqual(metrics["latest_records_recalled"], 0)
        self.assertEqual(metrics["required_latest_sources"], 1)
        self.assertEqual(metrics["wrong_answers"], 1)
        self.assertEqual(metrics["updated_wrong_answers"], 1)
        self.assertEqual(metrics["retrieval_records_scanned"], 1)
        self.assertEqual(metrics["context_record_bytes"], json_bytes([c.payload(summary[0])]))

    def test_same_bit_handles_distinct_label_names_without_label_state(self):
        for count in (2, 16, 256):
            labels = tuple(f"label{i}" for i in range(count))
            self.assertEqual(len(set(labels)), count)
            for bit in (0, 1):
                self.assertEqual([c.same_bit_answer(bit, label) for label in labels], [bit] * count)


class SuiteRowsTests(unittest.TestCase):
    def test_complete_development_factorial_schema_budgets_strata_and_exact_law(self):
        rows = c.run((0,))
        self.assertEqual(len(rows), 48 * 12 + 3)
        main = [row for row in rows if row["method"] != "same-bit"]
        self.assertEqual(len({row["condition"] for row in main}), 48)
        self.assertEqual(len({(r["condition"], r["method"]) for r in rows}), len(rows))
        for row in rows:
            self.assertEqual(set(row), {"suite", "seed", "condition", "method", "metrics"})
            self.assertEqual(row["suite"], "C")
            self.assertEqual(row["seed"], 0)
            self.assertTrue(all(isinstance(v, (int, float)) and math.isfinite(v)
                                for v in row["metrics"].values()))
        metric_names = set(main[0]["metrics"])
        for row in main:
            metrics = row["metrics"]
            self.assertEqual(set(metrics), metric_names)
            self.assertEqual(metrics["queries"], 32)
            self.assertEqual(sum(metrics[f"{s}_queries"] for s in c.STRATA), 32)
            self.assertEqual(metrics["rare_queries"], 1)
            self.assertEqual(metrics["updated_queries"], 1)
            self.assertEqual(sum(metrics[n] for n in ("answer_correct", "necessary_abstentions",
                                                     "avoidable_abstentions", "unsupported_answers",
                                                     "wrong_answers")), 32)
            k = int(row["condition"].split("k=")[-1])
            self.assertLessEqual(metrics["records_returned"], 32 * k)
            if row["method"] == "exact":
                self.assertEqual(metrics["decision_correct"], 32)
                self.assertEqual(metrics["retrieval_records_scanned"], 64 * 32)
            self.assertEqual(metrics["fts_document_rows_constructed"],
                             64 if row["method"] == "fts5" else 0)
            self.assertEqual(metrics["metadata_rows_constructed"],
                             64 if row["method"] == "fts5" else 0)
            if row["method"].startswith("majority"):
                self.assertLessEqual(metrics["retained_records"], 32)
                self.assertEqual(metrics["archive_records"], 0)
        self.assertEqual(json.loads(json.dumps(rows)), rows)
        self.assertEqual(c.run(()), [])


if __name__ == "__main__":
    unittest.main()
