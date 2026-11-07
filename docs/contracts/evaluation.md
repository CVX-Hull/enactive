---
owner: lead
review_trigger: A record, metric, reader, health rule or view-API change, or a new game binding
status: active
---

# Run evaluation records, metrics and the spectator view

[ADR008](../decisions/008-evaluation-and-spectator.md) owns the rationale. This page
owns the exact current formats. Every value here is **interpretive**: it is derived
from recorded evidence, carries its source and confidence, and accepts nothing. Frames,
receipts and the issue's decision rule still decide acceptance. No value on this page
reaches the player.

## Inputs

The evaluator reads one run directory read-only:
- `session.sqlite3` (`computer-session/1`);
- `sources/*.png`;
- each `actors/NNN/host.jsonl` (`player-host/3`);
- `manifest.json`;
- the run's `player-memory/2` store.

Open SQLite read-only (`mode=ro`) with a bounded busy timeout. A live run may grow
while it is read. Each pass records the last operation sequence it saw and continues
from there. A missing or unsupported input format is an error naming the file and
version. Nothing is guessed.

## `evaluation-record/1`

One SQLite file per run and version pair:
`.runtime/evaluations/<session>/<core_version>-<binding_id>-<binding_version>.sqlite3`.
An existing file for the same versions is refused unless `--replace` names it.
Re-scoring under new versions writes a new file. Hand-scored evidence elsewhere is
never modified.

| Table | Columns | Meaning |
| --- | --- | --- |
| `metadata` | `key`, `value` | `schema` (`evaluation-record/1`), `core_version`, `binding_id`, `binding_version`, `run`, `session`, input paths with SHA-256 digests, `last_operation_seq`, `created_wall` |
| `steps` | `seq`, `operation_id`, `actor`, `kind`, `wall`, `decision`, `tokens`, `dollars`, `game_time`, `mode`, `source_id`, `frame_sha256`, `frame_changed` | One row per computer operation. The three clocks are wall seconds, agent counters (decision, cumulative tokens and dollars) and nullable game time in the binding's unit. |
| `readings` | `seq`, `reader`, `reader_version`, `value`, `confidence`, `abstain` | One row per reader per step. `abstain` holds a reason, and `value` is then null. Abstention is never counted as zero. |
| `events` | `id`, `seq_start`, `seq_end`, `kind`, `source`, `confidence`, `payload` | Interval or point events (see the event kinds below) |
| `metrics` | `name`, `version`, `value`, `count`, `denominator`, `missing` | One row per metric. `count` and `denominator` are always stored. `missing` names the missing-data rule that applied, or is null. |

**Event envelope.**
- `source` is one of `harness` (a recorded mechanical fact), `reader` (a binding
  reader), `player_claim` (player text or record) or `human`.
- `judge` is reserved for the deferred model judge.
- `confidence` is between 0 and 1, or null for mechanical facts.
- `payload` is JSON. Core field names never contain game words; game detail lives in
  `payload.binding`.

**Core event kinds:**
- `mode_change`;
- `long_activity`: one stretch between consecutive clock readings that advances at
  least the binding's threshold;
- `stall`: an out-of-play streak at or above 15 decisions;
- `stuck_move`: the same movement input three or more times with under 1% map change;
- `vital_change`;
- `threat_change`;
- `milestone`;
- `death`;
- `handoff`;
- `memory_write`;
- `memory_read`;
- `program_save`;
- `program_run`;
- `custody_stop`;
- `continuity`.

## Core quantities and the binding interface

| Quantity | Core meaning | The binding supplies |
| --- | --- | --- |
| `mode` | `in_play`, `menu`, `prompt`, `loading`, `dead`, `unknown` | A mode classifier over a frame |
| `game_time` | Monotonic elapsed time in one unit | A clock reader, its unit, and plausibility guards (no backward step; no single jump beyond the binding maximum unless confirmed by the next reading) |
| `vital` | Normalised 0–1 with direction, critical threshold and scope (`whole` or `part:<id>`) | Readers that map labels or bars to vitals |
| `threat` | Count and bucket (`none`, `low`, `high`, `lethal`) | A threat reader and its bucket rule |
| `milestone` | A rung on an ordered ladder, with first-reached times on all three clocks | The ladder, each rung naming the reader evidence that fires it, or `human` |
| `death` | Cause class: `combat`, `starvation_thirst`, `environment`, `unknown` | A death-screen reader and cause mapping |

The CDDA binding (`harness/evaluation/cdda`) supplies:
- a glyph-atlas sidebar reader for date and time, with multi-day and plausibility guards;
- a main-view mode template;
- need labels: hunger, thirst, fatigue, pain;
- limb bars;
- monster-list ink;
- the death screen;
- a 900-second long-activity threshold;
- the ladder below.

Its readers must pass the held-out accuracy floors before their values feed a metric:
- clock: 98% exact;
- mode: 97%;
- other readers: 95% on non-abstained frames.

**CDDA ladder version 1** (evidence in brackets):

| Rung | Evidence | Rung | Evidence |
| --- | --- | --- | --- |
| In play | reader | Clean or boiled water | human |
| Armed | human | Slept | reader |
| Water obtained | human | Survived first night | reader |
| Drank | reader | Day 2 | reader |
| Food obtained | human | Day 3 | reader |
| Ate | reader | Day 7 | reader |
| Shelter | human | Resupplied | human |

