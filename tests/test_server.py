"""Real loopback HTTP checks with temporary bridge files, not game acceptance."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch
from http.client import HTTPConnection
import json
import sys
from types import ModuleType
from pathlib import Path
import tempfile
import threading
import time
import unittest

from harness.controller import Controller, read_json
from harness.gameplay.contracts import PlanCandidate
from harness.server import Server
from tests.test_controller import ControlBridge, FakeBridge, recovery_state


class StubRuntime:
    """Boundary fixture only; production must construct the real runtime."""
    def __init__(self, controller):
        self.controller = controller
        self.snapshot = None
        self.calls = []
        self.closed = False

    def command(self, kind, **payload):
        self.calls.append((kind, payload))
        result = {"status": "accepted", "gameplay": self.snapshot}
        if kind == "planning_request":
            result["planning_request"] = None
        return result

    def status(self):
        return self.snapshot

    def pause(self, reason):
        self.calls.append(("pause", {"reason": reason}))
        return self.controller.pause()

    def close(self):
        self.closed = True


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "web").mkdir()
        (self.root / "web" / "index.html").write_text('<meta content="__CONTROLLER_TOKEN__">')
        (self.root / "web" / "app.js").write_text('"use strict";')
        (self.root / "web" / "style.css").write_text('body {}')
        # Functional file/HTTP exchanges allow scheduler and fsync latency.
        # Expiry and responsiveness tests below retain explicit short limits.
        self.controller = Controller(self.root, timeout=2.0)
        runtime_module = ModuleType("harness.runtime")
        runtime_module.GameplayRuntime = StubRuntime
        with patch.dict(sys.modules, {"harness.runtime": runtime_module}):
            self.server = Server(self.controller, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.server.shutdown()
        self.thread.join(1)
        self.server.server_close()
        self.controller.close()
        self.temp.cleanup()

    def request(self, method="GET", path="/api/status", data=None, **headers):
        connection = HTTPConnection("127.0.0.1", self.server.port, timeout=3)
        defaults = {"Host": f"127.0.0.1:{self.server.port}"}
        defaults.update(headers)
        connection.request(method, path, body=data, headers=defaults)
        response = connection.getresponse()
        result = response.status, response.read(), dict(response.getheaders())
        connection.close()
        return result

    def post(self, value, **headers):
        defaults = {"Content-Type": "application/json", "X-CDDA-Token": self.controller.token}
        defaults.update(headers)
        return self.request("POST", "/api/command", json.dumps(value), **defaults)

    def recovery(self, value, **headers):
        defaults = {"Content-Type": "application/json", "X-CDDA-Token": self.controller.token}
        defaults.update(headers)
        return self.request("POST", "/api/recovery", json.dumps(value), **defaults)

    def gameplay(self, value, **headers):
        defaults = {"Content-Type": "application/json", "X-CDDA-Token": self.controller.token}
        defaults.update(headers)
        return self.request("POST", "/api/gameplay", json.dumps(value), **defaults)

    def test_gameplay_lifecycle_status_and_exact_dispatch(self):
        runtime = self.server.gameplay
        self.assertEqual(runtime.calls, [])
        self.assertIsNone(json.loads(self.request()[1])["gameplay"])
        runtime.snapshot = {"run_id": "run", "task": {}, "run": {"state": "planning"},
                            "planner": {"usage_known": False}, "last_receipt": None}
        payloads = [{"kind": "start", "direction": "east", "distance": 2,
                     "expected_session": "shown", "expected_revision": 7},
                    {"kind": "continue", "run_id": "run", "execution_epoch": 0,
                     "expected_session": "shown", "expected_revision": 7},
                    {"kind": "abandon", "run_id": "run", "execution_epoch": 0},
                    {"kind": "planning_request"}]
        for payload in payloads:
            code, body, _ = self.gameplay(payload)
            self.assertEqual(code, 200, body)
            self.assertEqual(json.loads(body)["gameplay"], runtime.snapshot)
            self.assertEqual(runtime.calls[-1], (payload["kind"], {k: v for k, v in payload.items() if k != "kind"}))
        for _ in range(5):
            self.assertEqual(json.loads(self.request()[1])["gameplay"], runtime.snapshot)
        self.assertEqual(len(runtime.calls), len(payloads), "status reads cannot execute gameplay")
        self.assertEqual(self.post({"kind": "pause"})[0], 200)
        self.assertEqual(runtime.calls[-1][0], "pause")
        self.assertTrue(self.controller.pause_requested)

    def test_gameplay_validates_exact_fields_types_and_candidate_version(self):
        start = {"kind": "start", "direction": "east", "distance": 2,
                 "expected_session": "shown", "expected_revision": 7}
        invalid = [{"kind": "resume"}, {**start, "extra": 1}, {"kind": "planning_request", "timeout": 1}]
        invalid.extend({k: v for k, v in start.items() if k != field} for field in start)
        for key, values in {"direction": ["up", None, 1], "distance": [0, 5, True, 1.0, "1"],
                            "expected_session": [None, "", True], "expected_revision": [-1, True, 1.0]}.items():
            invalid.extend({**start, key: value} for value in values)
        invalid += [{"kind": "abandon", "run_id": "run", "execution_epoch": True},
                    {"kind": "plan", "request_id": "request", "candidate": {"schema": "gameplay/2"}},
                    {"kind": "plan", "request_id": "request", "candidate": "{}"}]
        for payload in invalid:
            with self.subTest(payload=payload):
                code, body, _ = self.gameplay(payload)
                self.assertEqual(code, 400)
                result = json.loads(body)
                self.assertEqual(set(result), {"error"}, "ingress errors retain the existing HTTP envelope")
        self.assertEqual(self.server.gameplay.calls, [])

    def test_gameplay_plan_and_planning_request_preserve_runtime_data(self):
        candidate = PlanCandidate("candidate", "task", 1, "plan", 1, 0, "seen", 7,
                                  "outbound", "east", 2, "cardinal", 2, "Visible route is clear").to_dict()
        payload = {"kind": "plan", "request_id": "request-exact", "candidate": candidate}
        self.assertEqual(self.gameplay(payload)[0], 200)
        self.assertEqual(self.server.gameplay.calls[-1], ("plan", {"request_id": "request-exact", "candidate": candidate}))
        for bad_candidate in ({**candidate, "schema": "gameplay/2"}, {**candidate, "extra": 1},
                              {**candidate, "execution_epoch": True}):
            self.assertEqual(self.gameplay({**payload, "candidate": bad_candidate})[0], 400)
        request = {"request_id": "pending-exact", "deadline_ms": 12345,
                   "input": {"task": {}, "packet": {}, "skills": [], "binding": {},
                             "public_context": "bounded public context", "admission_monotonic": 1}}
        result = {"status": "accepted", "gameplay": None, "planning_request": request}
        with patch.object(self.server.gameplay, "command", return_value=result):
            code, body, _ = self.gameplay({"kind": "planning_request"})
            self.assertEqual((code, json.loads(body)), (200, result))
        for reason in ("duplicate candidate", "late candidate", "stale binding"):
            rejected = {"status": "rejected", "error": reason, "gameplay": {"run_id": "retained"}}
            with patch.object(self.server.gameplay, "command", return_value=rejected):
                code, body, _ = self.gameplay(payload)
                self.assertEqual((code, json.loads(body)), (409, rejected))

    def test_gameplay_malformed_json_and_runtime_errors_retain_diagnostics(self):
        headers = {"Content-Type": "application/json", "X-CDDA-Token": self.controller.token}
        for body in ('{"kind":"planning_request","kind":"planning_request"}',
                     '{"kind":"start","distance":NaN}', '[]', '{"kind":'):
            self.assertEqual(self.request("POST", "/api/gameplay", body, **headers)[0], 400)
        self.assertEqual(self.server.gameplay.calls, [])
        with patch.object(self.server.gameplay, "command", side_effect=ValueError("retained diagnostic")):
            code, body, _ = self.gameplay({"kind": "planning_request"})
            self.assertEqual(code, 409)
            result = json.loads(body)
            self.assertEqual(result["status"], "rejected")
            self.assertIn("retained diagnostic", result["error"])
            self.assertIn("gameplay", result)

    def test_gameplay_pause_and_status_do_not_wait_for_task_command(self):
        entered = threading.Event()
        release = threading.Event()

        def blocked(kind, **payload):
            entered.set()
            self.assertTrue(release.wait(2))
            return {"status": "rejected", "error": "Paused", "gameplay": None}

        with patch.object(self.server.gameplay, "command", side_effect=blocked), ThreadPoolExecutor() as pool:
            waiting = pool.submit(self.gameplay, {"kind": "planning_request"})
            try:
                self.assertTrue(entered.wait(1))
                started = time.monotonic()
                self.assertEqual(self.post({"kind": "pause"})[0], 200)
                self.assertEqual(self.request()[0], 200)
                self.assertLess(time.monotonic() - started, 0.2)
                self.assertFalse(waiting.done())
            finally:
                release.set()
            self.assertEqual(waiting.result()[0], 409)

    def test_gameplay_security_and_runtime_rejection(self):
        payload = {"kind": "planning_request"}
        for headers, code in [({"Origin": "null"}, 403), ({"Host": "evil.example"}, 403),
                              ({"Sec-Fetch-Site": "cross-site"}, 403),
                              ({"X-CDDA-Token": "wrong"}, 403), ({"Content-Type": "text/plain"}, 415)]:
            self.assertEqual(self.gameplay(payload, **headers)[0], code)
        self.assertEqual(self.gameplay({**payload, "padding": "x" * 4096})[0], 413)
        self.assertEqual(self.server.gameplay.calls, [])
        result = {"status": "rejected", "error": "stale request", "gameplay": None}
        with patch.object(self.server.gameplay, "command", return_value=result):
            code, body, _ = self.gameplay(payload)
            self.assertEqual((code, json.loads(body)), (409, result))

    def test_shutdown_pauses_and_closes_runtime(self):
        self.server.server_close()
        self.assertEqual(self.server.gameplay.calls[-1][0], "pause")
        self.assertTrue(self.server.gameplay.closed)

    def recovery_payload(self, kind="request_interrupt"):
        state = self.controller.state
        payload = {"kind": kind, "expected_session": state["session"],
                   "expected_control_generation": state["boundary"]["control_generation"]}
        if kind != "request_interrupt":
            payload.update(expected_boundary_id=state["boundary"]["id"],
                           expected_revision=state["revision"], expected_frame=state["frame"])
        if kind == "answer_interrupt":
            payload.update(interrupt_request_id=state["boundary"]["interrupt_request_id"], choice="NO")
        return payload

    def test_run_lease_enforced_on_existing_http_ingress(self):
        with FakeBridge(self.controller) as bridge:
            self.assertEqual(self.post({"kind": "observe"})[0], 200)
            self.assertEqual(self.post({"kind": "resume"})[0], 200)
            current = self.controller.state
            lease = self.controller.acquire_run("http-task", 0, "test-player",
                expected_session=current["session"], expected_revision=current["revision"])
            delivered = len(bridge.delivered)
            for kind, payload in (("key", {"key": "x"}), ("action", {"action": "RIGHT"}),
                                  ("walk", {"direction": "east", "steps": 1}), ("resume", {})):
                with self.subTest(kind=kind):
                    code, body, _ = self.post({"kind": kind, "expected_session": current["session"],
                        "expected_revision": current["revision"], **payload})
                    self.assertEqual(code, 409, body)
            self.assertEqual(len(bridge.delivered), delivered)

            code, body, _ = self.request()
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(body)["run_lease"], {"task_id": "http-task",
                "execution_epoch": 0, "owner": "test-player", "session": current["session"]})
            self.assertEqual(self.post({"kind": "observe"})[0], 200)
            self.assertEqual(self.post({"kind": "goal", "text": "record only"})[0], 200)
            # Public JSON cannot supply an in-process capability or start a run.
            self.assertEqual(self.post({"kind": "action", "action": "RIGHT", "run_lease": {}})[0], 400)
            self.assertEqual(self.post({"kind": "acquire_run"})[0], 409)
            self.assertEqual(self.post({"kind": "pause"})[0], 200)
            self.assertIsNone(self.controller.status()["run_lease"])
            rejected = self.controller.execute_run(lease, action="RIGHT",
                expected_session=current["session"], expected_revision=current["revision"],
                logical_action_id="revoked-http-lease", deadline_monotonic=time.monotonic() + 1)
            self.assertFalse(rejected["published"])
            self.assertNotEqual(rejected["result"]["status"], "ready")
            self.assertEqual(len(bridge.delivered), delivered)
            self.assertEqual(self.post({"kind": "observe"})[0], 200)
            self.assertEqual(self.post({"kind": "resume"})[0], 200)
            self.assertIsNone(self.controller.status()["run_lease"])

    def test_walk_stop_evidence_and_reassessment_through_http(self):
        with FakeBridge(self.controller) as bridge:
            self.assertEqual(self.post({"kind": "observe"})[0], 200)
            self.assertEqual(self.post({"kind": "resume"})[0], 200)
            bridge.value["scene"]["visible_creatures"] = [{"name": "cat", "hostile": False}]
            current = self.controller.state
            code, body, _ = self.post({"kind": "walk", "direction": "east", "steps": 2,
                "expected_session": current["session"], "expected_revision": current["revision"]})
            result = json.loads(body)
            self.assertEqual((code, result["status"], result["steps"]), (409, "stopped", 0))
            self.assertEqual(result["observation_phase"], "pre_step")
            self.assertEqual(result["terminal_response"], result["observation"])
            self.assertEqual(result["observation"]["scene"]["visible_creatures"][0]["name"], "cat")
            self.assertEqual(result["observation"]["frame"], bridge.value["frame"])
            self.assertIsInstance(result["observation_received_monotonic"], float)
            delivered = len(bridge.delivered)
            self.assertTrue(json.loads(self.request()[1])["frozen"])
            self.assertEqual(self.post({"kind": "resume"})[0], 409)
            self.assertEqual(len(bridge.delivered), delivered)
            self.assertEqual(self.post({"kind": "observe"})[0], 200)
            status = json.loads(self.request()[1])
            self.assertFalse(status["frozen"])
            self.assertTrue(status["pause_requested"])
            self.assertEqual(self.post({"kind": "resume"})[0], 200)
            self.assertFalse(json.loads(self.request()[1])["pause_requested"])
            self.assertFalse(any(request["kind"] == "action" for request in bridge.requests))

    def test_recovery_exact_payloads_and_types_before_dispatch(self):
        self.controller.state = recovery_state()
        good = self.recovery_payload()
        invalid = [{}, {"kind": "pause"}, {**good, "extra": 1},
                   {**good, "expected_revision": 1}]
        for key, values in {"expected_session": [None, 1, ""],
                            "expected_control_generation": [True, -1, 0.0, "0"],
                            "timeout": [None, True, 0, -1, 16, float("nan"), float("inf")]}.items():
            invalid.extend({**good, key: value} for value in values)
        for kind in ("answer_interrupt", "continue_debug_once"):
            self.controller.state = recovery_state("interrupt_confirmation", owner="owner")
            full = self.recovery_payload(kind)
            invalid.extend({k: v for k, v in full.items() if k != field}
                           for field in full if field != "kind")
            for field in ("expected_boundary_id", "expected_frame", "expected_revision"):
                invalid.append({**full, field: False})
            if kind == "answer_interrupt":
                invalid.extend([{**full, "choice": "yes"}, {**full, "choice": []},
                                {**full, "interrupt_request_id": None}])
        with patch.object(self.controller, "recover") as recover:
            for payload in invalid:
                with self.subTest(payload=payload):
                    self.assertEqual(self.recovery(payload)[0], 400)
            recover.assert_not_called()

    def test_recovery_security_controls_and_status_evidence(self):
        self.controller.state = recovery_state()
        payload = self.recovery_payload()
        for headers, code in [({"Host": "evil.example"}, 403),
                              ({"Origin": "null"}, 403), ({"Sec-Fetch-Site": "same-site"}, 403),
                              ({"X-CDDA-Token": "wrong"}, 403), ({"Content-Type": "text/plain"}, 415)]:
            self.assertEqual(self.recovery(payload, **headers)[0], code)
        self.assertEqual(self.recovery({**payload, "padding": "x" * 4096})[0], 413)
        for status in ("prompt_opened", "answer_delivered", "dismissal_delivered", "not_applicable",
                       "rejected", "unknown", "controller_error", "dispatched"):
            evidence = {"status": status, "id": "control-id", "error": "retained", "detail": {"frame_ok": False}}
            with patch.object(self.controller, "recover", return_value=evidence) as recover:
                code, body, _ = self.recovery(payload)
                self.assertEqual(code, 200 if status in {"prompt_opened", "answer_delivered", "dismissal_delivered", "not_applicable"} else 409)
                self.assertEqual(json.loads(body), evidence)
                recover.assert_called_once_with("request_interrupt", expected_session=payload["expected_session"],
                                                expected_control_generation=payload["expected_control_generation"])

    def test_recovery_http_round_trip_and_stale_authority(self):
        self.controller.state = recovery_state()
        stale = self.recovery_payload()
        with ControlBridge(self.controller) as bridge:
            code, body, _ = self.recovery(stale)
            self.assertEqual(code, 200, body)
            self.assertEqual(json.loads(body)["status"], "prompt_opened")
            self.assertEqual(self.recovery(stale)[0], 409)
            answer = self.recovery_payload("answer_interrupt")
            self.assertEqual(self.recovery({**answer, "interrupt_request_id": "wrong"})[0], 409)
            code, body, _ = self.recovery(answer)
            self.assertEqual((code, json.loads(body)["status"]), (200, "answer_delivered"))
            self.assertTrue(self.controller.pause_requested)
            self.assertEqual(len(bridge.delivered), 2)
        self.controller.state = recovery_state("debug_prompt")
        expected = self.recovery_payload("continue_debug_once")
        for change in ({"expected_frame": "old.png"}, {"expected_revision": 99},
                       {"expected_boundary_id": "old"}, {"expected_control_generation": 99}):
            self.assertEqual(self.recovery({**expected, **change})[0], 409)
        with ControlBridge(self.controller):
            self.assertEqual(self.recovery(expected)[0], 200)

    def test_recovery_missing_capture_and_unresolved_slot_remain_visible(self):
        self.controller.state = recovery_state()
        self.controller.state["frame_ok"] = False
        self.assertEqual(self.recovery(self.recovery_payload())[0], 409)
        self.controller.state = recovery_state()
        code, body, _ = self.recovery({**self.recovery_payload(), "timeout": 0.03})
        self.assertEqual((code, json.loads(body)["status"]), (409, "unknown"))
        status = json.loads(self.request()[1])
        self.assertIsNotNone(status["control_pending"])
        self.assertEqual(len(status["control_unknown_outcomes"]), 1)
        self.assertEqual(self.recovery(self.recovery_payload())[0], 409)
        self.assertEqual(self.post({"kind": "pause"})[0], 200)

    def test_pause_and_duplicate_recovery_while_control_writer_is_active(self):
        entered = threading.Event()
        release = threading.Event()
        self.controller.state = recovery_state("debug_prompt")
        payload = {**self.recovery_payload("continue_debug_once"), "timeout": 1.5}
        def hold(bridge, request):
            entered.set()
            self.assertTrue(release.wait(2))
        with ControlBridge(self.controller, before_gate=hold) as bridge, ThreadPoolExecutor() as pool:
            recovering = pool.submit(self.recovery, payload)
            try:
                self.assertTrue(entered.wait(1))
                self.assertEqual(self.recovery(payload)[0], 409)
                self.assertEqual(self.post({"kind": "pause"})[0], 200)
                self.assertFalse(recovering.done())
            finally:
                release.set()
            code, body, _ = recovering.result()
            self.assertEqual((code, json.loads(body)["status"]), (409, "rejected"))
            self.assertEqual(bridge.delivered, [])

    def test_only_explicit_observe_after_expiry_reconciles_http_recovery(self):
        self.controller.state = recovery_state("debug_prompt")
        payload = {**self.recovery_payload("continue_debug_once"), "timeout": 0.04}
        with ControlBridge(self.controller, publish=False) as control:
            self.assertEqual(self.recovery(payload)[0], 409)
            original = self.controller.control_pending.copy()
            with FakeBridge(self.controller) as ordinary:
                ordinary.value = recovery_state("debug_prompt")
                self.assertEqual(self.post({"kind": "observe"})[0], 200)
                self.assertIsNotNone(json.loads(self.request()[1])["control_pending"])
                time.sleep(max(0, (original["deadline_ms"] - time.time() * 1000) / 1000 + 0.02))
                self.assertIsNotNone(json.loads(self.request()[1])["control_pending"])
                self.assertEqual(self.post({"kind": "observe"})[0], 200)
                status = json.loads(self.request()[1])
                self.assertIsNone(status["control_pending"])
                self.assertEqual(status["control_unknown_outcomes"][0]["request"]["id"], original["id"])
            self.assertEqual(len(control.requests), 1)

    def test_recovery_does_not_wait_for_ordinary_http_request(self):
        entered = threading.Event()
        release = threading.Event()

        def hold_ordinary_response(path, *args, **kwargs):
            if path == self.controller.bridge / "response.json":
                # Publication is complete and pending is set before polling begins.
                # Hold ordinary I/O without holding the controller's data lock.
                entered.set()
                self.assertTrue(release.wait(5), "ordinary response polling was not released")
            return read_json(path, *args, **kwargs)

        with patch("harness.controller.read_json", side_effect=hold_ordinary_response), ThreadPoolExecutor() as pool:
            waiting = pool.submit(self.post, {"kind": "observe", "timeout": self.controller.timeout})
            try:
                self.assertTrue(entered.wait(2), "ordinary request did not reach response polling")
                with self.controller.data_lock:
                    self.controller.state = recovery_state()
                    self.assertIsNotNone(self.controller.pending)
                    original = self.controller.pending.copy()
                with ControlBridge(self.controller):
                    code, data, _ = self.recovery(self.recovery_payload())
                    self.assertEqual((code, json.loads(data)["status"]), (200, "prompt_opened"))
                    self.assertFalse(waiting.done())
                    self.assertEqual(self.controller.pending["id"], original["id"])
                    self.assertEqual(self.post({"kind": "pause"})[0], 200)
            finally:
                release.set()
            waiting.result()

    def test_loopback_bind_and_private_config(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        path = self.controller.bridge / "controller.json"
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(path.read_text())["token"], self.controller.token)
        self.assertEqual(json.loads(path.read_text())["protocol"], 3)

    def test_token_required_and_not_in_url(self):
        self.assertEqual(self.post({"kind": "pause"}, **{"X-CDDA-Token": "wrong"})[0], 403)
        self.assertEqual(self.request("POST", f"/api/command?token={self.controller.token}", '{}', **{"Content-Type": "application/json"})[0], 404)
        self.assertEqual(self.post({"kind": "pause"})[0], 200)

    def test_host_origin_and_fetch_site_rejected(self):
        for headers in ({"Host": "evil.example"}, {"Origin": "https://evil.example"},
                        {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"},
                        {"Sec-Fetch-Site": "same-site"}):
            self.assertEqual(self.request(**headers)[0], 403)
            self.assertEqual(self.post({"kind": "pause"}, **headers)[0], 403)
        origin = f"http://127.0.0.1:{self.server.port}"
        self.assertEqual(self.post({"kind": "pause"}, Origin=origin)[0], 200)

    def test_body_bounds_types_and_paths(self):
        self.assertEqual(self.post({"kind": "goal", "text": "a" * 5000})[0], 413)
        self.assertEqual(self.post({"kind": "pause"}, **{"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.post({"kind": []})[0], 400)
        self.assertEqual(self.post({"kind": "pause", "unexpected": 1})[0], 400)
        self.assertEqual(self.request(path="/../AGENTS.md")[0], 404)
        self.assertEqual(self.request(path="/frame.png")[0], 503)

    def test_recovery_is_not_an_ordinary_http_command(self):
        for kind in ("request_interrupt", "answer_interrupt", "continue_debug_once", "recover"):
            code, data, _ = self.post({"kind": kind})
            self.assertEqual(code, 409)
            self.assertEqual(json.loads(data)["status"], "controller_error")
        self.assertEqual(self.post({"kind": "request_interrupt", "expected_control_generation": 0})[0], 400)
        self.assertFalse((self.controller.bridge / "request.json").exists())
        self.assertFalse((self.controller.bridge / "control.json").exists())

    def test_token_injected_and_security_headers(self):
        code, data, headers = self.request(path="/")
        self.assertEqual(code, 200)
        self.assertIn(self.controller.token.encode(), data)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["Cross-Origin-Resource-Policy"], "same-origin")

    def test_immutable_frame_reference_and_path_validation(self):
        content = b"\x89PNG\r\n\x1a\nframe-one"
        (self.controller.bridge / "frame-123-456-2-1.png").write_bytes(content)
        (self.controller.bridge / "frame.png").write_bytes(b"\x89PNG\r\n\x1a\nframe-two")
        code, data, _ = self.request(path="/frame.png?name=frame-123-456-2-1.png")
        self.assertEqual((code, data), (200, content))
        self.assertEqual(self.request(path="/frame.png?name=../controller.json")[0], 400)

    def test_pause_endpoint_does_not_wait_for_native_exchange(self):
        with ThreadPoolExecutor() as pool:
            waiting = pool.submit(self.post, {"kind": "observe", "timeout": 0.4})
            deadline = time.monotonic() + 1
            while not (self.controller.bridge / "request.json").exists() and time.monotonic() < deadline:
                time.sleep(0.002)
            started = time.monotonic()
            code, data, _ = self.post({"kind": "pause"})
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(data)["status"], "pause_requested")
            self.assertLess(time.monotonic() - started, 0.15)
            self.assertFalse(waiting.done())
            waiting.result()

    def test_goal_is_saved_without_game(self):
        self.assertEqual(self.post({"kind": "goal", "text": "Explore"})[0], 200)
        result = json.loads(self.request()[1])
        self.assertEqual(result["goal"], "Explore")
        self.assertTrue(result["frozen"])
        self.assertEqual(result["connection"], "disconnected")

    def test_cli_uses_http_service_for_status_goal_and_pause(self):
        from harness import __main__ as cli
        for arguments in (["status"], ["goal", "Reach the shelter"], ["pause"]):
            output = StringIO()
            with patch.object(cli, "ROOT", self.root), patch("sys.argv", ["harness", *arguments]), redirect_stdout(output):
                self.assertEqual(cli.main(), 0)
            self.assertIsInstance(json.loads(output.getvalue()), dict)
        self.assertEqual(self.controller.goal, "Reach the shelter")
