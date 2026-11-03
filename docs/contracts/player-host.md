---
owner: lead
review_trigger: Driver/host invocation, route envelope, telemetry, settlement, isolation or adapter changes
status: active
---

# Player host contract

`player-host/8` is the one current boundary between the [campaign driver](../../tools/campaign_player.py)
and the program that hosts a deciding player, one pass of its subgoal level or one pass of its episode recorder
([ADR-007](../decisions/007-player-subgoal-level.md) candidate). The host turns frozen context, a
frozen provider route and the actor's MCP table into model calls and sequential
player tool calls. The driver owns actor minting, original limits, process-group
closure, handoff verification and succession. Any adapter that satisfies this page
and passes the [conformance suite](../../tests/test_player_host_contract.py) is
substitutable; no driver, packager or gameplay page depends on a particular
adapter. The [current adapter reference](../../tools/player_host/README.md) owns
its provider serializers, closed route `model` fields and limits.

## Adapter selection

A `campaign-run/7` package freezes `host`: `{"argv": [...]}` with 1–8 strings.
`argv[0]` is an absolute existing regular file (an adapter executable or its
interpreter); every later entry is a canonical project-local regular file covered
by the clean source commit. The driver and package validator append only the mode
and the arguments below. There is no adapter registry, default adapter, fallback
or resumed host. `campaign-run/2` packages and their `node` field are inert history.

## Modes

`ARGV validate --config ROUTE --mcp-config MCP --model ID --effort EFFORT` exits
zero exactly when the adapter accepts the route, MCP table, model and effort. It
reads only those files, needs no credential or network and finishes within 10
seconds. The package validator runs it with only `PATH` and `LANG`.

`ARGV run --config ROUTE --mcp-config MCP --context CONTEXT --model ID --effort EFFORT --timeout-seconds S -o FINAL`
hosts one actor. Each flag occurs exactly once; unknown, repeated or missing
arguments settle unsuccessfully. Input files and the prompt on stdin are each at
most 1 MiB. `S` is the actor's original host allowance in seconds; the host
enforces it and also stops on `SIGINT`/`SIGTERM`. `FINAL` is reserved by the
driver; the host writes the terminal player report there only after successful
`completed` settlement and leaves it unchanged otherwise.

The driver starts the host in a new session with `cwd` at the project root, stdout
to `host.jsonl`, stderr to `host-stderr.log` and an environment containing only
`PATH`, `LANG` and the route's `api_key_env` variable. Exit status is zero exactly
when the final `settled` event has `ok: true`.

## Route envelope

The frozen route is one closed JSON object with `schema: "player-host/8"`, `role`,
`intent_tail_bytes`, `model`, `api_key_env`, `max_requests`, `max_context_images`,
`context_image_block`, `request_timeout_seconds`, `service_tier` and
`max_cost_nano_usd`. The last field is a canonical decimal integer string for
the host's monetary allocation. `role` is
`actor`, `level` or `recorder`. `intent_tail_bytes` is null or, for an actor only, exactly 1024: the one fixed allocation of the intent tail (see below).

Each actual HTTP attempt, including an eligible retry, reserves the full
physical context and output cost before fetch. The route stores rates as plain
decimal strings of at most 64 characters. Both admission and the host round
these exact rates up to nanodollars per token. The SDK receives numeric rates
for its telemetry. A framed terminal stream marker and validated provider counts settle
at the upper input and output rates or the reported provider cost, whichever
is greater. Uncertain usage consumes the full reservation. Exhaustion settles
`request-budget-limit` before another fetch. A violated bound ends the host and
retains the observed contradiction. The request's `request-fetch-start`
records its reservation and `request-cost` records its charge and reconciliation
status. The final `settled.money` reconciles those records to the allocated lease.
`max_context_images` is the hard peak of pixel images in one request.
`context_image_block` (1 to that peak) is the count-only block in which the oldest
historical images beyond the peak are replaced by markers; block 1 replaces exactly
the overflow. The driver and package validator
read only: `model.id`, `model.name`, `model.cost.{input,output,cacheRead,cacheWrite}`
(dollars per million tokens), `model.contextWindow`, `model.maxTokens`,
`api_key_env`, `max_requests` and `service_tier`. The adapter owns every other
closed `model` field and rejects routes it cannot serve without fallback. The
driver lowers `max_requests` to the actor's remaining original allowance before
launch. Routes carrying any other schema, including `player-host/1` and earlier
adapter-named route schemas, are rejected; their packages and traces are inert history. One logical inference
request uses at most two charged attempts, each counted against `max_requests`;
the adapter's host reference defines which transient refusal classes are retried.

