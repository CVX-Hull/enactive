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

## Environment facts for agents

These hold in every checkout and worktree, on both hosts.

- **Python** is `.venv/bin/python` of the main checkout. There is no `python` on the
  path. A worktree has no `.venv` of its own; `tools/check.py` and the commit hook find
  the main checkout's.
- **Checks.** `.venv/bin/python tools/check.py --fast` before a commit; the hook runs
  it with `--quiet` and prints one summary line, or the failing command's output. The
  hook is never bypassed.
- **Worktrees** are project-local and git-ignored. The lead creates one under
  `.runtime/worktrees/<leaf>`; Claude Code's worktree isolation creates its own under
  `.claude/worktrees/`. Either is acceptable. A worktree that runs the adapter tests
  installs its own Node packages with `npm ci`
  ([work items](../workflows/work-items.md#ready-brief-and-execution-capacity)). The
  browser suites look for Chrome under the checkout's `.cache/puppeteer`; from a
  worktree, set `PUPPETEER_CACHE_DIR` to the main checkout's for that command.
- **Identity.** Commits use the repository-local identity already configured. An agent
  does not change it.
- **Pull requests** use the repository's template, reference issues with `Refs`, and
  say that agent review is not human approval. A worker does not merge.
- **Nothing outside the project.** No global installs, no home-directory files. Scratch
  files go in the host's scratch directory, not in the checkout.
- **Only the lead, or an operator the lead designates,** launches the game, uses the
  provider key or spends ([S-AGENT](../standards/agents.md#delegated-campaign-operation)).

## Owner approvals

[Requesting owner approval](../operator-permissions.md#requesting-owner-approval)
requires the host's structured question tool where one exists.

| Host | Mechanism |
| --- | --- |
| Claude Code | `AskUserQuestion`, one question per decision, recommended option first |
| Codex | Use the available structured question tool; otherwise ask one explicit question at the end of the turn |

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
Unlike a player host's MCP child, which receives only `PATH` and `LANG`, a lead-side
server inherits the coding agent's environment; do not attach it in a shell that
holds a provider credential. Generate the entry from source; the tool list is always the current
[`tool_specs`](../../harness/player_tools.py):

```sh
.venv/bin/python -m tools.configure_player_tools --coding-agent-format mcp-servers-toml --actor-config ACTOR_JSON --output .codex/config.toml
.venv/bin/python -m tools.configure_player_tools --coding-agent-format mcp-servers-json --actor-config ACTOR_JSON --output .mcp.json
```

The outputs hold absolute machine paths and are ignored by Git. Regenerate them
after moving the checkout, changing tools or issuing a different actor; the
generator refuses to overwrite an existing file or leave the checkout.

## Waiting on CI

The host-neutral rule is in [minimum checks and escalation](../workflows/development.md#minimum-checks-and-escalation):
one watch command, `gh run watch <RUN> --exit-status`, which runs until the whole run
has ended, the required `controller` job included, and pinned auto-merge.
Hosts differ only in how a session runs the wait and what re-invokes it. Host
permission prompts and refusals still apply.

| Host | Mechanics |
| --- | --- |
| Codex | Run the watch in the turn that waits on CI. |
| Claude Code | Start the watch with `run_in_background` before ending a turn that waits on CI; its exit notifies the session once. A `/goal` stop check re-runs each time a turn ends while CI is pending, re-prompting the session. In the desktop app, Auto-fix wakes the session on CI failures, conflicts and review comments but not on a pass, so a pass relies on the watch or pinned auto-merge ([incident](../acceptance/2026-11-09-moved-results.md#coding-agent-hosts-the-383-observation)). |

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
