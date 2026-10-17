---
owner: lead
status: historical
date: 2026-10-17
scope: Frozen #30/#21 interfaces, implementation handoffs and adjudicated review repairs
---

# Recovery and memory — implementation brief

Round: #30 and #21. Base: `74c9cdf4796780b53165456ad1f779b4d37b5810`.
The lead owns decisions, integration and shared runtime; @CVX-Hull is accountable.
The implementation and targeted acceptance are recorded in the
[dated report](../acceptance/2026-10-17-recovery-memory.md). This brief preserves the
round's design and handoffs; current contracts live in architecture/protocol.

## Owner outcome and scope

Provide a bounded native/controller route for asking CDDA to interrupt its current
activity, explicitly answering its own confirmation, and continuing one visible
raw debug error. Gameplay remains paused; no answer proves cancellation or task
success. In parallel, provide bounded task memory that distinguishes observations,
history and interpretation without granting execution authority.

#31 will add public recovery UI/CLI ingress; #8 owns broader integrated acceptance.
This round still requires #30's targeted real windowed native probes through the
controller API. #20 skills, #33 real gameplay-predicate integration, supervisor,
planner, live models and spending remain outside this round. Memory tests establish
software behavior, not gameplay competence. Original estimates remain #30 M/Low,
3–5 focused sessions plus native validation; #21 M/Medium, 2–4 sessions. These are
provisional effort units, not elapsed-time or cost promises.

## Coordinated wire-v3 migration

Use native wire **3** exclusively. Current v2 fixes recovery operations to empty
and interrupt ownership to null; changing these semantics requires a coordinated
cutover. Ordinary request and observation shapes remain otherwise unchanged.
Every producer/consumer, discovery advertisement, CLI/viewer guard, evidence
validator, source-form control and fixture must use v3; reject v2 and unknown
versions, with no alternate runtime readers or downgrade. Gameplay record schema
`gameplay/1` is a distinct contract and does not change merely because wire does.
The evidence-store format advances to version 2 because its stored observations
now use v3; no automatic old-store reader is introduced.

Stop affected writers before native installation/cutover. Preserve the full old
bridge and its hash inventory under a project incident archive. Do not relabel
old requests or observations as v3. Create a fresh bridge and represent unresolved
old actions as current-format **historical incident references**, not executable
admissions. Preserve the original v2 action ID and source file hash/path; never
read the archived envelope to grant authority. Source incident remains unknown.
Existing evidence stores remain archived originals; new tasks use fresh v3 stores.
Document validated before/after identities and remove any temporary converter.

The only current incident-reference file is `historical-incidents.json` in the
bridge: exact keys `schema` (literal `incident/1`) and `incidents` (at most 64).
Each item has exact keys `id` (nonempty, <=128 chars), `channel` (`gameplay` or
`control`), `source_path` (project-relative owned archive file), `source_sha256`
(lowercase 64 hex), and `reason` (nonempty, <=1024 chars). IDs are unique per
channel. Require the source under `.runtime/incidents/`, a path of at most 1024 chars,
and at most 1 MiB of source bytes. Validate containment (including symlinks), file
existence and SHA-256 without parsing source bytes. Invalid/missing evidence blocks startup. Expose immutable references as
`historical_unknowns` in controller status/journal, distinct from live admissions.
No automatic resolution, replay, copying authority fields, or save modification.

## Recovery wire and controller API

Keep existing gameplay files separate from
`control.json -> control-claimed.json -> control-response.json`. One process lock
outlives both writers. A nonblocking `control_lock` allows at most one dispatch-capable live
recovery (retained historical unknown outcomes are separate); `data_lock` serializes Pause/revocation and admission. Never acquire the
ordinary `command_lock` while waiting for recovery. Ordinary input/resume must
reject while recovery is pending or its writer is active; a recovery result cannot
clear a later Pause. Shutdown first revokes, then
waits for both writers before releasing the process lock. A second recovery cannot
overwrite an unexpired pending/claimed operation. Observe/status may reconcile
without acknowledging the original gameplay objective or silently replaying work.