## Telemetry

Stdout is JSONL telemetry version 2. Each line is one object with `type`; the
driver ignores kinds it does not account for, and observers project only known
kinds. Required semantics:

| Event | Contract |
| --- | --- |
| `host-start` | Exactly once and first in any run that admits its arguments and inputs, with `telemetry_version: 2`, `schema: "player-host/8"`, `role` and `intent_tail_bytes`; the driver rejects any other schema. |
| `mcp-connected` | Once the MCP child is connected, before tool discovery. A level's first pass waits for the actor's first `request-start` instead, which follows the tool checks. |
| `level-pass` | Level role only, once after tool discovery. |
| `level-commit` / `level-discard` | Level role only, per `player-level-commit/6` result of `player_level_keep`, `player_level_replace` or `player_level_close` (never for a local tool error, so a rejected call emits neither), with `receipt_schema`, `action` (`keep`, `replace` or `close`), `reason`, `position`, `inputs_since`, `staleness_inputs`, `subgoal_id` (the subgoal bound at push, or null), `derived` (`{observations, stalled}` or null), `record_ids` and `kept`. Either one ends the pass. |
| `level-abstain` | Level role only, per valid `player-level-abstain/3` result of `player_level_abstain` (never for a local tool error), with `request_id`, `tool_call_id`, `reason_code` and `reason`. It ends the pass. |
| `level-uncertain` | Level role only, when a terminal tool's result is a `player-transport/1` unknown receipt (the adapter lost the response and, for a reader, offers no collecting tool), with `request_id`, `tool_call_id`, `tool` and `identity` (the receipt's operation id). It ends the pass, which settles `ok: false` with reason `level-uncertain`; the driver reconciles `identity` from the store afterwards. |
| `level-terminal-call` | Level role only, per terminal tool call in an assistant message (at message end), with `request_id`, `tool_call_id`, `tool` and `arguments_error` (the arguments did not parse). A call with no matching `tool-start` was refused before dispatch. |
| `level-reserved-request` | Level role only, once per logical request that offers only the terminal tools, with `request_id` (the logical request's first attempt), `logical_request_id` and `offered_tools`. |
| `episode-pass` | Recorder role only, once after tool discovery, with `frames`: the pushed `{source_id, role}` manifest. |
| `episode-frame` | Recorder role only, once per pushed frame the host read, before the first request, with `source_id`, `role`, `media_type`, `bytes` and `sha256`. |
| `episode-record` | Recorder role only, per `player-episode-record/3` result with `status: "recorded"` of `player_episode_record` (never for a local tool error), with `request_id`, `tool_call_id`, `first_position`, `last_position`, `subgoal_id`, `counted`, `closed`, `observations`, `stalled` and `record_ids`. It ends the pass. |
| `episode-abstain` | Recorder role only, per valid `player-episode-abstain/3` result of `player_episode_abstain`, with `request_id`, `tool_call_id`, `first_position`, `last_position`, `subgoal_id`, `record_ids` and the call's `reason_code` and `reason`. It ends the pass. |
| `episode-uncertain` / `episode-terminal-call` / `episode-reserved-request` | Recorder role only; as `level-uncertain`, `level-terminal-call` and `level-reserved-request`, for the episode tools. |
| `intent-tail` | Actor with a tail, per request, with `available`, `record_id` (the subgoal's), `tail_bytes` (the whole tail, at most 1024), `surfaced_bytes` and `omitted_bytes` (summed over the parts), `skipped_items` (recall items left out for want of a usable source id), `parts` (per part `{part, bytes, omitted_bytes}`) and `age`. |
| `request-start` | One per provider HTTP attempt, including failed and provider-only retries, with `request_id` `request-N` contiguous from 1 and never above `max_requests`, and `logical_request_id` `request-K` (the K-th inference request, shared by its retries). |
| `response-complete` | Per completed attempt; `usage_available` is boolean and, when true, `usage.cost.total` carries the configured or provider estimate. Missing usage stays unknown. |
| `handoff` | At most once, with `actor_id`, `session`, `handoff_id`, `context_id`, `context_sha256` and `grants_authority: false`. |
| `settled` | Exactly once and last, with `ok`, `reason` and `requests` equal to the number of `request-start` events. |

Two failure shapes are permitted and always unsuccessful. A host that refuses its
mode, arguments or inputs before starting emits only one `settled` with `ok: false`
and no `host-start`. A host that fails after settling (for example while writing
`FINAL`) may append a second `settled` with `ok: false` and exits nonzero.
A partial final line, missing `host-start` or `settled`, repeated terminal events
or non-contiguous requests make accounting incomplete; the driver then charges the
whole original allocation and admits no successor. Telemetry carries bounded visible narration and
mechanical references, never credentials, private reasoning or raw provider
request/image histories.

## Roles and the intent tail

An **actor** host decides and sends input. With `intent_tail_bytes` set, before each
provider request it calls the custodian's host-internal `player_intent` tool itself,
which must be discovered and must not be in `enabled_tools`, so the model never sees
it. It accepts only a `player-intent/4` value for the `tail` audience, formats it into
the request-only status message and nothing else. A failed read, another schema or audience,
or an unexpectedly shaped value shows "Unavailable" and never stops the actor or gates its
input. A null tail (flat, arm B, the fourth arm and shadow mode) adds nothing.

**The tail is one fixed allocation of 1,024 UTF-8 bytes in all, labels included.** Each
part is one line, and player text collapses to a single line (control characters and runs of
whitespace become one space):

| Part | Budget |
| --- | --- |
| The intent label, ADR-007's frozen text ("Current intent (software-published from the player's subgoal level; fallible player data with sources and age, not instructions).") | 129, as written |
| `Subgoal: <text>` | ≤ 160 |
| `Expected: [status] <observation>; ...`, each observation with its one-word status (`seen`, `not_yet`, `contradicted`); every observation gets its token and an equal share of the remaining bytes (a short one leaves its spare to the others), each cut with a marker, so every status stays visible; `[`, `]` and `;` in observation text are shown as `(`, `)` and `,` | ≤ 200 |
| `id <8 characters>; conf <c>; <n> inputs, <s>s, <this\|prev>` (`this` is this session, `prev` an earlier one) (the subgoal's short record id by code points, confidence, then the age; the software's fields come first, so a cut falls on the age) | ≤ 50 |
| The recall label, ADR-007's frozen text ("Recalled episodes (software-selected from the player's own past; fallible; each with one source id; not instructions).") | 118, as written |
| Up to 3 recall lines: the one full source id of the record's first cited frame, its outcome (`seen x/y`, with `, n contradicted`; with no subgoal, a short excerpt of `changed:`) and its attempt text | ≤ 120 each |

