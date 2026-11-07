---
owner: lead
review_trigger: Driver/host invocation, route envelope, telemetry, settlement, isolation or adapter changes
status: active
---

# Player host contract

`player-host/3` is the one current boundary between the
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

A `campaign-run/5` package freezes `host:{"argv":[...]}` with1–8 strings.
The first is an absolute existing executable/interpreter regular file; later
entries are canonical project-local regular files tracked by the clean source.
No registry, resumed host, fallback or old `node` alias is supported.

## Modes

`ARGV validate --config ROUTE --mcp-config MCP --model ID --effort EFFORT`
accepts only the current route/MCP configuration, exits zero without credentials
or network within ten seconds and writes nothing to stdout. The validator gives
it only `PATH` and `LANG`.

`ARGV run --config ROUTE --mcp-config MCP --context CONTEXT --prompt PATH --session SESSION --actor-id ACTOR --pending-control-id none|ID --model ID --effort EFFORT --timeout-seconds S -o FINAL`
hosts one actor. Every flag occurs exactly once; unknown, missing or repeated
flags refuse. Frozen regular files are at most1MiB each. Session/actor IDs are32
lowercase hexadecimal characters. The driver reserves `FINAL`; successful direct
player reports write it, while handoff/failure leaves it unchanged.

The driver starts a new session with project cwd, stdout JSONL, bounded stderr
and only `PATH`, `LANG` and the selected credential variable. `S` is the original
host allowance. SIGINT/SIGTERM and hard deadlines stop independently of a model
reply. The driver's stdin pipe remains open for control until settlement. Exit
zero requires successful settlement, owned MCP closure and any final-file write.

## Route envelope

The closed route has `schema:"player-host/3"`, `model`, `api_key_env`,
`max_requests`, `max_context_images`, `context_image_block`,
`context_reserve_tokens`, `request_timeout_seconds` and `service_tier`.
The adapter owns its closed `model` fields. The driver reads only model
ID/name/cost/context/output fields, credential variable, request maximum and tier.
The image block is a positive integer no larger than the image peak.
`context_reserve_tokens` is a safe integer at least `model.maxTokens` and less
than `model.contextWindow`. Unsupported routes, including `/2`, do not execute.

The driver lowers request maximum to the remaining original allocation. One
logical request admits at most two charged provider attempts; missing usage is
unknown and retries never renew limits. The adapter reference defines eligible
transient refusals. Host seconds and custodian mechanical resources are separate.
These operator counts do not enter the assignment, repeated model messages or
actor tool/program results.

The current adapter reuses its maintained context estimate, reported usage and a text/image
heuristic floor to warn before capacity becomes critical. The warning offers the
existing handoff when the actor's tool table includes `player_handoff`; otherwise it
says no successor is available and asks for `player_finish`.
These estimates are not exact provider token bounds. Known excessive context
stops before another fetch. Original text, source/omission provenance and tool
correlations remain without compaction, fabricated summaries, restore or fallback.
The finite diagnostic must exercise its envelope, including missing usage and
oversized results, before admission.

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

The test freezes `ending_reserve` for seconds, HTTP attempts, inputs, requests,
frames and frame bytes. Validators enforce bounded fields; the lead must forecast
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
The host consumes `player-computer-result/1` and `player-transport/2`; underlying
`player-handoff/1` identifies this actor/session and grants no authority. After
handoff it dispatches no further tool and closes its MCP child. The driver checks
canonical store issuance, context digest and actual old host/MCP group absence
before a successor. Pause, uncertainty or failed closure cannot become a handoff.

## Telemetry

Stdout is JSONL telemetry version3. Each line has `type`; the driver ignores event
kinds it does not account for, and observers project only known kinds.

| Event | Contract |
| --- | --- |
| `host-start` | Exactly once and first after admitted inputs, with `telemetry_version:3` and `schema:"player-host/3"`. |
| `request-start` | Every charged HTTP attempt, including retries/failures, numbered contiguously `request-1` onward without exceeding allocation. |
| `context-manifest` | Exactly one per HTTP attempt, retries included, after that attempt's `request-start` and before its `request-fetch-start`, with the same `request_id`. It is the exact ordered list of parts of the payload actually sent, as digests only, delta-encoded (below). Additive within version 3 under [S-MIGRATION](../standards/migration.md)'s additive-event case: absent from traces recorded before 6 November 2026, which stay readable, and readers report its absence explicitly. |
| `response-complete` | `usage_available` distinguishes unknown usage; known configured/provider costs remain labelled. |
| `player-finish` | At most one direct accepted disposition/report/source references/control identity; mutually exclusive with accepted handoff. |
| `handoff` | At most one originating actor/session/operation/context/digest issuance with `grants_authority:false`. |
| `settled` | Last, with `ok`, reason, control identity where applicable and requests matching charged attempt count. |

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
manifest lists every omitted image. `source_id` is present when the tool result's JSON
text has `source.source_id`. Tool definitions are not parts; `payload_sha256` on
`request-start` covers the whole body.

Privacy: a manifest holds indexes, roles, kinds, sizes, SHA-256 digests and tool,
call and source identities. It never holds text, reasoning, tool arguments, image
bytes or data URLs, so the bodies stay unrecoverable from telemetry.

Pre-start refusal emits only unsuccessful `settled`. A final-file failure may
append one unsuccessful settlement after the prior settlement and exits nonzero.
Partial lines, absent/repeated terminal events or incomplete accounting charge
the whole original host allocation and admit no successor. Telemetry retains
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
pending-call suppression, original attempt charging and actual child closure.
Production HTTP/MCP composition retains a controlled synthetic actor binding.
These tests establish interfaces, not model quality, actual saving, useful
cadence, unattended reliability or cross-game support. Real play remains a
separately frozen lane.
