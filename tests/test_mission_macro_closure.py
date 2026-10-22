"""Finite local macro closure through the existing writer; synthetic game UI."""
import copy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from tests import test_mission_prompt_observation as prompts


class MacroClosureTests(unittest.TestCase):
    setUp = prompts.PromptObservationTests.setUp
    wait = prompts.PromptObservationTests.wait
    request = prompts.PromptObservationTests.request
    result = prompts.PromptObservationTests.result
    settled = prompts.PromptObservationTests.settled
    start = prompts.PromptObservationTests.start
    control = prompts.PromptObservationTests.control
    open_direction = prompts.PromptObservationTests.open_direction
    allow_direct = prompts.PromptObservationTests.allow_direct
    direct = prompts.PromptObservationTests.direct
    observe = prompts.PromptObservationTests.observe

    def exhaust(self, limit):
        self.allow_direct()
        root, _ = self.open_direction(limits=dict(primitives=1 if limit == "primitives" else 8,
            wall_seconds=1 if limit == "wall_seconds" else 120,
            game_seconds=1 if limit == "game_seconds" else 1200))
        phase = self.runtime._prompt_phase
        if limit == "wall_seconds":
            threading.Event().wait(1.05)  # Actual local deadline, no clock rollback.
        elif limit == "game_seconds":
            scene = copy.deepcopy(self.runtime._store.observation(phase.game_anchor)["scene"])
            scene["turn"] += 2

            def return_with_time(bridge, request):
                if request["kind"] == "observe":
                    bridge.value["revision"] += 1
                    bridge.value.update(scene=scene, ui=None, category="DEFAULTMODE")
                    bridge.value["boundary"].update(kind="normal_play", id="observed-return")

            self.bridge.before_gate = return_with_time
        return root, phase

    def test_input_exhaustion_closes_macro_and_allows_explicit_new_root(self):
        self.closure_and_new_root("primitives")

    def test_wall_exhaustion_closes_macro_and_allows_explicit_new_root(self):
        self.closure_and_new_root("wall_seconds")

    def closure_and_new_root(self, limit):
        root, old = self.exhaust(limit)
        old_child = self.direct(root, request_id="old-child")
        root_before = self.runtime._ledger.request(root["request_id"])
        lease = self.runtime._lease
        spent = self.runtime.status()["spent_inputs"]
        observed = self.observe()
        self.assertEqual(observed["state"], "completed", observed)
        closure = observed["result"]["macro_closure"]
        current = self.runtime._current
        self.assertEqual(closure, dict(root_request_id=root["request_id"],
            checkpoint_source_id=old.checkpoint.observation_id, fresh_source_id=current.observation_id,
            detected_at=closure["detected_at"], limit=limit, grants_authority=False))
        self.assertNotIn("phase", observed["result"])
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertEqual(self.runtime._ledger.request(root["request_id"]), root_before)
        self.assertEqual(self.runtime.command(old_child)["status"], "rejected")
        self.assertIs(self.runtime._lease, lease)
        new_root = self.direct(root, request_id="new-chosen-root", key="x") | dict(phase_id=None)
        self.assertEqual(self.runtime.command(new_root)["status"], "accepted")
        result = self.settled(new_root["request_id"])
        self.assertEqual(result["state"], "partial", result)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent + 1)
        self.assertEqual(self.runtime._prompt_phase.root_id, new_root["request_id"])
        self.assertEqual(self.runtime._ledger.request(root["request_id"]), root_before)

    def test_local_game_limit_is_closure_not_goal_completion_or_mission_exhaustion(self):
        root, _ = self.exhaust("game_seconds")
        original = self.runtime._ledger.request(root["request_id"])
        observed = self.observe()
        self.assertEqual(observed["state"], "completed", observed)
        self.assertEqual(observed["result"]["macro_closure"]["limit"], "game_seconds")
        self.assertNotIn("phase", observed["result"])
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["phase"], "active")
        self.assertEqual(self.runtime.status()["metrics"]["game_seconds"], 2)
        self.assertEqual(self.runtime._ledger.request(root["request_id"]), original)

    def test_exhausted_semantic_root_keeps_ordinary_observation_path(self):
        root, phase = self.exhaust("primitives")
        lease = self.runtime._lease
        child = self.direct(root, request_id="exhausted-semantic-child")
        self.assertEqual(self.runtime.command(child)["status"], "accepted")
        refused = self.settled(child["request_id"])
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertEqual(refused["result"]["macro_exhausted"], "primitives")
        self.assertIs(self.runtime._lease, lease)
        self.assertIs(self.runtime._prompt_phase, phase)
        self.assertEqual(self.observe()["result"]["macro_closure"]["limit"], "primitives")
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

    def test_local_wall_expiry_before_execution_keeps_observe(self):
        self.expired_child("execution")

    def test_standalone_deadline_refusal_preserves_age_but_not_capture_or_custody_faults(self):
        for fault in ("healthy", "aged", "frame", "malformed_frame", "timestamp", "receiver", "control"):
            with self.subTest(fault=fault):
                case = type(self)()
                case.setUp()
                try:
                    case.allow_direct()
                    case.start()
                    root = case.direct({"request_id": None}, request_id="expired-root-" + fault) | dict(
                        phase_id=None, limits=dict(primitives=1, wall_seconds=1, game_seconds=1200))
                    actual = case.runtime._deadline
                    delivered = copy.deepcopy(case.bridge.delivered)

                    def expire(work, before):
                        deadline = case.runtime._ledger.request(root["request_id"])["deadline"]
                        threading.Event().wait(max(0, deadline - case.runtime._wall() + .03))
                        if fault == "aged":
                            # Let both original clocks age; never rewrite one
                            # immutable capture to simulate elapsed time.
                            threading.Event().wait(2.1)
                        elif fault == "frame": case.controller.state.update(frame_ok=False, frame_geometry=None)
                        elif fault == "malformed_frame": case.controller.state["frame_ok"] = False
                        elif fault == "timestamp": case.controller.state["timestamp_ms"] -= 4000
                        elif fault == "receiver": case.controller.state["boundary"]["input_receiver"] = False
                        elif fault == "control": case.controller.state["boundary"]["control_generation"] += 1
                        return actual(work, before)

                    with patch.object(case.runtime, "_deadline", side_effect=expire):
                        self.assertEqual(case.runtime.command(root)["status"], "accepted")
                        result = case.settled(root["request_id"])
                    self.assertEqual(result["state"], "blocked", result)
                    self.assertEqual(case.runtime.status()["spent_inputs"], 0)
                    self.assertEqual(case.bridge.delivered, delivered)
                    if fault in ("healthy", "aged"):
                        self.assertIsNotNone(case.runtime._lease)
                        self.assertEqual(case.runtime.status()["phase"], "active")
                        self.assertEqual(case.observe()["state"], "completed")
                    else:
                        self.assertIsNone(case.runtime._lease)
                        self.assertEqual(case.runtime.status()["phase"], "paused")
                finally:
                    case.doCleanups()

    def test_local_wall_expiry_after_entry_check_keeps_observe(self):
        self.expired_child("entry")

    def test_local_wall_expiry_before_preparation_keeps_observe(self):
        self.expired_child("preparation")

    def test_local_wall_expiry_after_preparation_keeps_original_charge(self):
        self.expired_child("prepared")

    def test_late_local_expiry_cannot_hide_global_reserve(self):
        self.a = replace(self.a, limits=replace(self.a.limits, inputs=3, primitive_mappings=3),
                         cleanup_reserve=replace(self.a.cleanup_reserve, inputs=1))
        self.expired_child("prepared", fatal=True)

    def expired_child(self, stage, *, fatal=False):
        self.allow_direct()
        root, _ = self.open_direction(limits=dict(primitives=8, wall_seconds=1, game_seconds=1200))
        deadline = self.runtime._ledger.request(root["request_id"])["deadline"]
        original = self.runtime._ledger.request(root["request_id"])
        delivered = copy.deepcopy(self.bridge.delivered)
        child = self.direct(root, request_id="expires-" + stage)

        def expire():
            threading.Event().wait(max(0, deadline - self.runtime._wall() + .03))

        if stage == "execution":
            target, name = self.runtime, "_execute_work"
        elif stage == "entry":
            target, name = self.runtime, "_exhausted_prompt_refusal"
        elif stage == "preparation":
            target, name = self.runtime._store, "reserve_dispatch"
        else:
            target, name = self.runtime._ledger, "prepare_primitive"
        actual = getattr(target, name)
        called = False

        def delayed(*args, **kwargs):
            nonlocal called
            first = not called
            called = True
            if first and stage in ("execution", "preparation"):
                expire()
            value = actual(*args, **kwargs)
            if first and stage in ("entry", "prepared"):
                expire()
            return value

        with patch.object(target, name, side_effect=delayed):
            self.assertEqual(self.runtime.command(child)["status"], "accepted")
            refused = self.settled(child["request_id"])
        self.assertTrue(called)
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertEqual(self.bridge.delivered, delivered)
        rows = self.runtime._ledger.primitive_records()
        self.assertEqual([r["state"] for r in rows],
                         ["returned", "not_dispatched"] if stage == "prepared" else ["returned"])
        self.assertEqual(self.runtime.status()["spent_inputs"], len(rows))
        self.assertEqual(self.runtime._ledger.request(root["request_id"]), original)
        if fatal:
            self.assertIsNone(self.runtime._lease)
            self.assertIsNone(self.runtime._prompt_phase)
            self.assertEqual(self.runtime.status()["phase"], "paused")
            self.assertNotIn("macro_closure", refused["result"])
            return
        self.assertEqual(self.runtime.status()["phase"], "active", refused)
        self.assertIsNotNone(self.runtime._lease)
        observed = self.observe()
        self.assertEqual(observed["result"]["macro_closure"]["limit"], "wall_seconds")
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.result(child["request_id"]), refused)

    def test_exhausted_root_cannot_mask_global_input_reserve(self):
        self.a = replace(self.a, limits=replace(self.a.limits, inputs=2, primitive_mappings=2),
                         cleanup_reserve=replace(self.a.cleanup_reserve, inputs=1))
        root, _ = self.exhaust("primitives")
        child = self.direct(root, request_id="no-global-capacity")
        self.assertEqual(self.runtime.command(child)["status"], "accepted")
        refused = self.settled(child["request_id"])
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertNotIn("macro_exhausted", refused["result"])
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

    def test_exhausted_root_cannot_mask_corrupt_checkpoint(self):
        root, phase = self.exhaust("primitives")
        child = self.direct(root, request_id="corrupt-local-checkpoint")
        checkpoint = Path(phase.checkpoint.frame_path)
        checkpoint.chmod(0o600)
        checkpoint.write_bytes(b"corrupt retained frame")
        self.assertEqual(self.runtime.command(child)["status"], "accepted")
        refused = self.settled(child["request_id"])
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertNotIn("macro_exhausted", refused["result"])
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

    def test_exhausted_entry_cannot_mask_pause_pending_recovery_or_anchor_corruption(self):
        for fault in ("pause", "claimed", "recovery", "anchor"):
            with self.subTest(fault=fault):
                case = type(self)()
                case.setUp()
                try:
                    root, phase = case.exhaust("primitives")
                    child = case.direct(root, request_id="exhausted-with-" + fault)
                    delivered = copy.deepcopy(case.bridge.delivered)
                    if fault == "pause":
                        (case.controller.bridge / "pause").touch()
                    elif fault == "claimed":
                        (case.controller.bridge / "claimed.json").write_text("{}")
                    elif fault == "recovery":
                        case.controller.control_lock.acquire()
                    else:
                        anchor = Path(phase.game_anchor.frame_path)
                        anchor.chmod(0o600)
                        anchor.write_bytes(b"corrupt retained anchor")
                    try:
                        self.assertEqual(case.runtime.command(child)["status"], "accepted")
                        refused = case.settled(child["request_id"])
                        self.assertEqual(refused["state"], "blocked", refused)
                        self.assertNotIn("macro_exhausted", refused["result"])
                        self.assertIsNone(case.runtime._lease)
                        self.assertIsNone(case.runtime._prompt_phase)
                        self.assertEqual(case.runtime.status()["spent_inputs"], 1)
                        self.assertEqual(case.bridge.delivered, delivered)
                    finally:
                        if fault == "recovery":
                            case.controller.control_lock.release()
                finally:
                    case.doCleanups()

    def test_text_child_stops_at_original_root_remaining_input_without_revoking(self):
        self.allow_direct()
        self.bridge.editor_text = ""

        def type_scalar(bridge, request):
            if request["kind"] == "direct":
                bridge.editor_text += request["input"]["text"]
            return True

        root, _ = self.open_direction(effect=type_scalar,
            limits=dict(primitives=2, wall_seconds=120, game_seconds=1200))
        child = self.control("direct", dict(input=dict(type="text", text="abc"),
            intent="Type chosen text", expected="Inspect actual text", interrupt_allowed=False),
            phase_id=root["request_id"], request_id="text-with-one-input-left")
        self.assertEqual(self.runtime.command(child)["status"], "accepted")
        result = self.settled(child["request_id"])
        self.assertEqual(result["state"], "partial", result)
        self.assertEqual(result["result"]["macro_exhausted"], "primitives")
        self.assertEqual(self.bridge.editor_text, "a")
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertEqual(self.runtime.status()["phase"], "active")
        self.assertIsNotNone(self.runtime._lease)
        self.assertEqual([r["state"] for r in self.runtime._ledger.primitive_records()],
                         ["returned", "returned"])
        self.assertEqual(self.observe()["result"]["macro_closure"]["limit"], "primitives")
        self.assertEqual(self.result(child["request_id"]), result)
        self.assertEqual(self.bridge.editor_text, "a")

    def test_exhausted_direct_child_refuses_without_losing_observe_and_new_root(self):
        self.allow_direct()
        self.start()
        normal = copy.deepcopy(self.bridge.value["scene"])

        def visible_effect(bridge, request):
            if request["kind"] == "direct":
                if request["input"]["key"] == "V":
                    bridge.value.update(scene=None, ui=None, category="UNFAMILIAR_SCREEN_731")
                    bridge.value["boundary"].update(kind="menu", id="unfamiliar-screen")
                elif request["input"]["key"] == "ESC":
                    bridge.value.update(scene=normal, ui=None, category="DEFAULTMODE")
                    bridge.value["boundary"].update(kind="normal_play", id="returned-normal")
            return True

        self.bridge.behavior = visible_effect
        root = self.direct({"request_id": None}, request_id="one-key-inspection", key="V") | dict(
            phase_id=None, limits=dict(primitives=1, wall_seconds=120, game_seconds=1200))
        self.assertEqual(self.runtime.command(root)["status"], "accepted")
        opened = self.settled(root["request_id"])
        self.assertEqual(opened["state"], "partial", opened)
        original = self.runtime._ledger.request(root["request_id"])
        phase, lease = self.runtime._prompt_phase, self.runtime._lease
        delivered = copy.deepcopy(self.bridge.delivered)
        child = self.direct(root, request_id="exhausted-escape")
        self.assertEqual(self.runtime.command(child)["status"], "accepted")
        refused = self.settled(child["request_id"])
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertEqual(refused["result"]["macro_exhausted"], "primitives")
        self.assertIs(self.runtime._lease, lease)
        self.assertIs(self.runtime._prompt_phase, phase)
        self.assertEqual(self.runtime.status()["phase"], "active")
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertFalse(any(r["request_id"] == child["request_id"]
                             for r in self.runtime._ledger.primitive_records()))
        self.assertEqual(self.runtime._ledger.request(root["request_id"]), original)
        self.assertEqual(self.observe()["result"]["macro_closure"]["limit"], "primitives")
        new_root = self.direct(root, request_id="new-escape") | dict(phase_id=None)
        self.assertEqual(self.runtime.command(new_root)["status"], "accepted")
        escaped = self.settled(new_root["request_id"])
        self.assertEqual(escaped["state"], "partial", escaped)
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime._current.boundary_kind, "normal_play")
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertEqual(self.runtime._ledger.request(root["request_id"]), original)
        self.assertEqual(self.result(child["request_id"]), refused)

    def test_child_queued_before_closure_is_refused_without_revoking_healthy_custody(self):
        root, _ = self.exhaust("primitives")
        child = self.direct(root, request_id="queued-old-child")
        observe = self.runtime._observe_native
        entered, release = threading.Event(), threading.Event()
        lease = self.runtime._lease

        def blocked_capture(work, **kwargs):
            entered.set()
            self.assertTrue(release.wait(2))
            return observe(work, **kwargs)

        with patch.object(self.runtime, "_observe_native", side_effect=blocked_capture), ThreadPoolExecutor(2) as pool:
            first = pool.submit(self.observe)
            self.assertTrue(entered.wait(2))
            second = pool.submit(self.runtime.command, child)
            self.wait(lambda: self.runtime._queue.qsize() == 1)
            release.set()
            closed, refused = first.result(2), second.result(2)
        self.assertIn("macro_closure", closed["result"])
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertIn("No live prompt", refused["reason"])
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(self.runtime.status()["phase"], "active")
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertFalse(any(row["request"]["request_id"] == child["request_id"]
                             for row in self.runtime._ledger.request_records()))

    def test_storage_failure_precedes_scope_release_and_stops_without_a_fake_closure(self):
        _, phase = self.exhaust("primitives")
        complete = self.runtime._ledger.complete_request
        failures = []

        def fail_closure(identity, disposition, result, **kwargs):
            if "macro_closure" in result:
                self.assertIs(self.runtime._prompt_phase, phase)
                failures.append(identity)
                raise OSError("closure commit failed")
            return complete(identity, disposition, result, **kwargs)

        with patch.object(self.runtime._ledger, "complete_request", side_effect=fail_closure):
            observed = self.observe()
        self.assertEqual(failures, [observed["request"]["request_id"]])
        self.assertEqual(observed["state"], "blocked", observed)
        self.assertNotIn("macro_closure", observed["result"])
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

    def test_pause_after_commit_keeps_closure_historical_and_revokes_input(self):
        self.exhaust("primitives")
        complete = self.runtime._ledger.complete_request

        def pause_after_commit(identity, disposition, result, **kwargs):
            value = complete(identity, disposition, result, **kwargs)
            if "macro_closure" in result:
                self.runtime.pause("User Pause after macro closure")
            return value

        with patch.object(self.runtime._ledger, "complete_request", side_effect=pause_after_commit):
            observed = self.observe()
        self.assertEqual(observed["state"], "completed", observed)
        self.assertIn("macro_closure", observed["result"])
        self.assertEqual(self.runtime.status()["pause_cause"], "user")
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._prompt_phase)


if __name__ == "__main__":
    unittest.main()
