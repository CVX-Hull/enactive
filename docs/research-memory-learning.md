---
owner: lead
status: proposed
review_trigger: Before memory or learning implementation; new relevant evidence, model or observer changes, false-memory incidents; active research review under issue 26
---

# Gameplay memory and learning from experience

Research cutoff: **2026-10-18**. This is an evidence review and discussion proposal,
not an implemented contract or a commitment to training. The current
[protocol](protocol.md#passive-task-memory) remains authoritative. No gameplay,
weight training, model service, database installation or paid API experiment was
performed for this review.

## Recommendation and decision boundary

Build toward an agent that **remembers evidence, revises its understanding, and
improves through evaluated changes**. Keep those three responsibilities distinct.
Start with recoverable episode records and a small, task-relevant handoff packet;
then test whether retrieving scoped lessons helps actual gameplay. A persistent
player sub-agent can maintain working context, but durable memory must remain
inspectable outside its conversation.

Use automatic observation ingestion and explicit belief revision during play.
Treat generalized lessons as candidates with applicability conditions and
counterexamples. Promote changes to reusable planning instructions or executable
skills through versioned evaluation and the existing engineering review. Do not
make every ordinary observation wait for human approval. Reserve owner attention
for changed guarantees, material tradeoffs and resources; the lead can review
routine changes within the authorized scope.

This recommendation is our engineering inference. No reviewed paper demonstrates
CDDA survival improvements or establishes a universally best memory architecture.
The immediate evaluation-readiness work remains useful; this review does not
silently expand its scope or change the live GitHub priorities.

## What exists, and what is missing

The implemented [TaskMemory](../harness/gameplay/memory.py) is passive, bounded,
in-process and scoped to one immutable task and EvidenceStore. It distinguishes
source facts, interpretations, hypotheses, plans, procedure references and action
outcomes. Source disputes invalidate dependent records; snapshots are explicitly
as-of their clocks. It does not silently evict records, dispatch inputs, infer
completion or restore memory/leases after restart. A belief's `valid` flag means
its sources remain retained; it does **not** validate the proposition.

There is no durable cross-episode retrieval/consolidation service, learned world
model, learned skill library or continual-training pipeline. The
[evaluation recorder](evaluation.md) records supplied events and judgments; it
does not judge success or automatically measure external Codex planning.

Current visible telemetry supplies relative avatar position and adjacent clear
terrain/furniture. It does not export inventory contents, absolute world position,
unseen creatures or traps. The session changes on world entry/exit and same-process
save/reload. Consequently, current coordinates cannot align a durable map across
reloads. Remember historical observations without presenting them as fresh state;
keep session maps separate until a legitimate visible relocalization and identity
contract exists. No save inspection is an acceptable shortcut.

## Research method and limits

Six read-only sweeps covered agent memory, continual learning, embodied systems,
mathematical foundations, evaluation risks and the current implementation. The lead
checked decisive primary methods/results and requested deeper reading where an
initial result was only discovery-level. A separate clean-context reviewer checked
the CDDA transfer and authority boundaries.

Searches prioritized 2026, late 2025 and the October 11–18 window, then expanded to
foundations. Sources included arXiv, ACL/ICLR/ICML proceedings and author/official
software documentation. This is a targeted review, not an exhaustive systematic
review. New preprints may be unreplicated. No benchmark was reproduced locally.
Read depth below is more important than paper count or the word “self-improving.”

A project-local corpus under `.runtime/research/memory-learning/` retains source
URLs, downloads and extraction metadata. Sixteen of eighteen selected artifacts
were downloaded; a self-correction HTML revision returned 404 and the subjective
logic mirror returned 403. Their primary text was read through the web reader;
local download failure is not a claim that a PDF was archived. Initial sandbox DNS
failures are retained. Extracted HTML/PDF text is flattened; mathematical claims
were checked against the paper's web-rendered text, rather than inferred from
flattened tables alone. Discovery sources are explicitly excluded from stronger
claims below.

## Decisive evidence

| Primary source / date and read depth | Finding, limits and consequence |
| --- | --- |
| [STRATA](https://arxiv.org/html/2610.19386v1), Oct 14, 2026 preprint; methods, experiments, ablations and appendix | Separates atomic procedures, workflows and abstractions; handles confusable opposite operations and bounded memory. Four interactive benchmarks, two frozen backbones, three seeds. Promising support for typed applicability and counterexamples, not a reason to adopt its full graph/community-detection stack. Its environment outcomes are stronger feedback than many uncertain CDDA observations. |
| [MemScope](https://arxiv.org/html/2610.21170v1), Oct 15, 2026 preprint; methods/results/limitations | Localizes memory-provider code repairs using traces, patches and manifests, retaining regression history. Different cloud-model task suites and limited snapshots. Supports investigating a concrete defect before changing architecture; does not validate live self-modification or prove a patch generalizes. |
| [Beyond Memory / PoS](https://arxiv.org/html/2610.01415v1), Oct 1, 2026 preprint; §§3–4 and Appendix G | Maintains task-relevant world estimates plus knowledge and achievement gaps; audits candidate updates and diagnoses stagnation/recurrence. Four benchmarks and three backbones. Its health score is heuristic, not a calibrated posterior; maintenance costs and semantic distortion remain. Useful distinction between needing information and needing a different action. |
| [When Continual Learning Moves to Memory](https://arxiv.org/html/2604.27003v1), Apr 29, 2026 preprint; framework, experiments and appendix | Frozen-model ALFWorld/BabyAI sequences expose retrieval interference: stored experience can damage new tasks or earlier competence. Abstract insights often transfer more safely than raw trajectories, but not universally. Two task pairs and a particular memory/backbone setup limit generalization. Measure forward transfer and retention, not just a rising total memory count. |
| [EMemBench](https://arxiv.org/pdf/2601.16690), 2026; full methods/results/limits | Trajectory-conditioned game-memory questions in Jericho/Crafter; controlled exposure separates memory quality from which history an agent happened to collect. Visual/spatial and induction weaknesses persist; adding memory has mixed results. Ground truth uses game state: borrow only questions answerable from our player-visible evidence. Recall QA alone cannot establish improved action. |
| [Memora](https://aclanthology.org/2026.findings-acl.1337/), Findings of ACL 2026; full paper/error analysis | Tests obsolete and invalidated memories over long conversational histories. Stale reuse and incomplete retrieval matter alongside recall. Personalization is a different domain; transfer its update/forgetting test dimensions, not reported scores. |
| [HiMe](https://proceedings.mlr.press/v306/ji26k.html), ICML 2026; [full text](https://arxiv.org/html/2607.03449v1), methods/results/limits | Working visual context, episodic memory and event-triggered planning beat tested alternatives on three purpose-built robot tasks, 20 trials/task/method. Its learned sentry still misses completions; progress and success are not interchangeable. No matched standard simulation benchmark or long deployment validation. Borrow multimodal evidence and event boundaries; retain our exact per-primitive guards. |
| [ProactiveVLA](https://arxiv.org/html/2610.06999v1), Oct 4, 2026 preprint; §§3–6 and prompts | Frozen VLA, budgeted exploration, visual checks and evidence-reviewed consolidation; memories frozen for evaluation. LIBERO-Pro and simulated RoboCasa Composite-Seen. Visual judges remain fallible; seen task classes and unequal baseline coverage matter. Supports bounded information-seeking experiments, not exploratory risk to a preserved character or automatic rule truth. |
| [Evo-Memory](https://arxiv.org/html/2511.20857v2), Nov 2025 / May 2026 revision; method, experiments and compute/limitations appendices | Sequential retrieval, action and memory refinement, including four interactive environments and supplied correctness feedback. Fixed budgets but substantial aggregate API expenditure. Supports streaming comparisons; its feedback and textual tasks do not solve partial-observation CDDA outcome labeling. |
| [GEPA](https://arxiv.org/pdf/2507.19457v2), Feb 2026 revision, ICLR 2026; method/algorithm/experiments | Optimizes prompts with frozen weights, execution feedback, candidate ancestry and per-instance Pareto selection. Separate feedback/selection data and final held-out tests; validation consumes many rollouts. A candidate for offline optimization after an affordable evaluator exists. Its Pareto scheme is across task-instance scores, not an automatic safety/cost preference policy. |
| [Reflexion](https://arxiv.org/abs/2303.11366), NeurIPS 2023; full methods/limits, and [intrinsic self-correction study](https://arxiv.org/html/2310.01798), ICLR 2024; experiments/oracle analysis | External feedback can enable useful reflection; self-generated tests can falsely label success. Intrinsic answer criticism can hurt, and prior gains can depend on oracle correctness labels. These older task/model results are cautions, not a claim that current models cannot improve. Compare against equal inference budget and grounded feedback. |
| [Hidden in Memory](https://arxiv.org/html/2605.15338v2), May 2026 preprint; methods/results/judge and threat-model limits | Tests delayed poisoning through write, retrieve and action stages. Partial visibility into provider pipelines and model judges limit conclusions. Demonstrates a failure class, not a CDDA incidence estimate. Treat remembered game text as data; reject attempts to change authority or policy through it. |

Additional read sources: [EmbodiedMemory-Bench](https://arxiv.org/pdf/2609.28236)
(2026 simulation memory-to-action tasks), [MemGym](https://arxiv.org/pdf/2605.20833)
(2026 mixed tool/research/coding/computer-use memory tasks),
[MemoryVLA](https://arxiv.org/html/2508.19236) (trained latent robot memory), and
[PAST-Bench](https://arxiv.org/abs/2608.04003) (2026 capability/pathway evaluation).
They reinforce evaluating memory use separately from retention and matching the
observation/action interface. Trained robot embedding/action policies are not
reusable CDDA controllers. Discovery-only leads, not adopted evidence:
[MemCode](https://arxiv.org/abs/2610.19472) (Oct 14),
[MemComposer](https://arxiv.org/abs/2610.21091) (Oct 15),
[WorldMemArena](https://arxiv.org/abs/2605.29341), and MemoryVLA++.

## Proposed memory responsibilities

These are logical views over shared records, not a requirement for six services,
databases or models. Storage of a claim and permission to rely on it are different.

| View | Content and example | Lifetime / limits |
| --- | --- | --- |
| Working context | Current objective, next bounded stage, recent observations, unresolved effects, remaining budgets | Small current packet; observation freshness and lease always rechecked |
| Episodic history | What was seen, proposed, attempted and observed afterward; failed/uncertain attempts too | Durable only under explicit retention; source IDs and dispositions survive summarization |
| World belief / spatial view | Last-seen object/location/state and competing interpretations | Scope to session/visible coordinate frame; unseen means unknown, absence requires adequate visibility |
| Mechanics knowledge | Version-scoped claims about how interactions work, with exceptions and tests | Separate upstream documentation from experience-derived hypotheses; invalidate on relevant engine/content/config changes |
| Procedural library | Reusable planning tactics, applicability, stops and known failure modes | A remembered tactic is advisory; executable skill code remains reviewed/versioned with current contracts |
| Learning record | Which lesson/prompt/skill changed, why, evaluation results and regressions | Auditable candidate ancestry and active version; never silently promote a successful anecdote |

A raw event remains an event: “the step reached the requested coordinate, then the
next-tile cupboard check stopped the task.” A possible lesson is “the current
final-leg check may stop after reaching a waypoint.” Neither supports “all
cupboards are impassable in every situation” or “ignore the guard.” Existing
[#53](https://github.com/CVX-Hull/cdda-player/issues/53) owns that policy review.
A good learning system can attribute a failure to its harness, observation coverage,
planner, executor or evaluator instead of calling every stopped task a model error.

For a future claim record, distinguish: source integrity; observed-at time and
as-of assessment; world/coordinate and engine/config scope; observed/inferred type;
support and contradiction links; applicability; status; derivation/version.
A fresh authentic screenshot can still support an ambiguous interpretation.
A historical fact remains historically true when its current-state projection
becomes stale. Do not overwrite history to resolve a changed state.

For owner review, a future spectator disclosure should show the current objective,
what the player knows versus last saw or suspects, the few memories influencing
its next proposal, and the reason/evidence for a changed lesson. Link a concise
lesson card to its source frames, exceptions and evaluation version. A memory
counter or a long transcript cannot answer these questions. This is proposed UI,
not a claim about the current spectator.

## Retrieval, consolidation and forgetting

Filter by permitted source, task and world/version scope before semantic ranking.
Retrieve compact relevant lessons, counterexamples and source pointers, with a
bounded route to inspect actual frames. A rule about opening a door must not be
retrieved as instructions to close one merely because their words are similar.
Allow “no relevant memory.” Record what was retrieved and actually used so a
successful run is not automatically credited to learning.

Consolidation should propose a short claim with conditions, supporting episodes,
known exceptions and unresolved attribution. Keep detailed raw traces available
within retention limits, but do not inject every trace into every decision. Exact
visible event records may be retained automatically; generalized lessons remain
fallible. An episode's failure may reveal a useful counterexample even when its
causal explanation remains unresolved.

Keep three operations distinct: omit from current context, retire from active
retrieval, and delete underlying evidence. Retiring an entry needs a reason and
replacement/tombstone so a later consolidation cannot resurrect it. Expired or
missing evidence changes the record's evidence availability; it cannot masquerade
as a fully verifiable lesson. Deduplication must preserve shared origins and
contradictions. These proposals must fit the current 32-source bounded evidence
store; a durable archive is a new boundary with explicit retention/retrieval
limits, not permission to silently enlarge TaskMemory or evict its dependencies.

Prefer an existing relational store and ordinary queries for the first index.
[SQLite FTS5](https://www.sqlite.org/fts5.html) supplies local full-text search and
BM25; application tables would still own typing, scope and validity. Verify FTS5
availability in the pinned runtime before selecting it. Evaluate embeddings only
if lexical/tag lookup misses relevant lessons in representative traces.
[LanceDB](https://docs.lancedb.com/quickstart),
[Qdrant](https://qdrant.tech/documentation/quickstart/),
[Mem0](https://github.com/mem0ai/mem0),
[Letta](https://github.com/letta-ai/letta) and
[LangGraph memory](https://docs.langchain.com/oss/python/langgraph/add-memory)
were screened in official documentation. They offer reusable capabilities but
vary from search components to whole agent runtimes; extraction, embeddings,
providers and mutable-memory policies need separate review. No dependency has
been selected or installed. A generic framework does not supply our provenance
or action-authority contract automatically.

## Continuous learning at three cadences

1. **During play:** ingest observed events, update last-seen state, flag conflicts,
   revise provisional beliefs, track obligations and detect repeated ineffective
   attempts. Reobserve/escalate when information or judgment is insufficient.
   Preserve the current task's history and budgets. This is state estimation and
   within-run adaptation; it does not by itself establish transferable learning.
2. **Between episodes:** propose lessons and counterexamples from evidence; check
   whether a problem is game behavior, missing observation, harness policy,
   planning or outcome labeling. Apply automatic structural checks and lead review
   proportionate to semantic/generalization risk. Candidate lessons can be tested
   without being active in production.
3. **Between evaluated versions:** compare frozen memory/retrieval/prompt/skill
   variants, retain regression results, and promote a reviewed candidate. A model
   upgrade is a confound/configuration change, not evidence that the memory learned.
   Code and prompt changes use the existing PR/CI process. Unsupported active
   formats reject; migrate all callers/storage together, with historical evidence
   preserved. Any previous candidate used after regression must be migrated and
   pass the one current contract; do not introduce a fallback compatibility path.

Weight training/RL is a separate future option: it needs model access, permitted
training data, trustworthy feedback, evaluation and a resource budget. External
memory adaptation can work with frozen weights; it still faces interference and
negative transfer. No evidence here justifies buying a training pipeline now.

A player sub-agent should receive task/epoch/budget identities, current visible
observations and explicit memory-version/retrieval IDs. It can return a bounded
plan plus source-linked annotations or lesson candidates. The service validates
identity, evidence and plan eligibility. Replacing the sub-agent should not lose
committed evidence; its conversation is a cache. A separate offline learner may
review records and propose changes but does not share action-writer authority or
mutate the active library mid-task. This separation is a responsibility design,
not a measured benefit of extra agents or a claim of OS-level role isolation.

## Mathematics that helps, and where assumptions fail

**Partial observability.** A [POMDP belief](https://people.csail.mit.edu/lpk/papers/aij98-pomdp.pdf)
is a posterior over possible states given action/observation history. It motivates
last-seen state and explicit unknowns. A textual belief ledger is not an exact
Bayesian posterior or sufficient statistic merely because we call it a belief.
CDDA does not provide a validated transition/observation model for arbitrary game
outcomes, so use a factored, task-relevant approximation and test what it omits.

**Subjective logic.** [Jøsang's 2013 draft](https://files.givewell.org/files/labs/AI/Josang2013.pdf),
Chapters 2–4, separates belief, disbelief and uncommitted mass. For a binary claim,
`b + d + u = 1`, projected probability is `b + a*u`. With positive/negative evidence
`r,s` and prior weight `W`, a standard mapping is `b=r/(r+s+W)`,
`d=s/(r+s+W)`, `u=W/(r+s+W)`; `W=2` is a convention. Cumulative fusion requires
independent evidence. Three summaries of one screenshot are one origin, not three
new trials. Neither a model confidence nor these equations establish calibration.
Unknown evidence dependence should remain unknown rather than receive invented
counts. Use provenance/status first; test a numeric calculus only against a
simpler baseline when evidence units and scope are defensible.
Low uncommitted mass is not low disagreement: many conflicting observations can
yield a projected probability near one half with little uncommitted mass. Display
support, counterevidence and ignorance separately. A probability of success also
differs from the utility or acceptability of risking failure.

**Truth maintenance.** [Assumption-based truth maintenance](https://cdn.aaai.org/AAAI/1987/AAAI87-033.pdf)
tracks reasons/assumptions so dependent conclusions can be retracted. This is a
particularly good fit: distinguish changed world state from a refuted inference,
and reconsider dependent plans/lessons without erasing the original observation.
A dependency edge is useful even without a numeric probability.

**Nonstationarity and calibration.** [Bayesian online change-point detection](https://arxiv.org/abs/0710.3742)
requires a generative model and hazard assumptions. Use known session/version
boundaries and contradictions first; a single universal time-decay rate would
confuse durable terrain with moving creatures. [Conformal prediction beyond
exchangeability](https://projecteuclid.org/journals/annals-of-statistics/volume-51/issue-2/Conformal-prediction-beyond-exchangeability/10.1214/23-AOS2276.full)
provides results under specified shift/dependence assumptions, not coverage for
arbitrary dependent game histories. A claimed confidence threshold needs scoped
calibration data and explicit missingness, not fluent self-assurance.

**Value of information/computation.** [Metareasoning for planning under uncertainty](https://www.ijcai.org/Proceedings/15/Papers/229.pdf)
formalizes spending computation when its expected decision benefit exceeds cost,
under a model. For us, first distinguish a missing observation from a reasoning
failure: stronger reasoning cannot reveal unseen state. Prefer cheap useful
inspection, bounded alternatives or a targeted operator question where appropriate.
An observation/tool may consume turns or expose risk; even free gameplay Observe
has wall-time cost and may reveal no new information. Avoid observation loops.

**Constrained optimization and causal attribution.** Improve success, cost,
latency and review burden subject to authority and harm constraints. A weighted
score must not let faster movement compensate for a violated control boundary.
GEPA is a reusable optimization candidate, not an evaluator. Keep candidate
ancestry, account for all search cost, and reserve untouched tests. A death after
an action does not prove that action caused it: delayed effects and unobserved
conditions require hypotheses/counterexamples, not a causal rule from chronology.
Offline logs generally do not identify the value of an untried policy without
coverage/causal assumptions; do not claim counterfactual survival from replayed
observations. Information compression and memory selection are useful optimization
problems, but compression quality must be measured by retained decision evidence,
not just fewer tokens or a more plausible summary.

## How we would establish improvement

First separate **memory quality** from **gameplay benefit**. Use the same retained
player-visible traces for recall, temporal updates, contradictions, abstention,
spatial scope and source-retrieval tests. Ground answers in retained observations;
exclude questions whose answer requires hidden engine state. Fault tests cover
missing sources, changed sessions, superseded lessons and hostile remembered text.
Synthetic tests verify contracts, not model/gameplay effectiveness.

Then compare frozen versions in real play: current task memory only; scoped
cross-episode retrieval; retrieval plus consolidation. Add procedural/prompt
changes as a separate comparison so gains can be attributed. Raw-history exposure
can be a diagnostic control with a matched context/cost budget. Keep action and
observation authority identical across conditions. Record retrieved lesson IDs,
source support, changed decisions, failure/recovery and costs, without retaining
private reasoning transcripts.

For **continual** improvement, declare an adaptation stream and fixed evaluation
checkpoints. Score each episode before admitting its outcome as future memory.
Measure later-task transfer and earlier-task regression, plus changed worlds and
engine/config versions. Freeze the cross-episode lesson library during held-out
evaluation; ordinary task-local observations and state tracking still update.
Do not admit test outcomes as new cross-episode lessons during that comparison.
An explicitly online adaptation test is a different condition; report its ordering
and cumulative performance, never blend the two protocols. Do not repeatedly tune
on the same final tests or erase failed/uncertain/censored runs.

Report task completion separately from progress, harmful outcomes, interventions,
false remembered claims, unsupported generalizations, invalid proposals and
regressions. Charge planning, retrieval, consolidation, reflection, failed calls,
storage and review effort. External Codex model identity/usage remain unmeasured
where unavailable; zero extra API spend is not zero total cost.

Trials sharing a character/save are dependent, and actions change later starting
states. Use legitimate visible starting states, record identities/order and limit
claims when conditions cannot be matched; no save editing or fabricated resets.
Few episodes justify per-run evidence and uncertainty, not precise safety rates.
Choose repetition counts and practical promotion thresholds before collecting
outcomes, under the current evaluation brief; this paper review does not set them.

## Proposed next decisions and maintenance

The smallest useful follow-up is an episode/handoff design with an inspectable
retrieval packet and retention/invalidation rules, exercised on existing traces.
It should identify an actual memory failure before selecting a search backend.
A later bounded comparison can test a few evidence-backed lessons. Broader maps,
learned retrieval, automatic tactics, calibrated belief fusion and weight updates
remain conditional on measured gaps and costs.

Keep this evidence review under [#26](https://github.com/CVX-Hull/cdda-player/issues/26)'s
active-review trigger. Link any future scope to existing evaluation and
[#27](https://github.com/CVX-Hull/cdda-player/issues/27) conditional-learning work;
durable episode memory is distinct from training and needs its own bounded brief
before execution. This discussion does not create or mark issues Ready. Before
implementation, refresh decisive papers if older than the active weekly research
window, recheck official tooling docs, and record which decision changed. Newness
alone is not a reason to replace accepted components. Review memory utility,
stale/false lessons, source retention, migration burden and regressions after
relevant incidents and capability changes; retire mechanisms that cost more than
the benefit they demonstrate.
