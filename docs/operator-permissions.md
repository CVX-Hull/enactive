---
owner: lead
status: active
review_trigger: Launcher, provider delegation, permission or actor-custody changes
---

# Gameplay permissions and player ownership

Routine admitted gameplay uses the player host frozen by the package (currently
the Pi adapter) and its explicit current MCP actor configuration. The user has authorized gameplay API spending,
player-visible screenshots/observations/mission-context export to the selected
provider, and applicable source/evidence/tracker publication to GitHub. Do not
request those permissions again for each basic action or clean actor succession.
The selected frozen package still owns finite scope, ceilings, route and actual
resources; prior approval does not create input custody or resume a stopped run.

The owner also authorized bounded endpoint tests using selected retained gameplay
images with the current player guide and tool declarations. Freeze destinations,
context and original finite allowances before testing; dispatch no game tools in
an eligibility probe and count refusals/missing usage. This is scoped gameplay
evaluation, not permission to export unrelated engineering or personal data.
Actual tool-policy rejections still require resolution; retain the refusal and
the owner's specific authorization rather than disguising a test as live play.

## Finite gameplay budget delegation

The lead may select finite gameplay allocations within the standing approved
cumulative ceiling. Preserve spent costs, conservative reservations, missing usage,
original failures and retired unused allowances. Check prospective worst-case
allocation before admission. Reservation is not an invoice. A failed actor cannot
automatically renew resources. User Pause remains permanent for that admission.
Changes outside the user's authorized scope still require the applicable decision.

**Development-loop envelope (owner decision D2, 5 November 2026).** For the
ceiling benchmark and grounding-aid study in the [development run table](development-runs.md),
new model/gameplay spend is at most $150, keeping the cumulative actual upper bound
at or below $410 within the standing $1,000. Within that envelope the lead admits
development runs without per-run owner approval and reports each run's spend in
its table row. Stop and ask the owner when the envelope is reached.

**Actual-spend admission (owner decision, 6 November 2026).** The per-run
worst-case reservation ($102.40) would have closed the envelope after about $48
of actual spend. Packages for this loop therefore freeze the standing $1,000 as
their `ceiling_usd` worst-case guard, and D2 is enforced on actual
provider-reported spend: the lead admits a run only while actual new spend plus
twice the largest single run so far stays within $150.

