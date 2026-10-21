---
owner: lead
review_trigger: Procedure representation, reflection exchange, adaptation policy or source transfer changes
status: proposed
---

# Procedure memory and the advisory exchange

This is the proposed implementation boundary for #177/#178 within
[delivery057](../changes/057-discovery-learning-campaign.md). It extends the
[organic loop](organic-discovery.md) and [reflection design](asynchronous-reflection.md),
not the number of game executors. The player chooses current plans, interprets
outcomes and accepts/revises procedure data. The lead maintains the substrate.
Claims and unfinished Work continue to describe the current campaign; a procedure
is advisory knowledge about how to attempt a goal under stated conditions.

## Representation and storage

Reuse the existing strict JSON Schema helpers, canonical encoding, immutable
SQLite memory rows and bounded CampaignMemory projection. Do not store a second
trajectory. Source references resolve through the existing request/primitive
ledger and original frame archive; missing or disputed support stays unavailable.

| Record | Selected content and meaning |
| --- | --- |
| Procedure revision (`procedure/1`) | Stable family ID and immutable revision ID/number; expected parent revision; goal; named parameters/descriptions; applicability and invalidation conditions; closed-loop steps expressed as intent/expected observation/response to surprise; progress/termination and known limits; supporting and contrary episode references; candidate/active/disputed/retired disposition and explanation. Text is advisory data, never evaluated code or a ready-to-replay key macro. |
| Episode reference | Mission identity, existing request IDs and source IDs, plus the player's scoped interpretation where needed. Resolve actual requests, delivery/effects and original image support; no invented support or automatic success label. |
| Procedure selection | Explicit family/revision and use-instance ID attached once to a skill root, with the player's applicability judgment. The runtime resolves the exact retrieved version, validates it exists and propagates linkage to children. It does not infer mental influence or reselect a new revision mid-skill. |
| Context export | Exact packet/library revision and included procedure versions, with source availability, omissions and scope. Record supply by the runtime separately from host delivery/mental attention; no mandatory feedback narration per action. |
| Reflection job/proposal | Immutable input cutoff/request span, memory/procedure versions, bounded original sources and interpretation questions; stable work/result identity, declared limits, actual state/cost and omitted coverage. Candidate output is not accepted memory or an executable plan. |

Procedure conditions are bounded descriptive fields first, not a new predicate
language. Evaluate an exact supported predicate automatically only where existing
observation contracts support it; otherwise the active player judges applicability
and records uncertainty. An `active` disposition means selected advisory eligibility,
not verified universal correctness or calibrated confidence. Candidates remain
inspectable/testable under the declared adaptation policy.

Every revision is append-only. The serialized writer compares its expected parent
against the actual current family revision. Stale/conflicting proposals stay
proposals; no arrival-order overwrite. Retirement/dispute preserves lineage and
contrary evidence. A selected running instance retains its original version;
new advice affects a later selection or an explicit player-owned replan.

The current mission ledger owns newly authored revisions. For transfer into a
fresh campaign, admission explicitly identifies a bounded set of immutable closed
source ledgers/archives by mission ID and SHA256; only read-only validated advisory
records and their support are imported into retrieval. Do not reopen MissionLedger
as an actor or restore old phases/leases/queues. Missing support is visible and
cannot become current world truth. New revisions live in the new mission ledger
and name the selected predecessor. Original source history remains authoritative;
Git remains the source-code history, not a game-memory database.

Library source validation must enforce project-owned paths, no symlinks, exact
hashes/schema, finite records/bytes and closed source availability. Never copy old
inventory, map coordinates, identity or unfinished world Work into the new world
as facts. A procedure may refer to a scoped UI prerequisite while current evidence
still determines the actual source/target. Fresh-context transfer within a mission
must include required procedures and source coverage in the handoff fit check.

Freeze transitive closure explicitly: a revision's identity is its owning mission
plus immutable revision ID; episode request/source IDs are qualified by their own
mission. Admission lists at most4 source missions with exact ledger/index hashes,
including every predecessor and evidence mission needed by imported revisions.
Only the current schema is eligible as library input; old run formats remain
historical evidence, not a compatibility reader in live retrieval. The read-only
resolver derives paths from validated mission IDs beneath owned project storage;
it never accepts a caller path or opens an old ledger as a runtime actor.

