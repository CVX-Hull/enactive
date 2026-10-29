#!/usr/bin/env python3
"""Offline evidence analysis. Reads evidence; writes summaries to stdout.

Use ``python -m tools.evaluate validate run.json [run2.json ...]`` or
``python -m tools.evaluate summary run.json [run2.json ...]``. No trace is skipped
on error, and no evidence files are created or overwritten. Each input is bounded
at 8 MiB; an invocation is bounded to 64 MiB and 4096 paths.

``host-summary`` streams selected Pi JSONL files or known campaign directories;
``--format markdown`` produces a compact table. Limits: 64 MiB per line, two
million events and 200000 requests per trace, 4096 files / 8 GiB selected bytes.
``witness-summary`` joins a mission evidence index with 1–32 observer-timing/3
exports (64 MiB per metadata file). These are diagnostics, not gameplay verdicts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from harness.gameplay.contracts import ContractError
from harness.gameplay.evaluation import MAX_JSON_BYTES, MAX_RUNS, summarize_runs, validate_run

MAX_INPUT_BYTES = 64 * 1024 * 1024


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "summary", "host-summary", "witness-summary"))
    parser.add_argument("paths", type=Path, nargs="+")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    arguments = parser.parse_args(argv)
    if arguments.command in ("host-summary", "witness-summary"):
        from tools.host_analysis import host_summary, markdown
        from tools.observer_analysis import witness_summary
        try:
            if arguments.format == "markdown" and arguments.command != "host-summary":
                raise ContractError("Markdown output is supported for host-summary only")
            result = (host_summary if arguments.command == "host-summary" else witness_summary)(arguments.paths)
            print(markdown(result) if arguments.format == "markdown" else json.dumps(result, allow_nan=False, sort_keys=True))
            return 0 if result.get("complete", True) else 1
        except (ContractError, OSError, ValueError) as exc:
            print(f"Trace analysis failed: {exc}", file=sys.stderr)
            return 1
    if arguments.format != "json":
        parser.error("Existing evaluation records use JSON output")
    if len(arguments.paths) > MAX_RUNS:
        parser.error("At most 4096 run paths are supported")
    runs = []
    total_bytes = 0
    current: Path | None = None
    try:
        for current in arguments.paths:
            with current.open("rb") as stream:
                encoded = stream.read(min(MAX_JSON_BYTES, MAX_INPUT_BYTES - total_bytes) + 1)
            total_bytes += len(encoded)
            if total_bytes > MAX_INPUT_BYTES:
                raise ContractError("Invocation exceeds 64 MiB")
            runs.append(validate_run(encoded))
        # Duplicate run identities are an error in both modes.
        summary = summarize_runs(runs)
        result = summary if arguments.command == "summary" else {
            "schema": "evaluation-validation/1", "validated_runs": len(runs),
            "run_ids": [run["manifest"]["run_id"] for run in runs]}
        print(json.dumps(result, allow_nan=False, sort_keys=True))
        return 0
    except (ContractError, OSError) as exc:
        print(f"Evaluation failed ({current}): {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
