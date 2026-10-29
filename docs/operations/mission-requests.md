---
owner: maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

<a id="typed-mission-requests-and-the-player"></a>

# Basic computer tools and the player

The former typed semantic mission API is retired. The current
[tool schema](../../harness/player_tools.py) exposes basic computer controls plus
optional player-owned knowledge/program/context. Inspect it read-only with:

```sh
.venv/bin/python -m tools.configure_player_tools --describe
```

The [player guide](../player-guide.md) supplies the compact procedure. Observe actual
pixels, interpret game meaning, choose bounded basic input and inspect its actual
effect. Keys/text have no image-age/equality or game-phase precondition. A click
requires a source actually issued to that actor and original full-image coordinates;
mechanical geometry is bound by the runtime. Complete sequences validate before effects.

Each HTTP tool submission has a client-assigned operation ID before sending.
Collect `computer_result` or `player_result` by its original ID after uncertainty;
never retry the effect. Partial/unknown input permanently stops further input.
A known no-submission argument refusal may be corrected through a new explicit
choice; missing/lost transport proves neither delivery nor nondelivery.

Player memory stores fallible claims/Work/decisions/procedures/corrections/advice.
Programs are immutable proposals over actual selected image views and optional
player interpretation; helper faults/yields leave basic input available when
custody is healthy. Save/load, identity and success are player judgments, not tools.

`player_handoff` seals the actor with canonical bounded context. The driver alone
admits a successor after actual host/MCP quiescence and canonical verification,
under original resources. User Pause/unknown input is never handoff-resumable.
[Host procedure](player-host.md), [custody](mission-ownership.md),
[exact contract](../contracts/computer-control.md).

[Operations index](../runbook.md).

<!-- Retained bookmarks for the coordinated contract migration. -->
