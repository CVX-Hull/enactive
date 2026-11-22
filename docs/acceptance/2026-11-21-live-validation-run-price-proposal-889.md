---
owner: lead
status: historical
kind: measurement
date: '2026-11-21'
scope: 'Price proposal, frozen package plan, runner configuration, stop rules, ordered outcome table, pace cutoff, boundary-grooming command and upgraded #859 delivery-aware schedule replay for the first full live validation admission (#889, prepared under #895)'
---

# Price proposal for the full live validation run (#889)

## At a glance

One fresh `Wilderness / Campground / Survivor` admission (`S1`, `campaign-run/12`) with
the live curator runner publishing under `curator-fact/4`, live in-session knowledge
delivery enabled (`live_knowledge_updates: true`), and one post-admission
boundary-grooming session is forecast at about **$4.12 to $6.02** for a 300–400 decision
run at [#803](2026-11-19-joanna-campground-memory-803.md)'s player rate and
[#859](2026-11-21-live-curator-run-859.md)'s live accepted curator rate (about **$8.16**
if 20 curator sessions average the
[#836](2026-11-20-live-curator-run-price-proposal-836.md) price-pilot median of `$0.20`
with `$0.66` grooming, or about **$9.76** if play uses the entire `$4.10` work budget at
`#803`'s rate — ~479 decisions / 24–25 windows — at the `$0.20` pilot median and `$0.66`
grooming; `#859`'s cheaper single-actor rate would permit still more windows before
`$4.10`):

- **Play (one admission, work budget `$4.10`, ~355–479 decisions across the three full-run references' rates):** forecast **$2.50–$3.50** for 300–400 decisions at `#803`'s `$0.00856`/decision rate (about `$3.14–$4.19` at `#788`'s `$0.01047`/decision rate; work phase stops at `$4.10` + `$1.40` ending reserve), package limit **`$5.50`** (`ending_reserve.usd: "1.40"`).
- **Live curator runner (~15–20 sequential 20-step windows for 300–400 operations; ~24–25 windows if play uses the full `$4.10` work budget at `#803`'s rate, and more if `#859`'s cheaper rate holds):** forecast **$1.35–$1.86** for 15–20 windows at `#859` accepted rates (or **$3.00–$4.00** at `#836`'s `$0.20` pilot median; `$4.80–$5.00` for 24–25 windows at `$0.20`), runner cap **`$19.00`** with per-session cap **`$8.00`** (keeping full `$8.00` proxy reservation headroom on the 20th session even if all 19 earlier sessions hit `#836`'s `$0.57` maximum: `19 × $0.57 + $8.00 = $18.83`).
- **Post-admission boundary grooming (1 session after the store seals):** forecast **$0.27–$0.66** (the middle five of the seven recorded grooming sessions in [#618](2026-11-13-curator-scoring.md), dropping the `$0.08` minimum and `$0.76` maximum; median **$0.53**; `$0` if nothing was published, skipped cleanly), session cap **`$8.00`**.
- **Unallocated margin:** **`$1.50`**.
- **Planning ceiling:** **`$34.00`** (`$5.50 + $19.00 + $8.00 + $1.50`).

**`$34.00` is a planning ceiling, not a hard billing cap.** `$16.00` of the `$34.00`
ceiling is proxy worst-case reservation headroom (`$8.00` across the live runner's
session cap and `$8.00` for the separate post-admission boundary-grooming proxy), not
expected spend. The only hard billing cap is the credit limit on the provider key,
which the owner sets and the code cannot read. Nothing here is approved, no game was
launched, `.runtime/user/` was not touched, and **$0** was spent preparing this
proposal.

[First paid live run (#859)](2026-11-21-live-curator-run-859.md) · [Joanna Campground run (#803)](2026-11-19-joanna-campground-memory-803.md) · [Curator scoring (#618)](2026-11-13-curator-scoring.md) · [Price proposal (#836)](2026-11-20-live-curator-run-price-proposal-836.md) · [Price corrections (#836)](2026-11-20-live-curator-run-price-correction-836.md) · [Owner decision](../decisions/owner-decisions.md#post-838-validation-cut-failover-and-seven-day-sequence)

## Why `#889` needs a larger work budget than `#859` — and what budget cannot guarantee

The first paid live run ([#859](2026-11-21-live-curator-run-859.md)) gave the player
`spend_limit_usd: "3.00"` with `ending_reserve.usd: "1.40"` (`$1.60` work budget),
stopped at 127 decisions on actor `001` (`$0.79` player spend; early curator stop at
session 5 from [#886](https://github.com/CVX-Hull/enactive/issues/886), now fixed), and
therefore did **not** exercise a real in-session actor handoff, live mid-admission
delivery (`live_knowledge_updates: true`), `curator-fact/4` world/game scope separation
in live play, or post-admission boundary grooming.

| Evidence source | Decisions | Ops | Actors | Wall (s) | Player spend (USD) | USD / decision | Dec/min (receipt elapsed) | Ops/min (first-to-last op) |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| `wilderness-803-first-eligible-8a4badef08b9` (`#803`, same `S1` mission) | 405 | 414 | 2 (`001 -> 002` at req 210) | 3,423 | $3.47 | $0.00856 | 7.10 | 7.31 |
| `farm-788-equipment-return-e3da8d1f2714` (`#788`) | 265 | 286 | 1 | 2,312 | $2.78 | $0.01047 | 6.88 | 7.60 |
| `two-wake-772-farm-58ee9279783f45ba8ffd469e1c6357b9` (`#772`) | 310 | 322 | 1 | 2,488 | $3.58 | $0.01156 | 7.48 | 7.86 |
| `live-curator-run-859-2cda0867c344` (`#859`, partial, 1 actor) | 127 | 133 | 1 | 783 | $0.79 | $0.00623 | 9.74 | 10.46 |

At the three full-run references' rates (`#772` `$0.01156`, `#788` `$0.01047`, `#803`
`$0.00856`), a `$4.10` work budget (`spend_limit_usd: "5.50"` minus
`ending_reserve.usd: "1.40"`) buys roughly **355 to 479 decisions** (`355` at `#772`,
`392` at `#788`, `479` at `#803`; nothing in the package stops play at 400 decisions —
the work phase stops when reported spend plus pending recall reaches `$4.10`, or earlier
on a natural finish or limit). At `#859`'s cheaper single-actor partial rate
(`$0.00623`/decision), `$4.10` would buy roughly **658 decisions** if that rate held
across a longer admission.

**Budget gives room for a handoff; it does not guarantee one.** In `#803`, the
`001 -> 002` handoff occurred because actor `001` chose to call `player_handoff` at
request 210 (when its largest context estimate was 117,194 tokens against a 262,144
window, with `$10.35` of its `$12.00` limit remaining). Both `#788` (265 decisions) and
`#772` (310 decisions) ran to completion on a single actor with **no** handoff. `#889`
can therefore consume its entire `$4.10` work budget on actor `001` without a handoff.
If that happens, `#889` is reported honestly as **partial on handoff** (multi-window
`curator-fact/4` publication, live in-session `update` delivery, recall after adoption,
post-admission boundary grooming, and single-actor `#846` schedule replay are still
measured and recorded; successor-actor briefing adoption across a real handoff remains
unverified and is put back to the owner before any second run).

## Curator cost, grooming cost and reservation inputs

| Input | Figure | Source |
| --- | --- | --- |
| Live accepted curator session cost | median $0.0745 (S1–S3: $0.0557, $0.1481, $0.0745); mean $0.0928; **$0.00449 / covered step** | `#859` accepted sessions `v1`–`v3` (62 steps) |
| All five `#859` sessions (incl. 2 rejected by `#886`) | median $0.0769; mean $0.1286; $0.00606 / step | `#859` sessions S1–S5 (106 steps) |
| Session price pilot (offline sealed windows) | median $0.20, range $0.11–$0.57 | `#836` price pilot (10 sessions) |
| Grooming session cost (offline sealed lineage) | median **$0.53**, range **$0.08–$0.76** ($0.33, $0.53, $0.63, $0.08, $0.76, $0.27, $0.66; middle five: $0.27–$0.66) | [Curator scoring (#618)](2026-11-13-curator-scoring.md) (7 grooming sessions) |
| Live session wall time | 49.40 s to 113.73 s; every session ended before the next 20-step window filled | `#859` sessions S1–S5 |
| Operations per decision | 1.05 (`#859`: 133/127) and 1.02 (`#803`: 414/405); forecast assumes ~1.02–1.05 ops/decision | `#859` and `#803` sealed stores |
| Largest single-request proxy reservation in `#859` | $0.9380 (at `max_output_tokens: 16384`; largest real charge $0.0518) | `#859` `proxy-ledger.jsonl` |
| Largest single-request proxy reservation in `#836` pilot | $1.12–$1.41 at 32,768 max output (~$1.00–$1.29 at 16,384) | `#859` `before-launch-summary.md` |

The live `Runner` (`harness/curator/runner.py`) enforces no hardcoded session count cap;
its window trigger counts finished computer **operations** (not decisions), and polling
plus snapshot staging add time before each session starts.

- **Window count assumption:** At `#803`/`#859`'s ratio (~1.02–1.05 operations per
  decision), a 300–400 decision run generates roughly **306–420 operations** (**15–20**
  full 20-step windows). If play consumes the entire `$4.10` work budget at `#803`'s
  rate (~479 decisions), it reaches roughly **489–503 operations** (**24–25** full
  20-step windows). If `#859`'s cheaper partial rate (`$0.00623`/decision) held for the
  full `$4.10` work budget (~658 decisions), it could reach ~671–691 operations
  (**33–34** windows), so 24–25 windows is the `#803`-rate illustration rather than a
  hard upper bound.
- **Live curator forecast:**
  - For 15–20 windows: **$1.35–$1.86** at `#859`'s accepted rate (`$0.00449`/step or
    `$0.0928`/session mean), or **$3.00–$4.00** at `#836`'s pilot median (`$0.20`/session).
  - For 24–25 windows (`#803`-rate full `$4.10` work budget): **$2.20–$2.32** at `#859`'s
    accepted rate, or **$4.80–$5.00** at `#836`'s `$0.20` pilot median.
- **Curator run cap (`#836` correction rule):** Following
  [the `#836` price correction](2026-11-20-live-curator-run-price-correction-836.md#the-curators-cap-and-so-the-ceiling),
  for the 20th session still to keep the full `$8.00` `session_cap_usd` after 19 earlier
  sessions at the pilot's largest displayed cost (`$0.57`), `cap_usd` must be at least
  `19 × $0.57 + $8.00 = $18.83`. Setting **`cap_usd: "19.00"`** and
  **`session_cap_usd: "8.00"`** satisfies that rule through 20 windows (after 24 earlier
  sessions at `$0.57`, `$5.32` of the run cap remains; after 24 earlier sessions at the
  `$0.20` pilot median, `$14.20` remains, keeping the full `$8.00` session cap).

## Upgraded `#859` schedule replay with recorded deliveries (`#846` preparation)

Read-only (`$0`) comparison over the sealed `#859` admission (`1` actor, `135` player
requests, `4` recorded coverage changes, `v18` starting briefing of `1,457`
approximated tokens at 4 UTF-8 bytes/token, `12` delivered reminders totalling `5,473`
approximated tokens, `0` live updates, `0` unmatched deliveries):

```sh
.venv/bin/python -m tools.memory_screen_checks schedule .runtime/evidence/live-curator-run-859/run --output SCHEDULE
.venv/bin/python -m tools.memory_screen_checks cut .runtime/evidence/live-curator-run-859/run --coverage schedule --schedule SCHEDULE
.venv/bin/python -m tools.memory_screen_checks cut .runtime/evidence/live-curator-run-859/run --coverage schedule --schedule SCHEDULE --recorded-deliveries
```

| Row | Requests | Prompt p50 | Prompt p95 | Prompt max | Cuts | Cuts / reqs held back | Image drops | Cache write (vs recorded) | Share < 40k | Share < 60k |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `recorded` | 135 | 45,035 | 67,399 | 69,506 | 0 | 0 / 0 | 5 | 323,169 (1.000) | 0.407 | 0.830 |
| `no cut` (0 delivery tokens) | 135 | 43,590 | 63,010 | 64,910 | 0 | 0 / 0 | 5 | 311,134 (0.963) | 0.415 | 0.904 |
| `no cut` (`--recorded-deliveries`) | 135 | 47,871 | 69,474 | 71,414 | 0 | 0 / 0 | 5 | 342,609 (1.060) | 0.326 | 0.770 |
| `schedule` (0 delivery tokens) | 135 | 33,000 | 44,540 | 47,390 | 3 | 2 / 2 | 2 | 239,154 (0.740) | 0.830 | 1.000 |
| `schedule` (`--recorded-deliveries`) | 135 | 35,663 | 48,341 | 51,191 | 3 | 2 / 2 | 2 | 259,884 (0.804) | 0.681 | 1.000 |

Adding `--recorded-deliveries` shrinks upper-tail error against the recorded trace
(`p95` from `-6.5%` to `+3.1%`, `max` from `-6.6%` to `+2.7%`) while shifting median
prompt (`-3.2%` to `+6.3%`) and total cache write (`0.963x` to `1.060x`) above
recorded. Two simulation limits remain disclosed for `#889`/`#890`: delivery tokens use
the stated 4-UTF-8-bytes/token approximation, and `simulate` keeps each actor's
starting briefing size across cuts rather than modelling fresh-briefing growth at a cut
([measurement tools contract](../contracts/measurement-tools.md#runner-records-and-schedule-replay)).
Also, `cut` pools `prompt_max` across actors, so after a handoff with different actor
briefing sizes, the per-actor `prompt - briefing <= 60,000` check in the outcome table
below is evaluated per actor from `simulate` rather than from pooled `prompt_max` alone.

## The run proposed (`#889`)

### Frozen package plan (`campaign-run/12`)

- **Scenario and world:** One fresh `Wilderness / Campground / Survivor` admission (`S1`),
  using `#803`/`#859`'s mission text (`prompt.txt`), with explicit world label
  `labels.world: "campground-889"`, `labels.arm: "live-validation-run"`,
  `labels.start: "S1"`, `labels.scenario: "Wilderness / Campground / Survivor"`,
  `labels.lineage: null`, `labels.admission: null`.
- **Starting delivered knowledge (`delivered-knowledge/2`):** Exported empty (`version: null`,
  `commit: null`, `repository_id: null`, `0` articles, `0` facts) bound to `campground-889`:
  ```sh
  .venv/bin/python -m tools.knowledge_export --empty --world campground-889 --package .runtime/computer-sessions/PACKAGE
  ```
- **Live knowledge updates:** `live_knowledge_updates: true`. As the live curator
  publishes `v1`, `v2`, … into the game repository under
  `knowledge_root: ".runtime/knowledge/live-validation-run-889/cdda"` (the repository
  worktree is `.runtime/knowledge/live-validation-run-889/cdda/cdda`), verified updates
  reach the running actor via `knowledge-delivery` (`update`) and become the next
  actor's frozen file if a handoff occurs.
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
- **Package limits (matching sealed `#859` except `spend_limit_usd`; also matching `#803` except `spend_limit_usd` and `#803`'s `ending_reserve.usd: "1.50"`):**
  `spend_limit_usd: "5.50"`, `ending_reserve: {seconds: 600, usd: "1.40", inputs: 128,
  requests: 128, frames: 96, frame_bytes: 201326592}`, `max_hosts: 2`,
  `wall_seconds: 6300`, `host_seconds: 5700`, `total_host_seconds: 5700`,
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
  `max_bytes: 2147483648` and consistent with `ending_reserve.frames: 96`.

### Live curator runner configuration (`curator-runner-config/1`)

```json
{
  "schema": "curator-runner-config/1",
  "knowledge_root": ".runtime/knowledge/live-validation-run-889/cdda",
  "arm": "terra",
  "cap_usd": "19.00",
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
the same configuration file and a fresh output directory inside `.runtime/` outside both
the knowledge worktree and the run directory:

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

## Price, limits and stop rules

| Part | Forecast | Planning limit, and what enforces it |
| --- | --- | --- |
| Play (one admission; `$4.10` work buys ~355–479 dec across `#772`/`#788`/`#803`) | $2.50–$3.50 for 300–400 dec at `#803` rate ($3.14–$4.19 at `#788` rate; work phase caps at $4.10) | **`$5.50`**: package `spend_limit_usd` (`ending_reserve.usd: "1.40"` -> `$4.10` work). Checked before each player/recall request against reported spend plus pending recall allowance |
| Live curator runner (~15–20 windows for 300–400 ops; ~24–25 at `#803`-rate full `$4.10` work) | $1.35–$1.86 for 15–20 windows at `#859` rate ($3.00–$4.00 at `#836` pilot median; $4.80–$5.00 for 24–25 at pilot median) | **`$19.00`** run cap (`session_cap_usd: "8.00"`). Preserves full `$8.00` reservation headroom on session 20 even after 19 max-cost `$0.57` sessions (`$18.83`) |
| Post-admission boundary grooming (1 session) | $0.27–$0.66 (middle five of `#618`, median $0.53, full range $0.08–$0.76; $0 if skipped) | **`$8.00`**: `--cap-usd 8.00` passed to `tools.curator_host.groom` (proxy reservation headroom for one grooming session over the sealed multi-window store) |
| Unallocated margin | — | **`$1.50`** |
| **Total** | **~$4.12–$6.02** (300–400 dec at `#803` + `#859` rates; ~$8.16 at pilot median for 20 windows + `$0.66` grooming; ~$9.76 at `#803`-rate full `$4.10` work / 25 windows at pilot median + `$0.66` grooming) | **`$34.00`** |

**Why `$34.00` is not a hard billing cap:**

- **Player in-flight and unpriced charges:** The player host can pass `spend_limit_usd`
  by the final in-flight player and recall requests (`$0.4096 + $0.06144 = $0.47104`
  combined unpriced bound). Attempts returning no usable cost are recorded as unpriced
  and may still be billed; the driver passes `spend_limit_usd` minus *reported* spend to
  a successor actor.
- **Curator proxy reservation and kill-in-flight:** The proxy estimates each request's
  worst case by replacing inline images with a fixed image-token estimate and charging
  remaining body bytes plus `max_output_tokens`, and revokes only after an actual charge
  exceeds its reservation. A request already in flight when the runner stops is bounded
  on paper by ~$1.00–$1.30 at a 20-step window (larger at a 40-step tail), though real
  single-request charges were at most `$0.0518` in `#859` and `$0.10` in `#836`.
- **Hard cap:** Only a credit limit set by the owner on the provider key is a hard cap;
  the code cannot read that limit. The owner approval request states explicitly whether
  `#889` runs under the existing key with this `$34.00` planning ceiling or under a
  run-scoped key with a hard credit limit (which the owner sets at or above the ceiling).

**Stop rules (carrying forward [the `#836` corrections](2026-11-20-live-curator-run-price-correction-836.md#what-stops-the-players-side)):**

- A successful **player** response with no usable cost stops the player host.
- A successful **recall** response with no usable cost ends recall for that actor only,
  and the player continues.
- The player host enforces `spend_limit_usd`, `ending_reserve.usd`, and its per-actor
  timeout; the driver and custodian enforce `wall_seconds`, `host_seconds`,
  `total_host_seconds`, and the mechanical ceilings.
- The live curator runner stops for the admission when its run cap is reached; when the
  proxy refuses the next reservation even with counted spend under the cap; when the
  proxy is revoked, breached, or unsettled; when session cleanup is unconfirmed; when a
  charge is unknown; after two consecutive rejected or failed sessions; after three
  consecutive failed snapshots; or when the trace store closes. Play continues without
  it.
- Boundary grooming runs at most one session after the store seals and stops on any
  cap refusal, unresolved publication, proxy issue, unsealed session, or cleanup
  failure.
- `#889` is one admission and is not repeated on its own result without owner approval.

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

## Ordered outcome table (what each result changes)

Rows are read in order; the first row that applies decides. Snapshot safety comes before
an early stop, and any stop or inconclusive result comes before a favourable replay
([`#836` correction](2026-11-20-live-curator-run-price-correction-836.md#the-order-of-the-outcome-table-and-two-rows)).

| Result | Reading | Next |
| --- | --- | --- |
| Snapshots fail or pass their time bound | The live read is not safe beside the custodian as designed | Fall back to the custodian yielding a detached, stable copy of each window's prefix; repeat only after that |
| Session store closes with a non-empty write-ahead log | Sealed evidence cannot be read (does not by itself prove the snapshot reader caused it) | Investigate store close before another run |
| The run stops early, the covered prefix cannot be established, or no actor handoff occurred | Partial figures are reported as partial (noting which mechanisms were and were not exercised) | Report to the owner before another run |
| Player pace falls below 5.16 decisions/min (receipt) or 5.48 operations/min (first-to-last op) | A reason to look, not a finding: one admission cannot show cause | Inspect snapshot timings and `host.jsonl` before concluding |
| No version is published | Nothing can be said about lag, live updates, or grooming (boundary grooming skips cleanly at $0) | Read the curator sessions before retrying |
| Backlog grows across the admission | A session cannot keep up with play at this window | Live curation at this price/window is not workable; keep curation between admissions |
| Cost and lag disagree (close behind and far over forecast, or cheap and far behind) | Window and model are mismatched | Show both figures to the owner before another run |
| Upgraded `--recorded-deliveries` schedule replay makes no cut and holds back no request | Inconclusive: the admission gave the cut nothing to do | Longer admission needed before deciding `#890` |
| Replay holds back requests | Curation trails too far behind for the cut at this window | Test a smaller window or faster model in a second priced run before building `#890` |
| Replay holds back no request but drops image blocks | The cut keeps its token target only by losing images | Revisit the image policy before proposing `#890` |
| Replay makes cuts, holds back no request, drops no image block, but leaves any actor's request above `high_mark` above briefing (`prompt - briefing > 60,000`) | The cut is not keeping its above-briefing token target | Revisit window, model, or cut parameters before proposing `#890` |
| Replay meets the cut target, but live `update` delivery failed or boundary grooming failed | Cut timing is encouraging, while delivery or grooming is broken | Fix the delivery or grooming defect before proposing `#890` |
| Replay makes cuts, holds back no request, drops no image block, leaves every actor's request within `high_mark` above briefing (`prompt - briefing <= 60,000`), and live updates and grooming are clean | Curation and live delivery keep pace closely enough for the simulated cut to hold its target | Put `#890` (coverage-gated context cut) to the owner with these figures and the disclosed fresh-briefing simulation caveat |

## Pre-dispatch checklist (not yet executed)

1. **Owner approval:** Confirm planning ceiling (`$34.00`, forecast `~$4.12–$6.02`), key
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
