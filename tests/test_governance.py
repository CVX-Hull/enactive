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

import pytest

from tools import governance

ROOT = Path(__file__).resolve().parents[1]


def copy_source_files(root, names):
    for name in sorted(names):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = json.loads((ROOT / "docs/control-registry.json").read_text())
        # The checker reads these documents and schemas; evidence needs only
        # its referenced file, not the surrounding repository or media assets.
        names = {
            "docs/charter.md", "docs/engineering.md", "docs/protocol.md",
            "schemas/control-registry.schema.json", "schemas/acceptance-manifest.schema.json",
        }
        for control in self.registry["controls"]:
            for record in (control, control["last_exercise"], control["maintenance_review"]):
                if record is not None:
                    names.update(reference.split("#", 1)[0] for reference in record["evidence"])
        # CLI and fresh-clone tests still check every current curated manifest.
        for manifest in (ROOT / "docs/acceptance").glob("*-manifest.json"):
            names.add(str(manifest.relative_to(ROOT)))
            data = json.loads(manifest.read_text())
            names.update(data[field].split("#", 1)[0] for field in ("report", "upstream_pin"))
        copy_source_files(self.root, names)
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

    @pytest.mark.assurance_governance
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

    def test_a_passed_review_date_is_not_an_error_and_retired_controls_need_none(self):
        for day in (date(2027, 1, 15), date(2027, 1, 16), date(2030, 1, 1)):
            with self.subTest(day=day):
                self.assertEqual(governance.check_registry(self.root, self.registry, as_of=day), [])
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

    def run_cli(self, arguments):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(governance, "ROOT", self.root), \
                patch.object(governance, "date", wraps=date) as clock, \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            clock.today.return_value = date(2027, 1, 16)
            result = governance.main(arguments)
        return result, output.getvalue(), errors.getvalue()

    def test_the_command_passes_after_every_review_date_without_rewriting(self):
        registry_path = self.root / "docs/control-registry.json"
        map_path = self.root / "docs/controls.md"
        before = registry_path.read_bytes(), map_path.read_bytes()
        result, _, errors = self.run_cli([])
        self.assertEqual(result, 0, errors)
        self.assertEqual((registry_path.read_bytes(), map_path.read_bytes()), before)

    def test_record_errors_still_fail_after_the_review_date(self):
        original = copy.deepcopy(self.registry)
        cases = [
            (lambda c: c.update(maintenance_review=None), "requires maintenance review"),
            (lambda c: c.update(next_review=None), "requires next_review"),
            (lambda c: c["last_exercise"].update(date="2027-01-17"), "future"),
            (lambda c: c["maintenance_review"].update(date="2027-01-17"), "future"),
            (lambda c: c.update(next_review="2026-10-16"), "before maintenance review"),
            (lambda c: c.update(next_review="2027-01-16"), "90 days"),
            (lambda c: c.update(owner=""), "schema violation"),
            (lambda c: c.update(next_review="2026-02-30"), "schema violation"),
            (lambda c: c.update(evidence=["docs/missing.md"]), "evidence reference"),
        ]
        for mutate, expected in cases:
            with self.subTest(expected=expected):
                self.registry = copy.deepcopy(original)
                mutate(self.registry["controls"][0])
                errors = governance.check_registry(self.root, self.registry, as_of=date(2027, 1, 16))
                self.assertIn(expected, "\n".join(errors))

    def test_mapping_failure_and_stale_map_still_fail_without_rewriting(self):
        self.replace("docs/engineering.md", "Controls: C-PORTABLE, C-RUNTIME, C-NATIVE, C-USABILITY.",
                     "Controls: C-PORTABLE, C-RUNTIME, C-NATIVE.")
        result, _, errors = self.run_cli([])
        self.assertEqual(result, 1)
        self.assertIn("S-UX", errors)
        self.replace("docs/engineering.md", "Controls: C-PORTABLE, C-RUNTIME, C-NATIVE.",
                     "Controls: C-PORTABLE, C-RUNTIME, C-NATIVE, C-USABILITY.")
        map_path = self.root / "docs/controls.md"
        map_path.write_text("obsolete map\n")
        result, _, errors = self.run_cli([])
        self.assertEqual(result, 1)
        self.assertIn("stale", errors)
        self.assertEqual(map_path.read_text(), "obsolete map\n")

    def replace(self, name, before, after):
        path = self.root / name
        text = path.read_text()
        self.assertIn(before, text)
        path.write_text(text.replace(before, after))

    def test_missing_mandatory_mapping_is_rejected(self):
        self.registry["standards"].pop()
        self.assertIn("S-EVIDENCE", self.registry_errors())

    @pytest.mark.assurance_governance
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



    def test_manifest_does_not_require_local_media(self):
        # The fixture deliberately has no .runtime tree; this is a fresh-clone contract.
        self.assertFalse((self.root / ".runtime").exists())
        self.assertEqual(governance.check_manifests(self.root), [])


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        name = "docs/acceptance/2026-10-17-mvp-manifest.json"
        manifest = json.loads((ROOT / name).read_text())
        # Fault cases mutate one real manifest. The full corpus remains covered
        # above, without revalidating unrelated manifests for every mutation.
        copy_source_files(self.root, {
            name, "schemas/acceptance-manifest.schema.json",
            manifest["report"], manifest["upstream_pin"],
        })
        self.assertEqual(governance.check_manifests(self.root), [])

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


