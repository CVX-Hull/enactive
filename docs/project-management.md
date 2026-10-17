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

The selected public repository is [CVX-Hull/cdda-player](https://github.com/CVX-Hull/cdda-player).
GitHub Issues and the [public Project](https://github.com/users/CVX-Hull/projects/2) own live priorities, stages, owners,
dependencies, estimates and blockers. Repository docs own durable purpose,
contracts, procedures, decisions and dated evidence. [Work](work.md) is the
navigation entry point; exceptions are issues linked to their affected standard.
Repository/Project creation and configuration require separate verification;
this document alone does not establish that they exist or are enforced.

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

An issue represents one independently reviewable outcome. A milestone groups
issues into a useful capability or learning result with explicit acceptance and
limitations; a batch of files or number of agent sessions is not a milestone.

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
Avoid closing issue keywords in a PR when validation must follow its merge.

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
WIP or acceptance. Branch/ruleset checks are enforced only once configured and
verified; unavailable independent human review remains an explicit gap. Agent
review is evidence for lead adjudication, never a fabricated human approval.
