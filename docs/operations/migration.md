---
owner: maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Coordinated migration

The [computer/player contract](../contracts/computer-control.md) is the current
production boundary. Unsupported formats and versions refuse before effects; there
is no compatibility shim, alternate backend or automatic reader.
The [computer-control boundary decision](../decisions/006-computer-control-boundary.md)
explains the rationale.

Before changing a deployment:

1. Close writers and verify exact owned native/host/MCP cleanup. Never migrate under a live actor/game.
2. Preserve original saves, SQLite/JSON/PNG, configuration, source checkpoint and binary bytes as inert evidence. Keep failed/abandoned chains intact.
3. Select current coherent source, current adapter/native bytes and normal project-local input settings. Freeze a fresh explicit `campaign-run/13` package under `.runtime/computer-sessions/`.
4. Use a fresh `computer-session/1` store and launch marker. A selected partial directory refuses even with no DB; do not delete markers to rearm it.
5. Select a `player-journal/1` store (`user_version=1`); a supported journal can span fresh native-child sessions. Unsupported or unrecognized nonempty stores are refused before native launch without conversion.
6. Requalify the affected native/gameplay boundary. Earlier test/demo results remain bound to their source and cannot qualify the replacement.

Current actor consumers use `player-computer-result/2`, `player-computer-operation/1`, `player-error/2` and
`player-transport/2`. Host/control/telemetry and all finite-package
callers move together with `player-host/12`, telemetry 12, `campaign-run/13`,
`player-host-inputs/4`, `delivered-knowledge/4`, `player-knowledge/4`, `knowledge-update-entry/1`, `coverage-update-entry/1`,
`player-driver/7`, `campaign-receipt/7` and `spectator-view/3`. The live spectator requires
`computer-status/2`; its host block carries observed attempts. The evaluator
reads older versions only for sealed sessions individually pinned to those
versions in its [closed archive index](../standards/migration.md) (including `#889`'s
and `#896`'s sealed `campaign-run/12` manifests, journals and handoffs). Use the original
source commit and readers for preserved evidence outside that index. Native wire,
canonical `computer-operation/1`, `computer-source/1` and computer-session storage
are separate versions; the actor projection does not migrate the canonical database.

The continuous-play memory store migration starts a fresh `curator-knowledge/5`
repository (`curator-fact/6`, `curator-submission/3`, `curator-boundary-grooming/2`)
and fresh curator working state. Preserve older `curator-knowledge/4` repositories and draws as sealed
evidence; there is no `/4` to `/5` converter. Build new packages and `withholding-study-draw/2` draws from the new
repository using the [knowledge export procedure](campaign-run.md#freeze-delivered-knowledge).

Upstream saves are unchanged. Load them only through visible ordinary application
controls; the player judges identity/continuity from observations. The harness
certifies no save and imports no hidden game facts.

To go back, check out the earlier source after all writers close and start from
fresh stores as above. Never mix old and new readers, replay uncertain input or
renew the original run. Setup build manifests have their own version; unsupported
manifests are refused rather than converted
([Setup](../setup.md#build-metadata-migration)).

[Operations index](../runbook.md).
