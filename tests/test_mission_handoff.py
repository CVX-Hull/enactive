"""Player replacement through actual controller/SQLite/archive, synthetic UI only."""
import copy
from pathlib import Path
import unittest
import time
import threading
from unittest.mock import patch

from harness.mission_runtime import MissionRuntime
from tests.test_mission_creation import MissionCreationFixture
from tests.test_mission_contracts import claim


class MissionHandoffTests(MissionCreationFixture, unittest.TestCase):
    def operation(self, kind, identity, **fields):
        return dict(schema="mission/11", kind=kind, request_id=identity, mission_id=self.a.mission_id,
                    epoch=self.runtime.status()["epoch"], **fields)

    def handoff(self, **fields):
        ref, _ = self.current()
        data = dict(checkpoint_ids=[ref.observation_id], unfinished_work_ids=[], successor_role="player")
        data.update(fields)
        return self.run_request(self.operation("handoff", "handoff", **data))

    def context(self, *, binding=True, query="unfinished supplies shelter"):
        phase = self.runtime._registered_handoff.phase
        ref = phase.checkpoint
        result = self.runtime.command(dict(schema="mission/11", kind="context", mission_id=self.a.mission_id,
            scope=dict(mission_id=self.a.mission_id, session=ref.session, coordinate_epoch=0),
            query=query, max_bytes=32768, handoff=dict(handoff_id="handoff", prospective_player_id="successor",
                actor_role="player") if binding else None))
        self.assertEqual(result["status"], "accepted", result.get("reason"))
        return result

    def claim(self, packet, identity="claim", **changes):
        issued = self.runtime._ledger.request("handoff")["result"]
        fields = dict(handoff_id="handoff", player_id="successor", actor_role="player",
            packet_ids=[packet["packet_id"]], read_source_ids=issued["checkpoint_ids"] + [issued["post_pause_source_id"]],
            expected_session=issued["session"], expected_revision=issued["revision"], expected_boundary_id=issued["boundary_id"],
            expected_pause_origin=issued["pause_origin"], takeover_generation=issued["takeover_generation"],
            pause_generation=issued["pause_generation"], read_procedure_sources=[])
        fields.update(changes)
        return self.operation("claim", identity, **fields)

    def readmit(self):
        issued = self.runtime._ledger.request("handoff")["result"]
        return self.operation("readmit", "readmit", mode="handoff", handoff_id="handoff", claim_request_id="claim",
            sources=[issued["post_pause_source_id"]], expected_session=issued["session"], expected_revision=issued["revision"],
            expected_boundary_id=issued["boundary_id"], limits=dict(primitives=1, wall_seconds=30, game_seconds=10))

    def remember_work(self, *, status="active", identity="pending", event="work", intent=None, sources=None):
        ref, _ = self.current()
        entry = dict(schema="campaign-memory/6", record_type="Work", id=identity, predecessor_work_id=None,
            intent=intent or "unfinished supplies shelter", scope=dict(mission_id=self.a.mission_id, session=ref.session, coordinate_epoch=0),
            stage="pending", progress=25, available=[], committed=[], predicted_output=[], observed_output=[],
            unresolved_effects=[], sources=[ref.observation_id] if sources is None else sources,
            next_verification="Reobserve supplies", status=status)
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
        with self.runtime._ledger._mutex:
            self.runtime._ledger._verify(self.a)
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.start()
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._registered_handoff.phase)

    def test_passive_capture_at_handoff_keeps_the_exact_retained_checkpoint(self):
        from tests.test_mission_observation_churn import passive_capture
        self.create()
        capture = self.runtime._capture_memory
        def captured(reference):
            capture(reference)
            passive_capture(self.controller, self.bridge)
        with patch.object(self.runtime, "_capture_memory", side_effect=captured):
            issued = self.handoff()
        self.assertEqual(issued["state"], "completed", issued)
        checkpoint = self.runtime._registered_handoff.phase.checkpoint
        source = self.runtime._store.observation(checkpoint)
        self.assertEqual(source["frame"], self.controller.state["frame"])
        self.assertEqual(source["timestamp_ms"], self.controller.state["timestamp_ms"])
        self.assertEqual(issued["result"]["post_pause_source_id"], checkpoint.observation_id)
        self.assertIsNone(self.runtime._lease)

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
        before, lease = self.runtime.status(), self.runtime._lease
        delivered = copy.deepcopy(self.bridge.delivered)
        for identity, work_ids in (("omitted-work", []), ("extra-work", ["pending", "not-work"])):
            with self.subTest(identity=identity), \
                    patch.object(self.controller, "stop_input", wraps=self.controller.stop_input) as stopped:
                result = self.run_request(self.operation("handoff", identity,
                    checkpoint_ids=[self.runtime._current.observation_id], unfinished_work_ids=work_ids,
                    successor_role="player"))
                self.assertEqual(result["state"], "blocked", result)
                self.assertIn("unfinished Work", result["result"]["reason"])
                self.assertIn("before stopping input", result["result"]["reason"])
                stopped.assert_not_called()
                self.assertIs(self.runtime._lease, lease)
                self.assertEqual(self.runtime.status()["phase"], "active")
                self.assertEqual(self.runtime.status()["epoch"], before["epoch"])
                self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"])
                self.assertEqual(self.bridge.delivered, delivered)
        self.assertEqual(self.handoff(unfinished_work_ids=["pending"])["state"], "completed")

    def test_unknown_checkpoint_reference_can_be_corrected_without_losing_authority(self):
        self.create()
        self.remember_work()
        ref, _ = self.current()
        entry = claim(id="water-claim", key=dict(subject="water", property="supply", unit="charges",
            coverage_id="fixture-scene"), scope=dict(mission_id=self.a.mission_id, session=ref.session,
            coordinate_epoch=0), observed_time=dict(revision=ref.revision, turn=ref.turn),
            sources=[ref.observation_id], supports=[dict(sources=[ref.observation_id], claims=[])])
        self.assertEqual(self.run_request(self.operation("remember", "remember-character",
            entry_type="claim", entry=entry))["state"], "completed")
        before, lease = self.runtime.status(), self.runtime._lease
        delivered = copy.deepcopy(self.bridge.delivered)
        for index, unknown in enumerate(("water-claim", "pending", "f"*64)):
            with self.subTest(reference=unknown), \
                    patch.object(self.controller, "stop_input", wraps=self.controller.stop_input) as stopped:
                result = self.run_request(self.operation("handoff", f"wrong-checkpoint-{index}",
                    checkpoint_ids=[unknown], unfinished_work_ids=["pending"], successor_role="player"))
                self.assertEqual(result["state"], "blocked", result)
                self.assertIn("source observation IDs", result["result"]["reason"])
                self.assertIn(unknown, result["result"]["reason"])
                stopped.assert_not_called()
                self.assertIs(self.runtime._lease, lease)
                self.assertEqual(self.runtime.status()["phase"], "active")
                self.assertEqual(self.runtime.status()["epoch"], before["epoch"])
                self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"])
                self.assertEqual(self.bridge.delivered, delivered)
                self.assertIsNone(self.runtime._registered_handoff.phase)
        self.assertEqual(self.handoff(unfinished_work_ids=["pending"])["state"], "completed")

    def test_known_checkpoint_with_lost_bytes_still_revokes_authority(self):
        self.create()
        self.observe("historical-checkpoint")
        ref, _ = self.current()
        self.observe("new-current-source")
        Path(ref.frame_path).unlink()
        # An earlier caller typo must not hide damage to a supplied known source.
        result = self.handoff(checkpoint_ids=["not-a-source", ref.observation_id])
        self.assertEqual(result["state"], "blocked", result)
        self.assertIn("source unavailable", result["result"]["reason"])
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._registered_handoff.phase)
        self.assertEqual(self.runtime.status()["phase"], "paused")

    def expired_draft(self, *, checkpoint_ids=None):
        self.create()
        self.remember_work()
        before = self.runtime.status()
        delivered = copy.deepcopy(self.bridge.delivered)
        ordinary = before["deadline"] - self.a.cleanup_reserve.wall_seconds
        with patch.object(self.runtime, "_wall", return_value=ordinary):
            result = self.handoff(**({} if checkpoint_ids is None else dict(checkpoint_ids=checkpoint_ids)))
        self.assertEqual(result["state"], "blocked", result)
        self.assertIn("observation deadline exhausted", result["result"]["reason"])
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._registered_handoff.phase)
        self.assertEqual(self.runtime.status()["phase"], "paused")
        self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"])
        self.assertEqual(self.bridge.delivered, delivered)

    def test_unknown_checkpoint_cannot_hide_expired_ordinary_budget(self):
        self.expired_draft(checkpoint_ids=["not-a-source"])

    def test_work_coverage_error_cannot_hide_expired_ordinary_budget(self):
        self.expired_draft()

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
        ref, _ = self.current()
        entry = claim(id="later-claim", key=dict(subject="water", property="supply", unit="items", coverage_id="fixture-scene"),
            scope=dict(mission_id=self.a.mission_id, session=ref.session, coordinate_epoch=0),
            observed_time=dict(revision=ref.revision, turn=ref.turn), sources=[ref.observation_id],
            supports=[dict(sources=[ref.observation_id], claims=[])])
        self.assertEqual(self.run_request(self.operation("remember", "later-memory", entry_type="claim", entry=entry))["state"], "completed")
        result = self.run_request(self.claim(packet))
        self.assertEqual(result["state"], "blocked", result)
        self.assertIn("fresh-version", result["result"]["reason"])
        self.assertEqual(self.runtime.status()["phase"], "handoff")
        fresh = self.context()["context"]["packet"]
        corrected = self.run_request(self.claim(fresh, identity="corrected-claim"))
        self.assertEqual(corrected["state"], "completed", corrected)

    def test_query_cannot_displace_required_work_and_claim_still_checks_coverage(self):
        self.create()
        self.remember_work()
        self.handoff(unfinished_work_ids=["pending"])
        omitted = self.context(query="unrelated-xyz")["context"]["packet"]
        self.assertEqual([w["id"] for w in omitted["work"]], ["pending"])
        # Keep the receiver's coverage defense even if a cached packet is damaged.
        self.runtime._issued_packets[omitted["packet_id"]]["packet"]["work"] = []
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

    def test_work_mutation_cannot_invalidate_a_live_handoff(self):
        self.create()
        entry = self.remember_work()
        self.assertEqual(self.handoff(unfinished_work_ids=["pending"])["state"], "completed")
        before = self.runtime.status()
        changed = {**entry, "id": "new-work"}
        result = self.run_request(self.operation("remember", "new-work-event", entry_type="work", entry=changed))
        self.assertEqual(result["state"], "blocked", result)
        self.assertIn("frozen during handoff", result["result"]["reason"])
        self.assertEqual(self.runtime.status()["memory_version"], before["memory_version"])
        self.assertEqual(self.runtime.status()["epoch"], before["epoch"])
        packet = self.context()["context"]["packet"]
        result = self.run_request(self.claim(packet))
        self.assertEqual(result["state"], "completed", result)
        self.assertEqual(self.runtime.status()["actor_id"], "successor")
        self.assertIsNone(self.runtime._lease)

    def test_seventeen_work_items_refuse_handoff_before_authority_revocation(self):
        self.create()
        identities = [f"pending-{i}" for i in range(17)]
        for identity in identities:
            self.remember_work(identity=identity, event=f"remember-{identity}")
        before, lease = self.runtime.status(), self.runtime._lease
        with patch.object(self.controller, "stop_input", wraps=self.controller.stop_input) as stopped:
            result = self.handoff(unfinished_work_ids=identities[:16])
        self.assertEqual(result["state"], "blocked", result)
        self.assertIn("representation refused before stopping", result["result"]["reason"])
        stopped.assert_not_called()
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(self.runtime.status()["epoch"], before["epoch"])
        self.assertEqual(self.runtime.status()["phase"], "active")
        self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"])

    def test_actual_shaped_nine_source_work_retrieval_claim_and_readmission(self):
        self.create()
        first = self.remember_work()
        session = self.runtime._current.session
        menu_sources = []
        for index in range(8):
            self.bridge.value["revision"] += 1
            self.menu("UILIST", ["CONFIRM", "UILIST.QUIT"], in_game=True)
            self.observe(f"support-menu-{index}")
            menu_sources.append(self.runtime._current.observation_id)
        self.bridge.value["revision"] += 1
        self.normal(session)
        self.observe("back-normal")
        self.remember_work(event="work-update", sources=menu_sources)
        expected = set(first["sources"] + menu_sources)
        self.assertEqual(len(expected), 9)
        self.assertEqual(self.handoff(unfinished_work_ids=["pending"])["state"], "completed")
        packet = self.context(query="unrelated")["context"]["packet"]
        self.assertEqual(set(packet["work"][0]["sources"]), expected)
        self.assertEqual(packet["work"][0]["status"], "unknown")
        self.assertIsNone(packet["work"][0]["progress"])
        data = self.claim(packet)
        data["read_source_ids"] = list(dict.fromkeys(data["read_source_ids"] + list(expected)))
        with patch.object(self.runtime._store, "source_status", wraps=self.runtime._store.source_status) as checked:
            result = self.run_request(data)
        self.assertEqual(result["state"], "completed", result)
        checked_ids = [call.args[0].observation_id for call in checked.call_args_list]
        work_checks = [identity for identity in checked_ids if identity in expected]
        self.assertEqual(set(work_checks), expected)
        self.assertEqual(len(work_checks), len(expected))
        # Exact current checkpoint verification at both guards remains separate.
        self.assertLessEqual(len(set(checked_ids)), 128)
        before = self.runtime.status()["spent_inputs"]
        self.assertEqual(self.run_request(self.readmit())["state"], "completed")
        self.assertEqual(self.runtime.status()["spent_inputs"], before+1)

    def test_aggregate_packet_bytes_refuse_before_relinquishing_authority(self):
        self.create()
        template = self.remember_work(status="completed", identity="template")
        quantity = dict(subject="s"*128, quantity=1, unit="u"*32, coverage_id="c"*128)
        identities = []
        for index in range(6):
            identity = f"large-{index}"
            entry = {**template, "id": identity, "status": "active", "intent": "🧭"*1024,
                "next_verification": "🧭"*1024,
                **{key: [quantity]*16 for key in ("available", "committed", "predicted_output", "observed_output")}}
            result = self.run_request(self.operation("remember", f"event-{identity}", entry_type="work", entry=entry))
            self.assertEqual(result["state"], "completed", result)
            identities.append(identity)
        before, lease = self.runtime.status(), self.runtime._lease
        with patch.object(self.controller, "stop_input", wraps=self.controller.stop_input) as stopped:
            result = self.handoff(unfinished_work_ids=identities)
        self.assertEqual(result["state"], "blocked", result)
        self.assertIn("packet byte limit", result["result"]["reason"])
        stopped.assert_not_called()
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(self.runtime.status()["epoch"], before["epoch"])
        self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"])

    def test_source_budget_includes_checkpoint_work_and_reserved_post_pause(self):
        self.create()
        work = self.remember_work()
        self.observe("separate-checkpoint")
        self.assertNotEqual(work["sources"], [self.runtime._current.observation_id])
        before, lease = self.runtime.status(), self.runtime._lease
        # Two existing distinct sources need a third slot for post-Pause evidence.
        with patch("harness.mission_handoff.MAX_HANDOFF_SOURCES", 2), \
                patch.object(self.controller, "stop_input", wraps=self.controller.stop_input) as stopped:
            result = self.handoff(unfinished_work_ids=["pending"])
        self.assertEqual(result["state"], "blocked", result)
        self.assertIn("aggregate source-check bound", result["result"]["reason"])
        stopped.assert_not_called()
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(self.runtime.status()["epoch"], before["epoch"])

    def test_user_pause_wins_during_preflight_source_checks(self):
        self.create()
        self.remember_work()
        before = self.runtime.status()
        original = self.runtime._registered_handoff._source_checker
        paused = False
        def checker(*args, **kwargs):
            refs, status = original(*args, **kwargs)
            def check(identity):
                nonlocal paused
                if not paused:
                    paused = True
                    self.runtime.pause("Actual user Pause during representation preflight")
                return status(identity)
            return refs, check
        with patch.object(self.runtime._registered_handoff, "_source_checker", side_effect=checker):
            result = self.handoff(unfinished_work_ids=["pending"])
        self.assertIn(result["state"], ("blocked", "paused"))
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._registered_handoff.phase)
        self.assertGreater(self.runtime.status()["epoch"], before["epoch"])
        self.assertEqual(self.runtime.status()["pause_cause"], "user")
        self.assertEqual(self.runtime.status()["spent_inputs"], before["spent_inputs"])

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
