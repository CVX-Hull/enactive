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

## Both hosts

- **Binaries.** Both are single native binaries linking only system libraries:
  `claude` (307 MB) under `~/.local/share/claude/versions/` and `codex` (235 MB) under
  the Homebrew Caskroom. The profile allows reads of the one binary each session uses.
- **Inner sandboxes stay off.** A nested `sandbox-exec` fails, so the outer profile is
  the only enforcement.
- **Version drift.** Each session records the host version and binary hash. After any
  update, re-run the probe and the escape suite.
