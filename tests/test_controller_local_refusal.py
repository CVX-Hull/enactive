"""Local allowance refusal uses real controller transport, never native acceptance."""
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch

from harness import controller as controller_module
from harness.controller import ControlError, MissionInputRefusal
from tests import test_controller as fixtures
from tests.test_controller import FakeBridge


class ControllerLocalRefusalTests(unittest.TestCase):
    setUp = fixtures.ControllerTests.setUp
    ready = fixtures.ControllerTests.ready
    expect = fixtures.ControllerTests.expect
    acquire = fixtures.ControllerTests.acquire
    mission_dispatch = fixtures.ControllerTests.mission_dispatch

    def assert_healthy_refusal(self, receipt, lease, fake):
        self.assertEqual(receipt["result"]["status"], "controller_error", receipt)
        self.assertFalse(receipt["published"])
        self.assertIsNone(receipt["received_monotonic"])
        self.assertIs(self.controller._mission_lease, lease)
        self.assertFalse(self.controller.frozen)
        self.assertFalse(self.controller.pause_requested)
        self.assertFalse((self.controller.bridge / "pause").exists())
        self.assertEqual(self.controller.unknown_outcomes, [])
        self.assertFalse(any(row["kind"] in {"action", "key", "direct"} for row in fake.requests))
        self.assertEqual(list(self.controller.admissions.glob("*.json")), [])

    def test_local_expiry_at_each_unpublished_stage_preserves_receipt_and_custody(self):
        for stage in ("before_preparation", "after_preparation", "admission", "publication"):
            with self.subTest(stage=stage), FakeBridge(self.controller) as fake:
                self.ready()
                lease = self.acquire(operation="interaction")
                clock = SimpleNamespace(mono=time.monotonic())
                deadline = clock.mono + 1
                proxy = SimpleNamespace(monotonic=lambda: clock.mono, time=time.time, sleep=time.sleep)
                calls, prepared = [], []
                original_atomic = controller_module.atomic_json
                def classify():
                    with self.controller.data_lock:
                        self.controller.observation_snapshot()
                        calls.append(True)
                        self.assertGreaterEqual(clock.mono, deadline)
                        return "ordinary local allowance exhausted"
                def prepare(*args):
                    prepared.append(True)
                    if stage == "after_preparation": clock.mono = deadline
                def atomic(path, value, **kwargs):
                    if path.parent == self.controller.admissions and stage == "admission":
                        original_atomic(path, value, **kwargs)
                        clock.mono = deadline
                        return
                    if path.name == "request.json" and value["kind"] != "observe" and stage == "publication":
                        before_publish = kwargs["before_publish"]
                        def expire():
                            clock.mono = deadline
                            before_publish()
                        kwargs["before_publish"] = expire
                    return original_atomic(path, value, **kwargs)
                if stage == "before_preparation": clock.mono = deadline
                with patch("harness.controller.time", proxy), patch("harness.controller.atomic_json", atomic):
                    receipt = self.mission_dispatch(lease, preflight=prepare,
                        deadline_monotonic=deadline, unpublished_refusal=classify)
                self.assert_healthy_refusal(receipt, lease, fake)
                self.assertEqual(len(calls), 1)
                self.assertEqual(len(prepared), 0 if stage == "before_preparation" else 1)
                self.assertEqual(receipt["request"] is None, stage in {"before_preparation", "after_preparation"})
                if receipt["request"] is not None:
                    self.assertEqual(receipt["result"]["id"], receipt["request"]["id"])
                self.controller.release_mission(lease)

    def test_typed_preflight_refusal_waits_for_fatal_guards(self):
        for fault in (None, "pause", "pending", "recovery", "frame", "stale", "storage", "command"):
            with self.subTest(fault=fault), FakeBridge(self.controller) as fake:
                self.ready()
                lease = self.acquire(operation="interaction")
                clock = SimpleNamespace(mono=time.monotonic())
                proxy = SimpleNamespace(monotonic=lambda: clock.mono, time=time.time, sleep=time.sleep)
                def prepare(*args):
                    if fault == "pause": (self.controller.bridge / "pause").touch()
                    elif fault == "pending": self.controller.pending = {"id": "other"}
                    elif fault == "recovery": self.controller.control_pending = {"id": "other"}
                    elif fault == "frame": self.controller.state["revision"] += 1
                    elif fault == "stale": clock.mono += 4
                    elif fault == "command": self.controller._command_work += 1
                    elif fault == "storage": raise OSError("storage failed")
                    raise MissionInputRefusal("ordinary local primitive limit exhausted")
                with patch("harness.controller.time", proxy):
                    receipt = self.mission_dispatch(lease, preflight=prepare)
                if fault is None:
                    self.assert_healthy_refusal(receipt, lease, fake)
                    self.controller.release_mission(lease)
                else:
                    self.assertFalse(receipt["published"])
                    self.assertEqual(receipt["result"]["status"], "controller_error", receipt)
                    self.assertIsNone(self.controller._mission_lease)
                    self.assertTrue(self.controller.pause_requested)
                self.controller.pending = self.controller.control_pending = None
                self.controller._command_work = 0
                self.controller.state = None

    def test_classifier_decline_error_or_invalid_reason_is_fatal(self):
        for classification in (None, "", "x" * 1025, False, ControlError("global deadline exhausted")):
            with self.subTest(classification=repr(classification)[:60]), FakeBridge(self.controller) as fake:
                self.ready()
                lease = self.acquire(operation="interaction")
                clock = SimpleNamespace(mono=time.monotonic())
                deadline = clock.mono + 1
                proxy = SimpleNamespace(monotonic=lambda: clock.mono, time=time.time, sleep=time.sleep)
                def prepare(*args): clock.mono = deadline
                def classify():
                    if isinstance(classification, Exception): raise classification
                    return classification
                with patch("harness.controller.time", proxy):
                    receipt = self.mission_dispatch(lease, preflight=prepare,
                        deadline_monotonic=deadline, unpublished_refusal=classify)
                self.assertFalse(receipt["published"])
                self.assertIsNone(self.controller._mission_lease)
                self.assertTrue(self.controller.pause_requested)
                self.controller.state = None

    def test_unpublished_admission_cleanup_failure_is_fatal(self):
        with FakeBridge(self.controller) as fake:
            self.ready()
            lease = self.acquire(operation="interaction")
            clock = SimpleNamespace(mono=time.monotonic())
            deadline = clock.mono + 1
            proxy = SimpleNamespace(monotonic=lambda: clock.mono, time=time.time, sleep=time.sleep)
            original_atomic, original_unlink = controller_module.atomic_json, Path.unlink
            def atomic(path, value, **kwargs):
                original_atomic(path, value, **kwargs)
                if path.parent == self.controller.admissions: clock.mono = deadline
            def unlink(path, *args, **kwargs):
                if path.parent == self.controller.admissions and path.suffix == ".json" and path.exists():
                    raise OSError("admission cleanup failed")
                return original_unlink(path, *args, **kwargs)
            with patch("harness.controller.time", proxy), patch("harness.controller.atomic_json", atomic), \
                    patch.object(Path, "unlink", unlink):
                receipt = self.mission_dispatch(lease, deadline_monotonic=deadline,
                    unpublished_refusal=lambda: "ordinary local allowance exhausted")
            self.assertEqual(receipt["result"]["status"], "controller_error", receipt)
            self.assertFalse(receipt["published"])
            self.assertIsNotNone(receipt["request"])
            self.assertIsNone(self.controller._mission_lease)
            self.assertTrue(self.controller.pause_requested)
            self.assertEqual(self.controller.unknown_outcomes, [])
            self.assertFalse(any(row["kind"] == "action" for row in fake.requests))
