---
owner: lead
review_trigger: Admission-refusal certification, staging/collection or settlement-clock semantics change
status: historical
date: 2026-10-24
scope: Adopted request receipt and measurement boundary; source and actual gameplay evidence are separate
---

# Truthful refusal and measurable settlement

Parent: [player interface](../components/player-interface.md) and
[mission execution](../components/mission-execution.md). [#207](https://github.com/CVX-Hull/enactive/issues/207)
and [#208](https://github.com/CVX-Hull/enactive/issues/208) own delivery. Current
protocol/component views own the implemented contracts. The system roles,
single writer, native input and memory architecture remain unchanged.

The [Fresh024 review](../acceptance/2026-10-24-fresh024-execution-review.md)
locates missing request completion clocks. [Diagnostic001](../acceptance/2026-10-24-native-text-overflow.md#failed001-and-context-follow-through)
locates a rejected Launch whose staged ID led to nonexistent-operation collection.
The [execution-first repair](../acceptance/2026-10-24-execution-first-offline.md)
is already delivered; another tier/store or serialization rewrite is not justified.

## Admission receipt

Use a closed `mission-refusal/1` record in the response's `admission_refusal` field:
`schema`, `mission_id`, `request_id`, `request_sha256`, `admitted=false`,
`grants_authority=false`. The digest is SHA-256 of the exact validated canonical
request. The existing authenticated HTTP response supplies receiver provenance;
this is not a signature, durable receipt store or input authority. Reason remains
ordinary bounded response feedback. Shared pure builders/validation live beside
the existing mission contracts; no new parser or dependency is required.

The initial certified ledger branches are explicit new-request mission/epoch,
admitted skill/lifecycle-operation and lifecycle identity refusals, after its
existing prior-ID check and before insertion. A dedicated typed exception leaves
the existing SQLite transaction rolled back. Duplicate identities, budget/storage
exceptions and arbitrary errors are not converted to that type. The writer may
also certify its two explicit before-admission prompt/Observe refusals only after
positive exact `RequestNotFound` and non-cancellation checks; storage/other ledger
errors are not absence. The final cancellation check, response assignment and
ready signal are atomic under the same metadata lock as timeout/Pause; that work
then ends without execution. Never certify a timed-out admission wait, generic server/parse error,
missing/lost response or a post-admission failure. No claim of healthy authority
follows from a known refusal; current Pause/epoch/source checks still govern.

The client validates the complete closed receipt against its staged canonical
request. A valid certificate resolves this invocation as `submission=not_admitted`,
`settled=true`, retaining the assigned ID and immutable stage. It does not replay,
remove the stage or renew resources. The player may deliberately choose a NEW
request through the usual software-assigned identity. Reusing an existing stage
remains collection-only, including after restart when the response is unavailable.
Absent certificates keep current behavior; malformed/mismatched ones retain
uncertainty and the original collection identity. Existing busy-owner hints do not
become another certificate format.

Tools/MCP present the refusal reason, current context and next decision without
request digests or a phantom collection instruction. Raw SDK evidence remains
available before projection. Unexpected errors after staging retain original
collection obligations unless a validated refusal was actually returned; a generic
formatting/transport error cannot create nondelivery proof. No new gameplay
approval or critic round trip is introduced.

## Settlement timing

Use the existing controller journal, not a new database schema, timing store or
background service. One event per original admitted semantic work item records
its exact request/mission/epoch, controller boot, original ledger admission wall
clock, process-monotonic receipt/admission/settlement clocks, final observed row
state and available source identity. Do not copy full request/results/images into
that event. Cached collection, repeated submissions and passive reads do not emit
another settlement. Individual program primitives keep their existing lane.

Receipt begins at the runtime's newly created work handle; admission clocks bracket
the actual `begin_request` call. Settlement ends after that writer invocation's
post-commit work AND its per-work finally publication/handle cleanup. It is not the transaction commit,
client collection, native ACK, physical display, interpreted task success or model
inference endpoint. Atomic handoff/claim/Observe closure and Finish use the same
writer-finalization hook; cancellation/unknown/failed work records its actual row
or an explicit censored/unknown state. Row state, writer-finalization success or
censoring, and observed mission phase remain separate: a completed Finish result
can coexist with withheld terminal persistence. No historical endpoint is fabricated.

Process-monotonic durations only compare matching boot/operation samples. Wall
anchors remain labelled, with missing or discontinuous correspondence explicit.
Existing operation/source/session/revision/frame records support later joins;
current source at settlement is not automatically a useful effect. A small passive
reducer in the existing evaluation module may summarize these events and omissions;
there is no new trace framework or model annotation task.

A journal-only option on the existing writer excludes samples from the recent
status/UI event ring. New timing is non-authorizing telemetry. An unavailable timing append is retained
as a diagnostic/missing sample and cannot rewrite a committed operation or revoke
healthy input. Existing required domain persistence/journal failures retain their
current behavior. Reuse the journal's configured write contract, add no per-primitive
fsync or repeated source verification, and measure this event's overhead before
claiming it is negligible. Machine timing stays outside default player context.

## Delivery and qualification

Lead owns contracts, typed ledger refusals, runtime, timing/reducer and docs. One
worker owns disjoint SDK/tools/MCP/projection and focused tests after contract
review. Both checkouts start from `3be9fa6`; only the lead integrates. Shared native,
saves, ports and caches remain inactive during source work. At most one deciding
player and one optional adviser are later admitted under a fresh finite brief.

Prove exact no-row/no-input refusal and explicit correction, malformed/mismatched
proof, duplicate ID, response loss, admission timeout and admitted-result negatives
through existing real HTTP/SQLite fixtures. Prove single settlement coverage for
ordinary, atomic, Finish/cancellation and unknown paths, no duplicate read events,
clock missingness and telemetry-failure isolation. Use focused feedback before
one coherent independent review/full source PR/appropriate main check. Update the
protocol, affected component/evaluation/guide references together; no compatibility
path, unrelated hardening, global setup or new paid provider.

The user's Launch authorizes a later frozen independent useful-play assessment,
after source checks. Define the useful-decision cohort, numerical quality/cadence,
exceptions, finite attempts/resources/ending reserve and stopping policy before
play. Require organic procedure reuse/correction, substantive fresh-context memory
application, useful play during claimed advice and normal lifecycle; no lead
curation, scripted filler or task-success inference from ACKs. Retain failures and
costs. This assessment informs the next seven-day forecast, not seven-day acceptance.
