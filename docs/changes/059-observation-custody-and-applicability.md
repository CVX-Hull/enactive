---
owner: lead
review_trigger: Observation custody, semantic applicability or source publication changes
status: active
---

# Observation custody and action applicability

## Outcome and evidence

Fresh campaign009 failed after 341 game seconds. A filter-confirmation input has
a durable, correlated ready ACK, but subsequent source publication failed the
comparison with a later controller observation. No day, handoff, midpoint reload
or normal ending is accepted. Both actors are FINAL; the failed world is archived
and the owned processes are closed. The admission is never renewed.

The exact second observation at failure was not retained. A deterministic
real-component source test reproduces the same stop by publishing a healthy next
menu between ingestion and binding. This establishes a source defect, not the
precise native interleaving. The general problem also affects Observe, semantic
entry refresh and status publication; fixing only the reported post-ACK line
would leave the same assumption elsewhere.

An actual observation is an immutable sample with an original receipt, not a
promise that the application will remain unchanged until storage or model work
finishes. Separate its provenance and uninterrupted custody from whether a
particular proposed action still applies. This extends [design058](058-capture-provenance-action-preconditions.md)
and the existing ordinary-input/explicit-observation paths; it does not invent a
menu taxonomy, a second state store or another executor.

## Selected boundary

Bind a verified captured source to the same live lease, actor/epoch, controller
and operator origin, session, takeover, native control and Pause origin. Validate
source and live capture health separately. A later healthy revision, boundary,
scene, UI or image does not itself invalidate the immutable source or prove an
integrity failure. Keep pending-work, original clocks, retained-byte integrity,
store generation, resource and dispatch checks. Do not replace captured fields
with the latest fields or renew the receipt.
Reuse the archive's revision/scene comparison for live integrity: future clocks,
regressed revisions and contradictory scenes at the same revision remain faults,
even on a zero-input path. Aged evidence may support a read-only refusal without
being promoted to fresh input authority. At acquisition, classify expected ordinary
context mismatch inside the existing controller fence before rotation; after its
locks release, prove complete runtime health before retaining Observe lineage.

Observe authenticates its actual returned capture and original receipt. A later
healthy controller sample may differ visually while retaining custody. The
latest retained source in mission status is an as-of sample, separately from the
spectator's native frame and its freshness. Its availability and next-decision
fields must agree; neither the source binding nor status grants input authority.

Semantic intent still requires its existing state/image equivalence. At entry,
perform the actual bounded refresh under custody rather than declaring a changed
visible state an integrity failure before refresh. If verified fresh evidence
does not support the intent, send no input, retain both observations and return a
local applicability refusal. Advance an existing prompt checkpoint only through
its observation transition; do not restore an old EvidenceStore generation. A
new physical or semantic choice belongs to the player.

If applicability changes later, reuse `MissionInputRefusal`, the existing complete
health proof and read-only explicit-Observe lineage. An expected refusal is
eligible only after every fatal custody, queue, clock, storage and global-resource
guard passes. Preserve any delivered prefix, original source, ACK, charges, root
and deadlines. Do not catch arbitrary `EvidenceError`, silently refresh/retry an
input, reinterpret a rejected key as success or authorize a remaining text batch.

Registered creation, identity, Save, handoff, activity, recovery and exit retain
their specialized transition, identity, exact-image/native-state, owned-process
and separate Resume/readmission proofs. Review their shared binding callers;
do not weaken those proofs while separating source custody from applicability.

Reuse existing locks for short state snapshots, SQLite for durable operations,
the source archive for immutable evidence and existing typed refusal/observation
mechanisms. Add no controller/runtime lock spanning filesystem or SQLite I/O;
existing refusal-classifier locking limitations remain documented. No new
dependency, event store, retry service, compatibility path or game-specific key
handler is justified. Existing source-binding and relation fields can express
the distinction; challenge that decision if implementation requires new meaning
that cannot be represented truthfully by the current contracts.

## Verification and delivery

