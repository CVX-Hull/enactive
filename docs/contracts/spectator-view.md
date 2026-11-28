---
owner: lead
review_trigger: Changes to view routes, forwarding or Pause advice in harness/viewer/, tools/campaign_watch.py, tools/campaign_supervision.py or web/
status: active
---

# Spectator view

This contract covers the control path, the read-only spectator API and the viewer's Pause conditions.
Every value the view shows is interpretive and none reaches the player
([evaluation record](evaluation-record.md)).

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
- the viewer's `200`, `400`, `404`, `405`, `409` and `413` pass through unchanged, and any other
  status is a forwarding failure;
- the gateway's own security headers on every response.

A viewer response with a disallowed media type, invalid `Content-Length` or body over
the size cap returns `502` with `{"error": "Viewer response refused"}`. A refused
connection, timeout, unlisted viewer status or unavailable forwarding slot returns
`503` with `{"viewer": "unavailable"}`. The page polls and treats both as “viewer unavailable”.

**Launch and lifetime.**
- The supervisor starts `python -m harness.viewer` as an **unsupervised** child on a free
  loopback port with the live run directory and evaluation root (`.runtime/evaluations`).
  It can also pass archived run directories, labelled curator draft directories, result and session files,
  and the configured runner's status file.
- A launch failure or exit leaves the run running. The supervisor stops the viewer at
  the end and records its port in `campaign-watch-start/4` and its child entry in
  `campaign-watch-terminal/4`.
- The viewer evaluates the live run incrementally and writes only its `live` evaluation store.

- **View request rules:**
  - A `limit` outside 1–500 returns `400`.
  - The context route accepts `?actor=` and returns `409` when a request ID is ambiguous across actors.
  - The compare route accepts `horizon` in game hours, default 0.5.
  - Runs resolve by session ID or run directory name.

<a id="spectator-view-api-spectator-view3"></a>

## Spectator view API (`spectator-view/4`)

All viewer routes are read-only and use `GET`. Every JSON response from the viewer
under `/api/view/*`, including errors, carries `"schema": "spectator-view/4"`. The frame
route returns PNG on success. The 4 MiB cap applies to both formats. Use the session ID
for `<run>`. Paginated lists accept `after` and `limit` (1–500).

Unmatched paths under `/api/view/` return `404` with `error: "not_found"` and
`detail: "route not found"`. Unsupported methods on a matched view route return
`405` with `error: "method_not_allowed"` and `detail: "method not allowed"`. Both
use the viewer JSON error envelope and the viewer's `no-store` and
`nosniff` headers. Static routes keep their own responses.

