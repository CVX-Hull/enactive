---
owner: lead
review_trigger: Changes to events emitted by tools/player_host/, accounting in tools/campaign_player.py or the offline host reader in harness/evaluation/
status: active
---

# Player host telemetry

This contract covers [player host](player-host.md) JSONL events, accounting and context manifests.

## Knowledge delivery and agenda events

Telemetry records `knowledge-delivery` with `kind` (`briefing` or `update`), explicit `outcome`, delivered schema/version and receiving player request. Every `knowledge-delivery` event carries `outcome`:

- `delivered` (`briefing` or `update`): the logical player request carrying that placement reached a settled successful `response-complete` with usable provider-reported cost. Carries `receiving_player_request_id`, redacted `text` (with host-local `agenda` and `affects_agenda` fields stripped before logging so player working state never enters `host.jsonl`), `article_ids`, `fact_ids`, `index_ids`, `delivered_knowledge_schema` and `version` (plus `previous_version`, `coverage` and `removed_ids` on `kind: "update"`).
- `undelivered` (`briefing` or `update`): emitted on every other terminal outcome for a logical player request carrying that placement (including pre-header failure, terminal HTTP error, aborted stream, `cost-unreported`, or priced `length`/`deferred` failure). Carries the same placement fields for diagnostics without crediting player exposure.
- `empty-suppressed` (`update` only): emitted when a verified newer knowledge version produces an empty substantive delta relative to `lastAnnouncedKnowledge`; the host adopts the version silently without appending a user message. Carries `version`, `previous_version`, `coverage` and `delivered_knowledge_schema` with no `receiving_player_request_id` or `text`.
- `refused` (`update` only): pre-request refusal before placement; carries `version`, `previous_version`, `coverage` and `reason` with no `receiving_player_request_id`, `text` or `fact_ids`. `reason` is one of `invalid-entry` (the line failed both supported schemas, with null `version` and `coverage`), `not-newer`, `superseded` (a newer listed version verified), `repository-mismatch`, `file-unreadable`, `sha256-mismatch`, `invalid-delivered-knowledge`, `entry-mismatch`, `context-capacity`, or `update-check-failed` for an unexpected exception, with `error_name` (and null `version` and `coverage` outside per-entry request planning, or the entry's `version` and `coverage` during planning).

`knowledge-undelivered` records unsent update text remaining at actor end (with host-local `agenda` and `affects_agenda` fields stripped from `delta` and `text`). `player-agenda` records committed host-local `player_agenda` tool updates (`request_id`, `tool_call_id`, `op`, `cut_count`, `thread_count`, `active_count`, and the committed `player-agenda-continuation/1` object); curator trace projections exclude `player-agenda` events and defense-in-depth scrub any `agenda`/`affects_agenda` fields from delivery lines so player working state never leaks into durable memory. Background LLM recall is retired in `player-host/13`, so `recall-N` request starts and `knowledge-recall` events are no longer emitted.

## Telemetry

Stdout is JSONL telemetry version 13. The driver rejects other versions for live
accounting. Each line has `type`. The driver ignores event kinds it does not
account for, and observers project only known kinds.

| Event | Contract |
| --- | --- |
| `host-start` | Exactly once and first after admitted inputs, with `telemetry_version:13` and `schema:"player-host/13"`. It records `session_affinity_id` and the route's `spend_limit_usd`, `unpriced_request_usd` and `context_cut`, including null when cuts are disabled. `provider_routing` records the configured routing policy with one or two tags in both `only` and `order`, or null on a direct route. `endpoint_costs` records the frozen rates per declared endpoint on a two-endpoint route and is null otherwise. |
| `tail-notice` | One per request that actually placed a notice at a halving-step crossing (`100%`, `50%`, `25%`, `12.5%` of the warning threshold; earlier notices stay in the history without a new event): `request_id`, `kinds` (`context-capacity`, `host-timeout`, `spend-limit`) and the context `tokens` estimate. The driver ignores this event. |
| `spend-reserve-reached` | At most one per actor when ordinary-work spend admission fails while `spent < spend_limit`: `actor_id`, `spent_usd`, `spend_limit_usd`, `finish_reserve_usd`, `unpriced_bound_usd`. Consumed by the live driver to issue `orderly_stop` before the host's 2 s wait expires. |
| `request-start` | Every observed HTTP start, including retries and failures, with contiguous IDs `request-1` onward. |
| `context-cut` | One per triggered [cut decision](#context-cut) (edge-reported per `(reason, coverage_frontier)` state for holds), before the next player request's image projection. |
| `context-manifest` | Exactly one per player HTTP attempt, retries included, after that attempt's `request-start` and before its `request-fetch-start`, with the same `request_id`. It is the exact ordered list of parts of the payload actually sent, as digests only, delta-encoded (below). For a sealed archive trace without this event, the evaluator reports the manifest as `absent`. |
| `provider-refusal` | A bounded player refusal diagnostic with `request_id`, HTTP `status` and `body_read`. `refusal_class` is `credits-or-limit`, `moderation`, `auth`, `upstream-provider` or `unknown`. `provider_name` is a sanitized label from refusal metadata or null. `error_type`, `error_code`, `provider_error_code`, `limit_source` and `reason` are sanitized identifiers or null. The event excludes raw messages, refusal bodies and credentials. Older archived traces can omit `refusal_class` and `provider_name`. |
| `response-complete` | One per player HTTP attempt, a failed or aborted one included. Top-level `reported_provider` is the first usable, sanitized `provider` label in the response stream, or null when unavailable. Player events also retain it in `response_progress`. `usage_available` distinguishes unknown usage. `usage.cost` is an estimate from the route's configured rates, labelled `cost_source:"configured-rates"`; it is not counted. `reported_cost_usd` is the cost the provider itself reported for the response, as decimal text in US dollars, or `null` when the response carried no usable cost; a missing or malformed cost stays unknown and is never estimated. `counted_cost_usd` matches the provider cost, or is `null` when the attempt has unknown cost. `cost_counted_as` is `provider-reported` or `unpriced`. `spent_usd` is the running provider subtotal. |
| `tool-result` | The MCP result as the host received it, with each image replaced by an `image_reference`. The operation payload follows the [tool server's result formats](player-ports.md#mcp-projection-and-envelopes). Readers take the full record from `structuredContent` when present and from JSON text otherwise, including for sealed traces with text-only records. |
| `player-agenda` | One per committed host-local `player_agenda` mutation (`request_id`, `tool_call_id`, `op`, `cut_count`, `thread_count`, `active_count`, `agenda`). Excluded from curator trace projections. |
| `player-finish` | At most one direct accepted disposition/report/source references/control identity; mutually exclusive with accepted handoff. |
| `handoff` | At most one originating actor/session/operation/context/digest issuance with `grants_authority:false`. |
| `settled` | Last, with `ok`, reason, control identity where applicable, integer `requests` and `player_requests` counts matching the observed starts, the host's total `spent_usd` and `unpriced_requests` (no retired recall counts). A settlement written before the host started carries neither. |

Stop reasons the [host contract](player-host.md) adds to a failed settlement: `spend-limit`, `spend-reserve-timeout` and
`cost-unreported` ([Spend](player-host.md#spend)).

### Context cut

A `context-cut` event carries the next `request_id`, the `triggers` in order
(`high_mark`, `image_peak`), `covered_through_operation_id` (null without
eligible coverage), the adopted `knowledge_version`, `tokens_before` and
`images_before`. The request may still stop before fetch. Token fields are
approximate. `images_before` and `images_after` count images in the active
history before ordinary image eviction, while `tokens_before` and
`tokens_after` are estimated from the projected messages after ordinary image
eviction and any new tail notice.

- `outcome: "cut"` also reports `cut_result` (`target` when a prefix met both
  `low_mark` and the image target, `best_effort` when the full eligible or cuttable
  fallback ran, or `rescue` when strict-fit hard-capacity rescue ran), `removed_turns`,
  `uncovered_turns` (exact non-negative integer count of omitted turns not yet covered by
  `covered_through_operation_id`; `0` on covered cuts and healing toward `0` as coverage
  catches up),
  `cumulative_removed_turns`, `tokens_after`, `briefing_tokens`, `images_after`
  and `source_ids_count` for the cumulative distinct sources. The logical request
  carrying the cut gets a `knowledge-delivery` with `kind: "briefing"` and explicit
  `outcome` (`delivered` or `undelivered`).
- `outcome: "held-back"` also reports `reason`, `available_turns` and
  `min_free`. Holds are edge-reported once on entering a `(reason, coverage_frontier)`
  state while cut pressure remains armed (a restore clears cut pressure and emits no
  `held-back` event). The reason is `uncovered` when no surviving turn is eligible,
  `below-min-free` when eligible covered turns are below `min_free`, or
  `insufficient-cover` when no candidate prefix meets targets and even the full covered
  prefix (`k = E`) does not fit and strictly reduce estimated tokens.
  `available_turns` is zero for `uncovered`, and the eligible turn count otherwise.

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
