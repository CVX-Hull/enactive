"""Owned terminal correlation with unfamiliar/changing synthetic menus.

No actual game exit, keyboard parity or latency qualification is inferred.
"""
from dataclasses import replace
from contextlib import closing
import copy
import json
from pathlib import Path
import sqlite3
import time
import unittest
from unittest.mock import patch

from harness.gameplay.contracts import ContractError, canonical
from harness.gameplay.mission_ledger import MissionLedger
from harness.mission_runtime import MissionRuntime
from tests import test_mission_exit as fixtures


class OrdinaryExitTests(unittest.TestCase):
    fake_launch = fixtures.MissionExitTests.fake_launch
    start = fixtures.MissionExitTests.start
    settled = fixtures.MissionExitTests.settled
    request = fixtures.MissionExitTests.request
    launch = fixtures.MissionExitTests.launch
    ready = fixtures.MissionExitTests.ready
    exit_request = fixtures.MissionExitTests.exit_request
    run_request = fixtures.MissionExitTests.run_request
    begin_exit = fixtures.MissionExitTests.begin_exit
    confirmation = fixtures.MissionExitTests.confirmation

    def setUp(self):
        fixtures.MissionExitTests.setUp(self)
        self.a = replace(self.a, allowed_skills=(*self.a.allowed_skills, "direct"))
        self.terminal = dict(type="key", key="Z", modifiers=[])

    def behavior(self, bridge, request):
        if request["kind"] != "direct":
            result = fixtures.MissionExitTests.behavior(self, bridge, request)
            if request.get("action") == "QUIT":
                bridge.value.update(category="UNSEEN_EXIT_FIRST", actions=["COORDINATE"])
            return result
        physical = request["input"]
        if physical == self.terminal:
            self.process_state.update(running=False, returncode=self.exit_code, outcome="exited")
            return False
        if physical.get("key") == "ESC":
            bridge.value.update(category="MAIN_MENU", actions=["CONFIRM", "QUIT"])
        elif physical.get("key") == "?":
            bridge.value.update(category="UNSEEN_EXIT_SECOND", actions=["ANY_INPUT", "COORDINATE"])
        else:
            bridge.editor_text = (bridge.editor_text or "") + physical.get("text", "changed")
        return True

    def raw(self, identity="physical-exit", *, physical=None, parent="exit", limits=None):
        data = self.confirmation(identity=identity)
        data.update(skill_kind="direct", phase_id=parent, perception=None, goal=dict(
            input=copy.deepcopy(self.terminal if physical is None else physical),
            intent="Use the currently visible owned exit interface", expected="Inspect actual effect",
            interrupt_allowed=False))
        if limits is not None:
            data["limits"] = limits
        return data

    def test_unfamiliar_menu_key_exit_reopens_without_restoring_input(self):
        self.ready()
        self.begin_exit()
        result = self.run_request(self.raw())
        self.assertEqual(result["state"], "completed", result)
        proof = result["result"]["normal_exit"]
        primitive = self.runtime._ledger.primitive(proof["terminal_logical_id"])
        self.assertEqual(primitive["intent"]["kind"], "direct")
        self.assertEqual(primitive["state"], "unknown")
        self.assertEqual(primitive["effect"]["basis"], "OwnedNormalExit")
        self.assertIn("published exit input", primitive["effect"]["note"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.start()
        self.assertEqual(self.runtime._ledger.primitive(primitive["logical_id"]), primitive)
        self.assertIsNone(self.runtime._exit_phase)
        self.assertIsNone(self.controller._mission_lease)

    def test_menu_changes_after_input_and_raw_key_follows_current_receiver(self):
        self.ready()
        root = self.begin_exit(limits=dict(primitives=5, wall_seconds=10, game_seconds=1))
        changed = self.run_request(self.raw("explore", physical=dict(type="key", key="?", modifiers=[])))
        self.assertEqual(changed["state"], "partial", changed)
        self.assertEqual(changed["result"]["phase"]["stage"], "awaiting_control")
        self.assertEqual(self.runtime._store.observation(self.runtime._current)["category"], "UNSEEN_EXIT_SECOND")
        self.assertEqual(self.run_request(self.raw())["state"], "completed")
        self.assertEqual(self.runtime._ledger.request("exit")["deadline"], root["deadline"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 4)

    def test_ordinary_cancel_then_new_root_does_not_require_magic_no_history(self):
        self.ready()
        self.begin_exit()
        cancelled = self.run_request(self.raw("escape", physical=dict(type="key", key="ESC", modifiers=[])))
        self.assertEqual(cancelled["state"], "partial", cancelled)
        self.assertFalse(cancelled["result"]["normal_exit_verified"])
        self.assertIsNone(self.runtime._exit_phase)
        self.assertTrue(self.controller.pause_requested)
        self.assertEqual(self.begin_exit(identity="exit-again")["state"], "partial")
        self.assertEqual(self.run_request(self.raw(parent="exit-again"))["state"], "completed")
        self.assertEqual(self.runtime.status()["spent_inputs"], 6)
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.start()

    def test_text_batch_terminal_correlates_later_scalar_with_original_entry(self):
        self.ready()
        self.begin_exit(limits=dict(primitives=5, wall_seconds=10, game_seconds=1))
        self.terminal = dict(type="text", text="b")
        result = self.run_request(self.raw(physical=dict(type="text", text="ab"),
            limits=dict(primitives=2, wall_seconds=10, game_seconds=1)))
        self.assertEqual(result["state"], "completed", result)
        inputs = [p for p in self.runtime._ledger.primitive_records() if p["request_id"] == "physical-exit"]
        self.assertEqual([p["intent"]["value"]["text"] for p in inputs], ["a", "b"])
        self.assertIsNotNone(inputs[0]["intent"]["input_observation"])
        self.assertIsNone(inputs[1]["intent"]["input_observation"])
        self.assertEqual([p["state"] for p in inputs], ["returned", "unknown"])
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.start()

    def test_click_resize_refuses_without_spend_then_new_current_click_exits(self):
        self.ready()
        self.begin_exit()
        geometry = self.runtime._store.observation(self.runtime._current)["frame_geometry"]
        data = self.raw(physical=dict(type="click", button="left", x=0, y=0, geometry=geometry))
        original = self.runtime._observe_native
        def resize(*args, **kwargs):
            self.bridge.value["revision"] += 1
            self.bridge.value["frame_geometry"]["window_width"] += 1
            return original(*args, **kwargs)
        with patch.object(self.runtime, "_observe_native", side_effect=resize):
            refused = self.run_request(data)
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertIn("mapping changed", refused["result"]["reason"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertIsNotNone(self.runtime._exit_phase)
        self.terminal = dict(type="click", button="left", x=0, y=0,
            geometry=self.runtime._store.observation(self.runtime._current)["frame_geometry"])
        self.assertEqual(self.run_request(self.raw("new-click"))["state"], "completed")

    def test_raw_key_accepts_visual_drift_but_keeps_original_custody(self):
        self.ready()
        self.begin_exit()
        data = self.raw()
        self.bridge.editor_text = "A different visible exit instruction"
        self.assertEqual(self.run_request(data)["state"], "completed")

    def test_changed_interpreted_source_refuses_locally_then_ordinary_input_exits(self):
        self.ready()
        root = self.begin_exit()
        data = self.confirmation()
        self.bridge.editor_text = "Changed visible instructions"
        result = self.run_request(data)
        self.assertEqual(result["state"], "blocked", result)
        self.assertIsNotNone(self.runtime._exit_phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertEqual(self.runtime._ledger.request("exit")["deadline"], root["deadline"])
        self.assertEqual(self.run_request(self.raw())["state"], "completed")

    def test_optional_quit_can_exit_directly_without_a_confirmation_menu(self):
        self.ready()
        original = self.behavior
        def immediate(bridge, request):
            if request.get("action") == "QUIT":
                self.process_state.update(running=False, returncode=0, outcome="exited")
                return False
            return original(bridge, request)
        self.bridge.behavior = immediate
        result = self.begin_exit()
        self.assertEqual(result["state"], "completed", result)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.start()

    def test_semantic_any_key_popup_terminal_uses_same_owned_exit_proof(self):
        self.ready()
        original = self.behavior
        def popup(bridge, request):
            if request.get("action") == "QUIT":
                bridge.value.update(category="POPUP_WAIT", actions=["ANY_INPUT", "COORDINATE"])
                return True
            if request["kind"] == "key" and request["key"] == "SPACE":
                self.process_state.update(running=False, returncode=0, outcome="exited")
                return False
            return original(bridge, request)
        self.bridge.behavior = popup
        self.begin_exit()
        data = self.confirmation()
        data["perception"].update(kind="dismissal", question="Exit notice")
        data["goal"].update(label="Cancel", outcome="dismissed")
        result = self.run_request(data)
        self.assertEqual(result["state"], "completed", result)
        primitive = self.runtime._ledger.primitive(result["result"]["normal_exit"]["terminal_logical_id"])
        self.assertEqual(primitive["intent"]["kind"], "key")
        self.assertEqual(primitive["state"], "unknown")
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.start()

    def test_known_menu_ack_with_newer_healthy_current_capture_keeps_exit_scope(self):
        self.ready()
        original = self.behavior
        def live_yes(bridge, request):
            if request.get("action") == "QUIT":
                bridge.value.update(category="YESNO", actions=["YES", "NO"])
                return True
            if request.get("action") == "YES":
                return True
            return original(bridge, request)
        self.bridge.behavior = live_yes
        self.begin_exit()
        execute = self.controller.execute_mission
        def newer_current(*args, **kwargs):
            raw = execute(*args, **kwargs)
            current = copy.deepcopy(raw["result"])
            current.update(id="", revision=current["revision"] + 1)
            self.bridge.editor_text = "New visible instruction after the known input"
            self.bridge.value = copy.deepcopy(current)
            self.bridge.publish(current)
            self.controller._accept(json.loads((self.controller.bridge / "state.json").read_text()))
            return raw
        with patch.object(self.controller, "execute_mission", side_effect=newer_current):
            result = self.run_request(self.confirmation())
        self.assertEqual(result["state"], "partial", result)
        self.assertIsNotNone(self.runtime._exit_phase)
        self.assertEqual(result["result"]["phase"]["stage"], "awaiting_control")
        self.assertEqual(self.runtime._ledger.primitive_records()[-1]["state"], "returned")
        self.assertEqual(self.run_request(self.raw())["state"], "completed")

    def test_known_unexpected_native_row_jump_keeps_ordinary_exit_scope(self):
        self.ready()
        original = self.behavior
        rows = [dict(id=f"row-{i}", text=label, enabled=True, hotkey=None, rendered_marker=None)
                for i, label in enumerate(("One", "Two", "Three"))]
        def jump(bridge, request):
            if request.get("action") == "QUIT":
                bridge.value.update(category="UILIST", actions=["UILIST.UP", "UILIST.DOWN", "CONFIRM"],
                    ui=dict(purpose="uilist", title="Exit choices", rows=copy.deepcopy(rows), selected="row-0",
                            filter=None, count=None, coverage="rendered_rows_only"))
                return True
            if request.get("action") == "UILIST.DOWN":
                bridge.value["ui"]["selected"] = "row-2"
                bridge.value["boundary"]["id"] = "surprising-returned-focus"
                return True
            return original(bridge, request)
        self.bridge.behavior = jump
        self.begin_exit(limits=dict(primitives=5, wall_seconds=10, game_seconds=1))
        data = self.confirmation()
        data.update(perception=None, goal=dict(purpose="Choose current exit control", label="Three", outcome="focused"))
        result = self.run_request(data)
        self.assertEqual(result["state"], "partial", result)
        self.assertIn("row jump", result["result"]["reason"])
        self.assertIsNotNone(self.runtime._exit_phase)
        self.assertEqual(self.runtime._ledger.primitive_records()[-1]["state"], "returned")
        self.assertEqual(self.run_request(self.raw())["state"], "completed")

    def test_known_returned_input_with_invalidated_source_revokes_exit_scope(self):
        self.ready()
        original = self.behavior
        def live_yes(bridge, request):
            if request.get("action") == "QUIT":
                bridge.value.update(category="YESNO", actions=["YES", "NO"])
                return True
            if request.get("action") == "YES":
                return True
            return original(bridge, request)
        self.bridge.behavior = live_yes
        self.begin_exit()
        source = Path(self.runtime._current.frame_path)
        execute = self.controller.execute_mission
        def source_loss(*args, **kwargs):
            raw = execute(*args, **kwargs)
            source.chmod(0o600)
            source.write_bytes(b"Corrupted synthetic selected source")
            return raw
        with patch.object(self.controller, "execute_mission", side_effect=source_loss):
            result = self.run_request(self.confirmation())
        self.assertEqual(result["state"], "blocked", result)
        self.assertIsNone(self.runtime._exit_phase)
        self.assertIsNone(self.controller._mission_lease)
        self.assertEqual(self.runtime._ledger.primitive_records()[-1]["state"], "returned")
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)
        self.assertNotIn("normal_exit", result["result"])

    def test_pause_during_raw_refresh_sends_no_event(self):
        self.ready()
        self.begin_exit()
        data = self.raw()
        observe = self.runtime._observe_native
        def stop(*args, **kwargs):
            result = observe(*args, **kwargs)
            self.runtime.pause("User Pause during ordinary exit refresh")
            return result
        with patch.object(self.runtime, "_observe_native", side_effect=stop):
            result = self.run_request(data)
        self.assertEqual(result["state"], "paused", result)
        self.assertFalse(any(r["kind"] == "direct" for r in self.bridge.delivered))
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)

    def test_nonzero_raw_terminal_exit_keeps_unknown_charge_and_custody(self):
        self.ready()
        self.exit_code = 1
        self.begin_exit()
        result = self.run_request(self.raw())
        self.assertEqual(result["state"], "blocked", result)
        self.assertNotIn("normal_exit", result["result"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)
        self.assertIsNotNone(self.controller.pending)

    def test_reopen_rejects_retargeted_ordinary_terminal_input(self):
        self.ready()
        self.begin_exit()
        result = self.run_request(self.raw())
        self.assertEqual(result["state"], "completed", result)
        proof = result["result"]["normal_exit"]
        path, directory = self.runtime._ledger.path, self.runtime._ledger.directory
        self.runtime.close()
        with closing(sqlite3.connect(path)) as db, db:
            row = db.execute("SELECT intent FROM primitives WHERE id=?", (proof["terminal_logical_id"],)).fetchone()
            intent = json.loads(row[0])
            intent["value"]["key"] = "X"
            db.execute("UPDATE primitives SET intent=? WHERE id=?", (canonical(intent), proof["terminal_logical_id"]))
        before = path.read_bytes()
        with self.assertRaises(ContractError):
            MissionLedger(directory, now=time.time())
        self.assertEqual(path.read_bytes(), before)

    def test_reopen_rejects_native_admission_that_differs_from_retained_intent(self):
        self.ready()
        self.begin_exit()
        result = self.run_request(self.raw())
        self.assertEqual(result["state"], "completed", result)
        identity = result["result"]["normal_exit"]["terminal_logical_id"]
        path, directory = self.runtime._ledger.path, self.runtime._ledger.directory
        self.runtime.close()
        with closing(sqlite3.connect(path)) as db, db:
            receipt = json.loads(db.execute("SELECT result FROM primitives WHERE id=?", (identity,)).fetchone()[0])
            native = json.loads(receipt["native_request_json"])
            native["input"]["key"] = "X"
            receipt["native_request_json"] = canonical(native)
            db.execute("UPDATE primitives SET result=? WHERE id=?", (canonical(receipt), identity))
        before = path.read_bytes()
        with self.assertRaises(ContractError):
            MissionLedger(directory, now=time.time())
        self.assertEqual(path.read_bytes(), before)

    def test_reopen_rejects_terminal_binding_with_different_original_operator(self):
        self.ready()
        self.begin_exit()
        result = self.run_request(self.raw())
        self.assertEqual(result["state"], "completed", result)
        identity = result["result"]["normal_exit"]["terminal_logical_id"]
        path, directory = self.runtime._ledger.path, self.runtime._ledger.directory
        self.runtime.close()
        with closing(sqlite3.connect(path)) as db, db:
            receipt = json.loads(db.execute("SELECT result FROM primitives WHERE id=?", (identity,)).fetchone()[0])
            receipt["dispatch_binding"]["operator_pause_generation"] += 1
            db.execute("UPDATE primitives SET result=? WHERE id=?", (canonical(receipt), identity))
        before = path.read_bytes()
        with self.assertRaises(ContractError):
            MissionLedger(directory, now=time.time())
        self.assertEqual(path.read_bytes(), before)
