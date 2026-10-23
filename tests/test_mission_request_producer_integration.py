"""Canonical producer over real writer/controller/storage and synthetic native UI.

The native process/visible UI are controlled fixtures, not CDDA qualification.
Identity adoption and authority guards are never mocked in the lifecycle lane.
The activity lane retains its fixture's explicit pre-adopted identity assumption.
"""
from copy import deepcopy
import unittest
from unittest.mock import patch

from harness.gameplay.contracts import ContractError
from harness.gameplay.mission_requests import compose_request
from tests.test_mission_creation import MissionCreationFixture
from tests import test_mission_activity_recovery as activity


def compose(case, raw, scope, *, source=None, supports=()):
    """Reuse fixture semantic choices, discard all handwritten wire bindings."""
    intent = {key: deepcopy(raw[key]) for key in
        ("kind", "skill_kind", "goal", "perception", "procedure", "work_id", "operation", "world",
         "character", "identity_claim_ids") if key in raw}
    if intent.get("perception") is not None:
        intent["perception"].pop("source_id", None)
    if source is None and intent.get("operation") != "launch":
        ref = case.runtime._current
        source = dict(reference=ref.to_dict(), observation=case.runtime._store.observation(ref))
    return compose_request(case.runtime.status(), request_id=raw["request_id"], intent=intent,
        limits=raw["limits"], scope=scope, source=source, supporting_source_ids=supports)


class ProducedCreationFixture(MissionCreationFixture):
    def launch(self, **changes):
        return self.run_request(compose(self, self.request(**changes), "new_root"))

    def lifecycle(self, identity, operation="create", *, parent=None, claims=None, supports=()):
        raw = super().lifecycle(identity, operation, parent=parent, claims=claims)
        return compose(self, raw, "new_root" if parent is None else "lifecycle", supports=supports)

    def control(self, identity, label, **choices):
        return compose(self, super().control(identity, label, **choices), "lifecycle")

    def save(self):
        self.assertEqual(self.run_request(self.lifecycle("save", "save"))["state"], "partial")
        answer = self.run_request(self.control("save-yes", "Yes", parent="save", question="Save and quit?"))
        self.assertEqual(answer["state"], "unknown", answer)
        self.observe("save-observe-first")
        first = self.runtime._current
        self.observe("save-observe-second")
        self.assertNotEqual(first, self.runtime._current)
        request = self.lifecycle("save-reconcile", "save", parent="save", supports=(first.observation_id,))
        result = self.run_request(request)
        self.assertEqual(result["state"], "completed", result)
        return result


