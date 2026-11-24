---
owner: lead
status: historical
date: '2026-11-24'
scope: Open-horizon primary-source research on game-neutral epistemic meta-ontologies, hierarchical scope maps, bi-temporal rollback invalidation, wiki/graph memory retrieval, and competing 2025-2026 paradigms for curator memory; settled by the 24 November 2026 owner approval of the Wave 3 design
replacement: docs/design/knowledge-graph-scoping-contract.md
---

# Research note: game-neutral meta-ontology, scoped cross-referencing, and wiki/graph retrieval

The literature search cutoff is **2026-11-23** (`America/New_York`). Every arXiv paper
below was verified directly against its primary arXiv record (`arxiv.org/abs/<id>`), and
every quantitative result from a paper was taken from the paper's primary HTML or abstract
text rather than search snippets; the BFO/DOLCE ISO standards row is explicitly marked as
secondary background where the paywalled ISO texts were not read directly. This page builds
on, and does not repeat, [memory, ontology and oversight](research-curated-memory.md) (cutoff
`2026-11-08`) and [belief under conflicting observations](research-belief-under-conflict.md).

The design proposal built on this note is [scoped, traceable knowledge](design/knowledge-graph-scoping-contract.md).

## Search method and open-horizon discovery

Following `P-GENERALITY` and the project's research discipline, this review did not limit
itself to confirming pre-selected graph-RAG or wiki-memory ideas. We ran open-horizon
searches across 2025–2026 agent-memory, upper-ontology, temporal-database,
continual-learning, world-model, and negative-ablation literature to surface **directions
outside prior project assumptions** and **evidence against heavy knowledge graphs**.

