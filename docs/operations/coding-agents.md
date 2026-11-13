---
owner: maintainer
review_trigger: Supported coding-agent host, delegation, permission or MCP entry changes
status: active
---

# Coding-agent hosts

The lead's coding agent is engineering tooling. Project instructions, standards
and gameplay design are host-neutral; this page is the one place that maps them
to each supported coding agent. Codex and Claude Code are supported as the lead's
host; Antigravity is supported only as a non-interactive reviewer the lead starts
([below](#non-interactive-runs-for-a-second-model-family)), as the owner asked
([decision log](../decisions/owner-decisions.md)). None is a
deciding player host or a fallback for one: gameplay runs only through the
[player host contract](../contracts/player-host.md).

## Instructions

| Host | Reads | Rule |
| --- | --- | --- |
| Codex | [`AGENTS.md`](../../AGENTS.md) | Single instruction source. |
| Claude Code | [`CLAUDE.md`](../../CLAUDE.md) | Imports `@AGENTS.md`; adds no rules. |
| Antigravity | [`AGENTS.md`](../../AGENTS.md), loaded without being asked | Single instruction source. |

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

### Non-interactive runs for a second model family

A lead on one host may start a worker or reviewer on another, so that a review comes
from a second model family. Each run is given a brief from the
[template](../standards/agents.md#brief-template); its final message is the
hand-back, verified like any other. `WORKTREE` is the leaf's worktree, `OUT` a file
in the lead's scratch directory, and `BRIEF` the brief text.

| Role | Codex (`codex exec`), brief on standard input | Antigravity (`agy`), from the worktree |
| --- | --- | --- |
| Reviewer | `codex exec --ignore-rules --ephemeral -s read-only -C WORKTREE -o OUT -` | `agy --mode plan -p BRIEF` |
| Worker | `codex exec --ignore-rules -s workspace-write -C WORKTREE -o OUT -` | not used |

- **No gameplay allowance** ([R-DELEGATION-ERROR](../risks.md)): `--ignore-rules`
  keeps the tracked [gameplay rules](../../.codex/rules/gameplay.rules), which allow
  `harness run` without a prompt, out of a delegated run, since reviewers and workers
  never send game inputs. Cost: one flag.
- **Commits.** A Codex worker leaves its changes uncommitted and the lead inspects and
  commits them, as the lead does before every commit; the worker's hand-back is the
  diff and the commands it ran.
- **Antigravity reviewers.** Print mode refuses any shell command it was not granted,
  so the brief carries the diff and the command output the review needs; a large diff
  goes in parts, within the shell's argument limit. Antigravity keeps state between
  conversations (summaries, a `brain` directory) and whether a later run reads it is
  not known, so its review is the second family's view, and the clean-context review
  is still a fresh agent on the lead's host.
- **Credentials** ([R-KEY-LEAK](../risks.md)): the shell that starts either tool
  holds no provider key, since the tool reads its whole environment and would hand
  the key to a third provider. Cost: none beyond starting it from a clean shell.
- **Outside the project** each tool keeps its own state (sessions, logs, caches)
  under its home configuration directory, as it does when used by hand
  ([R-HOST-CHANGE](../risks.md)); the project changes no configuration of either.

## Environment facts for agents

These hold in every checkout and worktree, on every host.

- **Python** is `.venv/bin/python` of the main checkout. There is no `python` on the
  path, and a worktree has no `.venv` of its own. From a worktree, run it by its path:
  `"$(git rev-parse --git-common-dir)/../.venv/bin/python"`.
- **Checks.** Run `tools/check.py --fast` with that Python before a commit. The commit
  hook finds the main checkout's `.venv` by itself, runs the same check with `--quiet`
  and prints one summary line, or the failing command's output. The hook is never
  bypassed.
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
- **Nothing outside the project.** No global installs, and no home-directory files
  written by the task (a host's own state is the host's). Scratch
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

Both lead hosts, Codex and Claude Code, allow exactly the stable prefixes `.venv/bin/python -m harness status`,
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
