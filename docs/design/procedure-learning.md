---
owner: lead
review_trigger: Procedure representation, reflection exchange, adaptation policy or source transfer changes
status: proposed
---

# Procedure memory and the advisory exchange

This records the selected implementation boundary for #177/#178 within
[delivery057](../changes/057-discovery-learning-campaign.md). It extends the
[organic loop](organic-discovery.md) and [reflection design](asynchronous-reflection.md),
not the number of game executors. The player chooses current plans, interprets
outcomes and accepts/revises procedure data. The lead maintains the substrate.
Claims and unfinished Work continue to describe the current campaign; a procedure
is advisory knowledge about how to attempt a goal under stated conditions.
The delivery brief and current protocol own implemented status and actual
qualification. Current source uses procedure/2, campaign-memory/5 and reflection/2
with native6/mission10/ledger12/archive5; gameplay/2 is unchanged. Admission uses
`facts-procedures-reflection/2`. Remaining research/evaluation proposals below are
not guarantees. The matching native6 build passed and is installed; graphical
qualification, a current-contract learning library and a fresh campaign remain
pending. Earlier learning004 evidence keeps its original environment and scope;
it is not silently mounted under the current contract.
Further design follows P-GENERALITY and the CDDA-class constraint: shared memory,
learning and advisory machinery must not depend on CDDA menu categories or world
rules. Game/configuration applicability stays explicit. Changing menus can
invalidate a procedure while ordinary exploration remains available; the player
and advisory path revise data from retained attempts, rather than requiring a
new engineering handler. #191 owns remaining substrate/portability gaps.

The [October23 executable-policy review](../research-executable-policies.md)
proposes an additional player-authored program path. It identifies a real gap:
current procedure/2 steps are advisory and are not executed as branches/loops.
The future boundary must distinguish stable platform code from evolving player
artifacts under a declared update policy, without per-routine lead approval.
That proposal does not change current admissions or executable behavior.

## Representation and storage

Reuse the existing strict JSON Schema helpers, canonical encoding, immutable
SQLite memory rows and bounded CampaignMemory projection. Do not store a second
trajectory. Source references resolve through the existing request/primitive
ledger and original frame archive; missing or disputed support stays unavailable.

| Record | Selected content and meaning |
| --- | --- |
| Procedure revision (`procedure/2`) | Stable family ID and immutable revision ID/number; expected parent revision; goal; named parameters/descriptions; applicability and invalidation conditions; closed-loop steps expressed as intent/expected observation/response to surprise; progress/termination and known limits; supporting and contrary episode references; candidate/active/disputed/retired disposition and explanation. Text is advisory data, never evaluated code or a ready-to-replay key macro. |
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
hashes/schema, finite records/bytes and closed source availability. Input-authority
revocation in an archive's bounded blocked-ID list does not invalidate otherwise
retained undisputed history; validate those IDs against retained entries and keep
all exports authority-free. Disputed support and integrity/closure failures still
refuse. Never copy old
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
two incomparable heads cause the pure linear-family projector to reject the
closure, so the integration cannot select a branch. The current schema offers no
branch merge or adjudicating-revision mechanism; no import-order, timestamp or
numeric revision tie-break resolves that rejection. Cross-mission revision
requires the exact admitted predecessor, with missing closure reported instead
of silently fetching new dependencies. Historical frame exports use this bounded
library resolver, separately from the current mission's existing source reader;
both verify original bytes and neither refreshes native state or authority.

## Bounded asynchronous work

