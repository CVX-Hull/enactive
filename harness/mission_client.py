"""Bounded transport to the existing mission writer; never replay an action."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
from http.client import HTTPException
import math
import os
from pathlib import Path
import stat
import time
from typing import Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .gameplay.contracts import MAX_JSON_BYTES, json_object
from .gameplay.contracts import canonical
from .gameplay.mission_contracts import MAX_REQUEST_BYTES, VERSION, validate_request
from .gameplay.mission_requests import _source_binding

_CONFIG_BYTES = 64 * 1024
_FRAME_BYTES = 32 * 1024 * 1024
_HTTP_SECONDS = 6.0
_READ_ONLY = frozenset(("status", "result", "context"))


class MissionClientError(ValueError):
    """A local refusal or unavailable read, with no credentials or body attached."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@contextmanager
def _directory(path: Path | str, *, parent: int | None = None) -> Iterator[int]:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    try:
        yield descriptor
    finally:
        os.close(descriptor)


def _regular_bytes(directory: int, name: str, maximum: int, *, private: bool = False) -> bytes:
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_size > maximum
                or private and (stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_nlink != 1)):
            raise MissionClientError("Local transport file is not a bounded regular file")
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise MissionClientError("Local transport file exceeds its byte limit")
    return data


def _wait(value: float) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 15:
        raise MissionClientError("wait_seconds must be finite and between 0 and 15")
    return float(value)


def _envelope(response: dict | None, operation_id: str | None, *, reason: str | None = None,
              read_only: bool = False) -> dict:
    operation = None if response is None else response.get("operation")
    settled = reason is None and (type(operation) is dict and operation.get("result") is not None
        or read_only and response is not None and response.get("status") == "accepted")
    return dict(transport="uncertain" if reason is not None else "delivered", settled=bool(settled),
        operation_id=operation_id, response=response, reason=reason)


def _matches(operation: object, mission_id: str, operation_id: str) -> bool:
    if type(operation) is not dict or "result" not in operation:
        return False
    try:
        request = validate_request(operation.get("request"))
    except (ValueError, TypeError):
        return False
    owner = request["admission"]["mission_id"] if request["kind"] == "start" else request.get("mission_id")
    return request.get("request_id") == operation_id and owner == mission_id


