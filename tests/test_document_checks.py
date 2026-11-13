"""C-DOCUMENTS negative cases on isolated fixtures: the data rule, and the
risk IDs that controls and current pages name."""
import json
from pathlib import Path

from tools import documents

ROOT = Path(__file__).resolve().parents[1]


def test_the_data_rule_needs_a_reader_and_a_defined_schema(tmp_path):
    root = tmp_path
    for directory in ("schemas", "docs/contracts", "tools", "data/area/runs", "docs/acceptance/assets/x"):
        (root / directory).mkdir(parents=True)
    (root / "docs/contracts/c.md").write_text("Rows are `known-shape/1`, `big-run/12` and `xrun/1`.\n")
    (root / "tools/reader.py").write_text("RUNS = ROOT / 'data' / 'area' / 'runs'\nPRICES = 'prices.json'\n")
    (root / "data/area/runs/r1.jsonl").write_text("{}\n")        # read through its directory
    (root / "data/area/prices.json").write_text('{"schema": "known-shape/1"}')  # read by name; a contract names it
    assert documents.check_data(root) == []
    (root / "data/area/orphan.json").write_text("{}")             # data/area alone is not a reader
    assert "data/area/orphan.json: no code or test reads it" in "\n".join(documents.check_data(root))
    (root / "data/area/orphan.json").unlink()
    # Only whole tokens in schemas, contracts or code define an id: not a substring, not a run log.
    (root / "docs/log.md").write_text("A run/1 happened.\n")
    for undefined in ("run/1", "shape/1", "big-run/1", "one-off-summary/1"):
        (root / "data/area/prices.json").write_text(json.dumps({"schema": undefined}))
        assert "is defined by no schema file" in "\n".join(documents.check_data(root)), undefined
    # A dated record's asset is defined by its record.
    (root / "data/area/prices.json").write_text('{"schema": "known-shape/1"}')
    (root / "docs/acceptance/assets/x/summary.json").write_text('{"schema": "one-off-summary/1"}')
    assert documents.check_data(root) == []


def test_the_cache_diagnosis_figures_match_their_schema():
    path = ROOT / "data/curator/cache-diagnosis-489.json"
    assert documents.schema_errors(ROOT, "curator-cache-diagnosis", json.loads(path.read_text()), str(path)) == []


def test_a_control_names_a_risk_and_current_pages_name_only_registered_risks(tmp_path):
    front = "---\nowner: lead\nstatus: {}\n---\n\n"
    (tmp_path / "docs").mkdir()
    risks, controls = tmp_path / "docs/risks.md", tmp_path / "docs/controls.md"
    risks.write_text(front.format("active") + "| R-KEY-LEAK | The key leaks |\n| R-OVERSPEND | Too much is spent |\n")
    controls.write_text(front.format("active") + "| C-SECRETS | runtime | R-KEY-LEAK | Keeps the key in one process |\n")
    assert documents.check_risks(tmp_path) == []
    controls.write_text(controls.read_text() + "| C-SPARE | manual | none yet | Does something |\n")
    assert documents.check_risks(tmp_path) == ["docs/controls.md: C-SPARE names no risk"]
    controls.write_text(controls.read_text().replace("none yet", "R-IMAGINED"))
    assert documents.check_risks(tmp_path) == ["docs/controls.md: R-IMAGINED is not in the risk register"]
    (tmp_path / "docs/old.md").write_text(front.format("historical") + "R-RETIRED was a risk once.\n")
    controls.write_text(controls.read_text().replace("R-IMAGINED", "R-OVERSPEND") + "| C-SECRETS | runtime | R-KEY-LEAK | x |\n")
    risks.write_text(risks.read_text() + "| R-KEY-LEAK | Again |\n")
    assert documents.check_risks(tmp_path) == ["docs/risks.md: R-KEY-LEAK is defined more than once",
                                               "docs/controls.md: C-SECRETS is listed more than once"]


def test_the_repository_register_and_controls_agree():
    assert documents.check_risks(ROOT) == []


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
