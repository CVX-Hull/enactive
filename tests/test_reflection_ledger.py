"""SQLite advisory bookkeeping over synthetic requests, not model/game efficacy."""
from pathlib import Path
from copy import deepcopy
from dataclasses import replace
import sqlite3
import tempfile
import unittest

import pytest

from harness.gameplay.contracts import ContractError, canonical
from harness.gameplay.mission_contracts import LearningPolicy, ReflectionLimits
from harness.gameplay.mission_ledger import (BudgetError, LedgerError, MissionLedger,
    ReflectionBudgetRefusal, ReflectionRefusal)
from tests.test_mission_contracts import admission
from tests.test_reflection_exchange import command, job, procedure, proposal


class ReflectionLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "mission"
        self.admission = admission(mission_id="mission-a", learning=LearningPolicy(
            procedure()["environment"], reflector_id="reflector-a",
            reflection_limits=ReflectionLimits(total_seconds=180)))
        self.ledger = MissionLedger(self.path, admission=self.admission, now=1000)
        self.addCleanup(lambda: self.ledger.close())

    def offer(self, number=1, *, now=1000):
        request = dict(schema="mission/11", kind="observe", request_id=f"request-{number}", mission_id="mission-a", epoch=0)
        result = dict(source_ids=[f"source-{number}"], grants_authority=False, flag=1)
        self.ledger.begin_request(request, now=now)
        self.ledger.complete_request(request["request_id"], "completed", result, now=now)
        value = job(id=f"job-{number}", memory_version=0, after_sequence=number-1, through_sequence=number,
            included_request_ids=[request["request_id"]], trajectory=[dict(request=request, state="completed", result=result)],
            sources=[dict(mission_id="mission-a", source_id=f"source-{number}")])
        return self.ledger.append_reflection_job(value, now=now)

    def submission(self, **changes):
        value = command("submit-1", submit=True)
        value["proposal"] = proposal(memory_version=0, **changes)
        return value

    def test_claim_submit_duplicate_and_memory_sequence_remain_separate(self):
        self.offer()
        original = self.ledger.apply_reflection(command(), now=1001)
        self.assertEqual(original["deadline"], 1181)
        self.assertEqual(original["charged_seconds"], 180)
        self.assertEqual(self.ledger.apply_reflection(command(), now=1010), original)
        returned = self.ledger.apply_reflection(self.submission(), now=1011)
        self.assertEqual((returned["state"], returned["late"]), ("completed", False))
        self.assertEqual(self.ledger.apply_reflection(self.submission(), now=1012), returned)
        jobs, proposals = self.ledger.reflection_records()
        self.assertEqual(jobs[0]["state"], "completed")
        self.assertEqual(proposals[0]["id"], "proposal-1")
        self.assertEqual(self.ledger.memory_records("procedure"), ())
        self.assertEqual(self.ledger.snapshot(now=1012)["spent_inputs"], 0)
        self.ledger.close()
        self.ledger = MissionLedger(self.path, now=1012)
        self.assertEqual(self.ledger.reflection_records(), (jobs, proposals))

    def test_expiry_retains_late_output_and_never_refunds_claim_window(self):
        self.offer()
        self.offer(2)
        self.ledger.apply_reflection(command(), now=1001)
        self.ledger.expire_reflection(now=1182)
        returned = self.ledger.apply_reflection(self.submission(), now=1183)
        self.assertEqual((returned["state"], returned["late"]), ("expired", True))
        with self.assertRaises(BudgetError):
            self.ledger.apply_reflection(command("second-claim", job_id="job-2"), now=1184)
        self.assertEqual(self.ledger.snapshot(now=1184)["spent_inputs"], 0)

    def test_timely_software_receipt_remains_timely_after_writer_queue_delay(self):
        self.offer()
        self.ledger.apply_reflection(command(), now=1001)
        self.ledger.expire_reflection(now=1182)
        result = self.ledger.apply_reflection(self.submission(), now=1183, received_at=1100)
        self.assertEqual((result["state"], result["late"], result["observed_claim_elapsed_seconds"]),
                         ("completed", False, 99))
        self.ledger.close()
        self.ledger = MissionLedger(self.path, now=1184)
        self.assertEqual(self.ledger.reflection_records()[0][0]["state"], "completed")

    def test_restart_keeps_claimed_compute_unknown_and_offered_work_unreviewed(self):
        self.offer()
        self.offer(2)
        self.ledger.apply_reflection(command(), now=1001)
        self.ledger.close()
        self.ledger = MissionLedger(self.path, now=1002)
        jobs, _ = self.ledger.reflection_records()
        self.assertEqual([row["state"] for row in jobs], ["unknown", "unreviewed"])
        self.assertEqual(jobs[0]["deadline"], 1181)
        with self.assertRaises(ContractError):
            self.ledger.apply_reflection(command("renew-claim"), now=1003)

    def test_job_must_match_original_rows_cutoff_version_and_source_linkage(self):
        original = self.offer()
        for changes in (dict(id="different", after_sequence=0), dict(id="different", through_sequence=2),
                        dict(id="different", memory_version=1), dict(id="different", sources=[dict(mission_id="foreign", source_id="source-1")])):
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                self.ledger.append_reflection_job(original | changes, now=1001)
        self.assertEqual(len(self.ledger.reflection_records()[0]), 1)

    @pytest.mark.assurance_advice
    def test_conflicting_command_and_proposal_cutoff_refuse_without_adoption(self):
        self.offer()
        self.ledger.apply_reflection(command(), now=1001)
        with self.assertRaises(ContractError):
            self.ledger.apply_reflection(command(job_id="unknown-job"), now=1002)
        with self.assertRaises(ReflectionRefusal):
            self.ledger.apply_reflection(self.submission(cutoff_sequence=2), now=1002)
        self.assertEqual(self.ledger.reflection_records()[1], ())
        self.assertEqual(self.ledger.memory_records("procedure"), ())

    def test_terminal_expiry_does_not_mutate_sealed_history(self):
        self.offer()
        self.ledger.apply_reflection(command(), now=1001)
        self.ledger.finish_mission("stopped", epoch=0, request_id=None, reason="Synthetic ending", now=1002)
        before = (self.ledger.path.read_bytes(), self.ledger.reflection_records(), self.ledger.snapshot(now=1002))
        self.ledger.expire_reflection(now=1182)
        after = (self.ledger.path.read_bytes(), self.ledger.reflection_records(), self.ledger.snapshot(now=1002))
        self.assertEqual(before, after)

    def test_reopen_refuses_changed_claim_receipt_actor_or_orphan_job(self):
        self.offer()
        self.ledger.apply_reflection(command(), now=1001)
        original = self.ledger._db.execute("SELECT payload,result FROM reflection_commands").fetchone()
        for payload, result in ((original[0], "{}"),
                (canonical(command(reflector_id="foreign-reflector")), original[1]),
                (canonical(command(job_id="orphan-job")), original[1])):
            with self.subTest(payload=payload, result=result):
                self.ledger._db.execute("UPDATE reflection_commands SET payload=?,result=?", (payload, result))
                with self.assertRaises(ContractError):
                    self.ledger._verify_reflection(self.admission, self.ledger.snapshot(now=1001))
        self.ledger._db.execute("UPDATE reflection_commands SET payload=?,result=?", original)
        self.ledger._verify_reflection(self.admission, self.ledger.snapshot(now=1001))

    def test_original_trajectory_uses_canonical_data_not_numeric_python_equality(self):
        original = self.offer()
        changed = deepcopy(original)
        changed["trajectory"][0]["result"]["flag"] = 1.0
        with self.assertRaisesRegex(ContractError, "differs"):
            self.ledger._reflection_trace(changed)

    def test_proposal_identity_cannot_be_reused_by_a_second_job(self):
        self.ledger.close()
        extended = replace(self.admission, learning=LearningPolicy(procedure()["environment"],
            reflector_id="reflector-a", reflection_limits=ReflectionLimits(total_seconds=360)))
        self.ledger = MissionLedger(self.path.parent / "two-jobs", admission=extended, now=1000)
        self.offer()
        self.offer(2)
        self.ledger.apply_reflection(command(), now=1001)
        self.ledger.apply_reflection(self.submission(), now=1002)
        self.ledger.apply_reflection(command("second-claim", job_id="job-2"), now=1003)
        second = self.submission()
        second.update(command_id="second-submit", job_id="job-2")
        output = second["proposal"]
        output.update(job_id="job-2", cutoff_sequence=2)
        output["candidates"][0]["support"][0].update(request_ids=["request-2"], source_ids=["source-2"])
        output["notes"][0].update(request_ids=["request-2"], source_refs=[dict(mission_id="mission-a", source_id="source-2")])
        with self.assertRaisesRegex(ContractError, "proposal identity"):
            self.ledger.apply_reflection(second, now=1004)
        self.ledger._verify_reflection(extended, self.ledger.snapshot(now=1004))


    def test_rejected_unknown_job_is_durable_idempotent_and_does_not_charge_work(self):
        self.offer()
        value = command(job_id="unknown-job")
        before_jobs = self.ledger._db.execute("SELECT * FROM reflection_jobs").fetchall()
        with self.assertRaises(ReflectionRefusal):
            self.ledger.apply_reflection(value, now=1001, received_at=1000.5)
        original = self.ledger.record_reflection_rejection(value, "No original job", now=1001, received_at=1000.5)
        self.assertEqual(original, dict(status="rejected", reason="No original job", grants_authority=False))
        self.assertEqual(self.ledger.record_reflection_rejection(value, "Later reason", now=1002, received_at=1002), original)
        self.assertEqual(self.ledger.apply_reflection(value, now=1002), original)
        expected = (dict(command=value, result=original, received_at=1000.5),)
        self.assertEqual(self.ledger.reflection_command_records(), expected)
        self.assertEqual(self.ledger._db.execute("SELECT * FROM reflection_jobs").fetchall(), before_jobs)
        self.assertEqual(self.ledger.memory_records("procedure"), ())
        self.assertEqual(self.ledger.snapshot(now=1002)["spent_inputs"], 0)
        with self.assertRaisesRegex(ContractError, "identity changed"):
            self.ledger.record_reflection_rejection(command(), "Conflict", now=1002, received_at=1002)
        self.assertEqual(self.ledger.reflection_command_records(), expected)
        self.ledger.close()
        self.ledger = MissionLedger(self.path, now=1002)
        self.assertEqual(self.ledger.reflection_command_records(), expected)
        self.assertEqual(self.ledger.record_reflection_rejection(value, "After reopen", now=1003, received_at=1003), original)

    def test_rejection_requires_exact_valid_admitted_body_reason_and_receipt(self):
        invalid = [command() | {"extra": True}, command(schema="reflection/0"),
                   command(mission_id="foreign"), command(reflector_id="foreign")]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ContractError):
                self.ledger.record_reflection_rejection(value, "Refused", now=1001, received_at=1001)
        for reason in ("", "x" * 1025, None):
            with self.subTest(reason=reason), self.assertRaises(ContractError):
                self.ledger.record_reflection_rejection(command(), reason, now=1001, received_at=1001)
        for received_at in (1002, -1, float("nan"), True):
            with self.subTest(received_at=received_at), self.assertRaises(ContractError):
                self.ledger.record_reflection_rejection(command(), "Refused", now=1001, received_at=received_at)
        self.assertEqual(self.ledger.reflection_command_records(), ())

    def test_rejection_retention_cap_includes_accepted_commands(self):
        self.offer()
        accepted = self.ledger.apply_reflection(command(), now=1001)
        for number in range(127):
            self.ledger.record_reflection_rejection(command(f"refused-{number}", job_id="unknown-job"),
                "No original job", now=1002, received_at=1002)
        self.assertEqual(len(self.ledger.reflection_command_records()), 128)
        with self.assertRaises(BudgetError):
            self.ledger.record_reflection_rejection(command("overflow", job_id="unknown-job"),
                "No original job", now=1003, received_at=1003)
        self.assertEqual(self.ledger.record_reflection_rejection(command(), "Already retained", now=1003, received_at=1003), accepted)
        with self.assertRaises(ReflectionBudgetRefusal):
            self.ledger.apply_reflection(command("overflow"), now=1003)
        self.assertEqual(self.ledger.snapshot(now=1003)["spent_inputs"], 0)
        self.ledger._verify_reflection(self.admission, self.ledger.snapshot(now=1003))

    def test_restoration_returns_copies_of_original_commands_results_and_receipts(self):
        self.offer()
        self.ledger.apply_reflection(command(), now=1001, received_at=1000.5)
        self.ledger.apply_reflection(self.submission(), now=1003, received_at=1002)
        original = self.ledger.reflection_command_records()
        changed = self.ledger.reflection_command_records()
        changed[0]["result"]["deadline"] = 9999
        changed[0]["received_at"] = 9999
        changed[1]["command"]["proposal"]["notes"][0]["text"] = "Changed copy"
        self.assertEqual(self.ledger.reflection_command_records(), original)
        self.ledger.close()
        self.ledger = MissionLedger(self.path, now=1004)
        self.assertEqual(self.ledger.reflection_command_records(), original)

    def test_reopen_refuses_tampered_rejection_records(self):
        value = command(job_id="unknown-job")
        result = self.ledger.record_reflection_rejection(value, "No original job", now=1001, received_at=1000.5)
        original = (canonical(value), canonical(result), 1000.5)
        tampered = [(canonical(value), canonical(result | changes), 1000.5)
                    for changes in (dict(reason=""), dict(reason="x" * 1025), dict(reason=3),
                                    dict(grants_authority=0), dict(extra=True), dict(status="accepted"))]
        tampered += [(canonical(value | {"reflector_id": "foreign"}), original[1], 1000.5),
                     (canonical(value | {"mission_id": "foreign"}), original[1], 1000.5),
                     (original[0] + " ", original[1], 1000.5),
                     (original[0], original[1] + " ", 1000.5),
                     (original[0], original[1], 1002)]
        for payload, output, receipt in tampered:
            with self.subTest(payload=payload, output=output, receipt=receipt):
                self.ledger._db.execute("UPDATE reflection_commands SET payload=?,result=?,received_at=?", (payload, output, receipt))
                with self.assertRaises(ContractError):
                    self.ledger._verify_reflection(self.admission, self.ledger.snapshot(now=1001))
        self.ledger._db.execute("UPDATE reflection_commands SET payload=?,result=?,received_at=?", original)
        self.ledger._verify_reflection(self.admission, self.ledger.snapshot(now=1001))
        self.ledger._db.execute("UPDATE reflection_commands SET result=?", (canonical(result | dict(grants_authority=True)),))
        self.ledger.close()
        with self.assertRaises(ContractError):
            MissionLedger(self.path, now=1002)

    def test_rejections_cannot_replace_original_accepted_claim_or_submission_coverage(self):
        self.offer()
        self.ledger.apply_reflection(command(), now=1001)
        self.ledger.apply_reflection(self.submission(), now=1002)
        original = self.ledger.reflection_command_records()
        rejected = canonical(dict(status="rejected", reason="Refused", grants_authority=False))
        for row in original:
            identity = row["command"]["command_id"]
            with self.subTest(identity=identity):
                self.ledger._db.execute("UPDATE reflection_commands SET result=? WHERE id=?", (rejected, identity))
                with self.assertRaisesRegex(ContractError, "lost its original durable"):
                    self.ledger._verify_reflection(self.admission, self.ledger.snapshot(now=1002))
                self.ledger._db.execute("UPDATE reflection_commands SET result=? WHERE id=?", (canonical(row["result"]), identity))
        self.ledger._verify_reflection(self.admission, self.ledger.snapshot(now=1002))

    def test_terminal_settlement_preserves_original_windows_charges_and_results(self):
        self.offer()
        self.offer(2)
        accepted = self.ledger.apply_reflection(command(), now=1001)
        before = self.ledger._db.execute("SELECT payload,claimed_at,deadline,charged_seconds,proposal FROM reflection_jobs ORDER BY sequence").fetchall()
        self.ledger.finish_mission("stopped", epoch=0, request_id=None, reason="Synthetic ending", now=1002)
        self.assertEqual([row["state"] for row in self.ledger.reflection_records()[0]], ["unknown", "unreviewed"])
        self.assertEqual(self.ledger._db.execute("SELECT payload,claimed_at,deadline,charged_seconds,proposal FROM reflection_jobs ORDER BY sequence").fetchall(), before)
        self.assertEqual(self.ledger.reflection_command_records()[0]["result"], accepted)
        self.ledger._verify_reflection(self.admission, self.ledger.snapshot(now=1002))
        sealed = self.ledger.path.read_bytes()
        self.ledger.settle_reflection(now=1003)
        self.ledger.expire_reflection(now=1200)
        self.assertEqual(self.ledger.apply_reflection(command(), now=1200), accepted)
        for call in (lambda: self.ledger.apply_reflection(self.submission(), now=1200),
                     lambda: self.ledger.record_reflection_rejection(command("late"), "Closed", now=1200, received_at=1200)):
            with self.assertRaisesRegex(ContractError, "Sealed terminal"):
                call()
        self.assertEqual(self.ledger.path.read_bytes(), sealed)
        self.ledger.close()
        self.ledger = MissionLedger(self.path, now=1200)
        self.assertEqual([row["state"] for row in self.ledger.reflection_records()[0]], ["unknown", "unreviewed"])
        self.assertEqual(self.ledger.reflection_command_records()[0]["result"], accepted)

    def test_explicit_settlement_leaves_completed_proposals_and_receipts_unchanged(self):
        self.offer()
        self.ledger.apply_reflection(command(), now=1001)
        self.ledger.apply_reflection(self.submission(), now=1002)
        self.offer(2, now=1002)
        before = self.ledger.reflection_command_records()
        proposal_before = self.ledger.reflection_records()[1]
        self.ledger.settle_reflection(now=1003)
        jobs, proposals = self.ledger.reflection_records()
        self.assertEqual([row["state"] for row in jobs], ["completed", "unreviewed"])
        self.assertEqual(proposals, proposal_before)
        self.assertEqual(self.ledger.reflection_command_records(), before)
        self.ledger._verify_reflection(self.admission, self.ledger.snapshot(now=1003))

    def test_semantic_refusal_is_distinct_from_storage_and_clock_failure(self):
        self.offer()
        with self.assertRaises(ReflectionRefusal):
            self.ledger.apply_reflection(command(job_id="missing"), now=1001)
        with self.assertRaises(ReflectionRefusal):
            self.ledger.apply_reflection(command() | {"extra": True}, now=1001)
        for now, receipt in ((float("nan"), 1001), (1000, 1002), (999, 999)):
            with self.subTest(now=now, receipt=receipt), self.assertRaises(LedgerError) as raised:
                self.ledger.apply_reflection(command(), now=now, received_at=receipt)
            self.assertNotIsInstance(raised.exception, ReflectionRefusal)
        self.ledger._db.execute("CREATE TEMP TRIGGER refuse_claim BEFORE UPDATE ON reflection_jobs BEGIN SELECT RAISE(ABORT, 'controlled storage failure'); END")
        with self.assertRaises(LedgerError) as raised:
            self.ledger.apply_reflection(command(), now=1001)
        self.assertNotIsInstance(raised.exception, ReflectionRefusal)
        self.assertIsInstance(raised.exception.__cause__, sqlite3.Error)
        self.assertEqual(self.ledger.reflection_command_records(), ())


    def test_terminal_settlement_and_state_change_are_one_transaction(self):
        self.offer()
        self.offer(2)
        self.ledger.apply_reflection(command(), now=1001)
        before_jobs = self.ledger._db.execute("SELECT * FROM reflection_jobs").fetchall()
        before_commands = self.ledger.reflection_command_records()
        self.ledger._db.execute("CREATE TEMP TRIGGER refuse_settlement BEFORE UPDATE ON reflection_jobs WHEN NEW.state='unreviewed' BEGIN SELECT RAISE(ABORT, 'controlled settlement failure'); END")
        with self.assertRaisesRegex(LedgerError, "controlled settlement failure"):
            self.ledger.finish_mission("stopped", epoch=0, request_id=None, reason="Synthetic ending", now=1002)
        self.assertNotIn(self.ledger.snapshot(now=1002)["phase"], ("stopped", "failed", "completed"))
        self.assertEqual(self.ledger._db.execute("SELECT * FROM reflection_jobs").fetchall(), before_jobs)
        self.assertEqual(self.ledger.reflection_command_records(), before_commands)
        self.ledger._db.execute("DROP TRIGGER refuse_settlement")
        self.ledger.finish_mission("stopped", epoch=0, request_id=None, reason="Synthetic ending", now=1002)
        self.ledger._db.execute("UPDATE reflection_jobs SET state='claimed' WHERE id='job-1'")
        self.ledger.close()
        with self.assertRaisesRegex(ContractError, "job identity/cutoff/state"):
            MissionLedger(self.path, now=1003)
