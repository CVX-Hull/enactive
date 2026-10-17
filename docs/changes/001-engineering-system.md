---
date: '2026-10-17'
owner: lead
scope: Change brief 001 — A maintainable, reviewable engineering system
status: historical
---

# Change brief 001 — A maintainable, reviewable engineering system

Owner: lead. Status: implemented and verified locally. Authorized by the user's request to implement
the discussed system on 2026-10-17. Progress and acceptance: [work](../work.md).

## Problem and visible outcome

Useful MVP rules mix enduring principles, implementation decisions, historical
observations and active work. The user needs to understand direction, capabilities,
tradeoffs and confidence without reading code or reconstructing conversations.
Provide a compact overview, clear current contracts, selective decision records,
and standards linked to actual controls and explicit coverage gaps.

## Scope and design

Implement charter/principles, standards across engineering activities, progressive
documentation, operating/retention practices, historical acceptance provenance,
a control registry with generated readable map, dependency/protocol/governance
checks and negative cases. Preserve existing game behavior. The lead writes
and integrates docs; one bounded worker implements controls; fresh-context review
checks consistency, accuracy and maintainability. No new global dependencies.

## Alternatives and tradeoffs

Keeping all rules in one document minimizes files but combines different readers
and lifecycles. A large enterprise framework adds maintenance without demonstrated
need. Selective files with one source of truth expose the important distinctions.
A small registry adds upkeep but makes coverage and gaps inspectable; generate its
readable map and validate references to avoid manual duplication. Use established development tools in the local Python environment: JSON Schema
validation, Import Linter, Ruff and Markdown parsing. Keep custom code scoped to
project mappings, containment, generated summaries and native protocol forms.
The [tooling decision](../decisions/003-development-controls.md) records selection
and maintenance tradeoffs. Static checks cover specific
source properties; real native behavior remains a separate acceptance lane.

## Maintenance, reversibility and uncertainty

Owners update affected contracts and overview with behavior. Review drift at
change/release and every 90 days of active development, adjusting for real burden.
No automatic scheduler or cleanup is installed. The documentation/control changes
can be reverted without migrating saves or replacing the game. We do not know
whether these practices reduce long-term maintenance effort yet; track failed
procedures, contradictions, review effort and useful defects detected.

## Acceptance and decision rights

The user can answer purpose, capabilities/limits, rationale, next change/tradeoff
and evidence from the overview and immediate links. Every mandatory standard maps
to a control with owner, trigger, mechanism, evidence, failure response and limits.
Portable checks detect broken mappings, boundary/version drift and representative
negative cases. Curated historical provenance retains verified hashes without
committing media. Independent review and lead verification resolve material gaps.
No new native gameplay success is claimed by this change.

No further user decision is needed for this authorized increment. Changes to
constraints, product guarantees, hosting commitments or expanded gameplay scope
must be surfaced separately. Routine implementation choices remain with the lead.

Validation and remaining coverage limits: [engineering-system acceptance](../acceptance/2026-10-17-engineering-system.md).
