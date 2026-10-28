"""Shared clock arithmetic over projected data; no native or second-game claim."""
import unittest
from harness.gameplay.contracts import ContractError
from harness.gameplay.timeline import TimePoint, TimeContinuity, compose_timeline


class ObservedTimeTests(unittest.TestCase):
    def test_binding_projects_nonunit_ticks_and_counter_reset_without_gap_inference(self):
        # A binding supplies 6 seconds/tick. The shared reducer never sees ticks.
        first = TimePoint("a", "before", 1, 6 * 40)
        last = TimePoint("b", "before", 2, 6 * 43)
        reload = TimePoint("c", "after", 1, 0)
        end = TimePoint("d", "after", 3, 6 * 2)
        result = compose_timeline((first, last, reload, end), (TimeContinuity(last, reload),))
        self.assertEqual(result.elapsed_seconds, 30)
        self.assertEqual(result.segments, ((first, last), (reload, end)))

    def test_projected_counter_reset_cannot_supply_its_own_continuity(self):
        first, after = TimePoint("a", "one", 1, 900), TimePoint("b", "two", 1, 0)
        with self.assertRaises(ContractError):
            compose_timeline((first, after), ())

    def test_regressions_and_same_revision_contradictions_stay_fatal(self):
        first = TimePoint("a", "one", 2, 100)
        for last in (TimePoint("b", "one", 1, 101), TimePoint("b", "one", 3, 99), TimePoint("b", "one", 2, 101)):
            with self.subTest(last=last), self.assertRaises(ContractError):
                compose_timeline((first, last), ())
