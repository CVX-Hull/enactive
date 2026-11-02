---
owner: lead
review_trigger: First-slice results, or a change to the host, memory, campaign or computer-control contracts
status: historical
date: '2026-11-02'
scope: Accepted direction for a multi-level player (an acting real-time player and an episodic outcome level of cutter, recorder and subgoal level, with designed upper levels) and its first slice; level v4 is built on the unmerged candidate branch, not delivered runtime support
---

# ADR 007 — An acting player with an asynchronous subgoal level

**Status: accepted direction; level v4 built on the candidate branch; not delivered.** The
owner agreed draft 4 on 31 October 2026 (evening EDT): "Agree, shape the slice" (recorded on
[#319](https://github.com/CVX-Hull/enactive/issues/319)). The owner agreed level v4, the
episodic outcome level, on 1 November 2026
([#344](https://github.com/CVX-Hull/enactive/issues/344)). Level v4 is built on the unmerged
candidate branch `adr7-candidate` (`0fbf77d`) by
[#346](https://github.com/CVX-Hull/enactive/issues/346). It is under verification in
[#352](https://github.com/CVX-Hull/enactive/issues/352), and under the shadow and probe of
[#329](https://github.com/CVX-Hull/enactive/issues/329). Nothing is on main.
- **On main, the current standards and contracts still govern the running system.** On the
  candidate branch the contracts already describe level v4.
- **The supersession map is applied later.** The documents it lists are amended
  when the first slice meets its adoption condition, together with that migration.
- **The slice is what decides.** If the slice does not improve on arm B, the
  direction is revisited. The adoption condition is unchanged.

## History

Each amendment says what changed and why. The sections below describe the current design only.

- **Drafts 1–4, to 31 October 2026.** Draft 1 had the real-time player write its own memory,
  which conflicted with the owner's later direction and P1. Draft 2 followed the owner's
  newest-first reconciliation on #319, but an architecture review found six places where it
  did not match the code. Draft 3 fixed those. Draft 4 designed in the levels above the
  subgoal level (a strategic/aspiration level and a retrospective level, with one recursive
  pattern), after the owner asked: "What about layers above the reader layer per our
  discussions?" The first slice stayed the actor plus the subgoal level.
- **Level v2, 1 November 2026 ([#340](https://github.com/CVX-Hull/enactive/issues/340)).**
  Shadow showed 35 of 53 passes ending in a written proposal with no commit call. A pass
  therefore ends on a commit or an abstain, and its input is pushed rather than fetched. The owner
  approved ("Approve all") on
  [#329](https://github.com/CVX-Hull/enactive/issues/329#issuecomment-6561551205).
- **Level v3, flat tools, 1 November 2026 ([#341](https://github.com/CVX-Hull/enactive/issues/341)).**
  Shadow-2 refused every v2 commit: the model had to repeat a version constant inside a
  `const`-tagged union that the OpenRouter-to-Gemini route apparently did not show it, and the
  refusal never named the expected value. Flat terminal tools, portable schemas, software that
  resolves the current subgoal and stamps the version, and refusals that name the fix replaced
  the union. The owner approved ("A + B + C") on
  [#329](https://github.com/CVX-Hull/enactive/issues/329#issuecomment-6563083931). Shadow-3 and
  the persistent stage then passed.
- **Level v4, the episodic outcome level, 1 November 2026
  ([#344](https://github.com/CVX-Hull/enactive/issues/344)).** The v3 level was mechanically
  sound but read only the actor's own log, so it could only restate it. Only 1 of 106 commits
  cited anything the actor did not already hold, the median look-back was 1 frame, it closed no
  subgoal in 106 commits, and only the subgoal, not its outcomes, carried across sessions
  (evidence on #329). v4 reads recorded episode outcomes, derives closure and stall in software
  and recalls outcomes across sessions. The owner agreed: "I agree with your recommendations and
  directions". The offline ladder is [#345](https://github.com/CVX-Hull/enactive/issues/345). The
  v3 probe plan was retired and the evidence plan rescoped onto #329. The v4 design also
  introduced the [recursive memory pattern](#recursive-memory-designed) and the
  [label-evolution role](#label-evolution-designed).
- **Built, 2 November 2026 ([#346](https://github.com/CVX-Hull/enactive/issues/346)).** Custody
  ([#349](https://github.com/CVX-Hull/enactive/issues/349)), the driver
  ([#350](https://github.com/CVX-Hull/enactive/issues/350)) and the host
  ([#351](https://github.com/CVX-Hull/enactive/issues/351)) were built as separate leaves and
  integrated on the candidate branch. The owner's direction is "good design instead of
  maintaining legacy code or approaches", so v3's mechanisms were replaced outright under
  S-MIGRATION, with no compatibility paths.
- **Fold, 2 November 2026 ([#352](https://github.com/CVX-Hull/enactive/issues/352)).** v4 moved
  into the main sections, as built. Where the build settled a point #344 left open or drafted
  differently, the section says *decided at build* and names the issue.

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
| 1 | Software (host and custodian) | Feedback, accounting and budgets, on every request. Cuts the actor's log into episodes, settles each one, derives observation status, closure and stall, and commits proposals | Captures, receipts, budgets, the actor's log | Host status text; the session log; committed records | Nothing semantic |
| 2 | **Actor** (LLM, the deciding player) | Perceives and acts, every turn | Current frames, its frozen guide and mission brief, and the **published intent** with a few recalled episodes | Nothing in memory | Every input. It is the sole input sender and the sole decider |
| 3a | **Episode recorder** (LLM, its own role) | Records one closed episode at a time, asynchronously, at the scale of about six inputs | The episode's operations, a baseline frame and up to six of its own frames, and the subgoal current at the episode's first input. It gets no mission brief | **One episode record per episode**; software settles it as a claim | What the player attempted, whether each expected observation was seen, and what visibly changed. It sends no input, gates nothing, and writes nothing directly |
| 3b | **Subgoal level** (LLM, its own role) | Maintains one current subgoal toward the mission's objective, across episodes and sessions | The same frozen guide and mission brief, the **episode records** settled since its last pass, the current subgoal with its derived status, per-subgoal counts, recalled earlier episodes, and any cited frame | **Proposals only**; software commits them | Which subgoal to propose. It sends no input, gates nothing, and writes nothing directly |
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

## The episodic outcome level

The level reads outcomes, not the actor's own log. Software cuts the served actor's log into
**episodes**. An LLM **recorder** records each closed episode as a fallible claim. The
**subgoal level** reads those records, so it can see outcomes the actor's recent frames do not
carry, including those of earlier sessions. All mechanical state is computed by software, and the
LLM roles only propose.

Items marked *decided at build* were settled while building the level, in
[#349](https://github.com/CVX-Hull/enactive/issues/349) (custody),
[#350](https://github.com/CVX-Hull/enactive/issues/350) (driver) or
[#351](https://github.com/CVX-Hull/enactive/issues/351) (host). Where they differ from what #344
drafted, the as-built version governs.

**Held fixed:**
- one input writer, the actor;
- one memory writer, the custodian's own commit, closure and settle paths;
- a software-mediated commit with a staleness check S;
- forced tool calls and reserved terminal requests on both reader roles;
- the narrowed actor profile and an intent bound of 1,024 bytes;
- no level state gates input (ADR006).

### Capability and custody

- **Reader class.** Computer control has a **reader** class with two roles, `level` and
  `recorder`. A per-class tool allowlist in `Application.call` enforces it, not only `_guard`:
  - **Level:** exactly `player_source` and the four terminal tools `player_level_keep`,
    `player_level_replace`, `player_level_close` and `player_level_abstain`. It has no observe
    (which captures frames and spends budget), no input, no stop, no memory or program tool, no
    result tool and no log tool: the pushed input carries what it needs.
  - **Recorder:** exactly `player_source`, `player_episode_record` and `player_episode_abstain`.
  - **Actor:** refused all six terminal tools.
- **Storage.** A reader has an `actors` row with the `reader` stage and a `reader_role` column
  (`level` or `recorder`), because issued sources reference actors. A unique index allows one
  reader per (served actor, role). Readers are excluded from `add_actor`'s "every prior actor
  quiescent" test and from the `max_actors` count, so a live reader never blocks a successor
  actor. This is `computer-session/3`.
- **Write authorization** admits a recorder only for `player_episode_record` and
  `player_episode_abstain`. Both settle the episode.
- **The model never supplies** a record id, a contract version or a log position.

### Episode cutter

The cutter is software in the playing system, the campaign driver
(`tools/episode_cutter.py`), never `harness/computer`. It reads the served actor's log and its
result captures as player-visible sources.
- **Distance.** Each capture becomes a 32 × 20 greyscale box-pooled thumbnail. The distance d of
  an input is the mean absolute pixel difference, divided by 255, between that input's result
  capture and the result capture of the previous input that has one. An input with no result
  capture (pending or lost) has no distance and cannot close an episode.
  *Decided at build ([#350](https://github.com/CVX-Hull/enactive/issues/350)).* This is a recorded
  deviation from #345's ladder, where an input after a capture-less one had no distance, so θ was
  fitted under slightly different semantics. #352's replay probe reports how often the two differ.
- **Closure.**
  - **On content:** an episode closes before input *i* when d(*i*) ≥ θ and the episode holds at
    least *m* inputs. The input that crosses θ is the first input of the next episode, so an
    episode ends on the last stable screen.
  - **At the cap:** an episode closes when it holds C = K inputs.
  - **Mechanically at session edges:** an episode also closes at a handoff, a stop or the
    session's end, so the last partial episode is still recorded.
- **A tail with no inputs** (only observes, or the handoff itself) **is not an episode.** It is
  never recorded, so it cannot add a settle to the stall count.
  *Decided at build ([#350](https://github.com/CVX-Hull/enactive/issues/350)).*
- **Positions.** An episode is a range of the served actor's operations, `first_position` to
  `last_position`, 1-based, per actor and **inclusive**.
  *Decided at build ([#349](https://github.com/CVX-Hull/enactive/issues/349)).*
- **Order.** The cutter takes the log in order, and the next episode starts after the furthest
  cut, never after the newest settle, because episodes settle out of order (a drop can precede an
  earlier in-flight record).
  *Decided at build ([#350](https://github.com/CVX-Hull/enactive/issues/350)).*
- **The subgoal.** The driver records the level subgoal current at each episode's first input,
  when the episode opens, because no custodian API gives it later.
  *Decided at build ([#350](https://github.com/CVX-Hull/enactive/issues/350), with a #349 review fix).*
- **Frozen boundaries.** Boundaries are frozen once written and never recomputed.
- **No game semantics.** Every trigger is mechanical, and ADR006 and the no-game-semantics rule
  hold. θ is fitted per game by one game-independent procedure from player-visible captures
  (P-GENERALITY).

### Episode recorder

A second reader per actor, with its own role: one LLM pass per closed episode. Each pass is a
finite host with `role: recorder`.
- **Pushed input,** made by the driver under `Application.serial` as one `player-pass-input/1`
  document:
  - the episode's operations, as key tokens and positions;
  - a **baseline frame**: the result capture of the last *input* before the episode (not an
    observe);
  - the episode's own frames: always its last, and then those with the largest thumbnail
    distance from their predecessor, in capture order, up to 6;
  - each frame named by its source id and role (`baseline`, `in-episode` or `last`), so at most
    7 frames in all;
  - the id, text and ordered expected observations of the subgoal current at the episode's first
    input.

  #345's post-hoc check chose this frame policy. With first and last frames only, a change at an
  episode boundary was invisible. *Decided at build:* the baseline is the last input's result
  ([#349](https://github.com/CVX-Hull/enactive/issues/349), review fix).
- **No mission brief and no player guide.** The recorder sees one episode and the subgoal, and
  leaving the brief and the guide out keeps it an observer. Its host context is empty; the
  player tools' server instructions, which address the acting player, still reach it, and its
  prompt says such instructions are not for it.
  *Decided at build ([#350](https://github.com/CVX-Hull/enactive/issues/350); the guide by the
  no-nudge review on [#352](https://github.com/CVX-Hull/enactive/issues/352)).*
- **Reader profile:** `player_source`, `player_episode_record` and `player_episode_abstain`.
- **`player_episode_record(attempted, counterpart, observation_status, changed, residual,
  confidence, sources)`:**
  - `changed` says what visibly changed in the player's own state between the baseline frame and
    the last frame, citing the frames that show it. It is an empty string when nothing changed.
  - **Known limitation:** a change hidden behind an occluding screen at both ends of the episode
    stays invisible. Carrying recorded state forward between episodes was tried post hoc in #345;
    it did not recover such a change and added false positives, so it is not adopted.
  - `observation_status` is an array of `seen`, `not_yet` or `contradicted`. Its length must
    equal the pushed subgoal's number of expected observations, or it is empty when there is no
    subgoal.
  - `counterpart` and `residual` may be empty strings.
  - `confidence` is a number from 0 to 1.
  - **`sources` holds 1 to 4 ids from the episode, the most telling first.** A recall line shows
    the first one, so a record that cites no frame is refused and the "(no frame cited)" case does
    not exist. *Decided at build ([#349](https://github.com/CVX-Hull/enactive/issues/349) and
    [#351](https://github.com/CVX-Hull/enactive/issues/351), `c7ada0c`).* An episode whose inputs
    all lost their captures has no frames, so the recorder can only abstain.
  - Every field is required, and the schema is flat.
- **`player_episode_abstain(reason_code, reason, sources)`** has its own codes:
  `unreadable_frames`, `no_player_action` and `other`. `sources` may be empty.
- **Host rules** (the [player-host contract](../contracts/player-host.md#roles-and-the-intent-tail)
  owns them). *Decided at build ([#351](https://github.com/CVX-Hull/enactive/issues/351), with
  [#350](https://github.com/CVX-Hull/enactive/issues/350)):*
  - **The pushed frames are pinned for the whole pass.** They count toward `max_context_images`,
    and image eviction never omits them, so a later `player_source` read evicts an older read,
    never the baseline that `changed` depends on.
  - **The frames must be fewer than `max_context_images`,** so one read still fits. A document
    that leaves no room for a read is refused as `invalid-pass-input` before `host-start`. The
    recorder route therefore needs `max_context_images` of at least 8 (7 frames plus one read). The package
    validator checks the floor on the actor route, which the reader routes inherit, so a level
    arm constrains the actor route and a no-level arm does not.
  - **An over-peak `player_source` read is refused as fixable,** as `tool-refused` with reason
    `episode-image-peak`. The refusal names how many frames can be read at once. The
    `context-image-limit` stop is only a backstop, and it settles the episode as `failed`.
  - **Extra events and settle reasons** beyond `episode-pass`, `episode-record` and
    `episode-abstain` (for example `episode-frame`, `episode-uncertain`,
    `episode-final-refusal` and `frame-read-failed`) mirror the level's handling of lost
    transport and refusals. The host contract lists them.

### Storage: every episode settles

The custodian appends exactly one `claim` per closed episode, with:
- `data.level == "episode"` and `data.level_contract == "player-episode/1"`;
- the episode's session, actor and position range, and the pushed subgoal's id;
- `data.settled`, with one of four values:
  - `recorded`: the recorder's fields and marks;
  - `abstained`: the code and reason, with no marks;
  - `failed`: no marks;
  - `dropped`: no marks;
- `data.writer`, which is `recorder` for a recorder call and `software` for a settle the driver
  reports (a failed or dropped episode) through a custodian method under `Application.serial`.

The store copies only cited frames: at most 4 per episode. `player-record/1` and
`player-memory/1` are unchanged.
- **At store capacity** (256 MiB, no eviction):
  - a failure to remember stops the recorder and the level for the rest of the session;
  - **the actor continues,** because no level state gates input;
  - **the lineage ends** as a recorded failure, and **no successor actor is minted**
    *(decided at build, [#350](https://github.com/CVX-Hull/enactive/issues/350))*;
  - nothing is evicted silently.
- **Recall integrity.** Recall and counts trust only claims whose `level_contract` is
  `player-episode/1` and whose `data.writer` the custodian stamped. Because the stamp is in the
  record itself, the check also works on earlier sessions' claims.
  - **Enforced, not assumed.** The general memory-append paths (`player_memory_append`,
    `Memory.append` and `append_many`) refuse any record that sets the custodian's reserved data:
    `data.level` (any value), `data.level_contract`, `data.writer`, or `data.by == "software"`.
    Only the custodian's commit, closure and settle paths write them. A flat actor that writes
    memory cannot forge an episode, a settle, a subgoal or a software closure.
    *Decided at build ([#349](https://github.com/CVX-Hull/enactive/issues/349), review fix).*
- **Backlog.** Closed episodes wait in a FIFO queue. At most one recorder pass is in flight.
  - **Drops:** if more than 3 episodes are waiting, the oldest waiting episode settles as
    `dropped`. The bound is pinned at 3 and any other value is refused.
    *Decided at build ([#350](https://github.com/CVX-Hull/enactive/issues/350)).*
  - **Settling:** every closed episode ends with exactly one settle claim, whether recorded,
    abstained, failed or dropped. A pass that ends without settling its episode leaves the driver
    to settle it `failed`. A pass the host settles not-ok after its record or abstain event
    already left a settle in the store counts as committed and is never settled twice.

### Derived state: closure and stall

Observation status and stall are **derived at read time** from the store by the custodian and
are never stored on the Work record, which stays append-only.
- **What counts.** For the current subgoal *g*, the custodian reads its trusted episode claims:
  those committed after *g* whose pushed subgoal id is *g*.
  - **Marks** count only from `recorded` claims with confidence at least the floor *c*.
  - **Stall** counts every settled claim, so all of it is derivable from the store, across
    sessions too.
  - **Other subgoals.** A claim whose subgoal id is not *g* is ignored, so marks are never
    attributed to the wrong subgoal.
- **Status.** An observation is `seen` if its latest counted `seen` or `contradicted` mark is
  `seen`. It is `contradicted` if that mark is `contradicted`. Otherwise it is `not_yet`.
- **Closure.**
  - **When:** the episode record that makes every expected observation `seen`.
  - **What is written:** the custodian appends the closing correction in the same
    `append_many` transaction as that record, with the recorder reader as record actor. The
    correction carries outcome `achieved`, `data.level == "subgoal"`,
    `data.level_contract == "player-level/4"` and `data.by == "software"`. Its `supports` are the
    counted claims' ids, and its sources are capped at 16.
  - **Not vacuous:** `player-level/4` requires at least one expected observation on replace, so
    closure is never vacuous.
- **Stall.**
  - **When it fires:** *g* is **stalled** after N consecutive settle claims since *g* with
    nothing newly seen. An `abstained`, `failed` or `dropped` settle counts as nothing newly
    seen, and so does a `recorded` one below the floor.
  - **N and c** are given at reader minting, like S.
  - **Refusals:** while *g* is stalled, `player_level_keep` and `player_level_abstain` are
    fixable tool errors that name `player_level_replace` and `player_level_close`. This applies
    to start passes too.
- **Contradiction.** While any observation of *g* is `contradicted`, a keep must cite, in its
  `sources`, a frame of **any** counted claim with that mark, not only the latest. Otherwise it is
  a fixable tool error. *Decided at build ([#349](https://github.com/CVX-Hull/enactive/issues/349), review fix).*
- **Races.** The driver binds the current subgoal id at push (see
  [Binding and commit](#binding-and-commit)). The custodian refuses a commit as stale (a discard)
  if the current subgoal then differs from the bound one, because a closure or a replace
  happened meanwhile.
- **Contracts.** `player-level/4` and `player-level-commit/4` carry the pushed subgoal id, the
  derived status and the closure. Minting a reader refuses a store whose current level Work is
  not `/4`: migrate, or start a fresh store. The rules are in the
  [computer-control contract](../contracts/computer-control.md)'s level section.

### The subgoal level pass

- **Pushed input:** closed episodes and software counts, never the actor's raw log:
  - the episode records settled since its last pass, whatever their outcome;
  - the current subgoal with its derived status, its stalled flag and its id;
  - counts per subgoal: episodes, seen, contradicted, closures and failures;
  - recalled episodes (the top 10, see [Recall and the intent tail](#recall-and-the-intent-tail)).

  The driver pushes it under `Application.serial`, with the frozen role prompt and the mission
  brief. The level may read any cited frame with `player_source`. A failure of the push, or of
  either reader role, is recorded and never reaches the actor.
- **Forced tool calls.** The level host sends `tool_choice: required` on every request, so the
  model cannot end in prose. The level's text is discarded and shown to no one; only the four
  terminal calls below count.
- **Reserved terminal requests.** Requests count as logical requests (one per inference request,
  however many HTTP attempts its retries use). On every logical request with two or fewer
  remaining, including that request, the host declares only the reader's terminal tools (the four
  level tools, or the recorder's two). It restricts the request's tool declarations; the history
  and the executable tool set are unchanged. This reserves a repair slot for a refused call. A
  terminal call refused on the last allowed request settles as `level-final-refusal` (the
  recorder's `episode-final-refusal`), a counted outcome distinct from `request-limit`. A
  non-terminal call on a reserved request is refused without dispatch.
- **Lost transport.** A reader terminal tool has no collecting tool, so a `player-transport/1`
  unknown receipt on it ends the pass (`level-uncertain`, or `episode-uncertain`). The driver
  reads the store afterwards and counts the outcome: for the level the `service_operations` row
  for the identity (`committed` or `absent`; a discard writes no row), for the recorder the
  episode's settle claim.
- **What ends a pass.** The pass ends after a `player_level_keep`, `player_level_replace` or
  `player_level_close` that software commits or discards, or after a valid
  `player_level_abstain`. A call rejected as a fixable tool error does not end it, and the model
  may correct it. A pass that ends any other way (for example a text-only terminal response) is a
  failed pass with the reason `level-no-proposal`, recorded and counted.
- **The tools.** The level manages only its own subgoal: the current Work records with
  `data.level == "subgoal"`, at most one by construction. Other Work is out of its scope and
  untouched. Each tool is one flat object, every property required:
  - **`player_level_keep(reason, sources)`:** writes no record; the receipt says kept and gives
    the current id;
  - **`player_level_replace(text, expected_observations, status, confidence, sources,
    previous_outcome, previous_reason)`:** writes the new Work record. `expected_observations`
    holds 1 to 8 entries. `status` is `open` or `blocked`. `previous_outcome` is `none`,
    `achieved`, `failed`, `abandoned` or `revised`, and is `none` exactly when there is no current
    subgoal; otherwise it also writes a superseding correction (a `revised` one supports the new
    Work). Its `sources` are the replace's sources;
  - **`player_level_close(outcome, reason, sources)`:** `outcome` is `achieved`, `failed` or
    `abandoned`; it needs a current subgoal and writes the correction only.

  Software resolves the current subgoal, so the model supplies no record id and no version, and
  stamps the contract version into the stored record data and the `player-level-commit/4`
  receipt. A wrong-state call (keep or close with nothing current, a `none` previous outcome over
  a current subgoal or another one with none) is a fixable tool error that names the current
  subgoal state and the valid tool for it and keeps the bound. A keep alongside a new subgoal
  cannot be expressed.
- **Portable schemas.** The model-facing schemas use `type` on every node, string enums, all
  inlined, and plain objects; no `const`, `oneOf`, `anyOf`, `$ref`, `uniqueItems` or nested
  objects beyond arrays of strings. The research behind this
  ([LLM tool interface design](https://github.com/CVX-Hull/enactive/issues/329#issuecomment-6563083931))
  found that the schema a Gemini route shows may not be the one the host validates, so host
  validation is the only enforcement and nothing may depend on the model seeing a constant.
  Refusals come from the host: each failing field's path, rule, allowed values or limits, the
  received value truncated to 120 characters and a minimal valid example call, then the line "Fix
  the call and resend it; abstaining is not the remedy for a fixable call."
- **Abstain.** `player_level_abstain(reason_code, reason, sources)` ends the pass without a change
  when the evidence supports none of keeping, replacing or closing. `reason_code` is
  `insufficient_evidence`, `transient_screen_state`, `no_change_needed` or `other`; `sources` may
  be empty. Nothing is written, the reader's bound is cleared as a terminal call clears it, and
  the host trace records a `level-abstain` event carrying the code (`player-level-abstain/2`).
  Abstentions are counted by code. A stalled subgoal refuses it.

### Binding and commit

The commit is software-mediated (P5). The level calls `player_level_keep`,
`player_level_replace` or `player_level_close`, and software decides.
- **The driver binds the pass** under `Application.serial` at push. The model never supplies the
  binding.
  - **The position** is the **furthest** settled position: the highest `last_position` over the
    served actor's settled episodes in the current session, whatever their outcome (record,
    abstain, failure or drop). So a pass woken by a settle with no record still binds where it
    should, and the bound never goes back when a later episode is dropped before an earlier one is
    recorded. *Decided at build ([#349](https://github.com/CVX-Hull/enactive/issues/349), review
    fix B1: commit order made the bound go backwards and caused spurious S discards).*
  - **Recalled earlier-session records** never bind.
  - **At actor start,** before any episode has settled, the bound is 0.
  - **The current subgoal id** is bound with it.
- **Commit conditions.** The custodian first checks that the current subgoal still has the bound
  id. It commits only if a position is bound, the run is not stopped, fenced or past its
  deadline, the served actor is still active, and the actor has moved fewer than S `input`
  operations past the bound. A reader's store is one live session, so no session boundary can
  intervene.
- **Atomicity.** The commit runs under `Application.serial`, so no input or handoff can
  interleave. The Work record and any superseding correction are appended in one transaction, with
  the exact bytes of the cited sources (a multi-record `Memory` append).
- **Discards.** A proposal that fails a check is discarded and logged in the level's host trace,
  never in the store. A discard ends the pass, as a commit does.
- **Coupling.** S must exceed the p95, in actor inputs, of a recorder pass plus queue wait plus a
  level pass. #345 measured a p95 of 5 actor inputs against S = 10 on recorded latencies.

### Waking and revalidation

- **Waking:**
  - at actor start, **only when something is carried over:** an open subgoal, or an
    earlier-session `recorded` claim (an abstained, failed or dropped one does not count)
    *(decided at build, [#350](https://github.com/CVX-Hull/enactive/issues/350))*;
  - after every episode settles: record, abstain, failure or drop;
  - at the 25, 50 and 75% budget fractions, but only when something has settled since the last
    pass. That keeps the empty-delta rule of the
    [player-interface standard](../standards/player-interface.md).
- **In flight:** at most one level pass. Wakes that arrive during a pass coalesce into one pass
  over the newest records.
- **Revalidation.** At actor start the first pass is given the open subgoal and may keep, replace
  or close it, or abstain. An abstaining start pass leaves the earlier subgoal current, and its age
  in sessions still shows in the actor's intent tail, so revalidation is offered, not enforced,
  except for a stalled subgoal. Start-pass abstentions are counted separately.

### Recall and the intent tail

- **Candidates:** the trusted `recorded` episode claims from earlier sessions and from this
  session.
- **Score:** BM25 relevance over the record's text fields (`attempted`, `counterpart`,
  `residual` and `changed`), with the current subgoal's text and expected observations as the
  query (k1 = 1.2, b = 0.75). The score is multiplied by reliability, which is the recorder's
  confidence, and by 1.5 when the record has a residual. There is no demotion.
- **No current subgoal:** recall shows the most recent records instead.
- **The level sees** the top 10.
- **Cached.** Recall caches each episode's token counts and the ranking, because recomputing them
  under the serial lock took about 1 s at 5,000 episodes.
  *Decided at build ([#349](https://github.com/CVX-Hull/enactive/issues/349), review fix).*
- **Publication.** The actor's request-only tail shows the latest committed Work record, labelled
  fallible, with its sources and its age in inputs, seconds and sessions, and recalled episodes.
  The actor may ignore it.
- **The tail.** `player-intent/2` has a fixed allocation of 1,024 bytes in all, labels included.
  *Decided at build ([#351](https://github.com/CVX-Hull/enactive/issues/351)):* `intent_tail_bytes`
  is null or exactly 1024, because the allocation is fixed.

  | Part | Budget |
  |---|---|
  | The intent label | 129, as written |
  | `Subgoal: <text>` | ≤ 160 bytes |
  | `Expected: [status] <observation>; ...` | ≤ 200 bytes |
  | `id <8 characters>; conf <c>; <n> inputs, <s>s, <this\|prev>` | ≤ 50 bytes |
  | The recall label | 118, as written |
  | Up to 3 recall lines | ≤ 120 bytes each |

  The seven line breaks between the eight lines at the maxima make the sum exactly 1,024.
  - **Recall lines** are the top 2 by score plus 1 exploration line. The exploration line is an
    earlier-session record outside the top 10, drawn uniformly with a seed fixed per pass from the
    session id and pass index.
  - **What a line shows:** the full source id of the record's first cited frame, which the actor
    can read with `player_source`, then its outcome (`seen x/y`, with the count contradicted) and
    its attempt text, truncated to the rest of the line. For an episode with no subgoal the outcome
    is an excerpt of `changed`.
  - **Metadata order:** `id; conf; age; this|prev`. The software's fields come first, so a cut
    falls on the age, not on the id.
  - **Expected observations:** each observation gets a fair share of the `Expected:` line, with
    its status first, so every status stays visible. Observation text cannot spoof a status.
  - **Recall items without a showable id** are skipped, never shown without one, and counted.
  - **Markers:** each part's omission marker comes out of that part's own budget, so a truncated
    tail still fits the bound. Recall is therefore never cut first. Omitted bytes are logged per
    part.
  - **Fewer earlier records, fewer lines.** #345's check found every render within the bound and
    all three lines present in every render from session 2 on; the shortfall came only from renders
    with fewer than three candidates. The owner agreed on 2 November 2026 that the tail shows
    fewer lines then, and the allocation stands.

  The host formats the tail from `player-intent/2`; the
  [player-host contract](../contracts/player-host.md#roles-and-the-intent-tail) owns its exact
  rules.

### Prompts and model

- **The prompts** are frozen, versioned and game-agnostic
  ([appendix](#appendix-v4-role-prompts)), and reviewed against the no-nudge rule. The level steers
  toward the mission's objective using the same frozen guide and brief the actor has, so it adds
  no lead content. Software triggers stay mechanical; the level's semantic judgement belongs to the
  player system (ADR006).
- **Model.** The same model and pinned route for all roles. The slice uses Gemini 3.8 Flash,
  #314's and #320's reference route, for comparability. The deployed selection is DeepSeek
  Flash1017; switching routes is a separate decision. Each role has its own counted allowance.

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
| Input projection | Settled episode records and software counts, with recalled earlier episodes | Committed Work outcomes since its last pass, plus software statistics | The player store's records and sources, read at session start |
| Proposal | One current subgoal: keep, replace or close it | Active aspirations, with their grounded progress variable and status | Claims with evidence, corrections, candidate programs |
| Software commit | Staleness in actor inputs (S), at a position the driver binds at push; no handoff since | Staleness in Work records committed since the level's own read, bound by the custodian; no session boundary since | Schema, sources and supersession checks; nothing committed as authority |
| Published to | The actor's intent tail | The subgoal level's input (the objective it serves) | The subgoal level's input: candidate programs and claims it may cite. Committed claims are a store the levels read, not a publication |
| Wakes | Actor start (when something is carried over), each episode settle, budget fractions after a settle | A subgoal closes or fails, or a session starts | Session start, or a record-count threshold |

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
  version (`player-level/4`) and writes them into `data`.
- **Episode records** are `claim` records with `data.level == "episode"`
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

- **Requests per episode.** Per mean episode of L̄ inputs, the recorder runs one pass of 1–2
  provider requests and the level one pass of 2–3. With the pushed input and a forced ending
  call, a level pass is a terminal call plus, optionally, a read of a cited frame. At L̄ = 6 that
  is about 0.5–0.8 level-side requests per actor input, roughly 2–3 times what the earlier
  log-delta level cost. The shadow measures it against the cadence, and the probe's adoption
  condition weighs it.
- **Latency.** At #298's response median of about 12 s, a level pass of 2–3 requests takes about
  24–36 s. The p95 is about 25 s per request.
- **How far the actor moves meanwhile.** The actor makes about one input per request, so it
  advances about 2–3 inputs during a median level pass and about 4–6 during a p95 pass.
- **Coupling (P12).** S must exceed the p95, in actor inputs, of a recorder pass plus queue wait
  plus a level pass. #345 measured a p95 of 5 against S = 10. "At most one pass in flight" per
  role prevents overlap. K, S, L̄ and pass latency are set together, and are checked in the shadow
  stage.
- **Accounting.** Each actor has one level host and one recorder host at a time. Each
  actor, level and recorder gets partitioned allowances before launch, and the sum stays within
  the campaign cap. A level host starts after its actor is ready, and stops on that actor's stop,
  Pause or handoff. The recorder then works through its backlog, bounded in time, unless the run is
  fenced. The successor actor gets a new level host and recorder, and its first level pass
  revalidates what was carried over and sees the committed intent.
- **Actor waits.** The actor's critical path adds only the bounded intent tail.
  Because MCP calls are serialized (`Application.serial`), the level can delay the
  actor's tool calls, so the actor's lock wait is measured. The cadence target
  ([#164](https://github.com/CVX-Hull/enactive/issues/164)) applies to the actor.

## Calibrations and parameters

Each row names its source. The procedures are game-independent; the values below were fitted or set
on development data.

| Name | Value | Kind and procedure | Source |
|---|---|---|---|
| Episode threshold θ | 0.1251514705882353 | Calibration, fitted per game from player-visible captures: the q = 0.86 quantile of consecutive thumbnail distances, chosen so the mean episode length hits the target (fitted mean 5.94 over 444 episodes of 37 runs, all development data). Frozen in the profile by value and by the fitting digest `8a80f12b736b6d993fcf6c356a7686a03c85508779d52c376d2ce1394893c76b` (`calibration.json`). Recalibrated when the game, resolution or theme changes | [#345](https://github.com/CVX-Hull/enactive/issues/345) |
| Target mean episode length L̄ | 6 | Preference, half the cap. With *m*, it sets the cadence K set before; θ is fitted to it | Owner, #344; used as the fitting target in #345's registry |
| Minimum episode length *m* | 2 | Preference; a content cut needs this many inputs | #345's registry |
| Episode cap C and K | 10 | K is the owner's longest run of inputs between wakes and is now the cap. `episode_cap` must equal K (10); the package validator enforces it, and changing K is the owner's call | Owner; *decided at build* ([#350](https://github.com/CVX-Hull/enactive/issues/350)) |
| Staleness S | 10 | Owner preference, constrained by S > p95 of recorder pass plus queue plus level pass. Measured p95: 5 actor inputs | Owner; #345 |
| Budget fractions | 25%, 50%, 75% | Owner preferences. A fraction wakes the level only after a settle | Owner |
| Stall test N | 3 | Calibration. N = 3 is the registered default, checked by closure replay of 21 recorded v3 subgoals: N = 3 closes 3 and stalls 8, and N = 2, 4 and 5 stall 9, 6 and 4 | #345 |
| Confidence floor *c* | 0.0 | Preference set from cross-family agreement by confidence: κ is 0.673 at a floor of 0 (R1 Gemini 3.8 Flash against R2 Haiku 5.5, n = 431; the lower bound of its interval, 0.56, is below 0.6, so this is a pass on the point estimate) and 0.714 at 0.5 | #345 |
| Recorder backlog | 3 | Preference, pinned and enforced. Drops are counted | #344; *decided at build* (#350) |
| Recorder frames | ≤ 7: a baseline plus ≤ 6 own | Fixed by the frame policy; the host pins them, and the route needs `max_context_images` ≥ 8 | #345 post-hoc check; #350, #351 |
| Recall sizes | 2 top lines plus 1 exploration line in the tail; 10 for the level; residual weight 1.5 | Preferences within the fixed bound. The follow rate is measured | #344; #345 survival check |
| Intent byte bound | 1,024 bytes, the tail allocation as in the table above | Owner's preference, traded against cost. Surfaced and omitted bytes are logged per part | #344; #351 |
| BM25 parameters | k1 = 1.2, b = 0.75 | Fixed standard values, not fitted | #344 |
| Role prompt versions | `episode-v1`, `subgoal-v4` | Frozen artifacts, with digests in the [appendix](#appendix-v4-role-prompts). Reviewed against the no-nudge rule. A change makes a new version | #346 |

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
| One actor at a time, with no concurrent non-input host; the active actor writes memory | [Campaign run](../operations/campaign-run.md) and the driver; [mission ownership](../operations/mission-ownership.md) lines 11–18; the [computer-control contract](../contracts/computer-control.md) custody and write authority | R2, R3. Concurrent reader hosts (a level and a recorder per actor) are added. The actor stays the only input writer, and the software commit path becomes the only memory writer |
| Draft 1 of this ADR | This file's history | R1 |

**Consistent, not superseded:**
- the charter's "one designated deciding player" (the actor remains sole decider)
  and its "separately assigned advisory actor for reflection", this design's
  ancestor;
- the historical [asynchronous-reflection design](../design/asynchronous-reflection.md),
  which was archived at the cutover, not rejected on its merits. Its one-writer rule
  is kept.

## First slice and evidence plan

Shaped in [#326](https://github.com/CVX-Hull/enactive/issues/326); the evidence runs on
[#329](https://github.com/CVX-Hull/enactive/issues/329).

- **Question.** Does a separate subgoal level improve retained progress and mission
  commitment, compared with the flat player and with arm B (the flat player told to
  keep a ledger)?
- **Stages:**
  1. the offline ladder on recorded runs (#345), which ran and passed its gates;
  2. a v4 shadow. The level runs and commits, but intent is not shown to the actor. This
     measures intent accuracy without any influence on play;
  3. a pre-registered probe in **persistent lineages**, several sessions carried forward per
     lineage, because outcome recall can only matter across sessions.
- **Probe arms, all required, from one candidate build.** A zero-level-host profile value is
  configuration, not a compatibility path. Each arm's tool profile is stated:
  - **flat:** today's profile, with the memory tools and handoff summary;
  - **arm B:** today's profile plus the frozen ledger addendum; its ledger needs memory append;
  - **the narrowed actor with v4:** the narrowed actor profile, a level host and a recorder host;
  - optionally, **v4 with recall limited to the current session,** which isolates the
    cross-session part.

  The v4 arm changes two things at once, removing the actor's memory tools and adding the level.
  The flat arm's #314 history (zero memory calls) suggests the removal costs little, but a fourth
  arm (narrowed actor, no level) would separate the two effects. It is decided with the owner at
  pre-registration.
- **Starts:**
  - #314's save;
  - a second start made once through the game's ordinary new-game flow with
    default options, by a recorded designated operator, then frozen and restored by
    hash per arm. No save is edited.
- **Metrics, pre-registered (S-EVIDENCE):**
  - **Primary: retained change per session.** This is #314's M1, "the first retained change in
    inventory, carried weight, worn or wielded items, a consumed item or a status indicator,
    confirmed in a later frame". It is tightened beforehand to substantive changes caused by the
    player: no first evidence only in the message log, and no status change driven by passing
    time. It is scored by blind auditors from two model families, with their agreement reported.
  - **Adoption contrast:** v4 against arm B on the primary metric pooled over sessions, in the
    pre-registered direction. The arm × session-index slope is the pre-specified learning test.
  - **Power:** a power simulation for both, set before spend under S-EVIDENCE, with power of at
    least 0.8 for a stated effect. #314's metric was censored in every run, so run length is sized
    to it. An underpowered null is reported as underpowered.
  - **Mechanism:** passes, commits, discards, abstentions (with their reasons) and failed passes;
    intent age; subgoals opened, revised and closed.
  - **Intent accuracy:** a blind audit of committed intent against the log, plus the actor's
    follow rate when the intent is wrong. This covers the More Memory, Worse Agents risk.
  - **Secondary:**
    - semantic revisits, meaning time spent at counterparts or places already visited with no new
      outcome. They are labelled by an LLM and cross-checked across families;
    - the longest replayed stretch within a run. This is lens test T3′'s only statistic that
      passed its planted-replay power check (#329);
    - actor latency and lock wait against the cadence, and cost by role.
  - **Audit of software's inputs.** A blind cross-family LLM audit checks the recorder's marks and
    the precision of software closures and stalls, because software acts on those LLM marks.
  - **Manipulation check:** the intent tail must carry information the actor did not already
    hold. The measure is lens test T1's marginal coverage: the share of tail items whose sources
    the actor had not received. It must be above zero, or the run is void as a test of v4.
  - **No human labels** (owner, 1 November 2026).
- **Adoption condition.** Adopt only if the level improves on arm B in the
  pre-registered direction, within the cadence and an accepted cost. An
  underpowered null leaves the status quo, reported as underpowered.

## Boundary impact

- **Highest changed boundary:** the computer-control custody contract, which gains
  a reader capability class with two roles. The player-host and campaign contracts change too.
- **Placement** (the lead's decision; the owner may override). The level and the recorder run as
  separate concurrent hosts, rather than second and third agents in one host process, which
  would merge budgets and failure modes. The cutter, the backlog and the wakes live in the
  campaign driver.
- **Current contracts, each versioned under S-MIGRATION:**

  | Contract | What it covers |
  |---|---|
  | `computer-session/3` | The reader class, its two roles and the per-class tool allowlist; the `reader` stage and `reader_role` column; one reader per (served actor, role); the recorder's write authorization; the custodian method for driver-reported settles; the binding, closure, stall, contradiction and stale-subgoal rules; the reserved-data refusals (`harness/computer/store.py`, `runtime.py`, `harness/application.py`, [contract](../contracts/computer-control.md)) |
  | `player-level/4`, `player-level-commit/4` | The level's Work and correction data, with at least one expected observation on replace and software closure (`data.by == "software"`); the commit receipt with the pushed subgoal id and the derived state. Stores that are not `/4` are refused. `player-level-abstain/2` is unchanged |
  | `player-episode/1` | The episode claim's data. The receipts are `player-episode-record/1` and `player-episode-abstain/1` |
  | `player-intent/2` | The intent object, with the fixed 1,024-byte allocation (labels count) |
  | `player-handoff/2` | The handoff without an actor-written summary or memory snapshot |
  | `player-pass-input/1` | The recorder's closed pass-input document |
  | `player-host/6` | The roles actor, level and recorder; the `level-*` and `episode-*` events; the pinned recorder frames; the intent-tail format; `intent_tail_bytes` null or 1024; a level pass sends `tool_choice: required`, offers only the terminal tools on its last two requests and settles `level-no-proposal` or `level-final-refusal` otherwise |
  | `player-driver/6` | The episode cutter, recorder passes and their FIFO backlog; reporting failed and dropped settles to the custodian; binding at push; waking on settle; the counts (keeps, replaces, closes, discards, abstains by reason code, failed passes and final refusals). Closure and stall belong to the custodian, not the driver |
  | `campaign-run/5` | The level profile (θ and its fitting digest, C = K, *m*, N, *c*, S, the recall sizes, the recorder's allowance, partition, lifecycle and backlog) and the `episode-v1` and `subgoal-v4` prompts, frozen by digest. `episode_cap` replaces `inputs_per_pass` and must equal K |

  `player-memory/1` and `player-record/1` are unchanged: episodes are `claim` records with a level
  discriminator. The host and driver rules live in the [player-host](../contracts/player-host.md)
  contract and the [campaign-run](../operations/campaign-run.md) procedure.

  The chain, for history only: `computer-session/1` to `/2` (reader class) to `/3` (roles);
  `player-level/3` to `/4`; `player-level-commit/3` to `/4`; `player-intent/1` to `/2`;
  `player-handoff/1` to `/2`; `player-host/2` to `/3` to `/4` (#340) to `/5` (#341) to `/6`;
  `player-driver/3` to `/4` to `/5` to `/6`; `campaign-run/3` to `/4` to `/5`. `player_log_read`
  and `player-log/1` are removed, and so is the host rule that a level host includes
  `player_log_read`.
- **Callers, migrated together on the candidate branch** (by #349, #350, #351 and the lead's
  integration):
  - **Harness:** `harness/computer/runtime.py`, `store.py`, `harness/application.py`,
    `harness/player/contracts.py`, `harness/player/memory.py`, `harness/player/recall.py`,
    `harness/player_tools.py`, `harness/player_mcp`, `harness/player_client.py`.
  - **Driver and tools:** `tools/campaign_package.py`, `campaign_run.py`, `campaign_player.py`,
    `investigation_live.py`, `control_analysis.py`, `host_analysis.py`, `episode_cutter.py`,
    `level_schedule.py`, `level_offline.py`, `level_probe.py` and `tools/player_roles/`.
  - **Host:** `tools/player_host/host.mjs`, `run.mjs`, `test/*.mjs` and `README.md`.
  - **The observer.**
  - **Tests:** `tests/test_player_level.py`, `test_level_schedule.py`, `test_level_probe.py`,
    `test_episode_cutter.py`, `test_player_host_contract.py`, `test_campaign_player.py`,
    `test_host_analysis.py`, `test_observer_activity.py`, `test_campaign_run.py`,
    `test_investigation.py` and `fixtures/player_host_mcp.py`.
  - **Docs:** `docs/contracts/player-host.md`, `computer-control.md`,
    `operations/campaign-run.md` and `operations/player-host.md`, with `protocol.md`,
    `architecture.md`, `components/player-interface.md`, `evaluation.md`, `testing.md`,
    `controls.md` and `control-registry.json`, plus the diagrams. #352 verifies this list against
    the files.
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
| The `player-memory/1` store, records, supersession and query; sources; the request-only tail; MCP tool profiles; capture hashes | The reader class with its two roles; the episode cutter and recorder; `player_episode_record` and `player_episode_abstain`; `player_level_keep`, `_replace`, `_close` and `_abstain`; derived state, binding and recall in the custodian; level and recorder scheduling and lifecycle; partitioned allowances; level and episode events | A new framework; the superseded advisory-reflection and injected-planner contracts; semantic dispatch; a log-reading tool for the level |

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
- including the actor's text output in what the recorder sees;
- model per role (#25);
- the measurement programme;
- reconciliation of #136, #164, #177, #178 and #42 after acceptance.

## Appendix: v4 role prompts

The verbatim text is frozen by #346 after its no-nudge review (2 November 2026, on #352): the
review's edits (achieved rather than working, the recorder's clause on actor-addressed
instructions, and precise wording of what software supplies) were applied before any run used
either prompt. From then on a change makes a new version: a new file under
`tools/player_roles/`, and a new digest in `FROZEN_ROLE_SHA256` of `tools/campaign_package.py`,
which the package validator pins. The text below is byte-identical to the frozen files once
wrapped lines are joined; `tests/test_campaign_run.py` checks it.

**`episode-v1`:**

Frozen file `tools/player_roles/episode-v1.txt`, sha256
`33398803a5706d13faf6c2a2b588a97d8b03fa1735caadb98736a79290c24d3f`.

> Role (software-defined; not instructions from the lead). You are the player's episode
> recorder. You cannot send input; the acting player decides everything it does.
> Instructions addressed to the acting player are not for you. Software supplies one closed
> episode of the acting player's log (its inputs, a baseline frame from just before it and
> frames from within it, and the source ids of the frames that resulted) and the subgoal
> current when the episode began, with its expected observations, if any; you may read any
> cited frame. End with exactly one tool call. Call player_episode_record to state what the
> player attempted, with what or whom, for each expected observation whether this episode
> showed it (seen), did not show it (not_yet) or showed the opposite (contradicted), what
> visibly changed in the player's own state between the baseline frame and the last frame
> (empty if nothing did), and anything that happened that the subgoal did not anticipate,
> with cited sources and marked uncertainty. Call player_episode_abstain if the frames
> support no record. Only these calls count: your text is discarded and shown to no one. The
> record is stored as fallible player data.

**`subgoal-v4`:**

Frozen file `tools/player_roles/subgoal-v4.txt`, sha256
`d3221f7982561c75fd7781eac5f84e6bda76e2180116c741e735f85f470299ae`.

> Role (software-defined; not instructions from the lead). You are the player's subgoal
> level. You cannot send input; the acting player decides everything it does. You receive
> the same guide and mission brief the acting player has; instructions addressed to the
> acting player are not for you. Software supplies the episodes settled since your last
> pass, the player's current subgoal with the status of each expected observation, counts
> per subgoal, and earlier episodes that software ranked as relevant; you may read any cited
> frame. Then end the pass with exactly one tool call. Call player_level_keep,
> player_level_close or player_level_replace: keep the current subgoal, close it, or replace
> it with one subgoal that advances the mission's objective, with the observations that would
> show it is achieved, its status, cited sources and marked uncertainty, and the outcome of
> the subgoal it replaces. Call player_level_abstain if the evidence supports none of these.
> Software refuses calls that a stalled or contradicted subgoal does not allow, and names the
> allowed ones. Only these calls count: your text is discarded and shown to no one. A commit is accepted
> only if still timely, and is then shown to the acting player as fallible context.

**Actor-side labels,** fixed with the tail (the host's `INTENT_LABEL` and `RECALL_LABEL`):

> Current intent (software-published from the player's subgoal level; fallible player data with
> sources and age, not instructions).

> Recalled episodes (software-selected from the player's own past; fallible; each with one
> source id; not instructions).