Every control request has exact common fields:
`protocol: 3`, `id` (UUID; <=80 chars), `kind`, `session`, `control_generation`,
`authority: {controller_boot_id, counter}`, `created_ms`, `deadline_ms`.
Times are integer Unix milliseconds; deadline is created + 2000, no future creation
beyond 1000 ms clock tolerance. Maximum serialized envelope 4096 bytes. Distinct
control seen-ID ledger rejects duplicate IDs; overflow fails closed rather than
evicting IDs that could replay. Identity/session/generation/token are mandatory.

| Kind | Additional exact fields | Native eligibility/result |
| --- | --- | --- |
| `request_interrupt` | none | At an interruptible activity poll, inject the registered `pause` binding through the existing engine path. Return `prompt_opened` only when its owned confirmation is rendered; otherwise `not_applicable`, `rejected` or timeout/unknown. No matching turn revision is needed for this request. |
| `answer_interrupt` | `boundary_id`, `revision`, `frame`, `interrupt_request_id`, `choice` (`YES`/`NO`) | Match the owned confirmation and current successful frame; resolve its usable registered binding. Return `answer_delivered` after committing exactly one input. |
| `continue_debug_once` | `boundary_id`, `revision`, `frame` | Match the current raw debug prompt and rendered frame; emit Space only. Return `dismissal_delivered` after one committed input. |

Control response has exact fields `protocol: 3`, `id`, `status`, `error`, `state`.
`state` is the same validated v3 observation envelope (not command authority merely
because nested in a response). Native statuses: `dispatched` (nonterminal),
`prompt_opened`, `answer_delivered`, `dismissal_delivered`, `not_applicable`,
`rejected`. Host-only `unknown`/`controller_error` retain identity and uncertainty.
Delivery terminal states need not have a new successful frame; observation afterward
is still required. `prompt_opened` requires fresh matching confirmation evidence
and owning interrupt ID. Do not overwrite gameplay response/pending when publishing
control status; only the shared passive state snapshot may advance.

Expose recovery as an explicit `Controller.recover(kind, **payload)` API, not in
`execute`'s ordinary command allowlist or model facade. In this round HTTP/CLI do
not expose it. Caller supplies `expected_session`, `expected_control_generation`
and, for answers/debug, `expected_boundary_id`, `expected_revision`, `expected_frame`
plus owning interrupt ID/choice. Do not silently refresh a caller's decision from a
new observation. Each recovery first pauses/revokes; capture its own post-Pause token
under the admission lock. Any later Pause invalidates even already claimed inputs.
A bounded host wait may be shorter than the fixed two-second native expiry; retain
uncertainty until explicit reconciliation. All recovery leaves transport paused. After a control timeout, only explicit
successful `execute("observe")` with fresh validated state and the prior native
deadline elapsed may retire the live `control_pending` slot. Passive status never
clears it. Revoke the old token and retire unclaimed input before another admission;
a still-active writer or unreconciled claim rejects new recovery. Durable admission
and unknown history remain, with no inferred old cancellation or task success. A
deliberate new recovery needs new identity and current generation/prompt evidence,
not an automatic retry. This reconciles live transport capacity without resolving
the historical unknown outcome.

Persist a control admission before inbox publication; retain unknown admissions,
including after native dispatch removes claimed metadata. Restore only current
formats on startup; separately retire unclaimed work on both channels. Matching
terminal responses can retire their own admission, never unrelated gameplay work.
Expose `control_pending` and `control_unknown_outcomes` separately. Bounded display
history must not decide whether a durable admission exists. Late matching results
may explain delivery but cannot prove cancellation or retroactively resume gameplay.

## Native ownership and source anchors

Inspected pinned 0.I-1 source: `do_turn.cpp::handle_key_blocking_activity` injects
its registered `pause` through `input_context`, checks
`u.activity.is_interruptible_with_kb()`, then calls `cancel_activity_query`.
`game.cpp::cancel_activity_query` can ask destination and activity questions;
`cancel_auto_move` also serves unrelated callers. `debug_error_prompt` reads raw
Space outside `input_context`. Keep these policies and engine behavior intact.

