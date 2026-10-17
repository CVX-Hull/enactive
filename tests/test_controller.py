"""File-transport tests. This fake bridge is not evidence of CDDA acceptance."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from harness.controller import Controller, ControlError, atomic_json, read_json


def state(request_id="", *, revision=1, **changes):
    value = {"protocol": 1, "id": request_id, "session": "game-test", "revision": revision,
             "category": "DEFAULTMODE", "actions": ["UP", "DOWN", "LEFT", "RIGHT", "INVENTORY"],
             "status": "ready", "error": "", "paused": False,
             "timestamp_ms": int(time.time() * 1000), "frame_ok": True, "in_game": True,
             "scene": {"position": [0, 0, 0], "turn": 1, "visible_creatures": [],
                       "neighbors": [{"dx": dx, "dy": dy, "visible": True,
                                      "terrain": "t_floor", "furniture": "f_null"}
                                     for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]]}}
    value.update(changes)
    return value


class FakeBridge:
    """Exercises real atomic files and threads, never claims to emulate game rules."""
    def __init__(self, controller, behavior=None):
        self.bridge = controller.bridge
        self.behavior = behavior
        self.value = state(paused=True)
        self.requests = []
        self.failures = []
        self.stopped = threading.Event()
        self.claimed = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stopped.set()
        self.thread.join(2)
        if self.failures:
            raise self.failures[0]

    def publish(self, value):
        atomic_json(self.bridge / "response.json", value)
        atomic_json(self.bridge / "state.json", value)

    def run(self):
        try:
            while not self.stopped.wait(0.003):
                try:
                    (self.bridge / "request.json").rename(self.bridge / "claimed.json")
                except FileNotFoundError:
                    continue
                request = read_json(self.bridge / "claimed.json")
                self.requests.append(request)
                self.claimed.set()
                self.value["id"] = request["id"]
                self.value["timestamp_ms"] = int(time.time() * 1000)
                self.value["paused"] = (self.bridge / "pause").exists()
                kind = request["kind"]
                if kind == "resume":
                    (self.bridge / "pause").unlink(missing_ok=True)
                    self.value["paused"] = False
                    self.value["revision"] += 1
                if kind in {"key", "action"}:
                    self.value["revision"] += 1
                    self.value["status"] = "dispatched"
                    self.value["frame_ok"] = False
                    self.publish(self.value.copy())
                    self.value["status"] = "ready"
                    self.value["frame_ok"] = True
                    movement = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
                    if request.get("action") in movement:
                        dx, dy = movement[request["action"]]
                        self.value["scene"]["position"][0] += dx
                        self.value["scene"]["position"][1] += dy
                publish = True if self.behavior is None else self.behavior(self, request)
                (self.bridge / "claimed.json").unlink(missing_ok=True)
                if publish:
                    self.publish(self.value.copy())
        except Exception as exc:
            self.failures.append(exc)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        # Functional exchanges use real files/threads on shared CI runners.
        # Short deadline behavior is exercised with explicit per-call timeouts below.
        self.controller = Controller(self.root, timeout=2.0)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.controller.close)

    def ready(self):
        self.assertEqual(self.controller.execute("observe")["status"], "ready")
        self.assertEqual(self.controller.execute("resume")["status"], "ready")

    def expect(self):
        value = self.controller.state
        return {"expected_session": value["session"], "expected_revision": value["revision"]}

    def test_startup_pauses_retires_and_never_replays(self):
        self.controller.close()
        bridge = self.root / ".runtime" / "bridge"
        atomic_json(bridge / "request.json", {"kind": "key", "key": "x", "id": "old"})
        self.controller = Controller(self.root, timeout=2.0)
        self.addCleanup(self.controller.close)
        self.assertTrue((bridge / "pause").exists())
        self.assertFalse((bridge / "request.json").exists())
        self.assertEqual(len(list(bridge.glob("cancelled-startup-*.json"))), 1)
        self.assertEqual(self.controller.execute("key", key="x", **{"expected_session": "old", "expected_revision": 1})["status"], "controller_error")
        with FakeBridge(self.controller) as fake:
            self.ready()
            self.assertFalse(any(request["kind"] == "key" for request in fake.requests))

    def test_process_lock_is_exclusive(self):
        with self.assertRaisesRegex(ControlError, "Another controller"):
            Controller(self.root)

    def test_explicit_observe_then_resume(self):
        self.assertEqual(self.controller.execute("resume")["status"], "controller_error")
        with FakeBridge(self.controller):
            self.ready()
            result = self.controller.execute("key", key="i", **self.expect())
            self.assertEqual(result["status"], "ready")
            self.assertFalse(self.controller.status()["pause_requested"])

    def test_rejects_stale_decision_before_primitive(self):
        with FakeBridge(self.controller) as fake:
            self.ready()
            old = self.expect()
            fake.value["revision"] += 1
            result = self.controller.execute("key", key="x", **old)
            self.assertIn("Stale", result["error"])
            self.assertFalse(any(request["kind"] == "key" for request in fake.requests))

    def test_missing_expectation_does_not_dispatch(self):
        with FakeBridge(self.controller) as fake:
            self.ready()
            self.assertIn("require expected", self.controller.execute("action", action="UP")["error"])
            self.assertFalse(any(request["kind"] == "action" for request in fake.requests))

    def test_native_rejection_is_not_ready_or_retried(self):
        def reject(fake, request):
            if request["kind"] == "key":
                fake.value.update(status="rejected", error="stale session or revision")
            return True
        with FakeBridge(self.controller, reject) as fake:
            self.ready()
            result = self.controller.execute("key", key="x", **self.expect())
            self.assertEqual(result["status"], "rejected")
            self.assertEqual(sum(r["kind"] == "key" for r in fake.requests), 1)

    def test_timeout_retires_unclaimed_and_freezes(self):
        result = self.controller.execute("observe", timeout=0.04)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["retirement"], "retired_before_claim")
        self.assertTrue(self.controller.frozen)
        self.assertFalse((self.controller.bridge / "request.json").exists())
        self.assertEqual(len(list(self.controller.bridge.glob("cancelled-timeout-*.json"))), 1)
        self.assertEqual(self.controller.execute("resume")["status"], "controller_error")
        with FakeBridge(self.controller):
            self.ready()

    def test_claimed_timeout_is_unknown_and_never_replayed(self):
        def abandon(fake, request):
            return request["kind"] != "key"
        with FakeBridge(self.controller, abandon) as fake:
            self.ready()
            result = self.controller.execute("key", key="x", timeout=0.06, **self.expect())
            self.assertEqual(result["status"], "timeout")
            self.assertEqual(result["retirement"], "absent_may_be_claimed_or_dispatched")
            self.assertEqual(self.controller.execute("key", key="x", **self.expect())["status"], "controller_error")
            self.assertEqual(self.controller.execute("observe")["status"], "ready")
            self.assertTrue(self.controller.pause_requested)
            self.assertEqual(sum(r["kind"] == "key" for r in fake.requests), 1)

    def test_wrong_id_response_cannot_finish_request(self):
        atomic_json(self.controller.bridge / "response.json", state("prior-uuid"))
        result = self.controller.execute("observe", timeout=0.04)
        self.assertEqual(result["status"], "timeout")

    def test_wrong_protocol_freezes_with_visible_error(self):
        def corrupt(fake, request):
            fake.value["protocol"] = 99
            return True
        with FakeBridge(self.controller, corrupt):
            result = self.controller.execute("observe")
            self.assertEqual(result["status"], "controller_error")
            self.assertIn("protocol", result["error"])
            self.assertTrue(self.controller.frozen)

    def test_pause_is_responsive_during_wait(self):
        with ThreadPoolExecutor() as pool:
            waiting = pool.submit(self.controller.execute, "observe", timeout=0.3)
            deadline = time.monotonic() + 1
            while not (self.controller.bridge / "request.json").exists() and time.monotonic() < deadline:
                time.sleep(0.002)
            started = time.monotonic()
            self.assertEqual(self.controller.pause()["status"], "pause_requested")
            self.assertLess(time.monotonic() - started, 0.1)
            self.assertFalse(waiting.done())
            self.assertTrue((self.controller.bridge / "pause").exists())
            waiting.result()

    def test_serialized_decisions_cannot_share_revision(self):
        with FakeBridge(self.controller) as fake:
            self.ready()
            authority = self.expect()
            with ThreadPoolExecutor(2) as pool:
                results = list(pool.map(lambda _: self.controller.execute("key", key="x", **authority), range(2)))
            self.assertEqual(sum(result["status"] == "ready" for result in results), 1)
            self.assertEqual(sum(r["kind"] == "key" for r in fake.requests), 1)

    def test_walk_verifies_displacement(self):
        with FakeBridge(self.controller) as fake:
            self.ready()
            result = self.controller.execute("walk", direction="east", steps=3, **self.expect())
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["steps"], 3)
            self.assertEqual(fake.value["scene"]["position"], [3, 0, 0])

    def test_walk_stops_on_creature_even_when_not_hostile(self):
        def creature(fake, request):
            if request["kind"] == "action":
                fake.value["scene"]["visible_creatures"] = [{"name": "cat", "hostile": False}]
            return True
        with FakeBridge(self.controller, creature) as fake:
            self.ready()
            result = self.controller.execute("walk", direction="east", steps=5, **self.expect())
            self.assertEqual(result["status"], "stopped")
            self.assertEqual(result["steps"], 1)
            self.assertEqual(sum(r["kind"] == "action" for r in fake.requests), 1)

    def test_walk_stops_on_unknown_terrain_furniture_and_no_progress(self):
        with FakeBridge(self.controller) as fake:
            self.ready()
            for changes in ({"visible": False}, {"terrain": "t_water_sh"}, {"furniture": "f_chair"}):
                tile = fake.value["scene"]["neighbors"][-1]
                original = tile.copy()
                tile.update(changes)
                result = self.controller.execute("walk", direction="east", steps=2, **self.expect())
                self.assertEqual(result["steps"], 0)
                self.assertEqual(result["status"], "stopped")
                tile.clear()
                tile.update(original)
            self.assertFalse(any(r["kind"] == "action" for r in fake.requests))
        def no_progress(fake, request):
            if request["kind"] == "action":
                fake.value["scene"]["position"] = [0, 0, 0]
            return True
        with FakeBridge(self.controller, no_progress) as fake:
            self.ready()
            result = self.controller.execute("walk", direction="east", steps=3, **self.expect())
            self.assertEqual(result["status"], "stopped")
            self.assertIn("displacement", result["error"])

    def test_walk_context_change_stops(self):
        def prompt(fake, request):
            if request["kind"] == "action":
                fake.value.update(category="YESNO", scene=None)
            return True
        with FakeBridge(self.controller, prompt) as fake:
            self.ready()
            result = self.controller.execute("walk", direction="north", steps=4, **self.expect())
            self.assertEqual(result["status"], "stopped")
            self.assertEqual(sum(r["kind"] == "action" for r in fake.requests), 1)

    def test_goal_and_journal_do_not_claim_game_success(self):
        result = self.controller.execute("goal", text="Find water")
        self.assertEqual(result["status"], "recorded")
        lines = [json.loads(line) for line in self.controller.journal.read_text().splitlines()]
        self.assertEqual(lines[-1]["request"]["text"], "Find water")
        self.assertNotIn("success", lines[-1]["outcome"])

    def test_input_bounds(self):
        for kind, payload in [("key", {"key": "abc"}), ("key", {"key": "é"}),
                              ("walk", {"direction": "east", "steps": 9}),
                              ("observe", {"timeout": 16}), ("observe", {"timeout": True})]:
            self.assertEqual(self.controller.execute(kind, **payload)["status"], "controller_error")

    def test_shutdown_retires_waiter_before_releasing_writer_lock(self):
        with ThreadPoolExecutor() as pool:
            waiting = pool.submit(self.controller.execute, "observe", timeout=1)
            deadline = time.monotonic() + 1
            while not (self.controller.bridge / "request.json").exists() and time.monotonic() < deadline:
                time.sleep(0.002)
            self.controller.close()
            self.assertEqual(waiting.result()["status"], "controller_error")
            self.assertFalse((self.controller.bridge / "request.json").exists())
            self.assertTrue((self.controller.bridge / "pause").exists())
            self.assertEqual(self.controller.execute("resume")["status"], "controller_error")

    def test_pause_during_resume_observation_wins(self):
        observing_resume = threading.Event()
        release = threading.Event()
        def block(fake, request):
            if request["kind"] == "observe" and observing_resume.is_set():
                release.wait(1)
            return True
        with FakeBridge(self.controller, block):
            self.ready()
            self.controller.pause()
            observing_resume.set()
            with ThreadPoolExecutor() as pool:
                waiting = pool.submit(self.controller.execute, "resume")
                deadline = time.monotonic() + 1
                while not (self.controller.bridge / "claimed.json").exists() and time.monotonic() < deadline:
                    time.sleep(0.002)
                self.controller.pause()
                release.set()
                result = waiting.result()
            self.assertEqual(result["status"], "pause_requested")
            self.assertTrue((self.controller.bridge / "pause").exists())
            self.assertTrue(self.controller.pause_requested)

    def test_native_takeover_supersedes_queued_resume(self):
        self._queued_resume_loses_to_pause(native=True)

    def test_new_pause_supersedes_queued_resume(self):
        self._queued_resume_loses_to_pause(native=False)

    def _queued_resume_loses_to_pause(self, native):
        waiting = threading.Event()
        release = threading.Event()
        class Gate:
            def __enter__(self):
                waiting.set()
                if not release.wait(1):
                    raise AssertionError("test gate not released")
            def __exit__(self, *args):
                return False
        with FakeBridge(self.controller) as fake:
            self.ready()
            previous = sum(r["kind"] == "resume" for r in fake.requests)
            original = self.controller.command_lock
            self.controller.command_lock = Gate()
            try:
                with ThreadPoolExecutor() as pool:
                    queued = pool.submit(self.controller.execute, "resume")
                    self.assertTrue(waiting.wait(1))
                    if native:
                        fake.value["revision"] += 1
                        fake.value["paused"] = True
                        (fake.bridge / "pause").touch()
                        # No status poll: Resume must discover takeover itself.
                    else:
                        self.controller.pause()
                    release.set()
                    result = queued.result()
                self.assertEqual(result["status"], "pause_requested")
                self.assertTrue(self.controller.pause_requested)
                self.assertTrue((self.controller.bridge / "pause").exists())
                self.assertEqual(sum(r["kind"] == "resume" for r in fake.requests), previous)
            finally:
                self.controller.command_lock = original
