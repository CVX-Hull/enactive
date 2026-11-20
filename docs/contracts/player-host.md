---
owner: lead
review_trigger: Driver/host invocation, route envelope, telemetry, settlement, isolation or adapter changes
status: active
---

# Player host contract

`player-host/8` is the one current boundary between the
[campaign driver](../../tools/campaign_player.py) and the program hosting a
deciding player. The host owns the model/tool loop and player context. The finite
test driver owns original limits, process-group closure and verified succession.
The player receives its user objective and actual tool interface; experiment
countdowns and final-actor policy stay outside its context.

The [adapter reference](../../tools/player_host/README.md) owns provider-specific
serialization. The [conformance suite](../../tests/test_player_host_contract.py)
drives listed adapters only through this contract. No component name makes all
its behavior either player logic or test scaffolding.

## Adapter selection

A `campaign-run/10` package freezes `host:{"argv":[...]}` with1–8 strings.
The first is an absolute existing executable/interpreter regular file; later
entries are canonical project-local regular files tracked by the clean source.
No registry, resumed host, fallback or old `node` alias is supported.

## Modes

`ARGV validate --config ROUTE --mcp-config MCP --model ID --effort EFFORT`
accepts only the current route/MCP configuration, exits zero without credentials
or network within ten seconds and writes nothing to stdout. The validator gives
it only `PATH` and `LANG`.

`ARGV run --config ROUTE --mcp-config MCP --context CONTEXT --prompt PATH --session SESSION --actor-id ACTOR --pending-control-id none|ID --delivered-knowledge KNOWLEDGE --finish-reserve-usd USD --model ID --effort EFFORT --timeout-seconds S -o FINAL`
hosts one actor. Every flag occurs exactly once; unknown, missing or repeated
flags refuse. Frozen regular files other than knowledge are at most1MiB each. Delivered text has no hard cap. Session/actor IDs are32
lowercase hexadecimal characters. The driver reserves `FINAL`; successful direct
player reports write it, while handoff/failure leaves it unchanged.

The driver starts a new session with project cwd, stdout JSONL, bounded stderr
and only `PATH`, `LANG` and the selected credential variable. `S` is the original
host allowance. SIGINT/SIGTERM and hard deadlines stop independently of a model
reply. The driver's stdin pipe remains open for control until settlement. Exit
zero requires successful settlement, owned MCP closure and any final-file write.

## Route envelope

The closed route has `schema:"player-host/8"`, `model`, `api_key_env`,
`spend_limit_usd`, `unpriced_request_usd`, `max_context_images`,
`context_image_block`, `context_reserve_tokens`, `request_timeout_seconds` and
`service_tier`, and the closed `recall` object (`model`, `every`, `unpriced_request_usd`).
The adapter owns its closed `model` fields. The driver reads only model
ID/name/cost/context/output fields, credential variable, the two
dollar amounts and tier.
The image block is a positive integer no larger than the image peak.
`context_reserve_tokens` is a safe integer at least `model.maxTokens` and less
than `model.contextWindow`. Unsupported routes, including `/7`, do not execute.

A dollar amount is plain decimal text such as `"0.4096"`: digits with an optional
fraction. A JSON number, an exponent, a sign or a non-finite word is refused. Two
rules set its length:

