# Bounded Pi player host

This private package is the mandatory generic campaign-player host. The
[current component](../../docs/components/player-interface.md) owns its contract;
[`069-controllable-player-host.md`](../../docs/changes/069-controllable-player-host.md)
retains the original offline adoption decision.
It uses Pi agent-core, AI serialization and MCP 1.4.0 directly. It loads no coding
agent application, personal settings, sessions, shell/file tools or resources.
Host maintenance belongs to the engineering lead.
The campaign driver always invokes this runner with frozen provider/MCP/context
inputs; no coding-agent launch or resumed-host fallback is supported. Host choice
is independent of whether a particular model passes gameplay qualification.
Separately admitted gameplay advisers/reflectors use this same core with their
own explicit context, tool profile and budget; the campaign driver does not
automatically activate those roles.

From this directory, install and test with project-local dependencies:

```sh
npm --userconfig /dev/null --cache ../../.cache/npm ci --ignore-scripts --no-audit --no-fund
ENACTIVE_TEST_PYTHON=/absolute/project/.venv/bin/python npm test
```

Node >=22.19.0 and the repository's Python environment with MCP 2.x are required.
The tests invoke actual Pi provider serialization against synthetic SSE and local
HTTP fixtures, and official Python MCP servers, including current production
schema discovery. They make no inference calls and start no game. Reported sample
timings include fixture process startup and cleanup; they do not measure model
latency, gameplay competence or a hardware-independent performance threshold.
The in-flight tool-deadline case uses a controlled Node timeout clock only after
observing actual fixture tool start; startup/signal cases and outer watchdogs
retain real time, and all cases retain actual child-closure assertions.

The driver invokes:

```sh
node tools/player_host/run.mjs \
  --config FROZEN/player-pi-configuration.json \
  --mcp-config FROZEN/player-host-configuration.json \
  --context FROZEN/pi-player-context.txt \
  --model MODEL --effort EFFORT --timeout-seconds SECONDS \
  -o DRIVER_RESERVED_FINAL_FILE < FROZEN/prompt.txt
```

Each frozen file and stdin is limited to 1 MiB. Files must be regular files.
The driver exclusively reserves the final path; the runner writes that existing
path only after successful terminal completion. JSONL events go to stdout.
Exit zero requires terminal assistant `stop` or the completed-handoff settlement
below, no fatal failure latch, successful owned MCP closure, and a successful
final-file write. `runHost(options)` is the
programmatic seam; tests inject `fetch` there. No fake-provider CLI is exposed.

The closed route has exactly `schema: "pi-player-host/2"`, `model`,
`api_key_env`, `max_requests`, `request_timeout_seconds` and the required positive
integer `max_context_images`. Version1 and missing/invalid limits are rejected;
closed historical configurations are evidence, not runnable current inputs.
`model` contains Pi's
explicit `id`, `name`, `api: "openai-completions"`, `provider`, `baseUrl`,
`reasoning`, `input`, `cost`, `contextWindow` and `maxTokens`; optional `type`,
`thinkingLevelMap` and the supported `compat` properties are validated in
`validateConfiguration`. Both text and image input are mandatory. URL userinfo,
query strings and fragments, arbitrary headers, other APIs and unknown fields
are refused. Model metadata and costs are configuration, not verified provider
capabilities or billing evidence.

Freeze the actual provider's image-part allowance explicitly; the host imposes no
universal provider limit. Pi's maintained `transformContext` hook keeps the newest
historical images within that allowance while preserving all text, reasoning,
tool calls/results and IDs. The entire latest assistant tool-call batch is protected,
including when its final result contains only text. If that group alone exceeds
the allowance, the host stops before another provider request or request charge.
Historical omitted image parts become explicit text markers with original message/
image provenance and hash: pixels were not forwarded in this request, and the
marker grants no source-read proof or authority. Existing source IDs remain in
their unmodified text; the player can request the exact source again through its
available tools. No tool is called automatically to restore an image.

The request-only projection also appends one clearly labelled, software-generated
resource-status message after history. It reports actual HTTP attempts charged
before that request and remaining allowance including it. An eligible retry uses
the identical body, so its note remains the original context-construction snapshot;
the next assistant turn includes both charged attempts. This bookkeeping is not a
human task, gameplay evidence, a read declaration, authority or a quality/latency
metric. It does not enter canonical agent history, accumulate old notes or change
the stable system/tool prefix. The hard cap, deadlines and frozen ending reserves
still apply; seeing a counter does not establish that a player will honor them.

Original agent messages and complete MCP `tool-result` trace entries retain the
pixels. `request-start.payload` records the actual projected provider body; context
projection events expose the count and omissions. This is a declared image-history
window, without text summarization, automatic compaction, replay or permission
renewal. Qualification must include actual continuation and apparent effects;
reducing images alone is not a latency pass.

