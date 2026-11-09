"""Exercise our tool configuration against isolated source and document fixtures."""
import os
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from tools import check, ci

ROOT = Path(__file__).resolve().parents[1]


class DevToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copyfile(ROOT / "pyproject.toml", self.root / "pyproject.toml")
        (self.root / "harness").mkdir()
        self.write("__init__.py", "")
        for package in ("computer", "player", "evaluation", "evaluation/core", "evaluation/cdda", "viewer", "curator",
                        "trace"):
            (self.root / "harness" / package).mkdir()
            self.write(f"{package}/__init__.py", "")
        for module in ("computer/protocol", "computer/ports", "computer/runtime", "computer/channel", "computer/store", "computer/launch", "player/memory", "application", "player_client", "player_tools", "player_mcp", "server", "__main__"):
            self.write(module+".py", "")
        self.write("application.py", "from .computer import runtime\nfrom .player import memory\n")
        self.write("server.py", "import http.server\nfrom .computer import protocol\n")
        self.write("__main__.py", "from . import server\n")

    def write(self, filename, source):
        (self.root / "harness" / filename).write_text(source)

    def lint_imports(self):
        # Give Grimp only this source root, never the real checkout's harness.
        env = dict(os.environ, PYTHONPATH=str(self.root))
        return subprocess.run(
            [str(Path(sys.executable).parent / "lint-imports"), "--config", "pyproject.toml",
             "--no-cache", "--no-logo"], cwd=self.root, env=env,
            capture_output=True, text=True, timeout=30)

    def assert_broken(self, result, *modules):
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("BROKEN", output)
        for module in modules:
            self.assertIn(module, output)

    def test_composition_root_and_http_adapter_are_allowed(self):
        result = self.lint_imports()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        contracts = (ROOT / "pyproject.toml").read_text().count("[[tool.importlinter.contracts]]")
        self.assertIn(f"{contracts} kept, 0 broken", result.stdout)

    def test_player_and_computer_cannot_reach_evaluation(self):
        for source in ("player/memory", "player_tools", "computer/runtime", "server"):
            self.write(source+".py", "from harness.evaluation import core\n")
            self.assert_broken(self.lint_imports(), "harness.evaluation")
            self.write(source+".py", "import http.server\nfrom .computer import protocol\n" if source == "server" else "")

    def test_evaluation_core_cannot_import_a_binding(self):
        self.write("evaluation/core/__init__.py", "from harness.evaluation import cdda\n")
        self.assert_broken(self.lint_imports(), "harness.evaluation.cdda")

    def test_player_adapters_cannot_acquire_executor_directly_or_indirectly(self):
        for source in ("player_client", "player_tools", "player_mcp"):
            self.write(source+".py", "from .computer import runtime\n")
            self.assert_broken(self.lint_imports(), "harness."+source, "harness.computer.runtime")
            self.write(source+".py", "")
        self.write("player_client.py", "from . import helper\n")
        self.write("helper.py", "from .computer import launch\n")
        self.assert_broken(self.lint_imports(), "harness.player_client", "harness.helper")

    def test_player_logic_cannot_acquire_custody_or_network(self):
        for module in ("harness.computer.runtime", "harness.computer.store", "subprocess", "socket", "tools"):
            self.write("player/memory.py", f"import {module}\n")
            self.assert_broken(self.lint_imports(), "harness.player")

    def test_computer_cannot_acquire_semantics_or_adapters(self):
        for module in ("harness.player.memory", "harness.application", "harness.player_client", "harness.server", "tools"):
            self.write("computer/runtime.py", f"import {module}\n")
            self.assert_broken(self.lint_imports(), "harness.computer")

    def test_evaluation_cannot_acquire_custody_or_network(self):
        for module in ("harness.computer.runtime", "harness.computer.channel", "harness.computer.launch",
                       "harness.application", "harness.server", "harness.player_mcp", "harness.player_client",
                       "tools", "http", "urllib", "socket", "subprocess"):
            self.write("evaluation/core/__init__.py", f"import {module}\n")
            self.assert_broken(self.lint_imports(), f"harness.evaluation is not allowed to import {module}")
            self.write("evaluation/core/__init__.py", "")

    def test_viewer_cannot_acquire_custody_or_player_access(self):
        for module in ("harness.computer.runtime", "harness.computer.channel", "harness.computer.launch",
                       "harness.application", "harness.server", "harness.player", "harness.player_client",
                       "harness.player_tools", "harness.player_mcp", "harness.__main__", "tools", "subprocess"):
            self.write("viewer/__init__.py", f"import {module}\n")
            self.assert_broken(self.lint_imports(), f"harness.viewer is not allowed to import {module}")
            self.write("viewer/__init__.py", "")

    def test_server_cannot_depend_on_cli_or_tooling(self):
        for module in ("harness.__main__", "tools"):
            self.write("server.py", f"import {module}\n")
            self.assert_broken(self.lint_imports(), "harness.server")

    def test_ruff_configuration_detects_undefined_name(self):
        self.write("computer/runtime.py", "def value():\n    return unknown_value\n")
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--config", "pyproject.toml",
             "--no-cache", "harness"], cwd=self.root, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("F821", result.stdout)
        self.assertIn("unknown_value", result.stdout)
        # The checker relies on Ruff for parse errors (it has no separate compile step).
        self.write("computer/runtime.py", "def broken(:\n")
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--config", "pyproject.toml",
             "--no-cache", "harness"], cwd=self.root, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("runtime.py", result.stdout)

    def test_markdown_reference_links_and_images_are_checked(self):
        for name in check.REQUIRED_DOCS:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        (self.root / "README.md").write_text(
            "[missing][target]\n\n[target]: docs/missing.md\n\n"
            "![picture][image]\n\n[image]: ../outside.png\n\n"
            "`[code](ignored.md)`\n\n```md\n[example](ignored.md)\n```\n")
        errors = check.check_documents(self.root)
        self.assertEqual(len(errors), 2, errors)
        self.assertTrue(any("docs/missing.md" in error for error in errors))
        self.assertTrue(any("../outside.png" in error for error in errors))

    def checker_commands(self, arguments, fail_command=None, output=None):
        (self.root / "web").mkdir(exist_ok=True)
        (self.root / "web/viewer.js").write_text("export const ready = true;\n")
        executed = []
        output = output if output is not None else io.StringIO()

        def record(command, **kwargs):
            executed.append(command.copy())
            if fail_command is not None and fail_command(command):
                raise subprocess.CalledProcessError(1, command)

        with patch.object(check, "ROOT", self.root), \
                patch.object(check, "check_documents", return_value=[]), \
                patch.object(check.shutil, "which", return_value="/fixture/node"), \
                patch.object(check, "run", side_effect=record), redirect_stdout(output):
            result = check.main(arguments)
        return result, executed, output.getvalue()

    def test_each_profile_runs_its_scope_and_reports_only_what_ran(self):
        # Which lanes each profile runs; the exact commands are the checker's and the manifest's own.
        structural = {"fast", "main"}
        components = set(ci.COMPONENT_TESTS)
        for arguments, profile in ((["--fast"], "fast"), ([], "full"),
                *((["--profile", name], name) for name in ("full", "editorial", "main", *components))):
            with self.subTest(arguments=arguments):
                result, executed, output = self.checker_commands(arguments)
                self.assertEqual(result, 0)
                ran = lambda text: any(text in " ".join(command) for command in executed)  # noqa: E731
                tests = [command for command in executed if "pytest" in command]
                if profile in structural | {"editorial"}:
                    self.assertEqual(tests, [])
                else:
                    targets = ["tests"] if profile == "full" else list(ci.COMPONENT_TESTS[profile])
                    self.assertEqual(len(tests), 1)
                    self.assertEqual(tests[0][-len(targets):], targets)
                self.assertEqual(ran("tests/test_viewer.cjs"), profile not in structural | {"editorial"})
                for common in ("ruff check", "lint-imports", "tools.documents", "tools.evidence verify",
                               "git diff --check", "git diff --cached --check"):
                    self.assertTrue(ran(common), common)
                self.assertEqual("Portable checks passed." in output, profile == "full")
                if profile in {"editorial", *components}:
                    self.assertIn("Full regression" if profile != "editorial" else "full regression", output)
                if profile == "main":
                    self.assertIn("Tests, viewer tests", output)
                self.assertIn("real gameplay", output)

    def test_profiles_reject_fast_combination_and_unknown_names_before_execution(self):
        for arguments in (["--fast", "--profile", "full"], ["--profile", "unknown"]):
            with self.subTest(arguments=arguments), patch.object(check, "run") as commands, \
                    redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()), \
                    self.assertRaises(SystemExit) as error:
                check.main(arguments)
            self.assertEqual(error.exception.code, 2)
            commands.assert_not_called()

    def test_selected_command_failures_propagate_without_success_report(self):
        for profile in ("full", "editorial", "main", "viewer"):
            _, expected, _ = self.checker_commands(["--profile", profile])
            for command in expected:
                with self.subTest(profile=profile, command=command):
                    output = io.StringIO()
                    with self.assertRaises(subprocess.CalledProcessError) as error:
                        self.checker_commands(["--profile", profile],
                                              lambda actual: actual == command, output=output)
                    self.assertEqual(error.exception.cmd, command)
                    self.assertNotIn("checks passed", output.getvalue())
                    self.assertNotIn("tests passed", output.getvalue())

    def test_command_elapsed_is_logged_even_when_subprocess_fails(self):
        output = io.StringIO()
        failure = subprocess.CalledProcessError(2, ["fixture"])
        with patch.object(check.subprocess, "run", side_effect=failure) as process, \
                patch.object(check.time, "perf_counter", side_effect=[10.0, 12.5]), \
                redirect_stdout(output), self.assertRaises(subprocess.CalledProcessError) as error:
            check.run(["fixture"], input=b"source")
        self.assertIs(error.exception, failure)
        process.assert_called_once_with(["fixture"], cwd=check.ROOT, check=True, input=b"source")
        self.assertIn("Command elapsed: 2.50s", output.getvalue())

    def test_failed_command_output_is_kept_and_its_log_path_reported(self):
        output, success = io.StringIO(), io.StringIO()
        script = "import sys; print('first line'); print('assertion detail', file=sys.stderr); sys.exit(3)"
        with patch.object(check, "ROOT", self.root), patch.object(check, "_log_directory", None):
            with redirect_stdout(output), self.assertRaises(subprocess.CalledProcessError) as error:
                check.run([sys.executable, "-c", script])
            with redirect_stdout(success):
                check.run([sys.executable, "-c", "print('ok')"])
        self.assertEqual(error.exception.returncode, 3)
        logs = sorted((self.root / check.CHECK_LOGS).rglob("*.log"))
        self.assertEqual([path.name[:3] for path in logs], ["01-", "02-"])  # one log per command, one run directory
        self.assertEqual(len({path.parent for path in logs}), 1)
        self.assertEqual(logs[0].read_text().splitlines(), ["first line", "assertion detail"])
        self.assertIn("first line", output.getvalue())  # still streamed live
        self.assertIn(f"Full output of the failed command: {logs[0].relative_to(self.root)}", output.getvalue())
        self.assertNotIn("Full output", success.getvalue())

    def test_a_broken_terminal_fails_the_check_instead_of_hanging_it(self):
        class Broken(io.StringIO):  # like `check.py | head` once head exits: the runner's own lines get through first
            def write(self, text):
                if text.startswith(("+ ", "Command elapsed")) or text == "\n":
                    return super().write(text)
                raise BrokenPipeError(32, "Broken pipe")

        # About 1 MB, far more than a pipe buffer, so a reader that stopped draining would block the command.
        script = "import sys\nfor i in range(20000): print('x' * 50, i)"
        outcome = {}

        def attempt():
            with patch.object(check, "ROOT", self.root), patch.object(check, "_log_directory", None), \
                    redirect_stdout(Broken()):
                try:
                    check.run([sys.executable, "-c", script])
                except OSError as error:
                    outcome["error"] = error

        worker = threading.Thread(target=attempt, daemon=True)
        worker.start()
        worker.join(60)
        self.assertFalse(worker.is_alive(), "the checker hung after its terminal broke")
        self.assertIn("could not write command output to the terminal", str(outcome.get("error")))
        log = next((self.root / check.CHECK_LOGS).rglob("*.log")).read_text().splitlines()
        self.assertEqual(len(log), 20000)  # the log kept everything
        self.assertTrue(log[-1].endswith(" 19999"))

    def test_a_descendant_holding_the_output_pipe_cannot_hang_the_checker(self):
        # The command exits at once, but a grandchild keeps the inherited pipe open for much longer.
        # The cut-off note is asserted, not the parent's line, which a loaded machine may schedule late.
        script = ("import subprocess, sys; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(4)']);"
                  " print('parent done')")
        output = io.StringIO()
        with patch.object(check, "ROOT", self.root), patch.object(check, "_log_directory", None), \
                patch.object(check, "DRAIN_SECONDS", 1), redirect_stdout(output):
            started = time.monotonic()
            check.run([sys.executable, "-c", script])
            elapsed = time.monotonic() - started
        self.assertLess(elapsed, 3.5)  # returned before the grandchild released the pipe
        self.assertIn("Output pipe still held by a descendant", output.getvalue())
        log = next((self.root / check.CHECK_LOGS).rglob("*.log")).read_text()
        self.assertIn("still held by a descendant", log)

    def test_lanes_run_at_once_print_whole_outputs_and_fail_after_every_lane_ends(self):
        # Lane a can only pass its wait while lane b's first command runs: no clock is involved.
        flag = self.root / "b-started"
        wait = [sys.executable, "-c", f"import pathlib, sys, time; print('alpha start'); f = pathlib.Path({str(flag)!r})\n"
                                      "for _ in range(600):\n    if f.exists(): break\n    time.sleep(.05)\n"
                                      "else: sys.exit(9)\nprint('alpha end'); sys.exit(4)"]
        mark = [sys.executable, "-c", f"import pathlib, time; print('beta start'); pathlib.Path({str(flag)!r}).touch(); "
                                      "time.sleep(.3); print('beta end')"]
        after = [sys.executable, "-c", "print('gamma start'); print('gamma end')"]
        output = io.StringIO()
        with patch.object(check, "ROOT", self.root), patch.object(check, "_log_directory", None), \
                redirect_stdout(output):
            with self.assertRaises(subprocess.CalledProcessError) as error:
                check.run_lanes({"a": [wait], "b": [mark, after]})
        self.assertEqual(error.exception.returncode, 4)  # 9 would mean the lanes did not overlap
        text = output.getvalue()
        for name in ("alpha", "beta", "gamma"):  # every lane finished, failing lane included
            self.assertIn(f"{name} start\n{name} end\n", text)  # whole, not interleaved
        header = text.index("[a] + ")
        self.assertLess(header, text.index("[a] Full output of the failed command"))  # notes follow the log

    def test_an_interrupted_lane_run_kills_its_commands_and_starts_no_more(self):
        flag = self.root / "started"
        slow = [sys.executable, "-c", f"import pathlib, time; pathlib.Path({str(flag)!r}).touch(); time.sleep(30)"]
        never = [sys.executable, "-c", f"import pathlib; pathlib.Path({str(self.root / 'next')!r}).touch()"]
        real_join, calls = threading.Thread.join, []

        def interrupted_join(thread, timeout=None):
            if not calls:  # the first wait for the lanes is interrupted, once the command is running
                calls.append(thread)
                while not flag.exists():
                    time.sleep(.02)
                raise KeyboardInterrupt
            return real_join(thread, timeout)

        started = time.perf_counter()
        with patch.object(check, "ROOT", self.root), patch.object(check, "_log_directory", None), \
                patch.object(threading.Thread, "join", interrupted_join), redirect_stdout(io.StringIO()), \
                self.assertRaises(KeyboardInterrupt):
            check.run_lanes({"a": [slow, never]})
        self.assertLess(time.perf_counter() - started, 20)  # the 30 s command was killed
        self.assertFalse((self.root / "next").exists())
        self.assertEqual(check._lane_processes, set())

    def test_all_profiles_reject_broken_document_links_before_reporting_success(self):
        for arguments in (["--fast"], [], ["--profile", "editorial"], ["--profile", "main"],
                          ["--profile", "viewer"]):
            output = io.StringIO()
            with self.subTest(arguments=arguments), patch.object(check, "ROOT", self.root), \
                    patch.object(check, "check_documents", return_value=["Broken local link"]), \
                    patch.object(check.shutil, "which", return_value="/fixture/node"), \
                    patch.object(check, "run") as commands, redirect_stdout(output), \
                    self.assertRaisesRegex(ValueError, "Broken local link"):
                check.main(arguments)
            self.assertFalse(any("tools.documents" in call.args[0] for call in commands.call_args_list))
            self.assertNotIn("checks passed", output.getvalue())


if __name__ == "__main__":
    unittest.main()
