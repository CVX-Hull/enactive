---
owner: lead
status: historical
kind: measurement
date: '2026-11-27'
scope: '$0 offline #998 curator-lag and simulated flex-queueing/429 replay (2,504 requests across Admissions 01–04) evaluating bounded uncovered-cut fallback policies for #1037 on player-host/13'
---

# `#1037` `$0` offline `#998` curator-lag and `flex`/429 replay

## At a glance

- **Question.** Under recorded `default`-tier curator lag, simulated non-real-time `flex` queueing (`+120s`, `+300s`, `+600s + 15m 429 burst`), and a total curator stall across sealed `#998` Admissions 01–04 (`2,504` cut-check requests, `$0` provider spend), how do candidate uncovered-cut fallback policies trade off hard `context-capacity` stops, prompt-token / cache-read growth, working-state retention, and unsynthesized-turn exposure?
- **Answer — Tiered `100k` uncovered-cut fallback (`min(max(high_mark, hard_limit - low_mark), ceil(high_mark * 5 / 3))` + hard-fit rescue on `player-host/13`) dominates the Pareto frontier (`$0` spend, zero schema bump).**
  - **Baseline (`player-host/13`, covered-only):** `0/4` stops on recorded `default` tier (`49,105` mean prompt tokens, `93,168` peak), swells `+32.3%` (`64,951`) at `+120s`, `+56.4%` (`76,813`) at `+300s`, and `+102.8%` (`99,586`, peak `194,759`) under heavy `flex` + 15m `429` burst, and **halts `3/4` admissions with `context-capacity` stops** (`1,652/2,504` requests completed) under a total curator stall.
  - **Tiered `100k` fallback (owner-approved):** **Identical to baseline on recorded `default` tier** (`0` uncovered cuts, `81/81` covered cuts, `49,105` mean prompt tokens), incurs only `1` uncovered cut under `+120s` mild `flex`, cuts mean prompt tokens by `-12.9%` at `+300s` (`66,910`) and **`-34.5%` under heavy `flex` + 15m `429`** (`65,270`, peak `101,045` vs. `194,759`), and eliminates **all `3/4` capacity stops** under a total curator stall (`0/4` stops, `2,504/2,504` completed, `-51.4%` mean prompt tokens). Across all lag scenarios (`+120s` through total stall), `85.5%–98.8%` of uncovered-dropped turns (`53/62 = 85.5%` under mild `+120s` `flex`, and `96.9%–98.8%` under moderate/heavy/stall) fall within the recorded `#998` curator's final on-disk coverage prefix, and **`100%` of dropped frames stay listed in `source_ids`** alongside preserved `player_agenda` and `recent_intents`.
  - **Immediate `high_mark` (`60k`) fallback:** Achieves the lowest mean prompt tokens (`~39k`) across all regimes, but drops `1,854` uncovered turns even on recorded `default` tier where the curator was only seconds away from publishing.
  - **Rescue-only (`hard_limit = 245,760`):** Prevents the `3/4` stall stops, but allows mean prompt tokens to double under heavy `flex` (`98,027`) and thrashes with `740` single-turn rescues (`170,629` mean prompt tokens, `1`-token minimum headroom) under a total curator stall.
