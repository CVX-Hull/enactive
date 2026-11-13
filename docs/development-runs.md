---
owner: lead
review_trigger: A new development study, or a change to the benchmark, metric, admission rule or long-horizon method
status: active
---

# Development runs: method

This page owns the method of development runs: the ceiling benchmark, its metric,
the admission rule and the long-horizon classification. Dated owner decisions,
admissions and results are not kept here (S-DOCS); they are in dated records,
listed in the [acceptance index](acceptance/index.md). Per-run attempts, dollars
and wall seconds are data in the [tracked run ledger](contracts/evaluation.md#tracked-run-ledger-and-metrics-snapshot).
Acceptance records and independent review are reserved for adoption decisions,
contract changes and merges ([evidence cadence](workflows/evidence-cadence.md)).

| Study | Dated record | Checkpoint |
| --- | --- | --- |
| Ceiling benchmark and grounding aids ([#372](https://github.com/CVX-Hull/enactive/issues/372)), 5–6 November 2026 | [Development loop](acceptance/2026-11-06-development-loop.md) | Result and aid decisions in the record |
| Evaluator re-score and power check ([#383](https://github.com/CVX-Hull/enactive/issues/383)) | [Development loop](acceptance/2026-11-06-development-loop.md#evaluator-re-score-and-power-check-383) | Result and pre-registered process metrics in the record |
| Long-horizon arm ([#382](https://github.com/CVX-Hull/enactive/issues/382)), 7 November 2026 | [Long-horizon arm](acceptance/2026-11-07-long-horizon-382.md) | Result in the record |

## Question and decision rule

Can a frontier model survive in CDDA through the current pixels-and-keys boundary?
Earlier cheap-model results cannot answer this, and neither can the earlier
multi-day survival, which differs in model class and boundary
([seven-day record](acceptance/2026-10-19-seven-day-survival.md);
[its actor and harness](acceptance/2026-11-09-moved-results.md#development-runs-the-earlier-multi-day-survival)).

Five ceiling runs of GPT-6.1 Terra decide the next branch, fixed before any run:

- **Median survival at least 24 in-game hours:** perception and control are
  adequate for a frontier model. Next is a cost and latency reduction plan
  (cheaper models, programs), and #164's design resumes.
- **Median below 24 in-game hours:** grounding is the bottleneck. Test the
  game-neutral, player-owned aids below against the ceiling arm.

A survivor still alive when its allowance ends counts at its observed hours, so
the rule asks whether the player survives 24 hours *within the allowance*. Using
time well (resting, waiting out the night) is part of the tested competence, not
a separate pacing effect. The run note states whether each survivor died, was
alive at stop, or stopped by its own choice, so a reader can see when pacing rather
than death decided the median.

An aid is adopted only when its arm's median survival exceeds the ceiling arm's
by at least 50% and at least 2 in-game hours, with no more setup failures than
the ceiling arm. Otherwise the change is reverted and the result recorded. With
five runs per arm this detects only large effects; it is a screen, not a
qualification.

## Benchmark

Every run starts from a fresh project-local userdir containing only normal
windowed input options: no world, save, player memory or predecessor report.
The previous run's userdir and game log are archived, never deleted. The player
creates a normal world with default rules and its own survivor through ordinary
visible menus, then pursues indefinite survival. The lead gives no class,
traits, location, tactic, target item or hint.

| Start | Assignment difference |
| --- | --- |
| S1 | The player uses the default **Evacuee** scenario; profession, traits and stats are its choice. |
| S2 | The player chooses every setup option, including the scenario. |

Runs alternate S1, S2, S1, S2, S1 within an arm. Each run is frozen as a fresh
`campaign-run/6` package from merged main, with these limits outside the
player's context:

| Setting | Value |
| --- | --- |
| Route | OpenRouter, `openai/gpt-6.1-terra`, pinned `openai`, no fallback, medium effort, default tier |
| Context | 262,144-token window, 16,384 output tokens, 32,768 reserve (successor handoff when reached); 39 images, evicted in blocks of 10 |
| Requests | 250 charged HTTP attempts including retries, across at most 2 hosts |
| Time | 7,200 host seconds; 7,800 custodian seconds |
| Supervision | [Supervised launch](operations/campaign-supervision.md); nobody is required to watch |

The window stays below OpenRouter's 272,000-token long-prompt threshold, so the
short-prompt rates apply: $1.00/M input, $1.25/M cache write, $0.05/M cache read
and $5.00/M output (read from the public model list on 5 November 2026). A request
with no cost record counts for (262,144 × $1.25 + 16,384 × $5.00) / 1M = $0.4096,
the route's `unpriced_request_usd`. Each package declares a dollar limit, and its
receipt records the cost OpenRouter reported
([campaign procedure](operations/campaign-run.md#spend-limit)).

**Admission rule.** A run is admitted on actual provider-reported spend under the
[budget delegation](operator-permissions.md#finite-gameplay-budget-delegation) rule,
adopted in [#372](acceptance/2026-11-06-development-loop.md#pilot-and-the-admission-rules).
`python -m tools.run_ledger totals --study ISSUE --envelope USD` applies it to the
tracked ledger.

## Metric

Measured by the lead from original frames and receipts; an independent reviewer
samples the claims in each arm.

- **Survival hours (primary):** in-game time from the first in-play clock to the
  last frame showing the survivor alive, or to the death screen.
- **Status:** died, alive at stop (attempt allowance, time or context capacity
  ended the run), or player finished. Dates are UTC.
- **Verified improvements:** distinct visible changes that improve needs (thirst,
  hunger, fatigue or pain reduced), supplies (new food, water or tools confirmed
  carried) or shelter (secured and used for rest). Claims without a confirming
  frame do not count.
- **Death cause**, if shown.
- **Cost:** dollars, charged attempts, setup attempts (until the first in-play
  frame) and wall seconds. The **$ upper bound** column is provider-reported usage
  plus $0.4096 for every attempt without a provider record, so it is an upper bound,
  not an invoice. The generated evaluator tables in the dated records report
  configured-rate dollars per decision from host usage instead; their columns are
  defined beside the [#383 table](acceptance/2026-11-06-development-loop.md#evaluator-re-score-and-power-check-383).

## Long-horizon method (#382)

Over a full in-game day, do needs, rest and supplies hold, and does game time per
decision rise when the player chooses to sleep, wait or travel? The owner's
decisions, the frozen inputs, the pinned admission procedure and the lineages are in
the [long-horizon record](acceptance/2026-11-07-long-horizon-382.md). A new long-horizon
arm freezes its own inputs the same way and states them in its record.

### Classification (fixed before any run)

Each lineage gets exactly one class, checked in this order:

1. **Continuity failure:** an admission does not resume the same survivor in the same
   world, or an admission starts a new episode (`lineage.elapsed.episode_changes`).
2. **Failed:** death, or a failed day check, before 24 elapsed hours.
3. **Day-viable:** alive at 24 elapsed hours with the day check passed.
4. **Slow:** alive under 24 elapsed hours when the decision cap or a stop rule ends it.

The day check is `lineage.day_check`: alive at 24 elapsed hours with no severe thirst
("very thirsty", "dehydrated", "parched"), hunger ("very hungry", "famished", "near
starving", "starving") or rest ("dead tired", "exhausted"). The lead confirms every
boundary, day point and death from frames.

| Arm result | Meaning | Next step |
| --- | --- | --- |
| Any continuity failure | Save and reload blocks long play | Diagnose from the player's own reports and frames, with no harness game knowledge |
| At least 2 of 3 Day-viable | Day-scale survival is viable through this boundary | Design the seven-day attempt for #145 and the cost and latency plan that resumes #164 |
| At least 2 of 3 Failed | A day-scale failure class exists | Classify it from frames (needs, combat or shelter) and target that class |
| Otherwise (Slow or mixed) | Long-horizon pacing limits survival | Report the time-passing behaviour; any intervention is a separate owner decision |

With three lineages this is a screen, not a qualification.

## Recording a run

Each admission gets one row in the [tracked ledger](../data/evaluation/runs.jsonl),
written by `tools/run_ledger.py record` ([campaign procedure](operations/campaign-run.md#start-and-close)).
That row is the one numeric record of the run. The study's dated record holds the
run's notes and presents its numbers through generated tables or by citing the ledger
(`python -m tools.run_ledger totals --study ISSUE` gives a study's attempts, wall
seconds and spend); it keeps no second hand-typed copy of attempts, spend or duration.
A short issue comment may announce the run and link its ledger row.
Evaluator headlines go into the [metrics snapshot](../data/evaluation/run-metrics.jsonl)
with `python -m tools.evaluate evaluate-table RECORDS --snapshot data/evaluation/run-metrics.jsonl`,
and a record's generated tables are regenerated with
`python -m tools.evaluate evaluate-table data/evaluation/run-metrics.jsonl --write RECORD`. The fast checks
validate every ledger row and reject stale generated tables.
