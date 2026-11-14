---
owner: lead
review_trigger: A record, metric, reader, health rule or view-API change, or a new game binding
status: active
---

# Run evaluation records, metrics and the spectator view

This page owns the current formats ([#383](https://github.com/CVX-Hull/enactive/issues/383)).
[ADR008](../decisions/008-evaluation-and-spectator.md) owns the rationale.

Every value here is **interpretive**. It is derived from recorded evidence, carries its
source and confidence, and accepts nothing. Frames, receipts and the issue's decision
rule still decide acceptance. No value on this page reaches the player.

## Inputs

The evaluator reads one run directory read-only:
- `session.sqlite3` (`computer-session/1`);
- `sources/*.png`;
- each `actors/NNN/host.jsonl` (`player-host/5`), including its per-request context
  manifest;
- the handoff contexts under `contexts/*.json` (`player-handoff-context/1`);
- `manifest.json` (`campaign-run/7`), including its operator labels;
- for the closed set of archived sessions only, the older versions of the manifest,
  host traces, receipt and run-ending record that the archive index lists for each
  session (see "Implementation rules");
- the run's `player-memory/2` store.

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
- `sources.iter_host` is the one offline parser of `host.jsonl` (`player-host/5`), used by
  the evaluator, the viewer and `host-summary`. The supervisor's live incremental reader in
  `tools/campaign_player.py` stays separate because evaluation never gates the control path
  ([ADR008](../decisions/008-evaluation-and-spectator.md)). `iter_host` is bounded to 64 MiB
  per line and two million lines per trace, skips blank lines, and rejects a trace that is
  empty (or only blank lines), whose first event is not a `host-start`, or whose
  `host-start` is not `player-host/5` telemetry 5. The one exception is a trace of an
  archived session: its caller passes that session's index entry, and the trace is then
  also read in the version the entry lists, when its `host-start` names that session.
  `host-summary` finds the entry from the manifest of the run directory the trace sits in,
  so an older trace outside such a directory is an unsupported version. An unterminated final line that does not
  parse is an error for `host-summary`; the evaluator and the viewer ignore it on every
  pass, live or final, because a trace may still be appending. A newline-terminated
  malformed line is always an error.

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
- #382's severe needs for the day check (binding version 2):
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
| `lineage.day_check` | The crossing is the first step after the lineage's last reading below one game day from that start, so a rewind below the day undoes an earlier crossing. The needs are scored at the first in-play step from the crossing on whose needs the binding can read, in that admission or a later one (`scored_run`, `lag_hours` past the day). Deaths are compared in lineage order (admission, then step), so a death in an admission a reload later rewound still counts. A death at or before the crossing fails the check (`died_before`). A death after the crossing but before the scored step leaves it unscored (`died_in_lag`). Otherwise `passed` when `severe_needs` reports none; a severe need that was read counts even when another need is unreadable. Also `severe` and `episode_changes`; #382 classifies an episode change as a continuity failure first. If admission 1 never reaches play, a later admission's first in-play clock is the zero | 1 | Not crossed: `not_reached`; needs never legible after the crossing: `needs_not_legible`; death in the lag: `died_in_lag` |
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
| `python -m tools.memory_reads` | text, or `--json` | Per memory read (`player_memory_query`, `player_memory_read`, `player_memory_context`) in `player-host` traces: the records returned, whether the reading actor already held each, each record's age, and the actor's calls before and after, with later calls that type a record's words, fetch a source it cites or name it marked as references. It lists and counts; it does not judge use. |
| `python -m tools.memory_screen_checks` | text, or `--json` | Three subcommands for the [context design](../design/player-context.md). `store`: every published version of a curator knowledge repository, read from the repository's loose objects without a Git process: its session, its facts and articles (all and current) and bytes, and the facts whose text matches a pattern. It reads `curator-knowledge/2` repositories of `curator-fact/3` records only and refuses any other, so the sealed stores of the memory screen's gates are not read. `replay`: for a known loss, the request that returned the frame at which play needed the fact, when the player's record was written, and when a briefing or a snapshot difference would first have shown it. `cut`: a simulation of the design's cut over the recorded request sequences for assumed curator lags, with tokens per turn and the marks as options. Its `recorded` row is from the traces; every other row is simulated, not measured. |

**Percentiles.** There is one definition, nearest rank (`metrics.nearest_rank`): the
`ceil(q·n)`-th smallest value, and the smallest value when that rank is 0. Every `p50` and
`p95` uses it: the `host.latency` metric, the viewer's tool latencies, and the distributions
of both diagnostics. A metric named a median (the pace and handoff rows) is the arithmetic
median, the mean of the middle pair for an even count. The viewer's explore cohort median,
IQR and bootstrap intervals are not percentiles of this kind: they use numpy's defaults.
`host-summary` and `control-summary`
`p50` values are nearest-rank, so on an even count they are the lower middle value, not
the mean of the middle pair. Records written before #404 and #418 report those `p50`
values as true medians; compare them with current ones on that basis.

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
- 2-second timeout and 4 MiB cap;
- only `application/json` and `image/png` responses, never HTML or script;
- the viewer's `200`, `400`, `404`, `409` and `413` pass through unchanged, and any other
  status is a forwarding failure;
- the gateway's own security headers on every response.

A viewer response with a disallowed media type or over the size cap returns `502` with
`{"error": "Viewer response refused"}`. Any other forwarding failure (a refused connection,
a timeout, another viewer status, or all eight forwarding slots in use) returns `503` with
`{"viewer": "unavailable"}`. The page treats both as "viewer unavailable". The page polls;
there is no streaming connection.

**Launch and lifetime.**
- The supervisor starts the viewer as an **unsupervised** child: `python -m harness.viewer`.
- Its exit never ends, pauses or gates the run, and the supervisor stops it at the end.
- The viewer reads the live run directory and the evaluation root (`.runtime/evaluations`).
- It writes only the live run's `live` evaluation store.

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

- **Archived runs.** These readers are the closed-archive case that
  [S-MIGRATION](../standards/migration.md) allows; the `requests.manifest` column applies
  its additive-event case to `context-manifest`.
  - **The index.** `data/evaluation/archive-sessions.json` (`archive-sessions/1`) is the
    one closed index of the sealed sessions the evaluator reads, keyed by **session ID**.
    Each entry gives the sealed evidence `study`, the `run` directory name and `versions`:
    the versions that session's files carry for its manifest, its receipt, the receipt's
    driver record, its host traces with their telemetry version, and its run-ending record
    (`watch-terminal.json`). The entries of `campaign-run/4` sessions also hold the
    operator `labels`, which those manifests predate.
  - **One indexed session does not evaluate.** `522-held-out/computer-sessions/lh4a1`,
    a session of the fourth held-out lineage that an infrastructure fault ended early,
    was sealed with its database in write-ahead-log mode and without its log files, so
    SQLite cannot open it inside the read-only store. Its manifest, receipt and
    run-ending record read; its operations do not, and evaluating it is an error. The
    sealed copy stays as it is, because sealed evidence is never rewritten.
  - **What an entry allows.** An entry does not by itself make an old version readable.
    A record in its current version is read as current for any session, listed or not. A
    record in an older version is read only for a session the index lists with exactly
    that version, beside a manifest in the version the index lists for that session. Any
    other old version is an error naming the file and version. This reads historical
    evidence; it is not an admission, and admission still requires `campaign-run/7`.
  - **The spend-limit session.** The owner added `spend-limit-run-555` on 13 November 2026: `campaign-run/6`, `campaign-receipt/4`, `player-driver/4`, `player-host/4` telemetry 4 and `campaign-watch-terminal/4`. It is read-only in those versions. Its manifest supplies `spend_limit_usd` rather than the earlier reservation; receipt/driver ending fields and host evidence are read as recorded. No archive is admitted for play.
  - **The four combinations.** The index holds 55 sessions in four combinations of versions.
    The original 54 sessions predate the dollar limit: every one carries `campaign-receipt/3`,
    `player-driver/3` and `player-host/3` with telemetry version 3, beside a
    `campaign-run/4` or `campaign-run/5` manifest. For each record that is not current,
    the fields used are fixed.
    - **Shared by the original three combinations:**
      - From the receipt: `outcome` and `driver` for the run's ending; `session`,
        `source_commit`, `normal_save_claimed_by_harness`, `native_absence_verified`,
        `normal_native_exit_zero`, `deciding_hosts_quiescent` and
        `input_authority_revoked` for `host-summary`.
      - From the driver record: `actors` (each one's `settled` and `player_finish`) and
        `ending_request` for the run's ending; `schema`, `outcome`, `attempts_charged`,
        `host_seconds_used`, `configured_estimate_usd` and `missing_usage_attempts` for
        `host-summary`. The driver record's version must be the one the index lists.
      - From a host trace: every event, as from a current trace. Its `host-start` must
        carry the listed `schema` and `telemetry_version` and name the session; the
        evaluator also takes its `actor_id`, `model`, `provider`, `effort` and
        `provider_routing`. No field the evaluator reads differs between the two trace
        versions, and these original archived traces have no counted cost.
      - From the manifest: `schema`, `session`, `player_store`, `source_commit`,
        `effort`, `files`, `accounting`, `limits`, `ending_reserve`, `wall_seconds`,
        `host_seconds`, `max_hosts` and `max_http_attempts`. `accounting` is the
        worst-case reservation these packages declared; the spend allowance of an
        archived run comes from it.
    - **30 sessions** with a `campaign-run/4` manifest and a `campaign-watch-terminal/2`
      run-ending record. The operator labels come from the index. From the run-ending
      record: `reason` only (it has no `pause_reason`).
    - **22 sessions** with a `campaign-run/5` manifest and a `campaign-watch-terminal/3`
      run-ending record. The manifest's own `labels` are read. From the run-ending
      record: `reason` and `pause_reason`, and its `session`, which must be the
      manifest's.
    - **2 sessions** with a `campaign-run/5` manifest and a `campaign-watch-terminal/4`
      run-ending record. The manifest's own `labels` are read, and the run-ending record
      is current.
  - **Refusals.** A `campaign-receipt/3`, a `player-driver/3` record or a `player-host/3`
    trace of a session the index does not list is an error naming the file and
    version. An index entry
    with any other combination of versions, an index in another version and a missing
    index are each an error naming the index, and nothing is read through it.
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
  2. `owner_pause` (the watch terminal record's `reason` is `operator_pause`;
     `pause_reason` is read from `/3` only);
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
  dollar limit, `spend_limit_usd`. For an archived run it is the manifest's
  `ceiling_usd` minus `prior_reserved_usd`, which `run_facts` also holds as
  `declared_ceiling_usd` and `prior_reserved_usd`; both are null for a run that
  declares a limit. The spend rate uses the last ten minutes of requests.
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

A judge event is one model judge's answer to one closed question about recorded play
([#386](https://github.com/CVX-Hull/enactive/issues/386)). Judges are host agents the lead
starts; `python -m tools.memory_measure` builds what they read and counts what they answer,
and calls no model. `harness/evaluation/core/judge.py` validates the format. The design is
[general memory](../design/general-memory.md#3-measurement). `judge-events/1`, the format of
the [measure gate](../acceptance/2026-11-13-memory-measure-gate.md), is not read.

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
| `label` | `in_line` (acted in line with it), `against` (acted against it), `found_again` (found it again), `did_not_apply` or `cannot_tell` |
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
It is seeded (each rate has its own stream), prints JSON or a table, and writes no file.
`simulate-withholding --pilot REPORT` takes its inputs from a pilot report (below) in place
of the gate's numbers and refuses a flag for any of them (`--touched`, `--touched-ends`,
`--missed`, `--missed-ends`, `--wrong`, `--base-wrong`, `--rho`). It requires `--price`, the
pilot's own dollars per start (play and recall) from its record; the search settings stay
flags.

### The withholding pilot's analysis (`withholding-pilot/1`)

`pilot RUN --runs PACKAGE...` reads a judged run of blind packets over the pilot's starts
and writes `RUN/pilot.json` ([#638](https://github.com/CVX-Hull/enactive/issues/638)). The
rule below is fixed before any pilot start is played
([#619](https://github.com/CVX-Hull/enactive/issues/619)); a change to it is a new version.

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

**Isolation.** The tool writes packets, events and statistics only into its run
directory, and refuses a run directory whose parent is not named `memory-measure`; by
convention that is `.runtime/memory-measure/<run>/`. The anchor never writes into the gate
it reads. It does not check where the lead saves a judge's answers, and it does not keep a
judge from the mappings in the run directory's `private/` folder: the lead gives a judge
its packet directory and nothing else. An evaluation record holds no judge event, so the
viewer cannot serve one. The curator's trace is projected by allowlist from named session
directories, a run package freezes a closed set of files, and the import contracts forbid
the player, the curator and the trace projection from importing evaluation code or tools.

The owner's labels of the anchor set are the measure gate's sealed `labels.json`
(`owner-labels/2`, described in the [measure gate](../acceptance/2026-11-13-memory-measure-gate.md)
and its commit); the anchor reads only that format. No owner labels are made after it, by
the owner's decision.

## Tracked run ledger and metrics snapshot

Development-run quantities live as data in git, and pages render them or cite them
(S-EVIDENCE). Both files hold no local paths, ports or secrets.

| File | Format | Written by |
| --- | --- | --- |
| `runs.jsonl` | One [`dev-run/2`](../../schemas/dev-run.schema.json) row per admission: study issue, run, label (the run's short name in its study's dated record), arm, start, lineage, admission, session, source commit, UTC end, receipt outcome, charged attempts, wall seconds, and spend as decimal strings | `tools/run_ledger.py record`, from the package's `campaign-run/7` manifest and `campaign-receipt/5` alone |
| `run-metrics.jsonl` | One [`run-metrics/1`](../../schemas/run-metrics.schema.json) row per session and evaluator core and binding version: the headline metric values, copied verbatim from the evaluation record | `tools/evaluate.py evaluate-table RECORDS --snapshot data/evaluation/run-metrics.jsonl` |

- **Origin.** `record` reads `campaign-run/7` packages with a `campaign-receipt/5` only;
  there is no reader for older manifests or receipts, and the rows already in the ledger
  were migrated once from `dev-run/1` to `dev-run/2`: recall counts/bounds are zero/`"0"` for recorded splits and null/null for unknown splits. There is no runtime converter. It takes `provider_usd` from the receipt's `reported_usd`,
  `unpriced_attempts` from `unpriced_requests`, `unpriced_attempt_usd` from
  `unpriced_request_usd`, the recall fields from `unpriced_recall_requests` and `unpriced_recall_request_usd`, and `spend_usd` from `spent_usd`; no figure is typed in. A
  receipt whose `spend_complete` is false gets a row only with `--record-upper-bound`:
  `provider_usd` is then the receipt's `spend_limit_usd`. The player unpriced count is `min(1, attempts)`; the recall unpriced count is 1 only when delivered knowledge has units and at least two attempts were charged. Their bounds come from the receipt, and the combined unpriced count never exceeds attempts, so `spend_usd` is the most the run can have spent. No field marks such a row; its run's dated record does
  ([campaign procedure](../operations/campaign-run.md#start-and-close)). Rows whose packages are
  `campaign-run/4` take arm and start from the labels in the archive index,
  `archive-sessions.json`.
- **Spend.** `spend_usd` is an upper bound for the admission rule, not an invoice. It is
  `provider_usd` plus `unpriced_attempts` × `unpriced_attempt_usd` plus `unpriced_recall_attempts` × `unpriced_recall_attempt_usd`. An earlier row with an unknown split
  holds null in all five fields and `spend_usd` at the receipt's configured estimate verbatim
  (including its floating-point digits).
- **Rejection.** A row without `schema: dev-run/2`, a schema violation (a label is required),
  a repeated study and run, a repeated session, more combined player and recall unpriced attempts than charged attempts, or an
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

## Spectator view API (`spectator-view/1`)

All routes are `GET`, return JSON with `"schema": "spectator-view/1"` unless noted, stay
under 4 MiB, and write nothing. `<run>` is a session ID. Lists paginate with
`after`/`limit` (`limit` ≤ 500).

| Route | Returns |
| --- | --- |
| `/api/view/runs` | One summary per known run: facts, state (`live` only for the run this viewer evaluates; `unfinished` for any other run whose store is still `live`, because its final pass never ran; otherwise `final`; `versions.state` and the summary's `state` stay the store's own `live` or `final`), outcome (hours, died, `censor_reason`), decisions, dollars, headline metrics, versions. Built by scanning record stores read-only and cached in memory. |
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
| `/api/view/frame/health` | The spectator frame's health strip (`spectator-frame/1`, below) |
| `/api/view/frame/containers?after=&limit=`, `/api/view/frame/containers/<container_id>` | The container inventory and one manifest (`spectator-frame/1`, below) |
| `/api/view/frame/episodes` | The tracked forgetting episodes with anchors resolved to runs and frames (`spectator-frame/1`, below) |

### Spectator frame (`spectator-frame/1`)

The `/api/view/frame/*` routes are the spectator's frame
([ADR 009's spectator redesign](../decisions/009-curated-player.md#spectator-d18)). They follow the rules above (`GET` only, under 4 MiB, nothing written) but carry
`"schema": "spectator-frame/1"`. Errors keep the `spectator-view/1` envelope. They read
tracked data and the catalog's stores, and nothing they compute reaches the player or the
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
  - Every other slot is
    `{"state": "not-yet-measured", "phase": "curator-and-memory" | "programs-and-monitor"}`
    and carries no number until the phase that delivers it. `phase` names the
    [ADR 009 phase](../decisions/009-curated-player.md#phases); the page shows it as words
    ("arrives in the curator and memory phase").
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
  Each poll re-checks every anchor's frame digest. That is cheap at the current dozen anchors, and
  it is the cost to revisit when lineages grow.

The gateway forwards only the statuses listed in the
[observer component](../components/observer-operations.md#viewer), so a `500` from these
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

**Pause.** The gateway's Pause asks for `{"reason": "loop" | "fault" | "spend" | "other"}`
but never refuses a stop over it. It stops first (the Pause flag, the guardian datagram,
then `{}` to the custodian unchanged), and records the reason as given when valid, else
`unspecified`. Only a malformed datagram or an unknown reason on the guardian's own
datagram ends supervision as `invalid_pause_reason`. The watch terminal record holds
`pause_reason`. Pause never waits for the viewer.
