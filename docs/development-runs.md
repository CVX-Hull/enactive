---
owner: lead
review_trigger: A change to study design, start rules, admission, metrics or lineage classification
status: active
---

# Development runs: method

Each development comparison pre-registers a targeted process metric, such as
routine pace, stall length or the rate of the failure it targets. Survival,
verified improvements, setup attempts and cost are descriptive guards. See the
[evaluator re-score and power check](acceptance/2026-11-06-development-loop.md#evaluator-re-score-and-power-check-383).

The [owner decision log](decisions/owner-decisions.md) records the owner's decisions.
The [acceptance index](acceptance/index.md) lists dated records. The
[evidence cadence](workflows/evidence-cadence.md) governs recording and review.

## Benchmark

In a fresh-start arm, each run starts from a fresh project-local userdir with only
normal windowed input options. It starts without a world, save, player memory or
predecessor report.
The previous run's userdir and game log are archived, never deleted. The player
creates a normal world with default rules and its own survivor through ordinary
visible menus, then pursues indefinite survival. The lead gives no class,
traits, location, tactic, target item or hint.

| Start | Assignment difference |
| --- | --- |
| Assigned Evacuee scenario (S1) | The player uses the default **Evacuee** scenario and chooses profession, traits and stats. |
| Player-chosen scenario (S2) | The player chooses every setup option, including the scenario. |

Each comparison freezes its own route, package limits and schedule in its dated
record. The [ceiling arm](acceptance/2026-11-06-development-loop.md) ran under
[this method as it stood at `38a94c4`](https://github.com/CVX-Hull/enactive/blob/38a94c40bb60c13c3aa0ac44bb1903645214bb82/docs/development-runs.md#benchmark),
which holds its route and limits; the [long-horizon arm](acceptance/2026-11-07-long-horizon-382.md)
states its own.

**Admission rule.** A run is admitted on actual provider-reported spend under the
[budget delegation](operator-permissions.md#finite-gameplay-budget-delegation) rule.
`python -m tools.run_ledger totals --study ISSUE --envelope USD` applies it to the
tracked ledger.

## Descriptive guards

Measured by the lead from original frames and receipts; an independent reviewer
samples the claims in each arm.

- **Survival hours:** in-game time from the first in-play clock to the
  last frame showing the survivor alive, or to the death screen.
- **Status:** died, alive at stop (budget, time or context capacity
  ended the run), or player finished. Dates are UTC.
- **Verified improvements:** distinct visible changes that improve needs (thirst,
  hunger, fatigue or pain reduced), supplies (new food, water or tools confirmed
  carried) or shelter (secured and used for rest). Claims without a confirming
  frame do not count.
- **Death cause**, if shown.
- **Cost:** record the provider-returned subtotal, attempts, setup attempts (until
  the first in-play frame) and wall seconds. A settled player or recall attempt
  without a usable charge remains observed with unknown cost and adds
  nothing to the subtotal. The [campaign procedure](operations/campaign-run.md#spend-limit)
  defines the in-flight and ending allowances and the separate
  [admission amount for an incomplete trace](operations/campaign-run.md#start-and-close).
  The [owner manages provider billing](operator-permissions.md#finite-gameplay-budget-delegation).
  Generated evaluator tables report [configured-rate dollars per decision](contracts/evaluation.md#metrics-version-1).

## Day-scale survival and pacing

Over a full in-game day, check whether needs, rest and supplies hold and whether
game time per decision rises when the player chooses to sleep, wait or travel.

### Lineage classification

Each lineage gets exactly one class, checked in this order:

1. **Continuity failure:** an admission does not resume the same survivor in the same
   world, or an admission starts a new episode (`lineage.elapsed.episode_changes`).
2. **Failed:** death, or a failed day check, before 24 elapsed hours.
3. **Day-viable:** alive at 24 elapsed hours with the day check passed.
4. **Slow:** alive under 24 elapsed hours when the decision cap or a stop rule ends it.

The [evaluator's `lineage.day_check`](contracts/evaluation.md#metrics-version-1) checks
day-scale survival with no severe thirst
("very thirsty", "dehydrated", "parched"), hunger ("very hungry", "famished", "near
starving", "starving") or rest ("dead tired", "exhausted"). The lead confirms every
boundary, day point and death from frames.

## Reusable starts

`python -m tools.starts create seven-day-end-01` copies the sealed seven-day lineage's
`user/` and `player-memory-sd1.sqlite3` without editing their contents. The tool
checks every copied path and hash against `data/evidence/397-seven-day.sha256`,
refuses missing, changed or extra files, and prints the `start-manifest/2` SHA-256. The sealed source store remains historical input;
reset prepares a fresh current journal in `work/`. Unsupported old active starts refuse.
Starts live in the main checkout's `.runtime/starts/<name>/`; `list` reports their
hashes and player-store paths. A run using a start cites its manifest hash and says
that the copied lineage is no longer held out. These copies do not establish a
held-out comparison. Every start of one source is a byte-identical, hash-verified copy.
`create NAME --from STUDY` takes another sealed study as the source: one whose files
hold a saved game under `user/save/` and the player store, laid out as a lineage
(`user/` and the store at the root) or as a disposed start (`start/`, `user/`, and the
store under `start/work/` or `start/`). The start manifest records `source_study` and
`source_manifest_sha256`; the default source stays `397-seven-day`. A new source's
copies are not known to load until a load check has used one of them.
A load check is a minimal custodian run that loads the save and reads the character and
time; it uses the start up, so the starts a study plays are fresh copies of a source
whose copies have loaded ([load checks](acceptance/2026-11-14-start-load-checks.md)). The record citing a start lists its disposal
study and the userdir archive path.

With the game closed, `python -m tools.starts install NAME` stages the start, then
copies the current `.runtime/user/` into `.runtime/archive/userdir-<timestamp>/`
and verifies every file by hash before installing the staged userdir. It prints
the archive location and `player_store`: the run package points that field at the reported absolute
path, the fresh journal under `.runtime/starts/NAME/work/` in the main checkout.
The tool holds the shared game lock and checks `ps` for any executable whose
basename starts with `cataclysm`, ignoring case, before install, restore or
disposal (R-SAVE-LOSS). Dispose the installed start before installing another.

Keep the run's traces and evaluation record under the start's `work/` directory
(or copy them there after all writers stop). After the game saves and closes,
`python -m tools.starts dispose NAME --seal STUDY --cited-by RECORD --note TEXT`
uses `tools.evidence.seal` to retain the start, working outputs, player store and
installed final userdir. It verifies that every working file is present by path
and hash in the sealed copy before removing the working start and installed
userdir (R-EVIDENCE-LOSS). Excluded files are refused before sealing; mismatched
files prevent removal. A seal receipt makes disposal resumable: retry with the
same study to verify the seal and finish removal, with the installed marker
removed last. If a seal fails verification, the lifecycle refuses removal and the
lead investigates the evidence store before any manual recovery step.
Restore also finishes a pending sealed disposal. An unused start
can be disposed of the same way. Archives remain outside the save tree.
`python -m tools.starts restore-userdir ARCHIVE` restores a reported archive path
or archive basename, verifies its hashes and archives any current userdir first.
No command opens the sealed source for writing or launches the game.

## Recording a run

Each admission gets one row in the [tracked ledger](../data/evaluation/runs.jsonl),
written by `tools/run_ledger.py record` ([campaign procedure](operations/campaign-run.md#start-and-close)).
That row is the one numeric record of the run. The study's dated record holds the
run's notes and presents its numbers through generated tables or by citing the ledger
(`python -m tools.run_ledger totals --study ISSUE` gives attempts, wall seconds,
the provider subtotal and separate amounts used for admission). The dated record
links to those values.
A short issue comment may announce the run and link its ledger row.
Evaluator headlines go into the [metrics snapshot](../data/evaluation/run-metrics.jsonl)
with `python -m tools.evaluate evaluate-table RECORDS --snapshot data/evaluation/run-metrics.jsonl`,
and a record's generated tables are regenerated with
`python -m tools.evaluate evaluate-table data/evaluation/run-metrics.jsonl --write RECORD`. The fast checks
validate every ledger row and reject stale generated tables.
