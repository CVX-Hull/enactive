"""File-transport tests. This fake bridge is not evidence of CDDA acceptance."""
from concurrent.futures import ThreadPoolExecutor
import json
import copy
import hashlib
import uuid
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from harness.controller import Controller, ControlError, atomic_json, read_json, validate_state, validate_control_request, validate_control_response


def state(request_id="", *, revision=1, **changes):
    value = {"protocol": 3, "id": request_id, "session": "game-test", "revision": revision,
             "category": "DEFAULTMODE", "actions": ["UP", "DOWN", "LEFT", "RIGHT", "INVENTORY"],
             "status": "ready", "error": "", "paused": False,
             "timestamp_ms": int(time.time() * 1000), "frame_ok": True, "in_game": True,
             "frame": "frame-game-test-1.png",
             "boundary": {"kind": "normal_play", "id": "game-test-b1", "control_generation": 0,
                          "recovery_operations": [], "interrupt_request_id": None},
             "scene": {"position": [0, 0, 0], "turn": 1, "visible_creatures": [],
                       "neighbors": [{"dx": dx, "dy": dy, "visible": True,
                                      "terrain": "t_floor", "furniture": "f_null"}
                                     for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]]}}
    value.update(changes)
    return value


class FakeBridge:
    """Exercises real atomic files and threads, never claims to emulate game rules."""
    def __init__(self, controller, behavior=None, before_gate=None):
        self.bridge = controller.bridge
        self.behavior = behavior
        self.before_gate = before_gate
        self.delivered = []
        self.value = state(paused=True)
        self.requests = []
        self.failures = []
        self.stopped = threading.Event()
        self.claimed = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stopped.set()
        self.thread.join(2)
        if self.failures:
            raise self.failures[0]

    def publish(self, value):
        atomic_json(self.bridge / "response.json", value)
        atomic_json(self.bridge / "state.json", value)

    def run(self):
        try:
            while not self.stopped.wait(0.003):
                try:
                    (self.bridge / "request.json").rename(self.bridge / "claimed.json")
                except FileNotFoundError:
                    continue
                request = read_json(self.bridge / "claimed.json")
                self.requests.append(request)
                self.claimed.set()
                self.value["id"] = request["id"]
                self.value["timestamp_ms"] = int(time.time() * 1000)
                self.value["paused"] = (self.bridge / "pause").exists()
                kind = request["kind"]
                if self.before_gate is not None:
                    self.before_gate(self, request)
                if kind in {"key", "action", "resume"} and (
                        request.get("authority") != read_json(self.bridge / "authority.json")
                        or self.value["boundary"]["kind"] not in {"normal_play", "menu"}):
                    self.value.update(status="rejected", error="authority revoked or unsupported boundary")
                    (self.bridge / "claimed.json").unlink(missing_ok=True)
                    self.publish(self.value.copy())
                    continue
                if kind in {"key", "action", "resume"}:
                    self.delivered.append(request)
                if kind == "resume":
                    (self.bridge / "pause").unlink(missing_ok=True)
                    self.value["paused"] = False
                    self.value["boundary"]["control_generation"] += 1
                    self.value["revision"] += 1
                if kind in {"key", "action"}:
                    self.value["revision"] += 1
                    self.value["status"] = "dispatched"
                    self.value["frame_ok"] = False
                    self.publish(self.value.copy())
                    self.value["status"] = "ready"
                    self.value["frame_ok"] = True
                    movement = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
                    if request.get("action") in movement:
                        dx, dy = movement[request["action"]]
                        self.value["scene"]["position"][0] += dx
                        self.value["scene"]["position"][1] += dy
                publish = True if self.behavior is None else self.behavior(self, request)
                (self.bridge / "claimed.json").unlink(missing_ok=True)
                if publish:
                    self.publish(self.value.copy())
        except Exception as exc:
            self.failures.append(exc)


def recovery_state(kind="activity_poll", *, owner=None, generation=0, revision=3):
    operation = {"activity_poll": "request_interrupt", "interrupt_confirmation": "answer_interrupt",
                 "debug_prompt": "continue_debug_once"}.get(kind)
    return state(revision=revision, paused=True, scene=None, category="YESNO" if owner else "DEFAULTMODE",
                 boundary={"kind": kind, "id": f"prompt-{revision}", "control_generation": generation,
                           "recovery_operations": [operation] if operation else [], "interrupt_request_id": owner})


