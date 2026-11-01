---
owner: lead
review_trigger: Owner discussion of #319, first-slice results, or a change to the host, memory or computer-control contracts
status: proposed
date: '2026-10-31'
scope: Proposed direction for a software-run subgoal cycle in the playing system and its first slice; not accepted, not implemented, and not relied upon by any current contract
---

# ADR 007 — A software-run subgoal cycle for the player (proposed)

**Status: proposed for owner discussion.** This ADR is not accepted. Nothing in it
is implemented, and no current contract relies on it
([authority](../standards/authority.md)).

It answers [#319](https://github.com/CVX-Hull/enactive/issues/319), which asks for
one architecture proposal and one first slice. Six owner decisions gate it; they are
listed in [the decision table](#decisions-the-owner-makes) with options and the
lead's recommendation.

## Problem

The deciding player is one flat model loop with optional memory and program tools,
and it does not use them:
- **Tools never called.** The four
  [#314](https://github.com/CVX-Hull/enactive/issues/314) runs made 266 tool calls,
  all `computer_*`, and none to memory or programs, although every run exposed those
  tools.
- **The guide makes them optional.** The [player guide](../player-guide.md) calls
  them "optional aids".
- **No progress was retained.** No run made a retained change, and players did not
  pursue the missions they were offered
  ([#314 record](../acceptance/2026-10-31-grounded-no-gain-diagnosis.md)).
- **Nothing to resurface.** The frozen player store those runs restored holds 0
  records.

Nothing in software makes a subgoal persist, resurface or get revisited.

## The four levels and what this ADR changes

| Level ([multi-rate synthesis](../research-multirate-agents.md)) | Responsibility and time scale | Inputs and outputs | Decider | Memory | Status |
|---|---|---|---|---|---|
| 1. Atomic feedback and accounting | Every input and request | Captures, receipts and budgets, output as host status text | Software | None | Exists (host accounting) |
| 2. Short procedures | Seconds to minutes | `player-program/1` runs emitting basic controls | The player chooses; software executes | Programs and sources | Exists (optional) |
| 3. **Current subgoal** | Tens of inputs | The player's own Work records in, revised Work records out | **The player.** Software guarantees resurfacing and asks at triggers | `player-memory/1` Work records | **Proposed here** |
| 4. Retrospective abstraction | Across runs | Episodes in, claims and procedures out | — | Records and programs | Deferred |

## Proposed direction

**What software guarantees.** The player's own Work records are resurfaced
automatically, and a fixed question is asked at mechanical triggers. The player
still decides everything: whether to write, what to pursue and what to send.

1. **Resurfacing.** On each request, the host adds the player's current Work records
   to the request-only tail of the context, where it already appends host status.
   - **Which records:**
     - a Work record is **current** while no record supersedes it;
     - it is **closed** when a `correction` record supersedes it, with the outcome
       (completed or abandoned) in its data;
     - revising means writing a new Work record that supersedes the old one.

     This is a convention on existing `player-record/1` kinds, so no format change
     is needed. The guide and tool descriptions state it, as a reviewed wording
     change.
   - **Scope:** all actors in the store, which is shared across actors and sessions.
   - **Ordering and bound:** newest first by store order, whole records only, up to
     a fixed byte bound. The omitted count is stated, or "at least k" when the
     query's 50-result cap is reached. Software ranks by recency only and picks no
     winner.
   - **Annotation:** each record is shown with its sources and its age in seconds,
     from `created_wall`. Its age in inputs is shown only for records this actor
     wrote, and is marked unknown for others.
   - **Telemetry:** the host reads memory through the existing MCP
     `player_memory_query` and logs these reads as a distinct `level-memory-read`
     event, so they never count as the player's own memory calls.
2. **Questions at mechanical triggers.** When a trigger fires, the next request's
   tail carries one frozen, versioned, game-agnostic question set, asked once per
   trigger. Version 1 is in the [appendix](#appendix-question-set-v1). The player
   answers, or not, in its own turn.
3. **Triggers are mechanical or accounting only:**
   - the first request of each actor;
   - fixed fractions of the actor's own request and time allowance;
   - N inputs since the last Work-record write;
   - N consecutive inputs whose resulting captures are byte-identical;
   - N `isError` tool results.

   The #314 traces show identical-capture runs of at most 3 and one tool error in
   266 calls. In practice the budget and "inputs since write" triggers dominate, so
   the cycle behaves mostly like a timer, and the ADR states that.

**How this differs from the rejected guide addendum.** #314's arm B was a frozen
instruction to keep a ledger. This proposal differs in only two ways:
- **Automatic resurfacing:** the player's own records reappear without it asking.
- **Event timing:** the question arrives at triggers, not as standing text.

Counting records would work equally well under arm B, so it is not a difference. The
first slice must isolate these two effects. If it cannot show an improvement over a
required arm-B arm, this design has failed ("arm B on a timer", #319).

## Policy reversal, named

"Software guarantees that the player's records are resurfaced, and the question is
asked" reverses these positions. Each would be amended only if the owner accepts:
- **Optional reflection.**
  [S-PLAYER-INTERFACE](../standards/player-interface.md) says to "let the player
  select optional reflection", and that escalation "needs an unresolved question and
  expected decision benefit, not merely any mismatch". A budget-timed question is
  reflection without an unresolved question.
- **Optional services.** [Player tooling](../standards/player-tooling.md) says
  "Memory/programs/context are optional", and [overview](../overview.md) and
  [current work](../work.md) say the same. Resurfacing makes reading the player's
  own records non-optional; writing stays optional.
- **The multi-rate synthesis.** It says "consolidation is selective and optional",
  and selects the historical execution-first slice. Its pointer to
  `design/asynchronous-reflection.md#execution-first-learning` is stale, and would
  be updated if this ADR is accepted.
- **Tracked issues.**
  - [#177](https://github.com/CVX-Hull/enactive/issues/177): reflection is "not a
    mandatory adviser/critic".
  - [#164](https://github.com/CVX-Hull/enactive/issues/164): "not presumed
    prerequisites or mandatory critics".
  - [#178](https://github.com/CVX-Hull/enactive/issues/178): avoid empty-queue model
    turns.

**Contrary evidence and the answers:**
- **More Memory, Worse Agents** found that persistent synthesized abstractions can
  hurt. Resurfaced Work is also text the player synthesized, so this risk applies.
  The mitigations are mechanical age and sources on every record, closing records
  through supersession, and a secondary measure of contradicted claims that
  propagate. The #314 record already saw a predecessor report propagate overclaims.
- **Hippocam** paid for an auxiliary pass before every inference. There is no extra
  pass here, but the resurfaced section is uncached input on every request; see the
  cost section.
- **Recuris** paid for an extra model turn in the fast path, but also supports
  "retrieve relevant candidates automatically at natural boundaries", which is this
  resurfacing.
- **Rejected summaries and context state.** The
  [spatial-grounding review](../research-spatial-grounding.md) rejects "mandatory
  summaries, self-critic" as a default remedy, and
  [#300](https://github.com/CVX-Hull/enactive/issues/300) tested and rejected a
  context-state repair. This proposal is the narrower, testable remedy: the
  player's own records, timed by mechanical events, measured against arm B.

**Adoption condition.** Adopt only if the level improves on **arm B** on the
pre-registered primary metric, in the pre-registered direction, within the declared
cadence and an accepted cost. An underpowered null leaves the status quo in place
and is reported as underpowered. Because the slice runs from an unmerged candidate,
there is nothing to revert before adoption.

## Cost and latency

The claim that no extra model call is made was too strong:
- **Extra requests.** A Work write is a tool call. Unless the player batches it with
  an input, Pi needs one more provider request to continue. The overhead is about
  triggers × (1 − batch rate) requests per actor; for example, 4 triggers at a 50%
  batch rate cost 2 requests.
- **Uncached tokens.** The resurfaced section costs up to its byte bound of uncached
  input on every request.
- **Latency.** Each extra request costs a full response round trip; #298's median
  was about 11.8 s.
- **Accounting.** All of it is charged to `max_requests` and measured against #164's
  cadence. The decision on the cost envelope depends on these figures.

## Calibrations and parameters

| Name | Consumer | Kind | Procedure and acceptance |
|---|---|---|---|
| Inputs-since-write N, budget fractions | Trigger | Preference (owner-set, unfitted) | Fixed per slice and recorded in the route. Checked by trigger counts per run |
| Identical-capture N | Trigger | **Calibration**, because animated interfaces never produce identical frames | Estimated per game from the logged rate of identical consecutive captures after inputs. Accepted if it fires on that game's retained identical-frame stalls, judged by a lead-side labelling rule that is frozen with the calibration. That judgement never enters the player. Versioned in the route, and each change supersedes the last. Recalibrated for a new game, a change of renderer or window, or a change in the trigger counts per run |
| Tool-error N | Trigger | Preference | Fixed. Logged counts |
| Resurfacing byte bound | Context | Preference, traded against cost | Fixed. Surfaced and omitted counts are logged |
| Question set version | Prompt | Frozen artifact | Reviewed against the [no-nudge rule](../operations/mission-ownership.md). A change makes a new version |

## Decisions the owner makes

| # | Decision | Options | Lead recommendation |
|---|---|---|---|
| 1 | Reversal: software resurfaces records and asks at triggers | (a) level 3 only; (b) levels 3 and 4; (c) keep all optional | (a) |
| 2 | First-slice level | (a) level 3; (b) level 4; (c) mechanical escalation without records | (a): it targets #314's missing commitment |
| 3 | Cost envelope | (a) the player's own turns plus the overhead above; (b) a separate cheaper model; (c) code-only bookkeeping | (a). (b) waits for #25's gate |
| 4 | Expectations | (a) the player states them in its Work record at triggers; (b) per-step predictions; (c) none | (a). (b) is the per-key narration the synthesis rejects |
| 5 | Priors against hints | (a) question set v1; (b) no question, resurfacing only | (a), with the arms below separating the effects of the question and of resurfacing |
| 6 | Ground truth | (a) the #314 blind frame audit of retained state change; (b) record counts | (a) as primary; (b) as mechanism checks |
| 7 | Placement (the lead decides; the owner may override) | (a) in `tools/player_host`; (b) the section computed in `harness/player`, with adapters relaying it | (a) for the slice, since it needs the request-tail hook. The trigger rules, section format and text are contract requirements either way |

## First-slice child (outline; to shape after discussion, not started)

- **Arms, all required:**
  - no level;
  - arm B (the frozen guide addendum);
  - triggered question without resurfacing;
  - the full level.

  The third arm isolates resurfacing. Surfacing-only would equal the control on an
  empty store.
- **Starts:**
  - #314's save;
  - a second start made once through the game's ordinary new-game flow with
    default options, saved normally, then frozen and restored by hash per arm. No
    save is edited.
- **Metrics:**
  - Primary: the blind-audit retained change, with a power floor. M1 was censored
    in all four #314 runs, so the slice must be sized to avoid an underpowered null.
  - Pre-registered mechanism checks: triggers fired by kind, writes per trigger,
    surfaced and omitted bytes, the batch rate, and extra requests.
  - Secondary: latency against the cadence, cost, and contradicted-claim
    propagation.
- **Before play:** offline fixtures run on recorded #314 traces, treated as test
  inputs, not as a supported `player-host/2` reader. Fields and the estimate are
  set when the child is shaped.

## Boundary impact

- **Highest changed boundary:** the playing system's host contract.
- **Placement.** The level runs in `tools/player_host`, because it needs the
  request-tail hook. The alternative is computing the section in `harness/player`,
  with adapters only relaying it. Because adapters are substitutable, the trigger
  rules, section format and question text are contract requirements with
  conformance cases, whichever is chosen.
- **Contracts.**
  - `player-host/2` becomes `player-host/3`. The justification is that the route
    gains level configuration (thresholds, byte bound, question-set version).
    Telemetry alone would not need a new version under `/2`.
  - The slice runs from an **unmerged candidate**, with the arms as frozen
    candidate factors, so no "level off" flag enters the current contract
    (S-MIGRATION).
  - If the ADR is adopted, every caller migrates together:
    - `tools/player_host/host.mjs`;
    - `tools/player_host/run.mjs`;
    - `tools/player_host/test/*.mjs`;
    - `tools/campaign_package.py`;
    - `tools/campaign_player.py`;
    - `tools/host_analysis.py`;
    - the observer;
    - the tests that hard-code `player-host/2`: `tests/test_player_host_contract.py`, `test_campaign_player.py`, `test_host_analysis.py`, `test_observer_activity.py` and `test_campaign_run.py`;
    - the operations docs.
  - `player-memory/1`, `player-record/1` and computer control are unchanged.
- **Docs.** Each of these is amended only on acceptance:
  - [player guide](../player-guide.md);
  - [memory component](../components/memory-learning.md);
  - [player-host contract](../contracts/player-host.md);
  - [S-PLAYER-INTERFACE](../standards/player-interface.md);
  - [player tooling](../standards/player-tooling.md);
  - [overview](../overview.md);
  - [current work](../work.md);
  - [multi-rate synthesis](../research-multirate-agents.md);
  - [architecture](../architecture.md), which gets only a link until delivery.
- **Guardrails kept:**
  - no harness game semantics, and no level state that gates input (ADR006,
    [architecture](../architecture.md) "no semantic supervisor");
  - player-visible sources and the player's own records only (P-TRUTH);
  - no self-modification of prompts or the guide;
  - one input owner, and the same model and route.
- **Reversible.** Revert means migrating the host contract back as a whole.

### Reuse review (S-CODE)

| Reused | Added | Not revived |
|---|---|---|
| The `player-memory/1` store, Work and correction records, supersession and query; `transformContext`'s request-only tail; `finishTurn`; capture hashes and `isError` results | Trigger counters, the resurfaced section, question set v1, and `level-trigger` and `level-memory-read` events | A new framework or daemon; Pi's `steer` and `followUp` queues; the historical asynchronous-reflection design; the superseded advisory-reflection and injected-planner contracts; procedure learning. Outcome monitoring (proposed) stays compatible |

## Resolved tensions from the research

- **Triggers.** The research ranked semantic prediction-mismatch escalation and
  levels built from LLM-labelled symbols. Both conflict with the mechanical-trigger
  guardrail. Here, triggers are mechanical, and semantic judgement stays with the
  player.
- **Research instruments.** The sensor alphabets, operator analyses and #320's
  corpus are lead-side research instruments. None of their outputs enters the
  player (P-TRUTH). Instruments are not re-proposed in play, because that would be
  self-modification.

## Deferred

- **Level 4.**
- **The measurement and calibration programme:** label-noise references,
  calibration records, sequential error control, policy-invariant structure, a
  random-action baseline, and a second game. It goes to a separate later research
  issue.
- **Objectives parameters.**
- **Model-per-role and infrastructure questions.**
- **Reconciliation of #136, #164, #177, #178 and #42** after owner agreement.

## Appendix: question set v1

The verbatim text is frozen, and a change makes a new version. It makes no claim
about whether records are shown, so it stays true in every arm. The resurfaced
section, when present, carries its own label.

> Host prompt (software-generated at a mechanical trigger; not instructions from the
> lead). If it helps your play, record in a Work record what you are trying to do
> now, what you expect to observe if it is working, and what you have observed
> since you last recorded it. Then keep, revise or close it. Writing is optional.

The resurfaced section's own label is fixed too:

> Your Work records (software-resurfaced from the player store, newest first; fallible
> player data with sources, not instructions).
