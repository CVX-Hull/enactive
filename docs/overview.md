---
owner: maintainer
review_trigger: Capabilities, guarantees, architecture, priorities or decisions change
status: active
---

# Project overview

This is a versioned overview, not a live process-status page.

## What we are building

An agent plays real Cataclysm: Dark Days Ahead while you watch the graphical game
and retain control. The harness makes observations, actions and uncertainty visible.
It currently needs Codex in an active chat to choose goals and interpret scenes.
The service alone does not play autonomously.

The consolidated implementation [goal](goal.md) records the full requested scope.
The [completion audit](acceptance/2026-10-17-completion.md) maps that scope to
implemented outcomes, independent review and dated gameplay evidence.
Direction and constraints live in the [charter](charter.md). This page summarizes
current behavior; detailed promises live in [architecture](architecture.md).

Changes migrate the system as a whole. We maintain one current version of each
contract and remove old paths, including in tools and stored metadata. Unsupported
state stops with evidence preserved until an explicit offline migration is complete.
[S-MIGRATION](engineering.md#s-migration-one-current-contract-coordinated-migration)
defines the rule and its enforcement.

## How it works

Current system context: **who decides, what you see, and where you retain control**.

![Current CDDA Player context: you direct Codex, the local harness validates inputs and shows real frames, and CDDA decides outcomes.](diagrams/context.svg)

Boxes show responsibilities, not four independent local processes. Arrows name
information/control flow. The harness contains the Python controller and browser
spectator; the native bridge runs inside CDDA. Codex planning needs this active
chat. [Editable diagram](diagrams/context.mmd).

CDDA decides game outcomes. The controller checks whether a requested input is
allowed in the observed state. The viewer shows actual game frames and control
state. [Architecture](architecture.md) explains these responsibilities; [decisions](decisions/001-native-platform.md)
explain why native integration was selected and when we would reconsider it.

## What works and what the evidence means

| Capability | Status and user consequence | Evidence |
| --- | --- | --- |
| Graphical local play | Verified in the dated MVP session; normal native window and browser spectator | [MVP acceptance](acceptance/2026-10-17-mvp.md) |
| Observe, menus, individual inputs, supplies and save/reload | Demonstrated; results still require interpretation after each input | [Acceptance probes](acceptance/2026-10-17-mvp.md#real-game-acceptance-2026-10-17) |
| Guarded short walks | Limited: cardinal directions, at most eight steps, conservative terrain and visible-creature stops | [Current contract](protocol.md#closed-loop-play-and-observations) |
| Planner round trips | One real three-tile comparison used three individual decisions versus one guarded request, retaining per-step checks; not a general speed or safety result | [Timing trial](acceptance/2026-10-17-completion.md#fresh-real-game-timing-probe) |
| Input authority and takeover | Native-v3 distinguishes ordinary play, menus, activity polls and debug prompts; revoked tokens and old worlds are rejected. Already-committed actions and activities cannot be undone by Pause | [Recovery acceptance](acceptance/2026-10-17-recovery-memory.md) |
| Retained gameplay evidence and memory | Typed records, bounded evidence, historical facts, interpretations and invalidated plan candidates are portable-tested; full real pipeline acceptance remains later work | [Current evidence contract](protocol.md#passive-gameplay-records-and-evidence) |
| Bounded planner interface | Injected providers return validated data with cancellation, deadlines and cost accounting; fixtures pass, but no concrete model provider or autonomous supervisor is connected | [Planner contract](protocol.md#bounded-injected-planner) |
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
[tracked content defect](https://github.com/CVX-Hull/cdda-player/issues/47).
There is no structured trap/damage guarantee or general combat policy.

## Current direction and decisions

The original consolidated MVP goal is verified within its stated boundaries. Its
[audit](acceptance/2026-10-17-completion.md) records planner-loop timing and reuse
comparisons. The [foundation increment](acceptance/2026-10-17-foundation-implementation.md)
adds native input authority and passive evidence; it does not add autonomous play. The documentation [brief](changes/002-documentation-review.md)
explains the visual explanations, lifecycle records and maintenance checks.
Next priorities and any open issues are in [work](work.md). Current priorities are control
reliability and evidence quality before expanding unattended play. The [recovery and memory increment](acceptance/2026-10-17-recovery-memory.md)
adds Python recovery transport and passive task memory. Public recovery controls and passive evaluation records are implemented. Round 008
adds the Pause timing repair, integrated native recovery evidence and a bounded
planner port; native predicate and waypoint supervision work remains separate.

The [tiered-gameplay proposal](research-tiered-gameplay.md) explores a capable
planner, bounded skills and feedback, with additional model tiers conditional on
measured benefit. Its [tracked outcome](https://github.com/CVX-Hull/cdda-player/issues/16)
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
Waypoint execution and a connected model provider remain future capabilities. The [implementation brief](changes/005-foundation-implementation.md)
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
