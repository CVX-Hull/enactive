"""Negative cases for the bounded governance checks, using isolated source fixtures."""
import copy
from datetime import date
import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tools import governance

ROOT = Path(__file__).resolve().parents[1]


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("docs", "harness", "native", "tests", "tools", "web", ".github", ".githooks", "schemas"):
            shutil.copytree(ROOT / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("AGENTS.md", "README.md", "pyproject.toml", "requirements-dev.in", "requirements-dev.lock", "package.json", "package-lock.json", ".puppeteerrc.cjs"):
            shutil.copyfile(ROOT / name, self.root / name)
        self.registry = json.loads((self.root / "docs/control-registry.json").read_text())
        # Tests control time independently of legitimate future maintenance updates.
        # Production records are validated by the CLI at the actual current date.
        for control in self.registry["controls"]:
            if control["last_exercise"] is not None:
                control["last_exercise"]["date"] = "2026-10-17"
            if control["maintenance_review"] is not None:
                control["maintenance_review"]["date"] = "2026-10-17"
            if control["next_review"] is not None:
                control["next_review"] = "2027-01-15"
        (self.root / "docs/control-registry.json").write_text(json.dumps(self.registry))
        (self.root / "docs/controls.md").write_text(governance.render_map(self.registry))

    def registry_errors(self):
        return "\n".join(governance.check_registry(self.root, self.registry, as_of=date(2026, 10, 17)))

    def extra_control(self, status):
        control = copy.deepcopy(self.registry["controls"][0])
        control.update(id="C-EXTRA", status=status, rationale="Bounded lifecycle fixture.",
                       replacement=None, last_exercise=None, maintenance_review=None, next_review=None)
        self.registry["controls"].append(control)
        return control

    def test_registry_fixture_is_valid_at_record_date(self):
        self.assertEqual(self.registry_errors(), "")

    def test_only_active_controls_can_support_standards(self):
        for status in ("proposed", "deprecated", "retired"):
            with self.subTest(status=status):
                self.registry["controls"][0]["status"] = status
                self.assertIn("non-active", self.registry_errors())

    def test_inactive_controls_may_be_unmapped_but_active_orphans_fail(self):
        control = self.extra_control("proposed")
        for status in ("proposed", "retired"):
            control["status"] = status
            self.assertEqual(self.registry_errors(), "")
        control.update(status="active", maintenance_review=copy.deepcopy(
            self.registry["controls"][0]["maintenance_review"]), next_review="2027-01-15")
        self.assertIn("orphan control", self.registry_errors())

    def test_retirement_and_deprecation_require_rationale(self):
        control = self.extra_control("retired")
        for status in ("retired", "deprecated"):
            control.update(status=status, rationale=None)
            self.assertIn("rationale", self.registry_errors())

    def test_active_and_deprecated_require_review_and_due_date(self):
        control = self.extra_control("deprecated")
        self.assertIn("maintenance review", self.registry_errors())
        control["maintenance_review"] = copy.deepcopy(self.registry["controls"][0]["maintenance_review"])
        self.assertIn("next_review", self.registry_errors())

    def test_replacements_reject_self_unknown_and_cycles(self):
        control = self.extra_control("retired")
        for replacement, expected in (("C-EXTRA", "self"), ("C-UNKNOWN", "unknown")):
            control["replacement"] = replacement
            self.assertIn(expected, self.registry_errors())
        control["replacement"] = "C-PORTABLE"
        self.registry["controls"][0]["replacement"] = "C-EXTRA"
        self.assertIn("cycle", self.registry_errors())

    def test_future_dates_ordering_and_review_interval(self):
        original = copy.deepcopy(self.registry)
        cases = [
            ("last_exercise", "2026-10-18", "future"),
            ("maintenance_review", "2026-10-18", "future"),
            ("next_review", "2026-10-16", "before"),
            ("next_review", "2027-01-16", "90 days"),
            ("next_review", "2026-02-30", "schema"),
        ]
        for field, value, expected in cases:
            with self.subTest(field=field, value=value):
                self.registry = copy.deepcopy(original)
                control = self.registry["controls"][0]
                if field == "next_review":
                    control[field] = value
                else:
                    control[field]["date"] = value
                self.assertIn(expected, self.registry_errors())

    def test_exercise_and_maintenance_review_are_independent_events(self):
        self.registry["controls"][0]["maintenance_review"]["date"] = "2026-10-16"
        self.registry["controls"][0]["next_review"] = "2027-01-14"
        self.assertEqual(self.registry_errors(), "")

    def test_due_boundary_and_retired_controls_do_not_require_periodic_review(self):
        self.assertEqual(governance.check_registry(self.root, self.registry, as_of=date(2027, 1, 15)), [])
        self.assertIn("overdue", "\n".join(governance.check_registry(
            self.root, self.registry, as_of=date(2027, 1, 16))))
        control = self.extra_control("retired")
        control.update(maintenance_review=copy.deepcopy(self.registry["controls"][0]["maintenance_review"]),
                       next_review="2026-10-16")
        control["maintenance_review"]["date"] = "2026-10-16"
        self.assertEqual(self.registry_errors(), "")
        control["next_review"] = None
        self.assertEqual(self.registry_errors(), "")

    def test_exercise_and_review_evidence_use_safe_existing_files(self):
        for field in ("last_exercise", "maintenance_review"):
            for reference in ("../outside.md", "docs/missing.md", "/etc/passwd"):
                with self.subTest(field=field, reference=reference):
                    self.registry["controls"][0][field]["evidence"] = [reference]
                    self.assertIn("evidence reference", self.registry_errors())

    def test_forecast_prints_date_and_never_renews_records(self):
        registry_path = self.root / "docs/control-registry.json"
        before = registry_path.read_bytes()
        map_path = self.root / "docs/controls.md"
        before_map = map_path.read_bytes()
        with patch.object(governance, "ROOT", self.root), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(governance.main(["--as-of", "2027-01-15"]), 0)
        self.assertIn("2027-01-15", out.getvalue())
        with patch.object(governance, "ROOT", self.root), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(governance.main(["--as-of", "2027-01-16"]), 1)
        self.assertEqual(registry_path.read_bytes(), before)
        self.assertEqual(map_path.read_bytes(), before_map)

    def test_forecast_requires_an_iso_calendar_date(self):
        for value in ("20261017", "2026-W42-6", "2026-02-30"):
            with self.subTest(value=value), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    governance.main(["--as-of", value])
                self.assertEqual(raised.exception.code, 2)

    def replace(self, name, before, after):
        path = self.root / name
        text = path.read_text()
        self.assertIn(before, text)
        path.write_text(text.replace(before, after))

    def test_missing_mandatory_mapping_is_rejected(self):
        self.registry["standards"].pop()
        self.assertIn("S-EVIDENCE", self.registry_errors())

    def test_unknown_references_duplicates_and_missing_fields_are_rejected(self):
        cases = [
            (lambda r: r["standards"][0]["principles"].append("P-INVENTED"), "P-INVENTED"),
            (lambda r: r["standards"][0]["controls"].append("C-INVENTED"), "C-INVENTED"),
            (lambda r: r["controls"].append(copy.deepcopy(r["controls"][0])), "duplicate"),
            (lambda r: r["standards"].append(copy.deepcopy(r["standards"][0])), "duplicate"),
            (lambda r: r["controls"][0].pop("failure_response"), "failure_response"),
            (lambda r: r["controls"][0].update(status="invented"), "status"),
            (lambda r: r["standards"][0].update(controls=[]), "controls"),
        ]
        original = copy.deepcopy(self.registry)
        for mutate, expected in cases:
            with self.subTest(expected=expected):
                self.registry = copy.deepcopy(original)
                mutate(self.registry)
                self.assertIn(expected, self.registry_errors())

    def test_registry_references_cannot_escape_or_be_missing(self):
        for reference in ("../outside.md", "/etc/passwd", "docs/missing.md"):
            with self.subTest(reference=reference):
                self.registry["controls"][0]["evidence"] = [reference]
                self.assertIn("reference", self.registry_errors())
        (self.root / "docs/escape").symlink_to(self.root.parent, target_is_directory=True)
        self.registry["controls"][0]["evidence"] = ["docs/escape/outside.md"]
        self.assertFalse(governance.local_reference(self.root, "docs/escape/outside.md", exists=False))

    def test_changed_document_mapping_is_detected(self):
        self.replace("docs/engineering.md", "Principles: P-AUTHORITY, P-TRUTH, P-REVIEW, P-UNCERTAINTY.",
                     "Principles: P-AUTHORITY, P-TRUTH, P-REVIEW.")
        self.assertIn("S-UX", self.registry_errors())

    def test_stale_map_is_rejected_without_rewriting(self):
        path = self.root / "docs/controls.md"
        path.write_text("obsolete map\n")
        self.assertIn("stale", "\n".join(governance.check_generated(self.root, self.registry)))
        self.assertEqual(path.read_text(), "obsolete map\n")

    def test_protocol_drift_at_each_representation_is_detected(self):
        self.assertEqual(governance.check_protocol(self.root), [])
        changes = [
            ("native/cdda_harness.cpp", 'out.member( "protocol", 3 )', 'out.member( "protocol", 1 )'),
            ("native/cdda_harness.cpp", 'request.get_int( "protocol" ) != 3', 'request.get_int( "protocol" ) != 1'),
            ("harness/controller.py", '"protocol": 3', '"protocol": 1'),
            ("harness/controller.py", '"protocol": 3', '"protocol": "1"'),
            ("harness/controller.py", 'value["protocol"] != 3', 'value["protocol"] != 1'),
            ("harness/server.py", '"protocol": 3', '"protocol": 1'),
            ("harness/__main__.py", 'config["protocol"] != 3', 'config["protocol"] != 1'),
            ("harness/controller.py", 'request["protocol"] != 3', 'request["protocol"] != 1'),
            ("web/app.js", 'latest.state.protocol !== 3', 'latest.state.protocol !== 1'),
            ("native/cdda_harness.cpp", r'\"protocol\":3', r'\"protocol\":2'),
            ("native/cdda_harness.cpp", 'integer_member( request, "protocol" ) != 3', 'integer_member( request, "protocol" ) != 2'),
            ("harness/gameplay/evidence.py", '"protocol": {"type": "integer", "const": 3}', '"protocol": {"type": "integer", "const": 2}'),
            ("docs/protocol.md", 'Protocol version: 3.', 'Protocol version: 1.'),
        ]
        for name, before, after in changes:
            with self.subTest(name=name, before=before):
                self.replace(name, before, after)
                self.assertTrue(governance.check_protocol(self.root))
                self.replace(name, after, before)

    def test_protocol_refactor_requires_checker_review(self):
        self.replace("native/cdda_harness.cpp", 'out.member( "protocol", 3 )',
                     'out.member( "protocol", CURRENT_PROTOCOL )')
        self.assertIn("representation", "\n".join(governance.check_protocol(self.root)))

    def test_manifest_rejects_bad_provenance_hash_and_paths(self):
        path = self.root / "docs/acceptance/2026-10-17-mvp-manifest.json"
        original = json.loads(path.read_text())
        for field, value in (("source_commit", "unknown"), ("source_sha256", "x" * 64),
                             ("date", "2026-02-30"), ("platform", ""),
                             ("report", "../outside.md"), ("schema_version", True)):
            with self.subTest(field=field):
                data = copy.deepcopy(original)
                data[field] = value
                path.write_text(json.dumps(data))
                self.assertTrue(governance.check_manifests(self.root))
        for artifact in ("../outside.png", "/tmp/frame.png", "docs/../frame.png"):
            data = copy.deepcopy(original)
            data["artifacts"] = {artifact: next(iter(original["artifacts"].values()))}
            path.write_text(json.dumps(data))
            self.assertIn("artifact", "\n".join(governance.check_manifests(self.root)))

    def test_manifest_does_not_require_local_media(self):
        # The fixture deliberately has no .runtime tree; this is a fresh-clone contract.
        self.assertFalse((self.root / ".runtime").exists())
        self.assertEqual(governance.check_manifests(self.root), [])

    def test_still_frame_acceptance_needs_no_fabricated_video(self):
        path = self.root / "docs/acceptance/2026-10-17-mvp-manifest.json"
        data = json.loads(path.read_text())
        data["video"] = None
        path.write_text(json.dumps(data))
        self.assertEqual(governance.check_manifests(self.root), [])
        for invalid in ({}, "none", {"capture_interval_ms": [0, 1]}):
            with self.subTest(video=invalid):
                data["video"] = invalid
                path.write_text(json.dumps(data))
                self.assertTrue(governance.check_manifests(self.root))

    def test_manifest_rejects_invalid_artifact_metadata(self):
        path = self.root / "docs/acceptance/2026-10-17-mvp-manifest.json"
        original = json.loads(path.read_text())
        for field, value in (("sha256", "a" * 63), ("bytes", True),
                             ("bytes", -1), ("availability", "verified")):
            with self.subTest(field=field, value=value):
                data = copy.deepcopy(original)
                next(iter(data["artifacts"].values()))[field] = value
                path.write_text(json.dumps(data))
                self.assertIn("artifacts", "\n".join(governance.check_manifests(self.root)))


if __name__ == "__main__":
    unittest.main()
