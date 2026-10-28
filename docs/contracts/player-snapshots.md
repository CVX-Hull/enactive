---
owner: maintainer
review_trigger: Changes to this interface, its callers, persisted formats or authority boundary
status: active
---

# Player snapshots, detail and image presentation

For skill/non-Launch lifecycle composition, null `source_id` selects only the full
source already cached inside that explicitly selected snapshot; no source fetch or
newer status is substituted. Explicit retained-source selection remains available.
Launch with null stays source-free even if an older snapshot contains an image.
A snapshot with no source cannot supply an implicit binding. Diagnostic Observe
may return `result.source_ids` without publishing current source; explicitly read
and select that retained image. No archive search or cache fallback chooses it.
Source-cache eviction cannot erase the selected snapshot's embedded source, while
snapshot eviction still requires an explicit new read. Phase checkpoint matching
and all receiver freshness/custody/budget checks remain authoritative.

Lifecycle summaries expose their existing private `stage`; an expected-transition
candidate reports `awaiting_transition`, while diagnostic-only candidates expose
no executable lifecycle summary. This is as-of descriptive context, not a receipt
or authority. When a selected snapshot contains a lifecycle phase, the adapter
refuses `enactive_readmit` before submission and identifies the existing
`enactive_lifecycle`, same-operation, `scope=lifecycle` route, including provisional
identity readmission. It performs no fresh read, Resume, retarget or limit renewal;
actual lifecycle continuation still checks current custody and original bounds.
Recovery/handoff readmission keeps its existing separate contract.
If create/load supplies no source and the selected admitted snapshot has neither
an owned launch sample nor current source, a no-submission refusal names the
source-free launch entry point. Explicitly selected, previously read newer menu
evidence still composes with an older admission snapshot. This replaces the
otherwise generic source-selection error; it never launches a child or chooses
a new source implicitly.

Default snapshots advertise `detail_sections`. The frozen configuration is revealed
only through its exact cached detail section; metrics show original game seconds and primitive counts,
while original remaining limits, reserves and current uncertainty stay. Absolute
clocks/objective and advisory job/proposal inventories move to complete as-of
`mission` detail. Default snapshots use read_only=true rather than a constant
authority flag. Proof flags in canonical results remain descriptive; false does
not mean adoption failed. The writer, not cached JSON, checks execution.
Reference slots omit filesystem/hash/retention bookkeeping, preserving opaque
observation IDs and original session/revision/time/turn. Native transport framing
and cached process PID/launch IDs are not default decision data. Full values remain
retrievable in the named detail section. Software still uses the unprojected
mission/source for composition and verification; a hash-shaped opaque handle is
an address, not a request for the model to validate bytes.

Snapshot progress is replaced by `progress_operation_id` only when exactly equal
to the enclosing non-null result with its stable ID. Standalone/pending/different
progress remain complete. Raw native request/ACK payloads are omitted from default
receipts, along with technical source/dispatch/preflight bindings and control request
framing. Delivery, processing/loss diagnostics, correlation and unique feedback remain.
Actions/scene/UI deduplicate only when all match the actually returned source;
then exactly equal known native metadata also lives in that source view, while
capture timestamps and unknown fields remain in native state. This is field
equality, not a claim that independently rendered pixels match;
missing sources or differing native views retain their information. The general
engine action vocabulary is omitted only for DEFAULTMODE, normal in-game play
without represented UI; contextual menu actions, scenes and rows remain.
Complete explicit source/context/handoff/advice/proposal/operation payloads are preserved. Projection only touches declared slots, never recursively
prunes arbitrary memory/proof data. The exact field lists live in
[player_view.py](../../harness/player_view.py). Canonical evidence stays in the
existing ledger/archive/journal and readers. This is one current presentation;
there is no legacy mode. Source/SDK tests do not qualify actual-host responsiveness.

The adapter keeps one process-local presentation fingerprint under its existing
lock. An implicit `next_snapshot` image may be omitted only when its actual PNG
bytes and known mission/player/epoch/native control context match the last image
shown. The envelope explicitly reports the omission. Metadata, source reads and
canonical caches remain complete; this neither skips capture nor establishes a
source-read declaration. Explicit `enactive_snapshot` and `enactive_source` reads
always return their actual image. Historical source reads invalidate the comparison;
changed or unprovable context resends pixels. Restarting the producer clears this
bounded presentation state. No image hash becomes a model bookkeeping task.

Authenticated `GET /api/mission/source?mission_id=ID&source_id=ID` and
`GET /api/mission/frame` with the same exact query expose one indexed original
archive entry/PNG. Both require the local token, exact query keys and the atomically
published mission/store binding. Metadata includes reference, observation,
retained/disputed disposition and `grants_authority:false`; image reads verify the
original bounded PNG hash. They use neither an arbitrary path nor a newer bridge
frame and do not renew evidence clocks, Observe or mutate a lease. Missing/changed
bytes fail. Runtime input validation still owns sticky invalidation and freshness.
Storage replacement retires the presentation binding before closing the old store.
The [adapter brief](../changes/051-structured-player-tools.md) separates source/SDK,
actual host zero-review and native acceptance.

[Contract index](../protocol.md).
