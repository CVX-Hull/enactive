---
owner: lead
status: historical
kind: review
date: '2026-11-26'
scope: 'Offline review of curated memory, delivery, frame accuracy, expiry and live curation cost across the four sealed admissions of the three-day standard-build campaign (#998), resolving the open checks of #1019 and completing the $0 offline cost breakdown for #1027; subscription quota only, no game launch, no provider spend'
---

# Three-day campaign memory review and live curation cost breakdown (#1019, #1027)

## At a glance

- **Evidence basis:** Recomputed directly from the sealed `#998` admissions
  ([`multi-day-standard-build-998-admission-01`](../../data/evidence/multi-day-standard-build-998-admission-01.sha256)
  through [`-04`](../../data/evidence/multi-day-standard-build-998-admission-04.sha256)) and
  [`multi-day-standard-build-998-campaign`](../../data/evidence/multi-day-standard-build-998-campaign.sha256)
  at `$0` provider spend. The delegated verification reports (deterministic sealed-store/cost
  audit and multimodal PNG inspection) and the four initial handover reports are sealed as
  [`campaign-memory-review-1019`](../../data/evidence/campaign-memory-review-1019.sha256), and
  the independent clean-context review of this record is sealed as
  [`campaign-memory-review-1019-review`](../../data/evidence/campaign-memory-review-1019-review.sha256).
- **Exact spend reconciled (`$35.4508` total):** Live curation cost **`$23.0112`** (`$21.7433`
  across 82 publishing windows, `$1.0096` across 10 spend-cap-refused A3 retries, and
  **`$0.2583`** for A4's interrupted window `001-154-179-fad75a16`, which settled four proxy
  charges before exit without writing a `summary.json` — resolving the `$22.75` vs. `$23.01`
  gap). Boundary grooming cost **`$0.9487`** (total curation **`$23.9599`**) against
  **`$11.4909`** for play (`$11.1833`) and recall (`$0.3076`).
- **Facts matched their frames, but state went stale without retirement:** Across all **40/40**
  sampled active facts (`random.seed(998)`, first four citations per fact), **32** were
  supported, **8** partly supported (mostly unshown keystroke names or timing context), and
  **0** unsupported/wrong. Across **10** world facts checked for evidence of change before
  campaign end, **6** no longer held, **1** had a partial change (RV battery dropped while fuel
  held), **1** probably changed, and **2** were unresolved; all 10 remained `active` with
  `valid_to: null` and no `when` field. Only **3** facts ever ended (all by v12), and all four
  boundary grooming sessions changed **0** fact rows.
- **Food-security clarification:** Direct inspection of the three consume frames confirms prior
  completed days of **`1,899 kcal`** (A2) and **`2,155 kcal`** (A3/A4); Day 64's `225 kcal`
  was an early-morning partial-day total before the `8:02:48 AM` end (the `#998` run record
  explicitly labels it *"that day so far"*, while noting low reserves; the `"~200 kcal/day"`
  phrasing came from the initial handover note). The last consume screen displays **`234 × 127
  kcal = 29,718 kcal`** of animal cooking oil (`-25` joy raw, indefinite shelf life), `17`
  barbecue sauce (`680 kcal`) and `8` clean water (`Weight: Normal`).
- **Where curation spend went (`#1027`):** Across all **798** charged curation requests with
  retained token breakdowns (`$23.9373`, including both live windows and boundary grooming),
  **81.7% (`$19.5563`) went to prompt cache writes** (`15.65M` tokens at `$1.25/M`; **81.85%**
  across the 770 live-only priced requests), **11.7% (`$2.8057`) to cache reads** (`56.11M` at
  `$0.05/M`, 78.2% hit rate), and **6.6% (`$1.5730`) to output** (`314.6k` at `$5.00/M`).
  Alongside store growth (`current-facts.jsonl` `73 KB → 565 KB`), median text-only request-2
  spend rose **2.8×** (`$0.0402` → `$0.1120` from A1 to A4), live image-bearing requests
  accounted for **61.9%** (`$14.2455`) of live spend (`r = 0.81` with `view_frame` calls), and
  cost per net active fact rose **4.0×** from **`$0.0356`** (A1) to **`$0.1434`** (A4). Four
  `$0` offline counterfactual options (A–D) remain open for owner choice, with live parity and
  prefix/retry effects unmeasured.

