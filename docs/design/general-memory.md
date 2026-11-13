---
owner: lead
status: proposed
date: '2026-11-13'
scope: 'Direction for the player''s memory after the memory screen''s gates (#460, #386): a game-neutral curator and fact format that edit a bounded store, delivery that puts relevant knowledge in front of the player without waiting for it to ask, measurement of whether memory is used and helps, and model judges as the standing measure with few human labels. Built on the three gate records of 13 November 2026, an audit of the memory stack for game coupling and dated outside sources. Nothing here is built or approved'
review_trigger: The owner decides the questions below, or a measurement contradicts a premise marked as one here
---

# General memory: curation, delivery and judged measurement

## At a glance

- **What the gates showed** ([brief gate](../acceptance/2026-11-13-curator-brief-gate.md),
  [price pilot](../acceptance/2026-11-13-session-price-pilot.md),
  [measure gate](../acceptance/2026-11-13-memory-measure-gate.md)):
  1. **A curator told what to record stores it.** With a brief for places and goods it
     stored all four lost facts, against one before.
  2. **The store grows without bound.** It reached 279 records after about 1,400
     decisions, about 6,000 bytes for every 20, because the curator only appends.
  3. **Sessions are cheap and close behind play**: a median of \$0.20 and 99 s for 20
     decisions.
  4. **A comparison between arms is too dear to answer "does it help"**: \$165 to \$208
     of play for two arms at the measured values, \$93 to never across the intervals.
  5. **The model judges are good enough to lean on.** Where two judges agreed, the
     owner's checked labels matched them on 26 of 26 pairs.
