---
owner: lead
status: historical
date: '2026-11-24'
scope: 'Approved working specification for one coordinated S-MIGRATION from curator-knowledge/3, delivered-knowledge/2 and campaign-run/12 to curator-knowledge/4, delivered-knowledge/3 and campaign-run/13 (Wave 3: issues 936 and 937); adopted into the curator, player-host, campaign-run and spectator-view contracts.'
replacement: docs/contracts/curator.md
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
  - Every record, fact or article, gets a software-maintained `lifecycle_state` with five
    values (`active`, `contested`, `superseded`, `retracted`, `ended`) and open
    kebab-case `tags`, which replace curator-invented types.
  - A keyed `scope` map is filtered before any graph step, and so is an optional `when`
    condition. Curator scope axes must be declared by a run package's new `context` map
    of run-wide invariants in `campaign-run/13`; the gate refuses any other axis. An axis
    the target does not declare excludes the record. An unknown `when` delivers it
    flagged.
  - An article is delivered only when every fact it cites is.
  - Lineage is provenance, not a scope axis. Forks and restores select the revision that
    was visible at the fork, at a frozen knowledge version. A record from an unknown fork
    is delivered with the status `unverified_branch`, which propagates review without
    claiming a contradiction. A record later proven wrong is never resurrected in a child
    branch.
  - An `ended` retirement needs new evidence on the record's timeline. Its end time
    distinguishes a witnessed change, an absence found later and a record still current
    at its last sighting.
  - Articles get stable slugs and immutable revision IDs. A software-derived
    `supersedes` edge joins revisions. Code carries restated citations forward and
    derives scope minima. The curator edits articles surgically with `edit_article`,
    swaps a one-to-one restated fact with `remap_citations` and checks a submission with the
    `validate_submission` host tool before finishing. A session that ends on a provider
    error still gates the submissions that passed that check.
  - Every public identifier passes one eligibility rule before backlinks are derived.
    Session names are replaced by opaque per-export aliases in delivered positions and
    coverage stamps.
  - Status markers reach every projection the player sees.
  - Query ranking becomes `bm25_1hop` in the existing pure-Python ranker. A rank-order
    coverage skip is kept only if it does not hurt direct answers.
  - The gate validates submission shapes with the already pinned `jsonschema`.
