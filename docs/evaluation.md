---
owner: lead
review_trigger: Telemetry, source/store readers, clocks or outcome assessment changes
status: active
---

# Record and review gameplay measurements

Measure whole apparent useful-goal latency and behavior through real organic play.
Provider speed, tool delivery and DOM timing explain portions of the path; none
certifies useful progress. Freeze goals/configuration/resources before each finite
attempt, retain failures, and have an independent assessor review actual images
and original operation/source references. Starting inventory is not acquisition;
menu Save is not application exit; a local routine's done is not game success.

## Player host events

Current [`player-host/4`](contracts/player-host.md) uses telemetry version4 (a
`player-host/3` trace is read only inside the run directory of a session the
[closed archive index](contracts/evaluation.md#implementation-rules) lists; retained
`player-host/1` and `/2` traces report `unsupported_version`, and their summaries stay in the
acceptance records), one JSONL trace per actor at
`actors/NNN/host.jsonl`. Original request/tool IDs, wall and monotonic timestamps
correlate request construction, fetch, headers, first body, completed response,
provider refusal, tools and settlement. Exact payload SHA256/byte and image counts
replace persisted request bodies. Image telemetry stores digest/size references;
bounded ordinary assistant narration remains available. Private reasoning and
base64 history are excluded from telemetry without altering the actual model input.

Returned usage/cache/backend/service-tier metadata remains labelled by source.
Missing usage is unknown, not zero or an invoice. Every HTTP attempt, including an
eligible bounded 429 retry, consumes the original allowance. Stable frozen system
context and the ongoing objective are reused across actors; handoff knowledge
stays explicit fallible prompt data. Experiment quotas and final-actor policy
remain operator data. The host's decision-time budget is distinct from the native
custodian horizon. Request serialization and context projection have their own
measured costs; local headers/first bytes do not isolate provider queue or inference.

Control intent/acceptance, direct player-finish claims, host settlement, permanent
stop, game-persistence evidence, normal native exit and owned absence are separate
facts. A finish report does not certify the game outcome. Incomplete ending or
missing persistence evidence remains visible even if mechanical cleanup succeeds.

## Latency budgets for interactive play

Prefer a useful image-conditioned local program when it improves the task, while
preserving ordinary input fallback. Do not optimize call counts at the cost of
behavior or hide long reasoning/tool/approval gaps behind token throughput. Report
model/route/effort, context and image sizes, cache observations, retries, source
coverage and uncertainty alongside actual useful milestones and elapsed time.
[#164](https://github.com/CVX-Hull/enactive/issues/164) owns broader cadence
qualification; this diagnostic tooling cannot accept it automatically.

### Request settlement clocks

The mechanical store retains original intent/send/receipt wall and monotonic
timestamps. A later collection has the original ID and source receipt time; it
cannot renew freshness or overwrite an original unknown terminal disposition.
Cross-clock joins require coherent wall clocks. Never subtract unrelated monotonic
epochs or label network first-body time as first useful model decision.

## Retained host and browser analysis

For a separately approved candidate assessment, the scoped
[recorded-screen fixture](../tests/fixtures/recorded_player_mcp.py) can expose
original labelled PNGs through current tool schemas to the unchanged player host.
It refuses every effect and has no live target or player store. Its closed local
packet contains `current_source_id` and an ordered `sources` list of unchanged
`computer-source/1` metadata. Original PNGs are sibling `sources/<source_id>.png`;
hashes, dimensions, membership, regular files, at most thirty sources and 16 MiB
total PNGs are checked before serving. Source and focused tests own the executable
format. Each new paid assessment needs its own frozen protocol and agreement
([rationale](changes/074-recorded-player-assessment.md)). Offline tests establish the
fixture boundary only; provider compatibility, grounded proposals and actual
game usefulness require separate evidence. Host request-limit failure remains a
failure even if complete bounded assessment evidence was collected.

The [two-case candidate record](acceptance/2026-11-05-recorded-player-assessment.md)
holds the fresh-host recorded-image continuation result. A recorded assessment qualifies no
live game effect.

These commands are offline and read-only, writing summaries to stdout:

```sh
.venv/bin/python -m tools.evaluate host-summary .runtime/computer-sessions/SELECTED
.venv/bin/python -m tools.evaluate control-summary .runtime/computer-sessions/SELECTED
```

The selected actor traces and current `campaign-run/6` / `campaign-receipt/4`
sidecars supply scoped provenance. The control reader opens a current
`computer-session/1` SQLite snapshot read-only, bounded by table/byte/path limits;
it neither migrates data nor reconstructs authority. The browser page produces no
timing record, because DOM replacement is neither physical paint nor model attention
([ADR008](decisions/008-evaluation-and-spectator.md)). No runtime-wide
recursive history scan is supported.

## Investigate a selected interval

The spectator's separate read-only viewer shows a run from the offline evaluator's
records ([evaluation contract](contracts/evaluation.md)): steps with their original
frames, tool calls, requests, memory, programs and handoffs, each labelled with its
source and confidence. Operator steps are in
[start and observe](operations/start-observe.md). The viewer collects no new evidence,
captures no pixels and turns no public statement into a verified outcome. Coverage and
missing readings stay visible beside each value.

Compare request and tool wall time without adding overlapping spans or calling
uncovered time idle. Same-domain original durations stay separate from the
approximate shared wall axis; result and presentation points do not imply zero
execution time. Program elapsed time excludes authoring, retrieval and repair unless
separate retained records establish those costs. Missing program, error or authoring
detail limits diagnosis even when child native and source references are available.

Use the evidence to choose a concrete next gameplay experiment, explicit no-change
or missing-data decision. A plausible chart pattern is a hypothesis, not an
automatic causal diagnosis or acceptance of #164's useful-goal cadence.

## Caller contract

Use original operation IDs and immutable source references from the current
[contract](contracts/computer-control.md). Player claims, Work, corrections and
program results remain fallible evidence. Independently establish useful effects,
quantity changes, handoff application, save/reload identity and normal ending from
actual behavior and owned-process receipts. Unknown delivery and separately
resolved visible effects must both remain in the account.

## Offline review

Current fixture suites establish their stated source/SDK/socket/SQLite/V8 bounds,
not organic gameplay. A successful later repair cannot relabel a failed attempt or renew its allocation.
