---
owner: lead
status: active
date: '2026-11-13'
scope: 'Changes decided to the player''s memory after the memory screen''s gates (#460, #386): a game-neutral fact format and a curator that grooms the store into articles over facts, the briefing''s leads chosen by a recall model, reminders from a recall model during play, measurement of use on every run and of benefit by withholding facts within each start, and model judges as the standing measure. Amends the active context design (player-context.md). Built on the three gate records of 13 November 2026, an audit of the memory stack for game coupling and dated outside sources. Decided by the owner on 13 November 2026. Built: the format, articles and grooming (#460), the judges and the withholding simulation (#386), delivery with the briefing and reminders (#461); not built: the cut and curator sessions during play'
review_trigger: The withholding simulation reports, delivery is first measured in play, or a measurement contradicts a premise stated here
---

# General memory: curation, delivery and judged measurement

## At a glance

- **Question.** After the gates, how should the curator, the briefing and the measurement
  change so that memory is general across games, is actually used by the player, and can
  be shown to help at a price the project can pay?
- **What the gates showed** ([brief gate](../acceptance/2026-11-13-curator-brief-gate.md),
  [price pilot](../acceptance/2026-11-13-session-price-pilot.md),
  [measure gate](../acceptance/2026-11-13-memory-measure-gate.md)):
  1. **A curator told what to record stores it**: all four lost facts, against one before.
  2. **The store keeps growing**: 279 records after about 1,900 decisions, about 6,000
     bytes for every 20. The curator can supersede a fact but cannot retire or merge one,
     and its brief asks it to record every item.
  3. **Sessions are fast and not small**: a median of \$0.20 and 99 s for 20 decisions,
     inferred at two to three times the play they cover when the prompt is bounded.
  4. **A comparison between arms is dear**: \$165 to \$208 of play for two arms at the
     measured values, \$93 to never across the intervals.
  5. **The judges agree with each other** (κ 0.80) and with the owner's blind answers on 18
     of the random 20. On touched pairs the blind answers differed on 9 of 12 and the
     checked answers on 2 of 12. Which is nearer the truth on engagement is not known.
