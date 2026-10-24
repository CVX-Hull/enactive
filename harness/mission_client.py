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
from .gameplay.reflection import (
    MAX_COMMAND_BYTES, MAX_JOB_BYTES, MAX_PROPOSAL_BYTES, MAX_RESULT_BYTES,
    MAX_REFLECTION_READ_WAIT_SECONDS,
    validate_command, validate_job, validate_proposal,
)

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


def _wait(value: float, *, maximum: float = 15) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
        raise MissionClientError(f"wait_seconds must be finite and between 0 and {maximum}")
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
            if (type(config.get("protocol")) is not int or config["protocol"] != 6
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

    def _json(self, path: str, *, data: bytes | None = None, timeout: float = _HTTP_SECONDS,
              maximum: int = MAX_JSON_BYTES) -> dict:
        try:
            return json_object(self._fetch(path, data=data, timeout=timeout, maximum=maximum))
        except (OSError, URLError, HTTPException, ValueError, TypeError):
            raise MissionClientError("Mission response unavailable or invalid") from None

    def status(self) -> dict:
        """Return the service's complete cached status without issuing an action."""
        return self._json("/api/status")

    @staticmethod
    def _request_filename(mission_id: str, request_id: str) -> str:
        identity = hashlib.sha256((mission_id + "\0" + request_id).encode()).hexdigest()
        return f"mc-{identity}.json"

    def staged_request(self, mission_id: str, request_id: str) -> dict | None:
        """Read one immutable local intent; absence alone permits first staging.

        This is not a submission/result lookup and never contacts the service.
        Unsafe, partial or mismatched files preserve uncertainty and fail closed.
        """
        validate_request(dict(schema=VERSION, kind="result", mission_id=mission_id, operation_id=request_id))
        try:
            with self._runtime() as runtime:
                try:
                    with _directory("mission-requests", parent=runtime) as directory:
                        try:
                            payload = _regular_bytes(directory, self._request_filename(mission_id, request_id),
                                MAX_REQUEST_BYTES, private=True)
                        except FileNotFoundError:
                            return None
                except FileNotFoundError:
                    return None
            data = validate_request(payload)
            owner = data["admission"]["mission_id"] if data["kind"] == "start" else data["mission_id"]
            if (owner != mission_id or data.get("request_id") != request_id
                    or canonical(data).encode() != payload):
                raise MissionClientError("Staged request identity or canonical payload differs")
            return data
        except (OSError, ValueError, TypeError, KeyError):
            raise MissionClientError("Staged request unavailable or invalid; no submission dispatched") from None

    def _stage(self, request: dict, payload: bytes) -> bool:
        mission_id = request["admission"]["mission_id"] if request["kind"] == "start" else request["mission_id"]
        return self._stage_payload("mission-requests", self._request_filename(mission_id, request["request_id"]),
            payload, MAX_REQUEST_BYTES)

    def _stage_payload(self, folder: str, name: str, payload: bytes, maximum: int) -> bool:
        # Both callers derive folder/name internally, never from a caller path.
        try:
            with self._runtime() as runtime:
                try:
                    os.mkdir(folder, mode=0o700, dir_fd=runtime)
                    os.fsync(runtime)
                except FileExistsError:
                    pass
                with _directory(folder, parent=runtime) as directory:
                    try:
                        descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                            0o600, dir_fd=directory)
                    except FileExistsError:
                        if _regular_bytes(directory, name, maximum, private=True) != payload:
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
        return self._retained_source("/api/mission/", query, source_id)

    def _retained_source(self, prefix: str, query: str, source_id: str) -> tuple[dict, bytes]:
        try:
            metadata = self._json(prefix + "source?" + query)
            if (set(metadata) != {"reference", "observation", "disposition", "grants_authority"}
                    or metadata["disposition"] not in ("retained", "disputed")
                    or metadata["grants_authority"] is not False):
                raise MissionClientError("Source metadata unavailable or invalid")
            identity, _ = _source_binding(metadata)
            if identity != source_id:
                raise MissionClientError("Source identity differs from requested source")
            image = self._fetch(prefix + "frame?" + query, maximum=_FRAME_BYTES)
            if (not image.startswith(b"\x89PNG\r\n\x1a\n")
                    or hashlib.sha256(image).hexdigest() != metadata["reference"]["frame_sha256"]):
                raise MissionClientError("Source frame differs from retained reference")
            return metadata, image
        except (OSError, URLError, HTTPException, ValueError, TypeError, KeyError):
            raise MissionClientError("Exact retained source unavailable or invalid") from None

    @staticmethod
    def _reflection_scope(mission_id: str, reflector_id: str, job_id: str = "read",
                          command_id: str = "read") -> dict:
        return validate_command(dict(schema="reflection/2", kind="claim", mission_id=mission_id,
            reflector_id=reflector_id, job_id=job_id, command_id=command_id))

    @staticmethod
    def _reflection_unknown(command_id: str) -> dict:
        # Missing is not evidence of zero admission after an uncertain POST.
        return dict(status="unknown", admitted=None, command_id=command_id,
            reason="Original reflection receipt unavailable or invalid; collect only",
            grants_authority=False)

    def _reflection_receipt(self, path: str, command_id: str, *, payload: bytes | None = None,
                            timeout: float = _HTTP_SECONDS) -> dict:
        try:
            response = self._json(path, data=payload, timeout=timeout, maximum=MAX_RESULT_BYTES + 2048)
            if (not {"status", "admitted", "command_id", "grants_authority"} <= response.keys()
                    or response.keys() - {"status", "admitted", "command_id", "grants_authority", "result", "reason"}
                    or response["command_id"] != command_id or response["grants_authority"] is not False
                    or type(response["admitted"]) is not bool
                    or response["status"] not in ("pending", "committed", "busy", "unknown", "rejected", "missing")
                    or "reason" in response and (type(response["reason"]) is not str or len(response["reason"]) > 2048)
                    or "result" in response and (type(response["result"]) is not dict
                        or len(canonical(response["result"]).encode()) > MAX_RESULT_BYTES)):
                raise MissionClientError("Invalid reflection receipt")
            if (response["status"] == "missing"
                    or response["status"] in ("pending", "committed") and not response["admitted"]
                    or response["status"] == "busy" and response["admitted"]
                    or response["status"] == "committed" and "result" not in response):
                raise MissionClientError("Unavailable reflection receipt")
            return response
        except (MissionClientError, UnicodeError):
            return self._reflection_unknown(command_id)

    def reflection_command(self, command: dict, *, wait_seconds: float = 10) -> dict:
        """Stage an advisory command once; uncertainty permits only collection.

        Only an explicit zero-admission busy claim can be retried, at most three
        attempts within this call's original deadline. A final known busy claim
        releases its local fence for a later bounded call. Submissions never retry.
        """
        wait = _wait(wait_seconds)
        body = validate_command(command)
        payload = canonical(body).encode()
        identity = hashlib.sha256((body["mission_id"] + "\0" + body["command_id"]).encode()).hexdigest()
        if not self._stage_payload("reflection-commands", f"rc-{identity}.json", payload, MAX_COMMAND_BYTES):
            return self.reflection_collect(body["mission_id"], body["reflector_id"], body["command_id"], wait_seconds=wait)
        deadline = time.monotonic() + wait
        for attempt in range(3):
            remaining = deadline - time.monotonic()
            timeout = min(_HTTP_SECONDS, max(.001, remaining)) if wait else _HTTP_SECONDS
            response = self._reflection_receipt("/api/reflection/command", body["command_id"], payload=payload, timeout=timeout)
            remaining = deadline - time.monotonic()
            if (response["status"] != "busy" or body["kind"] != "claim"
                    or response["admitted"] is not False or attempt == 2 or remaining <= 0):
                break
            time.sleep(min(.1 * (attempt + 1), remaining))
            if time.monotonic() >= deadline:
                break
        if body["kind"] == "claim" and response["status"] == "busy" and response["admitted"] is False:
            # This validated receipt proves zero admission, unlike a missing
            # result after uncertainty. Preserve all other dispatch fences.
            with self._runtime() as runtime, _directory("reflection-commands", parent=runtime) as directory:
                name = f"rc-{identity}.json"
                if _regular_bytes(directory, name, MAX_COMMAND_BYTES, private=True) != payload:
                    raise MissionClientError("Busy claim stage differs from its original payload")
                os.unlink(name, dir_fd=directory)
                os.fsync(directory)
        remaining = deadline - time.monotonic()
        if response["status"] == "pending" and remaining > 0:
            return self.reflection_collect(body["mission_id"], body["reflector_id"], body["command_id"], wait_seconds=remaining)
        return response

    def reflection_collect(self, mission_id: str, reflector_id: str, command_id: str, *, wait_seconds: float = 10) -> dict:
        """Read the original advisory receipt without posting any command."""
        wait = _wait(wait_seconds)
        self._reflection_scope(mission_id, reflector_id, command_id=command_id)
        path = "/api/reflection/result?" + urlencode(dict(mission_id=mission_id, reflector_id=reflector_id, command_id=command_id))
        deadline = time.monotonic() + wait
        while True:
            remaining = deadline - time.monotonic()
            timeout = min(_HTTP_SECONDS, max(.001, remaining)) if wait else _HTTP_SECONDS
            response = self._reflection_receipt(path, command_id, timeout=timeout)
            remaining = deadline - time.monotonic()
            if response["status"] != "pending" or remaining <= 0:
                return response
            time.sleep(min(.1, remaining))
            if time.monotonic() >= deadline:
                return response

    def reflection_next(self, mission_id: str, reflector_id: str, *, wait_seconds: float = 0) -> dict:
        """Read/wait for bounded cached work; this read never claims a job."""
        wait = _wait(wait_seconds, maximum=MAX_REFLECTION_READ_WAIT_SECONDS)
        self._reflection_scope(mission_id, reflector_id)
        query = urlencode(dict(mission_id=mission_id, reflector_id=reflector_id, wait_seconds=wait))
        response = self._json("/api/reflection/next?" + query, timeout=wait + _HTTP_SECONDS,
            maximum=MAX_JOB_BYTES + 2048)
        if response.get("grants_authority") is not False:
            raise MissionClientError("Invalid reflection job response")
        if response.get("status") in ("idle", "closed") and set(response) == {"status", "grants_authority"}:
            return response
        try:
            if set(response) != {"status", "job", "grants_authority"} or response["status"] not in ("offered", "claimed"):
                raise ValueError
            wrapper = response["job"]
            if (type(wrapper) is not dict or set(wrapper) != {"job", "state", "claimed_at", "deadline"}
                    or wrapper["state"] != response["status"]):
                raise ValueError
            job = validate_job(wrapper["job"])
            if (job["mission_id"], job["reflector_id"]) != (mission_id, reflector_id):
                raise ValueError
            if wrapper["state"] == "offered":
                if wrapper["claimed_at"] is not None or wrapper["deadline"] is not None:
                    raise ValueError
            elif (any(type(wrapper[key]) not in (int, float) or not math.isfinite(wrapper[key]) or wrapper[key] < 0
                      for key in ("claimed_at", "deadline")) or wrapper["deadline"] <= wrapper["claimed_at"]):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise MissionClientError("Invalid reflection job response") from None
        return response

    def reflection_source(self, mission_id: str, reflector_id: str, job_id: str, source_id: str) -> tuple[dict, bytes]:
        """Read an exact job source; never Observe or use the player source path."""
        self._reflection_scope(mission_id, reflector_id, job_id, source_id)
        query = urlencode(dict(mission_id=mission_id, reflector_id=reflector_id, job_id=job_id, source_id=source_id))
        return self._retained_source("/api/reflection/", query, source_id)

    def reflection_advice(self, mission_id: str, proposal_id: str) -> dict:
        """Read one passive proposal; it is never accepted memory or authority."""
        validate_request(dict(schema=VERSION, kind="result", mission_id=mission_id, operation_id=proposal_id))
        query = urlencode(dict(mission_id=mission_id, proposal_id=proposal_id))
        response = self._json("/api/reflection/proposal?" + query, maximum=MAX_PROPOSAL_BYTES + 2048)
        if (set(response) == {"status", "grants_authority"} and response["status"] == "missing"
                and response["grants_authority"] is False):
            return response
        try:
            if (set(response) != {"status", "proposal", "grants_authority"}
                    or response["status"] != "available" or response["grants_authority"] is not False):
                raise ValueError
            proposal = validate_proposal(response["proposal"])
            if (proposal["mission_id"], proposal["id"]) != (mission_id, proposal_id):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise MissionClientError("Invalid reflection advice response") from None
        return response
