---
owner: harness maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# One finite campaign run

One [campaign custodian](../../tools/campaign_run.py) owns fresh mechanical target,
store/server lifetime and final cleanup. The [driver](../../tools/campaign_player.py)
owns the frozen [player host](../contracts/player-host.md)/MCP groups and at most one
successor. The [package validator](../../tools/campaign_package.py) is authoritative
for the closed `campaign-run/14` admission. Admission is that package check alone: it reads
no game phase or identity, and no semantic mission service exists.

A run is launched through [the maintained supervisor](campaign-supervision.md),
which wraps this same custodian.
The supervisor owns its wrapper processes, the custody deadline and Pause; native/actor custody
and original package allowances remain here. Its receipt does not accept gameplay.

## Frozen data

Select one fresh canonical project-local directory under `.runtime/computer-sessions/`.
Its manifest binds the exact clean source commit and SHA256 of eight required inputs
(`route.json`, `mcp-template.json`, `context.txt`, `prompt.txt`, `target.json`,
`delivered-knowledge.json`, `source-index.json` and `agenda.json`). The seven inputs
other than `delivered-knowledge.json` are each at most 1 MiB. Create the knowledge file in the
[export step](#freeze-delivered-knowledge), including for empty knowledge, alongside the
frozen same-lineage `player-source-index/1` (`source-index.json`) and starting
`player-agenda-continuation/1` (`agenda.json`, empty when starting fresh).
It also freezes native executable/adapter bytes, bounded initial target files,
shared-lock path, explicit `player-journal/1` store (`player_store`), player host argv, effort,
loopback port, original wall/host/aggregate-host seconds, one/two-host limit,
computer input/request/frame/byte capacities,
`ending_reserve`, the dollar limit `spend_limit_usd`, whether
[newer knowledge versions reach a running actor](#live-knowledge-updates)
(`live_knowledge_updates`) and the operator-only [`labels`](#operator-labels). Source/directory mismatch refuses before launch.
The [player ports contract](../contracts/player-ports.md#player-journal)
governs which journals the package can reopen.

`target.json` has explicit argv/cwd/environment; its first executable and selected
working directory are absolute. Keep the prepared wrapper/windowed project userdir
and normal input configuration. The target receives only the permitted environment
and inherited mechanical descriptors, not provider credentials.
The custodian creates `.runtime/logs/` before launch for the prepared wrapper's log.

`route.json` uses current `player-host/13` with text/image input and explicit
provider/effort/price metadata and image peak and block, chosen against the
provider's image limit (background LLM recall is retired). Set `endpoint_costs` for
the player as specified by the [route envelope](../contracts/player-host.md#route-envelope). Set
`context_cut` to `null` or the closed object with
`high_mark`, `low_mark` and `min_free` described in the [host procedure](player-host.md).
The route repeats the package's `spend_limit_usd` and carries
`unpriced_request_usd` ([Spend limit](#spend-limit)). Freeze the
[selected route](player-host.md) for ordinary runs. Diagnostic or qualification
packages may freeze another conforming route and name it in their record.
`mcp-template.json` must equal the current generated profile with `@ACTOR_CONFIG@`.
Freeze the player guide/current schema and ongoing user objective in context/prompt.
Keep experiment quotas, ending reserves and host counts in operator files,
outside the player's supplied prompt and tool views. The one deliberate
final-actor signal is the refusal of a handoff call: every actor has the same tool
table, and an actor with no successor is told so only when it calls
`player_handoff` ([host procedure](player-host.md)). Do not put mutable
engineering source or hidden game facts into player context.

A prior player's terminal report may be included as clearly bounded **fallible
historical data**, preserving its mistakes and uncertainty. It is not operator
instructions or current evidence. Old source/operation references gain no
readability, memory registration or input authority from inclusion in the packet;
current observations and actual tool availability govern the new player. This
does not replace canonical actor handoff or import a memory record.

The validator rejects unsupported/partial/used packages and selected old player
stores before native effects. It does not create a new allocation or discover a
credential. Preserve the frozen package and exact binary bytes before rebuilding.

### Construct a package

Select providers fastest first using the latest relevant speed and eligibility
evidence. Earlier refusals remain historical observations, not exclusion rules;
check the faster candidate again before falling back. A shallow same-payload probe
can inform admission, but does not establish useful gameplay latency or quality.
Include current cache/context conditions and tail/failure behavior when known.
Price or an earlier completed ending does not justify preferring a slower route.
Freeze one explicitly selected route per finite admission, with no hidden fallback;
changed routing requires a fresh package.

This is an engineering preparation step, outside the deciding player's tools.
Prepare the required inputs before hashing the package. Use the closed `target.json`
shape
`{"argv":["ABSOLUTE_PREPARED_WRAPPER"],"cwd":"ABSOLUTE_PROJECT_ROOT","env":{}}`.
Normal wrapper preparation supplies the windowed project userdir. Optional target
environment names are only PATH, LANG, SDL_AUDIODRIVER, SDL_VIDEODRIVER,
DYLD_LIBRARY_PATH and DYLD_FRAMEWORK_PATH; never include credentials. The
[host reference](../../tools/player_host/README.md) specifies the complete route
shape, supported reasoning/routing fields and their limits.

Generate the exact current MCP template without an actor capability:

```sh
.venv/bin/python -m tools.configure_player_tools --template --output .runtime/computer-sessions/SELECTED_FRESH_PACKAGE/mcp-template.json
```

The closed `manifest.json` shape is below. Replace uppercase path/identity/hash
placeholders and the example allocations with the prospectively selected values;
the example is not an admission. All artifact paths are canonical absolute
project-local regular files, never symlinks. Obtain the exact source with
`git rev-parse HEAD` after an inspected clean checkpoint. Calculate SHA256 from
the actual bytes, for example `shasum -a 256 SELECTED_FILE`; preserve those bytes.

```json
{
  "schema": "campaign-run/14",
  "session": "NEW_32_LOWERCASE_HEX_ID",
  "source_commit": "EXACT_40_HEX_CLEAN_HEAD",
  "labels": {"arm": "ARM", "start": "S1", "scenario": "SCENARIO", "lineage": null, "admission": null, "world": null},
  "context": {},
  "files": {
    "route.json": "SHA256", "mcp-template.json": "SHA256",
    "context.txt": "SHA256", "prompt.txt": "SHA256", "target.json": "SHA256",
    "delivered-knowledge.json": "SHA256", "source-index.json": "SHA256",
    "agenda.json": "SHA256"
  },
  "private_files": {"knowledge-full.json": "SHA256", "units.json": "SHA256"},
  "initial_files": {"ABSOLUTE_PREPARED_WRAPPER": "SHA256", "ABSOLUTE_OPTIONS_FILE": "SHA256"},
  "native": {"path": "ABSOLUTE_INSTALLED_GAME_BINARY", "sha256": "SHA256"},
  "library": {"path": "ABSOLUTE_QUALIFIED_BRIDGE", "sha256": "SHA256"},
  "shared_lock": "ABSOLUTE_PROJECT_ROOT/.runtime/bridge/game.lock",
  "player_store": "ABSOLUTE_SELECTED_CURRENT_PLAYER_SQLITE",
  "host": {"argv": ["ABSOLUTE_EXISTING_NODE_EXECUTABLE", "ABSOLUTE_PROJECT_ROOT/tools/player_host/run.mjs"]},
  "effort": "medium", "port": 8766,
  "wall_seconds": 9000, "host_seconds": 3600, "total_host_seconds": 7200,
  "max_hosts": 2,
  "limits": {"max_inputs": 6000, "max_requests": 10000, "max_frames": 1500, "max_bytes": 2147483648},
  "ending_reserve": {"seconds": 120, "usd": "0.50", "inputs": 128, "requests": 128, "frames": 128, "frame_bytes": 134217728},
  "spend_limit_usd": "5",
  "live_knowledge_updates": false
}
```

### Check planned capture headroom

Before asking approval for a paid interactive package, run the offline validator
with the planned cumulative retained PNG bytes immediately before the last work
capture and, if planned, immediately before the last finish-up capture. Include
earlier retained frames and the possible result of work already dispatched at
the start of finish-up. Use measured comparable PNG sizes or a documented
conservative forecast. With one planned capture, its prior retained total is zero.

```sh
.venv/bin/python -m tools.campaign_package \
  --run .runtime/computer-sessions/SELECTED_FRESH_PACKAGE \
  --work-before-bytes 42991616 --ending-before-bytes 115343360
```

The byte counts above are examples. Omit `--ending-before-bytes` when the planned
ending requires no capture. The check binds its result to the package manifest
hash and reports the remaining bytes at each declared checkpoint. Each planned
capture needs at least the runtime's full pending reservation. Work also needs
strictly more than the ending byte reserve at dispatch. Remaining bytes decline as
PNGs are retained, so the last checkpoint covers earlier captures in its phase.
Keep the byte forecast with the approval proposal. The runtime still enforces
actual bytes, other resource limits and input custody during the run. Observation-only
diagnostics can use the existing package preflight for their declared scope.

### Freeze delivered knowledge

Before hashing the package, run `python -m tools.knowledge_export REPOSITORY --version vN --package DIR`.
Pass `--world WORLD` with the exact value of `labels.world` when it is set, `--lineage LINEAGE`
with `labels.lineage` when set, and `--context KEY=VALUE` for each declared run-wide axis in
`context`. The exporter selects every current record whose scope is satisfied by that target
and blinds all raw world and lineage labels before drawing units. Omit `--world` to select
unbound records alone. `--empty --package DIR` creates the required files with no units or
coverage and takes the same selection options. Then run
`python -m tools.source_index --package DIR [--world WORLD --lineage LINEAGE --before-admission N] [--extra-run PRIOR_RUN ...] [--prior-agenda PRIOR_RUN/agenda-final.json]`
to freeze `source-index.json` (`player-source-index/1`, empty when unbound/non-lineage) and
`agenda.json` (`player-agenda-continuation/1`, empty when starting fresh or validated from a
prior admission's `agenda-final.json`). Freeze all returned hashes in `files` and
`private_files`. Preflight verifies the private selection against `labels.world`,
`labels.lineage`, `context` and the delivered file's SHA-256. The
[host contract](../contracts/player-host.md#delivered-knowledge-and-player-working-state-agenda) specifies
which files reach the player.

With `--withhold-seed S`, each unit is withheld independently with probability one
half in ID order. For a withholding study, use `--study-draw FILE --start-index I`
and the world named in the draw. The
[study design](../contracts/withholding-study.md#the-withholding-studys-design-withholding-study-draw2)
defines the blocked assignment. The sealed pilot's starts each took their own seed.
[Pilot analysis](../contracts/withholding-study.md#the-withholding-pilots-analysis-withholding-pilot1)
defines that measure. See the [unit rule](../contracts/measurement-tools.md#the-facts-to-judge-judged-facts1)
for shared facts and article units.

### Live knowledge updates

`live_knowledge_updates` is required and is `true` or `false`. With `false`, every
actor plays the frozen version for the whole admission. With `true`, on each poll the
driver adopts the highest newer version the
[curator runner](../components/curator.md#delivery-to-a-running-actor) has confirmed and
that verifies and publishes; the running host delivers non-empty substantive deltas that
fit within context capacity (suppressing empty updates and refusing oversized ones for
context capacity), and any successor starts from the driver's latest adopted version. The
[host contract](../contracts/player-host.md#a-newer-version-during-play) specifies
adoption, verification and the message the player receives.
Live delivery also sends the runner's verified coverage to the actor. On `player-host/13`
with context cuts enabled, the host prefers curator-covered turns at `high_mark` /
`image_peak` and activates a bounded deterministic uncovered-cut fallback above the
derived Tier-2 pressure ceiling or on strict hard-fit rescue without advancing
`covered_through_operation_id` (preserving `player_agenda`, `recent_intents`, omitted
`source_ids` and unchanged disk WAL ingestion;
[host contract](../contracts/player-host.md#coverage-gated-context-cut)). Play
continues through ordinary image eviction and handoff while coverage is unavailable or
after a restore.

Set it only for a run launched with `--curator-runner`
([supervision](campaign-supervision.md#freeze-launch-and-inspect)); without the
runner no newer version arrives and play keeps the frozen version. Preflight refuses
`true` when `private/units.json` records a withholding seed or a study draw: a newer
version is exported whole and would deliver what the draw withheld. The judged-facts
builder refuses such a run for the same reason
([facts to judge](../contracts/measurement-tools.md#the-facts-to-judge-judged-facts1)).

### Spend limit

Each package starts with a fresh spend allowance. Choose a positive
`spend_limit_usd` from the realistic cost of the planned run, inside the owner's
envelope, and put the same value in the manifest and `route.json`. Use the
[route envelope](../contracts/player-host.md#route-envelope) for the decimal format.
The validator recomputes `unpriced_request_usd` as
`(contextWindow × max(input, cacheRead, cacheWrite) + maxTokens × output) / 1e6`
from the frozen rates and refuses a mismatch or zero. For two-endpoint routing
the frozen model rates are the per-category maxima across the two endpoints.
Set `ending_reserve.usd` at or above the player bound,
and ensure `ending_reserve.usd` plus that player bound stays strictly below
`spend_limit_usd` so ordinary work can start before the ending reserve is reached.

The host contract defines [spend accounting and stops](../contracts/player-host.md#spend).
The provider may bill attempts with unknown charges. Preserve unpriced counts and
use the frozen time and mechanical ceilings. Read the counted figures from the
receipt.

The credit limit the owner sets on the provider key is the hard cap, and the code
cannot read it.

The [operator permissions](../operator-permissions.md#finite-gameplay-budget-delegation)
assign provider billing to the owner. Before paid play, the lead verifies the
approved envelope against the frozen package. Preserve provider credit refusals
as run evidence with the attempt's returned cost or explicit unknown.

Limits: seven input files other than `delivered-knowledge.json` each ≤1 MiB; 1–16 initial files; host argv of 1–8 entries,
the first an absolute regular file and the rest canonical project-local files tracked
by the clean source commit (ignored `.runtime`, `.worktrees` or dependency files refuse), with
the frozen adapter's `validate` mode accepting the route and MCP template; port 1024–65535;
wall 60–86400 s, host/aggregate-host 30–86400 s, one or two hosts.
Host seconds ≤ aggregate-host seconds < wall seconds minus 30 s cleanup. Each positive
computer capacity is ≤2^40. `spend_limit_usd` is above zero. `ending_reserve.usd`
covers the player's pending-request bound, and `ending_reserve.usd` plus that bound
stays strictly below the declared limit. The selected directory must have no prior started marker,
session DB, native-process receipt, actors or contexts. An existing selected player
store must be current; it never restores computer custody. The maintained
validator is authoritative and rejects changed bytes/unsupported fields before
effects. Do not remove markers to reuse a failed package.

### Operator labels

The required `labels` object contains exactly the fields below. The evaluator and
spectator use these values to describe the admission.

| Field | Value |
|---|---|
| `arm` | string, 1-40 characters (for example `ceiling`, `long-horizon`) |
| `start` | development run ledger start code from `S1` through `S99` |
| `scenario` | string, 1-80 characters (for example `Evacuee`) |
| `lineage` | string, 1-40 characters, or `null`; chained admissions of one survivor share it |
| `admission` | integer 1-10000, or `null`; position within the lineage; `null` exactly when `lineage` is `null` |
| `world` | string, 1-40 characters, or `null`; required when a lineage is set; may be set for an admission without a lineage |

Strings are printable ASCII only (space through `~`), with no control or non-ASCII
characters. Preflight checks the start code against the current ledger schema
before dispatch. A missing field, extra field or out-of-bound value refuses the
package before effects, like the rest of the manifest. Preflight accepts only `campaign-run/14`.

The required top-level `context` object (`{}` by default) declares 0 to 8 **run-wide
invariant** axes (`[a-z][a-z0-9_]{0,31}`, never `game`, `world` or `lineage`; printable
ASCII values of 1 to 64 characters) that remain constant for the entire run — such as
game build, modset or scenario rules. Never place transient in-run state in `context`;
transient conditions belong in a fact's `when` clause.

Keep the label values out of the player's argv, prompt, context, route, target,
MCP configuration and environment. The sole effect of the labels and `context` on a
player-visible input is determining the
[frozen knowledge selection](#freeze-delivered-knowledge).

### Ending reserve and external stop

`ending_reserve` is closed: `seconds,usd,inputs,requests,frames,frame_bytes`.
Every value but `usd` is a positive integer strictly below its corresponding original
host or mechanical limit. Use the [spend limit rules](#spend-limit) for the dollar
reserve. Before admission the lead forecasts reserve adequacy for the largest
already-admitted input burst, pending player requests, control delivery,
any permitted successor and the expected finish-up under the original limits.
Set these values for the planned run in place of the example numbers.

The driver applies the time reserve to host seconds, uses `spend` as the trigger
for the dollar reserve and records command intent in `control.json`. The
[external control contract](../contracts/player-host.md#external-control) defines when
finish-up is requested, how the command is delivered and how it survives handoff.

**Pace host time against the dollar limit.** On `player-host/12` a decision costs far
less than before, so host time can end a run long before its dollars do. In the
[bounded live validation (#963)](../acceptance/2026-11-25-wave3-wave4-live-validation-963.md)
the player made `690` decisions across `5,327.4` host seconds (`5,329` wall seconds)
for `$3.498` (`$0.00507` per decision, rounded to `$0.0051`, and `7.72` host seconds
per decision against a `5,837.5 ms` p50 player-request latency). The `600` s time
reserve inside `host_seconds: 5700` triggered an orderly `host_seconds` stop at
`5,100` s with `$2.17` of `$5.50` unspent and `spend_reserve_reached: 0`. At that
whole-run pace the `$4.10` above `ending_reserve.usd` (`$1.40`) funds about `809`
decisions, or about `6,244` working host seconds (`6,844` s including the `600` s
time reserve). Before freezing a package, decide which limit should end the run and
size the other one past it:

1. Divide `spend_limit_usd` minus `ending_reserve.usd` by the cost per decision of the
   latest comparable run to get the decisions the dollars fund.
2. Multiply by that run's host seconds per decision, not its response latency.
3. For a run meant to end on the spend reserve, or to reach a multi-day horizon, set
   `host_seconds` above that figure plus `ending_reserve.seconds`, and
   `total_host_seconds` and `wall_seconds` to keep the [limits](#spend-limit) above.
   For a run meant to end on time, keep the dollars funding more decisions than the
   host time allows, as in `#963`.
4. Write the expected trigger into the forecast, so an earlier stop is read as a
   pacing result rather than a fault.

The current CDDA launch binding requires the canonical absolute
`.runtime/bridge/game.lock`, shared with install/preparation and the project
userdir. A different project-local lock is rejected. This is preparation coupling
outside the game-independent computer runtime; a future game binding must define
its own coherent preparation/launch exclusion rather than bypass this one.

## Start and close

Follow the [supervised launch procedure](campaign-supervision.md#freeze-launch-and-inspect)
and open the gateway URL printed by the supervisor.

The custodian takes shared exclusion and writes `started.json` before native/DB
creation. Native inherits the exact shared-lock descriptor/socket, retaining
exclusion for its own lifetime. The custodian writes `ready.json` after starting
its service. The driver creates exclusive per-actor inputs/host traces and
operator-only resource notes. `frozen.json` is `player-host-inputs/5`.
With [live knowledge updates](#live-knowledge-updates) each actor directory also
holds `knowledge-updates.jsonl` and the adopted versions under `knowledge/`.
Each actor receives its starting `agenda.json` (`player-agenda-continuation/1`) and
writes its final committed `agenda-final.json`, which carries across handoffs and is
persisted to the run directory's `agenda-final.json` for resumed admissions.
It verifies canonical handoff/context plus actual host/MCP group quiescence before
a successor, without changing original limits. [Host details](player-host.md).

The spectator scopes status, activity, source and permanent-Pause facts to their
actual sessions. A fresh admission establishes a new current target while a
previous selection remains labelled recorded evidence; it is never Resume.
Reload discards client-retained history and does not grant input authority. The
[spectator component](../components/spectator.md) owns current behavior;
the [Watch/Timeline report](../acceptance/2026-10-29-spectator-watch-timeline.md)
retains actual same-page admission/Pause evidence and its limits.

During live play, keep elapsed/receipt checks short enough to meet the selected
operator stop window. Delegate extended review when it competes with runtime
ownership. Record a missed window or late closeout observation as a deviation;
a planned browser Pause is not evidence that the click occurred. No additional
monitoring service or per-action approval is required.

SIGINT/SIGTERM or browser Pause permanently fence input. Finalization closes the
channel and exact owned groups, with bounded signals if necessary. It never scans
for or adopts unrelated processes. Normal native exit zero is sampled before
forced cleanup. Save-to-menu, player save/success claims, native exit and absence
are separate evidence.

`receipt.json` (`campaign-receipt/7`) reports driver disposition, host quiescence,
native absence, input revocation, cleanup and the run's spend. Its `accounting`
block is closed:

| Field | Meaning |
| --- | --- |
| `spend_limit_usd` | The package's declared limit |
| `reported_usd` | The sum of the cost the provider reported, over the responses that reported one |
| `unpriced_requests` | Observed player attempts without a usable provider charge |
| `unpriced_request_usd` | Player in-flight and ending planning bound from the route |
| `unpriced_recall_requests` | Constant `0` on `player-host/13` (retained for `campaign-receipt/7` / `player-driver/7` compatibility) |
| `unpriced_recall_request_usd` | Constant `"0"` on `player-host/13` (retained for `campaign-receipt/7` / `player-driver/7` compatibility) |
| `spent_usd` | Provider subtotal counted toward the dollar limit, equal to `reported_usd` |
| `observed_attempts` | Player HTTP starts read from the traces |
| `observed_recall_attempts` | Constant `0` on `player-host/13` (retained for `campaign-receipt/7` / `player-driver/7` compatibility) |
| `spend_complete` | Whether [trace reconciliation](../contracts/player-host.md#spend) is complete. When false, the spend is unknown. |

The dollar amounts are decimal text. The invoice is separate from the reported cost.
For an incomplete trace, treat the observed subtotal and counts as lower bounds.
A direct finish yields `player_task_complete_unassessed`,
`player_cannot_continue_unassessed` or
`player_external_stop_complete_unassessed`. An earlier non-cleanup permanent
fence remains `interrupted`; later expected adapter closure cannot erase it.
Generic stop control can succeed without a normal native exit. Apply any separately
frozen game-persistence or exit criterion to its own evidence lane, using
[the settlement contract](../contracts/player-host.md#settlement-and-handoff).
The embedded driver result is `player-driver/7`, with the retained ending request
(its `trigger`, and the dollars and mechanical capacity left when it was sent), per-actor
direct player-finish/settlement, observed attempts and each actor's `allocated_usd`,
`reported_usd`, `unpriced_requests`, `spent_usd` and `spend_complete`. Its totals
carry `reported_usd`, `unpriced_requests`, `unpriced_request_usd`, `spent_usd` and
`spend_complete`. The totals list `configured_estimate_usd` separately as an estimate
from the route's configured rates. No receipt alone accepts gameplay.
Preserve failures and unrun lanes.

A development admission is recorded once its receipt exists, with
`.venv/bin/python -m tools.run_ledger record PACKAGE --study ISSUE --label LABEL`,
where `LABEL` is the
run's short name in its study's dated record (default: the package name). That command appends one
[`dev-run/3`](../contracts/run-ledger.md#tracked-run-ledger-and-metrics-snapshot) row to
`data/evaluation/runs.jsonl`, the one numeric record of the run: the study's record cites
that row or a generated table and keeps no hand-typed copy of attempts, spend or duration.
The spend figures are the receipt's; none is typed in. A package without a receipt
gets no row, and no further admission is made until the lead resolves it.

**When the receipt's `spend_complete` is false,** the run's spend could not be counted,
and `record` refuses the package. No further run of that study is admitted until the
lead has done both of these:

1. Recorded the run with `--record-upper-bound` added to the command above. The
   provider subtotal and observed unpriced counts stay as recorded. The ledger
   stores a separate planning amount for admission. It uses the larger of the
   declared limit and observed subtotal, plus one possible in-flight player
   request and, if the package delivers knowledge units, one possible in-flight
   recall request. These exposures can exist even when no starts were observed.
   The flag is refused for a complete trace.
2. Identified the separate admission amount in the run's dated record and stated which
   cost evidence was unavailable. The provider's charge remains unknown when the
   run could not establish it. The record supplies that context for the
   `dev-run/3` row.

`run_ledger totals --study ISSUE --envelope USD` applies the
[actual-spend admission rule](../operator-permissions.md#finite-gameplay-budget-delegation),
with `--forecast-largest USD` standing in for the largest admission before any completes.
This is the only ledger writer.

Never reopen the selected package, delete markers to retry, replay uncertain input
or resume after user Pause. Use a fresh coherent admission after owned cleanup.
The [production report](../acceptance/2026-10-29-computer-control.md) retains scoped
actual outcomes; each new admission still needs its own evidence and closeout.

[Operations index](../runbook.md).
