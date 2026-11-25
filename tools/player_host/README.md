---
owner: lead
review_trigger: Adapter invocation, provider serialization, MCP integration or telemetry instrumentation changes
status: active
---

# Bounded Pi player host

This private package is the Pi-based adapter that implements the host-neutral
[player-host contract](../../docs/contracts/player-host.md) (`player-host/12`);
the campaign driver selects it only through the package's frozen `host.argv`.
The [player interface component](../../docs/components/player-interface.md) describes
the adapter's place in the run.
It uses Pi agent-core, AI serialization and MCP 1.4.0 directly. It loads no coding
agent application, personal settings, sessions, shell/file tools or resources.
The campaign driver invokes the frozen `host.argv` followed by a mode word with
frozen provider/MCP/context inputs; no coding-agent launch or resumed-host fallback
is supported. Host choice
is independent of whether a particular model passes gameplay qualification.

## Invocation and settlement

See the [adapter procedure](../../docs/operations/player-host.md#install-and-test-the-adapter) for installation, tests and invocation with the required mode and flags (`validate` with `--config`, `--mcp-config`, `--model` and `--effort`, and `run` with those flags plus `--context`, `--prompt`, `--session`, `--actor-id`, `--pending-control-id`, `--delivered-knowledge`, `--finish-reserve-usd`, `--timeout-seconds` and `-o`, and the one optional flag `--knowledge-updates`).

The runner requires regular files of at most 1 MiB for the route, MCP table,
context and prompt. The delivered knowledge file has no text-size cap. Stdin
carries [finish-up control](../../docs/contracts/player-host.md#external-control),
including a successor's pending command when specified by `--pending-control-id`.
The driver exclusively reserves the final path; the runner writes that existing
path only with the report from successful direct `player_finish` settlement and leaves it unchanged after a
handoff or any failure. JSONL events go to stdout. A missing or unknown mode, or a
missing, repeated or unknown flag, settles `invalid-arguments` and exits one.
Exit zero requires direct finish or completed-handoff settlement below, no fatal
failure latch, successful owned MCP closure, and any required final-file write.
Ordinary terminal assistant text alone fails as `incomplete-terminal-response`.
`runHost(options)` is the
programmatic seam; tests inject `fetch` there. No fake-provider CLI is exposed.

## Frozen route and serving tier

The closed route has exactly `schema: "player-host/12"`, `model`,
`api_key_env`, `request_timeout_seconds`, `service_tier`, the required positive
integer `max_context_images` and the required integer `context_image_block`
(1 ≤ block ≤ `max_context_images`), plus required safe-integer
`context_reserve_tokens` (`maxTokens` ≤ reserve < `contextWindow`) and the two dollar
amounts `spend_limit_usd` (above zero) and `unpriced_request_usd`, each plain decimal
text ([the dollar limit](#the-dollar-limit)), the closed [recall configuration](#knowledge-delivery),
required `endpoint_costs` and required `context_cut`. Set `context_cut` to null or a closed object with
safe integers `1 <= low_mark < high_mark < model.contextWindow` and `min_free >= 1`.
The bounds use the player model's window.
The adapter rejects other schema versions and missing or invalid fields.
`model` contains Pi's
explicit `id`, `name`, `api: "openai-completions"`, `provider`, `baseUrl`,
`reasoning`, `input`, `cost`, `contextWindow` and `maxTokens`; optional `type`,
`thinkingLevelMap` and the supported `compat` properties are validated in
`validateConfiguration`. Both text and image input are mandatory. URL userinfo,
query strings and fragments, arbitrary headers, other APIs and unknown fields
are refused. Model metadata and costs are configuration, not verified provider
capabilities or billing evidence.

Freeze `service_tier` as `default` or `priority`. Direct-provider default leaves the API field
unset; priority adds only `service_tier: "priority"` through Pi's maintained
`onPayload` hook. Verify support and pricing for the exact provider/model before
selection. For the tested DeepInfra route, requested priority uses all configured
rates at 1.5× standard, which also raises the bound a request with no cost record
counts for. This is a
conservative configured estimate, separate from provider-reported cost,
actual applied-tier prices and invoices. DeepInfra may serve an unsupported
priority request at the default tier. There is no tier/model fallback or retry
triggered by the echo. `host-start.requested_service_tier` records selection;
`response-service-tier` records a parsed stream echo only for known
`default`/`priority`/`flex` values, once per value per HTTP attempt. Missing echo
remains unknown. Nonstream provider probes do not establish stream-echo support;
serving tier, cache counts and request spans do not qualify useful apparent latency.
See [DeepInfra's current contract](https://docs.deepinfra.com/chat/overview#service-tier).

## Request context and session affinity

Freeze the actual provider's image-part allowance explicitly as `max_context_images`,
the hard peak of pixel images per request; the host imposes no universal provider
limit (DeepInfra, for example, rejects more than 30). Pi's maintained
`transformContext` hook keeps historical images within that peak. After any
coverage-gated cut, image eviction preserves the remaining text, reasoning,
tool calls/results and IDs. Eviction is count-only, in whole
blocks of `context_image_block`. When `n` images exceed the peak, the oldest
`ceil((n − peak) / block) × block` become markers, never reaching into the protected
batch below, so a large protected batch can leave fewer. Otherwise retained pixels
cycle between `peak − block + 1` and the peak, and the serialized prefix stays
byte-stable between evictions, which lets
provider prefix caches reuse it. Block 1 omits exactly the overflow (rolling eviction). Choose the counts per route against the provider's image limit.
The host gives Pi one `sessionId` per mechanical session (a digest of the session
ID, shared by every actor of the session and recorded as
`host-start.session_affinity_id`), and Pi sends it as
`x-session-id` on every OpenRouter request (on a direct `api.openai.com` route Pi
would also send it as `prompt_cache_key`; none is configured); Pi enables that header for an OpenRouter
route by itself, so no compat key is needed, and the host fails closed
(`session-affinity-missing`) if a request would go out without it. In the
[#309 routing probe](../../docs/acceptance/2026-11-22-failover-routing-probe-309.md) and
[#896 seven-day campaign](../../docs/acceptance/2026-11-22-seven-day-campaign-896.md),
requests with `provider.order` sustained high prompt-cache reuse (97.4% on Azure in the
probe; 92.27% overall and 93.57% on deciding-player turns across 4,100 primary-served
responses in `#896-b`), though neither isolated `x-session-id` stickiness or `order`
precedence from OpenRouter's default routing or observed a live primary-to-secondary
failover. The entire latest assistant tool-call batch is protected,
including when its final result contains only text. If that group alone exceeds
the allowance, the host stops before another provider request or request charge.
Historical omitted image parts become explicit text markers with original message/
image provenance and hash: pixels were not forwarded in this request, and the
marker grants no source-read proof or authority. The marker names the frame's
`source_id` (from its tool result) and says to read it again with `player_source`;
the player can request the exact source again through its available tools. No tool is called automatically to restore an image.

Notices report context capacity, remaining time, and the spend budget above the
ending reserve at 100%, 50%, 25%, and 12.5% of each warning threshold. A request
that crosses several steps of one kind receives a single notice for that kind.
Simultaneous kinds share one append-only user message. A context cut resets
the context-capacity steps. The first spend notice asks the player to wrap up
with `player_finish`. See the contract's
[request-stability rules](../../docs/contracts/player-host.md#request-stability-and-tail-notices).
Every actor shares one system prompt and tool table. The ongoing user objective
survives actor turnover; experiment quotas, final-actor policy and ending reserves
stay in operator accounting. The adapter extracts `source_id` from the full MCP
operation record to label image omission markers. It sends the content defined
by the [player result projection](../../docs/contracts/player-ports.md#mcp-projection-and-envelopes)
to the model and keeps `structuredContent` in the trace.
The host reuses Pi's `estimateContextTokens`, reported usage and a heuristic
text/image floor to request the existing sealed handoff before critical context
pressure. Known oversized context stops before fetch. A cut uses a fresh
heuristic estimate until a response supplies usage for the new prefix.

Live agent messages retain the pixels needed by the provider. Original source
images stay in the mechanical/player stores. Telemetry stores image references
and the exact `request-start.payload_sha256`, sizes and counts, never the raw
projected body or private reasoning. Context projection events expose image
omissions, and `context-cut` records cut decisions. Qualification must include
actual continuation and apparent effects.

## Reasoning and credentials

For nonreasoning models effort must be `off`. For reasoning models the selected
Pi effort (`off`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`) must have a
non-null explicit `thinkingLevelMap` entry, with
`compat.supportsReasoningEffort: true` and `compat.thinkingFormat: "openai"`
for direct routes or `"openrouter"` for OpenRouter.
Direct Pi streaming sends the declared mapping without its simple-stream effort
clamping. OpenRouter uses its maintained nested reasoning serializer as described
below. Other reasoning formats need conformance evidence before support.

Credentials come only from the explicitly named environment variable, resolved
when preparing a provider call. The runner refuses `OPENAI_LOG`,
`OPENAI_CUSTOM_HEADERS`, `OPENAI_ORG_ID`, or `OPENAI_PROJECT_ID` in its environment
with `ambient-provider-configuration`: OpenAI SDK 7.19.0 reads these independently
of Pi's scoped environment and they can enable raw logging or inject headers.
Clear them only in the dedicated host child's environment; the package never
mutates the parent environment or a profile. No key values, headers or raw
provider exceptions are emitted. Pi cache retention is explicitly `short`, preserving the maintained default
while preventing an ambient `PI_CACHE_RETENTION` override.

## OpenRouter endpoint routing

For `model.provider: "openrouter"`, require a closed
`model.compat.openRouterRouting` object with exactly `only`, `order`,
`allow_fallbacks: false` and `require_parameters: true`. Put one or two distinct full
endpoint tags in `only` and the identical list in `order`, primary first. A tag
matches `^[a-z0-9][a-z0-9_./-]{0,127}$`. With two tags, OpenRouter may try the
second endpoint for the same model before the first token within one host HTTP
attempt. Model fallback and fallback to undeclared endpoints are unsupported.
Pi 1.4.0 serializes the routing policy and nested reasoning fields. OpenRouter
requires configured `service_tier: "default"` and sends that value explicitly to
exclude workspace tier defaults and priority pool admission. That does not prove
applied tier or performance. Refresh advertised full tags before each finite
freeze because base tags can match variants or regions and are not immutable
endpoint identities.
[Routing](https://openrouter.ai/docs/guides/routing/provider-selection) ·
[Tier semantics](https://openrouter.ai/docs/guides/features/service-tiers) ·
[Same-model failover probe](../../docs/acceptance/2026-11-22-failover-routing-probe-309.md)

With two tags, `endpoint_costs` is a closed object with the two declared tags as
its exact keys. Each value is a closed rate object with finite nonnegative
`input`, `output`, `cacheRead` and `cacheWrite` numbers in dollars per million
tokens. Each field of `model.cost` must equal the higher of the two corresponding
rates. The package uses these maximum rates for the in-flight planning bound.
Single-endpoint and direct routes set `endpoint_costs` to null. A direct route
omits `openRouterRouting`.

## HTTP attempts and retry

One logical player request admits at most two host HTTP attempts, the initial
attempt and one shared retry. Each sends the same declared endpoint order.
For failures before assistant output, the host uses Pi's abortable provider-retry
helper. The host alone decides eligibility. Its synthesized retry error carries no status, so Pi's
broader classifier (which also admits 408, 409 and 500) never widens the set. The
declared classes, recorded as `provider-retry.retry_class`, are:

- `server-error`: HTTP 502, 503 or 504, by status alone. HTML or non-JSON bodies
  are eligible, as is a refusal body that fails or exceeds 16 KiB while being read.
- `pre-header-rejection`: a rejected fetch with no response headers. A request
  timeout, cancellation or host deadline latches first and is never retried.
- `provider-403-failover`: HTTP 403 classified as `upstream-provider` after a
  bounded JSON read. A sanitized provider label attributes the refusal upstream.
  The retry resends the same declared endpoint order so an aggregator can route
  around a failing upstream endpoint. On a single-endpoint route, it acts as one
  bounded retry.
  Credit or limit, moderation, authorization and unknown refusals stay terminal.
- `rate-limit`: HTTP 429 whose classifier reads at most 16 KiB of a JSON error
  object; explicit authorization/invalid-request kinds, quota/billing/budget/credit
  limits, malformed or unrecognized errors stay terminal. A 429 whose metadata has
  `limit_source:openrouter_admission_control` is eligible even with no message or
  with account-balance wording (OpenRouter's transient admission hold, which clears
  when automatic refill lands); authorization, key, permission, malformed-request and
  context-length errors stay terminal.
- `stream-start-error`: an HTTP 2xx `text/event-stream` whose first `data:` event
  is an error object or `[DONE]`, or which ends or fails in transport before any
  `data:` event. The host reads it before anything reaches the SDK, until the first
  event or until about 64 KiB (checked per chunk). Keep-alive comments are skipped;
  once a normal event has been read the stream is replayed unchanged, so a later
  error stays terminal. Abort and timeout cancel a stalled read, as for refusal bodies.
  A usable cost in the player's first error event or bounded JSON refusal is
  recorded on that attempt. The SDK can end a stream before exposing a later
  error event's usage. An attempt with no usable cost observed stays unpriced.
- `in-flight-budget`: HTTP 402 only when its metadata has both
  `limit_source:openrouter_in_flight_budget` and `reason:in_flight_budget_exhausted`
  (OpenRouter's documented [transient hold](https://openrouter.ai/docs/api-reference/limits))
  and its `Retry-After` header parses as seconds or an HTTP date. Every other 402,
  including `openrouter_credits`, a missing or mismatched source or reason, or a
  missing, empty or unparseable `Retry-After`, is terminal.

- `incomplete-stream-timeout`: once per actor, the first HTTP 200 event stream of
  a logical request reaches its request deadline after Pi has parsed content,
  reasoning or tool arguments and before a provider finish reason or error. The host aborts and settles that attempt privately. Pi receives only the
  final assistant result, so even a complete-looking tool call in the abandoned
  stream cannot enter the conversation or reach MCP. The same actor can make one
  fresh inference with a new request deadline and byte-identical payload. Its
  projected charge and any in-flight recall must leave the ending reserve intact.
  A computer stop, pending handoff or earlier computer input/observation without
  a confirmed completed operation receipt disables this recovery. Pending ending
  control, cancellation and the original host deadline take precedence. The
  custodian still fences native input immediately on permanent Pause, including
  during the driver's bounded final-report grace.

The retry is shared: whatever the first class, a second failure of any kind is
terminal, so a logical request has at most two observed attempts. A provider
`x-should-retry:false` suppresses recovery for every class. HTTP 500, 408, 409 and
other undeclared statuses and partial-stream failures outside the bounded timeout
case are terminal. The provider stream's own retries remain disabled, so there
is no nested retry loop or assistant-turn restart. Error text is neither traced nor
sent back as model context. Bounded diagnostic identifiers include OpenRouter
metadata error_type, provider_code, limit_source and reason when present; raw
metadata, remedy text and provider bodies are excluded.

Each actual provider fetch emits a start and a completion, including a retry.
A logical request's attempts send the same serialized context. The pre-output
classes share the original request timer across classification, backoff and
response reading. An accepted orderly stop supersedes any unsent ordinary body
or retry with a fresh logical request carrying the control.
Every class stays within the original host and custody deadlines. Pi rejects a
provider-requested retry delay over 60 seconds (the pinned helper's maintained default); its bounded default backoff applies
when no valid delay is supplied. Cancellation interrupts backoff and bounded error
reading. An eligible refusal without usable cost records an unpriced attempt.
Before an ordinary player fetch, including a retry, counted spend plus the
in-flight recall bound, finish reserve, and proposed player request bound must
be strictly below the limit. If only the in-flight recall bound prevents
admission, the host waits for recall settlement and rechecks. At the reserve
the host emits `spend-reserve-reached` once and waits up to two seconds for
orderly stop. The hard spend limit, EOF, cancellation, and deadlines retain
their settlement reasons. A clean expiry settles as `spend-reserve-timeout`.
Only a body carrying the accepted control ID can use the finish reserve.

## MCP tools and control

The MCP config is the driver's current flat server table, with explicit command,
args, cwd, enabled tools and finite startup/tool timeouts. `enabled` must be true;
`required`, if present, must be boolean. Missing allowlisted tools fail before
inference. The validator accepts `default_tools_approval_mode` as a string and
`tools` as a dictionary of option objects keyed by enabled tool names. This adapter
uses neither setting for dispatch or result projection.
The MCP child inherits only PATH and LANG. The maintained transport owns its
child/process group and performs closure; no native cleanup is implied.

Tool calls run sequentially. SDK argument coercion or optional-null removal is a
known zero-dispatch refusal; a later explicit correction can proceed. Full MCP
text and image content pass through `toLlmContent` once; returned `isError: true`
gets one explicit `MCP isError: true` text marker because the provider serializer
otherwise drops error metadata. A known error can lead to deliberate collection
or correction. A transport/client error, rejected call, timeout or cancellation
latches the first fatal reason, aborts the agent, closes the child and suppresses
remaining calls and inference. The bounded provider-only recovery above never
retries a tool/gameplay submission or grants reconnect, replay, fallback,
automatic compaction or session restoration.

The adapter validates the receipt as part of [custody handoff](../../docs/contracts/computer-control.md#computer-operations-and-custody).
It reads a collection's JSON from the first MCP text part. Local MCP `isError`
refusals preserve explicit correction. Invalid successful receipts or incoherent
collections latch `invalid-handoff-receipt`.

Pi's `steer` method wakes the loop for an orderly stop. The host places the
labelled message in the request projection and associates each assistant reply
with its transmitted control ID. The `beforeToolCall` hook suppresses calls
that predate the control.

The adapter validates the [direct `player_finish` call](../../docs/contracts/player-host.md#settlement-and-handoff)
locally. `beforeToolCall` blocks subsequent dispatch in the batch. Pi's `finishTurn`
hook ends the turn after accepted finish or handoff, including batches with
ordinary tool results before the accepted call.

The host reserves at most one second (one quarter of short runs) from its total
budget for cleanup. Stdio closure uses at most 500 ms each for stdin grace and
post-SIGTERM wait. The provider request count and timeouts are finite. Setup and
cleanup share the host budget. SIGINT/SIGTERM use the same abort and closure path.

## Telemetry and accounting

Events carry UTC `wall_time`, host-relative `monotonic_ms`, request IDs and tool
call IDs where applicable. Telemetry version 12 retains request text/UTF-8 counts,
image/decoded-byte counts, message count, complete serialized payload byte count,
model/provider and logical request ID. `request-start.payload_sha256` hashes the
**exact** serialized Fetch `init.body`. No raw request payload, prompt, history,
private reasoning or image bytes are retained in events. The actual provider
request remains unchanged, including SDK-required forwarded reasoning and images,
stable prefix and Pi serialization.

`tool-result` retains actual text, structured game JSON and `isError`, replacing
each image content block with `{type:"image_reference",media_type,bytes,sha256,
image_index}`. Indexes count images within that result. This evidence-only
projection does not mutate canonical MCP/Pi objects or the result delivered to
the agent. Original tool text and raw PNG evidence are retained separately by
their owners; event image references avoid duplicate base64 histories.
`assistant-text` at assistant `message_end` records ordinary visible text parts
only, at most 8192 UTF-8 bytes per message, with explicit `omitted_bytes`. Thinking
parts are excluded. Final report file ownership stays with the runner. Headers,
API keys, private provider errors and private reasoning are excluded.

`response-first-chunk` is the first raw HTTP response-body chunk, including an
error body, before Pi parses it. `response-backend` reports the backend model ID
from parsed provider chunks. Each player or recall `response-complete` records
`reported_provider` from the first usable, sanitized SSE `provider` label, or
null if it is unavailable. Player completions also retain this label in
`response_progress`. A completion records the terminal stop reason and
available usage. Missing provider usage is `usage:null`
with `usage_available:false`; a reported complete input/output count enables
normalized usage. Its `usage.cost` is Pi's estimate from the route's configured rates,
which `cost_source:"configured-rates"` says; Pi discards any cost the provider reports.

### The dollar limit

The adapter reads the raw stream usage records to apply the [reported-cost and spend rules](../../docs/contracts/player-host.md#spend).
It converts each parsed JSON number to its shortest round-trippable decimal and
uses scaled `BigInt` values for sums and comparisons. Telemetry writes plain
decimal text without trailing fractional zeros, with `"0"` for zero.

HTTP refusal status is retained before SDK rejection. `tool-result`
text and structured data retain operation/source joins, with image references in
place of bytes. `tool-refused`, `abort` and `settled` retain refusal and failure outcomes. A pre-output refusal records its
`http_status` (null before headers). A stalled stream records its parsed progress
and aborted stop reason. Each attempt counts its own observed provider charge
or remains explicitly unpriced. Backoff aborts and excessive-delay refusals do not duplicate that first
receipt. `provider-retry` marks eligibility with its `retry_class` and the
configured delay ceiling, then a second-attempt start with the preceding request ID; monotonic intervals expose actual waiting without
inventing the SDK's planned delay. Internal blocked provider attempts create no
fabricated response-completion receipt. Model attention, provider inference start and
physical paint timestamps are unavailable and declared at `host-start`.

Player `abort` and `response-complete` events also snapshot constant-size `response_progress`
metadata for the last observed HTTP attempt, or null before any attempt. Its
`request_id` and `scope` distinguish the current attempt from a completed attempt
retained during tool work, backoff or a spend-limit refusal. Counters reset at
each actual fetch, including a retry; later traffic cannot mutate an emitted
snapshot. `body_bytes`/`body_chunks` count Fetch response-body data observed by the
existing stream transform, not compressed wire bytes or physical network arrival.
`provider_events` counts parsed OpenAI provider events; raw SSE heartbeats can
advance body counters without advancing parsed events.

For the first choice, `content_bytes`, `reasoning_bytes` and `tool_argument_bytes`
sum UTF-8 lengths of observed string fragments. Reasoning uses Pi 1.4.0's first
nonempty `reasoning_content`/`reasoning`/`reasoning_text` alias; tool arguments use
`tool_calls[].function.arguments`. These are neither token counts nor final
source lengths, and do not count opaque reasoning details or other representations.
`last_body_chunk_ms`, `last_provider_event_ms` and `last_field_delta_ms` use the
host's monotonic clock; the last field timestamp advances only for a nonempty
counted fragment. No generated text, reasoning or argument values are added to
these diagnostics. Missing diagnostics remain unknown. Zero observed bytes
does not establish absence of backend generation or explain a timeout. Recording
progress neither extends the active request deadline nor authorizes tool input.
The bounded timeout recovery requires observed assistant output before the deadline. Its observation overhead belongs in subsequent
live measurements.

Telemetry version 12 preserves first/last/max consecutive gaps for body chunks, parsed
provider events and nonempty reasoning/content/tool-argument fragments. Missing
first/last values stay null; max gaps exclude silence after the last fragment.
`provider-payload-ready`, `request-fetch-start`, projection/inspection timings
and the CLI's `settled.event_output` separate some local preparation and logging
costs from Fetch intervals. Output measurements cover synchronous callback,
serialization and enqueue time, bytes and backpressure signals **before** the
settled event; they do not measure disk durability or async drain. Library callers
without sink instrumentation retain null sink measurements. Observing overhead
still adds work and must be measured during subsequent play.

The adapter builds the [context manifest](../../docs/contracts/player-host-telemetry.md#context-manifest)
from the serialized player request just before Fetch.

`host-start` records the configured `provider_routing`, `endpoint_costs`,
`reasoning_format`, output cap, context window, effort mapping,
cut policy (`context_cut`) and image policy (`max_context_images`,
`context_image_block`, also repeated on each `context-image-projection`);
these are transmitted configuration, not backend effort attestation. Sanitized
bounded response/provider IDs and `x-request-id` permit later correlation when
reported. After bounded reading of an HTTP error response, `provider-refusal`
records its status, `body_read`, a closed `refusal_class`, and sanitized
`provider_name`, error type/code, provider code, `limit_source` and `reason`
when available, including terminal refusals and second attempts. Missing,
malformed or unsafe identifiers remain null. See the
[telemetry contract](../../docs/contracts/player-host-telemetry.md#telemetry).
A body-read failure prevents the event except for a 502/503/504, which records
`body_read:false` and null identifiers. `response-headers` adds the server's
requested delay and suppression for 402, 403, 429, 502, 503 and 504. Raw error
messages/bodies and credentials are not logged. This observation adds no fetch,
retry, timer renewal or dispatch; only an eligible first attempt can authorize the
one retry described above. Use the existing
[offline evaluator](../../docs/measurement-guide.md#retained-host-and-browser-analysis)
to analyze traces; future telemetry versions are not silently interpreted.

## Knowledge delivery

The required `--delivered-knowledge` file is `delivered-knowledge/3`; it has no
text-size cap. `validateKnowledge` accepts only its closed forms (articles,
facts, `history` and aliased `sN` sessions, as the
[player host contract](../../docs/contracts/player-host.md#delivered-knowledge-and-recall)
defines them) and refuses every other file. That includes a file whose revisions are
out of order, or whose derived fields (`cited_by_articles`, `backlinks`, `shadowed_by`,
`contradicted_by`, `lifecycle_state` and an article's inherited flags) disagree with
the links and citations they are derived from. It agrees with
`harness/player/knowledge.py` on every file in `tests/fixtures/delivered-knowledge-3/`.
`--finish-reserve-usd` is the frozen reserve from the package.

Every projected entry (briefing and reminder leads, recall and briefing index
rows, cut briefing leads and index rows, update `added` and `updated` entries)
carries `status` when any of these markers apply, in order: `contested`,
`unverified_branch`, `needs_review`, `condition_unverified`. A status change alone
produces an `updated` entry. Actor-start and cut briefings and the first update
from an empty store fit their final JSON within 24,000 UTF-16 code units, including
coverage, escaping, and overflow counts. They keep at most 64 articles and 24
standalone facts and clip snippets at 1,000 code units. Actor-start briefings
give recall-selected leads first claim on the budget, then fill the index in
tiers of articles, other standalone facts, and instance-state facts. Each tier
uses newest position first with delivered-order ties, and the kept entries
appear in delivered order. Ordinary live updates carry full changed leads.
With `--knowledge-updates LIST`, an unref'd refresh in `runHost` (at start, every
`UPDATE_POLL_MS` and after each player response, one at a time) reads the driver's
list and its files through the isolated `update-reader.mjs` helper (terminated on
settlement so a stalled read never blocks CLI exit) and stages verified candidates
above its own (`updateEntry`, `validateKnowledge`, `updateDelivery` in
`knowledge.mjs`) and coverage lines (`coverageEntry`). Building a player request
jointly plans coverage, the cut, and the pending reminders for candidate versions
from newest to oldest. Adoption requires the final projection to fit below the
context window with the configured token reserve. The
[update rules](../../docs/contracts/player-host.md#a-newer-version-during-play)
own what is checked and recorded. Nothing waits for the refresh, and it never stops the host.

With `context_cut` enabled, a `coverage-update-entry/1` line supplies the verified
operation boundary for that version, or permanently invalidates further cuts
for this actor after a restore. The host cuts whole turns only through applicable
coverage for adopted knowledge. Pressure arms the cut until coverage allows it.
The host chooses the smallest fitting covered prefix that meets both targets or,
when no prefix reaches both targets, falls back to the full covered prefix (`k = E`)
if it fits and strictly reduces estimated tokens (otherwise holding with
`insufficient-cover`). Independent capacity rescue can remove fewer than
`min_free` turns. The new prefix carries a bounded briefing and a marker with
the omitted frames' sources and the last five distinct committed public intents.
The
[cut contract](../../docs/contracts/player-host.md#coverage-gated-context-cut)
defines the boundaries, and the
[telemetry contract](../../docs/contracts/player-host-telemetry.md#context-cut)
defines the cut and holdback events.

The route pins `recall:{model,every,unpriced_request_usd,endpoint_costs}` with the
same provider and credential variable as the player. Recall validates its own
endpoint tags and rates and makes one host HTTP attempt. Recall counts and
request IDs begin at fetch. Recall sends a version-stable, title-first index
within 24,000 UTF-16 code units and validates selections against its actual rows.
The second message carries `already_in_context`, computed from complete leads
that survive in the player projection. If every sent row is already present, the
host skips recall. It filters completed reminders again when placing them, after
any update or cut. Delivery telemetry records one outcome per logical placement
at terminal settlement. A successful response with usable cost is `delivered`.
Other terminal outcomes are `undelivered`. Pre-request update refusals are
`refused`.

The [recall contract](../../docs/contracts/player-host.md#delivered-knowledge-and-recall)
defines selection, delivery and accounting. For OpenRouter the adapter's `onPayload`
hook sends a strict `response_format` of type `json_schema`, with only `articles`,
an array of strings. The pinned upstream must accept it because the route sets
`require_parameters: true`. Direct routes omit `response_format`.
