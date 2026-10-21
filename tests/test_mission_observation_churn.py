"""Causal passive-capture interleavings; synthetic transport, not native play."""
from contextlib import ExitStack
import copy
import json
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch

from harness import controller as controller_module
from harness.gameplay.contracts import ContractError
from harness.gameplay.semantic_controls import ControlIntent
from harness.gameplay.evidence import same_native_state
from harness.mission_runtime import _Work
from tests.test_mission_creation import MissionCreationFixture, expire_selected_at_dispatch
from tests import test_mission_runtime as runtime_fixtures


def passive_capture(controller, bridge):
    """Publish a synthetic unchanged heartbeat with the original immutable frame."""
    before, received = controller.observation_snapshot()
    image = (bridge.bridge / before["frame"]).read_bytes()
    response = bridge.bridge / "response.json"
    original_ack = response.read_bytes()
    count = bridge.frames
    bridge.publish_unchanged_passive(before)
    after = controller.status()["state"]
    assert before["frame"] == after["frame"] and same_native_state(before, after)
    assert before["timestamp_ms"] == after["timestamp_ms"]
    assert controller.observation_snapshot()[1] == received
    assert bridge.frames == count and (bridge.bridge / before["frame"]).read_bytes() == image
    assert response.read_bytes() == original_ack  # Includes original terminal UUID.
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

    def test_spectator_first_receipt_of_same_frame_keeps_terminal_clock_and_uuid(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        published = threading.Event()
        publish = self.bridge.publish
        read_json = controller_module.read_json
        execute = self.controller.execute_mission
        seen, receipts = [], []

        def publish_complete(value):
            publish(value)
            if value["category"] == "WORLDGEN_CONFIRM_DIALOG":
                published.set()

        def spectator_first(path):
            value = read_json(path)
            if (Path(path).name == "response.json" and value is not None
                    and value.get("status") == "ready" and value.get("category") == "WORLDGEN_CONFIRM_DIALOG"):
                # Fixture writes response before state; wait for the same frame's
                # actual state publication rather than polling an old boundary.
                self.assertTrue(published.wait(2))
                actual = self.controller.status()["state"]
                self.assertEqual(actual["frame"], value["frame"])
                seen.append(self.controller.observation_snapshot()[1])
            return value

        def terminal(*args, **kwargs):
            raw = execute(*args, **kwargs)
            receipts.append(copy.deepcopy(raw))
            return raw

        with patch.object(self.bridge, "publish", side_effect=publish_complete), \
                patch.object(controller_module, "read_json", side_effect=spectator_first), \
                patch.object(self.controller, "execute_mission", side_effect=terminal):
            result = self.run_request(self.control("world-form", "Create World"))
        self.assertEqual(result["state"], "partial", result)
        self.assertEqual(len(seen), 1)
        self.assertEqual(len(receipts), 1)
        raw = receipts[0]
        self.assertLess(seen[0], raw["received_monotonic"])
        primitive = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual(primitive["state"], "returned")
        self.assertEqual(primitive["native_id"], raw["request"]["id"])
        self.assertEqual(primitive["result"]["received_monotonic"], raw["received_monotonic"])
        ref = next(ref for ref in self.runtime._store.historical_references
                   if ref.observation_id == primitive["result"]["source_after"])
        self.assertEqual(self.runtime._store.observation(ref), raw["result"])
        self.assertEqual(ref.received_monotonic, raw["received_monotonic"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)

    def test_independent_receipt_clocks_keep_invalid_clock_state_and_uuid_checks(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        data = self.control("world-form", "Create World")
        receipts = []
        execute = self.controller.execute_mission
        def terminal(*args, **kwargs):
            raw = execute(*args, **kwargs)
            receipts.append(copy.deepcopy(raw))
            return raw
        with patch.object(self.controller, "execute_mission", side_effect=terminal):
            result = self.run_request(data)
        self.assertEqual(result["state"], "partial", result)
        raw = receipts[0]
        primitive = self.runtime._ledger.primitive_records()[-1]
        refs = {r.observation_id: r for r in self.runtime._store.historical_references}
        before = refs[primitive["intent"]["source_before"]]
        preflight = refs[primitive["intent"]["preflight_source"]]
        proposal = ControlIntent(primitive["logical_id"], "action", "CONFIRM", before,
                                 raw["request"]["boundary_id"])
        work = _Work(data)
        def check(value):
            return self.runtime._envelope(value, work, proposal, preflight, image_informed=True)
        for bad in (None, True, -1, float("nan"), float("inf"), time.monotonic() + 100, 10**1000):
            with self.subTest(snapshot_clock=type(bad).__name__), \
                    patch.object(self.controller, "observation_snapshot", return_value=(raw["result"], bad)):
                with self.assertRaisesRegex(ContractError, "current atomic"):
                    check(raw)
        variants = []
        for field, value in (("session", "other"), ("revision", raw["result"]["revision"] + 1),
                ("paused", True), ("takeover_generation", 1)):
            state = copy.deepcopy(raw["result"])
            state[field] = value
            variants.append(state)
        state = copy.deepcopy(raw["result"])
        state["boundary"]["id"] += "-changed"
        variants.append(state)
        for state in variants:
            with self.subTest(changed_snapshot=state["boundary"]["id"]), \
                    patch.object(self.controller, "observation_snapshot",
                                 return_value=(state, raw["received_monotonic"])):
                with self.assertRaisesRegex(ContractError, "current atomic"):
                    check(raw)
        for clock in (time.monotonic() - 4, time.monotonic() + 100,
                      preflight.received_monotonic - 0.001):
            value = copy.deepcopy(raw)
            value["received_monotonic"] = clock
            with self.subTest(terminal_clock=clock), self.assertRaisesRegex(ContractError, "terminal receipt time"):
                check(value)
        value = copy.deepcopy(raw)
        value["result"]["id"] = "00000000-0000-0000-0000-000000000000"
        with self.assertRaisesRegex(ContractError, "identity differs"):
            check(value)
        self.assertEqual(self.runtime._ledger.primitive(primitive["logical_id"]), primitive)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        events = [json.loads(line) for line in self.controller.journal.read_text().splitlines()]
        diagnostic = [event["outcome"] for event in events
                      if event["request"].get("kind") == "mission_ready_snapshot_mismatch"]
        self.assertEqual(len(diagnostic), 12)
        self.assertTrue(all(row["native_request_id"] == raw["request"]["id"]
                            and row["ready"] == raw["result"] for row in diagnostic))
        self.assertFalse(diagnostic[0]["snapshot_clock_valid"])

    def test_binding_does_not_turn_a_changed_image_into_input_consent(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        data = self.control("world-form", "Create World")
        before = self.runtime.status()["spent_inputs"]
        original, _ = self.controller.observation_snapshot()
        image = (self.bridge.bridge / original["frame"]).read_bytes()
        self.bridge.editor_text = "changed visible pixels"
        value = copy.deepcopy(original)
        value.update(id="", timestamp_ms=int(time.time() * 1000))
        self.bridge.publish(value)  # Changed capture must mint, never use unchanged helper.
        changed = self.controller.status()["state"]
        self.assertNotEqual(original["frame"], changed["frame"])
        self.assertNotEqual(image, (self.bridge.bridge / changed["frame"]).read_bytes())
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
    control = runtime_fixtures.MissionRuntimeTests.control
    open_direction = runtime_fixtures.MissionRuntimeTests.open_direction

    def test_fresh_navigation_revalidates_before_selected_source_expires(self):
        self.start()
        data = self.navigation(target=(1, 0, 0))
        before = self.runtime._current
        deadline = self.runtime._mission_deadline
        with expire_selected_at_dispatch(self.runtime, before):
            self.assertEqual(self.runtime.command(data)["status"], "accepted")
            result = self.settled(data["request_id"])
        self.assertEqual(result["state"], "completed", result)
        self.assertEqual(result["result"]["position"], [1, 0, 0])
        self.assertEqual(result["request"], data)
        primitive, = self.runtime._ledger.primitive_records()
        relation = primitive["intent"]["revalidation"]
        self.assertEqual(relation["original"]["source_id"], before.observation_id)
        self.assertEqual(relation["rule"], "native_state")
        self.assertEqual(len({before.observation_id, primitive["intent"]["source_before"],
                              primitive["intent"]["preflight_source"]}), 3)
        self.assertEqual(self.runtime._mission_deadline, deadline)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

    def test_fresh_prompt_revalidates_without_renewing_shared_root(self):
        root, _ = self.open_direction(limits=dict(primitives=2, wall_seconds=120, game_seconds=1200))
        before = self.runtime._current
        deadline = self.runtime._ledger.request(root["request_id"])["deadline"]
        child = self.control("menu", dict(purpose="Open direction", label="Here", outcome="activated"),
            phase_id=root["request_id"], perception=dict(kind="direction", basis="player_interpretation",
                source_id=before.observation_id, question="Where?"))
        with expire_selected_at_dispatch(self.runtime, before):
            self.assertEqual(self.runtime.command(child)["status"], "accepted")
            result = self.settled(child["request_id"])
        self.assertEqual(result["state"], "partial", result)
        self.assertEqual(result["result"]["phase"]["stage"], "complete")
        self.assertEqual(result["result"]["revalidation"]["rule"], "exact_png_bytes")
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertEqual(self.runtime._ledger.request(root["request_id"])["deadline"], deadline)
        self.assertIsNone(self.runtime._prompt_phase)

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
