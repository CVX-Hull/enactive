"""SQLite advisory bookkeeping over synthetic requests, not model/game efficacy."""
from pathlib import Path
from copy import deepcopy
from dataclasses import replace
import tempfile
import unittest

from harness.gameplay.contracts import ContractError, canonical
from harness.gameplay.mission_contracts import LearningPolicy, ReflectionLimits
from harness.gameplay.mission_ledger import BudgetError, MissionLedger
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

    def offer(self, number=1):
        request = dict(schema="mission/9", kind="observe", request_id=f"request-{number}", mission_id="mission-a", epoch=0)
        result = dict(source_ids=[f"source-{number}"], grants_authority=False, flag=1)
        self.ledger.begin_request(request, now=1000)
        self.ledger.complete_request(request["request_id"], "completed", result, now=1000)
        value = job(id=f"job-{number}", memory_version=0, after_sequence=number-1, through_sequence=number,
            included_request_ids=[request["request_id"]], trajectory=[dict(request=request, state="completed", result=result)],
            sources=[dict(mission_id="mission-a", source_id=f"source-{number}")])
        return self.ledger.append_reflection_job(value, now=1000)

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

    def test_conflicting_command_and_proposal_cutoff_refuse_without_adoption(self):
        self.offer()
        self.ledger.apply_reflection(command(), now=1001)
        with self.assertRaises(ContractError):
            self.ledger.apply_reflection(command(job_id="unknown-job"), now=1002)
        with self.assertRaises(ContractError):
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
