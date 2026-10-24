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

Keep summaries purpose-specific: the overview explains capabilities and limits;
the work map links the delivery path and decisive evidence; a change brief records
design/acceptance decisions. Do not copy Issue status, assignment, estimates,
next-action queues or CI receipts into those pages. A concise evidence checkpoint
may link a dated report, but detailed attempt chronology and exact costs belong
in that report, and publication receipts in the PR. At integration review, remove
mirrored fields, stale “current” claims and repeated narratives rather than append
another checkpoint. Use the existing C-REVIEW/C-MAINTENANCE process; semantic
duplication is a review judgment, not a new parser or per-action check.

Use GitHub's issues, sub-issues, dependencies, milestones, pull requests, fields,
saved views and built-in workflows. No custom tracker or background scheduler.
Select work for the next independent-play outcome and the longer-term capabilities
that enable future outcomes. Resolve demonstrated obstacles and make deliberate
investments in useful accelerators. Apply P-CHANGE/S-CODE to available capabilities
beyond this repository; adoption, integration and deletion can be more valuable
than new implementation. Include setup, latency, review and ongoing operating cost
in the choice. Do not turn a speculative framework, exhaustive defense or process
improvement into a campaign prerequisite without a concrete outcome dependency.
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

Reconcile actionable discussion, research, review and campaign findings at those
checkpoints. Prefer updating an existing issue; create a new one only for distinct
owned work. Give each finding an implementation/follow-up, duplicate, deferred or
rejected disposition with its reason, next action/acceptance and dependencies.
Link affected design, principles/standards/controls, procedures and evidence;
update their authoritative sources when applicable, including generated controls
through the registry. Preserve current-versus-proposed status and unverified lanes.
C-REVIEW checks this coverage and C-MAINTENANCE revisits drift under existing
triggers. A review finding is not fixed because it was filed, and a document is
not accurate merely because it has a recent date. This uses GitHub and the current
document/control system, without another tracker, parser or per-action ceremony.

## Risk-based assurance

The lead selects the required assurance when scoping the issue, based on impact,
uncertainty, reversibility and dependency reach. Review the highest changed
architectural responsibility first, then the affected component/internal design,
contracts/state/callers and implementation. Unchanged ancestors need an impact
statement and link, not serial approvals. A change can touch several branches.
The same approach applies to workflow, documentation and controls themselves.

| Change or claim | Minimum relevant feedback | Review / expensive evidence trigger |
| --- | --- | --- |
| Editorial: correct text or links without behavior/requirement change | Document/metadata/link checks and diff inspection; render changed visuals | Lead checks meaning; no game/native build or full behavioral rerun solely for wording |
| Contained: behavior change within understood existing boundaries | Fast checks and focused positive/negative behavioral cases | Lead reviews implementation against design; consolidate independent review at the coherent integration checkpoint |
| Boundary: change ownership, input, persistence/schema, permission, dependency or native contract | Brief/alternatives, focused independent architecture/risk review before commitment; affected failure cases and coordinated migration | Review changed contracts against callers; matching native build/affected qualification when native support is claimed; security/product/research lens only when relevant |
| Outcome: integration, release, new support, performance or learning claim | Independently assessed outcome/evidence against original acceptance | Exact full protected CI, applicable native/usability/held-out lanes and unresolved finding dispositions; merge alone is insufficient |

Choose checks that could detect a plausible consequential error; state unrun lanes
and why they are inapplicable or pending. A high-consequence boundary is not made
low risk by a small diff. Passing fixtures do not replace actual required native
evidence, and an unexplained red check is not waived by a cheaper green one.
Authority/Pause/identity/delivery/migration/cleanup failures block affected inputs.
Required full CI and branch protection remain unchanged for merge; an editorial
change can avoid a local full rerun without claiming one passed.

