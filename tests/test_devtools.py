"""Exercise our tool configuration against isolated source and document fixtures."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

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
        self.write("controller.py", "import json\n")
        self.write("movement.py", "import typing\n")
        self.write("server.py", "from . import controller\nimport http.server\n")
        self.write("__main__.py", "from . import controller, server\n")
        (self.root / "harness/gameplay").mkdir()
        self.write("gameplay/__init__.py", "")
        self.write("gameplay/evidence.py", "import json\n")

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

    def test_movement_policy_cannot_acquire_io_or_gameplay_dependencies(self):
        for module in ("harness.controller", "harness.gameplay.evidence", "time", "pathlib", "os"):
            with self.subTest(module=module):
                self.write("movement.py", f"import {module}\n")
                self.assert_broken(self.lint_imports(), "harness.movement")

    def test_gameplay_evidence_cannot_dispatch_or_launch_tools(self):
        for module in ("harness.controller", "harness.server", "harness.__main__",
                       "http.client", "urllib.request", "socket", "subprocess", "tools"):
            with self.subTest(module=module):
                self.write("gameplay/evidence.py", f"import {module}\n")
                self.assert_broken(self.lint_imports(), "harness.gameplay")

    def test_direct_controller_dependencies_are_forbidden(self):
        for module in ("harness.server", "harness.__main__", "http.client", "urllib.request",
                       "socket", "tools", "subprocess", "argparse"):
            with self.subTest(module=module):
                self.write("controller.py", f"import {module}\n")
                self.assert_broken(self.lint_imports(), "harness.controller", module.split(".")[0])

    def test_indirect_controller_dependencies_are_forbidden(self):
        self.write("controller.py", "from . import helper\n")
        for module in ("harness.server", "http.client", "tools"):
            with self.subTest(module=module):
                self.write("helper.py", f"import {module}\n")
                self.assert_broken(self.lint_imports(), "harness.controller", "harness.helper")

    def test_server_cannot_depend_on_cli_or_tooling(self):
        for module in ("harness.__main__", "tools"):
            with self.subTest(module=module):
                self.write("server.py", f"import {module}\n")
                self.assert_broken(self.lint_imports(), "harness.server")

    def test_ruff_configuration_detects_undefined_name(self):
        self.write("controller.py", "def value():\n    return unknown_value\n")
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


if __name__ == "__main__":
    unittest.main()
