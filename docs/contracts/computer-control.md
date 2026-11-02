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
`computer-session/3` SQLite store and exclusive launch marker **before** DB/native
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
Pause. `player_handoff` takes no arguments. Before sealing, persist a canonical
immutable `player-handoff-context/2` packet holding only mechanical identity
(`schema,context_id,session,actor_id,created_wall,grants_authority:false`); it carries
no actor-written summary and no knowledge snapshot. The operation
binds `handoff:{schema:"player-handoff/2",operation_id,session,actor_id,context_id,
context_sha256,sealed_wall,grants_authority:false}`. A sealed token permits original
result, retained-source and player/context reads only. It cannot observe anew,
input, mutate memory, run a program or create another handoff.

**Capability classes.** `computer-session/3` actors have stage `active`, `sealed`,
`quiescent` or `reader`. A **reader** serves exactly one actor (`serves`) in one
`reader_role`, `level` or `recorder`: the store is unique on (served actor, role), so an
actor has at most two readers, one per role, and a third is refused. A reader is minted
only while that actor is active, and never sends input, observes, stops or seals. The
composition's per-class allowlist refuses every tool outside the reader's role profile;
the runtime's write authorization admits a `level` reader only for `player_level_keep`,
`player_level_replace`, `player_level_close` and `player_level_abstain`, a `recorder`
reader only for `player_episode_record` and `player_episode_abstain`, and never admits an
actor for any of them nor a reader for another role's write; `_guard` refuses a reader's
observe, input and seal; `/api/actor-stop` refuses it. Older session schemas
(`computer-session/2` and before) are not read by this store, which is created fresh;
readers of retained session databases accept only `/3`. A retained-source integrity
failure found during a reader's read still fences the run, as for any reader of that
storage. A reader serves only a `narrowed` actor, which writes no memory, and minting
either role refuses while more than one current Work record has `data.level == "subgoal"`
(the level's own subgoals, at most one by construction) or while a current one is not
`player-level/4`; other current Work is out of the level's scope and untouched.
Afterwards only the level's commits and the recorder's software closure change the
current subgoal. Minting fixes, like the level's staleness bound S, the stall test N
(`stall_settles`, 1..1000) and the confidence floor c (`confidence_floor`, 0..1); one
actor's two readers must be minted with the same N and c, since both derive the same
state from the store.
Readers are excluded from `max_actors` and from the "every prior actor quiescent"
succession test, so a live reader never blocks a successor. The composition registers
each capability's profile when it mints it (`flat` or `narrowed` actors, `level`,
`recorder`); a capability minted without a profile has no tools. [Profiles](../../harness/player_tools.py)
are the custodian's allowlist as well as each host's `enabled_tools`:
- `flat`: basic control, sources, memory append/read/query/context, program
  save/read/run, `player_result` and `player_handoff`;
- `narrowed`: the same without memory tools or program save;
- `level`: exactly `player_source` and the four terminal tools `player_level_keep`,
  `player_level_replace`, `player_level_close` and `player_level_abstain`. It has no log,
  memory, program, result or `computer_result` tool: the pushed pass input carries the
  episodes, the current subgoal and recall;
- `recorder`: exactly `player_source`, `player_episode_record` and
  `player_episode_abstain`. The actor profiles refuse all six reader write tools.

`player_log_read` and `player-log/1` no longer exist. The driver reads the served actor's
operations in-process through `Application`; no tool serves them.

There is one input writer, the active actor. A level-arm actor writes no memory; the
custodian's commit and settle paths are then the only memory writers.
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

**Episodes, binding and the level commit** ([ADR-007](../decisions/007-player-subgoal-level.md),
level v4). Every closed episode of the served actor settles into player memory as exactly
one `claim` record (`player-episode/1`), and the level commits against state the custodian
derives from those claims. The roles propose; software counts.

*Episode settles.* The claim's `data` carries `level: "episode"`,
`level_contract: "player-episode/1"`, `settled` (`recorded`, `abstained`, `failed` or
`dropped`), `writer` (`recorder` for the first two, `software` for the others), the
`session`, served `actor_id`, `first_position` and `last_position` (1-based per-actor
operation positions, inclusive) and `subgoal_id`, the level subgoal current at the episode's
first input or null.
- `recorded` adds `attempted`, `counterpart`, `observation_status`, `residual`, `changed`,
  `confidence`; `abstained` adds `reason_code` and `reason`; `failed` and `dropped` add
  `reason`. Only `recorded` carries marks. The claim's `sources` are the cited frames, at
  most 4, copied into player memory in the same transaction; `text` is `attempted` (or
  the reason).