class MissionClient:
    """Authenticated fixed-endpoint client with durable, caller-chosen identities.

    Staging is an at-most-once dispatch fence, not proof that a server admitted an
    operation. A prior file permits only collection, even after a lost response.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    @contextmanager
    def _runtime(self) -> Iterator[int]:
        with _directory(self.root) as root, _directory(".runtime", parent=root) as runtime:
            yield runtime

    def _connection(self) -> tuple[str, str]:
        try:
            with self._runtime() as runtime, _directory("bridge", parent=runtime) as bridge:
                config = json_object(_regular_bytes(bridge, "controller.json", _CONFIG_BYTES))
            port, token = config.get("port"), config.get("token")
            if (type(config.get("protocol")) is not int or config["protocol"] != 5
                    or type(port) is not int or not 1 <= port <= 65535
                    or type(token) is not str or not token
                    or not token.isascii() or any(ord(character) < 33 or ord(character) == 127 for character in token)):
                raise MissionClientError("Invalid local controller discovery")
            return f"http://127.0.0.1:{port}", token
        except (OSError, ValueError, TypeError):
            raise MissionClientError("Local controller discovery unavailable or invalid") from None

    def _fetch(self, path: str, *, data: bytes | None = None, maximum: int = MAX_JSON_BYTES,
               timeout: float = _HTTP_SECONDS) -> bytes:
        deadline = time.monotonic() + timeout
        base, token = self._connection()
        request = Request(base + path, data=data,
            headers={"X-CDDA-Token": token, "Content-Type": "application/json"})
        try:
            response = self._opener.open(request, timeout=timeout)
        except HTTPError as error:
            # A server rejection is a delivered response. Never expose its URL or
            # exception text, which may contain credentials or untrusted content.
            response = error
        try:
            with response:
                lengths = response.headers.get_all("Content-Length", [])
                if (len(lengths) > 1 or lengths and (not lengths[0].isascii() or not lengths[0].isdigit())
                        or lengths and response.headers.get("Transfer-Encoding")):
                    raise MissionClientError("Invalid response length")
                expected = int(lengths[0]) if lengths else None
                if expected is not None and expected > maximum:
                    raise MissionClientError("Response exceeds its byte limit")
                chunks, size = [], 0
                while True:
                    if time.monotonic() >= deadline:
                        raise MissionClientError("Response deadline expired")
                    chunk = response.read1(min(65536, maximum + 1 - size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > maximum:
                        raise MissionClientError("Response exceeds its byte limit")
                if expected is not None and size != expected:
                    raise MissionClientError("Response body is incomplete")
            return b"".join(chunks)
        except (OSError, HTTPException, ValueError):
            raise MissionClientError("Response unavailable or exceeds its byte limit") from None

    def _json(self, path: str, *, data: bytes | None = None, timeout: float = _HTTP_SECONDS) -> dict:
        try:
            return json_object(self._fetch(path, data=data, timeout=timeout))
        except (OSError, URLError, HTTPException, ValueError, TypeError):
            raise MissionClientError("Mission response unavailable or invalid") from None

    def status(self) -> dict:
        """Return the service's complete cached status without issuing an action."""
        return self._json("/api/status")

    def _stage(self, request: dict, payload: bytes) -> bool:
        mission_id = request["admission"]["mission_id"] if request["kind"] == "start" else request["mission_id"]
        identity = hashlib.sha256((mission_id + "\0" + request["request_id"]).encode()).hexdigest()
        name = f"mc-{identity}.json"
        try:
            with self._runtime() as runtime:
                try:
                    os.mkdir("mission-requests", mode=0o700, dir_fd=runtime)
                    os.fsync(runtime)
                except FileExistsError:
                    pass
                with _directory("mission-requests", parent=runtime) as directory:
                    try:
                        descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                            0o600, dir_fd=directory)
                    except FileExistsError:
                        if _regular_bytes(directory, name, MAX_REQUEST_BYTES, private=True) != payload:
                            raise MissionClientError("Request identity already staged with different or incomplete payload")
                        return False
                    # Retain a partial file on any failure: a later call must not
                    # mistake uncertain publication for permission to dispatch.
                    with os.fdopen(descriptor, "wb") as stream:
                        os.fchmod(stream.fileno(), 0o600)
                        stream.write(payload)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.fsync(directory)
            return True
        except (OSError, ValueError):
            raise MissionClientError("Request staging failed; no submission dispatched") from None

    def submit(self, request: dict, *, wait_seconds: float = 10) -> dict:
        wait = _wait(wait_seconds)
        data = validate_request(request)
        payload = canonical(data).encode()
        kind = data["kind"]
        if kind == "result":
            return self.collect(data["mission_id"], data["operation_id"], wait_seconds=wait)
        if kind in _READ_ONLY:
            try:
                return _envelope(self._json("/api/mission", data=payload), None, read_only=True)
            except MissionClientError:
                return _envelope(None, None, reason="Read response unavailable or invalid")
        mission_id = data["admission"]["mission_id"] if kind == "start" else data["mission_id"]
        operation_id = data["request_id"]
        if not self._stage(data, payload):
            return self.collect(mission_id, operation_id, wait_seconds=wait)
        deadline = time.monotonic() + wait
        try:
            response = self._json("/api/mission", data=payload)
        except MissionClientError:
            return _envelope(None, operation_id, reason="Submission response unavailable; collect the original operation")
        if response.get("operation") is not None and not _matches(response["operation"], mission_id, operation_id):
            return _envelope(response, operation_id, reason="Original operation unavailable or mismatched")
        result = _envelope(response, operation_id)
        if result["settled"] or response.get("status") != "accepted" or wait == 0:
            return result
        remaining = max(0.0, deadline - time.monotonic())
        if remaining == 0:
            return result
        return self.collect(mission_id, operation_id, wait_seconds=remaining)

    def collect(self, mission_id: str, operation_id: str, *, wait_seconds: float = 10) -> dict:
        wait = _wait(wait_seconds)
        request = validate_request(dict(schema=VERSION, kind="result", mission_id=mission_id, operation_id=operation_id))
        payload = canonical(request).encode()
        deadline = time.monotonic() + wait
        while True:
            remaining = deadline - time.monotonic()
            timeout = min(_HTTP_SECONDS, max(.001, remaining)) if wait else _HTTP_SECONDS
            try:
                response = self._json("/api/mission", data=payload, timeout=timeout)
            except MissionClientError:
                return _envelope(None, operation_id, reason="Collection response unavailable; retain the original operation")
            operation = response.get("operation")
            if not _matches(operation, mission_id, operation_id):
                return _envelope(response, operation_id, reason="Original operation unavailable or mismatched")
            result = _envelope(response, operation_id)
            remaining = deadline - time.monotonic()
            if result["settled"] or remaining <= 0 or wait == 0:
                return result
            time.sleep(min(.1, remaining))
            if time.monotonic() >= deadline:
                return result

    def source(self, mission_id: str, source_id: str) -> tuple[dict, bytes]:
        # Reuse current ID validation without allowing a path or caller URL.
        validate_request(dict(schema=VERSION, kind="result", mission_id=mission_id, operation_id=source_id))
        query = urlencode(dict(mission_id=mission_id, source_id=source_id))
        try:
            metadata = self._json("/api/mission/source?" + query)
            if (set(metadata) != {"reference", "observation", "disposition", "grants_authority"}
                    or metadata["disposition"] not in ("retained", "disputed")
                    or metadata["grants_authority"] is not False):
                raise MissionClientError("Source metadata unavailable or invalid")
            identity, _ = _source_binding(metadata)
            if identity != source_id:
                raise MissionClientError("Source identity differs from requested source")
            image = self._fetch("/api/mission/frame?" + query, maximum=_FRAME_BYTES)
            if (not image.startswith(b"\x89PNG\r\n\x1a\n")
                    or hashlib.sha256(image).hexdigest() != metadata["reference"]["frame_sha256"]):
                raise MissionClientError("Source frame differs from retained reference")
            return metadata, image
        except (OSError, URLError, HTTPException, ValueError, TypeError, KeyError):
            raise MissionClientError("Exact retained source unavailable or invalid") from None
