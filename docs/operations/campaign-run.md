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
for the closed `campaign-run/5` admission. No game-phase/identity admission or semantic mission
service remains.

Development runs (`--attention best-effort`) and frozen tests that require
45-second operator checks (`--attention required`) use
[the maintained supervisor](campaign-supervision.md) around this same custodian.
The supervisor owns its wrapper processes and check clocks; native/actor custody
and original package allowances remain here. Its receipt does not accept gameplay.

## Frozen data

Select one fresh canonical project-local directory under `.runtime/computer-sessions/`.
Its manifest binds the exact clean source commit and SHA256 of all five driver
inputs: `route.json`, `mcp-template.json`, `context.txt`, `prompt.txt`, `target.json`.
It also freezes native executable/adapter bytes, bounded initial target files,
shared-lock path, explicit `player-memory/2` store, player host argv, effort,
loopback port, original wall/host/aggregate-host seconds, one/two-host limit,
aggregate HTTP-attempt bound, computer input/request/frame/byte capacities,
`ending_reserve`, cumulative cap accounting and the operator-only
[`labels`](#operator-labels). Source/directory mismatch refuses
before launch. Player stores use SQLite `user_version=2`; select a fresh
`player-memory/2` store for this migration and preserve unsupported old libraries
as inert history without conversion.

`target.json` has explicit argv/cwd/environment; its first executable and selected
working directory are absolute. Keep the prepared wrapper/windowed project userdir
and normal input configuration. The target receives only the permitted environment
and inherited mechanical descriptors, not provider credentials.

`route.json` uses current `player-host/3` with text/image input and explicit
provider/effort/price metadata and image peak and block, chosen against the
provider's image limit. The selected route is OpenRouter /
an explicitly pinned provider / DeepSeek Flash1017 medium, default service tier, no fallback.
Diagnostic or qualification packages may freeze another conformed route; their
record names it, and it confers no selection.
`mcp-template.json` must equal the current generated profile with `@ACTOR_CONFIG@`.
Freeze the player guide/current schema and ongoing user objective in context/prompt.
Keep experiment quotas, ending reserves and host counts in operator files,
outside the player's supplied prompt/tool/program views. The one deliberate
final-actor signal is the tool table: an actor with no successor is offered no
`player_handoff` ([host procedure](player-host.md)). Do not put mutable
engineering source or hidden game facts into player context.

A prior player's terminal report may be included as clearly bounded **fallible
historical data**, preserving its mistakes and uncertainty. It is not operator
instructions or current evidence. Old source/operation references gain no
readability, memory registration or input authority from inclusion in the packet;
current observations and actual tool availability govern the new player. This
does not replace canonical actor handoff or import a memory record.
For the next player/test-separation diagnostic, do not import the old quota-bearing
assignment or report; the [agreed rationale](../changes/073-player-objective-and-test-control.md#next-evidence-decision)
owns that prospective scope. Historical data is not scrubbed or rewritten.

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
changed routing requires a fresh package and actual cumulative accounting.

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
  "schema": "campaign-run/5",
  "session": "NEW_32_LOWERCASE_HEX_ID",
  "source_commit": "EXACT_40_HEX_CLEAN_HEAD",
  "labels": {"arm": "ARM", "start": "START", "scenario": "SCENARIO", "lineage": null, "admission": null},
  "files": {
    "route.json": "SHA256", "mcp-template.json": "SHA256",
    "context.txt": "SHA256", "prompt.txt": "SHA256", "target.json": "SHA256"
  },
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
  "ending_reserve": {"seconds": 120, "http_attempts": 8, "inputs": 128, "requests": 128, "frames": 128, "frame_bytes": 134217728},
  "accounting": {
    "prior_attempts": 0, "prior_reserved_usd": 0,
    "ceiling_usd": 0, "prospective_reserved_usd": 0
  }
}
```

Use the actual cumulative accounting rather than the zero placeholders. With
default tier, worst-case per attempt is
`(contextWindow × max(input, cacheRead, cacheWrite) + maxTokens × output) / 1e6`
using the frozen route's configured dollar rates. Prospective cumulative
reservation is the prior baseline plus that amount times `max_http_attempts`; it
must fit the standing ceiling exactly as frozen.

`prior_reserved_usd` is the **actual spend to date** (owner decision, 31 October
2026), not the sum of past worst-case reservations. The next package's baseline is
this baseline plus each settled run's actual cost, taken as follows:
- Provider usage or an account reading, using the upper end of any range.
- On a shared account, the whole account delta over the run, never apportioned
  downward.
- An attempt missing provider usage counts at its worst case, unless an account
  reading over the run covers it.
- A run whose cost neither a trace nor the account isolates counts at its original
  allocation.

Only the package being admitted reserves its own attempts at the worst case.
Record the baseline's sources with each package.

The first baseline under this rule is $47.64. It is about $30–40 billed on this
project's provider accounts when the old cumulative reservation stood at $1066.80
(owner reading, upper end), plus #304's $7.64, its account and key usage readings
over conformance, the visual check and play. If the owner's reading postdates part
of #304, the sum double-counts, which errs high.

A custodian report's `cumulative_conservative_reservation_usd` is the baseline plus
the run's charged attempts at the worst case; it is never the next baseline. The
field names are unchanged and no format migration applies, because the validator
and custodian only add a lead-supplied baseline to the package's own worst case. The
basis changed: receipts before this rule (through #304) record a cumulative
worst-case baseline, and later ones an actual-cost baseline. Do not compare the two
across that boundary.

The worst-case figure stays a bound on one package, not spend: it charges every
attempt as if it filled the whole context window and output limit, which
overstated actual cost by more than an order of magnitude, about $1066.80 against
$30–40 billed. Report actual cost first, from provider-reported usage, with missing
usage counted separately. When host traces carry only configured-rate costs (as on #304's
OpenRouter routes), use provider usage or account readings, and state when the account
is shared. Present the reservation only as the cap check it is.

Before paid play, the lead reads the provider account balance and confirms that
the auto top-up threshold stays above the realistic actual cost of the planned
runs. OpenRouter sizes its in-flight hold from the current balance, so a low
account produces repeated in-flight 402s that one host retry may not outlast
(#304's play001 ended this way), and an exhausted one returns terminal credit
refusals.

Limits: five input files each ≤1MiB; 1–16 initial files; host argv of 1–8 entries,
the first an absolute regular file and the rest canonical project-local files tracked
by the clean source commit (ignored `.runtime`, `.worktrees` or dependency files refuse), with
the frozen adapter's `validate` mode accepting the route and MCP template; port1024–65535;
wall60–86400s, host/aggregate-host30–86400s, one/two hosts and1–10000 HTTP attempts.
Host seconds ≤aggregate-host seconds <wall seconds minus30s cleanup. Each positive
computer capacity is ≤2^40. The route's per-host request maximum cannot exceed the
campaign aggregate. The selected directory must have no prior started marker,
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
have no `labels` and are rejected as inert history; there is no conversion or default.

**The labels are not player-visible.** Only the validator, evaluator and spectator
read them. The driver builds every player-visible input (host argv, route, prompt,
context, MCP configuration, actor identity, control command and host environment)
from other manifest fields, and never from `labels`. Do not copy a label into the
prompt, context, route or target files, which are frozen and hashed separately. A
negative test (`test_operator_labels_never_reach_the_player_host`) asserts that the
launched argv, environment and every file written for an actor lack the label values.

### Ending reserve and external stop

`ending_reserve` is closed: `seconds,http_attempts,inputs,requests,frames,frame_bytes`.
Every value is a positive integer strictly below its corresponding original
host/route/mechanical limit. The driver requests ending at the first threshold
crossed in host seconds, remaining attempts or mechanical capacities. It retains
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
notes; `frozen.json` is `player-host-inputs/2`.
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

`receipt.json` (`campaign-receipt/3`) reports driver disposition, host quiescence,
native absence, input revocation, cleanup and original accounting. Configured
estimates and conservative reservations are not invoices. Unknown trace accounting
charges the allocated attempts. Direct finish yields
`player_task_complete_unassessed`, `player_cannot_continue_unassessed` or
`player_external_stop_complete_unassessed`. An earlier non-cleanup permanent
fence remains `interrupted`; later expected adapter closure cannot erase it.
Normal native exit is reported separately; its absence is not a save certificate
or an automatic failure of generic stop control. Apply any separately frozen
game-persistence/exit criterion to its own evidence lane.
The embedded driver result is `player-driver/3`, with the retained ending request,
per-actor direct player-finish/settlement and original attempt charges. No receipt
alone accepts gameplay. Preserve failures and unrun lanes.

A development admission is recorded once its receipt exists, with
`.venv/bin/python -m tools.run_ledger record PACKAGE --study ISSUE --label LABEL
--provider-records N --provider-usd X --unpriced-attempt-usd 0.4096`, where `LABEL` is the
run's name in its hand-scored table (default: the package name). That command appends one
[`dev-run/1`](../contracts/evaluation.md#tracked-run-ledger-and-metrics-snapshot) row to
`data/evaluation/runs.jsonl`. The provider figures come from the operator's own
reconciliation. A package without a receipt gets no row, and no further admission
is made until the lead resolves it. `run_ledger totals --study ISSUE --envelope USD`
applies the actual-spend admission rule: new spend plus twice the largest admission,
with `--forecast-largest USD` standing in for the largest before any admission completes.
This is the only ledger writer: the untracked `.runtime` arm runners and `lh_admit.py`
that wrote the #372 and #382 operator ledgers are retired.

Never reopen the selected package, delete markers to retry, replay uncertain input
or resume after user Pause. Use a fresh coherent admission after owned cleanup.
The [production report](../acceptance/2026-10-29-computer-control.md) retains scoped
actual outcomes; each new admission still needs its own evidence and closeout.

[Operations index](../runbook.md).
