---
owner: lead
status: proposed
date: '2026-11-16'
scope: 'CDDA-only research proposal for structured recurrent memory and representation search across diverse real starts and visible-trace replay. Other games and their unforeseen generalization problems are deferred to future versions. No runtime adoption or study spending is authorized.'
review_trigger: Feasibility or price pilot reports; a representation or cross-game claim changes; the research is adopted, stopped or superseded
---

# Structured recurrence through diverse CDDA starts

## At a glance

**Question.** Can the gameplaying curator discover representations, updates and readouts
that improve decisions across diverse CDDA starts, at a useful measured cost, without
engineers supplying the game's ontology?

**Current scope: CDDA only.** Keep the shared representation/update mechanisms generic,
but test them in CDDA now. Other games, new game ports and a synthetic interactive-game
benchmark are outside this investigation. Unforeseen cross-game problems are work for
future versions; discovering or solving them is not a prerequisite to this outcome.
The [owner decision log](../decisions/owner-decisions.md) records that boundary.

**Proposed result.** A reproducible comparison of optimized replay, fixed recurrence
and editable representations on unseen CDDA worlds/survivors and conditions. More
fields or persuasive explanations are not success. Within-CDDA transfer is the claim;
cross-game generality remains untested.

- Start with a **no-model inventory, sealed-prefix packet/scoring check and priced
  CDDA pilot package**. No new game or diagnostic simulator is built.
- Separate evidence: deterministic replay checks test the apparatus; model replay
  tests retained distinctions and prediction under the observed policy; actual CDDA
  continuations test decision value. None substitutes for the others.
- The player chooses every game input. Its curator updates memory and proposes
  structural revisions; retrieval produces relevant, fallible readouts. Evaluator
  answers do not enter any of those roles.
- Existing memory adoption, the belief decision and the deferred context cut retain
  their own scope. This proposal enables no live scheduler or production schema.
- No study envelope or pilot dollar ceiling is set. Price the complete CDDA package
  before requesting spend; an unapproved amount from another design funds no play.

