#!/usr/bin/env python3
"""Offline evaluation/1 validation/summary. Reads evidence; writes JSON to stdout.

Use ``python -m tools.evaluate validate run.json [run2.json ...]`` or
``python -m tools.evaluate summary run.json [run2.json ...]``. No trace is skipped
on error, and no evidence files are created or overwritten. Each input is bounded
at 8 MiB; an invocation is bounded to 64 MiB and 4096 paths.
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
    parser.add_argument("command", choices=("validate", "summary"))
    parser.add_argument("paths", type=Path, nargs="+")
    arguments = parser.parse_args(argv)
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