Five findings from outside our initial framing materially shaped the recommendations for
[#925](https://github.com/CVX-Hull/enactive/issues/925):

1. **The Implicit Policy Adaptation (IPA) gap (`STALE`, May 2026; `StateAuditor`, Aug 2026):**
   Updating or superseding a stored fact does not guarantee that an agent stops planning
   around stale derived beliefs. Even when updated evidence is visible in context, plans
   frequently anchor on old premises; write-side staleness marking is an important warning
   signal, not a sufficient behavioral guarantee by itself.
2. **Preserve at write, resolve at read (`DISCERN`, Nov 2026) and versioned rollback (`ChronoMem`, Jul 2026):**
   `DISCERN` shows that retention/recall is near-saturated while entity/temporal resolution
   and calibrated abstention remain the true bottleneck—arguing for additive provenance
   preservation rather than destructive overwrite. `ChronoMem` treats memory rollback as an
   explicit versioned systems problem, though its evaluation covers linear history and
   leaves arbitrary branching/unknown-fork restores open.
3. **Upper-ontology discipline (`BFO` ISO/IEC 21838-2, `DOLCE`):**
   Formal upper ontologies separate enduring entities/invariants (*continuants*) from
   time-bounded events/processes (*occurrents*) without committing to domain vocabularies.
   Importing a full formal OWL hierarchy would over-engineer dynamic game discovery, so we
   borrow only a minimal game-neutral epistemic core while leaving domain tags emergent.
4. **Counter-evidence against heavy KG-RAG and sensitivity of graph walks (`BRINK`, Aug 2025; `xMemory / Beyond RAG`, Feb 2026; plus our `$0` offline ablation):**
   Under incomplete knowledge (`BRINK`) and correlated agent histories (`xMemory`), rigid
   pairwise KG triples and flat top-$k$ similarity underperform decoupled atomic-component
   + group hierarchies. In our own `$0` offline ablation on sealed `#896-b v91`, naive
   Personalized PageRank with local degree-`0` self-retention lost article rank to
   `bm25_1hop` (`0.825` vs `0.879` ArtMRR@5), whereas switching degree-`0` handling to
   seed teleportation lifted PPR to `0.900` ArtMRR@5 (essentially tying `bm25_1hop` at
   `0.700` vs `0.717` ArtRec@5).
5. **Alternative non-graph paradigms (`WorldEvolver`, Jun 2026; `TMEM`, Jun 2026; `How LoRA Remembers`, May 2026):**
   Training-free world models (`WorldEvolver`) extract semantic rules specifically from
   *prediction–observation mismatches* and gate low-confidence foresight—guiding what the
   curator should prioritize writing. Parametric fast-weight memory (`TMEM` / test-time
   LoRA) is a serious long-horizon alternative for procedural skill adaptation on owned
   weights, but is structurally unsuited to an auditable, rollbackable, API-hosted
   game-state fact store.

## Empirical diagnosis from sealed Enactive runs

Inspecting the sealed git tags directly—`#896-b` tag **`v91`**
(`.runtime/evidence/seven-day-896-b-admission-10/knowledge/cdda`, 572 `facts.jsonl` rows:
459 fact rows + 113 article rows, of which 112 are marked `superseded_by`: 46 facts and
66 articles, leaving **413 current facts** and **47 current articles**) and `#889` tag
**`v17`** (`.runtime/evidence/live-validation-run-889/knowledge/cdda`, 168 `facts.jsonl`
rows: 135 fact rows + 33 article rows, of which 11 articles and 0 facts are marked
`superseded_by`, leaving **135 current facts** and **22 current articles**)—reveals four
concrete structural limitations in `curator-knowledge/3` and `delivered-knowledge/2`:

1. **Free-text fact-type drift across runs of the exact same game:**
   Without a small game-neutral epistemic core, the curator invented incompatible type
   vocabularies across two runs of the same game (counting current facts at each tag):
   - `#896-b v91` (413 current facts): `control` (169), `world_observation` (106),
     `crafting_recipe` (71), `item_property` (56), `construction_project` (7),
     `creation_option_property` (4).
   - `#889 v17` (135 current facts): `interface_control` (65), `recipe_requirement` (29),
     `location_observation` (17), `entity_property` (17), `character_option` (4),
     `skill_effect` (3).
   (On `known` evidence basis, `v91` has 412 `observed` / 1 `inferred` and `v17` has
   134 `observed` / 1 `inferred`; the contract's `hinted` basis also exists in
   `docs/contracts/curator.md` and must be preserved separately from lifecycle state.)
2. **Coarse two-level scope (`game` vs `world`) without transfer or branch semantics:**
   Current facts split strictly into `level: "game"` vs `level: "world"` (`307 game / 106 world`
   at `#896-b v91`; `119 game / 16 world` at `#889 v17`). There is no game-neutral way to
   express scenario, ruleset/patch, biome, character, or timeline-branch scope, nor to state
   conditional applicability (`when`) or cross-scope transfer rules.
3. **Revision-suffixed article IDs complicate stable ID lookup and cross-version tracing:**
   Under the current contract (`docs/contracts/curator.md`), forward `links` target
   **article titles**—and every forward link in both `v91` and `v17` resolves cleanly.
   However, because the curator encodes revision suffixes into article IDs
   (`article-crafting-recipes-v3`, `article-bed-construction-grass-a02`,
   `article-bow-fire-drill-groom27`, `article-tent-sleep-corrected-a06`), every major
   rewrite mints a new ID, breaking stable ID-based `player_knowledge_read` references,
   complicating cross-version diffing, and leaving no inverse `backlinks` or
   `cited_by_articles` index. Meanwhile, raw evidence `citations` live on stored facts in
   `facts.jsonl` and are omitted from `delivered-knowledge/2` facts.
4. **Brittle retrieval ignores existing article–fact and link structure:**
   In `#896-b`, both live `player_knowledge_query` calls returned `[]` under
   `delivered-knowledge/2`'s strict all-token substring `AND` rule:
   - Admission 1 (`v3`): `"food cooking roasting stick makeshift cooking tool campfire"`
   - Admission 3 (`v38`): `"straw withered plants harvest tall grass grass straw"`
   Meanwhile, delivered articles already carry `1`–`6` forward `links` and `1`–`21` cited
   `facts` (`body[*].facts`), forming an n-ary hyperedge graph that retrieval ignores.

## Primary literature synthesis and read-scope honesty

Every source below was verified against its primary URL on `2026-11-23`. Read scope is
reported honestly: **Primary HTML sections** means the arXiv HTML text of the listed
sections was fetched and read; **Abstract + metadata** means only the primary `arxiv.org/abs`
page (or specification landing page) was read, so no deep claim beyond the abstract is
inferred.

| Source (verified primary URL & date) | Read scope | Core mechanism & verified finding | Relevance & limit for Enactive |
| --- | --- | --- | --- |
| **STALE** — Chao et al., [arXiv:2605.06527](https://arxiv.org/abs/2605.06527) (7 May 2026) | Primary HTML: §3.2, §4.2, §5, §6 | Defines *Implicit Conflict* across 400 scenarios (1,200 queries) with 3 probes: State Resolution (SR), Premise Resistance (PR), and Implicit Policy Adaptation (IPA). Best frontier model reached 55.2% overall; most memory frameworks fell below 10%. Proposes write-side adjudication (`CUPMem`). | Explains stale-plan anchoring after game state changes or reloads; conversational benchmark, not visual game control. |
| **StateAuditor** — Sun & He, [arXiv:2608.01619](https://arxiv.org/abs/2608.01619) (3 Aug 2026) | Primary HTML: §1, §4, §6.3, §8 | Diagnoses the IPA gap: write-side updates reach 91% SR yet only 32% IPA, with updated evidence visible in 67.8% of failed drafts. Audits generated drafts backward against provenance-verified timelines; finds extraction, not verification, is the bottleneck. | Shows why surfacing updated facts or marking articles `needs_review` is a warning rather than a behavioral guarantee. Personalized dialogue domain. |
| **DISCERN** — Ahuja et al., [arXiv:2611.15729](https://arxiv.org/abs/2611.15729) (11 Nov 2026) | Abstract + metadata | Argues persistent agent memory is a *resolution* problem ("preserve at write, resolve at read"): builds a strictly additive bi-temporal provenance graph without merging confusable entities or dropping superseded values, then navigates it via a zero-LLM tool surface with calibrated abstention (`ENT-310` abstention F1 `0.924` vs `<=0.802`, entity resolution `0.800` vs `<=0.40`). | Directly supports preserving immutable history/citations at write time and resolving scope/currency at read time with explicit uncertainty. Enterprise sales-agent benchmark. |
| **ChronoMem** — Su et al., [arXiv:2607.27773](https://arxiv.org/abs/2607.27773) (Jul 2026) | Primary HTML: §1, §2.3, §3.1–3.3, §4 | Models agent memory rollback via an append-only event log + versioned snapshots `S(v_j)` + deterministic rollback to eliminate post-rollback leakage in QA and summarization. | Validates git-versioned snapshots + explicit rollback semantics for save/load games; explicitly evaluates linear history and leaves branching/unknown-fork restores unevaluated. |
| **xMemory (Beyond RAG)** — Hu et al., [arXiv:2602.02007](https://arxiv.org/abs/2602.02007) (Feb 2026) | Primary HTML: §1, §3, §4.1 | Shows fixed top-$k$ similarity overweights near-duplicate trajectory spans; decouples history into atomic components aggregated into hierarchical groups and expands to raw messages only when reader uncertainty warrants it. | Strongly supports Enactive's atomic `facts` + synthesized `articles` + on-demand `player_source` hierarchy over flat chunk RAG. |
| **HyperMem** — Yue et al., [arXiv:2604.08256](https://arxiv.org/abs/2604.08256) (Apr 2026) | Primary HTML: §1, §3, §4, §5 | Models memory as a 3-level hypergraph (topics, episodes, facts) connecting multiple nodes in one n-ary hyperedge rather than pairwise triples; reports 92.73% on LoCoMo vs HippoRAG 2 (81.62%), GraphRAG (67.60%), Zep (65.99%), A-MEM (48.38%). | Shows n-ary groupings beat pairwise triples; Enactive's `article` (`body[*].facts`) is already a lightweight hyperedge without needing an embedding hypergraph engine. |
| **BRINK** — Zhou et al., [arXiv:2508.08344](https://arxiv.org/abs/2508.08344) (Aug 2025) | Primary HTML: §1, §3.3 | Benchmarks KG-RAG reasoning under incomplete knowledge (Family, FB15k-237, Wikidata5m) and measures structural degradation when multi-hop chains have missing edges. | Cautionary counter-evidence against heavy entity-relation KGs in partially explored games where most world edges remain unobserved. |
| **HippoRAG 2** — Gutiérrez et al., [arXiv:2502.14802](https://arxiv.org/abs/2502.14802) (Feb / rev. 19 Jun 2025) | Primary HTML: §1, §3, §5 | Combines dense-sparse retrieval with KG Personalized PageRank (PPR) and recognition memory for multi-hop associativity and sense-making. | Inspires our PPR ablation baseline; relies on large embedding encoders and targets much larger corpora than current Enactive stores. |
| **A-MEM** — Xu et al., [arXiv:2502.12110](https://arxiv.org/abs/2502.12110) (Feb 2025) | Primary HTML: §1, §3, §5 | Zettelkasten-inspired atomic notes with dynamic LLM-generated links and retroactive evolution of older notes as new memories arrive. | Validates retroactive linking during curation, though HyperMem's comparison (48.38% LoCoMo) warns that unstructured note linking alone underperforms hierarchical grouping. |
| **Zep / Graphiti** — Rasmussen et al., [arXiv:2501.13956](https://arxiv.org/abs/2501.13956) (20 Jan 2025) | Primary HTML: §1, §2.2.3, §4.3.2 | Bi-temporal KG tracking four timestamps (`t_created`, `t_expired`, `t_valid`, `t_invalid`) for edge invalidation; lifts LongMemEval accuracy (+15.2% / +18.5%) while cutting context from 115k to 1.6k tokens. | Establishes the clean bi-temporal split (system transaction time vs world valid time) that we adopt in simplified form without a graph DB. |
| **WorldEvolver** — Zhang et al., [arXiv:2606.30639](https://arxiv.org/abs/2606.30639) (Jun 2026) | Primary HTML: §1, §3.2, §5 | Training-free evolving world model: episodic transition memory + semantic heuristic rules extracted from *prediction–observation mismatches* + *Selective Foresight* gating. | Guides curator write prioritization: record action–outcome surprises and preconditions rather than routine narration. |
| **TMEM** — Ren et al., [arXiv:2606.04536](https://arxiv.org/abs/2606.04536) (3 Jun 2026) & **How LoRA Remembers** — Xu et al., [arXiv:2605.30260](https://arxiv.org/abs/2605.30260) (28 May 2026) | Primary HTML §1 (`2606.04536`); Abstract (`2605.30260`) | Compiles extracted rollout insights into fast parametric LoRA weights so experience alters policy natively; formalizes parametric memory recall laws. | Long-horizon contrast: strong for procedural adaptation on owned weights, unsuitable for auditable/rollbackable external game-state memory or hosted APIs. |
| **BFO** ([ISO/IEC 21838-2](https://www.iso.org/maintenance_agencies.html)) & **DOLCE** (Masolo et al., 2003; [ISO/IEC 21838-3](https://www.iso.org/obp/ui?_escaped_fragment_=iso%3Astd%3Aiso-iec%3A21838%3A-3%3Aed-1%3Av1%3Aen)) | Secondary summaries + ISO overview metadata (paywalled ISO texts not read) | Standard upper ontologies separating enduring entities/qualities (*continuants*) from time-bounded events/processes (*occurrents*); BFO realist vs DOLCE descriptive/cognitive. | *Engineering inference:* borrow only the minimal enduring-rule vs transient-instance/event distinction; reject full OWL/BFO class hierarchies to avoid ontological rigidity. |
| **AMV-L** (`2603.04443`), **Memory Security** (`2604.16548`), **Echo** (`2604.05533`), **BALROG** (`2411.13543`), **MemoryArena** (`2602.16313`), **Mem-Gallery** (`2601.03515`), **Surveys** (`2512.13564`, `2605.06716`), **CoALA** (`2309.02427`) | Abstract + metadata | Tail-latency footprint control, memory poisoning governance, Minecraft cross-task transfer, multi-game agent benchmarks, multimodal long-term memory, and agent memory taxonomies. | Reinforces bounding delivered briefing/index footprint, preserving `grants_authority=false` + citation provenance, and separating transferable mechanics from instance state. |
| **W3C PROV-O** ([w3.org/TR/prov-o](https://www.w3.org/TR/prov-o/)), **SQL:2011 / XTDB** ([docs.xtdb.com](https://docs.xtdb.com/)), **Datomic** ([docs.datomic.com](https://docs.datomic.com/)) | Primary spec landing pages | Standardized provenance (`Entity`, `Activity`, `Agent`, `wasDerivedFrom`, `wasInvalidatedBy`) and transaction-time vs valid-time bi-temporality (native in XTDB; app-level valid time over immutable transaction time in Datomic). | Provides standard terminology for provenance chains and bi-temporal validity without inventing ad-hoc names. |

## `$0` offline retrieval ablation on sealed Enactive corpora

Full exact queries, gold IDs, scoring formulas, live-version replays, and per-query ranks
are preserved in the dated study record
[Offline retrieval ablation on sealed knowledge snapshots (#924)](acceptance/2026-11-23-knowledge-retrieval-ablation-924.md).

### 1. Exact live-version replays (zero temporal lookahead)
Replaying the two live `#896-b` `player_knowledge_query` misses against the **exact**
delivered snapshots active at those steps (`A01 v3`: 5 articles / 37 facts; `A03 v38`: 22
articles / 210 facts):
- **`A01 v3`** (`"food cooking roasting stick makeshift cooking tool campfire"`):
  `strict_and` returned `[]`; both `ranked_overlap` and `bm25_1hop` ranked
  `article-crafting-recipes-v3` `#1` along with `clean-water-recipe-boiling`.
- **`A03 v38`** (`"straw withered plants harvest tall grass grass straw"`):
  `strict_and` returned `[]`; `ranked_overlap` ranked fact `grass-yarn-straw-spindle-recipe-a02`
  `#1` and `article-bed-construction-grass-a02` `#2`, while `bm25_1hop` ranked both
  synthesized articles (`article-bed-construction-grass-a02` and
  `article-grass-yarn-sheets-completed-a03`) `#1` and `#2`.

### 2. Retrospective `#896-b v91` (20 queries) and `#889 v17` (10 queries) summary
(Note: the two `#896-b` query strings are also scored retrospectively against `v91` to test
ranking behavior once the store grows to 47 articles / 413 facts; they are **not** credited
as live-step recovery.)

| Corpus & Method | Hit@5 (gold article or its cited fact) | Article Recall@5 | Article MRR@5 | Avg latency | Median top-5 payload |
| --- | --- | --- | --- | --- | --- |
| **`#896-b v91` (20 queries)** | | | | | |
| `prod_strict_and` (current `Knowledge.query`) | `0.250` | `0.133` | `0.250` | `2.26 ms` | `0 B` |
| `ranked_overlap` | `1.000` | `0.725` | `0.722` | `0.83 ms` | `5,260 B` |
| `bm25` (flat) | `1.000` | `0.512` | `0.658` | `1.49 ms` | `4,649 B` |
| **`bm25_1hop` (links + backlinks + parent)** | **`1.000`** | **`0.717`** | **`0.879`** (`1.000` direct, `0.760` multihop) | **`1.48 ms`** | **`5,423 B`** |
| `bm25_ppr_self` (PPR, dangling self-retain) | `0.950` (`0.875` multihop) | `0.650` | `0.825` (`0.625` multihop) | `1.92 ms` | `5,285 B` |
| `bm25_ppr_teleport` (PPR, dangling teleport) | `1.000` | `0.700` | `0.900` (`1.000` direct, `0.812` multihop) | `1.91 ms` | `5,342 B` |
| **`#889 v17` (10 queries)** | | | | | |
| `prod_strict_and` (current `Knowledge.query`) | `0.300` | `0.267` | `0.300` | `0.73 ms` | `0 B` |
| `ranked_overlap` | `1.000` | `0.900` | `0.950` | `0.18 ms` | `3,941 B` |
| `bm25` (flat) | `1.000` | `0.917` | `0.700` | `0.35 ms` | `3,309 B` |
| **`bm25_1hop` (links + backlinks + parent)** | **`1.000`** | **`1.000`** | **`1.000`** | **`0.35 ms`** | **`4,473 B`** |
| `bm25_ppr_self` (PPR, dangling self-retain) | `1.000` | `0.950` | `1.000` | `0.54 ms` | `3,659 B` |
| `bm25_ppr_teleport` (PPR, dangling teleport) | `1.000` | `1.000` | `1.000` | `0.56 ms` | `3,893 B` |

**Three empirical takeaways:**
- Moving off production `Knowledge.query` (`prod_strict_and`) eliminates the multi-term miss
  failure mode (`0.250 -> 1.000` Hit@5 on `v91`, `0.300 -> 1.000` on `v17`, and recovers
  both live `v3` and `v38` misses).
- **The case for `bm25_1hop` over `ranked_overlap` rests specifically on earlier article rank
  (`Article MRR@5` `0.879` vs `0.722` on `v91`, and `1.000` vs `0.950` on `v17`):**
  `ranked_overlap` matches `bm25_1hop` on `v91` `Hit@5` (`1.000`) and slightly edges it on
  `Article Recall@5` (`0.725` vs `0.717`), while flat `bm25` drops article recall to `0.512`
  because short facts outscore longer articles under length normalization. Propagating
  1-hop fact→parent-article and article-link scores restores article recall while lifting
  top-rank precision (`MRR@5`) cleanly in `~1.5 ms`.
- **Controlled dangling-node PPR ablation (`bm25_ppr_self` vs `bm25_ppr_teleport`):**
  With local self-retention for degree-`0` nodes, `bm25_ppr_self` lost rank on four
  multihop queries (`Q13, Q14, Q18, Q19`, while improving on `Q20`), dropping `v91`
  `Article MRR@5` to `0.825`. Switching *only* degree-`0` handling to seed teleportation
  (`bm25_ppr_teleport`) recovered all four queries (`0.900` ArtMRR@5, `1.000` Hit@5 on
  `v91`; `1.000` across all metrics on `v17`). Because `bm25_1hop` achieves virtually the
  same accuracy (`0.879` vs `0.900` MRR, `0.717` vs `0.700` Recall) with no iterative
  walk tuning, `bm25_1hop` is the right default for `delivered-knowledge/3`, with
  `bm25_ppr_teleport` as a tested drop-in upgrade if larger stores later need multi-hop
  associative recall.

## Cross-game stress test (`P-GENERALITY`)

Any schema adopted in [#925](https://github.com/CVX-Hull/enactive/issues/925) must work
across radically different game classes without CDDA-specific keys (`world`, `overmap`,
`crafting_recipe`, `profession`).

| Game archetype (examples) | Scope axes needed | Temporal / invalidation failure mode | Cross-scope transfer behavior |
| --- | --- | --- | --- |
| **Open-world survival roguelike** (CDDA) | `game`, `ruleset`, `scenario`, `biome`, `world`, `character`, `branch` | Reloading a save or abandoning a world leaves old tile/container state alive; patch changes recipes. | `game`/`ruleset`/`scenario`/`biome` mechanics transfer; `world`/`character`/`branch` `instance_state` stays isolated. |
| **4X / RTS with patches & maps** (Civilization, StarCraft) | `game`, `ruleset` (patch), `faction`, `map_type`, `match`, `branch` | Balance patch invalidates unit counters; fog-of-war enemy build changes mid-match. | Same-patch mechanics transfer across matches; cross-patch claims downgrade to *hypothesis*. |
| **Roguelite with meta-progression** (Hades, Slay the Spire) | `game`, `ruleset`, `profile` (meta-unlocks), `run` | Run-specific deck/boon state dies on run end, while meta-unlocks persist across runs. | `profile` state persists across `run`; `run`-scoped state excludes automatically on new `run`. |
| **Knowledge-gated time-loop puzzle** (Outer Wilds) | `game`, `loop_run` | Physical world resets every loop, yet physical laws and discovered codes remain valid across loops. | Separating `mechanic` (invariant) from `instance_state` (`loop_run`-scoped) solves time loops cleanly. |
| **Rule-rewriting puzzle** (Baba Is You) | `game`, `level`, `branch` + `valid_interval` | Pushing text blocks rewrites physics rules *inside a single level*! | Even `mechanic` claims carry `scope` and `valid_interval`, so a rule true at turn 4 can be invalidated at turn 5. |
| **Branching narrative / save-scum RPG** (Baldur's Gate 3, Disco Elysium) | `game`, `ruleset`, `campaign`, `branch`, `scene` | Loading an earlier save forks a parallel timeline where an NPC is alive and quest flags differ. | Explicit `branch` + fork-point metadata (or conservative `contested` downgrade when fork point is unknown) prevents post-reload leakage. |

## Concrete design recommendations for `#925` (`curator-knowledge/4` & `delivered-knowledge/3`)

### 1. Two-tier ontology: fixed epistemic core + separate lifecycle + emergent tags
Keep the fixed schema tiny, universal, and strictly game-neutral; separate **how a claim
was learned** (`evidence_basis`) from **whether it is still current** (`lifecycle_state`)
so provenance survives revision (preserving `hinted` alongside `observed` and `inferred`):

- **`claim_kind` (fixed 5-value enum):** `interface` | `mechanic` | `entity_property` | `instance_state` | `strategy`.
- **`evidence_basis` (fixed 3-value enum, immutable per record):** `observed` | `inferred` | `hinted` (preserving the existing `docs/contracts/curator.md` `known` semantics).
- **`lifecycle_state` (fixed 4-value enum):** `active` | `contested` | `superseded` | `retracted`.
- **`tags` (open lowercase kebab-case list):** Curator-emergent domain labels (`["fire", "water-boiling"]`, `["econ", "opening"]`). No game-specific schema enum.

### 2. Keyed `scope` map + optional `when` condition, enforced before graph expansion
Replace the rigid `{"game", "level": "game"|"world", "world"}` dict with a **keyed scope
map** (`scope: dict[str, str]`, always containing `"game"`, plus any subset of generic
axes such as `ruleset`, `scenario`, `biome`, `profile`, `world`, `run`, `level`,
`character`, `branch`) plus an optional free-text or structured `when` applicability
condition (e.g., `"night"`, `"indoor"`, `"under_rain"`, `"before_level_rule_change"`).

**Strict keyed-subset eligibility and `when` rule:** Given an active run's `target_scope`
map and a record's `scope` map (plus optional `when` condition):
1. **Direct match (`scope ⊆ target_scope`):** Every axis `k` declared in the record's
   `scope` MUST exist in `target_scope` with `scope[k] == target_scope[k]`. A record
   scoped to `{game, profile: A}` therefore does **not** directly qualify for a target
   containing only `{game}` (preventing unknown-prerequisite leaks). More specific matching
   scopes take precedence on conflict.
2. **Explicit cross-scope transfer exceptions (take precedence when a single non-matching
   axis differs):**
   - **Same world, different start/character** (`world` matches; `character` or `scenario`
     differs): `character`-scoped `instance_state` is **excluded**. World-level
     `instance_state` (e.g., cached loot at a map tile) is eligible as
     `transfer: "cross_start_hypothesis"`. Non-`instance_state` claims (`interface`,
     `mechanic`, `entity_property`, `strategy`) that match all declared axes remain directly
     eligible; those scoped to a different `scenario` downgrade to
     `transfer: "cross_scope_hypothesis"`.
   - **Same start/scenario, different world** (`scenario`/`biome`/`ruleset` matches; `world`
     differs): all `world`/`branch`/`character`/`run` `instance_state` records are **excluded
     by default** (zero cross-world state leakage). Non-`instance_state` claims with
     `scope ⊆ target_scope` transfer directly; those scoped to a sibling `world` or
     `ruleset` transfer only when explicitly requested and tagged
     `transfer: "cross_scope_hypothesis"`.
3. **`when` condition evaluation (applied alongside scope before expansion):**
   - Known `true` in current context → eligible normally.
   - Known `false` in current context → **excluded** from default reads and expansion.
   - `unknown` / unverified (the common case when no structured predicate evaluates it) →
     eligible **only** with `condition_unverified: true` attached (preserving the `when`
     text so the player verifies cheaply before relying).
4. **Graph-boundary invariant:** Both scope eligibility and `when` filtering are applied
   **before** 1-hop graph expansion and **before** computing delivered `backlinks` /
   `related` neighbors, so an eligible article can never expose an excluded sibling-world,
   wrong-profile, or falsified-`when` record through a link.

### 3. Bi-temporal + branch invalidation and honest staleness warnings
Combine `Zep`'s valid-time/transaction-time split, `DISCERN`'s additive provenance graph,
`ChronoMem`'s versioned snapshots, and `STALE`/`StateAuditor`'s IPA-gap lesson:

- **Transaction time & immutable history:** Preserve `published_in`, `superseded_by`, and
  raw `citations` in `facts.jsonl` without destructive deletion (`DISCERN`).
- **Valid interval & rollback branches:** Support optional `valid_from` / `valid_to` (step
  or game-clock coordinate) and `branch` (with optional `parent_branch` + `fork_point`).
  - **When the save/restore fork point is known:** `instance_state` and level/branch-scoped
    `mechanic` records with `valid_from > fork_point` on the abandoned branch are excluded
    from the restored branch, while pre-fork records on ancestor branches remain eligible.
  - **When the restore fork point is unknown** (for example, an opaque manual reload or
    untracked world reset): do **not** pretend automatic exclusion can separate pre-save
    from post-save facts. Instead, downgrade all `instance_state` records and all mutable
    `branch`- or `level`-scoped `mechanic` records whose validity across the restore cannot
    be established to `lifecycle_state: "contested"` / `needs_verification` until
    re-observed, preventing silent stale assertions.
- **Cascading stale-citation warnings (`needs_review`):** When a fact `F_old` transitions
  to `superseded` or `retracted`, the gate/exporter marks every article claim citing
  `F_old` with `stale_citations: [F_old]` and sets `needs_review: true` on the article,
  while `delivered-knowledge/3` resolves `superseded_by` pointers cleanly. Per `STALE`
  and `StateAuditor`, treat `needs_review` as an explicit **warning signal for curator
  repair and player verification**, not a guarantee that the player will ignore stale
  prose in its draft plan.

### 4. Stable article slugs, typed links, export-computed backlinks, and `bm25_1hop`
- **Stable logical slugs:** Separate logical article identity (e.g., `brazier-fires`) from
  git/publication version (`v27`), eliminating `-v3`/`-a02`/`-groom27` ID churn for stable
  `player_knowledge_read` ID lookups and cross-version diffing.
- **Typed directed links + export-computed backlinks:** Upgrade `articles[*].links` to
  typed edges `{target_slug, rel}` over a minimal 5-type vocabulary (`depends_on`,
  `contradicts`, `supersedes`, `part_of`, `see_also`), and compute scope-filtered
  `backlinks` and fact `cited_by_articles` deterministically at export time
  (`tools/knowledge_export.py`) so the curator never maintains reverse pointers by hand.
- **Provenance traceability (`W3C PROV-O` style):** Keep `article -> claim -> fact` links
  and expose optional `citation_source_ids` on delivered facts (projected from `facts.jsonl`
  `citations`) so player and curator can trace `article -> fact -> player_source PNG` and
  `fact -> dependent articles` in one hop.
- **Local retrieval (`delivered-knowledge/3`):** Implement scope-filtered **`bm25_1hop`**
  (Okapi BM25 over title/slug/lead/body/tags + 1-hop typed links, backlinks, and
  fact→parent-article elevation). Delivers `1.000` Hit@5 and `0.879`–`1.000` Article MRR@5
  in `~1.4 ms` with zero external services, zero embeddings, and deterministic replay.

### 5. What NOT to build yet (justified rejections)
- **No full BFO/DOLCE/OWL hierarchy or pairwise RDF triple extraction:** `BRINK` and
  `HyperMem` show pairwise triples degrade under incomplete knowledge; Enactive's n-ary
  `article -> claims -> facts` structure already avoids pairwise fragmentation.
- **No external vector DB or embedding service:** Current stores are 22–47 articles and
  135–413 facts (`< 0.5 MB`); `bm25_1hop` already hits `1.000` Hit@5 in `1.4 ms`. Revisit
  hybrid dense+sparse only if stores exceed ~1,000+ articles and an offline benchmark
  demonstrates lexical mismatch.
- **No multi-hop PPR diffusion by default yet:** Naive PPR with dangling self-retention
  lost article MRR (`0.825` vs `0.879`) on `v91`, and dangling-corrected `bm25_ppr_teleport`
  only roughly tied `bm25_1hop` (`0.900` vs `0.879` MRR, `0.700` vs `0.717` Recall) at
  added iterative complexity; keep `bm25_ppr_teleport` as a tested future upgrade if
  larger corpora later require multi-hop associative recall.
- **No parametric fast-weight / LoRA memory (`TMEM`):** Incompatible with hosted inference
  APIs, `grants_authority=false` auditability, and deterministic rollback. Keep as a
  long-horizon direction only if Enactive trains local procedural weights.
