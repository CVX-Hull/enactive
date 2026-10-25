"""Known delivery with absent/aged current evidence; synthetic visible transport."""
import copy
from contextlib import nullcontext
from dataclasses import replace
import threading
import unittest
from unittest.mock import patch

from harness.gameplay.mission_contracts import validate_admission_refusal, validate_submission
from tests import test_mission_prompt_observation as fixtures


class PendingObservationTests(unittest.TestCase):
    setUp = fixtures.PromptObservationTests.setUp
    wait = fixtures.PromptObservationTests.wait
    request = fixtures.PromptObservationTests.request
    result = fixtures.PromptObservationTests.result
    settled = fixtures.PromptObservationTests.settled
    start = fixtures.PromptObservationTests.start
    control = fixtures.PromptObservationTests.control
    open_direction = fixtures.PromptObservationTests.open_direction
    allow_direct = fixtures.PromptObservationTests.allow_direct
    direct = fixtures.PromptObservationTests.direct
    observe = fixtures.PromptObservationTests.observe

    def test_pending_text_busy_refusal_then_obsolete_enter_preserves_healthy_prompt(self):
        self.allow_direct()
        second, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        def text_effect(bridge, request):
            if request["kind"] == "direct":
                physical = request["input"]
                if physical["type"] == "text":
                    if physical["text"] == "b":
                        second.set()
                        self.assertTrue(release.wait(3))
                    bridge.editor_text = (bridge.editor_text or "") + physical["text"]
            return True

        root, _ = self.open_direction(prompt=dict(category="STRING_INPUT", actions=["ANY_INPUT"]),
            effect=text_effect)
        text = self.control("direct", dict(input=dict(type="text", text="ab"), intent="Enter observed search text",
            expected="Inspect the completed text", interrupt_allowed=False),
            phase_id=root["request_id"], request_id="pending-text")
        self.runtime.command(text)
        self.assertTrue(second.wait(2))
        stale = self.direct(root, request_id="busy-enter", key="ENTER")
        busy = self.runtime.command(stale)
        self.assertEqual(busy["status"], "rejected")
        self.assertEqual(busy["input_owner_operation_id"], text["request_id"])
        self.assertIn("Collect the original", busy["mission"]["next_needed_decision"])
        stale["request_id"] = "obsolete-enter"
        release.set()
        self.assertEqual(self.settled(text["request_id"])["state"], "partial")
        self.wait(lambda: self.runtime._active is None)
        phase, lease = self.runtime._prompt_phase, self.runtime._lease
        before, delivered = self.runtime.status(), copy.deepcopy(self.bridge.delivered)
        self.runtime.command(stale)
        refused = self.settled(stale["request_id"])
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertEqual(refused["result"]["proposals"], 0)
        self.assertIn("superseded", refused["result"]["reason"])
        self.assertIs(self.runtime._prompt_phase, phase)
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(self.runtime.status()["phase"], "active")
        self.assertEqual(self.runtime.status()["epoch"], before["epoch"])
        self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"])
        self.assertEqual(self.bridge.delivered, delivered)
        fresh = self.direct(root, request_id="fresh-explicit-enter", key="ENTER")
        self.runtime.command(fresh)
        self.assertEqual(self.settled(fresh["request_id"])["state"], "partial")
        self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"] + 1)

    def pending(self, kind="absent", *, new_root=False, limits=None, advance=0, expect_pending=True):
        self.allow_direct()
        if new_root:
            self.start()
            root = None
        else:
            root, _ = self.open_direction(**({"limits": limits} if limits else {}))
        old = self.runtime._prompt_phase
        execute = self.controller.execute_mission
        snapshot = self.controller.observation_snapshot
        returned = []

        def effect(bridge, request):
            if request["kind"] == "direct":
                if advance:
                    scene = copy.deepcopy(self.runtime._store.observation(
                        old.game_anchor if old else self.runtime._current)["scene"])
                    scene["turn"] += advance
                    bridge.value.update(scene=scene, ui=None, category="DEFAULTMODE")
                    bridge.value["boundary"].update(kind="normal_play", id="advanced-normal")
                elif new_root:
                    bridge.value.update(scene=None, ui=None, category="NOVEL_MENU", actions=["NOVEL_ACTION"])
                    bridge.value["boundary"].update(kind="menu", id="novel-menu")
            return True

        self.bridge.behavior = effect
        request = self.control("direct", dict(input=dict(type="text", text="ab"), intent="Try observed input",
            expected="Interpret actual effect", interrupt_allowed=False),
            phase_id=None if root is None else root["request_id"], request_id="input-needing-look")

        def deliver(*args, **kwargs):
            raw = execute(*args, **kwargs)
            returned.append(copy.deepcopy(raw))
            return raw

        def unavailable():
            state, received = snapshot()
            if returned:
                return (None, None) if kind == "absent" else (state, received - 4)
            return state, received

        with patch.object(self.controller, "execute_mission", side_effect=deliver), \
                patch.object(self.controller, "observation_snapshot", side_effect=unavailable):
            self.assertEqual(self.runtime.command(request)["status"], "accepted")
            operation = self.settled(request["request_id"])
        self.assertEqual(len(returned), 1, operation)
        if expect_pending:
            self.assertEqual(operation["state"], "partial", operation)
            self.assertEqual(operation["result"]["phase"]["stage"], "awaiting_observation")
        return root or request, old, request, operation

    def test_missing_current_retains_scope_and_ack_then_explicit_observe_permits_new_choice(self):
        self.resume_from_pending("absent")

    def test_stale_current_retains_scope_and_ack_then_explicit_observe_permits_new_choice(self):
        self.resume_from_pending("stale")

    def test_completed_input_publication_precedes_terminal_collection_cache(self):
        cached = self.runtime._cache_operation
        published = []
        def collect_after_publication(operation):
            result = operation.get("result")
            if result is not None and result.get("phase", {}).get("stage") == "awaiting_observation":
                published.append(self.runtime.status()["next_needed_decision"])
            cached(operation)
        with patch.object(self.runtime, "_cache_operation", side_effect=collect_after_publication):
            self.resume_from_pending("stale")
        self.assertTrue(published)
        self.assertTrue(all("Observe" in decision for decision in published), published)

    def resume_from_pending(self, kind):
        root, old, request, operation = self.pending(kind)
        phase = self.runtime._prompt_phase
        self.assertEqual((phase.root_id, phase.game_anchor, phase.actor_id, phase.epoch,
                          phase.operator_generation, phase.takeover_generation),
                         (old.root_id, old.game_anchor, old.actor_id, old.epoch,
                          old.operator_generation, old.takeover_generation))
        self.assertFalse(phase.quantity_editor)
        self.assertEqual(phase.observation_generation, self.runtime._lease.pause_generation)
        self.assertLess(self.runtime._bindings[phase.checkpoint.observation_id][1].pause_generation,
                        phase.observation_generation)
        status = self.runtime.status()
        self.assertEqual(status["phase"], "active")
        self.assertIsNone(status["current_source"])
        self.assertTrue(status["prompt_phase"]["observation_needed"])
        self.assertIn("Observe", status["next_needed_decision"])
        lease = self.runtime._lease
        receipts = self.runtime._ledger.primitive_records()
        terminal = receipts[-1]["result"]
        self.assertEqual(receipts[-1]["state"], "returned")
        self.assertIsNone(terminal["processing_error"])
        self.assertIsNone(terminal["evidence_loss"])
        self.assertNotEqual(terminal["source_after"], self.runtime._current.observation_id)
        # Even an already-built child queued after the completed operation must
        # refuse without another charge, lease rotation or automatic Pause.
        stale_child = copy.deepcopy(request)
        stale_child.update(request_id="input-before-look", phase_id=root["request_id"])
        self.assertEqual(self.runtime.command(stale_child)["status"], "rejected")
        self.assertEqual(self.runtime._ledger.primitive_records(), receipts)
        self.assertIs(self.runtime._lease, lease)
        observed = self.observe()
        self.assertEqual(observed["state"], "completed", observed)
        self.assertNotIn("revalidation", observed["result"])
        advanced = self.runtime._prompt_phase
        self.assertIsNone(advanced.observation_generation)
        self.assertEqual(advanced.root_id, root["request_id"])
        self.assertEqual(advanced.game_anchor, old.game_anchor)
        self.assertNotEqual(advanced.checkpoint, phase.checkpoint)
        self.assertEqual(self.runtime._bindings[advanced.checkpoint.observation_id][1].pause_generation,
                         lease.pause_generation)
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(self.runtime._ledger.primitive_records(), receipts)
        self.assertEqual(self.result(request["request_id"]), operation)
        chosen = self.direct(root, request_id="new-physical-choice", key="x")
        self.assertEqual(self.runtime.command(chosen)["status"], "accepted")
        self.assertEqual(self.settled(chosen["request_id"])["state"], "partial")
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)

    def test_new_root_from_normal_keeps_read_only_scope_until_observed_menu(self):
        root, _, _, _ = self.pending(new_root=True)
        phase = self.runtime._prompt_phase
        self.assertEqual(phase.checkpoint.boundary_kind, "normal_play")
        self.assertEqual(phase.root_id, root["request_id"])
        observed = self.observe()
        self.assertEqual(observed["state"], "completed", observed)
        self.assertEqual(self.runtime._prompt_phase.checkpoint.boundary_kind, "menu")
        self.assertIsNone(self.runtime._prompt_phase.observation_generation)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

    def test_pending_normal_root_observes_normal_return_without_replaying_or_goal_credit(self):
        root, _, _, operation = self.pending(new_root=True, advance=1)
        original = self.runtime._ledger.request(root["request_id"])
        receipts = self.runtime._ledger.primitive_records()
        lease = self.runtime._lease
        observed = self.observe()
        self.assertEqual(observed["state"], "completed", observed)
        self.assertEqual(observed["result"]["phase"]["stage"], "complete")
        self.assertNotIn("macro_closure", observed["result"])
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(self.runtime.status()["phase"], "active")
        self.assertEqual(self.runtime._ledger.request(root["request_id"]), original)
        self.assertEqual(self.runtime._ledger.primitive_records(), receipts)
        self.assertEqual(self.result(root["request_id"]), operation)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

    def test_lifecycle_queued_before_pending_scope_is_refused_at_writer_consumption(self):
        self.pending()
        from harness.mission_runtime import _Work
        current = self.runtime._current
        request = validate_submission(self.request("lifecycle", operation="save",
            world=self.a.scenario.world, character=self.a.scenario.character,
            sources=[current.observation_id],
            expected_session=current.session, expected_revision=current.revision,
            expected_boundary_id=self.runtime._store.observation(current)["boundary"]["id"],
            limits=dict(primitives=8, wall_seconds=120, game_seconds=1200)))
        lease = self.runtime._lease
        receipts = self.runtime._ledger.primitive_records()
        queued = _Work(request)
        self.runtime._queue.put_nowait(queued)  # Model a request already past ingress.
        self.wait(queued.ready.is_set)
        self.assertEqual(queued.response["status"], "rejected")
        self.assertIn("Observe", queued.response["reason"])
        validate_admission_refusal(queued.response["admission_refusal"], request)
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(self.runtime._ledger.primitive_records(), receipts)
        self.assertFalse(any(row["request"]["request_id"] == request["request_id"]
                             for row in self.runtime._ledger.request_records()))

    def test_pending_observe_rejects_changed_generation_store_custody_and_integrity(self):
        for fault in ("generation", "store", "takeover", "integrity", "unsettled"):
            with self.subTest(fault=fault):
                case = type(self)()
                case.setUp()
                try:
                    case.pending()
                    phase = case.runtime._prompt_phase
                    receipts = case.runtime._ledger.primitive_records()
                    if fault == "generation":
                        case.runtime._prompt_phase = replace(phase, observation_generation=phase.observation_generation + 1)
                    elif fault == "store":
                        case.runtime._store._authority_generation += 1
                    elif fault == "takeover":
                        with case.controller.data_lock:
                            case.controller.state["takeover_generation"] += 1
                    elif fault == "integrity":
                        from pathlib import Path
                        Path(phase.checkpoint.frame_path).unlink()
                    counts = case.runtime._ledger.measured_counts()
                    counts["primitives"]["by_state"]["prepared"] = 1
                    guard = (patch.object(case.runtime._ledger, "measured_counts", return_value=counts)
                             if fault == "unsettled" else nullcontext())
                    with guard:
                        observed = case.observe()
                    self.assertEqual(observed["state"], "blocked", observed)
                    self.assertIsNone(case.runtime._lease)
                    self.assertIsNone(case.runtime._prompt_phase)
                    self.assertEqual(case.runtime._ledger.primitive_records()[-1]["result"], receipts[-1]["result"])
                finally:
                    case.doCleanups()

    def test_local_game_overshoot_stays_observable_and_closes_without_global_renewal(self):
        root, _, _, operation = self.pending(limits=dict(primitives=8, wall_seconds=120, game_seconds=1), advance=2)
        self.assertEqual(operation["result"]["macro_exhausted"], "game_seconds")
        self.assertEqual(self.runtime.status()["phase"], "active")
        original_root = self.runtime._ledger.request(root["request_id"])
        observed = self.observe()
        self.assertEqual(observed["state"], "completed", observed)
        self.assertEqual(observed["result"]["macro_closure"]["limit"], "game_seconds")
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["phase"], "active")
        self.assertEqual(self.runtime.status()["metrics"]["game_seconds"], 2)
        self.assertEqual(self.runtime._ledger.request(root["request_id"]), original_root)

    def test_mission_game_exhaustion_stops_instead_of_creating_read_only_continuation(self):
        self.a = replace(self.a, limits=replace(self.a.limits, game_seconds=2))
        _, _, _, operation = self.pending(new_root=True, advance=2, expect_pending=False)
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._prompt_phase)
        primitive, = self.runtime._ledger.primitive_records()
        self.assertEqual(primitive["state"], "returned")
        self.assertIsNotNone(primitive["result"]["native_ack"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

    def test_local_normal_return_ends_root_without_revoking_mission_for_direct_semantic_and_navigation(self):
        for kind in ("direct", "interact", "navigate"):
            with self.subTest(kind=kind):
                case = type(self)()
                case.setUp()
                try:
                    case.allow_direct()
                    case.bridge.value["actions"].append("open")
                    case.start()

                    def elapsed(bridge, request):
                        if request["kind"] in ("action", "direct"):
                            bridge.value["scene"]["turn"] += 2
                        return True

                    case.bridge.behavior = elapsed
                    if kind == "navigate":
                        request = fixtures.core.MissionRuntimeTests.navigation(case)
                    else:
                        goal = (dict(input=dict(type="key", key="x", modifiers=[]), intent="Try input",
                                     expected="Inspect actual effect", interrupt_allowed=False) if kind == "direct" else
                                dict(action="open", intent="Open here", desired_outcome="Inspect actual effect"))
                        request = case.control(kind, goal)
                    request["limits"]["game_seconds"] = 1
                    case.runtime.command(request)
                    operation = case.settled(request["request_id"])
                    self.assertEqual(operation["state"], "partial", operation)
                    self.assertEqual(operation["result"]["macro_exhausted"], "game_seconds")
                    self.assertEqual(case.runtime.status()["phase"], "active")
                    self.assertIsNotNone(case.runtime._lease)
                    self.assertIsNone(case.runtime._prompt_phase)
                    self.assertEqual(case.runtime.status()["metrics"]["game_seconds"], 2)
                    self.assertEqual(case.runtime._ledger.request(request["request_id"])["request"], request)
                    self.assertEqual(case.runtime._ledger.primitive_records()[-1]["state"], "returned")
                    next_choice = case.control("direct", dict(input=dict(type="key", key="x", modifiers=[]),
                        intent="New root chosen from current evidence", expected="Inspect actual result",
                        interrupt_allowed=False), request_id="next-root")
                    case.runtime.command(next_choice)
                    self.assertEqual(case.settled("next-root")["state"], "partial")
                    self.assertEqual(case.runtime.status()["metrics"]["game_seconds"], 4)
                    self.assertEqual(case.runtime.status()["spent_inputs"], 2)
                finally:
                    case.doCleanups()

    def test_exact_global_cap_wins_simultaneous_local_game_overshoot_in_all_input_lanes(self):
        for kind in ("direct", "interact", "navigate"):
            with self.subTest(kind=kind):
                case = type(self)()
                case.setUp()
                try:
                    case.a = replace(case.a, limits=replace(case.a.limits, game_seconds=2))
                    case.allow_direct()
                    case.bridge.value["actions"].append("open")
                    case.start()

                    def elapsed(bridge, request):
                        if request["kind"] in ("action", "direct"):
                            bridge.value["scene"]["turn"] += 2
                        return True

                    case.bridge.behavior = elapsed
                    if kind == "navigate":
                        request = fixtures.core.MissionRuntimeTests.navigation(case)
                    else:
                        goal = (dict(input=dict(type="key", key="x", modifiers=[]), intent="Try input",
                                     expected="Inspect actual effect", interrupt_allowed=False) if kind == "direct" else
                                dict(action="open", intent="Open here", desired_outcome="Inspect actual effect"))
                        request = case.control(kind, goal)
                    request["limits"]["game_seconds"] = 1
                    case.runtime.command(request)
                    operation = case.settled(request["request_id"])
                    self.assertEqual(operation["state"], "partial", operation)
                    self.assertNotIn("macro_exhausted", operation["result"])
                    self.assertEqual(case.runtime.status()["phase"], "paused")
                    self.assertIsNone(case.runtime._lease)
                    self.assertIsNone(case.runtime._prompt_phase)
                    self.assertEqual(case.runtime.status()["metrics"]["game_seconds"], 2)
                    self.assertEqual(case.runtime._ledger.primitive_records()[-1]["state"], "returned")
                    self.assertEqual(case.runtime.status()["spent_inputs"], 1)
                finally:
                    case.doCleanups()

    def test_storage_failure_during_fresh_observe_still_stops_after_preserving_known_ack(self):
        self.pending()
        receipt = self.runtime._ledger.primitive_records()[-1]
        with patch.object(self.runtime._store, "ingest", side_effect=OSError("fresh capture storage failed")):
            observed = self.observe()
        self.assertEqual(observed["state"], "blocked", observed)
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(self.runtime._ledger.primitive_records()[-1], receipt)


if __name__ == "__main__":
    unittest.main()