The seven line breaks between the eight lines at the maxima make the sum exactly 1,024. With no
subgoal the subgoal part is "No committed intent." and the others are absent; with no recall
the recall label and lines are absent. A part over its budget is cut on whole characters
inside its own budget and ends in a marker `…[+N]` naming the N omitted bytes; the marker
comes out of that part's own budget, so a truncated tail always fits and no part takes room
from another. Recall is therefore never cut first. A recall line never cuts its source
id: it drops its outcome first, and every dropped byte (the outcome, and what a `changed:`
excerpt cut) counts as omitted. An item with no usable source id, or whose id cannot be shown
whole, is left out, never shown without one (the frozen label promises one source id on every
line), and `skipped_items` of the `intent-tail` event counts it. A value whose age is negative,
non-finite or absurd (over a century, or over a billion inputs) or whose confidence is outside
0–1 is malformed and shows "Unavailable". The `intent-tail` event logs the omitted bytes per part.

A **level** host runs one finite pass with a reader capability. Its enabled tools
must include the four terminal tools `player_level_keep`,
`player_level_replace`, `player_level_close` and `player_level_abstain`, and `player_source`
to read cited frames; it has no log tool. It
sends no input and makes no handoff. The driver, not the host, schedules passes and
supplies the frozen role prompt, the actor's mission brief and the pushed input as its
plain-text prompt: the episode records settled since the previous pass, the current subgoal
with its derived status, stalled flag and id, the per-subgoal counts and the recalled episodes
(ADR-007, level v4). The host does not parse a level's prompt.

