---
owner: lead
status: historical
date: 2026-10-29
scope: Pre-cutover background archived on this date; not current executable policy or new research qualification
review_trigger: Player-owned mission design; new relevant memory evidence; observer, engine or model changes; false-memory incidents; issue 26 research review
---

# Memory and gameplay architecture assessment

This is retained pre-cutover design/research evidence. Its old executable routes and
semantic authority are retired. The [current computer/player contract](contracts/computer-control.md) owns implemented behavior;
this page supplies background, not current operating instructions.


Assessed **2026-10-19, America/New_York**, against source `c58ee0a` and the first
seven-day run. This is a research assessment and proposed direction, **not an
implemented memory system or a new gameplay admission**. [Architecture](architecture.md)
and [protocol](protocol.md) remain the current contracts.

A [focused October20 follow-up](design/asynchronous-reflection.md) assesses active
play versus background reflection, automatic feedback and eventual revision. It
adds scoped research/design questions without renewing this assessment or claiming
a deployed learner.

## Decision for the owner

**Change the integration and lifetime of memory, while keeping the guarded execution
boundary.** The existing task memory is a useful bounded component, but it is not
the durable memory used by the campaign player. A better retriever alone would
not repair the actual run's mistaken interpretations or unfinished-work tracking.

The proposed next system has one player owning planning, memory use, semantic
skills, recovery and normal lifecycle within a finite mission. Retained evidence
feeds two compact views: **what is supported or uncertain**, and **what work is
underway or still owed**. The player's conversation and summaries are replaceable
views. An optional curator advises; it does not approve ordinary moves or become
the source of truth. No new model tier, graph service or training stack is justified.

