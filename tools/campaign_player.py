"""Run one frozen campaign player and at most one issued fresh successor.

This host driver reads status and collects an existing handoff. Only the players
may request mission actions, interpret retained context, claim or readmit.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import math
from pathlib import Path
import re
import signal
import subprocess
import time
from typing import TextIO
import uuid

from harness.gameplay.mission_contracts import validate_handoff_result
from harness.mission_client import MissionClient, MissionClientError


DEFAULT_CODEX = "/opt/homebrew/bin/codex"
TERMINAL = frozenset(("completed", "failed", "stopped"))
_CONFIG_KEYS = frozenset(("command", "args", "cwd", "enabled", "enabled_tools",
    "default_tools_approval_mode", "startup_timeout_sec", "tool_timeout_sec", "tools"))
_LIMITS = ("wall_seconds", "inputs", "game_seconds", "frames", "frame_bytes", "primitive_mappings")


class DriverError(ValueError):
    """A fixed, credential-free reason to stop without mission actions."""


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise DriverError("Driver deadline exhausted")
    return remaining


class _DeadlineClient(MissionClient):
    """Keep the SDK's existing transport inside the shared host deadline."""

    def __init__(self, root: Path, deadline: float):
        super().__init__(root)
        self.deadline = deadline

    def _fetch(self, path: str, *, timeout: float = 6.0, **kwargs) -> bytes:
        return super()._fetch(path, timeout=min(timeout, _remaining(self.deadline)), **kwargs)


def _write(stream: TextIO, value: dict | list) -> None:
    json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
    stream.write("\n")
    stream.flush()


def _read(path: Path) -> str:
    with path.open() as stream:
        value = stream.read(1_048_577)
    if len(value.encode()) > 1_048_576:
        raise DriverError("Frozen input exceeds its byte limit")
    return value


def _flags(values: dict, prefix: str = "mcp_servers.enactive_player"):
    for key, value in values.items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
            raise DriverError("Invalid frozen MCP configuration key")
        name = prefix + "." + key
        if isinstance(value, dict):
            yield from _flags(value, name)
        else:
            if value is None:
                raise DriverError("Invalid null frozen MCP configuration value")
            yield name + "=" + json.dumps(value, allow_nan=False)


def _argv(root: Path, run: Path, role: str, configuration: dict, *, model: str,
          effort: str, codex: str, thread: str | None = None) -> list[str]:
    args = [codex, "exec", "--json", "--ignore-user-config", "--sandbox", "read-only",
        "-C", str(root), "-m", model, "-c", "model_reasoning_effort=" + json.dumps(effort)]
    for flag in _flags(configuration):
        args.extend(("-c", flag))
    if thread is not None:
        args.extend(("resume", thread))
    return args + ["-o", str(run / f"driver-{role}-final.txt"), "-"]


def _stop_host(process: subprocess.Popen, receipt: dict) -> None:
    # The exact Popen handle is our custody boundary. Never signal a process
    # group, search descendants or imply that stopping this host cleans native.
    for name, action in (("SIGINT", lambda: process.send_signal(signal.SIGINT)),
                         ("SIGTERM", process.terminate), ("SIGKILL", process.kill)):
        if process.poll() is not None:
            return
        try:
            action()
            receipt["signals"].append(name)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2)
            return
        except subprocess.TimeoutExpired:
            continue
    receipt["host_exit_unresolved"] = process.poll() is None


