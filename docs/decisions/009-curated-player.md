---
owner: lead
review_trigger: A phase's study result, an owner decision on an open question below, or a change to the host, memory, program, computer-control, evaluation or spectator contracts
status: proposed
date: '2026-11-08'
scope: Proposed direction for an acting player with a coding-agent curator in ephemeral sessions, a player-fitted ontology in one knowledge repository per game, programs on the actor's interface, managed containers and a spectator native to the design; nothing adopted, and current contracts govern the running system
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
  stores, 57 (73%) are `work`, nearly all status snapshots. `decision` was never
  used, `claim` twice; 4 of 5 `procedure` records are keybinding notes and the
  fifth is a resource list; 11 of 12 `advice`
  records come from the arm whose prompt asked for reflection; `correction` appears
  in one run. Code uses `kind` as a query filter and requires a correction to name
  what it supersedes (`harness/player/contracts.py:99`).
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
| A fishing rod on the floor nearby (record `94ce47`, `sd1a2`; `sd1a3`'s summary placed it in the shelter) | `sd1a5`–`sd1a7` tried to craft one |
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

The owner's words are recorded verbatim on #387:
[D1–D13](https://github.com/CVX-Hull/enactive/issues/387#issuecomment-6724463819) and
[D14–D18](https://github.com/CVX-Hull/enactive/issues/387#issuecomment-6724702447).

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
| D14 | "it can be framed like a coding agent … access to the information it needs via the same interface or similar interface that a coding agent would have … the updates it can make can be a dedicated submission folder … Maybe it can also run things within its workbench" | The curator is framed as a coding agent with a workspace; changes by submission are the owner's suggested shape |
| D15 | "Lag is fine. We don't need to introduce more lanes unless it turns out to be necessary" | One curator path; no fast extraction lane unless evidence requires it |
| D16 | "The knowledge repo should be one per game for now" | One knowledge repository per game |
| D17 | "Drafts are fine, but ensure that they are 'containerized' so that we can manage them and surface them to the agent and or clean them up. Also, think about 'containerization' idea could apply to other areas as well" | Drafts are managed containers; the owner asked for the idea to be considered elsewhere. Extending it is the lead's proposal |
| D18 | "our spectator has to be fully overhauled/updated to be native to this new design as well" | The spectator is redesigned around the new roles and containers |

**The lead's proposals, not owner decisions:** the disagreement method (a
candidate is [below](#belief-and-disagreement)), ephemeral curator sessions,
extending containers beyond drafts and the practice instance.

This page is an unadopted ADR in `decisions/` with `status: proposed`, following
[ADR 007](007-player-subgoal-level.md)'s precedent.

## Relation to ADR 007

[ADR 007](007-player-subgoal-level.md) proposed an acting player plus an
asynchronous subgoal level and was not adopted on 3 November 2026. This proposal
keeps its constraints that still hold: one input sender, no level state gating basic
control, the charter's responsiveness rule, no lead hints, P-TRUTH, P-GENERALITY
and counted cost. It also keeps D1's ancestor, its R1 ("the real time player should
probably not be considered with reflection and memory but actions"), and its rule
that software, not a model, commits proposals: here, the submission gate.

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
    and never takes that lock.

## Roles

| Role | Responsibility and time scale | Reads | Writes | Decides |
| --- | --- | --- | --- | --- |
| Software (host, custodian, gate, container manager) | Mechanics: custody and budgets on every request; validating and publishing submissions; managing containers | Captures, receipts, submissions, manifests | Session logs, published snapshots, manifests | Nothing semantic: it applies declared checks, and assembles each snapshot by rules the curator's published knowledge declares |
| **Actor** (the deciding player) | Perceives and acts every turn; emits intent and expectations; reads memory; hints; starts, steers and stops programs | Current frames, guide, mission brief, the latest published snapshot, memory queries | Emissions and hints only | Every goal and input; sole input sender while it holds control |
| **Curator** (a sandboxed coding agent in ephemeral sessions) | Turns the trace into curated knowledge; maintains the ontology; induces, fits, tests and retires programs; benchmarks model slots | Its session workspace: the trace window, the published knowledge, the brief, the workbench | Submissions and drafts only | What to propose. Sends no input to the live game; publishes nothing itself |
| **Programs** | Act in the actor's place until they yield | The actor's observation interface | Emissions, like the actor | Inputs while running, within declared risk and budgets |
| **Monitor** (a model slot) | Watches running programs, and optionally the actor, for anomalies | Frames, emissions, progress stream | Stop or yield signals | Only whether to stop |

The actor keeps memory read tools. It loses memory append and program save;
continuity comes from published snapshots, with the outgoing actor's summary kept
as a labelled hint at handoffs ([below](#reaching-the-actor-without-latency-d2)).

## Memory

### Two layers

- **Epistemic core (fixed, game-neutral).** Every assertion carries its source
  frames, the game time and wall time observed, who asserted it (actor, curator,
  program or slot binding), how it is known (observed, inferred, hinted), what it
  supersedes, its belief state, and its **scope**: the world and lineage it was
  observed in, or the game as a whole. This replaces the six kinds: their epistemic
  meanings (claim, correction, candidate advice) become core fields.
- **Domain ontology (proposed, fitted, per game).** The curator proposes types.
  A new game starts with the core and an empty domain layer. No domain type is
  seeded from recalled game knowledge (D13).

Because one repository serves a whole game (D16), scope matters: a fact about one
world's furniture is never shown to a lineage in another world as true. Types,
programs and lessons are game-level; world facts are not. The gate accepts a
game-level scope only with supporting evidence from at least two worlds, so a
mislabelled world fact cannot leak into other lineages.

### Types and grooming

A type records a name, a definition, a field schema, an identity key (what makes
two instances the same thing), examples, an optional parent type, a staleness
hint, its version and usage statistics. Instances keep the type version they were
written under, so history never changes silently.

For every submission that proposes a type, the gate returns the nearest existing
types (name, definition and field overlap) and requires an explicit choice: reuse,
specialize as a subtype, or create with a stated reason (D3). Grooming operations
are merge, split, rename and deprecate; each is a new ontology version. A type with
no instances or reads over a set number of boundaries is flagged in the next
session's brief.

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

The curator proposes an edit; the **gate**, not the curator, computes the utility
measure minus a complexity penalty, on trace that arrived after the submission's
base version, and accepts the edit only if it improves. The curator never grades
its own proposals.

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

- The gate publishes versioned snapshots from accepted submissions: the working
  set (open commitments, relevant facts in the actor's scope, hazards, the ontology
  card), stamped "as of decision N, game time T".
- The actor's next observation result carries a **diff** against the last snapshot
  it saw, only when one changed, so the system prompt is not rewritten. Diffs still
  add to history.
  - **#397's large rewrites.** 58–66% of each admission's **spend** went to requests
    with large cache rewrites (the evaluator's `host.large_rewrite_share`, a dollar
    share over requests writing more than 30,000 cached tokens). It was not 58–66%
    of requests, as this page first said. The #455 estimate found those rewrites on
    8% of requests, mostly where the host's context projection shortened the prompt.
  - **What a diff costs.** The [snapshot-diff cost](../design/snapshot-diff-cost.md)
    record (#455) estimates it offline: one 200-token diff adds about 5–14% of an
    average request's cost. It recommends a cap of about 200 tokens per diff and
    about 2,000 tokens of live diff text.
- Each published snapshot is an immutable file per version, so the actor's reads
  never wait on the gate's writes. The actor never waits for the curator; a lagging
  curator means an older, labelled snapshot. Lag is accepted (D15).
- Snapshot content comes from game-derived text, which could carry instructions
  into the actor's context. It is delivered as typed fields with length caps and
  marked as fallible player knowledge, never as instructions.
- **Handoffs and lag.** At an admission boundary the game has been saved and quit,
  so the next admission waits until the curator has published a snapshot covering
  the boundary; no live play waits. Within an admission, the outgoing actor's
  summary still passes to its successor, labelled unverified, and to the curator as
  a hint, until a snapshot covering the handoff is published. Removing that summary
  is an ablation, not a default.

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
through the same port (ADR006). A program may be a small module with its own
fixtures and tests in the knowledge repository; each run pins the program version
it used.

**Programs stay passive policies in an isolated runtime,** as today's are: an
engine with no I/O, bounded memory and a per-step time limit
(`harness/player/policy_program.py:13-20`). A program never runs code in the
process that holds input custody. It returns inputs, emissions or slot requests as
data; the runner checks them and acts. Curator-written code, including programs'
tests, runs only in the curator's sandbox or the gate's own sandbox, never in the
live harness or the process that publishes.

### Model calls through capability slots (D8)

Programs request model calls through named slots; the runner, not the program,
executes each request under budget and returns the result as data. Examples:
`read_text(region)`,
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
  asynchronous run needs the runner outside that lock. Custody rules for the
  handover:
  - While a program runs, it holds the input capability, and the actor's input
    access is suspended until preemption completes: one input sender at a time.
  - Preemption waits, with a stated bound, for the current batch's receipt. If the
    bound expires with no receipt, delivery is unknown, and input stops permanently.
    A batch with partial or unknown delivery stops input permanently, as the
    [computer-control contract](../contracts/computer-control.md) requires today.
  - Actor input based on a frame older than the program's last delivered input is
    refused until the actor observes again.
  - A handoff seals only with no program running; a running program is stopped
    first.
  - This is a new, resumable handover, distinct from user Pause, whose takeover
    generation is a permanent fence that the handover never touches.
  - Supervising a program costs actor turns, which the cadence measurements count.
- **Risk classes.** A program's author declares a risk class per action, but
  self-declaration is not trusted: an action is high-risk unless the gate has
  verified its class on recorded cases. A high-risk step needs approval granted
  ahead of time or pauses for the actor. The hard limits are budgets.
- Budgets cover steps, wall time and model spend; a program also yields on a failed
  precondition or an unrecognized screen (perceptual hash).

### Monitor

A cheap model slot watches running programs' progress streams and frames for
anomalies and can only stop or yield a program (D11). It is narrower than ADR 007's
parallel levels: one watcher whose only power is to stop programs. It may also
watch the actor, but what it sees there goes to the curator as a flag, never to the
actor as advice.

The #397 death was the actor's own action, so a monitor that stops only programs
would not have prevented it; it is not this component's motivating case. A
game-neutral monitor recognizes anomalies only through the model's own knowledge
and the player's curated lessons. That is the player's knowledge, which is allowed;
no check is seeded from the lead's recalled game knowledge (D13). Its detection
rate is measured on anomalies in recorded program runs, not assumed.

### Fitting and curation

- **Offline:** replay a candidate on recorded segments; measure agreement with the
  actor's actual inputs; check declared preconditions and success predicates frame
  by frame. Offline replay cannot evaluate inputs the actor did not send, so it is
  a filter, not proof.
- **Live:** in P2, supervised use in play under the monitor, with yield on any
  failed precondition. Practice-instance trials come in P3, if adopted.
- **Probation:** a newly published program stays probationary until scored on trace
  that arrived after its publication.
- **Library:** per-program invocations, successes, yields, aborts and regressions;
  revision by parent over duplicates; retirement below a threshold; selection by
  explicit description, preconditions and measured statistics.

## The curator as a coding agent (D14)

### Workspace

Each session gets a fresh workspace with the access a coding agent expects:

| Path | Access | Contents |
| --- | --- | --- |
| `trace/` | Read-only | The session's trace window: frames, inputs, emissions, hints and tool results, as an allowlisted projection of the session stores (never a directory copy) |
| `knowledge/` | Read-only | A worktree of the game's knowledge repository at the published version |
| `brief.md` | Read-only | Generated by software: what is new since the last session, open and stale drafts, recent gate failures, pending hints, flagged types |
| `workbench/` | Run-only | Command-line tools (below) |
| `submissions/<id>/` | Writable | A manifest and the proposed change set |
| `drafts/<id>/` | Writable | Work in progress carried to later sessions |
| `scratch/` | Writable | Discarded at close |

### Ephemeral sessions (lead's proposal)

- **Trigger.** Software starts a session when enough material has accumulated: a
  number of new decisions, a hint, an admission boundary or a gate failure. **One
  session runs at a time per game repository:** a single writer, no merge conflicts.
- **Budget.** Each session has a token and wall-clock budget.
- **Close-out is mandatory.** A session ends with zero or more submissions, each
  gated separately, and optionally drafts. Then the workspace is deleted; the session
  record (input manifest, transcript, submissions, gate results) is kept.
- **Failures and ordering.**
  - A crash or breached guard seals the session as aborted and keeps its drafts.
  - Every submission is gated before the next session starts. A submission whose
    base version is no longer current is rejected and reported in the next brief.
  - Gate failures trigger later sessions with back-off, so a failing submission
    cannot loop.
  - The operator can have the gate revert to an earlier knowledge version or disable
    a published program. That removes curator output; it adds no lead knowledge.
- **Why.** Nothing survives a session except through the gate or a managed draft,
  so the curator cannot accumulate unreviewed state. A session is defined by its
  inputs, so it can be replayed, and two curator hosts or models can be compared on
  identical inputs.
- **Shared caches** persist outside the workspace, content-addressed and managed by
  software: perceptual-hash indexes, which carry no judgment, and the model-call
  replay cache, which stores model outputs and is therefore kept per study arm.
- **Cold-start cost** (re-reading the ontology and context each session) is kept
  down by the brief and an index of types and programs that the curator maintains
  in the knowledge repository, published through the gate like everything else.
  It is measured in the P0 shadow run.

### Submission gate

The gate is the curator's continuous integration. It runs in its own sandbox and
checks every submission for:
- schema validity and provenance: every fact has a scope and cites frames inside
  the session's trace window (a citation shows where a claim came from, not that it
  is true);
- the type-similarity check (D3);
- the curator's self-checks, plus **gate-owned tests the curator cannot see or
  edit**. These are prospective: they score the submission on trace that arrives
  after its base version, which the curator could not have read. They are defined
  for programs (replay agreement, predicates) and for knowledge (retrieval misses
  and re-observation outcomes in the new trace);
- offline replay and sandbox limits for programs;
- size and budget limits.

The curator may add tests; deleting one requires a stated reason and is reported.
It never changes gate checks. An accepted submission is published atomically as a
new knowledge version and snapshot; a rejected one returns diagnostics in the next
brief. Only the gate merges: neither the curator nor the lead edits published
knowledge, so no lead hint can enter.

### Knowledge repository (D16)

One Git repository per game holds the ontology, programs, their tests and fixtures,
and configuration; Git provides history, diffs and rollback (S-CODE's reuse rule).
High-volume facts are stored in a database or JSONL alongside it and published as
versioned snapshots; a commit per observation would be heavy, and the split is
measured, not assumed. The proposed location is a project-local runtime path
(`.runtime/knowledge/<game>/`), sealed as evidence by study (an open decision).

For studies, **each lineage gets its own fork** of the repository from a pinned
starting version. The curator learns within that lineage's fork during play, and
nothing flows between lineages or arms during the study. Shared caches are kept per
arm, because the model-call cache stores model outputs. Held-out lineages use
worlds no development lineage has seen. Promoting what a study's lineages learned
into the game's main repository is a separate, recorded step after the study.

### Isolation

The curator runs code on the machine that runs the live game, and today's runtime
files include live secrets: the actor host receives the provider key in its
environment (`tools/campaign_player.py:179`), and each actor's `actor.json` holds
its custody token. The boundary is therefore default-deny:
- **Model calls** go through a proxy outside the sandbox that holds the provider key
  and enforces the spend cap. The curator never holds a key.
- **Filesystem reads** are denied except the session workspace. `trace/` is an
  allowlisted projection that excludes tokens, keys, routes and process files.
- **Network** is denied, including loopback, so the curator cannot reach the
  custodian, the playing service or the Pause route; the model proxy is its only
  channel out.
- **Host configuration** is fresh per session: an empty home directory and
  configuration, the coding-agent host's own memory turned off, and no user or
  project instruction files loaded, so neither lead guidance nor state from
  earlier sessions leaks in.
- **Resources** are capped: memory, disk and process count as well as CPU priority,
  with live input latency as a guard.
- **No evaluator records** (ADR008) and **no lead probes** are reachable.

Which project-local sandbox mechanism can enforce this was a research question (R13).
The [curator sandbox](../research-curator-sandbox.md) page records the answer, a
Seatbelt profile with a supervisor and the proxy (open decision 6), and its residual
risks. If a later escape-suite run fails, P1 does not run live.

The curator runs on a substitutable host, as the actor does under `player-host/3`,
so the same workspace can run under different coding-agent hosts and models.

### Workbench (D6)

- **Trace tools:** fetch frames and segments by time or input; diff frames by region;
  find visually similar frames by perceptual hash.
- **Self-checks:** the curator turns retrieval misses it detects in the player's
  own trace into its own regression checks, and re-runs them on every memory or
  ontology change. The lead's probe suite is separate evaluation data and never
  reaches the curator.
- **Ontology evaluation** with the measures above.
- **Program fitting:** offline replay, and practice-instance trials if P3 is adopted.
- **Slot benchmarks:** candidate bindings scored on recorded cases.

The workbench is game-neutral; recorded cases are per game and lineage. Its first part,
the trace projection, evidence reader, trace tools and sidecar manifests (#452), is
described in [trace projection and workbench](../design/trace-workbench.md).

## Containers (D17)

D17 requires drafts to be managed containers. The lead proposes the same shape
for other bounded, pinned units of work, but **each further kind is adopted only
when a phase has a concrete need for it**. A container is a directory with one
manifest shape (identity, kind, owner role, inputs and pinned versions, budgets,
lifecycle state, provenance and retention), so listing, inspection, surfacing,
retention and display can work the same way for every adopted kind.

Candidate kinds:

| Container | Pins | Lifecycle |
| --- | --- | --- |
| Curator session | Repository version, trace window, brief, host and model | created → active → closed → sealed |
| Submission | Session, base version, change set | proposed → gated → published or rejected |
| Draft | Session, base version, linked hints and trace references | open → stale → promoted or abandoned |
| Knowledge snapshot | Repository version, published facts | published → superseded |
| Program run | Program version, slot bindings, budgets | started → running → yielded, finished or preempted |
| Slot benchmark | Slot, candidate binding, recorded case set | queued → run → scored |
| Practice fork (P3) | Boundary save, app copy, runtime root | forked → active → retired |
| Actor session | Run package, repository version | the existing `computer-sessions/<id>`, described by a sidecar manifest |
| Study arm or lineage | Pinned repository version, package, curator binding | frozen → running → closed |

**Drafts in particular:** software lists them, surfaces open and stale ones in the
brief, promotes one by submitting it to the gate, and archives an abandoned or
expired one. A draft goes stale after a set number of sessions untouched and is
archived after a further period unless renewed. Cleanup is a policy, not something
the curator must remember.

**Containers are logical, not Docker.** On this Mac a container engine means a Linux
VM: Docker, Colima and Lima are installed but would start a VM and change existing
per-user state, and Apple's `container` needs an administrator install. The project's
environment rules exclude both ([environment](../environment.md); corrected 8
November 2026 from "would need a global installation", per R13 in the
[curator sandbox](../research-curator-sandbox.md) page). A container is a directory, a
manifest, Git branches or worktrees and, where code runs, an OS sandbox profile.

**Sealed evidence is never rewritten.** Existing and sealed directories, such as
`computer-sessions/<id>`, are described by **sidecar manifests** written beside them
or in an index; they are never migrated in place
([evidence cleanup](../operations/evidence-cleanup.md): "A sealed study is never
rewritten"). Retention follows the same rules: sealed kinds become evidence sets,
and scratch kinds (drafts, practice forks) carry their own expiry.

**Reuse review (S-CODE).** Existing capability considered: session directories, Git
branches and worktrees, and the sealed evidence store with its hash manifests. Unmet
requirement: drafts must be listed, surfaced in the brief, promoted and expired by
policy (D17). Smallest custom scope: a manifest schema and a small manager for
drafts; further kinds only as phases need them. Owner: the lead, with the curator
component's owner once one exists. Maintenance cost: the manifest schema, one
lifecycle per adopted kind, and its tests. Retirement trigger: if Git branches and
the evidence store alone can list, surface and expire drafts, the manager is
removed.

## Spectator (D18)

The spectator is redesigned around the four roles and the containers. The current
one ([observer component](../components/observer-operations.md)) shows one player:
a supervised control path and a read-only evaluator view.

| View | Shows |
| --- | --- |
| Health strip | Actor cadence, curator lag, gate pass rate, snapshot freshness, program delegation share, monitor alerts, spend against cap |
| Actor | Live frame; decisions with **intent, expectation and outcome** side by side; citations; hints; which snapshot it is acting on |
| Curator | Session timeline with lag; each session's brief, transcript summary, submissions and gate verdicts; submission diffs; open and stale drafts |
| Knowledge | Ontology browser with versions and grooming history; facts with provenance frames, scope, belief and staleness; what each snapshot showed the actor and when (absorbing [#294](https://github.com/CVX-Hull/enactive/issues/294)) |
| Programs | Library with versions and statistics; live delegated runs with their progress; preemptions, yields, monitor flags and stops |
| Containers | One inventory across kinds, with state, age and retention |

**Constraints carried over:** the Pause path stays independent and unchanged; the
viewer stays read-only; nothing the viewer or evaluator computes reaches the player,
including the curator (ADR008). The shared manifest lets one generic container list
and detail view cover most kinds, with a few role-specific panels.

**Phasing:** P0 delivers sidecar manifests over the sealed traces and the new
frame, which can already show actor sessions and the four forgetting episodes. Each
later phase ships its views with it, so every view has real data when it ships. The
P0 frame's routes and payloads are in the
[spectator frame contract](../contracts/evaluation.md#spectator-frame-spectator-frame1).

## Latency, concurrency and cost

| Concern | Design | Measured as |
| --- | --- | --- |
| Actor waits | Curator in its own process, never the application lock; the actor reads published snapshots only | Actor wait per request, against the #164 cadence target |
| Store contention | SQLite locks a whole database file for each write, and the current store uses the default rollback journal with a 1 s timeout (`harness/player/memory.py:20`). The actor's emissions and hints go to the session store or their own file; published snapshots are read-only to the actor; only the gate writes the knowledge store | Lock waits; failed writes |
| Curator lag | Sessions triggered by new decisions, hints, boundaries or gate failures; one at a time per repository; lag accepted (D15) | Lag in decisions and game time |
| Spend | Coding agents read a lot. Shadow measurement on sealed traces before live use, on two curator hosts; a cap as a fraction of actor spend | $ per game hour (actor $0.80 in #397) |
| Local CPU | Background priority for curator sessions, workbench runs and practice work | Live input latency and frame timing |

## Evaluation and studies

Studies follow [S-EVIDENCE](../standards/evidence.md): development data and
evaluation data are separated, budgets are matched or reported, and each
claim-deciding comparison freezes its inputs, analysis and decision criteria and
checks its power by simulation before it runs.

- **Unit of analysis.** Each lineage has its own repository fork from a pinned
  start, and caches are per arm, so the lineage stays the independent unit.
- **P1 is decided offline first.** Memory arms can be compared without changing what
  the actor did: replay arm A and arm B over the same sealed and baseline traces,
  and score what each would have put in front of the actor against what the actor
  later needed. Scoring uses what the actor would have received, not each arm's own
  query interface. Live lineages then serve as non-inferiority guards (survival,
  pace, cost) and to observe behaviour, not to carry the primary comparison.
- **Probes are arm-independent and blinded.** They are written from the baseline
  trace before either arm is replayed, so they cannot depend on the arm. Their
  annotation cost (fact-level labelling per lineage) is estimated in P0 before any
  spend; ADR 007's recorder failed on a cost of this kind.
- **Development data:** the sealed #397 lineage, including the four episodes above,
  and #372's short development-loop runs. Probes built from them fit and debug the
  system; they decide nothing.
- **Held-out data:** #382's three day-scale lineages, sealed in `372-382-dev-loop`.
  No episode, probe or design choice came from them; this page's problem statement
  counted their records and queries only in aggregates. #178 writes their probes.
  They predate emissions, which the P1 study records as a limitation.
- **#441 is deferred.** On 8 November the owner decided: "I would prefer to do this
  run after we move forward on the ADR we just discussed to be fruitful." Its
  lineages are re-shaped against the design in place when it resumes.
- **Gate before spend:** each live study first simulates its power from the
  variance in development data and states a lineage count and dollar estimate. If
  it cannot reach the pre-registered detection rate within the owner's envelope, it
  does not run; the design is reshaped instead.
- **Process metrics per phase:**

| Phase | Primary metric | Guards |
| --- | --- | --- |
| Curator and memory | Rediscovery rate per game hour (re-observing a fact already known before a boundary); probe recall | Survival, pace, $ per game hour, curator lag, gate pass rate, audited false-fact rate |
| Programs and monitor | Share of decisions handled by programs at a matched failure rate; monitor detection of anomalies in recorded program runs | Survival, $ per decision, yields per hour |
| Ontology | Held-out probe utility minus complexity | Agreement, staleness Brier |

## Phases

| Phase | Scope | Spend | Adoption condition |
| --- | --- | --- | --- |
| **P0: baseline, workbench and frame** | Trace tools; probe suite from sealed runs and its annotation cost; baseline rediscovery and carry rates; handoff root validation (reject unknown IDs at handoff, not list them as omissions the successor may never see); snapshot-diff cache cost; draft containers and sidecar manifests over sealed traces; the spectator's new frame; the sandbox mechanism (R13); curator shadow sessions on sealed traces under two hosts (cost, lag, cold start); the research synthesis | $0 gameplay; research and shadow curator calls only | Workbench reproduces the four episodes as failing probes; shadow cost and lag measured; a sandbox enforcing the [isolation boundary](#isolation) exists |
| **P1: curator and memory** | Required emissions in every arm (D10). Arm A, the simpler path: root validation plus a pushed working set built from existing records, with no curator. Arm B: the epistemic core, the knowledge repository, curator sessions and the gate, snapshots, `player_hint`, and actor write tools removed. Ablations within B only where power allows. Spectator actor, curator, knowledge and draft views | Offline replay: curator calls only. Live: per package, after the gate before spend | Offline: pre-registered probe and rediscovery metrics, B against A, on replayed traces. Live: non-inferiority guards held |
| **P2: programs and monitor** | Actor-interface programs as passive policies; capability slots with record and replay; supervised runs with preemption and verified risk classes; monitor slot; offline fitting; probation and library statistics; spectator program views | Per package, after the gate before spend | Pre-registered delegation share at matched failure rate; monitor detection on anomalies in recorded program runs |
| **P3: practice instance** | One-way forks; determinism measurement; live fitting; slot swaps; spectator fork views | Per package | Owner decision first; concurrency guards held |

Every phase replaces its contracts and stores in one migration
(`player-memory/2` → `/3`, `player-record/1` and `player-program/2` → their
successors); unsupported versions are refused.

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
- **The curator holds only a practice port,** enforced by an import contract,
  filesystem permissions and separate credentials, so it cannot reach the live
  custodian.
- **Uses:** live program trials; counterfactual inputs; slot benchmarks on fresh
  frames; measuring whether the same save and inputs reproduce the same outcome in
  this build (unknown; to be measured, not assumed).
- **Concurrency is measured first.** It runs at background priority, with live input
  latency and frame timing as guards; it falls back to running between admissions if
  they are not held. The charter's "recheck before additional concurrent games"
  applies.
- A fork is a container; it is sealed or retired under the existing retention rules.

## Rule alignment

Each change below takes effect only when its phase is adopted (D12).

| Current position | Where | Becomes |
| --- | --- | --- |
| "the active player owns planning, ordinary interpretation and its own reflection"; "advisers and programs are optional and only propose"; "no asynchronous learner service … added only if a study shows it improves play"; "one game/controller" | [Charter](../charter.md) current assumptions | The actor owns planning and interpretation of its current screen; the curator owns reflection and curation, adopted on the P1 study; programs act in the actor's place under supervision and yield (P2); one live game plus isolated practice instances (P3). A curator running while no one watches triggers the charter's "recheck … unattended operation", done before P1 runs live |
| "Memory/programs/context are optional fallible player services" | [Player tooling](../standards/player-tooling.md); [architecture](../architecture.md) | Curated memory reaches the actor by snapshot; programs are actor-interface policies; the curator works through a gated workspace |
| Player-selected optional reflection | [S-PLAYER-INTERFACE](../standards/player-interface.md); [player-interface component](../components/player-interface.md) | Actor plays, reads, emits and hints |
| The player appends records; actor-written handoff summary | [Memory component](../components/memory-learning.md); [player guide](../player-guide.md); the driver (`tools/campaign_player.py`) | Curator submits; the gate publishes; continuity from snapshots |
| `player-record/1`, `player-program/2`, `program-view/4`, `player-memory/2`; the custody and program-runner sections | [Computer-control contract](../contracts/computer-control.md); schemas | Their P1 and P2 successors; a resumable program-to-actor handover with a bounded wait |
| `player_handoff` with an actor-written summary; the previous final report in the admission prompt | [Player-host contract](../contracts/player-host.md); the driver | Successors and admissions start from the published snapshot |
| One actor and no concurrent host; the active actor writes memory; no second game during an admission | [Campaign run](../operations/campaign-run.md); run procedures | A concurrent curator host; isolated practice instances only after P3 |
| "Optional advisers/programs only propose"; one custodian, "no second writer"; Pause and partial or unknown delivery "cannot become a resumable transfer" | [Mission ownership](../operations/mission-ownership.md) | Programs act in the actor's place under supervision (P2). One input sender at a time, through a new resumable program-to-actor handover; Pause and uncertain delivery stay permanent |
| A host "hosts one actor" | [Player-host contract](../contracts/player-host.md) | A curator-host contract, or an extension of the player host, so the curator runs on a substitutable host |
| `harness/player/` has no process, provider or native authority | [Documentation map](../documentation.md); [architecture](../architecture.md) and its components | An owned code location and component pages for the curator process, the gate, the container manager and the sandbox; the player package stays pure |
| The spectator's view API and the observer's responsibilities | [Evaluation contract](../contracts/evaluation.md); [observer component](../components/observer-operations.md); ADR008's spectator half | Views native to the roles and containers; read-only; Pause unchanged |
| Owned resources and retention | [Environment](../environment.md); [evidence cleanup](../operations/evidence-cleanup.md) | Knowledge repositories, curator sessions and practice forks as owned, managed containers with retention rules |
| "no separate always-running strategic agent" | [Multi-rate synthesis](../research-multirate-agents.md) | Pointer to this ADR |
| #178 closeout: optional, deferred reflection | [ADR 007 outcome](../acceptance/2026-11-03-adr007-status-quo.md) | Only the repeated-gap part of its revisit condition is met; on the owner's direction, #178 becomes P1's study gate |

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
| R13 Agent workspaces and verification gates | How well do coding agents work in sandboxed, ephemeral workspaces? Which project-local sandbox mechanisms exist on this platform? How do agents game pass/fail gates, and which gate designs resist it? What does a session cost in tokens and cold start? | Continuous integration; code review; capability-based security (Dennis and Van Horn 1966); least privilege (Saltzer and Schroeder 1975) |
| R14 Oversight interfaces | What must a supervisor see to judge a multi-role autonomous system and intervene in time? | Supervisory control (Sheridan); situation awareness (Endsley 1995) |

**Studies on our own data (P0):**
- the baseline rediscovery and carry rates on sealed traces;
- the probe suite and its inter-rater check;
- emission feasibility (tokens and pace from a short development run);
- curator shadow sessions on sealed traces under two hosts: cost, lag, cold start
  and gate pass rate;
- practice-instance determinism and concurrency (P3, after an owner decision).

## Open owner decisions

1. Whether to adopt the practice instance (P3) and its one-way fork rule.
2. The curator's spend cap as a fraction of actor spend, and whether its model may
   differ from the actor's.
3. *Decided 8 November 2026:* #441 is deferred until this design has moved forward,
   and P1's held-out data comes from #382 instead (above).
4. The belief model, after R3.
5. *Decided 8 November 2026:* the knowledge repository lives at the project-local
   runtime path `.runtime/knowledge/<game>/`, a separate Git repository sealed into
   the evidence store per study (#453).
6. *Decided 8 November 2026, after R13:* the sandbox is a project-owned Seatbelt
   profile with a supervisor and the key-holding model proxy, for P0 shadow runs and,
   if #454 holds, live P1. The escape suite is re-run after every macOS or host update.
   Disk becomes a hard cap through a sparse disk image if #454 shows write bursts
   ([curator sandbox](../research-curator-sandbox.md), #451).

## Issue routing

[#445](https://github.com/CVX-Hull/enactive/issues/445) holds the implementation and test
plan (phases, critical path, evidence split, test strategy and where each owner decision
sits). [#446](https://github.com/CVX-Hull/enactive/issues/446) owns P0;
[#387](https://github.com/CVX-Hull/enactive/issues/387) (cross-run knowledge) owns P1
memory and the knowledge repository; [#177](https://github.com/CVX-Hull/enactive/issues/177)
owns P2 programs; [#472](https://github.com/CVX-Hull/enactive/issues/472) owns P3;
[#178](https://github.com/CVX-Hull/enactive/issues/178) owns the P1 study gate; [#384](https://github.com/CVX-Hull/enactive/issues/384) owns emissions;
[#42](https://github.com/CVX-Hull/enactive/issues/42) owns expectation evaluation;
[#164](https://github.com/CVX-Hull/enactive/issues/164) owns the cadence target that
programs serve; [#143](https://github.com/CVX-Hull/enactive/issues/143) owns the
spectator redesign, absorbing [#294](https://github.com/CVX-Hull/enactive/issues/294).
