---
owner: maintainer
review_trigger: Changes to this interface, its callers, persisted formats or authority boundary
status: active
---

# Integrated mission lifecycle

The service constructs one [MissionRuntime](../../harness/mission_runtime.py), with
one bounded writer, one queue slot and no automatic admission, launch or Resume.
The old waypoint runtime and its live API/CLI are removed. Passive movement,
[planner](injected-planner.md) and [supervisor](movement-skills.md#passive-waypoint-supervision) components remain source/study tools, not another
execution ingress. The [mission component view](../components/mission-execution.md)
explains current responsibilities; this protocol and receiver schemas own exact
records/lifecycle requirements. The [original design](../design/player-owned-mission.md)
is historical rationale. Native/outcome evidence remains separately scoped.

Authenticated `POST /api/mission` accepts one strict mission/11 record, at most65536
UTF-8 bytes. It reuses host/origin/token and finite/duplicate-key JSON validation;
operator command/recovery bodies keep4096-byte limits. Required fields and closed
variants live in [mission_contracts.py](../../harness/gameplay/mission_contracts.py),
not a second HTTP schema. Unsupported versions and `/api/gameplay` reject, without
conversion. Admission and original deadlines/costs persist in the ledger; parsed
JSON and status contain no executable lease.

Start records source-free admission and sends no native request; explicit Observe
remains passive. Even already-unpaused normal play does not prove the named world/character, receive a lease or seed the mission's game-time
anchor. Registered creation/load must establish those facts after owned launch.
Registered creation/save/load and provisional character inspection now compose in
source tests through the real controller, ledger and evidence archive. Quiescent
successor handoff and deliberately charged readmission also compose in source.
Selected item/inspection roots, owned quantity editing and one-observation activity
polls and registered activity interruption/answer/resumption now compose in source.
Selected delivery reconciliation and separate normal-play readmission now compose
in source; normal finish has source coverage. Unsupported semantic uncertainty
remains stopped rather than being passed through unknown-delivery reconciliation.
[Native007](../acceptance/2026-10-20-native-lifecycle-qualified.md) qualified ordinary
creation/identity, counted drop/pickup, a known two-step return, bounded native
wait/poll, normal save/new-child exact reload and normal final stopped Finish.
The later [independent024 mission](../acceptance/2026-10-21-independent-supply-shelter.md)
qualifies the bounded integrated gameplay outcome and actual successor continuity.
Native006 retains its actual failure
and exceptional second-child cleanup; later success does not rewrite it.
Neither synthetic UI tests nor tests assuming identity accept an independent mission. Observe likewise cannot adopt
an unexplained normal session. Reopening restores neither phase nor input authority.

Lifecycle tasks: [launch](#owned-launch-and-initial-load-admission), [Create/Load](lifecycle-create-load.md), [adoption](lifecycle-preconditions.md#normal-identity-adoption-and-historical-proof), [exit](lifecycle-exit.md) and [Finish](lifecycle-exit.md#mission-limits-and-normal-finish).

## Owned launch and initial Load admission

Registered lifecycle launch is a source-free root: null phase/Work/native binding,
empty source/identity IDs and exact admitted names. It invokes only the fixed
prepared NativeProcess with its admitted binary hash. Original root/mission wall
and cleanup limits include process validation, exec, command queueing and native
readiness. It retains child custody after cancellation/timeout; a second launch
or admission replacement cannot silently replace it. A fresh paused untouched
MAIN_MENU, empty error, valid rendered frame and unchanged actor/epoch/controller/
operator counter are required for a readiness receipt. It remains passive: no
Resume, lease, normal facts, identity or game-time anchor. Portable fake-process
tests are not actual native launch acceptance.

A new admission with `scenario.mode=load` may enter its admitted existing world and
character through ordinary Load without a previous mission's SavedCheckpoint.
It requires this mission's owned launch, actual selection/transition, current
visible identity Claims and separate adoption. Its first normal segment starts
new game-time accounting at the loaded turn. It imports no prior execution
handles, map, stock, authority or elapsed-survival credit. A `fresh` admission still
requires its committed creation route. Later reloads in either mode require the
current mission's own SavedCheckpoint and cannot roll back newer normal evidence.
CDDA owns save validity; prospective experiment preparation retains any baseline
archive/pins. There is no cross-mission save-proof service or compatibility path.

Create/save/load roots require null `work_id` and empty `identity_claim_ids`.
The shared pure submission validator rejects violations before client submission or
receiver queue admission, so a malformed draft cannot itself revoke a lease.
It does not discard supplied fields or retry; a new corrected request must pass
every live guard. Identity adoption still uses its exact lifecycle child; Finish
may cite completed Work. Pause, missing evidence, budgets and storage failures
retain their existing stopping behavior. This syntax refusal grants no authority.
The underlying record validator still reads original rejected request history;
old failures are retained unchanged and cannot become executable through reopening.

Cached process facts are last samples, not a liveness guarantee. Shutdown journals
any owned child through the [exceptional shutdown contract](lifecycle-exit.md#exceptional-writer-shutdown);
reopening restores no process handle. Only a
validated committed OwnedNormalExit resolves that launch's historical custody.
Otherwise attempted/uncertain launches remain unavailable, with no PID adoption.
Process absence or exit code alone cannot prove a normal save/exit.

Continue with [Create/Load transitions](lifecycle-create-load.md); owned menu cleanup uses [normal exit](lifecycle-exit.md).

## Designated campaign operator

The lead designates one general-purpose player for a finite mission. It chooses
plans, interprets evidence, retrieves/updates memory and requests semantic skills
and registered normal lifecycle through mission/11. The lead owns source/release
acceptance, finite admission, shared runtime custody, escalation and final
verification. It supplies no ordinary gameplay rescue in the deciding mission.
Explorers/reviewers never send inputs. Actor names and instructions are workflow
controls, not an OS sandbox or authenticated sub-agent capability.

A brief names immutable source/native, admitted world/character, exact command/file
scope, actor/phase, cumulative limits, cleanup reserve and stop rules. No source or
save edits, debug advantages, arbitrary process commands, hidden state, competing
executor or silent budget extension follow from player assignment. User Pause and
native takeover always win. Unsupported or uncertain effects require explicit
source-linked reassessment; they never authorize blind replay or a different actor.

Handoff requires Pause, completed tool handles, no scheduled/queued input, a retained
checkpoint and explicit player quiescence. Cached status alone cannot prove an
empty external tool queue. Fresh-context replacement must use the registered
one-use handoff and retained campaign memory, not lead reconstruction. The runtime
must validate current actor/epoch, sources and original costs before continuation;
a durable receipt or summary restores no lease or Resume. Lifecycle and handoff
adapters remain implementation gates, not permission to fall back to raw commands.

The [first seven-day campaign](../acceptance/2026-10-19-seven-day-survival.md) used the
earlier supervised ordinary-input procedure. Its failures, known nondelivery
replans, unknown ACKs, native menu gaps and source-linked decisions remain evidence.
That workflow is historical, not an alternate live campaign ingress. The passive
waypoint planner remains candidate-only for offline studies. Future campaigns need
new prospective authority and actual-player permission preflight; no old campaign
budget, exception, rule allowance or running chat renews admission.

[Contract index](../protocol.md).
