---
owner: maintainer
review_trigger: Changes to this interface, its callers, persisted formats or authority boundary
status: active
---

# Bounded injected planner

[`PlannerPort`](../../harness/gameplay/planner.py) belongs to one immutable TaskSpec.
Construct it with `PlannerConfig`, a trusted provider callable and the original
`admission_monotonic` in seconds. This is the same admission origin used by
[evaluation](../evaluation.md), with explicit seconds-to-milliseconds conversion.
Construction and delayed first submission do not restart the task clock. The first
invoked request pins the exact start EvidenceRef; continuation cannot replace it
or replenish the original turn/call/time/spend ceilings.

`PlanningRequest` supplies typed task/evidence, accepted skill descriptors, exact
plan/version/epoch, expected outbound/return stage, remaining distance and bounded
public context. The caller owns route progress and capability truth. The provider
receives immutable serialized `ProviderInput` and a cooperative cancellation event,
then returns `ProviderReply(candidate_json, usage)`. It receives no controller or
filesystem handles. Trusted Python injection is not an isolation sandbox.

`submit` reserves cost before invocation and returns a unique call ID. `poll` takes
that ID and the caller's current `PlanningBinding`; mismatches permanently discard
applicability. Candidate JSON must satisfy the existing PlanCandidate schema,
binding, supplied skill/version and exact route semantics. Success returns data,
never permission to dispatch. `cancel` and `close` invalidate pending/completed
candidates; close returns without waiting for a stuck provider. No automatic retry,
restoration or model selection occurs. The runtime supplies the external-chat
provider; deterministic fixtures remain test-only.

| Limit | Contract |
| --- | --- |
| Concurrent/lifetime calls | One physical call; at most ten lifetime calls per port |
| Context/reply | At most 1 MiB each; defaults 1 MiB / 16 KiB |
| Input/output tokens | Network/fixture declared bounds at most 1,048,576 each; defaults 32,768 / 2,048. External chat usage is unmeasured and not enforced by this adapter; bytes are not token estimates |
| Supplied capabilities/context | At most 32 descriptors and 4096 public-context characters |
| Uninvoked rejections | Last 64 audit entries plus total/dropped counters |
| Deadline | At most 30 seconds per call, further limited by task and remaining budgets |

A timed-out call retains the physical slot until its provider exits, preventing
thread accumulation. Deadline, cancellation, close and stale bindings win over late
results. Provider completion is recorded separately from the stop and financial
settlement timestamps. Unknown cost does not keep an already completed call's
measured duration running.

Network mode requires declared credential availability, bounded pricing and a
positive operator-approved spend ceiling/reservation. Missing prerequisites reject
before invocation. These are adapter declarations, not credential discovery or a
billing-system guarantee. External mode requires zero API reservation/spend; it
enforces byte/call/deadline/gameplay bounds but cannot measure or cap the surrounding
Codex chat usage. `external-unreported` explicitly marks unavailable model provenance;
`external-chat-v1` identifies the adapter configuration. Usage fields remain null,
not fabricated zero tokens or subscription cost. Missing cost
or malformed/contradictory usage retains the reservation; valid actual cost can
settle even when token metrics are absent. Over-bound raw usage freezes future
calls before evaluation sanitization. Representable overshoot remains visible;
unrepresentable overshoot is null with a reason. Failed and cancelled calls retain
late cost without reviving their candidate.

`snapshot(cutoff_monotonic=...)` returns immutable accounting and exactly one
`evaluation/1` event per invoked call. Uninvoked rejections stay separate. Record
one snapshot once, with other events in timestamp order. Later knowledge belongs
in a new named artifact; do not append repeated snapshots as duplicate model calls.
Unknown metrics carry reasons. A physically unfinished call is censored at cutoff;
a completed call ends at physical completion even if its reservation is unsettled.

## Passive task memory

[TaskMemory](../../harness/gameplay/memory.py) belongs to one immutable TaskSpec and
EvidenceStore. It retains source facts, explicitly non-factual interpretations
and hypotheses, candidate plans, versioned procedure/failure references and action
results as separate immutable views. It dispatches nothing, advertises no executable
skills and infers no task completion. The store alone retains original frames.

Explicit `refresh` can retain fresh facts; `snapshot` rechecks existing history
without promoting a new observation. Both and `retain_plan` require caller clocks;
snapshots describe that instant, not live authority. Source disputes invalidate
dependent records. Staleness, observation identity or store generation changes,
unknown/conflicting actions, task/session/epoch changes and capacity failures
invalidate candidates. Epoch advance preserves verified history. Task replacement
retires the instance; restart never restores memory or a lease from a journal.

Identical action IDs are idempotent; conflicts preserve the original and mark the
conflict. Recorded displacement must match referenced positions. Cross-session
after-evidence remains unknown context, never progress. Capacity is checked before
append: 128 facts, 32 interpretations, 32 hypotheses, 16 plans, 16 procedures,
32 actions, 64 KiB text including diagnostic reserves, 1024 chars per annotation
and eight source references. No silent eviction. Source-status scans deduplicate
up to the store's 32 frames; freshness/fact/position access may add targeted hash
reads. Retained-byte limits are storage limits, not total I/O measurements.

[Contract index](../protocol.md).
