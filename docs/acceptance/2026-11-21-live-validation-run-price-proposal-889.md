---
owner: lead
status: historical
kind: measurement
date: '2026-11-21'
scope: 'Price proposal, frozen package plan, runner configuration, pace cutoff, boundary-grooming command and upgraded #859 delivery-aware schedule replay for the first full live validation admission (#889, prepared under #895)'
---

# Price proposal for the full live validation run (#889)

## At a glance

One fresh `Wilderness / Campground / Survivor` admission (`S1`, `campaign-run/12`)
crossing a real in-session actor handoff (`001 -> 002`) with the live curator runner
publishing under `curator-fact/4`, live in-session knowledge delivery enabled
(`live_knowledge_updates: true`), and one post-admission boundary-grooming session is
forecast at about **$4.00 to $5.80** (up to about **$7.50** if curator sessions average
the [#836](2026-11-20-live-curator-run-price-proposal-836.md) price-pilot median instead
of the [#859](2026-11-21-live-curator-run-859.md) live accepted rate):

- **Play (one admission, ~300–400 decisions across `001 -> 002`):** forecast **$2.50–$3.50**, package limit **`$5.50`** (`ending_reserve.usd: "1.40"`, leaving `$4.10` for the work phase).
- **Live curator runner (~15–20 sequential 20-step windows):** forecast **$1.35–$1.90** at `#859` accepted rates (up to `$3.60` at the `#836` pilot median), runner cap **`$15.00`** with per-session cap **`$8.00`**.
- **Post-admission boundary grooming (1 session after the store seals):** forecast **$0.15–$0.40** (`$0` if nothing was published, skipped cleanly), session cap **`$8.00`**.
- **Unallocated margin:** **`$1.50`**.
- **Planning ceiling:** **`$30.00`** (`$5.50 + $15.00 + $8.00 + $1.50`).

**`$30.00` is a planning ceiling, not a hard billing cap.** `$16.00` of the `$30.00`
ceiling is proxy worst-case reservation headroom (`$8.00` across the live runner's
session cap and `$8.00` for the separate post-admission boundary-grooming proxy), not
expected spend. The only hard billing cap is the credit limit on the provider key,
which the owner sets and the code cannot read. Nothing here is approved, no game was
launched, `.runtime/user/` was not touched, and **$0** was spent preparing this
proposal.

[First paid live run (#859)](2026-11-21-live-curator-run-859.md) · [Joanna Campground run (#803)](2026-11-19-joanna-campground-memory-803.md) · [Price proposal (#836)](2026-11-20-live-curator-run-price-proposal-836.md) · [Price corrections (#836)](2026-11-20-live-curator-run-price-correction-836.md) · [Owner decision](../decisions/owner-decisions.md#post-838-validation-cut-failover-and-seven-day-sequence)

## Why `#889` needs a larger work budget than `#859`

The first paid live run ([#859](2026-11-21-live-curator-run-859.md)) gave the player
`spend_limit_usd: "3.00"` with `ending_reserve.usd: "1.40"` (`$1.60` work budget),
stopped at 127 decisions on actor `001` (`$0.79` player spend; early curator stop at
session 5 from [#886](https://github.com/CVX-Hull/enactive/issues/886), now fixed), and
therefore did **not** exercise a real in-session actor handoff, live mid-admission
delivery (`live_knowledge_updates: true`), `curator-fact/4` world/game scope separation
in live play, or post-admission boundary grooming.

To exercise all of those mechanisms in one real `Wilderness / Campground / Survivor`
admission (`S1`), the player must have enough work-phase budget to cross an ordinary
`001 -> 002` handoff:

| Evidence source | Decisions | Actors | Wall (s) | Player spend (USD) | USD / decision | Pace (dec/min; op/min) |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `wilderness-803-first-eligible-8a4badef08b9` (`#803`, same `S1` mission) | 405 | 2 (`001 -> 002` at req 210) | 3,423 | $3.47 | $0.00856 | 7.10; 7.31 |
| `farm-788-equipment-return-e3da8d1f2714` (`#788`) | 265 | 1 | 2,312 | $2.78 | $0.01047 | 6.88; 7.60 |
| `two-wake-772-farm-58ee9279783f45ba8ffd469e1c6357b9` (`#772`) | 310 | 1 | 2,488 | $3.58 | $0.01156 | 7.48; 7.86 |
| `live-curator-run-859-2cda0867c344` (`#859`, partial, 1 actor) | 127 | 1 | 783 | $0.79 | $0.00623 | 9.74; 10.46 |

At `#803`'s rate (`$3.47` across 405 decisions and two actors), a `$4.10` work budget
(`spend_limit_usd: "5.50"` minus `ending_reserve.usd: "1.40"`) provides room for ~350–450
decisions and a real `001 -> 002` handoff without stopping prematurely like `#859` or
risking a multi-hour run.

## Curator cost and reservation inputs

| Input | Figure | Source |
| --- | --- | --- |
| Live accepted curator session cost | median $0.0745 (S1–S3: $0.0557, $0.1481, $0.0745); mean $0.0928; **$0.00449 / covered step** | `#859` accepted sessions `v1`–`v3` (62 steps) |
| All five `#859` sessions (incl. 2 rejected by `#886`) | median $0.0769; mean $0.1286; $0.00606 / step | `#859` sessions S1–S5 (106 steps) |
| Session price pilot (offline sealed windows) | median $0.20, range $0.11–$0.57 | `#836` price pilot (10 sessions) |
| Live session wall time | 49.40 s to 113.73 s; every session ended before the next 20-step window filled | `#859` sessions S1–S5 |
| Largest single-request proxy reservation in `#859` | $0.9380 (at `max_output_tokens: 16384`; largest real charge $0.0518) | `#859` `proxy-ledger.jsonl` |
| Largest single-request proxy reservation in `#836` pilot | $1.12–$1.41 at 32,768 max output (~$1.00–$1.29 at 16,384) | `#859` `before-launch-summary.md` |

The live `Runner` (`harness/curator/runner.py`) enforces no hardcoded session count cap;
it stops when `cap_usd` cannot fit the next session's proxy reservation, on two
consecutive rejected or failed sessions, or when the trace store closes. Across 300–400
operations (~15–20 sequential 20-step windows):

- At `#859`'s accepted rate (`$0.00449`/step), 300–400 steps forecast **$1.35–$1.80** (or
  **$1.39–$1.86** at the `$0.0928` accepted session mean).
- At `#836`'s pilot median (`$0.20`/session), 15–18 sessions forecast **$3.00–$3.60**.
- Setting `session_cap_usd: "8.00"` and `cap_usd: "15.00"` leaves at least `$8.00` of
  proxy reservation headroom even after `$7.00` of cumulative curator spend, preventing
  artificial mid-run reservation stalls on later windows when the store is larger.

## Upgraded `#859` schedule replay with recorded deliveries (`#846` preparation)

Before proposing `#889`, the upgraded `tools.memory_screen_checks cut --recorded-deliveries`
was run read-only (`$0`) over the sealed `#859` admission (`1` actor, `135` player
requests, `4` recorded coverage changes, `v18` starting briefing of `1,457` estimated
tokens, `12` delivered reminders totalling `5,473` estimated tokens, `0` live updates,
`0` unmatched deliveries):

```sh
.venv/bin/python -m tools.memory_screen_checks schedule .runtime/evidence/live-curator-run-859/run --output SCHEDULE
.venv/bin/python -m tools.memory_screen_checks cut .runtime/evidence/live-curator-run-859/run --coverage schedule --schedule SCHEDULE --recorded-deliveries
```

| Row | Requests | Prompt p50 | Prompt p95 | Prompt max | Cuts | Cuts / reqs held back | Image drops | Cache write (vs recorded) | Share < 40k | Share < 60k |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `recorded` | 135 | 45,035 | 67,399 | 69,506 | 0 | 0 / 0 | 5 | 323,169 (1.000) | 0.407 | 0.830 |
| `no cut` (with recorded deliveries) | 135 | 47,871 | 69,474 | 71,414 | 0 | 0 / 0 | 5 | 342,609 (1.060) | 0.326 | 0.770 |
| `schedule` (with recorded deliveries) | 135 | 35,663 | 48,341 | 51,191 | 3 | 2 / 2 | 2 | 259,884 (0.804) | 0.681 | 1.000 |

Including `#859`'s recorded `v18` briefing and `12` reminders brings the simulated
`no cut` row closely in line with the recorded trace (`47,871 / 69,474 / 71,414` and
`1.060x` cache write vs recorded `45,035 / 67,399 / 69,506` and `1.000x`), confirming
that the upgraded replay is ready to evaluate `#889`'s multi-window, live-update, and
post-handoff briefing trace under `#846`.

## The run proposed (`#889`)

### Frozen package plan (`campaign-run/12`)

- **Scenario and world:** One fresh `Wilderness / Campground / Survivor` admission (`S1`),
  using `#803`/`#859`'s mission text (`prompt.txt`), with explicit world label
  `labels.world: "campground-889"`, `labels.arm: "live-validation-run"`,
  `labels.start: "S1"`, `labels.scenario: "campground"`, `labels.lineage: null`,
  `labels.admission: null`.
- **Starting delivered knowledge (`delivered-knowledge/2`):** Exported empty (`v0`, `0`
  articles, `0` facts) bound to `campground-889`:
  ```sh
  .venv/bin/python -m tools.knowledge_export --empty --world campground-889 --package .runtime/computer-sessions/PACKAGE
  ```
- **Live knowledge updates:** `live_knowledge_updates: true`. As the live curator
  publishes `v1`, `v2`, … into `.runtime/knowledge/live-validation-run-889/cdda`,
  verified updates reach the running actor via `knowledge-delivery` (`update`) and
  become the next actor's frozen file on `001 -> 002` handoff.
- **Player route (`player-host/9`):** `openai/gpt-6.1-terra`, `effort: "medium"`, via
  OpenRouter pinned to `openai` (`allow_fallbacks: false`, `only: ["openai"]`,
  `order: ["openai"]`, `require_parameters: true`, `service_tier: "default"`),
  `contextWindow: 262144`, `maxTokens: 16384`, `max_context_images: 39`,
  `context_image_block: 20`, `context_reserve_tokens: 32768`,
  `request_timeout_seconds: 60`, `unpriced_request_usd: "0.4096"`.
- **Recall route (`player-host/9`):** `every: 10`, `openai/gpt-6.1-terra`,
  `effort: "medium"`, pinned to `openai`, `contextWindow: 32768`, `maxTokens: 4096`,
  `unpriced_request_usd: "0.06144"`. Combined player + recall in-flight unpriced bound is
  **`$0.47104`** (well below `ending_reserve.usd: "1.40"`; note `live_knowledge_updates:
  true` requires the recall bound in `ending_reserve.usd` even on an `--empty` start).
- **Package limits:** `spend_limit_usd: "5.50"`, `ending_reserve.usd: "1.40"`
  (other ending reserve fields matching `#859`: `seconds: 120`, `inputs: 128`,
  `requests: 128`, `frames: 128`, `frame_bytes: 134217728`), `max_hosts: 2`,
  `wall_seconds: 9000`, `host_seconds: 3600`, `total_host_seconds: 7200`,
  `limits: {max_inputs: 6000, max_requests: 10000, max_frames: 1500, max_bytes: 2147483648}`.
- **Working guide choice (`context.txt`) — explicit owner confirmation before freeze:**
  `docs/player-guide.md` on `main` (`sha256: 142e73034bbbfd3b53db33adf408904cad867419a4e806e0b3dfaf0d08ac70fd`,
  126 lines, 7,972 bytes) has been updated since `#803`/`#859`'s frozen `context.txt`
  (`sha256: 5b63e03efdb707da9a508c3c87d42403709eb7eb655f5cea819da6ad50f481cc`, 140 lines,
  9,513 bytes). **Proposal:** freeze current `docs/player-guide.md` so `#889` validates
  the current shipping player guide; alternatively, freeze `#803`/`#859`'s `context.txt`
  if the owner prefers strict prompt-byte continuity with `#803`/`#859`.
- **Planned capture headroom preflight:** Run `tools.campaign_package` before launch
  against the frozen package for 500 work frames + 96 ending frames at 524,288 bytes
  (`--work-before-bytes 262144000 --ending-before-bytes 312475648`), well inside
  `max_bytes: 2147483648`.

### Live curator runner configuration (`curator-runner-config/1`)

```json
{
  "schema": "curator-runner-config/1",
  "knowledge_root": ".runtime/knowledge/live-validation-run-889/cdda",
  "arm": "terra",
  "cap_usd": "15.00",
  "session_cap_usd": "8.00",
  "trigger_steps": 20,
  "ceiling_steps": 40,
  "poll_seconds": 15,
  "watch_seconds": 5,
  "host": {
    "effort": "medium",
    "max_requests": 120,
    "max_output_tokens": 16384,
    "request_timeout_seconds": 240,
    "wall_seconds": 1800,
    "max_context_images": 16,
    "context_image_block": 8
  }
}
```

### Post-admission boundary grooming (`tools.curator_host.groom`)

After `#889` closes and `session.sqlite3` seals, run one boundary-grooming session using
the same configuration file and a fresh output directory inside `.runtime/` outside the
knowledge worktree:

```sh
.venv/bin/python -m tools.curator_host.groom \
  --run .runtime/computer-sessions/PACKAGE \
  --config .runtime/live-validation-run-889/curator-runner-config.json \
  --out .runtime/live-validation-run-889/grooming \
  --cap-usd 8.00
```

If the live runner published no version during the admission, `tools.curator_host.groom`
writes a `skipped` (`no-published-admission`) summary at `$0` and exits `0` without
resolving credentials or starting a host. If one or more windows published, it runs one
`session_kind="grooming"` session under `curator-fact/4` (filing game-scoped facts into
articles while keeping world-scoped facts standalone under `campground-889`).

### What `#889` measures and validates

1. **Multi-window live publication without `#886`:** `curator-fact/4` facts and
   accumulated `last_admission` citations across consecutive 20-step windows, plus scope
   separation (`game` vs `world: campground-889`).
2. **In-session live delivery (`#838`):** real `knowledge-delivery` (`update`) events
   adopted by actor `001` mid-run, recall firing after live adoption from an empty `v0`
   start, and actor `002` starting with the latest live-adopted briefing on `001 -> 002`
   handoff.
3. **Post-admission boundary grooming (`#895`):** one real grooming session sealing cleanly
   over the multi-window live repository and trace.
4. **Live lag, backlog, snapshot hold/close, and player pace:** whether backlog stays
   bounded across an entire multi-actor run, whether `store-closing.json` / active-read
   wait behaves cleanly, and whether player pace clears the fixed cutoff.
5. **Upgraded `#846` schedule replay:** replaying `#889`'s real coverage schedule with
   `--recorded-deliveries` (live updates, reminders, and actor `002`'s non-empty starting
   briefing) to measure whether `#846` cuts hold back or drop image blocks in real play.

## Price, limits and why `$30.00` is not a hard cap

| Part | Forecast | Planning limit, and what enforces it |
| --- | --- | --- |
| Play (one admission, ~300–400 dec, `001 -> 002`) | $2.50–$3.50 | **`$5.50`**: package `spend_limit_usd` (`ending_reserve.usd: "1.40"` -> `$4.10` work). Checked before each player/recall request against reported spend plus pending recall allowance |
| Live curator runner (~15–20 windows) | $1.35–$1.90 (`#859` rate; up to $3.60 at `#836` pilot median) | **`$15.00`** run cap (`session_cap_usd: "8.00"`). Curator proxy reserves an estimated worst case before each request; `$8.00` headroom avoids reservation stalls on later windows |
| Post-admission boundary grooming (1 session) | $0.15–$0.40 ($0 if skipped) | **`$8.00`**: `--cap-usd 8.00` passed to `tools.curator_host.groom` (proxy reservation headroom for one grooming session over the sealed multi-window store) |
| Unallocated margin | — | **`$1.50`** |
| **Total** | **~$4.00–$5.80** (up to ~$7.50 at pilot median) | **`$30.00`** |

**Why `$30.00` is not a hard billing cap:**

- **Player in-flight and unpriced charges:** The player host can pass `spend_limit_usd`
  by the final in-flight player and recall requests (`$0.4096 + $0.06144 = $0.47104`
  combined unpriced bound). Attempts returning no usable cost are recorded as unpriced
  and may still be billed; the driver passes `spend_limit_usd` minus *reported* spend to
  the successor actor.
- **Curator proxy reservation and kill-in-flight:** The proxy reserves an estimated worst
  case (`body_bytes * $2.5/1e6 + max_output_tokens * $7.5/1e6`) and revokes only after
  an actual charge exceeds its reservation. A request already in flight when the runner
  stops is bounded on paper by ~$1.00–$1.30 at a 20-step window (larger at a 40-step
  tail), though real single-request charges were at most `$0.0518` in `#859` and `$0.10`
  in `#836`.
- **Hard cap:** Only a credit limit set by the owner on the provider key is a hard cap;
  the code cannot read that limit. The owner approval request will state explicitly
  whether `#889` runs under the existing key with this `$30.00` planning ceiling or under
  a run-scoped key with a hard credit limit.

## Fixed pace cutoff

Carried forward unchanged from the three named sealed fresh-start admissions of the same
player route (`#859` `before-launch-summary.md`, keeping both clocks labelled separately):

| Sealed admission | Decisions | Decisions/min (receipt elapsed) | Operations/min (first-to-last op) | Operations/min (receipt elapsed) |
| --- | ---: | ---: | ---: | ---: |
| `wilderness-803-first-eligible-8a4badef08b9` (same mission) | 405 | 7.10 | 7.31 | 7.26 |
| `farm-788-equipment-return-e3da8d1f2714` | 265 | 6.88 | 7.60 | 7.42 |
| `two-wake-772-farm-58ee9279783f45ba8ffd469e1c6357b9` | 310 | 7.48 | 7.86 | 7.77 |
| *Partial live reference:* `live-curator-run-859-2cda0867c344` | *127* | *9.74* | *10.46* | *10.20* |
| **Fixed "far from" cutoff (25% below slowest reference)** | — | **< 5.16** | **< 5.48** | — |

A pace under **5.16 decisions/min** (receipt elapsed) or under **5.48 operations/min**
(first-to-last op) triggers investigation before treating the run as clear on pace. One
admission cannot prove that the runner did or did not slow play.

## Pre-dispatch checklist (not yet executed)

1. **Owner approval:** Confirm planning ceiling (`$30.00`, forecast `~$4.00–$5.80`), key
   type (existing key vs run-scoped credit limit), and working guide choice
   (`docs/player-guide.md` vs `#803`/`#859` `context.txt`).
2. **Main checkout required:** Freeze the package on the clean merged `main` commit and
   launch from the **main checkout** (not a worktree), because
   `tools/campaign_supervision.py` invokes `tools.curator_host.live_runner` without
   `--runtime-root`.
3. **Preserve `Townsend`:** Move `.runtime/user/` aside under `.runtime/bridge/game.lock`
   and prepare a fresh windowed project userdir before package freeze and preflight,
   restoring `Townsend` after custody closes.
4. **Offline preflight:** Run `tools.campaign_package --run PACKAGE --work-before-bytes 262144000 --ending-before-bytes 312475648`
   and verify `live_runner.read_config` accepts `curator-runner-config.json`.
5. **Launch (only after approval):**
   ```sh
   .venv/bin/python -m tools.campaign_supervision \
     --run .runtime/computer-sessions/PACKAGE \
     --curator-runner .runtime/live-validation-run-889/curator-runner-config.json
   ```
6. **Post-admission boundary grooming & `#846` replay (after seal):** Run
   `tools.curator_host.groom` (above), then `tools.memory_screen_checks schedule` and
   `tools.memory_screen_checks cut --coverage schedule --schedule SCHEDULE --recorded-deliveries`.
