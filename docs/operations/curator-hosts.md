---
owner: lead
status: active
review_trigger: A coding-agent host update, a change to the curator sandbox or proxy, or a new curator host
---

# Curator hosts under the sandbox

Host-specific facts for running a coding-agent curator inside the
[curator sandbox](../research-curator-sandbox.md) (ADR 009, #451). The design and
research pages stay host-neutral; this operator page names the hosts. The host versions checked
are in the [dated record](../acceptance/2026-11-08-moved-measurements.md#curator-hosts-versions-footprint-and-body-limit).

## Claude Code (first host)

**Configuration.**
- **Bare mode.** `--bare` skips hooks, plugins, auto-memory, keychain reads and
  CLAUDE.md discovery, and takes its key only from `ANTHROPIC_API_KEY`. Sources: the
  local `--help` and the [headless docs](https://code.claude.com/docs/en/headless).
- **Proxy.** `ANTHROPIC_BASE_URL` points it at the proxy; the session token goes in
  `ANTHROPIC_API_KEY` ([gateway docs](https://code.claude.com/docs/en/llm-gateway-connect)).
- **Memory and network switches.** `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` and
  `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` are documented
  ([memory docs](https://code.claude.com/docs/en/memory)). Under the profile, network
  is denied anyway.
- **Temporary directory.** **`CLAUDE_CODE_TMPDIR` must point at the workspace's
  `scratch/`.** Without it the host opens a shared `/tmp/claude-<uid>`, which also holds
  other sessions' files. The profile refuses that path, and the host exits with `EPERM`.

**Probe under the profile (no spend).** The manual probe
[`tests/curator_host_probe.py`](../../tests/curator_host_probe.py) runs the host against a
local stand-in that answers in the Messages streaming shape. The token counts and price are
synthetic.
- **One turn.** It sends one upstream `/v1/messages` streaming request, and the proxy swaps
  in the key.
- **Bash tool turn.** The stand-in asks for a command that writes `scratch/`, reads
  `.runtime/credentials.json` and lists `~/../..`; only the write may succeed.
- **Footprint.** A run leaves no surviving process.

The home contents, tool result, time and memory the probe observed are in
[the sandbox research](../research-curator-sandbox.md#local-observations) (L13 and L14).

**What the host sends.** Five beta flags, all dropped by the proxy unless frozen:
`claude-code-20250219`, `context-management-2025-06-27`, `effort-2025-11-24`,
`interleaved-thinking-2025-05-14` and `thinking-token-count-2026-05-13`. It also sends
a clearing `context_management` field, which the proxy allows. A beta flag joins the
proxy's frozen allowlist only after it is checked against the real API (#454).

**Run the probe:**

```bash
.venv/bin/python -m tests.curator_host_probe ~/.local/bin/claude /tmp/host-probe.json tool
```

## Codex CLI (second host)

**Configuration.**
- **Flags.** `codex exec` has `--ephemeral`, `--ignore-user-config` and
  `--ignore-rules` (local `--help`).
- **Settings.** The
  [configuration schema](https://github.com/openai/codex/blob/main/codex-rs/core/config.schema.json)
  defines a custom `model_providers.<id>.base_url` and the `memories.*` switches.
- **Unverified.** Whether `project_doc_max_bytes=0` disables instruction files.

**Status.** It has not been run under the profile, and the proxy has no provider for its
model API. Before any spend, a provider for that API is added to
[`tools/curator_host/providers.py`](../../tools/curator_host/providers.py) with its request
allowlist checked against a dated source, and the same probe runs with a stand-in of its shape.

## Pi curator host (the shadow-session host)

The shadow host is one host the project controls (ADR 009's
[owner decision on the curator's spend cap and model](../decisions/009-curated-player.md#open-owner-decisions)), run with two models
through OpenRouter ([#454 record](../acceptance/2026-11-08-curator-shadow-454.md)). [`tools/curator_host`](../../tools/curator_host) is a private Node package
on `@earendil-works/pi-agent-core` and `pi-ai` 1.4.0, the versions the actor's
[`tools/player_host`](../../tools/player_host/README.md) uses. It has no MCP, no shell and no
coding-agent application. [`tools/curator_host/shadow.py`](../../tools/curator_host/shadow.py) runs it over
sealed traces.

**Install** (project-local, nothing global):
`npm --userconfig /dev/null --cache .cache/npm ci --ignore-scripts --no-audit --no-fund --prefix tools/curator_host`.
Node tests: `cd tools/curator_host && npm test`.

**What a session is.**
- `run.mjs --config FILE` runs in the workspace. The system prompt is
  [`prompt.md`](../../tools/curator_host/prompt.md); the first user message is `brief.md`.
- The frozen configuration is `curator-host/1`: model, effort, request and wall limits, image
  limits. It names no endpoint and holds no key.
- The host reads `CURATOR_PROXY_URL` (must be `http://127.0.0.1:<port>`) and presents
  `CURATOR_PROXY_TOKEN` as its API key. Anything else is refused at start.
- The tools are `list_dir`, `read_file`, `view_frame`, `write_file` (only `submissions/`,
  `drafts/`, `scratch/`; no `..`, absolute path or link), `run_workbench` and `finish`.
  The sandbox enforces the same limits, so the host's refusals are a courtesy to the model.
- The host stops after `finish`, the request limit, a provider error, the wall limit or
  context capacity. A session that ends without `finish` fails.
- A pre-header transport failure or HTTP 502/503/504 gets at most one retry after one
  second. HTTP 429 gets that same single retry only with a valid `Retry-After` of at
  most 60 seconds (seconds or a canonical HTTP date), unless `x-should-retry: false` suppresses
  it. A proxy budget refusal without that header stays terminal. The pinned SDK owns
  the cancellable wait; both attempts and backoff share the original request, wall
  and proxy ceilings. No resources are renewed. OpenRouter documents the
  [server retry instruction](https://openrouter.ai/docs/api_reference/errors-and-debugging#retry-after-header).
- Telemetry is JSON lines on stdout: `host-start`, `request-start`, `request-end` (tokens, cached,
  reasoning and the provider's reported `cost`), `tool-call` (name, ok, duration, bytes) and
  `host-end`. Failed requests add bounded `failure` diagnostics: a known SDK error signature
  or explicit unknown, stream phase/chunk count and an allowlisted finish reason. Raw HTTP
  error bodies and SDK/provider error messages are not emitted. The SDK consumes error events
  before its callback, so the host cannot recover their typed cause. The proxy reuses its
  JSON/SSE accounting decoder to retain only an allowlisted OpenRouter `error_type` and
  integer error code in the ledger, when available ([documented envelope](https://github.com/OpenRouterTeam/docs/blob/main/api_reference/errors-and-debugging.mdx)).
  These diagnostics do not authorize retries or identify the unknown causes of old failures.
  The first bounded `gen-` reference in streamed metadata is retained once per request as
  `provider-generation` for [read-only billing lookup](https://openrouter.ai/docs/api/api-reference/generations/get-generation),
  even if usage is lost later. The reference is private run metadata, not reported cost or
  proof of billing settlement; a failure before it arrives can still lack a lookup reference.
  Telemetry never carries the token or a header.

**The shadow runner.**
`.venv/bin/python -m tools.curator_host.shadow --arm terra|opus --lineage 397|372 [--sessions NAME…] --cap-usd N --out .runtime/curator-shadow/RUN`.
- **Input.** It reads `OPENROUTER_API_KEY` or the project credential mapped by the selected
  runtime's ignored `credentials.json`, and fails if neither resolves. `--upstream`
  accepts only OpenRouter or a local http origin. It selects only the sampled sessions (397:
  `sd1a1`–`sd1a7`; 372: `aidB3 ceil09 ceil07 ceil05 aidB9 aidA5`, in that order) and refuses
  the four held-out lineages, stored as `lh1`–`lh4`, and any other name. A 372 run gets its own sealed memory store; the 397 lineage
  store is not passed, because it would carry later admissions into earlier sessions.
- **Run.** One `run_session` per session against `.runtime/knowledge/shadow-454/<arm>/<lineage>/`
  (game `cdda`). Each session has its own proxy and token, sized to what the whole-run cap leaves
  (or `--session-cap-usd`). The run stops when the cap is reached, the proxy revokes or records
  a breach, accounting remains unsettled after shutdown, or host cleanup is unconfirmed.
  `--stop-on-abort` additionally
  stops on other non-sealed sessions.
- **Output.** `curator-shadow/1` summaries: one per session (`<out>/<lineage>/<session>/summary.json`
  and its `proxy-ledger.jsonl`) and one per run (`<out>/summary.json`). A session summary holds
  wall seconds, host start to first model request, first-request prompt tokens, tokens by kind,
  proxy-settled cost, requests, tool calls, submissions, verdicts with diagnostics, drafts, the
  record path, the proxy's `revoked` and breaches, and whether the cap stopped it.
- **Shutdown and uncertain accounting.** Preparation precedes listener startup; a `finally`
  closes the proxy after execution or interruption. Closing admission is distinct from
  an incident revocation. Shutdown waits at most five seconds for admitted requests to
  settle **and append their ledger receipts**, then writes `proxy-close.json`
  (`curator-proxy-close/1`) beside the session summary, including on an execution interrupt.
  It records `settled`, outstanding request count/reserved dollars, a spent snapshot,
  real revocation/breaches and any receipt failure. A missing receipt cannot certify settlement.
  The runner stops on incomplete accounting even after a clean host exit. The real session
  manifest is not rewritten to manufacture an abort. `cost_usd` is nonfinal when `settled`
  is false; reconcile the original ledger and explicit reserved exposure before another
  owner decision. Later settlement never renews the stopped run. Older frozen records
  have their original assurance; missing shutdown metadata is not retroactive success.
- **Malformed and oversized responses.** Invalid containers, numeric parsing or unrepresentable
  charges retain a conservative reservation and fail closed. Accounting arithmetic is
  validated before a reservation is released. Token fallback requires complete nonnegative
  integer counts; a present malformed charge cannot silently become absent or zero. BYOK
  charges require both the provider component and the routing fee. Ledger serialization
  uses a separate lock so a blocked disk write cannot hold admission open or defeat the
  accounting shutdown timeout. An interrupted upstream HTTP 200 keeps its
  actual status. The response accounting buffer is capped at 32 MiB; exceeding it aborts
  reading and keeps the reservation. A bounded shutdown does not cancel remote billing or
  prove every upstream handler finished. Hard termination or failed disk writes can still
  leave unknown exposure; preserve it rather than infer a final invoice.
- **Client disconnects.** A reset on an idle keep-alive connection ends that handler quietly.
  Active request/accounting errors remain visible. If response headers cannot reach a client
  that has gone, the proxy still drains upstream within its existing limits and settles usage;
  it does not replace available usage with a reservation merely because header delivery failed.

**Two arms, one route each.** The route is pinned to one provider with no fallback.

| Arm | OpenRouter model | Pinned provider | Effort | Recorded base price per MTok (in / out / cache read / cache write) |
| --- | --- | --- | --- | --- |
| `terra` | `openai/gpt-6.1-terra` | `openai` (as the actor) | medium | $1 / $5 / $0.05 / $1.25 |
| `opus` | `anthropic/claude-opus-5.5` | `anthropic` (not yet confirmed against the model's endpoint list) | medium | $4 / $20 / $0.20 / $8 (1-hour tier; 5-minute $5) |

Prices are in [`data/curator/openrouter-prices-2026-11-08.json`](../../data/curator/openrouter-prices-2026-11-08.json)
(`curator-prices/1`), read from OpenRouter's public model list (the file names the fetch date).
The loader validates finite, nonnegative decimal-string rates and takes each component's maximum
across the base and recorded long-prompt tiers. For Terra these reservation and missing-cost
fallback bounds are $2 / $7.50 / $0.10 / $2.50 per MTok. Reported actual fees remain authoritative;
old receipts are not repriced. Opus's bounds equal its base row. Its reasoning is mandatory and
its listed default effort is high; `--effort` overrides.

Both arms use a 262,144-token comparison preset. The host checks the previous response's prompt
usage plus the output allowance before sending the next request; it does not tokenize the newly
appended messages. A tool result can therefore push one request beyond that preset and Terra's
272,000-token pricing threshold before the following check stops the session. The bounds include
that tier; the preset is not a hard pre-request token limit. The price file's `long_prompt_note`
states the same beside the rates.

**What differs from the actor's route.** The proxy forwards a fixed field list, so the curator's
route sets `maxTokensField: max_completion_tokens` (the actor uses `max_tokens`); the curator proxy
refuses `max_tokens`. Both hosts explicitly request `service_tier: default`. The curator uses the
pinned SDK's `onPayload` hook and records `requested_service_tier` at host start; its proxy refuses
an omitted or different tier. OpenRouter can fill an omitted tier from a
[workspace default](https://openrouter.ai/docs/guides/features/service-tiers#workspace-default-service-tier),
so a request that omitted the tier does not establish its applied tier. Requests and failures
recorded without the explicit tier retain their original provenance
([recovery amendment of the curator memory study](../design/p1-study-3.md#owner-gated-robustness-recovery-amendment)),
and scientific use requires an approved runtime freeze that includes the explicit tier.
Nothing else Pi sends may be refused: the proxy allowlist and the ledger's refusal count are the check
(the [#454 record](../acceptance/2026-11-08-curator-shadow-454.md#isolation) holds the runs' result).

**Tool roots.** Node is a Homebrew build linked against about twenty kegs through
`/opt/homebrew/opt/<name>` links. The tool roots are the node keg, each keg its libraries live in
(read from `otool -L`), `/opt/homebrew/opt` (links only), the directory holding the frozen
configuration, and the Python base prefix for the workbench. From the host package the roots are
only `host.mjs`, `run.mjs`, `workspace-tools.mjs`, `prompt.md`, `package.json`, `node_modules` and
`launch.py` (`HOST_READABLE` in `tools/curator_host/shadow.py`), each as its own root. The runner,
report, providers and any `__pycache__` beside them are not readable by the curator; `launch.py`
is the only Python file the sandbox's own argv runs. Two facts about running node under the
profile:
- **`OPENSSL_CONF=/dev/null`.** Node reads `/opt/homebrew/etc/openssl@4/openssl.cnf` at start and
  aborts when the profile refuses it. The host speaks plain http to the loopback proxy, so no
  configuration is needed.
- **`launch.py`.** Node aborts at start when its standard output is a file the profile does not
  let it read (it calls `fstat` on descriptors 0 to 2, and the session record's `host-output.log`
  is outside the profile). A pipe is accepted. The sandbox argv is therefore
  `python -I launch.py <node> run.mjs --config FILE`, which relays node's output into the log. A
  sandbox that allowed metadata on its own output file would remove the relay.

The host's [observed footprint](../acceptance/2026-11-08-moved-measurements.md#curator-hosts-versions-footprint-and-body-limit)
is recorded; it leaves no surviving process. The check is the escape suite
(`tests/curator_adversary.py` through `tests/test_curator_sandbox.py`) run with these roots in
the layout; the [#454 record](../acceptance/2026-11-08-curator-shadow-454.md#isolation) holds its last result.

**Image cost in the reservation.** The proxy counts each inline image as a bounded number of input
tokens (`IMAGE_TOKENS`), not its base64 bytes, at the arm's highest input price, so more images in a
request raise the reservation. The host keeps at most `--max-context-images` (default 16) in a
request, evicting the oldest in blocks of `--context-image-block` (default 8). Each marker names the
evicted frame's source ID so `view_frame` can show it again. The peak trades three limits:
- **Eviction.** It rewrites the prompt prefix, so a wide window keeps it rare.
- **Reservation.** Each image reserves `IMAGE_TOKENS` (10,000) at the highest input price, $0.40
  per request at 16 images on terra and $1.28 on Opus, before any text or output. A small session
  cap therefore refuses requests that would really cost cents.
- **Body size.** The largest of the 1,932 frames in the sealed `397-seven-day` study (the
  [#397 lineage](../acceptance/2026-11-07-seven-day-397.md)) is 322,175 bytes, or 429,568 as
  base64, a design input. Sixteen such frames stay under the proxy's 8 MiB request limit
  (`MAX_BODY`), while 24 would exceed it and the proxy would refuse the request with a 413.

To compare cached shares with the [#454](../acceptance/2026-11-08-curator-shadow-454.md) and
[#489](../acceptance/2026-11-08-context-stability-489.md) records, pass the window they record
(24 images, evicted 12 at a time) explicitly.

**Cache stability.** A prompt cache only helps when each request extends the last
byte for byte, so:
- **Affinity.** The proxy generates one affinity value per proxy, that is per session, and sets it
  as `x-session-id` on every OpenRouter request. It is independent of the session token, the host's
  own header is never forwarded, and the ledger holds only a short SHA-256 of it (`affinity_sha256`).
- **Budget note.** Each request ends with a new budget note.
  - **Kept in place.** Earlier notes stay in the history, unchanged, where they were first sent. A
    retry resends the same body below the note step, so it adds no note. Each request therefore
    extends the previous one byte for byte,
    which the provider's cache needs; replacing the note on every request defeats it
    ([#489 record](../acceptance/2026-11-08-context-stability-489.md#follow-up-the-cause-found)).
  - **Time.** The note includes the time used against the wall-clock limit, and warns past half and
    four fifths of it.
  - **Phase.** Only requests and dollars set the phase that refuses reading tools.
  - **Context.** Once the prompt passes three quarters of the context window, every later note
    includes a context warning with the room left, before the capacity stop.
- **Proof.** All checks run with no provider call.
  - **Host tests.** The request-serialization tests in `tools/curator_host/test/host.test.mjs` check
    the prefix (notes included), the latest note and eviction.
  - **Proxy test.** `tests/test_curator_openrouter.py` checks the affinity header the proxy sets.
- **Note size.** Each note is about 40–80 tokens, so 120 requests add up to about 10k tokens,
  about 4% of the window, most of it read from the cache
  ([#489 record](../acceptance/2026-11-08-context-stability-489.md)).

## Both hosts

- **Binaries.** Both are single native binaries linking only system libraries:
  `claude` under `~/.local/share/claude/versions/` and `codex` under the Homebrew Caskroom. The profile allows reads of the one binary each session uses.
- **Inner sandboxes stay off.** A nested `sandbox-exec` fails, so the outer profile is
  the only enforcement.
- **Version drift.** Each session records the host version and binary hash. After any
  update, re-run the probe and the escape suite.

## What the sandbox bounds

These bounds apply to every host. The supervisor in
[`harness/curator/sandbox.py`](../../harness/curator/sandbox.py) checks them ten times a second
and stops the session's whole process tree when one is passed. The reason is
`lifecycle.stopped` in the session record and `sandbox.stopped` in a shadow summary.

| Bound | Default | Stop reason |
| --- | --- | --- |
| Resident memory of the session's process tree | 2 GiB | `memory limit` |
| Size of the session's own files: the workspace's `submissions/`, `drafts/` and `scratch/`, and its fresh home | 1 GiB | `disk limit` |
| Processes in the tree | 64 | `process limit` |
| Wall-clock time | 600 s for a session; the shadow runner passes `--wall-seconds` (default 1,800) | `wall-clock limit` |

The kernel also limits each process to 1,800 CPU seconds, 64 MiB per file and 256 open files.

**Disk: the session's own files and nothing else.**
- **Bounded.** The supervisor totals the allocated size of every file under the directories
  the profile lets the session write, without following links. The largest total seen is
  `provenance.peak_disk_bytes` in the session record. A tree it cannot measure, such as an
  unreadable directory or an over-long path, stops the session as `disk unmeasurable`.
- **Not bounded: the rest of the disk.** The sandbox does not read the volume's free space.
  Other programs' disk use does not stop a session, and the sandbox does not protect the
  disk from them. A disk that something else fills reaches a session only as failed writes,
  its own or the runner's.
- **Not counted.** A file the session deletes while holding it open keeps its space until
  the process ends, and the total does not see it; only the per-file and open-file limits
  bound it. The session's output log is in the session record, outside the workspace, under
  the per-file limit alone. Between two checks a session can pass the bound by what it
  writes in a tenth of a second.
