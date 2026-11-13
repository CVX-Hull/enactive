---
owner: lead
status: historical
kind: measurement
date: '2026-11-13'
scope: 'The measure gate of the memory screen (#386, protocol of 13 November 2026), $0 on the provider: a known-item list built from the seven-day lineage''s frames by two blind annotators, three model judges labelling how the recorded player used each item in 200-decision stretches of sd1a5 to sd1a7, the owner''s calibration labels, and the protocol''s simulation re-run on the measured numbers'
---

# Memory measure gate on the seven-day lineage (#386)

## At a glance

- **Question.** How many known items does play touch, how often does the current
  player miss them, how reliable is the judge, and is any comparison of the briefing
  affordable at those numbers?
- **Touched.** 8.3 known items per 200 decisions (exact Poisson interval 5.6 to 11.8):
  31 touched in 747 decisions. The protocol guessed 5.
- **Missed.** 45% of touched items (14 of 31; rough bootstrap over six stretches 0.12 to
  0.69). The protocol guessed 70%. Nine of the 14 are in one stretch.
- **The judges agree with each other** on 93.8% of pairs, κ 0.80, and pass the
  protocol's calibration on its letter: the adjudicated label matched the owner's first
  answer on 18 of the random 20.
- **But not where it matters.** The random 20 held only three touched pairs. On the 12
  pairs, random and supplementary, that the owner or the judges called straight or
  missed, the judges' label differed from the owner's first answer on 9 (error 0.75,
  exact interval 0.43 to 0.95). After seeing the judges' cited frames the owner changed
  6 of those answers to the judges' label; the owner's checked answers differ from the
  judges on 3 of the 12 (0.25).
- **No affordable comparison can detect a halving.** At a judge error of 0.25 none of up
  to 60 starts per arm reaches four chances in five. Even at 0.1 it needs 29 starts per
  arm: about \$208 of play for two arms at \$3.58 a start, plus about \$68 of curator
  sessions.
- **Not known.** Whether the owner's first answers or the judges' are nearer the truth;
  the measure on any other game; whether a cheaper measure than frames could tell
  re-finding from a return.
- **Owner decision needed.** What to do in place of the comparison, and the cut. They
  are put to the owner with this record.
- **Spend.** \$0 on the provider. The annotators and judges were clean-context agents of
  the lead's coding host (`claude-fable-5-2`); their use of the host is not priced.

## Method

All commands are `.venv/bin/python -m tools.memory_measure SUBCOMMAND RUN` with
`RUN=.runtime/memory-measure/seven-day-measure-gate`, run from the main checkout. The
tooling is #613 and #615.

1. **Annotator packets** (`packets annotate`): every third changed frame of `sd1a1` to
   `sd1a4` with the inputs before it: 390 frames in 8 packets of at most 60, from 1,166
   changed of 1,200 recorded. The packets hold frames only: no store, record or report.
2. **Annotators.** Two clean-context agents per packet, 16 in all, each told to use only
   its packet. Each listed 89 places with goods.
3. **Known items** (`items`). The lead matched the two lists in `matches.json`
   (sha256 `8b166822…`), joining one place seen in several packets. 82 of 89 entries of
   each annotator fell into an item; 7 of each were dropped as listed by one only. The
   frozen list `items.json` (sha256 `4cb77e39…`) holds 35 items.
4. **Judge packets** (`packets judge`): `sd1a5` to `sd1a7` cut into 200-decision
   stretches, with short tails kept and flagged: 6 stretches of 200, 52, 200, 82, 200
   and 13 decisions, 238 frames, under shuffled names, with each item's first frame.
5. **Judges.** Two clean-context agents per stretch, then a third on the five stretches
   holding disputed pairs (`events`, `agreement`). The adjudicated label is the label two
   of three gave; on three pairs the third judge's label matched neither and was taken
   (`third_alone`).
6. **Calibration sample** (`sample`): 20 pairs drawn at random from all 210, seed
   1681420555, before any verdict existed; then, by the owner's decision, 10 more drawn
   from the 39 pairs any judge called straight, missed or cannot tell, seed 1978173627,
   which also fixed a shuffled display order (`sample --engaged`).
7. **Owner labels** (`label-server`): by the owner's decisions, two passes on one page:
   a first answer on all 30 pairs with nothing of the judges shown, then a check pass
   showing the judges' labels, notes and cited frames. Only first answers calibrate.
8. **Statistics** (`agreement`, then `measure`), and the protocol's simulation
   (`simulate --touched T --missed M --wrong W`, 1,500 simulations a size, \$3.58 a start).

Files and hashes: `sample.json` `12048cb0…`, `sample-engaged.json` `2ee5203c…`,
`labels.json` `7af15bb9…`, `adjudicated.json` `0191e848…`, `agreement.json`
`e6900305…`, judge events `events/judge-a.jsonl`, `judge-b.jsonl`, `judge-c.jsonl`.

## Results

### What play touched

