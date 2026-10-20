"""Trusted activity transport fixtures; no native gameplay acceptance claim."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import copy
import hashlib
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from harness.controller import Controller, atomic_json, read_json, validate_control_request
from tests.test_controller import ControlBridge, FakeBridge, recovery_state


class MissionActivityControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.controller = Controller(Path(self.temp.name), timeout=1)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.controller.close)
        self.controller.stop_input()

    def prepare(self, fake, kind="activity_poll", owner=None):
        fake.value = recovery_state(kind, owner=owner)
        if self.controller.state is not None:
            fake.value["takeover_generation"] = self.controller.state["takeover_generation"]
        self.assertEqual(self.controller.execute("observe")["status"], "ready")
        (self.controller.bridge / fake.value["frame"]).write_bytes(b"informing image")
        return self.binding()

    def binding(self):
        controller = self.controller
        observed = controller.state
        return {"expected_generation": controller.pause_generation,
                "expected_operator_generation": controller.operator_pause_generation,
                "expected_controller_boot_id": controller.authority["controller_boot_id"],
                "expected_session": observed["session"], "expected_revision": observed["revision"],
                "expected_boundary_id": observed["boundary"]["id"],
                "expected_takeover_generation": observed["takeover_generation"],
                "expected_pause_origin": observed["pause_origin"],
                "expected_control_generation": observed["boundary"]["control_generation"],
                "logical_action_id": "activity-control", "deadline_monotonic": time.monotonic() + 2}

    def call(self, binding, kind="request_interrupt", **changes):
        return self.controller.recover_mission(kind, **{**binding, **changes})

    def assert_unpublished(self, receipt):
        self.assertEqual(receipt["result"]["status"], "controller_error", receipt)
        self.assertEqual(set(receipt), {"logical_action_id", "request", "result", "published",
                                        "received_monotonic", "preflight"})
        self.assertFalse(receipt["published"], receipt)
        self.assertIsNone(receipt["received_monotonic"])
        self.assertFalse((self.controller.bridge / "control.json").exists())
        self.assertEqual(list(self.controller.control_admissions.glob("*.json")), [])

    def test_exact_interrupt_answer_and_original_receipts(self):
        captured = []
        with FakeBridge(self.controller) as fake, ControlBridge(self.controller) as control:
            binding = self.prepare(fake)
            operator = self.controller.operator_pause_generation
            def preflight(observation, received):
                self.assertFalse(self.controller.data_lock._is_owned())
                self.assertTrue(self.controller.command_lock.locked())
                self.assertTrue(self.controller.control_lock.locked())
                self.assertEqual(control.requests, [])
                self.assertEqual(list(self.controller.control_admissions.glob("*.json")), [])
                captured.append((copy.deepcopy(observation), received))
                observation["revision"] = 999  # Callback cannot replace authority.
            digest = hashlib.sha256(b"informing image").hexdigest()
            receipt = self.call(binding, expected_image_sha256=digest, preflight=preflight)
            self.assertEqual(set(receipt), {"logical_action_id", "request", "result", "published",
                                            "received_monotonic", "preflight"})
            self.assertEqual(receipt["logical_action_id"], binding["logical_action_id"])
            self.assertTrue(receipt["published"], receipt)
            validate_control_request(receipt["request"])
            self.assertEqual(receipt["request"], control.requests[0])
            self.assertEqual(receipt["result"], read_json(self.controller.bridge / "control-response.json"))
            self.assertEqual(receipt["result"]["status"], "prompt_opened")
            self.assertEqual(receipt["preflight"], {"observation": captured[0][0],
                "received_monotonic": captured[0][1], "expected_image_sha256": digest})
            self.assertLessEqual(captured[0][1], receipt["received_monotonic"])
            self.assertLessEqual(receipt["received_monotonic"], time.monotonic())
            self.assertEqual(self.controller.operator_pause_generation, operator)
            self.assertTrue(self.controller.pause_requested)
            self.assertIsNone(self.controller._mission_lease)
            fake.value = copy.deepcopy(receipt["result"]["state"])
            answer_binding = self.binding()
            answered = self.call(answer_binding, "answer_interrupt", choice="NO",
                                 interrupt_request_id=receipt["request"]["id"])
            self.assertTrue(answered["published"], answered)
            self.assertEqual(answered["result"]["status"], "answer_delivered")
            self.assertEqual(answered["request"]["frame"], fake.value["frame"])
            self.assertEqual(answered["request"]["choice"], "NO")
            self.assertEqual(self.controller.operator_pause_generation, operator)
            self.assertEqual(len(control.delivered), 2)
            self.assertEqual(self.controller.control_admitted, {})

    def test_all_original_bindings_reject_stale_caller_before_callback(self):
        changes = {"expected_generation": self.controller.pause_generation + 1, "expected_operator_generation": 1,
                   "expected_controller_boot_id": "other", "expected_session": "other",
                   "expected_revision": 999, "expected_boundary_id": "other",
                   "expected_takeover_generation": 1, "expected_pause_origin": "human",
                   "expected_control_generation": 1}
        with FakeBridge(self.controller) as fake:
            binding = self.prepare(fake)
            for field, value in changes.items():
                with self.subTest(field=field):
                    calls = []
                    receipt = self.call(binding, **{field: value}, preflight=lambda *args: calls.append(args))
                    self.assert_unpublished(receipt)
                    self.assertEqual(calls, [])

    def test_fresh_observe_rejects_changed_source_or_native_authority(self):
        for field in ("revision", "session", "boundary", "takeover_generation", "pause_origin"):
            with self.subTest(field=field), FakeBridge(self.controller) as fake:
                binding = self.prepare(fake)
                if field == "boundary":
                    fake.value["boundary"]["control_generation"] += 1
                elif field in {"revision", "takeover_generation"}:
                    fake.value[field] += 1
                elif field == "session":
                    fake.value[field] = "other-world"
                else:
                    fake.value[field] = "none" if binding["expected_pause_origin"] != "none" else "host"
                calls = []
                receipt = self.call(binding, preflight=lambda *args: calls.append(args))
                self.assert_unpublished(receipt)
                self.assertEqual(calls, [])

    def test_debug_unadvertised_and_wrong_answer_owner_are_rejected(self):
        with FakeBridge(self.controller) as fake:
            for boundary, kind, payload in (("debug_prompt", "continue_debug_once", {}),
                    ("activity_poll", "answer_interrupt", {"choice": "YES", "interrupt_request_id": "wrong"}),
                    ("interrupt_confirmation", "answer_interrupt", {"choice": "YES", "interrupt_request_id": "wrong"})):
                with self.subTest(boundary=boundary):
                    binding = self.prepare(fake, boundary, owner="owner" if boundary == "interrupt_confirmation" else None)
                    self.assert_unpublished(self.call(binding, kind, **payload))

    def test_image_mismatch_and_callback_failure_prove_no_publication(self):
        with FakeBridge(self.controller) as fake:
            binding = self.prepare(fake)
            calls = []
            receipt = self.call(binding, expected_image_sha256="0" * 64,
                                preflight=lambda *args: calls.append(args))
            self.assert_unpublished(receipt)
            self.assertEqual(calls, [])
            def failure(*args):
                raise RuntimeError("reservation failed")
            receipt = self.call(self.binding(), preflight=failure)
            self.assert_unpublished(receipt)
            self.assertIn("reservation failed", receipt["result"]["error"])
            self.assertIsNotNone(receipt["preflight"])

    def test_charged_preflight_cannot_absorb_pause_deadline_or_changed_evidence(self):
        for fault in ("pause", "stop", "deadline", "image", "source", "sentinel", "competing_command"):
            with self.subTest(fault=fault), FakeBridge(self.controller) as fake:
                binding = self.prepare(fake)
                charged = []
                clock = [time.monotonic()]
                binding["deadline_monotonic"] = clock[0] + 2
                def preflight(observed, received):
                    charged.append(observed)
                    if fault == "pause": self.controller.pause()
                    elif fault == "stop": self.controller.stop_input()
                    elif fault == "deadline": clock[0] = binding["deadline_monotonic"] + 1
                    elif fault == "image": (self.controller.bridge / observed["frame"]).write_bytes(b"changed")
                    elif fault == "source": self.controller.state["revision"] += 1
                    elif fault == "sentinel": (self.controller.bridge / "pause").unlink()
                    elif fault == "competing_command": self.controller._command_work += 1
                try:
                    with patch("harness.controller.time.monotonic", side_effect=lambda: clock[0]):
                        receipt = self.call(binding, preflight=preflight,
                            expected_image_sha256=hashlib.sha256(b"informing image").hexdigest())
                    self.assert_unpublished(receipt)
                    self.assertEqual(len(charged), 1)
                finally:
                    if fault == "competing_command": self.controller._command_work -= 1
                    self.controller.stop_input()

    def test_command_lock_wait_expires_before_causally_releasing_writer(self):
        with FakeBridge(self.controller) as fake:
            binding = self.prepare(fake)
            self.controller.command_lock.acquire()
            try:
                with ThreadPoolExecutor(1) as pool:
                    future = pool.submit(self.call, binding, deadline_monotonic=time.monotonic() + 0.05)
                    try:
                        receipt = future.result(timeout=0.5)
                    except TimeoutError:
                        self.controller.command_lock.release()
                        future.result(timeout=2)
                        self.fail("recovery waited for writer release beyond original deadline")
                    self.assertTrue(self.controller.command_lock.locked())
                    self.assert_unpublished(receipt)
            finally:
                if self.controller.command_lock.locked(): self.controller.command_lock.release()

    def test_unknown_delivery_keeps_pending_identity_and_cannot_replay(self):
        with FakeBridge(self.controller) as fake, ControlBridge(self.controller, publish=False) as control:
            binding = self.prepare(fake)
            receipt = self.call(binding, timeout=0.06)
            self.assertTrue(receipt["published"], receipt)
            self.assertEqual(receipt["result"]["status"], "unknown")
            self.assertIsNone(receipt["received_monotonic"])
            self.assertEqual(self.controller.control_pending, receipt["request"])
            self.assertEqual(read_json(self.controller.control_admissions / f'{receipt["request"]["id"]}.json'), receipt["request"])
            duplicate = self.call(self.binding())
            self.assertFalse(duplicate["published"])
            self.assertEqual(duplicate["result"]["status"], "controller_error")
            self.assertEqual(len(control.requests), 1)
            self.assertEqual(self.controller.control_unknown_outcomes[0]["request"], receipt["request"])

    def test_original_deadline_bounds_native_wait_before_releasing_claim(self):
        claimed = threading.Event()
        release = threading.Event()
        def hold_claim(*args):
            claimed.set()
            if not release.wait(2):
                raise AssertionError("test failed to release native claim")
        with FakeBridge(self.controller) as fake, ControlBridge(self.controller, before_gate=hold_claim) as control:
            binding = self.prepare(fake)
            with ThreadPoolExecutor(1) as pool:
                future = pool.submit(self.call, binding, timeout=1,
                                     deadline_monotonic=time.monotonic() + 0.1)
                try:
                    self.assertTrue(claimed.wait(0.5))
                    receipt = future.result(timeout=0.5)
                    self.assertFalse(release.is_set())
                    self.assertTrue(receipt["published"], receipt)
                    self.assertEqual(receipt["result"]["status"], "unknown")
                    self.assertEqual(self.controller.control_pending, receipt["request"])
                except TimeoutError:
                    self.fail("native wait renewed the original mission deadline")
                finally:
                    release.set()
                future.result(timeout=2)
            self.assertEqual(len(control.requests), 1)

    def test_control_slot_and_lease_are_not_mission_recovery_authority(self):
        with FakeBridge(self.controller) as fake:
            binding = self.prepare(fake)
            self.controller.control_lock.acquire()
            try:
                self.assert_unpublished(self.call(binding))
            finally:
                self.controller.control_lock.release()
            self.controller._mission_lease = object()
            self.assert_unpublished(self.call(binding))
            self.controller._mission_lease = None

    def test_pause_after_durable_admission_and_deadline_at_atomic_publication_win(self):
        for fault in ("admission_pause", "publication_deadline"):
            with self.subTest(fault=fault), FakeBridge(self.controller) as fake:
                binding = self.prepare(fake)
                clock = [time.monotonic()]
                binding["deadline_monotonic"] = clock[0] + 2
                charged = []
                def publish(path, value, **callbacks):
                    if path.parent == self.controller.control_admissions:
                        self.assertFalse(self.controller.data_lock._is_owned())
                        atomic_json(path, value, **callbacks)
                        if fault == "admission_pause": self.controller.pause()
                    elif path.name == "control.json":
                        check = callbacks["before_publish"]
                        def before_publish():
                            clock[0] = binding["deadline_monotonic"] + 1
                            check()
                        atomic_json(path, value, before_publish=before_publish,
                                    on_publish=callbacks["on_publish"])
                    else:
                        atomic_json(path, value, **callbacks)
                with patch("harness.controller.atomic_json", side_effect=publish), patch(
                        "harness.controller.time.monotonic", side_effect=lambda: clock[0]):
                    receipt = self.call(binding, preflight=lambda *args: charged.append(args))
                self.assert_unpublished(receipt)
                self.assertEqual(len(charged), 1)
                self.assertIsNotNone(receipt["request"])
                self.assertEqual(self.controller.control_admitted, {})
                self.assertIsNone(self.controller.control_pending)
                self.assertEqual(self.controller.control_unknown_outcomes, [])
                self.controller.stop_input()

    def test_duplicate_during_callback_never_enters_second_writer(self):
        entered = threading.Event()
        release = threading.Event()
        with FakeBridge(self.controller) as fake, ControlBridge(self.controller) as control:
            binding = self.prepare(fake)
            def preflight(*args):
                entered.set()
                self.assertTrue(release.wait(2))
            with ThreadPoolExecutor(2) as pool:
                first = pool.submit(self.call, binding, preflight=preflight)
                self.assertTrue(entered.wait(1))
                try:
                    second = pool.submit(self.call, binding, deadline_monotonic=time.monotonic() + 0.05)
                    self.assert_unpublished(second.result(timeout=0.5))
                    self.assertEqual(control.requests, [])
                finally:
                    release.set()
                self.assertEqual(first.result(timeout=2)["result"]["status"], "prompt_opened")
            self.assertEqual(len(control.requests), 1)

    def test_terminal_receipt_clock_precedes_later_reconciliation_and_retention(self):
        clock = [time.monotonic()]
        seen = []
        reconcile = self.controller._reconcile_control
        def delayed(response=None, **kwargs):
            result = reconcile(response, **kwargs)
            if result is not None and result["status"] == "prompt_opened":
                seen.append(clock[0])
                clock[0] += 1
            return result
        with FakeBridge(self.controller) as fake, ControlBridge(self.controller):
            binding = self.prepare(fake)
            with patch("harness.controller.time.monotonic", side_effect=lambda: clock[0]), patch.object(
                    self.controller, "_reconcile_control", side_effect=delayed):
                receipt = self.call(binding)
            self.assertEqual(receipt["result"]["status"], "prompt_opened")
            self.assertEqual(receipt["received_monotonic"], seen[0])
            self.assertLess(receipt["received_monotonic"], clock[0])

    def test_postpublication_storage_failure_keeps_published_unknown_identity(self):
        with FakeBridge(self.controller) as fake, ControlBridge(self.controller, publish=False):
            binding = self.prepare(fake)
            def publish(path, value, **callbacks):
                atomic_json(path, value, **callbacks)
                if path.name == "control.json":
                    raise OSError("directory fsync failed after publication")
            with patch("harness.controller.atomic_json", side_effect=publish):
                receipt = self.call(binding)
            self.assertTrue(receipt["published"], receipt)
            self.assertEqual(receipt["result"]["status"], "controller_error")
            self.assertEqual(self.controller.control_pending, receipt["request"])
            self.assertEqual(self.controller.control_admitted[receipt["request"]["id"]], receipt["request"])
            self.assertEqual(self.controller.control_unknown_outcomes[0]["request"], receipt["request"])
            self.assertIsNone(receipt["received_monotonic"])

    def test_malformed_private_arguments_are_rejected_before_observe_or_callback(self):
        with FakeBridge(self.controller) as fake:
            binding = self.prepare(fake)
            count = len(fake.requests)
            for change in ({"deadline_monotonic": True}, {"deadline_monotonic": float("inf")},
                    {"deadline_monotonic": float("nan")}, {"expected_generation": True},
                    {"expected_control_generation": True}, {"expected_image_sha256": "bad"},
                    {"preflight": 3}, {"logical_action_id": ""}, {"timeout": True}, {"choice": "YES"}):
                with self.subTest(change=change):
                    self.assert_unpublished(self.call(binding, **change))
            self.assertEqual(len(fake.requests), count)

    def test_public_recover_still_records_operator_pause_and_json_cannot_select_mission(self):
        with FakeBridge(self.controller) as fake, ControlBridge(self.controller):
            binding = self.prepare(fake)
            before = self.controller.operator_pause_generation
            result = self.controller.recover("request_interrupt", expected_session=binding["expected_session"],
                expected_control_generation=binding["expected_control_generation"])
            self.assertEqual(result["status"], "prompt_opened")
            self.assertEqual(self.controller.operator_pause_generation, before + 1)
            self.assertEqual(self.controller.execute("recover_mission")["status"], "controller_error")

    def test_terminal_receipt_survives_terminal_journal_failure_without_unknown_ack(self):
        record = self.controller._record
        def failed_terminal(request, outcome):
            if request.get("kind") == "request_interrupt" and outcome.get("status") == "prompt_opened":
                raise OSError("terminal journal unavailable")
            return record(request, outcome)
        with FakeBridge(self.controller) as fake, ControlBridge(self.controller):
            binding = self.prepare(fake)
            with patch.object(self.controller, "_record", side_effect=failed_terminal):
                receipt = self.call(binding)
            self.assertTrue(receipt["published"], receipt)
            self.assertEqual(receipt["result"], read_json(self.controller.bridge / "control-response.json"))
            self.assertEqual(receipt["result"]["status"], "prompt_opened")
            self.assertIsNotNone(receipt["received_monotonic"])
            self.assertEqual(self.controller.control_unknown_outcomes, [])
            self.assertTrue(self.controller.frozen)
            self.assertIn("terminal journal", self.controller.transport_error)

    def test_terminal_receipt_survives_authority_persistence_failure_before_accept(self):
        failed = []
        def fail_once(path, value, **callbacks):
            response = read_json(self.controller.bridge / "control-response.json")
            if path.name == "authority.json" and response is not None and not failed:
                failed.append(True)
                raise OSError("terminal authority write unavailable")
            return atomic_json(path, value, **callbacks)
        with FakeBridge(self.controller) as fake, ControlBridge(self.controller):
            binding = self.prepare(fake)
            with patch("harness.controller.atomic_json", side_effect=fail_once):
                receipt = self.call(binding)
            self.assertTrue(failed)
            self.assertEqual(receipt["result"], read_json(self.controller.bridge / "control-response.json"))
            self.assertEqual(receipt["result"]["status"], "prompt_opened")
            self.assertIsNotNone(receipt["received_monotonic"])
            self.assertEqual(self.controller.control_unknown_outcomes, [])
            self.assertTrue(self.controller.frozen)

    def test_correlated_dispatched_progress_does_not_fabricate_an_unknown(self):
        seen = threading.Event()
        reconcile = self.controller._reconcile_control
        def accepted(response=None, **kwargs):
            value = reconcile(response, **kwargs)
            if value is not None and value["status"] == "dispatched":
                seen.set()
            return value
        def progress(control, request):
            value = copy.deepcopy(self.controller.state)
            value["revision"] += 1
            value["boundary"]["control_generation"] = request["control_generation"] + 1
            atomic_json(self.controller.bridge / "control-response.json", dict(protocol=4, id=request["id"],
                status="dispatched", error="", state=value))
            self.assertTrue(seen.wait(1))
        with FakeBridge(self.controller) as fake, ControlBridge(self.controller, after_commit=progress):
            binding = self.prepare(fake)
            with patch.object(self.controller, "_reconcile_control", side_effect=accepted):
                receipt = self.call(binding)
            self.assertTrue(seen.is_set())
            self.assertEqual(receipt["result"]["status"], "prompt_opened")
            self.assertEqual(self.controller.control_unknown_outcomes, [])
            self.assertIsNone(self.controller.control_pending)

    def test_native_ttl_expiry_before_atomic_visibility_is_not_unknown_delivery(self):
        with FakeBridge(self.controller) as fake:
            binding = self.prepare(fake)
            wall = [time.time()]
            def delayed_stage(path, value, **callbacks):
                if path.name == "control.json":
                    wall[0] += 2.15
                return atomic_json(path, value, **callbacks)
            with patch("harness.controller.time.time", side_effect=lambda: wall[0]), patch(
                    "harness.controller.atomic_json", side_effect=delayed_stage):
                receipt = self.call(binding)
            self.assert_unpublished(receipt)
            self.assertIn("native", receipt["result"]["error"].lower())
            self.assertEqual(self.controller.control_unknown_outcomes, [])

    def test_admission_journal_stall_does_not_block_pause_revocation(self):
        entered, release, revoked = threading.Event(), threading.Event(), threading.Event()
        stalled, timeout = threading.Event(), threading.Event()
        record, fsync, pause_file = self.controller._record, os.fsync, self.controller._pause_file
        local = threading.local()
        def retained(request, outcome):
            local.admission = request.get("kind") == "mission_admission"
            try:
                return record(request, outcome)
            finally:
                local.admission = False
        def stalled_fsync(fd):
            if getattr(local, "admission", False) and not stalled.is_set():
                stalled.set()
                entered.set()
                if not release.wait(2): timeout.set()
            return fsync(fd)
        def marked_pause():
            pause_file()
            if self.controller.operator_pause_generation > operator:
                revoked.set()
        with FakeBridge(self.controller) as fake:
            binding = self.prepare(fake)
            operator = self.controller.operator_pause_generation
            with patch.object(self.controller, "_record", side_effect=retained), patch(
                    "harness.controller.os.fsync", side_effect=stalled_fsync), patch.object(
                    self.controller, "_pause_file", side_effect=marked_pause), ThreadPoolExecutor(2) as pool:
                future = pool.submit(self.call, binding)
                self.assertTrue(entered.wait(1))
                pause = pool.submit(self.controller.pause)
                try:
                    self.assertTrue(revoked.wait(0.5), "Pause could not revoke while admission journal was stalled")
                finally:
                    release.set()
                    future.result(timeout=2)
                    pause.result(timeout=2)
            self.assertFalse(timeout.is_set())


if __name__ == "__main__":
    unittest.main()
