---
owner: lead
status: historical
kind: measurement
date: '2026-11-27'
scope: '$0 offline #998 curator cadence replay (20/40, 40/40, 40/60, 60/60, and cut-demand 20..60) paired with #1037 tiered 100k uncovered-cut fallback across recorded default and simulated flex/429 lag regimes'
---

# `#1027` `$0` offline `#998` curator cadence replay

## At a glance

- **Question.** On top of `#1037`'s tiered `100k` uncovered-cut fallback (`player-host/13`), how do wider curator window cadences (`40/40`, `40/60`, `60/60`, and cut-demand `20..60`) trade off curator window count against player prompt tokens, uncovered cuts, and context headroom across recorded `default` and simulated `flex`/`429` lag regimes on sealed `#998` Admissions 01–04 (`2,504` player requests, `$0` spend)?
- **Answer — `40/60` (`trigger_steps=40, ceiling_steps=60`) reduces curator windows by `20.7%–48.2%` across all four lag regimes with `0/4` stops, `0` hard-fit rescues, `100%` frame retention in `source_ids`, and *fewer* uncovered turns under moderate `+300s` `flex` lag (`1,291` vs. `2,049`, `-37.0%`).**
  - **Recorded `default` (`0s` lag):** `40/60` cuts curator windows from `112` to `58` (`-48.2%`), incurring only `1` uncovered cut (`54` turns, `49/49` frames retained, peak `101,051` tokens). `cut-demand (20..60)` cuts windows by `-27.7%` (`112 -> 81`) with `0` uncovered cuts.
  - **Mild `flex` (`+120s`):** `40/60` cuts windows by `-28.4%` (`81 -> 58`) with mean prompt tokens nearly flat (`66,599` vs. `65,360`, `+1.9%`).
  - **Moderate `flex` (`+300s`):** `40/60` cuts windows by `-20.7%` (`58 -> 46`) AND increases covered cuts (`7 -> 22`) while cutting uncovered turns by `-37.0%` (`2,049 -> 1,291`), because a `60`-step ceiling drains backlog faster per slow queueing round-trip than a `40`-step ceiling.
  - **Heavy `flex` + `15m` `429` burst (`+600s + 15m`):** `40/60` and `cut-demand (20..60)` both cut windows by `-31.0%` (`58 -> 40`) with `0/4` stops, `0` rescues, and `>= 144,715` tokens minimum headroom.
- **What is not known.** The replay fixes curator window service time at `90 s` plus scenario lag (`default` through `+600s + 15m`) and holds historical player tool sequences fixed; actual `flex` queue latency and per-window extraction quality at `40–60` steps require paid live measurement (gated separately under `#1047`).

