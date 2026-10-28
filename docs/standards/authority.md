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
per change. The registry maps P-* → S-* → C-*; it does not own another requirements
copy. [Documentation organization](../documentation.md) defines artifact roles and
their lifecycle.

## Control lifecycle and evidence

The registry owns each control's definition and latest maintenance record. Its
generated [maintenance table](../controls.md#maintenance) is the review entry point.
`proposed` means not relied upon; `active` means required in mapped standards;
`deprecated` means no standard may rely on it while its replacement/removal is
managed; `retired` preserves rationale/history and has no periodic review duty.
Only active controls support standards. Activation needs an owner, defined scope,
mechanism, failure response, limitations, maintenance review and acceptance evidence
appropriate to its claims. Deprecation/retirement needs rationale and any replacement;
replace standard mappings in the same change. Replacements cannot point to self or
form cycles. Changes are reviewed in Git; snapshot checks do not prove who approved
a transition. Re-activation requires a fresh review rather than reviving an old pass.

Keep three facts distinct: the control exists; it was exercised with a particular
result; its effectiveness has been assessed within a stated scope. `last_exercise`
links to a dated execution/review result recording candidate, environment, lane,
outcome and limits, not merely implementation source. Null means no recorded exercise.
Maintenance review records findings, effectiveness and cost with evidence; its follow-up links the existing Issue, which owns changing acceptance, allocation and stage.
Include custom tools/processes and previously rejected reuse options: revisit on
changed needs, upstream capability/support, repeated defects or excessive upkeep;
replace or retire redundant machinery rather than accumulating controls. Keep the
decision with its existing owner and record, not a second maintenance system.
Effectiveness can be unassessed; a fresh metadata review must not refresh native execution dates.
Exercise and maintenance review are independent events. Dated reports retain prior
observations when the latest record changes. A failure remains in history after repair.

Active/deprecated controls need a next review within 90 days of the recorded review,
with event triggers requiring earlier work. Every strict CI profile and standalone
governance uses the current date and fails **after** the due date. Fast development
checkpoints instead
print calendar-expiry warnings for all controls; they do not infer which controls
are relevant or relax structural, ownership, evidence/reference, chronology,
protocol or generated-map checks. Event-triggered review on resumption, incidents,
changed boundaries and release still applies; actual affected failures or evidence
gaps stop the affected work. Resolve overdue review at the existing integration/
formal-acceptance checkpoint. A warning is not effectiveness or support evidence.
The standalone `tools/governance.py --as-of YYYY-MM-DD` forecasts maintenance only;
it never renews records and cannot substitute for the common command's current-date
check. No check or background job edits dates automatically. At an overdue failure,
the owner reviews the control, records evidence/findings/actions, then chooses a
justified new date or retires/replaces it. Do not advance dates just to pass a check.
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
