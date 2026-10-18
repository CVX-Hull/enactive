---
owner: lead
status: active
review_trigger: Round 009 evidence, support claims or publication changes
---

# Bounded skills and native visible evidence

Round 009 implements passive cardinal movement stages and verifies the existing
native observation pipeline for this bounded task. A real one-tile outbound and
return completed with retained per-action evidence. The service still has no
autonomous supervisor or connected model provider. [Brief](../changes/009-bounded-skills-native-evidence.md),
[manifest](2026-10-17-bounded-skills-manifest.json),
[current contract](../protocol.md#passive-bounded-movement-skills).
Common checks pass 263 Python tests plus viewer, import, diagram and governance controls.
Protected publication remains pending at this source checkpoint.

## Implementation and review

The controller and skill share one pure cardinal movement policy. The public walk
keeps its existing result shape, including stopped after full displacement when
the final guard fails. Retained observation access returns a verified deep copy,
without refreshing authority. MovementStage binds the full leg and original
budgets, proposes one action, and independently verifies retained displacement.
Unknowns and disputed history cannot become completion or authorize a retry.

One isolated worker owned only skills.py and its tests from shared-helper checkpoint
`2cdfbf5cb2fac99c9d8dc8532663cd80721a38b9`. The lead owned contracts, shared extraction,
docs, integration and the single game/controller. Independent brief review found
five boundary gaps; all were corrected before dispatch. Shared extraction review
was clean. Skill review found a disputed credited source reported blocked at the
next proposal instead of unknown; the lead fixed it and added a regression.
Independent rereview was clean. Focused skill tests pass 23 cases; shared checks
before integration passed 239 Python tests and the existing viewer/docs controls.

The manual acceptance driver is local evidence, not a production integration.
Review corrected its preflight-versus-native admission filter and added unknown
recording for HTTP failures and exact-ID raw native receipt preservation. Logical
proposal IDs are explicitly mapped to native action UUIDs; Observe UUIDs cannot
stand in for movement. Driver error paths not directly exercised remain review
coverage, not native fault-injection claims.

## Source and graphical environment

The existing production native bridge is unchanged. Source and installed binary
were verified against the owned build extraction before reuse:
`native-reuse-before.json`. Installed SHA-256:
`e3c022b5da440d2e4a31fc537ea07c988c2a767bf96197b83de4c7224d47bf87`.
No native rebuild, global install, application/profile change or save editing was
needed. One wrapper-launched window used the explicit project userdir and the
visible localhost spectator. The spectator rendered genuine native tiles and
menus. A transient tool lock report cleared after the user correction; no unlock
workaround was used.

## Actual native-to-store acceptance

All numbered receipts below are local under `.runtime/evidence/round009/native/`.
The manifest identifies original frames, retained stores, mappings and scripts.
The UI was inspected at load, movement, inventory, save/reload and creature stop.

| Predicate or boundary | Source and observed result |
| --- | --- |
| Normal visible evidence | `010` retained Morgan Vale's actual DEFAULTMODE/normal_play frame through EvidenceStore. Position/turn, eight distinct visible neighbors and empty creature list were accepted. Source: native scene export, ordinary-boundary tagging and presented-frame revision. |
| Exact unit progress and completion | `015`–`017`: new task at relative `(1,0,0)`, west to `(0,0,0)`, east back to `(1,0,0)`. Revisions 12→14→16; turns 23623485→23623486→23623487. Both MovementStage results completed with one verified step, original task budgets, no pending action and passing final guards. Each result has exact logical/native mapping and before/after retained PNGs. |
| Pause and no replay | `018`–`020`: propose, then Pause, then attempt the exact proposed action. Host preflight rejected without a native action admission; assembler reported not_dispatched and skill earned zero progress. No retry was issued. |
| Actual stale evidence | The negative probe waited 3.2 actual wall seconds; store.current rejected the old receipt. Receipt time was not replaced. |
| Menu exclusion | Actual inventory `023` was rendered but rejected by EvidenceStore as not positively marked normal play; the original receipt/PNG remains outside the store. |
| Activity exclusion | Normal WAIT selection `030`, Pause `031` and Observe `032` returned activity_poll, no scene. Store rejected it. WAIT completed naturally while paused; `033` verified normal play afterward. Pause did not cancel or undo it. |
| Same-process reload | Morgan saved normally; `039` main menu rotated session. `044` retained the reloaded character with a new session and origin `(0,0,0)` at saved turn 23625287. `046` old-session LEFT was rejected before native dispatch. Reload/load/save command timeouts remain unknown even after current-state reconciliation. |
| Visible creature stop | Day/Kris Fink `059`–`061` exposed the actual visible zombie and Corinne Barone, consistent with the native creature sidebar. The real store retained this evidence; MovementStage returned blocked, zero steps, without a proposal or movement input. The scene also contained an adjacent locker and wall. |
| Visibility and provenance limits | Native exports eight adjacent cells and fields only for CLEAR visibility; creatures use the UI-visible creature query. Relative origin resets on game entry/exit. Source mapping below and portable negative tests enforce missing/invisible-field handling; no invisible-neighbor situation was manufactured in native play. |

The first demonstration (`012`–`013`) executed and recorded one valid east step,
then its evidence serializer called a nonexistent Progress.to_dict method. It
stopped before a return was dispatched. That script, failure and action mapping
are preserved. The corrected driver started a fresh explicitly chosen west/return
task from the observed new position; it did not replay the prior action.
An initial load request used timeout 25, outside the 15-second limit; it was
rejected before dispatch and corrected. Normal save/load transitions timed out
at the controller because they replaced the native session; explicit Observe
reconciled current state while preserving uncertain admissions.

## Fault and portable lanes

`047` supplies a fresh actual native receipt to isolated evidence-copy tests.
One store points at an empty copied bridge: ingestion rejects the missing PNG.
Another first retains the real frame, then receives contradictory copied position
metadata for that same identity: it rejects and marks the source disputed.
`frame-faults.json` labels both as fault injection. These do not demonstrate a
native renderer failure, nor alter the real bridge or game.

Portable tests cover all four directions, four-step full legs and return, missing,
stale and disputed evidence, generation A→B→A, malformed clocks and result data,
unknown/dispatched outcomes, duplicate identities, budget edges and final-guard
stops after full displacement. Synthetic PNG fixtures establish software checks,
not graphical validity. Native takeover/revocation and result-loss behavior are
reused from the unchanged production bridge's [round 008 acceptance](2026-10-17-native-recovery-planner.md);
this round adds fresh Pause, old-session rejection and actual timeout/no-replay evidence.

## Supported predicates and remaining gaps

Native `scene()` exports relative position/calendar turn, UI-visible creatures and
CLEAR adjacent terrain/furniture (`native/cdda_harness.cpp`, lines 156–204).
State assembly binds session/revision/category/actions/frame/boundary; game
entry/exit rotates session and origin. Presented frames and human input invalidate
native authority. Binding resolution separately checks that a registered action
has a usable current keyboard binding. EvidenceStore verifies source identity,
retained bytes, visibility shape and freshness; MovementStage adds checkpoint,
source-dispute, generation, exact displacement and budget predicates.

These exports suffice for the selected short cardinal waypoint task. No additional
map, inventory, health, damage or trap export is warranted. Visible floor is not a
claim of trap absence; no general combat, water safety, unseen-creature safety,
long-route planning or model efficacy is established. The source list covers more
negative configurations than the two live scenes; this is bounded acceptance.

The new skill diagram was rendered with the existing project-local Mermaid tool
and visually inspected for readable labels and correct caller/skill/native
responsibilities. Import Linter adds a fourth contract for the shared policy,
with negative fixtures for gameplay/controller, clock and filesystem dependencies.
No wire or persisted schema changed, and no compatibility path was introduced.

## Publication and retention

The [Project](https://github.com/users/CVX-Hull/projects/2) owns live execution
status. #20 and #33 close only after final checks, independent evidence review,
protected exact-head publication and merged-main CI; #19 reconciles their accepted
observation outcomes with #32. Future supervision and model wiring remain separate.
Original media and saves stay project-local; the Git manifest publishes hashes,
not all runtime media. No video or unattended-play claim is made. Both characters were saved normally;
the main-menu quit confirmation exited the game, the controller stopped cleanly,
and process inspection found no owned game/controller left. Final save/quit
receipts are `062`–`070`. The first common run found an ISO timestamp where the
manifest schema requires a date; the corrected run passed all 263 tests.
Independent evidence review verified source hashes, journal offsets/receipts,
retained frame hashes and the bounded claims; no material defect remained.