[Issue #1019](https://github.com/CVX-Hull/enactive/issues/1019) ·
[Issue #1027](https://github.com/CVX-Hull/enactive/issues/1027) ·
[Outcome #387](https://github.com/CVX-Hull/enactive/issues/387) ·
[Campaign #998 run record](2026-11-26-multi-day-standard-build-campaign-998.md) ·
[Attempts ledger](../../data/evaluation/coding-agent-attempts.jsonl)

---

## Method and evidence limits

1. **Primary sources verified:** All recomputed spend totals, store/grooming counts, delivery
   and read tables, and token breakdowns were derived directly from the four sealed `#998`
   admission directories (`run/curator-runner/`, `knowledge/cdda/cdda`,
   `knowledge/cdda/cdda.state/`, `grooming/`, `run/actors/001/host.jsonl`, `run/receipt.json`,
   `run/sources/*.png`) and `multi-day-standard-build-998-campaign` (`scripts/after_admission.sh`,
   `operator-note.md`), with one-off calculation methods documented in the sealed verification
   report (`verification-explorers/out-codex-cost-and-audit/reply.md`). SHA-256 verification
   covered 3,715 inspected files against the sealed manifests. Three figures carried forward
   from the initial handover reports—the qualitative `28`-call action-linked count, the single
   `v97` retrieval rank (`18th`) for `wilderness-default-calendar`, and the `~101`-call
   keyword estimate for start-clock hunting—are explicitly identified as handover results at
   their points of use.
2. **Visual audit completion:** The initial handover audit judged 34 of 40 sampled facts
   (`random.seed(998)`: 8 each of `interface`, `mechanic`, `entity_property`, `instance_state`,
   plus all 8 `strategy` facts, opening up to the first 4 citations per fact) and 7 expiry
   cases. A multimodal explorer directly inspected all 42 PNGs needed to judge the remaining 6
   sampled facts (`#8`–`#13`), verify the 3 consume/calorie screens, and check 3 additional
   world facts against the day-64 `8:02 AM` end frames.
3. **Limits (what is not established):**
   - **No reasoning text retained:** Neither player (`host.jsonl` `content_bytes == 0`, reasoning
     text omitted) nor curator (`host-output.log` keeps tool-call metadata and usage only)
     retains model reasoning prose. The handover classification of 28/126 player knowledge calls
     as action-linked (`17` acted-on + `11` verified-then-acted) therefore rests on one-line tool
     intents and subsequent operations, not verified causal attribution.
   - **Citations beyond the first 4:** For 10 of the 40 sampled facts (`#7`, `#11`, `#15`, `#25`,
     `#26`, `#30`, `#31`, `#32`, `#34`, `#39`), citations past the fourth frame were not opened;
     claims resting only on those frames are marked unverified rather than wrong.
   - **One interrupted token split & file-level token attribution:** A4's interrupted request 4
     (`$0.02260720`) settled at the proxy without a `request-end` token breakdown, and
     `host-output.log` logs `read_file` response bytes without file-path arguments (so store
     reads are size-fingerprinted against reconstructed `current-facts.jsonl` and tested history
     sizes, where unnamed files could share a size).

---

## 1. Spend reconciliation (`#1019` open check 2)

Joining runner attempts in `examined.jsonl` against every session directory's
`proxy-ledger.jsonl` (`charged`) and `proxy-close.json` (`spent_snapshot_usd`), grooming
summaries (`grooming/grooming-summary.json`), and player receipts (`run/receipt.json` +
`host.jsonl` `response-complete.counted_cost_usd`) reconciles every penny:

| Admission | Published live | Interrupted live | Spend-cap-refused live | All live | Boundary grooming | Player requests | Recall requests | All spend |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A1 | `$5.6276` | `$0.0000` | `$0.0000` | `$5.6276` | `$0.1582` | `$3.4442` | `$0.0891` | `$9.3190` |
| A2 | `$6.7327` | `$0.0000` | `$0.0000` | `$6.7327` | `$0.1869` | `$3.3101` | `$0.1959` | `$10.4256` |
| A3 | `$7.2031` | `$0.0000` | `$1.0096` | `$8.2127` | `$0.3316` | `$3.5154` | `$0.0104` | `$12.0701` |
| A4 | `$2.1799` | `$0.2583` | `$0.0000` | `$2.4382` | `$0.2720` | `$0.9136` | `$0.0122` | `$3.6360` |
| **Total** | **`$21.7433`** | **`$0.2583`** | **`$1.0096`** | **`$23.0112`** | **`$0.9487`** | **`$11.1833`** | **`$0.3076`** | **`$35.4508`** |

- **`$22.75` vs. `$23.01`:** The 92 live attempts that wrote a `summary.json` (82 published +
  10 A3 refused) sum to **`$22.75292225`**. Adding A4's interrupted session
  `001-154-179-fad75a16` (`$0.25827860` across four settled proxy charges in
  `proxy-ledger.jsonl`, with no `summary.json`) yields **`$23.01120085`**, matching the
  [campaign run record](2026-11-26-multi-day-standard-build-campaign-998.md#the-four-admissions)
  (`after_admission.sh` sums `proxy-close.json` `spent_snapshot_usd`).
- **`$23.70` vs. `$23.96`:** Adding the four boundary grooming sessions (`$0.94872080`) to
  `$22.75292225` produced the handover's `$23.70`; including A4's interrupted live window gives
  **`$23.95992165`** for all curation.
- **Play and recall (`$11.4909`):** `2,504` player requests (`$11.1833`) + `108` billed recall
  requests (`$0.3076`; split `30 / 70 / 4 / 4` across A1–A4), matching `run/receipt.json`
  (`spend_complete: true`, zero unpriced requests).

---

## 2. Sealed knowledge store, grooming and delivery (`#1019` verified baseline)

### Store composition and chronology growth

From the sealed Git tags `v0`–`v101` (102 commits in one chain; 101 `published` gate verdicts
with empty diagnostics: 95 live versions + 6 grooming versions):

| Active v101 facts | World-bound | General | Total |
| --- | ---: | ---: | ---: |
| `instance_state` | 111 | 0 | 111 |
| `interface` | 0 | 87 | 87 |
| `entity_property` | 0 | 71 | 71 |
| `mechanic` | 0 | 59 | 59 |
| `strategy` | 0 | 8 | 8 |
| **Total active** | **111** | **225** | **336** |
| `evidence_basis: observed` / `inferred` | 111 / 0 | 221 / 4 | 332 / 4 |
| `when` non-null (`when.requires == {}`) | 0 (0) | 128 (128) | 128 (128) |
| `valid_to` non-null (active rows) | 0 | 0 | 0 |

- **Ending/retirement:** Across all 341 fact rows, only **3** ever ended (`lifecycle_state:
  ended`, non-null `valid_to`): `campground-rowan-sewing-kit` (v3),
  `rowan-eastern-table-supplies` (v7) and `rowan-campground-luxury-rv` (v12). One row is
  `superseded` and one `retracted`.
- **Boundary grooming:** Byte-for-byte comparison across `v37→v38`, `v67→v68`, `v91→v94` and
  `v100→v101` confirms **0 fact rows added, edited or retired** across all four grooming
  sessions (active counts unchanged at `158`, `255`, `319`, `336`). Grooming only filed facts
  into articles, revised leads and consolidated article prose.
- **Chronology growth (`rowan-campground-spawn`):** Grew across the snapshots shown from
  **11 blocks / 3,416 UTF-8 bytes** at v10 → **46 / 15,643 B** (v37) → **78 / 30,758 B** (v67)
  → **102 / 44,894 B** (v91) → **109 blocks / 49,003 UTF-8 bytes** at v101 (49,015 B when
  ASCII-escaped as in the handover; one intermediate A1 edit at `v17→v18` briefly trimmed 11
  bytes from 6,566 B to 6,555 B at 22 blocks), with **103/111 (92.8%)** of active world facts
  cited exclusively by this one article (the other 8 are also cited by `rowan-campground-water`).

### Post-cut delivery, recalls, reads and citation errors

| Admission | Actual cuts | Delivered updates (total / paired with briefing / empty) | Recall events (selected / silence / all-delivered / empty) | Knowledge calls (reads / queries) | Read text bytes | Query text bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A1 | 26 | 26 / 26 / 25 | 14 / 16 / 33 / 5 | 34 / 8 | 188,534 | 35,917 |
| A2 | 28 | 28 / 27 / 26 | 1 / 69 / 3 / 0 | 27 / 6 | 525,460 | 28,649 |
| A3 | 21 | 22 / 21 / 21 | 1 / 3 / 58 / 0 | 26 / 7 | 747,422 | 33,612 |
| A4 | 6 | 6 / 6 / 6 | 1 / 3 / 14 / 0 | 14 / 4 | 305,910 | 18,663 |
| **Total** | **81** | **82 / 80 / 78** | **17 / 91 / 108 / 5** | **101 / 25** | **1,767,326** | **116,841** |

- **Empty updates & silent recalls:** `80/82` updates shared their request with a context-cut
  briefing and `78/82` were empty (`v6` and `v39` added unfiled facts; unpaired `v40` and `v91`
  listed updated articles). After A1's 14 mid-run selections, A2–A4 had only 1 opening-briefing
  selection each, followed by `75` billed mid-run requests returning `silence` and `75`
  `all-delivered` events (no request made).
- **Chronology reread dominance:** The `101` `player_knowledge_read` calls returned `1,767,326`
  UTF-8 text bytes (`1.69 MiB`; `1,821,199` bytes / `1.82 MB` as compact JSON result objects;
  `1,884,167` text bytes including queries). `rowan-campground-spawn` alone accounted for
  **`1,648,865` text bytes (93.3% of read text)** across 65 reads.
- **Cross-admission citation failures:** Exactly **2** `Unknown retained source` errors occurred
  (both in A4: request 80 citing A3 frame `f0e2…-20183` and request 207 citing A1 frame
  `088b…-1558`; both PNGs exist in the earlier admissions' sealed evidence).
- **Knowledge-call utility limit (`#1019` open check 4):** The handover classified 28/126 calls
  as action-linked (`17` acted-on + `11` verified-then-acted), `84` re-orientation/report, and
  `14` nothing traceable. A mechanical check finds **69/126** calls (`24 / 19 / 17 / 9`) whose
  next logged tool start was `computer_input` (adjacency only). Because model reasoning text is
  unretained, neither figure proves causal action change; the 28-call count remains a
  qualitative intent estimate.

---

## 3. Frame accuracy, expiry and food-security checks (`#1019` open checks 1 & 3)

### Complete 40/40 sampled-fact accuracy audit (`random.seed(998)`)

Combining the 34 individual verdict rows judged in the handover audit (**29 S, 5 P, 0 U** —
correcting the handover's summary subtotal, which counted only two of its three mechanic rows
`#14 S`, `#15 S`, `#16 P`) with the 6 previously unjudged facts (`#8`–`#13`, judged directly
from their PNGs in this review: **3 S, 3 P, 0 U**) completes the 40-fact sample (first four
citations opened per fact) with **zero wrong numbers**:

| # | Fact ID (`claim_kind`) | Verdict | Key direct PNG verification & gaps |
| --- | --- | --- | --- |
| #8 | `hauling-select-wood-leave-other-scrap` (`interface`) | **P** | `a697…-5590/5646/5651/5763` verify menu, `p` selector, wood drops and left-behind scrap/bolts; confirm key **`Enter`** and intermediate populated list not shown. |
| #9 | `purged-gastropods-rv-preparation` (`mechanic`) | **S** | `f91a…-19720/19863/19873/19919` verify 22-min estimate, boiling 1, 400-charge hotplate, missing Forager Cooking, crafting 2 onto table (actual 20m 01s). |
| #10 | `fishing-rod-nearby-planks-not-stick` (`mechanic`, `inferred`) | **S** | `a697…-5806/6170/6175` verify 2 planks at `1 E`, rod recipe missing `1 stick` (no plank substitute), `36 short cordage (have 1)` red, `1 improvised fishing hook (have 1)` green. |
| #11 | `sauteed-fiddleheads-rv-craft-success` (`mechanic`) | **S** *(first 4)* | `f0e2…-17684/17685/17917/18006` verify 175-charge hotplate, 136–185 kcal range, Enjoyability 5, crafting on ground; eating, exact `163 kcal` and later underpowered decline rest on unopened citations 5–8 (`unverified`). |
| #12 | `rv-wait-frozen-food-thawed` (`mechanic`) | **P** | `088b…-14797/15359/15390/15392` verify frozen → cold canned chicken & Pinot noir and eating; **`"around noon"`** and **`"three-hour wait"`** not visible in the 4 frames, and `14797` is in a building interior. |
| #13 | `campground-bench-smash-wood-salvage` (`mechanic`) | **P** | `a697…-5373/5416/5531/5588` verify `[Y]es/[N]o` prompt, destroyed bench tile and 2 planks / 4 splintered wood / 5 nut & bolt / 17 scrap metal; key sequence **`s then .`** not shown. |

**Full 40/40 sample totals (first four citations opened per fact):** `interface` **4 S, 4 P,
0 U** (`8/8`); `mechanic` **5 S, 3 P, 0 U** (`8/8`); `entity_property` **8 S, 0 P, 0 U**
(`8/8`); `instance_state` **8 S, 0 P, 0 U** (`8/8`); `strategy` **7 S, 1 P, 0 U** (`8/8`) —
**Total: 32 S, 8 P, 0 U** (0 unsupported/wrong; 10 of the 40 facts have unopened citations
beyond the fourth frame).

### 10 world facts checked for evidence of change before campaign end

Combining the 7 handover checks (several judged against interim frames) with 3 additional
day-62–64 world facts checked directly against Admission 4's final frames (`a697…-7668` and
`8093`–`8559`; note the `0%` battery reading is from `6:10 AM` in `1724` and vehicle inspection
is not reopened before `8:02:48 AM`):

| Fact ID | Stated state | Later / Day-64 evidence | Still true before end? |
| --- | --- | --- | --- |
| `rowan-starting-water-frozen` (#28) | Bottle water frozen (day 61) | `22921` (day 62): liquid clean water | **No** |
| `rowan-day-62-existing-fire-ring` (#29) | 5 twigs in fire ring | `3151` lit; `10601` wood ashes only | **No** |
| `rowan-day-63-oil-sandwich-and-acorn-requirement` (#32) | 235 oil, 7 water | `22537`: 234 oil, 3 water; `7668`: 8 clean water | **No** |
| `rowan-day-63-afternoon-fern-harvest` (#25) | 2 sandwiches, 5 water | `22537`: 1 sandwich, 3 water; `7668`: 0 sandwiches, 8 water | **No** |
| `rowan-day-62-oil-drop-and-supplies` *(added)* | Day 62 supply snapshot (23 bread, 5 hot dogs, 2 broth, 32 sauce, 240 oil) followed by dropping the oil gallon jug SW of RV | `a697…-7668`: 0 bread/hot dogs/broth, 17 sauce, 234 oil in inventory, 8 clean water; `8093`–`8458`: SW dirt empty, carried weight `29.3 lb` | **No** |
| `rowan-day-63-rv-two-water-and-scan` *(added)* | Digging stick 4 NW of RV, RV hotplate available, 2 toilet water | `a697…-8093`–`8458`: NW grass tile empty; `1724` (6:10 AM): RV battery `0%`; `7668`: 8 clean water *(long pointy stick still wielded)* | **No** |
| `rowan-day-62-afternoon-shallow-water-pending` (#30) | Plastic bottle filled with 2 water | `23220` (day 62): plastic bottle shows `0.50 L` storage | **Probably no** |
| `rowan-rv-access-and-condition` (#27) | RV fuel `17%`, battery `12%` | `a697…-8180`–`8458`: fuel `17%`; `1724` (6:10 AM): battery `0%` | **Partial (fuel yes; battery No at 6:10 AM)** |
| `rowan-day-62-ring-fire-road` (#31) | Toilet holds 22 water | `25649`: a toilet shows 19 water (tile identity unclear) | **Unresolved** |
| `rowan-day-64-rv-power-six-ten` *(added)* | Day 64 `6:10 AM`: `0%` battery, `+41 W`, `0.3%/h`, `17%` diesel | `a697…-8180`–`8458`: `Fuel: 17 %` confirmed; vehicle battery screen not reopened after `1724` | **Unresolved (fuel yes; battery unobserved)** |

Across the 10 checked world facts, **6** no longer held, **1** had a partial change (RV
battery dropped while fuel held), **1** probably changed, and **2** were unresolved; all 10
remained `active` with `valid_to: null` and no `when` field.

### Food-security clarification (`#1019` open check 3)

Direct inspection of the three consume modal PNGs clarifies the food-security discussion across
the [campaign run record](2026-11-26-multi-day-standard-build-campaign-998.md) (which explicitly
notes day 64's `225 kcal` as *"that day so far"* while repeating the player's low-reserve
assessment) and the handover's `"~200 kcal per day"` framing:

| Frame (Admission) | `Yesterday:` kcal | `Today:` kcal (partial day) | `Weight:` / Hunger | Key carried food & water visible |
| --- | ---: | ---: | --- | --- |
| `f91a…-25218` (A2) | `1899 kcal` | `320 kcal` | `Overweight` / blank | `11 bread` (`330 kcal`), `17 barbecue sauce` (`680 kcal`), `acorns`, `snail`, `4 clean water` |
| `f0e2…-31302` (A3) | `2155 kcal` | `153 kcal` | `Overweight` / blank | **`234 animal cooking oil`** (`+127 kcal`, `-25` joy, `-1` quench, indefinite), `17 barbecue sauce`, `acorns`, `snail`, `4 bee balm`, `8 clean water` |
| `a697…-7668` (A4, before `8:02:48 AM` end) | `2155 kcal` | `225 kcal` | `Normal` / blank | **`234 animal cooking oil` (`29,718 kcal`)**, `17 barbecue sauce` (`680 kcal`), `acorns`, `snail`, `4 bee balm`, `8 clean water` |

Full prior-day intakes were `1,899 kcal` and `2,155 kcal`, and day 64's `225 kcal` is an
early-morning partial-day counter before the `8:02:48 AM` save. On the last displayed consume
menu, earlier ready-to-eat staples (bread, hot dogs, broth) no longer appeared and raw oil
carries a `-25` joy penalty per portion, but Rowan finished at `Weight: Normal` with
`29,718 kcal` of non-perishable oil and `8` portions of clean water on hand.

---

## 4. Curation offline cost breakdown and counterfactuals (`#1027`)

### Sessions, tokens and exact price decomposition

Across all **93 live attempts** (`82` published, `1` interrupted, `10` spend-cap refused;
`6,036.9 s` summed elapsed time, `781` request attempts, `771` charged) and **4 boundary
grooming sessions** (`255.6 s`, `28` charged requests):

| Population | Input tokens | Uncached | Cached input | Cache-write input | Output tokens | Cache hit | Spend |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A1 live (`26` pub) | 16,217,766 | 888 | 12,679,222 | 3,537,656 | 114,130 | 78.18% | `$5.6276` |
| A2 live (`28` pub) | 23,059,538 | 693 | 18,773,767 | 4,285,078 | 87,389 | 81.41% | `$6.7327` |
| A3 live (`22` pub + `10` ref) | 22,433,127 | 570 | 16,834,093 | 5,598,464 | 74,475 | 75.04% | `$8.2127` |
| A4 live (`6` pub + `1` int*) | 6,756,708 | 159 | 5,125,466 | 1,631,083 | 24,067 | 75.86% | `$2.4382` |
| **Live total** | **68,467,139** | **2,310** | **53,412,548** | **15,052,281** | **300,061** | **78.01%** | **`$23.0112`** |
| All 4 grooming | 3,294,072 | 84 | 2,701,261 | 592,727 | 14,533 | 82.00% | `$0.9487` |
| **All curation** | **71,761,211** | **2,394** | **56,113,809** | **15,645,008** | **314,594** | **78.20%** | **`$23.9599`** |

*\*Token columns cover the 798 charged curation requests with retained `request-end` usage
(`$23.9373`: 770 live + 28 grooming); A4 interrupted `request-4` (`$0.0226`) settled at the
proxy without a token split.*

- **Exact dollar allocation (`798/799` priced curation requests including grooming, `$1.00/M`
  uncached, `$0.05/M` cache read, `$1.25/M` cache write, `$5.00/M` output):**
  - **Cache writes:** **`$19.5563` (81.7% of all priced curation; 81.85% of the 770 live-only
    priced requests)** — every new 25-step live window starts a fresh curator session and pays a
    cold cache-write burst.
  - **Cache reads:** `$2.8057` (11.7%).
  - **Output (including reasoning):** `$1.5730` (6.6%).
  - **Uncached input:** `$0.0024` (0.01%).

### Cost drivers: growing text baseline vs. `view_frame` images

- **Growing text-only baseline alongside store growth:** Reconstructed
  `knowledge/current-facts.jsonl` grew from `73,347 B` (v10) → `234,970 B` (v37) → `564,892 B`
  (v100). Against the tested store and history sizes, size fingerprinting matches `114` live
  `read_file` calls (`15.64 MB`) to the current-file size (distinct from tested history sizes;
  unnamed workspace files could still collide) and `66` (`14.38 MB`) to current/history chunks
  (out of `468` live `read_file` calls / `33.25 MB`). Across all 82 publishing windows, every
  second request carried zero images (combining store text, trace text and other tool results);
  its median charge rose **2.8×** from **`$0.0402`** (A1; median `30,311` cache-write tokens) to
  **`$0.1066`** (A2), **`$0.1100`** (A3) and **`$0.1120`** (A4; median `87,962` cache-write
  tokens).
- **Live image-bearing requests & spikes:** Across 82 publishing windows, mean spend per window
  rose by `$0.1469` from A1 (`$0.0600` text-only + `$0.1564` image-bearing = `$0.2164`) to A4
  (`$0.1260` text-only + `$0.2373` image-bearing = `$0.3633`), split `$0.0660` text-only and
  `$0.0809` image-bearing. Overall, `579` image-bearing live requests (`492` `view_frame` calls,
  `320.39 MB` decoded/tool bytes) accounted for **`$14.2455` (61.9%)** of live spend, and
  window cost correlated most strongly with `view_frame` calls (`r = 0.81`), frame bytes
  (`r = 0.80`) and request count (`r = 0.74`) vs. `read_file` bytes (`r = 0.23`).
- **Falling yield & A3 retry waste:** Across chronological publishing cohorts, mean window cost
  rose `$0.2143` (early, v0→v39) → `$0.2435` (middle, v39→v67) → `$0.3351` (late, v68→v100),
  while net active facts per published window fell from `6.08` (A1) → `3.46` (A2) → `2.91` (A3)
  → `2.83` (A4). Publishing cost per net active fact rose from **`$0.0356`** (A1) → `$0.0694`
  (A2) → `$0.1125` (A3) → **`$0.1282`** (A4), or **`$0.1434`** including A4's interrupted
  attempt. A3's 10 `spend-reservation-refused` retries burned **`$1.0096`** (`19` charged
  responses, `90.2 s`) for **0 publications**, leaving `$0.7873` unspent and 62 steps uncovered.
- **Cost per player lookup:** Live curation cost **`$0.1826`** per player knowledge call
  (`$23.0112 ÷ 126`; `$0.1902` with grooming) and **`$0.8218`** per handover-classified
  action-linked call (`÷ 28`, `$0.8557` with grooming; qualitative denominator). The 116 player
  requests emitting those 126 calls billed `$0.6259` total (`$0.0050`/call).

### `$0` offline counterfactual options for `#1027`

Baseline curation spend is **`$23.96`** (`$21.74` publishing + `$1.27` refused/interrupted +
`$0.95` grooming). Each row varies one assumption at a time using sealed `#998` arithmetic;
selection and sequencing remain open for owner choice:

| Option | Offline arithmetic on sealed `#998` baseline | Forecast curation spend | What it gives up / unmeasured effects |
| --- | --- | ---: | --- |
| **A. Cap current state near A1 size (`#1020`), keep 25-step cadence** | Cap request-2 charge in A2–A4's 56 publishing windows at A1's final-5 median (`$0.0854`), subtracting `$1.0531` observed excess. | **`$22.91`** | Models only request-2's initial burst; downstream prefix, retirement and retry effects require a live test. |
| **B1. Wider live windows (50 or 100 steps)** | Treat first 2 requests (`$7.2832` / 82 windows = `$0.0888`/window) as fixed session overhead; keep `$14.4601` remaining work; group into `41` or `22` windows + grooming (assuming failed retries clear; `$20.32` / `$18.63` if `$1.27` failed spend persists). | **`$19.05`** (50-step) / **`$17.36`** (100-step) | Exceeds current 45-step runner ceiling; increases publication lag and end-of-admission uncovered tail; assumes work per step stays flat. |
| **B2. Align live curation to context cuts (after `#1026`)** | Same fixed-overhead model at the `81` observed cuts (`$14.46 + 81 × $0.0888 + $0.95`), excluding `$1.27` failed-attempt spend (**`$23.87`** if unchanged). | **`$22.60`** (excl. failed) / **`$23.87`** (incl. failed) | Little savings at 81 vs. 82 windows unless `#1026` reduces cut frequency or decouples cuts from curator coverage. |
| **C. Boundary-only curation** | Two separate scenarios: (1) observed 4 grooming sessions alone (`$0.95`, 0 new facts); (2) fixed-work benchmark keeping `$14.46` measured publishing work + `4 × $0.0888` overhead + `$0.95` grooming (`$15.76`). | **`$0.95`** (observed grooming) / **`$15.76`** (fixed-work scenario) | Gives up all within-admission live publications; true admission-scale ingestion cost and fact yield are unmeasured (not bounded by `$15.76`). |
| **D. Smaller/cheaper curator tier on existing cadence** | Price sensitivity at unchanged usage: 50% across-the-board rate reduction (`$23.96 × 0.50`), or 50% cache-write rate reduction alone (`−$9.78`). | **`$11.98`** (all) / **`$14.18`** (cache-write) | No parity evidence on visual reading, schema validity, fact yield or cache hit rate without a benchmark/live trial. |

---

## Mapping to `#1020`–`#1027`

This record establishes the verified baseline and decides no leaf:
- [`#1020`](https://github.com/CVX-Hull/enactive/issues/1020) (current state & ending obsolete
  facts): across 10 checked world facts, 6 no longer held, 1 partially changed and 1 probably
  changed while remaining active; 3 ended total; 0 grooming fact edits; `rowan-campground-spawn`
  reached 109 blocks / 49 KB.
- [`#1021`](https://github.com/CVX-Hull/enactive/issues/1021) (anchoring in time & place):
  moment-relative wording, unstated scan positions, repeating landmarks and missing game-time
  data field (handover store audit).
- [`#1022`](https://github.com/CVX-Hull/enactive/issues/1022) (conditions, confidence &
  `claim_kind`): 128/128 `when.requires == {}`, 332/336 `observed`, uniform `Recheck...`
  boilerplate, `claim_kind` bleed seen in `#13` and `#14`.
- [`#1023`](https://github.com/CVX-Hull/enactive/issues/1023) (findability & retrieval): 103/111
  world facts cited only in chronology; `wilderness-default-calendar` ranked 18th in the
  handover `v97` query replay.
- [`#1024`](https://github.com/CVX-Hull/enactive/issues/1024) (derived syntheses & lessons):
  only 8 `strategy` and 4 `inferred` facts; oil reserve (`29,718 kcal`) and cordage gap
  unsynthesized.
- [`#1025`](https://github.com/CVX-Hull/enactive/issues/1025) (post-cut delivery & citations):
  78/82 empty updates, 0 mid-run recall selections in A2–A4 (`75` silent billed requests + `75`
  `all-delivered`), 2 cross-admission `Unknown retained source` errors.
- [`#1026`](https://github.com/CVX-Hull/enactive/issues/1026) (working state across cuts): 81
  cuts; 65 reads of chronology (`1.65 MB`, 93.3% of read text); ~101 tool calls chasing start
  time (handover keyword estimate).
- [`#1027`](https://github.com/CVX-Hull/enactive/issues/1027) (curation cost): `$23.96` total
  curation (`81.7%` cache writes across 798 priced requests; `81.85%` live-only), 4×
  cost-per-fact rise (`$0.0356`→`$0.1434`), `$1.01` A3 retry waste, and offline options A–D
  above.
