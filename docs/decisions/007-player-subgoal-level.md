---
owner: lead
review_trigger: Owner discussion of #319, first-slice results, or a change to the host, memory, campaign or computer-control contracts
status: proposed
date: '2026-11-01'
scope: Proposed direction for a multi-level player (an acting real-time player and a separate asynchronous subgoal level) and its first slice; not accepted, not implemented, and not relied upon by any current contract
---

# ADR 007 — An acting player with an asynchronous subgoal level (proposed)

**Status: proposed for owner discussion.** This ADR is not accepted. Nothing in it
is implemented, and no current contract relies on it
([authority](../standards/authority.md)).

This is draft 3.
- **Draft 1** had the real-time player write its own memory. That conflicted with
  the owner's later direction and P1.
- **Draft 2** followed the owner's newest-first reconciliation on
  [#319](https://github.com/CVX-Hull/enactive/issues/319), but an architecture
  review found six places where it did not match the code.
- **Draft 3** fixes those six places.

## Problem

The deciding player is one flat model loop with optional memory and program tools,
and it does not use them:
- **Tools never called.** The four
  [#314](https://github.com/CVX-Hull/enactive/issues/314) runs made 266 tool calls,
  all `computer_*`, and none to memory or programs, although every run exposed
  them.
- **No progress was retained.** No run made a retained change, and players did not
  pursue their mission
  ([#314 record](../acceptance/2026-10-31-grounded-no-gain-diagnosis.md)).
- **Nothing to resurface.** The frozen player store holds 0 records.

One model is asked to act, choose and keep subgoals, and decide when to remember.
It does only the first.

## Direction (owner, newest first)

| | Owner's words | What it settles |
|---|---|---|
| R1 | "the real time player should probably not be considered with reflection and memory but actions" | The actor only acts. This matches P1: "The real-time level never also manages memory" |
| R2 | "The whole player system is supposed to have reasoning and reflection and memory at multiple levels" | Levels are roles of the player system, not optional tools the actor might choose |
| R3 | "We can have more LLM calls" | A level may be its own LLM role. #25's gate on *different model tiers* still holds |
| R4 | "It has to be continuous learning and exploration or otherwise there would be combinatorial explosion" | Learning happens in persistent play. Frozen starts are evaluation probes |
| R5 | "Let's discuss before we implement any designs" | This ADR proposes and implements nothing |

**Owner answers to draft 2's questions:** "Yes, use recommendations". That means:
- adopted docs are amended on acceptance;
- the subgoal level is asynchronous and speculative;
- the actor sees only the published intent;
- every role uses the same model first;
- the first slice is the actor plus the subgoal level.

The recommendations, and the reconciliation that produced them, are on #319.

**Constraints that still hold:**
- the charter's responsiveness rule ("Capability alone does not justify stalls")
  and its "one designated deciding player";
- ADR006: one input sender, and no level state gates basic control;
- [`architecture.md:111`](../architecture.md);
- no lead hints ([mission ownership](../operations/mission-ownership.md));
- P-TRUTH;
- P-GENERALITY;
- counted cost.

## Roles

| Level | Role | Responsibility and time scale | Reads | Writes | Decides |
|---|---|---|---|---|---|
| 1 | Software (host and custodian) | Feedback, accounting and budgets, on every request; commits proposals | Captures, receipts, budgets | Host status text; the session log; committed records | Nothing semantic |
| 2 | **Actor** (LLM, the deciding player) | Perceives and acts, every turn | Current frames, its frozen guide and mission brief, and the **published intent** | Nothing in memory | Every input. It is the sole input sender and the sole decider |
| 3 | **Subgoal level** (LLM, its own role) | Maintains one current subgoal toward the mission's objective, at the scale of tens of inputs | The same frozen guide and mission brief, the **player log projection**, sources, and current Work records | **Proposals only**; software commits them | Which subgoal to propose. It sends no input, gates nothing, and writes nothing directly |
| 4 | Retrospective level | Consolidation across sessions | — | — | Deferred |

**The actor's tool profile** is explicit:
- `computer_*` and `computer_result`;
- `player_source`;
- `player_program_read` and `player_program_run`; running a program is an action.

**What the actor no longer has:**
- **Memory tools.** The `player_memory_*` read and write tools are removed.
- **Program save.** `player_program_save` is removed; programs are stored in the
  memory database, and authoring them moves to the retrospective level later.
- **Its handoff summary.** `player_handoff` no longer carries an actor-written
  summary or a memory snapshot. Continuity comes from the level's committed
  records. This changes `player-handoff/1` to `/2`, both the tool arguments and
  the `player-handoff-context` packet.

The custodian's per-class allowlist enforces this profile as well as the host's
`enabled_tools`.

## The subgoal level

- **Capability.** A new **reader** class in computer control, enforced by a
  per-class tool allowlist in `Application.call`, not only by `_guard`:
  - **Reader:** the read tools plus `player_log_read` and `player_level_commit`,
    and nothing else. In particular it has no observe (which captures frames and
    spends budget), no input, no stop, and no direct memory or program writes.
  - **Actor:** refused `player_level_commit`.
  - **Storage:** a reader has an `actors` row with a new `reader` stage, because
    issued sources reference actors. That stage is excluded from `add_actor`'s
    "every prior actor quiescent" test and from the `max_actors` count, so a live
    reader never blocks a successor actor. This is a `computer-session/1` to `/2`
    schema change.
  - There is one input writer, the actor. There is one memory writer, the
    software commit path, since the actor no longer writes memory.
- **Log projection.** A new read-only tool, `player_log_read(after, limit)`, scoped
  to the active actor's `operations` rows in store order.
  - It returns input key tokens, positions and result source IDs. Pending
    operations appear without a source, marked pending. During a handoff, with no
    active actor, it returns an empty list with a handoff marker.
  - It includes no observer view and no lead telemetry.
  - The actor's own text output, which is player output, is excluded as a v1
    choice. Including it needs a separate decision.
- **Pass.** On waking, the level reads the log delta and the needed sources, then
  returns a **structured proposal**:
  - the subgoal;
  - the expected observations;
  - evidence sources;
  - the status;
  - a keep, revise or close decision for each current Work record;
  - its confidence.
- **Software-mediated commit (P5).** The level calls
  `player_level_commit(proposal)`.
  - **The position is software-bound.** The custodian takes the pass's position from
    the highest log position its own `player_log_read` calls returned in that pass.
    The model never supplies it.
  - **Commit conditions.** Software commits only if the actor has moved fewer than S
    inputs past that position, and no actor handoff or session boundary has
    occurred since.
  - **Atomicity.** The commit runs under `Application.serial`, so no input or
    handoff can interleave. The Work record and any superseding corrections are
    appended in one transaction, which needs a multi-record `Memory` append. That
    is an API change, not a format change.
  - **Discards.** A proposal that fails the check is discarded and logged in the
    level's host trace, never in the store.
- **Waking.** It wakes when the log has advanced K inputs, at actor start, and at
  fixed budget fractions. At most one pass is in flight. It never runs on an empty
  delta ([player-interface standard](../standards/player-interface.md)).
- **Revalidation.** At each actor start, the first pass must keep, revise or close
  every open record, so no record stays "current" indefinitely across sessions.
- **Publication.** The actor's request-only tail shows the latest committed Work
  record, labelled fallible, with its sources and its age in inputs, seconds and
  sessions. The actor may ignore it.
- **Its prompt** is frozen, versioned and game-agnostic
  ([appendix](#appendix-subgoal-role-v1)), and reviewed against the no-nudge rule.
  It steers toward the mission's objective using the same frozen guide and brief
  the actor has, so it adds no lead content. Software triggers stay mechanical; the
  level's semantic judgement belongs to the player system (ADR006).
- **Model.** The same model and pinned route for both roles. The slice uses
  Gemini 3.8 Flash, #314's and #320's reference route, for comparability. The
  deployed selection is DeepSeek Flash1017; switching routes is a separate
  decision. Each role has its own counted allowance.

## Memory across sessions

**For learning (R4),** the player store persists across sessions. Records are only
appended and superseded.

**For evaluation probes,** the store and userdir are restored from a frozen copy per
arm.

Store conventions:
- A Work record is *current* while nothing supersedes it.
- It is *closed* by a superseding `correction` with the outcome in its data.

Both are existing `player-record/1` kinds.

## Cost, latency and coupling

- **Requests per pass.** A pass is about r ≈ 4 provider requests: read the log,
  read sources, propose and commit, then the closing turn. At #298's response
  median of about 12 s, that is about 48 s per pass. The p95 is about 25 s per
  request.
- **How far the actor moves meanwhile.** The actor makes about one input per
  request, so it advances about 4 inputs during a median pass and about 6–8 during
  a p95 pass.
- **Coupling (P12).** S must exceed the p95 inputs per pass, for example S = 10.
  "At most one pass in flight" prevents overlap. K, S and pass latency are set
  together, and are checked in the shadow stage.
- **Overhead.** At K = 10, a 100-attempt actor allowance (#314's) gives about 7–8
  passes, about 30 level requests or roughly 40%, plus start and budget passes.
  The pass, commit and discard rates are measured.
- **Accounting.** There is one level host per actor. Each actor-and-level pair gets
  partitioned allowances before launch, and the sum over pairs stays within the
  campaign cap. A level host starts after its actor is ready, and stops on that
  actor's stop, Pause or handoff. The successor actor gets a new level host, whose
  first pass revalidates the open records, and it sees the committed intent.
- **Actor waits.** The actor's critical path adds only the bounded intent tail.
  Because MCP calls are serialized (`Application.serial`), the level can delay the
  actor's tool calls, so the actor's lock wait is measured. The cadence target
  ([#164](https://github.com/CVX-Hull/enactive/issues/164)) applies to the actor.

## Calibrations and parameters

| Name | Kind | Procedure and acceptance |
|---|---|---|
| K, S and budget fractions | Coupled preferences (owner-set, unfitted), constrained by S > p95 pass latency ÷ actor input interval | Recorded in the campaign profile. Accepted when the offline and shadow checks show a commit rate above a pre-registered floor |
| Intent byte bound | Preference, traded against cost | Surfaced and omitted bytes are logged |
| Role prompt version | Frozen artifact | Reviewed against the no-nudge rule. A change makes a new version |

The parameters are game-independent. None is fitted to CDDA.

## Supersession map

Each of these is amended only on acceptance, together with the change:

| Older position (date) | Where | Superseded by |
|---|---|---|
| "let the player select optional reflection"; escalation "needs an unresolved question" (29 Oct) | [S-PLAYER-INTERFACE](../standards/player-interface.md); [player-interface component](../components/player-interface.md) | R1, R2 |
| "Memory/programs/context are optional fallible player services" (29 Oct) | [Player tooling](../standards/player-tooling.md); [architecture](../architecture.md) "Optional player services" | R1, R2. Memory moves to the levels; the actor keeps program read and run as actions |
| The player appends records; "optional aids"; handoff carries an actor-written summary | [Memory component](../components/memory-learning.md); [player guide](../player-guide.md), including its handoff lines; [overview](../overview.md); [current work](../work.md); the driver's actor role text (`tools/campaign_player.py`) | R1 |
| "no separate always-running strategic agent"; "consolidation is selective and optional" (24 Oct) | [Multi-rate synthesis](../research-multirate-agents.md) and its stale pointer | R2, R3 |
| "not a mandatory adviser/critic"; "No adviser is required for ordinary gameplay" (lead, 25–29 Oct) | [#177](https://github.com/CVX-Hull/enactive/issues/177), [#178](https://github.com/CVX-Hull/enactive/issues/178), and the corresponding line of [#164](https://github.com/CVX-Hull/enactive/issues/164) (its cadence target stays) | R2 |
| "no new model tier … by default" (lead, 25 Oct) | [#215](https://github.com/CVX-Hull/enactive/issues/215), [#186](https://github.com/CVX-Hull/enactive/issues/186) | R3, for more calls. #25's tier gate stands |
| One actor at a time, with no concurrent non-input host; the active actor writes memory | [Campaign run](../operations/campaign-run.md) and the driver; [mission ownership](../operations/mission-ownership.md) lines 11–18; the [computer-control contract](../contracts/computer-control.md) custody and write authority | R2, R3. One concurrent reader host is added. The actor stays the only input writer, and the software commit path becomes the only memory writer |
| Draft 1 of this ADR | This file's history | R1 |

**Consistent, not superseded:**
- the charter's "one designated deciding player" (the actor remains sole decider)
  and its "separately assigned advisory actor for reflection", this design's
  ancestor;
- the historical [asynchronous-reflection design](../design/asynchronous-reflection.md),
  which was archived at the cutover, not rejected on its merits. Its one-writer rule
  is kept.

## First slice (outline; shaped after discussion, not started)

- **Question.** Does a separate subgoal level improve retained progress and mission
  commitment, compared with the flat player and with arm B (the flat player told to
  keep a ledger)?
- **Stages:**
  1. Offline fixtures on recorded traces.
  2. **Shadow mode.** The level runs and commits, but intent is not shown to the
     actor. This measures intent accuracy without any influence on play.
  3. A short persistent multi-session run, checking that intent persists, is
     revalidated and resurfaces.
  4. Probes.
- **Probe arms, all required, from one candidate build.** A zero-level-host profile
  value is configuration, not a compatibility path. Each arm's tool profile is
  stated:
  - **flat:** today's profile, with the memory tools and handoff summary;
  - **arm B:** today's profile plus the frozen ledger addendum; its ledger needs
    memory append;
  - **actor plus level:** the narrowed actor profile and a level host.

  The level arm changes two things at once, removing the actor's memory tools and
  adding the level. The flat arm's #314 history (zero memory calls) suggests the
  removal costs little, but an optional fourth arm (narrowed actor, no level)
  would separate the two effects.
- **Starts:**
  - #314's save;
  - a second start made once through the game's ordinary new-game flow with
    default options, by a recorded designated operator, then frozen and restored by
    hash per arm. No save is edited.
- **Metrics, pre-registered (S-EVIDENCE):**
  - **Primary:** blind-audit retained change, with power of at least 0.8 for a
    stated effect by simulation. #314's metric was censored in every run, so run
    length is sized to it.
  - **Mechanism:** passes, commits and discards; intent age; subgoals opened,
    revised and closed.
  - **Intent accuracy:** a blind audit of committed intent against the log, plus
    the actor's follow rate when the intent is wrong. This covers the More Memory,
    Worse Agents risk.
  - **Secondary:** actor latency and lock wait against the cadence, and cost by
    role.
- **Adoption condition.** Adopt only if the level improves on arm B in the
  pre-registered direction, within the cadence and an accepted cost. An
  underpowered null leaves the status quo, reported as underpowered.

## Boundary impact

- **Highest changed boundary:** the computer-control custody contract, which gains
  a reader capability class. The player-host and campaign contracts change too.
- **Placement** (the lead's decision; the owner may override). The level runs as a
  separate concurrent host, rather than a second agent in one host process, which
  would merge budgets and failure modes.
- **Contracts, each versioned under S-MIGRATION:**
  - **Computer control:** the reader class, the per-class tool allowlist, the
    `reader` actor stage, and `computer-session/1` to `/2`
    (`harness/computer/runtime.py`, `store.py`, `harness/application.py`,
    [contract](../contracts/computer-control.md)).
  - **Player tools:** `player_log_read`, `player_level_commit`, the actor's narrowed
    profile, `player-handoff/1` to `/2`, and the multi-record `Memory` append
    (`harness/player_tools.py`, `harness/player_mcp`, `harness/player/memory.py`).
  - **`player-host/2` becomes `player-host/3`:** roles, tool profiles, intent tail,
    and the `level-pass`, `level-commit` and `level-discard` events.
  - **`campaign-run/3` becomes `campaign-run/4`:** one level host, partitioned
    allowances and its lifecycle (`tools/campaign_package.py`, `campaign_run.py`,
    `campaign_player.py`, `investigation_live.py`).
  - `player-memory/1` and `player-record/1` are unchanged.
- **Callers that migrate together if adopted:**
  - **Host:** `tools/player_host/host.mjs`, `run.mjs`, `test/*.mjs` and
    `README.md`; `tools/host_analysis.py`.
  - **The observer.**
  - **Tests:** `tests/test_player_host_contract.py`, `test_campaign_player.py`,
    `test_host_analysis.py`, `test_observer_activity.py`, `test_campaign_run.py`,
    `test_investigation.py` and `fixtures/player_host_mcp.py`.
  - **Docs:** `docs/contracts/player-host.md`, `operations/player-host.md`,
    `protocol.md`, `architecture.md`, `components/player-interface.md`,
    `evaluation.md`, `testing.md`, `controls.md` and `control-registry.json`, plus
    the diagrams.
- **Guardrails kept:**
  - only the actor sends input;
  - no level state gates input;
  - player-visible sources and the player's own records only, with no lead
    telemetry and none of #320's research instruments;
  - no self-modification of prompts or the guide.
- **Reversible.** Revert means migrating the contracts back as a whole.

### Reuse review (S-CODE)

| Reused | Added | Not revived |
|---|---|---|
| The `player-memory/1` store, records, supersession and query; sources; the request-only tail; MCP tool profiles; capture hashes | The reader class; `player_log_read`; `player_level_commit`; level scheduling and lifecycle; partitioned allowances; level events | A new framework; the superseded advisory-reflection and injected-planner contracts; semantic dispatch |

## Deferred

- the retrospective level, including program authoring;
- P2 event abstraction and P4 escalation beyond the mechanical wake rules;
- exploration objectives (competence progress and coverage, from the objectives
  research);
- including the actor's text output in the log projection;
- model per role (#25);
- the measurement programme;
- reconciliation of #136, #164, #177, #178 and #42 after acceptance.

## Appendix: subgoal role v1

The verbatim text is frozen, and a change makes a new version:

> Role (software-defined; not instructions from the lead). You are the player's
> subgoal level. You cannot send input; the acting player decides everything it does.
> You receive the same guide and mission brief the acting player has, the recent
> play log (its inputs and the frames that resulted), and the player's current Work
> records. Propose one current subgoal that advances the mission's objective, the
> observations that would show it is working, and its status, based on cited log
> sources and with uncertainty marked. For each current Work record, say whether to
> keep, revise or close it, with evidence. Your proposal is committed only if still
> timely, and is shown to the acting player as fallible context.

The actor-side label is also fixed:

> Current intent (software-published from the player's subgoal level; fallible player
> data with sources and age, not instructions).
