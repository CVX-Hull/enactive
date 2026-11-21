---
owner: lead
status: historical
kind: review
date: '2026-11-16'
scope: 'Retrospective audit of experiment measurements, interpretation and prospective evaluation repairs; no new gameplay, model calls or revised historical outcomes'
---

# Experiment measurement review

## At a glance

The experiments preserve unusually useful failures, source/configuration receipts,
cost limits and deviations. Their strongest evidence is about the apparatus and
bounded observed behavior. They do not yet establish that curated memory improves
useful gameplay, that advice is safe, or that a representation transfers to unseen
CDDA conditions. The frozen withholding primary remains inconclusive. This review
finds a concrete prospective sizing defect and several narrower measurement targets
than the claims we ultimately want to test.

Snapshot: `92b1168336604a69b956d16059ca00b4f93200a8`. The lead reviewed records,
contracts and scoring paths, with independent read-only causal, pipeline and earlier
experiment sweeps. The causal sweep reconstructed all 1,920 unit/start outcomes for
each of the three withholding label sets and reproduced their statistics and Monte
Carlo tests. The lead checked the frozen primary/counts and the sizing discrepancy
below against retained artifacts. Earlier families were reviewed through their
records and selected code, not by re-judging every historical frame. No new paid
inference, native play, corrected power grid or causal harm test was run.

## What the earlier experiments establish

| Evidence | Measurement that is useful | Limit on the conclusion |
| --- | --- | --- |
| [Representation experiment](2026-10-18-memory-representations.md) | Synthetic operators, source/applicability distinctions and seed variation | 355,840 rows over 256 seeds are not independent game trials, model calibration or live decision benefit |
| [Transition corpus](2026-11-01-transition-corpus.md) | Next-label prediction at the recorded sensor resolution, policy and lineage | Observational action associations and coarse labels do not identify causal action effects or a useful game abstraction; labeler assumptions constrain noise bounds |
| [Probe validation](2026-11-08-probe-validation-490.md) | Retrospective retrieval on confirmed pairs and a short second source | Both preregistered recall bars were missed; query coverage is not live use or utility |
| [Curator scoring](2026-11-13-curator-scoring.md) | Relevance and extraction differences between two pipelines | Brief, format and grooming changed together; fewer facts and higher relevant share do not isolate a mechanism or prove player benefit |
| [Image-input stop](2026-11-11-p1-image-input-stop-178.md) and [reader presentation stop](2026-11-12-p1-reader-presentation-stop-178.md) | Missing required images in one batch and truncated required text in a later reader batch | A response is not evidence of grounded answering without actual payload exposure; retained failures must stay in the accounting |
| [Seven-day development](2026-11-07-seven-day-397.md) and [day-scale screen](2026-11-07-long-horizon-382.md) | Visible time, death and censoring for particular finite lineages | One long lineage and a small screen do not qualify a general success rate; pre/post-migration configurations cannot silently form one homogeneous cohort |
| [Withholding study](2026-11-14-withholding-study.md) | Randomized article availability, judged engagement/misses and delivery behavior on repeated continuations | Frozen memory, shared facts, changed engagement and one source lineage limit attribution; no confirmed primary benefit |
| [Process measures](2026-11-14-process-measures.md) | Feasibility, unknown labels and agreement on sampled windows | Sparse or all-negative cases do not validate detection of failures; agreement is not correctness or coverage |

## Withholding: arithmetic versus the question answered

