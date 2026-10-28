"""Custody for one frozen finite campaign; no tactics, replay or normal-ending input.

Run ``python -m tools.campaign_run --root ROOT --mission-id ID``. Immutable
campaign-run/1 manifest/admission/context data belongs in .runtime/campaigns/ID/
frozen. Git and the maintained Pi validator supply source/configuration checks;
this thin custodian adds bounded child custody and advisory cleanup evidence.
The maintainer owns this integration; replace it when the driver owns admission
and controller lifetime. Development check declarations are not acceptance.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from harness.gameplay.mission_contracts import MissionAdmission
from harness.player_tools import PlayerTools
from tools.campaign_player import TERMINAL, _DeadlineClient

STARTUP_SECONDS = 30.0
SHUTDOWN_SECONDS = 60.0
_INPUTS = ("admission.json", "player-pi-configuration.json", "player-host-configuration.json",
    "pi-player-context.txt", "original-player-prompt.txt", "successor-player-brief.txt")
_ARTIFACTS = ("custodian-receipt.json", "custodian-clock.json", "custodian-start.json", "custodian-admission.json",
    "custodian-final-status.json", "custodian-stop.json")


class RunError(ValueError):
    """Fixed credential-free refusal; never include external bodies or exceptions."""


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_048_576:
        raise RunError("Frozen data or evidence is unavailable")
    value = path.read_bytes()
    if len(value) > 1_048_576:
        raise RunError("Frozen data or evidence exceeds its bound")
    return value


def _json(path: Path) -> dict:
    value = json.loads(_read(path))
    if type(value) is not dict:
        raise RunError("Expected a JSON object")
    return value


def _redacted(value: dict) -> dict:
    secret = os.environ.get("DEEPINFRA_API_KEY")
    def clean(item):
        if isinstance(item, str):
            return item.replace(secret, "[REDACTED]") if secret else item
        if isinstance(item, dict):
            return {clean(key): clean(part) for key, part in item.items()}
        if isinstance(item, list):
            return [clean(part) for part in item]
        return item
    return clean(value)


def _write(stream, value: dict) -> None:
    json.dump(_redacted(value), stream, indent=2, allow_nan=False)
    stream.write("\n")
    stream.flush()


def _positive(value) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value) and value > 0
    except OverflowError:
        return False


def _clean_env() -> dict[str, str]:
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8"}


def _source(root: Path, expected: str) -> None:
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root, env=_clean_env(),
            stderr=subprocess.DEVNULL, timeout=5).decode().strip()
    if (re.fullmatch(r"[0-9a-f]{40}", expected or "") is None
            or git("rev-parse", "HEAD") != expected or git("status", "--porcelain")):
        raise RunError("Run requires the exact clean committed checkpoint")


def _preflight(root: Path, mission_id: str) -> tuple[Path, dict, dict]:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", mission_id) is None:
        raise RunError("Invalid mission identity")
    run = root / ".runtime" / "campaigns" / mission_id
    frozen, prep = run / "frozen", run / "preparation"
    for path in (root / ".runtime", root / ".runtime" / "campaigns", run, frozen, prep):
        if path.is_symlink() or not path.is_dir():
            raise RunError("Run requires existing project-local directories")
    profile = _json(frozen / "manifest.json")
    if (profile.get("schema") != "campaign-run/1" or profile.get("mission_id") != mission_id
            or type(profile.get("max_hosts")) is not int or profile["max_hosts"] not in (1, 2)):
        raise RunError("Unsupported frozen run manifest")
    files = profile.get("files")
    if type(files) is not dict or set(files) != set(_INPUTS):
        raise RunError("Manifest must pin every current frozen driver input")
    for name in _INPUTS:
        if hashlib.sha256(_read(frozen / name)).hexdigest() != files[name]:
            raise RunError("Frozen input differs from its manifest")
    # Data only: no private executable framework in this freeze.
    if {path.name for path in frozen.iterdir()} != {*_INPUTS, "manifest.json"}:
        raise RunError("Frozen run directory must contain only declared data")
    current = MissionAdmission.from_dict(_json(frozen / "admission.json"))
    admission = current.to_dict()
    source = profile.get("source_commit")
    if current.mission_id != mission_id or current.configuration.source_commit != source:
        raise RunError("Admission and run source/identity differ")
    _source(root, source)
    validation = profile.get("validation", {})
    if type(validation) is not dict:
        raise RunError("Expected frozen development evidence declarations")
    for kind in ("fast", "focused"):
        check = validation.get(kind, {})
        if type(check) is not dict or check.get("passed") is not True or check.get("source_commit") != source:
            raise RunError("Declare passing exact-source fast and focused development evidence")
    begin, ending = (profile.get(key) for key in
        ("begin_normal_ending_seconds", "complete_normal_ending_before_seconds"))
    if (not _positive(begin) or not _positive(ending) or begin >= ending
            or ending + SHUTDOWN_SECONDS > current.limits.wall_seconds
            or ending > current.limits.wall_seconds - current.cleanup_reserve.wall_seconds):
        raise RunError("Frozen ending and shutdown reserves do not fit the original mission")
    route = _json(frozen / "player-pi-configuration.json")
    node = profile.get("node", "node")
    effort = profile.get("effort")
    if (not isinstance(node, str) or not node or route.get("api_key_env") != "DEEPINFRA_API_KEY"
            or type(route.get("model")) is not dict
            or route["model"].get("id") != current.configuration.model):
        raise RunError("Frozen route differs from the admission or credential route")
    # Reuse the maintained host's pure validator; this executes no provider work.
    validator = ("import {readFileSync} from 'node:fs'; "
        "import {validateConfiguration} from './tools/player_host/host.mjs'; "
        "const c=JSON.parse(readFileSync(process.argv[1],'utf8')); "
        "validateConfiguration(c,process.argv[2],process.argv[3]);")
    subprocess.run([node, "--input-type=module", "-e", validator,
        str(frozen / "player-pi-configuration.json"), current.configuration.model, effort],
        cwd=root, env=_clean_env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=5, check=True)
    host = _json(frozen / "player-host-configuration.json")
    if (host.get("args") != ["-m", "harness.player_mcp"] or host.get("cwd") != str(root)
            or host.get("command") != sys.executable or host.get("enabled") is not True
            or host.get("required") is not True):
        raise RunError("Frozen MCP entry must use this interpreter and maintained player module")
    provider = profile.get("provider", {})
    if type(provider) is not dict:
        raise RunError("Expected frozen provider reservation")
    names = ("prior_requests", "new_requests_max", "total_requests_max")
    if (any(type(provider.get(key)) is not int or provider[key] < 0 for key in names)
            or provider["new_requests_max"] != route["max_requests"] * profile["max_hosts"]
            or provider["total_requests_max"] != provider["prior_requests"] + provider["new_requests_max"]):
        raise RunError("Frozen provider request reservation is inconsistent")
    try:
        prior, per, total, limit = (Decimal(provider[key]) for key in
            ("prior_reservation_usd", "per_request_reservation_usd", "total_reservation_usd", "reservation_limit_usd"))
        if (any(not value.is_finite() or value < 0 for value in (prior, per, total, limit))
                or per <= 0 or prior + per * provider["new_requests_max"] != total or total > limit):
            raise RunError("Frozen provider monetary reservation is inconsistent")
    except (InvalidOperation, KeyError, TypeError):
        raise RunError("Frozen provider monetary reservation is invalid") from None
    if os.path.lexists(root / ".runtime" / "missions" / mission_id):
        raise RunError("Prior mission exists; never reopen or resume it")
    staged = root / ".runtime" / "mission-requests"
    if staged.exists():
        total_bytes = 0
        for index, path in enumerate(staged.iterdir()):
            if index >= 10_000:
                raise RunError("Prior admission inspection exceeds its bound")
            data = _read(path)
            total_bytes += len(data)
            if total_bytes > 16_777_216:
                raise RunError("Prior admission inspection exceeds its bound")
            item = json.loads(data)
            if type(item) is not dict:
                raise RunError("Prior admission stage is invalid")
            if item.get("kind") == "start" and item.get("admission", {}).get("mission_id") == mission_id:
                raise RunError("Prior admission intent exists; collection only, no new run")
    # The maintained driver exclusively reserves these later. Refuse existing
    # evidence before admission as well; it must never become a resume switch.
    driver_paths = [prep / f"driver-{name}.json" for name in
        ("report", "initial-status", "handoff-issuance", "successor-assignment", "successor-admission-status")]
    for role in ("original", "successor"):
        driver_paths += [prep / f"driver-{role}{suffix}" for suffix in
            ("-prompt.txt", "-argv.json", "-process.json", "-receipt.json", ".stderr", "-status.json")]
        driver_paths += [run / f"driver-{role}{suffix}" for suffix in (".jsonl", "-final.txt")]
    if any(os.path.lexists(path) for path in driver_paths):
        raise RunError("Prior driver evidence exists; no replay")
    return run, profile, admission


def _stop_child(child: subprocess.Popen, *, deadline: float, first_wait: float) -> dict:
    """Stop only this retained child; nested driver cleanup gets more than 6s."""
    receipt = {"signals": [], "returncode": child.poll(), "exit_unresolved": False}
    for sig, wait in ((signal.SIGINT, first_wait), (signal.SIGTERM, 2.0), (signal.SIGKILL, 1.0)):
        if child.poll() is not None:
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            child.send_signal(sig)
            receipt["signals"].append(sig.name)
        except ProcessLookupError:
            pass
        try:
            child.wait(timeout=min(wait, remaining))
        except subprocess.TimeoutExpired:
            continue
    receipt.update(returncode=child.poll(), exit_unresolved=child.poll() is None)
    return receipt


@contextmanager
def _signals():
    previous = {}
    interrupted = []
    def stop(signum, frame):
        interrupted.append(signal.Signals(signum).name)
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, stop)
        yield interrupted
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def _admitted(result: dict, request_id: str, mission_id: str) -> bool:
    response = result.get("response") or {}
    operation = response.get("operation") or {}
    mission = (result.get("next_snapshot") or {}).get("mission") or {}
    return (result.get("transport") == "delivered" and result.get("settled") is True
        and result.get("operation_id") == request_id and response.get("status") == "accepted"
        and operation.get("request_id") == request_id and operation.get("kind") == "start"
        and operation.get("state") == "completed" and type(operation.get("result")) is dict
        and operation["result"].get("admitted") is True
        and mission.get("mission_id") == mission_id and mission.get("phase") == "admitted")


def run_campaign(*, root: Path, mission_id: str, port: int = 8766) -> dict:
    """One fresh admission, one finite driver, exact owned-child cleanup receipts."""
    root = root.resolve(strict=True)
    if type(port) is not int or not 1 <= port <= 65535:
        raise RunError("Invalid controller port")
    run, profile, admission = _preflight(root, mission_id)
    if not os.environ.get("DEEPINFRA_API_KEY"):
        raise RunError("Supplied provider credential is unavailable; no admission")
    with ExitStack() as stack:
        # Exclusive creation fences retries even after setup/refusal/partial output.
        streams = {name: stack.enter_context((run / "preparation" / name).open("x")) for name in _ARTIFACTS}
        interrupted = stack.enter_context(_signals())
        receipt = {"mission_id": mission_id, "started_timestamp": time.time(), "outcome": "incomplete",
            "children": {}, "acceptance_claimed": False, "native_absence_verified": False,
            "normal_ending_claimed": False, "shutdown_receipt": None, "signals": interrupted}
        controller = driver = client = player = None
        boot_id = None
        admitted = False
        ending_deadline = None
        cleanup_deadline = time.monotonic() + STARTUP_SECONDS + SHUTDOWN_SECONDS
        def launch(name, argv, env):
            child = subprocess.Popen(argv, cwd=root, env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            receipt["children"][name] = {"pid": child.pid, "started_timestamp": time.time(),
                "console_output": "suppressed; use maintained structured driver evidence"}
            return child
        try:
            old = None
            discovery = root / ".runtime" / "bridge" / "controller.json"
            if discovery.exists():
                old = _json(discovery).get("controller_boot_id")
            controller = launch("controller", [sys.executable, "-m", "harness", "serve",
                "--port", str(port), "--timeout", "15"], _clean_env())
            startup_deadline = time.monotonic() + STARTUP_SECONDS
            client = _DeadlineClient(root, startup_deadline)
            while time.monotonic() < startup_deadline:
                if interrupted or controller.poll() is not None:
                    raise RunError("Owned controller interrupted or exited before admission")
                try:
                    current = _json(discovery)
                    candidate = current.get("controller_boot_id")
                    if (current.get("port") == port and current.get("controller_pid") == controller.pid
                            and re.fullmatch(r"[0-9a-f]{32}", candidate or "")
                            and candidate != old):
                        snapshot = client.status()
                        if snapshot.get("controller_boot_id") != candidate:
                            raise RunError("Controller status differs from owned discovery")
                        if snapshot.get("mission") is not None:
                            raise RunError("Owned controller already has an admission")
                        boot_id = candidate
                        break
                except (OSError, ValueError):
                    pass
                time.sleep(.1)
            if boot_id is None:
                raise RunError("Fresh owned controller discovery unavailable")
            receipt["controller_boot_id"] = boot_id
            if interrupted:
                raise RunError("Custodian cancelled before admission")
            # All actors share this original anchor. Frozen files remain untouched.
            anchor, wall = time.monotonic(), time.time()
            ending_deadline = anchor + profile["complete_normal_ending_before_seconds"]
            cleanup_deadline = ending_deadline + SHUTDOWN_SECONDS
            client.deadline = ending_deadline
            clocks = {"admission_anchor_timestamp": wall,
                "admission_anchor_utc": datetime.fromtimestamp(wall, timezone.utc).isoformat(),
                "begin_normal_ending_timestamp": wall + profile["begin_normal_ending_seconds"],
                "complete_normal_ending_before_timestamp": wall + profile["complete_normal_ending_before_seconds"],
                "custodian_cleanup_before_timestamp": wall + profile["complete_normal_ending_before_seconds"] + SHUTDOWN_SECONDS}
            _write(streams["custodian-clock.json"], clocks)
            player = PlayerTools(client)
            arguments, collection = player.model_arguments("enactive_start", {"admission": admission})
            _write(streams["custodian-start.json"], {"arguments": arguments, "collection": collection})
            result, _ = player.call("enactive_start", arguments, present_image=False)
            _write(streams["custodian-admission.json"], result)
            admitted = _admitted(result, arguments["request_id"], mission_id)
            if not admitted:
                raise RunError("Original admission acknowledgement is refused or uncertain; never replay")
            remaining = ending_deadline - time.monotonic()
            if interrupted or remaining <= 0 or controller.poll() is not None:
                raise RunError("Original campaign deadline or custody exhausted before driver launch")
            driver_env = {**_clean_env(), "DEEPINFRA_API_KEY": os.environ["DEEPINFRA_API_KEY"]}
            driver = launch("driver", [sys.executable, "-m", "tools.campaign_player", "--root", str(root),
                "--run-dir", str(run), "--mission-id", mission_id, "--model", admission["configuration"]["model"],
                "--effort", profile["effort"], "--max-hosts", str(profile["max_hosts"]),
                "--node", profile.get("node", "node"), "--timeout-seconds", str(remaining)], driver_env)
            del driver_env
            while driver.poll() is None:
                if interrupted or time.monotonic() >= ending_deadline or controller.poll() is not None:
                    raise RunError("Campaign interrupted, ending deadline reached or owned controller lost")
                time.sleep(min(.1, max(0, ending_deadline - time.monotonic())))
            if driver.returncode != 0:
                raise RunError("Campaign driver failed")
            final = client.status()
            _write(streams["custodian-final-status.json"], final)
            mission = final.get("mission") or {}
            if mission.get("mission_id") != mission_id or mission.get("phase") not in TERMINAL:
                raise RunError("Driver left no observed terminal mission")
            receipt.update(outcome="terminal", phase=mission["phase"])
        except (Exception, KeyboardInterrupt) as exc:
            receipt["error_type"] = type(exc).__name__
            receipt["reason"] = str(exc) if isinstance(exc, RunError) else "Campaign custody or evidence unavailable"
        finally:
            # Driver owns nested deciding hosts. Give its exact handle time to
            # settle them before asking the controller writer to close native.
            if driver is not None:
                receipt["children"]["driver"].update(_stop_child(driver,
                    deadline=cleanup_deadline, first_wait=10.0))
            if controller is not None and controller.poll() is None and player is not None:
                try:
                    client.deadline = min(cleanup_deadline, time.monotonic() + 15)
                    snapshot, _ = player.snapshot()
                    mission = snapshot.get("mission") or {}
                    if mission.get("mission_id") == mission_id and mission.get("phase") not in TERMINAL:
                        arguments, collection = player.model_arguments("enactive_stop", {
                            "snapshot_id": snapshot["snapshot_id"], "intent": {
                                "reason": "Exceptional custodian cancellation/failure/deadline; no normal ending claimed"}})
                        result, _ = player.call("enactive_stop", arguments, present_image=False)
                        _write(streams["custodian-stop.json"], {"arguments": arguments,
                            "collection": collection, "result": result})
                        receipt["exceptional_stop"] = True
                except Exception as exc:
                    receipt["stop_error_type"] = type(exc).__name__
            if controller is not None:
                receipt["children"]["controller"].update(_stop_child(controller,
                    deadline=cleanup_deadline, first_wait=22.0))
                if controller.poll() is not None and boot_id is not None:
                    try:
                        shutdown = _json(root / ".runtime" / "bridge" / f"mission-shutdown-{boot_id}.json")
                        if shutdown.get("controller_boot_id") != boot_id or shutdown.get("grants_authority") is not False:
                            raise RunError("Shutdown receipt does not match owned controller")
                        cleanup = shutdown.get("cleanup") or {}
                        receipt["shutdown_receipt"] = shutdown
                        receipt["native_absence_verified"] = (cleanup.get("writer_settled") is True
                            and cleanup.get("native_absence_verified") is True)
                    except (OSError, ValueError, TypeError):
                        receipt["native_cleanup_unknown"] = True
            receipt["deciding_hosts_quiescent"] = driver is None
            if driver is not None and driver.poll() is not None:
                try:
                    report = _json(run / "preparation" / "driver-report.json")
                    hosts = report.get("hosts")
                    receipt["deciding_hosts_quiescent"] = (type(hosts) is list and all(
                        type(host) is dict and type(host.get("returncode")) is int
                        and host.get("host_exit_unresolved", False) is False for host in hosts))
                except (OSError, ValueError, TypeError):
                    pass
            receipt["native_cleanup_unknown"] = not receipt["native_absence_verified"]
            receipt["admission_acknowledged"] = admitted
            receipt["ended_timestamp"] = time.time()
            _write(streams["custodian-receipt.json"], receipt)
        return _redacted(receipt)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--mission-id", required=True)
    parser.add_argument("--port", type=int, default=8766)
    try:
        receipt = run_campaign(**vars(parser.parse_args()))
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        receipt = {"outcome": "incomplete", "reason": "Frozen run setup refused; no retry or admission implied",
            "native_absence_verified": False, "acceptance_claimed": False}
    print(json.dumps(_redacted(receipt), allow_nan=False))
    raise SystemExit(0 if receipt["outcome"] == "terminal" and receipt["native_absence_verified"]
        and receipt.get("deciding_hosts_quiescent") is True else 1)


if __name__ == "__main__":
    main()
