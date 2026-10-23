---
owner: maintainer
review_trigger: Capabilities, guarantees, architecture or product direction change
status: active
---

# Project overview

## What we are building

**Enactive** lets an agent play CDDA-class survival/roguelike games while you watch
and retain control. Cataclysm: Dark Days Ahead is the first actual integration;
other games are not yet qualified. The [charter](charter.md) owns the game-family
constraint, purpose and principles.

A dedicated active Codex player chooses plans, interprets visible scenes and uses
memory. One local mission writer executes its requests through the native game.
The engineering lead maintains the project and verifies outcomes; routine play
must not depend on lead tactics, keys or memory curation. This is not yet an
accepted unattended seven-day survival service.

The browser spectator shows actual Tiles frames, ownership, progress and
uncertainty. The game stays windowed and project-local. You can Pause or take
over in the native window; Pause cannot undo a committed action or cancel an
already running activity. Memory and advice help decisions but never authorize input.

## How it works

![One designated player uses memory and semantic skills through the mission writer; the user retains Pause.](diagrams/player.svg)

Boxes show responsibilities, not mandatory separate model tiers. The player can
use higher-level skills, visible-label shortcuts or ordinary keys/text/clicks,
then inspect what actually happened. CDDA decides outcomes. The writer accounts
for original resources and the controller/native bridge checks current ownership
and delivery. A returned key alone does not establish success.

The background adviser reads recorded trajectories and proposes fallible advice
without pausing ordinary player reasoning. Software links selected procedures,
actions and results; the player decides applicability and adoption. Historical
facts, procedures and proposals retain their sources and limitations.

