# Bounded Pi player host

This private package implements the offline conformance seam described in
[`069-controllable-player-host.md`](../../docs/changes/069-controllable-player-host.md).
It uses Pi agent-core, AI serialization and MCP 1.4.0 directly. It loads no coding
agent application, personal settings, sessions, shell/file tools or resources.
Host maintenance belongs to the engineering lead.

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
Exit zero requires terminal assistant `stop`, no fatal failure latch, successful
owned MCP closure, and a successful final-file write. `runHost(options)` is the
programmatic seam; tests inject `fetch` there. No fake-provider CLI is exposed.

The closed route has exactly `schema: "pi-player-host/1"`, `model`,
`api_key_env`, `max_requests`, and `request_timeout_seconds`. `model` contains Pi's
explicit `id`, `name`, `api: "openai-completions"`, `provider`, `baseUrl`,
`reasoning`, `input`, `cost`, `contextWindow` and `maxTokens`; optional `type`,
`thinkingLevelMap` and the supported `compat` properties are validated in
`validateConfiguration`. Both text and image input are mandatory. URL userinfo,
query strings and fragments, arbitrary headers, other APIs and unknown fields
are refused. Model metadata and costs are configuration, not verified provider
capabilities or billing evidence.

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
remaining calls and inference. There is no retry, reconnect, replay, fallback,
automatic compaction or session restoration.

The host reserves at most one second (one quarter of short runs) from its total
budget for cleanup. Stdio closure uses at most 500 ms each for stdin grace and
post-SIGTERM wait. The provider request count and timeouts are finite. Setup and
cleanup share the host budget; SIGINT/SIGTERM use the same abort/closure path.

Events carry UTC `wall_time`, host-relative `monotonic_ms`, request IDs and tool
call IDs where applicable. `request-start` reports message text parts/UTF-8 bytes,
image parts/decoded bytes and complete serialized payload bytes. Text counts
include tool-call argument strings; schema bytes are included in payload bytes.
`response-first-chunk` is the first raw HTTP response-body chunk, including an
error body, before Pi parses it. `response-backend` reports the backend model ID
from parsed provider chunks. `response-complete` reports the Pi model/provider,
terminal stop reason and available usage. Missing provider usage is `usage:null`
with `usage_available:false`; a reported complete input/output count enables
normalized usage, with `cost_source` distinguishing provider totals from configured
rate estimates. HTTP refusal status is retained before SDK rejection. Full `tool-result` events retain
operation/source joins. `tool-refused`, `abort` and `settled` retain refusal and
failure outcomes. Internal blocked provider attempts create no fabricated
response-completion receipt. Model attention, provider inference start and
physical paint timestamps are unavailable and declared at `host-start`.
