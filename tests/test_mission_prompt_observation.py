"""Explicit reconsideration through real mission/controller/store components.

The file bridge and visible bytes remain synthetic CDDA-adapter fixtures. These
tests qualify source behavior, not native graphics or another game's binding.
"""
import copy
from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from harness.gameplay.evidence import EvidenceError
from tests import test_mission_runtime as core
from tests import test_mission_items as items


class PromptObservationTests(unittest.TestCase):
    setUp = core.MissionRuntimeTests.setUp
    wait = core.MissionRuntimeTests.wait
    request = core.MissionRuntimeTests.request
    result = core.MissionRuntimeTests.result
    settled = core.MissionRuntimeTests.settled
    start = core.MissionRuntimeTests.start
    control = core.MissionRuntimeTests.control
    open_direction = core.MissionRuntimeTests.open_direction
    open_items = items.MissionItemTests.open_items
    inventory = items.MissionItemTests.inventory
    editor = items.MissionItemTests.editor
    select = items.MissionItemTests.select
    edit = items.MissionItemTests.edit
    send = items.MissionItemTests.send

    def allow_direct(self):
        self.a = replace(self.a, allowed_skills=(*self.a.allowed_skills, "direct"))

    def direct(self, root, request_id="new-player-choice", key="ESC"):
        return self.control("direct", dict(input=dict(type="key", key=key, modifiers=[]),
            intent="Try the chosen ordinary input on this observed screen",
            expected="Inspect the actual return without certifying the root goal",
            interrupt_allowed=False), phase_id=root["request_id"], request_id=request_id)

    def observe(self, request_id="explicit-look"):
        request = self.request("observe", request_id=request_id)
        self.assertEqual(self.runtime.command(request)["status"], "accepted")
        return self.settled(request_id)

    def changed(self, variant="category"):
        self.bridge.editor_text = "Different labels and layout, no known menu handler"
        if variant != "pixels":
            self.bridge.value["revision"] += 1
            self.bridge.value.update(category="UNFAMILIAR_SCREEN_731", actions=["UNFAMILIAR_ACTION"])
            self.bridge.value["boundary"]["id"] = "changed-layout-731"

    def open_cancelable(self):
        self.allow_direct()
        def effect(bridge, request):
            if request["kind"] == "direct" and request["input"]["key"] == "ESC":
                bridge.editor_text = None
                bridge.value.update(scene=self.runtime._store.observation(self.runtime._prompt_phase.game_anchor)["scene"],
                    ui=None, category="DEFAULTMODE", actions=["open"])
                bridge.value["boundary"].update(kind="normal_play", id="ordinary-return")
            return True
        return self.open_direction(effect=effect)

    def assert_stopped(self, operation, charged=1):
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertIsNone(self.controller._mission_lease)
        self.assertFalse(self.runtime._bindings)
        self.assertEqual(self.runtime.status()["spent_inputs"], charged)

    def test_changed_pixels_and_unfamiliar_category_allow_new_source_choice(self):
        for variant in ("pixels", "category"):
            with self.subTest(variant=variant):
                case = type(self)()
                case.setUp()
                try:
                    root, original_result = case.open_cancelable()
                    phase = case.runtime._prompt_phase
                    original_root = case.runtime._ledger.request(root["request_id"])
                    lease = case.runtime._lease
                    charges = case.runtime._ledger.primitive_records()
                    case.changed(variant)
                    observed = case.observe()
                    self.assertEqual(observed["state"], "completed", observed)
                    self.assertNotIn("revalidation", observed["result"])
                    self.assertNotIn("phase", observed["result"])
                    current = case.runtime._prompt_phase
                    self.assertEqual(replace(current, checkpoint=phase.checkpoint), phase)
                    self.assertIs(case.runtime._lease, lease)
                    self.assertEqual(case.runtime._ledger.primitive_records(), charges)
                    self.assertEqual(case.runtime._ledger.request(root["request_id"]), original_root)
                    self.assertEqual(case.result(root["request_id"]), original_result)
                    transition = observed["result"]["observation"]
                    self.assertEqual(transition, dict(root_id=phase.root_id, before=phase.checkpoint.observation_id,
                        after=current.checkpoint.observation_id, grants_authority=False))
                    self.assertIn(current.checkpoint.observation_id, case.runtime._bindings)
                    records = [json.loads(line) for line in case.controller.journal.read_text().splitlines()]
                    events = [r["outcome"] for r in records if r["request"]["kind"] == "mission_prompt_observation"]
                    self.assertEqual(events[-1], transition)
                    escaped = case.send(case.direct(root))
                    self.assertEqual(escaped["state"], "partial", escaped)
                    self.assertEqual(escaped["result"]["phase"]["stage"], "complete")
                    self.assertTrue(escaped["result"]["verification_required"])
                    self.assertEqual(escaped["result"]["basis"], "ordinary_input")
                    self.assertIsNone(case.runtime._prompt_phase)
                    self.assertEqual(case.runtime.status()["spent_inputs"], 2)
                    self.assertEqual(case.result(root["request_id"]), original_result)
                    self.assertEqual(case.bridge.delivered[-1]["input"]["key"], "ESC")
                finally:
                    case.doCleanups()

    def test_old_source_request_stops_without_dispatch_after_new_observation(self):
        root, _ = self.open_cancelable()
        old_choice = self.direct(root, "old-source-choice")
        self.changed()
        self.assertEqual(self.observe()["state"], "completed")
        before = copy.deepcopy(self.bridge.delivered)
        self.assert_stopped(self.send(old_choice))
        self.assertEqual(self.bridge.delivered, before)
        replay = self.runtime.command(old_choice)
        self.assertEqual(replay["operation"], self.result(old_choice["request_id"]))

    def test_ordinary_key_keeps_physical_choice_and_lineage_across_changed_entry(self):
        root, _ = self.open_cancelable()
        choice = self.direct(root)
        original_root = self.runtime._ledger.request(root["request_id"])
        self.changed()
        result = self.send(choice)
        self.assertEqual(result["state"], "partial", result)
        self.assertIsNone(result["result"]["revalidation"])
        relation = result["result"]["input_observation"]
        self.assertEqual(relation["original"]["source_id"], choice["sources"][0])
        self.assertNotEqual(relation["original"]["source_id"], relation["current"]["source_id"])
        primitive = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual(primitive["state"], "returned")
        self.assertEqual(primitive["intent"]["source_before"], relation["current"]["source_id"])
        self.assertEqual(primitive["intent"]["input_observation"], relation)
        self.assertNotEqual(primitive["intent"]["preflight_source"], primitive["intent"]["source_before"])
        native = self.bridge.delivered[-1]
        self.assertEqual(native["input"], choice["goal"]["input"])
        self.assertFalse(native["require_exact_frame"])
        self.assertEqual(native["revision"], primitive["intent"]["expected_revision"])
        self.assertEqual(native["boundary_id"], primitive["intent"]["expected_boundary_id"])
        self.assertEqual(self.runtime._ledger.request(root["request_id"]), original_root)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)

    def test_semantic_interpretation_still_requires_its_exact_image_refresh(self):
        root, _ = self.open_cancelable()
        source = self.runtime.status()["current_source"]["observation_id"]
        choice = self.control("menu", dict(purpose="Open nearby door", label="East", outcome="activated"),
            phase_id=root["request_id"], perception=dict(kind="direction", basis="player_interpretation",
                source_id=source, question="Open which nearby door?"))
        self.changed("pixels")
        delivered = copy.deepcopy(self.bridge.delivered)
        self.assert_stopped(self.send(choice))
        self.assertEqual(self.bridge.delivered, delivered)

    def test_old_age_and_already_visible_drift_do_not_prevent_explicit_look(self):
        self.open_direction()
        old = self.runtime._current
        self.changed()
        with self.controller.data_lock:
            self.controller.state.update(category="UNFAMILIAR_SCREEN_731", actions=["UNFAMILIAR_ACTION"])
            self.controller.state["revision"] = self.bridge.value["revision"]
            self.controller.state["boundary"]["id"] = "changed-layout-731"
        original = self.runtime._store._fresh
        def aged(entry, now_monotonic, now_timestamp_ms):
            if entry.reference == old:
                raise EvidenceError("Old evidence is aged, retained and intact")
            return original(entry, now_monotonic, now_timestamp_ms)
        with patch.object(self.runtime._store, "_fresh", side_effect=aged):
            self.assertEqual(self.observe()["state"], "completed")
        self.assertEqual(self.runtime._prompt_phase.root_id, "open-direction")

    def test_unchanged_quantity_proof_survives_but_changed_editor_clears_it(self):
        self.allow_direct()
        self.open_items()
        self.assertEqual(self.send(self.select())["state"], "partial")
        self.assertTrue(self.runtime._prompt_phase.quantity_editor)
        unchanged = self.observe("unchanged-editor")
        self.assertEqual(unchanged["result"]["revalidation"]["rule"], "exact_png_bytes")
        self.assertTrue(self.runtime._prompt_phase.quantity_editor)
        self.bridge.editor_text = "4"
        self.bridge.value["revision"] += 1
        self.assertEqual(self.observe()["state"], "completed")
        self.assertFalse(self.runtime._prompt_phase.quantity_editor)
        phase = self.runtime._prompt_phase
        charged = self.runtime.status()["spent_inputs"]
        before = copy.deepcopy(self.bridge.delivered)
        rejected = self.send(self.edit())
        self.assertEqual(rejected["state"], "blocked", rejected)
        self.assertIn("MARK_WITH_COUNT", rejected["result"]["reason"])
        self.assertEqual(self.bridge.delivered, before)
        self.assertIs(self.runtime._prompt_phase, phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], charged)
        explored = self.send(self.direct(self.root, key="x"))
        self.assertEqual(explored["state"], "partial", explored)
        self.assertFalse(self.runtime._prompt_phase.quantity_editor)
        self.assertEqual(self.runtime.status()["spent_inputs"], charged + 1)

    def test_prepared_published_unknown_effects_stop_but_resolved_history_is_allowed(self):
        for state, effect in (("prepared", None), ("published", None), ("unknown", None),
                              ("unknown", {"retained_resolution_fixture": True})):
            with self.subTest(state=state, effect=effect):
                case = type(self)()
                case.setUp()
                try:
                    case.open_direction()
                    original = case.runtime._ledger.primitive_records()
                    # Inject only a historical classification, not a legal
                    # effect proof. Exercise the real SQLite summary queries;
                    # proof validation has separate ledger tests. Controller,
                    # source and observation components use the synthetic bridge.
                    with case.runtime._ledger._mutex:
                        case.runtime._ledger._db.execute(
                            "UPDATE primitives SET state=?,effect=? WHERE id=?",
                            (state, None if effect is None else json.dumps(effect), original[0]["logical_id"]))
                        case.runtime._ledger._db.commit()
                    self.assertEqual(case.runtime._ledger.snapshot(now=case.runtime._wall())["unreconciled"],
                        int(state == "unknown" and effect is None))
                    self.assertEqual(case.runtime._ledger.measured_counts()["primitives"]["by_state"][state], 1)
                    observed = case.observe()
                    if effect is None:
                        case.assert_stopped(observed)
                    else:
                        self.assertEqual(observed["state"], "completed", observed)
                        self.assertIsNotNone(case.runtime._prompt_phase)
                finally:
                    case.doCleanups()

    def test_capture_authority_health_and_revision_faults_do_not_adopt(self):
        faults = ("session-menu", "session-normal", "takeover", "control-generation", "human-pause-origin",
                  "fault-pause-origin", "paused", "error", "missing-frame", "regression", "contradiction")
        for fault in faults:
            with self.subTest(fault=fault):
                case = type(self)()
                case.setUp()
                try:
                    case.open_direction()
                    old = case.runtime._prompt_phase
                    def capture_fault(bridge, request):
                        if request["kind"] != "observe":
                            return
                        if fault.startswith("session"):
                            bridge.value["session"] = "other-session"
                            if fault == "session-normal":
                                bridge.value["scene"] = case.runtime._store.observation(old.game_anchor)["scene"]
                                bridge.value["boundary"]["kind"] = "normal_play"
                        elif fault == "takeover":
                            bridge.value["takeover_generation"] += 1
                        elif fault == "control-generation":
                            bridge.value["boundary"]["control_generation"] += 1
                        elif fault.endswith("pause-origin"):
                            bridge.value["pause_origin"] = "human" if fault.startswith("human") else "fault"
                            # Preserve this origin through VisibleBridge.publish.
                            bridge.value["paused"] = True
                        elif fault == "paused":
                            bridge.value["paused"] = True
                        elif fault == "error":
                            bridge.value["error"] = "Capture failure"
                        elif fault == "missing-frame":
                            bridge.value.update(frame_ok=False, frame_geometry=None)
                        elif fault == "regression":
                            bridge.value["revision"] -= 1
                        elif fault == "contradiction":
                            bridge.value["actions"] = ["changed-at-same-revision"]
                    case.bridge.before_gate = capture_fault
                    case.assert_stopped(case.observe())
                    self.assertEqual(case.runtime._current, old.checkpoint)
                    self.assertEqual(len(case.bridge.delivered), 2)  # initial Resume + root input
                finally:
                    case.doCleanups()

    def test_pre_capture_original_authority_integrity_and_capacity_faults_stop(self):
        faults = ("boot", "operator", "pause-generation", "actor", "epoch", "lease", "pending", "control-pending",
                  "binding", "store-generation", "corrupt", "missing", "disputed", "observe-deadline",
                  "mission-deadline", "mission-inputs", "game-cap", "frames", "bytes")
        for fault in faults:
            with self.subTest(fault=fault):
                case = type(self)()
                case.setUp()
                try:
                    case.open_direction(limits=dict(primitives=8,
                        wall_seconds=120, game_seconds=1200))
                    phase = case.runtime._prompt_phase
                    before = len(case.bridge.requests)
                    original_guard = case.runtime._prompt_observation_guard
                    def inject(work, owned, reference=None):
                        if reference is None:
                            if fault == "boot":
                                case.controller.authority["controller_boot_id"] = "different-boot"
                            elif fault == "operator":
                                case.controller.operator_pause_generation += 1
                            elif fault == "pause-generation":
                                case.controller.pause_generation += 1
                            elif fault == "actor":
                                case.runtime._prompt_phase = replace(owned, actor_id="different-actor")
                            elif fault == "epoch":
                                case.runtime._prompt_phase = replace(owned, epoch=owned.epoch + 1)
                            elif fault == "lease":
                                case.controller._mission_lease = None
                            elif fault == "pending":
                                case.controller.pending = {"fixture": True}
                            elif fault == "control-pending":
                                case.controller.control_pending = {"fixture": True}
                            elif fault == "binding":
                                case.runtime._bindings.clear()
                            elif fault == "store-generation":
                                case.runtime._store._authority_generation += 1
                            elif fault == "corrupt":
                                Path(owned.checkpoint.frame_path).write_bytes(b"corrupt")
                            elif fault == "missing":
                                Path(owned.checkpoint.frame_path).unlink()
                            elif fault == "disputed":
                                case.runtime._store._disputed.append(owned.checkpoint.observation_id)
                            elif fault.endswith("deadline"):
                                operation = case.runtime._ledger.request(work.request["request_id"])
                                limit = operation["deadline"] if fault != "mission-deadline" else (
                                    case.runtime._mission_deadline - case.a.cleanup_reserve.wall_seconds)
                                case.runtime._wall = lambda: limit
                            elif fault in ("mission-inputs", "game-cap"):
                                limits = case.runtime._admission.limits
                                changes = {"inputs": case.runtime.status()["spent_inputs"] + case.a.cleanup_reserve.inputs}
                                if fault == "game-cap":
                                    changes = {}
                                    case.runtime._game_cost = limits.game_seconds
                                if changes:
                                    case.runtime._admission = replace(case.runtime._admission, limits=replace(limits, **changes))
                            elif fault in ("frames", "bytes"):
                                usage = case.runtime._store.usage()
                                usage["frames" if fault == "frames" else "bytes"] = (
                                    case.a.limits.frames if fault == "frames" else case.a.limits.frame_bytes)
                                case.runtime._store.usage = lambda: usage
                        return original_guard(work, owned, reference)
                    with patch.object(case.runtime, "_prompt_observation_guard", side_effect=inject):
                        case.assert_stopped(case.observe())
                    self.assertEqual(len(case.bridge.requests), before)
                    self.assertEqual(case.runtime._current, phase.checkpoint)
                finally:
                    case.controller.pending = None
                    case.controller.control_pending = None
                    case.doCleanups()

    def test_pause_between_capture_and_publication_prevents_checkpoint_adoption(self):
        self.open_direction()
        phase = self.runtime._prompt_phase
        original = self.runtime._ingest
        def pause_after_capture(*args, **kwargs):
            reference = original(*args, **kwargs)
            self.controller.operator_pause_generation += 1
            return reference
        with patch.object(self.runtime, "_ingest", side_effect=pause_after_capture):
            self.assert_stopped(self.observe())
        self.assertNotEqual(self.runtime._current, phase.checkpoint)
        records = [json.loads(line) for line in self.controller.journal.read_text().splitlines()]
        self.assertFalse([r for r in records if r["request"]["kind"] == "mission_prompt_observation"])

    def test_original_deadline_and_capacity_are_rechecked_after_capture(self):
        for fault in ("root-deadline", "observe-deadline", "capacity", "control-pending"):
            with self.subTest(fault=fault):
                case = type(self)()
                case.setUp()
                try:
                    case.open_direction()
                    before = case.runtime._prompt_phase
                    original = case.runtime._observe_native
                    def capture_then_fault(work, **kwargs):
                        captured = original(work, **kwargs)
                        if fault.endswith("deadline"):
                            operation = case.runtime._ledger.request(before.root_id if fault == "root-deadline"
                                else work.request["request_id"])
                            case.runtime._wall = lambda: operation["deadline"]
                        elif fault == "capacity":
                            usage = case.runtime._store.usage()
                            usage["frames"] = case.a.limits.frames
                            case.runtime._store.usage = lambda: usage
                        else:
                            case.controller.control_pending = {"fixture": True}
                        return captured
                    with patch.object(case.runtime, "_observe_native", side_effect=capture_then_fault):
                        case.assert_stopped(case.observe())
                    self.assertEqual(case.runtime._ledger.request(before.root_id)["deadline"],
                                     case.result(before.root_id)["deadline"])
                    records = [json.loads(line) for line in case.controller.journal.read_text().splitlines()]
                    self.assertFalse([r for r in records if r["request"]["kind"] == "mission_prompt_observation"])
                finally:
                    case.controller.control_pending = None
                    case.doCleanups()


if __name__ == "__main__":
    unittest.main()
