---
owner: lead
status: active
review_trigger: Codex permission support, CLI entry point, executor ownership or campaign admission changes
---

# Gameplay permissions and player ownership

Routine admitted play should proceed without user keys or permission decisions.
User Pause/takeover remains available. There are three separate boundaries:
Codex controls process/network permission; the harness validates current input
authority; the player judges the visible game outcome. An allow rule changes
only the first boundary. It cannot grant a lease, make stale input current,
replay an unknown request or override CDDA.

## Command permissions

On this Mac's managed workspace-write session, a real passive preflight after
normal game shutdown found both `harness serve --port8766` and `harness status`
failed with Operation not permitted without elevation. The approved controller
and status call worked. The preflight sent no game input and was stopped normally.
The one-off capture helper had requested elevation on every invocation because
its child CLI uses loopback HTTP. Project-file reads/writes do not inherently
need that elevation. Git metadata writes, launch/process checks and remote GitHub
or downloads have separate permissions; do not stamp every shell call elevated.

[Project-local rules](../.codex/rules/gameplay.rules) allow only the existing
`.venv/bin/python -m harness` command family for ordinary observation, control,
recovery and bounded waypoint tasks. A second rule, requested at the paused005 checkpoint, matches only
`.venv/bin/python .runtime/campaigns/seven-day-campaign-005/preparation/capture.py`
with actor `lead` or `player`. Setup/server launch, GitHub publication, arbitrary
Python, shell scripts and every other study recorder are not matched by that rule.
Preparing these rules changed no global defaults, user rules, OS permissions or
broad network access. The later exact-project trust correction below adds only
this checkout's trust entry to Codex's user configuration.
Use the ordinary command directly when applicable; do not hide disallowed work
behind an allowed command or switch transports to evade review.

Rules permit matching commands **outside** the sandbox. They are not filesystem
confinement, source-hash pinning or a per-agent sandbox. The CLI and imports come
from the working directory: use only the reviewed trusted checkout, freeze source
during admitted play and re-review on entry-point or dependency changes. The rule
does not mechanically check cwd, source hashes, budgets or command intent. Managed
restrictions and more restrictive matching rules still win. Remaining reviews,
including invocations outside the exact recorder prefix, must be honored.

Codex0.162.1's mature `codex execpolicy check` parsed the rule and its inline
positive/negative cases. A key command matched allow; Python `-c` and server launch
had no match. **Policy syntax/matching is verified; active-chat loading and absence
of recurring review remain separate post-reload checks.** The later trust correction
verified an enabled project layer in a fresh bundled Codex process. Official
documentation requires a trusted project configuration and startup/reload. Do not
repeatedly restart an unchanged verified setup or claim every review disappeared.

Maintenance: lead rechecks examples with `codex execpolicy check --rules
.codex/rules/gameplay.rules -- COMMAND` when command syntax, trust or permission
support changes. Review the diff, effective policy and an allowed/blocked harmless
preflight before relying on activation. Retire obsolete allowances with their
commands. Reuse these inline checks rather than building a policy parser.

