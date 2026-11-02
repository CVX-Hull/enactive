"""Offline computer-source fixtures; no browser paint or native qualification."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from harness.computer.protocol import ControlError
from tools.control_analysis import control_summary, read_sources
from tools.evaluate import main
from tools.observer_analysis import witness_summary


class ComputerAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.session = "a" * 32
        self.source = dict(schema="computer-source/1", source_id=self.session + "-1", session=self.session,
            capture_id=1, sha256="b" * 64, media_type="image/png", presented_ms=1000,
            received_wall=1.025, width=20, height=10, window_width=20, window_height=10,
            viewport=[0, 0, 20, 10])
        self.database = self.root / "session.sqlite3"
        with sqlite3.connect(self.database) as db:
            db.executescript('''PRAGMA user_version=3;
                CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE sources(id TEXT PRIMARY KEY,metadata TEXT NOT NULL,bytes INTEGER NOT NULL);
                CREATE TABLE operations(id TEXT PRIMARY KEY,actor TEXT NOT NULL,kind TEXT NOT NULL,
                    created_wall REAL NOT NULL,deadline REAL NOT NULL,input_json TEXT NOT NULL,final_json TEXT);
                CREATE TABLE native_intents(id TEXT PRIMARY KEY,operation TEXT NOT NULL,receipt TEXT,source TEXT,timing TEXT NOT NULL);
                CREATE TABLE collections(native_id TEXT PRIMARY KEY,receipt TEXT NOT NULL,source TEXT);''')
            db.executemany("INSERT INTO metadata VALUES(?,?)", [("schema", json.dumps("computer-session/3")), ("session", json.dumps(self.session))])
            db.execute("INSERT INTO sources VALUES(?,?,?)", (self.source["source_id"], json.dumps(self.source), 120))
            final = dict(schema="computer-operation/1", operation_id="op", actor_id="actor", session=self.session,
                         kind="input", status="unknown", reason="PRIVATE")
            db.execute("INSERT INTO operations VALUES(?,?,?,?,?,?,?)", ("op", "actor", "input", .8, 10, '[{"type":"text","text":"PRIVATE"}]', json.dumps(final)))
            unknown = self.receipt("unknown")
            db.execute("INSERT INTO native_intents VALUES(?,?,?,?,?)", ("native", "op", json.dumps(unknown), None,
                json.dumps(dict(intent_wall=.9, intent_monotonic=10, send_started_monotonic=10.01,
                    send_finished_monotonic=10.02, receipt_received_monotonic=10.1))))
            db.execute("INSERT INTO collections VALUES(?,?,?)", ("native", json.dumps(self.receipt("delivered")), self.source["source_id"]))

    def receipt(self, disposition):
        return dict(schema="computer-receipt/2", id="native", session=self.session, disposition=disposition,
                    emitted_events=1, reason="PRIVATE", frame=None)

    def observer(self, rows, name="observer.json", **fields):
        path = self.root / name
        path.write_text(json.dumps(dict(schema="observer-timing/4", retention_limit=2000,
            omitted_rows=3, clock="wall clocks assumed", scope="DOM only", rows=rows, **fields)))
        return path

    def row(self, **fields):
        return dict(session=self.session, source_id=self.source["source_id"], capture_id=1,
            presented_ms=1000, observed_at_wall_ms=1010, decode_finished_wall_ms=1030,
            dom_replaced_wall_ms=1040, outcome="displayed", error=None, **fields)

    def test_exact_current_join_deduplicates_overlapping_exports(self):
        row = self.row()
        observer = self.observer([row, row])
        later = self.observer([{**row, "dom_replaced_wall_ms": 1050}], "later.json")
        report = witness_summary([self.root, observer, observer, later])
        self.assertEqual(report["unique_source_presented_to_dom_ms"]["sum"], 40)
        self.assertEqual(report["source_rows"][0]["distinct_matching_presentations"], 2)
        self.assertEqual(report["source_rows"][0]["received_to_dom_ms"], 15)
        self.assertEqual(report["exports"][0]["omitted_rows"], 3)
        self.assertIn("not physical paint", report["scope"])
        self.assertNotIn("PRIVATE", json.dumps(report))

    def test_session_source_capture_and_original_presented_clock_must_all_match(self):
        row = self.row()
        for changes in ({"session": "c" * 32}, {"source_id": self.session + "-2"},
                        {"capture_id": 2}, {"presented_ms": 1001}, {"outcome": "unavailable"}):
            observer = self.observer([{**row, **changes}])
            report = witness_summary([self.database, observer])
            self.assertEqual(report["missing_source_matches"], 1)
            self.assertEqual(report["unique_source_presented_to_dom_ms"]["n"], 0)

    def test_negative_clock_interval_remains_visible_and_is_not_a_latency_sample(self):
        observer = self.observer([{**self.row(), "dom_replaced_wall_ms": 990}])
        report = witness_summary([self.database, observer])
        self.assertEqual(report["source_rows"][0]["presented_to_dom_ms"], -10)
        self.assertEqual(report["source_rows"][0]["missing_reason"], "invalid_cross_clock_interval")
        self.assertEqual(report["unique_source_presented_to_dom_ms"]["n"], 0)

    def test_unsupported_db_and_source_versions_reject_without_migration(self):
        original = self.database.read_bytes()
        self.assertEqual(read_sources(self.database)[0]["presented_ms"], 1000)
        self.assertEqual(self.database.read_bytes(), original)
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE metadata SET value=? WHERE key='schema'", (json.dumps("computer-session/1"),))
        with self.assertRaisesRegex(ControlError, "Unsupported"):
            read_sources(self.database)
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE metadata SET value=? WHERE key='schema'", (json.dumps("computer-session/3"),))
            db.execute("UPDATE sources SET metadata=?", (json.dumps({**self.source, "schema": "computer-source/0"}),))
        with self.assertRaises(ControlError):
            read_sources(self.database)

    def test_old_observer_export_and_duplicate_json_fields_reject(self):
        path = self.root / "old.json"
        for data in ('{"schema":"observer-timing/3","frames":[]}',
                     '{"schema":"observer-timing/4","schema":"observer-timing/4","rows":[]}'):
            path.write_text(data)
            with self.assertRaises(ControlError):
                witness_summary([self.database, path])

    def test_original_unknown_and_later_collection_are_separate_and_read_only(self):
        before = hashlib.sha256(self.database.read_bytes()).hexdigest()
        report = control_summary([self.root])
        row = report["sessions"][0]
        self.assertEqual(row["operation_statuses"], {"unknown": 1})
        self.assertEqual(row["original_native_dispositions"], {"unknown": 1})
        self.assertEqual(row["additional_collection_dispositions"], {"delivered": 1})
        self.assertAlmostEqual(row["timing_ms"]["send_to_receipt"]["p50"], 90)
        self.assertEqual(row["native_rows"][0]["source_id"], None)
        self.assertEqual(row["native_rows"][0]["additional_source_id"], self.source["source_id"])
        self.assertNotIn("PRIVATE", json.dumps(report))
        self.assertEqual(hashlib.sha256(self.database.read_bytes()).hexdigest(), before)

    def test_transport_unknown_is_not_a_native_ack_or_replaced_by_collection(self):
        transport = dict(schema="computer-transport/2", id="native", session=self.session,
            disposition="unknown", emitted_events=None, frame=None, reason="Original deadline")
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE native_intents SET receipt=?", (json.dumps(transport),))
        row = control_summary([self.database])["sessions"][0]
        self.assertEqual(row["original_native_dispositions"], {"transport_unknown": 1})
        self.assertEqual(row["additional_collection_dispositions"], {"delivered": 1})
        self.assertEqual(row["operation_statuses"], {"unknown": 1})

    def test_missing_native_endpoints_remain_unknown_not_zero(self):
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE native_intents SET timing='{}'")
        report = control_summary([self.database])["sessions"][0]
        self.assertEqual(report["timing_ms"]["send_to_receipt"]["n"], 0)
        self.assertIsNone(report["native_rows"][0]["send_to_receipt_ms"])

    def test_missing_db_is_not_created_and_duplicate_selection_rejects(self):
        missing = self.root / "missing.sqlite3"
        with self.assertRaises(ControlError):
            read_sources(missing)
        self.assertFalse(missing.exists())
        with self.assertRaises(ControlError):
            control_summary([self.database, self.root])

    def test_current_cli_has_no_legacy_mission_evaluation(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["validate", str(self.database)])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["control-summary", str(self.root)]), 0)
        self.assertEqual(json.loads(output.getvalue())["schema"], "control-analysis/1")

    def test_byte_and_row_bounds_reject_without_partial_summary(self):
        observer = self.observer([self.row()])
        with patch("tools.observer_analysis.MAX_EXPORT_BYTES", 1), self.assertRaises(ControlError):
            witness_summary([self.database, observer])
        with patch("tools.control_analysis.MAX_ROWS", 0), self.assertRaises(ControlError):
            read_sources(self.database)
        with patch("tools.control_analysis.MAX_DATABASE_BYTES", 1), self.assertRaises(ControlError):
            control_summary([self.database])

    def test_the_previous_session_version_and_schema_are_rejected(self):
        with sqlite3.connect(self.database) as db:
            db.execute("PRAGMA user_version=2")
        with self.assertRaisesRegex(ControlError, "Unsupported computer session database version"):
            read_sources(self.database)
        with sqlite3.connect(self.database) as db:
            db.execute("PRAGMA user_version=3")
            db.execute("UPDATE metadata SET value=? WHERE key='schema'", (json.dumps("computer-session/2"),))
        with self.assertRaisesRegex(ControlError, "Unsupported computer session schema"):
            read_sources(self.database)

    def test_database_user_version_rejects_before_old_rows_are_read(self):
        with sqlite3.connect(self.database) as db:
            db.execute("PRAGMA user_version=1")
            db.execute("UPDATE sources SET metadata='malformed'")
        with self.assertRaisesRegex(ControlError, "Unsupported computer session database version"):
            read_sources(self.database)
