---
owner: lead
status: historical
kind: review
date: '2026-11-22'
scope: 'Zero-cost Go/No-Go decision brief for the coverage-gated context cut (#890) from sealed #889 evidence: real briefing sizes, growing-briefing and min_free=10 sensitivity, host-band cost and latency projection, architectural seams, S-MIGRATION archive impact, and registration of implementation leaf #900'
---

# Coverage-gated context-cut decision brief (#890)

## At a glance

- **Decision.** On 22 November 2026 the owner chose **Go**: register bounded `$0` implementation leaf [#900](https://github.com/CVX-Hull/enactive/issues/900) under [#664](https://github.com/CVX-Hull/enactive/issues/664) ahead of [#309](https://github.com/CVX-Hull/enactive/issues/309) (failover) and [#896](https://github.com/CVX-Hull/enactive/issues/896) (seven-day campaign), add `#889`'s two sealed `player-host/9` sessions to `data/evaluation/archive-sessions.json` on the `player-host/10` migration, include a small `.runtime/logs/` launch-safety fix, and close [#890](https://github.com/CVX-Hull/enactive/issues/890) ([owner decision](../decisions/owner-decisions.md#context-cut-go-and-archive-889)). No paid run is authorized by this brief; **$0** spent, no game launched.
- **Why Go.** On `#889`'s sealed evidence ([2026-11-22-live-validation-run-889.md](2026-11-22-live-validation-run-889.md)), live curation kept pace across **17 of 17** consecutive 20–23-step windows (`v1`–`v17`, `96.7%` covered, bounded backlog `4–11` in steady state), and real `knowledge.mjs` briefings stayed compact (`237` tokens at `v1` to **`2,815` tokens** at `v17`). Even modelling growing fresh briefings at every cut up to `~2,769` tokens (`3.0x` raw lead+world text, matching `v17`'s exact formatted briefing) with `min_free = 10`, coverage-gated cutting holds `prompt_p50` to **35,999** (`-59%`), `prompt_max` to **51,311** (`max(prompt - briefing) = 50,438 <= 60,000`), slashes simulated cache writes by **60.8%** (`0.392x`), and reduces projected player spend across `#889`'s own `host-summary` prompt bands from **~$4.14 to ~$2.18 (-47%)** with median response time dropping from **~6.08 s to ~4.86 s (-20%)**.