**Long-horizon envelope (owner decision D1 of [#382](https://github.com/CVX-Hull/enactive/issues/382), 7 November 2026).**
The long-horizon arm in the [development run table](development-runs.md#long-horizon-arm-382)
gets a new $150 envelope under the same actual-spend admission rule: the lead admits an
admission only while the arm's actual new spend plus twice its largest single admission
so far stays within $150. The arm starts from the loop's cumulative actual
$346.948934979, so the cumulative cap is about $497 within the standing $1,000.
Packages keep the standing $1,000 as their `ceiling_usd` worst-case guard. Stop and ask
the owner when the envelope is reached. The arm ended on 7 November 2026 having spent
$30.46 (cumulative actual $377.41); the unspent remainder is not carried to other work.

## Engineering decision and merge delegation

The owner is not a routine gate. The lead carries ordinary engineering work through
to merge: design within the charter, delegation, commits, branches, pull requests
and merging. Merge once the [formal acceptance checkpoint](workflows/development.md)
holds: the exact candidate's protected `controller` profile passed (full regression
for broad source changes), independent review findings are dispositioned and any
required native or gameplay evidence is recorded. When only the required check is
still running, queue auto-merge pinned to the validated head (`gh pr merge --auto
--squash --match-head-commit SHA`); main protection then merges it only if that
check passes. Agent review stays evidence, not human approval; say so in the pull
request rather than waiting for one.

**Waiting on CI (owner decision, 7 November 2026).** The lead waits for PR
validation with one `gh pr checks --watch`, and may run it in the background
([waiting on CI](operations/coding-agents.md#waiting-on-ci)), instead of re-checking
by hand. This authorizes the wait only; host tool permissions still apply.

Escalate to the owner only for exceptional situations:

- Irreversible or destructive actions beyond normal history: force-push or deletion
  on `main`, rewriting published history, or deleting retained evidence, saves or
  user data.
- Changes to repository protection, access, secrets or credentials, or new external
  accounts and services.
- Spending or data export beyond the standing authorizations on this page.
- A suspected vulnerability, or a licensing or legal question.
- A change to the charter's purpose, to this delegation or to other owner-held authority.
- A failed required check or unresolved review disagreement that could only proceed
  by being waived rather than fixed.

### Requesting owner approval

Ask only when an owner decision is required. Put the exact decision and the
rule that requires it up front. Give the viable options, their tradeoffs and a
recommendation with its reason. Use plain language. If a project term is needed,
define it in the request, even if it appeared earlier in the discussion.

Give a concrete example of what the options would do differently. State what
agreement authorizes, the maximum cost (including $0), any relevant stop condition,
and how a positive, negative or inconclusive result would affect the next decision.
Distinguish agreement on a design from permission to implement or run it when
those are separate decisions.

For example, an owner-held measurement decision could be phrased this way.

> Should we check for an injury in the first screenshot or anywhere in the
> episode? This changes the predicate, meaning the claim we check against the
> recorded screenshots. I recommend the first screenshot if the purpose is to
> see whether two models can apply the same rule to the same image. An injury
> that appears halfway through would only count under the whole-episode rule,
> where missing frames can leave the answer unknown. Agreement settles the
> wording at $0. A paid replay is a separate decision.

Ask once per decision and continue independent authorized work. Record the
agreement and its scope on the owning issue or pull request. Respect host or tool
permission refusals and report the exact action and stated reason.

## Command permissions

Engineering process/network permission, mechanical input custody and player
judgment are separate boundaries. Current CLI commands are `run --run`, `status
--url` and `pause --url`; the [campaign runbook](operations/campaign-run.md)
explains frozen admission. Old semantic/mission commands are removed. Setup,
Keychain retrieval, source/GitHub operations and arbitrary shell code retain their
own tool policies; do not hide them behind an allowed command.

Project-local coding-agent allowances provide narrow stable CLI allowances for the
same three prefixes in each supported host: [Codex rules](../.codex/rules/gameplay.rules)
and [Claude Code settings](../.claude/settings.json). They do not confine filesystem
access, pin source, load provider keys, prove active-chat policy loading or grant a
per-agent sandbox. Use the inspected trusted checkout and freeze source during play.
Managed or more restrictive policies still win. Test changed allowances with each
host's maintained checker or headless attempt and the harmless matching/nonmatching
examples, without a custom policy parser; [coding-agent hosts](operations/coding-agents.md)
gives the commands. No global trust/profile change is part of this setup.

### Verified loading and retired recorder allowance

Earlier policy-loading and recorder observations are retained in
[the pre-cutover document](https://github.com/CVX-Hull/enactive/blob/433ed973afe312d03f777d8b102a0cba528af746/docs/operator-permissions.md).
They do not prove newly edited rules are loaded. No restart is required merely to
repeat a known unchanged setup; use actual execution evidence for the selected route.

## Dedicated gameplay context

The deciding actor receives the compact player guide, frozen goal/context and
current tool schemas. It receives no engineering source/hidden game state, raw
credentials, shell, arbitrary process tools or save editing. The provider key is
read only from the selected Keychain item into the launcher/host environment,
never printed or written. Game/MCP environments exclude it and inherited native
FDs. A host owns only its bounded actor tools; all game semantics belong to it.

### Preflight for every campaign

Before real input: verify the exact clean source, current package/schema and frozen
bytes, original finite time/HTTP/input/frame/byte resources, prospective cumulative
reservation, selected provider authorization, shared target exclusion, owned
process lifecycle and independent Stop path. Preserve prior partial markers; never
reopen them. Use existing fast/focused checks and proportionate independent review
under [development-first delivery](workflows/development.md#development-first-delivery).
The lead alone schedules the shared runtime. Actual permission failure is evidence,
not a passing mock or an invitation to evade tool review. Resolve it before play.

### Historical execution gap and current scoped verification

Source, sandbox, native build, real game and provider outcomes are distinct lanes.
A prefix match or test double does not prove live permissions, normal ending,
provider competence, human takeover or second-game portability. Current evidence
is indexed in [work](work.md); retain failed observations and unknown causes.

### Constructing player requests

Use only the current [computer/player contract](contracts/computer-control.md) and
explicit per-actor MCP profile. Actor capabilities are ephemeral and are not player
identity or stored knowledge. Unknown input is collected by original ID, never
replayed. Handoff seals the actor; only actual host/MCP group quiescence permits a
successor under original limits. Unexpected cancellation after sealing stops the
run; a retired actor cannot stop its successor. Save/load/menus/identity/success are
player judgments over visible behavior, never harness eligibility primitives.
