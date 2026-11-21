---
owner: lead
status: active
scope: 'World-scoped curator facts and types, with the current curation, delivery and measurement boundaries'
review_trigger: The curator-fact/4 world-scope migration takes effect, or a change to its scope, provenance or delivery assumptions reopens the field table
---

# General memory: curation, delivery and judged measurement

## At a glance

- **Question.** How can the curator store facts about one game world while keeping
  game-wide facts reusable?
- **Working design.** The [field table](#the-next-format-the-field-table-for-curator-fact4-and-curator-type2)
  defines the move to `curator-fact/4` and `curator-type/2`. The current store uses
  `curator-fact/3`.
- **Unknown.** The effect of delivered memory on play is unconfirmed.
  [Withholding study](../acceptance/2026-11-14-withholding-study.md)
- **Owner decisions.** The field table cites the scope decisions that govern the
  migration. It identifies no additional decision to adopt these fields.

Terms are in the [glossary](../glossary.md).

## The principle

The charter's [portability constraint](../charter.md) and P-GENERALITY, and the owner's
instruction to follow the bitter lesson: prefer general methods that improve as models
improve over hand-built knowledge of one game.

- **The model decides what matters**: what to record, how to word it, what to merge or
  retire, and what is relevant now. Software keeps what no model should decide:
  provenance, order, versions, the gate's structural checks and the cache rule.
- **No rule names a kind of thing in a game.** "Goods have a place" or "drop facts older
  than a day" are guesses about one game.
- **Measures are worded in game-neutral terms**, and the facts they judge come from the
  trace and the store, not a list written in advance.

## 1. The fact format and the curator

### The format, `curator-fact/3`

| Field | Required | Meaning |
| --- | --- | --- |
| `schema`, `id` | yes | `curator-fact/3` and the record's identifier |
| `type` | yes | a type from the curator's ontology |
| `text` | yes | one durable claim, in the curator's words; where and when, when they matter, are in the text as the screen showed them |
| `citations` | yes | frame source ids checked under the session's admission or grooming rules |
| `subject` | no | a short name for what the fact is about, when it is about one thing |
| `seen` | written by software | the trace position of the latest cited frame: an order, not an age, since one step can span hours of play |

Facts carry `scope.game`. The [session contract](curator-session.md#submissions)
defines the exact fields and operations for facts, articles and types.

### The next format: the field table for `curator-fact/4` and `curator-type/2`

This table specifies the next format for the
[world-scoped fact store migration (#835)](https://github.com/CVX-Hull/enactive/issues/835).
`curator-fact/3` is the current contract. The rules in this section apply to
`curator-fact/4` and `curator-type/2`.
[World memory first](../decisions/owner-decisions.md#world-memory-first),
[no belief value](../decisions/owner-decisions.md#no-belief-value-in-the-fact-store) and
[a separate world label](../decisions/owner-decisions.md#a-separate-world-label)
record the owner decisions.

**Why it changes.** The only scope the gate validates today is a game, and nothing the
curator reads names a world. A fact such as "the trunk of this car held an
extinguisher" is true of one world and has no place to say so.

#### World and lineage

- **A lineage** is a chain of admissions that continue one survivor
  ([glossary](../glossary.md)). The run package already freezes it as the `lineage`
  label, with the admission's position in it.
- **A world** is the game world a lineage plays in. It is named by an opaque label,
  printable ASCII of 1 to 40 characters, that the operator chooses when the world is
  created and that is unique among the worlds of one game's repository. The package
  gains a `world` label for it. Several lineages may share a world.
- **Who writes them.** The operator, in the frozen package's labels. A package with a
  lineage must name a world; a package may name a world with no lineage; both may be
  null, as in a study that wants neither.
- **Not verified against the game.** Recognising a world from a screen is the playing
  system's business, and nothing here does it. What software can check is consistency
  across what the repository has cited, below. A wrong label that is consistent is not
  caught.
- **A closed manifest changes.** Adding `world` moves the campaign manifest to
  `campaign-run/11` with its validator, fixtures and campaign procedure. The driver
  accepts only the new version. The evaluator reads earlier versions through its closed
  archive index. The decision log holds the
  [eligibility rule](../decisions/owner-decisions.md#archive-index-holds-cited-sessions)
  and the [approved sessions](../decisions/owner-decisions.md#eleven-version-ten-sessions-join-the-archive-index).
- **Sealed sessions.** A session sealed before the `world` label supports only
  `game` facts. [Trace workbench](trace-workbench.md#projection)

#### A fact

New or changed fields are marked.

| Field | Written by | Rule the gate checks |
| --- | --- | --- |
| `schema` | curator | `curator-fact/4` |
| `record`, `id`, `type`, `text`, `citations`, `subject` | curator | as in `curator-fact/3`. An article keeps sharing the schema name, as `curator-fact/4` with `record: article`; its fields do not change and it has no `scope` |
| `known` (new) | curator | one of `observed`, `inferred`, `hinted`. `observed`: the cited frames show it. `inferred`: the curator concluded it from what the cited frames show. `hinted`: it rests on a player hint visible in the cited steps. The gate checks the value is one of the three and nothing more |
| `scope.game` | curator | equals the repository's game, as now |
| `scope.level` (new) | curator | `world` or `game`. `world`: true of the world it was seen in. `game`: true of the game in any world. A submitted `scope` holds exactly `game` and `level` |
| `scope.world` (new) | software | present on a `world` fact only: the one world label shared by every cited frame's session, read from provenance and never from a submission. The fact is refused if its citations name two worlds, or cite a session with no world. A stored `scope` holds exactly `game` and `level`, and `world` on a `world` fact |
| `seen` | software | unchanged, in shape and meaning: the trace position of the latest cited frame, an order and not an age. It carries no world |
| `published_in`, `session`, `retyped` | software | unchanged |
| `superseded_by`, `retired` | software | the fields are unchanged; which facts may replace or retire which is ruled below |

- **Who asserted it is not a field.** ADR 009 lists four kinds of asserter. Today only
  a curator session submits, and `session` already names it. The field arrives with
  the second kind of asserter, in the change that adds that producer.
- **Time.** The store keeps one time for a fact: `seen`, the order of its latest
  sighting. It keeps no game time and no wall time. A game clock reading is the
  playing system's interpretation of a screen, and wall time across a save and a
  reload says nothing about the world. Where the time matters to the claim, the
  curator writes it in `text` as the screen showed it. This settles the conflict with
  ADR 009's sentence that every assertion carries the game time and wall time
  observed: that sentence is not the plan. A consequence: a fact's age in game time
  cannot be computed from the store.
- **No belief value.** A fact has no belief, confidence or weight field, and the table
  reserves none. A fact is current, superseded or retired, and it links to its source
  frames. If the [belief-method comparison (#677)](https://github.com/CVX-Hull/enactive/issues/677)
  supports a model,
  adding one is a second migration with its own justification.

#### Provenance, and the checks it allows

- **The join.** A frame's source identifier begins with the sealed identifier of its
  session. The repository's provenance gains a map from that sealed identifier to the
  session's directory name, world, lineage and admission position, written by software
  at publication. Frame positions keep their four keys, so `seen` and an article's
  `last_confirmed` keep their shape. A current citation and a citation inherited by
  grooming resolve the same way: through the identifier in the citation itself. Frame
  ordering today is keyed by a session's directory name, so the map also holds that a
  directory name belongs to one sealed identifier.
- **Where the labels are trusted from.** Software takes a session's labels from its
  package manifest only after checking three things: the manifest is the current
  version, the manifest names the same session as the sealed store, and its digest is
  the one the supervisor recorded for the run. When any of that evidence is missing,
  the session has no world. The [trace projection](trace-workbench.md#projection) does
  the checking: it reads the manifest and the supervisor's record as files and imports
  no campaign code. A staged
  snapshot of a session that is still being played carries the same manifest and
  supervisor record, so its labels are verified in the same way before it first
  publishes; otherwise the session would be recorded with no world and keep none.
- **Consistency the gate enforces.** A publication is refused when a session is
  already recorded with a different world, lineage or position; when two sessions
  claim the same lineage and position; when one lineage appears with two worlds; or
  when a directory name appears with two sealed identifiers. These checks read every
  compatible tagged version, not only the current one, so that restoring an older
  version does not free a lineage position a later version used. A session recorded
  with no world stays so.
- **The stored-repository validator and restore** check the stored shape of `scope`,
  which differs from the submitted shape by the software-written `world`, and that a
  `world` fact's `scope.world` equals the recorded world of every session it cites.
- **Replacing and retiring across scopes.** A fact may supersede only facts of its own
  level and, for `world` facts, its own world. A `game` fact cannot replace a `world`
  fact, a `world` fact cannot hide a `game` fact from other worlds, and one world
  cannot replace another's fact. A `world` fact is retired only on citations from its
  own world. The validator enforces the same on a stored repository. Turning a `world`
  fact into a `game` fact is promotion, and is not possible until promotion is
  designed.

#### Articles, and what the gate cannot see

- **An article's claims may cite only `game` facts.** The gate refuses an article that
  cites a `world` fact, at publication and on restore. In the next format grooming must
  file every current `game` fact in an article; `world` facts stand alone. Under
  `curator-fact/3` grooming files every fact, and that stays true until the migration.
- **This is a structural guarantee, not a semantic one.** The gate checks references.
  It does not read prose, so it cannot stop a curator writing one world's detail into
  an article's title, lead or claim text, or marking a fact `game` that is true of one
  world. The curator's instructions say to keep article prose and `game` facts true of
  the game in any world. The gate's check of a `game` scope is deferred with promotion:
  ADR 009 has it accept a game-level scope only with evidence from two worlds, and
  until that later part exists a `game` fact is accepted on the curator's word, as
  today.

#### A type

| Field | Written by | Rule |
| --- | --- | --- |
| `schema` | curator | `curator-type/2` |
| `name` | curator | the type's own identity, unique in the ontology, as now |
| `description` | curator | the definition, as now |
| `fields` | curator | a list of field names, as now |
| `identity` (new) | curator | a list of names, each from `fields`, that the curator says make two facts of this type the same thing; may be empty. The gate checks only that each name is in `fields` |
| `reason` (new) | curator | a non-blank string: why this type is needed and how it relates to the existing ones. Required on every type an `add_type` adds and on every type a revision writes. The gate checks only that it is not blank |
| `published_in` (new) | software | the knowledge version in which the type was added or last written by a revision. Restore keeps it as stored, and the validator checks it names a tagged version no later than the snapshot |
| usage | computed | the count of current facts of the type. Not stored; shown in the session brief |
| parent | deferred | not in this format; see below |

- **Identity is guidance.** A fact has no typed values, so the gate cannot compare two
  facts by a type's identity names. They tell the curator and grooming what counts as
  a duplicate.
- **Reuse, specialize or justify.** The gate can require that a new type says why it
  exists, and that is all. It cannot judge the reason. It cannot see reuse, since a
  revision can also write a type. A specialization is stated in `reason`.
- **No parent field.** ADR 009's optional parent type is not in this table. A parent
  needs a revision operation that can change a parent and its children together, and
  the revision actions the gate has (merge, split, rename, deprecate) cannot. It is a
  later part with that operation.
- **Type versions.** A fact does not store the version of its type. Two rules make
  the definitions recoverable. Every fact in a submission must name a type that exists
  once the submission is applied, including a fact added and retired in one batch, so
  the snapshot named by a fact's `published_in` always holds the definition it was
  written under. And whenever a submission replaces a definition under a name the base
  snapshot already had, by a revision or by deprecating a type and adding one of the
  same name, it must assign every fact that was current under that name in the base
  snapshot and is still current once the submission is applied, so each gets a
  `retyped` entry even when the name does not change. A fact the same submission
  retires or supersedes is not assigned, and neither is one it adds. Today such a
  replacement can leave the surviving facts unassigned. The
  definition in effect now is the current type's. A player's query result carries the
  snapshot version and the type name, as now.
- **Where the rest of ADR 009's list goes.**
  - Shown in the session brief, computed at read time: flags for types with no current
    fact and the nearest existing types
    ([type flags in the session brief, #833](https://github.com/CVX-Hull/enactive/issues/833)). The gate does
    not return nearest types for a proposal.
  - Later parts, not in this migration: the parent type, the actor's ontology card and
    definition lookup, and the flag for a type no reader has used, which needs read
    records the store does not have.
  - Dropped, because nothing writes or reads them: the staleness hint, stored examples,
    and usage statistics beyond the count.

#### What moves, and what does not

- **An old repository can be neither read nor written.** The repository schema name
  moves with the two contracts, to `curator-knowledge/3`. The refusals differ by path.
  A repository wholly in the old format fails as soon as its published state is read,
  with the metadata message "start a new repository", which a submission reports as a
  failed publication. Foreign records behind current metadata are caught by the
  session's guard and by the gate's check of the stored history. Restore reports an
  incompatible or unavailable history. The screen checks have their own messages for a
  wrong layout and a wrong record schema. The exporter checks only the metadata today
  and would project a foreign record; in the next format it refuses any record that is
  not of the current schema.
- **A fresh start.** The migration starts a new repository, at its first version, and
  new working state. Old working repositories, session state and study draws are not
  carried over; sealed stores stay as evidence.
- **Delivery keeps its shape.** `delivered-knowledge/1` and the host input contract
  do not change. The exporter copies a fixed list of fact fields (`id`, `type`,
  `text`, `subject`, `seen`), none of which changes shape. What changes is which
  standalone facts it exports. The world label itself is never written into anything
  the player sees.
- **The world is bound at freeze, and checked at preflight.** The exporter exports
  every `game` fact, every article and the `world` facts of one world; with no world it
  exports game facts and articles only, as today. It writes two things into the
  package's private full file, which the player never receives: the world it selected,
  or that it selected none, and the digest of the delivered file it wrote. Package
  preflight refuses a package whose private record names a different world from its
  `world` label, or a different digest from the delivered file's. So a manifest whose
  `world` was changed after the export, and a delivered file whose bytes are not the
  ones the exporter recorded, are both caught. Two exports that produce the same bytes cannot be told
  apart, and need not be.
  The delivered file itself still does not name a world.
  The campaign procedure's rule that no player-visible input is derived from a label
  gains this one exception.
- **Study draws.** The same selection applies on both of the exporter's paths, the
  package export and the study draw, before anything is drawn. The private full file is
  that selected current subset. A draw becomes `withholding-study-draw/2` and records
  two things more: the commit that the version's tag names, because a new repository
  starts its version numbers again, and the world it was drawn for, or none. Applying a
  draw checks the version, that commit, the world and the unit layout, and an earlier
  draw is refused. A study that needs one layout across its starts uses packages with
  no world.
- The [session design](curator-session.md#readers-that-move-with-the-fact-and-type-contract)
  identifies the readers that move together.

#### What this table settles, and what it leaves

The field definitions depend on the
[trace session identity contract (#834)](https://github.com/CVX-Hull/enactive/issues/834)
for verified session labels. The [schema migration (#835)](https://github.com/CVX-Hull/enactive/issues/835)
moves the manifest, repository and study draw together with their readers, validators
and messages.

### Grooming

A grooming session reorganizes the published store between admissions by merging and
retiring facts, revising types, normalizing subjects and updating articles.
[Admission and grooming rules](curator-session.md#admission-and-grooming)

Grooming addresses growth without a hard store cap. The number of current facts and
the size of the record file measure different things because the file also keeps
articles and superseded records. [Groomed store measurement](../acceptance/2026-11-13-curator-scoring.md)

Facts are hypotheses. Each article shows when it was last confirmed, and the player
is told to check a fact cheaply before relying on it.

### Articles over facts

Facts stay the unit of evidence; articles are the unit of reading, as in an encyclopedia
where a page's lead gives the point and its references and links give the rest.

| Part | What it holds | Who writes it |
| --- | --- | --- |
| Title | the subject, in the curator's words | the curator |
| Lead | one or two sentences a player can act on without reading further | the curator |
| Body | the claims, each citing the fact ids it rests on | the curator |
| Links | other articles a reader may want next, by title | the curator |
| Last confirmed | the latest sighting among the facts it cites | software |

- **Written in the grooming session.** The curator groups facts into articles, writes and
  revises leads, splits or merges articles, and links related ones. Which subjects get
  an article, and what links to what, are its choices, so the structure assumes nothing
  about a game.
- **Every sentence traces to a screen**: an article cites facts, and a fact cites frames.
- A standalone fact has its own index line in delivery.
  [Gate checks and filing rules](curator-session.md#gate-v0)
- **Reading more.** `player_knowledge_read` returns an article or a fact by its id or
  title; `player_knowledge_query` searches articles and facts together
  ([player guide](../player-guide.md#delivered-knowledge)).
- **Format.** Articles are a second record kind in the same knowledge repository, in the
  same contract version as facts (`curator-fact/3`).

### How the curator improves

Score a curator variant on sealed development admissions. Compare its published facts
with later visible actions and re-observations. This measures relevance to the sealed
play. [Curator scoring method and limits](../acceptance/2026-11-13-curator-scoring.md#method)

## 2. Delivery: making the player use memory

The briefing carries selected article leads and an index for the actor's frozen
knowledge. Recall can add reminders during play. The player can follow a link or search
for more. [Delivery boundary](player-context.md#the-delivery-boundary)

The reminder cadence trades off timeliness, request cost and repetition. Reminders
persist in the actor's history, so their text contributes to subsequent requests.
[Measured delivery cost and prompt burden](../acceptance/2026-11-14-recall-fix-delivery-check.md)

[Owner decision of 13 November 2026 on knowledge delivery, "Yes, in that order"](../decisions/owner-decisions.md#in-force)

## 3. Measurement

### Is memory used? On every sealed run

Judges label windows where a delivered, read or indexed fact could matter. The
[standing use measures](../contracts/evaluation.md#adjudication-and-the-standing-use-measures)
define the rates for use, rediscovery, stale or false advice, and recall precision
and silence. A player's citation is evidence for the judge.

### Does memory help? Withholding within each start

The study withholds each unit in half the starts copied from the same sealed moment
and compares the unit with itself. The
[study design](../contracts/evaluation.md#the-withholding-studys-design-withholding-study-draw1)
defines the units, the draw and delivery exclusions. The
[analysis](../contracts/evaluation.md#the-withholding-studys-analysis-withholding-study1)
defines blind judging and the outcome, which separates active lookup from passive
re-exposure.

This estimates the effect of delivery for the tested units while half the store is
available. Delivery can change which topics play touches and can add distraction
beyond the units measured. A handoff, another article's prose or independent
re-observation can expose withheld knowledge. The
[study's sizing method](../contracts/evaluation.md#the-withholding-studys-sizing-withholding-study-simulation2)
sizes any repeat. Under the [owner's decision of 20 November 2026](../decisions/owner-decisions.md#in-force)
("Live run, then campaigns"), a claim that delivered memory improves play comes only from
the seven-day campaign outcome ([#145](https://github.com/CVX-Hull/enactive/issues/145)).

### Game-neutral judging

The [evaluation contract](../contracts/evaluation.md#packets) defines the packets and
their token budget. Annotators identify facts from the visible evidence that a later
actor could use.

## 4. Judges as the standing measure

Two judges independently label windows and a third adjudicates disputes. Reported
rates use the adjudicated labels and report agreement, disputes and uncertainty.
[Adjudication and reporting](../contracts/evaluation.md#adjudication-and-the-standing-use-measures)

The [change checks](../contracts/evaluation.md#checks-of-a-changed-judge) use the
frozen owner-labelled anchor set for model changes and compare judges' agreement
on frozen stretches for changes to their instructions. Leniency, missing evidence
in long contexts and shared errors limit their judgments.

## Limits

- **The outside evidence was read in summaries**, and none of it is on games played from
  screenshots. Figures quoted from it are leads.
- **No source runs withholding inside long game episodes**; the design is new here.
- **The recall model's benefit is shown on other kinds of task**, and an untrained small
  one did harm there.
- **One game and one lineage** produced every measured number here.

## Sources

Read on 13 November 2026, mostly as summaries.

- Proactive memory agent beside an actor:
  [Remember When It Matters](https://huggingface.co/papers/2607.08716).
- Models under-use memory tools: [MemTrack](https://arxiv.org/abs/2510.01353).
- Editing memory against what exists: [Memory-R1](https://arxiv.org/abs/2508.19828);
  Mem0. Offline consolidation: [Letta sleep-time compute](https://letta.com/blog/sleep-time-compute).
- Context as a budget: [Anthropic, effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).
- Stale memory: [STALE](https://arxiv.org/abs/2605.06527);
  [When Memory Lies](https://arxiv.org/abs/2608.04574).
- Judges: [AgentRewardBench](https://arxiv.org/abs/2504.08942);
  [Online-Mind2Web](https://arxiv.org/abs/2504.01382);
  [TRAIL](https://arxiv.org/abs/2505.08638).
- Judges with few human labels: [PPI](https://arxiv.org/abs/2301.09633);
  [PPI++](https://arxiv.org/abs/2311.01453);
  [active statistical inference](https://arxiv.org/abs/2403.03208);
  [stratified PPI](https://arxiv.org/abs/2406.04291).
