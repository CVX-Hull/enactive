"""Loopback-only HTTP boundary. No arbitrary file serving or external assets."""
from __future__ import annotations

import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .controller import Controller, MAX_REQUEST, atomic_json


class Server(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def __init__(self, controller: Controller, port: int = 8765):
        self.controller = controller
        super().__init__(("127.0.0.1", port), Handler)
        self.port = self.server_address[1]
        atomic_json(controller.bridge / "controller.json", {
            "protocol": 1, "port": self.port, "token": controller.token})

    def server_close(self) -> None:
        super().server_close()
        # A shutdown leaves the game paused; workers cannot silently resume later.
        self.controller.pause()


class Handler(BaseHTTPRequestHandler):
    server: Server
    protocol_version = "HTTP/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        # Avoid logging tokens, goals, or request bodies.
        return

    def _send(self, code: int, data: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, code: int, data: dict[str, Any]) -> None:
        self._send(code, json.dumps(data, ensure_ascii=True).encode(), "application/json; charset=utf-8")

    def _trusted(self) -> bool:
        hosts = {f"127.0.0.1:{self.server.port}", f"localhost:{self.server.port}"}
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        if (len(self.headers.get_all("Host", [])) != 1 or host not in hosts
                or origin is not None and origin != f"http://{host}"
                or self.headers.get("Sec-Fetch-Site", "none") not in {"none", "same-origin"}):
            self._json(403, {"error": "Host and browser origin must match this loopback service"})
            return False
        return True

    def do_GET(self) -> None:
        if not self._trusted():
            return
        path = urlsplit(self.path).path
        controller = self.server.controller
        if path == "/api/status":
            self._json(200, controller.status())
            return
        if path == "/frame.png":
            try:
                names = parse_qs(urlsplit(self.path).query).get("name", [])
                name = names[0] if len(names) == 1 else "frame.png"
                if name != "frame.png" and not re.fullmatch(r"frame-\d+-\d+-\d+\.png", name):
                    self._json(400, {"error": "Invalid native frame reference"})
                    return
                with (controller.bridge / name).open("rb") as stream:
                    data = stream.read(32 * 1024 * 1024 + 1)
                if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > 32 * 1024 * 1024:
                    raise ValueError("Native frame is invalid or oversized")
                self._send(200, data, "image/png")
            except (OSError, ValueError) as exc:
                self._json(503, {"error": f"Native frame unavailable: {exc}"})
            return
        assets = {"/": ("index.html", "text/html; charset=utf-8"),
                  "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                  "/style.css": ("style.css", "text/css; charset=utf-8")}
        if path not in assets:
            self._json(404, {"error": "Unknown endpoint"})
            return
        filename, content_type = assets[path]
        try:
            data = (controller.root / "web" / filename).read_bytes()
            if filename == "index.html":
                data = data.replace(b"__CONTROLLER_TOKEN__", controller.token.encode("ascii"))
            self._send(200, data, content_type)
        except OSError as exc:
            self._json(503, {"error": f"Viewer asset unavailable: {exc}"})

    def do_POST(self) -> None:
        if not self._trusted():
            return
        if self.path != "/api/command":
            self._json(404, {"error": "Unknown endpoint"})
            return
        supplied = self.headers.get("X-CDDA-Token", "")
        if not hmac.compare_digest(supplied.encode("utf-8"), self.server.controller.token.encode("ascii")):
            self._json(403, {"error": "Valid local controller token required"})
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            self._json(415, {"error": "Use application/json"})
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
            if self.headers.get("Transfer-Encoding") or not 0 < length <= MAX_REQUEST:
                self._json(413, {"error": "JSON body must be 1–4096 bytes"})
                return
            self.connection.settimeout(3)
            data = self.rfile.read(length)
            body = json.loads(data, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
            if not isinstance(body, dict) or not isinstance(body.get("kind"), str):
                raise ValueError("Command must be a JSON object with a string kind")
            allowed = {"kind", "timeout", "key", "action", "direction", "steps", "text",
                       "expected_session", "expected_revision"}
            if body.keys() - allowed:
                raise ValueError("Unknown command fields")
        except (ValueError, OSError) as exc:
            self._json(400, {"error": f"Invalid command: {exc}"})
            return
        kind = body.pop("kind")
        try:
            result = self.server.controller.execute(kind, **body)
        except (OSError, ValueError, TypeError) as exc:
            result = {"status": "controller_error", "error": f"Controller could not complete the request: {exc}"}
        code = 200 if result["status"] in {"ready", "recorded", "pause_requested", "complete"} else 409
        self._json(code, result)
