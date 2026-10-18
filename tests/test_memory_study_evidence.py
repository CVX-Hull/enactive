"""Hand-calculable probability and visibility tests, never a preferred ranking."""
from dataclasses import asdict
import math
import random
import unittest

from tools.memory_study.evidence import (
    Observation, decision, envelope, expected_utility, forecast,
    generate, point_losses, posterior, run, unique_signs,
)


class EvidenceStudyTests(unittest.TestCase):
    def test_likelihood_enumeration_and_single_source(self):
        for rho in (0., .75, 1.):
            self.assertAlmostEqual(posterior((1,), .8, rho), .8)
        # All-positive signs: independent branch plus one shared correctness bit.
        positive = .25 * .8**4 + .75 * .8
        negative = .25 * .2**4 + .75 * .2
        self.assertAlmostEqual(posterior((1, 1, 1, 1), .8, .75),
                               positive / (positive + negative))
        self.assertEqual(posterior((1, 0), .8, .75), .5)
        with self.assertRaises(ValueError):
            posterior((1, 0), .8, 1.)

    def test_origin_identity_and_conflicting_replay(self):
        single = (Observation("a", 1),)
        copies = single * 4
        self.assertEqual(unique_signs(copies), (1,))
        self.assertEqual(forecast(copies, deduplicate=True), .8)
        self.assertAlmostEqual(forecast(copies, deduplicate=False), 256 / 257)
        self.assertEqual(envelope(copies), envelope(single))
        with self.assertRaisesRegex(ValueError, "conflicting"):
            unique_signs((Observation("a", 0), Observation("a", 1)))

    def test_threshold_ties_and_utility(self):
        for p in (.2, .8, .8+5e-13):
            self.assertIsNone(decision(p))
        self.assertEqual(decision(.81), 1)
        self.assertEqual(decision(.19), 0)
        self.assertIsNone(decision(.1, .9))
        self.assertEqual(expected_utility(1, .8), 0)
        self.assertEqual(expected_utility(0, .2), 0)
        self.assertEqual(expected_utility(None, .5), 0)

    def test_labels_and_parameters_are_separate_from_visible_records(self):
        visible, hidden = generate(random.Random(0), n=4, q=.8, rho=1.)
        self.assertIn(hidden, (0, 1))
        self.assertEqual(len({o.observed_bit for o in visible}), 1)
        self.assertEqual(set(asdict(visible[0])), {"origin_id", "observed_bit"})
        # Candidate signatures have no hidden target or true-model arguments.
        self.assertEqual(set(forecast.__annotations__) - {"return"},
                         {"observations", "deduplicate"})

    def test_proper_scores_and_declared_development_conditions(self):
        self.assertEqual(point_losses(.5, 1)["brier"], .25)
        self.assertAlmostEqual(point_losses(.5, 0)["log_loss"], math.log(2))
        self.assertTrue(math.isfinite(point_losses(1., 0)["log_loss"]))
        rows = run((0,))
        self.assertEqual(len(rows), 162)
        self.assertEqual(len({(x["seed"], x["condition"], x["method"]) for x in rows}), 162)
        self.assertEqual(rows, run((0,)))
        for row in rows:
            self.assertEqual(set(row), {"suite", "seed", "condition", "method", "metrics"})
            self.assertLessEqual(row["metrics"]["visible_copies"], 192)
            self.assertTrue(all(math.isfinite(x) for x in row["metrics"].values()))


if __name__ == "__main__":
    unittest.main()
