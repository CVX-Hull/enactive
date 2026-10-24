"""Passive ordinary-loop tests with an independently shaped visible interface.

This fixture has no CDDA menu names, map/neighbors, item model, saves or game
clock. It tests the shared seam, not a real second game or learned gameplay.
"""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from harness.gameplay.contracts import ContractError, PrimitiveResult
from harness.gameplay.evidence import EvidenceError, EvidenceStore
from harness.gameplay.input_contracts import ControlIntent
from harness.gameplay.mission_contracts import InputObservation, SourceBinding, SourceRevalidation, VERSION
from harness.gameplay.ordinary_input import OrdinaryInputSkill
from harness.gameplay.semantic_controls import SemanticControlSkill
from tests.test_gameplay_evidence import png, observation


class OrdinaryInputTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.bridge = self.root / "bridge"
        self.bridge.mkdir()
        self.store = EvidenceStore(self.bridge, self.root / "retained", max_frames=256)
        self.addCleanup(self.store.close)
        self.clocks = dict(now_monotonic=100.0, now_timestamp_ms=1_000_000)
        self.counter = 0

    def frame(self, *, same=None, **changes):
        self.counter += 1
        geometry = dict(window_width=1, window_height=1, output_width=1, output_height=1, viewport=[0, 0, 1, 1])
        value = dict(protocol=6, id="", session="visible-interface", revision=self.counter,
            category="UNSEEN_RECEIVER", actions=[], status="ready", error="", paused=False,
            timestamp_ms=self.clocks["now_timestamp_ms"], frame_ok=True,
            frame=f"frame-visible-interface-{self.counter}.png", in_game=False,
            pause_origin="none", takeover_generation=0, scene=None, ui=None, frame_geometry=geometry,
            boundary=dict(kind="menu", id=f"receiver-{self.counter}", control_generation=0,
                          input_receiver=True, recovery_operations=[], interrupt_request_id=None))
        value.update(changes)
        (self.bridge / value["frame"]).write_bytes(Path(same.frame_path).read_bytes() if same else png(str(self.counter).encode()))
        return self.store.ingest(value, received_monotonic=self.clocks["now_monotonic"], **self.clocks)

    def request(self, original, event=None, **changes):
        return dict(schema=VERSION, kind="skill", request_id=f"request-{self.counter}", mission_id="mission", epoch=0,
            skill_kind="direct", work_id=None, phase_id=None, perception=None, procedure=None,
            goal=dict(input=event or dict(type="key", key="ESC", modifiers=[]),
                      intent="Try this physical event", expected="Observe the response", interrupt_allowed=False),
            sources=[original.observation_id], expected_session=original.session, expected_revision=original.revision,
            expected_boundary_id=self.store.observation(original)["boundary"]["id"],
            limits=dict(primitives=24, wall_seconds=120, game_seconds=100)) | changes

    def binding(self, source, generation):
        return SourceBinding(source.observation_id, "mission", 0, "player", "boot", 0, 0, generation)

    def entry(self, original=None, event=None, *, current_changes=None, **request_changes):
        original = original or self.frame()
        generation = self.store.authority_generation()
        request = self.request(original, event, **request_changes)
        current = self.frame(**(current_changes or {}))
        relation = InputObservation(self.binding(original, generation), self.binding(current, generation + 1))
        skill = OrdinaryInputSkill(request, deadline_monotonic=self.clocks["now_monotonic"] + 120)
        skill.observe(relation, self.store, **self.clocks)
        return skill, original, current, relation

    def propose(self, skill):
        return skill.propose(self.store, **self.clocks)

    def accept(self, skill, intent, after=None, disposition="returned", **changes):
        result = PrimitiveResult(intent.logical_id, intent.before, after, disposition, None, "actual delivery fact")
        return skill.accept(replace(result, **changes), self.store, **self.clocks)

    def test_entry_records_changed_evidence_without_equivalence_or_semantic_plan(self):
        skill, original, current, relation = self.entry(current_changes=dict(category="CHANGED_LABELS", actions=["unmapped"]))
        self.assertNotEqual(original.frame_sha256, current.frame_sha256)
        intent = self.propose(skill)
        self.assertIsInstance(intent, ControlIntent)
        self.assertEqual(intent.before, current)
        self.assertEqual(intent.input_observation, relation)
        self.assertIsNone(intent.revalidation)
        self.assertEqual(intent.action, dict(type="key", key="ESC", modifiers=[]))
        with self.assertRaises(ContractError):
            SemanticControlSkill(self.request(current), deadline_monotonic=220)

    def test_explicit_observation_required_and_equivalence_record_is_not_a_substitute(self):
        original = self.frame()
        request = self.request(original)
        skill = OrdinaryInputSkill(request, deadline_monotonic=220)
        with self.assertRaises(ContractError):
            self.propose(skill)
        generation = self.store.authority_generation()
        current = self.frame()
        revalidation = SourceRevalidation(self.binding(original, generation), self.binding(current, generation + 1), "exact_png_bytes")
        with self.assertRaises(ContractError):
            skill.observe(revalidation, self.store, **self.clocks)

    def test_stale_model_image_can_inform_a_fresh_entry_without_renewing_it(self):
        original = self.frame()
        self.clocks = dict(now_monotonic=110.0, now_timestamp_ms=1_010_000)
        skill, _, current, _ = self.entry(original)
        self.assertEqual(self.propose(skill).before, current)
        self.assertEqual(original.received_monotonic, 100.0)
        self.assertEqual(original.timestamp_ms, 1_000_000)

    def test_optional_observed_game_clock_keeps_original_informing_anchor(self):
        # Only this case supplies the CDDA integration's optional visible clock;
        # the independent interface fixture otherwise has no scene or turn.
        for elapsed in (10, 150):
            with self.subTest(elapsed=elapsed):
                native = observation()
                native["scene"]["turn"] = 100
                before = self.frame(category="DEFAULTMODE", in_game=True, scene=native["scene"],
                    boundary=native["boundary"])
                scene = deepcopy(native["scene"])
                scene["turn"] += elapsed
                skill, _, _, _ = self.entry(before, current_changes=dict(category="DEFAULTMODE", in_game=True,
                    scene=scene, boundary=native["boundary"]))
                proposal = self.propose(skill)
                self.assertEqual(isinstance(proposal, ControlIntent), elapsed < 100)
                if elapsed >= 100:
                    self.assertEqual((proposal.disposition, proposal.proposed_count), ("blocked", 0))

    def test_input_observation_cannot_be_rebound_to_intervening_source(self):
        skill, _, _, relation = self.entry()
        self.frame()
        with self.assertRaises(EvidenceError):
            self.propose(skill)
        other = OrdinaryInputSkill(self.request(self.store.historical_references[-1]), deadline_monotonic=220)
        with self.assertRaises(EvidenceError):
            other.observe(relation, self.store, **self.clocks)

    def test_same_store_and_monotonic_clocks_remain_required(self):
        skill, _, _, _ = self.entry()
        with self.assertRaises(EvidenceError):
            skill.propose(self.store, now_monotonic=99.0, now_timestamp_ms=1_000_000)
        with EvidenceStore(self.bridge, self.root / "other") as other:
            with self.assertRaises(EvidenceError):
                skill.propose(other, **self.clocks)

    def test_click_keeps_original_mapping_while_key_does_not_require_it(self):
        original = self.frame()
        geometry = self.store.observation(original)["frame_geometry"]
        changed = dict(frame_geometry=geometry | dict(window_width=2))
        click = dict(type="click", button="left", x=0, y=0, geometry=geometry)
        skill, _, _, _ = self.entry(original, click, current_changes=changed)
        outcome = self.propose(skill)
        self.assertEqual((outcome.disposition, outcome.proposed_count), ("blocked", 0))
        skill, _, current, _ = self.entry(current_changes=changed)
        self.assertEqual(self.propose(skill).before, current)

    def test_known_return_from_unclassified_screen_stays_returned_without_success_credit(self):
        skill, _, _, _ = self.entry()
        intent = self.propose(skill)
        boundary = dict(kind="unsupported", id="new-interface", control_generation=0, input_receiver=False,
                        recovery_operations=[], interrupt_request_id=None)
        after = self.frame(category="NEVER_SEEN", boundary=boundary)
        outcome = self.accept(skill, intent, after)
        self.assertEqual((outcome.disposition, outcome.basis, outcome.pending_logical_id), ("partial", "ordinary_input", None))
        self.assertTrue(outcome.verification_required)
        self.assertIn(after, outcome.evidence)
        self.assertIs(self.propose(skill), outcome)

    def test_newer_current_observation_does_not_make_known_delivery_unknown(self):
        skill, _, _, _ = self.entry()
        intent = self.propose(skill)
        after = self.frame()
        newer = self.frame()
        outcome = self.accept(skill, intent, after)
        self.assertEqual(outcome.disposition, "partial")
        self.assertIn(after, outcome.evidence)
        self.assertEqual(self.store.current_boundary(**self.clocks), newer)

    def test_late_terminal_history_does_not_need_dispatch_freshness_or_promote_current(self):
        skill, _, _, _ = self.entry()
        intent = self.propose(skill)
        after = self.frame()
        self.clocks = dict(now_monotonic=110.0, now_timestamp_ms=1_010_000)
        self.assertEqual(self.accept(skill, intent, after).disposition, "partial")

    def test_masked_text_scalar_is_known_delivery_and_batch_stops_without_replay(self):
        for text in ("x", "xy"):
            with self.subTest(text=text):
                skill, _, current, _ = self.entry(event=dict(type="text", text=text))
                intent = self.propose(skill)
                outcome = self.accept(skill, intent, self.frame(same=current))
                self.assertEqual((intent.action, outcome.disposition, outcome.proposed_count),
                                 (dict(type="text", text="x"), "partial", 1))
                self.assertIsNone(outcome.pending_logical_id)
                self.assertIs(self.propose(skill), outcome)

    def test_text_batch_charges_each_scalar_and_returns_first_entry_lineage_only_once(self):
        skill, _, _, relation = self.entry(event=dict(type="text", text="éx"))
        first = self.propose(skill)
        self.assertEqual(first.action, dict(type="text", text="é"))
        self.assertIs(self.propose(skill), first)
        self.assertIsNone(self.accept(skill, first, self.frame()))
        second = self.propose(skill)
        self.assertEqual(second.action, dict(type="text", text="x"))
        self.assertIsNone(second.input_observation)
        outcome = self.accept(skill, second, self.frame())
        self.assertEqual(outcome.proposed_count, 2)
        self.assertEqual(outcome.input_observation, relation)
        self.assertTrue(outcome.verification_required)

    def test_text_batch_stops_at_changed_receiver_or_local_limit(self):
        for changed in (True, False):
            with self.subTest(changed=changed):
                limits = dict(primitives=4 if changed else 1, wall_seconds=120, game_seconds=100)
                skill, _, _, _ = self.entry(event=dict(type="text", text="xy"), limits=limits)
                first = self.propose(skill)
                after = self.frame(**(dict(category="VARIANT_AFTER_T") if changed else {}))
                outcome = self.accept(skill, first, after)
                self.assertEqual((outcome.disposition, outcome.proposed_count), ("partial", 1))
                self.assertIs(self.propose(skill), outcome)

    def test_only_unknown_transport_produces_unknown_and_keeps_original_identity(self):
        for status in ("unknown", "dispatched", "rejected", "not_dispatched"):
            with self.subTest(status=status):
                skill, _, _, _ = self.entry()
                intent = self.propose(skill)
                outcome = self.accept(skill, intent, disposition=status)
                self.assertEqual(outcome.disposition, "unknown" if status in ("unknown", "dispatched") else "blocked")
                self.assertEqual(outcome.pending_logical_id, intent.logical_id if outcome.disposition == "unknown" else None)
                self.assertIs(self.propose(skill), outcome)

    def test_incorrect_feedback_is_a_contract_fault_not_inferred_delivery(self):
        skill, _, _, _ = self.entry()
        intent = self.propose(skill)
        with self.assertRaises(ContractError):
            self.accept(skill, intent, self.frame(), action_id="other-input")
        with self.assertRaises(ContractError):
            self.accept(skill, intent, intent.before)
        # Corrupt feedback cannot mint a second logical ID for the same event.
        self.assertIs(self.propose(skill), intent)

    def test_custody_or_missing_receiver_cannot_be_admitted_by_unfamiliar_category(self):
        for field in ("paused", "takeover_generation", "pause_origin", "input_receiver", "control_generation"):
            with self.subTest(field=field):
                original = self.frame()
                state = self.store.observation(original)
                if field in ("input_receiver", "control_generation"):
                    changes = dict(boundary=deepcopy(state["boundary"]) | {field: False if field == "input_receiver" else 1})
                else:
                    changes = {field: {"paused": True, "takeover_generation": 1, "pause_origin": "human"}[field]}
                with self.assertRaises(EvidenceError):
                    self.entry(original, current_changes=changes)

    def test_same_loop_accepts_unfamiliar_and_step_changing_interface_shapes(self):
        for change_after in (0, 2, 5):
            for step in range(7):
                changed = step >= change_after
                labels = ["β", "Stop?"] if changed else ["Proceed", "☂"]
                original = self.frame(category="FLOW_B" if changed else "FLOW_A", actions=labels)
                skill, _, _, _ = self.entry(original, current_changes=dict(category="FLOW_B" if changed else "FLOW_A", actions=labels))
                intent = self.propose(skill)
                outcome = self.accept(skill, intent, self.frame(category=f"RETURN-{step % 3}", actions=list(reversed(labels))))
                self.assertEqual((outcome.disposition, outcome.proposed_count), ("partial", 1))
                self.assertEqual(intent.action["key"], "ESC")


if __name__ == "__main__":
    unittest.main()