[Issue #890](https://github.com/CVX-Hull/enactive/issues/890) · [Implementation leaf #900](https://github.com/CVX-Hull/enactive/issues/900) · [Live validation run #889](2026-11-22-live-validation-run-889.md) · [Context-cut design](../design/coverage-gated-context-cut.md)

## Real briefing sizes in `#889` (`v1`–`v18`)

Measured read-only (`$0`) directly via `delivery(dk, ids, "briefing")` in `tools/player_host/knowledge.mjs` over `#889`'s sealed `curator-runner/delivered/v*.json` files (and `v18` exported from sealed `.runtime/evidence/live-validation-run-889/knowledge/cdda` into a temporary directory, approximated at 4 UTF-8 bytes/token):

| Version | Articles | Facts | `delivered-knowledge.json` bytes | Formatted `knowledge.mjs` full briefing (all leads) | Formatted `knowledge.mjs` index-only (0 leads) |
| --- | ---: | ---: | ---: | ---: | ---: |
| `v1` | 4 | 15 | 9,904 B | 947 B (~237 tok) | 936 B (~234 tok) |
| `v5` | 8 | 52 | 33,031 B | 3,111 B (~778 tok) | 3,088 B (~772 tok) |
| `v10` | 13 | 92 | 58,768 B | 7,252 B (~1,813 tok) | 7,214 B (~1,804 tok) |
| `v14` | 17 | 113 | 74,694 B | 9,520 B (~2,380 tok) | 9,470 B (~2,368 tok) |
| `v17` | 22 | 135 | 91,924 B | 11,258 B (~2,815 tok) | 11,193 B (~2,799 tok) |
| `v18` (groomed) | 31 | 131 | 98,451 B | — (raw leads+world 5,710 B / ~1,428 tok) | — |

Even at `v17` (after 355 operations and 17 live windows), a complete formatted briefing with every article lead takes under **3,000 tokens** — roughly 5% of the `60,000`-token high mark.

## Growing-briefing & `min_free = 10` sensitivity on `#889`

To address the constant-briefing limitation disclosed in [measurement tools](../contracts/measurement-tools.md#runner-records-and-schedule-replay), `#889`'s recorded coverage schedule (`369` player requests, `17` live updates, `30` reminders) was re-simulated read-only (`$0`) with:
1. **`min_free = 10`** (per [the cut design](../design/coverage-gated-context-cut.md#the-cut), vs default `1` in `CutModel`): produced **identical** results (`0` cuts freed fewer than 10 turns).
2. **Fresh-briefing growth at every cut** (replacing the actor's briefing size at each cut with `1.0x`, `2.0x`, and `3.0x` of the covered version's raw lead+world text — where `3.0x` reaches `2,769` tokens, matching `v17`'s exact formatted `knowledge.mjs` briefing of `2,815` tokens), while checking `high_mark` (`60,000`) and `low_mark` (`20,000`) strictly above briefing size.
3. **Band cost & latency projection** applying `#889`'s own observed `tools.evaluate host-summary` prompt-band means (`<20k`: `$0.0022` / `2.0 s`; `20k–60k`: `$0.0061` / `5.0 s`; `60k–100k`: `$0.0096` / `6.7 s`; `100k–150k`: `$0.0159` / `7.3 s`; `>150k`: `$0.0174` / `5.8 s`) to each simulated request's prompt size:

| Scenario (`#889`, 369 reqs) | Prompt p50 | Prompt p95 | Prompt max | Max briefing | Max above briefing | Cuts | Held back | Image drops | Cache write (vs rec.) | Band-est. play spend | Band-est. med. lat. |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `recorded` (`#889` real) | 88,458 | 162,685 | 171,996 | 45 | 171,951 | 0 | 0 | 17 | 1,850,815 (1.000x) | $4.14 | 6.08 s |
| `schedule` (const `b=45`, `min_free=1` or `10`) | 34,379 | 44,867 | 50,483 | 45 | 50,438 | 14 | 2 | 3 | 700,182 (0.378x) | $2.18 | 4.85 s |
| `schedule` (`1.0x` growing fresh briefing) | 34,888 | 45,386 | 50,729 | 923 | 50,438 | 14 | 2 | 3 | 707,929 (0.382x) | $2.18 | 4.85 s |
| `schedule` (`2.0x` growing fresh briefing) | 35,476 | 45,836 | 51,020 | 1,846 | 50,438 | 14 | 2 | 3 | 716,351 (0.387x) | $2.18 | 4.86 s |
| `schedule` (`3.0x`, `~2,769` tok ≈ real `v17`) | 35,999 | 46,495 | 51,311 | 2,769 | 50,438 | 14 | 2 | 3 | 724,773 (0.392x) | $2.18 | 4.86 s |

- **Key result:** Fresh-briefing growth adds less than 1.5 percentage points to cache writes (`0.378x` → `0.392x`) and leaves `prompt_max` (`51,311`), `max(prompt - briefing)` (`50,438 <= 60,000`), cuts (`14`), held-back requests (`2`), and image drops (`3`) completely intact.
- **Warm-up & outlier behavior:** All `2` held-back requests and `3` image drops occurred in requests `#41`, `#61`, `#105` (before `v1` applied on poll row `#43`, before `v2` at `#63`, and during S04's `164.86 s` outlier). Across the remaining 264 steady-state requests (`#106`–`#369`), all 12 consecutive cuts fired cleanly with `0` held-back requests and `0` image drops. In real play, block-20 image eviction remains the safe fallback if an outlier curator session ever temporarily delays coverage.
- **Economic & failover synergy:** Saving `~$2.00` in player spend per ~360-decision admission offsets roughly two-thirds of `#889`'s `$3.01` live curator spend (and scales linearly across seven-day runs of ~2,000 decisions under [#145](https://github.com/CVX-Hull/enactive/issues/145)). Landing the cut before [#309](https://github.com/CVX-Hull/enactive/issues/309) also prevents a second consecutive `player-host` schema bump and shrinks any failover cold cache-write spike by ~3x.

## Architectural seams, S-MIGRATION impact, and handoff note

Code inspection on `main` (`500c4b53`) identified four concrete engineering requirements carried directly into [#900](https://github.com/CVX-Hull/enactive/issues/900):

1. **Unbroken `covered_prefix` seam (`tools/curator_host/live_runner.py` → `tools/campaign_player.py`):** `vN.json`'s `curator-coverage/2` stamp records only the end of one window, whereas `Runner.coverage()['covered_prefix']` stops at any rejected/nothing-submitted/restored gap. `live_runner.py` must forward unbroken `covered_prefix.end.operation` (and `restore` invalidation) immediately after `poll()`, never relying on single-window `vN.coverage.last_step`.
2. **`operation_id` turn tracking (`tools/player_host/host.mjs`):** `host.mjs` knows 32-hex `actorId` and `operation_id` (not integer `step`). Tracking each turn's last creating `operation_id` lets `host.mjs` check coverage directly against `covered_prefix.end.operation`, latch cut prefixes for byte-identical stability between cuts, inject `[freshBriefing, cutMarkerWithSourceIds]` without colliding recall flights, run `projectImageContext` post-cut, and emit `context-cut` telemetry (excluded from `composition_pairs` in `tools/host_analysis.py`).
3. **`player-host/10` S-MIGRATION & `#889` closed archive index (`harness/evaluation/core/sources.py`, `data/evaluation/archive-sessions.json`):** Adding closed cut configuration bumps `player-host/9` → `player-host/10` (`telemetry_version: 10`). With the owner's 22 November approval, `#889`'s two sealed `campaign-run/12` + `player-host/9` sessions (`a02d8069d0434813a41acc7009217da6` and `49964eb42a7d4dabaef0c5ff6230a9be`) join the closed archive index in `#900` so offline evaluation and replay tools continue reading `#889`.
4. **Why no separate paid run is scheduled just to force `001 -> 002` handoff:** Once `#900` keeps prompts at `35k–51k` tokens, ordinary admissions will rarely reach the `229k`-token `context-capacity` handoff trigger (`host.mjs`). Within-admission handoff remains verified by offline host, driver, and stand-in suites (`tools/player_host/test/handoff.test.mjs`, `tests/test_player_host_contract.py`, `tests/live_curator_stand_in_run.py`), while cross-admission briefing adoption is exercised across multi-admission campaigns under [#896](https://github.com/CVX-Hull/enactive/issues/896).
