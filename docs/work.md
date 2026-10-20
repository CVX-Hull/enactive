---
owner: lead
review_trigger: Work tracker location, authority, campaign path or workflow changes
status: active
---

# Work and decisions

[Public Project](https://github.com/users/CVX-Hull/projects/2) · [Issues](https://github.com/CVX-Hull/enactive/issues) · [Pull requests](https://github.com/CVX-Hull/enactive/pulls)

GitHub Issues own work scope, acceptance, dependencies, estimates, owners and blockers. Project Status owns execution stage; Horizon owns Now/Next/Later. This page explains the delivery path and points to evidence. It does not duplicate the live backlog or serve as input authority. The [overview](overview.md) explains capability; [project management](project-management.md) explains how work is selected and reviewed.

## Campaign delivery path

[Outcome #10](https://github.com/CVX-Hull/enactive/issues/10) requires a normally created fresh character alive after seven elapsed game days, maintained essential needs, useful shelter/rest, meaningful supply/travel/threat decisions, normal save/restart, a real player handoff, a watchable graphical UI and user Pause/control. The user must not need to supply keys or rescue ordinary gameplay. Investigation completion, passing tests or a partial surviving character does not establish this outcome.

| Stage | Current evidence and authority |
| --- | --- |
| Survival pilot and findings | [Pilot report](acceptance/2026-10-18-survival-pilot.md) retains the stopped pre-spawn attempt and its dispositions; #78/#83 own acceptance. |
| Continuity and first-day rehearsal | [Qualified first-day result](acceptance/2026-10-18-first-day-completion.md) retains actual save/restart/handoff, needs and autonomy evidence plus its failures/unknowns; #79/#80 own acceptance. |
| Seven-day readiness | [Readiness report](acceptance/2026-10-18-seven-day-readiness.md) records the finite preparation gate and its limits; #81. Readiness does not guarantee campaign success. |
| Seven-day functional campaign | [Full report](acceptance/2026-10-19-seven-day-survival.md) owns accepted daily turns, same-character continuity, actual supplies/rest, corrections, costs and limits. All seven daily milestones and normal final runtime shutdown are accepted within their stated functional scope. Earlier closed attempts remain failures. |
| Closeout | Final normal Save/Quit and native/controller shutdown, independent complete-campaign review, protected candidate/main validation and owned branch cleanup are separate gates. Publication receipts and live status belong in #82/#10 and the PR. |

[Water evidence](acceptance/2026-10-19-water-coverage.md) preserves missing-tool and
crowbar-damage stops, declined storage advice, two heat interruptions and the
successful small-fuel continuation of the same craft. The two1.5L bulk outputs were
stored and later used for responsive care. This configuration is not a controlled
fuel-shape experiment or a guaranteed future supply policy.

[050](changes/050-curtain-fuel-and-retained-craft.md) is a closed historical
admission after completion, not continuing authority. [046](changes/046-replan-known-nondelivery.md)
and the [operator contract](protocol.md#designated-campaign-operator) retain the
handoff, unknown-effect and bounded-recovery rules. Future play requires a new
explicit finite objective, budget, current preflight and actor assignment. No old
allowance or running chat renews it.

The next planned outcome is [player-owned campaigns #136](https://github.com/CVX-Hull/enactive/issues/136)
in the [new milestone](https://github.com/CVX-Hull/enactive/milestone/6). [Design #137](https://github.com/CVX-Hull/enactive/issues/137)
and [#71](https://github.com/CVX-Hull/enactive/issues/71), bounded trace extraction
and label readiness, establish its accepted design/evidence basis. Semantic navigation
and interaction, durable campaign memory, outcome assessment/recovery, mission
ownership and observer visibility feed one [supply-and-shelter acceptance #144](https://github.com/CVX-Hull/enactive/issues/144),
then a [fresh seven-day assessment #145](https://github.com/CVX-Hull/enactive/issues/145)
with the engineering lead outside gameplay. Reviewed component readiness permits
shared native validation; the mission does not wait for component issue closure.
The current execution contract below remains in force until a reviewed migration.
The [proposed mission design](design/player-owned-mission.md) defines that migration
and bounded acceptance; the [trace pilot](acceptance/2026-10-19-memory-trace-pilot.md)
records actual source/interpretation limits. Neither page claims runtime delivery.

An [optional read-only curator #146](https://github.com/CVX-Hull/enactive/issues/146)
and broader memory/monitor/model efficacy studies remain separate candidates.
Use actual campaign failures, corrections and uncertainty before choosing memory
architecture or model comparisons. #75 owns finite workflow/control maintenance;
#40 retains broader monitoring scope. Research review remains October24,2026 and
control maintenance keeps January15,2027 and earlier event triggers. The public
Project owns changing estimates and Status/Horizon, not this evidence map.

## Execution ownership

The lead owns design, finite admission, the shared runtime/save/port, lifecycle, escalation, finding adjudication and final verification. A designated general-purpose campaign operator may own ordinary input under the [bounded actor/handoff contract](protocol.md#designated-campaign-operator). The leased waypoint planner remains candidate-only. A recorded objective or a running chat is not an execution lease.

One actor owns input at a time. Handoff requires Pause, completion of every tool handle, a referenced checkpoint, no queued/scheduled input and empty live slots. The next actor receives explicit bounded authority, fresh interpreted evidence and deliberate Resume. Status alone cannot prove an empty external tool queue. Read-only source/evidence review can run alongside gameplay; competing executors and changes to the admitted runtime cannot.

For implementation, follow [S-AGENT](engineering.md#s-agent-accountable-agent-assisted-work): bounded briefs, named roles, clean-context workers/reviewers, separate worktrees with disjoint ownership, one integrator and serialized native acceptance. The lead verifies results against files and actual evidence rather than treating agent prose as proof.

## Campaign findings and future work

Use the [campaign-driven improvement workflow](project-management.md#campaign-driven-improvement): observation → evidence-backed finding → owned disposition → bounded work or explicit deferral → verification. Useful failed investigations can improve the project without becoming survival success. One successful campaign does not establish causal learning or general reliability.

| Area | Backlog owner and revisit rule |
| --- | --- |
| Player autonomy and observer visibility | [#136](https://github.com/CVX-Hull/enactive/issues/136) owns the planned delivery and required children; #143 owns expanded player/memory/intervention visibility. #126 stays a narrow external-operator wording fix; #128 retains publication-stall recurrence/recovery triggers. Future campaigns need scoped admission and separate native evidence. |
| Workflow, documentation and control maintenance | [#75](https://github.com/CVX-Hull/enactive/issues/75); reconcile triggered gaps and burden. Keep current contracts concise, link historical evidence, and do not renew due dates through grooming. |
| Memory | [#140](https://github.com/CVX-Hull/enactive/issues/140) owns planned campaign continuity; [#70/#71](https://github.com/CVX-Hull/enactive/issues/70) retain research/label readiness. Inspect actual player-visible traces before choosing persistent architecture. Actual campaign handoff is separate from a general memory benchmark. |
| Model tiering and comparison | [#16/#24/#25](https://github.com/CVX-Hull/enactive/issues/16), with #72/#73/#74 as explicit measurement gates. More tiers or paid providers need a measured benefit and authorized configuration. |
| Outcome monitoring | [#141](https://github.com/CVX-Hull/enactive/issues/141) owns the first functional assessment/recovery slice, reusing the shared design; [#40/#42–44](https://github.com/CVX-Hull/enactive/issues/40) retain broader delivery/effectiveness scope. Active human/model interpretation does not claim this framework is implemented. |
| Research currency | [#26](https://github.com/CVX-Hull/enactive/issues/26); retain the October 24, 2026 active-work/event review trigger unless explicitly changed through the workflow. |

Native regression automation #9, broader host/browser delivery #11, tooling #12, advanced learning #27 and tutorial repair #47 retain their recorded revisit triggers. They are not automatic campaign prerequisites. Prefer existing engine activities, CLI/control tools, Git and GitHub capabilities over new infrastructure. No new paid API, global installation or generic world-model/training system follows solely from a difficult run.

## Retained evidence

The [grooming record](acceptance/2026-10-18-survival-grooming.md) and [earlier backlog checkpoint](acceptance/2026-10-18-backlog-grooming.md) preserve dated decisions; GitHub owns later work. The [migration record](acceptance/2026-10-18-enactive-migration.md) explains canonical Enactive references and historical PR archives.

Earlier deciding attempts remain in the [first campaign stop](acceptance/2026-10-18-seven-day-stop.md), [continuation stop](acceptance/2026-10-18-seven-day-continuation-stop.md), [integrated partial day](acceptance/2026-10-18-integrated-day1.md), [resource feasibility](acceptance/2026-10-18-resource-feasibility.md) and [daylight practice](acceptance/2026-10-18-daylight-practice.md) reports. The [walk reassessment](acceptance/2026-10-18-walk-reassessment.md), [ordinary menu](acceptance/2026-10-18-ordinary-menus.md), [activity distraction](acceptance/2026-10-18-activity-distraction.md) and [body-status](acceptance/2026-10-19-body-status.md) reports record separate capability repairs and their actual coverage. Those repairs do not by themselves accept daily survival.

Keep detailed receipt/cost narratives in the dated reports and reconcile outcomes at publication. Git retains prior page versions; no parallel history system is needed. A new functional study cannot relabel an expired study as successful.
