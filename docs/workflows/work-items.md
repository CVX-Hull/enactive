---
owner: lead
review_trigger: Changes to this delivery decision, ownership or review policy
status: active
---

# Work items and flow

During triage, the lead adds selected issues to the linked Project and assigns
Backlog, owner, Horizon, Priority, Size and Confidence. A newly opened issue is
not automatically Ready; unset planning fields are resolved before commitment.

An issue represents one independently reviewable outcome. Use the following scales
without another tracker or a mandatory record for each scale:

| Scale | Purpose and existing home |
| --- | --- |
| Product milestone | A useful capability or learning result spanning iterations; GitHub milestone/aggregate Issue owns acceptance and limitations |
| Delivery iteration / round | One coherent capability, qualification/repair or discovery/enabler outcome; an existing Issue owns its core, optional scope and decision |
| Integration batch | A safely reviewable integrated change; commits/PRs own implementation and review evidence |
| Feedback checkpoint | Focused tests, design review, prototype or observation resolving a relevant uncertainty; retain results in the owning Issue/PR or consolidated report |
| Runtime attempt | Separately frozen finite execution with original costs, failures and stop conditions; the existing run record owns evidence, not future authority |

## Outcome-focused iterations

Choose a valuable inspectable outcome, rather than a target number of cards, files,
PRs, agent sessions or game attempts. A substantial outcome can contain several
small integration batches and frequent inexpensive feedback. Related bounded
issues may share an integrated PR and relevant acceptance setup; an internal
adapter or handoff need not become a separate delivery round. Coordinated
S-MIGRATION changes may need an atomic batch; do not create a second active
contract simply to make the diff smaller.

Shape a required core and explicitly optional scope. Include work only when it
contributes to the goal, resolves a concrete risk/dependency, or economically
shares setup without displacing the core. Being small or easy to close is not
sufficient. Fund applicable reuse research, architecture/design, implementation,
integration, regression checks, native/usefulness evidence, proportionate review,
current documentation, publication and owned cleanup within the iteration.
Link existing artifacts; this is not a document, full-suite or review quota per task.

Capability iterations finish with the promised behavior and required evidence.
Qualification/repair iterations establish a named important boundary. Discovery
or accelerator iterations resolve a named decision or enable a specified later
outcome, with evidence and a stop/revisit condition. A negative investigation may
complete its declared research goal; it cannot satisfy failed feature acceptance.
Use a bounded investigation when uncertainty prevents shaping a credible core;
discovery can continue alongside independent understood delivery work.

Choose an effort appetite and a reviewable horizon that include integration,
rework, review and the scarce validation lane. If the core cannot fit, rescope or
split it; reduce optional scope before weakening required quality or evidence.
At a material forecast/risk change, explicitly decide to continue within the
appetite, reshape, stop or propose a new iteration. Do not silently extend forever.
No fixed sprint duration, story-point target, maintenance percentage or AI capacity
multiplier is prescribed. Start with a cohesive M-or-smaller scoped outcome and
adjust from comparable local evidence; large aggregates need bounded children.
The lead checks goal, fit and completion capacity at Ready and integration review
under C-REVIEW, retaining the [two-writer/shared-runtime limits](../standards/agents.md).

| Status | Entry/exit policy |
| --- | --- |
| Backlog | Candidate with a problem and intended outcome; no execution commitment |
| Ready | Scope, owner, interfaces/dependencies, acceptance and required validation lanes are clear; needed decisions resolved |
| In progress | Development, targeted checks and real development runs against the brief; record start date |
| Review | Cohesive diff and executed checks available; independent review appropriate to risk is requested |
| Validation | Review findings resolved; exact candidate undergoes formal portable/native/graphical acceptance |
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

Each Ready issue links its relevant contracts and records: problem/user outcome or
discovery decision; required core, optional scope and exclusions; owner;
acceptance/failure conditions and applicable validation lanes; dependencies and
agreed interfaces; risks/unknowns and stop/rescope conditions; effort appetite,
size, effort range, confidence and assumptions; evidence and completion work
expected; and any user decision required. For children, link the parent iteration's
appetite and shared integration/validation instead of allocating duplicate budgets.
An appetite, assignment or forecast grants no runtime/API resources. Consequential
changes link a [review brief](../standards/work.md#s-work-reviewable-and-proportionate-changes).
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

An appetite states how much effort the outcome merits; an estimate predicts the
effort needed. A forecast predicts completion under stated capacity and queue
assumptions. Authorized run/input/token/API/financial allowances separately cap
execution; none of these planning values grants or renews them.
Estimate a range for the whole outcome, including investigation/reuse, design,
implementation, review, integration, rework, applicable validation, documentation,
publication and cleanup; name units and major assumptions. Separate this from
elapsed delivery time, which includes queues and blocked time.
Record actual effort when known, elapsed start/finish dates, waiting causes and
budget use without inventing unavailable measurements. Re-estimate openly when
scope, dependencies or evidence changes; retain the original estimate for learning.

Track WIP, item age, completed outcomes per interval and elapsed cycle time from
In progress to Done. Distinguish aggregate outcomes from leaf work; do not count
them as independent jobs or invent unknown historical start dates. LOC, commits,
PR count, tests added and agent utilization are activity, not success targets.
Keep cancelled work separate. Compare similar item sizes,
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

[Workflow index](../project-management.md).
