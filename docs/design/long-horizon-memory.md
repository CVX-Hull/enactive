---
owner: lead
status: proposed
date: '2026-11-13'
scope: 'Diagnosis of the player''s memory in recorded long play and of the curator memory study''s result, what memory must do for long-horizon play, six design options with a recommendation, and the shape of an experiment that could decide it (#445, #463, #556); nothing here is adopted'
review_trigger: An owner decision on the memory direction, or new long-play evidence about memory
---

# Memory for long-horizon play: diagnosis and options

**Status: proposed, for the owner's decision.** Nothing here is adopted, and no study or
run is started by it. The owner's premise of 13 November 2026
([#441](https://github.com/CVX-Hull/enactive/issues/441#issuecomment-6854313488)) is
that Cataclysm DDA is not a short-memory decision problem: what matters now was often
seen days earlier, so memory is settled before any seven-day or other long run. This
note says what the recorded evidence shows, what the options are and which the lead
recommends.

**What this note does not yet answer.** The recorded evidence is about facts up to two
game days old, lost at the boundaries between model instances. Nothing recorded tests
whether a fact a week old reaches the model at the moment it matters inside a long run,
or how a store behaves after seven days of writing. The options below are judged
against that gap as well as against the recorded losses.

Terms used here:

- **Actor**: the model instance that is playing. A run uses one or two in turn.
- **Handoff**: one actor passing play to its successor inside a run.
- **Admission**: one frozen run. A **lineage** is a chain of admissions on one saved game.
- **Curator**: a second model that reads the play trace offline and writes a store of
  facts ([ADR 009](../decisions/009-curated-player.md), proposed).

## What memory the player has today

From the code, checked on 13 November 2026:

- **One store, written only by the player's own choice.** Records go into one SQLite
  store through the `player_memory_append` tool. Nothing is deleted or edited; a
  correction is a new record that names the one it replaces
  (`harness/player/memory.py`, `harness/player/contracts.py`).
- **Nothing is put in front of the model at a decision.** The prompt is the package's
  fixed text. A record reaches the model only when the model calls a memory tool.
- **The only search is by kind and recency.** `player_memory_query` returns the newest
  records, optionally of one kind, at most 50. There is no search by text, place or
  subject (`harness/player/memory.py:127`).
- **The conversation is not compacted.** Old images are dropped in blocks; when the
  context is nearly full the host tells the actor to hand off or finish
  (`tools/player_host/host.mjs`).
- **A handoff carries a packet the outgoing actor chooses**: up to 32 record roots and
  a summary of up to 8,192 characters. The successor gets no transcript.
- **A new admission carries only the previous final report**, plus whatever the new
  actor chooses to query.
- **Records carry wall-clock time only.** There is no game-time field and no handling
  of outdated records beyond the replacement link.
- **The curator is not part of live play.** Its code runs only from the offline runner
  `tools/curator_host/shadow.py`; no player code reads its store.

## Where it failed in recorded long play

The figures are from [ADR 009's problem section](../decisions/009-curated-player.md),
the [seven-day lineage record](../acceptance/2026-11-07-seven-day-397.md) (#397), the
[probe baseline](../acceptance/2026-11-08-probe-baseline-449.md) (#449) and the sealed
host traces of that lineage. They are development evidence from one lineage on one
route.

- **The player barely wrote.** In the seven-day lineage it made 12 append requests in
  1,969 tool calls, all in the last minute before a handoff. Its final store holds 11
  records, 9 of them status snapshots.
- **The player barely looked.** Across the 83 actor traces of that lineage and the
  earlier development runs, `player_memory_query` was called 7 times. In the seven-day
  lineage only three actors queried: the second actors of `sd1a2`, `sd1a3` and `sd1a4`.
  No actor of `sd1a5`, `sd1a6` or `sd1a7` did.
- **Admission boundaries lost most.** A handoff kept about 0.62 of what the outgoing
  actor held; an admission boundary, where only the final report crosses, kept 0.32.
  The lineage re-found 210 things it had already seen, 4.39 per game hour.
- **Four known facts were lost and the loss cost play.** They failed in three different
  ways:

| Known fact | What the trace shows | What happened later | Failure |
| --- | --- | --- | --- |
| A roof tank held 18 L of clean water | `sd1a3` tried to record it; the append stayed pending and the fact survived only in a handoff summary | `sd1a4` fetched dirty water from a lake and boiled it | Never stored |
| 20 ration boxes in a cupboard | Record `5db17f`, written in `sd1a5`; no later actor's trace contains it | `sd1a6` and `sd1a7` worked on 25 kcal stalks | Stored, never delivered |
| A fishing rod on the floor nearby | Record `94ce47`, written in `sd1a2`; a query returned it in `sd1a2`, `sd1a3` and `sd1a4`, and never after | `sd1a5` to `sd1a7` tried to craft one | Stored, not delivered to the actors that needed it |
| Batteries in the locker | Record `f49b80`, written in `sd1a1`; a query returned it to `sd1a3`'s second actor, whose handoff packet said the flashlight was empty | That actor's trace does not mention the flashlight or the batteries again | Delivered, not used |

- **The death was not a memory loss.** The fire hazard was carried in record `cb18d4`
  and in the handoff summary; the record calls the death a judgment failure.

Two things were looked for and not found in the records: a store that grew too large,
and a decision made on a stored record that was wrong. Almost nothing was stored, so
neither had a chance to occur.

So there are three failures, not one: facts that were never stored, stored facts that
never reached the actor who needed them, and at least one fact that was put in front of
an actor and not used. A design that fixes only carry leaves the third.

## Why the curator memory study ended in a no-go

The study (#178, with the held-out lineage of #522) compared two ways to add a text of
at most 2,000 tokens to what a successor received at each of 23 boundaries
([protocol](p1-study-3.md), [completion record](../acceptance/2026-11-12-p1-descriptive-completion-178.md)):

- **The own-records arm** added the player's own records, newest first, with no model
  calls.
- **The curator arm** added facts from the store a curator session would have
  published, run once per admission, twice over.
- **Reference** was what the successor actually received in play, with nothing added.

Two results must be kept apart.

**The registered no-go is a cost-cap event.** The protocol said a repeat that reaches
its spending cap fails. The curator arm's second repeat reached its cap after several
interrupted attempts: provider timeouts, rate-limit refusals, a stop on a disk
free-space floor that has since been removed, and failed requests charged at their
whole worst-case reservation
([cost-guard record](../acceptance/2026-11-11-p1-cost-guard-178.md)). The cap fired with
$57.62 allocated against a $59.34 limit, because the next reservation did not fit. The
first repeat ran clean and cost 0.34 of the actor's spend. Counted conservatively, the
second repeat finished at 1.06 of the actor's spend, above the limit of 1.0. No benefit
data existed when the no-go was registered.

**The measurement, finished afterwards for discussion, is also negative.** By the
frozen rule a mean difference of zero or below is the outcome "Negative", and the
difference was −5.62 points (one-sided 97.5% bound −11.24).

| | Own records | Curator, both repeats | Reference |
| --- | ---: | ---: | ---: |
| Questions answered, of 89 | 18 (20.2%) | 13 (14.6%) | 12 (13.5%) |
| Of the 77 that Reference missed | 7 | 2 | |
| Sampled items contradicted or outdated, of 40 | 29 (72.5%) | 1 and 2 (2.5%, 5.0%) | not sampled |

What it measured: whether a reader, given the received text and the added text, could
answer one question about a screen the player had seen before and later looked at
again. A control that put the answer in the text scored 89 of 89, so the reader was not
the limit.

What it did not measure, by the protocol's own words: whether the text was used,
anything learned through a different screen, facts the player needed but did not
re-observe, or any effect on play.

What can and cannot be read from it. These are the lead's inferences, not registered
findings:

1. **Neither added text helped much.** The own records added 7 answers on the 77
   questions Reference missed, and the curator's facts added 2. About four fifths of
   what the player went back to look at was answerable from neither text.
2. **The study scored capped text, not the stores.** Both texts were cut to 2,000
   tokens, newest first, and in the longest lineage both were close to the cap. Whether the missing answers
   were absent from the store or were cut by the cap is not known.
3. **Timing does not explain the curator's result.** It had nothing to deliver at four
   of the 23 boundaries, by design. But at the ten admission boundaries, where it
   delivered a fresh snapshot of 737 to 1,999 tokens, it still answered no more than
   Reference (4 of 36 questions).
4. **Currency and recall may be one trade, not two wins.** The player's records often
   copy the screen's wording, which is what a question about a screen rewards, and such
   snapshots go out of date quickly. The curator's short paraphrased facts were current
   and answered fewer questions. A design that takes "the own records' recall and the
   curator's currency" may not exist.
5. **The outdated count is per record, and the player's records are compound.** One
   record holds a danger, a place, a plan and a list of goods. One outdated clause
   makes the whole record count as outdated, and would make a tool that retires
   outdated records throw away true ones.

So the study shows that a once-per-admission curator, under a 2,000-token cap, did not
beat the player's own notes on recall of screens seen again, and cost more than its
limit in one of two repeats. It does not test any design that puts a fact in front of
the model when it is needed, and it does not measure play.

## What memory must do for this game

| Kind of knowledge | Example | Useful for | Goes out of date when |
| --- | --- | --- | --- |
| Places and what is in them | The cupboard with rations; the tank on the roof | Days | The thing is used, moved or lost |
| Current state and commitments | What is being crafted; the plan for tonight; a fire is lit here | Minutes to hours | Almost at once; it is replaced, not kept |
| How the game works | A key; what a recipe needs; that crafting beside a fire is dangerous | The whole game, and other worlds | Rarely |
| What happened | The full trace | Checking the others | Never; it is the record |

Requirements that follow from the evidence:

- **Writing cannot depend on the model remembering to write.** Twelve appends in 1,969
  tool calls is the measured rate when it is optional.
- **Recall cannot depend on the model remembering to look.** Seven queries in 83 traces.
- **A fact must be in view when it matters, not only at a boundary.** The batteries
  case shows that delivering a record once is not enough.
- **One fact per record.** Compound records cannot be kept current clause by clause.
- **Each item carries game time and place, written by the player as text.** The harness
  stores and shows them and never interprets them, so no game knowledge moves into the
  harness (P-GENERALITY).
- **What is shown is small.** A long injected text degrades use of it.
- **Lookup works by subject.** "Where did I see batteries?" cannot be answered by "the
  newest 50 records".
- **The trace stays the ground truth**, so that a wrong item can be checked.

## Evidence from outside the project

Read by the lead on 13 November 2026 through a tool that summarises each page. The
project's own research pages hold the earlier reading
([curated memory](../research-curated-memory.md), 8 November 2026).

| Source | Date | What it reports | Limit |
| --- | --- | --- | --- |
| Anthropic, [The components of agent memory](https://anthropic.com/research/components-of-agent-memory) | 6 November 2026 | Layers: a searchable transcript, notes the agent writes, further representations such as a wiki, an offline pass that corrects them, and a small text loaded every session. In one Pokémon case a run with a corrected note reached the next city at action 1,935; the run with the uncorrected note fell back three times and did not reach it in 3,000 actions; the run without memory did not reach it | A single case; the vendor's own tests |
| Karten et al., [Continual Harness](https://arxiv.org/html/2605.09998v1) | 11 May 2026 | Agent-edited memory with a periodic refiner that updates outdated entries; the titles of stored memories are listed in every step's prompt and the agent asks for the full entry. On Pokémon Emerald the strongest model completed 100% of milestones at a median $130, against 98% at $215 for a minimal harness; the weakest model did worse with it. Most stored entries were never read | One game family; weak models lose |
| He et al., [MemoryArena](https://arxiv.org/html/2602.16313v1) | 18 February 2026 | Tasks where later sessions depend on earlier ones. Agents that score near the top of recall benchmarks do poorly, and external memory does not reliably beat keeping the full history | Not games; one task model |
| Zhao et al., [AMA-Bench](https://arxiv.org/html/2602.22769v4) | Version 4, 27 May 2026 | Questions over real agent trajectories, some from games. Keeping the long context "is consistently strong"; memory systems that compress often do worse | Questions, not task success |
| Chao et al., [STALE](https://arxiv.org/html/2605.06527) | 7 May 2026 | When a stored fact has silently become false, the best model is right 55.2% of the time; retrieval found the newer evidence in 77.5% of cases and answers still failed. Deciding keep, stale or replace at the time of writing raised a small model from 8.7% to 68.0% | Conversation data; needs a fixed schema |
| Cheng et al., [AgenticSTS](https://arxiv.org/html/2607.02255) | 2 July 2026 | A card game played with a prompt rebuilt at every decision and no accumulating transcript. Wins: 3 of 10 with no memory layers, 6 of 10 with them; the authors call it "directional rather than statistically decisive". The same memory lowered one other model's score by 18.1% | Ten games per condition; no matched accumulating-context comparison |

What this supports, with the project's own results:

- **Compressing loses detail and unreviewed notes go wrong.** Both halves of the
  study's result appear elsewhere.
- **Showing the model what it has stored, at every step, is used in practice**, and
  even then most entries go unread.
- **Recall scores do not predict task results.** A decision should rest on play.
- **A memory design that helps one model can hurt another.**

What it does not settle: no source compares these designs on game progress over tens
of thousands of decisions, and none plays from screenshots alone.

## Options

The actor alone cost $0.53 to $1.04 per game hour in the recorded lineages.

### 1. Keep the current memory

- **Mechanism.** As today.
- **For.** No cost; no new machinery.
- **Against.** Every failure above.
- **Falsified by** a long lineage with a rediscovery rate well under the recorded 4.39
  per game hour and no costly loss.

### 2. Carry by the harness, written by the player

- **Mechanism.** The harness stops leaving carry to chance:
  - every new actor and every new admission starts with a working set of the player's
    current records, so an admission boundary carries as much as a handoff;
  - the handoff and finish steps require the actor to record or confirm its open
    facts, one per record, each with game time and place, and to mark replaced ones;
  - the working set is chosen by kind, not only by recency: places and rules are kept,
    and of state snapshots only the newest.
- **For.** It addresses "never stored" and "never delivered", three of the four losses.
  The study's own-records arm added answers over Reference (7 of 77).
- **Against.** That arm's items were 72.5% contradicted or outdated. It does nothing
  for "delivered, not used". It keeps the actor as a writer, which the owner's decision
  D1 in ADR 009 moved away from ("the actor … does not maintain the banks").
- **Cost and cadence.** The [snapshot-diff estimate](snapshot-diff-cost.md) prices one
  2,000-token addition at $0.011 to $0.026. No added model call, so no added latency
  per decision.
- **Other games.** Game-neutral: it moves the player's own text.
- **Falsified by** a live comparison in which rediscovery does not fall, or in which
  the player acts on outdated items it was shown.

### 3. A cue in view at every decision

- **Mechanism.** A short index of what is stored stays in the prompt: one line per
  record, with its place and game time, grouped by place. The actor reads a full
  record by its line. Query gains search by text. The index changes only when a record
  is written.
- **For.** It is the only option aimed at the moment of need inside an admission, which
  is the owner's premise and the "delivered, not used" failure. Continual Harness does
  this at every step.
- **Against.** That source also reports most entries unread. The index grows with the
  store; over seven days it needs a size limit and a rule for what drops out. Each
  change to it costs a prompt-cache write.
- **Cost and cadence.** Not measured. The snapshot-diff estimate recommends at most
  about 2,000 tokens of such text live. No added model call.
- **Other games.** Game-neutral.
- **Falsified by** a live comparison in which stored facts in the index are still
  re-found at the same rate.

### 4. The curator, repaired

- **Mechanism.** ADR 009's design with the study's faults addressed: a session at each
  handoff as well as each admission; a brief aimed at places and goods; one fact per
  item; a failed request counted at a fixed bound, as player runs now are (#556).
- **For.** Very few outdated items (1 and 2 of 40). The trace is its input, so it does
  not depend on the player writing. It is the owner's direction in ADR 009.
- **Against.** It added 2 answers of 77 in the one test, even with a fresh snapshot. A
  second model and a sandbox to run and pay for. A median lag of 47 decisions in the
  [shadow run](../acceptance/2026-11-08-curator-shadow-454.md).
- **Cost and cadence.** 0.34 and 1.06 of the actor's spend in the study's two repeats;
  0.61 to 0.87 in the shadow run ($0.49 per game hour on the seven-day lineage). It
  runs between decisions, so it adds no latency per decision; an admission boundary
  waits for a session (median 189 s).
- **Other games.** The epistemic core is game-neutral; the brief and types are per
  game.
- **Falsified by** a live comparison in which it does not beat options 2 and 3 at its
  added cost.

### 5. The player's notes, corrected offline

- **Mechanism.** Options 2 and 3, plus an offline pass between admissions that reads
  the trace and the player's records, marks single-fact records the trace shows are
  outdated, and adds facts the player saw and did not record.
- **For.** It is the layered design the Anthropic source describes, and it reuses the
  curator's sandbox, gate and trace projection, which exist.
- **Against.** Unmeasured as a whole. Reading the whole trace is what made the curator
  cost what it did, so this pass is unlikely to be cheaper than the curator. The study
  suggests currency and recall trade against each other. The pass can be wrong.
- **Cost and cadence.** Expect the curator's range, 0.34 to 0.87 of the actor's spend,
  until measured. No latency per decision.
- **Other games.** As option 4.
- **Falsified by** the pass adding no measurable gain over options 2 and 3 alone.

### 6. A prompt rebuilt at every decision

- **Mechanism.** No accumulating conversation. Each decision gets a freshly composed
  prompt: current screen, state, and selected memory.
- **For.** Bounded context; memory is the only carrier, so it cannot be skipped.
- **Against.** It replaces the player host's whole context model and discards the
  in-context continuity the current player relies on within an admission. The one
  source is directional at ten games per condition.
- **Cost and cadence.** Smaller prompts would be cheaper and faster per decision, but
  each loses the provider's prompt cache; unmeasured.
- **Not recommended now**: a rebuild whose benefit rests on one small study.

## Recommendation

**Build options 2 and 3 together as the first step, and decide the next step on play.**

- The recorded losses have three causes, and options 2 and 3 between them address all
  three with no second model. Neither alone does.
- Every later option needs their parts: single-fact records with game time and place,
  a working set, an index, search.
- They are the cheapest to build and to run, and they add no latency per decision.

**The curator (options 4 and 5) stays proposed and is not built further until the first
step has been measured in play.** The one test of it was negative on recall and over
its cost limit in one of two repeats; its strength, currency, only matters once the
player is being shown stored facts.

This recommendation departs from the owner's decision D1 in ADR 009, under which the
actor does not maintain the store. The first step keeps the actor as the writer because
no tested alternative writes better. If the owner holds to D1, the first step is option
3 over a curator-written store, at the curator's cost.

Option 6 is recorded and set aside.

## The experiment that could decide it

It has to measure play, not recall. This section gives its shape. A protocol with a
threshold and a check that the measure can detect the effect comes before any spend, as
[the evidence standard](../standards/evidence.md) requires, and is a separate owner
decision.

**Free steps first, no model calls:**

1. **Trace audit.** For each of the seven recorded queries, list what was returned and
   what the actor did in the following decisions. It shows how often a delivered
   record changed play.
2. **Replay of the four losses.** For each, compute whether the working set and index
   of the first step would have held the fact at the point where it was lost.

**Then a live screen with many short starts, not a few long ones:**

- **Why short.** Cost per game hour ran from $0.20 to $11.30 between admissions of one
  lineage, and rediscovery from 0.75 to 4.39 per game hour between lineages. Two long
  continuations per arm could not separate an effect from that spread.
- **Start.** A copy of the sealed saved game of the held-out lineage (#522), which
  ended alive at 27.76 game hours. Its records are rewritten once, by hand, into
  single facts with game time and place, the same for both arms. Using it ends that
  lineage's held-out standing.
- **Arms.** The current player; the player with the first step. Runs happen one after
  another, never two games at once.
- **Size.** Six starts per arm, first actor only, about 150 decisions each: about 1,800
  decisions, about $36 at the recorded $0.02 per decision. A $60 envelope is proposed.
- **Measure.** How often the actor goes back to look at something the lineage had
  already seen, counted mechanically against the lineage's frozen frames and fact
  ledger, with the threshold fixed in the protocol. The blinded annotation of the probe
  baseline is not used: it reproduced none of the four known losses in full.
- **Stop.** The envelope, or a pilot start that fails.

| Outcome | Meaning | Next |
| --- | --- | --- |
| Going back falls by the protocol's threshold | Carry and cue work at one to two days | Test the same at the longest horizon available, then decide on long runs |
| It falls, and the player acts on outdated items | Currency is now the limit | Test the offline correction pass, or the curator |
| No change, and the check showed the measure could have detected one | The player has the facts in view and does not use them | The problem is use, not memory; a different design is needed before any long run |

**What this screen cannot show.** Its oldest fact is about 28 game hours old, and each
start is one actor. It tests the first step at one to two days, not the week the
premise speaks of. No sealed saved game is older; a week-old store exists only after a
longer run.

Whether a copy of a sealed saved game may be continued, one game at a time, is an owner
decision. It is narrower than ADR 009's practice instance, which runs beside live play.

## What this means for the open items

These are proposals. Each is an owner decision.

- **ADR 009.** The curator and memory phase is not adopted and its study is closed.
  The proposal is to reach working memory by the first step, with the curator held
  until that is measured. The ADR's belief model and ontology stay open and are not
  needed for the first step.
- **[#463](https://github.com/CVX-Hull/enactive/issues/463)**, adopting the curator
  and memory phase: waits for the screen. Its migration would then cover the first
  step.
- **[#470](https://github.com/CVX-Hull/enactive/issues/470)**, programs and monitor:
  unchanged and after memory.
- **[#472](https://github.com/CVX-Hull/enactive/issues/472)**, the practice instance:
  unchanged. The screen needs only a sequential copy.
- **[#441](https://github.com/CVX-Hull/enactive/issues/441)**, the seven-day screen:
  parked under the owner's premise of 13 November 2026, which replaces its earlier
  triggers. It could later serve as the first week-long test of memory.
- **[#556](https://github.com/CVX-Hull/enactive/issues/556)**, how the curator charges
  a failed request: the lead recommends a fixed bound, as player runs use. Charging
  the whole reservation helped end the study's second repeat. The change would be made
  when curator sessions next run.
- **Responsiveness** ([#442](https://github.com/CVX-Hull/enactive/issues/442)): the
  first step adds no model call per decision. It adds prompt text, whose cost the
  cadence plan's budget for added text should cover.

## Limits of this note

- The live evidence is one lineage of 47.79 game hours on one route, and four lost
  facts.
- The readings of the study are inferences from its descriptive tables.
- External pages were read through a tool that summarises them; figures are as that
  reading gave them.
- No cost is measured for options 3, 5 or 6.
- The screen's measure is proposed, not validated; the protocol must show it can detect
  an effect before anything is spent.
