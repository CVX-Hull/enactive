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

The [seven-day campaign outcome](https://github.com/CVX-Hull/enactive/issues/10)
sets the next product target. The [delivery path](work.md#path-to-seven-day-survival)
starts with a bounded survival pilot and its first finding review, then campaign
continuity and an actual first-day rehearsal, an executable readiness decision,
and the seven-day run. The [first survival pilot](acceptance/2026-10-18-survival-pilot.md)
created a world but stopped on an unknown transition before a character spawned.
The [first-day rehearsal](acceptance/2026-10-18-first-day-rehearsal.md) then reached
Ramiro Winston, real ration pickup, a threat-driven retreat and an advisory player
handoff, but required user Escape at an unsupported pickup prompt after only
32 game seconds. It supplies no autonomous first-day success. Required human
rescue blocks campaign readiness. A desktop-tool access preflight failed before
load or input. The [direction-menu increment](changes/017-native-direction-menu.md)
then rebuilt the engine with its original bindings and
[verified](acceptance/2026-10-18-native-direction-menu.md) actual reload, pickup
cancellation/adjacent selection and current-tile behavior without user keys.
It used18inputs/218.939seconds with no game-time advance; lifecycle receipts remain
unknown. The recorded objective now appears above the native frame. Broader
continuity, usable supplies/rest and autonomous first-day survival remain open.
The [second rehearsal](acceptance/2026-10-18-first-day-rehearsal-002.md) then reached
Rosendo/Hotevilla at22h14m25s: real meals/water, medical-supply excursion/return,
overnight wake and matching save/application-restart reload, without human rescue.
It stopped at an unsupported sound-distraction prompt; an existing native UI
binding canceled it for normal cleanup.208charges included one agent-operated
desktop key; six lifecycle receipts stay unknown. It is still short of a full
day. The [same-character continuation](acceptance/2026-10-18-first-day-completion.md)
then reached **24h14m29s alive with zero human rescue**, using227charged inputs
including9cleanup and two autonomous native-window responses. Endpoint thirst,
unknown exact sleep duration, nine lifecycle acknowledgments and two cleanup
requests outside the deadline policy qualify this functional result. The first
partial report remains history; no seven-day success follows. The next gate is
#81's independent readiness protocol. [Operator permissions](operator-permissions.md)
separates tested command rules from activation and the candidate-only waypoint
planner from a designated campaign operator. The [operator probe](changes/020-campaign-operator.md)
must verify actual delegated input and takeover before campaign adoption.
Campaigns also expose concrete memory, planning,
monitoring and viewer needs. The [review workflow](project-management.md#campaign-driven-improvement)
routes observed problems into bounded improvements and checks their effect in later
play. This is a manual engineering process; continuous policy learning remains
unimplemented, and a successful campaign alone does not prove an improvement helped.

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