Validate the complete bounded dependency graph, its source availability and
parent family/revision invariants before exposing an eligible procedure. Resolve
heads by ancestry, never import order or wall-clock date. Identical copies dedupe;
two incomparable heads make that family disputed/ineligible for selection until
an explicit player-authored adjudicating revision names the supported resolution.
No implicit merge or numeric revision tie-break. For this first implementation,
the pure linear-family projector rejects incomparable branches; the integration
may report that rejection without selecting a branch. Cross-mission revision
requires the exact admitted predecessor, with missing closure reported instead
of silently fetching new dependencies. Historical frame exports use this bounded
library resolver, separately from the current mission's existing source reader;
both verify original bytes and neither refreshes native state or authority.

## Bounded asynchronous work

The source checkpoint freezes`reflection/1` job/proposal/command records in
`harness/gameplay/reflection.py`. A job keeps its exact current request/result
trajectory, request cutoff, accepted-memory version, at most8 qualified images
and16 procedures, with explicit request/source/procedure omissions. Bounds remain
at most64 jobs,2 pending bodies (including a callback in flight),32 requests and
64KiB input per job,32KiB output,180s per claimed window and3600s aggregate.
SQLite job/command records use their own sequence; they never increment accepted
memory. A full conservative claim window stays charged, with observed elapsed
wall time recorded separately and actual model compute/tokens unknown.

The standard-library mailbox/Condition holds no input or database lock while
waiting. Only the existing writer drains short callbacks. Receipt time is captured
by software at ingress and retained separately from writer-drain time: a timely
submission must not become late because a game operation delayed bookkeeping.
Unknown computation and omitted/unreviewed work remain explicit. Exact cutoff/
source checks and immutable command/result correlation apply on reopen too.
The source implementation now integrates this mailbox with RegisteredReflection,
the existing writer/server and structured MCP tools. Four routine root skill
decisions coalesce work; failed/unknown results and recovery/handoff boundaries
can trigger earlier review. Context selection preserves original omissions when
interrupted results are absent or individual records cannot fit. Reopening
reconstructs pending coverage from the ledger. Actual official host integration
and nonblocking graphical play remain separate qualifications below.

Advisory claim/source/submit/result tools bypass the active-player lock and never
Observe. The result tool collects an original stable command without requiring a
volatile claimed-job handle. A committed semantic refusal is exposed with its
original reason; it cannot fault gameplay or become a claimed packet. Storage
failure remains a fault. Before terminal sealing, ingress closes and queued
commands drain; offered/claimed work becomes unreviewed/unknown with its original
cost. A canceled finish can reopen ingress, without renewing old work. Actual
host-actor quiescence needs separate evidence, not an expired clock or a DB label.

At admission assign one general-purpose advisory Codex agent, with no game-input
role, and freeze finite job/pending/context/source/output/time limits. The lead may
provide only its role/interface/references and initial assignment. Subsequent work
comes from software over retained data, without lead wakeups, transcript curation
or tactical messages. No paid API or permanently running daemon is assumed.

The existing mission writer owns short durable job/cursor/proposal transactions.
Model computation runs outside it. Reuse the existing HTTP server/MCP SDK for
bounded work retrieval/result submission. A passive wait must not occupy the
mission queue, PlayerTools' active-input lock or a database write transaction.
Use a cached immutable work view plus condition/wait; serialize short mutations
through the existing writer. The actual host must demonstrate concurrent player
and reflector calls before nonblocking operation is claimed.

Software prepares work at semantic completion/exception boundaries, using bounded
segments of existing request results, selected procedure linkage, corrections and
unfinished obligations. It does not request reflection per primitive. Coalesce
pending work within the declared bounds and retain skipped/unreviewed coverage;
newer failures must not silently erase an older obligation. Reflection bookkeeping
does not recursively trigger more reflection.

The advisory agent consumes a structured immutable packet, reads selected retained
images without native Observe, and returns source-linked procedure/correction/
warning/question candidates. It cannot mutate accepted memory or issue game input.
The active player reads advice at meaningful decision boundaries and can accept,
defer, reject, revise or dispute it. Acceptance passes ordinary version/source/
update-policy validation, not an engineering/model approval round trip.

