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
| Current seven-day path | [020](acceptance/2026-10-19-midpoint-survival.md) accepted days1–3, midpoint restart/reload and player replacement. [024](acceptance/2026-10-19-four-day-survival.md) accepted day four. [025](acceptance/2026-10-19-first-clean-water.md) verified the first250mL clean-water output, not remaining coverage. Days5–7 remain incomplete. [#103](https://github.com/CVX-Hull/enactive/issues/103) is accepted; [#104](https://github.com/CVX-Hull/enactive/issues/104) owns day five and [#129](https://github.com/CVX-Hull/enactive/issues/129) resources/forecast. |
| Full closeout | Same-character daily evidence, normal midpoint save/restart/reload and player replacement, final normal shutdown, independent complete-campaign review, protected publication/CI, owned cleanup and current Project. #82 stays open until all are proved. |

[026–028](acceptance/2026-10-19-water-coverage.md) collected3Lraw and stored one1.5L
clean batch. A further six-portion craft stopped twice when heat disappeared; it
remains SAME59%wielded, no second output. Fresh stock3Lclean/500mLfree raw/12rations;
craft-bound water is not usable stock. Latest normal5562641 is healthy/Comfortable;
one owned game/controller paused, actual slots null/all tools terminal/noqueue.
Residual stick+ashes remain on old unlit[9,-13]; marked source[7,-13]empty. Days1–4
accepted; days5–7 and remaining coverage incomplete.

[050](changes/050-curtain-fuel-and-retained-craft.md) now proposes ordinary CUT salvage
of that residual stick into small fuel, existing marked-source feeding, ONE ignition
and SAMEcraft continuation:≤65inputs/25minutes, actual yield≥5 gate. User-delegated
prospective100input extension keeps time endpoints/original clocks/costs/reserve.
No new curtain/search/bash/newrecipe/replacementingredients/automatic renewal.
Actual tool/target/yield, heat, capacity and complete-route fit remain gates.

A successor needs source/review/common checks/clean checkpoint, fresh actual
preflight, explicit actor assignment and credible complete-route fit. The
[operator contract](protocol.md#designated-campaign-operator) governs handoff,
unknown effects and bounded recovery. [046](changes/046-replan-known-nondelivery.md)
records confirmed non-delivery versus game refusal; [047](changes/047-quality-data-continuation.md)
and [048](changes/048-water-coverage-budget.md) preserve earlier allocation decisions.
#129 owns resources/forecast and #75 control-fit findings. GitHub owns current
execution stage, estimates and dependencies; historical reports grant no authority.
Consolidated protected publication is a separate verification step.

## Execution ownership

The lead owns design, finite admission, the shared runtime/save/port, lifecycle, escalation, finding adjudication and final verification. A designated general-purpose campaign operator may own ordinary input under the [bounded actor/handoff contract](protocol.md#designated-campaign-operator). The leased waypoint planner remains candidate-only. A recorded objective or a running chat is not an execution lease.

One actor owns input at a time. Handoff requires Pause, completion of every tool handle, a referenced checkpoint, no queued/scheduled input and empty live slots. The next actor receives explicit bounded authority, fresh interpreted evidence and deliberate Resume. Status alone cannot prove an empty external tool queue. Read-only source/evidence review can run alongside gameplay; competing executors and changes to the admitted runtime cannot.

For implementation, follow [S-AGENT](engineering.md#s-agent-accountable-agent-assisted-work): bounded briefs, named roles, clean-context workers/reviewers, separate worktrees with disjoint ownership, one integrator and serialized native acceptance. The lead verifies results against files and actual evidence rather than treating agent prose as proof.

## Campaign findings and future work

Use the [campaign-driven improvement workflow](project-management.md#campaign-driven-improvement): observation → evidence-backed finding → owned disposition → bounded work or explicit deferral → verification. Useful failed investigations can improve the project without becoming survival success. One successful campaign does not establish causal learning or general reliability.

| Area | Backlog owner and revisit rule |
| --- | --- |
| Runtime autonomy, continuity and current gameplay gaps | #82 and its current daily child; implement only demonstrated blocking capabilities. Tests, native build and actual graphical gameplay stay separate evidence lanes. |
| Workflow, documentation and control maintenance | [#75](https://github.com/CVX-Hull/enactive/issues/75); reconcile triggered gaps and burden. Keep current contracts concise, link historical evidence, and do not renew due dates through grooming. |
| Memory | [#70/#71](https://github.com/CVX-Hull/enactive/issues/70); inspect actual player-visible traces before choosing persistent architecture. Actual campaign handoff is separate from a general memory benchmark. |
| Model tiering and comparison | [#16/#24/#25](https://github.com/CVX-Hull/enactive/issues/16), with #72/#73/#74 as explicit measurement gates. More tiers or paid providers need a measured benefit and authorized configuration. |
| Outcome monitoring | [#40/#42–44](https://github.com/CVX-Hull/enactive/issues/40); campaign findings can justify bounded capabilities. Active human/model interpretation does not claim this framework is implemented. |
| Research currency | [#26](https://github.com/CVX-Hull/enactive/issues/26); retain the October 24, 2026 active-work/event review trigger unless explicitly changed through the workflow. |

Native regression automation #9, broader host/browser delivery #11, tooling #12, advanced learning #27 and tutorial repair #47 retain their recorded revisit triggers. They are not automatic campaign prerequisites. Prefer existing engine activities, CLI/control tools, Git and GitHub capabilities over new infrastructure. No new paid API, global installation or generic world-model/training system follows solely from a difficult run.

## Retained evidence

The [grooming record](acceptance/2026-10-18-survival-grooming.md) and [earlier backlog checkpoint](acceptance/2026-10-18-backlog-grooming.md) preserve dated decisions; GitHub owns later work. The [migration record](acceptance/2026-10-18-enactive-migration.md) explains canonical Enactive references and historical PR archives.

Earlier deciding attempts remain in the [first campaign stop](acceptance/2026-10-18-seven-day-stop.md), [continuation stop](acceptance/2026-10-18-seven-day-continuation-stop.md), [integrated partial day](acceptance/2026-10-18-integrated-day1.md), [resource feasibility](acceptance/2026-10-18-resource-feasibility.md) and [daylight practice](acceptance/2026-10-18-daylight-practice.md) reports. The [walk reassessment](acceptance/2026-10-18-walk-reassessment.md), [ordinary menu](acceptance/2026-10-18-ordinary-menus.md), [activity distraction](acceptance/2026-10-18-activity-distraction.md) and [body-status](acceptance/2026-10-19-body-status.md) reports record separate capability repairs and their actual coverage. Those repairs do not by themselves accept daily survival.

Keep detailed receipt/cost narratives in the dated reports and reconcile outcomes at publication. Git retains prior page versions; no parallel history system is needed. A new functional study cannot relabel an expired study as successful.
