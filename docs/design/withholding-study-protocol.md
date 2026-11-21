---
owner: lead
status: historical
date: '2026-11-14'
scope: 'The completed withholding study and its pilot, including assignment, analysis and sizing'
---

# Withholding study protocol

This page records the simulation, assignment and analysis methods for the completed
[withholding pilot](../acceptance/2026-11-14-withholding-pilot.md) and
[full withholding study](../acceptance/2026-11-14-withholding-study.md).

## Protocol

### Withholding simulation (`withholding-simulation/1`)

`simulate-withholding` sizes the benefit measure before any play. Per start: a Poisson
number of touched units; each withheld with probability one half; a start-level miss
probability, Beta with the given mean and intra-start correlation (default 0.2); a
withheld unit missed with it and a delivered one with `ratio` times it; each label flipped
by the judge with the given probability. The statistic is missed withheld minus missed
delivered, pooled over starts; the test is the one-sided randomization test that re-draws
delivery within each start, computed exactly (given M missed units, the number withheld is
Binomial(M, 1/2)) at 0.05. For each case (the point values at each judge error, each input
at each end of its interval, and both corners) it reports the smallest number of starts
from 2 to 60 that detects a halving with probability 0.8, the chance of detecting a cut of
one third and the false-alarm rate at that size, and the price: play per start, the same
with the recall model's inferred overhead (×1.67 and ×2.0), and once a store (about \$23)
and one grooming session (\$1.16 to \$4.19). The defaults are the measure gate's numbers.
The [simulation's input record](../acceptance/2026-11-13-withholding-simulation.md#inputs-and-their-intervals)
attributes the one-time price inputs to the brief gate and session price pilot.
It is seeded (each rate has its own stream), prints JSON or a table, and writes no file.
It sizes the measure under the model's assumptions; it does not calibrate real-game power.
`simulate-withholding --pilot REPORT` takes its inputs from a pilot report (below) in place
of the gate's numbers and refuses a flag for any of them (`--touched`, `--touched-ends`,
`--missed`, `--missed-ends`, `--wrong`, `--base-wrong`, `--rho`). It requires `--price`, the
pilot's own dollars per start (play and recall) from its record; the search settings stay
flags.

### The withholding pilot's analysis (`withholding-pilot/1`)

