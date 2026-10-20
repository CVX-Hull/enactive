"""SQLite failure/restart probes. No native dispatch or gameplay is simulated."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from harness.gameplay.contracts import ContractError
from harness.gameplay.mission_contracts import CleanupReserve, MissionLimits
from harness.gameplay.mission_ledger import BudgetError, LedgerError, MissionLedger
from tests.test_mission_contracts import admission, claim, request, skill


def intent(**changes):
    values = {"kind": "action", "value": "RIGHT", "expected_session": "native-session",
              "expected_revision": 30, "expected_boundary_id": "boundary-1",
              "source_before": "source-1", "reservation_id": "reservation-1"}
    values.update(changes)
    return values


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name) / "mission"
        self.a = admission()
        self.ledger = MissionLedger(self.directory, admission=self.a, now=1000.0)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(lambda: self.ledger.close())

    def reopen(self, now=1010):
        self.ledger.close()
        self.ledger = MissionLedger(self.directory, admission=self.a, now=now)
        return self.ledger

    def active_request(self, value=None, now=1001):
        self.ledger.activate(epoch=self.ledger.snapshot(now=now)["epoch"], player_id="player-test", now=now)
        return self.ledger.begin_request(value or skill(), now=now)

    def prepared(self, *, native=False):
        self.active_request()
        out = self.ledger.prepare_primitive("request-1", "logical-1", intent(), now=1002)
        self.assertTrue(out["created"])
        if native: self.ledger.published("logical-1", "native-uuid-1", now=1003)

    def test_create_reopen_preserves_deadline_scope_and_no_authority(self):
        old = self.ledger.snapshot(now=1000)
        new = self.reopen().snapshot(now=1010)
        self.assertEqual(old["deadline"], 8200)
        self.assertEqual(new["deadline"], old["deadline"])
        self.assertEqual(new["phase"], "paused")
        self.assertEqual(new["epoch"], 1)
        self.assertFalse(new["grants_authority"])
        self.assertEqual(new["remaining_inputs"], 1500)
        with self.assertRaises(LedgerError): self.ledger.activate(epoch=0, player_id="player-test", now=1010)
        with self.assertRaises(LedgerError): self.ledger.activate(epoch=1, player_id="other-player", now=1010)

    def test_single_writer_and_wrong_admission_reject_without_rewriting(self):
        with self.assertRaises(LedgerError): MissionLedger(self.directory, admission=self.a, now=1001)
        self.ledger.close()
        before = self.ledger.path.read_bytes()
        with self.assertRaises(LedgerError):
            MissionLedger(self.directory, admission=replace(self.a, objective="New scope"), now=1001)
        self.assertEqual(self.ledger.path.read_bytes(), before)
        self.reopen(now=1002)

    def test_unsupported_database_version_rejects_without_migration(self):
        self.ledger.close()
        with sqlite3.connect(self.ledger.path) as connection: connection.execute("PRAGMA user_version=999")
        before = hashlib.sha256(self.ledger.path.read_bytes()).hexdigest()
        with self.assertRaises(LedgerError): MissionLedger(self.directory, now=1001)
        self.assertEqual(hashlib.sha256(self.ledger.path.read_bytes()).hexdigest(), before)

    def test_intent_and_charge_are_committed_before_publication(self):
        self.prepared()
        with sqlite3.connect(self.ledger.path) as reader:
            row = reader.execute("SELECT state,native_id FROM primitives WHERE id='logical-1'").fetchone()
            state = json.loads(reader.execute("SELECT value FROM metadata WHERE key='state'").fetchone()[0])
        self.assertEqual(row, ("prepared", None))
        self.assertEqual(state["spent_inputs"], 1)
        self.assertFalse(self.ledger.snapshot(now=1002)["grants_authority"])

    def test_crash_before_and_after_publication_never_replays_or_refunds(self):
        for published in [False, True]:
            with self.subTest(published=published), tempfile.TemporaryDirectory() as tmp:
                with MissionLedger(Path(tmp), admission=self.a, now=1000) as ledger:
                    ledger.activate(epoch=0, player_id="player-test", now=1000)
                    ledger.begin_request(skill(), now=1001)
                    ledger.prepare_primitive("request-1", "logical-1", intent(), now=1002)
                    if published: ledger.published("logical-1", "native-uuid-1", now=1003)
                with MissionLedger(Path(tmp), admission=self.a, now=1010) as reopened:
                    self.assertEqual(reopened.primitive("logical-1")["state"], "unknown")
                    self.assertEqual(reopened.primitive("logical-1")["native_id"], "native-uuid-1" if published else None)
                    self.assertEqual(reopened.request("request-1")["state"], "unknown")
                    self.assertEqual(reopened.snapshot(now=1010)["spent_inputs"], 1)
                    self.assertFalse(reopened.begin_request(skill(), now=1010)["created"])
                    self.assertFalse(reopened.prepare_primitive("request-1", "logical-1", intent(), now=1010)["created"])
                    with self.assertRaises(LedgerError): reopened.activate(epoch=1, player_id="player-test", now=1010)
                    with self.assertRaises(LedgerError): reopened.prepare_primitive("request-1", "logical-2", intent(), now=1010)

    def test_duplicate_request_and_logical_id_never_charge_again(self):
        self.prepared()
        self.assertFalse(self.ledger.begin_request(skill(), now=1003)["created"])
        self.assertFalse(self.ledger.prepare_primitive("request-1", "logical-1", intent(), now=1003)["created"])
        self.assertEqual(self.ledger.snapshot(now=1003)["spent_inputs"], 1)
        with self.assertRaises(LedgerError): self.ledger.begin_request(skill(expected_revision=31), now=1003)
        with self.assertRaises(LedgerError): self.ledger.prepare_primitive("request-1", "logical-1", intent(value="LEFT"), now=1003)

    def test_concurrent_identical_request_has_one_admission(self):
        outputs, errors = [], []
        barrier = threading.Barrier(2)
        def run():
            try:
                barrier.wait()
                outputs.append(self.ledger.begin_request(skill(), now=1001)["created"])
            except Exception as exc: errors.append(exc)
        threads = [threading.Thread(target=run) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join(2)
        self.assertEqual(errors, [])
        self.assertEqual(sorted(outputs), [False, True])

    def test_budget_and_cleanup_reserve_persist(self):
        self.ledger.close()
        self.a = admission(limits=MissionLimits(inputs=3), cleanup_reserve=CleanupReserve(inputs=1))
        self.directory = Path(self.tmp.name) / "small"
        self.ledger = MissionLedger(self.directory, admission=self.a, now=1000)
        self.active_request()
        for n in [1, 2]:
            self.ledger.prepare_primitive("request-1", f"logical-{n}", intent(), now=1001+n)
            self.ledger.settle_primitive(f"logical-{n}", "returned", {"status": "ready"}, now=1001+n)
        with self.assertRaises(BudgetError): self.ledger.prepare_primitive("request-1", "logical-3", intent(), now=1004)
        self.assertEqual(self.ledger.snapshot(now=1004)["spent_inputs"], 2)
        state = self.ledger.begin_finishing(epoch=0, reason="Normal ending", now=1004)
        cleanup = request("lifecycle", request_id="cleanup", epoch=state["epoch"], operation="finish",
                          world="test-world", character="test-person", sources=["source-1"], expected_session="native-session",
                          expected_revision=30, expected_boundary_id="boundary-1", limits={"primitives": 2, "wall_seconds": 120, "game_seconds": 1})
        self.ledger.begin_request(cleanup, now=1004)
        self.ledger.prepare_primitive("cleanup", "logical-3", intent(), now=1005, cleanup=True)
        self.ledger.settle_primitive("logical-3", "returned", {"status": "ready"}, now=1006)
        with self.assertRaises(BudgetError): self.ledger.prepare_primitive("cleanup", "logical-4", intent(), now=1007, cleanup=True)
        self.reopen(now=1010)
        self.assertEqual(self.ledger.snapshot(now=1010)["remaining_inputs"], 0)

    def test_request_ceiling_and_original_operation_deadline(self):
        value = skill(limits={"primitives": 1, "wall_seconds": 10, "game_seconds": 100})
        self.active_request(value)
        self.ledger.prepare_primitive("request-1", "logical-1", intent(), now=1002)
        self.ledger.settle_primitive("logical-1", "not_dispatched", {"reason": "known rejection"}, now=1003)
        with self.assertRaises(BudgetError): self.ledger.prepare_primitive("request-1", "logical-2", intent(), now=1004)
        self.assertEqual(self.ledger.request("request-1")["deadline"], 1011)
        self.assertFalse(self.ledger.begin_request(value, now=1020)["created"])
        with self.assertRaises(BudgetError): self.ledger.prepare_primitive("request-1", "logical-2", intent(), now=1020)
        self.assertEqual(self.ledger.snapshot(now=1020)["spent_inputs"], 1)

    def test_rollback_and_expiry_do_not_renew_clocks(self):
        self.active_request()
        with self.assertRaises(BudgetError): self.ledger.begin_request(skill(request_id="backward"), now=999)
        self.assertFalse(self.ledger.snapshot(now=999)["clock_valid"])
        with self.assertRaises(BudgetError): self.ledger.activate(epoch=0, player_id="player-test", now=7301)
        with self.assertRaises(BudgetError): self.ledger.prepare_primitive("request-1", "late", intent(), now=8201)
        self.assertEqual(self.ledger.snapshot(now=8201)["deadline"], 8200)

    def test_unknown_ack_remains_unknown_after_separate_effect_and_result(self):
        self.prepared(native=True)
        self.ledger.settle_primitive("logical-1", "unknown", {"status": "timeout"}, now=1004)
        with self.assertRaises(LedgerError): self.ledger.complete_request("request-1", "completed", {"goal": "reached"}, now=1005)
        self.ledger.reconcile_effect("logical-1", sources=("fresh-after",), note="Controller slots settled; effect separately observed", now=1005)
        self.ledger.complete_request("request-1", "completed", {"goal": "reached", "delivery": "unknown"}, now=1006)
        self.assertEqual(self.ledger.primitive("logical-1")["state"], "unknown")
        self.assertEqual(self.ledger.primitive("logical-1")["result"], {"status": "timeout"})
        with self.assertRaises(LedgerError): self.ledger.settle_primitive("logical-1", "returned", {"status": "ready"}, now=1007)
        self.assertEqual(self.ledger.snapshot(now=1007)["phase"], "paused")
        self.assertEqual(self.reopen().primitive("logical-1")["state"], "unknown")

    def test_failure_before_publication_rolls_back_cost_and_intent(self):
        self.active_request()
        self.ledger._db.execute("CREATE TRIGGER fail_charge BEFORE UPDATE ON metadata WHEN NEW.key='state' AND json_extract(NEW.value,'$.spent_inputs')=1 BEGIN SELECT RAISE(ABORT,'storage fault'); END")
        with self.assertRaises(LedgerError): self.ledger.prepare_primitive("request-1", "logical-1", intent(), now=1002)
        self.assertEqual(self.ledger.snapshot(now=1002)["spent_inputs"], 0)
        with self.assertRaises(LedgerError): self.ledger.primitive("logical-1")

    def test_failure_settling_published_input_reopens_as_unknown(self):
        self.prepared(native=True)
        self.ledger._db.execute("CREATE TRIGGER fail_settle BEFORE UPDATE OF result ON primitives BEGIN SELECT RAISE(ABORT,'storage fault'); END")
        with self.assertRaises(LedgerError): self.ledger.settle_primitive("logical-1", "returned", {"status": "ready"}, now=1004)
        self.assertEqual(self.ledger.primitive("logical-1")["state"], "published")
        self.ledger._db.execute("DROP TRIGGER fail_settle")
        self.reopen()
        self.assertEqual(self.ledger.primitive("logical-1")["state"], "unknown")
        self.assertEqual(self.ledger.snapshot(now=1010)["spent_inputs"], 1)

    def test_retention_and_corrupt_cost_reject_without_repair(self):
        self.ledger.append_memory("event-1", "claim", claim(), now=1001)
        self.assertEqual(self.ledger.append_memory("event-1", "claim", claim(), now=1002), 1)
        with self.assertRaises(LedgerError): self.ledger.append_memory("event-2", "claim", claim(text="changed"), now=1002)
        with self.assertRaises(LedgerError): self.ledger.append_memory("event-1", "claim", claim(text="changed"), now=1002)
        self.assertEqual(self.reopen().memory_records("claim")[0]["entry"], claim())
        self.ledger.close()
        with sqlite3.connect(self.ledger.path) as connection:
            state = json.loads(connection.execute("SELECT value FROM metadata WHERE key='state'").fetchone()[0])
            state["spent_inputs"] = 1
            connection.execute("UPDATE metadata SET value=? WHERE key='state'", (json.dumps(state),))
        with self.assertRaises(LedgerError): MissionLedger(self.directory, now=1020)

    def test_read_only_or_unadmitted_request_cannot_become_input(self):
        self.active_request()
        self.ledger.begin_request(request(request_id="observe-only"), now=1002)
        with self.assertRaises(LedgerError):
            self.ledger.prepare_primitive("observe-only", "bad-input", intent(), now=1003)
        with self.assertRaises(LedgerError):
            self.ledger.begin_request({"schema": "mission/1", "kind": "status", "mission_id": "mission-test"}, now=1003)
        with self.assertRaises(LedgerError):
            self.ledger.begin_request(skill(mission_id="other", goal={"scope": {"mission_id": "other", "session": "native-session", "coordinate_epoch": 0}, "target": [2, -3, 0]}), now=1003)
        self.ledger.close()
        self.directory = Path(self.tmp.name) / "restricted"
        self.a = admission(allowed_skills=("inspect",), allowed_lifecycle=("finish",))
        self.ledger = MissionLedger(self.directory, admission=self.a, now=1000)
        with self.assertRaises(LedgerError): self.ledger.begin_request(skill(), now=1001)

    def test_post_deadline_control_remains_readable_without_renewing_input_time(self):
        self.ledger.begin_request(request(request_id="late-observe"), now=8300)
        with self.assertRaises(BudgetError): self.ledger.begin_request(skill(), now=8300)
        self.assertEqual(self.ledger.snapshot(now=8300)["deadline"], 8200)
        self.reopen(now=8301)
        self.assertEqual(self.ledger.snapshot(now=8301)["remaining_wall_seconds"], 0)
        self.assertEqual(self.ledger.request("late-observe")["state"], "unknown")

    def test_late_unknown_receipt_never_resurrects_a_stopped_mission(self):
        self.prepared(native=True)
        self.ledger.finish_mission("stopped", reason="Retained failed attempt", now=1004)
        self.ledger.settle_primitive("logical-1", "unknown", {"status": "timeout"}, now=1005)
        self.ledger.reconcile_effect("logical-1", sources=("fresh-after",), note="Separately observed", now=1006)
        self.ledger.complete_request("request-1", "unknown", {"delivery": "unknown"}, now=1007)
        state = self.ledger.snapshot(now=1007)
        self.assertEqual((state["phase"], state["reason"]), ("stopped", "Retained failed attempt"))
        with self.assertRaises(LedgerError): self.ledger.activate(epoch=state["epoch"], player_id="player-test", now=1007)
        self.assertEqual(self.reopen(now=1006).snapshot(now=1007)["reason"], "Retained failed attempt")

    def test_rejected_expiry_retains_watermark_before_clock_rollback(self):
        self.active_request()
        with self.assertRaises(BudgetError): self.ledger.prepare_primitive("request-1", "late", intent(), now=8201)
        self.assertEqual(self.ledger.snapshot(now=8201)["last_wall"], 8201)
        with self.assertRaises(BudgetError): self.ledger.prepare_primitive("request-1", "rollback", intent(), now=1002)
        self.assertEqual(self.ledger.snapshot(now=8201)["spent_inputs"], 0)
        state = self.reopen(now=1003).snapshot(now=1003)
        self.assertFalse(state["clock_valid"])
        self.assertEqual(state["last_wall"], 8201)

    def test_unknown_operation_without_primitive_revokes_active_phase(self):
        self.active_request()
        self.ledger.complete_request("request-1", "unknown", {"reason": "Unprovable request outcome"}, now=1002)
        state = self.ledger.snapshot(now=1002)
        self.assertEqual((state["phase"], state["epoch"]), ("paused", 1))
        with self.assertRaises(LedgerError): self.ledger.begin_request(skill(request_id="next"), now=1003)

    def test_reopen_rejects_corrupt_intent_effect_result_or_reservation(self):
        self.prepared(native=True)
        self.ledger.settle_primitive("logical-1", "unknown", {"status": "timeout"}, now=1004)
        self.ledger.reconcile_effect("logical-1", sources=("fresh-after",), note="Observed", now=1005)
        self.ledger.close()
        original = self.ledger.path.read_bytes()
        mutations = ["UPDATE primitives SET intent='{}'", "UPDATE primitives SET effect='{}'",
                     "UPDATE primitives SET result='[]'", "UPDATE reservations SET space=zeroblob(10)",
                     "UPDATE primitives SET state='returned'", "UPDATE requests SET result='[]'"]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.ledger.path.write_bytes(original)
                with sqlite3.connect(self.ledger.path) as connection: connection.execute(mutation)
                before = self.ledger.path.read_bytes()
                with self.assertRaises(ContractError): MissionLedger(self.directory, now=1006)
                self.assertEqual(self.ledger.path.read_bytes(), before)

    def test_database_capacity_is_reserved_before_input_and_survives_full_storage(self):
        self.ledger.close()
        self.directory = Path(self.tmp.name) / "capacity"
        with patch("harness.gameplay.mission_ledger.MAX_DATABASE_BYTES", 512 * 1024):
            self.ledger = MissionLedger(self.directory, admission=self.a, now=1000)
            self.prepared(native=True)
            # Exhaust unreserved pages. This is a storage-pressure probe, not an
            # alternative application table or simulated native success.
            db = self.ledger._db
            db.execute("CREATE TABLE storage_pressure (payload BLOB)")
            while True:
                try: db.execute("INSERT INTO storage_pressure VALUES (zeroblob(4096))")
                except sqlite3.OperationalError as exc:
                    self.assertIn("full", str(exc))
                    break
            receipt = {"diagnostic": "x" * 60_000}
            self.ledger.settle_primitive("logical-1", "unknown", receipt, now=1004)
            self.ledger.reconcile_effect("logical-1", sources=("fresh-after",), note="Observed separately", now=1005)
            self.ledger.complete_request("request-1", "partial", receipt, now=1006)
            self.assertEqual(self.ledger.primitive("logical-1")["result"], receipt)
            self.assertEqual(self.ledger.request("request-1")["result"], receipt)
            while True:
                try: db.execute("INSERT INTO storage_pressure VALUES (zeroblob(4096))")
                except sqlite3.OperationalError: break
            with self.assertRaises(LedgerError): self.ledger.begin_request(skill(request_id="too-full", epoch=1), now=1007)
            self.assertEqual(self.ledger.snapshot(now=1007)["spent_inputs"], 1)

    def test_terminal_mission_cannot_restart_or_overwrite_result(self):
        self.ledger.finish_mission("stopped", reason="Known unsupported capability", now=1001)
        self.reopen()
        self.assertEqual(self.ledger.snapshot(now=1010)["phase"], "stopped")
        with self.assertRaises(LedgerError): self.ledger.activate(epoch=1, player_id="player-test", now=1010)
        with self.assertRaises(LedgerError): self.ledger.begin_request(skill(epoch=1), now=1010)
        with self.assertRaises(LedgerError): self.ledger.finish_mission("completed", reason="relabel", now=1010)


if __name__ == "__main__": unittest.main()
