"""Causal passive-capture interleavings; synthetic transport, not native play."""
from contextlib import ExitStack
import copy
import time
import unittest
from unittest.mock import patch

from harness.gameplay.evidence import same_native_state
from tests.test_mission_creation import MissionCreationFixture
from tests import test_mission_runtime as runtime_fixtures


def passive_capture(controller, bridge):
    """Publish another actual fixture frame without changing the native boundary."""
    before, _ = controller.observation_snapshot()
    value = copy.deepcopy(before)
    value.update(id="", timestamp_ms=int(time.time() * 1000))
    bridge.publish(value)
    after = controller.status()["state"]
    assert before["frame"] != after["frame"] and same_native_state(before, after)
    return after


def poll_at_boundaries(stack, controller, bridge, runtime):
    """Poll after actual Observe, final retention and ACK, without sleeps/races."""
    receipts = []
    observe = controller.observe_mission
    def observed(**kwargs):
        result, received = observe(**kwargs)
        if result.get("status") == "ready":
            original = copy.deepcopy(result)
            passive_capture(controller, bridge)
            receipts.append((original, received))
        return result, received
    stack.enter_context(patch.object(controller, "observe_mission", side_effect=observed))
    retain = runtime._store.retain_equivalent
    def retained(*args, **kwargs):
        result = retain(*args, **kwargs)
        passive_capture(controller, bridge)
        return result
    stack.enter_context(patch.object(runtime._store, "retain_equivalent", side_effect=retained))
    for name in ("execute_mission", "resume_mission"):
        original = getattr(controller, name)
        def returned(*args, _original=original, **kwargs):
            result = _original(*args, **kwargs)
            if result["result"].get("status") == "ready":
                passive_capture(controller, bridge)
            return result
        stack.enter_context(patch.object(controller, name, side_effect=returned))
    return receipts


class LifecycleObservationChurnTests(MissionCreationFixture, unittest.TestCase):
    def test_creation_identity_save_and_exit_keep_actual_receipts_under_polling(self):
        self.ready()
        initial = copy.deepcopy(self.runtime._store.observation(self.runtime._current))
        passive_capture(self.controller, self.bridge)
        with ExitStack() as stack:
            receipts = poll_at_boundaries(stack, self.controller, self.bridge, self.runtime)
            stack.enter_context(patch.object(self, "ready"))
            self.create()
            self.save()
            self.exit()
        self.assertEqual(self.runtime._store.observation(
            self.runtime._store.historical_references[0]), initial)
        for source, received in receipts:
            refs = [ref for ref in self.runtime._store.historical_references
                    if self.runtime._store.observation(ref)["frame"] == source["frame"]]
            if refs:
                self.assertEqual(self.runtime._store.observation(refs[0]), source)
                self.assertEqual(refs[0].received_monotonic, received)
        primitives = self.runtime._ledger.primitive_records()
        self.assertTrue(primitives)
        self.assertTrue(all(p["state"] == "returned" or p["state"] == "unknown" and p["effect"] is not None
                            for p in primitives))
        self.assertEqual(primitives[-1]["state"], "unknown")
        self.assertEqual(self.runtime.status()["spent_inputs"], len(primitives))
        self.assertIsNotNone(primitives[-1]["effect"])

    def test_binding_does_not_turn_a_changed_image_into_input_consent(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        data = self.control("world-form", "Create World")
        before = self.runtime.status()["spent_inputs"]
        self.bridge.editor_text = "changed visible pixels"
        passive_capture(self.controller, self.bridge)
        result = self.run_request(data)
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(self.runtime.status()["spent_inputs"], before)


class NormalObservationChurnTests(unittest.TestCase):
    setUp = runtime_fixtures.MissionRuntimeTests.setUp
    start = runtime_fixtures.MissionRuntimeTests.start
    wait = runtime_fixtures.MissionRuntimeTests.wait
    request = runtime_fixtures.MissionRuntimeTests.request
    result = runtime_fixtures.MissionRuntimeTests.result
    settled = runtime_fixtures.MissionRuntimeTests.settled
    navigation = runtime_fixtures.MissionRuntimeTests.navigation

    def test_navigation_uses_original_sources_and_correlated_acks_under_polling(self):
        self.start()
        data = self.navigation(target=(1, 0, 0))
        original = self.runtime._current
        before = self.runtime._store.observation(original)
        passive_capture(self.controller, self.bridge)
        with ExitStack() as stack:
            poll_at_boundaries(stack, self.controller, self.bridge, self.runtime)
            response = self.runtime.command(data)
            self.assertEqual(response["status"], "accepted", response)
            result = self.settled(data["request_id"])
        self.assertEqual(result["state"], "completed", result)
        self.assertEqual(result["result"]["position"], [1, 0, 0])
        self.assertEqual(self.runtime._store.observation(original), before)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        for primitive in self.runtime._ledger.primitive_records():
            receipt = primitive["result"]
            self.assertEqual(primitive["state"], "returned")
            after = self.runtime._store.observation(next(ref for ref in self.runtime._store.historical_references
                if ref.observation_id == receipt["source_after"]))
            self.assertEqual(after["id"], primitive["native_id"])
            self.assertNotEqual(after["id"], "")