[Editable diagram](diagrams/player.mmd) · [Architecture](architecture.md) ·
[Player contract](protocol.md#designated-campaign-operator)

## What works and what the evidence means

| Capability | Demonstrated scope and practical limit |
| --- | --- |
| Graphical play and user control | Actual native Tiles frames and browser spectator; Pause/takeover qualifications are scoped in the [architecture](architecture.md#action-and-recovery-views) and dated reports. |
| Useful skill composition | [Independent mission024](acceptance/2026-10-21-independent-supply-shelter.md) combines supplies/care, purposeful navigation/replanning, shelter/rest, memory correction, successor continuity and normal lifecycle. This is a bounded mission. |
| Organic ordinary interaction | [Learning006](acceptance/2026-10-22-discovery-learning-sixth-attempt.md) and [local-refusal001](acceptance/2026-10-22-native-local-refusal.md) exercise ordinary discovery/refusal/cancellation. Recent [Luna013](acceptance/2026-10-23-luna-responsiveness-thirteenth-attempt.md) independently loads/adopts identity, approaches a locker, picks up a ration and ends normally. Wider game-family behavior and full independent continuation remain unqualified. |
| Procedure memory and background advice | Learning006 demonstrates scoped reuse/refinement, actual fresh-context application and useful play while advice is pending. Technical creation assistance is disclosed. Retrieval/presentation is not attention or causal learning benefit. |
| Save, reload and ending | [Capture001](acceptance/2026-10-22-native-capture-preconditions.md) qualifies ordinary input and normal same-character save/reload/ending on the rebuilt boundary; actual PNG drift remains unexercised there. [Fresh008](acceptance/2026-10-22-independent-seven-day-eighth-attempt.md) retains the motivating failure. [Native001](acceptance/2026-10-22-native-save-refresh.md) also qualifies one unit-geometry click; non-unit/wider mouse remains unqualified. |
| Seven-day survival | The [first campaign](acceptance/2026-10-19-seven-day-survival.md) completed under supervision. The fresh independent outcome remains unaccepted; [#145](https://github.com/CVX-Hull/enactive/issues/145) owns follow-through. |
| Watchable stopped history | The [local-refusal001 report](acceptance/2026-10-22-native-local-refusal.md) records actual STOPPED/HISTORY/DISCONNECTED presentation, no current mission decision and a timeout diagnostic explicitly labelled historical. |
| Latency | Current play speed is unacceptable. [Fresh010](acceptance/2026-10-22-independent-seven-day-tenth-attempt.md) retains the motivating useful-play evidence. [Luna013](acceptance/2026-10-23-luna-responsiveness-thirteenth-attempt.md) verifies useful pickup and normal ending but advances two game seconds in596wall seconds; short tool execution and longer inter-call gaps do not isolate inference or qualify a routine cohort. [Evaluation](evaluation.md#latency-budgets-for-interactive-play) owns definitions; [#164](https://github.com/CVX-Hull/enactive/issues/164) owns delivery. |

Recent Luna trials verify an actual fresh CLI producer, compact text/detail/typed
images and scoped browser timing; [008](acceptance/2026-10-23-luna-responsiveness-eighth-attempt.md)
loads/adopts/saves but fails ending. [012](acceptance/2026-10-23-luna-responsiveness-twelfth-attempt.md)
retains an unsupported identity Claim and deadline failure. The
[latest013](acceptance/2026-10-23-luna-responsiveness-thirteenth-attempt.md) independently
loads/adopts with appropriate identity sources, picks up a ration and normally
Saves/exits/Finishes stopped. Useful travel, a complete learning mission, apparent
responsiveness and independent seven-day survival remain unaccepted.
Subsequent [015](changes/060-responsive-player.md#closed015-and-restart-checkpoint)
verifies software-owned request identities but fails a premature Load continuation
before character adoption. Its actor and owned processes are closed; the local
refusal repair remains outstanding. Restarting the desktop loads current tool
declarations, not a completed gameplay fix.

The [responsive-player brief](changes/060-responsive-player.md) addresses actual
duplication and manual memory metadata using the existing SDK/cache/staging
facilities. Canonical evidence and player judgment remain separate from mechanical
binding. Source/SDK checks cannot substitute for a new actual independent
continuation and useful-play measurement. [Work](work.md#current-integrated-checkpoint)
links decisive reports; the archive retains intermediate failures.
Current MCP also assigns request IDs and collection waits through that same SDK;
explicit as-of evidence, scope and execution budgets remain player choices.

Source tests, native builds, real gameplay and protected publication are separate
evidence lanes. A dated demonstration supports its tested scenario, source and
host. Failures and unknown acknowledgments stay recorded even when separate
effect evidence resolves what happened. A later repair cannot relabel a failed run.
The [work map](work.md#current-integrated-checkpoint) links decisive reports; those
reports own exact costs, turns, interventions and unexercised branches.

There is no general combat, trap/damage or survival guarantee. Optional movement
skills use conservative visible evidence. Current supported boundaries and known
coupling belong in [architecture](architecture.md) and [protocol](protocol.md).
[Operator permissions](operator-permissions.md) distinguishes project-preapproved
play from deterministic input checks, and procedural roles from security isolation.
No visible approval prompt is weaker evidence than complete host review telemetry,
which remains unavailable.

## How development reaches acceptance

We develop a useful behavior through focused checks and finite real play, then
qualify the coherent outcome. The [development-first workflow](project-management.md#development-first-delivery)
owns the required checks, independent review and protected publication gates.
Progress, a passing test or an investigated failure cannot substitute for the full
requested outcome. The [control map](controls.md) records enforcement and gaps.

## Current direction and decisions

[Player-owned campaigns #136](https://github.com/CVX-Hull/enactive/issues/136) and
[the independent seven-day outcome #145](https://github.com/CVX-Hull/enactive/issues/145)
own delivery scope; the public Project owns priorities and execution status.
The [discovery-and-learning brief](changes/057-discovery-learning-campaign.md)
explains the integrated design and links earlier research. Broader training,
model comparisons, paid providers and causal efficacy studies are separate choices.
No paid provider is configured.

Prefer existing engine/platform capabilities and maintained tools when they advance
the overall objective. Useful long-term accelerators can justify investment;
choices and reversal conditions belong in [ADRs](decisions/002-local-contract.md).
We keep one current contract and migrate all affected callers/state together under
[S-MIGRATION](engineering.md#s-migration-one-current-contract-coordinated-migration).

## How you stay in control of the project

Use this page for capabilities and limits, [GitHub Project](https://github.com/users/CVX-Hull/projects/2)
for live work and [work](work.md) for evidence navigation. Significant proposals
explain user consequences, alternatives, maintenance cost and open decisions;
implementation detail stays behind links. Routine work continues under the agreed
constraints, while changes to those constraints require your input.

For a first session, use the [spectator walkthrough](walkthrough.md). For technical
review, follow [architecture](architecture.md), [standards](engineering.md) and the
[maintenance table](controls.md#maintenance). Their owners and review triggers
support upkeep; a recent date is not proof of accuracy. Historical MVP and migration
records remain in [acceptance](acceptance/), rather than being copied here.

[Run and recover](runbook.md) · [Project workflow](project-management.md) ·
[Research basis](research.md) · [Environment history](environment.md)
