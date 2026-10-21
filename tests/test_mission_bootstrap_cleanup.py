"""Resume-only startup cleanup with real writer/ledger and synthetic UI."""
from contextlib import closing
import copy
import json
import sqlite3
import threading
import time
import unittest
from unittest.mock import patch

from harness.gameplay.evidence import EvidenceError
from harness.gameplay.mission_contracts import canonical
from harness.gameplay.mission_ledger import LedgerError, MissionLedger
from harness.mission_runtime import MissionRuntime
from tests.test_mission_creation import MissionCreationFixture


class BootstrapCleanupTests(MissionCreationFixture, unittest.TestCase):
    def untouched_setup(self, operation):
        if operation == "create":
            self.ready()
        else:
            self.create()
            self.save()
            self.exit()
            self.assertEqual(self.launch(identity="second-launch")["state"], "completed")
            self.stage = "load-world"
        self.assertEqual(self.run_request(self.lifecycle("setup", operation))["state"], "partial")
        return copy.deepcopy(self.runtime._ledger.primitive_records()[-1])

    def explicit_abort_and_finish(self, operation):
        resume = self.untouched_setup(operation)
        spent = self.runtime.status()["spent_inputs"]
        deadline = self.runtime.status()["deadline"]
        aborted = self.run_request(self.lifecycle("abort", "exit"))
        self.assertEqual(aborted["state"], "partial", aborted)
        self.assertTrue(aborted["result"]["cleanup_requested"])
        self.assertNotIn("phase", aborted["result"])
        self.assertNotIn("normal_exit", aborted["result"])
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.controller._mission_lease)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertEqual(self.runtime.status()["deadline"], deadline)
        # Model native's host-origin sentinel pause; no user Pause is supplied.
        self.bridge.value["pause_origin"] = "host"
        self.observe("abort-observe")
        self.assertEqual(self.runtime._owned_launch.checkpoint, self.runtime._current)
        exited = self.exit(root="exit-after-abort")
        self.assertTrue(exited["result"]["normal_exit"]["no_save_required"])
        finished = self.run_request(self.lifecycle("finish", "finish"))
        self.assertEqual(finished["result"]["normal_finish"]["disposition"], "stopped")
        self.assertEqual(self.runtime.status()["spent_inputs"], spent + 3)
        self.assertEqual(self.runtime._ledger.primitive(resume["logical_id"]), resume)
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.start()
        self.assertEqual(self.runtime.status()["phase"], "stopped")
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.runtime._owned_launch)
        self.assertIsNone(self.controller._mission_lease)

    def test_explicit_create_resume_only_abort_exits_without_manufactured_failure(self):
        self.explicit_abort_and_finish("create")

    def test_explicit_load_resume_only_abort_exits_without_manufactured_failure(self):
        self.explicit_abort_and_finish("load")

    def test_explicit_abort_rejects_additional_setup_input(self):
        self.untouched_setup("create")
        self.run_request(self.control("world-form", "Create World", parent="setup"))
        spent = self.runtime.status()["spent_inputs"]
        result = self.run_request(self.lifecycle("abort", "exit"))
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertFalse(any(row.get("action") == "QUIT" for row in self.bridge.delivered))

    def test_explicit_abort_rejects_changed_menu_pixels(self):
        self.untouched_setup("create")
        self.bridge.editor_text = "Changed visible menu"
        result = self.run_request(self.lifecycle("abort", "exit"))
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertIsNone(self.runtime._registered_lifecycle.phase)

    def user_pause_during_abort(self, method):
        self.untouched_setup("create")
        original = getattr(self.runtime, method)
        def pause_inside(*args, **kwargs):
            result = original(*args, **kwargs) if method == "_observe_native" else None
            self.runtime.pause("Controlled user Pause during explicit abort")
            return result if method == "_observe_native" else original(*args, **kwargs)
        with patch.object(self.runtime, method, side_effect=pause_inside):
            result = self.run_request(self.lifecycle("abort", "exit"))
        self.assertEqual(result["state"], "paused", result)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertEqual(self.runtime.status()["pause_cause"], "user")
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.controller._mission_lease)
        self.assertFalse(any(row["kind"] == "action" for row in self.bridge.delivered))

    def test_user_pause_during_abort_capture_sends_no_cleanup_input(self):
        self.user_pause_during_abort("_observe_native")

    def test_user_pause_during_abort_revocation_retains_user_cause(self):
        self.user_pause_during_abort("_stop_after_failure")

    def failed_after_resume(self):
        self.ready()
        self.assertEqual(self.run_request(self.lifecycle("create"))["state"], "partial")
        before = self.runtime._current
        # Fault at the same pre-input boundary as native002; no action is sent.
        with patch.object(self.runtime._store, "inspect_current_boundary", return_value=(before, False)), \
                patch.object(self.runtime, "_binding", side_effect=EvidenceError("Controlled pre-input failure")):
            stopped = self.run_request(self.control("world-form", "Create World"))
        self.assertEqual(stopped["state"], "blocked", stopped)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.runtime._registered_lifecycle.candidate)
        # The fixture models native's host-origin pause, without a user Pause.
        self.bridge.value["pause_origin"] = "host"
        return copy.deepcopy(self.runtime._ledger.primitive_records()[0])

    def test_resume_only_failure_normally_exits_finishes_stopped_and_reopens(self):
        resume = self.failed_after_resume()
        self.observe("cleanup-observe")
        self.assertEqual(self.runtime._owned_launch.checkpoint, self.runtime._current)
        self.assertIsNone(self.controller._mission_lease)
        exited = self.exit()
        self.assertTrue(exited["result"]["normal_exit"]["no_save_required"])
        finished = self.run_request(self.lifecycle("finish", "finish"))
        self.assertEqual(finished["result"]["normal_finish"]["disposition"], "stopped")
        self.assertEqual(self.runtime._ledger.primitive(resume["logical_id"]), resume)
        self.assertEqual(self.runtime.status()["spent_inputs"], 4)
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.start()
        self.assertEqual(self.runtime.status()["phase"], "stopped")
        self.assertEqual(self.runtime.status()["spent_inputs"], 4)
        self.assertEqual(self.runtime._ledger.primitive(resume["logical_id"]), resume)
        self.assertIsNone(self.runtime._owned_launch)
        self.assertIsNone(self.controller._mission_lease)

    def test_changed_pixels_cannot_adopt_the_resume_menu(self):
        self.failed_after_resume()
        initial = self.runtime._owned_launch.checkpoint
        self.bridge.editor_text = "A changed menu"
        self.observe("cleanup-observe")
        self.assertEqual(self.runtime._owned_launch.checkpoint, initial)
        exit_result = self.run_request(self.lifecycle("exit", "exit"))
        self.assertEqual(exit_result["state"], "blocked", exit_result)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

    def test_user_pause_cannot_adopt_old_launch_consent(self):
        self.failed_after_resume()
        initial = self.runtime._owned_launch.checkpoint
        self.runtime.pause("User Pause")
        deadline = time.monotonic() + 2
        while self.runtime._pending_pauses and time.monotonic() < deadline:
            threading.Event().wait(0.005)
        self.assertFalse(self.runtime._pending_pauses)
        self.observe("cleanup-observe")
        self.assertEqual(self.runtime._owned_launch.checkpoint, initial)
        exit_result = self.run_request(self.lifecycle("exit", "exit"))
        self.assertEqual(exit_result["state"], "blocked", exit_result)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

    def test_unknown_resume_cannot_become_no_save_cleanup(self):
        self.ready()
        resume = self.controller.resume_mission
        def lost_result(**kwargs):
            raw = resume(**kwargs)
            raw["result"] = {"status": "timeout", "error": "Controlled lost Resume result"}
            return raw
        with patch.object(self.controller, "resume_mission", side_effect=lost_result):
            self.run_request(self.lifecycle("create"))
        self.assertEqual(self.runtime._ledger.primitive_records()[0]["state"], "unknown")
        with self.assertRaisesRegex(LedgerError, "Resume/native correlation|unsettled"):
            self.runtime._ledger.menu_cleanup_resume("launch")
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

    def test_world_action_disqualifies_resume_only_cleanup(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        self.run_request(self.control("world-form", "Create World"))
        with self.assertRaisesRegex(LedgerError, "only one"):
            self.runtime._ledger.menu_cleanup_resume("launch")

    def test_future_exit_cannot_skip_the_current_unfinished_exit_inputs(self):
        resume = self.failed_after_resume()
        self.observe("cleanup-observe")
        begun = self.run_request(self.lifecycle("exit", "exit"))
        self.assertEqual(begun["state"], "partial", begun)
        self.assertEqual(self.runtime._ledger.menu_cleanup_resume("launch", exit_root_id="exit"), resume)
        with self.assertRaisesRegex(LedgerError, "unverified prior exit"):
            self.runtime._ledger.menu_cleanup_resume("launch")

    def test_unexpected_native_revision_cannot_adopt_resume_cleanup(self):
        self.failed_after_resume()
        initial = self.runtime._owned_launch.checkpoint
        self.bridge.value["revision"] += 1
        self.observe("cleanup-observe")
        self.assertEqual(self.runtime._owned_launch.checkpoint, initial)
        stopped = self.run_request(self.lifecycle("exit", "exit"))
        self.assertEqual(stopped["state"], "blocked", stopped)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

    def test_reopen_rejects_borrowed_resume_native_mapping_without_rewriting(self):
        resume = self.failed_after_resume()
        self.observe("cleanup-observe")
        self.exit()
        path, directory = self.runtime._ledger.path, self.runtime._ledger.directory
        self.runtime.close()
        with closing(sqlite3.connect(path)) as db, db:
            receipt = copy.deepcopy(resume["result"])
            native = json.loads(receipt["native_request_json"])
            native["revision"] += 1
            receipt["native_request_json"] = canonical(native)
            db.execute("UPDATE primitives SET result=? WHERE id=?", (canonical(receipt), resume["logical_id"]))
        before = path.read_bytes()
        with self.assertRaisesRegex(LedgerError, "Resume/native correlation"):
            MissionLedger(directory, now=time.time())
        self.assertEqual(path.read_bytes(), before)
