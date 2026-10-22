"""Prepared semantic capture refusal over real writer/files; not native acceptance."""
import copy
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from tests import test_mission_runtime as fixtures


class SemanticCaptureRefusalTests(unittest.TestCase):
    wait = fixtures.MissionRuntimeTests.wait
    request = fixtures.MissionRuntimeTests.request
    result = fixtures.MissionRuntimeTests.result
    settled = fixtures.MissionRuntimeTests.settled
    start = fixtures.MissionRuntimeTests.start
    control = fixtures.MissionRuntimeTests.control
    navigation = fixtures.MissionRuntimeTests.navigation
    open_direction = fixtures.MissionRuntimeTests.open_direction

    def setUp(self):
        fixtures.MissionRuntimeTests.setUp(self)
        self.a = replace(self.a, allowed_skills=tuple(dict.fromkeys((*self.a.allowed_skills, "activity", "direct"))))
        self.bridge.value["actions"].append("wait")

    def churn_after_preparation(self, at=1):
        prepare = self.runtime._ledger.prepare_primitive
        calls = []

        def churn(*args, **kwargs):
            result = prepare(*args, **kwargs)
            calls.append(result)
            if len(calls) == at:
                current = copy.deepcopy(self.controller.state)
                current.update(id="", frame="frame-game-test-999999.png")
                (self.controller.bridge / current["frame"]).write_bytes(self.bridge.visible_bytes(current))
                self.controller._accept(current)
            return result

        return patch.object(self.runtime._ledger, "prepare_primitive", churn)

    def observe(self):
        request = self.request("observe", request_id="explicit-observe")
        self.assertEqual(self.runtime.command(request)["status"], "accepted")
        return self.settled(request["request_id"])

    def assert_refused(self, operation, original, *, charged, verified=None):
        self.assertEqual(operation["state"], "partial" if verified else "blocked", operation)
        self.assertEqual(operation["result"]["phase"]["stage"], "awaiting_observation")
        if verified is not None:
            self.assertEqual(operation["result"]["verified_steps"], verified)
        status = self.runtime.status()
        self.assertEqual(status["phase"], "active", status)
        self.assertEqual(status["spent_inputs"], charged)
        for key in ("epoch", "started_at", "deadline", "player_id", "cleanup_reserve"):
            self.assertEqual(status[key], original[key], key)
        self.assertIs(self.runtime._lease, self.controller._mission_lease)
        self.assertFalse(self.controller.frozen)
        self.assertFalse(self.controller.pause_requested)
        self.assertEqual(status["unresolved_effects"], [])

    def test_wait_start_refusal_keeps_charge_then_explicit_observe_and_new_intent(self):
        original = self.start()
        goal = dict(operation="wait", target="Wait briefly", game_seconds=30,
                    interrupt_allowed=True, step="start", answer=None, interrupt_request_id=None)
        request = self.control("activity", goal, request_id="wait-start")
        with self.churn_after_preparation():
            self.assertEqual(self.runtime.command(request)["status"], "accepted")
            operation = self.settled(request["request_id"])
        self.assert_refused(operation, original, charged=1)
        primitive, = self.runtime._ledger.primitive_records()
        self.assertEqual(primitive["intent"]["kind"], "action")
        self.assertEqual(primitive["intent"]["value"], "wait")
        self.assertEqual(primitive["state"], "not_dispatched")
        self.assertFalse(primitive["result"]["published"])
        self.assertIsNone(primitive["native_id"])
        self.assertIsNone(primitive["result"]["native_ack"])
        self.assertFalse(any(r.get("action") == "wait" for r in self.bridge.delivered))
        self.assertEqual(self.runtime.command(request)["operation"], operation)
        self.assertEqual(len(self.runtime._ledger.primitive_records()), 1)
        observed = self.observe()
        self.assertEqual(observed["state"], "completed", observed)
        self.assertIsNone(self.runtime._prompt_phase)
        chosen = self.control("activity", goal, request_id="new-wait-choice")
        self.assertEqual(self.runtime.command(chosen)["status"], "accepted")
        self.assertEqual(self.settled(chosen["request_id"])["state"], "partial")
        self.assertEqual(sum(r.get("action") == "wait" for r in self.bridge.delivered), 1)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertEqual(self.runtime._ledger.primitive_records()[0], primitive)

    def test_navigation_first_refusal_and_delivered_prefix_require_explicit_observation(self):
        for prefix in (0, 1):
            with self.subTest(prefix=prefix):
                case = type(self)()
                case.setUp()
                try:
                    case.start()
                    if prefix:
                        # Observe the second tile by visiting its neighbour and
                        # returning; the route must not depend on hidden terrain.
                        for target, identity in (((1, 0, 0), "visit"), ((0, 0, 0), "return")):
                            seed = case.navigation(target=target, request_id=identity)
                            self.assertEqual(case.runtime.command(seed)["status"], "accepted")
                            self.assertEqual(case.settled(identity)["state"], "completed")
                    original = case.runtime.status()
                    baseline = case.runtime._ledger.primitive_records()
                    target = (prefix + 1, 0, 0)
                    request = case.navigation(target=target, request_id="route")
                    with case.churn_after_preparation(at=prefix + 1):
                        self.assertEqual(case.runtime.command(request)["status"], "accepted")
                        operation = case.settled(request["request_id"])
                    case.assert_refused(operation, original, charged=len(baseline) + prefix + 1, verified=prefix)
                    rows = case.runtime._ledger.primitive_records()
                    self.assertEqual(rows[:len(baseline)], baseline)
                    self.assertEqual([r["state"] for r in rows[len(baseline):]], ["returned"] * prefix + ["not_dispatched"])
                    self.assertEqual(case.runtime.command(request)["operation"], operation)
                    self.assertEqual(case.runtime._ledger.primitive_records(), rows)
                    self.assertEqual(case.observe()["state"], "completed")
                    self.assertIsNone(case.runtime._prompt_phase)
                    chosen = case.navigation(target=target, request_id="new-route-choice")
                    self.assertEqual(case.runtime.command(chosen)["status"], "accepted")
                    completed = case.settled(chosen["request_id"])
                    self.assertEqual(completed["state"], "completed", completed)
                    self.assertEqual(completed["result"]["position"], list(target))
                    self.assertEqual(case.runtime.status()["spent_inputs"], len(baseline) + prefix + 2)
                    self.assertEqual(case.runtime._ledger.primitive_records()[:len(rows)], rows)
                finally:
                    case.doCleanups()

    def test_early_image_refusal_rechecks_health_instead_of_trusting_rejected_status(self):
        for fault in (None, "pending", "global_deadline", "source", "native_state", "preflight_age"):
            with self.subTest(fault=fault):
                case = type(self)()
                case.setUp()
                try:
                    root, _ = case.open_direction()
                    original = case.runtime.status()
                    ref = original["current_source"]
                    view = dict(kind="direction", basis="player_interpretation",
                                source_id=ref["observation_id"], question="Where?")
                    request = case.control("menu", dict(purpose="Direction", label="Here", outcome="activated"),
                                           phase_id=root["request_id"], perception=view, request_id="image-refusal")
                    execute = case.controller.execute_mission

                    def refuse(*args, **kwargs):
                        with patch.object(case.controller, "_frame_sha256", return_value="0" * 64):
                            raw = execute(*args, **kwargs)
                        self.assertFalse(raw["published"])
                        self.assertEqual(raw["result"]["status"], "rejected", raw)
                        if fault == "pending": case.controller.pending = {"id": "other"}
                        elif fault == "global_deadline": case.runtime._mission_deadline = case.runtime._wall()
                        elif fault == "source":
                            source = Path(case.runtime._current.frame_path)
                            source.chmod(0o600)  # Deliberate corruption of this test's owned temporary file.
                            source.write_bytes(b"corrupted source")
                        elif fault == "native_state": case.controller.state["revision"] += 1
                        elif fault == "preflight_age": raw["preflight"]["received_monotonic"] -= 4
                        return raw

                    with patch.object(case.controller, "execute_mission", refuse):
                        self.assertEqual(case.runtime.command(request)["status"], "accepted")
                        operation = case.settled(request["request_id"])
                    self.assertEqual(operation["state"], "blocked", operation)
                    self.assertEqual(case.runtime.status()["spent_inputs"], original["spent_inputs"])
                    self.assertEqual(len(case.runtime._ledger.primitive_records()), 1)
                    if fault is None:
                        case.assert_refused(operation, original, charged=original["spent_inputs"])
                        self.assertEqual(case.observe()["state"], "completed")
                    else:
                        self.assertIsNone(case.runtime._lease)
                        self.assertIsNone(case.runtime._prompt_phase)
                        self.assertNotEqual(case.runtime.status()["phase"], "active")
                finally:
                    case.controller.pending = None
                    case.doCleanups()
