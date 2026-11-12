---
owner: maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Start and observe

Use a prepared windowed project target and a fresh explicit package. The sole
current launch command is the [finite campaign custodian](campaign-run.md), which
validates `campaign-run/5` before effects. Do not invoke old controller, mission or
experimental proof commands or launch an unprepared/fullscreen application.

Observe a run through [finite-test supervision](campaign-supervision.md): launch it
and open its printed gateway URL. Nobody is required to watch; run limits and your
Pause are what stop a run. The
gateway serves the page, relays the custodian's status and source reads and owns
Pause; the custodian serves no page of its own.

1. Finish [local setup](../setup.md), retain native/app/adapter bytes and source provenance.
2. Select normal project-local CDDA input options before freezing; mouse is enabled and fullscreen disabled. The primitive layer does not override settings.
3. Freeze the exact clean source, native/adapter/initial-config hashes, target argv/cwd/environment, player host argv, route/context/prompt and original limits in a fresh `.runtime/computer-sessions/` package.
4. Launch only that selected package through supervision, which starts the custodian
   (`tools/campaign_run.py --run`), the gateway, keep-awake and the viewer.
5. Open the printed gateway URL. Inspect actual images and status, including original
   remaining resources and uncertainty.

**Control.** The page shows the current captured image and the custodian's status.
Pause, with a reason (loop, fault, spend or other), stops the custodian receiving it,
even while you inspect the viewer. A fresh admission after permanent Pause is
separate custody, not Resume. An identical image after an input is a valid capture,
not a failure. See the [observer component](../components/observer-operations.md)
for the control path and its limits.

**Viewer.** The supervisor also starts the read-only viewer as a separate process,
outside supervision, and stops it with the other children. It shows the evaluator's
interpretation of the live run and of archived runs when you pass
`--runs DIR` to supervision, each reading labelled with its source and confidence
([contract](../contracts/evaluation.md#spectator-view-api-spectator-view1)). Its
displays inform you and gate nothing; the Pause conditions it computes are advice.
If the page says **viewer unavailable**, the run, the frame and
Pause are unaffected. Read the run directory's `viewer-stderr.txt` for the cause. The
viewer is not restarted during a run.

The custodian reserves `started.json` before DB/native creation, owns one native
process group and passes the exact inherited lock/socket. A partial/used package
refuses; select a new package rather than delete markers or scan old inboxes.

The player calls `computer_observe` for actual pixels and interprets all game
meaning. Browser status/source reads are passive and cannot capture anew or
restore authority. Repeated identical images remain valid captures; a changed
image is not itself proof of useful progress. Returned source metadata retains
original presentation/receipt times and geometry.

Keep the native game windowed. The prepared SDL startup hints request reduced
activation but do not guarantee window order. If needed, return the spectator to
the front once; never disable native takeover or repeatedly steal focus.
[Pause/timeout](pause-timeout.md) and [ownership](mission-ownership.md) cover stops.
The [production report](../acceptance/2026-10-29-computer-control.md) retains actual
play and the limits of browser timing evidence.

[Operations index](../runbook.md).
