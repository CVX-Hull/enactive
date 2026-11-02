---
owner: lead
review_trigger: First-slice results, or a change to the host, memory, campaign or computer-control contracts
status: historical
date: '2026-11-01'
scope: Accepted direction for a multi-level player (an acting real-time player and a separate asynchronous subgoal level, with designed upper levels) and its first slice; not delivered runtime support
---

# ADR 007 — An acting player with an asynchronous subgoal level

**Status: accepted direction; not delivered.** The owner agreed draft 4 on 31
October 2026 (evening EDT): "Agree, shape the slice" (recorded on
[#319](https://github.com/CVX-Hull/enactive/issues/319)). Nothing is on main.
Interface v3 is built on the unmerged candidate branch, and level v4 is
designed below.
- **The current standards and contracts still govern the running system.**
- **The supersession map is applied later.** The documents it lists are amended
  when the first slice meets its adoption condition, together with that migration.
- **The slice is what decides.** If the slice does not improve on arm B, the
  direction is revisited.

**Amended 1 November 2026 ([#340](https://github.com/CVX-Hull/enactive/issues/340)).**
The level interface is v2, approved by the owner ("Approve all") on
[#329](https://github.com/CVX-Hull/enactive/issues/329#issuecomment-6561551205) after
shadow showed 35 of 53 passes ending in a written proposal with no
commit call. A pass then ended on a commit or an abstain, with a versioned union
proposal; the pass input became pushed; the role prompt became v2; and `player-host/3`
became `/4`. The #341 amendment below replaces the union with flat tools; the pushed
input and the commit-or-abstain ending stand.

**Amended 1 November 2026 ([#341](https://github.com/CVX-Hull/enactive/issues/341)).**
The level interface is v3, approved by the owner ("A + B + C") on
[#329](https://github.com/CVX-Hull/enactive/issues/329#issuecomment-6563083931) after
shadow-2 refused every v2 commit: the model had to repeat a version constant inside a
`const`-tagged union that the OpenRouter-to-Gemini route apparently did not show it, and
the refusal never named the expected value.
- **Three flat terminal tools replace `player_level_commit`:** `player_level_keep`,
  `player_level_replace` and `player_level_close`, beside `player_level_abstain` with a
  closed reason code. The model supplies no record id and no version; software resolves the
  one current subgoal and stamps the contract version. Model-facing schemas use only the
  portable keyword set.
- **The reader profile shrinks** to `player_log_read`, `player_source` and the four
  terminal tools, since the pushed input already carries the current subgoal and the count
  of level records in player memory.
- **The last two logical requests of a pass offer only the terminal tools** (a provider
  retry reuses its request's declarations and does not move the window), a non-terminal
  call on them is refused without dispatch, and a terminal call refused on the last
  allowed request settles as `level-final-refusal`. A terminal call whose response the
  adapter lost ends the pass as `level-uncertain`; the driver reconciles it from the store.
- **Refusals name the failing field, the rule, the allowed values and a valid example
  call,** and say that abstaining is not the remedy for a fixable call.
- **Pre-spend checks:** a zero-token contract test of the production request, and a
  labelled engineering probe that replays recorded pass contexts.
- The role prompt is `subgoal-v3`; `player-host/4` becomes `/5` and `player-driver/4`
  becomes `/5`. The sections below state the amended design.

**Amended 1 November 2026 ([#344](https://github.com/CVX-Hull/enactive/issues/344)): level v4,
the episodic outcome level, as accepted direction.** The owner agreed: "I agree with your
recommendations and directions". The evidence is on
[#329](https://github.com/CVX-Hull/enactive/issues/329):
- **v3 is mechanically sound.** Shadow-3 and the persistent stage passed.
- **It restated the actor's own recent frames.** Only 1 of 106 commits cited anything the
  actor did not already hold, and the median look-back was 1 frame.
- **It never closed a subgoal,** in 106 commits.
- **Only the subgoal carried across sessions,** not its outcomes.

[Level v4](#level-v4-the-episodic-outcome-level) changes what the level reads, what it is
told and how subgoals end. It also designs the
[recursive memory pattern](#recursive-memory-designed) and the
[label-evolution role](#label-evolution-designed).

**Current state.** Interface v3 is built and evidenced on `adr7-candidate`; nothing is on main.

**Replacement.** The owner's direction is "good design instead of maintaining legacy code or
approaches", and readers may be added as needed. So [#346](https://github.com/CVX-Hull/enactive/issues/346)
replaces v3's mechanisms outright (S-MIGRATION), with no compatibility paths, and folds v4 into
every section. Until then, every section outside the #344 blocks describes v3 as built.

This is draft 4.
- **Draft 1** had the real-time player write its own memory. That conflicted with
  the owner's later direction and P1.
- **Draft 2** followed the owner's newest-first reconciliation on
  [#319](https://github.com/CVX-Hull/enactive/issues/319), but an architecture
  review found six places where it did not match the code.
- **Draft 3** fixes those six places.
- **Draft 4** designs in the levels above the subgoal level as architecture: a
  strategic/aspiration level and a retrospective level, with one recursive
  pattern. The owner asked: "What about layers above the reader layer per our
  discussions?" The first slice is unchanged: the actor plus the subgoal level.

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
| R5 | "Let's discuss before we implement any designs" | The design was discussed and agreed before any implementation ("Agree, shape the slice") |

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
| 4 | **Strategic / aspiration level** (LLM reader role; [later slice](#upper-levels-architecture-later-slices)) | Chooses which aspirations to pursue within viability, and when one is good enough. Works across episodes and sessions | The guide and mission brief, committed Work outcomes, and its own aspiration records, plus competence and viability statistics that software computes from committed records | Aspiration proposals; software commits them | Which aspiration the subgoal level serves. It sends no input |
| 5 | **Retrospective level** (LLM reader role; [later slice](#upper-levels-architecture-later-slices)) | Consolidates episodes into claims and procedures, with false-memory protection (P8). Works across sessions | Session logs, committed records and programs | Claim, correction and program proposals; software commits them | Which consolidations to propose. Adoption is never automatic: claims stay fallible, and programs run only when the actor chooses to |

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

*This section describes interface v3 as built on the candidate. [Level v4](#level-v4-the-episodic-outcome-level)
replaces its pushed input, binding, waking, revalidation and publication, and removes
`player_log_read`.*

- **Capability.** A new **reader** class in computer control, enforced by a
  per-class tool allowlist in `Application.call`, not only by `_guard`:
  - **Reader:** exactly `player_log_read`, `player_source` and the four terminal tools
    `player_level_keep`, `player_level_replace`, `player_level_close` and
    `player_level_abstain`, and nothing else. In particular it has no observe (which
    captures frames and spends budget), no input, no stop, no memory or program tool
    and no result tool: the pushed input carries the current subgoal.
  - **Actor:** refused all four terminal tools and `player_log_read`.
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
- **Pass.** On waking, software pushes the level its input, and the level ends the
  pass with exactly one tool call.
  - **Pushed input.** The pass prompt carries the served actor's log since the
    previous pass's projection (the latest 50 entries, oldest first with positions,
    and the omitted count if more are new) and the current level subgoal, if any:
    its ID, text, expected observations, status, confidence, sources, position and
    inputs since commit. The driver obtains the entries through the reader's own
    `player_log_read` path under `Application.serial`, so the position binding below
    is exactly what the prompt shows. The level may read more of the log, which
    extends the binding, and any cited frame. A failure of the push is a level
    failure and never reaches the actor.
  - **Forced tool calls.** The level host sends `tool_choice: required` on every
    request, so the model cannot end in prose. The level's text is discarded and
    shown to no one; only the four terminal calls below count.
  - **Reserved terminal requests.** Requests count as logical requests (one per inference
    request, however many HTTP attempts its retries use). On every logical request with
    two or fewer remaining, including that request, the host declares only the four terminal tools
    (it restricts the request's tool declarations; the history and the executable tool set
    are unchanged) and says so in the request's resource status. This reserves a repair
    slot for a refused call. A terminal call refused on the last allowed request settles
    as `level-final-refusal`, a counted outcome distinct from `request-limit`. A
    non-terminal call on a reserved request is refused without dispatch.
  - **Lost transport and persisted records.** A reader terminal tool has no collecting
    tool, so a `player-transport/1` unknown receipt on it ends the pass (`level-uncertain`);
    the driver reads the store's `service_operations` row for the identity afterwards
    (`committed` or `absent`; a discard writes no row) and counts it. Minting a reader
    refuses a store whose current level Work lacks `data.level_contract == "player-level/3"`
    (S-MIGRATION: migrate or start a fresh player store); nothing converts an older record.
  - **What ends a pass.** The pass ends after a `player_level_keep`,
    `player_level_replace` or `player_level_close` that software commits or discards, or
    after a valid `player_level_abstain`. A call rejected as a fixable tool error does
    not end it, and the model may correct it. A pass that ends any other way (for
    example a text-only terminal response) is a failed pass with the reason
    `level-no-proposal`, recorded and counted.
  - **The tools.** The level manages only its own subgoal: the current Work records with
    `data.level == "subgoal"`, at most one by construction. Other Work is out of its scope
    and untouched. Each tool is one flat object, every property required:
    - **`player_level_keep(reason, sources)`:** writes no record; the receipt says kept
      and gives the current id;
    - **`player_level_replace(text, expected_observations, status, confidence, sources,
      previous_outcome, previous_reason)`:** writes the new Work record. `status` is
      `open` or `blocked`. `previous_outcome` is `none`, `achieved`, `failed`, `abandoned`
      or `revised`, and is `none` exactly when there is no current subgoal; otherwise it
      also writes a superseding correction (a `revised` one supports the new Work). Its
      `sources` are the replace's sources;
    - **`player_level_close(outcome, reason, sources)`:** `outcome` is `achieved`,
      `failed` or `abandoned`; it needs a current subgoal and writes the correction only.

    Software resolves the current subgoal, so the model supplies no record id and no
    version, and stamps the contract version into the stored record data and the
    `player-level-commit/3` receipt. A wrong-state call (keep or close with nothing
    current, a `none` previous outcome over a current subgoal or another one with none) is a
    fixable tool error that names the current subgoal state and the valid tool for it and
    keeps the bound. A keep alongside a new subgoal cannot be expressed.
  - **Portable schemas.** The model-facing schemas use `type` on every node, string
    enums, all inlined, and plain objects; no `const`, `oneOf`, `anyOf`, `$ref`,
    `uniqueItems` or nested objects beyond arrays of strings. The research behind this
    ([LLM tool interface design](https://github.com/CVX-Hull/enactive/issues/329#issuecomment-6563083931))
    found that the schema a Gemini route shows may not be the one the host validates, so
    host validation is the only enforcement and nothing may depend on the model seeing a
    constant. Refusals come from the host: each failing field's path, rule, allowed
    values or limits, the received value truncated to 120 characters and a minimal valid
    example call, then the line "Fix the call and resend it; abstaining is not the remedy
    for a fixable call."
  - **Abstain.** `player_level_abstain(reason_code, reason, sources)` ends the pass
    without a change when the evidence supports none of keeping, replacing or closing.
    `reason_code` is `insufficient_evidence`, `transient_screen_state`,
    `no_change_needed` or `other`; `sources` may be empty. Nothing is written, the
    reader's bound is cleared as a terminal call clears it, and the host trace records a
    `level-abstain` event carrying the code (`player-level-abstain/2`). Abstentions are
    counted by code.
- **Software-mediated commit (P5).** The level calls `player_level_keep`,
  `player_level_replace` or `player_level_close`.
  - **The position is software-bound.** The custodian takes the pass's position from
    the highest log position its own `player_log_read` calls returned in that pass,
    which includes the pushed read. The model never supplies it.
  - **Commit conditions.** Software commits only if the actor has moved fewer than S
    inputs past that position, and no actor handoff or session boundary has
    occurred since.
  - **Atomicity.** The commit runs under `Application.serial`, so no input or
    handoff can interleave. The Work record and any superseding correction are
    appended in one transaction, which needs a multi-record `Memory` append. That
    is an API change, not a format change.
  - **Discards.** A proposal that fails the check is discarded and logged in the
    level's host trace, never in the store. A discard ends the pass, as a commit does.
- **Waking.** It wakes when the log has advanced K inputs, at actor start, and at
  fixed budget fractions. At most one pass is in flight. It never runs on an empty
  delta ([player-interface standard](../standards/player-interface.md)).
- **Revalidation.** At each actor start, the first pass is given the open subgoal and
  may keep, replace or close it, or abstain. An abstaining start pass leaves the earlier
  subgoal current, and its age in sessions still shows in the actor's intent tail, so
  revalidation is offered, not enforced. Start-pass abstentions are counted separately.
- **Publication.** The actor's request-only tail shows the latest committed Work
  record, labelled fallible, with its sources and its age in inputs, seconds and
  sessions. The actor may ignore it.
- **Its prompt** is frozen, versioned and game-agnostic
  ([appendix](#appendix-subgoal-role-v3)), and reviewed against the no-nudge rule.
  It steers toward the mission's objective using the same frozen guide and brief
  the actor has, so it adds no lead content. Software triggers stay mechanical; the
  level's semantic judgement belongs to the player system (ADR006).
- **Model.** The same model and pinned route for both roles. The slice uses
  Gemini 3.8 Flash, #314's and #320's reference route, for comparability. The
  deployed selection is DeepSeek Flash1017; switching routes is a separate
  decision. Each role has its own counted allowance.

## Level v4: the episodic outcome level

**Status:** accepted direction ([#344](https://github.com/CVX-Hull/enactive/issues/344)),
built by [#346](https://github.com/CVX-Hull/enactive/issues/346) after the offline ladder
([#345](https://github.com/CVX-Hull/enactive/issues/345)).

**Why it changes.** Interface v3's level read the actor's own log delta, so it could only
restate it. In lens terms it was a stride-1 level: its view of the past was the actor's view.
- **Nothing tested a subgoal.** `expected_observations` were written and never read, so no
  subgoal could fail or close.
- **Nothing carried across sessions but the subgoal.** What the player tried, with whom and
  with what result was lost at each session boundary.

**v4 keeps:**
- one input writer, the actor;
- one memory writer, the custodian's commit path;
- the software-mediated commit and its staleness check S, with a new binding (item 4);
- the four level terminal tools and the portable schema rules;
- the forced tool calls and reserved terminal requests;
- the narrowed actor profile;
- the intent bound of about 1 KB.

**v4 changes five things.** All mechanical state below is computed by software, and the LLM
roles only propose. The architecture review found 21 issues with the first draft of this
section (`2d3d397`); this text resolves them.

1. **Episode cutter.** Software in the playing system, the campaign driver, never
   `harness/computer`. It reads the session's captures as player-visible sources.
   - **Distance.** Each capture becomes a 32 × 20 greyscale box-pooled thumbnail. The distance d
     of an input is the mean absolute pixel difference, divided by 255, between that input's
     result capture and the result capture of the previous input that has one. An input with
     no result capture yet (pending or unknown) has no distance and cannot close an episode.
   - **Closure.**
     - **On content:** an episode closes after input *i* when d(*i*) ≥ θ and the episode holds
       at least *m* inputs. The input that crosses θ is the first input of the next episode, so
       an episode ends on the last stable screen.
     - **At the cap:** an episode closes when it holds C = K inputs.
     - **Mechanically at session edges:** an episode also closes at a handoff, a stop or the
       session's end, so the last partial episode is still recorded.
   - **Frozen boundaries.** Boundaries are frozen once written and never recomputed.
   - **No game semantics.** Every trigger is mechanical, and ADR006 and the no-game-semantics
     rule hold. θ is fitted per game by one game-independent procedure from player-visible
     captures (P-GENERALITY).
2. **Episode recorder.** A second reader per actor, with its own role: one LLM pass per closed
   episode.
   - **Custody.**
     - `computer-session/2` becomes `/3`: the `one_reader_per_actor` index becomes unique on
       (served actor, role), and an `actors.reader_role` column holds `level` or `recorder`.
     - Write authorization admits a recorder only for `player_episode_record` and
       `player_episode_abstain`. Both are reader writes that settle the episode (item 3).
     - Both readers keep the reader stage's exclusions from `add_actor` and `max_actors`.
   - **Pushed input** (made by the driver under `Application.serial`):
     - the episode's operations, as key tokens and positions;
     - a **baseline frame**: the result capture of the last input before the episode;
     - up to 6 of the episode's own frames: always its last, and then those with the largest
       thumbnail distance from their predecessor, in capture order;
     - each frame as an image part, marked with its source id and role (baseline, in-episode
       or last).

     #345's post-hoc check chose this frame policy. With first and last frames only, a change
     at an episode boundary was invisible.
     - the id, text and ordered expected observations of the subgoal current at the episode's
       first input.
   - **Reader profile:** `player_source`, `player_episode_record` and
     `player_episode_abstain`.
   - **`player_episode_record(attempted, counterpart, observation_status, changed, residual,
     confidence, sources)`:**
     - `changed` says what visibly changed in the player's own state between the baseline frame
       and the last frame, citing the frames that show it. It is an empty string when nothing
       changed.
     - **Known limitation:** a change hidden behind an occluding screen at both ends of the
       episode stays invisible. Carrying recorded state forward between episodes was tried post
       hoc in #345; it did not recover such a change and added false positives, so it is not
       adopted.
     - `observation_status` is an array of `seen`, `not_yet` or `contradicted`. Its length must
       equal the pushed subgoal's number of expected observations, or it is empty when there is
       no subgoal.
     - `counterpart` and `residual` may be empty strings.
     - `confidence` is a number from 0 to 1.
     - `sources` holds at most 4 ids from the episode.
     - Every field is required, and the schema is flat.
   - **`player_episode_abstain(reason_code, reason, sources)`** has its own codes:
     `unreadable_frames`, `no_player_action` and `other`.
   - **Storage: every episode settles into the store.** The custodian appends exactly one
     `claim` per closed episode, with:
     - `data.level == "episode"` and `data.level_contract == "player-episode/1"`;
     - the episode's session, actor and position range, and the pushed subgoal's id;
     - `data.settled`, with one of four values:
       - `recorded`: the recorder's fields and marks;
       - `abstained`: the code and reason, with no marks;
       - `failed`: no marks;
       - `dropped`: no marks;
     - `data.writer`, which is `recorder` for a recorder call and `software` for a settle the
       driver reports (a failed or dropped episode) through a custodian method under
       `Application.serial`.

     The store copies only cited frames: at most 4 per episode.
     - **At store capacity** (256 MiB, no eviction):
       - a failure to remember stops the recorder and the level for the rest of the session;
       - **the actor continues**, because no level state gates input;
       - the lineage ends at the next session boundary as a recorded failure;
       - nothing is evicted silently.
     - **Recall integrity.** Recall and counts trust only claims whose `level_contract` is
       `player-episode/1` and whose `data.writer` the custodian stamped. Because the stamp is in
       the record itself, the check also works on earlier sessions' claims.
       - **Enforced, not assumed.** The custodian's general memory-append path refuses any record
         that sets `data.level == "episode"` or `data.writer`; only the custodian's settle path
         writes them. A flat actor that writes memory cannot forge one.
     - **Format.** `player-record/1` and `player-memory/1` are unchanged.
   - **Backlog.** Closed episodes wait in a FIFO queue. At most one recorder pass is in flight.
     - **Drops:** if more than 3 episodes are waiting, the oldest waiting episode settles as
       `dropped`.
     - **Settling:** every closed episode ends with exactly one settle claim, whether recorded,
       abstained, failed or dropped.
3. **Closure and stall, in the custodian.** Observation status and stall are **derived at read
   time** from the store and are never stored on the Work record, which stays append-only.
   - **What counts.** For the current subgoal *g*, the custodian reads its trusted episode
     claims: those committed after *g* whose pushed subgoal id is *g*.
     - **Marks** count only from `recorded` claims with confidence at least the floor *c*.
     - **Stall** counts every settled claim (item 2), so all of it is derivable from the store,
       across sessions too.
     - **Other subgoals.** A claim whose subgoal id is not *g* is ignored, so marks are never
       attributed to the wrong subgoal.
   - **Status.** An observation is `seen` if some counted claim marks it seen and no later
     counted claim marks it contradicted. It is `contradicted` if its latest counted mark is
     contradicted. Otherwise it is `not_yet`.
   - **Closure.**
     - **When:** the episode record that makes every expected observation `seen`.
     - **What is written:** the custodian appends the closing correction in the same
       `append_many` transaction as that record, with the recorder reader as record actor. The
       correction carries outcome `achieved`, `data.level == "subgoal"`,
       `data.level_contract == "player-level/4"` and `data.by == "software"`. Its `supports`
       are the counted claims' ids, and its sources are capped at 16.
     - **Not vacuous:** `player-level/4` requires at least one expected observation on
       replace, so closure is never vacuous.
   - **Stall.**
     - **When it fires:** *g* is **stalled** after N consecutive settle claims since *g* with
       nothing newly seen. An `abstained`, `failed` or `dropped` settle counts as nothing newly
       seen, and so does a `recorded` one below the floor.
     - **N:** given at reader minting, like S.
     - **Refusals:** while *g* is stalled, `player_level_keep` and `player_level_abstain` are
       fixable tool errors that name `player_level_replace` and `player_level_close`. This
       applies to start passes too, so revalidation stays offered, not enforced, except for a
       stalled subgoal.
     - **Calibration:** #345 sets N, and may choose an anytime-valid e-process instead if it
       does better at an equal false-alarm rate.
   - **Contradiction.** While any observation of *g* is `contradicted`, a keep must cite, in
     its `sources`, the source of a counted claim with that mark. Otherwise it is a fixable
     tool error.
   - **Races.** At push time the driver binds the current subgoal id, together with the
     position, under `Application.serial`. The model never supplies a record id. The custodian
     refuses the commit as stale (a discard) if the current subgoal then differs from the bound
     one, because a closure or a replace happened meanwhile.
   - **Contracts.** `player-level/3` becomes `/4` and `player-level-commit/3` becomes `/4`
     (pushed subgoal id, derived status, closure). Minting a reader refuses a store whose
     current level Work is not `/4`; migrate, or start a fresh store. The rules are documented
     in the computer-control contract's level section.
4. **Subgoal level v4.**
   - **Pushed input:** closed episodes and software counts, never the actor's raw log:
     - the episode records committed since its last pass;
     - the current subgoal with its derived status, its stalled flag and its id;
     - counts per subgoal: episodes, seen, contradicted, closures and failures;
     - recalled episodes (item 5).
   - **Reader profile:** `player_source` and the four terminal tools.
   - **`player_log_read` and `player-log/1` are removed** (S-MIGRATION). The driver reads
     operations in-process through the `Application`. The refusal text and the `player-host`
     rule that names `player_log_read` change with them.
   - **Binding.** The driver binds the pass's position under `Application.serial`, replacing
     v3's reset-and-read.
     - **The bound** is the end position of the served actor's newest settled episode in the
       current session, whatever its outcome: record, abstain, failure or drop. So a pass woken
       by a settle with no record still binds where it should.
     - **Recalled earlier-session records** never bind.
     - **At actor start,** before any episode has settled, the bound is 0.

     The custodian's staleness check S applies from that bound.
   - **Waking:**
     - at actor start;
     - after every episode settles: record, abstain, failure or drop;
     - at the 25, 50 and 75% budget fractions, but only when something has settled since the
       last pass. That keeps the empty-delta rule of the player-interface standard.
   - **In flight:** at most one level pass. Wakes that arrive during a pass coalesce into one
     pass over the newest records.
   - **Coupling.** S must exceed the p95, in actor inputs, of a recorder pass plus queue wait
     plus a level pass. #345 checks this on recorded latencies before any build. If it fails,
     the question goes to the owner instead of being tuned around.
5. **Recall and the intent tail.**
   - **Candidates:** the trusted episode claims from earlier sessions and from this session.
   - **Score:** BM25 relevance over the record's text fields, with the current subgoal's text
     and expected observations as the query (k1 = 1.2, b = 0.75). The score is multiplied by
     reliability, which is the recorder's confidence, and by 1.5 when the record has a
     residual. There is no demotion in the first build.
   - **No current subgoal:** recall shows the most recent records instead.
   - **The level sees** the top 10.
   - **The tail.** `player-intent/1` becomes `/2`, with a fixed allocation within the
     unchanged bound of 1,024 bytes.
     - **Labels count.** The labels and omission markers now count toward the bound. They were
       extra before, so this changes `player-host/6` (`formatIntentTail`) and its contract text.

     | Part | Budget |
     |---|---|
     | The intent label (about 130 bytes) | as written |
     | Subgoal text, truncated | ≤ 160 bytes |
     | Its expected observations, each with a one-word status, truncated | ≤ 200 bytes |
     | Confidence, age and the subgoal's 8-character short record id | ≤ 50 bytes |
     | The recall label (118 bytes) | as written |
     | 3 recall lines, each ≤ 120 bytes, plus line breaks | ≤ 365 bytes |

     - **Recall lines** are the top 2 by score plus 1 exploration line. The exploration line is
       an earlier-session record outside the top 10, drawn uniformly with a seed fixed per pass
       from the session id and pass index.
     - **What a line shows:** one full source id, the record's first cited frame (about 36
       bytes), which the actor can read with `player_source`, then its outcome and attempt text,
       truncated to the rest of the line.
     - **Markers:** each part's omission marker comes out of that part's own budget, so a
       truncated tail still fits the bound.

     Recall is therefore never cut first. Omitted bytes are logged per part.

     **Check before build:** #345 checks on recorded data that three useful recall lines
     survive at the bound. If they cannot, the question goes to the owner, because the bound is
     the owner's.

**Owner parameters:**
- K = 10 becomes the episode cap C. It is still the longest run of inputs between wakes when
  the recorder settles.
- S = 10, the 25/50/75% fractions and the bound of about 1 KB keep their values. S's coverage
  is checked as above.
- **A new preference, the target mean episode length L̄, is proposed as 6 and set by the
  owner.** Together with *m*, it now sets the cadence that K set before.

**Cost.** Per mean episode of L̄ inputs, v4 runs one recorder pass (1–2 requests) and one level
pass (2–3 requests). At L̄ = 6 that is about 0.5–0.8 level-side requests per actor input,
roughly 2–3× v3's overhead. The shadow measures it against the cadence, and the probe's
adoption condition weighs it.

**Contracts** are listed under [Boundary impact](#boundary-impact). The role prompts are
[`episode-v1` and `subgoal-v4`](#appendix-v4-role-prompts-drafts), frozen at build after the
no-nudge review.

**Scope of this amendment.** Every section other than this one, the #344 notes and the designed
subsections below describes interface v3 as built on `adr7-candidate`. #346 folds v4 into
them.

## Upper levels (architecture; later slices)

These levels are designed here so the architecture is whole. The first slice builds
only what the subgoal level needs, and later levels may revise the shared mechanism
under S-MIGRATION. Each upper level gets its own shaped child, pre-registration and
owner decisions before any build. Their sources and revisit triggers are tracked in
[#325](https://github.com/CVX-Hull/enactive/issues/325).

**Where the levels run.** Every level runs as a reader inside a live session, the
only place a reader capability exists. Each upper level uses the same model and
route first (#25).

**One recursive pattern (P11).** Every level above the actor is the same kind of
component:

| Part | Subgoal level (first slice) | Strategic / aspiration level | Retrospective level |
|---|---|---|---|
| Capability | Reader | Reader | Reader |
| Input projection | The actor's log delta | Committed Work outcomes since its last pass, plus software statistics | The player store's records and sources, read at session start |
| Proposal | One current subgoal: keep, replace or close it | Active aspirations, with their grounded progress variable and status | Claims with evidence, corrections, candidate programs |
| Software commit | Staleness in actor inputs (S), at a position bound from the level's own reads; no handoff since | Staleness in Work records committed since the level's own read, bound by the custodian; no session boundary since | Schema, sources and supersession checks; nothing committed as authority |
| Published to | The actor's intent tail | The subgoal level's input (the objective it serves) | The subgoal level's input: candidate programs and claims it may cite. Committed claims are a store the levels read, not a publication |
| Wakes | K actor inputs, start, budget fractions | A subgoal closes or fails, or a session starts | Session start, or a record-count threshold |

**How intent and programs reach the actor.**
- **Each level publishes only to the level below it (P3).** The actor sees only the
  subgoal intent.
- **Programs.** Retrospective-authored programs reach the actor only when the
  subgoal intent cites their IDs. The actor's program tools read and run by ID, and
  it learns IDs only from the intent.
- **Viability.** A viability concern reaches the actor only through a revised
  subgoal; direct escalation (P4) is deferred.
- **Earlier sessions.** Reading earlier sessions' operation logs, which live in
  separate session stores, is a boundary decision for the retrospective level's
  slice.

**The strategic / aspiration level follows the objectives research** (the
*Aspiration and goal selection objectives 2* report, `5f25bd42…`; lead reading,
not adopted). Its structure is a cascade:
1. **Viability as a constraint.** It is stated in grounded, player-visible
   variables, with a credible bound computed by software from committed outcomes.
2. **Aspirations from above.** The owner's example is "max out a skill". Each one
   needs a grounded progress variable that passes a measurement check.
3. **Goal choice by absolute competence progress,** computed by software from
   attempt and success counts, with a uniform exploration floor.
4. **A satisficing stop** at level M with confidence 1 − δ.

The division of labour:
- **The LLM** proposes candidate aspirations and their variables. Each variable is
  drawn from a game-agnostic menu of variable *types* (Boolean event, ordinal level,
  bounded numeric), never from a lead-authored list of aspirations.
- **Classical computation** ranks and stops (P-GENERALITY's balance).
- **M, δ, slack and priority order** are owner-supplied preferences, frozen per run
  in the profile. No validated rule exists for fitting them.

The level works inside the frozen mission brief and does not replace it. Aspirations
the owner supplies enter only through that brief.

Two choices are left to that level's slice:
- how an aspiration enters goal selection: as a weight w(m), as the progress
  variable, or as a constraint;
- reuse by hindsight relabelling into a cell archive, the report's fifth structure.

**The retrospective level** takes over program authoring, which was removed from
the actor. It proposes claims and procedures with sources, uncertainty and
supersession. Its risk is persistent self-written error (More Memory, Worse Agents),
so its slice must measure claim accuracy and propagation before anything it writes
is resurfaced.

**Entry conditions:**
- **Strategic level:** the first slice shows the subgoal level opening, holding and
  closing subgoals, with intent accuracy above its pre-registered floor.
- **Retrospective level:** enough committed records across sessions exist to
  consolidate (a threshold set in its pre-registration).

**Record kinds.** Aspirations use `decision` records, and claims use `claim`
records, so there is no record-format change.
- **The typed fields are the terminal-tool contract.** The flat `player_level_replace`
  arguments are the typed fields; the custodian validates them, stamps the contract
  version (`player-level/3`; `/4` under level v4) and writes them into `data`.
- **Episode records** (level v4) are `claim` records with `data.level == "episode"`
  (`player-episode/1`). The retrospective level consolidates those claims into further claims
  and procedures.
- **A level discriminator in `data`** separates level-written records from other
  writers' records of the same kind (arm B, older stores).
- **Links.** Work records link to their aspiration through `supports`.
- **Statistics read the store directly.** Software competence and viability
  statistics read the store over those validated fields, including closed outcomes
  in superseding corrections. They do not rely on `query`'s 50-record, unsuperseded
  default.
- **Later format change.** If records later need typed fields of their own,
  `player-record/2` is that slice's decision.

### Recursive memory (designed)

The episode recorder's kernel applies to its own output. It reads closed units from below and
writes one unit with an outcome and a residual. Applied again, it gives chapters over episodes,
eras over chapters, and so on. **Compression recurses; decisions do not.** Deciders sit only at
grains where a real choice exists:
- the subgoal level reads episodes;
- the strategic level, as designed above, reads committed Work outcomes and software
  statistics. Once chapters exist, it reads those too. Which chapter-level inputs it uses is
  that slice's decision.

The retrospective level owns building chapters.

**Rules:**
- **When to merge, and where.** A capacity trigger says when; content says where. When a level
  holds *b* unmerged units, the adjacent pair with the weakest boundary merges into one unit
  above. Height grows with the logarithm of history, and cost is a convergent geometric series.
- **Each level reads what the level below cannot,** because its units span more time or
  sessions. A level that re-reads the window below is a narrator.
- **The upward message is the residual:** what the units below delivered against the level's
  own expectation, not a summary of summaries.
- **Units group two ways:** by time (chapters), and by theme (all episodes that served the same
  subgoal or involved the same counterpart). The structure is therefore a graph, not a strict
  tree.
- **Provenance and exact counts.** Every unit keeps provenance down to raw log entries. It also
  carries exact counts (attempts, seen, contradicted, durations) that roll up without loss. A
  challenged unit is re-derived from its sources, never from a summary of summaries.

Levels above the episode level are built when persistent lineages grow past one level's
capacity; their own slice measures whether chapter recall helps beyond episode recall.

### Label evolution (designed)

Classical methods need stable discrete labels: transition and successor-representation models,
change detection, competence-progress statistics per situation and goal, and revisit counts by
entity. Label evolution grows them from experience. It is an **offline analysis that the lead
runs on recorded logs**, as evaluation work, not a player role inside a live session.
- **Not self-modification.** A codebook it accepts becomes a new frozen recorder prompt and a new
  record-contract version, reviewed against the no-nudge rule, migrated under S-MIGRATION and
  admitted at a session boundary. So it is not runtime self-modification of prompts or the
  guide.
- **Later in-play role:** turning it into a player role inside sessions is the retrospective
  level's slice. That includes its reading of earlier-session logs.

**The loop:**
1. **The labeller,** an LLM, applies a versioned codebook: a finite menu of definitions,
   examples and typed fields.
2. **Classical diagnostics** score each label on:
   - cross-family reliability and test–retest agreement;
   - predictive value, as a held-out log-loss gain on next state or outcome;
   - lumpability;
   - residual mass.
3. **The proposer,** an LLM, sees those scores and the worst-confused examples, and proposes
   edits: split, merge, add, redefine or add a field.
4. **A gate fixed in advance** accepts an edit only if it improves the objective on held-out runs
   without dropping reliability below a floor. The objective is predictive information or
   description length. It keeps an entropy and coverage floor.
5. **Migration.** A new codebook version relabels the affected history from the immutable log.
   Every analysis names its version (S-MIGRATION).

The episode recorder's fields are the first codebook. The loop is piloted offline by
[#347](https://github.com/CVX-Hull/enactive/issues/347) before it is built into the
retrospective level.

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

*This section states interface v3. For level v4's per-episode cost and the coupling rule
"S > p95 of recorder pass, queue and level pass", see [Level v4](#level-v4-the-episodic-outcome-level).*

- **Requests per pass.** With the pushed input and a forced ending call, a pass is
  about r ≈ 2–3 provider requests: optionally read more of the log or a source, then
  commit or abstain. There is no read-the-log opening turn and no closing turn
  (v1 was about 4). At #298's response median of about 12 s, that is about 24–36 s
  per pass. The p95 is about 25 s per request.
- **How far the actor moves meanwhile.** The actor makes about one input per
  request, so it advances about 2–3 inputs during a median pass and about 4–6 during
  a p95 pass.
- **Coupling (P12).** S must exceed the p95 inputs per pass, for example S = 10.
  "At most one pass in flight" prevents overlap. K, S and pass latency are set
  together, and are checked in the shadow stage.
- **Overhead.** At K = 10, a 100-attempt actor allowance (#314's) gives about 7–8
  passes, about 15–23 level requests or roughly 20–30%, plus start and budget passes.
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
| Episode threshold θ (v4) | Calibration, fitted per game from player-visible captures | Quantile of consecutive thumbnail distances chosen so the mean episode length hits a target. Fitted on recorded runs ([#345](https://github.com/CVX-Hull/enactive/issues/345)), then frozen in the profile by value and fitting digest. Recalibrated when the game, resolution or theme changes |
| Target mean episode length L̄ (v4) | Preference, owner-set (proposed: 6). With *m*, it sets the cadence K used to set | Agreed with the owner alongside K and S. #345 fits θ to it |
| Episode cap C and minimum length *m* (v4) | Preferences | C = K. #345 sets *m* (its registry uses 2) |
| Stall test N, or e-process parameters (v4) | Calibration, with a false-alarm preference | Chosen in #345 by closure replay on recorded subgoals, at a stated false-alarm rate; then frozen |
| Confidence floor *c* for counted episode marks (v4) | Preference | Set in #345 from cross-family agreement by confidence |
| Recorder backlog bound (3) (v4) | Preference | Drops are counted |
| Recall: 2 top lines plus 1 exploration line in the tail, 10 for the level, residual weight 1.5, the tail byte allocation (v4) | Preferences within the fixed bound | Omitted bytes logged per part. #345 checks that recall survives at the bound; the follow rate is measured |
| BM25 parameters (v4) | Fixed standard values (k1 = 1.2, b = 0.75) | Not fitted |

**What is game-specific.** The procedures are game-independent. Only calibrations are fitted
per game, each by one game-independent procedure from player-visible experience (P-GENERALITY).
θ is such a calibration. Nothing is hand-set for CDDA.

## Supersession map

Each of these is amended when the first slice meets its adoption condition, together
with that migration:

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

## First slice (outline; shaped in [#326](https://github.com/CVX-Hull/enactive/issues/326), not started)

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
  - **Mechanism:** passes, commits, discards, abstentions (with their reasons) and
    failed passes; intent age; subgoals opened,
    revised and closed.
  - **Intent accuracy:** a blind audit of committed intent against the log, plus
    the actor's follow rate when the intent is wrong. This covers the More Memory,
    Worse Agents risk.
  - **Secondary:** actor latency and lock wait against the cadence, and cost by
    role.
- **Adoption condition.** Adopt only if the level improves on arm B in the
  pre-registered direction, within the cadence and an accepted cost. An
  underpowered null leaves the status quo, reported as underpowered.

**Amended by #344 for level v4.**
- **Done for v3:** stages 1–3 ran and passed for interface v3, as recorded on #329.
- **Retired:** the v3 probe plan.

The v4 evidence, rescoped onto #329, is:
- **Stages:**
  1. the offline ladder on recorded runs (#345);
  2. a v4 shadow;
  3. a pre-registered probe in **persistent lineages**, several sessions carried forward per
     lineage, because outcome recall can only matter across sessions.
- **Arms:**
  - flat;
  - arm B;
  - the narrowed actor with v4;
  - optionally, v4 with recall limited to the current session, which isolates the
    cross-session part.

  The fourth arm (narrowed actor, no level) is decided with the owner at pre-registration.
- **Primary metric:** retained change per session. This is #314's M1, "the first retained change
  in inventory, carried weight, worn or wielded items, a consumed item or a status indicator,
  confirmed in a later frame". It is tightened beforehand to substantive changes caused by the
  player: no first evidence only in the message log, and no status change driven by passing
  time. It is scored by blind auditors from two model families, with their agreement reported.
- **Adoption contrast:** v4 against arm B on the primary metric pooled over sessions, in the
  pre-registered direction. The arm × session-index slope is the pre-specified learning test.
- **Power:** a power simulation for both, set before spend under S-EVIDENCE. An underpowered null
  is reported as underpowered.
- **Secondary metrics:**
  - semantic revisits, meaning time spent at counterparts or places already visited with no new
    outcome. They are labelled by an LLM and cross-checked across families.
  - the longest replayed stretch within a run. This is lens test T3′'s only statistic that passed
    its planted-replay power check (#329).
- **Carried over from v3:** the mechanism counts, intent accuracy, actor latency and lock wait
  against the cadence, and cost by role.
- **Audit of software's inputs.** A blind cross-family LLM audit checks the recorder's marks and
  the precision of software closures and stalls, because software acts on those LLM marks.
- **Manipulation check:** the intent tail must carry information the actor did not already hold.
  The measure is lens test T1's marginal coverage: the share of tail items whose sources the
  actor had not received. It must be above zero, or the run is void as a test of v4.
- **No human labels** (owner, 1 November 2026).
- **The adoption condition is unchanged.**

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
  - **Player tools:** `player_log_read`, `player_level_keep`, `player_level_replace`,
    `player_level_close`, `player_level_abstain`, `player-level-commit/3` and
    `player-level-abstain/2` (#341), the actor's narrowed
    profile, `player-handoff/1` to `/2`, and the multi-record `Memory` append
    (`harness/player_tools.py`, `harness/player_mcp`, `harness/player/memory.py`).
  - **`player-host/2` becomes `player-host/3`, `/3` becomes `/4` (#340) and `/4` becomes
    `/5` (#341):** roles, tool profiles, intent tail, and the `level-pass`,
    `level-commit`, `level-discard`, `level-abstain` and `level-reserved-request` events;
    a level pass sends `tool_choice: required`, offers only the terminal tools on its last
    two requests, ends on a commit, discard or abstain, and otherwise settles
    `level-no-proposal` (or `level-final-refusal` when a terminal call is refused on the last
    allowed request). The `player-driver` disposition (`/3` to `/4` to `/5`) counts keeps,
    replaces, closes, discards, abstains by reason code, failed passes and final refusals.
    `campaign-run/4` keeps its shape and freezes `subgoal-v3` by digest.
  - **`campaign-run/3` becomes `campaign-run/4`:** one level host, partitioned
    allowances and its lifecycle (`tools/campaign_package.py`, `campaign_run.py`,
    `campaign_player.py`, `investigation_live.py`).
  - `player-memory/1` and `player-record/1` are unchanged.
  - **Level v4 ([#346](https://github.com/CVX-Hull/enactive/issues/346)):**
    - **`player-host/5` becomes `/6`:** the episode recorder role and its pass; the
      `episode-pass`, `episode-record` and `episode-abstain` events; the v4 level's pushed input;
      and the v4 intent-tail format.
    - **`player-driver/5` becomes `/6`:** the episode cutter, recorder passes and their FIFO
      backlog, reporting failed and dropped settles to the custodian, binding the position and
      subgoal id at push, waking on settle, and the counts. Closure and stall belong to the
      custodian, not the driver.
    - **`player-level/3` becomes `/4`:**
      - at least one expected observation on replace;
      - software closure corrections (`data.by == "software"`);
      - observation status and stall, derived at read time and never stored on the Work;
      - stores refused unless they are `/4`.
    - **New:** the `player-episode/1` record data, and the receipts `player-episode-record/1`
      and `player-episode-abstain/1`.
    - **`campaign-run/4` becomes `/5`:** the v4 profile (θ and its fitting digest, C, *m*, the
      stall test, the recall sizes) and the `episode-v1` and `subgoal-v4` prompts, frozen by
      digest.
    - **`computer-session/2` becomes `/3`:**
      - a reader role column, with one reader per (served actor, role);
      - the recorder's write authorization for `player_episode_record` and
        `player_episode_abstain`, and the custodian method for driver-reported settles;
      - the custodian's v4 rules: the binding pushed by the driver, closure in the record's
        transaction, stall refusals derived at read time, the contradiction citation rule, and
        refusal of a stale subgoal id;

      (`harness/computer/store.py`, `runtime.py`, `harness/application.py`,
      [contract](../contracts/computer-control.md)).
    - **`player-level-commit/3` becomes `/4`**, and `player-intent/1` becomes `/2` with its
      fixed byte allocation. `player-level-abstain/2` is unchanged.
    - **Removed:** `player_log_read` and `player-log/1`, and the host rule that a level host
      includes `player_log_read`.
    - **`campaign-run/5`** also carries the recorder's allowance, its partition and lifecycle,
      and `episode_cap`, which replaces `inputs_per_pass` and must equal K.
    - `player-record/1` and `player-memory/1` stay unchanged: episodes are `claim` records with a
      level discriminator.
    - **Callers v4 adds to the list below:**
      - `tools/level_schedule.py`, `tools/level_offline.py`, `tools/level_probe.py` and
        `tools/player_roles/`;
      - `harness/player/contracts.py`, `harness/player_tools.py` and `harness/player_mcp`;
      - `tests/test_player_level.py`, `tests/test_level_schedule.py` and
        `tests/test_level_probe.py`;
      - `docs/operations/campaign-run.md` and `docs/contracts/computer-control.md`.
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
| The `player-memory/1` store, records, supersession and query; sources; the request-only tail; MCP tool profiles; capture hashes | The reader class; `player_log_read`; `player_level_keep`, `_replace` and `_close`; `player_level_abstain`; level scheduling and lifecycle; partitioned allowances; level events | A new framework; the superseded advisory-reflection and injected-planner contracts; semantic dispatch |

## Deferred

Each item is tracked, with its owner source and revisit trigger, in
[#325](https://github.com/CVX-Hull/enactive/issues/325):
- **building** the strategic / aspiration and retrospective levels, which are
  designed above; each needs its own slice;
- **building** the recursive memory levels above the episode level, and the label-evolution
  loop, which [#347](https://github.com/CVX-Hull/enactive/issues/347) pilots offline first;
- a searchable raw-log arm with no summaries, kept as a later comparison;
- **a smarter episode cutter** (owner, 1 November 2026: "can we do it in a smarter way? … fine
  with starting with the current approach"). Candidates:
  - a multi-signal change score (screen distance, a change in key-token pattern, the end of
    identical captures, tool errors) under Bayesian online change-point detection;
  - propose and verify: the mechanical score proposes, and the recorder confirms the boundary
    at candidates only;
  - boundaries driven by expectations: an episode closes when a mark flips;
  - boundary models learned from evolved labels.

  Each is compared offline against the mechanical cutter on recorded runs, using #345's
  measures, before any replacement;
- P2 event abstraction and P4 escalation beyond the mechanical wake rules;
- exploration objectives (competence progress and coverage, from the objectives
  research);
- including the actor's text output in the log projection;
- model per role (#25);
- the measurement programme;
- reconciliation of #136, #164, #177, #178 and #42 after acceptance.

## Appendix: subgoal role v3

The verbatim text is frozen, and a change makes a new version. Versions 1 and 2 are
removed; v3 changes only the sentence that names the tools:

> Role (software-defined; not instructions from the lead). You are the player's
> subgoal level. You cannot send input; the acting player decides everything it does.
> You receive the same guide and mission brief the acting player has; instructions
> addressed to the acting player are not for you. Software supplies the served player's log since your
> last pass (its inputs and the frames that resulted, as source ids) and its current
> subgoal, if any; you may read more of the log and any cited frame. Then end the pass
> with exactly one tool call. Call player_level_keep, player_level_close or
> player_level_replace: keep the current subgoal, close it, or replace it with one
> subgoal that advances the mission's objective, with the observations that would show
> it is working, its status, cited sources and marked uncertainty, and the outcome of
> the subgoal it replaces. Call player_level_abstain if the evidence supports none of
> these. Only these calls count: your text is discarded and shown to no one. A commit is
> accepted only if still timely, and is then shown to the acting player as fallible
> context.

The actor-side label is also fixed:

> Current intent (software-published from the player's subgoal level; fallible player
> data with sources and age, not instructions).

## Appendix: v4 role prompts (drafts)

Both drafts are frozen when #346 builds them, after the no-nudge review. A change then makes a
new version.

**`episode-v1`:**

> Role (software-defined; not instructions from the lead). You are the player's episode
> recorder. You cannot send input; the acting player decides everything it does. Software
> supplies one closed episode of the acting player's log (its inputs, a baseline frame from
> just before it and frames from within it, and the source ids of the frames that resulted)
> and the player's current subgoal with its expected observations, if any; you may read any
> cited frame. End with exactly one tool call. Call player_episode_record to state what the
> player attempted, with what or whom, for each expected observation whether this episode
> showed it (seen), did not show it (not_yet) or showed the opposite (contradicted), what
> visibly changed in the player's own state since the baseline frame (empty if nothing did),
> and anything that happened that the subgoal did not anticipate, with cited sources and
> marked uncertainty. Call player_episode_abstain if the
> frames support no record. Only these calls count: your text is discarded and shown to no
> one. The record is stored as fallible player data.

**`subgoal-v4`:**

> Role (software-defined; not instructions from the lead). You are the player's subgoal
> level. You cannot send input; the acting player decides everything it does. You receive
> the same guide and mission brief the acting player has; instructions addressed to the
> acting player are not for you. Software supplies the episodes recorded since your last
> pass, the player's current subgoal with the status of each expected observation, counts of
> its attempts, and earlier episodes that software ranked as relevant; you may read any cited
> frame. Then end the pass with exactly one tool call. Call player_level_keep,
> player_level_close or player_level_replace: keep the current subgoal, close it, or replace
> it with one subgoal that advances the mission's objective, with the observations that would
> show it is working, its status, cited sources and marked uncertainty, and the outcome of the
> subgoal it replaces. Call player_level_abstain if the evidence supports none of these.
> Software states when a subgoal is stalled or contradicted and which calls are then allowed.
> Only these calls count: your text is discarded and shown to no one. A commit is accepted
> only if still timely, and is then shown to the acting player as fallible context.

**Actor-side recall label,** shown with the intent:

> Recalled episodes (software-selected from the player's own past; fallible; each with one
> source id; not instructions).