The [frozen rule](../design/withholding-study-protocol.md#the-withholding-studys-analysis-withholding-study1)
averages per-unit missed shares among starts where the unit was touched, admitting
only units touched in both arms. The retained Opus report gives primary
`0.02080351000049142`, one-sided `p=0.3291670832916708`, with 20 of 32 units counted.
There were 284 touched/62 missed delivered unit-starts and 194/31 withheld, out of
960 assigned unit-starts per arm. Nine units were never touched and three were
touched in one arm only.

Delivery changed engagement. Conditioning on that post-assignment behavior does
not compare mistakes at a common set of opportunities. The implemented blocked
randomization test correctly recomputes eligibility under each joint assignment;
this is not an arithmetic invalidation of its sharp global no-effect test. It is a
limit on interpreting the statistic as a pure per-fact reduction in mistakes among
comparable encounters. Topics also compete for attention and retrieval, while shared
facts have availability rules different from exclusive article facts.

The all-assigned missed statistic was `-0.03229166666666666`, with one-sided benefit
`p=1`. Failure to reject that direction is not equivalence, no difference or no harm.
The observed opposite sign also does not establish harm: engagement and active
verification affect what counts as a miss. Rechecking a stale fact can be sensible;
following incomplete advice can be harmful. The existing primary conclusion stands,
and revised codebooks/judges and exclusions remain exploratory.

The reported in-line action and stale/false rates are conditional process measures,
not safety outcomes. They omit routes such as failing to retrieve or heed a warning.
The four deaths remain valid adverse outcomes; they are not four independent worlds.
Future utility evaluation needs all assigned task/source outcomes alongside the
availability → selection → delivery/read → action chain, including justified lookup,
abstention, warning omission and adverse effects. Storage or citation alone is not use.

## Concrete sizing discrepancy

In `tools/memory_measure.py`, `unit_outcomes` scores exclusive fact IDs. An article
with no exclusive facts cannot be touched by that outcome rule. `study_inputs`
nevertheless smooths every unit toward the pooled rate, and `simulate_study` samples
those smoothed probabilities. In the retained pilot sizing input, **eight such units
each receive touch probability 0.06510416666666667** and conditional miss probability
0.3: a total **0.5208333333333334 expected impossible touches per simulated start**.
These are structural impossibilities, distinct from rare scoreable units with zero
observed touches. Shared-fact activity does not make them scoreable by the exclusive
unit rule.

This affects prospective power/sample-size forecasts. It does not change the recorded
outcomes or reproduced study test. The direction and magnitude of any change to the
power grid have not been established. Do not reuse the old forecast as qualified
power for a renewed study. Repair future inputs and simulation together, then compare
simulated scoreability, arm-dependent engagement and the exact planned estimator.
Keep sealed historical inputs/results and their frozen analysis source intact.

Reproduce the discrepancy without a model or game:

```python
import json
from pathlib import Path
root = Path('.runtime/evidence')
inputs = json.loads((root / 'withholding-measure-653/memory-measure/'
    'codebook-653/study-inputs.json').read_text())
draw = json.loads((root / 'withholding-study-651/computer-sessions/'
    'withholding-study-651-draw.json/withholding-study-651-draw.json').read_text())
empty = {u['id'] for u in draw['layout']['units'] if not u['fact_ids']}
rows = [u for u in inputs['units'] if u['id'] in empty]
print(len(rows), [u['shrunk'] for u in rows])
```

## Outcome instruments and uncertainty

The [development-loop validation](2026-11-06-development-loop.md) qualifies readers
only in tested conditions. The death check contained no deaths; threat examples had
empty creature lists. These do not measure positive-case sensitivity. Clock checks
expanded beyond morning examples, but late-night and partially obscured cases remain
unqualified. Missing severe-need labels and other unobserved regimes stay missing.

Process samples contain zero stuck/repeated-failure positives and zero contradicted
claims. Their reported zero-to-zero bootstrap ranges follow from resampling only
zero observations; they are not evidence of a zero population failure rate. The
bootstrap clusters by admission, not independent world, and later admissions can
share a lineage. A future measure must report effective source groups, positive and
negative support, unknown/missing coverage, and when an interval cannot support a
population inference. Do not substitute an independent-window binomial calculation.

Milestone agreement does not validate the milestones' derivation or frame coverage.
Two actual saves were not visible in sampled packets and correctly remained unknown.
The withholding pilot dropped its milestone measure; the full study has no validated
milestone or traveled-distance outcome. Pixel changes are not distance, game time is
not useful progress, and long menu activity can be necessary crafting. Select a small
visible task outcome first and qualify that reader on development examples, then
freeze its held-out assessment; do not require the player to produce semantic inputs
merely to make judging easy.

`survival.game_hours` describes the last episode with an accepted clock, not lifetime
progress through resets. Preserve episode/lineage identity, time origin and censor
reason. A budget-coded ending need not mean the dollar allowance was exhausted.
Report being alive, task progress and in-game duration separately; deaths, infrastructure
stops and finite limits should not be converted into interchangeable completed runs.

## Practical changes for the next CDDA tests

- Freeze the question, intervention and all-assigned primary outcome before power
  sizing. Use a fixed question/task bank independent of candidate outputs; report
  engagement, retrieval and action as separate mechanisms. Missing labels remain
  unknown, with coverage and sensitivity to missingness rather than dropped failures.
- Split by whole world/lineage before selection. Copies and continuations are related
  repeats. Diverse starts supply coverage, not automatically power. Keep Terra fixed
  while comparing representations; later cheaper-model trials are a separate factor.
- Verify one actual input-to-outcome unit using existing payload manifests and source
  references before a batch. Delivery is exposure, not proof of attention or understanding.
  Reuse the common packets for qualitative revision, numeric beliefs and matched
  Beta/subjective-logic controls; score prediction separately from gameplay utility.
- Measure cue-to-useful-effect for complete-player responsiveness. Completed-response
  percentiles remain useful diagnostics, with censored responses reported. Similar
  timings in sequential unmatched runs do not demonstrate zero reminder overhead.
- Price acquisition, all roles, retrieval, failed calls, retries, judging, setup and
  ending. Keep provider-reported usage, configured estimates and unpriced bounds
  distinct. Compare complete successful/failed outcomes, not price per response.
- Re-freeze any resumed seven-day cohort on the current configuration. The old #397
  lineage remains historical evidence; it does not fill a slot in a newly configured
  homogeneous cohort. Counts, affordable detectable effects and spend are chosen later.

These are bounded repairs to existing research work, not a new evaluation platform or
an extra prerequisite to the adopted memory migration. Existing Issues own execution;
the [structured recurrence proposal](../design/structured-recurrence-research.md) and
[belief comparison](../design/belief-method-comparison.md) own prospective research.

Review tracking is [#679](https://github.com/CVX-Hull/enactive/issues/679). The bounded
offline sizing repair [#680](https://github.com/CVX-Hull/enactive/issues/680) was made
Ready/Follow-up; outcome qualification [#681](https://github.com/CVX-Hull/enactive/issues/681)
remains Backlog/Follow-up after #668. Existing #164, #384, #441, #664, #668 and #677
descriptions were reconciled rather than duplicated. #463 remains the next Important
integration slice. Subsequent execution fields belong to the Project. Independent
review confirmed the material counts and causal limits and corrected an initial
source mismatch between missing-image and truncated-text incidents; no material
finding remains open in this documentation slice. No sizing implementation or new
outcome qualification is claimed here.

| Existing risk | Improvement and mechanism | Cost/scope limit |
| --- | --- | --- |
| R-FALSE-CLAIM | Structural scoreability and matching simulation/analysis prevent forecasts of impossible observed events | Focused offline repair; no new model or native test |
| R-FALSE-CLAIM, R-GAME-COUPLING | Qualify the specific visible outcome and source grouping used by a study | Reuse common CDDA packets; no universal scorer or hidden oracle |
| R-OVERSPEND, R-STUDY-OVERRUN | Reprice complete finite cohorts after outcome/coverage feasibility | Existing study approval only; no new standing gate |
| R-CONTROL-BLOAT | Amend existing owners and share packets/readers instead of per-failure frameworks | No duplicate collector, judge backend or production migration |
