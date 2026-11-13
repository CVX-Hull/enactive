"""Run the player-host adapter's own SDK and MCP unit lane without provider inference or a game."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
# This bounds the whole expanding subprocess suite, not a gameplay latency goal.
# CI's original 90s watchdog truncated valid later cases; host deadlines have
# separate controlled-clock assertions and must not depend on Python startup.
# Nearly all the time is Python MCP child startup, about 0.3s for each of roughly
# 200 host runs. Node runs each test file in its own process, at most one fewer
# than the CPU count at a time, so the wall time depends on the machine: about 14s
# on 16 CPUs, 38s with three files at a time and 90s with one. The hosted runner
# took 154s beside the other pytest workers while most cases still ran one after
# another, 2.3x the 68s that layout took locally. The bound covers a one-at-a-time
# run at that slowdown (about 205s) and still catches a hang.
CONFORMANCE_TIMEOUT_SECONDS = 360


class PlayerHostAdapterTests(unittest.TestCase):
    def test_adapter_sdk_and_subprocess_units(self):
        package = ROOT / "tools" / "player_host"
        tests = sorted((package / "test").glob("*.test.mjs"))
        self.assertTrue(tests, "Player-host adapter tests are required")
        environment = {**os.environ, "ENACTIVE_TEST_PYTHON": sys.executable}
        try:
            result = subprocess.run(["node", "--test", *map(str, tests)], cwd=package,
                env=environment, capture_output=True, text=True, timeout=CONFORMANCE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as error:
            def decoded(value):
                return value.decode(errors="replace") if isinstance(value, bytes) else value or ""
            self.fail(f"Player-host adapter tests exceeded {CONFORMANCE_TIMEOUT_SECONDS} seconds. Complete partial TAP:\n"
                + decoded(error.output) + "\nstderr:\n" + decoded(error.stderr))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
