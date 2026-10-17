"""Real loopback HTTP checks with temporary bridge files, not game acceptance."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from harness.controller import Controller
from harness.server import Server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "web").mkdir()
        (self.root / "web" / "index.html").write_text('<meta content="__CONTROLLER_TOKEN__">')
        (self.root / "web" / "app.js").write_text('"use strict";')
        (self.root / "web" / "style.css").write_text('body {}')
        self.controller = Controller(self.root, timeout=0.15)
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

    def test_loopback_bind_and_private_config(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        path = self.controller.bridge / "controller.json"
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(path.read_text())["token"], self.controller.token)
        self.assertEqual(json.loads(path.read_text())["protocol"], 2)

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
