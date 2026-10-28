---
owner: lead
review_trigger: Changes to this delivery decision, ownership or review policy
status: active
---

# Review by decision and risk

Name the decision and uncertainty a review should resolve, then choose the smallest
useful set of perspectives and an inspectable artifact. A review should enable the
next safe experiment or expose a concrete blocker. Do not ask every role to review
every change, require consensus, or repeat a full review of unchanged material.

On a consequential contract, assertion or evidence-boundary change, follow the
[responsibility assurance map](../architecture.md#responsibility-assurance) through
the affected producer/consumer components. Check the actual representative
assertions and their limits; update those associations or identify an owned gap.
Native pytest registration checks metadata, not semantic fit. This is part of the
existing scoped review, not another approval stage or authority to reduce CI.

| Trigger / artifact | Useful review and timing |
| --- | --- |
| Small mapping/bug fix with unchanged boundaries | Lead inspection and relevant regressions; native qualification as applicable. Include it in coherent integration review; no automatic product/architecture swarm before development. |
| New input/ownership/persistence/schema/learning boundary | Independent architecture/risk review of the brief and alternatives before implementation commitment. Reversible isolated probes may inform that design within their declared controls. |
| New player capability or observer workflow | Product/player or observer perspective on goals, acceptance and a working flow, diagram or prototype. Validate actual usability later; an agent persona is not a real user study. |
| New memory/adaptation policy or consequential literature claim | Research/evidence perspective checks prior documents, primary support, transfer limits, conflicts and functional-versus-efficacy claims. No fresh full survey for each leaf fix. |
| Permissions, external access or isolation change | Focused security/operations review at that boundary. This is not gameplay strategy review or a critic/approval per key. |
| Integrated acceptance/publication | Independent outcome/evidence and maintainability review against original requirements, source/configuration and failure/unknown receipts. Appropriate protected CI profiles and required outcome evidence remain. |

For maintainer-facing design review, lead with the user outcome, a small boundary
diagram when useful, important alternatives/tradeoffs, open decisions and evidence
limits. Link implementation detail rather than requiring the user to audit it.
Review the actual working flow again at integration when implementation reveals
new information; the earlier design review is not a promise that the design is right.

For consequential work, two or three clean-context reviewers may work in parallel
on distinct questions, such as product outcome, player/observer experience and
architecture/research. Use the named reviewer role with an explicit lens, source
paths, decisions already made, user constraints and acceptance questions. These
are proxy perspectives, not delegated product authority. The lead owns decisions
and verifies findings against evidence; the user decides actual product tradeoffs
when needed. Avoid identical prompts or a committee of overlapping approvals.

Report concrete findings with source, impact, uncertainty and what would resolve
them. Adjudicate material findings before the affected commitment; track other
owned work without blocking unrelated exploration. Re-review changed boundaries
or new contrary evidence, not the entire project after each edit. Stop reviewing
when evidence is adequate for the next stage and material findings are resolved;
unresolved required checks remain explicit blockers, never a green badge.

Record selection, findings/dispositions and known review effort in the existing
Issue/PR. At meaningful checkpoints compare useful progress, escaped defects,
false alarms and review/coordination cost; simplify or strengthen controls from
those observations. Reuse C-REVIEW, CI and current issue workflow. No new review
tracker, mandatory per-feature swarm, recurring date reset or routine gameplay
approval follows. The lead may review the tightly coupled change itself when
delegating would add little; independent acceptance remains separate.

## Risk-based assurance

The lead selects the required assurance when scoping the issue, based on impact,
uncertainty, reversibility and dependency reach. Review the highest changed
architectural responsibility first, then the affected component/internal design,
contracts/state/callers and implementation. Unchanged ancestors need an impact
statement and link, not serial approvals. A change can touch several branches.
The same approach applies to workflow, documentation and controls themselves.

| Change or claim | Minimum relevant feedback | Review / expensive evidence trigger |
| --- | --- | --- |
| Editorial: correct text or links without behavior/requirement change | Document/metadata/link checks and diff inspection; render changed visuals | Lead checks meaning; no game/native build or full behavioral rerun solely for wording |
| Contained: behavior change within understood existing boundaries | Fast checks and focused positive/negative behavioral cases | Lead reviews implementation against design; consolidate independent review at the coherent integration checkpoint |
| Boundary: change ownership, input, persistence/schema, permission, dependency or native contract | Brief/alternatives, focused independent architecture/risk review before commitment; affected failure cases and coordinated migration | Review changed contracts against callers; matching native build/affected qualification when native support is claimed; security/product/research lens only when relevant |
| Outcome: integration, release, new support, performance or learning claim | Independently assessed outcome/evidence against original acceptance | Appropriate exact protected CI profile, full regression for broad source changes before merge, applicable native/usability/held-out lanes and unresolved finding dispositions; merge alone is insufficient |

Choose checks that could detect a plausible consequential error; state unrun lanes
and why they are inapplicable or pending. A high-consequence boundary is not made
low risk by a small diff. Passing fixtures do not replace actual required native
evidence, and an unexplained red check is not waived by a cheaper green one.
Authority/Pause/identity/delivery/migration/cleanup failures block affected inputs.
The required `controller` check and branch protection remain unchanged; the
[profile policy](ci-profiles.md#protected-ci-profiles) selects the executed portable scope.
An editorial or smoke result cannot be reported as a full regression pass.

Use a larger **coherent outcome** with small inspectable implementation steps and
cheap feedback throughout. Integrate related components and pay for broad checks
when they answer a meaningful integration question. Do not batch unrelated work
into an unreviewable release or defer boundary review until after implementation.
Split a slice when uncertainty prevents focused tests/review, coordination exceeds
its benefit or the candidate cannot be understood as one outcome. Agile/Lean
feedback and limited WIP inform this policy; sprint rituals, fixed batch sizes and
more agents are not requirements. The [research basis](../research-engineering.md#recursive-architecture-and-assurance--2026-10-24)
distinguishes external guidance from this project's judgment.

At integration use existing command/CI/PR/run receipts to compare useful progress,
defects caught/escaped, review/rework/waiting effort and cost of checks. Record
unknowns without inventing measurements. Keep, narrow, replace or retire a control
from that evidence under C-MAINTENANCE. Do not create another metrics service,
review queue or per-action gameplay approval. Fast checkpoints visibly warn on
calendar-only maintenance expiry for every control; every hosted profile remains
strict at the current date. No dates are renewed automatically. Event-triggered
review and applicable actual failures/evidence gaps still govern the affected work; resolve overdue
review at the existing integration/formal-acceptance checkpoint under S-DOCS.

## Milestone review and controls

A milestone finishes only when its outcomes and required evidence lanes pass,
limitations are explicit and the lead verifies the candidate. Publish a concise
outcome/evidence update; carry unresolved work forward explicitly. After each
milestone, review estimate error, blocked/queue time, rework, escaped defects and
review burden. Repair stale guidance, tune WIP/decomposition and improve or retire
costly controls under [C-MAINTENANCE](../controls.md#c-maintenance--drift-recovery-and-retention-review-manual).
Record concrete findings and follow-up owners, not automatic date renewal.

| Principles → standards | Existing controls and enforcement limits |
| --- | --- |
| P-REVIEW/P-CHANGE/P-KNOWLEDGE → S-WORK/S-DOCS | C-REVIEW/C-USABILITY/C-GOVERNANCE: briefs, understandable views and current docs; metadata checks cannot prove comprehension or live board accuracy |
| P-TRUTH/P-KNOWLEDGE/P-REVIEW → S-AGENT | C-REVIEW/C-MAINTENANCE: bounded delegation, lead inspection and capacity review; same-account agents cannot supply independent GitHub human approval |
| P-TRUTH/P-UNCERTAINTY → S-EVIDENCE/S-DELIVERY | C-PORTABLE/C-NATIVE/C-RELEASE: exact-candidate checks and separate evidence lanes; merge/CI success alone cannot establish Done |

GitHub fields and views aid visibility; they do not enforce semantic readiness,
WIP or acceptance. Main currently requires a PR and the observed Actions `controller` check with
strict freshness; force-push/deletion and actor bypass are disabled. Required
human approvals are zero; unavailable independent human review remains an explicit gap.
Inspect the active rules and rerun relevant probes after configuration changes. Agent
review is evidence for lead adjudication, never a fabricated human approval.

[Workflow index](../project-management.md).
