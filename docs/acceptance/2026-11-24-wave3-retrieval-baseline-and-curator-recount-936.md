---
owner: lead
status: historical
kind: study
date: 2026-11-24
scope: "Zero-cost offline Wave 3 evidence record for #936 (Evidence Gate 11): the #920 field-weighted BM25 baseline and bm25_1hop on the 30 #924 queries over sealed #896-b v91 and #889 v17, the paired coverage-skip comparison on a labelled direct-answer subset with its Gate 9 decision, and a read-only recount of the sealed #896-b curator history (v0 to v91)"
---

# Wave 3 retrieval baseline, paired coverage-skip comparison and `#896-b` curator recount (#936)

## At a glance

- **Question.** What does #920's merged field-weighted BM25 score on the 30 #924 queries? What does
  one hop over the article graph add? Should the coverage skip ship in #937? Do the sealed `#896-b`
  curator counts quoted in the [design note](../design/knowledge-graph-scoping-contract.md#what-the-sealed-curator-run-shows)
  hold?
- **Baseline.** #920's `Knowledge.query` reaches Hit@5 `1.000` on both corpora. Its article MRR@5 is
  `0.700` on `#896-b v91` and `0.650` on `#889 v17`.
- **One hop.** `bm25_1hop` on #920's scores raises article MRR@5 to `0.917` and `1.000`, and article
  Recall@5 from `0.613` to `0.858` and from `0.917` to `1.000`. Its 95th-percentile query time is
  `0.490 ms` and `0.140 ms`, under the `5 ms` target.
- **Coverage skip: DROP for #937.** The subset is four explicit questions, each asking for a fact
  detail that the citing article's prose omits. On them the skip raises distinct records reached in
  the top 10 from `41.25` to `54.50`. It removes every gold fact from the top 10 in all four. Fact
  Recall@5 falls from `1.000` to `0.000` and fact MRR@5 from `0.458` to `0.000`. The answers cost `4`
  reads instead of `0`, over both the top 5 and the top 10. It fails three of the four Gate 9 conditions.
- **Recount.** Most of the design note's counts reproduce exactly: `91` of `91` gate verdicts published,
  `11` of `23` restatements omitting an old citation, `250` of `381` revised claims byte-identical,
  admission prompts `279.0` times completions, and nine aborted sessions ending on `provider-error`.
  Four quoted figures need correcting or qualifying (see [the comparison](#the-design-notes-counts-against-the-recount)).
- **Not known.** The queries and labels are in-sample. The subset has four queries. The timings come
  from one personal computer. Gate 9 itself runs on the migrated `delivered-knowledge/3` code, not on
  these `delivered-knowledge/2` files.
- **Owner decisions needed.** None. Gate 9 states the skip rule, and this record applies it.

## Reproduction

Both scripts read the sealed store only. They make no model call, launch no game and write nothing.
They default to the main checkout's `.runtime/evidence` (`tools.evidence.default_store`); `--evidence DIR`
points them elsewhere. In a worktree, use the main checkout's Python:

```sh
PY="$(git rev-parse --git-common-dir)/../.venv/bin/python"
"$PY" tools/knowledge_retrieval_benchmark.py --markdown   # or --json; --repeat N sets timing repetitions (default 50)
"$PY" tools/curator_history_recount.py --markdown          # or --json
"$PY" -m pytest -q tests/test_knowledge_retrieval_benchmark.py
```

Every number below is printed by one of the two scripts, in both `--json` and `--markdown`. Every
quality figure is deterministic. The timings are from one run on 2026-11-24. Three further runs of the
benchmark gave a v91 `bm25_1hop` 95th percentile between `0.492` and `0.507 ms`.

## Inputs

| Corpus | Sealed file | Articles | Facts | Graph edges |
| --- | --- | --- | --- | --- |
| `#896-b v91` | `seven-day-896-b-admission-10/run/curator-runner/delivered/v91.json` | `47` | `413` | `382` |
| `#889 v17` | `live-validation-run-889/run/curator-runner/delivered/v17.json` | `22` | `135` | `140` |
| `#896-b A01 v3` | `seven-day-896-b-admission-01/run/curator-runner/delivered/v3.json` | `5` | `37` | `35`, live replay only |
| `#896-b A03 v38` | `seven-day-896-b-admission-03/run/curator-runner/delivered/v38.json` | `22` | `210` | `214`, live replay only |

The recount reads `seven-day-896-b-admission-10/knowledge/` (the curator Git repository `cdda/` and its
`cdda.state/`). It also reads each `seven-day-896-b-admission-NN/` runner `examined.jsonl` and
`grooming/grooming-summary.json`.

## Method

**Queries and gold labels.** The script holds the 30 queries and gold articles of the
[#924 record](2026-11-23-knowledge-retrieval-ablation-924.md) verbatim: 20 on `v91` and 10 on `v17`.
Two `v91` queries (`Q01`, `Q02`) are the live `#896-b` `player_knowledge_query` calls. The script also
replays those two on the versions the player held, `A01 v3` and `A03 v38`, which have no gold labels.

**`prod_bm25`.** This method calls `harness.player.knowledge.Knowledge(path).query(q)` unchanged: #920's
merged ranking with weights title or subject `3`, lead or type `2`, and body or text `1`.

**`bm25_1hop`.** The script recomputes the production BM25 scores with the production index, term
folding and constants. On all 32 queries it checks that their order equals `Knowledge.query`'s, and it
stops if not. It then follows the design note's [retrieval steps](../design/knowledge-graph-scoping-contract.md#retrieval-bm25_1hop-with-a-coverage-skip):

1. It builds an undirected graph from claim citations (`body[*].facts`) and links.
2. It takes the 10 best records `u` among those with score `s > 0` and degree above 0, so an isolated
   record takes no seed slot. Each adds `0.35 · s / √deg(u)` to each neighbour, multiplied by `1.25`
   for an article and `0.70` for a fact.
3. It keeps records with a positive score, orders them by score with ties in delivered order, and
   returns the first 10.

This is the test-only projection Gate 9 names. The old ID stands in for the slug, and each link (a title
in `delivered-knowledge/2`) resolves to the article with that title. All 137 `v91` links and all 32 `v17`
links resolve, as do all 11 `v3` and all 65 `v38` links. The sealed files carry no tags, so the old `type` stays indexed at weight `2`, the slot
tags take in `delivered-knowledge/3`.

**`bm25_1hop_skip`.** The script walks the identical order, skips a fact that an article already kept
cites, and stops at 10 records.

**Article metrics.** These are as #924 defined them, over the first 5 results of the mixed list of
articles and facts:

- Hit@5 credits a gold article or a fact a gold article cites.
- Article Recall@5 is the share of gold articles returned.
- Article MRR@5 is the reciprocal 1-based rank of the first gold article.

**Reached@10** counts the distinct records a result reaches: each returned record and every fact a
returned article cites. **Timing** runs every query 50 times and takes the average and 95th percentile
over all samples. That covers 1,000 samples on `v91` and 500 on `v17`, each including the deep copy the
production reader makes.

## Overall ranking

| Corpus | Method | Hit@5 | Article Recall@5 | Article MRR@5 | Reached@10 | Average | 95th percentile |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `#896-b v91` (20 queries) | `prod_bm25` (#920 baseline) | `1.000` | `0.613` | `0.700` | `18.80` | `0.304 ms` | `0.436 ms` |
| `#896-b v91` (20 queries) | `bm25_1hop` | `1.000` | `0.858` | `0.917` | `33.10` | `0.349 ms` | `0.490 ms` |
| `#896-b v91` (20 queries) | `bm25_1hop_skip` | `1.000` | `0.900` | `0.925` | `45.50` | `0.361 ms` | `0.511 ms` |
| `#889 v17` (10 queries) | `prod_bm25` (#920 baseline) | `1.000` | `0.917` | `0.650` | `19.10` | `0.085 ms` | `0.117 ms` |
| `#889 v17` (10 queries) | `bm25_1hop` | `1.000` | `1.000` | `1.000` | `27.60` | `0.103 ms` | `0.140 ms` |
| `#889 v17` (10 queries) | `bm25_1hop_skip` | `1.000` | `1.000` | `1.000` | `39.30` | `0.109 ms` | `0.146 ms` |

On these projected files both one-hop arms meet Gate 9's overall-ranking condition on both corpora. Hit@5
and article MRR@5 are at least the baseline's, and the 95th percentile is under `5 ms`. The skip's
article gains do not bear on the skip decision: the skip only deletes facts from a fixed order, so it
cannot lower article metrics ([coverage versus redundancy](../design/knowledge-graph-scoping-contract.md#coverage-versus-redundancy)).

These one-hop figures are higher than #924's `bm25_1hop` (`0.717` article Recall@5 and `0.879` article
MRR@5 on `v91`). Two inputs differ. The base scores are #920's rather than #924's flat BM25. This graph
also resolves links by title, whereas #924's stated formula joins a link only when it equals a record ID,
and no sealed link does. The #924 record does not include its code, so this record does not split the
difference between the two causes.

### First gold-article rank in the top 5

`—` means no gold article is in the top 5.

| Corpus | Query | Group | Text | `prod_bm25` | `bm25_1hop` | `bm25_1hop_skip` |
| --- | --- | --- | --- | --- | --- | --- |
| `v91` | Q01 | `real_896b` | `food cooking roasting stick makeshift cooking tool campfire` | — | `3` | `2` |
| `v91` | Q02 | `real_896b` | `straw withered plants harvest tall grass grass straw` | `3` | `1` | `1` |
| `v91` | Q03 | `direct` | `boil murky water filtration wood stove clean water` | `1` | `1` | `1` |
| `v91` | Q04 | `direct` | `how to start fire bow drill tinder brazier` | `2` | `1` | `1` |
| `v91` | Q05 | `direct` | `sleep in tent bed wait fatigue warmth` | `1` | `1` | `1` |
| `v91` | Q06 | `direct` | `wooden spear pointy stick weapon melee reach` | `3` | `1` | `1` |
| `v91` | Q07 | `direct` | `foraging cattail stalks rhizome jelly seeds` | `1` | `1` | `1` |
| `v91` | Q08 | `direct` | `reading nearby books skill training light` | `1` | `1` | `1` |
| `v91` | Q09 | `direct` | `craft backpack improvised storage grass clothing` | `1` | `1` | `1` |
| `v91` | Q10 | `direct` | `butcher painted turtle meat snails gastropods` | `2` | `1` | `1` |
| `v91` | Q11 | `direct` | `ferns fiddleheads burdock cooked acorns wild vegetables` | `1` | `1` | `1` |
| `v91` | Q12 | `direct` | `pickup nested liquid containers household water` | `1` | `1` | `1` |
| `v91` | Q13 | `multihop` | `safe indoor heat source to purify drinking supply without smoke` | `4` | `2` | `2` |
| `v91` | Q14 | `multihop` | `sewing needle cordage fiber to repair or craft gear` | `2` | `1` | `1` |
| `v91` | Q15 | `multihop` | `batch crafting search filter resume interrupted recipe` | `1` | `1` | `1` |
| `v91` | Q16 | `multihop` | `scouting overmap distance binoculars vehicle electronic doors` | `1` | `1` | `1` |
| `v91` | Q17 | `multihop` | `hydration vitamin morale warm tea juice` | `1` | `1` | `1` |
| `v91` | Q18 | `multihop` | `window curtains line of sight monsters inside house` | `3` | `1` | `1` |
| `v91` | Q19 | `multihop` | `river crossing deep water swimming hazard movement` | `1` | `1` | `1` |
| `v91` | Q20 | `multihop` | `eating raw forage versus cooked meal hunger calories` | `4` | `2` | `2` |
| `v17` | Q01 | `direct` | `wooden spear crafting pointy stick` | `2` | `1` | `1` |
| `v17` | Q02 | `direct` | `water treatment boiling clean water recipes` | `1` | `1` | `1` |
| `v17` | Q03 | `direct` | `cotton patch bleeding emergency bandage treatment` | `1` | `1` | `1` |
| `v17` | Q04 | `direct` | `brazier fire wait fuel cooking` | `1` | `1` | `1` |
| `v17` | Q05 | `direct` | `digging stick clay extraction` | `2` | `1` | `1` |
| `v17` | Q06 | `direct` | `hickory nuts foraging calories` | `4` | `1` | `1` |
| `v17` | Q07 | `direct` | `sleeping fatigue rest shelter` | `2` | `1` | `1` |
| `v17` | Q08 | `direct` | `nearby items threats enemies V list` | `1` | `1` | `1` |
| `v17` | Q09 | `direct` | `wilderness scenario character creation survivor profession` | `2` | `1` | `1` |
| `v17` | Q10 | `direct` | `ground stick salvage firewood` | `4` | `1` | `1` |

### Live queries on the versions the player held

Unlike #924's all-terms search, which returned nothing for both, every arm returns records for both
live queries.

- **`A01 v3`** `food cooking roasting stick makeshift cooking tool campfire`
  - `prod_bm25`: `wooden-spear-recipe`, `article-crafting-recipes-v3`, `consume-menu-uppercase-e`, `campground-long-sticks-locusts`, `heat-pack-one-use`
  - `bm25_1hop`: `article-crafting-recipes-v3`, `wooden-spear-recipe`, `consume-menu-uppercase-e`, `heat-pack-one-use`, `clean-water-recipe-boiling`
  - `bm25_1hop_skip`: `article-crafting-recipes-v3`, `consume-menu-uppercase-e`, `heat-pack-one-use`, `campground-long-sticks-locusts`, `article-shelter-local-pickup`
- **`A03 v38`** `straw withered plants harvest tall grass grass straw`
  - `prod_bm25`: `grass-yarn-straw-spindle-recipe-a02`, `grass-yarn-wheel-recipes-a02`, `article-bed-construction-grass-a02`, `straw-basket-recipe-inspected-a03`, `construction-straw-bed`
  - `bm25_1hop`: `article-grass-yarn-sheets-completed-a03`, `article-bed-construction-grass-a02`, `grass-yarn-straw-spindle-recipe-a02`, `grass-yarn-wheel-recipes-a02`, `construction-straw-bed`
  - `bm25_1hop_skip`: `article-grass-yarn-sheets-completed-a03`, `article-bed-construction-grass-a02`, `straw-basket-recipe-inspected-a03`, `shore-vegetation-movement-slow-a02`, `lake-day62-harvest-return-brazier-a02`

## Paired coverage-skip comparison

### The labelled direct-answer subset

A direct-answer query is one whose gold answer is a fact detail that the citing article's prose omits.
The prose is the article's `lead` and `body[*].text`. The subset is separate from the 30 #924 queries,
which stay unchanged for the overall ranking. Each of its four queries is a question that asks for the
omitted detail. Each gold fact is cited by the gold article of a #924 query, named as its topic.

At run time the script checks three things and stops if any fails:

- every word of the detail except its number is a term of the question;
- the detail string is in every gold fact's text and in no citing article's prose;
- the skip suppresses a gold fact from the top 10 in at least one query.

The labels were chosen by reading candidates in the sealed files. Candidates were rejected where the
citing article stated the detail in words rather than digits.

| Label and topic | Question | Detail | Gold facts |
| --- | --- | --- | --- |
| `v91` `long-pointy-stick-pierce` (#924 Q06) | `what pierce damage does a long pointy stick do` | `pierce 9` | `long-pointy-stick-recipe-reach-a03` |
| `v91` `cooked-wild-vegetables-kcal` (#924 Q11) | `how many kcal do cooked wild vegetables give` | `34 kcal` | `cooked-wild-vegetables-inspected-a06` |
| `v17` `cotton-patch-improvement` (#924 Q03) | `what percent improvement does a cotton patch give on a bleeding wound` | `50% improvement` | `cotton-patch-bleeding-treatment` |
| `v17` `desert-island-variants` (#924 Q09) | `how many Desert Island variants does the Wilderness start location menu list` | `5 variants` | `wilderness-location-choices` |

| Label | What the citing article says instead |
| --- | --- |
| `long-pointy-stick-pierce` | Gives only the finished spear's pierce 18 |
| `cooked-wild-vegetables-kcal` | Gives the cooked result's 35% vitamin C, not its calories |
| `cotton-patch-improvement` | Says one patch reduced the bleed, without the menu's 50% |
| `desert-island-variants` | Gives Campground's four variants, not Desert Island's 5 or the random 13 |

The script's omission scan checks whether this selection favours the skip's failure. It runs on the 30
#924 queries and lists every fact in a `bm25_1hop` top 10 whose text holds a number that no citing
article states. On `v91` there are 35 such appearances, of 33 distinct facts, and the skip removes all
35. On `v17` there are 11 appearances of 11 distinct facts, and it removes all 11. So on these corpora
no direct-answer candidate of this kind survives the skip.

### Read counting rule

`player_knowledge_read` calls after the query, counted over the first `k` results. The gate counts both
`k = 5` and `k = 10`, and the skip fails it if it adds a read at either:

- `0` when a gold fact is itself among them;
- `1` when it is not, but an article among them cites it, so the player reads the fact ID in that
  article's `body[*].facts` and calls `player_knowledge_read` once;
- unreached when neither holds, because the query alone gives no ID to read. Unreached ranks worse
  than any count, and none occurred here.

### Results

| Query | Arm | Reached@10 | Fact Recall@5 | Fact MRR@5 | Gold fact rank in top 10 | Reads, k = 5 | Reads, k = 10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `long-pointy-stick-pierce` | no skip | `42` | `1.000` | `0.500` | `2` | `0` | `0` |
| `long-pointy-stick-pierce` | skip | `57` | `0.000` | `0.000` | — | `1` | `1` |
| `cooked-wild-vegetables-kcal` | no skip | `62` | `1.000` | `0.333` | `3` | `0` | `0` |
| `cooked-wild-vegetables-kcal` | skip | `70` | `0.000` | `0.000` | — | `1` | `1` |
| `cotton-patch-improvement` | no skip | `39` | `1.000` | `0.500` | `2` | `0` | `0` |
| `cotton-patch-improvement` | skip | `61` | `0.000` | `0.000` | — | `1` | `1` |
| `desert-island-variants` | no skip | `22` | `1.000` | `0.500` | `2` | `0` | `0` |
| `desert-island-variants` | skip | `30` | `0.000` | `0.000` | — | `1` | `1` |

| Arm | Mean Reached@10 | Fact Recall@5 | Fact MRR@5 | Reads, k = 5 | Reads, k = 10 | Unreached |
| --- | --- | --- | --- | --- | --- | --- |
| `bm25_1hop`, skip disabled | `41.25` | `1.000` | `0.458` | `0` | `0` | `0` |
| `bm25_1hop`, skip enabled | `54.50` | `0.000` | `0.000` | `4` | `4` | `0` |

| Gate 9 condition for keeping the skip | Result |
| --- | --- |
| Raises distinct records reached in the top 10 | Met: `41.25` to `54.50` |
| Lowers neither direct-answer fact Recall@5 | Not met: `1.000` to `0.000` |
| Nor fact MRR@5 | Not met: `0.458` to `0.000` |
| Adds no `player_knowledge_read` call, at `k = 5` or `k = 10` | Not met: `0` to `4` reads at `k = 5`, and `0` to `4` at `k = 10` |

**Decision for #937: DROP coverage skip.** `Knowledge.query` takes the first 10 records of the one-hop
order. This is the case the design note's [coverage versus redundancy](../design/knowledge-graph-scoping-contract.md#coverage-versus-redundancy)
section anticipated: in each labelled question the citing article ranks above its fact, and the skip
discards the only record that carries the number.

## Curator recount

Every count below is from `tools/curator_history_recount.py`, read at the Git tags and from the sealed
gate and session records. A submission counts only when `gate.jsonl` records it as published.

### Versions, gate and operations

| Measure | Count |
| --- | --- |
| Tags | `92` (`v0` to `v91`), so `91` published versions |
| Gate verdicts | `91`, all `published`; `0` with diagnostics, `0` restored |
| Published operations | `add_fact` 436, `add_article` 47, `revise_article` 66, `supersede_fact` 23, `add_type` 7, `revise_types` 3 |

### Facts and types

| Measure | Count |
| --- | --- |
| Facts stored, current and superseded at `v91` | `459`, `413` and `46` |
| Current facts by scope | `game` 307, `world` 106 |
| Types used by current facts | `6` |
| Types ever used | `8` |
| Types registered | `4` at `v1`, `6` at `v91` (range `4` to `6`) |
| Retype events | `12`, on `8` facts |
| Restatements | `23`, replacing `46` facts: `21` merge two, `1` merges three, `1` replaces one |
| Restatements reusing every old citation | `12` |
| Restatements omitting at least one old citation | `11`, `31` citations in all |

### Articles

| Measure | Count |
| --- | --- |
| Articles stored and current at `v91` | `113` and `47` |
| Revisions (`revise_article`) | `66` |
| Revisions with at most 3 claims changed, an edit counted once | `60` (median `2`) |
| Revisions with at most 3 claims added plus removed, an edit counted twice | `40` |
| Revised claims byte-identical to an old claim | `250` of `381` (`0.656`) |
| Citations a revision dropped | `22`. In `21` the fact was superseded at or before that submission. `1` is in the next row |
| Dropped but not superseded | `v16`: revising `article-bow-fire-drill-day62` to `article-bow-fire-drill-v16` dropped `short-string-plant-fiber-recipe`. `article-needle-plant-string-v16` still cited it until its supersession at `v17` |
| Facts left cited by no current article after a revision | `0` |
| Current facts cited by an article, and uncited | `238` and `175` |
| Shared-fact fanout at `v91` | `207` facts cited by one article, `30` by two, `1` by three |

### Sessions and grooming

| Measure | Count |
| --- | --- |
| Curator sessions | `94`: `86` admission sessions and `8` groomings |
| Admission sessions per admission, `a01` to `a10` | `16`, `8`, `11`, `7`, `9`, `11`, `8`, `0`, `10`, `6` |
| Groomings | `a01` to `a07` and `a09`. Admissions `a08` (no curator session ran; its runner `status.json` shows backlog `11`) and `a10` have none |
| Aborted sessions | `9`: `6` admissions and `3` groomings, all ending `provider-error` |
| Written submissions never gated | `1`, in the aborted `a07` admission session at base `v73` |
| Admission prompt and completion tokens | `122,261,824` and `438,232`, a ratio of `279.0` to 1 |

| Grooming | Outcome | Versions | Requests, cap 120 | Largest completed prompt | Bytes read | Charged, cap `$2.50` | Largest reservation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `a01` | Published 2 | `v16` to `v18` | `13` | `96,881` | `194,270` | `$0.248` | `$1.319` |
| `a02` | Published 2 | `v26` to `v28` | `6` | `116,890` | `264,566` | `$0.222` | `$1.523` |
| `a03` | Published 2 | `v38` to `v40` | `9` | `158,918` | `356,990` | `$0.328` | `$1.872` |
| `a04` | Published 3 | `v47` to `v50` | `12` | `179,191` | `424,869` | `$0.400` | `$2.061` |
| `a05` | Published 1 | `v58` to `v59` | `8` | `189,483` | `509,017` | `$0.326` | `$2.154` |
| `a06` | Aborted on HTTP 429, proxy "spend cap reached" | `v69` | `4` | `206,764` | `596,735` | `$0.264` | `$1.861` |
| `a07` | Aborted on HTTP 429, proxy "spend cap reached" | `v76` | `5` | `226,962` | `641,332` | `$0.305` | `$2.133` |
| `a09` | Aborted on HTTP 429, proxy "spend cap reached" | `v85` | `4` | `222,146` | `683,602` | `$0.284` | `$2.015` |

"Bytes read" is the sum of `read_file` results in the host log. In each failed grooming, the three
largest of those results add up to the whole `facts.jsonl` at the base version, superseded rows
included, plus exactly `100` bytes: `567,621`, `618,720` and `656,775` bytes against file sizes of
`567,521`, `618,620` and `656,675`. No completed grooming shows this: its three largest reads exceed the
base file by `16,096` to `39,263` bytes. The refused request records no token usage.

| Aborted admission session | Admission | Base | HTTP | Runner stop | Requests | Written / gated |
| --- | --- | --- | --- | --- | --- | --- |
| `001-356-390-ce6df1e4-786c73c7` | `a03` | `v38` | `429` | `spend-reservation-refused` | `4` | `0` / `0` |
| `001-215-249-692286a5-0ec9f331` | `a04` | `v47` | `429` | `spend-reservation-refused` | `15` | `0` / `0` |
| `001-286-320-19c8ec5b-5a274535` | `a05` | `v58` | `429` | `spend-reservation-refused` | `7` | `0` / `0` |
| `001-356-391-a50af451-97b24b84` | `a06` | `v69` | `429` | `spend-reservation-refused` | `11` | `0` / `0` |
| `001-143-178-7ccab7da-16d74a4c` | `a07` | `v73` | `403` | none recorded | `11` | `1` / `0` |
| `002-112-148-8fa67dc8-0c17bc9f` | `a09` | `v85` | `429` | `spend-reservation-refused` | `12` | `0` / `0` |

### Lineage label in the tenth admission's delivered `v91`

Both `run/actors/001/knowledge/v91.json` and `run/curator-runner/delivered/v91.json` name
`seven-day-896-b` `461` times. That is `413` times in fact `seen` session names, `47` in article
`last_confirmed` session names and `1` in `coverage.session`
(`seven-day-896-b-a10-7a28b7bea730`).

### The design note's counts against the recount

| Design note says | Recount | Holds |
| --- | --- | --- |
| All 91 gate results published, none rejected | `91` of `91` published, `0` with diagnostics | Yes |
| No revision silently dropped a fact | `1` citation dropped without supersession, but still cited elsewhere; no fact orphaned | Yes, if "silently dropped" means left uncited |
| Of 23 restatements, 11 fail a copy-every-citation rule | `11` of `23` | Yes |
| Of 66 revisions, 40 changed at most three claims | `40` when an edit counts as a removal plus an addition; `60` when it counts once | Yes, under the first rule |
| About two-thirds of claims came back byte-identical | `250` of `381` (`0.656`) | Yes |
| Admission prompts outnumbered completions about 279 to 1 | `279.0` to 1 | Yes |
| About ten copied hexadecimal IDs were mistyped | Not recounted | Unknown |
| Three of the last four groomings wrote nothing | `a06`, `a07` and `a09` published nothing; `a05` published 1 | Yes |
| Each re-read about 496 KB of current records | `596,735` to `683,602` bytes read, about the whole base `facts.jsonl` | No: 496 KB is not reproduced |
| HTTP 429 spend-reservation refusals after prompts of about 207,000 to 226,000 tokens | 429 with "spend cap reached"; largest completed prompts `206,764` to `226,962` | Yes |
| None reached its request cap | `4`, `5` and `4` of `120` | Yes |
| All nine aborted sessions (six admissions, three groomings) ended on `provider-error` | Yes; one admission stopped on HTTP `403`, not `429` | Yes; the stop status was mixed |
| One admission's written submission was lost | `1`, the `403` session | Yes |
| The tenth admission's delivered file names the label 440 times in `seen`, plus once in `coverage` | `413` in fact `seen`, `47` in article `last_confirmed`, `1` in `coverage`: `461` | No: 440 is not reproduced |

## Limitations

- **In-sample and wording-sensitive.** #924 wrote 28 of the 30 queries with their gold labels. This
  study wrote the four direct-answer questions after reading the sealed files. While writing them, two
  or three wordings were tried per fact, and the record keeps the full-sentence question for each. One
  keyword-only wording tried, `pointy stick pierce value`, ranked a gold fact above its citing article,
  and there the skip kept that fact. The omission scan shows that no candidate of the scanned kind
  escapes the skip on the #924 queries. Still, four questions is a small subset, wording moves the
  fact-against-article order, and the scan covers only numeric details.
- **Projection, not the migrated code.** Gate 9 replays the queries on test-only projections into
  `delivered-knowledge/3` once #937 lands. There, tags replace `type` in the weight-2 slot and links are
  typed. These figures use the old `type` and title links, so the migrated figures may differ.
- **Timing.** The timings come from one personal computer. They are an order of magnitude under the
  `5 ms` target, not a portable bound.
- **Unread inputs.** The recount does not read the hexadecimal-ID mistypes, provider-side bodies of the
  `429` and `403` responses, or spend beyond the proxy summaries the sealed records hold.
