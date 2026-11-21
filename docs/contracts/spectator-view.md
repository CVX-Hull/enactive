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

- **View request rules:**
  - A `limit` outside 1–500 returns `400`.
  - The context route accepts `?actor=` and returns `409` when a request ID is ambiguous across actors.
  - The compare route accepts `horizon` in game hours, default 0.5.
  - Runs resolve by session ID or run directory name.

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
