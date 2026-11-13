---
owner: lead
status: proposed
date: '2026-11-13'
scope: 'Diagnosis of the player''s memory in recorded long play and of the curator memory study''s result, what memory must do for long-horizon play, five design options with a recommendation, and the experiment that could decide it (#445, #463, #556); nothing here is adopted'
review_trigger: An owner decision on the memory direction, or new long-play evidence about memory
---

# Memory for long-horizon play: diagnosis and options

**Status: proposed, for the owner's decision.** Nothing here is adopted, and no study or
run is started by it. The owner's premise of 13 November 2026
([#441](https://github.com/CVX-Hull/enactive/issues/441)) is that Cataclysm DDA is not a
short-memory decision problem: what matters now was often seen days earlier, so memory is
settled before any seven-day or other long run. This note says what the recorded evidence
shows, what the options are and which one the lead recommends.

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
the [seven-day lineage record](../acceptance/2026-11-07-seven-day-397.md) (#397) and the
[probe baseline](../acceptance/2026-11-08-probe-baseline-449.md) (#449). They are
development evidence from one lineage on one route.

- **The player barely wrote.** In the seven-day lineage it made 12 append requests in
  1,969 tool calls, all in the last minute before a handoff. Its final store holds 11
  records.
- **The player barely looked.** Across all 83 actor traces of that lineage and the
  earlier development runs, `player_memory_query` was called 7 times.
- **Most of what it wrote was a status snapshot.** Of 78 records in 34 sealed stores,
  57 are of kind `work`.
- **Four known facts were lost and the loss cost play**, all in the seven-day lineage:

| Known fact | Where it was | What happened later |
| --- | --- | --- |
| A roof tank held 18 L of clean water | Only in actor `sd1a3`'s handoff summary; its record was never committed | `sd1a4` fetched dirty water from a lake and boiled it |
| 20 ration boxes in a cupboard | Record `5db17f`, written in `sd1a5` | `sd1a6` and `sd1a7` worked on 25 kcal stalks |
| A fishing rod on the floor nearby | Record `94ce47`, written in `sd1a2` | `sd1a5` to `sd1a7` tried to craft one |
| Batteries in the locker | Record `f49b80`, written in `sd1a1` | `sd1a3` reported a dead flashlight and a dark basement |

- **Carry across boundaries was low.** Over the lineage's 13 boundaries, 26% of live
  facts and 36% of needed facts were carried. The lineage re-found 210 things it had
  already seen, 4.39 per game hour.
- **The death was not a memory loss.** The fire hazard was carried in record `cb18d4`
  and in the handoff summary; the record calls the death a judgment failure.

Two things were looked for and not found in the records: a store that grew too large,
and a decision made on a stored record that was wrong. Almost nothing was stored, so
neither had a chance to occur.

The four losses are of one kind: **where a useful thing is**. One was never written.
Three were written and never looked up. The failure today is omission at both ends,
not bad content.

## Why the curator memory study ended in a no-go

The study (#178, with the held-out lineage of #522) compared two ways to fill a text of
at most 2,000 tokens pushed to a successor at each boundary
([protocol](p1-study-3.md), [completion record](../acceptance/2026-11-12-p1-descriptive-completion-178.md)):

- **Arm A** pushed the player's own records, newest first, with no model calls.
- **Arm B** pushed facts from the store a curator session would have published, run
  once per admission, twice over.
- **Reference** was what the successor actually received in play, with nothing pushed.

Two results must be kept apart.

**The registered no-go is a cost-cap event.** The protocol said a repeat that reaches
its spending cap fails. Arm B's second repeat reached its cap after several interrupted
attempts: provider timeouts, rate-limit refusals, a stop on a disk free-space floor that
has since been removed, and failed requests charged at their whole worst-case
reservation ([cost-guard record](../acceptance/2026-11-11-p1-cost-guard-178.md)). The cap
fired with $57.62 allocated against a $59.34 limit, because the next reservation did not
fit. The first repeat ran clean and cost 0.34 of the actor's spend. No benefit data
existed when the no-go was registered.

**The measurement, finished afterwards for discussion, is this:**

| | Arm A (own records) | Arm B (curator), both repeats | Reference |
| --- | ---: | ---: | ---: |
| Questions answered from the pushed text, of 89 | 18 (20.2%) | 13 (14.6%) | 12 (13.5%) |
| Sampled items that were contradicted or outdated, of 40 | 29 (72.5%) | 1 and 2 (2.5%, 5.0%) | not sampled |

What it measured: whether a reader, given only the pushed text, could answer one
question about a screen the player had seen before and later looked at again. A control
that put the answer in the text scored 89 of 89, so the reader was not the limit.

What it did not measure, by the protocol's own words: whether the text was used,
anything learned through a different screen, facts the player needed but did not
re-observe, or any effect on play.

Four readings follow, and they are the lead's inferences, not registered findings:

1. **Both arms missed about four fifths of what the player went back to look at.** The
   best arm answered 20%. The gap between the arms (5 questions of 89) is small beside
   what neither store held. Coverage is the first problem, and the study did not test a
   design that addresses it.
2. **Arm B had nothing to deliver early.** By design it delivered no facts at the
   handoffs of each lineage's first admission, and at the 36 admission boundaries it
   answered the same number as Reference (4).
3. **The player's own records go out of date fast.** Nearly three quarters of sampled
   Arm A items were contradicted or outdated, which is expected of status snapshots.
   Pushing them unreviewed would put stale statements in front of the model at every
   boundary. The study gave Arm B no credit for avoiding this, because it scored recall
   only.
4. **The study tested memory as a boundary note, not as working memory.** Every loss in
   the table above happened at a boundary, so this was a fair first target. It leaves
   untested what happens inside an admission, where the model must think of a fact at
   the moment it matters.

So the study does not show that curation fails. It shows that a once-per-admission
curator, scored on recall of re-observed screens under a 2,000-token cap, did not beat
the player's own notes, and that the player's own notes are mostly stale.

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
  Something must be put in front of the model, or a cue must be.
- **What is put in front of the model must be small and current.** Outdated statements
  are worse than none, and a long injected text degrades use of it (see evidence below).
- **Each item needs game time and a place**, so that an old item can be recognised as
  old and a newer one can replace it.
- **Lookup must work by subject.** "Where did I see batteries?" cannot be answered by
  "the newest 50 records".
- **The trace stays the ground truth**, so that a wrong item can be checked and
  corrected.

## Evidence from outside the project

Read on 13 November 2026. The project's own research pages hold the earlier reading
([curated memory](../research-curated-memory.md), 8 November 2026).

| Source | Date | What it reports | Limit |
| --- | --- | --- | --- |
| Anthropic, [The components of agent memory](https://anthropic.com/research/components-of-agent-memory) | 6 November 2026 | Layers: a searchable transcript, notes the agent writes, an offline pass that corrects them, and a small text loaded every session. In one Pokémon case a run with a corrected note reached the next city at action 1,935; the run with the uncorrected note fell back three times and did not reach it in 3,000 actions; the run without memory did not reach it | One run per condition; the vendor's own tests |
| Karten et al., [Continual Harness](https://arxiv.org/html/2605.09998v1) | 11 May 2026 | Agent-edited memory with a periodic refiner that updates outdated entries; memory titles listed at every step. On Pokémon Emerald the strongest model completed 100% of milestones at a median $130, against 98% at $215 for a minimal harness; the weakest model did worse with it. Most stored entries were never read | One game family; weak models lose |
| He et al., [MemoryArena](https://arxiv.org/html/2602.16313v1) | 18 February 2026 | Tasks where later sessions depend on earlier ones. Agents that score near the top of recall benchmarks do poorly; for precise reuse of earlier detail, retrieval over raw records was more robust than stores that compress | Not games; one task model |
| Zhao et al., [AMA-Bench](https://arxiv.org/html/2602.22769v4) | 27 May 2026 | Questions over real agent trajectories, some from games. Keeping the long context "is consistently strong"; memory systems that compress often do worse | Questions, not task success |
| Chao et al., [STALE](https://arxiv.org/html/2605.06527) | 7 May 2026 | When a stored fact has silently become false, the best model is right 55.2% of the time; retrieval found the newer evidence in 77.5% of cases and answers still failed. Deciding keep, stale or replace at the time of writing raised a small model from 8.7% to 68.0% | Conversation data; needs a fixed schema |

What this supports, with the project's own results:

- **Compressing loses detail and unreviewed notes go wrong.** Both halves of the
  study's result appear elsewhere. Neither is an artefact.
- **The layered design is the best supported**: the agent's notes, an offline pass that
  corrects them against the record, and only a small part pushed. The evidence is thin:
  single runs.
- **Recall scores do not predict task results.** A decision should rest on play.

What it does not settle: no source compares these designs on game progress over tens
of thousands of decisions, and none plays from screenshots alone.

## Options

Costs per game hour of the actor alone were $0.53 to $1.04 in the recorded lineages.

### 1. Keep the current memory

- **Mechanism.** As today.
- **For.** No cost; no new machinery.
- **Against.** Every failure above.
- **Cost and cadence.** None added.
- **Other games.** Game-neutral.
- **Falsified by** a long lineage with a rediscovery rate well under the recorded 4.39
  per game hour and no costly loss.

### 2. Carry by the harness, written by the player

- **Mechanism.** The player stays the only writer, and the harness stops leaving carry
  to chance:
  - every new actor and every new admission starts with a small working set of the
    player's current records, not only a summary or final report;
  - the handoff and finish steps require the actor to record or confirm its open
    facts, each with game time and place, and to mark replaced ones;
  - query gains search by text.
- **For.** It is the study's Arm A made live, and Arm A answered more than Reference
  (18 against 12, descriptive). It addresses the observed loss directly. No second
  model.
- **Against.** Arm A's items were 72.5% contradicted or outdated. The player still
  decides what to write, and the measured rate is low. Text search helps only a model
  that searches.
- **Cost and cadence.** At most about 2,000 tokens once per actor start, the size the
  [snapshot-diff estimate](snapshot-diff-cost.md) recommended; not priced here. No
  added model call, so no added latency per decision.
- **Other games.** Game-neutral: it moves the player's own text.
- **Falsified by** a paired live comparison in which rediscovery does not fall, or in
  which the player acts on outdated pushed items.

### 3. The curator, repaired

- **Mechanism.** ADR 009's design with the study's faults addressed: a session at each
  handoff as well as each admission; a brief aimed at coverage of places and stores of
  goods; the player's records taken in whole; a failed request counted at a fixed
  bound, as player runs now are (#556).
- **For.** Very few outdated items (1 and 2 of 40). The trace is its input, so it does
  not depend on the player writing.
- **Against.** Lower recall than the player's own notes in the one test; nothing to
  deliver until its first session; a second model and a sandbox to run and pay for; a
  median lag of 47 decisions in the [shadow run](../acceptance/2026-11-08-curator-shadow-454.md).
- **Cost and cadence.** 0.34 of the actor's spend in the study's clean repeat; 0.61, or
  $0.49 per game hour, in the shadow run on the seven-day lineage. It runs between
  decisions, so it adds no latency per decision; an admission boundary waits for a
  session (median 189 s).
- **Other games.** The epistemic core is game-neutral; the brief and types are per
  game.
- **Falsified by** a live comparison in which it does not beat option 2 on rediscovery
  at its added cost.

### 4. The player's notes, corrected offline (recommended)

- **Mechanism.** Option 2, plus a narrow offline pass between admissions that reads the
  trace and the player's records and does only three things: marks records the trace
  shows are outdated, adds places and stores of goods the player saw and did not
  record, and never rewrites or shortens a record that is still true. The working set
  pushed to the next actor is built from the result. The trace stays searchable.
- **For.** It takes Arm A's coverage and Arm B's currency, the two things the study
  measured. It matches the best supported design outside the project. It reuses the
  curator's sandbox, gate and trace projection, which exist.
- **Against.** Unmeasured as a whole. The correction pass can be wrong. More moving
  parts than option 2.
- **Cost and cadence.** Between options 2 and 3; the pass has a narrower task than the
  curator's, so its cost should be below 0.34 of the actor's spend, which is a
  hypothesis. No latency per decision.
- **Other games.** As option 3.
- **Falsified by** the pass adding no measurable gain over option 2 alone.

### 5. A prompt rebuilt at every decision

- **Mechanism.** No accumulating conversation. Each decision gets a freshly composed
  prompt: current screen, state, and selected memory.
- **For.** Bounded context; memory is the only carrier, so it cannot be skipped. One
  [card-game testbed](https://arxiv.org/html/2607.02255) reports it working (not
  re-read for this note; ten games per condition).
- **Against.** It replaces the player host's whole context model. It discards the
  in-context continuity the current player relies on within an admission. Evidence is
  the thinnest of the five.
- **Cost and cadence.** Smaller prompts would be faster and cheaper per decision, but
  each loses the provider's prompt cache; unmeasured.
- **Other games.** Game-neutral.
- **Not recommended now**: it is a rebuild whose benefit rests on one small study.

## Recommendation

**Build in two steps, and decide each on play.**

1. **Option 2 first.** It is the smallest change that addresses the recorded loss, it
   needs no second model, and every later option needs its parts (game time and place
   on records, a pushed working set, search).
2. **Then the offline correction pass of option 4**, kept only if it adds a measured
   gain over step 1.

The full curator of option 3 (ontology, fact store, later programs) stays proposed in
ADR 009 and is not built further until step 2 has reported. Option 5 is recorded and
set aside.

## The experiment that could decide it

It has to measure play, not recall. The proposal is a **paired continuation**:

- **Start.** A sealed saved game from a lineage that ended alive. The held-out lineage
  (#522) ended alive at 27.76 game hours with its store; a copy is used and the sealed
  original is untouched. Using it ends that lineage's held-out standing.
- **Arms.** The current player, and the player with option 2. Each continues from the
  same copy, one after the other, never two games at once.
- **Size.** Two continuations per arm of 12 game hours each: 48 game hours.
- **Measures, named before it runs.** Rediscoveries per game hour by the existing
  probe method; game hours advanced per dollar; survival; and, for the pushed arm,
  each decision that followed an outdated pushed item.
- **Cost.** About $50 of play at the $1.04 per game hour that lineage cost, plus
  annotation. A $100 envelope is proposed. Free first step: for each of the four losses
  in the table above, compute whether option 2's working set would have held the fact
  at the boundary where it was lost. That needs no model call.
- **Stop.** The envelope; or a death in the first two game hours of a continuation,
  which is replaced once.
- **It is a screen, not a qualification.** Four continuations from one saved game
  cannot support a general claim.

| Outcome | Meaning | Next |
| --- | --- | --- |
| Rediscovery falls clearly and hours per dollar do not | Carry was the problem and option 2 addresses it | Adopt option 2; test the correction pass the same way; then release the long runs |
| Rediscovery falls but the player acts on outdated items | Carry works and currency does not | Build the correction pass before any long run |
| No clear change | The player has the facts and does not use them | Test a cue at decision time before building anything larger |

Whether a copy of a sealed saved game may be continued, one game at a time, is an
owner decision; it is narrower than ADR 009's practice instance, which runs beside live
play.

## What this means for the open items

- **ADR 009.** The curator and memory phase is not adopted and its study is closed.
  This note proposes to reach it by the two steps above. The ADR's belief model and
  ontology stay open and are not needed for step 1.
- **[#463](https://github.com/CVX-Hull/enactive/issues/463)**, adopting the curator
  and memory phase: waits for the experiment. Its migration would then cover step 1
  only.
- **[#470](https://github.com/CVX-Hull/enactive/issues/470)**, programs and monitor:
  unchanged and after memory. The project's research found self-written skills lowered
  results while curated ones raised them ([curated programs](../research-curated-programs.md)).
- **[#472](https://github.com/CVX-Hull/enactive/issues/472)**, the practice instance:
  unchanged. The experiment needs only a sequential copy.
- **[#441](https://github.com/CVX-Hull/enactive/issues/441)**, the seven-day screen:
  stays parked until the experiment reports.
- **[#556](https://github.com/CVX-Hull/enactive/issues/556)**, how the curator charges
  a failed request: at a fixed bound, as player runs do. Charging the whole reservation
  helped end the study's second repeat. It is changed when curator sessions next run,
  not before.
- **Responsiveness** ([#442](https://github.com/CVX-Hull/enactive/issues/442)): steps
  1 and 2 add no model call per decision, so they do not move the response-time
  criterion in either direction.

## Limits of this note

- The live evidence is one lineage of 47.79 game hours on one route, and four lost
  facts.
- The four readings of the study are inferences from its descriptive tables.
- External figures were read through a tool that summarises pages; five sources were
  re-read by the lead on 13 November 2026 and the table holds only those.
- No cost in dollars is known for options 2, 4 or 5.
