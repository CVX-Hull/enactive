"""SQLite failure/restart probes. No native dispatch or gameplay is simulated."""
from contextlib import closing
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
from harness.gameplay.contracts import canonical
from harness.gameplay.mission_contracts import VERSION, CleanupReserve, MissionLimits, SourceRevalidation
from harness.gameplay.mission_ledger import BudgetError, LedgerError, MissionLedger
from tests.test_mission_contracts import admission, binding, claim, request, skill


def intent(**changes):
    values = {"kind": "action", "value": "RIGHT", "expected_session": "native-session",
              "expected_revision": 30, "expected_boundary_id": "boundary-1",
              "source_before": "source-1", "preflight_source": "preflight-1", "revalidation": None, "input_observation": None,
              "reservation_id": "reservation-1"}
    values.update(changes)
    return values


def published_receipt(*, native_id="native-uuid-1", logical_id="logical-1", proposed=None,
                      controller_boot_id="controller-test", dispatch_epoch=0, actor_id="player-test", frame=None):
    """Pure SQLite correlation fixture, not evidence of actual file custody."""
    proposed = proposed or intent()
    payload = ({} if proposed["kind"] == "resume" else
               {"input" if proposed["kind"] == "direct" else proposed["kind"]: proposed["value"]})
    native = dict(protocol=6, id=native_id, kind=proposed["kind"], session=proposed["expected_session"],
        revision=proposed["expected_revision"], boundary_id=proposed["expected_boundary_id"], takeover_generation=0,
        authority=dict(controller_boot_id=controller_boot_id, counter=1), deadline_ms=1,
        frame=frame or f"frame-{proposed['expected_session']}-{proposed['expected_revision']}.png",
        require_exact_frame=False, **payload)
    return dict(published=True, native_request_id=native_id, logical_action_id=logical_id,
                native_request_json=canonical(native), dispatch_binding=dict(controller_boot_id=controller_boot_id,
                    operator_pause_generation=0, takeover_generation=0, actor_id=actor_id,
                    epoch=dispatch_epoch, game_anchor_source_id=proposed["source_before"]))


def known_receipt(*, native_id="native-uuid-1", logical_id="logical-1", proposed=None,
                  disposition="returned", source_after=..., evidence_loss=None,
                  after=None, frame=None):
    """Current complete receipt fixture; no compatibility path in production."""
    from harness.gameplay.native_receipts import compact_native_ack
    from harness.gameplay.evidence import _identity
    from tests.test_gameplay_evidence import observation
    proposed = proposed or intent()
    native = after or observation(proposed["expected_revision"] + 1, session=proposed["expected_session"])
    native = dict(native, id=native_id, status="ready" if disposition == "returned" else "rejected")
    return published_receipt(native_id=native_id, logical_id=logical_id, proposed=proposed, frame=frame) | {
        **{key: proposed[key] for key in ("kind", "value", "expected_session", "expected_revision",
                                         "expected_boundary_id", "source_before", "preflight_source")},
        "transport_disposition": disposition, "received_monotonic": 100.5,
        "native_ack": compact_native_ack(native),
        "source_after": _identity(native) if source_after is ... else source_after,
        "processing_error": None, "evidence_loss": evidence_loss}


def delivery_resolution(ledger, *, now, logical_id="logical-1"):
    """Admit a synthetic read-only owner for ledger persistence tests only."""
    p = ledger.primitive(logical_id)
    original = ledger.request(p["request_id"])
    epoch = original["epoch"] + 1
    identity = "resolve-" + logical_id
    ledger.begin_request(request("reconcile", request_id=identity, epoch=epoch,
        unresolved_request_id=p["request_id"], evidence_id="fresh-after", reason="Synthetic exact-custody accounting probe"), now=now)
    proof = dict(schema=VERSION, record_type="DeliveryResolution", reconciliation_request_id=identity,
        original_request_id=p["request_id"], root_id=original["request"].get("phase_id") or p["request_id"],
        logical_id=logical_id, native_request_id=p["native_id"], actor_id=ledger.admission.player_id,
        origin_epoch=original["epoch"], recovery_epoch=epoch, controller_boot_id="controller-test",
        operator_pause_generation=0, takeover_generation=0, game_anchor_source_id=p["intent"]["source_before"],
        before_source_id=p["intent"]["source_before"], observed_source_id="fresh-after", terminal_source_id=None,
        native_request_json=p["result"]["native_request_json"], collection_started_monotonic=10,
        collection_deadline_monotonic=10.25, collection_received_monotonic=10.1,
        retirement="cancelled-timeout-synthetic.json", terminal=None, grants_authority=False)
    return proof, tuple(dict.fromkeys((p["intent"]["source_before"], "fresh-after")))


def reconcile_fixture(ledger, *, now, note):
    proof, sources = delivery_resolution(ledger, now=now)
    ledger.reconcile_effect("logical-1", proof=proof, sources=sources, note=note, now=now)
    ledger.complete_request(proof["reconciliation_request_id"], "completed", dict(
        reconciliation=proof, source_ids=list(sources), reason=note, grants_authority=False), now=now)
    return proof


def handoff_binding(**changes):
    values = dict(session="native-session", revision=30, boundary_id="boundary-1",
                  pause_generation=4, takeover_generation=0, pause_origin="host",
                  post_pause_source_id="post-pause", controller_boot_id="controller-test", operator_pause_generation=0)
    values.update(changes)
    return values


def handoff_claim(issuance, **changes):
    values = request("claim", request_id="claim-1", epoch=issuance["epoch"],
        handoff_id=issuance["handoff_id"], player_id="replacement-player", actor_role="player",
        packet_ids=["packet-1"], read_source_ids=[issuance["post_pause_source_id"]],
        expected_session=issuance["session"], expected_revision=issuance["revision"],
        expected_boundary_id=issuance["boundary_id"], expected_pause_origin=issuance["pause_origin"],
        pause_generation=issuance["pause_generation"], takeover_generation=issuance["takeover_generation"], read_procedure_sources=[])
    values.update(changes)
    return values


def phase_lifecycle(**changes):
    values = request("lifecycle", operation="create", world="test-world", character="test-person",
                     sources=["source-1"], expected_session="native-session", expected_revision=30,
                     expected_boundary_id="boundary-1", limits={"primitives": 3, "wall_seconds": 120, "game_seconds": 1200})
    values.update(changes)
    return values


