---
owner: lead
review_trigger: Changes to tools/run_ledger.py, evaluate-table in tools/evaluate.py or the dev-run and run-metrics schemas
status: active
---

# Run ledger and metrics snapshot

This contract covers the tracked development-run ledger, the metrics snapshot and the tables rendered from them.

## Tracked run ledger and metrics snapshot

Development-run quantities live as data in git, and pages render them or cite them
(S-EVIDENCE). Both files hold no local paths, ports or secrets.

| File | Format | Written by |
| --- | --- | --- |
| `runs.jsonl` | One [`dev-run/3`](../../schemas/dev-run.schema.json) row per admission: study issue, run, label (the run's short name in its study's dated record), arm, start, lineage, admission, session, source commit, UTC end, receipt outcome, observed attempts for current runs, wall seconds, and spend as decimal strings | `tools/run_ledger.py record`, from the package's `campaign-run/10` manifest and `campaign-receipt/7` alone |
| `run-metrics.jsonl` | One [`run-metrics/1`](../../schemas/run-metrics.schema.json) row per session and evaluator core and binding version: the headline metric values, copied verbatim from the evaluation record | `tools/evaluate.py evaluate-table RECORDS --snapshot data/evaluation/run-metrics.jsonl` |

- **Origin.** `record` accepts the current `campaign-run/10` and
  `campaign-receipt/7` pair. It copies the receipt's provider subtotal,
  observed attempts and unpriced player and recall counts. Incomplete traces
  preserve the observed starts as a lower bound. A complete trace has basis
  `provider-reported` and equal `spend_usd` and `provider_usd`. The per-attempt
  charge fields are null for current rows. On a complete trace the unpriced
  count describes observed attempts with an unknown charge.
- **Incomplete trace.** `--record-upper-bound` records the observed subtotal
  and counts under basis `incomplete-trace`. The separate
  `spend_upper_bound_usd` is a planning amount for admission. It uses the
  larger of the declared limit and observed subtotal, plus allowances for
  possible in-flight attempts. Ledger totals show the provider subtotal and
  the admission amounts separately. See the
  [campaign procedure](../operations/campaign-run.md#start-and-close).
- **Historical basis.** Rows with basis `historical` hold the original counted totals
  and any original split, with a null `spend_upper_bound_usd`. Their totals may include
  per-attempt bounds or configured estimates.
- **Rejection.** A row without `schema: dev-run/3`, a schema violation (a label is required),
  a repeated study and run, a repeated session, more combined player and recall unpriced attempts than recorded attempts, or an
  inconsistent spend split is an error naming the line. Snapshot rows are validated against
  their schema when read and before they are written.
- **Generated tables.** A `<!-- evaluate-table study=N [lineage=L] core=C binding=ID:V -->` …
  `<!-- /evaluate-table -->` block is the table of the snapshot rows for that study (and
  lineage), joined to the ledger on session, at those versions. Markers are whole lines and
  blocks do not nest; mismatched or malformed markers are an error before anything is
  written. `evaluate-table … --write` regenerates the blocks, and the fast checks run
  `--check`, which fails on a stale block.
- **One numeric record.** The ledger is the one numeric record of a run. A dated record
  presents numbers through generated tables or by citing the ledger, and keeps no second
  hand-typed copy of attempts, spend or duration. `run_ledger check`, part of the fast
  checks, validates every ledger row; it reads no document. Four study records keep
  hand-scored tables (the [development loop](../acceptance/2026-11-06-development-loop.md),
  the [long-horizon arm](../acceptance/2026-11-07-long-horizon-382.md), the
  [seven-day lineage](../acceptance/2026-11-07-seven-day-397.md) and the
  [added held-out lineage](../acceptance/2026-11-09-held-out-lineage-522.md)); those tables
  are never rewritten (ADR008) and are not checked.
