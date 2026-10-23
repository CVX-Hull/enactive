"""Synthetic ledger/source adoption proofs; no native acceptance or input authority."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from harness.gameplay.campaign_memory import CampaignMemory
from harness.gameplay.contracts import ContractError
from harness.gameplay.evidence import EvidenceError, EvidenceStore
from harness.gameplay.lifecycle import adopted_timeline, candidate_timeline
from harness.gameplay.contracts import canonical
from harness.gameplay.mission_ledger import LedgerError, MissionLedger
from harness.gameplay.mission_contracts import LearningPolicy, LibrarySource
from harness.gameplay.procedure_library import ProcedureLibrary
from tests import test_procedure_library as library_fixtures
from tests.test_gameplay_evidence import observation, png
from tests.test_mission_contracts import admission, claim, request, skill
from tests.test_mission_ledger import intent, known_receipt, published_receipt


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / ".runtime" / "lifecycle-tests"
        root.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bridge = self.root / "bridge"
        self.bridge.mkdir()
        self.store = EvidenceStore(self.bridge, self.root / "evidence", max_frames=128)
        self.addCleanup(self.store.close)
        self.a = admission()
        self.library = None
        self.ledger = MissionLedger(self.root / "ledger", admission=self.a, now=1000)
        self.addCleanup(self.ledger.close)
        self.ledger.activate(epoch=0, player_id=self.a.player_id, now=1000)
        self.number = 0

    def ingest(self, session, turn=None, category=None, *, in_game=None):
        self.number += 1
        value = observation(self.number, session=session)
        if category is not None:
            value.update(scene=None, category=category, in_game=False if in_game is None else in_game)
            value["boundary"]["kind"] = "menu"
        else:
            value["scene"]["turn"] = turn
        (self.bridge / value["frame"]).write_bytes(png())
        return self.store.ingest(value, received_monotonic=100, now_monotonic=100, now_timestamp_ms=1_000_000)

    def begin(self, data):
        data["epoch"] = self.ledger.snapshot(now=1000)["epoch"]
        self.ledger.begin_request(data, now=1000)
        return data["request_id"]

    def preflight(self, before):
        """Retain the distinct final capture without promoting current evidence."""
        self.number += 1
        value = self.store.observation(before)
        value["frame"] = f"frame-{before.session}-{self.number}.png"
        (self.bridge / value["frame"]).write_bytes(png())
        retained = self.store.retain_preflight(value, rule="exact_png_bytes",
            received_monotonic=100, now_monotonic=100, now_timestamp_ms=1_000_000)
        self.assertNotEqual(retained.observation_id, before.observation_id)
        return retained

    def lifecycle(self, identity, operation, before=None, phase=None, identities=None):
        return self.begin(request("lifecycle", request_id=identity, operation=operation,
            world=self.a.scenario.world, character=self.a.scenario.character,
            sources=[] if before is None else [before.observation_id],
            expected_session=None if before is None else before.session,
            expected_revision=None if before is None else before.revision,
            expected_boundary_id=None if before is None else self.store.observation(before)["boundary"]["id"],
            phase_id=phase, identity_claim_ids=identities or [], limits=dict(primitives=32, wall_seconds=120, game_seconds=1200)))

    def complete(self, identity, result, disposition="completed"):
        self.ledger.complete_request(identity, disposition, result, now=1000)

    def phase(self, root, operation, stage, *sources):
        root_sources = self.ledger.request(root)["request"]["sources"]
        launch_sources = self.ledger.request("launch")["result"]["source_ids"]
        return dict(schema="mission/11", record_type="PhaseReceipt", origin_request_id=root,
            phase_kind="lifecycle", operation=operation, stage=stage, epoch=self.ledger.snapshot(now=1000)["epoch"],
            actor_id=self.a.player_id, controller_boot_id="boot-test", operator_pause_generation=0,
            takeover_generation=0, source_ids=list(dict.fromkeys(launch_sources + root_sources + list(sources))),
            continuity=None, launch_request_id="launch", launch_id="owned-launch", grants_authority=False)

    def confirmation(self, identity, root, before, question):
        return self.begin(skill(request_id=identity, skill_kind="menu", phase_id=root,
            goal=dict(purpose="Confirm lifecycle", label="Yes", outcome="activated"),
            perception=dict(kind="confirmation", basis="player_interpretation", source_id=before.observation_id,
                            question=question), sources=[before.observation_id], expected_session=before.session,
            expected_revision=before.revision))

    def remember(self, entry):
        data = request("remember", request_id="remember-" + entry["id"], entry_type="claim", entry=entry)
        self.begin(data)
        result = CampaignMemory(self.ledger, self.store, self.library).apply(data, now=1000)
        self.complete(data["request_id"], result)

    def correct(self, entry):
        data = request("correct", request_id="correct-" + entry["id"], entry_type="claim", entry=entry,
            retired_ids=entry["supersedes"], reason="Correct visible character identity transcription")
        self.begin(data)
        result = CampaignMemory(self.ledger, self.store, self.library).apply(data, now=1000)
        self.complete(data["request_id"], result)

    def primitive(self, request_id, before, after, *, value="CONFIRM", preflight, unknown_operation=None):
        logical = "logical-" + request_id
        native = "native-" + request_id
        proposed = intent(value=value, expected_session=before.session, expected_revision=before.revision,
            expected_boundary_id=self.store.observation(before)["boundary"]["id"],
            source_before=before.observation_id, preflight_source=preflight.observation_id)
        self.ledger.prepare_primitive(request_id, logical, proposed, now=1000)
        self.ledger.published(logical, native, now=1000)
        disposition = "unknown" if unknown_operation is not None else "returned"
        receipt = dict(logical_action_id=logical, native_request_id=native, transport_disposition=disposition,
            published=True, source_after=None if unknown_operation is not None else after.observation_id,
            **{k: proposed[k] for k in ("kind", "value", "expected_session", "expected_revision", "expected_boundary_id", "source_before", "preflight_source")})
        if unknown_operation is None:
            receipt.update(known_receipt(native_id=native, logical_id=logical, proposed=proposed,
                after=self.store.observation(after), frame=self.store.observation(preflight)["frame"]))
        receipt.update(published_receipt(native_id=native, logical_id=logical, proposed=proposed, controller_boot_id="boot-test",
            dispatch_epoch=self.ledger.request(request_id)["epoch"], actor_id=self.a.player_id,
            frame=self.store.observation(preflight)["frame"]))
        self.ledger.settle_primitive(logical, disposition, receipt, now=1000)
        return logical, native

    def transition(self, root, before, after, *, terminal=None, preflight, unknown=False):
        terminal = root if terminal is None else terminal
        operation = self.ledger.request(root)["request"]["operation"]
        # The actual native playing(bool) changes session, Pauses and clears
        # pending input. No cross-world ready ACK can be returned. Retain its
        # original unknown delivery and prove the observed lifecycle separately.
        unknown = unknown or before.session != after.session
        logical, native = self.primitive(terminal, before, after, value="CONFIRM" if terminal == root else "YES",
            preflight=preflight, unknown_operation=operation if unknown else None)
        proof = dict(schema="mission/11", record_type="LifecycleTransition", operation=operation,
            origin_request_id=root, terminal_request_id=terminal, terminal_logical_id=logical, native_request_id=native,
            launch_request_id="launch", launch_id="owned-launch", before_source_id=before.observation_id,
            after_source_id=after.observation_id, origin_epoch=self.ledger.request(root)["epoch"],
            reconciled_epoch=self.ledger.snapshot(now=1000)["epoch"], actor_id=self.a.player_id,
            controller_boot_id="boot-test", operator_pause_generation=0,
            before_takeover_generation=0, after_takeover_generation=0, grants_authority=False)
        if unknown:
            self.ledger.reconcile_effect(logical, proof=proof, sources=(before.observation_id, after.observation_id),
                note=f"Observed lifecycle {operation} transition after {native}; original ACK remains unknown", now=1000)
            self.ledger.activate(epoch=self.ledger.snapshot(now=1000)["epoch"], player_id=self.a.player_id, now=1000)
        return proof

    def identity(self, identity, subject, source, epoch):
        return claim(id=identity, key=dict(subject=subject, property="identity", unit="name",
            coverage_id="visible-world-menu" if subject == "world" else "visible-character-screen"),
            value=dict(quantity=None, state=getattr(self.a.scenario, subject)),
            scope=dict(mission_id=self.a.mission_id, session=source.session, coordinate_epoch=epoch),
            observed_time=dict(revision=source.revision, turn=source.turn),
            sources=[source.observation_id], supports=[dict(sources=[source.observation_id], claims=[])])

    def adopt(self, root, before, session, turn, epoch, *, saved=None, omit=False, first_extra=False, unknown=False, pending=False, character_state=None):
        self.lifecycle(root, "create" if epoch == 0 else "load", before)
        if epoch == 0:
            self.complete(root, {}, "partial")
            character_form = self.ingest(before.session, category="NEW_CHAR_DESCRIPTION")
            self.lifecycle(root + "-commit", "create", character_form, phase=root)
            character_preflight = self.preflight(character_form)
            transition_before = self.ingest(before.session, category="YESNO")
            self.primitive(root + "-commit", character_form, transition_before, value="NEXT_TAB", preflight=character_preflight)
            self.complete(root + "-commit", {}, "partial")
            terminal = self.confirmation(root + "-yes", root, transition_before, "Are you SURE you're finished?")
        else:
            transition_before, terminal = before, root
        transition_preflight = self.preflight(transition_before)
        first = self.ingest(session, turn)
        newer = self.ingest(session, turn) if first_extra else first
        transition = self.transition(root, transition_before, newer, terminal=terminal,
            preflight=transition_preflight, unknown=unknown)
        self.complete(terminal, {})
        transition_id = root + "-transition"
        self.lifecycle(transition_id, "create" if epoch == 0 else "load", newer, phase=root)
        self.complete(transition_id, dict(lifecycle_transition=transition,
            phase=self.phase(root, transition["operation"], "awaiting_identity", transition_before.observation_id, newer.observation_id)))
        inspect_id = root + "-inspect"
        self.begin(skill(request_id=inspect_id, skill_kind="inspect", goal=dict(purpose="character_identity"),
            phase_id=root, sources=[newer.observation_id], expected_session=session, expected_revision=newer.revision))
        inspect_preflight = self.preflight(newer)
        screen = self.ingest(session, category="PLAYER_INFO", in_game=True)
        self.primitive(inspect_id, newer, screen, value="player_data", preflight=inspect_preflight)
        self.complete(inspect_id, dict(identity_screen_source_id=screen.observation_id, source_ids=[screen.observation_id]))
        checkpoint = self.ingest(session, turn)
        world_id, character_id = root + "-world", root + "-character"
        for identity, subject, source in ((world_id, "world", before), (character_id, "character", screen)):
            entry = self.identity(identity, subject, source, epoch)
            if subject == "character" and character_state is not None:
                entry["value"]["state"] = character_state
            self.remember(entry)
        final = root + "-adopt"
        self.lifecycle(final, "create" if epoch == 0 else "load", checkpoint, phase=root, identities=[world_id, character_id])
        adoption = dict(schema="mission/11", record_type="NormalSessionAdoption", origin_request_id=root,
            transition_result_request_id=transition_id, first_normal_source_id=newer.observation_id,
            world_claim_id=world_id, character_claim_id=character_id, identity_inspect_request_id=inspect_id,
            checkpoint_source_id=checkpoint.observation_id, saved_checkpoint_request_id=saved,
            scope=dict(mission_id=self.a.mission_id, session=session, coordinate_epoch=epoch), grants_authority=False)
        proposed = {} if omit else dict(normal_adoption=adoption,
            phase=self.phase(root, transition["operation"], "complete", first.observation_id, checkpoint.observation_id))
        if not pending:
            self.complete(final, proposed)
        return dict(first=first, checkpoint=checkpoint, screen=screen, adoption=adoption, result=final, proposed=proposed)

    def create(self, **changes):
        menu = self.ingest("menu-a", category="MAIN_MENU")
        self.lifecycle("launch", "launch")
        self.complete("launch", dict(native_ready=True, source_ids=[menu.observation_id], process=dict(launch_id="owned-launch")))
        return self.adopt("create", menu, "normal-a", -10, 0, **changes)

    def save(self, adopted, *, root="save", turn=20, launch=None):
        before = self.ingest(adopted["first"].session, turn)
        self.lifecycle(root, "save", before)
        endpoint = self.preflight(before)
        confirmation = self.ingest(before.session, category="QUERY_YN", in_game=True)
        self.primitive(root, before, confirmation, value="save", preflight=endpoint)
        self.complete(root, {}, "partial")
        terminal = self.confirmation(root + "-yes", root, confirmation, "Save and quit?")
        transition_preflight = self.preflight(confirmation)
        menu = self.ingest("menu-" + root, category="MAIN_MENU")
        proof = self.transition(root, confirmation, menu, terminal=terminal, preflight=transition_preflight)
        self.complete(terminal, {})
        result_id = root + "-checkpoint"
        self.lifecycle(result_id, "save", menu, phase=root)
        saved = dict(schema="mission/11", record_type="SavedCheckpoint", origin_request_id=root,
            transition_result_request_id=result_id, adoption_result_request_id=adopted["result"],
            normal_endpoint_source_id=endpoint.observation_id, menu_source_id=menu.observation_id, grants_authority=False)
        phase = self.phase(root, "save", "complete", confirmation.observation_id, menu.observation_id)
        if launch is not None:
            proof.update(launch_request_id=launch[0], launch_id=launch[1])
            phase.update(launch_request_id=launch[0], launch_id=launch[1])
        self.complete(result_id, dict(lifecycle_transition=proof, saved_checkpoint=saved, phase=phase))
        return endpoint, menu

    def chain(self):
        created = self.create()
        endpoint, menu = self.save(created)
        loaded = self.adopt("load", menu, "normal-b", endpoint.turn, 1, saved="save-checkpoint")
        last = self.ingest("normal-b", 55)
        return created, endpoint, loaded, last

    def tamper_result(self, identity, change):
        result = self.ledger.request(identity)["result"]
        change(result)
        self.ledger._db.execute("UPDATE requests SET result=? WHERE id=?", (canonical(result), identity))

    def tamper_claim(self, identity, change):
        entry = next(row["entry"] for row in self.ledger.memory_records("claim") if row["entry"]["id"] == identity)
        change(entry)
        self.ledger._db.execute("UPDATE memory SET body=? WHERE record_id=?", (canonical(entry), identity))

    def test_create_save_reload_exact_elapsed_and_coordinate_epoch(self):
        created, endpoint, loaded, last = self.chain()
        generation = self.store.authority_generation()
        timeline = adopted_timeline(self.ledger, self.store)
        self.assertEqual((timeline.elapsed_seconds, timeline.coordinate_epoch), (65, 1))
        self.assertEqual(timeline.segments, ((created["first"], endpoint), (loaded["first"], last)))
        self.assertEqual(self.store.authority_generation(), generation)
        self.assertEqual(self.ledger.request("save-checkpoint")["result"]["saved_checkpoint"]["transition_result_request_id"], "save-checkpoint")

    def test_no_normal_sources_returns_none(self):
        self.assertIsNone(adopted_timeline(self.ledger, self.store))
        self.ingest("menu", category="MAIN_MENU")
        self.assertIsNone(adopted_timeline(self.ledger, self.store))

    def test_orphan_transition_effect_checks_semantics_and_dispatch_before_any_result(self):
        menu = self.ingest("menu", category="MAIN_MENU")
        self.lifecycle("launch", "launch")
        self.complete("launch", dict(native_ready=True, source_ids=[menu.observation_id], process=dict(launch_id="owned-launch")))
        self.lifecycle("load", "load", menu)
        preflight = self.preflight(menu)
        after = self.ingest("normal", turn=10)
        logical, native = self.primitive("load", menu, after, preflight=preflight, unknown_operation="load")
        proof = dict(schema="mission/11", record_type="LifecycleTransition", operation="load", origin_request_id="load",
            terminal_request_id="load", terminal_logical_id=logical, native_request_id=native,
            launch_request_id="launch", launch_id="owned-launch", before_source_id=menu.observation_id,
            after_source_id=after.observation_id, origin_epoch=0, reconciled_epoch=1, actor_id=self.a.player_id,
            controller_boot_id="boot-test", operator_pause_generation=0, before_takeover_generation=0,
            after_takeover_generation=0, grants_authority=False)
        for change in (dict(origin_epoch=5), dict(after_takeover_generation=1), dict(actor_id="other-player"),
                       dict(launch_request_id="missing-launch"), dict(controller_boot_id="other-boot"),
                       dict(operator_pause_generation=1), dict(reconciled_epoch=2)):
            with self.subTest(change=change), self.assertRaises(ContractError):
                self.ledger.reconcile_effect(logical, proof={**proof, **change}, sources=(menu.observation_id, after.observation_id),
                    note="Contradictory orphan proof", now=1000)
            self.assertIsNone(self.ledger.primitive(logical)["effect"])
        self.ledger.reconcile_effect(logical, proof=proof, sources=(menu.observation_id, after.observation_id),
            note="Actual synthetic transition custody", now=1000)
        self.assertIsNone(self.ledger.request("load")["result"])
        self.ledger._verify(self.a)

    def test_bad_argument_types(self):
        for value in (None, {}, True):
            with self.assertRaises(ContractError): adopted_timeline(value, self.store)
            with self.assertRaises(ContractError): adopted_timeline(self.ledger, value)

    def test_missing_adoption_does_not_select_subset(self):
        self.create(omit=True)
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_missing_middle_adoption_rejects(self):
        _, _, loaded, _ = self.chain()
        endpoint, menu = self.save(loaded, root="save-second", turn=60)
        self.adopt("load-second", menu, "normal-c", endpoint.turn, 2, saved="save-second-checkpoint")
        self.tamper_result("load-adopt", lambda result: result.pop("normal_adoption"))
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_three_sessions_require_ordered_complete_proofs(self):
        _, _, loaded, _ = self.chain()
        endpoint, menu = self.save(loaded, root="save-second", turn=60)
        self.adopt("load-second", menu, "normal-c", endpoint.turn, 2, saved="save-second-checkpoint")
        self.ingest("normal-c", 70)
        timeline = adopted_timeline(self.ledger, self.store)
        self.assertEqual((timeline.elapsed_seconds, timeline.coordinate_epoch), (80, 2))

    def test_session_return_rejects(self):
        created, _, _, _ = self.chain()
        self.store.close()
        path = self.root / "evidence" / "evidence.json"
        manifest = json.loads(path.read_bytes())
        entries = manifest["entries"]
        index = next(i for i, entry in enumerate(entries)
                     if entry["reference"]["observation_id"] == created["checkpoint"].observation_id)
        entries.append(entries.pop(index))
        path.write_text(json.dumps(manifest))
        self.store = EvidenceStore(self.bridge, self.root / "evidence", max_frames=128)
        self.addCleanup(self.store.close)
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_duplicate_adoption_rejects(self):
        created = self.create()
        self.lifecycle("duplicate", "create", created["checkpoint"], phase="create",
            identities=["create-world", "create-character"])
        self.complete("duplicate", dict(normal_adoption=created["adoption"],
            phase=self.phase("create", "create", "complete", created["checkpoint"].observation_id)))
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_equal_turn_newer_anchor_rejects(self):
        self.create(first_extra=True)
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_wrong_save_endpoint_rejects(self):
        created = self.create()
        self.save(created)
        self.tamper_result("save-checkpoint", lambda result: result["saved_checkpoint"].update(normal_endpoint_source_id=created["checkpoint"].observation_id))
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_saved_endpoint_receipt_must_match_every_immutable_field(self):
        created = self.create()
        self.save(created)
        original = self.ledger.primitive("logical-save")["result"]
        changes = dict(logical_action_id="other-logical", native_request_id="other-native",
            kind="key", value="OTHER", transport_disposition="unknown", expected_session="other-session",
            expected_revision=999, expected_boundary_id="other-boundary", source_before="other-source",
            preflight_source="other-preflight")
        for key, value in changes.items():
            with self.subTest(key=key):
                receipt = dict(original, **{key: value})
                self.ledger._db.execute("UPDATE primitives SET result=? WHERE id='logical-save'", (canonical(receipt),))
                with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_save_transition_cannot_switch_the_adopted_owned_launch(self):
        created = self.create()
        launch_source = self.ledger.request("launch")["result"]["source_ids"]
        self.lifecycle("second-launch", "launch")
        self.complete("second-launch", dict(native_ready=True, source_ids=launch_source,
            process=dict(launch_id="second-owned-launch")))
        with self.assertRaises(LedgerError):
            self.save(created, launch=("second-launch", "second-owned-launch"))

    def test_corrupted_save_launch_rejects_on_projection_and_reopen(self):
        created = self.create()
        launch_source = self.ledger.request("launch")["result"]["source_ids"]
        self.lifecycle("second-launch", "launch")
        self.complete("second-launch", dict(native_ready=True, source_ids=launch_source,
            process=dict(launch_id="second-owned-launch")))
        self.save(created)
        def switch(result):
            for key in ("lifecycle_transition", "phase"):
                result[key].update(launch_request_id="second-launch", launch_id="second-owned-launch")
        self.tamper_result("save-checkpoint", switch)
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)
        with self.assertRaises(LedgerError): self.ledger._verify(self.a)

    def test_wrong_reload_turn_rejects(self):
        created = self.create()
        _, menu = self.save(created)
        self.adopt("load", menu, "normal-b", 21, 1, saved="save-checkpoint")
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_lost_and_restored_identity_bytes_remain_disputed(self):
        created = self.create()
        path = Path(created["screen"].frame_path)
        original = path.read_bytes()
        path.unlink()
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)
        path.write_bytes(original)
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_corrupt_identity_bytes_reject(self):
        created = self.create()
        path = Path(created["screen"].frame_path)
        path.chmod(0o600)
        path.write_bytes(png(b"corrupt"))
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_wrong_identity_value_scope_support_or_status_rejects(self):
        self.create()
        original = next(row["entry"] for row in self.ledger.memory_records("claim") if row["entry"]["id"] == "create-character")
        changes = (lambda c: c["value"].update(state="Other"),
            lambda c: c["scope"].update(coordinate_epoch=1), lambda c: c.update(status="disputed"),
            lambda c: c.update(status="inferred"), lambda c: c.update(sources=[], supports=[]),
            lambda c: c["scope"].update(session="menu-a"),
            lambda c: c["key"].update(coverage_id="visible-world-menu"))
        for change in changes:
            with self.subTest(change=change):
                candidate = deepcopy(original)
                change(candidate)
                self.ledger._db.execute("UPDATE memory SET body=? WHERE record_id='create-character'", (canonical(candidate),))
                with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_correction_invalidates_previous_identity(self):
        created = self.create()
        corrected = self.identity("corrected-character", "character", created["screen"], 0)
        corrected["supersedes"] = ["create-character"]
        self.ledger.append_memory("correction", "claim", corrected, now=1000)
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_conflicting_identity_assertion_rejects(self):
        created = self.create()
        conflict = self.identity("conflict", "character", created["screen"], 0)
        conflict["value"]["state"] = "Other"
        self.ledger.append_memory("conflict", "claim", conflict, now=1000)
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_wrong_inspect_phase_or_endpoint_rejects(self):
        created = self.create()
        self.tamper_result("create-inspect", lambda r: r.update(identity_screen_source_id=created["checkpoint"].observation_id))
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_wrong_inspection_phase_rejects(self):
        self.create()
        data = self.ledger.request("create-inspect")["request"]
        data["phase_id"] = "launch"
        self.ledger._db.execute("UPDATE requests SET payload=? WHERE id='create-inspect'", (canonical(data),))
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_wrong_inspection_purpose_rejects(self):
        self.create()
        data = self.ledger.request("create-inspect")["request"]
        data["goal"]["purpose"] = "inventory"
        self.ledger._db.execute("UPDATE requests SET payload=? WHERE id='create-inspect'", (canonical(data),))
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_wrong_phase_audit_schema_rejects(self):
        self.create()
        self.tamper_result("create-transition", lambda result: result["phase"].update(unrecognized=True))
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_source_free_annotation_cannot_manufacture_transition(self):
        self.create()
        self.tamper_result("create-transition", lambda r: r["lifecycle_transition"].update(terminal_logical_id="invented"))
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_transition_wrong_source_or_phase_rejects(self):
        created = self.create()
        self.tamper_result("create-transition", lambda r: r["lifecycle_transition"].update(before_source_id=created["checkpoint"].observation_id))
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_identity_checkpoint_chronology_rejects(self):
        created = self.create()
        self.tamper_result("create-adopt", lambda r: r["normal_adoption"].update(checkpoint_source_id=created["first"].observation_id))
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_unknown_ack_stays_unknown_with_independent_retained_effect(self):
        self.create(unknown=True)
        primitive = self.ledger.primitive("logical-create-yes")
        self.assertEqual(primitive["state"], "unknown")
        self.assertEqual(self.ledger.request("create-transition")["result"]["lifecycle_transition"]["reconciled_epoch"], 1)
        self.assertEqual(adopted_timeline(self.ledger, self.store).elapsed_seconds, 0)
        self.assertEqual(self.ledger.primitive("logical-create-yes")["state"], "unknown")
        self.ledger._db.execute("UPDATE primitives SET effect=NULL WHERE id='logical-create-yes'")
        with self.assertRaises(EvidenceError): adopted_timeline(self.ledger, self.store)

    def test_reopened_ledger_and_sources_preserve_adoption_without_authority(self):
        self.chain()
        expected = adopted_timeline(self.ledger, self.store)
        self.ledger.close()
        self.store.close()
        self.ledger = MissionLedger(self.root / "ledger", admission=self.a, now=1001)
        self.addCleanup(self.ledger.close)
        self.store = EvidenceStore(self.bridge, self.root / "evidence", max_frames=128)
        self.addCleanup(self.store.close)
        self.assertEqual(adopted_timeline(self.ledger, self.store), expected)
        self.assertFalse(self.ledger.snapshot(now=1001)["grants_authority"])

    def test_candidate_matches_actual_commit_without_writing(self):
        created = self.create(pending=True)
        before = self.ledger.request(created["result"])
        generation = self.store.authority_generation()
        proposed = deepcopy(created["proposed"])
        timeline = candidate_timeline(self.ledger, self.store, request_id=created["result"], result=proposed)
        self.assertEqual(self.ledger.request(created["result"]), before)
        self.assertEqual(proposed, created["proposed"])
        self.assertEqual(self.store.authority_generation(), generation)
        self.complete(created["result"], proposed)
        self.assertEqual(adopted_timeline(self.ledger, self.store), timeline)

    def admit_library(self):
        archive = library_fixtures.ProcedureLibraryTests()
        archive.root = self.root
        archive.environment = library_fixtures.procedure()["environment"]
        _, _, record, pin = archive.archive()
        self.library = self.enterContext(ProcedureLibrary(self.root, [pin], current_mission_id=self.a.mission_id))
        self.ledger.close()
        self.a = replace(self.a, learning=LearningPolicy(archive.environment, (LibrarySource(**pin),)))
        self.ledger = MissionLedger(self.root / "learning-ledger", admission=self.a, now=1000)
        self.addCleanup(self.ledger.close)
        self.ledger.activate(epoch=0, player_id=self.a.player_id, now=1000)
        return record

    def test_learning_library_supports_candidate_and_committed_timeline(self):
        record = self.admit_library()
        created = self.create(pending=True, unknown=True)
        before = self.ledger.request(created["result"])
        generation = self.store.authority_generation()
        timeline = candidate_timeline(self.ledger, self.store,
            request_id=created["result"], result=created["proposed"])
        self.assertEqual((timeline.elapsed_seconds, timeline.coordinate_epoch), (0, 0))
        self.assertEqual(self.ledger.request(created["result"]), before)
        self.assertEqual(self.store.authority_generation(), generation)
        invalid = deepcopy(created["proposed"])
        invalid["normal_adoption"]["checkpoint_source_id"] = "missing-source"
        with self.assertRaises(EvidenceError):
            candidate_timeline(self.ledger, self.store, request_id=created["result"], result=invalid)
        self.complete(created["result"], created["proposed"])
        self.assertEqual(adopted_timeline(self.ledger, self.store), timeline)
        packet = CampaignMemory(self.ledger, self.store, self.library).context(
            created["adoption"]["scope"], "water", max_bytes=32768,
            now_monotonic=100, now_timestamp_ms=1_000_000)
        self.assertEqual(packet["procedures"], [record])
        self.assertEqual(self.ledger.primitive("logical-create-yes")["state"], "unknown")
        self.ledger._db.execute("UPDATE primitives SET effect=NULL WHERE id='logical-create-yes'")
        with self.assertRaises(EvidenceError):
            adopted_timeline(self.ledger, self.store)

    def test_learning_memory_still_requires_library_and_matching_environment(self):
        self.admit_library()
        with self.assertRaisesRegex(ContractError, "requires its admitted library and environment"):
            CampaignMemory(self.ledger, self.store)
        policy = replace(self.a.learning, environment=dict(self.a.learning.environment, configuration="Other setup"))
        ledger = self.enterContext(MissionLedger(self.root / "other-environment",
            admission=replace(self.a, learning=policy), now=1000))
        with self.assertRaisesRegex(ContractError, "crosses its admitted environment"):
            CampaignMemory(ledger, self.store, self.library)

    def test_candidate_invalid_source_rejects_before_immutable_commit(self):
        created = self.create(pending=True)
        before = self.ledger.request(created["result"])
        proposed = deepcopy(created["proposed"])
        proposed["normal_adoption"]["checkpoint_source_id"] = "missing-source"
        with self.assertRaises(EvidenceError):
            candidate_timeline(self.ledger, self.store, request_id=created["result"], result=proposed)
        self.assertEqual(self.ledger.request(created["result"]), before)
        self.assertIsNone(before["result"])

    def test_candidate_phase_cannot_self_validate_actor_or_operator_mark(self):
        created = self.create(pending=True)
        before = self.ledger.request(created["result"])
        for field, value in (("actor_id", "other-actor"), ("operator_pause_generation", 42)):
            with self.subTest(field=field):
                proposed = deepcopy(created["proposed"])
                proposed["phase"][field] = value
                with self.assertRaises(EvidenceError):
                    candidate_timeline(self.ledger, self.store, request_id=created["result"], result=proposed)
                self.assertEqual(self.ledger.request(created["result"]), before)

    def test_candidate_uses_the_actual_requests_identity_selection(self):
        created = self.create(pending=True)
        self.complete(created["result"], {}, disposition="partial")
        self.lifecycle("unselected-adoption", "create", created["checkpoint"], phase="create")
        with self.assertRaises(EvidenceError):
            candidate_timeline(self.ledger, self.store, request_id="unselected-adoption", result=created["proposed"])

    def test_missing_inspection_input_rejects_before_adoption_commit(self):
        created = self.create(pending=True)
        self.ledger._db.execute("DELETE FROM primitives WHERE request_id='create-inspect'")
        with self.assertRaises(LedgerError): self.complete(created["result"], created["proposed"])
        with self.assertRaises(EvidenceError):
            candidate_timeline(self.ledger, self.store, request_id=created["result"], result=created["proposed"])

    def test_returned_identity_inspection_after_source_rejects_on_reopen(self):
        self.create()
        receipt = self.ledger.primitive("logical-create-inspect")["result"]
        receipt["source_after"] = "unrelated-source"
        self.ledger._db.execute("UPDATE primitives SET result=? WHERE id='logical-create-inspect'", (canonical(receipt),))
        with self.assertRaises(LedgerError): self.ledger._verify(self.a)

    def test_candidate_rejects_actor_forged_in_both_transition_and_phase(self):
        created = self.create(pending=True)
        self.tamper_result("create-transition", lambda result: (
            result["lifecycle_transition"].update(actor_id="other-actor"), result["phase"].update(actor_id="other-actor")))
        proposed = deepcopy(created["proposed"])
        proposed["phase"]["actor_id"] = "other-actor"
        with self.assertRaises(EvidenceError):
            candidate_timeline(self.ledger, self.store, request_id=created["result"], result=proposed)

    def test_cross_world_ready_ack_is_rejected_instead_of_manufacturing_delivery(self):
        menu = self.ingest("menu-a", category="MAIN_MENU")
        self.lifecycle("launch", "launch")
        self.complete("launch", dict(native_ready=True, source_ids=[menu.observation_id],
            process=dict(launch_id="owned-launch")))
        self.lifecycle("load", "load", menu)
        preflight = self.preflight(menu)
        after = self.ingest("normal-a", turn=10)
        with self.assertRaisesRegex(LedgerError, "preflight session/revision"):
            self.primitive("load", menu, after, preflight=preflight)
        primitive, = self.ledger.primitive_records()
        self.assertEqual(primitive["state"], "published")
        self.assertIsNone(primitive["result"])

    def test_candidate_cannot_replace_settled_request(self):
        created = self.create()
        before = self.ledger.request(created["result"])
        with self.assertRaises(EvidenceError):
            candidate_timeline(self.ledger, self.store, request_id=created["result"], result=created["proposed"])
        self.assertEqual(self.ledger.request(created["result"]), before)

    def test_candidate_rejects_nonadoption_or_bad_argument_types(self):
        created = self.create(pending=True)
        for request_id, result in ((None, created["proposed"]), (created["result"], []), (True, {})):
            with self.subTest(request_id=request_id, result=result), self.assertRaises(ContractError):
                candidate_timeline(self.ledger, self.store, request_id=request_id, result=result)
        for identity, result in (("missing", created["proposed"]), (created["result"], {})):
            with self.subTest(identity=identity), self.assertRaises(EvidenceError):
                candidate_timeline(self.ledger, self.store, request_id=identity, result=result)

    def test_candidate_explicit_correction_can_establish_identity(self):
        created = self.create(pending=True, character_state="Typo")
        with self.assertRaises(EvidenceError):
            candidate_timeline(self.ledger, self.store, request_id=created["result"], result=created["proposed"])
        corrected = self.identity("corrected-character", "character", created["screen"], 0)
        corrected["supersedes"] = ["create-character"]
        self.correct(corrected)
        self.complete(created["result"], {}, "partial")
        new_result = "corrected-adoption"
        self.lifecycle(new_result, "create", created["checkpoint"], phase="create",
            identities=["create-world", "corrected-character"])
        proposed = deepcopy(created["proposed"])
        proposed["normal_adoption"]["character_claim_id"] = "corrected-character"
        expected = candidate_timeline(self.ledger, self.store, request_id=new_result, result=proposed)
        self.complete(new_result, proposed)
        self.assertEqual(adopted_timeline(self.ledger, self.store), expected)

    def test_candidate_old_selected_identity_is_invalid_after_explicit_correction(self):
        created = self.create(pending=True)
        corrected = self.identity("corrected-character", "character", created["screen"], 0)
        corrected["supersedes"] = ["create-character"]
        self.correct(corrected)
        with self.assertRaises(EvidenceError):
            candidate_timeline(self.ledger, self.store, request_id=created["result"], result=created["proposed"])

    def test_candidate_incomparable_identity_frontier_rejects(self):
        created = self.create(pending=True)
        second = self.identity("incomparable-character", "character", created["checkpoint"], 0)
        # Native turn is present on only one of these actual source boundaries.
        self.remember(second)
        with self.assertRaises(EvidenceError):
            candidate_timeline(self.ledger, self.store, request_id=created["result"], result=created["proposed"])


if __name__ == "__main__":
    unittest.main()