Start with [design #137](https://github.com/CVX-Hull/enactive/issues/137) and the
bounded [trace/label pilot #71](https://github.com/CVX-Hull/enactive/issues/71).
The [player-owned outcome #136](https://github.com/CVX-Hull/enactive/issues/136)
already owns delivery; this assessment sharpens it rather than creating a second roadmap.

## What the assessed baseline did

This section describes the dated c58ee0a baseline above, not the current mission
API. Use [current architecture](architecture.md) for migrated behavior.

| Boundary | Verified current behavior | Consequence for the next architecture |
| --- | --- | --- |
| Campaign player | External operator using ordinary CLI/controller calls; lead still owns segment admissions, lifecycle and exceptional handling | The seven-day result is supervised development evidence, not end-to-end player autonomy |
| Waypoint service | `GameplayRuntime._start` creates only a cardinal waypoint-return task, distance 1–4; `WaypointSupervisor` coordinates its planning and steps | Do not stretch a round-trip task into a general campaign by accumulating special cases |
| Task memory | `TaskMemory` is task/store-bound, in-process, with separate facts, interpretations, hypotheses, plans and procedure references; restart does not reconstruct it | Durable campaign continuity is a new lifecycle boundary, not merely a larger capacity setting |
| Actual planner input | Supervisor supplies current facts and an empty interpretations tuple; runtime callers do not populate interpret/hypothesize/procedure methods | Having types is not an integrated retrieval/learning capability |
| Evidence hot set | `EvidenceStore` persists original PNGs/metadata, but accepts positively marked normal play only; 32 frames/64 MiB, no silent eviction | Useful for the short execution path; cannot alone represent menus, activities and an entire campaign |
| Facts and authority | Extracted facts are position, turn and visible-creature count. A belief's `valid` checks retained support, not semantic truth. Current-input freshness is separate | Preserve exact guards; do not mistake an authentic screenshot or source-linked interpretation for a correct current-state claim |
| Outcome monitoring | The general monitor is a proposed design; executable skills currently accept cardinal movement | Implement the first semantic families through the shared monitor/skill contract, not a second competing monitor |

Code anchors: [baseline runtime start](https://github.com/CVX-Hull/enactive/blob/c58ee0a1a31c5ab072edf4397cc76b677a311364/harness/runtime.py), [supervisor packet construction](https://github.com/CVX-Hull/enactive/blob/433ed973afe312d03f777d8b102a0cba528af746/harness/gameplay/supervisor.py),
[task memory](https://github.com/CVX-Hull/enactive/blob/433ed973afe312d03f777d8b102a0cba528af746/harness/gameplay/memory.py), [evidence validation/facts](https://github.com/CVX-Hull/enactive/blob/433ed973afe312d03f777d8b102a0cba528af746/harness/gameplay/evidence.py),
[skill registry](https://github.com/CVX-Hull/enactive/blob/433ed973afe312d03f777d8b102a0cba528af746/harness/gameplay/skills.py). Relevant functions are `_start`,
`_submit_or_verify`, `TaskMemory.refresh`, `_validate_observation` and `EvidenceStore.historical_facts`;
source navigation must use actual names when these change. The current
[operator contract](contracts/mission-admission.md#designated-campaign-operator),
[passive memory](contracts/injected-planner.md#passive-task-memory) and
[monitor proposal](design/outcome-monitoring.md) distinguish these scopes.

## What the earlier research and real run change

The [October 18 review](research-memory-learning.md) already included October14–15
papers. Its main recommendation survives: retain evidence, separate state from
lessons, use simple baselines and evaluate changes. This refresh adds missed
papers and tests the recommendation against real campaign failures; a one-day
change in the review date is not evidence of a new SOTA.

The [representation study](acceptance/2026-10-18-memory-representations.md) tested
specified algorithms with supplied context tags and synthetic feedback. Its
replay/cache, duplicate-evidence, compression and drift results remain useful
counterexamples. They do not measure screenshot extraction, autonomous policy
learning or native survival. The source-lineage counterexample is especially
relevant: keeping the latest citation did not guarantee keeping its meaning.
The migration-related protocol-hash clarification in that report preserves the
original results and identifies the sanitized historical source.

The real [campaign](acceptance/2026-10-19-seven-day-survival.md) and
[water treatment](acceptance/2026-10-19-water-coverage.md) show why:

- A lead's wrong southeast correction displaced an actual SOUTHWEST observation.
- An AND requirement for tool qualities became OR, despite source review.
- A wrong sleep condition/rate survived the first review and affected a hold.
- One craft continued across heat interruptions; reserved ingredients, unfinished
  output, available containers and actual finished water had different meanings.
- Later observations established some effects after acknowledgment timeouts;
  they did not retroactively turn the original receipts into acknowledged actions.

These are failures of interpretation, revision, resource/work tracking and outcome
attribution. An extra critic or a graph would not automatically fix them. The run
also included lead assistance, revised admissions and unknown model costs; it is
not a causal comparison of memory methods.

## Proposed responsibilities and feedback

Reader question: **how does the player remember and act without the lead becoming
a routine gameplay dependency?** This is a proposed logical view; participants are not
new processes, databases or model tiers.

![Proposed player-owned memory and gameplay loop, with source-linked views, semantic skills, current guards and optional reviewed improvement.](diagrams/player-owned-memory.svg)

Solid arrows show requests or updates; dashed arrows return observations or results.
Notes mark the user control and optional improvement boundaries. Text equivalent: retain visible observations and
outcomes; rebuild scoped state/work views; supply a bounded relevant packet to
the player; execute a semantic skill through the existing current-input gate;
assess the observed result and replan. User Pause/takeover wins. Optional curation
proposes evidence-linked lessons; reusable library changes are separately tested
and reviewed. There is no memory-to-controller permission edge.
[Editable source](diagrams/player-owned-memory.mmd).

### Necessary architecture changes

1. **One mission integration path.** Define mission objective, remaining resources,
   active plan/skill and ending conditions independently of the current waypoint
   shape. Reuse the controller lease, receipts and evidence identities. Coordinate
   the campaign operator and service into one admitted execution path; retain
   waypoint-return as a scenario/skill where useful, not a second general player
   runtime. Registered normal lifecycle operations belong to this path. A restart
   reconstructs advisory state, never a lease, queued action or automatic Resume.

2. **One retained evidence basis, with bounded execution and campaign views.** Reuse
   journals, original frames and their IDs; do not create another raw game log.
   Specify retention/source access for menu, activity and recovery observations as
   well as normal play. Preserve the small execution hot set and its guards until
   an explicit coordinated change. A durable campaign index references canonical
   artifacts; projections and summaries can be rebuilt. Storage existence is not
   semantic support or current execution eligibility.

3. **Explicit state revision and coverage.** Claims need source/derivation, observed
   time when known, receipt time, campaign/session/coordinate scope, and support,
   contradiction or correction status. Attach inspected region/container/menu
   coverage when making absence claims. Keep historical truth, current
   applicability, source integrity and interpretation quality distinct. Correcting
   a misread prerequisite must invalidate dependent advice without disputing the
   original PNG. Preserve independent surviving support; start with bounded lists
   and replay, not a general truth-maintenance engine.

4. **Progress and obligations, not only facts.** Keep a bounded skill/activity
   instance: intended target, last observed stage/progress, interrupted state,
   quantities committed versus available, unresolved effects and next verification.
   Do not invent engine activity identity where the observer cannot establish it;
   record an uncertain association. Separate predicted duration from measured game
   time. Unknown action delivery is reconciled, never automatically replayed.

5. **Query-specific context at meaningful boundaries.** Retrieve at subgoal/skill
   selection, material change, unexpected outcome and context replacement; preserve
   the IDs and version actually supplied. Hard guards still run per primitive.
   Select facts, pending work, applicable procedures and counterexamples within a
   budget; permit no relevant memory and a specific next observation. Measure packet
   size/order and source-inspection cost before adding embeddings or a composer.

6. **Player-local adaptation without live code changes.** The player may revise
   campaign facts and provisional, scoped tactics under the admitted policy.
   Such ordinary reasoning does not require a PR or critic approval. It cannot
   change executable skill code, guards, budgets or user Pause. Candidate general
   lessons retain counterexamples and evidence; promotion to the reusable library
   is a separate evaluated change. For assessment, freeze the implementation,
   library and update policy prospectively; declare which memory contents may
   evolve. This clarifies the earlier review's combined wording about planning
   instructions and executable skills.

7. **An inspectable player session.** Show objective, active skill, partial progress,
   unresolved effects, memories used and intervention reason. Expose relevant source
   frames, not an overwhelming transcript. The player owns ordinary replanning and
   permitted recovery; missing observations, interpretation difficulty, resource
   contradiction and authority loss need different remedies. A stronger model is
   useful only when the missing ingredient is reasoning and the added cost fits.

The logical objects are **mission** (objective/limits), **plan** (revocable proposed
work), **skill instance** (bounded closed-loop execution), **episode/evidence**
(what was observed/attempted), **claim/current view** (fallible scoped understanding),
and **lesson candidate/library** (experience-derived reusable guidance). Sharing
references does not make these one object. Their exact schemas and migration
remain #137's design work, not contracts invented by this review.

## Primary-source update and limits

Targeted primary reading used arXiv full texts, proceedings/author papers and
maintained official documentation. Six independent lenses covered source paths,
prior evidence, new memory methods, evaluation and adjacent disciplines. The lead
checked decisive methods/limitations and caller integration. A clean-context
reviewer verified the implementation/proposal boundaries, selected primary claims
and the historical hash correction; it did not independently reread every paper. This is not an exhaustive systematic review or benchmark
replication. Selected public papers, official snapshots and extraction manifests
remain project-local under `.runtime/research/memory-architecture-2026-10-19/`;
layout-text extraction was checked against primary HTML for decisive passages.
Downloading/extracting a source is not evidence of reading it. AiO-Mem and the
multimodal survey were catalogued but are not adopted method evidence here.
Read scope below means methods, evaluation and limitations; numerical
results are not imported as CDDA forecasts. Recent preprints remain preliminary.

| Source / pinned version | Evidence and limitation | Consequence here |
| --- | --- | --- |
| Zhang et al., [Useful Memories Become Faulty](https://arxiv.org/html/2605.12978v2), May13 / Aug29 2026; lead full-text check | Repeated lesson rewriting can degrade tested agents even with useful source trajectories; episodic-only controls are competitive. Particular tasks/models/update schedules, not a universal law against abstraction | Preserve episodes; compare against no consolidation; do not rewrite a master narrative after every action |
| Xie et al., [MemComposer](https://arxiv.org/html/2610.21091v1), Oct15 2026; lead + research review | Learns selection/count/order through downstream rollouts with frozen executors/bank. Composer itself is trained; service domains and small executors limit transfer | Context assembly is a distinct decision; test simple packet policies before trained assembly |
| Li et al., [MemCode](https://arxiv.org/html/2610.19472v1), Oct14 2026; lead + research review | Atomic source-linked units and a trained codebook improve tested conversational retrieval. Temporal detail can be lost; planning/tool-use deployment is outside scope | Keep source reconstruction and time; defer codebook/embedding stack without a demonstrated retrieval gap |
| Yehia et al., [Mem++](https://arxiv.org/html/2610.02002v1), Oct1 2026; research review | Preserves whole documents with read-time lexical/dense selection; extra consolidation/graph variants do not consistently help. Strong vector contribution and small synthetic organizational benchmark | Preservation-first comparison, not proof lexical lookup is always sufficient |
| Fan et al., [StateMem](https://arxiv.org/html/2608.19652v1), Aug20 2026; lead + research review | State supersession/recomputation differs from relevant retrieval. Synthetic short histories, small/mid backbones and expensive encoding; dependency propagation can over-invalidate | Test stale derived plans and legitimate non-updates; do not adopt a general dependency engine |
| Toma et al., [Beyond Downstream QA / FEB-30](https://arxiv.org/html/2610.22209v1), Oct15 2026; lead + research review | Checks stored state as well as QA. Thirty synthetic trajectories, related pipeline configurations, embedding/LLM scoring | Diagnose extraction, revision, retrieval and use separately; correct answers can conceal broken memory |
| [MemoryArena](https://arxiv.org/html/2602.16313v2), Feb18 / Sep17 2026; lead + evaluation review | Successive action tasks depend on earlier subtasks; memory resets between evaluation episodes. Domain/backbone-reporting limits prevent universal ranking | Use dependent mission stages and score final success separately from progress |
| [EmbodiedMemory-Bench](https://arxiv.org/html/2609.28236v1), Sep23 2026; evaluation review | Supplied histories lead to environment actions; cue ablations expose memory use. Simulation/reset access and differing text/image context baselines matter | Test decisive evidence and repeated failures, then real native action outcomes |
| [WorldMemArena](https://arxiv.org/html/2605.29341v2), May28 / Jun1 2026; evaluation review | Separates write/maintenance/retrieval/use diagnostics, but evaluated checkpoint QA over supplied histories; dataset counts vary across descriptions | Useful trace diagnosis, not evidence of improved closed-loop survival |
| [AuthMem-Bench](https://arxiv.org/html/2608.01679v2), Aug3 / Aug4 2026; evaluation review | Paired same-claim/different-source-authority cases measure downstream tool authorization. Clustered constructions, judges and complete bounded retrieval limit guarantees | Preserve source role/permitted use; remembered text cannot grant authority |
| [AgeMem](https://arxiv.org/html/2601.01885v3), Jan5 / Jul23 2026, [ACL2026](https://aclanthology.org/2026.acl-long.981/); research review | Memory tools are optimized through parameter training; controlled environments and partly judged quality | Borrow operation taxonomy, not a presumed drop-in frozen-player policy |
| [MemRL](https://arxiv.org/html/2601.03192v2), Jan6 / Feb12 2026; research review | Frozen-weight retrieval utilities use observed returns; credit assignment and stationarity assumptions are material | A useful retrieval score is neither causal credit nor belief probability |
| [ACE](https://arxiv.org/html/2510.04618v3), Oct2025 / Mar29 2026, ICLR2026; research review | Itemized playbook edits avoid whole-context rewriting in tested tasks; unreliable feedback can still cause regressions | Local candidate edits and evidence access, not mandatory curator calls or automatic lesson truth |
| [DynaMem](https://arxiv.org/html/2411.04999v2), Nov2024 / May29 2025; adjacent review | Removes obsolete geometry only with newly observed free-space evidence; calibrated poses/depth do not exist in our observer | Transfer the coverage condition, not a voxel map or geometric guarantee |
| [MEM](https://arxiv.org/html/2603.03596v2), Mar4 / Mar8 2026; adjacent review | Recent visual context plus semantic progress helps a trained VLA; correction data/training required, some failed attempts omitted from compact memory | Separate recent evidence/progress views; retain failures in the archive regardless of summary omissions |

The earlier [mathematical review](research-memory-representations.md#one-problem-six-useful-views)
still supplies the assumptions for POMDPs, provenance, subjective logic, temporal
records, selective prediction and off-policy evaluation. A prose ledger is not a
Bayesian sufficient statistic; repeated reviewers are not independent evidence;
selected action logs do not identify untried policy outcomes. None needs a new
numeric confidence calculus for the first delivery.

## Reuse and maintenance decision

Prefer existing artifacts plus ordinary queries. [SQLite views](https://www.sqlite.org/lang_createview.html),
[transactions](https://www.sqlite.org/lang_transaction.html) and [FTS5](https://www.sqlite.org/fts5.html)
are a candidate for a local disposable index and scoped claims/work rows. An
in-memory probe of the existing project Python3.14.7 / SQLite3.53.4 confirmed FTS5
availability on this Mac without installing anything. This is a capability check,
not a backend selection or performance result; compare with direct JSON/exact
replay and verify the delivery runtime before selection.
SQL can atomically update local records, **not** transact CDDA dispatch plus ACK;
crash recovery cannot become an outbox retry of unknown game effects.

[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
provides thread checkpoints and cross-thread stores; it does not supply our
source truth, native unknown-effect semantics or renewed execution authority.
[Letta](https://github.com/letta-ai/letta) is a stateful-agent platform and
[Mem0](https://github.com/mem0ai/mem0) a memory integration stack. Adopting either
would add extraction/provider/storage policy and integration ownership. Their
existence is a reuse option, not evidence that replacing our controller/runtime
is cheaper. [LangMem](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)
may supply bounded extraction/offline functions without a full runtime migration;
assess only against a demonstrated task. No library is selected or installed here.

Keep one writer for each campaign index; preserve source/retention dispositions,
strict current schema and rebuild checks. Git owns source/skill/prompt history,
the engine owns its real activities and the controller owns dispatch. No custom
VCS, event-sourcing service, universal world simulator or second actor registry.
Any implementation migrates affected producers, consumers and persisted formats
together and removes the obsolete paths under S-MIGRATION.

## Validation and existing work ownership

The bounded #71 pilot remains at most three episodes and 5–10 questions, not the
entire matrix below. Select real cases first and route uncovered cases to the
existing delivery/research issues. Test what evidence supports, including a useful
next verification, rather than supplying invented ground truth.

| Required diagnostic | Expected behavior / owner |
| --- | --- |
| Wrong advice with intact source; shared-origin reviewer repetition | Preserve original; correct interpretation; exclude dependent advice unless alternative support survives. #71/#140/#146 |
| Bottle absent from one page, old stock after consumption, delayed older observation | Distinguish partial coverage, historical possession and new current support; receipt order is not world time. #139/#140 |
| Interrupted same craft, committed ingredients, actual output versus forecast | Track work association/progress/obligations without double-counting or treating unfinished output as stock. #139/#140/#141 |
| Reload and identical relative coordinates | Rehydrate advisory state; keep coordinate scopes separate until legitimate visible relocalization. Never restore lease/queue. #137/#140/#142 |
| Lost acknowledgment and apparently unchanged screen | Keep unknown delivery separate from separately observed effects; no blind replay. #140/#141/#142 |
| Relevant memory retrieved, but stale or wrong operation | Exact eligibility/counterexample checks before relevance; permit no useful result and costed reobservation. #138/#140/#141 |
| Context replacement and dependency across mission stages | Player resumes objective, pending work and sources without engineering repair; semantic intents reduce model/tool decisions, while primitive guards remain. #142/#143/#144 |

Evaluate four distinct layers: retained evidence fidelity; extraction/current-state
revision; usefulness for a proposed decision; actual native execution utility.
Use current packet, permitted visible history, exact scoped replay and selected
lessons as baselines. Diagnostic supplied-evidence/cue-removal fixtures stay
offline; altered history is never supplied as real gameplay evidence. Charge
unnecessary abstention, source reopening, recovery and curator effort as well as
wrong accepted answers. Record external usage that cannot be measured as unknown.

A recorded prefix can support answer/decision diagnostics. Once candidate actions
diverge, the recorded later observations are not their consequences. Split by
independent campaign when available; adjacent windows of one campaign are
correlated development cases. The next integrated mission validates continuity
and functional autonomy; broader memory/curator/learning benefit remains #70,
#24/#44 and conditional #27, with matched budgets and frozen reusable versions.
Do not inflate the synthetic study's row count into independent gameplay trials.

#137 owns schema/authority/interface decisions; #138/#139 semantic skills; #140
campaign memory; #141 outcome/recovery; #142 mission/lifecycle; #143 observer and
cost visibility; #144 integrated acceptance; #145 fresh seven-day assessment;
#146 optional curator. #75 owns the documentary provenance/stale-status findings
and control burden; #26 owns research currency. Detailed work remains in
[GitHub](https://github.com/CVX-Hull/enactive/issues/136), not a parallel task list.
The October24 research and January15 maintenance dates and earlier event triggers
are unchanged. Revisit the selected design on new relevant evidence or failure;
this review does not renew a due date or complete #137's implementation briefs.
