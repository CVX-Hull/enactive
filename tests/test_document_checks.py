"""C-DOCUMENTS negative cases on isolated fixtures: acceptance manifests, evidence schema ids, and the
standard, principle and control identifiers."""
import copy
import json
from pathlib import Path
import re
import shutil

import pytest

from tools import documents

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "docs/acceptance/2026-10-17-mvp-manifest.json"


def copy_files(root, names):
    for name in sorted(names):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)


@pytest.fixture
def manifest_root(tmp_path):
    manifest = json.loads((ROOT / MANIFEST).read_text())
    copy_files(tmp_path, {MANIFEST, "schemas/acceptance-manifest.schema.json",
                          manifest["report"], manifest["upstream_pin"]})
    assert documents.check_manifests(tmp_path) == []  # no .runtime tree: a fresh-clone contract
    return tmp_path


def write(root, data):
    (root / MANIFEST).write_text(json.dumps(data))


def test_manifest_rejects_bad_provenance_hash_and_paths(manifest_root):
    original = json.loads((manifest_root / MANIFEST).read_text())
    for field, value in (("source_commit", "unknown"), ("source_sha256", "x" * 64), ("date", "2026-02-30"),
                         ("platform", ""), ("report", "../outside.md"), ("schema_version", True)):
        write(manifest_root, {**copy.deepcopy(original), field: value})
        assert documents.check_manifests(manifest_root), field
    for artifact in ("../outside.png", "/tmp/frame.png", "docs/../frame.png"):
        write(manifest_root, {**copy.deepcopy(original),
                              "artifacts": {artifact: next(iter(original["artifacts"].values()))}})
        assert "artifact" in "\n".join(documents.check_manifests(manifest_root)), artifact


def test_still_frame_acceptance_needs_no_fabricated_video(manifest_root):
    data = json.loads((manifest_root / MANIFEST).read_text())
    write(manifest_root, {**data, "video": None})
    assert documents.check_manifests(manifest_root) == []
    for invalid in ({}, "none", {"capture_interval_ms": [0, 1]}):
        write(manifest_root, {**data, "video": invalid})
        assert documents.check_manifests(manifest_root), invalid


def test_manifest_rejects_invalid_artifact_metadata(manifest_root):
    original = json.loads((manifest_root / MANIFEST).read_text())
    for field, value in (("sha256", "a" * 63), ("bytes", True), ("bytes", -1), ("availability", "verified")):
        data = copy.deepcopy(original)
        next(iter(data["artifacts"].values()))[field] = value
        write(manifest_root, data)
        assert "artifacts" in "\n".join(documents.check_manifests(manifest_root)), (field, value)


def test_evidence_schema_ids_must_be_defined_or_listed_exactly(tmp_path):
    root = tmp_path
    (root / "schemas").mkdir()
    (root / "docs/acceptance/assets/x").mkdir(parents=True)
    (root / "docs/acceptance/2026-01-01-x.md").write_text("Record.\n")
    (root / "docs/contracts").mkdir()
    (root / "docs/contracts/c.md").write_text("Rows are `known-shape/1`.\n")
    evidence = root / "docs/acceptance/assets/x/summary.json"
    registry = root / documents.EVIDENCE_IDS
    registry.write_text(json.dumps({"ids": {}}))
    evidence.write_text(json.dumps({"schema": "known-shape/1"}))
    assert documents.check_evidence_ids(root) == []  # a contract names it
    evidence.write_text(json.dumps({"schema": "one-off-summary/1"}))
    assert "defined nowhere" in "\n".join(documents.check_evidence_ids(root))
    # Only whole tokens in schemas, contracts or code define an id: not a substring, not a run log.
    (root / "docs/contracts/c.md").write_text("Rows are `known-shape/1`, `big-run/12` and `xrun/1`.\n")
    (root / "docs/log.md").write_text("A run/1 happened.\n")
    for undefined in ("run/1", "shape/1", "big-run/1"):
        evidence.write_text(json.dumps({"schema": undefined}))
        assert "defined nowhere" in "\n".join(documents.check_evidence_ids(root)), undefined
    evidence.write_text(json.dumps({"schema": "one-off-summary/1"}))
    entry = {"records": ["docs/acceptance/2026-01-01-x.md"], "files": ["docs/acceptance/assets/x/summary.json"]}
    registry.write_text(json.dumps({"ids": {"one-off-summary/1": entry}}))
    assert documents.check_evidence_ids(root) == []
    registry.write_text(json.dumps({"ids": {"one-off-summary/1": entry, "gone/1": entry | {"records": ["docs/none.md"]}}}))
    errors = "\n".join(documents.check_evidence_ids(root))
    assert "gone/1 lists" in errors and "missing record" in errors


