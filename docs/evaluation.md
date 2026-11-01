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

Current [`player-host/4`](contracts/player-host.md) uses telemetry version2 (retained
`player-host/1` traces report `unsupported_version`; their summaries stay in the
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
context is reused across actors; variable role, resource and handoff data stays
explicit in prompts. The host's decision-time budget is distinct from the native
custodian horizon. Request serialization and context projection have their own
measured costs; local headers/first bytes do not isolate provider queue or inference.

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

These commands are offline and read-only, writing summaries to stdout:

```sh
.venv/bin/python -m tools.evaluate host-summary .runtime/computer-sessions/SELECTED
.venv/bin/python -m tools.evaluate control-summary .runtime/computer-sessions/SELECTED
.venv/bin/python -m tools.evaluate witness-summary .runtime/computer-sessions/SELECTED observer-export.json
```

The selected actor traces and current `campaign-run/4` / `campaign-receipt/2`
sidecars supply scoped provenance. The control reader opens a current
`computer-session/2` SQLite snapshot read-only, bounded by table/byte/path limits;
it neither migrates data nor reconstructs authority. `observer-timing/4` exports
join exact session/source/capture/presentation IDs. Duplicate exports do not create
new witnesses. DOM replacement is neither physical paint nor model attention;
missing/invalid clocks and unmatched sources remain explicit. No runtime-wide
recursive history scan or legacy executable reader is supported.

## Investigate a selected interval

The [local investigation procedure](operations/start-observe.md) turns explicitly
selected closed current cases into a bounded [artifact](contracts/observer-investigation.md).
Analysis also attaches an on-demand current-session snapshot, labelled by its
separate producer cutoffs, per-kind retention and unknown live totals. Refresh
does not manufacture a closure receipt, new observation or automatic outcome.
The shared live/offline reader exposes interval lanes, exact rows, source pixels,
usage fields and existing attributed assessments. It does not collect new evidence
or turn public statements into verified outcomes. Whole-case coverage and omitted
fields remain visible beside a selected interval.

Compare request/tool wall unions, overlap and uncovered intervals without adding
overlapping spans or calling uncovered time idle. Same-domain original durations
remain separate from the approximate shared wall axis; result/presentation points
do not imply zero execution time. Kind/text filters narrow exact rows, not timing
accounting. Program local elapsed time excludes authoring/retrieval/repair unless
separate retained records establish those costs. Same-version links expose available
authoring/read/collection spans without treating a later collection as original preparation. A live snapshot's
added axis tail is unmeasured time, including snapshot preparation, not an inferred
ongoing request or idle/inference duration. Missing program/error/authoring
detail limits diagnosis even when child native/source references are available.

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
not organic gameplay. Earlier waypoint/mission evaluation formats and commands are
retired; their original readers and reports remain in
[Git history](https://github.com/CVX-Hull/enactive/blob/433ed973afe312d03f777d8b102a0cba528af746/docs/evaluation.md).
A successful later repair cannot relabel a failed attempt or renew its allocation.
