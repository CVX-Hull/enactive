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
player sub-agent owns planning, memory use and typed semantic requests within a
finite mission. The lead owns source integration and acceptance. The live service
uses one MissionRuntime. Owned windowed launch/untouched-menu exit passed a bounded
native retest with the first failure retained. Character creation/save/reload, quiescent retained-memory handoff, deliberate
readmission and normal finish now compose in source tests. Native character
lifecycle passed a scoped engineering qualification; independent normal-game
acceptance remains pending. Passive waypoint/planner components remain offline study tools.
Selected item/count/inspection and bounded activity observations now compose in
source. Activity interruption, exact answers and a separate charged Resume also
compose in source. Selected delivery reconciliation and separate normal-play
readmission also compose in source; native lifecycle/selector/activity/recovery
qualification remains distinct from independent play.
The observer now exposes readable historical memory and cumulative charged
admissions separately from requests, live activity and old results. These counts
do not measure model usage or prove greater gameplay efficiency. Its
[synthetic UI inspection](acceptance/2026-10-20-mission-observer.md) is separate from
the pending independent native mission.
Unknown-input custody and available late acknowledgements are now retained before
Observe can overwrite them. Typed proof can resolve that retained uncertainty
without changing the original charged/unknown delivery receipt. A separate charged
Resume and bounded continuation share the original root limits; user Pause revokes
eligibility. Missing proof stays stopped. These are source checks, not native
recovery or independent-player acceptance.

The latest [native007 qualification](acceptance/2026-10-20-native-lifecycle-qualified.md)
normally created Rowan, verified visible identity/stock Claims, counted drop/pickup,
a genuinely observed two-step return and a one-minute native wait/poll. Normal
save, new-child exact reload and final normal save/quit/stopped Finish passed.
Independent player/successor play and meaningful supplies/shelter remain unqualified.
[Native006](acceptance/2026-10-20-native-character-lifecycle.md) and earlier reports
retain their failures, unknown ACKs and exceptional cleanup.

The [first actual independent attempt](acceptance/2026-10-20-independent-mission-first-attempt.md)
failed before world confirmation: the player paraphrased the exact question and
included its adjacent legend. No Yes was dispatched; the stopped attempt retains
70 returned inputs and its exceptional setup cleanup. A separate actual spectator
Pause test revoked a live phase/lease and rejected stale input. Neither accepts
the independent mission. The source correction preserves an original phase only
for a local malformed-question rejection; a new corrected request must still pass
fresh evidence and all original authority/budget checks.

Current movement uses strictly known non-HOSTILE evidence. Inventory projection
omits only the engine's non-selecting cosmetic summary. Reload follows the actual
world→character-list transition and checks the unique enabled selected admitted
character before dispatch. A narrow Resume-only create/load abort exists in source;
general setup cancellation remains unsupported and unqualified.

