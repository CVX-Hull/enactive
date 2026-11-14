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
  three admissions (95% interval 0.625 to 0.857), the first two judges agreeing on 94 of 95
  pairs (binary κ 0.975, against the floor of 0.845).
- **Dropped, and reported, not tuned: the other three.** After adjudication nothing was
  stuck or looping, no failed approach was repeated and no success claim was contradicted,
  so the binary κ was undefined (stuck, claims: neither judge gave a positive) or 0
  (retry: judge B saw one repeat in one window, judge A none, and the third judge sided
  with A). The rule keeps a measure only above the floor, so they are not kept; stuck and
  claims had nothing to measure on this play, and retry had one disagreement and nothing
  else.
- **Against the game binding.** The binding's `stall` findings (15 or more consecutive
  decisions out of play; here all in prompts, 17 to 31 decisions long) fall in 7 of the 10
  judged windows, all of which both judges called `progressing`. Two things explain it: the
  judges read the menu work (crafting, cooking) as progress, and a window of 44 to 64
  decisions is labelled by what holds for most of it, so a stall of 17 to 31 decisions
  cannot decide its label. The binding found no `ineffective_repeat`; after adjudication
  neither did the judges.
- **What it changes.** Nothing for the withholding pilot (#619) or adoption (#463): the
  measures are descriptive and the pilot's analysis does not read them. The milestone
  measure can be read on the pilot's and the check start's traces at no provider spend.
- **Spend.** \$0 on the provider; the judges ran as host agents.
- **#620's acceptance.** Met: four measures defined in game-neutral terms, labelling windows
  (or shuffled frame samples) and citing frames, each with the first two judges' agreement
  and dispute rate; run on a sealed lineage at \$0; compared with the game binding where
  both exist; the measure gate applied as written. Judge output stays in the run
  directory and its seal: no judge event enters an evaluation record, the player's context
  or the curator's inputs. One departure from the contract's isolation sentence is under
  Deviations.
- **Not known.** How the dropped measures behave on play that has stuck stretches, repeated
  failures or overclaims: these three admissions had none for the judges to find.
- **Owner decisions needed.** None.

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
  kept and 4 more cut by the cap (one window's report had 16 sentences), all from the
  players' final and handoff reports, since these traces predate the recorded response
  text.
- **Judges.** Claude Opus 5.5 host agents with clean contexts, each given packet
  directories only: the goal judge; judges A and B on every packet; judge C on the two
  packets with a disputed pair. 135 events each from A and B, 20 from C; two pairs needed
  the third judge, who sided with one of the first two both times.
- **Comparison.** `measure --records` against the lineage's sealed evaluation records,
  read from a scratch copy so nothing in the evidence store was opened for writing.

## Results

| Measure | Rate | 95% interval | First two judges (binary) | Dispute rate (all pairs) | Kept |
| --- | --- | --- | --- | --- | --- |
| Milestones reached | 17 / 22 | 0.625 to 0.857 | agreement 0.989, κ 0.975, positive agreement 0.992 (95 pairs) | 0.011 | yes |
| Windows stuck or looping | 0 / 10 | 0 to 0 | agreement 1.0, κ undefined (no positive) | 0 | no |
| Windows with a repeated failed approach | 0 / 10 | 0 to 0 | agreement 0.9, κ 0.0 | 0.10 | no |
| Success claims contradicted | 0 / 7 | 0 to 0 | agreement 1.0, κ undefined (no positive) | 0 | no |

**Milestones by admission.** `sd1a5` 6 of 7 and `sd1a6` 6 of 7, each missing the ordinary
save; `sd1a7` 5 of 8, missing the save, survival into the next day and better gear. In
`sd1a5` and `sd1a6` the save did happen (the [seven-day record](2026-11-07-seven-day-397.md)
and, for `sd1a6`, a supported claim citing the world-selection menu): no sampled frame
showed it, and the rule scores absence as `cannot_tell`, never `not_reached`, so for those
two the rate is a lower bound. `sd1a7` ended in the survivor's death on day 63, so its save
and survival into the next day were truly not reached.

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
  differently, and their derivation was not judged twice. The κ of 0.975 is agreement on
  scoring frozen milestones, not on choosing them.
- Every judge was the same model (Claude Opus 5.5), so the agreement is within one model
  family.
- The claims are sentences of the players' end-of-actor reports only (these traces predate
  recorded response text), judged against the one window that holds the report; claims
  made during play are not in them, and most report claims concern other windows
  (`cannot_tell`).
- A rate of 0 of 10 has the degenerate bootstrap interval 0 to 0; an exact binomial upper
  bound for 0 of 10 is about 0.31.

## Deviations

- **Judges batched by admission, against the contract's isolation sentence** ("judges get
  one packet directory each"). Each judge agent judged one admission's window packets, or
  its milestone packets, in one context, told to judge each packet on its own files; so a
  judge saw several windows of one admission, and several shuffled samples of one
  admission's frames, and one judge's errors can correlate across them. Judges A and B
  were separate agents, so their agreement is not inflated by it. Window and milestone
  packets went to different agents, so no agent saw both order and shuffle. The goal judge
  read the three missions in one context, as the one judge the contract requires; judge C
  got one agent per packet. One agent per packet would have meant 46 agents. Only the one
  agent below reported losing frames from its context; the others were not asked to
  confirm it.
- **One packet re-judged.** Judge B's agent for `sd1a7`'s milestones reported that one
  packet's frames had left its context before it wrote the answer; that packet was judged
  again by a fresh judge-B agent that saw every frame, before any answer was imported.
- **The ten-window sample** is the tool's default; the four unsampled windows were not
  judged.
- **The binding comparison read a scratch copy** of the lineage's evaluation records, so
  the record paths inside the sealed `process.json` point at a copy that no longer exists;
  the originals are in `397-seven-day`.

## Evidence

Sealed: `process-measures-620` (the run directory: packets, frozen milestones, every
judge's answers and events, the adjudication and `process.json`), in the
[evidence index](../../data/evidence/index.json). The original run directory was removed
after the seal verified.