def _host(role: str, args: list[str], prompt: str, root: Path,
          streams: dict[str, TextIO], deadline: float) -> dict:
    _remaining(deadline)
    prefix = f"driver-{role}"
    streams[prefix + "-prompt.txt"].write(prompt)
    streams[prefix + "-prompt.txt"].flush()
    _write(streams[prefix + "-argv.json"], args)
    receipt = dict(start=time.time(), end=None, returncode=None, timed_out=False,
        interrupted=False, signals=[], native_cleanup_claimed=False)
    process = None
    try:
        _remaining(deadline)
        process = subprocess.Popen(args, cwd=root, stdin=subprocess.PIPE,
            stdout=streams[prefix + ".jsonl"], stderr=streams[prefix + ".stderr"], text=True)
        _write(streams[prefix + "-process.json"], dict(pid=process.pid,
            start=receipt["start"], argv=args))
        process.communicate(prompt, timeout=_remaining(deadline))
    except subprocess.TimeoutExpired:
        receipt["timed_out"] = True
        _stop_host(process, receipt)
    except KeyboardInterrupt:
        receipt["interrupted"] = True
        if process is not None:
            _stop_host(process, receipt)
    except (OSError, DriverError) as error:
        receipt["error_type"] = type(error).__name__
        if process is not None:
            _stop_host(process, receipt)
    finally:
        if process is not None:
            receipt["returncode"] = process.poll()
            if process.stdin is not None:
                process.stdin.close()
        receipt["end"] = time.time()
        _write(streams[prefix + "-receipt.json"], receipt)
    return receipt


def _status(client: MissionClient, mission_id: str, deadline: float) -> dict:
    _remaining(deadline)
    snapshot = client.status()
    _remaining(deadline)
    value = snapshot.get("mission")
    if not isinstance(value, dict) or value.get("mission_id") != mission_id:
        raise DriverError("Cached status does not identify the requested mission")
    if ("active_operation" not in value or value["active_operation"] is not None
            or value.get("unresolved_effects") != []):
        raise DriverError("Mission is not quiescent or effects remain unresolved")
    return snapshot


def _launch_guard(snapshot: dict, issued: dict | None = None) -> None:
    mission = snapshot["mission"]
    bootstrap = issued is None and mission.get("phase") == "admitted" and mission.get("pause_cause") == "internal_bootstrap"
    if (type(snapshot.get("frozen")) is not bool or snapshot["frozen"] and not bootstrap
            or bootstrap and snapshot.get("operator_pause_generation") != 0
            or "pending" not in snapshot or snapshot["pending"] is not None
            or "control_pending" not in snapshot or snapshot["control_pending"] is not None
            or type(snapshot.get("operator_pause_generation")) is not int
            or snapshot["operator_pause_generation"] < 0):
        raise DriverError("Controller is frozen, pending or lacks its Pause binding")
    native = snapshot.get("state")
    # A new controller's bootstrap may retain historical state.json. It is not
    # adopted authority; the player's lifecycle receiver owns custody checks.
    if not bootstrap and native is not None and (not isinstance(native, dict) or native.get("pause_origin") in ("human", "fault")):
        raise DriverError("Native Pause or fault prevents player launch")
    if issued is not None:
        if (not isinstance(native, dict) or native.get("paused") is not True
                or snapshot.get("operator_pause_generation") != issued["operator_pause_generation"]
                or snapshot.get("pause_generation") != issued["pause_generation"]
                or any(native.get(key) != issued[key] for key in
                    ("session", "revision", "takeover_generation", "pause_origin"))
                or not isinstance(native.get("boundary"), dict)
                or native["boundary"].get("id") != issued["boundary_id"]):
            raise DriverError("Current controller/native Pause binding differs from issuance")


def _budget(status: dict, *, allow_unmeasured_game: bool = False) -> None:
    remaining = status.get("remaining_limits", {})
    if not isinstance(remaining, dict) or status.get("clock_valid") is not True or any(
            not (allow_unmeasured_game and key == "game_seconds" and key in remaining and remaining[key] is None)
            and (type(remaining.get(key)) not in (int, float)
                or not math.isfinite(remaining[key]) or remaining[key] <= 0) for key in _LIMITS):
        raise DriverError("Mission clock or original remaining budget is invalid")


def _handoff_status(status: dict) -> dict:
    if status.get("phase") != "handoff" or status.get("pause_cause") != "internal_handoff":
        raise DriverError("Mission is not in an internal handoff")
    _budget(status)
    try:
        issued = validate_handoff_result(status.get("progress"))
    except (ValueError, TypeError):
        raise DriverError("Canonical progress is not a valid handoff issuance") from None
    if (issued["mission_id"] != status["mission_id"] or issued["epoch"] != status.get("epoch")
            or issued["original_player_id"] != status.get("actor_id")
            or status.get("player_id") != status.get("actor_id")
            or issued["pause_origin"] in ("human", "fault")):
        raise DriverError("Handoff issuance does not match the current original actor and epoch")
    return issued