A `human` rung is reported as not assessed until a human or a later reader confirms it.

## Metrics, version 1

Rates are shown with their counts. A metric with fewer than five qualifying intervals
reports `missing: insufficient_intervals`.

| Name | Definition | Denominator | Missing data |
| --- | --- | --- | --- |
| `survival.game_hours` | Last game time minus first in-play game time, in hours, with `died` (death event) or `censored` (alive at stop) | — | No clock reading: null |
| `pace.routine_seconds_per_decision` | Median over consecutive clock-reading pairs below the long-activity threshold of (game time change ÷ decisions between them) | pairs | Fewer than five pairs: missing |
| `pace.long_activities` | Count and total game seconds of `long_activity` events | — | — |
| `pace.dollars_per_game_hour` | Dollars ÷ survival game hours | game hours | Zero hours: null |
| `mode.out_of_play_share` | Decisions with a non-`in_play` mode ÷ decisions with a mode reading | readings | Abstentions excluded and counted |
| `stall.longest` / `stall.count` | Longest out-of-play streak; number of `stall` events | decisions | — |
| `input.actions_per_call` | Actions ÷ input operations | operations | — |
| `input.unseen_action_share` | 1 − returned frames ÷ actions | actions | — |
| `input.frame_unchanged_rate` | Input operations whose capture SHA-256 equals the previous capture's ÷ input operations | operations | No capture: excluded and counted |
| `input.uncertain_deliveries` | Partial or unknown receipts, and runs ended by a custody stop | receipts | — |
| `memory.writes` / `memory.reads` | Append calls; query, read and context calls | — | — |
| `memory.retrieved_beyond_carry` | Records returned by a read that were not in the actor's handoff context ÷ records written | records | No writes: null |
| `memory.late_write_share` | Writes within an actor's last six calls ÷ writes | writes | — |
| `programs.saved` / `run` / `reused` / `outcomes` | Saves; runs; runs by an actor or run other than the author; counts per status | — | — |
| `handoff.decisions_to_resume` | Decisions after a handoff until the first input with three or more actions and a frame change | handoffs | — |
| `handoff.carry_ratio` | Handoff context tokens ÷ predecessor context tokens | handoffs | — |
| `host.dollars_per_decision` | Configured-rate dollars ÷ input operations | operations | Missing usage: counted and excluded |
| `host.cache_write_share` | Cache-write dollars ÷ dollars | dollars | — |
| `host.large_rewrite_share` | Dollars of requests writing more than 30,000 cache tokens ÷ dollars | dollars | — |
| `host.latency` | p50 and p95 of response time and of first-chunk time, nearest rank | requests | — |
| `host.retry_share` | Retries, aborts and non-tool stops ÷ requests | requests | — |
| `needs.severe_share` | In-play decisions with any vital at or past its critical threshold ÷ in-play decisions with vital readings | readings | Abstentions excluded and counted |
| `ladder.reached` | Highest rung reached and decisions to each rung | — | `human` rungs: not assessed |
| `reader.coverage` | Non-abstained readings ÷ frames, per reader | frames | — |
| `lineage.continuity` | Per admission boundary: same survivor and world, and the game-time gap (negative means rewound) | boundaries | Unreadable identity: `unknown` |

**Comparison statistics** (across runs, never within the player):
- Kaplan–Meier survival with Greenwood intervals;
- restricted mean survival to a horizon inside the observed range;
- the log-rank test;
- bootstrap intervals.

Censored runs are kept as censored.

## Spectator view

The viewer serves `spectator-view/1` on loopback. The gateway forwards
`/api/view/*` to it with a 2-second timeout and a 4 MiB response cap. A forwarding
failure returns `503` with `{"viewer": "unavailable"}` and changes nothing else.
Pause, attention checks and their routes never pass through the viewer.

| Route | Returns |
| --- | --- |
| `GET /api/view/runs` | Runs the viewer can show: the live run, and archived runs under the configured roots |
| `GET /api/view/run/<run>/summary` | Health strip, component counters, ladder, alerts, versions |
| `GET /api/view/run/<run>/steps?after=<seq>&limit=<n>` | Step rows with readings and events, `n` ≤ 500 |
| `GET /api/view/run/<run>/frame/<source_id>` | The original PNG, after its SHA-256 matches the record |
| `GET /api/view/lineage/<lineage>` | Admissions in order with carried knowledge and continuity |
| `GET /api/view/compare?runs=<ids>` | Survival curves, run table and version comparison |
| `GET /api/view/stream` | Server-sent events naming the newest sequence; the page then fetches steps |

**Health strip rules.** Each cell reports `ok`, `watch` or `alert`, with its reason
and the step it refers to.

| Cell | Watch | Alert |
| --- | --- | --- |
| Liveness | No new operation for 60 s | 300 s |
| Pace | Routine pace missing after 50 in-play decisions | — |
| Stall | Current out-of-play streak ≥ 15 | ≥ 30, or a `stuck_move` run of 5 |
| Danger (interpretive) | A vital at its critical threshold, or threat `high` | A red limb bar, threat `lethal`, or a death event |
| Spend | Run dollars over 80% of its declared allowance | Over 100% |

Alerts are computed from these rules and events, displayed and never stored. No route
writes anything.
