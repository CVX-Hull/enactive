"""Pure authenticated delivery projections, without execution authority."""
from copy import deepcopy
import unittest

from harness.gameplay.contracts import ContractError, canonical
from harness.gameplay.mission_ledger import MAX_RECEIPT_BYTES, RESULT_RESERVE
from harness.gameplay.native_receipts import compact_native_ack, validate_ordinary_mapping, validate_published_input
from tests.test_gameplay_evidence import observation
from tests.test_mission_ledger import intent, known_receipt


class NativeReceiptTests(unittest.TestCase):
    def validate(self, receipt, proposed=None, disposition="returned"):
        validate_ordinary_mapping(proposed or intent(), receipt, logical_id="logical-1",
                                  native_id="native-uuid-1", disposition=disposition)

    def test_projection_is_closed_defensive_and_excludes_large_scene_ui_geometry(self):
        full = observation(31, session="native-session")
        full["id"] = "native-uuid-1"
        full["scene"]["visible_creatures"] = [{"name": "x" * 1024, "hostile": False} for _ in range(512)]
        ack = compact_native_ack(full)
        self.assertEqual(set(ack), {"protocol", "id", "session", "revision", "status", "error", "paused",
            "pause_origin", "takeover_generation", "timestamp_ms", "frame_ok", "frame", "boundary"})
        full["boundary"]["id"] = "changed"
        self.assertEqual(ack["boundary"]["id"], "boundary-1")
        self.assertLess(len(canonical(ack).encode()), 2048)
        self.assertGreater(len(canonical(full).encode()), 500_000)

    def test_known_returned_without_after_requires_explicit_loss_and_accepts_later_restricted_screen(self):
        receipt = known_receipt(source_after=None, evidence_loss="PNG retention failed")
        receipt["native_ack"]["boundary"].update(kind="unsupported", input_receiver=False)
        self.validate(receipt)
        for loss in (None, "", "x" * 1025):
            with self.subTest(loss=loss), self.assertRaises(ContractError):
                self.validate(receipt | {"evidence_loss": loss})

    def test_known_mapping_rejects_wrong_identity_event_session_revision_and_schema(self):
        receipt = known_receipt()
        mutations = [lambda r: r.update(logical_action_id="wrong"),
            lambda r: r.update(native_request_id="wrong"),
            lambda r: r.update(value="LEFT"), lambda r: r.update(expected_revision=29),
            lambda r: r.update(source_before="wrong"), lambda r: r.update(preflight_source="wrong"),
            lambda r: r.update(source_after="unrelated-capture"),
            lambda r: r.update(published=False), lambda r: r.update(received_monotonic=True),
            lambda r: r.update(received_monotonic=float("nan")),
            lambda r: r.update(processing_error="x" * 1025),
            lambda r: r.pop("processing_error"), lambda r: r.pop("native_ack"),
            lambda r: r.update(native_ack=canonical(r["native_ack"])),
            lambda r: r["native_ack"].update(id="wrong"),
            lambda r: r["native_ack"].update(session="wrong"),
            lambda r: r["native_ack"].update(revision=30),
            lambda r: r["native_ack"].update(protocol=5),
            lambda r: r["native_ack"].update(protocol=True),
            lambda r: r["native_ack"].update(status="dispatched"),
            lambda r: r["native_ack"]["boundary"].update(input_receiver=1),
            lambda r: r["native_ack"]["boundary"].update(kind="debug_prompt", input_receiver=True)]
        for mutate in mutations:
            changed = deepcopy(receipt)
            mutate(changed)
            with self.subTest(changed=changed), self.assertRaises(ContractError):
                self.validate(changed)

    def test_receipt_payload_keeps_its_independent_type_guard_after_correlation_factoring(self):
        geometry = dict(window_width=10, window_height=10, output_width=10, output_height=10, viewport=[0, 0, 10, 10])
        proposed = intent(kind="direct", value=dict(type="click", button="left", x=1, y=2, geometry=geometry))
        receipt = known_receipt(proposed=proposed)
        self.validate(receipt, proposed)
        # Python equality equates True and1; receipt shape must still be checked.
        receipt['value'] = {**receipt['value'], 'x': True}
        with self.assertRaises(ContractError):
            self.validate(receipt, proposed)

    def test_rejected_hard_fault_or_new_session_is_known_zero_input_without_capture(self):
        receipt = known_receipt(disposition="rejected", source_after=None)
        receipt["native_ack"].update(session="new-session", revision=0, paused=True,
            pause_origin="fault", frame_ok=False, frame="", error="hard fault")
        receipt["native_ack"]["boundary"].update(kind="unsupported", input_receiver=False)
        self.validate(receipt, disposition="rejected")

    def test_unknown_or_nonpublication_must_not_fabricate_an_ack(self):
        for disposition in ("unknown", "not_dispatched"):
            self.validate({"reason": "Uncertain or absent delivery"}, disposition=disposition)
            self.validate({"native_ack": None}, disposition=disposition)
            with self.assertRaises(ContractError):
                self.validate(known_receipt(), disposition=disposition)

    def test_published_admission_can_be_checked_without_inventing_unknown_ack(self):
        import json
        proposed = intent(kind="direct", value=dict(type="key", key="Z", modifiers=[]))
        receipt = known_receipt(proposed=proposed)
        receipt.update(native_ack=None, transport_disposition="unknown", source_after=None)
        native = validate_published_input(proposed, receipt, logical_id="logical-1", native_id="native-uuid-1")
        self.assertEqual(native["input"], proposed["value"])
        self.assertIsNone(receipt["native_ack"])
        for changes in ({"input": dict(type="key", key="X", modifiers=[])},
                        {"id": "other"}, {"revision": 1}, {"session": "other"}, {"require_exact_frame": True}):
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                changed = deepcopy(receipt)
                changed["native_request_json"] = canonical(json.loads(receipt["native_request_json"]) | changes)
                validate_published_input(proposed, changed, logical_id="logical-1", native_id="native-uuid-1")

    def test_native_request_rejects_wrong_event_authority_frame_flag_and_noncanonical_bytes(self):
        import json
        proposed = intent(kind="direct", value=dict(type="text", text="é"))
        receipt = known_receipt(proposed=proposed)
        self.validate(receipt, proposed)
        for change in (dict(protocol=5), dict(id="wrong"), dict(input=dict(type="text", text="x")),
                       dict(session="wrong"), dict(revision=29), dict(boundary_id="wrong"),
                       dict(require_exact_frame=True), dict(authority=dict(controller_boot_id="boot", counter=True)),
                       dict(frame="")):
            native = json.loads(receipt["native_request_json"]) | change
            with self.subTest(change=change), self.assertRaises(ContractError):
                self.validate(receipt | dict(native_request_json=canonical(native)), proposed)
        with self.assertRaises(ContractError):
            self.validate(receipt | dict(native_request_json=receipt["native_request_json"] + " "), proposed)

    def test_all_ordinary_kinds_use_actual_preflight_revision_and_ack_after_frame(self):
        for kind, value in (("action", "RIGHT"), ("key", "ESC"),
                            ("direct", dict(type="text", text="é")), ("resume", None)):
            proposed = intent(kind=kind, value=value, expected_revision=45)
            receipt = known_receipt(proposed=proposed)
            self.validate(receipt, proposed)
            self.assertEqual(receipt["native_ack"]["revision"], 46)
            self.assertIn("-45.png", receipt["native_request_json"])
            self.assertTrue(receipt["native_ack"]["frame"].endswith("-46.png"))

    def test_worst_case_unicode_and_escaping_stay_under_existing_receipt_reservation_without_truncation(self):
        import json
        for scalar in ("\x00", "😀"):
            maximum_id = "a" * 128
            proposed = intent(value=scalar * 160, expected_session=maximum_id,
                source_before=maximum_id, preflight_source=maximum_id, expected_boundary_id=maximum_id,
                expected_revision=2**63 - 2)
            receipt = known_receipt(logical_id=maximum_id, native_id=maximum_id, proposed=proposed,
                source_after=None, evidence_loss=scalar * 1024)
            receipt["processing_error"] = scalar * 1024
            ack = receipt["native_ack"]
            ack.update(error=scalar * 4096, frame=scalar * 300, timestamp_ms=2**63 - 1,
                takeover_generation=2**63 - 1)
            ack["boundary"].update(id=scalar * 128, control_generation=2**63 - 1,
                kind="interrupt_confirmation", input_receiver=False,
                recovery_operations=["answer_interrupt"], interrupt_request_id=scalar * 128)
            native = json.loads(receipt["native_request_json"])
            native.update(authority=dict(controller_boot_id="\x00" * 128, counter=2**63 - 1),
                deadline_ms=2**63 - 1, takeover_generation=2**63 - 1)
            # Choose the largest fixture frame within BOTH independent native
            # request limits (300 characters, 4096 encoded bytes). The projection
            # never truncates any actual correlation field or diagnostic.
            for count in range(300, 0, -1):
                native["frame"] = "\x00" * count
                remaining = 4096 - len(canonical(native).encode())
                if remaining >= 0:
                    native["frame"] += "x" * min(remaining, 300 - count)
                    break
            receipt["native_request_json"] = canonical(native)
            self.assertLessEqual(len(receipt["native_request_json"].encode()), 4096)
            self.assertGreater(len(receipt["native_request_json"].encode()), 3000)
            validate_ordinary_mapping(proposed, receipt, logical_id=maximum_id,
                native_id=maximum_id, disposition="returned")
            encoded = canonical(receipt).encode()
            self.assertLessEqual(len(encoded), MAX_RECEIPT_BYTES)
            self.assertEqual(RESULT_RESERVE, 81_920)
            self.assertEqual(json.loads(encoded), receipt)
            self.assertEqual(len(receipt["native_ack"]["error"]), 4096)


if __name__ == "__main__":
    unittest.main()
