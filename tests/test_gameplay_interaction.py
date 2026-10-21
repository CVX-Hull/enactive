"""Synthetic native rows and retained PNGs; no native gameplay acceptance."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import tempfile
import unittest

from harness.gameplay.contracts import ContractError, PrimitiveResult
from harness.gameplay.evidence import EvidenceError, EvidenceStore
from harness.gameplay.interaction import MenuIntent, MenuOutcome, MenuSkill
from harness.gameplay.mission_contracts import VERSION, SourceBinding, SourceRevalidation
from tests.test_gameplay_evidence import observation, png


class MenuTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="enactive-menu-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bridge = self.root / "bridge"
        self.bridge.mkdir()
        self.store = EvidenceStore(self.bridge, self.root / "retained", max_frames=128)
        self.addCleanup(self.store.close)
        self.clocks = dict(now_monotonic=100.0, now_timestamp_ms=1_000_000)
        self.number = 0
        self.rows = [dict(id=f"row-{n}", text=text, enabled=True, hotkey=None)
                     for n, text in enumerate(("One", "Two", "Three", "Four"))]

    def frame(self, selected=0, *, change=None):
        self.number += 1
        value = observation(self.number, session="world", timestamp_ms=self.clocks["now_timestamp_ms"])
        value.update(category="UILIST", actions=["UILIST.UP", "UILIST.DOWN", "CONFIRM"], scene=None,
                     ui=dict(purpose="uilist", title="", rows=deepcopy(self.rows),
                             selected=None if selected is None else self.rows[selected]["id"],
                             filter=None, count=None, coverage="rendered_rows_only"))
        value["boundary"].update(kind="menu", id=f"boundary-{self.number}")
        if change:
            change(value)
        return self.publish(value)

    def publish(self, value):
        (self.bridge / value["frame"]).write_bytes(png())
        return self.store.ingest(value, received_monotonic=self.clocks["now_monotonic"], **self.clocks)

    def request(self, before, *, label="Four", outcome="activated", **changes):
        value = dict(schema=VERSION, kind="skill", request_id="menu", mission_id="mission", epoch=0,
                     skill_kind="menu", work_id=None, phase_id=None, perception=None, goal=dict(purpose="Choose a duration", label=label,
                                                  outcome=outcome),
                     sources=[before.observation_id], expected_session="world",
                     expected_revision=before.revision,
                     expected_boundary_id=self.store.observation(before)["boundary"]["id"],
                     limits=dict(primitives=32, wall_seconds=120, game_seconds=100))
        value.update(changes)
        return value

    def skill(self, before=None, **changes):
        return MenuSkill(self.request(self.frame() if before is None else before, **changes))

    def propose(self, skill, **clocks):
        return skill.propose(self.store, **(self.clocks | clocks))

    def accept(self, skill, intent, after=None, *, disposition="returned", **changes):
        result = PrimitiveResult(intent.logical_id, intent.before, after, disposition, None,
                                 "Synthetic transport receipt")
        return skill.accept(replace(result, **changes), self.store, **self.clocks)

    def refresh(self, before, *, change=None):
        value = self.store.observation(before)
        self.number += 1
        value.update(frame=f"frame-world-{self.number}.png", timestamp_ms=self.clocks["now_timestamp_ms"])
        if change:
            change(value)
        return self.publish(value)

    def relation(self, before, after):
        generation = self.store.authority_generation()
        original = SourceBinding(before.observation_id, "mission", 0, "actor", "boot", 0, 0, generation - 1)
        return SourceRevalidation(original, replace(original, source_id=after.observation_id,
                                                   store_generation=generation), "native_state")

    def test_multistep_exact_actions_and_confirm_are_one_immutable_proposal_at_a_time(self):
        skill = self.skill()
        previous = None
        for selected in (1, 2, 3):
            intent = self.propose(skill)
            self.assertIsInstance(intent, MenuIntent)
            self.assertEqual((intent.kind, intent.action), ("action", "UILIST.DOWN"))
            self.assertIs(self.propose(skill), intent)
            with self.assertRaises(FrozenInstanceError):
                intent.action = "CONFIRM"
            after = self.frame(selected)
            self.assertGreater(after.revision, intent.before.revision)
            self.assertNotEqual(self.store.observation(after)["boundary"]["id"], intent.expected_boundary_id)
            self.assertIsNone(self.accept(skill, intent, after))
            previous = after
        intent = self.propose(skill)
        self.assertEqual((intent.action, intent.before), ("CONFIRM", previous))
        after = self.frame(change=lambda v: v.update(category="POPUP_WAIT", ui=None))
        outcome = self.accept(skill, intent, after)
        self.assertIsInstance(outcome, MenuOutcome)
        self.assertEqual((outcome.disposition, outcome.proposed_count, outcome.verified_focus_steps),
                         ("partial", 4, 3))
        self.assertTrue(outcome.verification_required)
        self.assertIsNone(outcome.pending_logical_id)
        self.assertEqual(outcome.evidence[-1], after)
        self.assertIn("verification", outcome.reason.lower())
        self.assertIs(self.propose(skill), outcome)
        self.assertIs(self.accept(skill, intent, after), outcome)

    def test_disabled_rows_are_skipped_but_enabled_jumps_overshoot_and_reverse_stop(self):
        self.rows[1]["enabled"] = False
        skill = self.skill()
        intent = self.propose(skill)
        self.assertIsNone(self.accept(skill, intent, self.frame(2)))
        self.assertEqual(self.propose(skill).action, "UILIST.DOWN")
        for selected in (2, 3, 0):
            with self.subTest(selected=selected):
                self.rows[1]["enabled"] = True
                skill = self.skill(label="Three")
                intent = self.propose(skill)
                outcome = self.accept(skill, intent, self.frame(selected))
                self.assertEqual((outcome.disposition, outcome.verified_focus_steps), ("unknown", 0))
                self.assertEqual(outcome.pending_logical_id, intent.logical_id)
                self.assertIs(self.propose(skill), outcome)

    def test_upward_focus_uses_native_action_and_next_enabled_row(self):
        before = self.frame(3)
        skill = self.skill(before, label="One")
        intent = self.propose(skill)
        self.assertEqual(intent.action, "UILIST.UP")
        self.assertIsNone(self.accept(skill, intent, self.frame(2)))

    def test_inspection_is_read_only_and_current_target_only_confirms_once(self):
        skill = self.skill(outcome="inspected")
        outcome = self.propose(skill)
        self.assertEqual((outcome.disposition, outcome.proposed_count), ("completed", 0))
        self.assertFalse(outcome.verification_required)
        self.assertIs(self.propose(skill), outcome)
        skill = self.skill(label="One")
        intent = self.propose(skill)
        self.assertEqual(intent.action, "CONFIRM")
        outcome = self.accept(skill, intent, self.frame(0))
        self.assertEqual((outcome.disposition, outcome.verified_focus_steps), ("partial", 0))
        self.assertTrue(outcome.verification_required)

    def test_confirm_to_normal_play_retains_actual_scene_without_claiming_effect(self):
        skill = self.skill(label="One")
        intent = self.propose(skill)
        self.number += 1
        value = observation(self.number, session="world")
        value["boundary"]["id"] = "normal-return"
        after = self.publish(value)
        outcome = self.accept(skill, intent, after)
        self.assertEqual(outcome.disposition, "partial")
        self.assertTrue(outcome.verification_required)
        self.assertIsNotNone(after.turn)
        self.assertIsNone(intent.before.turn)
        self.assertEqual(outcome.evidence[-1], after)

    def test_confirm_rejects_native_failure_pause_takeover_and_unclassified_after(self):
        changes = {
            "rejected": lambda v: v.update(status="rejected"),
            "error": lambda v: v.update(error="Native capture diagnostic"),
            "host_pause": lambda v: v.update(paused=True, pause_origin="host"),
            "human_pause": lambda v: v.update(paused=True, pause_origin="human", takeover_generation=1),
            "takeover": lambda v: v.update(takeover_generation=1),
            "control_generation": lambda v: v["boundary"].update(control_generation=1),
            "unsupported": lambda v: (v.update(ui=None), v["boundary"].update(kind="unsupported")),
            "debug": lambda v: (v.update(ui=None), v["boundary"].update(kind="debug_prompt")),
        }
        for name, change in changes.items():
            with self.subTest(native_after=name):
                skill = self.skill(label="One")
                intent = self.propose(skill)
                after = self.frame(change=change)
                self.assertEqual(self.store.current_boundary(**self.clocks), after)
                outcome = self.accept(skill, intent, after)
                self.assertEqual((outcome.disposition, outcome.proposed_count), ("unknown", 1))
                self.assertEqual(outcome.pending_logical_id, intent.logical_id)
                self.assertEqual(outcome.evidence[-1], after)
                self.assertIs(self.propose(skill), outcome)
                self.assertIs(self.accept(skill, intent, after), outcome)

    def test_confirm_allows_classified_activity_and_changed_menu_with_same_control(self):
        for kind, category in (("activity_poll", "ACTIVITY"), ("menu", "POPUP_WAIT")):
            with self.subTest(boundary=kind):
                skill = self.skill(label="One")
                intent = self.propose(skill)
                after = self.frame(change=lambda v: (v.update(category=category, ui=None, actions=[]),
                                                     v["boundary"].update(kind=kind)))
                outcome = self.accept(skill, intent, after)
                self.assertEqual(outcome.disposition, "partial")
                self.assertTrue(outcome.verification_required)
                self.assertIsNone(outcome.pending_logical_id)
                self.assertEqual(outcome.evidence[-1], after)

    def test_missing_hidden_disabled_and_duplicate_enabled_targets_block(self):
        for mode in ("missing", "disabled", "duplicate", "hidden"):
            with self.subTest(mode=mode):
                self.rows = [dict(id=f"row-{n}", text=t, enabled=True, hotkey=None)
                             for n, t in enumerate(("One", "Two", "Three", "Four"))]
                if mode == "disabled": self.rows[3]["enabled"] = False
                if mode == "duplicate": self.rows[2]["text"] = "Four"
                if mode == "hidden": self.rows.pop()
                skill = self.skill(label="Absent" if mode == "missing" else "Four")
                outcome = self.propose(skill)
                self.assertEqual((outcome.disposition, outcome.proposed_count), ("blocked", 0))

    def test_only_exact_label_and_unique_enabled_target_match(self):
        self.rows[2].update(text="Four", enabled=False)
        self.assertIsInstance(self.propose(self.skill()), MenuIntent)
        self.assertEqual(self.propose(self.skill(label="four")).disposition, "blocked")

    def test_quantity_and_unsupported_ui_are_explicit_capability_stops(self):
        before = self.frame()
        request = self.request(before)
        request["goal"]["quantity"] = 2
        with self.assertRaises(ContractError):
            MenuSkill(request)
        changes = [lambda v: v.update(ui=None),
                   lambda v: v["ui"].update(purpose="inventory"),
                   lambda v: v.update(category="INVENTORY"),
                   lambda v: v["ui"].update(selected=None),
                   lambda v: v["ui"]["rows"][0].update(enabled=False)]
        for change in changes:
            with self.subTest(change=change):
                skill = self.skill(self.frame(change=change))
                self.assertEqual(self.propose(skill).disposition, "blocked")

    def test_missing_registered_action_never_uses_ordinary_direction_or_hotkey(self):
        for selected, label, removed in ((0, "Four", "UILIST.DOWN"), (3, "One", "UILIST.UP"),
                                          (0, "One", "CONFIRM")):
            before = self.frame(selected, change=lambda v: v["actions"].remove(removed))
            outcome = self.propose(self.skill(before, label=label))
            self.assertEqual(outcome.disposition, "blocked")
            self.assertIn("registered", outcome.reason)

    def test_focusing_preserves_native_shape_and_stops_on_popup_or_paused_capture(self):
        changes = [lambda v: v["ui"]["rows"].reverse(),
                   lambda v: v["ui"]["rows"][3].update(text="Changed"),
                   lambda v: v["ui"]["rows"][3].update(enabled=False),
                   lambda v: v["ui"].update(title="Changed"),
                   lambda v: v["ui"].update(filter="x"),
                   lambda v: v["actions"].append("OTHER"),
                   lambda v: v.update(category="POPUP_WAIT", ui=None),
                   lambda v: v["boundary"].update(control_generation=1),
                   lambda v: v.update(takeover_generation=1),
                   lambda v: v.update(paused=True, pause_origin="host")]
        for change in changes:
            with self.subTest(change=change):
                skill = self.skill()
                intent = self.propose(skill)
                after = self.frame(1, change=change)
                outcome = self.accept(skill, intent, after)
                self.assertEqual((outcome.disposition, outcome.verified_focus_steps), ("unknown", 0))
                self.assertEqual(outcome.pending_logical_id, intent.logical_id)
                self.assertIn(after, outcome.evidence)

    def test_focus_requires_advanced_boundary_id_and_revision(self):
        before = self.frame()
        skill = self.skill(before)
        intent = self.propose(skill)
        after = self.frame(1, change=lambda v: v["boundary"].update(id=intent.expected_boundary_id))
        outcome = self.accept(skill, intent, after)
        self.assertEqual(outcome.disposition, "unknown")
        self.assertEqual(outcome.pending_logical_id, intent.logical_id)
        # Same-revision changed native rows are already rejected by the real store.
        skill = self.skill()
        intent = self.propose(skill)
        with self.assertRaises(EvidenceError):
            self.frame(1, change=lambda v: v.update(revision=intent.before.revision))
        self.assertEqual(self.propose(skill).disposition, "unknown")

    def test_proposal_limit_preserves_verified_progress_and_all_sources(self):
        skill = self.skill(limits=dict(primitives=1, wall_seconds=120, game_seconds=100))
        intent = self.propose(skill)
        after = self.frame(1)
        outcome = self.accept(skill, intent, after)
        self.assertEqual((outcome.disposition, outcome.proposed_count, outcome.verified_focus_steps),
                         ("partial", 1, 1))
        self.assertEqual(outcome.evidence, (intent.before, after))
        self.assertIs(self.propose(skill), outcome)

    def test_native_focus_completes_without_confirmation_even_at_exact_input_limit(self):
        skill = self.skill(label="Two", outcome="focused", limits=dict(primitives=1, wall_seconds=120, game_seconds=100))
        intent = self.propose(skill)
        self.assertEqual(intent.action, "UILIST.DOWN")
        after = self.frame(1)
        self.assertIsNone(self.accept(skill, intent, after))
        outcome = self.propose(skill)
        self.assertEqual((outcome.disposition, outcome.proposed_count, outcome.verified_focus_steps), ("completed", 1, 1))
        self.assertFalse(outcome.verification_required)
        self.assertIsNone(outcome.pending_logical_id)
        self.assertIs(self.propose(skill), outcome)

    def test_unknown_dispatched_and_bad_correlation_are_terminal_and_never_replayed(self):
        for mode in ("unknown", "dispatched", "wrong_id", "wrong_before", "missing_after"):
            with self.subTest(mode=mode):
                earlier = self.frame()
                skill = self.skill()
                intent = self.propose(skill)
                if mode in ("unknown", "dispatched"):
                    outcome = self.accept(skill, intent, disposition=mode)
                elif mode == "wrong_id":
                    outcome = self.accept(skill, intent, self.frame(1), action_id="wrong")
                elif mode == "wrong_before":
                    outcome = self.accept(skill, intent, self.frame(1), before=earlier)
                else:
                    # Corrupted typed records are revalidated at this trust boundary.
                    result = PrimitiveResult(intent.logical_id, intent.before, None, "unknown", None, "Corrupted receipt")
                    object.__setattr__(result, "transport_disposition", "returned")
                    outcome = skill.accept(result, self.store, **self.clocks)
                self.assertEqual(outcome.disposition, "unknown")
                self.assertEqual(outcome.pending_logical_id, intent.logical_id)
                self.assertIs(self.propose(skill), outcome)

    def test_nondelivery_and_rejection_block_without_replay(self):
        for disposition in ("not_dispatched", "rejected"):
            skill = self.skill()
            intent = self.propose(skill)
            outcome = self.accept(skill, intent, disposition=disposition)
            self.assertEqual(outcome.disposition, "blocked")
            self.assertIsNone(outcome.pending_logical_id)
            self.assertIs(self.propose(skill), outcome)

    def test_unrelated_promotion_before_or_after_attributed_source_invalidates(self):
        for mode in ("before", "after", "pending", "between"):
            with self.subTest(mode=mode):
                skill = self.skill()
                intent = self.propose(skill)
                if mode == "before": self.frame(0)
                after = self.frame(1)
                if mode == "after": self.frame(1)
                if mode == "pending": outcome = self.propose(skill)
                else: outcome = self.accept(skill, intent, after)
                if mode == "between":
                    self.assertIsNone(outcome)
                    self.frame(1)
                    outcome = self.propose(skill)
                self.assertEqual(outcome.disposition, "unknown" if mode != "between" else "partial")

    def test_pause_stale_source_loss_and_original_binding_prevent_input(self):
        for mode in ("pause", "stale", "source_loss", "revision", "session", "boundary", "undeclared"):
            with self.subTest(mode=mode):
                earlier = self.frame()
                before = self.frame(change=(lambda v: v.update(paused=True, pause_origin="host"))
                                    if mode == "pause" else None)
                request = self.request(before)
                if mode == "revision": request["expected_revision"] += 1
                if mode == "session": request["expected_session"] = "other"
                if mode == "boundary": request["expected_boundary_id"] = "other"
                if mode == "undeclared": request["sources"] = [earlier.observation_id]
                if mode == "source_loss": Path(earlier.frame_path).unlink(); request["sources"].append(earlier.observation_id)
                skill = MenuSkill(request)
                outcome = self.propose(skill, **(dict(now_monotonic=104, now_timestamp_ms=1_004_000)
                                                if mode == "stale" else {}))
                self.assertEqual((outcome.disposition, outcome.proposed_count), ("blocked", 0))

    def test_pending_staleness_and_lost_historical_source_are_unknown(self):
        for mode in ("stale", "lost"):
            skill = self.skill()
            intent = self.propose(skill)
            if mode == "lost": Path(intent.before.frame_path).unlink()
            outcome = self.propose(skill, **(dict(now_monotonic=104, now_timestamp_ms=1_004_000)
                                            if mode == "stale" else {}))
            self.assertEqual((outcome.disposition, outcome.proposed_count), ("unknown", 1))

    def test_one_equivalent_refresh_preserves_original_budget_and_first_intent_relation(self):
        original = self.frame()
        request = self.request(original)
        unchanged = deepcopy(request)
        skill = MenuSkill(request)
        request["goal"]["label"] = "Changed externally"
        self.clocks = dict(now_monotonic=104, now_timestamp_ms=1_004_000)
        current = self.refresh(original)
        relation = self.relation(original, current)
        skill.revalidate(relation, self.store, **self.clocks)
        self.assertEqual(skill._request, unchanged)
        intent = self.propose(skill)
        self.assertEqual(intent.before, current)
        self.assertIs(intent.revalidation, relation)
        with self.assertRaises(ContractError): skill.revalidate(relation, self.store, **self.clocks)
        self.assertIsNone(self.accept(skill, intent, self.frame(1)))
        self.assertIsNone(self.propose(skill).revalidation)
        self.assertEqual(skill._start, original)

    def test_refresh_cannot_renew_expired_original_wall_budget(self):
        original = self.frame()
        skill = self.skill(original, limits=dict(primitives=32, wall_seconds=4, game_seconds=100))
        self.clocks = dict(now_monotonic=104.5, now_timestamp_ms=1_004_500)
        current = self.refresh(original)
        relation = self.relation(original, current)
        skill.revalidate(relation, self.store, **self.clocks)
        outcome = self.propose(skill)
        self.assertEqual((outcome.disposition, outcome.proposed_count), ("blocked", 0))
        self.assertIn("Original", outcome.reason)
        self.assertIs(outcome.revalidation, relation)
        self.assertEqual(outcome.evidence, (original, current))

    def test_refresh_requires_exact_current_generation_equivalence_and_original_source(self):
        for mode in ("generation", "changed", "intervening", "source"):
            with self.subTest(mode=mode):
                original = self.frame()
                skill = self.skill(original)
                current = self.refresh(original, change=(lambda v: v.update(paused=True, pause_origin="host"))
                                       if mode == "changed" else None)
                relation = self.relation(original, current)
                if mode == "generation":
                    relation = SourceRevalidation(replace(relation.original, store_generation=10_000),
                                                  replace(relation.current, store_generation=10_001), "native_state")
                if mode == "source":
                    relation = SourceRevalidation(replace(relation.original, source_id="unavailable"),
                                                  relation.current, "native_state")
                if mode == "intervening": self.frame()
                with self.assertRaises(EvidenceError): skill.revalidate(relation, self.store, **self.clocks)

    def test_no_implicit_refresh_and_intervening_promotion_after_refresh_block(self):
        for explicit in (False, True):
            original = self.frame()
            skill = self.skill(original)
            current = self.refresh(original)
            if explicit:
                skill.revalidate(self.relation(original, current), self.store, **self.clocks)
                self.refresh(current)
            self.assertEqual(self.propose(skill).disposition, "blocked")

    def test_closed_requests_reject_other_skills_and_generic_input_payloads(self):
        before = self.frame()
        request = self.request(before)
        for extra in ({"actions": ["CONFIRM"]}, {"script": "anything"}, {"key": "a"}):
            with self.assertRaises(ContractError): MenuSkill(request | extra)
        request["skill_kind"] = "item"
        with self.assertRaises(ContractError): MenuSkill(request)
        self.assertIsInstance(self.propose(self.skill()), MenuIntent)


if __name__ == "__main__":
    unittest.main()
