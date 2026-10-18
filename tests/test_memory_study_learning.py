"""Prediction precedes feedback; probes and selected logs cannot invent knowledge."""
from dataclasses import asdict
import math
import unittest

from tools.memory_study.learning import Predictor, causal_control, frozen_probe, generate, run


class LearningStudyTests(unittest.TestCase):
    def test_beta_counts_scope_and_unseen_prediction(self):
        model = Predictor("scoped")
        original = model.state()
        self.assertEqual(model.predict("A", 0), (.5, 2))
        self.assertEqual(model.state(), original)
        model.update("A", 0, 1)
        self.assertAlmostEqual(model.predict("A", 0)[0], 2/3)
        self.assertEqual(model.predict("B", 0)[0], .5)
        self.assertEqual(model.predict("A", 1)[0], .5)
        pooled = Predictor("pooled")
        pooled.update("A", 0, 1)
        self.assertAlmostEqual(pooled.predict("B", 0)[0], 2/3)

    def test_window_forgets_only_its_own_context_action(self):
        model = Predictor("window8")
        for _ in range(8):
            model.update("A", 0, 1)
        model.update("B", 0, 0)
        self.assertEqual(model.predict("A", 0)[0], .9)
        model.update("A", 0, 0)
        self.assertEqual(model.predict("A", 0)[0], .8)
        self.assertEqual(len(model.windows[("A", 0)]), 8)
        self.assertEqual(len(model.windows[("B", 0)]), 1)

    def test_frozen_probe_does_not_update_and_hidden_domain_is_hidden(self):
        model = Predictor("scoped")
        model.update("A", 0, 1)
        before = model.state()
        frozen_probe(model, "drift")
        self.assertEqual(before, model.state())
        visible = generate(0, "hidden_domain")
        self.assertEqual({x.domain for x in visible}, {"unknown"})
        self.assertEqual(set(asdict(visible[0])), {"domain", "action", "outcome"})
        self.assertEqual(len(visible), 256)
        self.assertEqual(set(Predictor.predict.__annotations__) - {"return"}, {"domain", "action"})

    def test_causal_control_identifies_no_untried_value(self):
        result = causal_control()
        self.assertTrue(result["visible_logs_identical"])
        self.assertEqual(result["possible_policy_values"], [0, 1])
        self.assertEqual(result["identified_range"], [0, 1])

    def test_development_schema_conditions_and_reproduction(self):
        rows = run((0,))
        self.assertEqual(rows, run((0,)))
        self.assertEqual(len(rows), 144)
        self.assertEqual(len({(r["condition"], r["method"]) for r in rows}), 144)
        for row in rows:
            self.assertEqual(set(row), {"suite", "seed", "condition", "method", "metrics"})
            self.assertTrue(all(math.isfinite(x) for x in row["metrics"].values()))
            if "window_entries" in row["metrics"]:
                self.assertLessEqual(row["metrics"]["window_entries"], 128)
                self.assertLessEqual(row["metrics"]["observations_seen"], 256)


if __name__ == "__main__":
    unittest.main()
