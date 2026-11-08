---
owner: lead
status: active
review_trigger: A coding-agent host update, a change to the curator sandbox or proxy, or a new curator host
---

# Curator hosts under the sandbox

Host-specific facts for running a coding-agent curator inside the
[curator sandbox](../research-curator-sandbox.md) (ADR 009, #451). The design and
research pages stay host-neutral; this operator page names the hosts. Versions on this
Mac on 8 November 2026: Claude Code 2.1.319 and Codex CLI 0.162.1, on macOS 27.2.

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

**Observed under the profile (2026-11-08, $0).** The manual probe
[`tests/curator_host_probe.py`](../../tests/curator_host_probe.py) ran against a local
stand-in that answers in the Messages streaming shape. The token counts and price are
synthetic.
- **One turn.** It completed with one upstream `/v1/messages` streaming request, and
  the proxy swapped in the key. Afterwards the home held `.claude.json`,
  `.claude/backups`, `.claude/plugins/store` and `.claude/sessions`.
- **Bash tool turn.** The stand-in asked for a command that writes `scratch/`, reads
  `.runtime/credentials.json` and lists `~/../..`. The tool result was `written /
  secret-denied / users-denied`.
- **Footprint.** Each run took 0.23–0.24 s, peaked at about 157 MB and left no
  survivors.
- **What it sends.** Five beta flags, all dropped by the proxy unless frozen:
  `claude-code-20250219`, `context-management-2025-06-27`, `effort-2025-11-24`,
  `interleaved-thinking-2025-05-14` and `thinking-token-count-2026-05-13`. It also sends
  a clearing `context_management` field, which the proxy allows. #454 freezes the beta
  allowlist after checking each flag against the real API.

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

**Status.** It has not been run under the profile. The proxy's OpenAI request allowlist
is not yet checked against a dated source. #454 does both before any spend, using the
same probe with a Responses-shape stand-in.

## Pi curator host (the P0 shadow host)

The owner chose one host the project controls for #454 (ADR 009 open decision 2), measured with two
models through OpenRouter. [`tools/curator_host`](../../tools/curator_host) is a private Node package
on `@earendil-works/pi-agent-core` and `pi-ai` 1.4.0, the versions the actor's
[`tools/player_host`](../../tools/player_host/README.md) uses. It has no MCP, no shell and no
coding-agent application. [`tools/curator_shadow.py`](../../tools/curator_shadow.py) runs it over
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
- Telemetry is JSON lines on stdout: `host-start`, `request-start`, `request-end` (tokens, cached,
  reasoning and the provider's reported `cost`), `tool-call` (name, ok, duration, bytes) and
  `host-end`. It never carries the token or a header.

**The shadow runner.**
`.venv/bin/python -m tools.curator_shadow --arm terra|opus --lineage 397|372 [--sessions NAME…] --cap-usd N --out .runtime/curator-shadow/RUN`.
- **Input.** It reads the key only from `OPENROUTER_API_KEY`, and fails without it. `--upstream`
  accepts only OpenRouter or a local http origin. It selects only the sampled sessions (397:
  `sd1a1`–`sd1a7`; 372: `aidB3 ceil09 ceil07 ceil05 aidB9 aidA5`, in that order) and refuses
  `lh1`–`lh3` and any other name. A 372 run gets its own sealed memory store; the 397 lineage
  store is not passed, because it would carry later admissions into earlier sessions.
- **Run.** One `run_session` per session against `.runtime/knowledge/shadow-454/<arm>/<lineage>/`
  (game `cdda`). Each session has its own proxy and token, sized to what the whole-run cap leaves
  (or `--session-cap-usd`). The run stops when the cap is reached, the proxy revokes or records
  a breach.
- **Output.** `curator-shadow/1` summaries: one per session (`<out>/<lineage>/<session>/summary.json`
  and its `proxy-ledger.jsonl`) and one per run (`<out>/summary.json`). A session summary holds
  wall seconds, host start to first model request, first-request prompt tokens, tokens by kind,
  proxy-settled cost, requests, tool calls, submissions, verdicts with diagnostics, drafts, the
  record path, the proxy's `revoked` and breaches, and whether the cap stopped it.

**Two arms, one route each.** The route is pinned to one provider with no fallback.

| Arm | OpenRouter model | Pinned provider | Effort | Frozen price per MTok (in / out / cache read / cache write) |
| --- | --- | --- | --- | --- |
| `terra` | `openai/gpt-6.1-terra` | `openai` (as the actor) | medium | $1 / $5 / $0.05 / $1.25 |
| `opus` | `anthropic/claude-opus-5.5` | `anthropic` (not yet confirmed against the model's endpoint list) | medium | $4 / $20 / $0.20 / $8 (1-hour tier; 5-minute $5) |

Prices are in [`data/curator/openrouter-prices-2026-11-08.json`](../../data/curator/openrouter-prices-2026-11-08.json)
(`curator-prices/1`), read from OpenRouter's public model list on 8 November 2026. The context window
is 262,144 tokens for both arms, so they see the same capacity as the actor; Terra's higher
long-prompt tier (above 272,000 tokens) is therefore unreachable. Opus's reasoning is mandatory and
its listed default effort is high; `--effort` overrides.

**What differs from the actor's route.** The proxy forwards a fixed field list, so the curator's
frozen route sets `maxTokensField: max_completion_tokens` (the actor uses `max_tokens`) and the host
never adds `service_tier` (the actor's host adds `default`). Both are refused by the proxy. Nothing
else Pi sends was refused: in the tests every request of both arms passed the allowlist and the
proxy ledger shows no refusal.

**Tool roots.** Node is a Homebrew build linked against about twenty kegs through
`/opt/homebrew/opt/<name>` links. The tool roots are the node keg, each keg its libraries live in
(read from `otool -L`), `/opt/homebrew/opt` (links only), the host package directory, the directory
holding the frozen configuration, and the Python base prefix for the workbench. Two facts about
running node under the profile:
- **`OPENSSL_CONF=/dev/null`.** Node reads `/opt/homebrew/etc/openssl@4/openssl.cnf` at start and
  aborts when the profile refuses it. The host speaks plain http to the loopback proxy, so no
  configuration is needed.
- **`launch.py`.** Node aborts at start when its standard output is a file the profile does not
  let it read (it calls `fstat` on descriptors 0 to 2, and the session record's `host-output.log`
  is outside the profile). A pipe is accepted. The sandbox argv is therefore
  `python -I launch.py <node> run.mjs --config FILE`, which relays node's output into the log. A
  sandbox that allowed metadata on its own output file would remove the relay.

**Observed footprint** (2026-11-08, $0, local stand-in with three scripted requests, one frame image
and one workbench call): about 0.35 s of host time, 93–98 MB peak, 0.13–0.15 s from process start
to the first model request, no surviving process. The escape suite
(`tests/curator_adversary.py` through `tests/test_curator_sandbox.py`) passes unchanged with these
roots added to the layout.

**Image cost in the reservation.** The proxy counts each inline image as a bounded number of input
tokens (`IMAGE_TOKENS`), not its base64 bytes, at the arm's highest input price, so more images in a
request raise the reservation. The host keeps at most `--max-context-images` (default 24) in a
request, evicting the oldest in blocks of `--context-image-block` (default 12). Eviction rewrites the
prompt prefix, so the defaults keep it rare; each marker names the evicted frame's source ID so
`view_frame` can show it again.

**Cache stability (ADR 009 P1.0).** A prompt cache only helps when each request extends the last
byte for byte, so:
- **Affinity.** The proxy generates one affinity value per proxy, that is per session, and sets it
  as `x-session-id` on every OpenRouter request. It is independent of the session token, the host's
  own header is never forwarded, and the ledger holds only a short SHA-256 of it (`affinity_sha256`).
- **Tail notice.** The budget note is the last message of each request and is never stored. It now
  includes the time used against the wall-clock limit and warns past half and four fifths of it;
  only requests and dollars set the phase that refuses reading tools. Once the
  prompt passes three quarters of the context window, a context warning with the room left joins it
  on every later request, before the capacity stop.
- **Proof.** Request-serialization tests in `tools/curator_host/test/host.test.mjs` and
  `tests/test_curator_openrouter.py` check the prefix, the tail note, eviction and the header
  with no provider call.

## Both hosts

- **Binaries.** Both are single native binaries linking only system libraries:
  `claude` (307 MB) under `~/.local/share/claude/versions/` and `codex` (235 MB) under
  the Homebrew Caskroom. The profile allows reads of the one binary each session uses.
- **Inner sandboxes stay off.** A nested `sandbox-exec` fails, so the outer profile is
  the only enforcement.
- **Version drift.** Each session records the host version and binary hash. After any
  update, re-run the probe and the escape suite.
