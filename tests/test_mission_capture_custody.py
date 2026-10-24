"""Moving visible interfaces preserve capture evidence, not stale applicability.

Real controller/runtime/archive components with a synthetic file bridge; these
interleavings are source evidence, not native graphical qualification.
"""
import copy
from contextlib import ExitStack
from pathlib import Path
import unittest
from unittest.mock import patch

from tests import test_mission_pending_observation as fixtures
from tests import test_mission_runtime as core


class CaptureCustodyTests(unittest.TestCase):
    setUp = fixtures.PendingObservationTests.setUp
    wait = fixtures.PendingObservationTests.wait
    request = fixtures.PendingObservationTests.request
    result = fixtures.PendingObservationTests.result
    settled = fixtures.PendingObservationTests.settled
    start = fixtures.PendingObservationTests.start
    control = fixtures.PendingObservationTests.control
    open_direction = fixtures.PendingObservationTests.open_direction
    allow_direct = fixtures.PendingObservationTests.allow_direct
    direct = fixtures.PendingObservationTests.direct
    observe = fixtures.PendingObservationTests.observe
    native_choices = core.MissionRuntimeTests.native_choices
    navigation = core.MissionRuntimeTests.navigation

    def advance_visible(self, fault=None):
        value = copy.deepcopy(self.bridge.value)
        value["revision"] += 1
        value.update(category="UNFAMILIAR_ASYNC_VIEW")
        value["boundary"]["id"] = "next-visible-menu"
        if fault == "control":
            value["boundary"]["control_generation"] += 1
        elif fault == "takeover":
            value["takeover_generation"] += 1
        elif fault == "session":
            value["session"] = "unowned-new-session"
        elif fault == "pause":
            value.update(paused=True, pause_origin="human")
        elif fault == "unhealthy":
            value.update(frame_ok=False, error="Renderer unavailable")
        elif fault == "future":
            value["timestamp_ms"] += 10_000
        elif fault == "regression":
            value["revision"] -= 2
        elif fault == "contradiction":
            value["revision"] -= 1
        self.bridge.value = value
        self.bridge.publish(value)
        self.controller.status()

    def known_ack_then_advance(self, fault=None):
        self.allow_direct()
        root, _ = self.open_direction()
        request = self.control("direct", dict(input=dict(type="text", text="ab"),
            intent="Enter the observed text once", expected="Interpret the returned interface",
            interrupt_allowed=False), phase_id=root["request_id"], request_id="text-with-next-view")
        execute, ingest = self.controller.execute_mission, self.runtime._ingest
        delivered, advanced = [], []

        def returned(*args, **kwargs):
            raw = execute(*args, **kwargs)
            delivered.append(copy.deepcopy(raw))
            return raw

        def retained(*args, **kwargs):
            reference = ingest(*args, **kwargs)
            if delivered and not advanced:
                advanced.append(reference)
                if fault == "missing":
                    Path(reference.frame_path).unlink()
                else:
                    self.advance_visible(fault)
            return reference

        with patch.object(self.controller, "execute_mission", side_effect=returned), \
                patch.object(self.runtime, "_ingest", side_effect=retained):
            self.assertEqual(self.runtime.command(request)["status"], "accepted")
            operation = self.settled(request["request_id"])
        self.assertEqual(len(delivered), 1, operation)
        self.assertEqual(len(advanced), 1, operation)
        primitive = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual(primitive["state"], "returned")
        self.assertEqual(primitive["native_id"], delivered[0]["request"]["id"])
        self.assertEqual(primitive["result"]["source_after"], advanced[0].observation_id)
        self.assertEqual(primitive["result"]["received_monotonic"], delivered[0]["received_monotonic"])
        return root, operation, primitive

    def test_known_ack_survives_next_view_and_text_suffix_waits_for_a_new_decision(self):
        root, operation, primitive = self.known_ack_then_advance()
        self.assertEqual(operation["state"], "partial", operation)
        self.assertEqual(operation["result"]["phase"]["stage"], "awaiting_observation")
        self.assertEqual(self.runtime.status()["phase"], "active")
        self.assertIsNone(self.runtime.status()["current_source"])
        self.assertEqual(self.bridge.delivered[-1]["input"]["text"], "a")
        self.assertEqual(self.runtime._store.observation(self.runtime._current)["id"],
                         primitive["native_id"])
        observed = self.observe()
        self.assertEqual(observed["state"], "completed", observed)
        self.assertEqual(self.runtime._ledger.primitive_records()[-1], primitive)
        selected = self.direct(root, request_id="distinct-player-decision")
        self.assertEqual(self.runtime.command(selected)["status"], "accepted")
        self.assertEqual(self.settled(selected["request_id"])["state"], "partial")
        self.assertEqual(self.bridge.delivered[-1]["input"]["key"], "ESC")

    def test_next_view_never_hides_real_custody_or_capture_faults(self):
        for fault in ("control", "takeover", "session", "pause", "unhealthy", "missing",
                      "future", "regression", "contradiction"):
            with self.subTest(fault=fault):
                case = type(self)()
                case.setUp()
                try:
                    _, operation, _ = case.known_ack_then_advance(fault)
                    self.assertEqual(operation["state"], "blocked", operation)
                    self.assertIsNone(case.runtime._lease)
                    self.assertEqual(case.runtime.status()["spent_inputs"], 2)
                finally:
                    case.doCleanups()

    def test_observe_returns_its_original_capture_while_a_newer_owned_view_appears(self):
        for prompt in (False, True):
            with self.subTest(prompt=prompt):
                case = type(self)()
                case.setUp()
                try:
                    case.allow_direct()
                    case.open_direction() if prompt else case.start()
                    original = case.controller.observe_mission
                    captured = []

                    def observed(**kwargs):
                        result, received = original(**kwargs)
                        captured.append((copy.deepcopy(result), received))
                        case.advance_visible()
                        return result, received

                    charges = case.runtime.status()["spent_inputs"]
                    with patch.object(case.controller, "observe_mission", side_effect=observed):
                        operation = case.observe()
                    self.assertEqual(operation["state"], "completed", operation)
                    reference = case.runtime._current
                    self.assertEqual(case.runtime._store.observation(reference), captured[0][0])
                    self.assertEqual(reference.received_monotonic, captured[0][1])
                    self.assertEqual(case.runtime.status()["current_source"]["observation_id"], reference.observation_id)
                    self.assertEqual(case.runtime.status()["spent_inputs"], charges)
                    self.assertEqual(case.runtime.status()["phase"], "active")
                finally:
                    case.doCleanups()

    def test_observe_cannot_hide_timestamp_mutation_of_the_same_immutable_capture(self):
        self.start()
        observe = self.controller.observe_mission

        def contradicted(**kwargs):
            captured, received = observe(**kwargs)
            changed = copy.deepcopy(captured)
            changed["timestamp_ms"] += 1
            core.atomic_json(self.controller.bridge / "state.json", changed)
            self.controller.status()
            return captured, received

        with patch.object(self.controller, "observe_mission", contradicted):
            operation = self.observe()
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertIn("immutable capture", operation["result"]["reason"])
        self.assertIsNone(self.runtime._lease)
        self.assertNotEqual(self.runtime.status()["phase"], "active")

    def test_changed_semantic_intent_returns_fresh_evidence_without_input_or_lineage_rollback(self):
        self.allow_direct()
        root, _ = self.open_direction()
        old = self.runtime._prompt_phase
        view = dict(kind="direction", basis="player_interpretation",
                    source_id=old.checkpoint.observation_id, question="Where?")
        choice = self.control("menu", dict(purpose="Choose observed direction", label="Here", outcome="activated"),
                              phase_id=root["request_id"], request_id="old-semantic-choice", perception=view)
        delivered = copy.deepcopy(self.bridge.delivered)
        self.advance_visible()
        self.assertEqual(self.runtime.command(choice)["status"], "accepted")
        operation = self.settled(choice["request_id"])
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertIn("does not support", operation["result"]["reason"])
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertEqual(self.runtime.status()["phase"], "active")
        self.assertEqual(self.runtime._prompt_phase.root_id, old.root_id)
        self.assertNotEqual(self.runtime._prompt_phase.checkpoint, old.checkpoint)
        self.assertEqual(self.runtime._prompt_phase.checkpoint, self.runtime._current)
        self.assertFalse(self.runtime._prompt_phase.quantity_editor)
        self.assertEqual(self.observe()["state"], "completed")

    def test_late_semantic_drift_refuses_without_weakening_preflight_or_ending_the_mission(self):
        for point, fault in (("rotation", None), ("acquisition", None), ("preflight", None), ("prepared", None),
                             ("rotation", "future"), ("rotation", "regression"), ("rotation", "contradiction"),
                             ("acquisition", "future"), ("acquisition", "regression"), ("acquisition", "contradiction"),
                             ("prepared", "pause"), ("prepared", "pending"), ("prepared", "global_deadline")):
            with self.subTest(point=point, fault=fault):
                case = type(self)()
                case.setUp()
                try:
                    case.allow_direct()
                    root, _ = case.native_choices()
                    choice = case.control("menu", dict(purpose="Choose", label="Two", outcome="focused"),
                        phase_id=root["request_id"], request_id="late-semantic-choice")
                    delivered = copy.deepcopy(case.bridge.delivered)
                    primitives = case.runtime._ledger.primitive_records()
                    rotation, acquisition = case.runtime._rotate, case.controller.acquire_mission
                    exchange, prepare = case.controller._exchange, case.runtime._ledger.prepare_primitive
                    observed = []

                    def changed():
                        case.advance_visible(fault)
                        if fault == "pause": case.runtime.pause("Actual user Pause in the interleaving")
                        elif fault == "pending": case.controller.pending = {"id": "other-writer"}
                        elif fault == "global_deadline": case.runtime._mission_deadline = case.runtime._wall()

                    def before_rotation(*args, **kwargs):
                        changed()
                        return rotation(*args, **kwargs)

                    def before_acquisition(*args, **kwargs):
                        changed()
                        return acquisition(*args, **kwargs)

                    def before_observation(kind, *args, **kwargs):
                        if kind == "observe":
                            observed.append(kind)
                            if len(observed) == 2: changed()
                        return exchange(kind, *args, **kwargs)

                    def after_preparation(*args, **kwargs):
                        result = prepare(*args, **kwargs)
                        changed()
                        return result

                    with ExitStack() as stack:
                        if point == "rotation": stack.enter_context(patch.object(case.runtime, "_rotate", before_rotation))
                        elif point == "acquisition": stack.enter_context(patch.object(case.controller, "acquire_mission", before_acquisition))
                        elif point == "preflight": stack.enter_context(patch.object(case.controller, "_exchange", before_observation))
                        else: stack.enter_context(patch.object(case.runtime._ledger, "prepare_primitive", after_preparation))
                        self.assertEqual(case.runtime.command(choice)["status"], "accepted")
                        operation = case.settled(choice["request_id"])
                    self.assertEqual(case.bridge.delivered, delivered, operation)
                    rows = case.runtime._ledger.primitive_records()
                    self.assertEqual(rows[:len(primitives)], primitives)
                    self.assertEqual(len(rows), len(primitives) + (point == "prepared"))
                    if fault is None:
                        self.assertEqual(operation["state"], "blocked", operation)
                        self.assertEqual(operation["result"]["phase"]["stage"], "awaiting_observation")
                        self.assertEqual(case.runtime.status()["phase"], "active")
                        if point == "prepared": self.assertEqual(rows[-1]["state"], "not_dispatched")
                        self.assertEqual(case.observe()["state"], "completed")
                    else:
                        self.assertIsNone(case.runtime._lease)
                        self.assertNotEqual(case.runtime.status()["phase"], "active")
                finally:
                    case.controller.pending = None
                    case.doCleanups()

    def test_navigation_preflight_menu_is_inapplicable_not_a_navigation_custody_fault(self):
        self.start()
        choice = self.navigation(target=(1, 0, 0), request_id="route-with-new-menu")
        exchange = self.controller._exchange
        observations = []
        delivered = copy.deepcopy(self.bridge.delivered)

        def observed(kind, *args, **kwargs):
            if kind == "observe":
                observations.append(kind)
                if len(observations) == 2:
                    self.bridge.value.update(scene=None, ui=None)
                    self.bridge.value["boundary"].update(kind="menu", input_receiver=True)
                    self.advance_visible()
            return exchange(kind, *args, **kwargs)

        with patch.object(self.controller, "_exchange", side_effect=observed):
            self.assertEqual(self.runtime.command(choice)["status"], "accepted")
            operation = self.settled(choice["request_id"])
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertEqual(operation["result"]["phase"]["stage"], "awaiting_observation")
        self.assertEqual(operation["result"]["verified_steps"], 0)
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertEqual(self.runtime.status()["phase"], "active")
        self.assertEqual(self.runtime.status()["spent_inputs"], 0)
        self.assertEqual(self.observe()["state"], "completed")

    def test_changed_view_during_bad_draft_requires_observe_without_rewriting_the_draft(self):
        root, _ = self.open_direction()
        original = self.runtime._prompt_phase
        bad = self.control("menu", dict(purpose="Direction", label="Here", outcome="activated"),
                           phase_id=root["request_id"], request_id="bad-native-row-draft")
        retained_request = copy.deepcopy(bad)
        delivered, spent = copy.deepcopy(self.bridge.delivered), self.runtime.status()["spent_inputs"]
        self.advance_visible()
        self.assertEqual(self.runtime.command(bad)["status"], "accepted")
        operation = self.settled(bad["request_id"])
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertIn("Observe before correcting", operation["result"]["reason"])
        self.assertEqual(self.runtime._ledger.request(bad["request_id"])["request"], retained_request)
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertEqual(self.runtime.status()["phase"], "active")
        self.assertEqual(self.runtime._prompt_phase.root_id, original.root_id)
        self.assertEqual(self.runtime._prompt_phase.checkpoint, original.checkpoint)
        self.assertIsNotNone(self.runtime._prompt_phase.observation_generation)
        self.assertEqual(self.observe()["state"], "completed")

    def test_navigation_preserves_a_verified_return_but_never_continues_a_newer_live_view(self):
        self.start()
        request = self.navigation(target=(1, 0, 0), request_id="route-with-later-view")
        execute, ingest = self.controller.execute_mission, self.runtime._ingest
        returned, advanced = [], []

        def delivered(*args, **kwargs):
            result = execute(*args, **kwargs)
            returned.append(result)
            return result

        def retained(*args, **kwargs):
            reference = ingest(*args, **kwargs)
            if returned and not advanced:
                advanced.append(reference)
                self.bridge.value.update(scene=None, ui=None)
                self.bridge.value["boundary"].update(kind="menu", input_receiver=True)
                self.advance_visible()
            return reference

        with patch.object(self.controller, "execute_mission", delivered), patch.object(self.runtime, "_ingest", retained):
            self.assertEqual(self.runtime.command(request)["status"], "accepted")
            operation = self.settled(request["request_id"])
        self.assertEqual(len(returned), 1, operation)
        self.assertEqual(operation["state"], "partial", operation)
        self.assertEqual(operation["result"]["verified_steps"], 1)
        self.assertEqual(operation["result"]["position"], [1, 0, 0])
        self.assertEqual(operation["result"]["phase"]["stage"], "awaiting_observation")
        self.assertEqual(self.runtime.status()["phase"], "active")
        self.assertEqual(self.runtime._ledger.primitive_records()[-1]["state"], "returned")
        self.assertEqual(self.observe()["state"], "completed")
