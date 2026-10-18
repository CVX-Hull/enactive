"""Reproduce the offline memory study; final runs require a clean source freeze.

Writes immutable project-local reports. Raw per-seed aggregates are compressed,
not silently discarded; report statistics never count dependent queries as seeds.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import gzip
import hashlib
import importlib
from itertools import product
import json
import math
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = "memory-study-v1.1"
SEEDS = {"smoke": (0,), "development": tuple(range(32)),
         "final": tuple(range(10000, 10256))}
MODULES = {"L": "lineage", "E": "evidence", "C": "retrieval", "D": "learning"}
REFERENCES = {"L": "archive_replay", "E": "dedup", "C": "exact", "D": "pooled"}
EXPECTED_ROWS_PER_SEED = {"L": 505, "E": 162, "C": 579, "D": 144}
PAIRED_METRICS = {
    "L": {"total_work", "mismatches"},
    "E": {"brier", "log_loss", "expected_regret", "realized_utility", "abstained"},
    "C": {"decision_correct", "wrong_answers", "unsupported_answers",
          "avoidable_abstentions", "retained_record_bytes", "sqlite_database_bytes",
          "latest_records_recalled"},
    "D": {"brier", "log_loss", "first16_brier", "last16_brier", "probability_error",
          "retention_error_change", "state_bytes"},
}


def encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass
class Moments:
    """Bounded online sample moments (Welford); descriptive Monte Carlo only."""
    n: int = 0
    mean: float = 0.
    m2: float = 0.
    total: float = 0.
    minimum: float = math.inf
    maximum: float = -math.inf

    def add(self, value: float) -> None:
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (value - self.mean)
        self.total += value
        self.minimum = min(self.minimum, value)
        self.maximum = max(self.maximum, value)

    def report(self, *, exact: bool = False) -> dict:
        if not self.n:
            raise ValueError("empty metric")
        return {"n_seeds": self.n, "mean": self.mean, "sum": self.total,
                "min": self.minimum, "max": self.maximum,
                "mc_half_width": (None if exact or self.n < 2 else
                                  1.96 * math.sqrt(max(0., self.m2) / (self.n-1) / self.n))}


def validate_rows(rows: list[dict], suite: str, seed: int) -> None:
    seen = set()
    if not rows:
        raise ValueError(f"empty suite {suite}")
    for row in rows:
        if set(row) != {"suite", "seed", "condition", "method", "metrics"}:
            raise ValueError("invalid row fields")
        if row["suite"] != suite or type(row["seed"]) is not int or row["seed"] != seed:
            raise ValueError("wrong suite/seed")
        if not all(type(row[k]) is str and row[k] and "\n" not in row[k]
                   for k in ("condition", "method")):
            raise ValueError("invalid condition/method")
        key = row["condition"], row["method"]
        if key in seen:
            raise ValueError(f"duplicate seed aggregate {key}")
        seen.add(key)
        metrics = row["metrics"]
        if type(metrics) is not dict or not metrics:
            raise ValueError("empty or malformed metrics")
        for name, value in metrics.items():
            if (type(name) is not str or not name or type(value) not in (int, float)
                    or not math.isfinite(value)):
                raise ValueError("nonfinite or nonnumeric metric")


def source_manifest(mode: str) -> dict:
    fixtures = json.loads((ROOT / "docs/design/memory-study-cases.json").read_text())
    if fixtures.get("protocol") != PROTOCOL:
        raise ValueError("unsupported literal-fixture protocol")
    if json.loads((ROOT / "docs/design/memory-study-matrix.json").read_text()).get("protocol") != PROTOCOL:
        raise ValueError("unsupported experiment-matrix protocol")
    paths = [*sorted((ROOT / "tools/memory_study").glob("*.py")),
             *sorted((ROOT / "tests").glob("test_memory_study*.py")),
             ROOT / "docs/design/memory-study-protocol.md",
             ROOT / "docs/design/memory-study-matrix.json",
             ROOT / "docs/design/memory-study-cases.json"]
    git = lambda *args: subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    dirty = git("status", "--porcelain", "--untracked-files=normal")
    if mode == "final" and dirty:
        raise ValueError("final collection requires a clean committed source/config freeze")
    return {"protocol": PROTOCOL, "mode": mode, "seeds": list(SEEDS[mode]),
            "git_commit": git("rev-parse", "HEAD"), "dirty": bool(dirty),
            "source_sha256": {str(path.relative_to(ROOT)): digest_file(path) for path in paths},
            "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
            "system": platform.system(), "machine": platform.machine()}


def expected_specs(suite: str) -> dict[tuple[str, str], frozenset[str]]:
    """Independent declared coverage/schema, not inferred from candidate outputs."""
    matrix = json.loads((ROOT / "docs/design/memory-study-matrix.json").read_text())
    if matrix.get("protocol") != PROTOCOL:
        raise ValueError("unsupported experiment-matrix protocol")
    result = {}
    for entry in matrix["suites"][suite]:
        axes = entry["axes"]
        metrics = frozenset(entry["metrics"]) | frozenset(
            prefix + name for prefix in entry.get("strata", ())
            for name in entry.get("stratified_metrics", ()))
        for values in product(*axes.values()):
            condition = entry["condition"].format(**dict(zip(axes, values)))
            for method in entry["methods"]:
                key = condition, method
                if key in result:
                    raise ValueError("duplicate declared comparison")
                result[key] = metrics
    if len(result) != EXPECTED_ROWS_PER_SEED[suite]:
        raise ValueError("declared matrix count disagrees with frozen protocol")
    return result


def validate_seed(rows: list[dict], suite: str, seed: int,
                  expected: dict[tuple[str, str], frozenset[str]]) -> None:
    validate_rows(rows, suite, seed)
    actual = {(r["condition"], r["method"]) for r in rows}
    if actual != set(expected):
        raise ValueError(f"declared condition/method coverage mismatch: missing={sorted(set(expected)-actual)[:3]}, unexpected={sorted(actual-set(expected))[:3]}")
    for row in rows:
        if set(row["metrics"]) != expected[(row["condition"], row["method"])]:
            raise ValueError("required metric schema mismatch")
    exact_laws(rows, suite)


def exact_laws(rows: list[dict], suite: str) -> None:
    """Stop known structural/control failures; utility losses remain valid results."""
    def require(condition: bool, message: str) -> None:
        if not condition:
            raise ValueError(f"exact-law failure: {message}")

    majority = {}
    for row in rows:
        method, condition, m = row["method"], row["condition"], row["metrics"]
        if suite == "L":
            if method in ("archive_replay", "incremental_view"):
                require(m["mismatches"] == 0 and m["correct"] == m["queries"], "L complete-method correctness")
                require(m["archive_records"] <= 64 and m["source_records"] <= 16 and m["claim_records"] <= 16, "L record bounds")
            if method == "identification_control":
                require(m["identical_visible_inputs"] == 1 and m["unique_identity_available"] == 0, "L identity ambiguity")
        elif suite == "E":
            require(m["episodes"] == 1 and m["origins"] <= 12 and m["visible_copies"] <= 192, "E input bounds")
            if method in ("dedup", "envelope"):
                require(m["replay_forecast_change"] <= 1e-12 and m["replay_decision_change"] == 0, "E duplicate invariance")
            if method == "envelope":
                require(0 <= m["lower"] <= m["upper"] <= 1 and abs(m["width"]-(m["upper"]-m["lower"])) <= 1e-12, "E envelope bounds")
                if m["model_in_class"]:
                    require(m["contains_true_model_posterior"] == 1, "E in-class posterior containment")
            else:
                require(0 <= m["forecast"] <= 1 and m["brier"] >= 0 and m["log_loss"] >= 0, "E proper score domain")
        elif suite == "C":
            if method == "same-bit":
                require(m["answer_correct"] == m["queries"] and m["retained_bits"] == 1, "C same-bit sufficiency")
                continue
            require(m["queries"] == 32 and m["retained_records"] <= 64, "C input/query bounds")
            require(sum(m[name] for name in ("answer_correct", "necessary_abstentions", "avoidable_abstentions", "unsupported_answers", "wrong_answers")) == 32, "C exhaustive outcomes")
            require(m["records_returned"] <= 32 * int(condition.rsplit("=", 1)[1]), "C working-context budget")
            if method == "exact":
                require(m["decision_correct"] == 32, "C exact recorded-answer control")
            if method.startswith("majority-depth"):
                comparable = {k: v for k, v in m.items() if k != "projection_records_visited"}
                require(majority.setdefault(condition, comparable) == comparable, "C projection idempotence")
        elif suite == "D":
            if ":phase=" in condition:
                phase = int(condition.rsplit("=", 1)[1])
                require(m["steps"] == 64 and m["observations_seen"] == 64*phase and m["window_entries"] <= 128, "D feedback budget")
            else:
                require(m["probe_actions"] == 2, "D frozen probe denominator")


def paired_rows(rows: list[dict], suite: str) -> list[dict]:
    by_condition = {}
    for row in rows:
        by_condition.setdefault(row["condition"], {})[row["method"]] = row
    paired = []
    for condition, methods in by_condition.items():
        reference = methods.get(REFERENCES[suite])
        if reference is None:
            if ((suite == "L" and condition == "identity_ambiguity")
                    or (suite == "C" and condition.startswith("same-bit;"))):
                continue
            raise ValueError("missing paired reference method")
        for name, row in methods.items():
            if row is reference:
                continue
            metrics = {key: row["metrics"][key] - reference["metrics"][key]
                       for key in sorted(PAIRED_METRICS[suite])
                       if key in row["metrics"] and key in reference["metrics"]}
            if metrics:
                paired.append({"suite": suite, "seed": row["seed"], "condition": condition,
                               "method": f"{name}-minus-{REFERENCES[suite]}", "metrics": metrics})
    return paired


def execute(mode: str, suites: tuple[str, ...], output: Path) -> dict:
    if mode not in SEEDS or not suites or len(set(suites)) != len(suites) or any(s not in MODULES for s in suites):
        raise ValueError("invalid mode/suite selection")
    output = output.resolve()
    if not output.is_relative_to((ROOT / ".runtime").resolve()):
        raise ValueError("reports must stay in project-local .runtime")
    manifest = source_manifest(mode)
    manifest["suites"] = list(suites)
    output.mkdir(parents=True, exist_ok=False)
    (output / "manifest.json").write_bytes(encoded(manifest) + b"\n")
    groups: dict[tuple[str, str, str, str], Moments] = {}
    group_seeds: dict[tuple[str, str, str], set[int]] = {}
    schemas = {}
    counts = {}
    timing = {}
    raw_path = output / "seed-aggregates.jsonl.gz"
    try:
        with raw_path.open("xb") as target:
            with gzip.GzipFile(filename="", mode="wb", compresslevel=6, fileobj=target, mtime=0) as compressed:
                for suite in suites:
                    module = importlib.import_module(f"tools.memory_study.{MODULES[suite]}")
                    start = time.monotonic()
                    counts[suite] = 0
                    declared = expected_specs(suite)
                    for seed in SEEDS[mode]:
                        rows = module.run((seed,))
                        try:
                            validate_seed(rows, suite, seed, declared)
                        except Exception:
                            # repr deliberately preserves invalid nonfinite values
                            # that cannot be written to the strict JSON report.
                            (output / f"rejected-{suite}-{seed}.txt").write_text(
                                "Rejected seed aggregates (Python repr, not report JSON):\n" + repr(rows))
                            raise
                        for kind, stream in (("absolute", rows), ("paired", paired_rows(rows, suite))):
                            for row in sorted(stream, key=lambda r: (r["condition"], r["method"])):
                                key = suite, kind, row["condition"] + "\n" + row["method"]
                                names = frozenset(row["metrics"])
                                if schemas.setdefault(key, names) != names:
                                    raise ValueError("metric schema changed between seeds")
                                group_seeds.setdefault(key, set()).add(seed)
                                for metric, value in row["metrics"].items():
                                    groups.setdefault((*key, metric), Moments()).add(value)
                                if kind == "absolute":
                                    compressed.write(encoded(row) + b"\n")
                                    counts[suite] += 1
                    timing[suite] = time.monotonic() - start
        expected = set(SEEDS[mode])
        if any(seeds != expected for seeds in group_seeds.values()):
            raise ValueError("condition/method missing a seed")
        ending = source_manifest(mode)
        if (ending["source_sha256"] != manifest["source_sha256"]
                or ending["git_commit"] != manifest["git_commit"]
                or ending["dirty"] != manifest["dirty"]):
            raise ValueError("source/config changed during collection")
        aggregate = []
        for (suite, kind, combined), seeds in sorted(group_seeds.items()):
            condition, method = combined.split("\n", 1)
            metrics = {metric: groups[(suite, kind, combined, metric)].report(exact=suite == "L")
                       for metric in sorted(schemas[(suite, kind, combined)])}
            aggregate.append({"suite": suite, "kind": kind, "condition": condition,
                              "method": method, "metrics": metrics})
        from tools.memory_study.learning import causal_control
        content = {"protocol": PROTOCOL, "mode": mode, "seeds": list(SEEDS[mode]),
                   "suites": list(suites), "row_counts": counts,
                   "causal_negative_control": causal_control(), "groups": aggregate}
        # Content excludes timings, output path and Git commit so a reviewed-doc
        # follow-up can reproduce the same data from identical hashed source files.
        encoded_content = encoded(content)
        result = {"status": "completed", "manifest": manifest,
                  "content_sha256": hashlib.sha256(encoded_content).hexdigest(),
                  "raw_sha256": digest_file(raw_path), "raw_bytes": raw_path.stat().st_size,
                  "suite_wall_seconds": timing, "content": content,
                  "limits": "Synthetic conditional results; seed-cluster descriptive Monte Carlo, no native efficacy. Timings include generation, scoring, accounting and report compression; not candidate latency."}
        (output / "report.json").write_bytes(encoded(result) + b"\n")
        return result
    except Exception as error:
        failure = {"status": "failed", "manifest": manifest,
                   "error": str(error), "traceback": traceback.format_exc()}
        (output / "failure.json").write_bytes(encoded(failure) + b"\n")
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=SEEDS, required=True)
    parser.add_argument("--suites", choices=MODULES, nargs="+", default=list(MODULES))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = execute(args.mode, tuple(args.suites), args.output_dir)
    print(json.dumps({key: result[key] for key in ("status", "content_sha256", "raw_sha256", "raw_bytes")}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Memory study failed: {error}", file=sys.stderr)
        raise SystemExit(1)
