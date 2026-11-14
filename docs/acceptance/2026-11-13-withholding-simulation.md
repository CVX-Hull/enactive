---
owner: lead
status: historical
kind: study
date: '2026-11-13'
scope: 'The withholding simulation (#386): the size and price of measuring whether delivered memory helps, by withholding a random half of the store''s units within each start, simulated at $0 on the measure gate''s numbers before any play is asked for'
---

# Withholding simulation on the measure gate's numbers (#386)

## At a glance

- **Question.** How many starts, and what spend, would measure whether delivering memory
  helps, with the design the owner chose on 13 November 2026 (withholding within each
  start, [general memory](../design/general-memory.md#does-memory-help-withholding-within-each-start))?
- **At the measured values** (8.3 units touched per start, 45% of them missed, a judge
  that swaps a label one time in ten): **37 starts** detect a halving of misses four times
  in five. That is \$132 of play at \$3.58 a start, \$221 to \$265 with the recall model's
  inferred overhead, and \$157 to \$292 in all, with a store and one grooming session.
- **Against the comparison it replaces**: two arms needed 29 starts each (58 starts,
  \$208 of play) at the same values ([measure gate](2026-11-13-memory-measure-gate.md#sizing)).
  Withholding needs about two thirds of the starts. Every start yields a comparison, but
  only half its touched units fall on each side.
- **The price spans the intervals.** At the favourable ends 16 starts suffice (\$81 to
  \$142 in all). At the low end of the missed share, or with the judge's error on first
  answers (0.25), no size up to 60 does.
- **Not known.** Whether the measure gate's known items behave like units (an article and
  the facts only it cites); the variation between starts (assumed, never measured); how
  often a judge misses that the player engaged at all, which this model does not price.
- **Owner decision needed.** The envelope for withholding play (#619), asked with this
  record.
- **Spend.** \$0. The simulation ran on the lead's machine; nothing was played or judged.

## Method

One command of `python -m tools.memory_measure` at the commit of this record (#386):

    simulate-withholding --touched 8.30 --touched-ends 5.64 11.78 --missed 0.452
      --missed-ends 0.115 0.690 --wrong 0 0.1 0.167 0.25 --base-wrong 0.1 --rho 0.2
      --sims 20000 --seed 386 --target 0.8 --alpha 0.05 --min-starts 2 --ceiling 60
      --price 3.58 --json

The report is [2026-11-13-withholding-simulation.json](2026-11-13-withholding-simulation.json)
(sha256 `120d3070…8740`); a second run of the same command gave the same bytes.

- **Model.** Per start: a Poisson number of touched units; each withheld with
  probability one half; a start-level miss probability drawn from a Beta with the given
  mean and intra-start correlation 0.2; a withheld unit is missed with that probability, a
  delivered one with half of it (a third less for the secondary row, the same for the
  false alarm); each label flipped by the judge with the given probability.
- **Test.** Missed withheld minus missed delivered, pooled over starts, against the
  randomization that re-draws delivery within each start; with each unit withheld
  independently that null is exact (given M missed units, the number withheld is
  Binomial(M, ½)), one-sided at 0.05. The test is conservative: false alarms 0.037 to 0.045.
- **Search.** The smallest number of starts from 2 to 60 whose simulated power reaches
  0.8, 20,000 simulated studies a size.

### Inputs and their intervals

| Input | Value | Interval used | Source |
| --- | ---: | --- | --- |
| Units touched per start | 8.30 | 5.64 to 11.78 (exact Poisson) | Known items touched per 200 decisions, [measure gate](2026-11-13-memory-measure-gate.md) |
| Missed share without delivery | 0.452 | 0.115 to 0.690 (bootstrap over six stretches) | The current player's missed share, same record |
| Judge error | 0.1 | 0, 0.167, 0.25 | Straight and missed swapped on 1 of 10 checked answers and 1 of 4 first answers where both sides called an item touched |
| Intra-start correlation | 0.2 | none | The protocol's assumption, never measured |
| Play per start | \$3.58 | ×1.67 to ×2.0 with recall | The gate's figure for a 200-decision start; recall overhead inferred in [general memory](../design/general-memory.md#2-delivery-making-the-player-use-memory) |
| Bought once | \$23 store, \$1.16 to \$4.19 grooming | none | Brief gate and price pilot records |

## Result

| Case | Touched | Missed | Judge error | Starts | Halving | One-third cut | False alarm | Play | With recall | In all |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- | --- |
| Point values | 8.3 | 0.452 | 0 | 22 | 0.81 | 0.46 | 0.040 | \$79 | \$132 to \$158 | \$103 to \$185 |
| Point values | 8.3 | 0.452 | 0.1 | 37 | 0.80 | 0.47 | 0.042 | \$132 | \$221 to \$265 | \$157 to \$292 |
| Point values | 8.3 | 0.452 | 0.167 | 55 | 0.80 | 0.48 | 0.045 | \$197 | \$329 to \$394 | \$221 to \$421 |
| Point values | 8.3 | 0.452 | 0.25 | none up to 60 (0.60 at 60) | – | – | – | – | – | – |
| Touched, lower end | 5.64 | 0.452 | 0.1 | 54 | 0.80 | 0.47 | 0.041 | \$193 | \$323 to \$387 | \$217 to \$414 |
| Touched, upper end | 11.78 | 0.452 | 0.1 | 26 | 0.80 | 0.47 | 0.043 | \$93 | \$155 to \$186 | \$117 to \$213 |
| Missed, lower end | 8.3 | 0.115 | 0.1 | none up to 60 (0.31 at 60) | – | – | – | – | – | – |
| Missed, upper end | 8.3 | 0.690 | 0.1 | 22 | 0.81 | 0.47 | 0.042 | \$79 | \$132 to \$158 | \$103 to \$185 |
| Both unfavourable | 5.64 | 0.115 | 0.1 | none up to 60 (0.23 at 60) | – | – | – | – | – | – |
| Both favourable | 11.78 | 0.690 | 0.1 | 16 | 0.82 | 0.48 | 0.039 | \$57 | \$96 to \$115 | \$81 to \$142 |

"In all" is play without recall plus the store and the cheaper grooming session, up to
play at ×2.0 plus the store and the dearer session. Seeds 387 and 388 give the same sizes
within one start (36 to 37 at the 0.1 row, 55 to 56 at 0.167).

## Interpretation

- **A halving is affordable at the measured values, a third is not.** At 37 starts a cut
  of one third is detected about half the time.
- **The judge's error matters more here than in the comparison**, because each start's
  units are split: from 22 starts with a perfect judge to 55 at one error in six.
- **The missed share decides whether it can work at all.** If the current player misses
  few items, there is little for delivery to halve; at 0.115 no size up to 60 detects it.
- **The measure counts only misses.** A distracting reminder or a harm to play as a whole
  is seen in the use labels and in time per decision, not here.

## Limits

- **Items stand in for units.** The gate counted annotator-listed known items per 200
  decisions; a unit is an article with the facts only it cites. A unit may hold several
  items or none touched.
- **Withholding is modelled per unit with probability one half**, not as exactly half of
  a finite store. The analysis of real play re-draws the recorded design, not this
  shortcut; it needs each start's record of which units were withheld, which #461 writes.
- **The judge error only swaps missed and not missed among touched units.** The gate's
  main disagreement with the owner was whether the player engaged at all; that is not
  priced.
- **The correlation of 0.2 is assumed.** A larger one raises the size.
- **One lineage of one game** produced every input.

## Deviations

- The simulation was built and run by a delegated worker in the #386 worktree from the
  lead's brief; the lead re-read the report and its inputs. No input was collected for
  it: every number is from the sealed gate records.
