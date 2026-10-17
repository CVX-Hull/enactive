---
owner: lead
status: historical
date: '2026-10-17'
scope: Consolidated goal audit, reuse provenance and fresh planner-loop gameplay timing
---

# Consolidated goal acceptance — 2026-10-17

Scope: the full [requested goal](../goal.md), evaluated against current files,
primary sources and retained evidence. Base checkpoint: `de695d3`; runtime remains
unchanged from `88dd803`. The checkpoint containing this report identifies the
final documentation/evidence changes. This is a dated acceptance record, not live
process status or a guarantee about all future CDDA situations.

## Requirement-by-requirement result

| Required outcome | Authoritative evidence inspected | Assessment |
| --- | --- | --- |
| Research and choose setup on capability/cost; reuse mature work | [Platform decision](../decisions/001-native-platform.md), pinned upstream/build recipe, [research](../research.md#reuse-candidates-rechecked--2026-10-17), local installed binary | Satisfied for the MVP. Native, Linux/display streaming, browser and screen-only alternatives are distinguished; costs not benchmarked are labeled. Exact references replace previously untraceable reuse claims; a recently updated browser candidate remains credible. |
| Principles → standards → controls across engineering levels | [Charter](../charter.md), [ten standards](../engineering.md), [12 controls](../controls.md), actual check orchestration, schemas, import rules, locks and tests | Implemented. Automated prevention/detection, manual review and native acceptance have explicit coverage limits. Mature parsers, linters and renderer are used. |
| Recent agentic/GPT pitfalls integrated into practice | [Evidence matrix](../research.md#recent-agentic-coding-evidence), S-AGENT/S-CODE/S-EVIDENCE, bounded delegation and independent findings | Implemented and exercised. Reviewers verified primary works and concrete controls; historical model performance is not treated as current proof. |
| Documentation and control maintenance | Metadata/schema/lifecycle checks, registry fields, review dates, replacement/retirement, [maintenance practices](../engineering.md#workflow-and-maintenance) | Implemented, with meaningful negative fixtures and manual semantic review. No scheduler or automatic date renewal. Long-term effectiveness remains unmeasured. |
| User reviewability, diagrams and walkthrough | [Overview](../overview.md), three editable/rendered diagrams and text equivalents, [walkthrough](../walkthrough.md), dated evidence and next-work links | Lead and independent reader inspections passed. User-facing guidance exposes limitations, authority, decisions and maintenance without requiring code reading. No user-study claim. |
| Authentic graphical play, control/recovery and efficiency research | [MVP acceptance](2026-10-17-mvp.md), pinned unchanged binary/source, six retained artifacts, fresh trial below, actual spectator inspection | Implemented and demonstrated in the recorded scenarios. Fresh trial adds planner-loop timing, ordinary creation, movement, timeout reconciliation, save/reload and paused handover. Codex in an active chat remains the planner. |
| Isolation, windowed operation, Git and delegation | Explicit wrapper userdir, FULLSCREEN=no, local caches/environments, owned temporary build marker, [environment history](../environment.md), Git/hook, role briefs and reviews | Current setup conforms. Earlier global feasibility changes and retained metadata refresh remain disclosed; this audit does not prove a pristine global history. One game/controller at handover; no global install or new scheduler. |

Independent engineering review found no material gap in outcomes 2–5. Independent
research/gameplay review found two P2 gaps: planner-loop latency was not measured,
and reuse conclusions lacked exact primary references. The lead addressed both
below. Targeted independent re-review recomputed receipt timings, checked all 20
artifact hashes, verified pinned primary-source statements and inspected gameplay
frames; both findings were resolved with no new material issue. This
acceptance does not silently add unattended survival or cross-platform support.

## Fresh real-game timing probe

Platform: the same Mac and CDDA 0.I-1 Tiles build as the MVP. Installed executable
SHA-256: `7f83a0661ae4970dea890edceb516386950f0e2951b5adae66acf5d4ca3c62b7`.
No native/controller/viewer code change or fresh native compilation. The prepared
wrapper supplies the project userdir; configuration is FULLSCREEN=no and
TURN_DURATION=0. Browser inspection showed actual native frames and paused control.

The game was not running at audit start, although the service and its old frame
remained. The spectator correctly labeled the old observation disconnected/stale.
The lead stopped the identified project service and started a new service/journal,
then launched the prepared game. Ordinary game UI created a separate default world
**Day** and default Evacuee/Survivor **Kris Fink**; existing world H was preserved.
No save editing, debug spawning, hidden-state lookup or guard relaxation occurred.

At a clear indoor floor aisle, each condition moved north from relative `(3,0,0)`
to `(3,-3,0)`, with no visible creatures in its observations. Baseline used three
separate active-chat action decisions, checking each returned scene/frame. After
walking back normally, the routine used one three-step guarded request, retaining
fresh observation and displacement checks per step. Both completed 3/3 tiles.
Native session: `1792269913768-30294`. Baseline revisions: 60→62→64→66; routine:
72→74→76→78. Turns advanced 5212803→5212806 and 5212809→5212812 respectively.

| Measured quantity | Three individual steps | One guarded request |
| --- | ---: | ---: |
| Planner play decisions | 3 | 1 |
| Observation/return-to-next-command gaps, summed | 14.362 s | 4.946 s |
| CLI execution time, summed | 0.581 s | 0.441 s |
| Start observation returned → final play command returned | 14.942 s | 5.386 s |
| Native exchanges | 3 observations + 3 actions | 3 observations + 3 actions |
| Native request-to-ready time, summed across all six exchanges | 0.310 s | 0.313 s |
| Action-only native request-to-ready time, summed | 0.195 s | 0.175 s |

**Interpretation:** this pair demonstrates fewer planner round trips while retaining
per-step native checks. Planner-loop gaps include image inspection, reasoning,
tool scheduling and execution/approval overhead; pure model deliberation cannot
be isolated from these tools. CLI durations use a monotonic clock; native estimates
use same-host wall timestamps and recorded 5-second deadlines. The end-to-end
metric stops at command return, excluding final interpretation. The routine's
final state was additionally read via `status` and visually inspected.

This is one sequential pair, not randomized or statistically representative. The
second trial benefits from route familiarity and occurs at a later game turn.
There was no parallel research or commentary during either timed interval, but
scheduling and other uncontrolled costs remain. No survival, safety or general
speed superiority is claimed. The older trial remains historical; it did not
measure planner-loop elapsed time. Exact observations and estimates are in the
[tracked timing results](2026-10-17-planner-timing.json).

Normal save/quit and reload preserved turn **5212812**, the scene and visible
neighbor layout. Relative coordinates reset on re-entry and were not mistaken
for global position. The survivor was left saved with remote control paused,
revision 91, in the visible spectator. Existing H saves were not changed by play;
new Day and tutorial saves are retained locally, not deleted as cleanup.

## Failures and maintenance lessons

- Tutorial preparation was unsuitable: its concrete floor is outside the existing
  guarded-walk allowlist. The lead saved/exited it and created a normal world;
  neither the guard nor the game was modified to make the trial pass.
- Selecting Day took longer than the initial five-second deadline. The controller
  froze; a subsequent observation found character creation, then explicit resume
  continued. The uncertain action was not replayed.
- A native app lookup by name launched a second copy because the wrapper-launched
  process was not identified by that lookup. The bridge refused ownership with
  “another game owns the bridge.” The lead identified and terminated only duplicate
  PID 31183 at its main menu; primary PID 30294 and service PID 30291 remained.
  `duplicate-window.png` is diagnostic evidence of the duplicate, not the trial's
  native scene. The actual trial was inspected through native bridge frames and
  the live browser. The runbook now warns that app lookup is not an existence check.
- Stopping the earlier controller appended a normal pause event to its live journal.
  The original accepted byte prefix still matched its recorded hash exactly. It
  was copied to `.runtime/evidence/mvp-journal-snapshot.jsonl`; the MVP manifest now
  points to that stable snapshot and records why. The full journal, including the
  later event, remains intact. New trial evidence likewise snapshots its journal.
  No failed event was removed or historical hash replaced to conceal a change.
- The first final-check attempt rejected manifest metadata that did not conform
  to the existing acceptance schema. The lead corrected the metadata without
  weakening the check. The completion manifest also indexes the inspected older
  video, explicitly labeled historical, separately from the fresh timing receipts.

## Research and final verification scope

The lead checked primary files at exact GitHub commits for CDDAi, old cdda-web and
the recently updated Play CDDA publisher. The [research comparison](../research.md#reuse-candidates-rechecked--2026-10-17)
records observed source behavior, revision dates and decision limits. It removes
an unsupported blanket implication that browser alternatives are unmaintained.
No browser candidate was built or benchmarked; the native decision remains tied
to the validated local observation/control requirements, with explicit revisit
triggers rather than convenience or a universal-performance claim.

The lead verified all six prior manifest artifacts against byte counts/hashes
before the trial, inspected the retained spectator/zombie evidence and sampled
the recorded gameplay video visually. The installed binary matches prior evidence;
runtime/setup source has no diff from the demonstrated implementation. Reviews
freshly ran metadata/governance and 29 focused tests. The final staged checkpoint
uses the full common hook (84 Python tests, four viewer scenarios, real diagram
rendering and the other documented checks). No remote CI execution is claimed.

[Completion manifest](2026-10-17-completion-manifest.json) records local artifact
hashes and source identity. Raw receipts, timing scripts, journal snapshots and
screenshots remain project-local; small results/manifests and this report are in
Git. A fresh checkout lacks those large local artifacts, as the retention policy
states. Native activity interruption, unsupported error screens, broad survival,
other hosts, remote branch protection and long-term effectiveness remain explicitly
limited/deferred; none is silently represented by this scoped acceptance.
