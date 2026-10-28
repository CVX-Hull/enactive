---
owner: maintainer
review_trigger: Changes to this operating task, supported setup or recovery behavior
status: active
---

# Start and observe

The existing service option `serve --timeout SECONDS` sets the native exchange
ceiling (default5, supported maximum15seconds). It returns as soon as a matching
ACK arrives and remains bounded by the original operation/mission deadlines.
Freeze the chosen value in the run configuration/argv; legitimate loading may
need more than the default. This is separate from routine responsiveness targets
and cannot repair a lost request identity, extend original operation deadlines or
authorize replay. GitHub owns any next experiment and its prospective conditions.

For an admitted mission, start only the controller service below, then follow
[typed mission requests](mission-requests.md#typed-mission-requests-and-the-player). The designated
player launches the owned windowed child through `enactive_lifecycle`; manual
bundle launch and raw CLI inputs below are engineering procedures outside a
nonterminal mission.

First inspect existing terminals/processes to avoid starting a second game or
controller. A native app lookup by name may launch a second copy when the game
was started directly by its wrapper; do not use lookup as a process-existence check.
Use the existing spectator to inspect native frames when a tool cannot bind the
already-running native window.
Do not kill an unrelated service to free a port. From this checkout,
use an available loopback port and launch only the prepared project bundle:

```sh
.venv/bin/python -m harness serve --port 8766 --timeout 15
```

The explicit15second native wait uses the existing bounded setting. Actual world
selection exceeded the default5second wait in qualification004; ordinary replies
still return immediately. Record the chosen value in a mission's frozen setup;
it cannot renew original root deadlines or repair an expired/unknown input.
[Latency accounting and proposed targets](../evaluation.md#latency-budgets-for-interactive-play)
separate loading, skill execution, observer updates and model/tool overhead.
The spectator's local timing disclosure can prepare fixed **Show export JSON**
data for DOM collection, using the same bounded observer-timing/3 history as its
download. Collect after the measured interval before reload; a later explicit click
refreshes the export. This avoids a download-event wait without introducing another
telemetry service. A status-only probe establishes no native/frame latency.

Outside an admitted mission, `open .runtime/Cataclysm.app` launches the prepared
app **bundle**, which executes that project's wrapper and
explicit userdir. Direct terminal execution of the wrapper produced a game that
native app automation could not bind in the first-day rehearsal. Bundle launch
exposed the actual window in a subsequent menu-only probe. Neither launch method
by itself proves recovery works. For an agent campaign, verify current actual
native frames, windowed configuration and control access before loading the
character; do not make a desktop UI tool's binding/unlock availability a
prerequisite for supported engine menus. A UI tool may launch the exact stopped bundle directly,
but must not use app lookup to check whether another game is already running.

Open http://127.0.0.1:8766/ to watch. Port 8766 was used for the MVP because 8765
was occupied; current availability must be checked. Observe, interpret the frame,
then explicitly resume. Read returned session/revision after every command:

```sh
.venv/bin/python -m harness observe
.venv/bin/python -m harness resume
.venv/bin/python -m harness action inventory --expect SESSION:REVISION
.venv/bin/python -m harness walk north --steps 3 --expect SESSION:REVISION
.venv/bin/python -m harness pause
```

SESSION:REVISION is a placeholder for values from the observation used to decide
the action. Resume changes revision. `ready` is an input-boundary acknowledgment,
not proof that an objective succeeded. Reinterpret prompts and new frames. The
viewer displays the recorded objective read-only. Outside a mission, the CLI
`goal` command records text without starting an agent. Mission objectives come
from their immutable admission.
A registered action can be rejected if it has no usable single-key binding. A
walk may report `stopped` after all requested steps completed; inspect `steps`
and the frame before deciding again. See the [protocol](../protocol.md).

Public `walk` returns an aggregate with a nested `observation`, its phase and
original receipt clock, and a separate `terminal_response`. Inspect both: after
an uncertain input the observation can still be the pre-action image. Missing or
unavailable observations remain explicit. Capture the nested frame when retaining
walk evidence; an aggregate is not a native response packet.

Every stopped walk now leaves dispatch paused and frozen. Obtain a separate fresh
Observe, inspect its actual image and the stop reason, reassess, then explicitly
Resume before choosing the next input using its current session/revision. Status,
internal preflight and an earlier retained frame cannot substitute for this step.
Do not automatically replace a stopped walk with ordinary movement. The controller
requires Observe/Resume; it cannot prove your interpretation. Actual approval
denial still ends an investigation under its admitted stop rules; no retry,
permission expansion or actor/transport switch is a recovery around it.

Use each command's actual CLI grammar: Observe, Resume, Pause, status and goal do
not accept `--expect`; ordinary key/action/walk require it. Observe and Resume
do accept `--timeout`, subject to the admission's ordinary deadline. Consult
generated `--help` or the shared parser rather than copying
flags between commands. Keep large capture envelopes redirected and read original
numbered receipt JSON; a truncated tool display is not an original receipt.

[Operations index](../runbook.md).
