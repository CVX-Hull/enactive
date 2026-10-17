# Active work and decisions

Owner: lead. Status: current board. Review at each integration checkpoint.
Current product summary: [overview](overview.md). Historical MVP outcomes and
failures: [2026-10-17 acceptance](acceptance/2026-10-17-mvp.md).

## Latest completed increment

[Brief 001](changes/001-engineering-system.md) is verified: charter and progressive
overview, current architecture/protocol and decision history, ten standards mapped
to eleven controls, mature development tools, historical provenance and operating
maintenance practices. See [acceptance](acceptance/2026-10-17-engineering-system.md)
for execution scope, independent review, failed attempts and remaining limitations.

No implementation slice is active. No current blocker or approved exception.
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
During active development review external drift every 90 days; next baseline due
2027-01-15, earlier on relevant change. No scheduled automation is installed.

Record an exception here with standard, exact scope, reason, accountable owner,
expiry/revisit, mitigation and disposition. Never waive user constraints or erase
failed tests. Record process observations here when they arise: failed guides,
contradictions, repeated questions, escaped defects, false alarms and review burden.
Promote durable lessons into standards/tests; archive completed increments into
dated reports and remove their detailed progress rows from this board.
