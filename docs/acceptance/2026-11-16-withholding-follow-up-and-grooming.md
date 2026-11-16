---
owner: lead
status: historical
kind: review
date: '2026-11-16'
scope: 'Backlog review of all 29 open issues and the Enactive Project; exploratory re-reading of the full withholding study’s 60 valid starts for elapsed game time, progress, fire outcomes and the delivery-to-action gap; project-local cleanup. No new play or provider spend.'
---

# Withholding follow-up and backlog review

## At a glance

- The 60 valid continuations lasted a median **2.41 in-game hours**, range **0.084 to
  10.71 hours**. Four died; 56 ended at finite limits. These are short continuations
  of one survivor from two saved moments, not independent seven-day campaigns.
- All four deaths were in the earlier saved-moment block. Their finish reports describe
  fire during cooking, water crafting or fuel hauling near the shelter. This identifies
  a repeated development case, not a fresh-world failure rate or a causal memory effect.
- The bounded progress sample showed local resource work and an unfinished cooking
  attempt even in the longest continuation. There is **no measured travel distance** or
  validated milestone score for this study. Advancing the clock is not progress.
- The study used fixed store `v18`. Recall varied what it delivered; it did not test a
  live curator learning from these starts. Adoption claims no confirmed benefit, as
  the [original record](2026-11-14-withholding-study.md) and
  [owner decision](../decisions/owner-decisions.md) require.
