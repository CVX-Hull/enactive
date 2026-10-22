"""Portable skill tests with real retention; synthetic frames are not native proof."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import tempfile
import unittest

from harness.gameplay.contracts import Budgets, ContractError, PrimitiveResult, TaskSpec
from harness.gameplay.evidence import EvidenceError, EvidenceStore
from harness.gameplay.skills import CARDINAL_MOVEMENT, MovementStage, RouteAttempt, SkillEvaluation, StepProposal, summarize_route
from harness.movement import DIRECTIONS


class MovementSkillTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / ".runtime" / "skill-tests"
        root.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.serial = 0
        self.reset()

    def reset(self, **limits):
        if hasattr(self, "store"):
            self.store.close()
        self.serial += 1
        self.bridge = self.root / str(self.serial) / "bridge"
        self.bridge.mkdir(parents=True)
        self.store = EvidenceStore(self.bridge, self.bridge.parent / "retained", **limits)
        self.addCleanup(self.store.close)
        self.number = 0
        self.values = {}

    def frame(self, position=(0, 0, 0), *, turn=10, now=100.0,
              timestamp=1_000_000, session="world", revision=None, change=None,
              reservation=None):
        self.number += 1
        value = {"protocol": 6, "pause_origin": "none", "takeover_generation": 0, "ui": None, "id": "native-observe-is-not-logical-action",
                 "session": session, "revision": self.number if revision is None else revision,
                 "category": "DEFAULTMODE", "actions": ["UP", "DOWN", "LEFT", "RIGHT"],
                 "status": "ready", "error": "", "paused": False,
                 "timestamp_ms": timestamp, "frame_ok": True,
                 "frame_geometry": {"window_width": 800, "window_height": 600,
                    "output_width": 800, "output_height": 600, "viewport": [0, 0, 800, 600]},
                 "frame": f"frame-{session}-{self.number}.png", "in_game": True,
                 "boundary": {"kind": "normal_play", "id": "boundary", "control_generation": 0,
                              "input_receiver": True, "recovery_operations": [], "interrupt_request_id": None},
                 "scene": {"provenance": "player-visible input boundary", "position": list(position),
                           "turn": turn, "visible_creatures": [],
                           "neighbors": [{"dx": dx, "dy": dy, "visible": True, "terrain": "t_floor",
                                          "name": "floor", "furniture": "f_null"}
                                         for dy in range(-1, 2) for dx in range(-1, 2) if (dx, dy) != (0, 0)]}}
        if change:
            change(value)
        (self.bridge / value["frame"]).write_bytes(b"\x89PNG\r\n\x1a\nsynthetic-portable-fixture")
        ref = self.store.ingest(value, received_monotonic=now, now_monotonic=now,
                                now_timestamp_ms=timestamp, reservation=reservation)
        self.values[ref.observation_id] = value
        return ref

    def task(self, direction="east", distance=2, **changes):
        dx, dy, _ = DIRECTIONS[direction]
        values = dict(task_id="task", session="world", origin=(0, 0, 0), direction=direction,
                      distance=distance, target=(dx * distance, dy * distance, 0), task_version=1,
                      budgets=Budgets(), operator_request_id="operator")
        return TaskSpec(**(values | changes))

    def stage(self, task=None, start=None, **changes):
        start = self.frame() if start is None else start
        values = dict(stage_id="outbound", stage_version=1, stage="outbound", store=self.store,
                      task_start=start, checkpoint=start, admission_monotonic=100.0,
                      history=())
        return MovementStage(task or self.task(), **(values | changes))

    def propose(self, stage, action_id="logical-1", **changes):
        return stage.propose(action_id, **(dict(now_monotonic=100.0, now_timestamp_ms=1_000_000,
                                               paused=False, frozen=False) | changes))

    def settle(self, stage, result, **changes):
        return stage.settle(result, **(dict(now_monotonic=100.0, now_timestamp_ms=1_000_000,
                                           paused=False, frozen=False) | changes))

    def result(self, proposal, after=None, disposition="returned", displacement=None):
        if displacement is None and after is not None and after.session == proposal.before.session:
            a, b = self.store.position(proposal.before), self.store.position(after)
            displacement = tuple(y - x for x, y in zip(a, b))
        return PrimitiveResult(proposal.action_id, proposal.before, after, disposition, displacement,
                               "Synthetic transport result")

    def obstruct_neighbor(self, value, dx, dy, obstacle):
        tile = next(t for t in value["scene"]["neighbors"] if (t["dx"], t["dy"]) == (dx, dy))
        if obstacle == "invisible":
            tile.clear()
            tile.update(dx=dx, dy=dy, visible=False)
        else:
            tile.update({"terrain": "t_wall"} if obstacle == "wall" else {"furniture": "f_cupboard"})

    def test_descriptor_declares_only_implemented_predicates_and_bindings(self):
        self.assertEqual(CARDINAL_MOVEMENT.skill_version, 4)
        self.assertIn("known_nonhostile_visible_creatures", CARDINAL_MOVEMENT.observable_predicates)
        self.assertIn("hostile_or_unknown_visible_creatures_or_current_boundary", CARDINAL_MOVEMENT.stop_rules)
        self.assertIn("current_boundary_at_exact_verified_target", CARDINAL_MOVEMENT.observable_predicates)
        self.assertIn("visible_allowlisted_furniture_free_neighbor_before_further_step", CARDINAL_MOVEMENT.observable_predicates)
        self.assertIn("current_guard_at_target_full_guard_before_further_step", CARDINAL_MOVEMENT.postconditions)
        self.assertEqual(set(CARDINAL_MOVEMENT.action_bindings), {"UP", "DOWN", "LEFT", "RIGHT"})
        self.assertEqual(CARDINAL_MOVEMENT.maximum_budgets.primitives_per_stage, 4)
        self.assertEqual(CARDINAL_MOVEMENT.contexts, ("normal_play",))
        self.assertEqual(type(CARDINAL_MOVEMENT).from_dict(CARDINAL_MOVEMENT.to_dict()), CARDINAL_MOVEMENT)

    def test_all_cardinal_full_legs_and_return(self):
        for direction, (dx, dy, action) in DIRECTIONS.items():
            with self.subTest(direction=direction):
                self.reset()
                task = self.task(direction, 4)
                start = self.frame()
                stage = self.stage(task, start)
                history = ()
                for number in range(1, 5):
                    proposal = self.propose(stage, f"out-{number}")
                    self.assertIsInstance(proposal, StepProposal)
                    self.assertEqual(proposal.action, action)
                    self.assertEqual(proposal.expected_position, (dx * number, dy * number, 0))
                    after = self.frame(proposal.expected_position, turn=10 + number)
                    result = self.result(proposal, after)
                    value = self.settle(stage, result)
                    history += (RouteAttempt("outbound", result),)
                    self.assertEqual(value.progress.verified_steps, number)
                    self.assertEqual(value.stage_result is None, number < 4)
                self.assertEqual(value.stage_result.disposition, "completed")
                self.assertEqual(value.progress.displacement, (dx * 4, dy * 4, 0))
                back = self.stage(task, start, stage="return", stage_id="return", checkpoint=after, history=history)
                for number in range(1, 5):
                    proposal = self.propose(back, f"back-{number}")
                    after = self.frame((dx * (4 - number), dy * (4 - number), 0), turn=14 + number)
                    value = self.settle(back, self.result(proposal, after))
                self.assertEqual(value.stage_result.disposition, "completed")
                self.assertEqual(value.progress.displacement, (-dx * 4, -dy * 4, 0))

    def test_nonhostile_npc_and_monster_allow_proposal_and_target_verification(self):
        for name in ("Cornell", "cat"):
            with self.subTest(name=name):
                self.reset()
                def change(v):
                    v["scene"]["visible_creatures"] = [{"name": name, "hostile": False}]
                start = self.frame(change=change)
                stage = self.stage(self.task(distance=1), start)
                proposal = self.propose(stage)
                self.assertIsInstance(proposal, StepProposal)
                after = self.frame((1, 0, 0), turn=11, change=change)
                value = self.settle(stage, self.result(proposal, after))
                self.assertEqual((value.stage_result.disposition, value.progress.verified_steps), ("completed", 1))

    def test_frozen_proposal_evaluation_and_single_outstanding(self):
        stage = self.stage()
        proposal = self.propose(stage)
        with self.assertRaises(FrozenInstanceError):
            proposal.action = "UP"
        with self.assertRaises(ContractError):
            self.propose(stage, "second")
        after = self.frame((1, 0, 0), turn=11)
        value = self.settle(stage, self.result(proposal, after))
        with self.assertRaises(FrozenInstanceError):
            value.reason = "changed"
        self.assertEqual(stage.progress, value.progress)

    def test_final_neighbor_does_not_block_target_but_stops_an_intermediate_step(self):
        for direction, (dx, dy, _) in DIRECTIONS.items():
            for obstacle in ("wall", "cupboard", "invisible"):
                for distance in (1, 2):
                    with self.subTest(direction=direction, obstacle=obstacle, distance=distance):
                        self.reset()
                        task = self.task(direction, distance)
                        start = self.frame()
                        stage = self.stage(task, start)
                        proposal = self.propose(stage)
                        after = self.frame((dx, dy, 0), turn=11,
                                           change=lambda v: self.obstruct_neighbor(v, dx, dy, obstacle))
                        result = self.result(proposal, after)
                        value = self.settle(stage, result)
                        self.assertEqual(value.progress.verified_steps, 1)
                        self.assertEqual(value.stage_result.disposition,
                                         "completed" if distance == 1 else "blocked")
                        self.assertIsNone(value.stage_result.pending_action_id)
                        self.assertEqual(self.settle(stage, result), value)
                        self.assertEqual(self.propose(stage, "no-extra-proposal"), value)
                        continued = self.stage(task, start, checkpoint=after,
                                               history=(RouteAttempt("outbound", result),))
                        verified = self.propose(continued, "verify-or-step")
                        self.assertEqual(verified.stage_result.disposition,
                                         "completed" if distance == 1 else "blocked")
                        self.assertIsNone(verified.primitive_result)
                        self.assertIsNone(verified.stage_result.pending_action_id)
                        self.assertEqual(self.propose(continued, "still-terminal"), verified)

    def test_target_current_guards_still_stop_settlement_and_retained_verification(self):
        for stop in ("creature", "action", "stale", "paused", "frozen"):
            for retained in (False, True):
                with self.subTest(stop=stop, retained=retained):
                    self.reset()
                    task = self.task(distance=1)
                    start = self.frame()
                    stage = self.stage(task, start)
                    proposal = self.propose(stage)
                    def mutation(v):
                        self.obstruct_neighbor(v, 1, 0, "cupboard")
                        if stop == "creature":
                            v["scene"]["visible_creatures"] = [{"name": "zombie", "hostile": True}]
                        elif stop == "action":
                            v["actions"] = ["LEFT"]
                    after = self.frame((1, 0, 0), turn=11, change=mutation)
                    result = self.result(proposal, after)
                    flags = {stop: True} if stop in ("paused", "frozen") else {}
                    clocks = dict(now_monotonic=104, now_timestamp_ms=1_004_000) if stop == "stale" else {}
                    if retained:
                        stage = self.stage(task, start, checkpoint=after,
                                           history=(RouteAttempt("outbound", result),))
                        value = self.propose(stage, "verify-only", **(flags | clocks))
                    else:
                        value = self.settle(stage, result, **(flags | clocks))
                    self.assertNotEqual(value.stage_result.disposition, "completed")
                    self.assertEqual(value.stage_result.disposition,
                                     "interrupted" if flags else ("unknown" if stop == "stale" else "blocked"))
                    self.assertEqual(value.progress.verified_steps, 1 if retained or stop != "stale" else 0)
                    self.assertEqual(self.propose(stage, "no-rearm"), value)

    def test_completed_target_still_requires_complete_schema_valid_evidence(self):
        for change in (lambda v: v["scene"]["neighbors"].pop(),
                       lambda v: v["scene"].update(visible_creatures=None)):
            with self.subTest(change=change):
                self.reset()
                stage = self.stage(task=self.task(distance=1))
                proposal = self.propose(stage)
                with self.assertRaises(EvidenceError):
                    self.frame((1, 0, 0), turn=11, change=change)
                value = self.settle(stage, self.result(proposal, None, "unknown"))
                self.assertNotEqual(value.stage_result.disposition, "completed")
                self.assertEqual(value.progress.verified_steps, 0)

    def test_constructor_rejects_bad_types_identity_and_original_history(self):
        start = self.frame()
        for changes in ({"stage": "continue"}, {"stage_id": ""}, {"stage_version": True},
                        {"admission_monotonic": float("nan")}, {"admission_monotonic": -1},
                        {"admission_monotonic": 10**1000},
                        {"history": True}, {"history": []},
                        {"store": object()}, {"task_start": start.to_dict()},
                        {"task_start": replace(start, revision=99)}, {"stage": "return"}):
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                self.stage(start=start, **changes)
        with self.assertRaises(ContractError):
            self.stage(task=self.task(session="other"), start=start)
        middle = self.frame((1, 0, 0), turn=11)
        with self.assertRaises(ContractError):
            self.stage(start=start, checkpoint=middle)
        target = self.frame((2, 0, 0), turn=12)
        with self.assertRaises(ContractError):
            self.stage(start=start, stage="return", checkpoint=target)
        # The removed full-leg/count API has no compatibility path.
        with self.assertRaises(TypeError):
            self.stage(start=start, prior_primitive_count=2)

    def test_guard_preconditions_stop_before_proposal(self):
        mutations = (
            lambda v: v.update(paused=True),
            lambda v: v.update(actions=["LEFT"]),
            lambda v: v["scene"].update(visible_creatures=[{"name": "zombie", "hostile": True}]),
            lambda v: next(t for t in v["scene"]["neighbors"] if (t["dx"], t["dy"]) == (1, 0)).update(terrain="t_wall"),
            lambda v: next(t for t in v["scene"]["neighbors"] if (t["dx"], t["dy"]) == (1, 0)).update(furniture="f_chair"),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.reset()
                start = self.frame(change=mutation)
                value = self.propose(self.stage(start=start))
                self.assertIsInstance(value, SkillEvaluation)
                self.assertIn(value.stage_result.disposition, ("blocked", "interrupted"))
                self.assertEqual(value.progress.verified_steps, 0)
        for flags in ({"paused": True}, {"frozen": True}):
            self.reset()
            self.assertEqual(self.propose(self.stage(), **flags).stage_result.disposition, "interrupted")
        self.reset()
        def invisible(v):
            tile = next(t for t in v["scene"]["neighbors"] if (t["dx"], t["dy"]) == (1, 0))
            tile.clear()
            tile.update(dx=1, dy=0, visible=False)
        start = self.frame(change=invisible)
        self.assertEqual(self.propose(self.stage(start=start)).stage_result.disposition, "blocked")

    def test_unsupported_missing_or_malformed_frames_invalidate_before_proposal(self):
        for mutation in (lambda v: v["boundary"].update(kind="menu"),
                         lambda v: v.update(frame_ok=False), lambda v: v.update(scene=None),
                         lambda v: v["scene"].update(position=[False, 0, 0]),
                         lambda v: v["scene"]["neighbors"][0].clear()):
            self.reset()
            stage = self.stage()
            with self.assertRaises(EvidenceError):
                self.frame(change=mutation)
            self.assertIsNotNone(self.propose(stage).stage_result)

    def test_stale_first_frame_and_missing_retained_bytes_stop(self):
        for missing in (False, True):
            self.reset()
            start = self.frame()
            stage = self.stage(start=start)
            if missing:
                Path(start.frame_path).unlink()
            value = self.propose(stage, now_monotonic=104 if not missing else 100,
                                 now_timestamp_ms=1_004_000 if not missing else 1_000_000)
            self.assertEqual(value.progress.verified_steps, 0)
            self.assertIsNotNone(value.stage_result)

    def test_generation_change_and_a_b_a_restoration_cannot_restore_intent(self):
        start = self.frame()
        stage = self.stage(start=start)
        self.frame(revision=1)  # B shares scene/revision and is independently retained.
        self.store.ingest(self.values[start.observation_id], received_monotonic=100,
                          now_monotonic=100, now_timestamp_ms=1_000_000)
        self.assertEqual(self.store.current(now_monotonic=100, now_timestamp_ms=1_000_000), start)
        self.assertIsNotNone(self.propose(stage).stage_result)

    def test_extra_generation_at_settlement_does_not_credit_movement(self):
        stage = self.stage()
        proposal = self.propose(stage)
        self.frame((1, 0, 0), turn=11)
        after = self.frame((1, 0, 0), turn=11, revision=2)
        value = self.settle(stage, self.result(proposal, after))
        self.assertEqual(value.stage_result.disposition, "unknown")
        self.assertEqual(value.progress.verified_steps, 0)
        self.assertEqual(value.stage_result.pending_action_id, proposal.action_id)

    def test_older_credited_frame_dispute_invalidates_completion(self):
        stage = self.stage()
        first = self.propose(stage)
        after = self.frame((1, 0, 0), turn=11)
        self.settle(stage, self.result(first, after))
        second = self.propose(stage, "logical-2")
        final = self.frame((2, 0, 0), turn=12,
                           change=lambda v: self.obstruct_neighbor(v, 1, 0, "cupboard"))
        bad = deepcopy(self.values[after.observation_id])
        bad["scene"]["position"] = [9, 0, 0]
        with self.assertRaises(EvidenceError):
            self.store.ingest(bad, received_monotonic=100, now_monotonic=100, now_timestamp_ms=1_000_000)
        # Restore a fresh current frame; neither restoration nor full target fixes old evidence.
        final = self.frame((2, 0, 0), turn=12)
        self.assertEqual(self.store.source_status(after), "disputed")
        value = self.settle(stage, self.result(second, final))
        self.assertNotEqual(value.stage_result.disposition, "completed")
        self.assertEqual(value.progress.verified_steps, 1)

    def test_disputed_credited_source_before_next_proposal_stops_unknown(self):
        stage = self.stage()
        first = self.propose(stage)
        after = self.frame((1, 0, 0), turn=11)
        self.settle(stage, self.result(first, after))
        bad = deepcopy(self.values[after.observation_id])
        bad["scene"]["position"] = [9, 0, 0]
        with self.assertRaises(EvidenceError):
            self.store.ingest(bad, received_monotonic=100, now_monotonic=100,
                              now_timestamp_ms=1_000_000)
        value = self.propose(stage, "logical-2")
        self.assertEqual(value.stage_result.disposition, "unknown")
        self.assertEqual(value.progress.verified_steps, 1)
        self.assertEqual(self.propose(stage, "logical-3"), value)

    def test_correlation_malformed_and_conflicting_results_never_release_pending(self):
        stage = self.stage()
        proposal = self.propose(stage)
        after = self.frame((1, 0, 0), turn=11)
        good = self.result(proposal, after)
        for bad in (None, good.to_dict(), replace(good, action_id="native-observe-is-not-logical-action"),
                    replace(good, before=after), replace(good, observed_displacement=None),
                    replace(good, observed_displacement=(9, 0, 0))):
            with self.subTest(bad=bad), self.assertRaises(ContractError):
                self.settle(stage, bad)
            with self.assertRaises(ContractError):
                self.propose(stage, "new")
        value = self.settle(stage, good)
        self.assertEqual(self.settle(stage, good), value)
        self.assertEqual(stage.progress.verified_steps, 1)
        with self.assertRaises(ContractError):
            self.settle(stage, replace(good, reason="Conflicting duplicate"))
        with self.assertRaises(ContractError):
            self.propose(stage, proposal.action_id)

    def test_unknown_rejection_and_no_progress_are_terminal(self):
        for disposition in ("unknown", "dispatched", "rejected", "not_dispatched", "returned"):
            self.reset()
            stage = self.stage()
            proposal = self.propose(stage)
            after = proposal.before if disposition == "returned" else None
            result = self.result(proposal, after, disposition)
            value = self.settle(stage, result)
            self.assertEqual(value.progress.verified_steps, 0)
            self.assertIsNotNone(value.stage_result)
            self.assertEqual(value.stage_result.disposition == "unknown", disposition in ("unknown", "dispatched"))
            self.assertEqual(self.propose(stage, "another"), value)
            self.frame((1, 0, 0), turn=11)
            self.assertEqual(self.settle(stage, result), value)
            with self.assertRaises(ContractError):
                self.settle(stage, result.to_dict())
            with self.assertRaises(ContractError):
                self.settle(stage, replace(result, reason="Conflicting terminal result"))
            self.assertEqual(self.propose(stage, "still-terminal"), value)

    def test_unknown_cross_session_context_never_credits_or_later_reconciles(self):
        stage = self.stage()
        proposal = self.propose(stage)
        new_world = self.frame((1, 0, 0), session="other-world")
        value = self.settle(stage, self.result(proposal, new_world, "unknown"))
        self.assertEqual(value.stage_result.disposition, "unknown")
        self.assertEqual(value.progress.verified_steps, 0)
        with self.assertRaises(ContractError):
            self.settle(stage, self.result(proposal, None, "rejected"))
        self.assertEqual(self.propose(stage), value)

    def test_unexpected_stale_turn_and_revision_results_never_credit(self):
        for options in ({"position": (0, 1, 0), "turn": 11}, {"position": (1, 0, 0), "turn": 9},
                        {"position": (0, 0, 0), "turn": 10, "revision": 1},
                        {"position": (1, 0, 0), "turn": 11, "now": 100}):
            self.reset()
            stage = self.stage(task=self.task(distance=1))
            proposal = self.propose(stage)
            after = self.frame(**options, change=None if options.get("revision") == 1 else
                               lambda v: self.obstruct_neighbor(v, 1, 0, "invisible"))
            clocks = dict(now_monotonic=104, now_timestamp_ms=1_004_000) if options.get("now") else {}
            value = self.settle(stage, self.result(proposal, after), **clocks)
            self.assertIsNotNone(value.stage_result)
            self.assertEqual(value.progress.verified_steps, 0)

    def test_partial_and_full_displacement_can_stop_on_post_guard(self):
        for distance in (1, 2):
            for stop in ("terrain", "creature", "action", "paused", "frozen"):
                self.reset()
                stage = self.stage(task=self.task(distance=distance))
                proposal = self.propose(stage)
                def mutation(v):
                    if stop == "terrain":
                        next(t for t in v["scene"]["neighbors"] if (t["dx"], t["dy"]) == (1, 0))["terrain"] = "t_wall"
                    elif stop == "creature":
                        v["scene"]["visible_creatures"] = [{"name": "zombie", "hostile": True}]
                    elif stop == "action":
                        v["actions"] = ["LEFT"]
                after = self.frame((1, 0, 0), turn=11, change=mutation)
                flags = {stop: True} if stop in ("paused", "frozen") else {}
                value = self.settle(stage, self.result(proposal, after), **flags)
                self.assertEqual(value.progress.verified_steps, 1)
                self.assertEqual(value.stage_result.disposition,
                                 "completed" if distance == 1 and stop == "terrain"
                                 else "interrupted" if flags else "blocked")

    def test_budget_edges_preserve_original_clocks_turn_and_counts(self):
        for budgets, prior in ((Budgets(primitives=0), 0), (Budgets(primitives=2), 2),
                               (Budgets(primitives_per_stage=0), 0), (Budgets(turns=0), 0),
                               (Budgets(wall_seconds=0), 0), (Budgets(primitive_wait_seconds=0), 0)):
            self.reset()
            start = self.frame()
            history = tuple(RouteAttempt("outbound", PrimitiveResult(f"rejected-{n}", start, None,
                            "not_dispatched", None, "Known non-delivery")) for n in range(prior))
            stage = self.stage(task=self.task(budgets=budgets), start=start, history=history)
            self.assertEqual(self.propose(stage).stage_result.disposition, "budget_exhausted")
        self.reset()
        start = self.frame()
        current = self.frame(turn=12, now=102, timestamp=1_002_000)
        stage = self.stage(task=self.task(budgets=Budgets(turns=2)), start=start, checkpoint=current)
        self.assertEqual(self.propose(stage, now_monotonic=102, now_timestamp_ms=1_002_000)
                         .stage_result.disposition, "budget_exhausted")
        self.reset()
        start = self.frame()
        current = self.frame(now=102, timestamp=1_002_000)
        stage = self.stage(task=self.task(budgets=Budgets(wall_seconds=2)), start=start, checkpoint=current)
        self.assertEqual(self.propose(stage, now_monotonic=102, now_timestamp_ms=1_002_000)
                         .stage_result.disposition, "budget_exhausted")

    def test_wait_ceiling_and_post_commit_overshoot_keep_progress(self):
        for final in (False, True):
            self.reset()
            task = self.task(distance=1 if final else 2,
                             budgets=Budgets(wall_seconds=2, turns=1, primitive_wait_seconds=10))
            stage = self.stage(task=task)
            proposal = self.propose(stage, now_monotonic=101, now_timestamp_ms=1_001_000)
            self.assertEqual(proposal.wait_seconds, 1)
            self.number += 1
            preflight_value = self.store.observation(proposal.before)
            preflight_value.update(frame=f"frame-world-{self.number}.png", timestamp_ms=1_001_000)
            (self.bridge / preflight_value["frame"]).write_bytes(Path(proposal.before.frame_path).read_bytes())
            preflight = self.store.retain_preflight(preflight_value, rule="native_state",
                received_monotonic=101, now_monotonic=101, now_timestamp_ms=1_001_000)
            token = self.store.reserve_dispatch(proposal.before, preflight=preflight, rule="native_state",
                now_monotonic=101, now_timestamp_ms=1_001_000)
            after = self.frame((1, 0, 0), turn=12, now=103, timestamp=1_003_000, reservation=token,
                               change=lambda v: self.obstruct_neighbor(v, 1, 0, "cupboard") if final else None)
            value = self.settle(stage, self.result(proposal, after), now_monotonic=103, now_timestamp_ms=1_003_000)
            self.assertEqual(value.progress.verified_steps, 1)
            self.assertEqual(value.stage_result.disposition, "budget_exhausted")

    def test_exact_budget_limit_can_complete_but_cannot_authorize_another_step(self):
        for distance in (1, 2):
            self.reset()
            task = self.task(distance=distance, budgets=Budgets(primitives=1, primitives_per_stage=1,
                                                               turns=1, wall_seconds=1))
            stage = self.stage(task=task)
            proposal = self.propose(stage)
            after = self.frame((1, 0, 0), turn=11, now=101, timestamp=1_001_000,
                               change=lambda v: self.obstruct_neighbor(v, 1, 0, "cupboard") if distance == 1 else None)
            result = self.result(proposal, after)
            value = self.settle(stage, result, now_monotonic=101, now_timestamp_ms=1_001_000)
            self.assertEqual(value.progress.verified_steps, 1)
            self.assertEqual(value.stage_result.disposition, "completed" if distance == 1 else "budget_exhausted")
            self.assertEqual(self.propose(stage, "new", now_monotonic=101, now_timestamp_ms=1_001_000), value)

    def test_retained_complete_target_rejects_each_original_budget_overshoot(self):
        for exhausted in ("primitives", "primitives_per_stage", "turns", "wall_seconds"):
            for overshot in (False, True):
                with self.subTest(exhausted=exhausted, overshot=overshot):
                    self.reset()
                    task = self.task(distance=1, budgets=Budgets(**{exhausted: 0 if overshot else 1}))
                    start = self.frame()
                    after = self.frame((1, 0, 0), turn=11, now=101, timestamp=1_001_000,
                                       change=lambda v: self.obstruct_neighbor(v, 1, 0, "invisible"))
                    result = PrimitiveResult("retained-step", start, after, "returned", (1, 0, 0), "Verified")
                    stage = self.stage(task, start, checkpoint=after, history=(RouteAttempt("outbound", result),))
                    value = self.propose(stage, "verification-only", now_monotonic=101,
                                         now_timestamp_ms=1_001_000)
                    self.assertEqual(value.stage_result.disposition, "budget_exhausted" if overshot else "completed")
                    self.assertEqual(value.progress.verified_steps, 1)
                    self.assertIsNone(value.primitive_result)
                    self.assertIsNone(value.stage_result.pending_action_id)

    def test_duplicate_old_result_during_new_proposal_cannot_release_the_new_one(self):
        stage = self.stage()
        proposal = self.propose(stage)
        after = self.frame((1, 0, 0), turn=11)
        old = self.result(proposal, after)
        value = self.settle(stage, old)
        new = self.propose(stage, "logical-2")
        self.assertEqual(self.settle(stage, old), value)
        self.assertEqual(stage.progress.verified_steps, 1)
        with self.assertRaises(ContractError):
            self.propose(stage, "logical-3")
        after = self.frame((2, 0, 0), turn=12)
        self.assertEqual(self.settle(stage, self.result(new, after)).stage_result.disposition, "completed")

    def test_invalid_and_regressing_clocks_terminate_without_releasing_pending(self):
        for clocks in ({"now_monotonic": float("nan")}, {"now_monotonic": float("inf")},
                       {"now_monotonic": True}, {"now_monotonic": 99}, {"now_monotonic": 10**1000},
                       {"now_timestamp_ms": True}, {"now_timestamp_ms": -1},
                       {"now_timestamp_ms": 1_000_000.0}):
            self.reset()
            stage = self.stage()
            proposal = self.propose(stage)
            value = self.settle(stage, self.result(proposal, None, "unknown"), **clocks)
            self.assertIsNotNone(value.stage_result)
            self.assertEqual(value.stage_result.pending_action_id, proposal.action_id)
            self.assertEqual(self.propose(stage), value)
        self.reset()
        stage = self.stage()
        proposal = self.propose(stage, now_monotonic=101, now_timestamp_ms=1_001_000)
        value = self.settle(stage, self.result(proposal, None, "unknown"), now_monotonic=100.5)
        self.assertIn("clock", value.reason.lower())
        self.assertEqual(value.progress.verified_steps, 0)
        self.reset()
        stage = self.stage()
        proposal = self.propose(stage, now_monotonic=101, now_timestamp_ms=1_001_000)
        value = self.settle(stage, self.result(proposal, None, "unknown"),
                            now_monotonic=102, now_timestamp_ms=1_000_999)
        self.assertIn("clock", value.reason.lower())

    def test_original_task_primitive_budget_includes_return_history(self):
        task = self.task(distance=2, budgets=Budgets(primitives=3))
        start = self.frame()
        outbound = self.stage(task, start)
        history = ()
        for n in range(1, 3):
            proposal = self.propose(outbound, f"out-{n}")
            waypoint = self.frame((n, 0, 0), turn=10+n)
            result = self.result(proposal, waypoint)
            self.settle(outbound, result)
            history += (RouteAttempt("outbound", result),)
        stage = self.stage(task, start, stage="return", checkpoint=waypoint, history=history)
        proposal = self.propose(stage)
        after = self.frame((1, 0, 0), turn=13)
        value = self.settle(stage, self.result(proposal, after))
        self.assertEqual(value.progress.verified_steps, 1)
        self.assertEqual(value.stage_result.disposition, "budget_exhausted")

    def test_capacity_preflight_stops_without_reserving_or_consuming_a_primitive(self):
        self.reset(max_frames=1)
        value = self.propose(self.stage())
        self.assertIsNotNone(value.stage_result)
        self.assertEqual(value.progress.verified_steps, 0)
        self.assertEqual(len(self.store.historical_references), 1)

    def test_partial_continuation_derives_both_legs_and_never_replays_prefix(self):
        task = self.task(distance=2)
        start = self.frame()
        history = ()
        for leg, positions in (("outbound", ((1, 0, 0), (2, 0, 0))),
                               ("return", ((1, 0, 0), (0, 0, 0)))):
            for n, position in enumerate(positions):
                checkpoint = self.store.current(now_monotonic=100, now_timestamp_ms=1_000_000)
                stage = self.stage(task, start, stage=leg, checkpoint=checkpoint, history=history)
                self.assertEqual(stage.progress.verified_steps, n)
                proposal = self.propose(stage, f"{leg}-{n}")
                self.assertEqual(proposal.expected_position, position)
                after = self.frame(position, turn=11+len(history))
                result = self.result(proposal, after)
                self.settle(stage, result)
                history += (RouteAttempt(leg, result),)
        summary = summarize_route(task, self.store, start, history)
        self.assertEqual((summary.primitive_count, summary.outbound_steps, summary.return_steps), (4, 2, 2))
        self.assertEqual(summary.position, task.origin)
        self.assertEqual(self.store.position(summary.waypoint), task.target)

    def test_history_charges_failed_attempts_and_original_leg_limit(self):
        task = self.task(budgets=Budgets(primitives_per_stage=2))
        start = self.frame()
        history = (RouteAttempt("outbound", PrimitiveResult("no-delivery", start, None,
                         "not_dispatched", None, "Explicit rejection")),)
        stage = self.stage(task, start, history=history)
        proposal = self.propose(stage, "moved")
        after = self.frame((1, 0, 0), turn=11)
        result = self.result(proposal, after)
        value = self.settle(stage, result)
        self.assertEqual(value.stage_result.disposition, "budget_exhausted")
        history += (RouteAttempt("outbound", result),)
        continued = self.stage(task, start, checkpoint=after, history=history)
        self.assertEqual(self.propose(continued, "new").stage_result.disposition, "budget_exhausted")
        self.assertEqual(continued.progress.verified_steps, 1)

    def test_complete_leg_verification_with_no_primitives_does_not_rearm_old_stage(self):
        task = self.task(distance=1, budgets=Budgets(primitives=1, primitives_per_stage=1))
        start = self.frame()
        stage = self.stage(task, start)
        proposal = self.propose(stage)
        after = self.frame((1, 0, 0), turn=11)
        result = self.result(proposal, after)
        stopped = self.settle(stage, result, paused=True)
        self.assertEqual(stopped.stage_result.disposition, "interrupted")
        fresh = self.frame((1, 0, 0), turn=11)
        self.assertEqual(self.propose(stage, "ignored"), stopped)
        continued = self.stage(task, start, checkpoint=fresh, history=(RouteAttempt("outbound", result),))
        verified = self.propose(continued, "verification-only")
        self.assertEqual(verified.stage_result.disposition, "completed")
        self.assertIsNone(verified.primitive_result)
        self.assertIsNone(verified.stage_result.pending_action_id)

    def test_history_rejects_unknown_wrong_duplicate_or_disputed_route(self):
        start = self.frame()
        after = self.frame((1, 0, 0), turn=11)
        good = PrimitiveResult("one", start, after, "returned", (1, 0, 0), "Verified")
        invalid = ((RouteAttempt("outbound", replace(good, transport_disposition="unknown")),),
                   (RouteAttempt("outbound", replace(good, observed_displacement=(0, 0, 0))),),
                   (RouteAttempt("return", good),),
                   (RouteAttempt("outbound", good), RouteAttempt("outbound", good)),
                   (RouteAttempt("outbound", replace(good, transport_disposition="not_dispatched")),))
        for history in invalid:
            with self.subTest(history=history), self.assertRaises(ContractError):
                self.stage(start=start, checkpoint=after, history=history)
        history = (RouteAttempt("outbound", good),)
        with self.assertRaises(ContractError):
            self.propose(self.stage(start=start, checkpoint=after, history=history), "one")
        Path(start.frame_path).chmod(0o600)
        Path(start.frame_path).write_bytes(b"disputed")
        with self.assertRaises(EvidenceError):
            self.stage(start=start, checkpoint=after, history=history)


if __name__ == "__main__":
    unittest.main()
