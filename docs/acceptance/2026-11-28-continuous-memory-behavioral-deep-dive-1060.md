---
owner: lead
status: historical
kind: review
date: '2026-11-28'
scope: 'Comparative behavioral deep dive across player, curated memory, delivery, context cuts, curation economics, and multi-day survival routines comparing post-wave #1060 (campaign-run/14, curator-knowledge/5, delivered-knowledge/4, player-host/13, curator-host/2, 40/60 flex, retired LLM recall) against pre-wave #998 (#1019 baseline); $0 provider spend, three delegated clean-context explorers across sealed evidence'
---

# Comparative player and memory deep dive: `#1060` vs. `#998`

## At a glance

- **Evidence basis (`$0` provider spend):** Recomputed directly from the three sealed `#1060` Lineage 2 bundles (`continuous-memory-1060-lineage2-admission-01` through `-03`, `v0 -> v39`) and the four sealed `#998` bundles (`multi-day-standard-build-998-admission-01` through `-04`, `v0 -> v101`, baseline in [`#1019`](2026-11-26-campaign-memory-review-1019.md)) by three clean-context explorers (`Claude Opus 5.5` High × 2, `GPT-6.2 Sol` Extra-high × 1), whose briefs and full reports are sealed as [`campaign-1060-comparative-deep-dive`](../../data/evidence/campaign-1060-comparative-deep-dive.sha256).
- **The post-wave store migration (`#1020`–`#1027`, `#1055`) solved `#998`'s core store pathologies:**
  - **Fact retirement jumped `0.9% -> 41.6%`** (`3/341` in `#998` vs. `101/243` in `#1060`), with `0` duplicate active `state_key` readings across `52` keys, `0` frameless `state` facts, `18/20` sampled active facts fully supported (`2/20` partial, **`0/20` wrong**), and stale active world facts dropping from `6/10` (`#998`) to `1/7` (`#1060`, excluding the uncovered tail).
  - **Chronology bloat disappeared:** Largest article in `#1060` is `2,900 B` / `3` blocks vs. `#998`'s `49,003 B` / `109` blocks (`rowan-campground-spawn`); A03's `14` player reads returned `25 KB` total vs. `1.77 MB` across `#998`'s `101` reads.
  - **The `93.8%` curation cost drop (`$23.96 -> $1.49`) was mostly structural, not just `flex`:** Even at `default` tier prices, `#1060` would have cost `$2.97` (**`-87.6%`** vs. `#998`). Targeted workspace reads decoupled window cost from store size (`facts.jsonl` grew `5.8×` while window cost grew `22%`; cache-write share fell `81.7% -> 54.4%`; cache-hit rate rose `78.2% -> 88.0%`).
