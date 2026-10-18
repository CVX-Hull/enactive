"""Real HTTP/runtime/controller composition over synthetic native file transport."""
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

from harness.controller import Controller
from harness.server import Server
from test_gameplay_runtime import VisibleBridge, candidate


class GameplayHTTPTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.controller = Controller(Path(temporary.name), timeout=1.5)
        self.addCleanup(self.controller.close)
        bridge = VisibleBridge(self.controller)
        bridge.__enter__()
        self.addCleanup(bridge.__exit__, None, None, None)
        self.server = Server(self.controller, 0)
        self.addCleanup(self.server.server_close)
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.port}"
        self.opener = build_opener(ProxyHandler({}))
        self.assertEqual(self.command("observe")["status"], "ready")
        self.assertEqual(self.command("resume")["status"], "ready")

    def request(self, path, body=None):
        req = Request(self.base + path, data=None if body is None else json.dumps(body).encode(),
                      headers={"Content-Type": "application/json", "X-CDDA-Token": self.controller.token})
        try:
            with self.opener.open(req, timeout=5) as response:
                return json.load(response)
        except HTTPError as error:
            with error:
                return json.load(error)

    def command(self, kind, **payload):
        return self.request("/api/command", {"kind": kind, **payload})

    def gameplay(self, kind, **payload):
        return self.request("/api/gameplay", {"kind": kind, **payload})

    def status(self):
        return self.request("/api/status")

    def expect(self):
        state = self.status()["state"]
        return {"expected_session": state["session"], "expected_revision": state["revision"]}

    def wait(self, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = predicate()
            if result:
                return result
            threading.Event().wait(0.01)
        self.fail(f"HTTP integration wait timed out: {self.status()}")

    def pending(self):
        return self.wait(lambda: self.gameplay("planning_request")["planning_request"])

    def answer(self, request):
        return self.gameplay("plan", request_id=request["request_id"], candidate=candidate(request))

    def test_slow_plan_survives_http_status_polling_and_completes_both_legs(self):
        self.assertIsNone(self.status()["gameplay"])
        self.assertEqual(self.gameplay("start", direction="east", distance=1, **self.expect())["status"], "accepted")
        outbound = self.pending()
        end = time.monotonic() + 3.05
        while time.monotonic() < end:
            self.assertEqual(self.status()["gameplay"]["run"]["state"], "planning")
            threading.Event().wait(0.1)
        self.assertFalse(self.status()["gameplay"]["run"]["fresh"])
        self.assertEqual(self.answer(outbound)["status"], "accepted")
        back = self.pending()
        self.assertEqual(back["input"]["binding"]["expected_stage"], "return")
        self.assertEqual(self.answer(back)["status"], "accepted")
        self.wait(lambda: self.status()["gameplay"]["run"]["state"] == "completed")
        status = self.status()
        self.assertEqual(status["gameplay"]["run"]["progress"]["verified_steps"], 2)
        self.assertEqual(status["state"]["scene"]["position"], [0, 0, 0])
        self.assertIsNone(status["run_lease"])
        self.assertTrue(status["pause_requested"])
        self.assertEqual(status["gameplay"]["last_receipt"]["disposition"], "returned")

    def test_http_pause_rejects_old_return_and_continuation_preserves_waypoint(self):
        self.assertEqual(self.gameplay("start", direction="east", distance=1, **self.expect())["status"], "accepted")
        self.assertEqual(self.answer(self.pending())["status"], "accepted")
        old_return = self.pending()
        self.assertEqual(old_return["input"]["binding"]["expected_stage"], "return")
        self.assertEqual(self.command("pause")["status"], "pause_requested")
        self.wait(lambda: self.status()["gameplay"]["run"]["state"] == "paused")
        stopped = self.status()["gameplay"]
        self.assertEqual(self.answer(old_return)["status"], "rejected")
        self.assertEqual(stopped["run"]["progress"]["verified_steps"], 1)
        self.assertEqual(self.command("observe")["status"], "ready")
        self.assertEqual(self.command("resume")["status"], "ready")
        continued = self.gameplay("continue", run_id=stopped["run_id"],
                                  execution_epoch=stopped["run"]["execution_epoch"], **self.expect())
        self.assertEqual(continued["status"], "accepted", continued)
        remaining = self.pending()
        self.assertEqual(remaining["input"]["binding"]["expected_stage"], "return")
        self.assertEqual(remaining["input"]["task"], old_return["input"]["task"])
        self.assertLess(remaining["input"]["packet"]["remaining_budgets"]["wall_seconds"],
                        old_return["input"]["packet"]["remaining_budgets"]["wall_seconds"])
        self.assertEqual(self.answer(remaining)["status"], "accepted")
        self.wait(lambda: self.status()["gameplay"]["run"]["state"] == "completed")
        self.assertEqual(self.status()["gameplay"]["run"]["progress"]["verified_steps"], 2)
