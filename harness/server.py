"""Loopback-only HTTP boundary. No arbitrary file serving or external assets."""
from __future__ import annotations

import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
import threading
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .controller import Controller, MAX_REQUEST, MAX_WAIT, RECOVERY_KINDS, atomic_json
from .gameplay.contracts import json_object
from .gameplay.mission_contracts import MAX_REQUEST_BYTES, validate_request
from .gameplay.mission_ledger import TERMINAL
from .gameplay.reflection import MAX_COMMAND_BYTES, validate_command as validate_reflection_command
from .host_status import deciding_host_status


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
        from .mission_runtime import MissionRuntime

        self.controller = controller
        # A failed bind must not leave a mission worker running. Base server
        # construction can call server_close before a runtime exists.
        self._mission_closed = True
        # Coordinate raw dispatch with admission, without queueing behind native
        # waits. Pause and cached status never acquire this gate.
        self.ingress_lock = threading.Lock()
        self.raw_ingress = 0
        super().__init__(("127.0.0.1", port), Handler)
        self.port = self.server_address[1]
        try:
            self.mission = MissionRuntime(controller)
            self._mission_closed = False
            atomic_json(controller.bridge / "controller.json", {
                "protocol": 7, "port": self.port, "token": controller.token,
                "controller_boot_id": controller.authority["controller_boot_id"], "controller_pid": os.getpid()})
        except BaseException:
            self.server_close()
            raise

    def server_close(self) -> None:
        super().server_close()
        if not self._mission_closed:
            self._mission_closed = True
            # The immediate path revokes authority before waiting for worker cleanup.
            try:
                self.mission.pause("Service shutdown", cause="internal_recovery")
            finally:
                receipt = self.mission.close()
                if type(receipt) is not dict:
                    receipt = {"writer_settled": False, "native_cleanup": {"outcome": "cleanup_unknown"},
                        "native_absence_verified": False, "acceptance_claimed": False, "grants_authority": False}
                boot_id = self.controller.authority["controller_boot_id"]
                atomic_json(self.controller.bridge / f"mission-shutdown-{boot_id}.json",
                    {"controller_boot_id": boot_id, "cleanup": receipt, "grants_authority": False})


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
        # Match canonical context byte sizing without applying a single-record
        # parser limit to aggregate spectator status/history responses.
        body = json.dumps(data, ensure_ascii=False, allow_nan=False,
                          sort_keys=True, separators=(",", ":")).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

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
        if path.startswith("/api/reflection/"):
            self._reflection_get(path)
            return
        if path in {"/api/mission/source", "/api/mission/frame"}:
            supplied = self.headers.get("X-CDDA-Token", "")
            if not hmac.compare_digest(supplied.encode("utf-8"), controller.token.encode("ascii")):
                self._json(403, {"error": "Valid local controller token required"})
                return
            try:
                query = parse_qs(urlsplit(self.path).query, strict_parsing=True)
                if (set(query) != {"mission_id", "source_id"}
                        or any(len(values) != 1 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", values[0])
                               for values in query.values())):
                    raise ValueError("Select one exact mission and retained source ID")
                metadata, data = self.server.mission.source(query["mission_id"][0], query["source_id"][0])
                if path == "/api/mission/source":
                    self._json(200, metadata)
                else:
                    self._send(200, data, "image/png")
            except (OSError, ValueError) as exc:
                self._json(409, {"error": str(exc)[:1024]})
            return
        if path == "/api/status":
            mission = self.server.mission.status()
            self._json(200, {**controller.status(), "mission": mission,
                "controller_boot_id": controller.authority["controller_boot_id"], "controller_pid": os.getpid(),
                "deciding_host": deciding_host_status(controller.root, mission)})
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
        if self.path == "/api/reflection/command":
            self._reflection_post()
            return
        if self.path not in {"/api/command", "/api/recovery", "/api/mission"}:
            self._json(404, {"error": "Unknown endpoint"})
            return
        with self.server.controller.data_lock:
            entry_generation = self.server.controller.pause_generation
        supplied = self.headers.get("X-CDDA-Token", "")
        if not hmac.compare_digest(supplied.encode("utf-8"), self.server.controller.token.encode("ascii")):
            self._json(403, {"error": "Valid local controller token required"})
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            self._json(415, {"error": "Use application/json"})
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
            maximum = MAX_REQUEST_BYTES if self.path == "/api/mission" else MAX_REQUEST
            if self.headers.get("Transfer-Encoding") or not 0 < length <= maximum:
                self._json(413, {"error": f"JSON body must be 1–{maximum} bytes"})
                return
            self.connection.settimeout(3)
            data = self.rfile.read(length)
            body = json_object(data)
            if not isinstance(body, dict) or not isinstance(body.get("kind"), str):
                raise ValueError("Command must be a JSON object with a string kind")
            if self.path == "/api/recovery":
                validate_recovery(body)
            elif self.path == "/api/mission":
                body = validate_request(body)
            else:
                allowed = {"kind", "timeout", "key", "action", "direction", "steps", "text",
                           "expected_session", "expected_revision"}
                if body.keys() - allowed:
                    raise ValueError("Unknown command fields")
        except (ValueError, OSError, RecursionError) as exc:
            self._json(400, {"error": f"Invalid command: {exc}"})
            return
        kind = body["kind"]
        starting = self.path == "/api/mission" and kind == "start"
        raw_input = self.path != "/api/mission" and not (self.path == "/api/command" and kind == "pause")
        guarded = starting or raw_input
        if guarded and not self.server.ingress_lock.acquire(blocking=False):
            self._json(409, {"status": "rejected", "error": "Another raw input or mission admission owns ingress"})
            return
        if starting and self.server.raw_ingress:
            self.server.ingress_lock.release()
            self._json(409, {"status": "rejected", "error": "Raw input must settle before mission admission"})
            return
        if raw_input:
            self.server.raw_ingress += 1
            # Recovery must still run while an ordinary native input is waiting.
            # Only admission needs exclusion; controller owns channel writers.
            self.server.ingress_lock.release()
        try:
            if self.path == "/api/mission":
                result = self.server.mission.command(body)
            elif self.path == "/api/command" and kind == "pause":
                result = self.server.mission.pause("Operator Pause")
            else:
                mission = self.server.mission.status()
                if mission is not None and mission.get("phase") not in TERMINAL:
                    raise ValueError("An admitted mission owns observation/input; use its typed mission request or Pause")
                body.pop("kind")
                if self.path == "/api/recovery":
                    result = self.server.controller.recover(kind, **body)
                else:
                    result = self.server.controller.execute(kind, expected_generation=entry_generation, **body)
        except (OSError, ValueError, TypeError) as exc:
            result = {"status": "rejected" if self.path == "/api/mission" else "controller_error",
                      "error": f"Controller could not complete the request: {exc}"}
            if self.path == "/api/mission":
                result["mission"] = self.server.mission.status()
        finally:
            if starting:
                self.server.ingress_lock.release()
            elif raw_input:
                with self.server.ingress_lock:
                    self.server.raw_ingress -= 1
        success = ({"accepted"} if self.path == "/api/mission" else
                   {"prompt_opened", "answer_delivered", "dismissal_delivered", "not_applicable"}
                   if self.path == "/api/recovery" else {"ready", "recorded", "pause_requested", "complete"})
        code = 200 if result["status"] in success else 409
        self._json(code, result)

    def _reflection_token(self) -> bool:
        supplied = self.headers.get("X-CDDA-Token", "")
        if not hmac.compare_digest(supplied.encode("utf-8"), self.server.controller.token.encode("ascii")):
            self._json(403, {"error": "Valid local controller token required"})
            return False
        return True

    def _reflection_get(self, path: str) -> None:
        if not self._reflection_token():
            return
        fields = {
            "/api/reflection/next": {"mission_id", "reflector_id", "wait_seconds"},
            "/api/reflection/result": {"mission_id", "reflector_id", "command_id"},
            "/api/reflection/proposal": {"mission_id", "proposal_id"},
            "/api/reflection/source": {"mission_id", "reflector_id", "job_id", "source_id"},
            "/api/reflection/frame": {"mission_id", "reflector_id", "job_id", "source_id"},
        }
        if path not in fields:
            self._json(404, {"error": "Unknown advisory endpoint"})
            return
        try:
            query = parse_qs(urlsplit(self.path).query, strict_parsing=True)
            if set(query) != fields[path] or any(len(values) != 1 for values in query.values()):
                raise ValueError("Advisory selection fields must match exactly")
            args = {key: values[0] for key, values in query.items()}
            if any(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value) is None
                   for key, value in args.items() if key != "wait_seconds"):
                raise ValueError("Advisory identities must be bounded ASCII")
            mission = self.server.mission
            if path.endswith("/next"):
                args["wait_seconds"] = float(args["wait_seconds"])
                result = mission.reflection_next(**args)
            elif path.endswith("/result"):
                result = mission.reflection_result(**args)
            elif path.endswith("/proposal"):
                result = mission.reflection_proposal(**args)
            else:
                metadata, data = mission.reflection_source(**args)
                if path.endswith("/frame"):
                    self._send(200, data, "image/png")
                else:
                    self._json(200, metadata)
                return
            self._json(200, result)
        except (OSError, ValueError, TypeError) as exc:
            self._json(409, {"status": "rejected", "reason": str(exc)[:1024], "grants_authority": False})

    def _reflection_post(self) -> None:
        # Advisory ingress never acquires the game ingress lock or input queue.
        if not self._reflection_token():
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            self._json(415, {"error": "Use application/json"})
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
            if self.headers.get("Transfer-Encoding") or not 0 < length <= MAX_COMMAND_BYTES:
                self._json(413, {"error": "Advisory command exceeds its finite body bound"})
                return
            self.connection.settimeout(3)
            body = validate_reflection_command(self.rfile.read(length))
            result = self.server.mission.reflection_command(body)
            self._json(200 if result["status"] in ("pending", "committed") else 409, result)
        except (OSError, ValueError, TypeError, RecursionError) as exc:
            self._json(409, {"status": "rejected", "reason": str(exc)[:1024], "grants_authority": False})
