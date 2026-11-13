"""Run the player-host adapter's own SDK and MCP unit lane without provider inference or a game."""
import os
from pathlib import Path
import signal
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
        # Without the host's Node packages every case waits on a child that cannot start, the suite
        # runs to its timeout and its Node processes outlive it. Fail at once and say what to install.
        self.assertTrue((package / "node_modules").is_dir(),
            "tools/player_host/node_modules is missing; install the host's packages first: "
            'npm --userconfig /dev/null --cache "$PWD/.cache/npm" --prefix tools/player_host ci '
            "--ignore-scripts --no-audit --no-fund (docs/setup.md)")
        environment = {**os.environ, "ENACTIVE_TEST_PYTHON": sys.executable}
        # Its own process group, so a timeout stops the per-file Node processes too, not only their parent.
        suite = subprocess.Popen(["node", "--test", *map(str, tests)], cwd=package, env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            output, errors = suite.communicate(timeout=CONFORMANCE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            os.killpg(suite.pid, signal.SIGKILL)
            output, errors = suite.communicate()
            self.fail(f"Player-host adapter tests exceeded {CONFORMANCE_TIMEOUT_SECONDS} seconds. Complete partial TAP:\n"
                + (output or "") + "\nstderr:\n" + (errors or ""))
        self.assertEqual(suite.returncode, 0, output + errors)


if __name__ == "__main__":
    unittest.main()
