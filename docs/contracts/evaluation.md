---
owner: lead
review_trigger: A record, metric, reader, health rule or view-API change, or a new game binding
status: active
---

# Run evaluation records, metrics and the spectator view

This page owns the current formats
([evaluation framework proposal (#383)](https://github.com/CVX-Hull/enactive/issues/383)).
[ADR008](../decisions/008-evaluation-and-spectator.md) owns the rationale.

Every value here is **interpretive**. It is derived from recorded evidence, carries its
source and confidence, and accepts nothing. Frames, receipts and the issue's decision
rule still decide acceptance. No value on this page reaches the player.

## Inputs

The evaluator reads one run directory read-only:
- `session.sqlite3` (`computer-session/1`);
- `sources/*.png`;
- each `actors/NNN/host.jsonl` (`player-host/8`), including its per-request context
  manifest;
- the handoff contexts under `contexts/*.json` (`player-handoff-context/2`);
- `manifest.json` (`campaign-run/10`), including its operator labels;
- `receipt.json` (`campaign-receipt/7`, with `player-driver/7`) and
  `watch-terminal.json` (`campaign-watch-terminal/4`), when recorded;
- the run's `player-journal/1` public call and hint store.

Open SQLite read-only (`mode=ro`) with a bounded busy timeout. A missing or unsupported
input format is an error naming the file and version. Nothing is guessed.

**One JSON reader, one host parser.**
- Every JSON document the evaluation side and the viewer read from a run or from
  `data/evaluation/` goes through `records.loads`: a malformed document, a duplicate key or
  a non-finite number is an error naming where it came from. Files go through
  `sources.read_json_file` and `read_json_lines`, which refuse a file over 16 MiB.
  The exceptions are the binding's own `atlas.json` and `anchors.json` (`atlas.py`), which
  ship with the code, and the tool-result text embedded in host events (`context.py`,
  `host.py`), which is probed for JSON and may be anything.
- The viewer reads a run's `manifest.json` only through `sources.read_manifest`, so an
  unsupported version is rejected there too.
- `harness/computer/protocol.py` keeps its own decoder, because the import contracts
  forbid the computer importing evaluation.
- `sources.iter_host` is the one offline parser of `host.jsonl` (`player-host/8`), used by
  the evaluator, the viewer and `host-summary`. The supervisor's live incremental reader in
  `tools/campaign_player.py` stays separate because evaluation never gates the control path
  ([ADR008](../decisions/008-evaluation-and-spectator.md)). `iter_host` is bounded to 64 MiB
  per line and two million lines per trace, skips blank lines, and rejects a trace that is
  empty (or only blank lines), whose first event is not a `host-start`, or whose
  `host-start` is not `player-host/8` telemetry 8. For an [archived run](#implementation-rules),
  the parser also accepts the exact host version and session in its manifest's archive
  entry. An unterminated final line that does not parse is an error for `host-summary`.
  The evaluator and viewer ignore it because a trace may still be appending. A malformed
  line ending in a newline is always an error.

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
- **No overwrite.** A `final` store is never overwritten by a `live` pass and is never
  continued incrementally; only an explicit `evaluate-run --replace` (a `final` pass)
  rewrites it. A `live` pass is refused while a `final` store of the same versions exists,
  and it never erases the final input digests. The viewer then serves the `final` store
  read-only, stops live evaluation and reports that in the summary's `evaluator` status
  (`finished`). Re-scoring under new versions writes a new file. Hand-scored evidence
  elsewhere is never modified.
- **Lineage.** `evaluate-lineage` takes one lineage's admission run directories in order. It
  scores any admission without a `final` store as `evaluate-run` does, then writes
  `continuity` events and the four `lineage.*` metrics (continuity, elapsed time, the day
  check and memory reuse) into every admission's store. Stitching again after re-scoring an
  admission restores them.
- **Current versions.** Core 2 and CDDA binding 2. Core 2 includes the lineage elapsed time,
  day check and memory reuse; binding 2 includes `severe_needs`.

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
- `judge` is a model judge's answer to one closed question. A judge event uses this
  envelope but is never a row of an evaluation record: the `events` table refuses the
  source. It lives in its own file ([judge events](#judge-events-judge-events2)).
- `confidence` is 0–1, or null for mechanical facts.
- `payload` is JSON. Core field names never contain game words; game detail lives in
  `payload.binding`.

**Core event kinds.** Legacy memory and program events are historical evidence;
the current journal supplies public calls and hints, with authored-memory and
program views unavailable for current runs.

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
| severe needs | The lineage day check's failing needs at one step | `severe_needs(values)`: the needs that fail, `[]` when none does, None when the needs are not legible |

**Plausibility guard.** A clock reading earlier than the last accepted one, or later by
more than the binding's maximum jump, abstains with `implausible`. The exception is a
jump the next reading confirms.

**Accuracy floors (a process rule).** Each reader has a held-out validation record in
`data/evaluation/reader-validation.json` with a floor: clock 98% exact, mode 97%, every
other reader 95% on non-abstained frames. The record is shown with every reader's values,
with `pass` of `true` (floor met), `false` (below it) or `null` (unmeasured, with a note).
Values are never hidden. A metric derived from a reader without `pass: true` is labelled
unvalidated: the metric JSON carries `validated` (`true`, `false` or `null` for a metric
that reads no frame reader) and the page shows it next to the provenance chip. At present
`death` (recall unmeasured: no held-out death screen) and `threat` (empty lists only) are
`null`.

**The CDDA binding** (`harness/evaluation/cdda`) supplies:
- a glyph-atlas sidebar reader for date and time;
- a main-view mode template;
- need labels for hunger, thirst, weariness and pain;
- limb bars;
- monster-list ink;
- the death screen;
- identity where legible;
- a 900-second long-activity threshold;
- severe needs for the day check (binding version 2), as defined for the
  [long-horizon study (#382)](https://github.com/CVX-Hull/enactive/issues/382):
  - thirst "very thirsty", "dehydrated" or "parched";
  - hunger "very hungry", "famished", "near starving" or "starving";
  - rest "dead tired" or "exhausted", read from the weariness reader's `rest` field (its
    `label` is the worse of weariness and rest).

  This is narrower than the readers' `critical` flag, which also covers pain, red labels
  and limbs;
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

### How the binding detects a UI change

There is no UI hash check, and no check compares the game's UI with anything. What exists:
- A frame that is not 960×640 abstains: the `mode` reading carries `frame_size` and no
  other reader runs.
- The glyph atlas (`atlas.json`) carries a version and an 8×16 cell size, and loading it
  fails when either differs from the code's. This guards the atlas data against the code,
  not the game UI against the atlas.
- A font change at the same frame and cell size shows as `no_signature`, `label_occluded`
  and `unknown_glyph` abstentions: label and anchor checks fail before most glyphs are
  decoded, and the cells' ink masks are not in the atlas.
- A same-font layout change shows as `label_occluded`, `unknown_label`,
  `clock_not_legible` or `no_signature` abstentions, depending on what moved. It is not
  guaranteed to abstain: the clock reader only lowers its confidence to 0.85 when its
  `Date:` and `Time:` labels are not where it expects but its text still parses.

Abstentions show as lower `reader.coverage`. The atlas is relearned when the game's font,
size or layout changes (this follows the custom-code table in
[ADR008](../decisions/008-evaluation-and-spectator.md), whose correction line points here).

## Metrics, version 1

A **decision** is one completed `computer_input` operation. Rates are shown with their
counts. The pace median built from fewer than five qualifying intervals reports
`missing: insufficient` (the one name for this rule). Every other rate and median carries
its `count` and `denominator`, and the viewer shows an insufficient sample as such.

| Name | Definition | Denominator | Missing data |
| --- | --- | --- | --- |
| `survival.game_hours` | Last accepted game time minus game time at `first_in_play_seq`, in hours, with `died` (death event) or `censored` (alive at stop) | — | No accepted reading: null |
| `pace.routine_seconds_per_decision` | Median, over consecutive accepted clock pairs with at least one decision between them and a gap below the long-activity threshold, of (game-time change ÷ decisions between) | pairs | Fewer than five pairs: missing |
| `pace.long_activities` | Count and total game seconds of `long_activity` events | — | — |
| `pace.dollars_per_game_hour` | Run dollars ÷ survival game hours | game hours | Zero hours: null |
| `mode.out_of_play_share` | Decisions whose mode is not `in_play` ÷ decisions with a non-abstained mode | mode readings | Abstentions excluded and counted |
| `stall.longest` / `stall.count` | Longest streak of decisions without `in_play` (abstentions neither extend nor break a streak); number of `stall` events | decisions | — |
| `input.actions_per_call` | Key, text and click actions in input operations (`wait` actions excluded) ÷ input operations | input operations | — |
| `input.unseen_action_share` | 1 − input operations with a capture ÷ actions in input operations | input actions | — |
| `input.frame_unchanged_rate` | Input operations whose capture SHA-256 equals the previous capture's ÷ input operations with a capture | captured inputs | — |
| `custody.uncertain_receipts` | Partial or unknown receipts ÷ receipts; a run end or custody stop never counts here | receipts | No receipts: null (`no_receipts`) |
| `custody.stopped` | Boolean: whether a custody stop ended the run | — | — |
| `tools.calls` | Calls per tool, with refusals and error results per tool | calls | — |
| `memory.writes` / `memory.reads` | Append calls; query, read and context calls | — | — |
| `memory.retrieved_beyond_carry` | Distinct record IDs returned by any read that were not in the reading actor's handoff context ÷ distinct records written (capped at 1) | records written | No writes: null |
| `memory.late_write_share` | Writes within an actor's last six tool calls ÷ writes | writes | — |
| `programs.saved` / `programs.runs` / `programs.reused` / `programs.outcomes` | Saves; runs; runs by an actor or run other than the author; runs per status | — | — |
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
| `lineage.elapsed` | Game time from admission 1's first in-play clock to the lineage's last accepted reading (a rewind lowers it), with total decisions, overall game seconds per decision (null when elapsed is not positive), long-activity hours and their share of elapsed time (null when elapsed is not positive, and above 1 when a reload undid long activities), and `episode_changes` (a restarted clock or another survivor inside an admission) | game seconds | No accepted reading: missing (`no_game_time`) |
| `lineage.day_check` | The crossing is the first step after the lineage's last reading below one game day from that start, so a rewind below the day undoes an earlier crossing. The needs are scored at the first in-play step from the crossing on whose needs the binding can read, in that admission or a later one (`scored_run`, `lag_hours` past the day). Deaths are compared in lineage order (admission, then step), so a death in an admission a reload later rewound still counts. A death at or before the crossing fails the check (`died_before`). A death after the crossing but before the scored step leaves it unscored (`died_in_lag`). Otherwise `passed` when `severe_needs` reports none. A severe need that was read counts even when another need is unreadable. The metric also reports `severe` and `episode_changes`. The long-horizon study treats an episode change as a continuity failure first. If admission 1 never reaches play, a later admission's first in-play clock is the zero | 1 | Not crossed: `not_reached`; needs never legible after the crossing: `needs_not_legible`; death in the lag: `died_in_lag` |
| `lineage.memory_reuse` | Distinct memory record IDs read in an admission that an earlier admission of the lineage wrote, per admission and in total | records written before the last admission | None written: `no_earlier_writes` |

The four `lineage.*` metrics are written only by `evaluate-lineage` and are the same in every
admission's store. An incremental pass keeps them; a fresh `--replace` pass drops them until
the lineage is stitched again.

**Comparison statistics** (across runs, never within the player):
- Kaplan–Meier survival with Greenwood intervals;
- restricted mean survival to a horizon inside the observed range;
- the log-rank test;
- bootstrap intervals.

Censored runs stay censored.

## Diagnostics owned by this contract

`tools/evaluate.py` also prints two read-only diagnostics. They report recorded intervals and
counts, are interpretive like every value here, and give no verdict. The evaluator reuses
their numbers for latency and delivery counts.

| Command | Output format | Reports |
| --- | --- | --- |
| `host-summary` | `host-analysis/1` | Per `host.jsonl` trace: coverage (`player_host`, `empty`, `unsupported_format`, `unsupported_version` or `invalid`), request attempts and censoring, host time and request share, and distributions (count, sum, p50, p95, max) of response, tool, timing, usage and context figures. Per trace, per run directory and for the whole selection, `response_by_prompt`: response time (count, p50, p95), the share within 2 s and within 5 s and the mean provider-reported cost per request, for all responses and by prompt-size band (input plus cache read plus cache write tokens: under 20,000; 20,000 to 60,000; 60,000 to 100,000; 100,000 to 150,000; over 150,000), and the interval from one request's first tool result to the next. `prompt_composition`: per trace one object, per run directory and for the whole selection a list with one object per route (the host's `model`). It says what the prompt is made of, fitted by least squares on the growth in prompt tokens between consecutive requests of an actor against what was added, from the provider's reported `usage` and the trace's own sizes alone, so it holds for any model that reports usage. An object has `pairs` (fitted), `left_out`, `image_counts` (histogram of images per fitted pair), `image_term_separable`, `images_per_turn`, `usage_fit`, `usage_fit_reason` and `tokenizer_check`. `usage_fit` has `per_result_byte` (tokens per byte of tool-result text: the `content` text the model reads, in the short form or the full one, never `structuredContent`), `per_output_token` (per output token of the previous reply, reasoning included), `per_image`, `per_turn_constant`, `per_turn_at_modal_images`, `residual_abs` (p50, p95, share within 5 tokens) and `pairs`. Every eligible pair is fitted; the image count is a term of the fit whenever it varies, so a turn with another count has its own intercept and does not bend the byte slope. `per_image` and `per_turn_constant` are numbers only when at least 10% of the fitted pairs have a count other than the most common one (`image_term_separable` true). Otherwise (`image_term_separable` false) they are null, because the image term cannot be told from the constant, and the supported figure is `per_turn_at_modal_images`, the constant plus `images_per_turn` (the most common count) images; it is null when they are separable. `left_out` counts the pairs not fitted, by `usage_unknown` (a prompt size or the reply's output is unknown), `projection_unknown` (only one of the two requests has an image projection event), `images_dropped` (the host dropped images between the two requests), `notice_added` (a `tail-notice` or delivered knowledge reminder on the second) and `not_one_call` (the reply did not make exactly one call with one result). `usage_fit` is null, with `usage_fit_reason`, when there are no more pairs than terms or the terms are not independent (for example every result has the same length). A tokenizer is only an optional check: `python -m tools.host_analysis PATH... --tokenizer [ROUTE=]ENCODING` (or `host_summary(paths, tokenizers)`) fills `tokenizer_check`, otherwise null; it fits the growth on that tokenizer's count of the result text, the reply's visible output tokens and its reasoning tokens (with the same image treatment) and reports `slope` (`per_result_token`) and `holds`: the slope is within 1 ± 0.01 and the median absolute residual is at most 1 token (this reader's stated limit; the recorded medians for `o200k_base` were 0.2 and 0.1). A tokenizer that is not installed, cannot be loaded or whose counting function raises gives `available: false` and a `reason`, and a degenerate fit gives a `reason` and no `slope`; the usage fit is unaffected. The command exits 2 when a `ROUTE` names no selected trace. `--format markdown` prints the tables. |
| `control-summary` | `control-analysis/1` | Per `computer-session/1` database: original native dispositions and the timing distributions between intent, send and receipt. |
| `python -m tools.memory_measure` | files under `.runtime/memory-measure/<run>/`; text, or `--json` | The memory measure. `packets use` and `packets blind` build packets for model judges from sealed admissions and a `judged-facts/1` file, cut to a token budget; `events` validates a judge's answers into `judge-events/2`; `agreement` adjudicates two judges with a third on disputes; `measure` reports the standing use measures (`memory-use/1`). `packets annotate` and `items` build a matched list of facts two annotators saw. `anchor packets`, `anchor events` and `anchor report` re-judge the measure gate's owner-labelled pairs with its frozen prompt; `prompt-check packets` and `prompt-check report` compare the first two judges' agreement on frozen stretches before and after a prompt change. `simulate-withholding` sizes and prices withholding within each start (`withholding-simulation/1`); `pilot` writes the withholding pilot's unit-level analysis (`withholding-pilot/1`). It calls no model and spends nothing; see [judge events](#judge-events-judge-events2). |
| `python -m tools.process_measures` | files under `.runtime/memory-measure/<run>/`; text, or `--json` | The game-neutral process measures: `milestones packets` and `milestones events` freeze each admission's milestones; `packets`, `events`, `agreement` and `measure` judge windows and report `process-measures/2`. It calls no model and spends nothing; see [process measures](#process-measures-process-measures2). |
| `python -m tools.memory_reads` | text, or `--json` | For sealed historical traces, per memory read (`player_memory_query`, `player_memory_read`, `player_memory_context`) in `player-host` traces: the records returned, whether the reading actor already held each, each record's age, and the actor's calls before and after, with later calls that type a record's words, fetch a source it cites or name it marked as references. It lists and counts; it does not judge use. |
| `python -m tools.memory_screen_checks` | text, or `--json`; `schedule` writes `curator-coverage-schedule/1` | Four subcommands for the [context design](../design/player-context.md). `store`: every published version of a curator knowledge repository, read from the repository's loose objects without a Git process: its session, its facts and articles (all and current) and bytes, and the facts whose text matches a pattern. It reads `curator-knowledge/2` repositories of `curator-fact/3` records only and refuses any other, so the sealed stores of the memory screen's gates are not read. `replay`: for a known loss, the request that returned the frame at which play needed the fact, when the player's record was written, and when a briefing or a snapshot difference would first have shown it. `cut`: a simulation of the design's cut over the recorded request sequences for assumed curator lags, with tokens per turn and the marks as options; `--coverage` is `steady`, `sessions` or `schedule`, and `--coverage schedule --schedule FILE` replays one run's recorded covered prefix in place of the lag rows ([replaying a recorded schedule](../design/live-curator-integration.md#replaying-a-recorded-schedule)). Its `recorded` row is from the traces; every other row is simulated, not measured. `schedule RUN [--output FILE]` (a FILE outside RUN): that run's covered prefix from `curator-runner/polls.jsonl` and the final `status.json`, as a schedule. |

**Percentiles.** There is one definition, nearest rank (`metrics.nearest_rank`): the
`ceil(q·n)`-th smallest value, and the smallest value when that rank is 0. Every `p50` and
`p95` uses it: the `host.latency` metric, the viewer's tool latencies, and the distributions
of both diagnostics. A metric named a median (the pace and handoff rows) is the arithmetic
median, the mean of the middle pair for an even count. The viewer's explore cohort median,
IQR and bootstrap intervals are not percentiles of this kind: they use numpy's defaults.
`host-summary` and `control-summary` `p50` values use the lower middle value on an even count.

## Control path and viewer

**Control path.** The supervised gateway (`tools/campaign_watch.py`) keeps:
- Pause;
- the page origin and static files;
- the frame and status that the control strip shows.

The control strip reads those only from the custodian's `/api/status` and
`/api/source/<id>` routes: session, freshness line, source details and frame. A viewer
outage therefore cannot block the strip, a Pause or a run.

**Viewer.** The viewer is a separate read-only loopback process. The gateway forwards
`/api/view/*` to it under these rules:
- 2-second socket timeout for the request and headers, then a body deadline measured
  2 seconds from forwarding start, with a 4 MiB body cap;
- at most eight forwards at once;
- only `application/json` and `image/png` responses, never HTML or script;
- the viewer's `200`, `400`, `404`, `409` and `413` pass through unchanged, and any other
  status is a forwarding failure;
- the gateway's own security headers on every response.

A viewer response with a disallowed media type, invalid `Content-Length` or body over
the size cap returns `502` with `{"error": "Viewer response refused"}`. A refused
connection, timeout, unlisted viewer status or unavailable forwarding slot returns
`503` with `{"viewer": "unavailable"}`. The page polls and treats both as “viewer unavailable”.

**Launch and lifetime.**
- The supervisor starts `python -m harness.viewer` as an **unsupervised** child on a free
  loopback port with the live run directory and evaluation root (`.runtime/evaluations`).
  It can also pass archived run directories, labelled curator result and session files,
  and the configured runner's status file.
- A launch failure or exit leaves the run running. The supervisor stops the viewer at
  the end and records its port in `campaign-watch-start/4` and its child entry in
  `campaign-watch-terminal/4`.
- The viewer evaluates the live run incrementally and writes only its `live` evaluation store.

## Further record contents (`evaluation-record/1`)

| Table | Columns | Meaning |
| --- | --- | --- |
| `run_facts` | `key`, `value` | From `manifest.json` and frozen inputs: `labels` (arm, start, scenario, lineage, admission), `source_commit`, model id, effort, route, guide and assignment SHA-256 digests, limits, and the spend allowance (`spend_allowance_usd`; `declared_ceiling_usd` and `prior_reserved_usd` are filled for an archived run only, see "Spend allowance" below) |
| `tool_calls` | `request_id`, `tool_call_id`, `actor`, `decision`, `tool`, `status` (`ok`, `error`, `refused`), `latency_ms`, `result_bytes`, `wall` | One row per tool call, from host `tool-start`, `tool-result` and `tool-refused` |
| `requests` | `request_id`, `actor`, `wall`, `attempt`, `input_tokens`, `cache_read`, `cache_write`, `output_tokens`, `dollars`, `retry_class`, `omitted_images`, `manifest` | One row per HTTP attempt. `manifest` is `exact` when a `context-manifest` event exists, else `absent`. |

`metrics` also has a `key` column for multi-valued metrics, such as per reader, per
percentile, per status or per handoff. The primary key is (`name`, `key`).

**Also in the record:**
- `source` also takes `derived`, for values computed from other records.
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

### Implementation rules

- **Archived runs.** The evaluator reads older records only for a session and exact
  manifest and record versions listed in the [closed archive index](../../data/evaluation/archive-sessions.json)
  (`archive-sessions/1`), under [S-MIGRATION's closed-archive rule](../standards/migration.md#s-migration-one-current-contract-coordinated-migration).
  The index includes `spend-limit-run-555` under the
  [“Add it to the index” decision](../decisions/owner-decisions-archive.md#index-the-spend-limit-check). The
  indexed session `522-held-out/computer-sessions/lh4a1` does not evaluate: its database
  cannot be opened in the read-only store, evaluating it is an error, and the sealed copy
  stays as it is ([“Record it as a limit” decision](../decisions/owner-decisions-archive.md#record-the-unreadable-archive-session-as-a-limit)).
- **Metadata key.** `metadata.last_seq` names the last operation read.
- **Store replacement.** A `live` store is replaced by any later `final` pass. A `final`
  store needs an explicit replace and is never replaced or continued by a `live` pass.
  An incremental pass (`after_seq`) continues only a `live` record.
- **`tool_calls` table.** It also stores `operation_id`, linking a call to the step it produced.
- **Long-form metric keys:**
  - `reader.coverage` per reader;
  - `host.latency` with keys `response.p50`, `response.p95`, `first_chunk.p50` and `first_chunk.p95`;
  - `programs.outcomes` per status;
  - `tools.calls` per tool, plus `player_source+zoom`;
  - `memory.records` per kind;
  - `handoff.*` as one summary row plus one row per handoff.
- **Run-loss metrics.** `run.infrastructure_loss` covers infrastructure or custody loss;
  `run.provider_loss` covers provider-error loss only.
- **Censor reasons.** The first matching reason applies, in this order:
  1. `died`;
  2. `owner_pause` (the watch terminal record's `reason` is `operator_pause`, with
     `pause_reason` when recorded);
  3. `custody`;
  4. `infrastructure` (the last actor settled not ok);
  5. `player_stop`;
  6. `budget`.
- **Episodes.**
  - A new episode starts when game time moves back by more than one day, or identity
    changes, and the next reading confirms it.
  - Survival uses the last episode that has an in-play clock reading.
  - A death counts if it falls in or after that episode.
- **Derived events.** `stall`, `ineffective_repeat`, `long_activity`, `episode` and
  `continuity` have source `derived`.
- **Spend allowance** (`run_facts.spend_allowance_usd`) is the manifest's declared
  dollar limit, `spend_limit_usd`. For an archived run that declares a reservation,
  the allowance is `declared_ceiling_usd` minus `prior_reserved_usd` as recorded in
  `run_facts`. Both reservation fields are null for a run that declares a limit.
  The spend rate uses the last ten minutes of requests.
- **Dollars** in the record (`requests.dollars`, the cumulative dollars of a step and
  the cost metrics) are the configured-rate estimate of each response,
  `usage.cost.total`: the one figure every run, archived or not, carries. The cost the
  provider reported, which the host counts toward the limit, is not in the record; the
  run's receipt holds it.
- **Change baselines.** A change record may name `baseline` arms or run patterns to compare against.
- **View request rules:**
  - A `limit` outside 1–500 returns `400`.
  - The context route accepts `?actor=` and returns `409` when a request ID is ambiguous across actors.
  - The compare route accepts `horizon` in game hours, default 0.5.
  - Runs resolve by session ID or run directory name.

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

## Judge events (`judge-events/2`)

A judge event is one model judge's answer to one closed question about recorded play.
The lead starts the judges. `python -m tools.memory_measure` builds what they read and
counts what they answer without calling a model. `harness/evaluation/core/judge.py`
validates the format. See the [memory measurement work (#386)](https://github.com/CVX-Hull/enactive/issues/386)
and [measurement design](../design/world-scoped-memory.md#3-measurement).

- **File.** JSON Lines, one event per line, one judge and one kind per file, written once
  and never replaced. Each pair appears at most once. Use verdicts are in
  `.runtime/memory-measure/<run>/events/<judge>.jsonl`; anchor verdicts in
  `.runtime/memory-measure/<run>/anchor/events/<judge>.jsonl`.
- **Envelope.** Exactly `schema` (`judge-events/2`), `kind`, `source` (`judge`),
  `confidence` (always null: agreement is measured over the file) and `payload`.

**`fact_use_verdict`**: one judge's label for one fact over one window.

| Payload field | Meaning |
| --- | --- |
| `window` | `<admission>/<actor>:<first decision>-<last decision>`: a stretch of one actor's decisions, never a single step |
| `fact` | The fact's id in the facts file |
| `route` | How the fact reached the player: `lead` (its article's lead was delivered), `read` (the player read it through a link or a search), `index` (only on the index) or `withheld` (the benefit measure). The tool sets it from the facts file; a judge's answer cannot |
| `label` | `in_line` (acted in line with it), `against` (acted against it), `found_again` (looked it up: an action spent only to learn what the fact says), `did_not_apply` or `cannot_tell` |
| `holds` | Whether the frames show the fact still holding: `held`, `stale_or_false` or `cannot_tell` |
| `cited_frames` | Source IDs of the frames the judge cited. `in_line`, `against` and `found_again` cite at least one |
| `judge`, `model` | The judge's name and the model the lead pinned for it |
| `packet`, `packet_sha256` | The shuffled name of the packet the judge was given and the SHA-256 of its manifest, which lists every file's hash |

**`anchor_verdict`**: the measure gate's frozen question, used only by the anchor check.
Payload: `start` (`<admission>:<first>-<last>`), `item`, `label` (`straight`, `missed`,
`not_engaged`, `cannot_tell`; the first two cite a frame), `cited_frames`, `judge`, `model`,
`packet`, `packet_sha256`.

### The facts to judge (`judged-facts/1`)

Facts come from the store and the trace, not from a list written in advance. `python -m tools.memory_measure facts RUN --runs PACKAGE...` builds `RUN/judged-facts.json` from the frozen delivered/full knowledge, private unit record, knowledge-tool results and delivery telemetry. It verifies the frozen knowledge hashes and the exporter's unit rule: a unit's fact list is exclusive, and `private/units.json.shared` records multiply cited facts with their citing article IDs; any delivered citing article delivers the shared fact; the player never sees the private inputs.

    {"schema": "judged-facts/1",
     "admissions": {"<admission directory name>": {"<actor directory name>": {
       "lead": [{"id": "...", "text": "...", "from_decision": 40}],
       "read": [...], "index": [...], "withheld": [...],
       "briefing": "the briefing as delivered",
       "reminders": [{"decision": 40, "text": "..."}]}}}}

- A fact has one route for an actor; an id listed twice is refused.
- The route is the first lead or read exposure in time, with `index` only if neither occurs. Withheld facts come from `private/units.json`.
- `from_decision` is optional: the last player decision completed before that same exposure; briefing leads and index lines have none. Recall requests have `decision: null` and never advance this numbering. Cumulative player-decision cost includes recall only with the next player request, so a successor's briefing is never charged to the preceding actor. Player latency and retry-share denominators exclude recall. A delivered reminder is a notice when fitting prompt-composition pairs. Its `available_from` frame is the first kept frame whose carried
  inputs all come from decisions strictly after it; a use packet leaves the fact out of
  windows with no such frame, and an applied label (`in_line`, `against`, `found_again`)
  must cite a frame from there on, or `events` refuses it, so an action before or during a
  read or a reminder cannot count as using it. A fact with no such frame in any window is
  listed under `not_shown` (actor and fact) in the mapping and the report.
- `briefing` and `reminders` are optional and are shown only in use packets.
- An actor without an entry is not judged. Any other version or key is refused.

### Packets

`packets use` and `packets blind` write one packet per window and group of facts under
`judge-packets/<shuffled name>/`, and `private/judge-mapping.json` (`judge-mapping/2`),
which maps each shuffled name to its admission, actor, decisions, source IDs and each
fact's route and is never given to a judge. A run directory holds one kind.

- **Token budget.** Windows are cut so that everything a judge reads stays within the
  budget (`--budget`, default 60,000 estimated tokens), evened toward an average packet
  across the windows of an actor where decisions allow, each priced with its real bounds;
  cuts fall between decisions and within one actor. An image
  is estimated at width × height / 750 tokens after a long edge over 1568 px is scaled
  down to it, text at one token per three characters, counted on the files as written.
  The manifest (`judge-packet/2`) records `budget: {tokens, estimated: {images, text,
  total}, over}`; `over` is true when a written packet passes the budget, which a single
  decision larger than the budget can. Facts are split over several packets of the same
  window when they would take more than half of what the briefing, reminders and
  instructions leave; when those leave less than a quarter of the budget, the tool refuses.
- A run's frames are the sources its calls returned whose id carries the run's own
  session (`<session>-<n>`, the session in its `manifest.json`); each must have its file
  under `sources/`. A source of another session, such as an earlier lineage's screenshot
  the player opened with `player_source` from its inherited store, is not a frame of the
  run and is skipped.
- An actor with facts but no kept frame is listed under `no_frames` in the mapping and
  the report.
- **Use packets** hold `manifest.json`, `instructions.md`, `facts.json` (id, text, route,
  and `available_from` where the fact arrived during play),
  `delivered.json` (the briefing and the reminders up to the window's end) and `frames/`;
  a frame's row may carry `stated_before`, the `intent` and `cites` of the player's calls
  since the previous frame. Withheld facts are left out.
- **Blind packets**, for the benefit measure, hold `manifest.json`, `instructions.md`,
  `facts.json` (text under an opaque id drawn per packet, in an order and grouping that do
  not depend on the route) and `frames/`: frames and inputs only. The briefing, the
  reminders, `intent`, `cites`, the route, the facts' own ids and decision numbers are
  absent (frames are numbered by position, so a gap cannot show a memory read), and every
  fact of the actor is in every window, so a judge cannot tell a delivered fact from a
  withheld one. The mapping translates the opaque ids back.
- Frames and directories carry shuffled names; a packet holds no admission name, source
  ID, player record or report. The held-out lineage's evidence is refused.
- **Annotators.** `packets annotate` cuts frames to the same budget for two annotators,
  who list every fact the frames show a later player could use (`{fact, frames}`); `items`
  joins their lists by the lead's matches into `annotated-facts.json`
  (`annotated-facts/1`), frozen with its hash. An entry only one annotator listed is left out.

### Adjudication and the standing use measures

`agreement` writes `adjudicated.json` (`judge-adjudicated/2`): per pair the label both of
the first two judges gave, else the third judge's (`by`: `agreement`, `third`, or
`third_alone` when the third gave a label neither did); `holds` is the value both gave,
else the third's when it sides with one of them, else `cannot_tell`. A pair on which the
first two differ in the label or in `holds` needs a third judge. It reports the first two
judges' agreement, Cohen's κ and the dispute rate, for the label and for `holds`
separately, and the packets a third judge must answer.

Every answer import (`events`, `anchor events`) and `prompt-check report` checks each
file of the packet against its manifest, and refuses a packet with an unlisted or changed
file.

`measure` writes `measure.json` (`memory-use/1`) from the adjudicated labels of a run of
use packets:

| Measure | Definition |
| --- | --- |
| `use_rate_delivered` | Of the windows in which a fact whose lead was delivered applied (`in_line`, `against` or `found_again`), the share labelled `in_line` |
| `rediscovery` | Of the same windows, the share labelled `found_again` |
| `stale_or_false_acted` | Of the windows in which the player acted in line with a fact it had (lead, read or index), the share whose `holds` is `stale_or_false` |
| `read_then_in_line` | Of the facts the player read through a link or a search, the share it acted in line with in some window; the denominator is how many it read |

- Each rate carries, beside it, the first two judges' agreement, κ and dispute rate
  (`stale_or_false_acted` on `holds`, the others on the label) twice: over every pair of
  its routes (`judges_route`), and over the pairs that drive it (`judges_rate_pairs`:
  either of the first two judges gave an applied label, or for the stale rate `in_line`),
  chosen before adjudication so the set does not depend on the outcome. Easy agreement on
  "did not apply" lifts the first; the second is the health signal. Each rate has a 95%
  interval from a cluster bootstrap over starts (admissions); one start gives none.
- The report's `not_corrected` field states that the rates rest on adjudicated model-judge
  labels and are not corrected against a human truth
  ([owner decisions](../decisions/owner-decisions.md)).
- A run of blind packets gets label counts by route and the judges' agreement only.
- `recall` records precision and silence when the facts builder recorded recall inputs (`private/recall.json`); older judge runs report `recorded:false`. Precision is the applied share (`in_line`, `against`, `found_again`) of judged fact windows after an actually delivered recall selection, excluding `cannot_tell`. A selection counts even if the fact's first route was an earlier read. Silence is explicit empty reminder selections divided by successful reminder selections; failures and opportunities not made are reported separately. A reminder still unsent at actor end contributes no precision exposure.

### Checks of a changed judge

- **Anchor, when a judge's model changes.** `anchor packets RUN --gate GATE` (the gate
  is the sealed `.runtime/evidence/memory-screen-gates-460-386/memory-measure`) copies,
  unchanged, the measure gate's judge packets that hold one of its owner-labelled pairs
  into `RUN/anchor/packets/`, after checking every file against the hashes the gate
  recorded and every `instructions.md` against the frozen prompt's SHA-256
  (`14c7d593…6af24`, also pinned by a test), and every gate file it reads (the mapping,
  `labels.json`, `adjudicated.json` and the packets) against the sealed evidence manifest
  `data/evidence/memory-screen-gates-460-386.sha256`, so a gate rewritten consistently
  with its own mapping is still refused. `anchor events` rechecks the frozen prompt. The
  gate is only read; `--dry-run` writes nothing. `private/anchor.json` (`anchor-set/1`) holds the pairs with the owner's blind
  and checked labels (read from the gate's `labels.json`, `owner-labels/2`) and the gate
  judges' labels. `anchor events` writes the new judge's `anchor_verdict` events;
  `anchor report` writes `anchor/report-<judge>.json` (`anchor-report/1`): the new judge's
  matches with the owner's blind and checked labels, over all pairs and over the random
  draw, with exact intervals, beside the same figures for each gate judge and the gate's
  adjudicated label, the shift (new minus adjudicated, in pairs), and agreement and κ
  with the gate's labels over every re-judged pair.
- **Prompt change.** The frozen set is a judged run's packets: its mapping records for
  each packet a `stretch_sha256` over the manifest without the instructions' hash and the
  token estimate. `prompt-check packets RUN --before BEFORE` rebuilds the same windows,
  frames, inputs, facts and names with the tool's current instructions, after checking
  every file of `BEFORE`. `prompt-check report RUN --before BEFORE --judges A B` writes
  `prompt-check.json` (`prompt-check/1`): the first two judges' agreement, κ and dispute
  rate before and after, the difference with an interval over starts, the share of its
  own labels each judge changed, and each judge's model on both sides; it refuses a run
  whose models differ, so a model change is not credited to the prompt. Each event file
  holds one model.

### Withholding simulation (`withholding-simulation/1`)

`simulate-withholding` sizes the benefit measure before any play. Per start: a Poisson
number of touched units; each withheld with probability one half; a start-level miss
probability, Beta with the given mean and intra-start correlation (default 0.2); a
withheld unit missed with it and a delivered one with `ratio` times it; each label flipped
by the judge with the given probability. The statistic is missed withheld minus missed
delivered, pooled over starts; the test is the one-sided randomization test that re-draws
delivery within each start, computed exactly (given M missed units, the number withheld is
Binomial(M, 1/2)) at 0.05. For each case (the point values at each judge error, each input
at each end of its interval, and both corners) it reports the smallest number of starts
from 2 to 60 that detects a halving with probability 0.8, the chance of detecting a cut of
one third and the false-alarm rate at that size, and the price: play per start, the same
with the recall model's inferred overhead (×1.67 and ×2.0), and once a store (about \$23)
and one grooming session (\$1.16 to \$4.19). The defaults are the measure gate's numbers.
The [simulation's input record](../acceptance/2026-11-13-withholding-simulation.md#inputs-and-their-intervals)
attributes the one-time price inputs to the brief gate and session price pilot.
It is seeded (each rate has its own stream), prints JSON or a table, and writes no file.
It sizes the measure under the model's assumptions; it does not calibrate real-game power.
`simulate-withholding --pilot REPORT` takes its inputs from a pilot report (below) in place
of the gate's numbers and refuses a flag for any of them (`--touched`, `--touched-ends`,
`--missed`, `--missed-ends`, `--wrong`, `--base-wrong`, `--rho`). It requires `--price`, the
pilot's own dollars per start (play and recall) from its record; the search settings stay
flags.

### The withholding pilot's analysis (`withholding-pilot/1`)

`pilot RUN --runs PACKAGE...` reads a judged run of blind packets over the pilot's starts
and writes `RUN/pilot.json` ([unit-level pilot analysis (#638)](https://github.com/CVX-Hull/enactive/issues/638)).
The [withholding pilot (#619)](https://github.com/CVX-Hull/enactive/issues/619) freezes
this rule before its first start. A change to the rule requires a new version.

- **Inputs.** The run's `adjudicated.json` (`judge-adjudicated/2`, every pair resolved),
  `private/judge-mapping.json` and `judged-facts.json`, and each package's
  `private/units.json` (`knowledge-units/1` with a recorded seed). A start is one package,
  over all its actors and windows. Each start's draw has its own seed, so the arms of
  different starts are independent, as the pooled test assumes. It refuses a run of use
  packets, a package whose unit record has no seed or does not match its manifest, a seed
  repeated across packages, and a judged fact that is in no unit and not shared.
- **A fact's outcome in a start.** The fact is **touched** when any of its windows in that
  start has an applied adjudicated label (`in_line`, `against` or `found_again`); otherwise
  it is untouched, whatever its `did_not_apply` and `cannot_tell` windows. A touched fact is
  **missed** when any of its windows is labelled `against` or `found_again`: the player
  acted against it or had to find it again, so it did not have the fact when it mattered.
  A touched fact whose applied labels are all `in_line` is **straight**. `holds` does not
  enter the outcome.
- **A unit's outcome.** A unit (an article with the facts only it cites, or a fact no
  article files) is touched when any of its facts is touched, and missed when any touched
  fact of it is missed. Its arm is its draw in `private/units.json`: withheld or delivered.
- **Shared facts** (cited by more than one article) are not drawn on their own, so they
  stay out of the units and the test. Their touched and missed counts are reported apart,
  as delivered when any citing article was delivered.
- **Estimates**, each with a 95% interval from a cluster bootstrap over starts (seed 619
  unless `--seed` is given, so the simulation's interval ends are fixed with the rule; a
  draw in which an estimate is undefined is left out of its interval):
  - `touched_per_start`: touched units per start, its mean and the counts per start, and
    the ratio of its variance to its mean (1 for a Poisson count);
  - `missed_share`: missed over touched units, pooled, and per arm;
  - `spread`: the intra-start correlation of the unit-level missed outcome (the one-way
    analysis-of-variance estimator for a binary outcome, truncated at 0);
  - `judges`: the first two judges' agreement, Cohen's κ and dispute rate on the label,
    over all pairs and over the pairs driving the outcome (either of the first two gave an
    applied label), as `measure` reports them; and the per-judge error they imply for the
    simulation, `wrong = (1 − √(1 − 2d)) / 2`, where `d` is the share of driving pairs on
    which the first two judges disagree about the missed outcome itself (one gave
    `against` or `found_again` and the other did not), since the simulation flips that
    binary outcome (two judges each wrong independently with probability `wrong` disagree
    with probability `2·wrong·(1 − wrong)`). The measured missed share already carries
    judge noise, so applying `wrong` on top errs toward more starts.
- **The comparison, descriptive only.** Per start and pooled: touched and missed units by
  arm, the statistic missed withheld minus missed delivered, and the one-sided
  randomization p-value of the simulation's test (given a start's `M` missed units, the
  number withheld is Binomial(`M`, 1/2); independent draws pool to Binomial of the summed
  `M`). The report's `not_a_claim` field states that the pilot's starts, however many were
  analysed, make no claim of benefit, and `not_corrected` that the outcome rests on
  adjudicated model-judge labels.
- **Secondary counts.** Touched units missed only by `against`, only by `found_again`, and
  by both, per arm; touched units with an applied window whose `holds` is
  `stale_or_false`; actors listed under `no_frames`.
- **Threats** stated in the report: every start copies one saved game, about four game
  minutes before the lineage's recorded death; one lineage of one game; the number of
  starts analysed; and that the spread pools both arms, so an effect of delivery that
  differs between starts can show as spread.
- **The simulation inputs.** `simulation` holds `touched` (mean and interval ends),
  `missed` (the withheld arm's missed share and its ends, the simulation's "missed when
  withheld"), `rho` (the spread's point value) and `wrong` (the point value, used as the
  judge error at the interval ends too), in the form `simulate-withholding --pilot` reads.

### The withholding study's design (`withholding-study-draw/1`)

A withholding study fixes one draw for all starts before play, under the
[withholding measure revision (#653)](https://github.com/CVX-Hull/enactive/issues/653).
Each unit is its own comparison, withheld in half of each block's starts and delivered
in the other half, with odd counts rounded as described below.

- `knowledge_export draw-study REPOSITORY --version V --starts N --blocks LABEL:COUNT...
  --seed S [--placebo UNIT_ID...] --out FILE` writes the draw: the store version, the unit
  layout (units and shared facts, as the [unit rule](../design/player-context.md) builds
  it), the seed, the starts in order (index `0`…`N−1`, each with its block), the blocks,
  the placebo unit IDs, and per unit and block the half size and the withheld start
  indices.
- **Blocks** are the saved moments the starts copy: a block's label names the source
  study (`starts create --from`), and the counts, each at least 2, sum to `N`. Within each block, each unit
  takes its own random permutation that withholds it in exactly half of the block's
  starts; for an odd count a fair coin per unit sets the half to the floor or the ceiling,
  and the draw records it.
- **Placebo units** are units of the store's own layout, true facts that cannot matter in
  the study's saved moments, named before the draw. They are drawn like any unit and
  analysed apart; no fact is invented for them.
- A reader rebuilds the draw from its seed and refuses a file that differs, repeated or
  unknown placebo IDs, a block of fewer than 2 starts, or blocks that do not sum to `N`. The rebuild uses numpy's
  generator, whose stream is reproducible only under the pinned numpy, so the pin does not
  change while a study's draw is in use.
- A block's label is asserted, not checked: the analysis checks each package's block
  against the draw but not which saved moment the start copied. The study's record lists
  each start's source study and start manifest hash.
- `--study-draw FILE --start-index I` exports start `I`'s package. Its
  `private/units.json` is `knowledge-units/2`: the `knowledge-units/1` fields with the
  draw's seed, plus `draw_sha256`, `start_index`, `block` and each unit's `placebo`. The
  facts builder, `study` and `study-inputs` read `knowledge-units/1` (the sealed pilot's
  packages) and `knowledge-units/2`; the pilot analysis reads only `knowledge-units/1`.
  Any other version is refused.

### The withholding study's analysis (`withholding-study/1`)

`study RUN --runs PACKAGE... --draw FILE [--seed N] [--draws N] [--json]` reads a judged
run of blind packets over the study's starts and writes `RUN/study.json`. The rule is
fixed before any start of a study is played. A change to it requires a new version.

- **Inputs** are the pilot's, with every package's units record as `knowledge-units/2`
  carrying this draw's hash, version, seed and block, and the arms the draw gives. It
  refuses a run of use packets, a repeated or missing start index, and a package whose
  units or arms differ from the draw.
- **Outcome.** Touched and missed per unit and start as in the
  [pilot's rule](#the-withholding-pilots-analysis-withholding-pilot1), under the judge
  instructions' decision rules: a miss is `against`, or `found_again` for an active
  lookup; information the player saw on a screen opened for another purpose, or in a
  message the game showed on its own, is not a miss. Shared facts are reported apart, as
  in the pilot.
- **Primary.** Over non-placebo units touched at least once in each arm: the mean over
  units of the unit's missed share when withheld minus its missed share when delivered,
  each over the starts where it was touched. The test is one-sided (withheld misses
  more): a Monte Carlo randomization test that re-draws the assignment as the draw makes
  it (per unit and block, a fresh permutation with the recorded half sizes), with the
  outcomes fixed and the eligible units recomputed on every re-draw; a re-draw with no
  eligible unit scores 0. `p = (1 + re-draws at or above the observed) / (1 + draws)`,
  10,000 draws and seed 653 unless given. It reports the value, the units counted, and
  the units excluded as never touched or touched in one arm only.
- **Intention to treat.** The same statistic and test over every non-placebo unit, with
  missed per unit and start and an untouched unit counted as not missed.
- **Touch balance.** Over non-placebo units, the touched share per arm, and the same test, two-sided, on touched:
  withholding must not change what the player gets to.
- **Placebo.** The primary statistic and test over placebo units only. Delivery of facts
  that cannot matter should show no effect; one would point to a bias in the judges or
  the outcome.
- **Secondary, a crossed mixed model.** On touched non-placebo (unit, start) rows, statsmodels'
  `BinomialBayesMixedGLM` (variational fit): missed on withheld, with variance components
  for unit, start, and a withheld-by-unit slope. It reports the withheld coefficient's
  posterior mean and SD and each component's (log SD and implied variance). A failed or
  non-converged fit is reported as `failed` with its reason, and the rest of the report
  stands.
- **Judges.** As in the pilot, the first two judges' agreement, κ and dispute rate over
  all pairs and over driving pairs, with a start-bootstrap interval on agreement, and on
  the binary missed outcome (`against` or `found_again` against any other label) the 2×2
  table of the two judges' answers, positive and negative specific agreement and Gwet's AC1. κ falls when
  misses are rare even with high agreement; the specific agreements and AC1 show which
  side the disagreement is on.
- `not_corrected` states that the outcome rests on adjudicated model-judge labels;
  `threats` lists the blocks and their sources, the number of units counted, and that
  judge reliance.

### The withholding study's sizing (`withholding-study-simulation/2`)

The simulator estimates power under the withholding study's assumptions.

- `study-inputs RUN --runs PACKAGE... --out FILE` writes `withholding-study-inputs/2`
  from a judged blind run. Every unit carries required boolean `exclusive_scoreable`
  (whether its validated exclusive fact list is nonempty) and `placebo` (false for
  `knowledge-units/1`). Exclusive fact lists and placebo flags must agree across starts.
  The output gives counts, raw shares and shares shrunk toward pooled values using a
  beta prior of strength 2 (`(k + 2·pooled) / (n + 2)`). A structurally empty unit
  has zero shrunk touch and missed-when-touched shares; its raw conditional miss is
  null. A scoreable unit with no observed touches retains the usual shrinkage.
  Pooled touch uses all unit-starts as its denominator, including structural and placebo
  units. Pooled miss uses all touched unit-starts. Spread uses all units.
- `simulate-study --inputs FILE --price USD [--starts …] [--blocks …] [--effect 0.5]
  [--slope-sd …] [--sims 1000] [--seed 653] [--json]` selects only scoreable,
  non-placebo units and reports excluded structural-empty and placebo IDs. It refuses
  no eligible units or no positive touch probability. Defaults are starts 10 to 100 by
  10, blocks 1, 2, 3, slope SD 0, 0.5, 1. Each unit is touched with its shrunk
  probability; a shared start effect and a withheld per-unit slope act on miss log-odds.
  The solved `log_or` makes the pooled delivered missed share `effect` times the
  withheld share. Each simulated study receives a fresh blocked draw and the primary
  test with 2,000 re-draws. It refuses block counts above half the smallest number of
  starts and effects it cannot solve within 1e-6 at |`log_or`| up to 10⁴. It reports
  power, smallest starts reaching 0.8, and price. It is seeded and writes no file.
  It rejects unsupported input versions.

<a id="process-measures-process-measures1"></a>

### Process measures (`process-measures/2`)

`python -m tools.process_measures` reports [game-neutral process measures (#620)](https://github.com/CVX-Hull/enactive/issues/620).
It scores windows stuck or looping, repeated failed approaches, progress against
milestones frozen before scoring, and success claims the frames do not support. It reuses
this section's packets, budget, hashing, agreement and bootstrap. It calls no model,
launches no game and spends nothing.

| Kind | Pair | Labels (those that must cite a frame first) |
| --- | --- | --- |
| `stuck_verdict` | a window | `stuck`, `looping`, `progressing`, `cannot_tell` |
| `retry_verdict` | a window | `repeated_failed_approach` (at least two frames: the failure and the repeat), `no_repeat`, `cannot_tell` |
| `milestone_verdict` | a packet and a milestone | `reached`, `not_reached`, `cannot_tell` |
| `claim_verdict` | a window and a candidate | `supported`, `unsupported`, `not_a_success_claim`, `cannot_tell` |

Each is a `judge-events/2` event with the payload fields `label`, `cited_frames` (original
source IDs, translated from the packet's frame names), `judge`, `model`, `packet` and
`packet_sha256`, plus the pair's fields. Files are written once, one judge and kind each.

- **Milestones, frozen first.** `milestones packets RUN --runs ADMISSION...` gives one judge
  only the admission's mission (its `prompt.txt`, which may hold the previous admission's
  fallible report), no actor's message, handoff, player memory or frame, so no milestone is
  picked from what the scored admission went on to do, and asks for 3 to 8 observable
  milestones. `milestones events` writes
  `milestones/<admission>.json` (`process-milestones/1`) once; the private mapping records
  its SHA-256. Scoring packets are refused until every admission has a frozen list, and a
  changed list is refused.
- **Window packets.** `packets RUN --runs ADMISSION...` cuts each actor's decisions into
  windows within the token budget (never one decision), holding frames, the inputs between
  them, the player's own response text and final or handoff report, and claim candidates:
  every sentence of that text, with stable IDs, the first 12 kept (`--claims-per-window`),
  the cut recorded. No game-binding finding, memory fact or briefing is included. A claim is
  `unsupported` only when the window's frames contradict it; a claim about something these
  frames do not show is `cannot_tell`, and the report gives that share.
- **The repeat filter, first.** A window is flagged when it holds three or more identical
  input batches in a row whose frames did not change. Every flagged window is judged, with a
  seeded sample of the others (`--sample-unflagged`, by default as many as are flagged and at
  least 10, within what there is); the
  flags and sampling fractions are in the private mapping only.
- **Milestone packets** hold the frozen list and the admission's frames in a seeded shuffled
  order with new names, without inputs, actors or decision numbers. A milestone is reached
  when any of its admission's packets is adjudicated `reached`.
- **Agreement.** `agreement` writes `process-adjudicated.json` (`process-adjudicated/1`) as
  `agreement` above does for use labels: the first two judges' label, else a third's
  (`by`). Per kind it reports agreement, κ and dispute rate over all pairs and over the
  pairs driving the measure (either first judge gave `stuck` or `looping`,
  `repeated_failed_approach`, `reached`, or `unsupported`), chosen before adjudication.

`measure RUN [--records ROOT]` writes `process.json` (`process-measures/2`):

| Measure | Definition |
| --- | --- |
| `stuck` | Windows judged stuck or looping over judged windows, also for flagged and sampled windows apart, and weighted back to all windows by the sampling fraction |
| `retry` | Windows judged a repeated failed approach over judged windows, weighted the same way |
| `milestone` | Frozen milestones reached over frozen milestones, overall and per admission |
| `claim` | Unsupported over supported plus unsupported success claims, among the kept candidates |

Each rate retains its numerator, denominator and value, and reports `eligible_admissions`
(the number of admissions with an observed positive denominator), `resample_range`,
`range_status` and `range_reason`. A nondegenerate `descriptive` range gives the 2.5th and
97.5th percentiles of the seeded admission bootstrap; it is neither a population confidence
interval nor a validated error bound. Other statuses give a null range and a reason:
`no_denominator`, `insufficient_admissions`, `boundary_observation` (rate zero or one),
`no_defined_resamples`, `degenerate_resampling` or `unestimable_sampling` (an unsampled
stratum). For the last, the eligible count still describes observed denominators and does
not make the all-window rate estimable. Bootstrap metadata states the resampling unit is an
admission and independent source groups are unknown: current inputs do not qualify world or
lineage independence. Admissions are not counts of independent worlds.

The all-pairs and driving-pairs judge κ and dispute rates use the same range fields;
`undefined_statistic` marks an undefined point, and the boundary rule applies to dispute
rate but not κ. These and the plain agreement and binary κ figures are diagnostics of judge
agreement, not accuracy or truth. The claim rate is over kept candidates only and is not
weighted by window sampling.
`events` refuses, before writing anything, answers that do not cover every packet (for a
third judge, every packet the agreement lists) and any answer field not allowed for its
kind; one judge and model derive every admission's milestones. Whether a measure is `kept` is decided on its driving outcome as a
binary (the driving labels against all others, `cannot_tell` included), over all its pairs:
the first two judges' Cohen's κ, with their agreement and positive specific agreement
beside it. `kept` is false, with the reason, when that κ is undefined or below 0.845, the
memory measures' κ computed the same way (applied or not) over all 1,911 first-two-judge
pairs of the [curator scoring](../acceptance/2026-11-13-curator-scoring.md) run: such a
measure is reported, not tuned. (A κ over the driving pairs alone cannot exceed 0 for a
measure with one driving label, so it is reported but decides nothing.) The report compares
the filter's flags with the adjudicated `stuck` and `looping` windows and, with
`--records`, the game binding's `stall` findings with the stuck or looping windows and its
`ineffective_repeat` findings with those and with the repeated-failed-approach windows,
unweighted. A finding touches a window when one of the evaluation steps it spans, of that
window's actor, holds a frame source ID the window holds (the record counts decisions as
completed inputs and the windows count player requests, so decision numbers are not joined) (`binding`; a record of another core version is skipped and
listed with its reason, and `binding` is null with the reason when none is readable). `not_corrected` states that the labels are not corrected against a human
truth. Isolation is as below: judges get one packet directory each, and nothing a judge
produces reaches the player, the curator or an evaluation record.

**Isolation.** The tool writes packets, events and statistics only into its run
directory, and refuses a run directory whose parent is not named `memory-measure`; by
convention that is `.runtime/memory-measure/<run>/`. The anchor never writes into the gate
it reads. It does not check where the lead saves a judge's answers, and it does not keep a
judge from the mappings in the run directory's `private/` folder: the lead gives a judge
its packet directory and nothing else. An evaluation record holds no judge event, so the
viewer cannot serve one. The curator's trace is projected by allowlist from named session
directories, a run package freezes a closed set of files, and the import contracts forbid
the player, the curator and the trace projection from importing evaluation code or tools.

The fixed anchor set is the measure gate's sealed `labels.json` (`owner-labels/2`).
The anchor reads only that format, and the standing measure uses no further owner
labels. See the [measure gate record](../acceptance/2026-11-13-memory-measure-gate.md)
and the [“Judges without audits” decision](../decisions/owner-decisions.md#two-standing-judges-and-a-dispute-judge).

## Tracked run ledger and metrics snapshot

Development-run quantities live as data in git, and pages render them or cite them
(S-EVIDENCE). Both files hold no local paths, ports or secrets.

| File | Format | Written by |
| --- | --- | --- |
| `runs.jsonl` | One [`dev-run/3`](../../schemas/dev-run.schema.json) row per admission: study issue, run, label (the run's short name in its study's dated record), arm, start, lineage, admission, session, source commit, UTC end, receipt outcome, observed attempts for current runs, wall seconds, and spend as decimal strings | `tools/run_ledger.py record`, from the package's `campaign-run/10` manifest and `campaign-receipt/7` alone |
| `run-metrics.jsonl` | One [`run-metrics/1`](../../schemas/run-metrics.schema.json) row per session and evaluator core and binding version: the headline metric values, copied verbatim from the evaluation record | `tools/evaluate.py evaluate-table RECORDS --snapshot data/evaluation/run-metrics.jsonl` |

- **Origin.** `record` accepts the current `campaign-run/10` and
  `campaign-receipt/7` pair. It copies the receipt's provider subtotal,
  observed attempts and unpriced player and recall counts. Incomplete traces
  preserve the observed starts as a lower bound. A complete trace has basis
  `provider-reported` and equal `spend_usd` and `provider_usd`. The per-attempt
  charge fields are null for current rows. On a complete trace the unpriced
  count describes observed attempts with an unknown charge.
- **Incomplete trace.** `--record-upper-bound` records the observed subtotal
  and counts under basis `incomplete-trace`. The separate
  `spend_upper_bound_usd` is a planning amount for admission. It uses the
  larger of the declared limit and observed subtotal, plus allowances for
  possible in-flight attempts. Ledger totals show the provider subtotal and
  the admission amounts separately. See the
  [campaign procedure](../operations/campaign-run.md#start-and-close).
- **Historical basis.** Rows with basis `historical` hold the original counted totals
  and any original split, with a null `spend_upper_bound_usd`. Their totals may include
  per-attempt bounds or configured estimates.
- **Rejection.** A row without `schema: dev-run/3`, a schema violation (a label is required),
  a repeated study and run, a repeated session, more combined player and recall unpriced attempts than recorded attempts, or an
  inconsistent spend split is an error naming the line. Snapshot rows are validated against
  their schema when read and before they are written.
- **Generated tables.** A `<!-- evaluate-table study=N [lineage=L] core=C binding=ID:V -->` …
  `<!-- /evaluate-table -->` block is the table of the snapshot rows for that study (and
  lineage), joined to the ledger on session, at those versions. Markers are whole lines and
  blocks do not nest; mismatched or malformed markers are an error before anything is
  written. `evaluate-table … --write` regenerates the blocks, and the fast checks run
  `--check`, which fails on a stale block.
- **One numeric record.** The ledger is the one numeric record of a run. A dated record
  presents numbers through generated tables or by citing the ledger, and keeps no second
  hand-typed copy of attempts, spend or duration. `run_ledger check`, part of the fast
  checks, validates every ledger row; it reads no document. Four study records keep
  hand-scored tables (the [development loop](../acceptance/2026-11-06-development-loop.md),
  the [long-horizon arm](../acceptance/2026-11-07-long-horizon-382.md), the
  [seven-day lineage](../acceptance/2026-11-07-seven-day-397.md) and the
  [added held-out lineage](../acceptance/2026-11-09-held-out-lineage-522.md)); those tables
  are never rewritten (ADR008) and are not checked.

## Spectator view API (`spectator-view/2`)

All routes are `GET`, return JSON with `"schema": "spectator-view/2"` unless noted, stay
under 4 MiB, and write nothing. `<run>` is a session ID. Lists paginate with
`after`/`limit` (`limit` ≤ 500).

| Route | Returns |
| --- | --- |
| `/api/view/runs` | One summary per known run: facts, state (`live` only for the run this viewer evaluates; `unfinished` for any other run whose store is still `live`, because its final pass never ran; otherwise `final`; `versions.state` and the summary's `state` stay the store's own `live` or `final`), outcome (hours, died, `censor_reason`), decisions, dollars, headline metrics, versions. Built by scanning record stores read-only and cached in memory. |
| `/api/view/run/<run>/summary` | Facts, evaluator outcome, recorded `custodian_receipt`, Pause conditions (below), game state with provenance, findings, ladder, metrics with `source`, `count`, `denominator`, `missing`, and reader coverage with held-out validation status |
| `/api/view/run/<run>/steps?after=&limit=` | Steps: `seq`, `decision`, `wall`, `kind`, `mode`, `game_time`, `source_id`, `frame_changed`, `dollars`, `keys` |
| `/api/view/run/<run>/frame/<source_id>` | The original PNG (`image/png`), only after its SHA-256 matches the record |
| `/api/view/run/<run>/tools` | Per-tool aggregates (calls, p50 and p95 latency, refused, errors, result bytes) and transitions `[from, to, n]` |
| `/api/view/run/<run>/calls?tool=&status=&after=&limit=` | Tool-call rows, each with the step it produced (and its frame) where one exists |
| `/api/view/run/<run>/requests?after=&limit=` | Request rows, plus eviction and handoff markers |
| `/api/view/run/<run>/context/<request_id>` | Ordered parts replayed from the manifest (`exact: true`). Without a manifest: frozen inputs plus recorded tool results (`exact: false`). |
| `/api/view/run/<run>/memory` | Records with kind, chain, cited sources, reads (record IDs returned), handoff carry and human audit labels |
| `/api/view/run/<run>/knowledge?actor=&request=&entry=&after=&limit=` | Actor/request selection, recorded knowledge selection/delivery, verified frozen snapshot entries, explicit reads and public reports, linked mechanical results and separately labelled evaluator outcome |
| `/api/view/run/<run>/programs` | Programs with lineage and runs (status, steps, elapsed, reason) |
| `/api/view/run/<run>/handoffs` | Handoffs with position, decisions to resume, carry ratio, carry text and identity check |
| `/api/view/improve/changes` | Change records with per-run target, uptake and guard values for each arm, and bootstrap intervals |
| `/api/view/improve/failures` | Failure modes from derived events and human labels: occurrences, runs, decisions and dollars inside, source |
| `/api/view/compare?group=arm\|start&runs=` | Per group: n, deaths, censored, Kaplan–Meier with Greenwood bounds, median or `not_reached`, restricted mean to the stated horizon with a bootstrap interval, excluded runs, version facts |
| `/api/view/explore?arm=&start=&outcome=&metric=` | Cohort rows; the metric's n, median, IQR and bootstrap interval for the median (n ≥ 5); the 12 decisions before each death |
| `/api/view/frame/health` | The spectator frame's health strip (`spectator-frame/1`, below) |
| `/api/view/frame/containers?after=&limit=`, `/api/view/frame/containers/<container_id>` | The container inventory and one manifest (`spectator-frame/1`, below) |
| `/api/view/frame/episodes` | The tracked forgetting episodes with anchors resolved to runs and frames (`spectator-frame/1`, below) |
| `/api/view/frame/curator-sources?after=&limit=` | Configured curator result-source labels, without paths (`spectator-frame/1`, below) |
| `/api/view/frame/curator-results?source=&after=&limit=&snapshot=` | One source’s recorded current submission/restore results and read-snapshot provenance (`spectator-frame/1`, below) |
| `/api/view/frame/curator-session-sources?after=&limit=` | Operator-configured receipt labels |
| `/api/view/frame/curator-session?source=&after=&limit=&snapshot=` | One terminal curator session receipt and its paged gate results |
| `/api/view/frame/curator-runner` | The curator runner's status file, read at this request: how far the curator trails play (`spectator-frame/1`, [below](#curator-runner-status)) |

### Recorded browser entry

The standalone viewer with `--recorded-page` serves the shared spectator page
at `/recorded/` and its allowlisted assets under `/app/` and `/vendor/`. The
page and existing viewer API stay on the same loopback origin. This mode reads
existing evaluation stores and recorded sources and opens Run Overview. Its
browser code makes viewer requests only. The supervised gateway owns live status,
native captures and Pause. See the [recorded viewer procedure](../components/spectator.md#recorded-browser-entry).

### Recorded custodian receipt

`custodian_receipt` projects the current package's `campaign-receipt/7` when the
catalogued directory's current manifest and receipt agree with the summary's session
and source commit. A missing, unreadable, unsupported or mismatched source yields
`null`. The projection contains `outcome` (the custodian's disposition) and the
booleans `normal_native_exit_zero`, `native_absence_verified`,
`deciding_hosts_quiescent` and `input_authority_revoked`. Unavailable individual
facts are `null`. The evaluator's outcome and Pause conditions use their existing
sources. Input acknowledgement, save persistence and wrapper cleanup each require
their own evidence.

`custodian_receipt.accounting` is `null` when receipt accounting is missing,
incomplete or invalid. When `spend_complete` is true and the amounts and counts
are valid, the projection gives equal `reported_usd` and `spent_usd` as exact
decimal strings, with `unpriced_requests` and `unpriced_recall_requests` as
counts. Run Overview shows the provider subtotal and the unpriced counts when
some charges remain unknown.
The evaluator's `dollars` field remains the configured-rate estimate.

### Recorded knowledge and public reports

The `knowledge` route is a pure viewer projection over the selected run. Without
`actor` it returns actor IDs from recorded requests; with `actor` it returns that
actor's request IDs, `events`, `snapshot_status`/`snapshot`, `calls`, `hints`,
`journal_available`, `finishes`, `context` and `outcome`. `request` filters
selection/delivery by its recorded player or recall request IDs and calls by their
request ID; hints and finish claims remain actor-wide. An unknown actor/request is
`404`. `entry` selects an exact ID within the actor's snapshot, not a global store.

- `events` allowlist `knowledge-recall`, `knowledge-delivery` and
  `knowledge-undelivered` fields, selected article/fact/index IDs, delivery leads/index
  and original trace line. Selection, delivery and an explicit read are distinct.
  Missing delivery text or a missing join stays unavailable; proximity proves no use.
- `snapshot_status` is `verified`, `unavailable`, `hash_unavailable` or
  `hash_mismatch`. Entries are served only after the actor's `player-host-inputs/3`
  `frozen.json` names this actor/session and its `delivered-knowledge.json` digest
  matches. Missing/mismatched bytes are never presented as the frozen contents.
  The `delivered-knowledge/1` snapshot exposes only public article/fact fields,
  coverage and confirmation markers in their recorded units. It pages `items` with
  `total`, `limit` and `next`. An absent entry is unavailable, not proof of withholding.
  No private full export, withheld-unit file or curator repository is read.
- `calls` expose public intent/cites, knowledge query/read returned IDs, status and
  explicit operation/source/step IDs, allowlisted tool-result status/reason/delivery,
  and original operation status/receipt dispositions. Intent, hints and finish
  claims are unverified player reports; SDL delivery and evaluator outcome have
  their separate meanings. No expectation or private reasoning is inferred.
- `anchors` resolve only explicitly recorded source IDs through the existing
  catalog/frame digest verifier, including other catalog runs. Each has `run`,
  `source_id`, `available`, `reason`; missing catalog/source/digest support remains
  unavailable. Citation IDs are not reinterpreted as source IDs. Confirmation tuples
  without source IDs or comparable timestamps provide neither a source link nor an
  absolute age. Publication/coverage recency is not truth or measured curator lag.
- `context` exposes exactness, part count and missing-kind markers through the
  existing request-context reader, without transcript text or reasoning.
  `journal_available: false` is distinct from a readable journal with zero hints.
- Actor/request lists cap at 500; event/call/hint/finish lists cap at 100. Text fields
  cap at 1,024 characters; identifiers over 512 characters are omitted instead of
  truncated into false identities. Nested body/lead/index/receipt/source lists have
  explicit bounds and omissions. `*_omitted`/`omitted_characters` disclose omitted
  items/characters. The common 4 MiB ceiling still returns `413 response_too_large`;
  select a request or narrower entry/page instead of treating that as empty data.

The Actor tab offers this reader alongside historical forgetting episodes. It
supports native keyboard controls, focuses a selected snapshot entry after loading,
refreshes at the existing five-second viewer cadence, uses escaped text and
phone-width wrapping, and preserves the separate Live/Pause
path. The existing hint list remains available. Richer curator, belief/scope,
ontology, draft and program views remain outside this projection.

### Recorded curator results

The Curator tab reads only operator-configured result files. Repeat
`--curator-results LABEL=FILE` on the supervisor or standalone viewer CLI to select
existing `gate.jsonl` files or immutable snapshots. Labels are unique, match
`[A-Za-z0-9][A-Za-z0-9_.-]{0,127}` and are the only source selectors exposed to the
browser. The default has no sources. A label is operator-supplied identity, not
verification of game/fork identity or a link to a player run. The supervisor forwards
these arguments only to its unsupervised viewer child; they grant no input authority.

Both result routes use `spectator-frame/1` success payloads and the existing
`spectator-view/2` error envelope. The sources route pages `items: [{label}]` with
`total`, `next` and `limit`. The results route requires a configured `source` and
returns that label, `source_status`, `snapshot`, `items`, `total`, `next` and `limit`:

- `source_status` is `available`, `empty`, `missing`, `unreadable`, `too_large`,
  `unsupported` or `malformed`. A readable empty source differs from an absent one.
  Unsupported/mixed schemas, malformed JSON or a partial tail produce no result rows.
  A valid result whose status is `unknown` belongs to an `available` source.
- A successful read identifies its exact bytes with `snapshot: {sha256, bytes}`.
  The reader reads at most `MAX_JSON_FILE_BYTES + 1` (16 MiB plus one byte); excess
  is `too_large`, never a complete truncated journal. Regular result files are read
  without a writer lock, repository access, Git execution or a persistent history.
- `after > 0` requires the snapshot digest. A changed digest returns `409
  source_changed`; the page resets visibly instead of combining different reads.
  Bad paging/digests are `400`; an unknown configured-source label is `404`.
  The existing response ceiling remains `413 response_too_large`.
- Rows preserve journal order with an `index`, exact `operation_id`, `operation`,
  `status`, `base_version`, `restored_from`, `version`, `submission`, `session` and
  bounded `diagnostics`. Only the current exact `curator-gate/2` shape and its
  operation/status/null conventions are accepted. No Boolean alias or historical
  converter is used. Text, identifiers and lists use the existing bounded omission
  conventions; an overlong identifier is omitted, never shortened into another ID.
  Free-form references and diagnostics containing `/` or `\` are conservatively
  withheld as path-like detail, with `path_details_omitted` and identifier omission
  metadata. This also hides benign separator-containing text; the source remains
  available for local inspection. Whole values are withheld rather than presenting partially redacted identifiers.
- Publication is a recorded gate report, not semantic verification, the repository's
  present head or delivery/read/use. Restore, unchanged and submission results remain
  distinct. Null and unknown versions remain explicit. No timestamp, gate pass rate,
  lag, absolute age, health-slot value or run association is inferred.

The reader serves no raw paths, briefs, transcripts, submission bodies, drafts,
credentials or arbitrary repository files. It writes nothing and imports no curator
runtime; no output reaches the player or curator. The Curator tab provides source
selection, result rows and detail using escaped content and keyboard controls. The
remaining session timeline, diffs, draft contents and current states, ontology and program views stay unavailable.
Source changes reset stale result/detail selection; the control frame and independent
Pause continue through their existing path. Fixture projection and rendered checks
establish this reader's behavior, not semantic gate efficacy or real curator lag.

### Recorded curator sessions

Repeat `--curator-sessions LABEL=FILE` on the supervisor or standalone viewer to
configure individual current `close-out.json` receipts. The browser selects only
operator-supplied aliases, with the same label, bounded regular-file read, paging,
source status and snapshot rules as recorded results. JSON does not require a final
newline. A source change requires a fresh snapshot; no receipt is associated with a
run or a separate result journal. The reader accepts the current close-out object,
terminal curator-session `container-manifest/1` and current `curator-gate/2` results;
unsupported metadata and records yield no partial projection.
Required close-out lifecycle fields and prepared-session metadata must be present;
the producer's minimal preparation-abort receipt remains valid. Restricted windows
start at one and end no earlier than their first step.

The session route returns `header` and `drafts` alongside the paged result `items`.
The allowlisted header records inputs, pinned versions and digests, configured limits,
terminal lifecycle, resource measurements and `published_after`; absent values are
unavailable. A USD cap is not measured spend, and wall timestamps do not represent
game time or live custody. Identifiers and free text use bounded path-like omission;
no host configuration, repository path or raw manifest is returned. `drafts: null`
means no collection report was recorded; a report with empty lists is distinct. These
collection events are historical, not current draft states or complete promotion
history. Empty verdicts establish no result, not zero publications or acceptance.
The reader uses no producer lock, writes no records and makes no Git or provider call.

### Curator runner status

`--curator-runner-status FILE` on the standalone viewer names the curator runner's
`status.json` (`curator-runner-status/1`, owned by `harness/curator/runner.py`). The
supervisor passes `<run>/curator-runner/status.json` when it starts the runner with
`--curator-runner`, and passes nothing otherwise. The file shows what the curator has
done since the actor's delivered version; the actor's delivered version stays in the
[knowledge view](#recorded-knowledge-and-public-reports), and the two are never merged.

`GET /api/view/frame/curator-runner` opens the file for reading at each request, with
the same bounded regular-file read as recorded results, no lock and no write, and
returns `source_status`, `snapshot` (`{sha256, bytes}` of the bytes read, or `null`),
`read_wall` (when the viewer read it) and `status`:

- `source_status` is `available`, `not_configured`, `missing`, `unreadable`,
  `too_large`, `empty`, `malformed` (not complete JSON, as a partly written file
  would be) or `unsupported` (not a `curator-runner-status/1` object). Every state
  but `available` has `status: null`, so no figure is shown; a missing or partly
  written file is never read as zero lag.
- `status` projects, by allowlist: `session`, `state` (`polling`, `in-session`,
  `stopped` or `ended`), `updated_wall`, `stop_reason`, `look_error`, `settings`,
  `position` (actor, step, operation, ordinal among the admission's finished
  operations, and the snapshot's `read_wall`), `as_of` (the same for the last
  successful read), `after_last_read`, `snapshot` timings, `current` (the session in
  flight), `covered_prefix` (`end` as a placed step, and `restore`; after a restore the
  prefix is known through `end` and unknown past the restore), `lag`, `stamp_distance`,
  `backlog` (finished steps beyond the curator's cursor, counting steps in aborted and
  in-flight windows), `last_confirmed` (version, label, window and its coverage stamp's
  session, actor and last step), `latest_version` (version and stamp), `failures`,
  `unconfirmed` (how many publications could not be confirmed), `examined` (the
  latest 100 ranges; each has its window, outcome, whether the cursor advanced and its
  wall times) and `unexamined` (the first 100 ranges the cursor had not passed).
  `last_confirmed` and `latest_version` also carry `baseline`, the runner's own flag for
  that version from its list of versions; a null stamp alone does not establish it.
- `examined` and `unexamined` are `{items, total, omitted}`: `total` is the length of the
  runner's list and `omitted` how many rows were left out. When the runner wrote null (it
  writes `unexamined` only once it has stopped or ended) all three are null; when the
  value is absent or not a list all three are `unknown`. A row that is not an object is a
  row whose every field is `unknown`.
- A value that is absent, the runner's `unknown`, or of another type is `unknown`,
  never zero. `after_last_read` is always `unknown`: it is the runner's sentinel and no
  other value is projected. A null the runner wrote (no session in flight, nothing
  confirmed, no stop reason) stays null. Text that looks like a path or exceeds the
  identifier limit is withheld whole, with `omitted_characters`. Wall times are seconds,
  passed on as recorded; the page shows one it cannot place as a date as unknown.

The page polls this route every five seconds, and each response replaces the previous
one: a file that goes missing or is read partly written clears the figures shown.
Nothing is sent to the curator, and no figure is derived beyond what the file states.

### Spectator frame (`spectator-frame/1`)

The spectator's `/api/view/frame/*` routes follow the view API rules above and carry
`"schema": "spectator-frame/1"`. Errors keep the `spectator-view/2` envelope. They read
tracked data, the catalog's stores, explicitly configured curator result files and the curator runner's status file, and nothing they compute reaches the player or the
curator (ADR008). The container and probe directories default to the repository's
`data/containers` and `data/evaluation/probes`; `create_app(frame_sources=)` overrides
them for tests.

- **Health.** `slots` in a fixed order: `actor_cadence`, `curator_lag`, `gate_pass_rate`,
  `snapshot_freshness`, `program_delegation_share`, `monitor_alerts`, `spend_against_cap`. Each
  slot has an `id` and a `label`. The response also has `containers`, and `runs` (catalog
  runs that belong to a container).
  - `actor_cadence` is `measured` when derived from the catalog runs whose session a
    container manifest records. It then has `source` (`derived`), `runs`, `unreadable_runs`,
    `decisions`, `steps`, `game_hours`, `decisions_per_game_hour`, `steps_per_game_hour` and
    `dollars`. A run whose store cannot be read is counted in `unreadable_runs` and left out
    of the figures.
  - `actor_cadence` is `no-data`, with a `detail`, when no readable run has a game-time
    reading.
  - Every other slot is a placeholder with `state: "not-yet-measured"`, a `phase` of
    `curator-and-memory` or `programs-and-monitor`, and no numeric value. The page labels
    it “not yet measured” and names the phase after “arrives in”
    ([health response source](../../harness/viewer/frame.py)).
- **Containers.** Every `data/containers/*.json` index (`container-index/1`), each manifest
  checked with `harness.trace.sidecar.validate`. The list pages like the run list: `items`
  (`id`, `kind`, `owner_role`, `lifecycle_state`, `retention_policy`, `evidence_study`,
  `index_study`), `total`, `kinds`. The detail route returns `container` (the manifest
  unchanged) and `index_study`; an unknown ID is `404 unknown_container`. An invalid
  manifest, index or repeated ID refuses the routes with `500 invalid_container` or
  `bad_data_file`; the inventory never lists a manifest that does not validate. Age is not
  reported, because a sealed manifest records no creation time.
- **Episodes.** `lineages`, one per `data/evaluation/probes/*/episodes.json`
  (`probe-episodes/1`, validated by `harness.evaluation.core.probes.episodes`).
  - **Each lineage** has `lineage`, `study`, `note`, `source` and its `episodes`.
  - **Each episode** has `id`, `title`, `fact`, `record` (a memory record ID prefix or null)
    and `lost_at`. It also has `probe` (`boundary`, `failing`, `costly`, and `annotation`,
    which is `blinded` or `adjudicated`), and the anchors `observed`, `needed` and
    `acted_without` (null when not recorded).
  - **Each anchor** has `chunk`, `run`, `actor` (the chunk's actor directory), `source_id`,
    `available` and `reason`. Where a manifest describes the session it also has `actor_id`
    and `container`, and it has `text` when the fact appears only in the actor's text.
  - **`run`** is the catalog run name for the frame's session. An anchor without a frame
    falls back to the chunk's run name. An anchor whose session is absent from the catalog
    has `run` null.
  - **`available`** is true only when `/api/view/run/<run>/frame/<source_id>` would serve
    that frame now. Otherwise `reason` is one of:
    - `no_frame`;
    - `run_not_in_catalog`;
    - `ambiguous_run`: another session's run has the same name, and that route resolves the
      name to it;
    - that route's own error code. An unreadable store gives `record_unavailable` for that
      anchor rather than failing the route.

  The page opens anchors through the per-run views; frames are served only by that route.
  Each poll re-checks every anchor's frame digest.

The gateway forwards only the statuses listed under
[Control path and viewer](#control-path-and-viewer), so a `500` from these
routes reaches the page as "viewer unavailable".

## Pause conditions (supervise)

The viewer computes these for the live run. They inform the owner and gate nothing.
Each has a value, a threshold, `met`, and the dollars per minute that continuing costs.

| Condition | Met when |
| --- | --- |
| Feed alive | No new operation for 300 s |
| Custody healthy | Any partial or unknown receipt, or a custody stop |
| Not looping | 30 or more decisions without `in_play` while game time does not advance |
| Spend inside allowance | Spend so far, or the one-hour projection, exceeds the run's spend allowance. Spend here is the configured-rate estimate, so it informs and is not the host's counted total |
| Not dead and still spending | A death event followed by further requests |

Game state (vitals, threat) is information only and never a Pause condition.

**Pause.** The gateway handles the operator's reason and stops automation independently of
the viewer under the [operator Pause contract](computer-control.md#passive-spectator-reads-and-operator-pause).
