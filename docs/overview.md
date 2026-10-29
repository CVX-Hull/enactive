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

A designated model in the generic Pi gameplay host chooses plans, interprets
visible scenes and uses memory. One local mission writer executes its requests through the native game.
The engineering lead maintains the project and verifies outcomes; routine play
must not depend on lead tactics, keys or memory curation. This is not yet an
accepted unattended seven-day survival service.

The [generic gameplay host](components/player-interface.md) is mandatory and uses
pinned Pi core/MCP libraries with explicit tools, context, provider route and
timestamped events. The campaign driver has one execution path; choosing a model
is a separate decision. Engineering Codex owns development and verification.
Current evidence includes bounded
[organic learning and fresh corrected-program application](acceptance/2026-10-28-organic-play.md)
with useful food acquisition and normal Save/owned exit/Finish. Broad model quality,
apparent useful cadence and independent seven-day survival remain unqualified.
The earlier [configuration pilot](acceptance/2026-10-25-pi-configuration-pilot.md)
retains its failures; a failed model configuration does not cancel the required
host migration.

Development prioritizes authentic useful gameplay as the main behavioral feedback
loop. Players pursue coherent objectives; learning and reuse must emerge from
actual consequences. Focused offline checks support prompt returns to play, while
consolidated acceptance retains independent review and protected validation.
Approved API spending serves revealing play; apparent useful progress, quality
and total engineering burden guide decisions. The
[workflow](workflows/development.md#gameplay-as-the-primary-feedback-loop) owns the
decision rules and the distinction between estimates, invoices and reservations.

Bounded independent play has demonstrated supplies/travel, current procedure
revision and useful application of an exact correction by a registered fresh
successor. The [latest evidence](acceptance/2026-10-28-organic-play.md) verifies
three additional rations from that successor's generated selection/confirmation.
Its routine also selects packaging; broader applicability, final quantity/Work
reconciliation and useful cadence remain open. The [evidence index](work.md) links
other decisive results and retained failures; GitHub owns current execution.
Source repairs never retrospectively qualify failed runs. This remains short of
an accepted independent seven-day campaign.

The [registered lifecycle](components/mission-execution.md#lifecycle-and-change-review)
can keep an initial post-Load menu provisional. Explicit bounded dismissal must
reach actual normal play before identity inspection/adoption; a menu or reconciled
unknown input alone grants no ordinary gameplay authority. This is a narrow
CDDA integration path, not general cleanup of unadopted sessions.

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

[Explicit offline advisory export](acceptance/2026-10-27-historical-advisory-import.md)
preserves selected older routine lineage and original images as historical data.
Current retrieval and same-family revision plumbing are qualified with an offline
Pi/MCP fixture. Old code cannot execute as a current routine; useful player
application and apparent cadence remain separate requirements.

The background adviser reads recorded trajectories and proposes fallible advice
without pausing ordinary player reasoning. Software links selected procedures,
actions and results; the player decides applicability and adoption. Historical
facts, procedures and proposals retain their sources and limitations. Software
fills canonical procedure metadata and can submit a player-selected background
candidate without copying its record. The [offline execution repair](acceptance/2026-10-24-execution-first-offline.md)
reduces measured local overhead; the complete player's apparent responsiveness
and independent campaign remain separate acceptance questions.

[Editable diagram](diagrams/player.mmd) · [Architecture](architecture.md) ·
[Player contract](contracts/mission-admission.md#designated-campaign-operator)

## What works and what the evidence means

| Capability | Demonstrated scope and practical limit |
| --- | --- |
| Graphical play and user control | Actual native Tiles frames and browser spectator; Pause/takeover qualifications are scoped in the [architecture](architecture.md#action-and-recovery-views) and dated reports. |
| Useful skill composition | [Independent mission024](acceptance/2026-10-21-independent-supply-shelter.md) combines supplies/care, purposeful navigation/replanning, shelter/rest, memory correction, successor continuity and normal lifecycle. This is a bounded mission. |
| Organic ordinary interaction | [Learning006](acceptance/2026-10-22-discovery-learning-sixth-attempt.md) and [local-refusal001](acceptance/2026-10-22-native-local-refusal.md) exercise ordinary discovery/refusal/cancellation. Recent [Luna013](acceptance/2026-10-23-luna-responsiveness-thirteenth-attempt.md) independently loads/adopts identity, approaches a locker, picks up a ration and ends normally. Wider game-family behavior and full independent continuation remain unqualified. |
| Procedure memory and background advice | [Organic027](acceptance/2026-10-28-organic-play.md) verifies current parent/correction and exact fresh executable food acquisition with normal ending. Its packaging selection and quantity/Work limits remain. [Learning009](acceptance/2026-10-23-discovery-learning-ninth-attempt.md) retains earlier short movement/advice evidence. Broader generalization, causal learning benefit and useful cadence remain unqualified. |
| Save, reload and ending | [Capture001](acceptance/2026-10-22-native-capture-preconditions.md) qualifies ordinary input and normal same-character save/reload/ending on the rebuilt boundary; actual PNG drift remains unexercised there. [Fresh008](acceptance/2026-10-22-independent-seven-day-eighth-attempt.md) retains the motivating failure. [Native001](acceptance/2026-10-22-native-save-refresh.md) also qualifies one unit-geometry click; non-unit/wider mouse remains unqualified. |
| Seven-day survival | The [first campaign](acceptance/2026-10-19-seven-day-survival.md) completed under supervision. The fresh independent outcome remains unaccepted; [#145](https://github.com/CVX-Hull/enactive/issues/145) owns follow-through. |
| Watchable stopped history | The [local-refusal001 report](acceptance/2026-10-22-native-local-refusal.md) records actual STOPPED/HISTORY/DISCONNECTED presentation, no current mission decision and a timeout diagnostic explicitly labelled historical. |
| Latency | Current play speed is unacceptable. [Real endpoint comparison](acceptance/2026-10-28-endpoint-gameplay.md) observes faster serving, bounded gains and normal endings, alongside failed routines and shallow progress. Earlier [Luna013](acceptance/2026-10-23-luna-responsiveness-thirteenth-attempt.md) advances two game seconds in596wall seconds. API/DOM timings do not qualify useful cadence. [Evaluation](evaluation.md#latency-budgets-for-interactive-play) owns definitions; [#164](https://github.com/CVX-Hull/enactive/issues/164) owns delivery. |

The [player interface](components/player-interface.md) and
[current protocol](protocol.md) separate
semantic judgment from mechanical SDK identities, staging, original collection
and progressive detail. The player should decide intent, inspect relevant evidence
and evaluate outcomes; software handles canonical metadata and provenance.

Earlier [useful-bootstrap failures](acceptance/2026-10-24-useful-bootstrap-trials.md)
do not establish a memory-architecture conclusion. The latest organic case now
combines useful corrected-executable fresh succession with normal ending;
whole-player cadence remains unqualified before another full campaign. GitHub owns
the next selected configuration and finite assessment.

The [executable-routine substrate](components/memory-learning.md) lets
the player author observation-conditioned JavaScript procedures over ordinary
inputs through the same writer. Host bounds and automatic action/result joins
remain outside generated control flow. Its current view supplies structured
visible state, without pixels; image-only conditions return to the player.
[Literal inventory markers](acceptance/2026-10-27-rendered-markers.md) are
qualified on one native mark/unmark/cancel sequence with normal ending, separately
from row labels and focus. This representation check establishes no useful
player-authored program application or cadence improvement.
Novel interfaces must remain discoverable through ordinary input, rather than
requiring a hand-written semantic handler. Bounded organic learning is demonstrated;
useful apparent cadence and the complete fresh campaign remain unqualified.

[Work](work.md#current-integrated-checkpoint) links the decisive successful and
failed evidence. Dated reports own attempt history, costs and interventions;
this overview describes the product and its demonstrated limits.

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

We plan [iterations around a useful outcome or explicit learning decision](workflows/work-items.md#outcome-focused-iterations),
including its relevant review, validation and completion work. Small integrated
changes and focused feedback build toward that outcome. The [development-first workflow](workflows/development.md#development-first-delivery)
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
One explicitly approved bounded DeepInfra comparison is closed with a negative
selection decision; its project-local configuration is not a default gameplay service.

The next engineering direction is to make faster, less flagship players effective
through sufficient current context, ergonomic tools and useful local execution.
The [context and prompting review](research-context-engineering.md) informs that
work. Model, prompt and context changes must earn their place through complete
useful outcomes and apparent latency; no particular smaller model, extra model
tier or new context policy is qualified by this direction alone.

Prefer existing engine/platform capabilities and maintained tools when they advance
the overall objective. Useful long-term accelerators can justify investment;
choices and reversal conditions belong in [ADRs](decisions/002-local-contract.md).
We keep one current contract and migrate all affected callers/state together under
[S-MIGRATION](standards/migration.md#s-migration-one-current-contract-coordinated-migration).

## How you stay in control of the project

Use this page for capabilities and limits, [GitHub Project](https://github.com/users/CVX-Hull/projects/2)
for live work and [work](work.md) for evidence navigation. Significant proposals
explain user consequences, alternatives, maintenance cost and open decisions;
implementation detail stays behind links. Routine work continues under the agreed
constraints, while changes to those constraints require your input.

For a first session, use the [spectator walkthrough](walkthrough.md). For technical
review, follow the [documentation map](documentation.md), [architecture](architecture.md), [standards](engineering.md) and the
[maintenance table](controls.md#maintenance). Their owners and review triggers
support upkeep; a recent date is not proof of accuracy. Historical MVP and migration
records remain in [acceptance](acceptance/), rather than being copied here.

[Run and recover](runbook.md) · [Project workflow](project-management.md) ·
[Research basis](research.md) · [Environment history](environment.md)
