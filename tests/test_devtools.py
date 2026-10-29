"""Exercise our tool configuration against isolated source and document fixtures."""
import os
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import check

ROOT = Path(__file__).resolve().parents[1]


class DevToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copyfile(ROOT / "pyproject.toml", self.root / "pyproject.toml")
        (self.root / "harness").mkdir()
        self.write("__init__.py", "")
        for package in ("computer", "player"):
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
        self.assertIn("4 kept, 0 broken", result.stdout)

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

    def test_profiles_keep_exact_test_scope_and_strict_common_checks(self):
        smoke_cases = ["tests/test_computer_protocol.py", "tests/test_computer_runtime.py",
                       "tests/test_player_application.py", "tests/test_server.py"]
        components = {"viewer": ["tests/test_cli.py", *smoke_cases]}
        for arguments, profile in ((["--fast"], "fast"), ([], "full"),
                *((["--profile", name], name) for name in ("full", "editorial", "main-smoke", *components))):
            with self.subTest(arguments=arguments):
                result, executed, output = self.checker_commands(arguments)
                self.assertEqual(result, 0)
                commands = [command for command in executed if "pytest" in command]
                if profile not in {"fast", "editorial"}:
                    targets = ["tests"] if profile == "full" else (
                        smoke_cases if profile == "main-smoke" else components[profile])
                    self.assertEqual(commands, [[sys.executable, "-m", "pytest", "-q", "-n",
                        "0" if profile == "main-smoke" else "4", "--dist",
                        "worksteal" if profile == "full" else "loadfile",
                        "--max-worker-restart=0", "--durations=20", *targets]])
                else:
                    self.assertEqual(commands, [])
                self.assertEqual(any("tools/diagrams.py" in command for command in executed), profile != "fast")
                self.assertEqual(any("tests/test_viewer.cjs" in command for command in executed),
                                 profile not in {"fast", "editorial"})
                governance_commands = [command for command in executed if "tools/governance.py" in command]
                self.assertEqual(governance_commands, [[sys.executable, "tools/governance.py"] +
                                                       (["--development"] if profile == "fast" else [])])
                self.assertIn([sys.executable, "-m", "ruff", "check", "--config", "pyproject.toml",
                               "harness", "tools", "tests"], executed)
                self.assertIn([str(Path(sys.executable).parent / "lint-imports"), "--config",
                               "pyproject.toml", "--no-cache", "--no-logo"], executed)
                self.assertIn(["/fixture/node", "--check", "--input-type=module"], executed)
                self.assertIn([sys.executable, "-m", "tools.documents"], executed)
                self.assertEqual(executed[-2:], [["git", "diff", "--check"],
                                                ["git", "diff", "--cached", "--check"]])
                self.assertEqual("Portable checks passed." in output, profile == "full")
                if profile in {"editorial", "main-smoke", *components}:
                    self.assertIn("Full regression" if profile != "editorial" else "full regression", output)
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
        for profile in ("full", "editorial", "main-smoke", "viewer"):
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

    def test_all_profiles_reject_invalid_python_before_reporting_success(self):
        self.write("computer/runtime.py", "def broken(:\n")
        for arguments in (["--fast"], [], ["--profile", "editorial"], ["--profile", "main-smoke"],
                          ["--profile", "viewer"]):
            output = io.StringIO()
            with self.subTest(arguments=arguments), patch.object(check, "ROOT", self.root), \
                    patch.object(check, "run") as commands, redirect_stdout(output), self.assertRaises(SyntaxError):
                check.main(arguments)
            commands.assert_not_called()
            self.assertNotIn("checks passed", output.getvalue())

    def test_all_profiles_reject_broken_document_links_before_reporting_success(self):
        for arguments in (["--fast"], [], ["--profile", "editorial"], ["--profile", "main-smoke"],
                          ["--profile", "viewer"]):
            output = io.StringIO()
            with self.subTest(arguments=arguments), patch.object(check, "ROOT", self.root), \
                    patch.object(check, "check_documents", return_value=["Broken local link"]), \
                    patch.object(check.shutil, "which", return_value="/fixture/node"), \
                    patch.object(check, "run") as commands, redirect_stdout(output), \
                    self.assertRaisesRegex(ValueError, "Broken local link"):
                check.main(arguments)
            self.assertFalse(any("tools/governance.py" in call.args[0] for call in commands.call_args_list))
            self.assertNotIn("checks passed", output.getvalue())


if __name__ == "__main__":
    unittest.main()
