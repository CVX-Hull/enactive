"""Activity/mission composition over synthetic files; never native qualification."""
from contextlib import closing
import copy
import json
import sqlite3
import threading
import time
import unittest
from unittest.mock import patch

from harness.controller import ControlError, atomic_json, read_json, validate_control_request
from harness.gameplay.mission_ledger import LedgerError, MissionLedger
from tests import test_mission_activities as activity_fixtures


class ActivityControls:
    """Controlled activity effects over the same file transport as the runtime."""
    def __init__(self, case):
        self.case = case
        self.requests = []
        self.failures = []
        self.closed = threading.Event()
        self.publish = True
        self.after_commit = None
        self.thread = threading.Thread(target=self.run, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.closed.set()
        self.thread.join(2)
        if self.thread.is_alive():
            raise AssertionError("Activity control fixture did not stop")
        if self.failures:
            raise self.failures[0]

    def run(self):
        case = self.case
        bridge = case.controller.bridge
        try:
            while not self.closed.wait(0.003):
                try:
                    (bridge / "control.json").rename(bridge / "control-claimed.json")
                except FileNotFoundError:
                    continue
                req = read_json(bridge / "control-claimed.json")
                validate_control_request(req)
                self.requests.append(req)
                value = case.bridge.value
                value.update(paused=True, pause_origin="recovery", revision=value["revision"] + 1)
                value["boundary"]["control_generation"] = req["control_generation"] + 1
                if req["kind"] == "request_interrupt":
                    value.update(category="YESNO", scene=None, actions=["YES", "NO"])
                    value["boundary"].update(kind="interrupt_confirmation", id="owned-interrupt",
                        recovery_operations=["answer_interrupt"], interrupt_request_id=req["id"])
                    case.bridge.publish(value)
                    native = read_json(bridge / "state.json")
                    status = "prompt_opened"
                else:
                    native = copy.deepcopy(value)
                    native.update(frame_ok=False, frame="")
                    if req["choice"] == "YES":
                        case.return_normal()
                    else:
                        value.update(category="DEFAULTMODE", scene=None, actions=[])
                        value["boundary"].update(kind="activity_poll", id="continued-poll",
                            recovery_operations=["request_interrupt"], interrupt_request_id=None)
                    status = "answer_delivered"
                (bridge / "control-claimed.json").unlink()
                if self.after_commit:
                    self.after_commit(req)
                if self.publish:
                    atomic_json(bridge / "control-response.json", dict(protocol=4, id=req["id"],
                        status=status, error="", state=native))
        except BaseException as exc:
            self.failures.append(exc)


class ActivityRecoveryTests(unittest.TestCase):
    setUp = activity_fixtures.MissionActivityTests.setUp
    wait = activity_fixtures.MissionActivityTests.wait
    request = activity_fixtures.MissionActivityTests.request
    result = activity_fixtures.MissionActivityTests.result
    settled = activity_fixtures.MissionActivityTests.settled
    start = activity_fixtures.MissionActivityTests.start
    control = activity_fixtures.MissionActivityTests.control
    begin = activity_fixtures.MissionActivityTests.begin

    def prepare(self, **changes):
        self.begin(**changes)
        behavior = self.bridge.behavior
        def stable_paused_poll(bridge, request):
            if (request["kind"] == "observe" and (self.controller.bridge / "pause").exists()
                    and bridge.value["boundary"]["kind"] == "activity_poll"):
                return True
            return behavior(bridge, request)
        self.bridge.behavior = stable_paused_poll
        self.resumes_at_start = len([x for x in self.bridge.delivered if x["kind"] == "resume"])
        self.controls = self.enterContext(ActivityControls(self))

    def return_normal(self):
        self.bridge.value.update(category="DEFAULTMODE", scene=copy.deepcopy(self.normal),
                                 actions=["sleep", "UP", "DOWN", "LEFT", "RIGHT"])
        self.bridge.value["scene"]["turn"] += 10
        self.bridge.value["revision"] += 1
        self.bridge.value["boundary"].update(kind="normal_play", id="after-rest",
            recovery_operations=[], interrupt_request_id=None)

    def recovery(self, step, identity=None, **changes):
        goal = {**self.goal, "step": step}
        if step == "answer_interrupt":
            goal.update(answer="YES", interrupt_request_id=self.runtime._registered_activity.phase.interrupt_id)
        goal.update(changes.pop("goal_changes", {}))
        req = self.control("activity", goal, phase_id="rest-root", request_id=identity or step, **changes)
        response = self.runtime.command(req)
        self.assertEqual(response["status"], "accepted", response)
        return self.settled(req["request_id"])

    def test_yes_ack_without_frame_then_separate_charged_resume(self):
        self.prepare()
        original = self.runtime._ledger.request("rest-root")
        operator, epoch = self.runtime._operator_mark(), self.runtime.status()["epoch"]
        result = self.recovery("interrupt")
        self.assertEqual(result["state"], "partial", result)
        self.assertEqual(result["result"]["phase"]["stage"], "interrupt_confirmation")
        self.assertIsNone(self.runtime._lease)
        summary = self.runtime.status()["activity_phase"]
        self.assertEqual(summary["origin_request_id"], "rest-root")
        self.assertEqual(summary["stage"], "interrupt_confirmation")
        self.assertFalse(summary["answered"])
        self.assertFalse(summary["grants_authority"])
        result = self.recovery("answer_interrupt")
        self.assertEqual(result["state"], "partial", result)
        self.assertEqual(result["result"]["phase"]["stage"], "awaiting_readmission")
        self.assertEqual(self.runtime.status()["activity_phase"]["stage"], "awaiting_readmission")
        primitives = self.runtime._ledger.primitive_records()
        self.assertEqual([x["intent"]["kind"] for x in primitives], ["action", "request_interrupt", "answer_interrupt"])
        answer = primitives[-1]
        self.assertEqual(answer["state"], "returned")
        self.assertIsNone(answer["result"]["source_after"])
        self.assertFalse(answer["result"]["control"]["result"]["state"]["frame_ok"])
        self.assertEqual(answer["result"]["control"]["result"]["status"], "answer_delivered")
        self.assertEqual(self.runtime._ledger.request("rest-root"), original)
        self.assertEqual(self.runtime._operator_mark(), operator)
        self.assertEqual(self.runtime.status()["epoch"], epoch)
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)
        self.assertIsNone(self.runtime._lease)
        result = self.recovery("resume")
        self.assertEqual(result["state"], "partial", result)
        self.assertEqual(result["result"]["phase"]["stage"], "complete")
        self.assertIsNone(self.runtime._registered_activity.phase)
        self.assertIsNone(self.runtime.status()["activity_phase"])
        self.assertIsNotNone(self.runtime._lease)
        self.assertEqual(self.runtime.status()["spent_inputs"], 4)
        self.assertEqual(len([x for x in self.bridge.delivered if x["kind"] == "resume"]), self.resumes_at_start + 1)
        self.assertEqual(self.runtime._ledger.memory_records("work"), ())
        self.runtime._ledger._verify(self.a)

    def test_no_keeps_activity_running_paused_and_observe_never_resumes(self):
        self.prepare()
        self.recovery("interrupt")
        result = self.recovery("answer_interrupt", goal_changes={"answer": "NO"})
        self.assertEqual(result["state"], "partial", result)
        self.assertEqual(result["result"]["phase"]["stage"], "activity_poll")
        self.assertIsNone(self.runtime._lease)
        delivered = len(self.bridge.delivered)
        req = self.request("observe", request_id="paused-poll")
        self.assertEqual(self.runtime.command(req)["status"], "accepted")
        result = self.settled("paused-poll")
        self.assertEqual(result["result"]["phase"]["stage"], "activity_poll")
        self.assertEqual(len(self.bridge.delivered), delivered)
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)
        self.return_normal()
        self.assertEqual(self.runtime.command(self.request("observe", request_id="natural-return"))["status"], "accepted")
        result = self.settled("natural-return")
        self.assertEqual(result["result"]["phase"]["stage"], "awaiting_readmission")
        self.assertEqual(self.recovery("resume")["state"], "partial")
        self.runtime._ledger._verify(self.a)

    def test_resume_at_poll_is_refused_without_an_input_or_new_lease(self):
        self.prepare()
        self.recovery("interrupt")
        self.recovery("answer_interrupt", goal_changes={"answer": "NO"})
        count = len(self.bridge.requests)
        result = self.recovery("resume")
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(len(self.bridge.requests), count)
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)
        self.assertIsNone(self.runtime._lease)

    def test_wrong_interrupt_owner_cannot_answer(self):
        self.prepare()
        self.recovery("interrupt")
        result = self.recovery("answer_interrupt", goal_changes={"interrupt_request_id": "wrong-owner"})
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(len(self.controls.requests), 1)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)

    def test_root_input_ceiling_includes_control_and_separate_resume(self):
        self.prepare(limits=dict(primitives=3, wall_seconds=120, game_seconds=300))
        self.recovery("interrupt")
        self.recovery("answer_interrupt")
        result = self.recovery("resume")
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)
        self.assertEqual(len([x for x in self.bridge.delivered if x["kind"] == "resume"]), self.resumes_at_start)
        self.runtime._ledger._verify(self.a)

    def test_user_pause_after_control_publication_retains_delivery_without_continuation(self):
        self.prepare()
        self.controls.after_commit = lambda _: self.runtime.pause("user at delivered interrupt")
        result = self.recovery("interrupt")
        self.assertEqual(result["state"], "paused", result)
        self.assertEqual(self.runtime.status()["pause_cause"], "user")
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._registered_activity.phase)
        self.assertIsNone(self.runtime.status()["activity_phase"])
        self.assertEqual(len(self.controls.requests), 1)
        row = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual(row["state"], "returned")
        self.assertEqual(row["result"]["control"]["result"]["status"], "prompt_opened")

    def test_pause_during_summary_build_cannot_republish_old_activity_or_lease(self):
        self.prepare()
        self.recovery("interrupt")
        summary = self.runtime._registered_activity.summary
        publish = self.runtime._publish
        interrupted, snapshots = [], []
        def pause_after_summary():
            value = summary()
            active = self.runtime._active
            # The preceding interrupt's final cache publication may still be
            # running after its result is readable. Inject only in this admitted
            # Observe, not that earlier publication before Observe can be admitted.
            if (value is not None and not interrupted and active is not None
                    and active.request["request_id"] == "summary-race"):
                interrupted.append(True)
                self.runtime.pause("Pause between summary build and cache publication")
            return value
        def capture_publication():
            publish()
            snapshots.append(self.runtime.status())
        count = len(self.bridge.delivered)
        with patch.object(self.runtime._registered_activity, "summary", side_effect=pause_after_summary), \
             patch.object(self.runtime, "_publish", side_effect=capture_publication):
            req = self.request("observe", request_id="summary-race")
            self.runtime.command(req)
            operation = self.settled(req["request_id"])
            self.assertEqual(operation["state"], "paused")
        self.assertTrue(interrupted)
        paused = [snapshot for snapshot in snapshots if snapshot["phase"] == "paused"]
        self.assertTrue(paused)
        for snapshot in paused:
            for key in ("activity_phase", "lease_owner", "prompt_phase", "lifecycle_phase"):
                self.assertIsNone(snapshot[key], key)
        self.assertEqual(len(self.bridge.delivered), count)

    def test_control_timeout_remains_unknown_and_same_request_never_replays(self):
        self.prepare()
        self.controls.publish = False
        req = self.control("activity", {**self.goal, "step": "interrupt"}, phase_id="rest-root", request_id="lost-control")
        self.assertEqual(self.runtime.command(req)["status"], "accepted")
        result = self.settled("lost-control")
        self.assertEqual(result["state"], "unknown", result)
        row = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual(row["state"], "unknown")
        self.assertIsNotNone(row["native_id"])
        self.assertIsNone(row["effect"])
        self.assertEqual(self.runtime.command(req)["operation"]["state"], "unknown")
        self.assertEqual(len(self.controls.requests), 1)
        self.assertIsNone(self.runtime._registered_activity.phase)

    def test_natural_completion_before_interrupt_publication_costs_no_control(self):
        self.prepare()
        stop = self.controller.stop_input
        def finish_during_stop():
            value = stop()
            self.return_normal()
            return value
        with patch.object(self.controller, "stop_input", side_effect=finish_during_stop):
            result = self.recovery("interrupt")
        self.assertEqual(result["state"], "partial", result)
        self.assertEqual(result["result"]["phase"]["stage"], "awaiting_readmission")
        self.assertEqual(self.controls.requests, [])
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertEqual(self.recovery("resume")["state"], "partial")
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)

    def test_no_then_new_interrupt_uses_a_new_owner_with_original_root_limits(self):
        self.prepare()
        self.recovery("interrupt")
        old_owner = self.runtime._registered_activity.phase.interrupt_id
        self.recovery("answer_interrupt", goal_changes={"answer": "NO"})
        self.assertIsNone(self.runtime._registered_activity.phase.interrupt_id)
        result = self.recovery("interrupt", identity="interrupt-again")
        self.assertEqual(result["state"], "partial", result)
        self.assertNotEqual(self.runtime._registered_activity.phase.interrupt_id, old_owner)
        self.assertEqual(self.recovery("answer_interrupt", identity="answer-again")["state"], "partial")
        self.assertEqual(self.recovery("resume")["state"], "partial")
        self.assertEqual(self.runtime.status()["spent_inputs"], 6)
        self.runtime._ledger._verify(self.a)

    def test_missing_after_observation_does_not_rewrite_known_answer_ack(self):
        self.prepare()
        self.recovery("interrupt")
        observed = self.runtime._observe_native
        def unavailable_after_answer(work, **kwargs):
            if len(self.controls.requests) == 2:
                raise ControlError("Controlled missing after-frame")
            return observed(work, **kwargs)
        with patch.object(self.runtime, "_observe_native", side_effect=unavailable_after_answer):
            result = self.recovery("answer_interrupt")
        self.assertEqual(result["state"], "blocked", result)
        row = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual(row["state"], "returned")
        self.assertIsNotNone(row["native_id"])
        self.assertIsNone(row["result"]["source_after"])
        self.assertEqual(row["result"]["control"]["result"]["status"], "answer_delivered")
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._registered_activity.phase)
        self.runtime._ledger._verify(self.a)

    def test_publication_bookkeeping_failure_settles_known_ack_atomically(self):
        self.prepare()
        with patch.object(self.runtime._ledger, "published", side_effect=OSError("one failed publication transaction")):
            result = self.recovery("interrupt")
        self.assertEqual(result["state"], "partial", result)
        row = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual(row["state"], "returned")
        self.assertEqual(row["native_id"], self.controls.requests[-1]["id"])
        self.assertEqual(row["result"]["control"]["result"]["status"], "prompt_opened")
        self.assertEqual(len(self.controls.requests), 1)
        self.runtime._ledger._verify(self.a)

    def test_controller_post_ack_storage_fault_blocks_observation_continuation(self):
        self.prepare()
        with patch.object(self.controller, "_finish_mission_receipt", side_effect=OSError("controlled terminal retention fault")):
            result = self.recovery("interrupt")
        self.assertEqual(result["state"], "blocked", result)
        row = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual(row["state"], "returned")
        self.assertEqual(row["result"]["control"]["result"]["status"], "prompt_opened")
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertIsNone(self.runtime._registered_activity.phase)
        self.assertIsNone(self.runtime._lease)
        self.runtime._ledger._verify(self.a)

    def test_user_pause_during_preflight_prevents_control_publication(self):
        self.prepare()
        prepare = self.runtime._ledger.prepare_primitive
        def paused(*args, **kwargs):
            result = prepare(*args, **kwargs)
            self.runtime.pause("user during activity preflight")
            return result
        with patch.object(self.runtime._ledger, "prepare_primitive", side_effect=paused):
            result = self.recovery("interrupt")
        self.assertEqual(result["state"], "paused", result)
        self.assertEqual(self.controls.requests, [])
        row = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual(row["state"], "not_dispatched")
        self.assertIsNone(row["native_id"])
        self.assertEqual(self.runtime.status()["pause_cause"], "user")
        self.assertIsNone(self.runtime._registered_activity.phase)

    def test_original_root_deadline_bounds_paused_observation_queue(self):
        self.prepare()
        deadline = self.runtime._ledger.request("rest-root")["deadline"]
        self.controller.command_lock.acquire()
        started = time.monotonic()
        try:
            with patch.object(self.runtime, "_wall", return_value=deadline - 0.05):
                result = self.recovery("interrupt")
        finally:
            self.controller.command_lock.release()
        self.assertLess(time.monotonic() - started, 0.6)
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(self.controls.requests, [])
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertIsNone(self.runtime._registered_activity.phase)

    def test_expiry_during_resume_lease_acquisition_revokes_without_further_input(self):
        self.prepare()
        self.recovery("interrupt")
        self.recovery("answer_interrupt")
        original_wall = self.runtime._wall
        deadline = self.runtime._ledger.request("rest-root")["deadline"]
        offset = [0]
        acquire = self.controller.acquire_mission
        def acquire_at_deadline(*args, **kwargs):
            result = acquire(*args, **kwargs)
            offset[0] = deadline + 1 - original_wall()
            return result
        with patch.object(self.runtime, "_wall", side_effect=lambda: original_wall() + offset[0]), \
                patch.object(self.controller, "acquire_mission", side_effect=acquire_at_deadline):
            result = self.recovery("resume")
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(self.runtime._ledger.primitive_records()[-1]["state"], "returned")
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.controller._mission_lease)
        self.assertIsNone(self.runtime._registered_activity.phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], 4)

    def test_reopen_rejects_changed_terminal_interrupt_owner(self):
        self.prepare()
        self.recovery("interrupt")
        self.runtime._ledger._verify(self.a)
        row = self.runtime._ledger.primitive_records()[-1]
        row["result"]["control"]["result"]["state"]["boundary"]["interrupt_request_id"] = "other-owner"
        path, database = self.runtime._ledger.directory, self.runtime._ledger.path
        self.runtime.close()
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("UPDATE primitives SET result=? WHERE id=?", (
                json.dumps(row["result"], sort_keys=True, separators=(",", ":")), row["logical_id"]))
        with self.assertRaisesRegex(LedgerError, "exact returned owner"):
            MissionLedger(path, admission=self.a, now=time.time())

    def test_reopen_restores_costs_and_history_without_activity_authority(self):
        self.prepare()
        self.recovery("interrupt")
        self.runtime._ledger._verify(self.a)
        path = self.runtime._ledger.directory
        self.runtime.close()
        with MissionLedger(path, admission=self.a, now=time.time()) as ledger:
            self.assertEqual(ledger.snapshot(now=time.time())["spent_inputs"], 2)
            self.assertEqual(ledger.snapshot(now=time.time())["phase"], "paused")
            self.assertEqual(ledger.primitive_records()[-1]["state"], "returned")


if __name__ == "__main__":
    unittest.main()
