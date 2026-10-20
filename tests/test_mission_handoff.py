"""Player replacement through actual controller/SQLite/archive, synthetic UI only."""
import copy
from pathlib import Path
import unittest
import time
import threading
from unittest.mock import patch

from harness.mission_runtime import MissionRuntime
from tests.test_mission_creation import MissionCreationFixture


class MissionHandoffTests(MissionCreationFixture, unittest.TestCase):
    def operation(self, kind, identity, **fields):
        return dict(schema="mission/5", kind=kind, request_id=identity, mission_id=self.a.mission_id,
                    epoch=self.runtime.status()["epoch"], **fields)

    def handoff(self, **fields):
        ref, _ = self.current()
        data = dict(checkpoint_ids=[ref.observation_id], unfinished_work_ids=[], successor_role="player")
        data.update(fields)
        return self.run_request(self.operation("handoff", "handoff", **data))

    def context(self, *, binding=True, query="unfinished supplies shelter"):
        phase = self.runtime._registered_handoff.phase
        ref = phase.checkpoint
        return self.runtime.command(dict(schema="mission/5", kind="context", mission_id=self.a.mission_id,
            scope=dict(mission_id=self.a.mission_id, session=ref.session, coordinate_epoch=0),
            query=query, max_bytes=32768, handoff=dict(handoff_id="handoff", prospective_player_id="successor",
                actor_role="player") if binding else None))

    def claim(self, packet, identity="claim", **changes):
        issued = self.runtime._ledger.request("handoff")["result"]
        fields = dict(handoff_id="handoff", player_id="successor", actor_role="player",
            packet_ids=[packet["packet_id"]], read_source_ids=issued["checkpoint_ids"] + [issued["post_pause_source_id"]],
            expected_session=issued["session"], expected_revision=issued["revision"], expected_boundary_id=issued["boundary_id"],
            expected_pause_origin=issued["pause_origin"], takeover_generation=issued["takeover_generation"],
            pause_generation=issued["pause_generation"])
        fields.update(changes)
        return self.operation("claim", identity, **fields)

    def readmit(self):
        issued = self.runtime._ledger.request("handoff")["result"]
        return self.operation("readmit", "readmit", handoff_id="handoff", claim_request_id="claim",
            sources=[issued["post_pause_source_id"]], expected_session=issued["session"], expected_revision=issued["revision"],
            expected_boundary_id=issued["boundary_id"], limits=dict(primitives=1, wall_seconds=30, game_seconds=10))

    def remember_work(self, *, status="active", identity="pending", event="work", intent=None):
        ref, _ = self.current()
        entry = dict(schema="campaign-memory/2", record_type="Work", id=identity, predecessor_work_id=None,
            intent=intent or "unfinished supplies shelter", scope=dict(mission_id=self.a.mission_id, session=ref.session, coordinate_epoch=0),
            stage="pending", progress=25, available=[], committed=[], predicted_output=[], observed_output=[],
            unresolved_effects=[], sources=[ref.observation_id], next_verification="Reobserve supplies", status=status)
        result = self.run_request(self.operation("remember", event, entry_type="work", entry=entry))
        self.assertEqual(result["state"], "completed", result)
        return entry

    def test_quiescent_bound_context_claim_and_separately_charged_resume(self):
        self.create()
        self.remember_work()
        before = self.runtime.status()
        issued = self.handoff(unfinished_work_ids=["pending"])
        self.assertEqual(issued["state"], "completed", issued)
        self.assertEqual(self.runtime.status()["phase"], "handoff")
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"])
        context = self.context()
        self.assertEqual(context["status"], "accepted", context)
        packet = context["context"]["packet"]
        self.assertIn("pending", [w["id"] for w in packet["work"]])
        claim = self.run_request(self.claim(packet))
        self.assertEqual(claim["state"], "completed", claim)
        self.assertEqual(self.runtime.status()["actor_id"], "successor")
        self.assertEqual(self.runtime.status()["phase"], "paused")
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"])
        data = self.readmit()
        result = self.run_request(data)
        self.assertEqual(result["state"], "completed", result)
        self.assertEqual(self.runtime.status()["phase"], "active")
        self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"] + 1)
        self.assertEqual(self.runtime._lease.actor_id, "successor")
        self.assertEqual(self.runtime._ledger.request("handoff")["result"], issued["result"])
        self.assertEqual(self.runtime._ledger.request("claim")["result"], claim["result"])
        self.assertEqual(self.run_request(data), result)
        self.remember_work(status="completed", event="pending-completed")
        self.remember_work(status="completed", identity="objective", event="objective", intent=self.a.objective)
        self.save()
        self.exit()
        finish = self.lifecycle("finish", "finish")
        finish["work_id"] = "objective"
        completed = self.run_request(finish)
        self.assertEqual(completed["state"], "completed", completed)
        self.assertEqual(self.runtime.status()["phase"], "completed")
        self.assertIsNone(self.runtime._native)
        self.runtime._ledger._verify(self.a)
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.start()
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._registered_handoff.phase)

    def test_predecessor_context_does_not_satisfy_successor_claim(self):
        self.create()
        self.handoff()
        packet = self.context(binding=False)["context"]["packet"]
        result = self.run_request(self.claim(packet))
        self.assertEqual(result["state"], "blocked", result)
        self.assertIsNone(self.runtime._lease)

    def test_omitted_unfinished_work_blocks_issuance(self):
        self.create()
        self.remember_work()
        result = self.handoff()
        self.assertEqual(result["state"], "blocked", result)
        self.assertIn("unfinished", result["result"]["reason"])

    def test_lost_completed_work_source_blocks_handoff_without_hiding_failure(self):
        self.create()
        work = self.remember_work(status="completed")
        # Move to a different retained normal observation before removing the old source.
        self.observe("different-source")
        ref = next(ref for ref in self.runtime._store.historical_references if ref.observation_id == work["sources"][0])
        Path(ref.frame_path).unlink()
        result = self.handoff()
        self.assertEqual(result["state"], "blocked", result)
        self.assertIn("unavailable", result["result"]["reason"])

    def test_memory_change_after_packet_requires_new_retrieval(self):
        self.create()
        self.handoff()
        packet = self.context()["context"]["packet"]
        self.remember_work()
        result = self.run_request(self.claim(packet))
        self.assertEqual(result["state"], "blocked", result)
        self.assertIn("fresh-version", result["result"]["reason"])
        self.assertEqual(self.runtime.status()["phase"], "handoff")
        fresh = self.context()["context"]["packet"]
        corrected = self.run_request(self.claim(fresh, identity="corrected-claim"))
        self.assertEqual(corrected["state"], "completed", corrected)

    def test_packet_omitting_declared_work_is_correctable_without_resume(self):
        self.create()
        self.remember_work()
        self.handoff(unfinished_work_ids=["pending"])
        omitted = self.context(query="unrelated-xyz")["context"]["packet"]
        before = self.runtime.status()["spent_inputs"]
        result = self.run_request(self.claim(omitted))
        self.assertEqual(result["state"], "blocked", result)
        self.assertIn("omits unfinished", result["result"]["reason"])
        self.assertEqual(self.runtime.status()["spent_inputs"], before)
        fresh = self.context()["context"]["packet"]
        self.assertEqual(self.run_request(self.claim(fresh, identity="retry-claim"))["state"], "completed")

    def test_retained_work_support_must_be_read_even_when_not_a_checkpoint(self):
        self.create()
        work = self.remember_work()
        self.observe("new-checkpoint")
        self.handoff(unfinished_work_ids=["pending"])
        packet = self.context()["context"]["packet"]
        data = self.claim(packet)
        self.assertNotIn(work["sources"][0], data["read_source_ids"])
        result = self.run_request(data)
        self.assertEqual(result["state"], "blocked", result)
        self.assertIn("Work support", result["result"]["reason"])
        data["request_id"] = "reads-work"
        data["read_source_ids"] += work["sources"]
        self.assertEqual(self.run_request(data)["state"], "completed")

    def test_work_source_loss_after_retrieval_requires_new_unknown_packet(self):
        self.create()
        self.observe("work-only-source")
        work = self.remember_work()
        self.observe("new-checkpoint")
        self.handoff(unfinished_work_ids=["pending"])
        packet = self.context()["context"]["packet"]
        ref = next(ref for ref in self.runtime._store.historical_references if ref.observation_id == work["sources"][0])
        Path(ref.frame_path).unlink()
        data = self.claim(packet)
        data["read_source_ids"] += work["sources"]
        result = self.run_request(data)
        self.assertEqual(result["state"], "blocked", result)
        self.assertIn("changed after retrieval", result["result"]["reason"])
        fresh = self.context()["context"]["packet"]
        self.assertEqual(fresh["work"][0]["status"], "unknown")
        self.assertTrue(any(s["id"] == work["sources"][0] and s["status"] != "retained" for s in fresh["sources"]))
        self.assertEqual(self.run_request(self.claim(fresh, identity="reads-unknown"))["state"], "completed")

    def test_wrong_actor_role_cannot_consume_handoff(self):
        self.create()
        self.handoff()
        packet = self.context()["context"]["packet"]
        result = self.run_request(self.claim(packet, actor_role="curator"))
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(self.runtime.status()["actor_id"], self.a.player_id)
        self.assertIsNone(self.runtime._lease)

    def test_unknown_resume_retains_cost_and_cannot_replay(self):
        self.create()
        self.handoff()
        self.run_request(self.claim(self.context()["context"]["packet"]))
        previous = self.bridge.behavior
        def missing_ack(bridge, request):
            return False if request["kind"] == "resume" else previous(bridge, request)
        self.bridge.behavior = missing_ack
        spent = self.runtime.status()["spent_inputs"]
        data = self.readmit()
        result = self.run_request(data)
        self.assertEqual(result["state"], "unknown", result)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent + 1)
        self.assertEqual(self.runtime._ledger.primitive_records()[-1]["state"], "unknown")
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._registered_handoff.phase)
        before = len(self.bridge.requests)
        self.assertEqual(self.run_request(data), result)
        self.assertEqual(len(self.bridge.requests), before)

    def test_claim_cannot_expand_unfinished_work_beyond_sixteen_after_issuance(self):
        self.create()
        self.handoff()
        for index in range(17):
            self.remember_work(identity=f"new-{index}", event=f"remember-new-{index}")
        packet = self.context()["context"]["packet"]
        result = self.run_request(self.claim(packet))
        self.assertEqual(result["state"], "blocked", result)
        self.assertIn("bound exceeded", result["result"]["reason"])
        self.assertEqual(self.runtime.status()["actor_id"], self.a.player_id)
        self.assertIsNone(self.runtime._lease)

    def test_intake_fence_prevents_new_queue_work_at_atomic_issuance(self):
        self.create()
        original = self.runtime._ledger.issue_handoff
        attempts = []
        def competing(*args, **kwargs):
            attempts.append(self.runtime.command(self.operation("observe", "competing-observe")))
            return original(*args, **kwargs)
        with patch.object(self.runtime._ledger, "issue_handoff", side_effect=competing):
            result = self.handoff()
        self.assertEqual(result["state"], "completed", result)
        self.assertEqual(attempts[0]["status"], "rejected", attempts)
        self.assertIn("sole writer", attempts[0]["reason"])
        self.assertTrue(self.runtime._queue.empty())

    def test_refresh_lock_wait_cannot_outlive_readmission_deadline(self):
        self.create()
        self.handoff()
        self.run_request(self.claim(self.context()["context"]["packet"]))
        original = self.runtime._registered_handoff._observe
        acquired = threading.Event()
        release = threading.Event()
        fallback_timeout = threading.Event()
        def hold():
            with self.controller.command_lock:
                acquired.set()
                if not release.wait(2):
                    fallback_timeout.set()
        def contended(work):
            thread = threading.Thread(target=hold)
            thread.start()
            self.assertTrue(acquired.wait(1))
            try:
                return original(work)
            finally:
                release.set()
                thread.join(1)
        data = self.readmit()
        data["limits"]["wall_seconds"] = 0.05
        before = self.runtime.status()["spent_inputs"]
        with patch.object(self.runtime._registered_handoff, "_observe", side_effect=contended):
            result = self.run_request(data)
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(self.runtime.status()["spent_inputs"], before)
        self.assertFalse(fallback_timeout.is_set(), "Observe waited until the lock holder's fallback timeout")

    def test_duplicate_claim_is_cached_but_second_claim_cannot_consume_again(self):
        self.create()
        self.handoff()
        data = self.claim(self.context()["context"]["packet"])
        result = self.run_request(data)
        self.assertEqual(result["state"], "completed", result)
        self.assertEqual(self.run_request(data), result)
        data["request_id"] = "other-claim"
        self.assertEqual(self.run_request(data)["state"], "blocked")
        self.assertEqual(self.runtime.status()["actor_id"], "successor")

    def test_resume_refreshes_an_aged_checkpoint_without_renewing_limits(self):
        self.create()
        self.handoff()
        self.assertEqual(self.run_request(self.claim(self.context()["context"]["packet"]))["state"], "completed")
        deadline = self.runtime.status()["deadline"]
        time.sleep(3.1)
        result = self.run_request(self.readmit())
        self.assertEqual(result["state"], "completed", result)
        self.assertEqual(self.runtime.status()["deadline"], deadline)

    def test_pause_in_resume_preflight_preserves_charge_and_sends_no_resume(self):
        self.create()
        self.handoff()
        self.run_request(self.claim(self.context()["context"]["packet"]))
        original = self.runtime._ledger.prepare_primitive
        def paused(*args, **kwargs):
            result = original(*args, **kwargs)
            self.runtime.pause("Pause during readmission preflight")
            return result
        before = len(self.bridge.requests)
        spent = self.runtime.status()["spent_inputs"]
        with patch.object(self.runtime._ledger, "prepare_primitive", side_effect=paused):
            result = self.run_request(self.readmit())
        self.assertNotEqual(result["state"], "completed", result)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent + 1)
        self.assertIsNone(self.runtime._lease)
        self.assertFalse(any(row["kind"] == "resume" for row in self.bridge.requests[before:]))
        self.assertEqual(self.runtime._ledger.primitive_records()[-1]["state"], "not_dispatched")

    def test_expired_ordinary_budget_rejects_readmit_before_input(self):
        self.create()
        self.handoff()
        self.run_request(self.claim(self.context()["context"]["packet"]))
        ordinary = self.runtime.status()["deadline"] - self.a.cleanup_reserve.wall_seconds
        before = self.runtime.status()["spent_inputs"]
        with patch.object(self.runtime, "_wall", return_value=ordinary):
            response = self.runtime.command(self.readmit())
        self.assertEqual(response["status"], "rejected", response)
        self.assertEqual(self.runtime.status()["spent_inputs"], before)

    def test_postcommit_pause_keeps_claim_receipt_without_restoring_phase(self):
        self.create()
        self.handoff()
        packet = self.context()["context"]["packet"]
        original = self.runtime._ledger.consume_handoff
        def paused(*args, **kwargs):
            result = original(*args, **kwargs)
            self.runtime.pause("Race after claim")
            return result
        with patch.object(self.runtime._ledger, "consume_handoff", side_effect=paused):
            result = self.run_request(self.claim(packet))
        self.assertEqual(result["state"], "completed", result)
        self.assertEqual(self.runtime.status()["phase"], "paused")
        self.assertEqual(self.runtime.status()["actor_id"], "successor")
        self.assertFalse(self.runtime._closed.is_set())
        self.assertIsNone(self.runtime._registered_handoff.phase)

    def test_postcommit_pause_keeps_atomic_issue_receipt_and_writer_open(self):
        self.create()
        original = self.runtime._ledger.issue_handoff
        def paused(*args, **kwargs):
            result = original(*args, **kwargs)
            self.runtime.pause("Race after issuance")
            return result
        with patch.object(self.runtime._ledger, "issue_handoff", side_effect=paused):
            result = self.handoff()
        self.assertEqual(result["state"], "completed", result)
        self.assertEqual(self.runtime.status()["phase"], "paused")
        self.assertFalse(self.runtime._closed.is_set())
        self.assertIsNone(self.runtime._registered_handoff.phase)
        self.assertIsNone(self.runtime._lease)

    def test_claim_pause_cannot_be_automatically_readmitted(self):
        self.create()
        self.handoff()
        packet = self.context()["context"]["packet"]
        self.assertEqual(self.run_request(self.claim(packet))["state"], "completed")
        before = copy.deepcopy(self.bridge.requests)
        self.runtime.pause("User keeps control")
        response = self.runtime.command(self.readmit())
        if response["status"] == "accepted":
            self.assertEqual(self.settled("readmit")["state"], "blocked")
        else:
            self.assertEqual(response["status"], "rejected", response)
        self.assertFalse(any(row["kind"] == "resume" for row in self.bridge.requests[len(before):]))
