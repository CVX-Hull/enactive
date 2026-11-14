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
for the closed `campaign-run/7` admission. Admission is that package check alone: it reads
no game phase or identity, and no semantic mission service exists.

A run is launched through [the maintained supervisor](campaign-supervision.md),
which wraps this same custodian.
The supervisor owns its wrapper processes, the custody deadline and Pause; native/actor custody
and original package allowances remain here. Its receipt does not accept gameplay.

## Frozen data

Select one fresh canonical project-local directory under `.runtime/computer-sessions/`.
Its manifest binds the exact clean source commit and SHA256 of all five driver
inputs: `route.json`, `mcp-template.json`, `context.txt`, `prompt.txt`, `target.json`.
It also freezes native executable/adapter bytes, bounded initial target files,
shared-lock path, explicit `player-memory/2` store, player host argv, effort,
loopback port, original wall/host/aggregate-host seconds, one/two-host limit,
aggregate HTTP-attempt bound, computer input/request/frame/byte capacities,
`ending_reserve`, the dollar limit `spend_limit_usd` and the operator-only
[`labels`](#operator-labels). Source/directory mismatch refuses
before launch. Player stores use SQLite `user_version=2`; unsupported old
libraries are refused without conversion.

`target.json` has explicit argv/cwd/environment; its first executable and selected
working directory are absolute. Keep the prepared wrapper/windowed project userdir
and normal input configuration. The target receives only the permitted environment
and inherited mechanical descriptors, not provider credentials.

`route.json` uses current `player-host/5` with text/image input and explicit
provider/effort/price metadata and image peak and block, chosen against the
provider's image limit. It repeats the package's `spend_limit_usd` and carries
`unpriced_request_usd` ([Spend limit](#spend-limit)). The selected route is OpenRouter /
an explicitly pinned provider / DeepSeek Flash1017 medium, default service tier, no fallback.
Diagnostic or qualification packages may freeze another conformed route; their
record names it, and it confers no selection.
`mcp-template.json` must equal the current generated profile with `@ACTOR_CONFIG@`.
Freeze the player guide/current schema and ongoing user objective in context/prompt.
Keep experiment quotas, ending reserves and host counts in operator files,
outside the player's supplied prompt/tool/program views. The one deliberate
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
Create the five inputs above first. `target.json` is closed:
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
  "schema": "campaign-run/7",
  "session": "NEW_32_LOWERCASE_HEX_ID",
  "source_commit": "EXACT_40_HEX_CLEAN_HEAD",
  "labels": {"arm": "ARM", "start": "START", "scenario": "SCENARIO", "lineage": null, "admission": null},
  "files": {
    "route.json": "SHA256", "mcp-template.json": "SHA256",
    "context.txt": "SHA256", "prompt.txt": "SHA256", "target.json": "SHA256",
    "delivered-knowledge.json": "SHA256"
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
  "max_hosts": 2, "max_http_attempts": 360,
  "limits": {"max_inputs": 6000, "max_requests": 10000, "max_frames": 1500, "max_bytes": 2147483648},
  "ending_reserve": {"seconds": 120, "http_attempts": 8, "usd": "0.50", "inputs": 128, "requests": 128, "frames": 128, "frame_bytes": 134217728},
  "spend_limit_usd": "5"
}
```

### Freeze delivered knowledge

Before hashing the package, run `python -m tools.knowledge_export REPOSITORY --version vN --package DIR`, optionally with `--withhold-seed S`. Each unit is withheld independently with probability one half in ID order. Each start of a withholding study takes its own seed: the analysis pools starts as independent draws and refuses a repeated seed ([pilot analysis](../contracts/evaluation.md#the-withholding-pilots-analysis-withholding-pilot1)). An article's unit lists only the facts exclusive to it; `private/units.json` records other cited facts under `shared` with their citing article IDs. Shared facts follow any delivered citing article, unfiled facts are their own units, and links to withheld articles are removed. `--empty --package DIR` creates the same required files with no units or coverage. Freeze the returned hashes in `files` and the closed `private_files` map shown above. The host/application receive only `delivered-knowledge.json`; judges read the private full version and unit draw. No delivered-text cap is imposed.

The route has a closed `recall` object: the selected model on the player's provider/key, `every` completed inputs per reminder, `max_requests`, and `unpriced_request_usd` computed from that model's rates. The package's attempt limit includes both player and recall HTTP attempts. The model and cadence are pinned before spending.

### Spend limit

`spend_limit_usd` is the most this run may count as spent. The player host stops the
run when the counted total reaches it ([host contract](../contracts/player-host.md#spend)).
Nothing is carried over from earlier packages.

- **Amounts are decimal text.** `spend_limit_usd`, `ending_reserve.usd` and the
  route's two amounts are strings such as `"5"` or `"0.4096"`. A JSON number, an
  exponent, a sign or a non-finite word refuses the package. The limit is above zero.
- **The route repeats the limit.** `route.json` has the same `spend_limit_usd`. The
  driver gives each actor a copy whose value is the dollars the run has left.
- **The route carries the bound.** `unpriced_request_usd` is what one request with no
  cost record counts for:
  `(contextWindow × max(input, cacheRead, cacheWrite) + maxTokens × output) / 1e6`
  from the frozen route's configured dollar rates. The validator computes it and
  refuses a route that states another value, naming the value it expects. It also
  refuses a route whose rates give a bound of zero, which would count a failed
  request as free.
- **The dollar reserve covers both in-flight bounds.** `ending_reserve.usd` is at least
  the player bound plus the recall bound (the latter contributes zero with empty knowledge); the validator refuses less, naming both amounts. With less
  than one request's bound left, a single failed request would end the run abruptly
  instead of in order. The reserve is below the limit, so the limit exceeds the bound.
- **What counts.** A response counts at the cost the provider reported for it. A
  request with no cost record (refused, timed out, cut off, aborted at a deadline)
  counts at the bound, because the provider may still bill it.
- **Overshoot.** The host checks before each request, so a run can pass its limit by
  at most what one player request and one recall request count; each unpriced request counts at its own bound.
- **A player response the host cannot price ends the run.** A successful player response with no
  usable cost stops the host with reason `cost-unreported`. A failed or unpriced recall ends recall for that actor only. A valid provider cost is counted even on a rejected selection or a length stop; only missing/invalid cost counts at the recall bound.
- **The hard cap is the key's credit limit**, set by the owner on the OpenRouter key
  ([operator permissions](../operator-permissions.md#finite-gameplay-budget-delegation)).
  The code cannot read it.

Choose the limit from the realistic cost of the planned run, inside the owner's
envelope. The configured-rate estimate in a trace (`usage.cost`) is not what counts;
the receipt records the counted figures.

Before paid play, the lead reads the provider account balance and confirms that
the auto top-up threshold stays above the realistic actual cost of the planned
runs. OpenRouter sizes its in-flight hold from the current balance, so a low
account produces repeated in-flight 402s that one host retry may not outlast
(the [#304 record](../acceptance/2026-10-31-capable-player.md) holds an example), and an exhausted one returns terminal credit
refusals. A key credit limit close to what the key has already spent can cause the
same refusals, and each refused request counts at the bound.

Limits: five input files each ≤1MiB; 1–16 initial files; host argv of 1–8 entries,
the first an absolute regular file and the rest canonical project-local files tracked
by the clean source commit (ignored `.runtime`, `.worktrees` or dependency files refuse), with
the frozen adapter's `validate` mode accepting the route and MCP template; port1024–65535;
wall60–86400s, host/aggregate-host30–86400s, one/two hosts and1–10000 HTTP attempts.
Host seconds ≤aggregate-host seconds <wall seconds minus30s cleanup. Each positive
computer capacity is ≤2^40. The route's per-host request maximum cannot exceed the
campaign aggregate. `spend_limit_usd` is above zero, and `ending_reserve.usd` is
at least the route's `unpriced_request_usd` and below the limit. The selected directory must have no prior started marker,
session DB, native-process receipt, actors or contexts. An existing selected player
store must be current; it never restores computer custody. The maintained
validator is authoritative and rejects changed bytes/unsupported fields before
effects. Do not remove markers to reuse a failed package.

### Operator labels

`labels` is required and closed: `arm`, `start`, `scenario`, `lineage`, `admission`.
They are operator-only analysis labels frozen with the admission so the evaluator
and spectator ([ADR008](../decisions/008-evaluation-and-spectator.md)) can name
the experiment arm, start and scenario without inferring them from player data.

| Field | Value |
|---|---|
| `arm` | string, 1-40 characters (for example `ceiling`, `long-horizon`) |
| `start` | string, 1-40 characters (for example `S1`) |
| `scenario` | string, 1-80 characters (for example `Evacuee`) |
| `lineage` | string, 1-40 characters, or `null`; chained admissions of one survivor share it |
| `admission` | integer 1-10000, or `null`; position within the lineage; `null` exactly when `lineage` is `null` |

Strings are printable ASCII only (space through `~`), with no control or non-ASCII
characters. A missing field, extra field or out-of-bound value refuses the package
before effects, like the rest of the manifest. Packages of any earlier schema
have no `labels` and are rejected; there is no conversion or default.

**The labels are not player-visible.** Only the validator, evaluator and spectator
read them. The driver builds every player-visible input (host argv, route, prompt,
context, MCP configuration, actor identity, control command and host environment)
from other manifest fields, and never from `labels`. Do not copy a label into the
prompt, context, route or target files, which are frozen and hashed separately. A
negative test (`test_operator_labels_never_reach_the_player_host`) asserts that the
launched argv, environment and every file written for an actor lack the label values.

### Ending reserve and external stop

`ending_reserve` is closed: `seconds,http_attempts,usd,inputs,requests,frames,frame_bytes`.
Every value but `usd` is a positive integer strictly below its corresponding original
host/route/mechanical limit; `usd` is a decimal string above zero and below
`spend_limit_usd`. The driver requests ending at the first threshold
crossed in host seconds, remaining attempts, remaining dollars (trigger `spend`) or
mechanical capacities. Remaining dollars are the limit minus the cost counted so
far; a request still in flight is not yet counted, so the reserve should cover what
one more request can count. It retains
one command identity for the whole admission. Static validation checks field
bounds only. Before admission the lead forecasts reserve adequacy for the largest
already-admitted input/program burst, the current provider attempt, control
delivery and any permitted successor, under the original limits. The example
numbers above are placeholders, not a proof that a particular ending fits.

The driver retains `control.json` intent before writing a closed
`player-control/1` `orderly_stop` command to host stdin. The initial prompt is
passed by `--prompt PATH`; `--session`, `--actor-id` and
`--pending-control-id none|32hex` bind each actor. The pipe stays open until
settlement. Duplicate identical commands are idempotent; malformed, oversized,
conflicting or wrong-identity input and unexpected EOF fail the host.

Finish-up is optional bounded player-chosen game work. It mandates no Save or
Quit and never delays independent permanent Pause, hard limits or cleanup. Unsent
pre-control tool calls are withheld; dispatched input is not canceled/replayed
to deliver text. New handoff is refused while stop is pending. If an in-flight
handoff has already sealed, a verified successor receives the same command ID
before MCP connection or provider fetch, or ending stays incomplete. Sealing
and host exit never erase the request. Direct `player_finish` and its command
identity are retained separately from game saving, native exit and owned absence.

The current CDDA launch binding requires the canonical absolute
`.runtime/bridge/game.lock`, shared with install/preparation and the project
userdir. A different project-local lock is rejected. This is preparation coupling
outside the game-independent computer runtime; a future game binding must define
its own coherent preparation/launch exclusion rather than bypass this one.

## Start and close

From the exact clean source checkpoint, with the selected credential injected only
through its explicit environment name:

```sh
.venv/bin/python -m tools.campaign_run --run "$PWD/.runtime/computer-sessions/SELECTED_FRESH_PACKAGE"
```

The custodian takes shared exclusion and writes `started.json` before native/DB
creation. Native inherits the exact shared-lock descriptor/socket, retaining
exclusion for its own lifetime. `ready.json` gives the loopback viewer URL. The
driver creates exclusive per-actor inputs/host traces and operator-only resource
notes; `frozen.json` is `player-host-inputs/3`.
It verifies canonical handoff/context plus actual host/MCP group quiescence before
a successor, without changing original limits. [Host details](player-host.md).

The spectator scopes status, activity, source and permanent-Pause facts to their
actual sessions. A fresh admission establishes a new current target while a
previous selection remains labelled recorded evidence; it is never Resume.
Reload discards client-retained history and does not grant input authority. The
[observer component](../components/observer-operations.md) owns current behavior;
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

`receipt.json` (`campaign-receipt/5`) reports driver disposition, host quiescence,
native absence, input revocation, cleanup and the run's spend. Its `accounting`
block is closed:

| Field | Meaning |
| --- | --- |
| `spend_limit_usd` | The package's declared limit |
| `reported_usd` | The sum of the cost the provider reported, over the responses that reported one |
| `unpriced_requests` | Requests with no cost record |
| `unpriced_request_usd` | What each of those counts for: the route's bound |
| `spent_usd` | What counted toward the limit: `reported_usd` plus `unpriced_requests` × `unpriced_request_usd` |
| `attempts_charged` | HTTP attempts charged against the request allowance |
| `allocated_max_attempts` | The package's `max_http_attempts` |
| `spend_complete` | Whether every actor's trace was read to its settlement and the host's own totals equal the driver's sums; when false the spend is unknown |

The dollar amounts are decimal text. What the provider reports is what the provider
says; it is not an invoice. Unknown trace accounting charges the allocated attempts,
marks the spend incomplete and starts no further actor. Direct finish yields
`player_task_complete_unassessed`, `player_cannot_continue_unassessed` or
`player_external_stop_complete_unassessed`. An earlier non-cleanup permanent
fence remains `interrupted`; later expected adapter closure cannot erase it.
Normal native exit is reported separately; its absence is not a save certificate
or an automatic failure of generic stop control. Apply any separately frozen
game-persistence/exit criterion to its own evidence lane.
The embedded driver result is `player-driver/5`, with the retained ending request
(its `trigger`, and the dollars and attempts left when it was sent), per-actor direct
player-finish/settlement, original attempt charges and each actor's `allocated_usd`,
`reported_usd`, `unpriced_requests`, `spent_usd` and `spend_complete`. Its totals
carry `reported_usd`, `unpriced_requests`, `unpriced_request_usd`, `spent_usd` and
`spend_complete`. `configured_estimate_usd` stays beside them as an estimate from the
route's configured rates; it is not counted. No receipt
alone accepts gameplay. Preserve failures and unrun lanes.

A development admission is recorded once its receipt exists, with
`.venv/bin/python -m tools.run_ledger record PACKAGE --study ISSUE --label LABEL`,
where `LABEL` is the
run's short name in its study's dated record (default: the package name). That command appends one
[`dev-run/2`](../contracts/evaluation.md#tracked-run-ledger-and-metrics-snapshot) row to
`data/evaluation/runs.jsonl`, the one numeric record of the run: the study's record cites
that row or a generated table and keeps no hand-typed copy of attempts, spend or duration.
The spend figures are the receipt's; none is typed in. A package without a receipt
gets no row, and no further admission is made until the lead resolves it.

**When the receipt's `spend_complete` is false,** the run's spend could not be counted,
and `record` refuses the package. No further run of that study is admitted until the
lead has done both of these:

1. Recorded the run with `--record-upper-bound` added to the command above. The row
   then holds the most the run can have spent: `provider_usd` is the receipt's
   `spend_limit_usd`; the player unpriced count is `min(1, attempts)`, and the recall unpriced count is 1 only when delivered knowledge has units and at least two attempts were charged. The two bounds come from the receipt. Thus `spend_usd` is the limit plus the possible in-flight bounds, and combined unpriced counts never exceed attempts. The flag is refused for a receipt whose spend is complete.
2. Noted in the run's dated record that the row is an upper bound, with the OpenRouter
   key's activity figure for the run's time window. A `dev-run/2` row has no field
   that marks an upper bound, so the dated record is where that is stated. `run_ledger totals --study ISSUE --envelope USD`
applies the [actual-spend admission rule](../operator-permissions.md#finite-gameplay-budget-delegation),
with `--forecast-largest USD` standing in for the largest admission before any completes.
This is the only ledger writer.

Never reopen the selected package, delete markers to retry, replay uncertain input
or resume after user Pause. Use a fresh coherent admission after owned cleanup.
The [production report](../acceptance/2026-10-29-computer-control.md) retains scoped
actual outcomes; each new admission still needs its own evidence and closeout.

[Operations index](../runbook.md).