- The review selected the coordinated memory adoption migration
  [#463](https://github.com/CVX-Hull/enactive/issues/463) as the sole Ready leaf, with
  intent implementation inside it. The later intent measurement remains
  [#384](https://github.com/CVX-Hull/enactive/issues/384). Live curator freshness has its
  own follow-up, [#664](https://github.com/CVX-Hull/enactive/issues/664). GitHub owns
  subsequent scope and status; this is the dated review result.
- No stale game, campaign, curator or test process was found. Only `main` and its remote
  tracking branch existed; there were no extra worktrees. Two routine check-log
  directories were removed; saves, sealed evidence and reusable build/dependency inputs
  were retained. The full evidence-store hash verification passed.

## Elapsed game time and endings

Source: the committed [run metrics](../../data/evaluation/run-metrics.jsonl), read on
main `6a9e05283d5483327888d40b1fce0f8e16dfb38e`. The frozen primary's sealed
`withholding-study-651-judging/memory-measure/study-651-blind/study.json` declares 60
starts, two blocks of 30 and draw hash `35b9bcff…c63c`. The 63 metric rows include the
three replaced originals. Select the replacement at indices 9, 20 and 29, not both
attempts. All original failures remain in the source data.

| Saved moment | Starts | Median hours | Mean hours | Range, hours | Deaths | Limit-censored |
| --- | --- | --- | --- | --- | --- | --- |
| Earlier, indices 1–30 | 30 | 2.331 | 3.374 | 0.084–10.261 | 4 | 26 |
| Later, indices 31–60 | 30 | 2.536 | 4.072 | 0.493–10.708 | 0 | 30 |
| Both | 60 | 2.411 | 3.723 | 0.084–10.708 | 4 | 56 |

There were 11,582 completed computer-input decisions. Twelve continuations covered less
than one game hour; nineteen covered at least six; none covered 24. The middle half
covered 1.259 to 7.022 hours (Python's exclusive quartiles). The evaluator labels all
56 censored endings `budget`; that label is not proof the dollar cap was exhausted.
It describes finite observation termination under the evaluator's end classification.

The evaluator's `survival.game_hours` takes the accepted player-visible clock span of
the last play episode, not the survivor's total lifetime. Each selected row has one
episode. The existing binding's clock/death reading remains fallible; this review did
not relabel every frame. See [metric implementation](../../harness/evaluation/core/metrics.py)
and its [contract](../contracts/evaluation.md). The two moments are the same lineage,
a day apart, in the same shelter; their difference is descriptive, not an independent
comparison or evidence that the later state is safer.

Reproduce with the main checkout's Python (no game or model):

```python
import json, re, statistics
from collections import Counter
from pathlib import Path

rows = [json.loads(line) for line in
        Path("data/evaluation/run-metrics.jsonl").read_text().splitlines()]
replaced = {f"withholding-study-651-{n}" for n in ("09", "20", "29")}
starts = [r for r in rows if r["run"].startswith("withholding-study-651-")
          and r["run"] not in replaced]
assert len(starts) == len({r["session"] for r in starts}) == 60
for name, selected in (
    ("earlier", [r for r in starts if
                 int(re.search(r"651-(\d+)", r["run"])[1]) <= 30]),
    ("later", [r for r in starts if
               int(re.search(r"651-(\d+)", r["run"])[1]) > 30]),
    ("both", starts),
):
    spans = [r["metrics"]["survival.game_hours"] for r in selected]
    hours = [s["hours"] for s in spans]
    print(name, len(hours), statistics.median(hours), statistics.mean(hours),
          min(hours), max(hours), Counter(s["outcome"] for s in spans))
print("decisions", sum(r["decisions"] for r in starts))
hours = [r["metrics"]["survival.game_hours"]["hours"] for r in starts]
print("below 1h", sum(h < 1 for h in hours), "at least 6h",
      sum(h >= 6 for h in hours), "at least 24h", sum(h >= 24 for h in hours))
print("quartiles", statistics.quantiles(hours, n=4, method="exclusive"))
print("out-of-play median", statistics.median(
    r["metrics"]["mode.out_of_play_share"]["value"] for r in starts))
print("routine pace median", statistics.median(
    r["metrics"]["pace.routine_seconds_per_decision"] for r in starts))
streaks = [r["metrics"]["stall.longest"] for r in starts]
print("longest streak median/max", statistics.median(streaks), max(streaks))
```

## How far the player got

Bounded sample: indices 1 and 31 (one from each moment), all four deaths, and index 58
(the longest clock span). Raw paths below are inside
`.runtime/evidence/withholding-study-651/computer-sessions/`; the existing
[evidence index](../../data/evidence/index.json) and manifests own their identity.
No save or hidden engine state was inspected.

- **S1, 1.976 hours:** actor 002's `host.jsonl:864` reports a field near the boat rental,
  three collected rocks, a fitted straw hat and an unfinished fire ring/cooking plan.
  This is the player's claim, not measured distance or independently verified inventory.
- **S31, 7.781 hours:** actor 001's `host.jsonl:2875` reports a fire ring, roof water,
  fishing without an observed catch, and cattail harvesting in swamp northwest of B-19.
  Frame `98ad79d5e6efe544f8e35a07e0387b8d-9733.png`, inspected directly, shows swamp,
  hydrated status and cattail harvest messages at Spring day 64, 2:45:02 PM. The frame
  supports harvesting and local terrain, not the claimed displacement from shelter.
- **S58, 10.708 hours:** actor 002's `host.jsonl:380` reports that the fire went out
  before a five-stalk cooking batch finished, leaving work in progress. Inspected frame
  `b68c77805e143c4fab55ab7b1ebd26dd-11311.png` shows the shelter, a hauling menu and
  “no longer have a nearby fire and can't continue crafting.” It supports a local
  incomplete activity, not ten hours of useful progress.

The retained metrics contain no traveled distance. Map-region pixel change is not a
route length. The pilot's milestone attempt was rejected for excessive `cannot_tell`
labels ([pilot record](2026-11-14-withholding-pilot.md)); this review does not resurrect
it or infer useful exploration from elapsed hours. Median out-of-play share was 0.669,
median routine pace 5.0 seconds/decision and median longest out-of-play streak 14
(maximum 37 decisions), from the same selected rows. Menus can be necessary work;
these mode readings do not establish looping or tactical failure.

## Repeated fire outcomes and the delivery-to-action gap

The four evaluated deaths and the corresponding public finish reports were:

| Start | Elapsed hours | Actor 001 finish-report line | Player's reported activity |
| --- | --- | --- | --- |
| S14 | 0.363 | 1699 | Cooking cattail rhizomes outside B-19 |
| S18 | 0.084 | 571 | Crafting near shelter fires; extinguishing failed |
| S20 replacement | 1.542 | 1664 | Crafting clean water beside the fire; extinguishing failed |
| S23 | 0.373 | 1312 | Hauling fuel too close to the fire |

These are variants of the original lineage's fire death, which produced this saved
moment and the curator's warning. They warrant investigating the observation, recall,
action and recovery sequence. They do not justify a hard-coded fire guard in the
computer port or an engineered gameplay hint from the lead.

In all four death packages, `delivered-knowledge.json` omits
`article-open-fire-safety-3`, and no sampled actor's `knowledge-delivery` event selects
that article. **That does not mean every fire warning was absent.** S14's delivered
`article-water-6` includes shared fact `open-fire-crafting-burn-1`; its lead says to
“treat open fire as a serious hazard.” The fact recounts the earlier death and cautions
against remaining in a burning area. The trace records this fact ID in the initial
briefing and nine reminder deliveries, before the finish report. A recorded fact ID
means the knowledge was supplied, not that its complete body was read or obeyed.
The other three death packages do not contain that fact.

The [unit rule](../contracts/evaluation.md#the-facts-to-judge-judged-facts1) permits shared facts to
arrive through a delivered citing article; exclusive unit facts are withheld. S14 is
therefore not evidence of a withholding leak. It does show why “article absent,”
“warning absent,” “warning selected,” “warning read” and “action followed it” must be
kept separate in an investigation. This is a post-hoc, selected death sample, not a
prespecified safety test or a causal claim that the safety article prevents death.

## What the curator and player evidence can answer next

The store was frozen at `v18` for this study. Actor-specific recall selections and
reminders are retrieval, not curator learning from these continuations. The original
study's 84.4% in-line use rate and 2.5% stale/false rate among in-line windows remain
model-judged process readings, not useful-survival or harm estimates.

The review assigned the following questions to existing work or the distinct
live-curator follow-up rather than create a separate issue for every pattern:

| Question | Evidence needed | Home |
| --- | --- | --- |
| Where does known warning become unsafe action? | Source frame → available article/shared fact → selected lead/reminder/read → nearby inputs and recovery, across successes and deaths; separate lookup from execution | #441's reshaping and #664's development reader tasks |
| Does new evidence reach the actor before it becomes stale? | Live session queue/coverage, decision lag and tail, publication/correction, new-fact uptake and total cost; design and price first | #664 after #463/#457 |
| What changed with stated intent? | Its cost and attribution, with comparison/confounding fixed before paid play | #384, implementation only in #463 |
| Does the player progress beyond the shelter loop? | Prospective visible milestones with adequate judge coverage; useful supplies/travel and same-character continuity, not clock advance alone | #441, then #145 |
| Does memory alter engagement rather than reduce mistakes? | Preserve intention-to-treat and touch imbalance; inspect unit/block and advice-checking differences without promoting exploratory readings to confirmation | #387; any new efficacy study needs its own protocol |
| Are repeated reminders useful or redundant? | Recall selection repetition, exposure-to-action timing, shared-fact routes and stale advice, separated by actor and moment | #664; reuse #164's host timing reader |

No new play, paid judging or provider request occurred in this review. No pending study
budget was reopened.

## Backlog and integration reconciliation

All 29 open issue descriptions, their parentage and native blocker edges, and the
Project's 260 items, fields, README and four saved-view filters were inspected. Existing
issues remained open: none had complete acceptance that justified closing it merely
because a study or PR merged. A clean-context reviewer checked the proposed briefs,
owner decisions, migration boundary and acyclic sequencing; agent review is evidence,
not human approval.

The review replaced stale pilot/adoption claims in the outcome descriptions, moved the
entire intent implementation into #463, and kept #384 as later priced measurement.
The context design's migration table was reconciled with the already-recorded cut
deferral; it no longer includes live scheduling or coverage-based removal in adoption.
#457 retained its belief decision. #42 owns its own later expectation producer and
reader. #290 and #473 stopped reserving the completed study's launches or starts.
The Project README was reconciled with the four-status workflow, Priority on leaves,
Horizon on outcomes and the current saved views.

The chosen implementation order made the shared-file constraints visible as native
blockers: #463 → #457 → #465 → #466 → #467 → #469 → #468; the data-dependent viewer work
#464 precedes #471, and #470 follows its producers and phase views. #664 follows the
active-player/store contracts. Outcome decisions such as practice adoption remain
conditions in their descriptions; a child is not blocked on its own parent's completion.
The exact live graph and priorities remain GitHub's authority.

The closed-item cross-check found three `NOT_PLANNED` issues still counted as Done:
#385, #458 and #459. Their Project cards were removed, preserving the closed issues
and the consolidated scope in #457. Five historical PR cards (#201, #202, #204, #205
and #206) duplicated issue execution tracking and were removed from the Project;
the PRs and evidence remain. The board therefore retains issue delivery records,
without counting canceled scope or both a PR and its issue as completed work.

Shared validation is paid once where it answers an integrated question: #463's contract,
trace and viewer reader migration belongs in one candidate/full regression. Later runner
and gate work reuse cases and setup while retaining their own focused regressions,
review and protected checks. A common native setup never replaces separate actual
custody/play evidence. Viewer changes have one writer; the lead owns the sole native
lane. More parallel implementation would not shorten those dependencies.

## Cleanup and retained limits

After a host process inventory found no owned game, player, curator, campaign, check or
test process, these stopped, routine check outputs were removed under the existing
[evidence cleanup policy](../operations/evidence-cleanup.md):

| Removed directory | Files | Bytes |
| --- | --- | --- |
| `.runtime/check-logs/20261114T202843Z-0i9uovff` | 37 | 4,838 |
| `.runtime/check-logs/20261114T202905Z-mla0_o99` | 37 | 4,838 |

`git worktree list` and branch inspection showed only the primary checkout on `main`
and `origin/main`; `.runtime/worktrees/` was empty. There was no stale branch to delete.
The temporary build path named in `.runtime/build-manifest.json` was already absent.
Prepared app/builds, pinned downloads and dependency/browser caches were retained as
reusable inputs, not classified obsolete merely by size. The archived userdir, sole
sealed evidence, configuration backups and an unmatched evaluator database were
retained. No save was deleted and no unrelated process was stopped.

`.venv/bin/python -m tools.evidence verify --full` passed for every present study and
manifest. The sealed originals and historical records were not rewritten. The working
checkout gained this review record and corrections to current navigation/design only;
source behavior did not change.
