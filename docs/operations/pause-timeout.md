---
owner: maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Pause, timeout and recovery

Pause permanently stops further automation for the run. Use the browser Pause
control (`POST /api/pause` with `{}`), the actor's `computer_stop`, or custodian
cancellation. These paths do not save, quit, win or undo events already delivered.
Real input in the native window takes precedence and fences synthetic input.

The Python stop event latches before executor/DB waits. A separate send lock has
a bounded Pause send; failure shuts down the socket write side to signal EOF.
The receive side remains open to collect original receipts. Report stop-requested
separately from native-confirmed Pause, especially during backpressure or failure.

On partial/unknown input or lost transport:

1. Retain the original operation ID and result/uncertainty. Do not repeat the action.
2. Collect `computer_result` for mechanical work or `player_result` for player-service work. Reads have no effects and never restore custody.
3. Preserve original charged resources and deadlines. A later receipt does not erase the earlier transport uncertainty.
4. Stop the finite run and inspect its owned cleanup receipts. Do not hand off, rearm or reopen a used package to continue input.

An invalid request known to have no submission may support a new explicit corrected
choice. A missing response does not prove nondelivery. The original complete
sequence is validated before its first effect; native emitted input cannot become
an undelivered rejection. [Exact contract](../contracts/computer-control.md#computer-operations-and-custody).

## Operator recovery

Use ordinary native controls if the application needs interruption, menu recovery,
saving or quitting after automation stops. The harness has no activity/debug/menu
recovery handlers or phase-specific Resume. Pause does not guarantee interruption
of an already running game activity. Record manual intervention and observed effects.

The custodian closes its channel and terminates/reaps only exact owned children
and groups. Normal exit zero is sampled before forced signals and stays distinct
from process absence and player save claims. Unknown cleanup stays unknown; do
not kill unrelated processes or adopt a retained PID. A new run needs fresh
explicit admission/stores after the prior owner is closed.

[Operations index](../runbook.md).
