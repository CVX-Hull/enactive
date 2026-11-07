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

**Routes.** The route list and the health and attention rules are **finalised with the
approved spectator design**. Until then the starting set is:
- `GET /api/view/runs`;
- `GET /api/view/run/<run>/summary`;
- `GET /api/view/run/<run>/steps?after=<seq>&limit=<n ≤ 500>`;
- `GET /api/view/run/<run>/frame/<source_id>`, served only after its SHA-256 matches;
- `GET /api/view/lineage/<lineage>`;
- `GET /api/view/compare?runs=<ids>`.

No route writes anything.
