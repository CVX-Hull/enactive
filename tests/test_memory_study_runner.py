"""Reporting contracts, independent seed units and immutable output boundaries."""
import copy
import gzip
import json
from pathlib import Path
import statistics
import tempfile
import unittest
from unittest.mock import patch

from tools.memory_study import run as r


def row(seed=0, method="dedup", value=.2):
    return {"suite": "E", "seed": seed, "condition": "literal", "method": method,
            "metrics": {"brier": value}}


class StudyRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Fresh checkouts have no ignored runtime directory. Tests create only
        # this project-owned parent before allocating their temporary reports.
        (r.ROOT / ".runtime").mkdir(exist_ok=True)

    def test_moments_use_seed_replicates_and_exact_cases_have_no_mc_interval(self):
        values = [1., 2., 4., 9.]
        moments = r.Moments()
        for value in values:
            moments.add(value)
        result = moments.report()
        self.assertEqual(result["n_seeds"], len(values))
        self.assertAlmostEqual(result["mean"], statistics.mean(values))
        self.assertAlmostEqual(result["mc_half_width"],
                               1.96 * statistics.stdev(values) / len(values)**.5)
        self.assertIsNone(moments.report(exact=True)["mc_half_width"])

    def test_rows_reject_duplicate_nonfinite_wrong_identity_and_boolean_metrics(self):
        r.validate_rows([row()], "E", 0)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            r.validate_rows([row(), row()], "E", 0)
        for bad in (float("nan"), float("inf"), True, "0.2"):
            item = row()
            item["metrics"]["brier"] = bad
            with self.assertRaises(ValueError):
                r.validate_rows([item], "E", 0)
        with self.assertRaises(ValueError):
            r.validate_rows([row(seed=1)], "E", 0)

    def test_paired_differences_are_within_same_seed_condition(self):
        original = [row(value=.1), row(method="naive", value=.4)]
        before = copy.deepcopy(original)
        paired = r.paired_rows(original, "E")
        self.assertEqual(original, before)
        self.assertEqual(paired[0]["method"], "naive-minus-dedup")
        self.assertAlmostEqual(paired[0]["metrics"]["brier"], .3)
        self.assertEqual(paired[0]["seed"], 0)
        with self.assertRaisesRegex(ValueError, "missing paired reference"):
            r.paired_rows([row(method="envelope")], "E")

    def test_final_dirty_source_is_rejected_before_creating_output(self):
        # The real final collection also exercises the clean-source guard; this
        # unit case isolates its rejection without committing a test repository.
        with patch.object(r.subprocess, "check_output", return_value=" M tools/memory_study/run.py\n"):
            with self.assertRaisesRegex(ValueError, "clean committed"):
                r.source_manifest("final")

    def test_report_root_is_local_and_existing_results_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as outside:
            with self.assertRaisesRegex(ValueError, "project-local"):
                r.execute("smoke", ("E",), Path(outside) / "report")
        with tempfile.TemporaryDirectory(dir=r.ROOT / ".runtime") as owned:
            with self.assertRaises(FileExistsError):
                r.execute("smoke", ("E",), Path(owned))

    def test_smoke_retains_raw_seed_rows_causal_control_and_reproducible_content(self):
        with tempfile.TemporaryDirectory(dir=r.ROOT / ".runtime") as owned:
            first = r.execute("smoke", ("E", "D"), Path(owned) / "first")
            second = r.execute("smoke", ("E", "D"), Path(owned) / "second")
            self.assertEqual(first["content_sha256"], second["content_sha256"])
            self.assertEqual(first["raw_sha256"], second["raw_sha256"])
            self.assertEqual(first["content"]["row_counts"], {"E": 162, "D": 144})
            self.assertEqual(first["content"]["causal_negative_control"]["identified_range"], [0, 1])
            self.assertIs(type(first["manifest"]["dirty"]), bool)
            with gzip.open(Path(owned) / "first/seed-aggregates.jsonl.gz", "rt") as source:
                rows = [json.loads(line) for line in source]
            self.assertEqual(len(rows), 306)
            self.assertEqual({x["seed"] for x in rows}, {0})

    def test_exact_matrix_and_runtime_laws_reject_renamed_missing_or_broken_outputs(self):
        from tools.memory_study.evidence import run as evidence_run
        good = evidence_run((0,))
        expected = r.expected_specs("E")
        r.validate_seed(good, "E", 0, expected)
        for corruption in ("rename", "metric", "law"):
            bad = copy.deepcopy(good)
            for item in bad:
                if item["method"] != "dedup":
                    continue
                if corruption == "rename":
                    item["method"] = "unregistered-replacement"
                elif corruption == "metric":
                    del item["metrics"]["brier"]
                else:
                    item["metrics"]["replay_forecast_change"] = .5
                    item["metrics"]["replay_decision_change"] = 1
            with self.subTest(corruption=corruption):
                with self.assertRaises(ValueError):
                    r.validate_seed(bad, "E", 0, expected)
                with tempfile.TemporaryDirectory(dir=r.ROOT / ".runtime") as owned:
                    target = Path(owned) / "failed"
                    with patch("tools.memory_study.evidence.run", return_value=bad):
                        with self.assertRaises(ValueError):
                            r.execute("smoke", ("E",), target)
                    self.assertTrue((target / "rejected-E-0.txt").is_file())
                    self.assertEqual(json.loads((target / "failure.json").read_text())["status"], "failed")
                    self.assertFalse((target / "report.json").exists())


if __name__ == "__main__":
    unittest.main()
