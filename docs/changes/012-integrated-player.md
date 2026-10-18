---
owner: lead
status: historical
date: 2026-10-18
scope: Reviewed round012 integration brief and frozen allocation; accepted behavior and limits are recorded in the linked report
---

# Integrated player and spectator

## Outcome and size

From main `ca92dac431b6a18a9cbaea19dd5b515bc7c17bdf`, deliver one usable
waypoint-and-return path: explicit start, a capable player proposing each leg,
guarded execution with retained evidence, visible progress, Pause and explicit
continuation. This round joins the remaining integration in #36 with spectator
#23. It is a larger delivery outcome, with bounded disjoint implementation briefs;
component completion alone does not finish the round. #24 retains comparative
model experiments; #10 retains broad-objective task formation and survival.
The bounded runtime allocation is [#52](https://github.com/CVX-Hull/cdda-player/issues/52).

Two implementation allocations, one integrated candidate and one native acceptance
session avoid repeating publication and runtime setup for each internal seam.
Provisional aggregate effort: 4–7 focused sessions including review/rework and
native acceptance, Low confidence because real planner latency and revalidation
are new. This is not a calibrated time forecast. Split implementation ownership,
not the user-visible acceptance; keep aggregate issues outside Ready until their
bounded work is accepted. No additional model tier, hosted service or global setup.

## Player arrangement

The user selected this active Codex chat instead of a separately billed model API
and approved documenting a dedicated player sub-agent. The lead coordinates the
project, owns the shared runtime, admits tasks and verifies acceptance. One player
sub-agent reads bounded public observations and answers planning requests. It may
submit candidates through the planner endpoint; it may not start/continue tasks,
resume, send game inputs, operate native UI, modify source/saves, or launch a game.
The service alone admits and executes actions. The lead can answer the same
external interface when needed; these are callers of one contract, not alternate
compatibility paths. No automatic fallback to a different player or API.

Start the player only for an explicitly admitted bounded session and stop it when
that session ends. Give a clean brief with task, endpoint, retained frame references,
allowed operations, deadline and stop conditions. Keep gameplay context separate
from engineering logs. Use the existing capable model; role separation does not
establish that a smaller model is useful. Record the actual model/configuration when
known, otherwise mark it unmeasured. Harness API spending is zero; Codex usage,
full token consumption and subscription cost are not measured by this adapter.

Add the explicit PlannerConfig/ProviderInput mode `external` alongside the existing
fixture and separately gated network modes. External mode accepts only zero API
reservation/spend and does not claim to enforce the external chat's token usage;
request/reply bytes, call count, wall deadlines and gameplay budgets remain enforced.
Use model identity `external-unreported` when actual model provenance is unavailable
and configuration `external-chat-v1`; these are explicit unmeasured provenance,
not a model name inferred from the Codex application. ProviderUsage fields remain
null and evaluation keeps its existing missing-metric reasons. No evaluation
schema migration is needed merely to use these valid identity strings. A fixture
cannot be labeled external or used to claim model acceptance.

Sub-agent instructions are advisory: agents inherit session permissions. Controller
lease, schema validation, bounded task, native admission and Pause remain the
enforced boundary for the normal interface; do not claim OS isolation from a role.
A separate persistent Codex session may be reconsidered for independent user-owned
conversation/lifecycle needs, not merely to obtain parallelism. A stopped chat or
missing player yields a bounded planner timeout, never fabricated plans or retries.
This follows the context-separation and coordination tradeoffs in the current
[official sub-agent documentation](https://developers.openai.com/codex/multi-agent),
read 2026-10-17; it is a project design choice, not measured gameplay superiority.

## Frozen service boundary

New `harness/runtime.py` owns `GameplayRuntime(controller)`. The gameplay package
remains passive and cannot import the controller/server. Runtime exposes
`command(kind, **payload) -> dict`, `status() -> dict | None`, `pause(reason)` and
`close()`. Construction starts no task and acquires no lease. A single serialized
run worker starts only on explicit admission; it owns supervisor/store/provider
and the exact controller lease. No task/authority restoration after restart.

HTTP adds authenticated `POST /api/gameplay` with existing host/origin/token/body
limits and exact fields. CLI adds `gameplay-start DIRECTION --distance N --expect
SESSION:REV`, `gameplay-continue RUN_ID --epoch N --expect SESSION:REV`,
`gameplay-abandon RUN_ID --epoch N`, `gameplay-request`, and
`gameplay-plan REQUEST_ID --candidate PATH`. Plan files contain one gameplay/1
PlanCandidate; unknown fields/versions reject. The existing goal remains record-only.

Operations and JSON fields after `kind`:

| Kind | Required fields | Meaning |
| --- | --- | --- |
| start | direction, distance, expected_session, expected_revision | Construct immutable task from current observed origin; distance 1–4; default existing budgets |
| continue | run_id, execution_epoch, expected_session, expected_revision | Same task/history/original budgets, fresh checkpoint, new epoch and lease |
| abandon | run_id, execution_epoch | Pause and retire that exact run; unresolved effects remain unknown |
| planning_request | none | Return pending bounded request or null; read does not refresh a deadline |
| plan | request_id, candidate | Supply one candidate for the exact pending request; reject duplicate/late/stale responses |

Runtime-dispatched responses use `status: accepted | rejected`, optional error, `gameplay` snapshot,
and `planning_request` only for that read. The immutable external request contains
`request_id`, `deadline_ms`, and `input` (decoded ProviderInput.request_json: task,
packet, skills, binding, public_context, admission_monotonic). It contains no lease,
credentials or arbitrary executable tools. Candidate reasons are public concise
justifications, not private reasoning. Request consumption is at most once.
HTTP ingress failures retain the existing status codes and error-only envelope
(host/origin/auth/body/schema errors); clients handle both layers. `pause(reason)`
returns the ordinary controller `pause_requested` result; `close()` returns None.

`/api/status` adds `gameplay: null | {run_id, task, run, planner, last_receipt}`.
`task` is TaskSpec.to_dict(); `run` is RunStatus.to_dict(), with actual lease owner,
pause and next check supplied by the runtime. `planner` contains `kind:
external_chat`, `pending_request_id`, `deadline_ms`, and `usage_known: false`.
`last_receipt` is null or `{logical_action_id, native_request_id, disposition,
reason}`. Historical progress remains visible after stopping. No false idle state
while a native request is outstanding. Status reads do not execute gameplay.

Pause must revoke controller authority synchronously without waiting for the run
worker or model. Signal supervisor invalidation for serialized processing. The
ordinary Pause endpoint and shutdown use this path; native takeover, recovery,
world change and lost lease are detected before any further dispatch. Completion
releases the lease and leaves the controller paused. Continue never resumes the
transport implicitly. Unknown pending effects prohibit task continuation.
Completed/stopped tasks remain inspectable until explicit abandon; starting a new
task requires the prior run to be abandoned and its worker finished. No implicit
discard of retained task state. The existing recovery ingress keeps its own
generation-bound controller revocation; do not insert an extra Pause that would
invalidate the operator's supplied recovery generation.

## Native receipt and evidence

Extend the sole `execute_run` contract with required `logical_action_id` and
`deadline_monotonic` (absolute minimum of the original task and intent deadlines), and return
an explicit envelope: `logical_action_id`, `request` (exact native action admission
or null), `result` (controller/native result), `published` boolean, and
`received_monotonic` (actual first terminal response receipt or null). All callers
and tests migrate together. Preflight Observe is never an action receipt. Capture
the native request ID at admission, before publication; retain logical/native
mapping and receipt in the run journal. Do not reconstruct mappings by scanning
the last event or assuming the last Observe UUID was the action.
Check the absolute deadline after queueing, after preflight Observe and under the
publication lock; bound preflight/action waits and native deadline by remaining
time. No new full timeout after preflight. Known expiry before publication cannot
be an unknown action. Add `observation_snapshot()` returning an atomically copied
current observation and its original first receipt monotonic time; repeated reads
cannot refresh that time. The runtime uses it for initial and refresh ingestion.

Reserve EvidenceStore after-frame capacity before input; validate live intent,
original deadline, lease, current evidence and budgets again at dispatch. Ingest
only actual validated native frames with original receipt clocks, then settle the
exact intent once. Definitive nonpublication is not_dispatched; exact native
rejection is rejected; published/malformed/timed-out/unattributable results are
unknown. A returned observation in another world is not movement proof. Preserve
unknowns and never retry. Release reservations only on known nondelivery; retain
raw error/menu/activity receipts even when they cannot enter normal-play evidence.

## Slow planning and explicit revalidation

The three-second input evidence limit remains. A planning packet may become
historical while its bounded call is outstanding. Do not run the supervisor's
fresh-input checks against it repeatedly and thereby force sub-three-second
reasoning. On a candidate response, obtain a fresh Observe before admitting input.
Planning status must also avoid the invalidating `EvidenceStore.current()` path
when merely reporting an aged source. Add a non-authorizing evidence inspection
method for truthful freshness/status; ordinary age reports stale without changing
authority generation. Integrity disputes still invalidate. Exercise repeated HTTP
status reads during a plan older than three seconds. Runtime status/pause reporting
must not wait for a native exchange; keep a serialized worker snapshot or a short
metadata lock that is never held across I/O.

Add an explicit supervisor planning revalidation operation. Validate original
request/task/epoch/deadlines and retained source integrity; require same native
session, revision, turn, position, boundary/control identity, actions and complete
visible scene, plus identical retained frame pixels/hash. The new observation must
be fresh, normal-play, unpaused and pass current movement guard. Accept exactly
the single evidence-generation advance caused by this refresh, with no intervening
invalidation. Record old/new evidence and the equivalence decision. The candidate
keeps its original binding; it is never rewritten to match changed state.

If equivalence fails, stop with an explicit reason and require continuation/replan;
do not silently rebind. Revalidation does not renew task/planner budgets, replace
start/waypoint history, or authorize dispatch without the lease. Native/controller
checks still run immediately before the action. Test planner delays beyond three
seconds without weakening freshness, and changed frames/state even when revision
is unchanged. Fixture planning remains test-only, never the production player.

## Parallel allocation

After independent brief review, freeze a base commit and create two project-local
worktrees. Worker A owns `harness/runtime.py`, `harness/controller.py`,
`harness/gameplay/planner.py`, `harness/gameplay/supervisor.py`,
`harness/gameplay/evidence.py`,
`tests/test_gameplay_runtime.py`, and the corresponding existing controller,
planner, evidence and supervisor test files. It owns lifecycle, external inbox, exact receipt
binding and explicit planning revalidation. No server/UI/CLI/docs edits.

Worker B owns `harness/server.py`, `harness/__main__.py`, `web/`,
`tests/test_server.py`, `tests/test_cli.py` if needed, and `tests/test_viewer.cjs`.
It implements the frozen HTTP/CLI boundary and spectator using a fake runtime
at its boundary until integration. No core/runtime/gameplay/docs edits.

Both use the existing project Python read-only with PYTHONDONTWRITEBYTECODE=1,
isolated temporary fixtures and no shared game/build/save/bridge/port/cache writes.
The lead owns docs/diagrams, integration, full checks and native acceptance; an
independent clean-context reviewer audits combined authority/races and test evidence.
Escalate after two failed repairs or ownership drift. Worker commits name checks,
failures, limitations and unresolved questions. A player sub-agent is a later
planning-only role, not a third implementation writer or runtime owner.

## Acceptance and publication

Portable checks cover full two-leg completion, slow planning plus explicit fresh
revalidation with repeated status reads, stale/duplicate/late plan rejection,
expiry during blocked native preflight before publication, concurrent start, Pause during
planning and outstanding input, exact receipt mapping, preflight rejection versus
unknown action, capacity failure before input, fresh continuation without replay,
original budgets, world changes, shutdown and restart without authority restoration.
HTTP/CLI validation includes token/origin/schema/extra-field rejection. Viewer
tests and ordinary-window inspection cover planning, progress, stop/unknown,
staleness, evidence references and unavailable cost metrics. Keep Pause visible.

Run `.venv/bin/python tools/check.py`; inspect integrated diff and independent
review. Lead verifies unchanged native source/binary provenance, starts the prepared
windowed wrapper and captures a real short outbound/return using actual player
candidate responses, matching action receipts, frames and spectator. Exercise Pause
and rejected stale candidates; continuation proves retained progress where feasible.
Keep failed/censored attempts and portable/native/model-efficacy lanes distinct.
No claim of unattended survival or measured model efficiency from a short demo.

Update current architecture/protocol/overview/runbook and one responsibility visual
together; keep work.md navigation-only. Publish dated exact-candidate acceptance,
protected PR and passing merged-main CI; reconcile Issues/Project and clean only
owned runtime/worktrees/branches. Revisit the player arrangement after this evidence
or when persistence, latency, context size, cost visibility or permissions change.

## Brief review

Independent clean-context review on 2026-10-17 found and resolved three gaps:
stale status polling must not revoke planning evidence merely for age; the original
dispatch deadline must reach controller publication; external-chat provenance and
missing usage require an explicit planner mode. Re-review found the corrected
interfaces ready for bounded implementation. This is design evidence only.

## Accepted outcome

[Round012 acceptance](../acceptance/2026-10-18-integrated-player.md) records the
combined implementation, independent review repairs, two real completed tasks,
Pause/continuation and the blocked first route. Current architecture/protocol own
shipped behavior; this brief is historical rationale and allocation evidence.
