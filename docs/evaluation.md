---
owner: maintainer
review_trigger: Evaluation schema, caller, scenario protocol or accounting changes
status: active
---

# Record and review gameplay measurements

The passive recorder measures explicitly supplied observations; it does not run
the game, call a model or judge success. Future planner/skill adapters must record
their actual calls and outcomes. External Codex/operator planning is currently
uninstrumented. An empty call list does not establish zero total cost.

The [round brief](changes/007-recovery-evaluation-monitoring.md#waypoint-experiment-protocol)
owns the predeclared waypoint families, development/held-out split, repeats,
budgets and pilot decision thresholds for #24. No live model comparison is claimed
by this tooling. Change that protocol before collecting affected outcomes, with a
recorded reason; do not tune thresholds after seeing results.

## Caller contract

Use `RunRecorder(manifest)`, `record(event)`, `finish(outcome)` and `write(path)`
from [evaluation.py](../harness/gameplay/evaluation.py). Its `run_schema()` returns
the exact JSON Schema; module documentation describes payloads. Validation adds
sequence, missingness, provenance and identity checks beyond the schema. There is
one current artifact format, `evaluation/1`; unsupported formats reject.

Capture admission monotonic time before planning or dispatch. Event `elapsed_ms`
is completion time minus admission, with a duration ending at that time. Finish
with the actual final elapsed time, including post-event waits/timeouts. Native
game turns are signed identities; turn consumption requires same-session endpoints.
Retain real `EvidenceRef` objects from the evidence store for native start/final
observations. Structural validation cannot verify frame bytes or prove a judgment.

Record one action event per primitive attempt, including rejected and uncertain
attempts; use a unique action ID and explicit dispatch state. Expand bounded walks
from their observed primitive records. Preserve partial verified progress even
when a run fails. First useful action requires known dispatch and an independently
explained judgment; delivery alone is insufficient, and useful nonmovement inputs
may have zero displacement. Missing measurements need a reason, never a fabricated
zero. Record failed model calls and their actual usage/cost; cached input is a
subset of input tokens. No private reasoning transcript belongs in these records.

Configuration identity identifies the whole declared condition, including possible
models and routing policy. Change it when that configuration changes. Summaries
group by declared family/split/lane/condition/source/native/model/configuration/
protocol identity. Session and realized call subsets are provenance: reloads and
pre-call failures stay in their cohort. Actual role/model/configuration usage is
also reported within the cohort. Do not infer that a shared label proves identical
configuration; retain the configuration and assessment evidence with each run.

`finish` seals the recorder; writes create a new file exclusively. Failed validation
does not discard prior accepted records. Bounds are 4096 events, 8 MiB per run,
4096 characters per string and 64 evidence references per list. These are evidence
bounds, not enforcement of the declared gameplay budget: the supervisor must stop
execution, and the recorder must retain any observed overrun.

## Offline review

From the project root, using project-local files:

```sh
.venv/bin/python -m tools.evaluate validate .runtime/evidence/run.json
.venv/bin/python -m tools.evaluate summary .runtime/evidence/run.json
```

Both commands accept multiple paths, reject any malformed/duplicate run rather
than skip it, and print JSON without changing evidence. CLI input is bounded to
64 MiB and 4096 files. Summaries retain unknown and budget-censored runs; report
known subtotals and missing counts, outcome coverage, progress, interventions,
harms, elapsed time, calls and median/nearest-rank p95 durations. Read coverage and
sample size before comparing totals. Synthetic fixtures test accounting only.

Maintain the schema, callers, tests and this guide together. On a format change,
preserve historical evidence and migrate active consumers as one coordinated
change; no fallback reader. Revisit missing instrumentation and independent outcome
labeling before #24/#44 trials and after any false-success or accounting incident.
