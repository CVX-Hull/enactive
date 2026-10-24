---
owner: lead
review_trigger: Local feedback cost, procedure authoring/selection or reflection scheduling changes
status: historical
date: 2026-10-24
scope: Adopted execution-first implementation rationale; current behavior lives in components and protocol
---

# Execution-first learning: implementation boundary

Parent: [current architecture](../architecture.md), especially
[mission execution](../components/mission-execution.md) and
[memory/learning](../components/memory-learning.md). GitHub
[#164](https://github.com/CVX-Hull/enactive/issues/164),
[#177](https://github.com/CVX-Hull/enactive/issues/177) and
[#178](https://github.com/CVX-Hull/enactive/issues/178) own delivery/status.
This brief freezes implementation decisions; it is not another task tracker.
The [execution-first proposal](../design/asynchronous-reflection.md#execution-first-learning)
and [research crosswalk](../research-multirate-agents.md) own broader alternatives.
Current contracts remain authoritative until each coordinated change lands.

## Purpose and constraints

Reduce time spent outside useful decisions and ordinary local execution. CDDA
remains normal human play: actual visible observations, ordinary interface input
and unchanged engine mechanics. No hidden-state advantage, save modification,
engine-validation bypass, menu catalogue or engineered winning trace is permitted.
One player chooses; one optional learner proposes; one writer commits. The lead
maintains the system without supplying tactics or curating play.

Gameplay, native probes and campaigns remain user-paused. This iteration uses
offline source, real retained data read-only and explicitly synthetic transport
fixtures. Those lanes cannot qualify graphical response, organic competence,
learning benefit or the independent seven-day outcome.

## First boundary: eliminate repeated metadata serialization

Fresh024's [read-only review](../acceptance/2026-10-24-fresh024-execution-review.md)
locates multi-second local intervals without intervening model calls. Separate
helper profiles at its final scale find manifest build/encoding about56ms, file
usage about20ms and primitive-history reads about28ms on this Mac. These are
component samples, not additive historical attribution.

A coherent synthetic Controller/MissionRuntime/EvidenceStore/SQLite fixture with
3,617 source-shaped historical entries and matching frame byte sizes yields three
ordinary-input samples around1.05s. Its current capacity/usage/persistence path
repeatedly builds the full manifest. The fixture supplies test-only identity and
synthetic marker frames; it never launches CDDA or modifies original evidence.
Existing cProfile and standard-library timing provide the measurements; no tracing
service or new profiler dependency is needed.

Selected change: EvidenceStore retains only an exact **canonical metadata byte
length**, lazily derived and invalidated on its serialized state changes. It
does not cache the payload, physical file sizes, source validity or authority.
Successful atomic persistence refreshes that length. Read-only usage/capacity
checks reuse it rather than reconstructing every historical entry each time.
Initial load starts unknown and derives canonical in-memory size, never the raw
manifest file length. Session/retirement, new entry, retention promotion and
blocked/disputed mutations invalidate before subsequent capacity checks. A failed
write cannot retain a pre-mutation cached size.

Use ordinary `os.scandir` and `DirEntry.stat(follow_symlinks=False)` for each actual
directory usage scan. Preserve indexed slots for missing files, orphan accounting,
nonfile refusal and real I/O errors. Selected-source hashing, capture freshness,
custody, reservations, durable intent/receipts, atomic writes and fsync remain.
This is a bounded derived scalar and a standard-library iteration improvement,
not a second store/journal or a relaxed archive-consistency contract.

No native, wire or persisted format changes are needed for this boundary. Lead
owns integration and the repeated offline profile. A worker owns only
`harness/gameplay/evidence.py` and `tests/test_gameplay_evidence.py` in a managed
worktree. Focused independent boundary review found no blocking issue; it required
noncanonical reopen, failed session transition, actual persistence failure and
scandir disappearance-race coverage. Existing selected-tamper/missing/orphan/
nonfile/capacity/reservation negatives remain required. A regression should show
read-only capacity queries avoid full metadata serialization, not assert a flaky
wall-clock threshold. Report before/after wall distributions separately.

## Authoring and selection boundary

A shared pure authoring helper derives canonical Procedure/3 from a closed
semantic schema, original admission environment, submission identity and explicitly
selected qualified parent. Both deciding player and learner use it. The learner's
parents come only from its claimed job's procedures; the player's direct parents
come from explicitly retrieved context. Semantic support, counterexamples and code
remain model choices. The existing writer owns source, environment and lineage
acceptance; there is no semantic certification or extra review gate.

MCP5.3.0 changes the sole model-facing advice contract to
`snapshot_id, proposal_index`. Null lists the latest four proposals using their
original indexes and compact candidate applicability/limits; an exact index reveals
full original detail. Candidate bodies are bounded SDK copies keyed by that exact
snapshot/index. Explicit `remember` with `entry_type=procedure_candidate` and its
proposal/candidate indexes submits that original canonical body, preserving its ID
for automatic proposal → adoption → use joins. It requires a prior advice read in
that SDK context. Eviction needs an explicit reread; indexes never follow a newer
snapshot. Reading is exposure, not proof of attention, applicability or success.

No canonical Procedure/3, reflection/2, mission/11 or persisted format changes are
needed. All model callers migrate together; old canonical candidate authoring and
old mission/proposal-ID model advice shapes reject. The explicit-ID engineering
MissionClient remains the same machine contract, not a compatibility model path.

The learner supplies semantics/code, selected parent and source support; software
supplies canonical metadata from the original admission/job. The player selects
an actually presented candidate without copying its canonical body. Adoption is
an explicit gameplay choice through the writer, with current lineage/conflict and
source checks; it is never a lead/reviewer approval or silent world-fact overwrite.
Expose compact relevant candidates and exact detail progressively.

## Horizon allocation and software waiting

Use `capacity=min(jobs,floor(total_seconds/job_seconds))`, with progress the maximum
clamped fraction of original wall span and spent input allowance. Routine earned
jobs are `min(capacity,1+floor(progress*capacity))`; urgent work may borrow one
future slot within capacity. This is a conservative full-window allocation policy,
not a renewal or a guarantee of useful inference. Routine work requires four
roots or original request age `min(job_seconds,wall_span/(capacity+1))`. The
capacity1/2 boundaries get an opportunity before the deadline. No game-state
measurement or maintained Work/Decision tree is required. Original job claims,
pending limits and charged wall windows remain independently enforced.

Select from all settled rows: reserve oldest/latest when space permits, then
oldest exceptions, then ordinary rows, restoring original chronological order.
Use the same priority while shrinking context for byte fit. Sources, procedures,
cutoffs and exact omission counts remain immutable. Summary distinguishes current
unreviewed rows from cumulative omitted rows; omitted evidence is not silently
replayed or called reviewed. This is bounded priority, not a promise that every
failure can fit. Cheap credit/count/age checks precede full history reads.

An optional frozen adviser-only profile holds an empty `reflect_next` in software
across existing finite passive polls. One initial status read obtains its original
mission/deadline; it is not a live Observe, though status can reconcile control
state. Later polls validate the same role/mission. A monotonic end is bounded by
both frozen profile window and original remaining wall allowance; no later status
can extend it. Non-idle claims/refusals/unknown/closure return unchanged. A
cancellation checkpoint precedes another poll; an in-flight transport/claim call
retains its existing finite bounds. Default deciding-player profile is unchanged.
Export via existing configure tooling without editing active/global settings;
`tool_timeout_sec` covers the finite profile window plus transport margin. This
uses documented [Codex MCP configuration](https://developers.openai.com/codex/config-reference/),
not a new agent scheduler. Actual frozen-host qualification remains paused.

Allocation must spread useful questions across the finite horizon, coalesce
routine work and retain exceptions, age, omissions and exhausted/absent-worker
states. Existing request/program roots are available; Fresh024 has no Work or
Decision rows, so no maintained subgoal tree may be assumed. Any needed intent
marker belongs at a meaningful selection boundary, with software-owned lineage,
not per-key narration. Do not add a learned scheduler, new event store or mandatory
model tier. Original limits and unknown no-replay remain independent of advice.

## Verification and artifact upkeep

The independent design review rejected a last-credit-at-deadline formula and
blind middle-row truncation; the selected rules above incorporate those findings.
Current components/protocol own implemented behavior; this brief retains rationale.
The [offline report](../acceptance/2026-10-24-execution-first-offline.md) owns timing
observations and limits. Broader organic usefulness and campaign gates remain on
the three parent outcome issues.

Use focused positive/negative and retained-scale checks during development, one
coherent independent integration review and required exact-head/merged-main CI
for publication. Preserve failed fixtures and qualify their limits. Update current
component/protocol/tool guidance when implemented behavior changes; retain this
brief as rationale afterward. GitHub owns stage, estimates, allocations and
remaining actual gameplay qualification. Existing S-ARCH/S-UX/S-CODE/S-MIGRATION,
C-REVIEW/C-PORTABLE/C-USABILITY apply without another per-action control.
