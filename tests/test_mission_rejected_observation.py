"""Known native refusal and prompt diagnostics on a synthetic file bridge.

This reproduces a source defect, not the missing private state of Fresh024.
"""
import copy
from dataclasses import replace
from pathlib import Path
import unittest
import time
from unittest.mock import patch

from harness.gameplay.evidence import EvidenceError
from harness.mission_runtime import _Work
from tests import test_mission_prompt_observation as prompts


class RejectedObservationTests(unittest.TestCase):
    setUp = prompts.PromptObservationTests.setUp
    wait = prompts.PromptObservationTests.wait
    request = prompts.PromptObservationTests.request
    result = prompts.PromptObservationTests.result
    settled = prompts.PromptObservationTests.settled
    start = prompts.PromptObservationTests.start
    control = prompts.PromptObservationTests.control
    navigation = prompts.core.MissionRuntimeTests.navigation
    open_direction = prompts.PromptObservationTests.open_direction
    allow_direct = prompts.PromptObservationTests.allow_direct
    direct = prompts.PromptObservationTests.direct
    observe = prompts.PromptObservationTests.observe
    send = prompts.PromptObservationTests.send

    def rejected(self, *, fault=None, healthy=True):
        self.allow_direct()
        root, _ = self.open_direction()
        root_record = self.runtime._ledger.request(root["request_id"])

        def refuse(bridge, request):
            if request["kind"] == "direct":
                # The fake bridge increments/delivers before this callback;
                # model an authenticated native refusal with no actual input.
                bridge.delivered.pop()
                bridge.value["revision"] -= 1
                bridge.value.update(status="rejected", error="Arbitrary native refusal")
            else:
                bridge.value.update(status="ready", error="")
            return True

        self.bridge.behavior = refuse
        execute = self.controller.execute_mission

        def ready(*args, **kwargs):
            raw = execute(*args, **kwargs)
            if healthy:
                self.bridge.value.update(status="ready", error="")
                self.bridge.publish(copy.deepcopy(self.bridge.value))
                self.controller.status()
            if fault == "store":
                self.runtime._store._authority_generation += 1
            elif fault == "integrity":
                Path(self.runtime._prompt_phase.checkpoint.frame_path).unlink()
            elif fault == "takeover":
                with self.controller.data_lock:
                    self.controller.state["takeover_generation"] += 1
            elif fault == "game_budget":
                self.runtime._game_cost = self.a.limits.game_seconds
            return raw

        before = copy.deepcopy(self.bridge.delivered)
        with patch.object(self.controller, "execute_mission", side_effect=ready):
            operation = self.send(self.direct(root, "native-refusal"))
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertEqual(self.bridge.delivered, before)
        self.assertEqual(self.runtime._ledger.request(root["request_id"]), root_record)
        primitive = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual(primitive["state"], "rejected")
        self.assertTrue(primitive["result"]["published"])
        self.assertEqual(primitive["result"]["native_ack"]["status"], "rejected")
        self.assertIsNone(primitive["result"]["source_after"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        return root, root_record, operation

    def test_known_rejection_retains_only_observation_then_new_explicit_choice(self):
        root, root_record, operation = self.rejected()
        phase = self.runtime._prompt_phase
        self.assertEqual(phase.observation_generation, self.runtime._lease.pause_generation)
        binding = self.runtime._bindings[phase.checkpoint.observation_id][1]
        self.assertEqual(binding.pause_generation + 1, phase.observation_generation)
        self.assertTrue(self.runtime.status()["prompt_phase"]["observation_needed"])
        self.assertIsNone(self.runtime.status()["current_source"])
        receipts = self.runtime._ledger.primitive_records()
        deadline = self.runtime.status()["deadline"]
        self.assertEqual(self.observe()["state"], "completed")
        self.assertEqual(self.runtime._ledger.primitive_records(), receipts)
        self.assertEqual(self.runtime._ledger.request(root["request_id"]), root_record)
        self.assertEqual(self.result("native-refusal"), operation)
        self.assertEqual(self.runtime.status()["deadline"], deadline)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.bridge.behavior = lambda bridge, request: True
        current = self.send(self.direct(root, "new-explicit-choice"))
        self.assertEqual(current["state"], "partial", current)
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)
        self.assertEqual(self.result("native-refusal"), operation)

    def test_rejection_does_not_hide_actual_custody_storage_or_global_fault(self):
        for fault in ("store", "integrity", "takeover", "game_budget"):
            with self.subTest(fault=fault):
                case = type(self)()
                case.setUp()
                try:
                    case.rejected(fault=fault)
                    self.assertIsNone(case.runtime._lease)
                    self.assertIsNone(case.runtime._prompt_phase)
                finally:
                    case.doCleanups()

    def test_unhealthy_native_rejection_does_not_grant_observation_lineage(self):
        self.rejected(healthy=False)
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._prompt_phase)

    def test_missing_ack_stays_unknown_without_refusal_continuation(self):
        self.allow_direct()
        root, _ = self.open_direction()
        original = self.runtime._ledger.request(root["request_id"])
        self.bridge.behavior = lambda bridge, request: request["kind"] != "direct"
        operation = self.send(self.direct(root, "withheld-ack"))
        self.assertEqual(operation["state"], "unknown", operation)
        self.assertEqual(self.runtime._ledger.primitive_records()[-1]["state"], "unknown")
        self.assertEqual(self.runtime._ledger.request(root["request_id"]), original)
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)

    def semantic_rejection(self, *, prompt=False, fault=None, navigate=False, aged=False, prefix=False):
        self.allow_direct()
        root = self.open_direction()[0] if prompt else None
        if root is None:
            self.bridge.value["actions"].append("open")
            self.start()
        if prefix:
            for target, identity in (((1, 0, 0), "map-neighbour"), ((0, 0, 0), "return-before-route")):
                self.assertEqual(self.send(self.navigation(target=target, request_id=identity))["state"], "completed")
        original = self.runtime.status()
        if prompt:
            source = original["current_source"]["observation_id"]
            request = self.control("menu", dict(purpose="Direction", label="Here", outcome="activated"),
                phase_id=root["request_id"], request_id="semantic-refusal",
                perception=dict(kind="direction", basis="player_interpretation", source_id=source, question="Where?"))
        elif navigate:
            request = self.navigation(target=(2 if prefix else 1, 0, 0), request_id="semantic-refusal")
        else:
            request = self.control("interact", dict(action="open", intent="Inspect here",
                desired_outcome="Interpret the actual result"), request_id="semantic-refusal")
        before = copy.deepcopy(self.bridge.delivered)
        prior_scene = None
        attempted = 0
        def refuse(bridge, packet):
            nonlocal attempted
            if packet["kind"] in ("action", "key", "direct"):
                attempted += 1
                if prefix and attempted == 1:
                    return True
                bridge.delivered.pop()
                bridge.value["revision"] -= 1
                bridge.value["scene"] = copy.deepcopy(prior_scene)
                bridge.value.update(status="rejected", error="Arbitrary native refusal")
            else:
                bridge.value.update(status="ready", error="")
            return True
        self.bridge.behavior = refuse
        execute = self.controller.execute_mission
        def ready(*args, **kwargs):
            nonlocal prior_scene
            prior_scene = copy.deepcopy(self.bridge.value["scene"])
            raw = execute(*args, **kwargs)
            if raw["result"].get("status") != "rejected":
                return raw
            self.bridge.value.update(status="ready", error="")
            self.bridge.publish(copy.deepcopy(self.bridge.value))
            self.controller.status()
            if fault == "store":
                self.runtime._store._authority_generation += 1
            elif fault == "integrity":
                Path(self.runtime._current.frame_path).unlink()
            elif fault == "takeover":
                with self.controller.data_lock:
                    self.controller.state["takeover_generation"] += 1
            elif fault == "operator_pause":
                self.controller.pause()
            elif fault == "game_budget":
                self.runtime._game_cost = self.a.limits.game_seconds
            elif fault == "processing":
                raw["processing_error"] = "Injected controller processing failure"
            elif fault == "ack":
                raw["result"]["id"] = "mismatched-rejection"
            return raw
        dispatch = self.runtime._dispatch
        def feedback(*args, **kwargs):
            result = dispatch(*args, **kwargs)
            if aged and result.transport_disposition == "rejected":
                # Age only after authenticated rejection/read-only continuation;
                # no stale controller snapshot can establish that health proof.
                time.sleep(3.1)
            return result
        with patch.object(self.controller, "execute_mission", side_effect=ready), \
                patch.object(self.runtime, "_dispatch", side_effect=feedback):
            operation = self.send(request)
        unknown = fault == "ack"
        self.assertEqual(operation["state"], "unknown" if unknown else "partial" if prefix else "blocked", operation)
        self.assertEqual(self.bridge.delivered[:len(before)], before)
        self.assertEqual(len(self.bridge.delivered), len(before) + int(prefix))
        if prefix:
            self.assertEqual(operation["result"]["verified_steps"], 1)
            self.assertEqual(self.runtime._ledger.primitive_records()[-2]["state"], "returned")
        primitive = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual(primitive["state"], "unknown" if unknown else "rejected")
        self.assertTrue(primitive["result"]["published"])
        self.assertIsNone(primitive["result"]["source_after"])
        if unknown:
            self.assertIsNone(primitive["result"]["native_ack"])
        else:
            self.assertEqual(primitive["result"]["native_ack"]["status"], "rejected")
        self.assertEqual(self.runtime.status()["spent_inputs"], original["spent_inputs"] + 1 + int(prefix))
        return request, operation, original

    def test_semantic_native_rejection_requires_observe_before_ordinary_fallback(self):
        for prompt, navigate, aged, prefix in (
                (False, False, False, False), (True, False, False, False),
                (False, False, True, False), (True, False, True, False),
                (False, True, True, False), (False, True, True, True)):
            with self.subTest(prompt=prompt, navigate=navigate, aged=aged, prefix=prefix):
                case = type(self)()
                case.setUp()
                try:
                    request, operation, original = case.semantic_rejection(prompt=prompt, navigate=navigate, aged=aged, prefix=prefix)
                    status = case.runtime.status()
                    self.assertEqual(status["phase"], "active", status)
                    self.assertIsNone(status["current_source"])
                    self.assertTrue(status["prompt_phase"]["observation_needed"])
                    lease, phase = case.runtime._lease, case.runtime._prompt_phase
                    self.assertEqual(phase.observation_generation, lease.pause_generation)
                    self.assertEqual(case.runtime._bindings[phase.checkpoint.observation_id][1].pause_generation + int(not prefix),
                                     lease.pause_generation)
                    charges = case.runtime._ledger.primitive_records()
                    stale = {**request, "request_id": "stale-fallback"}
                    refused = case.runtime.command(stale)
                    self.assertEqual(refused["status"], "rejected", refused)
                    self.assertTrue("Observe" in refused["reason"] or "exact phase" in refused["reason"], refused)
                    self.assertIs(case.runtime._lease, lease)
                    self.assertIs(case.runtime._prompt_phase, phase)
                    self.assertEqual(case.observe()["state"], "completed")
                    self.assertEqual(case.runtime._ledger.primitive_records(), charges)
                    self.assertEqual(case.result(request["request_id"]), operation)
                    for field in ("epoch", "deadline", "player_id", "cleanup_reserve"):
                        self.assertEqual(case.runtime.status()[field], original[field])
                    if not prompt:
                        self.assertIsNone(case.runtime._prompt_phase)
                    current = case.direct({"request_id": phase.root_id}, "ordinary-fallback")
                    if not prompt:
                        current["phase_id"] = None
                    case.bridge.behavior = lambda bridge, packet: True
                    self.assertEqual(case.send(current)["state"], "partial")
                    self.assertEqual(case.runtime.status()["spent_inputs"], len(charges) + 1)
                finally:
                    case.doCleanups()

    def test_semantic_native_rejection_cannot_hide_custody_storage_or_global_fault(self):
        for fault in ("store", "integrity", "takeover", "operator_pause", "game_budget", "processing"):
            with self.subTest(fault=fault):
                case = type(self)()
                case.setUp()
                try:
                    case.semantic_rejection(fault=fault)
                    self.assertIsNone(case.runtime._lease)
                    self.assertIsNone(case.runtime._prompt_phase)
                finally:
                    case.doCleanups()

    def test_miscorrelated_semantic_rejection_stays_unknown(self):
        self.semantic_rejection(fault="ack")
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["unreconciled"], 1)

    def test_predicate_label_is_retained_in_the_original_observe_result(self):
        self.open_direction()
        self.runtime._store._authority_generation += 1
        operation = self.observe()
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertEqual(operation["result"]["reason"],
                         "EvidenceError: Observe prompt authority lost: store_generation")
        self.assertEqual(self.result("explicit-look"), operation)

    def test_prompt_guard_names_each_original_failure_without_dumping_state(self):
        root, _ = self.open_direction()
        phase = self.runtime._prompt_phase
        before = self.runtime._bindings[phase.checkpoint.observation_id]
        original = before[1]
        for label, binding in (
                ("binding_identity", replace(original, actor_id="different-actor")),
                ("pause_generation", replace(original, pause_generation=original.pause_generation + 2)),
                ("store_generation", replace(original, store_generation=original.store_generation + 1))):
            with self.subTest(label=label):
                self.runtime._bindings[phase.checkpoint.observation_id] = (before[0], binding)
                with self.assertRaisesRegex(EvidenceError, "^Observe prompt authority lost: " + label + "$"):
                    self.runtime._prompt_observation_guard(_Work(root), phase)
        self.runtime._bindings[phase.checkpoint.observation_id] = before
        with patch.object(self.runtime._store, "source_status", return_value="disputed"):
            with self.assertRaisesRegex(EvidenceError, "^Observe prompt authority lost: source_retention$"):
                self.runtime._prompt_observation_guard(_Work(root), phase)
        # The intended pending one-generation pattern remains valid.
        phase = replace(phase, observation_generation=original.pause_generation)
        self.runtime._prompt_phase = phase
        self.runtime._bindings[phase.checkpoint.observation_id] = (
            before[0], replace(original, pause_generation=original.pause_generation - 1))
        self.runtime._prompt_observation_guard(_Work(root), phase)
