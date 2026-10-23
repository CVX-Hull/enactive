"""Small independently shaped ledger projections; no native acceptance evidence."""
from copy import deepcopy
import json
import unittest
from types import SimpleNamespace

from harness.gameplay.contracts import ContractError
from harness.gameplay.creation_provenance import creation_input_chain, validate_creation_sources


def request_record(identity, *, kind="lifecycle", phase="create-root", epoch=2):
    data = dict(schema="mission/10", kind=kind, request_id=identity,
        mission_id="mission-a", epoch=epoch, work_id=None, phase_id=phase,
        sources=["informing-" + identity], expected_session="setup-session",
        expected_revision=10, expected_boundary_id="menu-boundary",
        limits=dict(primitives=16, wall_seconds=120, game_seconds=1200))
    if kind == "lifecycle":
        data.update(operation="create", world="World", character="Same Name", identity_claim_ids=[])
    else:
        data.update(skill_kind="menu", goal=dict(purpose="Choose", label="Yes", outcome="activated"),
            perception=None, procedure=None)
    return dict(request=data, epoch=epoch, state="partial", result=None, admitted_at=100, deadline=220)


def primitive_record(identity, owner, *, revision=10, action="NEXT_TAB", kind="action", state="returned"):
    intent = dict(kind=kind, value=action, expected_session="setup-session", expected_revision=revision,
        expected_boundary_id="menu-boundary", source_before="before-" + identity,
        preflight_source="preflight-" + identity, revalidation=None, input_observation=None,
        reservation_id="reservation-" + identity)
    native = dict(protocol=6, id="native-" + identity, kind=kind, session="setup-session", revision=revision,
        boundary_id="menu-boundary", takeover_generation=0,
        authority=dict(controller_boot_id="boot-a", counter=revision), deadline_ms=1000,
        frame=f"frame-setup-session-{revision}.png", require_exact_frame=False,
        **{"input" if kind == "direct" else kind: action})
    receipt = {key: intent[key] for key in ("kind", "value", "expected_session", "expected_revision",
        "expected_boundary_id", "source_before", "preflight_source")}
    receipt.update(logical_action_id=identity, native_request_id=native["id"], published=True,
        native_request_json=json.dumps(native, sort_keys=True, ensure_ascii=True, separators=(",", ":")),
        dispatch_binding=dict(controller_boot_id="boot-a", operator_pause_generation=0,
            takeover_generation=0, actor_id="player-a", epoch=2, game_anchor_source_id="before-" + identity),
        transport_disposition=state, received_monotonic=None, source_after=None, native_ack=None,
        processing_error=None, evidence_loss=None)
    if state == "returned":
        receipt.update(received_monotonic=100 + revision, evidence_loss="Synthetic omitted after-source",
            native_ack=dict(protocol=6, id=native["id"], session="setup-session", revision=revision + 1,
                status="ready", error="", paused=False, pause_origin="none", takeover_generation=0,
                timestamp_ms=1000, frame_ok=True, frame=f"frame-setup-session-{revision + 1}.png",
                boundary=dict(kind="menu", id="menu-boundary", control_generation=0, input_receiver=True,
                    recovery_operations=[], interrupt_request_id=None)))
    return dict(logical_id=identity, request_id=owner, intent=intent, native_id=native["id"],
        state=state, result=receipt, effect=None)


class CreationProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.requests = [request_record("create-root", phase=None), request_record("commit"),
            request_record("confirm", kind="skill"), request_record("terminal", kind="skill")]
        self.primitives = [primitive_record("stage", "commit"),
            primitive_record("confirmation", "confirm", revision=11, action="YES"),
            primitive_record("last", "terminal", revision=12, action="YES", state="unknown")]

    def chain(self):
        return creation_input_chain(tuple(self.requests), tuple(self.primitives), root_id="create-root",
            terminal_request_id="terminal", terminal_logical_id="last")

    def test_unknown_terminal_preserves_exact_raw_chain_without_ack_or_after_source(self):
        original = deepcopy((self.requests, self.primitives))
        result = self.chain()
        self.assertEqual(result, tuple(self.primitives))
        self.assertTrue(all(actual is raw for actual, raw in zip(result, self.primitives)))
        self.assertEqual((self.requests, self.primitives), original)

    def test_returned_raw_direct_terminal_and_intermediate_confirmation(self):
        self.requests[-1]["request"].update(skill_kind="direct", goal=dict(
            input=dict(type="key", key="y", modifiers=[]), intent="Answer visible confirmation",
            expected="Finish creation", interrupt_allowed=False))
        self.primitives[-1] = primitive_record("last", "terminal", revision=12,
            action=dict(type="key", key="y", modifiers=[]), kind="direct")
        self.assertEqual([p["logical_id"] for p in self.chain()], ["stage", "confirmation", "last"])
        self.primitives[-1] = primitive_record("last", "terminal", revision=12,
            action=dict(type="key", key="y", modifiers=[]), kind="direct", state="unknown")
        self.assertEqual(self.chain(), tuple(self.primitives))

    def test_request_names_labels_and_private_stage_flags_do_not_establish_commit(self):
        self.requests[1]["request"].update(kind="skill", skill_kind="menu",
            goal=dict(purpose="character_confirmation", label="NEXT_TAB", outcome="activated"),
            procedure=None, perception=None)
        for key in ("operation", "world", "character", "identity_claim_ids"):
            del self.requests[1]["request"][key]
        self.requests[1]["result"] = {"phase": {"stage": "character_confirmation"}}
        with self.assertRaises(ContractError):
            self.chain()

    def test_missing_stage_cannot_turn_same_named_load_under_create_root_into_creation(self):
        self.primitives.pop(0)
        self.primitives[0]["intent"]["value"] = "UILIST.CONFIRM"
        with self.assertRaises(ContractError):
            self.chain()

    def test_stage_must_be_returned_published_and_a_direct_create_child(self):
        for change in ("unpublished", "unknown", "root-owner", "wrong-root", "wrong-operation"):
            with self.subTest(change=change):
                original = deepcopy((self.requests, self.primitives))
                if change == "unpublished":
                    self.primitives[0]["result"]["published"] = False
                elif change == "unknown":
                    self.primitives[0]["state"] = "unknown"
                elif change == "root-owner":
                    self.primitives[0]["request_id"] = "create-root"
                elif change == "wrong-root":
                    self.requests[1]["request"]["phase_id"] = "another-root"
                else:
                    self.requests[1]["request"]["operation"] = "load"
                with self.assertRaises(ContractError):
                    self.chain()
                self.requests, self.primitives = original

    def test_foreign_owner_epoch_mission_work_and_session_cannot_join_chain(self):
        for field, value in (("phase_id", "foreign"), ("epoch", 3), ("mission_id", "foreign"),
                ("work_id", "foreign"), ("expected_session", "foreign")):
            with self.subTest(field=field):
                original = deepcopy(self.requests)
                self.requests[2]["request"][field] = value
                with self.assertRaises(ContractError):
                    self.chain()
                self.requests = original

    def test_unsettled_published_or_resumed_intermediate_is_not_confirmation(self):
        for state in ("unknown", "prepared", "published", "rejected", "not_dispatched"):
            with self.subTest(state=state):
                original = deepcopy(self.primitives)
                self.primitives[1]["state"] = state
                with self.assertRaises(ContractError):
                    self.chain()
                self.primitives = original
        self.primitives[1]["intent"].update(kind="resume", value=None)
        with self.assertRaises(ContractError):
            self.chain()

    def test_known_unpublished_nondelivery_is_retained_without_becoming_a_dispatch(self):
        p = self.primitives[1]
        p.update(state="not_dispatched", native_id=None)
        p["result"].update(published=False, native_request_id=None, native_request_json=None,
            native_ack=None, source_after=None, transport_disposition="not_dispatched")
        self.assertEqual(self.chain(), (self.primitives[0], self.primitives[-1]))
        self.assertEqual(p["state"], "not_dispatched")

    def test_authenticated_native_rejection_is_not_a_confirmation_or_stage_reset(self):
        p = self.primitives[1]
        p["state"] = "rejected"
        p["result"].update(transport_disposition="rejected", source_after=None, evidence_loss=None)
        p["result"]["native_ack"].update(status="rejected", revision=11, error="Unsupported event")
        self.assertEqual(self.chain(), (self.primitives[0], self.primitives[-1]))
        self.assertEqual(p["state"], "rejected")
        for fault in ("ack", "native-id", "custody"):
            with self.subTest(fault=fault):
                original = deepcopy(p)
                if fault == "ack":
                    p["result"]["native_ack"]["status"] = "ready"
                elif fault == "native-id":
                    p["result"]["native_request_id"] = "another-request"
                else:
                    p["result"]["dispatch_binding"]["actor_id"] = "another-player"
                with self.assertRaises(ContractError):
                    self.chain()
                p.clear()
                p.update(original)

    def test_unpublished_stage_or_resume_attempt_did_not_reset_creation(self):
        self.requests[2] = request_record("confirm")
        for kind, value in (("action", "NEXT_TAB"), ("action", "FINALIZE"), ("resume", None)):
            with self.subTest(kind=kind, value=value):
                p = primitive_record("confirmation", "confirm", revision=11, kind=kind, action=value)
                p.update(state="not_dispatched", native_id=None)
                p["result"].update(published=False, native_request_id=None, native_request_json=None,
                    native_ack=None, source_after=None, transport_disposition="not_dispatched")
                self.primitives[1] = p
                self.assertEqual(self.chain(), (self.primitives[0], self.primitives[-1]))

    def test_latest_explicit_character_commit_replaces_earlier_candidate(self):
        earlier = primitive_record("earlier", "commit", revision=9)
        self.primitives.insert(0, earlier)
        self.assertEqual(self.chain(), tuple(self.primitives[1:]))

    def test_stage_reset_or_wrong_candidate_cannot_use_earlier_commit(self):
        for action in ("FINALIZE", "NEXT_TAB"):
            with self.subTest(action=action):
                self.primitives[1]["intent"]["value"] = action
                with self.assertRaises(ContractError):
                    self.chain()

    def test_terminal_requires_exact_owner_and_supported_raw_native_state(self):
        for field, value in (("request_id", "confirm"), ("state", "prepared"), ("state", "rejected")):
            with self.subTest(field=field, value=value):
                original = deepcopy(self.primitives)
                self.primitives[-1][field] = value
                with self.assertRaises(ContractError):
                    self.chain()
                self.primitives = original

    def test_later_identity_or_reconciliation_does_not_replace_named_terminal(self):
        self.requests.append(request_record("later"))
        self.primitives.append(primitive_record("later-input", "later", revision=13, action="UP"))
        self.assertEqual(self.chain(), tuple(self.primitives[:3]))

    def test_order_and_published_correlation_mutations_fail(self):
        mutations = (lambda: self.primitives.reverse(),
            lambda: self.requests.reverse(),
            lambda: self.primitives[0]["result"].update(logical_action_id="other"),
            lambda: self.primitives[0]["result"]["native_ack"].update(id="other"),
            lambda: self.primitives[-1]["result"].update(native_request_id="other"),
            lambda: self.primitives[-1]["result"].update(native_request_json="{}"),
            lambda: self.primitives[-1]["result"]["dispatch_binding"].update(actor_id="other"),
            lambda: self.primitives[-1]["result"]["dispatch_binding"].update(epoch=3),
            lambda: self.primitives[-1]["result"].update(source_before="other"),
            lambda: self.primitives.insert(1, deepcopy(self.primitives[0])))
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                original = deepcopy((self.requests, self.primitives))
                mutation()
                with self.assertRaises(ContractError):
                    self.chain()
                self.requests, self.primitives = original