- **Retiring LLM recall (`#1025`) worked cleanly and shifted retrieval to active search, with two measurable visibility limits:**
  - **Zero empty updates:** All `23/23` covered cuts carried non-empty `changes_since` diffs (vs. `#998`'s `78/82` empty version updates); active querying rose **`4.35×` per decision** (`1.14 -> 4.95` / 100 decisions), full reads dropped `32%` (`4.60 -> 3.13`), and all `4` `player_hint` calls (`0` in `#998`) reached the live curator and produced matching published facts.
  - **Visibility limits:** `14/49` (`29%`) of queries were rephrasings of the start-clock lookup (because `player_agenda` was unused and the observed start clock lived in an ended reading); the `24`-fact briefing index cap hid `83/115` (`72%`) of top-level records by `v37`; and one cut-delta (`v34 -> v36` at A03 `request-386`) overflowed the `10,000`-char cut-marker cap, omitting `2` rows of `water-purification-tablets`.
  - **Why `host.large_rewrite_share` doubled (`8.5% -> 16.1%`) while `$/decision` stayed flat (`$0.00523 -> $0.00531`, `+1.5%`):** **All `19/19` large rewrites (`>30k` cache-write tokens) came from image-block evictions *between* cuts (`host.mjs:162`, at 40 or 60 images), not from cuts (`13k–28k` tokens).** Wider `40/60` curator windows let segments cross image-block boundaries before coverage arrived, while retiring `$0.000140/dec` of recall absorbed almost the entire cache-write increase.
- **Forensics of Rowan Vale's death (A03, `requests 403–426`) and four corrections to [`#1060`'s merged run record](2026-11-28-fresh-world-continuous-memory-campaign-1060.md):**
  - Head damage began 14 hours earlier (day 63 `6:39 AM`, `HEAD` dropped to `||||\` and was never rechecked). Rowan slept at `8:30 PM` in **Clear, Comfortable** weather (drizzle came overnight), declined the sleep alarm because the A02/A03 prompt's `"natural sleep"` wording was interpreted as `"no alarm"`, and pressed `C` (`"continue and don't ask again"`) at `11:00 PM` when `"You feel your head getting chilly"` fired. On waking at `4:41 AM` (`HEAD .....`), the player started the heater, **checked `@` (`request-418`) and compared pre-sleep frame `-18988` via `player_source` (`request-421`)**, saw `||||\` → `.....`, and still sent `| w 3 I` (5-min wait pre-typing `I` to auto-ignore the freezing warning), guided by heater records that only showed full-HP 30–90 min rewarming with zero cold-HP-drain warnings and zero cold/shelter/health articles.
  - **Ballot 11 (`wait` batches `19.8%`) is benign:** `#998` already had `15.8%` (`351/2,217`, `32.5%` in A01); `~185/196` waits in `#1060` let long activities run (only `5–8` were true screen-settle waits). Do not reopen Ballot 11 (`settle`); address wait-until-done and hazard-stop monitoring in `#177`/`#996`.
  - **Four factual corrections to the merged `#1060` record** (recorded here per [historical-pages-metadata-may-be-fixed-content-never](../decisions/owner-decisions.md#historical-pages-metadata-may-be-fixed-content-never)): (1) `#1060`'s `4` retracted facts mostly reflect grooming link/dependency repairs (`6/7` replacements copied identical text, and grooming wrongly retired the valid safety fact `brazier-wait-wet-cold-outcome` at `v38`), overstating `#677`'s genuine belief-revision corpus; (2) A02 `request-459` **did** carry an explicit 250-byte `player_handoff` host notice (`host.mjs:1367`, SHA-256 verified), contradicting `"with no prompt nudge"`; (3) A03 slept in Clear, Comfortable weather (not `"during cold drizzle"`) and checked `@` + `-18988` before waiting (not `"without first checking medical status"`); (4) interleaved hygiene had **four** blockers, adding `min_windows: 5` and per-request default-tier proxy reservations (`$0.143–$0.212`, `38–48×` median charge) to the two blockers named in `#1060`.

[Campaign `#1060` record](2026-11-28-fresh-world-continuous-memory-campaign-1060.md) · [Baseline `#1019` memory review](2026-11-26-campaign-memory-review-1019.md) · [Campaign `#998` record](2026-11-26-multi-day-standard-build-campaign-998.md) · [Hygiene leaf `#1068`](https://github.com/CVX-Hull/enactive/issues/1068) · [Parent `#387`](https://github.com/CVX-Hull/enactive/issues/387) · [Programs `#177`](https://github.com/CVX-Hull/enactive/issues/177) · [Recurrence `#666`](https://github.com/CVX-Hull/enactive/issues/666) · [Pause/Resume `#1057`](https://github.com/CVX-Hull/enactive/issues/1057)

---

## 1. Curated memory store and `40/60` `flex` economics (`#998` vs. `#1060`)

### Store lifecycle, structure, and grounding

| Metric | `#998` (`curator-knowledge/4`, `v101`) | `#1060` (`curator-knowledge/5`, `v39`) | Shift |
| --- | ---: | ---: | --- |
| Total facts / articles | `341` facts (active `336`) / articles incl. chronology | `243` facts (active `131`) / `14` article versions (`9` active) | Cleaner compact active store (`140` active total, `171.6 KB`) |
| Ended facts | `3 / 341` (`0.9%`) | `101 / 243` (`41.6%`: `81` `state`, `20` `synthesis`) | `state_key` + `changed` transitions ended stale state |
| Duplicate active `state_key` | *(no `state_key`)* | `0` across `52` distinct keys (`25` multi-reading chains) | `rowan-vale` (`23` readings), `campground-observed-supply-summary` (`20`) |
| Largest article / fact | `49,003 B` / `109` blocks (`rowan-campground-spawn`) | `2,900 B` / `3` blocks (`water-purification-tablets@v39`); largest fact `3,819 B` (ended) | Chronology bloat eliminated; player reads `25 KB` (A03) vs. `1.77 MB` (`#998`) |
| Boilerplate `when` conditions | `128` (`when.requires == {}`) | `1` (`rock-crushes-frozen-toilet-water`) | Noise removed |
| Boundary grooming fact edits | `0` across 4 passes | `7` fact replacements + `1` retirement across 3 passes | Active link/stale repair, with one over-aggressive retirement |
| Sampled active fact grounding | `32/40` supported, `8/40` partial, `0` wrong | `18/20` supported, `2/20` partial, `0` wrong (`random.seed(1060)`) | High grounding preserved at `40/60` `flex` |
| Stale active world states | `6 / 10` (`+2` partial/probable) | `1 / 7` (`sedan-door-open-after-exit`), `+1` uncovered tail | Dramatic stale-state reduction |

- **Grooming link-repair artifact & `#677` correction:** Across the three boundary grooming passes (`v6->v8`, `v20->v24`, `v37->v39`), `6/7` fact replacements copied the exact prior text while changing only `links` (dropping chronological `see_also` or `depends_on` on a mutable state reading; the 7th changed `"still showed"` → `"showed"`). Because changing a link mints a new ID and marks the old ID retracted/superseded, the `4` retracted facts (`brazier-wait-wet-cold-outcome`, `barn-water-tablet-recipe-unavailable`, `sedan-consume-menu-low-calorie-intake`, `gas-station-provisions-and-boiling-gap`) primarily record dependency-link cleanup rather than genuine belief revisions. `#677` protocol prep should distinguish link-modeling repairs from true empirical revisions.
- **Harmful safety-record deletion (`v38`):** Boundary grooming retired `brazier-wait-wet-cold-outcome` as `"wrong"` at `v38` solely because it had been modeled as `depends_on` a later-ended mutable fire reading — even though its cited frames (`2b837f…-5601`, `-6151`) directly confirm `Cold (head)`, `Wet (head)`, `Speed 66`, and `"Your head hurts!"`. It was the store's **only** record linking wet cold to head pain. Grooming prompts/rules should repair broken `depends_on` links without deleting valid hazard observations.
- **Uncurated tails and missing HUD vitals:** The last `16`, `23`, and `22` steps of A01–A03 fell past the live curator's cursor (`161/177`, `405/428`, `371/393`) and boundary grooming saw only cited frames plus first/last frames — so the entire fatal night never entered the store. Additionally, `0` facts in `v39` recorded HUD body-part HP bars (`HEAD`, `TORSO`, limbs), even though every HUD frame displays them.

### Curation token & cost decomposition (`#1027` comparison)

All `300/300` `#1060` curator and grooming requests repriced at exact `0.5000×` default rates (`0` mismatches, `0` long-prompt charges):

| Population | Spend | Cache writes | Cache reads | Output | Uncached | Cache hit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `#1060` Live (`247` reqs, `23` windows) | `$1.2946` | `55.6%` | `14.7%` | `29.6%` | `0.03%` | `86.89%` |
| `#1060` Grooming (`53` reqs, `3` passes) | `$0.1920` | `46.2%` | `24.1%` | `29.7%` | `0.04%` | `92.86%` |
| **All `#1060` (`300` reqs)** | **`$1.4866`** | **`54.4%`** (`$0.8082`) | **`15.9%`** (`$0.2371`) | **`29.7%`** (`$0.4408`) | **`0.03%`** | **`87.99%`** |
| `#998` baseline (`#1019`, `798` reqs) | `$23.96` | `81.7%` (`$19.56`) | `11.7%` (`$2.81`) | `6.6%` (`$1.57`) | `0.01%` | `78.20%` |

- **Store-size decoupling:** While `facts.jsonl` grew `5.8×` (`60.6 KB` at `v6` → `351.9 KB` at `v37`), mean live window cost rose only `22%` (`$0.0514` A01 → `$0.0525` A02 → `$0.0627` A03) and first-request prompt stayed flat at `5.7k–6.8k` tokens because the store is queried on demand rather than dumped into the prompt. Cost per net active fact dropped to **`$0.01135`** (`$0.0227` at default rates) vs. `#998`'s `$0.0356 → $0.1434`.
- **Structural vs. tier share:** Even repriced at `default` tier, `#1060` curation would cost `$2.97` (**`-87.6%`** vs. `#998`); `flex` halves `$2.97 → $1.49` (`-93.8%` total).
- **Sampling-density trade-off (noted, not causally tested):** `#1060` viewed `99` frames across `937` covered steps (`1` per `9.5` steps) vs. `~1` per `4.2` steps in `#998`, which may skip intermediate transitions on dense stretches.

### Interleaved hygiene: four blockers and `#1068` recalibration inputs

Replaying every poll in `polls.jsonl` against `live_runner.py:249-251,333-369` and `runner.py:818-847` identified **four** coupled blockers:

1. **Spend-share vs. `min_headroom`:** `min_headroom()` reserves `1,024 × $1.25/M + 16,384 × $5.00/M = $0.0832` (default prices), requiring `$0.832` within-admission curator spend under `10%` share; admissions peaked at `$0.2056`, `$0.5246`, and `$0.5643` (max hygiene cap `$0.0564`).
2. **Backlog ceiling (`max_unexamined_steps: 10`):** At `6.42–6.47 s`/step player pace and `50–134 s` `flex` windows, first-poll backlogs after each window were `[14, 13, 11, 14, 12, 9, 10, 13, 11, 12]` (A02) and `[16, 14, 13, 11, 14, 24, 17, 22, 11]` (A03) — qualifying on only `2/77` A02 and `0/48` A03 post-window-5 polls.
3. **`min_windows: 5`:** A01 ran only `4` windows and could never qualify.
4. **Per-request default-tier proxy reservations (`$0.143–$0.212`, `38–48×` median charge):** Lowering `min_headroom` alone would let hygiene start and then fail mid-pass on proxy reservation refusals.

**Concrete `#1068` recalibration targets:** (a) base hygiene budget on `cap × share` (`$0.45`) or `max($0.20, spent × share)` capped at `$0.30`/pass (actual grooming passes cost `$0.029–$0.094`); (b) add a hygiene-specific `max_output_tokens` of `6,144–8,192` (max observed across 300 requests was `4,935`, `p99 = 4,052`) and compute `min_headroom` from a realistic text-only prompt size; (c) raise `max_unexamined_steps` to `20–25` (`10/10` A02 and `7/9–9/9` A03 post-window polls qualify while staying below `trigger_steps: 40`); (d) lower `min_windows` to `3`; (e) for `#1058` S1 (`60 s` wall cap — `15/23` live windows overall exceeded `60 s`, and text-only grooming reached request 10 at `36.2 s` A02 / `56.3 s` A03), raise `hygiene.wall_seconds` to `120–150` (`90–120 s` host wall) or reduce `max_requests` to `8`.

---

## 2. Player delivery, retrieval, unused tools, and context-cut economics

### Retiring LLM recall (`#1025`): delivery and retrieval shift

| Cohort | Decisions | Queries | Reads | Queries / 100 dec | Reads / 100 dec | Query + read / 100 | `player_hint` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `#998` A01–A04 (`player-host/12`, LLM recall) | `2,197` | `25` | `101` | `1.14` | `4.60` | `5.74` | `0` |
| `#1060` L2 A01 (`player-host/13`, no recall) | `170` | `2` | `1` | `1.18` | `0.59` | `1.76` | `0` |
| `#1060` L2 A02 | `427` | `22` | `16` | `5.15` | `3.75` | `8.90` | `3` |
| `#1060` L2 A03 | `392` | `25` | `14` | `6.38` | `3.57` | `9.95` | `1` |
| **`#1060` L2 total** | **`989`** | **`49`** | **`31`** | **`4.95`** (`4.35×`) | **`3.13`** (`-32%`) | **`8.09`** (`+41%`) | **`4`** |

- **Why `0` standalone mid-segment delta messages fired:** Every one of the `23` actor-visible live exports arrived with enough coverage to release an already-pending `held-back` cut (`0.6–8.3 s` after window end; `21/23` on the very first player request, `2/23` on the second). Replaying all `23` transitions through `host.mjs` confirmed **`23/23` non-empty `changes_since` diffs** riding cleanly on the cut briefings, with `0` empty-suppressed events (vs. `#998`'s `78/82` empty version updates and `91/108` silent LLM recall calls costing `$0.3076`).
- **One measurable delivery gap — cut-delta overflow:** At A03 `request-386` (`v34 -> v36`), `changes_since` exceeded the `10,000`-char cut-marker cap and silently omitted `2` rows of `water-purification-tablets` (the standalone `12,000`-char cap would have carried both). No action loss occurred here because the player had already hinted the procedure at `request-349`, but cut-delta overflow should be logged and prioritized.
- **Query and read behavior (`49/49` queries non-empty, `31/31` reads resolved):** `21/31` reads and `53/80` query/read calls were followed immediately by `computer_input` (vs. `69/126` in `#998`). **Inefficiency:** `14/49` (`29%`) of all `#1060` queries were repeated rephrasings asking for the starting clock (`9` in A02, `5` in A03), every one returning `Spring day 61, 8:00 AM` at rank 1. Meanwhile, the `24`-fact briefing index cap was binding from `v3` onward, leaving **`44/76` (`v26`) to `83/115` (`v37`, `72%`)** top-level records unlisted (including `brazier-wait-wet-cold-outcome` and `sedan-heater-warming-and-charging`).
- **All `4/4` `player_hint` calls worked end-to-end:** In every owning curator window (A02 `286–325`, `326–365`; A03 `288–329`), the live curator read `tools.jsonl`, inspected the cited frames (`14871/15319`, `16453`, `17903/17907/17915`, and A03 `349`'s three frames), and published matching facts delivered back to the player (`v18`, `v19`, `v36`).

### Diagnosis of unused tools (`0` voluntary calls)

| Tool / field | Observed calls | Diagnosed cause & distinction (friction vs. unneeded) |
| --- | ---: | --- |
| **`player_agenda`** | `0 / 1,096` | **Affordance/friction gap:** Opening and cut blocks omit the agenda entirely when `threads` is empty (`agenda.mjs:17`, `knowledge.mjs:375`), leaving no live cue beyond generic guide text; creating a thread requires a separate multi-field call. Yet the `14` repeated start-clock queries prove a real concrete need for persisting verified baseline/target/objective state across cuts. |
| **Ancestor `player_source`** | `0` (`8` same-admission reads) | **Discoverability + sufficiency:** Of `176`/`603` indexed ancestor IDs in A02/A03, `49`/`141` overlapped adopted fact citations, and only `9`/`21` distinct ancestor IDs appeared in query/read responses (briefings carry no frame IDs; article bodies cite facts rather than frames). Text sufficed for most actions, while the `8` same-admission reads (`7/8` available) showed the tool itself is used when a frame ID is visibly in hand (e.g., A03 `request-421` comparing pre-sleep `-18988`). |
| **Optional `cites`** | `0 / 1,096` (`#998`: `0 / 2,554`) | **No functional cue:** The player reliably attached `source_ids` where required (`7/7/5` on finish reports, `4/4` on hints), but never used optional per-decision `cites`. |
| **`player_handoff`** | `0` | **Host-notice vs. mission-prompt conflict (correcting `#1060` record):** A02 `request-459` (`2,703.4 s`) **did** send an explicit 250-byte host notice (`host.mjs:1367`, SHA-256 verified): *"Host time allowance: about 5 minutes remain before the host stops. Request the existing `player_handoff` with the context you need to retain (if it reports that no successor is available, use `player_finish`), or use `player_finish` if you cannot continue."* Because `"about 5 minutes"` hid the `116.6 s` `orderly_stop` reserve (`2,820 s`) while the mission prompt explicitly instructed Save to title + Quit before ending, Actor `001` treated the notice as an admission ending (`464–472`). |

### Context cuts (`#1037`) and why `host.large_rewrite_share` doubled (`8.5% -> 16.1%`)

- **All `23` cuts were covered `best_effort` cuts (`0` uncovered cuts):** Median `held-back` waits were `131.7 s` (A01), `138.7 s` (A02), and `155.5 s` (A03); gross token estimates peaked at **`87,487`** (A03 `request-68`, `>= 12,513` below the `100,000` Tier-2 uncovered ceiling; highest sent while held was `83,828` at A03 `request-295`).
- **Root cause of `large_rewrite_share` (`8.5%` `#998` -> `16.1%` `#1060`: `0% / 15.8% / 22.1%`):** `large_rewrite_share` counts requests with `>30,000` cache-write tokens. Actual cut requests in `#1060` wrote only `12,981–28,208` tokens. **Every single one of the `19` large rewrites (`8` in A02, `11` in A03, up to `41,804` cache-write tokens) occurred on an image-block eviction at 40 or 60 images (`host.mjs:162`) *while waiting for `40/60` coverage to release a cut*.**
- **Net cost impact was near zero (`+1.5%`):** Across cohorts, player+recall spend per decision moved from `$0.005230` (`#998`) to `$0.005308` (`#1060`). Higher cache writes (`+$0.000142/dec`) and reads (`+$0.000128/dec`) were nearly offset by retiring recall (`-$0.000140/dec`) and lower output (`-$0.000052/dec`), while prompt cache-read share remained `94.2–94.6%`.

---

## 3. Gameplay forensics, fatal cold episode, and multi-day routine friction

### Forensic timeline of Rowan Vale's death (A03, `requests 84–105` & `403–426`)

1. **Unhealed head injury (`14 h` earlier, day 63 `6:39:06 AM`):** Auto-travelling in rain while `Very cold!` triggered `"You were hurt! Cancel auto move?"` and `"Your head hurts!"` (`0b3243…-4795.png`). Reading the heater/brazier records (`requests 85–88`) led to a successful rewarm in the eastern sedan (`Comfortable` by `7:12:52 AM`, `-6283.png`), **but `HEAD` remained damaged at `||||\` all day** (`-4963`, `-18664`, `-18892`, `-18988`) and was never rechecked (`request-105` inspected `@` for heat/wetness only).
2. **Three pre-sleep choices that sealed the outcome (`requests 403–409`):**
   - **Exposed sleep spot (`403–405`):** Entered the campground V6 Sports Sedan and closed one door (`-18664`, `-18755`; sprite still suggests open southern panels; overnight death log `-20673` shows wind/cold messages and `@` `-20179` shows `Damp` head/torso and `Wet` eyes). Meanwhile, `request-404` returned `restroom-floor-sleep-through-morning` (which warned of head chilling by `1:00 AM` even indoors), with no record on overnight sedan sleep.
   - **Declined alarm (`406–407`, `-18892`):** Chose `"Permit an unalarmed natural sleep"` — in both A02 (`request-364`) and A03 (`request-408`), the model interpreted the mission prompt's `"natural sleep"` wording as prohibiting an alarm.
   - **Suppressed sleep safety prompt (`408–410`):** At `8:30 PM` (`-18988`, **Clear, Comfortable** — correcting `#1060`'s `"during cold drizzle"`), chose `C` (`"continue and don't ask again"`) on the trouble-sleeping prompt (`request-409`, `-19228`) just as weather turned `Cloudy` and `"You feel your head getting chilly"` logged at `11:00 PM`. One `2 s` host wait spanned `11:00 PM → 4:41:02 AM` asleep (`-19561`: `Drizzle`, `Very cold!`, `HEAD .....` empty, `L ARM ||||.`, `R ARM |||..`, `Speed 36`).
3. **Final `3 min 57 s` (`requests 411–426`, `15` decisions, `74 s` wall time):** Started engine + heater (`411–413`, `-19770`), ate fruit leather answering `"You are freezing!"` with `N` then `I` (`ignore`, `414–417`), **checked `@` (`418`, `-20179`) and used `player_source -18988` (`421`) to compare pre-sleep `||||\` against current `.....`** (correcting `#1060`'s `"without first checking medical status"`), queried head injury (`420`, `422` — returning only the full-HP heater record and the later-retracted brazier record), and then sent `| w 3 I` (`423–425`: a 5-min wait pre-typing `I` to auto-ignore the next freezing interrupt). Died at `4:44:58 AM` (`-20444`, `-20530`; memorial: `Head: 0/85`, `"Broke his head"`, `140` damage taken, `5` healed).
4. **Role of memory:** Memory helped during the day-63 morning rescue (`85–97`), but **misled by omission** at `4:41 AM`: every heater record was a full-HP `30–90 min` success story; none of the `8` active articles at `v37` covered cold, shelter, sleep, or health; `rowan-very-cold-in-eastern-sedan` had ended and was not delivered; and no fact recorded HP-bar drain rates.

### Why `#1060` used half the decisions and play spend of `#998`, and Ballot 11 / `#177` routine loops

- **Pacing (`989` decisions / `$5.25` play for `68.77 h` vs. `#998`'s `2,197` decisions / `$11.49` for `72.05 h`):** Driven primarily by (1) tighter wall-clock cap (`3,000 s` vs. `7,200 s`, `6,285 s` vs. `16,726 s` total wall time at similar `0.157` vs. `0.131` decisions/wall s), (2) identical long-activity hours (`64.41 h` vs. `64.87 h`) with less awake hands-on play (`4.36 h` vs. `7.17 h`), and (3) purification tablets replacing boiling fires (`239` vs. `468` water decisions; `3` vs. `93` boiling intents) — which also indirectly removed the daily fire routine that kept `#998` warm alongside `#998`'s deliberate roofed-RV-bed shelter search.
- **Ballot 11 (`wait` batches `19.8%`) verdict: benign — do not reopen Ballot 11 (`settle`).** `#998` already had `15.8%` wait batches (`351/2,217`, `32.5%` in A01); `#963`'s `5.1%` was a short 1.8 h admission. In `#1060`, `~185/196` waits let long game activities run (travel `47`, timed waits/warming `24`, crafting/salvage `24`, sleep `23`, reading `22`, eating `12`, loading `9`, death/quit `4`) and only `5–8` were true screen-settle waits. Wait-until-done and hazard-stop monitoring belong in **`#177`/`#996`**, not in Ballot 11.
- **Top recurring loops informing `#177` / `#996` (share of `1,096` `#1060` calls vs. `#998`):**
  - Water (fetch, tablet treat, wait, decant via `a`): **`21.8%`** (`#998`: `18.3%`)
  - Food (forage, consume menu, recipes): **`15.7%`** (`#998`: `17.9%`)
  - Overmap travel (`m`, `W`, `Y`): **`13.2%`** (`11.2%` of batches vs. `3.7%` in `#998`; `#998` topic share `8.6%`)
  - Heat and cold (fire, heater, freezing prompts): **`12.7%`** (`#998`: `10.5%`)
  - Nearby-items scan `V`: **`9.1%`** of batches (`#998`: `5.0%`)

---

## 4. Actionable engineering & workstream takeaways

1. **Interleaved hygiene recalibration (`#1068`, `Ready`):** Address all four blockers together — decouple pass cap from `total_spent × 0.10`, add hygiene `max_output_tokens` (`6,144–8,192`) + realistic prompt headroom, raise `max_unexamined_steps` (`20–25`), lower `min_windows` (`3`), and widen `wall_seconds` (`120–150`) or lower `max_requests` (`8`) for `#1058` S1.
2. **Curator & grooming guardrails (follow-up under `#387` / `#457`):** Prevent grooming from retiring valid hazard observations as `"wrong"` when repairing `depends_on` links; ensure end-of-admission/death tails enter coverage before lineage close; consider recording critical HUD vitals/HP-bar changes.
3. **Player delivery, agenda & handoff UX (follow-up under `#387` / `#1057`):** Log `changes_since` cut-delta overflow (`v34->v36`); add a concrete start-clock/target `player_agenda` example and render an explicit empty-agenda affordance if adoption is desired; align `host-timeout` handoff notice with the driver's `orderly_stop` reserve and mission Save/Quit wording; track image-block evictions separately from cuts in cache-rewrite metrics; clarify in continuation mission prompts that sleep alarms are permitted (`"natural sleep"` ≠ `"no alarm"`).
4. **Programs & monitor (`#177` / `#996`, activated `Ready`):** Prioritize three high-frequency candidate program families surfaced directly by `#1060` + `#998`: (a) water fetch/treat/wait/decant, (b) overmap route/confirm/follow, and (c) monitored wait/rest that stops on HP or heat degradation without suppressing freezing interrupts.
5. **Research (`#681` & `#677`, activated `Ready` at `$0`):** `#1060` provides a strong second independent world with a negative/death outcome for `#681` scoping, while `#677` protocol prep must separate `#1060`'s link-repair retractions (`6/7` identical text) from genuine empirical belief revisions.
6. **Responsiveness (`#164`):** Keep Ballot 11 (`settle`), Ballot 12 (`20/992 = 2.0%`), and Ballot 13 (`8` calls, `0` zooms) deferred; `#164` remains gated on `#177`.

## Delegated explorations and limits

All three explorer starts (`Claude Opus 5.5` High `693 s`, `GPT-6.2 Sol` Extra-high `583 s`, `Claude Opus 5.5` High `435 s`) are recorded in [`data/evaluation/coding-agent-attempts.jsonl`](../../data/evaluation/coding-agent-attempts.jsonl) and sealed in [`campaign-1060-comparative-deep-dive`](../../data/evidence/campaign-1060-comparative-deep-dive.sha256). Limits: no model reasoning prose is retained; topic-loop shares use keyword heuristics; `#1060` vs. `#998` differ across world seed, admission time limit (`3,000 s` vs. `7,200 s`), cadence, schema, and host version so cross-cohort deltas are observational rather than randomized causal effects.
