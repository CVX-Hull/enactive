"""Passive, bounded projection of the campaign driver's existing host receipts.

These reports describe observed host events, never current process liveness,
mission authority, native cleanup or permission to launch another actor.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any


def _record(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("rb") as stream:
            data = stream.read(1_048_577)
        if len(data) > 1_048_576:
            return None
        if not data.strip():
            return {}
        value = json.loads(data)
        return value if isinstance(value, dict) else None
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, RecursionError):
        # Empty precreated outputs, partial writes and unavailable files are
        # ordinary uncertainty. Never publish their contents or local paths.
        return None


def _identity(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value) is not None


def _clock(value: Any) -> bool:
    return type(value) in (int, float) and 0 < value <= sys.float_info.max


def _receipt_fields(value: dict[str, Any]) -> tuple:
    return tuple(value.get(key) for key in ("start", "end", "returncode", "timed_out", "interrupted")) + (
        value.get("host_exit_unresolved", False),)


def _host(preparation: Path, role: str, actor_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    process = _record(preparation / f"driver-{role}-process.json") or {}
    receipt = _record(preparation / f"driver-{role}-receipt.json") or {}
    evidence = dict(role=role, actor_id=actor_id, state="unreported", returncode=None)
    start = process.get("start")
    if _clock(start):
        evidence.update(state="launch_reported", started_at=start)
    if not receipt:
        return evidence, receipt
    began, ended = receipt.get("start"), receipt.get("end")
    code = receipt.get("returncode")
    if (not _clock(began) or not _clock(ended) or ended < began
            or type(receipt.get("timed_out")) is not bool
            or type(receipt.get("interrupted")) is not bool
            or type(receipt.get("host_exit_unresolved", False)) is not bool
            or code is not None and type(code) is not int):
        return evidence, {}
    if not _clock(start) or start != began:
        return dict(role=role, actor_id=actor_id, state="unreported", returncode=None), {}
    state = ("exit_unresolved" if code is None or receipt.get("host_exit_unresolved") else
        "timed_out" if receipt["timed_out"] else "interrupted" if receipt["interrupted"] else "exited")
    evidence.update(state=state, ended_at=ended, returncode=code)
    return evidence, receipt


def deciding_host_status(root: Path, mission: dict[str, Any] | None) -> dict[str, Any]:
    """Read only the exact mission's canonical driver outputs, with no discovery."""
    unknown = dict(role=None, state="unreported", returncode=None)
    result = dict(grants_authority=False, current=unknown, original=None,
        driver=dict(outcome="unreported", no_continuing_host_reported=False))
    if not isinstance(mission, dict) or not all(_identity(mission.get(key)) for key in ("mission_id", "actor_id")):
        return result
    mission_id, actor_id = mission["mission_id"], mission["actor_id"]
    result.update(mission_id=mission_id, actor_id=actor_id)
    preparation = root / ".runtime" / "campaigns" / mission_id / "preparation"
    initial = (_record(preparation / "driver-initial-status.json") or {}).get("mission")
    if (not isinstance(initial, dict) or initial.get("mission_id") != mission_id
            or not _identity(initial.get("actor_id"))):
        return result
    original, original_receipt = _host(preparation, "original", initial["actor_id"])
    result["original"] = original
    hosts = {"original": (original, original_receipt)}
    if actor_id == initial["actor_id"]:
        result["current"] = original
    assignment = _record(preparation / "driver-successor-assignment.json") or {}
    if (assignment.get("mission_id") == mission_id and _identity(assignment.get("actor_id"))
            and assignment["actor_id"] != initial["actor_id"]):
        successor = _host(preparation, "successor", assignment["actor_id"])
        hosts["successor"] = successor
        if actor_id == assignment["actor_id"]:
            result["current"] = successor[0]
    report = _record(preparation / "driver-report.json") or {}
    if (report.get("mission_id") != mission_id or report.get("outcome") not in ("incomplete", "terminal")
            or type(report.get("exit_code")) is not int):
        return result
    result["driver"]["outcome"] = report["outcome"]
    observed = report.get("hosts")
    if not isinstance(observed, list) or not 1 <= len(observed) <= 2:
        return result
    roles = []
    for host in observed:
        if not isinstance(host, dict) or not isinstance(host.get("role"), str) or host["role"] not in hosts:
            return result
        role = host["role"]
        evidence, receipt = hosts[role]
        if (evidence["state"] not in ("exited", "timed_out", "interrupted")
                or _receipt_fields(host) != _receipt_fields(receipt)):
            return result
        roles.append(role)
    # A final report must cover every launch, including a successor which has
    # not adopted its assignment. An unbound successor cannot prove closure.
    if roles != ["original", "successor"][:len(roles)]:
        return result
    successor_process = _record(preparation / "driver-successor-process.json")
    successor_receipt = _record(preparation / "driver-successor-receipt.json")
    if (successor_process is None or successor_receipt is None
            or (successor_process or successor_receipt) and "successor" not in roles):
        return result
    result["driver"]["no_continuing_host_reported"] = True
    return result