- **What is wrong with what we built.** Its code names no game, but its schema and
  instructions assume places and goods: required places and game times, a fixed
  `place_with_goods` kind, judge labels about going to a place. The format was designed
  around places and goods after the four losses, though the brief named none of them. The rows are added to the architecture's
  [current coupling](../architecture.md#game-family-portability) table.
- **Decided by the owner on 13 November 2026** ([decisions](#decisions)):
  1. **Format.** The fixed kinds and the required place and time go; ADR 009's
     model-proposed types, citations and order of sighting stay. Retiring and merging are
     added.
  2. **Curator.** A grooming session between admissions reorganizes the whole store into
     [articles over facts](#articles-over-facts): a lead, a body citing facts, and links,
     as in an encyclopedia. No hard cap.
  3. **Delivery.** The briefing stays where the context design has it. A recall model,
     not a kind, chooses which articles' leads each actor gets; every other article has
     an index line, and the player follows links or searches for more. Then, during play,
     it may add a short reminder, or say nothing, as a notice that stays in the history.
  4. **Measurement.** Use of memory is judged on every sealed run. Benefit is measured by
     withholding each unit of the store in half of a study's starts, once a simulation
     has sized it.
  5. **Judges** are the standing measure, without further audits by the owner; the
     measure gate's 30 owner labels are the anchor set.
  6. **The cut** is not built yet.
- **Not known.** Whether delivery helps: the full withholding study suggests a benefit
  limited by the measure, not a confirmed one
  ([record](../acceptance/2026-11-14-withholding-study.md)); whether a recall model helps
  or distracts in this game; whether grooming holds the store's size; whether the owner's
  blind answers or the judges are nearer the truth on engagement.

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
| `schema`, `id` | yes | as now |
| `type` | yes | a type from the ontology, proposed and kept by the system as [ADR 009](../decisions/009-curated-player.md) decided |
| `text` | yes | one durable claim, in the curator's words; where and when, when they matter, are in the text as the screen showed them |
| `citations` | yes | frame source ids inside the session's window, checked by the gate |
| `subject` | no | a short name for what the fact is about, when it is about one thing |
| `seen` | written by software | the trace position of the latest cited frame: an order, not an age, since one step can span hours of play |

- **Removed:** the four fixed kinds, `place`, `game_time`, and `statement` (renamed
  `text`). `scope.game` stays.
- **Operations:** `add_fact`, `supersede_fact` with one or more ids, `retire_fact` with
  a reason and citations, and `add_type`.
- **Migration.** One contract with no shim (S-MIGRATION). `curator-fact/3` is the one
  current contract and earlier ones are refused. Sealed stores stay as evidence.
- **Also in a record, not in the table above:** `record` (`fact` or `article`), which
  the curator writes on both, and `scope`, which the curator writes on a fact only (an
  article has none); and `published_in`, `session`, `superseded_by`, `retired` and
  `retyped`, which software writes. The
  [session design](curator-session.md#submissions) gives the exact shapes.

### The next format: the field table for `curator-fact/4` and `curator-type/2`

**Designed, not built.** This table fixes, once, what a fact and a type carry after
the single migration that
[the schema migration leaf](https://github.com/CVX-Hull/enactive/issues/835)
implements. Until that merges, `curator-fact/3` above is the contract, and every rule
in this section is a rule of the next format only. It acts on three owner decisions of
20 November 2026 in the [decision log](../decisions/owner-decisions.md):
[world memory first](../decisions/owner-decisions.md#world-memory-first),
[no belief value](../decisions/owner-decisions.md#no-belief-value-in-the-fact-store) and
[a separate world label](../decisions/owner-decisions.md#a-separate-world-label).

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
- **A closed manifest changes.** The label set is closed, so adding `world` makes a new
  campaign manifest version, `campaign-run/11`. The validator, the package fixtures and
  the campaign procedure move with it; the driver accepts only the new version. The
  evaluator reads an earlier manifest version only for sessions listed in its closed
  archive index, and `campaign-run/10` has no entry there because it is current. Adding
  to that index needs an owner decision that names the sessions and their recorded
  versions ([S-MIGRATION](../standards/migration.md)); the decision for the `world`
  label does not include one. Until it is made, sealed `campaign-run/10` sessions are
  not readable through the evaluator once the version moves. The schema migration leaf
  puts that decision to the owner before it is built. Those sessions have no world.
- **Sealed sessions.** A session sealed before this migration names no world. It
  supports `game` facts only, unless
  [the identity leaf](https://github.com/CVX-Hull/enactive/issues/834) finds a
  trustworthy way to give it one.

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
  frames. If the belief comparison
  ([#677](https://github.com/CVX-Hull/enactive/issues/677)) later supports a model,
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
  the session has no world. Which module does the checking, given that the trace
  projection may not import the campaign code, is for the identity leaf. A staged
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
    ([the brief leaf](https://github.com/CVX-Hull/enactive/issues/833)). The gate does
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
  `world` label, or a different digest from the delivered file's. So a manifest edited
  after the export, and a delivered file whose bytes are not the ones the exporter
  recorded, are both caught. Two exports that produce the same bytes cannot be told
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
  lists every reader that moves.

#### What this table settles, and what it leaves

This table settles what a fact and a type carry, who writes each field, the rules
across scopes, and which contracts move together. It is not the implementation. Two
leaves must settle these before they are built, and each is briefed from this table:

- [The identity leaf](https://github.com/CVX-Hull/enactive/issues/834): which module
  verifies a session's manifest against its sealed store and the supervisor's digest;
  the trace projection's next version; and whether a sealed session can be given a
  trustworthy world.
- [The schema migration leaf](https://github.com/CVX-Hull/enactive/issues/835): the
  exact stored shapes and messages; the archive index entries for retained sessions;
  what each evaluator, viewer and ledger reader does with the `world` label; and the
  order in which the manifest, the repository and the study draw change inside the one
  migration.

### Grooming

- **The curator already sees the published facts** and is told not to repeat them. What
  it lacks is a way to retire or merge them, and a brief that does not ask for every
  item.
- **A grooming session between admissions** reads the whole store and the last
  admission's citations, and reorganizes it: it merges facts, retires facts a later frame
  contradicts, revises types as ADR 009 allows, makes subject names consistent, and
  writes and revises the [articles](#articles-over-facts) that file every fact. Outside
  systems that edit against what exists (Mem0,
  Memory-R1, Letta's sleep-time agents) keep their stores more compact. Cost: one more
  curator session per admission, inferred at the gate's \$1.16 to \$4.19 a session.
- **No hard cap**, as the owner decided. The store's size after grooming is measured in
  the first paid grooming run, which is asked of the owner with its price.
- **Facts are hypotheses.** Each article shows when it was last confirmed, and the player is told
  to check a fact cheaply before relying on it. Outside work finds agents follow stale
  notes into harm.

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
- **The gate checks structure only**: every cited fact id and every link resolves to a
  current fact or article. After a grooming session every current fact belongs to at
  least one article; between groomings, facts a session added stand alone and have their
  own index lines until the next grooming files them. It does not judge what an article
  says.
- **Reading more.** `player_knowledge_read` returns an article or a fact by its id or
  title; `player_knowledge_query` searches articles and facts together
  ([the delivery boundary](player-context.md#the-delivery-boundary)).
- **Format.** Articles are a second record kind in the same knowledge repository, in the
  same contract version as facts (`curator-fact/3` gains its article record); no shim.

### How the curator improves

- **Scored on sealed replays.** A curator variant runs over a fixed set of sealed
  admissions, and the judges score its store against what later frames needed: facts the
  player later acted on or found again, weighted above facts never needed again. The
  existing probe annotations (`data/evaluation/probes/397`) already mark re-observations.
- **The four lost facts become one test among many**, so a brief cannot be tuned to them.
- **Cost** about \$16 a variant at the brief gate's rates; a consolidating curator may
  cost more, and the first run measures it.

## 2. Delivery: making the player use memory

The read audit found 8 memory reads in 98 traces and none by an admission's first actor
([record](../acceptance/2026-11-13-memory-read-audit.md)). Outside work finds the same:
models under-use memory they must ask for (MemTrack). So the player should not have to
ask. The [context design](player-context.md#2-a-briefing-from-the-curators-store) already
puts a briefing in every actor's first message and appends later differences as new
messages, which keeps the provider's cache: every request extends the previous one byte
for byte (`tools/player_host/host.mjs`, the notice rule). This note keeps that and
changes two things.

1. **A recall model chooses the leads.** The briefing carries the
   [articles](#articles-over-facts): the leads of the articles a recall model chooses for
   this actor from its first message (the mission and any handoff context) and the
   article index, and one
   index line (title and lead's first clause) for every other article. The player follows
   a link or searches only when it wants more. Relevance is judged by a model, so it
   holds for any game.
2. **Reminders during play.** At a fixed cadence (every N completed inputs, N pinned per
   run: by the lead for the withholding pilot, then from development play's measurement), the recall model reads the player's recent tool calls, the latest
   screen and the article index, and answers with up to a few article titles and their
   leads, or with nothing. It runs beside the player and never blocks it; its answer is added as a notice
   to the next request after it finishes, and stays in the history, so the cache holds.
   A reminder may arrive a decision or two late. Like the briefing, it is labelled as
   fallible knowledge, not instructions, as ADR 009 requires.

**Curator sessions during play** stay in the design as the owner decided ("Yes, priced
first"). Reminders do not depend on them: the recall model reads the published store,
whatever version it is. Sessions during play make the store more current.

**What it costs.**

- **Prompt.** Reminders stay, so each adds its tokens to every later request in that
  actor. The recall model's silence keeps that small; the first development play
  measures it.
- **Dollars, inferred.** If a recall request costs what a curator request does, about
  \$0.02 at the pilot's rates (\$2.34 over 112 requests), one every five decisions is about
  \$0.004 a decision. Play with a bounded prompt costs about \$0.006 a decision by the
  [context design](player-context.md)'s figure, and \$0.003 to \$0.004 in the pilot's
  windows under 60,000 tokens. So recall adds about two thirds to about the same as play.
  A recall request reads one screen and an index, against a curator's frames and files,
  so it may cost less; a smaller model would cost less again. The first development play
  measures it.
- **Risk.** In the closest outside study a proactive memory agent beside an actor raised
  task success by 2.5 to 8 points, and an untrained small one lowered it. Every reminder
  and every silence is logged and judged.

**Citations.** The decided `intent` and optional `cites` fields, once built, let the
player cite a fact id it acted on. Citations are evidence for the judges, not proof of
use.

**Not proposed:** the cut, which is a decision of its own below; a whole-store briefing;
relevance decided by keywords or embeddings alone (an embedding may pre-filter for the
recall model); triggers built on signs of no progress, which are hand-set and fire on
ordinary movement in this game; a required "memory checked" field.

## 3. Measurement

### Is memory used? On every sealed run

For each fact whose article's lead was delivered in the briefing or a reminder, each fact
the player read through a link or a search, and each fact only on the index, the judges
label each stretch in which the fact could matter:

- **Acted in line with it**: the player did what the fact supports.
- **Acted against it**: the player did what the fact advises against, or went where the
  fact says is empty or gone.
- **Found it again**: the player discovered by looking what the fact already said.
- **Did not apply**, or **cannot tell**.

These labels fit any fact: a place, a hazard, a rule, a procedure or a commitment. From
them come the use rate of delivered facts, re-discovery, acting on a stale or false fact,
the recall model's precision and silence, and how often the player follows a link or
searches and then acts on what it read. Judging is done by host agents, \$0 on the
provider; the coding host's capacity is its cost.

### Does memory help? Withholding within each start

- **Design.** A withheld unit's articles and facts are left out of the leads, the index,
  the reminders and search, and links to them are removed
  ([the delivery boundary](player-context.md#the-delivery-boundary)). A unit is an article with the facts only it cites; a fact
  cited by a delivered and a withheld article counts as delivered. The grooming before
  the start makes one article per subject, so one thing is one unit. The pilot
  ([record](../acceptance/2026-11-14-withholding-pilot.md)) showed that misses follow the
  unit, not the arm, and that every start copied one saved game. So a study draws all its
  starts at once: each unit is withheld in exactly half of the starts of each block, a
  block being the starts copied from one sealed saved moment, and each unit is compared
  with itself across arms. Placebo units, true facts of the store that cannot matter in
  the study's saved moments, are drawn like the others and analysed apart as a negative
  control ([study design](../contracts/evaluation.md#the-withholding-studys-design-withholding-study-draw1)).
- **Outcome.** For every fact, over the whole start: was it looked up again, acted
  against, or acted in line with? A miss is acting against the fact or an active lookup,
  an action spent only to learn what the fact says. Seeing the fact on a screen opened to
  do something else, or in a message the game showed on its own, is not a miss: in the
  pilot, most misses were such passive re-exposure, which delivery cannot prevent. The
  judges' instructions carry ordered decision rules with worked examples. Whether a fact
  "became relevant" is judged only as a secondary measure, because delivering a fact can
  create the need for it.
- **Analysis.** The primary test is a randomization test within units over this store's
  units; a crossed mixed model (unit, start, and a unit-by-delivery slope) is secondary;
  intention to treat, touch balance and the placebo units are reported beside them
  ([study analysis](../contracts/evaluation.md#the-withholding-studys-analysis-withholding-study1)).
  It estimates the effect for this store's units, not for facts in general.
- **Blind judging.** For this measure the judges and the owner see frames and inputs
  only: the briefing, the reminders and the player's own `intent` and `cites`, which can
  name delivered facts, are removed. Only the use labels read them.
- **What it estimates.** The effect of delivering a fact while half the store is
  delivered. It cannot see a harm to play as a whole, such as a distracting reminder;
  that is seen in the use labels and in time spent per decision.
- **Threats.** Handoff summaries and the previous final report can restate a withheld
  fact; a delivered article's prose can name a withheld subject; facts the curator writes during a start are not randomized; the player's own
  records can hold a withheld fact while that store still exists. These bias towards no
  effect.
- **Before any spend** a simulation gives the study its size and price. The blocked
  within-unit study is sized from the pilot's units under the codebook, with the planned
  test, in the [measure validation](../acceptance/2026-11-14-withholding-measure-validation.md);
  the first sizing, from the measure gate's numbers for the earlier per-start design, is
  the [withholding simulation](../acceptance/2026-11-13-withholding-simulation.md).
- **Status.** A benefit is not confirmed: the full study's frozen primary is not
  positive, and a benefit is only suggested, limited by the measure
  ([record](../acceptance/2026-11-14-withholding-study.md)). Delivery changes which topics
  the player touches, so the touch-conditioned estimand compares groups the treatment
  shaped.

### Game-neutral judging

- Packets are cut to a token budget, not to 200 decisions or 60 frames.
- The annotators list every fact the frames show a later actor could use, not only
  places with goods.

## 4. Judges as the standing measure

- **Two judges on everything and a third on disputes**, all host agents. The dispute rate
  is the health signal; it was 6.2% at the measure gate. Judges from a second model
  family would reduce shared blind spots but may need a paid provider; that is not
  proposed now.
- **Windows, not steps.** Judges label a window and cite frames; outside work finds them
  weak at finding the one wrong step in a long trace (TRAIL).
- **No further owner audits**, as the owner decided. Reported rates rest on the adjudicated
  judge labels, with the first two judges' agreement and the dispute rate beside them,
  and intervals over runs. They are not corrected against a human truth, and a record
  says so. Prediction-powered inference (PPI++, or active statistical inference for a
  weighted sample) is how a later audit would be used, if the owner asks for one.
- **An anchor set.** The measure gate's 30 owner-labelled pairs, with the owner's blind
  and checked labels, are re-judged with the measure gate's own judge prompt, frozen,
  whenever a judge's model changes: that shows drift in the model, in the labels the owner
  gave. The game-neutral labels have no owner labels, by the owner's decision; a change
  to their prompt is checked by the first two judges' agreement on a frozen set of
  sealed stretches, re-judged before and after. Risk R-FALSE-CLAIM: a changed judge
  silently shifts every later measure; both checks show the shift; each costs one
  judging pass.
- **Known judge risks**: leniency, missing evidence in long contexts, and errors shared by
  both judges.

## Changes to the context design

Made in [player-context.md](player-context.md) with this note:

- The briefing carries the leads of the articles the recall model chooses, not items by
  kind, and an index line per other article; the knowledge tools
  `player_knowledge_read` and `player_knowledge_query` read articles and facts.
- In the curator's table, the rows for game time and place, the four kinds, and a brief
  aimed at places and goods are replaced by this note's format and grooming.
- Reminders during play are a new layer between the briefing and the cut.

## Decisions

Put to the owner on 13 November 2026 with the recommendation first; the answers are rows
in the [owner decision log](../decisions/owner-decisions.md).

| Question | Recommended | Answer |
| --- | --- | --- |
| Adopt `curator-fact/3`: no fixed kinds or required place and time; ADR 009's types kept; retire and merge added (\$0 to build) | Yes | Yes |
| Store growth: consolidation between admissions and no hard cap (one more session per admission, \$1.16 to \$4.19 inferred), or a byte budget now | Consolidate, no cap | A full grooming and organizing pass by the curator |
| Delivery: the recall model's choice of full items at each actor's start, then reminders during play (\$0 to build; reminders inferred at two thirds to about the same as the cost of play) | Yes, in that order | Yes, in that order |
| The cut, now that the pilot has reported | Not yet | Not yet |
| Articles over facts: an article per subject with a lead, a body citing facts, and links; the briefing carries leads; the player follows links or searches for more (\$0 to build, in the same contract) | Yes | Yes |
| What replaces the comparison (\$165 to \$208 of play at the measured values) | Simulate withholding (\$0) | Simulate withholding |
| Judges as the standing measure with a 30 to 60 pair blind audit by the owner per study, or without audits | With audits | Without audits |

Spend on scoring curator variants (about \$16 each) and on development play with
withholding is asked later, with prices.

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
