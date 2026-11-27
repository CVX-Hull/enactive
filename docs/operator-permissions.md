---
owner: lead
status: active
review_trigger: Launcher, provider delegation, permission or actor-custody changes
---

# Gameplay permissions and player ownership

Routine admitted gameplay uses the [player host and route](operations/player-host.md)
frozen in the package. The owner's standing permission covers gameplay API spending
within the approved scope, sending player-visible observations and mission context to
the selected provider, and applicable source, evidence and tracker publication to
GitHub. That permission covers basic actions and clean actor succession within the
original limits. Input custody and permanent Pause follow the
[computer-control contract](contracts/computer-control.md#computer-operations-and-custody).

The owner also allows bounded endpoint tests with selected retained gameplay images,
the current player guide and tool declarations. Freeze destinations, context and
finite allowances before testing. Run eligibility probes without game tools and
record refusals and missing usage. Unrelated engineering or personal data requires
separate export approval.

## Finite gameplay budget delegation

The owner manages the provider account balance, auto-recharge and key credit limit.
The key's credit limit is the overall hard cap and is outside the code. Each study
needs an owner-set envelope, and each run needs its own dollar limit. The lead checks
the approval and frozen limit at admission and tracks provider-reported costs and
unpriced attempts under the [campaign spend procedure](operations/campaign-run.md#spend-limit).

**Actual-spend admission.** Within an open envelope, the lead allocates and admits
runs without per-run approval only while the study's actual provider subtotal plus
twice its largest admission so far stays within the envelope. The lead stops and
asks the owner when the envelope is reached. Unused funds expire when the approved
scope ends. The [campaign procedure](operations/campaign-run.md#start-and-close)
covers the ledger and the separate admission bound for an incomplete trace.

**Real-model checks before merge.** A change to how a model is prompted or how its reply
is parsed may spend up to \$1 of provider credit before merge without a separate
approval ([owner decision](decisions/owner-decisions.md#one-dollar-for-prompt-and-parser-checks)). The lead runs a
short campaign package on the pinned route whose dollar limit and in-flight allowance
together keep the spend within that \$1 ([spend limit](operations/campaign-run.md#spend-limit)),
and records the check in the pull request. The spend counts against the key's
credit limit and opens no study envelope. Anything larger is asked with its price.

See the [in-force owner decisions](decisions/owner-decisions.md#in-force) for
specific spending approvals and their conditions. Record other spend outside a
study in the dated record for that work.

## Engineering decision and merge delegation

The lead may design within the charter, [delegate under S-AGENT](standards/agents.md),
create branches, commit, open pull requests and merge without routine owner approval.
Merge only the commit named in review, once
[formal acceptance](workflows/development.md#development-first-delivery) holds,
including a passed required [`controller` check](workflows/ci-profiles.md#jobs-of-the-check).
When only that check is pending, the lead may queue
`gh pr merge --auto --squash --match-head-commit SHA` using the commit named in review.
Follow the [merge and wait procedure](workflows/development.md#minimum-checks-and-escalation)
and the [host's CI wait instructions](operations/coding-agents.md#waiting-on-ci).
Agent review is evidence, not human approval; say so in the pull request rather
than waiting for one.

Escalate to the owner only for exceptional situations:

- Irreversible or destructive actions beyond normal history: force-push or deletion
  on `main`, rewriting published history, or deleting retained evidence, saves or
  user data.
- Changes to repository protection, access, secrets or credentials, or new external
  accounts and services.
- Spending or data export beyond the standing permissions and applicable owner decisions.
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

Ask once per decision and continue independent authorized work. Put every
approval request through the host's structured question tool where the host has
one, not only in prose, with the recommended option first
([coding-agent hosts](operations/coding-agents.md#owner-approvals) names the tool per
host). Record the agreement and its scope as a row in the
[owner decision log](decisions/owner-decisions.md), and note it on the owning issue or
pull request. Respect host or tool
permission refusals and report the exact action and stated reason.

## Dedicated gameplay context

The deciding actor gets the [player guide](player-guide.md), frozen task context
and current tools. Its authority is limited to player-visible observations and
actor tools: no engineering source, hidden game state, raw credentials, shell,
arbitrary process tools or save editing. The [player host procedure](operations/player-host.md) owns context
and credential isolation.

### Preflight for every campaign

Before real input, follow the [campaign procedure](operations/campaign-run.md#frozen-data)
and resolve any permission refusal. [S-AGENT](standards/agents.md#delegated-campaign-operation)
governs who may operate the run and who retains authority.

### Scoped verification

Use the relevant evidence lane under the [testing guide](testing.md) and retain
failed observations and unknown causes in the [dated records](acceptance/index.md).

### Constructing player requests

Use the explicit per-actor tool profile and follow the
[custody contract](contracts/computer-control.md#computer-operations-and-custody)
for requests, unknown delivery and handoff.
