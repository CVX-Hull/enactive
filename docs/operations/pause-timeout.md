---
owner: maintainer
review_trigger: Changes to this operating task, supported setup or recovery behavior
status: active
---

# Pause, timeout and recovery

Pause prevents subsequent remote dispatch. Native keyboard/button input also
latches takeover. Neither guarantee cancels an already-running native activity;
use explicit operator recovery below or the native window to interrupt it. Do not spam remote keys to escape a stall.

For a timeout or frozen viewer: preserve the error/journal and last frame; inspect
the native window. Unsupported upstream error screens may need native dismissal.
Observe to reconcile current state, then explicitly resume only when interpretable.
Do not resend an uncertain action. New observations do not prove its old objective.
The player must handle routine prompts through the current ordinary-input path
rather than requiring the user or lead to press a key. Native7 attests the actual
ordinary receiver independently of menu category names; an unfamiliar category
alone is not an unsupported-input judgment. The dated direction-query qualification
below covers ordinary selection/cancellation, not every prompt. Current source,
custody, Pause, receiver and delivery checks remain mandatory. If a required
receiver is unavailable, retain the failed attempt rather than request tactical
rescue. If using verified desktop automation for a different
prompt, Pause remote control first, inspect the actual prompt, charge any native
input to the same accounting, and retain its result separately from remote receipts.
Never send a remote key at an
unsupported boundary, invent an acknowledgment or turn an unreadable prompt into
permission. Unavailable access or required human rescue fails campaign readiness.
An app-inventory access/lock error does not prove an existing game binding is
unusable. If an already-owned binding exists, inspect it once against the current
bridge prompt before concluding access failed; do not use app lookup to launch
another game. In [rehearsal002](../acceptance/2026-10-18-first-day-rehearsal-002.md),
that binding supplied actual before/after screenshots and ordinary Shift+Y at a
sound-distraction query. Charge native input before sending it, retain its tool/
image evidence separately from a bridge receipt, and Observe afterward. Remote
takeover remains paused until explicit reauthorization. A failed/unreadable
binding stops; no user unlock or alternative OS-event injection is prescribed.
The [direction-menu acceptance](../acceptance/2026-10-18-native-direction-menu.md)
records actual rebuilt-engine Escape, adjacent selection and empty-current-tile
behavior without user keys. The reuse-first desktop-tool preflight failed before
admission; this narrow support does not establish general native recovery.

