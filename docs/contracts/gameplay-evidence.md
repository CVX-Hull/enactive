---
owner: maintainer
review_trigger: Changes to this interface, its callers, persisted formats or authority boundary
status: active
---

# Passive gameplay records and evidence

Mission navigation's `ObservedMap` is a bounded candidate cache, not durable world
memory or a lifetime exploration budget. Each valid projection keeps its current
position and four cardinal coordinates within512cached coordinates, atomically
evicting oldest other coordinates by their newest cell/anchor source revision,
with deterministic coordinate tie-breaks. Both cell and anchor entries are removed
together. A test configuration too small for one footprint refuses before mutation.
Eviction never removes retained frames or Claims, renews authority, changes scope
or refunds mission costs. An old route may become blocked/unknown until reobserved;
ordinary observation/input and fresh guarded navigation continue within the
original mission limits. Source integrity, regression, session, Pause/takeover and
uncertain delivery remain separate stopping conditions. This process-local cache
change adds no persisted or tool format and no compatibility path.

[Contracts](../../harness/gameplay/contracts.py) define eight frozen records:
TaskSpec, EvidenceRef, EvidencePacket, SkillDescriptor, PlanCandidate,
PrimitiveResult, StageResult and RunStatus. Serialized records carry
`schema: "gameplay/2"` and `record_type`. Constructors and `from_dict` reject
unknown fields, wrong types, unsupported enums, nonfinite numbers and contradictory
completion claims. Nested values are immutable; `to_dict` encodes these already
validated frozen values into fresh containers without repeating schema validation.
Raw serialized input and explicit trust-boundary receipt checks retain their
validation. JSON input is bounded to 1 MiB. The injected planner and supervisor
[contracts](injected-planner.md) consume these records in passive/offline studies. MissionRuntime has no
live planner/supervisor endpoint or concrete planner provider; its deciding player
and writer are the separate live execution path. The
[first-slice design](../design/gameplay.md) retains historical rationale, not a claim
that those study components are connected to the current runtime.

[EvidenceStore](../../harness/gameplay/evidence.py) retains successful native-v7
normal/menu/activity/recovery/unsupported diagnostic frames with their actual
coverage. `current()` requires a positively marked normal scene for movement;
`current_boundary()` checks freshness/integrity without granting input permission.
Non-normal references have null game time and no fabricated position/scene facts.
Native `ui` is null or bounded rendered-row coverage only; omitted rows, titles,
filter/count and null selection are unknown, not absence. Inventory rows follow
the visible renderer's selecting columns; the engine's non-selecting cosmetic
selection-summary column is omitted. Other actionable columns, disabled rows,
renderer order and active focus remain represented when visible. Each row also
retains its literal rendered marker independently of focus; an unrendered/clipped
marker is null, not unmarked. The capture joins marker and label within the same
row draw, including item-symbol offsets, with no label-based matching. This is not
label deduplication: genuine duplicate actionable targets remain ambiguous.
Quantities and complete selected-item coverage remain player interpretations of
the actual screen, not native stock or acquisition facts. Native facts never
include latent/off-page inventory. `pause_origin` is diagnostic; host generation
and process-scoped human takeover count govern continuation checks. Its observation identity is the hash of session plus immutable
frame basename; a transport request ID is not a frame identity. It copies original
PNG bytes outside the evictable bridge cache, verifies hashes and records session,
revision, native timestamp, actual first receipt and `cdda-visible/1` provenance.
It checks bounded PNG signature/size and byte integrity, not image decoding; native
capture and viewer/native graphical acceptance own rendering quality.

For current ingestion, native wall-clock age must be -1000 through 3000 ms. Effective
age adds nonnegative initial lag to monotonic time elapsed since the original
receipt, with a three-second ceiling. Duplicate reads and reopening never renew
that receipt. Clock discontinuity, missing/corrupt source, unsupported boundary,
revision regression, contradiction or session replacement invalidates current
authority. A conflicting retained identity cannot become current again, including
when it was not the current frame; same-revision scene conflicts invalidate
retained peers. Transport-only Pause may produce distinct frames at the same
scene revision: `paused` remains immutable within one frame but is excluded from
cross-frame scene comparison. Actual scene/boundary conflicts still dispute peers.
Historical terminal retention instead validates bounded historical age and original
lag without imposing current dispatch freshness or promoting authority. Archive5
records the retention kind, so reopening preserves that distinction. Historical
references remain verifiable but cannot authorize input.
Reopening starts without current authority or a dispatch reservation.
Valid retained metadata remains inspectable when an original image is missing or
corrupt. Reopening records that source as disputed; verification still rejects
unavailable bytes and restored bytes do not clear the dispute. This preserves
memory frontiers without reviving older claims. Invalid metadata and failed
dispute persistence still reject reopening.

