---
owner: lead
status: proposed
date: '2026-11-13'
scope: 'Changes proposed to the player''s memory after the memory screen''s gates (#460, #386): a game-neutral fact format and a curator that consolidates, the briefing''s full items chosen by a model, reminders from a recall model during play, measurement of use on every run and of benefit by withholding facts within each start, and model judges as the standing measure. Amends the active context design (player-context.md). Built on the three gate records of 13 November 2026, an audit of the memory stack for game coupling and dated outside sources. Nothing here is built or approved'
review_trigger: The owner decides the questions below, or a measurement contradicts a premise stated here
---

# General memory: curation, delivery and judged measurement

## At a glance

- **Question.** After the gates, how should the curator, the briefing and the measurement
  change so that memory is general across games, is actually used by the player, and can
  be shown to help at a price the project can pay?
- **What the gates showed** ([brief gate](../acceptance/2026-11-13-curator-brief-gate.md),
  [price pilot](../acceptance/2026-11-13-session-price-pilot.md),
  [measure gate](../acceptance/2026-11-13-memory-measure-gate.md)):
  1. **A curator told what to record stores it**: all four lost facts, against one before.
  2. **The store keeps growing**: 279 records after about 1,900 decisions, about 6,000
     bytes for every 20. The curator can supersede a fact but cannot retire or merge one,
     and its brief asks it to record every item.
  3. **Sessions are fast and not small**: a median of \$0.20 and 99 s for 20 decisions,
     inferred at two to three times the play they cover when the prompt is bounded.
  4. **A comparison between arms is dear**: \$165 to \$208 of play for two arms at the
     measured values, \$93 to never across the intervals.
  5. **The judges agree with each other** (κ 0.80) and with the owner's blind answers on 18
     of the random 20. On touched pairs the blind answers differed on 9 of 12 and the
     checked answers on 2 of 12. Which is nearer the truth on engagement is not known.
