"""Negative cases for the bounded governance checks, using isolated source fixtures."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools import governance

ROOT = Path(__file__).resolve().parents[1]


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("docs", "harness", "native", "tests", "tools", ".github", ".githooks", "schemas"):
            shutil.copytree(ROOT / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("AGENTS.md", "README.md", "pyproject.toml", "requirements-dev.in", "requirements-dev.lock"):
            shutil.copyfile(ROOT / name, self.root / name)
        self.registry = json.loads((self.root / "docs/control-registry.json").read_text())

    def registry_errors(self):
        return "\n".join(governance.check_registry(self.root, self.registry))

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
        changes = [
            ("native/cdda_harness.cpp", 'out.member( "protocol", 1 )', 'out.member( "protocol", 2 )'),
            ("native/cdda_harness.cpp", 'request.get_int( "protocol" ) != 1', 'request.get_int( "protocol" ) != 2'),
            ("harness/controller.py", '"protocol": 1', '"protocol": 2'),
            ("harness/controller.py", '"protocol": 1', '"protocol": "1"'),
            ("harness/controller.py", 'value["protocol"] != 1', 'value["protocol"] != 2'),
            ("harness/server.py", '"protocol": 1', '"protocol": 2'),
            ("docs/protocol.md", 'Protocol version: 1.', 'Protocol version: 2.'),
        ]
        for name, before, after in changes:
            with self.subTest(name=name, before=before):
                self.replace(name, before, after)
                self.assertTrue(governance.check_protocol(self.root))
                self.replace(name, after, before)

    def test_protocol_refactor_requires_checker_review(self):
        self.replace("native/cdda_harness.cpp", 'out.member( "protocol", 1 )',
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
