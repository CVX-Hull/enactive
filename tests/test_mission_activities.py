"""Real mission accounting over synthetic activity observations, not CDDA proof."""
import copy
from dataclasses import replace
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from tests import test_mission_runtime as runtime_fixtures


class MissionActivityTests(unittest.TestCase):
    setUp = runtime_fixtures.MissionRuntimeTests.setUp
    wait = runtime_fixtures.MissionRuntimeTests.wait
    request = runtime_fixtures.MissionRuntimeTests.request
    result = runtime_fixtures.MissionRuntimeTests.result
    settled = runtime_fixtures.MissionRuntimeTests.settled
    start = runtime_fixtures.MissionRuntimeTests.start
    control = runtime_fixtures.MissionRuntimeTests.control

    def begin(self, **changes):
        self.bridge.value["actions"].append("sleep")
        self.start()
        self.normal = copy.deepcopy(self.bridge.value["scene"])
        self.finish = False
        def behavior(bridge, request):
            if request.get("action") == "sleep":
                bridge.value.update(category="DEFAULTMODE", scene=None, ui=None, actions=[])
                bridge.value["boundary"].update(kind="activity_poll", input_receiver=False, id="rest-poll",
                    recovery_operations=["request_interrupt"])
            elif request["kind"] == "observe" and bridge.value["boundary"]["kind"] == "activity_poll":
                bridge.value["revision"] += 1
                bridge.value["boundary"]["id"] = f'activity-{bridge.value["revision"]}'
                if self.finish:
                    scene = copy.deepcopy(self.normal)
                    scene["turn"] += self.finish
                    bridge.value.update(scene=scene, actions=["sleep"])
                    bridge.value["boundary"].update(kind="normal_play", input_receiver=True, recovery_operations=[])
            return True
        self.bridge.behavior = behavior
        self.goal = dict(operation="rest", target="rest in shelter", game_seconds=300,
                         interrupt_allowed=True, step="start", answer=None, interrupt_request_id=None)
        self.root = self.control("activity", self.goal, request_id="rest-root", **changes)
        self.assertEqual(self.runtime.command(self.root)["status"], "accepted")
        opened = self.settled("rest-root")
        self.assertEqual(opened["state"], "partial", opened)
        self.assertEqual(opened["result"]["phase"]["stage"], "activity_poll")
        return opened

    def poll(self, request_id="poll-1", **changes):
        req = self.control("activity", {**self.goal, "step": "poll"}, phase_id="rest-root",
                           request_id=request_id, **changes)
        self.assertEqual(self.runtime.command(req)["status"], "accepted")
        return self.settled(request_id)

    def test_poll_advances_only_the_owned_checkpoint_without_input_or_completion(self):
        self.begin()
        before = self.runtime._prompt_phase
        original = self.runtime._ledger.request("rest-root")
        delivered = len(self.bridge.delivered)
        result = self.poll()
        self.assertEqual(result["state"], "partial", result)
        self.assertEqual(result["result"]["phase"]["stage"], "activity_poll")
        self.assertTrue(result["result"]["verification_required"])
        self.assertNotEqual(self.runtime._prompt_phase.checkpoint, before.checkpoint)
        self.assertEqual(self.runtime._prompt_phase.game_anchor, before.game_anchor)
        self.assertEqual(self.runtime._ledger.request("rest-root"), original)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertEqual(len(self.bridge.delivered), delivered)
        self.assertEqual(result["deadline"], original["deadline"])
        self.assertIsNotNone(self.runtime._lease)

    def test_normal_return_closes_phase_but_does_not_claim_sleep_or_work_success(self):
        self.begin()
        self.finish = 20
        result = self.poll()
        self.assertEqual(result["state"], "partial", result)
        self.assertEqual(result["result"]["phase"]["stage"], "complete")
        self.assertTrue(result["result"]["verification_required"])
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertEqual(self.runtime._ledger.memory_records("work"), ())
        self.assertEqual(self.runtime.status()["metrics"]["game_seconds"], 20)

    def test_plain_observe_uses_same_owned_poll_path_and_can_report_normal_return(self):
        self.begin()
        self.assertEqual(self.runtime.command(self.request("observe", request_id="observe-poll"))["status"], "accepted")
        result = self.settled("observe-poll")
        self.assertEqual(result["result"]["phase"]["stage"], "activity_poll")
        self.finish = 15
        self.assertEqual(self.runtime.command(self.request("observe", request_id="observe-return"))["status"], "accepted")
        result = self.settled("observe-return")
        self.assertEqual(result["result"]["phase"]["stage"], "complete")
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

    def test_poll_can_retain_native_output_menu_without_inventing_stored_inventory(self):
        self.begin()
        behavior = self.bridge.behavior
        def output(bridge, request):
            behavior(bridge, request)
            if request["kind"] == "observe":
                bridge.value.update(category="YESNO", actions=["YES", "NO"])
                bridge.value["boundary"].update(kind="menu", input_receiver=True, id="output-question", recovery_operations=[])
            return True
        self.bridge.behavior = output
        result = self.poll()
        self.assertEqual(result["state"], "partial", result)
        self.assertEqual(result["result"]["phase"]["stage"], "awaiting_control")
        self.assertIn(self.runtime._current.observation_id, self.runtime._bindings)
        self.assertFalse([r for r in self.runtime._ledger.memory_records("claim")
                          if r["entry"]["key"]["property"] == "supply"])

    def distraction_answer(self, label):
        self.begin()
        original = self.runtime._ledger.request("rest-root")
        behavior = self.bridge.behavior
        shown = False

        def distracted(bridge, request):
            nonlocal shown
            behavior(bridge, request)
            if request.get("action") in ("YES", "NO"):
                bridge.value.update(category="DEFAULTMODE", ui=None)
                if request["action"] == "YES":
                    bridge.value.update(scene=copy.deepcopy(self.normal), actions=["sleep"])
                    bridge.value["boundary"].update(kind="normal_play", input_receiver=True, id="cancelled-rest", recovery_operations=[])
                else:
                    bridge.value.update(scene=None, actions=[])
                    bridge.value["boundary"].update(kind="activity_poll", input_receiver=False, id="continued-rest",
                        recovery_operations=["request_interrupt"])
            elif request["kind"] == "observe" and not shown:
                shown = True
                bridge.value.update(category="CANCEL_ACTIVITY_OR_IGNORE_QUERY", scene=None, ui=None,
                    actions=["YES", "NO", "MANAGER", "IGNORE", "LEFT", "RIGHT"])
                bridge.value["boundary"].update(kind="menu", input_receiver=True, id="sound-question", recovery_operations=[])
            return True

        self.bridge.behavior = distracted
        question = self.poll("sound-observation")
        self.assertEqual(question["result"]["phase"]["stage"], "awaiting_control")
        source = self.runtime.status()["current_source"]
        view = dict(kind="confirmation", basis="player_interpretation", source_id=source["observation_id"],
                    question="Heard blam! Stop waiting?")
        answer = self.control("menu", dict(purpose="Assess interrupted wait", label=label, outcome="activated"),
                              phase_id="rest-root", perception=view, request_id="sound-answer")
        self.assertEqual(self.runtime.command(answer)["status"], "accepted")
        result = self.settled("sound-answer")
        self.assertEqual(result["state"], "partial", result)
        self.assertTrue(result["result"]["verification_required"])
        self.assertEqual(result["result"]["proposals"], 1)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertEqual(self.runtime._ledger.request("rest-root"), original)
        self.assertEqual(result["deadline"], original["deadline"])
        self.assertEqual(self.runtime._ledger.memory_records("work"), ())
        delivered = len(self.bridge.delivered)
        self.assertEqual(self.runtime.command(answer)["operation"]["result"], result["result"])
        self.assertEqual(len(self.bridge.delivered), delivered)
        return result

    def test_owned_distraction_yes_returns_normal_without_claiming_rest(self):
        result = self.distraction_answer("Yes")
        self.assertEqual(result["result"]["phase"]["stage"], "complete")
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["metrics"]["game_seconds"], 0)

    def test_owned_distraction_no_keeps_poll_under_original_activity_root(self):
        result = self.distraction_answer("No")
        self.assertEqual(result["result"]["phase"]["stage"], "activity_poll")
        self.assertEqual(self.runtime._prompt_phase.root_id, "rest-root")
        # No new normal endpoint was observed; retain the prior measured cost,
        # without turning the selected wait duration into credited rest.
        self.assertEqual(self.runtime.status()["metrics"]["game_seconds"], 0)

    def test_local_game_overshoot_keeps_authority_costs_and_allows_new_intent(self):
        for typed in (False, True):
            with self.subTest(typed=typed):
                case = type(self)()
                case.setUp()
                try:
                    case.begin(limits=dict(primitives=8, wall_seconds=120, game_seconds=300))
                    root = case.runtime._ledger.request("rest-root")
                    lease = case.runtime._lease
                    delivered = len(case.bridge.delivered)
                    case.finish = 301
                    if typed:
                        result = case.poll()
                    else:
                        case.runtime.command(case.request("observe", request_id="observe-overshoot"))
                        result = case.settled("observe-overshoot")
                    self.assertEqual(result["result"]["macro_exhausted"], "game_seconds", result)
                    self.assertNotIn("budget_stop", result["result"])
                    self.assertEqual(result["result"]["phase"]["stage"], "complete")
                    self.assertEqual(case.runtime.status()["phase"], "active")
                    self.assertIs(case.runtime._lease, lease)
                    self.assertIsNone(case.runtime._prompt_phase)
                    self.assertEqual(case.runtime._ledger.request("rest-root"), root)
                    self.assertEqual(case.runtime.status()["metrics"]["game_seconds"], 301)
                    self.assertEqual(case.runtime.status()["spent_inputs"], 1)
                    self.assertEqual(len(case.bridge.delivered), delivered)
                    self.assertEqual(case.runtime._ledger.primitive_records()[-1]["state"], "returned")
                    # A genuinely new intent, not a replay or extension of the old root.
                    case.runtime.command(case.control("activity", case.goal, request_id="new-root"))
                    self.assertEqual(case.settled("new-root")["state"], "partial")
                    self.assertEqual(case.runtime._lease.epoch, lease.epoch)
                    self.assertEqual(case.runtime._lease.actor_id, lease.actor_id)
                    self.assertEqual(case.runtime.status()["spent_inputs"], 2)
                finally:
                    case.doCleanups()

    def test_exact_local_game_limit_is_not_an_overshoot(self):
        self.begin(limits=dict(primitives=8, wall_seconds=120, game_seconds=300))
        self.finish = 300
        result = self.poll()
        self.assertNotIn("macro_exhausted", result["result"])
        self.assertIsNotNone(self.runtime._lease)
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["metrics"]["game_seconds"], 300)

    def test_smaller_poll_child_limit_does_not_revoke_healthy_root(self):
        self.begin(limits=dict(primitives=8, wall_seconds=120, game_seconds=1200))
        root = self.runtime._ledger.request("rest-root")
        self.finish = 301
        result = self.poll(limits=dict(primitives=8, wall_seconds=120, game_seconds=300))
        self.assertEqual(result["result"]["macro_exhausted"], "game_seconds", result)
        self.assertEqual(self.runtime._ledger.request("rest-root"), root)
        self.assertEqual(self.runtime.status()["metrics"]["game_seconds"], 301)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertIsNotNone(self.runtime._lease)

    def test_global_game_cap_wins_simultaneous_local_overshoot(self):
        self.a = replace(self.a, limits=replace(self.a.limits, game_seconds=301))
        self.begin(limits=dict(primitives=8, wall_seconds=120, game_seconds=300))
        self.finish = 301
        result = self.poll()
        self.assertEqual(result["state"], "blocked", result)
        self.assertNotIn("macro_exhausted", result["result"])
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertEqual(self.runtime.status()["metrics"]["game_seconds"], 301)

    def test_local_overshoot_cannot_mask_input_reserve(self):
        self.a = replace(self.a, limits=replace(self.a.limits, inputs=2, primitive_mappings=2),
                         cleanup_reserve=replace(self.a.cleanup_reserve, inputs=1))
        self.begin(limits=dict(primitives=8, wall_seconds=120, game_seconds=300))
        self.finish = 301
        delivered = len(self.bridge.delivered)
        result = self.poll()
        self.assertEqual(result["state"], "blocked", result)
        self.assertNotIn("macro_exhausted", result["result"])
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(len(self.bridge.delivered), delivered)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

    def test_local_overshoot_cannot_mask_corrupt_anchor_or_checkpoint(self):
        for which in ("game_anchor", "checkpoint"):
            with self.subTest(which=which):
                case = type(self)()
                case.setUp()
                try:
                    case.begin(limits=dict(primitives=8, wall_seconds=120, game_seconds=300))
                    case.finish = 301
                    req = case.control("activity", {**case.goal, "step": "poll"},
                        phase_id="rest-root", request_id="corrupt-evidence-poll")
                    retained = Path(getattr(case.runtime._prompt_phase, which).frame_path)
                    retained.chmod(0o600)
                    retained.write_bytes(b"corrupt retained evidence")
                    self.assertEqual(case.runtime.command(req)["status"], "accepted")
                    result = case.settled(req["request_id"])
                    self.assertEqual(result["state"], "blocked", result)
                    self.assertNotIn("macro_exhausted", result["result"])
                    self.assertIsNone(case.runtime._lease)
                    self.assertEqual(case.runtime.status()["spent_inputs"], 1)
                finally:
                    case.doCleanups()

    def test_local_overshoot_cannot_mask_changed_session_takeover_or_clock(self):
        for fault in ("session", "takeover", "clock"):
            with self.subTest(fault=fault):
                case = type(self)()
                case.setUp()
                try:
                    case.begin(limits=dict(primitives=8, wall_seconds=120, game_seconds=300))
                    case.finish = -1 if fault == "clock" else 301
                    behavior = case.bridge.behavior
                    def changed(bridge, request):
                        result = behavior(bridge, request)
                        if request["kind"] == "observe":
                            if fault == "session":
                                bridge.value["session"] = "unexplained-session"
                            elif fault == "takeover":
                                bridge.value["takeover_generation"] += 1
                        return result
                    case.bridge.behavior = changed
                    result = case.poll()
                    self.assertEqual(result["state"], "blocked", result)
                    self.assertNotIn("macro_exhausted", result["result"])
                    self.assertIsNone(case.runtime._lease)
                    self.assertEqual(case.runtime.status()["spent_inputs"], 1)
                finally:
                    case.doCleanups()

    def test_after_capture_local_overshoot_cannot_hide_wall_reserve_or_prepared_input(self):
        for fault in ("wall_reserve", "prepared_input"):
            with self.subTest(fault=fault):
                case = type(self)()
                case.setUp()
                try:
                    case.begin(limits=dict(primitives=8, wall_seconds=120, game_seconds=300))
                    case.finish = 301
                    pending = case.control("activity", {**case.goal, "step": "poll"},
                        phase_id="rest-root", request_id="synthetic-competing-request")
                    deliveries = len(case.bridge.delivered)
                    observe = case.runtime._observe_native
                    wall = case.runtime._wall
                    offset = 0
                    def concurrent_fault(work, **kwargs):
                        nonlocal offset
                        value = observe(work, **kwargs)
                        if fault == "wall_reserve":
                            offset = (case.runtime._mission_deadline
                                - case.a.cleanup_reserve.wall_seconds - wall() + .01)
                        else:
                            # A real charged ledger preparation, with no native
                            # publication; it must not be hidden by local expiry.
                            ledger = case.runtime._ledger
                            ledger.begin_request(pending, now=wall())
                            intent = copy.deepcopy(ledger.primitive_records()[0]["intent"])
                            intent.update(source_before=pending["sources"][0], preflight_source=pending["sources"][0],
                                revalidation=None, input_observation=None)
                            ledger.prepare_primitive(pending["request_id"], "synthetic-unsettled-input",
                                intent, now=wall())
                        return value
                    with patch.object(case.runtime, "_wall", side_effect=lambda: wall() + offset), \
                            patch.object(case.runtime, "_observe_native", side_effect=concurrent_fault):
                        result = case.poll()
                        self.assertEqual(result["state"], "blocked", result)
                        self.assertNotIn("macro_exhausted", result["result"])
                        self.assertIn("ending reserve" if fault == "wall_reserve" else "Unsettled input",
                            result["result"]["reason"])
                        self.assertIsNone(case.runtime._lease)
                        self.assertEqual(case.runtime.status()["spent_inputs"],
                            1 if fault == "wall_reserve" else 2)
                        self.assertEqual(len(case.bridge.delivered), deliveries)
                finally:
                    case.doCleanups()

    def test_user_pause_during_poll_cannot_publish_a_phase_or_lease(self):
        self.begin()
        observe = self.runtime._observe_native
        def paused(work, **kwargs):
            value = observe(work, **kwargs)
            self.runtime.pause("user during poll", cause="user")
            return value
        with patch.object(self.runtime, "_observe_native", side_effect=paused):
            result = self.poll()
        self.assertEqual(result["state"], "paused", result)
        self.assertEqual(self.runtime.status()["pause_cause"], "user")
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

    def test_poll_command_queue_uses_original_root_deadline_without_renewal(self):
        self.begin()
        deadline = self.runtime._ledger.request("rest-root")["deadline"]
        before = len(self.bridge.requests)
        self.controller.command_lock.acquire()
        started = time.monotonic()
        try:
            with patch.object(self.runtime, "_wall", return_value=deadline - 0.05):
                result = self.poll()
        finally:
            self.controller.command_lock.release()
        self.assertLess(time.monotonic() - started, 0.6)
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(len(self.bridge.requests), before)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)


if __name__ == "__main__":
    unittest.main()
