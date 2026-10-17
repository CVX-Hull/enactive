---
owner: lead
review_trigger: Each integration checkpoint and maintenance finding
status: active
---

# Active work and decisions

Current product summary: [overview](overview.md). Historical MVP outcomes and
failures: [2026-10-17 acceptance](acceptance/2026-10-17-mvp.md).

## Consolidated goal verified

The full [project goal](goal.md) is verified within its stated MVP boundaries.
The [completion audit](acceptance/2026-10-17-completion.md) maps every outcome to
evidence. Independent review's two gaps were resolved with a real-game planner-loop
timing trial and pinned reuse-candidate sources; targeted re-review found no remaining
material issue. The trial preserved existing guards, saved/reloaded normally and
ended with remote control paused. No active implementation slice or blocker remains.

## Completed documentation increment

[Brief 002](changes/002-documentation-review.md) is verified: documentation metadata,
control lifecycle and review records, local overdue checks, three rendered visual
explanations and a first-session walkthrough. See [acceptance](acceptance/2026-10-17-documentation-review.md)
for checks, independent findings/fixes, visual inspection and evidence limits.
The consolidated [project goal](goal.md) includes the previously accepted MVP and
engineering-system increments. No current blocker or approved exception.
The next proposed product slice is native activity interruption and error-screen
recovery; it requires its own design/acceptance and is not started by this board.

## Prioritized deferred work

| Priority / work | Why deferred | Revisit / acceptance |
| --- | --- | --- |
| Native activity interrupt and unsupported error screens | Requires engine design and real scenario validation; current pause limitation is explicit | Next gameplay reliability slice; demonstrate interrupt semantics and recovery in native game |
| Automated native regression runner | Existing real acceptance is manual and host-specific | Bridge/platform expansion or repeated upgrade burden; validate actual engine transitions, not a mock |
| Broader survival/agent independence | Current Codex-guided scope remains useful | Explicit product expansion with task-based evaluations and cost/latency/survival measures |
| Multi-host/instance support | One tested Mac; alternatives not benchmarked | Requirements or maintenance evidence reopen platform ADR |
| Stronger hosted merge enforcement | No remote requested; local hook is bypassable | When shared remote is authorized, configure and verify required checks/reviews |
| Broader formatting/type-analysis | Selected Ruff correctness checks are enabled; formatting/types remain review-based | Repeated style/type defects or contributor growth; choose and pin locally |

## Maintenance and review record

On changed behavior: update authoritative contract, controls, guide and overview
as relevant. At release and before resumed work after dormancy: inspect high-risk
procedures, exceptions, evidence availability and dependency/research freshness.
During active development review external drift within the dates in the
[maintenance table](controls.md#maintenance), earlier on relevant change. No
scheduled automation is installed. The first baseline is not longitudinal evidence
of effectiveness. Track the browser/dependency burden and whether the three visuals
actually reduce review questions; revisit the toolchain if costs outweigh that value.

Record an exception here with standard, exact scope, reason, accountable owner,
expiry/revisit, mitigation and disposition. Never waive user constraints or erase
failed tests. Record process observations here when they arise: failed guides,
contradictions, repeated questions, escaped defects, false alarms and review burden.
Promote durable lessons into standards/tests; archive completed increments into
dated reports and remove their detailed progress rows from this board.
