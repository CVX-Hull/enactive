---
owner: lead
status: historical
date: 2026-10-18
scope: Memory investigation brief, predeclared comparisons and implementation handoff; completed research evidence linked below, no runtime architecture adoption
---

# Investigate memory representations and continuous improvement

## Requested outcome

Explore different mathematical, statistical and related ways to understand memory
and learning for CDDA Player. Critically assess which representations and update
mechanisms address real pain points, then simulate selected hypotheses and produce
a coherent, understandable recommendation with adopt/test/defer decisions.

The user authorized this investigation on **2026-10-18**. It extends the
[initial memory review](../research-memory-learning.md); that proposal is a starting
point to challenge, not a predetermined answer. The current
[architecture](../architecture.md) and [protocol](../protocol.md) remain authoritative.
This is research and experimental design, not authorization to change live gameplay
contracts or claim a new gameplay capability. GitHub owns status and allocations;
[study outcome #59](https://github.com/CVX-Hull/cdda-player/issues/59) owns acceptance
and its bounded children; [work](../work.md) links the Project.

## Questions and competing perspectives

Examine both the representation of information and the operations that update,
retrieve, compress, revise and learn from it. Ask what each view explains, what it
hides, which assumptions it needs and how it could fail.

| Research lens | Competing ways to see the problem and questions to test |
| --- | --- |
| Probability and decision state | Factored Bayesian beliefs, predictive-state representations, sets of hypotheses, subjective/imprecise probabilities; what is a sufficient state, and when is numerical precision unjustified? |
| Logic, databases and provenance | Event history, temporal tables, materialized views, derivation algebra, truth maintenance and explicit alternatives; which operations preserve history, retract unsupported conclusions and prevent resurrection? |
| Information theory and compression | Memory as a constrained channel or decision-sufficient summary; what distortion matters for action, which rare events must survive, and how do repeated compactions lose information? |
| Control and identification | Memory as an observer state, learning as model identification, surprise/innovation and change detection, robust/set-valued control and active sensing; when does a wrong model make decisions worse? |
| Statistics, causality and optimization | Learning as a sequence of interventions, prequential performance, transfer/retention, adaptive selection and constrained policy improvement; what can selected logs actually identify? |
| Composition and cognition | Typed representations, evidence-carrying claims, composable plans, episodic/semantic complementary systems, event segmentation and affordances; when does an abstraction simplify reasoning and when does it add ceremony? |

The list is a breadth map, not a requirement to implement every formalism. Follow
unexpectedly useful connections; avoid collecting analogies without operational
consequences. Do not select the existing architecture merely because it is
convenient, nor select advanced machinery because it is new.

## What elegance means here

Assess each candidate with an explicit scorecard and examples, without inventing a
single numerical beauty score:

- Few coherent concepts with clear meanings; distinguish observations, inferences,
  predictions, procedures and permissions without unnecessary object kinds.
- Explicit invariants and composable operations. State which properties actually
  hold: identity/idempotence, order sensitivity, dependency retraction, boundedness,
  and rebuild/replay behavior; do not assume a graph or algebra guarantees them.
- Explainable decisions: the owner can inspect the evidence, uncertainty,
  applicability and reason for a changed lesson without reading implementation.
- Graceful behavior under ambiguity, missing evidence, contradiction and drift;
  no invented certainty or authority gained through memory.
- Predictable resource use and total maintenance cost, including schema changes,
  indexing, review, migration, measurement and retirement.
- Parsimony supported by comparisons: retain a mechanism only when it buys an
  observable benefit over a simpler alternative for a stated need.

A finding that a small relational/evidence representation is sufficient is valid.
So is a justified richer representation for a specific demonstrated problem.
A patchwork of independently attractive formalisms is not automatically coherent.

## Research and delegation workflow

The lead owns questions, source verification, design, adjudication, simulation
protocol, integration and final acceptance. Read-only researchers use distinct
lenses above; every handoff must provide primary URLs/revisions, read depth,
objects/operations, assumptions, CDDA mapping, a counterexample, a simpler baseline
and a falsifiable experiment. Repository summaries are context, not new literature
evidence. Incomplete or unsupported handoffs return for deeper reading.

Start with 2026 and late-2025 literature, explicitly check the latest week, and
retain foundational work where it supplies an applicable result. Verify actual
submission/revision dates; a future conference date does not by itself invalidate
a pre-cutoff preprint or establish future peer review. Read decisive methods,
results/proofs and limitations. Label discovery-only, unverified and inaccessible
sources; distinguish authors' claims from project inference. No universal SOTA
claim follows from this targeted survey.

After breadth, follow only material unresolved questions. Independent clean-context
review challenges the proposed comparisons, theorem transfers, missing baselines,
complexity and whether the study could disprove the lead's preferred design.
Do not stop because agents agree; their errors and source evidence can be shared.

Simulation implementation starts only after a reviewed concrete protocol and
interfaces exist. If parallel implementation is useful, use at most two workers in
separate project-local worktrees with disjoint named ownership, one writer per
checkout, and the lead as sole integrator/shared-runtime owner under S-AGENT.
Workers receive base revision, owned paths, fixed decisions and exact checks.
Do not split a tight implement/test loop over shared files. Do not build a general
simulation framework where a bounded experiment using mature tools is sufficient.

## Simulation contract to freeze before execution

Create a dated, versioned protocol before collecting comparison outcomes. It must
name the hypotheses, candidate representations/update rules, simpler baselines,
assumptions, event schema, scorer-only truth, observation visibility, budgets,
development/held-out seeds and regimes, repetitions, metrics, stop conditions and
analysis procedure. Record later changes and reasons before affected outcomes;
retain earlier results. Candidate choice and thresholds cannot be justified by
quietly tuning against the final test set.

Cover at least these discriminating pain points, combining cases where useful:

1. Duplicate or correlated evidence that must not manufacture independent support.
2. Delayed/out-of-order observations, changed world state and uncertain effects.
3. Retraction with multiple derivations, surviving independent support, and
   prevention of a retired claim returning through summaries/index rebuilds.
4. Session/coordinate reset, ambiguous identity and two observationally
   indistinguishable situations where abstention or sensing is required.
5. Tight memory budgets, rare consequential counterexamples, retrieval confusion
   between opposite operations and repeated lossy consolidation.
6. Mechanism drift and later learning that can damage earlier-task performance;
   confounded/selectively logged outcomes and unsupported counterfactuals.

Use identical observable streams for memory-only comparisons. Keep latent truth
and generating parameters in the assessor; audit every candidate's input for
leakage. When active information acquisition changes a trajectory, use a separately
declared interactive condition with its own action/information costs; do not label
that a fixed-history comparison. Privileged truth stays assessor-only; an explicitly
labeled oracle policy may serve as a theoretical reference, with any claimed bound
justified. Full observable history is an ordinary diagnostic baseline with declared
budgets/costs, not an oracle or an assumed performance ceiling. Include model misspecification,
negative controls, perturbations, adversarial cases and sensitivity to budget,
noise, correlation, drift, sparsity and task order as relevant.

Measure the dimensions appropriate to each representation: source/lineage
correctness, stale/unsupported claims, abstention, decision loss, probability scores
only for proper declared distributions, interval/set coverage and width, transfer,
retention, retrieval/compaction cost, time/storage and review burden. State which
are measured, structural proxies or unmeasured. Separate hard authority invariants
from utility tradeoffs; speed cannot compensate for invalid action authority.
Report seeds, sample sizes, dependence, missingness and uncertainty; justified
statistical assumptions are required for coverage or significance claims.

Reproducible synthetic results test mechanisms under their generating assumptions.
They do not establish CDDA survival, model effectiveness, calibrated real-game
confidence or native acceptance. Recorded real visible traces can test memory
questions; logs without counterfactual support cannot establish an untried policy's
value. Any later gameplay comparison requires a separate bounded native protocol.

## Deliverables and completion

- A source/evidence matrix with explicit recent/foundational coverage, read depth,
  assumptions, contested claims and transfer limits; lead-verified decisive sources.
- A comparison of candidate representations and update/learning operations, mapped
  to actual CDDA pain points, with alternatives and explicit rejected/deferred ideas.
- A predeclared reviewed experiment protocol; reproducible project-local simulation
  code/configuration, seeds, outputs, failures, ablations and sensitivity analysis.
- Clear diagrams and progressive explanation of the recommended concepts, state
  transitions, evidence/learning loops and action-authority boundary. Explain what
  becomes simpler and what new maintenance burden remains.
- Adopt/test/defer decisions supported by evidence, a minimal implementation scope,
  measurable acceptance and reversal/revisit triggers. Unresolved uncertainty stays
  explicit; negative or inconclusive experiments are legitimate outcomes.
- Independent protocol and final review, relevant passing repository/simulation
  checks, inspected versioned artifacts, and public evidence through a protected PR.
- Bounded GitHub follow-ups with owners, dependencies, acceptance and provisional
  estimates. Coordinate with baseline evaluation #24/#56, monitor work #40/#42–#44,
  research maintenance #26 and conditional advanced learning #27 without declaring
  any dependent capability accepted or committing to training.

Keep source corpus, dependencies, caches and experiment outputs project-local;
commit recipes and reviewable selected results, not uncontrolled generated bulk.
Evaluate maintained tools before custom numerical/statistical infrastructure.
No global installs/profiles, save editing, hidden game-state advantage, fullscreen,
new model API spending, model training or live self-modification. Existing saves,
evidence and current runtime contracts remain preserved. Any later contract change
must migrate every caller/persisted format together; no compatibility path.

The aggregate study is L/Low confidence until candidates and simulation scope are
reviewed; estimate each bounded child separately. Initial planning range: 3–8
focused work sessions for research, design, simulation, review and synthesis,
provisional rather than a calibrated elapsed-time forecast. Re-estimate openly on
new evidence. Do not force a preferred conclusion to meet that range. Research
currency and memory/evaluation maintenance use #26's existing active review trigger,
plus model/observer/engine changes and false-memory or regression incidents.

## Implementation allocation

The [evidence matrix](../research-memory-representations.md) selects four falsifiable
comparisons and the [frozen protocol](../design/memory-study-protocol.md) fixes
inputs, assumptions, baselines, scoring, configurations and seeds. At this
allocation checkpoint no simulation result or live schema had been adopted.
The source/protocol checkpoint had to be published before implementation workers
received their exact base revision.
GitHub #62 owns execution; #63 owns final adjudication and review.

| Owner | Exclusive implementation paths | Acceptance |
| --- | --- | --- |
| Lineage worker | `tools/memory_study/lineage.py`, `tests/test_memory_study_lineage.py` | L's 12 literal fixtures/32 queries; replay/view equality; duplicate, time, scope, retraction and retirement controls; hand-calculated counters; no other owned paths |
| Retrieval worker | `tools/memory_study/retrieval.py`, `tests/test_memory_study_retrieval.py` | C's exact FTS/schema/query, shared answerer, source/session filters, deterministic generator, idempotent and lossy controls; backend failure stays explicit |
| Lead | Remaining `tools/memory_study/` modules, remaining study tests, reports/docs/tracking | E/D implementation, common accounting/runner, leakage audit, exact-config execution, integration, reproducibility, negative results and final verification |
| Clean-context reviewer | Read-only changed code/protocol/results | Challenge correctness, independence/leakage, baselines, scope, reproducibility and claims against primary evidence |

Workers use separate project-local worktrees, one writer per checkout, no native
runtime, API calls, installs or shared output/cache writes. Lead passes the
published base revision and absolute worktree path in each brief. Use the existing
root `.venv/bin/python` as a read-only interpreter/dependency source; put bytecode,
tool caches and test output in each worktree. Workers stop after two failed repair
attempts or ownership drift; lead integrates inspected diffs. No worker changes
the protocol or tunes a rule from final outcomes.

### Fixed module handoff

Each suite exports `run(seeds: tuple[int, ...]) -> list[dict]`. Rows are independent
**seed aggregates per condition/method**, not per-query pseudo-replicates. Each row
has exactly `suite` (`L`/`E`/`C`/`D`), `seed` (integer), `condition` (string),
`method` (string), and `metrics` (mapping of descriptive metric name to finite
number). Conditions encode every varying regime/budget; no condition merging
that hides failures. Include denominators/counts for rates and document units.
The lead-owned runner validates rows, retains raw seed aggregates and writes
aggregate reports with source/config hashes and runtime identity. Timing is
measured by the runner and excluded from deterministic content comparison.

Common helpers, owned by the lead, are `json_bytes(value) -> int` (canonical
UTF-8 JSON, sorted keys, separators comma/colon, no NaN), and
`rng(seed: int, namespace: str) -> random.Random` (seed the private generator from
the integer value of SHA-256 of UTF-8 `namespace + ':' + str(seed)`). Suite names
are namespaces; separately randomized reservoirs use `C-reservoir:<condition>`.
No Python process-randomized `hash()` seeds. Workers may import only these helpers
from `tools.memory_study.common`; they own no shared helper edits. Suite-local
dataclasses, generators and method functions remain in their assigned modules.

Tests use literal/development examples only, exercise formulas/semantics/leakage
and report schema, and must not assert a preferred performance ranking. Exact
worker commands are given with their worktree. The final seed set is run by the
lead only after integration and code/config freeze. Preserve report revisions on
any later bug or analysis change. This is experimental scaffolding, not a generic
agent-memory framework or a second runtime contract.

## Outcome record

The [synthesis](../research-memory-representations.md) and
[acceptance](../acceptance/2026-10-18-memory-representations.md) record the research,
two complete identical collections, independent reproduction checks, readable
advice/improvement diagram and adopt/test/defer recommendation. Source/protocol
checkpoint PR68 and implementation/results PR69 provide protected publication.
The minimal next slice is a player-visible trace benchmark before persistent
memory redesign. Its live scope, estimate and acceptance are in GitHub, alongside
native baseline #24/#56, monitoring #40, maintenance #26 and conditional #27.
This historical brief preserves the original questions/allocation and does not
promise an implemented memory architecture or completed native-policy evaluation.
