#!/usr/bin/env python3
"""Opt-in assurance inventory and finite, archived pytest-testmon experiment.

No production CI selection. See the verification-pilots design and docs/testing.md.
Selection is observed through public pytest hooks, never inferred from stdout.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = "tests/test_player_view.py::DecisionViewTests::"
MEMORY = "tests/test_campaign_memory.py::CampaignMemoryTests::"
CONTROLLER = "tests/test_controller.py::ControllerTests::"
GOVERNANCE = "tests/test_governance.py::GovernanceTests::test_registry_fixture_is_valid_at_record_date"
NATIVE = "tests/test_native_receiver.py::NativeReceiverTests::test_wire_and_live_publication_contract"
BOUNDARY = "tests/_verification_boundaries.py::BoundaryTests::"
COHORT = (
    CONTEXT + "test_context_projects_only_binding_slots_not_claims_procedures_or_other_tools",
    CONTEXT + "test_projection_never_mutates_or_aliases_full_result_or_handle_cache",
    MEMORY + "test_durable_forward_or_cyclic_support_is_rejected_without_projection",
    MEMORY + "test_newest_loss_never_resurrects_old_stock_after_sqlite_reopen",
    CONTROLLER + "test_nonimage_mission_resume_preserves_original_capture_across_render_churn",
    CONTROLLER + "test_leased_preflight_rejects_changed_session_revision_or_boundary",
    GOVERNANCE, NATIVE,
    BOUNDARY + "test_viewer", BOUNDARY + "test_exports", BOUNDARY + "test_subprocess",
)
SUPPLEMENTAL = {
    "pilot_subject/__init__.py": '__all__ = ["available"]\navailable = True\n',
    "pilot_subject/helper.py": 'print("ok")\n',
    "tests/_verification_boundaries.py": '''"""Supplemental boundaries; no actual game or package-upgrade qualification."""
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import pilot_subject

ROOT = Path(__file__).resolve().parents[1]

class BoundaryTests(unittest.TestCase):
    def test_exports(self):
        self.assertIn("available", pilot_subject.__all__)

    def test_subprocess(self):
        result = subprocess.run([sys.executable, str(ROOT / "pilot_subject/helper.py")],
                                capture_output=True, text=True, timeout=10, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "ok\\n")

    def test_viewer(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js unavailable: viewer boundary unqualified")
        result = subprocess.run([node, "tests/test_viewer.cjs"], cwd=ROOT,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
''',
}


@dataclass(frozen=True)
class Seed:
    name: str
    path: str
    before: str
    after: str
    target: str
    fidelity: str


SEEDS = (
    Seed("context-copy", "harness/player_view.py", "view = deepcopy(value)", "view = value",
         COHORT[1], "real Python defensive-copy function; no game"),
    Seed("memory-forward", "harness/gameplay/campaign_memory.py", "if not parents <= seen:", "if False:",
         COHORT[2], "real Python durable-dependency function; fixture ledger"),
    Seed("capture-binding", "harness/controller.py", 'frame=observed["frame"], require_exact_frame=kind !=',
         'frame=self.state["frame"], require_exact_frame=kind !=', COHORT[4], "real Python input metadata; no game"),
    Seed("registry-owner", "docs/control-registry.json", "", "", GOVERNANCE,
         "real schema/governance non-Python input"),
    Seed("native-wire", "native/cdda_harness.cpp", 'out.member( "protocol", 6 );',
         'out.member( "protocol", 5 );', NATIVE, "real C++ source-reading oracle with compiled fixture; no native app"),
    Seed("viewer-protocol", "web/app.js", "state?.protocol !== 6", "state?.protocol !== 7",
         COHORT[8], "pytest subprocess wrapper around actual Node oracle; wrapper selection only"),
    Seed("package-reexport", "pilot_subject/__init__.py", '__all__ = ["available"]', '__all__ = []',
         COHORT[9], "constructed module/import/re-export fixture"),
    Seed("subprocess-helper", "pilot_subject/helper.py", 'print("ok")', 'print("wrong")',
         COHORT[10], "constructed Python subprocess dependency; no package upgrade"),
)


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


class Recorder:
    """Small public-hook adapter; each xdist process writes its own evidence."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.data = {"selected": [], "deselected": [], "unidentified_deselections": 0,
                     "calls": [], "skips": [], "errors": [], "warnings": [], "inventory": []}

    def pytest_warning_recorded(self, warning_message, when, nodeid, location):
        category = warning_message.category
        self.data["warnings"].append({"category": category.__module__ + "." + category.__qualname__,
            "message": str(warning_message.message), "when": when, "nodeid": nodeid})

    def pytest_collection_finish(self, session):
        self.data["selected"] = sorted(item.nodeid for item in session.items)
        descriptions = dict(line.split(":", 1) for line in session.config.getini("markers") if ":" in line)
        for item in session.items:
            markers = sorted({mark.name for mark in item.iter_markers() if mark.name.startswith("assurance_")})
            if markers:
                self.data["inventory"].append({"nodeid": item.nodeid,
                    "markers": {name: descriptions.get(name, "").strip() for name in markers}})

    def pytest_deselected(self, items):
        # testmon 2.2.0 reports database-only deselections as synthetic objects
        # without nodeid. Preserve their count; do not invent test identities.
        for item in items:
            nodeid = getattr(item, "nodeid", None)
            if nodeid is None:
                self.data["unidentified_deselections"] += 1
            else:
                self.data["deselected"].append(nodeid)

    def pytest_collectreport(self, report):
        if report.failed:
            self.data["errors"].append({"nodeid": report.nodeid, "phase": "collection", "detail": str(report.longrepr)})

    def pytest_runtest_logreport(self, report):
        if report.skipped:
            self.data["skips"].append({"nodeid": report.nodeid, "phase": report.when, "detail": str(report.longrepr)})
        if report.when == "call":
            self.data["calls"].append({"nodeid": report.nodeid, "outcome": report.outcome,
                                       "detail": str(report.longrepr) if report.failed else None})
        elif report.failed:
            self.data["errors"].append({"nodeid": report.nodeid, "phase": report.when, "detail": str(report.longrepr)})

    def pytest_sessionfinish(self, session, exitstatus):
        self.data["exitstatus"] = int(exitstatus)
        write_json(self.directory / f"hooks-{os.getpid()}.json", self.data)


