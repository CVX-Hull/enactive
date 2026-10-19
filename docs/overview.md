---
owner: maintainer
review_trigger: Capabilities, guarantees, architecture, priorities or decisions change
status: active
---

# Project overview

This is a versioned overview, not a live process-status page.

**Enactive** is the canonical repository name. The [migration record](acceptance/2026-10-18-enactive-migration.md)
explains preserved work, historical PR records and the limits of metadata removal.

## What we are building

An agent plays real Cataclysm: Dark Days Ahead while you watch the graphical game
and retain control. The harness makes observations, actions and uncertainty visible.
It needs an active Codex player to choose plans and interpret scenes. A dedicated
player sub-agent can act as a bounded campaign operator while the lead supervises;
the waypoint planner has a separate candidate-only role.
The service executes an explicitly started waypoint task with per-step feedback;
without a player response it stops on a deadline. General survival is not implemented.
The[earlier resource discovery](acceptance/2026-10-18-daylight-practice.md) verified
phone-off daylight and partial medical practice on Ned Meyers/Belgium, then stopped
before a complete remaining-day fit. It remains qualified historical evidence.

The [functional survival report](acceptance/2026-10-19-functional-survival.md)
verifies two days alive on normally created Ned Meyers / Belgium.
[020 accepted day three](acceptance/2026-10-19-midpoint-survival.md), normal midpoint
native restart/exact saved-turn reload and genuine fresh F ordinary-input
replacement. [021 stopped](acceptance/2026-10-19-treatment-stop.md) after confirming
raw water and a boiling tool but no heat, and retreating from a distant hostile.
[024 accepted day four](acceptance/2026-10-19-four-day-survival.md) at5558422,
96h00m22 after the original start, after failed floor rest, successful bench wake
and adaptation to interrupted upstairs waiting. Days five through seven remain
incomplete. [025 verified the first250mL clean-water batch](acceptance/2026-10-19-first-clean-water.md)
using ordinary outdoor fire, boiling and bottle storage, after rejected sites and
a transient unsupported-menu return. Fresh stock is1.5L clean/500mL untreated/
12rations; remaining-three-day coverage is unproved. Last normal5559025 is alive/
Comfortable with blank needs at the assessed outdoor worksite. One owned game/
controller remain paused, with no ordinary actor, queued input or live slots.
Small fire and open-window retreat remain; final shutdown is unproved. Lifecycle
ACKs, failed attempts and corrections remain qualified.

