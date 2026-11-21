---
owner: lead
status: historical
kind: run
date: '2026-11-21'
scope: 'One paid live curator run beside real CDDA play: lag, covered prefix, time to publication, backlog, cost, snapshot timing, player pace, published facts, prompt cache share, input routine recurrence, schedule lag replay, and an early curator stop from a gate provenance defect (#859)'
---

# Paid live curator run beside real play (#859)

## At a glance

- **Question.** When the curator runner follows a live CDDA admission with 20-step windows, how far does confirmed coverage trail play, what does it cost beside the player, how long do live snapshots hold the store, does play slow against comparable sealed admissions, and what does the recorded coverage schedule do in the lag simulation?
- **Outcome (partial — both sides stopped early).** The run ran once on main `371ed949` under the owner's 21 November 2026 launch approval (session `2cda0867c34442f394299555aece7009`, world `Richwoods`, survivor `Rowan Reed`, Wilderness / Campground / Survivor, `S1`). **All 21 live snapshot reads succeeded** (max lock hold 1.50 ms vs 2,000 ms bound; max transaction 1.20 ms vs 1,500 ms bound; max staging 77.92 ms; `sealed()` accepted the finished store with an empty write-ahead log). **Both the curator runner and the player stopped early**:
  1. **Curator runner stopped after 5 sessions (`2 consecutive failed sessions`).** Sessions 1–3 (`001` steps 1–20, 21–41, 42–62) published `v1`, `v2`, and `v3`. Sessions 4–5 (steps 63–84, 85–106) were both rejected with `publication failed: incompatible history at v3` because consecutive operations 41 and 42 shared unchanged frame `2cda0867c34442f394299555aece7009-808` across the window 2/3 boundary and `harness/curator/gate.py:519` overwrote that frame's step from 41 to 42 in `v3`, breaking `_history()` on two `v2` facts (filed as [#886](https://github.com/CVX-Hull/enactive/issues/886)). As designed, the runner's stop never stopped play.
  2. **Player stopped early for safety** before reaching the $1.60 work budget or $1.40 ending reserve (attempts, spend, and wall duration are in the [run ledger](../../data/evaluation/runs.jsonl) row for `live-curator-run-859-2cda0867c344`; evaluator headlines are in the generated table below), saving `Richwoods` to title and sending Quit (`normal_native_exit_zero: true`; `driver.outcome: interrupted` from native EOF before `player_finish`).
