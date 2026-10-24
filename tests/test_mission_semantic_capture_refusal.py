"""Capture provenance and image-conditioned refusal; not native acceptance."""
import copy
from dataclasses import replace
import json
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
    native_choices = fixtures.MissionRuntimeTests.native_choices

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

    def assert_refused(self, operation, original, *, charged, progressed=False):
        self.assertEqual(operation["state"], "partial" if progressed else "blocked", operation)
        self.assertEqual(operation["result"]["phase"]["stage"], "awaiting_observation")
        status = self.runtime.status()
        self.assertEqual(status["phase"], "active", status)
        self.assertEqual(status["spent_inputs"], charged)
        for key in ("epoch", "started_at", "deadline", "player_id", "cleanup_reserve"):
            self.assertEqual(status[key], original[key], key)
        self.assertIs(self.runtime._lease, self.controller._mission_lease)
        self.assertFalse(self.controller.frozen)
        self.assertFalse(self.controller.pause_requested)
        self.assertEqual(status["unresolved_effects"], [])

    def test_wait_start_capture_churn_preserves_issued_preflight_and_charges_once(self):
        original = self.start()
        goal = dict(operation="wait", target="Wait briefly", game_seconds=30,
                    interrupt_allowed=True, step="start", answer=None, interrupt_request_id=None)
        request = self.control("activity", goal, request_id="wait-start")
        with self.churn_after_preparation():
            self.assertEqual(self.runtime.command(request)["status"], "accepted")
            operation = self.settled(request["request_id"])
        self.assertEqual(operation["state"], "partial", operation)
        self.assertNotEqual(operation["result"]["phase"]["stage"], "awaiting_observation")
        status = self.runtime.status()
        for key in ("epoch", "started_at", "deadline", "player_id", "cleanup_reserve"):
            self.assertEqual(status[key], original[key], key)
        self.assertEqual(status["spent_inputs"], 1)
        primitive, = self.runtime._ledger.primitive_records()
        self.assertEqual(primitive["intent"]["kind"], "action")
        self.assertEqual(primitive["intent"]["value"], "wait")
        self.assertEqual(primitive["state"], "returned")
        self.assertTrue(primitive["result"]["published"])
        request_body = json.loads(primitive["result"]["native_request_json"])
        source = next(ref for ref in self.runtime._store.historical_references
            if ref.observation_id == primitive["intent"]["preflight_source"])
        preflight = self.runtime._store.observation(source)
        self.assertEqual(request_body["frame"], preflight["frame"])
        self.assertFalse(request_body["require_exact_frame"])
        self.assertEqual(sum(r.get("action") == "wait" for r in self.bridge.delivered), 1)
        self.assertEqual(self.runtime.command(request)["operation"], operation)
        self.assertEqual(len(self.runtime._ledger.primitive_records()), 1)
        self.assertEqual(self.runtime._ledger.primitive_records()[0], primitive)

    def test_navigation_capture_churn_preserves_original_source_and_verified_steps(self):
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
                    self.assertEqual(operation["state"], "completed", operation)
                    self.assertEqual(operation["result"]["verified_steps"], prefix + 1)
                    for key in ("epoch", "started_at", "deadline", "player_id", "cleanup_reserve"):
                        self.assertEqual(case.runtime.status()[key], original[key], key)
                    self.assertEqual(case.runtime.status()["spent_inputs"], len(baseline) + prefix + 1)
                    rows = case.runtime._ledger.primitive_records()
                    self.assertEqual(rows[:len(baseline)], baseline)
                    self.assertEqual([r["state"] for r in rows[len(baseline):]], ["returned"] * (prefix + 1))
                    self.assertEqual(case.runtime.command(request)["operation"], operation)
                    self.assertEqual(case.runtime._ledger.primitive_records(), rows)
                    self.assertIsNone(case.runtime._prompt_phase)
                    self.assertEqual(operation["result"]["position"], list(target))
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

    def test_aged_semantic_entry_preserves_prefix_and_requires_explicit_new_decision(self):
        for prefix, interpreted in ((0, False), (1, False), (1, True)):
            with self.subTest(prefix=prefix, interpreted=interpreted):
                case = type(self)()
                case.setUp()
                try:
                    root, _ = case.native_choices()
                    original = case.runtime.status()
                    perception = None if not interpreted else dict(kind="menu", basis="player_interpretation",
                        source_id=case.runtime._current.observation_id, control="vertical",
                        rows=[dict(label=label, enabled=True) for label in ("One", "Two", "Three")],
                        selected=0, question="Choose")
                    request = case.control("menu", dict(purpose="Choose", label="Three", outcome="focused"),
                        phase_id=root["request_id"], perception=perception, request_id="aged-semantic-entry")
                    reserve, clocks = case.runtime._store.reserve_dispatch, case.runtime._clocks
                    checks, aged = [], []

                    def after_retention(before, **kwargs):
                        checks.append(before)
                        if len(checks) == prefix + 1:
                            # Model time spent between entry and final reservation.
                            # The real fresh preflight has a later original receipt.
                            aged.append(dict(now_monotonic=before.received_monotonic + 3.001,
                                             now_timestamp_ms=before.timestamp_ms + 3001))
                            kwargs.update(aged[0])
                        return reserve(before, **kwargs)

                    with patch.object(case.runtime._store, "reserve_dispatch", side_effect=after_retention), \
                            patch.object(case.runtime, "_clocks", side_effect=lambda: aged[0] if aged else clocks()):
                        self.assertEqual(case.runtime.command(request)["status"], "accepted")
                        operation = case.settled(request["request_id"])
                    case.assert_refused(operation, original, charged=original["spent_inputs"] + prefix,
                                        progressed=bool(prefix))
                    self.assertEqual(operation["result"]["basis"],
                                     "player_interpretation" if interpreted else "native_rows")
                    self.assertIsNotNone(operation["result"]["revalidation"])
                    self.assertIsNone(operation["result"]["pending_logical_id"])
                    primitives = case.runtime._ledger.primitive_records()
                    self.assertEqual(len(primitives), 1 + prefix)
                    self.assertTrue(all(row["state"] == "returned" for row in primitives))
                    self.assertEqual(case.bridge.value["ui"]["selected"], f"row-{prefix}")
                    self.assertEqual(case.runtime.command(request)["operation"], operation)
                    self.assertEqual(case.runtime._ledger.primitive_records(), primitives)
                    self.assertEqual(case.runtime.command({**request, "request_id": "before-observe"})["status"], "rejected")
                    self.assertEqual(case.observe()["state"], "completed")
                    new = case.control("direct", dict(input=dict(type="key", key="ESC", modifiers=[]),
                        intent="Cancel after inspecting", expected="Inspect result", interrupt_allowed=False),
                        phase_id=root["request_id"], request_id="distinct-after-observe")
                    response = case.runtime.command(new)
                    self.assertEqual(response["status"], "accepted", response)
                    self.assertEqual(case.settled(new["request_id"])["state"], "partial")
                    self.assertEqual(case.runtime._ledger.primitive_records()[:len(primitives)], primitives)
                finally:
                    case.doCleanups()

    def test_age_refusal_never_hides_clock_custody_pending_or_global_faults(self):
        for fault in ("future", "reversal", "pending", "deadline", "corruption", "generation", "pause", "takeover"):
            with self.subTest(fault=fault):
                case = type(self)()
                case.setUp()
                try:
                    root, _ = case.native_choices()
                    original = case.runtime.status()
                    request = case.control("menu", dict(purpose="Choose", label="Three", outcome="focused"),
                        phase_id=root["request_id"], request_id="age-with-fault")
                    reserve, fresh = case.runtime._store.reserve_dispatch, case.runtime._store._fresh
                    checking = []

                    def check(entry, now_monotonic, now_timestamp_ms):
                        if checking and entry.reference == checking[0]:
                            if fault == "pending": case.controller.pending = {"id": "other-input"}
                            elif fault == "deadline": case.runtime._mission_deadline = case.runtime._wall()
                            elif fault == "corruption":
                                path = Path(entry.reference.frame_path)
                                path.chmod(0o600)
                                path.write_bytes(b"corrupt owned fixture")
                            elif fault == "generation": case.runtime._store._invalidate("Fixture invalidation")
                            elif fault == "pause": case.runtime.pause("Real Pause interleaving")
                            elif fault == "takeover": case.controller.state["takeover_generation"] += 1
                            return fresh(entry,
                                entry.reference.received_monotonic + (-1 if fault == "reversal" else 4),
                                entry.reference.timestamp_ms + (-2000 if fault == "future" else 4000))
                        return fresh(entry, now_monotonic, now_timestamp_ms)

                    def after_retention(before, **kwargs):
                        checking.append(before)
                        return reserve(before, **kwargs)

                    with patch.object(case.runtime._store, "reserve_dispatch", side_effect=after_retention), \
                            patch.object(case.runtime._store, "_fresh", side_effect=check):
                        self.assertEqual(case.runtime.command(request)["status"], "accepted")
                        operation = case.settled(request["request_id"])
                    self.assertNotEqual(operation["state"], "completed")
                    self.assertIsNone(case.runtime._lease)
                    self.assertIsNone(case.runtime._prompt_phase)
                    self.assertNotEqual(case.runtime.status()["phase"], "active")
                    self.assertEqual(case.runtime.status()["spent_inputs"], original["spent_inputs"])
                    self.assertEqual(len(case.runtime._ledger.primitive_records()), 1)
                    self.assertEqual(sum(row.get("action") == "UILIST.DOWN" for row in case.bridge.delivered), 0)
                finally:
                    case.controller.pending = None
                    case.doCleanups()

    def test_navigation_age_refusal_retains_observation_scope_and_verified_prefix(self):
        for prefix in (0, 1):
            with self.subTest(prefix=prefix):
                case = type(self)()
                case.setUp()
                try:
                    case.start()
                    if prefix:
                        for target, identity in (((1, 0, 0), "seed-visit"), ((0, 0, 0), "seed-return")):
                            seed = case.navigation(target=target, request_id=identity)
                            self.assertEqual(case.runtime.command(seed)["status"], "accepted")
                            self.assertEqual(case.settled(identity)["state"], "completed")
                    original = case.runtime.status()
                    prior = case.runtime._ledger.primitive_records()
                    reserve, clocks = case.runtime._store.reserve_dispatch, case.runtime._clocks
                    aged, checks = [], []

                    def after_retention(before, **kwargs):
                        checks.append(before)
                        if len(checks) == prefix + 1:
                            aged.append(dict(now_monotonic=before.received_monotonic + 3.001,
                                             now_timestamp_ms=before.timestamp_ms + 3001))
                            kwargs.update(aged[0])
                        return reserve(before, **kwargs)

                    request = case.navigation(target=(prefix + 1, 0, 0), request_id="aged-navigation")
                    with patch.object(case.runtime._store, "reserve_dispatch", side_effect=after_retention), \
                            patch.object(case.runtime, "_clocks", side_effect=lambda: aged[0] if aged else clocks()):
                        self.assertEqual(case.runtime.command(request)["status"], "accepted")
                        operation = case.settled(request["request_id"])
                    case.assert_refused(operation, original, charged=original["spent_inputs"] + prefix,
                                        progressed=bool(prefix))
                    self.assertEqual(operation["result"]["verified_steps"], prefix)
                    self.assertIsNone(operation["result"]["pending_logical_id"])
                    rows = case.runtime._ledger.primitive_records()
                    self.assertEqual(rows[:len(prior)], prior)
                    self.assertEqual(len(rows), len(prior) + prefix)
                    for row in rows[len(prior):]:
                        self.assertEqual(row["state"], "returned")
                        self.assertIn(row["result"]["source_after"], operation["result"]["source_ids"])
                    self.assertEqual(case.observe()["state"], "completed")
                    new = case.navigation(target=(prefix + 1, 0, 0), request_id="new-navigation-decision")
                    self.assertEqual(case.runtime.command(new)["status"], "accepted")
                    self.assertEqual(case.settled(new["request_id"])["state"], "completed")
                    self.assertEqual(case.runtime._ledger.primitive_records()[:len(rows)], rows)
                finally:
                    case.doCleanups()

    def test_actual_preflight_expiring_after_age_refusal_still_stops(self):
        root, _ = self.native_choices()
        original = self.runtime.status()
        reserve, fresh = self.runtime._store.reserve_dispatch, self.runtime._store._fresh
        authenticate, clock = self.runtime._unpublished_refusal_guard, self.runtime._clock
        checking = []

        def after_retention(before, **kwargs):
            checking.append(before)
            return reserve(before, **kwargs)

        def age_before(entry, now_monotonic, now_timestamp_ms):
            if checking and entry.reference == checking[0]:
                return fresh(entry, entry.reference.received_monotonic + 4, entry.reference.timestamp_ms + 4000)
            return fresh(entry, now_monotonic, now_timestamp_ms)

        def expire_actual(*args, **kwargs):
            with patch.object(self.runtime, "_clock", side_effect=lambda: clock() + 4):
                return authenticate(*args, **kwargs)

        request = self.control("menu", dict(purpose="Choose", label="Three", outcome="focused"),
            phase_id=root["request_id"], request_id="actual-expired-after-refusal")
        with patch.object(self.runtime._store, "reserve_dispatch", side_effect=after_retention), \
                patch.object(self.runtime._store, "_fresh", side_effect=age_before), \
                patch.object(self.runtime, "_unpublished_refusal_guard", side_effect=expire_actual):
            self.assertEqual(self.runtime.command(request)["status"], "accepted")
            operation = self.settled(request["request_id"])
        self.assertNotEqual(operation["state"], "completed")
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], original["spent_inputs"])
        self.assertEqual(sum(row.get("action") == "UILIST.DOWN" for row in self.bridge.delivered), 0)