class ControlBridge:
    """Control-only file consumer; gates model transport races, not CDDA behavior."""
    def __init__(self, controller, *, before_claim=None, before_gate=None, after_commit=None, publish=True):
        self.controller = controller
        self.bridge = controller.bridge
        self.before_claim = before_claim
        self.before_gate = before_gate
        self.after_commit = after_commit
        self.publish_result = publish
        self.claimed = threading.Event()
        self.committed = threading.Event()
        self.stop = threading.Event()
        self.requests = []
        self.delivered = []
        self.failures = []
        self.thread = threading.Thread(target=self.run, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(3)
        if self.failures:
            raise self.failures[0]
        if self.thread.is_alive():
            raise AssertionError("control fixture failed to stop")

    def run(self):
        try:
            while not self.stop.wait(0.003):
                inbox = self.bridge / "control.json"
                if not inbox.exists():
                    continue
                if self.before_claim:
                    self.before_claim(self)
                try:
                    inbox.rename(self.bridge / "control-claimed.json")
                except FileNotFoundError:
                    continue
                request = read_json(self.bridge / "control-claimed.json")
                validate_control_request(request)
                self.requests.append(request)
                self.claimed.set()
                if self.before_gate:
                    self.before_gate(self, request)
                value = copy.deepcopy(self.controller.state)
                result = "rejected"
                if request["authority"] == read_json(self.bridge / "authority.json"):
                    self.delivered.append(request)
                    self.committed.set()
                    generation = request["control_generation"] + 1
                    if request["kind"] == "request_interrupt":
                        value = recovery_state("interrupt_confirmation", owner=request["id"],
                                               generation=generation, revision=value["revision"] + 1)
                        result = "prompt_opened"
                    else:
                        value.update(paused=True, revision=value["revision"] + 1, frame_ok=False, frame="")
                        value["boundary"]["control_generation"] = generation
                        result = "answer_delivered" if request["kind"] == "answer_interrupt" else "dismissal_delivered"
                    if self.after_commit:
                        self.after_commit(self, request)
                response = {"protocol": 3, "id": request["id"], "status": result,
                            "error": "revoked" if result == "rejected" else "", "state": value}
                (self.bridge / "control-claimed.json").unlink(missing_ok=True)
                if self.publish_result:
                    atomic_json(self.bridge / "state.json", value)
                    atomic_json(self.bridge / "control-response.json", response)
        except BaseException as exc:
            self.failures.append(exc)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        # Functional exchanges use real files/threads on shared CI runners.
        # Short deadline behavior is exercised with explicit per-call timeouts below.
        self.controller = Controller(self.root, timeout=2.0)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.controller.close)

    def ready(self):
        self.assertEqual(self.controller.execute("observe")["status"], "ready")
        self.assertEqual(self.controller.execute("resume")["status"], "ready")

    def expect(self):
        value = self.controller.state
        return {"expected_session": value["session"], "expected_revision": value["revision"]}

    def recovery_expect(self):
        value = self.controller.state
        result = {"expected_session": value["session"],
                  "expected_control_generation": value["boundary"]["control_generation"]}
        if value["boundary"]["kind"] != "activity_poll":
            result.update(expected_boundary_id=value["boundary"]["id"], expected_revision=value["revision"],
                          expected_frame=value["frame"])
        return result

    def test_control_envelopes_are_exact_v3_and_prompt_owner_is_mandatory(self):
        value = recovery_state("interrupt_confirmation", owner=str(uuid.uuid4()))
        validate_state(value)
        response = {"protocol": 3, "id": value["boundary"]["interrupt_request_id"],
                    "status": "prompt_opened", "error": "", "state": value}
        validate_control_response(response)
        for mutate in (lambda v: v.update(protocol=2), lambda v: v.update(extra=1),
                       lambda v: v["state"].update(frame_ok=False),
                       lambda v: v["state"]["boundary"].update(interrupt_request_id=None)):
            broken = copy.deepcopy(response)
            mutate(broken)
            with self.assertRaises(ControlError):
                validate_control_response(broken)
        request = {"protocol": 3, "id": str(uuid.uuid4()), "kind": "request_interrupt", "session": "world",
                   "control_generation": 1, "authority": {"controller_boot_id": "boot", "counter": 1},
                   "created_ms": 1000, "deadline_ms": 3000}
        validate_control_request(request)
        for change in ({"protocol": 2}, {"id": "not-uuid"}, {"deadline_ms": 2999},
                       {"created_ms": True}, {"control_generation": False}, {"extra": 1}):
            with self.subTest(change=change), self.assertRaises(ControlError):
                validate_control_request({**request, **change})

    def test_recovery_opens_owned_prompt_and_explicit_answer_stays_paused(self):
        self.controller.state = recovery_state()
        with ControlBridge(self.controller) as fake:
            opened = self.controller.recover("request_interrupt", **self.recovery_expect())
            self.assertEqual(opened["status"], "prompt_opened")
            self.assertEqual(self.controller.state["boundary"]["interrupt_request_id"], opened["id"])
            request = fake.requests[0]
            self.assertEqual(request["deadline_ms"] - request["created_ms"], 2000)
            self.assertEqual(set(request), {"protocol", "id", "kind", "session", "control_generation",
                                            "authority", "created_ms", "deadline_ms"})
            answered = self.controller.recover("answer_interrupt", **self.recovery_expect(),
                                               interrupt_request_id=opened["id"], choice="NO")
            self.assertEqual(answered["status"], "answer_delivered")
            self.assertEqual([r["kind"] for r in fake.delivered], ["request_interrupt", "answer_interrupt"])
            self.assertTrue(self.controller.pause_requested)
            self.assertTrue((fake.bridge / "pause").exists())
            self.assertIsNone(self.controller.control_pending)
            self.assertEqual(list(self.controller.control_admissions.glob("*.json")), [])
            self.assertFalse((fake.bridge / "response.json").exists())
        self.assertEqual(self.controller.execute("request_interrupt")["status"], "controller_error")

    def test_recovery_never_refreshes_stale_caller_or_exposes_arbitrary_debug_keys(self):
        self.controller.state = recovery_state("debug_prompt")
        expected = self.recovery_expect()
        with ControlBridge(self.controller) as fake:
            for change in ({"expected_session": "old"}, {"expected_control_generation": 1},
                           {"expected_boundary_id": "old"}, {"expected_revision": 99},
                           {"expected_frame": "old.png"}, {"key": "I"}):
                result = self.controller.recover("continue_debug_once", **{**expected, **change})
                self.assertEqual(result["status"], "controller_error")
            self.assertEqual(fake.requests, [])
            result = self.controller.recover("continue_debug_once", **expected)
            self.assertEqual(result["status"], "dismissal_delivered")
            self.assertNotIn("key", fake.requests[0])

    def test_control_pause_before_claim_after_claim_and_after_commit(self):
        for stage in ("before_claim", "before_gate", "after_commit"):
            self.controller.state = recovery_state("debug_prompt")
            def pause(*args):
                self.controller.pause()
            with self.subTest(stage=stage), ControlBridge(self.controller, **{stage: pause}) as fake:
                result = self.controller.recover("continue_debug_once", **self.recovery_expect())
                self.assertEqual(result["status"], "dismissal_delivered" if stage == "after_commit" else "rejected")
                self.assertEqual(len(fake.delivered), 1 if stage == "after_commit" else 0)
                self.assertTrue(self.controller.pause_requested)
                self.assertTrue((fake.bridge / "pause").exists())

    def test_control_writer_never_waits_for_gameplay_writer_or_retires_its_identity(self):
        entered = threading.Event()
        release = threading.Event()
        def hold(fake, request):
            if request["kind"] == "key":
                entered.set()
                self.assertTrue(release.wait(3))
        with FakeBridge(self.controller, before_gate=hold) as ordinary:
            self.ready()
            with ThreadPoolExecutor() as pool:
                pending = pool.submit(self.controller.execute, "key", key="x", **self.expect())
                self.assertTrue(entered.wait(2))
                original = self.controller.pending.copy()
                original_admission = self.controller.admissions / f'{original["id"]}.json'
                self.controller.state = recovery_state()
                try:
                    with ControlBridge(self.controller) as control:
                        result = self.controller.recover("request_interrupt", **self.recovery_expect())
                        self.assertEqual(result["status"], "prompt_opened")
                        self.assertEqual(self.controller.pending["id"], original["id"])
                        self.assertEqual(read_json(original_admission)["id"], original["id"])
                        self.assertNotEqual(control.requests[0]["id"], original["id"])
                finally:
                    release.set()
                self.assertEqual(pending.result()["status"], "rejected")
                self.assertEqual(sum(r["kind"] == "key" for r in ordinary.delivered), 0)

    def test_control_timeout_cannot_rearm_from_status_or_overwrite_before_expiry(self):
        self.controller.state = recovery_state("debug_prompt")
        with ControlBridge(self.controller, publish=False) as fake:
            result = self.controller.recover("continue_debug_once", timeout=0.04, **self.recovery_expect())
            self.assertEqual(result["status"], "unknown")
            original = self.controller.control_pending.copy()
            self.assertTrue(fake.committed.wait(1))
            self.controller.status()
            self.assertEqual(self.controller.control_pending["id"], original["id"])
            blocked = self.controller.recover("continue_debug_once", **self.recovery_expect())
            self.assertEqual(blocked["status"], "controller_error")
            with FakeBridge(self.controller) as ordinary:
                ordinary.value = recovery_state("debug_prompt")
                self.assertEqual(self.controller.execute("observe")["status"], "ready")
                self.assertIsNotNone(self.controller.control_pending)
                time.sleep(max(0, (original["deadline_ms"] - time.time() * 1000) / 1000 + 0.02))
                self.controller.status()
                self.assertIsNotNone(self.controller.control_pending)
                self.assertEqual(self.controller.execute("observe")["status"], "ready")
                self.assertIsNone(self.controller.control_pending)
            self.assertTrue((self.controller.control_admissions / f'{original["id"]}.json').exists())
            self.assertEqual(self.controller.control_unknown_outcomes[0]["request"]["id"], original["id"])
            self.assertEqual(len(fake.requests), 1)

    def test_control_lock_nonblocking_and_shutdown_holds_process_lock_for_writer(self):
        entered = threading.Event()
        release = threading.Event()
        self.controller.state = recovery_state("debug_prompt")
        def hold(fake, request):
            entered.set()
            self.assertTrue(release.wait(3))
        with ControlBridge(self.controller, before_gate=hold), ThreadPoolExecutor() as pool:
            recovering = pool.submit(self.controller.recover, "continue_debug_once", **self.recovery_expect())
            self.assertTrue(entered.wait(2))
            duplicate = self.controller.recover("continue_debug_once", **self.recovery_expect())
            self.assertEqual(duplicate["status"], "controller_error")
            self.assertEqual(self.controller.execute("resume")["status"], "controller_error")
            closing = pool.submit(self.controller.close)
            time.sleep(0.03)
            if not closing.done():
                with self.assertRaisesRegex(ControlError, "Another controller"):
                    Controller(self.root)
            release.set()
            self.assertIn(recovering.result()["status"], {"controller_error", "rejected"})
            closing.result()
        replacement = Controller(self.root)
        replacement.close()

    def test_control_crash_after_dispatch_restores_durable_identity_and_rejects_old_formats(self):
        self.controller.close()
        child_code = """
import sys
from pathlib import Path
from harness.controller import Controller
from tests.test_controller import recovery_state
c = Controller(Path(sys.argv[1]), timeout=15)
c.state = recovery_state('debug_prompt')
c.recover('continue_debug_once', expected_session=c.state['session'], expected_control_generation=0,
          expected_boundary_id=c.state['boundary']['id'], expected_revision=c.state['revision'],
          expected_frame=c.state['frame'])
"""
        process = subprocess.Popen([sys.executable, "-c", child_code, str(self.root)],
                                   env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            request = None
            while time.monotonic() < deadline and process.poll() is None:
                request = read_json(self.controller.bridge / "control.json")
                if request is not None:
                    break
                time.sleep(0.005)
            self.assertIsNotNone(request)
            admission = self.controller.control_admissions / f'{request["id"]}.json'
            self.assertEqual(read_json(admission), request)
            (self.controller.bridge / "control.json").rename(self.controller.bridge / "control-claimed.json")
            value = recovery_state("debug_prompt", generation=1, revision=4)
            value.update(frame_ok=False, frame="")
            response = {"protocol": 3, "id": request["id"], "status": "dispatched", "error": "", "state": value}
            atomic_json(self.controller.bridge / "control-response.json", response)
            (self.controller.bridge / "control-claimed.json").unlink()
            process.kill()
            process.communicate(timeout=3)
            self.controller = Controller(self.root)
            self.addCleanup(self.controller.close)
            self.assertEqual(self.controller.control_pending["id"], request["id"])
            self.assertEqual(self.controller.control_unknown_outcomes[0]["request"]["id"], request["id"])
            self.assertFalse((self.controller.bridge / "control.json").exists())
            self.controller.close()
            for relative in (f'control-admissions/{request["id"]}.json', "control.json", "control-claimed.json", "control-response.json"):
                path = self.controller.bridge / relative
                current = response if relative == "control-response.json" else request
                before_existing = path.read_bytes() if path.exists() else None
                atomic_json(path, {**current, "protocol": 2})
                before = path.read_bytes()
                with self.assertRaises(ControlError):
                    Controller(self.root)
                # Failed startup preserves all original bytes, even if an inbox
                # is retired by revocation while the process lock is released.
                preserved = path.exists() and path.read_bytes() == before
                if relative == "control.json" and not preserved:
                    preserved = any(p.read_bytes() == before for p in self.controller.bridge.glob("control-cancelled-*.json"))
                self.assertTrue(preserved)
                if before_existing is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(before_existing)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=3)

    def test_orphan_control_claim_and_malformed_passive_state_fail_closed(self):
        self.controller.close()
        created = int(time.time() * 1000)
        request = {"protocol": 3, "id": str(uuid.uuid4()), "kind": "request_interrupt", "session": "world",
                   "control_generation": 0, "authority": {"controller_boot_id": "boot", "counter": 1},
                   "created_ms": created, "deadline_ms": created + 2000}
        path = self.controller.bridge / "control-claimed.json"
        atomic_json(path, request)
        before = path.read_bytes()
        with self.assertRaisesRegex(ControlError, "exact durable admission"):
            Controller(self.root)
        self.assertEqual(path.read_bytes(), before)
        path.unlink()
        self.controller = Controller(self.root)
        self.addCleanup(self.controller.close)
        self.controller.frozen = False
        self.controller.pause_requested = False
        token = read_json(self.controller.bridge / "authority.json")
        atomic_json(self.controller.bridge / "state.json", state(protocol=2))
        status = self.controller.status()
        self.assertTrue(status["frozen"])
        self.assertTrue(status["pause_requested"])
        self.assertNotEqual(read_json(self.controller.bridge / "authority.json"), token)
        self.assertTrue((self.controller.bridge / "pause").exists())

    def test_late_control_terminal_only_resolves_its_own_admission(self):
        self.controller.state = recovery_state("debug_prompt")
        with ControlBridge(self.controller, publish=False) as fake:
            result = self.controller.recover("continue_debug_once", timeout=0.04, **self.recovery_expect())
            self.assertEqual(result["status"], "unknown")
            request = fake.requests[0]
        original = {"protocol": 3, "id": "ordinary-unknown", "kind": "action", "action": "UP",
                    "session": "game-test", "revision": 1, "deadline_ms": 1,
                    "authority": {"controller_boot_id": "old", "counter": 0}}
        self.controller.pending = original.copy()
        atomic_json(self.controller.admissions / "ordinary-unknown.json", original)
        value = recovery_state("debug_prompt", generation=request["control_generation"] + 1)
        value.update(frame_ok=False, frame="")
        atomic_json(self.controller.bridge / "control-response.json", {"protocol": 3, "id": request["id"],
                    "status": "dismissal_delivered", "error": "", "state": value})
        self.controller.status()
        self.assertEqual(self.controller.control_pending["id"], request["id"])
        self.controller._reconcile_control()
        self.assertIsNone(self.controller.control_pending)
        self.assertEqual(self.controller.pending, original)
        self.assertTrue((self.controller.admissions / "ordinary-unknown.json").exists())
        self.assertFalse((self.controller.control_admissions / f'{request["id"]}.json').exists())
        self.assertEqual(self.controller.control_unknown_outcomes[0]["transport_result"], "dismissal_delivered")
        self.assertTrue(self.controller.pause_requested)

    def test_historical_references_hashcheck_without_parsing_or_replaying_archived_wire(self):
        self.controller.close()
        archive = self.root / ".runtime/incidents/cutover/request.json"
        archive.parent.mkdir(parents=True)
        archive.write_bytes(b'{"protocol":2, deliberately-not-valid-json')
        reference = {"id": "original-v2-id", "channel": "gameplay", "source_path": str(archive.relative_to(self.root)),
                     "source_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "reason": "v2 action remains unknown"}
        path = self.controller.bridge / "historical-incidents.json"
        atomic_json(path, {"schema": "incident/1", "incidents": [reference]})
        self.controller = Controller(self.root)
        self.addCleanup(self.controller.close)
        returned = self.controller.status()["historical_unknowns"]
        self.assertEqual(returned, [reference])
        returned[0]["id"] = "mutated"
        self.assertEqual(self.controller.status()["historical_unknowns"][0]["id"], "original-v2-id")
        self.assertEqual(self.controller.unknown_outcomes, [])
        self.controller.close()
        for change in ({"source_sha256": "0" * 64}, {"source_path": "../../elsewhere"}, {"extra": 1}):
            atomic_json(path, {"schema": "incident/1", "incidents": [{**reference, **change}]})
            before = path.read_bytes()
            with self.assertRaises(ControlError):
                Controller(self.root)
            self.assertEqual(path.read_bytes(), before)
        outside = self.root / "outside.json"
        outside.write_bytes(archive.read_bytes())
        link = archive.with_name("link.json")
        link.symlink_to(outside)
        atomic_json(path, {"schema": "incident/1", "incidents": [{**reference, "source_path": str(link.relative_to(self.root))}]})
        with self.assertRaises(ControlError):
            Controller(self.root)

    def test_response_requires_current_fields_without_alternate_shape(self):
        for field in ("frame", "scene"):
            value = state()
            del value[field]
            with self.subTest(missing=field), self.assertRaises(ControlError):
                validate_state(value)
        with self.assertRaises(ControlError):
            validate_state(state(legacy_frame="old.png"))

    def test_startup_rejects_unsupported_stored_versions_and_preserves_evidence(self):
        self.controller.close()
        request = {"protocol": 3, "id": "uncertain", "kind": "action", "action": "UP",
                   "session": "world", "revision": 1, "deadline_ms": 1,
                   "authority": {"controller_boot_id": "old-boot", "counter": 1}}
        bridge = self.controller.bridge
        for relative in ("admissions/uncertain.json", "claimed.json", "response.json"):
            path = bridge / relative
            for version in (None, 1, 2, True, 3.0):
                with self.subTest(path=relative, version=version):
                    value = state() if relative == "response.json" else request.copy()
                    if version is None:
                        value.pop("protocol")
                    else:
                        value["protocol"] = version
                    atomic_json(path, value)
                    before = path.read_bytes()
                    with self.assertRaises(ControlError):
                        Controller(self.root)
                    self.assertEqual(path.read_bytes(), before)
                    self.assertTrue((bridge / "pause").is_file())
                    self.assertFalse((bridge / "request.json").exists())
                    path.unlink()  # Test fixture only; production evidence is retained.
                    # A failed startup must release its lock and never replay input.
                    with_controller = Controller(self.root)
                    with_controller.close()

    def test_orphan_dispatched_response_is_not_converted_to_synthetic_input(self):
        self.controller.close()
        path = self.controller.bridge / "response.json"
        atomic_json(path, state("orphan", status="dispatched", frame_ok=False))
        before = path.read_bytes()
        with self.assertRaisesRegex(ControlError, "lacks a current durable admission"):
            Controller(self.root)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(self.controller.admissions.glob("*.json")), [])
        self.assertFalse((self.controller.bridge / "request.json").exists())

    def test_startup_matches_admission_outside_bounded_viewer_history(self):
        self.controller.close()
        for index in range(61):
            request_id = f"retained-{index:03d}"
            atomic_json(self.controller.admissions / f"{request_id}.json",
                        {"protocol": 3, "id": request_id, "kind": "action", "action": "UP",
                         "session": "world", "revision": 1, "deadline_ms": 1,
                         "authority": {"controller_boot_id": "old-boot", "counter": 1}})
        atomic_json(self.controller.bridge / "response.json",
                    state("retained-000", status="dispatched", frame_ok=False))
        self.controller = Controller(self.root)
        self.addCleanup(self.controller.close)
        self.assertTrue(self.controller.pause_requested)
        self.assertEqual(len(self.controller.unknown_outcomes), 60)
        self.assertEqual(len(list(self.controller.admissions.glob("*.json"))), 61)
        self.assertFalse((self.controller.bridge / "request.json").exists())

    def test_authority_is_durable_and_revoked_on_every_pause_and_restart(self):
        first = read_json(self.controller.bridge / "authority.json")
        self.controller.pause()
        second = read_json(self.controller.bridge / "authority.json")
        self.controller.pause()
        third = read_json(self.controller.bridge / "authority.json")
        self.assertEqual(first["controller_boot_id"], second["controller_boot_id"])
        self.assertLess(first["counter"], second["counter"])
        self.assertLess(second["counter"], third["counter"])
        self.controller.close()
        closed = read_json(self.controller.bridge / "authority.json")
        self.assertGreater(closed["counter"], third["counter"])
        self.controller = Controller(self.root)
        self.addCleanup(self.controller.close)
        restarted = read_json(self.controller.bridge / "authority.json")
        self.assertNotEqual(restarted["controller_boot_id"], first["controller_boot_id"])

    def test_crash_after_dispatch_retains_identity_across_new_world_and_restart(self):
        self.controller.close()
        child_code = '''
import sys
from pathlib import Path
from harness.controller import Controller
from tests.test_controller import state
c = Controller(Path(sys.argv[1]), timeout=15)
c.state = state()
c.frozen = False
c.pause_requested = False
(c.bridge / "pause").unlink(missing_ok=True)
c._exchange("action", 15, generation=c.pause_generation, action="UP")
'''
        process = subprocess.Popen([sys.executable, "-c", child_code, str(self.root)],
                                   env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            request = None
            while time.monotonic() < deadline and process.poll() is None:
                request = read_json(self.controller.bridge / "request.json")
                if request is not None:
                    break
                time.sleep(0.01)
            self.assertIsNotNone(request)
            admission = self.controller.admissions / f'{request["id"]}.json'
            self.assertEqual(read_json(admission), request)
            # Synthetic native dispatch removes claimed.json while the host still waits.
            (self.controller.bridge / "request.json").rename(self.controller.bridge / "claimed.json")
            atomic_json(self.controller.bridge / "response.json",
                        state(request["id"], revision=2, status="dispatched", frame_ok=False))
            (self.controller.bridge / "claimed.json").unlink()
            process.kill()
            process.communicate(timeout=5)
            self.controller = Controller(self.root)
            self.addCleanup(self.controller.close)
            self.assertIn(request["id"], [item["request"]["id"] for item in self.controller.unknown_outcomes])
            with FakeBridge(self.controller) as fake:
                fake.value["session"] = "new-world"
                self.assertEqual(self.controller.execute("observe")["status"], "ready")
                self.assertFalse(any(item["kind"] == "action" for item in fake.requests))
            self.assertTrue(admission.is_file())
            self.controller.close()
            self.controller = Controller(self.root)
            self.addCleanup(self.controller.close)
            self.assertIn(request["id"], self.controller.journal.read_text())
            self.assertTrue(self.controller.pause_requested)
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)

    def test_terminal_input_retires_its_durable_admission(self):
        with FakeBridge(self.controller):
            self.ready()
            result = self.controller.execute("action", action="UP", **self.expect())
            self.assertEqual(result["status"], "ready")
        self.assertEqual(list(self.controller.admissions.glob("*.json")), [])

    def test_pause_after_claim_rejects_key_action_and_resume_at_final_gate(self):
        for kind in ("key", "action", "resume"):
            with self.subTest(kind=kind):
                armed = threading.Event()
                entered = threading.Event()
                release = threading.Event()
                admitted = []
                def gate(fake, request):
                    if request["kind"] == kind and armed.is_set():
                        admitted.append(request["authority"].copy())
                        entered.set()
                        if not release.wait(5):
                            raise AssertionError("final-gate fixture was not released")
                with FakeBridge(self.controller, before_gate=gate) as fake:
                    self.ready()
                    armed.set()
                    payload = {"key": "x"} if kind == "key" else {"action": "UP"} if kind == "action" else {}
                    previous = len(fake.delivered)
                    with ThreadPoolExecutor() as pool:
                        result = pool.submit(self.controller.execute, kind, timeout=10, **payload, **self.expect())
                        try:
                            # The gate signals after atomic claim and stays blocked until
                            # Pause has revoked authority. No transient-file polling race.
                            self.assertTrue(entered.wait(5), "input was not claimed")
                            self.controller.pause()
                            self.assertNotEqual(admitted[0], read_json(fake.bridge / "authority.json"))
                        finally:
                            release.set()
                        self.assertIn(result.result(timeout=5)["status"], {"rejected", "pause_requested"})
                    self.assertEqual(len(fake.delivered), previous)

    def test_pause_after_native_commit_does_not_undo_delivered_input(self):
        def pause_after_commit(fake, request):
            if request["kind"] == "key":
                self.controller.pause()
            return True
        with FakeBridge(self.controller, pause_after_commit) as fake:
            self.ready()
            result = self.controller.execute("key", key="x", **self.expect())
            self.assertEqual(result["status"], "ready")
            self.assertEqual(sum(r["kind"] == "key" for r in fake.delivered), 1)
            self.assertTrue(self.controller.pause_requested)
            self.assertTrue((fake.bridge / "pause").exists())
            self.assertEqual(self.controller.execute("key", key="x", **self.expect())["status"], "controller_error")

    def test_boundary_admission_matrix_and_capture_failure(self):
        with FakeBridge(self.controller) as fake:
            self.ready()
            for boundary in ("activity_poll", "debug_prompt", "interrupt_confirmation", "unsupported"):
                fake.value["boundary"] = {**fake.value["boundary"], "kind": boundary,
                    "recovery_operations": ["answer_interrupt"] if boundary == "interrupt_confirmation" else [],
                    "interrupt_request_id": "owned" if boundary == "interrupt_confirmation" else None}
                fake.value["scene"] = None
                for kind, payload in (("key", {"key": "x"}), ("action", {"action": "UP"}), ("resume", {})):
                    before = len(fake.delivered)
                    result = self.controller.execute(kind, **payload, **self.expect())
                    self.assertEqual(result["status"], "controller_error")
                    self.assertEqual(len(fake.delivered), before)
            fake.value["boundary"].update(kind="menu", recovery_operations=[], interrupt_request_id=None)
            self.assertEqual(self.controller.execute("key", key="x", **self.expect())["status"], "ready")
            fake.value["frame_ok"] = False
            self.assertEqual(self.controller.execute("resume")["status"], "controller_error")

    def test_unknown_old_world_action_is_retained_across_new_world_reconciliation(self):
        def reload(fake, request):
            if request["kind"] == "key":
                fake.value["session"] = "new-world"
            return True
        with FakeBridge(self.controller, reload) as fake:
            self.ready()
            old_session = self.controller.state["session"]
            result = self.controller.execute("key", key="x", **self.expect())
            self.assertEqual(result["status"], "controller_error")
            self.assertTrue(self.controller.frozen)
            self.assertEqual(self.controller.execute("observe")["status"], "ready")
            self.assertEqual(self.controller.state["session"], "new-world")
            unresolved = self.controller.status()["unknown_outcomes"]
            self.assertEqual(len(unresolved), 1)
            self.assertEqual(unresolved[0]["request"]["session"], old_session)
            self.assertEqual(unresolved[0]["status"], "unknown")
            self.assertEqual(sum(r["kind"] == "key" for r in fake.requests), 1)

    def test_v1_and_malformed_boundaries_fail_closed(self):
        from harness.controller import validate_state
        for changes in ({"protocol": 1}, {"boundary": None},
                        {"boundary": {**state()["boundary"], "control_generation": True}},
                        {"boundary": {**state()["boundary"], "extra": 1}},
                        {"boundary": {**state()["boundary"], "kind": "debug_prompt"}}):
            with self.subTest(changes=changes), self.assertRaises(ControlError):
                validate_state(state(**changes))

    def test_startup_pauses_retires_and_never_replays(self):
        self.controller.close()
        bridge = self.root / ".runtime" / "bridge"
        atomic_json(bridge / "request.json", {"protocol": 3, "kind": "key", "key": "x", "id": "old",
            "session": "world", "revision": 1, "deadline_ms": 1,
            "authority": {"controller_boot_id": "old-boot", "counter": 1}})
        self.controller = Controller(self.root, timeout=2.0)
        self.addCleanup(self.controller.close)
        self.assertTrue((bridge / "pause").exists())
        self.assertFalse((bridge / "request.json").exists())
        self.assertEqual(len(list(bridge.glob("cancelled-startup-*.json"))), 1)
        self.assertEqual(self.controller.execute("key", key="x", **{"expected_session": "old", "expected_revision": 1})["status"], "controller_error")
        with FakeBridge(self.controller) as fake:
            self.ready()
            self.assertFalse(any(request["kind"] == "key" for request in fake.requests))

    def test_process_lock_is_exclusive(self):
        with self.assertRaisesRegex(ControlError, "Another controller"):
            Controller(self.root)

    def test_explicit_observe_then_resume(self):
        self.assertEqual(self.controller.execute("resume")["status"], "controller_error")
        with FakeBridge(self.controller):
            self.ready()
            result = self.controller.execute("key", key="i", **self.expect())
            self.assertEqual(result["status"], "ready")
            self.assertFalse(self.controller.status()["pause_requested"])

    def test_rejects_stale_decision_before_primitive(self):
        with FakeBridge(self.controller) as fake:
            self.ready()
            old = self.expect()
            fake.value["revision"] += 1
            result = self.controller.execute("key", key="x", **old)
            self.assertIn("Stale", result["error"])
            self.assertFalse(any(request["kind"] == "key" for request in fake.requests))

    def test_missing_expectation_does_not_dispatch(self):
        with FakeBridge(self.controller) as fake:
            self.ready()
            self.assertIn("require expected", self.controller.execute("action", action="UP")["error"])
            self.assertFalse(any(request["kind"] == "action" for request in fake.requests))

    def test_native_rejection_is_not_ready_or_retried(self):
        def reject(fake, request):
            if request["kind"] == "key":
                fake.value.update(status="rejected", error="stale session or revision")
            return True
        with FakeBridge(self.controller, reject) as fake:
            self.ready()
            result = self.controller.execute("key", key="x", **self.expect())
            self.assertEqual(result["status"], "rejected")
            self.assertEqual(sum(r["kind"] == "key" for r in fake.requests), 1)

    def test_timeout_retires_unclaimed_and_freezes(self):
        result = self.controller.execute("observe", timeout=0.04)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["retirement"], "retired_before_claim")
        self.assertTrue(self.controller.frozen)
        self.assertFalse((self.controller.bridge / "request.json").exists())
        self.assertEqual(len(list(self.controller.bridge.glob("cancelled-timeout-*.json"))), 1)
        self.assertEqual(self.controller.execute("resume")["status"], "controller_error")
        with FakeBridge(self.controller):
            self.ready()

    def test_claimed_timeout_is_unknown_and_never_replayed(self):
        claimed = threading.Event()
        monotonic = time.monotonic

        def abandon(fake, request):
            if request["kind"] == "key":
                claimed.set()
                return False
            return True

        # Expire the host wait only after the fixture has consumed the key.
        # A real one-second watchdog still fails if the fixture never claims it.
        # This tests claimed uncertainty, independently of runner scheduling.
        clock = SimpleNamespace(time=lambda: time.time() + (2 if claimed.is_set() else 0), sleep=time.sleep,
                                monotonic=lambda: monotonic() + (2 if claimed.is_set() else 0))
        with FakeBridge(self.controller, abandon) as fake:
            self.ready()
            with patch("harness.controller.time", clock):
                result = self.controller.execute("key", key="x", timeout=1, **self.expect())
                self.assertTrue(claimed.is_set(), "fixture did not claim the key")
                self.assertEqual(result["status"], "timeout")
                self.assertEqual(result["retirement"], "absent_may_be_claimed_or_dispatched")
                self.assertEqual(self.controller.execute("key", key="x", **self.expect())["status"], "controller_error")
                self.assertEqual(self.controller.execute("observe")["status"], "ready")
                self.assertTrue(self.controller.pause_requested)
                self.assertEqual(sum(r["kind"] == "key" for r in fake.requests), 1)

    def test_wrong_id_response_cannot_finish_request(self):
        atomic_json(self.controller.bridge / "response.json", state("prior-uuid"))
        result = self.controller.execute("observe", timeout=0.04)
        self.assertEqual(result["status"], "timeout")

    def test_wrong_protocol_freezes_with_visible_error(self):
        def corrupt(fake, request):
            fake.value["protocol"] = 99
            return True
        with FakeBridge(self.controller, corrupt):
            result = self.controller.execute("observe")
            self.assertEqual(result["status"], "controller_error")
            self.assertIn("protocol", result["error"])
            self.assertTrue(self.controller.frozen)

    def test_pause_is_responsive_during_wait(self):
        with ThreadPoolExecutor() as pool:
            waiting = pool.submit(self.controller.execute, "observe", timeout=0.3)
            deadline = time.monotonic() + 1
            while not (self.controller.bridge / "request.json").exists() and time.monotonic() < deadline:
                time.sleep(0.002)
            started = time.monotonic()
            self.assertEqual(self.controller.pause()["status"], "pause_requested")
            self.assertLess(time.monotonic() - started, 0.1)
            self.assertFalse(waiting.done())
            self.assertTrue((self.controller.bridge / "pause").exists())
            waiting.result()

    def test_serialized_decisions_cannot_share_revision(self):
        with FakeBridge(self.controller) as fake:
            self.ready()
            authority = self.expect()
            with ThreadPoolExecutor(2) as pool:
                results = list(pool.map(lambda _: self.controller.execute("key", key="x", **authority), range(2)))
            self.assertEqual(sum(result["status"] == "ready" for result in results), 1)
            self.assertEqual(sum(r["kind"] == "key" for r in fake.requests), 1)

    def test_walk_verifies_displacement(self):
        with FakeBridge(self.controller) as fake:
            self.ready()
            result = self.controller.execute("walk", direction="east", steps=3, **self.expect())
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["steps"], 3)
            self.assertEqual(fake.value["scene"]["position"], [3, 0, 0])

    def test_walk_preserves_full_progress_when_final_post_guard_blocks(self):
        def block_beyond_destination(fake, request):
            if request["kind"] == "action":
                fake.value["scene"]["neighbors"][-1]["terrain"] = "t_wall"
            return True
        with FakeBridge(self.controller, block_beyond_destination) as fake:
            self.ready()
            result = self.controller.execute("walk", direction="east", steps=1, **self.expect())
            self.assertEqual(result["status"], "stopped")
            self.assertEqual(result["steps"], 1)
            self.assertEqual(fake.value["scene"]["position"], [1, 0, 0])
            self.assertEqual(sum(r["kind"] == "action" for r in fake.requests), 1)

    def test_walk_stops_on_creature_even_when_not_hostile(self):
        def creature(fake, request):
            if request["kind"] == "action":
                fake.value["scene"]["visible_creatures"] = [{"name": "cat", "hostile": False}]
            return True
        with FakeBridge(self.controller, creature) as fake:
            self.ready()
            result = self.controller.execute("walk", direction="east", steps=5, **self.expect())
            self.assertEqual(result["status"], "stopped")
            self.assertEqual(result["steps"], 1)
            self.assertEqual(sum(r["kind"] == "action" for r in fake.requests), 1)

    def test_walk_stops_on_unknown_terrain_furniture_and_no_progress(self):
        with FakeBridge(self.controller) as fake:
            self.ready()
            for changes in ({"visible": False}, {"terrain": "t_water_sh"}, {"furniture": "f_chair"}):
                tile = fake.value["scene"]["neighbors"][-1]
                original = tile.copy()
                tile.update(changes)
                result = self.controller.execute("walk", direction="east", steps=2, **self.expect())
                self.assertEqual(result["steps"], 0)
                self.assertEqual(result["status"], "stopped")
                tile.clear()
                tile.update(original)
            self.assertFalse(any(r["kind"] == "action" for r in fake.requests))
        def no_progress(fake, request):
            if request["kind"] == "action":
                fake.value["scene"]["position"] = [0, 0, 0]
            return True
        with FakeBridge(self.controller, no_progress) as fake:
            self.ready()
            result = self.controller.execute("walk", direction="east", steps=3, **self.expect())
            self.assertEqual(result["status"], "stopped")
            self.assertIn("displacement", result["error"])

    def test_walk_context_change_stops(self):
        def prompt(fake, request):
            if request["kind"] == "action":
                fake.value.update(category="YESNO", scene=None)
                fake.value["boundary"] = {**fake.value["boundary"], "kind": "menu", "id": "question"}
            return True
        with FakeBridge(self.controller, prompt) as fake:
            self.ready()
            result = self.controller.execute("walk", direction="north", steps=4, **self.expect())
            self.assertEqual(result["status"], "stopped")
            self.assertEqual(sum(r["kind"] == "action" for r in fake.requests), 1)

    def test_goal_and_journal_do_not_claim_game_success(self):
        result = self.controller.execute("goal", text="Find water")
        self.assertEqual(result["status"], "recorded")
        lines = [json.loads(line) for line in self.controller.journal.read_text().splitlines()]
        self.assertEqual(lines[-1]["request"]["text"], "Find water")
        self.assertNotIn("success", lines[-1]["outcome"])

    def test_input_bounds(self):
        for kind, payload in [("key", {"key": "abc"}), ("key", {"key": "é"}),
                              ("walk", {"direction": "east", "steps": 9}),
                              ("observe", {"timeout": 16}), ("observe", {"timeout": True})]:
            self.assertEqual(self.controller.execute(kind, **payload)["status"], "controller_error")

    def test_shutdown_retires_waiter_before_releasing_writer_lock(self):
        with ThreadPoolExecutor() as pool:
            waiting = pool.submit(self.controller.execute, "observe", timeout=1)
            deadline = time.monotonic() + 1
            while not (self.controller.bridge / "request.json").exists() and time.monotonic() < deadline:
                time.sleep(0.002)
            self.controller.close()
            self.assertEqual(waiting.result()["status"], "controller_error")
            self.assertFalse((self.controller.bridge / "request.json").exists())
            self.assertTrue((self.controller.bridge / "pause").exists())
            self.assertEqual(self.controller.execute("resume")["status"], "controller_error")

    def test_pause_during_resume_observation_wins(self):
        observing_resume = threading.Event()
        release = threading.Event()
        def block(fake, request):
            if request["kind"] == "observe" and observing_resume.is_set():
                release.wait(1)
            return True
        with FakeBridge(self.controller, block):
            self.ready()
            self.controller.pause()
            observing_resume.set()
            with ThreadPoolExecutor() as pool:
                waiting = pool.submit(self.controller.execute, "resume")
                deadline = time.monotonic() + 1
                while not (self.controller.bridge / "claimed.json").exists() and time.monotonic() < deadline:
                    time.sleep(0.002)
                self.controller.pause()
                release.set()
                result = waiting.result()
            self.assertEqual(result["status"], "pause_requested")
            self.assertTrue((self.controller.bridge / "pause").exists())
            self.assertTrue(self.controller.pause_requested)

    def test_native_takeover_supersedes_queued_resume(self):
        self._queued_resume_loses_to_pause(native=True)

    def test_new_pause_supersedes_queued_resume(self):
        self._queued_resume_loses_to_pause(native=False)

    def _queued_resume_loses_to_pause(self, native):
        waiting = threading.Event()
        release = threading.Event()
        class Gate:
            def __enter__(self):
                waiting.set()
                if not release.wait(1):
                    raise AssertionError("test gate not released")
            def __exit__(self, *args):
                return False
        with FakeBridge(self.controller) as fake:
            self.ready()
            previous = sum(r["kind"] == "resume" for r in fake.requests)
            original = self.controller.command_lock
            self.controller.command_lock = Gate()
            try:
                with ThreadPoolExecutor() as pool:
                    queued = pool.submit(self.controller.execute, "resume")
                    self.assertTrue(waiting.wait(1))
                    if native:
                        fake.value["revision"] += 1
                        fake.value["boundary"]["control_generation"] += 1
                        fake.value["paused"] = True
                        (fake.bridge / "pause").touch()
                        # No status poll: Resume must discover takeover itself.
                    else:
                        self.controller.pause()
                    release.set()
                    result = queued.result()
                self.assertEqual(result["status"], "pause_requested")
                self.assertTrue(self.controller.pause_requested)
                self.assertTrue((self.controller.bridge / "pause").exists())
                self.assertEqual(sum(r["kind"] == "resume" for r in fake.requests), previous)
            finally:
                self.controller.command_lock = original
