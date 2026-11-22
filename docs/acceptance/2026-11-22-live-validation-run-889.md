---
owner: lead
status: historical
kind: run
date: '2026-11-22'
scope: 'Full live validation admission (#889) on main 5e3f51ad: 17/17 accepted live curator windows (v1-v17), 17/17 mid-run knowledge updates and 30 post-adoption reminders, curator-fact/4 world/game separation, post-admission boundary grooming (v17->v18), snapshot timing and close-out, player pace, cost, and delivery-aware #846 schedule replay; partial on actor handoff'
---

# Live validation admission with curator delivery and boundary grooming (#889)

## At a glance

- **Question.** On merged `main` (`5e3f51ad`, after [#886](https://github.com/CVX-Hull/enactive/issues/886), [#835](https://github.com/CVX-Hull/enactive/issues/835), [#838](https://github.com/CVX-Hull/enactive/issues/838) and [#895](https://github.com/CVX-Hull/enactive/issues/895)), do multi-window live curation, `curator-fact/4` world/game scope separation, within-admission live knowledge delivery (`live_knowledge_updates: true`), snapshot safety and store close-out, post-admission boundary grooming (`tools.curator_host.groom`), and actor handoff work together in one bounded `Wilderness / Campground / Survivor` admission — and what does the upgraded `--recorded-deliveries` schedule replay show for [#890](https://github.com/CVX-Hull/enactive/issues/890)?
- **Outcome (all live curator, delivery, scoping, snapshot, and grooming mechanisms verified; partial on actor handoff).** Launched once from clean `main` (`5e3f51ad`) under the owner's 21 November 2026 approval ([owner decision](../decisions/owner-decisions.md#live-validation-run-889-approved), session `a02d8069d0434813a41acc7009217da6`, world `Burtons Bridge`, survivor `Rowan Hale`, `labels.world: "campground-889"`):
  - **Snapshots & sealed close-out:** **94 of 94 live reads succeeded** (1 initial `refused:no-store` before store creation; max lock hold **3.31 ms** vs 2,000 ms bound; max transaction **3.00 ms** vs 1,500 ms bound; max staging **340.91 ms**). `sealed(session.sqlite3)` verified clean with an empty write-ahead log (`367` operations).
  - **Multi-window live publication (`#886` & `#835` verified in live play):** **17 of 17 consecutive 20–23-step windows accepted (`v1`–`v17`, steps 1–355 of 367, 96.7% covered)** with **0 session rejections, 0 session failures, and 0 snapshot failures**. End-of-session backlog stayed bounded (peaking at `21` at session S04 and `23` across all polls, then settling to `4–11` across S05–S17; final runner lag `11`, backlog `11`).
  - **Within-admission live delivery (`#838` verified in live play):** Starting from `--empty` (`version: null`, 45-token empty briefing), **all 17 published versions (`v1`–`v17`) were delivered mid-run** via `knowledge-delivery` (`kind: "update"`, `outcome: "delivered"`, median **3.62 s** after publication, range `0.70–10.19 s`, `6,398` approx. tokens), and recall woke up automatically after live adoption, delivering **30 reminders** (`16,903` approx. tokens) with **0 unmatched deliveries**.
  - **Post-admission boundary grooming (`#895` verified in live play):** `tools.curator_host.groom` ran one sealed session (`v17 -> v18`, 6 requests, `93.8 s`, **$0.1874**, `settled: true`, `survivors: []`). At `v18`, **118 of 118 current game-scoped facts (100%)** were cited across 31 current articles while all **13 current world-scoped facts (`world: "campground-889"`)** stayed strictly standalone (`0` cited in articles).
  - **Actor handoff (partial):** Actor `001` played the entire `$4.10` work budget (`359` evaluator decisions, `25.88` game hours, `0` retries, `0` stalls; total attempts, player spend, and wall duration are in the [run ledger](../../data/evaluation/runs.jsonl)), hit `ending_request.trigger: "spend"`, saved `Burtons Bridge` cleanly to title, and exited zero (`normal_native_exit_zero: true`) without calling `player_handoff`. Per [the `#889` proposal](2026-11-21-live-validation-run-price-proposal-889.md#why-889-needs-a-larger-work-budget-than-859--and-what-budget-cannot-guarantee), successor-actor briefing adoption across a real handoff therefore remains unverified in live play.
- **Spend (counted, complete, settled):** Player spend is recorded in the [run ledger](../../data/evaluation/runs.jsonl) (`0` unpriced player or recall requests, `spend_complete: true`; the initial aborted launch `live-validation-run-889-49964eb42a7d` is also recorded in the ledger as `incomplete` with `0` attempts and zero spend). Combined spend across play (from `runs.jsonl`), 17 live curator sessions (**`$3.0131`**, `$0.00849`/step, median `$0.1145`), and 1 boundary-grooming session (**`$0.1874`**) totalled **`$7.4788`** — well inside the `$34.00` planning ceiling (and below the `$8.16` pilot-median forecast).
- **Ordered outcome-table reading:** Reading [the `#889` ordered outcome table](2026-11-21-live-validation-run-price-proposal-889.md#ordered-outcome-table-what-each-result-changes) in strict order: row 1 (snapshots) **clear**, row 2 (WAL) **clear**, and **row 3 ("no actor handoff occurred") applies** — figures are reported with handoff marked partial. Looking through the remaining diagnostic rows for [#890](https://github.com/CVX-Hull/enactive/issues/890): pace (`8.21` dec/min, `8.46` ops/min), publication (`17/17`), backlog (bounded), live updates (`17/17`), and grooming (`v17 -> v18`) are all clear; the upgraded `--recorded-deliveries` schedule replay made **14 cuts** (`0` under 10 turns), cut `prompt_max` from `171,996` to **`50,483`** (`max(prompt - briefing) = 50,438 <= 60,000`), cut cache writes to **`0.378x`** recorded (`-62.2%`), and held back **2 requests** with **3 image drops** (all during early warm-up / session S04's `164.86 s` outlier at requests `#41`, `#61`, `#105`), followed by **12 consecutive clean steady-state cuts (requests `#125`–`#369`) with 0 held-back requests and 0 image drops**.

[Issue #889](https://github.com/CVX-Hull/enactive/issues/889) · [Price proposal #889](2026-11-21-live-validation-run-price-proposal-889.md) · [Next decision #890](https://github.com/CVX-Hull/enactive/issues/890) · [First live run #859](2026-11-21-live-curator-run-859.md) · [Curator component](../components/curator.md)

## What ran and how it ended

The package `.runtime/computer-sessions/live-validation-run-889-a02d8069d043` (`campaign-run/12`, session `a02d8069d0434813a41acc7009217da6`, source commit `5e3f51ad13f7c6b8e54b898cf671b7554253cb7b`, manifest SHA-256 `d72fd5acbc7b6c7f9505e91199a0227db3a640304ccfc1b4b897f9e31baa4af8`) was launched from the clean main checkout on 21–22 November 2026 with `.runtime/live-validation-run-889/curator-runner-config.json` (SHA-256 `8fc820007a673b72cca181cf00d81fdbe3b42548f114a60fefe4a7f3b8cbccd7`) after passing offline preflight (`tools.campaign_package --work-before-bytes 262144000 --ending-before-bytes 312475648`, `live_runner.read_config`, and keychain lookup):

```sh
.venv/bin/python -m tools.campaign_supervision \
  --run .runtime/computer-sessions/live-validation-run-889-a02d8069d043 \
  --curator-runner .runtime/live-validation-run-889/curator-runner-config.json
```

*(Operational note: an initial package `live-validation-run-889-49964eb42a7d` exited before any provider attempt because `.runtime/logs/` did not yet exist for `Cataclysm.sh`'s log redirect; its `incomplete` receipt is recorded in [`data/evaluation/runs.jsonl`](../../data/evaluation/runs.jsonl) and sealed in [`data/evidence/live-validation-run-889-aux.sha256`](../../data/evidence/live-validation-run-889-aux.sha256). `.runtime/logs/` was created, a fresh package `live-validation-run-889-a02d8069d043` was frozen and preflighted without reusing the failed package, and the approved run proceeded once.)*

**Start and frozen inputs.** Labels: `arm: "live-validation-run"`, `start: "S1"`, `scenario: "Wilderness / Campground / Survivor"`, `world: "campground-889"`, `lineage: null`, `admission: null`. Mission text (`prompt.txt`, SHA-256 `f2e09fe8…6fb8af45`) matched `#803`/`#859`; working guide (`context.txt`, SHA-256 `142e7303…08ac70fd`) was current `docs/player-guide.md` per the owner's 21 November confirmation. Delivered knowledge (`delivered-knowledge.json`, `delivered-knowledge/2`, SHA-256 `7bb85625…e5a3c`) was exported `--empty --world campground-889` with `live_knowledge_updates: true`. Player route (`player-host/9`): `openai/gpt-6.1-terra`, `medium`, pinned to OpenAI via OpenRouter, recall every 10 inputs, `spend_limit_usd: "5.50"`, `ending_reserve.usd: "1.40"`. Runner config (`curator-runner-config/1`): arm `terra`, `cap_usd: "19.00"`, `session_cap_usd: "8.00"`, `trigger_steps: 20`, `ceiling_steps: 40`, `poll_seconds: 15`, `watch_seconds: 5`, `max_output_tokens: 16384`, fresh knowledge repository under `.runtime/knowledge/live-validation-run-889/cdda`. Prior user directory (`Townsend`) was moved aside under `.runtime/bridge/game.lock` before launch and restored intact after custody closed (preserving `Burtons Bridge` in the sealed `study-userdir`).

**Supervision, gameplay, and custody (`watch-terminal.json`, `receipt.json`).** The guardian recorded `reason: "custodian_terminal"`, `terminal_coverage_verified: true`, `cleanup_verified: true`, `manifest_unchanged: true`, `custodian_receipt_unchanged: true`, and `pause_reason: null`. All five child process groups (`custodian`, `gateway`, `wake`, `viewer`, `curator_runner`) exited and were verified absent; `curator_runner` had `exited_before_teardown: false`, `returncode: 130`, and `snapshots_removed: true`. The custodian recorded `normal_native_exit_zero: true`, `native_absence_verified: true`, `deciding_hosts_quiescent: true`, and `input_authority_revoked: true`. In-world, `Rowan Hale` killed and pulped a zombie dog, treated bleeding, crafted a wooden spear, needle, fishing hook, and leather hand wraps, completed one natural sleep and wake on a van bench, hit `ending_request.trigger: "spend"` (`spend_remaining_usd: "1.30043105"`), saved `Burtons Bridge` to title (`spring day 62, 9:52:30 AM`), submitted Quit (`normal_native_exit_zero: true`), and closed cleanly with `player_finish(disposition="external_stop_complete")` (`driver.outcome: "interrupted"` from native EOF on Quit).

## Activity units and player pace

The [run ledger](../../data/evaluation/runs.jsonl) (`live-validation-run-889-a02d8069d043`) is the single tracked record of player attempts, provider-reported spend, and wall duration. The generated evaluator table below (`python -m tools.evaluate evaluate-table data/evaluation/run-metrics.jsonl --write docs/acceptance/2026-11-22-live-validation-run-889.md`) gives the headline CDDA evaluator metrics from [`data/evaluation/run-metrics.jsonl`](../../data/evaluation/run-metrics.jsonl):

<!-- evaluate-table study=889 core=2 binding=cdda:2 -->
| Run | Arm | Start | End | Game h | Decisions | Setup | Routine pace | Long activities | Out of play | Longest stall | $ / decision | Large rewrites |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| live-validation-run-889-49964eb42a7d | live-validation-run | S1 | — | — | 0 | 0 | — | 0 · 0.00 h | — | 0 | — | — |
| live-validation-run-889-a02d8069d043 | live-validation-run | S1 | custody | 25.88 | 359 | 20 | 4.0 | 12 · 24.85 h | 64% | 10 | 0.0119 | 44% |
<!-- /evaluate-table -->

Decisions, computer operations, and game time are reported separately:

| Unit | Observed | Source |
| --- | --- | --- |
| Decisions | 359 (0 retries; player/recall request breakdown in `receipt.json` and total attempts in `runs.jsonl`) | Generated evaluator table (`run-metrics.jsonl`); `receipt.json` (`runs.jsonl`) |
| Computer operations | 367 (360 `input`, 7 `observe`; step 367 Quit exited zero with no returned frame) | `harness.trace.stores.sealed(session.sqlite3)` |
| Game time | 25.88 game hours (`start_game_time` 5,212,800 to `end_game_time` 5,305,950; 12 long activities totalling 89,464 s / 24.85 h; routine pace 4.0 game s/decision; `mode.out_of_play_share` 64% with 20 setup decisions; `stall.count` 0, `stall.longest` 10) | `tools.evaluate evaluate-run` (`2-cdda-2.sqlite3`, generated table above) |

**Player pace against the fixed cutoff** (both clocks labelled separately):

| Admission | Decisions | Decisions/min (receipt elapsed) | Operations/min (first-to-last op, frozen ref) | Operations/min (receipt elapsed) |
| --- | ---: | ---: | ---: | ---: |
| **This run (`live-validation-run-889-a02d8069d043`)** | **359** | **8.21** | **8.46** | **8.39** |
| `wilderness-803-first-eligible-8a4badef08b9` (same mission) | 405 | 7.10 | 7.31 | 7.26 |
| `farm-788-equipment-return-e3da8d1f2714` | 265 | 6.88 | 7.60 | 7.42 |
| `two-wake-772-farm-58ee9279783f45ba8ffd469e1c6357b9` | 310 | 7.48 | 7.86 | 7.77 |
| *Partial live reference:* `live-curator-run-859-2cda0867c344` | *127* | *9.74* | *10.46* | *10.20* |
| **Fixed "far from" cutoff (25% below slowest reference)** | — | **< 5.16** | **< 5.48** | — |

Play was faster than all three full-run reference admissions on both clocks and cleared the fixed cutoff comfortably. One admission cannot establish that the runner did or did not slow play.

## Live curator sessions, lag, publication and delivery latency

All 17 sequential live sessions over actor `001` were accepted and published (`v1`–`v17`), leaving `12` tail operations (`356–367`, under the 20-step trigger) unexamined at close:

| Session | Window (steps) | Ver. | Dur. (s) | Reqs | Counted USD (USD/step) | Max res. / max chg (USD) | Cache share | Ops start → end (end backlog) | Pub. latency min/p50/max (s) | Delivered at req (+s after pub) |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | --- | --- | --- |
| S01 | `001` 1–20 (20) | `v1` | 63.43 | 7 | $0.063782 ($0.00319) | $0.7066 / $0.02369 | 77.4% | 20 → 38 (18) | 66.1 / 95.8 / 120.1 | `request-40` (+3.62 s) |
| S02 | `001` 21–41 (21) | `v2` | 100.50 | 19 | $0.287676 ($0.01370) | $0.9022 / $0.04264 | 64.7% | 41 → 61 (20) | 104.1 / 147.3 / 178.3 | `request-63` (+4.30 s) |
| S03 | `001` 42–64 (23) | `v3` | 93.80 | 14 | $0.183920 ($0.00800) | $0.9426 / $0.04670 | 76.2% | 64 → 77 (13) | 94.8 / 157.2 / 208.4 | `request-79` (+5.41 s) |
| S04 | `001` 65–86 (22) | `v4` | 164.86 | 32 | $0.771544 ($0.03507) | $1.0863 / $0.06580 | 60.4% | 86 → 107 (21) | 170.4 / 236.6 / 315.5 | `request-109` (+0.77 s) |
| S05 | `001` 87–109 (23) | `v5` | 58.34 | 5 | $0.082976 ($0.00361) | $0.8779 / $0.03349 | 71.0% | 109 → 116 (7) | 64.5 / 142.4 / 237.1 | `request-118` (+2.38 s) |
| S06 | `001` 110–131 (22) | `v6` | 73.31 | 11 | $0.155212 ($0.00706) | $0.9356 / $0.03536 | 78.9% | 131 → 139 (8) | 74.1 / 143.0 / 235.4 | `request-141` (+8.15 s) |
| S07 | `001` 132–151 (20) | `v7` | 45.26 | 7 | $0.081379 ($0.00407) | $0.8724 / $0.03637 | 80.8% | 151 → 156 (5) | 46.4 / 117.1 / 200.3 | `request-158` (+6.83 s) |
| S08 | `001` 152–171 (20) | `v8` | 56.94 | 7 | $0.089482 ($0.00447) | $0.8899 / $0.03763 | 80.5% | 171 → 178 (7) | 59.5 / 117.4 / 202.3 | `request-180` (+2.00 s) |
| S09 | `001` 172–191 (20) | `v9` | 52.70 | 5 | $0.093200 ($0.00466) | $0.9437 / $0.04139 | 71.9% | 192 → 198 (7) | 62.7 / 117.3 / 196.2 | `request-200` (+0.70 s) |
| S10 | `001` 192–212 (21) | `v10` | 47.88 | 5 | $0.094723 ($0.00451) | $0.9670 / $0.04183 | 71.9% | 212 → 217 (5) | 49.7 / 127.8 / 206.3 | `request-219` (+9.59 s) |
| S11 | `001` 213–232 (20) | `v11` | 43.14 | 5 | $0.093530 ($0.00468) | $0.9024 / $0.04285 | 72.1% | 232 → 236 (4) | 43.6 / 116.8 / 203.0 | `request-238` (+2.76 s) |
| S12 | `001` 233–252 (20) | `v12` | 92.25 | 15 | $0.346992 ($0.01735) | $1.0322 / $0.06935 | 69.1% | 252 → 263 (11) | 104.0 / 159.2 / 247.8 | `request-265` (+5.58 s) |
| S13 | `001` 253–273 (21) | `v13` | 77.60 | 7 | $0.121216 ($0.00577) | $0.9761 / $0.03855 | 80.7% | 273 → 283 (10) | 80.4 / 156.2 / 244.7 | `request-285` (+2.40 s) |
| S14 | `001` 274–294 (21) | `v14` | 56.02 | 8 | $0.119834 ($0.00571) | $1.0830 / $0.03496 | 82.8% | 294 → 300 (6) | 62.0 / 144.9 / 217.7 | `request-302` (+4.82 s) |
| S15 | `001` 295–314 (20) | `v15` | 52.21 | 5 | $0.111240 ($0.00556) | $1.0605 / $0.04024 | 70.9% | 314 → 319 (5) | 54.2 / 133.9 / 228.5 | `request-321` (+3.30 s) |
| S16 | `001` 315–335 (21) | `v16` | 68.28 | 10 | $0.201874 ($0.00961) | $1.0329 / $0.03907 | 73.7% | 335 → 346 (11) | 70.8 / 131.2 / 217.4 | `request-348` (+10.19 s) |
| S17 | `001` 336–355 (20) | `v17` | 45.01 | 5 | $0.114488 ($0.00572) | $1.0159 / $0.04308 | 71.1% | 355 → 360 (5) | 49.5 / 121.8 / 187.4 | `request-362` (+2.93 s) |
| **Live total** | **17 windows (355 steps)** | **`v1`–`v17`** | **p50 58.34** | **167** | **$3.013068 ($0.00849)** | **$1.0863 / $0.06935** | **71.2%** | **4–21 (final 11)** | **43.6 / 139.0 / 315.5** | **17/17 (+0.70 to +10.19 s, p50 +3.62 s)** |

- **Proxy settlement:** Every one of the 17 live proxies closed with `settled: true`, `revoked: false`, `breaches: 0`, `unsettled_requests: 0`, `pending_reserved_usd: 0`.
- **Total curator prompt tokens (17 live sessions):** `6,745,427` prompt tokens (`4,805,684` cached, **71.2%**), `1,939,242` cache-write tokens, `69,646` completion tokens (`12,719` reasoning).
- **Frame-to-delivery latency (all 355 covered frames):** min `46.38 s`, median `143.19 s`, max `316.24 s`. Delivery gap from publication (`versions.jsonl` `first_present_ended_wall`) to `knowledge-delivery` (`update`) in `host.jsonl`: min `0.70 s`, median **`3.62 s`**, max `10.19 s`.

## Snapshots and store close

From `curator-runner/polls.jsonl`, `store-closing.json`, and `harness.trace.stores.sealed(session.sqlite3)` (nearest-rank percentiles over all 94 successful reads):

- **Poll outcomes:** 95 polls total — 1 initial `refused:no-store` before custodian creation and **94 successful `read` snapshots** (`0` failures, `0` over bound, `2.17` reads/min across `2,601.11 s`).
- **Timing across all 94 reads:**
  - Read-lock hold (`hold_seconds`, bound 2,000 ms): min **0.39 ms**, median **1.93 ms**, p95 **2.83 ms**, max **3.31 ms**.
  - Read transaction (`transaction_seconds`, bound 1,500 ms): min **0.24 ms**, median **1.69 ms**, p95 **2.60 ms**, max **3.00 ms**.
  - Staging (`staging_seconds`): min **8.65 ms**, median **122.40 ms**, p95 **193.99 ms**, max **340.91 ms**.
- **Closing marker & seal:** `store-closing.json` was written at `1795325198.173` (`7.37 s` after read 94 ended at `1795325190.803`), the runner wrote terminal `status.json` `0.03 s` later (`1795325198.208`), and `sealed(session.sqlite3)` verified an empty write-ahead log.

## Post-admission boundary grooming and `curator-fact/4` store

After the store sealed, one post-admission boundary-grooming session ran cleanly with the approved command:

```sh
.venv/bin/python -m tools.curator_host.groom \
  --run .runtime/computer-sessions/live-validation-run-889-a02d8069d043 \
  --config .runtime/live-validation-run-889/curator-runner-config.json \
  --out .runtime/live-validation-run-889/grooming \
  --cap-usd 8.00
```

- **Outcome (`grooming-summary.json`):** `status: "completed"`, `published_before: "v17"`, `published_after: "v18"`, `session_state: "sealed"`, `cost_usd: "0.18741400"`, `requests: 6`, `wall_seconds: 93.845`, `sandbox.survivors: []`, `proxy.settled: true`, `proxy.revoked: false`, `proxy.breaches: 0`, `max_reserved_usd: "$1.3906"`, `max_charge: "$0.0578"`. Tokens: `374,138` prompt (`264,070` cached, **70.6%**), `110,050` cache-write, `7,326` completion (`2,239` reasoning).
- **Knowledge repository progression (`v0 -> v17 -> v18`, 6 ontology types: `character_option`, `entity_property`, `interface_control`, `location_observation`, `process_requirement`, `skill_effect`):**

| Version | Total facts (current) | Game-scoped current (cited in articles) | World-scoped current (`campground-889`, cited) | Superseded / retired | Current articles (total records) |
| --- | ---: | ---: | ---: | ---: | ---: |
| `v0` | 0 (0) | 0 (0) | 0 (0) | 0 / 0 | 0 (0) |
| `v1` | 15 (15) | 15 (15) | 0 (0) | 0 / 0 | 4 (4) |
| `v5` | 52 (52) | 47 (46) | 5 (0) | 0 / 0 | 8 (13) |
| `v10` | 92 (92) | 81 (70) | 11 (0) | 0 / 0 | 13 (20) |
| `v14` | 113 (113) | 98 (83) | 15 (0) | 0 / 0 | 17 (26) |
| `v17` (end of live run) | 135 (135) | 119 (101) | 16 (0) | 0 / 0 | 22 (33) |
| **`v18` (after boundary grooming)** | **139 (131)** | **118 (118 — 100%)** | **13 (0 — standalone)** | **8 / 0** | **31 (44)** |

`v18` retained `last_admission` coverage (`actor: "001"`, `last_step: 355`) with `202` accumulated citations, filed every remaining uncited game-scoped fact into articles (`118/118`), consolidated 8 redundant facts via supersession, and kept every world-scoped `campground-889` observation (such as `campground-start-tent-observation`, `campground-dog-sighting`, `campground-nearby-frozen-water`, `campground-tent-crossbow-sighting`) strictly standalone.

## Host response time by prompt band and total cost

From `python -m tools.evaluate host-summary` (`0` retries, `17` image drops, completed player responses median **6.40 s**, p95 **10.13 s**):

| Prompt tokens | Responses | Median s | 95th percentile s | Within 2 s | Within 5 s | Mean cost per request |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| All responses | 369 | 6.4 | 10.1 | 3.0% | 27.4% | $0.0112 |
| Under 20,000 | 19 | 2.0 | 4.6 | 52.6% | 100.0% | $0.0022 |
| 20,000 to 60,000 | 97 | 5.0 | 8.9 | 1.0% | 48.5% | $0.0061 |
| 60,000 to 100,000 | 93 | 6.7 | 10.1 | 0.0% | 12.9% | $0.0096 |
| 100,000 to 150,000 | 112 | 7.3 | 10.7 | 0.0% | 9.8% | $0.0159 |
| Over 150,000 | 48 | 5.8 | 9.5 | 0.0% | 25.0% | $0.0174 |

Prompt-size scaling is directly visible: keeping prompts under 60,000 tokens corresponds to median `2.0–5.0 s` and `$0.0022–$0.0061`/request, whereas growing to 100,000–172,000 tokens pushed cost to `$0.0159–$0.0174`/request (`host.large_rewrite_share`: `43.6%`).

- **Spend breakdown:** Player spend is recorded in [`data/evaluation/runs.jsonl`](../../data/evaluation/runs.jsonl) (`spend_complete: true`, `0` unpriced attempts; derived `$0.01192` / evaluator decision over 359 decisions, `$0.01166` / operation over 367 operations). Live curator spend was `$3.01306770` across 17 settled sessions, and boundary grooming spend was `$0.18741400`, for a combined total of **`$7.47877910`** against the `$34.00` planning ceiling.

## Upgraded `#846` schedule replay (`--recorded-deliveries`) and `#890` inputs

Read-only (`$0`) replay over the sealed `#889` run (`18` coverage changes read, `18` applied, `0` left out; actor `001` starting briefing `45` approximated tokens at 4 UTF-8 bytes/token, `17` live updates totalling `6,398` tokens, `30` reminders totalling `16,903` tokens, `0` unmatched deliveries):

```sh
.venv/bin/python -m tools.memory_screen_checks schedule .runtime/evidence/live-validation-run-889/run --output SCHEDULE
.venv/bin/python -m tools.memory_screen_checks cut .runtime/evidence/live-validation-run-889/run --coverage schedule --schedule SCHEDULE
.venv/bin/python -m tools.memory_screen_checks cut .runtime/evidence/live-validation-run-889/run --coverage schedule --schedule SCHEDULE --recorded-deliveries
```

| Row | Requests | Prompt p50 | Prompt p95 | Prompt max | Cuts | Cuts / reqs held back | Image drops | Cache write (vs recorded) | Share < 40k | Share < 60k |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `recorded` | 369 | 88,458 | 162,685 | 171,996 | 0 | 0 / 0 | 17 | 1,850,815 (1.000) | 0.168 | 0.314 |
| `no cut` (0 delivery tokens) | 369 | 77,680 | 126,300 | 134,990 | 0 | 0 / 0 | 17 | 1,563,154 (0.845) | 0.152 | 0.336 |
| `no cut` (`--recorded-deliveries`) | 369 | 86,326 | 148,088 | 158,044 | 0 | 0 / 0 | 17 | 1,765,773 (0.954) | 0.146 | 0.306 |
| `schedule` (0 delivery tokens) | 369 | 32,190 | 41,690 | 47,390 | 14 | 2 / 2 | 3 | 654,254 (0.353) | 0.864 | 1.000 |
| `schedule` (`--recorded-deliveries`) | 369 | 34,379 | 44,867 | 50,483 | 14 | 2 / 2 | 3 | 700,182 (0.378) | 0.751 | 1.000 |

**Per-cut diagnosis for [#890](https://github.com/CVX-Hull/enactive/issues/890):**
- Adding `--recorded-deliveries` narrowed `no cut` error against the real trace on prompt percentiles and cache writes (`p50` `-2.4%`, `p95` `-9.0%`, `max` `-8.1%`, cache write `0.954x`; `under_40000` moved slightly farther from recorded, `0.152` to `0.146` vs `0.168`).
- All `2` held-back requests and all `3` image drops occurred in the first 105 requests:
  - `request-41` (`cov = 0`, held back, image drop): `v1` had been delivered to the actor at `request-40`, while replay coverage first applied at `request-43` from the next runner poll row.
  - `request-61` (`cov = 20`, freed 20 turns, image drop): `v2` had not yet published (delivered at `request-63`).
  - `request-105` (`cov = 64`, held back, image drop): caused by session `S04`'s `164.86 s` (32-request) outlier while publishing `v4` (delivered at `request-109`).
- Across the entire remaining **264 requests (`request-106` through `request-369`)**, `schedule` executed **12 consecutive cuts** (`#125`, `#150`, `#172`, `#192`, `#212`, `#232`, `#253`, `#273`, `#293`, `#314`, `#335`, `#355`, freeing 20–45 turns each) with **0 held-back requests, 0 image drops**, `max(prompt - briefing) = 50,438 <= 60,000`, and a **68.9% reduction in simulated cache writes** over requests 106–369 (**62.2%** full-run, `0.378x` recorded). As disclosed in [measurement tools](../contracts/measurement-tools.md#runner-records-and-schedule-replay), the simulation keeps actor `001`'s starting briefing size (`45` tokens) constant across cuts and does not model fresh-briefing growth at each cut — a key input for `#890`'s design and Go/No-Go decision brief.

## Sealed evidence

Sealed under `.runtime/evidence/live-validation-run-889/` (854 files: played run, curator runner, knowledge repository `v0`–`v18`, boundary grooming, runner config, recorded coverage schedule, and saved `study-userdir`) with tracked SHA-256 manifest [`data/evidence/live-validation-run-889.sha256`](../../data/evidence/live-validation-run-889.sha256), and companion seal `.runtime/evidence/live-validation-run-889-aux/` (30 files: initial zero-spend aborted launch package and evaluated `2-cdda-2.sqlite3` record) with tracked manifest [`data/evidence/live-validation-run-889-aux.sha256`](../../data/evidence/live-validation-run-889-aux.sha256), both indexed in [`data/evidence/index.json`](../../data/evidence/index.json).
