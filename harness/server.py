"""Loopback-only HTTP boundary. No arbitrary file serving or external assets."""
from __future__ import annotations

import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .controller import Controller, MAX_REQUEST, MAX_WAIT, RECOVERY_KINDS, atomic_json
from .gameplay.contracts import PlanCandidate, json_object


GAMEPLAY_FIELDS = {
    "start": {"direction", "distance", "expected_session", "expected_revision"},
    "continue": {"run_id", "execution_epoch", "expected_session", "expected_revision"},
    "abandon": {"run_id", "execution_epoch"},
    "planning_request": set(),
    "plan": {"request_id", "candidate"},
}


def validate_gameplay(body: dict[str, Any]) -> None:
    """Check data at ingress; only the runtime can admit gameplay authority."""
    kind = body.get("kind")
    if not isinstance(kind, str) or kind not in GAMEPLAY_FIELDS:
        raise ValueError("Unknown gameplay operation")
    if body.keys() != GAMEPLAY_FIELDS[kind] | {"kind"}:
        raise ValueError("Gameplay fields must match the operation exactly")
    for field in {"run_id", "request_id", "expected_session"} & body.keys():
        if not isinstance(body[field], str) or not body[field].strip() or len(body[field]) > 160:
            raise ValueError(f"{field} must be nonempty text of at most 160 characters")
    for field in {"execution_epoch", "expected_revision"} & body.keys():
        if type(body[field]) is not int or body[field] < 0:
            raise ValueError(f"{field} must be a nonnegative integer")
    if kind == "start":
        if body["direction"] not in ("north", "east", "south", "west"):
            raise ValueError("Direction must be north, east, south or west")
        if type(body["distance"]) is not int or not 1 <= body["distance"] <= 4:
            raise ValueError("Distance must be an integer from 1 to 4")
    if kind == "plan":
        if type(body["candidate"]) is not dict:
            raise ValueError("Candidate must be a gameplay/2 PlanCandidate object")
        PlanCandidate.from_dict(body["candidate"])


def validate_recovery(body: dict[str, Any]) -> None:
    """Validate caller authority without refreshing or substituting native state."""
    kind = body["kind"]
    if kind not in RECOVERY_KINDS:
        raise ValueError("Unknown recovery operation")
    required = {"kind", "expected_session", "expected_control_generation"}
    strings = {"expected_session"}
    integers = {"expected_control_generation"}
    if kind != "request_interrupt":
        required |= {"expected_boundary_id", "expected_revision", "expected_frame"}
        strings |= {"expected_boundary_id", "expected_frame"}
        integers.add("expected_revision")
    if kind == "answer_interrupt":
        required |= {"interrupt_request_id", "choice"}
        strings |= {"interrupt_request_id", "choice"}
    if body.keys() - {"timeout"} != required:
        raise ValueError("Recovery fields must match the operation exactly")
    if any(not isinstance(body[field], str) or not body[field] for field in strings):
        raise ValueError("Recovery identity and choice fields must be nonempty strings")
    if any(type(body[field]) is not int or body[field] < 0 for field in integers):
        raise ValueError("Recovery generation and revision must be nonnegative integers")
    if kind == "answer_interrupt" and body["choice"] not in {"YES", "NO"}:
        raise ValueError("Interrupt choice must be YES or NO")
    if "timeout" in body and (type(body["timeout"]) not in {int, float} or not 0 < body["timeout"] <= MAX_WAIT):
        raise ValueError("Timeout must be greater than 0 and at most 15 seconds")


class Server(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def __init__(self, controller: Controller, port: int = 8765):
        from .runtime import GameplayRuntime

        self.controller = controller
        self.gameplay = GameplayRuntime(controller)
        self._gameplay_closed = False
        super().__init__(("127.0.0.1", port), Handler)
        self.port = self.server_address[1]
        atomic_json(controller.bridge / "controller.json", {
            "protocol": 4, "port": self.port, "token": controller.token})

    def server_close(self) -> None:
        super().server_close()
        if not self._gameplay_closed:
            self._gameplay_closed = True
            # The immediate path revokes authority before waiting for worker cleanup.
            try:
                self.gameplay.pause("Service shutdown", operator=False)
            finally:
                self.gameplay.close()


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
            self._json(200, {**controller.status(), "gameplay": self.server.gameplay.status()})
            return
        if path == "/frame.png":
            try:
                names = parse_qs(urlsplit(self.path).query).get("name", [])
                name = names[0] if len(names) == 1 else "frame.png"
                if name != "frame.png" and not re.fullmatch(r"frame-[0-9]{1,20}-[0-9]{1,10}(?:-[0-9]{1,10})?-[1-9][0-9]{0,9}\.png", name):
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
        if self.path not in {"/api/command", "/api/recovery", "/api/gameplay"}:
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
            body = json_object(data)
            if not isinstance(body, dict) or not isinstance(body.get("kind"), str):
                raise ValueError("Command must be a JSON object with a string kind")
            if self.path == "/api/recovery":
                validate_recovery(body)
            elif self.path == "/api/gameplay":
                validate_gameplay(body)
            else:
                allowed = {"kind", "timeout", "key", "action", "direction", "steps", "text",
                           "expected_session", "expected_revision"}
                if body.keys() - allowed:
                    raise ValueError("Unknown command fields")
        except (ValueError, OSError, RecursionError) as exc:
            self._json(400, {"error": f"Invalid command: {exc}"})
            return
        kind = body.pop("kind")
        try:
            if self.path == "/api/gameplay":
                result = self.server.gameplay.command(kind, **body)
            elif self.path == "/api/command" and kind == "pause":
                result = self.server.gameplay.pause("Operator Pause")
            else:
                dispatch = self.server.controller.recover if self.path == "/api/recovery" else self.server.controller.execute
                result = dispatch(kind, **body)
        except (OSError, ValueError, TypeError) as exc:
            result = {"status": "rejected" if self.path == "/api/gameplay" else "controller_error",
                      "error": f"Controller could not complete the request: {exc}"}
            if self.path == "/api/gameplay":
                result["gameplay"] = self.server.gameplay.status()
        success = ({"accepted"} if self.path == "/api/gameplay" else
                   {"prompt_opened", "answer_delivered", "dismissal_delivered", "not_applicable"}
                   if self.path == "/api/recovery" else {"ready", "recorded", "pause_requested", "complete"})
        code = 200 if result["status"] in success else 409
        self._json(code, result)
