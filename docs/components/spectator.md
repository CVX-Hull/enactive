---
owner: lead
review_trigger: Spectator control, viewer presentation or supervision changes
status: active
---

# Spectator, host operations and delivery

The spectator shows actual owned target images, mechanical resources/custody and
separately labelled player claims. It owns no actor capability. The operator's
Pause is an independent permanent stop. The spectator is two parts
([ADR008](../decisions/008-evaluation-and-spectator.md)): a minimal **control path**
that keeps Pause, status and the frame, and a **viewer** that shows interpreted
records and can fail without effect. [Architecture](../architecture.md) and
[current contract](../contracts/computer-control.md) own system/port guarantees.

## Internal responsibilities

| Part | Owns |
| --- | --- |
| [Server](../../harness/server.py) | Selected `127.0.0.1` host/origin checks, bounded JSON, passive `/api/status` and `/api/source/ID` routes, independent Pause and the actor tool routes. It serves no page and no derived view. |
| [Gateway](../../tools/campaign_watch.py) | The page origin and static files, relayed status and source reads, Pause with a reason, and bounded forwarding of view reads. Its exit ends supervision, so it stays minimal. |
| [Page](../../web/) | Source presentation, labels, resource status, Pause feedback and the viewer's views. Served by the gateway. |
| Viewer (`harness/viewer`) | Read-only evaluator views, operator-selected curator result records and the curator runner's status ([contract](../contracts/evaluation.md#spectator-view-api-spectator-view2)). |
| [Supervisor](../../tools/campaign_supervision.py) | Starts and stops the custodian, gateway, keep-awake and viewer children; the guardian owns the custody deadline and the Pause receipt ([procedure](../operations/campaign-supervision.md)). |
| [Custodian](../../tools/campaign_run.py) | Frozen admission validation, exact native target, store/server lifetime and final cleanup/accounting receipt. |
| [Preparation](../../tools/prepare_game.py) | Project-local windowed options, normal mouse input, wrapper/userdir and shared exclusion before changes. |
| [Build](../../tools/build_computer.py) | Current mechanical SDL adapter/fixture plus source/output provenance; no gameplay claim. |

## Control path

**Custodian routes.** `GET /api/status` is passive `computer-status/2`;
`/api/source/ID` serves current session PNGs with retained identity/digest
verification. A failed spectator image read reports unavailable without calling
actor-side source-failure fencing, so it never affects actor capture or input integrity.
Browser reads do not select a player store or create observations.
`POST /api/pause` accepts `{}` and bypasses actor/executor/DB waits. Its
`computer-pause/1` response identifies the actual receiving session and original
stop facts. Authenticated actor tools use `/api/tool`; source reads use
`/api/player-source`. No CORS/public exposure, semantic recovery controls or
browser-issued actor handoff exists.

**Gateway.** It binds `127.0.0.1` on a free port, checks `Host` and `Origin`, and
serves only `index.html`, `web/app/*` and `web/vendor/*`, unchanged, with its
own security headers (`default-src 'self'`, `nosniff`, `no-store`). It relays only
`/api/status` and `/api/source/<session>-<n>` from the custodian, and accepts no
mutation except Pause.
- **Watching.** The page asks for no acknowledgement and nobody is required to watch:
  an unwatched run continues until a run limit or Pause stops it
  ([procedure](../operations/campaign-supervision.md)). The control strip takes the
  frame and status only from the two relayed routes, so a viewer outage cannot blank it.