@pytest.fixture
def identifier_root(tmp_path):
    copy_files(tmp_path, {"docs/charter.md", "docs/engineering.md", "docs/controls.md"})
    assert documents.check_identifiers(tmp_path) == []
    return tmp_path


def replace(root, name, before, after):
    path = root / name
    assert before in path.read_text()
    path.write_text(path.read_text().replace(before, after, 1))


def test_standards_name_only_known_principles_and_controls(identifier_root):
    replace(identifier_root, "docs/engineering.md", "Controls: C-BOUNDARY,", "Controls: C-UNKNOWN, C-BOUNDARY,")
    assert "S-ARCH: unknown control C-UNKNOWN" in documents.check_identifiers(identifier_root)
    replace(identifier_root, "docs/engineering.md", "Controls: C-UNKNOWN, C-BOUNDARY,", "Controls: C-BOUNDARY,")
    replace(identifier_root, "docs/engineering.md", "Principles: P-CHANGE,", "Principles: P-NOPE, P-CHANGE,")
    assert "S-ARCH: unknown principle P-NOPE" in documents.check_identifiers(identifier_root)


def test_every_control_serves_a_standard_and_appears_once(identifier_root):
    text = (identifier_root / "docs/controls.md").read_text()
    row = next(line for line in text.splitlines() if line.startswith("| C-VISUAL |"))
    (identifier_root / "docs/controls.md").write_text(text + row.replace("C-VISUAL", "C-SPARE") + "\n" + row + "\n")
    errors = "\n".join(documents.check_identifiers(identifier_root))
    assert "duplicate control ID" in errors and "['C-SPARE'] serve no standard" in errors


def test_mapping_lines_name_something_once_and_every_principle_is_used(identifier_root):
    original = (identifier_root / "docs/engineering.md").read_text()
    cases = (("Controls: C-BOUNDARY, C-REVIEW, C-DOCUMENTS.", "Controls: none yet.", "S-ARCH: its Controls line names none"),
             ("Principles: P-CHANGE,", "Principles: P-CHANGE, P-CHANGE,", "S-ARCH: its Principles line repeats an ID"))
    for before, after, expected in cases:
        (identifier_root / "docs/engineering.md").write_text(original.replace(before, after, 1))
        assert expected in documents.check_identifiers(identifier_root), expected
    (identifier_root / "docs/engineering.md").write_text(re.sub(r", P-GENERALITY\b|P-GENERALITY, ", "", original))
    assert "charter: principles ['P-GENERALITY'] serve no standard" in documents.check_identifiers(identifier_root)


def test_local_references_cannot_escape_through_a_symlink(tmp_path):
    root, outside = tmp_path / "repo", tmp_path / "outside"
    (root / "docs").mkdir(parents=True)
    outside.mkdir()
    (outside / "secret.md").write_text("x")
    (root / "docs" / "real.md").write_text("x")
    (root / "docs" / "linked").symlink_to(outside)
    assert documents.local_reference(root, "docs/real.md")
    for reference in ("docs/linked/secret.md", "../outside/secret.md", "/etc/passwd", "docs/missing.md", "a\\b"):
        assert not documents.local_reference(root, reference), reference


def test_the_frozen_evidence_id_list_stays_closed_until_the_data_rule_replaces_it():
    registry = json.loads((ROOT / documents.EVIDENCE_IDS).read_text())["ids"]
    assert sorted(registry) == [
        "campaign-evidence-summary/1", "capable-player-304-summary/1", "corpus320-summary/1", "diagnosis-314-summary/1",
        "effects-298-evidence/1", "grounding-300-evidence/1", "investigation-295-evidence/1", "organic-play-evidence/1",
        "request-timing-summary/1", "spectator-383-evidence/1", "useful-trials-accounting/1",
        "visual-player-302-evidence/1"]


def test_mandatory_standards_and_single_mapping_lines(identifier_root):
    replace(identifier_root, "docs/engineering.md", "## S-UX", "## S-UNEXPECTED")
    assert "mandatory standards differ" in "\n".join(documents.check_identifiers(identifier_root))
    replace(identifier_root, "docs/engineering.md", "## S-UNEXPECTED", "## S-UX")
    replace(identifier_root, "docs/engineering.md", "Controls: C-BOUNDARY, C-REVIEW, C-DOCUMENTS.",
            "Controls: C-BOUNDARY.\nControls: C-REVIEW.")
    assert "S-ARCH: needs exactly one Controls line" in documents.check_identifiers(identifier_root)
