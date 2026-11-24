---
owner: lead
status: proposed
date: '2026-11-23'
scope: 'Design for one coordinated S-MIGRATION from curator-knowledge/3 and delivered-knowledge/2 to curator-knowledge/4 and delivered-knowledge/3 (issue 925): epistemic core, keyed scope, lineages, forks and restores, stale-citation propagation, typed links and revision identity, public identifiers, retrieval, reuse review, the provenance bridge to the belief comparison, the retired type rulings, and the migration inventory and plan. No code, contract or spend is authorized by this note.'
review_trigger: 'The owner decides the questions in At a glance, a second game binding is started, or the curator, delivered-knowledge, player-host or spectator-view contract changes before this migration lands'
---

# Scoped, traceable knowledge: `curator-knowledge/4` and `delivered-knowledge/3`

## At a glance

- **Question.** What single format change, from `curator-knowledge/3` and
  `delivered-knowledge/2` to `curator-knowledge/4` and `delivered-knowledge/3`, fixes the
  four limits that the [meta-ontology and retrieval research](../research-knowledge-graph-scoping.md)
  found in sealed runs, while keeping operator blinding, `P-GENERALITY` and the
  [no-belief-value decision](../decisions/owner-decisions.md#no-belief-value-in-the-fact-store)?
  The four limits are type drift, two-level scope, revision-suffixed article IDs and
  retrieval that ignores the article graph.
- **Answer.**
  - Every fact gets a fixed epistemic core: a five-value `claim_kind` and an immutable
    `evidence_basis`.
  - Every record, fact or article, gets a software-maintained `lifecycle_state` and open
    kebab-case `tags`, which replace curator-invented types.
  - A keyed `scope` map is filtered before any graph step, and so is an optional `when`
    condition. An unknown scope axis excludes the record. An unknown `when` delivers it
    flagged.
  - An article is delivered only when every fact it cites is.
  - Lineage is provenance, not a scope axis. Forks and restores select the revision that
    was visible at the fork. When the fork is unknown, the record is downgraded to
    `contested` at delivery, and the downgrade propagates.
  - Articles get stable slugs and immutable revision IDs. A software-derived
    `supersedes` edge joins revisions.
  - Every public identifier passes one eligibility rule before backlinks are derived.
  - Status markers reach every projection the player sees.
  - Query ranking becomes `bm25_1hop` with a rank-order coverage skip, written in the
    existing pure-Python ranker.
- **Evidence.** The [#924 ablation record](../acceptance/2026-11-23-knowledge-retrieval-ablation-924.md)
  is the only sealed measurement. On `#896-b v91` (20 queries), a 1-hop expansion over
  article citations and links raised flat BM25's article MRR@5 from `0.658` to `0.879`.
  On `#889 v17` (10 queries) it rose from `0.700` to `1.000`. Production ranking has
  since become field-weighted BM25 (#920). That baseline and the coverage skip have no
  sealed measurement yet. Wave 3's first retrieval slice records both in a dated
  acceptance record ([evidence](#the-evidence-this-design-rests-on)).
- **Not known.** The ranking gains are in-sample: the queries, their gold labels and the
  constants were written together. Nobody knows whether flags such as `needs_review`
  change what the player does (the research's policy-adaptation gap). The `claim_kind`
  boundaries, such as `mechanic` against `entity_property`, are untested on curator
  output. A save reload inside one lineage is invisible to the store unless an operator
  labels it.
- **Owner decisions needed** (recommendation in bold):
  1. Adopt the fixed `claim_kind` core and retire `curator-type/2` and
     `ontology/types.json` in favour of tags. This rewrites five type rulings, listed in
     [the retired type rulings](#what-the-retired-type-rulings-become). They revisit
     [player-proposed, explained types](../decisions/owner-decisions.md#player-system-proposes-and-explains-types)
     and [types earn their place](../decisions/owner-decisions.md#types-earn-their-place).
     They partly revisit [free-text facts](../decisions/owner-decisions.md#free-text-facts-with-optional-subject),
     which dropped fixed kinds. **Adopt.**
  2. Let admission sessions publish articles whose citations went stale. They are flagged
     `needs_review`, and a grooming session's close-out fails while any current record
     keeps a stale citation ([close-out rule](#grooming-close-out)). Today the gate
     rejects them. **Adopt.**
  3. Let an article cite world-bound facts when the article itself binds that world.
     Today world facts stand alone. **Adopt.**
  4. Choose the source of fork and restore points. Either (a) every other lineage is
     "unknown fork" and is downgraded, while each lineage is assumed linear, or (b)
     `campaign-run/13` gains operator fork and restore labels. **(a) now; (b) when a
     study restores a start mid-lineage, or when `lineage.continuity` records a rewind
     inside a studied lineage.**
  5. Exclude records whose scope names a curator axis the run package does not declare,
     until a package declares curator axes. **Adopt.**
  6. After the migration, sealed `curator-knowledge/3` and `delivered-knowledge/2`
     evidence (`#889`, `#896-b`) can be read in one of two ways. Either check out the
     earlier source (the [migration procedure](../operations/migration.md)), or grow the
     closed archive index. **Check out the earlier source.**
  7. Approve the [migration plan](#migration-plan), its `$0` gates and one
     `C-MODEL-CHECK` of up to `$1` for the curator instructions. **Approve.**

## What changes for whom

| Reader | Today | After this migration |
| --- | --- | --- |
| Curator | Invents a `type` name per fact; scope is `game` or `world`; revising an article mints a new ID; superseding a cited fact forces rewriting every citing article in the same submission | Picks one of five `claim_kind` values and free tags; declares curator scope axes and `when`; keeps one slug per article; may leave stale citations flagged during admission; grooming clears them |
| Gate | Checks references and two-level scope | Also checks the scope lattice, citation carry-over and identifier rules, and recomputes lifecycle and review flags as a fixed point |
| Exporter | Selects `game` facts and the run's `world` facts | Evaluates scope, `when`, lineage and article eligibility against the target. It builds public identifiers and history from the kept set, and recomputes flags in the target's view |
| Player | Sees `id`, `type`, `text`, `seen` per fact; untyped title links; flat ranked search | Also sees `claim_kind`, `evidence_basis`, `lifecycle_state`, blinded `scope`, `branch_relation`, review flags and typed links. It also sees backlinks, `cited_by_articles`, citation source IDs and a history of replaced IDs, plus status markers in every briefing projection. Search follows the article graph |
| Spectator view (#464) | Shows every fact's scope as unrecorded | Shows the delivered scope class, flags, links, tags and claim kinds through `spectator-view/3` ([mapping](#mapping-the-spectator-deliverables-464)) |
| Belief comparison (#677) | Must reconstruct support from prose | Reads citation sets with origin positions, immutable revisions, supersession and contradiction edges and retirement reasons; polarity stays in #677's frozen extraction ([bridge](#provenance-bridge-to-the-belief-comparison-677)) |

## The evidence this design rests on

The [research note](../research-knowledge-graph-scoping.md#empirical-diagnosis-from-sealed-enactive-runs)
counted the four limits on sealed `#896-b v91` and `#889 v17`. At `v91` the store held
413 current facts and 47 articles. At `v17` it held 135 facts and 22 articles. The
[dated ablation](../acceptance/2026-11-23-knowledge-retrieval-ablation-924.md)
compared six retrieval methods on those files:

| Corpus | Method in the #924 record | Hit@5 | Article Recall@5 | Article MRR@5 |
| --- | --- | --- | --- | --- |
| `#896-b v91`, 20 queries | `bm25` (flat, unweighted fields) | `1.000` | `0.512` | `0.658` |
| `#896-b v91`, 20 queries | `bm25_1hop` | `1.000` | `0.717` | `0.879` |
| `#896-b v91`, 20 queries | `bm25_ppr_teleport` | `1.000` | `0.700` | `0.900` |
| `#889 v17`, 10 queries | `bm25` | `1.000` | `0.917` | `0.700` |
| `#889 v17`, 10 queries | `bm25_1hop` | `1.000` | `1.000` | `1.000` |

That record's production baseline was the all-terms substring search. Since then #920
has replaced it with field-weighted BM25 in
[`harness/player/knowledge.py`](../../harness/player/knowledge.py). No sealed record
measures that baseline, 1-hop on top of it, or the coverage skip. So this note makes no
claim about their sizes. Wave 3's first retrieval slice commits a rerunnable benchmark
script and records its results in one dated acceptance record. The script runs the 30
#924 queries on both corpora with #920's merged ranking as the baseline. The
[ranking gate](#offline-verification-gates) is defined against that record.

The query set is in-sample. Twenty-eight queries were written by the #924 study
together with their gold labels. The other two came from live `#896-b`
`player_knowledge_query` calls at `A01 v3` and `A03 v38`, and the record also replays them
retrospectively on `v91`.

## Lenses that shape the design

Each lens below is a way of looking at the problem that yields a concrete rule and a
check. None of the mathematics is implemented as such.

### Scopes form a partial order

A scope is a finite map from axis to value that always contains `game`. Read it as a
set of `(axis, value)` pairs. Then `s ⊑ s′` (s is at least as general as s′) exactly
when `s ⊆ s′`. For example, `{game}` ⊑ `{game, biome: forest}` ⊑
`{game, biome: forest, world: W1}`.

- The **join** `s ⊔ s′` is the union of the two maps when they agree on every shared
  axis. Otherwise it does not exist, because no run can satisfy both scopes.
- **Disjoint and overlapping are different.** `{game, biome: forest}` and
  `{game, biome: swamp}` give the shared axis `biome` different values, so they have no
  join and no run is both. `{game, biome: forest}` and `{game, ruleset: winter}` share
  no axis but `game`. Neither contains the other, yet their join
  `{game, biome: forest, ruleset: winter}` exists. A winter forest satisfies both, so
  the two can conflict there. Incomparable does not mean disjoint.
- **Eligibility is antitone in scope.** Each declared axis must match the target. A
  record with fewer axes therefore passes wherever a more specific one does. This
  covers scope axes only. `when`, lineage, `claim_kind` and lifecycle are per-record
  tests, so they do not follow from it.
- **Rule this gives:** an article's scope must be ⊒ the join of the scopes of the facts
  it cites, and the gate checks that each cited fact's scope is a subset of the
  article's. Antitonicity covers the scope part. The exporter still checks every cited
  fact's eligibility in full, because the per-record tests can exclude a fact whose
  article scope passes ([articles and their facts](#an-article-is-eligible-only-with-every-cited-fact)).

### Contradictions that do not glue

Think of the facts valid at each scope as a family of local views, where moving to a
more specific scope keeps everything the general scope holds. Two worlds' observations
are local views. They combine into one game-wide claim only if they agree. When world
W1 shows one behaviour and W2 another, there is no game-wide claim to write: both
observations are right where they were made.

**Rule this gives:** a `contradicts` link is classified by the two scopes and the two
`when` conditions.

| Scopes | `when` conditions | Result |
| --- | --- | --- |
| No join (a shared axis differs) | Any | No conflict. Both stay `active` |
| Equal | Not exclusive | Conflict. Both are `contested` |
| Incomparable, join exists | Not exclusive | Conflict inside the join. Both are `contested` wherever both are delivered |
| Comparable, unequal | Not exclusive | The specific record *shadows* the general one inside its own scope. The general one stays `active` and is delivered with `shadowed_by` |
| Join exists | Exclusive | No conflict. Both stay `active` |

- **Exclusive `when` conditions.** Two conditions are exclusive when their `requires`
  maps give a shared axis different values. Two opposing claims at an equal scope, one
  requiring `{"light": "night"}` and one requiring `{"light": "day"}`, need not conflict.
- **Unknown exclusion.** A pair whose `when` conditions cannot be shown exclusive counts
  as not exclusive. A `when` with only a `note` is one example, and so is a pair of
  `requires` maps with no shared axis. The conservative result is a conflict, and the
  curator removes it by stating the distinguishing axis in `requires`. Scope overlap is
  never unknown, because a join is computed from the maps alone.
- **Two views of the state.** The stored `contested` state is the curator's repair
  signal and ignores the target. The delivered state is recomputed in the target's view
  ([review flags](#stale-citations-and-review-flags)). A conflict with a record the
  target does not receive therefore does not mark a delivered record.

**Operation this gives:** `narrow_fact` replaces one over-general fact by facts scoped
more narrowly, and carries its citations over. It never overwrites a valid local
observation with another place's observation. Today a replacement must keep the level,
so the curator cannot repair an over-general `game` fact without retiring it.

### Minimal change

AGM belief revision asks that adding information change no more than necessary. Here
that becomes four acceptance tests for the gate and for grooming:

1. **Success.** Every record a submission adds is current in the candidate.
2. **Preservation.** Some records are not targeted by an operation and are not in the
   propagation closure of one. In the candidate, each such record is byte-identical to
   the base, apart from software fields whose inputs did not change (so, none).
3. **Citation carry-over.** A restatement, merge or narrowing keeps every origin
   citation of the facts it replaces. Evidence is never silently dropped, which is also
   what the belief comparison needs (see [the provenance bridge](#provenance-bridge-to-the-belief-comparison-677)).
4. **Scope consistency.** After publication, every stored `lifecycle_state` agrees with
   the [classification table](#contradictions-that-do-not-glue) for every `contradicts`
   link between current records.

### Coverage versus redundancy

Facility-location selection picks a set `S` to maximize `f(S) = Σᵤ maxₛ∈S sim(u, s)`.
The function is submodular, so greedy selection by marginal gain is near-optimal. With
`sim(u, s) = 1` when `s` is `u` or an article citing `u`, `f` counts the distinct records
that a result reaches.

The query step here is only *inspired* by that objective. It walks the ranked list in
score order and skips a fact that a record already kept cites. It never reorders by
marginal gain, so it is not greedy marginal-coverage maximization and inherits no
approximation bound. It is a cheap way to spend result slots on records an article does
not already carry. No sealed record measures it. The Wave 3 benchmark keeps it only if
it does not lower article MRR@5 or article Recall@5 against 1-hop alone.

The cut briefing keeps its recency rule. No sealed record shows its budget binding on
articles. The trigger to revisit it is in [What is not known](#what-is-not-known).

### Propagation to a fixed point

Review flags are monotone booleans over a dependency graph. They are defined as the
least fixed point of local rules, so the result does not depend on the order in which
records are visited, and cycles terminate. At current sizes (under 600 records), a full
recomputation at every publication and every export is cheaper than keeping
incremental state. So "incremental" describes the definition, not a separate engine.

## The repository: `curator-knowledge/4`

`knowledge.json` holds exactly `schema` (`curator-knowledge/4`) and `game`. A published
tree holds `knowledge.json`, `facts.jsonl`, `provenance.json`, `coverage.json` (from
the first publication of a submission) and the empty `programs/.keep` and
`tests/.keep`. `ontology/types.json` is gone (owner decision 1). Records keep sharing
one file and one schema, now `curator-fact/5`. Versions, tags, the lock, drafts and
restore are unchanged. So is the gate result (`curator-gate/2`).

### The epistemic core

| Field | Values | On | Written by | Mutable | Meaning |
| --- | --- | --- | --- | --- | --- |
| `claim_kind` | `interface`, `mechanic`, `entity_property`, `instance_state`, `strategy` | Facts | curator | Only by replacement | What sort of claim it is, in terms any game has |
| `evidence_basis` | `observed`, `inferred`, `hinted` | Facts | curator | Never | How it was learned; the current `known` field, renamed |
| `lifecycle_state` | `active`, `contested`, `superseded`, `retracted` | Facts and articles | software | Each publication | Whether it is still the current statement |
| `tags` | 0 to 8 distinct kebab-case words, each up to 32 characters | Facts and articles | curator | By `retag` in grooming | Emergent domain labels, such as `fire` or `water-boiling` |

The five kinds come from the research note. In game-neutral terms:

- `interface` is how to operate the game's screens and controls.
- `mechanic` is a rule of cause and effect.
- `entity_property` is a stable property of a class of things (an item, a unit or a
  card).
- `instance_state` is a fact about one game instance at one time.
- `strategy` is advice about what to do.

These are epistemic categories rather than game kinds, so the curator contract's rule
that "no format or check names a kind of thing in a game" still holds.
Two candidates were left out. `warning` is a matter of salience, and a tag says it.
`procedure` belongs to the program and procedure work in
[procedure learning](procedure-learning.md).

An article has no `claim_kind` or `evidence_basis`. It is a synthesis, and its claims
trace through facts to frames. `evidence_basis` and `lifecycle_state` are separate so
that provenance survives revision. A record that was `observed` stays `observed` when it
is later `superseded`. Retirement reasons (`wrong`, `ended`) are stored in `retired` and
are not lifecycle states.

**Why the types go.** Under `curator-type/2`, type `fields` add no keys and `identity`
cannot be checked. In practice the curator used types only as labels, and minted
different labels in two runs of the same game. Tags keep the useful part, which is
emergent vocabulary with a usage list in the brief. They drop the format, the
`revise_types` operation and the `retyped` history. Each type ruling and its
replacement is listed in [the retired type rulings](#what-the-retired-type-rulings-become).

### Identity: IDs, slugs and revisions

- A **fact ID** is written by the curator and matches `[a-z0-9][a-z0-9-]{0,63}`. A fact
  record is immutable in its curator fields except curator-authored `tags` updated by
  `retag`. Restating it mints a new fact ID, so a fact ID is also its revision ID.
- An **article slug** has the same pattern. It is written by the curator, stays the
  same across revisions, and is the ID that links, reads and deliveries use. Fact IDs
  and slugs share one namespace. A slug is never reused after retirement.
- An **article revision ID** is `<slug>@<published_in>`, written by software, and is
  the stored record's `id`. The `@` cannot occur in a fact ID or slug. So no revision
  ID can collide with a fact ID or a slug, and the gate needs no extra uniqueness check
  for it.
- **`supersedes`** is the fifth link relation, beside the curator's `depends_on`,
  `contradicts`, `part_of` and `see_also`. It is derived by software and never
  submitted. It joins immutable revisions only:
  - an old fact ID to each ID in its `superseded_by`;
  - one article revision ID to the next revision of the same slug.

  It is never a slug-to-slug link, so it can never be a self-link. Ranking ignores it,
  because ranking sees only current records. History, reads and the replay bridge use
  it.

### Record fields

`R` is required, `O` optional, `D` derived by software and `—` absent. A dash in a
delivered column means the field is never delivered.

| Field | Stored fact | Stored article revision | Delivered fact | Delivered article |
| --- | --- | --- | --- | --- |
| `schema`, `record` | R: `curator-fact/5`, `fact` | R: `curator-fact/5`, `article` | — | — |
| `id` | R: the fact ID | D: the revision ID | R: the fact ID | R: the slug |
| `slug` | — | R | — | — (it is `id`) |
| `revision` | — | — (it is `id`) | — | D: the delivered revision's ID |
| `claim_kind`, `evidence_basis` | R | — | R | — |
| `tags` | R, may be empty | R, may be empty | R | R |
| `text` | R | — | R | — |
| `subject` | O | — | O | — |
| `title`, `lead`, `body` | — | R; each claim's `facts` are distinct fact IDs | — | R |
| `scope` | R: curator axes, plus D `world` when bound | R, as for a fact | D: [blinded](#operator-blinding) | D: blinded |
| `when` | O | — | O | — |
| `links` | R, may be empty | R, may be empty | D: [public targets only](#public-identifiers) | D: public targets only |
| `citations` | R: non-empty distinct frame source IDs | — | D: as `citation_source_ids` | — |
| `lineages` | D on world-bound facts | D on world-bound articles | — | — |
| `seen` | D: latest cited frame | — | D | — |
| `last_confirmed` | — | D: latest `seen` among cited facts | — | D |
| `valid_from` | D: earliest cited frame | D: latest `valid_from` among cited facts | — | — |
| `valid_to` | D: `null` unless retired as `ended` | D: as for a fact | — | — |
| `lifecycle_state` | D | D | D: target view | D: target view |
| `stale_citations`, `needs_review` | D | D | D: target view, public IDs | D: target view, public IDs |
| `condition_unverified` | — | — | D | D: true when any cited fact's is |
| `branch_relation` | — | — | D | D |
| `backlinks`, `shadowed_by`, `contradicted_by` | — | — | D | D |
| `cited_by_articles` | — | — | D: slugs | — |
| `superseded_by` | D: absent while current; a list of one or more fact IDs | D: absent while current; a list of exactly one revision ID | — | — |
| `retired` | D: `{reason, reason_kind, citations, published_in, session}` | D: as for a fact, with empty `citations` | — | — |
| `retagged` | D: absent until the first retag; a list of `{from, to, version}` | D: as for a fact | — | — |
| `published_in`, `session` | D | D | — | — |

- **`superseded_by` is a list.** It names one fact for a restatement or a corrected
  supersession, two or more for `narrow_fact`, and the next revision for an article. The
  supersession reason is not stored, because it follows from the operation. A
  `retracted` record with `superseded_by` was corrected. A `superseded` record names
  either several replacements (narrowed) or one (restated). `superseded_by` and
  `retired` never appear together.
- **`retag` is not a revision.** It rewrites `tags` on the current row in place and
  appends `{from, to, version}` to `retagged`. Software already rewrites `superseded_by`
  in place the same way. The fact ID or article revision ID does not change, and the
  version's Git tag keeps the old row.
- **Articles have no `when`.** A delivered article's `condition_unverified` is true when
  any cited fact's is. An article cannot be more certain than its facts.
- The `known`, `type`, `retyped` and `scope.level` fields are removed.

Example stored fact:

```json
{"schema": "curator-fact/5", "record": "fact", "id": "boiling-makes-water-safe",
 "claim_kind": "mechanic", "evidence_basis": "observed", "tags": ["water", "fire"],
 "text": "Boiling murky water over a fire yields water the game labels clean.",
 "subject": "water treatment",
 "scope": {"game": "example"},
 "when": {"note": "needs a lit heat source", "requires": {}},
 "links": [{"rel": "depends_on", "target": "fire-needs-tinder"}],
 "citations": ["<frame source ID>"],
 "seen": {"session": "…", "actor": "…", "step": 41, "order": [3, "001", 41]},
 "valid_from": {"session": "…", "actor": "…", "step": 12, "order": [1, "001", 12]},
 "valid_to": null, "lifecycle_state": "active",
 "stale_citations": [], "needs_review": false,
 "published_in": "v12", "session": "…"}
```

### Provenance

`provenance.json` keeps `frames`, `sessions` and `last_admission`. It gains two
operator-label maps, which the gate copies from verified session labels and never takes
from a submission:

- `branches` maps a lineage label to `{"parent": label or null, "fork_at": position or null}`;
- `restores` is a list of `{"lineage": label, "restored_at": position, "saved_at": position or null}`.

`null` means unknown. Under owner decision 4(a), every lineage is recorded with both
`branches` fields `null`, and `restores` is empty. Under 4(b) both come from
`campaign-run/13` labels. The gate refuses a history where one lineage has two different
parents or fork points.

### Submission changes (`curator-submission/2`)

| Operation | Change |
| --- | --- |
| `add_fact`, `add_article` | New core fields; the article names its `slug` |
| `supersede_fact` | Adds `reason_kind`. `restated` requires the replacement's citations to include every citation of the facts it replaces, and leaves them `superseded`. `corrected` needs at least one citation none of them had, and leaves them `retracted` |
| `narrow_fact` | New. One current fact and two or more replacements, each with a scope strictly more specific than the original. Together the replacements' citations include all of the original's. The original becomes `superseded` |
| `retire_fact`, `retire_article` | Add `reason_kind`: `wrong` (becomes `retracted`) or `ended` (becomes `superseded`, and `valid_to` is set). The article operations address the article by `slug` |
| `revise_article` | Addresses the article by `slug`; the new revision gets a new revision ID |
| `retag` | Replaces `revise_types`. Grooming only, at most once per submission. Maps record IDs or slugs to new tag lists |
| `add_type`, `revise_types` | Removed |

## Scope and conditions

### The scope map

A scope is an object with 1 to 8 axes. Axis names match `[a-z][a-z0-9_]{0,31}`.
Values are 1 to 64 printable characters.

- **`game`** is required and equals the repository's game.
- **`world`** is the one software axis. Its value is the package's
  [world label](../decisions/owner-decisions.md#a-separate-world-label), an opaque
  operator name for one persistent game instance. A submission never writes it. It asks
  for it with `binds: ["world"]`, and the gate fills it from the citations' single
  world. `instance_state` requires `binds: ["world"]`. As today, a bound record is
  refused when its citations name two worlds or a session with no world.
- **Curator axes** are any other names, such as `ruleset`, `scenario`, `profile`,
  `level` or `character`. Their values are what the screen showed. No axis name is
  reserved for one game.

**Lineage is provenance, not scope.** On a world-bound record the gate also writes
`lineages`. This is the sorted distinct list of the cited sessions' lineage labels, with
`null` for a cited session that records none. It is never an axis: a lineage says which
timeline the evidence came from, not where the claim holds. A record whose citations
span several lineages stays world-bound and keeps every lineage in the list. It is never
widened into an unbound record, because binding comes from `binds` and not from how many
lineages the citations name.

The submitted form has `scope` (`game` plus curator axes) and optional `binds`. The
[cross-game table](../research-knowledge-graph-scoping.md#cross-game-stress-test-p-generality)
in the research note expresses each of its archetypes with these axes plus `lineages`.
Examples are a roguelite `profile` against a `run`, and a time loop whose
`instance_state` is bound to one loop through the world and lineage. A third is a
rule-rewriting puzzle with `level` plus `valid_to`.

### The target of an export

The exporter evaluates each record against a **target** built from the run package. It
holds `game`, `world` if the package names one, and `lineage` if it names one. Under 4(b)
it also holds the package's `branches` and `restores` entries. No package declares
curator axes, so in this deployment every curator axis compares as unknown. A package
`context` map would change `campaign-run/12`, and owner decision 5 makes the cost of not
having one explicit.

### Matching a record against the target

Each declared scope axis compares as **true** (the values are equal), **false** (they
differ) or **unknown** (the axis is absent from the target). Results combine with
Kleene's three-valued AND. Steps run in this order, and the first exclusion wins:

| Step | Test | Result |
| --- | --- | --- |
| Lifecycle | Not current (`superseded` or `retracted`) | Not delivered as a record, unless the [lineage rule](#lineages-forks-and-restores) selects it as the revision visible at a fork. It may appear in [history](#public-identifiers) |
| World | The record binds `world`, and the target's is absent or different | Excluded |
| Curator axes | Kleene AND of the declared curator axes | False or unknown: excluded ([why](#unknown-scope-is-not-unknown-condition)) |
| `when` | Kleene AND of `when.requires` against the target | False: excluded. Unknown: delivered with `condition_unverified: true` |
| Lineage | World-bound records only ([rules](#lineages-forks-and-restores)) | `branch_relation` is `same`, `inherited` or `unknown`; a known non-ancestor or a known post-fork revision is excluded |
| Article | Every fact in `body[*].facts` | Any cited fact excluded: the article is excluded ([rule](#an-article-is-eligible-only-with-every-cited-fact)) |

An unbound record has `branch_relation: null` and is never downgraded, because nothing
about it depends on the timeline.

### Unknown scope is not unknown condition

A scope axis and a `when` condition say different things. A scope axis is a
prerequisite that holds or fails for a whole run, such as the ruleset. If the target
does not say, the exporter does not know whether the claim applies at all. A `when` is
a condition that can change within a run, such as night or indoors. The exporter can
rarely decide it, but the player can check it on the screen when it matters. So the
two unknowns get different treatment:

- **Unknown scope axis: excluded.** The record does not enter the delivered file, so it
  never reaches a briefing, an index, a cut or a query result. Delivering it with a flag
  would promote a claim whose prerequisite is unconfirmed into ordinary retrieval.
- **Unknown `when`: delivered** with `condition_unverified: true` and its `note`.

`when.requires` uses the curator-axis grammar. A `when` with an empty `requires` is
unknown, so in this deployment every `when` is delivered flagged. The exporter writes
the number of records excluded for an unknown axis into `private/knowledge-full.json`'s
`selection`. The cost of decision 5 is therefore visible, and it is the trigger for a
package `context` map.

The **permitted transfers** are the only cases where a record reaches a target other
than the one it was observed in:

1. **Unbound records** (no `world`, no curator axis) go to every target of the game.
   This is today's `game` rule.
2. **Same world, same lineage**, with no labelled restore in between: delivered with
   `branch_relation: same`.
3. **Same world, known ancestor lineage** (4(b) only): the revision visible at the fork
   is delivered with `branch_relation: inherited`.
4. **Same world, unknown or mixed lineage**: delivered `contested`, with
   `branch_relation: unknown`. This covers world state such as cached loot on a map tile
   when a different start or character uses the same world.

Everything else is excluded:

- every record bound to another world (as today);
- every record with an unknown or false curator axis;
- every record with a false `when`;
- under 4(b), every known non-ancestor or post-fork revision.

The research note's cross-scope *hypotheses* would offer a sibling world's records on
request. They are not part of this migration, because no package can ask for them and no
study needs them.

### An article is eligible only with every cited fact

An article and its lead are exported only if every fact in `body[*].facts` passes every
step of the [matching table](#matching-a-record-against-the-target) for this target. The
cited fact must also be the exact fact revision the article revision cites. If one cited
fact is excluded, the whole article is excluded. It is not trimmed, because removing a
claim's fact changes what the claim says. The lattice rule makes a scope failure rare.
`when`, lineage and lifecycle can still exclude one fact under an eligible article scope,
and this rule catches them.

- **Flags flow up.** A delivered article is `contested`, `needs_review` or
  `condition_unverified` when any cited fact is, in the target's view.
- **Narrower examples.** A broader article may point to a separately scoped example
  only by a `see_also` link to that article or fact, never inline in a claim. The link
  is dropped where the example is not delivered, like any link to a record that is not
  public.

### The enforcement order

The exporter applies these steps in this order. Graph steps see only what earlier steps
kept:

1. **Eligibility.** Evaluate facts, then articles, against the target. For world-bound
   records this includes the lineage rule's choice of revision.
2. **Withholding draw.** Apply it to the eligible set. Ordinary and pilot exports use
   `knowledge-units/1`, and study exports use `knowledge-units/2`. A unit holds an
   article and every fact only it cites. A fact cited by several articles is delivered
   whenever any of them is kept, so a kept article always keeps its facts. The result is
   the **public set** `P`.
3. **Public identifiers.** Compute history, `stale_citations` and the target-view flags
   from `P` and the [public history rule](#public-identifiers).
4. **Graph.** Drop links to records outside `P`. Then compute `backlinks`,
   `cited_by_articles`, `shadowed_by` and `contradicted_by` from the remaining links and
   citations.
5. **Write.** The application's ranking and the host's briefing work only on that file.

### Public identifiers

Every field that names another record names only a public identifier, and the exporter
fixes those identifiers before it derives any backlink.

- **The public set `P`** is the delivered records' IDs, slugs and delivered article
  revision IDs (`<slug>@<published_in>`).
- **The public history set `H`** is the IDs of historical records (retired facts and
  earlier article revision IDs) that would pass step 1 for this target if they were
  current. When the export has a withholding seed, `H` is further restricted to IDs whose
  terminal replacement is in `P`. So a draw never reveals, through an old ID's descriptive
  text, a unit it withheld.
- The **terminal replacements** of an ID are the current records reached by following
  `supersedes` edges through any number of steps. Intermediate revisions are never
  named on another's behalf. Each one that is in `H` gets its own entry.

| Field | Allowed identifiers | Otherwise |
| --- | --- | --- |
| `body[*].facts` | In `P` | The article is excluded |
| `links[*].target` | In `P` | The link is dropped |
| `history.replaced` keys | In `H` | No entry |
| `history.replaced[*].by` | Terminal replacements in `P` | The replacement is dropped. An entry left with no replacement is removed |
| `history.ended`, `history.retracted` | In `H`, and only when the export has no withholding seed | Not listed |
| `stale_citations` | In `H` | The name is dropped. `needs_review` stays true without naming it |
| `revision` | The delivered revision of a slug in `P` | — |
| `backlinks`, `cited_by_articles`, `shadowed_by`, `contradicted_by` | Derived from the links and citations above | — |

Two examples show the rule. Suppose `narrow_fact` splits a fact into a W1 fact and a W2
fact. For a W1 target the redirect names only the W1 replacement, because the W2 fact is
not in `P`. A chain `a → b → c` resolves `a` to `c`. It names `b` only if `b` is in `H`,
and then in its own entry.

A test asserts the resulting invariant on the synthetic two-world, two-lineage
repository. No delivered record, link, backlink, history entry or index line names an
identifier outside `P ∪ H`.

### Operator blinding

The guarantee is about operator-sourced data. World labels, lineage labels, `branches`,
`restores` and the withholding layouts in `private/units.json` are never emitted in a
delivered file. The delivered record builders enforce that by construction:

- A world-bound record's `scope.world` is delivered as `null`. Only records of the
  target's own world pass the world step, so `null` always means "bound to this run's
  world, label withheld". This holds for other-lineage records too.
- Lineage is never delivered as a label. A world-bound record carries `branch_relation`
  (`same`, `inherited` or `unknown`), and an unbound record carries `null`. `unknown`
  never claims the record came from this run's own timeline.
- As today, the world label appears only in `private/knowledge-full.json`'s `selection`.
  That object gains `lineage`, and preflight checks it against `labels.lineage`.

Curator-authored strings are a separate boundary. This guarantee does not cover prose,
tags, fact IDs, slugs and `when` notes. If a curator wrote a label into text, delivery
would carry it. Which labels the curator's inputs expose is owned by the
[curator contract](../contracts/curator.md), and this migration does not widen them.
Position fields (`seen`, `last_confirmed`) keep today's session names unchanged.

Two projection tests verify the guarantee, both in `tests/test_knowledge_export.py` on
the synthetic repository with distinctive labels:

- `test_delivered_bytes_carry_no_operator_label` searches every delivered byte for every
  world and lineage label in the repository's provenance and the target.
- `test_no_delivered_reference_leaves_the_public_sets` checks the invariant above.

The shared reader fixtures also include files that the readers must refuse because they
carry a label-shaped `world` value.

## Time, lineages and staleness

### Two kinds of time

- **Publication time** is `published_in` and the `published_in` of `superseded_by` or
  `retired`. It says what the store said at each version, and replay of a prefix uses
  it.
- **Observed validity** is `valid_from` and `valid_to`, both trace positions. No game
  clock exists, which is still true. They are honest bounds: the claim was seen holding
  from `valid_from`, and it was seen ending at `valid_to`. It may have held earlier.

Restoring the knowledge store ([operator restore](../contracts/curator.md#operator-restore))
is a change in publication time and keeps its current rules. Loading an earlier *game*
save is a branch in the game's timeline, and the rest of this section handles it.

### Lineages, forks and restores

A lineage is one operator-labelled timeline. The game can still be rewound inside one
lineage. The [evaluation record](../contracts/evaluation-record.md) reports this after
the fact: `lineage.continuity` records a negative game-time gap at an admission
boundary, and `lineage.elapsed` drops when a reload undoes activity. Both readings come
from the game clock on screen, which the curator store does not keep. So the store never
infers a rewind from frames. A rewind is known only from an operator label.

- **A fork point** is `branches[L].fork_at`: the position in the parent lineage after
  which lineage `L` no longer shares the parent's timeline.
- **A restore point** is a `restores` entry. Within lineage `L`, the game was loaded at
  `restored_at` from a save written at `saved_at`. The stretch of trace strictly after
  `saved_at` and before `restored_at` is **abandoned**. A restore is a fork whose
  abandoned stretch is a dead branch.

What was visible at a fork is a historical revision, not the current record. A current
record restated after the fork can merge citations from before and after it, and the
child timeline never saw that merged statement. So for each world-bound record, the
exporter picks a revision in the target's lineage view:

- **Same lineage, no abandoned stretch touched:** the current record, with
  `branch_relation: same`.
- **Known ancestor, or own lineage with a labelled restore:** select from the full
  publication, revision and retirement history (not only current records) the latest
  revision of each record that existed at `fork_at` (or outside the abandoned stretch):
  its publication/revision position and all of its citations lie at or before `fork_at`
  (or outside the abandoned stretch), and it had not been retired at or before `fork_at`.
  This covers facts retired *after* the fork without a successor (visible at the fork) and
  excludes post-fork article revisions even when they cite only pre-fork facts. Deliver
  that revision under its own ID, with `branch_relation: inherited`. If no revision
  qualifies, the record is excluded, because it is known to be post-fork.
  - An article revision qualifies only if every fact it cites is the delivered revision
    of that fact.
  - The delivered `revision` names the article revision that qualified.
  - History never redirects such a fact to a post-fork successor, because that successor
    is not in `P`.
- **Known non-ancestor** (4(b)): excluded.
- **Unknown:** `branch_relation: unknown`, and the record is delivered `contested`. This
  case covers:
  - the parent or fork is `null` (always, under 4(a));
  - the record's `lineages` hold the target's lineage and others (mixed);
  - a cited session has no lineage;
  - the target names no lineage;
  - a restore has `saved_at: null`, which applies to every world-bound record citing a
    position before `restored_at` in that lineage.

The `contested` from an unknown fork exists only at delivery, because it depends on the
target. It is not stored. It propagates like a stored `contested`: the target-view fixed
point below sets `needs_review` on every delivered record that relies on it. An article
citing such a fact is itself delivered `contested`, because flags flow up.

Without labels (4(a)), a reload inside one lineage is invisible. The store treats the
lineage as linear and may deliver a record that the reload undid as `same`. This is
listed under [what is not known](#what-is-not-known). The evaluation's rewind readings
are the trigger for 4(b).

### Stale citations and review flags

For a record `x`, let `R(x)` be what it relies on. For an article, that is the facts
its claims cite plus its `depends_on` targets. For a fact, it is its `depends_on`
targets. One function computes:

```text
stale_citations(x) = sorted { y ∈ R(x) : y is not current in the view }
needs_review(x)    = stale_citations(x) ≠ ∅
                     or ∃ y ∈ R(x) : contested(y) or needs_review(y)
```

`needs_review` is the least fixed point. The computation starts with every flag false,
seeds a worklist with the records whose own condition holds, and propagates along the
reverse of `R` (cited-by and depended-on-by). Each record is set at most once, so the
work is `O(V + E)`. The function runs on two views:

- **Stored view.** The gate runs it at every publication over the current records,
  using stored lifecycle. History validation recomputes the flags and refuses a stored
  version whose flags differ.
- **Target view.** The exporter runs conflict classification and the flag fixed point in
  step 3 over the post-draw public set `P` (after step 2's withholding draw), never over
  withheld records. Here a record is current when it is in `P`, including a revision the
  lineage rule chose, and `contradicts` links to records outside `P` are dropped first so
  a withheld record never marks a delivered record `contested`. `contested` includes
  delivery-only contests. Names that are not in `H` are then dropped from
  `stale_citations`, as the [public identifier table](#public-identifiers) says.

Stored `lifecycle_state` is derived from operations:

- `retracted`: corrected supersession, or retirement as `wrong`.
- `superseded`: restatement, narrowing, article revision, or retirement as `ended`.
- `contested`: current, and joined by `contradicts` to a current record where the
  [classification table](#contradictions-that-do-not-glue) gives a conflict.
- `active`: otherwise.

The delivered `lifecycle_state` is the same rule in the target view, plus the
delivery-only `contested`.

### Grooming close-out

Owner decision 2 moves one rule from the gate to close-out. An **admission** may publish
with stale citations, which today it may not. The rule that clears them applies to the
**successful close-out of a grooming session**, not to each grooming candidate. One
grooming session may repair over several submissions. If each candidate had to be clean,
repair would be atomic again, which decision 2 removes. The gate still refuses a
grooming candidate that adds a stale citation which was not in its base.

- **Rule.** A grooming close-out succeeds only when no current record at
  `published_after` has non-empty `stale_citations`. The rule counts stale citations
  only. A `needs_review` that comes only from a `contested` dependency is a warning that
  may persist, because resolving a real conflict can need new evidence that grooming
  cannot get.
- **Reader.** [`tools/curator_host/groom.py`](../../tools/curator_host/groom.py) opens
  the repository at `published_after` and counts those records. The count goes into the
  summary as `stale_records`, which makes the format `curator-boundary-grooming/2`.
  `failure_reason` checks it after its existing checks, so a cap, proxy or sealing
  failure is still reported first.
- **Failure status.** `status: failed`, with reason `stale-citations-remain`. A
  `published_after` that cannot be read gives `stale-citations-unreadable`.
- **No submission.** If the session submits nothing and the base version has stale
  citations, close-out fails with `stale-citations-remain`. With none, it completes as
  today.
- **Rejected repair.** Today a clean rejection that leaves the version unchanged
  completes. Under this rule it still completes when no stale citation remains. It fails
  with `stale-citations-remain` when one does.
- **Skip.** A skip for `no-published-admission` is unchanged. A failed grooming follows
  the existing operator procedure for any failed grooming.

The flags are warnings for curator repair and player checks. The research note's
[findings on stale plans](../research-knowledge-graph-scoping.md#search-method-and-open-horizon-discovery)
show that marking is not a guarantee that a plan stops relying on a stale premise.

### Minimal-change checks

The [four tests](#minimal-change) run as property tests over random operation sequences
on synthetic repositories. They are not runtime checks. The gate enforces only
citation carry-over and scope consistency, which are cheap structural rules.

## Delivered knowledge: `delivered-knowledge/3`

The top level has exactly `schema`, `version`, `commit`, `repository_id`, `coverage`,
`articles`, `facts` and `history`. The empty file has empty lists, an empty history and
`null` identity, as today.

```json
{"replaced": {"old-fact-id": {"reason": "restated", "by": ["new-fact-id"]}},
 "ended": ["fact-or-slug"], "retracted": ["fact-or-slug"]}
```

`reason` is `restated`, `narrowed` or `corrected`. A corrected record appears in
`replaced` and not also in `retracted`. Each list follows the
[public identifier rule](#public-identifiers). A player holding an ID from an earlier
version learns what replaced it, or that it was withdrawn. This answers the
policy-adaptation gap with a pointer, not with silence.

**Article** (`id` is the slug):

```json
{"id": "water-treatment", "revision": "water-treatment@v12",
 "title": "Water treatment", "lead": "…",
 "body": [{"text": "…", "facts": ["boiling-makes-water-safe"]}],
 "tags": ["water"], "scope": {"game": "example"}, "branch_relation": null,
 "lifecycle_state": "active", "needs_review": false, "stale_citations": [],
 "condition_unverified": true,
 "links": [{"rel": "depends_on", "target": "fire-starting"}],
 "backlinks": [{"rel": "see_also", "source": "camp-setup"}],
 "shadowed_by": [], "contradicted_by": [],
 "last_confirmed": {"session": "…", "actor": "…", "step": 41, "order": [3, "001", 41]}}
```

**Fact**: the fields in the [delivered fact column](#record-fields). `citation_source_ids`
is the stored `citations` under a name that says what a player can do with it: pass it to
`player_source` where that tool can reach the frame. This design does not change the
tool's reach.

Both readers, `harness/player/knowledge.py` and `tools/player_host/knowledge.mjs`,
accept exactly these closed forms and refuse any other. Parity comes from one shared
fixture directory of valid and invalid files that both test suites load. No JSON Schema
library is added to either runtime.

### Reads

`player-knowledge/2` has one read result for every kind of identifier:

```json
{"schema": "player-knowledge/2", "version": "v12", "grants_authority": false,
 "identity": "<what was asked>", "resolution": "restated",
 "resolved_from": "old-fact-id", "records": [{…}]}
```

| `resolution` | When the identity is | `records` | `resolved_from` |
| --- | --- | --- | --- |
| `current` | The ID or slug of a delivered record | That record | `null` |
| `revision` | `<slug>@<version>` of a delivered slug where that revision ID is the delivered revision in `P` or an earlier eligible revision explicitly present in `H` (any excluded earlier revision falls through to `unknown`) | The delivered article | The revision asked |
| `restated`, `narrowed`, `corrected` | A key of `history.replaced` | Its `by` records, in order | The old ID |
| `ended` | In `history.ended` | Empty | The ID |
| `retracted` | In `history.retracted` | Empty | The ID |
| `title` | The exact title of a delivered article, as [`Knowledge.read`](../../harness/player/knowledge.py) matches today | That article | `null` |
| `unknown` | Anything else | Empty | `null` |

Rows are tried in table order, so an ID or slug wins over a title that happens to equal
it. A query result carries the same top-level fields, with `resolution` `query` and the
ranked records. The records inside a read or query result are the closed delivered
forms. `resolved_from` sits on the result, not on a record.

### Status markers in every projection

A record that is not plainly `active` says so wherever the player sees it. Its
`status` is the list, in this order, of whichever of `contested`, `needs_review` and
`condition_unverified` hold in the target view. One projection function in
`tools/player_host/knowledge.mjs` adds `status` to a projected entry only when the list
is non-empty. So the bytes of plainly `active` entries stay stable for the provider cache
([request stability](../contracts/player-host.md#request-stability-and-tail-notices)).
The same entry form is used everywhere, for articles and standalone facts alike:

| Projection | Where it is built today | Change |
| --- | --- | --- |
| Briefing leads and reminder leads | `lead()` inside `delivery()` | `status` on each lead |
| Recall index and briefing index | `knowledgeIndex()` | `status` on each row |
| Cut briefing leads and index | `cutBriefing()`, through `lead()` and `knowledgeIndex()` | Same; the 24,000-character cap counts the added bytes |
| Update `added` and `updated` entries | `updateDelivery()`, through `lead()` | `status` on each entry |
| Update comparison | `face()` in `updateDelivery()` | The face includes `status`, so an entry whose prose is unchanged but whose status changed is `updated` |

The cut keeps its recency selection.

### Retrieval: `bm25_1hop` with a coverage skip

This replaces the body of `Knowledge.query`, and `QUERY_LIMIT` stays 10:

1. Score every delivered record with the current field-weighted BM25. The field weights
   become title or subject `3`, lead or tags `2`, and body or text `1`. Tags take the
   place of type; `claim_kind` is not indexed.
2. Build an undirected graph from claim citations and every delivered typed link.
   `supersedes` is not in it.
3. For each of the 10 highest-scoring records `u` with score `s > 0` and degree above
   0, add `0.35 · s / √deg(u)` to each neighbour, multiplied by `1.25` for an article
   and `0.70` for a fact.
4. Keep only records whose combined score is positive. A neighbour reached only through
   a seed has a positive score, and a record no query term reaches is never returned.
   A query that matches no record returns an empty list, as
   [`Knowledge.query`](../../harness/player/knowledge.py) does today.
5. Order by score, descending, and break ties by delivered order, as today.
6. Walk that order. Skip a fact that a record already in the result cites, and stop at
   10 records. This is the rank-order skip described in
   [coverage versus redundancy](#coverage-versus-redundancy), not a marginal-gain
   selection.

Contradicting records stay in the graph on purpose: a query should surface both sides.
The constants are the ablation's and are not tuned. The [gates](#offline-verification-gates)
measure them on the migrated code. Personalized PageRank with teleporting dangling nodes
is the tested upgrade if a store outgrows one hop.

## Reuse review: the search engine and storage

`S-CODE` asks whether a maintained capability fits before custom code grows. The
nearest fit is the standard library's SQLite with its FTS5 extension, with relational
tables for edges and scopes. The fair way to use it here keeps the project's tokenizer:

- store `' '.join(terms_of(field))` in three FTS5 columns with a non-stemming tokenizer;
- quote each query term from `terms_of` and join them with `OR`;
- rank with `bm25(index, 3, 2, 1)`.

Pre-tokenized columns avoid a second stemmer, and quoting removes the query-syntax
hazard, so neither is a reason against FTS5. The other option is to extend the existing
pure-Python ranker.

| Concern | Stdlib SQLite FTS5 in memory | Extend the pure-Python ranker |
| --- | --- | --- |
| Dependency | None to install. FTS5 is a compile-time option, and the slice must confirm that both the main checkout's and CI's Python builds include it | None |
| Query handling | Quoted `terms_of` tokens joined by `OR`; nothing else reaches the parser | Tokens only |
| Tokenizer | `terms_of` is reused, so query, record and replay tokenize the same way | Same |
| Scoring | FTS5's `bm25()` weights phrase counts by column and normalizes by total document length. Its IDF differs from the current `ln(1 + …)` form for very common terms. Rankings may differ, and the direction is unknown until measured | The current formula, already tested |
| Index lifetime | An index per delivered version: build on load and on adoption of a newer version, and close the connection with the `Knowledge` object | Built in the constructor, as today |
| Determinism | Needs explicit `ORDER BY` with a position column | Explicit sort key, as today |
| Graph, scope and coverage | Custom Python either way, or SQL joins over tables built from the same JSON | Dict adjacency, tens of lines |
| Maintenance | Drops about 40 lines of scorer. Adds SQL text, connection management and a build-option dependency | Keeps about 40 lines of scorer and tokenizer, which the project already maintains and tests |
| Second reader | The Node host does no search, so there is no parity issue | Same |

**Recommendation: extend the pure-Python ranker in this migration.** Both options are
workable. The store is under 600 records. The #924 record measured `bm25_1hop` at
`1.48 ms` on `v91`, so no performance need exists. The graph, scope and coverage logic
stays custom either way, so FTS5 would trade a small tested scorer for index lifetime
management and a build-option check. The ranking would also need re-measuring, with
nothing yet to gain from it. Revisit FTS5 if any of these happens:

- a store passes 5,000 delivered records;
- 95th-percentile query time passes 20 ms;
- a feature needs phrase or prefix queries.

**Rejected frameworks.** The research note's sources cover several memory frameworks:
`Graphiti`/Zep, `Mem0`, `Letta`, `Cognee`, `Hindsight` and `Honcho`. Each brings its own
service, store or extraction pipeline, mostly behind a model call. The gate's contract
rules all of them out:

- it executes nothing and calls no model;
- it is the single Git-tagged writer;
- the curator's sandbox has a closed workspace.

They would also put game semantics into a dependency's schema (`P-GENERALITY`) and add
a lifetime upgrade cost that 40 lines do not have. The young embedded graph databases
are rejected on the same grounds plus maturity: `LadybugDB` and its archived ancestor
`KuzuDB`. The bi-temporal split is the useful idea from this family, and it is taken
here as two fields.

## Provenance bridge to the belief comparison (#677)

`curator-knowledge/4` stores **no** probability, confidence, weight or opinion tuple, as
the [no-belief-value decision](../decisions/owner-decisions.md#no-belief-value-in-the-fact-store)
requires. Every numerical view is computed at offline replay time and never written back.
The [belief-method comparison](belief-method-comparison.md) replays cases in the
`belief-replay-fixture/1` form that
[`belief_replay.py`](../../tools/recurrence_research/belief_replay.py) reads. Each
observation there has a `source_id` and reports with `origin`, `event` and `polarity`. A
case has `applicable_events`, optional `required_support`, a `dependence_group`, and
checkpoints with `withdrawn_origins`. The table says what this store supplies for each
of those, and what still comes from #677's frozen extraction set.

| Replay input | From the store | From #677's frozen extraction |
| --- | --- | --- |
| Proposition and scope | One fact is one proposition at one scope: `id`, `text`, `scope`, `when` | The question wording |
| Observation `source_id`, `exposure`, `detail` | Frame citations supply frame `source_id`s | Ordered `exposure`, observation `detail` and any non-frame stand-in observation (as in `belief-replay-cases.json`) |
| Report `origin` across merges | Each citation's frame, with session and actor from `provenance.frames`. Restatement, merge and narrowing carry citations forward as a set union, so a frame cited by two merged facts is one origin, never two. The immutable earlier revisions keep each original citation set, which shows which fact first cited each origin | — |
| `event` and `polarity` | Not stored | Yes |
| Independent alternatives or `required_support` | An `inferred` fact jointly requires its `depends_on` premises. Nothing in the store says whether one fact's several citations are independent alternatives or jointly required | Yes, per case: the `required_support` list |
| Refutation | Citations of a retirement with `reason_kind: wrong`. Citations a `corrected` replacement adds. Citations of a record joined by `contradicts` where the classification table gives a conflict | Polarity of each |
| Local exception | A `contradicts` link at a comparable, unequal scope is shadowing. Inside the specific scope the general proposition is not asserted, so the specific record is not refutation of the general proposition at its own scope | — |
| `corrected` replacements | The old and new records are different propositions, joined by a `supersedes` edge with the old record `retracted`. The old revision's text and citations stay in `facts.jsonl`, so a prefix replay sees the old claim | Whether the replacement negates the old claim |
| Withdrawal (`withdrawn_origins`) | The version that retracted a record whose citations are the origin | Which origins a checkpoint withdraws |
| `ended` retirement | Censoring: `valid_to` bounds observed applicability. It is not refutation and not error | — |
| Dependence | Shared sessions, actors and windows, `depends_on` for inferences, and `lineages` | `dependence_group` |
| Checkpoints and `through` | `published_in` order of revisions and transitions; prefix replay sees only what was published by then | Checkpoint choice and checkpoint `through` cut |
| Prior weight `W`, base rate `a`, opinions and Beta views | Never stored | Replay parameters and formulas |

**What the mapping establishes.** The store keeps what a replay needs to *locate* the
evidence for a proposition:

- citation sets with origin positions;
- immutable revisions;
- supersession and contradiction edges with a computable scope relation;
- retirement reasons;
- publication order.

It does not establish polarity, event identity, the conjunctive structure within one
fact's citations, or which events apply. Those stay in #677's frozen extraction set. So
"no later schema change" holds only for the located inputs in the store column, not for
every replay quantity. A *production* belief value would still be a second, separately
justified migration. The comparison note's warning also stands: different frames may
share an error cause.

## What the retired type rulings become

Owner decision 1 retires the type format. Five standing rulings depend on it, and each
gets an explicit replacement so that nothing is dropped silently:

| Ruling today | Source | After this migration |
| --- | --- | --- |
| Types are proposed by the player system and checked against existing types | [Decision](../decisions/owner-decisions.md#player-system-proposes-and-explains-types); curator contract `add_type` | The curator proposes tags. The brief lists existing tags with counts and near pairs before the curator writes. `claim_kind` is fixed and needs no proposal |
| Types are explained to every reader | Same decision | The five `claim_kind` values are defined once in the curator instructions and the [player guide](../player-guide.md). A tag carries no definition: the curator sees it with its usage count, and the player sees it on records. **This is the ruling the owner revisits** |
| Types earn their place or go; an unused type is flagged | [Decision](../decisions/owner-decisions.md#types-earn-their-place); the type list in the brief | A tag exists only while a current record uses it, so a tag with no use leaves the list and needs no "unused" flag |
| Grooming re-types with `revise_types`, at most once per submission, recorded in `retyped` | Curator contract | `retag`, grooming only, at most once per submission, recorded in `retagged` |
| Near pairs use the words of a type's name and field names | Curator contract, the type list | Near pairs use the words of the tag alone, because tags have no fields. The 1/3 shared-word rule and the size limits are unchanged, now in [`type_usage.py`](../../harness/curator/type_usage.py)'s successor |

The [free-text facts](../decisions/owner-decisions.md#free-text-facts-with-optional-subject)
decision keeps its free text, optional subject and order of sighting. It dropped fixed
kinds of game thing. `claim_kind` reintroduces a fixed, game-neutral kind of claim, which
the owner's decision on item 1 settles.

### Mapping the spectator deliverables (#464)

[#464](https://github.com/CVX-Hull/enactive/issues/464) waits on this migration. Each of
its deliverables maps as follows:

| #464 deliverable | Source after this migration |
| --- | --- |
| `scope`, `evidence_basis`, `lifecycle_state`, `stale_citations`, `needs_review` | The delivered records |
| Typed `links` and `backlinks` | The delivered records |
| Clickable fact citations to frames | `citation_source_ids`, resolved by the view's existing anchor rule. A frame of this run resolves; another admission's frame has `null`, as for positions today |
| `ontology/types.json` view | Retired with the file. Replaced by a tag and `claim_kind` view counted from the delivered records |
| Curator draft and gate views | Not provided. Drafts and gate results live in the curator repository and session records, which the [spectator contract](../contracts/spectator-view.md) does not let the knowledge route read. #464 keeps this deliverable and chooses its own source |

The #464 description needs the `ontology/types.json` line replaced with the tag and
`claim_kind` view when this migration is accepted.

## Migration inventory

This follows [S-MIGRATION](../standards/migration.md): one coordinated change, no
compatibility reader, and unsupported versions refused. The paths were checked against
the tree at `41006bd7`.

### Formats

| Old | New | Note |
| --- | --- | --- |
| `curator-knowledge/3` | `curator-knowledge/4` | A fresh repository; older ones are kept as sealed evidence |
| `curator-fact/4` | `curator-fact/5` | Facts and articles |
| `curator-type/2` | Removed | With `ontology/types.json` |
| `curator-submission/1` | `curator-submission/2` | The operations above |
| `curator-boundary-grooming/1` | `curator-boundary-grooming/2` | Adds `stale_records` and the two failure reasons |
| `delivered-knowledge/2` | `delivered-knowledge/3` | Also the private `knowledge-full.json`, whose `selection` gains `lineage` and the unknown-axis count |
| `player-knowledge/1` | `player-knowledge/2` | Read and query results |
| `spectator-view/2` | `spectator-view/3` | One API schema for every route. The knowledge route's facts gain recorded scope, flags, links, tags and kinds, and its `scope` filter changes from `all`, `world` and `game` to the delivered scope classes |
| `knowledge-units/1`, `knowledge-units/2` | Unchanged | Their shapes are the same. Units are built over the eligible set, and the article unit names the slug |
| `withholding-study-draw/2` | Unchanged under 4(a) | Under 4(a) lineage excludes nothing, so a layout depends on version, commit and world as today. Under 4(b) it gains `lineage` and becomes `/3`, with `campaign-run/13` |
| `curator-gate/2`, `curator-coverage/2`, `knowledge-update-entry/1`, `coverage-update-entry/1`, `campaign-run/12`, `player-host-inputs/4` | Unchanged | Their shapes are the same; readers that expect the delivered schema change with it |
| Telemetry `delivered_knowledge_schema` | Unchanged field | Records the new value |

### Code

| Area | Paths |
| --- | --- |
| Repository, gate and session | `harness/curator/knowledge.py`, `gate.py` (also its `curator-submission/1` check), `session.py` (`current-facts.jsonl`, brief), `type_usage.py` (becomes the tag list) |
| Curator instructions and grooming | `tools/curator_host/prompt.md`, `grooming.md`, `groom.py` (close-out rule) |
| Export and selection | `tools/knowledge_export.py`: the ordinary `knowledge-units/1` `draw()` and `filter_delivery()`, the `knowledge-units/2` `study_record()`, selection, the graph and history. Also `tools/curator_host/live_runner.py` (target with lineage) and `tools/campaign_package.py` (preflight of `selection`) |
| Player application | `harness/player/knowledge.py`, `harness/application.py`, `harness/player_view.py` |
| Player host | `tools/player_host/knowledge.mjs` (closed forms, the shared projection with `status`, `updateDelivery`'s face), `tools/player_host/README.md`, `tools/campaign_player.py` (adoption check) |
| Measurement | `tools/memory_measure.py` (unit layouts against the new full export, for both units versions), `tools/memory_screen_checks.py`, `tools/run_ledger.py` (uses `Knowledge`, API unchanged) |
| Spectator view, server | `harness/viewer/__init__.py`, `app.py`, `catalog.py` and `views.py` (`spectator-view/3`). Also `delivered.py` (recorded scope), `knowledge.py` (`CURRENT_SNAPSHOT`) and `telemetry.py` (`curator-boundary-grooming/2`) |
| Spectator view, browser | `web/app/data.js` (`viewerGet`'s default schema), `web/app/memory.js`, `web/app/records.js` |
| Campaign watch | `tools/campaign_watch.py` (reads `spectator-view/2`) |
| Text only | `tools/recurrence_research/trial.py` names the old delivered schema in a status string |

### Tests and fixtures

- **Curator:** `tests/curator_stand_in.py`, `tests/live_curator_stand_in_run.py`,
  `tests/test_curator_gate.py`, `test_curator_session.py`, `test_curator_host.py`,
  `test_curator_runner.py` (also the grooming summary), `test_curator_type_usage.py`,
  `test_evaluation_memory_screen_checks.py`, and the curator host's
  `tools/curator_host/test/host.test.mjs` (its scripted `curator-submission/1`).
- **Delivery and measurement:** `tests/test_knowledge_export.py`,
  `test_evaluation_delivery.py`, `test_campaign_run.py`, `test_campaign_player.py`,
  `test_player_host_contract.py`, `test_player_knowledge_query.py`,
  `test_process_measures.py`, `test_memory_measure.py`,
  `test_memory_measure_study.py`, `test_memory_measure_withholding.py` and
  `test_run_ledger.py`.
- **Viewer and watch:** `tests/test_viewer_api.py`, `tests/test_viewer.cjs`,
  `tests/test_campaign_watch.py`, and every fixture under `tests/fixtures/spectator/`
  that names `spectator-view/2`, with its `refresh.py`, `server.py` and `synthetic.py`.
- **Fixtures:** `tests/fixtures/empty-delivered-knowledge.json`, and the new shared
  reader fixture directory.
- **Player host:** the files in `tools/player_host/test/` that name the delivered
  schema: `cli`, `control-and-finish`, `knowledge-delivery`, `live-knowledge-update`,
  `mcp-connection`, `provider-requests`, `recorded-player` and `serialization` (each
  `.test.mjs`), plus `delivery-scenario.mjs`, `host-scenario.mjs`,
  `delivery-demo.mjs` and `context-cut.test.mjs`.

### Current documentation

- **Contracts:** `docs/contracts/curator.md` (its reader table must gain
  `harness/player`, the viewer and `tools/campaign_package.py`),
  `player-host.md`, `spectator-view.md`, `measurement-tools.md`,
  `withholding-study.md`, `player-host-telemetry.md` and `evaluation-record.md`.
- **Components and operations:** `docs/components/curator.md` (the grooming summary),
  `docs/components/player-interface.md`, `docs/operations/migration.md`,
  `docs/operations/campaign-run.md` and `docs/operations/curator-hosts.md` (reading
  `grooming-summary.json`).
- **Overview pages:** `docs/overview.md`, `docs/architecture.md`, `docs/glossary.md`
  and `docs/player-guide.md` (query and read results, status markers, `claim_kind`).
- **Owner decision log:** the rows that owner decisions 1 to 7 add.
- **This note** becomes `historical`, with its replacement set to the curator contract.

### Left as evidence

`docs/design/world-scoped-memory.md`, ADR 009, dated records, `data/evidence/index.json`
and `data/evaluation/coding-agent-attempts.jsonl` keep their wording. The sealed
repositories and delivered files under `.runtime/evidence/` are not converted.

## Migration plan

The Project calls this "Wave 3". It lands as **one** merge, because no slice works with
the others' old formats. The slices below have disjoint file ownership so that workers
can build them in parallel worktrees. The lead integrates them and owns the shared
runtime.

| Slice | Owner | Files | Done when |
| --- | --- | --- | --- |
| Shared shapes | Lead, first | The shared fixture directory of valid and invalid `delivered-knowledge/3` files, and the synthetic two-world, two-lineage repository builder | Fixtures reviewed; every other slice builds on them |
| Retrieval benchmark | Worker, first | A rerunnable benchmark script over the 30 #924 queries, and one dated acceptance record | The record gives #920's merged ranking as the baseline on both corpora, with 1-hop and the coverage skip measured against it |
| Repository and gate | Worker | Repository, gate and session code, curator instructions, `groom.py`, curator tests including `host.test.mjs`, `memory_screen_checks` | Gate tests cover each operation and the lattice, identifier and carry-over rules. They also cover the fixed point, the close-out cases and refusal of `curator-knowledge/3` |
| Export and selection | Worker | `knowledge_export`, `live_runner`, `campaign_package`, `memory_measure`, their tests | The public-set and blinding tests pass on the synthetic repository, including fork and restore cases |
| Player reads and ranking | Worker | `harness/player/knowledge.py`, `application.py`, `player_view.py`, the query test, `docs/player-guide.md` | Shared fixtures agree; the ranking gate passes |
| Player host | Worker | `knowledge.mjs`, its tests, README, `campaign_player.py` and its tests | Shared fixtures agree. Serialization tests show stable bytes for `active` entries, and status markers on every projection |
| Spectator view | Worker | Viewer Python, `web/app` files, `campaign_watch.py`, viewer and watch tests and fixtures | Viewer tests show scope, flags, links, tags and kinds under `spectator-view/3`, with no label |
| Contracts and integration | Lead | Every current document listed, plus integration | Full regression, review and the protected CI profile pass |

### Offline verification gates

All of these gates cost `$0` and need no game launch:

1. **Reader parity.** Python and Node accept and refuse exactly the same shared
   fixtures.
2. **No leak.** No delivered identifier leaves `P ∪ H`, and no operator-sourced field in
   delivered output emits a raw world/lineage label (verified by byte-level absence scan
   on a synthetic fixture whose operator labels are unique strings absent from curator
   prose and session names). The steps run in the
   [enforcement order](#the-enforcement-order).
3. **Article eligibility.** No delivered article cites a fact that is not delivered.
4. **Default preserved.** A store holding only unbound and world-bound records exports
   the same eligible set as today's rule.
5. **Fixed point.** The flags are the same after a recomputation, after shuffling the
   input order, and on `depends_on` cycles. This holds in both views.
6. **Minimal change.** The property tests in [minimal-change checks](#minimal-change-checks)
   pass.
7. **Ranking.** The 30 #924 queries are replayed on test-only projections of the
   sealed `v91` and `v17` files into the new form. The projection takes the slug from
   the old ID and resolves links by title. It lives in the test and is never a runtime
   reader. Against the Wave 3 benchmark record's baseline, the gate requires:
   - Hit@5 and article MRR@5 at least the baseline's on both corpora;
   - the coverage skip kept only if it lowers neither article MRR@5 nor article
     Recall@5 against 1-hop alone;
   - a 95th-percentile query time under 5 ms.
8. **Cut and cache.** Existing context-cut and request-serialization tests pass, the
   cut payload stays within 24,000 characters, and a flag-only change produces an
   `updated` entry.

Full regression runs before merge, because this is a broad source change.

### Model check criteria

One `C-MODEL-CHECK`, capped at `$1`, covers the changed curator instructions. Sample
replies to a fixed small window must produce a `curator-submission/2` that passes the
gate's well-formed and candidate stages, with valid core fields and scope. A failure is
fixed in the instructions, never by loosening the gate. The recall prompt is unchanged
apart from the status markers, which the recorded-player tests cover. A paid live
admission on the new store is a separate, priced approval.

### Stop conditions

Stop and return to the owner in any of these cases:

- a gate other than ranking fails after two repair attempts;
- a slice needs a file outside its ownership;
- the ranking gate falls below the benchmark record's production baseline;
- the model check reaches `$1` without a passing sample.

## Alternatives considered

| Alternative | Why not now |
| --- | --- |
| Keep free-text types and add only scope | Type drift remains, and nothing game-neutral is left to rank, filter or compare across runs |
| Exclude everything from another lineage | Throws away world state that is still valid in a shared world; a downgrade with a flag is more honest |
| Deliver unknown-axis records flagged, like an unknown `when` | Promotes a claim whose run-wide prerequisite is unconfirmed into briefings and search; decision 5 |
| Trim an article's claims to its eligible facts | Changes what a claim says without the curator; the article is excluded instead |
| Keep atomic repair (no stale citations) | Safe, but a live admission must rewrite every article citing a superseded fact. Shared facts are common enough that the withholding layout lists them (`shared` in `knowledge-units`); decision 2 |
| Require each grooming candidate to be free of stale citations | Makes repair atomic again within grooming; the rule applies at close-out |
| An entity-relation triple graph, or PageRank by default | Research counter-evidence under incomplete knowledge; PageRank only tied 1-hop in #924 |
| Coverage-aware cut briefing now | No sealed record shows the cut budget binding on articles |

## What is not known

- **Whether the ranking gains hold.** The #924 queries and gold labels were written
  together by the study. Its two live player queries came from `A01 v3` and `A03 v38`
  and were replayed retrospectively on `v91`. All are in-sample. The fix is a held-out
  query set drawn from future live `player_knowledge_query` calls.
- **The size of the gain over today's ranking.** #920's field-weighted BM25 was not in
  the #924 ablation. The Wave 3 benchmark record measures it first.
- **Whether flags change behaviour.** It is unknown whether `needs_review`,
  `contested`, `condition_unverified` or a `history` redirect changes what the player
  plans. Measuring that belongs with the [judged measures](../contracts/measurement-tools.md#adjudication-and-the-standing-use-measures),
  not this migration.
- **Whether curators pick kinds consistently.** No inter-session agreement check exists
  yet, so it is unknown whether two curator sessions assign the same `claim_kind` to the
  same claim.
- **Reloads inside a lineage.** Without operator restore labels, the store cannot see a
  reload within one lineage. It may deliver a record the reload undid as `same`. A
  negative `lineage.continuity` gap or a lowered `lineage.elapsed` in a studied lineage
  is the trigger for decision 4(b).
- **How much decision 5 excludes.** The unknown-axis count in `selection` will show
  whether curator axes cost the player knowledge before packages declare them.
- **Whether session names carry labels.** Position fields keep session names. This
  design does not establish that no session name embeds a world or lineage label.
- **When the cut briefing needs coverage selection.** Revisit it when a store passes 64
  articles or 20,000 characters of leads. Revisit it also if a replay shows that the
  cut's recency rule drops a gold article that a query needed.
