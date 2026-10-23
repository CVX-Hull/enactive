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

from harness.controller import Controller, read_json, validate_state
from harness.gameplay.contracts import MAX_JSON_BYTES
from tests.test_mission_contracts import admission, claim, request as mission_record
from harness.server import Server
from tests.test_controller import ControlBridge, FakeBridge, recovery_state


class StubRuntime:
    """Boundary fixture only; production must construct the real runtime."""
    def __init__(self, controller):
        self.controller = controller
        self.snapshot = None
        self.calls = []
        self.closed = False

    def command(self, record):
        self.calls.append(("command", record))
        return {"status": "accepted", "mission": self.snapshot}

    def status(self):
        return self.snapshot

    def pause(self, reason, *, cause="user"):
        self.calls.append(("pause", {"reason": reason}))
        return self.controller.pause() if cause == "user" else self.controller.stop_input()

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
        runtime_module = ModuleType("harness.mission_runtime")
        runtime_module.MissionRuntime = StubRuntime
        with patch.dict(sys.modules, {"harness.mission_runtime": runtime_module}):
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

    def test_compact_utf8_codec_does_not_add_a_single_record_cap_to_status_history(self):
        state = FakeBridge(self.controller).value
        state.update(category="UILIST", in_game=False, scene=None,
            actions=["UILIST.UP", "UILIST.DOWN", "CONFIRM", "UILIST.QUIT"],
            ui=dict(purpose="uilist", title="", rows=[dict(id=f"row-{i}", text="x" * 1024,
                enabled=True, hotkey=None) for i in range(32)], selected="row-0", filter=None,
                count=None, coverage="rendered_rows_only"))
        state["boundary"].update(kind="menu", id="large-menu")
        validate_state(state)  # Synthetic data within native row/text bounds.
        for _ in range(32):
            self.controller._record(dict(kind="observe"), dict(status="ready", observation=state))
        status, body, headers = self.request()
        self.assertEqual(status, 200)
        self.assertGreater(len(body), MAX_JSON_BYTES)
        self.assertEqual(int(headers["Content-Length"]), len(body))
        decoded = json.loads(body)
        self.assertEqual(decoded["events"][-1]["outcome"]["observation"]["ui"]["rows"][0]["text"], "x" * 1024)

    def recovery(self, value, **headers):
        defaults = {"Content-Type": "application/json", "X-CDDA-Token": self.controller.token}
        defaults.update(headers)
        return self.request("POST", "/api/recovery", json.dumps(value), **defaults)

    def mission(self, value, **headers):
        defaults = {"Content-Type": "application/json", "X-CDDA-Token": self.controller.token}
        defaults.update(headers)
        return self.request("POST", "/api/mission", json.dumps(value), **defaults)

    def test_failed_bind_does_not_start_a_mission_worker(self):
        with patch("harness.mission_runtime.MissionRuntime") as runtime:
            with self.assertRaises(OSError):
                Server(self.controller, self.server.port)
            runtime.assert_not_called()

    def test_failed_metadata_publication_closes_bound_socket_and_worker(self):
        runtime = StubRuntime(self.controller)
        closed_servers = []
        original_close = Server.server_close
        def tracked_close(server):
            closed_servers.append(server)
            original_close(server)
        with patch("harness.mission_runtime.MissionRuntime", return_value=runtime), \
                patch("harness.server.atomic_json", side_effect=OSError("disk full")), \
                patch.object(Server, "server_close", tracked_close):
            with self.assertRaisesRegex(OSError, "disk full"):
                Server(self.controller, 0)
        self.assertTrue(runtime.closed)
        self.assertEqual(len(closed_servers), 1)
        self.assertEqual(closed_servers[0].socket.fileno(), -1)

    def test_mission_status_and_exact_typed_dispatch(self):
        runtime = self.server.mission
        self.assertEqual(runtime.calls, [])
        self.assertIsNone(json.loads(self.request()[1])["mission"])
        runtime.snapshot = dict(mission_id="mission-test", phase="active", epoch=0, memory_context=None)
        payloads = [dict(schema="mission/11", kind="start", request_id="start-1", admission=admission().to_dict()),
                    mission_record(), dict(schema="mission/11",kind="status",mission_id="mission-test"),
                    dict(schema="mission/11",kind="result",mission_id="mission-test",operation_id="observe-1")]
        for payload in payloads:
            code, body, _ = self.mission(payload)
            self.assertEqual(code, 200, body)
            self.assertEqual(json.loads(body)["mission"], runtime.snapshot)
            self.assertEqual(runtime.calls[-1], ("command", payload))
        for _ in range(5): self.assertEqual(json.loads(self.request()[1])["mission"], runtime.snapshot)
        self.assertEqual(len(runtime.calls), len(payloads), "status reads cannot execute work")
        self.assertEqual(self.post({"kind":"pause"})[0], 200)
        self.assertEqual(runtime.calls[-1][0], "pause")
        self.assertTrue(self.controller.pause_requested)

    def test_mission_validates_exact_fields_types_and_current_version(self):
        observe = mission_record()
        invalid = [dict(observe, schema="mission/1"), dict(observe, extra=1), dict(observe, epoch=True),
                   dict(observe, kind="resume"), {"kind":"planning_request"}, {"kind":"start","direction":"east"}]
        invalid.extend({k:v for k,v in observe.items() if k != field} for field in observe)
        for payload in invalid:
            with self.subTest(payload=payload):
                code, body, _ = self.mission(payload)
                self.assertEqual(code, 400, body)
                self.assertEqual(set(json.loads(body)), {"error"})
        self.assertEqual(self.server.mission.calls, [])

    def test_mission_malformed_json_and_runtime_errors_retain_diagnostics(self):
        headers = {"Content-Type":"application/json", "X-CDDA-Token":self.controller.token}
        for body in ('{"kind":"observe","kind":"observe"}', '{"kind":"observe","epoch":NaN}', '[]', '{"kind":'):
            self.assertEqual(self.request("POST", "/api/mission", body, **headers)[0], 400)
        self.assertEqual(self.server.mission.calls, [])
        with patch.object(self.server.mission, "command", side_effect=ValueError("retained diagnostic")):
            code, body, _ = self.mission(mission_record())
            self.assertEqual(code, 409)
            result = json.loads(body)
            self.assertEqual(result["status"], "rejected")
            self.assertIn("retained diagnostic", result["error"])
            self.assertIn("mission", result)

    def test_mission_rejection_preserves_result_without_retry(self):
        result = {"status":"rejected", "reason":"stale epoch", "mission":{"mission_id":"mission-test"}}
        with patch.object(self.server.mission, "command", return_value=result) as command:
            code, body, _ = self.mission(mission_record())
            self.assertEqual((code, json.loads(body)), (409,result))
            self.assertEqual(command.call_count,1)

    def test_mission_pause_and_status_do_not_wait_for_blocked_command(self):
        entered, release = threading.Event(), threading.Event()
        def blocked(record):
            entered.set()
            self.assertTrue(release.wait(2))
            return {"status":"rejected", "reason":"Paused", "mission":None}
        with patch.object(self.server.mission,"command",side_effect=blocked), ThreadPoolExecutor() as pool:
            waiting=pool.submit(self.mission,mission_record())
            try:
                self.assertTrue(entered.wait(1))
                started=time.monotonic()
                self.assertEqual(self.post({"kind":"pause"})[0],200)
                self.assertEqual(self.request()[0],200)
                self.assertLess(time.monotonic()-started,0.2)
                self.assertFalse(waiting.done())
            finally: release.set()
            self.assertEqual(waiting.result()[0],409)

    def test_mission_security_limits_and_retired_route(self):
        payload=mission_record()
        for headers, code in [({"Origin":"null"},403),({"Host":"evil.example"},403),
                ({"Sec-Fetch-Site":"cross-site"},403),({"X-CDDA-Token":"wrong"},403),({"Content-Type":"text/plain"},415)]:
            self.assertEqual(self.mission(payload,**headers)[0],code)
        self.assertEqual(self.mission({**payload,"padding":"x"*65536})[0],413)
        self.assertEqual(self.post({"kind":"goal","text":"x"*4096})[0],413)
        self.assertEqual(self.request("POST","/api/gameplay",'{}')[0],404)
        self.assertEqual(self.server.mission.calls,[])

    def test_large_valid_mission_record_uses_its_own_bounded_body_limit(self):
        sources=["source"+str(i)+"x"*120 for i in range(8)]
        entry=claim(sources=sources,supports=[dict(sources=sources,claims=[]) for _ in range(8)])
        record=mission_record("remember",entry_type="claim",entry=entry)
        self.assertGreater(len(json.dumps(record)),4096)
        self.assertLess(len(json.dumps(record)),65536)
        self.assertEqual(self.mission(record)[0],200)
        self.assertEqual(self.server.mission.calls[-1],("command",record))

    def test_nonterminal_mission_has_one_observation_and_input_ingress(self):
        self.server.mission.snapshot=dict(mission_id="mission-test",epoch=0,phase="paused")
        for kind in ("observe","resume","key","action","goal"):
            self.assertEqual(self.post({"kind":kind})[0],409)
        self.assertEqual(self.recovery(dict(kind="request_interrupt",expected_session="world",expected_control_generation=0))[0],409)
        self.assertEqual(self.post({"kind":"pause"})[0],200)
        self.assertEqual(self.mission(mission_record())[0],200)
        self.assertFalse((self.controller.bridge/"request.json").exists())
        self.server.mission.snapshot["phase"]="completed"
        with FakeBridge(self.controller): self.assertEqual(self.post({"kind":"observe"})[0],200)

    def test_start_cannot_overtake_raw_admission_and_pause_supersedes_old_resume(self):
        entered, release = threading.Event(), threading.Event()
        current_status = self.server.mission.status
        def delayed_snapshot():
            if not entered.is_set():
                entered.set()
                self.assertTrue(release.wait(3))
            return current_status()
        with FakeBridge(self.controller) as bridge:
            self.assertEqual(self.post({"kind":"observe"})[0], 200)
            with patch.object(self.server.mission, "status", side_effect=delayed_snapshot), ThreadPoolExecutor() as pool:
                waiting = pool.submit(self.post, {"kind":"resume"})
                try:
                    self.assertTrue(entered.wait(1))
                    start = dict(schema="mission/11", kind="start", request_id="start-1", admission=admission().to_dict())
                    self.assertEqual(self.mission(start)[0], 409, "Start cannot pass raw ownership using a stale snapshot")
                    self.assertEqual(self.server.mission.calls, [])
                    self.assertEqual(self.post({"kind":"pause"})[0], 200)
                    self.assertEqual(self.request()[0], 200)
                finally: release.set()
                code, body, _ = waiting.result()
                self.assertEqual(code, 409, body)
                self.assertIn("superseded", json.loads(body)["error"])
            self.assertEqual(bridge.delivered, [], "Older raw Resume cannot adopt the post-Pause generation")

    def test_raw_input_does_not_enter_while_start_is_awaiting_admission(self):
        entered, release = threading.Event(), threading.Event()
        def delayed_start(record):
            entered.set()
            self.assertTrue(release.wait(3))
            return {"status":"accepted", "mission":None}
        start = dict(schema="mission/11", kind="start", request_id="start-1", admission=admission().to_dict())
        with patch.object(self.server.mission, "command", side_effect=delayed_start), ThreadPoolExecutor() as pool:
            waiting = pool.submit(self.mission, start)
            try:
                self.assertTrue(entered.wait(1))
                self.assertEqual(self.post({"kind":"resume"})[0], 409)
                self.assertEqual(self.post({"kind":"pause"})[0], 200)
                self.assertEqual(self.request()[0], 200)
            finally: release.set()
            self.assertEqual(waiting.result()[0], 200)
        self.assertFalse((self.controller.bridge/"request.json").exists())

    def test_shutdown_pauses_and_closes_runtime(self):
        counter = self.controller.operator_pause_generation
        self.server.server_close()
        self.assertEqual(self.controller.operator_pause_generation, counter)
        self.assertEqual(self.server.mission.calls[-1][0], "pause")
        self.assertTrue(self.server.mission.closed)

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

    def test_mission_lease_enforced_on_existing_http_ingress(self):
        with FakeBridge(self.controller) as bridge:
            self.assertEqual(self.post({"kind": "observe"})[0], 200)
            self.assertEqual(self.post({"kind": "resume"})[0], 200)
            current = self.controller.state
            lease = self.controller.acquire_mission("http-task", 0, "test-player", operation="navigate",
                expected_boundary_id=current["boundary"]["id"], expected_session=current["session"], expected_revision=current["revision"])
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
            self.assertEqual(json.loads(body)["mission_lease"], {"mission_id": "http-task", "epoch": 0, "actor_id": "test-player", "session": current["session"],
                "operation": "navigate", "pause_generation": lease.pause_generation, "takeover_generation": 0})
            self.assertEqual(self.post({"kind": "observe"})[0], 200)
            self.assertEqual(self.post({"kind": "goal", "text": "record only"})[0], 200)
            # Public JSON cannot supply an in-process capability or start a run.
            self.assertEqual(self.post({"kind": "action", "action": "RIGHT", "mission_lease": {}})[0], 400)
            self.assertEqual(self.post({"kind": "acquire_mission"})[0], 409)
            self.assertEqual(self.post({"kind": "pause"})[0], 200)
            self.assertIsNone(self.controller.status()["mission_lease"])
            rejected = self.controller.execute_mission(lease, kind="action", value="RIGHT", expected_boundary_id=current["boundary"]["id"],
                expected_session=current["session"], expected_revision=current["revision"],
                logical_action_id="revoked-http-lease", deadline_monotonic=time.monotonic() + 1)
            self.assertFalse(rejected["published"])
            self.assertNotEqual(rejected["result"]["status"], "ready")
            self.assertEqual(len(bridge.delivered), delivered)
            self.assertEqual(self.post({"kind": "observe"})[0], 200)
            self.assertEqual(self.post({"kind": "resume"})[0], 200)
            self.assertIsNone(self.controller.status()["mission_lease"])

    def test_walk_accepts_known_nonhostile_evidence_through_http(self):
        with FakeBridge(self.controller) as bridge:
            self.assertEqual(self.post({"kind": "observe"})[0], 200)
            self.assertEqual(self.post({"kind": "resume"})[0], 200)
            bridge.value["scene"]["visible_creatures"] = [{"name": "cat", "hostile": False}]
            current = self.controller.state
            code, body, _ = self.post({"kind": "walk", "direction": "east", "steps": 2,
                "expected_session": current["session"], "expected_revision": current["revision"]})
            result = json.loads(body)
            self.assertEqual((code, result["status"], result["steps"]), (200, "complete", 2))
            self.assertEqual(result["observation"]["scene"]["position"], [2, 0, 0])
            self.assertEqual(result["observation"]["scene"]["visible_creatures"],
                [{"name": "cat", "hostile": False}])
            self.assertEqual([request["action"] for request in bridge.requests if request["kind"] == "action"],
                ["RIGHT", "RIGHT"])

    def test_walk_stop_evidence_and_reassessment_through_http(self):
        with FakeBridge(self.controller) as bridge:
            self.assertEqual(self.post({"kind": "observe"})[0], 200)
            self.assertEqual(self.post({"kind": "resume"})[0], 200)
            bridge.value["scene"]["visible_creatures"] = [{"name": "cat", "hostile": True}]
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
        self.assertEqual(json.loads(path.read_text())["protocol"], 6)

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
        entered, release = threading.Event(), threading.Event()
        response_path = self.controller.bridge / "response.json"
        def held_native_response(path):
            if path == response_path:
                entered.set()
                if not release.wait(5):
                    raise AssertionError("Native response fixture was not released")
            return read_json(path)
        # Hold the actual exchange after publication and outside data_lock.
        # Completion before release proves independence; a 150ms scheduler/fsync
        # threshold did not. The outer timeout is only a deadlock watchdog.
        with patch("harness.controller.read_json", side_effect=held_native_response), \
                ThreadPoolExecutor(max_workers=2) as pool:
            waiting = pool.submit(self.post, {"kind": "observe", "timeout": 2.0})
            try:
                self.assertTrue(entered.wait(2))
                self.assertTrue(self.controller.command_lock.locked())
                self.assertTrue((self.controller.bridge / "request.json").exists())
                generation = self.controller.operator_pause_generation
                paused = pool.submit(self.post, {"kind": "pause"})
                code, data, _ = paused.result(timeout=2)
                self.assertEqual(code, 200)
                self.assertEqual(json.loads(data)["status"], "pause_requested")
                self.assertEqual(self.controller.operator_pause_generation, generation + 1)
                self.assertTrue(self.controller.pause_requested)
                self.assertTrue((self.controller.bridge / "pause").exists())
                self.assertFalse(release.is_set())
                self.assertFalse(waiting.done())
            finally:
                release.set()
            waiting.result(timeout=3)

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
