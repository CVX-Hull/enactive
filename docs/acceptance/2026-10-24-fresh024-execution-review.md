---
owner: lead
status: historical
date: 2026-10-24
scope: Read-only Fresh024 task-path, program-coverage and timing-evidence review; no resumed gameplay or performance qualification
---

# Fresh024: local programs work, but cover little of the run

The player still made most interaction decisions through individual tool calls.
Programs executed **104 of 1,376 charged primitives (7.56%)** in 19 requests. They
are working local state machines, not yet a sufficient fast execution layer for
the campaign. Memory authoring remains on the deciding player's path, but the
retained clocks cannot establish how much wall time it caused.

This is a focused follow-up to the [original closeout](2026-10-24-independent-seven-day-twenty-fourth-attempt.md),
which owns the source/native pins, failed outcome, all-role costs and exceptional
ending. No game, native probe or benchmark was launched. Independent read-only
lanes reviewed original traces, program results, source responsibilities, research
and backlog; the lead checked counts and source boundaries. This report does not
turn the failed 30h44m partial into seven-day, cadence or learning-benefit acceptance.

## Where the deciding player's work went

| Observed surface | Count and interpretation |
| --- | --- |
| Admitted skill requests | 738:705 direct,19 program,6 edit,3 inspect,3 navigate,2 menu. Direct means the request kind, not proof of its semantic purpose. |
| Other admitted requests | 100 Observe,18 remember,8 lifecycle,1 Start,1 Stop;866 total. |
| Original-host MCP calls | 937 completed items:751 skill attempts,100 Observe,42 result collection,21 remember attempts,9 lifecycle,7 context,4 source,1 advice,1 Snapshot,1 detail. Some fail before ledger admission. |
| Model-authored memory attempts | 11 Claim and10 Procedure calls. The ledger admits8 Claim and10 Procedure requests; one Procedure request is blocked for unrelated evidence, leaving9 stored revisions. Three Claim drafts fail before admission. |
| Automatic memory | 2,171 stored Claims, mostly native capture bookkeeping; these are not 2,171 model-authored writes or proof that every row entered every prompt. There are no Work or Decision rows. |
| Advisory output | 16 claimed/completed jobs,19 notes,0 candidate procedures; one explicit advice fetch with a supported hydration correction. Limited useful overlap exists, but later trajectory coverage runs out. |

The result-collection calls are mechanical opportunities to assess, not 42 proven
avoidable waits: original operation deadlines, pending states and unknown delivery
still matter. Current tools already derive canonical player metadata and many
action/result joins. The remaining problem is not that the player transcribes
every machine identifier, nor that all memory operations should use another model.

## What the programs actually did

Grouping by stable procedure family, rather than changing revision goal text:

| Family | Calls / charged primitives | Observed result and limit |
| --- | ---: | --- |
| Adjacent pickup | 3 /10 | Distinct locker selections, including a one-input yield when no new essentials were found. Acquired-item success needs the actual subsequent evidence. |
| Rest revisions1–4 | 11 /51 | Short menu routines selected intervals and returned for activity/player assessment. One numeric choice selected weather-change waiting instead of the intended interval. Revision5 was later stored retired, with no invocation. |
| Consume intended item | 2 /12 | Selected ration/item paths. Its own completion is not independent proof of hydration, nutrition or survival benefit. |
| Smartphone light | 1 /12 | Traversed menus, then requested actual lighting/battery verification. |
| Conservative recovery | 2 /19 | Later revised recovery selections; no general threat-handling or safety claim. |

All 104 program primitives have returned delivery records. That proves neither
the procedure's own success label nor causal usefulness. The mean is 5.47 inputs
per invocation; many inputs are menu traversal. Primitive count is a coverage
diagnostic, not an optimization target: unnecessary inputs must not earn credit.

The wait mismatch is retained in `op-297926e94f0448749c8f99a10270563a` and the
[visible menu](../assets/fresh024-wait-menu.png). Numeric 8 selected “Wait till
weather changes.” This supports observation-conditioned selection and post-state
verification, not a harness-maintained catalogue of CDDA menus. The later threat
retirement does not prove a missing program-view field caused the incident.

Source inspection confirms `ProgramInputSkill` evaluates a pinned `step(view,state)`
after fresh feedback; there is already **no LLM call between its primitives**.
Its structured view excludes pixels and some HUD/editor facts. Missing data must
lead to appropriate uncertainty/yield or ordinary image-informed discovery, not
an assumption that visible content is absent. Longer routines require useful
progress, suitable observations and correct termination, not merely a larger cap.

## What the clocks and payloads can establish

Inside the programs, 85 adjacent native-ACK timestamp pairs have median 2.260s,
p95=2.935s and maximum 3.011s; all are positive. Eighteen invocations contain
multiple ACKs; one contains only one. The first pickup's six ACKs span 1.321s,
while a later ten-input recovery spans 25.952s. These same-clock intervals include
game processing, capture, storage and harness feedback between acknowledgments;
they exclude first-input latency and cannot isolate any component's CPU time.
There is no model call between these primitives. Thus local execution itself
needs investigation; off-path memory reasoning or a faster model alone cannot
remove this observed delay. Different routines/states prevent attributing the
difference to history growth from these examples alone.

The existing controller journal supplies a narrower join for these104 inputs:

| Local interval | Samples | Median | Inclusive p95 |
| --- | ---: | ---: | ---: |
| Program `step` evaluation | 104 | 0.877ms | 3.182ms |
| Evaluation journal timestamp → native admission journal timestamp | 104 | 1.5745s | 2.096s |
| Native admission journal timestamp → native ACK timestamp | 104 | 31ms | 45.85ms |
| Native ACK timestamp → next evaluation journal timestamp, same invocation | 85 | 636ms | 824ms |

These endpoints are the retained same-host epoch-millisecond events, except the
evaluator's own elapsed timer. They are not interchangeable with monotonic receipt
time, physical display or whole-player response. Cohorts differ; do not add their
percentiles or treat them as an exhaustive service-time allocation. The principal
observed local delay surrounds evaluation/native admission, not JavaScript
execution itself. A late sequence also records a fresh Observe between those
endpoints.

Source inspection identifies repeated retained-file scans in EvidenceStore usage/
capacity, whole-manifest serialization/publication, selected-source hashing,
image persistence and journal fsync as plausible costs on that path. No retained
subphase profile assigns their individual contribution. Profile before choosing
a repair; do not remove selected-source/custody checks or persistence guarantees
from a timing correlation. Reuse configured filesystem/SQLite contracts instead
of duplicating an archive consistency audit on every input where unnecessary.

The 865 adjacent request-admission gaps have median 12.971s, p90=35.942s,
p95=48.908s, p99=107.047s and maximum 467.278s; 116 exceed 30s, 26 exceed 60s,
and 2 exceed 300s. Percentiles use inclusive linear interpolation. These are
**request-arrival gaps**, not useful-decision latency, model inference or tool
service time. They include mixed request classes, activities and later closeout.
The first 25 admissions span 225.684s and include setup; they are not a routine cohort.

The host JSONL has no per-item timestamps. The request table stores `admitted_at`
but no completion timestamp; `complete_request(now=...)` updates state/result
without retaining that endpoint. Primitive ACK epoch and monotonic receive clocks
have no retained origin mapping sufficient for a complete join. Summing service
intervals or allocating these gaps to memory/inference/approval would invent data.
Existing DOM proxies are not physical paint or a qualified useful-effect endpoint.

Original-host MCP text totals 6,244,081 UTF-8 bytes. Skill replies have median 6,682B
and maximum 10,062B; 7 context replies have median 20,938B and maximum 27,854B.
Repeated envelopes appear frequently, but neither these bytes nor cached-token
share establishes a bottleneck. Count actual forwarded context, image and host
work before choosing further projection. The original closeout owns full scope
and omissions; there is no isolated monetary/inference/hidden-review measurement.

## Reproduction and decision

Read the original `driver-original.jsonl` as a stream under
`.runtime/campaigns/independent-seven-day-024/`; select completed MCP items, not
both started and completed copies. Open the original mission database using
SQLite URI `mode=ro&immutable=1`, without constructing a runtime or memory writer.
The relevant existing queries are:

```sql
SELECT json_extract(payload,'$.kind'),
       json_extract(payload,'$.skill_kind'), count(*)
FROM requests GROUP BY 1,2;
SELECT id, payload FROM requests
WHERE json_extract(payload,'$.skill_kind')='program';
SELECT request_id, state, count(*) FROM primitives GROUP BY 1,2;
SELECT request_id, json_extract(result,'$.native_ack.timestamp_ms')
FROM primitives ORDER BY rowid;
SELECT entry_type, count(*) FROM memory GROUP BY 1;
SELECT admitted_at FROM requests ORDER BY rowid;
```

Join program requests' selected `procedure.revision_id` to immutable Procedure
records and group their stable `procedure_id`; preserve attempted, blocked,
retired and unexecuted revisions separately. Sort adjacent admissions before
computing gap percentiles; retain the definitions above rather than calling them
latency. For within-program intervals, group ACKs by program request, preserve
primitive row order and difference only adjacent timestamps within that group;
do not compare epoch ACKs to monotonic receipt clocks. Tool arguments distinguish
Claim versus Procedure authoring attempts.

For the local component join, use the existing session journal
`.runtime/sessions/20261024-072018-bfecea94/events.jsonl`: select
`mission_program_step` entries with `outcome.status=act`, ordered within each
program request. Join each primitive's `native_request_id` to the
`mission_admission` event's `outcome.request.id`; check one-to-one coverage of
all104 inputs. The next evaluation must belong to the same program. The evaluator
records `evaluation_seconds`; journal envelopes record `timestamp_ms`. This
join does not recover missing host/model timestamps.

The next source iteration should combine local feedback-path cost, useful routine
coverage, off-path candidate authoring/retrieval and sufficient timing joins. Another architecture
audit or model switch alone will not deliver responsive play. The
[proposed design](../design/asynchronous-reflection.md#execution-first-learning)
and [research update](../research-multirate-agents.md) explain the selected direction;
[#164](https://github.com/CVX-Hull/enactive/issues/164),
[#177](https://github.com/CVX-Hull/enactive/issues/177) and
[#178](https://github.com/CVX-Hull/enactive/issues/178) own live scope and sequencing.
Actual gameplay remains user-paused; eventual campaign acceptance stays in
[#145](https://github.com/CVX-Hull/enactive/issues/145).
