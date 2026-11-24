---
owner: lead
status: historical
kind: study
date: 2026-11-23
scope: "Zero-cost offline retrieval ablation for #924 on sealed #896-b (A01 v3, A03 v38, A10 v91) and #889 (v17) delivered knowledge snapshots: production strict_and baseline, exact formulas, controlled dangling-node PPR ablation, and per-query ranks"
---

# Offline retrieval ablation on sealed knowledge snapshots (#924)

## At a glance

- **Spend:** `\$0` (pure offline local scoring over read-only sealed snapshots; no model call, no game launch).
- **Exact live-version replays (zero lookahead):** Both `#896-b` `player_knowledge_query` misses (`A01 v3`, `A03 v38`) return `[]` under production `harness.player.knowledge.Knowledge.query` and recover relevant articles/facts under all four ranked variants.
- **Production baseline vs ranked (`v91`, 20 queries):** production `strict_and` scores `0.250` Hit@5 / `0.250` ArtMRR@5; `bm25_1hop` reaches `1.000` / `0.879` (`1.48 ms`).
- **Controlled dangling-node PPR ablation (`v91`):** switching only degree-`0` node handling from local self-retention (`bm25_ppr_self`: `0.950` Hit@5, `0.825` ArtMRR@5) to seed teleportation (`bm25_ppr_teleport`: `1.000` Hit@5, `0.900` ArtMRR@5) eliminates the PPR regression and essentially ties `bm25_1hop` (`0.900` vs `0.879` MRR, `0.700` vs `0.717` ArtRec).

