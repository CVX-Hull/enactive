---
owner: maintainer
review_trigger: Changes to this standard, its controls or engineering constraints
status: active
---

# Authority and reading order

The [overview](../overview.md) is the user's starting point; the charter owns purpose,
constraints and principles. This document owns engineering requirements. Current
architecture and protocol own system behavior. Setup and runbook own procedures.
GitHub Issues and the linked Project own active priorities, status, blockers and
exceptions; work.md is their navigation entry point. Dated acceptance reports
own historical observations; ADRs own decision rationale; research owns external
evidence and its limits. AGENTS.md routes agents to the relevant current material.
A discrepancy is a defect to resolve, not permission to silently pick a convenient
source. User instructions take precedence. Proposed/superseded records cannot
silently change current contracts. Link to authoritative facts instead of copying
full contracts, procedures or delegation rules into multiple documents.

Principles explain the desired qualities and tradeoffs. Policies are decision rules
about when and by whom work proceeds; they live here and in project management.
Standards specify required properties; contracts/design apply them at a boundary;
controls provide prevention, detection, review or recovery; evidence records what
actually happened. These are related responsibilities, not six mandatory documents
per change. [Engineering](../engineering.md) maps each standard to its principles and
controls, once. [Documentation organization](../documentation.md) defines artifact
roles and their lifecycle.

## Control review

The [controls page](../controls.md) owns what each control stops, where it is
enforced and its known gap. A control exists only to stop a named failure more
cheaply than the failure costs ([ADR 010](../decisions/010-streamlined-delivery.md)).
Review it when it fails, is bypassed, costs more than expected or its boundary
changes, in the issue that changes it; keep, narrow, replace or retire it from that
evidence, and change the controls page and the standards that name it together.
Revisit custom tools and previously rejected reuse options on changed needs, upstream
support, repeated defects or excessive upkeep, rather than accumulating controls.
Keep three facts distinct: a control exists; it was exercised with a result, recorded
in the dated record or PR that ran it; its effectiveness was assessed. A failure stays
in history after repair; actual affected failures or evidence gaps stop the affected work.
An exception issue identifies scope, owner, expiry, reason and mitigation; it
does not silently suppress a failed mechanical gate or override user constraints.

## Change and review cadence

Define outcome/failure conditions → inspect real interfaces → brief/design where
needed → implement a cohesive slice → run relevant checks → review risk and
semantic drift → inspect staged candidate → checkpoint with honest scope.
The fast development-checkpoint command is `python tools/check.py --fast`, with
applicable focused behavior tests chosen by the lead. The default common command
`python tools/check.py` remains full. The [protected CI profile policy](../workflows/ci-profiles.md#protected-ci-profiles)
owns eligibility and evidence reuse; [development-first delivery](../workflows/development.md#development-first-delivery)
owns sequencing and escalation. Setup owns commands and environment requirements.
Only a successful full profile establishes a full portable pass; fast, editorial
and selected smoke results must state their narrower executed and unrun lanes.

On behavior changes, update contract, tests, guide and overview as applicable.
On failure, classify transport/perception/decision/engine/process, preserve
provenance, and add a reusable regression or adjust a rule when justified.
At a release, verify high-risk operating procedures, open exceptions, dependency
pins and research currency. During active development, review external dependency
and documentation drift at least every 90 days; when dormant, review before
resuming. This is a starting policy, not an empirical optimum or an installed
scheduler. Adjust based on actual drift and review burden. Remove checks that
cost more than the risk they control, recording the rationale.

Track practical signals in work/release reviews: failed setup/recovery instructions,
contradictory guidance, repeated questions, escaped defects, false-positive checks,
review effort and duplicate edits per behavior change. Do not optimize document
count, lines of code or test count as substitutes for quality. The research basis
and evidence limits are in [engineering research](../research-engineering.md).

[Standards index](../engineering.md).
