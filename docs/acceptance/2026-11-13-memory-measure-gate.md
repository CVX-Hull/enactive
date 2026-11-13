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
  player miss them, how reliable is the judge, and what would a comparison of the
  briefing cost to detect a halving of misses?
- **Touched.** 8.3 known items per 200 decisions (exact Poisson interval 5.6 to 11.8,
  treating the 31 labels as independent). The protocol guessed 5.
- **Missed.** 45% of touched items (14 of 31; rough bootstrap over six stretches 0.12 to
  0.69). The protocol guessed 70%. Nine of the 14 are in one stretch.
- **The judges** agree with each other on 93.8% of pairs (κ 0.80) and pass the protocol's
  calibration on its letter: 18 of the random 20 match the owner's first answer.
- **Where they and the owner differ, it is mostly about whether the player engaged at
  all.** On the 12 pairs that the owner or the judges called straight or missed, the
  owner's first answer differed on 9, eight of them engaged against not engaged. After
  seeing the judges' cited frames, the owner's checked answers differed on 2 of those 12,
  and on none did the owner keep "not engaged" against an engaged label. Where both
  sides called an item touched, straight and missed were swapped on 1 of 10 checked
  answers.
- **What a comparison would cost.** At the measured point values and a judge error of
  0.1, 29 starts per arm detect a halving four times in five: \$208 of play for two arms
  (\$408 for three at Holm's step), plus about \$23 for the first store. Even a perfect
  judge needs 23 starts per arm (\$165). At the favourable ends of the intervals 13
  starts per arm suffice (\$93); at the unfavourable ends no size up to 60 does.
- **Not known.** Which end of those intervals is true; whether the owner's first
  answers or the judges' are nearer the truth on engagement; the measure on any other
  game.
- **Owner decision needed.** Whether to fund a comparison at these prices or take the
  protocol's fallback, and the cut. They are put to the owner with this record.
- **Spend.** \$0 on the provider. The annotators and judges were clean-context agents of
  the lead's coding host (`claude-fable-5-2`); their use of the host is not priced.

## Method

All commands are `.venv/bin/python -m tools.memory_measure SUBCOMMAND RUN` with
`RUN=.runtime/memory-measure/seven-day-measure-gate`, run from the main checkout. The
tooling is #613 and #615.

1. **Annotator packets** (`packets annotate`): every third changed frame of `sd1a1` to
   `sd1a4` with the inputs before it: 390 frames in 8 packets (largest 55), from 1,166
   changed of 1,200 recorded. The packets hold frames only: no store, record or report.
2. **Annotators.** Two clean-context agents per packet, 16 in all, each told to use only
   its packet. Each listed 89 places with goods.
3. **Known items** (`items`). The lead matched the two lists in `matches.json`
   (sha256 `8b166822…`). 82 of 89 entries of each annotator fell into an item; 7 of each
   were left out as listed by one only. The frozen list `items.json` (sha256
   `4cb77e39…`) holds 35 items.
4. **Judge packets** (`packets judge`, shuffle seed 2442423801): `sd1a5` to `sd1a7` cut
   into 200-decision stretches with short tails kept: 6 stretches of 200, 52, 200, 82,
   200 and 13 decisions, 238 frames under shuffled names, plus each of the 35 items'
   first frame in every packet.
5. **Judges.** Two clean-context agents per stretch, then a third on all 35 items of the
   five stretches holding disputed pairs (`events`, `agreement`, seed 3593231150). The
   adjudicated label is the label two of three gave; on three pairs the third judge's
   label matched neither and was taken (`third_alone`).
6. **Calibration sample** (`sample`): 20 pairs drawn at random from all 210, seed
   1681420555, before any verdict existed; then, by the owner's decision, 10 more drawn
   from the 39 pairs outside the 20 that any judge called straight, missed or cannot
   tell, seed 1978173627, which also fixed a shuffled display order
   (`sample --engaged`).
7. **Owner labels** (`label-server`): by the owner's decisions, two passes on one page:
   a first answer on all 30 pairs with nothing of the judges shown, then a check pass
   showing the judges' labels, notes and cited frames. All 30 first answers were given
   before the first check. Only first answers calibrate.
8. **Statistics** (`measure`, seed 829631240; `measure.json` sha256 `158bddbb…`), and the
   protocol's simulation (`simulate --touched T --missed M --wrong W`, 1,500 simulations
   a size, seed 590, \$3.58 a start).