def _issuance(client: MissionClient, issued: dict, deadline: float) -> dict:
    _remaining(deadline)
    envelope = client.collect(issued["mission_id"], issued["handoff_id"], wait_seconds=0)
    _remaining(deadline)
    response = envelope.get("response") or {}
    if not isinstance(response, dict):
        raise DriverError("Collected handoff response is invalid")
    operation = response.get("operation") or {}
    if not isinstance(operation, dict):
        raise DriverError("Collected handoff operation is invalid")
    request = operation.get("request") or {}
    if not isinstance(request, dict):
        raise DriverError("Collected handoff request is invalid")
    try:
        result = validate_handoff_result(operation.get("result"))
    except (ValueError, TypeError):
        raise DriverError("Collected result is not a valid handoff issuance") from None
    if (envelope.get("transport") != "delivered" or envelope.get("settled") is not True
            or envelope.get("operation_id") != issued["handoff_id"]
            or response.get("status") != "accepted" or operation.get("state") != "completed"
            or request.get("kind") != "handoff" or request.get("mission_id") != issued["mission_id"]
            or request.get("request_id") != issued["handoff_id"]
            or request.get("epoch") != issued["epoch"] - 1
            or request.get("successor_role") != issued["successor_role"]
            or request.get("checkpoint_ids") != issued["checkpoint_ids"]
            or request.get("unfinished_work_ids") != issued["unfinished_work_ids"] or result != issued):
        raise DriverError("Collected handoff is uncertain or contradicts canonical issuance")
    return result