- **What is wrong with what we built.** Its code names no game, but its schema and
  instructions assume places and goods: required places and game times, a fixed
  `place_with_goods` kind, judge labels about going to a place. The format was designed
  around places and goods after the four losses, though the brief named none of them. The rows are added to the architecture's
  [current coupling](../architecture.md#game-family-portability) table.
- **Proposal.**
  1. **Format.** Drop the fixed kinds and the required place and time; keep ADR 009's
     model-proposed types, citations and order of sighting. Add retiring and merging.
  2. **Curator.** A consolidation session between admissions merges and retires facts.
     No hard cap until growth after consolidation shows one is needed.
  3. **Delivery.** The briefing stays as the context design has it. A recall model,
     not a kind, chooses which facts each actor gets in full. During play it may add a
     short reminder, or say nothing, as a notice that stays in the history.
  4. **Measurement.** Use of memory is judged on every sealed run. Benefit is measured by
     withholding a random half of the store, by subject, within each start, once a
     simulation has sized it.
  5. **Judges** stay the standing measure, with the owner's blind labels as truth and
     prediction-powered inference for intervals.
- **Not known.** Whether a recall model helps or distracts in this game; the withholding
  design's power; whether consolidation alone holds the store's size; whether the
  owner's blind answers or the judges are nearer the truth on engagement.
- **Owner decisions:** six, [at the end](#owner-decisions). Some change standing
  decisions, and each says which.

Terms are in the [glossary](../glossary.md).

## The principle

The charter's [portability constraint](../charter.md) and P-GENERALITY, and the owner's
instruction to follow the bitter lesson: prefer general methods that improve as models
improve over hand-built knowledge of one game.

- **The model decides what matters**: what to record, how to word it, what to merge or
  retire, and what is relevant now. Software keeps what no model should decide:
  provenance, order, versions, the gate's structural checks and the cache rule.
- **No rule names a kind of thing in a game.** "Goods have a place" or "drop facts older
  than a day" are guesses about one game.
- **Measures are worded in game-neutral terms**, and the facts they judge come from the
  trace and the store, not a list written in advance.

## 1. The fact format and the curator

### The format, `curator-fact/3`

| Field | Required | Meaning |
| --- | --- | --- |
| `schema`, `id` | yes | as now |
| `type` | yes | a type from the ontology, proposed and kept by the system as [ADR 009](../decisions/009-curated-player.md) decided |
| `text` | yes | one durable claim, in the curator's words; where and when, when they matter, are in the text as the screen showed them |
| `citations` | yes | frame source ids inside the session's window, checked by the gate |
| `subject` | no | a short name for what the fact is about, when it is about one thing |
| `seen` | written by software | the trace position of the latest cited frame: an order, not an age, since one step can span hours of play |

- **Removed:** the four fixed kinds, `place`, `game_time`, and `statement` (renamed
  `text`). `scope.game` stays.
- **Operations:** `add_fact`, `supersede_fact` with one or more ids, `retire_fact` with
  a reason and citations, and `add_type`.
- **Migration.** One contract with no shim (S-MIGRATION). The brief gate's
  `brief-gate` check reads only `curator-fact/2`; it served one finished gate and is
  retired with the migration (R-TECH-DEBT). Sealed stores stay as evidence.

### Consolidation

- **The curator already sees the published facts** and is told not to repeat them. What
  it lacks is a way to retire or merge them, and a brief that does not ask for every
  item.
- **A consolidation session between admissions** reads only the store and the last
  admission's citations: it merges facts about one subject, retires facts a later frame
  contradicts, and ranks facts for the briefing. Outside systems that edit against what
  exists (Mem0, Memory-R1, Letta's sleep-time agents) keep their stores more compact.
- **No hard cap.** The owner decided on 13 November that added text has no hard cap until
  experience shows one is needed. Growth after consolidation is that experience; it is
  measured before a cap is proposed.
- **Facts are hypotheses.** Each is shown with its sighting order, and the player is told
  to check a fact cheaply before relying on it. Outside work finds agents follow stale
  notes into harm.

### How the curator improves

- **Scored on sealed replays.** A curator variant runs over a fixed set of sealed
  admissions, and the judges score its store against what later frames needed: facts the
  player later acted on or found again, weighted above facts never needed again. The
  existing probe annotations (`data/evaluation/probes/397`) already mark re-observations.
- **The four lost facts become one test among many**, so a brief cannot be tuned to them.
- **Cost** about \$16 a variant at the brief gate's rates; a consolidating curator may
  cost more, and the first run measures it.

## 2. Delivery: making the player use memory

The read audit found 8 memory reads in 98 traces and none by an admission's first actor
([record](../acceptance/2026-11-13-memory-read-audit.md)). Outside work finds the same:
models under-use memory they must ask for (MemTrack). So the player should not have to
ask. The [context design](player-context.md#2-a-briefing-from-the-curators-store) already
puts a briefing in every actor's first message and appends later differences as new
messages, which keeps the provider's cache: every request extends the previous one byte
for byte (`tools/player_host/host.mjs`, the notice rule). This note keeps that and
changes two things.

1. **A recall model chooses the full items.** The context design shows in full "open
   commitments, known hazards, the places with goods, and what the player has learned
   about how the game works", by kind, and one index line for every other item. With the
   kinds gone, a recall model reads the mission, the previous final report and the
   store's index, and chooses which facts each actor gets in full. Every other fact keeps
   its index line, readable with `player_memory_read`. Relevance is judged by a model, so
   it holds for any game.
2. **Reminders during play.** At a fixed cadence (every N decisions, N set by the first
   development play), the recall model reads the player's recent tool calls, the latest
   screen and the index, and answers with up to a few fact ids and a line each, or with
   nothing. It runs beside the player and never blocks it; its answer is added as a notice
   to the next request after it finishes, and stays in the history, so the cache holds.
   A reminder may arrive a decision or two late.

**What it costs.**

- **Prompt.** Reminders stay, so each adds its tokens to every later request in that
  actor. The recall model's silence keeps that small; the first development play
  measures it.
- **Dollars, inferred.** If a recall request costs what a curator request does, about
  \$0.02 at the pilot's rates (\$2.34 over 112 requests), one every five decisions is about
  \$0.004 a decision. Play with a bounded prompt costs about \$0.006 a decision by the
  [context design](player-context.md)'s figure, and \$0.003 to \$0.004 in the pilot's
  windows under 60,000 tokens. So recall adds about two thirds to about the same as play.
  A recall request reads one screen and an index, against a curator's frames and files,
  so it may cost less; a smaller model would cost less again. The first development play
  measures it.
- **Risk.** In the closest outside study a proactive memory agent beside an actor raised
  task success by 2.5 to 8 points, and an untrained small one lowered it. Every reminder
  and every silence is logged and judged.

**Citations.** The decided `intent` and optional `cites` fields, once built, let the
player cite a fact id it acted on. Citations are evidence for the judges, not proof of
use.

**Not proposed:** the cut, which is a decision of its own below; a whole-store briefing;
relevance decided by keywords or embeddings alone (an embedding may pre-filter for the
recall model); triggers built on signs of no progress, which are hand-set and fire on
ordinary movement in this game; a required "memory checked" field.

## 3. Measurement

### Is memory used? On every sealed run

For each fact delivered in full or by a reminder, and each fact on the index, the judges
label each stretch in which the fact could matter:

- **Acted in line with it**: the player did what the fact supports.
- **Acted against it**: the player did what the fact advises against, or went where the
  fact says is empty or gone.
- **Found it again**: the player discovered by looking what the fact already said.
- **Did not apply**, or **cannot tell**.

These labels fit any fact: a place, a hazard, a rule, a procedure or a commitment. From
them come the use rate of delivered facts, re-discovery, acting on a stale or false fact,
and the recall model's precision and silence. Judging is done by host agents, \$0 on the
provider; the coding host's capacity is its cost.

### Does memory help? Withholding within each start

- **Design.** In each start a random half of the store's units (drawn per start, seed
  recorded) is withheld: their facts are left out of the full items, the index and the
  reminders. A unit is a subject, where facts have one; otherwise a supersede chain, or a
  single fact. The consolidation before the start merges subject names, so one thing is
  one unit.
- **Outcome.** For every fact, over the whole start: was it found again, acted against,
  or acted in line with? Whether a fact "became relevant" is judged only as a secondary
  measure, because delivering a fact can create the need for it.
- **Blind judging.** For this measure the judges and the owner see frames and inputs
  only: the briefing, the reminders and the player's own `intent` and `cites`, which can
  name delivered facts, are removed. Only the use labels read them.
- **What it estimates.** The effect of delivering a fact while half the store is
  delivered. It cannot see a harm to play as a whole, such as a distracting reminder;
  that is seen in the use labels and in time spent per decision.
- **Threats.** Handoff summaries and the previous final report can restate a withheld
  fact; facts the curator writes during a start are not randomized; the player's own
  records can hold a withheld fact while that store still exists. These bias towards no
  effect.
- **Before any spend** the protocol's simulation is adapted to this design with the
  measure gate's numbers, to give its size and price.

### Game-neutral judging

- Packets are cut to a token budget, not to 200 decisions or 60 frames.
- The annotators list every fact the frames show a later actor could use, not only
  places with goods.

## 4. Judges as the standing measure

- **Two judges on everything and a third on disputes**, all host agents. The dispute rate
  is the health signal; it was 6.2% at the measure gate. Judges from a second model
  family would reduce shared blind spots but may need a paid provider; that is not
  proposed now.
- **Windows, not steps.** Judges label a window and cite frames; outside work finds them
  weak at finding the one wrong step in a long trace (TRAIL).
- **The owner's blind labels are the truth**, as the owner decided on 13 November. The
  check pass after them stays, reported apart.
- **Intervals.** Every reported rate combines all judge labels with a small audit of the
  owner's blind labels by prediction-powered inference. A uniform random audit uses PPI++;
  an audit weighted towards disputes or rare labels uses known sampling probabilities
  (active statistical inference, or stratified PPI). Clustering by run is an extension of
  these papers, by bootstrap over runs. If the estimator's weight on the judges is near
  zero, the judges add nothing, and that is reported. The audit costs about 30 to 60 pairs
  of the owner's time per study.
- **An anchor set.** About 30 audited pairs are re-judged after any change to a judge's
  prompt or model. Risk R-FALSE-CLAIM: a changed judge silently shifts every later
  measure; the anchor set shows the shift; it costs one judging pass of 30 pairs.
- **Known judge risks**: leniency, missing evidence in long contexts, and errors shared by
  both judges.

## Changes to the context design

If the owner decides as recommended, [player-context.md](player-context.md) changes:

- The briefing's full items are chosen by the recall model, not by kind; index lines
  carry the subject and the sighting order, not a place and a game time.
- In the curator's table, the rows "one fact per item, with game time and place", the
  four kinds, and "a brief aimed at places and goods" are replaced by this note's format
  and consolidation.
- Reminders during play are added as a new layer between the briefing and the cut.

## Owner decisions

1. **The fact format.** Drop the fixed kinds and the required place and game time; keep
   ADR 009's types; add retiring and merging. *Recommended: yes.* Changes the context
   design's curator rows. Cost: \$0 to build; the curator is re-scored on sealed
   replays (decision 6).
2. **Store growth.** Consolidation sessions between admissions, and no hard cap until
   growth after consolidation shows one is needed. *Recommended: yes*, as the 13 November
   decision on caps asks. The alternative, a byte budget the gate enforces now, reverses
   that decision.
3. **Delivery.** The full items chosen by a recall model at each actor's start, built
   first; reminders during play built next, behind a measurement of their silence and
   use. *Recommended: yes.* Cost: \$0 to build; in play, inferred at about two thirds to
   about the same as the cost of play at one recall request every five decisions, less
   with a smaller model.
4. **The cut.** The pilot has reported, and the protocol left the cut to be decided then.
   *Recommended: not yet.* Delivery at the moment of need may matter more than holding the
   prompt under 60,000 tokens, and it is measured first. Cost: \$0 now.
5. **What replaces the comparison.** Simulate withholding within each start (\$0) and put
   its price to the owner, instead of funding the comparison (\$165 to \$208 at the
   measured values) or only development play without a measure of benefit.
   *Recommended: simulate withholding.*
6. **Judges and later spend.** The judge protocol above, with the owner's time limited to
   about 30 to 60 blind audit labels per study. Spend on curator-variant scoring (about
   \$16 a variant) and on development play with withholding is asked later, priced.
   *Recommended: yes.*

## Limits

- **The outside evidence was read in summaries**, and none of it is on games played from
  screenshots. Figures quoted from it are leads.
- **No source runs withholding inside long game episodes**; the design is new here.
- **The recall model's benefit is shown on other kinds of task**, and an untrained small
  one did harm there.
- **One game and one lineage** produced every measured number here.

## Sources

Read on 13 November 2026, mostly as summaries.

- Proactive memory agent beside an actor:
  [Remember When It Matters](https://huggingface.co/papers/2607.08716).
- Models under-use memory tools: [MemTrack](https://arxiv.org/abs/2510.01353).
- Editing memory against what exists: [Memory-R1](https://arxiv.org/abs/2508.19828);
  Mem0. Offline consolidation: [Letta sleep-time compute](https://letta.com/blog/sleep-time-compute).
- Context as a budget: [Anthropic, effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).
- Stale memory: [STALE](https://arxiv.org/abs/2605.06527);
  [When Memory Lies](https://arxiv.org/abs/2608.04574).
- Judges: [AgentRewardBench](https://arxiv.org/abs/2504.08942);
  [Online-Mind2Web](https://arxiv.org/abs/2504.01382);
  [TRAIL](https://arxiv.org/abs/2505.08638).
- Judges with few human labels: [PPI](https://arxiv.org/abs/2301.09633);
  [PPI++](https://arxiv.org/abs/2311.01453);
  [active statistical inference](https://arxiv.org/abs/2403.03208);
  [stratified PPI](https://arxiv.org/abs/2406.04291).
