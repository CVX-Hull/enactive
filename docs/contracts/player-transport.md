---
owner: maintainer
review_trigger: Changes to this interface, its callers, persisted formats or authority boundary
status: active
---

# Player transport and original result collection

The [MCP server](../../harness/player_mcp.py) reports its implementation version at
SDK initialization; its presentation is `player-view/5`, marked by `presentation_schema`.
Only typed historical-source/context reference fields and the context native hash
join the existing snapshot projection. Raw SDK/evidence is complete; opaque authored
data is not recursively filtered. Snapshot detail stays exact to its selected read.
Its tool arguments omit `request_id` and `wait_seconds`; old MCP payloads are
rejected, not translated. The adapter assigns one UUID to each invocation whose
imperative SDK request needs an ID, then uses existing immutable staging and
bounded submit/collection. Result waits are15 seconds; advisory next waits40,
retaining the existing per-job deterministic claim and original remaining window.
These waits are transport collection, not execution budgets or renewed authority.
Positively matched, delivered unfinished input returns a software-derived
`next_call` to collect its original mission/operation; uncertain or mismatched
response bodies cannot redirect collection. A delivered busy input refusal reports `input_owner_operation_id`; the
SDK marks that new input `input_admission=not_admitted` and targets the actual
owner for collection, never the rejected invocation. In-progress images are
read-only partial evidence, not completed outcomes or permission for another
input. After collection the player explicitly selects current evidence; software
does not retarget the intended key. Guarded stale-selection refusal reuses the
current request-draft checks: verify retained support and healthy current custody,
then return blocked with zero proposals without input, refresh, lease/phase loss
or payload rewriting. Actual Pause, takeover, unresolved delivery, integrity and
global-limit faults retain their stopping paths. Lifecycle stale selection defers
to its existing specialized active/paused transition guard. Recovery cannot manufacture an
unknown-delivery candidate for a key that was never dispatched.
Invalid semantic whole-field creation-name targets use the same guarded local
draft refusal, retaining the strict complete admitted identity requirement.
Ordinary bounded input remains a separate explicit player choice; software does
not truncate a target, choose clearing keys or construct replacement chunks.
During a semantic whole-field edit, a returned clear of an interpreted nonempty
field that leaves byte-identical pixels stops the remaining replacement text for
fresh player interpretation. An interpreted empty field may have a no-op clear.
A changed image still does not prove the field cleared or the target was entered;
separate fresh interpretation is required before committing. Original charges,
root limits and authority remain unchanged.
Positively pure new mutation-preparation and pure advisory-submit validation
refusals before SDK submission return `submission=not_submitted` and no collection
handle; no new request exists to collect. Ordinary mutation refusal checks the
existing SDK stage for the assigned identity before making that classification.
An existing stage or corrupt/unavailable stage retains original collection and
uncertainty. Successful preparation needs no extra stage read. Submit, finish and
presentation errors stay outside that preparation boundary. Advisory closure lookup/validation must precede any
staging or POST; failures after that boundary retain original collection.
Errors from staging onward retain the assigned original collection identity. The
adapter never infers nondelivery from an arbitrary exception or a missing reply.
Exact selected snapshot/source, phase scope, finite execution limits and semantic
intent remain explicit. Neither a JSON-RPC correlation ID nor a new status read
replaces the selected evidence or original mission operation.

Assigned IDs and selected mission/reflector scope survive dispatch and presentation
errors as `original_collection` arguments, separate from the bounded error text.
An error alone establishes neither delivery nor nondelivery; a pre-staging failure
can leave no collectable operation. Pending/unknown work permits collection only,
not resubmission under a new UUID. Across producer restart, explicit original IDs
use existing durable SDK/ledger collection without snapshot/job caches. Status's
active-operation ID helps only while active; settled lost identities cannot be
recovered from it. Quiesce if the original identity is unavailable. No second
history/index, directory scan, automatic replay or blanket crash-recovery claim is
introduced. The imperative Python SDK retains explicit-ID requests for engineering
and exact duplicate collection; it is not another accepted MCP input mode.

StdIO returns one standard JSON text content block plus any typed image. It does
not repeat that value as `structuredContent`; SDK/HTTP canonical records and
selected detail remain available. Callers preserve text/image/error content once.
It copies canonical results without changing ledger records, HTTP contracts or
request bindings. The existing32-entry adapter cache retains each complete returned
snapshot (without PNG bytes or the already-excluded historical memory preview).
`enactive_detail(snapshot_id, section)` reveals its exact cached `configuration`,
`metrics`, `receipt`, `progress`, `native` or `source` subtree, with
`grants_authority:false`. It does no I/O, Observe, submission, refresh or cache
renewal. Missing sections return null; unavailable/evicted IDs require an explicit
new snapshot. The original selected snapshot never silently retargets. Actual
source images still use the existing exact source reader.
The separate source-metadata cache retains up to `MAX_HANDOFF_SOURCES` (128)
distinct reads, so one allowed Claim working set fits. Other snapshot/procedure
caches remain 32 entries. A source evicted from producer context requires an
explicit exact reread before an explicit source binding/declaration; it is not
proof that the image was never shown. Durable sources and read declarations remain
unchanged. No automatic source selection, reading or declaration is introduced.

Receiver-side uncertain effects use [delivery collection/reconciliation](delivery-reconciliation.md); [certified nonadmission](#certified-request-admission-refusal) has a separate correction path.

## Certified request admission refusal

An authenticated response with `status=rejected` may contain `admission_refusal`,
the closed `mission-refusal/1` record: `schema`, `mission_id`, `request_id`,
`request_sha256` (SHA-256 of the validated canonical request), `admitted=false`
and `grants_authority=false`. The pure mission-contract validator binds it to the
exact original staged request. This digest is not a signature or input authority.

Only explicit typed new-request policy refusals after the ledger's prior-ID check
and before insertion, or the writer's two specific prompt/Observe guards with
positive exact no-row proof, issue this receipt. A final cancellation check,
response assignment and ready signal share the timeout/Pause metadata lock.
Duplicate IDs, admission timeouts, budget/storage exceptions and generic errors
never become certificates. Existing busy-owner hints remain a separate bounded
collection aid, not another certificate format.

The SDK reports a valid certificate as `submission=not_admitted, settled=true`,
retains the operation ID/staged bytes and does not collect a nonexistent operation.
The player may explicitly choose a NEW request under unchanged original limits;
there is no automatic retry, deletion/refund or authority restoration. An existing
stage still permits collection only, including after restart without the response.
Missing certificates preserve the ordinary path; malformed/mismatched certificates,
lost responses and admitted failures retain uncertainty/original collection.
Tools show reason/current context and hide technical certificate fields from the
default model view. A formatting failure may preserve only an actually validated
known refusal; arbitrary staging/presentation errors prove neither delivery nor
nondelivery. No extra approval/reviewer runs on the gameplay path.

HTTP JSON uses Python's finite compact UTF-8 codec with the same encoding basis
as canonical bounded advisory contexts. Per-record parser caps do not become
aggregate spectator-status response caps; each client retains its own limits. A valid Unicode job and its offered/
claimed envelope must fit the unchanged client response cap; ASCII escaping and
pretty-print expansion are not extra admitted context. Request, job and transport
bounds remain separate checks. Serialization changes no job claim or authority.

[Contract index](../protocol.md).
