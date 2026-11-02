---
owner: maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Coordinated migration

The [computer/player contract](../contracts/computer-control.md) is the single
current production boundary. Native7/mission11/DB13, old proof launch profiles,
semantic gameplay APIs, phase/identity/recovery commands and old executable-memory
imports are unsupported. No compatibility shim, alternate backend or automatic
reader remains. [ADR006](../decisions/006-computer-control-boundary.md) owns rationale.

Before changing a deployment:

1. Close writers and verify exact owned native/host/MCP cleanup. Never migrate under a live actor/game.
2. Preserve original saves, SQLite/JSON/PNG, configuration, source checkpoint and binary bytes as inert evidence. Keep failed/abandoned chains intact.
3. Select current coherent source, current adapter/native bytes and normal project-local input settings. Freeze a fresh explicit `campaign-run/4` package under `.runtime/computer-sessions/`.
4. Use a fresh `computer-session/3` store and launch marker. A selected partial directory refuses even with no DB; do not delete markers to rearm it.
5. Explicitly select a `player-memory/1` store. It can span fresh native-child sessions, but old campaign-memory/procedure/advisory formats are not current executable inputs. Unsupported selected stores reject before native launch.
6. Requalify the affected native/gameplay boundary. Old test/demo results remain bound to their earlier source and cannot qualify the replacement.

Upstream saves are unchanged. Load them only through visible ordinary application
controls; the player judges identity/continuity from observations. The harness
certifies no save and imports no hidden game facts. Retained old source is available
in Git at the accepted checkpoint; superseded contract bookmarks link it explicitly.

Rollback is a coherent earlier source/data deployment after all writers close.
It never mixes old/new readers, replays uncertain input, restores capabilities
from storage or renews the original run. Setup build manifests have their own
version; preserve/refuse unsupported manifests rather than silently convert them.
[Setup](../setup.md#build-metadata-migration).

[Operations index](../runbook.md).
