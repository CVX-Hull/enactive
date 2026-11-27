---
owner: lead
status: historical
kind: measurement
date: '2026-11-27'
scope: 'Zero-cost offline store-migration freeze (#1046): #1021 #998 bounding-box check on RV, fire ring, and brazier; pinned #1023 four #998 diagnostic probe queries and retrieval baselines across #896-b v91, #889 v17, and #998 v97/v101; and shared #998 player-host replay baseline across A01-A04'
---

# Store-migration freeze, `#998` bounding-box check and shared replay baselines (`#1046`)

## At a glance

- **Question.** (1) Can vision-only bounding-box prediction on sealed `#998` `960×640` frames reliably produce `~20–35%` coarse-neighborhood boxes for the RV, fire ring, and brazier to justify `depiction: {source_id, region?}` cropping over full-frame `depiction_source_id` (`#1021`)? (2) What are the exact pinned `#1023` `#998` probe queries, as-of targets, snippet-content criteria, and pre-migration retrieval baselines across `#896-b v91`, `#889 v17`, and `#998 v97`/`v101`? (3) What is the verified `#998` player-host replay baseline shared by `#1025`, `#1037`, and `#1027`?
- **`#1021` bounding-box verdict: SELECT full-frame `depiction_source_id` (defer `region` cropping).** Both `gpt-6.1-terra` (medium, Codex) and `claude-sonnet-5-5` (medium, Claude Code) achieved `100%` containment and `0.0 px` center error on the single-tile adjacent fire ring and brazier, **but both clipped the multi-tile Luxury RV** (`176×352 px`, `55.0%` of frame height) to `63.6%` and `62.5%` recall under the `20–35%` neighborhood band—cutting off the RV's front door and/or rear beds. Furthermore, both single-tile frames sat immediately adjacent to the camera-centered avatar (`(320..352, 320..352)`), and coding-agent vision transports differ from the live curator's `view_frame` transport. Under `#1046`'s rule (all 3 landmarks must pass; inconclusive selects full-frame), Batch 1 ships `depiction_source_id`.
- **`#1023` retrieval baseline (`knowledge-retrieval-benchmark/2`):** Historical `#896-b v91` and `#889 v17` baselines reproduce `#936` bit-for-bit (`bm25_1hop` Article MRR@5 `0.917` and `1.000`). On the four pinned `#998` probes (`start-time`, `fire-ring`, `rv-door`, `crafting-filter`), current production `bm25_1hop` reaches `Hit@5 = 1.000` and `Article MRR@5 = 1.000` on both `v97` and `v101`, `3/4` top-5 hit snippets pass (`start-time` fails because `wilderness-default-calendar` ranks `18th`), and **`0/4` gold-article snippets pass** on both `v97` and `v101` (every gold article lead omits the answer detail).
- **Shared `#998` replay baseline (`player_host_replay_benchmark.py --lineage 998`):** Replays all 4 admissions, 4 actors, `102` versions (`v0..v101`), `2,504` context checks, `81` observed cuts (`81` projected under Ballot 4), `78` observed holds (`78` projected), `0` hard capacity stops (`152,592` min uncut headroom), `82` delivered updates (`78` empty, `80` paired with a briefing), `108` recall fetches (`$0.307616`), and prior-admission ancestor PNG counts `0 / 683 / 1,410 / 2,023` at A01–A04.
- **Frozen Batch 1 contract:** Complete schemas (`curator-knowledge/5`, `curator-fact/6`, `curator-submission/3`, `delivered-knowledge/4`, `player-knowledge/4`), gate invariants, `8,192`-byte (`8 KiB`) `hygiene.py` article cutoff, caller/fixture inventory, and five-session `#963`+`#998` archive cutover live in [the frozen Batch 1 store-migration contract](../design/store-migration-contract.md).
- **Cost & stop condition:** `$0` provider API spend (read-only sealed evidence + subscription coding-agent delegates only).

