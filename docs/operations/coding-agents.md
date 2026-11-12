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
one `gh pr checks <PR> --watch` and pinned auto-merge. Hosts differ only in how a
session runs the wait and what re-invokes it. Host permission prompts and refusals
still apply.

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

## P1 study readers

All agents of [p1-study/3's measurement chain](../design/p1-study-3.md#the-measurement-chain)
run on Codex. The owner first selected it for readers on 10 November 2026: "Use codex for this
which has a lot of credits. But, otherwise, do whatever that's needed. Just ensure we don't trip
any rate limits." Later that day the owner selected it for the remaining agents: "There's no
quota on claude code at the moment, and historical studies had been done on codex. Run it via
Codex instead." The full development chain is repeated with this configuration before any
held-out question is written.

- **Session.** One `codex exec --ephemeral --skip-git-repo-check -s workspace-write` per batch,
  with the installed Codex CLI, model `gpt-6.1-sol` and `model_reasoning_effort="high"`. Record
  the actual CLI version in the existing batch provenance. The owner permits CLI updates with
  the same model; dedicated version copies and global installation changes are unnecessary.
  Keep the model, effort and scientific briefs fixed. Normal output validation detects incompatible
  behavior; a CLI update alone requires neither duplicate binaries nor repeated calibration.
  Stop and repair an incompatible CLI/API boundary instead of silently changing the model. A reader batch
  contains exactly one item; other roles retain their frozen batch sizes.
- **Verified input.** The maintained `tools.coding_host.p1` executor prepares role-specific inputs
  through `tools.coding_host.p1_input`. Question and Audit sessions receive all exact batch-named
  original PNGs as initial images; Reader, Grader, Guess and Paraphrase sessions receive none.
  Local `codex debug prompt-input` must verify complete count/order/payload hashes before
  inference, including exact initial user text. Every role receives its exact authorized public batch JSON
  in that initial text as well as a copy in its leaf; a Reader batch still contains exactly one item.
  An oversized renderer argument fails closed
  rather than launching without verification. A path string or parser-valid answer is not image-delivery evidence. Keep the
  frozen brief and per-item frame order unchanged; image presentation proves neither
  attention nor interpretation. Old finite path-only launchers are historical evidence,
  not the supported path for another visual measurement run.
  Original PNGs must remain under immutable custodian/evidence-store ownership for the
  whole session. Pre-launch rendering and post-cleanup hashes detect persistent changes;
  they cannot prevent temporary replacement during CLI loading or prove which pixels a
  concurrently modified file supplied. No copied-image cache or filesystem-confinement
  guarantee is added.
  Prepare with `python -m tools.coding_host.p1 prepare KIND --batches BUILD --expected-key-sha256 SHA --out HANDOUT`;
  use `--only BATCH...` to prepare a declared subset of the original key without resampling or
  copying/rendering unused batches. Unknown, empty or duplicate selections are refused before preparation.
  Run an authorized finite pool with `python -m tools.coding_host.p1 run HANDOUT --max-attempts N --workers 3`.
  The first run fixes N, a handout lock prevents concurrent controllers, and a stopped handout
  cannot renew. Preserve candidates for separate process review before parsing/acceptance.
  Worker completion and controller interruption share one cleanup owner per child;
  repeated interruption does not reenter cleanup. Queued items skip rendering after an observed stop.
  The lead owns the global allocation and runs only one pool at a time; this executor's
  cap is per handout, not a global account quota. CLI updates require local input rechecking,
  not duplicate binaries or a silent model change.
  Compatible updates continue when the locally reverified inputs are identical; each attempt
  records the version observed before launch. A version change alone does not repeat a completed
  candidate or require new calibration. Source, model/effort, key, prompt and image checks remain.
- **Isolation.** Each initial directory contains only the public batch; its prompt is supplied as input. The frozen brief
  restricts reads to that batch and any images it names; the operator copies out the validated
  answer. Separate directories and fresh contexts isolate payloads, but do not establish an
  item-only readable filesystem. Keep that assurance limit distinct from observed tool use.
- **Rate limits.** At most three sessions at once. The maintained executor makes one attempt
  per item and stops on failure. It never automatically retries or renews a stopped handout.
  Any separately authorized infrastructure retry or output redo uses a fresh handout within
  the study's original per-item and global limits, retaining the failed attempt.
- **Output handling.** Reuse the study parser for every role. Refused output is preserved and
  gets at most the protocol's one fresh redo; existing invalid output or an interrupted
  attempt is not silently skipped or renewed. Raw attempt streams are retained before launch,
  and validated answer bytes are published atomically after owned cleanup.
- **Measured cost.** Earlier mixed-host development used about 115,000 tokens per Codex reader,
  mostly cached input, and about 60,000 per Claude Code subagent. Those measurements do not
  forecast the newly selected all-Codex chain's other roles.

[Operations index](../runbook.md).
