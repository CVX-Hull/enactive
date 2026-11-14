---
owner: lead
status: historical
kind: study
date: '2026-11-14'
scope: 'The withholding pilot (#619): six short starts from copies of one sealed save (seven-day-end-11 to -16), each withholding each unit of the groomed store v18 independently with probability one half, judged blind by model judges; the missed share, the units touched per start, their spread, the judges'' agreement and the price per start, the withholding simulation re-run on them, and the re-priced full study; $8.86 of a $70 cap'
---

# The withholding pilot (#619)

## At a glance

- **Question.** What are the real inputs of the full withholding study: how many units a
  start touches, how often a touched unit is missed, how much starts differ, how well the
  judges agree, and what a start costs; and so what size and price the full study needs.
  No claim of benefit is made from six starts.
- **Play: all six starts valid, nothing withheld leaked.** Every start loaded the same
  save (start game time 5384600 in each evaluator record) and ended in order on the
  attempt reserve, the survivor alive. In each start, the 13 to 18 withheld units of 32
  appear in no recall selection, delivered text or tool result, by article or fact id.
  Briefings named 9 to 17 articles; 113 reminders were made at `N = 10` with one
  silence, no failure, and two not made because the orderly stop had begun.
- **The inputs, each with a 95% interval over starts** (the frozen analysis of #638 at
  `caffedd7`, blind labels):
  - units touched per start **8.8** (7.0 to 10.3), variance over mean 0.61;
  - missed share **0.40** pooled (21 of 53; 0.25 to 0.58): **0.32** withheld (8 of 25;
    0.09 to 0.54) and 0.46 delivered (13 of 28; 0.28 to 0.70);
  - spread, the intra-start correlation of the missed outcome, **0.09** (0 to 0.19);
  - judges: the first two agree on 95.2% of 1,155 pairs (κ 0.79), but on the 148 pairs
    that drive the outcome on 67.6% (κ **0.45**, 0.34 to 0.56, as low as the curator
    scoring's 0.45 to 0.49), an implied per-judge error of **0.10** (0.05 to 0.17).
- **Descriptively, withheld units were missed less often than delivered ones** (−5 in
  the pooled statistic; one-sided p 0.91). Six starts support no claim either way; the
  analysis states it (`not_a_claim`).
- **Price per start: \$1.48 counted, \$1.34 provider-reported**, against the
  simulation's assumed \$6 to \$7. The counted \$8.86 for six (play and recall) includes
  two requests with no cost record, counted at their \$0.4096 bound; the provider
  reported \$8.04.
- **The full study, re-priced.** At the measured point values it needs **53 starts**
  for 80% power to detect a halving of the missed share: about **\$78** at the counted
  \$1.48 a start (\$71 at the reported price). These are play and recall only: they
  reuse the store `v18`, already paid for (the simulation's totals add a new store and
  grooming, \$24 to \$27), and the judges are host agents at no provider spend. With
  both the units touched and the missed share at their favourable ends 23 starts (\$34); with more
  units touched 46 (\$68); with a higher missed share 27 (\$40). With the missed share
  at its lower end, or fewer units touched, no size up to 60 reaches the target.
- **Use, judged separately** (use packets, briefing and reminders shown): when a fact
  whose lead was delivered applied, the player acted in line with it in **79%** of the
  windows (46 of 58; 0.58 to 0.94) and found it again by looking in 21%; of the 49
  windows in which it acted in line with a fact it had, none acted on a fact the frames
  showed stale or false; it acted on 2 of the 15 facts it read. Recall precision was
  0.16: of 2,329 judged fact windows following a delivered recall selection, the fact
  applied in 376. Five facts of S5's second actor had no frame in its window to judge
  (`not_shown`) and are outside these rates.
- **Threats**, as the analysis names them: every start copies one saved game, about four
  game minutes before the lineage's recorded death; one lineage of one game; six starts;
  and the spread pools both arms, so an effect of delivery that differs between starts
  can show as spread.
- **Not known.** Whether delivered memory helps (the comparison here is descriptive and
  points the other way); how much of the judges' disagreement on the driving pairs is
  the packets' frames rather than the judges.
- **Owner decision.** The owner approved the spending the pilot required
  ([decision log](../decisions/owner-decisions.md)). The full study is put to the owner
  with its price.

## What was run

| Start | Package | Seed | Withheld | Briefing leads (actors) | Reminders made | Attempts | Spend | Game h |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| S1 | `withholding-pilot-619-11` | 61911 | 13 | 17, 9 | 19 | 231 | \$1.500 | 2.24 |
| S2 | `withholding-pilot-619-12` | 61912 | 16 | 12, 10 | 19 | 233 | \$1.116 | 23.25 |
| S3 | `withholding-pilot-619-13` | 61913 | 18 | 11, 11 | 18 | 234 | \$1.164 | 0.32 |
| S4 | `withholding-pilot-619-14` | 61914 | 15 | 11, 11 | 19 | 233 | \$1.912 | 9.02 |
| S5 | `withholding-pilot-619-15` | 61915 | 18 | 14, 10 | 19 | 232 | \$1.626 | 2.21 |
| S6 | `withholding-pilot-619-16` | 61916 | 18 | 9, 14 | 19 | 233 | \$1.539 | 2.06 |

Every start handed off once, so each has two actors and two briefings. Reminders made
counts selections and silences (the one silence was in S3), not the two not made at the
orderly stop (S3 and S6). S2's survivor passed most of a day in the shelter; in S3 a
fight with a zombie dog left the survivor bitten. Spend is the counted figure, which in
S4 and S5 includes one unpriced request each (below); the run ledger labels the starts
`withholding-pilot-S1` to `-S6`.

## Results

<!-- evaluate-table study=619 core=2 binding=cdda:2 -->
| Run | Arm | Start | End | Game h | Decisions | Setup | Routine pace | Long activities | Out of play | Longest stall | $ / decision | Large rewrites |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| withholding-pilot-619-11 | withholding-pilot | S1 | budget | 2.24 | 195 | 4 | 7.0 | 1 · 1.57 h | 70% | 14 | 0.0077 | 33% |
| withholding-pilot-619-12 | withholding-pilot | S2 | budget | 23.25 | 197 | 4 | 1.2 | 11 · 22.99 h | 80% | 25 | 0.0057 | 23% |
| withholding-pilot-619-13 | withholding-pilot | S3 | budget | 0.32 | 200 | 4 | 1.0 | 0 · 0.00 h | 76% | 41 | 0.0058 | 23% |
| withholding-pilot-619-14 | withholding-pilot | S4 | budget | 9.02 | 201 | 4 | 3.0 | 6 · 7.63 h | 70% | 10 | 0.0075 | 33% |
| withholding-pilot-619-15 | withholding-pilot | S5 | budget | 2.21 | 196 | 4 | 6.0 | 1 · 0.30 h | 67% | 17 | 0.0062 | 28% |
| withholding-pilot-619-16 | withholding-pilot | S6 | budget | 2.06 | 200 | 4 | 4.7 | 1 · 1.58 h | 70% | 16 | 0.0077 | 34% |
<!-- /evaluate-table -->

The table's \$ / decision is from provider-reported cost, so S4 and S5 read lower than
their counted spend.

**Time per response (#164).** 1,269 player responses: median 6.1 s, 95th percentile
11.2 s (by start, medians 5.5 to 6.6 s). By prompt size: under 20,000 tokens 3.6 s
(175 responses), 20,000 to 60,000 6.0 s (722), 60,000 to 100,000 7.3 s (371), and one
over 100,000. One request's first tool result to the next request's: median 6.9 s.

**Provider retries (#309).** Two, in S4 and S5: each a rate-limit refusal of a player
request, retried once by the host ten seconds later, which succeeded. The refused
attempt carried no cost record and counted at the \$0.4096 bound. No 5xx occurred.

**Progress against frozen milestones (#620), descriptive.** Seven milestones a start,
derived from the mission alone and frozen before scoring (the world loaded, the
survivor's identity shown and kept, needs tended, time passing alive, no death screen,
and so on). Reached: 31 of 42 (0.74; 0.64 to 0.83); by start 4, 6, 4, 6, 5 and 6 of 7.
Each start's milestones were judged in three packets of shuffled frames, 126
milestone-packet pairs in all, and a milestone counts as reached when any of its packets
shows it. On these starts the measure **fails its own keep rule**: the first two judges
agree on 87% of the 126 pairs, κ 0.75 against the floor of 0.845 (it was 0.975 in #620), and 66 of
the 126 adjudicated labels are `cannot_tell`. The figure is not a reading of progress.

## Method

- **Frozen before spend**, stated on [#619](https://github.com/CVX-Hull/enactive/issues/619#issuecomment-6879379138):
  six `campaign-run/7` packages built to mirror #642's check start (the player's pinned
  GPT-6.1 Terra route through OpenRouter, medium effort, default tier; recall on the same
  route with a 32,768-token window, bound \$0.06144, up to 30 requests; `N = 10`;
  240 attempts; a \$5 limit and a \$1.00 finish reserve), source `26bb24e0`, each with
  its own `--withhold-seed` and its manifest, unit draw and delivered knowledge hashed.
  The store is `v18` of the [curator scoring](2026-11-13-curator-scoring.md).
- **Play.** One start at a time on the main checkout, windowed through the prepared
  wrapper, no inputs from the lead; S1 was played and read end to end
  ([comment](https://github.com/CVX-Hull/enactive/issues/619#issuecomment-6879803407))
  before the other five.
- **Judges.** Claude Opus 5.5 host agents with clean contexts, each given one packet
  directory only. Blind run `pilot-619-blind` (`packets blind`, seed 619, 15 packets,
  1,155 pairs): judges A and B on every packet, C on the 14 packets with a disputed pair
  (98 pairs; 5 settled with a label neither first judge gave). Use run `pilot-619-use`
  (`packets use`, 15 packets, 643 pairs): A and B, and C on 13 packets.
- **Analysis.** `python -m tools.memory_measure pilot` at `caffedd7`
  (`tools/memory_measure.py` sha256 `74a8b233…dc70bc`), bootstrap seed 619;
  `simulate-withholding --pilot … --price 1.476` (seed 386); `measure` on the use run.
- **Readings at no spend.** Response time from `tools.evaluate host-summary`
  (`tools/host_analysis.py`); milestones with `tools/process_measures.py` at `26bb24e0`
  (not in `caffedd7`): one goal judge derived each start's milestones from its mission,
  frozen before scoring; judges A and B on all 28 packets the tool cuts (it requires
  every packet answered), C on the 13 with disputes; only the milestone measure, kept by
  #620, is read.

## Deviations

- **Four blind answers left facts out** (one to two each); each judge was sent back to its
  own packet for the missing facts and rewrote its file. No label was supplied by the lead.
- **The simulation's "with recall" column double-counts.** The measured \$1.48 a start
  already includes recall; the column multiplies it again by ×1.67 to ×2.0. The prices
  above use the measured figure.
- **The run ledger's schema allowed only starts `S1` and `S2`.** It is widened to `S1`
  to `S99` in this change, as the owner chose, so all six starts have rows.
- **The milestone and window judging ran at `26bb24e0`**, since `tools/process_measures.py`
  postdates the frozen analysis commit; the dropped measures were judged only because the
  tool requires every packet answered, and are not reported.
- **The provider balance was not read before spend**: no project tool reads it, and the
  key's credit limit stays the hard cap.

## Evidence

- `withholding-pilot-619` (4,409 files): the six frozen packages with both actors' host
  traces, frames, receipts and session stores; their six evaluation records; the blind,
  use and process judge runs (packets, events, adjudication, `pilot.json`,
  `measure.json`, frozen milestones); and the judges' raw answers with the lead's
  scripts (package builder, play chain, trace reader) and the simulation and
  host-summary outputs.
- `withholding-pilot-619-start-11` to `-16`: the final userdirs of the six starts, which
  were used up and disposed of.
