"""Owned-process contract tests; never launch a game or run a real process guard."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from harness.native_process import NativeProcess, NativeProcessError
from harness.prepared_app import wrapper_source


class Clock:
    def __init__(self):
        self.now = 10.0

    def __call__(self):
        return self.now


class NativeProcessTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.runtime = self.root / ".runtime"
        self.app = self.runtime / "Cataclysm.app/Contents"
        self.wrapper = self.app / "MacOS/Cataclysm.sh"
        self.native = self.app / "Resources/cataclysm-tiles"
        self.options = self.runtime / "user/config/options.json"
        for directory in (self.wrapper.parent, self.native.parent, self.options.parent,
                          self.runtime / "bridge", self.runtime / "logs"):
            directory.mkdir(parents=True, exist_ok=True)
        self.wrapper.write_text(wrapper_source(self.root))
        self.wrapper.chmod(0o755)
        self.native.write_bytes(b"prepared native fixture, not an executable game")
        self.native.chmod(0o755)
        self.sha = hashlib.sha256(self.native.read_bytes()).hexdigest()
        self.options.write_text(json.dumps([{"name": "FULLSCREEN", "value": "no"},
                                           {"name": "ENABLE_MOUSE", "value": "false"}]))
        self.clock = Clock()
        self.child = Mock(spec=["pid", "poll", "wait", "kill", "terminate", "send_signal"])
        self.child.pid = 1234
        self.child.poll.return_value = None
        self.popen = self.enterContext(patch("harness.native_process.subprocess.Popen", return_value=self.child))
        self.pgrep = self.enterContext(patch("harness.native_process.subprocess.run",
            return_value=subprocess.CompletedProcess([], 1, "", "")))
        self.process = NativeProcess(self.root, self.sha, clock=self.clock)

    def launch(self, deadline=20.0):
        return self.process.launch(deadline_monotonic=deadline, cancelled=lambda: False)

    def assert_no_signals(self):
        for name in ("kill", "terminate", "send_signal"):
            getattr(self.child, name).assert_not_called()

    def test_constructor_and_unlaunched_status_have_no_side_effects(self):
        with patch.object(Path, "open", side_effect=AssertionError("status read disk")):
            state = self.process.status()
        self.assertEqual(state, {"launch_id": None, "pid": None, "running": False,
            "returncode": None, "outcome": "not_launched", "error": None})
        self.popen.assert_not_called()
        self.pgrep.assert_not_called()
        self.child.poll.assert_not_called()

    def test_launch_uses_only_fixed_direct_wrapper_and_project_cwd(self):
        state = self.launch()
        self.popen.assert_called_once_with([str(self.wrapper)], cwd=self.root,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.pgrep.assert_called_once_with(["/usr/bin/pgrep", "-x", "cataclysm-tiles"],
            capture_output=True, text=True, check=False, timeout=1.0)
        self.assertTrue(state["running"])
        self.assertEqual(state["outcome"], "running")
        self.assertEqual(state["pid"], 1234)
        self.assertIsInstance(state["launch_id"], str)
        self.assert_no_signals()

    def test_launch_requires_explicit_callable_cancellation(self):
        with self.assertRaisesRegex(NativeProcessError, "cancelled"):
            self.process.launch(deadline_monotonic=20, cancelled=False)
        self.popen.assert_not_called()
        self.pgrep.assert_not_called()

    def test_launch_cancellation_before_guard_after_guard_and_preparation(self):
        for checks in ([True], [False, True], [False, False, True]):
            with self.subTest(checks=checks):
                result = self.process.launch(deadline_monotonic=20, cancelled=Mock(side_effect=checks))
                self.assertEqual(result["outcome"], "cancelled")
                self.assertEqual(result["launch_id"], None)
                self.popen.assert_not_called()
        self.assert_no_signals()

    def test_cancellation_after_spawn_retains_child_and_never_sends_signals(self):
        result = self.process.launch(deadline_monotonic=20,
            cancelled=Mock(side_effect=[False, False, False, True]))
        self.assertEqual(result["outcome"], "cancelled")
        self.assertTrue(result["running"])
        self.assertEqual(result["launch_id"], self.process.status()["launch_id"])
        self.popen.assert_called_once()
        self.assert_no_signals()

    def test_status_only_polls_owned_handle_and_returns_copies(self):
        state = self.launch()
        self.popen.reset_mock()
        self.pgrep.reset_mock()
        state["pid"] = 999
        state["launch_id"] = "changed"
        with patch.object(Path, "open", side_effect=AssertionError("status read disk")):
            current = self.process.status()
        self.assertEqual(current["pid"], 1234)
        self.assertNotEqual(current["launch_id"], "changed")
        self.popen.assert_not_called()
        self.pgrep.assert_not_called()
        self.assert_no_signals()

    def test_duplicate_live_launch_rejects_without_guard_or_another_child(self):
        self.launch()
        self.pgrep.reset_mock()
        with self.assertRaisesRegex(NativeProcessError, "live owned child"):
            self.launch()
        self.popen.assert_called_once()
        self.pgrep.assert_not_called()

    def test_new_launch_after_exit_gets_new_audit_id(self):
        first = self.launch()
        self.child.poll.return_value = 0
        second = self.launch()
        self.assertNotEqual(first["launch_id"], second["launch_id"])
        self.assertEqual(self.popen.call_count, 2)

    def test_guard_blocks_match_malformed_and_error_without_adoption(self):
        for code, stdout, stderr in ((0, "998\n", ""), (0, "garbage", ""),
                                     (1, "998", ""), (1, "", "warning"),
                                     (2, "", "error"), (-1, "", "")):
            with self.subTest(code=code, stdout=stdout, stderr=stderr):
                self.pgrep.return_value = subprocess.CompletedProcess([], code, stdout, stderr)
                with self.assertRaisesRegex(NativeProcessError, "process guard"):
                    self.launch()
                self.assertEqual(self.process.status()["outcome"], "not_launched")
        self.popen.assert_not_called()
        self.assert_no_signals()

    def test_guard_timeout_and_os_error_fail_closed(self):
        for error in (subprocess.TimeoutExpired("pgrep", 1), OSError("pgrep unavailable")):
            with self.subTest(error=error):
                self.pgrep.side_effect = error
                with self.assertRaisesRegex(NativeProcessError, "process guard"):
                    self.launch()
        self.popen.assert_not_called()

    def test_guard_timeout_is_capped_by_original_remaining_time(self):
        self.launch(10.25)
        self.assertEqual(self.pgrep.call_args.kwargs["timeout"], 0.25)

    def test_invalid_deadlines_reject_before_guard(self):
        for deadline in (True, None, "20", float("nan"), float("inf"), -1, 10 ** 1000):
            with self.subTest(deadline=deadline), self.assertRaises(NativeProcessError):
                self.launch(deadline)
        self.pgrep.assert_not_called()
        self.popen.assert_not_called()

    def test_expired_original_deadline_never_launches(self):
        state = self.launch(10.0)
        self.assertEqual(state["outcome"], "deadline")
        self.pgrep.assert_not_called()
        self.popen.assert_not_called()

    def test_deadline_exhausted_by_guard_is_not_renewed(self):
        def guard(*args, **kwargs):
            self.clock.now = 20.0
            return subprocess.CompletedProcess([], 1, "", "")
        self.pgrep.side_effect = guard
        self.assertEqual(self.launch()["outcome"], "deadline")
        self.popen.assert_not_called()

    def test_deadline_exhausted_by_hash_is_not_renewed(self):
        original = hashlib.sha256

        def digest():
            value = original()
            update = value.update
            result = Mock()
            def advance(data):
                update(data)
                self.clock.now = 20.0
            result.update.side_effect = advance
            result.hexdigest.side_effect = value.hexdigest
            return result
        with patch("harness.native_process.hashlib.sha256", side_effect=digest):
            self.assertEqual(self.launch()["outcome"], "deadline")
        self.popen.assert_not_called()

    def test_deadline_rechecked_after_preparation_before_popen(self):
        def prepared(deadline):
            self.clock.now = deadline
            return self.wrapper
        with patch.object(self.process, "_validate_preparation", side_effect=prepared):
            self.assertEqual(self.launch()["outcome"], "deadline")
        self.popen.assert_not_called()

    def test_deadline_after_popen_retains_live_owned_child(self):
        def spawn(*args, **kwargs):
            self.clock.now = 21.0
            return self.child
        self.popen.side_effect = spawn
        state = self.launch()
        self.assertEqual(state["outcome"], "deadline")
        self.assertTrue(state["running"])
        self.assertEqual(self.process.status()["outcome"], "running")
        with self.assertRaisesRegex(NativeProcessError, "live owned child"):
            self.launch(30.0)
        self.assert_no_signals()

    def test_bad_native_hash_and_invalid_admission_hash_reject(self):
        self.native.write_bytes(b"different binary")
        with self.assertRaisesRegex(NativeProcessError, "SHA256"):
            self.launch()
        for sha in (None, "x" * 64, "abc", self.sha.upper()):
            with self.subTest(sha=sha), self.assertRaises(NativeProcessError):
                NativeProcess(self.root, sha)
        self.popen.assert_not_called()

    def test_native_size_ceiling_rejects_before_hash(self):
        with patch("harness.native_process.MAX_NATIVE_BYTES", 2):
            with self.assertRaisesRegex(NativeProcessError, "size"):
                self.launch()
        self.popen.assert_not_called()

    def test_wrong_root_wrapper_and_changed_wrapper_reject(self):
        for value in (wrapper_source(self.root / "other"), "#!/bin/sh\nexit 0\n", "\ufffd"):
            with self.subTest(value=value):
                self.wrapper.write_text(value)
                with self.assertRaisesRegex(NativeProcessError, "wrapper"):
                    self.launch()
        self.popen.assert_not_called()

    def test_wrapper_byte_and_executable_limits(self):
        for content in (b"x" * (16 * 1024 + 1), b"\xff"):
            self.wrapper.write_bytes(content)
            with self.assertRaisesRegex(NativeProcessError, "wrapper|size"):
                self.launch()
        self.wrapper.write_text(wrapper_source(self.root))
        self.wrapper.chmod(0o644)
        with self.assertRaisesRegex(NativeProcessError, "executable"):
            self.launch()
        self.popen.assert_not_called()

    def test_options_require_exactly_one_fullscreen_no(self):
        for options in ([], {}, [None], [{"name": "FULLSCREEN", "value": "yes"}],
                        [{"name": "FULLSCREEN", "value": "no"}] * 2,
                        [{"name": "FULLSCREEN", "value": False}]):
            with self.subTest(options=options):
                self.options.write_text(json.dumps(options))
                with self.assertRaisesRegex(NativeProcessError, "options|FULLSCREEN"):
                    self.launch()
        self.popen.assert_not_called()

    def test_keyboard_driven_launch_requires_exactly_one_mouse_disabled_option(self):
        for mouse in ([], [{"name": "ENABLE_MOUSE", "value": "true"}],
                      [{"name": "ENABLE_MOUSE", "value": False}],
                      [{"name": "ENABLE_MOUSE", "value": "false"}] * 2):
            with self.subTest(mouse=mouse):
                self.options.write_text(json.dumps([{"name": "FULLSCREEN", "value": "no"}, *mouse]))
                with self.assertRaisesRegex(NativeProcessError, "ENABLE_MOUSE=false"):
                    self.launch()
        self.popen.assert_not_called()

    def test_options_malformed_duplicate_keys_and_size_are_rejected(self):
        for content in (b"not json", b"\xff", b" " * (1024 * 1024 + 1),
                b'[{"name":"FULLSCREEN","value":"yes","value":"no"}]'):
            with self.subTest(size=len(content)):
                self.options.write_bytes(content)
                with self.assertRaises(NativeProcessError):
                    self.launch()
        self.popen.assert_not_called()

    def test_bounded_options_integer_parser_failure_is_native_process_error(self):
        content = '[{"name":"FULLSCREEN","value":"no","number":' + "1" * 5000 + '}]'
        self.options.write_text(content)
        with self.assertRaisesRegex(NativeProcessError, "options JSON"):
            self.launch()
        self.popen.assert_not_called()

    def test_every_owned_path_component_rejects_symlink_substitution(self):
        paths = (self.runtime, self.runtime / "Cataclysm.app", self.app,
                 self.wrapper.parent, self.native.parent, self.runtime / "user",
                 self.options.parent, self.runtime / "bridge", self.runtime / "logs",
                 self.wrapper, self.native, self.options)
        for index, path in enumerate(paths):
            with self.subTest(path=path):
                retained = self.root / f"retained-{index}"
                path.rename(retained)
                path.symlink_to(retained, target_is_directory=retained.is_dir())
                try:
                    with self.assertRaisesRegex(NativeProcessError, "symlink"):
                        self.launch()
                finally:
                    path.unlink()
                    retained.rename(path)
        self.popen.assert_not_called()

    def test_log_target_symlink_and_missing_directory_reject(self):
        (self.runtime / "logs/game.log").symlink_to(self.native)
        with self.assertRaisesRegex(NativeProcessError, "symlink"):
            self.launch()
        (self.runtime / "logs/game.log").unlink()
        (self.runtime / "bridge").rmdir()
        with self.assertRaises(NativeProcessError):
            self.launch()
        self.assertFalse((self.runtime / "bridge").exists())
        self.popen.assert_not_called()

    def test_nonregular_fixed_file_and_nonexecutable_native_reject(self):
        self.native.chmod(0o644)
        with self.assertRaisesRegex(NativeProcessError, "executable"):
            self.launch()
        self.native.chmod(0o755)
        self.options.unlink()
        self.options.mkdir()
        with self.assertRaisesRegex(NativeProcessError, "regular"):
            self.launch()
        self.popen.assert_not_called()

    def test_spawn_error_is_explicit_without_inventing_owned_child(self):
        self.popen.side_effect = OSError("exec denied")
        with self.assertRaisesRegex(NativeProcessError, "exec denied"):
            self.launch()
        self.assertEqual(self.process.status()["outcome"], "not_launched")

    def test_wait_unlaunched_and_invalid_cancellation(self):
        state = self.process.wait_exit(deadline_monotonic=20.0, cancelled=lambda: False)
        self.assertEqual(state["outcome"], "not_launched")
        with self.assertRaises(NativeProcessError):
            self.process.wait_exit(deadline_monotonic=20.0, cancelled=False)
        self.child.wait.assert_not_called()
        self.popen.assert_not_called()
        self.pgrep.assert_not_called()

    def test_cancelled_wait_retains_owned_live_handle(self):
        self.launch()
        state = self.process.wait_exit(deadline_monotonic=20.0, cancelled=lambda: True)
        self.assertEqual(state["outcome"], "cancelled")
        self.assertTrue(state["running"])
        self.child.wait.assert_not_called()
        self.assertEqual(self.process.status()["outcome"], "running")
        self.assert_no_signals()

    def test_wait_intervals_use_original_deadline_and_retain_handle(self):
        self.launch()
        def wait(*, timeout):
            self.clock.now += timeout
            raise subprocess.TimeoutExpired("owned child", timeout)
        self.child.wait.side_effect = wait
        state = self.process.wait_exit(deadline_monotonic=10.25, cancelled=lambda: False)
        self.assertEqual(state["outcome"], "deadline")
        self.assertTrue(state["running"])
        timeouts = [call.kwargs["timeout"] for call in self.child.wait.call_args_list]
        self.assertEqual(len(timeouts), 3)
        self.assertTrue(all(0 < timeout <= 0.1 for timeout in timeouts))
        self.assertAlmostEqual(sum(timeouts), 0.25)
        self.assertEqual(self.process.status()["outcome"], "running")
        def exit_normally(*, timeout):
            self.child.poll.return_value = 0
            return 0
        self.child.wait.side_effect = exit_normally
        settled = self.process.wait_exit(deadline_monotonic=20.0, cancelled=lambda: False)
        self.assertEqual(settled["outcome"], "exited")
        self.assertEqual(settled["returncode"], 0)
        self.popen.assert_called_once()
        self.assert_no_signals()

    def test_wait_checks_cancellation_between_intervals(self):
        self.launch()
        self.child.wait.side_effect = subprocess.TimeoutExpired("owned child", 0.1)
        cancelled = Mock(side_effect=[False, True])
        state = self.process.wait_exit(deadline_monotonic=20.0, cancelled=cancelled)
        self.assertEqual(state["outcome"], "cancelled")
        self.child.wait.assert_called_once_with(timeout=0.1)
        self.assert_no_signals()

    def test_late_owned_wait_completion_preserves_exit_and_reports_deadline(self):
        launched = self.launch()
        def wait(*, timeout):
            self.clock.now = 10.2
            self.child.poll.return_value = 0
            return 0
        self.child.wait.side_effect = wait
        state = self.process.wait_exit(deadline_monotonic=10.1, cancelled=lambda: False)
        self.assertEqual(state["outcome"], "deadline")
        self.assertFalse(state["running"])
        self.assertEqual(state["returncode"], 0)
        self.assertEqual(state["launch_id"], launched["launch_id"])
        self.assertEqual(self.process.status()["outcome"], "exited")
        self.assert_no_signals()

    def test_owned_zero_and_nonzero_exit_are_only_process_facts(self):
        for code in (0, 9, -15):
            with self.subTest(code=code):
                self.process = NativeProcess(self.root, self.sha, clock=self.clock)
                self.child.poll.return_value = None
                self.launch()
                def wait(*, timeout):
                    self.child.poll.return_value = code
                    return code
                self.child.wait.side_effect = wait
                state = self.process.wait_exit(deadline_monotonic=20.0, cancelled=lambda: False)
                self.assertEqual(state["outcome"], "exited")
                self.assertFalse(state["running"])
                self.assertEqual(state["returncode"], code)
                self.assertEqual(set(state), {"launch_id", "pid", "running", "returncode", "outcome", "error"})
        self.assert_no_signals()


if __name__ == "__main__":
    unittest.main()
