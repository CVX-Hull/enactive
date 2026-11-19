---
owner: lead
review_trigger: Mechanical wire, operation/source, custody or player port changes
status: active
---

# Computer control and player ports

This is the current source contract ([#176](https://github.com/CVX-Hull/enactive/issues/176))
with one production backend. [ADR006](../decisions/006-computer-control-boundary.md)
owns the boundary; the [cutover brief](../changes/071-computer-control-cutover.md)
retains historical rationale. The [production report](../acceptance/2026-10-29-computer-control.md)
owns scoped actual outcomes; #176 and its linked PR retain the delivery receipts.

## Responsibilities and current data

`harness/computer/` owns pixels, basic events, mechanical geometry, one writer,
original limits, permanent Pause, exact delivery uncertainty and owned cleanup.
It cannot import player/game/tooling modules. `harness/player/` owns fallible
public call and hint journals and game interpretation. The composition service
connects them; player assertions never grant input custody or certify a save.
All game-specific preparation stays outside the computer package.

Start a fresh explicit session under `.runtime/computer-sessions/`, with a new
`computer-session/1` SQLite store and exclusive launch marker **before** DB/native
creation. A selected partial directory refuses even without a DB. Never scan or
drain old inboxes or unrelated retained sessions. Existing native7/mission11/DB13,
proof profiles and executable old player formats are unsupported. Preserve their
original artifacts/source as inert history; retain upstream saves unchanged and
load them only through visible controls. The selected `player-journal/1` store
(SQLite `user_version=1`) may span fresh native-child sessions. A supported current
journal may be reopened; a nonempty unrecognized or unsupported store is refused
before native launch. The journal stores public calls, hints and referenced source
metadata and PNGs, not player-authored durable knowledge or programs. The canonical
computer store and native wire versions are the ones this contract defines.

## Native channel

Use one inherited nonblocking `AF_UNIX/SOCK_STREAM` socketpair. This keeps
filesystem IPC/publication out of the native event loop, including the
class of coupling implicated in [#128](https://github.com/CVX-Hull/enactive/issues/128).
The custodian outside the game owns file/SQLite publication. No native publisher
thread, detached helper, recovery journal or transport framework is needed.
Upstream save I/O, SDL readback/PNG CPU and arbitrary OS hangs are outside this
bounded publication guarantee; the original rename-stall cause remains unknown.

At startup, validate the exact inherited shared-lock descriptor/file identity and
socket type; retain the locked reference for the native lifetime. Set both FDs
close-on-exec before application main, the socket nonblocking and `SO_NOSIGPIPE`.
Never `LOCK_UN` a shared inherited reference. The parent closes its child socket
copy after spawn. The host/MCP inherits no native FD. Only the player host receives its selected provider credential; MCP and the game do not.
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
| `computer-request/3` | `schema,id,session,kind,expires_ms,continue_ms,input`;32hex IDs/session; kind `observe`, `input` or `pause`; null input for observe/Pause; `expires_ms` ≤ `continue_ms`, which Pause sets equal |
| `computer-target/2` | `schema,session,pid,window_id,paused,takeover_generation,latest_frame,error` |
| Frame | `name,capture_id,presented_ms,width,height,window_width,window_height,viewport`; name is logical `frame-N.png`, never a native filesystem path |
| `computer-receipt/2` | `schema,id,session,disposition,emitted_events,reason,frame`; disposition delivered/rejected/partial/unknown, emitted0..8, frame null or frame above |
| `computer-local/1` | Same fields, written by the custodian when the channel refuses publication before any byte is sent: disposition `rejected`, emitted0, frame null ([runtime](../../harness/computer/runtime.py)) |
| `computer-transport/2` | Same fields, written when native delivery cannot be resolved: disposition `unknown`, `emitted_events` null, frame null ([channel](../../harness/computer/channel.py)); input then stops permanently |

At claim, derive two local monotonic bounds once, from the original wall times, and
check them before every command event without renewal. The **start bound**
(`expires_ms`, capped5s) refuses a request's first command event. Once one is
emitted, the remaining events may follow until the **continuation bound**
(`continue_ms`, capped15s). A game that stalls between a key's down and up events
([#396](https://github.com/CVX-Hull/enactive/issues/396)) then still receives the
release. At either bound the request fails: before any event it is rejected; after
one it latches Pause, neutralizes owned presses and ends partial. A request first
read after its start bound (the game was busy before polling) is likewise rejected
with no events; a stale Pause is a protocol fault and fences. The custodian ends
both bounds at least250ms before its operation deadline and publishes nothing,
including the post-input capture, inside that margin, so native emission ends before
receipt collection does. Parent operation/run monotonic deadlines remain independent. Delivered means SDL event handoff, not
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

At MCP serialization, [the actor projection](../../harness/player_view.py) returns
the operation record `player-computer-operation/1`: the operation identity, status,
original receipts, source and handoff stay intact, but `deadline_monotonic` and
global `remaining` are absent. This covers immediate results, exact collection and
declared nested computer results in `player_result`. Native `computer-receipt/2`
contents remain original evidence.

**What the model reads of a computer call.** Receipts and identifiers say nothing
about the game and were most of the player's prompt, so the tool server
([MCP adapter](../../harness/player_mcp.py)) returns only what the player acts on.

| Call | The model reads | The host and the trace hold |
| --- | --- | --- |
| `computer_observe`, `computer_input`, `player_handoff` | `player-computer-result/2`, the short result below | The operation record, as the result's MCP `structuredContent`, which the host never forwards to the model |
| `computer_result` | The operation record itself: collecting an original operation is how the player sees its receipts, and it is called only after a result that was pending, partial or unknown | The same record as the result text |

The short result is closed JSON: `schema`, `status`; `source_id`, `width` and
`height` (the frame's size in the image pixels a click uses) when the operation has a
frame, and `image_unavailable:true` when its pixels were not returned; `operation_id`
while the status is `pending`, `partial` or `unknown`; and `reason`, which says what to
do next, for every status but `completed` and `sealed`. Completed with a frame:
`{"schema":"player-computer-result/2","status":"completed","source_id":"<session>-<n>","width":1280,"height":720}`.
An input with no frame omits those three fields. A partial or unknown delivery adds
`operation_id` and `reason` ("input is stopped and never replayed; call
`computer_result` with this `operation_id`"). A refused operation adds its `reason`
and its `operation_id` too: a refusal can follow a batch that was delivered in part,
and `computer_result` shows which actions were. The session, actor, kind, creation time, receipts, source record and
handoff issuance are not in it. The session database and the canonical operation
are unchanged; the host reads `source_id` and the full handoff issuance from the
record. `player-computer-result/1` is retired: the host rejects it as a handoff
receipt. Sealed traces in the old form stay readable by the evidence readers, which
take the operation and frame from the record where a result has one and from the
text otherwise.

Model-facing errors and transport uncertainty use
`player-error/2` and `player-transport/2`, preserving correction/control facts and
original collection identity without experiment countdowns. Unknown mechanical
versions fail with a bounded unsupported-result error, never raw pass-through.
Player-authored text, code, interpretation and state are opaque; keys named
`remaining` or `requests` inside them are not deleted. Canonical
`computer-operation/1`, internal HTTP/client errors and operator accounting remain
unchanged; the actor projection is not a database migration. An operation's
`receipts` hold `computer-receipt/2`, `computer-local/1` or `computer-transport/2`
values (table above).

Internal service envelopes, below the actor projection, are `player-response/1`,
`player-error/1` and `player-transport/1` ([service](../../harness/server.py),
[client](../../harness/player_client.py)), plus the per-tool results
`player-service-result/2` and `player-source-read/1`. [The actor projection](../../harness/player_view.py)
is their authority. It maps the internal error and transport envelopes to
`player-error/2` and `player-transport/2` for the model. These are layer names,
not older versions of the `/2` envelopes.

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
result and retained-source reads only. It cannot observe anew,
input, write a hint or create another handoff.
The host accepts only its direct handoff or collection of its own pending original
handoff. The driver verifies canonical issuance/context digest and actual old host/
MCP process-group quiescence before minting a successor under **original** limits.
The current sealed actor retains only independent cancellation, never new input. Retired actors cannot stop successors. Store I/O never holds the cancellation lock; a final stopped/stage check precedes quiescence. Unexpected closure/cancellation after sealing still permanently pauses; later
collection cannot restore succession. No game phase or identity requirement.

## Player knowledge and executable proposals

The player receives curated knowledge through the delivered-knowledge tools and
may submit a fallible `player_hint`. The journal is public trace and hint storage;
it is separate from the curator's assertions and cannot publish facts. Every
public player tool call, including host-local `player_finish`, requires `intent`:
nonempty one-line text of at most 512 characters. Optional `cites` contains at
most 16 unique nonempty IDs of at most 128 characters each. These are public
reports, not provider reasoning or input eligibility. The application and host
validate the metadata; only semantic arguments reach the mechanical runtime.

`player_hint` accepts `text` (1..8192 characters) and optional `source_ids`
(default empty, at most 16 unique IDs). Unknown source references fail. Its
`player-hint/1` record contains `id`, `actor_id`, `created_wall`, `text`,
`source_ids`, `intent` and `cites`. Referenced images establish availability,
not attention. The bounded source store preserves original PNGs and digests;
source read verifies the digest. Failure to retain a hint leaves ordinary input
available when custody is healthy.

The journal records public operation ID, actor, tool and arguments and refuses
conflicting reuse. Hint authoring is atomic and idempotent. `player_result`
collects only the actor's original hint as `player-service-result/2`, with
`operation_id`, `actor_id`, `kind:player_hint`, `status:completed`, `value` and
`grants_authority:false`. A metadata row alone does not establish submission;
uncertainty depends on a native operation or stored hint. Mechanical operations
keep their original collection and no-replay rules.

`player_handoff` accepts only a summary and common metadata. Its immutable
`player-handoff-context/2` contains `context_id`, `session`, `actor_id`, `summary`,
`created_wall`, `grants_authority:false` and `summary_is_hint:true`; it has no
record roots or player knowledge graph. The successor receives the summary as a
labelled predecessor hint. The final actor gets a refusal before sealing and can
continue or finish. The original actor fence, quiescence and finite limits remain.

## Composed operations and telemetry

Native intent/send/receipt timestamps retain their original wall/monotonic values.
Late collection never renews a source's `received_wall`. Host telemetry version 8
records public call metadata, payload hashes/counts, image references and bounded
ordinary assistant text; it excludes private reasoning and base64 history. Stable
frozen system context and the ongoing user objective are reused across actors.
Experiment quotas, final-actor policy and ending reserves remain in operator
accounting, outside the player prompt and tool views. Host decision-time and
custodian horizons stay distinct.

## Passive spectator reads and operator Pause

The custodian serves these loopback routes to the spectator and serves no page. Under
supervision the gateway ([observer operations](../components/observer-operations.md))
serves the page and relays them.

`GET /api/status` is `computer-status/2`. When a host is present,
`host.observed_attempts` reports observed HTTP starts across this admission.
`GET /api/source/ID` verifies and
serves this session's original retained PNG. A public read failure is unavailable
observer evidence, not a stop request; actor-side source integrity, input validation
and capture/publication fencing remain unchanged. The spectator creates no source
issuance, observation, operation, player record or capability. The custodian has no
activity, investigation or timing route: derived views come from the separate
read-only viewer and the offline evaluator ([evaluation contract](evaluation.md)),
which have no route into the custodian, the player context or any input.

`POST /api/pause` with `{}` unconditionally stops its actual receiving custodian,
then returns `computer-pause/1` with `session` and original `stop` facts. It never
waits for any projection, executor/application/database lock or prior status. The
supervised gateway takes `{"reason": "loop" | "fault" | "spend" | "other"}`, records the
reason in its terminal record and forwards `{}` here unchanged, so the custodian never
sees a reason. A delayed request can stop a replacement custodian; this emergency
meaning is explicit. Attribute confirmation to the response's actual session, not a
stale page/click. The page retains one last identified Pause receiver and its monotone
stop facts. A receiver outside the current/previous view is named explicitly, without
inferring chronological freshness from its opaque ID or replacing current diagnostics.
Its retained stop facts merge with later matching status/receipts; reordered
unconfirmed evidence cannot erase received confirmation.
Unsupported/lost responses leave confirmation unknown. Same-session stop facts are
monotone; an earlier status cannot undo later stop. Old/unidentified requests
cannot disable a deliberate fresh-session stop. No automatic retry, Resume or
authority renewal follows. Pause reasons never reach the actor or native stop interfaces.

## Reuse and qualification limits

The spectator view API ([evaluation contract](evaluation.md#spectator-view-api-spectator-view2))
is a separate read-only projection of recorded data. It has no actor/native effects,
grants no authority, replaces no current status/source and cannot block independent
Pause. No archive, collector or semantic control API is added to these runtime ports.

Socketpair/SQLite/HTTP/MCP and the player host adapter are maintained facilities. Thin framing and custody
integration cover the demonstrated native-publication/one-writer gap; no framework.
Pillow is a pinned project-local maintained codec for Python image views, replacing
an otherwise unnecessary PNG parser. The lead owns this integration; reconsider on
backend/platform incompatibility or recurring protocol fault. Keep applicable macOS
build compatibility. The pinned upstream source carries no game-semantic engine hooks:
[`tools/patch_game.py`](../../tools/patch_game.py) applies only the macOS
deployment-target patch and rejects a source tree holding legacy semantic hooks.

Primary contracts: [socketpair](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/socketpair.2.html),
[socket options](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/getsockopt.2.html),
[Python sockets/shutdown](https://docs.python.org/3.14/library/socket.html),
[SDL PNG RWops](https://wiki.libsdl.org/SDL2_image/IMG_SavePNG_RW),
[RWops buffer lifetime](https://wiki.libsdl.org/SDL2/SDL_RWFromMem),
[Pillow image operations](https://pillow.readthedocs.io/en/stable/reference/Image.html).
Native fixtures, source tests and organic gameplay are distinct evidence lanes.
This contract does not qualify cadence, learning benefit, survival duration, arbitrary
filesystem resilience, second-game, Unicode/IME or real-human takeover qualification.