[Issue #1027](https://github.com/CVX-Hull/enactive/issues/1027) · [Curator component](../components/curator.md#runner-windows) · [`#1037` lag replay](2026-11-27-uncovered-cut-lag-replay-1037.md)

## Replay matrix (`#998` Admissions 01–04, `2,504` requests)

Reproducible command against the sealed `#998` evidence store (`$0` spend):

```bash
python -m tools.player_host_replay_benchmark --lineage 998 --cadence-replay
```

| Scenario | Cadence | Windows (Delta) | In-Play Pubs | Stops | Cov / Uncov Cuts | Rescues | Mean Prompt Tok | Peak Tok | Min Headroom | Uncov Turns (Max/Cut) | Frames Retained |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Recorded `default` (`0s`) | `20/40` (baseline) | 112 (0.0%) | 107 | 0/4 | 107 / 0 | 0 | 48,898 | 92,321 | 153,439 | 0 (0) | 0/0 |
| Recorded `default` (`0s`) | `40/40` | 58 (-48.2%) | 53 | 0/4 | 52 / 1 | 0 | 56,521 | 101,051 | 144,709 | 54 (54) | 49/49 |
| Recorded `default` (`0s`) | **`40/60`** | **58 (-48.2%)** | **53** | **0/4** | **52 / 1** | **0** | **56,521** | **101,051** | **144,709** | **54 (54)** | **49/49** |
| Recorded `default` (`0s`) | `60/60` | 39 (-65.2%) | 35 | 0/4 | 28 / 8 | 0 | 61,600 | 101,047 | 144,713 | 535 (74) | 459/459 |
| Recorded `default` (`0s`) | `cut-demand (20..60)` | 81 (-27.7%) | 74 | 0/4 | 74 / 0 | 0 | 53,456 | 96,270 | 149,490 | 0 (0) | 0/0 |
| Mild `flex` (`+120s`) | `20/40` (baseline) | 81 (0.0%) | 73 | 0/4 | 72 / 1 | 0 | 65,360 | 100,515 | 145,245 | 59 (59) | 50/50 |
| Mild `flex` (`+120s`) | `40/40` | 58 (-28.4%) | 50 | 0/4 | 47 / 4 | 0 | 66,599 | 101,117 | 144,643 | 265 (77) | 231/231 |
| Mild `flex` (`+120s`) | **`40/60`** | **58 (-28.4%)** | **50** | **0/4** | **47 / 4** | **0** | **66,599** | **101,117** | **144,643** | **265 (77)** | **231/231** |
| Mild `flex` (`+120s`) | `60/60` | 39 (-51.9%) | 32 | 0/4 | 22 / 11 | 0 | 66,228 | 101,047 | 144,713 | 806 (98) | 705/705 |
| Mild `flex` (`+120s`) | `cut-demand (20..60)` | 77 (-4.9%) | 69 | 0/4 | 68 / 1 | 0 | 65,701 | 100,723 | 145,037 | 58 (58) | 49/49 |
| Moderate `flex` (`+300s`) | `20/40` (baseline) | 58 (0.0%) | 39 | 0/4 | 7 / 22 | 0 | 64,708 | 101,053 | 144,707 | 2,049 (136) | 1,817/1,817 |
| Moderate `flex` (`+300s`) | `40/40` | 58 (0.0%) | 38 | 0/4 | 9 / 22 | 0 | 64,605 | 101,044 | 144,716 | 1,980 (120) | 1,755/1,755 |
| Moderate `flex` (`+300s`) | **`40/60`** | **46 (-20.7%)** | **38** | **0/4** | **22 / 16** | **0** | **66,260** | **101,044** | **144,716** | **1,291 (116)** | **1,123/1,123** |
| Moderate `flex` (`+300s`) | `60/60` | 39 (-32.8%) | 32 | 0/4 | 14 / 19 | 0 | 65,214 | 101,047 | 144,713 | 1,653 (116) | 1,456/1,456 |
| Moderate `flex` (`+300s`) | `cut-demand (20..60)` | 46 (-20.7%) | 38 | 0/4 | 22 / 17 | 0 | 66,324 | 101,053 | 144,707 | 1,359 (114) | 1,190/1,190 |
| Heavy `flex` + 15m `429` | `20/40` (baseline) | 58 (0.0%) | 18 | 0/4 | 2 / 23 | 0 | 64,761 | 101,045 | 144,715 | 2,194 (176) | 1,951/1,951 |
| Heavy `flex` + 15m `429` | `40/40` | 58 (0.0%) | 18 | 0/4 | 2 / 23 | 0 | 65,242 | 101,045 | 144,715 | 2,229 (151) | 1,975/1,975 |
| Heavy `flex` + 15m `429` | **`40/60`** | **40 (-31.0%)** | **18** | **0/4** | **2 / 23** | **0** | **64,943** | **101,045** | **144,715** | **2,180 (150)** | **1,930/1,930** |
| Heavy `flex` + 15m `429` | `60/60` | 39 (-32.8%) | 17 | 0/4 | 1 / 23 | 0 | 65,074 | 101,045 | 144,715 | 2,249 (169) | 1,995/1,995 |
| Heavy `flex` + 15m `429` | `cut-demand (20..60)` | 40 (-31.0%) | 18 | 0/4 | 2 / 23 | 0 | 64,704 | 101,045 | 144,715 | 2,178 (175) | 1,942/1,942 |
