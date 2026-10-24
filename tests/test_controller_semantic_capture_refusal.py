"""Capture churn in real controller transport; not native gameplay qualification."""
import copy
import hashlib
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch

from harness.controller import atomic_json, read_json
from tests import test_controller as fixtures
from tests.test_controller import FakeBridge


class ControllerSemanticCaptureRefusalTests(unittest.TestCase):
    setUp = fixtures.ControllerTests.setUp
    ready = fixtures.ControllerTests.ready
    expect = fixtures.ControllerTests.expect
    acquire = fixtures.ControllerTests.acquire
    mission_dispatch = fixtures.ControllerTests.mission_dispatch
    mission_resume_binding = fixtures.ControllerTests.mission_resume_binding
    mission_resume = fixtures.ControllerTests.mission_resume

    def refresh(self, fake, observation):
        replacement = copy.deepcopy(observation)
        replacement.update(id="", frame="frame-game-test-2.png")
        fake.value = copy.deepcopy(replacement)
        self.controller._accept(replacement)

    def assert_unpublished(self, receipt, fake):
        self.assertFalse(receipt["published"], receipt)
        self.assertIsNone(receipt["request"])
        self.assertIsNone(receipt["received_monotonic"])
        self.assertNotIn("id", receipt["result"])
        self.assertEqual(self.controller.unknown_outcomes, [])
        self.assertEqual(list(self.controller.admissions.glob("*.json")), [])
        self.assertFalse(any(row["kind"] in {"key", "action", "direct"} for row in fake.requests))

    def assert_healthy(self, lease, authority):
        self.assertIs(self.controller._mission_lease, lease)
        self.assertFalse(self.controller.frozen)
        self.assertFalse(self.controller.pause_requested)
        self.assertFalse((self.controller.bridge / "pause").exists())
        self.assertEqual(read_json(self.controller.bridge / "authority.json"), authority)

    def test_wait_start_retains_prepared_evidence_without_native_request_or_retry(self):
        # Semantic activity START emits ordinary action "wait", not paused recovery.
        for equal_pixels in (True, False):
            with self.subTest(equal_pixels=equal_pixels), FakeBridge(self.controller) as fake:
                self.ready()
                fake.value["actions"].append("wait")
                fake.value["revision"] += 1
                self.assertEqual(self.controller.execute("observe")["status"], "ready")
                lease = self.acquire(operation="interaction")
                authority = read_json(self.controller.bridge / "authority.json")
                image = b"synthetic informing pixels"
                (fake.bridge / fake.value["frame"]).write_bytes(image)
                captured = []
                preparation = self.root / "prepared-wait-start.json"

                def prepare(observation, received):
                    captured.append((copy.deepcopy(observation), received))
                    atomic_json(preparation, {"logical_action_id": "wait-start", "charge": 1,
                        "observation": observation, "received_monotonic": received})
                    self.refresh(fake, observation)
                    (fake.bridge / fake.value["frame"]).write_bytes(image if equal_pixels else b"changed pixels")

                receipt = self.mission_dispatch(lease, value="wait", logical_action_id="wait-start",
                    preflight=prepare, expected_image_sha256=hashlib.sha256(image).hexdigest())
                self.assertEqual(receipt["result"]["status"], "rejected", receipt)
                self.assert_unpublished(receipt, fake)
                self.assert_healthy(lease, authority)
                self.assertEqual(len(captured), 1)
                self.assertEqual(read_json(preparation)["charge"], 1)
                self.assertEqual(receipt["preflight"], {"observation": captured[0][0],
                    "received_monotonic": captured[0][1], "expected_image_sha256": hashlib.sha256(image).hexdigest()})
                self.assertNotEqual(self.controller.state["frame"], captured[0][0]["frame"])

                # Only an explicit Observe and separately chosen key send input.
                observed, received = self.controller.observe_mission(deadline_monotonic=time.monotonic() + 2)
                self.assertEqual(observed["frame"], "frame-game-test-2.png")
                self.assertGreaterEqual(received, captured[0][1])
                self.assert_healthy(lease, authority)
                self.assertFalse(any(row["kind"] == "action" for row in fake.requests))
                chosen = self.mission_dispatch(lease, kind="key", value="ESC", logical_action_id="new-choice")
                self.assertEqual(chosen["result"]["status"], "ready", chosen)
                self.assertEqual([row["kind"] for row in fake.requests if row["kind"] in {"key", "action"}], ["key"])
                self.assertEqual(read_json(preparation)["charge"], 1)
                self.controller.release_mission(lease)

    def test_nonimage_key_and_navigation_keep_original_preflight_across_capture_churn(self):
        for operation, kind, value in (("interaction", "key", "ENTER"), ("navigate", "action", "UP")):
            for stage in ("callback", "final_fence"):
                with self.subTest(operation=operation, stage=stage), FakeBridge(self.controller) as fake:
                    self.ready()
                    if kind == "key":
                        fake.value.update(scene=None, category="UNFAMILIAR_PANEL")
                        fake.value["boundary"]["kind"] = "menu"
                        self.assertEqual(self.controller.execute("observe")["status"], "ready")
                    lease = self.acquire(operation=operation)
                    authority = read_json(self.controller.bridge / "authority.json")
                    captured, refreshed = [], []
                    original_owner_check = self.controller._check_owner

                    def refresh():
                        self.refresh(fake, self.controller.state)
                        refreshed.append(True)

                    def prepare(observation, received):
                        captured.append((copy.deepcopy(observation), received))
                        if stage == "callback":
                            refresh()

                    def owner_check(*args):
                        original_owner_check(*args)
                        if stage == "final_fence" and captured and not refreshed:
                            refresh()

                    with patch.object(self.controller, "_check_owner", owner_check):
                        receipt = self.mission_dispatch(lease, kind=kind, value=value, preflight=prepare)
                    self.assertEqual(receipt["result"]["status"], "ready", receipt)
                    self.assertTrue(receipt["published"], receipt)
                    self.assertEqual(receipt["request"]["frame"], captured[0][0]["frame"])
                    self.assertFalse(receipt["request"]["require_exact_frame"])
                    self.assertEqual(len([row for row in fake.delivered if row["kind"] == kind]), 1)
                    self.assertNotEqual(receipt["request"]["frame"], "frame-game-test-2.png")
                    self.assert_healthy(lease, authority)
                    self.assertEqual(receipt["preflight"]["observation"], captured[0][0])
                    self.assertEqual(receipt["preflight"]["received_monotonic"], captured[0][1])
                    self.controller.release_mission(lease)

    def test_capture_churn_cannot_hide_simultaneous_fatal_faults(self):
        faults = ("pause", "takeover", "revision", "scene", "receiver", "control_generation",
                  "pending", "recovery", "command", "monotonic_age", "wall_age", "deadline", "storage")
        for kind, value in (("key", "ESC"), ("action", "wait")):
            for fault in faults:
                with self.subTest(kind=kind, fault=fault), FakeBridge(self.controller) as fake:
                    self.ready()
                    fake.value["actions"].append("wait")
                    fake.value["revision"] += 1
                    self.assertEqual(self.controller.execute("observe")["status"], "ready")
                    lease = self.acquire(operation="interaction")
                    clock = SimpleNamespace(mono=time.monotonic(), wall=time.time())
                    proxy = SimpleNamespace(monotonic=lambda: clock.mono, time=lambda: clock.wall, sleep=time.sleep)

                    def prepare(observation, received):
                        self.refresh(fake, observation)
                        if fault == "pause": (fake.bridge / "pause").touch()
                        elif fault == "takeover": self.controller.state["takeover_generation"] += 1
                        elif fault == "revision": self.controller.state["revision"] += 1
                        elif fault == "scene": self.controller.state["scene"]["turn"] += 1
                        elif fault == "receiver": self.controller.state["boundary"]["input_receiver"] = False
                        elif fault == "control_generation": self.controller.state["boundary"]["control_generation"] += 1
                        elif fault == "pending": self.controller.pending = {"id": "other"}
                        elif fault == "recovery": self.controller.control_pending = {"id": "other"}
                        elif fault == "command": self.controller._command_work += 1
                        elif fault == "monotonic_age": clock.mono += 3.01
                        elif fault == "wall_age": clock.wall += 3.01
                        elif fault == "deadline": clock.mono += 1
                        elif fault == "storage": raise OSError("preparation storage failed")

                    try:
                        with patch("harness.controller.time", proxy):
                            receipt = self.mission_dispatch(lease, kind=kind, value=value, preflight=prepare,
                                deadline_monotonic=clock.mono + (1 if fault == "deadline" else 10))
                        self.assert_unpublished(receipt, fake)
                        self.assertEqual(receipt["result"]["status"],
                                         "rejected" if fault == "revision" else "controller_error", receipt)
                        self.assertNotEqual(receipt["result"]["error"], "Native frame identity changed during final preflight")
                        if fault == "revision":
                            self.assertIs(self.controller._mission_lease, lease)
                            self.assertFalse(self.controller.frozen)
                            self.assertFalse(self.controller.pause_requested)
                            self.controller.release_mission(lease)
                        else:
                            self.assertIsNone(self.controller._mission_lease)
                            self.assertTrue(self.controller.frozen)
                            self.assertTrue(self.controller.pause_requested)
                    finally:
                        self.controller.pending = self.controller.control_pending = None
                        self.controller._command_work = 0
                        self.controller.state = None

    def test_image_conditioned_lifecycle_and_resume_capture_churn_remain_fatal(self):
        for operation in ("lifecycle", "resume"):
            with self.subTest(operation=operation), FakeBridge(self.controller) as fake:
                if operation == "lifecycle":
                    self.ready()
                    lease = self.acquire(operation="lifecycle")
                else:
                    self.assertEqual(self.controller.execute("observe")["status"], "ready")
                image = b"image-conditioned lifecycle source"
                (fake.bridge / fake.value["frame"]).write_bytes(image)

                def prepare(observation, received):
                    self.refresh(fake, observation)

                expected = hashlib.sha256(image).hexdigest()
                receipt = (self.mission_dispatch(lease, preflight=prepare, expected_image_sha256=expected)
                           if operation == "lifecycle" else self.mission_resume(preflight=prepare,
                               expected_image_sha256=expected))
                self.assert_unpublished(receipt, fake)
                self.assertEqual(receipt["result"]["status"], "controller_error", receipt)
                self.assertIsNone(self.controller._mission_lease)
                self.assertTrue(self.controller.frozen)
                self.assertTrue(self.controller.pause_requested)
