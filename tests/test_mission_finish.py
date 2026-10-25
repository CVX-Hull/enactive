"""Normal-finish composition with real ledger/controller and synthetic UI only."""
from dataclasses import replace
from contextlib import contextmanager
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from harness.mission_runtime import MissionRuntime
from harness.gameplay.mission_contracts import LearningPolicy
from harness.gameplay.mission_ledger import BudgetError
from tests.test_reflection_exchange import procedure
from tests.test_mission_creation import MissionCreationFixture
from tests.test_request_receipts import settled_timing


class MissionFinishTests(MissionCreationFixture, unittest.TestCase):
    @contextmanager
    def hold_after_finish_publication(self):
        published, release = threading.Event(), threading.Event()
        original = self.runtime._cache_operation
        def cache_before_next_tick(operation):
            original(operation)
            if operation["request"]["request_id"] == "finish" and operation["result"] is not None:
                published.set()
                if not release.wait(3):
                    raise TimeoutError("Finish publication barrier was not released")
        with patch.object(self.runtime, "_cache_operation", side_effect=cache_before_next_tick):
            try:
                yield published
            finally:
                release.set()

    def assert_advisory_reopened(self, reflection, operation):
        self.assertEqual(operation["state"], "completed", operation)
        self.assertEqual(self.runtime.status()["phase"], "paused")
        self.assertFalse(self.runtime._closed.is_set())
        self.assertFalse(reflection.exchange._sealed)
        self.assertEqual(reflection.summary()["phase"], "paused")
        self.assertEqual(reflection.exchange.next_job(mission_id=self.a.mission_id,
            reflector_id="reflector-a")["status"], "idle")

    def test_finish_deadline_failure_after_advisory_seal_does_not_disable_learner(self):
        self.a = replace(self.a, learning=LearningPolicy(procedure()["environment"], reflector_id="reflector-a"))
        self.untouched_exit()
        reflection = self.runtime._registered_reflection
        original = self.runtime._finish_guard
        def expire_after_seal(work):
            if reflection.exchange._sealed:
                raise BudgetError("Original finish/mission wall deadline expired")
            return original(work)
        with patch.object(self.runtime, "_finish_guard", side_effect=expire_after_seal), \
                self.hold_after_finish_publication() as published:
            operation = self.finish()
            self.assertTrue(published.wait(3))
            self.assert_advisory_reopened(reflection, operation)
        timing = settled_timing(self.runtime, "finish")
        self.assertEqual(timing["row_state"], "completed")
        self.assertEqual(timing["mission_phase"], "paused")
        self.assertTrue(timing["writer_finalized"])

    def test_real_terminal_ledger_deadline_refusal_reopens_advisory_before_next_tick(self):
        self.a = replace(self.a, learning=LearningPolicy(procedure()["environment"], reflector_id="reflector-a"))
        self.untouched_exit()
        reflection = self.runtime._registered_reflection
        original, wall = self.runtime._ledger.finish_mission, self.runtime._wall
        offset, refusals = [0], []
        def expire_at_terminal_write(*args, **kwargs):
            self.assertTrue(reflection.exchange._sealed)
            offset[0] = self.runtime._ledger.request("finish")["deadline"] + 1 - wall()
            try:
                return original(*args, **{**kwargs, "now": self.runtime._wall()})
            except BudgetError as exc:
                refusals.append(str(exc))
                raise
        with patch.object(self.runtime, "_wall", side_effect=lambda: wall() + offset[0]), \
                patch.object(self.runtime._ledger, "finish_mission", side_effect=expire_at_terminal_write), \
                self.hold_after_finish_publication() as published:
            operation = self.finish()
            self.assertTrue(published.wait(3))
            self.assertEqual(refusals, ["Original normal-finish deadline expired before terminal persistence"])
            self.assert_advisory_reopened(reflection, operation)

    def test_pause_during_advisory_seal_keeps_future_reflection_available(self):
        self.a = replace(self.a, learning=LearningPolicy(procedure()["environment"], reflector_id="reflector-a"))
        self.untouched_exit()
        reflection = self.runtime._registered_reflection
        original = reflection.finish
        def pause_after_seal(*, permanent):
            original(permanent=permanent)
            self.runtime.pause()
        with patch.object(reflection, "finish", side_effect=pause_after_seal), \
                self.hold_after_finish_publication() as published:
            operation = self.finish()
            self.assertTrue(published.wait(3))
            self.assert_advisory_reopened(reflection, operation)

    def test_terminal_storage_fault_does_not_reopen_advisory_ingress(self):
        self.a = replace(self.a, learning=LearningPolicy(procedure()["environment"], reflector_id="reflector-a"))
        self.untouched_exit()
        reflection = self.runtime._registered_reflection
        with patch.object(self.runtime._ledger, "finish_mission", side_effect=OSError("Injected terminal storage failure")), \
                patch.object(reflection, "cancel_finish", wraps=reflection.cancel_finish) as cancel:
            self.assertEqual(self.runtime.command(self.lifecycle("finish", "finish"))["status"], "accepted")
            self.assertTrue(self.runtime._closed.wait(3))
            cancel.assert_not_called()
        self.runtime.close()
        self.assertTrue(reflection.exchange._sealed)
        self.assertEqual(reflection.exchange.next_job(mission_id=self.a.mission_id,
            reflector_id="reflector-a")["status"], "closed")
        self.assertIn("Injected terminal storage failure", self.runtime.status()["diagnostic"])

    def test_committed_terminal_state_is_never_reopened_after_late_refusal(self):
        self.a = replace(self.a, learning=LearningPolicy(procedure()["environment"], reflector_id="reflector-a"))
        self.untouched_exit()
        reflection = self.runtime._registered_reflection
        original = self.runtime._ledger.finish_mission
        def refuse_after_terminal_commit(*args, **kwargs):
            original(*args, **kwargs)
            raise BudgetError("Injected refusal after terminal commit")
        with patch.object(self.runtime._ledger, "finish_mission", side_effect=refuse_after_terminal_commit), \
                self.hold_after_finish_publication() as published:
            operation = self.finish()
            self.assertTrue(published.wait(3))
            self.assertEqual(operation["state"], "completed", operation)
            self.assertEqual(self.runtime.status()["phase"], "stopped")
            self.assertTrue(reflection.exchange._sealed)
            self.assertEqual(reflection.summary()["phase"], "stopped")
            self.assertEqual(reflection.exchange.next_job(mission_id=self.a.mission_id,
                reflector_id="reflector-a")["status"], "closed")

    def remember_work(self, identity="objective", *, source=None, status="completed", intent=None):
        source = source or self.runtime._current
        entry = dict(schema="campaign-memory/6", record_type="Work", id="objective-work", predecessor_work_id=None,
            intent=intent or self.a.objective, scope=dict(mission_id=self.a.mission_id, session=source.session,
                coordinate_epoch=0), stage="verified" if status == "completed" else "pending",
            progress=100 if status == "completed" else 25, available=[], committed=[], predicted_output=[],
            observed_output=[], unresolved_effects=[], sources=[source.observation_id],
            next_verification="Independent acceptance assesses the actual objective evidence", status=status)
        result = self.run_request(dict(schema="mission/11", kind="remember", request_id=identity,
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"], entry_type="work", entry=entry))
        self.assertEqual(result["state"], "completed", result)
        return entry

    def finish(self, identity="finish", work_id=None):
        data = self.lifecycle(identity, "finish")
        data["work_id"] = work_id
        return self.run_request(data)

    def untouched_exit(self):
        self.ready()
        self.exit()

    def test_untouched_exit_finishes_stopped_without_more_native_input(self):
        self.untouched_exit()
        count = len(self.bridge.requests)
        operation = self.finish()
        self.assertEqual(operation["state"], "completed", operation)
        self.assertEqual(operation["result"]["normal_finish"]["disposition"], "stopped")
        self.assertEqual(self.runtime.status()["phase"], "stopped")
        self.assertEqual(len(self.bridge.requests), count)
        timing = settled_timing(self.runtime, "finish")
        self.assertEqual(timing["row_state"], "completed")
        self.assertEqual(timing["mission_phase"], "stopped")
        self.assertTrue(timing["writer_finalized"])
        self.assertIsNone(self.runtime._native)
        self.assertIsNone(self.runtime._native_owner)
        self.assertIsNone(self.runtime._owned_launch)
        self.assertFalse(self.runtime._closed.is_set())
        self.assertEqual(self.runtime.command(operation["request"])["operation"], operation)
        self.assertEqual(len(self.bridge.requests), count)

    def test_completed_work_is_player_reported_separately_from_normal_cleanup(self):
        self.create()
        self.remember_work()
        self.save()
        self.exit()
        count = len(self.bridge.requests)
        operation = self.finish(work_id="objective-work")
        self.assertEqual(operation["state"], "completed", operation)
        self.assertEqual(operation["result"]["normal_finish"]["completed_work_event_id"], "objective")
        self.assertEqual(self.runtime.status()["phase"], "completed")
        self.assertEqual(self.runtime.status()["reason"], "Player-reported objective completion")
        self.assertEqual(len(self.bridge.requests), count)
        with self.runtime._ledger._mutex:
            self.runtime._ledger._verify(self.a)
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.start()
        self.assertEqual(self.runtime.status()["phase"], "completed")
        self.assertIsNone(self.runtime._native)
        self.assertIsNone(self.runtime._lease)

    def test_normal_cleanup_allows_a_new_explicit_mission(self):
        self.untouched_exit()
        self.assertEqual(self.finish()["state"], "completed")
        self.a = replace(self.a, mission_id="next-mission")
        operation = self.run_request(dict(schema="mission/11", kind="start", request_id="next-start", admission=self.a.to_dict()))
        self.assertEqual(operation["state"], "completed", operation)
        self.assertEqual(self.runtime.status()["mission_id"], "next-mission")
        self.assertIsNone(self.runtime._native)

    def test_finish_accepts_stale_retained_evidence_without_observe(self):
        self.untouched_exit()
        clock = self.runtime._clock
        count = len(self.bridge.requests)
        with patch.object(self.runtime, "_clock", side_effect=lambda: clock() + 10):
            operation = self.finish()
        self.assertEqual(operation["state"], "completed", operation)
        self.assertEqual(self.runtime.status()["phase"], "stopped")
        self.assertEqual(len(self.bridge.requests), count)

    def test_missing_final_source_rejects_without_more_native_input(self):
        self.untouched_exit()
        data = self.lifecycle("finish", "finish")
        Path(self.runtime._current.frame_path).unlink()
        count = len(self.bridge.requests)
        operation = self.run_request(data)
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertNotIn(self.runtime.status()["phase"], ("completed", "stopped"))
        self.assertEqual(len(self.bridge.requests), count)

    def test_source_free_or_unexited_run_cannot_claim_normal_finish(self):
        self.ready()
        operation = self.finish()
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertNotIn(self.runtime.status()["phase"], ("completed", "stopped"))

    def test_newer_incomplete_work_frontier_defeats_later_old_completion_report(self):
        self.create()
        old = self.runtime._current
        self.turn += 1
        self.observe("newer-observation")
        self.remember_work("newer-incomplete", status="active")
        self.remember_work("late-old-completion", source=old)
        self.save()
        self.exit()
        operation = self.finish(work_id="objective-work")
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertIn("incomplete or conflicting", operation["result"]["reason"])
        self.assertNotEqual(self.runtime.status()["phase"], "completed")

    def test_pause_after_report_commit_keeps_history_and_writer_but_not_terminal_success(self):
        self.untouched_exit()
        original = self.runtime._commit_finish
        def pause_before_terminal(work, result):
            self.runtime.pause()
            return original(work, result)
        with patch.object(self.runtime, "_commit_finish", side_effect=pause_before_terminal):
            operation = self.finish()
        self.assertEqual(operation["state"], "completed", operation)
        self.assertIn("normal_finish", operation["result"])
        self.assertEqual(self.runtime.status()["phase"], "paused")
        self.assertFalse(self.runtime._closed.is_set())
        self.assertIsNotNone(self.runtime._native)
        self.assertIsNone(self.runtime._lease)

    def test_crash_between_report_and_terminal_reopens_paused_without_replay(self):
        self.untouched_exit()
        with patch.object(self.runtime, "_commit_finish", side_effect=OSError("Injected terminal storage failure")):
            self.assertEqual(self.runtime.command(self.lifecycle("finish", "finish"))["status"], "accepted")
            self.assertTrue(self.runtime._closed.wait(3))
        self.runtime.close()
        count = len(self.bridge.requests)
        self.runtime = MissionRuntime(self.controller)
        self.start()
        self.assertEqual(self.runtime.status()["phase"], "paused")
        self.assertEqual(self.runtime._ledger.request("finish")["state"], "completed")
        self.assertIsNone(self.runtime._native)
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(len(self.bridge.requests), count)

    def test_unrelated_work_intent_cannot_claim_objective_completion(self):
        self.create()
        self.remember_work(intent="Unrelated completed task")
        self.save()
        self.exit()
        result = self.finish(work_id="objective-work")
        self.assertEqual(result["state"], "blocked", result)
        self.assertNotEqual(self.runtime.status()["phase"], "completed")

    def test_dangling_native_inbox_prevents_finish(self):
        self.untouched_exit()
        inbox = self.controller.bridge / "control.json"
        inbox.symlink_to(self.controller.bridge / "missing-target")
        self.addCleanup(inbox.unlink, missing_ok=True)
        result = self.finish()
        self.assertEqual(result["state"], "blocked", result)
        self.assertIn("empty native inboxes", result["result"]["reason"])
        self.assertNotIn(self.runtime.status()["phase"], ("completed", "stopped"))

    def test_later_work_update_does_not_rewrite_historical_finish_report(self):
        self.create()
        self.remember_work()
        self.save()
        self.exit()
        original = self.runtime._commit_finish
        def pause_before_terminal(work, result):
            self.runtime.pause()
            return original(work, result)
        with patch.object(self.runtime, "_commit_finish", side_effect=pause_before_terminal):
            self.assertEqual(self.finish(work_id="objective-work")["state"], "completed")
        normal = [ref for ref in self.runtime._store.historical_references if ref.boundary_kind == "normal_play"][-1]
        self.remember_work("later-incomplete-report", source=normal, status="active")
        with self.runtime._ledger._mutex:
            self.runtime._ledger._verify(self.a)
        self.assertEqual(self.runtime._ledger.request("finish")["result"]["normal_finish"]["completed_work_event_id"], "objective")
        self.assertEqual(self.runtime.status()["phase"], "paused")

    def expire_during_final_status(self, *, work_id=None):
        original_status, original_wall = self.runtime._native.status, self.runtime._wall
        offset = [0]
        def status_crossing_deadline():
            operation = self.runtime._ledger.request("finish")
            if operation["result"] is not None and "normal_finish" in operation["result"]:
                offset[0] = operation["deadline"] + 1 - original_wall()
            return original_status()
        with patch.object(self.runtime, "_wall", side_effect=lambda: original_wall() + offset[0]), \
                patch.object(self.runtime._native, "status", side_effect=status_crossing_deadline):
            operation = self.finish(work_id=work_id)
            self.assertEqual(operation["state"], "completed", operation)
            self.assertEqual(self.runtime.status()["phase"], "paused")
            self.assertIn("deadline expired", self.runtime.status()["diagnostic"])
            self.assertFalse(self.runtime._closed.is_set())

    def test_final_guard_cannot_terminalize_stopped_cleanup_after_its_deadline(self):
        self.untouched_exit()
        self.expire_during_final_status()

    def test_final_guard_cannot_terminalize_completed_report_after_its_deadline(self):
        self.create()
        self.remember_work()
        self.save()
        self.exit()
        self.expire_during_final_status(work_id="objective-work")

    def test_pause_during_final_process_sample_wins_before_terminal_write(self):
        self.untouched_exit()
        original = self.runtime._native.status
        def pause_at_last_sample():
            operation = self.runtime._ledger.request("finish")
            if operation["result"] is not None and "normal_finish" in operation["result"]:
                self.runtime.pause()
            return original()
        with patch.object(self.runtime._native, "status", side_effect=pause_at_last_sample):
            operation = self.finish()
        self.assertEqual(operation["state"], "completed", operation)
        self.assertEqual(self.runtime.status()["phase"], "paused")
        self.assertEqual(self.runtime._ledger.snapshot(now=self.runtime._wall())["phase"], "paused")
        self.assertFalse(self.runtime._closed.is_set())
        self.assertIsNotNone(self.runtime._native)


if __name__ == "__main__":
    unittest.main()
