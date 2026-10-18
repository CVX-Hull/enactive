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
save/resume, understandable progress and user Pause/control. Failed, dead, partial
or unknown attempts remain evidence and do not count as successful completion.
The campaign milestone has no committed delivery date.

| Gate | Evidence needed to proceed | Tracked outcome |
| --- | --- | --- |
| Useful survival pilot and its first review | [Pilot001](acceptance/2026-10-18-survival-pilot.md) stopped on an unknown world-selection acknowledgment before spawning; retained findings and cleanup are gap evidence, not survival success | [#78 pilot](https://github.com/CVX-Hull/enactive/issues/78), then [#83 first review](https://github.com/CVX-Hull/enactive/issues/83) |
| Continuity and first-day rehearsal | Context/accounting survives player replacement and normal restart; a real first-day needs/shelter/supply/travel/rest loop works | [#79 continuity](https://github.com/CVX-Hull/enactive/issues/79) and [#80 first day](https://github.com/CVX-Hull/enactive/issues/80); design may overlap after the pilot, shared execution is serialized |
| Executable seven-day readiness | Accepted #79/#80/#83, actual capability gaps resolved, measured throughput, finite total/segment/attempt limits, frozen scenario/candidate and independent outcome review | [#81 readiness](https://github.com/CVX-Hull/enactive/issues/81) |
| Seven-day campaign | Bounded owned segments of the same fresh character, real visible calendar/needs/identity evidence, save/restart/handoff and reviewed endpoint | [#82 execution](https://github.com/CVX-Hull/enactive/issues/82), split and estimated before Ready |

The first integrated pilot/review round used **18 charged inputs**, including four
cleanup inputs, and 229.232 seconds through the final receipt capture. It stopped
before a character spawned; supplies and survival were unexercised. The unknown
world-confirmation and final Quit receipts remain unknown, even though fresh
observations supported ordinary menu cancellation and the native process exited with code 0.
The [shared finding table](acceptance/2026-10-18-survival-pilot.md#shared-finding-and-disposition-review)
routes the concrete gaps without creating a new framework.

The next work combines **#79 continuity with #80 first-day preparation/rehearsal**.
Their [prospective brief](changes/015-campaign-continuity-rehearsal.md) starts with
existing advisory files/journals, explicit cumulative accounting, fresh player
handoff, and a declared lifecycle procedure. It proposes one bounded development
attempt; admission remains gated on exact source/configuration, limits and independent
review. It does not continue or renew pilot001. Original M/Low, 2–4 and M/Low, 3–5
focused-session estimates remain in Issues; menu-only evidence cannot calibrate
survival throughput or a calendar forecast.

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
