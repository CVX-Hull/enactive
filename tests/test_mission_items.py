"""Synthetic item/inspection composition; no native inventory acceptance claim."""
import copy
import time
import unittest
from unittest.mock import patch

from harness.gameplay.mission_ledger import MissionLedger
from tests import test_mission_runtime as runtime_fixtures


class MissionItemTests(unittest.TestCase):
    setUp = runtime_fixtures.MissionRuntimeTests.setUp
    wait = runtime_fixtures.MissionRuntimeTests.wait
    request = runtime_fixtures.MissionRuntimeTests.request
    result = runtime_fixtures.MissionRuntimeTests.result
    settled = runtime_fixtures.MissionRuntimeTests.settled
    start = runtime_fixtures.MissionRuntimeTests.start
    control = runtime_fixtures.MissionRuntimeTests.control

    def open_items(self, *, direct_editor=False, primitives=16):
        self.bridge.value["actions"].extend(["pickup", "inventory"])
        self.start()
        self.normal = copy.deepcopy(self.bridge.value["scene"])
        self.chosen = 0
        def behavior(bridge, request):
            action = request.get("action")
            if action in ("pickup", "inventory"):
                self.inventory()
                if direct_editor:
                    self.editor()
            elif action == "MARK_WITH_COUNT":
                self.editor()
            elif action == "TEXT.CLEAR":
                bridge.editor_text = ""
            elif request["kind"] == "key":
                bridge.editor_text += request["key"]
            elif action == "TEXT.CONFIRM":
                self.chosen = int(bridge.editor_text)
                self.inventory()
            elif action in ("CONFIRM", "QUIT"):
                bridge.value.update(category="DEFAULTMODE", scene=self.normal, ui=None, actions=["pickup", "inventory"])
                bridge.value["boundary"].update(kind="normal_play", id="item-return")
            return True
        self.bridge.behavior = behavior
        goal = dict(purpose="pickup", label="clean water", quantity=2, quantity_unit="charges",
                    step="start", outcome="acquired")
        root = self.control("item", goal, request_id="water-root",
                            limits=dict(primitives=primitives, wall_seconds=120, game_seconds=1200))
        self.assertEqual(self.runtime.command(root)["status"], "accepted")
        opened = self.settled(root["request_id"])
        self.assertEqual(opened["state"], "partial", opened)
        self.assertEqual(opened["result"]["phase"]["phase_kind"], "item")
        self.root = root
        return opened

    def inventory(self):
        self.bridge.editor_text = None
        self.bridge.value.update(category="INVENTORY", scene=None, ui=None,
                                 actions=["UP", "DOWN", "MARK_WITH_COUNT", "CONFIRM", "QUIT"])
        self.bridge.value["boundary"].update(kind="menu", id="water-selector")

    def editor(self):
        self.bridge.editor_text = "0"
        self.bridge.value.update(category="STRING_INPUT", scene=None, ui=None,
                                 actions=["TEXT.CLEAR", "TEXT.CONFIRM", "TEXT.QUIT"])
        self.bridge.value["boundary"].update(kind="menu", id="quantity-editor")

    def send(self, request):
        self.assertEqual(self.runtime.command(request)["status"], "accepted")
        return self.settled(request["request_id"])

    def select(self, *, step="select", **changes):
        source = self.runtime.status()["current_source"]["observation_id"]
        view = dict(kind="item_selection", basis="player_interpretation", source_id=source,
            control="vertical", mode="multi", rows=[dict(label="clean water", enabled=True,
            available_quantity=6, quantity_unit="charges", chosen_quantity=self.chosen)], selected=0,
            selection_coverage="all_selected", selected_items=[] if not self.chosen else [dict(
                label="clean water", quantity=self.chosen, quantity_unit="charges")])
        goal = {**self.root["goal"], "step": step}
        return self.control("item", goal, phase_id="water-root", perception=view,
                            request_id="item-" + step, **changes)

    def edit(self, *, text="2", commit=False, purpose="quantity", request_id="edit-count"):
        source = self.runtime.status()["current_source"]["observation_id"]
        view = dict(kind="editor", basis="player_interpretation", source_id=source,
            purpose=purpose, label="Count", visible_text=self.bridge.editor_text, whole_value=True, focused=True)
        return self.control("edit", dict(purpose=purpose, text=text, commit=commit),
            phase_id="water-root", perception=view, request_id=request_id)

    def open_consumption_selector(self):
        self.bridge.value["actions"].append("eat")
        self.start()
        normal = copy.deepcopy(self.bridge.value["scene"])
        self.consume_return = False
        def behavior(bridge, request):
            action = request.get("action")
            if action == "eat":
                self.inventory()
            elif action == "CONFIRM":
                bridge.value.update(category="DEFAULTMODE", scene=None, ui=None, actions=[])
                bridge.value["boundary"].update(kind="activity_poll", id="consume-poll",
                    recovery_operations=["request_interrupt"])
            elif request["kind"] == "observe" and bridge.value["boundary"]["kind"] == "activity_poll":
                if self.consume_return:
                    bridge.value["revision"] += 1
                    self.inventory()
                    bridge.value["boundary"]["recovery_operations"] = []
            elif action == "QUIT" or (request["kind"] == "direct" and request["input"] ==
                    dict(type="key", key="ESC", modifiers=[])):
                bridge.value.update(category="DEFAULTMODE", scene=normal, ui=None, actions=["eat"])
                bridge.value["boundary"].update(kind="normal_play", id="consume-return", recovery_operations=[])
            return True
        self.bridge.behavior = behavior
        goal = dict(purpose="consume", label="ration", quantity=1, quantity_unit="items",
            step="start", outcome="consumed")
        self.root = self.control("item", goal, request_id="consume-root")
        self.assertEqual(self.send(self.root)["state"], "partial")

    def consumption_selection(self, request_id="consume-selection"):
        source = self.runtime.status()["current_source"]["observation_id"]
        view = dict(kind="item_selection", basis="player_interpretation", source_id=source,
            control="vertical", mode="single", rows=[dict(label="ration", enabled=True,
            available_quantity=1, quantity_unit="items", chosen_quantity=None)], selected=0,
            selection_coverage="all_selected", selected_items=[])
        return self.control("item", {**self.root["goal"], "step": "select"}, phase_id="consume-root",
            perception=view, request_id=request_id)

    def begin_consumption_activity(self):
        self.open_consumption_selector()
        selected = self.send(self.consumption_selection())
        self.assertEqual(selected["result"]["phase"]["stage"], "activity_poll", selected)

    def observe_consumption(self, request_id="consume-observation"):
        self.assertEqual(self.runtime.command(self.request("observe", request_id=request_id))["status"], "accepted")
        return self.settled(request_id)

    def test_consumption_poll_return_and_explicit_control_keep_original_root(self):
        self.begin_consumption_activity()
        original = self.runtime._ledger.request("consume-root")
        before, delivered = self.runtime.status()["spent_inputs"], copy.deepcopy(self.bridge.delivered)
        polling = self.observe_consumption("consume-progress")
        self.assertEqual(polling["state"], "completed", polling)
        self.consume_return = True
        result = self.observe_consumption()
        self.assertEqual(result["state"], "completed", result)
        self.assertEqual(polling["result"]["phase"]["stage"], "activity_poll")
        self.assertEqual(result["result"]["phase"]["phase_kind"], "item")
        self.assertEqual(result["result"]["phase"]["origin_request_id"], "consume-root")
        self.assertEqual(result["result"]["phase"]["stage"], "awaiting_control")
        self.assertTrue(result["result"]["verification_required"])
        self.assertFalse(result["result"]["grants_authority"])
        self.assertEqual(self.runtime._prompt_phase.root_id, "consume-root")
        self.assertEqual(self.runtime.status()["spent_inputs"], before)
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertEqual(self.observe_consumption("consume-menu-refresh")["state"], "completed")
        source = self.runtime.status()["current_source"]["observation_id"]
        closed = self.send(self.control("menu", dict(purpose="Close consume selector", label="Cancel", outcome="dismissed"),
            phase_id="consume-root", request_id="consume-close", perception=dict(kind="dismissal",
                basis="player_interpretation", source_id=source, question="Consume item")))
        self.assertEqual(closed["result"]["phase"]["stage"], "complete", closed)
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], before+1)
        self.assertEqual(self.runtime._ledger.request("consume-root"), original)
        self.assertFalse([r for r in self.runtime._ledger.memory_records("claim")
            if r["entry"]["key"]["property"] == "supply"])
        directory = self.runtime._ledger.path.parent
        self.runtime.close()
        with MissionLedger(directory, now=time.time()) as reopened:
            self.assertEqual(reopened.request("consume-observation"), result)
            self.assertEqual(reopened.snapshot(now=time.time())["phase"], "paused")

    def test_consumption_observe_cannot_cross_native_control_generation(self):
        self.begin_consumption_activity()
        self.consume_return = True
        self.bridge.value["boundary"]["control_generation"] += 1
        before = copy.deepcopy(self.bridge.delivered)
        result = self.observe_consumption()
        self.assertEqual(result["state"], "blocked", result)
        self.assertIn("control", result["result"]["reason"])
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(self.bridge.delivered, before)

    def test_consumption_observe_uses_original_deadline_without_new_input(self):
        self.begin_consumption_activity()
        deadline = self.runtime._ledger.request("consume-root")["deadline"]
        before = len(self.bridge.requests)
        with patch.object(self.runtime, "_wall", return_value=deadline):
            result = self.observe_consumption()
        self.assertEqual(result["state"], "blocked", result)
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(len(self.bridge.requests), before)

    def test_user_pause_wins_during_consumption_observation(self):
        self.begin_consumption_activity()
        self.consume_return = True
        observe = self.runtime._observe_native
        def paused(work, **kwargs):
            value = observe(work, **kwargs)
            self.runtime.pause("User Pause during item activity", cause="user")
            return value
        with patch.object(self.runtime, "_observe_native", side_effect=paused):
            result = self.observe_consumption()
        self.assertEqual(result["state"], "paused", result)
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertIsNone(self.runtime._lease)

    def test_item_activity_cannot_borrow_a_typed_activity_root(self):
        self.begin_consumption_activity()
        phase, before = self.runtime._prompt_phase, copy.deepcopy(self.bridge.delivered)
        poll = self.control("activity", dict(operation="rest", target="rest", game_seconds=300,
            interrupt_allowed=True, step="poll", answer=None, interrupt_request_id=None),
            phase_id="consume-root", request_id="borrowed-activity-poll")
        result = self.runtime.command(poll)
        self.assertEqual(result["status"], "rejected", result)
        self.assertIn("immutable root goal", result["reason"])
        self.assertIs(self.runtime._prompt_phase, phase)
        self.assertEqual(self.bridge.delivered, before)

    def test_pickup_count_edit_fresh_commit_and_effect_verification_share_root(self):
        self.open_items()
        selected = self.send(self.select())
        self.assertEqual(selected["state"], "partial", selected)
        self.assertTrue(self.runtime._prompt_phase.quantity_editor)
        typed = self.send(self.edit())
        self.assertEqual(typed["state"], "partial", typed)
        self.assertEqual(self.bridge.editor_text, "2")
        edited = self.send(self.edit(commit=True, request_id="commit-count"))
        self.assertEqual(edited["state"], "partial", edited)
        self.assertFalse(self.runtime._prompt_phase.quantity_editor)
        result = self.send(self.select(step="commit"))
        self.assertEqual(result["state"], "partial", result)
        self.assertTrue(result["result"]["verification_required"])
        self.assertEqual(result["result"]["phase"]["stage"], "complete")
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], 6)
        records = self.runtime._ledger.primitive_records()
        self.assertEqual([r["intent"]["value"] for r in records],
                         ["pickup", "MARK_WITH_COUNT", "TEXT.CLEAR", "2", "TEXT.CONFIRM", "CONFIRM"])
        self.assertTrue(all(r["state"] == "returned" for r in records))
        self.assertFalse([r for r in self.runtime._ledger.memory_records("claim")
                          if r["entry"]["key"]["property"] == "supply"])
        self.runtime._ledger._verify(self.a)

    def test_quantity_claim_cannot_borrow_an_unopened_editor(self):
        self.open_items(direct_editor=True)
        before = len(self.bridge.delivered)
        result = self.send(self.edit())
        self.assertEqual(result["state"], "blocked", result)
        self.assertIn("MARK_WITH_COUNT", result["result"]["reason"])
        self.assertEqual(len(self.bridge.delivered), before)

    def test_root_count_cannot_be_changed_by_an_editor_interpretation(self):
        self.open_items()
        self.send(self.select())
        before = len(self.bridge.delivered)
        result = self.send(self.edit(text="3"))
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(len(self.bridge.delivered), before)

    def test_item_phase_cannot_relabel_count_editor_as_filter(self):
        self.open_items()
        self.send(self.select())
        before = len(self.bridge.delivered)
        result = self.send(self.edit(purpose="filter"))
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(len(self.bridge.delivered), before)

    def test_fresh_editor_commit_remains_a_separate_charged_operation(self):
        self.open_items(primitives=3)
        self.send(self.select())
        result = self.send(self.edit())
        self.assertEqual(result["state"], "partial", result)
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)
        self.assertEqual(self.bridge.editor_text, "")
        self.assertNotIn("TEXT.CONFIRM", [r.get("action") for r in self.bridge.delivered])

    def test_item_commit_cannot_use_an_ordinary_menu_confirmation(self):
        self.open_items()
        source = self.runtime.status()["current_source"]["observation_id"]
        request = self.control("menu", dict(purpose="select water", label="clean water", outcome="activated"),
            phase_id="water-root", perception=dict(kind="menu", basis="player_interpretation", source_id=source,
                control="vertical", rows=[dict(label="clean water", enabled=True)], selected=0, question=""))
        before = len(self.bridge.delivered)
        result = self.send(request)
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(len(self.bridge.delivered), before)

    def test_consume_inspection_uses_bound_all_items_selector_and_can_cancel(self):
        # Pinned DEFAULTMODE binds eat, while advertising open_consume without
        # a default key. Registration alone does not prove an executable action.
        self.bridge.value["actions"].extend(["eat", "open_consume"])
        self.start()
        delivered_before = len(self.bridge.delivered)
        normal = copy.deepcopy(self.bridge.value["scene"])
        def behavior(bridge, request):
            if request.get("action") == "open_consume":
                bridge.value["revision"] -= 1
                bridge.value.update(status="rejected", error="action has no single-key binding in current mode")
            elif request.get("action") == "eat":
                self.inventory()
            elif request.get("action") == "QUIT":
                bridge.value.update(category="DEFAULTMODE", scene=normal, ui=None, actions=["eat", "open_consume"])
                bridge.value["boundary"].update(kind="normal_play", id="consume-inspection-return")
            return True
        self.bridge.behavior = behavior
        root = self.control("inspect", dict(purpose="consume"), request_id="inspect-consume",
            limits=dict(primitives=2, wall_seconds=120, game_seconds=1200))
        opened = self.send(root)
        self.assertEqual(opened["state"], "partial", opened)
        self.assertEqual(opened["result"]["phase"]["phase_kind"], "inspect")
        source = self.runtime.status()["current_source"]["observation_id"]
        closed = self.send(self.control("menu", dict(purpose="Close actual consume choices", label="Cancel", outcome="dismissed"),
            phase_id=root["request_id"], perception=dict(kind="dismissal", basis="player_interpretation",
                source_id=source, question="Visible consume selector"), request_id="close-consume"))
        self.assertEqual(closed["state"], "partial", closed)
        self.assertEqual(closed["result"]["phase"]["stage"], "complete")
        self.assertEqual([r.get("action") for r in self.bridge.delivered[delivered_before:]], ["eat", "QUIT"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertIsNone(self.runtime._prompt_phase)
        self.runtime._ledger._verify(self.a)

    def test_inspection_root_opens_and_dismisses_without_claiming_inventory(self):
        self.bridge.value["actions"].append("inventory")
        self.start()
        normal = copy.deepcopy(self.bridge.value["scene"])
        def behavior(bridge, request):
            if request.get("action") == "inventory":
                self.inventory()
            elif request.get("action") == "QUIT":
                bridge.value.update(category="DEFAULTMODE", scene=normal, ui=None, actions=["inventory"])
                bridge.value["boundary"].update(kind="normal_play", id="inspection-return")
            return True
        self.bridge.behavior = behavior
        rejected = self.control("inspect", dict(purpose="inventory"), request_id="unusable-inspection-budget",
            limits=dict(primitives=1, wall_seconds=120, game_seconds=1200))
        lease, epoch = self.runtime._lease, self.runtime.status()["epoch"]
        refused = self.send(rejected)
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertEqual(refused["result"]["proposals"], 0)
        self.assertIn("whole phase", refused["result"]["reason"])
        self.assertEqual(self.runtime.status()["spent_inputs"], 0)
        self.assertEqual(self.runtime.status()["epoch"], epoch)
        self.assertIs(self.runtime._lease, lease)
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertFalse(any(r.get("action") == "inventory" for r in self.bridge.delivered))
        root = self.control("inspect", dict(purpose="inventory"), request_id="inspect-inventory",
            limits=dict(primitives=2, wall_seconds=120, game_seconds=1200))
        opened = self.send(root)
        self.assertEqual(opened["state"], "partial", opened)
        self.assertEqual(opened["result"]["phase"]["phase_kind"], "inspect")
        source = self.runtime.status()["current_source"]["observation_id"]
        child = self.control("menu", dict(purpose="Close inventory", label="Cancel", outcome="dismissed"),
            phase_id=root["request_id"], perception=dict(kind="dismissal", basis="player_interpretation",
                source_id=source, question="Visible inventory"), request_id="close-inventory")
        closed = self.send(child)
        self.assertEqual(closed["state"], "partial", closed)
        self.assertEqual(closed["result"]["phase"]["stage"], "complete")
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.runtime._ledger._verify(self.a)


if __name__ == "__main__":
    unittest.main()
