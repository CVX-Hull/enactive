---
owner: maintainer
review_trigger: Changes to this interface, its callers, persisted formats or authority boundary
status: active
---

# Controller run ownership

The in-process controller API exposes `acquire_mission(mission_id, epoch,
actor_id, *, operation, expected_session, expected_revision, expected_boundary_id,
replace=None, refuse_changed_context=False)`,
`execute_mission(lease, *, kind, value, expected_session, expected_revision,
expected_boundary_id, logical_action_id, deadline_monotonic, timeout=None,
expected_image_sha256=None, preflight=None)` and
`release_mission(lease)`. Operation is navigate, interaction or lifecycle.
A frozen MissionLease belongs to one controller; only the exact returned Python
object authorizes input. Status `mission_lease` contains descriptive mission/actor/
epoch/session, host pause generation, native takeover generation and operation;
JSON cannot reconstruct the capability. Navigation permits guarded cardinal
movement only at normal play. Interaction/lifecycle can also use supported menus;
activity/debug/unsupported boundaries never admit ordinary keys.

Acquisition is explicit, nonblocking and has one winner. It requires no active or
queued ordinary/control writer, live lease, pending effect or native inbox, plus
reconciled, unpaused, fresh successful operation-eligible evidence matching the
supplied session/revision/boundary. It rotates native authority and admission generation without
observing, resuming or dispatching. Historical unknowns remain historical unknowns;
new ownership cannot establish the outcome or continuation of an older task.
Deliberate operation rotation supplies the exact live capability as `replace`.
It preserves mission/epoch/actor/session and requires the same empty writer slots
and unchanged Pause/takeover state. Rotation revokes the old capability and advances
host generation under the admission locks, without Pause or an input gap for an
external writer. A serialized lease description cannot request replacement.
For an ordinary operation replacement only, `refuse_changed_context` can report a
typed zero-input applicability mismatch under that same acquisition fence before
rotation. The runtime must then prove complete ordinary custody, source integrity
and resource health after the locks release before retaining read-only Observe
lineage. It never retargets acquisition or applies to specialized lifecycle,
activity, recovery or exit authority.

An authenticated published native rejection settles the primitive as rejected,
with no after-source; it does not prove delivery or restore the old lease. For
ordinary input only, after settlement the runtime may preserve read-only Observe
lineage across that exact operation rotation if the existing refusal guard proves
healthy current custody, retained evidence, no unsettled work and global capacity.
A new explicit observation precedes any new input choice. Lifecycle/activity/
recovery scopes, unhealthy native status, uncertain delivery and actual faults
remain outside this continuation. No retry, allowance renewal or error-text
classification follows. Prompt authority failures identify binding identity,
pause generation, store generation or source retention in the existing durable
operation reason; they do not publish private binding dumps or infer a past cause.

Ordinary external key/action/walk/resume reject while leased. Existing HTTP/CLI
input reaches this same controller gate; it cannot supply or obtain a capability.
At the controller layer Observe/status, record-only goal and Pause remain
available. HTTP further routes nonterminal mission Observe through typed ingress
and blocks raw input/recovery. The viewer displays mission ownership; a model call
never holds controller locks. Only registered mission operations can request a
lease; service startup, admission and transport Resume never establish identity.

A leased call submits one registered action, permitted key or direct physical
event, using native-v7 observation and input checks. Intended boundary and human takeover generation are
bound in native action/key/resume requests and checked at native commit. The original command admission generation and exact live lease
are checked around queueing/preflight and immediately before atomic publication.
Every walk step uses its original entry generation. Pre-takeover or pre-acquisition
queued inputs cannot become current merely by waiting. Semantic decisions retain
their source-equivalence policy. Direct events retain their informing source while
the actual fresh dispatch capture supplies the native expected triple; this is
physical-event drift permission, not semantic retargeting.

## Controller dispatch, freshness and preflight

