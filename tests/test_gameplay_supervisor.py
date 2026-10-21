"""Retained synthetic evidence and real components; no native/model efficacy claim."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from harness.gameplay.contracts import Budgets, ContractError, PlanCandidate, PrimitiveResult, TaskSpec
from harness.gameplay.evidence import EvidenceError, EvidenceStore
from harness.gameplay.evaluation import RunRecorder, validate_run
from harness.gameplay.planner import PlannerConfig, ProviderReply, ProviderUsage
from harness.gameplay.supervisor import DispatchIntent, WaypointSupervisor


class Clock:
    value = 100.0

    def __call__(self):
        return self.value


class Provider:
    def __init__(self, gated=False, change=None):
        self.requests = []
        self.entered = threading.Event()
        self.release = threading.Event()
        self.cancelled = None
        self.change = change
        if not gated:
            self.release.set()

    def __call__(self, snapshot, cancelled):
        value = json.loads(snapshot.request_json)
        self.requests.append(value)
        self.cancelled = cancelled
        self.entered.set()
        if not self.release.wait(3):
            raise RuntimeError("Synthetic gate timed out")
        binding = value["binding"]
        direction = value["task"]["direction"]
        if binding["expected_stage"] == "return":
            direction = {"east": "west", "west": "east", "north": "south", "south": "north"}[direction]
        data = dict(candidate_id="synthetic-candidate", task_id=binding["task_id"],
                    task_version=binding["task_version"], plan_id=binding["plan_id"],
                    plan_version=binding["plan_version"], execution_epoch=binding["execution_epoch"],
                    evidence_session=binding["evidence_session"], evidence_revision=binding["evidence_revision"],
                    stage=binding["expected_stage"], direction=direction,
                    distance_remaining=binding["distance_remaining"], skill_id="cardinal_movement",
                    skill_version=4, reason="Synthetic bounded route")
        if self.change:
            data.update(self.change)
        return ProviderReply(json.dumps(PlanCandidate(**data).to_dict()), ProviderUsage(10, 5, 0, 0))


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / ".runtime" / "supervisor-tests"
        root.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.clock = Clock()
        self.number = 0
        self.bridge = self.root / "bridge"
        self.bridge.mkdir()
        self.store = EvidenceStore(self.bridge, self.root / "retained")
        self.addCleanup(self.store.close)
        self.values = {}
        self.start_ref = self.frame()
        self.provider = Provider()

    def clocks(self):
        return dict(now_monotonic=self.clock.value,
                    now_timestamp_ms=1_000_000 + round((self.clock.value - 100) * 1000))

    def frame(self, position=(0, 0, 0), *, turn=None, session="world", change=None, revision=None):
        self.number += 1
        turn = getattr(self, "last_turn", 10) if turn is None else turn
        self.last_turn = turn
        value = {"protocol": 5, "pause_origin": "none", "takeover_generation": 0, "ui": None, "id": "observe-is-not-action", "session": session,
                 "revision": self.number if revision is None else revision,
                 "category": "DEFAULTMODE", "actions": ["UP", "DOWN", "LEFT", "RIGHT"],
                 "status": "ready", "error": "", "paused": False,
                 "timestamp_ms": self.clocks()["now_timestamp_ms"], "frame_ok": True,
                 "frame": f"frame-{session}-{self.number}.png", "in_game": True,
                 "boundary": {"kind": "normal_play", "id": "boundary", "control_generation": 0,
                              "recovery_operations": [], "interrupt_request_id": None},
                 "scene": {"provenance": "player-visible input boundary", "position": list(position),
                           "turn": turn, "visible_creatures": [],
                           "neighbors": [{"dx": dx, "dy": dy, "visible": True, "terrain": "t_floor",
                                          "name": "floor", "furniture": "f_null"}
                                         for dy in range(-1, 2) for dx in range(-1, 2) if (dx, dy) != (0, 0)]}}
        if change:
            change(value)
        (self.bridge / value["frame"]).write_bytes(b"\x89PNG\r\n\x1a\nsynthetic-supervisor-fixture")
        ref = self.store.ingest(value, received_monotonic=self.clock.value, **self.clocks())
        self.values[ref.observation_id] = value
        return ref

    def supervisor(self, distance=2, budgets=None, provider=None, config=None):
        task = TaskSpec("task", "world", (0, 0, 0), "east", distance, (distance, 0, 0),
                        1, budgets or Budgets(), "operator")
        self.super = WaypointSupervisor(task=task, run_id="run", store=self.store,
            task_start=self.start_ref, admission_monotonic=100, planner_config=config or
            PlannerConfig("fixture", "configuration"), provider=provider or self.provider, clock=self.clock)
        self.addCleanup(lambda: self.super.abandon("Fixture cleanup", **self.clocks()))
        return self.super

    def status(self):
        return self.super.status(**self.clocks())

    def wait_plan(self):
        deadline = time.monotonic() + 2
        while self.super.accounting_snapshot().physical_call_active:
            if time.monotonic() >= deadline:
                self.fail("Synthetic provider did not exit")
            threading.Event().wait(0.001)
        return self.super.poll(**self.clocks())

    def admitted(self, **options):
        supervisor = self.supervisor(**options)
        supervisor.start(**self.clocks())
        self.wait_plan()
        self.assertEqual(self.status().state, "admitted")
        return supervisor

    def intent(self, name="step"):
        return self.super.propose(name, **self.clocks())

    def result(self, intent, after=None, disposition="returned"):
        displacement = None if after is None or after.session != intent.proposal.before.session else tuple(
            b-a for a, b in zip(self.store.position(intent.proposal.before), self.store.position(after)))
        return PrimitiveResult(intent.proposal.action_id, intent.proposal.before, after,
                               disposition, displacement, "Synthetic transport assertion")

    def step(self, name, position, *, change=None):
        intent = self.intent(name)
        after = self.frame(position, turn=11 + len(self.super.route_history), change=change)
        self.super.settle(intent, self.result(intent, after), **self.clocks())
        return after

    @staticmethod
    def threat(value):
        value["scene"]["visible_creatures"] = [{"name": "zombie", "hostile": True}]

    @staticmethod
    def grass(value):
        for tile in value["scene"]["neighbors"]:
            tile["terrain"] = "t_grass"

    def test_both_legs_require_fresh_return_plan_and_frozen_data_only_intent(self):
        self.admitted(distance=1)
        intent = self.intent()
        self.assertIsInstance(intent, DispatchIntent)
        self.assertFalse(intent.grants_dispatch_authority)
        self.assertEqual((intent.run_id, intent.task_id, intent.task_version, intent.skill_version),
                         ("run", "task", 1, 4))
        with self.assertRaises(FrozenInstanceError):
            intent.execution_epoch = 7
        after = self.frame((1, 0, 0), turn=11)
        self.super.settle(intent, self.result(intent, after), **self.clocks())
        self.assertEqual(self.status().state, "planning")
        self.assertIsNone(self.intent("premature"))
        self.wait_plan()
        self.assertEqual(len(self.provider.requests), 2)
        out, back = self.provider.requests
        self.assertNotEqual(out["binding"]["plan_id"], back["binding"]["plan_id"])
        self.assertEqual(back["binding"]["evidence_revision"], after.revision)
        self.assertEqual(back["packet"]["waypoint"], after.to_dict())
        self.step("back", (0, 0, 0))
        self.assertEqual(self.status().state, "completed")
        self.assertIsNone(self.status().lease_owner)
        self.assertEqual(len(self.super.route_history), 2)

    def test_nonhostile_creatures_allow_both_version_four_legs(self):
        def creatures(value):
            value["scene"]["visible_creatures"] = [{"name": "Cornell", "hostile": False},
                                                     {"name": "cat", "hostile": False}]
        self.start_ref = self.frame(change=creatures)
        self.admitted(distance=1)
        self.step("outbound", (1, 0, 0), change=creatures)
        self.wait_plan()
        self.assertEqual(self.status().state, "admitted")
        self.step("return", (0, 0, 0), change=creatures)
        self.assertEqual(self.status().state, "completed")
        self.assertEqual(len(self.super.route_history), 2)

    def test_partial_both_leg_continuation_keeps_one_port_memory_and_remaining_distance(self):
        self.admitted()
        memory, port = self.super.memory, self.super.planner
        for leg, positions in (("outbound", ((1, 0, 0), (2, 0, 0))),
                               ("return", ((1, 0, 0), (0, 0, 0)))):
            self.step(f"{leg}-one", positions[0])
            self.super.pause("Operator pause", **self.clocks())
            self.frame(positions[0], turn=11 + len(self.super.route_history))
            self.super.continue_task(**self.clocks())
            self.wait_plan()
            self.assertEqual(self.provider.requests[-1]["binding"]["distance_remaining"], 1)
            intent = self.intent(f"{leg}-two")
            self.assertEqual(intent.proposal.expected_position, positions[1])
            after = self.frame(positions[1], turn=12 + len(self.super.route_history))
            self.super.settle(intent, self.result(intent, after), **self.clocks())
            if leg == "outbound": self.wait_plan()
        self.assertEqual(self.status().state, "completed")
        self.assertIs(self.super.memory, memory)
        self.assertIs(self.super.planner, port)
        self.assertEqual(self.status().remaining_budgets.primitives, 4)
        self.assertEqual(len(self.super.memory.snapshot(**self.clocks()).actions), 4)

    def test_complete_leg_post_guard_stop_continues_without_zero_distance_planning(self):
        self.admitted(distance=1, budgets=Budgets(primitives=2, primitives_per_stage=1))
        self.step("out", (1, 0, 0), change=self.threat)
        self.assertEqual(self.status().state, "blocked")
        self.frame((1, 0, 0), turn=11)
        self.super.continue_task(**self.clocks())
        self.wait_plan()
        self.assertEqual(len(self.provider.requests), 2)
        self.assertEqual(self.provider.requests[-1]["binding"]["distance_remaining"], 1)
        self.step("back", (0, 0, 0), change=self.threat)
        self.assertEqual(self.status().state, "blocked")
        verification = self.frame((0, 0, 0), turn=12)
        self.super.continue_task(**self.clocks())
        self.assertEqual(self.status().state, "completed")
        self.assertIn(verification, self.status().evidence)
        self.assertEqual(len(self.provider.requests), 2)
        self.assertIsNone(self.super.pending_intent)
        self.assertEqual(self.status().remaining_budgets.primitives, 0)

    @staticmethod
    def future_neighbor(value, dx, kind):
        tile = next(t for t in value["scene"]["neighbors"] if (t["dx"], t["dy"]) == (dx, 0))
        if kind == "invisible":
            tile.clear()
            tile.update(dx=dx, dy=0, visible=False)
        else:
            tile["furniture"] = "f_cupboard"

    def test_completed_legs_before_cupboards_keep_fresh_return_planning(self):
        self.admitted(distance=1)
        self.step("out", (1, 0, 0), change=lambda v: self.future_neighbor(v, 1, "cupboard"))
        self.wait_plan()
        self.assertEqual(self.status().state, "admitted")
        self.assertEqual(len(self.provider.requests), 2)
        self.assertEqual(self.provider.requests[-1]["binding"]["expected_stage"], "return")
        self.step("back", (0, 0, 0), change=lambda v: self.future_neighbor(v, -1, "cupboard"))
        self.assertEqual(self.status().state, "completed")
        self.assertEqual(len(self.super.route_history), 2)
        self.assertIsNone(self.intent("extra"))

    def test_completed_legs_allow_schema_valid_invisible_future_neighbors(self):
        self.admitted(distance=1)
        self.step("out", (1, 0, 0), change=lambda v: self.future_neighbor(v, 1, "invisible"))
        self.wait_plan()
        self.step("back", (0, 0, 0), change=lambda v: self.future_neighbor(v, -1, "invisible"))
        self.assertEqual(self.status().state, "completed")
        self.assertEqual(len(self.provider.requests), 2)
        self.assertEqual(len(self.super.route_history), 2)

    def test_outbound_completion_does_not_authorize_a_blocked_return_direction(self):
        self.admitted(distance=1)
        self.step("out", (1, 0, 0), change=lambda v: self.future_neighbor(v, -1, "cupboard"))
        self.assertEqual(self.status().state, "blocked")
        self.assertEqual(self.status().progress.verified_steps, 1)
        self.assertEqual(len(self.provider.requests), 1)
        self.assertIsNone(self.intent("blocked-return"))

    def test_intermediate_next_neighbor_still_blocks_without_another_intent(self):
        self.admitted(distance=2)
        self.step("out", (1, 0, 0), change=lambda v: self.future_neighbor(v, 1, "cupboard"))
        self.assertEqual(self.status().state, "blocked")
        self.assertEqual(self.status().progress.verified_steps, 1)
        self.assertEqual(len(self.provider.requests), 1)
        self.assertIsNone(self.intent("blocked-next"))

    def test_final_verification_after_a_threat_still_checks_current_evidence(self):
        self.admitted(distance=1)
        self.step("out", (1, 0, 0))
        self.wait_plan()
        self.step("back", (0, 0, 0), change=self.threat)
        self.assertEqual(self.status().state, "blocked")
        self.frame((0, 0, 0), turn=12, change=lambda v: self.future_neighbor(v, -1, "invisible"))
        self.super.continue_task(**self.clocks())
        self.assertEqual(self.status().state, "completed")
        self.assertEqual(len(self.provider.requests), 2)
        self.assertEqual(len(self.super.route_history), 2)

    def test_pause_at_deadline_cannot_convert_expiry_to_operator_retry_exemption(self):
        self.admitted(budgets=Budgets(primitive_wait_seconds=1))
        intent = self.intent()
        self.clock.value = 101
        self.super.pause("Pause at deadline", **self.clocks())
        self.super.settle(intent, self.result(intent, None, "not_dispatched"), **self.clocks())
        self.frame()
        with self.assertRaises(ContractError):
            self.super.continue_task(**self.clocks())
        self.assertEqual(len(self.provider.requests), 1)
        self.assertEqual(self.status().remaining_budgets.primitives, 7)

    def test_completion_remains_terminal_until_explicit_abandon(self):
        self.admitted(distance=1)
        self.step("out", (1, 0, 0))
        self.wait_plan()
        final = self.step("back", (0, 0, 0))
        epoch = self.status().execution_epoch
        self.super.pause("Later pause", **self.clocks())
        self.super.invalidate("Later takeover", **self.clocks())
        with self.assertRaises(ContractError):
            self.super.pause("Bad clock", now_monotonic=99, now_timestamp_ms=1_000_000)
        self.clock.value = 221
        self.frame(turn=12)
        with self.assertRaises(ContractError):
            self.super.continue_task(**self.clocks())
        status = self.status()
        self.assertEqual((status.state, status.execution_epoch, status.progress.verified_steps),
                         ("completed", epoch, 2))
        self.assertIn(final, status.evidence)
        self.assertEqual(len(self.provider.requests), 2)
        self.super.abandon("Explicit retirement", **self.clocks())
        self.assertEqual(self.status().state, "abandoned")

    def test_foreign_world_turns_cannot_restore_original_reported_budget(self):
        self.admitted()
        self.step("one", (1, 0, 0))
        self.assertEqual(self.status().remaining_budgets.turns, 31)
        self.frame(session="another-world", turn=0)
        self.super.poll(**self.clocks())
        self.assertFalse(self.status().fresh)
        self.assertEqual(self.status().remaining_budgets.turns, 31)

    def test_sticky_disputed_start_never_reaches_provider_with_new_origin_frame(self):
        self.supervisor()
        contradictory = deepcopy(self.values[self.start_ref.observation_id])
        contradictory["scene"]["position"] = [1, 0, 0]
        with self.assertRaises(EvidenceError):
            self.store.ingest(contradictory, received_monotonic=100, **self.clocks())
        self.assertEqual(self.store.source_status(self.start_ref), "disputed")
        self.frame()
        self.super.start(**self.clocks())
        self.assertEqual(self.status().state, "blocked")
        self.assertEqual(self.provider.requests, [])
        self.assertEqual(len(self.super.accounting_snapshot().calls), 0)

    def test_completion_verification_source_is_preserved_and_rechecked_in_status(self):
        self.admitted(distance=1)
        self.step("out", (1, 0, 0))
        self.wait_plan()
        self.step("back", (0, 0, 0), change=self.threat)
        verification = self.frame(turn=12)
        self.super.continue_task(**self.clocks())
        self.assertEqual(self.status().state, "completed")
        self.assertIn(verification, self.status().evidence)
        contradictory = deepcopy(self.values[verification.observation_id])
        contradictory["scene"]["position"] = [1, 0, 0]
        with self.assertRaises(EvidenceError):
            self.store.ingest(contradictory, received_monotonic=100, **self.clocks())
        later = self.frame(turn=12)
        status = self.status()
        self.assertEqual(status.state, "completed")
        self.assertFalse(status.fresh)
        self.assertIn("disputed", status.last_public_reason)
        self.assertIn(verification, status.evidence)
        self.assertNotIn(later, status.evidence)

    def test_result_binding_duplicates_and_logical_id_reuse(self):
        self.admitted()
        intent = self.intent()
        after = self.frame((1, 0, 0), turn=11)
        good = self.result(intent, after)
        for bad_intent, bad_result in ((replace(intent, run_id="other"), good),
                                      (intent, replace(good, action_id="other")),
                                      (intent, replace(good, before=after)),
                                      (intent, replace(good, observed_displacement=(9, 0, 0))),
                                      (intent, replace(good, observed_displacement=None))):
            with self.assertRaises(ContractError):
                self.super.settle(bad_intent, bad_result, **self.clocks())
            self.assertEqual(self.super.pending_intent, intent)
        self.super.settle(intent, good, **self.clocks())
        self.super.settle(intent, good, **self.clocks())
        with self.assertRaises(ContractError):
            self.super.settle(intent, replace(good, reason="conflict"), **self.clocks())
        with self.assertRaises(ContractError): self.intent()
        next_intent = self.intent("next")
        self.super.settle(intent, good, **self.clocks())
        self.assertEqual(self.super.pending_intent, next_intent)

    def test_pause_pending_late_non_delivery_can_only_resolve_exact_intent(self):
        self.admitted()
        intent = self.intent()
        self.super.pause("Operator pause", **self.clocks())
        self.assertEqual(self.super.pending_intent, intent)
        with self.assertRaises(ContractError): self.super.continue_task(**self.clocks())
        bad = self.frame((1, 0, 0), turn=11)
        with self.assertRaises(ContractError):
            self.super.settle(intent, self.result(intent, bad, "not_dispatched"), **self.clocks())
        after = self.frame((0, 0, 0), turn=11)
        result = self.result(intent, after, "not_dispatched")
        self.super.settle(intent, result, **self.clocks())
        self.super.settle(intent, result, **self.clocks())
        self.assertIsNone(self.super.pending_intent)
        self.assertEqual(self.status().remaining_budgets.primitives, 7)
        self.super.continue_task(**self.clocks())
        self.wait_plan()
        self.assertEqual(self.intent("new").proposal.expected_position, (1, 0, 0))

    def test_revoked_returned_and_unknown_results_cannot_gain_credit_or_resume(self):
        self.admitted()
        intent = self.intent()
        self.super.pause("Operator pause", **self.clocks())
        after = self.frame((1, 0, 0), turn=11)
        result = self.result(intent, after)
        self.super.settle(intent, result, **self.clocks())
        self.assertEqual(self.status().state, "unknown")
        self.assertEqual(self.status().progress.verified_steps, 0)
        self.assertEqual(self.super.pending_intent, intent)
        self.frame((0, 0, 0), turn=12)
        with self.assertRaises(ContractError): self.super.continue_task(**self.clocks())
        self.super.settle(intent, result, **self.clocks())
        with self.assertRaises(ContractError):
            self.super.settle(intent, self.result(intent, None, "rejected"), **self.clocks())

    def test_active_unknown_remains_unresolved_after_later_observation(self):
        self.admitted()
        intent = self.intent()
        self.super.settle(intent, self.result(intent, None, "unknown"), **self.clocks())
        self.frame((1, 0, 0), turn=11)
        with self.assertRaises(ContractError): self.super.continue_task(**self.clocks())
        self.assertEqual(self.status().state, "unknown")
        self.assertEqual(self.super.pending_intent, intent)

    def test_no_progress_requires_concrete_change_and_pause_does_not_erase_gate(self):
        self.admitted()
        self.step("zero", (0, 0, 0))
        self.assertEqual(self.status().state, "blocked")
        self.frame()
        with self.assertRaises(ContractError): self.super.continue_task(**self.clocks())
        self.super.pause("Operator pause", **self.clocks())
        self.super.invalidate("Takeover", **self.clocks())
        with self.assertRaises(ContractError): self.super.continue_task(**self.clocks())
        self.frame(change=self.grass)
        self.super.continue_task(**self.clocks())
        self.wait_plan()
        self.step("zero-again", (0, 0, 0), change=self.grass)
        self.frame()  # Previously failed floor signature cannot cycle back in.
        with self.assertRaises(ContractError): self.super.continue_task(**self.clocks())
        self.assertEqual(self.status().remaining_budgets.primitives, 6)

    def test_active_non_delivery_requires_change_and_counts_toward_leg_ceiling(self):
        self.admitted(budgets=Budgets(primitives_per_stage=1))
        intent = self.intent()
        self.super.settle(intent, self.result(intent, None, "rejected"), **self.clocks())
        self.frame(change=self.grass)
        self.super.continue_task(**self.clocks())
        self.assertEqual(self.status().state, "budget_exhausted")
        self.assertEqual(len(self.provider.requests), 1)

    def test_stale_planner_binding_rejects_revision_and_generation_changes(self):
        provider = Provider(gated=True)
        self.addCleanup(provider.release.set)
        self.supervisor(provider=provider).start(**self.clocks())
        self.assertTrue(provider.entered.wait(1))
        self.frame()
        self.super.poll(**self.clocks())
        provider.release.set()
        self.wait_plan()
        self.assertNotEqual(self.status().state, "admitted")
        self.assertIsNone(self.intent())
        self.assertTrue(provider.cancelled.is_set())

    def test_pause_cancelled_provider_retains_physical_slot_and_late_accounting_only(self):
        provider = Provider(gated=True)
        self.addCleanup(provider.release.set)
        self.supervisor(provider=provider).start(**self.clocks())
        self.assertTrue(provider.entered.wait(1))
        self.super.pause("Operator pause", **self.clocks())
        self.assertTrue(provider.cancelled.is_set())
        port = self.super.planner
        self.super.continue_task(**self.clocks())
        self.assertNotEqual(self.status().state, "admitted")
        self.assertEqual(len(provider.requests), 1)
        provider.release.set()
        self.wait_plan()
        self.assertIs(self.super.planner, port)
        self.assertNotEqual(self.status().state, "admitted")
        accounting = self.super.accounting_snapshot()
        self.assertEqual(accounting.calls[0].status, "cancelled")
        self.assertEqual(accounting.calls[0].observed_usage.cost_usd, 0)
        self.super.continue_task(**self.clocks())
        self.wait_plan()
        self.assertEqual(self.status().state, "admitted")

    def test_planner_call_ceiling_stops_without_automatic_retry(self):
        self.admitted(distance=1, budgets=Budgets(planner_calls=1))
        self.step("out", (1, 0, 0))
        self.assertEqual(self.status().state, "budget_exhausted")
        self.assertEqual(len(self.provider.requests), 1)
        self.super.poll(**self.clocks())
        self.assertEqual(len(self.provider.requests), 1)

    def test_source_dispute_and_new_session_never_import_an_origin(self):
        self.admitted()
        self.step("one", (1, 0, 0))
        Path(self.start_ref.frame_path).chmod(0o600)
        Path(self.start_ref.frame_path).write_bytes(b"disputed")
        self.assertIsNone(self.intent("next"))
        self.assertNotEqual(self.status().state, "completed")
        self.frame((1, 0, 0), turn=11, session="another-world")
        self.super.invalidate("Session changed", **self.clocks())
        with self.assertRaises((ContractError, EvidenceError)):
            self.super.continue_task(**self.clocks())
        self.assertEqual(self.super.task_start, self.start_ref)

    def test_threatened_origin_never_admits(self):
        self.supervisor()
        self.frame(change=self.threat)
        self.super.start(**self.clocks())
        self.assertEqual(self.status().state, "blocked")
        self.assertEqual(len(self.provider.requests), 0)

    def test_exact_and_overshot_original_time_turn_budgets_preserve_progress(self):
        self.admitted(distance=1, budgets=Budgets(turns=1))
        intent = self.intent()
        after = self.frame((1, 0, 0), turn=12)
        self.super.settle(intent, self.result(intent, after), **self.clocks())
        self.assertEqual(self.status().state, "budget_exhausted")
        self.assertEqual(self.status().progress.verified_steps, 1)
        self.assertEqual(len(self.provider.requests), 1)
        self.super.continue_task(**self.clocks())
        self.assertEqual(self.status().state, "budget_exhausted")

    def test_wall_budget_includes_pauses_and_planning(self):
        self.admitted(budgets=Budgets(wall_seconds=2))
        self.super.pause("Operator pause", **self.clocks())
        self.clock.value = 102
        self.frame()
        self.super.continue_task(**self.clocks())
        self.assertEqual(self.status().state, "budget_exhausted")
        self.assertEqual(len(self.provider.requests), 1)

    def test_invalid_clocks_revoke_without_losing_pending_and_status_rejects(self):
        self.admitted()
        intent = self.intent()
        bad = self.clocks() | {"now_monotonic": float("nan")}
        with self.assertRaises(ContractError): self.super.poll(**bad)
        self.assertEqual(self.super.pending_intent, intent)
        self.assertIsNone(self.intent("never"))
        with self.assertRaises(ContractError): self.super.status(**bad)
        self.assertEqual(self.super.pending_intent, intent)

    def test_abandon_retires_original_memory_and_preserves_pending_settlement_audit(self):
        self.admitted()
        intent = self.intent()
        self.super.abandon("Goal replacement", **self.clocks())
        self.super.settle(intent, self.result(intent, None, "not_dispatched"), **self.clocks())
        self.assertEqual(self.status().state, "abandoned")
        self.assertTrue(self.super.memory.snapshot(**self.clocks()).retired)
        self.assertEqual(len(self.super.memory.snapshot(**self.clocks()).actions), 0)
        with self.assertRaises(ContractError): self.super.continue_task(**self.clocks())
        self.assertIsNone(self.intent("later"))

    def test_synthetic_events_compose_with_one_planner_snapshot_in_real_recorder(self):
        self.admitted(distance=1)
        self.step("out", (1, 0, 0))
        self.wait_plan()
        final = self.step("back", (0, 0, 0))
        snapshot = self.super.accounting_snapshot()
        events = self.super.evaluation_events(snapshot)
        self.assertEqual(sum(e["kind"] == "model_call" for e in events), 2)
        actions = [e for e in events if e["kind"] == "action"]
        self.assertEqual(len(actions), 2)
        self.assertEqual(sum(e["payload"]["verified_steps"] for e in actions), 2)
        from tests.test_evaluation import manifest, outcome
        recorder = RunRecorder(manifest(run_id="run", admission={"monotonic_ms": 100000,
            "session": "world", "game_turn": 10, "game_turn_missing_reason": None}))
        for event in events:
            recorder.record(event)
        recorder.finish(outcome(elapsed_ms=0, session="world", game_turn=12, verified_steps=2,
            first_useful_action_event_id=None, first_useful_action_missing_reason="Independent assessment absent",
            evidence=[final.to_dict()]))
        self.assertEqual(validate_run(recorder.to_dict())["manifest"]["lane"], "synthetic")
        events[0]["payload"]["corruption"] = True
        self.assertNotIn("corruption", self.super.evaluation_events(snapshot)[0]["payload"])


    def test_irrelevant_action_neighbor_names_and_frame_changes_do_not_clear_retry_gate(self):
        self.admitted()
        self.step("zero", (0, 0, 0))
        def irrelevant(value):
            value["actions"].remove("UP")
            for tile in value["scene"]["neighbors"]:
                tile["name"] = "different display text"
                if (tile["dx"], tile["dy"]) == (0, 1):
                    tile["terrain"] = "t_grass"
        self.clock.value = 101
        self.frame(change=irrelevant)
        with self.assertRaises(ContractError): self.super.continue_task(**self.clocks())
        self.assertEqual(len(self.provider.requests), 1)

    def test_paused_generation_a_b_a_cannot_rebase_a_pending_plan(self):
        provider = Provider(gated=True)
        self.addCleanup(provider.release.set)
        self.supervisor(provider=provider).start(**self.clocks())
        self.assertTrue(provider.entered.wait(1))
        self.frame(revision=self.start_ref.revision)
        self.store.ingest(self.values[self.start_ref.observation_id],
                          received_monotonic=100, **self.clocks())
        self.assertEqual(self.store.current(**self.clocks()), self.start_ref)
        self.super.poll(**self.clocks())
        provider.release.set()
        self.wait_plan()
        self.assertNotEqual(self.status().state, "admitted")
        self.assertTrue(provider.cancelled.is_set())

    def test_wrong_skill_version_candidate_cannot_become_an_intent(self):
        provider = Provider(change={"skill_version": 3})
        self.supervisor(provider=provider).start(**self.clocks())
        self.wait_plan()
        self.assertEqual(self.status().state, "failed")
        self.assertIsNone(self.intent())
        self.assertEqual(len(provider.requests), 1)

    def test_timed_out_provider_late_completion_changes_only_original_accounting(self):
        provider = Provider(gated=True)
        self.addCleanup(provider.release.set)
        self.supervisor(provider=provider, config=PlannerConfig("fixture", "config", call_timeout_seconds=0.5))
        self.super.start(**self.clocks())
        self.assertTrue(provider.entered.wait(1))
        self.clock.value = 100.6
        self.super.poll(**self.clocks())
        self.assertEqual(self.status().state, "budget_exhausted")
        self.assertTrue(provider.cancelled.is_set())
        provider.release.set()
        self.wait_plan()
        self.assertEqual(self.status().state, "budget_exhausted")
        snapshot = self.super.accounting_snapshot()
        self.assertEqual(snapshot.calls[0].status, "timed_out")
        self.assertEqual(snapshot.calls[0].observed_usage.cost_usd, 0)
        self.assertIsNone(self.intent())

    def test_original_planner_spend_reservation_rejects_before_provider_invocation(self):
        self.supervisor(config=PlannerConfig("fixture", "config", reservation_usd_per_call=1,
                                            spend_ceiling_usd=1))
        self.super.start(**self.clocks())
        self.assertEqual(self.status().state, "blocked")
        self.assertEqual(len(self.provider.requests), 0)
        self.assertEqual(self.super.accounting_snapshot().rejection_count, 1)

    def test_stale_origin_does_not_start_provider_or_admit_intent(self):
        self.supervisor()
        self.clock.value = 104
        self.super.start(**self.clocks())
        self.assertEqual(self.status().state, "blocked")
        self.assertFalse(self.status().fresh)
        self.assertEqual(len(self.provider.requests), 0)
        self.assertIsNone(self.intent())

    def test_menu_boundary_invalidates_current_evidence_and_cannot_admit(self):
        self.supervisor()
        def menu(value): value["boundary"]["kind"] = "menu"
        with self.assertRaises(EvidenceError): self.frame(change=menu)
        self.super.start(**self.clocks())
        self.assertEqual(self.status().state, "blocked")
        self.assertEqual(len(self.provider.requests), 0)

    def test_retention_capacity_prevents_planning_and_never_reserves_internally(self):
        self.store.close()
        self.store = EvidenceStore(self.bridge, self.root / "capacity", max_frames=1)
        self.addCleanup(self.store.close)
        self.start_ref = self.frame()
        self.supervisor().start(**self.clocks())
        self.assertEqual(self.status().state, "blocked")
        self.assertEqual(self.status().remaining_budgets.primitives, 8)
        self.assertEqual(len(self.provider.requests), 0)
        self.assertIsNone(self.intent())

    def test_primitive_task_limit_persists_across_stage_handoff(self):
        self.admitted(distance=1, budgets=Budgets(primitives=1))
        self.step("out", (1, 0, 0))
        self.assertEqual(self.status().state, "budget_exhausted")
        self.assertEqual(self.status().remaining_budgets.primitives, 0)
        self.assertEqual(len(self.provider.requests), 1)
        self.super.continue_task(**self.clocks())
        self.assertEqual(self.status().state, "budget_exhausted")

    def test_wall_overshoot_exceeds_clipped_wait_and_cannot_gain_late_credit(self):
        self.admitted(distance=1, budgets=Budgets(wall_seconds=1))
        intent = self.intent()
        self.clock.value = 102
        after = self.frame((1, 0, 0), turn=11)
        self.super.settle(intent, self.result(intent, after), **self.clocks())
        self.assertEqual(self.status().state, "unknown")
        self.assertEqual(self.status().progress.verified_steps, 0)
        self.assertEqual(self.super.pending_intent, intent)
        self.assertEqual(self.status().remaining_budgets.wall_seconds, 0)
        self.assertEqual(len(self.provider.requests), 1)

    def test_pending_world_change_poll_revokes_and_late_return_cannot_credit(self):
        self.admitted()
        intent = self.intent()
        after = self.frame((1, 0, 0), turn=11, session="another-world")
        self.super.poll(**self.clocks())
        self.assertEqual(self.status().state, "unknown")
        self.super.settle(intent, self.result(intent, after, "unknown"), **self.clocks())
        self.assertEqual(self.status().progress.verified_steps, 0)
        self.assertEqual(self.super.pending_intent, intent)
        with self.assertRaises(ContractError): self.super.continue_task(**self.clocks())

    def test_unknown_result_is_retained_in_original_memory_without_route_credit(self):
        self.admitted()
        intent = self.intent()
        result = self.result(intent, None, "dispatched")
        self.super.settle(intent, result, **self.clocks())
        actions = self.super.memory.snapshot(**self.clocks()).actions
        self.assertEqual(tuple(a.value for a in actions), (result,))
        self.assertEqual(self.super.route_history, ())
        self.assertEqual(self.status().remaining_budgets.primitives, 7)

    def test_invalid_clock_settlement_preserves_intent_and_rejects_late_credit(self):
        self.admitted()
        intent = self.intent()
        after = self.frame((1, 0, 0), turn=11)
        result = self.result(intent, after)
        with self.assertRaises(ContractError):
            self.super.settle(intent, result, **(self.clocks() | {"now_timestamp_ms": True}))
        self.assertEqual(self.super.pending_intent, intent)
        self.super.settle(intent, result, **self.clocks())
        self.assertEqual(self.status().state, "unknown")
        self.assertEqual(self.status().progress.verified_steps, 0)

    def test_status_is_a_snapshot_and_does_not_rebind_changed_evidence(self):
        self.admitted()
        before = self.status()
        self.frame()
        after = self.status()
        self.assertEqual((after.plan_id, after.execution_epoch), (before.plan_id, before.execution_epoch))
        self.assertIsNone(self.intent())
        self.assertNotEqual(self.status().state, "admitted")

    def test_decision_events_are_bounded_with_explicit_dropped_count(self):
        self.admitted()
        for n in range(80): self.super.pause(f"Operator pause {n}", **self.clocks())
        events = self.super.evaluation_events(self.super.accounting_snapshot())
        self.assertEqual(sum(e["kind"] == "decision" for e in events), 64)
        self.assertGreater(self.super.dropped_decision_events, 0)
        self.assertEqual(sum(e["kind"] == "model_call" for e in events), 1)

    def test_start_is_once_and_original_task_cannot_be_replaced_by_continuation(self):
        self.admitted()
        task = self.super.task
        with self.assertRaises(ContractError): self.super.start(**self.clocks())
        self.super.pause("Operator pause", **self.clocks())
        self.frame((1, 0, 0), turn=11)
        with self.assertRaises(EvidenceError): self.super.continue_task(**self.clocks())
        self.assertIs(self.super.task, task)
        self.assertEqual(self.super.task_start, self.start_ref)


    def test_first_non_operator_revocation_cannot_be_promoted_by_later_pause(self):
        self.admitted()
        intent = self.intent()
        with self.assertRaises(ContractError):
            self.super.poll(**(self.clocks() | {"now_monotonic": float("nan")}))
        self.super.pause("Later operator pause", **self.clocks())
        self.super.settle(intent, self.result(intent, None, "not_dispatched"), **self.clocks())
        self.frame()
        with self.assertRaises(ContractError): self.super.continue_task(**self.clocks())
        self.frame(change=self.grass)
        self.super.continue_task(**self.clocks())
        self.wait_plan()
        self.assertEqual(self.status().state, "admitted")

    def test_poll_at_exact_pending_wait_deadline_revokes_and_preserves_context(self):
        self.admitted(budgets=Budgets(primitive_wait_seconds=1))
        intent = self.intent()
        self.clock.value = 101
        self.super.poll(**self.clocks())
        self.assertEqual(self.status().state, "unknown")
        self.assertEqual(self.super.pending_intent, intent)
        self.assertEqual(self.status().remaining_budgets.primitives, 7)
        after = self.frame((1, 0, 0), turn=11)
        self.super.settle(intent, self.result(intent, after), **self.clocks())
        self.assertEqual(self.status().progress.verified_steps, 0)
        self.assertEqual(self.super.pending_intent, intent)

    def test_settle_at_exact_wait_deadline_cannot_gain_credit_without_poll(self):
        self.admitted(budgets=Budgets(primitive_wait_seconds=1))
        intent = self.intent()
        self.clock.value = 101
        after = self.frame((1, 0, 0), turn=11)
        self.super.settle(intent, self.result(intent, after), **self.clocks())
        self.assertEqual(self.status().state, "unknown")
        self.assertEqual(self.status().progress.verified_steps, 0)
        with self.assertRaises(ContractError): self.super.continue_task(**self.clocks())

    def test_expired_intent_non_delivery_releases_but_requires_changed_conditions(self):
        self.admitted(budgets=Budgets(primitive_wait_seconds=1))
        intent = self.intent()
        self.clock.value = 101
        self.super.settle(intent, self.result(intent, None, "rejected"), **self.clocks())
        self.assertIsNone(self.super.pending_intent)
        self.assertEqual(self.status().remaining_budgets.primitives, 7)
        with self.assertRaises(ContractError): self.super.continue_task(**self.clocks())
        self.frame(change=self.grass)
        self.super.continue_task(**self.clocks())
        self.wait_plan()
        self.assertEqual(self.status().state, "admitted")


    def test_pending_expired_and_later_settled_exports_each_record_one_charged_attempt(self):
        from tests.test_evaluation import manifest, outcome
        self.admitted(budgets=Budgets(primitive_wait_seconds=1))
        intent = self.intent()
        def export():
            events = self.super.evaluation_events(self.super.accounting_snapshot())
            actions = [e for e in events if e["kind"] == "action"]
            self.assertEqual(len(actions), 1)
            recorder = RunRecorder(manifest(run_id="run", admission={"monotonic_ms": 100000,
                "session": "world", "game_turn": 10, "game_turn_missing_reason": None}))
            for event in events: recorder.record(event)
            recorder.finish(outcome(disposition="unknown", elapsed_ms=(self.clock.value-100)*1000,
                session="world", game_turn=10, verified_steps=None,
                verified_steps_missing_reason="No independent task assessment",
                first_useful_action_event_id=None,
                first_useful_action_missing_reason="No useful action assessment"))
            validate_run(recorder.to_dict())
            return actions[0]
        pending = export()
        self.assertEqual(pending["payload"]["dispatch_state"], "unknown")
        self.assertIsNone(pending["payload"]["verified_steps"])
        self.assertFalse(pending["payload"]["stale"])
        self.clock.value = 101
        self.super.poll(**self.clocks())
        expired = export()
        self.assertEqual(expired["payload"]["duration_ms"], 1000)
        self.assertTrue(expired["payload"]["stale"])
        self.assertEqual(self.super.pending_intent, intent)
        self.super.settle(intent, self.result(intent, None, "rejected"), **self.clocks())
        settled = export()
        self.assertEqual(settled["payload"]["dispatch_state"], "not_dispatched")
        self.assertEqual(settled["payload"]["verified_steps"], 0)
        self.assertIsNone(self.super.pending_intent)
        self.assertEqual(pending["payload"]["dispatch_state"], "unknown")


    def test_maximum_distance_four_composes_eight_attempts_and_retained_memory_bounds(self):
        self.admitted(distance=4)
        for number in range(1, 5): self.step(f"out-{number}", (number, 0, 0))
        self.wait_plan()
        for number in range(1, 5): self.step(f"back-{number}", (4-number, 0, 0))
        status = self.status()
        status.to_dict()
        self.assertEqual(status.state, "completed")
        self.assertEqual(status.progress.verified_steps, 8)
        self.assertEqual(status.progress.displacement, (0, 0, 0))
        self.assertEqual(status.remaining_budgets.primitives, 0)
        self.assertEqual(len(status.evidence), 9)
        self.assertTrue(all(self.store.source_status(ref) == "retained" for ref in status.evidence))
        memory = self.super.memory.snapshot(**self.clocks())
        self.assertEqual(memory.counts.actions, 8)
        self.assertEqual(memory.counts.plans, 2)
        self.assertEqual(memory.counts.unique_sources, 9)
        self.assertLessEqual(memory.counts.text_bytes, 64*1024)
        events = self.super.evaluation_events(self.super.accounting_snapshot())
        self.assertEqual(sum(e["kind"] == "action" for e in events), 8)
        self.assertEqual(sum(e["kind"] == "model_call" for e in events), 2)
        self.assertIsNone(self.super.pending_intent)

    def test_slow_planning_status_and_pending_poll_do_not_invalidate_by_age(self):
        provider = Provider(gated=True)
        supervisor = self.supervisor(provider=provider)
        supervisor.start(**self.clocks())
        self.assertTrue(provider.entered.wait(1))
        generation = self.store.authority_generation()
        self.clock.value += 4
        for _ in range(5):
            self.assertFalse(self.status().fresh)
            self.assertEqual(supervisor.poll(**self.clocks()).state, "planning")
        self.assertEqual(self.store.authority_generation(), generation)
        provider.release.set()
        while supervisor.accounting_snapshot().physical_call_active:
            threading.Event().wait(0.001)
        refreshed = self.frame(revision=self.start_ref.revision)
        admitted = supervisor.revalidate_planning(refreshed, **self.clocks())
        self.assertEqual(admitted.state, "admitted")
        self.assertEqual(supervisor.task_start, self.start_ref)
        self.assertEqual(self.intent().proposal.before, refreshed)
        events = supervisor.evaluation_events(supervisor.accounting_snapshot())
        self.assertTrue(any(len(e["evidence"]) == 2 and e["payload"].get("reason") == "equivalent"
                            for e in events))

    def test_planning_refresh_rejects_changed_pixels_and_intervening_generation(self):
        for changed_pixels in (True, False):
            with self.subTest(changed_pixels=changed_pixels):
                # Use a separate component instance for each integrity history.
                supervisor = self.supervisor()
                supervisor.start(**self.clocks())
                while supervisor.accounting_snapshot().physical_call_active:
                    threading.Event().wait(0.001)
                self.clock.value += 0.1
                original = deepcopy(self.values[self.start_ref.observation_id])
                original["frame"] = f"frame-world-{self.number + 1}.png"
                original["timestamp_ms"] = self.clocks()["now_timestamp_ms"]
                (self.bridge / original["frame"]).write_bytes(b"\x89PNG\r\n\x1a\n" +
                    (b"different pixels" if changed_pixels else b"synthetic-supervisor-fixture"))
                ref = self.store.ingest(original, received_monotonic=self.clock.value, **self.clocks())
                self.number += 1
                if not changed_pixels:
                    self.clock.value += 0.1
                    ref = self.frame(revision=self.start_ref.revision)
                self.assertEqual(supervisor.revalidate_planning(ref, **self.clocks()).state, "interrupted")
                supervisor.abandon("Subcase complete", **self.clocks())
                # Restore a new base checkpoint without hiding the prior generation.
                self.start_ref = self.frame()

    def test_revalidation_cannot_renew_original_planning_deadline(self):
        supervisor = self.supervisor()
        supervisor.start(**self.clocks())
        while supervisor.accounting_snapshot().physical_call_active:
            threading.Event().wait(0.001)
        self.clock.value = 130
        refreshed = self.frame(revision=self.start_ref.revision)
        status = supervisor.revalidate_planning(refreshed, **self.clocks())
        self.assertEqual(status.state, "interrupted")
        self.assertIn("deadline", status.last_public_reason)
        self.assertEqual(status.remaining_budgets.planner_calls, 9)

    def test_explicit_revalidation_requires_a_distinct_refresh_generation(self):
        supervisor = self.supervisor()
        supervisor.start(**self.clocks())
        while supervisor.accounting_snapshot().physical_call_active:
            threading.Event().wait(0.001)
        status = supervisor.revalidate_planning(self.start_ref, **self.clocks())
        self.assertEqual(status.state, "interrupted")
        self.assertIn("invalidation", status.last_public_reason)


if __name__ == "__main__":
    unittest.main()