def run_campaign(*, root: Path, run_dir: Path, mission_id: str, model: str,
                 effort: str, timeout_seconds: float, original_thread: str | None = None,
                 codex: str = DEFAULT_CODEX) -> dict:
    """Run frozen hosts; return observed terminal phase or an incomplete report."""
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise DriverError("timeout_seconds must be positive and finite")
    deadline = time.monotonic() + timeout_seconds
    root, run = root.resolve(strict=True), run_dir.resolve(strict=True)
    campaigns = (root / ".runtime" / "campaigns").resolve(strict=True)
    if not root.is_dir() or not run.is_dir() or run == campaigns or not run.is_relative_to(campaigns):
        raise DriverError("run-dir must be an existing run under root/.runtime/campaigns")
    preparation = run / "preparation"
    if not preparation.is_dir():
        raise DriverError("Run preparation directory does not exist")
    frozen = run / "frozen"
    configuration = json.loads(_read(frozen / "player-host-configuration.json"))
    if not isinstance(configuration, dict) or configuration.keys() - _CONFIG_KEYS:
        raise DriverError("Frozen configuration must contain only known player MCP settings")
    # Validate/flatten before reserving any output or launching a process.
    list(_flags(configuration))
    original_prompt = _read(frozen / "original-player-prompt.txt")
    successor_brief = _read(frozen / "successor-player-brief.txt")
    paths = {"driver-report.json": preparation / "driver-report.json",
        "driver-initial-status.json": preparation / "driver-initial-status.json",
        "driver-handoff-issuance.json": preparation / "driver-handoff-issuance.json",
        "driver-successor-assignment.json": preparation / "driver-successor-assignment.json",
        "driver-successor-admission-status.json": preparation / "driver-successor-admission-status.json"}
    for role in ("original", "successor"):
        for suffix in ("-prompt.txt", "-argv.json", "-process.json", "-receipt.json", ".stderr", "-status.json"):
            name = f"driver-{role}{suffix}"
            paths[name] = preparation / name
        for suffix in (".jsonl", "-final.txt"):
            name = f"driver-{role}{suffix}"
            paths[name] = run / name
    # Reserve every name with exclusive creation before starting either host.
    # A collision leaves existing evidence intact; a partial reservation remains
    # a visible failed attempt, never permission to retry with the same names.
    with ExitStack() as stack:
        streams = {name: stack.enter_context(path.open("x")) for name, path in paths.items()}
        report = dict(mission_id=mission_id, outcome="incomplete", phase=None, exit_code=1,
            hosts=[], native_cleanup_claimed=False, acceptance_claimed=False)
        try:
            client = _DeadlineClient(root, deadline)
            initial_snapshot = _status(client, mission_id, deadline)
            _write(streams["driver-initial-status.json"], initial_snapshot)
            _launch_guard(initial_snapshot)
            initial = initial_snapshot["mission"]
            report["phase"] = initial.get("phase")
            if (initial.get("phase") not in ("admitted", "active")
                    or initial.get("pause_cause") not in ("internal_bootstrap", "internal_lifecycle",
                        "internal_recovery", "internal_handoff")
                    or not isinstance(initial.get("actor_id"), str)
                    or not initial["actor_id"] or initial.get("player_id") != initial["actor_id"]):
                raise DriverError("Original player requires an admitted or active unpaused mission")
            _budget(initial, allow_unmeasured_game=initial["phase"] == "admitted")
            prompt = original_prompt
            for role in ("original", "successor"):
                args = _argv(root, run, role, configuration, model=model, effort=effort,
                    codex=codex, thread=original_thread if role == "original" else None)
                receipt = _host(role, args, prompt, root, streams, deadline)
                report["hosts"].append(dict(role=role, **receipt))
                if receipt["returncode"] != 0 or receipt["timed_out"] or receipt["interrupted"] or "error_type" in receipt:
                    raise DriverError("Player host did not exit normally with code zero")
                snapshot = _status(client, mission_id, deadline)
                _write(streams[f"driver-{role}-status.json"], snapshot)
                status = snapshot["mission"]
                report["phase"] = status.get("phase")
                if status.get("phase") in TERMINAL:
                    report.update(outcome="terminal", exit_code=0)
                    break
                if role == "successor":
                    raise DriverError("Successor left a nonterminal mission; no further host is permitted")
                canonical = _handoff_status(status)
                _launch_guard(snapshot, canonical)
                issued = _issuance(client, canonical, deadline)
                if issued["original_player_id"] != initial["actor_id"]:
                    raise DriverError("Handoff original actor differs from initial assignment")
                _write(streams["driver-handoff-issuance.json"], issued)
                current_snapshot = _status(client, mission_id, deadline)
                _write(streams["driver-successor-admission-status.json"], current_snapshot)
                _launch_guard(current_snapshot, issued)
                current = current_snapshot["mission"]
                report["phase"] = current.get("phase")
                if _handoff_status(current) != issued:
                    raise DriverError("Handoff changed before successor launch")
                successor_id = "successor-" + uuid.uuid4().hex
                if successor_id == issued["original_player_id"]:
                    raise DriverError("Generated successor identity equals the original actor")
                assignment = dict(mission_id=mission_id, actor_id=successor_id,
                    actor_role=issued["successor_role"], handoff_id=issued["handoff_id"],
                    epoch=issued["epoch"], issuance_path=str(paths["driver-handoff-issuance.json"]))
                _write(streams["driver-successor-assignment.json"], assignment)
                prompt = successor_brief + "\n\nMechanical player assignment:\n" + json.dumps(assignment, indent=2) + "\n"
                _remaining(deadline)
        except (DriverError, MissionClientError) as error:
            report["reason"] = str(error)
        except (OSError, ValueError, TypeError, KeyError) as error:
            # Never print transport discovery, credentials or arbitrary bodies.
            report["reason"] = "Driver evidence unavailable or invalid"
            report["error_type"] = type(error).__name__
        finally:
            _write(streams["driver-report.json"], report)
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--mission-id", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument("--original-thread")
    parser.add_argument("--codex", default=DEFAULT_CODEX)
    args = parser.parse_args()
    try:
        report = run_campaign(**vars(args))
    except (OSError, ValueError, TypeError):
        report = dict(outcome="incomplete", exit_code=1,
            reason="Driver setup refused; frozen inputs or exclusive output names unavailable")
    print(json.dumps(report, allow_nan=False))
    raise SystemExit(report["exit_code"])


if __name__ == "__main__":
    main()