| Stretch | Decisions | Straight | Missed | Not engaged | Cannot tell |
| --- | ---: | ---: | ---: | ---: | ---: |
| `sd1a5` 1–200 | 200 | 6 | 3 | 25 | 1 |
| `sd1a5` 201–252 | 52 | 3 | 0 | 32 | 0 |
| `sd1a6` 1–200 | 200 | 4 | 0 | 31 | 0 |
| `sd1a6` 201–282 | 82 | 0 | 2 | 32 | 1 |
| `sd1a7` 1–200 | 200 | 3 | 9 | 23 | 0 |
| `sd1a7` 201–213 | 13 | 1 | 0 | 34 | 0 |
| **All** | **747** | **17** | **14** | **177** | **2** |

- Touched (straight or missed) per 200 decisions: 8.30, exact Poisson 95% interval 5.64
  to 11.78; on the three full stretches 8.33 (5.39 to 12.30).
- Missed share among touched: 0.452; rough percentile bootstrap over 6 stretches from 3
  admissions 0.115 to 0.690; on the full stretches 0.480 (0.000 to 0.750).
- Cannot tell among touched and cannot tell: 2 of 33 (0.061), under the protocol's 0.30.
- The bootstrap has six units from three admissions; its intervals are rough.

### The judges

- Agreement between the first two judges: 0.938 (bootstrap over pairs 0.905 to 0.967);
  Cohen's κ 0.800 (0.699 to 0.893). The bootstrap treats pairs as independent although
  a judge reads a whole stretch, so these intervals are too narrow.
- 13 pairs disputed; the third judge settled all 13.

### Against the owner

| Owner's first answer \ judges | Not engaged | Straight | Missed |
| --- | ---: | ---: | ---: |
| Not engaged | 18 | 2 | 4 |
| Straight | 2 | 2 | 0 |
| Missed | 0 | 1 | 1 |

- **Random 20 (the calibration):** 18 of 20 match (exact 0.683 to 0.988), which passes
  the protocol's 18 of 20. Only three of the 20 are touched by either reading, and the
  judges match the owner on one of them.
- **Supplementary 10:** 3 of 10 match. On five of them the owner's first answer was
  "not engaged" where the judges found engagement.
- **Touched pairs, both groups:** 3 of 12 match; error 0.75 (exact 0.43 to 0.95). The
  supplementary pairs cannot include a pair that every judge called not engaged, so
  this is conditional on a judge noticing engagement.
- **After the check pass:** the owner changed 9 of 30 answers, all towards the judges'
  label. Checked answers match the judges on all 20 random pairs and 7 of 10
  supplementary pairs; on touched pairs they differ on 3 of 12 (0.25). The checked
  answers saw the judges' evidence and are not independent of it.

Two readings fit this, and the gate cannot tell them apart:

1. **The judges find engagement that a person scanning a strip of 60 frames misses.**
   Six of the nine disagreements on touched pairs are the owner's "not engaged" against
   the judges' "missed" or "straight", and the owner adopted the judges' label once their
   cited frames were shown.
2. **The judges over-read engagement.** The owner kept "not engaged" or another label on
   three touched pairs after seeing the evidence.

### Sizing

`simulate` on the measured touched rate and missed share, the protocol's model and test:

| Judge error | Basis | Starts per arm to detect a halving 4 times in 5 (0.05; Holm 0.025) | Play for two arms |
| --- | --- | --- | ---: |
| 0.75 | first answers, touched pairs | none up to 60 (best 0.01) | – |
| 0.25 | checked answers, touched pairs | none up to 60 (0.78 and 0.68 at 59) | over \$420 |
| 0.10 | the random 20, all labels | 29; 38 | \$208; \$272 |

Each start would also need about ten curator sessions, about \$2.34 at the pilot's
rates. The lower touched rate or missed share at their interval ends makes every row
worse.

## Interpretation

- **The measure is too weak for any comparison this project would fund.** A halving
  of missed items from 45% to about 23% of 8 touched items is a change of about two
  items per start, and the judge's error on the items that matter is high enough to
  hide it.
- **The protocol's fallback applies:** "development play in its place: one or two
  admissions with the briefing, read for whether briefed facts are stored and acted on,
  with no claim of benefit".
- **The calibration rule passed on pairs that do not test the judge.** Eighteen of the
  random 20 were "not engaged" by both readings. The supplement, added by the owner's
  decision, is what exposed the error.

## Deviations

- **The calibration was widened before labelling** by two owner decisions recorded in
  the owner decision log: ten supplementary pairs, and a check pass after a blind first
  pass. The 18-of-20 test uses the random 20 and first answers, as the protocol states.
- **The known-item list's matches were made by the lead**, who had read the free checks
  and knew the four lost facts. The annotators did not. The matching joined only
  entries that described the same place and goods.
- **The protocol's appendix simulation was re-run through the tool**, which reproduces
  the appendix's table within simulation noise (tested in #613), not by the appendix
  script itself.