Pause and release revoke before returning; release requires the current capability
and also pauses. Recovery, native takeover/session change, a paused native
observation, transport failure and shutdown invalidate ownership. Resume does not
restore a lease. Startup restores no task or capability. Native token validation
remains the final input commit gate; an already committed action cannot be undone.
The controller serializes durable publication, revocation and some journal writes
under its data lock. A filesystem stall in that critical section can delay Pause;
there is no hard response-time guarantee under disk failure. Runtime memory/model
work must add no lock that delays revocation, and native activity cancellation
remains separate from revoking further harness inputs.
`execute_mission` returns an envelope containing the logical action ID, exact native
`request` or null, `result`, `published`, original terminal
`received_monotonic` or null, nullable `preflight` and separate nullable
`processing_error`. Preflight contains the copied final Observe, its original
`received_monotonic` and `expected_image_sha256` or null; direct preflight also
retains its immutable `informing` triple. Preflight Observe is not an action receipt. The
absolute monotonic intent/task deadline is checked after queueing/preflight and
under the publication lock; it bounds both exchanges and the native deadline.
`observation_snapshot()` returns a copied current observation and original first
receipt clock. Reading a snapshot does not renew its freshness.
Live-versus-retained state comparison excludes transport id, timestamp and frame
filename; it retains status/error/frame validity and complete semantic/Pause/takeover
state. This comparison grants neither freshness nor image equivalence. Final
publication preserves the original native-issued preflight capture. Non-spatial,
non-image-conditioned input may use that retained capture after a newer rendering
only while its original clock and complete normalized native metadata remain
valid. Native checks the issued record; the host never substitutes a newer
filename or timestamp. Image-conditioned semantic input, spatial clicks and
recovery retain their applicable current-capture/image/geometry rules. Direct
preflight binds its actual fresh capture under uninterrupted custody, separately
from the immutable model-informing source.
If an image-conditioned ordinary input or spatial capture's filename changes during host preflight while
all existing ownership, complete state, receiver, Pause, pending-work, original
freshness and deadline guards still pass, input is refused before publication
without revoking the healthy lease. Its prepared primitive remains charged and
the batch ends; no native request, ACK or after-source is invented. The runtime
retains only the existing authenticated read-only observation scope across its
operation rotation. Explicit Observe supplies a fresh binding before a distinct
new input intent under the original
mission/prompt limits. This neither retries the old batch nor refreshes its
receipt, replaces its frame or restores expired/lost authority. Combined guard
failures keep their existing stop behavior. Non-image input does not refuse solely
because the latest capture basename changed. Normal lifecycle source policy is
defined in [lifecycle preconditions](lifecycle-preconditions.md); image-conditioned setup/Resume and paused recovery remain strict.
Known early ordinary nonpublication, such as a changed click mapping before
primitive preparation, uses that same observation scope without inventing a
primitive charge. Prepared refusal retains its actual charge. Processing/storage
faults still stop. Observe may close an exhausted local macro through the existing
closure receipt; it cannot renew its root or spend protected mission reserves.

An ordinary semantic shortcut may also expire after its distinct actual preflight
was retained but before reservation/preparation. If the failed source is exactly
the prior entry and its only failed predicates are age limits, the writer may
refuse it through the existing controller fences and authenticated unpublished
receipt. The actual preflight must still be fresh; ownership, retained sources,
store generation, pending-work and global limits must remain healthy. Preserve
only the existing read-only Observe lineage, earlier delivered effects and costs;
clear the refused proposal's pending ID without attributing any new effect.
The player explicitly observes and chooses a distinct intent. Never refresh,
replay or finish the old suffix automatically. Expired actual preflight, clock
reversal/future capture, invalidated custody and specialized lifecycle/activity/
recovery paths retain their stopping behavior. Freshness audit records retain
the actual source, check clocks and failed predicates without granting authority.

Native passive captures freshly present and encode. Only unchanged complete
observation metadata, geometry and actual bounded PNG bytes may reuse the current
identity within its original three-second window, checked after encoding/comparison.
The transport id/status/error and capture basename/timestamp are normalized for
that metadata comparison. Reuse preserves the original timestamp, immutable file,
receipt age and retention entry. Explicit id-bearing captures always mint a fresh
identity. Changed/expired/failed captures cannot reuse an older matching frame.
The existing 120-frame native retention deque also retains each issued filename's
original capture timestamp and normalized complete observation metadata. Input
looks up that exact record, compares its metadata with current game-thread state,
then checks its original TTL, current saved/presented clocks and original request
deadline. Unknown, evicted, expired or changed-context captures refuse with
predicate-specific diagnostics. Pixel changes do not renew those clocks.
Image-conditioned input and spatial clicks additionally require the current
capture; registered normal readmission Resume uses its native-state policy while
other Resume callers retain image conditioning. No TTL renewal, automatic retry
or silent retargeting follows. Immutable ACK/UUID,
retained preflight correlation and semantic exact-PNG commit checks remain exact. Recovery
hashes the sampled live PNG outside the Pause lock and fences that same identity.

The trusted Python-only `preflight` callback receives that copied Observe and
actual receipt after boundary/lease/image checks, inside the command lock but
outside the data lock. Runtime may retain the exact source, reserve after-frame
capacity and commit a durable intent before publication. The controller rechecks
owner, Pause, recovery, boundary, freshness and the original deadline afterward.
An ordinary callback exception stops before input publication and freezes/revokes
the owner; secondary persistence failures remain explicit diagnostics. A crash is
not converted into proof of nondelivery. Callback and expected-image arguments
are never accepted from public command JSON.

`resume_mission` accepts the exact recorded controller boot, host operator-Pause
counter, general authority generation and native session,
revision, boundary, takeover count and diagnostic origin for a runtime-admitted
transition. It rechecks after queueing/observation; a newer Pause/takeover wins.
It does not establish an admitted phase itself. Public command JSON cannot call
this API, and an old lease cannot Resume. Runtime integration remains separately
tracked; these controller capabilities alone do not make a player autonomous.

[Contract index](../protocol.md).
