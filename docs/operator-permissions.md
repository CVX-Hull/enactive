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
recovery and bounded waypoint tasks. Setup/server launch, GitHub publication,
arbitrary Python, shell scripts and one-off capture wrappers are not matched.
No global config, user rules, OS permissions or broad network access was changed.
Use the ordinary command directly when applicable; do not hide disallowed work
behind an allowed command or switch transports to evade review.

Rules permit matching commands **outside** the sandbox. They are not filesystem
confinement, source-hash pinning or a per-agent sandbox. The CLI and imports come
from the working directory: use only the reviewed trusted checkout, freeze source
during admitted play and re-review on entry-point or dependency changes. The rule
does not mechanically check cwd, source hashes, budgets or command intent. Managed
restrictions and more restrictive matching rules still win. Remaining reviews,
including a capture wrapper not matched by the CLI rule, must be honored.

Codex0.162.1's mature `codex execpolicy check` parsed the rule and its inline
positive/negative cases. A key command matched allow; Python `-c` and server launch
had no match. **Policy syntax/matching is verified; activation and a live command
under the new rule are not.** Official documentation requires a trusted project
configuration and startup/reload. This session was not restarted or weakened;
existing auto-review remains the available route. Do not make a user restart a
routine gameplay prerequisite or claim every review disappeared.

Maintenance: lead rechecks examples with `codex execpolicy check --rules
.codex/rules/gameplay.rules -- COMMAND` when command syntax, trust or permission
support changes. Review the diff, effective policy and an allowed/blocked harmless
preflight before relying on activation. Retire obsolete allowances with their
commands. Reuse these inline checks rather than building a policy parser.

Official sources checked2026-10-18: [rules](https://learn.chatgpt.com/docs/agent-configuration/rules),
[sandbox and approvals](https://learn.chatgpt.com/docs/agent-approvals-security),
[sub-agent permissions](https://learn.chatgpt.com/docs/agent-configuration/subagents).

## Dedicated gameplay context

A long-lived bounded player sub-agent is useful for keeping gameplay facts and
observations separate from engineering discussion. It does not require a weaker
model tier or another paid API. It inherits parent permissions; role instructions
do not create security isolation, and delegation alone cannot remove approvals.

**Current arrangement:** the player proposes candidates through the
[existing planning contract](protocol.md#bounded-injected-planner). The lead owns
admission, raw input, recovery and the shared game/service; the harness executes
accepted waypoint plans. The actual rehearsal handoff was summary-only advice,
not transferred execution. Do not use the read-only explorer/reviewer roles to
send game inputs.

**Proposed next arrangement:** a designated player could own decisions and
ordinary input for a bounded admitted segment, while the lead handles engineering,
review, deliberate inspection and escalation. Only one executor may own the
runtime at a time. Before enabling it, freeze its command/write scope, retain the
same charged ledger and deadlines, and demonstrate Pause/revoke, fresh-state
handoff, unknown handling and normal cleanup. Lead inspection first revokes and
quiesces the player; returning control needs fresh observation and explicit
authorization. Missing player or approval failure stops visibly. User rescue is
not the fallback. This is a design change to the present planning-only policy,
not an already activated role or an additional simultaneous executor.

Track this bounded operating-mode decision in #81 and, if implementation is
needed, a scoped child before execution. The lead remains accountable for design,
budget/source acceptance, adjudication and final verification. Do not expand an
active frozen campaign's authority mid-run just because a new role is convenient.
