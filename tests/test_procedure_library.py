"""Sealed synthetic archives: integrity/closure, never gameplay acceptance."""
import fcntl
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import pytest

from harness.gameplay.contracts import ContractError, EvidenceRef
from harness.gameplay.evidence import EvidenceStore, MAX_FRAMES, _identity
from harness.gameplay.mission_contracts import LearningPolicy
from harness.gameplay.contracts import canonical
from harness.gameplay.procedure_library import ProcedureLibrary
from harness.gameplay.procedures import project_procedures
from tests.test_mission_ledger import intent, known_receipt
from tests.test_gameplay_evidence import observation, png
from tests.test_procedures import procedure, successor
from tests.test_mission_contracts import admission


def digest(data):
    return hashlib.sha256(data).hexdigest()


class ProcedureLibraryTests(unittest.TestCase):
    def setUp(self):
        owned = Path(__file__).resolve().parents[1] / ".runtime" / "procedure-library-tests"
        owned.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=owned)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.environment = procedure()["environment"]

    def archive(self, mission="mission-a", *, records=None, dependencies=(), phase="stopped"):
        directory = self.root / ".runtime" / "missions" / mission
        frames = directory / "evidence" / "frames"
        frames.mkdir(parents=True)
        for lock in (directory / "mission.lock", frames.parent / "evidence.lock"):
            lock.touch()
        native = observation(session=mission)
        identity = _identity(native)
        frame = frames / (identity + ".png")
        frame.write_bytes(png())
        reference = EvidenceRef(identity, native["session"], native["revision"], native["timestamp_ms"],
            100.0, native["scene"]["turn"], str(frame), digest(png()), "normal_play").to_dict()
        index = {"store_version": 5, "session": mission, "retired_sessions": [], "blocked": [],
                 "disputed": [], "entries": [{"reference": reference, "observation": native,
                                               "initial_lag_seconds": 0.0, "retention": "current"}]}
        (frames.parent / "evidence.json").write_text(canonical(index))
        row = procedure(mission_id=mission, support=[{"mission_id": mission, "request_ids": ["request-1"],
            "source_ids": [identity], "interpretation": "Scoped synthetic interpretation"}])
        learning = {"environment": self.environment, "library_sources": list(dependencies), "reflector_id": None,
            "reflection_limits": {"jobs": 8, "pending": 2, "requests_per_job": 16, "sources_per_job": 8,
                "context_bytes": 65536, "result_bytes": 32768, "job_seconds": 180, "total_seconds": 3600}}
        db = sqlite3.connect(directory / "mission.sqlite3")
        with db:
            db.execute("PRAGMA user_version=12")
            db.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
            db.execute("CREATE TABLE requests(id TEXT PRIMARY KEY,payload TEXT,digest TEXT,state TEXT,result TEXT)")
            db.execute("CREATE TABLE primitives(id TEXT PRIMARY KEY,request_id TEXT,intent TEXT,native_id TEXT,state TEXT,result TEXT,effect TEXT)")
            db.execute("CREATE TABLE memory(sequence INTEGER PRIMARY KEY,event_id TEXT UNIQUE,entry_type TEXT,record_id TEXT,body TEXT)")
            db.execute("CREATE TABLE reflection_jobs(state TEXT NOT NULL)")
            db.execute("CREATE TABLE reflection_commands(id TEXT PRIMARY KEY)")
            db.execute("INSERT INTO metadata VALUES ('admission',?)", (canonical(admission(
                mission_id=mission, learning=LearningPolicy.from_dict(learning)).to_dict()),))
            db.execute("INSERT INTO metadata VALUES ('state',?)", (canonical({"phase": phase}),))
            payload = canonical({"schema": "mission/11", "kind": "observe", "request_id": "request-1",
                                 "mission_id": mission, "epoch": 0})
            db.execute("INSERT INTO requests VALUES (?,?,?,?,?)", ("request-1", payload, digest(payload.encode()),
                "completed", canonical({"source_ids": [identity], "grants_authority": False})))
            for i, record in enumerate([row] if records is None else records):
                db.execute("INSERT INTO memory VALUES (?,?,?,?,?)", (i + 1, f"event-{i}", "procedure",
                    record["id"], canonical(record)))
        db.close()
        return directory, identity, row, self.pin(mission)

    def pin(self, mission):
        directory = self.root / ".runtime" / "missions" / mission
        return {"mission_id": mission, "ledger_sha256": digest((directory / "mission.sqlite3").read_bytes()),
                "index_sha256": digest((directory / "evidence" / "evidence.json").read_bytes())}

    def edit_db(self, directory, sql, parameters=()):
        db = sqlite3.connect(directory / "mission.sqlite3")
        with db:
            db.execute(sql, parameters)
        db.close()
        return self.pin(directory.name)

    def edit_index(self, directory, mutate):
        path = directory / "evidence" / "evidence.json"
        data = json.loads(path.read_bytes())
        mutate(data)
        path.write_text(canonical(data))
        return self.pin(directory.name)

    def library(self, *pins):
        library = ProcedureLibrary(self.root, pins, current_mission_id="current")
        self.addCleanup(library.close)
        return library

    def skill_request(self, directory, identity):
        payload = canonical({"schema": "mission/11", "kind": "skill", "request_id": "request-1",
            "mission_id": directory.name, "epoch": 0, "skill_kind": "inspect", "procedure": None, "goal": {"purpose": "inventory"},
            "sources": [identity], "expected_session": directory.name, "expected_revision": 1,
            "expected_boundary_id": "boundary-1", "limits": {"primitives": 1, "wall_seconds": 60, "game_seconds": 60},
            "work_id": None, "phase_id": None, "perception": None})
        return self.edit_db(directory, "UPDATE requests SET payload=?,digest=?,result=?",
            (payload, digest(payload.encode()), canonical({"source_ids": []})))

    def test_valid_sealed_library_exports_originals_defensively_without_writes(self):
        directory, identity, record, pin = self.archive()
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        library = self.library(pin)
        self.assertEqual(library.records(), (record,))
        self.assertEqual(project_procedures(library.records()), {record["procedure_id"]: record})
        request = library.request("mission-a", "request-1")
        self.assertEqual(set(request), {"request", "state", "result"})
        self.assertEqual(request["state"], "completed")
        metadata, data = library.source("mission-a", identity)
        self.assertEqual(data, png())
        self.assertEqual(metadata["reference"]["frame_sha256"], digest(data))
        self.assertFalse(metadata["grants_authority"])
        self.assertEqual(metadata["disposition"], "retained")
        request["result"]["source_ids"].clear()
        metadata["observation"]["scene"]["turn"] = 9999
        library.records()[0]["support"].clear()
        self.assertEqual(library.records(), (record,))
        self.assertEqual(library.request("mission-a", "request-1")["result"]["source_ids"], [identity])
        self.assertEqual(library.source("mission-a", identity)[0]["observation"]["scene"]["turn"], 4)
        library.close()
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        with self.assertRaises(ContractError):
            library.records()

    def test_truncated_current_admission_refuses_even_with_matching_pin(self):
        directory, _, _, _ = self.archive()
        pin = self.edit_db(directory, "UPDATE metadata SET value=? WHERE key='admission'",
            (canonical({"schema": "mission/11", "record_type": "MissionAdmission", "mission_id": directory.name,
                        "learning": None}),))
        with self.assertRaises(ContractError):
            self.library(pin)

    @pytest.mark.assurance_advice
    def test_closed_campaign_outcomes_preserve_procedure_data_without_authority(self):
        for phase in ("completed", "failed", "stopped", "paused"):
            with self.subTest(phase=phase):
                mission = "mission-" + phase
                directory, identity, record, pin = self.archive(mission, phase=phase)
                before = {p.relative_to(directory): p.read_bytes() for p in directory.rglob("*") if p.is_file()}
                with self.library(pin) as library:
                    self.assertEqual(library.records(), (record,))
                    self.assertEqual(library.validate_episode(record["support"][0]), ((mission, identity),))
                    request = library.request(mission, "request-1")
                    self.assertEqual(request["state"], "completed")
                    self.assertEqual(request["result"], {"source_ids": [identity], "grants_authority": False})
                    metadata, frame = library.source(mission, identity)
                    self.assertEqual(frame, png())
                    self.assertEqual(metadata["disposition"], "retained")
                    self.assertFalse(metadata["grants_authority"])
                self.assertEqual(self.pin(mission), pin)
                self.assertEqual(before,
                    {p.relative_to(directory): p.read_bytes() for p in directory.rglob("*") if p.is_file()})

    def test_stopped_archive_retains_revoked_support_and_menu_without_restoring_authority(self):
        directory, identity, record, _ = self.archive()
        bridge = self.root / "bridge"
        bridge.mkdir()
        normal = observation(session=directory.name)
        menu = observation(2, session=directory.name)
        menu.update(category="UILIST", scene=None, ui={"purpose": "UILIST", "title": "Alarm",
            "rows": [{"id": "rendered-1", "text": "8 hours", "enabled": True, "hotkey": "8"}],
            "selected": "rendered-1", "filter": None, "count": None, "coverage": "rendered_rows_only"})
        menu["boundary"]["kind"] = "menu"
        originals = {}
        # Use the production writer's ordinary stale-boundary revocation. Neither
        # lost current authority nor the stopped ledger disputes retained history.
        with EvidenceStore(bridge, directory / "evidence") as store:
            for value in (normal, menu):
                (bridge / value["frame"]).write_bytes(png())
                reference = store.ingest(value, received_monotonic=100.0,
                    now_monotonic=100.0, now_timestamp_ms=1_000_000)
                with self.assertRaises(ContractError):
                    store.current_boundary(now_monotonic=104.0, now_timestamp_ms=1_004_000)
                self.assertEqual(store.source_status(reference), "retained")
                originals[reference.observation_id] = store.export_source(reference.observation_id)
        index_path = directory / "evidence" / "evidence.json"
        index = json.loads(index_path.read_bytes())
        self.assertEqual(index["blocked"], [identity, _identity(menu)])
        self.assertEqual(index["disputed"], [])
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with self.library(self.pin(directory.name)) as library:
            self.assertEqual(library.records(), (record,))
            self.assertEqual(library.validate_episode(record["support"][0]), ((directory.name, identity),))
            for source_id, original in originals.items():
                self.assertEqual(library.source(directory.name, source_id), original)
                self.assertEqual(original[0]["disposition"], "retained")
                self.assertFalse(original[0]["grants_authority"])
        with EvidenceStore(bridge, directory / "evidence") as store:
            with self.assertRaises(ContractError):
                store.current_boundary(now_monotonic=100.0, now_timestamp_ms=1_000_000)
            for value in (normal, menu):
                with self.assertRaisesRegex(ContractError, "cannot regain current authority"):
                    store.ingest(value, received_monotonic=100.0,
                        now_monotonic=100.0, now_timestamp_ms=1_000_000)
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_blocked_ids_must_be_bounded_unique_retained_sha256_identities(self):
        directory, identity, _, _ = self.archive()
        malformed = (None, {}, identity, True, [None], [1], [{}], [True],
                     ["A" * 64], ["0" * 63], ["0" * 64 + "\n"], ["foreign"],
                     ["0" * 64], [identity, identity])
        for blocked in malformed:
            pin = self.edit_index(directory, lambda index: index.update(blocked=blocked))
            before = {p.relative_to(directory): p.read_bytes() for p in directory.rglob("*") if p.is_file()}
            with self.subTest(blocked=blocked), self.assertRaises(ContractError):
                self.library(pin)
            self.assertEqual(before,
                {p.relative_to(directory): p.read_bytes() for p in directory.rglob("*") if p.is_file()})
        oversized = [f"{number:064x}" for number in range(MAX_FRAMES + 1)]
        pin = self.edit_index(directory, lambda index: index.update(blocked=oversized))
        with self.assertRaisesRegex(ContractError, "Unsupported or unavailable historical evidence index"):
            self.library(pin)

    def test_revoked_sources_do_not_bypass_disputes_integrity_or_support_linkage(self):
        directory, identity, _, _ = self.archive()
        pin = self.edit_index(directory, lambda index: index.update(blocked=[identity], disputed=[identity]))
        with self.assertRaises(ContractError):
            self.library(pin)
        self.edit_index(directory, lambda index: index.update(disputed=[]))
        pin = self.edit_db(directory, "UPDATE requests SET result=?", (canonical({"source_ids": []}),))
        with self.assertRaisesRegex(ContractError, "unrelated to its episode requests"):
            self.library(pin)
        self.edit_db(directory, "UPDATE requests SET result=?", (canonical({"source_ids": [identity]}),))
        frame = directory / "evidence" / "frames" / (identity + ".png")
        frame.write_bytes(png() + b"changed")
        with self.assertRaisesRegex(ContractError, "pinned hash differs"):
            self.library(self.pin(directory.name))

    def test_empty_sources_and_exact_bounded_unique_pins(self):
        self.assertEqual(self.library().records(), ())
        _, _, _, pin = self.archive()
        for sources in ([pin] * 2, [pin] * 9, [{**pin, "path": "/tmp/foreign"}],
                        [{**pin, "ledger_sha256": "A" * 64}], [{**pin, "mission_id": "../escape"}],
                        [{**pin, "mission_id": "current"}], [{**pin, "mission_id": "bad\n"}]):
            with self.subTest(sources=sources), self.assertRaises(ContractError):
                self.library(*sources)

    def test_terminal_library_rejects_still_open_reflective_work(self):
        directory, _, _, _ = self.archive()
        for state in ("offered", "claimed", "invented"):
            pin = self.edit_db(directory, "INSERT INTO reflection_jobs VALUES (?)", (state,))
            with self.subTest(state=state), self.assertRaisesRegex(ContractError, "reflection admission"):
                self.library(pin)
            self.edit_db(directory, "DELETE FROM reflection_jobs")

    def test_hash_schema_versions_and_nonterminal_closure_refuse(self):
        directory, _, _, original = self.archive()
        with self.assertRaises(ContractError):
            self.library({**original, "ledger_sha256": "0" * 64})
        with self.assertRaises(ContractError):
            self.library({**original, "index_sha256": "0" * 64})
        for sql in ("PRAGMA user_version=10", "PRAGMA user_version=11",
                    "UPDATE metadata SET value='{\"phase\":\"active\"}' WHERE key='state'",
                    "UPDATE metadata SET value='{\"phase\":\"admitted\"}' WHERE key='state'",
                    "UPDATE metadata SET value='{\"phase\":\"handoff\"}' WHERE key='state'",
                    "UPDATE requests SET state='running'", "UPDATE requests SET result=NULL",
                    "UPDATE requests SET digest='bad'", "UPDATE memory SET record_id='foreign'"):
            data = (directory / "mission.sqlite3").read_bytes()
            pin = self.edit_db(directory, sql)
            with self.subTest(sql=sql), self.assertRaises(ContractError):
                self.library(pin)
            (directory / "mission.sqlite3").write_bytes(data)
        for field, value in (("store_version", 3), ("store_version", 4), ("blocked", ["0" * 64]), ("disputed", ["0" * 64])):
            path = directory / "evidence" / "evidence.json"
            before = path.read_bytes()
            pin = self.edit_index(directory, lambda index: index.update({field: value}))
            with self.subTest(field=field), self.assertRaises(ContractError):
                self.library(pin)
            path.write_bytes(before)

    def test_existing_writer_locks_refuse_and_reader_releases_all_locks(self):
        directory, _, _, pin = self.archive()
        for path in (directory / "mission.lock", directory / "evidence" / "evidence.lock"):
            with path.open("rb") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(ContractError):
                    self.library(pin)
            library = self.library(pin)
            with path.open("rb") as lock:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                library.close()
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_symlink_ancestor_directory_lock_index_database_and_frame_refuse(self):
        directory, identity, _, pin = self.archive()
        paths = [self.root / ".runtime", directory, directory / "mission.lock", directory / "mission.sqlite3",
                 directory / "evidence", directory / "evidence" / "evidence.json",
                 directory / "evidence" / "frames", directory / "evidence" / "frames" / (identity + ".png")]
        for path in paths:
            saved = path.with_name(path.name + "-original")
            path.rename(saved)
            path.symlink_to(saved, target_is_directory=saved.is_dir())
            try:
                with self.subTest(path=path), self.assertRaises(ContractError):
                    self.library(pin)
            finally:
                path.unlink()
                saved.rename(path)

    def test_sqlite_sidecars_and_corrupt_database_refuse_without_mutation(self):
        directory, _, _, pin = self.archive()
        for suffix in ("-wal", "-shm", "-journal"):
            sidecar = directory / ("mission.sqlite3" + suffix)
            sidecar.touch()
            with self.subTest(suffix=suffix), self.assertRaises(ContractError):
                self.library(pin)
            sidecar.unlink()
        (directory / "mission.sqlite3").write_bytes(b"not sqlite")
        with self.assertRaises(ContractError):
            self.library(self.pin("mission-a"))

    def test_missing_changed_and_metadata_conflicting_sources_refuse(self):
        directory, identity, _, pin = self.archive()
        frame = directory / "evidence" / "frames" / (identity + ".png")
        frame.write_bytes(png() + b"changed")
        with self.assertRaises(ContractError):
            self.library(pin)
        frame.unlink()
        with self.assertRaises(ContractError):
            self.library(pin)
        frame.write_bytes(png())
        for field, value in (("frame_path", "/tmp/foreign.png"), ("revision", 1000), ("observation_id", "0" * 64)):
            path = directory / "evidence" / "evidence.json"
            before = path.read_bytes()
            changed = self.edit_index(directory, lambda data: data["entries"][0]["reference"].update({field: value}))
            with self.subTest(field=field), self.assertRaises(ContractError):
                self.library(changed)
            path.write_bytes(before)
        library = self.library(pin)
        frame.write_bytes(png() + b"changed-after-open")
        with self.assertRaises(ContractError):
            library.source("mission-a", identity)

    def test_episode_source_must_link_to_named_request_not_arbitrary_frame_or_prose(self):
        directory, identity, record, _ = self.archive()
        for result in ({"source_ids": []}, {"reason": identity}, {"source_ids": ["unrelated"]}):
            pin = self.edit_db(directory, "UPDATE requests SET result=?", (canonical(result),))
            with self.subTest(result=result), self.assertRaises(ContractError):
                self.library(pin)
        self.skill_request(directory, identity)
        # Distinct second source occurs only in the actual primitive receipt.
        index = json.loads((directory / "evidence" / "evidence.json").read_bytes())
        second = observation(2, session="mission-a")
        second_id = _identity(second)
        reference = dict(index["entries"][0]["reference"])
        reference.update(observation_id=second_id, revision=2,
            frame_path=str(directory / "evidence" / "frames" / (second_id + ".png")))
        index["entries"].append({"reference": reference, "observation": second, "initial_lag_seconds": 0.0, "retention": "terminal"})
        (directory / "evidence" / "evidence.json").write_text(canonical(index))
        (directory / "evidence" / "frames" / (second_id + ".png")).write_bytes(png())
        record["support"][0]["source_ids"] = [second_id]
        self.edit_db(directory, "UPDATE memory SET body=?", (canonical(record),))
        proposed = intent(source_before=identity, preflight_source=identity, expected_session="mission-a", expected_revision=1)
        receipt = known_receipt(proposed=proposed, after=second, source_after=second_id)
        pin = self.edit_db(directory, "INSERT INTO primitives VALUES (?,?,?,?,?,?,?)", ("logical-1", "request-1",
            canonical(proposed), "native-uuid-1", "returned", canonical(receipt), None))
        self.assertEqual(self.library(pin).records(), (record,))

    def test_unknown_primitive_needs_settled_effect_and_live_primitive_refuses(self):
        directory, identity, _, _ = self.archive()
        self.skill_request(directory, identity)
        for state, effect in (("prepared", None), ("published", None), ("unknown", None), ("unknown", "{}")):
            pin = self.edit_db(directory, "INSERT OR REPLACE INTO primitives VALUES (?,?,?,?,?,?,?)",
                ("p-1", "request-1", canonical(intent(source_before=identity, preflight_source=identity)), None,
                 state, canonical({"source_after": identity}), effect))
            with self.subTest(state=state, effect=effect), self.assertRaises(ContractError):
                self.library(pin)

    def known_archive(self, *, source_after=True, disposition="returned"):
        directory, before_id, record, _ = self.archive()
        self.skill_request(directory, before_id)
        after = observation(2, session=directory.name)
        after_id = _identity(after)
        path = directory / "evidence" / "evidence.json"
        index = json.loads(path.read_bytes())
        reference = dict(index["entries"][0]["reference"], observation_id=after_id, revision=2,
            frame_path=str(directory / "evidence" / "frames" / (after_id + ".png")))
        index["entries"].append({"reference": reference, "observation": after,
                                 "initial_lag_seconds": 0.0, "retention": "terminal"})
        path.write_text(canonical(index))
        (directory / "evidence" / "frames" / (after_id + ".png")).write_bytes(png())
        proposed = intent(source_before=before_id, preflight_source=before_id,
                          expected_session=directory.name, expected_revision=1)
        receipt = known_receipt(proposed=proposed, after=after, disposition=disposition,
            source_after=after_id if source_after else None,
            evidence_loss="After retention failed" if not source_after and disposition == "returned" else None)
        pin = self.edit_db(directory, "INSERT INTO primitives VALUES (?,?,?,?,?,?,?)", ("logical-1", "request-1",
            canonical(proposed), "native-uuid-1", disposition, canonical(receipt), None))
        return directory, before_id, after_id, receipt, record, pin

    def test_known_receipt_cross_checks_preflight_and_after_capture_not_transport_metadata(self):
        directory, before_id, after_id, receipt, _, pin = self.known_archive()
        library = self.library(pin)
        self.assertFalse(library.source("mission-a", after_id)[0]["grants_authority"])
        library.close()
        # Archive was first retained under a spectator request with a different
        # transport result; those three fields do not identify the capture.
        pin = self.edit_index(directory, lambda data: data["entries"][1]["observation"].update(
            id="spectator", status="rejected", error="spectator diagnostic"))
        self.library(pin).close()
        mutations = [lambda r: r["native_ack"].update(id="wrong"),
            lambda r: r["native_ack"].update(frame="frame-mission-a-99.png"),
            lambda r: r["native_ack"].update(timestamp_ms=999),
            lambda r: r["native_ack"].update(takeover_generation=1),
            lambda r: r.update(source_after=before_id),
            lambda r: r.update(source_after="missing"),
            lambda r: r.update(source_before="wrong"),
            lambda r: r.update(native_request_json=canonical(
                json.loads(r["native_request_json"]) | dict(frame="frame-mission-a-99.png"))),
            lambda r: r.update(native_request_json=canonical(
                json.loads(r["native_request_json"]) | dict(takeover_generation=1)))]
        for mutate in mutations:
            changed = deepcopy(receipt)
            mutate(changed)
            pin = self.edit_db(directory, "UPDATE primitives SET result=?", (canonical(changed),))
            with self.subTest(changed=changed), self.assertRaises(ContractError):
                self.library(pin)

    def test_known_delivery_without_after_remains_advisory_history_with_explicit_loss(self):
        directory, before_id, _, receipt, record, pin = self.known_archive(source_after=False)
        library = self.library(pin)
        self.assertEqual(library.records(), (record,))
        self.assertFalse(library.source("mission-a", before_id)[0]["grants_authority"])
        library.close()
        changed = receipt | dict(evidence_loss=None)
        pin = self.edit_db(directory, "UPDATE primitives SET result=?", (canonical(changed),))
        with self.assertRaises(ContractError):
            self.library(pin)

    def test_rejected_hard_fault_without_capture_preserves_delivery_without_authority(self):
        directory, _, _, receipt, _, _ = self.known_archive(source_after=False, disposition="rejected")
        receipt["native_ack"].update(session="changed", revision=0, paused=True, pause_origin="fault",
            frame_ok=False, frame="", error="Hard fault")
        receipt["native_ack"]["boundary"].update(kind="unsupported", input_receiver=False)
        pin = self.edit_db(directory, "UPDATE primitives SET result=?", (canonical(receipt),))
        self.assertEqual(self.library(pin).request("mission-a", "request-1")["state"], "completed")

    def test_unknown_ack_with_exact_settled_original_effect_stays_unknown(self):
        directory, identity, record, _ = self.archive()
        # This is a typed retained proof fixture, not native lifecycle acceptance.
        index = json.loads((directory / "evidence" / "evidence.json").read_bytes())
        after = observation(2, session="mission-a")
        after_id = _identity(after)
        reference = dict(index["entries"][0]["reference"])
        reference.update(observation_id=after_id, revision=2,
            frame_path=str(directory / "evidence" / "frames" / (after_id + ".png")))
        index["entries"].append({"reference": reference, "observation": after, "initial_lag_seconds": 0.0, "retention": "terminal"})
        (directory / "evidence" / "evidence.json").write_text(canonical(index))
        (directory / "evidence" / "frames" / (after_id + ".png")).write_bytes(png())
        payload = canonical({"schema": "mission/11", "kind": "lifecycle", "request_id": "request-1",
            "mission_id": "mission-a", "epoch": 0, "operation": "save", "world": "world", "character": "person",
            "sources": [identity], "expected_session": "native-session", "expected_revision": 30,
            "expected_boundary_id": "boundary-1", "limits": {"primitives": 1, "wall_seconds": 60, "game_seconds": 60},
            "work_id": None, "phase_id": None, "identity_claim_ids": []})
        self.edit_db(directory, "UPDATE requests SET payload=?,digest=?,state='unknown'",
                     (payload, digest(payload.encode())))
        proof = {"schema": "mission/11", "record_type": "LifecycleTransition", "operation": "save",
            "origin_request_id": "request-1", "terminal_request_id": "request-1", "terminal_logical_id": "logical-1",
            "native_request_id": "native-1", "launch_request_id": "launch-1", "launch_id": "owned-launch",
            "before_source_id": identity, "after_source_id": after_id, "origin_epoch": 0, "reconciled_epoch": 0,
            "actor_id": "player", "controller_boot_id": "boot", "operator_pause_generation": 0,
            "before_takeover_generation": 0, "after_takeover_generation": 0, "grants_authority": False}
        effect = {"schema": "mission/11", "record_type": "EffectReconciliation", "basis": "LifecycleTransition",
            "sources": [identity, after_id], "note": "Scoped typed fixture", "proof": proof}
        pin = self.edit_db(directory, "INSERT INTO primitives VALUES (?,?,?,?,?,?,?)", ("logical-1", "request-1",
            canonical(intent(value="save", source_before=identity, preflight_source=identity)), "native-1", "unknown", None,
            canonical(effect)))
        library = self.library(pin)
        self.assertEqual(library.records(), (record,))
        self.assertEqual(library.request("mission-a", "request-1")["state"], "unknown")
        library.close()
        pin = self.edit_index(directory, lambda index: index.update(blocked=[identity, after_id]))
        with self.library(pin) as library:
            self.assertEqual(library.records(), (record,))
            self.assertEqual(library.request("mission-a", "request-1")["state"], "unknown")
        effect["proof"]["terminal_logical_id"] = "different-input"
        pin = self.edit_db(directory, "UPDATE primitives SET effect=?", (canonical(effect),))
        with self.assertRaisesRegex(ContractError, "original primitive"):
            self.library(pin)

    def test_cross_mission_ancestry_and_episode_closure_are_explicit_and_pinned(self):
        _, identity, first, a = self.archive()
        child = successor(first, mission_id="mission-b", id="revision-b", support=first["support"])
        directory, _, _, b = self.archive("mission-b", records=[child], dependencies=[a])
        library = self.library(b, a)
        self.assertEqual(project_procedures(library.records()), {first["procedure_id"]: child})
        with self.assertRaises(ContractError):
            self.library(b)
        library.close()
        db = sqlite3.connect(directory / "mission.sqlite3")
        admission = json.loads(db.execute("SELECT value FROM metadata WHERE key='admission'").fetchone()[0])
        db.close()
        admission["learning"]["library_sources"][0]["ledger_sha256"] = "0" * 64
        b = self.edit_db(directory, "UPDATE metadata SET value=? WHERE key='admission'", (canonical(admission),))
        with self.assertRaises(ContractError):
            self.library(a, b)

    def test_fifth_donor_retains_self_contained_root_and_full_ancestry_on_reopen(self):
        pins, ancestors = [], []
        for index in range(4):
            mission = f"ancestor-{index}"
            support = [{"mission_id": mission, "request_ids": ["request-1"],
                "source_ids": [_identity(observation(session=mission))], "interpretation": "Synthetic ancestor"}]
            record = (procedure(mission_id=mission, support=support) if not ancestors else
                successor(ancestors[-1], mission_id=mission, support=ancestors[-1]["support"] + support))
            _, _, _, pin = self.archive(mission, records=[record], dependencies=pins)
            pins.append(pin)
            ancestors.append(record)
        mission = "fifth-donor"
        own_support = [{"mission_id": mission, "request_ids": ["request-1"],
            "source_ids": [_identity(observation(session=mission))], "interpretation": "Synthetic fifth donor"}]
        own = procedure(mission_id=mission, id="fifth-root", procedure_id="fifth-only", support=own_support)
        descendant = successor(ancestors[-1], mission_id=mission, id="fifth-descendant",
            support=ancestors[-1]["support"] + own_support)
        directory, _, _, fifth = self.archive(mission, records=[own, descendant], dependencies=pins)
        expected = tuple(ancestors + [own, descendant])
        all_pins = [*pins, fifth]
        originals = {path.relative_to(self.root): path.read_bytes()
            for path in self.root.rglob("*") if path.is_file()}
        for _ in range(2):
            with self.library(*all_pins) as library:
                self.assertEqual(library.records(), expected)
                self.assertEqual(project_procedures(library.records()),
                    {own["procedure_id"]: own, descendant["procedure_id"]: descendant})
                for episode in descendant["support"]:
                    self.assertEqual(library.validate_episode(episode),
                        ((episode["mission_id"], episode["source_ids"][0]),))
                    self.assertEqual(library.source(episode["mission_id"], episode["source_ids"][0])[1], png())
        self.assertEqual(all_pins, [self.pin(pin["mission_id"]) for pin in all_pins])
        self.assertEqual(originals, {path.relative_to(self.root): path.read_bytes()
            for path in self.root.rglob("*") if path.is_file()})
        # Even a self-contained fifth-owned root does not prune its owner's
        # declared whole-donor dependencies or fetch omitted archives.
        for selected in ([fifth], all_pins[1:], [*pins[:-1], {**pins[-1], "ledger_sha256": "0" * 64}, fifth]):
            with self.subTest(selected=selected), self.assertRaises(ContractError):
                self.library(*selected)
        db = sqlite3.connect(directory / "mission.sqlite3")
        stored = json.loads(db.execute("SELECT value FROM metadata WHERE key='admission'").fetchone()[0])
        db.close()
        self.assertEqual(stored["learning"]["library_sources"], pins)
        # Remove the descendant in this separate synthetic variant: admission
        # closure still applies when the fifth archive retains only its own root.
        self_contained = self.edit_db(directory, "DELETE FROM memory WHERE record_id=?", (descendant["id"],))
        with self.library(*pins, self_contained) as library:
            self.assertEqual(library.records(), tuple(ancestors + [own]))
        with self.assertRaisesRegex(ContractError, "missing or conflicting dependency pin"):
            self.library(self_contained)

    def test_eight_donor_256_record_fixture_mounts_and_ninth_or_257_records_refuse(self):
        # Frozen synthetic setup envelope: eight sealed donors, each with 32
        # independent records, one PNG and one settled observe request. This is
        # setup/mount evidence, not a routine-play cadence or archive-size claim.
        pins, expected = [], []
        for index in range(8):
            mission = f"capacity-{index}"
            support = [{"mission_id": mission, "request_ids": ["request-1"],
                "source_ids": [_identity(observation(session=mission))], "interpretation": "Synthetic capacity"}]
            records = [procedure(mission_id=mission, id=f"revision-{row}",
                procedure_id=f"procedure-{index}-{row}", support=support) for row in range(32)]
            _, _, _, pin = self.archive(mission, records=records)
            pins.append(pin)
            expected.extend(records)
        for _ in range(2):
            with self.library(*pins) as library:
                self.assertEqual(library.records(), tuple(expected))
                self.assertEqual(len(project_procedures(library.records())), 256)
        _, _, _, ninth = self.archive("capacity-8")
        with self.assertRaisesRegex(ContractError, "at most 8"):
            self.library(*pins, ninth)
        extra = procedure(mission_id="capacity-7", id="extra-revision", procedure_id="extra-procedure",
            support=expected[-1]["support"])
        directory = self.root / ".runtime" / "missions" / "capacity-7"
        pins[-1] = self.edit_db(directory, "INSERT INTO memory VALUES (?,?,?,?,?)",
            (33, "extra-event", "procedure", extra["id"], canonical(extra)))
        with self.assertRaisesRegex(ContractError, "procedure record"):
            self.library(*pins)

    def test_current_revision_can_validate_historical_episodes_with_exact_qualified_ids(self):
        _, identity, record, pin = self.archive()
        library = self.library(pin)
        episode = record["support"][0]
        self.assertEqual(library.validate_episode(episode), (("mission-a", identity),))
        for change in ({"mission_id": "foreign"}, {"request_ids": ["missing"]},
                       {"source_ids": ["missing"]}, {"request_ids": []},
                       {"source_ids": [identity, identity]}, {"inventory": "prose"},
                       {"request_ids": ["request-1\n"]}):
            with self.subTest(change=change), self.assertRaises(ContractError):
                library.validate_episode({**episode, **change})
        library.close()
        with self.assertRaises(ContractError):
            library.validate_episode(episode)

    def test_source_byte_limits_are_enforced_before_decoding(self):
        directory, identity, _, pin = self.archive()
        for path, limit in ((directory / "mission.sqlite3", 64 * 1024 * 1024),
                            (directory / "evidence" / "evidence.json", 34 * 1024 * 1024),
                            (directory / "evidence" / "frames" / (identity + ".png"), 32 * 1024 * 1024)):
            before = path.read_bytes()
            with path.open("r+b") as stream:
                stream.truncate(limit + 1)
            try:
                with self.subTest(path=path), self.assertRaisesRegex(ContractError, "byte bound"):
                    self.library(pin)
            finally:
                path.write_bytes(before)

    def test_missing_episode_mission_request_and_parent_or_branch_refuse(self):
        directory, _, record, _ = self.archive()
        cases = [procedure(mission_id="mission-a"), successor(record),
                 {**record, "support": [{**record["support"][0], "request_ids": ["missing"]}]},
                 {**record, "support": [{**record["support"][0], "mission_id": "missing"}]}]
        for value in cases:
            pin = self.edit_db(directory, "UPDATE memory SET body=?,record_id=?", (canonical(value), value["id"]))
            with self.subTest(value=value), self.assertRaises(ContractError):
                self.library(pin)
        self.edit_db(directory, "DELETE FROM memory")
        for i, value in enumerate((record, successor(record), successor(record, id="branch"))):
            pin = self.edit_db(directory, "INSERT INTO memory VALUES (?,?,?,?,?)",
                (i + 1, f"event-{i}", "procedure", value["id"], canonical(value)))
        with self.assertRaises(ContractError):
            self.library(pin)


class PausedProcedureLibraryTests(ProcedureLibraryTests):
    """Apply the same integrity and closure checks to closed paused archives."""

    def archive(self, mission="mission-a", *, records=None, dependencies=(), phase="paused"):
        return super().archive(mission, records=records, dependencies=dependencies, phase=phase)


if __name__ == "__main__":
    unittest.main()
