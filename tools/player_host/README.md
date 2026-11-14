---
owner: lead
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Bounded Pi player host

This private package is the Pi-based adapter that implements the host-neutral
[player-host contract](../../docs/contracts/player-host.md) (`player-host/5`);
the campaign driver selects it only through the package's frozen `host.argv`.
The [current component](../../docs/components/player-interface.md) owns the player interface;
[`069-controllable-player-host.md`](../../docs/changes/069-controllable-player-host.md)
retains the original offline adoption decision.
It uses Pi agent-core, AI serialization and MCP 1.4.0 directly. It loads no coding
agent application, personal settings, sessions, shell/file tools or resources.
Host maintenance belongs to the engineering lead.
The campaign driver invokes the frozen `host.argv` followed by a mode word with
frozen provider/MCP/context inputs; no coding-agent launch or resumed-host fallback
is supported. Host choice
is independent of whether a particular model passes gameplay qualification.
A separately admitted gameplay adviser, which only proposes, uses this same core
with its own explicit context, tool profile and budget; the campaign driver does
not automatically activate it.

From this directory, install and test with project-local dependencies:

```sh
npm --userconfig /dev/null --cache ../../.cache/npm ci --ignore-scripts --no-audit --no-fund
ENACTIVE_TEST_PYTHON=/absolute/project/.venv/bin/python npm test
```

Node >=22.19.0 and the repository's Python environment with MCP 2.x are required.
The tests invoke actual Pi provider serialization against synthetic SSE and local
HTTP fixtures, and official Python MCP servers (the shared double is
`tests/fixtures/player_host_mcp.py`), including current production
schema discovery. The adapter-agnostic contract suite
(`tests/test_player_host_contract.py`) drives this runner only through its argv,
files, environment and exit status; `tests/test_player_host_adapter.py` runs these
Node tests from pytest. They make no inference calls and start no game. Reported sample
timings include fixture process startup and cleanup; they do not measure model
latency, gameplay competence or a hardware-independent performance threshold.
The in-flight tool-deadline case uses a controlled Node timeout clock only after
observing actual fixture tool start; startup/signal cases and outer watchdogs
retain real time, and all cases retain actual child-closure assertions.

`node --test` runs each `test/*.test.mjs` file in its own process, several at a
time, and the cases inside one file one after another. Almost all the time is
Python MCP child startup, so the `runHost` cases are divided by responsibility
(route configuration, context projection, tool dispatch, provider requests, MCP
connection, the three retry files, control and finish, handoff) and share the
route, provider responses and `scenario` runner in `test/host-scenario.mjs`. Add
a case to the file that owns its responsibility, or to a new descriptively named
file, rather than growing one file until it sets the suite's wall time. Each
host run starts its own child in a fresh temporary directory, so the files share
no state.

The runner requires a leading mode word. `validate` checks the route and MCP
table offline and exits zero only if both are accepted, writing nothing to stdout:

```sh
node tools/player_host/run.mjs validate \
  --config FROZEN/route.json --mcp-config FROZEN/mcp-template.json \
  --model MODEL --effort EFFORT
```

`run` hosts one actor. The driver invokes:

```sh
node tools/player_host/run.mjs run \
  --config FROZEN/route.json \
  --mcp-config FROZEN/mcp.json \
  --context FROZEN/context.txt --prompt FROZEN/prompt.txt \
  --session SESSION_32HEX --actor-id ACTOR_32HEX \
  --pending-control-id none \
  --model MODEL --effort EFFORT --timeout-seconds SECONDS \
  -o DRIVER_RESERVED_FINAL_FILE
```

Each frozen input file is limited to 1 MiB and must be regular. Stdin remains an
open JSONL control pipe, not the initial prompt. For a successor with inherited
stop, `--pending-control-id` is its 32hex command ID rather than `none`; the host
waits for that exact command before MCP connection or any provider fetch.
The driver exclusively reserves the final path; the runner writes that existing
path only with the report from successful direct `player_finish` settlement and leaves it unchanged after a
handoff or any failure. JSONL events go to stdout. A missing or unknown mode, or a
missing, repeated or unknown flag, settles `invalid-arguments` and exits one.
Exit zero requires direct finish or completed-handoff settlement below, no fatal
failure latch, successful owned MCP closure, and any required final-file write.
Ordinary terminal assistant text alone fails as `incomplete-terminal-response`.
`runHost(options)` is the
programmatic seam; tests inject `fetch` there. No fake-provider CLI is exposed.

