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
service remains. With a subgoal level ([ADR-007](../decisions/007-player-subgoal-level.md)
candidate), the driver also owns one episode cutter, one episode recorder and one level per actor, as described below.

## Frozen data

Select one fresh canonical project-local directory under `.runtime/computer-sessions/`.
Its manifest binds the exact clean source commit and SHA256 of all five driver
inputs: `route.json`, `mcp-template.json`, `context.txt`, `prompt.txt`, `target.json`
(seven with a level, adding `level-role.txt` and `episode-role.txt`). It also freezes the actor profile and the level.
It also freezes native executable/adapter bytes, bounded initial target files,
shared-lock path, explicit `player-memory/1` store, player host argv, effort,
loopback port, original wall/host/aggregate-host seconds, one/two-host limit,
aggregate HTTP-attempt bound, computer input/request/frame/byte capacities and
cumulative cap accounting. Source/directory mismatch refuses before launch.

`target.json` has explicit argv/cwd/environment; its first executable and selected
working directory are absolute. Keep the prepared wrapper/windowed project userdir
and normal input configuration. The target receives only the permitted environment
and inherited mechanical descriptors, not provider credentials.

### Actor profile, the episode recorder and the subgoal level (level v4)

`actor_profile` is `flat` (basic control, memory and programs) or `narrowed` (no
memory tools or program save). `level` is null, the zero-level-host configuration
(flat, arm B and the fourth arm), or a closed object (a level requires `narrowed`):

| Field | Meaning |
|---|---|
| `mode` | `shadow` or `live` |
| `episode_cap` | The episode cap C, which must equal the owner's K (10) |
| `min_episode_inputs` | m, the fewest inputs before a content cut |
| `theta`, `theta_fitting_sha256` | The fitted episode threshold, by value, and the SHA256 of the fitting that produced it (#345's `calibration.json`) |
| `stall_settles`, `confidence_floor` | N and c, given to both readers at minting |
| `staleness_inputs` | S |
| `budget_fractions`, `intent_tail_bytes` | at most 8 increasing values in (0,1); 64-4096 |
| `recall` | `tail_top`, `tail_exploration`, `level_items`: must equal the custodian's 2, 1 and 10 |
| `max_http_attempts`, `pass_max_requests`, `pass_seconds` | The level's share per actor and its pass bounds |
| `recorder` | `max_http_attempts`, `pass_max_requests`, `pass_seconds` and `backlog` (3): the recorder's own allowance and bounds |

A level freezes two more inputs, `level-role.txt` and `episode-role.txt`, byte-identical to the
[frozen role prompt `subgoal-v4`](../../tools/player_roles/subgoal-v4.txt) and
[`episode-v1`](../../tools/player_roles/episode-v1.txt). The validator pins both digests
(`FROZEN_ROLE_SHA256`), so a changed wording is a new version, not an edit. The route stays the actor
role; its `intent_tail_bytes` equals the level's bound in live mode and is null in shadow mode, where the
level commits but the actor never sees intent.

Each actor, its level and its recorder are partitioned before launch: the level and then the recorder get
`min(their max_http_attempts, campaign remainder)` and the actor the route's allowance from what is left, so
their sum stays within the campaign cap. The driver mints two readers per actor (roles `level` and `recorder`)
after the actor. Once the actor host makes its first request:

- **Cutter.** The [episode cutter](../../tools/episode_cutter.py) reads the served actor's log in order from the
  application and cuts it on player-visible captures only: 32 x 20 greyscale thumbnails, a mean-absolute distance
  to the previous input that has a result capture, a close before the crossing input when d >= theta and the episode
  holds m inputs, at C inputs, and mechanically at a session edge. An input whose result is still in flight waits;
  one that is lost has no distance. Boundaries are frozen once written. The driver records the level subgoal id
  current when an episode opens, because no custodian API gives it later, and the next episode always starts after
  the furthest cut, never after the newest settle (episodes settle out of order when a drop precedes an earlier
  in-flight record).
- **Recorder.** Closed episodes wait in a FIFO backlog; one pass runs at a time, and when more than `backlog`
  wait, the oldest waiting episode settles as `dropped`. A recorder pass is a finite `role: recorder` host under
  `actors/NNN/recorder/PPP/` with the profile `player_source`, `player_episode_record`, `player_episode_abstain`.
  Its input is the baseline frame (the result capture of the last input before the episode) and up to six of
  the episode's own frames (always the last, then the largest thumbnail distance from the predecessor, in capture
  order), each an image file in `frames/` marked with its source id and role, plus the operations as key tokens, and
  the subgoal id, text and expected observations. A pass that ends without settling its episode (a failed pass, its
  time, a stop) leaves the driver to settle it `failed` through the custodian; an exhausted recorder allowance or a
  session that ends first settles what waits as `failed`. Every closed episode therefore ends with exactly one
  settle claim, whatever its outcome.