Bracket only the harness-delivered pause's native cancellation invocation with an
interrupt-owner RAII scope. Scope the two specific `query_yn` call sites (destination
and activity) through a helper/RAII wrapper which is active only inside that owned
invocation. Do not promote every YESNO under an arbitrary outer context. Each owned
query entry/exit gets a new opaque boundary ID, including repeated same-category
questions. Input-context scopes inherit confirmation identity only from this
specific marker; nested unrelated input or debug replaces it and cannot consume an
answer. Returning from a nested boundary requires new matching evidence. Clear
ownership when the invocation exits, session changes or the operation is invalidated.

Advertise `request_interrupt` only at the eligible activity-poll boundary,
`answer_interrupt` only at the exact owned confirmation (with nonnull interrupt ID),
and `continue_debug_once` only at the raw debug boundary. Other boundaries advertise
no operations and null ownership. All ordinary key/action/resume still reject
activity/confirmation/debug boundaries. No private activity contents are exported.

At eligible input points: process native input/Pause, then recovery, then ordinary
requests. Recovery must be polled even when ordinary gameplay is pending. Native
acceptance increments control generation/revision and latches Pause before delivery;
re-read the durable host token at the final input commit gate. A later Pause cannot
undo already committed input. WAIT can finish or resume backlog: report actual
boundary, not assumed cancellation. Never call cancel_activity directly.

Freshly verify original hashes for new `game.cpp` anchors from the pinned archive;
patches remain count/hash checked and repeatable. No test-only success bypass.

## Bounded memory contract

New `harness/gameplay/memory.py` composes the existing `TaskSpec`, `EvidenceRef`,
`Fact`, `Interpretation`, `PlanCandidate`, `PrimitiveResult`, `SkillDescriptor` and
`EvidenceStore`. No controller import, bridge writes, separate image store, generated
code, filesystem journal replay or dependency installation. Import Linter's existing
passive-gameplay contract applies. Module-local frozen typed records can represent
memory classifications without changing serialized gameplay/1 contracts.

One `TaskMemory` instance belongs to one immutable TaskSpec/store. An explicit
monotonically increasing execution epoch invalidates plans, never verified history;
retire a task on replacement and create a new instance. A new instance/reopened
store has no current facts, candidate validity or execution permission until fresh
observation is supplied. This is not run continuation or a lease manager.

Lead-owned prerequisite: `EvidenceStore.source_status(ref)` verifies identity and
file integrity and returns `retained` or `disputed`. Its separate persistent disputed
set survives successful ingestion/reopening; freshness/session invalidation alone
does not dispute historical truth. Store format 2 includes this set. Hash failure
persists the dispute before raising, and repairing bytes never clears it. The memory
worker must use this public API, not private store fields or transient error text.
Implementation review additionally reproduced an A→B→rejection→A sequence that
hid an intervening invalidation from identity comparison alone. The store now
exposes process-local `authority_generation()`, incremented on identity changes,
invalidation and close. Memory captures and compares it during synchronization;
an old candidate cannot become valid again merely because A returns. This is
instance-local invalidation history, not a persisted execution token or permission.

Public operations must support: observe/refresh from `store.current` with caller's
actual monotonic/wall clock; typed immutable snapshot; append interpretation or
hypothesis with source references; retain candidate plan; retain versioned procedural
descriptor/failure references; record an action result once; advance epoch; retire.
Snapshots and plan retention also require current caller clocks and recheck freshness.
Deduplicate dependencies, then recheck every retained source status at live retrieval
and annotation/plan validation (at most 32 original frames); reject disputed sources
for new beliefs and invalidate their retained dependent beliefs/plans. Immutable
returned snapshots are explicitly classified as of those clocks, never live authority.
The worker may select cohesive method names but cannot change these semantics.

Current facts come only from fresh verified store evidence in this task's session.
Historical facts keep original frame/session/turn and are never promoted by memory
access or a summary. Interpretations and hypotheses remain explicitly non-factual,
even if their source is current. Plans are data, not approved actions. Procedural
references/failures are separate from world facts and do not advertise implemented
skills. All source references must belong to the store and pass integrity checks.
Cross-session action evidence is permitted only as context for an unknown outcome
under the existing PrimitiveResult contract; it cannot advance task progress.

