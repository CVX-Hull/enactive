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
| Outcome: integration, release, new support, performance or learning claim | Independently assessed outcome/evidence against original acceptance | Appropriate exact protected CI profile, full regression for broad source changes before merge, applicable native/usability/held-out lanes and unresolved finding dispositions; merge alone is insufficient |

Choose checks that could detect a plausible consequential error; state unrun lanes
and why they are inapplicable or pending. A high-consequence boundary is not made
low risk by a small diff. Passing fixtures do not replace actual required native
evidence, and an unexplained red check is not waived by a cheaper green one.
Authority/Pause/identity/delivery/migration/cleanup failures block affected inputs.
The required `controller` check and branch protection remain unchanged; the
[profile policy](#protected-ci-profiles) selects the executed portable scope.
An editorial or smoke result cannot be reported as a full regression pass.

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
review queue or per-action gameplay approval. Fast checkpoints visibly warn on
calendar-only maintenance expiry for every control; every hosted profile remains
strict at the current date. No dates are renewed automatically. Event-triggered
review and applicable actual failures/evidence gaps still govern the affected work; resolve overdue
review at the existing integration/formal-acceptance checkpoint under S-DOCS.

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
| Integration checkpoint | A useful behavior composes end to end, or evidence identifies a concrete blocker; consolidate findings and current contracts | One cohesive independent review and appropriate portable profile/PR validation; broad source changes receive full regression before merge |
| Formal acceptance and merge | Review the exact frozen candidate and retained run evidence; require the appropriate passed exact PR `controller` profile, full regression for broad source changes, required native/graphical outcomes and finding dispositions | Merge through existing main protection; Done/release waits for actual appropriate merged-main validation and applicable outcome evidence |

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

The local commit hook runs the fast command. Development play need not wait for
CI, but formal acceptance/merge requires the actual successful exact-candidate
check under the profile policy below. It may complete after an unchanged development
run, before acceptance is granted. C-PORTABLE/C-RELEASE own the mechanical
boundaries; C-REVIEW checks selected tests, outcome scope and evidence rather than
approving ordinary gameplay actions.

### Protected CI profiles

![Proportional validation before and after protected integration.](diagrams/ci-validation.svg)

This view separates the required PR gate from post-merge evidence. Unknown
eligibility uses full checks; native/gameplay outcomes remain separate.
[Editable source](diagrams/ci-validation.mmd).

One always-present Actions `controller` job remains required with its existing App
association and strict main ruleset. Pull-request triggers explicitly target main;
main pushes also run. There are no workflow path filters, conditional required jobs,
manual labels/overrides or ignored failures. Superseded PR runs are cancelled;
running main checks are not cancelled by that policy. `tools/ci.py` chooses a closed
profile from existing Git/GitHub facts and invokes `tools/check.py`. Missing or
ambiguous eligibility selects full; checker or execution failure fails the job.
The [proportional validation brief](changes/065-proportional-ci.md) records rationale.

All hosted profiles run syntax, selected Ruff, import contracts, JavaScript syntax,
document metadata/local links, current-date strict governance, whitespace and diagram
rendering. Local `--fast` retains calendar-only warnings and omits behavioral tests
and diagram rendering. It is not a hosted profile.

| Profile | Additional executed checks | Supported claim |
| --- | --- | --- |
| Full (also the default local command) | Complete pytest collection of existing unittest cases, four xdist processes with work stealing and 20 slowest durations, plus viewer regressions | Full portable regression; native build/gameplay remain separate |
| Editorial | No runtime tests or viewer regressions | Strict document/structural validation only |
| Movement | Explicit policy and all four direct consumer suites, plus fixed boundary smoke and viewer regressions | Contained movement-policy regression; full regression was not run |
| Viewer | Server and fixed boundary smoke, plus production viewer logic with a synthetic DOM | Contained viewer/boundary regression; no browser layout or full regression claim |
| Main-smoke | Fixed gameplay/evidence/request, ledger and HTTP cases, plus viewer regressions; serial pytest | Bounded smoke on main with linked qualifying full PR coverage; full regression was not rerun on main |

The [testing guide](testing.md) maps test responsibilities, overlap and upkeep.
`tools/ci.py` owns the exact source allowlists and test targets; the checker consumes
that same manifest. Full and component scopes use four pytest-xdist processes. Full uses built-in
work stealing to balance heterogeneous case durations; component scopes group by
file to keep module/class fixtures together. Main-smoke is serial.
Worker crashes fail the run without restart or silent serial fallback. The pinned
pytest version supports existing unittest assertions, setup/cleanup and subtests.
Collection identity and representative negative matrices are checked when changing
the runner; counts alone do not establish semantic coverage.

Editorial eligibility requires a complete nonempty native Git diff, using the
event's original PR base/head via merge base or main before/after, with
`--no-renames` and NUL-separated paths. Both sides of renames/deletions participate;
every changed object must be regular. The five root documents inspected by the
checker and all `docs/**/*.md` qualify, including current guidance and contracts.
Report assets/JSON under acceptance, assets under docs/assets, and Mermaid source,
SVG and rendered.json directly under docs/diagrams also qualify. Ancillary Markdown
outside the checked set, executable assets, configuration, schemas and registry
JSON do not qualify. Structural consistency cannot prove prose or prompt semantics:
C-REVIEW still checks changed guidance against contracts/source and selects any
needed native/player evidence; running unchanged Python code cannot establish that
new instructions are effective.

A regular diff confined to the explicit movement or viewer allowlist, optionally
with eligible documents, runs that component profile on both PR and main. Movement
includes controller, navigation, skills and supervisor consumers; viewer includes
server/boundary smoke and the Node viewer suite. Changes to both components,
additional source/test helpers, state/persistence/authority, native code, schemas,
dependencies, validation machinery or unknown paths require full PR regression.
Do not infer transitive impact or use manual labels to widen an allowlist. Extending
a boundary requires reviewed consumer coverage and measured benefit. Browser layout
changes retain proportionate rendered review; a synthetic DOM cannot qualify them.

A main editorial or component diff independently executes its selected scope;
it does not borrow a PR pass or claim full coverage. Otherwise main-smoke is
eligible only for an ordinary single-parent squash push adding exactly one commit:
the event's before SHA equals its parent P; exactly one actual merged PR has that
merge SHA, a main base P and head H; P is an ancestor of H; and H's tree equals
actual main. The latest expected `check.yml` pull_request run at H must be completed
and successful, with one successful completed `controller` job, its unique successful
completed `Run strict full validation` step, and an original
`created_at` strictly earlier than the PR's `merged_at`. Equality, malformed times,
a newer failed/cancelled/incomplete run or missing/ambiguous facts require full;
do not search past a newer run for an older success. A successful editorial step
is not full coverage: the earlier run's comparison can differ from the merged PR's
comparison even at the same head. The native step receipt identifies actual full
execution without a new evidence store. The main-only PR trigger,
strict up-to-date protection and default PR merge checkout bind that coverage to
the actual main tree. GitHub's run `pull_requests` list may be empty after merge;
use actual PR/run/Git relationships without fabricating an association.

Changes to validation machinery/context force full on main too: `.github/`, all
engineering `tools/` initially (including checker, selector and package bootstrap),
tests package bootstrap, dependency manifests/locks, renderer
configuration, schemas and control-registry JSON. Covered Markdown alone uses
editorial regardless of whether it describes policy; source changes to implement
that policy are classified separately. This coarse tools boundary avoids maintaining a checker-helper
dependency graph; narrower reuse needs a demonstrated benefit. Normal feature regression tests still receive full PR coverage
but do not alone change validation context. Unknown main paths, nonstandard pushes,
nonregular objects, tree mismatch or unavailable proof select full. Existing pinned
workflow/dependency contracts define the supported environment; no green cache,
provenance service or ambient host fingerprint is introduced. This migration itself
changes validation context and requires full PR and main checks.

Print the selected profile and reason in logs and the Actions summary. Main-smoke
links its qualifying PR run and explicitly reports full regression as unrun on main.
Done requires the appropriate actual PR/main profile and outcome evidence; a reduced
pass never establishes full regression, native support or gameplay acceptance.
Broad source changes always receive full regression before merge. Reuse valid
exact-candidate evidence without duplicating a hosted full pass locally solely for
a checklist; new changes, failures or uncovered risk can require fresh coverage.

### Upkeep

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
| Integrated acceptance/publication | Independent outcome/evidence and maintainability review against original requirements, source/configuration and failure/unknown receipts. Appropriate protected CI profiles and required outcome evidence remain. |

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

An issue represents one independently reviewable outcome. Use the following scales
without another tracker or a mandatory record for each scale:

| Scale | Purpose and existing home |
| --- | --- |
| Product milestone | A useful capability or learning result spanning iterations; GitHub milestone/aggregate Issue owns acceptance and limitations |
| Delivery iteration / round | One coherent capability, qualification/repair or discovery/enabler outcome; an existing Issue owns its core, optional scope and decision |
| Integration batch | A safely reviewable integrated change; commits/PRs own implementation and review evidence |
| Feedback checkpoint | Focused tests, design review, prototype or observation resolving a relevant uncertainty; retain results in the owning Issue/PR or consolidated report |
| Runtime attempt | Separately frozen finite execution with original costs, failures and stop conditions; the existing run record owns evidence, not future authority |

### Outcome-focused iterations

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
under C-REVIEW, retaining the two-writer/shared-runtime limits below.

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
[Operator permissions](operator-permissions.md#finite-gameplay-budget-delegation)
owns the standing delegation and its limits. Record finite revised ceilings/
endpoints, reason/forecast and retained costs before input; preserve the effective
final cleanup reserve against both whole and aggregate limits.
Use the [development-first checkpoints](#development-first-delivery) to select
validation timing: frozen finite development runs follow fast/focused checks;
formal acceptance follows reviewed exact-candidate checks under the
[profile policy](#protected-ci-profiles). Unchanged-runtime
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