Use stable job/result IDs and compare the exact original cutoff/version. Duplicate
delivery returns the original result; conflicting bodies refuse. Lost computation
may become expired/unknown work, never an instruction to replay game input.
Late advice remains attached to its original evidence and is rechecked before use;
do not restamp it with a new frame. Worker absence, timeouts and exhausted reflective
budgets are visible and cannot stop otherwise justified routine play. If the player
has no justified next action, it reasons/observes/stops deliberately rather than
sending Wait merely to appear busy.

## Automatic feedback and limits

The root selection plus existing requests/primitives/sources provides automatic
attempt, delivery, observed supported progress and cost linkage. Known refusals
and independently settled unknown effects retain original statuses. Ambiguous
semantic success needs a marked player/learner judgment, not an invented software
label. Extra explanation is optional at meaningful boundaries, never required
after each action. Unselected advice is not proof it was read or ignored.

Freeze named adaptation rules: procedure DATA may be proposed/tested/revised/
retired under current source/version checks; code, templates, weights, substrate,
input permissions and budgets cannot self-modify. Existing no-online-promotion
historical admissions stay unchanged. Source integrity, user Pause, single-writer
ownership and unknown no-replay remain immediate, independently of evolving advice.

Use explicit finite limits, not an unbounded learner. Exact per-record/API shapes,
numeric bounds, scheduling/claim semantics and cross-ledger validation tests must
be frozen in the implementation brief before affected worker dispatch. The current
proposal is not a schema implementation. Migrate campaign-memory4 with the shared
native5/mission9/ledger11/archive4 change; old runtime inputs reject, historical
artifacts remain evidence. Do not add a compatibility reader to the live path.

## Acceptance, controls and maintenance

Focused tests cover strict records and bounds, actual source references,
cross-world fact exclusion, missing/corrupt support, revision conflicts/retirement,
root/child selection linkage, retrieval omissions and handoff coverage; job
duplicates/late results/worker loss/coalesced coverage; concurrent play while work
waits; no reflective Observe/input/Resume; unchanged Pause/budget/unknown behavior.
Use real ledger/runtime/MCP components for integration, not only pure-model mocks.

The graphical mission must demonstrate actual player-derived abstraction, distinct
reuse, meaningful counterexample revision and fresh-context application while
useful play continues with advice pending. A source test, stored transcript,
engineered popup handler or fluent reflection cannot satisfy that outcome.
Follow with the independently assessed fresh seven-day campaign. Record latency,
retrieval/reflection/tool costs and unavailable metrics honestly; functional
success is not causal learning benefit or a transfer/convergence theorem.

Lead owns integration and maintenance through existing S-ARCH/S-WORK/C-REVIEW and
source/native/graphical lanes. Reconcile prior offline-only promotion proposals
prospectively, keep authoritative contracts truthful during implementation and
review library/worker cost and usefulness at actual campaign findings. Retain
counterexamples and retire superseded assumptions instead of rewriting history.

## Candidate pure-module interface

The following bounded pure interface was accepted after independent design review
on October21 and is frozen for the disjoint procedure worker. This does not freeze
or implement the remaining runtime/transport migration. The worker owns only
`harness/gameplay/procedures.py` and `tests/test_procedures.py`. It imports existing
strict schema/canonical helpers, never ledger/controller/runtime/network code.

`procedure_schema()` returns a defensive copy of one closed JSON Schema;
`validate_procedure(value)` returns a validated decoded copy; and
`project_procedures(records)` validates a bounded sequence of revisions
and returns a mapping from family ID to a decoded copy of its latest revision,
preserving full input history outside
the returned projection. These functions confer no input authority and do not
certify semantic truth or source availability. The lead validates actual episode
references, authorized library ancestry and policy before persistence/retrieval.

The revision fields are `schema="procedure/1"`, `record_type="Procedure"`,
`id`, `mission_id`, `procedure_id`, `revision`, nullable `parent`, `goal`, `parameters`,
`applicability`, `invalidators`, `steps`, `progress`, `stop_conditions`, `limits`,
`environment`, `support`, `counterexamples`, `status`, and `reason`.
IDs use the current bounded ASCII ID shape. `mission_id` owns this revision;
`parent` is null or the exact object `mission_id`/`revision_id`. The family ID is
stable across transfer and cannot be independently recreated with a second root
inside the admitted closure. Revision is1–1024, starts at1 with null parent, and
advances exactly once from the current family's qualified ID/revision. A qualified
ID is immutable; identical repeated copies dedupe, changed copies refuse.
Conflicting/stale parent or duplicate revision refuses rather than overwriting.
Resolve the complete graph by ancestry regardless of input/import order; a
reversed complete sequence returns the same head, while missing/cyclic closure
refuses. Input order is never a version or conflict tie-break.

