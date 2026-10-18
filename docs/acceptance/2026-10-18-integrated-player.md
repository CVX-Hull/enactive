---
owner: lead
status: historical
date: 2026-10-18
scope: Round012 integrated external-chat player, runtime and spectator; portable review and real windowed waypoint/Pause/continuation evidence, not model efficacy or survival
---

# Integrated player — round 012

One dedicated player sub-agent now answers bounded planning requests while the
service executes and verifies an explicitly admitted waypoint task. The lead owns
task admission, shared runtime and acceptance. This delivers the bounded runtime
[#52](https://github.com/CVX-Hull/cdda-player/issues/52) and spectator
[#23](https://github.com/CVX-Hull/cdda-player/issues/23) together under
[the brief](../changes/012-integrated-player.md). The
[current protocol](../protocol.md#integrated-gameplay-lifecycle) owns behavior;
[this manifest](2026-10-18-integrated-player-manifest.json) identifies local evidence.

## Source and independent review

Base main `ca92dac431b6a18a9cbaea19dd5b515bc7c17bdf`; reviewed brief checkpoint
`885efcbe65c3d38772eca3b09b11ace3dc742ce8`. Two disjoint project-local worktrees
produced viewer `72ca8b8d8599b3a210df6f08f9b939ebabd38d2f` and runtime
`9c8a3bb241d0d18930f4d947973e584563424223`; lead integrated as `a34edcf` and
`def9293`. Lead added real HTTP composition tests, review repairs and documentation.
`runtime-candidate.json` records exact backend/viewer file hashes including those
working-tree repairs. Backend hashes were unchanged throughout the accepted two
native tasks. Viewer timeline labels were corrected afterward and verified through
an actual browser reload; the final hash record includes that change. Native
source/binary identity remains unchanged from round011; no rebuild is claimed.

Brief review resolved stale-status invalidation, absolute publication deadlines
and external-chat accounting gaps. Boundary review found no blocking viewer/HTTP
issues. Independent combined review found three defects, all repaired and rerun:

- A journal exception after native movement incorrectly became known nondelivery.
  Exceptions after entering execution now retain an unknown outcome and pending intent.
- Persistent journal failure could kill the worker with stale executing status.
  Pause bookkeeping, diagnostics, unknown settlement and abandonment now survive it.
- One Pause could advance the epoch twice around an outstanding rejection.
  The worker consumes each signal before exposing the paused epoch; newer signals remain pending.

Independent re-review passed 20 runtime tests and found no remaining blocking
finding. A minor diagnostic carry-over was reset on new-run admission. The common
command passed **379 Python tests**, viewer regressions, import boundaries,
syntax, document, diagram, governance and whitespace controls. Two new tests use
real HTTP/runtime/controller composition over a synthetic native bridge, including
slow planning with repeated status reads and Pause/continuation. These tests are
portable evidence, not native gameplay. Journal/publication faults and timing races
were not deliberately injected into the live game.

## Real graphical acceptance

The installed binary hash is
`e3c022b5da440d2e4a31fc537ea07c988c2a767bf96197b83de4c7224d47bf87`.
The prepared wrapper used the explicit project userdir and `FULLSCREEN=no`.
The ordinary service ran on loopback port8766; no alternate in-process acceptance
controller dispatched gameplay. A helper retained supported HTTP results/frames.
The player sub-agent used only planning-request/plan operations, inspected each
actual retained PNG and authored exact-bound candidate JSON. It used no test
candidate generator, hidden map data, save editing or engine-validation bypass.

Recovery Eight / Morgan Vale loaded normally. Five runtime action receipts have
matching logical IDs, native request/result UUIDs, original receipt clocks and
retained frames. `native-summary.json` independently checks those associations.

| Probe | Native result |
| --- | --- |
| First east route, retained failure | Revision9→11, `(0,0,0)`→`(1,0,0)`: one verified step, then blocked. The existing post-step guard checks the next outbound tile even after reaching the waypoint; a cupboard beyond it stopped completion. No return plan or retry was fabricated. |
| New north-and-return task | Revision12→14→16, `(1,0,0)`→`(1,-1,0)`→`(1,0,0)`. Player independently proposed both legs; two verified steps, completed, paused and no lease owner. |
| Browser Pause at waypoint | New task revision17→19 reached `(1,-1,0)`. Player prepared but held its return candidate. Actual spectator Pause revoked ownership, retained one verified step and published epoch1. |
| Old proposal rejection | `023-gameplay-plan.json`: old return proposal rejected for lost lease. No action replay or extra movement. |
| Explicit continuation | Observe/Resume gave revision20; same task continued at epoch2 with a newly inspected/proposed return. Revision20→22 returned to `(1,0,0)`, two verified steps and completed. Original TaskSpec unchanged; remaining wall budget fell from71.51s at the recorded pause to47.97s at final capture, rather than renewing120s. |
| Ordinary cleanup | After completion the lead moved west once to restore the session's original relative origin, then used normal save-and-quit and main-menu quit. This manual cleanup is not credited to the player task. |

Slow native planning took longer than the three-second input-evidence window.
The runtime explicitly observed/revalidated equivalent visible state before
sending input. Status polling did not invalidate the original request, and the
original candidate binding was retained. The task/source frames and refreshed
frames remain in the run evidence stores.

The initial load, save confirmation and final quit commands timed out across
world/process transitions. Subsequent Observe established the loaded world or
normal main menu; final process exit was checked separately. Those old transport
outcomes remain unknown and were never replayed or relabeled successful receipts.
Historical gameplay/control unknowns stayed visible throughout. Save files were
preserved through CDDA's normal flow; no saves were deleted.

## Reviewability, maintenance and limits

The spectator was inspected at its ordinary window size during planning, blocked,
completed and paused states. It showed leg, player/executor, verified progress,
stop reason, next check, ownership, evidence and missing usage; Pause stayed visible.
The final screenshot includes completed continuation and the usage disclosure.
The responsibility diagram was inspected at about1000px, with independent visual
review against the contract; boxes/edges and role-versus-process meaning are readable.

Harness API spending was zero; Codex token/subscription usage was **unmeasured**.
Model identity is `external-unreported`, configuration `external-chat-v1`.
Sub-agent role instructions are advisory, not OS isolation. There is no paid API
configuration, general survival, generic semantic monitor or comparative model
performance claim. The two completed one-tile tasks do not establish broad reliability.
The first conservative guard stop remains a limitation tracked in
[#53](https://github.com/CVX-Hull/cdda-player/issues/53); no policy was weakened for
this demonstration. #24 retains model comparisons, #40 semantic monitoring and
#10 broad-objective task formation.

Development failures were retained: worker timing/planner regressions were repaired;
initial sandbox socket calls required authorized escalation. One preview command
used an unsupported renderer flag; another rendered a PNG successfully but then
failed the SVG-only accessibility parser. The final SVG receipt/common check passed,
and the PNG was visually inspected; neither failed command is counted as a pass.

Two implementation worktrees allowed parallel bounded work while one lead integrated
and owned all native resources. The larger outcome avoided publishing each internal
seam separately; review still found cross-boundary bugs, so component passes alone
were insufficient. Revisit allocation size when integration/review queues grow.
Use the documented player brief and timeout behavior for future sessions; reconsider
its model, latency, context or persistence only with evidence.

Owned game, controller and helper exited; port8766 was free and the temporary
spectator tab closed. No global package/profile/application changes were made.
Original media, raw receipts, helper scripts and journals remain ignored and local,
with hashes in the manifest; a fresh checkout does not contain them. Retain these
for review. GitHub records exact protected-head/main CI, issue closure and branch
cleanup; those publication facts are separate from this native observation report.