RUNNER = """import sys, pytest
from pathlib import Path
from tools.testing_pilots import Recorder
raise SystemExit(pytest.main(sys.argv[2:], plugins=[Recorder(Path(sys.argv[1]))]))
"""


def clean_environment(root: Path, backend: str) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("PYTEST_", "COVERAGE_", "TESTMON_")) and key not in
           ("PYTHONPATH", "PYTHONHOME", "PYTHONPYCACHEPREFIX", "PYTHONSTARTUP")}
    env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(root), TESTMON_DATAFILE=str(root / ".testmondata"))
    if backend == "ctrace":
        env["COVERAGE_CORE"] = "ctrace"
    return env


def command(command: list[str], cwd: Path, directory: Path, env: dict[str, str], timeout: float) -> dict:
    directory.mkdir()
    started = time.perf_counter()
    timed_out = False
    with (directory / "stdout.txt").open("w") as stdout, (directory / "stderr.txt").open("w") as stderr:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            # Also kill descendants after the parent exits: workers may ignore TERM.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            code = process.wait()
    records = [json.loads(path.read_text()) for path in sorted(directory.glob("hooks-*.json"))]
    data = {"command": command, "cwd": str(cwd), "returncode": code, "timeout": timed_out,
            "seconds": time.perf_counter() - started, "records": records,
            "selected": sorted({node for record in records for node in record["selected"]}),
            "call_failed": sorted({call["nodeid"] for record in records for call in record["calls"] if call["outcome"] == "failed"}),
            "call_passed": sorted({call["nodeid"] for record in records for call in record["calls"] if call["outcome"] == "passed"}),
            "skipped": sorted({skip["nodeid"] for record in records for skip in record["skips"]}),
            "errors": [error for record in records for error in record["errors"]]}
    data["warnings"] = [warning for record in records for warning in record["warnings"]]
    # Coverage.py documents that sysmon cannot provide testmon's dynamic contexts.
    # Preserve the warning and refuse to qualify that map, even if tests passed.
    data["mapping_warnings"] = [warning for warning in data["warnings"]
        if warning["category"].startswith("coverage.") and "(no-sysmon-context)" in warning["message"]]
    # xdist's coordinator does not own collected items; actual call reports also
    # provide exact node IDs, including setup failures reported above.
    data["selected"] = sorted(set(data["selected"]) | set(data["call_failed"]) | set(data["call_passed"]) |
                              set(data["skipped"]) | {error["nodeid"] for error in data["errors"] if error["phase"] != "collection"})
    data["status"] = status(data)
    write_json(directory / "result.json", data)
    return data


