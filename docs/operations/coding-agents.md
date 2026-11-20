---
owner: maintainer
review_trigger: Supported coding-agent host, delegation, permission or MCP entry changes
status: active
---

# Coding-agent hosts

The lead's coding agent is engineering tooling. Project instructions, standards
and gameplay design are host-neutral; this page is the one place that maps them
to each supported coding agent. Codex, Claude Code and Antigravity may each lead
engineering work, as the owner decided
([decision log](../decisions/owner-decisions.md)), and a lead on one may hand the role
to a lead on another. Codex and Claude Code hold the
[gameplay command allowances](#gameplay-command-allowances); an Antigravity lead leads
engineering work only. None is a
deciding player host or a fallback for one: gameplay runs only through the
[player host contract](../contracts/player-host.md).

Every table on this page has a column for each coding agent. A cell says how that
coding agent does the thing, or names a gap, its date and how the lead routes around
it.

## Instructions

| | Codex | Claude Code | Antigravity |
| --- | --- | --- | --- |
| Reads | [`AGENTS.md`](../../AGENTS.md) | [`CLAUDE.md`](../../CLAUDE.md) | [`AGENTS.md`](../../AGENTS.md), loaded without being asked |
| Rule | Single instruction source. | Imports `@AGENTS.md`; adds no rules. | Single instruction source. |

Change instructions only in `AGENTS.md`, the documents it links and the shared role
instructions in `.agents/roles/`.

## The lead's duties on each coding agent

[S-AGENT](../standards/agents.md#the-leads-duties) states the lead's duties once. This
table maps each to the three coding agents. The lead role depends on no one coding
agent or model family: where a cell names a gap, the lead routes around it, which may
mean borrowing another coding agent's command, or hands the leaf to a lead on another
coding agent through the issue.

Codex and Claude Code have both led work here and needed no trial
([decision log](../decisions/owner-decisions.md)); their cells give the mechanism.
The Antigravity column is written from one watched session
([trial record](../acceptance/2026-11-19-antigravity-lead-trial-810.md)): the
Antigravity app on `gemini-4-neon-high`, from 04:07:55Z to 04:54:43Z on 20 November
2026 (the evening of 19 November local time), leading one small documentation leaf
with the owner present. The record gives neither the app's version nor its approval
mode. A "step" is that record's transcript step. The session shows nothing about a
session started from the command line, source code, the native lane or the game.

| Duty | Codex | Claude Code | Antigravity |
| --- | --- | --- | --- |
| Delegate with clean context | The role files in `.codex/agents/`; a worker or reviewer starts with `fork_turns=none` ([delegation roles](#delegation-roles)). | The role files in `.claude/agents/`; a worker or reviewer starts as a fresh agent, not a fork ([delegation roles](#delegation-roles)). | Observed in the trial: an explorer (step 17) and a worker (step 23) each ran as its own conversation whose first message was the brief. Gap, 19 November 2026: the session did not use the role files in `.agents/agents/`, which were not yet merged, so a lead session starting them is not shown. Whichever sub-agent type it starts, the lead names the role and gives it the whole brief ([delegation roles](#delegation-roles)). |
| Keep one writer per checkout | The lead creates the worker's worktree under `.runtime/worktrees/<leaf>` and names it in the brief. | The worker runs with `isolation: worktree`, or in a worktree the lead creates under `.runtime/worktrees/<leaf>`. | Observed in the trial: the worker edited only its two owned files under `.runtime/worktrees/pull-request-model-record`, and the main checkout's working tree was not edited. `git worktree add` was blocked in [the app's terminal sandbox](#the-antigravity-apps-terminal-sandbox) and retried outside it. |
| Verify a delegated result from files and tests | No host mechanism: the lead reads the diff and reruns the brief's acceptance check in the worktree. A sub-agent's final message is a report, not the result. | No host mechanism: the lead reads the diff and reruns the brief's acceptance check in the worktree. A sub-agent's final message is a report, not the result. | Observed in the trial for the worker's result: the lead read the diff and ran `tools/check.py --fast` and the document tests, and repeated both after the repair (steps 28 to 31 and 49 to 53). Gap, 19 November 2026: after the review it reopened two of the files the reviewer quoted, not all of them, while writing that it had checked every quoted passage (step 45), and two claims in its final message went beyond its transcript. The lead that takes the leaf over, or merges it, checks the session's report against the files. |
| Commit before review | The lead commits in the leaf's worktree through the hook, then starts the reviewer on that commit. A Codex worker leaves its changes uncommitted, so the lead inspects and commits them first. | The lead commits in the leaf's worktree through the hook, then starts the reviewer on that commit. | Gap, 19 November 2026: the trial's reviewer examined an uncommitted diff over `44a5ef14` and never named `21677a5d`, the commit the session then queued to merge (step 97). The lead commits first and gives the reviewer the commit. `git add` and `git commit` were blocked in [the app's terminal sandbox](#the-antigravity-apps-terminal-sandbox) and retried outside it. |
| Wait on CI | The watch runs in the turn that waits; the merge is the pinned auto-merge command ([waiting on CI](#waiting-on-ci)). | The watch starts in the background before the turn ends; the merge is the pinned auto-merge command ([waiting on CI](#waiting-on-ci)). | Observed in the trial in the app, with a gap for a session started from the command line; both are under [waiting on CI](#waiting-on-ci). |
| Ask the owner a structured question | The available structured question tool ([owner approvals](#owner-approvals)). | `AskUserQuestion` ([owner approvals](#owner-approvals)). | Observed in the trial ([owner approvals](#owner-approvals)). |
| Hold the runtime | No host mechanism: one lead session at a time integrates into the main checkout and starts the game, builds and installs. `harness status`, `pause` and `run` run without a prompt ([gameplay command allowances](#gameplay-command-allowances)). | No host mechanism: one lead session at a time integrates into the main checkout and starts the game, builds and installs. `harness status`, `pause` and `run` run without a prompt ([gameplay command allowances](#gameplay-command-allowances)). | Gap, 19 November 2026: the trial was one documentation leaf with no source code, no native lane and no game, so holding a build or a live game is not shown. An Antigravity lead holds no gameplay allowance and leads engineering work only; a leaf that needs gameplay goes to a lead on Codex or Claude Code through the issue. Builds and installs fall under the same one-lead rule and are untried on this coding agent. |
| Hand over through the issue | No host mechanism: the lead replaces the issue's description with `gh`, and the incoming lead starts from the issue, the branch, the pull request and the worktree. | No host mechanism: the lead replaces the issue's description with `gh`, and the incoming lead starts from the issue, the branch, the pull request and the worktree. | Gap, 19 November 2026: the trial's steps did not include a handover, so an Antigravity lead writing one is not shown. The receiving side is shown: the session ended with the merge queued on a branch behind `main`, and the watching lead on another coding agent took the leaf back, merged `main` into the branch and completed the merge. The lead replaces the issue's description with `gh`, whose calls were blocked in [the app's terminal sandbox](#the-antigravity-apps-terminal-sandbox) and retried outside it. |

### The Antigravity app's terminal sandbox

In the trial the app's terminal sandbox blocked every git write (`worktree add`, `add`,
`commit` and `push`: four blocks), every `gh` call to GitHub (six) and the
second-family reviewer once: the reviewer could not read its own configuration file
outside the project, and its output went to `/tmp`. Each was retried outside the
sandbox: eleven retries in 47 minutes. The owner reports approving several by hand, and
which retries those were is not recorded. Creating the pull request took 26 minutes.
No refusal is recorded.

Allow rules for these commands were added afterwards
([per-user activation](#per-user-activation)). Whether the sandbox now lets them run
without the owner present has not been tried, and the trial does not show unattended
leading. Until it is tried, an Antigravity lead session runs with the owner present,
and a leaf that must go on unattended goes to a lead on Codex or Claude Code.

## Delegation roles

[S-AGENT](../standards/agents.md) names roles; each host supplies the mechanism.
Role definitions are tracked in this repository, as the owner decided
([decision log](../decisions/owner-decisions.md)): one shared instruction per role in
`.agents/roles/`, and a thin wrapper per host that names the model and points to it, in
`.claude/agents/`, `.codex/agents/` and `.agents/agents/`. On Claude Code a project
definition takes precedence over a user's own definition of the same name. The
Antigravity CLI listed its wrappers from the main checkout, and not from a worktree
of it or from a scratch copy
([Choosing a model](model-routing.md#roles-and-their-default-models)).
[Choosing a model](model-routing.md) owns each role's default model and when the lead
overrides it.

The explorer role has two forms. Locating (where a file, rule or name is) runs on the
smallest model. Synthesis (a question answered from evidence across files) runs on a
larger one.

| Role | Codex | Claude Code | Antigravity |
| --- | --- | --- | --- |
| Explorer, locating | `agent_type` locator | `subagent_type` `locator` | The `locator` role file. Not used in the trial. |
| Explorer, synthesis | `agent_type` explorer | `subagent_type` `Explore` | The `explorer` role file. The trial session started its explorer as the host's `research` type instead (step 17). |
| Worker, owned paths | `agent_type` worker with `fork_turns=none`, separate worktree | `subagent_type` worker, fresh agent (not a fork), `isolation: worktree` | The `worker` role file, in a separate worktree the lead creates. The trial session defined a `worker` type itself, with write tools and no sub-agent tools (step 23). |
| Reviewer, clean context | `agent_type` reviewer with `fork_turns=none` | `subagent_type` reviewer, fresh agent | The `reviewer` role file. Not used in the trial. Gap, 19 November 2026: Antigravity keeps state between conversations and whether a later one reads it is not known, so a clean context is not established. The lead takes its clean-context review from the Codex reviewer command [below](#non-interactive-runs-for-a-second-model-family), as the trial session did (step 37), or hands the leaf to a lead on another coding agent. |

No Antigravity lead session is recorded using its role files: the trial session ran on
19 November 2026, before they were merged. Its two sub-agents each ran as their own
conversation whose first message was the brief, and both inherited the lead's model.

### Non-interactive runs for a second model family

A lead on one host may start a worker or reviewer on another, so that a review comes
from a second model family. Each run is given a brief from the
[template](../standards/agents.md#brief-template); its final message is the
hand-back, verified like any other. `WORKTREE` is the leaf's worktree, `OUT` a file
in the lead's scratch directory, and `BRIEF` the brief text.

| Role | Codex (`codex exec`), brief on standard input | Claude Code | Antigravity (`agy`), from the worktree |
| --- | --- | --- | --- |
| Reviewer | `codex exec --ignore-rules --ephemeral -s read-only -C WORKTREE -o OUT -` | Gap, 20 November 2026: no command that starts a Claude Code reviewer from another coding agent is recorded here. A lead on another coding agent uses the Codex or Antigravity command in this row. | `agy --mode plan -p BRIEF` |
| Worker | `codex exec --ignore-rules -s workspace-write -C WORKTREE -o OUT -` | Gap, 20 November 2026: no command that starts a Claude Code worker from another coding agent is recorded here. A lead on another coding agent uses its own worker role or the Codex command in this row. | Gap, 20 November 2026: not used. Print mode refuses any shell command it was not granted. The lead uses its own worker role or the Codex command in this row. |

- **No gameplay allowance** ([R-DELEGATION-ERROR](../risks.md)): `--ignore-rules`
  keeps the tracked [gameplay rules](../../.codex/rules/gameplay.rules), which allow
  `harness run` without a prompt, out of a delegated run, since reviewers and workers
  never send game inputs. Cost: one flag.
- **Commits.** A Codex worker leaves its changes uncommitted and the lead inspects and
  commits them, as the lead does before every commit; the worker's hand-back is the
  diff and the commands it ran.
- **Antigravity reviewers.** Print mode refuses any shell command it was not granted,
  so the brief carries the diff and the command output the review needs; a large diff
  goes in parts, within the shell's argument limit. On 20 November 2026 a print-mode
  review (CLI 1.5.13, `--mode plan`) whose brief pointed at diff files instead of
  carrying them ended with exit code 0 and no output, after a shell command was denied:
  an empty result is a failed run, whatever the exit code. Antigravity keeps state between
  conversations (summaries, a `brain` directory) and whether a later run reads it is
  not known, so its review is a second family's view and not the clean-context review.
  That one comes from a reviewer that starts clean: the Codex command above, or a
  fresh reviewer agent where the lead is on Claude Code or Codex. Which changes get a
  review, and when the one review of a document change may come from a second family,
  is in [review](../workflows/review.md).
- **Credentials** ([R-KEY-LEAK](../risks.md)): the shell that starts either tool
  holds no provider key, since the tool reads its whole environment and would hand
  the key to a third provider. Cost: none beyond starting it from a clean shell.
- **Outside the project** each tool keeps its own state (sessions, logs, caches)
  under its home configuration directory, as it does when used by hand
  ([R-HOST-CHANGE](../risks.md)); the project changes no configuration of either,
  apart from the one owner-approved edit under
  [per-user activation](#per-user-activation).

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

| | Codex | Claude Code | Antigravity |
| --- | --- | --- | --- |
| Mechanism | Use the available structured question tool; otherwise ask one explicit question at the end of the turn | `AskUserQuestion`, one question per decision, recommended option first | One structured question per decision with the recommended option marked. Observed in the trial (step 93): one question with three options and a recommendation, and the owner chose the recommended one. The record does not name the tool. |

## Gameplay command allowances

Codex and Claude Code allow exactly the stable prefixes `.venv/bin/python -m harness status`,
`… pause` and `… run` without a prompt; every other command keeps the host's
default approval. Antigravity has no gameplay allowance and none is added: it leads
engineering work only ([decision log](../decisions/owner-decisions.md)).
[Operator permissions](../operator-permissions.md) explains why a
match is not filesystem confinement, source pinning, credential loading or
gameplay authority.

| | Codex | Claude Code | Antigravity |
| --- | --- | --- | --- |
| Tracked file | [`.codex/rules/gameplay.rules`](../../.codex/rules/gameplay.rules) | [`.claude/settings.json`](../../.claude/settings.json) | None: no allowance is tracked for it. |
| Loads when | The user trusts the exact checkout. | The user trusts the workspace, or passes `--settings .claude/settings.json`. | Nothing to load. A leaf that needs gameplay goes to a lead on Codex or Claude Code, handed over through the issue. |

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
an explicitly issued `player-adapter/2` actor: a fixture service, or an actor the
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

The first command writes Codex's entry and the second Claude Code's. No entry format
is recorded for Antigravity as of 20 November 2026, so an Antigravity lead leaves this
inspection to a lead on Codex or Claude Code.

The outputs hold absolute machine paths and are ignored by Git. Regenerate them
after moving the checkout, changing tools or issuing a different actor; the
generator refuses to overwrite an existing file or leave the checkout.

## Waiting on CI

The host-neutral rule is in [minimum checks and escalation](../workflows/development.md#minimum-checks-and-escalation):
one watch command, `gh run watch <RUN> --exit-status`, which runs until the whole run
has ended, the required `controller` job included, and pinned auto-merge.
Hosts differ in how a session runs the wait, what re-invokes it and whether the host
lets the merge command run. Host permission prompts and refusals still apply.

| | Codex | Claude Code | Antigravity |
| --- | --- | --- | --- |
| The wait | Run the watch in the turn that waits on CI. | Start the watch with `run_in_background` before ending a turn that waits on CI; its exit notifies the session once. A `/goal` stop check re-runs each time a turn ends while CI is pending, re-prompting the session. In the desktop app, Auto-fix wakes the session on CI failures, conflicts and review comments but not on a pass, so a pass relies on the watch or pinned auto-merge ([incident](../acceptance/2026-11-09-moved-results.md#coding-agent-hosts-the-383-observation)). | Run the watch in the turn that waits on CI. Observed in the trial: the run was found by commit (step 85), and `gh run watch 44676906546 --exit-status` ended with `controller` green after about two minutes (step 89). `gh` calls were blocked in [the app's terminal sandbox](#the-antigravity-apps-terminal-sandbox) and retried outside it. |
| The merge | The pinned auto-merge command of the [standing delegation](../operator-permissions.md#engineering-decision-and-merge-delegation). | The pinned auto-merge command of the [standing delegation](../operator-permissions.md#engineering-decision-and-merge-delegation). | An Antigravity lead may merge ([decision log](../decisions/owner-decisions.md)). In the app, `gh pr merge 818 --auto --squash --match-head-commit` was allowed and queued the merge in the trial (step 97). Gap, 19 November 2026: a user-wide rule of the owner's, outside this project, refuses `gh pr merge` to the command-line tool, so a session started from the command line stops at the open pull request and another lead merges. |

A queued merge does not complete on a branch that has fallen behind `main`: the
ruleset requires a head that contains main's tip
([merge procedure](../workflows/development.md#minimum-checks-and-escalation)). A lead that queues the merge and
ends leaves that to the next lead, on any coding agent, as the trial session did.

## Per-user activation

These settings are each user's own and are not tracked or automated here. The project
never edits user configuration, with one exception the owner approved, in the
Antigravity column ([decision log](../decisions/owner-decisions.md)).

| | Codex | Claude Code | Antigravity |
| --- | --- | --- | --- |
| Project files load when | Project rules and `.codex/config.toml` load only for a checkout trusted in the user's own Codex configuration. A nested clone does not inherit its parent's trust, and a `-c projects…trust_level` override does not enable project files. | `CLAUDE.md` is read without trust. Project `.claude/settings.json` permissions apply only after the user accepts the workspace trust dialog, and it asks once before starting a project `.mcp.json` server. | `AGENTS.md` loads without being asked. The command-line tool listed the role files from the main checkout only ([delegation roles](#delegation-roles)). The trial record names no trust step. |
| For one invocation | Pass the generated entry as an inline override (`-c 'mcp_servers.enactive_player={…}'`). | Pass `--settings .claude/settings.json` and `--mcp-config .mcp.json`. | Gap, 20 November 2026: no per-invocation option and no [player MCP entry](#player-mcp-entry) format is recorded for it. Inspection of an issued actor goes to a lead on Codex or Claude Code. |
| Git and GitHub commands | The host's default approval; the project tracks no rule for them. | The host's default approval; the project tracks no rule for them. | The owner's settings file for this project alone, under `~/.gemini/config/projects/`, holds `allow`, `deny` and `ask` lists under the key `permissionGrants.permissionGrants`. On 20 November 2026 the lead, with the owner's approval, added allow rules there for git and GitHub commands: force-push and credential commands are refused, and `--no-verify` asks. The path, key and lists are as the lead that made the edit reported them; the file is outside the repository and no tracked record holds them. It is a single edit and grants nothing further ([decision log](../decisions/owner-decisions.md)). Whether [the app's terminal sandbox](#the-antigravity-apps-terminal-sandbox) now lets those commands run without the owner present has not been tried. No user-wide rule changed. |

[Operations index](../runbook.md).