- `player_episode_record(attempted≤1024, counterpart≤512 (may be empty),
  observation_status[≤8 of seen|not_yet|contradicted], changed≤1024 (may be empty),
  residual≤1024 (may be empty), confidence 0..1, sources≤4)` is one flat object of portable
  schema keywords with every property required. `changed` is what visibly changed in the
  player's own state between the baseline frame and the episode's last frame, citing the
  frames that show it. The length of `observation_status` must equal the number of expected
  observations of the pushed subgoal, or be empty when none was pushed. Each cited source
  must be in the episode's `sources` (below).
- `player_episode_abstain(reason_code: unreadable_frames|no_player_action|other,
  reason≤1024, sources≤4)` settles the episode as `abstained`, with no marks.
- Receipts: `player-episode-record/1` `{schema, status:"recorded", settled, first_position,
  last_position, subgoal_id, counted, closed, observations, stalled, records}` and
  `player-episode-abstain/1` of the same shape with `status:"abstained"`. `counted` is
  whether the claim counts toward the current subgoal's marks; `closed` whether it closed
  it; `observations` and `stalled` are the derived state after the claim, null when the pushed
  subgoal is not the current one.
- Schema or source errors are fixable tool errors that keep the bound episode. A repeated
  request identity with the same tool and arguments returns the retained result.
- `Application.bind_episode(recorder, first_position, last_position, subgoal_id)`, called
  by the driver under `Application.serial`, binds the recorder's pass to one episode and
  returns what the driver pushes: the operations (key tokens, positions, statuses, result
  source ids), the subgoal's id, text and ordered expected observations, and `sources`, the
  frames the recorder may cite: the result frame of each operation in the range, led by the
  baseline frame (the result capture of the last `input`, not observe, before the range). It
  refuses a range outside
  the log, one overlapping an already settled episode, and a subgoal id that is not a
  `player-level/4` level subgoal.
- `Application.settle_episode(recorder, first_position, last_position, subgoal_id,
  settled, reason)` settles an episode the driver reports as `failed` or `dropped`, with
  `writer: "software"`, no marks and the recorder as record actor. An episode settles
  exactly once: any settle overlapping a settled range is refused.
- The memory-append paths other than the custodian's own commit, closure and settle paths
  refuse any record that sets the reserved `data.level` (any value), `data.level_contract`
  or `data.writer`, or `data.by` equal to `"software"` (`player_memory_append` and
  `Memory.append`/`append_many`), so an actor cannot forge a level record, a settle or a
  software closure. Recall and every count
  trust only claims whose contract is `player-episode/1` and whose `writer` stamp matches
  how they settled, in any session.

*Derived state (read time, never stored on the Work record).* For the current subgoal *g*
the custodian reads the trusted episode claims committed after *g* whose `subgoal_id` is
*g*'s id (others are ignored), across sessions of the one store.
- **Marks** count only from `recorded` claims with `confidence` at least the floor *c*. An
  observation is `seen` if its latest counted `seen`/`contradicted` mark is `seen`,
  `contradicted` if it is `contradicted`, else `not_yet`.
- **Stall.** *g* is stalled after N consecutive settled claims since *g* with nothing newly
  seen; an `abstained`, `failed` or `dropped` settle, and a `recorded` one below *c*, count
  as nothing newly seen. N and *c* are fixed at reader minting.
- **Closure.** The `recorded` claim that makes every expected observation `seen` appends,
  in the same `Memory.append_many` transaction, a `correction` superseding *g* with the
  recorder as record actor, `data.outcome: "achieved"`, `data.by: "software"`,
  `data.level: "subgoal"`, `data.level_contract: "player-level/4"`, the counted claims' ids
  in `supports` (those that last made each observation seen first, at most 16) and their
  newest frames as `sources` (at most 16). Replace requires at least one expected
  observation, so closure is never vacuous.
- A start pass is refused keep and abstain for a stalled subgoal like any other pass.

*Level terminals.* The level manages only its own subgoal: the current Work records with
`data.level == "subgoal"`, at most one by construction. Software resolves it, so the
model supplies neither a record id nor a version. Each terminal tool is one flat object of
the portable schema keywords (`type` on every node, string enums, no `const`, `anyOf`,
`oneOf`, `$ref` or nested objects); every property is required, and the server-side
validator is closed (`additionalProperties: false`) without any model dependence on it.
- `player_level_keep(reason≤1024, sources≤16)` writes no record; the receipt says kept and
  gives the current id;
- `player_level_replace(text≤2048, expected_observations 1..8×512, status:open|blocked,
  confidence 0..1, sources≤16, previous_outcome:none|achieved|failed|abandoned|revised,
  previous_reason≤1024)` writes the Work record, plus a superseding correction for the
  current subgoal when there is one (a `revised` outcome makes the correction support the
  new Work); `sources` are the replace's sources for both records. `previous_outcome` is
  `none` exactly when there is no current subgoal, and `previous_reason` is empty only
  with `none`;