def status(result: dict) -> str:
    if result["timeout"]:
        return "timeout"
    if result["errors"]:
        return result["errors"][0]["phase"] + "-error"
    if result.get("mapping_warnings"):
        return "mapping-unqualified"
    if result["returncode"] not in (0, 1, 5) or not result["records"]:
        return "execution-error"
    if result["call_failed"]:
        return "test-failure" if result["returncode"] == 1 else "execution-error"
    if result["returncode"] == 5 and not result["selected"]:
        return "no-selection"
    if result["returncode"] != 0:
        return "execution-error"
    return "skipped" if result["skipped"] else "passed"


def judge(confirmation: dict, selected: dict, target: str) -> str:
    if confirmation["status"] != "test-failure" or target not in confirmation["call_failed"]:
        return "unconfirmed"
    if selected["status"] not in ("test-failure", "passed", "no-selection"):
        return "unqualified"
    return "detected" if target in selected["call_failed"] else "miss"


def new_output(root: Path, requested: Path) -> Path:
    output = requested.resolve()
    if not output.is_relative_to(root.resolve()) or output == root.resolve():
        raise ValueError("--out must be a new directory inside the project")
    if ".git" in output.relative_to(root.resolve()).parts:
        raise ValueError("--out cannot be inside Git metadata")
    # mkdir's exclusive contract refuses an existing or symlinked output.
    output.mkdir(parents=True, exist_ok=False)
    return output


def restore_source(pristine: Path, work: Path) -> None:
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(pristine, work, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))


def backup_map(source: Path, destination: Path) -> None:
    for suffix in ("", "-wal", "-shm", "-journal"):
        destination.with_name(destination.name + suffix).unlink(missing_ok=True)
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original, sqlite3.connect(destination) as copy:
        original.backup(copy)


def mutate(root: Path, seed: Seed) -> dict:
    path = root / seed.path
    original = path.read_text()
    if seed.name == "registry-owner":
        data = json.loads(original)
        owner = data["controls"][0]["owner"]
        if not isinstance(owner, str) or not owner:
            raise ValueError("inapplicable registry-owner: first owner is not a nonempty string")
        data["controls"][0]["owner"] = ""
        modified = json.dumps(data, indent=2) + "\n"
    else:
        count = original.count(seed.before)
        if count != 1:
            raise ValueError(f"inapplicable {seed.name}: expected one exact anchor, found {count}")
        modified = original.replace(seed.before, seed.after, 1)
    path.write_text(modified)
    return {"path": seed.path, "before_sha256": hashlib.sha256(original.encode()).hexdigest(),
            "after_sha256": hashlib.sha256(modified.encode()).hexdigest()}