A changed observation identity invalidates retained candidates even at the same
revision; a new source must not conceal a rejection between memory refreshes. A
changed revision also invalidates plans bound to the older revision. Store rejection,
missing/stale evidence, contradiction, unknown action, session/task/epoch change or
retirement invalidates dependent plans conservatively. Preserve history and reasons;
never rewrite an old fact as current truth. A source conflict invalidates affected
beliefs and dependent candidates; if the store only exposes a global invalidation,
invalidate all source-dependent candidates rather than infer which remained valid.
Repeated identical action IDs are idempotent; conflicting results for an ID preserve
the original and record a conflict, never double-count progress. Memory records
observed displacement only when consistent with referenced positions; it does not
infer action success from unrelated later frames or implement stage completion.

Initial ceilings per task: 128 source facts, 32 interpretations, 32 hypotheses,
16 plans, 16 procedural references, 32 action results; 64 KiB total stored text,
1024 chars per text and at most 8 references per annotation. Enforce before mutation;
capacity failure preserves existing entries and invalidates current candidate use.
No silent eviction of unresolved actions or source evidence. Snapshot retrieval is
bounded and deterministic, never a similarity search. Report counts/text bytes and
that image verification cost is bounded by the existing store's 32-frame/64-MiB
limits; avoid redundant full-store rehash per item. These are conservative starting
limits, revisited on measured pressure rather than a generalized memory platform.

## Allocation and acceptance

After independent brief review, create `.runtime/worktrees/native-recovery` and
`.runtime/worktrees/gameplay-memory` at the exact integration checkpoint. Named
clean-context workers each own their checkout; at most two implementation writers.
Native worker owns native bridge/header, patch/upstream pin, controller and existing
controller/setup tests. Memory worker owns only new memory module/focused tests.
Lead owns all shared contracts/evidence migration, consumers, controls, current docs,
integration, builds, game, saves, bridge, dependencies and ports. No overlapping
worker writes; hand back after two failed repairs or ownership drift.

Focused checks: controller/setup transport and patch fixtures for native worker;
memory tests with real temporary EvidenceStore files for memory worker. Workers use
project interpreter but isolated cache/output directories. Lead integrates, runs
`.venv/bin/python tools/check.py`, independently reviews code/tests and verifies an
exact pinned native build. Record unsuccessful attempts, not just repaired passes.

Required native probes: legitimate WAIT interruption and explicit YES/NO, activity
finished/unsupported, raw debug continuation, stale generation/prompt/frame, later
Pause and timeout/restart retaining original/control IDs. Record frames, original
engine errors, source/binary hashes and effects actually observed. No full-screen,
save editing, direct cancellation, fabricated completion, hidden-state inspection
or weakened guard. If source hooks cannot prove ownership, repair/escalate design
before claiming #30 accepted; do not close it with mocks or by dropping operations.

Update current docs/controls only with implemented behavior, retaining future #31/#8
claims as future. Update diagrams if their asserted flow changes. Publish through
protected PR(s), attach them, verify exact CI/rules, merge without bypass and close
only accepted #30/#21. Refresh dependent readiness. Clean completed worktrees,
branches and stale owned processes after preserving handoffs, saves and evidence.

## Design review disposition

Independent reviewer `recovery_memory_design_review` identified that the old public
evidence API could not expose historical conflicts after newer ingest cleared the
transient error. The lead added sticky source-status metadata and tests for conflict
then newer ingest between refreshes, stale-versus-disputed history, and corruption
through reopen/byte restoration without losing other entries. Reviewer accepted the
bounded per-source-status approach without a separate generation API, requiring
identity-sensitive candidate invalidation and current clocks for snapshots. Native
hooks and other ownership/migration boundaries had no additional design findings.
This review is design evidence, not proof of implemented recovery or native behavior.
The later independent implementation review found the generation gap above and
required cost reporting to distinguish deduplicated status scans from extra
integrity reads performed by freshness/fact/position access. Both are acceptance
requirements; the earlier design review did not establish their correctness.
