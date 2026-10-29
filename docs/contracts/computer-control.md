---
owner: lead
review_trigger: Mechanical wire, operation/source, custody or player port changes
status: active
---

# Computer control and player ports

This is the current source contract for [#176](https://github.com/CVX-Hull/enactive/issues/176),
with one production backend. [ADR006](../decisions/006-computer-control-boundary.md)
owns the boundary; the [cutover brief](../changes/071-computer-control-cutover.md)
retains historical rationale. Native7/mission11 and the prototype are retired
executable routes. The [production report](../acceptance/2026-10-29-computer-control.md)
owns scoped actual outcomes; #176 and its linked PR own protected delivery state.

## Responsibilities and current data

`harness/computer/` owns pixels, basic events, mechanical geometry, one writer,
original limits, permanent Pause, exact delivery uncertainty and owned cleanup.
It cannot import player/game/tooling modules. `harness/player/` owns fallible
knowledge, programs, game interpretation and context. The composition service
connects them; player assertions never grant input custody or certify a save.
All game-specific preparation stays outside the computer package.

Start a fresh explicit session under `.runtime/computer-sessions/`, with a new
`computer-session/1` SQLite store and exclusive launch marker **before** DB/native
creation. A selected partial directory refuses even without a DB. Never scan or
drain old inboxes or unrelated retained sessions. Existing native7/mission11/DB13,
proof profiles and executable old player formats are unsupported. Preserve their
original artifacts/source as inert history; retain upstream saves unchanged and
load them only through visible controls. Current player knowledge uses a selected
`player-memory/1` store, which may span fresh native-child sessions.

## Native channel

Use one inherited nonblocking `AF_UNIX/SOCK_STREAM` socketpair. This removes
ongoing filesystem IPC/publication from the native event loop, including the
class of coupling implicated in [#128](https://github.com/CVX-Hull/enactive/issues/128).
The custodian outside the game owns file/SQLite publication. No native publisher
thread, detached helper, recovery journal or transport framework is needed.
Upstream save I/O, SDL readback/PNG CPU and arbitrary OS hangs are outside this
bounded publication guarantee; the original rename-stall cause remains unknown.

At startup, validate the exact inherited shared-lock descriptor/file identity and
socket type; retain the locked reference for the native lifetime. Set both FDs
close-on-exec before application main, the socket nonblocking and `SO_NOSIGPIPE`.
Never `LOCK_UN` a shared inherited reference. The parent closes its child socket
copy after spawn. The host/MCP inherits no native FD. Only the Pi host receives its selected provider credential; MCP and the game do not.
After startup, no bridge filesystem checks, environment polling or file writes
occur in SDL callbacks. EOF/protocol failure permanently fences automation.

Environment: `ENACTIVE_COMPUTER_FD`, `ENACTIVE_COMPUTER_SESSION`,
`ENACTIVE_COMPUTER_LOCK_FD`, `ENACTIVE_COMPUTER_LOCK_FILE`.
Current launch rejects `ENACTIVE_COMPUTER_DIR` and `CDDA_HARNESS_DIR`.

A packet is four big-endian header-length bytes, UTF-8 JSON header, then raw image
bytes. Header length is 1..65536; closed header:
`{schema:"computer-wire/1",kind:"request"|"state"|"receipt",value:object,payload_bytes:int}`.
Only a capture receipt carries PNG bytes, at most64MiB. Raw pixels are separately
bounded64MiB. Encode using installed SDL_image `IMG_SavePNG_RW` and bounded owned
`SDL_RWFromMem` storage, which outlives encoding/transmission; no PNG implementation.

Use one outgoing packet, one deferred Pause receipt and a dirty-state flag.
Coalesce only unsent passive state. Preserve partial read/write offsets and exact
pending receipts/images; never replace a terminal receipt or renew its timestamps.
Each SDL callback does at most256KiB socket work and8 incoming packets, never
waits for a peer, and returns on `EAGAIN`. An exhausted work budget does not prove
a queue empty. Backpressure cannot block real SDL polling/presentation or normal
application execution. A busy response prevents further synthetic command events;
Pause/EOF is still consumed. No new normal request until the prior receipt is
fully handed to the socket. Duplicate IDs permanently pause without redispatch or
relabelled receipts; remember all prior IDs in a bounded65536-entry set, then stop.

| Value | Closed fields |
| --- | --- |
| `computer-request/2` | `schema,id,session,kind,expires_ms,input`;32hex IDs/session; kind `observe`, `input` or `pause`; null input for observe/Pause |
| `computer-target/2` | `schema,session,pid,window_id,paused,takeover_generation,latest_frame,error` |
| Frame | `name,capture_id,presented_ms,width,height,window_width,window_height,viewport`; name is logical `frame-N.png`, never a native filesystem path |
| `computer-receipt/2` | `schema,id,session,disposition,emitted_events,reason,frame`; disposition delivered/rejected/partial/unknown, emitted0..8, frame null or frame above |

At claim, derive a **single** local monotonic expiry from the original wall expiry,
capped5s; check it before every command event without renewal. Parent operation/run
monotonic deadlines remain independent. Delivered means SDL event handoff, not
application consumption/success; emitted input cannot become undelivered rejection.
Capture is the last actual default-renderer present, with original time/geometry.
Keys have no image-age/equality or game-phase predicate. Clicks bind returned
mechanical geometry; unsupported logical-size/scale transforms refuse explicitly.
Real SDL events precede synthetic stages; takeover preserves human input/state.

Pause is idempotent and immediately latches, including during frame backpressure.
Retain the original pending packet/receipt. Neutralize only owned presses, then
emit its original partial/delivered result; emit the one separate Pause receipt
when the original packet drains, then passive state. Never evict either receipt.
The Python stop path sets its permanent event first and uses a separate send lock,
with at most250ms to finish framing/send Pause, independent of executor/DB locks.
If it cannot finish, `shutdown(SHUT_WR)` signals native EOF; keep receive open for
original collection. Report stop-requested separately from native-confirmed Pause.

## Computer operations and custody

The custodian owns exact subprocess handles, shared exclusion, socket, store and
writer. Its bounded receive thread only decodes into one normal receipt/frame
slot, one Pause slot and latest state; it never writes SQLite/files. The serialized
executor stores original intent/native IDs and reserves original capacities before
publication. DB/PNG failure pauses and leaves the original uncertain operation;
no replay or authority reconstruction after restart. User Pause bypasses executor
and DB waits. Cleanup closes the channel and terminates/reaps exact owned children.
Normal native exit0 is sampled **before** forced cleanup, separately from Save claims.

Public input is1..32 key/text/click/wait actions. Keys are printable ASCII or the
named keys in the [shared schema](../../harness/computer/protocol.py); modifiers
are explicit. Text is1..31UTF-8 bytes without controls. Waits are0..2s each and
at most15s combined; one operation is at most15s and never exceeds the run deadline.
Wait delays the caller in wall time without sending an SDL input event; it is
not an application command or settlement guarantee. Clicks use a source actually
returned to that actor; keys/text need no source.
Validate the complete sequence before its first effect. Partial/unknown delivery
permanently stops new input; collection retains the original IDs, never repeats it.

`computer-operation/1` has `schema,operation_id,session,actor_id,kind,status,
created_wall,deadline_monotonic,receipts,source,remaining,reason,handoff`.
Kinds: observe/input/handoff. Status: pending/completed/refused/partial/unknown/sealed.
Client assigns the ID before HTTP submission; duplicates collect or refuse, never
dispatch. Source/handoff are null unless present. MCP cancellation first requests
independent permanent Pause, then abandons the await. Result/source reads have no effects.

`computer-source/1` is immutable: `schema,source_id,session,capture_id,sha256,
media_type,presented_ms,received_wall,width,height,window_width,window_height,viewport`.
Source ID is `<session>-<capture_id>`; media is image/png. `received_wall` is the
original receipt time. Per-read time is separate. Verify original bytes on source
consumption. Full PNG remains available; derived player views disclose omissions.
Custodian remaining seconds and host HTTP/time budgets are distinctly labelled.

The loopback service binds127.0.0.1, accepts bounded JSON and per-actor bearer
capabilities, with no CORS/public exposure. Browser routes are passive status/source
plus independent user Pause. The writer validates active custody immediately before
effects. Memory/progress/identity are never capability tokens.

Handoff seals the actor only with no outstanding/uncertain input or permanent
Pause. Persist a canonical immutable context snapshot before sealing. The operation
binds `handoff:{schema:"player-handoff/1",operation_id,session,actor_id,context_id,
context_sha256,sealed_wall,grants_authority:false}`. A sealed token permits original
result, retained-source and player/context reads only. It cannot observe anew,
input, mutate memory, run a program or create another handoff.
The host accepts only its direct handoff or collection of its own pending original
handoff. The driver verifies canonical issuance/context digest and actual old host/
MCP process-group quiescence before minting a successor under **original** limits.
The current sealed actor retains only independent cancellation, never new input. Retired actors cannot stop successors. Store I/O never holds the cancellation lock; a final stopped/stage check precedes quiescence. Unexpected closure/cancellation after sealing still permanently pauses; later
collection cannot restore succession. No game phase or identity requirement.

## Player knowledge and executable proposals

The pure player package has no process/provider/server/runtime imports. Its typed
control callback is `observe(actor_id,*,deadline_monotonic=None)->(operation,png|None)`
and `input(actor_id,actions,*,source_id=None,deadline_monotonic=None)->(operation,png|None)`.
A supplied deadline can only shrink the original run/15-second operation horizon;
the runner passes its one original deadline to every callback. `ProgramRunner` belongs
in `harness/player/programs.py`; only the coordinator submits its proposals through
the same computer port. A helper failure/yield leaves basic input available unless
mechanical custody itself stopped.

Predispatch program lookup/argument faults produce a terminal collectable helper
result under the original run ID, with no computer operation. They do not revoke
healthy basic input. An exception during computer input remains uncertain and
permanently stops further input; collecting a helper result cannot rearm custody.

`player-record/1`: closed `schema,kind,text,data,sources,supports,supersedes,
applicability,program_id`; kinds claim/work/decision/procedure/correction/advice.
Text≤8192; data object≤16KiB; source/support lists≤16; supersedes/program may be null.
Applicability is null or `{game,version,notes}` (128/128/1024characters).
Store assigns ID, actor and creation time. References must exist; corrections name
a prior superseded record. Keep parents/contradictions; default queries hide
superseded records, never erase history. Quantities/Work/success remain player claims.
Advice is candidate-only. No old campaign-memory or executable import readers.

`player-program/1`: closed `schema,code,parent_id,reason,source_ids,record_ids,
applicability`; code≤32KiB UTF-8, reason≤2048, references≤16. Store assigns immutable
program ID/SHA/actor/time; parent must exist. Preserve source/record support and
one-parent ancestry. Sibling revisions may coexist as fallible alternatives;
the store chooses no winner. Applicability is fallible data, not native eligibility.

Composition lazily registers exact referenced images on explicit memory append or
program save, before that transaction. Current sources come from the computer
port; prior-session sources from the explicitly selected player store. The bounded
256MiB PNG BLOB store keeps durable provenance independent of old input authority.
Do not copy every Observe. Capacity/registration failure reports cannot-remember
and leaves basic input available. Verify SHA on image read; no silent eviction.

Context selects≤32 roots, follows bounded support/correction/program ancestry and
returns whole records, source references and explicit omissions within≤64KiB.
Oversized records/code are omitted explicitly with readable IDs, never truncated
into plausible executable content. Source references are availability, not read proof.

`program-view/3` contains `schema,source,image,interpretation,remaining`.
Pillow13.0.0 decodes exact PNG into a player-selected crop and nearest-neighbour
RGB view≤96×96. Image includes dimensions, flat RGB channel values, original
geometry, crop, sampling and explicit omissions/alpha-on-black derivation.
Selection is `{crop:null|[x,y,w,h],size:[max_width,max_height]}`; interpretation is
player JSON, never inferred engine facts. Full source is separately readable.
Keep the existing V8 source/view/state/result/heap/compile/step and microtask bounds.
A step returns `{status:"act"|"yield"|"done",state,actions,reason}`: actions are the
same basic public controls for act and null otherwise. Evaluation never dispatches.
`ProgramRunner` consumes an actual capture each step (including a preceding input's
returned capture), runs≤64steps/20s under original control limits and retains every
original operation/source. No replay or success inference; faults/unknown stop that run.

## Composed operations and telemetry

All public mutation IDs share one namespace across computer and player services.
Persist player service intent before authoring/execution and child computer IDs
before each callback. A duplicate collects its original result or refuses; it
cannot cross from a program-run ID into a new basic input. `player_result` reads
original authoring/program results and child operation references without execution.
Earlier session references remain knowledge only, with no restored input authority.
Compact program results keep source/operation IDs, decisions, state hashes and final
state, with explicit omissions; full original receipts/images remain separately readable.

Native intent/send/receipt timestamps retain their original wall/monotonic values.
Late collection never renews a source's `received_wall`. Host telemetry version2
records payload hashes/counts, image references and bounded ordinary assistant text;
it excludes private reasoning and base64 history while preserving the actual model
payload. Stable frozen system context is reused across actors; changing role,
resources and handoff knowledge are explicit prompt data. Host decision-time and
custodian horizons stay distinct. Analysis is read-only and current-format only.
Observer `observer-timing/4` joins exact session/source/capture to DOM replacement,
with missing/invalid clocks labelled; it does not measure paint or useful progress.

## Reuse and qualification limits

Socketpair/SQLite/HTTP/MCP/Pi are maintained facilities. Thin framing and custody
integration cover the demonstrated native-publication/one-writer gap; no framework.
Pillow is a pinned project-local maintained codec for Python image views, replacing
an otherwise unnecessary PNG parser. The lead owns this integration; reconsider on
backend/platform incompatibility or recurring protocol fault. Keep applicable macOS
build compatibility, remove old game-semantic engine hooks and retire the prototype.

Primary contracts: [socketpair](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/socketpair.2.html),
[socket options](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/getsockopt.2.html),
[Python sockets/shutdown](https://docs.python.org/3.14/library/socket.html),
[SDL PNG RWops](https://wiki.libsdl.org/SDL2_image/IMG_SavePNG_RW),
[RWops buffer lifetime](https://wiki.libsdl.org/SDL2/SDL_RWFromMem),
[Pillow image operations](https://pillow.readthedocs.io/en/stable/reference/Image.html).
Native fixtures, source tests and organic gameplay are distinct evidence lanes.
The cutover does not imply cadence, learning benefit, survival duration, arbitrary
filesystem resilience, second-game, Unicode/IME or real-human takeover qualification.
