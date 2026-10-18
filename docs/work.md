---
owner: lead
review_trigger: Work tracker location, authority, campaign path or workflow changes
status: active
---

# Work and decisions

[Public Project](https://github.com/users/CVX-Hull/projects/2) ·
[Issues](https://github.com/CVX-Hull/enactive/issues) ·
[Pull requests](https://github.com/CVX-Hull/enactive/pulls) ·
[Milestones](https://github.com/CVX-Hull/enactive/milestones)

GitHub Issues own scope, acceptance, dependencies, estimates, owners and blockers.
Project Status owns execution stage; Horizon owns Now/Next/Later. This page explains
the delivery path, not a second live backlog. The [overview](overview.md) explains
current capability; [project management](project-management.md) owns the workflow.

## Path to seven-day survival

The [campaign outcome #10](https://github.com/CVX-Hull/enactive/issues/10) means a
normally created fresh character alive after seven elapsed in-game days, with
maintained needs, shelter/rest, meaningful supply/travel decisions, ordinary
save/resume, understandable progress and user Pause/control. The user must not
have to supply keys or routine recovery; required rescue fails autonomy readiness.
Failed, dead, partial
or unknown attempts remain evidence and do not count as successful completion.
The campaign milestone has no committed delivery date.

| Gate | Evidence needed to proceed | Tracked outcome |
| --- | --- | --- |
| Useful survival pilot and its first review | [Pilot001](acceptance/2026-10-18-survival-pilot.md) stopped on an unknown world-selection acknowledgment before spawning; retained findings and cleanup are gap evidence, not survival success | [#78 pilot](https://github.com/CVX-Hull/enactive/issues/78), then [#83 first review](https://github.com/CVX-Hull/enactive/issues/83) |
| Continuity and first-day rehearsal | [Rehearsal001](acceptance/2026-10-18-first-day-rehearsal.md) failed autonomy. The [direction probe](acceptance/2026-10-18-native-direction-menu.md) verified same-character reload and actual pickup selection/cancel without user keys; the [later same-character run](acceptance/2026-10-18-first-day-completion.md) reached24h14m29s without user rescue, with qualified needs/rest evidence and a retained cleanup deadline deviation | [#91 recovery](https://github.com/CVX-Hull/enactive/issues/91), [#79 continuity](https://github.com/CVX-Hull/enactive/issues/79) and [#80 first day](https://github.com/CVX-Hull/enactive/issues/80); shared execution is serialized |
| Executable seven-day readiness | Adjudicated #79/#80/#83 evidence and exceptions, actual capability gaps resolved, measured throughput, finite total/segment/attempt limits, frozen scenario/candidate and independent outcome review | [#81 readiness](https://github.com/CVX-Hull/enactive/issues/81) |
| Seven-day campaign | Bounded owned segments of the same fresh character, real visible calendar/needs/identity evidence, save/restart/handoff and reviewed endpoint | [#82 execution](https://github.com/CVX-Hull/enactive/issues/82), split and estimated before Ready |

The first integrated pilot/review round used **18 charged inputs**, including four
cleanup inputs, and 229.232 seconds through the final receipt capture. It stopped
before a character spawned; supplies and survival were unexercised. The unknown
world-confirmation and final Quit receipts remain unknown, even though fresh
observations supported ordinary menu cancellation and the native process exited with code 0.
The [shared finding table](acceptance/2026-10-18-survival-pilot.md#shared-finding-and-disposition-review)
routes the concrete gaps without creating a new framework.

The [#79/#80 rehearsal](changes/015-campaign-continuity-rehearsal.md) has now stopped
after **57 charged inputs** (48 play/nine cleanup, including one requested native
Escape supplied by the user), 727.918 seconds through closeout and only 32 elapsed
game seconds. Ramiro Winston/Sneedville was normally saved; the later direction
probe verified its reload. A real advisory player handoff retained facts/budget;
it did not establish full continuity or first-day success.

The [reuse-first recovery preflight](changes/016-autonomous-native-recovery.md)
stopped before admission when desktop automation reported an access/lock failure;
no user unlock was requested and no probe input charged. Its replacement
[direction-menu brief](changes/017-native-direction-menu.md) added narrow engine
query coverage with unchanged native keybindings. Its
[real probe](acceptance/2026-10-18-native-direction-menu.md) used14probe+4cleanup
inputs/218.939seconds, with zero game-time advance and no user keys. Same-character
reload, actual Escape, adjacent and current-tile selection worked; load/save/final
Quit receipts stay unknown. This is no first-day success or renewed survival
allowance. Keep failed attempts, the separate menu operation and unadmitted
preflight visible. The [next first-day brief](changes/018-first-day-rehearsal.md)
admitted one fresh ordinary attempt preserving the assisted character.
Its [stopped prefix](acceptance/2026-10-18-first-day-rehearsal-002.md) reached
22h14m25s with meals/water, medical excursion/return, overnight wake, handoff and
normal application restart. An unsupported wheezing prompt stopped investigation;
existing native CUA canceled it for normal cleanup with no human input.208charges
include203play+5cleanup(one native UI); six lifecycle unknowns remain. No full-day
success at that stop. The [same-character continuation](acceptance/2026-10-18-first-day-completion.md),
prospectively admitted after protectedPR95 inside the original500/180min/26h
absolute envelope, then reached **24h14m29s alive**,227charges=218play+9cleanup,
two agent-native CUA responses and zero human rescue. Endpoint Thirsty, unknown
exact sleep duration and nine lifecycle ACKs remain explicit. Two final cleanup
requests incorrectly used15s instead of ordinary5s deadlines; acceptance records
the deviation, no retroactive brief amendment. Original741 and continuation200
artifact hashes and ledger were independently checked. The lead owns functional
acceptance with these qualifications. Original estimates remain historical;
measured elapsed time includes reasoning/review/publication, not just game runtime.

Next #81 freezes the fresh deciding scenario, candidate, practical supply/rest
capabilities, finite whole-run/segment/attempt limits and independent outcome
review. It must consume the deadline-control finding, actual throughput and the
[permission/player audit](operator-permissions.md): narrowly matched CLI rules are
prepared and policy-tested, activation is unverified; dedicated direct player
execution needs an explicit ownership design and acceptance, not silent expansion
of the current advisory role. #82 stays gated until that decision. No new generic
monitor, memory database or paid API is required by the rehearsal evidence.

Pilot001's 150-input/45-minute/six-game-hour ceilings remain historical fixed limits,
not a renewable allowance. Every later attempt needs a prospective finite brief
and retained cumulative history. Unknown delivery is charged and never replayed
blindly. A useful failed investigation/review cannot establish first-day or seven-day
survival. Readiness and execution remain gated on actual evidence.

The active player interprets fresh graphical evidence and chooses ordinary menu,
key or action inputs. The harness's automated task is still bounded waypoint-and-return;
there is no general survival planner, durable campaign context or mechanically
enforced campaign-wide ledger. The pilot determines the smallest real gaps before
implementation. [Protocol](protocol.md) owns current authority and uncertainty.
The next brief cannot turn a later scene into an old request's missing receipt.

## Allocation and parallel work

The lead owns admission, design, the only executor/game/save/port, finding
adjudication and final acceptance. One player may propose bounded choices; read-only
source/evidence reviews can run alongside it. No implementation worker is needed
just to start the pilot. After evidence freezes #79/#80 interfaces, at most two
workers may use separate worktrees and disjoint paths; one integrator and serialized
native acceptance remain. Shared runtime, save or cache work cannot be parallelized
by creating more source checkouts.

## Parallel questions and maintenance

- [Memory #70/#71](https://github.com/CVX-Hull/enactive/issues/70): #71 can inspect existing visible traces if review capacity permits. No persistent memory architecture or benchmark is a pilot prerequisite; actual campaign handoff belongs to #79.
- [Comparison/tiering #16/#24/#25](https://github.com/CVX-Hull/enactive/issues/16): #72/#73/#74 remain genuine #24 gates; #73's complete both-arm export also needs #72. Additional tiers, matched trials and runtime evaluation export are a separate lane; #73 is revisited on a demonstrated accounting/export need or comparison selection.
- [General monitoring #40/#42–44](https://github.com/CVX-Hull/enactive/issues/40): recurring campaign findings may justify bounded capabilities, but active player interpretation does not claim that framework is delivered.
- [Research review #26](https://github.com/CVX-Hull/enactive/issues/26): October 24, 2026 active-work/event trigger remains; grooming does not renew it.
- [Maintenance #75](https://github.com/CVX-Hull/enactive/issues/75): migration/CI events triggered scoped review. Current main CI passed after fixture hardening; the historical timeout cause is unproven and needs correlated evidence if repeated. This is visible review work, not an invented pilot dependency.

Conditional native automation #9, other-host/browser #11, broader tooling #12,
advanced learning #27 and tutorial repair #47 retain their existing revisit triggers.
No new paid provider, training, world model, background service or global setup is
selected. All actual campaign gaps enter the [review-to-backlog workflow](project-management.md#campaign-driven-improvement)
with an owner, disposition and appropriate acceptance; useful review is separate
from survival success and generalized learning claims.

## Decisions and dated evidence

The [survival pilot](acceptance/2026-10-18-survival-pilot.md) records the actual
stopped attempt, shared review and next-work routing. The earlier
[grooming checkpoint](acceptance/2026-10-18-survival-grooming.md) records the initial
open-item dispositions and graph/Project checks. GitHub owns subsequent changes.
The [migration record](acceptance/2026-10-18-enactive-migration.md)
explains canonical Enactive references and historical PR archives.

[Integrated player acceptance](acceptance/2026-10-18-integrated-player.md) and
[waypoint readiness](acceptance/2026-10-18-waypoint-readiness.md) are real bounded
native evidence, not fresh-character survival results. The [original MVP audit](acceptance/2026-10-17-completion.md)
and [earlier grooming checkpoint](acceptance/2026-10-18-backlog-grooming.md) remain
historical. The overview links deeper designs, studies and acceptance; historical
briefs do not override current contracts or live Project fields.