Current job/proposal/command records use `reflection/2`; the closed schemas in
[reflection.py](../../harness/gameplay/reflection.py) own their exact shapes.
A job keeps its exact current request/result trajectory, request cutoff, accepted-memory version, at most8 qualified images
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
failure remains a fault. Finalization temporarily seals ingress and drains queued
commands; offered/claimed work becomes unreviewed/unknown with its original cost.
A canceled finish can reopen healthy nonterminal ingress without renewing old
work, including when the terminal ledger write refuses its original deadline.
Temporary sealing suppresses jobs but preserves bounded waiting/`idle`; only a
terminal phase or permanent writer shutdown reports `closed`. Actual host-actor
quiescence needs separate evidence, not an expired clock or a DB label.

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
be frozen in the implementation brief before affected worker dispatch. The
[mission and memory schemas](../../harness/gameplay/mission_contracts.py) and
[ordinary-input protocol](../protocol.md#ordinary-discovery-and-procedure-data)
own the current coordinated contracts. Delivery057's first October21 checkpoint
used campaign-memory/4 with native5/mission9/ledger11/archive4, procedure/1 and
reflection/1. Those versions describe historical run evidence only. Old runtime
and library inputs reject; no compatibility reader or relabeling of old procedure
environments is supported. A fresh finite current-contract learning run must
normally close before its pinned library is used in the fresh campaign.

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

## Pure procedure interface and exchange bounds

The October21 reviewed pure-module interface is implemented in
[procedures.py](../../harness/gameplay/procedures.py). Its current closed
`procedure/2` schema owns exact fields and bounds; the initial procedure/1 contract
is historical. The pure module imports strict schema/canonical helpers and has no
ledger/controller/runtime/network execution role.

`procedure_schema()` returns a defensive copy of the closed JSON Schema;
`validate_procedure(value)` returns a validated decoded copy; and
`project_procedures(records)` returns a mapping from family ID to its latest
revision, preserving full input history outside the projection. These functions
confer no input authority and do not certify truth or source availability. The
serialized runtime validates actual episode references, admitted library ancestry,
environment pins and update policy before persistence/retrieval.

A revision has an immutable mission-qualified ID and stable family ID, an exact
nullable parent and consecutive revision number, bounded descriptive procedure
content, environment pins, supporting/contrary episodes and disposition. Complete
linear ancestry resolves independently of input order. Identical copies dedupe;
changed copies, missing parents, multiple roots or incomparable branches refuse.
No branch selection or merge is inferred from timestamps or numeric revisions.

The current environment pins `engine_commit`, `native_protocol=6`,
`mission_schema="mission/10"` and a bounded configuration description. Matching
these identifies interface applicability, not equivalent world facts or a guarantee
that the described conditions hold. Episode references qualify request/source IDs
by their own mission; the runtime resolves original informing, entry, actual
preflight and after evidence through the ledger/archive rather than inventing a
second trajectory. Known ACK delivery, current input eligibility and semantic
success remain separate when interpreting support.

Each revision is at most32KiB canonical JSON and the pure projection accepts at
most256 records. The schema bounds parameters, steps, conditions and episode
references; omission accounting belongs to bounded context selection. No
current-world stock, position or input capability field is embedded in a procedure.
Structural validation cannot exclude semantic leakage through prose; player judgment
and source review remain necessary. Tests distinguish shape/lineage from truth.

Current admission and reflection schemas bound the exchange to at most64 jobs per
mission,2 pending including claimed work,32 request results and8 sources per job,
16 procedures,64KiB text input,32KiB output,180seconds per claimed job and
3600seconds aggregate charged wall time. Admission may select lower limits; these
upper bounds grant no authority or promise sufficient compute. Passive waits are
at most15seconds without game-input/MCP-handle/database write locks. Stable
job/command IDs, original receipt/deadline checks and durable writer transactions
are implemented by the existing advisory exchange. No unbounded retry, automatic
input, replaced queue or silently reviewed backlog follows.

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
advisory agent keeps its bounded wait while finalization is reversible. A
terminal mission phase or permanent shutdown supplies the `closed` cutoff through
its next-job call, after which it quiesces; temporary sealing alone supplies no
termination signal. Late bodies receive an explicit closing/closed refusal, not a
new accepted memory revision. Retain original claimed-time/known elapsed/unknown
remaining computation separately; no refund or fabricated exact model duration.
Verify advisory quiescence before final controller/storage closure and immutable
library hashing. If computation cannot terminate within its declared bounds,
record the actual host failure and close the attempt honestly. After permanent
closure and verified actor quiescence, library ledgers are immutable; no late
proposal write is allowed. Temporary sealing is not that archival boundary.