class ProducerLifecycleIntegrationTests(ProducedCreationFixture, unittest.TestCase):
    def test_item_uilist_and_inventory_dismissals_then_normal_ending(self):
        self.create()
        self.bridge.value["actions"].append("inventory")
        self.bridge.value["revision"] += 1  # The changed fixture action set is a new native revision.
        self.bridge.value["boundary"]["id"] = "inventory-capable-normal"
        self.observe("inventory-ready")
        ordinary = self.bridge.behavior

        def item_menu(bridge, request):
            category, action = bridge.value["category"], request.get("action")
            if category == "DEFAULTMODE" and action == "inventory":
                self.menu("INVENTORY", ["UP", "DOWN", "CONFIRM", "QUIT"], in_game=True)
            elif category == "INVENTORY" and action == "CONFIRM":
                self.menu("UILIST", ["UILIST.UP", "UILIST.DOWN", "CONFIRM", "UILIST.QUIT"], in_game=True)
            elif category == "UILIST" and action == "UILIST.QUIT":
                self.menu("INVENTORY", ["UP", "DOWN", "CONFIRM", "QUIT"], in_game=True)
            elif category == "INVENTORY" and action == "QUIT":
                self.normal(f"normal-{self.launch_count}")
            else:
                return ordinary(bridge, request)
            return True

        self.bridge.behavior = item_menu
        intent = dict(kind="skill", skill_kind="inspect", goal=dict(purpose="inventory"),
                      work_id=None, perception=None, procedure=None)
        limits = dict(primitives=8, wall_seconds=120, game_seconds=60)

        def request(identity, intent, scope):
            ref = self.runtime._current
            return compose_request(self.runtime.status(), request_id=identity, intent=intent,
                limits=limits, scope=scope,
                source=dict(reference=ref.to_dict(), observation=self.runtime._store.observation(ref)))

        opened = self.run_request(request("inventory", intent, "new_root"))
        self.assertEqual(opened["state"], "partial", opened)
        menu = dict(kind="skill", skill_kind="menu", work_id=None,
            goal=dict(purpose="Inspect actual represented item", label="pocket knife", outcome="activated"),
            perception=dict(kind="menu", basis="player_interpretation", control="vertical",
                rows=[dict(label="pocket knife", enabled=True)], selected=0, question=""), procedure=None)
        self.assertEqual(self.run_request(request("item", menu, "prompt"))["state"], "partial")
        for identity in ("item-dismiss", "inventory-dismiss"):
            intent = dict(kind="skill", skill_kind="menu", work_id=None,
                goal=dict(purpose="Return from current menu", label="Cancel", outcome="dismissed"),
                perception=dict(kind="dismissal", basis="player_interpretation", question="Current item menu"), procedure=None)
            result = self.run_request(request(identity, intent, "prompt"))
            self.assertEqual(result["state"], "partial", result)
        values = [r["intent"]["value"] for r in self.runtime._ledger.primitive_records()
                  if r["request_id"] in ("inventory", "item", "item-dismiss", "inventory-dismiss")]
        self.assertEqual(values, ["inventory", "CONFIRM", "UILIST.QUIT", "QUIT"])
        self.assertIsNone(self.runtime.status()["prompt_phase"])
        self.save()
        self.exit()
        result = self.run_request(self.lifecycle("finish", "finish"))
        self.assertEqual(result["result"]["normal_finish"]["disposition"], "stopped")
        self.runtime._ledger._verify(self.a)

    def test_create_save_new_child_exact_reload_and_retained_finish(self):
        self.create()
        original_ack = deepcopy(self.runtime._ledger.request("character-yes"))
        self.assertEqual(original_ack["state"], "unknown")
        self.save()
        self.exit()
        self.assertEqual(self.launch(identity="second-launch")["state"], "completed")
        self.stage = "load-world"
        self.assertEqual(self.run_request(self.lifecycle("load", "load"))["state"], "partial")
        world = self.runtime._current
        self.run_request(self.control("load-world", f"{self.a.scenario.world} (1)", parent="load"))
        raw = MissionCreationFixture.control(self, "load-entry", self.a.scenario.character, parent="load")
        raw["perception"] = None  # Native UILIST supplies the interpreted selection.
        selection = compose(self, raw, "lifecycle")
        self.assertEqual(self.run_request(selection)["state"], "unknown")
        self.observe("load-observe")
        adopted = self.finish_identity("load", world, 1)
        self.assertEqual(adopted["result"]["normal_adoption"]["saved_checkpoint_request_id"], "save-reconcile")
        # A second normal save uses fresh IDs; do not replay any unknown delivery.
        self.save_final()
        self.exit("final-exit")
        request = self.lifecycle("finish", "finish")
        before = self.runtime.status()["spent_inputs"]
        result = self.run_request(request)
        self.assertEqual(result["state"], "completed", result)
        self.assertEqual(self.runtime.status()["phase"], "stopped")
        self.assertEqual(self.runtime.status()["spent_inputs"], before)
        self.assertEqual(self.runtime._ledger.request("character-yes"), original_ack)
        self.runtime._ledger._verify(self.a)

    def save_final(self):
        self.run_request(self.lifecycle("final-save", "save"))
        result = self.run_request(self.control("final-save-yes", "Yes", parent="final-save", question="Save and quit?"))
        self.assertEqual(result["state"], "unknown", result)
        self.observe("final-save-observe-1")
        first = self.runtime._current
        self.observe("final-save-observe-2")
        result = self.run_request(self.lifecycle("final-save-reconcile", "save", parent="final-save",
            supports=(first.observation_id,)))
        self.assertEqual(result["state"], "completed", result)

    def test_missing_identity_scope_rejects_locally_then_direct_root_succeeds(self):
        finish_identity = self.finish_identity

        def inspect_scope(root, world_source, epoch=0):
            self.run_request(self.lifecycle("create-reconcile", parent=root))
            self.run_request(self.lifecycle("create-readmit", parent=root))
            raw = MissionCreationFixture.control(self, "wrong-root", "Character", kind="inspect", parent=None)
            phase_before = deepcopy(self.runtime.status()["lifecycle_phase"])
            wall_before = phase_before["remaining_limits"].pop("wall_seconds")
            before = deepcopy((phase_before, self.runtime._lease,
                self.runtime._ledger.request(root), self.runtime.status()["spent_inputs"], self.runtime._current))
            with self.assertRaises(ContractError):
                compose(self, raw, "new_root")
            phase_after = deepcopy(self.runtime.status()["lifecycle_phase"])
            wall_after = phase_after["remaining_limits"].pop("wall_seconds")
            # An asynchronous status publication may advance the countdown;
            # original deadlines, phase identity and all authority must agree.
            self.assertLessEqual(wall_after, wall_before)
            self.assertGreaterEqual(wall_after, 0)
            self.assertEqual((phase_after, self.runtime._lease,
                self.runtime._ledger.request(root), self.runtime.status()["spent_inputs"], self.runtime._current), before)
            # Continue identity inspection/adoption through unmodified guards.
            inspected = self.run_request(compose(self, {**raw, "request_id": "correct-root"}, "lifecycle"))
            self.assertEqual(inspected["state"], "completed", inspected)
            screen = self.runtime._current
            ids = [self.remember_identity("visible-world", "world", world_source, epoch),
                   self.remember_identity("visible-character", "character", screen, epoch)]
            self.run_request(self.control("return", "Cancel", parent=root))
            adopted = self.run_request(self.lifecycle("adopt", parent=root, claims=ids))
            self.assertEqual(adopted["state"], "completed", adopted)
            return adopted

        self.finish_identity = inspect_scope
        self.addCleanup(setattr, self, "finish_identity", finish_identity)
        self.create()

    def test_composed_menu_cannot_survive_user_pause(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        request = self.control("after-pause", "Create World")
        before = self.runtime.status()["spent_inputs"]
        self.runtime.pause("actual user Pause", cause="user")
        response = self.runtime.command(request)
        if response["status"] == "accepted":
            self.assertEqual(self.settled("after-pause")["state"], "blocked")
        else:
            self.assertEqual(response["status"], "rejected", response)
        self.assertEqual(self.runtime.status()["spent_inputs"], before)
        self.assertIsNone(self.runtime._lease)

    def test_explicit_setup_abort_remains_null_root_without_free_input(self):
        self.ready()
        self.run_request(self.lifecycle("setup"))
        original = deepcopy(self.runtime._ledger.primitive_records()[-1])
        before = self.runtime.status()["spent_inputs"]
        request = self.lifecycle("abort", "exit")
        self.assertIsNone(request["phase_id"])
        aborted = self.run_request(request)
        self.assertTrue(aborted["result"]["cleanup_requested"])
        self.assertNotIn("normal_exit", aborted["result"])
        self.assertEqual(self.runtime.status()["spent_inputs"], before)
        self.bridge.value["pause_origin"] = "host"  # Simulated native host sentinel.
        self.observe("abort-observe")
        self.exit("after-abort")
        finished = self.run_request(self.lifecycle("finish", "finish"))
        self.assertEqual(finished["result"]["normal_finish"]["disposition"], "stopped")
        self.assertEqual(self.runtime._ledger.primitive(original["logical_id"]), original)
        self.runtime._ledger._verify(self.a)

    def test_changed_pixels_after_composition_block_before_finalize(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        self.run_request(self.control("world-form", "Create World"))
        request = self.lifecycle("world-finalize", parent="create")
        source = self.runtime._current
        spent, delivered = self.runtime.status()["spent_inputs"], len(self.bridge.delivered)
        self.bridge.editor_text = "Changed visible world configuration"
        # Force the existing aged-source refresh branch; never patch its guard.
        with patch.object(self.runtime._store, "inspect_current_boundary", return_value=(source, False)):
            result = self.run_request(request)
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertEqual(len(self.bridge.delivered), delivered)
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.controller._mission_lease)


class ProducerActivityIntegrationTests(unittest.TestCase):
    setUp = activity.ActivityRecoveryTests.setUp
    wait = activity.ActivityRecoveryTests.wait
    request = activity.ActivityRecoveryTests.request
    result = activity.ActivityRecoveryTests.result
    settled = activity.ActivityRecoveryTests.settled
    start = activity.ActivityRecoveryTests.start
    control = activity.ActivityRecoveryTests.control
    begin = activity.ActivityRecoveryTests.begin
    prepare = activity.ActivityRecoveryTests.prepare
    return_normal = activity.ActivityRecoveryTests.return_normal

    def test_frameless_answer_retains_receipt_and_separate_resume_charge(self):
        self.prepare()
        original = deepcopy(self.runtime._ledger.request("rest-root"))
        for step in ("interrupt", "answer_interrupt", "resume"):
            goal = {**self.goal, "step": step}
            if step == "answer_interrupt":
                goal.update(answer="YES", interrupt_request_id=self.runtime._registered_activity.phase.interrupt_id)
            raw = self.control("activity", goal, phase_id="rest-root", request_id=step)
            scope = "prompt" if step == "interrupt" else "activity"
            checkpoint = self.runtime.status()[scope + "_phase"]["checkpoint_id"]
            ref = next(ref for ref in self.runtime._store.historical_references if ref.observation_id == checkpoint)
            source = dict(reference=ref.to_dict(), observation=self.runtime._store.observation(ref))
            request = compose(self, raw, scope, source=source)
            self.assertEqual(self.runtime.command(request)["status"], "accepted")
            result = self.settled(step)
            self.assertEqual(result["state"], "partial", result)
            if step == "answer_interrupt":
                receipt = deepcopy(self.runtime._ledger.primitive_records()[-1])
                self.assertIsNone(receipt["result"]["source_after"])
                self.assertFalse(receipt["result"]["control"]["result"]["state"]["frame_ok"])
                self.assertIsNone(self.runtime._lease)
        self.assertEqual(self.runtime.status()["spent_inputs"], 4)
        self.assertEqual(self.runtime._ledger.primitive_records()[-2], receipt)
        self.assertEqual(self.runtime._ledger.request("rest-root"), original)
        self.assertEqual(len([x for x in self.bridge.delivered if x["kind"] == "resume"]), self.resumes_at_start + 1)
        self.runtime._ledger._verify(self.a)
