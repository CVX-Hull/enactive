"""Client transport through a controlled HTTP stub, never a CDDA runtime."""
from copy import deepcopy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import stat
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from harness.gameplay.contracts import ContractError, MAX_JSON_BYTES
from harness.gameplay.mission_contracts import canonical
from harness.mission_client import MissionClient, MissionClientError
from tests.test_gameplay_evidence import png
from tests.test_mission_contracts import admission, request
from tests.test_mission_request_producer import bundle


class Stub(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), Handler)
        self.calls = []
        self.callback = lambda handler, body: handler.reply(dict(status="accepted"))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, value, *, code=200, headers=None):
        data = json.dumps(value).encode() if isinstance(value, dict) else value
        self.send_response(code)
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def dispatch(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        body = json.loads(raw) if raw else None
        self.server.calls.append((self.command, self.path, dict(self.headers), body, raw))
        self.server.callback(self, body)

    do_GET = dispatch
    do_POST = dispatch


def operation(value=None, *, state="running", result=None):
    return dict(request=request() if value is None else value, epoch=0, state=state, result=result,
                admitted_at=0, deadline=10)


class MissionClientTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bridge = self.root / ".runtime" / "bridge"
        self.bridge.mkdir(parents=True)
        self.server = self.start_stub()
        self.config = dict(protocol=4, port=self.server.server_port, token="private-test-token")
        self.write_config()
        self.client = MissionClient(self.root)

    def start_stub(self):
        server = Stub()
        thread = threading.Thread(target=server.serve_forever, kwargs=dict(poll_interval=.01), daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def write_config(self):
        (self.bridge / "controller.json").write_text(json.dumps(self.config))

    def stage_path(self, value=None):
        value = request() if value is None else value
        mission = value["admission"]["mission_id"] if value["kind"] == "start" else value["mission_id"]
        name = hashlib.sha256((mission + "\0" + value["request_id"]).encode()).hexdigest()
        return self.root / ".runtime" / "mission-requests" / ("mc-" + name + ".json")

    def respond_operation(self, value=None, *, state="running", result=None):
        response = dict(status="accepted", operation=operation(value, state=state, result=result))
        self.server.callback = lambda handler, body: handler.reply(response)
        return response

    def test_discovery_authentication_closed_paths_and_proxy_bypass(self):
        expected = dict(mission=None, state=dict(status="ready"))
        self.server.callback = lambda handler, body: handler.reply(expected)
        with patch.dict(os.environ, {"http_proxy": "http://127.0.0.1:1", "HTTP_PROXY": "http://127.0.0.1:1", "no_proxy": ""}):
            self.assertEqual(self.client.status(), expected)
        method, path, headers, body, _ = self.server.calls[0]
        self.assertEqual((method, path, body), ("GET", "/api/status", None))
        self.assertEqual(headers["X-Cdda-Token"], self.config["token"])
        self.assertIsNone(body)
        self.assertFalse((self.root / ".runtime" / "mission-requests").exists())

    def test_invalid_discovery_cannot_send_or_leak_credentials(self):
        cases = [dict(protocol=3), dict(protocol=True), dict(port=True), dict(port=0), dict(port=65536),
                 dict(port="8765"), dict(token=""), dict(token=None), dict(token="header\ninjection")]
        for changes in cases:
            with self.subTest(changes=changes):
                self.config = dict(protocol=4, port=self.server.server_port, token="private-test-token") | changes
                self.write_config()
                with self.assertRaises(MissionClientError) as raised:
                    self.client.status()
                self.assertNotIn("private-test-token", str(raised.exception))
        self.assertEqual(self.server.calls, [])

    def test_discovery_rejects_symlink_nonregular_oversize_and_duplicate_keys(self):
        config = self.bridge / "controller.json"
        config.unlink()
        outside = self.root / "not-discovery.json"
        outside.write_text(json.dumps(self.config))
        config.symlink_to(outside)
        with self.assertRaises(MissionClientError): self.client.status()
        config.unlink()
        os.mkfifo(config)
        with self.assertRaises(MissionClientError): self.client.status()
        config.unlink()
        config.write_bytes(b" " * (65536 + 1))
        with self.assertRaises(MissionClientError): self.client.status()
        config.write_text('{"protocol":4,"protocol":4}')
        with self.assertRaises(MissionClientError): self.client.status()
        config.unlink()
        self.bridge.rmdir()
        self.bridge.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(MissionClientError): self.client.status()
        self.assertEqual(self.server.calls, [])

    def test_redirect_cannot_forward_token(self):
        other = self.start_stub()
        self.server.callback = lambda handler, body: handler.reply(b"redirect", code=302,
            headers={"Location": f"http://127.0.0.1:{other.server_port}/stolen"})
        with self.assertRaises(MissionClientError): self.client.status()
        result = self.client.submit(request(), wait_seconds=0)
        self.assertEqual(result["transport"], "uncertain")
        self.assertEqual(other.calls, [])
        self.assertEqual([call[1] for call in self.server.calls], ["/api/status", "/api/mission"])

    def test_staging_is_exact_private_and_durable_before_one_post(self):
        value = request(request_id="x" * 128)
        expected = dict(status="accepted", operation_id=value["request_id"])
        fsyncs = []
        real_fsync = os.fsync
        def fsync(descriptor):
            real_fsync(descriptor)
            fsyncs.append(stat.S_ISDIR(os.fstat(descriptor).st_mode))
        def callback(handler, body):
            staged = self.stage_path(value)
            self.assertEqual(staged.read_bytes(), canonical(value).encode())
            self.assertEqual(stat.S_IMODE(staged.stat().st_mode), 0o600)
            self.assertLess(len(staged.name), 80)
            self.assertIn(False, fsyncs)
            self.assertTrue(fsyncs[-1])
            handler.reply(expected)
        self.server.callback = callback
        with patch("harness.mission_client.os.fsync", side_effect=fsync):
            result = self.client.submit(value, wait_seconds=0)
        self.assertEqual(result, dict(transport="delivered", settled=False, operation_id=value["request_id"],
                                     response=expected, reason=None))
        self.assertEqual(len(self.server.calls), 1)
        self.assertEqual(self.server.calls[0][4], canonical(value).encode())

    def test_duplicate_only_collects_same_operation_and_changed_payload_refuses(self):
        expected = self.respond_operation(result=dict(outcome="blocked"), state="blocked")
        first = self.client.submit(request(), wait_seconds=0)
        second = MissionClient(self.root).submit(request(), wait_seconds=0)
        self.assertEqual(first, second)
        self.assertEqual(second["response"], expected)
        self.assertTrue(second["settled"])
        self.assertEqual([call[3]["kind"] for call in self.server.calls], ["observe", "result"])
        with self.assertRaises(MissionClientError):
            self.client.submit(request(epoch=1), wait_seconds=0)
        self.assertEqual(len(self.server.calls), 2)

    def test_ambiguous_submission_is_never_resent_even_if_operation_is_missing(self):
        def disconnect(handler, body):
            handler.connection.shutdown(socket.SHUT_RDWR)
            handler.connection.close()
        self.server.callback = disconnect
        first = self.client.submit(request(), wait_seconds=0)
        self.assertEqual(first["transport"], "uncertain")
        self.assertEqual(first["operation_id"], "request-1")
        self.server.callback = lambda handler, body: handler.reply(dict(status="rejected", reason="Unknown semantic request"))
        second = MissionClient(self.root).submit(request(), wait_seconds=0)
        self.assertEqual(second["transport"], "uncertain")
        self.assertFalse(second["settled"])
        self.assertEqual([call[3]["kind"] for call in self.server.calls], ["observe", "result"])

    def test_initial_http_rejection_is_delivered_without_claiming_success(self):
        rejected = dict(status="rejected", reason="No matching admitted mission")
        self.server.callback = lambda handler, body: handler.reply(rejected, code=409)
        result = self.client.submit(request(), wait_seconds=1)
        self.assertEqual(result["transport"], "delivered")
        self.assertFalse(result["settled"])
        self.assertEqual(result["response"], rejected)
        self.assertIsNone(result["reason"])
        self.assertEqual(len(self.server.calls), 1)

    def test_staging_failure_or_partial_file_never_dispatches(self):
        with patch("harness.mission_client.os.fsync", side_effect=OSError("sensitive details")):
            with self.assertRaises(MissionClientError) as raised:
                self.client.submit(request(), wait_seconds=0)
        self.assertNotIn("sensitive", str(raised.exception))
        path = self.stage_path()
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b'{"schema":')
        path.chmod(0o600)
        with self.assertRaises(MissionClientError): self.client.submit(request(), wait_seconds=0)
        self.assertEqual(self.server.calls, [])

    def test_failed_file_fsync_retains_fence_and_cannot_later_repost(self):
        self.stage_path().parent.mkdir()
        with patch("harness.mission_client.os.fsync", side_effect=OSError("lost write")):
            with self.assertRaises(MissionClientError): self.client.submit(request(), wait_seconds=0)
        self.assertEqual(self.stage_path().read_text(), canonical(request()))
        self.assertEqual(self.server.calls, [])
        self.server.callback = lambda handler, body: handler.reply(dict(status="rejected", reason="Unknown operation"))
        result = self.client.submit(request(), wait_seconds=0)
        self.assertEqual(result["transport"], "uncertain")
        self.assertEqual([call[3]["kind"] for call in self.server.calls], ["result"])

    def test_collection_read_timeout_is_uncertain_and_never_retries(self):
        entered = threading.Event()
        release = threading.Event()
        self.addCleanup(release.set)
        def blocked(handler, body):
            entered.set()
            release.wait(1)
            handler.reply(dict(status="accepted", operation=operation()))
        self.server.callback = blocked
        start = time.monotonic()
        result = self.client.collect("mission-test", "request-1", wait_seconds=.03)
        self.assertTrue(entered.is_set())
        self.assertEqual(result["transport"], "uncertain")
        self.assertLess(time.monotonic() - start, .8)
        self.assertEqual(len(self.server.calls), 1)
        release.set()

    def test_keyboard_cancellation_keeps_stage_and_schedules_no_future_submission(self):
        with patch.object(self.client._opener, "open", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): self.client.submit(request(), wait_seconds=0)
        self.assertTrue(self.stage_path().is_file())
        self.assertEqual(self.server.calls, [])
        self.respond_operation(state="completed", result=dict(outcome="known"))
        self.assertTrue(self.client.submit(request(), wait_seconds=0)["settled"])
        self.assertEqual([call[3]["kind"] for call in self.server.calls], ["result"])

    def test_stage_refuses_symlink_directory_symlink_file_and_nonregular_file(self):
        path = self.stage_path()
        outside = self.root / "outside"
        outside.mkdir()
        path.parent.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(MissionClientError): self.client.submit(request(), wait_seconds=0)
        path.parent.unlink()
        path.parent.mkdir()
        target = outside / "payload.json"
        target.write_text(canonical(request()))
        path.symlink_to(target)
        with self.assertRaises(MissionClientError): self.client.submit(request(), wait_seconds=0)
        path.unlink()
        os.mkfifo(path)
        with self.assertRaises(MissionClientError): self.client.submit(request(), wait_seconds=0)
        self.assertEqual(self.server.calls, [])

    def test_validation_and_wait_bounds_fail_before_staging_or_network(self):
        for value in (-1, 15.01, float("inf"), float("nan"), True, "1"):
            with self.subTest(value=value), self.assertRaises(MissionClientError):
                self.client.submit(request(), wait_seconds=value)
        for value in (request(schema="mission/6"), {k: v for k, v in request().items() if k != "request_id"}, request(extra="bad")):
            with self.subTest(value=value), self.assertRaises(ContractError):
                self.client.submit(value)
        self.assertFalse(self.stage_path().parent.exists())
        self.assertEqual(self.server.calls, [])

    def test_start_staging_and_collection_use_admission_mission_id(self):
        value = dict(schema="mission/7", kind="start", request_id="start-1", admission=admission().to_dict())
        self.respond_operation(value, state="completed", result=dict(lifecycle_needed=True))
        self.assertTrue(self.client.submit(value, wait_seconds=0)["settled"])
        self.assertTrue(self.stage_path(value).exists())
        self.assertTrue(self.client.submit(value, wait_seconds=0)["settled"])
        self.assertEqual(self.server.calls[-1][3], dict(schema="mission/7", kind="result",
            mission_id=value["admission"]["mission_id"], operation_id="start-1"))

    def test_polling_keeps_pending_and_unknown_receipts_without_resumption(self):
        pending = self.respond_operation(state="unknown", result=None)
        result = self.client.collect("mission-test", "request-1", wait_seconds=.12)
        self.assertEqual(result["response"], pending)
        self.assertEqual(result["transport"], "delivered")
        self.assertFalse(result["settled"])
        terminal = self.respond_operation(state="unknown", result=dict(delivery="unknown", success=False))
        result = self.client.collect("mission-test", "request-1", wait_seconds=1)
        self.assertEqual(result["response"], terminal)
        self.assertTrue(result["settled"])
        self.assertTrue(all(call[3]["kind"] == "result" for call in self.server.calls))
        self.assertFalse(self.stage_path().parent.exists())

    def test_submit_polls_only_result_until_terminal(self):
        counts = []
        def callback(handler, body):
            counts.append(body["kind"])
            handler.reply(dict(status="accepted", operation=operation(state="completed" if len(counts) > 2 else "running",
                result=dict(effect="requires interpretation") if len(counts) > 2 else None)))
        self.server.callback = callback
        result = self.client.submit(request(), wait_seconds=1)
        self.assertTrue(result["settled"])
        self.assertEqual(counts, ["observe", "result", "result"])

    def test_collection_deadline_and_zero_wait_schedule_no_future_calls(self):
        self.respond_operation()
        start = time.monotonic()
        result = self.client.collect("mission-test", "request-1", wait_seconds=.12)
        self.assertFalse(result["settled"])
        self.assertLess(time.monotonic() - start, .8)
        count = len(self.server.calls)
        time.sleep(.15)
        self.assertEqual(len(self.server.calls), count)
        self.client.collect("mission-test", "request-1", wait_seconds=0)
        self.assertEqual(len(self.server.calls), count + 1)

    def test_mismatched_collection_is_uncertain(self):
        for value in (request(request_id="different"), request(mission_id="different")):
            self.respond_operation(value, result=dict(effect="unknown"), state="unknown")
            result = self.client.collect("mission-test", "request-1", wait_seconds=0)
            self.assertEqual(result["transport"], "uncertain")
            self.assertEqual(result["operation_id"], "request-1")
            self.assertFalse(result["settled"])

    def test_read_only_requests_use_current_schema_without_staging(self):
        for kind in ("status", "context"):
            value = dict(schema="mission/7", kind=kind, mission_id="mission-test")
            if kind == "context":
                value.update(query="water", scope=dict(mission_id="mission-test", session="native-session", coordinate_epoch=0),
                             handoff=None, max_bytes=32768)
            response = dict(status="accepted", **({"context": dict(complete="preserved")} if kind == "context" else {}))
            self.server.callback = lambda handler, body: handler.reply(response)
            result = self.client.submit(value)
            self.assertEqual(result["response"], response)
            self.assertTrue(result["settled"])
            self.assertIsNone(result["operation_id"])
        self.assertFalse(self.stage_path().parent.exists())
        self.assertEqual([call[3]["kind"] for call in self.server.calls], ["status", "context"])

    def test_malformed_oversize_and_incomplete_json_fail_without_body_leak_or_retry(self):
        for index, payload in enumerate((b'{"error":"private-test-token","error":"other"}', b'{"value":NaN}',
                                        b"not json private-test-token", b" " * (MAX_JSON_BYTES + 1))):
            with self.subTest(index=index):
                self.server.callback = lambda handler, body: handler.reply(payload)
                with self.assertRaises(MissionClientError) as raised: self.client.status()
                self.assertNotIn("private-test-token", str(raised.exception))
                result = self.client.submit(request(request_id=f"id-{index}"), wait_seconds=0)
                self.assertEqual(result["transport"], "uncertain")
                self.assertNotIn("private-test-token", result["reason"])
        def incomplete(handler, body):
            handler.send_response(200)
            handler.send_header("Content-Length", "1000")
            handler.end_headers()
            handler.wfile.write(b'{"status":"accepted"}')
            handler.close_connection = True
        self.server.callback = incomplete
        self.assertEqual(self.client.submit(request(request_id="short-read"), wait_seconds=0)["transport"], "uncertain")
        self.assertEqual(len(self.server.calls), 9)

    def source_fixture(self, *, disposition="retained"):
        image = png()
        value = bundle()
        value["reference"]["frame_sha256"] = hashlib.sha256(image).hexdigest()
        metadata = dict(reference=value["reference"], observation=value["observation"],
                        disposition=disposition, grants_authority=False)
        def callback(handler, body):
            path = urlsplit(handler.path).path
            handler.reply(metadata if path == "/api/mission/source" else image)
        self.server.callback = callback
        return metadata, image, value["reference"]["observation_id"]

    def test_source_uses_exact_bound_metadata_frame_and_authenticated_queries(self):
        for disposition in ("retained", "disputed"):
            metadata, image, source_id = self.source_fixture(disposition=disposition)
            self.assertEqual(self.client.source("mission-test", source_id), (metadata, image))
            for method, path, headers, body, _ in self.server.calls[-2:]:
                self.assertEqual(method, "GET")
                self.assertEqual(parse_qs(urlsplit(path).query), dict(mission_id=["mission-test"], source_id=[source_id]))
                self.assertEqual(headers["X-Cdda-Token"], self.config["token"])
                self.assertIsNone(body)
            self.assertEqual([urlsplit(call[1]).path for call in self.server.calls[-2:]],
                             ["/api/mission/source", "/api/mission/frame"])

    def test_source_rejects_missing_substituted_mismatched_or_authority_metadata(self):
        metadata, image, source_id = self.source_fixture()
        variants = [dict(error="Source missing"), {**metadata, "grants_authority": True},
                    {**metadata, "disposition": "current"}]
        changed = deepcopy(metadata)
        changed["observation"]["revision"] += 1
        variants.append(changed)
        for value in variants:
            with self.subTest(value=value):
                self.server.callback = lambda handler, body: handler.reply(value)
                with self.assertRaises(MissionClientError): self.client.source("mission-test", source_id)
        self.source_fixture()
        with self.assertRaises(MissionClientError): self.client.source("mission-test", "newer-source")
        self.assertTrue(all(urlsplit(call[1]).path == "/api/mission/source" for call in self.server.calls))

    def test_source_rejects_wrong_hash_non_png_and_oversize_frame(self):
        for image in (png(b"tampered"), b"not a PNG", b"\x89PNG\r\n\x1a\n" + b"x" * (32 * 1024 * 1024)):
            metadata, _, source_id = self.source_fixture()
            self.server.callback = lambda handler, body: handler.reply(metadata if urlsplit(handler.path).path == "/api/mission/source" else image)
            with self.assertRaises(MissionClientError): self.client.source("mission-test", source_id)


if __name__ == "__main__":
    unittest.main()
