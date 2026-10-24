---
owner: lead
review_trigger: Player roles, background memory/procedure updates, latency, evidence or adaptation policy changes
status: proposed
---

# Active play and asynchronous reflection

The player should act, learn and correct itself without the engineering lead
becoming its slow reasoning path. Use one active player and an advisory background
trajectory learner. The active path retains its own planning and judgment, uses
semantic skills where useful and falls back to ordinary interface interaction.
Reflection can improve future decisions without becoming an approval before each
action. The [current component view](../components/memory-learning.md) and protocol
own the implemented advisory exchange. This page retains broader design proposals;
it does not define another deployed contract or establish general learning benefit.

![Proposed active-player and background-reflection design with one input writer.](../diagrams/asynchronous-reflection.svg)

Text equivalent: one active player sends skills or direct interaction through the
existing writer to windowed CDDA. Canonical visible evidence feeds background
reflection. Source-linked proposals return to the player at decision boundaries;
only the active player requests input or commits accepted advisory-memory changes.
User Pause remains independent. [Diagram source](../diagrams/asynchronous-reflection.mmd).

## Fit with the existing system

| Existing basis | Keep / explicit change |
| --- | --- |
| [Tiered research](../research-tiered-gameplay.md#concrete-delegation-and-feedback-contract), especially its asynchronous-candidate rules | Retain one writer, current feedback and bounded skills. The older planning proposal initially waits; current reflection can overlap useful play. This does not establish generic continuous strategy/inference overlap. A procedure can outlive a frame, but input still needs current authority. |
| [Current architecture](../architecture.md), [historical mission design](player-owned-mission.md) and [campaign memory source](../../harness/gameplay/campaign_memory.py) | Claims/Work/context, procedures, pinned historical libraries and bounded reflection compose through the existing writer/SQLite/evidence. [Learning009](../acceptance/2026-10-23-discovery-learning-ninth-attempt.md) demonstrates bounded learned reuse, successor application and useful play during claimed advice. Whole-player cadence, general advisory benefit and the full independent campaign remain unaccepted. |
| [Organic discovery](organic-discovery.md) and [#176](https://github.com/CVX-Hull/enactive/issues/176) / [#177](https://github.com/CVX-Hull/enactive/issues/177) | Mixed interaction enables exploration; procedure data captures abstractions the player develops. Background reflection is one way to help, not a requirement that every procedure be authored by another model. |
| [Memory architecture assessment](../research-memory-architecture.md) / [optional curator #146](https://github.com/CVX-Hull/enactive/issues/146) | Curation advises, has no input authority and must earn its cost. The proposed exchange belongs to the player system, not a standing lead/engineer review service. Curator benefit comparison remains separate from functional procedure learning. |
| [Representation study](../research-memory-representations.md) and [memory review](../research-memory-learning.md) | Keep evidence/interpretation/procedure distinctions and source-linked retirement. Earlier offline reviewed-promotion defaults conflict with autonomous procedure-data evolution: migrate the affected policy/contracts prospectively before implementation. Existing no-online-promotion admissions are unchanged. Code, prompt-template, weight and substrate edits remain versioned engineering work. |

## Execution-first learning

The [source boundary064](../changes/064-execution-first-learning.md) implements
shared candidate authoring/selection, horizon allocation and software adviser
waiting. This broader responsibility model remains partly proposed, informed by the
[Fresh024 execution review](../acceptance/2026-10-24-fresh024-execution-review.md)
and [October24 primary-source synthesis](../research-multirate-agents.md).
Current architecture/protocol remain authoritative. This section refines the
broader proposal below; remaining semantic prioritization/strategic reasoning and
benefit claims are unqualified. It introduces no extra deployed role or run authorization.

![Proposed decision horizons, one input writer and one optional learner.](../diagrams/multirate-player.svg)

The diagram answers “Which work belongs on the next-action path?” Solid arrows
carry current intent/feedback; dotted arrows carry fallible background work.
Its text equivalent is the responsibility table below.
[Editable diagram](../diagrams/multirate-player.mmd).

### Responsibility before model count

| Horizon | Owner and trigger | What must stay off this path |
| --- | --- | --- |
| Each ordinary input | Existing writer/controller and local routine consume fresh feedback, retain actual effects/costs and honor Pause/custody. No LLM is needed for canonical metadata, supported checks or collection. | Memory narration, retrospective synthesis, a second input writer or model approval. |
| Useful local task / surprise | The deciding player selects a routine or raw action from compact current goal/Work, relevant evidence and invalidators. It interprets unfamiliar or image-only conditions and chooses recovery. A routine can branch repeatedly without another model turn. | Copying canonical procedure bodies, source archaeology, empty advice polling and routine retrospective curation. |
| Completed/failed segment; likely upcoming work | One existing bounded learner diagnoses selected evidence, proposes/revises code or guidance, and retains counterexamples. Software coalesces jobs and assembles the useful question. | Taking input custody, live Observe, automatic world-fact overwrite or blocking ordinary justified play. |
| Mission strategy / material plan failure | The active player retains its objective and working plan. The same learner may answer a scoped longer-horizon question in the background. A separate strategic model is deferred until a measured benefit warrants it. | A permanent extra tier, planning on every key, lead tactical advice or ungrounded plan replacement. |

These are decision scales, not four required agents. The convolutional analogy
suggests reusing local computation, but does not establish learned features,
correctness or convergence. Start with one deciding actor and the existing
optional learner. A slow strategic answer can help while useful work proceeds;
if the next decision truly depends on it, show the deliberation rather than filler.

Immediate working memory cannot all move into the background: current obligations,
hazards and interpretations necessary for the next action remain available to the
player. Raw evidence, exact state projections and use/result bookkeeping are
already mostly automatic. Move optional durable abstraction and mechanical
authoring away from that decision; do not create a memory-agent call per action.

### One coherent implementation slice

First address the observed **local execution latency floor** (#164): Fresh024's
85 adjacent within-program ACK gaps have median2.260s/p95=2.935s without model
calls. Profile native exchange/capture, evidence/memory/accounting and publication
on retained scale using existing journals/profilers. Fix demonstrated repeated
history work or other hot-path cost, relying on existing DB/OS contracts; do not
assume a model or manual memory write caused it. Retain original fidelity and
negative cases. The following authoring/scheduling work must not hide this delay.

1. **Canonical candidate authoring and selection** (#177/#178): reuse the player
   SDK's existing metadata derivation for adviser-authored semantic content/code,
   selected parent and allowed support. Expose relevant candidate summaries at
   natural boundaries and exact detail on request. Let explicit player selection
   adopt a candidate through the existing writer without copying its canonical
   JSON into another tool call. Selection is a gameplay decision, not a new
   reviewer/lead approval. A player may still author directly or ignore advice.
   The learner never silently overwrites current facts/Work or executes its code.
2. **Useful questions across the finite horizon** (#178): replace indiscriminate
   four-root expenditure where appropriate with bounded event/recurrence/subgoal
   prioritization, coalescing, age and remaining-horizon allocation. Reuse the
   existing job/mailbox/ledger; do not build an event bus or learned scheduler.
   Known bookkeeping/refusal handling stays automatic. Preserve urgent questions,
   original charged limits, explicit omissions and exhausted/absent-worker states.
3. **Routine coverage with truthful feedback** (#177/#191): use retained pickup,
   wait-menu and changed-condition cases to check what the present view can express.
   Prefer current observed labels/state to remembered indexes. Where a genuinely
   needed visible fact is absent, compare existing rendered-widget/text/image
   facilities before adding the smallest general observation capability. Do not
   hand-code a CDDA recovery policy or claim that a new HUD field fixes the run.
   Keep raw image-informed discovery, yield/revision/retirement and exact versions.
4. **Mechanical collection and measured response** (#164/#143): carry known pending
   operations through existing bounded SDK/host collection without unnecessary
   model round trips where supported. Add only missing correlated timing endpoints
   to existing host/request/native/browser records; retain clock domains and
   unavailable spans. There is no new telemetry service or success-label model.
   Do not infer nondelivery from error text or reset unknown staging; the separate
   positive pre-admission refusal repair stays an explicitly scoped #164 action.

Before dispatching implementation, the lead freezes the changed tool/record
shapes, ownership and migration after a focused boundary review. Reuse existing
schemas/canonical derivation rather than a second authoring API; migrate affected
callers/persisted formats together and remove old paths. The design must say how
original job sources/environment/parents bind a candidate, how selection handles
stale/conflicting revisions and which existing operation owns adoption. These
exact interface choices remain open here; they are not permission to bypass the
current contract. No new dependency is selected by this proposal.

### Allocation, assurance and stopping point

Treat this as one integrated source iteration with small inspectable steps, not
four campaigns or a broad framework. Lead owns shared tool/SDK/runtime/ledger
integration and timing. After the interface review, at most two workers use
disjoint managed worktrees: one owns pure candidate authoring/projection plus
its tests; the other owns reflection scheduling/context plus its tests. The lead
assigns exact paths from the accepted diff scope, avoiding shared-file writes.
A clean-context reviewer checks authority, product responsiveness and evidence
claims at the coherent checkpoint. Existing S-AGENT/C-REVIEW apply.

Source acceptance covers a bounded cost regression/profile for any chosen local
feedback-path repair, with realistic retained history and no weakened guarantees;
canonical authoring without model metadata arithmetic;
explicit selection without retranscribing a procedure; correct source/parent and
stale-conflict behavior; useful-question coverage across early/middle/late synthetic
trajectory phases within the same finite allowance; no routine reflective calls
for successful bookkeeping; worker absence and long compilation leaving the input
path available; original Pause/unknown accounting; and correlated timing with
unknown clock mappings rejected. Replay can test projection/selection and trace
joins, not counterfactual survival or organically learned competence.

Use fast/focused checks throughout, independent boundary/integration review and
protected full CI once coherent. Do not build native or launch games solely to
accept this proposal. **Gameplay remains user-paused.** After an explicit resume,
one finite integrated development assessment should combine organically acquired
useful routines, a counterexample-driven revision/abstention, fresh-context use,
meaningful progress during optional learning, and normal lifecycle. The deciding
system must do this without lead tactics, curation or a per-procedure approver.

Freeze the existing useful-decision cohort and quality/latency criteria before
that assessment: count acquisition, repair, fallback, context, all actor costs,
long activities, misses and failures. A program's `done`, a returned key, higher
coverage or a compact reply is not task success or speed qualification. Reject
the responsiveness claim if thresholds fail; retain useful development evidence
under the existing stopping policy. The seven-day outcome remains separate #145
acceptance, and optional matched-budget causal studies remain #146/#70/#24 work.

No new principle or standing control is needed: S-ARCH owns the automatic/model
split and lead independence, S-UX whole-configuration response, S-MIGRATION contract
changes, C-PORTABLE boundary regressions and C-USABILITY actual adoption/cadence.
Issues/Project own estimates, sequence and current disposition. Revisit extra
model tiers, perception or infrastructure only on a measured decision/coverage gap.

## Responsibilities and concurrency

The active player owns the current objective/plan, local recovery, working facts,
unfinished obligations and actual decisions. It can reason beyond a fixed tree;
being fast does not mean blindly executing the reflector's plan. The background
path reviews trajectory segments, compares successes/failures, identifies repeated
work, proposes procedures/repairs and asks focused evidence questions. It may use a
more capable model when measured benefit justifies the added delay/cost. A distinct
model tier is not mandatory.

Reuse the canonical archive, ledger, source IDs, memory/context and structured
player tools. Add the smallest bounded proposal/exchange records to those systems;
compare maintained facilities first. Do not build another game log, version control,
event bus, autonomous runtime or generic multi-agent orchestration framework. The
exact schema, persistence ownership and estimates still need interface design.

Software schedules background work and retains request/results/cursors. It must
not rely on the lead reading transcripts, sending tactical messages, hand-writing
JSON, approving lessons or waking the worker. The lead owns engineering changes,
not player interpretation, procedure choice or normal recovery. An assessed run
records in-system reflective assistance separately from prohibited lead/user play.

Use immutable trajectory snapshots with a last-included ledger position, episode
and source IDs, relevant memory/procedure/plan versions, and declared limits. The
reflector reads historical artifacts without calling native Observe or taking a
lease. Even a nominally read-only native observation may change the live source.
Any experiment needing game interaction goes back as a proposed information goal
for the active player; it never creates a second input actor or hidden-state reader.

Proposals are persisted separately from accepted memory. The existing serialized
writer applies bounded, item-version-checked changes under the declared update
policy. Publish an atomic new advisory version; preserve evidence and superseded
items. Do not let a late worker overwrite the active player's corrected facts,
unfinished Work or adopted plan. It may propose a correction with evidence.

Read suggestions at meaningful boundaries and promptly surface relevant warnings.
The current skill instance keeps its selected procedure version; a revision affects
later choices, or the player explicitly stops/replans the remaining suffix. Do not
silently rewrite a queued action or already executed prefix. A live hazard or lost
input authority is handled locally without waiting for the background process.

## Automatic work versus model judgment

Use deterministic software for bookkeeping and supported predicates; reserve model
calls for interpretation, abstraction and consequential choices that need them.
The player need not explain every action to a reflector. Reuse existing runtime,
ledger, skill-result and memory hooks to assemble feedback automatically.

| Work | Default mechanism and epistemic limit |
| --- | --- |
| Retain source/action/result IDs, versions, times, costs and unknown delivery | Automatic existing writer/archive/ledger instrumentation. No reflective call or duplicate history. |
| Queue/cursor/batch/retry scheduling and resource ceilings | Automatic bounded software; retry computation only where appropriate, never uncertain game input. Keep skipped coverage and worker failure visible. |
| Retrieval delivery and explicit procedure selection | Automatically record what entered the context, and link a selected procedure/version once to the goal/skill root; children inherit that linkage. A normal structured selection is enough, not another feedback narration per primitive. |
| Delivered/blocked/unknown inputs and exact supported progress | Derive from actual receipts and existing skill checks. Delivery is not semantic success; an unsupported predicate stays unknown. |
| Candidate applicability and outcome | Evaluate declared predicates from available current evidence where possible. Interpreting a screenshot, ambiguous consequence or missing prerequisite may require a model judgment, marked as such. No hidden-state oracle or automatic success from a fluent description. |
| Semantic diagnosis, abstraction, counterexamples and procedure repair | Model work over selected evidence/trajectory segments; prompt only at useful learning or decision boundaries. Different model agreement is not new environment evidence. |
| Duplicate detection, item-version conflicts and known dependency invalidation | Automatic exact checks first. Semantic equivalence/conflict may require model interpretation; it must not silently overwrite a corrected item. |
| Publication of accepted advisory changes | Existing serialized memory writer applies versioned policy-valid updates; neither an engineer nor an extra LLM needs to approve every record. Semantic usefulness remains provisional and revisable. |

Distinguish **retrieved/exposed**, **explicitly selected/referenced**, **attempted**,
**delivery**, **observed effect**, and **judged goal success**. These are different
memory events. A tool can prove which text entered a context, not whether that text
causally changed a model's reasoning. When the player acts freely without an
explicit procedure association, influence remains unknown. Likewise, an unselected
suggestion is not proof it was read and rejected; do not train on invented feedback.

The reflector consumes those automatic events and existing Claim/Work corrections.
An LLM supplies extra feedback only for information the runtime does not have: a
chosen interpretation, unexplained deviation, relevant hypothesis or why advice
was unsuitable. The player can provide this once at a meaningful boundary. If
outcomes remain ambiguous, retain that ambiguity or request a targeted later
observation; never require a success/failure report to keep routine play moving.

A future procedure record is derived advisory memory linked to canonical episodes,
not a replacement transcript. Retrieval records its supplied version; selection
binds an instance to a goal; outcomes/counterexamples inform the next revision.
Retain sources and supersession so fresh player/reflector contexts reconstruct the
loop without the lead. Source support, applicability, outcome interpretation and
causal usefulness remain distinct. This instrumentation is proposed, not a claim
that current skill tools already link procedural-library IDs.

## Signals in both directions

Records should be assembled from existing receipts and source IDs, with concise
player interpretations where needed. Models should not transcribe raw wire JSON.
These are proposed semantic payloads, not a new accepted schema.

| Direction / signal | Payload and use |
| --- | --- |
| Active → reflection: episode or subgoal completed | Goal, actual action/result span, before/after sources, observed outcome, costs and unknowns. Include failures and corrections, not only successful endings. |
| Active → reflection: surprise or repeated non-progress | Intended versus observed effect, failure signature, attempts already made and current unresolved question. Self-rated uncertainty is a useful request, not calibrated evidence of error. |
| Runtime/player → reflection: reuse feedback | Automatically linked procedure ID/version, applicable goal instance, attempts/delivery/observations; add interpreted outcome, deviations and counterexamples only where needed. Separate candidate advice from an executed test and causal benefit from mere exposure. |
| Active → reflection: priorities and information needs | Next likely subgoal, plan version, relevant needs/remaining resources, evidence coverage and how soon advice could be useful. Do not continually overwrite an older unfinished learning obligation. |
| Reflection → active: procedure or plan-suffix candidate | ID/version/parent, goal/parameters, applicability and invalidation conditions, closed-loop steps, progress/termination, supporting and contrary sources, known limits and proposed next verification. Not a ready-to-replay key macro. |
| Reflection → active: correction, warning or retraction | Which claim/procedure/assumption is affected, source support, scope, priority and uncertainty. A high-priority warning requests reconsideration; it cannot grant authority or automatically replace the plan. |
| Reflection → active: proposed experiment or unanswered question | Distinguish missing observation from reasoning difficulty; request a minimal discriminating visible observation. No assertion that an unexecuted alternative would have succeeded. |
| Runtime/player → reflection: disposition | Automatic exposure, explicit selection, attempt and supported outcome records; optional player reasons for deferred/inapplicable/disputed advice. Absence of selection does not establish that advice was read or ignored. Unknown attribution remains unknown. |

A result retains the episode/evidence/plan/library versions it actually reviewed.
Do not stamp it with the newest frame ID. Recheck current applicability/dependencies
before use; a new revision alone need not invalidate a general procedure. A warning
about empty water is state-sensitive, whereas a scoped container-filling procedure
may remain useful after unrelated movement. Expiry and scoped invalidators differ
by advice type; model confidence alone does not set them.

## Eventual improvement, not first-attempt correctness

The contract should support propose → try → observe → revise/narrow/retire → reuse.
Early procedures may be incomplete or wrong. Preserve their lineage, contradictory
evidence, alternatives and unfinished learning questions. Failed reuse should make
a later attempt better informed, without an engineer repairing memory in between.
Separate whether a procedure is retrievable from how broadly its usefulness has
been established. One success is local evidence, not universal certification.

This is an empirical improvement objective, not a theorem that model advice will
converge to truth. CDDA is partially observed and changing; some hypotheses remain
unresolved. Database eventual consistency does not imply semantic correctness.
Permit persistent disagreement, narrowing, abstention and retirement. Ownership,
Pause, exact delivery/unknown accounting and current-input checks stay immediate;
we do not weaken those to tolerate eventually correct learned advice.

For example, a candidate from the water episodes might first describe a container
procedure too broadly. A frozen-water counterexample should narrow its applicability
and create an evidence question about treatment/thawing, not turn historical stock
into usable current water. A later applicable attempt supplies new evidence. This
is a proposed learning case drawn from retained failures, not a claim of a test.

## Scheduling, latency and failure cases

CDDA normally waits for input; a background learner reduces viewer/player waiting,
not a robot's required motor-control deadline. Engine activities can advance while
the model thinks, so current activity/obligation tracking remains on the active
path. Do not issue Wait or extra game inputs merely to appear busy during reflection.

Trigger learning on useful completed segments, repeated surprises, corrections,
reuse failures and likely upcoming work, plus bounded periodic coverage. Coalesce
redundant jobs while retaining their source coverage. Bound queue size, concurrent
calls, tokens/context, wall effort and retained output; record skipped/deferred work
and last-processed position. Prioritize likely useful unanswered questions and
prevent starvation of older important failures. No model call or reflection per key.

The hot path does not wait for routine reflection. It can continue meaningful work
supported by current evidence, or use direct interaction. If no justified next
action is available, it can deliberately request focused reasoning and hold the
affected decision. This is different from making every action wait. A silent or
failed reflector must not freeze ordinary input or silently erase pending learning.

| Failure case | Required behavior to design and exercise |
| --- | --- |
| Late advice uses an older plan or consumed resource | Keep its original basis; revalidate applicability, retain useful general content, reject stale instance advice. |
| Player corrects a claim while reflection is running | An item-version conflict prevents overwrite; preserve the proposal and request scoped reconsideration. |
| Two reflections disagree or a stored procedure fails | Preserve support/counterexamples and disputed status; neither arrival order nor repeated text establishes truth. |
| Pause, takeover, unknown delivery or worker crash | Current input rules remain independent; no reflector Resume/replay. Retain pending proposal/cost state without restoring authority. |
| Advice arrives during a long skill/activity | Surface relevant warning at the next possible decision boundary; retain local feedback/interrupt handling. Do not promise to undo committed effects or guarantee instantaneous model warning delivery. |
| Reflection floods or competes for model/CPU/context capacity | Bounded batching/backpressure and priority for active play; charge total resource cost and show backlog age. More concurrency can worsen latency. |

## Focused primary-source review

Cutoff: **2026-10-20, America/New_York**. Searched recent 2025–October2026 scholarly
sources and checked the existing project corpus; arXiv full text is the access path
below, with conference/index searches used for breadth. Selected PDFs and local
extraction/reading notes are retained project-locally. This is a scoped follow-up,
not an exhaustive SOTA survey or a renewal of existing research/control dates.
Relevant methods, evidence and limitations were read; the transfer column is our
engineering inference. Recent preprints remain provisional.

| Primary source / reading | Evidence and critique | Transfer to this project |
| --- | --- | --- |
| [RTC, Black et al.](https://arxiv.org/html/2506.07339v2), June2025 / Dec2025 revision; §§3–4,6 | Overlaps execution/inference while preserving committed action prefixes; tested in simulation and real manipulation. Limited to diffusion/flow policies and adds compute. | Respect already-executed prefixes and revalidate future work. CDDA does not need action inpainting or a continuous motor stream. |
| [Acting While Understanding](https://arxiv.org/html/2606.15285v1), June2026 preprint; §§3–5 | Separates slow semantics from fast action feedback. Its stale-cache ablation degrades; history/delay training recovers much of that loss. Fixed refresh may mislead under large semantic changes (the authors' stated limitation, not a refresh-interval ablation). | A fast path needs current observations and progress history; cached advice is insufficient. Internal trained VLA interfaces are not a drop-in text-agent design. |
| [Memory Beyond Recall / DCPM](https://arxiv.org/html/2606.09483v1), June2026 preprint; §§2–3.4 | Synchronous fact revision and asynchronous schema induction, with retrieval not requiring an LLM. Personalization/recall tasks; some baseline numbers are from public reports and supersedes can over-fire. | Keep raw evidence/revision history separate from slower abstraction. Its graph/clustering/intention machinery and conversational results do not establish game procedure learning. |
| [Grounding Agent Memory](https://arxiv.org/html/2609.11060v1), September2026 preprint; §§3–5, appendix accounting | Probes uncertain trajectory-derived memories with read-only environment tools. Tests database/document tasks. Curator finishes after a task and before the next, so it does not validate concurrent mid-task adaptation. Task-agent cost excludes separately tracked curation. | Reflection cannot recover never-observed evidence. Reopen retained sources; ask the active player for missing observations. CDDA look/menu probes require inputs and cannot be copied as reflector read-only world tools. Count both paths' costs. |
| [CONTRAMEM](https://arxiv.org/html/2608.22533v2), August2026 / September revision; methods, experiments, ablations and conclusion | Contrasts verified trajectories and locally curates function/skill cards; held-out app-agent evaluation freezes runtime memory. Over-broad cards cause regressions; authors explicitly retain temporal/state-monitoring limitations. | Keep counterexamples and bounded relevant procedures; memory does not replace unfinished Work or activity monitoring. This is not evidence of live concurrent consolidation or CDDA benefit. |
| [BenchTrace](https://arxiv.org/html/2605.29225v1), May2026 preprint; §§3.3–4.3 and limitations | Separates failure detection/localization/diagnosis from later avoidance. Its tested models show weak diagnosis, forgetting and negative transfer. Controlled snapshots and fallible annotations limit generalization. | Score diagnosis and actual later behavior separately; a convincing reflection or model agreement is not success. Do not infer current model rankings from this study. |
| [Sleep-time Compute](https://arxiv.org/html/2504.13171v1), April2025; §§3–7 | Precomputes reusable context for later queries; benefits depend on predictable questions. Assumes a context/query split; SWE case uses file-set overlap rather than functional correctness and loses advantage at high online budgets. | Use likely next subgoals to prioritize useful work, but compare total compute and useless/stale suggestions. Background work is not free or universally better. |

## Delivery and evaluation

Keep #176 input work and the original #144 independent mission outcome intact.
Design the bounded exchange/procedure-data slice with [#178](https://github.com/CVX-Hull/enactive/issues/178)
under #177; #146 separately asks
whether another curator model earns its cost. The minimum functional experiment
uses one existing deciding player and a bounded advisory worker, no new provider
spend, training, graph service or mandatory per-action approval. It must show actual
player-authored/derived reuse, a counterexample-driven revision, fresh-context
retrieval and continued useful play while nonurgent reflection is outstanding.
Software owns orchestration; lead tactical assistance invalidates independence.

Test stale advice, corrections during generation, worker absence, queue overload,
Pause, unknown delivery and exposure/selection/effect-attribution distinctions before
live adoption. Compare no-extra-reflector and
bounded-reflection conditions at matched declared resource limits, including
reflection/retrieval/tool delay and failures. Development replay can check extraction
or interface behavior, not counterfactual survival after a divergent action.
Meaningful functional delivery and causal efficacy claims retain separate gates.
Measure repeat-failure rates, inappropriate reuse, retention/transfer, useful game
progress, player/reflector/context costs, critical-path delay and interventions;
report unmeasurable model usage as unknown. No convergence or speedup is claimed.

At meaningful integration/maintenance checkpoints, review whether the exchange
helped enough to justify its complexity and cost. Reuse current Issues/Project,
C-REVIEW and maintenance triggers; no new ceremony or date reset. If simple local
reasoning/procedure retrieval suffices, an always-running reflector may be deferred.
