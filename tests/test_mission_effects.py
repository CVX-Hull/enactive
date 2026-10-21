"""Closed effect/write/reopen/capacity probes, never native delivery evidence."""
from contextlib import closing
import copy
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

from harness.gameplay.contracts import ContractError
from harness.gameplay.mission_contracts import canonical, validate_effect_reconciliation
from harness.gameplay.mission_ledger import MissionLedger
from tests import test_mission_ledger as fixtures
from tests.test_mission_ledger import delivery_resolution, published_receipt, reconcile_fixture


class EffectTests(unittest.TestCase):
    setUp = fixtures.LedgerTests.setUp
    active_request = fixtures.LedgerTests.active_request
    prepared = fixtures.LedgerTests.prepared

    def unknown(self):
        self.prepared(native=True)
        self.ledger.settle_primitive("logical-1", "unknown", {"status": "timeout", **published_receipt()}, now=1004)

    def test_old_sources_and_note_is_not_a_current_effect(self):
        self.unknown()
        old = dict(sources=["fresh-after"], note="A later frame is insufficient")
        with self.assertRaises(ContractError): validate_effect_reconciliation(old)
        with self.assertRaises(ContractError):
            self.ledger.reconcile_effect("logical-1", proof=old, sources=("fresh-after",), note="No typed custody", now=1005)
        self.assertIsNone(self.ledger.primitive("logical-1")["effect"])
        self.assertEqual(self.ledger.snapshot(now=1005)["unreconciled"], 1)

    def test_proof_cannot_replace_original_receipt_custody_or_collection_window(self):
        self.unknown()
        proof, sources = delivery_resolution(self.ledger, now=1005)
        wrong_native = json.loads(proof["native_request_json"])
        wrong_native["action"] = "LEFT"
        changes = [dict(native_request_json=canonical(wrong_native)), dict(actor_id="other-player"),
            dict(root_id=proof["reconciliation_request_id"]), dict(operator_pause_generation=1),
            dict(game_anchor_source_id="fresh-after"), dict(collection_received_monotonic=10.25),
            dict(collection_deadline_monotonic=11), dict(native_request_id="other-native")]
        original = self.ledger.primitive("logical-1")
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ContractError):
                self.ledger.reconcile_effect("logical-1", proof={**proof, **change}, sources=sources,
                    note="Contradictory synthetic proof must reject", now=1005)
            self.assertEqual(self.ledger.primitive("logical-1"), original)

    def test_orphan_proof_survives_reopen_without_completed_readmission_owner(self):
        self.unknown()
        proof, sources = delivery_resolution(self.ledger, now=1005)
        self.ledger.reconcile_effect("logical-1", proof=proof, sources=sources, note="Crash after typed proof commit", now=1005)
        self.ledger.close()
        self.ledger = MissionLedger(self.directory, now=1006)
        self.assertEqual(self.ledger.primitive("logical-1")["state"], "unknown")
        self.assertIsNone(self.ledger.request(proof["reconciliation_request_id"])["result"])
        self.assertEqual(self.ledger.snapshot(now=1006)["phase"], "paused")
        self.assertEqual(self.ledger.snapshot(now=1006)["spent_inputs"], 1)

    def test_reopen_rejects_coherently_changed_proof_against_original_receipt(self):
        self.unknown()
        reconcile_fixture(self.ledger, now=1005, note="Retained synthetic custody")
        self.ledger.close()
        original = self.ledger.path.read_bytes()
        for field, value in (("actor_id", "other-player"), ("operator_pause_generation", 1),
                             ("game_anchor_source_id", "fresh-after"), ("native_request_id", "other-native")):
            with self.subTest(field=field):
                self.ledger.path.write_bytes(original)
                with closing(sqlite3.connect(self.ledger.path)) as db, db:
                    effect = json.loads(db.execute("SELECT effect FROM primitives").fetchone()[0])
                    effect["proof"][field] = value
                    result = json.loads(db.execute("SELECT result FROM requests WHERE id='resolve-logical-1'").fetchone()[0])
                    result["reconciliation"] = copy.deepcopy(effect["proof"])
                    db.execute("UPDATE primitives SET effect=?", (canonical(effect),))
                    db.execute("UPDATE requests SET result=? WHERE id='resolve-logical-1'", (canonical(result),))
                before = self.ledger.path.read_bytes()
                with self.assertRaises(ContractError): MissionLedger(self.directory, now=1006)
                self.assertEqual(self.ledger.path.read_bytes(), before)

    def test_large_closed_effect_and_its_result_use_existing_reserved_sqlite_capacity(self):
        self.ledger.close()
        self.directory = Path(self.tmp.name) / "effect-capacity"
        with patch("harness.gameplay.mission_ledger.MAX_DATABASE_BYTES", 512 * 1024):
            self.ledger = MissionLedger(self.directory, admission=self.a, now=1000)
            self.prepared(native=True)
            receipt = published_receipt()
            native = json.loads(receipt["native_request_json"])
            native["frame"] = '"' * 1700
            receipt["native_request_json"] = canonical(native)
            self.assertLessEqual(len(receipt["native_request_json"].encode()), 4096)
            self.ledger.settle_primitive("logical-1", "unknown", receipt, now=1004)
            proof, sources = delivery_resolution(self.ledger, now=1005)
            db = self.ledger._db
            db.execute("CREATE TABLE storage_pressure (payload BLOB)")
            while True:
                try: db.execute("INSERT INTO storage_pressure VALUES (zeroblob(4096))")
                except sqlite3.OperationalError as exc:
                    self.assertIn("full", str(exc))
                    break
            note = "\x00" * 1024
            self.ledger.reconcile_effect("logical-1", proof=proof, sources=sources, note=note, now=1006)
            effect = self.ledger.primitive("logical-1")["effect"]
            self.assertGreater(len(canonical(effect).encode()), 4096)
            self.ledger.complete_request(proof["reconciliation_request_id"], "completed", dict(
                reconciliation=proof, source_ids=list(sources), reason=note, grants_authority=False), now=1006)
            self.ledger._verify(self.a)
            self.assertEqual(self.ledger.snapshot(now=1006)["spent_inputs"], 1)
            self.assertEqual(self.ledger.primitive("logical-1")["result"], receipt)


if __name__ == "__main__":
    unittest.main()