`pilot RUN --runs PACKAGE...` reads a judged run of blind packets over the pilot's starts
and writes `RUN/pilot.json` ([unit-level pilot analysis (#638)](https://github.com/CVX-Hull/enactive/issues/638)).
The [withholding pilot (#619)](https://github.com/CVX-Hull/enactive/issues/619) freezes
this rule before its first start. A change to the rule requires a new version.

- **Inputs.** The run's `adjudicated.json` (`judge-adjudicated/2`, every pair resolved),
  `private/judge-mapping.json` and `judged-facts.json`, and each package's
  `private/units.json` (`knowledge-units/1` with a recorded seed). A start is one package,
  over all its actors and windows. Each start's draw has its own seed, so the arms of
  different starts are independent, as the pooled test assumes. It refuses a run of use
  packets, a package whose unit record has no seed or does not match its manifest, a seed
  repeated across packages, and a judged fact that is in no unit and not shared.
- **A fact's outcome in a start.** The fact is **touched** when any of its windows in that
  start has an applied adjudicated label (`in_line`, `against` or `found_again`); otherwise
  it is untouched, whatever its `did_not_apply` and `cannot_tell` windows. A touched fact is
  **missed** when any of its windows is labelled `against` or `found_again`: the player
  acted against it or had to find it again, so it did not have the fact when it mattered.
  A touched fact whose applied labels are all `in_line` is **straight**. `holds` does not
  enter the outcome.
- **A unit's outcome.** A unit (an article with the facts only it cites, or a fact no
  article files) is touched when any of its facts is touched, and missed when any touched
  fact of it is missed. Its arm is its draw in `private/units.json`: withheld or delivered.
- **Shared facts** (cited by more than one article) are not drawn on their own, so they
  stay out of the units and the test. Their touched and missed counts are reported apart,
  as delivered when any citing article was delivered.
- **Estimates**, each with a 95% interval from a cluster bootstrap over starts (seed 619
  unless `--seed` is given, so the simulation's interval ends are fixed with the rule; a
  draw in which an estimate is undefined is left out of its interval):
  - `touched_per_start`: touched units per start, its mean and the counts per start, and
    the ratio of its variance to its mean (1 for a Poisson count);
  - `missed_share`: missed over touched units, pooled, and per arm;
  - `spread`: the intra-start correlation of the unit-level missed outcome (the one-way
    analysis-of-variance estimator for a binary outcome, truncated at 0);
  - `judges`: the first two judges' agreement, Cohen's κ and dispute rate on the label,
    over all pairs and over the pairs driving the outcome (either of the first two gave an
    applied label), as `measure` reports them; and the per-judge error they imply for the
    simulation, `wrong = (1 − √(1 − 2d)) / 2`, where `d` is the share of driving pairs on
    which the first two judges disagree about the missed outcome itself (one gave
    `against` or `found_again` and the other did not), since the simulation flips that
    binary outcome (two judges each wrong independently with probability `wrong` disagree
    with probability `2·wrong·(1 − wrong)`). The measured missed share already carries
    judge noise, so applying `wrong` on top errs toward more starts.
- **The comparison, descriptive only.** Per start and pooled: touched and missed units by
  arm, the statistic missed withheld minus missed delivered, and the one-sided
  randomization p-value of the simulation's test (given a start's `M` missed units, the
  number withheld is Binomial(`M`, 1/2); independent draws pool to Binomial of the summed
  `M`). The report's `not_a_claim` field states that the pilot's starts, however many were
  analysed, make no claim of benefit, and `not_corrected` that the outcome rests on
  adjudicated model-judge labels.
- **Secondary counts.** Touched units missed only by `against`, only by `found_again`, and
  by both, per arm; touched units with an applied window whose `holds` is
  `stale_or_false`; actors listed under `no_frames`.
- **Threats** stated in the report: every start copies one saved game, about four game
  minutes before the lineage's recorded death; one lineage of one game; the number of
  starts analysed; and that the spread pools both arms, so an effect of delivery that
  differs between starts can show as spread.
- **The simulation inputs.** `simulation` holds `touched` (mean and interval ends),
  `missed` (the withheld arm's missed share and its ends, the simulation's "missed when
  withheld"), `rho` (the spread's point value) and `wrong` (the point value, used as the
  judge error at the interval ends too), in the form `simulate-withholding --pilot` reads.

### The withholding study's design (`withholding-study-draw/1`)

A withholding study fixes one draw for all starts before play, under the
[withholding measure revision (#653)](https://github.com/CVX-Hull/enactive/issues/653).
Each unit is its own comparison, withheld in half of each block's starts and delivered
in the other half, with odd counts rounded as described below.

- `knowledge_export draw-study REPOSITORY --version V --starts N --blocks LABEL:COUNT...
  --seed S [--placebo UNIT_ID...] --out FILE` writes the draw: the store version, the unit
  layout (units and shared facts, as the [unit rule](../design/player-context.md) builds
  it), the seed, the starts in order (index `0`…`N−1`, each with its block), the blocks,
  the placebo unit IDs, and per unit and block the half size and the withheld start
  indices.
- **Blocks** are the saved moments the starts copy: a block's label names the source
  study (`starts create --from`), and the counts, each at least 2, sum to `N`. Within each block, each unit
  takes its own random permutation that withholds it in exactly half of the block's
  starts; for an odd count a fair coin per unit sets the half to the floor or the ceiling,
  and the draw records it.
- **Placebo units** are units of the store's own layout, true facts that cannot matter in
  the study's saved moments, named before the draw. They are drawn like any unit and
  analysed apart; no fact is invented for them.
- A reader rebuilds the draw from its seed and refuses a file that differs, repeated or
  unknown placebo IDs, a block of fewer than 2 starts, or blocks that do not sum to `N`. The rebuild uses numpy's
  generator, whose stream is reproducible only under the pinned numpy, so the pin does not
  change while a study's draw is in use.
- A block's label is asserted, not checked: the analysis checks each package's block
  against the draw but not which saved moment the start copied. The study's record lists
  each start's source study and start manifest hash.
- `--study-draw FILE --start-index I` exports start `I`'s package. Its
  `private/units.json` is `knowledge-units/2`: the `knowledge-units/1` fields with the
  draw's seed, plus `draw_sha256`, `start_index`, `block` and each unit's `placebo`. The
  facts builder, `study` and `study-inputs` read `knowledge-units/1` (the sealed pilot's
  packages) and `knowledge-units/2`; the pilot analysis reads only `knowledge-units/1`.
  Any other version is refused.

### The withholding study's analysis (`withholding-study/1`)

`study RUN --runs PACKAGE... --draw FILE [--seed N] [--draws N] [--json]` reads a judged
run of blind packets over the study's starts and writes `RUN/study.json`. The rule is
fixed before any start of a study is played. A change to it requires a new version.

- **Inputs** are the pilot's, with every package's units record as `knowledge-units/2`
  carrying this draw's hash, version, seed and block, and the arms the draw gives. It
  refuses a run of use packets, a repeated or missing start index, and a package whose
  units or arms differ from the draw.
- **Outcome.** Touched and missed per unit and start as in the
  [pilot's rule](#the-withholding-pilots-analysis-withholding-pilot1), under the judge
  instructions' decision rules: a miss is `against`, or `found_again` for an active
  lookup; information the player saw on a screen opened for another purpose, or in a
  message the game showed on its own, is not a miss. Shared facts are reported apart, as
  in the pilot.
- **Primary.** Over non-placebo units touched at least once in each arm: the mean over
  units of the unit's missed share when withheld minus its missed share when delivered,
  each over the starts where it was touched. The test is one-sided (withheld misses
  more): a Monte Carlo randomization test that re-draws the assignment as the draw makes
  it (per unit and block, a fresh permutation with the recorded half sizes), with the
  outcomes fixed and the eligible units recomputed on every re-draw; a re-draw with no
  eligible unit scores 0. `p = (1 + re-draws at or above the observed) / (1 + draws)`,
  10,000 draws and seed 653 unless given. It reports the value, the units counted, and
  the units excluded as never touched or touched in one arm only.
- **Intention to treat.** The same statistic and test over every non-placebo unit, with
  missed per unit and start and an untouched unit counted as not missed.
- **Touch balance.** Over non-placebo units, the touched share per arm, and the same test, two-sided, on touched:
  withholding must not change what the player gets to.
- **Placebo.** The primary statistic and test over placebo units only. Delivery of facts
  that cannot matter should show no effect; one would point to a bias in the judges or
  the outcome.
- **Secondary, a crossed mixed model.** On touched non-placebo (unit, start) rows, statsmodels'
  `BinomialBayesMixedGLM` (variational fit): missed on withheld, with variance components
  for unit, start, and a withheld-by-unit slope. It reports the withheld coefficient's
  posterior mean and SD and each component's (log SD and implied variance). A failed or
  non-converged fit is reported as `failed` with its reason, and the rest of the report
  stands.
- **Judges.** As in the pilot, the first two judges' agreement, κ and dispute rate over
  all pairs and over driving pairs, with a start-bootstrap interval on agreement, and on
  the binary missed outcome (`against` or `found_again` against any other label) the 2×2
  table of the two judges' answers, positive and negative specific agreement and Gwet's AC1. κ falls when
  misses are rare even with high agreement; the specific agreements and AC1 show which
  side the disagreement is on.
- `not_corrected` states that the outcome rests on adjudicated model-judge labels;
  `threats` lists the blocks and their sources, the number of units counted, and that
  judge reliance.

### The withholding study's sizing (`withholding-study-simulation/2`)

The simulator estimates power under the withholding study's assumptions.

- `study-inputs RUN --runs PACKAGE... --out FILE` writes `withholding-study-inputs/2`
  from a judged blind run. Every unit carries required boolean `exclusive_scoreable`
  (whether its validated exclusive fact list is nonempty) and `placebo` (false for
  `knowledge-units/1`). Exclusive fact lists and placebo flags must agree across starts.
  The output gives counts, raw shares and shares shrunk toward pooled values using a
  beta prior of strength 2 (`(k + 2·pooled) / (n + 2)`). A structurally empty unit
  has zero shrunk touch and missed-when-touched shares; its raw conditional miss is
  null. A scoreable unit with no observed touches retains the usual shrinkage.
  Pooled touch uses all unit-starts as its denominator, including structural and placebo
  units. Pooled miss uses all touched unit-starts. Spread uses all units.
- `simulate-study --inputs FILE --price USD [--starts …] [--blocks …] [--effect 0.5]
  [--slope-sd …] [--sims 1000] [--seed 653] [--json]` selects only scoreable,
  non-placebo units and reports excluded structural-empty and placebo IDs. It refuses
  no eligible units or no positive touch probability. Defaults are starts 10 to 100 by
  10, blocks 1, 2, 3, slope SD 0, 0.5, 1. Each unit is touched with its shrunk
  probability; a shared start effect and a withheld per-unit slope act on miss log-odds.
  The solved `log_or` makes the pooled delivered missed share `effect` times the
  withheld share. Each simulated study receives a fresh blocked draw and the primary
  test with 2,000 re-draws. It refuses block counts above half the smallest number of
  starts and effects it cannot solve within 1e-6 at |`log_or`| up to 10⁴. It reports
  power, smallest starts reaching 0.8, and price. It is seeded and writes no file.
  It rejects unsupported input versions.
