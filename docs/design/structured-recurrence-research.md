---
owner: lead
status: proposed
date: '2026-11-16'
scope: 'CDDA-only research proposal for structured recurrent memory and representation search across diverse real starts and visible-trace replay. Other games and their unforeseen generalization problems are deferred to future versions. No runtime adoption or study spending is authorized.'
review_trigger: A live run supplies a curator-written fact about an earlier sighting, or the comparison's claims or scope change
---

# Structured recurrence through diverse CDDA starts

## At a glance

Can a curator discover a representation that helps a player make better decisions
across diverse CDDA starts within a common budget? The proposal compares episodic
replay, fixed recurrence and editable representations. Whether editable structure
improves visible play enough to justify its cost remains unknown.

Revisit the [memory study (#666)](https://github.com/CVX-Hull/enactive/issues/666)
when a live run has a curator-written fact about an earlier sighting. At that
point, decide whether the comparison is feasible and worth pricing. Claims of
benefit from delivered memory come from the
[seven-day campaign outcome (#145)](https://github.com/CVX-Hull/enactive/issues/145).
[Decision on measuring memory benefit in campaigns](../decisions/owner-decisions.md#memory-benefit-measured-in-campaigns)

The proposal tests genuine starts within CDDA and keeps the update and read
mechanisms game-independent. Its parent is the
[curated-player outcome (#445)](https://github.com/CVX-Hull/enactive/issues/445).
The [delayed-memory assessment](delayed-memory-assessment.md) specifies choice
enrollment, context comparisons and acquisition across waking periods.

## Research contract and prior evidence

Research cutoff and primary-source retrieval: **16 November 2026**. This is a mechanism
proposal, not a new literature leaderboard. The prior [representation synthesis](../research-memory-representations.md),
[curated memory](../research-curated-memory.md), [belief under conflict](../research-belief-under-conflict.md), [programs](../research-curated-programs.md)
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
| Sun et al., [test-time training (TTT)](https://arxiv.org/html/2407.04620v2), 2024 v2, §§2.1–2.3, 2.7, 4.3 | A recurrent state can itself be a learner; update and readout are optimized in nested loops | Neural sequence learning does not establish that symbolic edits have gradients, sufficient state or useful game transfer |
| Kemp and Tenenbaum, [structural form](https://pmc.ncbi.nlm.nih.gov/articles/PMC2492756/), 2008, model, inference and examples | Jointly select a representational family and its instance using a likelihood and complexity-sensitive prior | Candidate forms and likelihoods are supplied; entities and datasets are already available |
| Littman, Sutton and Singh, [predictive state](https://proceedings.neurips.cc/paper_files/paper/2001/file/1e4d36177d71bbb3558e43af9577d70e-Paper.pdf), 2001, tests and Theorem 1 | Represent state by multi-step action-conditioned observation predictions | Existence in finite partially observable Markov decision processes (POMDPs) does not establish efficient discovery. Selected logs leave untried actions unidentified |
| Tishby, Pereira and Bialek, [information bottleneck](https://arxiv.org/html/physics/0004057), 1999, §§2–3 | Compress while retaining information about specified relevant consequences | Relevance and a suitable distribution must be defined; tokens are not mutual information |
| Ellis et al., [DreamCoder](https://arxiv.org/pdf/2006.08381), 2020 preprint, methods and search analysis | Learn a reusable program language together with the search procedure using it | Primitive language, task likelihood and substantial search are required; uncertain visual worlds are not solved |
| Battaglia et al., [relational inductive biases](https://arxiv.org/html/1806.01261v3), 2018, §§2.2, 3.2, 5 | Shared relational operations and permutation symmetry support recombination | Entity extraction, useful relations and unseen dynamics remain learning problems |
| Berlot-Attwell et al., [Library Learning Doesn't](https://arxiv.org/html/2410.20274), 2024, §§3–6 | Test actual reuse and minimally ablate it at comparable compute | Two mathematical systems do not refute library learning generally; their gains were not evidence of useful direct reuse |

All mappings from these methods to curator agents below are **research hypotheses**.

## Fit with the implemented player, curator and planned designs

### Baseline and the missing connection

The [player host](../operations/player-host.md) runs the deciding player's loop over
visible frames, its objective, recent turns and basic controls. Treat its recent
conversation as part of recurrent state and hold it equal across arms.
The [player-ownership migration (#463)](https://github.com/CVX-Hull/enactive/issues/463)
defines the boundary for public intent, citations and fallible hints. Historical
packets may lack those fields. Use recorded sources and public evidence to connect
a revision to a published version, readout, player input and visible effect.
Keep missing links unknown.

The [curator component](../components/curator.md) owns the published facts and
articles. The [host contract](../contracts/player-host.md#delivered-knowledge-and-recall)
owns delivery from the frozen export. The comparison needs a supported
experimental readout for arbitrary schema data. A revised type or relation is
useful only when the frozen reader and player can interpret its applicability
and source support. The [belief, schema and gate work (#457)](https://github.com/CVX-Hull/enactive/issues/457)
governs any production integration. The [belief-method proposal](belief-method-comparison.md)
examines those methods on matched prefixes. Its results can inform that choice
without becoming a prerequisite to it.

### Learning feedback, freshness and integration

The curator compares predictions with later player-visible observations. A
prospective publication gate may use private later-trace admission tests under
#457. The [independent evaluator](../contracts/evaluation-record.md) scores sealed
final trials outside both paths. Use development and selection scores to rank
generic configurations. Keep final evaluator answers outside the learner.

Measure update freshness in decisions, wall time and game time, with coverage
and version. A coverage stamp records what was read. Applicability still
depends on the fact and its context. Preserving recent player turns lets the
player continue while the curator works. The
[context cut proposal](coverage-gated-context-cut.md#the-cut)
is independent of the comparison.

Within-admission research depends on [live memory integration (#664)](https://github.com/CVX-Hull/enactive/issues/664)
and the applicable schema work. Executable behavior and practice have separate
requirements under [programs and monitor (#177)](https://github.com/CVX-Hull/enactive/issues/177)
and [isolated practice (#472)](https://github.com/CVX-Hull/enactive/issues/472).
The proposed comparison uses the existing player and visible evidence.

Freeze the player model, effort and route in each package. Hold the same
configuration for each corresponding role across arms and include all role
costs. Cheaper-player trials follow the
[responsiveness outcome (#164)](https://github.com/CVX-Hull/enactive/issues/164)
as a separate comparison.

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

For the [source and packet preparation (#668)](https://github.com/CVX-Hull/enactive/issues/668),
a deterministic prefix cycle checks reset, source references, failed edits,
stale coverage, explicit unknowns and all-assigned scoring. It uses actual
development traces. Its results concern the apparatus.

The [belief-method replay (#677)](https://github.com/CVX-Hull/enactive/issues/677)
can reuse the common packets. [Outcome-reader qualification (#681)](https://github.com/CVX-Hull/enactive/issues/681)
depends on eligible visible outcomes and grouped sources. The
[earlier sizing-estimator repair (#680)](https://github.com/CVX-Hull/enactive/issues/680)
is independent of packet preparation and memory adoption.

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

### Proposed actual-play pilot

If the study is revisited, one proposed method is an actual-play development pilot
with **three independent source-starts from three profiles** and three arms,
for at most nine player continuations before priced repeats.
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

A within-admission arm depends on live memory integration and the applicable
schema work. Do not change delivery cadence and representation at the
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
with an arm's earlier outputs. Nothing an arm learns reaches the game's main knowledge
repository during the study; promoting it afterwards is a separate, recorded step
([rationale](../decisions/009-curated-player.md#knowledge-repository-d16)). Fresh and legacy-derived starts prepare a fresh
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

One player makes decisions and one logical curator writes knowledge. The
existing recall design can provide the bounded readout. Slower representation
search is a mode of the curator.

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

A proposed inter-admission comparison curates a sealed development prefix
and delivers the published version to the next player. The
[curator runner](../components/curator.md) is built and tested offline only
and has yet to run beside a real custodian. Delivery of newly published
knowledge to the running player depends on the within-admission integration
and the applicable schema path.

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

### Implemented no-model preparation

The [preparation record](../acceptance/2026-11-16-cdda-recurrence-preparation.md)
documents a deterministic update and readout cycle over one visible-trace prefix.

Use the [frozen specification](../../data/recurrence-research/spec.json) to reproduce
the preparation into a fresh output directory:

```sh
.venv/bin/python -m tools.recurrence_research.prepare --root "$PWD" --spec data/recurrence-research/spec.json --out .runtime/recurrence-preparation
```

### Visible outcome feasibility

The [feasibility record](../acceptance/2026-11-17-cdda-outcome-feasibility.md)
shows that the assigned pairs lack a common, answerable before-and-after
task-progress measure with named endpoint identity.

## Resource, evidence and delivery decisions

| Boundary | Proposed allowance or decision |
| --- | --- |
| CDDA replay / play pilot | Price exact inputs, acquisition, role requests, judges and failures before requesting its envelope; no standing $20 pilot allowance |
| Deciding CDDA screen | Separate priced envelope after pilot; no remainder from another study is reused; no implied $1,500 research allocation |
| Expansion | No new interpreter, representation family, model tier, game installation or extra concurrent game merely because a pilot passed |
| Stop/rescope | Unpriced request or ownership failure, leakage, invalid scoring, budget limit, no affordable calibrated comparison, or no useful result after one full frozen screen |

Retain all failed candidates, seeds and starts; use the existing evidence retention,
ledger and finite-run practices where applicable. Do not reopen a failed admission or
renew resources through a retry.

These proposed study procedures apply existing controls to named risks; they do not
change the project's global control set:

| Risk | How the study reduces it | Cost / remaining limit |
| --- | --- | --- |
| R-FALSE-CLAIM | All-assigned outcomes, split isolation, calibrated analysis, source/usage receipts, exact comparisons | Simulation, sealing and independent review; finite CDDA source worlds and noisy visible readers still limit claims |
| R-GAME-COUPLING | Generic edit operators, no seeded CDDA ontology and whole-world/lineage holdouts | Portfolio acquisition and review; cross-game problems remain unknown and deferred to future versions |
| R-STUDY-OVERRUN, R-OVERSPEND | One no-spend slice, one capped price pilot, later priced batches and stop rule | Pilot/integration effort; unknown prices and model variance remain |
| R-ARCHITECTURE-DRIFT, R-PRIVATE-DATA | Sealed prefix only, no evaluator-to-player path, same existing secret/isolation ownership | Packet/isolation checks; offline replay does not qualify the live boundary |
| R-TECH-DEBT, R-CONTROL-BLOAT | Reuse existing primitives; keep a small study package and retire it on closure | Maintenance while the question remains open; no general platform is promised |

## Decisions still required and expected outputs

Any future paid comparison needs the owner's decision on its priced envelope.
A live curator, context cut, production representation or belief calculus
has its own adoption decision. The [portability outcome (#191)](https://github.com/CVX-Hull/enactive/issues/191)
carries the cross-game aim. This proposal tests transfer within CDDA.

The discovery outcome ends with: frozen artifacts and costs; an executable comparison
or a justified stop; effects and uncertainty by CDDA profile/source world and complete search repeat;
a structural-contribution reading or an explicit failure to establish it; and an
adopt/reject/defer recommendation with its scope. A useful negative result can close
the research outcome without adopting a representation.