Active observer polling now schedules250ms after each completed status response;
actual presentation latency still needs native/browser measurement. Fast ordinary
input samples do not measure player/model latency or accept independent play.
Routine play should compose guarded skills without a model or approval per key;
latency must be assessed at the whole-skill and displayed-frame boundaries too.
[Latency budgets](evaluation.md#latency-budgets-for-interactive-play) separate native
input, whole skills, model/tool delay, observer decode and loading.

The [seven-day functional campaign](acceptance/2026-10-19-seven-day-survival.md)
records the same normally created Ned Meyers / Belgium, ordinary supplies and
water treatment, shelter/rest, midpoint save/restart/exact reload, a genuine
player replacement and final normal shutdown. It reached168h02m54s, healthy and
Comfortable with displayed needs clear. The owned runtime is closed; future play
needs a new explicit admission.
This is one supervised development campaign under revised finite admissions;
earlier failures and uncertain acknowledgments remain. It establishes neither a
general autonomous survival policy nor a controlled model-performance result.

[#71](https://github.com/CVX-Hull/enactive/issues/71) owns evidence/memory readiness,
[#40](https://github.com/CVX-Hull/enactive/issues/40) outcome monitoring and
[#75](https://github.com/CVX-Hull/enactive/issues/75) workflow/control improvements.
The [work map](work.md) links current priorities and the retained campaign lineage.
[Operator permissions](operator-permissions.md) distinguishes tested literal CLI
access from rule activation and actor instructions from security isolation.

The [project goal](goal.md) records the original MVP and seven-day campaign
requirements. The [MVP completion audit](acceptance/2026-10-17-completion.md) maps
the original scope to implemented outcomes, independent review and dated gameplay
evidence; the later campaign has its own evidence above.
Direction and constraints live in the [charter](charter.md). This page summarizes
current behavior; detailed promises live in [architecture](architecture.md).

Changes migrate the system as a whole. We maintain one current version of each
contract and remove old paths, including in tools and stored metadata. Unsupported
state stops with evidence preserved until an explicit offline migration is complete.
[S-MIGRATION](engineering.md#s-migration-one-current-contract-coordinated-migration)
defines the rule and its enforcement.

## How it works

Current system context: **who decides, what you see, and where you retain control**.

![One designated player uses memory and semantic skills through the mission writer; the user retains Pause.](diagrams/player.svg)

Boxes show responsibilities, not separate model tiers. The player interprets
visible evidence and requests semantic operations. The mission writer accounts
for their original limits and checks live authority through the controller and
native bridge. Historical memory supports decisions but cannot authorize input.
The lead reviews engineering and admission; it is not the deciding player's
ordinary gameplay fallback. Owned lifecycle and actual fresh-context continuity
remain acceptance gates. [Editable diagram](diagrams/player.mmd),
[actor contract](protocol.md#designated-campaign-operator).

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
| Guarded short walks | Limited: cardinal directions, at most eight steps, conservative terrain and hostile/unknown creature stops | [Current contract](protocol.md#closed-loop-play-and-observations) |
| Planner round trips | One real three-tile comparison used three individual decisions versus one guarded request, retaining per-step checks; not a general speed or safety result | [Timing trial](acceptance/2026-10-17-completion.md#fresh-real-game-timing-probe) |
| Input authority and takeover | The accepted native-v3 baseline distinguishes ordinary play, menus, activity polls and debug prompts; revoked tokens and old worlds are rejected. Already-committed actions and activities cannot be undone by Pause | [Recovery acceptance](acceptance/2026-10-17-recovery-memory.md) |
| Retained gameplay evidence and memory | First-campaign traces and reviewed source underpin the new memory/navigation components. Wire4 menu preflight is exercised; native character lifecycle passed a scoped qualification; independent memory continuity remains pending | [Component probe](acceptance/2026-10-20-native-presentation.md), [current evidence contract](protocol.md#passive-gameplay-records-and-evidence) |
| Mission skill composition | Source integration shares navigation, native menu focus, interpreted controls and bounded text entry through one writer; ordinary prompts preserve original limits. One typed ingress and cached historical memory observer are connected; native lifecycle passed within engineering scope; independent mission acceptance remains pending | [Architecture](architecture.md), [mission design](design/player-owned-mission.md#integrated-runtime-and-admission-gate) |
| Passive movement skills | One proposed step at a time with cumulative route history; version4 permits strictly known non-HOSTILE evidence and separates reached-target verification from another step | [Skill contract](protocol.md#passive-bounded-movement-skills) |
| Mission input ownership | Nonterminal mission owns HTTP observation/input; exact controller lease gates dispatch; Pause remains available, with disk-stall limits | [Ownership contract](protocol.md#controller-run-ownership) |
| Passive waypoint supervision | Retained offline library and historical probes; no live task endpoint | [Supervisor contract](protocol.md#passive-waypoint-supervision) |
| Passive planner handoff | Candidate-only study component; current mission player chooses typed operations and interprets outcomes; chat usage remains unmeasured | [Planner contract](protocol.md#bounded-injected-planner) |
| Dedicated gameplay operator | Bounded ordinary campaign play with lead admission, corrections and terminal handoffs; no general survival guarantee | [Campaign evidence](acceptance/2026-10-19-seven-day-survival.md) |
| Evaluation records | Passive versioned outcome/cost recorder and offline summaries; external planning and future adapters are not automatically measured | [Evaluation guide](evaluation.md) |
| Unattended survival service | Not implemented; an active Codex player remains the planner | [Current scope](architecture.md#scope-and-responsibilities) |
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
remaining step and the actual return direction still require a visible,
furniture-free allowlisted neighbor. Creature occupancy is not established;
public `walk` remains conservative after each step.
[Waypoint readiness](changes/014-waypoint-readiness.md) records this decision and
the gates remaining before a comparative experiment. Its
[acceptance](acceptance/2026-10-18-waypoint-readiness.md) records real completion,
intermediate-obstacle stopping and Pause/continuation, including failures.

## Current direction and decisions

The original MVP and campaign are scoped milestones, with dated evidence and
limits. [Work](work.md) links accepted outcomes, failures and future decisions.
The campaign-driven [improvement workflow](project-management.md#campaign-driven-improvement)
routes observed pain points to owned work and later verification. It is manual
engineering; continuous policy learning remains unimplemented.

The next planned outcome is [player-owned campaigns (#136)](https://github.com/CVX-Hull/enactive/issues/136):
the player handles planning, campaign memory, semantic skills, routine recovery
and normal lifecycle while the user and engineering lead observe. [Design #137](https://github.com/CVX-Hull/enactive/issues/137)
and the bounded trace/label pilot #71 prepare an integrated supply-and-shelter
mission, then a fresh seven-day assessment. This is a delivery roadmap, not a
change to current runtime authority. An optional read-only curator and broader
efficacy studies remain separate candidates; [work](work.md) links their owners.
The [architecture assessment](research-memory-architecture.md) explains what to keep,
what needs to change and which recent memory results transfer to this project.

The next memory and [monitoring design](design/outcome-monitoring.md) must use
actual trajectories while distinguishing observations, fallible judgments and
unknowns. The [representation study](research-memory-representations.md) and
[monitoring review](research-outcome-monitoring.md) provide research, not gameplay
proof. Model-tier comparisons retain explicit data and measurement gates; no paid
provider is configured. Prefer existing native activities, Git and GitHub over new
simulators, history systems or trackers without a demonstrated gap.

No platform migration or hosted service is proposed. Revisit choices when measured
capability or maintenance cost justifies it; [ADRs](decisions/002-local-contract.md)
record alternatives and reversal triggers. Research review remains October24,2026;
control maintenance keeps its recorded dates and earlier event triggers.

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