- `player_level_close(outcome:achieved|failed|abandoned, reason≤1024, sources≤16)` needs a
  current subgoal and writes the correction only.

A wrong-state call (keep or close with no current subgoal; a replace whose
`previous_outcome` is `none` while a subgoal is current, or is not `none` while none is
current, or lacks its `previous_reason`) is a tool error that names the current subgoal
state (its id, status and leading text, or "no current subgoal") and the valid tool for it.
So are the v4 refusals: while the subgoal is **stalled**, `player_level_keep` and
`player_level_abstain` are refused with an error naming `player_level_replace` and
`player_level_close`; while an observation is **contradicted**, a keep must cite in its
`sources` a frame of any counted claim (committed after the subgoal, for its id, at or
above the floor) that marks a contradicted observation `contradicted`, not only the
latest such claim; otherwise it is refused (naming the allowed frames, or saying keep is
unavailable when none cited a frame). A schema, unavailable-source or other fixable error is likewise a tool error. All
keep the bound for a corrected resubmission; cited source bytes are read and verified before
the timeliness check.

*Binding.* `Application.bind_level(level)` is called by the driver under
`Application.serial` when a level pass is pushed, replacing any log read. It binds the
pass's position to the highest `last_position` over the served actor's settled episodes in
this session (so a later episode dropped before an earlier one is recorded never moves it
back), whatever their outcome (record, abstain, failure or drop), or 0 before any
has settled; recalled earlier-session records never bind. It also binds the current
subgoal id (or none). A served actor that is not active binds nothing. The model never
supplies either. `Application.release_reader(reader)` forgets a binding at pass end.

