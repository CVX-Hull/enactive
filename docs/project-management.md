---
owner: lead
review_trigger: Workflow, ownership, forecasting, tooling or milestone policy changes
status: active
---

# Project management

The user owns product direction and constraints. The lead owns design, briefs,
integration, escalation and final verification under [S-AGENT](engineering.md#s-agent-accountable-agent-assisted-work).
This contract defines how work becomes a reviewable outcome. [Engineering](engineering.md)
owns mandatory standards; [research](research-engineering.md#project-management-basis--2026-10-17)
records external support and limits.

## Authority and review surfaces

The selected public repository is [CVX-Hull/enactive](https://github.com/CVX-Hull/enactive).
GitHub Issues and the [public Project](https://github.com/users/CVX-Hull/projects/2) own live priorities, stages, owners,
dependencies, estimates and blockers. Repository docs own durable purpose,
contracts, procedures, decisions and dated evidence. [Work](work.md) is the
navigation entry point; exceptions are issues linked to their affected standard.
[Enactive migration acceptance](acceptance/2026-10-18-enactive-migration.md) records
replacement configuration and enforcement probes; the original
[public-workflow acceptance](acceptance/2026-10-17-public-workflow.md) remains
historical. The [campaign path](work.md#campaign-delivery-path) links capability
gates to owned Issues; this contract alone does not prove current settings.

Use GitHub's issues, sub-issues, dependencies, milestones, pull requests, fields,
saved views and built-in workflows. No custom tracker or background scheduler.
The Project README links this contract, the overview and these three saved views:

| View | User question and contents |
| --- | --- |
| Direction | What outcome comes next and why? Group by Horizon; show milestone, priority, outcome, confidence and decision needed |
| Execution | What is moving? Board by Status; show owner, size, dependencies and linked pull request |
| Needs attention | What needs intervention? Filter blocked, decision-needed and risk labels; lead flags aging Review/Validation work during checkpoint triage |

At a meaningful checkpoint, update the Project with outcomes achieved, next
outcome, risks/blockers, decisions needed and evidence links. Give consequences
in plain language; implementation detail belongs behind links. Routine authorized
work continues; changed user constraints or substantial commitments need user input.

## Work items and flow

During triage, the lead adds selected issues to the linked Project and assigns
Backlog, owner, Horizon, Priority, Size and Confidence. A newly opened issue is
not automatically Ready; unset planning fields are resolved before commitment.

An issue represents one independently reviewable outcome. A milestone groups
issues into a useful capability or learning result with explicit acceptance and
limitations; a batch of files or number of agent sessions is not a milestone.

Choose delivery rounds around a complete user-visible behavior when the interfaces
and acceptance are understood. Related bounded issues can share one integrated PR
and native acceptance session; an internal adapter or handoff need not become a
separate delivery round. Split implementation ownership for safe parallel work,
while retaining the shared end-to-end acceptance. Keep a smaller round when an
unresolved experiment or interface decision would otherwise create speculative
work. The lead checks this tradeoff at Ready review under C-REVIEW; file counts or
agent count do not enforce it. Large aggregate issues still require bounded children
before execution, and the two-writer/shared-runtime limits below remain unchanged.

| Status | Entry/exit policy |
| --- | --- |
| Backlog | Candidate with a problem and intended outcome; no execution commitment |
| Ready | Scope, owner, interfaces/dependencies, acceptance and required validation lanes are clear; needed decisions resolved |
| In progress | Capacity available and owner starts work against the brief; record start date |
| Review | Cohesive diff and executed checks available; independent review appropriate to risk is requested |
| Validation | Review findings resolved; lead integrates and checks the exact candidate, including required native/graphical lanes |
| Done | Lead verifies acceptance, evidence and documentation; record finish date and close as completed |

Blocked is a flag plus reason, owner and next action/revisit condition; keep the
current Status so the stalled stage remains visible. Use issue dependencies for
blocked-by relationships. A failed check stays recorded. Rework returns to the
appropriate stage with a reason. Closed duplicates/cancellations record disposition
and any replacement, remain outside Done and are excluded from delivery counts.
Do not use automatic close/merge-to-Done rules: a merge can precede validation.
Before merging a PR whose issue completion depends on post-merge validation,
inspect `gh pr view <number> --json closingIssuesReferences` and require an empty
list. Remove every closing reference and read the field again; prose negation
does not disable GitHub keyword parsing. Use neutral `Refs #N` wording, then update
the Issue and Project only after actual merged-main evidence. Reuse GitHub’s
computed field instead of maintaining a keyword parser.
[The observed failure](https://github.com/CVX-Hull/enactive/issues/75) records why
this explicit check supplements prose review.

Use these Project single-select fields consistently:

| Field | Values and meaning |
| --- | --- |
| Horizon | Now: selected current outcome; Next: ordered candidates; Later: deferred with revisit trigger |
| Priority | P0: urgent constraint/control failure; P1: next important outcome; P2: useful follow-up |
| Size | S: one bounded slice; M: several cohesive steps; L: split before Ready; Unknown: investigate before commitment |
| Confidence | Low: major unknowns; Medium: understood with material assumptions; High: supported by comparable local evidence |

Horizon is sequencing, priority is importance, size is scope and confidence is
confidence in the estimate. None is a promised delivery date. Put a blocker flag
in a dedicated label/field and its reason in the issue; retain the same convention
across views. Use assignees for accountable owners and linked PRs for implementation.

## Ready brief and execution capacity

Each Ready issue links its relevant contracts and records: problem/user outcome;
scope and exclusions; owner; acceptance/failure conditions and validation lanes;
dependencies and agreed interfaces; risks/unknowns; size, effort range, confidence
and assumptions; evidence expected; and any user decision required. Consequential
changes link a [review brief](engineering.md#s-work-reviewable-and-proportionate-changes).
A worker handoff additionally names base revision, worktree, owned paths, fixed
decisions, exact checks and return evidence, as required by S-AGENT.

Keep one active integration slice. Initially allow at most two concurrent
implementation workers, each in a separate project-local worktree with disjoint
named paths, agreed interfaces and one writer per checkout. Explorers read only;
reviewers receive fresh context. The lead alone integrates and serializes the
game, saves, bridge, ports, builds, dependency environments and caches. Workers
do not run native demonstrations. Source isolation does not isolate shared runtime.

Pull new work only when implementation, review and validation capacity exist.
Work counts as in progress from In progress until Done or explicit cancellation,
including Review, Validation and blocked time. Clear growing queues before starting more implementation; reduce concurrency if review or integration cannot keep up. Do not
increase the initial worker limit without measured evidence and a standards change.
After two unsuccessful repair attempts, or drift beyond owned paths, the worker
stops and hands evidence to the lead, who takes the work back and replans.

## Estimates and forecasts

Estimate a range of effort for the whole outcome, including investigation,
implementation, review, integration, rework and validation; name units and major
assumptions. Separate this from elapsed delivery time, which includes queues and
blocked time, and from token/API or financial budgets, which cap resources.
Record actual effort when known, elapsed start/finish dates, waiting causes and
budget use without inventing unavailable measurements. Re-estimate openly when
scope, dependencies or evidence changes; retain the original estimate for learning.

Track WIP, item age, completed outcomes per interval and elapsed cycle time from
In progress to Done. Keep cancelled work separate. Compare similar item sizes,
validation lanes and model/tool versions. Forecast from this project's history,
recording sample size, period, exclusions and assumptions. With sparse history,
give an explicitly provisional range and confidence; do not invent probability
claims or import benchmark throughput. A dated target is a planning assumption
unless the user agrees to a commitment. Update it when evidence changes.

Review dependencies and the critical path: the longest dependent chain including
review and serialized native validation. Parallel workers cannot shorten a shared
bottleneck merely by increasing their count. Resolve critical unknowns early.
When models, harnesses or tools change, record versions and compare representative
accepted outcomes, defects, review effort, elapsed time and cost before revising
capacity or forecasts. Historical model results are not current guarantees.

## Campaign-driven improvement

Every gameplay campaign is both a bounded product outcome and a source of evidence
for future work. The lead owns this manual workflow for development rehearsals,
deciding runs and future campaign objectives. Use the existing capability milestone,
campaign issue and bounded segment children; an attempt does not need a new tracker
or milestone. GitHub owns findings, decisions and follow-ups; retained gameplay
artifacts supply evidence. A campaign is not automatically a learning experiment.

Before Ready, record the campaign objective/scenario, success and failure criteria,
source/configuration, player/executor, finite attempt and cumulative resource limits,
stop/save/handoff rules, evidence retention, and review checkpoints and effort.
Distinguish development evidence from any held-out assessment before using it to
choose changes. Keep campaign-specific observed facts separate from reusable lesson
candidates. Unknown identity, absent observations and uncertain delivery remain
unknown; a review cannot reconstruct an unobserved outcome.

Review at planned segment boundaries, handoffs, material failure/unknown stops and
campaign closeout. A stopped attempt gets a review even if it cannot supply a
successful gameplay result. Use a concise finding table in the campaign issue or
linked dated report: source observation/action references; expected versus observed
result and user consequence; suspected cause and alternative explanations; affected
area; disposition; accountable owner; linked follow-up or revisit trigger; and the
evidence required to accept a change. Diagnose missing observations, memory or
retrieval, planning, execution/authority, outcome monitoring and UI separately;
one failure may involve several areas. Record what the owner could not understand
or control, not just what the player failed to accomplish.

Route findings to existing issues first. Create a bounded child only for an actual
unowned gap; do not reopen accepted foundations or add every research program to
the critical path. Mark a finding as fix now, investigate, defer, reject/no change,
or unresolved. A true readiness blocker gets a native GitHub dependency, blocked
label, owner and next action; optional research gets a link and revisit trigger.
Explain how the finding changes the next segment's objective, context, plan or
limits, or why no change is justified. Never renew an attempt or budget silently.

Before adopting an improvement, apply the existing reuse, review, migration and
validation controls. Retest the demonstrated defect and relevant regression cases;
generalized memory/lesson or performance claims also require separate held-out
evidence with source-episode separation. Failed and successful development episodes
remain development data, not fresh tests. In a deciding run, freeze the declared
implementation and reusable lesson/prompt configuration; ordinary observations,
campaign facts and plan corrections may still evolve under its protocol. If a
repair changes the frozen candidate, stop and replan prospectively, retain the old
attempt and declare any new assessment. Never patch away a deciding-run failure.

At closeout, assess the gameplay outcome separately from the improvement findings.
A useful failure review can complete its review task but cannot satisfy successful
survival acceptance. Link accepted changes, unresolved risks and deferred work into
the next campaign brief. A successful run alone does not establish causal benefit,
general reliability or continuous learning. Read-only evidence/area reviews may run
in parallel; shared execution, integration and native validation stay serialized.

Enforce this through the existing Ready/Done and C-REVIEW checks: a campaign cannot
be Ready without its review plan or Done without its outcome and finding dispositions.
The lead verifies issue links/dependencies and the exact evidence; GitHub fields do
not enforce semantic completeness. At campaign closeout, and under C-MAINTENANCE's
existing event/date triggers, inspect review effort, recurring or reopened defects,
unresolved finding age, escaped regressions and whether accepted changes helped
later play. Record unavailable measurements. Simplify, improve or retire ineffective
steps from evidence; do not add a scheduler, automatically renew dates, or create a
second findings database.

## Milestone review and controls

A milestone finishes only when its outcomes and required evidence lanes pass,
limitations are explicit and the lead verifies the candidate. Publish a concise
outcome/evidence update; carry unresolved work forward explicitly. After each
milestone, review estimate error, blocked/queue time, rework, escaped defects and
review burden. Repair stale guidance, tune WIP/decomposition and improve or retire
costly controls under [C-MAINTENANCE](controls.md#c-maintenance--drift-recovery-and-retention-review-manual).
Record concrete findings and follow-up owners, not automatic date renewal.

| Principles → standards | Existing controls and enforcement limits |
| --- | --- |
| P-REVIEW/P-CHANGE/P-KNOWLEDGE → S-WORK/S-DOCS | C-REVIEW/C-USABILITY/C-GOVERNANCE: briefs, understandable views and current docs; metadata checks cannot prove comprehension or live board accuracy |
| P-TRUTH/P-KNOWLEDGE/P-REVIEW → S-AGENT | C-REVIEW/C-MAINTENANCE: bounded delegation, lead inspection and capacity review; same-account agents cannot supply independent GitHub human approval |
| P-TRUTH/P-UNCERTAINTY → S-EVIDENCE/S-DELIVERY | C-PORTABLE/C-NATIVE/C-RELEASE: exact-candidate checks and separate evidence lanes; merge/CI success alone cannot establish Done |

GitHub fields and views aid visibility; they do not enforce semantic readiness,
WIP or acceptance. Main currently requires a PR and the observed Actions `controller` check with
strict freshness; force-push/deletion and actor bypass are disabled. Required
human approvals are zero; unavailable independent human review remains an explicit gap.
Inspect the active rules and rerun relevant probes after configuration changes. Agent
review is evidence for lead adjudication, never a fabricated human approval.