Each caller-owned store has one writer and defaults to32frames/64MiB, including
indexed source slots (including missing originals) and orphan files on reopen.
Explicit mission admission may raise retention up to
8192frames/2GiB. These shared mission/store/library ceilings support a prospectively
sized campaign; existing default budgets and original admissions do not grow.
Metadata stays bounded to34MiB with4MiB bookkeeping headroom;
capacity checks reserve worst-case after metadata before dispatch. Each image is at most 32 MiB. Before
dispatch, retain the before-frame and reserve one additional slot plus 32 MiB for
the after/failure frame. Consume or explicitly release that reservation; capacity
failure stops before dispatch and never deletes evidence to make room. The store
itself cannot dispatch. There is no automatic pruning, hidden-state augmentation
or synthetic replacement. Original evidence and bounded tagged interpretations
remain separate. A cross-session PrimitiveResult can retain an after-observation
only as unknown context with no attributed displacement. The bounded native
predicate path was accepted in
[#33](https://github.com/CVX-Hull/enactive/issues/33); see the
[bounded-skill acceptance](../acceptance/2026-10-17-bounded-skills.md) for its tested
scope. This does not establish general campaign evidence ingestion.

The evidence store uses format version 6 and exposes `source_status(reference)`
as `retained` or `disputed` after identity/integrity verification. Disputes persist
across newer observations and reopening, including after damaged bytes are restored.
Stale current authority alone does not dispute historical truth. Earlier stores
are archived evidence, not current runtime inputs; create a fresh store for a new
task. Donor retrieval instead requires the explicit current advisory export
[contract](historical-import.md). The selected offline native6/store5 migration preserves original
bytes and typed historical data; it provides no old runtime reader, synthetic
marker insertion or historical hash rewrite. Mission/11, campaign-memory/6 and
canonical Procedure/3 remain current; ledger13/reflection3 migrate persisted jobs
and all callers together. New procedure environments name native7. Engine saves remain
engine-owned and can be loaded only under a fresh supported admission, without
importing an old mission's authority or evidence store. Neither historical status
grants current input permission.

`authority_generation()` is process-local invalidation history: it advances when
current identity changes, validation invalidates evidence, or the store closes.
Returning to an earlier frame cannot conceal an intervening rejection. It is not
an execution token and is not restored; a new store/memory starts without current
authority.

## Closed-loop play and observations

Use goal → bounded skill → one primitive → fresh observation → verification.
Start with movement, menu navigation and single actions. Movement routines have
a small step limit, require normal-game context, and stop on a prompt, no
progress, a visible hostile creature or unknown creature evidence, pause, stale revision or
transport error. Unknown information stops a routine instead of assuming safe.
Maintain observed facts with provenance/age; do not infer an unseen route is
clear. Structured movement fields are relative avatar position, current game
turn, the UI's visible-creature list, and eight neighboring tiles' terrain and
furniture identities only at CLEAR visibility. No item contents, unseen
creatures, absolute world position, or trap state is exported. Movement accepts
only a small known floor/ground whitelist without furniture. Strictly represented
non-HOSTILE creatures may remain visible. Native`hostile:false` means not classified
HOSTILE, not FRIENDLY or safe; creature positions/occupancy are unavailable. An
attempt into an occupied tile can prompt or fail displacement and stops without
retry. New hostility after a returned step stops subsequent input, including at
the target, without undoing that delivered turn. Damage has no
structured field in the first slice and is assessed visually by the planner;
no deterministic damage guard is claimed. The model chooses high-level objectives, while deterministic guards
handle immediate interrupts. VLA/robotics supplies architectural inspiration;
there is no reason to train a robot motor policy for a discrete keyboard game.

Measure verified primitive actions, model invocations, elapsed time, task
completion and harness failures. Compare single-step control and a guarded
routine on a repeatable safe route, with fresh observations in both. Do not
confound fewer model calls with better survival, or claim statistical superiority
from one short demonstration.

A guarded walk checks the next tile even after its final requested displacement.
It can return `stopped` with all requested steps completed if the next tile is
blocked. Read `steps` and the fresh observation; `stopped` does not mean no
movement occurred and must not cause an automatic retry.

An admitted walk aggregate always includes `observation` (the last validated ready
response returned during this walk, or null), `observation_phase` (`pre_step`,
`post_step`, or null), `observation_received_monotonic` (its original receipt clock,
only when the atomic snapshot fully matches that response, otherwise null), and
`terminal_response` (the exact last exchange return, or null before any exchange).
Earlier ingress/admission errors remain plain `controller_error`. Post-step marks
the attempted input, not credited displacement. A timeout can leave only a
pre-action observation: the separate terminal response preserves the unknown;
neither the old image nor a later image supplies its missing acknowledgment.
Unavailable/stale frames and menu responses retain their actual limitations.
These are evidence, not renewed authority or proof of objective success.

Every stopped walk freezes dispatch, requests Pause, revokes the original
admission generation and publishes the sentinel before returning. Even a known
zero-step stop requires explicit successful Observe, player interpretation of the
fresh image and reason, then explicit Resume before another input. Status reads,
internal native preflight and the retained walk image cannot clear the hold.
Queued old generations stay revoked. Complete walks add no hold. The controller
enforces this sequence; semantic reassessment remains the player's responsibility.
The [repair brief](../changes/023-walk-reassessment.md) explains scope and migration;
its conservative movement guards remain shared with mission navigation.

[Contract index](../protocol.md).


## Binding projections

The current `gameplay/2` EvidenceRef and `cdda-visible/1` identify CDDA observations.
A shared source port supplies identity, session, revision, optional opaque counter,
receipt clocks and an advisory serialized reference; it grants no current input
permission. CDDA EvidenceStore validates the current native format and retained
bytes. Shared memory uses [memory data contracts](../../harness/gameplay/memory_contracts.py)
without interpreting a native scene or equating an observed counter with seconds.
The [mission adapter](../../harness/gameplay/mission_memory.py) authenticates mutation
payloads; the [CDDA adapter](../../harness/gameplay/cdda_memory.py) projects native facts.

The shared [timeline](../../harness/gameplay/timeline.py) consumes immutable
`TimePoint(source_id, session, revision, seconds)` data plus exact `TimeContinuity`
endpoints authenticated by its binding. It rejects missing/reordered links,
regressing revisions/time, duplicate sources and contradictory same-revision time.
It sums only within-session deltas; a new session's counter origin contributes no
gap-time inference. CDDA's [time adapter](../../harness/gameplay/cdda_timeline.py)
projects observed turn seconds, requires equal-turn reload endpoints and verifies
canonical reference equality and retained endpoint bytes before returning game time.
These source seams preserve the current wire/persisted formats; a second actual
binding and its qualification remain separate work.