Lead owns the tightly coupled runtime/controller/evidence/test integration;
independent reviewers own design and closed-evidence/source review. No worker
shares these paths during the repair. GitHub #176 owns work and #145 the unchanged
full campaign outcome; this document is the design, not a mirrored tracker.

Regress healthy transitions after Observe returns, after ingestion, during
semantic refresh and before dispatch, including standalone Observe and owned
prompts. Semantic non-equivalence must dispatch nothing and permit explicit
observation and a distinct decision with coherent current/checkpoint/generation.
Keep ACK UUID, source_after, bytes, clocks and costs immutable; stop a text batch
when its informing context changes. Pair positive cases with Pause, session,
control/takeover, pending work, stale/contradictory/missing sources, storage and
global exhaustion. Exercise ordinary keys/text/clicks and image-conditioned
semantic intent without merging their preconditions.

Pass focused checks, independent review and the applicable native disposition
before another frozen finite development campaign. Full portable/exact-candidate
CI qualifies coherent integration and formal acceptance under the
[development-first workflow](../project-management.md#development-first-delivery);
hosted CI may run alongside finite development after relevant local checks pass.
Record actual native disposition and limits; a synthetic interleaving
does not retrospectively pass009 or prove a native race. Keep prior failures,
all original campaign requirements and normal-ending acceptance intact.

The first implementation checkpoint `de97c8b` passed 142 focused tests and
independent review, then failed 49 assertions in the full 1,619-test lane. Its
[finite graphical run](../acceptance/2026-10-22-native-observation-custody.md)
completed the valid ordinary/lifecycle path; harder race/refusal branches remain
unexercised. The full lane exposed missing controller entry/late progression
checks, stopped unbound-source presentation and passive malformed-state
containment. Correct those through the existing common proof/binding paths;
retain explicitly owned private checkpoints and result collection. Migrate
fixtures that contradicted immutable clocks/revision semantics. These findings
and source/graphical lane differences remain evidence, not retrospective success.

The subsequent `dea2a9d` full lane ran 1,619 tests in 740.636 seconds with four
errors: two negative fixtures tried to obtain a new source after revocation or
while another request held rotation, one fixture cleanup cascaded from that error,
and a real handoff presentation regression hid a newer read-only Observe. Reuse
the existing exact handoff phase-binding proof for that presentation; retain the
issued post-Pause checkpoint, newer-source readmission refusal and separate Resume.
Build negative requests from previously retained source data rather than exposing
revoked current sources. The controller and both preflight-only actors were
quiescent before this correction; no new campaign had been admitted.

Corrected source `5d667818c50c3e2cdebac860505f6ac5f97af59c` passes the full
local portable lane: 1,619 tests in 737.743 seconds, rendered diagrams, viewer
regressions and structural/governance checks. Independent source review and 33
focused handoff/runtime tests also pass. [Exact source CI](https://github.com/CVX-Hull/enactive/actions/runs/39867983281)
is a separate receipt, required before formal acceptance and protected merge.
No corrected-source graphical or fresh seven-day result follows from
these checks. A later documentation-only publication checkpoint may run its own
CI alongside finite development play when runtime/native identity is verified;
formal acceptance and protected publication still require that exact head's CI.

Hosted `5d66781` [CI](https://github.com/CVX-Hull/enactive/actions/runs/39867983281)
subsequently failed one assertion after 1,619 tests in 1,207.024 seconds. This
exposed a real Pause presentation gap rather than a reason to wait in the test:
immediate cached revocation left `current_source` and `coordinate_scope` intact,
and an in-flight publication could restore them. Clear both in the existing
immediate Pause update and preserve those cleared fields in its existing pending
publication overlay. Freshness already derives from source availability.
Regress both a blocked writer and Pause during normal/activity summary publication;
historical sources remain readable and controller-first input revocation is unchanged.

This bounded follow-up is prepared in an isolated project-local worktree while
campaign010 retains frozen `77d02fa`. Integrate only after its actual actors are
terminal; do not patch a deciding run or relabel the failed CI. Focused/source
qualification and the run's actual native outcome remain separate evidence lanes.
