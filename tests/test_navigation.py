"""Synthetic retained scenes exercise proposals; these are not native game evidence."""
from copy import deepcopy
from collections import Counter
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from harness.gameplay.contracts import ContractError, PrimitiveResult
from harness.gameplay.evidence import CapacityError, EvidenceError, EvidenceStore
from harness.gameplay.mission_contracts import VERSION, SourceBinding, SourceRevalidation
from harness.gameplay.navigation import NavigationIntent, NavigationOutcome, NavigationSkill, ObservedMap
from harness.movement import MovementBlocked, guard, visible_destination
from tests.test_gameplay_evidence import observation, png


class NavigationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="enactive-navigation-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bridge = self.root / "bridge"
        self.bridge.mkdir()
        self.store = EvidenceStore(self.bridge, self.root / "retained", max_frames=256)
        self.addCleanup(self.store.close)
        self.number = 0
        self.clocks = dict(now_monotonic=100.0, now_timestamp_ms=1_000_000)
        self.map = ObservedMap("mission", "world", 0)

    def frame(self, position=(0, 0, 0), *, cells=None, change=None, turn=10, session="world"):
        self.number += 1
        value = observation(self.number, session=session, timestamp_ms=self.clocks["now_timestamp_ms"])
        value["scene"].update(position=list(position), turn=turn)
        value["boundary"]["id"] = f"boundary-{self.number}"
        if cells is not None:
            for tile in value["scene"]["neighbors"]:
                point = (position[0] + tile["dx"], position[1] + tile["dy"], position[2])
                if point not in cells:
                    tile["terrain"] = "t_wall"
        if change:
            change(value)
        (self.bridge / value["frame"]).write_bytes(png())
        return self.store.ingest(value, received_monotonic=self.clocks["now_monotonic"], **self.clocks)

    def request(self, before, target=(1, 0, 0), **changes):
        value = dict(schema=VERSION, kind="skill", request_id="navigate", mission_id="mission", epoch=0,
                     skill_kind="navigate", work_id=None, phase_id=None, perception=None,
                     goal={"scope": {"mission_id": "mission", "session": "world",
                         "coordinate_epoch": 0}, "target": list(target)}, sources=[before.observation_id],
                     expected_session="world", expected_revision=before.revision,
                     expected_boundary_id=self.store.observation(before)["boundary"]["id"],
                     limits={"primitives": 32, "wall_seconds": 120, "game_seconds": 100})
        value.update(changes)
        return value

    def skill(self, before=None, target=(1, 0, 0), **changes):
        before = self.frame() if before is None else before
        self.map.add(before, self.store)
        return NavigationSkill(self.request(before, target, **changes), self.map)

    def propose(self, skill, **clocks):
        return skill.propose(self.store, **(self.clocks | clocks))

    def accept(self, skill, intent, after=None, disposition="returned", displacement=None, **clocks):
        if displacement is None and after is not None and after.session == intent.before.session:
            displacement = tuple(b - a for a, b in zip(self.store.position(intent.before),
                                                       self.store.position(after)))
        result = PrimitiveResult(intent.logical_id, intent.before, after, disposition, displacement,
                                 "Synthetic transport result")
        return skill.accept(result, self.store, **(self.clocks | clocks))

    def recapture(self, before, *, change=None, data=None, promote=True):
        value = self.store.observation(before)
        self.number += 1
        value.update(frame=f"frame-{value['session']}-{self.number}.png", id=f"refresh-{self.number}",
                     timestamp_ms=self.clocks["now_timestamp_ms"])
        if change:
            change(value)
        (self.bridge / value["frame"]).write_bytes(png() if data is None else data)
        method = self.store.ingest if promote else self.store.retain_equivalent
        extra = {} if promote else {"rule": "native_state"}
        return method(value, received_monotonic=self.clocks["now_monotonic"], **self.clocks, **extra)

    def refresh_relation(self, before, current, *, rule="native_state", generation=None):
        generation = self.store.authority_generation() if generation is None else generation
        original = SourceBinding(before.observation_id, "mission", 0, "actor", "boot", 0, 0, generation - 1)
        return SourceRevalidation(original, replace(original, source_id=current.observation_id,
                                                   store_generation=generation), rule)

    def test_deliberate_refresh_preserves_request_provenance_and_first_intent_relation(self):
        self.map.add(self.frame((1, 0, 0)), self.store)
        original = self.frame()
        request = self.request(original, (2, 0, 0))
        unchanged = deepcopy(request)
        self.map.add(original, self.store)
        skill = NavigationSkill(request, self.map)
        self.clocks = dict(now_monotonic=104.0, now_timestamp_ms=1_004_000)
        current = self.recapture(original)
        relation = self.refresh_relation(original, current)
        skill.revalidate(relation, self.store, **self.clocks)
        self.assertEqual(request, unchanged)
        self.assertEqual(skill._request, unchanged)
        intent = self.propose(skill)
        self.assertIsInstance(intent, NavigationIntent)
        self.assertEqual(intent.before, current)
        self.assertIs(intent.revalidation, relation)
        self.assertEqual(skill._start, original)
        preflight = self.recapture(current, promote=False)
        self.assertNotEqual(preflight, current)
        self.assertEqual(self.store.current(**self.clocks), current)
        self.assertIs(self.propose(skill), intent)
        self.assertIsNone(self.accept(skill, intent, self.frame((1, 0, 0), turn=11)))
        second = self.propose(skill)
        self.assertIsNone(second.revalidation)
        outcome = self.accept(skill, second, self.frame((2, 0, 0), turn=12))
        self.assertEqual((outcome.disposition, outcome.verified_steps), ("completed", 2))
        self.assertIs(outcome.revalidation, relation)
        self.assertTrue({original, current, second.before}.issubset(outcome.evidence))

    def test_refresh_does_not_renew_original_wall_limit(self):
        original = self.frame()
        skill = self.skill(original, limits={"primitives": 32, "wall_seconds": 4, "game_seconds": 100})
        self.clocks = dict(now_monotonic=104.5, now_timestamp_ms=1_004_500)
        current = self.recapture(original)
        relation = self.refresh_relation(original, current)
        skill.revalidate(relation, self.store, **self.clocks)
        outcome = self.propose(skill)
        self.assertEqual((outcome.disposition, outcome.proposed_count), ("blocked", 0))
        self.assertIn("Original navigation", outcome.reason)
        self.assertIs(outcome.revalidation, relation)

    def test_native_state_refresh_allows_changed_png_but_exact_png_rule_rejects_it(self):
        original = self.frame()
        skill = self.skill(original)
        current = self.recapture(original, data=png(b"changed"))
        with self.assertRaises(EvidenceError):
            skill.revalidate(self.refresh_relation(original, current, rule="exact_png_bytes"),
                             self.store, **self.clocks)
        skill.revalidate(self.refresh_relation(original, current), self.store, **self.clocks)
        self.assertIsInstance(self.propose(skill), NavigationIntent)

    def test_exact_png_refresh_with_equal_bytes_and_plain_navigation_have_explicit_relation(self):
        original = self.frame()
        plain = self.skill(original)
        self.assertIsNone(self.propose(plain).revalidation)
        skill = self.skill(original)
        current = self.recapture(original)
        relation = self.refresh_relation(original, current, rule="exact_png_bytes")
        skill.revalidate(relation, self.store, **self.clocks)
        self.assertIs(self.propose(skill).revalidation, relation)

    def test_refresh_rejects_actual_native_changes(self):
        changes = (
            lambda v: v["scene"].update(position=[1, 0, 0]),
            lambda v: v["scene"].update(turn=11),
            lambda v: v.update(revision=v["revision"] + 1),
            lambda v: v["boundary"].update(id="other-boundary"),
            lambda v: v["boundary"].update(control_generation=1),
            lambda v: v.update(takeover_generation=1),
            lambda v: v.update(paused=True, pause_origin="user"),
            lambda v: v.update(actions=["UP"]),
            lambda v: v.update(category="OTHER"),
            lambda v: v["scene"].update(visible_creatures=[{"name": "cat", "hostile": False}]),
            lambda v: v.update(scene=None, category="MENU", boundary=v["boundary"] | {"kind": "menu"}),
            lambda v: v.update(session="other", frame="frame-other-999.png"),
        )
        for change in changes:
            with self.subTest(change=change):
                self.map = ObservedMap("mission", "world", 0)
                original = self.frame()
                skill = self.skill(original)
                try:
                    current = self.recapture(original, change=change)
                except EvidenceError:
                    # Store contradictions already prevent a refresh from existing.
                    self.assertIsNone(skill._revalidation)
                    continue
                with self.assertRaises(EvidenceError):
                    skill.revalidate(self.refresh_relation(original, current), self.store, **self.clocks)
                self.assertIsNone(skill._revalidation)

    def test_refresh_requires_request_scope_and_exact_original_informing_source(self):
        original = self.frame()
        skill = self.skill(original)
        current = self.recapture(original)
        relation = self.refresh_relation(original, current)
        invalid = [None, relation.to_dict(),
                   replace(relation, original=replace(relation.original, source_id="missing")),
                   replace(relation, current=replace(relation.current, source_id="missing"))]
        for field, value in (("mission_id", "foreign"), ("epoch", 1)):
            invalid.append(SourceRevalidation(replace(relation.original, **{field: value}),
                                              replace(relation.current, **{field: value}), relation.rule))
        for candidate in invalid:
            with self.subTest(candidate=candidate), self.assertRaises((ContractError, EvidenceError)):
                skill.revalidate(candidate, self.store, **self.clocks)
        for changes in ({"expected_session": "other"}, {"expected_revision": 999},
                        {"expected_boundary_id": "other"}, {"sources": ["missing"]}):
            with self.subTest(changes=changes), self.assertRaises((ContractError, EvidenceError)):
                self.skill(original, **changes).revalidate(relation, self.store, **self.clocks)
        skill.revalidate(relation, self.store, **self.clocks)

    def test_refresh_rejects_false_native_takeover_binding_even_when_both_records_match(self):
        original = self.frame()
        skill = self.skill(original)
        current = self.recapture(original)
        relation = self.refresh_relation(original, current)
        false = SourceRevalidation(replace(relation.original, takeover_generation=1),
                                   replace(relation.current, takeover_generation=1), relation.rule)
        with self.assertRaises(EvidenceError):
            skill.revalidate(false, self.store, **self.clocks)

    def test_refresh_rejects_stale_current_foreign_store_and_generation_gap(self):
        original = self.frame()
        skill = self.skill(original)
        current = self.recapture(original)
        relation = self.refresh_relation(original, current)
        other = EvidenceStore(self.bridge, self.root / "other-refresh")
        self.addCleanup(other.close)
        with self.assertRaises(EvidenceError):
            skill.revalidate(relation, other, **self.clocks)
        with self.assertRaises(EvidenceError):
            skill.revalidate(self.refresh_relation(original, current, generation=relation.current.store_generation + 1),
                             self.store, **self.clocks)
        with self.assertRaises(ContractError):
            replace(relation, current=replace(relation.current, store_generation=relation.current.store_generation + 1))
        with self.assertRaises(EvidenceError):
            skill.revalidate(relation, self.store, now_monotonic=104.0, now_timestamp_ms=1_004_000)
        self.assertIsNone(skill._revalidation)

    def test_refresh_rejects_lost_corrupt_and_disputed_sources(self):
        for which in ("original", "current"):
            for damage in ("missing", "corrupt", "disputed"):
                with self.subTest(which=which, damage=damage):
                    self.map = ObservedMap("mission", "world", 0)
                    original = self.frame()
                    skill = self.skill(original)
                    current = self.recapture(original)
                    relation = self.refresh_relation(original, current)
                    source = original if which == "original" else current
                    if damage == "missing":
                        Path(source.frame_path).unlink()
                    elif damage == "corrupt":
                        Path(source.frame_path).chmod(0o600)
                        Path(source.frame_path).write_bytes(b"corrupt")
                    else:
                        contradiction = self.store.observation(source)
                        contradiction["actions"] = []
                        with self.assertRaises(EvidenceError):
                            self.store.ingest(contradiction, received_monotonic=100.0, **self.clocks)
                    with self.assertRaises(EvidenceError):
                        skill.revalidate(relation, self.store, **self.clocks)
                    self.assertIsNone(skill._revalidation)

    def test_refresh_once_before_any_proposal_or_terminal_and_no_second_current_adoption(self):
        original = self.frame()
        skill = self.skill(original)
        current = self.recapture(original)
        relation = self.refresh_relation(original, current)
        skill.revalidate(relation, self.store, **self.clocks)
        with self.assertRaises(ContractError):
            skill.revalidate(relation, self.store, **self.clocks)
        later = self.recapture(current)
        self.assertNotEqual(later, current)
        outcome = self.propose(skill)
        self.assertEqual(outcome.disposition, "blocked")
        self.assertIs(outcome.revalidation, relation)
        with self.assertRaises(ContractError):
            skill.revalidate(relation, self.store, **self.clocks)
        original = self.frame()
        proposed = self.skill(original)
        self.propose(proposed)
        current = self.recapture(original)
        with self.assertRaises(ContractError):
            proposed.revalidate(self.refresh_relation(original, current), self.store, **self.clocks)

    def test_refresh_intervening_invalidation_and_unknown_feedback_cannot_resume(self):
        original = self.frame()
        skill = self.skill(original)
        current = self.recapture(original)
        relation = self.refresh_relation(original, current)
        skill.revalidate(relation, self.store, **self.clocks)
        intent = self.propose(skill)
        outcome = self.accept(skill, intent, disposition="unknown")
        self.assertEqual(outcome.disposition, "unknown")
        self.assertIs(outcome.revalidation, relation)
        self.frame((1, 0, 0), turn=11)
        self.assertIs(self.propose(skill), outcome)
        original = self.frame()
        skill = self.skill(original)
        current = self.recapture(original)
        skill.revalidate(self.refresh_relation(original, current), self.store, **self.clocks)
        with self.assertRaises(EvidenceError):
            self.store.current(now_monotonic=104.0, now_timestamp_ms=1_004_000)
        # Returning to the same retained identity cannot erase the invalidation.
        with self.assertRaises(EvidenceError):
            self.store.ingest(self.store.observation(current), received_monotonic=100.0, **self.clocks)
        self.assertEqual(self.propose(skill).disposition, "blocked")

    def test_refresh_does_not_adopt_an_unattributed_capture_after_verified_progress(self):
        self.map.add(self.frame((1, 0, 0)), self.store)
        original = self.frame()
        skill = self.skill(original, (2, 0, 0))
        current = self.recapture(original)
        skill.revalidate(self.refresh_relation(original, current), self.store, **self.clocks)
        intent = self.propose(skill)
        after = self.frame((1, 0, 0), turn=11)
        self.assertIsNone(self.accept(skill, intent, after))
        self.recapture(after)
        outcome = self.propose(skill)
        self.assertEqual((outcome.disposition, outcome.verified_steps), ("partial", 1))

    def test_known_l_route_uses_one_frozen_proposal_and_actual_feedback_per_step(self):
        route = ((0, 0, 0), (1, 0, 0), (2, 0, 0), (2, 1, 0), (2, 2, 0))
        for position in route[1:]:
            self.map.add(self.frame(position, cells=route), self.store)
        start = self.frame(route[0], cells=route)
        skill = self.skill(start, route[-1])
        actions = []
        for index, position in enumerate(route[1:], 1):
            intent = self.propose(skill)
            self.assertIsInstance(intent, NavigationIntent)
            self.assertIs(self.propose(skill), intent)
            self.assertEqual(intent.target_next, position)
            self.assertEqual(intent.expected_boundary_id, self.store.observation(intent.before)["boundary"]["id"])
            with self.assertRaises(FrozenInstanceError):
                intent.action = "attack"
            actions.append(intent.action)
            after = self.frame(position, cells=route, turn=10 + index)
            outcome = self.accept(skill, intent, after)
            if index < 4:
                self.assertIsNone(outcome)
            else:
                self.assertEqual(outcome.disposition, "completed")
                self.assertEqual((outcome.verified_steps, outcome.proposed_count), (4, 4))
                self.assertIs(self.propose(skill), outcome)
        self.assertEqual(actions, ["RIGHT", "RIGHT", "DOWN", "DOWN"])

    def test_unknown_target_and_disconnected_known_cells_are_blocked(self):
        before = self.frame(cells={(1, 0, 0)})
        skill = self.skill(before, (4, 0, 0))
        self.assertEqual(self.propose(skill).disposition, "blocked")
        self.map.add(self.frame((4, 0, 0), cells={(4, 1, 0)}), self.store)
        self.assertEqual(self.map.shortest_path((0, 0, 0), (4, 1, 0), self.store).disposition, "blocked")

    def test_changed_obstacle_replaces_older_cell_and_delayed_add_cannot_restore_it(self):
        old = self.frame(cells={(1, 0, 0), (0, 1, 0)})
        self.map.add(old, self.store)
        new = self.frame(cells={(0, 1, 0)})
        self.map.add(new, self.store)
        self.map.add(old, self.store)
        path = self.map.shortest_path((0, 0, 0), (1, 0, 0), self.store)
        self.assertEqual(path.disposition, "blocked")
        self.assertIn(new, path.sources)

    def test_current_obstacle_after_a_step_produces_partial_without_replaying_route(self):
        self.map.add(self.frame((1, 0, 0)), self.store)
        skill = self.skill(self.frame(), (2, 0, 0))
        intent = self.propose(skill)
        after = self.frame((1, 0, 0), cells={(0, 0, 0)}, turn=11)
        self.assertIsNone(self.accept(skill, intent, after))
        outcome = self.propose(skill)
        self.assertEqual((outcome.disposition, outcome.verified_steps), ("partial", 1))

    def test_current_creatures_pause_missing_action_and_furniture_stop(self):
        mutations = (lambda v: v.update(paused=True),
                     lambda v: v["scene"].update(visible_creatures=[{"name": "zombie", "hostile": True}]),
                     lambda v: v.update(actions=[]),
                     lambda v: next(t for t in v["scene"]["neighbors"] if (t["dx"], t["dy"]) == (1, 0)).update(furniture="f_chair"))
        for change in mutations:
            with self.subTest(change=change):
                self.map = ObservedMap("mission", "world", 0)
                skill = self.skill(self.frame(change=change))
                self.assertEqual(self.propose(skill).disposition, "blocked")

    def test_nonhostile_npc_and_monster_allow_navigation_through_target(self):
        for name in ("Cornell", "cat"):
            with self.subTest(name=name):
                self.map = ObservedMap("mission", "world", 0)
                def change(v):
                    v["scene"]["visible_creatures"] = [{"name": name, "hostile": False}]
                skill = self.skill(self.frame(change=change))
                intent = self.propose(skill)
                self.assertIsInstance(intent, NavigationIntent)
                outcome = self.accept(skill, intent, self.frame((1, 0, 0), turn=11, change=change))
                self.assertEqual((outcome.disposition, outcome.verified_steps, outcome.proposed_count),
                                 ("completed", 1, 1))

    def test_malformed_creature_evidence_revokes_navigation_without_inventing_a_step(self):
        for pending in (False, True):
            for creatures in (None, [{"name": "cat"}], [{"name": "cat", "hostile": 0}]):
                with self.subTest(pending=pending, creatures=creatures):
                    self.map = ObservedMap("mission", "world", 0)
                    skill = self.skill(self.frame())
                    if pending:
                        self.assertIsInstance(self.propose(skill), NavigationIntent)
                    with self.assertRaises(EvidenceError):
                        self.frame((1, 0, 0) if pending else (0, 0, 0), turn=11,
                                   change=lambda v: v["scene"].update(visible_creatures=creatures))
                    outcome = self.propose(skill)
                    self.assertEqual((outcome.disposition, outcome.verified_steps, outcome.proposed_count),
                                     ("unknown" if pending else "blocked", 0, int(pending)))
                    self.assertIs(self.propose(skill), outcome)

    def test_new_hostile_after_returned_step_stops_including_at_target(self):
        for target in ((1, 0, 0), (2, 0, 0)):
            with self.subTest(target=target):
                self.map = ObservedMap("mission", "world", 0)
                self.map.add(self.frame((1, 0, 0)), self.store)
                skill = self.skill(self.frame(), target)
                intent = self.propose(skill)
                after = self.frame((1, 0, 0), turn=11, change=lambda v: v["scene"].update(
                    visible_creatures=[{"name": "Cornell", "hostile": False}, {"name": "zombie", "hostile": True}]))
                outcome = self.accept(skill, intent, after)
                self.assertEqual((outcome.disposition, outcome.verified_steps, outcome.proposed_count), ("partial", 1, 1))
                self.assertIn(after, outcome.evidence)
                self.assertIs(self.propose(skill), outcome)

    def test_stale_menu_and_session_changes_stop(self):
        skill = self.skill()
        self.assertEqual(self.propose(skill, now_monotonic=104.0, now_timestamp_ms=1_004_000).disposition, "blocked")
        before = self.frame()
        skill = self.skill(before)
        self.frame(change=lambda v: (v.update(scene=None, category="MENU"), v["boundary"].update(kind="menu")))
        self.assertEqual(self.propose(skill).disposition, "blocked")
        before = self.frame()
        skill = self.skill(before)
        self.frame(session="new-world")
        self.assertEqual(self.propose(skill).disposition, "blocked")

    def test_scope_and_initial_boundary_bindings_are_exact(self):
        before = self.frame()
        for field, value in (("mission_id", "other"), ("session", "other"), ("coordinate_epoch", 1)):
            request = self.request(before)
            request["goal"]["scope"][field] = value
            with self.subTest(field=field), self.assertRaises(ContractError):
                NavigationSkill(request, self.map)
        for changes in ({"expected_revision": 999}, {"expected_boundary_id": "different"}, {"sources": ["missing"]}):
            self.assertEqual(self.propose(self.skill(before, **changes)).disposition, "blocked")
        with self.assertRaises(EvidenceError):
            self.map.add(replace(before, session="new-world"), self.store)
        other = ObservedMap("mission", "world", 1)
        self.assertEqual(other.shortest_path((0, 0, 0), (1, 0, 0), self.store).disposition, "blocked")

    def test_zero_unexpected_and_unconfirmed_displacement_stop(self):
        for actual, disposition in (((0, 0, 0), "returned"), ((0, 1, 0), "returned"),
                                    ((1, 0, 0), "unknown"), ((1, 0, 0), "dispatched")):
            with self.subTest(actual=actual, disposition=disposition):
                skill = self.skill(self.frame())
                intent = self.propose(skill)
                outcome = self.accept(skill, intent, self.frame(actual, turn=11), disposition)
                self.assertEqual(outcome.disposition, "unknown" if disposition in ("unknown", "dispatched") else "blocked")
                self.assertEqual(outcome.verified_steps, 0)
                self.assertIs(self.propose(skill), outcome)

    def test_goal_verification_does_not_require_a_future_tile(self):
        skill = self.skill()
        intent = self.propose(skill)
        after = self.frame((1, 0, 0), cells=set(), turn=11)
        outcome = self.accept(skill, intent, after)
        self.assertEqual(outcome.disposition, "completed")
        self.assertEqual(outcome.position, (1, 0, 0))

    def test_goal_verification_does_not_require_map_expansion_capacity(self):
        self.map = ObservedMap("mission", "world", 0, max_nodes=5)
        skill = self.skill()
        intent = self.propose(skill)
        outcome = self.accept(skill, intent, self.frame((1, 0, 0), turn=11))
        self.assertEqual(outcome.disposition, "completed")
        self.assertEqual(self.map.node_count, 5)

    def test_already_at_goal_requires_fresh_safe_current_scene_but_no_next_tile(self):
        before = self.frame(cells=set())
        self.assertEqual(self.propose(self.skill(before, (0, 0, 0))).disposition, "completed")
        before = self.frame(cells=set(), change=lambda v: v.update(paused=True))
        self.assertEqual(self.propose(self.skill(before, (0, 0, 0))).disposition, "blocked")

    def test_accept_exact_pending_only_once_and_conflicting_feedback_never_releases_it(self):
        skill = self.skill()
        intent = self.propose(skill)
        after = self.frame((1, 0, 0), turn=11)
        result = PrimitiveResult(intent.logical_id, intent.before, after, "returned", (1, 0, 0), "synthetic")
        for bad in (replace(result, action_id="another"), replace(result, before=after),
                    replace(result, observed_displacement=(0, 0, 0))):
            with self.assertRaises(ContractError):
                skill.accept(bad, self.store, **self.clocks)
        outcome = skill.accept(result, self.store, **self.clocks)
        self.assertEqual(outcome.disposition, "completed")
        with self.assertRaises(ContractError):
            skill.accept(result, self.store, **self.clocks)

    def test_intervening_capture_prevents_attribution_and_unknown_never_becomes_completion(self):
        skill = self.skill()
        intent = self.propose(skill)
        after = self.frame((1, 0, 0), turn=11)
        self.frame((1, 0, 0), turn=11)
        self.assertEqual(self.accept(skill, intent, after).disposition, "unknown")
        skill = self.skill(self.frame())
        intent = self.propose(skill)
        outcome = self.accept(skill, intent, disposition="unknown")
        self.frame((1, 0, 0), turn=11)
        self.assertIs(self.propose(skill), outcome)
        self.assertEqual(outcome.disposition, "unknown")

    def test_original_request_limits_and_monotonic_clocks_do_not_reset(self):
        self.map.add(self.frame((1, 0, 0)), self.store)
        before = self.frame()
        skill = self.skill(before, (2, 0, 0), limits={"primitives": 1, "wall_seconds": 120, "game_seconds": 100})
        intent = self.propose(skill)
        outcome = self.accept(skill, intent, self.frame((1, 0, 0), turn=11))
        if outcome is None:
            outcome = self.propose(skill)
        self.assertEqual((outcome.disposition, outcome.proposed_count), ("partial", 1))
        for clocks in ({"now_monotonic": 221.0}, {"now_monotonic": float("nan")}, {"now_timestamp_ms": True}):
            skill = self.skill(self.frame())
            self.assertIsInstance(self.propose(skill), NavigationIntent)
            self.assertIsInstance(self.propose(skill, **clocks), NavigationOutcome)
        before = self.frame()
        skill = self.skill(before, limits={"primitives": 32, "wall_seconds": 120, "game_seconds": 1})
        intent = self.propose(skill)
        self.assertNotEqual(self.accept(skill, intent, self.frame((1, 0, 0), turn=12)).disposition, "completed")

    def test_node_cap_source_loss_dispute_and_retention_are_explicit(self):
        before = self.frame()
        small = ObservedMap("mission", "world", 0, max_nodes=4)
        with self.assertRaises(CapacityError):
            small.add(before, self.store)
        self.assertTrue(Path(before.frame_path).exists())
        self.assertEqual(small.node_count, 0)
        for cap in (0, 513, True):
            with self.assertRaises(ContractError): ObservedMap("mission", "world", 0, max_nodes=cap)
        self.map.add(before, self.store)
        Path(before.frame_path).unlink()
        self.assertEqual(self.map.shortest_path((0, 0, 0), (1, 0, 0), self.store).disposition, "unknown")
        before = self.frame()
        self.map = ObservedMap("mission", "world", 0)
        skill = self.skill(before)
        contradictory = self.store.observation(before)
        contradictory["scene"]["neighbors"][0]["terrain"] = "t_wall"
        with self.assertRaises(EvidenceError):
            self.store.ingest(contradictory, received_monotonic=100.0, **self.clocks)
        self.frame()
        self.assertEqual(self.propose(skill).disposition, "blocked")

    def test_full_32_proposal_limit_survives_feedback_and_replanning(self):
        for x in range(1, 34):
            self.map.add(self.frame((x, 0, 0)), self.store)
        skill = self.skill(self.frame(), (33, 0, 0), request_id="x" * 128)
        identities = set()
        for x in range(1, 33):
            intent = self.propose(skill)
            self.assertIsInstance(intent, NavigationIntent)
            self.assertLessEqual(len(intent.logical_id), 128)
            identities.add(intent.logical_id)
            outcome = self.accept(skill, intent, self.frame((x, 0, 0), turn=10 + x))
        self.assertEqual(len(identities), 32)
        self.assertEqual((outcome.disposition, outcome.proposed_count, outcome.verified_steps),
                         ("partial", 32, 32))
        self.assertIs(self.propose(skill), outcome)
        with self.assertRaises(ContractError):
            self.skill(self.frame(), limits={"primitives": 33, "wall_seconds": 120, "game_seconds": 100})

    def test_reload_new_store_and_session_cannot_reuse_observed_coordinates(self):
        before = self.frame()
        self.map.add(before, self.store)
        other = EvidenceStore(self.bridge, self.root / "other-retained")
        self.addCleanup(other.close)
        with self.assertRaises(EvidenceError): self.map.add(before, other)
        self.assertEqual(self.map.shortest_path((0, 0, 0), (1, 0, 0), other).disposition, "unknown")
        fresh = self.frame(session="reloaded-world")
        with self.assertRaises(EvidenceError): self.map.add(fresh, self.store)
        new_map = ObservedMap("mission", "reloaded-world", 1)
        self.assertEqual(new_map.shortest_path((0, 0, 0), (1, 0, 0), self.store).disposition, "blocked")

    def test_loss_of_candidate_source_invalidates_an_existing_pending_proposal(self):
        surveyed = self.frame((1, 0, 0))
        self.map.add(surveyed, self.store)
        skill = self.skill(self.frame(), (2, 0, 0))
        intent = self.propose(skill)
        Path(surveyed.frame_path).unlink()
        outcome = self.propose(skill)
        self.assertEqual(outcome.disposition, "unknown")
        self.assertEqual(outcome.pending_logical_id, intent.logical_id)

    def surveyed_route(self):
        route = ((0, 0, 0), (1, 0, 0), (2, 0, 0))
        unrelated = self.frame((100, 100, 0))
        self.map.add(unrelated, self.store)
        surveyed = self.frame((1, 0, 0), cells=route)
        self.map.add(surveyed, self.store)
        start = self.frame(cells=route)
        skill = self.skill(start, route[-1])
        return route, unrelated, surveyed, start, skill

    def measured_hashes(self, operation):
        with patch.object(self.store, "_verify_file", wraps=self.store._verify_file) as verify:
            result = operation()
        return result, Counter(call.args[0] for call in verify.call_args_list)

    def test_selected_route_provenance_survives_reprojection_and_completion(self):
        route, unrelated, surveyed, start, skill = self.surveyed_route()
        path = self.map.shortest_path(route[0], route[-1], self.store)
        self.assertEqual(set(path.sources), {start, surveyed})
        self.assertEqual(len(path.sources), 2)
        intent = self.propose(skill)
        self.assertIsNone(self.accept(skill, intent, self.frame(route[1], cells=route, turn=11)))
        intent = self.propose(skill)
        outcome = self.accept(skill, intent, self.frame(route[2], cells=route, turn=12))
        self.assertEqual(outcome.disposition, "completed")
        self.assertIn(surveyed, outcome.evidence)
        self.assertNotIn(unrelated, outcome.evidence)
        self.assertEqual(len(outcome.evidence), len(set(outcome.evidence)))

    def test_each_call_hashes_historical_route_sources_once_and_current_twice(self):
        route, unrelated, surveyed, start, skill = self.surveyed_route()
        expected = Counter({start: 2, surveyed: 1})
        intent, hashes = self.measured_hashes(lambda: self.propose(skill))
        self.assertEqual(hashes, expected)
        repeated, hashes = self.measured_hashes(lambda: self.propose(skill))
        self.assertIs(repeated, intent)
        self.assertEqual(hashes, expected)
        after = self.frame(route[1], cells=route, turn=11)
        result = PrimitiveResult(intent.logical_id, intent.before, after, "returned", (1, 0, 0), "synthetic")
        outcome, hashes = self.measured_hashes(lambda: skill.accept(result, self.store, **self.clocks))
        self.assertIsNone(outcome)
        self.assertEqual(hashes, Counter({after: 2, start: 1, surveyed: 1}))
        next_intent, hashes = self.measured_hashes(lambda: self.propose(skill))
        self.assertIsInstance(next_intent, NavigationIntent)
        self.assertEqual(hashes, Counter({after: 2, start: 1, surveyed: 1}))
        self.assertNotIn(unrelated, hashes)

    def test_disconnected_source_loss_does_not_invalidate_a_supported_route(self):
        route, unrelated, surveyed, start, skill = self.surveyed_route()
        Path(unrelated.frame_path).unlink()
        path, hashes = self.measured_hashes(lambda: self.map.shortest_path(route[0], route[-1], self.store))
        self.assertEqual(path.disposition, "candidate")
        self.assertEqual(hashes, Counter({start: 1, surveyed: 1}))
        intent, hashes = self.measured_hashes(lambda: self.propose(skill))
        self.assertIsInstance(intent, NavigationIntent)
        self.assertEqual(hashes, Counter({start: 2, surveyed: 1}))

    def test_blocked_path_verifies_only_explored_supports(self):
        unrelated = self.frame((100, 100, 0))
        self.map.add(unrelated, self.store)
        start = self.frame(cells=set())
        self.map.add(start, self.store)
        path, hashes = self.measured_hashes(lambda: self.map.shortest_path((0, 0, 0), (2, 0, 0), self.store))
        self.assertEqual(path.disposition, "blocked")
        self.assertEqual(path.sources, (start,))
        self.assertEqual(hashes, Counter({start: 1}))

    def test_node_cap_is_atomic_after_existing_projection_and_turn_regression_rejects(self):
        observed = ObservedMap("mission", "world", 0, max_nodes=5)
        before = self.frame()
        observed.add(before, self.store)
        self.assertEqual(observed.node_count, 5)
        later = self.frame((1, 0, 0), turn=11)
        with self.assertRaises(CapacityError): observed.add(later, self.store)
        self.assertEqual(observed.node_count, 5)
        self.assertEqual(observed.shortest_path((0, 0, 0), (1, 0, 0), self.store).disposition, "candidate")
        self.assertEqual(observed.shortest_path((0, 0, 0), (2, 0, 0), self.store).disposition, "blocked")
        regressed = self.frame(turn=9)
        with self.assertRaises(EvidenceError): observed.add(regressed, self.store)

    def test_shared_helper_has_no_current_authority_and_guard_retains_before_position(self):
        before = self.frame()
        state = self.store.observation(before)
        self.assertEqual(visible_destination(state["scene"], 1, 0), (1, 0, 0))
        self.assertEqual(guard(state, 1, 0, paused=False, frozen=False,
                               now_timestamp_ms=1_000_000), (0, 0, 0))
        state["paused"] = True
        self.assertEqual(visible_destination(state["scene"], 1, 0), (1, 0, 0))
        with self.assertRaises(MovementBlocked):
            guard(state, 1, 0, paused=False, frozen=False, now_timestamp_ms=1_000_000)
        for change in (lambda s: s.update(neighbors=[]),
                       lambda s: s["neighbors"].append(deepcopy(s["neighbors"][4])),
                       lambda s: next(t for t in s["neighbors"] if (t["dx"], t["dy"]) == (1, 0)).update(furniture="f_chair")):
            scene = deepcopy(state["scene"])
            change(scene)
            with self.assertRaises(MovementBlocked): visible_destination(scene, 1, 0)


if __name__ == "__main__":
    unittest.main()
