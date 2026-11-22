---
owner: lead
review_trigger: Changes to events emitted by tools/player_host/, accounting in tools/campaign_player.py or the offline host reader in harness/evaluation/
status: active
---

# Player host telemetry

This contract covers [player host](player-host.md) JSONL events, accounting and context manifests.

## Knowledge delivery and recall events

Telemetry records `knowledge-delivery` with kind, full text, article/fact/index IDs, delivered schema/version, recall request and receiving player request. `knowledge-recall` records selections, silence, failures and opportunities not made; a recall aborted because the actor ended has reason `actor-ended`. Every `knowledge-recall` for a recall whose attempt received a response (a stop other than an error or abort; status `selected`, `silence` or `failure`) carries `reply_text` and `reply_omitted_bytes`, the reply's text bounded at 8192 bytes on a UTF-8 boundary as the player's `assistant-text` is. An invalid reply has reason `invalid-recall-selection` and `selection_error`, one of `not-json`, `not-one-object`, `wrong-keys`, `repeated-entry`, `unknown-entry`; an unexpected exception has reason `recall-failed` and `error_name`. Each recall attempt has exactly one `response-complete`, emitted before its reply is parsed. `knowledge-undelivered` records text still unsent at actor end, an adopted update's included. Recall requests are never player decisions.

A [newer version during play](player-host.md#a-newer-version-during-play) records
`knowledge-delivery` with kind `update`, `version`, `previous_version` and the new
version's `coverage`, and `outcome`:

- `delivered`: the update message reached the receiving player request. It also has
  the full text, `article_ids`, `fact_ids` and `index_ids` of the entries it shows,
  `removed_ids`, `delivered_knowledge_schema`, `receiving_player_request_id` and a
  null `recall_request_id`.
- `refused`: the host kept the version it holds. `reason` is one of `invalid-entry`
  (the line failed both supported schemas, with null `version` and `coverage`),
  `not-newer`,
  `superseded` (a newer listed version verified), `repository-mismatch`,
  `file-unreadable`, `sha256-mismatch`, `invalid-delivered-knowledge`,
  `entry-mismatch`, `context-capacity`, or `update-check-failed` for an unexpected
  exception, with `error_name` and null `version` and `coverage`.

## Telemetry

Stdout is JSONL telemetry version 11. The driver rejects other versions for live
accounting. Each line has `type`. The driver ignores event kinds it does not
account for, and observers project only known kinds.

| Event | Contract |
| --- | --- |
| `host-start` | Exactly once and first after admitted inputs, with `telemetry_version:11` and `schema:"player-host/11"`. It records `session_affinity_id` and the route's `spend_limit_usd`, `unpriced_request_usd` and `context_cut`, including null when cuts are disabled. `provider_routing` records the configured routing policy with one or two tags in both `only` and `order`, or null on a direct route. `endpoint_costs` records the frozen rates per declared endpoint on a two-endpoint route and is null otherwise. `recall` includes its own frozen model and endpoint costs. |
| `tail-notice` | One per request that added a notice (earlier notices stay in the history without a new event): `request_id`, `kinds` (`context-capacity`, `host-timeout`) and the context `tokens` estimate. Additive; the driver ignores it. |
| `request-start` | Every observed HTTP start, including retries and failures. Each role has a contiguous ID sequence, `request-1` or `recall-1` onward. |
| `context-cut` | One per triggered [cut decision](#context-cut), before the next player request's image projection. |
| `context-manifest` | Exactly one per player HTTP attempt, retries included, after that attempt's `request-start` and before its `request-fetch-start`, with the same `request_id`. It is the exact ordered list of parts of the payload actually sent, as digests only, delta-encoded (below). For a sealed archive trace without this event, the evaluator reports the manifest as `absent`. |
| `response-complete` | One per player or recall HTTP attempt, a failed or aborted one included. Top-level `reported_provider` is the first usable, sanitized `provider` label in the response stream, or null when unavailable. Player events also retain it in `response_progress`. `usage_available` distinguishes unknown usage. `usage.cost` is an estimate from the route's configured rates, labelled `cost_source:"configured-rates"`; it is not counted. `reported_cost_usd` is the cost the provider itself reported for the response, as decimal text in US dollars, or `null` when the response carried no usable cost; a missing or malformed cost stays unknown and is never estimated. `counted_cost_usd` matches the provider cost, or is `null` when the attempt has unknown cost. `cost_counted_as` is `provider-reported` or `unpriced`. `spent_usd` is the running provider subtotal. |
| `tool-result` | The MCP result as the host received it, with each image replaced by an `image_reference`. The operation payload follows the [tool server's result formats](player-ports.md#mcp-projection-and-envelopes). Readers take the full record from `structuredContent` when present and from JSON text otherwise, including for sealed traces with text-only records. |
| `player-finish` | At most one direct accepted disposition/report/source references/control identity; mutually exclusive with accepted handoff. |
| `handoff` | At most one originating actor/session/operation/context/digest issuance with `grants_authority:false`. |
| `settled` | Last, with `ok`, reason, control identity where applicable, integer combined, player and recall counts matching the observed starts by role, the host's total `spent_usd` and both unpriced counts. A settlement written before the host started carries neither. |

Stop reasons the [host contract](player-host.md) adds to a failed settlement: `spend-limit` and
`cost-unreported` ([Spend](player-host.md#spend)).

### Context cut

A `context-cut` event carries the next `request_id`, the `triggers` in order
(`high_mark`, `image_peak`), `covered_through_operation_id` (null without
eligible coverage), the adopted `knowledge_version`, `tokens_before` and
`images_before`. The request may still stop before fetch. Token fields are
approximate. Token and image counts describe the active history before ordinary
image eviction and new tail notices.

- `outcome: "cut"` also reports `removed_turns`, `cumulative_removed_turns`,
  `tokens_after`, `briefing_tokens`, `images_after` and `source_ids_count` for
  the cumulative distinct sources. The first HTTP attempt carrying the cut
  gets a `knowledge-delivery` with `kind: "briefing"` and a null
  `recall_request_id`.
- `outcome: "held-back"` also reports `reason`, `available_turns` and
  `min_free`. The reason is `restored` after invalidation, `uncovered` when
  no surviving turn is eligible, or `below-min-free` when the planned
  number of turns is below the configured minimum. `available_turns` is zero
  for the first two reasons and the planned number for the last.

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
costs its new parts. A cut starts a new message prefix in the same manifest chain.
An image eviction rewrites the parts after the oldest newly omitted image, because
omitted images change positions.

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
