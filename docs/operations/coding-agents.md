---
owner: maintainer
review_trigger: Supported coding-agent host, delegation, permission or MCP entry changes
status: active
---

# Coding-agent hosts

The lead's coding agent is engineering tooling. Project instructions, standards
and gameplay design are host-neutral; this page is the one place that maps them
to each supported coding agent. Codex and Claude Code are supported. Neither is a
deciding player host or a fallback for one: gameplay runs only through the
[player host contract](../contracts/player-host.md).

## Instructions

| Host | Reads | Rule |
| --- | --- | --- |
| Codex | [`AGENTS.md`](../../AGENTS.md) | Single instruction source. |
| Claude Code | [`CLAUDE.md`](../../CLAUDE.md) | Imports `@AGENTS.md`; adds no rules. |

Change instructions only in `AGENTS.md` and the documents it links.

## Delegation roles

[S-AGENT](../standards/agents.md) names roles; each host supplies the mechanism.
Role definitions (model, tools, read-only mode) live in each user's host profile,
not in this repository.

| Role | Codex | Claude Code |
| --- | --- | --- |
| Explorer, read-only | `agent_type` explorer | `subagent_type` `Explore` |
| Worker, owned paths | `agent_type` worker with `fork_turns=none`, separate worktree | `subagent_type` worker, fresh agent (not a fork), `isolation: worktree` |
| Reviewer, clean context | `agent_type` reviewer with `fork_turns=none` | `subagent_type` reviewer, fresh agent |

## Gameplay command allowances

Both hosts allow exactly the stable prefixes `.venv/bin/python -m harness status`,
`… pause` and `… run` without a prompt; every other command keeps the host's
default approval. [Operator permissions](../operator-permissions.md) explains why a
match is not filesystem confinement, source pinning, credential loading or
gameplay authority.

| Host | Tracked file | Loads when |
| --- | --- | --- |
| Codex | [`.codex/rules/gameplay.rules`](../../.codex/rules/gameplay.rules) | The user trusts the exact checkout. |
| Claude Code | [`.claude/settings.json`](../../.claude/settings.json) | The user trusts the workspace, or passes `--settings .claude/settings.json`. |

Change both files together and check both against the rule file's inline
`match`/`not_match` examples. Codex: `codex execpolicy check --rules .codex/rules/gameplay.rules -- COMMAND…`
(pass the command as separate tokens). Claude Code: a headless
`claude -p --output-format json --permission-mode default --settings .claude/settings.json`
attempt of each example from the checkout; a non-matching command must appear in
`permission_denials`. Pin the default permission mode: a user-selected automatic
mode may approve more than the project allowance, which is the user's choice, not
project policy. Never widen one host to match a mistake in the other.

## Player MCP entry

A coding agent may attach the player MCP adapter only for engineering inspection of
an explicitly issued `player-adapter/1` actor: a fixture service, or an actor the
lead deliberately issued under the current custody procedure. It is not a deciding
host, and any input sent through it is a game input under the designation rules.
Generate the entry from source; the tool list is always the current
[`tool_specs`](../../harness/player_tools.py):

```sh
.venv/bin/python -m tools.configure_player_tools --coding-agent-format mcp-servers-toml --actor-config ACTOR_JSON --output .codex/config.toml
.venv/bin/python -m tools.configure_player_tools --coding-agent-format mcp-servers-json --actor-config ACTOR_JSON --output .mcp.json
```

The outputs hold absolute machine paths and are ignored by Git. Regenerate them
after moving the checkout, changing tools or issuing a different actor; the
generator refuses to overwrite an existing file or leave the checkout.

## Per-user activation

These steps are each user's own and are not tracked or automated here:

- Codex loads project rules and `.codex/config.toml` only for a checkout trusted in
  the user's own Codex configuration; a nested clone does not inherit its parent's
  trust, and a `-c projects…trust_level` override does not enable project files.
  For one untrusted invocation, pass the generated entry as an inline override
  (`-c 'mcp_servers.enactive_player={…}'`). The project never edits user configuration.
- Claude Code reads `CLAUDE.md` without trust, but applies project
  `.claude/settings.json` permissions only after the user accepts the workspace
  trust dialog. It asks once before starting a project `.mcp.json` server. For one
  invocation, pass `--settings .claude/settings.json` and `--mcp-config .mcp.json`.

[Operations index](../runbook.md).
