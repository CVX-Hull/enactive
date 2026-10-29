---
owner: harness maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# One finite campaign run

One [campaign custodian](../../tools/campaign_run.py) owns fresh mechanical target,
store/server lifetime and final cleanup. The [driver](../../tools/campaign_player.py)
owns generic-Pi host/MCP groups and at most one successor. The
[package validator](../../tools/campaign_package.py) is authoritative for the closed
`campaign-run/2` admission. No game-phase/identity admission or semantic mission
service remains.

## Frozen data

Select one fresh canonical project-local directory under `.runtime/computer-sessions/`.
Its manifest binds the exact clean source commit and SHA256 of all five driver
inputs: `route.json`, `mcp-template.json`, `context.txt`, `prompt.txt`, `target.json`.
It also freezes native executable/adapter bytes, bounded initial target files,
shared-lock path, explicit `player-memory/1` store, existing Node path, effort,
loopback port, original wall/host/aggregate-host seconds, one/two-host limit,
aggregate HTTP-attempt bound, computer input/request/frame/byte capacities and
cumulative conservative accounting. Source/directory mismatch refuses before launch.

`target.json` has explicit argv/cwd/environment; its first executable and selected
working directory are absolute. Keep the prepared wrapper/windowed project userdir
and normal input configuration. The target receives only the permitted environment
and inherited mechanical descriptors, not provider credentials.

`route.json` uses current `pi-player-host/4` with text/image input and explicit
provider/effort/price/image-history metadata. The selected route is OpenRouter /
Fireworks US / DeepSeek Flash1017 medium, default service tier, no fallback.
`mcp-template.json` must equal the current generated profile with `@ACTOR_CONFIG@`.
Freeze the player guide/current schema, meaningful task, original limits and ending
reserve in context/prompt. Do not put mutable engineering source or hidden game
facts into player context.

The validator rejects unsupported/partial/used packages and selected old player
stores before native effects. It does not create a new allocation or discover a
credential. Preserve the frozen package and exact binary bytes before rebuilding.

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
Production real-game acceptance of this route remains open.

[Operations index](../runbook.md).