| Route | Returns |
| --- | --- |
| `/api/view/runs` | One summary per known run: facts, state (`live` only for the run this viewer evaluates; `unfinished` for any other run whose store is still `live`, because its final pass never ran; otherwise `final`; `versions.state` and the summary's `state` stay the store's own `live` or `final`), outcome (hours, died, `censor_reason`), decisions, dollars, headline metrics, versions. Scans record stores read-only and caches the catalog. Skips stores with a non-current core. `skipped_non_current` counts sessions with older or otherwise non-current stores and no current Core 4 store. |
| `/api/view/run/<run>/summary` | Facts, evaluator outcome, recorded `custodian_receipt`, Pause conditions (below), game state with provenance, findings, ladder, metrics with `source`, `count`, `denominator`, `missing`, and reader coverage with held-out validation status. [`evaluator_freshness`, `latest_step_seq`, `agenda`, `host_telemetry`, `curator_spend` and `boundary_grooming`](#host-telemetry-and-curator-spend) |
| `/api/view/run/<run>/feed?after=&limit=` | The [story feed](#story-feed): steps, context cuts, coverage waits, knowledge deliveries, agenda changes and findings in one order |
| `/api/view/run/<run>/telemetry` | The [request series](#request-telemetry), context cuts, coverage waits, costly requests, curator sessions, handoffs, service tiers and spend |
| `/api/view/run/<run>/delivered-knowledge?version=&q=&scope=&kind=&after=&limit=` | The [knowledge versions exported for the player](#delivered-knowledge) and one version's articles and facts |
| `/api/view/run/<run>/steps?after=&limit=` | Steps: `seq`, `decision`, `wall`, `kind`, `mode`, `game_time`, `source_id`, `frame_changed`, `dollars`, `keys` |
| `/api/view/run/<run>/frame/<source_id>` | The [verified original PNG](#recorded-frames) (`image/png`) |
| `/api/view/run/<run>/tools` | Per-tool aggregates (calls, p50 and p95 latency, refused, errors, result bytes) and transitions `[from, to, n]` |
| `/api/view/run/<run>/calls?tool=&status=&after=&limit=` | Tool-call rows, each with the step it produced (and its frame) where one exists |
| `/api/view/run/<run>/requests?after=&limit=` | Request rows, plus eviction and handoff markers |
| `/api/view/run/<run>/context/<request_id>` | Ordered parts replayed from the manifest (`exact: true`). Without a manifest: frozen inputs plus recorded tool results (`exact: false`). |
| `/api/view/archive/run/<run>/memory` | Recorded player rows, sources and audit labels from a configured store. An available current journal projects hints and public reports. |
| `/api/view/run/<run>/knowledge?actor=&request=&entry=&after=&limit=` | Actor/request selection, recorded knowledge selection/delivery, verified frozen snapshot entries, explicit reads and public reports, linked mechanical results and separately labelled evaluator outcome |
| `/api/view/run/<run>/handoffs` | Handoffs with position, decisions to resume, carry ratio, carry text, `carried_agenda` and identity check |
| `/api/view/improve/changes` | Change records with per-run target, uptake and guard values for each arm, and bootstrap intervals |
| `/api/view/improve/failures` | Failure modes from derived events and human labels: occurrences, runs, decisions and dollars inside, source |
| `/api/view/compare?group=arm\|start&runs=` | Per group: n, deaths, censored, Kaplan–Meier with Greenwood bounds, median or `not_reached`, restricted mean to the stated horizon with a bootstrap interval, excluded runs, version facts |
| `/api/view/explore?arm=&start=&outcome=&metric=` | Cohort rows; the metric's n, median, IQR and bootstrap interval for the median (n ≥ 5); the 12 decisions before each death |
| `/api/view/run/<run>/curator` | [Runner status](#curator-runner-status), spend, compact sessions, grooming and run-filtered gate verdicts and drafts |
| `/api/view/run/<run>/curator/session/<session_id>` | [Bounded session detail](#run-curator-sessions) and proxy ledger rows |
| `/api/view/archive/containers?after=&limit=`, `/api/view/archive/containers/<container_id>` | The [container inventory](#archive) and one manifest |
| `/api/view/archive/episodes` | The [tracked forgetting episodes](#archive) with anchors resolved against recorded runs |
| `/api/view/curator-sources/draft-sources?after=&limit=` | Configured draft source labels |
| `/api/view/curator-sources/drafts?source=&after=&limit=&snapshot=` | Paged active and archived [draft metadata](#curator-drafts) |
| `/api/view/curator-sources/result-sources?after=&limit=` | Configured result source labels |
| `/api/view/curator-sources/results?source=&after=&limit=&snapshot=` | One source's [submission and restore results](#recorded-curator-results) |
| `/api/view/curator-sources/session-sources?after=&limit=` | Configured session receipt labels |
| `/api/view/curator-sources/session?source=&after=&limit=&snapshot=` | One [terminal session receipt](#recorded-curator-sessions) and its paged gate results |

### Recorded frames

The frame route opens `sources/<source_id>.png` as a regular file rooted at the run
directory. Every path component, including the run directory, must be free of symlinks.
It verifies the bytes against the evaluator's recorded SHA-256 on each serve and returns
`Cache-Control: private, max-age=31536000, immutable`. Anchor availability checks cache
verification results by run directory, source ID, expected digest and file stat
(device, inode, modification time, change time and size). A changed file is checked again.

### Host telemetry and curator spend

The summary reports `latest_step_seq` (the maximum sequence in the store, or null)
and `evaluator_freshness` (`running`, `passes`, `last_seq`, `last_pass_wall`, `error`,
`finished`, or null when no evaluator status applies). `agenda` projects the recorded
initial, latest and final agenda, with tool call counts. Handoffs include
`carried_agenda` from the successor's recorded agenda files or the run's opening
agenda when available.

`summary`, `feed` and `telemetry` project the run's `actors/*/host.jsonl` with the
evaluator's own [trace](player-host-telemetry.md) parser when a request needs them. The
[evaluation record](evaluation-record.md) stores none of it. A trace that is absent,
unsupported, damaged, over 16 MiB, behind a symlink or of another session is no source:
`host_telemetry` is `null`, and the other two routes use the evaluation record alone and
say so in `source` (`host_trace` or `evaluation_record`). A last line still being written
is ignored. The viewer parses the traces once for each state of the files.

**Files of a run package.** The host traces, the delivered knowledge, the runner's status
file and the curator sessions are opened from the run directory down, one path component
at a time. A symlink at any component, the run directory included, or anything but a
regular file, is unreadable. A read stops at 16 MiB. An operator-named file is read under
the same limits and may not itself be a symlink; its directories are the operator's choice.

`host_telemetry` has:

- **Spend.** `reported_cost_usd` is the exact sum of the responses' provider-reported cost
  and `spent_usd` the hosts' own totals, both as decimal text or `null`.
  `player_requests` and `recall_requests` come from each actor's settlement, else from the
  events read. `unpriced_requests` and `unpriced_recall_requests` count the request starts
  without a priced response of the same actor and request ID, in flight or not, and are
  never below what the events show, whatever a settlement claims.
  `spend_complete` is true only when every directory under `actors/` has a readable trace,
  every actor has settled, its settlement equals the events read, every start has a priced
  response and every response a start. Otherwise the cost is a subtotal. A trace that
  records no cost field has `null` unpriced counts and completeness. The summary's
  `dollars` stays the configured-rate estimate. `spend_reserve_reached` has the
  event `count` and the `latest` event in actor and trace order, or `null`. The latest
  event has `actor`, recorded `actor_id`, `wall_time`, and decimal text or `null` for
  `spent_usd`, `spend_limit_usd`, `finish_reserve_usd` and `unpriced_bound_usd`.
- **Routing.** `response_by_endpoint` counts responses by `reported_provider`, with
  `unknown` for a response without a label. It is empty when the trace records none.
  `latest_provider` is the label of the response that completed last by its own time.
- **Context.** `context_cuts` has `applied`, `held_back` and the `latest` applied cut.
  `uncovered_cuts` counts applied cuts with positive `uncovered_turns`.
  `uncovered_turns_total` sums those recorded turns across applied cuts.
  `by_result` counts applied cuts with each recorded result (`target`, `best_effort`
  and `rescue`). The latest cut includes the four result and count fields listed in
  [Story feed](#story-feed). `tail_notices.count` counts notice events and `by_kind`
  counts each recorded occurrence of `context-capacity`, `host-timeout` and
  `spend-limit`, including repeated kinds in one event. Traces without reserve or
  tail-notice events have zero counts.
  `token_summary` has the latest, median (`p50_prompt_tokens`) and largest prompt of the
  player's own requests, and `cache_hit_share` over every response with usage, recall
  included. A prompt is `input + cacheRead + cacheWrite`.
- **Knowledge.** `knowledge_updates` has the `count` of versions delivered during play and
  the `latest_version` the player holds. `knowledge_deliveries` summarizes the
  delivery kinds in the [story feed](#story-feed). `coverage_waits` summarizes
  recorded spans, active waits, longest duration and peak tokens. `service_tiers`
  gives player response counts and the latest recorded player tier.

`curator_spend` sums the live curator sessions under `curator-runner/sessions/*/*` and is
`null` without a session directory. It uses the curator proxy's accounting. A charge can be the
reservation where actual cost is unknown. For each session it uses
`spent_snapshot_usd` from a valid `curator-proxy-close/1` closure, falling back to
the charged ledger rows and then the session summary's `cost_usd`. Without a
valid closure, the unsettled count is the greater of the summary's count and the
number of ledger rows without a charge. `spent_usd` is null when there are no
recorded amounts. `spend_complete` requires all sessions settled, no unsettled
requests and a readable inventory.
`ingestion_usd` covers recorded `admission` and `ingestion` sessions. `hygiene_usd`
covers recorded `hygiene` sessions. `hygiene_share` divides the hygiene subtotal by recorded spend only when
`spend_complete` is true and every session and hygiene pass is priced (otherwise
`null`).
`hygiene_failed` counts failed hygiene passes across all sessions before any list cap.
`applied_tiers` counts sessions per applied tier, and `deferrals` totals recorded
flex deferrals (or `null` when none are recorded), with `deferrals_complete` stating
whether every session reported a count.

`boundary_grooming` is what one operator-configured
[grooming receipt](curator.md#boundary-grooming-summary-curator-boundary-grooming2) states.
Grooming runs after an admission ends and writes outside its package, so the viewer reads
only the file that `--curator-grooming FILE` (`FrameSources.curator_grooming`) names, and
looks in no other directory. The receipt is shown only when its `run` is the summary's
session or the admission's name under `curator-runner/sessions`, or the run's own name
when there is no such session. `source_status` is `not_configured`, `available`,
`other_run`, or why the file cannot be used (`missing`, `unreadable`, `too_large`, `empty`,
`malformed` or `unsupported`). Only `available` has `status`, `reason`, `spent_usd` (proxy-accounted),
`spend_complete`, the published versions and `stale_records`. `spend_complete` needs an amount and a
settled proxy, or a skip. No path of the receipt is served.

### Story feed

The feed is one list, sorted and paginated by each item's integer `order`; `after` and
`next` are orders. An item's `id` is its identity and never depends on another item. A
step, cut, knowledge delivery or agenda change has an integer ID derived from its
actor and trace line, or step number when there is no trace. A coverage wait uses
the actor index and opening trace line. A finding is identified by its kind, first step, source and
payload as text, because the evaluator renumbers its events on every pass; a stall, whose
payload grows while it lasts, by the first three. Findings that state exactly the same
thing are numbered. A finding the evaluator adds late can move the `order` of other items
but changes no `id`, and may appear behind a cursor. The page therefore re-reads the recent
part of a live feed, and the whole feed once when the run is no longer live. A page also
ends early at 3 MiB, with `next` set. `total` and `counts` (by `entry_kind`) cover the
whole feed.

Every item has `entry_kind`, `seq`, `exact_step`, `decision`, `step_decision`, `wall`,
`source_id`, `mode` and `game_time`. `exact_step` is false when the entry made no step of
its own; `seq` is then the latest step at or before that time, and `null` with the rest of
the step's values before the first one. `decision` is the entry's own recorded one: the
call's, as in the `calls` route, else its own step's, else `null`. `step_decision` is that
of the step `seq` names, which numbers completed inputs and so differs from a call's
request number; neither replaces the other.

| `entry_kind` | Further fields |
| --- | --- |
| `step` | `tool`, `intent` (`intent_source` is `player_claim`), `keys`, `status` (`ok`, `error`, `refused` or `pending`), `latency_ms`, `arguments_preview`, the request's `reported_provider`, `reported_cost_usd` and token counts, the identifiers, and `result` (mechanical status, reason and receipt dispositions). One request may issue several calls, each carrying the request's cost |
| `context_cut` | Applied cuts with `outcome: "applied"`, `triggers`, `knowledge_version`, tokens and images before and after, `removed_turns`, `uncovered_turns` and `reason`. They can also record `cut_result` (`target`, `best_effort`, `rescue`), `cumulative_removed_turns`, `briefing_tokens` and `source_ids_count`. Unrecorded values are null. |
| `coverage_wait` | A span opens on a held-back cut. A repeated reason and covered-operation edge extends the same wait. A different edge, an applied cut, actor settlement, a handoff to a successor actor or the end of the last actor's trace closes the observed span (`ended_by` is `superseded`, `cut`, `settled`, `handoff` or `trace_end`). It remains `active` only at `trace_end`. Fields include `start_request_id`, `end_request_id`, `duration_seconds`, `requests` and `peak_tokens`. |
| `knowledge_delivery` | `delivery_kind` is `opening_briefing`, `post_cut_briefing`, `update`, `empty_suppressed`, `refused` or `undelivered`. The row carries version and request IDs, outcome, lead/index counts, and recorded delta counts and preview. |
| `agenda_change` | `request_id`, `tool_call_id`, `op`, `cut_count`, `thread_count`, `active_count` and the projected `agenda`. |
| `finding` | `finding_kind` (`stall`, `death`, `custody_stop`, `handoff` or `run_end`), `seq_end`, `source`, `payload` |

An applied cut joins a delivered post-cut briefing using the cut's request ID and
the briefing's `receiving_player_request_id` within the same actor. It exposes
`briefing` with a `delivery_id`. The delivery keeps its own ID and points back with
`joined_cut_id`. The viewer parses recorded delivery text (falling back to the event
delta) for the `DELTA_BUCKETS` `corrections`, `state_changes`, `flag_changes`,
`added_facts`, `claim_updates` and `article_changes`. Older updates can carry
`added`, `updated` and `removed`.

Intents are unverified player reports, at most 1,024 characters, with the omitted count.
Arguments are bounded JSON text (2,048 characters). A run without a trace has steps, tool
calls and findings only, with no intent, cost, cut or update.

### Request telemetry

`requests` lists each response, player and recall, with its `index`, `seq` (the latest
step at or before it, or `null`), token counts,
`reported_cost_usd` and, separately, the configured-rate `estimated_dollars`. `cuts` lists
context cuts at the `index` of the request that carried each, with the cut fields from
the story feed. Over 2,000 requests the
series is thinned evenly, keeping the requests beside an applied cut;
`requests_omitted` and `cuts_omitted` say how many are left out. `spend_reserve_reached`
lists reserve events with the same actor and amount fields as the summary, plus
`wall` and the latest `seq` at or before that time, or `null`. Both event lists
keep up to the last 1,000 entries in actor and trace order. The reserve list reports
`spend_reserve_reached_omitted`. `tail_notices` repeats the summary counts, with zeros
when no trace is available. `spend` repeats the player, limit and curator figures above.
`top_costliest` ranks up to 15 requests before thinning, using reported cost or
the configured estimate when reported cost is unavailable. `coverage_waits` lists recent
spans and exposes `coverage_waits_omitted`. `curator_sessions` contains compact session
rows. `handoffs` marks actor transitions and `service_tiers` repeats the player tier
summary.

### Delivered knowledge

The route browses the run package's own `delivered-knowledge.json` (`initial`, the version
the run started with) and `curator-runner/delivered/vN.json`, in version order. It reads no
curator repository, private export, alias map or withheld-unit file and runs no Git command.
Files are bounded at 16 MiB. Each of `versions` has its counts, coverage stamp, the version
the file itself records, and `status`; a file that is not a readable `delivered-knowledge/4`
(or `delivered-knowledge/3` strictly for the five owner-approved `#963`/`#998` sealed sessions)
is listed with its status and no counts.

- `version` defaults to the latest readable one. An unknown version is
  `404 unknown_version`; one that cannot be read is `409 unsupported_knowledge`.
  Without any file, `source_status` is `unavailable`.
- `q` (at most 200 characters) matches case-insensitively in articles and facts (including
  tags, `statement_kind`, `anchor_display`, `when`, and exact `state_key`, with exact ID or
  `state_key` matches sorted first). `scope` is `all`, `world`, `game` or `unrecorded` and filters
  facts by delivered scope class (`world` key present vs absent, or missing scope), paging
  by `after` and `limit`. `kind` filters by exact `statement_kind` on current
  facts and `claim_kind` on archived facts. Articles are bounded, with `articles_omitted`.
- Each record projects its delivered `scope` class (`world` or `game`), bounded non-world
  `scope_axes` (never exposing a world or lineage label), `tags`, `lifecycle_state`,
  `branch_relation`, review flags (`stale_citations`, `needs_review`,
  `unverified_branch`) and typed `links`/`backlinks` (`shadowed_by`, `contradicted_by`),
  plus clock labels (`clock_label` or tagged `prior_clock`) on position markers.
  Current `/4` facts also project `statement_kind`, `state_key`, `anchor` (the kinematic
  `state_key`), `anchor_display`, `when` (string), `depiction_source_id`, `cited_by_articles`
  and `citation_source_ids`. The response includes `knowledge_schema`, `scope_counts`,
  `tag_counts` (with `tag_counts_omitted`), `statement_kind_counts` (or `claim_kind_counts`
  on the five archived `/3` sessions), `frame_clocks` for shown citations, and bounded `history`.
- `frame_anchor` (on current `/4` facts, `anchor` on articles and archived `/3`
  facts) and `citation_anchors` resolve citations against the run's own steps and
  other admissions in the catalog. A local anchor gives `seq` and `source_id` for a verified frame. A cross-admission
  anchor also identifies the catalog run and session, and reports availability and
  the reason when the frame cannot be served. Anchor resolution uses the [frame verification cache](#recorded-frames).
- `version_chain` combines recorded publications, exports and deliveries. Its
  `delivery_status` distinguishes `delivered`, `refused`, `empty_suppressed`,
  `undelivered`, `superseded`, `exported_not_delivered`, `published_only` and
  `trace_only`. The selected
  version's `delivery` projects recorded delta bucket counts and previews.
- `state_groups` groups the returned facts by `state_key` with replacement history
  and omission counts. `anchor_groups` summarizes matching facts by location anchor.
  `quality` summarizes record, state and review counts and the coverage of `when`.
  Its `default_view` is `articles` if there are articles, then `state` if there are
  state keys, otherwise `facts`.

### The page: Mission Control

The page groups one selected run under **Watch**, **Memory**, **Curator** and
**Diagnostics**, with **All Runs** for Lineage, Compare, Explore, Changes, Failures
and Archive. The compact Mission Control bar keeps control status, run selection,
key run figures and Pause together. URL hashes support deep links to viewer sections.

The control path shows its own frame in full when the viewer is unavailable.
Watch may hide the duplicate only after painting the same capture of the same
session. A new undecoded capture, scrubbing, holding, or leaving the live view
brings the control frame back. Pause targets the live control session.

The spend figures distinguish player and recall (provider-reported), live curator
and boundary grooming (proxy-accounted). A combined figure identifies its
components and is partial when an included record is missing or unsettled.

### Recorded browser entry

The standalone viewer with `--recorded-page` serves the shared spectator page
at `/recorded/` and its allowlisted assets under `/app/` and `/vendor/`. The
page and existing viewer API stay on the same loopback origin. This mode reads
existing evaluation stores and recorded sources and opens Watch. Its
browser code makes viewer requests only. The supervised gateway owns live status,
native captures and Pause. See the [recorded viewer procedure](../operations/start-observe.md#recorded-browser-entry).

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
counts. Diagnostics uses the host trace's figure and this one where there is no trace,
and shows a subtotal and the unpriced counts when some charges remain unknown.
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
  and original trace line (with `outcome: "undelivered"` rows labelled as attempted
  rather than delivered in the page). An update event also has `outcome`, `previous_version`,
  its coverage marker, `removed_ids` and the `added`, `updated` and `removed` rows of
  its text. Selection, delivery and an explicit read are distinct.
  Missing delivery text or a missing join stays unavailable; proximity proves no use.
- `snapshot_status` is `verified`, `unavailable`, `hash_unavailable` or
  `hash_mismatch`. Entries are served only after the actor's `player-host-inputs/5`
  `frozen.json` names this actor/session and its `delivered-knowledge.json` digest
  matches (`delivered-knowledge/4` for current `campaign-run/14` packages). Archived
  `campaign-run/13` sessions listed in `data/evaluation/archive-sessions.json` (the five
  owner-approved `#963`/`#998` runs) use `player-host-inputs/4` with `delivered-knowledge/3`;
  sealed archived sessions before `/12` use `player-host-inputs/3` with `delivered-knowledge/1`;
  a sealed `campaign-run/12` run (whose snapshot is `delivered-knowledge/2`) or a run
  with no supported manifest reports explicit `hash_unavailable` and never falls through
  to `delivered-knowledge/1`.
  Missing/mismatched bytes are never presented as the frozen contents.
  The snapshot is the version the actor started with, never one adopted during play.
  The `delivered-knowledge/4` snapshot exposes only public article/fact fields (including
  scope class, non-world axes, `statement_kind`, `state_key`, `anchor`, `anchor_display`,
  `when`, `depiction_source_id`, `tags`, lifecycle/review flags, typed links/backlinks,
  `citation_source_ids`, coverage, `frame_clocks`, bounded `history` and confirmation markers
  in their recorded units) and supports `entry` lookup by ID or `state_key`. It pages `items` with
  `total`, `limit` and `next`. An absent entry is unavailable, not proof of withholding.
  No private full export, withheld-unit file or curator repository is read.
- `calls` expose public intent/cites, knowledge query/read `returned_ids`, status and
  explicit operation/source/step IDs, allowlisted tool-result status/reason/delivery/resolution,
  and original operation status/receipt dispositions. `returned_hits` carries the first
  20 compact `player-knowledge/4` query hits (or `/3` on the five archived `#963`/`#998`
  sessions) with string IDs, in returned order, with
  `returned_hits_omitted` counting the rest. Each hit exposes bounded `id`, `kind`,
  `title`, `subject`, `via` (`match`, `hop` or `fuzzy`), `snippet`, `status`,
  `cited_by_articles` and current fact metadata (`statement_kind`, `state_key`, `anchor`,
  `anchor_display`, `when`, `depiction_source_id`).
  Calls without compact hits have an empty list and zero omitted. Intent, hints and finish
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

For a `player_source` call with a `player-source-read/2` result, the call projection
includes `player_alias`, `non_clickable` (reflecting the recorded `clickable` boolean,
or `null` when unrecorded) and the recorded origin. The separate
`anchors` array resolves a real source ID against its catalog admission and
reports whether the verified frame is available. An alias alone cannot supply a
frame link.

### Recorded curator results

The *Curator results* source reads only operator-configured result files. Repeat
`--curator-results LABEL=FILE` on the supervisor or standalone viewer CLI to select
existing `gate.jsonl` files or immutable snapshots. Labels are unique, match
`[A-Za-z0-9][A-Za-z0-9_.-]{0,127}` and are the only source selectors exposed to the
browser. The default has no sources. A label is operator-supplied identity, not
verification of game/fork identity or a link to a player run. The supervisor forwards
these arguments only to its unsupervised viewer child; they grant no input authority.

The result sources route pages `items: [{label}]` with
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
  bounded `diagnostics`. When the gate records draft IDs, `from_drafts` lists the first
  100 in recorded order and `from_drafts_omitted` counts any excess. The same fields
  appear on session verdict rows. Only the exact [`curator-gate/2`](curator.md#gate-result-curator-gate2)
  shape and its operation, status and null conventions are accepted, with no alias or
  historical converter.
- Text, identifiers and lists use the existing bounded omission conventions. An overlong
  identifier is omitted, never shortened into another ID. Whole free-form references and
  diagnostics containing `/` or `\` are withheld as path-like detail, with
  `path_details_omitted` and identifier omission metadata. This also hides benign text
  with separators; the source stays available for local inspection.
- A row reports what the gate recorded. It shows neither semantic verification nor the
  repository's present head, and no delivery or use. Restore, unchanged and submission
  results stay distinct, null and unknown versions stay explicit, and nothing else is
  inferred: no time, pass rate, lag, age, health value or run.

The reader serves no raw paths, briefs, transcripts, submission bodies, drafts,
credentials or arbitrary repository files. It writes nothing, imports no curator runtime
and sends nothing to the player or curator. The page provides source selection,
result rows and detail with escaped content and keyboard controls. It reads no submission
text, draft contents or current draft states. A source change resets a stale selection; the control frame and Pause continue
on their own path. Fixture and rendered checks establish this reader's behavior only.

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

### Curator drafts

Repeat `--curator-drafts LABEL=DIR` on the supervisor or standalone viewer to
configure curator state directories. Labels follow the [result-source rules](#recorded-curator-results)
and the supervisor forwards the arguments only to the viewer. The source list exposes
labels with `items`, `total`, `next` and `limit`. Drafts and gate records are separate
operator-selected views, independent of delivered knowledge and run selection.

The viewer reads only `drafts/<draft_id>/manifest.json` and
`drafts-archive/<draft_id>/manifest.json` beneath the configured directory. It opens
the configured directory and its entries without following symlinks, reads at most
16 MiB plus one byte per manifest, and uses no producer lock. It accepts
`container-manifest/1` for curator-owned drafts whose ID matches the directory name
and whose lifecycle state matches the bucket.

The response includes `source`, `source_status`, `snapshot`, `items`, `total`, `next`
and `limit`. Items are ordered by directory bucket and draft ID. Each item exposes
`id`, `bucket` (`active` or `archived`), `state` (`open`, `stale`, `promoted` or
`abandoned`), `untouched_sessions`, `created_by_session`, `last_touched_session`,
nullable `promoted_by_session`, `sessions`, `max_bytes` and `retention_policy`.
Text omits path-like or oversized values. `sessions` uses the bounded list shape
`{items, omitted, values_omitted}`. Draft bodies and raw manifest metadata stay private.

- `available` means valid manifests were read. `empty` means the readable directory
  had no manifests. `missing` means the configured directory is absent. `unreadable`
  covers directory or manifest I/O failures and symlinks refused along the read path.
  Oversized manifests are `too_large`, invalid JSON is `malformed`, and invalid schema,
  identity, lifecycle or metadata is `unsupported`. Failure statuses return no rows.
- `snapshot` is `null` for `missing` and `unreadable`. Otherwise its `sha256` hashes the
  sorted `(directory bucket, draft ID, manifest SHA-256, bytes read)` entries as compact
  JSON lines, and `bytes` sums manifest bytes read. An oversized manifest contributes
  only its bounded prefix to this fingerprint. Draft body changes do not affect it.
- Bad paging or digests return `400`. `after > 0` requires a `snapshot` digest.
  An unknown label returns `404 unknown_source` and a changed digest returns
  `409 source_changed`. The page offers a refresh from the first page.

### Curator runner status

The `runner` object from `GET /api/view/run/<run>/curator` reads the selected run's
`curator-runner/status.json` per request. Only the live run can fall back to the file
named by `--curator-runner-status FILE`, and only when its own status is missing.
The supervisor passes the live package's own status file when it starts a runner.
The runner replaces it atomically at polls and session boundaries. The file records
the curator's progress. Exports and actual deliveries are recorded separately in
[delivered knowledge](#delivered-knowledge) and the [story feed](#story-feed).

The reader returns `source_status` (`available`, `not_configured`, `other_run`, `missing`,
`unreadable`, `too_large`, `empty`, `malformed` or `unsupported`), `snapshot`
(`sha256` and `bytes` when available), `read_wall` and `status`. When the file
is unavailable, `status` is null. For a readable status, `status_schema` identifies
the producer format. Current files use [`curator-runner-status/2`](curator.md#live-runner-status).
Archived `curator-runner-status/1` files still project recorded values. The viewer
leaves unrecorded `limits`, `failures.hygiene` and `failures.flex_deferrals`
unpopulated (null).

The projection includes the runner's session, state and timestamps, settings,
last observed position and snapshot timings, current session, covered prefix, lag,
stamp distance, backlog and failures. `last_confirmed` and `latest_version`
include the runner's recorded `baseline` flag. `examined` and `unexamined` give
`items`, `total` and `omitted` for the latest 100 examined and first 100 unexamined
ranges. `unexamined` is null before stop or end, and `unconfirmed` is the count
of publications the runner could not confirm. `after_last_read` stays `unknown`.
The projection withholds path-like or overlong identifiers and gives
`omitted_characters` for withheld fields.

### Run curator sessions

The viewer stat-caches compact rows for the selected run's
`curator-runner/sessions/<group>/<label>/` files. The curator response returns up to
500 recent rows in `sessions`, with `sessions_omitted`, `spend` and `grooming`
(including `stale_records` when recorded). Compact rows give recorded session
kind, coverage window, spend and settlement, service tiers, deferrals, verdict
counts and draft counts. The viewer withholds host paths.

`gate_verdicts` selects configured `gate.jsonl` rows whose `session` belongs to
this run. `drafts` selects drafts associated with those same session IDs through
recorded session provenance, creation, last touch or promotion. The viewer takes
the IDs from the run's session summaries and examined runner entries. Each result
has `filtered_to_run`, `total_lineage`, `items`, `total` and `omitted`.
The full configured lineage sources are available at `/api/view/curator-sources/*`.

`GET /api/view/run/<run>/curator/session/<session_id>` accepts the recorded session
ID, `<group>:<label>` or a session label within the run. It returns `session` with
bounded tokens, tool calls, sandbox disposition, errors, refusals, verdicts, draft
events and proxy accounting. `ledger` projects allowlisted rows from complete
lines of `proxy-ledger.jsonl` with timings, recorded model and tiers, status,
reservation, charge, refusal and usage. `ledger_total` and `ledger_omitted` count
the rows and those left out. Host paths are withheld in both projections.

<a id="spectator-frame-spectator-frame1"></a>

### Archive

The archive routes read tracked containers and forgetting probes, and can project
player records from a selected run. The container and probe roots default to
`data/containers` and `data/evaluation/probes`. Tests can override them with
`create_app(frame_sources=)`.

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
  Anchor checks reuse the [frame verification cache](#recorded-frames).

The gateway forwards only the statuses listed under
[Control path and viewer](#control-path-and-viewer), so a `500` from these
routes reaches the page as "viewer unavailable".

## Pause conditions

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