- **What is wrong with what we built.** Its code is game-neutral, but its schema and
  instructions are not ([audit](#where-the-stack-is-coupled-to-one-game)). The
  `place_with_goods` kind, required places and times, and judge labels about "going to
  the known place" assume a world of places and goods, and the format was tuned on the
  four facts the gate then checked.
- **Proposal, in four parts:**
  1. **Curation.** The curator edits a store under a fixed budget, in a minimal format:
     free text plus provenance. The model decides what is worth keeping; no closed kinds.
  2. **Delivery.** The player does not have to remember to look. A small digest is always
     in its context, and a recall model watching play pushes short reminders, or nothing,
     at the moment they are relevant.
  3. **Measurement.** Whether memory is used is measured on every sealed run by judges.
     Whether it helps is measured by withholding a random half of what the store knows
     within each start, so that each start is its own control.
  4. **Judges.** Two judges and a third on disputes are the standing measure, with
     prediction-powered inference over a small random audit for valid intervals.
- **Owner decisions** are [at the end](#owner-decisions): adopting the format, which
  delivery to build first, the judge protocol, and two later spends.

## The principle

Two constraints shape every choice here: the charter's
[portability constraint](../charter.md) and P-GENERALITY, and the owner's instruction
to follow Sutton's bitter lesson. Prefer general methods that improve as models improve
over hand-built knowledge of one game. In practice:

- **The model decides what matters**: what to record, how to word it, what to keep when
  space runs out, and what is relevant now. Software keeps only what no model should
  decide: provenance, budgets, versions, the gate's structural checks.
- **No rule names a kind of thing in a game.** A rule like "goods have a place" or "drop
  facts older than a day" is a guess about one game that a better model would not need.
- **Measures are written in game-neutral terms, and items are found in the trace**, not
  listed in advance.

## Where the stack is coupled to one game

From an audit of the memory and measure code on 13 November 2026. The Python names no
game. The coupling is in the schema and the prose.

| Where | What | Kind of coupling |
| --- | --- | --- |
| `harness/curator/gate.py`, `curator-fact/2` | `place` and `game_time` required on every fact; non-empty for `place_with_goods` and `hazard`; four fixed kinds | Hand-built schema; assumes places, goods and an on-screen clock |
| `tools/curator_host/prompt.md` | Defines the four kinds; asks for a place as "a landmark and a direction, or coordinates" | Survival-genre framing |
| `tools/memory_screen_checks.py` `brief-gate` | Regex on `subject` and `place`, only for `place_with_goods` | Hand-built rule; returns no match, not an error, in a game without places |
| `tools/memory_measure.py` | Known items keyed by place; judge labels "went straight to the known place"; packets of 60 frames, stretches of 200 decisions, every third changed frame | Spatial wording; hand-set sizes |
| `docs/design/long-horizon-memory.md` | A table of what memory "must do for this game" (rations, a roof tank, a fire) | Game examples written as requirements |

The frozen patterns of the brief gate name one game's items. They are evidence of one
run, not a rule, and stay as they are.

## 1. Curation

### The format

A fact becomes free text with provenance:

| Field | Required | Who writes it |
| --- | --- | --- |
| `id`, `schema` | yes | the curator; the gate checks them |
| `text` | yes | the curator: one durable claim a later actor can use, in its own words, including where and when if they matter |
| `subject` | yes | the curator: a short name for what the fact is about, used to find related facts |
| `citations` | yes | frame source ids inside the session's window; the gate checks provenance |
| `seen` | yes | software: the trace step of the latest cited frame |
| `label` | no | the curator: any short grouping word it chooses |
| `supersedes` | no | the curator: the fact this one replaces |

- **Removed:** the four fixed kinds, `place`, `game_time` and `type` with its ontology.
  The gate checks structure and provenance only, never meaning.
- **Why `subject` stays.** The curator needs to find the facts about one thing before it
  edits them, and the delivery layer needs a short name to list. It is the model's own
  word, not a category.
- **Migration.** One contract, `curator-fact/3`, with no shim (S-MIGRATION). Sealed
  stores stay as they are; their readers read git objects.

### The curator edits a bounded store

- **Before writing, the curator sees the existing facts about each subject it touches**,
  and adds, rewrites, merges or retires. Systems that only append grow without bound;
  those that edit against what exists (Mem0, Memory-R1) do not.
- **A byte budget for the store.** The gate refuses a version over budget. The curator
  must decide what to drop or compress to fit. That makes the model do the ranking; no
  rule about age or kind does it.
- **A consolidation session between admissions**: one curator session that reads only
  the store, merges duplicates, retires facts later frames contradict, and rewrites the
  digest (below). This is the "sleep-time" pattern (Letta).
- **Facts are hypotheses.** Each shows when it was last seen. The brief tells the curator
  to retire a fact when a later frame contradicts it. Outside work finds agents follow
  stale notes into harm, so the player is told to check a fact cheaply, not to obey it.

### How the curator improves

- **Scored on sealed replays, not by inspection.** A curator variant (a brief, a budget,
  a model) runs over a fixed set of sealed admissions, and the judges score its store:
  recall of what the frames showed, precision against the cited frames, and stale facts.
  About \$16 a variant at the brief gate's rates.
- **The four lost facts become one test among many.** Recall is measured against items
  the annotators find in the frames, so a brief cannot be tuned to four answers.

## 2. Delivery: making the player use memory

The audit of memory reads found 8 reads in 98 traces and none by an admission's first
actor ([record](../acceptance/2026-11-13-memory-read-audit.md)). Outside work finds the
same: models under-use memory they must ask for (MemTrack). The fix is not a better
prompt. It is delivery the player does not have to start.

Ranked by expected effect per cost:

1. **A pinned digest, always in context.** The curator writes a short digest of the
   facts most likely to matter next, within a token budget, at each consolidation. The
   host puts it in every request near the end of the context, where models attend most,
   as a cached block that changes only between sessions. This is how coding agents'
   always-loaded instruction files work. It needs no choice by the player.
2. **A recall model that watches play.** Every few decisions, and on signals of no
   progress (a repeated input, an unchanged screen, an error), a small model reads the
   player's recent tool calls and stated `intent`, the latest screen, and the store's
   subjects. It answers with up to a few fact ids and one line each, or with nothing.
   The host adds the reminder to the next tool result as transient text that leaves the
   history on the next turn. Relevance is judged by a model, so it is game-neutral; a
   proactive memory agent of this kind raised task success by 2.5 to 8 points on two
   agent benchmarks, and an untrained small one lowered it, so its silence rate and use
   are measured from the start.
3. **A recall at the start of each actor.** The same model reads the mission and the
   previous final report and selects facts for the first message. This aims directly at
   the first actor that never read memory.
4. **The player cites what it used.** The tool calls already carry `intent` and an
   optional `cites`. The guide asks the player to cite a fact id when it acts on one.
   Citations are not trusted as use; the judges check them.

Each delivered fact carries its id and when it was last seen. Every injection and every
silence is logged, so delivery is measured, not assumed.

**Not proposed:** keyword or embedding rules that decide relevance alone (an embedding
may pre-filter candidates for the recall model); a whole-store briefing; a required
"memory checked" field, which models fill without reading.

**Cost.** The digest adds a fixed, cached block. The recall model is one small request
every few decisions; at a session's measured price per request it is well under the
cost of play, and it is measured in the first development play.

## 3. Measurement

### Is memory used? On every sealed run, at \$0 on the provider

The judges score, in game-neutral terms:

- **Use of each delivered fact**: acted on and helped, relevant but ignored, misled, or
  never relevant.
- **Acting on a stale or false fact**: a fact later frames contradict, and whether the
  player acted on it.
- **Re-discovery**: the player found again something a fact it held already said.
- **Silence and precision of the recall model**: injections acted on, and needs the
  frames show it stayed silent on.

### Does memory help? Withholding within each start

- **Design.** In each start, a random half of the store's facts (drawn per start, seed
  recorded) is withheld from the digest and from recall. The judges label, for each fact
  that became relevant, whether the player used the source it describes before any
  alternative. The effect is the difference in that rate between delivered and withheld
  facts within the same starts, with starts as clusters.
- **Why.** The between-arm comparison was too dear because starts vary so much. Here
  each start is its own control, and only one arm is played.
- **Threats.** A delivered fact can imply a withheld one; the player's own records can
  hold a withheld fact. Both bias towards no effect.
- **Before any spend** the protocol's simulation is adapted to this design, with the
  measure gate's numbers, to give its size and price.

### Game-neutral judge wording

- A **known item** becomes any source of something the actor could later use, found by
  the annotators in the frames.
- The labels become: **used it first** (used the known source before any alternative
  for the same need), **missed it** (sought or used an alternative while the known source
  went unused), **not engaged**, **cannot tell**.
- Packets are cut to a token budget, not to 200 decisions or 60 frames.

## 4. Judges as the standing measure

- **Two judges on everything**, from different model families where one is available,
  since judges of one family share blind spots. Each cites frames and labels a window,
  not a step; judges are weak at finding the one step that went wrong in a long trace
  (TRAIL).
- **A third judge on disputes.** The dispute rate is the health signal; it was 6.2% at
  the measure gate.
- **Frozen prompts and models, with an anchor set.** About 30 audited pairs are re-run
  after any change to a judge's prompt or model.
- **Prediction-powered inference for the numbers that matter.** Every estimate combines
  all judge labels with a small random audit by the owner, about 30 to 60 pairs a study,
  stratified by the judges' verdict and by delivered or withheld, on the two-pass page.
  PPI++ gives valid intervals, clustered by run. If its weight on the judges comes out
  near zero, the judges are adding nothing, and that is reported.
- **The audit shows evidence.** The measure gate found that blind labels miss engagement
  the judges find, so the owner labels with the judges' cited frames and some frames
  they did not cite, and a small blind subsample measures anchoring.
- **Known risks**: leniency (judges call failures successes), missing evidence in long
  contexts, judging differently when a briefing names the item, and errors shared by two
  judges. The stratified audit and the anchor set are aimed at these.

## Migration

| Step | What | Cost |
| --- | --- | --- |
| Format and curator | `curator-fact/3`, the budget, editing against existing facts, the consolidation session, the digest; game-neutral brief | \$0 to build |
| Judged measures | Game-neutral wording, token-budget packets, the standing metrics, PPI++ and the audit protocol in the measure tool | \$0 to build |
| Simulation | The withholding design's size and price | \$0 |
| Curator variants | The current brief and the new curator over the same sealed admissions, scored by the judges | about \$16 a variant, owner's approval |
| Delivery | The digest in the host, the recall model, the start-of-actor recall, logging | \$0 to build |
| Development play with withholding | Priced by the simulation | owner's approval |

The issues that hold this work are #445 (the plan), #460 (the curator), #461 (the
host's delivery), #386 (the judge) and #388 (the copy tool). The cut stays out: price no
longer rules it out, but delivery at the moment of need may matter more than holding the
prompt under 60,000 tokens, and that is measured first.

## Owner decisions

1. **Adopt the minimal format** (`curator-fact/3`: free text, subject, citations, when
   seen; no fixed kinds or required place) with a budgeted, editing curator.
   *Recommended: yes.* Cost: \$0 to build; the brief gate's result was under the old
   format and is re-checked by the curator-variant scoring.
2. **Which delivery to build first.** *Recommended: the pinned digest and the
   start-of-actor recall together, then the recall model.* The first two are cheap and
   aim at the first actor that never reads memory; the recall model costs more and needs
   its silence measured.
3. **Judges as the standing measure** with the protocol above, and the owner's role
   reduced to a stratified audit of about 30 to 60 pairs per study. *Recommended: yes.*
4. **Spend, asked later with a price:** the curator-variant scoring, and development
   play with withholding once the simulation has sized it.

## Limits

- **The outside evidence was read in summaries**, not full papers, and none of it is on
  games played from screenshots. Figures quoted from it are leads.
- **No source runs withholding inside long game episodes**; the design is new here, and
  its power is unknown until simulated.
- **The recall model's benefit is shown on other kinds of task**, and an untrained small
  one did harm there.
- **One game, one lineage** produced every measured number in this note.

## Sources

Read on 13 November 2026, mostly as summaries.

- Proactive memory agent beside an actor:
  [Remember When It Matters](https://huggingface.co/papers/2607.08716).
- Models under-use memory tools: [MemTrack](https://arxiv.org/abs/2510.01353).
- Editing memory against what exists: [Memory-R1](https://arxiv.org/abs/2508.19828);
  Mem0. Offline consolidation: [Letta sleep-time compute](https://letta.com/blog/sleep-time-compute).
- Context as a budget, just-in-time retrieval:
  [Anthropic, effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).
- Position in context: [Lost in the Middle](https://arxiv.org/abs/2307.03172).
- Stale memory: [STALE](https://arxiv.org/abs/2605.06527);
  [When Memory Lies](https://arxiv.org/abs/2608.04574).
- Judges: [AgentRewardBench](https://arxiv.org/abs/2504.08942);
  [Online-Mind2Web](https://arxiv.org/abs/2504.01382);
  [TRAIL](https://arxiv.org/abs/2505.08638).
- Judges with few human labels: [PPI](https://arxiv.org/abs/2301.09633);
  [PPI++](https://arxiv.org/abs/2311.01453);
  [active statistical inference](https://arxiv.org/abs/2403.03208).
- Failure taxonomies scored by models: [MAST](https://arxiv.org/abs/2503.13657).
