---
owner: lead
review_trigger: Historical grooming record; supersede with new evidence rather than rewriting outcomes
status: historical
date: 2026-10-18
scope: Post-migration backlog review, campaign critical path, next integrated round and Project navigation
---

# Seven-day survival backlog checkpoint

The next product result is the user-approved fresh-character seven-day survival
campaign, [#10](https://github.com/CVX-Hull/enactive/issues/10). This grooming reviews
all 26 open work Issues and the 63-item existing Project after the Enactive
migration. Inspected source: `f5efffe2003a198d269e2363d77b14ae01445ecd`.
The [current work page](../work.md) gives the reviewable path; GitHub owns live
planning. This report is a scoped decision/acceptance record, not a new tracker.

## What can be attempted now

Source and dated native evidence support a supervised short pilot with ordinary
graphical menus and low-level controls. Earlier MVP evidence includes food/water,
shelter/travel and normal save/reload; integrated/waypoint acceptance demonstrates
bounded execution, exact receipts, Pause and continuation. Those are historical
scenarios, not a current ordinary fresh character, first-day survival or seven days.

| Boundary | Current evidence and limit | Campaign consequence |
| --- | --- | --- |
| Creation, inventory and menus | [MVP native probes](2026-10-17-mvp.md); current [menu boundary contract](../protocol.md#transport-and-state) has no structured scene, and advertised bindings can reject | Pilot verifies actual ordinary creation/input and supply semantics using fresh frames; unsupported cases become real gaps |
| Movement and threats | [Waypoint acceptance](2026-10-18-waypoint-readiness.md); conservative local movement stops on visible creatures and lacks general combat/trap/damage guarantees | Active player observes/reasons/retreats or stops; no hidden-state routing or stronger-model assurance |
| Automated task | [Runtime at the retained campaign baseline](https://github.com/CVX-Hull/enactive/blob/7ef93c802b9d51524057c2655934bf32f1b954d5/harness/runtime.py) and [task budgets](https://github.com/CVX-Hull/enactive/blob/433ed973afe312d03f777d8b102a0cba528af746/harness/gameplay/contracts.py) implement bounded waypoint-return, not general survival | Pilot may use direct capable-player input; a general task framework, VLA or trained policy is not presumed necessary |
| Continuity and limits | Ordinary engine save/reload is demonstrated; durable campaign context and mechanically enforced aggregate resources across player/restart are not implemented | #79 must demonstrate the minimum advisory handoff/accounting, fresh applicability and reauthorization before deciding-run readiness |
| Evidence and UI | Actual frames, receipts and bounded task progress are retained; semantic judgments and external chat usage remain fallible/unreported | Pilot must expose what the user can understand/control and what evidence is absent, rather than inventing successful outcomes or cost |

Two read-only sweeps inspected capability boundaries and the complete open backlog.
The lead checked source and actual native dependency/sub-issue edges and Project
values. Returning an agent recommendation is not acceptance: the lead retained
#78's whole-outcome M estimate rather than reducing it to S from the play-time cap.
The source/native bridge is unchanged by grooming; no live game state was inspected.

## Decisions and all-open-item dispositions

| Issues | Disposition and next evidence |
| --- | --- |
| #10 | Keep L/Low aggregate open, Backlog/Now. Its seven-day success criteria and milestone remain unchanged; no unexecuted work is marked Done. |
| #78, #83 | Select one integrated pilot/first-review round. #78 stays Ready/Now with no open prerequisite. #83 becomes Backlog/Now and remains blocked by #78; share evidence/table inspection without duplicating the retrospective or weakening #83's routing/adoption acceptance. |
| #79, #80 | Remain post-pilot Backlog/Next with #78 dependency. Freeze scope/estimates from observed friction; design may overlap, shared implementation/native validation stays serialized. |
| #81, #82 | Keep genuine gates: #81 after #79/#80/#83; #82 after #81. Split and estimate the L campaign before Ready. No attempt date or seven-day throughput forecast is invented. |
| #71, #70 | #71 stays Ready/Next for a read-only 5–10-question, at-most-three-episode extraction/label pilot if review capacity permits; replace its obsolete dispatch SHA with current clean-main verification. #70 remains blocked by #71 and must be decomposed before Ready. Neither blocks the campaign pilot. |
| #16, #24, #25, #72, #73, #74 | Preserve comparison/tier acceptance and #24's real #72/#73/#74 blockers. Move #73 to Later with that lane, updating its own and #16's text. Add missing #73 blocked-by #72 plus blocked label: complete both-arm native export requires the missing matched execution. Contract/adapter preparation may overlap. Revisit on a demonstrated campaign accounting/export gap or explicit comparison selection; do not monopolize the shared runtime speculatively. |
| #40, #42, #43, #44 | Keep generic monitoring/escalation work and its native gates Later. Use actual campaign findings for requirements; a capable player's manual assessment is not a delivered semantic monitor. |
| #26 | Keep Next and October 24/event review, unchanged size/estimate/date. Correct coordination from closed #13 to current maintenance owner #75. No new literature search or automatic date renewal is claimed. |
| #75 | Migration/CI failure events have triggered scoped review. Move to Next and surface risk; current main passed after fixture hardening, but the exact historical timeout cause is unproven. Preserve the existing request/journal capture action and 0.5–1-session review estimate; not a pilot dependency unless a real readiness defect emerges. |
| #9, #11, #12, #27, #47 | Retain conditional native-runner, other-host/browser, broader tooling, advanced learning and tutorial-repair triggers. No speculative infrastructure or ordinary-creation tutorial dependency is added. |

The actual campaign chain is **#78 → #79/#80/#83 → #81 → #82**. #10 depends on
#82's completion; its child hierarchy describes decomposition, not an execution
edge back to #10. Closed #5 remains accepted provenance. This is not a dependency
cycle or a reason to remove useful historical links. Independent review identified
the one missing delivery dependency, #73→#72, from the actual both-arm acceptance;
it is added only in the comparative lane. No campaign edge, hierarchy, milestone,
ownership, estimate field, execution status or start/finish date changes are selected;
the three Horizon changes are #83→Now, #75→Next and #73→Later.
Existing Ready #78/#71 stay Ready. Historical-change archives remain outside the
Project and accepted delivery counts. No Issues are created, closed or reopened.

## Next round, allocation and forecasting

One M/Medium integrated round combines #78's bounded attempt with #83's first
source-linked finding/disposition review, then produces concrete #79/#80 briefs.
Provisional **3–5 focused sessions** include admission, play, shared review/routing,
rework and publication, assuming no bridge redesign or substantive implementation.
This range is uncalibrated effort, not elapsed time; original #78 M/Medium 2–4 and
#83 S/Medium 1–2 ranges remain recorded and are not mechanically summed. Split any
actual implementation gap before committing to it. Measure throughput before a
seven-day execution forecast; the remaining chain has Low-confidence unknowns.

The existing pilot ceiling remains 150 charged inputs, 45 minutes and six in-game
hours, counting creation and expanded walk steps; ten inputs and the final two
minutes are reserved for eligible cleanup. Admission fixes exact source/native
identity, ordinary scenario, one player/executor, manual cumulative accounting and
stop rules. No retrospective budget renewal or paid provider is selected. A gap
result may finish investigation/review but cannot satisfy first-day or campaign
success. The whole-round effort estimate does not enlarge this play allowance.

The lead owns design/admission, the shared game/save/port, the sole executor,
finding adjudication and final verification. One player can propose from visible
evidence, with read-only source/evidence reviews alongside. No implementation worker
is needed to begin the pilot. After actual #79/#80 boundaries freeze, at most two
disjoint worktree writers may implement separately; the lead integrates and serializes
native validation. Read-only #71 work must not delay this review/validation queue.

Campaign findings route through the existing [workflow](../project-management.md#campaign-driven-improvement)
to context/memory, planning, monitoring and UI owners, with actual blocker edges
only when justified. Generalized lessons, held-out comparisons and model training
retain their own evidence requirements. No second tracker, recorder or control
framework is introduced. Revisit the path after pilot/rehearsal findings, material
failure, source/model/engine changes or the existing #26/#75 triggers.

## Verification and publication boundary

Independent clean-context review checked the concrete Issue/Project plan and
current-doc diff before mutation; the missing #73→#72 dependency was corrected
and rechecked. Live readback then passed for all 84 Issue records (63 work Issues
and 21 historical-change archives), including the unchanged set of 26 open work
Issues. Eight bodies changed: #10/#16/#26/#71/#73/#75/#78/#83. Labels only add risk
to #75 and blocked to #73. The only dependency addition is #73 blocked by #72;
all campaign and sub-issue edges are preserved, and the open dependency graph is
acyclic. No Issue was created, closed or reopened.

All 63 Project item identities, owners, Status, size, confidence, priority and
start/finish values were preserved. The only manual field changes are the three
Horizon moves above; #78/#71 remain Ready, with no active execution introduced.
All five milestones, Project field definitions, views, public visibility and
repository link, and the active main ruleset match the original snapshot.
Historical archives remain outside the Project. The Project README now links
the campaign path without recreating issue-level status. One-off private snapshot
and verification receipts are project-local under `.runtime/backlog-grooming/`;
they do not create a maintained tracking service.

Common checks and protected exact-candidate/merged-main CI are required for
publication; the publishing PR records those terminal results. This grooming
includes no native build, game launch,
save update, new survival evidence or global setup. Historical migration and CI
failures remain in their original evidence records.
