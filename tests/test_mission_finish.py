"""Normal-finish composition with real ledger/controller and synthetic UI only."""
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from harness.mission_runtime import MissionRuntime
from tests.test_mission_creation import MissionCreationFixture


class MissionFinishTests(MissionCreationFixture, unittest.TestCase):
    def remember_work(self, identity="objective", *, source=None, status="completed", intent=None):
        source = source or self.runtime._current
        entry = dict(schema="campaign-memory/3", record_type="Work", id="objective-work", predecessor_work_id=None,
            intent=intent or self.a.objective, scope=dict(mission_id=self.a.mission_id, session=source.session,
                coordinate_epoch=0), stage="verified" if status == "completed" else "pending",
            progress=100 if status == "completed" else 25, available=[], committed=[], predicted_output=[],
            observed_output=[], unresolved_effects=[], sources=[source.observation_id],
            next_verification="Independent acceptance assesses the actual objective evidence", status=status)
        result = self.run_request(dict(schema="mission/7", kind="remember", request_id=identity,
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
        operation = self.run_request(dict(schema="mission/7", kind="start", request_id="next-start", admission=self.a.to_dict()))
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
