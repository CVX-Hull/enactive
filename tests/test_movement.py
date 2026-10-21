"""Shared visible movement policy; fixtures are not native evidence."""
import copy
import unittest

from harness.movement import DIRECTIONS, MovementBlocked, current_guard, expected_position, guard, observed_step
from tests.test_controller import state


class MovementTests(unittest.TestCase):
    def check(self, value, dx=1, dy=0, **kwargs):
        return guard(value, dx, dy, paused=False, frozen=False,
                     now_timestamp_ms=value.get("timestamp_ms", 0), **kwargs)

    def test_each_cardinal_step_requires_exact_same_session_and_category(self):
        for direction, (dx, dy, _) in DIRECTIONS.items():
            with self.subTest(direction=direction):
                before = state()
                self.assertEqual(self.check(before, dx, dy), (0, 0, 0))
                after = copy.deepcopy(before)
                after["scene"]["position"] = list(expected_position((0, 0, 0), dx, dy))
                self.assertTrue(observed_step(before, after, dx, dy))
                for field, value in (("session", "other-world"), ("category", "YESNO")):
                    wrong = copy.deepcopy(after)
                    wrong[field] = value
                    self.assertFalse(observed_step(before, wrong, dx, dy))
                after["scene"]["position"][2] += 1
                self.assertFalse(observed_step(before, after, dx, dy))

    def test_current_guard_does_not_require_a_future_neighbor(self):
        for direction, (dx, dy, _) in DIRECTIONS.items():
            for obstacle in ("wall", "cupboard", "invisible"):
                with self.subTest(direction=direction, obstacle=obstacle):
                    value = state()
                    tile = next(t for t in value["scene"]["neighbors"]
                                if (t["dx"], t["dy"]) == (dx, dy))
                    if obstacle == "invisible":
                        tile.clear()
                        tile.update(dx=dx, dy=dy, visible=False)
                    else:
                        tile.update({"terrain": "t_wall"} if obstacle == "wall"
                                    else {"furniture": "f_cupboard"})
                    arguments = dict(paused=False, frozen=False,
                                     now_timestamp_ms=value["timestamp_ms"])
                    self.assertEqual(current_guard(value, dx, dy, **arguments), (0, 0, 0))
                    with self.assertRaises(MovementBlocked):
                        guard(value, dx, dy, **arguments)

    def test_current_guard_preserves_every_current_boundary_stop(self):
        changes = (lambda v: v.update(paused=True), lambda v: v.pop("boundary"),
                   lambda v: v.update(in_game=False), lambda v: v.update(frame_ok=False),
                   lambda v: v.update(timestamp_ms=True), lambda v: v.update(scene=None),
                   lambda v: v["scene"].update(visible_creatures=None),
                   lambda v: v["scene"].update(visible_creatures=[{"name": "cat"}]),
                   lambda v: v["scene"].update(position=[True, 0, 0]))
        for change in changes:
            value = state()
            timestamp = value["timestamp_ms"]
            change(value)
            with self.subTest(change=change), self.assertRaises(MovementBlocked):
                current_guard(value, 1, 0, paused=False, frozen=False,
                              now_timestamp_ms=timestamp)
        value = state()
        timestamp = value["timestamp_ms"]
        self.assertEqual(current_guard(value, 1, 0, paused=False, frozen=False,
                                       now_timestamp_ms=timestamp + 3000), (0, 0, 0))
        for changes in ({"paused": True}, {"frozen": True},
                        {"now_timestamp_ms": timestamp + 3001}):
            arguments = dict(paused=False, frozen=False, now_timestamp_ms=timestamp)
            with self.subTest(changes=changes), self.assertRaises(MovementBlocked):
                current_guard(value, 1, 0, **(arguments | changes))
        for dx, dy in ((0, 0), (1, 1), (True, 0)):
            with self.assertRaises(MovementBlocked):
                current_guard(state(), dx, dy, paused=False, frozen=False,
                              now_timestamp_ms=state()["timestamp_ms"])

    def test_unknown_or_ambiguous_requirements_fail_closed(self):
        changes = [lambda v: v.pop("paused"), lambda v: v.pop("boundary"),
                   lambda v: v.update(timestamp_ms=True), lambda v: v.update(frame_ok=False),
                   lambda v: v["scene"].update(visible_creatures=None),
                   lambda v: v["scene"].update(position=[True, 0, 0]),
                   lambda v: v["scene"].update(neighbors=None),
                   lambda v: v["scene"]["neighbors"].append(v["scene"]["neighbors"][-1].copy())]
        for change in changes:
            value = state()
            change(value)
            with self.subTest(change=change), self.assertRaises(MovementBlocked):
                self.check(value)

    def test_threat_visibility_furniture_and_terrain_are_independent_stops(self):
        for change in ({"visible": False}, {"furniture": "f_chair"}, {"terrain": "t_water_sh"}):
            value = state()
            value["scene"]["neighbors"][-1].update(change)
            with self.subTest(change=change), self.assertRaises(MovementBlocked):
                self.check(value)
        value = state()
        value["scene"]["visible_creatures"] = [{"name": "zombie", "hostile": True}]
        with self.assertRaises(MovementBlocked):
            self.check(value)

    def test_closed_nonhostile_creature_evidence_permits_bounded_movement(self):
        for creatures in ([], [{"name": "Cornell", "hostile": False}],
                          [{"name": "cat", "hostile": False}],
                          [{"name": "n" * 1024, "hostile": False}] * 512):
            with self.subTest(creatures=creatures[:1]):
                value = state()
                value["scene"]["visible_creatures"] = creatures
                original = copy.deepcopy(value)
                self.assertEqual(self.check(value), (0, 0, 0))
                self.assertEqual(value, original)

    def test_hostile_missing_and_malformed_creature_evidence_fail_closed(self):
        invalid = (None, {}, (), [None], ["cat"], [{"name": "cat"}],
                   [{"hostile": False}], [{"name": "", "hostile": False}],
                   [{"name": "n" * 1025, "hostile": False}],
                   [{"name": 1, "hostile": False}],
                   [{"name": "cat", "hostile": False, "friendly": True}],
                   [{"name": "cat", "hostile": False}] * 513,
                   [{"name": "zombie", "hostile": True}],
                   [{"name": "Cornell", "hostile": False}, {"name": "zombie", "hostile": True}],
                   *([{"name": "cat", "hostile": value}] for value in (0, 1, None, "false", [], {})))
        for creatures in invalid:
            with self.subTest(creatures=creatures):
                value = state()
                value["scene"]["visible_creatures"] = creatures
                with self.assertRaises(MovementBlocked):
                    self.check(value)
        value = state()
        del value["scene"]["visible_creatures"]
        with self.assertRaises(MovementBlocked):
            self.check(value)

    def test_age_and_transport_stop_without_mutating_state(self):
        value = state()
        original = copy.deepcopy(value)
        for kwargs in ({"paused": True}, {"frozen": True},
                       {"now_timestamp_ms": value["timestamp_ms"] + 3001}):
            arguments = dict(paused=False, frozen=False, now_timestamp_ms=value["timestamp_ms"])
            arguments.update(kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(MovementBlocked):
                guard(value, 1, 0, **arguments)
        self.assertEqual(value, original)

    def test_invalid_delta_and_boolean_displacement_never_count_as_movement(self):
        for delta in [(0, 0), (1, 1), (2, 0), (True, 0)]:
            with self.assertRaises(MovementBlocked):
                self.check(state(), *delta)
        before = state()
        after = copy.deepcopy(before)
        after["scene"]["position"] = [True, 0, 0]
        self.assertFalse(observed_step(before, after, 1, 0))