- **A declared amount** (the route's `spend_limit_usd` and `unpriced_request_usd`, and
  the package's limit and dollar reserve) has at most twelve whole and eighteen
  fractional digits. Both route amounts are above zero.
- **A counted amount** in a trace (`reported_cost_usd`, `counted_cost_usd`,
  `spent_usd`) has no cap on its digits, because the host writes the provider's own
  digits, which can be more than eighteen. The driver reads it at any length and sums
  without rounding. When it gives a successor what remains, it cuts that to eighteen
  fractional digits, never up.

The driver sets `spend_limit_usd` to the dollars the run has left ([Spend](#spend)). One
logical request admits at most two provider attempts. Once per actor, an HTTP 200 stream may reach its request deadline after
producing content, reasoning or tool arguments and before a provider finish reason. After aborting and accounting for that attempt, the adapter may
make one inference with a fresh request deadline from the identical serialized
context. Only a completed reply reaches the agent or its tools. The next attempt
must fit below the dollar limit with ending and concurrent recall reserves intact.
A prior computer stop, unconfirmed computer operation, pending handoff, accepted
ending control, cancellation or host timeout prevents recovery. The custodian
permanently fences native input on Pause, including during final-report grace. Actor,
session and custody deadlines stay fixed. Missing charges remain unknown. The
[adapter reference](../../tools/player_host/README.md) defines the eligible failures. For an eligible pre-output refusal, the original request deadline covers the
backoff and the retry. Actor time and custodian mechanical resources are separate.
[Pre-output retry contract](https://github.com/CVX-Hull/enactive/issues/308) · [Live refusal evidence](../acceptance/2026-11-19-joanna-campground-memory-803.md).
These operator counts do not enter the assignment, repeated model messages or
actor tool results.

The current adapter reuses its maintained context estimate, reported usage and a text/image
heuristic floor to warn before capacity becomes critical. The warning offers the
existing handoff when the actor's tool table includes `player_handoff` (every actor's
does; the final actor's handoff call is refused, and the notice says to use
`player_finish` then); otherwise it says no successor is available and asks for
`player_finish`.
These estimates are not exact provider token bounds. Known excessive context
stops before another fetch. Original text, source/omission provenance and tool
correlations remain without compaction, fabricated summaries, restore or fallback.
The finite diagnostic must exercise its envelope, including missing usage and
oversized results, before admission.

### Spend

The host stops a run at a dollar limit, from the cost the provider reports for each
response ([R-OVERSPEND](../risks.md#operating-risks)).

- **What the route carries.** `spend_limit_usd` is the dollars this actor may still
  count. The route's `unpriced_request_usd` is a planning bound for an in-flight
  request. The package check computes it from the full context window at the largest
  configured input/cache rate plus the configured output limit at its output rate.
  The host uses it for the in-flight and ending allowances.
- **What counts.** Telemetry records every started HTTP request, including a
  retry. It adds only a usable provider-reported cost to the dollar total. A
  refusal, timeout, cutoff or abort without a usable cost keeps an unknown charge
  and an explicit unpriced attempt. A successful response without such a cost
  keeps the integration stop below.
- **The reported cost** is read from the response's usage records. On a route that is
  not on the caller's own provider key it is the larger of `cost` and
  `cost_details.upstream_inference_cost`; on an own-key route it is their sum. A
  malformed record leaves the cost unknown, never estimated. The curator applies the
  same rule, and both test suites run one shared file of usage records
  (`tests/fixtures/provider-usage-cost.json`).
- **Exact sums.** Amounts are summed as decimals, never as floating-point numbers.
- **Stop at the limit.** Before each HTTP attempt, a retry included, the host stops
  with reason `spend-limit` when the total has reached `spend_limit_usd`. A request
  already sent finishes. The provider subtotal can pass the limit by the returned
  charges for final in-flight player and recall requests.
- **Stop on an unpriced player success.** After a player response that did not fail and whose
  `reported_cost_usd` is null, the host stops with reason `cost-unreported` and
  dispatches no tool call from it. This keys on the cost, not on `usage_available`:
  token counts without a cost stop the run, and a cost without token counts does not.
- **No notice.** The host sends no tail notice for dollars. The driver's ending
  reserve asks for an orderly finish before the limit ([External control](#external-control)).

The driver reconciles each `request-start` with its cost record and sums returned
charges. A trace is complete when every attempt has a cost record, including
explicit unknowns, and settlement agrees on the subtotal and both unpriced
counts. A lost terminal record or a mismatch marks the trace incomplete and
admits no successor. The observed subtotal still records only provider charges.

### Delivered knowledge and recall

Every `campaign-run/10` package carries `delivered-knowledge.json` (`delivered-knowledge/1`), including an empty file of that format when no knowledge exists. `private_files` is a closed manifest map of `knowledge-full.json` and `units.json` hashes; neither private file is given to the host or application. The application requires the delivered file; every caller supplies it, including an explicit empty file when there is no knowledge. The driver copies its exact bytes into each actor's frozen inputs (`player-host-inputs/3`). It records the finish reserve there too.

The host appends a briefing to the first user message: recall-selected article leads or standalone fact text, an index line for every other article and standalone fact, and the coverage stamp. It labels the text as fallible data granting no authority. The system prompt and tool table stay identical across actors. With no articles or facts there is no recall request.

Every `recall.every` completed `computer_input` result offers a reminder request beside continued play. A completed selection becomes its own delimited user message in the next player request; it is never joined with control or limit notices and stays where first sent. An empty selection is an explicit silence. If another recall is in flight the opportunity is recorded as not made.

Recall uses the player's provider and credential variable, with the pinned
`recall.model`. A recall makes one HTTP attempt with no automatic retry. At fetch
it emits `request-start` with `recall-N` and `request_role:recall`. Player attempts
use `request-N`. Both roles share the run's dollar limit, including across handoff.
Recall runs serially at the configured cadence. Empty knowledge skips it.

Recall pre-checks and rechecks at fetch that an orderly stop is neither pending
nor accepted and that `spent + in-flight player bound + recall bound + finish reserve`
is below the route limit. The bound for the proposed recall keeps its possible
charge outside the dollars reserved for ending. The player's next request
continues to account for any recall in flight. A spend refusal, unavailable cost,
failed recall or provider/client failure before fetch disables later recall for
that actor. A reserve or orderly-stop refusal creates no request ID. An invalid
selection with a valid provider charge fails that opportunity and permits later
reminders. Valid charges are counted even when selection is invalid or a
response stopped for length. Host end or handoff aborts any in-flight recall and
settles its accounting. Player requests retain the unpriced-success stop.
Settlement, driver and receipt distinguish unpriced player and recall counts.
The planning bounds are reported separately from the combined provider subtotal.

The recall request's user text is one JSON object whose first key is `index`, then `kind`, then `first_message` (briefing) or `recent_calls` (reminder), so its stable prefix is shared across actors and reminders. When the recall model's provider is `openrouter` the request asks for structured output (`response_format` of type `json_schema`, strict, an object with exactly the key `articles`, an array of strings); other providers get no `response_format`. Because an OpenRouter route requires `require_parameters:true`, an OpenRouter recall route's pinned upstream must accept that strict `json_schema`; otherwise the recall is refused and any missing cost stays unknown. The real-model check of a new route covers that capability before it is used. The reply's text parts, joined and trimmed, must be exactly one JSON object, bare or inside exactly one Markdown code fence (optionally tagged `json`) with only whitespace outside it; anything else is an invalid selection.

Recall accepts only IDs and titles on the delivered index (articles and standalone facts). An article named by both ID and title is selected once; a repeated selection entry is invalid. A standalone fact is accepted as a lead carrying its text; IDs/titles absent from the index are refused, including facts filed under articles.

Telemetry records `knowledge-delivery` with kind, full text, article/fact/index IDs, delivered schema/version, recall request and receiving player request. `knowledge-recall` records selections, silence, failures and opportunities not made; a recall aborted because the actor ended has reason `actor-ended`. Every `knowledge-recall` for a recall whose attempt received a response (a stop other than an error or abort; status `selected`, `silence` or `failure`) carries `reply_text` and `reply_omitted_bytes`, the reply's text bounded at 8192 bytes on a UTF-8 boundary as the player's `assistant-text` is. An invalid reply has reason `invalid-recall-selection` and `selection_error`, one of `not-json`, `not-one-object`, `wrong-keys`, `repeated-entry`, `unknown-entry`; an unexpected exception has reason `recall-failed` and `error_name`. Each recall attempt has exactly one `response-complete`, emitted before its reply is parsed. `knowledge-undelivered` records text still unsent at actor end. Recall requests are never player decisions.

### Request stability and tail notices

A provider's prompt cache helps only when each request extends the previous one
byte for byte. The host therefore keeps these rules, which the offline
request-serialization tests prove for consecutive requests, a retried request, a
handoff successor and a new admission's first actor, with no provider call:

- **Prefix.** A request's messages begin with all of the previous request's messages,
  its notices included. The provider's cache reuses a request only when a later one
  extends it, so a tail that changes on every request is never reused
  ([#489 record](../acceptance/2026-11-08-context-stability-489.md#follow-up-the-cause-found)).
  The one earlier rewrite is image
  eviction: whole blocks of the oldest pixels become omission markers, each image
  once, and a marker never changes afterwards. Every other request field (tool table,
  limits, routing) is identical.
- **System prompt and tool table.** The system prompt is the frozen context plus the
  MCP server instructions, and holds no per-actor identity. Every actor of a package
  gets the same system prompt and the same tool table, so they are byte-identical
  across actors. The final actor keeps `player_handoff`. An actor's own session and
  actor IDs (audit data granting no authority) are in the first user message.
- **Session affinity.** The host gives its provider serializer one session identifier
  per mechanical session, a digest of the session ID that every actor of the session
  shares, recorded as `session_affinity_id` in `host-start`. For a route whose provider takes a
  session-affinity header (the adapter reference names it) the serializer sends it on
  every request, retries included; a request that would go out without it fails
  closed (`session-affinity-missing`) before any charge. It is not a credential. A
  serializer may also derive a provider prompt-cache key from it on routes that take
  one (the adapter reference names them).
- **Omission markers** carry the omitted frame's `source_id` (when its tool result
  has one) and name `player_source` as the way to read it again.
- **Notices** go at the end of the request in which they are first sent, and then stay
  in the history there unchanged. A retry resends the same body below the notice step,
  so it adds no notice. Once a threshold is passed, every later request adds a new
  notice. The first context and time notices explain how to wrap up. The context
  notice latches when the `context_reserve_tokens` line is crossed and reports the
  tokens of room before the stop. The time notice starts when the work deadline is
  within a tenth of the allowance, at least a minute and at most half. An accepted
  ending control carries its own ending instruction. Later notices update the
  applicable figures. Each emission is a `tail-notice` event with `request_id` and
  `kinds`; the notice text itself is not telemetry. Provider errors cannot be warned
  of before they happen, and the dollar limit has no notice.

## External control

Stdin carries newline-delimited closed `player-control/1` objects containing
`schema,id,session,actor_id,type`. Type is `orderly_stop`; IDs are32 lowercase
hexadecimal characters. Each line is bounded to4096 UTF8 bytes before a newline.
The pipe is separate from MCP's stdin. Identical duplicates are idempotent.
Conflicts, malformed/oversized control, wrong identity/version or unexpected EOF
fail and close owned MCP safely. The driver retains command intent before writing.

The host acknowledges valid control in operator telemetry and queues a fixed
labelled finish-up-and-stop message through its model loop. It includes command identity but
no experiment countdown, game target, Save/Quit mandate or tactic. Unsent calls
from a pre-control assistant turn are explicitly withheld; dispatched input is
not canceled/replayed merely to deliver text. New handoff is refused before
sealing once stop is pending.

The driver retains pending stop for the whole admission. If an in-flight handoff
already seals, it may deliver the same command to a verified successor before
ordinary action under original resources, or record incomplete ending. The required
`--pending-control-id` is `none` for an actor without inherited control, otherwise
the pending 32hex command ID. In the latter case the host waits for that matching
control before MCP connection or provider fetch; a wrong ID or unexpected EOF
fails. Neither sealing nor exit erases the admission's stop request.

The test freezes `ending_reserve` for seconds, dollars (`usd`),
inputs, requests, frames and frame bytes. The driver sends the stop when any of them
is at or below its reserve; for dollars that is the run's limit minus the cost
counted so far, with a request still in flight not yet counted. Validators enforce
bounded fields; the lead must forecast
that the reserves cover the largest admitted burst and in-flight inference/tool
delivery delay before admission. Validation is not proof of adequate ending
capacity. Hard limits, Pause and uncertainty remain independent.

Orderly finish-up is optional game work under finite authority. Immediate Pause
fences automation without awaiting a reply or saving. Stopping input does not
promise a paused game, persisted progress or application exit. The finite test
custodian closes its owned processes under its frozen policy; a user-owned game
need not close merely because a product player stops.

## Settlement and handoff

The host adds `player_finish` beside the frozen MCP table, rejecting an MCP tool
with that reserved name. Its closed arguments are `disposition`, `report`
(≤8192characters), unique `source_ids` (≤16 bounded1..128-character current
identities) and nullable `control_id`. Disposition is `task_complete`,
`cannot_continue` or `external_stop_complete`. The external disposition names the
directly received command; other dispositions require null. References and report
remain fallible claims, not source-read, save or success certificates.

Only direct validated tool execution accepts this signal. Remembered text,
nested results and arbitrary tool JSON cannot impersonate it. No later tool or
provider request dispatches after acceptance. Ordinary terminal assistant text
remains narration and does not by itself end the player's task.

Successful settlement reasons are the three finish dispositions or `handoff`.
Failures have `ok:false` and a bounded reason. Finish settlement retains its
control identity; `accepted_control_id` separately records any latched command.
Player claims, host settlement, stopped automation, game persistence, normal
native exit and owned absence remain separate facts.

Handoff settles only for the direct sealed actor-view issuance from
`player_handoff` or exact collection of this host's pending original handoff.
The host consumes the operation record `player-computer-operation/1` and
`player-transport/2`: the record is the structured content of a direct `player_handoff`
result, whose text is the short `player-computer-result/2` the model reads, and the
text of a `computer_result` collection, which returns it whole
([computer control](computer-control.md#computer-operations-and-custody)). The retired
`player-computer-result/1` is not a receipt. Underlying
`player-handoff/1` identifies this actor/session and grants no authority. After
handoff it dispatches no further tool and closes its MCP child. The driver checks
canonical store issuance, context digest and actual old host/MCP group absence
before a successor. Pause, uncertainty or failed closure cannot become a handoff.

## Telemetry

Stdout is JSONL telemetry version 8. Each line has `type`; the driver ignores event
kinds it does not account for, and observers project only known kinds.

| Event | Contract |
| --- | --- |
| `host-start` | Exactly once and first after admitted inputs, with `telemetry_version:8` and `schema:"player-host/8"`. It records `session_affinity_id` and the route's `spend_limit_usd` and `unpriced_request_usd`. |
| `tail-notice` | One per request that added a notice (earlier notices stay in the history without a new event): `request_id`, `kinds` (`context-capacity`, `host-timeout`) and the context `tokens` estimate. Additive; the driver ignores it. |
| `request-start` | Every observed HTTP start, including retries and failures. Each role has a contiguous ID sequence, `request-1` or `recall-1` onward. |
| `context-manifest` | Exactly one per HTTP attempt, retries included, after that attempt's `request-start` and before its `request-fetch-start`, with the same `request_id`. It is the exact ordered list of parts of the payload actually sent, as digests only, delta-encoded (below). An archived trace recorded before the event existed has none, and readers report its absence explicitly. |
| `response-complete` | One per HTTP attempt, a failed or aborted one included. `usage_available` distinguishes unknown usage. `usage.cost` is an estimate from the route's configured rates, labelled `cost_source:"configured-rates"`; it is not counted. `reported_cost_usd` is the cost the provider itself reported for the response, as decimal text in US dollars, or `null` when the response carried no usable cost; a missing or malformed cost stays unknown and is never estimated. `counted_cost_usd` matches the provider cost, or is `null` when the attempt has unknown cost. `cost_counted_as` is `provider-reported` or `unpriced`. `spent_usd` is the running provider subtotal. |
| `tool-result` | The MCP result as the host received it, with each image replaced by an `image_reference`: `content` is what the model reads, and `structuredContent`, where the tool server supplies one, is the full operation record of a computer observe, input or handoff that the model reads short. Readers take the operation and frame from the record where there is one, else from the text; a trace recorded before the short form holds the full record in the text. `result` is the tool server's payload and is versioned by the `schema` inside it, not by the telemetry version: the short form is `player-computer-result/2` and the record `player-computer-operation/1`. |
| `player-finish` | At most one direct accepted disposition/report/source references/control identity; mutually exclusive with accepted handoff. |
| `handoff` | At most one originating actor/session/operation/context/digest issuance with `grants_authority:false`. |
| `settled` | Last, with `ok`, reason, control identity where applicable, integer combined, player and recall counts matching the observed starts by role, the host's total `spent_usd` and both unpriced counts. A settlement written before the host started carries neither. |

Stop reasons this contract adds to a failed settlement: `spend-limit` and
`cost-unreported` ([Spend](#spend)).

### Context manifest

`context-manifest` fields: `request_id`; `base_request_id` (the previous attempt's
manifest in this host, `null` for the first); `reused_prefix_parts`; `part_count`;
`parts`, only the parts after the reused prefix; and `omitted_image_indexes`, the
full list of part indexes whose image was omitted, present only when it differs from
the base manifest's (absent means unchanged; the first manifest's base is empty).

**Replay rule.** For a manifest M, `parts(M) = parts(base(M))[0:reused_prefix_parts] ++ M.parts`
and `omitted(M) = M.omitted_image_indexes` if present, else `omitted(base(M))`. Replay
every manifest of one host in trace order from its first; `len(parts(M))` equals
`part_count` and each part's `index` equals its position. A new host (handoff successor)
starts a fresh chain with `base_request_id:null`. A retry attempt resends the same body,
so its manifest has `reused_prefix_parts == part_count` and no `parts`. The prefix is
the longest run of leading parts equal in every field, so a request that only appends
costs its new parts; an image eviction rewrites the parts after the oldest newly
omitted image, because omitted images change positions.

**Parts** follow the payload's message order; within a message: `reasoning`, then
text, then tool calls. Fields: `index`, `role` (`system`, `user`, `assistant` or
`tool`; the provider's `developer` role is `system`), `kind`, `bytes`, `sha256`.

| `kind` | `bytes` / `sha256` cover | Also |
| --- | --- | --- |
| `text` | the UTF-8 text of the system, user or assistant text part | |
| `reasoning` | the UTF-8 reasoning text returned to the provider | |
| `tool_call` | the compact JSON of the tool call as serialized | `tool_call_id`, `tool` |
| `tool_result_text` | the UTF-8 text of the tool message (with any omission marker) | `tool_call_id`, `tool` |
| `image` | the decoded image bytes | `state`, `tool_call_id`, `image_index`, `source_id` |

An image has `state:"sent"` (a part of the payload) or `"omitted"` (replaced by the
frozen omission marker inside its tool result's text; listed directly after that
`tool_result_text`). Its `sha256` equals the `image_reference` digest in `tool-result` and
the marker's `SHA256=`, and `bytes` is the decoded size. `tool_call_id`/`image_index`
match `context-image-projection`'s `omissions`, whose preview stays capped at 16; the
manifest lists every omitted image. `source_id` is present when the tool result has a
frame: `source.source_id` of its structured operation record, or of its JSON text where
the model reads the result whole (`computer_result`, `player_source`). Tool definitions are not parts; `payload_sha256` on
`request-start` covers the whole body.

Privacy: a manifest holds indexes, roles, kinds, sizes, SHA-256 digests and tool,
call and source identities. It never holds text, reasoning, tool arguments, image
bytes or data URLs, so the bodies stay unrecoverable from telemetry.

Pre-start refusal emits only unsuccessful `settled`. A final-file failure may
append one unsuccessful settlement after the prior settlement and exits nonzero.
Partial lines, absent/repeated terminal events, a cost record the driver cannot
count or incomplete accounting charge the whole original host allocation, mark the
run's spend incomplete and admit no successor. Telemetry retains
bounded public narration, claims and original references, never credentials,
private reasoning or raw request/image histories.

## Isolation

No coding-agent application prompt, shell/file tools, personal settings, ambient
resource discovery, replay, reconnect, restore, compaction or model fallback is
loaded. Only the selected credential variable reaches the host; MCP receives
only locale/executable lookup. Game input stays within sequential actor tools.

## Conformance

The contract suite uses scripted local provider/MCP fixtures, the real driver's
accounting reader, cancellation/EOF/identity cases, direct finish origin,
pending-call suppression, observed-attempt accounting, the dollar limit and actual
child closure.
Production HTTP/MCP composition retains a controlled synthetic actor binding.
These tests establish interfaces, not model quality, actual saving, useful
cadence, unattended reliability or cross-game support. Real play remains a
separately frozen lane.
