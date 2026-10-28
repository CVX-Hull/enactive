"""Exceptional writer shutdown with controlled OS children, never game inputs."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from harness.controller import Controller
from harness.mission_runtime import MissionRuntime
from harness.native_process import NativeProcess
from harness.server import Server


class MissionShutdownTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.controller = Controller(self.root, timeout=.1)
        self.addCleanup(self.controller.close)
        self.runtime = MissionRuntime(self.controller)
        self.addCleanup(self.runtime.close)

    def child(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        def cleanup():
            if child.poll() is None:
                child.kill()
            child.wait(timeout=3)
        self.addCleanup(cleanup)
        process = NativeProcess(self.root, "0" * 64)
        process._child, process._launch_id = child, "owned-fixture"
        self.runtime._native = process
        return child

    def test_settled_writer_revokes_then_closes_owned_native_before_storage(self):
        child = self.child()
        native = self.runtime._native
        events = []
        close = native.close_exceptional
        storage = self.runtime._close_storage
        def exceptional(**kwargs):
            self.assertTrue(self.controller.status()["frozen"])
            self.assertIsNone(self.runtime._active)
            events.append("native")
            return close(**kwargs)
        def close_storage():
            events.append("storage")
            storage()
        with patch.object(native, "close_exceptional", side_effect=exceptional), patch.object(
                self.runtime, "_close_storage", side_effect=close_storage):
            receipt = self.runtime.close()
        self.assertEqual(events, ["native", "storage"])
        self.assertIsNotNone(child.poll())
        self.assertTrue(receipt["writer_settled"])
        self.assertTrue(receipt["native_absence_verified"])
        self.assertEqual(receipt["native_cleanup"]["outcome"], "exceptional_closed")
        self.assertFalse(receipt["normal_exit_verified"])
        self.assertFalse(receipt["acceptance_claimed"])

    def test_persistence_failure_does_not_skip_owned_cleanup(self):
        child = self.child()
        with patch.object(self.runtime, "_apply_pauses", side_effect=OSError("fixture storage failure")):
            receipt = self.runtime.close()
        self.assertIsNotNone(child.poll())
        self.assertTrue(receipt["native_absence_verified"])

    def test_stop_persistence_failure_still_closes_after_in_memory_revocation(self):
        child = self.child()
        with patch.object(self.controller, "_pause_file", side_effect=OSError("disk full")):
            receipt = self.runtime.close()
        self.assertIsNotNone(child.poll())
        self.assertTrue(receipt["input_authority_revoked"])
        self.assertFalse(receipt["input_stop_persistence_confirmed"])
        self.assertTrue(receipt["native_absence_verified"])

    def test_unexpected_stop_failure_before_revocation_preserves_unknown_without_cleanup(self):
        from harness.controller import ControlError
        child = self.child()
        with patch.object(self.controller, "stop_input", side_effect=ControlError("pre-revocation failure")), \
                patch.object(self.runtime, "pause"):
            receipt = self.runtime.close()
        self.assertIsNone(child.poll())
        self.assertFalse(receipt["input_authority_revoked"])
        self.assertFalse(receipt["native_absence_verified"])
        self.assertEqual(receipt["native_cleanup"]["outcome"], "cleanup_unknown")

    def test_lost_native_custody_remains_unknown_without_adoption(self):
        self.runtime._lost_process_custody = ("old-launch",)
        receipt = self.runtime.close()
        self.assertFalse(receipt["native_absence_verified"])
        self.assertEqual(receipt["unresolved_custody_requests"], ["old-launch"])

    def test_blocked_writer_returns_unknown_and_caller_never_races_native_cleanup(self):
        child = self.child()
        entered, release = threading.Event(), threading.Event()
        native = self.runtime._native
        def blocked():
            entered.set()
            release.wait(3)
        with patch.object(self.runtime._registered_reflection, "tick", side_effect=blocked):
            self.assertTrue(entered.wait(1))
            with patch.object(self.runtime._thread, "join"), patch.object(
                    native, "close_exceptional", wraps=native.close_exceptional) as cleanup:
                receipt = self.runtime.close()
                self.assertFalse(receipt["writer_settled"])
                self.assertFalse(receipt["native_absence_verified"])
                cleanup.assert_not_called()
                self.assertIsNone(child.poll())
            release.set()
        self.assertTrue(self.runtime.close()["writer_settled"])

    def test_server_publishes_matching_advisory_shutdown_without_token(self):
        self.runtime.close()
        server = Server(self.controller, 0)
        discovery = json.loads((self.controller.bridge / "controller.json").read_text())
        boot = self.controller.authority["controller_boot_id"]
        self.assertEqual(discovery["controller_boot_id"], boot)
        server.server_close()
        path = self.controller.bridge / f"mission-shutdown-{boot}.json"
        data = json.loads(path.read_text())
        self.assertEqual(data["controller_boot_id"], boot)
        self.assertTrue(data["cleanup"]["writer_settled"])
        self.assertNotIn(self.controller.token, path.read_text())
        self.assertFalse(data["grants_authority"])
