---
owner: lead
status: proposed
date: '2026-11-16'
scope: 'Research proposal for learning structured recurrent memory and searching its representations across controlled games and independent real games; objectives, competing arms, evaluation, agent operation and bounded first delivery. No runtime adoption or study spending is authorized.'
review_trigger: Feasibility or price pilot reports; a representation or cross-game claim changes; the research is adopted, stopped or superseded
---

# Structured recurrence and representation search across games

## At a glance

**Question.** Can one game-independent learning procedure discover representations,
updates and readouts that improve later decisions in unfamiliar games, at a useful
cost, without an engineer supplying each game's ontology?

**Proposed result.** A reproducible research screen, including failures, that decides
whether representation editing adds value over optimized replay and a fixed recurrent
structure. More types, shorter notes and plausible explanations are not success.

- Start with a **$0, no-model fixture and scoring slice**, then request a **$20-capped
  model price pilot**. The pilot and every subsequent paid batch need approval; no
  envelope is open. This proposal funds no experiment.
- Separate evidence: generated finite observation games test mechanisms; recorded
  play tests prediction under an observed policy; ordinary real-game play tests useful
  transfer. One cannot substitute for another.
- Compare **replay**, **fixed recurrence**, and **representation search** under the
  same resource ceilings, with an editing-disabled ablation for a structure-specific
  claim. Charge unsuccessful search and report actual usage as well as allowances.
- Engineering agents build and audit the study. A bounded model instance performs
  candidate generation or recurrent updates. An isolated evaluator scores it. None
  gains gameplay custody or hidden-state access.
- This is an alternative research path alongside the existing memory design. It does
  not revise the adopted memory direction, choose a belief calculus, enable the context
  cut, or introduce live curation. Current contracts remain authoritative.