def pytest_run(python: str, work: Path, output: Path, label: str, nodes: tuple[str, ...],
               backend: str, timeout: float, plugin: str | None = None, workers: int = 0,
               collect: bool = False) -> dict:
    directory = output / label
    args = [python, "-c", RUNNER, str(directory), "-q", "--strict-markers", "-o", "addopts=", "-p", "no:cacheprovider"]
    if plugin:
        args += ["-p", plugin, "--testmon-forceselect"]
    if workers:
        args += ["-p", "xdist.plugin", "-n", str(workers), "--max-worker-restart=0"]
    if collect:
        args.append("--collect-only")
    args.extend(nodes)
    return command(args, work, directory, clean_environment(work, backend), timeout)


def trace(args) -> int:
    output = new_output(ROOT, args.out)
    result = pytest_run(str(Path(sys.executable)), ROOT, output, "collection", tuple(args.nodes or ["tests"]),
                        "default", args.timeout, collect=True)
    registry = json.loads((ROOT / "docs/control-registry.json").read_text())
    controls = {control["id"] for control in registry["controls"]}
    inventory = [item for record in result["records"] for item in record["inventory"]]
    for item in inventory:
        references = {reference for description in item["markers"].values()
                      for reference in re.findall(r"\bC-[A-Z-]+\b", description)}
        item["controls"] = sorted(references & controls)
        item["unknown_controls"] = sorted(references - controls)
    write_json(output / "trace.json", {"inventory": sorted(inventory, key=lambda item: item["nodeid"]),
               "collection": result, "limits": "Collected markers/descriptions and registry IDs only; no semantic coverage claim."})
    return 0 if result["status"] == "passed" else 1


