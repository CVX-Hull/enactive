---
owner: lead
status: proposed
review_trigger: GitHub workflow, publication scope or verification changes
---

# Public project workflow

## Outcome and scope

Publish the source as CVX-Hull/cdda-player, with a public linked GitHub Project,
Issues for work state, PRs for reviewed implementation and verified hosted CI and
main-branch rules. The user owns direction; the lead owns integration and evidence.
The user selected MIT for original project work; upstream-derived code and assets
retain their existing terms. Audit tracked history before publishing. No game,
saves, credentials, downloaded dependencies or runtime logs are published.

## Before and after

Previously the local work page owned priorities and a bypassable local hook ran
checks. GitHub will own live work status and enforce selected merge rules. Durable
specifications, principles and acceptance remain versioned documents. Replace the
duplicated Markdown backlog with links. Public evidence must distinguish portable
CI from local native gameplay and retain the unavailable-large-media limitation.

## Design and delegation

Use native Issues, sub-issues/dependencies, Projects fields/views and branch rules;
do not build a tracker. Ready means a bounded outcome, scope, acceptance, ownership
and dependencies are known. Done means integrated and accepted, not just generated.
Separate Review and Validation; preserve blockers and uncertainty. Use size and
confidence initially, then calibrate forecasts from comparable observed history.

Project-scoped S-AGENT now permits two bounded workers in separate project-local
worktrees with disjoint ownership. Lead alone integrates; game/runtime and mutable
build/dependency resources remain serialized. No global delegation file changes.
Implementation briefs allocate documentation and contributor templates separately.
The lead handles GitHub configuration, licensing, publication and final evidence.

## Alternatives and maintenance

A second tracker duplicates state; a custom orchestration framework adds upkeep.
Retain ordinary Git and GitHub capabilities. Required PR/check rules are useful
even with one GitHub identity; independent agent review is not a second human
GitHub approval. Review WIP, aging work, defects, cost and rule effectiveness at
milestones and after failures. No unrequested timer or background agent is added.

## Acceptance and risk

Verify public repository/project visibility, linkage, seeded work and dependencies;
inspect useful views. Execute hosted CI on the published candidate. Require its
actual status context and PRs, prohibit force-push/deletion of main, and inspect
bypass configuration. Exercise a harmless direct-main negative probe and a normal
PR path; preserve unexpected success/failure honestly. Do not bypass protections
to finish. Independent review checks authority, isolation, contributor usability
and publication evidence. If GitHub permissions/API limits block an outcome,
record the exact limitation rather than claim configuration is enforcement.
