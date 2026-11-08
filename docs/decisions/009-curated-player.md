---
owner: lead
review_trigger: A phase's study result, an owner decision on an open question below, or a change to the host, memory, program or computer-control contracts
status: proposed
date: '2026-11-08'
scope: Proposed direction for an acting player with an asynchronous curator, a player-fitted ontology and programs on the actor's interface; nothing adopted, and current contracts govern the running system
---

# ADR 009 — A curated player: actor, curator, ontology and programs

**Status: proposed, 8 November 2026.** The owner set the direction below in
discussion on 8 November 2026. Nothing here is adopted or implemented. The
[computer-control contract](../contracts/computer-control.md), the
[player guide](../player-guide.md) and the current standards govern the running
system until a phase meets its adoption condition. Each phase is adopted on study
evidence, and the [rule alignment](#rule-alignment) takes effect with it, together
with the migration (S-MIGRATION).

The owner asked that real data and studies drive development. This page therefore
separates what the owner decided (the direction) from what evidence must still
decide (the methods, parameters and adoption of each phase).

## Problem

The player's memory and program library are optional tools that the playing model
must choose to maintain. In practice it does not. The figures below were derived
from the sealed stores and host traces (`397-seven-day` and `372-382-dev-loop` in the
[evidence store](../operations/evidence-cleanup.md)) and checked by the lead on
8 November 2026. They are development evidence from one diagnostic route.

- **Memory is a handoff note, not a working memory.** In the
  [#397 lineage](../acceptance/2026-11-07-seven-day-397.md) the player made 12
  memory append requests (11 committed) in 1,969 tool calls. All came from the
  first actor of each admission in the last minute before `player_handoff`. Across
  all 83 actor traces in both evidence sets, `player_memory_query` was called 7
  times.
- **Memory is pulled, apart from one actor-chosen packet, and the only search is
  kind and recency** (`harness/player/memory.py:127-137`). Within an admission the
  successor's prompt carries the handoff packet (`tools/campaign_player.py:169`):
  0–3 records the previous actor chose and a 350–1,600 character summary. Between
  admissions the prompt carries only the final report (333–1,503 bytes); 6 records
  were read in a later admission, through queries.
- **Record kinds do not separate content.** Of the 78 records in the 34 sealed
  stores, 57 (73%) are `work`, nearly all status snapshots. `decision` was never used, `claim` twice;
  `procedure` holds keybinding notes; 11 of 12 `advice` records come from the arm
  whose prompt asked for reflection; `correction` appears in one run. Code uses
  `kind` as a query filter and requires a correction to name what it supersedes
  (`harness/player/contracts.py:99`).
- **Programs are nearly unused and cannot read the screen.** One program exists in
  the current design (walk up 25 times, twice). A program sees one crop resampled to
  at most 96×96 by nearest neighbour (`harness/player/images.py:25,54`), plus the
  actor's interpretation. A whole frame at that size cannot resolve interface text;
  only a small crop arrives at native resolution. Programs have no tests, success
  predicates, usage statistics or retrieval by purpose.
- **Forgetting cost real play, and it was lost carry, not failed recall.** In #397:

| Known fact (source) | Then |
| --- | --- |
| A roof tank held 18 L of clean water (in `sd1a3`'s handoff summary only: its record append stayed pending, its handoff root ID was mistyped, and `sd1a3`'s final report omitted it) | `sd1a4` fetched dirty water from a lake and boiled it (time spent not yet measured) |
| 20 ration boxes in a cupboard (record `5db17f`, `sd1a5`) | `sd1a6`–`sd1a7` worked on 25 kcal stalks |
| A fishing rod already in the shelter (record `94ce47`, `sd1a2`) | `sd1a5`–`sd1a7` tried to craft one |
| Batteries in the locker (record `f49b80`, `sd1a1`) | `sd1a3` reported a dead flashlight and a dark basement |

The first case is a fact that never reached the store and was dropped at the
next boundary; the other three are stored records that were not found. These are
the two gaps the [ADR 007 outcome](../acceptance/2026-11-03-adr007-status-quo.md)
distinguished, and they repeated within one lineage. That meets only the
repeated-gap part of its revisit condition for #178. The outcome also required
credible audit completion, costs and at least 80% detection, and it warranted a
single read-only lookup first; a separate adviser needed "evidence of a distinct
failure the simpler access path cannot address". No episode yet shows that failure.
This proposal therefore rests on the owner's direction of 8 November, and P1 keeps
the simpler path as its [baseline arm](#phases).

The lineage's death was different: the hazard was carried (record `cb18d4`), and
the player started a new craft beside a fuelled fire. That is a judgment failure.
Whether a [monitor](#monitor) would catch such failures is a hypothesis.

## Owner direction (8 November 2026)

The owner's words are recorded verbatim on
[#387](https://github.com/CVX-Hull/enactive/issues/387#issuecomment-6724463819).

| | Owner's words | What it settles |
| --- | --- | --- |
| D1 | "the actor that's actually playing be separate from the memory and/or program curator … the actor should just need to use memory or maybe hint at the memory or program curator" | Two roles. The actor plays, reads memory and hints; it does not maintain the banks |
| D2 | "it has to run alongside in a way that doesn't add latency. The actor has to continuously act and would have access to things that curator makes at best effort" | The curator runs concurrently and never blocks the actor |
| D3 | "a player (the overall system) proposed and maintained ontology … the harness to remind about the existence of existing types … users of the memory will need to have sufficient context to understand what the ontology is" | Types are proposed by the player system, checked against existing types, and explained to every reader |
| D4 | "ontology should start with the game neutral … think about how we can 'evaluate' or 'fit' an ontology" | A fixed game-neutral core; domain types are fitted and evaluated |
| D5 | "either make the type fruitful or not have them" | Types must earn their place or go. Replacing the six kinds with a fitted ontology is the lead's proposal under D3–D4 |
| D6 | "think about 'backtesting' or toolset to enable curating and testing and managing the ontology, the memory, and programs … tools that can help it 'fit' the program" | A curator workbench |
| D7 | "Programs should be like drop in replacement for the actor agent. If a game is really simple maybe the actor can just call the program and be done" | Programs implement the actor's interface |
| D8 | "Model calls inside programs are acceptable … swapping out slow LLM calls with maybe other models that might be fast or can serve a specific purpose" | Programs may call models through swappable slots |
| D9 | "having the actor over the loop for the program without adding latency" | Supervised asynchronous program runs |
| D10 | "the intent should be visible … any other information that the actor can emit"; "Emitting expectations should be required from the start" | Required intent and expectation emissions |
| D11 | "Monitor should be part of the first program phase" | A monitor slot ships with programs |
| D12 | "Charter and other rules have to align with this latest directions. But, we should also use real data and study to drive the development" | Rules are amended with each adopted phase; studies decide adoption |
| D13 | "Ensure that we don't overfit to CDDA, and also don't rely on your prior knowledge for the game" | Game-neutral mechanisms; no domain type, program or check is seeded from recalled game knowledge ([S-EVIDENCE](../standards/evidence.md)) |

The disagreement method (a candidate is [below](#belief-and-disagreement)) and the
practice instance are proposals, not owner decisions.

## Relation to ADR 007

[ADR 007](007-player-subgoal-level.md) proposed an acting player plus an
asynchronous subgoal level and was not adopted on 3 November 2026. This proposal
keeps its constraints that still hold: one input sender, no level state gating basic
control, the charter's responsiveness rule, no lead hints, P-TRUTH, P-GENERALITY
and counted cost. It also keeps D1's ancestor, its R1 ("the real time player should
probably not be considered with reflection and memory but actions").

It differs in role and in how it is judged:
- **The curator curates; it does not set subgoals.** It owns memory, the ontology
  and programs. The actor still chooses every goal and input.
- **Lessons from its first slice are designed in.**
  - *Power.* ADR 007's retained-progress screen reached 48.7% detection against
    80% required. Offline, deterministic metrics (retrieval probes, fit scores) guide
    development here, but adoption still rests on live lineage studies. Each one
    passes a power and cost gate before spend, and stops if underpowered
    ([evaluation](#evaluation-and-studies)).
  - *Cost.* Its recorder took $162.69 of $165.95 headroom. Here the curator is first
    run in shadow on sealed traces, so its cost per game hour is measured before
    any live run.
  - *Latency through serialization.* All playing-service calls share one lock
    (`harness/application.py:62-68`). The curator therefore runs as its own process
    with its own store connection and never takes that lock.

## Roles

| Role | Responsibility and time scale | Reads | Writes | Decides |
| --- | --- | --- | --- | --- |
| Software (host, custodian, memory service) | Mechanics on every request: custody, budgets, snapshot publication, type-similarity checks | Captures, receipts, store | Session logs; nothing semantic | Nothing semantic |
| **Actor** (the deciding player) | Perceives and acts every turn; emits intent and expectations; reads memory; hints; starts, steers and stops programs | Current frames, guide, mission brief, the latest curator snapshot, memory queries | Emissions and hints only | Every goal and input; sole input sender while it holds control |
| **Curator** (its own model role, concurrent) | Turns the trace into curated knowledge; maintains the ontology; induces, fits, tests and retires programs; benchmarks model slots | The full trace (frames, inputs, tool results, emissions, hints), the store, the workbench | Facts, ontology versions, programs, snapshots | What to remember, how to type it, which programs to keep. Sends no input to the live game |
| **Programs** | Act in the actor's place until they yield | The actor's observation interface | Emissions, like the actor | Inputs while running, within declared risk and budgets |
| **Monitor** (a model slot) | Watches running programs, and optionally the actor, for anomalies | Frames, emissions, progress stream | Stop or yield signals | Only whether to stop |

The actor keeps memory read tools. It loses memory append, program save and the
actor-written handoff summary; continuity comes from curator snapshots.

## Memory

### Two layers

- **Epistemic core (fixed, game-neutral).** Every assertion carries its source
  frames, the game time and wall time observed, who asserted it (actor, curator,
  program or slot binding), how it is known (observed, inferred, hinted), what it
  supersedes, and its belief state. This replaces the six kinds: their epistemic
  meanings (claim, correction, candidate advice) become core fields.
- **Domain ontology (proposed, fitted, per game).** The curator proposes types.
  A new game starts with the core and an empty domain layer. No domain type is
  seeded from recalled game knowledge (D13).

### Types and grooming

A type records a name, a definition, a field schema, an identity key (what makes
two instances the same thing), examples, an optional parent type, a staleness
hint, its version and usage statistics. Instances keep the type version they were
written under, so history never changes silently.

On every proposed type, the memory service returns the nearest existing types
(name, definition and field overlap) and requires an explicit choice: reuse,
specialize as a subtype, or create with a stated reason (D3). Grooming operations
are merge, split, rename and deprecate; each is a new ontology version. A type with
no instances or reads over a set number of boundaries is flagged for grooming.

Every reader gets the context to interpret the ontology: a compact **ontology
card** (types, one-line definitions, counts) is part of the actor's snapshot, every
query result names its type and version, and full definitions are one read away.

### Fitting and evaluating the ontology (D4)

An ontology is a model, judged by what it lets the player retrieve, penalized by
complexity, on data it was not fitted to:

| Criterion | Measure |
| --- | --- |
| Task utility (primary) | Curator: retrieval misses it detects in the player's own trace (a fact re-observed or needed while an earlier record of it went unretrieved, from expectations, citations and hints). Evaluation: the lead's probe suite, offline only |
| Compression | Description length of types plus instances against a flat store |
| Agreement | Independent classification passes; Krippendorff's α per type |
| Identity quality | Duplicate and wrong-merge rates found at re-observation |
| Staleness calibration | Brier score per type at re-observation |
| Coverage, use, stability | Share left untyped; reads and citations per type; churn per boundary |

The curator proposes an edit and keeps it when its own utility measure minus a
complexity penalty improves under cross-validation by lineage.

**The lead's probes never enter the playing system.** A probe ("at this point, a
query about X should surface Y") is written by the lead from a real episode's
frames, so it is game-specific lead knowledge. Feeding it to the curator would be a
lead hint and would let the system be curated toward a known answer
([mission ownership](../operations/mission-ownership.md)). Probes are offline
evaluation data only. Probes for held-out lineages are written after the lineage
ends, by the lead or an independent reviewer from frames, never from evaluator
readers (ADR008).

### Belief and disagreement

**Candidate, pending research (R3).** Represent belief in each assertion as a
subjective-logic opinion (belief, disbelief, uncertainty, base rate), which maps
to a Beta distribution. This keeps "no evidence" distinct from "conflicting
evidence".
- **Source reliability** is learned per source and type from re-observations, each
  of which confirms or refutes an earlier assertion (truth-discovery models of the
  Dawid–Skene family).
- **Staleness** is a per-type rate of change estimated from re-observation
  intervals (survival analysis); aging moves belief into uncertainty.
- **Partial pooling** uses the type hierarchy: sparse types borrow strength from
  their parent. The project's synthetic representation study found pooled
  estimation beating scoped estimation after drift (Brier .223 against .340), but
  scoped estimation winning on its phase-4 return; R3 must settle the trade-off.
- **The actor's current screen** is a fresh, low-uncertainty observation and
  overrides on conflict. A disputing hint becomes a correction for the curator.
- **Calibration** is reported as Brier scores at re-observation; uncalibrated
  scores are never labelled probabilities.

### Reaching the actor without latency (D2)

- The curator publishes versioned snapshots: the working set (open commitments,
  relevant facts, hazards, the ontology card), stamped "as of decision N, game
  time T".
- The actor's next observation result carries a **diff** against the last snapshot
  it saw, only when one changed, so the system prompt is not rewritten. Diffs still
  add to history. What they cost in cache rewrites and context is a hypothesis to
  measure in P0: in #397, 58–66% of requests already had large cache rewrites from
  image eviction.
- Reads are local store reads on their own connection. The actor never waits for
  the curator; a lagging curator means an older, labelled snapshot.
- Because the snapshot carries continuity, actor handoffs can become frequent and
  cheap. A successor starts from the curated state, not from a summary the
  previous actor wrote.

## Actor emissions (D10)

Emissions are fields on the tool calls the actor already makes, not extra turns.

| Field | Required | Example | Feeds |
| --- | --- | --- | --- |
| `intent` | Yes | "fetch water from the roof tank" | #384; credit assignment |
| `expectation` | Yes | "menu closes; water count rises by 1" | Prediction error as a curator attention signal; program success predicates; source reliability |
| `cites` | No | Memory IDs relied on | Carried-versus-used; reliability updates when a cited fact fails |
| `goal` | No | start, finish or abandon a subgoal | Segment boundaries for program induction |
| `confidence` | No | low, medium, high | Calibrated against outcomes |
| `flags` | No | unfamiliar screen; repeating myself; could be a program | Ontology gaps; program candidates |

`player_hint` is a separate tool: one line plus the current frame. The emission
burden (tokens, pace) is measured; survival and pace are guards. Expectations
also supply the producer of expectation evidence that
[#42](https://github.com/CVX-Hull/enactive/issues/42) is waiting for.

## Programs

### On the actor's interface (D7)

A program receives what the actor receives (the full-resolution frame, the
snapshot and the objective) and returns basic computer inputs with emissions, or
yields with a reason. The actor delegates "run this until it yields". For a simple
game the top level may itself be a program. Programs still emit only basic controls
through the same port (ADR006).

### Model calls through capability slots (D8)

Programs call models through named slots, for example `read_text(region)`,
`classify(region, labels)`, `ask(frame, question)` and `decide(options, context)`.
Each run's frozen package binds every slot to a route. Calls are cached by frame
hash, slot, prompt and binding, so offline backtests replay deterministically and a
slot swap is re-tested on the same frames. A faster or specialized binding replaces a
slow one when it matches accuracy on the slot's recorded cases. Slot spend counts
against the run's budgets. A text-reading slot carries no game semantics and sits
in the player system, separate from the evaluator's readers (ADR008).

### Supervised runs (D9)

- `program_start` returns a handle at once; the actor receives a compressed progress
  stream (milestones, expectation outcomes, anomalies, yields) and may `steer`,
  `stop` or act.
- **Actor input preempts the program between batches.** Today a program run holds
  the application lock for its whole run (`harness/application.py:185-196`), so an
  asynchronous run needs the runner outside that lock. Preemption waits, with a
  stated bound, for the current batch's receipt, then hands input to the actor: one
  input sender at a time. It is a new, resumable handover, distinct from user Pause,
  whose takeover generation is a permanent fence. A batch with partial or unknown
  delivery still stops input permanently under the
  [computer-control contract](../contracts/computer-control.md).
- A program declares a risk class per action. Low-risk steps run freely; a high-risk
  step needs approval granted ahead of time or pauses for the actor. Only those
  points wait.
- Budgets cover steps, wall time and model spend; a program also yields on a failed
  precondition or an unrecognized screen (perceptual hash).

### Monitor

A cheap model slot watches the progress stream and frames for anomalies and can
only stop or yield a program (D11). It may also watch the actor and raise a flag.
It is narrower than ADR 007's parallel levels: one watcher whose only power is to stop.

Whether it catches failures like the #397 death is a hypothesis. A game-neutral
monitor can recognize a hazard only through the model's own knowledge and the
player's curated lessons. That is the player's knowledge, which is allowed. But no
check is seeded from the lead's recalled game knowledge (D13), and its detection
rate is measured, not assumed. One recorded death is development data, not a
held-out case.

### Fitting and curation

- **Offline:** replay a candidate on recorded segments; measure agreement with the
  actor's actual inputs; check declared preconditions and success predicates frame
  by frame. Offline replay cannot evaluate inputs the actor did not send, so it is
  a filter, not proof.
- **Live:** in P2, supervised use in play under the monitor, with yield on any
  failed precondition. Practice-instance trials come in P3, if adopted.
- **Library:** per-program invocations, successes, yields, aborts and regressions;
  revision by parent over duplicates; retirement below a threshold; selection by
  explicit description, preconditions and measured statistics.

## The curator's workbench (D6)

- **Trace tools:** fetch frames and segments by time or input; diff frames by region;
  find visually similar frames by perceptual hash.
- **Self-checks:** the curator turns retrieval misses it detects in the player's
  own trace into its own regression checks, and re-runs them on every memory or
  ontology change. The lead's probe suite is separate evaluation data and never
  reaches the curator.
- **Ontology evaluation** with the measures above.
- **Program fitting** offline and in the practice instance.
- **Slot benchmarks:** candidate bindings scored on recorded cases.

The workbench is game-neutral; probes and recorded cases are per game and lineage.

## Practice instance (proposal; owner decision open)

- **Fork only at admission boundaries,** where the live game has saved and quit, into
  `.runtime/practice/<fork-id>/` with its own runtime root, app copy, lock,
  custodian, socket and session store. A shared app would escape the exclusion,
  because the game lock is per runtime directory
  (`harness/prepared_app.py:9`). The native bridge delivers events inside its own
  process (`harness/computer/native/bridge.mm`), so a second instance should not take
  the live game's input. Whether either game reacts to losing window focus is
  untested.
- **One way only.** Nothing is copied back; practice outcomes never become live state
  or count toward survival claims.
- **The curator holds only a practice port,** enforced by an import contract and
  separate credentials, so it cannot reach the live custodian.
- **Uses:** live program trials; counterfactual inputs; slot benchmarks on fresh
  frames; measuring whether the same save and inputs reproduce the same outcome in
  this build (unknown; to be measured, not assumed).
- **Concurrency is measured first.** It runs at background priority, with live input
  latency and frame timing as guards; it falls back to running between admissions if
  they are not held. The charter's "recheck before additional concurrent games"
  applies.
- Forks are evidence sets under the existing retention rules.

## Latency, concurrency and cost

| Concern | Design | Measured as |
| --- | --- | --- |
| Actor waits | Curator in its own process and store connection; never the application lock | Actor wait per request, against the #164 cadence target |
| Store contention | SQLite locks a whole database file for each write, and the store now uses the default rollback journal with a 1 s timeout (`harness/player/memory.py:20`). The actor's emissions and hints go to the session store or their own database file, never the curator's; the curator's store moves to WAL so readers never wait | Lock waits; failed writes |
| Curator lag | Batches triggered by screen change, hints or every K decisions | Lag in decisions and game time |
| Spend | Shadow measurement on sealed traces before live use; a cap as a fraction of actor spend | $ per game hour (actor $0.80 in #397) |
| Local CPU | Background priority for curator and practice work | Live input latency and frame timing |

## Evaluation and studies

Studies follow [S-EVIDENCE](../standards/evidence.md): development data and
evaluation data are separated, the unit is the lineage, budgets are matched or
reported, and each claim-deciding comparison freezes its inputs, analysis and
decision criteria and checks its power by simulation before it runs.

- **Development data:** the sealed #397 and #382 traces, including the four
  episodes above. Probes built from them fit and debug the system; they decide
  nothing.
- **Baseline lineages:** the two-lineage screen the owner selected for
  [#145](https://github.com/CVX-Hull/enactive/issues/145)
  ([#441](https://github.com/CVX-Hull/enactive/issues/441)) runs on the current player
  and can supply baseline rediscovery and carry rates, if its package records them.
- **Gate before spend:** each live study first simulates its power from the
  variance in development data and states a lineage count and dollar estimate. If
  it cannot reach the pre-registered detection rate within the owner's envelope, it
  does not run; the design is reshaped instead.
- **Process metrics per phase:**

| Phase | Primary metric | Guards |
| --- | --- | --- |
| Curator and memory | Rediscovery rate per game hour (re-observing a fact already known before a boundary); probe recall | Survival, pace, $ per game hour, curator lag, audited false-fact rate |
| Programs and monitor | Share of decisions handled by programs at a matched failure rate; monitor stops on recorded hazard cases | Survival, $ per decision, yields per hour |
| Ontology | Held-out probe utility minus complexity | Agreement, staleness Brier |

## Phases

| Phase | Scope | Spend | Adoption condition |
| --- | --- | --- | --- |
| **P0: baseline and workbench** | Trace tools; probe suite from sealed runs; baseline rediscovery and carry rates; handoff root validation (reject unknown IDs at handoff, not list them as omissions the successor may never see); snapshot-diff cache cost; the research synthesis | $0 gameplay; research only | Workbench reproduces the four episodes as failing probes |
| **P1: curator and memory** | Required emissions in every arm (D10). Arm A, the simpler path: root validation plus a pushed working set built from existing records, with no curator. Arm B: the epistemic core, ontology service, curator (shadow on sealed traces first, then live), snapshots, `player_hint`, and actor write tools removed. Ablations within B where the design allows | Shadow: curator calls only. Live: per package, after the gate | Pre-registered rediscovery and probe metrics on new lineages, B against A, guards held |
| **P2: programs and monitor** | Actor-interface programs; capability slots with record and replay; supervised runs with preemption and risk classes; monitor slot; offline fitting; library statistics | Per package | Pre-registered delegation share at matched failure rate; monitor detection on held-out hazard cases |
| **P3: practice instance** | One-way forks; determinism measurement; live fitting; slot swaps | Per package | Owner decision first; concurrency guards held |

Every phase replaces its contracts and stores in one migration
(`player-memory/2` → `/3`, `player-record/1` and `player-program/2` → their
successors); unsupported versions are refused.

## Rule alignment

Each change below takes effect only when its phase is adopted (D12).

| Current position | Where | Becomes |
| --- | --- | --- |
| "the active player owns planning, ordinary interpretation and its own reflection"; "advisers and programs are optional and only propose"; "no asynchronous learner service … added only if a study shows it improves play"; "one game/controller" | [Charter](../charter.md) current assumptions | The actor owns planning and interpretation of its current screen; the curator owns reflection and curation, adopted on the P1 study; one live game plus isolated practice instances (P3) |
| "Memory/programs/context are optional fallible player services" | [Player tooling](../standards/player-tooling.md); [architecture](../architecture.md) | Curated memory reaches the actor by snapshot; programs are actor-interface policies |
| Player-selected optional reflection | [S-PLAYER-INTERFACE](../standards/player-interface.md); [player-interface component](../components/player-interface.md) | Actor plays, reads, emits and hints |
| The player appends records; actor-written handoff summary | [Memory component](../components/memory-learning.md); [player guide](../player-guide.md); the driver (`tools/campaign_player.py`) | Curator writes; continuity from snapshots |
| `player-record/1`, `player-program/2`, `program-view/4`, `player-memory/2`; the custody and program-runner sections | [Computer-control contract](../contracts/computer-control.md); schemas | Their P1 and P2 successors; a resumable program-to-actor handover with a bounded wait |
| `player_handoff` with an actor-written summary; the previous final report in the admission prompt | [Player-host contract](../contracts/player-host.md); the driver | Successors and admissions start from the curator's snapshot |
| One actor and no concurrent host; the active actor writes memory; no second game during an admission | [Campaign run](../operations/campaign-run.md); [mission ownership](../operations/mission-ownership.md); run procedures | A concurrent curator host; the actor stays the only live input sender; isolated practice instances only after P3 |
| "no separate always-running strategic agent" | [Multi-rate synthesis](../research-multirate-agents.md) | Pointer to this ADR |
| #178 closeout: optional, deferred reflection | [ADR 007 outcome](../acceptance/2026-11-03-adr007-status-quo.md) | Its revisit condition is met by the episodes above; #178 becomes P1's study gate |

**Unchanged and binding:** ADR006 (basic control, one input sender), ADR008
(evaluator output never reaches the player, including the curator), P-TRUTH, the
no-lead-hint rule, S-MIGRATION, and S-EVIDENCE's treatment of recalled knowledge.

## Research agenda

S-EVIDENCE requires a dated synthesis of primary sources before any of the methods
above are chosen. The pass made on 8 November 2026 read abstracts and snippets and
cannot justify a design decision. Briefs pose questions and may name foundational
sources only.

| Area | Questions | Foundational sources a brief may name |
| --- | --- | --- |
| R1 Agent memory | Which write policies (event-triggered, extracted by a separate model, self-written) and retrieval policies (pushed working set, pulled queries) improve long-horizon tasks under partial observability, at what cost? What evidence exists on typed versus unified stores? | Cognitive architectures (Soar, ACT-R); episodic and semantic memory (Tulving) |
| R2 Concurrent consolidation | How do systems consolidate memory concurrently with an acting agent without adding latency, and what staleness and consistency costs result? | Complementary learning systems (McClelland et al. 1995) |
| R3 Belief under conflict | Subjective logic against Bayesian and Dempster–Shafer fusion; source-reliability estimation without ground truth; staleness as survival analysis; hierarchical pooling; calibration reporting | Jøsang (subjective logic); Dawid and Skene (1979); Kaplan and Meier (1958); Gelman's hierarchical models; Zadeh's critique of Dempster's rule |
| R4 Ontology induction and evaluation | How do LLM systems propose, merge and split schemas? Which evaluation methods (task-based, MDL, inter-coder agreement, entity resolution) predict utility? | Rissanen (MDL); Krippendorff (α); codebook development in qualitative research; Fellegi–Sunter record linkage |
| R5 Program induction and libraries | What makes induced skills help rather than hurt (verification by execution, granularity, retrieval, curation, drift)? | Options framework (Sutton, Precup and Singh 1999); DreamCoder; programming by demonstration |
| R6 Programs with model calls | Cascades, routing and distillation to replace slow calls with fast or specialized models; caching and replay for evaluation | Model cascades; knowledge distillation (Hinton et al. 2015) |
| R7 Supervision and interruption | Asynchronous human-on-the-loop supervision, preemption, risk-gated autonomy and runtime shields | Safe interruptibility (Orseau and Armstrong 2016); shielding (Alshiekh et al. 2018); sliding autonomy |
| R8 Novelty and anomaly detection | Detecting unfamiliar screens and anomalies from pixels for yield and monitor triggers; perceptual hashing reliability | Out-of-distribution detection basics |
| R9 Expectations and prediction error | Do agents that state expectations act better or learn faster? How are self-predictions calibrated? | Predictive processing; temporal-difference prediction error |
| R10 Offline evaluation of policies | Evaluating programs from logged play: agreement metrics, off-policy evaluation and their limits | Importance sampling and doubly robust estimators |
| R11 Practice environments | Forked environments for testing policies; determinism and replay in interactive software | Record and replay debugging |
| R12 Study design | Power and design for lineage-level process metrics; sequential testing to cap spend | Cluster-randomized design; sequential analysis (Wald) |

**Studies on our own data (P0):**
- the baseline rediscovery and carry rates on sealed traces;
- the probe suite and its inter-rater check;
- emission feasibility (tokens and pace from a short development run);
- curator shadow cost and lag on sealed traces;
- practice-instance determinism and concurrency (P3, after an owner decision).

## Open owner decisions

1. Whether to adopt the practice instance (P3) and its one-way fork rule.
2. The curator's spend cap as a fraction of actor spend, and whether its model may
   differ from the actor's.
3. Whether #441's baseline lineages record the P0 metrics before this design runs.
4. The belief model, after R3.

## Issue routing

[#387](https://github.com/CVX-Hull/enactive/issues/387) (cross-run knowledge) owns P1
memory; [#177](https://github.com/CVX-Hull/enactive/issues/177) owns P2 programs;
[#178](https://github.com/CVX-Hull/enactive/issues/178) owns the P1 study gate;
[#384](https://github.com/CVX-Hull/enactive/issues/384) owns emissions;
[#42](https://github.com/CVX-Hull/enactive/issues/42) owns expectation evaluation;
[#164](https://github.com/CVX-Hull/enactive/issues/164) owns the cadence target that
programs serve.
