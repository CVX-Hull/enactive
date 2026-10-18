---
owner: lead
status: historical
date: 2026-10-17
scope: Issues 29 and 32 native-v2 authority and passive gameplay evidence, on one macOS host; full recovery and gameplay pipeline excluded
---

# Input authority and evidence foundation acceptance

This increment gives each native input boundary explicit authority, replaces world
sessions on reload, and retains uncertain requests through host restart. A passive
module validates gameplay records and retains bounded original observations. It
adds no autonomous planner, recovery buttons or model spending.

Implementation source: `63e4dedd50d265a90717618a87208dc923ec7909`, based on
`abb58670f15d9c23daec43a32beda9a3d148d085`. Native source bytes were compared with
the exact compiled source; hashes are retained in the
[manifest](2026-10-17-foundation-implementation-manifest.json). Later acceptance,
control-maintenance and documentation changes do not change that native binary.
The protected PR identifies the final candidate and hosted checks; Issues
[#29](https://github.com/CVX-Hull/enactive/issues/29) and
[#32](https://github.com/CVX-Hull/enactive/issues/32) own live acceptance/closure.

## Separate evidence lanes

| Lane | Executed result | What it does not establish |
| --- | --- | --- |
| Portable implementation | Full common lane passed: 144 Python tests, Ruff, three Import Linter contracts and negative fixtures, document/governance checks, real Mermaid rendering and viewer regressions. Focused gameplay lane passed 46 tests after review repairs | Native execution or task success |
| Native build | Fresh pinned source extraction, original-file hashes and anchors verified, full six-job build succeeded; explicit menu additions rebuilt incrementally and the final binary installed/signed | Runtime correctness by compilation alone |
| Windowed native acceptance | Real menu, ordinary play, nested inventory, activity poll, raw diagnostic, takeover, world exit/reload, timeout/reconciliation, restart and version/token rejection probes below | Full recovery, general survival, other hosts or engine versions |
| Passive gameplay evidence | Strict records, provenance, clock age, immutable retention, reopen/session/conflict handling and capacity reservation exercised with synthetic fixtures | The later real gameplay evidence pipeline, still #33 |
| Review and visual | Separate native and evidence reviewers found defects; lead repaired them and reviewers verified fixes. Action sequence was rendered and inspected at ordinary width with an independent semantic check | Independent human approval or exhaustive race proof |

The common lane passed again after acceptance-schema/document changes with 145
Python tests. Hosted CI and any final candidate rerun are recorded with the PR. Test count is a scope indicator,
not a quality target. No new library was installed: records reuse project-pinned
jsonschema, dependency boundaries use Import Linter, and schemas/diagrams use
existing controls.

## Real native observations

All runs used the prepared `.runtime/Cataclysm.app` wrapper, explicit project
userdir, `FULLSCREEN=no`, 120×40 character settings and turn duration zero. Native
windows were 960×672 including window chrome. The browser spectator displayed
actual native frames and the new boundary label. No save content was inspected
for gameplay, edited or synthesized; normal UI selected, saved and loaded characters.

| Probe | Observed outcome and retained artifact names |
| --- | --- |
| Main menu and bounded remote input | Menu scene was null; explicit Resume and one DOWN moved the selected world. `menu-resume`, `menu-down` |
| Normal play and bounded step | H-world movement was accepted as input but CDDA safe mode blocked movement because a zombie was visible; no movement success was claimed. Day-world LEFT moved from `[0,0,0]` to `[-1,0,0]`, turn 5212812 → 5212813. `normal-east`, `day-resume`, `day-west` |
| Stale choice and takeover | Old revision was rejected. Native Escape closed inventory, paused remote control and changed authority; subsequent input was denied while paused. `stale-revision`, `takeover`, `paused-action` |
| Nested menu | Inventory was `menu`, with a distinct boundary and no inherited gameplay scene. Its actual popup was visually inspected. `inventory` |
| Activity DEFAULTMODE | A normal one-minute wait produced a real distraction confirmation, classified unsupported. Native No continued it. A read-only watcher captured `DEFAULTMODE` as `activity_poll`, scene null, recovery operations empty; the wait then finished normally. `activity-enter`, `activity-poll`, `watch_activity.py` |
| Raw debug prompt | Loading the retained TUTORIAL save naturally raised invalid tutorial-terrain diagnostics. `DEBUG_MSG` was `debug_prompt`, paused, scene null and successful actual-frame capture; Resume was denied. Native Space advanced individual diagnostics. Repeated tutorial errors led to closing the failed load without saving. No engine validation was disabled or “ignore future errors” selected. `loaded-observe`, `debug-resume-rejected`, `tutorial-load-debug.log` |
| Same-process world replacement | PID 37574 remained unchanged: H world session suffix `-1`, exit `-2`, reloaded H `-3`. Session/origin authority changed and an old-world request was rejected after explicit fresh Resume. `regular-loaded`, `world-exit`, `same-process-reload`, `old-world-rejected` |
| Real uncertain input | A normal Day load CONFIRM with a 0.2-second deadline timed out after dispatch. Native loading completed later under a new world session. Observe reconciled current state while request `7f4aa377-503a-49b3-8e7b-d7702b696bf9` remained unknown. It survived controller restart and another observation, still paused and without replay. `load-deadline`, `load-reconcile`, `load-reconciled-status`, `restart-status` |
| Native version and revocation gates | With the service stopped and the probe holding its exclusive bridge lock, a v1 observe request was rejected as unsupported protocol. After a fresh v2 observe, Resume using the pre-shutdown host token was rejected as revoked. The probe did not forge a successful action or change engine state. `native-mixed-version`, `native-revoked-token`, `native_negative_probes.py` |
| Spectator | Original tiles, normal-play label, paused state, relative position and unresolved-event timeline were visibly correct after restart. `viewer.png` |

A preliminary 0.001-second **observe** timeout tested only observation transport;
it was not an uncertain gameplay input. The later actual load input is the relevant
unknown-input evidence. The activity probe establishes correct classification and
scene exclusion. The complete rejection matrix and precise claim/commit race
interleavings additionally have portable tests; the live revoked-token probe is
not a timing measurement of every concurrent Pause race. Native Pause cannot undo
an input after its final commit check. No remote interruption/cancellation claim
is made for the unsupported distraction query or raw error prompt.

## Review repairs and failed attempts retained

- Native review found that a host crash after native dispatch could lose the request
  identity when its response was overwritten. The lead added a durable admission
  before request publication and terminal retirement afterward. A child-process
  SIGKILL regression, new-world observation and second restart preserve the unknown
  identity; the real timed-load/restart probe independently exercised persistence.
- Native review found an overly small explicit menu allowlist. Source-verified help,
  character, world-generation and related categories were added; generic DEFAULTMODE
  remains unsupported without the positive ordinary-input marker.
- Evidence review found that a conflicting noncurrent frame could regain authority.
  Repairs block the disputed identity and current authority; same-revision scene
  contradictions block peers. A second review caught lower-revision ordering that
  bypassed the identity block; the comparison now occurs first. Timestamp, scene,
  downward-revision and reopen regressions pass; reviewers verified the repairs.
- Initial common checks failed because isolated Import Linter fixtures lacked the
  new gameplay package. Fixtures were corrected, retaining negative dependency
  checks; the rerun passed. Earlier focused test failures and sandbox-only HTTP
  binding failure remain in local logs. They were not counted as native failures
  or replaced with mocks to claim gameplay acceptance.
- The tutorial-load failure is retained as a real engine/profile diagnostic. Regular
  H/Day saves supplied successful normal/reload probes. The tutorial save was neither
  repaired nor deleted and is not claimed healthy.
- The first manual protocol-probe guard mistook retained controller discovery for
  a running process and stopped before writing a request. The corrected probe used
  the existing exclusive bridge lock, verified service shutdown and then passed.

## Control and documentation maintenance

Updated architecture/protocol/overview/runbook/setup and the two accepted larger
designs to separate this implemented slice from future recovery and task execution.
The action diagram now includes the final native boundary/frame/token gate and
explicitly limits what a later Pause can undo. Its text equivalent and rendering
were reviewed together. The overview exposes capabilities and limits without
requiring the owner to read schemas or code.

C-PROTOCOL now recognizes seven native-v2 representations, including CLI discovery;
negative fixtures reject drift and unrecognized refactors. C-BOUNDARY adds the
passive gameplay import contract and exercises forbidden imports. C-PORTABLE adds
record/evidence, crash-admission and v2 rejection cases. C-RUNTIME/C-NATIVE now have
fresh scoped native evidence. Relevant control exercise and maintenance records
point here; previous reports retain the v1 and earlier portable evidence.

The acceptance manifest originally required a video for every native report. This
round used original still frames, so the existing JSON Schema now explicitly
permits `video: null`; it still rejects malformed video metadata and validates
intervals when a video exists. This removes pressure to invent media evidence
without weakening the provenance/hash/path checks. A regression exercises both
still-frame acceptance and invalid video values. No custom schema validator or
image decoder was added.

Maintenance cost includes manual native UI probing, reviewer repair cycles and one
full compile plus an incremental rebuild. No reliable long-term cadence or agent
performance improvement is inferred from this round. Follow-up remains #13 for
control upkeep and the scoped recovery/gameplay issues for further capability.

## Provenance, retention and cleanup

Host: macOS 26.6.2 arm64, Apple Clang 21, existing Python 3.14.7. Upstream:
CDDA 0.I-1 `7b2efa5cea38e4d4d97dd0e63b28b9148623da59`. Source/header archive
hashes, final native and signed installed hashes are in the manifest. Local build
workspace is `/private/tmp/cdda-player-build-8vgf_363`; source comparison confirms
the final checked-in native bridge matches compiled bytes. Runtime output and
media are retained under `.runtime/evidence/implementation-round/`, outside Git.
No video was captured. The manifest hashes curated originals, logs, probe code,
build/source receipts and stopped-session journal snapshots. A fresh clone lacks
these local media; absence does not represent a new native failure.

The game was saved/quit normally and controller sessions stopped. Process inspection
found no remaining CDDA or harness service. Saves, unresolved admissions and incident
logs are retained. Worker changes are preserved in the integrated source checkpoint
before temporary worktree/branch cleanup. Publication and exact post-merge cleanup
verification are recorded in the PR and issue closing evidence. No global Mac package,
profile, Git config or service changes were made. Temporary builds remain explicitly
owned; cleanup may remove them only after checking their manifest/ownership marker
and preserving provenance.

Remaining limits: #30/#31/#8 full recovery, #33 real gameplay observation pipeline,
waypoint skills/supervisor/planner, model efficiency evaluations, broad host support
and general autonomous survival are outside this acceptance. This round's native
and portable evidence must not close those outcomes.

## Coordinated migration addition

After the original native acceptance, the user required no backward compatibility
anywhere in the project. S-MIGRATION now applies to architecture, implementation,
configuration, stored state, tools and documentation. PRs must identify migrated
consumers/data, removal of old paths, version rejection tests and coordinated
cutover/rollback. Existing governance requires the standard and its control mapping;
C-PROTOCOL now checks nine forms, adding stored-request and viewer guards. Review
covers paths outside these narrow checks; matching literals do not prove that all
compatibility code is absent. Existing JSON Schema and test tools were reused.

Host startup now validates current stored requests/responses and blocks an orphaned
dispatch response instead of inventing a synthetic input identity. Build metadata
requires exact version 1. Unsupported-version tests cover build manifests, native
stored admissions/claims/responses and evidence stores; failed reads preserve input
bytes and never replay actions. The local unversioned build manifest was converted
once offline after ownership, pins, native source bytes and binary-hash checks.
Original and converted manifests plus a migration receipt are retained. The temporary
converter was removed; its text is retained only as an operation-history artifact.

Independent reviewer `migration_review` found that checking identity in the bounded
60-item viewer history could incorrectly reject the 61st retained admission. The
lead changed startup to track all validated input IDs separately and added a 61-record
regression. Initial passing focused/common checks did not detect this edge case;
the review finding and repair remain part of this acceptance history.

The final host-only startup check used the actual unresolved native admission from
this round, remained paused, replayed nothing and preserved admission/response bytes.
`migration-final-source-receipt.json` identifies these later host/tool/test bytes.
The original native build and graphical probes remain tied to source `63e4dedd`;
no new native binary, graphical demonstration or passive gameplay integration is
claimed by this addition. Final common checks passed 152 Python tests plus viewer, Ruff, Import Linter,
document/governance and diagram checks. The independent reviewer confirmed the
repair with no further findings; local logs are included in the manifest. Controls retain their
normal event/90-day maintenance duty, including review of new formats and gaps.