[Issue #1046](https://github.com/CVX-Hull/enactive/issues/1046) ·
[Frozen Batch 1 contract](../design/store-migration-contract.md) ·
[Memory review #1019](2026-11-26-campaign-memory-review-1019.md) ·
[Retrieval baseline #936](2026-11-24-wave3-retrieval-baseline-and-curator-recount-936.md) ·
[Attempts ledger](../../data/evaluation/coding-agent-attempts.jsonl)

---

## 1. `#1021` offline `#998` bounding-box check (RV, fire ring, brazier)

### Pre-stated selection rule

Select `depiction: {source_id, region?: [x1, y1, x2, y2]}` cropping in Batch 1 only if **all three** unobstructed `#998` `960×640` landmark frames (Luxury RV, fire ring, brazier) achieve:

1. `100%` landmark containment (`recall == 1.0`, zero clipping of the landmark's ground-truth pixel box);
2. Coarse-neighborhood size within the `~20–35%` width/height band (`<= 40%` width and `<= 40%` height) and center error `<= 50 px`; and
3. Verification on the pinned live curator transport (or conclusive pass without transport/off-center confounds).

Any failure or inconclusive result selects full-frame **`depiction_source_id`** first and defers `region` cropping.

### Ground truth and vision-only measurements (`$0`)

Ground-truth pixel coordinates were measured on the `32×32`-tile `960×640` PNGs from sealed `#998` evidence (reticle-verified against `Look around` frames `088ba6385ed4d42f6e728ad34d8fe943-24289` and `a6979727b98c9fde6e8e0f502fea128d-3507`). Two read-only vision explorers in the strongest frame-reading group (`gpt-6.1-terra` medium on Codex and `claude-sonnet-5-5` medium on Claude Code) were instructed to view the three unobstructed normal-play PNGs directly with **zero shell or pixel-measurement commands** (verified in both raw run logs):

| Landmark | Sealed `#998` frame (`960×640`) | Ground-truth tight box | Model (effort) | Predicted `tight` | Predicted `region` | Region W×H % | Region recall | Center err | Verdict |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- |
| **Luxury RV** | `088ba6385ed4d42f6e728ad34d8fe943-5068.png` | `[280, 288, 456, 640]` (`18.3% × 55.0%`) | `gpt-6.1-terra` (med) | `[282, 287, 455, 640]` | `[240, 352, 496, 576]` | `26.7% × 35.0%` | **`0.636`** | `0.0 px` | **FAIL (clipped)** |
| **Luxury RV** | `088ba6385ed4d42f6e728ad34d8fe943-5068.png` | `[280, 288, 456, 640]` (`18.3% × 55.0%`) | `claude-sonnet-5-5` (med) | `[288, 284, 448, 640]` | `[230, 300, 500, 520]` | `28.1% × 34.4%` | **`0.625`** | **`54.1 px`** | **FAIL (clipped)** |
| **Fire ring** | `f91a383e469ae6722febb75cf90a7bbd-3151.png` | `[320, 320, 352, 352]` (`3.3% × 5.0%`) | `gpt-6.1-terra` (med) | `[319, 321, 353, 352]` | `[216, 256, 456, 416]` | `25.0% × 25.0%` | `1.000` | `0.0 px` | Pass (centered) |
| **Fire ring** | `f91a383e469ae6722febb75cf90a7bbd-3151.png` | `[320, 320, 352, 352]` (`3.3% × 5.0%`) | `claude-sonnet-5-5` (med) | `[318, 318, 354, 352]` | `[206, 240, 466, 432]` | `27.1% × 30.0%` | `1.000` | `0.0 px` | Pass (centered) |
| **Brazier** | `a6979727b98c9fde6e8e0f502fea128d-3738.png` | `[320, 320, 352, 352]` (`3.3% × 5.0%`) | `gpt-6.1-terra` (med) | `[322, 329, 351, 346]` | `[216, 256, 456, 416]` | `25.0% × 25.0%` | `1.000` | `0.0 px` | Pass (centered) |
| **Brazier** | `a6979727b98c9fde6e8e0f502fea128d-3738.png` | `[320, 320, 352, 352]` (`3.3% × 5.0%`) | `claude-sonnet-5-5` (med) | `[320, 326, 354, 348]` | `[206, 240, 466, 432]` | `27.1% × 30.0%` | `1.000` | `0.0 px` | Pass (centered) |

**Findings and frozen decision:**

1. Although both models localized the tight boxes accurately (`<= 2 px` error on RV and fire ring), forcing a `20–35%` neighborhood crop on a large multi-tile landmark (`55.0%` frame height) **clipped the Luxury RV on both models**, dropping the exact west-side driver's door (`y = 288..352`) on `gpt-6.1-terra` and the rear interior (`y = 520..640`) on `claude-sonnet-5-5`.
2. Both single-tile landmarks sat one tile east of the camera-centered avatar (`(320..352, 320..352)`), so off-center single-tile localization remains untested, and the live curator's `view_frame` transport was not exercised at `$0`.
3. **Frozen selection:** Batch 1 (`curator-fact/6`, `delivered-knowledge/4`, `player-knowledge/4`) ships optional **`depiction_source_id`** (full-frame pointer resolved via `#1025`'s `player_source`) and defers `depiction.region` cropping.

---

## 2. `#1023` pinned `#998` probe queries and retrieval baseline

### Reproduction

```sh
PY="$(git rev-parse --git-common-dir)/../.venv/bin/python"
"$PY" tools/knowledge_retrieval_benchmark.py --repeat 50 --markdown
"$PY" tools/player_host_replay_benchmark.py --lineage all --markdown
"$PY" -m pytest -q tests/test_knowledge_retrieval_benchmark.py tests/test_player_host_replay_benchmark.py
```

### Four pinned `#998` diagnostic probe queries (`PROBES_998`)

| Probe | Source | Exact query string | As-of status (`v97`/`v101`) | Gold article(s) | Acceptable gold facts (latest preferred) | Snippet-content criterion (case-insensitive) |
| --- | --- | --- | --- | --- | --- | --- |
| `start-time` | Live `#998` A04 `request-107` | `Rowan starting time spring day 61 72 hours character creation clock` | `current` | `wilderness-start` | **Latest:** `wilderness-default-calendar`; also `rowan-starting-water-frozen` (stale water state, valid spawn clock) | Contains `"8:00 am"` |
| `fire-ring` | Live `#998` A03 `request-257` | `fire ring fire fuel haul stick wood camp Rowan` | `mixed-stale` | `rowan-campground-spawn` | **Latest (Day 63):** `rowan-day-63-ring-fiddlehead-meal`, `rowan-day-63-bough-fire-craft-interruption`; **stale Day 62 / game-wide:** 8 additional fire-ring facts in `PROBES_998` | Contains `"fire ring"` |
| `rv-door` | Diagnostic `#998` | `Luxury RV door enter west side driver door` | `partial-stale` | `rowan-campground-spawn` | `rowan-rv-access-and-condition`, `rowan-returned-rv-rear-bed` (battery/inventory stale by Day 64; west-side door holds) | Contains both `"west-side"` and `"door"` |
| `crafting-filter` | Diagnostic `#998` | `crafting screen recipe filter reset clear query` | `current` | `crafting-controls` | `crafting-filter-controls`, `crafting-replace-filter-and-prefixes`, `crafting-filter-control-u`, `crafting-filter-control-backspace-appends` | Contains any of `"ctrl-u"`, `"backspace"`, `"r to reset"`, `"r resets"` |

### Recorded retrieval baseline (`knowledge-retrieval-benchmark/2`, 50 repetitions)

| Corpus | Method | Queries | Hit@5 | Article Recall@5 | Article MRR@5 | Top-5 snippet pass | Gold article snippet pass | Avg ms | p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `#896-b v91` (47 art / 413 facts) | `prod_bm25` | 20 | `1.000` | `0.613` | `0.700` | — | — | `0.314` | `0.453` |
| `#896-b v91` (47 art / 413 facts) | `bm25_1hop` | 20 | `1.000` | `0.858` | `0.917` | — | — | `0.360` | `0.514` |
| `#889 v17` (22 art / 135 facts) | `prod_bm25` | 10 | `1.000` | `0.917` | `0.650` | — | — | `0.091` | `0.132` |
| `#889 v17` (22 art / 135 facts) | `bm25_1hop` | 10 | `1.000` | `1.000` | `1.000` | — | — | `0.107` | `0.146` |
| `#998 v97` (15 art / 326 facts) | `bm25_1hop` (prod) | 4 | `1.000` | — | `1.000` | `3/4` | **`0/4`** | `0.283` | `0.384` |
| `#998 v101` (17 art / 336 facts) | `bm25_1hop` (prod) | 4 | `1.000` | — | `1.000` | `3/4` | **`0/4`** | `0.297` | `0.392` |

Per-probe `#998` baseline ranks (`v97` / `v101`):

| Probe | Article rank@5 | First gold fact rank@10 | Latest fact full rank (`v97` / `v101`) | Top-5 snippet pass | Gold article snippet pass |
| --- | ---: | ---: | ---: | --- | --- |
| `start-time` | `1` / `1` | `8` / `8` | **`18`** / **`18`** | no / no | no / no |
| `fire-ring` | `1` / `1` | `2` / `2` | **`6`** / **`7`** | yes / yes | no / no |
| `rv-door` | `1` / `1` | `2` / `2` | `2` / `2` | yes / yes | no / no |
| `crafting-filter` | `1` / `1` | `2` / `2` | `2` / `2` | yes / yes | no / no |

Every gold article ranked `#1` yet scored **`0/4`** on `gold_article_snippet_pass` because its lead omitted the query's answer detail—providing a direct paired `$0` gate for `#1023`'s benchmark-gated query-matched claim snippet candidate.

---

## 3. Shared `#998` player-host replay baseline

Measured by `tools/player_host_replay_benchmark.py --lineage all`:

| Metric | `#896-b` (10 admissions, `v0..v91`) | `#998` (4 admissions, `v0..v101`) |
| --- | ---: | ---: |
| Actors / context checks | `12` / `3,744` (Ballot 4) | `4` / `2,504` |
| Recorded cuts / Ballot-4 projected cuts | `77` / `77` | `81` / `81` |
| Observed holds / Ballot-4 projected holds | `2,128` / `85` | `78` / `78` |
| Observed / projected hard capacity stops (Ballot 4) | `0` / `0` | `0` / `0` |
| Ballot-4 min uncut headroom (est. tokens) | `112,444` | `152,592` |
| Archive heuristic error (max over / under tokens) | `0` / `8,583` | `2` / `4,239` |
| Recorded recall fetches / observed recall spend | `358` / `$3.496352` | `108` / `$0.307616` |
| Recorded `all-delivered` skips (no fetch) | — (`player-host/11`) | `108` (`player-host/12`) |
| Delivered updates (total / empty / non-empty / paired with briefing) | — | **`82` / `78` / `4` / `80`** |
| Prior-admission ancestor PNGs on disk at admission start | — | A01 `0`, A02 `683`, A03 `1,410`, A04 `2,023` |
| Actor-start briefing JSON chars (observed / projected) | up to `51,502` / `20,042` | `100`, `2,616`, `2,777`, `3,679` (`0` omitted) |

---

## Limitations

- The four `#998` retrieval probes are in-sample diagnostic probes over sealed `#998` `v97`/`v101` (`delivered-knowledge/3`), distinct from the out-of-sample corpus required for `#1020` trigger `T1`.
- The `#1021` bounding-box check used coding-agent vision transports at `$0` rather than the live curator's `view_frame` transport and did not test off-center single-tile objects; this conservatism reinforces selecting `depiction_source_id` first.
- All timings come from one personal computer and are indicative only.