- **Headline readings (partial).** Reading the [corrected outcome table](2026-11-20-live-curator-run-price-correction-836.md#the-order-of-the-outcome-table-and-two-rows) in strict order: snapshots passed (row 1 clear), and **row 2 ("The run stops early") decides**: figures are reported as partial and a further run requires a new owner decision. Within those partial figures:
  - **Pace:** 9.74 decisions/min and 10.20 operations/min on receipt elapsed time (10.46 operations/min on the first-to-last-operation clock that reproduces the frozen reference rates) — faster than all three named reference admissions and well above the fixed cutoff (under 5.16 decisions/min or 5.48 operations/min).
  - **Backlog and lag:** backlog never grew across the five sessions; every session finished before the next 20-step window filled (49.40–113.73 s runner duration, median 57.60 s; completed-operation backlog at session end 9–16 steps; backlog at the next poll after sessions 1–4 was 11–15 steps). True lag against completed operations fell to 10–14 operations at the end of each of the three accepted sessions.
  - **Spend (counted, complete, settled):** player spend is recorded in the [run ledger](../../data/evaluation/runs.jsonl) (0 unpriced requests, `spend_complete: true`), and curator spend across all 5 settled sessions was **$0.64280670** (**$0.27826640** for accepted `v1`–`v3`; **$0.36454030** for rejected sessions 4–5; `$0.00606`/examined step; `proxy-close.json`, `summary.json`). Combined spend stayed well inside the $3.50–$3.90 forecast and $18.50 planning ceiling.
  - **Lag simulation replay (`tools.memory_screen_checks cut --coverage schedule`):** over all 135 player requests, `schedule` made 3 cuts (turns 41, 61, 82), reduced median prompt from 45,035 to 33,000 tokens and full-run max from 69,506 to 47,390 (reached at turn 122; `under_60000` 1.00), and held back 2 cuts/requests with 2 image drops — both at turns 103 and 123, after coverage froze at step 62 due to [#886](https://github.com/CVX-Hull/enactive/issues/886). Across turns 1–82 (while publishing), all 3 cuts fired on time with 0 held-back requests, 0 image drops, and a prompt maximum of 41,550 tokens.
- **Archive index.** Session `2cda0867c34442f394299555aece7009` (`campaign-run/10`) is put forward for the evaluator's closed archive list (making 12 `campaign-run/10` sessions under the [owner decision](../decisions/owner-decisions.md#the-paid-runs-session-joins-the-archive-index)).

[Issue #859](https://github.com/CVX-Hull/enactive/issues/859) · [Gate defect #886](https://github.com/CVX-Hull/enactive/issues/886) · [Live curator design](../design/live-curator-integration.md) · [Price proposal](2026-11-20-live-curator-run-price-proposal-836.md) · [Price correction](2026-11-20-live-curator-run-price-correction-836.md) · [Stand-in run](2026-11-20-live-curator-stand-in-run-851.md)

## What ran and how it ended

The package `.runtime/computer-sessions/live-curator-run-859-2cda0867c344` (`campaign-run/10`, session `2cda0867c34442f394299555aece7009`, source commit `371ed9493c0e38a93ba669063460a948102e0fda`, manifest SHA-256 `90327605ccb5cf15f48896681d018fdcfd0b3c0b12dcc9d3f92013ad3fefcf49`) was launched once from the clean main checkout on 21 November 2026, windowed through the prepared wrapper and a fresh project user directory, with `.runtime/live-curator-run-859/curator-runner-config.json` (SHA-256 `7083e76aa4e353d899aa444d5c17b259f7da31e842725d8b98ec58add7b8c917`):

```sh
.venv/bin/python -m tools.campaign_supervision \
  --run .runtime/computer-sessions/live-curator-run-859-2cda0867c344 \
  --curator-runner .runtime/live-curator-run-859/curator-runner-config.json
```

**Start and frozen inputs.** Labels: arm `live-curator-run`, start `S1`, scenario `Wilderness / Campground / Survivor`, `lineage: null`, `admission: null`. Mission text (`prompt.txt`, SHA-256 `f2e09fe8…6fb8af45`), player guide (`context.txt`, SHA-256 `5b63e03e…50f481cc`, frozen as [#803](https://github.com/CVX-Hull/enactive/issues/803) froze it per the owner's 21 November decision), and delivered knowledge `v18` (`delivered-knowledge.json`, 32 articles, 77 facts, SHA-256 `dad85102…927d3dbb`, nothing withheld) matched the first #803 admission byte for byte. Player route: `openai/gpt-6.1-terra` at `medium` pinned to OpenAI through OpenRouter, recall every 10 inputs, `spend_limit_usd: "3.00"`, `ending_reserve.usd: "1.40"`. Runner configuration: arm `terra` (`openai/gpt-6.1-terra`, `medium`, pinned to OpenAI), `cap_usd: "14.50"`, `session_cap_usd: "8.00"`, `trigger_steps: 20`, `ceiling_steps: 40`, `poll_seconds: 15`, `watch_seconds: 5`, `max_output_tokens: 16384`, fresh knowledge repository starting at `v0`. Prior user directory (`Townsend`) was archived under `.runtime/bridge/game.lock` before launch and restored with verified hashes after sealing.

**Supervision and custody (`watch-terminal.json`, `receipt.json`).** The guardian recorded `reason: "custodian_terminal"`, `terminal_coverage_verified: true`, `cleanup_verified: true`, `manifest_unchanged: true`, `custodian_receipt_unchanged: true`, and `pause_reason: null`. All five child process groups (`custodian`, `gateway`, `wake`, `viewer`, `curator_runner`) exited and were verified absent; `curator_runner` had `exited_before_teardown: true`, `returncode: 1`, and `snapshots_removed: true`. The custodian recorded `normal_native_exit_zero: true`, `native_absence_verified: true`, `deciding_hosts_quiescent: true`, and `input_authority_revoked: true` (elapsed wall time and attempts are in the [run ledger](../../data/evaluation/runs.jsonl)).

**Why both sides stopped early.**
- **Curator runner (`curator-runner/status.json`, `stopped.json`, `harness/curator/gate.py`).** After sessions 1–3 published `v1`–`v3`, session 4 (`001` steps 63–84) and session 5 (`001` steps 85–106) both produced submissions against `v3` (9 and 12 changes) and were both rejected with `publication failed: incompatible history at v3`. At `1795286426.78` (`91.00 s` before `store-closing.json`) the runner hit its `2 consecutive failed sessions` stop rule and exited 1, leaving play running undisturbed. Inspection of `v3` (`harness.curator.gate._history`) traced the failure to a real defect ([#886](https://github.com/CVX-Hull/enactive/issues/886)): consecutive operations 41 (`d5a1fcc5…`) and 42 (`cd947720…`) shared unchanged presented frame `2cda0867c34442f394299555aece7009-808` (capture id 808) across the window 2/3 boundary. Session 2 published `v2` with that frame at step 41 and two facts (`nearby-items-monsters-control`, `stick-weapon-preview`) stamped `seen.step = 41`. Session 3 published `v3`, where `gate.py:519` ran `provenance['frames'].update(frames)`, overwriting that frame's step to 42 while those `v2` facts kept `seen.step = 41`. Because `gate.py` checks `_history()` only before applying the current submission, `v3` published with an inconsistent provenance/fact history that locked out every later submission (`ValueError('invalid fact position')` at `gate.py:149`).
- **Player (`receipt.json`, `actors/001/host.jsonl`).** The player entered Wilderness / Campground / Survivor in world `Richwoods` (`Rowan Reed`, confirmed by evaluator identity readings at steps 16–17; 0 death readings across 132 frames). At player request 135, after saving to title and issuing Quit (step 133, whose receipt remained delivery-unknown as the game exited zero), the player called `player_finish(disposition="cannot_continue")` reporting an early safety stop (cold, thirsty, hungry, tired after an interrupted forest sleep attempt; no reload tested). Because native exited on Quit before `player_finish`, the driver recorded `outcome: "interrupted"` (`Native receive failed: Native channel EOF`) while `normal_native_exit_zero` was `true`.

## Activity units and player pace

The [run ledger](../../data/evaluation/runs.jsonl) (`live-curator-run-859-2cda0867c344`) is the single tracked record of player attempts, provider-reported spend, and wall duration. The generated evaluator table below (`python -m tools.evaluate evaluate-table data/evaluation/run-metrics.jsonl --write docs/acceptance/2026-11-21-live-curator-run-859.md`) gives the headline CDDA evaluator metrics from [`data/evaluation/run-metrics.jsonl`](../../data/evaluation/run-metrics.jsonl):

<!-- evaluate-table study=859 core=2 binding=cdda:2 -->
| Run | Arm | Start | End | Game h | Decisions | Setup | Routine pace | Long activities | Out of play | Longest stall | $ / decision | Large rewrites |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| live-curator-run-859-2cda0867c344 | live-curator-run | S1 | custody | 20.99 | 127 | 14 | 2.5 | 9 · 20.75 h | 71% | 15 | 0.0062 | 28% |
<!-- /evaluate-table -->

Decisions, computer operations, and game time are reported separately:

| Unit | Observed | Source |
| --- | --- | --- |
| Decisions | 127 (135 player requests and 13 recall requests; total attempts in `runs.jsonl`) | Generated evaluator table (`run-metrics.jsonl`); `receipt.json` (`runs.jsonl`) |
| Computer operations | 133 (128 `input`, 5 `observe`; 132 with `received_wall` frames, step 133 Quit had none) | `harness.trace.stores.sealed(session.sqlite3)` |
| Game time | 20.99 game hours (`start_game_time` 5,212,800 at step 19 to `end_game_time` 5,288,380 at step 130; 9 long activities totalling 20.75 h; routine pace 2.5 game s/decision; `mode.out_of_play_share` 71% with 14 setup decisions; `stall.longest` 15) | `tools.evaluate evaluate-run` (`2-cdda-2.sqlite3`, generated table above) |

**Player pace against the fixed cutoff.** Two clocks appear in the reference comparison and are labelled separately (one-off read-only script over `session.sqlite3`, `receipt.json`, `runs.jsonl`, and `run-metrics.jsonl`):
- **Receipt elapsed clock** (`receipt.json` `elapsed_seconds`): this run achieved **9.74 decisions/min** and **10.20 operations/min** (on the same receipt-elapsed clock, the three reference admissions had **7.26**, **7.42**, and **7.77** operations/min).
- **First-to-last-operation clock** (`last.created_wall - first.created_wall` in `session.sqlite3`, which reproduces the frozen reference table's operations/min): this run achieved **10.46 operations/min** (133 operations over 762.72 s).

| Admission | Decisions | Decisions/min (receipt elapsed) | Operations/min (first-to-last op, frozen ref) | Operations/min (receipt elapsed) | Source |
| --- | ---: | ---: | ---: | ---: | --- |
| **This run (`live-curator-run-859-2cda0867c344`)** | **127** | **9.74** | **10.46** | **10.20** | `run-metrics.jsonl`, `session.sqlite3`, `receipt.json` |
| `wilderness-803-first-eligible-8a4badef08b9` (same mission) | 405 | 7.10 | 7.31 | 7.26 | sealed study `joanna-campground-memory-803` (`before-launch-summary.md`) |
| `farm-788-equipment-return-e3da8d1f2714` | 265 | 6.88 | 7.60 | 7.42 | sealed study `oceana-farm-memory-788` (`before-launch-summary.md`) |
| `two-wake-772-farm-58ee9279783f45ba8ffd469e1c6357b9` | 310 | 7.48 | 7.86 | 7.77 | sealed study `two-wake-memory-772` (`before-launch-summary.md`) |
| **Fixed "far from" cutoff (25% below slowest)** | — | **< 5.16** | **< 5.48** | — | [Issue #859](https://github.com/CVX-Hull/enactive/issues/859) |

The run was faster than all three reference admissions on both clocks and cleared the cutoff comfortably. One admission cannot establish that the runner did or did not slow play.

## Curator sessions, lag, publication timing and backlog

All five sessions ran sequentially over actor `001` (`curator-runner/examined.jsonl`, `polls.jsonl`, `versions.jsonl`, `status.json`, `session.sqlite3`, and completed `tool-result` wall times in `actors/001/host.jsonl`; completion times are used for true lag because operation 42 reused frame 808's earlier `received_wall` and was created 3.48 s after session 2 started):

| Session | Window | Outcome (version) | Runner dur. (s) | Runner as-of start (pos / cov / lag / backlog) | Runner as-of end (pos / cov / lag / backlog) | Completed ops start → end (true lag start → end; backlog at end) | Next poll (+15 s) pos / backlog |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| `001-1-20-12aaf0f8` | `001` 1–20 | accepted (`v1`) | 49.40 | 20 / none / 20 / 20 | 20 / 20 / 0 / 0 | 20 → 32 (20 → 12; 12) | 35 / 15 |
| `001-21-41-cf616004` | `001` 21–41 | accepted (`v2`) | 97.98 | 41 / 20 / 21 / 21 | 41 / 41 / 0 / 0 | 41 → 55 (21 → 14; 14) | 56 / 15 |
| `001-42-62-c7ddac1c` | `001` 42–62 | accepted (`v3`) | 57.60 | 62 / 41 / 21 / 21 | 62 / 62 / 0 / 0 | 62 → 72 (21 → 10; 10) | 74 / 12 |
| `001-63-84-4f3dd0b6` | `001` 63–84 | rejected (none) | 57.03 | 84 / 62 / 22 / 22 | 84 / 62 / 22 / 0 | 84 → 93 (22 → 31; 9) | 95 / 11 |
| `001-85-106-ab2ae29a` | `001` 85–106 | rejected (none) | 113.73 | 106 / 62 / 44 / 22 | 106 / 62 / 44 / 0 | 106 → 122 (44 → 60; 16) | stopped |

- **Backlog.** Unexamined steps did not grow across the five sessions. Even at 10.20–10.46 operations/min, every session finished before the next 20-step window filled: completed-operation backlog at session end was **12, 14, 10, 9, and 16** across sessions 1–5, and the next poll (+15 s) after sessions 1–4 observed **15, 15, 12, and 11** unexamined steps (below the 20-step trigger). Every window started at 20–22 steps (half the 40-step ceiling).
- **Unexamined and uncovered work at end.** The runner's final `status.json` reports as of step 106: `lag: 44`, `backlog: 0`, `unexamined: []`, `after_last_read: "unknown"`. Against the sealed store's 133 operations, **27 operations** (steps 107–133) were left unexamined and **71 operations** (steps 63–133) were left uncovered after `v3`'s step 62.
- **Time to publication** (`versions.jsonl` `first_present_ended_wall` minus frame `received_wall` in `session.sqlite3`, across the 62 covered steps):

| Version | Covered steps | Watch interval (s) | Min (newest frame, s) | Median (s) | Max (oldest frame, s) |
| --- | --- | ---: | ---: | ---: | ---: |
| `v1` | `001` 1–20 | 4.28 | 50.78 | 79.30 | 103.38 |
| `v2` | `001` 21–41 | 2.69 | 99.49 | 151.10 | 190.61 |
| `v3` | `001` 42–62 | 2.44 | 59.03 | 146.27 | 217.30 |
| **All (`v1`–`v3`)** | **62 steps** | **2.44–4.28** | **50.78** | **118.63** | **217.30** |

## Snapshots and store close

From `curator-runner/polls.jsonl`, `store-closing.json`, and `harness.trace.stores.sealed(session.sqlite3)` (percentiles computed with `harness.evaluation.core.metrics.nearest_rank` over the 21 successful reads; 20th sorted observation for p95):

- **Poll outcomes:** 22 polls total — 1 initial `refused:no-store` before the custodian created `session.sqlite3` (retried by rule) and **21 successful `read` snapshots** (0 failed, 0 over bound, 0 other refusals; 2.13 reads/min across the 562.94 s read span while the runner was active).
- **Timing across all 21 reads:**
  - Read-lock hold (`hold_seconds`, bound 2,000 ms): min **0.39 ms**, median **0.82 ms**, p95 **1.35 ms**, max **1.50 ms**.
  - Read transaction (`transaction_seconds`, bound 1,500 ms): min **0.24 ms**, median **0.62 ms**, p95 **0.98 ms**, max **1.20 ms**.
  - Staging (`staging_seconds`, copying frames and logs): min **7.55 ms**, median **41.35 ms**, p95 **58.32 ms**, max **77.92 ms**.
- **Closing marker and sealed store:** `store-closing.json` was written at `1795286517.78`, **91.00 s** after the runner stopped (`status.json` `updated_wall: 1795286426.78`) and **204.74 s** after the last snapshot read ended (`polls.jsonl` row 22 `ended_wall: 1795286313.04`). The custodian's wait for an active read at close was therefore not exercised. `sealed()` accepted `session.sqlite3` cleanly with an empty write-ahead log.

## Cost and prompt caching

Player total spend, attempts, and accounting status live in the [run ledger](../../data/evaluation/runs.jsonl) row for `live-curator-run-859-2cda0867c344` (`spend_complete: true`, 0 unpriced player or recall attempts; derived rates from `runs.jsonl` `provider_usd` are **$0.00623 / evaluator decision** over 127 decisions and **$0.00594 / operation** over 133 operations; the generated evaluator table's `$ / decision` of `$0.0062` uses the evaluator's 128 input-call denominator and configured-rate dollars).

In the curator table below, **Counted spend**, **USD / step**, and **Max request charge** are counted provider-reported charges from each session's `proxy-close.json`, `summary.json`, and `proxy-ledger.jsonl` (all 5 curator proxies `settled: true`, `pending_reserved_usd: 0`, `unsettled_requests: 0`, `breaches: 0`, `revoked: false`), while **Max reservation** is the proxy's pre-request worst-case estimate, not a charge:

| Curator session | Requests | Steps | Counted spend (USD) | USD / step | Max reservation (est., USD) | Max request charge (USD) | Prompt tokens | Cached tokens (share) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| S1 (`001-1-20`, accepted) | 4 | 20 | $0.05570710 | $0.00279 | $0.6905225 | $0.03292380 | 68,562 | 40,052 (58.4%) |
| S2 (`001-21-41`, accepted) | 13 | 21 | $0.14809825 | $0.00705 | $0.8260400 | $0.03196195 | 312,188 | 224,035 (71.8%) |
| S3 (`001-42-62`, accepted) | 8 | 21 | $0.07446105 | $0.00355 | $0.8273350 | $0.01688500 | 214,441 | 174,391 (81.3%) |
| S4 (`001-63-84`, rejected) | 8 | 22 | $0.07690635 | $0.00350 | $0.8301650 | $0.01917385 | 217,567 | 177,022 (81.4%) |
| S5 (`001-85-106`, rejected) | 18 | 22 | $0.28763395 | $0.01307 | $0.9380150 | $0.05179445 | 630,165 | 437,149 (69.4%) |
| **Curator total (5 sessions)** | **51** | **106** | **$0.64280670** | **$0.00606** | **$0.9380150** | **$0.05179445** | **1,442,923** | **1,052,649 (73.0%)** |

- Across the three accepted sessions (`v1`–`v3`, 25 requests, 62 covered steps), curator spend was **$0.27826640** (**$0.00449**/covered step); rejected sessions 4–5 spent **$0.36454030** (56.7% of curator spend) without publishing because of [#886](https://github.com/CVX-Hull/enactive/issues/886).
- Median curator session cost was **$0.0769** (mean $0.1286), well below the price pilot's $0.20 median. Every single-request proxy reservation stayed under $0.94 (below $1.00 and well inside the $8.00 session cap), and the largest real request charge was $0.0518.
- Curator prompt cache share (descriptive, from `summary.json` `tokens`) was **73.0%** overall (58.4%–81.4% per session; 390,121 cache-write tokens, 20,474 completion tokens, 3,489 reasoning tokens).

## Knowledge published and input routine recurrence

**Knowledge repository versions (`harness.curator.knowledge.Repository` over `.runtime/evidence/live-curator-run-859/knowledge`):**

| Version | Window | Facts (+new / superseded / retired) | Current articles (total records incl. superseded) | Article additions / revisions | Ontology types (+added) |
| --- | --- | --- | --- | --- | --- |
| `v0` | baseline | 0 | 0 (0) | 0 / 0 | 0 |
| `v1` | `001` 1–20 | 11 (+11 / 0 / 0) | 4 (4) | +4 / 0 | 4 (`interface`, `profession`, `scenario`, `setup_control`) |
| `v2` | `001` 21–41 | 23 (+12 / 0 / 0) | 8 (9) | +4 / 1 | 6 (`crafting`, `survival`) |
| `v3` | `001` 42–62 | 27 (+4 / 0 / 0) | 9 (12) | +1 / 2 | 6 (none) |

No fact was superseded or retired in `v1`–`v3` (no grooming ran). Sessions 4 and 5 submitted 5 and 9 additional facts and 2 and 1 additional articles (plus 2 article revisions each), none published because of [#886](https://github.com/CVX-Hull/enactive/issues/886).

**Input routine recurrence (descriptive, one-off read-only script over `operations.input_json` in `session.sqlite3` across 128 `input` operations):**

- **Single-call payloads:** 90 distinct canonical action payloads across 128 `input` calls; 16 payloads occurred at least twice, accounting for 54 of 128 calls (42.2%). Most frequent: `Shift+Y` + 2 s wait (9×), `TAB` (5×), `Shift+W` (5×), `ESC` then `Shift+V` (4×), `Shift+V` (4×), `ESC` then `m` (4×), 2 s wait (3×), `m` (3×), `Shift+Y` + `Shift+V` + `TAB` (3×).
- **Multi-call sequences:** 5 distinct consecutive 2-call pairs repeated at least twice (top two at 3× each: `[ESC, Shift+V] -> [TAB]` and `[Shift+W] -> [Shift+Y, 2 s wait]`; three pairs at 2× each); **0 repeated 3-call sequences** and **0 repeated 4-call sequences**.

## Lag simulation replay and outcome-table reading

Commands (read-only over the run directory, 0 briefing tokens, 1 actor, 135 player requests):

```sh
.venv/bin/python -m tools.memory_screen_checks schedule .runtime/evidence/live-curator-run-859/run --output SCHEDULE
.venv/bin/python -m tools.memory_screen_checks cut .runtime/evidence/live-curator-run-859/run --coverage schedule --schedule SCHEDULE --json
```

The schedule read 4 coverage changes, applied all 4, and left 0 out. Tag first-sight times (`versions.jsonl`) preceded the poll rows where the schedule replay applied each advance (`polls.jsonl` `ended_wall`): `v1` was first seen between player requests 33 and 34 and applied at turn 37 (covered 20); `v2` was first seen between requests 56 and 57 and applied at turn 58 (covered 41); `v3` was first seen between requests 73 and 74 and applied at turn 76 (covered 62):

| Row | Requests | Prompt p50 | Prompt p95 | Prompt max | Cuts | Cuts / reqs held back | Image drops | Cache write (vs recorded) | Share < 40k | Share < 60k |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `recorded` | 135 | 45,035 | 67,399 | 69,506 | 0 | 0 / 0 | 5 | 323,169 (1.000) | 0.407 | 0.830 |
| `no cut` | 135 | 43,590 | 63,010 | 64,910 | 0 | 0 / 0 | 5 | 311,134 (0.963) | 0.415 | 0.904 |
| `schedule` | 135 | 33,000 | 44,540 | 47,390 | 3 | 2 / 2 | 2 | 239,154 (0.740) | 0.830 | 1.000 |

- **Turn-by-turn breakdown (`tools.memory_screen_checks.simulate`).** Across turns 1–82 (while the curator was publishing), all three cuts fired on time with 0 held-back requests, 0 image drops, and a prompt maximum of **41,550 tokens**: turn 41 freed 20 turns (`v1` applied at turn 37), turn 61 freed 21 turns (`v2` applied at turn 58), and turn 82 freed 21 turns (`v3` applied at turn 76). Both held-back cuts and both image drops occurred at **turns 103 and 123**, and the full-run maximum of **47,390 tokens** occurred at **turn 122**, after `covered` froze at 62 because [#886](https://github.com/CVX-Hull/enactive/issues/886) prevented `v4` and `v5` from publishing.
- **Reading against the [corrected outcome table](2026-11-20-live-curator-run-price-correction-836.md#the-order-of-the-outcome-table-and-two-rows):**
  1. *Snapshots fail or pass their time bound?* **No** (21/21 succeeded, max lock hold 1.50 ms, `sealed()` accepted the closed store).
  2. *The run stops early, or the covered prefix cannot be established?* **Yes — this row decides.** Both the curator runner (after session 5 due to [#886](https://github.com/CVX-Hull/enactive/issues/886)) and the player (see [run ledger](../../data/evaluation/runs.jsonl)) stopped early. Figures are partial and any second run requires a new owner approval.
  3. *Secondary observations (subordinate to row 2):* player pace was above the cutoff on both clocks, backlog did not grow across the 5 sessions, curator cost ($0.0769 median/session) was below the pilot forecast, and across the three publishing windows (turns 1–82) the schedule fired 3 cuts with 0 held-back requests, 0 image drops, and prompt max 41,550 (full-run max 47,390 at turn 122, both below the 60,000 high mark).

## Evidence, archive list and limits

- **Sealed study:** `live-curator-run-859` under `.runtime/evidence/live-curator-run-859/` (tracked manifest [`data/evidence/live-curator-run-859.sha256`](../../data/evidence/live-curator-run-859.sha256) and [`data/evidence/index.json`](../../data/evidence/index.json): 343 files, 23,237,547 bytes, manifest SHA-256 `0867fe22581c9af2174938047d1c33a221e6afe61fbad44d8944e04ac469d2e6`), sealing the run directory (including `curator-runner/`), the runner configuration, the before-launch summary, the curator knowledge repository (`v0`–`v3` and session records), and the run's saved user directory (`Richwoods`). `curator-read.lock` was excluded by the `.lock` suffix rule; the empty repository lock file `knowledge/cdda.state/lock` is retained in the verified manifest. The owner's prior user directory (`Townsend`) was restored from `.runtime/archive/userdir-20261121T182701941889Z` with verified hashes.
- **Evaluator archive list:** Under the [owner's decision](../decisions/owner-decisions.md#the-paid-runs-session-joins-the-archive-index), session `2cda0867c34442f394299555aece7009` (`run: live-curator-run-859-2cda0867c344`, `study: live-curator-run-859`, versions `manifest: campaign-run/10`, `driver: player-driver/7`, `host: player-host/8`, `host_telemetry: 8`, `receipt: campaign-receipt/7`, `run_ending: campaign-watch-terminal/4`) is put forward as the twelfth `campaign-run/10` session for `data/evaluation/archive-sessions.json` in [#835](https://github.com/CVX-Hull/enactive/issues/835). Its knowledge repository is not carried over by that migration.
- **Limits.**
  - Partial run: one actor, no handoff, no grooming, and no live curator publication past step 62 because of [#886](https://github.com/CVX-Hull/enactive/issues/886).
  - The custodian's wait for an active snapshot read at store close was not exercised because the runner stopped 91.00 s before `store-closing.json` (and the last snapshot read ended 204.74 s before it).
  - The lag simulation models prompt size with 0 briefing tokens and no delivered-knowledge updates inside play; this run measures neither memory benefit nor delivery latency during play.
  - One admission cannot establish that the runner did or did not slow play, nor whether a multi-actor admission with handoffs maintains the same curator pace and cost.
