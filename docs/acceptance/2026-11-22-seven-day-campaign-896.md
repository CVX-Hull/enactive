---
owner: lead
status: historical
kind: run
date: '2026-11-22'
scope: 'Seven-day survival campaign (#896 under #145): Stage 1 Gate 1 (Starrsville / Rowan Reed on main 403864d3) and fresh-world lineage campground-seven-day-896-b (Norge / Rowan Vale across 10 admissions on frozen main 0ff6ace5) reaching Spring day 68, 8:24:07 AM (606,247 elapsed game seconds = 168h 24m 07s >= 7 full days) with 98/98 HP on all 12 body parts, 86/86 settled live curator sessions (v0->v91), 92.27% prompt cache share, and $90.67 recorded / $95.13 conservative upper-bound total spend inside the $120.00 approved envelope'
---

# Seven-day survival campaign with live curator memory and context cutting (#896)

## At a glance

- **Question.** Under [#145](https://github.com/CVX-Hull/enactive/issues/145) and [#896](https://github.com/CVX-Hull/enactive/issues/896), can the frozen playing system (`campaign-run/12` + `player-host/11`, live curator with `curator-fact/4` world/game separation, `live_knowledge_updates: true`, `#890` `60k/20k/10` context cutting, and `#914` bounded `15.0 s` graceful curator teardown) autonomously survive **seven full in-game days (`>= 604,800` elapsed game seconds / `168.0` hours)** from a fresh `Wilderness / Campground / Survivor` start with normal `Save` persistence and zero manual gameplay intervention inside the owner-approved `$120.00` campaign envelope?
- **Outcome: PASS for `campground-seven-day-896-b` under `#145` (independent cross-family audit confirmed).**
  - **Seven-day survival milestone verified on screen and on disk:** Across 10 supervised admissions (`A1`–`A10`) on frozen `main` (`0ff6ace5d6299d2100c6a7291f3eb812e3c59555`), `Norge` / `Rowan Vale` progressed from `Spring day 61, 8:00:00 AM` (`game_start = 5,212,800`) to **`Spring day 68, 8:24:07 AM` (`turn = 5,819,047`)** — **`606,247` elapsed game seconds (`168 h 24 m 07 s`)**, clearing the `604,800 s` seven-day target by `1,447 s` (`24 m 07 s`). Decompressing the sealed `A10` character save (`#Um93YW4gVmFsZQ==.sav.zzip`, SHA-256 `132be6dd…8b26e1c`) independently verified `player.name = "Rowan Vale"`, `turn = 5,819,047`, **`98/98` HP on all 12 body parts**, and sustained daily calorie intake across days 61–68 (`2,311`, `2,988`, `2,241`, `2,344`, `2,456`, `2,314`, `2,121`, and `543` kcal on partial day 68). Admission 10 closed with `player_finish.disposition = "task_complete"`, title-screen `» Norge (1)` confirmation, and `normal_native_exit_zero: true`.
  - **Stage 1 Gate 1 (`Starrsville` / `Rowan Reed`, `main` `403864d3`) accounted honestly and separately:** Gate 1 ended early in `Starrsville` (`turn = 5,227,297`, both legs `0/98` HP) and exposed a `curator_runner` teardown `SIGKILL` (`31/32` settled windows, 1 interrupted at teardown). Following the owner's 22 November 2026 authorization ([owner decision](../decisions/owner-decisions-archive.md#spectator-redesign-and-fresh-world-896-b-2026-11-22)), `#914` (bounded `15.0 s` graceful teardown wait) and `#913` (3-tab Mission Control Spectator) were merged before starting fresh world `campground-seven-day-896-b`. Gate 1's spend is included in the campaign envelope; none of its survival time counts toward `Rowan Vale`.
  - **Spend (well inside the `$120.00` approved envelope):** Player+recall attempts, wall durations, and provider-reported player subtotals for all 11 admissions are recorded in [`data/evaluation/runs.jsonl`](../../data/evaluation/runs.jsonl). Combined with live curator proxy ledgers (`$55.28265795` across `118` sessions; `$48.93173425` across `86/86` settled sessions in `896-b`) and boundary grooming (`$2.73897440` across 9 sessions), **whole-campaign recorded spend is `$90.66595280`**, and the **conservative upper bound** (covering Gate 1's 1 interrupted curator window at its full `$3.72992375` window cap plus `$0.4096` each for A7 and A8's two unpriced HTTP `403` player requests) is **`$95.13422910`** — **`$24.87` under the `$120.00` hard ceiling** (`campground-seven-day-896-b` alone: `$80.31087645` recorded / `$81.13007645` upper bound, `$0.477`/game-hour).
  - **Live curator, `#914` teardown, and `#890` context cutting validated at campaign scale:** In `campground-seven-day-896-b`, **`86 of 86` live curator sessions settled cleanly (`0` unsettled requests, `0` `SIGKILL`s)**, publishing an unbroken `v0 -> v91` knowledge chain (`2687d763…0ab647c1`). Context cutting (`60k/20k/10`) executed **`77` actual cuts** (`2,128` held-back checks) and delivered **`508` knowledge messages** (`89` briefings, `80` updates, `339` reminders) while sustaining **`92.27%` overall prompt cache hit share** (`93.57%` on deciding-player turns).
  - **Independence (`#145`) verified:** Independent clean-context audit matched **all `3,637` recorded game input operation IDs** across all ten sealed `session.sqlite3` stores to hosted actor tool results (`0` manual inputs), verified byte-identical `docs/player-guide.md` (`142e7303…08ac70fd`, frozen per [`#player-guide-frozen-through-896`](../decisions/owner-decisions-archive.md#player-guide-frozen-through-896)), identical source commit `0ff6ace5…` across `A1`–`A10`, `10/10` terminal custody invariants, and unbroken curator publication history (`#curator-is-player-memory-145`).
  - **Honest caveats (detailed below):** Player-chosen custom `Survivor` (`12/12/12/12` stats, `overpowered` point rating); two mid-campaign autosave rollbacks (`A2` overmap `cannot_continue`, `A7`/`A8` upstream HTTP `403` `provider-refusal`s); `A6`/`A7`/`A9` boundary grooming `cap-reached` on the grown `v69`–`v85` graph inside the frozen `$2.50` cap; benign Quit-click `Native channel EOF` race recording `custodian_receipt.outcome = "interrupted"` despite `normal_native_exit_zero: true`; and no live CDDA reload after `A10` Save (persistence verified via on-disk decompressed save JSON, pre-save HUD frame, title screen, and native exit `0`).

[Issue #896](https://github.com/CVX-Hull/enactive/issues/896) · [Goal #145](https://github.com/CVX-Hull/enactive/issues/145) · [Owner approvals](../decisions/owner-decisions-archive.md#seven-day-campaign-896-approved) · [Fresh-world authorization](../decisions/owner-decisions-archive.md#spectator-redesign-and-fresh-world-896-b-2026-11-22) · [Run ledger](../../data/evaluation/runs.jsonl) · [Evidence index](../../data/evidence/index.json)

## Frozen configuration and campaign boundaries

All 10 admissions of `campground-seven-day-896-b` launched via `tools.campaign_supervision --run <PKG> --curator-runner .runtime/campaigns/seven-day-896-b/curator-runner-config.json` from clean `main` at `0ff6ace5d6299d2100c6a7291f3eb812e3c59555` (`docs/player-guide.md` unchanged from commit `24c55a41`, SHA-256 `142e73034bbbfd3b53db33adf408904cad867419a4e806e0b3dfaf0d08ac70fd`):

- **Runtime & route:** `campaign-run/12`, `player-host/11`, `openai/gpt-6.1-terra` (`medium` effort, `service_tier: "default"`), player failover allowlist `["openai", "azure"]` (`allow_fallbacks: false`, `require_parameters: true`), recall pinned `["openai"]` every 10 inputs, `max_context_images: 39`, `context_image_block: 20`, `context_cut: {high_mark: 60000, low_mark: 20000, min_free: 10}`, `live_knowledge_updates: true`.
- **Frozen caps (`campground-seven-day-896-b`):** Play `$5.00` (with `$1.40` ending reserve inside the play cap), live curator `$8.00` (`$5.00`/session, `trigger_steps: 35`, `ceiling_steps: 60`, `max_output_tokens: 16384`), post-admission boundary grooming `$2.50` (`--cap-usd 2.50`). *(Stage 1 Gate 1 on `403864d3` used `$10.00` live / `$6.00`/session with `20/40` steps under the `$18.00` Stage 1 ceiling.)*
- **Independence rules (`#145`):** Per [`#curator-is-player-memory-145`](../decisions/owner-decisions.md#curator-is-player-memory-145), curator-written memory counts as player memory; manual game inputs, lead tactical hints, manual memory edits, save editing, and runtime rescues are strictly prohibited.

## Evaluator metrics (`run-metrics.jsonl`)

The [run ledger](../../data/evaluation/runs.jsonl) is the single tracked record for per-admission player attempts, provider-reported player subtotals, and wall durations. The generated evaluator table below (`python -m tools.evaluate evaluate-table data/evaluation/run-metrics.jsonl --write docs/acceptance/2026-11-22-seven-day-campaign-896.md`) summarizes all 11 sealed `#896` admissions (`seven-day-896-a01` plus the 10-admission `seven-day-896-b` lineage):

<!-- evaluate-table study=896 core=2 binding=cdda:2 -->
| Run | Arm | Start | End | Game h | Decisions | Setup | Routine pace | Long activities | Out of play | Longest stall | $ / decision | Large rewrites |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| seven-day-896-a01-b55e1a8d3500 | seven-day-campaign | S1 | custody | 4.03 | 669 | 22 | 2.8 | 3 · 2.43 h | 76% | 26 | 0.0054 | 0% |
| seven-day-896-b-a01-c949ed5cecf2 | seven-day-campaign | S1 | custody | 23.65 | 569 | 21 | 2.5 | 10 · 22.20 h | 69% | 20 | 0.0064 | 25% |
| seven-day-896-b-a02-20551a8e9e25 | seven-day-campaign | S1 | player_stop | 7.66 | 313 | 4 | 3.5 | 8 · 6.56 h | 79% | 25 | 0.0067 | 25% |
| seven-day-896-b-a03-b312d2c8e509 | seven-day-campaign | S1 | custody | 22.39 | 483 | 4 | 3.0 | 13 · 20.31 h | 72% | 24 | 0.0076 | 28% |
| seven-day-896-b-a04-9d8f05986ffa | seven-day-campaign | S1 | custody | 25.50 | 430 | 4 | 2.5 | 12 · 23.62 h | 76% | 20 | 0.0085 | 35% |
| seven-day-896-b-a05-4d06a351c23c | seven-day-campaign | S1 | custody | 25.41 | 429 | 3 | 4.0 | 10 · 23.60 h | 74% | 27 | 0.0086 | 36% |
| seven-day-896-b-a06-aaf541c340e1 | seven-day-campaign | S1 | custody | 20.64 | 457 | 4 | 2.8 | 14 · 18.55 h | 80% | 20 | 0.0082 | 32% |
| seven-day-896-b-a07-1d14589af7c2 | seven-day-campaign | S1 | infrastructure | 3.83 | 291 | 4 | 4.0 | 4 · 2.43 h | 69% | 14 | 0.0087 | 35% |
| seven-day-896-b-a08-17610f3033b2 | seven-day-campaign | S1 | infrastructure | 0.00 | 13 | 7 | — | 0 · 0.00 h | 71% | 3 | 0.0060 | 0% |
| seven-day-896-b-a09-a6a0013cd039 | seven-day-campaign | S1 | custody | 17.13 | 408 | 5 | 3.0 | 7 · 14.82 h | 79% | 33 | 0.0090 | 33% |
| seven-day-896-b-a10-7a28b7bea730 | seven-day-campaign | S1 | custody | 25.55 | 237 | 4 | 3.0 | 17 · 23.66 h | 78% | 24 | 0.0090 | 33% |
<!-- /evaluate-table -->

*(Note: evaluator `Game h` sums per-admission in-play clock deltas, including ~`3.36 h` of play later rolled back by CDDA autosave reloads on `A2 -> A3` and `A7 -> A9`. Elapsed campaign survival uses the persisted `A10` save clock directly so discarded play is never double-counted.)*

## Cost, curator settlement, and teardown reconciliation

Player+recall subtotals and attempt counts are authoritative in [`data/evaluation/runs.jsonl`](../../data/evaluation/runs.jsonl); every receipt reported `spend_complete: true` (`0` unpriced recall requests; `2` unpriced player HTTP `403` refusals on `A7` and `A8`, bounded at `$0.4096` each). Live curator and grooming totals below are summed directly from the sealed proxy ledgers and reconciled against session summaries; each row's combined recorded total adds the corresponding player+recall subtotal from `runs.jsonl`:

| Sealed study | Live curator posted (settled/started) | Live pub. | Runner exit / signals | Grooming status | Grooming USD (`max_reserved`) | Groom pub. | Combined recorded USD | Conservative upper bound USD |
|---|---:|---|---|---|---|---|---:|---:|
| `seven-day-896-admission-01` (Gate 1) | `$6.35092370` (`31/32`) | `v0 -> v31` | `-9` / `SIGINT, SIGTERM, SIGKILL` | `completed` | `$0.36140535` (`$1.7826`) | `v31 -> v33` | `$10.35507635` | `$14.00415265` |
| `seven-day-896-b-admission-01` (`A1`) | `$6.33520855` (`16/16`) | `v0 -> v16` | `130` / `[]` | `completed` | `$0.24798340` (`$1.3193`) | `v16 -> v18` | `$10.24269720` | `$10.24269720` |
| `seven-day-896-b-admission-02` (`A2`) | `$3.45337175` (`8/8`) | `v18 -> v26` | `130` / `[]` | `completed` | `$0.22241370` (`$1.5230`) | `v26 -> v28` | `$5.75792510` | `$5.75792510` |
| `seven-day-896-b-admission-03` (`A3`) | `$6.53702520` (`11/11`) | `v28 -> v38` | `1` / `[]` (`spend-reservation-refused`) | `completed` | `$0.32843310` (`$1.8715`) | `v38 -> v40` | `$10.54267865` | `$10.54267865` |
| `seven-day-896-b-admission-04` (`A4`) | `$6.36709815` (`7/7`) | `v40 -> v47` | `1` / `[]` (`spend-reservation-refused`) | `completed` | `$0.39955615` (`$2.0610`) | `v47 -> v50` | `$10.42883295` | `$10.42883295` |
| `seven-day-896-b-admission-05` (`A5`) | `$6.44748715` (`9/9`) | `v50 -> v58` | `1` / `[]` (`spend-reservation-refused`) | `completed` | `$0.32647030` (`$2.1543`) | `v58 -> v59` | `$10.48484955` | `$10.48484955` |
| `seven-day-896-b-admission-06` (`A6`) | `$6.27973625` (`11/11`) | `v59 -> v69` | `1` / `[]` (`spend-reservation-refused`) | `failed` (`cap-reached`) | `$0.26355610` (`$1.8609`) | `v69 -> v69` | `$10.31293190` | `$10.31293190` |
| `seven-day-896-b-admission-07` (`A7`) | `$4.59111445` (`8/8`) | `v69 -> v76` | `130` / `[]` | `failed` (`cap-reached`) | `$0.30518080` (`$2.1328`) | `v76 -> v76` | `$7.43030430` | `$7.83990430` |
| `seven-day-896-b-admission-08` (`A8`) | `$0.00000000` (`0/0`) | `v76 -> v76` | `130` / `[]` | not run | `$0.00000000` | — | `$0.07816785` | `$0.48776785` |
| `seven-day-896-b-admission-09` (`A9`) | `$6.06072050` (`10/10`) | `v76 -> v85` | `1` / `[]` (`spend-reservation-refused`) | `failed` (`cap-reached`) | `$0.28397550` (`$2.0152`) | `v85 -> v85` | `$10.03203915` | `$10.03203915` |
| `seven-day-896-b-admission-10` (`A10`) | `$2.85997225` (`6/6`) | `v85 -> v91` | `130` / `[]` | not run | `$0.00000000` | — | `$5.00044980` | `$5.00044980` |
| **`896-b` fresh lineage (`A1`–`A10`)** | **`$48.93173425` (`86/86`)** | **`v0 -> v91`** | **`0` `SIGKILL`s** | `5` done / `3` cap / `2` skip | **`$2.37756905`** | — | **`$80.31087645`** | **`$81.13007645`** |
| **Whole `#896` campaign (11 runs)** | **`$55.28265795` (`117/118`)** | — | `1` `SIGKILL` (Gate 1 pre-`#914`) | `6` done / `3` cap / `2` skip | **`$2.73897440`** | — | **`$90.66595280`** | **`$95.13422910`** |

- **Gate 1 accounting detail:** Gate 1's 31 settled live summaries totalled `$6.27007625`; interrupted window 32 (`001-664-683-2a0bc651`) posted `$0.08084745` across requests 1–3 before `SIGKILL` during `request-4`. Replacing that partial window charge with its full `$3.72992375` window cap bounds Gate 1 live curation at `$10.00000000` (`+$3.64907630` upper-bound delta), bringing Gate 1 to `$14.00415265` and the whole campaign to `$95.13422910` — **`$24.86577090` below the `$120.00` ceiling**.
- **`#914` teardown fix validated 10-for-10:** After `#914` merged (`3f8abe16`), zero `curator_runner` processes escalated to `SIGKILL` across all 10 `896-b` admissions (`5` exited cleanly during teardown with `returncode: 130`, `5` exited before teardown on `spend-reservation-refused` with `returncode: 1`), and all **`86/86`** live curator sessions settled with **`0` unsettled requests**.

## Host telemetry, context cutting, and provider routing (`896-b`)

Across all actors (including the recorded actor handoffs in `A4` and `A9`) for `campground-seven-day-896-b` (`A1`–`A10`), splitting each admission's [`runs.jsonl`](../../data/evaluation/runs.jsonl) attempts by reported routing backend:

| Admission | Primary provider | Secondary failover | Unknown (`403`) | Actual cuts (`removed_turns > 0`) | Held-back checks | Knowledge deliveries | Cache read / total prompt tokens | Cache share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `A1` | 642 | 0 | 0 | 15 | 345 | 83 | 20,926,285 / 22,707,427 | 92.16% |
| `A2` | 360 | 0 | 0 | 8 | 158 | 47 | 12,025,018 / 13,019,749 | 92.36% |
| `A3` | 547 | 0 | 0 | 10 | 282 | 65 | 22,182,162 / 23,941,736 | 92.65% |
| `A4` | 484 | 0 | 0 | 6 | 296 | 53 | 22,919,733 / 24,663,945 | 92.93% |
| `A5` | 481 | 0 | 0 | 8 | 292 | 59 | 22,112,957 / 23,947,037 | 92.34% |
| `A6` | 513 | 0 | 0 | 10 | 254 | 64 | 22,324,086 / 24,197,318 | 92.26% |
| `A7` | 324 | 0 | 1 | 7 | 174 | 43 | 14,213,816 / 15,519,193 | 91.59% |
| `A8` | 16 | 0 | 1 | 0 | 0 | 2 | 245,497 / 291,301 | 84.28% |
| `A9` | 464 | 0 | 0 | 7 | 231 | 56 | 21,830,323 / 23,693,623 | 92.14% |
| `A10` | 269 | 0 | 0 | 6 | 96 | 36 | 12,071,986 / 13,180,990 | 91.59% |
| **Total** | **4,100** | **0** | **2** | **77** | **2,128** | **508** | **170,851,863 / 185,162,319** | **92.27%** |

- **Deliveries & caching:** The `508` knowledge deliveries comprised `89` briefings, `80` mid-run version updates, and `339` recall reminders. Excluding recall (`358` responses), deciding-player prompt cache share was **`93.57%`**.
- **Provider failures (`A7` & `A8`):** `A7` `request-295` (`2026-11-23T03:54:04Z`) and `A8` `request-15` (`03:58:10Z`) each returned an identical `451`-byte HTTP `403` `provider-refusal` (`error_code: "403"`, `provider_request_id: null`, `reported_provider: null`, `reason: null`). Separately, `A7` live-curator window `143–178` also encountered an HTTP `403` (`$0` charged, `0` unsettled; later windows recovered through `v76`). Because `player_host` redacts raw refusal bodies by design, the sealed logs do not establish the upstream refusal string; the lead paused after `A8` (wall duration recorded in [`runs.jsonl`](../../data/evaluation/runs.jsonl)) rather than looping, the owner topped up upstream account credits (which had reached `$13.82` remaining), and `A9` + `A10` completed with `0` further `403`s (`733/733` requests succeeded).

## Survival progression, save continuity, and Day 7 verification

Each sealed character archive (`study-userdir/save/Norge/#Um93YW4gVmFsZQ==.sav.zzip`) was decompressed read-only (zstd stream at byte offset `69`) and cross-checked against pre-save HUD frames and title screens (all clocks Spring, 24-hour):

| Admission | Persisted turn | Persisted day & clock | Live end / notable milestones | `normal_native_exit_zero` |
|---|---:|---|---|---|
| Gate 1 (`Starrsville`) | `5,227,297` | Day 61 · `12:01:37` | `Rowan Reed`; both legs `0/98` HP; fresh world authorized | `true` |
| `A1` (`Norge`) | `5,297,938` | Day 62 · `07:38:58` | Fresh start Day 61 `08:00:00`; camp, brazier, cattails, clean water; normal Save | `true` |
| `A2` | `5,314,200` | Day 62 · `12:10:00` | Reached Day 62 `15:18:42`, bow drill + water; overmap stalled -> `cannot_continue` (`SIGTERM` exit `0`, autosave intact) | `false` |
| `A3` | `5,394,815` | Day 63 · `10:33:35` | Resumed `A2` autosave (`12:10:01`); killed/pulped zombie with wooden spear; secured rural house + stove + supplies; normal Save | `true` |
| `A4` | `5,486,626` | Day 64 · `12:03:46` | Actor handoff (`001 -> 002`); sustained cooking, water, reading, threat avoidance; normal Save | `true` |
| `A5` | `5,578,099` | Day 65 · `13:28:19` | Foraged & boiled fiddleheads, managed wood stove + gallon jugs; normal Save | `true` |
| `A6` | `5,652,391` | Day 66 · `10:06:31` | River water collection + boiling, cooked greens & rhizomes, Mood `:)`, Focus `100`; normal Save | `true` |
| `A7` | `5,665,400` | Day 66 · `13:43:20` | Final live frame Day 66 `13:56:28` (alive on bed, full green HP) before HTTP `403` (`SIGTERM` exit `0`, autosave intact) | `false` |
| `A8` | `5,665,400` | Day 66 · `13:43:20` | Reloaded `A7` autosave (`13:43:21`), aborted on HTTP `403` at `request-15` (wall duration in `runs.jsonl`); save byte-identical to `A7` | `false` |
| `A9` | `5,727,069` | Day 67 · `06:51:09` | Actor handoff (`001 -> 002`); swamp foraging, 15 river-water portions collected, plank staged on stove; normal Save | `true` |
| **`A10`** | **`5,819,047`** | **Day 68 · `08:24:07`** | **Cooked cattail stalks, `task_complete`, title screen `» Norge (1)`, `98/98` HP all 12 body parts** | **`true`** |

- **Exact Day 7 milestone proof (`A10`):** `5,819,047 - 5,212,800 = 606,247` elapsed game seconds = **`168 h 24 m 07 s`** (`>= 604,800 s`, exceeding 7 full days by `1,447 s`). Every body part in `player.body` (`arm_l`, `arm_r`, `eyes`, `foot_l`, `foot_r`, `hand_l`, `hand_r`, `head`, `leg_l`, `leg_r`, `mouth`, `torso`) is at `(98, 98)` HP. The save's calorie diary confirms active daily nutrition across the entire week (`2,311`, `2,988`, `2,241`, `2,344`, `2,456`, `2,314`, `2,121`, `543` kcal).
- **Custody & Quit/EOF note:** On all eight normal-Save admissions (`Gate 1`, `A1`, `A3`, `A4`, `A5`, `A6`, `A9`, `A10`), after confirming `Save and quit` to the title screen (`Starrsville` on Gate 1; `» Norge (1)` on `A1`, `A3`–`A6`, `A9`, `A10`), the player's separate title-screen `Quit` confirmation exited CDDA cleanly (`returncode: 0`, `signals: []`, `normal_native_exit_zero: true`) before the bridge returned an input acknowledgement (`status: "unknown"` -> `Native channel EOF`). The player followed the guide by collecting the operation once without replay, while the custodian recorded `outcome: "interrupted"` (`Input permanently fenced outside accepted host cleanup`). On `A10`, `player_finish.disposition = "task_complete"`, `normal_native_exit_zero = true`, `cleanup_verified = true`, `manifest_unchanged = true`, and `terminal_coverage_verified = true`.

## Independence audit (`#145`) and honest caveats

An independent clean-context reviewer audited all 11 sealed evidence bundles (`seven-day-896-admission-01` and `seven-day-896-b-admission-01..10`) and confirmed **pass for `campground-seven-day-896-b` under `#145`**:

- **Zero manual game inputs:** All **`3,637` recorded input operation IDs** across all ten sealed `session.sqlite3` databases matched hosted actor tool results (`0` unexplained inputs).
- **Frozen runtime & guide:** All 10 `896-b` admissions share commit `0ff6ace5…`, identical frozen settings, byte-identical `docs/player-guide.md` (`142e7303…`), and `10/10` true terminal custody flags (`manifest_unchanged`, `cleanup_verified`, `terminal_coverage_verified`, `deciding_hosts_quiescent`, `native_absence_verified`, `input_authority_revoked`, `pause_reason: null`).
- **Unbroken curator memory:** All `91` publications (`v0 -> v91`, final commit `2687d763…`) match curator session verdicts and gate transitions with zero restores and zero manual edits.

**Explicit caveats and follow-up engineering findings:**

1. **Custom Survivor build:** `Rowan Vale` was created by the player as a custom `Survivor` with `12/12/12/12` stats (character-editor rating `overpowered`) inside the authorized `Wilderness / Campground / Survivor` scenario; this pass applies to that autonomous custom-character run.
2. **Two autosave rollbacks (`A2` and `A7`/`A8`):** `A2` stopped cleanly (`cannot_continue`) on an unresponsive overmap (`3h 08m` rolled back into `A3`); `A7` and `A8` aborted on upstream HTTP `403`s (`13m` rolled back into `A9`). No rolled-back time is counted in the `168h 24m 07s` milestone, though curator memory retained notes from rolled-back steps without manual repair.
3. **Boundary grooming cap scaling (`A6`/`A7`/`A9`):** Once the cumulative knowledge repository grew past `v69`, worst-case single-turn prompt+output reservations (`$1.86–$2.13`) plus initial turns exceeded the frozen `$2.50` grooming cap (`cap-reached`), leaving `v69`/`v76`/`v85` intact (`0` unsettled requests). Future multi-day campaigns should size boundary-grooming caps or reservation bounds for large mature graphs.
4. **Quit-click EOF classification:** Clean title-screen `Quit` reliably closes the native channel before the input ack arrives, causing `custodian_receipt.outcome = "interrupted"` even when `player_finish.disposition = "task_complete"` and `normal_native_exit_zero = true`.
5. **No live post-`A10` reload & final 24-step curator lag:** `A10` persistence is verified via on-disk decompressed save JSON (`turn = 5,819,047`, `98/98` HP), pre-save HUD frame, title screen, and native exit `0`, rather than a live CDDA reload; `v91` covered through step `215` of `239` on `A10` (`24`-step tail backlog, below the `35`-step live trigger).

## Sealed evidence

All 11 evidence bundles are sealed read-only under `.runtime/evidence/` with SHA-256 manifests tracked under [`data/evidence/`](../../data/evidence/index.json):

- `seven-day-896-admission-01` (Gate 1, `Starrsville` / `Rowan Reed`, `main` `403864d3`)
- `seven-day-896-b-admission-01` through `seven-day-896-b-admission-10` (`campground-seven-day-896-b`, `Norge` / `Rowan Vale`, `main` `0ff6ace5`)
