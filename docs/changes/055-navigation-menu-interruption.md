---
owner: lead
review_trigger: Navigation feedback, ordinary prompt ownership or mission/ledger contracts change
status: active
---

# Let the player handle a menu opened by movement

Independent017 returned one verified move, then its next directional input opened
a friendly-NPC UILIST. Navigation required a displacement even though the menu
correctly had no scene. The player stopped autonomously. The failed mission and
exceptional ordered shutdown remain; none of its unfinished outcomes is accepted.
[#138](https://github.com/CVX-Hull/enactive/issues/138) owns the repair and
[#144](https://github.com/CVX-Hull/enactive/issues/144) owns full mission acceptance.

## Decision and prior-work fit

Keep the [navigation contract](../protocol.md), existing mission writer, retained
observations, prompt phase, ledger and explicit controls. A returned input with
exact fresh same-session ordinary-menu feedback ends navigation as partial,
including when no step was credited. Retain the verified prefix and last verified
route position; neither is the character's unobserved position behind the menu.
The menu input gets no displacement credit. Its actual source and returned
delivery remain. No route replay or automatic answer is added. Normal-scene
feedback still requires independently checkable displacement; unknown delivery,
intervening observations, takeover and unsupported activity/debug boundaries keep
their existing stopped handling.

Transfer an interrupted recovered suffix to the original navigation root and game
anchor before clearing its terminal continuation. Menu and editor
children keep the root's Work, deadlines and cumulative costs. They do not acquire
item/activity/interaction-root authority. Returning to normal closes the prompt;
the player then chooses a new plan from current evidence. No new navigation root
can bypass an occupied phase, and no retained PhaseReceipt restores a live handle.

This implements the existing #138 expectation to react to changed menus and the
[player-owned mission design](../design/player-owned-mission.md). It supports the
[target-first input proposal](../design/mixed-input.md) through existing visible
controls; it does not implement raw mouse input, a widget tree or learned
procedures. The [organic-discovery crosswalk](../design/organic-discovery.md#cross-check-against-prior-work)
and [asynchronous-reflection proposal](../design/asynchronous-reflection.md) remain
proposals. Routine interpretation belongs to the player, bookkeeping to software;
neither the engineering lead nor a background critic approves each menu action.
No new learning or research-performance claim follows from this repair.

## Coordinated migration and maintenance

Mission/8 adds a closed navigation PhaseReceipt variant, operation `navigate`,
with stages awaiting_control/complete/unknown. Ledger10 accepts only the selected
control children under a navigation root. Existing mission/7 and ledger9 readers
reject these records, so migrate contracts, runtime, client/CLI/viewer, fixtures
and current guidance together. Earlier request/database versions reject; no shim,
dual reader or runtime conversion is retained. Native4, archive3, gameplay/2 and
campaign-memory/3 are unchanged. Closed historical missions, saves and costs stay
untouched; use a new directory and finite admission for deciding play.

All owned game/controller processes must be closed before deployment. Qualify the
actual fresh player's current MCP adapter and review-free access before gameplay;
an old host process or changed source file alone does not prove activation. Reuse
the official SDK and existing producer/receiver validation, not another transport.

Lead owns this coupled change and integration; independent boundary/source review
checks attribution, root/Work continuity, migration and failure handling. Focused
checks cover zero/prefixed interruption, no replay/credit, explicit cancellation
and replanning, recovered-suffix transfer, root budget/Pause, corrupt receipt
rejection and read-only reopen. Full portable CI and actual native gameplay remain
separate evidence lanes. Revisit through existing C-REVIEW/C-RUNTIME/C-MAINTENANCE
on another uncovered boundary; no new framework, dependency or review schedule.