- **What is not known.** Offline replay holds historical player tool sequences fixed and estimates tokens via the manifest-based heuristic of `tools/player_host_replay_benchmark.py`; it does not measure live gameplay quality changes when unsynthesized turns leave the player's raw prompt before curator publication, nor real provider `flex` queue latencies (gated separately under `#1047`).
- **Owner decisions.** Settled on 27 November 2026 in [uncovered-cut fallback decision](../decisions/owner-decisions.md#uncovered-cut-fallback-1037), narrowing `context-cut-go-and-archive-889` to adopt Tiered `100k` uncovered-cut fallback on `player-host/13`.

[Issue #1037](https://github.com/CVX-Hull/enactive/issues/1037) · [Player host contract](../contracts/player-host.md#coverage-gated-context-cut) · [Risk register](../risks.md)

## Replay matrix (`#998` Admissions 01–04, `2,504` requests)

Reproducible command against the sealed `#998` evidence store (`$0` spend):

```bash
python -m tools.player_host_replay_benchmark --lineage 998 --lag-replay
```

The `Later Cov On Disk` column counts uncovered-dropped turns whose turn index is at or before the final curator-covered turn in the recorded `#998` disk trace (showing what fraction of turns dropped early from live context were covered on disk in the recorded `#998` run; under simulated total stall, this measures what the unblocked `#998` curator covered on disk).

| Scenario | Arm | Stops | Completed | Edge Holds | Cov / Uncov Cuts | Rescues | Mean Prompt Tok | Peak Tok | Min Headroom | Uncov Turns (Max/Cut) | Later Cov On Disk | Frames Retained |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Recorded `default` (`0s`) | Baseline | 0/4 | 2504/2504 | 78 | 81 / 0 | 0 | 49,105 | 93,168 | 152,592 | 0 (0) | 0/0 | 0/0 |
| Recorded `default` (`0s`) | Immediate `60k` | 0/4 | 2504/2504 | 0 | 27 / 83 | 0 | 40,359 | 61,095 | 184,665 | 1,854 (29) | 1,757/1,854 | 1,649/1,649 |
| Recorded `default` (`0s`) | Tiered `90k` | 0/4 | 2504/2504 | 78 | 81 / 1 | 0 | 48,861 | 90,205 | 155,555 | 68 (68) | 0/68 | 65/65 |
| Recorded `default` (`0s`) | **Tiered `100k`** | **0/4** | **2504/2504** | **78** | **81 / 0** | **0** | **49,105** | **93,168** | **152,592** | **0 (0)** | **0/0** | **0/0** |
| Recorded `default` (`0s`) | Rescue-only | 0/4 | 2504/2504 | 78 | 81 / 0 | 0 | 49,105 | 93,168 | 152,592 | 0 (0) | 0/0 | 0/0 |
| Mild `flex` (`+120s`) | Baseline | 0/4 | 2504/2504 | 84 | 75 / 0 | 0 | 64,951 | 104,192 | 141,568 | 0 (0) | 0/0 | 0/0 |
| Mild `flex` (`+120s`) | Immediate `60k` | 0/4 | 2504/2504 | 0 | 0 / 95 | 0 | 39,150 | 61,095 | 184,665 | 2,379 (35) | 2,282/2,379 | 2,097/2,097 |
| Mild `flex` (`+120s`) | **Tiered `100k`** | **0/4** | **2504/2504** | **86** | **77 / 1** | **0** | **64,232** | **96,414** | **149,346** | **62 (62)** | **53/62** | **58/58** |
| Moderate `flex` (`+300s`) | Baseline | 0/4 | 2504/2504 | 79 | 61 / 0 | 0 | 76,813 | 121,507 | 124,253 | 0 (0) | 0/0 | 0/0 |
| Moderate `flex` (`+300s`) | Immediate `60k` | 0/4 | 2504/2504 | 0 | 0 / 95 | 0 | 39,142 | 61,095 | 184,665 | 2,422 (35) | 2,325/2,422 | 2,137/2,137 |
| Moderate `flex` (`+300s`) | **Tiered `100k`** | **0/4** | **2504/2504** | **98** | **53 / 12** | **0** | **66,910** | **101,047** | **144,713** | **873 (93)** | **846/873** | **756/756** |
| Heavy `flex` + 15m `429` | Baseline | 0/4 | 2504/2504 | 58 | 44 / 0 | 0 | 99,586 | 194,759 | 51,001 | 0 (0) | 0/0 | 0/0 |
| Heavy `flex` + 15m `429` | Immediate `60k` | 0/4 | 2504/2504 | 0 | 0 / 95 | 0 | 39,116 | 61,095 | 184,665 | 2,420 (35) | 2,325/2,420 | 2,135/2,135 |
| Heavy `flex` + 15m `429` | **Tiered `100k`** | **0/4** | **2504/2504** | **68** | **9 / 22** | **0** | **65,270** | **101,045** | **144,715** | **2,026 (147)** | **1,999/2,026** | **1,805/1,805** |
| Heavy `flex` + 15m `429` | Rescue-only | 0/4 | 2504/2504 | 75 | 55 / 0 | 0 | 98,027 | 194,759 | 51,001 | 0 (0) | 0/0 | 0/0 |
| Total curator stall | Baseline | 3/4 | 1652/2504 | 4 | 0 / 0 | 0 | 132,766 | 245,520 | 240 | 0 (0) | 0/0 | 0/0 |
| Total curator stall | Immediate `60k` | 0/4 | 2504/2504 | 0 | 0 / 95 | 0 | 38,936 | 61,095 | 184,665 | 2,420 (35) | 2,325/2,420 | 2,135/2,135 |
| Total curator stall | **Tiered `100k`** | **0/4** | **2504/2504** | **26** | **0 / 23** | **0** | **64,492** | **101,045** | **144,715** | **2,231 (175)** | **2,204/2,231** | **1,965/1,965** |
| Total curator stall | Rescue-only | 0/4 | 2504/2504 | 46 | 0 / 0 | 740 | 170,629 | 245,759 | 1 | 939 (21) | 939/939 | 848/848 |

## Invariants preserved in `#1037`

- `covered_through_operation_id` stays strictly pinned to the curator's verified `coverage-update-entry/1` frontier (or `null` before first coverage); uncovered cuts never advance `covered_prefix`.
- `BEGIN CONTEXT CUT` reports the exact outstanding `uncovered_turns` count (healing back toward `0` as curator coverage overtakes previously-omitted turns) and uses a truthful header when `uncovered_turns > 0`.
- `player_agenda`, `recent_intents`, and 100% of dropped `source_ids` (current-session runtime store + same-lineage `player-source-index/1`) remain preserved across every uncovered cut.
- `restored: true` invalidation, accepted `orderly_stop` fencing, and unknown `player-transport/2` operation fencing apply identically to uncovered cuts.
- Curator disk WAL and `host.jsonl` ingestion are unchanged.