9. **Owner-against-judge counts** below that no subcommand prints (the confusion table,
   the changes in the check pass, the subsets of touched pairs) were counted from
   `labels.json` and `adjudicated.json` by joining each sampled pair on stretch and item.

Other hashes: `sample.json` `12048cb0…`, `sample-engaged.json` `2ee5203c…`,
`labels.json` `7af15bb9…`, `adjudicated.json` `0191e848…`, `agreement.json`
`e6900305…`. Judge events are `events/judge-a.jsonl`, `judge-b.jsonl` and
`judge-c.jsonl`, 595 in all.

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

- Touched per 200 decisions: 8.30, exact Poisson 95% interval 5.64 to 11.78; on the three
  full stretches 8.33 (5.39 to 12.30).
- Missed share among touched: 0.452; rough percentile bootstrap over 6 stretches from 3
  admissions 0.115 to 0.690; on the full stretches 0.480 (0.000 to 0.750).
- Cannot tell among touched and cannot tell: 2 of 33 (0.061, exact 0.007 to 0.202), under
  the protocol's 0.30. Per first judge: 7 of 37 and 4 of 37.
- **The counts depend on the item list's grain.** Some items are near-duplicates: two
  lockers carry identical judge notes and frames in `sd1a7` 1–200, and four items there
  cite the same frames of sticks gathered at a swamp. The nine misses in that stretch
  come from about five behaviours.

### The judges

- Agreement between the first two judges: 0.938 (bootstrap over pairs 0.905 to 0.967);
  Cohen's κ 0.800 (0.699 to 0.893). The bootstrap treats pairs as independent although
  a judge reads a whole stretch, so these intervals are too narrow.
- 13 pairs disputed; the third judge settled all 13, three of them alone.

### Against the owner

Owner's first answers against the adjudicated label, all 30 pairs:

| Owner's first answer \ judges | Not engaged | Straight | Missed |
| --- | ---: | ---: | ---: |
| Not engaged | 18 | 2 | 4 |
| Straight | 2 | 2 | 0 |
| Missed | 0 | 1 | 1 |

- **Random 20 (the calibration):** 18 of 20 match (exact 0.683 to 0.988), which passes
  the protocol's 18 of 20. Seventeen of the 20 are not engaged by both readings; three
  are touched by either, and the judges match the owner on one of them.
- **Supplementary 10:** 3 of 10 match. On five the owner's first answer was "not
  engaged" where the judges found engagement.