*Timeliness.* A terminal call first checks that the current subgoal still has the bound
id: if a closure or a replace happened since, the call is a discard (reason "Current
subgoal changed since the pass began"). Otherwise it commits only if a position is bound,
the run is not stopped, fenced or past its deadline (a user Pause or takeover changes the
game without custodian input), the served actor is still active, and it moved fewer than S
`input` operations past the bound (S fixed per level reader at minting); a reader's store
is one live session, so no session boundary can intervene. Otherwise return
`player-level-commit/4` `status:"discarded"` with the `action`, reason, bound position,
inputs since and the pushed `subgoal_id`; a discard writes nothing to either store and
ends the pass.

A committed replace or close appends, under `Application.serial` and in one
`Memory.append_many` transaction, the exact bytes of its cited sources (idempotent
immutable copies; a keep registers no frame and only checks its citations are available),
a new Work record for a replace, one superseding correction for a close or a replace over a
current subgoal, and the service row (named for the tool) with its final result. The
receipt is one schema, `player-level-commit/4` `{schema, status, action:keep|replace|close,
reason, position, inputs_since, staleness_inputs, subgoal_id, derived, kept, records}`;
`subgoal_id` is the id bound at push, `derived` the pushed subgoal's `{observations,
stalled}` (null with no subgoal), and a keep gives the current id in `kept`. Every record's
`data` carries `level:"subgoal"`, the software-stamped `level_contract: "player-level/4"`,
served actor, session and bound position; the record actor is the level reader. Minting a
reader refuses a store whose current level Work is not `player-level/4`: migrate or start
a fresh player store. A repeated request identity with the same tool and arguments
returns that retained result without recommitting. `player-memory/1` and
`player-record/1` are unchanged.

`player_level_abstain(reason_code, reason≤1024, sources≤16)` ends a pass without a change.
`reason_code` is `insufficient_evidence`, `transient_screen_state`, `no_change_needed` or
`other`; `sources` may be empty and, if cited, must be available. It writes nothing to
memory, clears the reader's bound as a terminal call does, and returns
`player-level-abstain/2` `{status:"abstained", reason_code, reason}`. It is refused while
the subgoal is stalled. The actor and flat profiles refuse it.

*Intent and recall.* `Application.intent(actor, audience)` (the host-internal
`player_intent` tool, `tail`) returns `player-intent/2`: `{schema, session, actor_id,
audience, pass_index, subgoal, age, recall, grants_authority:false}`. `subgoal` holds
`record_id`, text, sources, `status`, `confidence`, `expected_observations` as
`{text, status:seen|not_yet|contradicted}`, `stalled`, `contradicted` and `counts`;
`age` as before (seconds, inputs since commit, same actor and session). `recall` is
`{basis: ranked|recent, items}` over the trusted `recorded` claims of all sessions, each
item `{record_id, session, same_session, first_position, last_position, subgoal_id, attempted,
counterpart, residual, changed, observation_status, confidence, sources, first_source,
score, exploration}`. Ranking is software (`harness/player/recall.py`): BM25 (k1 = 1.2, b =
0.75) over `attempted`, `counterpart`, `residual` and `changed`, the query being the
subgoal's text and expected observations, multiplied by the recorder's confidence and by 1.5
for a non-empty residual. With no current subgoal recall is the most recent records
(`score` null). The `level` audience gets the top 10; the `tail` gets the top 2 plus one
exploration item: an earlier-session record outside the top 10 drawn uniformly with a
seed from the session id and the level's pass index (the number of `bind_level` calls).
Byte truncation of what is shown belongs to the host. `Application.settled_episodes` and
`subgoal_counts` give the driver the settled records and per-subgoal counts (episodes,
seen, contradicted, closures, failures) for the level's pushed input.

*Capacity.* If remembering fails (a storage fault, or cited frames that do not fit the
256 MiB source store, which evicts nothing), `Application.remember_failure` is set and
reported in `/api/status`. The level and the recorder then refuse every tool, bind and
mint for the rest of the session; the actor's input is unaffected. The driver's
`settle_episode` may still try to record the failure.

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
including replacement while Watch is hidden, with missing/invalid clocks labelled;
it does not establish visibility, paint or useful progress.

## Passive spectator projections

`GET /api/status` remains `computer-status/1`. `GET /api/source/ID` verifies and
serves this session's original retained PNG. A public read failure is unavailable
observer evidence, not a stop request; actor-side source integrity, input validation
and capture/publication fencing remain unchanged. The spectator creates no source
issuance, observation, operation, player record or capability.

`GET /api/activity` has no body/query and returns `observer-activity/1`: actual
`session`, session-local snapshot `revision`, `entries`, `latest_statement`,
`omitted_entries` and `coverage`. At most200 complete entries and256KiB of encoded
JSON (including newline) survive. Host entries retain original actor/trace ordinal,
kind, available request/tool-call/operation/program IDs, original wall time and
actor-local monotonic milliseconds. Computer entries retain original operation ID,
actor, kind, creation wall time, status, bounded reason, exact source metadata and
separate original/additional-collection disposition lists (at most64 per list,
with an explicit omitted flag). Identity joins require actual recorded references;
cross-process wall ordering is approximate, not causal evidence.

Host projection allowlists lifecycle/request/response, public assistant text,
tool names/dispositions, handoff and retry events. It excludes raw tool arguments,
request bodies, private reasoning and credentials. IDs are at most256 UTF-8 bytes;
ordinary status/reason text is bounded. Narration retains at most8192 UTF-8 bytes,
original `omitted_bytes` and separate `display_omitted_bytes`; omitted original text
is not recoverable. Bounded latest narration remains separately readable even if
it precedes the current tail. An absent statement does not prove silence outside
the retained coverage or model attention.

Coverage reports projected host events/errors, computer operation count and each
producer's availability. Unavailable computer counts and incomplete total omission
counts are `null`, not zero. Retained-field/text omission counts cover only the
projected entries, not unknown missing producer data. A failed read/parse is a labelled gap, not measured zero,
game failure or renewed authority. Computer reads use a separate read-only SQLite
transaction with finite busy/query bounds. A disposable host cache reuses the
driver's original trace consumer; no second durable event log is maintained.

`POST /api/pause` with `{}` unconditionally stops its actual receiving custodian,
then returns `computer-pause/1` with `session` and original `stop` facts. It never
waits for activity, executor/application/database locks or prior status. A delayed
request can stop a replacement custodian; this emergency meaning is explicit.
Attribute confirmation to the response's actual session, not a stale page/click.
The page retains one last identified Pause receiver and its monotone stop facts
separately from bounded activity history. A receiver outside the current/previous view is named explicitly,
without inferring chronological freshness from its opaque ID or replacing current
diagnostics. Its retained stop facts merge with later matching status/receipts;
reordered unconfirmed evidence cannot erase received confirmation.
Unsupported/lost responses leave confirmation unknown. Same-session stop facts are
monotone; an earlier status cannot undo a later stop. Old/unidentified requests
cannot disable a deliberate fresh-session stop. No automatic retry, Resume or
authority renewal follows. Actor/native stop interfaces remain unchanged.

## Reuse and qualification limits

The [recorded investigation artifact](observer-investigation.md) defines a separate
bounded passive artifact for attached current-session snapshots and selected closed
cases. Its GET/POST observational projection has no actor/native effects. Local import and the
recorded-only HTML share a renderer. Imported IDs/data grant no actor authority,
replace no current status/source, and cannot block independent Pause. No archive,
collector or semantic control API is added to these runtime ports.

Socketpair/SQLite/HTTP/MCP and the player host adapter are maintained facilities. Thin framing and custody
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