GitHub owns ownership, capacity and stage: [research outcome #666](https://github.com/CVX-Hull/enactive/issues/666)
and [no-model feasibility slice #668](https://github.com/CVX-Hull/enactive/issues/668).
The [work map](../work.md) routes to the curated-player parent;
[work-item flow](../workflows/work-items.md) governs execution.

## Research contract and prior evidence

Research cutoff and primary-source retrieval: **16 November 2026**. This is a mechanism
proposal, not a new literature leaderboard. The prior [representation synthesis](../research-memory-representations.md),
[curated memory](../research-curated-memory.md), [programs](../research-curated-programs.md)
and [multiple-timescale review](../research-multirate-agents.md) supply the broader corpus.

The [representation experiments](../acceptance/2026-10-18-memory-representations.md)
show why source identity, applicability and retained meaning are separate. The
[transition study](../acceptance/2026-11-01-transition-corpus.md) supports only bounded
predictive claims at its sensor resolution and policy; it did not establish a useful
hierarchy. The [withholding study](../acceptance/2026-11-14-withholding-study.md) did not
confirm memory benefit, and delivery changed the set of topics touched. These are
reasons to score all assigned episodes and to separate predictive fit from action value.

| Primary source, read scope | Useful mechanism | Transfer limit |
| --- | --- | --- |
| Sun et al., [TTT](https://arxiv.org/html/2407.04620v2), 2024 v2, §§2.1–2.3, 2.7, 4.3 | A recurrent state can itself be a learner; update and readout are optimized in nested loops | Neural sequence learning does not establish that symbolic edits have gradients, sufficient state or useful game transfer |
| Kemp and Tenenbaum, [structural form](https://pmc.ncbi.nlm.nih.gov/articles/PMC2492756/), 2008, model, inference and examples | Jointly select a representational family and its instance using a likelihood and complexity-sensitive prior | Candidate forms and likelihoods are supplied; entities and datasets are already available |
| Littman, Sutton and Singh, [predictive state](https://proceedings.neurips.cc/paper_files/paper/2001/file/1e4d36177d71bbb3558e43af9577d70e-Paper.pdf), 2001, tests and Theorem 1 | Represent state by multi-step action-conditioned observation predictions | Finite-POMDP existence is not efficient discovery; selected logs leave untried actions unidentified |
| Tishby, Pereira and Bialek, [information bottleneck](https://arxiv.org/html/physics/0004057), 1999, §§2–3 | Compress while retaining information about specified relevant consequences | Relevance and a suitable distribution must be defined; tokens are not mutual information |
| Ellis et al., [DreamCoder](https://arxiv.org/pdf/2006.08381), 2020 preprint, methods and search analysis | Learn a reusable program language together with the search procedure using it | Primitive language, task likelihood and substantial search are required; uncertain visual worlds are not solved |
| Battaglia et al., [relational inductive biases](https://arxiv.org/html/1806.01261v3), 2018, §§2.2, 3.2, 5 | Shared relational operations and permutation symmetry support recombination | Entity extraction, useful relations and unseen dynamics remain learning problems |
| Berlot-Attwell et al., [Library Learning Doesn't](https://arxiv.org/html/2410.20274), 2024, §§3–6 | Test actual reuse and minimally ablate it at comparable compute | Two mathematical systems do not refute library learning generally; their gains were not evidence of useful direct reuse |

All mappings from these methods to curator agents below are **research hypotheses**.

## Hypotheses and objectives

The primary question concerns a **frozen learner configuration**, not the superiority
of every possible symbolic system or its LLM backbone.

| Hypothesis | Falsifying or limiting result |
| --- | --- |
| Representation search improves held-out episode success over both comparators within the same ceilings | No meaningful improvement; gains disappear when search cost is included; only development families improve |
| Structural edits contribute beyond ordinary recurrent writing | Editing-disabled execution performs as well; superficial field/name churn explains the apparent emergence |
| Discovered operations transfer or adapt to unfamiliar mechanics | Transfer needs engineer-written game fields/rules, or succeeds only under renamed familiar mechanics |
| Search learns to preserve consequential distinctions | Delayed cues, contradictions, rare exceptions or new goals are lost despite shorter states |

The practical primary effect proposed for the generated-game screen is **10 percentage
points in episode success**, averaged equally over the frozen held-out mechanics
families. This is a design threshold, not a forecast. Family-specific effects and
consequential-error rates accompany it. Approval of the final protocol fixes the
threshold before collection; the power exercise can reject the affordable design.

Two related objectives must not be conflated:

1. **External research objective:** improve task success and decision quality under
   declared inference, adaptation, storage and wall-time limits.
2. **Search objective on development data:** propose compact representations that
   predict relevant observable consequences and make useful readouts at low cost.
   Better search loss is a proxy, not acceptance.

For action/observation history h_t, candidate state M_t and query q_t:

```text
M_(t+1) = U_theta(M_t, a_t, o_(t+1))
r_t     = R_theta(M_t, q_t)
a_t     = pi_fixed(recent_observations, objective, r_t)
```

The actor pi is pinned for a comparison. Theta includes representation rules, updater
and reader; state instances change within an episode. A slower outer search changes
theta only on development/selection data. Both theta and episode memory start from the
frozen initial bytes on each final unit; no learning carries between held-out families.

A proposed development score is:

```text
future observable prediction loss
+ lambda * canonical representation description bytes
+ mu * measured update/read/search cost
```

The pilot defines prediction targets, horizons and cost units, normalizes each term on
development data, and fixes lambda/mu by selection performance. Description bytes are
a measured complexity penalty, not a claim to universal MDL or information content.
No optimization target reconstructs every pixel by default. All arms retain the same
raw evidence archive and access permissions; the budget applies to working state and
what is read, not erasure of evidence.

A representation may merge histories only relative to named objectives, actions and
prediction horizons. Prediction under the logged policy does not identify the value
of an untried action. A store can retain a distinction that its reader omits, so the
store, reader and actor are evaluated together.

## Competing representations and experiment arms

A game-independent hypothesis language supplies operations, not a list of game nouns.
The proposal permits these alternatives; the first slice implements only the minimal
replay/data-structure trial, not a general probabilistic programming system.

| Candidate family | Representation and allowed operations | Place in the study |
| --- | --- | --- |
| Episodic replay | Source-linked observations/actions and a query-selected readout; no consolidated world model | Required comparator |
| Recurrent prose/records | A bounded set of revisable claims and unresolved alternatives | Cheap fixed-form candidate and fallback |
| Relational state | Curator-invented types/fields/relations with scoped instances, supports and revisions | Initial structured candidate; shared software supplies generic JSON/reference validation |
| Predictive state or constraints | Named action-conditioned tests, alternative states and conditional dependencies | Candidate expressed as data/predicates after the minimal trial; no calibrated-probability claim from generated numbers |
| Compositional programs | Reusable update, query or prediction expressions over observations and state | Later search-space extension, admitted only with a bounded interpreter and separately frozen capacity |

The first model screen has **three arms**:

| Arm | What can change during an episode | What outer search can optimize |
| --- | --- | --- |
| Replay | Evidence index and retrieval selection; recent context is common to all arms | Reader/retrieval prompt or procedure |
| Fixed recurrence | Values and instances in a frozen record/relational shape | Updater and reader; choose the fixed shape on development/selection data and freeze it before final tests |
| Representation search | Instances plus explicit type/field/relation edits within the trial language | Updater, reader and representation-edit policy |

Use an initially empty record/relational store, not game-labelled slots. A fixed-form
record can contain model-chosen semantic labels as values; it cannot alter its field
schema. Search can emit a new version of that schema and migrate its state. This
separates semantic content from representational editing.

Every recurrent arm starts with a usable generic record list (`id`, free-text body,
source references), including the editing-disabled arm. Schema changes extend or
replace this shape; an empty domain means no supplied game concepts, not an unusable
empty schema. Because free text can encode relations too, this comparison tests the
utility of explicit editing affordances under budgets, not strictly greater expressive
power or the unique correctness of an ontology.

**Initial capacity proposal:** at most 64 KiB canonical UTF-8 working state including
its schema, 16 KiB candidate updater/reader definitions, and 2,048 output tokens per
readout. These are experimental resource settings, not new production text caps.
The price pilot can revise them once; subsequent capacity changes are new conditions.
All arms share archive access and actor recent context; no arm privately retains its
LLM conversation between research calls. The fixed-form baseline must be optimized,
not deliberately impoverished.

**Search allowance:** at most 12 proposed candidate configurations per arm per search
repeat, including invalid proposals. Every candidate receives the same training-unit
allowance. Training, selection, failed parsing, model requests and compilation all
count. Unused allowance is not padded with meaningless requests. Report resource
frontiers as well as the chosen common ceiling; equal caps do not imply equal spend.

To claim **structural contribution**, add a pre-registered editing-disabled ablation
of the selected search learner on new final units: same initial state, updater/reader
and resource ceiling, but reject type/field/relation changes while allowing value
updates. Record rejected edits and fallback. This intervention is a diagnostic in
controlled games, not a planted false memory or bad routine in ordinary game play.
A flat/prose search result is valid: the experiment must be able to conclude that
explicit structure did not earn its cost.

Make the intervention executable: proposals separate schema/migration edits from
value edits. The ablation receives an editing-disabled capability flag, ignores the
former group and applies valid value edits against its current generic schema without
an extra retry allowance. Its reader can still use the record bodies. Verify this
fallback on development examples before freezing the comparison. Report invalid-output
rates and rejected edits alongside the contrast; a gain explained by breaking the
ablation's update path does not establish useful structure. This tests the editing
affordance as a package, not a particular discovered relation's causal necessity.

## What counts as emergence

A structural edit is not an outcome by itself. Record its parent version, proposed
change, supporting visible episodes, migration and its consequences for predictions,
readouts and decisions. Inspect whether it:

- separates previously aliased histories whose later action consequences differ;
- merges redundant distinctions without losing consequential exceptions;
- represents an interaction that independent attributes could not predict;
- reuses a parameterized update/query computation on a new instance;
- revises persistence or applicability when mechanics change.

Do not grade using similarity to an engineer's preferred ontology. Permutation of
arbitrary entity/action names and different rendering are nuisance tests, not new
mechanics families. More variables, schema churn, textual elegance, compression alone
and claims that an agent “understands” do not establish emergence.

## Experiment sequence and stopping decisions

### Fixture and measurement feasibility: no model or game launch

Build a minimal, project-local diagnostic package. It renders finite observation games
as images or visible text and accepts basic key-like actions. A pure simulator/oracle
is **evaluator-only**; it is not a second game adapter or evidence of native support.
Its hidden state, rule parameters, seeds and scoring functions never enter learner
packets. Synthetically complete labels establish diagnostic correctness only.

Use four development mechanisms: delayed finite-state cues, conjunctive prerequisites,
state revision with ambiguous identity, and irrelevant observations. Reserve two
selection mechanisms: interactions requiring a relation and changed action effects.
Final generators use new combinations/rule templates, not only new seeds. Include a
fully observable negative control where memory should add little. For every family,
write counterexamples that distinguish wrong from useful state while allowing multiple
valid representations. Ordinary labels, icons and key mappings are randomized.

The first delivery implements one delayed-cue family and a fully observable control,
with example specifications for the other mechanisms; it does not build the whole
screen. It supplies the common manifest, generic record/edit format and executable
all-assigned scorer. Calibration initially uses simulated outcome tables, not model
learning or a complete game generator.

At **$0 new provider spend**, inspect one complete unit, verify packet boundaries and
scoring with deterministic stand-ins, and simulate the proposed statistical analysis.
No stand-in pass is evidence that a model learns. Appetite: two worker implementation
turns plus one integration/review turn; reduce scope if the generic fixture needs a
new runtime framework. Deliver the pilot's exact prompt/profile, resource table and
price worksheet; do not make a model call to price it.

### Model price pilot: proposed $20 cap, approval required

Use eight development worlds across two mechanisms, all three arms, one search repeat,
with a maximum of four candidate configurations per arm and 24 key decisions per
rollout. Curator updates occur after each three observations; the common actor gets
recent frames plus the arm's readout. Freeze update/read/actor request maxima and a
finite wall limit in the pilot package before approval. The pilot stops on the first
invalid end-to-end packet or exhausted allowance; a replacement needs a stated reason
and retains the failed original.

The price worksheet covers the complete worst-case **96 candidate-world rollouts**
(three arms × four candidates × eight worlds), including proposer, updater, reader,
prediction and actor calls, failures and selection scoring. If its conservative total
does not fit $20, reduce and re-freeze the pilot before approval; do not start a batch
that only prices its selected configuration. A smaller pilot estimates feasibility
and price only, never effectiveness.

Measure total provider-reported or conservatively bounded spend, tokens, calls, wall
time, invalid edits and scoring availability. Read the first complete rollout end to
end before the rest. Fit no final claims. Price the full screen from these actuals,
including all search repeats and the editing-disabled ablation. A cheap unit is not
permission for an unbounded batch; the existing admission rule still applies.

### Generated-game screen: first possible mechanism claim

Freeze four development families, two selection families and a reproducible grammar
for previously unseen final mechanics families. The unit is a mechanics family, with
worlds nested within it; the study claims only transfer within that declared generator
distribution. A change to its grammar after seeing final results makes those results
development evidence.

Use **eight paired worlds per final family**, each run with two independent model
sampling repeats for each arm. Propose a family count from **8, 12, 16 or 24** and
choose the smallest that passes the analysis calibration and fits the approved price.
Different colors/names/seeds are not independent families. Search is repeated from
scratch under three independent search seeds. Each repeat selects one complete
configuration per arm on selection families only. Final learner state resets per world;
repeat the complete frozen-bank comparison, and report shared-family/search-bank
uncertainty rather than treating all rollouts as independent n.

**Primary:** intention-to-treat task success at the declared ceiling, averaged equally
over final mechanics families. Assigned deaths, budget exhaustion, invalid outputs and
abandoned tasks stay in the denominator. Scorer/transport failures are retained with
a pre-frozen technical-failure rule and an all-assigned sensitivity analysis.

**Claim rule:** estimate search-minus-fixed and search-minus-replay effects. A useful
screen requires both gains to be at least 10 percentage points and both adjusted
one-sided confidence bounds to be positive. A structure-specific reading additionally
requires positive evidence against the editing-disabled ablation. Calibrate the three
pre-declared contrasts jointly at familywise 5%; report all three even when null.
No separate winner search over prediction horizons, mechanisms or scoring codebooks.
The 10-point rule is an observed practical screening threshold. Positive confidence
bounds support a positive effect, not a true effect of at least 10 points; that stronger
claim would require bounds exceeding 10 points and a separately powered protocol.

**Calibration before collection:** at least 2,000 simulations of the exact estimator,
intervals and decision rule, with family heterogeneity, paired worlds, shared search
banks, sampling repeats, scorer error and missingness. Report binomial uncertainty on
simulation error rates. Require a conservative false-positive bound no greater than
5% under specified nulls and at least 80% power for declared useful alternatives.
The pilot sets plausible alternatives and variance ranges. If no affordable setting
passes, stop or label the design exploratory; do not lower the bar after results.

Secondary diagnostics: predictive loss at fixed horizons, delayed-cue retention,
conflict/retraction, interference, rare consequential errors, structural-edit validity,
reuse, total search/adaptation/inference cost and latency. Rare-error results accompany
mean success; a higher mean cannot be described as safer without its own powered test.

### Recorded-play replay: observed-policy evidence

Reuse sealed development lineages and the trace projector. For each prefix, ask about
later visible consequences and ongoing work using questions fixed independently of
candidate outputs. Never include future frames, current evaluator labels or oracle
state in an updater/read packet. Split whole lineages, not adjacent windows. All CDDA
lineages already used for prompts/design are development data, including this proposal.
The old held-out labels do not restore held-out status to data now inspected.

Compare online recurrence against rebuilding from the same prefix at boundaries, plus
the optimized replay baseline. Test whether update errors compound and whether the
reader loses distinctions that remain in state. Preserve insufficient evidence as
unknown. This stage cannot establish alternative-action value, useful live play or
cross-game transfer from a single-game archive.

### Real-game transfer: separate admission and evidence

This phase requires the second-game feasibility work in **#291**, an owner choice of
lawful builds/tasks, and a separately priced protocol. It uses ordinary player-visible
screens and basic computer input; no symbolic environment state, hidden saves or game
semantics enter the shared computer harness. Keep natural player context/handoff
rules the same in every arm; do not silently introduce the deferred context cut to
make the memory comparison easier.

A proposed split is CDDA development, **NetHack** integration/selection, and untouched
**Brogue Community Edition** and **Dungeon Crawl Stone Soup** targets. These are
candidates, not chosen installations or qualified ports: source/build/license,
windowed rendering, basic-input control and reset/seed feasibility are checked first.
Official repositories were inspected on 16 November 2026:
[NetHack](https://github.com/NetHack/NetHack), [Brogue CE](https://github.com/tmewett/BrogueCE),
[DCSS](https://github.com/crawl/crawl). Related variants of the same engine, such as
NetHack tasks in MiniHack, do not count as independent real-game codebases. Broader
puzzle/survival benchmarks may be diagnostics; this proposal does not expand the
charter's supported game class.

Use a selection-game pilot of three paired starts to test native reliability, reset
and scoring. Then price and power a comparison of the selected search learner and the
strongest comparator on each target game; freeze meaningful visible task success and
finite episode limits per game before launch. Paired seeds are used only when ordinary
reset evidence supports them. Otherwise use independent randomized starts and price
that design. Controls/setup are identical within a game; game tasks are naturally
different, so report each game's effect and weight games equally in summaries.

Two successful target games would be scoped transfer evidence to those games, not
family-wide qualification. Failure in one target remains visible; repeated seeds do
not increase the number of independent games. If only one new game is feasible, report
a single-game pilot and stop short of the cross-game research claim. No native run or
second game is authorized by this proposal.

## Practical operation with our agents

### Logical roles and information flow

| Role | Inputs and outputs | Authority and limits |
| --- | --- | --- |
| Engineering lead | Research brief, source, costs, integration and final evidence | Sole integrator, native scheduler and admission owner; never supplies gameplay tactics |
| Explorer | Bounded source/research or artifact inventory | Read-only; no game input or study-model spending |
| Implementation workers | Disjoint study-runner and candidate/scorer paths in separate worktrees | At most two; no shared native runtime, provider key or environment changes |
| Candidate proposer | Training-visible prefixes and generic representation language; emits candidate artifact | No hidden fixture state, final outcomes or live game access; every proposal charged |
| Research curator/updater | Prior state and current visible batch; emits new state/schema or typed edit | One logical writer per trial; fallible; no evaluator imports or custody |
| Reader and fixed actor | Query/current observations, frozen objective and bounded memory readout | Actor decides actions through the current port in real play; updater/reader never send input |
| Evaluator and independent reviewer | Sealed assignments, outputs and later outcomes | Score after the prefix/episode; no final labels returned to player or curator |

The **outer research selector** is an engineering function: it ranks generic candidate
algorithms using training/selection scores. Final outcome scores are opened only after
all final outputs are sealed. It never sends judge facts, hidden state or task-specific
answer keys into a playing agent. Giving an operating curator access to evaluator
labels would be a different boundary and is outside this proposal. Current
[ADR 008](../decisions/008-evaluation-and-spectator.md) isolation remains in force.

For no-spend document/fixture work, use our coding agents. For measured model arms,
use the same explicitly pinned model/provider/effort and bounded host profile. A fresh
agent's prior conversation, repository access or private reasoning must not become an
unaccounted memory channel. Host agents without comparable usage or model identity
can help develop examples but cannot establish matched-cost model superiority. “No
new provider bill” is not zero compute or quota consumption.

### Minimal research interface and artifact ownership

The following is a **proposed study interface**, not a current production schema/API:

| Artifact or operation | Required content / responsibility |
| --- | --- |
| Frozen trial manifest | Split and family identifiers, generator/build/prompt/model hashes, candidate bytes, sampling seed, observation/action permissions and all resource ceilings |
| Visible batch | Ordered source IDs/images or text, previous actions and their delivery status; only the prefix available at that point |
| Candidate | Representation definition, updater/reader prompts or bounded expressions, initial state, parent candidate and declared capacity; no importable production code |
| `update(state, batch)` | Return one new version and source-linked edits; fail as an invalid candidate if shape, budget or references are invalid |
| `read(state, query)` | Return bounded text/records, source references and explicit unknowns; no action or evaluator result |
| `predict(state, test)` | Return a prediction for named future observable tests, recorded before their outcomes; no oracle query |
| Trial receipt | Original request IDs, all retries/failures, publication/read versions, resource usage, state/artifact hashes and ending reason |
| Scoring output | All-assigned episode and family metrics, paired assignments and uncertainty; stored only on the evaluator side |

The initial package accepts JSON data and prompt-defined updates. It uses the existing
`jsonschema` dependency for structural validation and a bounded interpreter only for
expressions whose grammar the first slice defines and reviews. Arbitrary generated
Python/JavaScript execution is not part of that slice. No compatibility mode is added
to `curator-fact/3`: trial artifacts remain inert and cannot be imported as active
player knowledge. Any later deployment needs one coordinated contract migration.

Reuse seams verified against source: `harness/trace/` for sealed prefix projection;
`harness/curator/session.py`, `window.py` and `tools/curator_host/` for isolation, bounded
model sessions and receipts; `knowledge.py` for versioned publication concepts;
`tools/memory_measure.py` for offline packet/judge patterns. Their existing fixed
fact/article gate is **not** an arbitrary representation runner. Reuse machinery through
its actual interfaces; document a missing seam before extending it. Do not duplicate
the campaign custodian, secret proxy, evaluator database or Git source history.

The first implementation brief owns only `tools/recurrence_research/` and
`tests/test_recurrence_research_*.py`, plus this proposed document if the design changes.
A minimal package contains fixture generation, candidate/data validation, replay/packet
construction and scoring/calibration. Worker ownership is split between fixture/runner
and candidate/scoring files, with the lead owning the manifest and integration. Exact
filenames/interfaces are written in the bounded briefs before either worker starts.
No worker modifies `harness/`, existing host adapters, shared locks, dependencies or
production schemas. A needed change there returns to the lead as a separate decision.
All outputs stay in an owned ignored `.runtime/` study directory; reusable sources are
tracked normally. One-off study tooling is retired when its question is finished.

## Resource, evidence and delivery decisions

| Boundary | Proposed allowance or decision |
| --- | --- |
| Current change | Proposal, source-backed review and tracker reconciliation only; $0 provider spend |
| First implementation slice | No model/game launch, no new dependency, two worker turns plus lead integration/review; owned local fixture execution capped at two CPU-hours |
| Model price pilot | Request $20 maximum after exact inputs, host request ceilings, token prices and complete-pilot forecast exist; not yet approved |
| Generated screen / replay / real play | Separate priced envelopes after pilot; no remainder from another study is reused; no implied $1,500 research allocation |
| Expansion | No new interpreter, representation family, model tier, game installation or extra concurrent game merely because a pilot passed |
| Stop/rescope | Unpriced request or ownership failure, leakage, invalid scoring, budget limit, no affordable calibrated comparison, or no useful result after one full frozen screen |

Retain all failed candidates, seeds and starts; use the existing evidence retention,
ledger and finite-run practices where applicable. Do not reopen a failed admission or
renew resources through a retry. Paid checks of the research hypothesis are not the
standing $1 pre-merge prompt check. Pin and inspect source, identities and complete
commit messages before publication; use the required protected CI profile.

These proposed study procedures apply existing controls to named risks; they do not
change the project's global control set:

| Risk | How the study reduces it | Cost / remaining limit |
| --- | --- | --- |
| R-FALSE-CLAIM | All-assigned outcomes, split isolation, calibrated analysis, source/usage receipts, exact comparisons | Simulation, sealing and independent review; finite families and noisy real-game readers still limit claims |
| R-GAME-COUPLING | Generic edit operators, empty domain initialization and mechanics/codebase holdouts | Extra environments and transfer work; a finite holdout does not prove universal learning |
| R-STUDY-OVERRUN, R-OVERSPEND | One no-spend slice, one capped price pilot, later priced batches and stop rule | Pilot/integration effort; unknown prices and model variance remain |
| R-DELEGATION-ERROR, R-WRONG-MERGE | Disjoint worker ownership, one integrator, exact-candidate review and protected checks | Review/CI time; agents remain fallible |
| R-ARCHITECTURE-DRIFT, R-PRIVATE-DATA | Sealed prefix only, no evaluator-to-player path, same existing secret/isolation ownership | Packet/isolation checks; generated-data success does not qualify the real boundary |
| R-TECH-DEBT, R-CONTROL-BLOAT | Reuse existing primitives; keep a small study package and retire it on closure | Maintenance while the question remains open; no general platform is promised |

## Decisions still required and expected outputs

No research result is claimed by merging this proposal. The lead can scope the
no-spend fixture/price worksheet within ordinary engineering delegation. Before paid
work, the owner decides the priced pilot and envelope. Before real-game work, #291
owns the game/build/task decision and port feasibility. A live curator, context cut,
new belief calculus or production replacement has its own evidence and adoption path.

The discovery outcome ends with: frozen artifacts and costs; an executable comparison
or a justified stop; effects and uncertainty by family/game and complete search repeat;
a structural-contribution reading or an explicit failure to establish it; and an
adopt/reject/defer recommendation with its scope. A useful negative result can close
the research outcome without adopting a representation. Further implementation issues
are created only when a completed slice supplies their prerequisites.