- **Level.** The [wake rules](../../tools/level_schedule.py) wake it at start (only to revalidate what earlier
  sessions left), after every settle, and at a budget fraction only after a settle; wakes that arrive during a pass
  coalesce into one pass over the newest records. At push, under the application lock, the driver binds the position
  (the end of the newest settled episode this session, whatever its outcome, or 0) and the current subgoal id, and
  reads the episodes settled since its last pass, the `player-intent/2` object for the `level` audience (the
  subgoal with its derived status and stalled flag, and the top 10 recalled episodes) and the per-subgoal counts.
  Each pass is a finite `role: level` host under `actors/NNN/level/PPP/` with the profile `player_source` and the four
  terminal tools. A pass ends on its first `player_level_keep`, `player_level_replace` or `player_level_close` that
  commits or discards, or on a valid `player_level_abstain`
  (see the [host contract](../contracts/player-host.md#roles-and-the-intent-tail)); one that ends otherwise is a
  failed pass with its settled reason, for example `level-no-proposal`, `level-final-refusal` or `level-uncertain`
  (a lost terminal call, reconciled from the store).

Both readers' passes are written as `input.json` (`player-pass-input/1`: the role, the frozen role prompt, the
actor's brief for the level only, mechanical wake facts and the structured pushed input
`player-level-push/1` or `player-episode-push/1`) and fed to the host on stdin; the host formats it. The level
stops on its actor's stop, Pause or handoff. The open episode closes at that session edge, and the recorder then
works through its backlog (bounded by `backlog + 1` passes of `pass_seconds` and the campaign deadline) unless the
run is fenced; whatever remains settles as `failed`. No successor is minted unless every pass's exact process group
is confirmed absent. Attempts are charged like an actor's; an unaccounted pass is charged its whole allocation.
A failure of the cutter, recorder or level (a malformed trace, a launch or store error, a store that cannot remember)
charges the pass, disables both readers for the rest of the session and is recorded, but never stops or gates the
actor; episodes already cut still settle. A reader the custodian refuses to mint fails closed before that actor
launches. The custodian appends per-call lock wait and hold times to `call-timing.jsonl`.

`route.json` uses current `player-host/6` (role `actor`) with text/image input and explicit
provider/effort/price metadata and image peak and block, chosen against the
provider's image limit. The selected route is OpenRouter /
an explicitly pinned provider / DeepSeek Flash1017 medium, default service tier, no fallback.
Diagnostic or qualification packages may freeze another conformed route; their
record names it, and it confers no selection.
`mcp-template.json` must equal the current generated profile for `actor_profile` with `@ACTOR_CONFIG@`.
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
.venv/bin/python -m tools.configure_player_tools --template --profile SELECTED_ACTOR_PROFILE --output .runtime/computer-sessions/SELECTED_FRESH_PACKAGE/mcp-template.json
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
  "actor_profile": "flat", "level": null,
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
The `player-driver/6` disposition embedded in it reports, per actor, a `level` object with the level lane
(`commits` with `keeps`, `replaces` and `closes`, `discards`, `abstains` with `abstain_codes` and `start_abstains`,
`failed_passes`, `final_refusals`, `uncertain_terminals` with their reconciliation, every pass's settled reason and
bound), the recorder lane (`records`, `abstains` by code, `failed_passes`, `final_refusals`), `episodes` (the cuts by
close reason, the settles by outcome read back from the store, the backlog's high-water mark) and `subgoals`
(per-subgoal episodes, seen, contradicted, closures and failures). The driver total adds `level_attempts_charged`
(level plus recorder), `level_failed_passes`, `level_final_refusals`, `level_uncertain_terminals` and `episodes_cut`.
Earlier driver schemas are rejected by the readers.

Never reopen the selected package, delete markers to retry, replay uncertain input
or resume after user Pause. Use a fresh coherent admission after owned cleanup.
The [production report](../acceptance/2026-10-29-computer-control.md) retains scoped
actual outcomes; each new admission still needs its own evidence and closeout.

[Operations index](../runbook.md).