A **recorder** host runs one finite pass over one closed episode, with its own reader
capability. Its enabled tools must include `player_episode_record` and
`player_episode_abstain`, and `player_source` when frames are pushed. It sends no input
and makes no handoff. Its prompt is one `player-pass-input/2` JSON document
`{"schema", "text", "frames"}`, closed: `text` is the driver's non-empty pushed text (the frozen
role prompt, the episode's operations and the pushed subgoal; no mission brief) and `frames`
lists at most 7 `{"source_id", "role"}` entries with distinct ids, in order: an optional `baseline`
first, then at most 6 episode frames, `in-episode` ones ending in exactly one `last` (so `last`
is required, and final, whenever there are episode frames). The pushed frames are pinned: they
count toward `max_context_images`, and image eviction never omits them, so a later
`player_source` read evicts an older read instead of the baseline. A document whose frames do
not leave room for a read (`frames.length >= max_context_images`) is refused as
`invalid-pass-input` before `host-start`: **the driver's recorder peak must be at least its
frames + 1.** The reads of one assistant turn all sit in the next request, so a
`player_source` call that would take it over the peak (pinned frames plus the turn's reads
above `max_context_images`) is refused without dispatch as a fixable `tool-refused`, reason
`episode-image-peak`, naming how many frames can be read at once and that earlier reads are
evicted first; the recorder reads one frame per turn. A request that would still exceed the
peak stops the pass before it is sent (`context-image-limit`), as a backstop only. Frames are far
larger than the 1 MiB prompt bound, so the host reads each through the recorder's own
`player_source` before the first request and puts the text, then for each frame a marker line
`Frame <source_id> (<role>):` and the image, into the first user message. A frame it cannot
read (an error, or no image) settles `ok: false` with reason `frame-read-failed` before any
request; a malformed document settles `invalid-pass-input` before `host-start`. Every other
rule below holds for a recorder with its own names: the `episode-` events and settlement
reasons `episode-no-record`, `episode-final-refusal` and `episode-uncertain` replace the
`level-` ones, `tool-refused` reasons are `episode-ended`, `episode-reserved` and `episode-image-peak`, and the
terminal tools are the two episode tools. A host enables exactly its own role's terminal
tools: any other role's, or any at all on an actor, settles `unexpected-pass-tools` before
any request.