For service restart: stop that service normally, start one controller, observe
and reconcile, then resume. An already-open spectator automatically refreshes its
normal same-origin page credential after a service disconnect/reconnect. Explicit
Pause sends immediately; only a403rejection before admission with a changed
credential permits its one retry. Other commands, including Observe, Resume and
recovery, are never replayed. Unknown network outcomes remain unknown. Credential
refresh does not restore game authority; fresh observation/reconciliation is still
required. A browser-code upgrade needs a normal page reload. For a game crash/restart: preserve diagnostics, follow
the bundle-based [start procedure](start-observe.md#start-and-observe), use normal CDDA load UI,
and acquire new session authority.
Old-session commands must not be reused, including after normal save/reload in the
same process. The [current native contract](../protocol.md) rejects older and mixed components; restart a
matching controller and native build, then observe. No save-file repair/editing is prescribed.

Input admissions are durably retained in `.runtime/bridge/admissions/` before
dispatch. An unresolved request remains unknown across reconciliation and service
restart; the current scene is not proof of its old result. Do not delete admissions
or rewrite journals to clear this condition. Preserve them with incident evidence.
At `activity_poll`, `debug_prompt` or `unsupported`, observation is allowed but
remote key/action/Resume is denied. Return to a supported boundary through explicit recovery or normal
native controls, then observe and explicitly resume. Pause only revokes input
that has not crossed the final native commit check; it cannot undo a prior input.

Use CDDA's normal Save menu before quitting. Stop the controller with Ctrl-C; it
leaves remote control paused. Saves are in `.runtime/user/`. Never treat a stale
frame or old acceptance record as proof a current process is healthy.

For an authorized failed-run cleanup, preserve final status and original run
evidence. Use the [maintained campaign custodian](campaign-run.md), which first
allows the actual driver to settle its deciding hosts, requests exceptional Stop
when needed, and closes its exact controller child. Controller shutdown now asks
the settled mission writer to close its retained native child exceptionally. This
can terminate an unsaved game; use ordinary Save/exit before service closure when
normal ending is still supported. No gameplay input is manufactured by cleanup.

The [shutdown contract](../contracts/lifecycle-exit.md#exceptional-writer-shutdown)
distinguishes normal prior exit, exceptional termination and unknown custody.
Only a matching boot-bound receipt with a settled writer and verified absence
supports owned native closure. A blocked/lost writer or controller, missing receipt
or unresolved launch remains unknown. Do not replace the retained handle with a
PID scan, adopt another process, or infer exit code/cause from later PID absence.
A closed source fixture does not qualify native Save/exit or gameplay success;
original unknowns in earlier failed runs remain historical.

## Operator recovery

For activity interruption, inspect the fresh decoded activity frame and choose
Request interrupt if advertised. The control performs Pause before admission.
A committed
activity continues while paused; it may finish or enter another prompt before
recovery applies. Transport-only Pause preserves scene revision; a fresh native
probe opened the owned WAIT question without the former Pause/Observe workaround.
Preserve any rejection, observe deliberately, and decide anew; never automatically
retry. [Round 008 evidence](../acceptance/2026-10-17-native-recovery-planner.md) records
the YES/NO, completed-activity, unknown-result, revocation and reload probes,
including controlled fault injection and its limits. Tutorial save-load errors
remain a separate [content defect](https://github.com/CVX-Hull/enactive/issues/47).

For prompt answers and debug continuation, use Observe, inspect the frame, and use the
explicit recovery button when eligible. An owned confirmation exposes Yes/No;
a raw debug prompt exposes one-shot continuation. Gameplay and recovery pending
or unknown records remain separately inspectable. Pause remains available during
either request. Recovery never automatically resumes play or repeats a request.

For CLI use, copy the exact evidence that informed your decision:

```sh
.venv/bin/python -m harness request_interrupt --session SESSION --generation GENERATION
.venv/bin/python -m harness answer_interrupt --session SESSION --generation GENERATION --boundary BOUNDARY --revision REVISION --frame FRAME --interrupt-request-id REQUEST_ID --choice NO
.venv/bin/python -m harness continue_debug_once --session SESSION --generation GENERATION --boundary BOUNDARY --revision REVISION --frame FRAME
```

These are alternative operations, not a sequence to run blindly. Placeholders
come from fresh observed state; old values reject rather than refresh themselves.
An operator controlling the existing Python `Controller` instance can also call
`recover`; never start a second controller to obtain this API. Obtain fresh
observation and pass its session and control generation explicitly. At an eligible
activity poll use `request_interrupt`. Inspect the actual returned owned prompt,
then call `answer_interrupt` with YES or NO and its exact boundary, revision,
frame and originating interruption ID. At a raw debug prompt, preserve the error
frame and use `continue_debug_once` with its exact evidence. This sends one Space;
it does not repair the error or suppress later ones. Exact argument names are in
the [protocol](../contracts/operator-recovery.md#explicit-operator-recovery).

Check the returned status and then observe: prompt opening and answer delivery
are different from activity cancellation. WAIT may resume backlog. Unsupported
activities and failed recovery remain paused and require native controls. Ordinary
key/action/Resume stays forbidden at recovery boundaries; never auto-confirm.
A recovery timeout preserves `control_pending`, its durable admission and unknown
history separately from the original gameplay request. Passive status cannot clear
the live slot. After the fixed two-second native deadline, an explicit fresh
observe can reconcile transport capacity; it cannot establish the old outcome.
Any next recovery must be a deliberate new request against current evidence.

[Operations index](../runbook.md).
