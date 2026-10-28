"""Run the locked Pi/MCP conformance lane without provider inference or a game."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PiPlayerHostTests(unittest.TestCase):
    def test_real_sdk_and_subprocess_conformance(self):
        package = ROOT / "tools" / "player_host"
        tests = sorted((package / "test").glob("*.test.mjs"))
        self.assertTrue(tests, "Pi host conformance tests are required")
        environment = {**os.environ, "ENACTIVE_TEST_PYTHON": sys.executable}
        try:
            result = subprocess.run(["node", "--test", *map(str, tests)], cwd=package,
                env=environment, capture_output=True, text=True, timeout=90)
        except subprocess.TimeoutExpired as error:
            def decoded(value):
                return value.decode(errors="replace") if isinstance(value, bytes) else value or ""
            self.fail("Pi conformance exceeded 90 seconds. Complete partial TAP:\n"
                + decoded(error.output) + "\nstderr:\n" + decoded(error.stderr))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
