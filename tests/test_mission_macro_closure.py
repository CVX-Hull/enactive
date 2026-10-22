"""Finite local macro closure through the existing writer; synthetic game UI."""
import copy
from concurrent.futures import ThreadPoolExecutor
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
