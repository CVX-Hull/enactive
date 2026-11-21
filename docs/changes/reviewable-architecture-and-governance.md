---
owner: lead
status: historical
date: 2026-10-24
scope: Adopted architecture and governance rationale; current requirements live in documentation, engineering and project-management contracts
---

# Reviewable architecture and proportionate delivery

## Outcome and scope

The maintainer should be able to understand and challenge a project decision
before needing to read its implementation. Current architecture, component
design, exact contracts and code should form a navigable hierarchy. Historical
observations must remain available without becoming current instructions.

This change covers documentation structure, standards, existing control
definitions/checks, contributor templates and GitHub workflow reconciliation.
Gameplay is paused by user instruction. No run, native build, tactical change,
protocol-version change or broad code refactor is part of this change. Existing
independent-play requirements remain open.

## Starting evidence

The October 24 inventory finds a long architecture reference containing repair
chronology, large components without focused internal views, dated acceptance
reports marked active, repeated requirements in the control registry and stale
Project status. Existing standards already require authority separation and
proportionate development checks; their application needs repair. Inventory and
review coverage, uncertainty and dispositions will be recorded in the dated audit
report. This is not a claim that every source line has been reviewed.

## Architecture and documentation decisions

Keep one project architecture map, then focused explanations of player ingress,
mission execution, evidence/memory/learning, native control, and spectator/host
operations. Each names its parent, responsibility, owned state, interfaces,
important internal collaborators, failure behavior, code and exact-contract links.
Go deeper where risk or review difficulty warrants it; do not create one document
per class, draw every C4 level or force a physical code split to match the views.

Architecture explains the current structure. Protocol/schema reference defines
exact contracts. Design briefs explain proposed changes and alternatives; accepted
design is incorporated into current architecture/contracts and its brief becomes
historical rationale. ADRs retain consequential decision context. Dated reports
retain outcomes under their original conditions. GitHub Issues own actionable
scope and acceptance; Project fields own stage, sequencing and estimates. The
Project README and work page are navigation, not additional status reports.

Retain existing protocol anchors while their exact contracts remain in the same
document; provide a selective reading map rather than moving every reference in
one change. Remove duplicated architectural prose and stale qualification claims
where their authoritative contract or historical evidence already exists. Current
unsupported behavior stays explicit in component views and the overview.

Disposition of existing design material: extract the current mission explanation
from the chronology-heavy player-owned-mission design into the mission component
view and retain the old design as history; remove its delegated contract ownership
from protocol. Keep native-control as a linked current detailed recovery design.
Keep partially adopted organic/reflection/procedure/mixed-input proposals scoped
to their remaining proposals with links to current implemented contracts. Retain
prior change briefs as rationale and dated reports as historical evidence;
unfinished work remains in Issues rather than a brief's live task list.

Before implementation, identify the affected outcome and enclosing architecture
boundary, then affected components, contracts/state/callers, tests and operating
docs. Review from the highest changed responsibility downward. An unchanged
parent needs a link and impact statement, not another full review. Cross-cutting
concerns may touch several branches of this hierarchy.

## Governance and verification decisions

Use the existing charter, standards and control registry. Explain policies as
decision/trigger rules within those authorities, not a new policy database.
Controls describe the owner, trigger, action, evidence, failure response and
limitations; they link mandatory requirements instead of copying them.

Select assurance from consequence, uncertainty, reversibility and dependency
reach. Text corrections need document checks and diff inspection; behavior
changes need focused positive/negative tests; consequential boundaries need
focused independent design review and affected integration evidence; outcome or
release claims require exact full CI and applicable native/usability evidence.
Cheap feedback continues during implementation. Batch expensive qualification
around a coherent reviewable outcome, without accumulating unrelated unreviewed
changes or postponing an applicable authority failure. No per-key approval or
automatic review swarm follows.

Keep the existing full-CI protection and overdue-maintenance policy for now.
Changing maintenance blocking semantics has no demonstrated present benefit;
reconsider before expiry if it obstructs an unrelated development repair. Do not
build a second tracker, semantic duplication detector, metrics service or custom
diagram framework. Extend the existing metadata check only for the concrete rule
that dated acceptance records are historical evidence.

## Alternatives and maintenance

Appending another checklist preserves the demonstrated drift. A full arc42
template or generated code-to-document inventory introduces a larger upkeep
surface than this project needs. Reuse C4/arc42 zooming ideas, Diataxis reader
roles, existing Mermaid rendering, Git/GitHub history, native Issue hierarchies,
JSON Schema/frontmatter, Import Linter and current CI.

The lead owns integration and current-document accuracy. Component maintainers
update their explanation and parent map when responsibility/interface changes;
manual review checks meaning, while existing checks validate structure. At the
next meaningful integration assess findability, stale/duplicate edits, escaped
defects and observed review/check cost. Simplify or retire machinery whose cost
outweighs its concrete risk reduction. Unknown effort stays unknown.

## Acceptance

- A reviewer can navigate product → system → component → contract/code, including
  input authority, memory/advice and observer responsibilities, without run history.
- Current vs proposed vs historical roles are explicit; tracked acceptance records
  have historical metadata and the existing check rejects role drift.
- The registry/generated map and contributor forms agree with the top-down,
  risk-scaled workflow; required checks and gaps are described honestly.
- All confirmed audit findings have a fix, owned follow-up/revisit or justified
  rejection. GitHub tracks actions; gameplay items retain valid stages with the
  existing blocked/pause convention and explicit user-resumption condition.
  Correct demonstrably stale stages separately; do not close outcomes or reset
  meaningful development/validation history just to reduce the displayed WIP.
- Focused document/control regressions, rendered diagrams and independent
  cross-document review pass. Exact protected CI/publication remains a separate
  evidence lane; no game acceptance is claimed.
