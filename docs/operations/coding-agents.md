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

## Instructions

| | Codex | Claude Code | Antigravity |
| --- | --- | --- | --- |
| Reads | [`AGENTS.md`](../../AGENTS.md) | [`CLAUDE.md`](../../CLAUDE.md) | [`AGENTS.md`](../../AGENTS.md), loaded without being asked |
| Rule | Single instruction source. | Imports `@AGENTS.md`; adds no rules. | Single instruction source. |

Change instructions only in `AGENTS.md`, the documents it links and the shared role
instructions in `.agents/roles/`.

## The lead's duties on each coding agent

[S-AGENT](../standards/agents.md#the-leads-duties) assigns these duties to the lead.
The lead weighs the [delegate profiles](delegate-profiles.md) before choosing whom to
start. The Antigravity app's documented scope is one watched documentation leaf. Its
version and approval mode are unknown. [App evidence](../acceptance/2026-11-19-antigravity-lead-trial-810.md).

| Duty | Codex | Claude Code | Antigravity |
| --- | --- | --- | --- |
| Delegate with clean context | Start the named role with `fork_turns=none`. | Start the named role as a fresh agent. | Give the sub-agent the whole brief as its first message. For a clean review, use the route under [delegation roles](#delegation-roles). |
| Choose the delegate for the task | The sandbox denies the network access the [delegate call](#starting-a-delegate-on-any-coding-agent) needs. Run it outside the sandbox with host approval. This route is unverified from a Codex lead. | Run the delegate call from the lead's shell for any of the three hosts. | The call is unverified from an Antigravity lead. For a blocked start, see [the app's terminal sandbox](#the-antigravity-apps-terminal-sandbox). |
| Keep one writer per checkout | Create the worker's worktree under `.runtime/worktrees/<leaf>` and name it in the brief. | Use `isolation: worktree` or a worktree the lead creates. | Create a worktree for the worker and name its owned paths in the brief. |
| Verify a delegated result from files and tests | Read the diff and rerun the brief's check in the worktree. | Read the diff and rerun the brief's check in the worktree. | Read the diff, rerun the check and verify each quoted passage against its file. The lead taking over or merging checks the session's report against the files. |
| Commit before review | Commit through the hook in the worktree and give the reviewer that commit. | Commit through the hook in the worktree and give the reviewer that commit. | Commit through the hook in the worktree and give the reviewer that commit. |
| Wait on CI | Watch in the waiting turn. | Start the watch in the background. | Watch in the waiting turn. The app and CLI have different [merge permissions](#waiting-on-ci). |
| Ask the owner a structured question | Use the host's [approval mechanism](#owner-approvals). | Use `AskUserQuestion`. | The app supports [structured questions](#owner-approvals). |
| Hold the runtime | One lead holds builds, installs and the [gameplay allowances](#gameplay-command-allowances). | One lead holds builds, installs and the gameplay allowances. | Hand gameplay to a Codex or Claude Code lead through the issue. Builds and installs are unverified. |
| Hand over through the issue | Replace the issue description with `gh`. | Replace the issue description with `gh`. | Use `gh`. Handover from an Antigravity lead is unverified. |

### The Antigravity app's terminal sandbox

The app's terminal sandbox can block git writes, GitHub commands and a reviewer
that needs its configuration outside the project. Retry a blocked command outside
the sandbox under the host's approval. The project-specific rules are under
[per-user activation](#per-user-activation).

An Antigravity lead session may run unattended, by the owner's decision of
21 November 2026 in the [decision log](../decisions/owner-decisions.md#the-lead-trials-are-not-run). None has
run, so unattended approvals remain unverified.
If a leaf cannot afford a wait for approval, prefer Codex or Claude Code.

## Delegation roles

[S-AGENT](../standards/agents.md) names roles; each host supplies the mechanism.
Role definitions are tracked in this repository, as the owner decided
([decision log](../decisions/owner-decisions.md)): one shared instruction per role in
`.agents/roles/`, and a thin wrapper per host that names the model and points to it, in
`.claude/agents/`, `.codex/agents/` and `.agents/agents/`. On Claude Code a project
definition takes precedence over a user's own definition of the same name. The
Antigravity CLI lists the wrappers from the main checkout. They are missing from
the listing in a worktree and in a scratch copy. The cause is unknown. No
Antigravity lead is on record starting a tracked wrapper. The
[role defaults](model-routing.md#roles-and-their-default-models) apply to native
starts. To name a different host, model or effort, use the
[delegate call](#starting-a-delegate-on-any-coding-agent).

The explorer role has two forms. Locating (where a file, rule or name is) runs on the
smallest model. Synthesis (a question answered from evidence across files) runs on a
larger one.

| Role | Codex | Claude Code | Antigravity |
| --- | --- | --- | --- |
| Explorer, locating | `agent_type` locator | `subagent_type` `locator` | The `locator` role file. |
| Explorer, synthesis | `agent_type` explorer | `subagent_type` `Explore` | The `explorer` role file. |
| Worker, owned paths | `agent_type` worker with `fork_turns=none` in a separate worktree | `subagent_type` worker, fresh agent, `isolation: worktree` | The `worker` role file in a worktree the lead creates. |
| Reviewer, clean context | `agent_type` reviewer with `fork_turns=none` | `subagent_type` reviewer, fresh agent | The native role is `reviewer`. Antigravity keeps summaries and a `brain` directory between conversations. Whether a later conversation reads them is unknown, so an Antigravity review counts only as a second family's view. For clean-context review, start a Codex or Claude Code reviewer through the [delegate call](#starting-a-delegate-on-any-coding-agent), use a fresh native reviewer on either host, or hand the leaf to a lead there. |

### Starting a delegate on any coding agent

A lead on any of the three coding agents starts a worker, a reviewer or an explorer on
any of the three with one call. This one starts a Codex worker; it runs from the main
checkout or a worktree, with the main checkout's Python
([environment facts](#environment-facts-for-agents)):

```sh
"$(git rev-parse --git-common-dir)/../.venv/bin/python" tools/delegate.py \
  --coding-agent codex --model gpt-6.2-sol --effort xhigh --role worker \
  --brief "$SCRATCH/brief.txt" --worktree "$WORKTREE" --out "$SCRATCH/worker-run" \
  --check "$ACCEPTANCE" --timeout 2400
```

`--coding-agent` is `codex`, `claude-code` or `antigravity`; `--role` is `worker`,
`reviewer`, `explorer` or `locator`; `--check` and `--timeout` are optional.

- **The lead names the delegate; the call starts it.** The coding agent, model, effort
  and role have no default, and the call holds no preference among them
  ([choosing the delegate](../standards/agents.md#the-leads-duties)). `MODEL` and
  `EFFORT` are that coding agent's own names for them. `--list` prints every coding
  agent and role that can be named.
- **Brief and worktree.** `BRIEF_FILE` holds a brief from the
  [template](../standards/agents.md#brief-template), or is `-` for standard input.
  The call puts the role's instruction ahead of it: read and follow
  `.agents/roles/<role>.md`. `WORKTREE` is where the delegate works; a worker gets a
  worktree of its own that the lead created. `OUT` is a directory in the lead's scratch
  space, outside the checkout; the call writes the brief as sent, the reply, the run's
  output and `result.json` there.
- **What comes back.** The call prints a result and then the hand-back, and exits with
  0 when there is a hand-back and 1 when there is none. The result names the delegate,
  its version, the wall time, the commits made in the worktree during the run, the paths
  left uncommitted there and one outcome: `handed_back`; `failed_start` (the command is missing or
  could not be run); `empty_reply` (exit code 0 and no reply, which is a failed run; its detail says when
  the output could not be read as the record the reply comes in);
  `refused` (a run that failed or returned nothing, whose output carries a quota or
  sign-in message); `failed` (any other non-zero exit); `timed_out` (the delegate and
  everything it started are stopped); or `unavailable` (the role is recorded as having no start that works on
  that coding agent). After any outcome but the first the call starts nothing else: the
  lead decides what to try next.
- **Token use and the served model.** Each start turns on the coding agent's
  machine-readable output, and the result carries what that output reports: `usage`,
  with `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens` and
  `output_tokens` summed over the run, and `models_reported`, the models the coding
  agent says it served. A name the coding agent does not report is null. Codex and
  Antigravity report no served model, and Antigravity reports no cache writes. Claude
  Code's `input_tokens` leaves cached tokens out, Codex's includes them, and what
  Antigravity's includes is undetermined. Compare token counts within one coding agent, not across
  them. A coding agent prints its counts when a turn ends, so a run stopped at its time
  limit may report none. Name a Claude model by its full identifier and compare
  `models_reported` with it: the alias `haiku` is served by Claude Sonnet 5.5 on this
  host ([probes](../acceptance/2026-11-25-delegate-start-probes.md)).
- **The acceptance check is run again outside.** With `--check`, the brief asks the
  delegate to end by saying whether it saw the check pass, fail or not run. After the
  run the call runs the same command in the worktree itself, outside any sandbox the
  delegate had, and reports both: what the delegate said and what the rerun showed.
  The rerun has the same time limit as the delegate.
- **The hand-back is a report.** The lead still reads the diff and checks quoted
  passages against the tree
  ([verify a delegated result](../standards/agents.md#the-leads-duties)). The call does
  not commit, merge or push.

[Delegate definitions](../../.agents/delegates.json) supply the starts below and say
how each coding agent's reply and usage are read. The starts are for
Codex CLI 0.171.0, Claude Code 2.1.329 and Antigravity CLI 1.5.17. The Antigravity
print-mode limits below are from 1.5.13 and are unchecked on 1.5.17. The
[attempts ledger](../../data/evaluation/coding-agent-attempts.jsonl) holds outcomes
on repository tasks.

| Role | Codex | Claude Code | Antigravity |
| --- | --- | --- | --- |
| Worker | `codex exec --ignore-rules -s workspace-write` reads the brief on standard input. Its sandbox denies loopback connections and process listing, so the whole test suite fails inside it. It leaves changes uncommitted. Use the call's `--check` rerun outside the sandbox, then have the lead inspect the diff and commit. | `claude -p --permission-mode auto` reads the brief on standard input. It runs checks and can commit through the hook without a sandbox. | `agy --mode accept-edits -p BRIEF` edits files. Supply the worker's check with `--check`. |
| Reviewer | `codex exec --ignore-rules --ephemeral -s read-only` reads the brief on standard input and starts clean. The sandbox enforces read-only access. A test that writes a temporary directory fails inside it. | `claude -p --permission-mode plan --no-session-persistence` reads the brief on standard input and starts clean. File-editing tools are disabled. Plan mode directs the reviewer to run only read-only commands and refuse edits (observed by hand, no retained record). The filesystem does not enforce that rule. | `agy --mode plan -p BRIEF` opens files by path. Whether plan mode prevents edits is unverified. For clean context see [delegation roles](#delegation-roles). |
| Explorer, both forms | Use the reviewer's start. | Use the reviewer's start. | Use the reviewer's start. |

- **No gameplay allowance** ([R-DELEGATION-ERROR](../risks.md)): `--ignore-rules`
  keeps the tracked [gameplay rules](../../.codex/rules/gameplay.rules), which allow
  `harness run` without a prompt, out of a delegated Codex run, since reviewers and
  workers never send game inputs. Cost: one flag. A delegated Claude Code run reads the
  project's settings, whose only allowances are the three
  [gameplay prefixes](#gameplay-command-allowances); the role instruction and the brief
  forbid them, and nothing mechanical does.
- **Refusals.** When a run fails or returns nothing, the call looks in its output for
  quota or sign-in wording listed for each coding agent in the definitions file. It
  never reads a reply for that wording, since a hand-back may discuss quotas. The
  call reports an Antigravity quota refusal as `refused`, with the time until the quota
  resets in its detail.
  Detection on Codex and Claude Code is unproven.
  A refusal worded differently is reported as `failed` or `empty_reply`, and one that arrives
  as an ordinary reply with exit code 0 is handed back as text for the lead to read.
  Either way nothing else is started.
- **Claude Code settings.** A delegated run loads the user's settings as well as the
  project's. The user's selected output style carries into the hand-back.
- **Antigravity print mode.** The delegated modes run no shell command. A denied
  command ends the run with exit code 0 and an empty reply. The call reports
  `empty_reply` and lists any files changed. Verify the files even if the CLI status
  line reports success. Tell the delegate to run no command,
  name source files by path, and include the diff and any command output a review
  needs in the brief. Split a large diff to fit the shell's single-argument limit.
- **Credentials** ([R-KEY-LEAK](../risks.md)): the shell that starts the call holds no
  provider key, since a coding agent reads its whole environment and would hand the key
  to a third provider, or bill it in place of the subscription. The call also starts
  the delegate without the key variables listed in the definitions file. Cost: none
  beyond starting it from a clean shell; the list covers only the names written in it.
- **Outside the project** each coding agent keeps its own state (sessions, logs,
  caches) under its home configuration directory, as it does when used by hand
  ([R-HOST-CHANGE](../risks.md)). The owner-approved settings for this project are
  under [per-user activation](#per-user-activation).

## Environment facts for agents

- **Python.** Use the main checkout's `.venv/bin/python`. There is no `python` on
  the path. From a worktree, use `"$(git rev-parse --git-common-dir)/../.venv/bin/python"`.
  A leaf that changes the Python lockfile builds and uses its own `.venv`
  ([work items](../workflows/work-items.md#ready-brief-and-execution-capacity)).
- **Checks.** Run `tools/check.py --fast` with that Python before a commit. The hook
  uses the checkout's `.venv` if present and otherwise the main checkout's. It runs
  the same check with `--quiet` and prints one summary line or the failing command's
  output. The hook is never bypassed.
- **Worktrees** are project-local and git-ignored. The lead creates one under
  `.runtime/worktrees/<leaf>`; Claude Code's worktree isolation creates its own under
  `.claude/worktrees/`. Either is acceptable. A worktree that runs the Node, adapter,
  curator-host, or browser suites installs its own Node packages with `npm ci` at the
  three prefixes it exercises: repository root (`.`), `tools/player_host`, and
  `tools/curator_host` (using `--userconfig /dev/null --cache "$PWD/.cache/npm" --ignore-scripts --no-audit --no-fund`;
  [work items](../workflows/work-items.md#ready-brief-and-execution-capacity)). The
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
| Mechanism | Use the available structured question tool. If none is available, ask one explicit question at the end of the turn. | Use `AskUserQuestion`, one decision at a time, with the recommendation first. | The app supports one structured question per decision with the recommendation marked. The tool's name is unrecorded. |

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

The first command writes Codex's entry and the second Claude Code's. Antigravity
has no recorded entry format. Route inspection to a Codex or Claude Code lead.

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
| The wait | Run the watch in the turn that waits on CI. | Start the watch with `run_in_background` before ending the turn. Its exit notifies the session once. A `/goal` stop check re-prompts the session while CI is pending. In the desktop app, Auto-fix wakes on CI failures, conflicts and review comments. A pass relies on the watch or pinned auto-merge ([incident](../acceptance/2026-11-09-moved-results.md#coding-agent-hosts-the-383-observation)). | In the app, find the run by commit and watch in the waiting turn. The CLI wait is unverified. |
| The merge | Use the pinned auto-merge command in the [standing delegation](../operator-permissions.md#engineering-decision-and-merge-delegation). | Use the same pinned auto-merge command. | An Antigravity lead may merge under the [owner's merge decision](../decisions/owner-decisions.md#third-coding-agent-may-merge-when-leading). The app can queue the pinned auto-merge. The owner's user-wide CLI rule refuses `gh pr merge`. A CLI lead stops at the open pull request and another lead merges. |

A queued merge needs a head that contains the tip of `main`. If the branch falls
behind after the session ends, the incoming lead brings it up to date under the
[merge procedure](../workflows/development.md#minimum-checks-and-escalation).

## Per-user activation

Trust and activation are per user and are not tracked or automated here. The project
never edits user configuration except where the owner approved an edit, and another
edit to the owner's Antigravity settings
requires new approval.

| | Codex | Claude Code | Antigravity |
| --- | --- | --- | --- |
| Project files load when | Project rules and `.codex/config.toml` load only for a checkout trusted in the user's Codex configuration. A nested clone needs its own trust. A `-c projects…trust_level` override does not enable project files. | `CLAUDE.md` is read without trust. Project permissions apply after workspace trust, and the user is asked once before a project `.mcp.json` server starts. | `AGENTS.md` loads automatically. The trust step is unknown. For role-file discovery, see [delegation roles](#delegation-roles). |
| For one invocation | Pass the generated entry as an inline override (`-c 'mcp_servers.enactive_player={…}'`). | Pass `--settings .claude/settings.json` and `--mcp-config .mcp.json`. | No per-invocation option is recorded. See [player MCP entry](#player-mcp-entry) for actor inspection. |
| Git, GitHub and project commands | Host default approval. | Host default approval. | Open the app on the main project folder and work in a worktree beneath it. The project settings allow git and GitHub commands, deny force-push and credential commands, and prompt on `--no-verify`. Allow rules cover `tools/check.py` and `tools/delegate.py` with the main checkout's Python, from the main checkout or a worktree three levels below it. No command match has been demonstrated. Whether the git and GitHub rules apply inside the worktree is also unverified. |

The owner's Antigravity settings apply to this project alone. The file under
`~/.gemini/config/projects/` uses `allow`, `deny` and `ask` lists at
`permissionGrants.permissionGrants`, as reported by the lead that made the edit.
The git and GitHub rules have the owner's approval of 20 November 2026. The project
command rules stay under the owner's decision of 21 November 2026 in the [decision log](../decisions/owner-decisions.md).

[Operations index](../runbook.md).
