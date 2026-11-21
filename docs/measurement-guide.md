---
owner: lead
review_trigger: Telemetry, source/store readers, clocks or outcome assessment changes
status: active
---

# Record and review gameplay measurements

Measure elapsed time to useful milestones in real play. Provider speed, tool
delivery and page timing explain parts of the path; none certifies useful progress.
Starting inventory is not acquisition, menu Save is not application exit, and a
finish report is not game success. For how to freeze,
retain and review evidence, see the [evidence workflow](workflows/evidence-cadence.md).

## Player host events

Separate request construction, provider request and tool execution. Header and
first-body arrival times include network and provider delays. Use the
[host telemetry contract](contracts/player-host-telemetry.md#telemetry) to identify the
recorded events and clock domains.

## Latency budgets for interactive play

Report actual milestones and elapsed time, including delays between useful
effects. Include route and effort, context and image sizes, cache observations,
retries, source coverage and uncertainty. See the [useful-goal cadence outcome](https://github.com/CVX-Hull/enactive/issues/164)
for the assessment criteria.

### Request settlement clocks

Use the original intent, send and receipt times for mechanical delivery. A later
collection time describes when you retrieved the result. Subtract monotonic
timestamps only within the same clock domain. Use coherent wall clocks to align
events across domains, and treat the alignment as approximate.

## Retained host and browser analysis

The [recorded-screen fixture](../tests/fixtures/recorded_player_mcp.py) serves retained
labelled PNGs through the current tool schemas to an unchanged player host and refuses
every effect; it has no live target or player store. Each paid assessment with it needs
its own frozen protocol and owner agreement, and it qualifies no live game effect
([two-case record](acceptance/2026-11-05-recorded-player-assessment.md)).

Run these offline, read-only diagnostics on a selected session.

```sh
.venv/bin/python -m tools.evaluate host-summary .runtime/computer-sessions/SELECTED
.venv/bin/python -m tools.evaluate control-summary .runtime/computer-sessions/SELECTED
```

The [evaluation contract](contracts/measurement-tools.md#diagnostics-owned-by-this-contract)
defines the summaries. For what browser evidence establishes, see
[spectator component](components/spectator.md#assurance-and-evidence).

## Investigate a selected interval

Select the run and interval in the [recorded viewer](operations/start-observe.md#recorded-browser-entry).
Open the original frames beside tool calls, requests and handoffs. Check their
provenance and coverage before interpreting the interval.

Compare request and tool durations without adding overlapping spans. Leave
uncovered time unknown. Use receipt and presentation points to order evidence,
and use the original timings to measure elapsed time.

Use patterns in the interval to form hypotheses for the next experiment. If
coverage is insufficient, identify the missing evidence.

## Caller contract

Use original operation IDs and immutable source references from the
[computer-control contract](contracts/computer-control.md). Check player claims
against actual images and owned-process receipts for useful effects, changes in
quantity, handoff, save/reload identity and normal ending. Record unknown delivery
alongside any separately verified visible effect.

## Offline review

Use the [testing guide](testing.md#review-overlap-by-failure-responsibility) to
interpret fixture and real-game evidence.
