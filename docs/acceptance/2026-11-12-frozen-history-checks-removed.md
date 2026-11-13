---
owner: lead
status: historical
date: '2026-11-12'
scope: 'Removal of the acceptance-manifest check and the hand-table cross-check on the owner''s decision of 12 November 2026; the run ledger is the one numeric record of a run (#556)'
---

# Frozen-history checks removed, 12 November 2026

The [control review](2026-11-12-control-review-and-names.md#left-for-the-owner) of
12 November 2026 left seven smaller control candidates for the owner in
[#556](https://github.com/CVX-Hull/enactive/issues/556). The owner decided two of them
the same day: remove the two checks below. Both validated files or records that never
change, so each could fail only on an accidental edit, which the diff and review
already show. Neither served a current risk in the [risk register](../risks.md). The
[control rule](../standards/authority.md#control-review) names this trigger: "the work
it protected is finished".

| Removed | What it did | Why it had nothing left to protect |
| --- | --- | --- |
| The acceptance-manifest check: `check_manifests` in `tools/documents.py`, `schemas/acceptance-manifest.schema.json` and three tests | Validated every `docs/acceptance/*-manifest.json` against the schema and checked its report, upstream-pin and artifact paths | All 41 manifests date from 17 to 19 October 2026 and are not edited |
| The hand-table cross-check: `cross_check`, `hand_rows`, `HAND_TABLES` and their helpers in `tools/run_ledger.py`, one test and one assertion | Compared attempts, dollars and wall seconds in the hand-scored tables of four study records with the run ledger | The four studies are closed and their tables are never rewritten; a new study keeps no hand table |

The 41 manifest files and the four records' hand tables
([development loop](2026-11-06-development-loop.md),
[long-horizon arm](2026-11-07-long-horizon-382.md),
[seven-day lineage](2026-11-07-seven-day-397.md) and
[added held-out lineage](2026-11-09-held-out-lineage-522.md)) are unchanged. On main at
`4784cb4`, the last commit with the cross-check, `python -m tools.run_ledger check`
reported the hand tables consistent with the ledger.

## Rule for new studies

The run ledger (`data/evaluation/runs.jsonl`) is the one numeric record of a run. A
dated record presents numbers through the generated run tables or by citing the
ledger, and keeps no second hand-typed copy of attempts, spend or duration. A short
issue comment may announce a run and link its ledger row. The rule is stated in
[evidence cadence](../workflows/evidence-cadence.md),
[development runs](../development-runs.md#recording-a-run),
[S-EVIDENCE](../standards/evidence.md), the
[campaign procedure](../operations/campaign-run.md#start-and-close),
[operator permissions](../operator-permissions.md#finite-gameplay-budget-delegation) and the
[evaluation contract](../contracts/evaluation.md#tracked-run-ledger-and-metrics-snapshot).

## What still covers the risks

- `python -m tools.run_ledger check` validates every ledger row: its schema, a
  repeated run or session, and the spend identity.
- `python -m tools.evaluate evaluate-table … --check` fails a generated run table that
  differs from the metrics snapshot joined to the ledger.
- The link check fails a record whose link to a manifest, report or other record no
  longer resolves.
- Git history and review show any edit to a manifest or a hand table.

The [controls page](../controls.md) needed no change: the C-DOCUMENTS row named neither
removed check.

## Checks run

On the change, in a worktree of main at `4784cb4`, on macOS: `python tools/check.py --fast`
passed, including the document check, the ledger check (52 rows valid) and the
generated run tables (current). `python -m pytest -q -n 4 tests` gave 1005 passed and
8 skipped, after four test functions were removed with the checks. No game was
launched and no paid call was made.

## Limits

- The generated run tables hold the evaluator's headline metrics. They do not hold
  attempts, spend or wall seconds, so a figure a record cites from the ledger in prose
  is not compared with the ledger by any check.
- `local_reference` in `tools/documents.py` lost its `exists` option, which only the
  manifest check used. `schema_errors` is kept; the metadata check uses it.
