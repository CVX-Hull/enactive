---
owner: lead
review_trigger: Changes to tools/evaluate.py diagnostics, tools/memory_measure.py, tools/knowledge_export.py or tools/process_measures.py
status: active
---

# Measurement tools

This contract covers offline diagnostics, judging and process measures. The
[withholding study contract](withholding-study.md) covers the study's commands and
file formats. Every value these tools report is interpretive and none reaches the
player ([evaluation record](evaluation-record.md)).

## Diagnostics owned by this contract

`tools/evaluate.py` also prints two read-only diagnostics. They report recorded intervals and
counts, are interpretive like every value these tools report, and give no verdict. The evaluator reuses
their numbers for latency and delivery counts.

| Command | Output format | Reports |
| --- | --- | --- |
| `host-summary` | `host-analysis/1` | Per `host.jsonl` trace: coverage (`player_host`, `empty`, `unsupported_format`, `unsupported_version` or `invalid`), request attempts and censoring, host time and request share, and distributions (count, sum, p50, p95, max) of response, tool, timing, usage and context figures. Per trace, per run directory and for the whole selection, `response_by_prompt`: response time (count, p50, p95), the share within 2 s and within 5 s and the mean provider-reported cost per request, for all responses and by prompt-size band (input plus cache read plus cache write tokens: under 20,000; 20,000 to 60,000; 60,000 to 100,000; 100,000 to 150,000; over 150,000), and the interval from one request's first tool result to the next. `prompt_composition`: per trace one object, per run directory and for the whole selection a list with one object per route (the host's `model`). It says what the prompt is made of, fitted by least squares on the growth in prompt tokens between consecutive requests of an actor against what was added, from the provider's reported `usage` and the trace's own sizes alone, so it holds for any model that reports usage. An object has `pairs` (fitted), `left_out`, `image_counts` (histogram of images per fitted pair), `image_term_separable`, `images_per_turn`, `usage_fit`, `usage_fit_reason` and `tokenizer_check`. `usage_fit` has `per_result_byte` (tokens per byte of tool-result text: the `content` text the model reads, in the short form or the full one, never `structuredContent`), `per_output_token` (per output token of the previous reply, reasoning included), `per_image`, `per_turn_constant`, `per_turn_at_modal_images`, `residual_abs` (p50, p95, share within 5 tokens) and `pairs`. Every eligible pair is fitted; the image count is a term of the fit whenever it varies, so a turn with another count has its own intercept and does not bend the byte slope. `per_image` and `per_turn_constant` are numbers only when at least 10% of the fitted pairs have a count other than the most common one (`image_term_separable` true). Otherwise (`image_term_separable` false) they are null, because the image term cannot be told from the constant, and the supported figure is `per_turn_at_modal_images`, the constant plus `images_per_turn` (the most common count) images; it is null when they are separable. `left_out` counts the pairs not fitted, by `usage_unknown` (a prompt size or the reply's output is unknown), `projection_unknown` (only one of the two requests has an image projection event), `images_dropped` (the host dropped images between the two requests), `notice_added` (a `tail-notice` or delivered knowledge reminder on the second) and `not_one_call` (the reply did not make exactly one call with one result). `usage_fit` is null, with `usage_fit_reason`, when there are no more pairs than terms or the terms are not independent (for example every result has the same length). A tokenizer is only an optional check: `python -m tools.host_analysis PATH... --tokenizer [ROUTE=]ENCODING` (or `host_summary(paths, tokenizers)`) fills `tokenizer_check`, otherwise null; it fits the growth on that tokenizer's count of the result text, the reply's visible output tokens and its reasoning tokens (with the same image treatment) and reports `slope` (`per_result_token`) and `holds`: the slope is within 1 ± 0.01 and the median absolute residual is at most 1 token (this reader's stated limit; the recorded medians for `o200k_base` were 0.2 and 0.1). A tokenizer that is not installed, cannot be loaded or whose counting function raises gives `available: false` and a `reason`, and a degenerate fit gives a `reason` and no `slope`; the usage fit is unaffected. The command exits 2 when a `ROUTE` names no selected trace. `--format markdown` prints the tables. |
| `control-summary` | `control-analysis/1` | Per `computer-session/1` database: original native dispositions and the timing distributions between intent, send and receipt. |
| `python -m tools.memory_measure` | files under `.runtime/memory-measure/<run>/`; text, or `--json` | The memory measure. `packets use` and `packets blind` build packets for model judges from sealed admissions and a `judged-facts/1` file, cut to a token budget; `events` validates a judge's answers into `judge-events/2`; `agreement` adjudicates two judges with a third on disputes; `measure` reports the standing use measures (`memory-use/1`). `packets annotate` and `items` build a matched list of facts two annotators saw. `anchor packets`, `anchor events` and `anchor report` re-judge the measure gate's owner-labelled pairs with its frozen prompt; `prompt-check packets` and `prompt-check report` compare the first two judges' agreement on frozen stretches before and after a prompt change. `simulate-withholding` sizes and prices withholding within each start (`withholding-simulation/1`); `pilot` writes the withholding pilot's unit-level analysis (`withholding-pilot/1`). It calls no model and spends nothing; see [judge events](#judge-events-judge-events2). |
| `python -m tools.process_measures` | files under `.runtime/memory-measure/<run>/`; text, or `--json` | The game-neutral process measures: `milestones packets` and `milestones events` freeze each admission's milestones; `packets`, `events`, `agreement` and `measure` judge windows and report `process-measures/2`. It calls no model and spends nothing; see [process measures](#process-measures-process-measures2). |
| `python -m tools.memory_reads` | text, or `--json` | For sealed historical traces, per memory read (`player_memory_query`, `player_memory_read`, `player_memory_context`) in `player-host` traces: the records returned, whether the reading actor already held each, each record's age, and the actor's calls before and after, with later calls that type a record's words, fetch a source it cites or name it marked as references. It lists and counts; it does not judge use. |
| `python -m tools.memory_screen_checks` | text, or `--json`; `schedule` writes `curator-coverage-schedule/1` | Four subcommands for the [proposed coverage-gated cut](../design/coverage-gated-context-cut.md). `store`: every published version of a curator knowledge repository, read from the repository's loose objects without a Git process: its session, its facts and articles (all and current) and bytes, and the facts whose text matches a pattern. It reads `curator-knowledge/3` repositories of `curator-fact/4` records only and refuses any other, so the sealed stores of the memory screen's gates are not read. `replay`: for a known loss, the request that returned the frame at which play needed the fact, when the player's record was written, and an estimate labelled “publication timing only” for curated facts. The estimate assumes publication is enough for delivery and omits the receiving admission’s world. `cut`: a simulation of the design's cut over the recorded request sequences for assumed curator lags, with tokens per turn and the marks as options (the high and low marks count tokens above the briefing); `--coverage` is `steady`, `sessions` or `schedule`, `--coverage schedule --schedule FILE` replays one run's recorded covered prefix in place of the lag rows ([schedule replay](#runner-records-and-schedule-replay)), and `--recorded-deliveries` reads per-actor starting briefings and delivered mid-run updates and reminders from `host.jsonl` (requiring `--briefing-tokens 0`). Its `recorded` row is from the traces; every other row is simulated, not measured. `schedule RUN [--output FILE]` (a FILE outside RUN): that run's covered prefix from `curator-runner/polls.jsonl` and the final `status.json`, as a schedule. |

## Trace projection

The [projector](../../harness/trace/projection.py) writes `trace-projection/3`.
The manifest lists SHA-256 digests of the projected payload files, the exclusions
and one entry per session. Each entry has a unique directory `name` and unique
sealed `session_id`, actor and handoff lists, and nullable `world`, `lineage`
and `admission` labels.

The projector reads the run's `manifest.json` and `watch-start.json` directly.
It checks both session IDs against the store and the manifest bytes against the
SHA-256 in the `campaign-watch-start/4` record. A verified `campaign-run/12`
manifest supplies world, lineage and admission. A verified `campaign-run/10`
manifest supplies lineage and admission and leaves world null. A save path supplies
no world label. Missing or invalid evidence leaves all three labels
null. `label_check` is `manifest-schema` for a package file, schema or label error,
`manifest-session` for a package session mismatch, or `supervisor-digest` for a
launch-record or digest error. `label_error` gives a fixed explanation. Both
diagnostics are null on success.

| Payload | Fields or contents |
| --- | --- |
| Frames and per-actor steps | Verified PNGs. Each step records `seq`, `operation_id`, `kind`, `created_wall`, allowlisted `actions` (including wait duration), `status` and `frame`. |
| Per-actor tool calls | `tool`, `wall_time`, arguments allowlisted for that tool, and named outcome fields. Refused and unfinished calls carry their respective flags. |
| Actor inputs and outputs | Prompt, working guide and final report when present, plus allowlisted sealed handoff fields. |
| Optional store | Historical `memory.json` or current `journal.json`, as described by the [evidence readers](../components/curator.md#projection-and-evidence-readers). |

The [curator window](../../harness/curator/window.py) exposes the directory name,
world, lineage, admission and both diagnostics by sealed session ID through
`positions(...).sessions` or `session_labels(manifest)`. A frame position has
`session`, `actor`, `step` and `order`.

## Runner records and schedule replay

Under `curator-runner/`, `examined.jsonl` records a session's start and end, its
actor and step range, both operation endpoints on the start row, and coverage at
each boundary. The end row gives the outcome and whether the cursor advanced.
`versions.jsonl` records the publication interval, stamp and restore information.
`polls.jsonl` and terminal `status.json` supply the recorded schedule. The
[runner](../../harness/curator/runner.py) defines the record shapes and the
[curator component](../components/curator.md#publication-and-coverage) defines coverage.

For frame age, match the evaluator's operation by ID and use the source's
`received_wall` in the sealed session store. A step without a frame has no frame age.
A fact's [`seen` position](../design/world-scoped-memory.md#the-format-curator-fact3)
gives sighting order.

The [schedule reader](../../tools/memory_screen_checks.py) joins the recorded
prefix to operation-creating calls in the sealed host log without opening the session store. Retries count as one
player request. A prefix covers a request once it includes the last operation
that request created. It covers all requests of earlier actors. An unplaceable
change is omitted, except that an unplaceable restore clears coverage.

An advance applies to requests starting strictly after the row that shows it.
This may be later than publication. A newly observed restore applies at the preceding row's time
(or its own time for the first row), including requests that start at that time.
A request without a start time inherits the previous request's coverage for its
actor, initially zero.

With `--recorded-deliveries`, `cut` reads `knowledge-delivery` events from each
actor's `host.jsonl`, estimating tokens at four UTF-8 bytes per token (`ceil(bytes / 4)`).
An actor's `briefing` events set that actor's starting briefing size (zero when absent,
such as an empty `v0` start, and fresh for a successor actor after handoff). Delivered
`update` events (`outcome: "delivered"`) and `reminder` events are assigned to their
`receiving_player_request_id`'s logical player request (matching retries and skipping
recall requests), adding their tokens on that request and releasing them when a cut
removes that turn. Refused updates and `knowledge-undelivered` events add no tokens;
deliveries whose receiving request matches no logical player request are counted as
unmatched. In every mode, `high_mark` and `low_mark` count tokens above the actor's
briefing size per the [context-cut design](../design/coverage-gated-context-cut.md#the-cut).

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

The facts builder and pilot read `campaign-run/12` and indexed `campaign-run/10`
and `campaign-run/7` evidence. For `/12` the facts builder also verifies the
[private selection](player-host.md#delivered-knowledge-and-recall) against the
package's world and delivered file digest, and expects `delivered-knowledge/2`; the
archive versions predate that field and keep `delivered-knowledge/1`. The builder
refuses a `/12` run that sets [`live_knowledge_updates`](../operations/campaign-run.md#live-knowledge-updates):
its judged facts are the frozen file's, and a version adopted during play delivers
facts outside it.

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
