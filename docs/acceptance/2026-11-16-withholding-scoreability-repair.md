---
owner: lead
status: historical
kind: measurement
date: '2026-11-16'
scope: 'No-model prospective withholding scoreability repair and finite same-assumption Monte Carlo diagnostic; historical observed study and frozen artifacts unchanged'
---

# Prospective withholding scoreability repair

## At a glance

[The measurement audit](2026-11-16-experiment-measurement-review.md#concrete-sizing-discrepancy)
identified eight articles without exclusive facts. The actual unit scorer could not
touch them, but the old prospective simulator could. [#680](https://github.com/CVX-Hull/enactive/issues/680)
repairs that mismatch with `withholding-study-inputs/2` and
`withholding-study-simulation/2`. Structural-empty units now have exactly zero touch
and miss probability; sparse scoreable units retain the existing shrinkage. This is
an apparatus repair, not a revised study result or a qualified future power forecast.

## Source and invariant checks

The comparison uses the sealed six-start pilot's codebook-653 labels and sizing
input from `withholding-measure-653/memory-measure/codebook-653/`, plus its original
`withholding-pilot-619/computer-sessions/` packages. The old implementation is the
exact pre-repair file from `7c6c24695bdb49fa92f32a652320eb7b890d9f5e` (SHA-256
`7bf78f73fbb93f17d19cdeca7c9424fb077ca4c2cd9b832b953db7566e714b21`).
The retained input's SHA-256 is
`a1d6eabeae562ebcf867b37dc4f966a039310f2188f706ee393e6e38c963a17a`.
The repaired producer regenerated inputs from the same judged evidence and validated
exclusive fact maps; no sealed file was edited.

All 32 units' observed counts/raw rates, pooled rates and spread matched. All
24 scoreable units' shrunk probabilities matched exactly. Each of the eight
structural-empty units previously had touch probability `0.06510416666666667` and
missed-when-touched probability `0.3`: together **0.5208333333333334 impossible
expected touches and 0.15625 impossible expected misses per start**. Both repaired
expectations are exactly zero. Their observed touches/misses were already zero.

The repaired contract keeps the original all-unit pooling denominator and spread
calculation to isolate this repair. It excludes structural-empty and placebo units
before sampling, matching the primary analysis population; this pilot has no placebo
units. It does not refit a new population model. The observed `withholding-study/1`
estimator, eligibility reduction, assignment and randomization test are unchanged.
Old sizing inputs are rejected by the current simulator; frozen historical source
and results remain evidence. The [evaluation contract](../design/withholding-study-protocol.md#the-withholding-studys-sizing-withholding-study-simulation2)
owns the current interface.

## Finite diagnostic

Settings were fixed before dispatch: 20 and 60 starts, two blocks, slope SD zero,
halving effect, seed 680, **200 simulated studies per cell**, and 2,000 randomization
draws per simulated study. Price remained the historical $1.48 per start. There was
no new game, provider request or dependency. The old and repaired simulation used
29.11 and 20.88 CPU seconds respectively, within the two-CPU-hour appetite.

| Starts | Old rejection fraction | Repaired rejection fraction | Difference | Simultaneous Monte Carlo difference bounds |
| --- | --- | --- | --- | --- |
| 20 | 195/200 = 0.975 | 198/200 = 0.990 | +0.015 | −0.0385 to +0.0670 |
| 60 | 200/200 = 1.000 | 200/200 = 1.000 | 0 | −0.0251 to +0.0251 |

Bounds use exact binomial Clopper–Pearson intervals at 98.75% for each of the four
implementation/grid cells, then subtract interval endpoints. Bonferroni gives at
least 95% simultaneous Monte Carlo coverage; no independence between old and repaired
random streams is assumed. In particular, 200/200 rejections is not known power one.
The script's initial reference standard errors are not used for these bounds.

These high-power point-assumption cells do not resolve a small change, equivalence,
other slopes, effects or grids. They quantify this finite diagnostic only. The
simulation still assumes its historical conditional-touch model and miss effects;
matching structurally possible outcomes does not calibrate real-game power. A new
all-assigned task outcome, treatment-dependent engagement, new source populations
and clustered repeats require their own exact estimator, reliability model and
prospective sizing. No renewed study or recurrence sample size follows here.

## Verification and retention

The integrated focused memory/study/withholding suite passed **196 tests**. Independent
review found no material implementation or estimator drift; it identified a malformed-
input test whose empty population could hide missing validation. A valid scoreable
companion now makes those rejection cases meaningful. Source-map tests distinguish
structural zero from rare zero; deterministic cases pass simulated outcomes into the
actual primary test, including one-arm/never-touched exclusions, placebo exclusion
and undefined no-eligible inference. The real sealed-pilot case checks all eight
structural zeros. Worker fixture failures were corrected before the passing reruns.

The sealed `withholding-scoreability-680` entry in the
[evidence index](../../data/evidence/index.json) retains old source/input bytes,
repaired inputs, prospective settings, both simulation outputs, comparison and
uncertainty scripts, and focused test logs. Source is hashed in the comparison.
Protected full CI and merged-main validation are reported on the pull request.
The frozen withholding conclusion remains inconclusive; this repair reopens no study.