GitHub owns ownership, capacity and stage: [research outcome #666](https://github.com/CVX-Hull/enactive/issues/666)
and [no-model feasibility slice #668](https://github.com/CVX-Hull/enactive/issues/668).
The [delayed-memory assessment proposal](delayed-memory-assessment.md) specifies
how to select decisions, compare context budgets and acquire a later waking period.
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

The [measurement audit](../acceptance/2026-11-16-experiment-measurement-review.md)
also identifies structurally impossible simulated events in earlier power sizing,
unqualified positive-case readers and narrow conditional process measures. Future
scoring must distinguish impossible from rare outcomes, qualify the specific visible
task outcome on positive/negative/unknown examples, and group related continuations
before uncertainty or power calculations. Reuse the common packets for these checks;
the old sizing forecast is not a qualified sample-size recommendation for this study.

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

## Fit with the implemented player, curator and planned designs

### Baseline and the missing connection

The initial source and artifact review used `a3d61521`; the adopted journal migration
subsequently landed through #463 (`7c6c2469`). Distinguish built, measured and proposed.
Current contracts/source remain the
runtime authority; this comparison does not adopt the research design.

| Part | What exists | What this research adds or must not assume |
| --- | --- | --- |
| Deciding player | The [Pi host](../../tools/player_host/README.md) runs a model/tool loop over visible frames, objective, conversation and basic controls. Context/handoff and original resource limits belong to the [host contract](../contracts/player-host.md). | Treat the actor's recent conversation as part of recurrent state. Extra curator memory is not the whole recurrence, and its benefit is tested with natural actor context held equal. |
| Player-owned durable state | [Current tools](../../harness/player_tools.py) record public intent/cites and separate fallible hints in `player-journal/1`; authored-memory/program tools are removed. | [#463](https://github.com/CVX-Hull/enactive/issues/463) implements this adopted boundary. Historical sources lack the new emissions. Immediate reasoning, ongoing objectives and summary-only handoff remain the player's responsibility. |
| Curator | [Sessions](curator-session.md) read sealed visible trace windows and published knowledge, propose facts/articles/types, and groom the store. Sandboxing, model proxy, source references and versioned publication are built. | Reuse them for incremental learning. There is no live scheduler or hidden engine-state feed to assume. A player hint is a fallible learning lead, not an assertion automatically promoted to truth. |
| Representation | [Gate v0](../../harness/curator/gate.py) supports typed free-text facts, articles and type metadata. [The prompt](../../tools/curator_host/prompt.md) explicitly says type fields do not add fact keys. | New type names do not demonstrate learned typed state. Explicit relation instances, identity rules, constraints and schema migrations need an experimental representation/readout and eventually the coordinated schema path in #457. |
| Delivery | [Knowledge export](../../tools/knowledge_export.py) freezes a version for a run; [recall](../../tools/player_host/host.mjs) selects briefing/reminder entries, and delivered facts/articles can be read or queried. | Recall is a retrieval role, not a curator updating the store. Arbitrary schema data cannot silently pass through the current closed delivered-knowledge format. |
| Publication and evaluation | The current gate validates form, source membership, references and base version. The [independent evaluator](../contracts/evaluation.md) reads recorded outcomes and never feeds the player/curator. | Structural validity does not establish truth, sufficient memory or action value. Planned later-trace admission tests in #457 must remain distinct from independent study outcomes. |

The inspected groomed `v18` artifact has 77 current facts, 32 articles and four types
(procedure, recipe, resource, hazard), all with empty field lists. The
[curator-scoring record](../acceptance/2026-11-13-curator-scoring.md) establishes the
store/version provenance and its measured limits. This is a working text-knowledge
organization, not evidence that a general structured world model emerged. Mechanics
can already be expressed in prose; structured payloads must earn their extra machinery.

The [withholding study](../acceptance/2026-11-14-withholding-study.md) and
[session follow-up](../acceptance/2026-11-16-withholding-follow-up-and-grooming.md)
measured a fixed store on two saved moments of one lineage. Their null frozen primary,
short/censored continuations and delivery-to-action gaps motivate the new comparison.
They neither establish nor refute the value of a continuously revising curator.

The [owner decision](../decisions/owner-decisions.md) adopts memory with benefit
unclaimed. #463 aligns current rules and contracts for the implemented journal/hint
boundary. Later representation, belief, live-update and execution phases remain
proposals; this research does not adopt them.

### One system, several kinds of learned content

The proposed recurrent system consists of **actor context C**, **published knowledge K**,
its **representation S**, and later optional **programs P**. These are responsibilities,
not mandatory separate databases, model tiers or hand-written domain types.

- **Immediate working context:** what the actor currently sees, intends and is doing.
  The player owns decisions and can continue when a helper is unavailable.
- **World/episode beliefs:** source-linked, revisable interpretations of this survivor's
  surroundings, possessions and events. Historical observation and current belief differ.
- **Mechanics hypotheses:** conditional relationships supported by observed effects,
  including their applicability, alternatives and counterexamples. They do not become
  universally true because the curator wrote an article about them.
- **Ongoing work:** unfinished objectives, dependencies and reasons a plan changed.
  Curator records help continuity; they do not take planning authority from the actor.
- **Reusable representations and later procedures:** types, relations and bounded
  rule expressions may be state data; an executable gameplay program is a separate,
  versioned behavior with its own proposed admission/execution contract.

The existing recurrence equations describe the curator's explicit state and readout.
The whole loop also updates the actor's conversation after each observation/action.
A schema change is useful only if the same frozen reader and actor can interpret the
new version. The reader therefore needs definitions/applicability and source support,
not just unexplained field names. The proposed ontology card in #457 is a natural
consumer seam, not proof that the current reader already supports arbitrary schemas.

For example, an observed interaction suggests a rule conditional on some capability.
A later visible counterexample causes the curator to narrow that rule or preserve two
alternatives. A subsequent player query retrieves the revised condition and unresolved
uncertainty. The player chooses whether to act, re-observe or investigate. Success is
measured from the resulting visible play, not the elegance of the rewritten rule.
No engineer needs to seed a CDDA capability type to conduct that test.

### Crosswalk from the session's research

| Research/design discussion | Place in this system | Consequence and limit |
| --- | --- | --- |
| [Memory representations](../research-memory-representations.md): replay, provenance, constraints, predictive state and compression | Evidence archive, K/S and reader R | Preserve consequential distinctions and origins; prediction under logged actions does not identify untried-action value. Byte length is a complexity penalty, not a sufficiency theorem. |
| [Curated memory](../research-curated-memory.md): belief revision, truth maintenance, ontology and oversight | Curator update/grooming and #457 | Keep observation, interpretation, contradiction and retraction distinguishable. The belief calculus remains an owner decision; evidence is not converted to calibrated confidence by counting citations. |
| Structured recurrence / the RNN analogy, including test-time-learning inspiration | Repeated visible-evidence updates plus slower schema proposals | The explicit recurrent state can contain records, graphs or bounded rules. This first experiment is discrete/model-mediated adaptation, not an implemented differentiable learner or automatic gradient through symbolic edits. |
| Relational structures, predictive tests, information bottleneck and structural-form search | Competing S/U/R candidates under the same evidence/cost permissions | Search for operations that reuse across CDDA situations; retain replay/prose as serious alternatives. A fully expressive text baseline can encode relations, so explicit structure must improve use under resources. |
| Database/materialized-view, truth-maintenance and compiler analogies from the representation discussion | Original visible evidence, revisable K/S and query views | Preserve source identity while rebuilding derived views; schema migrations should preserve relevant query meaning. These are design analogies, not a mandate for another event store, graph database or compiler framework. |
| Control/state-estimation, automata and probabilistic-model analogies | Conditional mechanics hypotheses and state uncertainty | A compact state should retain distinctions needed for specified future observations/actions. Unknown hidden conditions remain unknown; a descriptive latent state or invented probability is not validated dynamics or calibrated belief. |
| [Programs/library learning](../research-curated-programs.md), [executable policies](../research-executable-policies.md) and [organic discovery](organic-discovery.md) | Optional P, after useful memory | Reusable behavior is a later consumer of learned conditions and procedures. #177 owns its program/slot/monitor work; representation editing does not grant execution or prove library reuse. |
| [Multiple timescales](../research-multirate-agents.md) | Fast actor, batched curator updates, slower grooming | Separate rates where useful; do not add mandatory agents or model tiers. Queueing, stale knowledge and correlated errors can outweigh compression. |
| [Player context](player-context.md), [general memory](general-memory.md) and the delivery experiments | R, briefings/reminders, handoff and context cost | Store coverage is what was read, not proof of complete recall. A recent citation in an article does not make every claim fresh. The deferred context cut is not needed to test this system. |
| [Transition study](../acceptance/2026-11-01-transition-corpus.md), [representation experiments](../acceptance/2026-10-18-memory-representations.md) and the latest withholding follow-up | Hypothesis selection and study design | Earlier predictive/toy results and frozen-store use are bounded evidence, not proof of hierarchy, safety or live learning. Diverse genuine CDDA sources and all-assigned outcomes address some of those limits. |

### Learning feedback, freshness and integration order

Keep three feedback paths distinct. The operating curator can compare its own earlier
predictions with **later player-visible observations**. A future submission gate can
run the separately specified private later-trace admission tests in #457; their feedback
policy must not become an unrestricted answer oracle for repeated proposals. The
independent research evaluator scores sealed final trials and sends no final answers
into the operating learner. Development/selection scores can rank generic learner
configurations outside final play, as this protocol already specifies.

Measure freshness in **decisions, wall time and in-game time**, plus source coverage and
version. The same number of player inputs can represent a short interaction or a long
in-game activity. Coverage, publication recency and semantic validity are different:
a mechanics claim may remain useful for a long time while an inventory claim changes
immediately. Atomic publication avoids half-migrated views; it cannot make stale data
true. Retrieval must preserve uncertainty and applicability. The player keeps recent
observations and control while the curator works; no context cut follows from a
coverage stamp.

The smallest coherent sequence uses existing work rather than a new stack:

1. **#463, complete:** the adopted ownership/tool migration, intent/hint inputs and rule
   alignment are on main. No positive recurrence result was required. Player
   reasoning/handoff and knowledge reads remain.
2. **#668:** prepare the real-CDDA source portfolio, deterministic stand-in packets,
   candidate/readout comparison protocol and complete prices through current public
   primitives. This tests the apparatus and defines the question; substantive model
   replay and learner-failure evidence belong to a later separately approved pilot
   under #666. Neither preparation nor research changes #463's shared files.
3. **#457:** settle the open belief decision, later-trace gate semantics and coordinated
   schema/ontology consumers. Use #668's interface requirements and, when available,
   failures from the separately approved model-replay pilot to assess what structure
   is needed. That pilot is not a new prerequisite to #457; do not install every
   proposed mathematical formalism.
4. **#664:** integrate new evidence, publication and delivery under the settled contracts;
   compare inter-admission use with a separately admitted live-update condition. Price
   total player/curator/recall cost and lag before reconsidering any context cut.
5. **#177 / #472:** programs/monitor and practice remain their separately decided phases.
   Offline representation research needs neither executable gameplay libraries nor an
   extra practice instance. Other games remain future-version work.

For each trial, join **source → claim/schema revision → published version → selected
readout → delivery/read → player intent/input → observed effect**. Keep missing links
unknown. This lets a failure be attributed to capture, representation, retrieval,
timing or action use rather than blaming the curator as a whole. Existing telemetry,
source IDs and #463's public emissions are the reuse path; retain no private reasoning.

Freeze the complete role configuration per comparison. The current player is
**GPT-6.1 Terra, medium effort, OpenRouter with the OpenAI provider pinned**, as the
[owner decision log](../decisions/owner-decisions.md) and
[host operations](../operations/player-host.md) state. DeepSeek and other cheaper
player models are future alternatives under #25, not current defaults. The inspected
full-study package also used Terra for recall (262,144 player context, 32,768 recall
context, 39 player images evicted in blocks of 20, reminders scheduled every ten
completed computer-input/program-run calls, subject to availability and budget).
Curator, recall and judge configurations remain explicitly frozen per package; the
player selection does not choose every role's model automatically. Hold corresponding
roles equal across belief/representation arms, charge them all, and test cheaper player
models separately so a model switch cannot masquerade as a memory improvement.

The [belief-method comparison](belief-method-comparison.md) specifies how provenance,
qualitative revision, numerical opinions and optional staleness/pooling models can be
screened on the same CDDA prefixes. It supplies evidence for #457's open choice without
adopting a calculus or becoming a new prerequisite to the decided #463 migration.

## Hypotheses and objectives

The primary question concerns a **frozen learner configuration** across CDDA conditions,
not superiority over every symbolic system or discovery from scratch by its LLM backbone.

| Hypothesis | Falsifying or limiting result |
| --- | --- |
| Representation search improves held-out CDDA task success over both comparators within the same ceilings | No meaningful improvement; gains disappear when search cost is included; only development lineages improve |
| Structural edits contribute beyond ordinary recurrent writing | Editing-disabled execution performs as well; superficial field/name churn explains the apparent emergence |
| Discovered operations transfer or adapt to unseen CDDA situations | Transfer needs engineer-written CDDA fields/rules, or succeeds only on copies of familiar moments |
| Search learns to preserve consequential distinctions | Delayed cues, contradictions, rare exceptions or new goals are lost despite shorter states |

The pilot chooses a meaningful visible task-progress outcome and practical effect
threshold before a deciding batch. Whole-run survival and rare deaths may be too costly to power;
if the affordable source-start count cannot answer the chosen question, report an
exploratory screen or stop. The research proposal is not a claim-deciding protocol.

Two related objectives must not be conflated:

1. **External research objective:** improve task success and decision quality under
   declared inference, adaptation, storage and wall-time limits.
2. **Search objective on development data:** propose compact representations that
   predict relevant observable consequences and make useful readouts at low cost
   across development starts.
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
frozen initial bytes on each final unit; no episode memory carries between independently
assigned final source-starts.

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
updates. Record rejected edits and fallback. This intervention first uses sealed CDDA prefixes with a valid generic record fallback.
Any later live comparison must be separately frozen and admitted; no false facts or
intentionally bad routines are planted in the player.
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

## CDDA start portfolio and experiment sequence

### Diversity is in situations and histories

Vary conditions that require different distinctions, not just random seeds. Candidate
profiles below are experimental assignments, not assertions that these starts already
exist or instructions about how to win. Check what the pinned game's ordinary setup
menus permit; record profiles from visible frames. Keep engine rules/default difficulty
fixed initially so differences are interpretable. Do not select a harder start merely
to make memory look necessary.

| Candidate profile | Contrast to seek in real CDDA | Representation demand to investigate |
| --- | --- | --- |
| Sheltered, limited supplies | A fresh start with protection but few confirmed useful resources | Dependencies, priorities and distinguishing known stock from guesses |
| Exposed, unfamiliar surroundings | A different normal starting situation requiring exploration | Locations/relations, revisitation and uncertain route knowledge |
| Different capabilities or equipment | A visibly different profession/character configuration | Applicability: a method may depend on capabilities rather than being a universal rule |
| Different visible environmental conditions | Day/night, season or weather where normally selectable or encountered | Conditional rules, changed visibility and stale assumptions |
| Established survivor and base | A later naturally reached saved moment | Persistent stock, unfinished work, long-delay recall and accumulated changes |
| Changed location or later return | A genuine continuation after travel or elapsed time | Scope, entity identity, revision and separating old from current state |

Use a small covering portfolio rather than a Cartesian product. Start with three
meaningfully distinct development profiles; after feasibility, a possible coverage
target is six profiles with two independently created worlds per profile. **Twelve
sources is a coverage proposal, not a power calculation or approved run count.** Some
profiles may not be affordable or obtainable; report the uncovered demand rather than
manufacture a save. Skills, traits, exact locations or tactical facts never become
hard-coded fields in shared memory or computer-control code.

### Sources, copies, continuations and leakage

The [reusable-start lifecycle](../development-runs.md#reusable-starts) preserves a
sealed saved game's historical source payload and prepares a fresh current journal.
`tools/starts.py` supports another
sealed source through `--from STUDY`; it does not generate a new survivor or world.
Its [load evidence](../acceptance/2026-11-14-start-load-checks.md) concerns copies of one
saved moment. The [withholding study](../acceptance/2026-11-14-withholding-study.md)
used 60 valid runs from two saved moments of the same lineage, with a fixed v18 store.
That is replication under two conditions, not 60 independent worlds or online learning.

- **Independent source:** genuinely new world/survivor created by ordinary visible
  setup. A new character in an already inspected world still shares that world.
- **Continuation:** a later saved moment in the same world/survivor. Useful for history
  and revision tests, but correlated with earlier moments.
- **Copy:** a hash-verified branch from the same saved moment for paired arms or model
  sampling repeats. More copies reduce execution noise; they add no start diversity.

For each source, record world/lineage/survivor grouping, parent moment, setup options
visible in the UI, first-play identity/time/location frames, source manifest hash,
visible condition labels and split. These are study metadata, never a semantic game
API. Include all acquisition/setup failures and cost. Predeclare a finite acquisition
allowance and assignment rule; no repeated rerolling until a preferred outcome appears.

Create a source through normal play and saving, close the game, seal it, then make fresh
verified copies for comparison. No save editing, developer console or hidden-state
inspection supplies conditions or facts. Load checks consume their copies and are
priced. Shared source bytes pair the initial conditions only; different actions can
produce different later randomness and observations.

Split **entire world/lineage groups** into development, selection and final test before
using their prefixes. Never put an early moment in training and a later continuation
in the held-out test. All previously inspected CDDA lineages are development evidence.
Hold out combinations of conditions and goals where feasible, not just fresh copies.
The LLM's pretraining may already contain CDDA knowledge; fixed models and no supplied
engine ontology do not establish learning from scratch.

### No-spend preparation: real-prefix apparatus checks

Inventory sealed sources and visible evidence at $0 new provider spend. Build one
prefix-only player → curator update → retrieval → player-decision packet cycle using
deterministic stand-ins and an actual development CDDA trace. Check reset, source
references, failed edits, stale coverage, explicit unknowns and all-assigned scoring.
Use one prefix packet/cycle and one deterministic outcome reduction, rather than a
general scorer or power grid. Outcome-reader qualification belongs to #681 after
source feasibility; the later #677 comparison reuses these packets. Calibration is
a plan here, not a result. The old-estimator sizing repair #680 is independent and
does not become a prerequisite to packet preparation or memory adoption #463.
Retain failures; do not launch a model or CDDA to pass this slice. No stand-in success
is evidence of useful learning. Existing traces can establish the apparatus even if
new independent source acquisition needs later paid setup.

Deliver the portfolio manifest/specification, exact candidate language and role prompts,
resource ceilings, scorer reliability plan and conservative complete pilot price.
Include acquisition, save/load checks, all arms, search, curator, retrieval, player,
judges, retries, failed attempts and cleanup. Report what cannot yet be priced. Stop
or reduce scope if this needs a new generic simulator/framework. Appetite: two worker
turns plus lead integration/review and at most two CPU-hours; no new dependency.

### Recorded CDDA replay: representation and reader screening

Use prefixes of whole development lineages. Fix questions independently of candidate
outputs: what remains applicable, what changed, which distinction affects a later
visible consequence, and what cannot be known. Predictions are committed before their
later frames are exposed. No evaluator label or future frame enters the update/read
packet. An absent visual answer stays unknown rather than becoming a confident label.

Compare all three arms on the same evidence and questions. Compare incremental updates
with rebuilding from the same prefix to expose accumulated errors. Inspect whether
state preserved a distinction that retrieval omitted. Score all preassigned queries,
not only topics the candidate chose to retrieve or the player later touched. This
supports observed-policy prediction/retrieval claims, not alternative-action benefit.
Model replay itself requires a priced envelope; no-model packet checks do not fund it.

### Small actual-play pilot before the deciding screen

A proposed development pilot uses **three independent source-starts from three profiles**
and three arms: at most nine player continuations before explicitly priced repeats.
Inspect the first complete cycle before admitting the rest. These are pilot sources,
never final tests. The count is a proposal to price, not an approval or efficacy study.
If new starts cannot be obtained within the priced acquisition allowance, reduce or
stop and state the lost coverage. Do not substitute nine copies of one moment.

For the first feasible integration, curate sealed development prefixes between finite
admissions and deliver each arm's complete published version to its next player.
That tests continued learning and delivery at existing boundaries. Arbitrary-schema
artifacts do not fit the current fixed fact/article gate: first test them offline;
before any live arm, name and implement a supported research readout path or narrow
the live pilot to current supported facts/articles and limit its claim accordingly.
No silent flattening can count as an arbitrary-schema integration result.

Within-admission online recurrence is a later integrated condition through #664 and
the appropriate schema work. Do not change delivery cadence and representation at the
same time and attribute the difference to structure. The player keeps natural context,
ordinary control and its ongoing objective in all arms; no deferred context cut is
introduced to force dependence on memory.

### Frozen comparison on unseen CDDA sources

After the pilot, freeze exact profile definitions, source groups, candidate identities,
updater/reader/search configuration, role routes, capacities, source acquisition rule,
resource limits, stopping rules and analysis. Optimize replay and fixed recurrence as
seriously as the editable arm. Search uses only development prefixes; selection picks
one complete configuration per arm before final sources are opened. The proposed
12-candidate allowance is a maximum to price, not an obligation to spend it.

Pair arms by copied source moment; randomize/counterbalance their execution order.
Reset memory and model session at each independent source assignment. Give each arm
the same permitted visible setup history, initial source information and natural player
context; only the memory treatment differs. Do not seed an inherited player store
with an arm's earlier outputs. Fresh and legacy-derived starts prepare a fresh
supported journal. Arms paired at a current prospective checkpoint take separate
verified copies of the same supported closed pre-arm journal and preserve equal
permitted source access. Keep each sealed source immutable. Repeated samples,
saved moments and query windows remain nested in their source world or lineage.

**Primary live outcome:** a source-specific, predeclared **visible task-progress bundle
achieved while still alive at the finite allowance's end**, with each source weighted equally within profile and
profiles weighted equally. The priced protocol defines its exact predicates, time
boundary and practical threshold from pilot feasibility before final collection.
Score all assigned source trials: deaths, invalid outputs, budget exhaustion and failed
starts remain outcomes. Freeze technical-failure handling in advance and report an
all-assigned sensitivity analysis; never condition the primary on memory being used.
The player receives the ongoing mission, not evaluator milestones or a solution script.

Use targeted progress before a survival claim. Record separately:

- elapsed **in-game time**, decision count, wall time, cost and stop/censoring reason;
- visible new useful supplies, needs improvement and shelter use where independently
  supported; starting possessions are not newly acquired gains;
- exploration/revisits and displacement **only where visible landmarks or map frames
  establish them**; map pixel change is not travel distance, and distance alone is not
  useful progress;
- source-supported distinctions retained/retrieved, contradiction correction, stale
  readouts, uncertainty, migration failures, edit reuse and update-to-use lag;
- catastrophic events and per-profile results alongside averages, without turning a
  small death count into a safety claim.

Success requires useful observed progress against both comparators under declared
ceilings and priced search costs. A structure-specific claim additionally needs the
valid editing-disabled comparison on held-out CDDA prefixes; a live ablation is used
only if its fallback and supported integration are frozen separately. An offline
ablation supports structural contribution on replay only; a live causal attribution
needs a valid live ablation. Invalid-update failures do not prove a relation was useful.

Before a claim-deciding batch, simulate the exact estimator and intervals with paired
arms, world/lineage clustering, continuation dependence, scoring error, budget limits
and complete search-repeat effects. Calibrate multiplicity for every claimed contrast
at familywise 5%, report simulation uncertainty, and target 80% power for declared
useful alternatives across stated variance ranges. Choose source/repeat counts from
this exercise **and the full price**, not from the twelve-source coverage suggestion.
If unaffordable, report an exploratory screen or justified stop, not a confirmed null
or generalization result. Predeclare independent complete search repeats if claiming
a generally better learner; otherwise condition conclusions on the selected bank.

## Practical operation inside the gameplaying system

### Player, curator and retrieval loop

These are **gameplaying responsibilities**, not development-agent assignments or a
requirement for a separate model process per box. The initial research configuration
uses one deciding player and one logical curator writer. Retrieval can be a bounded
curator/read call using the existing recall design. The slower proposer is a mode of
the curator, not a second actor with game control.

```text
visible observations + delivered-action receipts
        |                         |
        v                         v
   deciding player <--- readout --- curator state M, schema S, version v
        |                            ^
        | basic input                | update / revise from visible evidence
        v                            |
       game -------- new observations+

slower curator mode: propose S', migrate a copy, check visible-prefix predictions,
                    publish one complete version or retain the current version
independent evaluator: score sealed outputs; no return path to gameplaying agents
```

| Gameplay responsibility | Inputs and outputs | Learning / authority boundary |
| --- | --- | --- |
| Deciding player | Current view, ongoing objective, recent history and retrieved memory; chooses basic input and may ask a memory question | Owns all real game actions and tactics; may choose an informative action when worthwhile, but no curator request forces one |
| Curator: recurrent update | Previous state/schema and newly available player-visible observations/action receipts; emits cited revisions and uncertainty | Learns an episode/world model and mechanics hypotheses from observed effects; no saves, engine facts or evaluator labels |
| Curator: slower representation search | Its visible-evidence archive, unresolved contradictions, retrieval misses and predictions compared with later visible outcomes | Proposes split/merge/new relation or update/read rules within the frozen language and allowance; no arbitrary generated-code execution |
| Retrieval/readout | Player query/objective, published memory version and recent context | Returns relevant claims, supports, applicability, unknowns and coverage; can be the same curator model, not an obligatory extra agent |
| Independent evaluator | Sealed trial outputs and later outcomes | Reports research scores outside the playing system; never teaches the operating curator with judge answers |

The curator can propose representations for current episode state, reusable mechanics,
or ongoing work, but these are example uses, not mandatory game-specific slots. A
useful distinction may be an entity relation in one game, a conditional rule in another,
or simply a well-maintained record. The reader and the player must be able to consume
what is learned: a schema that only its author can interpret has not improved play.

**One update cycle.** The player observes and acts. The curator receives the delivered
prefix, revises values and explicitly records hypotheses about later observations.
When the corresponding visible outcome arrives, the curator can compare it with its
prediction and revise its own hypotheses. This is ordinary learning from game feedback,
not access to the independent evaluator. An unexpected observation or an unanswerable
query can motivate a structural proposal. The curator migrates a scratch copy, checks
its references and revisits visible-prefix examples, then publishes the whole version
atomically. A failed migration leaves the prior published version usable; it is still
charged as an unsuccessful proposal and follows the frozen invalid-candidate/ending
rule, without silent repair. Retrospective fit is not held-out evidence.

**Two learning timescales.** Episode state and its schema can adapt online under
the frozen learner's policy; generic updater/reader/search-policy configuration changes
only on development data through the outer research selector. A final game's visible
feedback may change its own memory, but never its prompt/configuration in response to
final judge scores. Reset to frozen initial bytes for independent final worlds. A
later continual-learning study would explicitly test carrying generic operations
across CDDA lineages; it must separate reusable operations from game-specific facts and price
order effects. That is a different condition from this reset-based transfer test.
Online rule proposals are state data in M/S, interpreted by the same frozen updater
and reader within the admitted grammar. They do not rewrite host prompts, tool
permissions, budgets or the generic interpreter. Searching those generic updater/reader
definitions is the outer development loop, not unbounded self-modification in play.

### Delivery cadence and staged integration

Start offline with a declared three-observation curator batch and a readout at each
assigned CDDA prefix boundary; tune cadence on development evidence before freezing it. The player is identical across arms; its memory path
changes. Query, observation, token and cost permissions are equal. Tests include a
stale memory read, failed edit, contradicted mechanics hypothesis and a query whose
answer remains unknown, followed by an actual player decision.

For the first real-game integration, keep existing admitted session boundaries: curate
a sealed development prefix between finite admissions and deliver the published version
to the next player. That tests persistent learning and usability, **not** online
recurrence within an admission. The within-admission updater/scheduler remains proposed
work through #664 and the appropriate schema path; this research document does not
turn the existing fixed fact/article gate into an arbitrary-schema runtime.

When a live research integration is separately built and admitted, it should publish
source coverage/version with each readout and measure update-to-use lag. The player
continues with recent observations and available fallible memory while a slow curator
works; curator delay cannot silently become a context cut or a second input writer.
Do not treat an inter-admission result as evidence that this live loop works.

The outer selector ranks generic candidate algorithms with development/selection
scores; final outcomes are opened only after outputs are sealed. Current
[ADR 008](../decisions/008-evaluation-and-spectator.md) isolation remains in force.
Measured roles use explicitly pinned model/provider/effort profiles, equal across arms
for each corresponding role; they need not all use the same model. Charge player,
curator, retrieval and search requests, including failed proposals. No private LLM
conversation or repository tools become an unaccounted memory channel. Development
agents only implement and review these interfaces under S-AGENT; their workflow does
not constitute the agent architecture under test.

### Minimal research interface and artifact ownership

The following is a **proposed study interface**, not a current production schema/API:

| Artifact or operation | Required content / responsibility |
| --- | --- |
| Frozen trial manifest | Split and source-world/lineage/profile identifiers, build/prompt/model hashes, candidate bytes, sampling seed, observation/action permissions and all resource ceilings |
| Visible batch | Ordered source IDs/images or text, previous actions and their delivery status; only the prefix available at that point |
| Candidate | Representation definition, updater/reader prompts or bounded expressions, initial state, parent candidate and declared capacity; no importable production code |
| `update(state, batch)` | Return one new version and source-linked edits; fail as an invalid candidate if shape, budget or references are invalid |
| `read(state, query)` | Return bounded text/records, source references and explicit unknowns; no action or evaluator result |
| `predict(state, test)` | Return a prediction for named future observable tests, recorded before their outcomes; no oracle query |
| Trial receipt | Original request IDs, all retries/failures, publication/read versions, resource usage, state/artifact hashes and ending reason |
| Scoring output | All-assigned source-start/profile metrics, world/lineage groups, paired assignments and uncertainty; stored only on the evaluator side |

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

The first implementation brief owns `tools/recurrence_research/`, its inert protocol
data in `data/recurrence-research/`, and `tests/test_recurrence_research_*.py`, plus
this proposed document if the design changes. Generic tools consume an explicit
specification; selected provider/model profiles belong to the study data.
A minimal package contains source-portfolio metadata, candidate/data validation, real
prefix packet construction, one deterministic score example and a later calibration
and reader-qualification plan. It contains no game generator or general scoring stack.
Worker ownership is split between portfolio/packet
and candidate/scoring files, with the lead owning the manifest and integration. Exact
filenames/interfaces are written in the bounded briefs before either worker starts.
No worker modifies `harness/`, existing host adapters, shared locks, dependencies or
production schemas. A needed change there returns to the lead as a separate decision.
All outputs stay in an owned ignored `.runtime/` study directory; reusable sources are
tracked normally. One-off study tooling is retired when its question is finished.

### Implemented no-model preparation

[`tools/recurrence_research/prepare.py`](../../tools/recurrence_research/prepare.py)
prepares one source inventory, selected real-CDDA prefix subset, inert update/readout
cycle, fixed-question outcome example and proposed role/price worksheet:

```sh
.venv/bin/python -m tools.recurrence_research.prepare --root "$PWD" --spec data/recurrence-research/spec.json --out .runtime/recurrence-preparation
```

The output directory must be fresh. Retained evidence is optional in a fresh checkout;
absent sources produce an explicit unavailable packet. The selected development
subset is three visible frames from #397's second admission, not a complete actor
history. Historical intent/cites/hints and actual downstream readout use remain
unknown. Source annotations are manually checked against those frames. This is a
deterministic stand-in, not a model comparison, learned structure or a qualified
task/survival reader.

[`spec.json`](../../data/recurrence-research/spec.json) fixes the generic candidate,
schema/value-edit separation, paired-source metadata, role prompts and proposed
resource allocations. The worksheet computes conservative configured-price model
bounds, separately for replay and a nine-continuation pilot, including finite new-world
acquisition, load/ending requests and failures. It keeps non-provider costs and source
feasibility unknown. Extra requests, replacements, larger searches and additional
coverage are excluded and need their own price; no balance or envelope is opened.
These proposed prompts are inert data; no host or provider runner is added.

The inventory covers retained reusable-source manifests and their source admissions.
It hashes frozen payload maps to distinguish exact copies from changed payloads;
neither a payload hash nor a study archive hash proves a new world. Related #397
sources stay in one conservative cluster. Other properties remain unknown where no
visible evidence was inspected. Three genuinely independent acquisition slots remain
unfilled; copies cannot satisfy the diversity proposal. The
[preparation record](../acceptance/2026-11-16-cdda-recurrence-preparation.md)
owns the measured output and limits. #681 retains outcome-reader qualification;
#677 can reuse the packets, while supported live integration remains #664/#457.

### Visible outcome feasibility

The fixed development comparison in the [feasibility record](../acceptance/2026-11-17-cdda-outcome-feasibility.md)
**defers** an outcome-reader target: the assigned pairs show visible death and useful
boundaries but do not support a common before/after task-progress bundle with named
identity at the endpoint. Existing starting stock and isolated action messages do not
establish that bundle. The parent primary remains task progress AND alive; clock and
travel remain separate measurements. The record fixes a provisional codebook and
retains unknowns and all assignments, not qualified labels or a final estimand.

#681 needs a specified observable task, supporting positive/negative and failure
cases, endpoint identity and genuinely independent uninspected source groups before
reader qualification. The inspected #397, #642 and #651 cases are related development
evidence, not independent held-out worlds. Price acquisition and independent labels
using the existing worksheet before seeking an envelope. #677 may reuse these cases;
this decision does not gate #457.

## Resource, evidence and delivery decisions

| Boundary | Proposed allowance or decision |
| --- | --- |
| Current change | Proposal, source-backed review and tracker reconciliation only; $0 provider spend |
| First implementation slice | No model/game launch, no new dependency, two worker turns plus lead integration/review; owned packet/scoring execution capped at two CPU-hours |
| CDDA replay / play pilot | Price exact inputs, acquisition, role requests, judges and failures before requesting its envelope; no standing $20 pilot allowance |
| Deciding CDDA screen | Separate priced envelope after pilot; no remainder from another study is reused; no implied $1,500 research allocation |
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
| R-FALSE-CLAIM | All-assigned outcomes, split isolation, calibrated analysis, source/usage receipts, exact comparisons | Simulation, sealing and independent review; finite CDDA source worlds and noisy visible readers still limit claims |
| R-GAME-COUPLING | Generic edit operators, no seeded CDDA ontology and whole-world/lineage holdouts | Portfolio acquisition and review; cross-game problems remain unknown and deferred to future versions |
| R-STUDY-OVERRUN, R-OVERSPEND | One no-spend slice, one capped price pilot, later priced batches and stop rule | Pilot/integration effort; unknown prices and model variance remain |
| R-DELEGATION-ERROR, R-WRONG-MERGE | Disjoint worker ownership, one integrator, exact-candidate review and protected checks | Review/CI time; agents remain fallible |
| R-ARCHITECTURE-DRIFT, R-PRIVATE-DATA | Sealed prefix only, no evaluator-to-player path, same existing secret/isolation ownership | Packet/isolation checks; offline replay does not qualify the live boundary |
| R-TECH-DEBT, R-CONTROL-BLOAT | Reuse existing primitives; keep a small study package and retire it on closure | Maintenance while the question remains open; no general platform is promised |

## Decisions still required and expected outputs

No research result is claimed by merging this proposal. The lead can scope the
no-spend CDDA portfolio/packet/price worksheet within ordinary engineering delegation. Before paid
work, the owner decides the priced CDDA pilot and envelope. #291 and other-game
feasibility are outside this investigation and are not prerequisites. A live curator, context cut,
new belief calculus or production replacement has its own evidence and adoption path.

The discovery outcome ends with: frozen artifacts and costs; an executable comparison
or a justified stop; effects and uncertainty by CDDA profile/source world and complete search repeat;
a structural-contribution reading or an explicit failure to establish it; and an
adopt/reject/defer recommendation with its scope. A useful negative result can close
the research outcome without adopting a representation. Further implementation issues
are created only when a completed slice supplies their prerequisites.