- **Touched pairs, both groups** (touched by the owner's first answer or the judges):
  the first answer differs on 9 of 12 (exact 0.43 to 0.95). Eight are engaged against
  not engaged; one swaps straight and missed. The supplementary pairs cannot include a
  pair every judge called not engaged, so this is conditional on a judge noticing
  engagement.
- **After the check pass:** the owner changed 9 of the 30 answers, eight of them among
  the nine touched disagreements: six from not engaged to engaged, one from missed to
  straight and one from straight to not engaged. The ninth was a disputed pair moved
  from not engaged to missed. Seven of the nine ended on the adjudicated label and all
  on some judge's label. On the same
  12 touched pairs the checked answers differ from the judges on 2 (exact 0.02 to
  0.48). Checked answers saw the judges' evidence and are not independent of it.
- **Where checked answers still differ**, all three times the first two judges had
  disputed the pair and the owner sided with the outvoted judge: twice the owner's
  answer has more engagement than the adjudicated label, once both are engaged. On the
  26 pairs where the first two judges agreed, the checked answers match on all 26.

Two readings of the first-answer disagreement:

1. **The judges find engagement that a person scanning a strip of up to 64 frames
   misses.** The check pass supports this: the owner moved every disputed "not engaged"
   to an engaged label once the cited frames were shown, and nowhere kept "not engaged"
   against the judges.
2. **The judges' evidence persuaded rather than revealed.** Its only support is the
   first answers themselves, and the fact that checked answers were given with the
   judges' evidence on screen.

### Sizing

`simulate` with the protocol's model and test. The model's error flips straight and
missed among touched items; it cannot add or remove a touched item, so the
engaged-against-not-engaged disagreement above is not what it takes. The closest
measured input is the swap rate where both sides call an item touched: 1 of 4 on first
answers, 1 of 10 on checked answers.

| Touched | Missed | Judge error | Starts per arm at 0.05; at Holm 0.025 | Play: two arms; three arms |
| ---: | ---: | ---: | --- | --- |
| 8.30 | 0.452 | 0 | 23; 28 | \$165; \$301 |
| 8.30 | 0.452 | 0.10 | 29; 38 | \$208; \$408 |
| 8.30 | 0.452 | 0.167 | 39; 50 | \$279; \$537 |
| 8.30 | 0.452 | 0.25 | none up to 60 (0.78 and 0.68 at 59) | over \$430 |
| 11.78 | 0.690 | 0.10 | 13; 18 | \$93; \$193 |
| 8.30 | 0.690 | 0.10 | 17; 21 | \$122; \$226 |
| 11.78 | 0.452 | 0.10 | 24; 31 | \$172; \$333 |
| 5.64 | 0.452 | 0.10 | 38; 49 | \$272; \$526 |
| 8.30 | 0.115 | 0.10 | none up to 60 (best 0.40) | – |

- Two arms is the current arm against the curator-briefing arm at 0.05; three arms adds
  the own-records ablation and Holm's correction. Costs are play only, \$3.58 a start.
  The comparison also needs the first store, about \$23; it has no sessions during play.
- At 0.75, the first answers' error on all touched pairs, the model inverts its own
  signal (best rate 0.01, below its false-alarm rate); that row is outside the model's
  meaning and is not used.
- Simulation noise: other seeds give 30 to 31 starts at the 0.1 row and 36 to 38 at
  Holm; the 0.25 row stays at none.

## Interpretation

- **The effect is small in absolute terms.** Halving a 45% missed share of about 8
  touched items is about two fewer misses per start. Even a perfect judge needs 23
  starts per arm to see that four times in five. So the cost comes mostly from the
  effect's size and the variation between starts, not from the judge.
- **The judge is good enough on what the model uses.** Where both sides call an item
  touched, straight and missed are swapped on about one in ten checked answers. Its
  weakness is noticing engagement in the first place, which this model does not price.
- **The price spans an order of magnitude** across the intervals: \$93 to never for two
  arms at the same judge error. The point estimate is \$208 plus the store.
- **The protocol's fallback** is development play in its place: one or two admissions
  with the briefing, read for whether briefed facts are stored and acted on, with no
  claim of benefit.

## Deviations

- **The calibration was widened before labelling** by two owner decisions in the owner
  decision log: ten supplementary pairs, and a check pass after a blind first pass. The
  18-of-20 test uses the random 20 and first answers, as the protocol states.
- **The lead matched the annotators' lists, knowing the four lost facts from the free
  checks.** The annotators did not. Some items join several entries per annotator: one
  joins seven entries covering the fields north, south and north-west of the shelter
  and scattered ground items; one joins roaming boars with rocks in the grass; one
  includes an entry whose tile is not shown. Leaving out entries "listed by one only"
  was also the lead's judgement: one entry of each annotator in packet 8 describes the
  same room floor.
- **The third judge labelled all 35 items of five stretches** (175 verdicts); only its
  13 labels on disputed pairs were used. On undisputed pairs it differed from the agreed
  label 3 times. On three disputed pairs its label was taken alone, one of them a
  touched label (`sd1a5` 1–200, item 10, "straight" against not engaged and cannot
  tell).
- **Judge packets are larger than the tool's frame sizing**: each carries the 35 items'
  first frames, up to 99 images in one packet and 448 across one judge's six.
- **Three of the six stretches are short tails** (52, 82 and 13 decisions). The headline
  rates pool them; the full-stretch rates are given beside them.
- **The protocol's appendix simulation was re-run through the tool**, which reproduces
  the appendix's table within simulation noise (tested in #613).