[#129](https://github.com/CVX-Hull/enactive/issues/129) owns further resources/whole
forecast; [work](work.md) links the path. Closed019–025 grant no successor authority.
025 closes for a source/forecast handoff after its narrow first-output result.
Measured daily care exceeded the prior forecast; [048](changes/048-water-coverage-budget.md)
proposes a finite budget revision, with input-budget delegation still a decision.
The user delegated prospective time extensions to prioritize quality data;
[047](changes/047-quality-data-continuation.md) records025's time/phase decision,
retaining original clocks, costs and input ceilings. Its [046 decision](changes/046-replan-known-nondelivery.md)
prospectively distinguished known non-delivery capability failures from authority
refusals. The [operator workflow](protocol.md#designated-campaign-operator) permits
bounded passive reassessment only when an admission allows it, then explicit
reassignment at supported settled state. This manual control is not general
monitoring. Stable literal CLI access worked without recurring human approval
prompts; no broader permission rule or Codex restart was required.

The [project goal](goal.md) records the original MVP and active seven-day campaign
continuation. The [MVP completion audit](acceptance/2026-10-17-completion.md) maps
the original scope to implemented outcomes, independent review and dated gameplay
evidence; it does not establish the campaign continuation.
Direction and constraints live in the [charter](charter.md). This page summarizes
current behavior; detailed promises live in [architecture](architecture.md).

Changes migrate the system as a whole. We maintain one current version of each
contract and remove old paths, including in tools and stored metadata. Unsupported
state stops with evidence preserved until an explicit offline migration is complete.
[S-MIGRATION](engineering.md#s-migration-one-current-contract-coordinated-migration)
defines the rule and its enforcement.

## How it works

Current system context: **who decides, what you see, and where you retain control**.

![Player responsibilities: one campaign operator or the leased waypoint service sends input, with explicit handoff and user Pause.](diagrams/player.svg)

Boxes show responsibilities, not separate model tiers. The harness contains the
run service, controller and spectator; the native bridge runs inside CDDA. A player
sub-agent keeps gameplay context separate from engineering work. A designated
operator uses ordinary input checked by the controller under a finite brief; a waypoint planner
submits candidate data for the leased service to execute. Only one arrangement
owns input at a time. Actor assignment is procedural; it does not isolate inherited
tools. [Editable diagram](diagrams/player.mmd), [handoff contract](protocol.md#designated-campaign-operator).

CDDA decides game outcomes. The controller checks whether a requested input is
allowed in the observed state. The viewer shows actual game frames and control
state. [Architecture](architecture.md) explains these responsibilities; [decisions](decisions/001-native-platform.md)
explain why native integration was selected and when we would reconsider it.

## What works and what the evidence means

| Capability | Status and user consequence | Evidence |
| --- | --- | --- |
| Graphical local play | Verified in the dated MVP session; normal native window and browser spectator | [MVP acceptance](acceptance/2026-10-17-mvp.md) |
| Observe, menus, individual inputs, supplies and save/reload | Demonstrated; results still require interpretation after each input | [Acceptance probes](acceptance/2026-10-17-mvp.md#real-game-acceptance-2026-10-17) |
| Ordinary direction queries | Common chooser preserves CDDA bindings; real adjacent-pickup cancellation/selection and saved-character reload worked without user keys | [Direction-menu acceptance](acceptance/2026-10-18-native-direction-menu.md) |
| Guarded short walks | Limited: cardinal directions, at most eight steps, conservative terrain and visible-creature stops | [Current contract](protocol.md#closed-loop-play-and-observations) |
| Planner round trips | One real three-tile comparison used three individual decisions versus one guarded request, retaining per-step checks; not a general speed or safety result | [Timing trial](acceptance/2026-10-17-completion.md#fresh-real-game-timing-probe) |
| Input authority and takeover | Native-v3 distinguishes ordinary play, menus, activity polls and debug prompts; revoked tokens and old worlds are rejected. Already-committed actions and activities cannot be undone by Pause | [Recovery acceptance](acceptance/2026-10-17-recovery-memory.md) |
| Retained gameplay evidence and memory | Typed records and bounded retention now have native normal/menu/activity, movement and reload evidence; missing/conflicting copies are tested in a separate fault lane | [Current evidence contract](protocol.md#passive-gameplay-records-and-evidence) |
| Passive movement skills | One proposed step at a time with cumulative route history; version 3 separates reached-target verification from eligibility for another step | [Skill contract](protocol.md#passive-bounded-movement-skills) |
| Run input ownership | Explicit task owns input; competing remote inputs reject; Pause immediately revokes further dispatch | [Ownership contract](protocol.md#controller-run-ownership) |
| Waypoint task supervision | Explicit start, fresh stage planning, verified steps, visible stops and continuation with original history/budgets | [Supervisor contract](protocol.md#passive-waypoint-supervision) |
| Player planning handoff | Active-chat player returns bounded candidates; slow decisions require fresh evidence revalidation. Missing/stale replies stop; chat usage remains unmeasured | [Planner contract](protocol.md#bounded-injected-planner) |
| Dedicated gameplay operator | Two real input phases consumed carried water, conserved rations and handed off paused for lead inspection; one saved-character result, no resupply or survival guarantee | [Operator acceptance](acceptance/2026-10-18-campaign-operator.md) |
| Evaluation records | Passive versioned outcome/cost recorder and offline summaries; external planning and future adapters are not automatically measured | [Evaluation guide](evaluation.md) |
| Autonomous survival | Not implemented; Codex remains the planner | [Current scope](architecture.md#scope-and-responsibilities) |
| Reproducible installation | Fresh build demonstrated on this Mac; other hosts remain unverified | [Setup](setup.md), [historical provenance](acceptance/2026-10-17-mvp-manifest.json) |
| Engineering assurance | Portable checks, source checks and review; native gameplay is a separate validation lane | [Control map](controls.md) |

A dated demonstration supports the tested scenarios. It does not guarantee every
future game state, host or version. The spectator, CLI and Python operator API can request an eligible activity interruption, answer its
exact confirmation and continue a raw debug prompt once. Recovery stays paused;
delivery is not task success. Native WAIT YES/NO, finished-activity races, lost
results, revocation ordering, save/reload and raw-debug recovery have been exercised.
[Round 008 evidence](acceptance/2026-10-17-native-recovery-planner.md) separates normal
production gameplay from controlled fault probes and preserves unsuccessful attempts.
Native keyboard control remains available. Tutorial save loading still has a
[tracked content defect](https://github.com/CVX-Hull/enactive/issues/47).
There is no structured trap/damage guarantee or general combat policy. The movement
skill verifies the reached waypoint without requiring a further clear tile. Every
remaining step and the actual return direction still require a visible empty
allowlisted neighbor; public `walk` remains conservative after each step.
[Waypoint readiness](changes/014-waypoint-readiness.md) records this decision and
the gates remaining before a comparative experiment. Its
[acceptance](acceptance/2026-10-18-waypoint-readiness.md) records real completion,
intermediate-obstacle stopping and Pause/continuation, including failures.

## Current direction and decisions

The original consolidated MVP goal is verified within its stated boundaries. Its
[audit](acceptance/2026-10-17-completion.md) records planner-loop timing and reuse
comparisons. The [foundation increment](acceptance/2026-10-17-foundation-implementation.md)
adds native input authority and passive evidence; it does not add autonomous play. The documentation [brief](changes/002-documentation-review.md)
explains the visual explanations, lifecycle records and maintenance checks.
Current priorities are in [work](work.md). The integrated player uses the accepted
native authority, evidence, skills, planner and supervisor components in one
explicit task lifecycle. The spectator shows the current leg, verified progress,
next check and stop reason; deeper evidence and unknown usage remain inspectable.
The [integration brief](changes/012-integrated-player.md) explains the player
arrangement; [round 012 acceptance](acceptance/2026-10-18-integrated-player.md) records
two completed native tasks, Pause/continuation and the unsuccessful first route. Comparative model efficiency, generic semantic
monitoring and broader survival remain separately tracked follow-ups.

The [seven-day target](https://github.com/CVX-Hull/enactive/issues/10) remains open:
a normally created fresh character, essential needs/shelter/rest and meaningful
supply/travel choices, normal save/restart and actual player-context replacement,
with watchable graphics and user Pause. The user must not supply routine keys or
rescue. [Work](work.md#campaign-delivery-path) links the full retained lineage,
including failed, assisted and partial attempts.

The [qualified development first day](acceptance/2026-10-18-first-day-completion.md)
reached24h14m29s alive without human rescue. Endpoint Thirsty, unknown exact sleep
duration, nine lifecycle ACKs and two cleanup deadline deviations remain explicit.
The [two-phase operator result](acceptance/2026-10-18-campaign-operator.md) verified
carried-water consumption, ration conservation and paused lead inspection with
13delegated inputs; it did not establish water resupply or seven-day feasibility.
[Operator permissions](operator-permissions.md) separates tested rules from live
activation and actor instructions from actual security isolation.

[Readiness #81](acceptance/2026-10-18-seven-day-readiness.md) then accepted a frozen
finite protocol, actual actor/native preflight and seven owned daily outcomes.
The [first deciding campaign](acceptance/2026-10-18-seven-day-stop.md) normally
created Ned Meyers/Belgium and collected supplies, but stopped after13game seconds
on an approval rejection after a guarded-walk stop lacked a fresh verified player
observation. The rejection was honored and normal Save/Quit preserved the partial;
48charges include the denied request and cleanup. No first-day/seven-day success.
The [walk correction](acceptance/2026-10-18-walk-reassessment.md) now retains the
actual stop observation and freezes input until explicit fresh Observe/Resume.
Its native zero-step probe passed after an earlier unexercised load probe;17combined
charges and zero game advance, with lifecycle ACKs still unknown. Broader permissions
were unnecessary. Further campaign play requires prospective admission, not unused
allowance from the stopped attempt.

The [integrated003 partial](acceptance/2026-10-18-integrated-day1.md) secured more
supplies and boiling/fuel materials but stopped before day1: a local heat plan did
not fit the complete remaining day within its input allowance. Normal cleanup
retained259whole charges,119elapsed game seconds and all unknowns. Further play
requires a prospective complete-day plan and allocation; no seven-day result yet.

Campaigns expose concrete memory, planning, monitoring and UI needs. The
[review workflow](project-management.md#campaign-driven-improvement) routes observed
problems into owned bounded improvements and checks their effect in later play.
This is manual engineering; continuous policy learning remains unimplemented,
and one successful campaign cannot establish causal improvement or reliability.

The [memory study](research-memory-representations.md) compares six mathematical
and engineering views, with reproducible simulations and negative results. It
recommends traceable evidence, explicit applicability, simple replay/query
baselines and offline evaluated lessons. The next step is a bounded visible-trace
benchmark; persistent memory, continuous policy improvement and new model tiers
remain unimplemented. [Study evidence](acceptance/2026-10-18-memory-representations.md).

The [tiered-gameplay proposal](research-tiered-gameplay.md) explores a capable
planner, bounded skills and feedback, with additional model tiers conditional on
measured benefit. Its [tracked outcome](https://github.com/CVX-Hull/enactive/issues/16)
links the design, implementation and evaluation work; it is not current gameplay
capability.

The [outcome-monitoring design](design/outcome-monitoring.md) explains the next
architectural extension: distinguish exact visible facts from fallible semantic
judgments, keep unknowns explicit, and choose between another observation,
stronger reasoning, plan repair or operator help. Its
[evidence review](research-outcome-monitoring.md) includes October 2026 research.
This remains proposed behavior, not an implemented general monitor.

The accepted foundation design specifies [native operator recovery](design/native-control.md)
and [waypoint-and-return gameplay](design/gameplay.md). Its
[brief](changes/004-gameplay-foundation.md) explains the source findings, ownership
and verification gates. Boundary/session authority and typed evidence are now
implemented, along with scoped operator activity interruption and debug continuation.
The integrated runtime connects waypoint execution to the active-chat player;
a separately paid model API is not configured. The [implementation brief](changes/005-foundation-implementation.md)
explains the accepted slice and its limits.

No platform migration or new hosted service is being proposed. We will reopen
platform and transport choices when requirements or measured maintenance costs
justify it, using the [decision records](decisions/002-local-contract.md).

## How you stay in control of the project

Start here for direction, behavior, limitations and next decisions. Follow links
for design and evidence; code-level detail is optional. Significant proposals
state the problem, visible change, alternatives, maintenance cost, reversibility,
evidence and uncertainties, and whether your decision is needed. Routine work
continues under agreed direction. Changes to your constraints require your input.

For a first session, use the [spectator walkthrough](walkthrough.md). To review
behavior, follow the [action and recovery views](architecture.md#action-and-recovery-views).
For governance, the [maintenance table](controls.md#maintenance) separates last
exercise, maintenance review, effectiveness and next review. These are recorded
observations, not live badges. [Work](work.md) links open decisions and exceptions
in the public GitHub Project. The [project workflow](project-management.md) explains
ownership, planning, parallel implementation and acceptance.

[Run and recover](runbook.md) · [Standards and workflow](engineering.md) ·
[Research basis](research.md) · [Environment history](environment.md)
