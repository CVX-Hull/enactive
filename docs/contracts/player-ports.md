---
owner: lead
review_trigger: Changes to journal or player tool formats in harness/player/, harness/player_view.py, harness/player_mcp.py or harness/player_tools.py
status: active
---

# Player ports

This contract covers the journal, the MCP projection and envelopes, player knowledge and the rules for composed operations on top of [computer control](computer-control.md).

## Player journal

The selected `player-journal/1` store
(SQLite `user_version=1`) may span fresh native-child sessions. A supported current
journal may be reopened; a nonempty unrecognized or unsupported store is refused
before native launch. The journal stores public calls, hints and referenced source
metadata and PNGs, not player-authored durable knowledge or programs.

## MCP projection and envelopes

At MCP serialization, [the actor projection](../../harness/player_view.py) returns
the operation record `player-computer-operation/1`: the operation identity, status,
original receipts, source and handoff stay intact, but `deadline_monotonic` and
global `remaining` are absent. This covers immediate results, exact collection and
declared nested computer results in `player_result`. Native `computer-receipt/2`
contents remain original evidence.

**What the model reads of a computer call.** The [MCP adapter](../../harness/player_mcp.py)
projects the result for the model and retains the full operation record for the host
and trace.

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
and `computer_result` shows which actions were. The full operation record retains
the session, actor, kind, creation time, receipts, source record and handoff
issuance. The host reads `source_id` and the full handoff issuance from that record.

Model-facing errors and transport uncertainty use
`player-error/2` and `player-transport/2`, preserving correction/control facts and
original collection identity without experiment countdowns. Unknown mechanical
versions fail with a bounded unsupported-result error, never raw pass-through.
Player-authored text, code, interpretation and state are opaque; keys named
`remaining` or `requests` inside them are not deleted. Canonical
`computer-operation/1`, internal HTTP/client errors and operator accounting remain
unchanged; the actor projection is not a database migration. An operation's
`receipts` hold `computer-receipt/2`, `computer-local/1` or `computer-transport/2`
values (see the [native channel table](computer-control.md#native-channel)).

Internal service envelopes, below the actor projection, are `player-response/1`,
`player-error/1` and `player-transport/1` ([service](../../harness/server.py),
[client](../../harness/player_client.py)), plus the per-tool results
`player-service-result/2` and `player-source-read/1`. [The actor projection](../../harness/player_view.py)
is their authority. It maps the internal error and transport envelopes to
`player-error/2` and `player-transport/2` for the model.

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
Late collection never renews a source's `received_wall`. The host records public
calls and evidence references in [host telemetry](player-host-telemetry.md#telemetry).
Stable frozen system context and the ongoing user objective are reused across actors.
Experiment quotas, final-actor policy and ending reserves remain in operator
accounting, outside the player prompt and tool views. Host decision-time and
custodian horizons stay distinct.
