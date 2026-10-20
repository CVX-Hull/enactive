"""Core integration with synthetic transport and an explicit trusted admission fixture.

Core dispatch tests isolate the owned-identity boundary, not its implementation.
Unmodified production admission is tested separately; no native gameplay claim.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import copy
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from harness.controller import Controller
from harness.gameplay.evidence import CapacityError
from harness.gameplay.mission_contracts import CleanupReserve, MissionLimits, canonical
from harness.gameplay.mission_ledger import MissionLedger
from tests.test_mission_ledger import intent
from harness.mission_runtime import MissionRuntime
from tests.test_controller import FakeBridge
from tests.test_mission_contracts import admission, claim


def bootstrap_core_fixture(runtime, work):
    """Assume already-proven identity only for temporary fake-bridge core tests.

    This replaces no production gate or native failure: ordinary Start must not
    call this path. Registered lifecycle needs separate real and synthetic checks.
    """
    state, received = runtime._observe_native(work)
    # Explicitly assume the same missing durable identity boundary here only.
    # Production has no flag, restored-handle shortcut or automatic adoption.
    runtime._require_normal_adoption = runtime._store.verify
    ledger = runtime._ledger.snapshot(now=runtime._wall())
    runtime._lease = runtime.controller.acquire_mission(runtime._admission.mission_id,
        ledger["epoch"], ledger["player_id"], operation="interaction", expected_session=state["session"],
        expected_revision=state["revision"], expected_boundary_id=state["boundary"]["id"])
    runtime._ledger.activate(epoch=ledger["epoch"], player_id=ledger["player_id"], now=runtime._wall())
    reference = runtime._ingest(state, received)
    runtime._publish_source(reference, authoritative=True)
    runtime._capture_memory(reference)
    return dict(admitted=True, lifecycle_needed=False, fixture_only=True,
                source_ids=[reference.observation_id], grants_authority=False)


class VisibleBridge(FakeBridge):
    def __init__(self, controller, **options):
        super().__init__(controller, **options)
        self.frames = 0
        self.editor_text = None
        self.value.update(pause_origin="startup")
        self.value["scene"]["provenance"] = "player-visible input boundary"
        self.value["scene"]["neighbors"] = [
            {"dx": dx, "dy": dy, "visible": True, "terrain": "t_floor",
             "name": "floor", "furniture": "f_null"}
            for dy in range(-1, 2) for dx in range(-1, 2) if (dx, dy) != (0, 0)]

    def publish(self, value):
        self.frames += 1
        value = copy.deepcopy(value)
        value["frame"] = f'frame-{value["session"]}-{self.frames}.png'
        if not value["paused"]:
            value["pause_origin"] = "none"
        # A synthetic visible-state marker, never a native or rendered PNG claim.
        content = {key: value[key] for key in ("scene", "ui", "category", "actions")}
        content["visible_editor"] = self.editor_text
        (self.bridge / value["frame"]).write_bytes(b"\x89PNG\r\n\x1a\n" + canonical(content).encode())
        super().publish(value)


class MissionRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.controller = Controller(Path(temporary.name), timeout=0.8)
        self.addCleanup(self.controller.close)
        self.bridge = VisibleBridge(self.controller)
        self.bridge.__enter__()
        self.addCleanup(self.bridge.__exit__, None, None, None)
        self.runtime = MissionRuntime(self.controller)
        self.addCleanup(lambda: self.runtime.close())
        self.a = admission()
        self._prepared_native = False

    def wait(self, condition, timeout=4):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            value = condition()
            if value:
                return value
            threading.Event().wait(0.005)
        self.fail(f"Timed out; status={self.runtime.status()}")

    def request(self, kind, **changes):
        data = dict(schema="mission/2", kind=kind, request_id=kind + "-1",
                    mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"])
        if kind == "skill":
            data.update(work_id=None, phase_id=None, perception=None)
        elif kind == "lifecycle":
            data.update(work_id=None, phase_id=None, identity_claim_ids=[])
        data.update(changes)
        return data

    def result(self, identity):
        out = self.runtime.command(dict(schema="mission/2", kind="result",
            mission_id=self.a.mission_id, operation_id=identity))
        self.assertEqual(out["status"], "accepted", out)
        return out["operation"]

    def settled(self, identity):
        return self.wait(lambda: (op if (op := self.result(identity))["result"] is not None else None))

    def start(self):
        if not self._prepared_native:
            self.assertEqual(self.controller.execute("observe")["status"], "ready")
            self.assertEqual(self.controller.execute("resume")["status"], "ready")
            self._prepared_native = True
        req = dict(schema="mission/2", kind="start", request_id="start-1", admission=self.a.to_dict())
        with patch.object(self.runtime, "_bootstrap", side_effect=lambda work: bootstrap_core_fixture(self.runtime, work)):
            response = self.runtime.command(req)
            self.assertEqual(response["status"], "accepted", response)
            self.settled("start-1")
        return self.runtime.status()

    def navigation(self, target=(1, 0, 0), **changes):
        status = self.runtime.status()
        ref = status["current_source"]
        data = self.request("skill", skill_kind="navigate", goal={"scope": {
            "mission_id": self.a.mission_id, "session": ref["session"], "coordinate_epoch": 0},
            "target": list(target)}, sources=[ref["observation_id"]],
            expected_session=ref["session"], expected_revision=ref["revision"],
            expected_boundary_id=self.runtime._store.observation(self.runtime._current)["boundary"]["id"],
            limits={"primitives": 8, "wall_seconds": 120, "game_seconds": 1200})
        data.update(changes)
        return data

    def control(self, kind, goal, *, phase_id=None, perception=None, request_id="control-1", **changes):
        reference = self.runtime.status()["current_source"]
        data = self.request("skill", request_id=request_id, skill_kind=kind, goal=goal,
            phase_id=phase_id, perception=perception, sources=[reference["observation_id"]],
            expected_session=reference["session"], expected_revision=reference["revision"],
            expected_boundary_id=self.runtime._store.observation(self.runtime._current)["boundary"]["id"],
            limits={"primitives": 8, "wall_seconds": 120, "game_seconds": 1200})
        data.update(changes)
        return data

    def open_direction(self, *, prompt=None, effect=None, **changes):
        self.bridge.value["actions"].append("open")
        self.start()
        normal = copy.deepcopy(self.bridge.value["scene"])
        def direction_query(bridge, request):
            if request.get("action") == "open":
                bridge.value.update(scene=None, ui=None, category="DEFAULTMODE",
                    actions=["UP", "DOWN", "LEFT", "RIGHT", "pause", "QUIT"])
                bridge.value["boundary"].update(kind="menu", id="direction-query")
                if prompt is not None:
                    bridge.value.update(copy.deepcopy(prompt))
            elif effect is not None:
                return effect(bridge, request)
            elif request.get("action") == "pause":
                bridge.value.update(scene=normal, ui=None, category="DEFAULTMODE", actions=["UP", "DOWN", "LEFT", "RIGHT", "open"])
                bridge.value["boundary"].update(kind="normal_play", id="returned-normal")
            return True
        self.bridge.behavior = direction_query
        root = self.control("interact", dict(action="open", intent="Open here", desired_outcome="Inspect actual result"),
                            request_id="open-direction", **changes)
        self.assertEqual(self.runtime.command(root)["status"], "accepted")
        operation = self.settled(root["request_id"])
        self.assertEqual(operation["state"], "partial", operation)
        return root, operation

    def test_interaction_direction_and_normal_return_share_root_without_position_invention(self):
        root, opened = self.open_direction(limits=dict(primitives=2, wall_seconds=120, game_seconds=1200))
        self.assertEqual(opened["result"]["phase"]["stage"], "awaiting_control")
        source = self.runtime.status()["current_source"]
        view = dict(kind="direction", basis="player_interpretation", source_id=source["observation_id"], question="Where?")
        child = self.control("menu", dict(purpose="Open direction", label="Here", outcome="activated"),
                             phase_id=root["request_id"], perception=view)
        self.assertEqual(self.runtime.command(child)["status"], "accepted")
        operation = self.settled(child["request_id"])
        self.assertEqual(operation["state"], "partial", operation)
        self.assertEqual(operation["result"]["phase"]["stage"], "complete")
        self.assertTrue(operation["result"]["verification_required"])
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertEqual([r["action"] for r in self.bridge.delivered if r["kind"] == "action"], ["open", "pause"])
        self.assertTrue([r for r in self.bridge.delivered if r.get("action") == "pause"][0]["require_exact_frame"])
        records = self.runtime._ledger.primitive_records()
        self.assertEqual([r["state"] for r in records], ["returned", "returned"])

    def test_contradictory_image_fence_receipt_stays_unknown_despite_actual_return(self):
        root, _ = self.open_direction()
        ref = self.runtime.status()["current_source"]
        child = self.control("menu", dict(purpose="Direction", label="Here", outcome="activated"),
            phase_id=root["request_id"], perception=dict(kind="direction", basis="player_interpretation",
            source_id=ref["observation_id"], question="Where?"))
        real = self.controller.execute_mission
        def contradict(*args, **kwargs):
            receipt = real(*args, **kwargs)
            self.assertTrue(receipt["published"])
            receipt["request"]["require_exact_frame"] = False
            receipt["preflight"]["expected_image_sha256"] = None
            return receipt
        with patch.object(self.controller, "execute_mission", contradict):
            self.runtime.command(child)
            operation = self.settled(child["request_id"])
        self.assertEqual(operation["state"], "unknown", operation)
        self.assertIn("image policy", operation["result"]["reason"])
        self.assertIsNotNone(operation["result"]["pending_logical_id"])
        self.assertEqual([r["state"] for r in self.runtime._ledger.primitive_records()], ["returned", "unknown"])
        self.assertIsNone(self.runtime._prompt_phase)

    def test_equivalent_observe_refreshes_owned_prompt_without_renewing_root(self):
        root, _ = self.open_direction()
        original = self.runtime._prompt_phase
        deadline = self.runtime._ledger.request(root["request_id"])["deadline"]
        self.runtime.command(self.request("observe"))
        observed = self.settled("observe-1")
        self.assertEqual(observed["state"], "completed", observed)
        self.assertEqual(observed["result"]["revalidation"]["rule"], "exact_png_bytes")
        current = self.runtime._prompt_phase
        self.assertEqual(current.game_anchor, original.game_anchor)
        self.assertNotEqual(current.checkpoint, original.checkpoint)
        self.assertEqual(self.runtime._ledger.request(root["request_id"])["deadline"], deadline)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

    def test_owned_prompt_blocks_unrelated_root_and_user_pause_clears_it(self):
        self.open_direction()
        request = self.control("interact", dict(action="open", intent="Unrelated", desired_outcome="Other"))
        self.assertEqual(self.runtime.command(request)["status"], "rejected")
        self.assertIsNotNone(self.runtime._prompt_phase)
        self.runtime.pause()
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertIsNone(self.controller._mission_lease)

    def test_prompt_dismissal_is_one_accounted_input_with_partial_effect_verification(self):
        normal = copy.deepcopy(self.bridge.value["scene"])
        def dismiss(bridge, request):
            if request.get("action") == "TEXT.QUIT":
                bridge.value.update(scene=normal, ui=None, category="DEFAULTMODE", actions=["UP", "DOWN", "LEFT", "RIGHT"])
                bridge.value["boundary"].update(kind="normal_play", id="editor-cancel-return")
            return True
        root, _ = self.open_direction(prompt=dict(category="STRING_INPUT", actions=["TEXT.QUIT"]), effect=dismiss)
        child = self.control("menu", dict(purpose="Cancel filter editor", label="Cancel", outcome="dismissed"),
            phase_id=root["request_id"], perception=dict(kind="dismissal", basis="player_interpretation",
            source_id=self.runtime.status()["current_source"]["observation_id"], question="Filter"))
        self.runtime.command(child)
        operation = self.settled(child["request_id"])
        self.assertEqual(operation["state"], "partial", operation)
        self.assertTrue(operation["result"]["verification_required"])
        self.assertEqual(operation["result"]["phase"]["stage"], "complete")
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertEqual([r.get("action") for r in self.bridge.delivered if r["kind"] == "action"], ["open", "TEXT.QUIT"])

    def native_choices(self, *, effect=None, **changes):
        ui = dict(purpose="uilist", title="Choices", rows=[
            dict(id=f"row-{n}", text=text, enabled=True, hotkey=None)
            for n, text in enumerate(("One", "Two", "Three"))],
            selected="row-0", filter=None, count=None, coverage="rendered_rows_only")
        def focus(bridge, request):
            if request.get("action") == "UILIST.DOWN":
                ui = bridge.value["ui"]
                ui["selected"] = f'row-{int(ui["selected"].split("-")[1]) + 1}'
                bridge.value["boundary"]["id"] = f'choice-{bridge.value["revision"]}'
            return True
        return self.open_direction(prompt=dict(ui=ui, category="UILIST",
            actions=["UILIST.UP", "UILIST.DOWN", "CONFIRM", "QUIT"]),
            effect=focus if effect is None else effect, **changes)

    def test_native_menu_batches_focus_without_activation_and_keeps_owned_phase(self):
        root, _ = self.native_choices(limits=dict(primitives=3, wall_seconds=120, game_seconds=1200))
        child = self.control("menu", dict(purpose="Choose", label="Three", outcome="focused"),
                             phase_id=root["request_id"])
        self.runtime.command(child)
        operation = self.settled(child["request_id"])
        self.assertEqual(operation["state"], "completed", operation)
        self.assertEqual(operation["result"]["verified_focus_steps"], 2)
        self.assertEqual(operation["result"]["phase"]["stage"], "awaiting_control")
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)
        self.assertEqual(self.bridge.value["ui"]["selected"], "row-2")
        self.assertNotIn("CONFIRM", [r.get("action") for r in self.bridge.delivered])

    def test_returned_native_focus_mismatch_is_policy_unknown_and_revokes_once(self):
        root, _ = self.native_choices(effect=lambda bridge, request: True)
        epoch = self.runtime.status()["epoch"]
        child = self.control("menu", dict(purpose="Choose", label="Two", outcome="focused"),
                             phase_id=root["request_id"])
        self.runtime.command(child)
        operation = self.settled(child["request_id"])
        self.assertEqual(operation["state"], "unknown", operation)
        self.assertEqual(self.runtime.status()["epoch"], epoch + 1)
        self.assertIsNotNone(operation["result"]["pending_logical_id"])
        self.assertEqual(operation["result"]["phase"]["stage"], "unknown")
        self.assertEqual([r["state"] for r in self.runtime._ledger.primitive_records()], ["returned", "returned"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertIsNone(self.controller._mission_lease)
        self.assertIsNone(self.runtime._prompt_phase)

    def test_native_takeover_after_menu_input_keeps_pending_unknown_policy_receipt(self):
        def takeover(bridge, request):
            if request.get("action") == "UILIST.DOWN":
                bridge.value.update(paused=True, pause_origin="human", takeover_generation=1)
                bridge.value["boundary"]["control_generation"] += 1
            return True
        root, _ = self.native_choices(effect=takeover)
        child = self.control("menu", dict(purpose="Choose", label="Two", outcome="focused"),
                             phase_id=root["request_id"])
        self.runtime.command(child)
        operation = self.settled(child["request_id"])
        self.assertEqual(operation["state"], "unknown", operation)
        self.assertIsNotNone(operation["result"]["pending_logical_id"])
        self.assertEqual(self.runtime.status()["pause_cause"], "takeover")
        self.assertEqual([r["state"] for r in self.runtime._ledger.primitive_records()], ["returned", "returned"])
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertIsNone(self.controller._mission_lease)

    def test_changed_image_observe_cannot_refresh_owned_prompt(self):
        self.open_direction()
        self.bridge.value["actions"].remove("RIGHT")
        self.runtime.command(self.request("observe"))
        operation = self.settled("observe-1")
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertIsNone(self.controller._mission_lease)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

    def test_owned_prompt_root_input_ceiling_cannot_be_renewed_by_child(self):
        root, _ = self.open_direction(limits=dict(primitives=1, wall_seconds=120, game_seconds=1200))
        ref = self.runtime.status()["current_source"]
        child = self.control("menu", dict(purpose="Direction", label="Here", outcome="activated"),
            phase_id=root["request_id"], perception=dict(kind="direction", basis="player_interpretation",
            source_id=ref["observation_id"], question="Where?"))
        self.runtime.command(child)
        operation = self.settled(child["request_id"])
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertEqual([r["state"] for r in self.runtime._ledger.primitive_records()], ["returned"])

    def test_actual_normal_return_records_root_game_time_overshoot(self):
        root, _ = self.open_direction(limits=dict(primitives=8, wall_seconds=120, game_seconds=2))
        anchor = self.runtime._prompt_phase.game_anchor
        self.bridge.value.update(scene=self.runtime._store.observation(anchor)["scene"], ui=None)
        self.bridge.value["scene"]["turn"] += 3
        self.bridge.value["revision"] += 1
        self.bridge.value["boundary"]["kind"] = "normal_play"
        self.runtime.command(self.request("observe"))
        operation = self.settled("observe-1")
        self.assertEqual(operation["state"], "completed", operation)
        self.assertIn("budget", operation["result"]["budget_stop"])
        self.assertEqual(operation["result"]["phase"]["stage"], "complete")
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertIsNone(self.controller._mission_lease)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

    def test_interaction_without_prompt_does_not_block_following_navigation(self):
        self.bridge.value["actions"].append("open")
        self.start()
        root = self.control("interact", dict(action="open", intent="Open", desired_outcome="Inspect result"))
        self.runtime.command(root)
        operation = self.settled(root["request_id"])
        self.assertEqual(operation["state"], "partial", operation)
        self.assertEqual(operation["result"]["phase"]["stage"], "complete")
        self.assertIsNone(self.runtime._prompt_phase)
        navigation = self.navigation()
        self.runtime.command(navigation)
        self.assertEqual(self.settled(navigation["request_id"])["state"], "completed")

    def test_editor_batch_requires_new_whole_value_view_before_separate_commit(self):
        self.bridge.editor_text = "Old"
        normal = copy.deepcopy(self.bridge.value["scene"])
        def text(bridge, request):
            if request.get("action") == "TEXT.CLEAR": bridge.editor_text = ""
            elif request["kind"] == "key": bridge.editor_text += request["key"]
            elif request.get("action") == "TEXT.CONFIRM":
                bridge.value.update(scene=normal, ui=None, category="DEFAULTMODE", actions=["UP", "DOWN", "LEFT", "RIGHT"])
                bridge.value["boundary"]["kind"] = "normal_play"
            if request["kind"] in ("key", "action"):
                bridge.value["boundary"]["id"] = f'edit-{bridge.value["revision"]}'
            return True
        root, _ = self.open_direction(prompt=dict(category="STRING_INPUT", actions=["TEXT.CLEAR", "TEXT.CONFIRM", "QUIT"]), effect=text)
        def editor(visible):
            return dict(kind="editor", source_id=self.runtime.status()["current_source"]["observation_id"],
                basis="player_interpretation", purpose="filter", label="Filter", visible_text=visible,
                whole_value=True, focused=True)
        child = self.control("edit", dict(purpose="filter", text="New", commit=False),
            phase_id=root["request_id"], perception=editor("Old"))
        self.runtime.command(child)
        operation = self.settled(child["request_id"])
        self.assertEqual(operation["state"], "partial", operation)
        self.assertEqual(operation["result"]["proposals"], 4)
        self.assertTrue(operation["result"]["verification_required"])
        self.assertEqual(self.bridge.editor_text, "New")
        self.assertNotIn("TEXT.CONFIRM", [r.get("action") for r in self.bridge.delivered])
        commit = self.control("edit", dict(purpose="filter", text="New", commit=True),
            phase_id=root["request_id"], perception=editor("New"), request_id="commit")
        self.runtime.command(commit)
        operation = self.settled("commit")
        self.assertEqual(operation["state"], "partial", operation)
        self.assertEqual(operation["result"]["phase"]["stage"], "complete")
        self.assertEqual(self.runtime.status()["spent_inputs"], 6)
        self.assertIsNone(self.runtime._prompt_phase)

    def test_ordinary_editor_cannot_claim_creation_name_purpose(self):
        root, _ = self.open_direction(prompt=dict(category="STRING_INPUT", actions=["TEXT.CLEAR", "TEXT.CONFIRM", "QUIT"]))
        for purpose in ("character_name", "world_name"):
            child = self.control("edit", dict(purpose=purpose, text="Unadmitted", commit=False),
                phase_id=root["request_id"], request_id=purpose, perception=dict(kind="editor",
                basis="player_interpretation", source_id=self.runtime.status()["current_source"]["observation_id"],
                purpose=purpose, label="Name", visible_text="", whole_value=True, focused=True))
            response = self.runtime.command(child)
            self.assertEqual(response["status"], "rejected", response)
            self.assertIn("lifecycle", response["reason"])
        self.assertIsNotNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

    def test_observer_memory_is_copied_journaled_context_not_a_fresh_projection(self):
        initial = self.start()
        self.assertIsNone(initial["memory_context"])
        scope = dict(mission_id=self.a.mission_id, session=initial["current_source"]["session"], coordinate_epoch=0)
        response = self.runtime.command(dict(schema="mission/2", kind="context", mission_id=self.a.mission_id,
            scope=scope, query="position", max_bytes=32768))
        packet = copy.deepcopy(response["context"]["packet"])
        response["context"]["packet"]["query"] = "Modified caller copy"
        with patch.object(self.runtime._memory, "context", side_effect=AssertionError("Status must not recompute memory")):
            first = self.runtime.status()
            self.assertEqual(first["memory_context"], packet)
            first["memory_context"]["query"] = "Modified status copy"
            self.assertEqual(self.runtime.status()["memory_context"], packet)
        navigation = self.navigation()
        self.runtime.command(navigation)
        self.settled(navigation["request_id"])
        self.assertEqual(self.runtime.status()["memory_context"], packet)
        self.assertFalse(packet["grants_authority"])

    def test_interaction_unknown_delivery_cannot_open_prompt(self):
        self.bridge.value["actions"].append("open")
        self.start()
        self.bridge.behavior = lambda bridge, request: request["kind"] != "action"
        root = self.control("interact", dict(action="open", intent="Open", desired_outcome="Inspect actual result"))
        self.runtime.command(root)
        operation = self.settled(root["request_id"])
        self.assertEqual(operation["state"], "unknown", operation)
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertNotIn("phase", operation["result"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertIsNone(self.controller._mission_lease)

    def test_policy_unknown_precedes_simultaneous_game_budget_overshoot(self):
        self.bridge.value["actions"].append("open")
        self.start()
        epoch = self.runtime.status()["epoch"]
        def changed_control(bridge, request):
            if request.get("action") == "open":
                bridge.value["scene"]["turn"] += 3
                bridge.value["boundary"]["control_generation"] += 1
            return True
        self.bridge.behavior = changed_control
        root = self.control("interact", dict(action="open", intent="Open", desired_outcome="Inspect actual result"),
            limits=dict(primitives=8, wall_seconds=120, game_seconds=2))
        self.runtime.command(root)
        operation = self.settled(root["request_id"])
        self.assertEqual(operation["state"], "unknown", operation)
        self.assertEqual(operation["result"]["disposition"], "unknown")
        self.assertIn("control", operation["result"]["reason"])
        self.assertIn("budget", operation["result"]["budget_stop"])
        self.assertIsNotNone(operation["result"]["pending_logical_id"])
        self.assertEqual(self.runtime.status()["pause_cause"], "unknown")
        self.assertEqual(self.runtime.status()["epoch"], epoch + 1)
        self.assertEqual(self.runtime._ledger.primitive_records()[0]["state"], "returned")

    def test_unintegrated_phase_or_missing_work_cannot_be_ignored_to_dispatch_navigation(self):
        self.start()
        for n, change in enumerate((dict(phase_id="guessed-phase"), dict(work_id="missing-work"))):
            request = self.navigation(request_id=f"blocked-association-{n}", **change)
            response = self.runtime.command(request)
            if "phase_id" in change:
                self.assertEqual(response["status"], "rejected", response)
                continue
            self.assertEqual(response["status"], "accepted")
            operation = self.settled(request["request_id"])
            self.assertEqual(operation["state"], "blocked", operation)
        self.assertFalse([r for r in self.bridge.delivered if r["kind"] == "action"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 0)

    def test_false_publication_flag_after_actual_movement_stays_unknown_unresolved(self):
        self.start()
        request = self.navigation()
        real = self.controller.execute_mission
        def contradict_publication(*args, **kwargs):
            receipt = real(*args, **kwargs)
            self.assertTrue(receipt["published"])
            self.assertEqual(receipt["result"]["status"], "ready")
            receipt["published"] = False
            return receipt
        with patch.object(self.controller, "execute_mission", contradict_publication):
            self.runtime.command(request)
            operation = self.settled(request["request_id"])
        self.assertEqual(self.bridge.value["scene"]["position"], [1, 0, 0])
        self.assertEqual(len([r for r in self.bridge.delivered if r["kind"] == "action"]), 1)
        self.assertEqual(operation["state"], "unknown", operation)
        row, = self.runtime._ledger.primitive_records()
        self.assertEqual(row["state"], "unknown")
        self.assertEqual(row["result"]["transport_disposition"], "unknown")
        self.assertIn("contradicts", row["result"]["reason"])
        self.assertIsNone(row["effect"])
        self.assertEqual(self.runtime.status()["unresolved_effects"], [row["logical_id"]])
        self.assertEqual(self.runtime.status()["phase"], "paused")
        self.assertIsNone(self.controller._mission_lease)
        self.assertEqual(self.runtime.command(request)["operation"], operation)
        self.assertEqual(len([r for r in self.bridge.delivered if r["kind"] == "action"]), 1)

    def test_lost_retained_preflight_before_publication_is_known_non_delivery(self):
        self.start()
        request = self.navigation()
        real = self.runtime._ledger.prepare_primitive
        def lose_preflight(*args, **kwargs):
            result = real(*args, **kwargs)
            identity = result["primitive"]["intent"]["preflight_source"]
            reference = next(r for r in self.runtime._store.historical_references if r.observation_id == identity)
            Path(reference.frame_path).unlink()
            return result
        with patch.object(self.runtime._ledger, "prepare_primitive", lose_preflight):
            self.runtime.command(request)
            op = self.settled(request["request_id"])
        self.assertNotEqual(op["state"], "completed", op)
        row, = self.runtime._ledger.primitive_records()
        self.assertEqual(row["state"], "not_dispatched")
        self.assertEqual(row["result"]["transport_disposition"], "not_dispatched")
        self.assertFalse(row["result"]["published"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertEqual(self.runtime.status()["unresolved_effects"], [])
        self.assertEqual([r for r in self.bridge.delivered if r["kind"] == "action"], [])

    def test_active_stop_revokes_now_and_never_queues_or_retargets_old_epoch(self):
        self.start()
        entered, release = threading.Event(), threading.Event()
        real = self.runtime._store.retain_equivalent
        def blocked(*args, **kwargs):
            entered.set()
            release.wait(3)
            return real(*args, **kwargs)
        with patch.object(self.runtime._store, "retain_equivalent", blocked):
            request = self.navigation()
            self.runtime.command(request)
            self.assertTrue(entered.wait(2))
            stop = self.request("stop", finish=False, reason="Stop ordinary input now")
            original = copy.deepcopy(stop)
            started = time.monotonic()
            response = self.runtime.command(stop)
            self.assertLess(time.monotonic() - started, 0.4)
            self.assertEqual(response["status"], "rejected", response)
            self.assertIn("not admitted", response["reason"])
            self.assertEqual(stop, original)
            self.assertEqual(self.runtime._queue.qsize(), 0)
            self.assertEqual(self.runtime.status()["phase"], "paused")
            release.set()
            self.assertEqual(self.settled(request["request_id"])["state"], "paused")
        self.wait(lambda: self.runtime.status()["active_operation"] is None)
        absent = self.runtime.command(dict(schema="mission/2", kind="result", mission_id=self.a.mission_id,
                                           operation_id=stop["request_id"]))
        self.assertEqual(absent["status"], "rejected")
        retry = self.request("stop", request_id="stop-new-epoch", finish=False, reason=stop["reason"])
        self.assertNotEqual(retry["epoch"], stop["epoch"])
        self.assertEqual(self.runtime.command(retry)["status"], "accepted")
        completed = self.settled(retry["request_id"])
        self.assertTrue(completed["result"]["paused"])
        self.assertEqual(self.runtime.status()["phase"], "paused")
        self.assertEqual([r for r in self.bridge.delivered if r["kind"] == "action"], [])
        epoch = self.runtime.status()["epoch"]
        self.assertEqual(self.runtime.command(retry)["operation"], completed)
        self.assertEqual(self.runtime.status()["epoch"], epoch)

    def test_context_pending_work_and_lost_new_source_never_resurrect_old_stock(self):
        self.start()
        first = self.runtime.status()["current_source"]
        scope = dict(mission_id=self.a.mission_id, session=first["session"], coordinate_epoch=0)
        def assertion(identity, source, quantity):
            return claim(id=identity, scope=scope, value={"quantity": quantity, "state": None},
                sources=[source["observation_id"]], supports=[{"sources": [source["observation_id"]], "claims": []}],
                received_time=int(time.time() * 1000), observed_time={"revision": source["revision"], "turn": source["turn"]})
        req = self.request("remember", request_id="old-stock", entry_type="claim", entry=assertion("old", first, 18))
        self.runtime.command(req)
        self.assertEqual(self.settled("old-stock")["state"], "completed")
        self.bridge.value["revision"] += 1
        observe = self.request("observe")
        self.runtime.command(observe)
        self.settled(observe["request_id"])
        second = self.runtime.status()["current_source"]
        req = self.request("remember", request_id="new-stock", entry_type="claim", entry=assertion("new", second, 0))
        self.runtime.command(req)
        self.assertEqual(self.settled("new-stock")["state"], "completed")
        work = {"schema": "campaign-memory/2", "record_type": "Work", "predecessor_work_id": None, "id": "water-pending",
            "intent": "Treat water and verify storage", "scope": scope, "stage": "pending-storage",
            "progress": None, "available": [], "committed": [],
            "predicted_output": [{"subject": "clean-water", "quantity": 2, "unit": "charges", "coverage_id": "kettle"}],
            "observed_output": [], "unresolved_effects": [], "sources": [],
            "next_verification": "Inspect actual water and storage", "status": "planned"}
        req = self.request("remember", request_id="pending-work", entry_type="work", entry=work)
        self.runtime.command(req)
        self.assertEqual(self.settled("pending-work")["state"], "completed")
        Path(second["frame_path"]).unlink()
        context_request = dict(schema="mission/2", kind="context", mission_id=self.a.mission_id,
                               scope=scope, query="water", max_bytes=32768)
        out = self.runtime.command(context_request)
        self.assertEqual(out["status"], "accepted", out)
        packet = out["context"]["packet"]
        water = [c for c in packet["claims"] if c["key"]["subject"] == "water"]
        self.assertEqual([c["id"] for c in water], ["new"])
        self.assertEqual(water[0]["status"], "unknown")
        self.assertIsNone(water[0]["value"]["quantity"])
        self.assertEqual(packet["work"][0]["available"], [])
        self.assertEqual(packet["work"][0]["observed_output"], [])
        self.assertEqual(packet["work"][0]["predicted_output"][0]["quantity"], 2)
        self.assertTrue(packet["reobservations"])
        self.assertIsNone(self.runtime.status()["current_source"])

    def test_decisions_require_exact_durably_issued_packet_and_cannot_change_authority(self):
        self.start()
        source = self.runtime.status()["current_source"]
        scope = dict(mission_id=self.a.mission_id, session=source["session"], coordinate_epoch=0)
        out = self.runtime.command(dict(schema="mission/2", kind="context", mission_id=self.a.mission_id,
            scope=scope, query="water", max_bytes=32768))
        packet = out["context"]["packet"]
        decision = dict(schema="campaign-memory/2", record_type="Decision", id="decision-1",
            packet_id=packet["packet_id"], scope=scope, query=packet["query"], memory_version=packet["memory_version"],
            claim_ids=[], work_ids=[], source_ids=[], lesson_ids=packet["lesson_ids"],
            omitted=packet["omitted"]["claims"] + packet["omitted"]["work"], reason="Inspect actual water")
        lease = self.controller._mission_lease
        valid = self.request("remember", request_id="decision", entry_type="decision", entry=decision)
        self.runtime.command(valid)
        self.assertEqual(self.settled("decision")["state"], "completed")
        invalid = self.request("remember", request_id="unissued-decision", entry_type="decision",
            entry={**decision, "id": "decision-2", "packet_id": "unissued-packet"})
        self.runtime.command(invalid)
        self.assertEqual(self.settled("unissued-decision")["state"], "blocked")
        self.assertIs(self.controller._mission_lease, lease)
        self.assertEqual(self.runtime.status()["phase"], "active")

    def test_input_cleanup_reserve_rejects_second_input_without_new_mapping(self):
        self.a = replace(self.a, limits=replace(self.a.limits, inputs=2, primitive_mappings=2),
                         cleanup_reserve=replace(self.a.cleanup_reserve, inputs=1))
        self.start()
        first = self.navigation()
        self.runtime.command(first)
        self.assertEqual(self.settled(first["request_id"])["state"], "completed")
        second = self.navigation(target=(2, 0, 0), request_id="second")
        self.runtime.command(second)
        op = self.settled("second")
        self.assertEqual(op["state"], "blocked", op)
        self.assertEqual(len(self.runtime._ledger.primitive_records()), 1)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertEqual(self.runtime.status()["remaining_limits"]["inputs"], 1)
        self.assertIsNone(self.runtime._store._reservation)

    def test_byte_cleanup_reserve_alone_rejects_preflight_before_preparation(self):
        self.a = replace(self.a, limits=replace(self.a.limits, frame_bytes=200 * 1024 * 1024),
            cleanup_reserve=replace(self.a.cleanup_reserve, frame_bytes=140 * 1024 * 1024))
        self.start()
        request = self.navigation()
        self.runtime.command(request)
        self.assertEqual(self.settled(request["request_id"])["state"], "blocked")
        self.assertEqual(self.runtime._ledger.primitive_records(), ())
        self.assertEqual([r for r in self.bridge.delivered if r["kind"] == "action"], [])

    def test_malformed_correlated_receipt_keeps_unknown_without_replay(self):
        self.start()
        operator_counter = self.controller.operator_pause_generation
        request = self.navigation()
        real = self.controller.execute_mission
        def corrupt(*args, **kwargs):
            receipt = real(*args, **kwargs)
            receipt["logical_action_id"] = "wrong-logical-id"
            return receipt
        with patch.object(self.controller, "execute_mission", corrupt):
            self.runtime.command(request)
            op = self.settled(request["request_id"])
        self.assertEqual(op["state"], "unknown", op)
        self.assertEqual(self.runtime._ledger.primitive_records()[0]["state"], "unknown")
        self.runtime.command(request)
        self.assertEqual(len([r for r in self.bridge.delivered if r["kind"] == "action"]), 1)
        self.assertEqual(self.runtime.status()["epoch"], 1)
        self.assertEqual(self.controller.operator_pause_generation, operator_counter)

    def test_unknown_receipt_after_user_pause_preserves_original_pause_cause_epoch(self):
        self.start()
        entered, release = threading.Event(), threading.Event()
        def lose_after_effect(bridge, request):
            if request["kind"] == "action":
                entered.set()
                release.wait(2)
                return False
            return True
        self.bridge.behavior = lose_after_effect
        request = self.navigation()
        self.runtime.command(request)
        self.assertTrue(entered.wait(2))
        self.runtime.pause("User Pause before lost ACK")
        operator_counter = self.controller.operator_pause_generation
        release.set()
        op = self.settled(request["request_id"])
        self.assertEqual(op["state"], "unknown", op)
        self.assertEqual(self.runtime.status()["epoch"], 1)
        self.assertEqual(self.runtime.status()["pause_cause"], "user")
        self.assertEqual(self.runtime.status()["reason"], "User Pause before lost ACK")
        self.assertEqual(self.controller.operator_pause_generation, operator_counter)

    def test_new_controller_boot_opens_same_stable_mission_without_restored_authority(self):
        self.start()
        def elapsed(bridge, request):
            if request["kind"] == "action":
                bridge.value["scene"]["turn"] += 7
            return True
        self.bridge.behavior = elapsed
        request = self.navigation()
        self.runtime.command(request)
        self.assertEqual(self.settled(request["request_id"])["state"], "completed")
        ledger_path = self.runtime._ledger.path
        evidence_directory = self.runtime._store.directory
        deadline = self.runtime._mission_deadline
        original_journal = self.controller.journal
        original_boot = self.controller.authority["controller_boot_id"]
        self.runtime.close()
        self.bridge.__exit__(None, None, None)
        root = self.controller.root
        self.controller.close()
        self.controller = Controller(root, timeout=0.8)
        self.addCleanup(self.controller.close)
        self.bridge = VisibleBridge(self.controller)
        self.bridge.__enter__()
        self.addCleanup(self.bridge.__exit__, None, None, None)
        self.runtime = MissionRuntime(self.controller)
        self.assertNotEqual(self.controller.journal, original_journal)
        self.assertNotEqual(self.controller.authority["controller_boot_id"], original_boot)
        self._prepared_native = True
        # This core fixture assumes durable identity only to isolate historical
        # timeline arithmetic. Production diagnostic-session reopening is tested
        # without this assumption in test_mission_exit.
        with patch.object(self.runtime, "_require_normal_adoption", side_effect=lambda ref: self.runtime._store.verify(ref)):
            status = self.start()
        self.assertEqual(self.runtime._ledger.path, ledger_path)
        self.assertEqual(self.runtime._store.directory, evidence_directory)
        self.assertEqual(self.runtime._mission_deadline, deadline)
        self.assertEqual(status["spent_inputs"], 1)
        self.assertEqual(status["metrics"]["game_seconds"], 7)
        self.assertEqual(status["phase"], "paused")
        self.assertEqual(self.runtime._bindings, {})
        self.assertIsNone(status["current_source"])
        self.assertIsNone(self.controller._mission_lease)
        self.assertEqual(self.result(request["request_id"])["state"], "completed")
        self.assertEqual(self.bridge.delivered, [])

    def test_paused_start_admits_without_native_resume_or_planning_binding(self):
        req = dict(schema="mission/2", kind="start", request_id="start-1", admission=self.a.to_dict())
        self.assertEqual(self.runtime.command(req)["status"], "accepted")
        op = self.settled("start-1")
        self.assertTrue(op["result"]["lifecycle_needed"])
        self.assertEqual(self.runtime.status()["phase"], "admitted")
        self.assertEqual(self.bridge.delivered, [])

        self.assertEqual(self.runtime._bindings, {})
        self.assertIsNone(self.controller._mission_lease)
        req = self.request("observe")
        self.runtime.command(req)
        self.settled(req["request_id"])
        self.assertEqual(self.runtime.status()["phase"], "admitted")
        self.assertEqual(self.bridge.delivered, [])

    def test_unpaused_unowned_scene_cannot_seed_identity_or_mission_game_clock(self):
        self.assertEqual(self.controller.execute("observe")["status"], "ready")
        self.assertEqual(self.controller.execute("resume")["status"], "ready")
        delivered = copy.deepcopy(self.bridge.delivered)
        req = dict(schema="mission/2", kind="start", request_id="start-1", admission=self.a.to_dict())
        with patch.object(self.controller, "acquire_mission", side_effect=AssertionError("Start cannot adopt identity")):
            self.assertEqual(self.runtime.command(req)["status"], "accepted")
            self.assertTrue(self.settled("start-1")["result"]["lifecycle_needed"])
            self.runtime.command(self.request("observe"))
            self.settled("observe-1")
        self.assertEqual(self.runtime.status()["phase"], "admitted")
        self.assertIsNone(self.runtime.status()["current_source"])
        self.assertIsNone(self.runtime.status()["metrics"]["game_seconds"])
        self.assertEqual(self.runtime._store.historical_references, ())
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertIsNone(self.controller._mission_lease)

    def test_missing_native_start_stays_admitted_without_launch(self):
        self.bridge.__exit__(None, None, None)
        req = dict(schema="mission/2", kind="start", request_id="start-1", admission=self.a.to_dict())
        self.runtime.command(req)
        op = self.settled("start-1")
        self.assertTrue(op["result"]["lifecycle_needed"])
        self.assertEqual(self.runtime.status()["phase"], "admitted")
        self.assertIsNone(self.runtime.status()["current_source"])
        self.assertEqual(self.bridge.delivered, [])
        self.assertIsNone(self.controller.pending)
        self.assertEqual(self.bridge.requests, [])

    def test_two_step_surveyed_route_uses_only_verified_cardinal_displacement(self):
        self.bridge.value["scene"]["position"] = [1, 0, 0]
        self.start()
        # A separate synthetic observed boundary establishes the starting position.
        self.bridge.value["scene"]["position"] = [0, 0, 0]
        self.bridge.value["revision"] += 1
        observe = self.request("observe")
        self.runtime.command(observe)
        self.settled(observe["request_id"])
        request = self.navigation(target=(2, 0, 0))
        self.runtime.command(request)
        op = self.settled(request["request_id"])
        self.assertEqual(op["state"], "completed", op)
        self.assertEqual(op["result"]["verified_steps"], 2)
        self.assertEqual(op["result"]["position"], [2, 0, 0])
        self.assertEqual(len(self.runtime._ledger.primitive_records()), 2)
        self.assertEqual(self.runtime.status()["phase"], "active")

    def test_large_valid_native_observation_does_not_overflow_ledger_receipts(self):
        self.bridge.value["actions"] += [f"ACTION-{i:03d}-" + "x" * 117 for i in range(507)]
        self.start()
        request = self.navigation()
        self.runtime.command(request)
        op = self.settled(request["request_id"])
        self.assertEqual(op["state"], "completed", op)
        rows = self.runtime._ledger.primitive_records()
        self.assertEqual(rows[0]["state"], "returned")
        self.assertLess(len(canonical(rows[0]["result"]).encode()), 4096)
        self.assertNotIn("actions", rows[0]["result"])
        self.assertGreater(len(canonical(self.controller.observation_snapshot()[0]).encode()), 65_536)

    def test_prepared_callback_failure_keeps_charge_and_proves_non_delivery(self):
        self.start()
        request = self.navigation()
        real = self.runtime._ledger.prepare_primitive
        def cancel_after_prepare(*args, **kwargs):
            out = real(*args, **kwargs)
            self.runtime._active.cancelled.set()
            return out
        with patch.object(self.runtime._ledger, "prepare_primitive", cancel_after_prepare):
            self.runtime.command(request)
            op = self.settled(request["request_id"])
        self.assertEqual(op["state"], "paused", op)
        primitive, = self.runtime._ledger.primitive_records()
        self.assertEqual(primitive["state"], "not_dispatched")
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertEqual([r for r in self.bridge.delivered if r["kind"] == "action"], [])
        self.assertIsNone(self.runtime._store._reservation)

    def test_after_storage_failure_stays_unknown_and_does_not_fake_before_as_after(self):
        self.start()
        request = self.navigation()
        with patch.object(self.runtime._store, "ingest", side_effect=OSError("after-frame fsync failed")):
            self.runtime.command(request)
            op = self.settled(request["request_id"])
        self.assertEqual(op["state"], "unknown", op)
        row, = self.runtime._ledger.primitive_records()
        self.assertEqual(row["state"], "unknown")
        self.assertIsNone(row["result"]["source_after"])
        self.assertEqual(len([r for r in self.bridge.delivered if r["kind"] == "action"]), 1)
        self.wait(lambda: self.runtime.status()["active_operation"] is None)
        self.assertIsNone(self.runtime.status()["current_source"])
        self.assertEqual(self.runtime.status()["epoch"], 1)

    def test_crash_prepared_reopen_keeps_unknown_effect_and_no_authority(self):
        directory = self.controller.root / ".runtime" / "missions" / self.a.mission_id
        with MissionLedger(directory, admission=self.a, now=time.time()) as ledger:
            start = dict(schema="mission/2", kind="start", request_id="start-1", admission=self.a.to_dict())
            ledger.begin_request(start, now=time.time())
            ledger.complete_request("start-1", "completed", {"admitted": True}, now=time.time())
            ledger.activate(epoch=0, player_id=self.a.player_id, now=time.time())
            from tests.test_mission_contracts import skill
            request = skill()
            ledger.begin_request(request, now=time.time())
            ledger.prepare_primitive(request["request_id"], "crashed-logical", intent(), now=time.time())
            deadline = ledger.snapshot(now=time.time())["deadline"]
        self._prepared_native = True
        self.start()
        operation = self.result(request["request_id"])
        self.assertEqual(operation["state"], "unknown")
        self.assertEqual(self.runtime.status()["unresolved_effects"], ["crashed-logical"])
        self.assertEqual(self.runtime._mission_deadline, deadline)
        self.assertEqual(self.runtime._bindings, {})
        self.assertIsNone(self.controller._mission_lease)
        self.assertEqual(self.bridge.delivered, [])

    def test_input_and_game_ceiling_preserve_original_counters(self):
        self.a = replace(self.a, limits=replace(self.a.limits, inputs=2, primitive_mappings=2, game_seconds=1),
                         cleanup_reserve=replace(self.a.cleanup_reserve, inputs=1))
        self.start()
        def elapsed(bridge, request):
            if request["kind"] == "action":
                bridge.value["scene"]["turn"] += 1
            return True
        self.bridge.behavior = elapsed
        first = self.navigation()
        self.runtime.command(first)
        self.assertEqual(self.settled(first["request_id"])["state"], "completed")
        second = self.navigation(target=(2, 0, 0), request_id="second")
        self.runtime.command(second)
        self.assertNotEqual(self.settled("second")["state"], "completed")
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertEqual(self.runtime.status()["metrics"]["game_seconds"], 1)
        self.assertEqual(len([r for r in self.bridge.delivered if r["kind"] == "action"]), 1)

    def test_observed_game_overshoot_retains_returned_receipt_and_partial_result(self):
        self.a = replace(self.a, limits=replace(self.a.limits, game_seconds=1))
        self.start()
        def elapsed(bridge, request):
            if request["kind"] == "action":
                bridge.value["scene"]["turn"] += 5
            return True
        self.bridge.behavior = elapsed
        request = self.navigation()
        self.runtime.command(request)
        op = self.settled(request["request_id"])
        self.assertEqual(op["state"], "partial", op)
        self.assertEqual(self.runtime._ledger.primitive_records()[0]["state"], "returned")
        self.assertEqual(self.runtime.status()["metrics"]["game_seconds"], 5)
        self.assertEqual(self.runtime.status()["remaining_limits"]["game_seconds"], 0)

    def test_frame_and_byte_cleanup_reserves_reject_before_preparation(self):
        self.a = replace(self.a, limits=replace(self.a.limits, frames=10,
                         frame_bytes=200 * 1024 * 1024), cleanup_reserve=replace(self.a.cleanup_reserve,
                         frames=8, frame_bytes=140 * 1024 * 1024))
        self.start()
        request = self.navigation()
        self.runtime.command(request)
        op = self.settled(request["request_id"])
        self.assertEqual(op["state"], "blocked", op)
        self.assertEqual(self.runtime._ledger.primitive_records(), ())
        self.assertEqual([r for r in self.bridge.delivered if r["kind"] == "action"], [])
        self.assertLess(self.runtime._store.usage()["frames"], 3)

    def test_original_wall_cleanup_reserve_does_not_renew_on_context(self):
        self.a = replace(self.a, limits=replace(self.a.limits, wall_seconds=2),
                         cleanup_reserve=replace(self.a.cleanup_reserve, wall_seconds=1))
        self.start()
        deadline = self.runtime._mission_deadline
        actual_wall = time.time
        self.runtime._wall = lambda: actual_wall() + 1.1
        request = self.navigation()
        self.runtime.command(request)
        op = self.settled(request["request_id"])
        self.assertNotEqual(op["state"], "completed", op)
        self.assertEqual(self.runtime._mission_deadline, deadline)
        self.assertEqual(self.runtime._ledger.primitive_records(), ())
        self.assertEqual([r for r in self.bridge.delivered if r["kind"] == "action"], [])

    def test_pause_during_observe_retains_user_cause_without_late_relabel(self):
        self.start()
        entered, release = threading.Event(), threading.Event()
        def gate(bridge, request):
            if request["kind"] == "observe":
                entered.set()
                release.wait(3)
        self.bridge.before_gate = gate
        request = self.request("observe")
        self.runtime.command(request)
        self.assertTrue(entered.wait(2))
        started = time.monotonic()
        self.runtime.pause("User Pause during Observe")
        self.assertLess(time.monotonic() - started, 0.4)
        self.assertEqual(self.runtime.status()["pause_cause"], "user")
        release.set()
        op = self.settled(request["request_id"])
        self.assertEqual(op["state"], "paused", op)
        self.assertEqual(self.runtime.status()["epoch"], 1)
        self.assertEqual(self.runtime.status()["pause_cause"], "user")
        self.assertEqual(self.runtime.status()["reason"], "User Pause during Observe")

    def test_context_journal_failure_never_issues_a_packet_or_allows_more_work(self):
        self.start()
        source = self.runtime.status()["current_source"]
        request = dict(schema="mission/2", kind="context", mission_id=self.a.mission_id,
            scope=dict(mission_id=self.a.mission_id, session=source["session"], coordinate_epoch=0),
            query="water", max_bytes=8192)
        record = self.controller._record
        def fail(request, result):
            if request["kind"] == "mission_context":
                raise OSError("context fsync failed")
            return record(request, result)
        with patch.object(self.controller, "_record", fail):
            out = self.runtime.command(request)
            self.assertEqual(out["status"], "rejected", out)
        self.assertEqual(self.runtime._issued_packets, [])
        self.assertIsNone(self.controller._mission_lease)
        self.assertEqual(self.runtime.command(self.request("observe"))["status"], "rejected")

    def test_close_wait_is_bounded_and_storage_stays_open_under_live_writer(self):
        self.start()
        entered, release = threading.Event(), threading.Event()
        real = self.runtime._store.retain_equivalent
        def blocked(*args, **kwargs):
            entered.set()
            release.wait(4)
            return real(*args, **kwargs)
        with patch.object(self.runtime._store, "retain_equivalent", blocked):
            request = self.navigation()
            self.runtime.command(request)
            self.assertTrue(entered.wait(2))
            started = time.monotonic()
            self.runtime.close()
            self.assertLess(time.monotonic() - started, 1.8)
            self.assertTrue(self.runtime._thread.is_alive())
            self.assertIsNotNone(self.runtime._ledger._db)
            self.assertFalse(self.runtime._store._lock.closed)
            release.set()
            self.runtime._thread.join(3)
        self.assertFalse(self.runtime._thread.is_alive())
        self.assertIsNone(self.runtime._ledger._db)
        self.assertTrue(self.runtime._store._lock.closed)
        self.assertEqual([r for r in self.bridge.delivered if r["kind"] == "action"], [])

    def test_constructor_strict_start_holding_lease_and_cache_are_passive(self):
        self.assertIsNone(self.runtime.status())
        self.assertEqual(self.bridge.requests, [])
        self.assertEqual(self.runtime.command({"kind": "start"})["status"], "rejected")
        snapshot = self.start()
        self.assertEqual(snapshot["phase"], "active")
        self.assertEqual(self.controller._mission_lease.operation, "interaction")
        self.assertFalse(snapshot["grants_authority"])
        with patch.object(self.controller, "status", side_effect=AssertionError("source IO")), \
                patch.object(self.runtime._store, "usage", side_effect=AssertionError("storage IO")):
            snapshot["objective"] = "mutated"
            self.assertEqual(self.runtime.status()["objective"], self.a.objective)
        raw = self.controller.execute("action", action="RIGHT", expected_session="game-test", expected_revision=2)
        self.assertEqual(raw["status"], "controller_error")
        self.assertEqual([r for r in self.bridge.delivered if r["kind"] == "action"], [])

    def test_navigation_exact_dedup_durable_prepare_and_bounded_receipt(self):
        self.start()
        seen = []
        def gate(bridge, request):
            if request["kind"] == "action":
                rows = self.runtime._ledger.primitive_records()
                seen.append(rows[-1]["state"])
        self.bridge.before_gate = gate
        req = self.navigation()
        self.assertEqual(self.runtime.command(req)["status"], "accepted")
        self.assertEqual(self.runtime.command(req)["operation_id"], req["request_id"])
        self.assertEqual(self.runtime.command({**req, "goal": {**req["goal"], "target": [0, 1, 0]}})["status"], "rejected")
        op = self.settled(req["request_id"])
        self.assertEqual(op["state"], "completed", op)
        self.assertEqual(op["result"]["verified_steps"], 1)
        self.assertEqual(seen, ["prepared"])
        primitive, = self.runtime._ledger.primitive_records()
        self.assertEqual(primitive["state"], "returned")
        self.assertNotEqual(primitive["intent"]["source_before"], primitive["intent"]["preflight_source"])
        self.assertNotIn("scene", primitive["result"])
        self.assertEqual(primitive["native_id"], self.bridge.delivered[-1]["id"])
        self.assertEqual(self.runtime.command(req)["operation"], op)

    def test_already_reached_and_unknown_route_do_not_rotate_or_send(self):
        self.start()
        lease = self.controller._mission_lease
        req = self.navigation(target=(0, 0, 0))
        self.runtime.command(req)
        self.assertEqual(self.settled(req["request_id"])["state"], "completed")
        self.assertIs(self.controller._mission_lease, lease)
        req = self.navigation(target=(50, 0, 0), request_id="far")
        self.runtime.command(req)
        self.assertEqual(self.settled("far")["state"], "blocked")
        self.assertEqual(len(self.runtime._ledger.primitive_records()), 0)

    def test_slow_thought_refresh_keeps_original_request_and_three_sources(self):
        self.start()
        req = self.navigation()
        original = copy.deepcopy(req)
        threading.Event().wait(3.05)
        self.runtime.command(req)
        op = self.settled(req["request_id"])
        self.assertEqual(op["state"], "completed", op)
        self.assertEqual(op["request"], original)
        primitive, = self.runtime._ledger.primitive_records()
        intent = primitive["intent"]
        relation = intent["revalidation"]
        self.assertEqual(relation["original"]["source_id"], original["sources"][0])
        self.assertEqual(len({original["sources"][0], intent["source_before"], intent["preflight_source"]}), 3)
        self.assertEqual(self.runtime._ledger.snapshot(now=time.time())["deadline"], self.runtime._mission_deadline)

    def test_pause_status_while_runtime_preflight_storage_blocked(self):
        self.start()
        entered, release = threading.Event(), threading.Event()
        real = self.runtime._store.retain_equivalent
        def blocked(*args, **kwargs):
            entered.set()
            release.wait(3)
            return real(*args, **kwargs)
        with patch.object(self.runtime._store, "retain_equivalent", blocked):
            req = self.navigation()
            self.runtime.command(req)
            self.assertTrue(entered.wait(2))
            start = time.monotonic()
            paused = self.runtime.pause("User pressed Pause")
            self.assertLess(time.monotonic() - start, 0.4)
            self.assertEqual(paused["status"], "pause_requested")
            self.assertEqual(self.runtime.status()["pause_cause"], "user")
            release.set()
            op = self.settled(req["request_id"])
        self.assertNotEqual(op["state"], "completed")
        self.assertEqual([r for r in self.bridge.delivered if r["kind"] == "action"], [])
        self.wait(lambda: not self.runtime.status()["active_operation"])
        self.assertEqual(self.runtime.status()["epoch"], 1)

    def test_preflight_capacity_failure_has_no_input_or_prepared_charge(self):
        self.start()
        req = self.navigation()
        with patch.object(self.runtime._store, "reserve_dispatch", side_effect=CapacityError("full")):
            self.runtime.command(req)
            op = self.settled(req["request_id"])
        self.assertEqual(op["state"], "blocked", op)
        self.assertEqual(self.runtime._ledger.primitive_records(), ())
        self.assertEqual(self.runtime._ledger.snapshot(now=time.time())["spent_inputs"], 0)
        self.assertEqual([r for r in self.bridge.delivered if r["kind"] == "action"], [])

    def test_unknown_ack_is_never_replayed_or_renewed_after_reopen(self):
        self.start()
        req = self.navigation()
        self.bridge.behavior = lambda bridge, request: request["kind"] != "action"
        self.runtime.command(req)
        op = self.settled(req["request_id"])
        self.assertEqual(op["state"], "unknown", op)
        self.assertEqual(self.runtime._ledger.primitive_records()[0]["state"], "unknown")
        deadline = self.runtime._mission_deadline
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.start()
        self.assertEqual(self.runtime.status()["phase"], "paused")
        self.assertEqual(self.runtime._bindings, {})
        self.assertIsNone(self.controller._mission_lease)
        self.assertEqual(self.runtime._mission_deadline, deadline)
        self.assertEqual(self.runtime.command(req)["operation"]["state"], "unknown")
        self.assertEqual(len([r for r in self.bridge.delivered if r["kind"] == "action"]), 1)

    def test_context_exact_wrapper_before_return_size_and_memory_correction(self):
        self.start()
        source = self.runtime.status()["current_source"]
        scope = dict(mission_id=self.a.mission_id, session=source["session"], coordinate_epoch=0)
        req = dict(schema="mission/2", kind="context", mission_id=self.a.mission_id,
                   scope=scope, query="water and pending work", max_bytes=8192)
        response = self.runtime.command(req)
        self.assertEqual(response["status"], "accepted", response)
        context = response["context"]
        self.assertLessEqual(len(canonical(context).encode()), 8192)
        events = [json.loads(line) for line in self.controller.journal.read_text().splitlines()]
        issued = [e["outcome"]["context"] for e in events if e["request"]["kind"] == "mission_context"]
        self.assertEqual(issued[-1], context)
        self.assertEqual(context["packet"]["packet_id"], self.runtime._memory._packets[-1]["packet_id"])
        self.assertEqual(self.runtime.command({**req, "max_bytes": 512})["status"], "rejected")
        entry = claim(scope=scope, sources=[source["observation_id"]], supports=[{"sources": [source["observation_id"]], "claims": []}],
                      observed_time={"revision": source["revision"], "turn": source["turn"]}, received_time=int(time.time() * 1000))
        remember = self.request("remember", entry_type="claim", entry=entry)
        self.runtime.command(remember)
        self.assertEqual(self.settled(remember["request_id"])["state"], "completed")
        corrected = {**entry, "id": "corrected", "supersedes": [entry["id"]], "value": {"quantity": 3, "state": None}}
        correction = self.request("correct", entry_type="claim", entry=corrected, retired_ids=[entry["id"]], reason="Misread")
        self.runtime.command(correction)
        self.assertEqual(self.settled(correction["request_id"])["state"], "completed")

    def test_active_normal_scene_cannot_authorize_process_launch(self):
        self.start()
        data = self.request("lifecycle", operation="launch", world=self.a.scenario.world,
            character=self.a.scenario.character, sources=[], expected_session=None,
            expected_revision=None, expected_boundary_id=None,
            limits=dict(primitives=1, wall_seconds=60, game_seconds=1))
        with patch("harness.mission_runtime.NativeProcess", side_effect=AssertionError("No launch from active game")):
            self.assertEqual(self.runtime.command(data)["status"], "accepted")
            operation = self.settled(data["request_id"])
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertIn("unchanged paused/admitted", operation["result"]["reason"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 0)
        self.assertIsNone(self.controller._mission_lease)

    def test_no_fake_handoff_unimplemented_load_or_finish_and_stop_revokes(self):
        self.start()
        source = self.runtime.status()["current_source"]
        for req in [self.request("handoff", checkpoint_ids=[], successor_role="player"),
                    self.request("lifecycle", operation="load", world=self.a.scenario.world,
                                 character=self.a.scenario.character, sources=[source["observation_id"]],
                                 expected_session=source["session"], expected_revision=source["revision"],
                                 expected_boundary_id=self.runtime._store.observation(self.runtime._current)["boundary"]["id"],
                                 limits={"primitives": 1, "wall_seconds": 60, "game_seconds": 1}),
                    self.request("stop", finish=True, reason="claimed success")]:
            self.assertEqual(self.runtime.command(req)["status"], "accepted")
            self.assertEqual(self.settled(req["request_id"])["state"], "blocked")
        req = self.request("stop", request_id="stop-real", finish=False, reason="Stop now")
        self.runtime.command(req)
        self.settled("stop-real")
        self.assertEqual(self.runtime.status()["phase"], "paused")
        self.assertIsNone(self.controller._mission_lease)

    def test_old_ledger_format_rejects_without_replacing_bytes(self):
        directory = self.controller.root / ".runtime" / "missions" / self.a.mission_id
        directory.mkdir(parents=True)
        path = directory / "mission.sqlite3"
        with closing(sqlite3.connect(path)) as db:
            db.execute("PRAGMA user_version=2")
        before = path.read_bytes()
        response = self.runtime.command(dict(schema="mission/2", kind="start", request_id="start-1", admission=self.a.to_dict()))
        self.assertEqual(response["status"], "rejected", response)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.bridge.delivered, [])

    def test_one_writer_blocks_concurrent_skill_and_pause_cancels_queue(self):
        self.start()
        entered, release = threading.Event(), threading.Event()
        real = self.runtime._store.retain_equivalent
        def blocked(*args, **kwargs):
            entered.set()
            release.wait(3)
            return real(*args, **kwargs)
        with patch.object(self.runtime._store, "retain_equivalent", blocked):
            req = self.navigation()
            self.runtime.command(req)
            self.assertTrue(entered.wait(2))
            competing = self.navigation(request_id="competing")
            self.assertEqual(self.runtime.command(competing)["status"], "rejected")
            with ThreadPoolExecutor(1) as pool:
                queued = pool.submit(self.runtime.command, self.request("observe"))
                self.wait(lambda: self.runtime._queue.qsize() == 1)
                self.runtime.pause()
                release.set()
                self.assertEqual(queued.result(3)["status"], "rejected")
        self.assertEqual([r for r in self.bridge.delivered if r["kind"] == "action"], [])


if __name__ == "__main__":
    unittest.main()