Goal/reason/condition/progress/limit text is at most1024characters. Parameters are
at most8 unique names with `name`/`description`; steps are1–16 objects with
`intent`/`expected`/`on_unexpected`, each at most1024characters. Applicability,
invalidators, progress, stop_conditions and limits are lists of at most8 bounded
strings; applicability/progress/stop_conditions require at least one. Status is
candidate/active/disputed/retired. `environment` contains exact pinned
`engine_commit`, `native_protocol=5`, `mission_schema="mission/9"` and a bounded
`configuration` description. Matching this identifies interface applicability,
not equivalence of world facts or a guarantee every described condition holds.

Support and counterexamples each contain at most8 episode objects with
`mission_id`,1–16 unique `request_ids`,1–8 unique `source_ids` and bounded
`interpretation`. Support requires at least one episode. No current-world stock,
position or input capability field is embedded in a procedure. The schema can
enforce that structural separation; semantic leakage through prose still requires
player judgment and evidence review. Each revision is at most32KiB canonical JSON;
the pure projection accepts at most256 records and refuses exceeded bounds.
Omitted retrieval is handled by the lead's bounded context selection, not silently
discarded by this function. Unit tests must distinguish shape/lineage from truth.

The candidate exchange bounds are at most64jobs per mission,2pending including
claimed work,32request results and8sources per immutable task,64KiB text input,
32KiB output,180seconds per claimed job and3600seconds aggregate charged worker
wall time. These are upper bounds for prospective admission selection, not current
authority or a promise of sufficient time. Passive work waits are at most15seconds
and hold no game-input/MCP-handle/database write lock. First issue/claim/result and
expiry retain stable IDs and original costs; the exact job claim/writer transaction
shape remains the lead's integration boundary to freeze before that implementation.
No unbounded retry, automatic input, replaced queue or silently reviewed backlog.

## Lifecycle ordering for advisory mutations

Use a bounded advisory-only ingress mailbox (at most2 result bodies) beside the
existing input queue. This is not a second executor: only the existing writer
drains it into SQLite between complete input operations. Receipt means queued,
not durable or accepted memory. The structured adapter stages the original body
and stable ID before submission and collects the original result. Duplicate
identical bodies return that pending/committed disposition; conflicting bodies
refuse. A known full mailbox returns an explicit zero-admission busy result with
finite backoff; only this advisory computation payload may be reoffered under the
same identity. No game input, lease, source or allowance is retried/renewed.

This avoids the current input queue's5second admission cancellation and prevents
an advisory result from taking the player's sole queued input slot. A worker
result produced before its computation deadline retains that receipt time while
waiting for the next writer boundary; waiting cannot extend computation limits.
The writer revalidates original job/body/versions before persistence. A crash
before commit leaves the original job/result uncertainty explicit; a mailbox ACK
never pretends the result is durable. New admission cannot restore an old job.

Job/proposal bookkeeping has its own sequence and cannot change CampaignMemory's
accepted revision, handoff packet hash or required-Work fit. During handoff,
procedure/Claim/Work adoption is frozen along with the issued memory snapshot;
advisory computation/results can remain scoped to their original job and become
available after successor readmission. They never acquire the successor epoch or
rewrite the packet. User Pause still revokes game input immediately; no proposal
or late result grants Resume.

At normal finishing, stop issuing/claiming new advisory work, drain already
received bounded results and record unresolved/expired jobs with their original
costs. Never wait for a late suggestion before saving/quitting the game. The
advisory agent sees the closed cutoff through its next task/result call and
quiesces; late bodies receive an explicit closed-cutoff disposition, not a new
accepted memory revision. Retain original claimed-time/known elapsed/unknown
remaining computation separately; no refund or fabricated exact model duration.
Verify advisory quiescence before final controller/storage closure and immutable
library hashing. If computation cannot terminate within its declared bounds,
record the actual host failure and close the attempt honestly. After sealing,
library ledgers are immutable; no late proposal write is allowed.