The closed route has exactly `schema: "player-host/5"`, `model`,
`api_key_env`, `max_requests`, `request_timeout_seconds`, `service_tier`, the required positive
integer `max_context_images` and the required integer `context_image_block`
(1 ≤ block ≤ `max_context_images`), plus required safe-integer
`context_reserve_tokens` (`maxTokens` ≤ reserve < `contextWindow`) and the two dollar
amounts `spend_limit_usd` (above zero) and `unpriced_request_usd`, each plain decimal
text ([the dollar limit](#the-dollar-limit)).
`pi-player-host/1` through `/4`, `player-host/1` through `/3` and
missing/invalid fields are rejected; closed historical configurations and traces are
evidence, not runnable current inputs.
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
rates at1.5× standard, which also raises the bound a request with no cost record
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

Freeze the actual provider's image-part allowance explicitly as `max_context_images`,
the hard peak of pixel images per request; the host imposes no universal provider
limit (DeepInfra, for example, rejects more than 30). Pi's maintained
`transformContext` hook keeps historical images within that peak while preserving
all text, reasoning, tool calls/results and IDs. Eviction is count-only, in whole
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
(`session-affinity-missing`) if a request would go out without it. Whether OpenRouter
honours sticky routing with a pinned `provider.order` is unmeasured; the paid
verification decides. The entire latest assistant tool-call batch is protected,
including when its final result contains only text. If that group alone exceeds
the allowance, the host stops before another provider request or request charge.
Historical omitted image parts become explicit text markers with original message/
image provenance and hash: pixels were not forwarded in this request, and the
marker grants no source-read proof or authority. The marker names the frame's
`source_id` (from its tool result) and says to read it again with `player_source`;
the player can request the exact source again through its available tools. No tool is called automatically to restore an image.

The request projection adds no standing countdown. Instead, once a threshold is
passed, each request adds a notice. The notice stays in the history where it was
first sent, so every request extends the previous one for the provider's cache. It
warns before each stop
the host enforces itself: context capacity, `max_requests` (a tenth of the allowance
left, at least two and at most half) and the work deadline (a tenth left, at least a
minute and at most half). See the contract's
[request-stability rules](../../docs/contracts/player-host.md#request-stability-and-tail-notices).
Every actor shares one system prompt and tool table. The ongoing user objective
survives actor turnover; experiment quotas, final-actor policy and ending reserves
stay in operator accounting. MCP's typed actor projection returns
`player-computer-result/2` (a short result: status, frame `source_id` and size, and for
a pending, partial or unknown delivery the operation identifier and next step; the full
`player-computer-operation/1` record rides in `structuredContent`, which the host reads
for `source_id` and the handoff receipt, records in the trace and never forwards to the
model), `player-error/2` and `player-transport/2`, without global
deadline/remaining fields; canonical operator records retain original accounting.
The host reuses Pi's `estimateContextTokens`, reported usage and a heuristic
text/image floor to request the existing sealed handoff before critical context
pressure. These are not exact provider token bounds. Known oversized context
stops before fetch; no text compaction, restore or fallback is introduced.

Live agent messages retain the pixels needed by the provider. Original source
images stay in the mechanical/player stores. Telemetry stores image references
and the exact `request-start.payload_sha256`, sizes and counts, never the raw
projected body or private reasoning. Context projection events expose omissions. This is a declared image-history
window, without text summarization, automatic compaction, replay or permission
renewal. Qualification must include actual continuation and apparent effects;
reducing images alone is not a latency pass.

Pi1.4.0's full `anyOf` validation can describe an unrelated memory type when a
selected Work body is invalid. `validation-feedback.mjs` supplies a request-only
diagnostic using the same `validateToolArguments`, narrowing only the existing
`intent.entry_type` alternatives and retaining surrounding constraints. It never
changes arguments, tool schemas, normal SDK validation, execution or collection.
It requires a unique completed call/result batch, `isError`, absent `durationMs`,
one text part with the exact SDK validation header, a known unambiguous branch,
and no parser `argumentsError`. In pinned Pi, executed calls always carry a
duration, including zero and exceptions. Parser/blocked errors have other headers;
MCP errors keep their original path. If the narrowed check passes, the original
refusal stays. No independent validator, successful-call revalidation or SDK fork
is introduced.

Canonical history stays unchanged. The existing trace's
`tool-validation-feedback` event retains the original SDK result, exact call ID
and projected text before forwarding. A weak memo of canonical call/result
objects avoids repeating diagnostic work and keeps earlier feedback stable in
later request prefixes; batch pairing is checked anew. This happens before image
projection clones messages. These diagnostics prove neither semantic truth nor
gameplay success and grant no input authority. Recheck these SDK assumptions on
upgrade and retire the helper when upstream supplies precise union feedback.

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


For `model.provider: "openrouter"`, require a closed
`model.compat.openRouterRouting` object with exactly `only: ["FULL_TAG"]`,
`order: ["FULL_TAG"]`, `allow_fallbacks: false` and `require_parameters: true`.
Pi1.4.0 owns its provider-policy and nested reasoning serialization; no arbitrary
payload/header injection is admitted. Direct routes reject this policy. OpenRouter
requires configured `service_tier: "default"` and sends that value explicitly to
exclude workspace tier defaults and priority pool admission. That does not prove
applied tier or performance. Refresh advertised full tags before each finite
freeze; base/prefix tags can match variants/regions and are not immutable endpoint
identities. Actual provider metadata and failures remain evidence, without automatic
fallback or a claim that Baseten's base tag identifies its FAST benchmark variant.
`host-start.provider_routing` and `reasoning_format` retain configured policy;
parsed stream IDs/provider names and optional generation metadata establish only
what the service actually reports. See [routing](https://openrouter.ai/docs/guides/routing/provider-selection)
and [tier semantics](https://openrouter.ai/docs/guides/features/service-tiers).

One inference request may recover once from one eligible transient failure before
assistant output, using Pi's maintained abortable provider-retry helper. The host
alone decides eligibility; its synthesized retry error carries no status, so Pi's
broader classifier (which also admits 408, 409 and 500) never widens the set. The
declared classes, recorded as `provider-retry.retry_class`, are:

- `server-error`: HTTP 502, 503 or 504, by status alone. HTML or non-JSON bodies
  are eligible, as is a refusal body that fails or exceeds16KiB while being read.
- `pre-header-rejection`: a rejected fetch with no response headers. A request
  timeout, cancellation or host deadline latches first and is never retried.
- `rate-limit`: HTTP 429 whose classifier reads at most16KiB of a JSON error
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
- `in-flight-budget`: HTTP 402 only when its metadata has both
  `limit_source:openrouter_in_flight_budget` and `reason:in_flight_budget_exhausted`
  (OpenRouter's documented [transient hold](https://openrouter.ai/docs/api-reference/limits))
  and its `Retry-After` header parses as seconds or an HTTP date. Every other 402,
  including `openrouter_credits`, a missing or mismatched source or reason, or a
  missing, empty or unparseable `Retry-After`, is terminal.

The retry is shared: whatever the first class, a second failure of any kind is
terminal, so a logical request has at most two charged attempts. A provider
`x-should-retry:false` suppresses recovery for every class. HTTP 500, 408, 409 and
other statuses, failures after `<400` headers (inside Pi's stream) and partial-stream
failures are terminal. The provider stream's own retries remain disabled, so there
is no nested retry loop or assistant-turn restart. Error text is neither traced nor
sent back as model context. Bounded diagnostic identifiers include OpenRouter
metadata error_type, provider_code, limit_source and reason when present; raw
metadata, remedy text and provider bodies are excluded.

`max_requests` counts each actual provider HTTP fetch attempt, including the retry.
The host checks and charges immediately before fetching; a refused extra attempt
has no fabricated request/completion. Both attempts send the same serialized
context under one original request timer, combined abort signal and host deadline.
Classification, backoff and response reading consume that timer. Pi rejects a
provider-requested retry delay over60seconds (the pinned helper's maintained default); its bounded default backoff applies
when no valid delay is supplied. Cancellation interrupts backoff and bounded error
reading. The first eligible refusal records unknown usage, without a zero-price
assumption; another attempt requires spare capacity before any backoff.

The MCP config is the driver's current flat server table, with explicit command,
args, cwd, enabled tools and finite startup/tool timeouts. `enabled` must be true;
`required`, if present, must be boolean. Missing allowlisted tools fail before
inference. Codex approval and per-tool presentation dictionaries are accepted as
presentation settings; they do not change the exact schema or truncate results.
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

A sealed `player_handoff` response, or collection
through `computer_result` of this host's one pending original handoff, ends this
host. The receipt is the operation record `player-computer-operation/1`: the structured
content of a direct `player_handoff` result (the model reads only its short
`player-computer-result/2` text) or the first MCP text of a collection. It must bind matching 32-character hex operation/session/actor
IDs and a current `player-handoff/1` issuance with matching IDs, a 32-character hex context ID,
64-character hex context digest, positive finite sealing time and `grants_authority:false`.
There are no game-phase, menu, identity or source-checkpoint requirements.
Only this host's direct response can establish an origin; collection must request
that exact operation and return its original session/actor. A direct
`player-transport/2` unknown receipt establishes only the pending origin.
Unrelated reads and reads without an origin never settle the host. Local MCP
`isError` refusals establish no origin and preserve explicit correction. Invalid
successful direct receipts and incoherent original collection latch a fatal stop.
Unsupported old mission/player-view receipts are rejected.

The host latches the issuance, refuses every later call in that sequential batch
before dispatch, and uses Pi's maintained `finishTurn` hook to end before another
provider request, including batches with ordinary tools before handoff. The
`handoff` event carries session/actor, operation as `handoff_id`, context ID/digest
and `grants_authority:false`. Settlement has reason `handoff`, can end with assistant
`toolUse`, and leaves the reserved final file unchanged.
Fatal cancellation, deadlines, transport and cleanup failures still win. The
host closes its owned MCP child. The driver independently validates canonical
issuance/context and actual old host/MCP process-group quiescence before minting
a successor under original limits; host settlement grants no authority.

Stdin carries closed `player-control/1` objects with exactly
`schema,id,session,actor_id,type`; `type` is `orderly_stop`, with bound 32hex IDs.
The line limit is 4096 UTF8 bytes before newline. Identical duplicates are
idempotent. Conflicting or malformed control, wrong identity/version, oversized
lines and unexpected EOF latch failure and close owned MCP. The driver retains
intent before writing and preserves pending stop across the whole admission.

Pi's `steer` and turn hooks deliver one fixed labelled finish-up request without
countdowns, tactics or a Save/Quit mandate. Unsent calls from a pre-control turn
are withheld; dispatched input is not canceled/replayed for text delivery. New
handoff is refused before sealing while stop is pending. If a handoff already
sealed, the driver may deliver the same command to a verified successor under
original reserves, gated as above, or record incomplete ending. Pause, hard
deadlines and owned cleanup remain independent of model response or game saving.

The host adds reserved `player_finish` beside MCP tools, with closed
`disposition,report,source_ids,control_id` arguments. Dispositions are
`task_complete`, `cannot_continue`, `external_stop_complete`; report≤8192characters,
unique source IDs≤16 (each1..128characters). External completion must name the
directly received control; other dispositions require null. Only validated direct
execution accepts it. Remembered/nested JSON and ordinary narration cannot finish
the task. Acceptance stops later tool/provider dispatch through Pi's `finishTurn`
hook and records `player-finish` plus settlement. Supporting claims remain fallible;
host success, stopped automation, persistence, native exit and owned absence are
separate facts. The admission's reserve forecast includes the largest burst and
in-flight delivery delay; field validation does not establish adequate capacity.

The host reserves at most one second (one quarter of short runs) from its total
budget for cleanup. Stdio closure uses at most 500 ms each for stdin grace and
post-SIGTERM wait. The provider request count and timeouts are finite. Setup and
cleanup share the host budget; SIGINT/SIGTERM use the same abort/closure path.

Events carry UTC `wall_time`, host-relative `monotonic_ms`, request IDs and tool
call IDs where applicable. Telemetry version 5 retains request text/UTF8 counts,
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
from parsed provider chunks. `response-complete` reports the Pi model/provider,
terminal stop reason and available usage. Missing provider usage is `usage:null`
with `usage_available:false`; a reported complete input/output count enables
normalized usage. Its `usage.cost` is Pi's estimate from the route's configured rates,
which `cost_source:"configured-rates"` says; Pi discards any cost the provider reports.

### The dollar limit

The host stops at the route's `spend_limit_usd`, counted from what the provider
reports; the [contract](../../docs/contracts/player-host.md#spend) states the rule.
In this adapter:

- **Counting.** Each HTTP attempt counts once, when its `response-complete` is
  written: at `reported_cost_usd` when that is not null, otherwise at the route's
  `unpriced_request_usd`. The event carries `counted_cost_usd`, `cost_counted_as`
  (`provider-reported` or `unpriced-bound`) and the running `spent_usd`. Every attempt
  ends in a `response-complete`, a failed or aborted one included. `settled` carries
  the total `spent_usd` and the count of `unpriced_requests`, which the driver checks
  against its own sums from the trace.
- **`spend-limit`.** The check sits beside the `max_requests` check: on entering a
  logical request, before every fetch, and after a first attempt fails and before its
  retry. When the total has reached the limit the host stops and sends nothing. A
  request already sent finishes, so the total can pass the limit by at most what one
  request counts.
- **`cost-unreported`.** A response that did not fail (stop reason other than `error`,
  `aborted`, `length` or `deferred`) with a null `reported_cost_usd` stops the host
  before any tool call from it is dispatched. It has counted at the bound.
- **The bound is not computed here.** `unpriced_request_usd` comes from the route;
  the package check computes it from the route's configured rates.
- **No notice** is added for dollars. The driver's ending reserve asks for an orderly
  finish before the limit.

`response-complete.reported_cost_usd` is the cost the provider itself reported
for that response, read from the same raw usage record of the stream. The rule is the curator's
(`tools/curator_host/providers.py`, `reported_cost`), and both hosts' tests run the
usage records in `tests/fixtures/provider-usage-cost.json`:

- A route that is not on the caller's own provider key counts the larger of `cost` and
  `cost_details.upstream_inference_cost`. On the pinned route the two were equal in the
  [pilot of 12 November 2026](../../docs/acceptance/2026-11-12-provider-cost-pilot-555.md).
- An own-key route (`is_byok` true) counts their sum, the fee plus the upstream cost.
- If a response carries several usage records, the largest counts.
- A response with no cost, or with a malformed one (negative, non-finite, not a number,
  an own-key record missing either amount, or one malformed record among several), has
  `reported_cost_usd:null`. Missing cost stays unknown; it is never estimated. Token
  counts are not needed for a cost, and a cost is not needed for `usage_available`.
- The value is a plain decimal string in US dollars, such as `"0.0001893"`: no exponent,
  no trailing zeros, `"0"` for zero. Each JSON number is turned once into the shortest
  decimal that reads back as the same number, which is the provider's own digits for up
  to 15 significant digits, and sums and comparisons use integers, so no floating-point
  arithmetic touches the amount. The route's two amounts and every counted amount and
  total use the same text and the same integer arithmetic.

HTTP refusal status is retained before SDK rejection. `tool-result`
text and structured data retain operation/source joins, with image references in
place of bytes. `tool-refused`, `abort` and `settled` retain refusal and failure outcomes. An eligible first attempt has a transport-derived
`response-complete` with its `http_status` (null for a pre-header rejection), error
stop reason, unknown usage, a null reported cost and the bound as its counted cost; the final attempt is completed by the SDK assistant
message. Backoff aborts and excessive-delay refusals do not duplicate that first
receipt. `provider-retry` marks eligibility with its `retry_class` and the
configured delay ceiling, then a second-attempt start with the preceding request ID; monotonic intervals expose actual waiting without
inventing the SDK's planned delay. Internal blocked provider attempts create no
fabricated response-completion receipt. Model attention, provider inference start and
physical paint timestamps are unavailable and declared at `host-start`.

`abort` and `response-complete` also snapshot constant-size `response_progress`
metadata for the last charged HTTP attempt, or null before any attempt. Its
`request_id` and `scope` distinguish the current attempt from a completed attempt
retained during tool work, backoff or a request-limit refusal. Counters reset at
each actual fetch, including a retry; later traffic cannot mutate an emitted
snapshot. `body_bytes`/`body_chunks` count Fetch response-body data observed by the
existing stream transform, not compressed wire bytes or physical network arrival.
`provider_events` counts parsed OpenAI provider events; raw SSE heartbeats can
advance body counters without advancing parsed events.

For the first choice, `content_bytes`, `reasoning_bytes` and `tool_argument_bytes`
sum UTF8 lengths of observed string fragments. Reasoning uses Pi1.4.0's first
nonempty `reasoning_content`/`reasoning`/`reasoning_text` alias; tool arguments use
`tool_calls[].function.arguments`. These are neither token counts nor final
source lengths, and do not count opaque reasoning details or other representations.
`last_body_chunk_ms`, `last_provider_event_ms` and `last_field_delta_ms` use the
host's monotonic clock; the last field timestamp advances only for a nonempty
counted fragment. No generated text, reasoning or argument values are added to
these diagnostics. Missing older diagnostics remain unknown; zero observed bytes
does not establish absence of backend generation or explain a timeout. Recording
progress never renews a timer, retries a partial response, changes provider
context or authorizes tool input. Its observation overhead belongs in subsequent
live measurements.

Telemetry version 5 preserves first/last/max consecutive gaps for body chunks, parsed
provider events and nonempty reasoning/content/tool-argument fragments. Missing
first/last values stay null; max gaps exclude silence after the last fragment.
`provider-payload-ready`, `request-fetch-start`, projection/inspection timings
and the CLI's `settled.event_output` separate some local preparation and logging
costs from Fetch intervals. Output measurements cover synchronous callback,
serialization and enqueue time, bytes and backpressure signals **before** the
settled event; they do not measure disk durability or async drain. Library callers
without sink instrumentation retain null sink measurements. Observing overhead
still adds work and must be measured during subsequent play.

`context-manifest` (absent from archived version 3 traces recorded before 6 November 2026)
records, once per HTTP attempt before the fetch, the ordered parts of the payload as
roles, kinds, sizes and SHA-256 digests with tool-call, image and source identities,
delta-encoded against the previous attempt; it stores no text or pixels. The replay rule
and fields are in [the contract](../../docs/contracts/player-host.md#context-manifest).

`host-start` records the configured output cap, context window, effort mapping and
image policy (`max_context_images`, `context_image_block`, also repeated on each
`context-image-projection`);
these are transmitted configuration, not backend effort attestation. Sanitized
bounded response/provider IDs and `x-request-id` permit later correlation when
reported. After bounded reading of an HTTP error response, `provider-refusal`
records its status, `body_read`, and allowlisted error type/code, provider code and
server-reported `limit_source` and `reason` when available, including terminal
refusals and second attempts. Missing, malformed or unsafe identifiers remain null.
A body-read failure prevents the event except for a 502/503/504, which records
`body_read:false` and null identifiers. `response-headers` adds the server's
requested delay and suppression for 402, 429, 502, 503 and 504. Raw error
messages/bodies and credentials are not logged. This observation adds no fetch,
retry, timer renewal or dispatch; only an eligible first attempt can authorize the
one retry described above. Use the existing
[offline evaluator](../../docs/evaluation.md#retained-host-and-browser-analysis)
to analyze traces; future telemetry versions are not silently interpreted.

## Frozen knowledge delivery

The required `--delivered-knowledge` file is `delivered-knowledge/1`; it has no text-size cap. `--finish-reserve-usd` is the frozen reserve from the package. The closed route additionally requires `recall:{model,every,max_requests,unpriced_request_usd}` with the same provider and credential variable as the player. `max_requests` limits all player and recall HTTP attempts together; the nested maximum is a per-run recall allowance that the driver reduces by prior actors' recall attempts (their whole recall allocation when accounting is incomplete). Recall counts and request IDs begin at fetch, where both attempt limits are checked again; it never takes the player's final attempt.

The first user message carries a labelled fallible briefing and complete remaining index, including standalone facts and coverage. Recall reminders run beside play, become separate labelled messages, and preserve the sent prefix. Recall failure or absent cost disables recall alone. A valid reported cost is retained when selection is rejected or a response stops for length; only missing or invalid cost uses the bound. `recall-N` attempts share counted spend and limits, include every in-flight bound in admission, and never begin after an orderly stop or when spent plus an in-flight player bound plus the finish reserve reaches the limit. Empty knowledge makes no recall request. The host aborts and counts an in-flight recall at actor end. Settlement carries separate `unpriced_requests` and `unpriced_recall_requests` counts; telemetry 5 records `knowledge-delivery`, `knowledge-recall` (including silence/failure/not-made) and `knowledge-undelivered`. The full boundary is in the player-host contract.
