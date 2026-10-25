"""Pilot glue boundaries, not a reimplementation of pytest or SQLite tests."""
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest

from tools import testing_pilots as pilot


class TestingPilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_testmon_synthetic_deselections_keep_count_without_inventing_ids(self):
        recorder = pilot.Recorder(self.root)
        recorder.pytest_deselected([SimpleNamespace(nodeid="real.py::test_real"), object(), object()])
        self.assertEqual(recorder.data["deselected"], ["real.py::test_real"])
        self.assertEqual(recorder.data["unidentified_deselections"], 2)

    def test_unsupported_dynamic_context_warning_never_qualifies_a_green_map(self):
        result = self.result()
        result["mapping_warnings"] = [{"category": "coverage.exceptions.CoverageWarning",
                                      "message": "Dynamic contexts unsupported (no-sysmon-context)"}]
        result["status"] = pilot.status(result)
        self.assertEqual(result["status"], "mapping-unqualified")
        target = "test.py::target"
        self.assertEqual(pilot.judge(self.result(1, (target,)), result, target), "unqualified")

    def result(self, code=0, failed=(), selected=("test.py::target",), errors=(), timeout=False):
        result = {"returncode": code, "call_failed": list(failed), "selected": list(selected),
                  "errors": list(errors), "timeout": timeout, "records": [{}], "skipped": []}
        result["status"] = pilot.status(result)
        return result

    def test_only_confirmed_exact_target_call_failure_is_detection(self):
        target = "test.py::target"
        confirmation = self.result(1, (target,))
        self.assertEqual(pilot.judge(confirmation, self.result(1, (target,)), target), "detected")
        self.assertEqual(pilot.judge(confirmation, self.result(1, ("test.py::other",)), target), "miss")
        self.assertEqual(pilot.judge(confirmation, self.result(5, selected=()), target), "miss")
        self.assertEqual(pilot.judge(confirmation, self.result(), target), "miss")
        self.assertEqual(pilot.judge(self.result(1, ("test.py::other",)), self.result(1, (target,)), target), "unconfirmed")

    def test_setup_collection_internal_and_timeout_never_qualify(self):
        target = "test.py::target"
        confirmation = self.result(1, (target,))
        cases = [self.result(2), self.result(3), self.result(4), self.result(timeout=True)]
        cases += [self.result(1, errors=({"nodeid": target, "phase": phase},))
                  for phase in ("collection", "setup", "teardown")]
        for result in cases:
            with self.subTest(status=result["status"]):
                self.assertEqual(pilot.judge(confirmation, result, target), "unqualified")
        missing = self.result()
        missing["records"] = []
        self.assertEqual(pilot.status(missing), "execution-error")
        skipped = self.result()
        skipped["skipped"] = [target]
        skipped["status"] = pilot.status(skipped)
        self.assertEqual(pilot.judge(confirmation, skipped, target), "unqualified")

    def test_output_refuses_overwrite_escape_symlink_and_git_metadata(self):
        output = pilot.new_output(self.root, self.root / "results")
        (output / "keep").write_text("original")
        for requested in (output, self.root, self.root.parent / "escape", self.root / ".git/new"):
            with self.subTest(path=requested), self.assertRaises((ValueError, FileExistsError)):
                pilot.new_output(self.root, requested)
        (self.root / "escape-link").symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaises(ValueError):
            pilot.new_output(self.root, self.root / "escape-link/new")
        self.assertEqual((output / "keep").read_text(), "original")

    def test_reset_removes_mutations_generated_files_and_bytecode_at_same_path(self):
        pristine, work = self.root / "pristine", self.root / "work"
        pristine.mkdir()
        (pristine / "source.py").write_text("pristine")
        (pristine / "__pycache__").mkdir()
        (pristine / "__pycache__/old.pyc").write_bytes(b"stale")
        for name, text in pilot.SUPPLEMENTAL.items():
            path = pristine / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        pilot.restore_source(pristine, work)
        (work / "source.py").write_text("fault")
        (work / "generated.sqlite").touch()
        (work / "pilot_subject/helper.py").write_text("fault")
        pilot.restore_source(pristine, work)
        self.assertEqual((work / "source.py").read_text(), "pristine")
        self.assertEqual((work / "pilot_subject/helper.py").read_text(), pilot.SUPPLEMENTAL["pilot_subject/helper.py"])
        self.assertFalse((work / "generated.sqlite").exists())
        self.assertFalse((work / "__pycache__").exists())

    def test_map_reset_discards_learning_and_sidecars(self):
        pristine, selected = self.root / "map.sqlite", self.root / "selected.sqlite"
        with sqlite3.connect(pristine) as connection:
            connection.execute("create table evidence (value text)")
            connection.execute("insert into evidence values ('pristine')")
        pilot.backup_map(pristine, selected)
        with sqlite3.connect(selected) as connection:
            connection.execute("update evidence set value='learned'")
        (self.root / "selected.sqlite-wal").write_text("stale")
        pilot.backup_map(pristine, selected)
        with sqlite3.connect(selected) as connection:
            self.assertEqual(connection.execute("select value from evidence").fetchone(), ("pristine",))
        self.assertFalse((self.root / "selected.sqlite-wal").exists())

    def test_exact_anchor_required_and_owner_mutates_only_first_control(self):
        seed = pilot.Seed("small", "subject.py", "original", "mutated", "target", "fixture")
        path = self.root / seed.path
        for source in ("missing", "original original"):
            path.write_text(source)
            with self.assertRaisesRegex(ValueError, "expected one exact anchor"):
                pilot.mutate(self.root, seed)
            self.assertEqual(path.read_text(), source)
        path.write_text("original")
        proof = pilot.mutate(self.root, seed)
        self.assertEqual(path.read_text(), "mutated")
        self.assertNotEqual(proof["before_sha256"], proof["after_sha256"])
        path = self.root / "docs/control-registry.json"
        path.parent.mkdir()
        path.write_text(json.dumps({"controls": [{"owner": "maintainer"}, {"owner": "second"}]}))
        pilot.mutate(self.root, pilot.SEEDS[3])
        self.assertEqual(json.loads(path.read_text())["controls"], [{"owner": ""}, {"owner": "second"}])
        with self.assertRaisesRegex(ValueError, "nonempty string"):
            pilot.mutate(self.root, pilot.SEEDS[3])

    def test_frozen_real_anchors_and_independent_targets_exist(self):
        self.assertEqual(len(pilot.SEEDS), 8)
        self.assertEqual(len(pilot.COHORT), 11)
        for seed in pilot.SEEDS:
            self.assertIn(seed.target, pilot.COHORT)
            if seed.before and seed.path not in pilot.SUPPLEMENTAL:
                self.assertEqual((pilot.ROOT / seed.path).read_text().count(seed.before), 1, seed.name)
            if not seed.path.startswith("pilot_subject"):
                self.assertTrue((pilot.ROOT / seed.path).is_file())

    def test_real_public_collection_and_call_reports_preserve_node_identity(self):
        # The runner uses the production hook adapter, with actual pytest and an
        # isolated source fixture. Stdout content is deliberately irrelevant.
        (self.root / "tools").mkdir()
        shutil.copyfile(pilot.ROOT / "tools/testing_pilots.py", self.root / "tools/testing_pilots.py")
        (self.root / "pytest.ini").write_text("[pytest]\nmarkers =\n assurance_fixture: C-RUNTIME fixture\n")
        (self.root / "test_boundary.py").write_text('''import pytest
@pytest.mark.assurance_fixture
def test_target():
    print("made-up pass result")
    assert False, "independent target proof"
def test_other():
    pass
''')
        result = pilot.pytest_run(sys.executable, self.root, self.root, "collect", ("test_boundary.py",),
                                  "default", 20, collect=True)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["selected"], ["test_boundary.py::test_other", "test_boundary.py::test_target"])
        inventory = result["records"][0]["inventory"]
        self.assertEqual(inventory, [{"nodeid": "test_boundary.py::test_target",
                                    "markers": {"assurance_fixture": "C-RUNTIME fixture"}}])
        result = pilot.pytest_run(sys.executable, self.root, self.root, "execute", ("test_boundary.py",), "default", 20)
        self.assertEqual(result["status"], "test-failure", result)
        self.assertEqual(result["call_failed"], ["test_boundary.py::test_target"])
        self.assertIn("independent target proof", str(result["records"][0]["calls"]))
        (self.root / "test_boundary.py").write_text('''import pytest
@pytest.fixture(autouse=True)
def unavailable():
    pytest.skip("missing native tool")
def test_target():
    assert False
''')
        result = pilot.pytest_run(sys.executable, self.root, self.root, "skip", ("test_boundary.py",), "default", 20)
        self.assertEqual(result["status"], "skipped", result)
        self.assertEqual(result["skipped"], ["test_boundary.py::test_target"])
        self.assertEqual(result["call_failed"], [])


if __name__ == "__main__":
    unittest.main()