class CreationSourceTests(unittest.TestCase):
    """Receiver chronology only; archive integrity has separate real-store tests."""

    def setUp(self):
        stage = primitive_record("stage", "commit", revision=10)
        stage["result"]["source_after"] = "after-stage"
        terminal = primitive_record("last", "terminal", revision=12, action="YES", state="unknown")
        self.chain = (stage, terminal)
        ids = ("before-stage", "preflight-stage", "after-stage", "before-last", "preflight-last")
        self.refs = tuple(SimpleNamespace(observation_id=identity, session="setup-session", revision=revision)
            for identity, revision in zip(ids, (10, 10, 11, 12, 12)))
        self.observations = {identity: dict(category="NEW_CHAR_DESCRIPTION" if index < 2 else "YESNO",
            takeover_generation=0, boundary=dict(id="menu-boundary", control_generation=1))
            for index, identity in enumerate(ids)}
        self.store = SimpleNamespace(historical_references=self.refs,
            observation=lambda ref: self.observations[ref.observation_id])

    def validate(self):
        validate_creation_sources(self.chain, self.store, terminal_before=self.refs[3])

    def test_committed_form_through_unknown_terminal_has_valid_source_chain(self):
        self.validate()

    def test_older_same_category_form_cannot_authenticate_actual_commit(self):
        self.refs[0].revision = self.refs[1].revision = 9
        with self.assertRaisesRegex(ContractError, "source chain"):
            self.validate()

    def test_changed_control_generation_or_preflight_receiver_retires_commitment(self):
        for field in ("control_generation", "id"):
            with self.subTest(field=field):
                original = deepcopy(self.observations)
                self.observations["preflight-stage"]["boundary"][field] = 2 if field == "control_generation" else "another-boundary"
                with self.assertRaises(ContractError):
                    self.validate()
                self.observations = original

    def test_observed_intermediate_main_menu_retires_commitment(self):
        self.observations["after-stage"]["category"] = "MAIN_MENU"
        with self.assertRaises(ContractError):
            self.validate()


if __name__ == "__main__":
    unittest.main()
