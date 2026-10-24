"""Known native refusal and prompt diagnostics on a synthetic file bridge.

This reproduces a source defect, not the missing private state of Fresh024.
"""
import copy
from dataclasses import replace
from pathlib import Path
import unittest
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