- **Pause.** The page sends the operator's reason to the gateway under the
  [operator Pause contract](../contracts/computer-control.md#passive-spectator-reads-and-operator-pause).

**Failure.** Report stop-requested separately from native-confirmed Pause. A stale
image or retained launch receipt is historical evidence, not current liveness. Player
claims are fallible, separately labelled data. Delivered events, process absence and
host completion do not certify a save or objective. Unknown input remains stopped.
The finite custodian retains exact owned process/group handles and distinguishes
normal native exit before forced cleanup from exceptional termination. Failure to
verify absence stays unknown. No unrelated process scan/adoption is supported.

## Viewer

The viewer can fail independently of the run under the
[launch and lifetime rules](../contracts/evaluation.md#control-path-and-viewer).

The viewer lists only its own live run as `live`. Another run whose store is still
`live`, because its final `evaluate-run` pass never ran, is listed as `unfinished`, so the
page follows the [current live run (#435)](https://github.com/CVX-Hull/enactive/issues/435).

Diagnose → Overview shows [recorded custodian receipt facts](../contracts/evaluation.md#recorded-custodian-receipt)
beside the evaluator's outcome. A normally exited process and an unresolved input
acknowledgement can occur in the same run. The live Pause display uses its own
sources.

### Recorded browser entry

After supervisor shutdown, start the recorded viewer from the project checkout.

```sh
.venv/bin/python -m harness.viewer --recorded-page --root .runtime/evaluations --runs .runtime/computer-sessions
```

Open `http://127.0.0.1:8765/recorded/`. `--root` holds evaluation databases in
session-named subdirectories. `--runs` names a parent directory of campaign
packages with their manifests and original sources. For a sealed admission,
point `--runs` to the parent of its package and use a session-named copy of its
final evaluation files under a separate evaluation root. The viewer opens
Run Overview. Select a run and open **Recorded playback** to inspect its
findings and original frames with the shared playhead.

The recorded page reads existing records, labels unfinished stores, and offers
recorded playback controls. The CLI reserves the live evaluation option `--run`
for the separate API entry. The supervisor continues to serve the live page,
including the control path and independent Pause.

### Playback and live relay

The page's feed player shows the live control-path frame or the playhead's recorded
frame:
- Each frame is decoded before it replaces the last, and is drawn at its own pixel size. It never blanks or rescales as frames arrive.
- **1:1** (the default), **2×** and **3×** are pixel-exact and scroll instead of scaling. **Fit** scales smoothly within the column and the screen height.
- **Wide** puts the player first, across the page ([feed player display and controls (#437)](https://github.com/CVX-Hull/enactive/issues/437)).
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

The gateway forwards `GET /api/view/*` under the
[viewer forwarding limits and failure rules](../contracts/evaluation.md#control-path-and-viewer).

**Spectator frame.** The page's *Roles and containers* view puts a health strip over
role tabs. *Actor* lets the operator select an actor and request, inspect knowledge
selection and delivery, and follow an ID into the digest-verified frozen snapshot.
It also shows explicit reads, fallible public reports and their mechanical results.
Source links use recorded IDs and the frame verifier. Missing links, ages and journals
stay unavailable. See the [recorded knowledge contract](../contracts/evaluation.md#recorded-knowledge-and-public-reports).
Forgetting episodes from the [seven-day development lineage (#397)](../acceptance/2026-11-07-seven-day-397.md)
can open Live at a recorded step or explain why its frame is unavailable.

*Containers* shows the sidecar inventory and manifests. *Curator* uses the runner's
status file to show the last observed play position, covered prefix, lag, backlog,
last confirmed version and stamp, the session in flight and examined ranges. Steps
after the last successful read are unknown. Missing or partly written status shows no
figures. See the [runner status contract](../contracts/evaluation.md#curator-runner-status).
From configured terminal session receipts, *Curator* shows recorded metadata, draft
collection events and paged gate results. See the [session contract](../contracts/evaluation.md#recorded-curator-sessions).
Operator-configured result journals show submission and restore statuses and versions at a
fixed digest and byte cutoff. These journals establish neither run association, a semantic
verdict, the current published head nor lag. Missing, empty, unsupported, malformed and
changed sources remain distinct. See the [result contract](../contracts/evaluation.md#recorded-curator-results).

The *Knowledge* and *Programs* tabs show placeholders. In the health strip, placeholder
slots say “not yet measured” and actor cadence without a reading says “no data”.
The page reads the [spectator frame routes](../contracts/evaluation.md#spectator-frame-spectator-frame1)
independently of Pause.

## Assurance and evidence

The [testing guide](../testing.md) routes the HTTP boundary, gateway/forwarding,
guardian and compiled-native tests. Proven by fixture: forwarding refuses HTML, script
and oversize bodies; a viewer killed mid-run leaves status, frames and Pause
working; Pause with a reason forwards `{}` and records the reason; viewer exit does not
end supervision. A reference test checks that the player driver and host never name the
evaluator or viewer.

Limits:
- The viewer port is chosen before launch and recorded, not bound by the supervisor,
  so another loopback service could take it; the media and size rules still bound what
  the page accepts, but the answer is not proven to come from the viewer.
- The Pause receiver check is the Mac-specific `lsof` socket binding. It qualifies
  neither another OS nor a hostile local process.
- The page shows retained evidence. Human attention, physical paint and useful game
  effects are separate, and nothing records whether anyone watched.
- Actual browser/native visual inspection is separate from parser, hash and HTTP
  checks. [Operations](../runbook.md) route launch, Pause and cleanup; the
  [production report](../acceptance/2026-10-29-computer-control.md) retains
  native/player qualification.