def test_evidence_schema_ids_must_be_defined_or_listed_exactly(tmp_path):
    root = tmp_path
    (root / "schemas").mkdir()
    (root / "docs/acceptance/assets/x").mkdir(parents=True)
    (root / "docs/acceptance/2026-01-01-x.md").write_text("Record.\n")
    (root / "docs/contracts").mkdir()
    (root / "docs/contracts/c.md").write_text("Rows are `known-shape/1`.\n")
    evidence = root / "docs/acceptance/assets/x/summary.json"
    registry = root / governance.EVIDENCE_IDS
    registry.write_text(json.dumps({"ids": {}}))
    evidence.write_text(json.dumps({"schema": "known-shape/1"}))
    assert governance.check_evidence_ids(root) == []  # a contract names it
    evidence.write_text(json.dumps({"schema": "one-off-summary/1"}))
    assert "defined nowhere" in "\n".join(governance.check_evidence_ids(root))
    # Only whole tokens in schemas, contracts or code define an id: not a substring, not a run log.
    (root / "docs/contracts/c.md").write_text("Rows are `known-shape/1`, `big-run/12` and `xrun/1`.\n")
    (root / "docs/log.md").write_text("A run/1 happened.\n")
    for undefined in ("run/1", "shape/1", "big-run/1"):
        evidence.write_text(json.dumps({"schema": undefined}))
        assert "defined nowhere" in "\n".join(governance.check_evidence_ids(root)), undefined
    evidence.write_text(json.dumps({"schema": "one-off-summary/1"}))
    entry = {"records": ["docs/acceptance/2026-01-01-x.md"], "files": ["docs/acceptance/assets/x/summary.json"]}
    registry.write_text(json.dumps({"ids": {"one-off-summary/1": entry}}))
    assert governance.check_evidence_ids(root) == []
    registry.write_text(json.dumps({"ids": {"one-off-summary/1": entry, "gone/1": entry | {"records": ["docs/none.md"]}}}))
    errors = "\n".join(governance.check_evidence_ids(root))
    assert "gone/1 lists" in errors and "missing record" in errors
    assert governance.check_evidence_ids(governance.ROOT) == []


def test_the_frozen_evidence_id_registry_is_closed():
    registry = json.loads((governance.ROOT / governance.EVIDENCE_IDS).read_text())["ids"]
    assert sorted(registry) == [
        "campaign-evidence-summary/1", "capable-player-304-summary/1", "corpus320-summary/1", "diagnosis-314-summary/1",
        "effects-298-evidence/1", "grounding-300-evidence/1", "investigation-295-evidence/1", "organic-play-evidence/1",
        "request-timing-summary/1", "spectator-383-evidence/1", "useful-trials-accounting/1",
        "visual-player-302-evidence/1"]


if __name__ == "__main__":
    unittest.main()
