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
for the closed `campaign-run/3` admission. No game-phase/identity admission or semantic mission
service remains.

## Frozen data

Select one fresh canonical project-local directory under `.runtime/computer-sessions/`.
Its manifest binds the exact clean source commit and SHA256 of all five driver
inputs: `route.json`, `mcp-template.json`, `context.txt`, `prompt.txt`, `target.json`.
It also freezes native executable/adapter bytes, bounded initial target files,
shared-lock path, explicit `player-memory/1` store, player host argv, effort,
loopback port, original wall/host/aggregate-host seconds, one/two-host limit,
aggregate HTTP-attempt bound, computer input/request/frame/byte capacities and
cumulative cap accounting. Source/directory mismatch refuses before launch.

`target.json` has explicit argv/cwd/environment; its first executable and selected
working directory are absolute. Keep the prepared wrapper/windowed project userdir
and normal input configuration. The target receives only the permitted environment
and inherited mechanical descriptors, not provider credentials.

`route.json` uses current `player-host/2` with text/image input and explicit
provider/effort/price metadata and image peak and block, chosen against the
provider's image limit. The selected route is OpenRouter /
an explicitly pinned provider / DeepSeek Flash1017 medium, default service tier, no fallback.
`mcp-template.json` must equal the current generated profile with `@ACTOR_CONFIG@`.
Freeze the player guide/current schema, meaningful task, original limits and ending
reserve in context/prompt. Do not put mutable engineering source or hidden game
facts into player context.

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
  "schema": "campaign-run/3",
  "session": "NEW_32_LOWERCASE_HEX_ID",
  "source_commit": "EXACT_40_HEX_CLEAN_HEAD",
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
driver creates exclusive per-actor inputs/host traces and original resource notes.
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

`receipt.json` (`campaign-receipt/2`) reports driver disposition, host quiescence,
native absence, input revocation, cleanup and original accounting. Configured
estimates and conservative reservations are not invoices. Unknown trace accounting
charges the allocated attempts. `host_completed_unassessed` means only successful
host completion; missing normal native exit becomes an incomplete outcome.
No receipt alone accepts gameplay. Preserve failures and unrun lanes.

Never reopen the selected package, delete markers to retry, replay uncertain input
or resume after user Pause. Use a fresh coherent admission after owned cleanup.
The [production report](../acceptance/2026-10-29-computer-control.md) retains scoped
actual outcomes; each new admission still needs its own evidence and closeout.

[Operations index](../runbook.md).
