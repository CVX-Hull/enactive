---
owner: lead
status: historical
kind: measurement
date: '2026-11-14'
scope: 'The game-neutral process measures (#620) run once on sealed development play, the seven-day lineage''s admissions sd1a5 to sd1a7, with host-agent judges at no provider spend: windows stuck or looping, the same failed approach tried again, progress against milestones frozen before scoring, and success claims the frames contradict; each with the first two judges'' agreement, the keep rule and a comparison with the evaluator''s game binding'
---

# The game-neutral process measures on sealed play (#620)

## At a glance

- **Question.** On sealed play, do model judges agree well enough on the four process
  measures of #620 to keep them, and what do they report beside the evaluator's game
  binding?
- **Kept: progress against frozen milestones.** 17 of 22 milestones reached across the
  three admissions (95% interval 0.63 to 0.86), the first two judges agreeing on 94 of 95
  pairs (binary κ 0.975, against the floor of 0.845).
- **Dropped, and reported, not tuned: the other three.** On the judged windows nothing was
  stuck or looping, no failed approach was repeated and no success claim was contradicted,
  so the binary κ was undefined (stuck, claims) or 0 (retry: one judge saw one repeat in
  one window, the other none). The rule keeps a measure only above the floor, so they are
  not kept; on this play they have nothing to measure rather than disagreeing about
  something.
- **Against the game binding.** The binding's `stall` findings (long runs of out-of-play
  decisions) fall in 7 of the 10 judged windows, all of which both judges called
  `progressing`: the binding counts menu work (crafting, cooking) as a stall and the judges
  count it as progress. The binding found no `ineffective_repeat`; neither did the judges.
- **What it changes.** Nothing for the withholding pilot (#619) or adoption (#463): the
  measures are descriptive and the pilot's analysis does not read them. The milestone
  measure can be read on the pilot's and the check start's traces at no provider spend.
- **Spend.** \$0 on the provider; the judges ran as host agents.

## Method

- **Tooling.** `python -m tools.process_measures` at main `24d22e14` (`tools/process_measures.py`
  sha256 `053f7fa0…09c6`), as the [evaluation contract](../contracts/evaluation.md#process-measures-process-measures1)
  states. Run directory `.runtime/memory-measure/process-lineage-620`, seed 620, token
  budget 60,000, up to 12 claim candidates a window.
- **Play.** The sealed [seven-day lineage](2026-11-07-seven-day-397.md)'s admissions
  `sd1a5`, `sd1a6` and `sd1a7` (development data, the admissions the
  [curator scoring](2026-11-13-curator-scoring.md) judged); evidence `397-seven-day`, read
  only.
- **Milestones, frozen first.** One judge read each admission's mission only and derived 7,
  7 and 8 observable milestones (reloaded in play, identity shown, alive past the
  admission's start, water, food, better gear, an ordinary save; and alive into the next
  day for `sd1a7`); they were frozen with their hashes before any scoring packet was cut.
- **Packets.** 14 windows; the repeat filter flagged none, so 10 unflagged windows were
  sampled (fraction 0.714). 13 milestone packets of shuffled frames. 43 claim candidates
  (4 cut by the cap), all from the players' final and handoff reports, since these traces
  predate the recorded response text.
- **Judges.** Claude Opus 5.5 host agents with clean contexts, each given packet
  directories only: the goal judge; judges A and B on every packet; judge C on the two
  packets with a disputed pair. 135 events each from A and B, 20 from C; two pairs needed
  the third judge, who sided with one of the first two both times.
- **Comparison.** `measure --records` against the lineage's sealed evaluation records,
  read from a scratch copy so nothing in the evidence store was opened for writing.

## Results

| Measure | Rate | 95% interval | First two judges (binary) | Kept |
| --- | --- | --- | --- | --- |
| Milestones reached | 17 / 22 | 0.63 to 0.86 | agreement 0.989, κ 0.975, positive agreement 0.992 (95 pairs) | yes |
| Windows stuck or looping | 0 / 10 | — | agreement 1.0, κ undefined (no positive) | no |
| Windows with a repeated failed approach | 0 / 10 | — | agreement 0.9, κ 0.0 | no |
| Success claims contradicted | 0 / 7 | — | agreement 1.0, κ undefined (no positive) | no |

**Milestones by admission.** `sd1a5` 6 of 7 and `sd1a6` 6 of 7, each missing the ordinary
save; `sd1a7` 5 of 8, missing the save, survival into the next day and better gear. A save
that happened (the players' reports of `sd1a6` and `sd1a7` say so) can be missed when no
sampled frame shows it; the rule scores absence as `cannot_tell`, never `not_reached`, so
the milestone rate is a lower bound on what the frames could show.

**Claims.** 20 of the 43 candidates fell in judged windows. Adjudicated: 7 success claims
the window's frames support, none contradicted, 10 not success claims, and 3 `cannot_tell`
(claims about events outside the window).

**The game binding.** Per admission (windows with a binding finding and judged stuck or
looping / binding only / neither): `sd1a5` 0 / 4 / 0 for `stall`; `sd1a6` 0 / 3 / 1;
`sd1a7` 0 / 0 / 2; `ineffective_repeat` found nowhere, and no window judged a repeated
failed approach. Counts are unweighted over the judged windows.

## Limits

- Three admissions and ten windows: the agreement figures rest on few positives, and the
  rates have wide intervals or none.
- One lineage of one game, development play only.
- The milestones come from one judge reading the mission; another judge would word them
  differently.

## Deviations

- **Judges batched by admission.** Each judge agent judged one admission's window packets,
  or its milestone packets, in one context, told to judge each packet on its own files;
  so a judge saw several windows of one admission, and several shuffled samples of one
  admission's frames. Window and milestone packets went to different agents, so no agent
  saw both order and shuffle. One agent per packet would have meant 46 agents.
- **One packet re-judged.** Judge B's agent for `sd1a7`'s milestones reported that one
  packet's frames had left its context before it wrote the answer; that packet was judged
  again by a fresh judge-B agent that saw every frame, before any answer was imported.
- **The ten-window sample** is the tool's default; the four unsampled windows were not
  judged.

## Evidence

Sealed: `process-measures-620` (the run directory: packets, frozen milestones, every
judge's answers and events, the adjudication and `process.json`), in the
[evidence index](../../data/evidence/index.json). The original run directory was removed
after the seal verified.
