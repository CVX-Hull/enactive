---
owner: lead
review_trigger: A record, metric, reader, health rule or view-API change, or a new game binding
status: proposed
---

# Run evaluation records, metrics and the spectator view

**Status: proposed target formats for [#383](https://github.com/CVX-Hull/enactive/issues/383).**
This page becomes the current contract when the evaluator ships.
[ADR008](../decisions/008-evaluation-and-spectator.md) owns the rationale.

Every value here is **interpretive**. It is derived from recorded evidence, carries its
source and confidence, and accepts nothing. Frames, receipts and the issue's decision
rule still decide acceptance. No value on this page reaches the player.

## Inputs

The evaluator reads one run directory read-only:
- `session.sqlite3` (`computer-session/1`);
- `sources/*.png`;
- each `actors/NNN/host.jsonl` (`player-host/3`), including its per-request context
  manifest once the host records one;
- the handoff contexts under `contexts/*.json` (`player-handoff-context/1`);
- `manifest.json` (`campaign-run/5`), including its operator labels;
- the run's `player-memory/2` store.

Open SQLite read-only (`mode=ro`) with a bounded busy timeout. A missing or unsupported
input format is an error naming the file and version. Nothing is guessed.

**Sequence and incremental reading.**
- The operation sequence `seq` is the `operations` table's rowid.
- An incremental pass reads rows with `seq` greater than the last one seen.
- It also re-reads every earlier row whose `final_json` was still null, because the
  store settles an operation after inserting it.

## `evaluation-record/1`

One SQLite file per run and version pair:
`.runtime/evaluations/<session>/<core_version>-<binding_id>-<binding_version>.sqlite3`.
Its `metadata.state` is `live` or `final`.
- **Live.** The viewer may write and extend a `live` store while the run moves.
- **Final.** `evaluate-run` writes a `final` store after the run ends, replacing a
  `live` store of the same versions. Input digests are taken only then.
- **No overwrite.** A `final` store is never overwritten. Re-scoring under new
  versions writes a new file. Hand-scored evidence elsewhere is never modified.

| Table | Columns | Meaning |
| --- | --- | --- |
| `metadata` | `key`, `value` | `schema` (`evaluation-record/1`), `state`, `core_version`, `binding_id`, `binding_version`, `run`, `session`, `labels` (from the manifest), `last_seq`, `first_in_play_seq`, input paths with SHA-256 digests (final only), `created_wall` |
| `steps` | `seq`, `operation_id`, `actor`, `kind`, `wall`, `decision`, `tokens`, `dollars`, `game_time`, `mode`, `source_id`, `frame_sha256`, `frame_changed` | One row per computer operation. Three clocks: wall seconds; agent counters (decision index, cumulative tokens and dollars); nullable game time in the binding's unit. |
| `readings` | `seq`, `reader`, `reader_version`, `value`, `confidence`, `abstain` | One row per reader per step. `abstain` holds a reason, and `value` is then null. Abstention is never counted as zero. |
| `events` | `id`, `seq_start`, `seq_end`, `kind`, `source`, `confidence`, `payload` | Interval or point events (the kinds are listed below) |
| `metrics` | `name`, `version`, `value`, `count`, `denominator`, `missing` | One row per metric. `count` and `denominator` are always stored. `missing` names the missing-data rule that applied, or is null. |

**Event envelope.**
- `source` is one of:
  - `harness`: a recorded mechanical fact;
  - `reader`: a binding reader;
  - `player_claim`: player text or a player record;
  - `human`.
- `judge` is reserved for the deferred model judge.
- `confidence` is 0–1, or null for mechanical facts.
- `payload` is JSON. Core field names never contain game words; game detail lives in
  `payload.binding`.

**Core event kinds.**

Mechanical (from host traces and the session store):
- `handoff`;
- `memory_write`, `memory_read` (with the returned record IDs);
- `program_save`, `program_run`;
- `tool_refused`;
- `context_eviction` (images omitted or blocked);
- `custody_stop`.

Derived from readings:
- `mode_change`;
- `long_activity`: consecutive clock readings advancing at least the binding threshold;
- `stall`: a streak of 15 or more decisions without an `in_play` mode;
- `ineffective_repeat`: the same binding-declared movement input on three or more
  consecutive decisions, with under 1% pixel change in the binding's map region;
- `vital_change`, `threat_change`;
- `milestone`;
- `death`;
- `continuity`.

## Core quantities and the binding interface

The interface is [`harness/evaluation/core/binding.py`](../../harness/evaluation/core/binding.py).

| Quantity | Core meaning | The binding supplies |
| --- | --- | --- |
| `mode` | `in_play`, `menu`, `prompt`, `loading`, `dead`, `unknown` | A mode classifier over a frame |
| `game_time` | Monotonic elapsed time in one unit | A clock reader, its unit and a maximum plausible jump |
| `vital` | Normalised 0–1 with scope `whole` or `part:<id>`, and a binding-decided `critical` flag | Readers that map labels or bars to vitals |
| `threat` | Count and bucket (`none`, `low`, `high`, `lethal`) | A threat reader and its bucket rule |
| `identity` | Text identifying the playing entity, when legible | An identity reader |
| `milestone` | A rung on an ordered ladder, with first-reached times on all three clocks | The ladder; each rung names the reader evidence that fires it, or `human` |
| `death` | A death event with a binding-supplied cause string | A death-screen reader |

**Plausibility guard.** A clock reading earlier than the last accepted one, or later by
more than the binding's maximum jump, abstains with `implausible`. The exception is a
jump the next reading confirms.

**Accuracy floors.** A reader's values feed a metric only after held-out validation
meets its floor:
- clock: 98% exact;
- mode: 97%;
- every other reader: 95% on non-abstained frames.

**The CDDA binding** (`harness/evaluation/cdda`) supplies:
- a glyph-atlas sidebar reader for date and time;
- a main-view mode template;
- need labels for hunger, thirst, weariness and pain;
- limb bars;
- monster-list ink;
- the death screen;
- identity where legible;
- a 900-second long-activity threshold;
- this ladder (evidence in brackets):

| Rung | Evidence | Rung | Evidence |
| --- | --- | --- | --- |
| `in_play` | reader | `clean_water` | human |
| `armed` | human | `slept` | reader |
| `water_obtained` | human | `survived_first_night` | reader |
| `drank` | reader | `elapsed_24h` | reader |
| `food_obtained` | human | `elapsed_72h` | reader |
| `ate` | reader | `elapsed_168h` | reader |
| `shelter` | human | `resupplied` | human |

A `human` rung is reported as not assessed until a human or a later reader confirms it.

## Metrics, version 1

A **decision** is one completed `computer_input` operation. Rates are shown with their
counts. A median or rate built from fewer than five qualifying intervals or events
reports `missing: insufficient`.

| Name | Definition | Denominator | Missing data |
| --- | --- | --- | --- |
| `survival.game_hours` | Last accepted game time minus game time at `first_in_play_seq`, in hours, with `died` (death event) or `censored` (alive at stop) | — | No accepted reading: null |
| `pace.routine_seconds_per_decision` | Median, over consecutive accepted clock pairs with at least one decision between them and a gap below the long-activity threshold, of (game-time change ÷ decisions between) | pairs | Fewer than five pairs: missing |
| `pace.long_activities` | Count and total game seconds of `long_activity` events | — | — |
| `pace.dollars_per_game_hour` | Run dollars ÷ survival game hours | game hours | Zero hours: null |
| `mode.out_of_play_share` | Decisions whose mode is not `in_play` ÷ decisions with a non-abstained mode | mode readings | Abstentions excluded and counted |
| `stall.longest` / `stall.count` | Longest streak of decisions without `in_play` (abstentions neither extend nor break a streak); number of `stall` events | decisions | — |
| `input.actions_per_call` | Actions in input operations ÷ input operations | input operations | — |
| `input.unseen_action_share` | 1 − input operations with a capture ÷ actions in input operations | input actions | — |
| `input.frame_unchanged_rate` | Input operations whose capture SHA-256 equals the previous capture's ÷ input operations with a capture | captured inputs | — |
| `custody.uncertain_receipts` | Partial or unknown receipts ÷ receipts | receipts | — |
| `custody.stopped` | Whether a custody stop ended the run | — | — |
| `tools.calls` | Calls per tool, with refusals and error results per tool | calls | — |
| `memory.writes` / `memory.reads` | Append calls; query, read and context calls | — | — |
| `memory.retrieved_beyond_carry` | Distinct records returned by any read that were not in the reading actor's handoff context ÷ distinct records written (at most 1) | records written | No writes: null |
| `memory.late_write_share` | Writes within an actor's last six tool calls ÷ writes | writes | — |
| `programs.saved` / `runs` / `reused` / `outcomes` | Saves; runs; runs by an actor or run other than the author; runs per status | — | — |
| `handoff.decisions_to_resume` | Decisions after a handoff until the first input operation with three or more actions and a changed capture | handoffs | — |
| `handoff.carry_ratio` | Handoff context file bytes ÷ the predecessor's last request text bytes | handoffs | — |
| `host.dollars_per_decision` | Configured-rate dollars ÷ decisions | decisions | Requests without usage: counted and excluded |
| `host.cache_write_share` | Cache-write dollars ÷ dollars | dollars | — |
| `host.large_rewrite_share` | Dollars of requests writing more than 30,000 cache tokens ÷ dollars | dollars | — |
| `host.latency` | Nearest-rank p50 and p95 of response time and of first-chunk time | requests | — |
| `host.retry_share` | Retries, aborts and non-tool stops ÷ requests | requests | — |
| `needs.severe_share` | In-play decisions with any `critical` vital ÷ in-play decisions with vital readings | readings | Abstentions excluded and counted |
| `ladder.reached` | Highest rung reached and decisions to each rung | — | `human` rungs: not assessed |
| `reader.coverage` | Non-abstained readings ÷ frames, per reader | frames | — |
| `lineage.continuity` | Per admission boundary: same identity (or `unknown`) and game-time gap (negative means rewound) | boundaries | — |

**Comparison statistics** (across runs, never within the player):
- Kaplan–Meier survival with Greenwood intervals;
- restricted mean survival to a horizon inside the observed range;
- the log-rank test;
- bootstrap intervals.

Censored runs stay censored.

## Control path and viewer

**Control path.** The supervised gateway (`tools/campaign_watch.py`) keeps:
- Pause;
- the attention checks;
- the page origin and static files;
- the frame and status that the checks read.

The checks read those only from the custodian's `/api/status` and `/api/source/<id>`
routes. The check panel's elements keep the identifiers that `tools/campaign_watch_ui.js`
reads: session, freshness line, source details and frame. A viewer outage therefore
cannot block a check, a Pause or a run.

**Viewer.** The viewer is a separate read-only loopback process. The gateway forwards
`/api/view/*` to it under these rules:
- 2-second timeout and 4 MiB cap;
- only `application/json` and `image/png` responses, never HTML or script;
- the gateway's own security headers on every response.

A forwarding failure returns `503` with `{"viewer": "unavailable"}`. The page polls;
there is no streaming connection.

**Launch and lifetime.**
- The supervisor starts the viewer as an **unsupervised** child: `python -m harness.viewer`.
- Its exit never ends, pauses or gates the run, and the supervisor stops it at the end.
- The viewer reads the live run directory and the evaluation root (`.runtime/evaluations`).
- It writes only the live run's `live` evaluation store.

## Record extensions (version 1 additions, before first delivery)

| Table | Columns | Meaning |
| --- | --- | --- |
| `run_facts` | `key`, `value` | From `manifest.json` and frozen inputs: `labels` (arm, start, scenario, lineage, admission), `source_commit`, model id, effort, route, guide and assignment SHA-256 digests, limits, and the declared spend ceiling |
| `tool_calls` | `request_id`, `tool_call_id`, `actor`, `decision`, `tool`, `status` (`ok`, `error`, `refused`), `latency_ms`, `result_bytes`, `wall` | One row per tool call, from host `tool-start`, `tool-result` and `tool-refused` |
| `requests` | `request_id`, `actor`, `wall`, `attempt`, `input_tokens`, `cache_read`, `cache_write`, `output_tokens`, `dollars`, `retry_class`, `omitted_images`, `manifest` | One row per HTTP attempt. `manifest` is `exact` when a `context-manifest` event exists, else `absent`. |

`metrics` gains a `key` column for multi-valued metrics, such as per reader, per
percentile, per status or per handoff. The primary key is (`name`, `key`).

**Further additions:**
- `source` gains `derived` for values computed from other records.
- `survival.game_hours` carries `censor_reason`:
  - `died`;
  - `budget`;
  - `player_stop`;
  - `custody`;
  - `infrastructure`;
  - `owner_pause`.
- **Episodes.** When game time moves backward by more than one day, or the identity
  reading changes, the evaluator starts a new **episode**. It emits an `episode` event,
  and survival is measured within the last episode.
- **Run end.** An orderly stop or a player finish is a `run_end` event with its reason.
  It is not a `custody_stop`, which is reserved for partial or unknown delivery and
  custody fences.

## Human labels and change records

Human-authored evaluation data lives in git-tracked files under `data/evaluation/`. The
evaluator reads them, and nothing writes them at run time.

| File | Content |
| --- | --- |
| `taxonomy.json` | `{version, codes: [{code, name, definition, examples}]}` for failure modes |
| `labels.jsonl` | One label per line: `{id, session, seq_start, seq_end, target, code, verdict, note, author, date, taxonomy_version}`. `target` names an event or record ID, and `verdict` is `confirm`, `reject` or `unsure`. |
| `changes.json` | `[{id, name, arms, commits, hypothesis, target_failure, target_metric: {name, direction, min_effect}, uptake_metric, guards, verdict, notes}]`, where `verdict` is `moved`, `wrong_way`, `no_effect_detected` or `untested` |

Labels enter records as `human` events. A label never changes a derived value; it sits
beside it.

## Spectator view API (`spectator-view/1`)

All routes are `GET`, return JSON with `"schema": "spectator-view/1"` unless noted, stay
under 4 MiB, and write nothing. `<run>` is a session ID. Lists paginate with
`after`/`limit` (`limit` ≤ 500).

| Route | Returns |
| --- | --- |
| `/api/view/runs` | One summary per known run: facts, state (`live` or `final`), outcome (hours, died, `censor_reason`), decisions, dollars, headline metrics, versions. Built by scanning record stores read-only and cached in memory. |
| `/api/view/run/<run>/summary` | Facts; outcome; the Pause conditions (below); game state with provenance; findings; ladder; metrics with `source`, `count`, `denominator`, `missing`; reader coverage with held-out validation status |
| `/api/view/run/<run>/steps?after=&limit=` | Steps: `seq`, `decision`, `wall`, `kind`, `mode`, `game_time`, `source_id`, `frame_changed`, `dollars`, `keys` |
| `/api/view/run/<run>/frame/<source_id>` | The original PNG (`image/png`), only after its SHA-256 matches the record |
| `/api/view/run/<run>/tools` | Per-tool aggregates (calls, p50 and p95 latency, refused, errors, result bytes) and transitions `[from, to, n]` |
| `/api/view/run/<run>/calls?tool=&status=&after=&limit=` | Tool-call rows, each with the step it produced (and its frame) where one exists |
| `/api/view/run/<run>/requests?after=&limit=` | Request rows, plus eviction and handoff markers |
| `/api/view/run/<run>/context/<request_id>` | Ordered parts replayed from the manifest (`exact: true`). Without a manifest: frozen inputs plus recorded tool results (`exact: false`). |
| `/api/view/run/<run>/memory` | Records with kind, chain, cited sources, reads (record IDs returned), handoff carry and human audit labels |
| `/api/view/run/<run>/programs` | Programs with lineage and runs (status, steps, elapsed, reason) |
| `/api/view/run/<run>/handoffs` | Handoffs with position, decisions to resume, carry ratio, carry text and identity check |
| `/api/view/improve/changes` | Change records with per-run target, uptake and guard values for each arm, and bootstrap intervals |
| `/api/view/improve/failures` | Failure modes from derived events and human labels: occurrences, runs, decisions and dollars inside, source |
| `/api/view/compare?group=arm\|start&runs=` | Per group: n, deaths, censored, Kaplan–Meier with Greenwood bounds, median or `not_reached`, restricted mean to the stated horizon with a bootstrap interval, excluded runs, version facts |
| `/api/view/explore?arm=&start=&outcome=&metric=` | Cohort rows; the metric's n, median, IQR and bootstrap interval for the median (n ≥ 5); the 12 decisions before each death |

## Pause conditions (supervise)

The viewer computes these for the live run. They inform the owner and gate nothing.
Each has a value, a threshold, `met`, and the dollars per minute that continuing costs.

| Condition | Met when |
| --- | --- |
| Feed alive | No new operation for 300 s |
| Custody healthy | Any partial or unknown receipt, or a custody stop |
| Not looping | 30 or more decisions without `in_play` while game time does not advance |
| Spend inside allowance | Spend so far, or the one-hour projection, exceeds the manifest's declared ceiling |
| Not dead and still spending | A death event followed by further requests |

Game state (vitals, threat) is information only and never a Pause condition.

**Pause.** The gateway's Pause takes `{"reason": "loop" | "fault" | "spend" | "other"}`.
It forwards `{}` to the custodian unchanged and records the reason in its watch terminal
record. Pause never waits for the viewer.
