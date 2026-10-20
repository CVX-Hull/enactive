"""Source integration with file transport; no native gameplay/autonomy claim."""
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


class VisibleBridge(FakeBridge):
    def __init__(self, controller, **options):
        super().__init__(controller, **options)
        self.frames = 0
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
        (self.bridge / value["frame"]).write_bytes(b"\x89PNG\r\n\x1a\n" + str(value["scene"]).encode())
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
        data = dict(schema="mission/1", kind=kind, request_id=kind + "-1",
                    mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"])
        data.update(changes)
        return data

    def result(self, identity):
        out = self.runtime.command(dict(schema="mission/1", kind="result",
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
        req = dict(schema="mission/1", kind="start", request_id="start-1", admission=self.a.to_dict())
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
        absent = self.runtime.command(dict(schema="mission/1", kind="result", mission_id=self.a.mission_id,
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
        work = {"schema": "campaign-memory/1", "record_type": "Work", "id": "water-pending",
            "intent": "Treat water and verify storage", "scope": scope, "stage": "pending-storage",
            "progress": None, "available": [], "committed": [],
            "predicted_output": [{"subject": "clean-water", "quantity": 2, "unit": "charges", "coverage_id": "kettle"}],
            "observed_output": [], "unresolved_effects": [], "sources": [],
            "next_verification": "Inspect actual water and storage", "status": "planned"}
        req = self.request("remember", request_id="pending-work", entry_type="work", entry=work)
        self.runtime.command(req)
        self.assertEqual(self.settled("pending-work")["state"], "completed")
        Path(second["frame_path"]).unlink()
        context_request = dict(schema="mission/1", kind="context", mission_id=self.a.mission_id,
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
        out = self.runtime.command(dict(schema="mission/1", kind="context", mission_id=self.a.mission_id,
            scope=scope, query="water", max_bytes=32768))
        packet = out["context"]["packet"]
        decision = dict(schema="campaign-memory/1", record_type="Decision", id="decision-1",
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
        release.set()
        op = self.settled(request["request_id"])
        self.assertEqual(op["state"], "unknown", op)
        self.assertEqual(self.runtime.status()["epoch"], 1)
        self.assertEqual(self.runtime.status()["pause_cause"], "user")
        self.assertEqual(self.runtime.status()["reason"], "User Pause before lost ACK")

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
        req = dict(schema="mission/1", kind="start", request_id="start-1", admission=self.a.to_dict())
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

    def test_missing_native_start_stays_admitted_without_launch(self):
        self.bridge.__exit__(None, None, None)
        req = dict(schema="mission/1", kind="start", request_id="start-1", admission=self.a.to_dict())
        self.runtime.command(req)
        op = self.settled("start-1")
        self.assertTrue(op["result"]["lifecycle_needed"])
        self.assertEqual(self.runtime.status()["phase"], "admitted")
        self.assertIsNone(self.runtime.status()["current_source"])
        self.assertEqual(self.bridge.delivered, [])

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
            start = dict(schema="mission/1", kind="start", request_id="start-1", admission=self.a.to_dict())
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
        request = dict(schema="mission/1", kind="context", mission_id=self.a.mission_id,
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
        req = dict(schema="mission/1", kind="context", mission_id=self.a.mission_id,
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

    def test_no_fake_handoff_lifecycle_or_finish_and_stop_revokes(self):
        self.start()
        for req in [self.request("handoff", checkpoint_ids=[], successor_role="player"),
                    self.request("lifecycle", operation="launch", world=self.a.scenario.world,
                                 character=self.a.scenario.character, sources=[], expected_session=None,
                                 expected_revision=None, expected_boundary_id=None,
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
        response = self.runtime.command(dict(schema="mission/1", kind="start", request_id="start-1", admission=self.a.to_dict()))
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