Use a larger **coherent outcome** with small inspectable implementation steps and
cheap feedback throughout. Integrate related components and pay for broad checks
when they answer a meaningful integration question. Do not batch unrelated work
into an unreviewable release or defer boundary review until after implementation.
Split a slice when uncertainty prevents focused tests/review, coordination exceeds
its benefit or the candidate cannot be understood as one outcome. Agile/Lean
feedback and limited WIP inform this policy; sprint rituals, fixed batch sizes and
more agents are not requirements. The [research basis](research-engineering.md#recursive-architecture-and-assurance--2026-10-24)
distinguishes external guidance from this project's judgment.

At integration use existing command/CI/PR/run receipts to compare useful progress,
defects caught/escaped, review/rework/waiting effort and cost of checks. Record
unknowns without inventing measurements. Keep, narrow, replace or retire a control
from that evidence under C-MAINTENANCE. Do not create another metrics service,
review queue or per-action gameplay approval. Existing maintenance expiry still
applies; an alternative scoped-development exception needs a separately reviewed
policy/check change, not an undocumented bypass.

## Development-first delivery

Get a coherent behavior working through real use, then qualify it. The lead selects
one useful integration outcome and spends development effort finding its important
failures. Review and verification protect the resulting acceptance claim; they are
not a ritual to repeat before each short attempt. This applies to code, gameplay,
documentation and project controls under P-CHANGE/P-KNOWLEDGE/P-REVIEW and
S-WORK/S-EVIDENCE/S-DOCS. The full user outcome remains the definition of Done.

| Checkpoint | Required work and evidence | What may proceed |
| --- | --- | --- |
| Development checkpoint | Fast checks, relevant focused behavioral/negative tests, inspected diff and a Git commit; record unrun or failed lanes | A finite development run on that exact source; full review/CI may be pending |
| Development run | Declared development purpose, objective, actor, source/native/configuration, finite attempts/resources/reserve and stop rules; retain original ledger/frames/unknowns | Player-owned meaningful gameplay and learning about the implementation; no acceptance or reliability claim |
| Integration checkpoint | A useful behavior composes end to end, or evidence identifies a concrete blocker; consolidate findings and current contracts | One cohesive independent review, full portable checks and PR validation; split ownership without fragmenting the outcome |
| Formal acceptance and merge | Review the exact frozen candidate and retained run evidence; require passed exact PR `controller` check/full suite, required native/graphical outcomes and finding dispositions | Merge through existing main protection; Done/release waits for actual merged-main validation and applicable outcome evidence |

For example, the supply-and-shelter checkpoint required useful
navigation/replanning, supplies/needs, shelter/rest, genuine memory correction and
unfinished Work, actual fresh player context, normal same-character save/new-child
reload and final normal ending. The selected outcome belongs in its GitHub issue.
An early menu failure is development evidence,
not a reason to redefine success or publish a new acceptance package before trying
again. Other iterations name their equivalent meaningful checkpoint in the issue.

### Minimum checks and escalation

Run `.venv/bin/python tools/check.py --fast` and the focused tests that exercise the
changed behavior and its consequential failure boundaries. The fast command checks
syntax/lint, imports, document structure/links, governance and whitespace; it does
not run behavioral tests or render diagrams. The lead names focused commands and
results in the existing issue/PR or run note. Missing checks are explicit, never
implied green. A documentation-only correction needs the applicable document checks;
a controller change needs relevant behavior and negative cases, not just lint.

An applicable failure in input authority, Pause, identity, budgets, delivery
uncertainty, required version migration or owned cleanup blocks affected play.
Consequential new boundaries/dependencies still need S-ARCH's design/risk review.
Relevant native changes need a valid matching build and bounded checks of affected
input boundaries. No full suite or second readiness reviewer is automatically
required before every ordinary development attempt. Pending unrelated CI is not
a development gate; a discovered applicable failure stops affected new inputs for
repair. Preserve all prior evidence and costs. Never suppress a failed gate or use
`--no-verify` as the workflow.

Freeze source and declared conditions for EACH finite run, including development.
A source repair happens only after the deciding actor is quiescent and the owned
runtime is closed; a new run gets a new identity and prospective allowance. No
patching a live run, replaying uncertain input, restoring old authority or silently
extending a stopped phase. Native freshness, one input owner, independent user
Pause, project-local state and normal CDDA behavior apply in every checkpoint.
Routine gameplay keeps zero human/automatic approval-review round trips. The lead
owns engineering and observes; development labeling does not authorize tactical
rescue or make assisted evidence independent.

Separate **qualification** from **development continuation** in each prospective
brief. A missed latency target or incomplete useful-decision cohort rejects the
configuration's responsiveness claim; alone it need not end an explicitly finite
development campaign. Within its original limits, the player can continue useful
survival, acquisition, revision and memory succession to expose the next important
failure. Do not manufacture samples, count filler as progress or deploy the slow
configuration as qualified. Freeze an ending deadline and reassess the coupled
forecast at meaningful boundaries. Pause/custody loss and uncertain delivery still
stop dispatch; insufficient ending capacity, terminal failure or unresolved
authority/source uncertainty require the declared quiescence/ending procedure.
No automatic extension, revival or retrospective change to a failed run follows.
This applies the [existing non-myopic development distinction](research-executable-policies.md#evidence-matrix-and-project-judgment),
not a guarantee of convergence. C-REVIEW checks the two decisions in the brief and
closed evidence; C-USABILITY keeps the original acceptance criteria.

### Efficient discovery

Optimize for useful uncertainty resolved and capability progress per unit of work.
Use the cheapest relevant check first: producer source/configuration, a focused
real-component reproduction, then finite native exploration and the integrated
outcome. For example, registered action names do not prove default key bindings;
inspect the engine's existing bindings before spending another creation cycle.
Batch related unknown capabilities into a coherent development admission where
possible. A traceable failure can guide the next experiment without a fresh full
suite or report package. The player uses supported replanning/recovery while its
scope remains eligible; unknown delivery or lost authority never permits replay.

Retain the starting basis, source/configuration, intent, observations, delivery and
semantic outcome, costs, interventions and finding disposition in the existing
admission/ledger/archive/Git/Issues. Show the maintainer a small coverage/findings
summary with links to those records; do not build a second history or tracker.
Current normal checkpoint reload is limited to its own mission's proven save.
[Cross-admission development checkpoint reuse #175](https://github.com/CVX-Hull/enactive/issues/175)
is proposed work, not permission to restore old authority or roll back a run.
Source repairs still require closure and a new finite admission; exploratory
evidence keeps its declared conditions and does not become a fresh assessment.

### Evidence and documentation cadence

Use the existing issue, immutable admission, ledger and archive. A development
attempt needs a short closure/finding note referencing source and artifacts,
outcome, known costs/unknowns, cleanup disposition and the next owned action.
Do not copy the entire contract, write a standalone acceptance report, launch
another review swarm or publish an amendment for every menu error. Retain the raw
evidence immediately; consolidate reports, selected images/provenance and finding
dispositions at the integration/acceptance checkpoint. Public notes need the usual
identity/privacy inspection. Historical failures remain accessible and never turn
into passing tests after a repair.

Update authoritative contracts when behavior changes; mark incomplete support and
unrun checks plainly. Keep chat updates brief and the overview understandable.
An issue/PR brief is enough for a routine fix. A consequential workflow/boundary
change may need one short design rationale, not parallel plan/status systems.
Apply S-CODE's platform-contract rule during that review: state which configured
DB/OS/library behavior already supplies the guarantee and what project requirement
remains. Simplification and removal of duplicate validation/recovery are valid work
outcomes. Track evidence-backed gaps in existing issues; speculative hardening is
not a new campaign gate or a reason to add another approval layer.

Development episodes used to select repairs remain development data. Freeze source,
objective, conditions and limits before every run. Formal acceptance is a decision
on the resulting evidence, not a requirement to repeat an unchanged run. A complete
unassisted development run may establish the prospective functional mission outcome
after its unchanged exact source passes full checks and independent evidence review.
The run must actually meet every original criterion, including independence, memory
succession and normal ending; missing evidence or prohibited assistance cannot be
repaired afterward. Keep its development label. Held-out comparisons and generalized
learning/performance claims require their separately frozen assessment conditions
and source-episode separation; development data is not relabeled held-out data. A comprehensive acceptance suite
is paid once per coherent candidate and repeated when new changes, failures or uncovered risk
justify it. Do not rerun it for unchanged procedural admissions or duplicate a
passed hosted suite locally solely to complete a checklist.

### Enforcement and upkeep

The local commit hook runs the fast command. CI runs the full command on PRs and
pushes to main, with no path filters on the required PR job. Superseded PR runs are
cancelled through GitHub concurrency; running main checks are not cancelled by
that policy. Development play need not wait for CI, but formal acceptance/merge
must use the actual successful exact candidate check. It may be completed after
the development run, before acceptance is granted. The required job name,
GitHub App association and main ruleset remain unchanged. C-PORTABLE/C-RELEASE
own those mechanical boundaries; C-REVIEW checks selected tests, outcome scope and
evidence rather than approving ordinary gameplay actions.

At meaningful integration/closeout checkpoints, C-MAINTENANCE reviews time to real
play, verification/review/waiting effort, useful gameplay reached, recurring failures,
escaped regressions and user interventions. Use available command/ledger/CI times;
unmeasured model effort stays unknown. Do not impose a numerical performance quota
from a single run. Simplify or retire a step whose cost is not justified by defects
it catches; strengthen a targeted check when evidence warrants it. The lead owns
this review under existing event/date triggers, without another scheduler or tracker.

## Review by decision and risk

Name the decision and uncertainty a review should resolve, then choose the smallest
useful set of perspectives and an inspectable artifact. A review should enable the
next safe experiment or expose a concrete blocker. Do not ask every role to review
every change, require consensus, or repeat a full review of unchanged material.

| Trigger / artifact | Useful review and timing |
| --- | --- |
| Small mapping/bug fix with unchanged boundaries | Lead inspection and relevant regressions; native qualification as applicable. Include it in coherent integration review; no automatic product/architecture swarm before development. |
| New input/ownership/persistence/schema/learning boundary | Independent architecture/risk review of the brief and alternatives before implementation commitment. Reversible isolated probes may inform that design within their declared controls. |
| New player capability or observer workflow | Product/player or observer perspective on goals, acceptance and a working flow, diagram or prototype. Validate actual usability later; an agent persona is not a real user study. |
| New memory/adaptation policy or consequential literature claim | Research/evidence perspective checks prior documents, primary support, transfer limits, conflicts and functional-versus-efficacy claims. No fresh full survey for each leaf fix. |
| Permissions, external access or isolation change | Focused security/operations review at that boundary. This is not gameplay strategy review or a critic/approval per key. |
| Integrated acceptance/publication | Independent outcome/evidence and maintainability review against original requirements, source/configuration and failure/unknown receipts. Full checks and protected publication remain. |

For maintainer-facing design review, lead with the user outcome, a small boundary
diagram when useful, important alternatives/tradeoffs, open decisions and evidence
limits. Link implementation detail rather than requiring the user to audit it.
Review the actual working flow again at integration when implementation reveals
new information; the earlier design review is not a promise that the design is right.

For consequential work, two or three clean-context reviewers may work in parallel
on distinct questions, such as product outcome, player/observer experience and
architecture/research. Use the named reviewer role with an explicit lens, source
paths, decisions already made, user constraints and acceptance questions. These
are proxy perspectives, not delegated product authority. The lead owns decisions
and verifies findings against evidence; the user decides actual product tradeoffs
when needed. Avoid identical prompts or a committee of overlapping approvals.

Report concrete findings with source, impact, uncertainty and what would resolve
them. Adjudicate material findings before the affected commitment; track other
owned work without blocking unrelated exploration. Re-review changed boundaries
or new contrary evidence, not the entire project after each edit. Stop reviewing
when evidence is adequate for the next stage and material findings are resolved;
unresolved required checks remain explicit blockers, never a green badge.

Record selection, findings/dispositions and known review effort in the existing
Issue/PR. At meaningful checkpoints compare useful progress, escaped defects,
false alarms and review/coordination cost; simplify or strengthen controls from
those observations. Reuse C-REVIEW, CI and current issue workflow. No new review
tracker, mandatory per-feature swarm, recurring date reset or routine gameplay
approval follows. The lead may review the tightly coupled change itself when
delegating would add little; independent acceptance remains separate.

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

Before banking long optional work, reconcile actual current inventory and observed
resource dependencies with the full remaining outcome. Separate current visibility,
remembered terrain, historical possession and generic mechanics. A replenishment
candidate or recipe screen is not a demonstrated supply chain: require actual
output, source/storage/fuel coverage and safe access where the outcome depends on
it. Include required startup, midpoint and final cleanup in remaining fit. An early
readiness failure stops its frozen attempt; another attempt needs its own
prospective finite decision and cannot silently renew old authority. In an explicitly
reviewed functional continuation, bounded essential exploration may proceed while
current needs, usable stock and a next-decision/retreat margin support it. A verified
week of supplies is not required before acquisition gameplay; actual output and
coverage remain necessary before banking optional work on that supply.

Prefer one cohesive functional admission and rolling evidence/needs review over
serial short probe–cleanup–amendment–publication cycles. Retire redundant internal
class limits prospectively when their measured cost no longer serves the outcome;
retain every prior limit/result/cost and finite new total/segment/attempt ceilings.
Never change user guarantees or original whole ceilings through an internal exception.
For this survival campaign the user explicitly delegated **gameplay-related
extensions**, including prospective time and input budgets, to prioritize quality
data. Record finite revised ceilings/endpoints, reason/forecast and retained costs
before input; preserve the effective final cleanup reserve against both whole and
aggregate limits. This delegation does not waive safety, renew failed phases, reset
costs or authorize provider spending or permission/global environment changes.
No routine gameplay-budget question is required within that delegation.
Use the [development-first checkpoints](#development-first-delivery) to select
validation timing: frozen finite development runs follow fast/focused checks;
formal acceptance follows reviewed exact-candidate full checks. Unchanged-runtime
procedural admissions reuse applicable evidence; they do not trigger another suite
or reviewer. Consolidate publication, review and merged-main CI for the coherent
outcome. Do not require a new PR per tactical segment. Source/native changes and
held-out assessments retain their declared verification and freeze requirements. C-REVIEW/C-NATIVE/C-RELEASE/C-MAINTENANCE own these manual
checks; this is no new automated enforcement claim.

Review at planned segment boundaries, handoffs, material failure/unknown stops and
campaign closeout. A stopped attempt gets a concise finding/closure disposition even if it cannot
supply a successful gameplay result; an independent acceptance review waits for
the integration checkpoint unless a concrete risk requires it earlier. Use a concise finding table in the campaign issue or
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