For nonreasoning models effort must be `off`. For reasoning models the selected
Pi effort (`off`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`) must have a
non-null explicit `thinkingLevelMap` entry, with
`compat.supportsReasoningEffort: true` and `compat.thinkingFormat: "openai"`.
Direct Pi streaming sends the declared mapping without its simple-stream effort
clamping. Other reasoning formats need conformance evidence before support.

Credentials come only from the explicitly named environment variable, resolved
when preparing a provider call. The runner refuses `OPENAI_LOG`,
`OPENAI_CUSTOM_HEADERS`, `OPENAI_ORG_ID`, or `OPENAI_PROJECT_ID` in its environment
with `ambient-provider-configuration`: OpenAI SDK 7.19.0 reads these independently
of Pi's scoped environment and they can enable raw logging or inject headers.
Clear them only in the dedicated host child's environment; the package never
mutates the parent environment or a profile. No key values, headers or raw
provider exceptions are emitted. Pi cache retention is explicitly `short`, preserving the maintained default
while preventing an ambient `PI_CACHE_RETENTION` override.

One inference request may recover from one eligible HTTP429 before assistant
output, using Pi's maintained abortable provider-retry helper. Its classifier reads
at most16KiB of a JSON error object; explicit authorization/invalid-request kinds,
quota/billing limits, malformed or unrecognized errors stay terminal. A provider
`x-should-retry:false` also suppresses recovery. The second429, other HTTP statuses,
transport failures and partial-stream failures are terminal. The provider stream's
own retries remain disabled, so there is no nested retry loop or assistant-turn
restart. Error text is neither traced nor sent back as model context.

`max_requests` counts each actual provider HTTP fetch attempt, including the retry.
The host checks and charges immediately before fetching; a refused extra attempt
has no fabricated request/completion. Both attempts send the same serialized
context under one original request timer, combined abort signal and host deadline.
Classification, backoff and response reading consume that timer. Pi rejects a
provider-requested retry delay over5seconds; its bounded default backoff applies
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
remaining calls and inference. The bounded provider-only429 recovery above never
retries a tool/gameplay submission or grants reconnect, replay, fallback,
automatic compaction or session restoration.

A coherent completed handoff response from `enactive_handoff` or collection of
that host's own pending/uncertain handoff ends this host. Only the actual MCP receipt is inspected:
current `player-view/5` and `mission/11`, settled delivered accepted completion,
matching issuance/operation, original actor/mission and an issued post-Pause source.
Successor-role/Work selections must match this host's original handoff intent.
Collection is armed only by its actual handoff response or original-collection
identity after an uncertain handoff call, and must name that same mission/operation.
A fresh successor's read of its assigned issuance does not settle its host. A
newer read-only Observe can be current while the issued checkpoint stays fixed;
the driver checks the actual checkpoint/native binding separately.
Claimed but incoherent completion is fatal; draft refusals, unfinished results
and ordinary collection errors leave explicit correction/collection available. Model prose and other tools are
not settlement evidence.

The host latches the receipt, refuses every later call in that sequential batch
before dispatch, and uses Pi's maintained `finishTurn` hook to end before another
provider request, including batches with ordinary tools before handoff. Original
MCP results remain intact in the trace. Settlement has reason `handoff`, can end
with assistant `toolUse`, and writes empty final text (a newline in the reserved
CLI file). Fatal cancellation, deadlines, transport and cleanup failures still
win. This ends the original host; it grants no successor authority or native
cleanup. The driver still validates the complete canonical issuance and fresh
runtime/custody/actor/source/Pause/budget state before assigning a fresh successor.

The host reserves at most one second (one quarter of short runs) from its total
budget for cleanup. Stdio closure uses at most 500 ms each for stdin grace and
post-SIGTERM wait. The provider request count and timeouts are finite. Setup and
cleanup share the host budget; SIGINT/SIGTERM use the same abort/closure path.

Events carry UTC `wall_time`, host-relative `monotonic_ms`, request IDs and tool
call IDs where applicable. `request-start` reports message text parts/UTF-8 bytes,
image parts/decoded bytes and complete serialized payload bytes. Text counts
include tool-call argument strings; schema bytes are included in payload bytes.
Its `payload` field retains the complete JSON body at each actual HTTP fetch for the
provider, including schemas, context, images and forwarded reasoning/tool history.
These private run traces contain model context; headers and API keys are excluded.
Unforwarded assistant content and failed final text are not retained. Body
serialization and disk writes add cost, which must remain in live measurements;
the earlier metadata-only fixture measurement does not qualify that overhead.
`response-first-chunk` is the first raw HTTP response-body chunk, including an
error body, before Pi parses it. `response-backend` reports the backend model ID
from parsed provider chunks. `response-complete` reports the Pi model/provider,
terminal stop reason and available usage. Missing provider usage is `usage:null`
with `usage_available:false`; a reported complete input/output count enables
normalized usage, with `cost_source` distinguishing provider totals from configured
rate estimates. HTTP refusal status is retained before SDK rejection. Full `tool-result` events retain
operation/source joins. `tool-refused`, `abort` and `settled` retain refusal and
failure outcomes. An eligible429 attempt has a transport-derived
`response-complete` with `http_status:429`, error stop reason and unknown usage;
the final attempt is completed by the SDK assistant message. Backoff aborts and
excessive-delay refusals do not duplicate that first receipt. `provider-retry`
marks eligibility with the configured delay ceiling, then a second-attempt start
with the preceding request ID; monotonic intervals expose actual waiting without
inventing the SDK's planned delay. Internal blocked provider attempts create no
fabricated response-completion receipt. Model attention, provider inference start and
physical paint timestamps are unavailable and declared at `host-start`.

`abort` and `response-complete` also snapshot constant-size `response_progress`
metadata for the last charged HTTP attempt, or null before any attempt. Its
`request_id` and `scope` distinguish the current attempt from a completed attempt
retained during tool work, backoff or a request-limit refusal. Counters reset at
each actual fetch, including a429retry; later traffic cannot mutate an emitted
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
