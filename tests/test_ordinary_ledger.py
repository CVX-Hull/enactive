"""Durable ordinary-entry/physical-selection accounting, without native input."""
from dataclasses import replace
from contextlib import closing
from copy import deepcopy
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from harness.gameplay.contracts import ContractError, canonical
from harness.gameplay.mission_contracts import InputObservation, SourceRevalidation
from harness.gameplay.mission_ledger import LedgerError, MissionLedger
from tests.test_mission_contracts import admission, binding, skill
from tests import test_mission_ledger as fixtures
from tests.test_mission_ledger import intent, known_receipt


class OrdinaryLedgerTests(unittest.TestCase):
    active_request = fixtures.LedgerTests.active_request
    reopen = fixtures.LedgerTests.reopen

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name) / "mission"
        self.a = admission(allowed_skills=("direct",))
        self.ledger = MissionLedger(self.directory, admission=self.a, now=1000)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(lambda: self.ledger.close())

    def entry(self):
        original = binding()
        return InputObservation(original, replace(original, source_id="entry-source", store_generation=2))

    def ordinary_request(self, event=None):
        return skill(skill_kind="direct", goal=dict(input=event or dict(type="key", key="ESC", modifiers=[]),
            intent="Try this physical event", expected="Interpret the result", interrupt_allowed=False))

    def ordinary_intent(self, **changes):
        return intent(kind="direct", value=dict(type="key", key="ESC", modifiers=[]),
            source_before="entry-source", expected_revision=45, expected_boundary_id="actual-preflight",
            input_observation=self.entry().to_dict()) | changes

    def test_first_ordinary_intent_preserves_entry_and_actual_preflight_without_equivalence(self):
        self.active_request(self.ordinary_request())
        value = self.ordinary_intent()
        self.ledger.prepare_primitive("request-1", "ordinary-1", value, now=1002)
        self.ledger.settle_primitive("ordinary-1", "not_dispatched", {"reason": "Synthetic known nonpublication"}, now=1003)
        self.reopen()
        stored = self.ledger.primitive("ordinary-1")
        self.assertEqual(stored["intent"], value)
        self.assertEqual(stored["intent"]["expected_revision"], 45)
        self.assertEqual(self.ledger.request("request-1")["request"]["expected_revision"], 30)
        self.assertEqual(self.ledger.snapshot(now=1010)["spent_inputs"], 1)

    def test_first_ordinary_input_requires_exact_non_authorizing_entry(self):
        self.active_request(self.ordinary_request())
        missing = self.ordinary_intent()
        missing.pop("input_observation")
        wrong = self.entry().to_dict()
        wrong["grants_authority"] = True
        for value in (missing, self.ordinary_intent(input_observation=None), self.ordinary_intent(input_observation=wrong),
                      self.ordinary_intent(source_before="other-source")):
            with self.subTest(value=value), self.assertRaises(ContractError):
                self.ledger.prepare_primitive("request-1", "ordinary-1", value, now=1002)
        self.assertEqual(self.ledger.snapshot(now=1002)["spent_inputs"], 0)

    def test_entry_cannot_cross_actor_epoch_or_informing_source(self):
        self.active_request(self.ordinary_request())
        for field, changed in (("actor_id", "other-player"), ("epoch", 1), ("source_id", "not-informing")):
            original = replace(binding(), **{field: changed})
            current = replace(original, source_id="entry-source", store_generation=2)
            value = self.ordinary_intent(input_observation=InputObservation(original, current).to_dict())
            with self.subTest(field=field), self.assertRaises(LedgerError):
                self.ledger.prepare_primitive("request-1", "ordinary-1", value, now=1002)

    def test_semantic_revalidation_is_never_an_ordinary_entry(self):
        self.active_request(self.ordinary_request())
        original = binding()
        refreshed = SourceRevalidation(original, replace(original, source_id="entry-source", store_generation=2), "exact_png_bytes")
        with self.assertRaises(LedgerError):
            self.ledger.prepare_primitive("request-1", "ordinary-1", self.ordinary_intent(
                input_observation=None, revalidation=refreshed.to_dict()), now=1002)
        self.assertEqual(self.ledger.snapshot(now=1002)["spent_inputs"], 0)

    def test_physical_event_cannot_be_retargeted_or_changed_to_a_shortcut(self):
        self.active_request(self.ordinary_request())
        for value in (self.ordinary_intent(value=dict(type="key", key="ENTER", modifiers=[])),
                      self.ordinary_intent(expected_session="another-session"),
                      self.ordinary_intent(expected_revision=29),
                      self.ordinary_intent(kind="action", value="QUIT", input_observation=None)):
            with self.subTest(value=value), self.assertRaises(LedgerError):
                self.ledger.prepare_primitive("request-1", "ordinary-1", value, now=1002)

    def test_returned_text_prefix_charges_each_selected_scalar_and_entry_once(self):
        self.active_request(self.ordinary_request(dict(type="text", text="éx")))
        first = self.ordinary_intent(value=dict(type="text", text="é"))
        self.ledger.prepare_primitive("request-1", "ordinary-1", first, now=1002)
        self.ledger.settle_primitive("ordinary-1", "returned", known_receipt(
            logical_id="ordinary-1", proposed=first), now=1003)
        second = self.ordinary_intent(value=dict(type="text", text="x"), input_observation=None, source_before="after-1")
        with self.assertRaises(LedgerError):
            self.ledger.prepare_primitive("request-1", "repeated-entry", second | dict(input_observation=self.entry().to_dict()), now=1003)
        self.ledger.prepare_primitive("request-1", "ordinary-2", second, now=1003)
        self.ledger.settle_primitive("ordinary-2", "returned", known_receipt(
            logical_id="ordinary-2", native_id="native-2", proposed=second), now=1004)
        with self.assertRaises(LedgerError):
            self.ledger.prepare_primitive("request-1", "extra-scalar", second, now=1004)
        self.assertEqual(self.ledger.snapshot(now=1004)["spent_inputs"], 2)
        self.reopen()
        self.assertEqual(self.ledger.primitive("ordinary-2")["intent"], second)

    def test_text_prefix_cannot_skip_an_unpublished_scalar(self):
        self.active_request(self.ordinary_request(dict(type="text", text="xy")))
        self.ledger.prepare_primitive("request-1", "ordinary-1", self.ordinary_intent(value=dict(type="text", text="x")), now=1002)
        self.ledger.settle_primitive("ordinary-1", "not_dispatched", {"reason": "Synthetic nonpublication"}, now=1003)
        with self.assertRaises(LedgerError):
            self.ledger.prepare_primitive("request-1", "ordinary-2", self.ordinary_intent(
                value=dict(type="text", text="y"), input_observation=None, source_before="after-1"), now=1003)
        self.assertEqual(self.ledger.snapshot(now=1003)["spent_inputs"], 1)

    def prepared_ordinary(self):
        self.active_request(self.ordinary_request())
        proposed = self.ordinary_intent()
        self.ledger.prepare_primitive("request-1", "ordinary-1", proposed, now=1002)
        return known_receipt(logical_id="ordinary-1", proposed=proposed)

    def test_failed_publication_bookkeeping_binds_known_ack_and_missing_capture_once(self):
        receipt = self.prepared_ordinary() | dict(source_after=None,
            evidence_loss="After image storage failed", processing_error="Publication bookkeeping failed")
        with patch.object(self.ledger, "_touch", side_effect=sqlite3.OperationalError("published failed")):
            with self.assertRaises(LedgerError):
                self.ledger.published("ordinary-1", receipt["native_request_id"], now=1003)
        self.assertEqual(self.ledger.primitive("ordinary-1")["state"], "prepared")
        settled = self.ledger.settle_primitive("ordinary-1", "returned", receipt, now=1003)
        self.assertEqual(settled["state"], "returned")
        self.assertEqual(settled["native_id"], receipt["native_request_id"])
        self.assertEqual(self.ledger.snapshot(now=1003)["spent_inputs"], 1)
        self.assertEqual(self.ledger.settle_primitive("ordinary-1", "returned", receipt, now=1003), settled)
        for changed in (receipt | dict(source_after="late-capture"), receipt | dict(evidence_loss="revised")):
            with self.assertRaises(LedgerError):
                self.ledger.settle_primitive("ordinary-1", "returned", changed, now=1003)
        self.reopen()
        self.assertEqual(self.ledger.primitive("ordinary-1")["result"], receipt)
        self.assertEqual(self.ledger.snapshot(now=1010)["phase"], "paused")

    def test_failed_settlement_rolls_back_binding_reservations_and_terminal_result(self):
        receipt = self.prepared_ordinary()
        with patch.object(self.ledger, "_release", side_effect=sqlite3.OperationalError("Storage failed")):
            with self.assertRaises(LedgerError):
                self.ledger.settle_primitive("ordinary-1", "returned", receipt, now=1003)
        primitive = self.ledger.primitive("ordinary-1")
        self.assertEqual((primitive["state"], primitive["native_id"], primitive["result"]), ("prepared", None, None))
        self.reopen()
        self.assertEqual(self.ledger.primitive("ordinary-1")["state"], "unknown")

    def test_incorrect_mapping_never_binds_prepared_native_id(self):
        receipt = self.prepared_ordinary()
        mutations = [dict(logical_action_id="wrong"), dict(native_request_id="wrong"),
            dict(value=dict(type="key", key="ENTER", modifiers=[])), dict(expected_revision=30),
            dict(preflight_source="wrong"), dict(source_before="wrong"), dict(native_ack=None),
            dict(source_after="0" * 64)]
        for changed in mutations:
            with self.subTest(changed=changed), self.assertRaises(LedgerError):
                self.ledger.settle_primitive("ordinary-1", "returned", receipt | changed, now=1003)
            self.assertEqual(self.ledger.primitive("ordinary-1")["state"], "prepared")
            self.assertIsNone(self.ledger.primitive("ordinary-1")["native_id"])

    def test_reopen_audits_ack_correlation_and_rejects_tampering(self):
        receipt = self.prepared_ordinary()
        self.ledger.settle_primitive("ordinary-1", "returned", receipt, now=1003)
        original = self.ledger.path.read_bytes()
        self.ledger.close()
        mutations = [lambda r: r["native_ack"].update(id="wrong"),
            lambda r: r["native_ack"].update(session="wrong"),
            lambda r: r["native_ack"].update(revision=45),
            lambda r: r.update(source_after="0" * 64),
            lambda r: r.update(native_request_json=r["native_request_json"] + " "),
            lambda r: r.update(value=dict(type="key", key="ENTER", modifiers=[])),
            lambda r: r.pop("native_ack")]
        for mutate in mutations:
            self.ledger.path.write_bytes(original)
            changed = deepcopy(receipt)
            mutate(changed)
            with closing(sqlite3.connect(self.ledger.path)) as db, db:
                db.execute("UPDATE primitives SET result=?", (canonical(changed),))
            with self.subTest(changed=changed), self.assertRaises(LedgerError):
                MissionLedger(self.directory, now=1010)
        self.ledger.path.write_bytes(original)
        self.ledger = MissionLedger(self.directory, now=1010)

    def test_known_rejection_can_retain_hard_fault_without_after(self):
        receipt = self.prepared_ordinary()
        receipt.update(transport_disposition="rejected", source_after=None)
        receipt["native_ack"].update(status="rejected", paused=True, pause_origin="fault",
            session="new-session", revision=0, error="hard fault", frame_ok=False, frame="")
        receipt["native_ack"]["boundary"].update(kind="unsupported", input_receiver=False)
        self.ledger.settle_primitive("ordinary-1", "rejected", receipt, now=1003)
        self.reopen()
        self.assertEqual(self.ledger.primitive("ordinary-1")["result"], receipt)


if __name__ == "__main__":
    unittest.main()