def evaluate(args) -> int:
    if subprocess.run(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT,
                      capture_output=True, text=True, check=True, timeout=10).stdout:
        raise ValueError("evaluate requires a clean committed source checkout")
    python = str(args.python.absolute())  # Preserve venv executable symlinks.
    if not args.python.is_file():
        raise ValueError("--python must name the isolated environment's Python executable")
    output = new_output(ROOT, args.out)
    started = time.perf_counter()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                            text=True, check=True, timeout=10).stdout.strip()
    report = {"source_commit": commit, "python": python, "backend": args.backend, "workers": args.workers,
              "cohort": COHORT, "seeds": [], "recipe": [asdict(seed) for seed in SEEDS], "supplemental": SUPPLEMENTAL,
              "limits": ["Cohort-only, single measurements; whole-repository cost/recall unknown.",
                         "No actual game/native app or dependency-upgrade qualification.",
                         "Viewer credit is only selected pytest wrapper invoking the actual Node oracle."]}
    write_json(output / "report.json", report)
    archive = output / "source.tar"
    with archive.open("wb") as stream:
        subprocess.run(["git", "archive", commit], cwd=ROOT, stdout=stream, check=True, timeout=30)
    pristine = output / "pristine"
    pristine.mkdir()
    with tarfile.open(archive) as source:
        source.extractall(pristine, filter="data")
    for name, text in SUPPLEMENTAL.items():
        path = pristine / name
        if path.exists():
            raise ValueError(f"supplemental path already exists: {name}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    work = output / "work"
    restore_source(pristine, work)
    # Query the installed distribution's public entrypoint, not a guessed module.
    probe = command([python, "-c", '''import importlib.metadata as m, json, platform, sys
dist = m.distribution("pytest-testmon")
entries = [entry.value for entry in dist.entry_points if entry.group == "pytest11"]
assert len(entries) == 1, entries
print(json.dumps({"entrypoint": entries[0], "python": sys.version, "platform": platform.platform(),
"packages": {name: m.version(name) for name in ("pytest", "pytest-testmon", "coverage")}}))
'''], work, output / "environment", clean_environment(work, args.backend), args.timeout)
    if probe["returncode"] != 0 or probe["timeout"]:
        report["error"] = "isolated pytest-testmon environment probe failed; original output retained"
        write_json(output / "report.json", report)
        return 1
    environment = json.loads((output / "environment/stdout.txt").read_text())
    report["environment"] = environment
    plugin = environment["entrypoint"]
    def run(label, nodes=COHORT, instrument=False):
        return pytest_run(python, work, output, label, nodes, args.backend, args.timeout,
                          plugin if instrument else None, args.workers)
    report["plain"] = run("plain")
    restore_source(pristine, work)
    report["cold"] = run("cold", instrument=True)
    valid = lambda result: result["status"] == "passed" and set(result["call_passed"]) == set(COHORT)
    map_path = work / ".testmondata"
    qualified = valid(report["plain"]) and valid(report["cold"]) and map_path.is_file()
    if qualified:
        backup_map(map_path, output / "pristine-map.sqlite")
        report["map_bytes"] = (output / "pristine-map.sqlite").stat().st_size
        restore_source(pristine, work)
        backup_map(output / "pristine-map.sqlite", map_path)
        report["warm"] = run("warm", instrument=True)
        for seed in SEEDS:
            # Same stable path, no cumulative source, generated state, bytecode or map learning.
            restore_source(pristine, work)
            backup_map(output / "pristine-map.sqlite", map_path)
            item = {"seed": asdict(seed)}
            try:
                item["mutation"] = mutate(work, seed)
            except ValueError as error:
                item.update(verdict="inapplicable", error=str(error))
                report["seeds"].append(item)
                continue
            map_hash = hashlib.sha256(map_path.read_bytes()).hexdigest()
            item["confirmation"] = run(seed.name + "-confirmation", (seed.target,))
            if hashlib.sha256(map_path.read_bytes()).hexdigest() != map_hash:
                raise ValueError("ordinary confirmation unexpectedly changed the selected map")
            # Also discard confirmation's generated files before selection.
            restore_source(pristine, work)
            backup_map(output / "pristine-map.sqlite", map_path)
            mutate(work, seed)
            item["selected"] = run(seed.name + "-selected", instrument=True)
            item["verdict"] = judge(item["confirmation"], item["selected"], seed.target)
            report["seeds"].append(item)
            write_json(output / "report.json", report)
    else:
        report["error"] = "plain/cold cohort or pristine map unqualified; no seed comparisons claimed"
    verdicts = [item["verdict"] for item in report["seeds"]]
    report["counts"] = {key: verdicts.count(key) for key in ("detected", "miss", "unqualified", "unconfirmed", "inapplicable")}
    report["valid_comparisons"] = verdicts.count("detected") + verdicts.count("miss")
    report["planned_comparisons"] = len(SEEDS)
    report["full_seconds"] = time.perf_counter() - started
    report["retained_bytes"] = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    write_json(output / "report.json", report)
    return 0 if qualified and len(verdicts) == len(SEEDS) and all(value in ("detected", "miss") for value in verdicts) else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    inventory = commands.add_parser("trace", help="Collect actual assurance markers without executing tests")
    inventory.add_argument("nodes", nargs="*")
    experiment = commands.add_parser("evaluate", help="Finite cohort experiment; never changes production selection")
    experiment.add_argument("--python", type=Path, required=True)
    experiment.add_argument("--backend", choices=("default", "ctrace"), required=True)
    experiment.add_argument("--workers", type=int, choices=range(0, 5), default=0)
    for subparser in (inventory, experiment):
        subparser.add_argument("--out", type=Path, required=True, help="New project-local output directory")
        subparser.add_argument("--timeout", type=float, default=120, help="Finite seconds per command (max 600)")
    args = parser.parse_args(argv)
    if not 0 < args.timeout <= 600:
        parser.error("--timeout must be greater than zero and at most 600 seconds")
    try:
        return trace(args) if args.mode == "trace" else evaluate(args)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Pilot failed (original outputs retained): {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
