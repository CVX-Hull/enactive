---
owner: harness maintainer
review_trigger: Finite run admission, frozen inputs, controller/host custody or exceptional cleanup changes
status: active
---

# One finite campaign run

Use `tools.campaign_run` for a fresh finite development run that needs controller
lifetime and admission as well as the [player driver](player-host.md). The
custodian reuses that maintained driver; it chooses no tactics, interpretations,
normal-ending inputs or successor decisions. Do not copy a Python supervisor into
an ignored run directory. Original frozen scripts remain historical evidence.

Before preparing a run, select its useful objective, finite scope and resources
in the existing Issue under the [development checkpoint policy](../workflows/development.md).
Use an inspected, clean committed source with passing exact-source fast/focused
checks. These declarations do not replace the protected profile and independent
outcome review required for formal acceptance. No extra full PR/main gate is
required solely to start development play. A new run never reopens an old mission,
actor, allocation or uncertain admission.

## Frozen data

Prepare `.runtime/campaigns/<mission_id>/frozen/` and `preparation/` in the current
checkout. The frozen directory contains only `manifest.json` and these six inputs:

- `admission.json`: the current MissionAdmission, including this source/model,
  original mission limits and cleanup reserve.
- `player-pi-configuration.json` and `player-host-configuration.json`: the current
  Pi/provider route and maintained MCP entry with explicit tools and timeouts.
- `pi-player-context.txt`, `original-player-prompt.txt` and
  `successor-player-brief.txt`: actual context for the original and any permitted
  fresh successor. The custodian does not edit them or append a new deadline.

The closed `campaign-run/1` manifest has these fields:

| Field | Required value |
| --- | --- |
| `schema`, `mission_id`, `source_commit` | `campaign-run/1`, this fresh mission ID and the exact clean Git checkpoint matching admission |
| `max_hosts`, `effort` | Integer 1 or 2; effort accepted by the current Pi configuration |
| `begin_normal_ending_seconds`, `complete_normal_ending_before_seconds` | Positive finite prospective offsets with begin before completion; completion preserves the original admission cleanup reserve and a finite 60-second shutdown allowance |
| `files` | Exact SHA256 map of the six filenames above, without executable programs or other inputs |
| `validation` | `fast` and `focused` objects, each declaring `source_commit` and `passed:true`; retain actual check evidence under its existing scope |
| `provider` | Request and conservative reservation fields below; these are resource guards, not useful-latency acceptance |

Provider fields are `prior_requests`, `new_requests_max`, `total_requests_max`,
`prior_reservation_usd`, `per_request_reservation_usd`, `total_reservation_usd` and
`reservation_limit_usd`. Counts are nonnegative integers; new requests equal the
Pi route's per-host ceiling times `max_hosts`, and total equals prior plus new.
Monetary fields are finite nonnegative decimal strings, with a positive per-request
reservation; total equals prior reservation plus per-request times new requests
and must fit the selected ceiling. Reservation remains distinct from configured
usage estimates, actual invoices and unknown usage.

The maintained preflight validates both Pi and MCP configurations before admission.
Node is selected by trusted launcher configuration, never frozen data. Keep the
MCP command on this interpreter's `-m harness.player_mcp` with this checkout as cwd.
The caller supplies `DEEPINFRA_API_KEY` securely in its environment; the custodian
performs no Keychain/profile discovery. It forwards that value only to the owned
driver, never the controller, argv or frozen files. Console output is suppressed;
use the maintained structured driver evidence and fixed custodian receipts.

## Start and close

```sh
.venv/bin/python -m tools.campaign_run --root "$PWD" --mission-id FRESH_MISSION_ID
```

The custodian exclusively reserves its output names and refuses prior mission,
admission intent or driver evidence. A collision is not permission to retry with
those identities. Source and frozen-data checks happen before admission. Startup
has a finite 30-second allowance; the actual admission anchor and prospective
ending/cleanup times go in `custodian-clock.json`. All actor time is deducted from
the original remaining ending allowance. The clock receipt does not renew limits
or rewrite context; the player still owns normal ending within its frozen brief.

After exactly one acknowledged admission, the driver runs the original and at
most one clean successor through its existing handoff/current-custody checks.
Uncertain admission is collected/reconciled under its original identity outside
this fresh-run launcher; it is never replayed. Run output is evidence, not an
acceptance decision or a resume switch.

On cancellation, failure or the ending deadline, the custodian first gives its
exact driver handle time to settle nested hosts, then requests exceptional Stop
when needed and closes its exact controller child. Only the settled mission
writer closes a retained native handle under the
[exceptional shutdown contract](../contracts/lifecycle-exit.md#exceptional-writer-shutdown).
Controller and driver launch in separate OS sessions so terminal cancellation
reaches the custodian first. It still signals only each retained child handle;
there is no production process-group signalling or PID adoption. Controlled
terminal-style fixtures check child-written cleanup evidence and settlement order.
This can terminate an unsaved owned game. Missing/lost controller or native custody,
unsettled writers/hosts and absent matching shutdown receipts remain unknown;
no PID scan, process adoption, group signal or replay repairs them. Cleanup does
not establish normal Save/exit, useful play or acceptance. Preserve all original
failure and unknown fields when performing later disposition.

`custodian-receipt.json` records owned child exits, acknowledged admission,
terminal/incomplete outcome, deciding-host quiescence and the boot-bound native
cleanup receipt. Source tests use controlled children and offline configuration
checks; their pass does not qualify real native cleanup or the complete campaign.

[Operations index](../runbook.md).