Official sources checked2026-10-18: [rules](https://learn.chatgpt.com/docs/agent-configuration/rules),
[sandbox and approvals](https://learn.chatgpt.com/docs/agent-approvals-security),
[sub-agent permissions](https://learn.chatgpt.com/docs/agent-configuration/subagents).


### Loading the current recorder allowance

The [scoped change](changes/032-recorder-permission-reload.md) follows the user's
explicit request. Invoke the recorder directly with the relative path above from
this trusted checkout, one literal command per call. Do not combine it with shell
redirection, a heredoc, arbitrary Python post-processing or a command chain: the
whole shell script can become the policy target instead of the recorder prefix.
The recorder already retains its indexed receipts and frames; the calling tool
can parse its returned JSON without another shell command. No recorder code change
or input-guard relaxation is needed.

This allowance does not pin executable bytes or enforce cwd. The ignored005
recorder must retain its independently reviewed hash and all existing admission,
source/native, actor, original-clock/budget, parser and frame checks. Trust the
checkout deliberately; do not use the rule with unreviewed source. Retire this
exact-study rule when005 ends or its recorder changes; a later study path needs a
new scoped review. Do not add wildcard studies, broad Python or shell prefixes.

At the first requested checkpoint, the player and lead verified paused supported
STRING_INPUT, no activity and empty live slots. Gameplay authority is suspended;
the owned controller was stopped normally, while the native game stays paused.
The user-authorized permission/docs change ends the old source freeze without
reopening any input allowance. The original clocks and every cost/unknown remain.
Restart Codex and reopen this project after publication/verification. Project
rules load only from a trusted project configuration at startup; the inspected
user config then had no explicit trust entry for this path, so activation could
not be assumed. Rule preparation changed no user/global configuration. The later
trust correction added only the exact project entry, as documented below.

The first restart did not establish activation; a later diagnostic proved the
project layer was disabled for missing exact-project trust. That entry is now
corrected, with fresh-process loading verified. After active-chat reload, verify
live calls from the actual player before relying on no-review behavior.
The suspended recorder refuses gameplay;
resume needs explicit user authorization, current clean reviewed source/helper/
native, fresh paused observations and a prospective remaining-budget decision.
Do not silently rebind its old source hash or reset clocks. Managed restrictions
or stricter matching rules may still require review; honor them.

## Dedicated gameplay context

### Preflight for every campaign

The lead owns permission readiness before ordinary input. A recorder that requires
admitted metadata must receive only a bounded passive preflight assignment first;
that setup assignment authorizes no keys, actions or Resume. Repeat this check when
the checkout, command entry point, recorder, player, Codex version or permission
configuration changes; reuse the verified setup otherwise.

1. Prefer the stable reviewed harness CLI entry points. If a campaign recorder
   wraps them, verify the exact outer recorder prefix too. A child CLI allowance
   does not automatically allow its wrapper. Review the executable and scope once
   during setup; do not request approval separately for each ordinary game action.
2. Verify that this exact checkout's project layer is enabled. Codex's documented
   `config/read` with `cwd` and `includeLayers` can show an enabled project layer;
   an absent exact trust entry or an ancestor's trust is not activation evidence.
   Codex stores project trust in user-level `config.toml`, under
   `projects.<absolute-checkout-path>.trust_level`. An authorized change adds only
   that project entry and preserves unrelated settings. Keep gameplay allowances
   in this checkout's `.codex/rules/`, not a broad user-level Python/shell rule.
3. Check positive and negative command examples with the installed Codex policy
   checker. Then reload Codex when required and test two consecutive harmless live
   status/observation calls from the actual designated player through its exact
   entry point. Record whether either call required review; a successful approved
   call alone proves access, not absence of per-action review.
   Retain loading, matching, access and absence of recurring review as separate
   evidence. A fresh diagnostic process does not prove the active chat reloaded.
4. If every action still reaches approval review, stop permission admission and
   diagnose trust/loading, outer shell syntax and managed restrictions. Do not
   spend the campaign repeating reviews or disable the sandbox globally. Honor
   any actual denial. If supported project rules cannot remove recurring review,
   report that product/policy limit explicitly instead of claiming readiness.

Existing admitted campaigns retain their original budgets and stop rules during
a user-requested configuration interruption. This prospective setup standard
does not retroactively invalidate their recorded gameplay or renew allowances.
Native guards, user Pause, recovery eligibility and campaign limits still apply.
Setup, source changes, publication and unrelated commands have separate scope.

The [trust correction](changes/033-gameplay-permission-preflight.md) records the
observed disabled project layer and the exact-project fix. Its current result is
enabled loading in a fresh bundled Codex process; live no-review gameplay remains
unverified until the active chat reloads and the actual player passes the check.

A long-lived bounded player sub-agent is useful for keeping gameplay facts and
observations separate from engineering discussion. It does not require a weaker
model tier or another paid API. It inherits parent permissions; role instructions
do not create security isolation, and delegation alone cannot remove approvals.

The waypoint planner proposes candidates through the
[existing planning contract](protocol.md#bounded-injected-planner); it still has
no raw-input role. A separately designated campaign operator may use ordinary
inputs under the [bounded actor contract](protocol.md#designated-campaign-operator).
The lead retains admission, source/game/service ownership, escalation and final
verification. These responsibilities are mutually scheduled, not simultaneous
executors or alternate protocol versions.

The operator's clean-context brief identifies command/file scope, phase and
cumulative limits. Pause, completed tool calls, an explicitly quiescent agent,
empty live request/lease checks and fresh paused observation precede lead
inspection. Returning control needs a new bounded assignment and fresh Resume;
historical unknowns and accounting do not reset. Actor names and instructions
are workflow controls, not exclusive external capabilities or a sandbox. Do not
use explorer/reviewer roles to send input. See the [runbook](runbook.md#designated-campaign-operator).

[#97](https://github.com/CVX-Hull/enactive/issues/97)'s
[two-phase result](acceptance/2026-10-18-campaign-operator.md) records actual
delegated consumption/conservation and paused lead takeover, following a retained
default-sandbox invocation failure. Its approved actor preflight and explicit
tool mode worked in this session; allow-rule activation remains unverified.
This is one qualified operating result, not general survival or a reliability claim.
Missing/unquiesced player, denied approval or failed readable access stops; user
rescue is not the fallback. Do not expand an active frozen campaign mid-run.

Test access from the **designated actor**, before gameplay admission. A successful
lead call does not prove that the player's next tool invocation will request the
same permission mode. When this session requires elevation, the brief must name
`sandbox_permissions: "require_escalated"` and a narrow justification explicitly;
omitting the field uses the default sandbox. Honor an approval rejection; do not
route it through another actor. A sandbox connection failure before any elevated
request is a different event and must not be reported as automatic-review denial.
Retain the actual passive preflight and terminal tool result. Project allow-rule
matching still does not prove live activation.

The [first deciding campaign](acceptance/2026-10-18-seven-day-stop.md) later passed
actor access and sent ordinary inputs, then received an actual approval rejection
for movement without fresh verified observation after a stopped walk. The player
honored it; the admission ended and normal cleanup preserved the partial. This
was a decision/freshness requirement, not missing loopback access. #108 tracks
the bounded observation/caller correction; do not broaden rules, change actors
or switch transports to bypass that rejection. A later assessment needs an explicit
prospective decision; the stopped admission supplies no remaining input authority.
The [subsequent bounded correction/probe](acceptance/2026-10-18-walk-reassessment.md)
used existing explicitly approved CLI calls without broader rules or another actor.
It verified stop evidence and the fresh Observe/Resume sequence; the first load
probe remained unexercised. Narrow rule activation is still unverified, and the
original approval denial was not retried. Further survival needs its own admission.

The [later functional continuation](acceptance/2026-10-18-seven-day-continuation-stop.md)
passed actual actor access and stopped on unsupported LIST_ITEMS. Broader permissions
could not fix native UI coverage. Native CUA access also failed; no user unlock/keys
were requested. A separately recorded cleanup-only upstream Quit exception closed
the process without a new Save; normal Save/Quit acceptance failed. Its scope has
expired and grants no general fallback or authority for further survival.
