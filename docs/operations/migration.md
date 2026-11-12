---
owner: maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Coordinated migration

The [computer/player contract](../contracts/computer-control.md) is the current
production boundary. Unsupported formats and versions refuse before effects; there
is no compatibility shim, alternate backend or automatic reader.
[ADR006](../decisions/006-computer-control-boundary.md) owns rationale.

Before changing a deployment:

1. Close writers and verify exact owned native/host/MCP cleanup. Never migrate under a live actor/game.
2. Preserve original saves, SQLite/JSON/PNG, configuration, source checkpoint and binary bytes as inert evidence. Keep failed/abandoned chains intact.
3. Select current coherent source, current adapter/native bytes and normal project-local input settings. Freeze a fresh explicit `campaign-run/5` package under `.runtime/computer-sessions/`.
4. Use a fresh `computer-session/1` store and launch marker. A selected partial directory refuses even with no DB; do not delete markers to rearm it.
5. Select a fresh `player-memory/2` store (`user_version=2`); it can span fresh native-child sessions. Old player stores and executable libraries are refused before native launch, with no conversion or old-view reader.
6. Requalify the affected native/gameplay boundary. Earlier test/demo results remain bound to their source and cannot qualify the replacement.

Current actor consumers use `player-computer-result/1`, `player-error/2` and
`player-transport/2`, and programs use `player-program/2` with required
`view_schema:"program-view/4"`. Host/control/telemetry and all finite-package
callers move together with `player-host/3`, telemetry3, `campaign-run/5`,
`player-driver/3`, `campaign-receipt/3` and `player-host-inputs/2`. Native wire,
canonical `computer-operation/1`, `computer-source/1` and computer-session storage
are separate versions; the actor projection does not migrate the canonical database.

Upstream saves are unchanged. Load them only through visible ordinary application
controls; the player judges identity/continuity from observations. The harness
certifies no save and imports no hidden game facts.

To go back, check out the earlier source after all writers close and start from
fresh stores as above. Never mix old and new readers, replay uncertain input or
renew the original run. Setup build manifests have their own version; unsupported
manifests are refused rather than converted
([Setup](../setup.md#build-metadata-migration)).

[Operations index](../runbook.md).
