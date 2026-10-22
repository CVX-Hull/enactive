"""Trusted exit retirement tests; process ownership remains runtime's responsibility."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from harness.controller import Controller, ControlError, MissionLease, atomic_json, read_json


class ExitRetirementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.controller = Controller(Path(self.temp.name))
        self.addCleanup(self.controller.close)
        self.request = {
            "protocol": 6, "id": "native-exit", "kind": "key", "key": "y",
            "session": "owned-session", "revision": 3, "boundary_id": "exit-confirmation",
            "takeover_generation": 0, "authority": self.controller.authority.copy(),
            "frame": "exit.png", "require_exact_frame": True,
            "deadline_ms": int(time.time() * 1000) - 1000,
        }
        self.controller.pending = copy.deepcopy(self.request)
        self.controller._restore_request(self.request, "final input outcome unknown")

    def binding(self, **changes):
        value = {
            "expected_controller_boot_id": self.controller.authority["controller_boot_id"],
            "expected_operator_generation": self.controller.operator_pause_generation,
            "expected_generation": self.controller.pause_generation,
            "expected_request": copy.deepcopy(self.request),
            "launch_id": "owned-launch", "exit_request_id": "mission-exit", "returncode": 0,
        }
        value.update(changes)
        return value

    def retire(self, **changes):
        return self.controller.retire_mission_exit(**self.binding(**changes))

    def assert_rejected(self, **changes):
        pending = copy.deepcopy(self.controller.pending)
        unknowns = copy.deepcopy(self.controller.unknown_outcomes)
        authority = self.controller.authority.copy()
        with self.assertRaises(ControlError):
            self.retire(**changes)
        self.assertEqual(self.controller.pending, pending)
        self.assertEqual(self.controller.unknown_outcomes, unknowns)
        self.assertEqual(self.controller.authority, authority)

    def test_pending_retirement_records_before_clear_and_grants_no_authority(self):
        unknowns = copy.deepcopy(self.controller.unknown_outcomes)
        error = self.controller.transport_error
        generation = self.controller.pause_generation
        record = self.controller._record

        def checked_record(request, receipt):
            self.assertEqual(self.controller.pending, self.request)
            record(request, receipt)

        with patch.object(self.controller, "_record", side_effect=checked_record):
            receipt = self.retire()
        self.assertEqual(receipt, {"launch_id": "owned-launch", "exit_request_id": "mission-exit",
            "native_request_id": "native-exit", "returncode": 0, "retired_pending": True,
            "grants_authority": False})
        self.assertIsNone(self.controller.pending)
        self.assertEqual(self.controller.unknown_outcomes, unknowns)
        self.assertEqual(self.controller.transport_error, error)
        self.assertGreater(self.controller.pause_generation, generation)
        self.assertEqual(read_json(self.controller.bridge / "authority.json"), self.controller.authority)
        self.assertTrue((self.controller.bridge / "pause").exists())
        self.assertTrue(self.controller.pause_requested)
        self.assertTrue(self.controller.frozen)
        self.assertIsNone(self.controller._mission_lease)
        event = json.loads(self.controller.journal.read_text().splitlines()[-1])
        self.assertEqual(event["request"]["kind"], "mission_exit_retirement")
        self.assertEqual(event["outcome"], receipt)

    def test_null_pending_requires_no_request_and_still_records_receipt(self):
        self.controller.pending = None
        receipt = self.retire(expected_request=None)
        self.assertEqual(receipt, {"launch_id": "owned-launch", "exit_request_id": "mission-exit",
            "native_request_id": None, "returncode": 0, "retired_pending": False,
            "grants_authority": False})
        self.assertEqual(self.controller.events[-1]["outcome"], receipt)

    def test_action_pending_is_supported(self):
        self.request.pop("key")
        self.request.update(kind="action", action="QUIT")
        self.controller.pending = copy.deepcopy(self.request)
        self.controller.unknown_outcomes[0]["request"] = copy.deepcopy(self.request)
        self.assertTrue(self.retire()["retired_pending"])

    def test_boot_operator_and_general_generation_are_exact(self):
        for changes in (
            {"expected_controller_boot_id": "other-boot"},
            {"expected_operator_generation": self.controller.operator_pause_generation + 1},
            {"expected_generation": self.controller.pause_generation + 1},
            {"expected_operator_generation": False}, {"expected_generation": True},
        ):
            with self.subTest(changes=changes):
                self.assert_rejected(**changes)

    def test_identity_and_returncode_are_bounded_and_typed(self):
        for field in ("launch_id", "exit_request_id"):
            for invalid in (None, "", "é", "x" * 129, 1, "\n"):
                with self.subTest(field=field, invalid=invalid):
                    self.assert_rejected(**{field: invalid})
        for invalid in (None, False, True, 0.0, 1, -1, "0"):
            with self.subTest(returncode=invalid):
                self.assert_rejected(returncode=invalid)

    def test_session_payload_and_entire_pending_request_must_match(self):
        for changes in ({"session": "other-session"}, {"key": "n"}, {"id": "other-id"},
                        {"revision": 4}, {"authority": {"controller_boot_id": "other", "counter": 0}}):
            request = {**self.request, **changes}
            with self.subTest(changes=changes):
                self.assert_rejected(expected_request=request)
        self.assert_rejected(expected_request=None)
        self.controller.pending = None
        self.assert_rejected()

    def test_stored_request_validator_and_action_key_only_are_required(self):
        for changes in ({"protocol": 3}, {"deadline_ms": False}, {"extra": 1},
                        {"session": ""}, {"key": ""}, {"authority": {}},
                        {"kind": "resume"}, {"kind": "observe"}):
            with self.subTest(changes=changes):
                request = {**self.request, **changes}
                self.controller.pending = copy.deepcopy(request)
                self.controller.unknown_outcomes[0]["request"] = copy.deepcopy(request)
                self.assert_rejected(expected_request=request)

    def test_unexpired_request_cannot_be_retired(self):
        self.request["deadline_ms"] = int(time.time() * 1000) + 60_000
        self.controller.pending = copy.deepcopy(self.request)
        self.controller.unknown_outcomes[0]["request"] = copy.deepcopy(self.request)
        self.assert_rejected()

    def test_exact_deadline_is_expired_and_same_binding_cannot_be_replayed(self):
        binding = self.binding()
        with patch("harness.controller.time.time", return_value=self.request["deadline_ms"] / 1000):
            self.controller.retire_mission_exit(**binding)
        with self.assertRaises(ControlError):
            self.controller.retire_mission_exit(**binding)

    def test_operator_pause_while_waiting_for_data_lock_wins(self):
        binding = self.binding()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.controller.data_lock:
                future = pool.submit(self.controller.retire_mission_exit, **binding)
                deadline = time.monotonic() + 1
                while not self.controller.control_lock.locked() and time.monotonic() < deadline:
                    time.sleep(0.001)
                self.assertTrue(self.controller.control_lock.locked())
                self.controller.pause()
            with self.assertRaises(ControlError):
                future.result(timeout=1)
        self.assertEqual(self.controller.pending, self.request)

    def test_exact_unknown_request_entry_is_required(self):
        for changes in ({"key": "n"}, {"session": "other-session"}, {"id": "other-id"}):
            with self.subTest(changes=changes):
                self.controller.unknown_outcomes[0]["request"] = {**self.request, **changes}
                self.assert_rejected()
        self.controller.unknown_outcomes.clear()
        self.assert_rejected()

    def test_paused_frozen_open_and_unleased_are_required_even_without_pending(self):
        for field, value in (("closed", True), ("frozen", False), ("pause_requested", False),
                             ("_mission_lease", MissionLease("m", 1, "a", "s", 1, 0, "lifecycle")),
                             ("control_pending", {"id": "control"}), ("_command_work", 1)):
            for null in (False, True):
                with self.subTest(field=field, null=null):
                    original = getattr(self.controller, field)
                    setattr(self.controller, field, value)
                    self.controller.pending = None if null else copy.deepcopy(self.request)
                    try:
                        self.assert_rejected(expected_request=None if null else self.request)
                    finally:
                        setattr(self.controller, field, original)

    def test_busy_writer_locks_reject_without_waiting_or_releasing_another_writer(self):
        for lock in (self.controller.command_lock, self.controller.control_lock):
            for null in (False, True):
                self.controller.pending = None if null else copy.deepcopy(self.request)
                lock.acquire()
                try:
                    self.assert_rejected(expected_request=None if null else self.request)
                    self.assertTrue(lock.locked())
                finally:
                    lock.release()
                self.assertFalse(self.controller.command_lock.locked())
                self.assertFalse(self.controller.control_lock.locked())

    def test_every_native_inbox_including_dangling_symlinks_blocks_retirement(self):
        for name in ("request.json", "claimed.json", "control.json", "control-claimed.json"):
            for symlink in (False, True):
                for null in (False, True):
                    with self.subTest(name=name, symlink=symlink, null=null):
                        path = self.controller.bridge / name
                        path.symlink_to("missing-target") if symlink else path.write_text("retained")
                        self.controller.pending = None if null else copy.deepcopy(self.request)
                        try:
                            self.assert_rejected(expected_request=None if null else self.request)
                        finally:
                            path.unlink()

    def test_durable_admission_responses_sources_and_unknown_history_are_preserved(self):
        admission = self.controller.admissions / "native-exit.json"
        atomic_json(admission, self.request)
        response = self.controller.bridge / "response.json"
        response.write_bytes(b"retained native response")
        source = self.controller.bridge / "exit.png"
        source.write_bytes(b"retained source")
        prior = {"status": "unknown", "reason": "older incident", "request": {"id": "older"}}
        self.controller.unknown_outcomes.insert(0, prior)
        unknowns = copy.deepcopy(self.controller.unknown_outcomes)
        files = {path: path.read_bytes() for path in (admission, response, source)}
        self.retire()
        self.assertEqual(self.controller.unknown_outcomes, unknowns)
        self.assertEqual({path: path.read_bytes() for path in files}, files)

    def test_restart_retains_unknown_durable_admission_after_retirement(self):
        atomic_json(self.controller.admissions / "native-exit.json", self.request)
        self.retire()
        self.controller.close()
        reopened = Controller(Path(self.temp.name))
        self.addCleanup(reopened.close)
        self.assertTrue(any(item["request"] == self.request for item in reopened.unknown_outcomes))
        self.assertTrue(reopened.frozen)
        self.assertTrue(reopened.pause_requested)

    def test_revocation_pause_or_journal_failure_does_not_clear_pending(self):
        for method in ("_revoke", "_pause_file", "_record"):
            with self.subTest(method=method):
                with patch.object(self.controller, method, side_effect=OSError("disk failure")):
                    with self.assertRaisesRegex(OSError, "disk failure"):
                        self.retire()
                self.assertEqual(self.controller.pending, self.request)
                self.assertTrue(self.controller.frozen)
                self.assertTrue(self.controller.pause_requested)
                self.assertFalse(self.controller.command_lock.locked())
                self.assertFalse(self.controller.control_lock.locked())

    def test_real_fsync_failure_preserves_pending(self):
        # Authority file, authority directory and journal are distinct barriers.
        for fail_at in (1, 2, 3):
            calls = 0

            def fail_fsync(fd):
                nonlocal calls
                calls += 1
                if calls == fail_at:
                    raise OSError("fsync failure")

            with self.subTest(fail_at=fail_at):
                with patch("harness.controller.os.fsync", side_effect=fail_fsync):
                    with self.assertRaisesRegex(OSError, "fsync failure"):
                        self.retire()
                self.assertEqual(calls, fail_at)
                self.assertEqual(self.controller.pending, self.request)
                self.assertTrue(self.controller.frozen)
                self.assertTrue(self.controller.pause_requested)

    def test_public_command_cannot_invoke_retirement(self):
        binding = self.binding()
        result = self.controller.execute("retire_mission_exit", **binding)
        self.assertEqual(result["status"], "controller_error")
        self.assertEqual(result["error"], "Unknown command")
        self.assertEqual(self.controller.pending, self.request)
        result = self.controller.execute("mission_exit_retirement")
        self.assertEqual(result["status"], "controller_error")
        self.assertEqual(self.controller.pending, self.request)