**A level pass ends on a terminal call.** Every provider request of a level
host carries `tool_choice: "required"` (an actor's does not), so the model cannot end
in prose. The pass ends, with no further tool dispatch (later calls in the same batch
are refused with `tool-refused` reason `level-ended`) and settles `completed`, after
either a `player_level_keep`, `player_level_replace` or `player_level_close` result that
becomes a commit or discard (`level-commit` or `level-discard`) or a valid
`player_level_abstain` result (`level-abstain`). A rejected terminal call (a tool error)
does not end the pass; the model may correct it within the pass allowance. A level pass
that ends any other way without such a result, for example a text-only terminal
response, settles `ok: false` with reason `level-no-proposal`; a failure that was already
latched (a provider error, the request limit or the deadline) keeps its own reason. The
level's text is never read.

**Lost transport on a terminal call.** A terminal tool whose response the adapter lost
returns `player-transport/1` with `status: "unknown"` and `collect_with: null` (a reader
has no collecting tool). The host emits `level-uncertain`, ends the pass with no further
dispatch and settles `ok: false`, reason `level-uncertain`. Whether the call committed is
known only to the player store, and the lost call may still be waiting on the
application's serial lock in a handler thread. After the pass the driver therefore takes
that lock once and, in the same hold, clears the reader's bound and writes a tombstone
`service_operations` row (a row with no result) for every uncertain identity that has no
row; a later arrival of that identity is refused as an identity conflict and writes
nothing. It then reports each identity as `committed` with its record ids (a row with a
result exists) or `absent` (it wrote the tombstone: a discard writes no row, so a
discarded call and one that never arrived are both `absent` and changed nothing), and
counts it in the pass receipt. The identity is never replayed.

**Reserved terminal requests.** Requests are counted as logical requests, one per
inference request whatever its provider retries. `logical_request_id` is `request-K`
for the K-th logical request, in both `request-start` (every attempt of the request
carries the same value) and `level-reserved-request`; `request_id` is still the HTTP
attempt number. A level or recorder host declares only its own terminal tools (four, or the two episode tools) to the model on a
logical request when, at its start, either the HTTP attempts left (`max_requests - R`,
R the attempts already made) or the logical requests left (`max_requests - (K - 1)`)
is two or fewer, so retries that spend the attempt budget bring the window forward
instead of ending the pass before it. The history and the executable tool set stay
unchanged (the adapter's mechanism is in its README). A provider retry resends its
logical request's declarations; the HTTP attempt cap `max_requests` still bounds
attempts. Each such request emits
`level-reserved-request` with `request_id`, `logical_request_id` and `offered_tools`, and
its resource status says that only the pass-ending tools are offered. A non-terminal
tool call on such a request is executable but refused without dispatch (`tool-refused`,
reason `level-reserved`) with a message naming the terminal tools and ending in the fix line.
A pass of two requests or fewer is terminal-only throughout. A
terminal call refused (a validation or custodian error) on the last allowed request
leaves no budget to repair it and settles `ok: false` with reason `level-final-refusal`,
distinct from `request-limit` (the limit reached after an ordinary tool or a provider
retry).

**Refusal text.** A level or recorder host's validation refusals of the terminal
tools name each failing field path, the rule, the allowed values or limits from the
tool's schema and the received value truncated to 120 characters, then a minimal valid
example call for that tool; a terminal tool's refusal ends with "Fix the call and resend
it; abstaining is not the remedy for a fixable call." The `tool-validation-feedback`
event retains the original SDK result, the call ID and the projected text. The
`player_level_replace` example is followed by a line saying its `previous_outcome` of `none`
is valid only when there is no current subgoal, and the `player_episode_record` example by a line saying its empty `observation_status` is valid only when no subgoal was pushed. A terminal call whose arguments the SDK
changed (`tool-arguments-changed`) is refused naming the changed fields and ends with the
same line, and so does every custodian refusal of a terminal call (wrong subgoal state,
unavailable cited sources, source capacity, invalid arguments), which names the offending
ids, sizes or limits and the valid action within the 600-character error bound. An
actor's refusals are the SDK's own text.

## Settlement and handoff

`settled.reason` is `completed` for a terminal player report, `handoff` after a
handoff, or an adapter failure reason with `ok: false`. The host settles `handoff`
only for a direct sealed `player-handoff/2` issuance returned by `player_handoff`,
or exact collection through `computer_result` of its own pending original handoff,
naming its own actor and session. After a handoff it dispatches no further tool
call and closes its MCP child before exiting. The driver independently verifies the
canonical issuance, frozen context digest and actual host process-group absence
before minting a successor. User Pause, uncertainty or failed closure never becomes
a resumable handoff.

## Isolation

The host loads no coding-agent application, shell or file tools, personal settings,
resource discovery, resumed session, compaction, reconnect, replay or model
fallback. Only the selected credential variable reaches the host; it never appears
in files, argv, telemetry, stderr, URLs or headers other than the provider request.
The MCP child receives only `PATH` and `LANG`. The host calls tools sequentially
through the frozen MCP table; it never sends game input except through those tools.
Host attempts and seconds are separate from custodian mechanical resources.

## Conformance

The [contract suite](../../tests/test_player_host_contract.py) drives each listed
adapter only through this page's argv, files, environment, stdout and exit status,
with a scripted reference provider and an MCP double. It covers validation,
argument refusal, completed and handoff settlement, telemetry accounting through
the driver's own reader, credential isolation, cancellation with MCP-child closure
and deadline expiry. An adapter for another provider wire format supplies an
equivalent provider double. Passing the suite is interface evidence only: it does
not qualify a model, provider, latency or gameplay outcome. The
[adoption record](../acceptance/2026-10-31-host-neutral-player.md) retains the first
conformance run and an offline native driver preflight through this contract.
