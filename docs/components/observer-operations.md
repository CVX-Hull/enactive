---
owner: harness maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Spectator, host operations and delivery

The spectator shows actual owned target images, mechanical resources/custody and
separately labelled player claims. It owns no actor capability. The operator's
Pause is an independent permanent stop. The spectator is two parts
([ADR008](../decisions/008-evaluation-and-spectator.md)): a minimal **control path**
that keeps Pause and the attention checks, and a **viewer** that shows interpreted
records and can fail without effect. [Architecture](../architecture.md) and
[current contract](../contracts/computer-control.md) own system/port guarantees.

## Internal responsibilities

| Part | Owns |
| --- | --- |
| [Server](../../harness/server.py) | Selected `127.0.0.1` host/origin checks, bounded JSON, passive `/api/status` and `/api/source/ID` routes, independent Pause and the actor tool routes. It serves no page and no derived view. |
| [Gateway](../../tools/campaign_watch.py) | The page origin and static files, relayed status and source reads, the check endpoint, Pause with a reason, and bounded forwarding of view reads. Its exit ends supervision, so it stays minimal. |
| [Check panel script](../../tools/campaign_watch_ui.js) | Reads the displayed session, freshness line, source details and frame on an explicit trusted click. |
| [Page](../../web/) | Source presentation, labels, resource status, Pause feedback and the viewer's views. Served by the gateway. |
| Viewer (`harness/viewer`) | Read-only evaluator views of the live run and archived runs ([contract](../contracts/evaluation.md#spectator-view-api-spectator-view1)). A separate process outside supervision. |
| [Supervisor](../../tools/campaign_supervision.py) | Starts and stops the custodian, gateway, keep-awake and viewer children; the guardian owns check deadlines and the Pause receipt ([procedure](../operations/campaign-supervision.md)). |
| [Custodian](../../tools/campaign_run.py) | Frozen admission validation, exact native target, store/server lifetime and final cleanup/accounting receipt. |
| [Preparation](../../tools/prepare_game.py) | Project-local windowed options, normal mouse input, wrapper/userdir and shared exclusion before changes. |
| [Build](../../tools/build_computer.py) | Current mechanical SDL adapter/fixture plus source/output provenance; no gameplay claim. |

## Control path

**Custodian routes.** `GET /api/status` is passive `computer-status/1`;
`/api/source/ID` serves current session PNGs with retained identity/digest
verification. A failed spectator image read reports unavailable without calling
actor-side source-failure fencing; canonical actor/capture/input integrity behavior
is unchanged. Browser reads do not select a player store or create observations.
`POST /api/pause` accepts `{}` and bypasses actor/executor/DB waits. Its
`computer-pause/1` response identifies the actual receiving session and original
stop facts. Authenticated actor tools use `/api/tool`; source reads use
`/api/player-source`. No CORS/public exposure, semantic recovery controls or
browser-issued actor handoff exists.

**Gateway.** It binds `127.0.0.1` on a free port, checks `Host` and `Origin`, and
serves only `index.html`, `web/app/*`, `web/vendor/*` and its own check script, with its
own security headers (`default-src 'self'`, `nosniff`, `no-store`). It relays only
`/api/status` and `/api/source/<session>-<n>` from the custodian.
- **Checks.** Under `--attention required` it injects the check panel before the
  frame viewport and the check script before `</head>`; under `best-effort` the page
  has no check and `/record` is refused. A check requires a trusted click, decoded
  in-viewport pixels, matching session/source/digest, an increasing number and a
  displayed status at most 12 seconds old. The panel takes the frame and status only
  from the two relayed routes, so a viewer outage cannot block a check.
- **Pause.** The page posts `{"reason": "loop" | "fault" | "spend" | "other"}`; a missing
  or unknown reason is recorded as `unspecified`, and the stop is never refused. The
  gateway sends the guardian the reason with the Pause time,
  then forwards `{}` to the custodian unchanged, after verifying the connected socket
  belongs to the exact custodian child. The reason lands in the watch terminal record
  (`pause_reason`, null when no owner Pause). Pause never waits for the viewer or a
  check.

**Failure.** Report stop-requested separately from native-confirmed Pause. A stale
image or retained launch receipt is historical evidence, not current liveness. Player
claims are fallible, separately labelled data. Delivered events, process absence and
host completion do not certify a save or objective. Unknown input remains stopped.
The finite custodian retains exact owned process/group handles and distinguishes
normal native exit before forced cleanup from exceptional termination. Failure to
verify absence stays unknown. No unrelated process scan/adoption is supported.

## Viewer

The supervisor starts `python -m harness.viewer` as an **unsupervised** child on a free
loopback port, with the live run directory, the evaluation root
(`.runtime/evaluations`) and optionally a directory of archived runs. It runs the
evaluator incrementally over the live run's records and serves `spectator-view/1`. It
writes only the live run's `live` evaluation store and never reaches the custodian, the
player context or any input.

The viewer lists only its own live run as `live`. Another run whose store is still
`live`, because its final `evaluate-run` pass never ran, is listed as `unfinished`, so the
page cannot follow it in place of the real live run
([#435](https://github.com/CVX-Hull/enactive/issues/435)).

The page's feed player shows the live control-path frame or the playhead's recorded
frame:
- Each frame is decoded before it replaces the last, and is drawn at its own pixel size. It never blanks or rescales as frames arrive.
- **1:1** (the default), **2×** and **3×** are pixel-exact and scroll instead of scaling. **Fit** scales smoothly within the column and the screen height.
- **Wide** puts the player first, across the page ([#437](https://github.com/CVX-Hull/enactive/issues/437)).
- **Hold** freezes the view only. It sends nothing to the run and is separate from Pause.
- The step buttons move the shared playhead.
- A caption names the decision on screen: its game clock, mode and the keys the player sent. While following live, it shows the newest step as of the frame on screen, so a held frame keeps its caption.
- **Liveness:** a frame-age badge turns amber when the "feed alive" Pause condition is met. A "steps behind live" badge jumps back to live.
- **Shortcuts** never take a key from a text field, the timeline, the Pause button or the open Pause sheet. Space also stays with any button, link or other control it would activate, and holding it down toggles only once:
  - Space: hold;
  - ← / →: step;
  - L: live;
  - T: wide;
  - F: full screen;
  - 0–3: scale.

  The "?" button lists them. The scale and wide choices are remembered per browser.

The gateway forwards `GET /api/view/*` to it on its own connection:
- a 2-second total deadline and a 4 MiB cap;
- only `application/json` and `image/png` responses; another media type, or a response
  over the cap, returns `502` with `{"error": "Viewer response refused"}`, so HTML or
  script from the viewer is never served;
- at most eight forwards at once, and the gateway's own headers on every reply;
- any other failure, including a refused connection, a timeout, a viewer status other
  than 200, 400, 404, 409 or 413, or no free forwarding slot, returns `503` with `{"viewer": "unavailable"}`. The page
  shows both `502` and `503` as "viewer unavailable".

**Spectator frame.** The page's *Roles and containers* view
([ADR 009](../decisions/009-curated-player.md) D18, `web/app/frame.js`) is a health strip
over role tabs. *Actor* lists the four #397 forgetting episodes from the tracked probe
episodes, each anchor opening the existing Live view at that step, or saying why its frame
is unavailable. *Containers* lists the sidecar inventory with each manifest. *Curator*,
*Knowledge* and *Programs* are placeholders that name the phase that brings them, and
health slots without data say "not yet measured" instead of a number. It is served by the
viewer's `/api/view/frame/*` routes ([contract](../contracts/evaluation.md#spectator-frame-spectator-frame1)),
reads only, and leaves the Pause path untouched.

The viewer's exit is never supervision loss: the guardian, startup wait and cleanup
treat it separately from the custodian, gateway and keep-awake children. The supervisor
stops it with them at the end and records its pid and port (`campaign-watch-start/3`
port, `campaign-watch-terminal/3` children). A viewer that cannot start leaves the run
and its checks unchanged.

## Assurance and evidence

The [testing guide](../testing.md) routes the HTTP boundary, gateway/forwarding,
guardian and compiled-native tests. Proven by fixture: forwarding refuses HTML, script
and oversize bodies; a viewer killed mid-run leaves required checks, status and Pause
working; Pause with a reason forwards `{}` and records the reason; viewer exit does not
end supervision. A reference test checks that the player driver and host never name the
evaluator or viewer.

Limits:
- The viewer port is chosen before launch and recorded, not bound by the supervisor,
  so another loopback service could take it; the media and size rules still bound what
  the page accepts, but the answer is not proven to come from the viewer.
- The Pause receiver check is the Mac-specific `lsof` socket binding. It qualifies
  neither another OS nor a hostile local process.
- A check is evidence that the displayed pixels and status were current at a click.
  Human attention, physical paint and useful game effects are separate.
- Actual browser/native visual inspection is separate from parser, hash and HTTP
  checks. [Operations](../runbook.md) route launch, Pause and cleanup; the
  [production report](../acceptance/2026-10-29-computer-control.md) retains
  native/player qualification.
