"""Synthetic file transport plus real runtime/components; no native efficacy claim."""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from harness.controller import Controller
from harness.gameplay.contracts import PlanCandidate
from harness.gameplay.evidence import CapacityError
from harness.runtime import GameplayRuntime
from test_controller import FakeBridge


class VisibleBridge(FakeBridge):
    def __init__(self, controller, **options):
        super().__init__(controller, **options)
        self.frames = 0
        self.pixels = b"same visible scene"
        self.value["scene"]["provenance"] = "player-visible input boundary"
        self.value["scene"]["neighbors"] = [
            {"dx": dx, "dy": dy, "visible": True, "terrain": "t_floor", "name": "floor", "furniture": "f_null"}
            for dy in range(-1, 2) for dx in range(-1, 2) if (dx, dy) != (0, 0)]

    def publish(self, value):
        self.frames += 1
        value = copy.deepcopy(value)
        value["frame"] = f'frame-{value["session"]}-{self.frames}.png'
        data = b"\x89PNG\r\n\x1a\n" + self.pixels + str(value["scene"]["position"]).encode()
        (self.bridge / value["frame"]).write_bytes(data)
        super().publish(value)


def candidate(request):
    value = request["input"]
    binding = value["binding"]
    direction = value["task"]["direction"]
    if binding["expected_stage"] == "return":
        direction = {"east": "west", "west": "east", "north": "south", "south": "north"}[direction]
    return PlanCandidate("candidate", binding["task_id"], binding["task_version"], binding["plan_id"],
        binding["plan_version"], binding["execution_epoch"], binding["evidence_session"],
        binding["evidence_revision"], binding["expected_stage"], direction, binding["distance_remaining"],
        "cardinal_movement", 3, "Follow the bounded clear cardinal route").to_dict()


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        # Functional file/thread exchanges share CI scheduling and storage.
        # Use the controller tests' budget; explicit deadline tests stay separate.
        self.controller = Controller(Path(temporary.name), timeout=2.0)
        self.addCleanup(self.controller.close)
        self.bridge = VisibleBridge(self.controller)
        self.bridge.__enter__()
        self.addCleanup(self.bridge.__exit__, None, None, None)
        self.runtime = GameplayRuntime(self.controller)
        self.addCleanup(self.runtime.close)
        self.assertIsNone(self.runtime.status())
        self.assertIsNone(self.controller.status()["run_lease"])
        self.assertEqual(self.controller.execute("observe")["status"], "ready")
        self.assertEqual(self.controller.execute("resume")["status"], "ready")

    def wait(self, condition, timeout=3):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            result = condition()
            if result:
                return result
            threading.Event().wait(0.005)
        recent = [{key: request[key] for key in ("id", "kind", "deadline_ms")}
                  for request in self.bridge.requests[-6:]]
        self.fail(f"Runtime condition timed out: {self.runtime.status()}; "
                  f"recent native requests: {recent}; observed_ms: {int(time.time() * 1000)}")

    def expect(self):
        state, _ = self.controller.observation_snapshot()
        return {"expected_session": state["session"], "expected_revision": state["revision"]}

    def start(self, distance=1):
        result = self.runtime.command("start", direction="east", distance=distance, **self.expect())
        self.assertEqual(result["status"], "accepted", result)
        return self.request()

    def request(self):
        return self.wait(lambda: self.runtime.command("planning_request")["planning_request"])

    def answer(self, request):
        result = self.runtime.command("plan", request_id=request["request_id"], candidate=candidate(request))
        self.assertEqual(result["status"], "accepted", result)

    def state(self, name):
        return self.wait(lambda: (snapshot if (snapshot := self.runtime.status())["run"]["state"] == name else None))

    def test_full_two_leg_completion_exact_receipts_and_unmeasured_usage(self):
        outbound = self.start(distance=2)
        self.assertNotIn("lease", json.dumps(outbound))
        self.assertEqual(outbound["input"]["binding"]["distance_remaining"], 2)
        self.answer(outbound)
        back = self.request()
        self.assertEqual(back["input"]["binding"]["expected_stage"], "return")
        self.answer(back)
        final = self.state("completed")
        self.assertEqual(final["run"]["progress"]["verified_steps"], 4)
        self.assertEqual(final["run"]["remaining_budgets"]["primitives"], 4)
        self.assertEqual(final["run"]["model_id"], "external-unreported")
        self.assertEqual(final["run"]["configuration_id"], "external-chat-v1")
        self.wait(lambda: self.controller.status()["pause_requested"])
        self.assertIsNone(self.runtime.status()["run"]["lease_owner"])
        action_requests = [r for r in self.bridge.requests if r["kind"] == "action"]
        self.assertEqual(len(action_requests), 4)
        self.assertEqual(final["last_receipt"]["native_request_id"], action_requests[-1]["id"])
        events = [json.loads(line) for line in self.controller.journal.read_text().splitlines()]
        receipts = [event["outcome"] for event in events if event["request"]["kind"] == "gameplay_receipt"]
        self.assertEqual([r["request"]["id"] for r in receipts], [r["id"] for r in action_requests])
        usage = self.runtime._supervisor.accounting_snapshot().evaluation_events()
        for event in usage:
            for metric in ("input_tokens", "output_tokens", "cached_input_tokens", "cost_usd"):
                self.assertIsNone(event["payload"][metric])
                self.assertTrue(event["payload"][metric + "_missing_reason"])

    def test_obsolete_cardinal_candidate_is_rejected_without_consuming_current_request(self):
        request = self.start()
        old = candidate(request) | {"skill_version": 2}
        result = self.runtime.command("plan", request_id=request["request_id"], candidate=old)
        self.assertEqual(result["status"], "rejected")
        self.assertFalse(any(r["kind"] == "action" for r in self.bridge.requests))
        self.assertEqual(self.request()["request_id"], request["request_id"])
        self.answer(request)
        self.answer(self.request())
        self.assertEqual(self.state("completed")["run"]["progress"]["verified_steps"], 2)

    def test_slow_plan_status_reads_preserve_generation_then_fresh_equivalent_refresh(self):
        request = self.start()
        generation = self.runtime._store.authority_generation()
        before = self.runtime._supervisor.task_start
        end = time.monotonic() + 3.1
        while time.monotonic() < end:
            self.assertEqual(self.runtime.status()["run"]["state"], "planning")
            threading.Event().wait(0.02)
        self.assertFalse(self.runtime.status()["run"]["fresh"])
        self.assertEqual(self.runtime._store.authority_generation(), generation)
        self.assertEqual(self.runtime.command("planning_request")["planning_request"]["deadline_ms"], request["deadline_ms"])
        self.answer(request)
        back = self.request()
        self.assertEqual(back["input"]["binding"]["expected_stage"], "return")
        self.assertEqual(self.runtime._supervisor.task_start, before)
        self.answer(back)
        self.state("completed")

    def test_changed_pixels_same_revision_stop_original_candidate(self):
        request = self.start()
        self.bridge.pixels = b"changed visible pixels"
        self.answer(request)
        stopped = self.state("interrupted")
        self.assertIn("pixels", stopped["run"]["last_public_reason"])
        self.assertEqual([r for r in self.bridge.requests if r["kind"] == "action"], [])

    def test_bad_schema_binding_duplicate_and_late_candidate_are_rejected(self):
        request = self.start()
        wrong = candidate(request)
        wrong["extra"] = True
        self.assertEqual(self.runtime.command("plan", request_id=request["request_id"], candidate=wrong)["status"], "rejected")
        wrong = candidate(request)
        wrong["execution_epoch"] += 1
        self.assertEqual(self.runtime.command("plan", request_id=request["request_id"], candidate=wrong)["status"], "rejected")
        self.answer(request)
        self.assertEqual(self.runtime.command("plan", request_id=request["request_id"], candidate=candidate(request))["status"], "rejected")
        self.runtime.pause("Stop external planning")
        self.state("paused")
        self.assertEqual(self.runtime.command("plan", request_id=request["request_id"], candidate=candidate(request))["status"], "rejected")

    def test_concurrent_start_has_one_admission(self):
        barrier = threading.Barrier(2)
        expected = self.expect()
        def start():
            barrier.wait()
            return self.runtime.command("start", direction="east", distance=1, **expected)
        with ThreadPoolExecutor(2) as pool:
            first, second = pool.submit(start), pool.submit(start)
            results = [first.result(), second.result()]
        self.assertEqual(sorted(r["status"] for r in results), ["accepted", "rejected"])
        self.request()

    def test_pause_return_planning_continue_retains_progress_task_and_budgets(self):
        self.answer(self.start())
        back = self.request()
        original = self.wait(lambda: (s if (s := self.runtime.status())["run"]["progress"]["verified_steps"] == 1 else None))
        self.assertEqual(original["run"]["progress"]["verified_steps"], 1)
        self.assertEqual(self.runtime.pause("Operator checkpoint")["status"], "pause_requested")
        paused = self.state("paused")
        self.assertEqual(self.runtime.command("planning_request")["planning_request"], None)
        self.assertEqual(self.runtime.command("plan", request_id=back["request_id"], candidate=candidate(back))["status"], "rejected")
        # Explicit Observe/Resume is required; continuation never does it itself.
        rejected = self.runtime.command("continue", run_id=paused["run_id"],
            execution_epoch=paused["run"]["execution_epoch"], **self.expect())
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(self.runtime.status()["run"]["state"], "paused")
        self.assertEqual(self.controller.execute("observe")["status"], "ready")
        self.assertEqual(self.controller.execute("resume")["status"], "ready")
        stopped = self.runtime.status()
        result = self.runtime.command("continue", run_id=stopped["run_id"],
            execution_epoch=stopped["run"]["execution_epoch"], **self.expect())
        self.assertEqual(result["status"], "accepted", result)
        fresh = self.request()
        self.assertEqual(fresh["input"]["binding"]["expected_stage"], "return")
        self.assertEqual(fresh["input"]["task"], original["task"])
        self.assertEqual(fresh["input"]["packet"]["remaining_budgets"]["primitives"], 7)
        self.assertLessEqual(fresh["input"]["packet"]["remaining_budgets"]["planner_calls"], 8)
        self.answer(fresh)
        self.state("completed")
        self.assertEqual(len([r for r in self.bridge.requests if r["kind"] == "action"]), 2)

    def test_pause_during_native_wait_is_responsive_and_rejection_is_not_unknown(self):
        entered, release = threading.Event(), threading.Event()
        def gate(bridge, request):
            if request["kind"] == "action":
                entered.set()
                release.wait(2)
        self.bridge.before_gate = gate
        self.answer(self.start())
        self.assertTrue(entered.wait(2))
        started = time.monotonic()
        self.runtime.pause("Pause outstanding action")
        snapshot = self.runtime.status()
        self.assertLess(time.monotonic() - started, 0.15)
        self.assertTrue(snapshot["run"]["paused"])
        self.assertEqual(snapshot["run"]["state"], "executing")
        release.set()
        stopped = self.state("paused")
        self.assertEqual(stopped["last_receipt"]["disposition"], "rejected")
        self.assertIsNone(self.runtime._supervisor.pending_intent)

    def test_published_timeout_is_unknown_never_replayed_or_continued(self):
        def lose(bridge, request):
            return request["kind"] != "action"
        self.bridge.behavior = lose
        self.answer(self.start())
        stopped = self.state("unknown")
        self.assertEqual(stopped["last_receipt"]["disposition"], "unknown")
        self.assertIsNotNone(self.runtime._supervisor.pending_intent)
        self.assertEqual(len([r for r in self.bridge.requests if r["kind"] == "action"]), 1)
        result = self.runtime.command("continue", run_id=stopped["run_id"],
            execution_epoch=stopped["run"]["execution_epoch"], **self.expect())
        self.assertEqual(result["status"], "rejected")

    def test_receipt_journal_failure_after_movement_remains_unknown(self):
        request = self.start()
        original = self.controller._record
        def fail_receipt(request, outcome):
            if request.get("kind") == "run_receipt":
                raise OSError("Receipt journal unavailable after native action")
            return original(request, outcome)
        with patch.object(self.controller, "_record", side_effect=fail_receipt):
            self.answer(request)
            stopped = self.state("unknown")
        actions = [r for r in self.bridge.requests if r["kind"] == "action"]
        self.assertEqual(len(actions), 1)
        self.assertEqual(self.bridge.value["scene"]["position"], [1, 0, 0])
        self.assertEqual(stopped["last_receipt"]["disposition"], "unknown")
        self.assertIsNotNone(self.runtime._supervisor.pending_intent)
        self.assertEqual(self.runtime.command("continue", run_id=stopped["run_id"],
            execution_epoch=stopped["run"]["execution_epoch"], **self.expect())["status"], "rejected")

    def test_persistent_journal_failure_keeps_worker_and_unknown_state_visible(self):
        request = self.start()
        original = self.controller._record
        failed = False
        def fail_from_receipt(request, outcome):
            nonlocal failed
            failed = failed or request.get("kind") == "run_receipt"
            if failed:
                raise OSError("Persistent journal outage")
            return original(request, outcome)
        with patch.object(self.controller, "_record", side_effect=fail_from_receipt):
            self.answer(request)
            stopped = self.state("unknown")
            self.assertTrue(self.runtime._thread.is_alive())
            self.assertIsNotNone(self.runtime._supervisor.pending_intent)
            self.assertEqual(stopped["last_receipt"]["disposition"], "unknown")
            self.assertIn("persistence failed", stopped["run"]["last_public_reason"])
            self.assertIsNone(self.controller.status()["run_lease"])
            self.assertEqual(self.runtime.command("abandon", run_id=stopped["run_id"],
                execution_epoch=stopped["run"]["execution_epoch"])["status"], "accepted")
            self.state("abandoned")
        self.assertEqual(len([r for r in self.bridge.requests if r["kind"] == "action"]), 1)

    def test_pause_after_outstanding_rejection_is_consumed_before_continuation(self):
        entered, release_action = threading.Event(), threading.Event()
        paused_published, release_publish = threading.Event(), threading.Event()
        def gate(bridge, request):
            if request["kind"] == "action":
                entered.set()
                release_action.wait(2)
        original_publish = self.runtime._publish
        def publish():
            original_publish()
            snapshot = self.runtime.status()
            if snapshot["run"]["state"] == "paused" and snapshot["last_receipt"] is not None:
                paused_published.set()
                release_publish.wait(2)
        self.bridge.before_gate = gate
        with patch.object(self.runtime, "_publish", side_effect=publish):
            self.answer(self.start())
            self.assertTrue(entered.wait(1))
            self.runtime.pause("Pause outstanding action")
            release_action.set()
            self.assertTrue(paused_published.wait(1))
            stopped = self.runtime.status()
            self.assertEqual(stopped["last_receipt"]["disposition"], "rejected")
            self.bridge.value.update(status="ready", error="")
            self.assertEqual(self.controller.execute("observe")["status"], "ready")
            self.assertEqual(self.controller.execute("resume")["status"], "ready")
            self.assertEqual(self.runtime.command("continue", run_id=stopped["run_id"],
                execution_epoch=stopped["run"]["execution_epoch"], **self.expect())["status"], "accepted")
            release_publish.set()
            fresh = self.request()
        self.assertEqual(fresh["input"]["binding"]["expected_stage"], "outbound")
        self.answer(fresh)
        self.answer(self.request())
        self.state("completed")

    def test_capacity_failure_occurs_before_input_and_retains_non_delivery(self):
        request = self.start()
        with patch.object(self.runtime._store, "reserve_dispatch", side_effect=CapacityError("Retention cap reached")):
            self.answer(request)
            stopped = self.state("blocked")
        self.assertEqual(stopped["last_receipt"]["disposition"], "not_dispatched")
        self.assertFalse(any(r["kind"] == "action" for r in self.bridge.requests))

    def test_abandon_exact_run_and_restart_restore_no_authority(self):
        self.start()
        before = self.runtime.status()
        bad = self.runtime.command("abandon", run_id=before["run_id"], execution_epoch=12)
        self.assertEqual(bad["status"], "rejected")
        result = self.runtime.command("abandon", run_id=before["run_id"], execution_epoch=0)
        self.assertEqual(result["status"], "accepted")
        self.state("abandoned")
        self.runtime.close()
        replacement = GameplayRuntime(self.controller)
        self.addCleanup(replacement.close)
        self.assertIsNone(replacement.status())
        self.assertIsNone(self.controller.status()["run_lease"])
        self.assertTrue(self.controller.status()["pause_requested"])

    def test_close_during_planning_is_bounded_and_invalidates_request(self):
        request = self.start()
        started = time.monotonic()
        self.runtime.close()
        self.assertLess(time.monotonic() - started, 0.3)
        self.assertIsNone(self.controller.status()["run_lease"])
        self.assertEqual(self.runtime.command("plan", request_id=request["request_id"], candidate=candidate(request))["status"], "rejected")
        self.assertEqual(self.runtime.command("start", direction="east", distance=1, **self.expect())["status"], "rejected")

    def test_command_exact_fields_and_no_implicit_task(self):
        for kind, payload in [("planning_request", {"extra": 1}), ("start", {"direction": "east"}),
                              ("continue", {"run_id": "missing", "execution_epoch": 0, **self.expect()}),
                              ("invalid", {})]:
            self.assertEqual(self.runtime.command(kind, **payload)["status"], "rejected")
        self.assertIsNone(self.runtime.status())
        self.assertFalse(any(r["kind"] == "action" for r in self.bridge.requests))

    def test_native_lease_loss_rejects_candidate_before_consumption(self):
        request = self.start()
        self.controller.pause()
        result = self.runtime.command("plan", request_id=request["request_id"], candidate=candidate(request))
        self.assertEqual(result["status"], "rejected")
        self.assertIsNone(self.runtime.command("planning_request")["planning_request"])
        self.state("interrupted")
        self.assertFalse(any(r["kind"] == "action" for r in self.bridge.requests))

    def test_malformed_envelope_and_world_change_remain_unknown(self):
        request = self.start()
        with patch.object(self.controller, "execute_run", return_value={"malformed": True}):
            self.answer(request)
            stopped = self.state("unknown")
        self.assertEqual(stopped["last_receipt"]["disposition"], "unknown")
        self.assertIsNotNone(self.runtime._supervisor.pending_intent)
        self.assertFalse(any(r["kind"] == "action" for r in self.bridge.requests))

    def test_world_change_during_planning_revokes_without_input(self):
        request = self.start()
        self.bridge.value["session"] = "replacement"
        self.bridge.value["revision"] += 1
        self.controller.execute("observe")
        self.assertEqual(self.runtime.command("plan", request_id=request["request_id"], candidate=candidate(request))["status"], "rejected")
        self.state("interrupted")
        self.assertFalse(any(r["kind"] == "action" for r in self.bridge.requests))

    def test_expired_inbox_does_not_consume_late_response_or_renew_deadline(self):
        request = self.start()
        deadline = self.runtime._inbox.pending[1]
        self.runtime._inbox.clock = lambda: deadline
        self.assertIsNone(self.runtime.command("planning_request")["planning_request"])
        self.assertEqual(self.runtime.command("plan", request_id=request["request_id"], candidate=candidate(request))["status"], "rejected")
        self.assertIsNone(self.runtime._inbox.candidate)

    def test_concurrent_continuation_cannot_admit_the_same_epoch_twice(self):
        self.start()
        self.runtime.pause("Checkpoint before dispatch")
        paused = self.state("paused")
        self.assertEqual(self.controller.execute("observe")["status"], "ready")
        self.assertEqual(self.controller.execute("resume")["status"], "ready")
        entered, release = threading.Event(), threading.Event()
        original = self.runtime._ingest_snapshot
        def gate(*args, **kwargs):
            entered.set()
            release.wait(2)
            return original(*args, **kwargs)
        payload = {"run_id": paused["run_id"], "execution_epoch": paused["run"]["execution_epoch"], **self.expect()}
        with patch.object(self.runtime, "_ingest_snapshot", side_effect=gate):
            self.assertEqual(self.runtime.command("continue", **payload)["status"], "accepted")
            self.assertTrue(entered.wait(1))
            self.assertEqual(self.runtime.command("continue", **payload)["status"], "rejected")
            release.set()
            request = self.request()
        self.assertGreater(request["input"]["binding"]["execution_epoch"], payload["execution_epoch"])
        self.answer(request)
        back = self.request()
        self.answer(back)
        self.state("completed")