- **Evidence.** The [#924 ablation record](../acceptance/2026-11-23-knowledge-retrieval-ablation-924.md)
  is the only sealed measurement. On `#896-b v91` (20 queries), a 1-hop expansion over
  article citations and links raised flat BM25's article MRR@5 from `0.658` to `0.879`.
  On `#889 v17` (10 queries) it rose from `0.700` to `1.000`. Production ranking has
  since become field-weighted BM25 (#920). That baseline and the coverage skip have no
  sealed measurement yet. Wave 3's first retrieval slice records both in a dated
  acceptance record ([evidence](#the-evidence-this-design-rests-on)). The curator
  operations rest on a review recount of the sealed `#896-b` store
  ([curator evidence](#what-the-sealed-curator-run-shows)).
- **Not known.** The ranking gains are in-sample: the queries, their gold labels and the
  constants were written together. Nobody knows whether flags such as `needs_review`
  change what the player does (the research's policy-adaptation gap). The `claim_kind`
  boundaries, such as `mechanic` against `entity_property`, are untested on curator
  output. A save reload inside one lineage is invisible to the store unless an operator
  labels it.
- **Owner decisions** (all 9 recommendations approved on 24 November 2026;
  [owner decision log](../decisions/owner-decisions.md#knowledge-graph-scoping-rfc-approved)):
  1. Adopt the fixed `claim_kind` core and the five stored lifecycle states, and retire
     `curator-type/2` and `ontology/types.json` in favour of tags. This rewrites five
     type rulings, listed in [the retired type rulings](#what-the-retired-type-rulings-become).
     They revisit [player-proposed, explained types](../decisions/owner-decisions-archive.md#player-system-proposes-and-explains-types)
     and [types earn their place](../decisions/owner-decisions-archive.md#types-earn-their-place).
     They partly revisit [free-text facts](../decisions/owner-decisions.md#free-text-facts-with-optional-subject),
     which dropped fixed kinds. **Adopt.**
  2. Let admission sessions publish articles whose citations went stale. They are flagged
     `needs_review`, and a grooming session's close-out fails while any current record
     keeps a stale citation ([close-out rule](#grooming-close-out)). Grooming gets a
     generated worklist and an atomic repair unit. Today the gate rejects them.
     **Adopt.**
  3. Let an article cite world-bound facts when the article itself binds that world.
     Today world facts stand alone. **Adopt.**
  4. Choose the source of fork and restore points. Either (a) every other lineage is
     "unknown fork" and delivered `unverified_branch`, while each lineage is assumed
     linear, or (b) a later `campaign-run/14` gains operator fork and restore labels,
     each with the knowledge version visible at that point. **(a) now; (b) when a study
     restores a start mid-lineage, or when `lineage.continuity` records a rewind inside
     a studied lineage.**
  5. Bump `campaign-run/12` to `campaign-run/13` with a required top-level `context` map
     of declared run-wide target axes, `{}` by default. The gate refuses a curator scope
     axis that no admitted package declares, and the exporter excludes a record whose
     axis the target does not declare. **Adopt.**
  6. After the migration, sealed `curator-knowledge/3` and `delivered-knowledge/2`
     evidence (`#889`, `#896-b`) can be read in one of two ways. Either check out the
     earlier source (the [migration procedure](../operations/migration.md)), or grow the
     closed archive index. **Check out the earlier source.** The evaluation's existing
     closed archive keeps reading `#889`'s `campaign-run/12` manifests, journals and
     handoffs, which carry no delivered knowledge ([why](#why-campaign-run-changes)).
  7. Give the curator `edit_article` and `remap_citations`, keep `revise_article` with
     partial inheritance, and move citation carry-over, world derivation and scope
     minima into code ([curator operations](#submission-changes-curator-submission2)).
     **Adopt.**
  8. Validate submission shapes in the gate with `jsonschema==4.26.0`, already pinned in
     `requirements.in`, and keep cross-record rules in Python
     ([reuse review](#reuse-review-validation-search-and-storage)). **Adopt.**
  9. Approve the [migration plan](#migration-plan), its `$0` gates and one
     `C-MODEL-CHECK` of up to `$1` for the curator instructions. **Approve.**

## What changes for whom

| Reader | Today | After this migration |
| --- | --- | --- |
| Curator | Invents a `type` per fact; scope is `game` or `world`; revising mints a new ID; superseding a cited fact forces rewriting every citing article at once | Picks a `claim_kind` and tags; uses declared axes; edits articles surgically under one slug; may leave stale citations in admission; validates before finishing |
| Gate | Checks references and two-level scope with hand-coded shape checks | Validates shapes by JSON Schema; checks declared axes, the scope order, end evidence and identifier rules; carries citations; recomputes lifecycle and flags as a fixed point |
| Exporter | Selects `game` facts and the run's `world` facts | Evaluates scope, `when`, lineage and article eligibility against the target; builds identifiers, history, aliases and flags from the eligible and public sets |
| Player | Sees `id`, `type`, `text`, `seen` per fact; untyped title links; flat ranked search | Also sees core fields, blinded `scope`, `branch_relation`, review flags, typed links, backlinks, citations and history, with status markers everywhere. Search follows the article graph |
| Spectator view (#464) | Shows every fact's scope as unrecorded | Shows the delivered scope class, flags, links, tags and claim kinds through `spectator-view/3` ([mapping](#mapping-the-spectator-deliverables-464)) |
| Belief comparison (#677) | Must reconstruct support from prose | Reads citation sets with origins, immutable revisions, supersession and contradiction edges, retirement reasons and end bounds; polarity stays in #677's extraction ([bridge](#provenance-bridge-to-the-belief-comparison-677)) |

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
#924 queries on both corpora with #920's merged ranking as the baseline for the overall
ranking change. For the coverage skip it runs a paired comparison on a labelled
direct-answer subset: `bm25_1hop` with the skip against the identical `bm25_1hop` with
the skip disabled. The [ranking gate](#offline-verification-gates) is defined against
that record.

The query set is in-sample. Twenty-eight queries were written by the #924 study
together with their gold labels. The other two came from live `#896-b`
`player_knowledge_query` calls at `A01 v3` and `A03 v38`, and the record also replays them
retrospectively on `v91`. Hit@5 credits a gold article or a fact it cites, so it cannot
tell whether the directly usable answer was returned.

### What the sealed curator run shows

Three independent reviews of the earlier draft recounted the sealed `#896-b` store
(`v0` to `v91`) at `.runtime/evidence/seven-day-896-b-admission-10/knowledge/`, with its
gate results, session submissions and Git tags. Their counts are not yet in a dated
record. The benchmark-and-recount slice, which runs first, commits the read-only recount
script beside the `#920` baseline benchmark and publishes both in one dated `#896-b`
curator-behaviour and retrieval record before decision 7's curator changes are
implemented (`#937`) ([plan](#migration-plan)). The counts bear on
the curator operations only:

- All 91 gate results published and none was rejected, and no revision silently dropped a
  fact. Whole-article rewrites are therefore not a correctness problem.
- Of 23 restatements, 11 would fail a rule that makes the curator copy every old citation.
- Of 66 `revise_article` calls, 40 changed at most three claims. About two-thirds of all
  claims came back byte-identical.
- Admission prompts outnumbered completions by about 279 to 1, so smaller edits save
  little money. They matter for guaranteed preservation, cheaper grooming repair and
  fewer copied hexadecimal IDs, about ten of which were mistyped.
- Three of the last four groomings wrote nothing. Each re-read about 496 KB of current
  records, and each stopped on HTTP 429 spend-reservation refusals after prompts of about
  207,000 to 226,000 tokens, recorded as `provider-error`; none reached its request cap.
  #918 fixed the over-reservation. All nine aborted sessions (six admissions, three
  groomings) ended on `provider-error`. One admission's written submission was lost,
  because today close-out gates submissions only after a clean exit.
- The delivered file of the tenth admission names the lineage label 440 times, inside
  session names in `seen`, and once more in `coverage.session`. At `v91` that coverage
  value is still a lineage-labelled session name (`run/actors/001/knowledge/v91.json`
  line 2398), and the host passes the coverage object into the player's update.

## Lenses that shape the design

Each lens below is a way of looking at the problem that yields a concrete rule and a
check. None of the mathematics is implemented as such.

### Scopes form a partial order

A scope is a finite map from axis to value that always contains `game`. Read it as a
set of `(axis, value)` pairs. Then `s ⊑ s′` (s is at least as general as s′) exactly
when `s ⊆ s′`. For example, `{game}` ⊑ `{game, biome: forest}` ⊑
`{game, biome: forest, world: W1}`.

- **Predicates, not stored maps.** Order, join and overlap are computed in the uncapped
  space of axis predicates. The eight-axis limit applies only to a stored record. Two
  legal eight-axis maps that share only `game` have a fifteen-axis join: their
  predicates overlap, even though no stored record could carry that join.
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
  it cites. Code computes that join as the article's minimum scope, and the curator adds
  only further declared axes. The gate refuses an article whose cited facts have no join.
  Antitonicity covers the scope part. The exporter still checks every cited fact's
  eligibility in full, because the per-record tests can exclude a fact whose article
  scope passes ([articles and their facts](#an-article-is-eligible-only-with-every-cited-fact)).

### Contradictions that do not glue

Think of the facts valid at each scope as a family of local views, where moving to a
more specific scope keeps everything the general scope holds. Two worlds' observations
are local views. They combine into one game-wide claim only if they agree. When world
W1 shows one behaviour and W2 another, there is no game-wide claim to write: both
observations are right where they were made.

**Rule this gives:** a `contradicts` link is classified by each record's **constraint**,
the union of its `scope` and its `when.requires`. The gate refuses a record whose own
`scope` and `requires` give one axis two values.

| Constraints | Scopes | Result |
| --- | --- | --- |
| A shared axis differs | Any | Disjoint. No conflict. Both stay `active` |
| Compatible | Equal | Conflict. Both are `contested` |
| Compatible | Incomparable | Conflict inside the join. Both are `contested` wherever both are delivered |
| Compatible | Comparable, unequal; the specific record has no `when` | The specific record *shadows* the general one inside its scope. The general one stays `active`, delivered with `shadowed_by` |
| Compatible | Comparable, unequal; the specific record has a `when` | Conditional shadow: as above, but it holds only where that `when` holds, which the player checks |

- **Cross-comparison.** Because the constraint joins both maps, one record scoped to
  `{mode: hard}` and another requiring `{mode: easy}` are disjoint, even though one
  axis is a scope and the other a condition.
- **Unknown exclusion.** A pair whose constraints cannot be shown disjoint counts as
  compatible. A `when` with only a `note` is one example. The conservative result is a
  conflict, and the curator removes it by stating the distinguishing axis in
  `requires`. A `requires` axis never excludes delivery when the target lacks it; it
  only flags the record ([why](#unknown-scope-is-not-unknown-condition)). Scope overlap
  is never unknown, because a join is computed from the maps alone.
- **Existential aggregation.** A record is `contested` when at least one incident
  `contradicts` link classifies as a conflict. A disjoint pair never clears a conflict
  that another pair established, so the result does not depend on the order of pairs.
- **Two views of the state.** The stored `contested` state is the curator's repair
  signal and ignores the target. The delivered state is recomputed in the target's view
  ([review flags](#stale-citations-and-review-flags)). A conflict with a record the
  target does not receive therefore does not mark a delivered record.

**Operation this gives:** `narrow_fact` replaces one over-general fact by facts scoped
more narrowly, through declared axes or a world binding, and keeps its citations. It never
overwrites a valid local observation with another place's observation. Today a
replacement must keep the level, so the curator cannot repair an over-general `game`
fact without retiring it.

### Minimal change

AGM belief revision asks that adding information change no more than necessary. Here
that becomes four acceptance tests for the gate and for grooming:

1. **Success.** Every record a submission adds is current in the candidate.
2. **Preservation.** Some records are not targeted by an operation and are not in the
   propagation closure of one. In the candidate, each such record is byte-identical to
   the base, apart from software fields whose inputs did not change (so, none). Inside
   a targeted article, `edit_article` and `remap_citations` keep every claim they do not
   name byte-identical.
3. **Citation carry-over.** A restatement, merge or narrowing keeps every origin
   citation of the facts it replaces. Code adds them to a restatement itself. Evidence is
   never silently dropped, which is also what the belief comparison needs (see
   [the provenance bridge](#provenance-bridge-to-the-belief-comparison-677)).
4. **Scope consistency.** After publication, every current record's stored `contested`
   bit equals `any(incident current pair is a conflict)` under the
   [classification table](#contradictions-that-do-not-glue), plus the
   [article inheritance rule](#stale-citations-and-review-flags). A record may have a
   disjoint neighbour and a conflicting one; it is `contested`.

### Coverage versus redundancy

Facility-location selection picks a set `S` to maximize `f(S) = Σᵤ maxₛ∈S sim(u, s)`.
The function is submodular, so greedy selection by marginal gain is near-optimal under a
cardinality budget. With `sim(u, s) = 1` when `s` is `u` or an article citing `u`, `f`
counts the distinct records that a result reaches.

The query step here is only *inspired* by that objective. It walks the ranked list in
score order and skips a fact that a record already kept cites. It never reorders by
marginal gain, so it inherits no approximation bound. With one slot and a singleton
ranked above an article that covers `m` facts, the walk covers one record where greedy
covers `m + 1`, so the ratio tends to zero. It is a cheap way to spend result slots on
records an article does not already carry.

The skip deletes only facts from a fixed ranking. Every article therefore keeps or
improves its rank, so article MRR@5 and article Recall@5 **cannot fall** by
construction, and a gate on them would pass vacuously. The risk is elsewhere. Take the
order `[article, fact, unrelated]` with two slots, where the article cites the fact but
its prose omits the fact's exact number. The skip returns `[article, unrelated]` and
drops the only direct answer. So the Wave 3 benchmark keeps the skip only if, against
the identical one-hop ranking with the skip disabled, it raises distinct records reached
without lowering direct-answer fact retrieval or adding reads. Comparing it with flat
BM25 instead would credit the one-hop gain to the skip
([ranking gate](#offline-verification-gates)).

The cut briefing keeps its recency rule. No sealed record shows its budget binding on
articles. The trigger to revisit it is in [What is not known](#what-is-not-known).

### Propagation to a fixed point

Review flags are monotone booleans over a dependency graph. They are defined as the
least fixed point of local rules, so the result does not depend on the order in which
records are visited, and cycles terminate. An unseeded dependency cycle stays clear.
At current sizes (under 600 records), a full recomputation at every publication and
every export is cheaper than keeping incremental state. So "incremental" describes the
definition, not a separate engine.

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
| `lifecycle_state` | `active`, `contested`, `superseded`, `retracted`, `ended` | Facts and articles | software | Each publication | Whether it is still the current statement, and if not, why |
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
is later `superseded`.

**The five lifecycle states.** Software derives each from the operations alone, so the
gate stays the only writer:

- `active` and `contested` are current ([derivation](#stale-citations-and-review-flags)).
- `superseded`: replaced by a faithful restatement, a narrowing or the next article
  revision. **Checked invariant:** a `superseded` record has a non-empty
  `superseded_by`.
- `retracted`: shown to be false, by a `corrected` supersession (which also has a
  `superseded_by`) or a retirement with `reason_kind: wrong` (which has none).
- `ended`: retired with `reason_kind: ended` (a fact whose state stopped holding) or
  `editorial` (an article withdrawn without a claim about the world). It has no
  `superseded_by`.

So a reader of one stored row can tell a broken redirect from an ended state, and the
converse of the invariant fails only for `retracted`, by design.

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
| `scope` | R: D `game`, declared curator axes, D `world` when bound | D minimum from cited facts, plus declared axes | D: [blinded](#operator-blinding) | D: blinded |
| `when` | O | — | O | — |
| `links` | R, may be empty | R, may be empty | D: [public targets only](#public-identifiers) | D: public targets only |
| `citations` | R: non-empty distinct frame source IDs; D union for a restatement | — | D: as `citation_source_ids` | — |
| `lineages` | D on world-bound facts | D on world-bound articles | — | — |
| `seen` | D: latest cited frame | — | D: session [aliased](#operator-blinding) | — |
| `last_confirmed` | — | D: latest `seen` among cited facts | — | D: session aliased |
| `valid_from` | D: earliest cited frame | D: latest `valid_from` among cited facts | — | — |
| `valid_to` | D: see [end times](#observed-ends-and-censoring) | D: `null` | — | — |
| `lifecycle_state` | D | D | D: target view | D: target view |
| `stale_citations`, `needs_review` | D | D | D: target view, public IDs | D: target view, public IDs |
| `condition_unverified`, `unverified_branch` | — | — | D | D: true when any cited fact's is |
| `branch_relation` | — | — | D | D |
| `backlinks`, `shadowed_by`, `contradicted_by` | — | — | D | D |
| `cited_by_articles` | — | — | D: slugs | — |
| `superseded_by` | D: absent while current; one or more fact IDs | D: absent while current; exactly one revision ID | — | — |
| `retired` | D: `{reason_kind, …}` (`wrong`: `reason`, `citations`, `published_in`, `session`; `ended`: `events` list) | D: `{reason, reason_kind, published_in, session}` | — | — |
| `retagged` | D: absent until the first retag; a list of `{from, to, version}` | D: as for a fact | — | — |
| `published_in`, `session` | D | D | — | — |

- **`superseded_by` is a list.** It names one fact for a restatement or a corrected
  supersession, two or more for `narrow_fact`, and the next revision for an article. The
  supersession reason is not stored, because it follows from the operation and the
  lifecycle state: `retracted` with a successor was corrected, and `superseded` with
  several successors was narrowed. `superseded_by` and `retired` never appear together.
- **`retired.reason_kind`** is `wrong` or `ended` on a fact and `wrong` or `editorial`
  on an article. On a `wrong` fact, `retired` is `{reason, reason_kind: "wrong",
  citations, published_in, session}` with non-empty `citations` (terminal; never retired
  again). On an `ended` fact, `retired` is `{reason_kind: "ended", events}` where
  `events` is a non-empty list of `{reason, end, end_citations, citations, valid_to,
  published_in, session}`: one entry in linear histories, or more when a fact ended on
  an abandoned stretch or sibling branch and later ended on another surviving timeline
  ([observed ends](#observed-ends-and-censoring)). Each event's `end` (`transition` or
  `absence`) and `end_citations` are non-empty, and `citations` is optional supporting
  evidence (possibly empty). On an article, `retired` has no citations.
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

`provenance.json` keeps `frames`, `sessions` and `last_admission`. Each `sessions` entry
gains `context`, the package's declared target axes. It also gains two operator-label
maps. The gate copies all three from verified session labels and never takes them from a
submission:

- `branches` maps a lineage label to
  `{"parent": label or null, "fork_at": position or null, "fork_version": version or null}`;
- `restores` is a list of
  `{"lineage": label, "restored_at": position, "restored_version": version or null, "saved_at": position or null, "saved_version": version or null}`.

`fork_version`, `saved_version` and `restored_version` are the latest knowledge version
published before the save at `fork_at` or `saved_at` was written, or before the restore
at `restored_at` began. They give fork and restore selection a publication coordinate
comparable with a record's `published_in`; a trace position alone is not.

`null` means unknown. Under owner decision 4(a), every lineage is recorded with every
`branches` field `null`, and `restores` is empty. Under 4(b) all come from
`campaign-run/14` labels. The gate refuses a history where one lineage has two different
parents, fork points or fork versions, and a `branches` parent graph with a cycle (such
as `A.parent = B` and `B.parent = A`), because ancestor traversal needs an acyclic
history.

The **declared axes** of a store are the union of the `context` keys of its recorded
sessions. A submission may use only those as curator scope axes
([the scope map](#the-scope-map)).

### Submission changes (`curator-submission/2`)

| Operation | Change |
| --- | --- |
| `add_fact`, `add_article` | New core fields; the article names its `slug`. Code fills `scope.game`, the article's minimum scope and any world binding |
| `supersede_fact` | Adds `reason_kind`. Code copies the replaced scope. `restated`: code unions the replaced citations; the curator lists only new frames; `when` must be equal. `corrected`: needs a frame none of them cited |
| `narrow_fact` | New. One current fact and two or more replacements, strictly narrower in scope while preserving or strengthening `when`. Inherited citations are exempt from the window check |
| `retire_fact` | Adds `reason_kind` (`wrong` or `ended`). `ended` requires `end` and non-empty `end_citations` ([end times](#observed-ends-and-censoring)); `citations` is optional supporting evidence |
| `retire_article` | By `slug`. Adds `reason_kind`: `wrong` (becomes `retracted`) or `editorial` (becomes `ended`, `valid_to: null`) |
| `revise_article` | By `slug`, for restructures. Omitted top-level fields inherit from the current revision; `null` is refused |
| `edit_article` | New. Surgical edits by claim index with an exact-text guard ([editing](#editing-articles)) |
| `remap_citations` | New. Swaps a restated fact's ID in the named articles ([editing](#editing-articles)) |
| `retag` | Replaces `revise_types`. Grooming only, at most once per submission. Maps record IDs or slugs to new tag lists |
| `add_type`, `revise_types` | Removed |

**Code, not the curator, does the bookkeeping.** Copying old citations, splitting world
labels, writing `scope.game`, computing an article's minimum scope and finding stale
records are deterministic, so code does them. The curator keeps the judgments only it
can make: whether a replacement says the same thing, which evidence supports which
narrowed child, `claim_kind`, `evidence_basis`, tags, axis values, slugs and prose.

- **Restatement in both session kinds.** Because code carries the old citations, a
  restatement needs no reuse of old frames by the curator. It is allowed in admissions
  as well as grooming, and an empty list of new citations is a pure restatement. A gate
  pass still establishes structure only: a curator can file a reversed claim as
  `restated`.
- **Supersession keeps where a fact applies.** Code copies the replaced facts' curator
  axes and world binding into the replacement, as today's gate refuses a scope change
  ([`gate.py`](../../harness/curator/gate.py) line 611). The gate refuses an `ids` list
  whose facts have different scopes, and any submitted `scope` holding a `game` or
  `world` key, which a curator copying a stored row would otherwise send. A `restated`
  replacement also needs a `when` equal to the replaced facts'. Equal applicability,
  scope and condition together, is what lets `remap_citations` keep an article's prose
  and eligibility unchanged. A changed condition is a `corrected` supersession or a
  `narrow_fact`.
- **Narrowing.** Each replacement must keep all parent scope axes equal and strictly
  narrow scope by either adding a declared curator axis or setting `binds: ["world"]` on
  a previously unbound fact. Each replacement must also preserve or strengthen the
  parent's `when` without clearing an unresolved condition: when the parent has a
  non-null `when`, every child must have a non-null `when` with the parent's exact
  `when.note` verbatim; if the parent's `when.requires` is empty (`{}`), every child's
  `when.requires` must also stay empty (`{}`) so `condition_unverified` stays `true`
  (turning an unformalized note into structured keys is a `corrected` supersession); if
  the parent's `when.requires` is non-empty, every child's `when.requires` must include
  every parent key with the same value (additional keys are allowed). By Kleene AND
  monotonicity, no child can then broaden applicability or flip an unknown condition to
  verified. The children's citations together must include the original fact's citations.
  Code fills each bound replacement's `world` from its own citations and refuses one
  that names two worlds or a session with no world. So narrowing a game fact into
  per-world facts needs no world label from the curator.
- **Narrowing in admissions.** A child's citations of the original fact's frames are
  inherited, so they are exempt from the trace-window check. `_publication()`
  ([`gate.py`](../../harness/curator/gate.py) lines 671 to 677) keeps them out of
  `last_admission.citations`. Otherwise the next grooming's `grooming_context`
  ([`window.py`](../../harness/curator/window.py) lines 212 to 213) would refuse the
  admission's citations as missing from its trace.
- **Article scope.** Code sets an article's scope to the join of its cited facts' scopes,
  including `world` when any cited fact binds it. The curator may add declared axes to
  narrow it further.

### Editing articles

Four substantive operations change an existing article: `revise_article`, `edit_article`,
`remap_citations` and `retire_article`. `retag` can also update an article's tags in
grooming.

**One working article per slug per submission.** A revision ID is
`<slug>@<published_in>`, so a slug can have only one revision per version. The gate
therefore keeps one working copy per slug. It starts from the base's current revision,
or from the `add_article` of the same submission. Every operation naming the slug applies
to that copy in submission order. At publication, each slug changed by a substantive
operation (`revise_article`, `edit_article` or `remap_citations`) gets exactly one new
revision, joined to the previous one by `supersedes`. A tag-only `retag` is exempt from
revision creation: it updates `tags` and appends `{from, to, version}` to `retagged` in
place on the current revision, keeping its revision ID unchanged. When a submission
combines `retag` with a substantive edit on the same slug, all operations apply to the
working copy in submission order and publish one new `<slug>@<published_in>` revision
carrying the final `tags` and the appended `retagged` entry. Compatible substantive
operations combine, such as two `remap_citations`, or a remap and then an
`edit_article`. `retire_article` together with any other operation on the same slug
(including `retag`) is refused, and the diagnostic names the other operation. Today's
gate refuses a second operation on one record ID within a submission
([`gate.py`](../../harness/curator/gate.py) line 558). This rule replaces that check
for articles; facts keep the within-submission limit (across submissions, a world-bound
`ended` fact may record an additional end event on a surviving timeline where it is
still alive; see [observed ends](#observed-ends-and-censoring)).

- **`revise_article`** takes `slug` and any of `title`, `lead`, `tags`, `links`, `scope`
  and `body`. An omitted field inherits unchanged from the working copy, as in RFC 7396
  merge patch. A present field replaces the whole value, so `body` is rewritten in full.
  Unlike RFC 7396, `null` never deletes a field: any `null` value is refused.
- **`edit_article`** takes `slug` and any of these:
  - `set_title`, `set_lead` and `set_scope`;
  - `add_claims`, a list of new claims appended in order;
  - `replace_claims` and `remove_claims`, each a list of `{index, old_text, old_facts}`
    (with `text` and `facts` for a replacement);
  - `add_links`, `remove_links`, `add_tags` and `remove_tags`.

  Indices refer to this operation's input body: the working copy as earlier operations
  left it. The gate validates every index against that input before applying any. It
  refuses an index out of range, an index named twice within or across `replace_claims`
  and `remove_claims`, and a result whose `body` is empty, which is what
  `retire_article` is for. A claim is identified by its text and its facts together:
  `old_text` and `old_facts` must both equal the indexed claim, or the gate refuses the
  operation. So a stale index fails safely, and two claims with the same prose but
  different citations cannot be confused. Replacements and removals apply to the input
  indices, then `add_claims` appends. Untouched claims stay byte-identical by
  construction.
- **Article scope in edits.** `edit_article.set_scope` and `revise_article.scope`
  accept declared curator axes only. `game` and `world` come from the cited facts, and
  the result must still be ⊒ the article's minimum scope.
- **`remap_citations`** is
  `{"op": "remap_citations", "from": "<old fact ID>", "to": "<new fact ID>", "in": ["<slug>", …]}`.
  - `to` must be the end of a chain from `from` in which every step is a one-to-one
    `supersede_fact` with `reason_kind: restated`, in the base store or the same
    submission. So `a → b` in the base and `b → c` in the batch allow a remap from `a`
    to `c`. Multi-input restated merges are not followed by `remap_citations`; after a
    restated merge, the curator updates affected claims with `edit_article`'s
    `replace_claims`.
  - Every slug in `in` must cite `from` in its working copy, or the operation is
    refused.
  - Code replaces `from` with `to` in each claim's `facts`. When a claim already cites
    `to`, it removes `from` instead, so the claim's facts stay distinct. All prose stays
    byte-identical.
  - Code recomputes the article's minimum scope, `last_confirmed`, `valid_from` and
    `lineages` from the updated citations. Equal applicability keeps the scope. A `to`
    with citations from another lineage can still change the article's branch relation
    at delivery.

The gate never remaps by itself. An automatic remap would publish article revisions no
curator session wrote. It would also be wrong for `corrected`, where the article's claim
may now be false, and for `narrowed`, where the article scope rule may refuse the
narrower fact.

**Atomic repair unit.** One submission may replace an immutable fact and, in the same
batch, edit or remap every record that cites it. At `v8`, for example,
`supersede_fact(f → g, restated)`, then `remap_citations(f, g, [guide])`, then
`edit_article(guide, …)` publish one revision, `guide@v8`. In a grooming session the
gate checks newly introduced stale debt on the post-batch candidate, never between
operations, by the [non-regression rule](#grooming-close-out). So a fact with a stale
premise and its current dependents can be repaired together.

### Validation before close-out

- **Why not the workbench.** A `validate` command under `harness/trace/workbench.py`
  cannot work. The import contract in `pyproject.toml` (lines 54 to 57) forbids
  `harness.trace` from importing `harness.curator` or `subprocess`. The sandbox's
  workbench holds only `harness/trace`, and Seatbelt exposes no `.git` history, which
  the candidate stage reads. `host.mjs` also refuses `run_workbench` once 80% of the
  budget is spent (lines 126 and 268 to 269), exactly when the curator finishes.
- **`harness/curator/check.py`.** A pure module, importing only the standard library and
  `jsonschema`, with no `subprocess` or Git access. It runs the gate's well-formed
  stage, its `base_version` check and its candidate stage, in the gate's order, against
  a published base. It also reports each article whose derived scope changes. The gate
  calls it on the repository; `harness/curator/validate.py` is its command-line entry
  over the workspace.
- **Staging into the sandbox.** `harness/curator/session.py` copies `check.py` and
  `validate.py` into `workbench/harness/curator/` and the two schemas into
  `workbench/schemas/`. It adds `jsonschema` to `WORKBENCH_DEPENDENCIES` (line 38). It
  exports a read-only `knowledge/validation-context.json` holding `base_version`,
  `reserved_ids`, `reserved_sessions` (every historical session identity and its
  recorded name, world, lineage, admission and `context` across prior Git tags, matching
  the post-restore reservation check in `tests/test_curator_gate.py` line 1451),
  `session_kind`, `window_frames`, `session_labels` and `declared_axes`. So validation
  needs no history read inside the sandbox, even after a knowledge-store restore, and it
  compares against the same published base and session reservations the gate will use.
- **`validate_submission`.** A host tool in `tools/curator_host/workspace-tools.mjs`
  that runs `validate.py` on one `submissions/<id>/submission.json` and returns the
  diagnostics. It publishes nothing. Because one session may repair over several ordered
  submissions (`01`, `02`, …), `validate.py` evaluates the ordered sequence in
  `submissions/` up to and including `<id>` starting from `base_version`, advancing the
  candidate version only after each passing submission and skipping rejected earlier
  ones without advancing (matching clean close-out in `session.py` lines 368 to 376). It
  returns each prefix file's verdict alongside `<id>`'s diagnostics. It is not in
  `host.mjs`'s reading-tool set, so the 80% refusal never blocks it. When every file in
  the prefix up to `<id>` passes, the host's event log records the ordered `(path,
  sha256)` list for that all-passing prefix, authorizing it for `provider-error`
  close-out and binding a later submission's pass to the exact bytes of every preceding
  submission it depends on.
- **Atomic submission files.** `write_file` writes to a temporary file in the same
  directory and renames it, so a submission file is either whole or absent.

**Abort-safe close-out.** Today close-out gates submissions only after a clean exit
(`session.py` line 367), and `run.mjs` exits with code 1 on every failure (line 33), so
`session.py` cannot tell a provider error from a crash.

- **Detection.** `runCurator`'s result and the `host-end` event already carry
  `reason: 'provider-error'` (`host.mjs` lines 400, 428 and 440 to 442); `run.mjs` maps
  that reason to a reserved exit code. A crash, invalid argument or invalid input keeps
  code 1.
- **Gating intent.** On a `provider-error` stop, `session.py` finds the longest
  all-passing ordered prefix of current files in `submissions/` whose exact `(path,
  sha256)` sequence matches a passing `validate_submission` call of that session, and
  gates only that prefix in order. That call is the curator's expression of intent short
  of `finish`. Every other written file (including any submission whose earlier
  dependency changed after validation, or followed a rejected file) is kept in the
  record, reported and not gated, so a half-written, stale or unchecked batch is never
  published.
- **Sealing.** When the sandbox reports `stopped is None` and the reserved
  `provider-error` exit code, `session.py` writes `lifecycle.stopped: 'provider-error'`
  and seals the session record with `state: 'sealed'` (overriding the nonzero-exit abort
  check at `session.py` line 335 only for that reserved exit code), so `shadow.py`
  (line 443) forwards `sandbox.stopped = 'provider-error'`. Drafts are collected with
  `drafts.collect(age=False)`, as for any aborted session today.
- **Runner.** `Outcome` (`harness/curator/runner.py` lines 160 to 172) gains
  `provider_error: bool = False`. `Sessions.__call__` in
  `tools/curator_host/live_runner.py` (lines 214 to 235) sets
  `provider_error = summary.get('sandbox', {}).get('stopped') == 'provider-error'` while
  leaving `Outcome.stop` unset unless a terminal proxy, cleanup or spend stop also
  occurred. In `runner.py`, `classify()` (lines 274 to 292) handles a sealed
  `provider_error` session before its ordinary `rejected` and `unknown` branches (after
  `lock-refused`, `SPEND_REFUSED`, `not-started` and `aborted`): advancement is computed
  strictly from whether any submission verdict is `'published'` or `'unknown'` (never
  advancing when all verdicts were `'rejected'` or empty, even if a gated submission
  unexpectedly rejected before tagging), `failed` is always `True`, and the outcome
  label is `'unconfirmed'` if `'unknown'` is present, `'rejected'` if `'rejected'` is
  present, else `'provider-error'`. Because `failed` is always `True`,
  `session_failures()` (lines 398 to 401) counts it toward `SESSION_FAILURES = 2` and two
  consecutive `provider-error` sessions stop the runner, preserving the spend-safety
  control in [`docs/components/curator.md`](../components/curator.md) line 214. With
  nothing published the cursor stays so a single transient error retries the window
  without duplicating work. Because `Outcome.stop` stays `None` and the outcome is not
  `SPEND_REFUSED`, `Runner._session()` (lines 711 to 717) neither halts on the first
  provider error nor halves the window (lines 676 to 683), while keeping all terminal
  `Outcome.stop` halting intact. The session record's stop reason discloses that the
  curator stopped partway through the window.
- **Grooming.** `failure_reason` in `tools/curator_host/groom.py` reports a sealed
  `provider-error` grooming as failed with reason `provider-error`, where it checks
  `session-not-sealed` today (lines 31 to 32). Any repair it published stays published.
- The [curator contract](../contracts/curator.md) and
  [`docs/components/curator.md`](../components/curator.md) (line 214) state this
  close-out and failure-count rule in the same change.

**Grooming worklist.** A grooming `brief.md` lists records in two parts, one compact line
each with its ID, state and the IDs it names. Grooming starts from that list instead of
scanning the whole store.

- **Must clear:** every current record with non-empty `stale_citations`. Close-out fails
  while one remains ([grooming close-out](#grooming-close-out)).
- **Advisory:** `contested` records and records whose `needs_review` comes only from
  them; world-bound records whose `lineages` hold several labels or `null`, which
  deliver `unverified_branch` to some targets; and unfiled facts.

**Filing rule.** `grooming.md` (line 23) says to file every current `game` fact. With
`scope.level` retired, the rule becomes: file every current unbound fact in at least one
current article, and file a world-bound fact once an article bound to its world exists.
A fact the rule covers that no current article cites is **unfiled**.

## Scope and conditions

### The scope map

A scope is an object with 1 to 8 axes. Axis names match `[a-z][a-z0-9_]{0,31}`.
Values are 1 to 64 printable characters.

- **`game`** is required, equals the repository's game, and is filled by code.
- **`world`** is the one software axis. Its value is the package's
  [world label](../decisions/owner-decisions.md#a-separate-world-label), an opaque
  operator name for one persistent game instance. A submission never writes it. It asks
  for it with `binds: ["world"]`, and the gate fills it from the citations' single
  world. `instance_state` requires `binds: ["world"]`. As today, a bound record is
  refused when its citations name two worlds or a session with no world.
- **Curator axes** are any other names that a package declared in its `context`, such
  as `ruleset`, `scenario`, `profile`, `level` or `character`. Their values are what the
  screen showed. No axis name is reserved for one game. A `context` key is a **run-wide
  invariant**: it holds one value for the whole run, such as `scenario`, `ascension`,
  `faction` or `patch`. A **transient condition** that can change within a run, such as
  `night` or `indoors`, is never a `context` key
  ([why](#unknown-scope-is-not-unknown-condition)).

**Undeclared axes are refused.** The gate refuses a curator scope axis outside the
store's [declared axes](#provenance), and a `narrow_fact` replacement that narrows only
through one. The diagnostic names the declared axes. A narrowing through
`binds: ["world"]` needs only a world on its citations. A situational qualifier that no
declared axis backs goes in `when.note` or the text. Without this rule, every export
would silently drop the record, which is the same as retiring it. `when.requires` may
name any axis, because an unknown condition delivers flagged.

**Axis names stay visible.** The curator `brief.md` lists the active package's declared
axes with their values and the curator axes current records use, with counts. That
makes drift, such as `biome` beside `terrain`, visible to the curator. Whether two names
mean the same thing is the curator's judgment; code detects only identical scopes.

**Lineage is provenance, not scope.** On a world-bound record the gate also writes
`lineages`. This is the sorted distinct list of the cited sessions' lineage labels, with
`null` for a cited session that records none. It is never an axis: a lineage says which
timeline the evidence came from, not where the claim holds. A record whose citations
span several lineages stays world-bound and keeps every lineage in the list. It is never
widened into an unbound record, because binding comes from `binds` and not from how many
lineages the citations name.

The submitted form has `scope` (curator axes only) and optional `binds`. The gate
refuses a submitted `scope` holding a `game` or `world` key. The
[cross-game table](../research-knowledge-graph-scoping.md#cross-game-stress-test-p-generality)
in the research note expresses each of its archetypes with these axes plus `lineages`.
Examples are a roguelite `profile` against a `run`, and a time loop whose
`instance_state` is bound to one loop through the world and lineage. A third is a
rule-rewriting puzzle with `level` plus `valid_to`. A deckbuilder's ascension, a
strategy game's faction and map, or a patch level are declared the same way, so a game
without a CDDA-like world still has first-class scope.

**`instance_state` needs a world.** Because `instance_state` must bind `world`, a game
whose packages carry no world label cannot hold `instance_state` at all; such a claim is
refused, which is safe. A roguelite uses the profile as its world label and must declare
a `run` axis in `context`, so that one run's state does not reach the next run. If the
curator omits the `run` axis, a dead run's state is delivered `same` with no flag.

### The target of an export

The exporter evaluates each record against a **target** built from the run package. It
holds `game`, `world` if the package names one, `lineage` if it names one, and the
package's `context` map (`{}` when it declares none). Under 4(b) it also holds the
package's `branches` and `restores` entries.

### Matching a record against the target

Each curator scope axis compares as **true** (the values are equal), **false** (they
differ) or **unknown** (the axis is absent from the target's `context`). Results combine
with Kleene's three-valued AND. Steps run in this order, and the first exclusion wins:

| Step | Test | Result |
| --- | --- | --- |
| Lifecycle | Not current (`superseded`, `retracted` or `ended`) | Not delivered, unless the [lineage rule](#lineages-forks-and-restores) selects it (pre-cut revision, or world-bound `ended` with no visible end on this lineage). May appear in [history](#public-identifiers) |
| World | The record binds `world`, and the target's is absent or different | Excluded |
| Curator axes | Kleene AND of the record's curator axes against `context` | False or unknown: excluded ([why](#unknown-scope-is-not-unknown-condition)) |
| `when` | Kleene AND of `when.requires` against `context` | False: excluded. Unknown: delivered with `condition_unverified: true` |
| Lineage | World-bound records only ([rules](#lineages-forks-and-restores)) | `same`, `inherited` or `unknown` (`unknown` adds `unverified_branch`); a known non-ancestor or post-fork revision is excluded |
| Article | Every fact in `body[*].facts` | Any cited fact excluded: the article is excluded ([rule](#an-article-is-eligible-only-with-every-cited-fact)) |

An unbound record has `branch_relation: null` and is never `unverified_branch`, because nothing
about it depends on the timeline.

### Unknown scope is not unknown condition

A scope axis and a `when` condition say different things. A scope axis is a
prerequisite that holds or fails for a whole run, such as the ruleset. If the target
does not say, the exporter does not know whether the claim applies at all. A `when` may
name a run-wide axis or a transient condition, such as night or indoors. The exporter
can rarely decide a transient one, but the player can check it on the screen when it
matters. So the two unknowns get different treatment:

- **Unknown scope axis: excluded.** The record does not enter the delivered file, so it
  never reaches a briefing, an index, a cut or a query result. Delivering it with a flag
  would promote a claim whose prerequisite is unconfirmed into ordinary retrieval.
- **Unknown `when`: delivered** with `condition_unverified: true` and its `note`.

`when.requires` uses the curator-axis grammar. A `when` with an empty `requires` is
unknown, so it is always delivered flagged.

- **Run-wide `requires` axes are settled.** A `requires` axis that the target's
  `context` declares is a run-wide invariant, so it is true or false for the whole run.
- **Transient `requires` axes stay unknown.** Because no package declares `night` or
  `indoors` in `context`, a fact requiring `night: true` is always delivered with
  `condition_unverified: true`, and the player verifies it on screen. Freezing such a
  condition into `context` would exclude the fact for a run in which night later falls.
  [`docs/operations/campaign-run.md`](../operations/campaign-run.md) gains this rule for
  package authors.

The exporter writes the number of records excluded for an unknown axis into
`private/knowledge-full.json`'s `selection` as `excluded_unknown_axis`. Because the gate
refuses undeclared axes, that count is non-zero only when the target package declares
fewer axes than the store's declared union, the `context` keys of all its recorded
sessions. The evidence for an excluded record may come from a session that declared
fewer axes than that union.

The **permitted transfers** are the only cases where a record reaches a target other
than the one it was observed in:

1. **Unbound records** with no curator axis, or only axes the target matches, go to every
   such target of the game. With no axes this is today's `game` rule.
2. **Same world, same lineage**, with no labelled restore in between: delivered with
   `branch_relation: same`.
3. **Same world, known ancestor lineage** (4(b) only): the revision visible at the fork
   is delivered with `branch_relation: inherited`.
4. **Same world, unknown or mixed lineage**: delivered with `branch_relation: unknown`
   and the status `unverified_branch`. This covers world state such as cached loot on a
   map tile when a different start or character uses the same world.

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

- **Flags flow up.** A delivered article is `unverified_branch` or
  `condition_unverified` when any cited fact is, in the target's view. It is
  `contested` by the single [article conflict rule](#stale-citations-and-review-flags),
  and `needs_review` comes from the fixed point that follows it.
- **Narrower examples.** A broader article may point to a separately scoped example
  only by a `see_also` link to that article or fact, never inline in a claim. The link
  is dropped where the example is not delivered, like any link to a record that is not
  public.

### The enforcement order

The exporter applies these steps in this order. Graph steps see only what earlier steps
kept:

1. **Eligibility.** Evaluate facts, then articles, against the target. For world-bound
   records this includes the lineage rule's choice of revision. The result is the
   **eligible set** `E`.
2. **Withholding draw.** Apply it to `E`. Ordinary and pilot exports use
   `knowledge-units/1`, and study exports use `knowledge-units/2`. A unit holds an
   article and every fact only it cites. A fact cited by several articles is delivered
   whenever any of them is kept, so a kept article always keeps its facts. The result is
   the **public set** `P`. An export **withholds** when it has a seed or a study draw
   (`seed is not None or study is not None`), as
   [`tools/knowledge_export.py`](../../tools/knowledge_export.py)'s `export()` already
   distinguishes. A study draw sets `seed` to `None`, so a seed alone is not the test.
3. **Public identifiers and flags**, in this order:
   1. `stale_citations` for each record in `P`, judged against `E`
      ([review flags](#stale-citations-and-review-flags)). A dependency in `E` but not in
      `P` is withheld, never stale.
   2. Drop every link, of every relation, whose target is outside `P`.
   3. Classify the remaining `contradicts` links, apply the article conflict rule, add
      `unverified_branch`, and only then compute `needs_review` as the fixed point over
      `P`.
   4. Build history from `P` and the [public history rule](#public-identifiers), and
      drop names outside `H` from `stale_citations`.
4. **Graph.** Compute `backlinks`, `cited_by_articles`, `shadowed_by` and
   `contradicted_by` from the remaining links and citations.
5. **Aliases.** Replace session names in delivered positions and the coverage stamp
   ([operator blinding](#operator-blinding)).
6. **Write.** The application's ranking and the host's briefing work only on that file.

`private/knowledge-full.json` holds `E` before the draw, so the measurement check that
`units(full)` equals `private/units.json` still holds. Steps 3 to 5 run on the drawn set
only.

### Public identifiers

Every field that names another record names only a public identifier, and the exporter
fixes those identifiers before it derives any backlink.

- **The public set `P`** is the delivered records' IDs, slugs and delivered article
  revision IDs (`<slug>@<published_in>`).
- **The public history set `H`** holds the IDs of retired facts, the slugs of retired
  articles, and earlier article revision IDs of delivered slugs, when each would pass
  step 1 for this target if it were current. When the export withholds, `H` is further
  restricted to IDs whose terminal replacements meet `P`. So a draw never reveals,
  through an old ID's descriptive text, a unit it withheld. Revision IDs of a retired
  slug are not in `H`; only the slug is.
- The **terminal replacements** of an ID in the target's view,
  `terminals_in_target_view(id)`, are the records reached by following `supersedes`
  edges through any number of steps until a record current in `E`. A redirect names only
  `terminals_in_target_view(id) ∩ P`. An empty redirect is omitted. Intermediate
  revisions are never named on another's behalf. Each one that is in `H` gets its own
  entry.
- **Reason composition.** A redirect's `reason` is the most severe along every path
  it flattens: `corrected` over `narrowed` over `restated`. So
  `a —restated→ b —corrected→ c` resolves `a` as `corrected`, never `restated`.
- **End events follow branch visibility, inside `H` itself.** A world-bound `ended`
  record has a **visible end** for target lineage `L` in two cases:
  - for an `ended` fact, at least one event in `retired.events` has every frame in its
    `end_citations` on a [surviving timeline segment](#observed-ends-and-censoring) of
    `L` (none in an abandoned stretch, and no `saved_at: null` restore between `seen`
    and any end frame of that event);
  - for an `editorial`-retired world-bound article, its `retired.session` belongs to `L`
    (the curator session's admitted trace lineage, or `last_admission`'s lineage for
    grooming, equals `L`, never `null`), for every labelled restore on `L` positive
    evidence places the retirement outside the abandoned stretch (either `saved_version`
    is known and `retired.published_in <= saved_version`, or `restored_version` is known
    and `retired.published_in > restored_version`), and if `L` has a fork cut,
    `fork_version` is known and `retired.published_in > fork_version`.

  A world-bound `ended` fact or `editorial`-retired article enters `H` (and
  `history.ended` when not withholding) only when it has a visible end for `L`.
  Otherwise every recorded end may postdate the target's fork or lie on another branch
  or abandoned stretch, so the ID is in neither `H` nor `history.ended`: if the target
  still delivers the record in `P`, a read by identifier (`by: "id"`) resolves
  `current`; otherwise it resolves `unknown`, never `ended`. No `stale_citations` list
  or redirect can name an ID that reads `unknown`. This holds with or without
  withholding.

| Field | Allowed identifiers | Otherwise |
| --- | --- | --- |
| `body[*].facts` | In `P` | The article is excluded |
| `links[*].target` | In `P` | The link is dropped |
| `history.replaced` keys | In `H` | No entry |
| `history.replaced[*].by` | `terminals_in_target_view(key) ∩ P` | The replacement is dropped. An entry with no replacement is removed |
| `history.ended`, `history.retracted` | In `H`, when the export does not withhold; `H` already applies branch visibility to ends | Not listed |
| `stale_citations` | In `H` | The name is dropped. `needs_review` stays true without naming it |
| `revision` | The delivered revision of a slug in `P` | — |
| `backlinks`, `cited_by_articles`, `shadowed_by`, `contradicted_by` | Derived from the links and citations above | — |

Two examples show the rule. Suppose `narrow_fact` splits a fact into a W1 fact and a W2
fact. For a W1 target the redirect names only the W1 replacement, because the W2 fact is
not in `P`. A chain `a → b → c` resolves `a` to `c`. It names `b` only if `b` is in `H`,
and then in its own entry.

The invariant is about identifiers, not every bit. Under a withholding draw, the word
`narrowed` on a redirect with one surviving replacement still says that a narrowing
happened. It names no withheld record and is accepted as disclosed.

A test asserts the resulting invariant on the synthetic two-world, two-lineage
repository. No delivered record, link, backlink, history entry or index line names an
identifier outside `P ∪ H`.

### Operator blinding

The guarantee is about operator-sourced data. World labels, lineage labels, `branches`,
`restores`, session names and the withholding layouts in `private/units.json` are never
emitted in a delivered file. The delivered record builders enforce that by construction:

- A world-bound record's `scope.world` is delivered as `null`. Only records of the
  target's own world pass the world step, so `null` always means "bound to this run's
  world, label withheld". This holds for other-lineage records too.
- Lineage is never delivered as a label. A world-bound record carries `branch_relation`
  (`same`, `inherited` or `unknown`), and an unbound record carries `null`. `unknown`
  never claims the record came from this run's own timeline.
- **Session aliases.** Session names embed operator labels; a sealed `#896-b` delivered
  file repeated its lineage label inside them hundreds of times. Every session name in a
  delivered `seen`, `last_confirmed` or `coverage.session` is therefore replaced by a
  deterministic opaque alias. Aliases are `s` followed by at least two digits (`s01`,
  `s02`, …, `s99`, `s100`, with no upper bound), numbered by first trace position within
  that export. This covers the initial `delivered-knowledge.json`, every live update
  under `curator-runner/delivered/`, and a whole-admission coverage stamp. The coverage
  object reaches the player through the host's update
  ([`knowledge.mjs`](../../tools/player_host/knowledge.mjs) line 252). The real map is
  kept only in `private/knowledge-full.json`'s `selection` as `session_aliases`. `actor`,
  `step` and `order` are unchanged.
- **Citation source IDs are opaque, not anonymous.** `citation_source_ids` keep the
  stored form `<32-hex session ID>-<capture ID>`
  ([`runtime.py`](../../harness/computer/runtime.py) line 139), so `player_source` and
  the spectator's anchors keep working. A recount of the sealed `#896-b` store matched
  all 1,117 distinct citation IDs to that form. They carry no world or lineage label.
  They do let a reader correlate frames of one session across exports, and with a
  session ID known by other means. This migration accepts that limit on blinding.
- The world label, lineage label, `context`, aliases and the unknown-axis count appear
  only in `private/knowledge-full.json`'s `selection`, whose keys are exactly `world`,
  `lineage`, `context`, `session_aliases`, `excluded_unknown_axis` and
  `delivered_sha256`. Preflight checks `world`, `lineage` and `context` against the
  package.

Curator-authored strings are a separate boundary. This guarantee does not cover prose,
tags, fact IDs, slugs and `when` notes. If a curator wrote a label into text, delivery
would carry it, and a literal scan cannot catch a paraphrase. Which labels the curator's
inputs expose is owned by the [curator contract](../contracts/curator.md); today the
published tree it reads includes `provenance.json`. This migration does not widen those
inputs. Removing raw labels from them is the stronger fix if blinding must cover prose.

Two projection tests verify the guarantee, both in `tests/test_knowledge_export.py` on
the synthetic repository:

- `test_delivered_bytes_carry_no_operator_label` searches every delivered byte for every
  world and lineage label in the repository's provenance and the target. It checks both
  an initial delivered file and a live update, including their coverage stamps. Its
  fixture uses realistic session names that contain those labels, in the
  `<lineage>-a01-<suffix>` form of sealed runs, so the test fails if the alias layer is
  removed from any position.
- `test_no_delivered_reference_leaves_the_public_sets` checks the invariant above.

The shared reader fixtures also include files that the readers must refuse because they
carry a label-shaped `world` value.

**Spectator anchors without positions.** Today the spectator resolves a `seen` or
`last_confirmed` position to a step of this run only when its session is this run's ID
or runner name ([`delivered.py`](../../harness/viewer/delivered.py) lines 108 to 115).
An alias such as `s01` matches neither, and the
[spectator contract](../contracts/spectator-view.md) (line 200) bars reading the private
alias map. So `spectator-view/3` resolves anchors from `citation_source_ids` instead:

- A **fact's** anchor is the step of this run whose source ID is one of the fact's
  `citation_source_ids`, matching this run's 32-hex `info.session`; with several, the
  latest step.
- An **article's** anchor is the latest such step among its cited facts'
  `citation_source_ids`.
- A citation of another session has no anchor (`null`), as a position of another
  admission has today. Nothing under `private/` is read.
- `harness/viewer/knowledge.py` (line 81, `source_ids`) and `delivered.py` make this
  change, and the contract's anchor text (lines 216 to 219) changes with them.

## Time, lineages and staleness

### Two kinds of time

- **Publication time** is `published_in` and the `published_in` of `superseded_by` or
  `retired`. It says what the store said at each version, and replay of a prefix uses
  it. "What did the store assert at `v2`?" is a publication-time question.
- **Observed validity** is `valid_from` and `valid_to`, both trace positions. No game
  clock exists, which is still true, and trace order says nothing about elapsed time.
  The claim was seen holding from `valid_from` and was last seen holding at `seen`. It
  may have held earlier. "Was this fire lit on day 2?" needs an observation on day 2 or
  a stated persistence assumption.

Restoring the knowledge store ([operator restore](../contracts/curator.md#operator-restore))
is a change in publication time and keeps its current rules. Loading an earlier *game*
save is a branch in the game's timeline, and the rest of this section handles it.

### Observed ends and censoring

`valid_to` is set only from evidence that the state stopped holding. A frame that shows a
lit fire cannot show that it went out, so `retire_fact` with `reason_kind: ended`
requires a non-empty `end_citations` list: frames showing the state ended. Ordinary
supporting frames go in optional `citations` (default `[]`). Both lists pass the usual
trace-window and provenance frame checks, while the **new end frame** rule and `valid_to`
selection apply strictly to `end_citations`. Every frame in `end_citations` must be
absent from the retired fact's stored `citations` (`end_citations` and the operation's
optional `citations` are disjoint) and placed after `seen` as follows.

- **A surviving timeline segment** of a lineage is its trace with every labelled
  abandoned stretch removed. A world-bound fact's `end_citations` must each lie on a
  surviving segment of `seen`'s lineage (or a descendant lineage forked from `seen`'s
  lineage at or after `seen`), strictly after `seen` along that timeline: neither `seen`
  nor any end frame may lie in an abandoned stretch. So a fire seen lit on an abandoned
  stretch and found absent after the restore bounds no transition. A restore with
  `saved_at: null` between `seen` and an end frame disqualifies that end frame, because
  its abandoned stretch is unknown.
- **Unbound facts** have no `lineages` field. Each frame in `end_citations` need only
  post-date `seen` in global trace order (`order`).
- **Which frame sets `valid_to`.** Only `end_citations` frames count. Ordinary
  supporting frames in `citations` set nothing, so carrying background frames alongside
  absence evidence never picks the wrong frame.

The curator also states `end`:

| Case | `end` | Stored | Meaning |
| --- | --- | --- | --- |
| Witnessed transition | `transition` | Event `valid_to` is the latest `end_citations` frame | The change was seen; its time is exact to the frame |
| Found absent later | `absence` | Event `valid_to` is the earliest `end_citations` frame | The change happened in `(seen, valid_to]` |
| Still holding at last sighting | — (not retired) | `valid_to: null` | Right-censored at `seen`; nothing says it ended |

- **One timeline or none.** An end event's `valid_to` is set only on a world-bound fact
  whose sightings and that event's `end_citations` lie on one surviving timeline
  (single lineage, or ancestor prefix plus descendant lineage). Top-level `valid_to` on
  the fact equals the sole event's `valid_to` when `retired.events` has length 1, and is
  `null` when distinct timelines hold distinct end events (each branch reads its own
  event's `valid_to`) or on unbound / multi-lineage facts.
- **Per-timeline end events after a restore or fork.** Across submissions,
  `retire_fact` with `reason_kind: ended` is accepted on a current fact, OR on an
  already-`ended` world-bound fact that is still alive in the resolved view of the new
  `end_citations`'s lineage (no existing event in `retired.events` is already a
  [visible end](#public-identifiers) for that lineage's surviving segment). The gate
  appends the new event to `retired.events` in place, keeping earlier tags intact. A
  second `ended` retirement on a lineage that already has a visible end — or on an
  unbound, `retracted` or `superseded` fact — is refused. Under 4(b), `session.py`
  includes any world-bound `ended` fact still alive on the incoming session's surviving
  lineage in `current-facts.jsonl` so the curator can retire it if it ends there.
- **A recurrence is a new episode.** A fire lit again after it ended gets a fresh fact
  ID. It neither supersedes the ended fact nor fills the gap between sightings.
- **Editorial article retirement.** An article makes no observation of its own, so
  `retire_article` cannot claim an observed end. `editorial` sets `ended` with
  `valid_to: null` and no citations; a cited fact's own end is recorded on that fact.
- **Faithful restatement is not an end.** `restated` changes the statement, not the
  world, and sets no `valid_to`.

### Lineages, forks and restores

A lineage is one operator-labelled timeline. The game can still be rewound inside one
lineage. The [evaluation record](../contracts/evaluation-record.md) reports this after
the fact: `lineage.continuity` records a negative game-time gap at an admission
boundary, and `lineage.elapsed` drops when a reload undoes activity. Both readings come
from the game clock on screen, which the curator store does not keep. So the store never
infers a rewind from frames. A rewind is known only from an operator label.

- **A fork point** is `branches[L].fork_at`: the position in the parent lineage after
  which lineage `L` no longer shares the parent's timeline. Its **cut** is the pair
  (`fork_at`, `fork_version`).
- **A restore point** is a `restores` entry. Within lineage `L`, the game was loaded at
  `restored_at` from a save written at `saved_at`. The stretch of trace strictly after
  `saved_at` and before `restored_at` is **abandoned**. A restore is a fork whose
  abandoned stretch is a dead branch, and its cut is (`saved_at`, `saved_version`).

What was visible at a fork is a historical revision, not the current record. A current
record restated after the fork can merge citations from before and after it, and the
child timeline never saw that merged statement. Two article revisions can also cite the
same pre-fork frames while only the first was published before the fork, and a later
`retag` rewrites tags in place. Citation order cannot separate those cases; the cut's
version can. So for each world-bound record, the exporter picks a revision in the
target's lineage view:

- **Same lineage, no abandoned stretch touched:** the current record — plus any
  world-bound `ended` fact or `editorial`-retired world-bound article in `L` that has no
  [visible end](#public-identifiers) for `L` (for example, a record ended only on a
  descendant branch) — delivered with `branch_relation: same`. The parent view that step
  1 below inherits applies this same rule.
- **Known ancestor or labelled restore (resolved view):** compute the target lineage
  `L`'s view in three uniform steps, recursively up to a root lineage:
  1. **Inherited base `V`.** For a known ancestor cut (`fork_at`, `fork_version`),
     start from the parent's resolved view at `fork_version` (never the raw Git tag
     alone) filtered to records whose citations in the parent lineage all lie at or
     before `fork_at`. For a labelled restore cut (`saved_at`, `saved_version`) within
     `L`, start from `L`'s own resolved view at `saved_version`. Mark all rows in `V` as
     `inherited`; post-cut ancestor or abandoned-stretch edits, retirements and retags
     are invisible.
  2. **Replay surviving own-lineage records in publication order.** A record in `L`
     (whether still `current` or later superseded or retired) is a **surviving
     own-lineage record** when all of its citations in `L` lie on `L`'s surviving
     timeline (none in any abandoned stretch `(saved_at, restored_at)`) — and, after a
     restore on `L`, either at least one citation in `L` lies at or after `restored_at`
     or (when `restored_version` is known) its `published_in` is strictly after
     `restored_version` (covering a pure restatement with zero new frames). Replay every
     surviving own-lineage record `r` published after the cut version in publication
     order: remove from `V` any record superseded by `r`, and add `r` to `V` as `same`.
     Because replay does not require `r` to still be `current`, a post-restore
     restatement `f → g` removes `f` even if `g` itself later ends or is replaced, so
     `f` is never resurrected.
  3. **Apply visible ends unconditionally.** Remove from `V` any world-bound fact or
     `editorial`-retired article that has a **visible end** for `L` under the exact same
     predicate used for `H` and `history.ended` ([public identifiers](#public-identifiers)).
     Removal is unconditional whether or not the export withholds, so a record in `V` is
     never delivered alongside `history.ended`: an identifier read (`by: "id"`) resolves
     `ended` when the export publishes end history, and `unknown` under withholding,
     which omits `history.ended`.

  Any record citing an abandoned stretch is excluded unless the cut supplies an earlier
  revision that survives steps 2 and 3. A post-fork record with no qualifying revision
  is excluded.
- **Rules for every selected row:**
  - **Later off-timeline ends stay visible; later falsity does not.** A record selected
    at an ancestor fork cut (or at a restore cut when its later end or supersession lies
    on the abandoned stretch) and later retired as `ended` or `superseded` off this
    timeline is still delivered as `inherited`: the state changed off this timeline, or
    only its wording did. Any surviving own-lineage replacement or visible end on `L` is
    already applied in steps 2 and 3 above, so it supersedes the cut. A record later
    `retracted` (retired as `wrong` or `corrected`) is never delivered: the retraction
    says the claim was false on the shared prefix too.
  - **Falsity follows faithful restatements and applicable narrowings.** Before
    admitting a row, walk forward in the current store from it:
    - follow every `restated` edge where the current node is replaced, including
      faithful multi-input merges (several duplicate inputs merged into one `restated`
      fact);
    - at a `narrow_fact` edge, test each child's scope and `when` applicability against
      the target (the matching table's world, curator-axis and `when` steps, where
      unknown `when` stays applicable) **independently of publication time, lineage cut
      and current lifecycle**, and continue into every applicable child.

    If any reached node is `retracted` (retired as `wrong` or superseded as
    `corrected`), do not deliver the inherited row: the claim was found false for this
    target. Retracting an inapplicable narrower sibling does not falsify the inherited
    row.
  - An article revision qualifies only if every fact it cites is the delivered revision
    of that fact.
  - The delivered `revision` names the article revision that qualified.
  - History never redirects such a fact to a post-fork successor, because that successor
    is not in `P`.
- **Known non-ancestor** (4(b)): excluded.
- **Unknown:** `branch_relation: unknown`, and the record is delivered with the status
  `unverified_branch`. This case covers:
  - the parent or fork is `null` (always, under 4(a));
  - the record's `lineages` hold the target's lineage and others (mixed);
  - a cited session has no lineage;
  - the target names no lineage;
  - a restore has `saved_at: null`, which applies to every world-bound record citing a
    position before `restored_at` in that lineage.

Three worked histories fix the expected outputs; all three are export tests on the
synthetic repository.

- **Nested cut.** Lineage `A` records fact `a` (a lit fire) at `v3`. `B` forks from `A`
  after `a`'s frame, with `fork_version: v3`. `A` then retires `a` as `ended` at `v5`.
  `C` forks from `B` at `v7`. `B`'s resolved view at `v7` holds `a`, inherited at `v3`.
  So `C` receives `a` as `inherited`. Reading the raw `v7` tag would find `a` ended and
  wrongly drop it. For an `A` target, `a` is in `history.ended`.
- **Parent target.** Lineage `A` records fact `f` at `v2`. `B` forks from `A` at `v2`
  and retires `f` as `ended` on `B` (`e1`) at `v3`. Because `e1` is not a visible end
  for `A`, an `A` target still receives `f` as `same` (and `A` may record its own end
  `e2` later); a sibling `C` forked from `A` at `v4` inherits `f` from `A`'s view.
- **Restore.** In lineage `L`, facts `f` (a lit fire) and `k` (a cached crate) are seen
  at position 10 (`v2`), and the game is saved at 12 (`saved_version: v2`). Fact `g` is
  seen at 15 on the abandoned stretch (`v3`). The game is restored at 20; at 22 (`v4`),
  `f` is observed extinguished (`end_citations` at 22) and fact `h` is seen. An `L`
  target at `v4` receives `k` as `inherited` and `h` as `same`; `f` is dropped from the
  saved view by its surviving post-restore retirement and resolves `ended` through
  `history.ended` (or `unknown` under withholding on `by: "id"` reads); `g` is excluded.
  Reading only the saved tag would lose `h` and resurrect `f`.

`unverified_branch` is not `contested`. `contested` stays reserved for a real
`contradicts` conflict; an unknown fork is an absence of evidence about the timeline, not
evidence against the claim. The status exists only at delivery, because it depends on the
target. It is not stored. It seeds `needs_review` like `contested` does: the target-view
fixed point below sets `needs_review` on every delivered record that relies on it. An
article citing such a fact is itself delivered `unverified_branch`, because flags flow
up. For a program precondition on volatile world state, `unverified_branch` and even
`same` call for a fresh screen check.

Without labels (4(a)), a reload inside one lineage is invisible. The store treats the
lineage as linear and may deliver a record that the reload undid as `same`. This is
listed under [what is not known](#what-is-not-known). The evaluation's rewind readings
are the trigger for 4(b).

### Stale citations and review flags

For a record `x`, let `R(x)` be what it relies on. For an article, that is the facts
its claims cite plus its `depends_on` targets. For a fact, it is its `depends_on`
targets. One function computes:

```text
stale_citations(x) = sorted { y ∈ R(x) : y is not current in the reference set }
needs_review(x)    = stale_citations(x) ≠ ∅
                     or ∃ y ∈ R′(x) : contested(y) or unverified_branch(y) or needs_review(y)
```

`R′(x)` is `R(x)` after links outside the view are dropped. `needs_review` is the least
fixed point: with `B` the records whose own condition holds, the flagged set is
everything that reaches `B` along `R′`. The computation starts with every flag false,
seeds a worklist with `B`, and propagates along the reverse of `R′` (cited-by and
depended-on-by). Each record is set at most once, so the work is `O(V + E)`, apart from
sorting the stale lists. `contradicts` seeds `contested` and does not itself carry review
further. The function runs on two views:

- **Stored view.** The gate runs it at every publication over the current records,
  using stored lifecycle. The reference set is the current records, and `R′ = R`.
  History validation recomputes the flags and refuses a stored version whose flags
  differ.
- **Target view.** The exporter runs it in step 3 over the post-draw public set `P`,
  never over withheld records. The reference set for staleness is the pre-draw
  eligible set `E`, including a revision the lineage rule chose. So a current dependency
  the draw withheld is not stale. Then every link to a record outside `P` is dropped
  before conflict classification and propagation, so a withheld record never marks a
  delivered record `contested`, `unverified_branch` or `needs_review`. Names that are not
  in `H` are then dropped from `stale_citations`, as the
  [public identifier table](#public-identifiers) says.

So a public record that depends on a withheld but current record shows
`needs_review: false`, exactly as if the dependency had never existed. Withholding
leaves no flag behind.

Stored `lifecycle_state` is derived from operations:

- `retracted`: corrected supersession, or retirement as `wrong`.
- `superseded`: restatement, narrowing or article revision; `superseded_by` is
  non-empty.
- `ended`: retirement as `ended` (facts) or `editorial` (articles).
- `contested`: current, and either joined by `contradicts` to a current record where at
  least one link classifies as a conflict in the
  [classification table](#contradictions-that-do-not-glue), or, for an article, citing
  a `contested` fact.
- `active`: otherwise.

**Article conflict rule.** The second `contested` clause is the one place that defines
article conflict inheritance. It is computed after fact conflicts are classified and
before the `needs_review` fixed point, in both views. So an article citing a contested
fact is `contested` whether or not it has a `contradicts` link of its own, and its
dependents see the same state whichever order records are visited in.

The delivered `lifecycle_state` is the same rule in the target view, over `P`.
`unverified_branch` is a separate delivered flag and status, never a lifecycle state.

An `ended` citation and a `restated` one raise the same flag but need different repairs.
For a one-to-one restatement, the curator checks the replacement and uses
`remap_citations` (for a restated merge, `edit_article`'s `replace_claims`). For an
ended state there is no successor to follow: the curator removes or time-qualifies the
claim with `edit_article`, or retires the article.

### Grooming close-out

Owner decision 2 moves one rule from the gate to close-out. An **admission** may publish
with stale citations, which today it may not. The rule that clears them applies to the
**successful close-out of a grooming session**, not to each grooming candidate. One
grooming session may repair over several submissions. If each candidate had to be clean,
repair would be atomic again, which decision 2 removes.

**Post-batch non-regression.** The gate still refuses a grooming candidate that adds
stale debt. It compares `(owner, stale_target)` pairs: the owner is a fact ID or an
article's slug, and the target is a name in its `stale_citations`. Every post-batch pair
must already be a base pair. A partial repair under the same slug passes. Moving debt
fails: if article `A` starts with stale target `f`, and one batch repairs `A` but adds a
citation of `f` to article `B`, the pair `(B, f)` is new and the candidate is refused.
Comparing only the set of stale targets, or the count of stale records, would accept it.
The check runs on the post-batch candidate, never between operations
([atomic repair unit](#editing-articles)).

- **Rule.** A grooming close-out succeeds only when no current record at
  `published_after` has non-empty `stale_citations`, the worklist's must-clear part. The
  rule counts stale citations only. The advisory part may persist: a `needs_review` that
  comes only from a `contested` dependency, a mixed-lineage record and an unfiled fact.
  Resolving a real conflict can need new evidence that grooming cannot get.
- **Reader.** [`tools/curator_host/groom.py`](../../tools/curator_host/groom.py) opens
  the repository at `published_after` and counts those records. The count goes into the
  summary as `stale_records`, which makes the format `curator-boundary-grooming/2`.
  `failure_reason` checks it after its existing checks, so a cap, proxy, sealing or
  `provider-error` failure is still reported first
  ([abort-safe close-out](#validation-before-close-out)).
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

Decision 2 lets repair debt grow while groomings fail, and `#896-b`'s groomings failed
on provider errors after very large re-reads. Four measures keep repair inside the
budget: the [worklist](#validation-before-close-out) in the brief, `edit_article` and
`remap_citations`, which make a repair a few lines, `validate_submission`, which finds a
gate error before `finish` even late in the budget, and abort-safe close-out, which
keeps a validated repair when the provider fails. If two consecutive groomings still fail with
`stale-citations-remain`, the operator procedure for failed grooming applies and the
owner reconsiders decision 2.

The flags are warnings for curator repair and player checks. The research note's
[findings on stale plans](../research-knowledge-graph-scoping.md#search-method-and-open-horizon-discovery)
show that marking is not a guarantee that a plan stops relying on a stale premise.

### Minimal-change checks

The [four tests](#minimal-change) run as property tests over random operation sequences
on synthetic repositories. They are not runtime checks. The gate enforces only
citation carry-over, the `edit_article` text guards and scope consistency, which are
cheap structural rules.

## Delivered knowledge: `delivered-knowledge/3`

The top level has exactly `schema`, `version`, `commit`, `repository_id`, `coverage`,
`articles`, `facts` and `history`. The empty file has empty lists, an empty history and
`null` identity, as today.

```json
{"replaced": {"old-fact-id": {"reason": "restated", "by": ["new-fact-id"]}},
 "ended": ["ended-fact-id", "retired-slug"], "retracted": ["wrong-fact-id"]}
```

`reason` is `restated`, `narrowed` or `corrected`, composed as the
[public identifier rule](#public-identifiers) says. A corrected record appears in
`replaced` and not also in `retracted`. `ended` and `retracted` name fact IDs and the
slugs of retired articles, never revision IDs. Each list follows the public identifier
rule. A player holding an ID from an earlier version learns what replaced it, or that it
was withdrawn. This answers the policy-adaptation gap with a pointer, not with silence.

**Article** (`id` is the slug):

```json
{"id": "water-treatment", "revision": "water-treatment@v12",
 "title": "Water treatment", "lead": "…",
 "body": [{"text": "…", "facts": ["boiling-makes-water-safe"]}],
 "tags": ["water"], "scope": {"game": "example"}, "branch_relation": null,
 "lifecycle_state": "active", "needs_review": false, "stale_citations": [],
 "condition_unverified": true, "unverified_branch": false,
 "links": [{"rel": "depends_on", "target": "fire-starting"}],
 "backlinks": [{"rel": "see_also", "source": "camp-setup"}],
 "shadowed_by": [], "contradicted_by": [],
 "last_confirmed": {"session": "s03", "actor": "…", "step": 41, "order": [3, "001", 41]}}
```

**Fact**: the fields in the [delivered fact column](#record-fields). `citation_source_ids`
is the stored `citations` under a name that says what a player can do with it: pass it to
`player_source` where that tool can reach the frame. This design does not change the
tool's reach. The IDs embed opaque session IDs, a stated
[limit on blinding](#operator-blinding).

Both readers, `harness/player/knowledge.py` and `tools/player_host/knowledge.mjs`,
accept exactly these closed forms and refuse any other. Parity comes from one shared
fixture directory of valid and invalid files that both test suites load. The Node host
adds no dependency.

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
| `revision` | `<slug>@<version>` of a delivered slug, where that ID is the delivered revision or an earlier revision in `H` | The delivered article | The revision asked |
| `restated`, `narrowed`, `corrected` | A key of `history.replaced` | Its `by` records, in order | The old ID |
| `ended` | A fact ID or retired slug in `history.ended` | Empty | The ID |
| `retracted` | A fact ID or retired slug in `history.retracted` | Empty | The ID |
| `title` | Exact title of a delivered article (skipped when `by: "id"` is set) | That article | `null` |
| `unknown` | Anything else, including an excluded revision, a withheld end (`by: "id"`) and an invisible branch end | Empty | `null` |

Rows are tried in table order, so an ID or slug wins over a title that happens to equal
it. `Knowledge.read` and `player_knowledge_read` accept an optional `by` parameter
(`"any"` by default; `"id"` skips the `title` fallback so identifier resolution never
collides with an unrelated article's title, including under withholding). A query result
carries the same top-level fields, with `resolution` `query` and the ranked records. The
records inside a read or query result are the closed delivered forms. `resolved_from`
sits on the result, not on a record. `unknown` supplies no evidence that a state ended;
for a precondition, the player re-observes.

### Status markers in every projection

A record that is not plainly `active` says so wherever the player sees it. Its
`status` is the list, in this order, of whichever of `contested`, `unverified_branch`,
`needs_review` and `condition_unverified` hold in the target view. One projection
function in `tools/player_host/knowledge.mjs` adds `status` to a projected entry only
when the list is non-empty. So the bytes of plainly `active` entries stay stable for the
provider cache ([request stability](../contracts/player-host.md#request-stability-and-tail-notices)).
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
6. If the benchmark keeps the coverage skip, walk that order, skip a fact that a record
   already in the result cites, and stop at 10 records. This is the rank-order skip
   described in [coverage versus redundancy](#coverage-versus-redundancy), not a
   marginal-gain selection. Otherwise take the first 10.

Contradicting records stay in the graph on purpose: a query should surface both sides.
The constants are the ablation's and are not tuned. The [gates](#offline-verification-gates)
measure them on the migrated code. Personalized PageRank with teleporting dangling nodes
is the tested upgrade if a store outgrows one hop.

## Reuse review: validation, search and storage

`S-CODE` asks whether a maintained capability fits before custom code grows. Three
capabilities were reviewed against maintained 2025–2026 options.

### Submission validation: `jsonschema`

`jsonschema==4.26.0` is already pinned in `requirements.in` and already used by
`harness/player/contracts.py`, `tools/run_ledger.py` and `tools/evaluate.py`, so using it
in the gate adds no dependency. The sandbox gets the same pinned package through
`WORKBENCH_DEPENDENCIES` ([staging](#validation-before-close-out)) rather than by
sharing another package's install directory.

- **Adopt** `Draft202012Validator` in `harness/curator/check.py`, which the gate calls,
  with two new schemas, `schemas/curator-submission.schema.json` and
  `schemas/curator-fact.schema.json`. They carry the closed shapes of every operation
  and record: required and forbidden keys, enumerations, ID and axis patterns, list
  sizes and the eight-axis limit. A review count found about 170 non-blank lines of
  submission-shape checks in `gate.py` today. About 53 of them are type-only checks that
  owner decision 1 retires anyway. The stored-record shape checks are mixed with
  cross-record rules in `_validate_snapshot`, so only their shape part moves into the
  record schema. The gain is one declarative shape per operation, not a large line
  saving.
- **Keep in Python** every rule that needs more than one record: references, the scope
  order and declared axes, citation carry-over and end-frame novelty, the `old_text`
  guards, lifecycle derivation, the fixed point and the identifier rules.
- **Keep Node lightweight.** `tools/player_host/knowledge.mjs` keeps hand-written closed
  checks of the delivered forms, and the shared fixture directory proves parity. The
  `validate_submission` tool runs the same schemas and `check.py` as the gate.

### Patterns borrowed and libraries rejected

Borrowed as ideas, with no dependency:

- **RFC 7396 merge patch** for `revise_article`'s inherited fields.
- **W3C PROV-DM** for the entity, activity and derivation reading of citations,
  revisions and `supersedes`.
- **DBSP-style fixed points** for the review flags, as a full recomputation.
- **The `llm-wiki` pattern** (Karpathy) of a curated article layer over cited notes.

Rejected:

- `jsonpatch` (RFC 6902): its array-index pointers are brittle for claim edits, which
  `edit_article`'s `old_text` guard handles.
- `pydantic` and `msgspec`: a second validation model beside the already pinned
  `jsonschema`.
- `bm25s`: no gain over the tested pure-Python scorer at this size.
- `networkx` and `rustworkx`: one-hop expansion and the fixed point are dict adjacency.
- `pyoxigraph`, `duckdb`, `Dolt` and `TerminusDB`: a second store beside the Git-tagged
  repository, which stays the single writer.
- `Kuzu`, archived in October 2025, and its successor `LadybugDB`, plus `FalkorDBLite`:
  young embedded graph stores with maturity risk.
- `sqlite-vec` and `Memvid`: no measured need for embeddings.
- Memory frameworks with a model in the loop: `Graphiti`/Zep, `Mem0`, `Letta`,
  `Cognee`, `Hindsight` and `Honcho`. Each brings its own service, store or extraction
  pipeline, mostly behind a model call. The gate's contract rules all of them out: it
  executes nothing and calls no model, it is the single Git-tagged writer, and the
  curator's sandbox has a closed workspace. They would also put game semantics into a
  dependency's schema (`P-GENERALITY`). The bi-temporal split is the useful idea from
  this family, and it is taken here as two kinds of time.

### Search engine and storage

The nearest fit is the standard library's SQLite with its FTS5 extension, with relational
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
| Scoring | FTS5's `bm25()` normalizes by total document length, and its IDF differs from the current `ln(1 + …)` form for common terms. Rankings may differ in an unknown direction | The current formula, already tested |
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

## Provenance bridge to the belief comparison (#677)

`curator-knowledge/4` stores **no** probability, confidence, weight or opinion tuple, as
the [no-belief-value decision](../decisions/owner-decisions.md#no-belief-value-in-the-fact-store)
requires. Every numerical view is computed at offline replay time and never written back.
The [belief-method comparison](belief-method-comparison.md) replays cases in the
`belief-replay-fixture/1` form that
[`belief_replay.py`](../../tools/recurrence_research/belief_replay.py) reads. Each
observation there has a `source_id` and reports with `origin`, `event` and `polarity`. A
case has `applicable_events`, optional `required_support`, a `dependence_group`, and
checkpoints with `withdrawn_origins`. Today's replay reads a frozen exposure prefix,
event polarities and explicit withdrawals; it reads no lifecycle value, so this
migration breaks no current replay. The table says what this store supplies for each
input, and what still comes from #677's frozen extraction set.

| Replay input | From the store | From #677's frozen extraction |
| --- | --- | --- |
| Proposition and scope | One fact is one proposition at one scope: `id`, `text`, `scope`, `when` | The question wording |
| Observation `source_id`, `exposure`, `detail` | Frame citations supply frame `source_id`s | Ordered `exposure`, observation `detail` and any non-frame stand-in observation (as in `belief-replay-cases.json`) |
| Report `origin` across merges | Each citation's frame, with session and actor from `provenance.frames`. Carry-over is a set union, so one frame cited by two merged facts is one origin. Earlier revisions keep each original citation set | — |
| `event` and `polarity` | Not stored | Yes |
| Independent alternatives or `required_support` | An `inferred` fact jointly requires its `depends_on` premises. Nothing says whether one fact's several citations are alternatives or jointly required | Yes, per case: the `required_support` list |
| Refutation | Citations of a `wrong` retirement and those a `corrected` replacement adds; citations of a record in a classified `contradicts` conflict | Polarity of each |
| Local exception | A `contradicts` link at a comparable, unequal scope is shadowing. Inside the specific scope the general proposition is not asserted, so it is not refuted at its own scope | — |
| `corrected` replacements | Different propositions joined by `supersedes`, the old one `retracted`. Its text and citations stay in `facts.jsonl`, so a prefix replay sees the old claim | Whether the replacement negates the old claim |
| Withdrawal (`withdrawn_origins`) | The version that retracted a record whose citations are the origin. An `ended` state never withdraws its supporting frames, which stay valid history | Which origins a checkpoint withdraws |
| `ended` retirement | Observed end: `exact` at `valid_to` for `transition`, interval `(seen, valid_to]` for `absence`, unbounded when `valid_to` is `null`. Not refutation and not error | — |
| Never retired | Right-censored at `seen` | Any persistence assumption |
| Dependence | Shared sessions, actors and windows, `depends_on` for inferences, and `lineages` | `dependence_group` |
| Checkpoints and `through` | `published_in` order of revisions and transitions; prefix replay sees only what was published by then | Checkpoint choice and checkpoint `through` cut |
| Prior weight `W`, base rate `a`, opinions and Beta views | Never stored | Replay parameters and formulas |

**What the mapping establishes.** The store keeps what a replay needs to *locate* the
evidence for a proposition:

- citation sets with origin positions;
- immutable revisions;
- supersession and contradiction edges with a computable scope relation;
- retirement reasons and observed end bounds;
- publication order.

It does not establish polarity, event identity, the conjunctive structure within one
fact's citations, or which events apply. Those stay in #677's frozen extraction set. A
future adapter must not treat a restatement as an observed end, which would invent an
event, nor withdraw a supporting frame because its state later ended. So "no later
schema change" holds only for the located inputs in the store column, not for every
replay quantity. A *production* belief value would still be a second, separately
justified migration. The comparison note's warning also stands: different frames may
share an error cause.

## What the retired type rulings become

Owner decision 1 retires the type format. Five standing rulings depend on it, and each
gets an explicit replacement so that nothing is dropped silently:

| Ruling today | Source | After this migration |
| --- | --- | --- |
| Types are proposed by the player system and checked against existing types | [Decision](../decisions/owner-decisions-archive.md#player-system-proposes-and-explains-types); curator contract `add_type` | The curator proposes tags. The brief lists existing tags with counts over facts and articles, and near pairs. `claim_kind` is fixed and needs no proposal |
| Types are explained to every reader | Same decision | The five `claim_kind` values are defined once in the curator instructions and the [player guide](../player-guide.md). A tag carries no definition; it is seen with its usage count. **This is the ruling the owner revisits** |
| Types earn their place or go; an unused type is flagged | [Decision](../decisions/owner-decisions-archive.md#types-earn-their-place); the type list in the brief | A tag exists only while a current record uses it, so a tag with no use leaves the list and needs no "unused" flag |
| Grooming re-types with `revise_types`, at most once per submission, recorded in `retyped` | Curator contract | `retag`, grooming only, at most once per submission, recorded in `retagged` |
| Near pairs use the words of a type's name and field names | Curator contract, the type list | Near pairs use the words of the tag alone. The 1/3 shared-word rule and the size limits are unchanged, now in [`type_usage.py`](../../harness/curator/type_usage.py)'s successor |

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
| Clickable fact citations to frames | `citation_source_ids`, resolved by the [citation anchor rule](#operator-blinding). A frame of this run resolves; another admission's frame has `null`, as for positions today |
| `ontology/types.json` view | Retired with the file. Replaced by a tag and `claim_kind` view counted from the delivered records |
| Curator draft and gate views | Not provided. Drafts and gate results live in the curator repository and session records, which the [spectator contract](../contracts/spectator-view.md) bars the knowledge route from reading. #464 picks its own source |

The #464 description needs the `ontology/types.json` line replaced with the tag and
`claim_kind` view when this migration is accepted.

## Migration inventory

This follows [S-MIGRATION](../standards/migration.md): one coordinated change, no
compatibility reader, and unsupported versions refused. The paths were checked against
the tree at `41006bd7`, and the additions below against `e652ef83`.

### Formats

| Old | New | Note |
| --- | --- | --- |
| `curator-knowledge/3` | `curator-knowledge/4` | A fresh repository; older ones are kept as sealed evidence |
| `curator-fact/4` | `curator-fact/5` | Facts and articles |
| `curator-type/2` | Removed | With `ontology/types.json` |
| `curator-submission/1` | `curator-submission/2` | The operations above, with JSON Schemas |
| `curator-boundary-grooming/1` | `curator-boundary-grooming/2` | Adds `stale_records` and the two failure reasons |
| `delivered-knowledge/2` | `delivered-knowledge/3` | Also the private `knowledge-full.json` and its `selection` keys ([blinding](#operator-blinding)) |
| `player-knowledge/1` | `player-knowledge/2` | Read and query results |
| `campaign-run/12` | `campaign-run/13` | Unconditional. Adds the required top-level `context` map, `{}` by default. The evaluation archive keeps reading `/12` ([why the bump](#why-campaign-run-changes)) |
| `spectator-view/2` | `spectator-view/3` | One API schema for every route. Knowledge facts gain scope, flags, links, tags and kinds; the `scope` filter uses delivered scope classes |
| `knowledge-units/1`, `knowledge-units/2` | Unchanged | Same shapes. Units are built over `E`, and the article unit names the slug |
| `withholding-study-draw/2` | Unchanged under 4(a) | Lineage excludes nothing under 4(a). Under 4(b) it gains `lineage` and becomes `/3`, with `campaign-run/14` |
| `curator-gate/2`, `curator-coverage/2`, `knowledge-update-entry/1`, `coverage-update-entry/1`, `player-host-inputs/4` | Unchanged | Their shapes are the same; readers that expect the delivered schema change with it |
| Telemetry `delivered_knowledge_schema` | Unchanged field | Records the new value |

#### Why `campaign-run` changes

Sealed `#889` packages are indexed in `data/evaluation/archive-sessions.json` as
`campaign-run/12` with `delivered-knowledge/2`. Two readers choose the delivered schema
from whether a manifest equals `MANIFEST_SCHEMA`: `harness/viewer/knowledge.py`
(`CURRENT_SNAPSHOT`) and `tools/memory_measure.py` (lines 646 and 650, which also compare
`selection` exactly). If new packages kept `campaign-run/12`, those readers could not
tell a sealed package from a new one. The bump makes the distinction by manifest, and it
carries `context`. Under owner decision 6, `/12` delivered knowledge is then read from
the earlier source.

**The `context` field.** `context` is a required top-level manifest field, not a key
under `labels`. `tools/campaign_package.py` writes `{}` when a package declares none, and
adds `context` to `FIELDS`, so `closed(profile, FIELDS)` (line 145) still closes the
manifest. It holds 0 to 8 keys. Each key matches `[a-z][a-z0-9_]{0,31}` and is neither
`game` nor `world`. Each value is 1 to 64 printable ASCII characters. Only run-wide
invariants belong in it ([the scope map](#the-scope-map)).

**The closed archive stays readable.** `#889`'s sealed `campaign-run/12` sessions are in
`data/evaluation/archive-sessions.json`, and the evaluation reads their manifests,
journals and handoffs, which hold no delivered knowledge. Moving `MANIFEST_SCHEMA` to
`/13` would silently drop them, so the slice names `/12` explicitly:

- `JOURNAL_MANIFEST_SCHEMAS` (`harness/evaluation/core/sources.py` line 31) keeps
  `'campaign-run/12'` beside the new `MANIFEST_SCHEMA`.
- The `#889` row of `ARCHIVE_COMBINATIONS` (`sources.py` lines 127 to 131) stays and adds
  `'manifest'` alongside `'host'` in its differing `fields`, matching
  `tests/test_evaluation_core.py` lines 1675 to 1677.
- `harness/evaluation/core/facts.py` (lines 30 to 31 and 48 to 49) treats `/12` as it
  does today, so `#889`'s world labels and `max_http_attempts` handling are unchanged.
- `harness/viewer/knowledge.py` (lines 17 to 18 and 148) gives a `/12` run an explicit
  `snapshot_status: hash_unavailable`. It never falls through to `ARCHIVED_SNAPSHOT`,
  which would misread a `/12` run as `delivered-knowledge/1`.

### Code

| Area | Paths |
| --- | --- |
| Repository and gate | `harness/curator/knowledge.py`, `gate.py` (new operations, working articles, end, axis and scope rules, the `(owner, stale_target)` check, narrowing exemption in `_publication()`) |
| Validation | New `harness/curator/check.py` (pure stages, JSON Schema) and `harness/curator/validate.py` (its command line) |
| Session | `harness/curator/session.py`: `current-facts.jsonl`, brief worklist and axes, workbench staging, `WORKBENCH_DEPENDENCIES`, `validation-context.json`, `provider-error` close-out |
| Runner and window | `harness/curator/runner.py` (`Outcome.provider_error`, `classify()` for `provider-error`); `harness/curator/window.py` lines 171 to 175 (`session_labels` keeps `context`) |
| Tag counts | `harness/curator/type_usage.py` lines 32 to 36 and `session.py` line 180: counts over facts and articles |
| Schemas | New `schemas/curator-submission.schema.json` and `schemas/curator-fact.schema.json` |
| Curator host | `tools/curator_host/workspace-tools.mjs` (`validate_submission`, atomic `write_file`), `host.mjs` (tool set, `provider-error` result), `run.mjs` (its exit code) |
| Curator instructions and grooming | `tools/curator_host/prompt.md`, `grooming.md` (filing rule, worklist), `groom.py` (close-out rule, `provider-error` reason) |
| Export and selection | `tools/knowledge_export.py` lines 32 to 69 (`units()`, `draw()`, `filter_delivery()`), `study_record()`, `export()`, selection, history and aliases |
| Export command line | `tools/knowledge_export.py` lines 241 to 279: `--lineage` and `--context` beside `--world` |
| Live exports | `tools/curator_host/live_runner.py` lines 214 to 235 (`Outcome.provider_error`), 244 to 268 (`delivery_world()`) and 281 to 315 (delivered-version writer): forward `world`, `lineage` and `context` |
| Package manifest | `harness/evaluation/core/sources.py` (`MANIFEST_SCHEMA`, lines 31 and 127 to 131), `facts.py` lines 30 to 31 and 48 to 49, `harness/trace/projection.py` (labels with `context`) |
| Package builder | `tools/campaign_package.py`: `context` in `FIELDS`; the live-updates guard (line 187) refuses `knowledge-units/2`, a `draw_sha256` or `seed is not None` |
| Player application | `harness/player/knowledge.py`, `harness/application.py`, `harness/player_view.py`, `harness/player_tools.py` lines 24 and 25 (the read and query tools' descriptions) |
| Player host | `tools/player_host/knowledge.mjs` (closed forms, the shared projection with `status`, `updateDelivery`'s face), `tools/player_host/README.md`, `tools/campaign_player.py` (adoption check) |
| Measurement | `tools/memory_measure.py` (lines 646 and 650, unit layouts over the new full export), `tools/memory_screen_checks.py`, `tools/run_ledger.py` (uses `Knowledge`, API unchanged) |
| Spectator view, server | `harness/viewer/__init__.py`, `app.py`, `catalog.py`, `views.py` (`spectator-view/3`) and `telemetry.py` |
| Spectator knowledge | `harness/viewer/delivered.py` (scope; citation anchors, lines 108 to 115), `knowledge.py` (`CURRENT_SNAPSHOT`, `/12` as `hash_unavailable`; `entry()` reads `type` at line 77, `source_ids` at 81) |
| Spectator view, browser | `web/app/data.js` (`viewerGet`'s default schema), `web/app/memory.js`, `web/app/records.js` |
| Campaign watch | `tools/campaign_watch.py` (reads `spectator-view/2`) |
| Text only | `tools/recurrence_research/trial.py` names the old delivered schema in a status string |

Every other reader of `MANIFEST_SCHEMA` or a literal `campaign-run/12` moves to `/13` in
the same change, except the closed-archive readers named
[above](#why-campaign-run-changes); the slice lists them with a repository search.

### Tests and fixtures

- **Curator:** `tests/curator_stand_in.py`, `tests/live_curator_stand_in_run.py`,
  `tests/test_curator_gate.py`, `test_curator_session.py`, `test_curator_host.py`,
  `test_curator_runner.py` (`runner.py` and `provider-error` cases: single no-publish
  retry without halving, single publish advance, unexpected-reject non-advance, and two
  consecutive `provider-error` sessions tripping `SESSION_FAILURES = 2`; owned solely by
  the repository-and-gate slice), new `tests/test_curator_groom.py` (grooming summary
  and `provider-error` grooming reasons, owned by the curator-host slice), new
  `tests/test_live_runner_export.py` (delivery context and `Outcome.provider_error`
  forwarding, owned by the export-and-selection slice), `test_curator_type_usage.py`,
  `test_evaluation_memory_screen_checks.py`, and the curator host's
  `tools/curator_host/test/host.test.mjs` (its scripted `curator-submission/1`,
  `validate_submission` past 80% of the budget, and the `provider-error` result).
  Integration updates the existing shared `live_runner` and `groom` cases in
  `tests/test_curator_runner.py` (line 812 and lines 1172 to 1221).
- **Closed archive:** `test_evaluation_core.py` keeps an `#889` `campaign-run/12` case
  that still reads, and `test_viewer_api.py` a `/12` run that reports
  `hash_unavailable`.
- **Delivery and measurement:** `tests/test_knowledge_export.py`,
  `test_evaluation_delivery.py`, `test_campaign_run.py`, `test_campaign_player.py`,
  `test_player_host_contract.py`, `test_player_knowledge_query.py`,
  `test_process_measures.py`, `test_memory_measure.py`,
  `test_memory_measure_study.py`, `test_memory_measure_withholding.py` and
  `test_run_ledger.py`.
- **Manifest readers:** every test that names `campaign-run/12`, including
  `tests/curator_trace.py`, `test_evaluation_core.py`, `test_host_analysis.py`,
  `test_recurrence_research_prepare.py` and `test_viewer_frame.py`.
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

- **Curator contract:** `docs/contracts/curator.md`. Its reader table must gain
  `harness/player`, the viewer and `tools/campaign_package.py`. It also states the
  `provider-error` close-out and runner rule, `validate_submission`, and one revision
  per slug per submission, which replaces its one-change-per-target rule.
- **Other contracts:** `player-host.md` (lines 181 to 215, 277 to 278 and 291:
  `delivered-knowledge/2`, `campaign-run/12` and `selection`), `measurement-tools.md`,
  `withholding-study.md`, `player-host-telemetry.md`, `evaluation-record.md`,
  `run-ledger.md` (lines 18 and 21, the accepted `campaign-run/12` manifest) and
  `computer-control.md` (line 213, `#spectator-view-api-spectator-view2` fragment).
- **Spectator contract:** `spectator-view.md`: lines 55, 57, 356 and 478
  (`spectator-view/2` → `/3`), line 142 (the grooming receipt link), line 202 (readable
  delivered schema), lines 211 to 219 (scope fields and the anchor rule), and lines 310
  to 314 (snapshot schemas, `/12` as `hash_unavailable`).
- **Components and operations:** `docs/components/curator.md` (lines 12, 35, 191 and
  214: schema references, grooming summary and runner-failure rule),
  `docs/components/player-interface.md`, `docs/components/spectator.md` (line 52,
  `spectator-view/2` fragment), `docs/operations/migration.md`,
  `docs/operations/campaign-run.md` (`context` and its run-wide rule),
  `docs/operations/campaign-supervision.md` (line 76, the fresh `campaign-run/12`
  package), `docs/operations/player-host.md` (line 59, `campaign-run/12`),
  `docs/operations/start-observe.md` (line 43, `spectator-view/2` fragment) and
  `docs/operations/curator-hosts.md` (reading `grooming-summary.json`).
- **Overview, protocol and proposed design links:** `docs/overview.md`,
  `docs/architecture.md` (line 60, curator scope wording; line 205, `spectator-view/2`
  fragment), `docs/protocol.md` (line 27, `types` prose), `docs/documentation.md`
  (line 92, `spectator-view/2` fragment), `docs/glossary.md`, `docs/player-guide.md`
  (query and read results, status markers, `claim_kind`) and
  `docs/design/programs-and-monitor.md` (line 13, `#facts-curator-fact4` →
  `#facts-curator-fact5`, required by `tools/check.py` because that note is `proposed`).
- **Owner decision log:** the rows that owner decisions 1 to 9 add.
- **This note** becomes `historical`, with its replacement set to the curator contract.

### Left as evidence

`docs/design/world-scoped-memory.md`, `docs/design/curator-session.md`, ADR 009, dated
records, `data/evidence/index.json`
and `data/evaluation/coding-agent-attempts.jsonl` keep their wording. The sealed
repositories and delivered files under `.runtime/evidence/` are not converted.

## Migration plan

The Project calls this "Wave 3". It lands as **one** merge, because no slice works with
the others' old formats. The slices below have disjoint file ownership so that workers
can build them in parallel worktrees. The lead integrates them and owns the shared
runtime.

| Slice | Owner | Files | Done when |
| --- | --- | --- | --- |
| Shared shapes | Lead, first | The shared `delivered-knowledge/3` fixture directory, the two curator JSON Schemas, and the synthetic two-world, two-lineage repository builder | Fixtures and schemas reviewed; every other slice builds on them |
| Benchmark and recount | Worker, first | A rerunnable benchmark script (30 #924 queries, labelled direct-answer subset), a read-only `#896-b` recount script, and one dated acceptance record | Evidence gate 11 passes (`#936`): the record holds #920's baseline, paired skip comparison and recount before implementing decision 7 (`#937`) |
| Repository and gate | Worker | `harness/curator/` (`knowledge`, `gate`, `check`, `validate`, `session`, `runner`, `window`, `type_usage`), `test_curator_runner.py`, other curator tests, `memory_screen_checks` | Gate tests cover every operation, working articles, axis, scope, end, identifier, carry-over and `(owner, stale_target)` rules, the fixed point, `provider-error` close-out, and refusal of `curator-knowledge/3` |
| Curator host | Worker | `tools/curator_host/` `workspace-tools.mjs`, `host.mjs`, `run.mjs`, `prompt.md`, `grooming.md`, `groom.py`, `host.test.mjs`, new `test_curator_groom.py` | `validate_submission` runs past 80% of the budget; `provider-error` is reported distinctly; submissions are written atomically; grooming reasons pass |
| Export and selection | Worker | `knowledge_export`, `live_runner` (delivery context, `Outcome.provider_error`), `campaign_package`, `projection.py`, `sources.py`, `facts.py`, manifest readers, `memory_measure`, new `test_live_runner_export.py` | Public-set, alias and blinding tests pass for initial files and live updates, with fork, nested-cut, restore and withheld-dependency cases; `#889`'s `/12` archive still reads |
| Player reads and ranking | Worker | `harness/player/knowledge.py`, `application.py`, `player_view.py`, `player_tools.py`, the query test, `docs/player-guide.md` | Shared fixtures agree; the ranking gate passes |
| Player host | Worker | `knowledge.mjs`, its tests, README, `campaign_player.py` and its tests | Shared fixtures agree. Serialization tests show stable bytes for `active` entries, and status markers on every projection |
| Spectator view | Worker | Viewer Python, `web/app` files, `campaign_watch.py`, viewer and watch tests and fixtures | Viewer tests show scope, flags, links, tags, kinds and citation anchors under `spectator-view/3`, with no label; a `/12` run is `hash_unavailable` |
| Contracts and integration | Lead | Every current document listed, shared `test_curator_runner.py:812,1172-1221`, plus integration | Full regression, review and the protected CI profile pass |

### Offline verification gates

All of these gates cost `$0` and need no game launch:

1. **Reader parity.** Python and Node accept and refuse exactly the same shared
   fixtures.
2. **No leak.** No delivered identifier leaves `P ∪ H`, and no delivered byte contains a
   raw world or lineage label, in an initial file or a live update, coverage stamps
   included. The byte scan runs on a synthetic fixture whose session names embed those
   labels, as sealed runs do, so it proves the alias layer works. The steps run in the
   [enforcement order](#the-enforcement-order).
3. **Article eligibility.** No delivered article cites a fact that is not delivered.
4. **Default preserved.** A store holding only unbound and world-bound records exports
   the same eligible set as today's rule.
5. **Fixed point.** The flags are the same after a recomputation, after shuffling the
   input order, and on `depends_on` cycles. This holds in both views. A public record
   whose only dependency was withheld shows `needs_review: false`.
6. **Minimal change.** The property tests in [minimal-change checks](#minimal-change-checks)
   pass.
7. **Lifecycle and timelines.** Every stored `superseded` record has a non-empty
   `superseded_by`; no `ended` fact lacks valid `end_citations` (on a surviving segment
   for a world-bound fact); a retracted pre-fork record, or one whose faithful
   restatement (including a faithful merge) or applicable narrowed child was later
   retracted, is never delivered `inherited`; an end on an unknown branch reads
   `unknown` and is not in `H`. The
   [nested-cut and restore histories](#lineages-forks-and-restores) give their stated
   outputs (including post-restore end superseding the saved view).
8. **Validation parity.** `validate_submission` and the gate give the same diagnostics
   on the gate test corpus, including a structurally valid stale-base submission,
   sequential multi-submission repairs in one session, and post-restore session
   reservations. On a `provider-error` stop, close-out gates the longest validated
   prefix whose exact bytes match a passing call.
9. **Ranking.** The 30 #924 queries are replayed on test-only projections of the
   sealed `v91` and `v17` files into the new form. The projection takes the slug from
   the old ID and resolves links by title. It lives in the test and is never a runtime
   reader.
   - **Overall ranking, against #920's flat BM25** in the benchmark record: Hit@5 and
     article MRR@5 at least the baseline's on both corpora, and a 95th-percentile query
     time under 5 ms.
   - **Coverage skip, paired.** `bm25_1hop` with the skip is compared with the
     identical `bm25_1hop` with the skip disabled, on the labelled direct-answer subset:
     queries whose gold answer is a fact detail that the citing article's prose omits.
     The subset is non-empty and holds at least one query where the skip actually
     suppresses a direct-answer candidate. The skip is kept only if it raises distinct
     records reached in the top 10, lowers neither direct-answer fact Recall@5 nor fact
     MRR@5, and adds no `player_knowledge_read` calls needed to reach the answer.
     Article MRR@5 and Recall@5 are not used for this decision, because the skip cannot
     lower them.
10. **Cut and cache.** Existing context-cut and request-serialization tests pass, the
    cut payload stays within 24,000 characters, and a flag-only change produces an
    `updated` entry.
11. **Evidence record.** The benchmark-and-recount slice's dated acceptance record exists
    before decision 7's curator changes are implemented (`#937`). It holds #920's
    measured baseline on both corpora,
    the paired skip comparison, and the `#896-b` curator-behaviour recount from
    `.runtime/evidence/seven-day-896-b-admission-10/knowledge/`, each with the command
    that produced it.

Full regression runs before merge, because this is a broad source change.

### Model check criteria

One `C-MODEL-CHECK`, capped at `$1`, covers the changed curator instructions. The fixed
small window is chosen from sealed `#896-b` admissions so that a restatement and an
article edit arise naturally from its frames; a window that needs neither would test the
instructions only by prompting. Sample replies must produce a `curator-submission/2` that
passes the gate's well-formed, `base_version` and candidate stages, with valid core
fields and declared scope, and must include at least one `edit_article` or
`remap_citations`. A failure is fixed in the
instructions, never by loosening the gate. The recall prompt is unchanged apart from the
status markers, which the recorded-player tests cover. A paid live admission on the new
store is a separate, priced approval.

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
| Keep four lifecycle states, with `ended` inside `superseded` | A stored `superseded` row without a successor reads as a broken redirect; the fifth state costs nothing during this migration |
| Exclude everything from another lineage | Throws away world state that is still valid in a shared world; a flagged delivery is more honest |
| Mark unknown-fork records `contested` | Fabricates a contradiction from missing timeline evidence; `unverified_branch` says what is known |
| Deliver unknown-axis records flagged, like an unknown `when` | Promotes a claim whose run-wide prerequisite is unconfirmed into briefings and search; decision 5 |
| Accept undeclared curator axes and let exports drop them | Silently retires knowledge, worst for games without a CDDA-like world; the gate refuses instead |
| Trim an article's claims to its eligible facts | Changes what a claim says without the curator; the article is excluded instead |
| Keep atomic repair (no stale citations) | Safe, but a live admission must rewrite every article citing a superseded fact; shared facts are common (`shared` in `knowledge-units`); decision 2 |
| Require each grooming candidate to be free of stale citations | Makes repair atomic again within grooming; the rule applies at close-out |
| Make the curator copy old citations into a restatement | About half of sealed restatements would fail it; code takes the union instead |
| Let the gate remap citations automatically | Publishes revisions no session wrote, and is wrong for `corrected` and `narrowed`; `remap_citations` keeps the choice with the curator |
| JSON Patch (RFC 6902) for article edits | Array-index pointers drift silently; `edit_article` guards each index with exact text |
| An entity-relation triple graph, or PageRank by default | Research counter-evidence under incomplete knowledge; PageRank only tied 1-hop in #924 |
| Coverage-aware cut briefing now | No sealed record shows the cut budget binding on articles |

## What is not known

- **Whether the ranking gains hold.** The #924 queries and gold labels were written
  together by the study. Its two live player queries came from `A01 v3` and `A03 v38`
  and were replayed retrospectively on `v91`. All are in-sample, and so will be the
  direct-answer subset. The fix is a held-out query set drawn from future live
  `player_knowledge_query` calls.
- **The size of the gain over today's ranking.** #920's field-weighted BM25 was not in
  the #924 ablation. The Wave 3 benchmark record measures it first.
- **Whether flags change behaviour.** It is unknown whether `needs_review`,
  `contested`, `unverified_branch`, `condition_unverified` or a `history` redirect
  changes what the player plans. Measuring that belongs with the
  [judged measures](../contracts/measurement-tools.md#adjudication-and-the-standing-use-measures),
  not this migration.
- **Whether curators pick kinds consistently.** No inter-session agreement check exists
  yet, so it is unknown whether two curator sessions assign the same `claim_kind` to the
  same claim. At least 20 of the 307 `#896-b` game facts describe one moment in one
  world, so the `instance_state` boundary will decide much of what transfers.
- **Whether the curator uses the new operations well.** No model has produced a
  `curator-submission/2`. The model check samples it once; a filed `restated` that
  reverses a claim passes the gate.
- **Whether the new tools keep grooming within budget.** `#896-b`'s groomings failed on
  spend-reservation refusals after very large re-reads, which #918 fixed. The worklist,
  surgical edits, `validate_submission` and abort-safe close-out are designed to shrink
  those re-reads and keep a validated repair. Neither the fix nor the tools have been
  measured on a grooming.
- **Reloads inside a lineage.** Without operator restore labels, the store cannot see a
  reload within one lineage. It may deliver a record the reload undid as `same`. A
  negative `lineage.continuity` gap or a lowered `lineage.elapsed` in a studied lineage
  is the trigger for decision 4(b).
- **How much decision 5 excludes.** `excluded_unknown_axis` in `selection` will show
  whether target packages declare fewer axes than the store's declared union.
- **Curator-authored labels.** Session aliases close the operator-label channel in
  positions. A label the curator copies into prose, a tag, an ID or a `when` note is not
  detected.
- **When the cut briefing needs coverage selection.** Revisit it when a store passes 64
  articles or 20,000 characters of leads. Revisit it also if a replay shows that the
  cut's recency rule drops a gold article that a query needed.
