---
owner: maintainer
review_trigger: Changes to this interface, its callers, persisted formats or authority boundary
status: active
---

# Unknown delivery collection and reconciliation

For an eligible published non-lifecycle, non-Resume unknown dispatch, the runtime keeps its original
root, actor/epochs, operator/takeover binding, native request and after-frame
reservation in a private process-local candidate. Before the first later Observe,
it makes one bounded delivery-evidence collection attempt. An exact successful
unclaimed inbox retirement or a validated correlated terminal result may be
retained; missing/claimed files, progress or the next frame alone are not proof.
Collection admits no new evidence after250ms or the caller's deadline, including
after delayed file reads. Filesystem stalls themselves cannot be interrupted by
this software deadline. Host locks do not serialize the native response writer;
an uncaptured terminal result may be overwritten by Observe and stay ambiguous.

The existing journal records collection start, deadline and receipt clocks. A
framed terminal result consumes its original reserved archive capacity before
Observe changes the current source; unavailable or stale frame bytes stop this
path. Exact unclaimed retirement or a frameless terminal result releases only its
unused reservation on explicit reconciliation. Collection alone neither accepts
the response as current, resolves the ledger effect, refunds cost nor sends Resume.

`reconcile` requires the exact original unresolved request, captured private proof
and current fresh paused same-session diagnostic source. A later frame or model
assertion cannot replace missing delivery proof. The uniform closed
`EffectReconciliation` envelope is bounded to32768bytes and has exactly one typed
basis: `DeliveryResolution`, `LifecycleTransition` or `OwnedNormalExit`. Write and
reopen validate its basis semantics and correlate the original request/root/Work,
actor/epochs, primitive/native mapping, canonical native request, independently
retained dispatch binding, collection clocks and source IDs. Reconciliation leaves
the immutable unknown ACK and cumulative charge intact and grants no lease. A
correctable stale/wrong diagnostic selection allows fresh Observe and a new
read-only reconciliation request under the same original bounds; authority changes
or missing proof do not. A proof committed before a crash without its semantic
receipt cannot authorize readmission. Reopen restores no candidate or consent.

Ordinary delivery `reconcile` is separate from same-root `lifecycle` transition
reconciliation. If no ordinary recovery candidate exists but a positively healthy
expected lifecycle unknown remains, the wrong-tool request is a zero-input local
refusal naming the lifecycle operation/root. Existing child/operator/actor/epoch,
clock, original transition deadline and native takeover checks must pass, with no
Pause, frozen controller or restored lease. Its unknown ACK, source, charges and
limits remain; no request is automatically replayed or retargeted. Missing/invalid
custody still stops. Diagnostic-only lifecycle candidates get no such continuation.

`readmit` has explicit closed `handoff` and `recovery` modes. Recovery names the
completed reconciliation, original root and Work, exact sources and live binding.
It requires fresh equivalent normal play, sends one separately charged deliberate
Resume through the existing writer, then acquires the same actor/epoch lease.
Menus, editors, confirmations and activities cannot regain private ownership from
history. Unknown Resume stops without recursive recovery. User Pause/takeover
revokes eligibility while preserving uncertainty/capacity/costs. Registered
lifecycle keeps its own transition handling through the same effect envelope.

A navigation suffix names the original root and unchanged goal/scope/Work. Resume
and suffix share that root's original primitive/wall limits and first game-time
anchor; checks apply before input and after returned effects. Pending continuation
fences ordinary competing skill/lifecycle roots and handoff/claim/readmit until a
verified terminal suffix or explicit stop. Historical phase IDs grant no authority.
This selected source path does not establish semantic success, native recovery or
general recovery from already-returned but uninterpretable outcomes.

[Contract index](../protocol.md).