This dated study record preserves the exact inputs, scoring equations, live-version
replays, controlled PPR ablation, and per-query ranks summarized in the
[meta-ontology, scoping and wiki/graph retrieval research note](../research-knowledge-graph-scoping.md)
for [#924](https://github.com/CVX-Hull/enactive/issues/924).

## Sealed inputs

- `.runtime/evidence/seven-day-896-b-admission-01/run/curator-runner/delivered/v3.json` (5 articles, 37 facts)
- `.runtime/evidence/seven-day-896-b-admission-03/run/curator-runner/delivered/v38.json` (22 articles, 210 facts)
- `.runtime/evidence/seven-day-896-b-admission-10/run/curator-runner/delivered/v91.json` (47 articles, 413 facts)
- `.runtime/evidence/live-validation-run-889/run/curator-runner/delivered/v17.json` (22 articles, 135 facts)

## Exact scoring equations (`k = 5`, tie-break `(-score, id)`)

Tokenization extracts lowercase `[a-z0-9]+` tokens of length `>= 2` excluding 20 English
stopwords (`a, an, and, are, as, at, be, by, for, from, how, in, is, it, of, on, or, the, to, with`).
Each article defines `title_toks = tok(title + ' ' + id)` and `body_toks = tok(lead + ' ' + join(body[*].text))`;
each fact defines `title_toks = tok(subject + ' ' + id)` and `body_toks = tok(text)`.
Every ranked method sets `all_toks = title_toks + title_toks + body_toks`, deduplicates
query tokens via `Q = set(tok(query))`, and breaks exact score ties lexicographically by
ascending record `id` (`key=lambda x: (-score, id)`).

1. **`prod_strict_and` (production `delivered-knowledge/2`):** exact call to `harness.player.knowledge.Knowledge(path).query(query)['records'][:5]`, which checks every lowercase whitespace-split term against the full serialized record JSON.
2. **`ranked_overlap`:** `score(d) = 2.5 * |Q ∩ set(title_toks)| + 1.0 * |Q ∩ set(body_toks)| + (0.2 if article else 0.0)`, excluding zero-overlap records.
3. **`bm25`:** Okapi BM25 (`k1 = 1.2`, `b = 0.75`) over `all_toks` with `N = len(docs)`, `avgdl = mean(|all_toks|)`, `idf(t) = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))`, summing over unique query terms `t ∈ Q`: `idf(t) * tf(t, d) * (k1 + 1) / (tf(t, d) + k1 * (1 - b + b * |all_toks| / avgdl))`.
4. **`bm25_1hop`:** undirected adjacency `adj` connects each article `a` to any record whose ID is in `a.links` or `a.body[*].facts` (symmetric). Starting from `combined = bm25`, for each of the top-10 BM25 seeds `(u, s)` with `deg(u) > 0`, add `(0.35 * s / sqrt(deg(u))) * w(v)` to every neighbor `v ∈ adj[u]`, where `w(v) = 1.25` if `v` is an article else `0.70`.
5. **`bm25_ppr_self` (dangling self-retention):** seed distribution `p` normalizes top-12 BM25 scores to sum to `1`. Run 15 iterations with restart probability `alpha = 0.35`: `r_{t+1}[u] = alpha * p[u] + sum_{v -> u} (1 - alpha) * r_t[v] / deg(v)`, plus `(1 - alpha) * r_t[u]` retained on `u` whenever `deg(u) == 0`. Final score uses max-normalization: `0.55 * (bm25[d] / max(bm25)) + 0.45 * (r[d] / max(r))`.
6. **`bm25_ppr_teleport` (controlled dangling-node ablation):** identical to `bm25_ppr_self` in every parameter (`alpha = 0.35`, 15 iterations, top-12 seeds, `0.55 / 0.45` max-normalized blend), except mass from `deg(u) == 0` nodes (`sum_{deg(u)==0} (1 - alpha) * r_t[u]`) is redistributed proportionally across `p` instead of retained on `u`.

## Exact live-version replays (zero temporal lookahead)

### A01 v3 (seven-day-896-b-admission-01) (5 articles, 37 facts)
- Query: `food cooking roasting stick makeshift cooking tool campfire`
- `prod_strict_and`: `[]`
- `ranked_overlap`: `['article-crafting-recipes-v3', 'wooden-spear-recipe', 'article-shelter-local-pickup', 'clean-water-recipe-boiling', 'consume-menu-uppercase-e']`
- `bm25`: `['wooden-spear-recipe', 'consume-menu-uppercase-e', 'clean-water-recipe-boiling', 'article-crafting-recipes-v3', 'heat-pack-one-use']`
- `bm25_1hop`: `['article-crafting-recipes-v3', 'wooden-spear-recipe', 'consume-menu-uppercase-e', 'clean-water-recipe-boiling', 'heat-pack-one-use']`
- `bm25_ppr_self`: `['wooden-spear-recipe', 'article-crafting-recipes-v3', 'consume-menu-uppercase-e', 'clean-water-recipe-boiling', 'heat-pack-one-use']`
- `bm25_ppr_teleport`: `['wooden-spear-recipe', 'article-crafting-recipes-v3', 'clean-water-recipe-boiling', 'consume-menu-uppercase-e', 'heat-pack-one-use']`

### A03 v38 (seven-day-896-b-admission-03) (22 articles, 210 facts)
- Query: `straw withered plants harvest tall grass grass straw`
- `prod_strict_and`: `[]`
- `ranked_overlap`: `['grass-yarn-straw-spindle-recipe-a02', 'article-bed-construction-grass-a02', 'article-grass-yarn-sheets-completed-a03', 'grass-yarn-wheel-recipes-a02', 'construction-straw-bed']`
- `bm25`: `['grass-yarn-straw-spindle-recipe-a02', 'article-bed-construction-grass-a02', 'grass-yarn-wheel-recipes-a02', 'construction-straw-bed', 'straw-basket-recipe-inspected-a03']`
- `bm25_1hop`: `['article-bed-construction-grass-a02', 'article-grass-yarn-sheets-completed-a03', 'grass-yarn-straw-spindle-recipe-a02', 'grass-yarn-wheel-recipes-a02', 'construction-straw-bed']`
- `bm25_ppr_self`: `['article-bed-construction-grass-a02', 'article-grass-yarn-sheets-completed-a03', 'grass-yarn-straw-spindle-recipe-a02', 'straw-basket-recipe-inspected-a03', 'grass-yarn-wheel-recipes-a02']`
- `bm25_ppr_teleport`: `['article-bed-construction-grass-a02', 'article-grass-yarn-sheets-completed-a03', 'grass-yarn-straw-spindle-recipe-a02', 'grass-yarn-wheel-recipes-a02', 'construction-straw-bed']`

## Aggregate metrics

| Corpus & Method | Hit@5 (gold article or its cited fact) | Article Recall@5 | Article MRR@5 | Avg latency | Median top-5 payload |
| --- | --- | --- | --- | --- | --- |
| **`#896-b v91` (20 queries)** | | | | | |
| `prod_strict_and` | `0.250` | `0.133` | `0.250` | `2.26 ms` | `0 B` |
| `ranked_overlap` | `1.000` | `0.725` | `0.722` | `0.83 ms` | `5,260 B` |
| `bm25` | `1.000` | `0.512` | `0.658` | `1.49 ms` | `4,649 B` |
| `bm25_1hop` | `1.000` | `0.717` | `0.879` | `1.48 ms` | `5,423 B` |
| `bm25_ppr_self` | `0.950` | `0.650` | `0.825` | `1.92 ms` | `5,285 B` |
| `bm25_ppr_teleport` | `1.000` | `0.700` | `0.900` | `1.91 ms` | `5,369 B` |
| **`#889 v17` (10 queries)** | | | | | |
| `prod_strict_and` | `0.300` | `0.267` | `0.300` | `0.73 ms` | `0 B` |
| `ranked_overlap` | `1.000` | `0.900` | `0.950` | `0.18 ms` | `3,941 B` |
| `bm25` | `1.000` | `0.917` | `0.700` | `0.35 ms` | `3,309 B` |
| `bm25_1hop` | `1.000` | `1.000` | `1.000` | `0.35 ms` | `4,473 B` |
| `bm25_ppr_self` | `1.000` | `0.950` | `1.000` | `0.54 ms` | `3,659 B` |
| `bm25_ppr_teleport` | `1.000` | `1.000` | `1.000` | `0.56 ms` | `3,747 B` |

## Retrospective `#896-b v91` per-query ranks (20 queries)

Rank columns report the 1-based rank of the first gold article in top 5 (`—` if absent).

| # | Group | Query | Gold articles | `prod_strict_and` | `ranked_overlap` | `bm25` | `bm25_1hop` | `bm25_ppr_self` | `bm25_ppr_teleport` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `real_896b` | `food cooking roasting stick makeshift cooking tool campfire` | `article-basic-tools-groom40`, `article-brazier-fires-groom27`, `article-cattail-stalk-cooking-groom27`, `article-fire-reliability-groom39` | — | 2 | — | 2 | 2 | 2 |
| 2 | `real_896b` | `straw withered plants harvest tall grass grass straw` | `article-bed-construction-grass-a02`, `article-grass-yarn-sheets-groom39`, `article-storage-clothing-groom39` | — | 2 | 2 | 1 | 1 | 1 |
| 3 | `direct` | `boil murky water filtration wood stove clean water` | `article-murky-filtration-a06`, `article-water-fire-toilet-a03`, `article-wood-stove-water-groom59` | — | 3 | 1 | 1 | 1 | 1 |
| 4 | `direct` | `how to start fire bow drill tinder brazier` | `article-bow-fire-drill-groom27`, `article-brazier-fires-groom27` | 1 | 2 | 2 | 1 | 1 | 1 |
| 5 | `direct` | `sleep in tent bed wait fatigue warmth` | `article-bed-construction-grass-a02`, `article-bed-wait-groom59`, `article-tent-sleep-corrected-a06` | — | 2 | 2 | 1 | 1 | 1 |
| 6 | `direct` | `wooden spear pointy stick weapon melee reach` | `article-wooden-spear-pointy-a03` | — | 1 | 3 | 1 | 1 | 1 |
| 7 | `direct` | `foraging cattail stalks rhizome jelly seeds` | `article-cattail-foraging-raw-stalk-a07`, `article-cattail-jelly-seeds-groom48`, `article-cattail-stalk-cooking-groom27` | 1 | 1 | 1 | 1 | 1 | 1 |
| 8 | `direct` | `reading nearby books skill training light` | `article-books-reading-a06` | 1 | 1 | 1 | 1 | 1 | 1 |
| 9 | `direct` | `craft backpack improvised storage grass clothing` | `article-backpack-recipes-groom59`, `article-storage-clothing-groom39` | 1 | 1 | 1 | 1 | 1 | 1 |
| 10 | `direct` | `butcher painted turtle meat snails gastropods` | `article-painted-turtle-butchery-a07`, `article-snails-gastropods-a07` | — | 1 | 2 | 1 | 1 | 1 |
| 11 | `direct` | `ferns fiddleheads burdock cooked acorns wild vegetables` | `article-burdock-fire-out-a06`, `article-cooked-acorns-a07`, `article-fern-fiddleheads-groom59`, `article-underbrush-wild-vegetables-a06-late` | — | 3 | 1 | 1 | 1 | 1 |
| 12 | `direct` | `pickup nested liquid containers household water` | `article-household-pickup-groom48`, `article-household-water-groom59`, `article-pickup-storage-groom48` | 1 | 1 | 1 | 1 | 1 | 1 |
| 13 | `multihop` | `safe indoor heat source to purify drinking supply without smoke` | `article-brazier-fires-groom27`, `article-craftable-braziers-a04`, `article-water-fire-toilet-a03`, `article-wood-stove-water-groom59` | — | 4 | — | 3 | — | — |
| 14 | `multihop` | `sewing needle cordage fiber to repair or craft gear` | `article-grass-yarn-sheets-groom39`, `article-needle-plant-string-groom17`, `article-storage-clothing-groom39` | — | 1 | 2 | 1 | 2 | 1 |
| 15 | `multihop` | `batch crafting search filter resume interrupted recipe` | `article-crafting-selection-groom50`, `article-crafting-workflow-groom40`, `article-fire-reliability-groom39` | — | 1 | 1 | 1 | 1 | 1 |
| 16 | `multihop` | `scouting overmap distance binoculars vehicle electronic doors` | `article-binoculars-flaregun-groom17`, `article-electronic-door-groom59`, `article-inspection-travel-groom40`, `article-vehicle-inspection-groom17` | — | 1 | 1 | 1 | 1 | 1 |
| 17 | `multihop` | `hydration vitamin morale warm tea juice` | `article-bee-balm-tea-consumed-a09`, `article-field-nutrition-groom59`, `article-fruit-juice-groom48` | — | 1 | 1 | 1 | 1 | 1 |
| 18 | `multihop` | `window curtains line of sight monsters inside house` | `article-curtains-threats-groom48` | — | 5 | 1 | 1 | 2 | 1 |
| 19 | `multihop` | `river crossing deep water swimming hazard movement` | `article-salvage-movement-groom39`, `article-water-traversal` | — | 3 | — | 4 | — | 2 |
| 20 | `multihop` | `eating raw forage versus cooked meal hunger calories` | `article-cattail-foraging-raw-stalk-a07`, `article-cattail-stalk-cooking-groom27`, `article-food-consumption-raw-stalk-a07` | — | 1 | 3 | 2 | 1 | 1 |

**Controlled dangling-node PPR diagnosis:** Under `bm25_ppr_self`, four multihop queries
lost gold-article rank relative to `bm25_1hop` (`Q13`: `3 -> —`, `Q14`: `1 -> 2`, `Q18`: `1 -> 2`,
`Q19`: `4 -> —`), while `Q20` improved (`2 -> 1`). Replacing only degree-`0` self-retention
with seed teleportation (`bm25_ppr_teleport`, holding every other parameter fixed)
recovered `Q13`, `Q14`, `Q18`, and `Q19`, lifting `v91` `Article MRR@5` from `0.825` to
`0.900` and `Hit@5` from `0.950` to `1.000` (and `v17` `Article Recall@5` from `0.950`
to `1.000`).

## Retrospective `#889 v17` per-query ranks (10 queries)

| # | Query | Gold articles | `prod_strict_and` | `ranked_overlap` | `bm25` | `bm25_1hop` | `bm25_ppr_self` | `bm25_ppr_teleport` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `wooden spear crafting pointy stick` | `article-wooden-spear-v3` | 1 | 1 | 2 | 1 | 1 | 1 |
| 2 | `water treatment boiling clean water recipes` | `article-water-treatment-recipes-v5` | 1 | 1 | 1 | 1 | 1 | 1 |
| 3 | `cotton patch bleeding emergency bandage treatment` | `article-emergency-patches` | — | 1 | 1 | 1 | 1 | 1 |
| 4 | `brazier fire wait fuel cooking` | `article-brazier-fire-and-wait` | — | 1 | 1 | 1 | 1 | 1 |
| 5 | `digging stick clay extraction` | `article-digging-stick`, `article-extracting-clay` | — | 1 | 4 | 1 | 1 | 1 |
| 6 | `hickory nuts foraging calories` | `article-hickory-nuts` | — | 2 | 4 | 1 | 1 | 1 |
| 7 | `sleeping fatigue rest shelter` | `article-sleeping` | — | 1 | 1 | 1 | 1 | 1 |
| 8 | `nearby items threats enemies V list` | `article-exploration-controls-v2`, `article-nearby-threats` | — | 1 | 1 | 1 | 1 | 1 |
| 9 | `wilderness scenario character creation survivor profession` | `article-creation-v2`, `article-survivor`, `article-wilderness-v2` | 1 | 1 | 2 | 1 | 1 | 1 |
| 10 | `ground stick salvage firewood` | `article-stick-salvage` | — | 1 | 2 | 1 | 1 | 1 |
