---
owner: maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Start and observe

Use a prepared windowed project target and freeze a fresh explicit package
following the [finite campaign procedure](campaign-run.md). The custodian
validates the selected package before launch. Do not invoke old controller,
mission or experimental proof commands or launch an unprepared/fullscreen
application.

[Launch through finite-test supervision](campaign-supervision.md#freeze-launch-and-inspect)
and open the printed gateway URL. Nobody is required to watch; run limits and your
Pause are what stop a run. The
gateway serves the page, relays the custodian's status and source reads and owns
Pause; the custodian serves no page of its own.

1. Finish [local setup](../setup.md), retain native/app/adapter bytes and source provenance.
2. Select normal project-local CDDA input options before freezing; mouse is enabled and fullscreen disabled. The primitive layer does not override settings.
3. [Freeze the package](campaign-run.md#construct-a-package) with the exact clean source,
   native, adapter and initial-config hashes, target argv, cwd and environment,
   player host argv, route, context, prompt and original limits in a fresh
   `.runtime/computer-sessions/` directory.
4. Launch only that selected package through supervision, which starts the custodian
   (`tools/campaign_run.py --run`), the gateway, keep-awake and the viewer.
5. Open the printed gateway URL. Inspect actual images and status, including original
   remaining resources and uncertainty.

**Control.** The page shows the current captured image and the custodian's status.
Pause, with a reason (loop, fault, spend or other), stops the custodian receiving it,
even while you inspect the viewer. A fresh admission after permanent Pause is
separate custody, not Resume. An identical image after an input is a valid capture,
not a failure. See the [spectator component](../components/spectator.md)
for the control path and its limits.

**Viewer.** The supervisor also starts the read-only viewer as a separate process,
outside supervision, and stops it with the other children. It shows the evaluator's
interpretation of the live run and of archived runs when you pass
`--runs DIR` to supervision, each reading labelled with its source and confidence
([contract](../contracts/spectator-view.md#spectator-view-api-spectator-view3)). Its
displays inform you and gate nothing; the Pause conditions it computes are advice.

After the supervisor exits, open completed runs through the
[recorded browser entry](#recorded-browser-entry).

For recorded curator drafts, repeat `--curator-drafts LABEL=DIR` on the supervisor
command, naming curator state directories holding `drafts/` and `drafts-archive/`.
Under **Memory & Curator** → **Curator drafts & gate results** → **Curator drafts**,
select those labels to inspect active and archived draft manifests without reading
draft body files. See the [draft contract](../contracts/spectator-view.md#curator-drafts).

For recorded curator results, repeat `--curator-results LABEL=FILE` on the supervisor
command, naming existing current result files or snapshots. Under **Memory & Curator** →
**Curator drafts & gate results** → **Gate results**, select those labels to display
recorded submission/restore status, `from_drafts` IDs and versions. No source is selected
by default; labels do not associate a journal with the live player run. Files are read
only, with a 16 MiB input ceiling and digest-bound paging. Empty, unavailable, unsupported
and unknown data stay explicit; publication is not factual verification or measured lag.
See the [result contract](../contracts/spectator-view.md#recorded-curator-results).

For recorded curator sessions, repeat `--curator-sessions LABEL=FILE` with individual
terminal `close-out.json` files. Select the operator-supplied alias under **Memory & Curator** →
**Curator drafts & gate results** → **Curator sessions**; the recorded session and its
draft collection events do not establish a run association or current draft state. See the
[session contract](../contracts/spectator-view.md#recorded-curator-sessions).

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
[Pause/timeout](pause-timeout.md) and [run custody](run-custody.md) cover stops.
The [production report](../acceptance/2026-10-29-computer-control.md) retains actual
play and the limits of browser timing evidence.

## Viewer procedures

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
**Watch** with the selected run's recorded screen, timeline and Story Feed; use
**Memory & Curator** and **Diagnostics** to inspect curated knowledge, spend and telemetry.

To include what an admission's boundary grooming spent, add `--curator-grooming FILE` with
its `grooming-summary.json`. It is shown only for the run that receipt names; without it
**Diagnostics** says that grooming is recorded outside the admission and marks the combined
figure partial. Name the package directory itself, not a symlink to it: the viewer
[opens a package's files](../contracts/spectator-view.md#host-telemetry-and-curator-spend)
without following one.

The recorded page reads existing records, labels unfinished stores, and offers
recorded playback controls. The CLI reserves the live evaluation option `--run`
for the separate API entry. The supervisor continues to serve the live page,
including the control path and independent Pause.

### Playback and live relay

The page's feed player shows the live control-path frame or the playhead's recorded
frame:
- Each frame is decoded before it replaces the last, and is drawn at its own pixel size. It never blanks or rescales as frames arrive.
- **Fit** (the default) scales smoothly within the column and the screen height; **1:1**, **2×** and **3×** are pixel-exact and scroll instead of scaling.
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

[Operations index](../runbook.md).