def phase_skill(kind="menu", **changes):
    goals = {
        "menu": {"purpose": "Choose", "label": "One", "outcome": "activated"},
        "item": {"purpose": "consume", "label": "water", "quantity": 1, "quantity_unit": "charges", "step": "start", "outcome": "consumed"},
        "activity": {"operation": "rest", "target": "bench", "game_seconds": 10, "interrupt_allowed": True, "step": "start", "answer": None, "interrupt_request_id": None},
        "inspect": {"purpose": "inventory"},
        "interact": {"action": "open_consume", "intent": "Inspect food", "desired_outcome": "Food choices"},
        "edit": {"purpose": "character_name", "text": "Survivor", "commit": False},
    }
    values = skill(skill_kind=kind, goal=goals[kind])
    if kind == "edit":
        values["perception"] = dict(kind="editor", basis="player_interpretation", source_id="source-1",
            purpose="character_name", label="Name", visible_text="", whole_value=True, focused=True)
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

    def issue_handoff(self):
        self.active_request(request("handoff", request_id="handoff-1", checkpoint_ids=["source-1"], successor_role="player"))
        return self.ledger.issue_handoff("handoff-1", binding=handoff_binding(), now=1002)

    def readmit_request(self, **changes):
        issued = self.issue_handoff()
        self.ledger.begin_request(handoff_claim(issued), now=1003)
        self.ledger.consume_handoff("claim-1", actor_id="replacement-player", actor_role="player", now=1004)
        values = request("readmit", request_id="readmit-1", epoch=issued["epoch"], mode="handoff", handoff_id="handoff-1",
            claim_request_id="claim-1", sources=[issued["post_pause_source_id"]], expected_session=issued["session"],
            expected_revision=issued["revision"], expected_boundary_id=issued["boundary_id"],
            limits=dict(primitives=1, wall_seconds=10, game_seconds=10))
        values.update(changes)
        return values

    def test_rejected_lifecycle_root_history_reopens_without_rewriting_payload_or_digest(self):
        # A formerly admitted malformed request is immutable failure evidence,
        # even though the new pure submission boundary refuses its execution.
        rejected = phase_lifecycle(operation="save", work_id="pending", identity_claim_ids=["old-identity"])
        self.active_request(rejected)
        self.ledger.complete_request(rejected["request_id"], "blocked",
            dict(reason="Lifecycle root cannot import Work or old identity authority", grants_authority=False), now=1002)
        before = self.ledger.request(rejected["request_id"])
        payload = self.ledger._db.execute("SELECT payload,digest FROM requests WHERE id=?",
            (rejected["request_id"],)).fetchone()
        self.reopen(now=1003)
        self.assertEqual(self.ledger.request(rejected["request_id"]), before)
        self.assertEqual(self.ledger._db.execute("SELECT payload,digest FROM requests WHERE id=?",
            (rejected["request_id"],)).fetchone(), payload)
        self.assertEqual(self.ledger.primitive_records(), ())

    def test_measured_counts_use_cumulative_rows_and_preserve_unknowns_across_reopen(self):
        empty = self.ledger.measured_counts()
        self.assertEqual(empty, {"operations": {"total": 0, "by_kind": {}, "by_skill": {}, "by_state": {}},
                                 "primitives": {"charged": 0, "by_state": {}}})
        self.active_request()
        self.ledger.prepare_primitive("request-1", "not-sent", intent(), now=1001)
        self.ledger.settle_primitive("not-sent", "not_dispatched", {"reason": "Preflight stopped"}, now=1001)
        self.ledger.prepare_primitive("request-1", "uncertain", intent(), now=1001)
        self.ledger.published("uncertain", "native-uncertain", now=1001)
        self.ledger.settle_primitive("uncertain", "unknown", {"reason": "No terminal ACK"}, now=1001)
        self.ledger.complete_request("request-1", "unknown", {"reason": "Needs verification"}, now=1001)
        epoch = self.ledger.snapshot(now=1001)["epoch"]
        for index in range(80):
            identity = f"observe-{index}"
            self.ledger.begin_request(request("observe", request_id=identity, epoch=epoch), now=1001)
            self.ledger.complete_request(identity, "completed", {"source_ids": []}, now=1001)
        with patch.object(self.ledger, "request_records", side_effect=AssertionError("No receipt scan")), \
             patch.object(self.ledger, "primitive_records", side_effect=AssertionError("No primitive scan")):
            counts = self.ledger.measured_counts()
        self.assertEqual(counts, {"operations": {"total": 81, "by_kind": {"observe": 80, "skill": 1},
            "by_skill": {"navigate": 1}, "by_state": {"completed": 80, "unknown": 1}},
            "primitives": {"charged": 2, "by_state": {"not_dispatched": 1, "unknown": 1}}})
        self.assertEqual(counts["primitives"]["charged"], self.ledger.snapshot(now=1001)["spent_inputs"])
        self.assertEqual(self.reopen(now=1002).measured_counts(), counts)
        counts["operations"]["by_kind"]["observe"] = 0
        self.assertEqual(self.ledger.measured_counts()["operations"]["by_kind"]["observe"], 80)

    def test_readmission_charges_only_one_resume_and_preserves_original_deadlines(self):
        value = self.readmit_request()
        operation = self.ledger.begin_request(value, now=1005)["operation"]
        self.assertEqual(operation["deadline"], 1015)
        self.ledger.activate(epoch=value["epoch"], player_id="replacement-player", now=1005)
        with self.assertRaisesRegex(LedgerError, "only its charged Resume"):
            self.ledger.prepare_primitive("readmit-1", "wrong-action", intent(), now=1006)
        self.ledger.prepare_primitive("readmit-1", "readmit-resume", intent(kind="resume", value=None), now=1006)
        self.ledger.settle_primitive("readmit-resume", "not_dispatched", {"reason": "Explicit nonpublication"}, now=1007)
        with self.assertRaises(BudgetError):
            self.ledger.prepare_primitive("readmit-1", "second-resume", intent(kind="resume", value=None), now=1008)
        self.assertEqual(self.ledger.snapshot(now=1008)["spent_inputs"], 1)
        self.ledger.complete_request("readmit-1", "blocked", {"reason": "Synthetic accounting probe"}, now=1008)
        self.assertEqual(self.reopen(now=1009).snapshot(now=1009)["phase"], "paused")

    def test_readmission_deadline_tamper_rejects_on_reopen(self):
        self.ledger.begin_request(self.readmit_request(), now=1005)
        self.ledger._db.execute("UPDATE requests SET deadline=1016 WHERE id='readmit-1'")
        with self.assertRaisesRegex(LedgerError, "deadline was altered"):
            self.reopen(now=1006)

    def test_readmission_cannot_claim_completion_without_its_charged_returned_proof(self):
        self.ledger.begin_request(self.readmit_request(), now=1005)
        with self.assertRaises(ContractError):
            self.ledger.complete_request("readmit-1", "completed", {"grants_authority": False}, now=1006)
        self.assertIsNone(self.ledger.request("readmit-1")["result"])

    def phase_input(self, request_id, logical_id, now=1002):
        self.ledger.prepare_primitive(request_id, logical_id, intent(), now=now)
        self.ledger.settle_primitive(logical_id, "not_dispatched", {"reason": "Synthetic accounting probe"}, now=now)

    def prompt_receipt(self, **changes):
        value = dict(schema="mission/10", record_type="PhaseReceipt", origin_request_id="request-1",
            phase_kind="interact", operation="open_consume", stage="awaiting_control", epoch=0,
            actor_id="player-test", controller_boot_id="controller-test", operator_pause_generation=0,
            takeover_generation=0, source_ids=["source-1"], continuity=None, grants_authority=False)
        value.update(changes)
        return value

    def test_prompt_receipt_root_child_and_observe_reopen_without_authority(self):
        self.active_request(phase_skill("interact"))
        root = self.prompt_receipt()
        self.ledger.complete_request("request-1", "partial", {"phase": root}, now=1002)
        self.ledger.begin_request(phase_skill(request_id="child", phase_id="request-1"), now=1003)
        self.ledger.complete_request("child", "partial", {"phase": root}, now=1004)
        self.ledger.begin_request(request("observe", request_id="observe"), now=1005)
        closed = self.prompt_receipt(stage="complete")
        self.ledger.complete_request("observe", "completed", {"phase": closed}, now=1006)
        state = self.reopen(now=1007).snapshot(now=1007)
        self.assertEqual(state["phase"], "paused")
        self.assertFalse(state["grants_authority"])
        self.assertEqual(self.ledger.request("request-1")["result"]["phase"], root)
        self.assertEqual(self.ledger.request("observe")["result"]["phase"], closed)

    def test_item_observation_progress_does_not_grant_activity_recovery_stages(self):
        root = phase_skill("item")
        self.active_request(root)
        phase = self.prompt_receipt(phase_kind="item", operation=root["goal"]["purpose"], stage="activity_poll")
        self.ledger.complete_request("request-1", "partial", {"phase": phase}, now=1002)
        self.ledger.begin_request(request("observe", request_id="observe"), now=1003)
        for stage in ("interrupt_confirmation", "awaiting_readmission"):
            with self.subTest(stage=stage), self.assertRaises(ContractError):
                self.ledger.complete_request("observe", "completed", {"phase": phase | {"stage": stage}}, now=1004)
        returned = phase | {"stage": "awaiting_control"}
        self.ledger.complete_request("observe", "completed", {"phase": returned}, now=1004)
        state = self.reopen(now=1005).snapshot(now=1005)
        self.assertEqual(self.ledger.request("observe")["result"]["phase"], returned)
        self.assertEqual(state["phase"], "paused")
        self.assertFalse(state["grants_authority"])

    def test_navigation_prompt_controls_and_closing_observe_reopen_without_authority(self):
        self.active_request(skill())
        receipt = self.prompt_receipt(phase_kind="navigate", operation="navigate")
        for changes in (dict(operation="open"), dict(stage="activity_poll"), dict(actor_id="other")):
            with self.subTest(changes=changes), self.assertRaises(LedgerError):
                self.ledger.complete_request("request-1", "partial", {"phase": receipt | changes}, now=1002)
        self.ledger.complete_request("request-1", "partial", {"phase": receipt}, now=1002)
        for kind in ("interact", "item", "activity", "inspect"):
            child = phase_skill(kind, request_id=kind, phase_id="request-1")
            if kind in ("item", "activity"):
                child["goal"]["step"] = "select" if kind == "item" else "poll"
            with self.subTest(kind=kind), self.assertRaises(ContractError):
                self.ledger.begin_request(child, now=1003)
        for kind in ("menu", "edit"):
            child = phase_skill(kind, request_id=kind, phase_id="request-1")
            self.ledger.begin_request(child, now=1003)
            self.phase_input(kind, "input-" + kind, now=1003)
            self.ledger.complete_request(kind, "partial", {"phase": receipt}, now=1003)
        self.ledger.begin_request(request("observe", request_id="observe"), now=1004)
        self.ledger.complete_request("observe", "completed", {"phase": receipt | {"stage": "complete"}}, now=1004)
        state = self.reopen(now=1005).snapshot(now=1005)
        self.assertEqual(state["phase"], "paused")
        self.assertEqual(state["spent_inputs"], 2)
        self.assertFalse(state["grants_authority"])
        self.assertEqual(self.ledger.request("menu")["result"]["phase"], receipt)

    def test_prompt_receipt_rejects_nonobjects_and_malformed_correlation_transactionally(self):
        self.active_request(phase_skill("interact"))
        changes = (dict(actor_id="other"), dict(epoch=1), dict(operation="open"),
            dict(origin_request_id="missing"), dict(phase_kind="lifecycle"), dict(stage="exited"),
            dict(continuity={}), dict(grants_authority=True), dict(source_ids=[]), dict(extra=True))
        bad = [None, json.dumps(self.prompt_receipt()), [], *[self.prompt_receipt(**v) for v in changes]]
        before = self.ledger.snapshot(now=1002)
        # Rejection retains the observed wall clock even when intent/result rolls back.
        before["last_wall"] = 1002.0
        for value in bad:
            with self.subTest(value=value), self.assertRaises(LedgerError):
                self.ledger.complete_request("request-1", "partial", {"phase": value}, now=1002)
            self.assertIsNone(self.ledger.request("request-1")["result"])
            self.assertEqual(self.ledger.snapshot(now=1002), before)

    def test_prompt_receipt_corrupted_nested_string_rejects_on_reopen(self):
        self.active_request(phase_skill("interact"))
        self.ledger.complete_request("request-1", "partial", {"phase": self.prompt_receipt()}, now=1002)
        self.ledger._db.execute("UPDATE requests SET result=? WHERE id='request-1'",
            (json.dumps({"phase": json.dumps(self.prompt_receipt())}, sort_keys=True, separators=(",", ":")),))
        with self.assertRaisesRegex(LedgerError, "typed object"): self.reopen()

    def test_new_prompt_receipt_cannot_be_authored_for_previous_actor_after_handoff(self):
        self.active_request(phase_skill("interact"))
        self.reopen(now=1002)
        epoch = self.ledger.snapshot(now=1002)["epoch"]
        self.ledger.activate(epoch=epoch, player_id="player-test", now=1003)
        self.ledger.begin_request(request("handoff", request_id="handoff-1", epoch=epoch,
            checkpoint_ids=["source-1"], successor_role="player"), now=1003)
        issued = self.ledger.issue_handoff("handoff-1", binding=handoff_binding(), now=1004)
        self.ledger.begin_request(handoff_claim(issued), now=1005)
        self.ledger.consume_handoff("claim-1", actor_id="replacement-player", actor_role="player", now=1006)
        for actor in ("player-test", "replacement-player"):
            with self.assertRaisesRegex(LedgerError, "actor"):
                self.ledger.complete_request("request-1", "partial", {"phase": self.prompt_receipt(actor_id=actor)}, now=1007)
        self.assertIsNone(self.ledger.request("request-1")["result"])

    def rewrite_request(self, identity, **changes):
        value = self.ledger.request(identity)["request"]
        value.update(changes)
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        self.ledger._db.execute("UPDATE requests SET payload=?,digest=? WHERE id=?",
            (payload, hashlib.sha256(payload.encode()).hexdigest(), identity))

    def test_phase_root_and_children_share_original_cap_exactly_once(self):
        root = phase_lifecycle()
        self.active_request(root)
        self.phase_input("request-1", "root-input")
        self.ledger.complete_request("request-1", "partial", {"awaiting": "player choice"}, now=1002)
        original = self.ledger.request("request-1")
        child = phase_skill(request_id="menu-child", phase_id="request-1")
        self.ledger.begin_request(child, now=1003)
        self.phase_input("menu-child", "menu-input", now=1003)
        self.assertFalse(self.ledger.prepare_primitive("menu-child", "menu-input", intent(), now=1004)["created"])
        self.ledger.complete_request("menu-child", "completed", {"choice": "One"}, now=1004)
        continuation = phase_lifecycle(request_id="continuation", phase_id="request-1")
        self.ledger.begin_request(continuation, now=1004)
        self.phase_input("continuation", "continuation-input", now=1004)
        self.assertFalse(self.ledger.begin_request(root, now=1005)["created"])
        with self.assertRaisesRegex(BudgetError, "[Pp]hase"):
            self.ledger.prepare_primitive("continuation", "fourth", intent(), now=1005)
        self.assertEqual(self.ledger.request("request-1"), original)
        self.assertEqual(self.ledger.snapshot(now=1005)["spent_inputs"], 3)
        self.reopen()
        self.assertEqual(self.ledger.request("request-1"), original)
        self.assertEqual(self.ledger.snapshot(now=1010)["spent_inputs"], 3)

    def test_item_and_activity_roots_accept_only_direct_control_children(self):
        self.ledger.activate(epoch=0, player_id="player-test", now=1001)
        for root_kind in ("item", "activity"):
            root_id = f"root-{root_kind}"
            self.ledger.begin_request(phase_skill(root_kind, request_id=root_id), now=1001)
            for child_kind in ("menu", "edit", "interact", "inspect"):
                child_id = f"{root_kind}-{child_kind}"
                self.ledger.begin_request(phase_skill(child_kind, request_id=child_id, phase_id=root_id), now=1001)
                self.phase_input(child_id, f"input-{child_id}", now=1001)
        self.assertEqual(self.reopen().snapshot(now=1010)["spent_inputs"], 8)

    def test_invalid_phase_links_roll_back_request_and_reservation(self):
        self.active_request(phase_lifecycle())
        for kind in ("menu", "edit", "interact", "inspect"):
            self.ledger.begin_request(phase_skill(kind, request_id=f"root-{kind}"), now=1001)
        self.ledger.begin_request(skill(request_id="root-navigate"), now=1001)
        self.ledger.begin_request(request(request_id="observe-only"), now=1001)
        self.ledger.begin_request(phase_skill(request_id="nested", phase_id="request-1"), now=1001)
        self.ledger.begin_request(phase_skill("item", request_id="root-item"), now=1001)
        bad = [phase_skill(request_id="bad", phase_id=parent) for parent in
               ("missing", "bad", "nested", "root-menu", "root-edit", "observe-only")]
        bad += [phase_skill(kind, request_id="bad", phase_id="request-1") for kind in ("item", "activity")]
        bad += [skill(request_id="bad", phase_id="request-1"),
                phase_skill("interact", request_id="bad", phase_id="root-navigate"),
                phase_skill("interact", request_id="bad", phase_id="root-interact"),
                phase_lifecycle(request_id="bad", phase_id="request-1", operation="load"),
                phase_lifecycle(request_id="bad", phase_id="root-item"),
                phase_lifecycle(request_id="bad", phase_id="request-1", world="other"),
                phase_lifecycle(request_id="bad", phase_id="request-1", character="other"),
                phase_skill(request_id="bad", phase_id="request-1", work_id="different-work"),
                phase_skill(request_id="bad", phase_id="request-1", mission_id="other")]
        before = tuple(self.ledger._db.execute("SELECT (SELECT count(*) FROM requests),(SELECT count(*) FROM reservations)"))
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ContractError):
                self.ledger.begin_request(value, now=1002)
            self.assertEqual(tuple(self.ledger._db.execute("SELECT (SELECT count(*) FROM requests),(SELECT count(*) FROM reservations)")), before)

    def test_inspection_root_owns_direct_prompt_children_with_original_limits(self):
        root = phase_skill("inspect", request_id="inspect-root",
                           limits=dict(primitives=1, wall_seconds=60, game_seconds=120))
        self.active_request(root)
        self.ledger.complete_request("inspect-root", "partial", {"verification_required": True}, now=1002)
        child = phase_skill(request_id="inspect-dismiss", phase_id="inspect-root")
        admitted = self.ledger.begin_request(child, now=1003)
        self.assertEqual(admitted["operation"]["deadline"], 1061)
        self.phase_input("inspect-dismiss", "dismiss", now=1003)
        with self.assertRaisesRegex(BudgetError, "Phase primitive"):
            self.phase_input("inspect-dismiss", "extra", now=1004)
        self.assertEqual(self.reopen().snapshot(now=1010)["spent_inputs"], 1)

    def test_previous_mission_admission_rejects_reopen_without_migrating_database(self):
        self.ledger._put("admission", {**self.a.to_dict(), "schema": "mission/4"})
        path = self.ledger.path
        self.ledger.close()
        before = path.read_bytes()
        with self.assertRaises(ContractError):
            MissionLedger(self.directory, now=1010)
        self.assertEqual(path.read_bytes(), before)

    def test_ordinary_interaction_prompt_reuses_original_root_budget_without_nested_interaction(self):
        root = phase_skill("interact", request_id="open-direction",
                           limits={"primitives": 2, "wall_seconds": 60, "game_seconds": 120})
        self.active_request(root)
        self.phase_input(root["request_id"], "open", now=1002)
        self.ledger.complete_request(root["request_id"], "partial", {"awaiting": "direction"}, now=1002)
        child = phase_skill(request_id="direction", phase_id=root["request_id"])
        self.assertEqual(self.ledger.begin_request(child, now=1003)["operation"]["deadline"], 1061)
        self.phase_input("direction", "east", now=1003)
        with self.assertRaisesRegex(BudgetError, "Phase"):
            self.ledger.prepare_primitive("direction", "extra", intent(), now=1004)
        with self.assertRaisesRegex(LedgerError, "before another interaction root"):
            self.ledger.begin_request(phase_skill("interact", request_id="nested-interaction", phase_id=root["request_id"]), now=1004)
        self.assertEqual(self.reopen().snapshot(now=1010)["spent_inputs"], 2)

    def test_phase_deadline_cannot_be_renewed_by_new_children(self):
        self.active_request(phase_lifecycle(limits={"primitives": 3, "wall_seconds": 10, "game_seconds": 1200}))
        long = phase_skill(request_id="long", phase_id="request-1")
        self.assertEqual(self.ledger.begin_request(long, now=1005)["operation"]["deadline"], 1011)
        short = phase_skill(request_id="short", phase_id="request-1",
                            limits={"primitives": 2, "wall_seconds": 2, "game_seconds": 10})
        self.assertEqual(self.ledger.begin_request(short, now=1005)["operation"]["deadline"], 1007)
        self.phase_input("long", "before-expiry", now=1010)
        with self.assertRaises(BudgetError): self.ledger.prepare_primitive("long", "at-expiry", intent(), now=1011)
        before = self.ledger._db.execute("SELECT count(*) FROM reservations").fetchone()
        with self.assertRaises(BudgetError):
            self.ledger.begin_request(phase_skill(request_id="late", phase_id="request-1"), now=1011)
        self.assertEqual(self.ledger._db.execute("SELECT count(*) FROM reservations").fetchone(), before)
        with self.assertRaises(LedgerError): self.ledger.request("late")
        self.assertEqual(self.reopen(now=1012).request("long")["deadline"], 1011)

    def test_phase_direct_root_input_cannot_bypass_child_costs(self):
        self.active_request(phase_lifecycle())
        self.ledger.begin_request(phase_skill(request_id="child", phase_id="request-1"), now=1001)
        self.phase_input("child", "child-input")
        self.phase_input("request-1", "root-one")
        self.phase_input("request-1", "root-two")
        with self.assertRaisesRegex(BudgetError, "Phase"):
            self.ledger.prepare_primitive("request-1", "over-cap", intent(), now=1003)
        self.assertEqual(len(self.ledger.primitive_records()), 3)

    def test_phase_deadline_still_obeys_original_mission_ceiling(self):
        self.active_request(phase_lifecycle(limits={"primitives": 3, "wall_seconds": 1800, "game_seconds": 1200}), now=7200)
        value = phase_lifecycle(request_id="continuation", phase_id="request-1",
                                limits={"primitives": 3, "wall_seconds": 1800, "game_seconds": 1200})
        self.assertEqual(self.ledger.begin_request(value, now=7250)["operation"]["deadline"], 8200)
        self.assertEqual(self.reopen(now=7251).request("request-1")["deadline"], 8200)

    def test_phase_admission_rejects_altered_root_deadline_or_noncanonical_payload(self):
        self.active_request(phase_lifecycle())
        original = self.ledger.request("request-1")
        self.ledger._db.execute("UPDATE requests SET deadline=deadline+1 WHERE id='request-1'")
        with self.assertRaises(LedgerError):
            self.ledger.begin_request(phase_skill(request_id="child", phase_id="request-1"), now=1002)
        self.ledger._db.execute("UPDATE requests SET deadline=? WHERE id='request-1'", (original["deadline"],))
        payload = json.dumps(original["request"])
        self.ledger._db.execute("UPDATE requests SET payload=?,digest=? WHERE id='request-1'",
            (payload, hashlib.sha256(payload.encode()).hexdigest()))
        with self.assertRaises(LedgerError):
            self.ledger.begin_request(phase_skill(request_id="child", phase_id="request-1"), now=1002)
        self.assertEqual(self.ledger._db.execute("SELECT count(*) FROM requests").fetchone()[0], 1)
        self.assertEqual(self.ledger._db.execute("SELECT count(*) FROM reservations").fetchone()[0], 1)

    def test_phase_keeps_child_own_limit_state_and_current_epoch(self):
        self.active_request(phase_lifecycle())
        self.ledger.complete_request("request-1", "partial", {"awaiting": "transition"}, now=1002)
        self.ledger.pause(cause="internal_lifecycle", reason="Verified lifecycle transition", now=1002)
        value = phase_skill(request_id="child", phase_id="request-1", epoch=1,
                            limits={"primitives": 1, "wall_seconds": 30, "game_seconds": 10})
        self.ledger.begin_request(value, now=1003)
        with self.assertRaises(LedgerError): self.ledger.prepare_primitive("child", "paused", intent(), now=1003)
        self.ledger.activate(epoch=1, player_id="player-test", now=1003)
        self.phase_input("child", "one", now=1003)
        with self.assertRaisesRegex(BudgetError, "Per-operation"):
            self.ledger.prepare_primitive("child", "two", intent(), now=1004)
        self.ledger.complete_request("child", "completed", {"done": True}, now=1004)
        self.ledger.begin_request(phase_skill(request_id="terminal", phase_id="request-1", epoch=1), now=1004)
        self.ledger.complete_request("terminal", "partial", {"done": False}, now=1004)
        with self.assertRaises(LedgerError): self.ledger.prepare_primitive("terminal", "terminal-input", intent(), now=1004)
        self.ledger.begin_request(phase_skill(request_id="stale", phase_id="request-1", epoch=1), now=1004)
        self.ledger.pause(cause="user", reason="User pause", now=1004)
        self.ledger.activate(epoch=2, player_id="player-test", now=1004)
        with self.assertRaises(LedgerError): self.ledger.prepare_primitive("stale", "stale-input", intent(), now=1004)
        self.assertEqual(self.reopen().snapshot(now=1010)["spent_inputs"], 1)

    def test_phase_crash_preserves_unknown_cost_and_does_not_restore_authority(self):
        self.active_request(phase_lifecycle())
        self.phase_input("request-1", "direct")
        self.ledger.complete_request("request-1", "partial", {"awaiting": "menu"}, now=1002)
        self.ledger.begin_request(phase_skill(request_id="child", phase_id="request-1"), now=1002)
        self.ledger.prepare_primitive("child", "uncertain", intent(), now=1003)
        self.ledger.published("uncertain", "native-uncertain", now=1003)
        snapshot = self.reopen().snapshot(now=1010)
        self.assertEqual((snapshot["spent_inputs"], snapshot["phase"], snapshot["epoch"]), (2, "paused", 1))
        self.assertFalse(snapshot["grants_authority"])
        self.assertEqual(self.ledger.primitive("uncertain")["state"], "unknown")
        self.assertEqual(self.ledger.request("child")["state"], "unknown")
        self.assertFalse(self.ledger.prepare_primitive("child", "uncertain", intent(), now=1011)["created"])
        with self.assertRaises(LedgerError): self.ledger.activate(epoch=1, player_id="player-test", now=1011)

    def test_phase_corrupt_parent_relationships_reject_on_reopen(self):
        for corruption in ("missing", "self", "nested", "future", "wrong-operation", "wrong-kind", "older-epoch"):
            with self.subTest(corruption=corruption):
                self.ledger.close()
                self.directory = Path(self.tmp.name) / corruption
                self.ledger = MissionLedger(self.directory, admission=self.a, now=1000)
                self.active_request(phase_lifecycle())
                self.ledger.begin_request(phase_skill(request_id="child", phase_id="request-1"), now=1002)
                self.ledger.begin_request(phase_lifecycle(request_id="future"), now=1002)
                if corruption in ("missing", "self", "future"):
                    self.rewrite_request("child", phase_id={"missing": "missing", "self": "child", "future": "future"}[corruption])
                elif corruption == "nested": self.rewrite_request("future", phase_id="child")
                elif corruption == "wrong-operation": self.rewrite_request("future", phase_id="request-1", operation="load")
                elif corruption == "wrong-kind": self.rewrite_request("request-1", **phase_skill(request_id="request-1"))
                else:
                    self.rewrite_request("request-1", epoch=1)
                    self.ledger._db.execute("UPDATE requests SET epoch=1 WHERE id='request-1'")
                    self.ledger.pause(cause="internal_lifecycle", reason="Transition", now=1002)
                self.ledger.close()
                with self.assertRaises(ContractError): MissionLedger(self.directory, now=1010)

    def test_phase_corrupt_deadline_or_cumulative_ceiling_reject_on_reopen(self):
        for corruption in ("child-deadline", "root-deadline", "cumulative-cap"):
            with self.subTest(corruption=corruption):
                self.ledger.close()
                self.directory = Path(self.tmp.name) / corruption
                self.ledger = MissionLedger(self.directory, admission=self.a, now=1000)
                self.active_request(phase_lifecycle(limits={"primitives": 3, "wall_seconds": 10, "game_seconds": 1200}))
                self.phase_input("request-1", "direct")
                self.ledger.begin_request(phase_skill(request_id="child", phase_id="request-1"), now=1002)
                self.phase_input("child", "child-input")
                if corruption == "cumulative-cap": self.rewrite_request("request-1", limits={"primitives": 1, "wall_seconds": 10, "game_seconds": 1200})
                else: self.ledger._db.execute("UPDATE requests SET deadline=deadline+1 WHERE id=?",
                    ("child" if corruption == "child-deadline" else "request-1",))
                self.ledger.close()
                with self.assertRaises(LedgerError): MissionLedger(self.directory, now=1010)

    def test_handoff_claim_is_durable_one_use_and_still_requires_readmission(self):
        before = self.ledger.snapshot(now=1000)
        issued = self.issue_handoff()
        self.assertEqual(issued["handoff_id"], "handoff-1")
        self.assertEqual(issued["epoch"], 1)
        self.assertFalse(issued["grants_authority"])
        with self.assertRaises(LedgerError): self.ledger.activate(epoch=1, player_id="player-test", now=1003)
        claim = handoff_claim(issued)
        self.ledger.begin_request(claim, now=1003)
        result = self.ledger.consume_handoff("claim-1", actor_id="replacement-player", actor_role="player", now=1004)
        state = self.ledger.snapshot(now=1004)
        self.assertEqual(state["phase"], "paused")
        self.assertEqual(state["deadline"], before["deadline"])
        self.assertEqual(state["remaining_inputs"], before["remaining_inputs"])
        self.assertEqual(state["player_id"], "replacement-player")
        self.assertFalse(result["grants_authority"])
        self.ledger.activate(epoch=1, player_id="replacement-player", now=1005)
        reopened = self.reopen(now=1006).snapshot(now=1006)
        self.assertEqual(reopened["player_id"], "replacement-player")
        self.assertEqual(reopened["phase"], "paused")
        self.assertEqual(self.ledger.request("handoff-1")["result"], issued)
        self.assertEqual(self.ledger.request("claim-1")["result"], result)

    def test_handoff_duplicates_return_original_results_without_budget_or_epoch_renewal(self):
        issued = self.issue_handoff()
        self.assertEqual(self.ledger.issue_handoff("handoff-1", binding=handoff_binding(), now=1003), issued)
        with self.assertRaises(LedgerError):
            self.ledger.issue_handoff("handoff-1", binding=handoff_binding(revision=31), now=1003)
        self.ledger.begin_request(handoff_claim(issued), now=1003)
        result = self.ledger.consume_handoff("claim-1", actor_id="replacement-player", actor_role="player", now=1004)
        result["epoch"] = 99
        again = self.ledger.consume_handoff("claim-1", actor_id="replacement-player", actor_role="player", now=1005)
        self.assertEqual(again["epoch"], 1)
        self.assertEqual(self.ledger.snapshot(now=1005)["epoch"], 1)
        self.assertEqual(self.ledger.snapshot(now=1005)["deadline"], 8200)

    def test_handoff_claim_exact_origin_boundary_and_actor_role_reject(self):
        issued = self.issue_handoff()
        for index, changes in enumerate((dict(expected_pause_origin="fault"), dict(expected_boundary_id="other"),
                dict(pause_generation=5), dict(takeover_generation=1), dict(expected_session="other"),
                dict(expected_revision=31), dict(player_id="player-test"))):
            value = handoff_claim(issued, request_id=f"bad-{index}", **changes)
            self.ledger.begin_request(value, now=1004)
            with self.assertRaises(LedgerError):
                self.ledger.consume_handoff(value["request_id"], actor_id=value["player_id"], actor_role="player", now=1004)
            self.ledger.complete_request(value["request_id"], "blocked", {"reason": "Exact binding rejected"}, now=1004)
        self.ledger.begin_request(handoff_claim(issued), now=1004)
        for actor, role in (("other-actor", "player"), ("replacement-player", "curator")):
            with self.assertRaises(LedgerError): self.ledger.consume_handoff("claim-1", actor_id=actor, actor_role=role, now=1005)
        self.ledger.consume_handoff("claim-1", actor_id="replacement-player", actor_role="player", now=1005)

    def test_handoff_human_pause_and_reopen_invalidate_without_relabelling(self):
        issued = self.issue_handoff()
        self.ledger.pause(cause="user", reason="User Pause wins", now=1003)
        current_epoch = self.ledger.snapshot(now=1003)["epoch"]
        value = handoff_claim(issued, epoch=current_epoch)
        self.ledger.begin_request(value, now=1003)
        with self.assertRaises(LedgerError):
            self.ledger.consume_handoff("claim-1", actor_id="replacement-player", actor_role="player", now=1004)
        self.reopen(now=1005)
        self.assertEqual(self.ledger.request("handoff-1")["result"], issued)
        value = handoff_claim(issued, request_id="claim-after-reopen", epoch=self.ledger.snapshot(now=1005)["epoch"])
        self.ledger.begin_request(value, now=1005)
        with self.assertRaises(LedgerError):
            self.ledger.consume_handoff(value["request_id"], actor_id="replacement-player", actor_role="player", now=1006)

    def test_stale_unconsumed_handoff_does_not_block_a_later_explicit_readmission(self):
        old = self.issue_handoff()
        paused = self.ledger.pause(cause="user", reason="Newer user event", now=1003)
        self.ledger.activate(epoch=paused["epoch"], player_id="player-test", now=1004)
        value = request("handoff", request_id="handoff-2", epoch=paused["epoch"], checkpoint_ids=["source-2"], successor_role="player")
        self.ledger.begin_request(value, now=1004)
        new = self.ledger.issue_handoff("handoff-2", binding=handoff_binding(revision=31, pause_generation=6), now=1005)
        self.assertGreater(new["epoch"], old["epoch"])
        self.assertEqual(self.ledger.request("handoff-1")["result"], old)

    def test_competing_handoff_claims_have_exactly_one_winner(self):
        issued = self.issue_handoff()
        for identity in ("claim-a", "claim-b"):
            self.ledger.begin_request(handoff_claim(issued, request_id=identity, player_id=identity), now=1003)
        def consume(identity):
            try:
                return self.ledger.consume_handoff(identity, actor_id=identity, actor_role="player", now=1004)
            except LedgerError:
                return None
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(consume, ("claim-a", "claim-b")))
        self.assertEqual(sum(result is not None for result in results), 1)

    def test_handoff_success_cannot_bypass_atomic_transitions(self):
        issued = self.issue_handoff()
        self.ledger.begin_request(handoff_claim(issued), now=1003)
        for identity in ("handoff-1", "claim-1"):
            with self.assertRaises(LedgerError):
                self.ledger.complete_request(identity, "completed", {}, now=1004)

    def test_handoff_issuance_requires_active_settled_work_and_eligible_origin(self):
        self.prepared()
        value = request("handoff", request_id="handoff-1", checkpoint_ids=[], successor_role="player")
        self.ledger.begin_request(value, now=1003)
        with self.assertRaises(LedgerError): self.ledger.issue_handoff("handoff-1", binding=handoff_binding(), now=1004)
        for origin in ("human", "fault"):
            with self.assertRaises(LedgerError): self.ledger.issue_handoff("handoff-1", binding=handoff_binding(pause_origin=origin), now=1004)
        self.ledger.pause(cause="user", reason="User stop", now=1004)
        with self.assertRaises(LedgerError): self.ledger.issue_handoff("handoff-1", binding=handoff_binding(), now=1005)

    def test_handoff_claim_cannot_spend_cleanup_reserve(self):
        issued = self.issue_handoff()
        self.ledger.begin_request(handoff_claim(issued), now=7299)
        with self.assertRaises(BudgetError):
            self.ledger.consume_handoff("claim-1", actor_id="replacement-player", actor_role="player", now=7300)
        self.assertEqual(self.ledger.snapshot(now=7300)["phase"], "handoff")

    def test_handoff_cap_and_actor_chain_survive_reopen(self):
        self.ledger.activate(epoch=0, player_id="player-test", now=1001)
        for index in range(16):
            now = 1002 + index * 4
            epoch = self.ledger.snapshot(now=now)["epoch"]
            identity = f"handoff-{index}"
            self.ledger.begin_request(request("handoff", request_id=identity, epoch=epoch, checkpoint_ids=[], successor_role="player"), now=now)
            issued = self.ledger.issue_handoff(identity, binding=handoff_binding(), now=now)
            claim = handoff_claim(issued, request_id=f"claim-{index}", player_id=f"player-{index}")
            self.ledger.begin_request(claim, now=now+1)
            self.ledger.consume_handoff(claim["request_id"], actor_id=claim["player_id"], actor_role="player", now=now+1)
            self.ledger.activate(epoch=issued["epoch"], player_id=claim["player_id"], now=now+2)
        self.ledger.begin_request(request("handoff", request_id="handoff-overflow", epoch=16, checkpoint_ids=[], successor_role="player"), now=1100)
        with self.assertRaises(BudgetError): self.ledger.issue_handoff("handoff-overflow", binding=handoff_binding(), now=1100)
        self.assertEqual(self.reopen(now=1101).snapshot(now=1101)["player_id"], "player-15")

    def test_handoff_result_and_epoch_roll_back_together(self):
        self.active_request(request("handoff", request_id="handoff-1", checkpoint_ids=[], successor_role="player"))
        original_put = self.ledger._put
        def fail_transition(key, value):
            if key == "state" and value["phase"] == "handoff":
                raise sqlite3.OperationalError("Injected failure after receipt, before state")
            return original_put(key, value)
        with patch.object(self.ledger, "_put", side_effect=fail_transition):
            with self.assertRaises(LedgerError): self.ledger.issue_handoff("handoff-1", binding=handoff_binding(), now=1002)
        self.assertEqual(self.ledger.snapshot(now=1002)["epoch"], 0)
        self.assertIsNone(self.ledger.request("handoff-1")["result"])
        self.assertIsNotNone(self.ledger._db.execute("SELECT id FROM reservations WHERE id='request:handoff-1'").fetchone())
        self.assertEqual(self.ledger.issue_handoff("handoff-1", binding=handoff_binding(), now=1003)["epoch"], 1)

    def test_full_storage_preserves_reserved_handoff_and_claim_receipts(self):
        self.ledger.close()
        self.directory = Path(self.tmp.name) / "handoff-capacity"
        with patch("harness.gameplay.mission_ledger.MAX_DATABASE_BYTES", 512 * 1024):
            self.ledger = MissionLedger(self.directory, admission=self.a, now=1000)
            self.active_request(request("handoff", request_id="handoff-1", checkpoint_ids=[], successor_role="player"))
            db = self.ledger._db
            db.execute("CREATE TABLE storage_pressure (payload BLOB)")
            def fill():
                while True:
                    try: db.execute("INSERT INTO storage_pressure VALUES (zeroblob(4096))")
                    except sqlite3.OperationalError as error:
                        self.assertIn("full", str(error))
                        return
            fill()
            issued = self.ledger.issue_handoff("handoff-1", binding=handoff_binding(), now=1002)
            db.execute("DELETE FROM storage_pressure WHERE rowid IN (SELECT rowid FROM storage_pressure LIMIT 32)")
            self.ledger.begin_request(handoff_claim(issued), now=1003)
            fill()
            receipt = self.ledger.consume_handoff("claim-1", actor_id="replacement-player", actor_role="player", now=1004)
            self.assertEqual(self.ledger.request("claim-1")["result"], receipt)
            self.assertEqual(self.reopen(now=1005).snapshot(now=1005)["player_id"], "replacement-player")

    def test_reopen_rejects_typed_but_contradictory_handoff_history(self):
        issued = self.issue_handoff()
        self.ledger.begin_request(handoff_claim(issued), now=1003)
        receipt = self.ledger.consume_handoff("claim-1", actor_id="replacement-player", actor_role="player", now=1004)
        receipt["actor_role"] = "curator"
        self.ledger.close()
        with closing(sqlite3.connect(self.ledger.path)) as connection, connection:
            connection.execute("UPDATE requests SET result=? WHERE id='claim-1'",
                               (json.dumps(receipt, sort_keys=True, separators=(",", ":")),))
        with self.assertRaisesRegex(LedgerError, "actor binding"):
            MissionLedger(self.directory, now=1005)

    def test_earlier_ledger_format_is_rejected_without_conversion(self):
        self.ledger.close()
        for version in range(1, 12):
            with self.subTest(version=version):
                with closing(sqlite3.connect(self.ledger.path)) as connection, connection:
                    connection.execute(f"PRAGMA user_version={version}")
                original = self.ledger.path.read_bytes()
                with self.assertRaisesRegex(LedgerError, "Unsupported mission ledger version"):
                    MissionLedger(self.directory, now=1001)
                self.assertEqual(self.ledger.path.read_bytes(), original)

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
        with closing(sqlite3.connect(self.ledger.path)) as connection, connection: connection.execute("PRAGMA user_version=999")
        before = hashlib.sha256(self.ledger.path.read_bytes()).hexdigest()
        with self.assertRaises(LedgerError): MissionLedger(self.directory, now=1001)
        self.assertEqual(hashlib.sha256(self.ledger.path.read_bytes()).hexdigest(), before)

    def test_intent_and_charge_are_committed_before_publication(self):
        self.prepared()
        with closing(sqlite3.connect(self.ledger.path)) as reader, reader:
            row = reader.execute("SELECT state,native_id FROM primitives WHERE id='logical-1'").fetchone()
            state = json.loads(reader.execute("SELECT value FROM metadata WHERE key='state'").fetchone()[0])
        self.assertEqual(row, ("prepared", None))
        self.assertEqual(state["spent_inputs"], 1)
        self.assertFalse(self.ledger.snapshot(now=1002)["grants_authority"])

    def test_resume_is_charged_before_publication_and_crash_retains_unknown(self):
        lifecycle = request("lifecycle", operation="create", world="test-world", character="test-person",
            sources=["source-1"], expected_session="native-session", expected_revision=30,
            expected_boundary_id="boundary-1", limits={"primitives": 2, "wall_seconds": 120, "game_seconds": 3600})
        self.active_request(lifecycle)
        resume = intent(kind="resume", value=None)
        self.ledger.prepare_primitive("request-1", "resume-1", resume, now=1002)
        with closing(sqlite3.connect(self.ledger.path)) as reader:
            encoded, state, native_id = reader.execute(
                "SELECT intent,state,native_id FROM primitives WHERE id='resume-1'").fetchone()
            self.assertEqual(json.loads(encoded), resume)
            self.assertEqual((state, native_id), ("prepared", None))
            persisted = json.loads(reader.execute("SELECT value FROM metadata WHERE key='state'").fetchone()[0])
            self.assertEqual(persisted["spent_inputs"], 1)
        reopened = self.reopen(now=1003)
        self.assertEqual(reopened.primitive("resume-1")["state"], "unknown")
        self.assertEqual(reopened.snapshot(now=1003)["spent_inputs"], 1)
        self.assertFalse(reopened.snapshot(now=1003)["grants_authority"])
        self.assertFalse(reopened.prepare_primitive("request-1", "resume-1", resume, now=1003)["created"])
        with self.assertRaises(LedgerError):
            reopened.prepare_primitive("request-1", "resume-retry", resume, now=1003)

    def test_resume_cannot_borrow_a_skill_or_action_value(self):
        self.active_request()
        for value in (intent(kind="resume", value="RESUME"), intent(kind="resume", value=None), intent(value=None)):
            with self.subTest(value=value), self.assertRaises(LedgerError):
                self.ledger.prepare_primitive("request-1", "invalid-resume", value, now=1002)
        self.assertEqual(self.ledger.snapshot(now=1002)["spent_inputs"], 0)

    def test_reopen_rejects_resume_tampered_under_skill_parent(self):
        self.prepared()
        self.ledger.close()
        with closing(sqlite3.connect(self.ledger.path)) as connection, connection:
            connection.execute("UPDATE primitives SET intent=? WHERE id='logical-1'",
                (json.dumps(intent(kind="resume", value=None), sort_keys=True, separators=(",", ":")),))
        original = self.ledger.path.read_bytes()
        with self.assertRaisesRegex(LedgerError, "Resume requires lifecycle/readmission or its activity resume child"):
            MissionLedger(self.directory, now=1003)
        self.assertEqual(self.ledger.path.read_bytes(), original)

    def test_prepared_intent_requires_actual_preflight_and_scoped_refresh(self):
        self.active_request()
        refreshed = SourceRevalidation(binding(), binding(source_id="fresh-1", store_generation=2), "native_state")
        missing = intent(); missing.pop("preflight_source")
        invalid = [missing, intent(preflight_source=None), intent(preflight_source=""),
                   intent(revalidation=refreshed.to_dict()),
                   intent(source_before="fresh-1", revalidation=SourceRevalidation(
                       binding(source_id="not-in-request"), binding(source_id="fresh-1", store_generation=2), "native_state").to_dict()),
                   intent(source_before="fresh-1", revalidation=SourceRevalidation(
                       binding(epoch=1), binding(epoch=1, source_id="fresh-1", store_generation=2), "native_state").to_dict()),
                   intent(source_before="fresh-1", revalidation=SourceRevalidation(
                       binding(actor_id="other"), binding(actor_id="other", source_id="fresh-1", store_generation=2), "native_state").to_dict())]
        for index, value in enumerate(invalid):
            with self.subTest(index=index), self.assertRaises(ContractError):
                self.ledger.prepare_primitive("request-1", f"invalid-{index}", value, now=1002)
        self.assertEqual(self.ledger.snapshot(now=1002)["spent_inputs"], 0)
        self.ledger.prepare_primitive("request-1", "logical-refresh", intent(source_before="fresh-1",
            revalidation=refreshed.to_dict()), now=1002)
        reopened = self.reopen(now=1003).primitive("logical-refresh")
        self.assertEqual(reopened["intent"]["preflight_source"], "preflight-1")
        self.assertEqual(reopened["intent"]["revalidation"], refreshed.to_dict())
        self.assertEqual(reopened["state"], "unknown")

    def test_reopen_validates_refresh_actor_at_original_request_epoch(self):
        self.active_request()
        first = SourceRevalidation(binding(), binding(source_id="fresh-1", store_generation=2), "native_state")
        self.ledger.prepare_primitive("request-1", "logical-old", intent(source_before="fresh-1", revalidation=first.to_dict()), now=1002)
        self.ledger.settle_primitive("logical-old", "returned", known_receipt(logical_id="logical-old",
            proposed=intent(source_before="fresh-1", revalidation=first.to_dict())), now=1003)
        self.ledger.complete_request("request-1", "completed", {"synthetic": True}, now=1003)
        self.ledger.begin_request(request("handoff", request_id="handoff-actor", checkpoint_ids=["source-1"], successor_role="player"), now=1004)
        issued = self.ledger.issue_handoff("handoff-actor", binding=handoff_binding(), now=1005)
        self.ledger.begin_request(handoff_claim(issued), now=1006)
        self.ledger.consume_handoff("claim-1", actor_id="replacement-player", actor_role="player", now=1007)
        self.ledger.activate(epoch=1, player_id="replacement-player", now=1008)
        self.ledger.begin_request(skill(request_id="replacement-skill", epoch=1, sources=["replacement-source"]), now=1009)
        second = SourceRevalidation(
            binding(source_id="replacement-source", epoch=1, actor_id="replacement-player"),
            binding(source_id="replacement-fresh", epoch=1, actor_id="replacement-player", store_generation=2), "native_state")
        self.ledger.prepare_primitive("replacement-skill", "logical-new", intent(source_before="replacement-fresh",
            preflight_source="replacement-preflight", revalidation=second.to_dict()), now=1010)
        self.reopen(now=1011)
        self.assertEqual(self.ledger.primitive("logical-old")["state"], "returned")
        self.assertEqual(self.ledger.primitive("logical-new")["state"], "unknown")
        corrupt = self.ledger.primitive("logical-new")["intent"]
        for key in ("original", "current"): corrupt["revalidation"][key]["actor_id"] = "player-test"
        self.ledger.close()
        with closing(sqlite3.connect(self.ledger.path)) as connection, connection:
            connection.execute("UPDATE primitives SET intent=? WHERE id='logical-new'",
                               (json.dumps(corrupt, sort_keys=True, separators=(",", ":")),))
        with self.assertRaisesRegex(LedgerError, "actor"):
            MissionLedger(self.directory, now=1012)

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

    def test_effect_history_is_copied_and_retains_unresolved_intents_for_memory(self):
        self.prepared()
        records = self.ledger.primitive_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["state"], "prepared")
        records[0]["intent"]["expected_revision"] = 999
        self.assertEqual(self.ledger.primitive_records()[0]["intent"]["expected_revision"], 30)
        self.reopen()
        self.assertEqual(self.ledger.primitive_records()[0]["state"], "unknown")
        self.assertFalse(self.ledger.snapshot(now=1010)["grants_authority"])

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
            self.ledger.settle_primitive(f"logical-{n}", "returned", known_receipt(
                logical_id=f"logical-{n}", native_id=f"native-{n}"), now=1001+n)
        with self.assertRaises(BudgetError): self.ledger.prepare_primitive("request-1", "logical-3", intent(), now=1004)
        self.assertEqual(self.ledger.snapshot(now=1004)["spent_inputs"], 2)
        state = self.ledger.begin_finishing(epoch=0, reason="Normal ending", now=1004)
        cleanup = request("lifecycle", request_id="cleanup", epoch=state["epoch"], operation="finish",
                          world="test-world", character="test-person", sources=["source-1"], expected_session="native-session",
                          expected_revision=30, expected_boundary_id="boundary-1", limits={"primitives": 2, "wall_seconds": 120, "game_seconds": 1})
        self.ledger.begin_request(cleanup, now=1004)
        self.ledger.prepare_primitive("cleanup", "logical-3", intent(), now=1005, cleanup=True)
        self.ledger.settle_primitive("logical-3", "returned", known_receipt(
            logical_id="logical-3", native_id="native-3"), now=1006)
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
        receipt = {"status": "timeout", **published_receipt()}
        self.ledger.settle_primitive("logical-1", "unknown", receipt, now=1004)
        with self.assertRaises(LedgerError): self.ledger.complete_request("request-1", "completed", {"goal": "reached"}, now=1005)
        reconcile_fixture(self.ledger, note="Controller custody separately established; original ACK remains unknown", now=1005)
        self.ledger.complete_request("request-1", "completed", {"goal": "reached", "delivery": "unknown"}, now=1006)
        self.assertEqual(self.ledger.primitive("logical-1")["state"], "unknown")
        self.assertEqual(self.ledger.primitive("logical-1")["result"], receipt)
        with self.assertRaises(LedgerError): self.ledger.settle_primitive("logical-1", "returned", known_receipt(), now=1007)
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
        with self.assertRaises(LedgerError): self.ledger.settle_primitive("logical-1", "returned", known_receipt(), now=1004)
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
        with closing(sqlite3.connect(self.ledger.path)) as connection, connection:
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
            self.ledger.begin_request({"schema": "mission/10", "kind": "status", "mission_id": "mission-test"}, now=1003)
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
        self.ledger.finish_mission("stopped", request_id=None, epoch=self.ledger.snapshot(now=1004)["epoch"], reason="Retained failed attempt", now=1004)
        self.ledger.settle_primitive("logical-1", "unknown", {"status": "timeout"}, now=1005)
        # A stopped mission cannot admit a new reconciliation or regain input.
        with self.assertRaises(LedgerError):
            self.ledger.begin_request(request("reconcile", request_id="late-resolution", epoch=1,
                unresolved_request_id="request-1", evidence_id="fresh-after", reason="Late evidence"), now=1006)
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

    def test_unknown_primitive_and_operation_share_one_revocation_epoch(self):
        self.prepared(native=True)
        self.ledger.settle_primitive("logical-1", "unknown", {"status": "timeout"}, now=1004)
        first = self.ledger.snapshot(now=1004)
        self.ledger.complete_request("request-1", "unknown", {"reason": "Delivery remains unknown"}, now=1005)
        final = self.ledger.snapshot(now=1005)
        for key in ("epoch", "phase", "pause_cause", "reason", "spent_inputs"):
            self.assertEqual(final[key], first[key])
        self.assertEqual(final["epoch"], 1)
        self.assertEqual(self.ledger.request("request-1")["state"], "unknown")
        self.assertEqual(self.ledger.primitive("logical-1")["state"], "unknown")
        self.assertEqual(self.reopen().request("request-1")["result"], {"reason": "Delivery remains unknown"})

    def test_late_unknown_receipt_preserves_user_pause_cause_and_epoch(self):
        self.prepared(native=True)
        paused = self.ledger.pause(cause="user", reason="User chose Pause", now=1004)
        self.ledger.settle_primitive("logical-1", "unknown", {"status": "timeout"}, now=1005)
        self.ledger.complete_request("request-1", "unknown", {"reason": "Unknown after Pause"}, now=1006)
        state = self.ledger.snapshot(now=1006)
        for key in ("epoch", "phase", "pause_cause", "reason"):
            self.assertEqual(state[key], paused[key])
        self.assertEqual(state["unreconciled"], 1)
        self.assertEqual(state["spent_inputs"], 1)

    def test_paused_operation_result_preserves_explicit_takeover(self):
        self.active_request()
        paused = self.ledger.pause(cause="takeover", reason="Native human input", now=1002)
        self.ledger.complete_request("request-1", "paused", {"reason": "Canceled by takeover"}, now=1003)
        state = self.ledger.snapshot(now=1003)
        for key in ("epoch", "phase", "pause_cause", "reason"):
            self.assertEqual(state[key], paused[key])

    def test_reopen_rejects_corrupt_intent_effect_result_or_reservation(self):
        self.prepared(native=True)
        self.ledger.settle_primitive("logical-1", "unknown", {"status": "timeout", **published_receipt()}, now=1004)
        reconcile_fixture(self.ledger, note="Synthetic captured custody", now=1005)
        self.ledger.close()
        original = self.ledger.path.read_bytes()
        mutations = ["UPDATE primitives SET intent='{}'", "UPDATE primitives SET effect='{}'",
                     "UPDATE primitives SET result='[]'", "UPDATE reservations SET space=zeroblob(10)",
                     "UPDATE primitives SET state='returned'", "UPDATE requests SET result='[]'"]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.ledger.path.write_bytes(original)
                with closing(sqlite3.connect(self.ledger.path)) as connection, connection: connection.execute(mutation)
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
            with self.assertRaises(LedgerError):
                self.ledger.begin_request(request("reconcile", request_id="capacity-resolution", epoch=1,
                    unresolved_request_id="request-1", evidence_id="fresh-after", reason="Storage full"), now=1005)
            self.ledger.complete_request("request-1", "partial", receipt, now=1006)
            self.assertEqual(self.ledger.primitive("logical-1")["result"], receipt)
            self.assertEqual(self.ledger.request("request-1")["result"], receipt)
            while True:
                try: db.execute("INSERT INTO storage_pressure VALUES (zeroblob(4096))")
                except sqlite3.OperationalError: break
            with self.assertRaises(LedgerError): self.ledger.begin_request(skill(request_id="too-full", epoch=1), now=1007)
            self.assertEqual(self.ledger.snapshot(now=1007)["spent_inputs"], 1)

    def test_terminal_mission_cannot_restart_or_overwrite_result(self):
        self.ledger.finish_mission("stopped", request_id=None, epoch=self.ledger.snapshot(now=1001)["epoch"], reason="Known unsupported capability", now=1001)
        self.reopen()
        self.assertEqual(self.ledger.snapshot(now=1010)["phase"], "stopped")
        with self.assertRaises(LedgerError): self.ledger.activate(epoch=1, player_id="player-test", now=1010)
        with self.assertRaises(LedgerError): self.ledger.begin_request(skill(epoch=1), now=1010)
        with self.assertRaises(LedgerError): self.ledger.finish_mission("completed", request_id=None, epoch=self.ledger.snapshot(now=1010)["epoch"], reason="relabel", now=1010)


if __name__ == "__main__": unittest.main()
