---
owner: lead
status: historical
kind: measurement
date: '2026-11-27'
scope: 'Frozen parameters, $0 stand-in rehearsal and offline preflight, and owner price proposal for one fresh-world multi-day standard-build live validation campaign under campaign-run/14, curator-knowledge/5, delivered-knowledge/4, player-host/13, curator-host/2 and curator-runner-config/2 (40/60 flex default, interleaved hygiene, multi-actor handoff), for issue #1056 under #387 and #136; $0 spent, zero game launches, zero provider requests; awaiting explicit owner spending approval'
---

# Fresh-world continuous-memory live validation: frozen parameters, `$0` stand-in rehearsal and price proposal (`#1056`)

## At a glance

- **Nothing was launched or spent (`$0`).** Zero game processes started, zero paid provider requests were sent, and `.runtime/user/` was left untouched. This record proposes a paid live campaign; it does not authorize one. Execution requires an explicit owner spending decision in the [owner decision log](../decisions/owner-decisions.md) ([`C-SPEND`](../controls.md)).
- **Frozen code and fresh-world rule.** Baseline code and guide are frozen on post-`#1055` `main` commit `b6ba747d01244cc04bc3ee2306dddc5876e72465` (`docs/player-guide.md`, 158 lines, 12,280 bytes, SHA-256 `25a1ba6bbd5b94c7c39387627f12d29895e0ebddb1f793f518f186a7b06844fc`). Following [`#archive-index-adds-963-and-998-sessions`](../decisions/owner-decisions.md#archive-index-adds-963-and-998-sessions), the campaign starts on a fresh `Wilderness / Campground / Survivor` world (`campground-continuous-memory-1056`, standard character build, zero `/4 -> /5` live converter) after archiving `#998`'s remaining user-directory files.
- **One bounded run informing four downstream lines:**
  1. **Batches 1–4 + `flex` + multi-actor handoff (`#387`, `#136`):** Live-verify `curator-knowledge/5`, `delivered-knowledge/4`, `player-host/13` (retired recall, substantive deltas, `player_agenda`, `player-source-index/1` / `player-source-read/2`, `#1037` uncovered-cut fallback), `curator-host/2` (`40/60` default cadence, automatic pinned `openai/flex` routing, interleaved text-only hygiene passes), and at least one natural inside-admission `player_handoff` (`001 -> 002`).
  2. **Second independent-world corpus (`#681`, `#677`):** Produce a fresh-world `curator-knowledge/5` lineage distinct from `#998` and report whether its recovery/use and belief-revision cases satisfy `#681` and `#677`'s respective research gates.
  3. **Routine recurrence measurement (`#996`, `#177`):** Measure multi-day routine recurrence on the continuous-memory stack to decide whether `#996`/`#177` activates next.
  4. **Parked trigger observation (`#336`, `#384`, `#1057`, `#164`):** Observe whether any parked trigger fires (including `#1058` review note S1 watching whether interleaved hygiene's `60 s` host wall cap hits `flex` queueing timeouts).
- **Price.** One full admission is forecast at **`$4.51` to `$7.25`** (`$4.45` low end if boundary grooming is skipped), comparing forecast endpoints to `#998`'s measured full-admission range of `$9.32–$12.07` (~40–50% lower forecast). Its three configured allocations sum to **`$11.50`**, and its planning bound (including `$0.4096` worst-case in-flight player request overshoot) is **`$12.00`**—about 35% below `#968`'s `$18.50` planning bound. The recommended envelope is **`$48.00` for three in-game days (`259,200` game seconds, at most `4` admissions; forecast `$14.76–$24.37` for 3 full + 1 short admission, or `$18.04–$29.00` if 4 full admissions are needed)**.
- **`$0` offline rehearsal and preflight passed across separate lanes.** Verified on `b6ba747d` and retained in [`fresh-world-validation-preflight-1056`](../../data/evidence/fresh-world-validation-preflight-1056.sha256) and [`fresh-world-validation-rehearsal-1056`](../../data/evidence/fresh-world-validation-rehearsal-1056.sha256): live Seatbelt WAL stand-in (`25/25` checks with retained `host-config/terra.json` and 3 `proxy-ledger.jsonl` logs), Admission 1 & 2 `campaign-run/14` preflights, `live_runner.read_config` defaults + hygiene checks, and `647` automated Python + Node tests (`220` Python + `359` `player_host` + `68` `curator_host`) covering multi-actor handoff + `player_agenda` carryover and eligible interleaved hygiene dispatch.
- **Owner decisions required before launch:** (1) spending approval and envelope/horizon option ([below](#options-for-the-owner)); (2) named supervisor operator; and (3) whether the campaign serves as a post-wave `#136` deciding assessment or development validation evidence (`#998` already met prior-stack multi-day survival except for `#968` item 7).

[Issue #1056](https://github.com/CVX-Hull/enactive/issues/1056) · [Parent #387](https://github.com/CVX-Hull/enactive/issues/387) · [Outcome #136](https://github.com/CVX-Hull/enactive/issues/136) · [Prior `#968` proposal](2026-11-26-multi-day-standard-build-campaign-freeze-and-price-proposal-968.md) · [`#998` campaign record](2026-11-26-multi-day-standard-build-campaign-998.md) · [`#1047` flex probe](2026-11-27-flex-tier-probe-1047.md)

## Why this campaign runs now

Every Batches 1–4 engineering change (`#1020`–`#1023`, `#1025`–`#1026`, `#1037`, `#1027` Phase A, `#1047` Step B1, and `#1055` pre-validation defaults) is merged on `main` (`b6ba747d`) and verified offline or via `#1047`'s 2-window `flex` probe, but none has live multi-admission or multi-actor gameplay evidence.

| Evidence gap | What exists today | What `#1056` supplies |
| --- | --- | --- |
| Full Batches 1–4 stack in live play (`#387`) | Offline replays (`#1037`, `#1027`, Batch 1/2 checks) and 2-window `flex` probe (`#1047`, `$0.0938`) | Live multi-admission campaign on `campaign-run/14`, `player-host/13`, `curator-knowledge/5`, `delivered-knowledge/4`, `curator-host/2` |
| Multi-actor `player_handoff` inside an admission | Unit/rehearsal tests only; `#963` (`5700 s`) and `#998` (`7200 s`) each ran 1 actor per admission | `host_seconds: 3000` inside `total_host_seconds: 6600` creates a nominal `~120 s` time-threshold gap inviting natural `001 -> 002` handoff |
| `flex` contention, `429` deferrals, `40/60` quality, and interleaved hygiene | `0` `429`s on 2 windows in `#1047`; interleaved hygiene verified in unit/runner tests only | Live `40/60` `flex` windows + live interleaved text-only hygiene passes (`60 s` host wall watch) |
| Second independent-world `curator-knowledge/5` corpus (`#681`, `#677`) | Only `#998` (`curator-knowledge/4`) exists on a standard build | Fresh independent world (`campground-continuous-memory-1056`) under `curator-knowledge/5`, evaluated separately against `#681` and `#677` gates |
| Multi-day routine recurrence (`#996`, `#177`) | Measured on `#998` before `player_agenda` and retired recall | Multi-day recurrence rates under continuous memory and working-state continuity |

## Measured rates the price rests on

| Rate | Measured value | Source |
| --- | --- | --- |
| Full-admission play spend (`openai/gpt-6.1-terra` medium, `default`) | `$3.51` to `$3.53` (`618–729` decisions; `$0.0048–$0.0057`/decision; `22.96–23.59` game h/admission; recall now retired) | [`#998` record](2026-11-26-multi-day-standard-build-campaign-998.md) |
| Decision pace (wall time) | `7.16` to `8.00` s/decision in `#998` (`7.72` s/decision in `#963`) | [`#998` record](2026-11-26-multi-day-standard-build-campaign-998.md), [`#963` record](2026-11-25-wave3-wave4-live-validation-963.md) |
| Pre-wave live curator spend (`default`, `25/45`) | `$5.63` to `$8.21`/full admission (`26–32` sessions; `$23.01` across 4 admissions) | [`#998` record](2026-11-26-multi-day-standard-build-campaign-998.md) |
| Post-wave `flex` curator spend (`curator-host/2`, `openai/flex`) | `$0.0938` across 2 `#998` windows (`$0.0469`/window, `-77.9%` vs. `#998` baseline; exact `0.5000×` billing; peak reservation `$0.1755`; `0` HTTP `429`s) | [`#1047` record](2026-11-27-flex-tier-probe-1047.md) |
| `40/60` curator window count reduction (vs. `20/40`) | `-48.2%` (`112 -> 58` windows across 4 admissions on recorded `default`), `-20.7%` to `-31.0%` under `+120s` to `+600s + 15m 429` lag; `0/4` context stops | [`#1027` replay](2026-11-27-curation-cost-cadence-1027.md), [`#1037` replay](2026-11-27-uncovered-cut-lag-replay-1037.md) |
| Post-admission boundary grooming | `$0.16` to `$0.33`/admission on `default` in `#998` -> forecast `$0.06` to `$0.20` on `flex` (`0.50×` rates + targeted reads) | [`#998` record](2026-11-26-multi-day-standard-build-campaign-998.md), [`#1047` record](2026-11-27-flex-tier-probe-1047.md) |

## Proposed frozen parameters

### Code, guide, build check and user directory

- **Frozen baseline code commit:** `b6ba747d01244cc04bc3ee2306dddc5876e72465` (clean `main` post-`#1055`). Because `tools.campaign_package` verifies `source_commit == git rev-parse HEAD` on the clean launch checkout and `#1056` modifies only dated records, evidence manifests/index, and the coding-agent attempts ledger, the execution leaf records its exact clean launch `HEAD` SHA and rebuilt `bridge.dylib` SHA-256 before moving to `Ready` ONLY after verifying the **full diff** (`git diff --stat b6ba747d..HEAD`) contains exclusively reviewed dated records, `docs/acceptance/index.md`, `data/evidence/`, and `data/evaluation/coding-agent-attempts.jsonl` (zero diff across `harness/`, `tools/`, `native/` including `native/upstream.json`, `data/curator/`, root dependency pins, and `docs/player-guide.md`), rebuilding and qualifying `bridge.dylib` with `tools/build_computer.py` at that exact launch commit, and re-running both offline preflight checks on that commit. If any code, native pin, dependency pin, or guide change lands before launch, the freeze is explicitly renewed and re-verified before execution.
- **Launch checkout vs. bookkeeping worktree:** Keep the launch checkout (main checkout pinned at the frozen launch commit) clean and unmodified across all admissions so `tools.campaign_package` always verifies `source_commit == HEAD` on a clean tree. Perform all tracked bookkeeping between admissions (`tools.evidence seal`, `data/evaluation/runs.jsonl`, and the final run record) inside a separate bookkeeping worktree (e.g., `.runtime/worktrees/campaign-1056-bookkeeping`) branched from the launch commit. Build Admission `N+1`'s `player-source-index/1` sidecar from the clean launch checkout by passing every closed prior admission's `.runtime/computer-sessions/<run>` directory via `--extra-run` (matching `scripts/rehearse.py`).
- **Working guide:** `docs/player-guide.md` at `b6ba747d` (158 lines, 12,280 bytes, SHA-256 `25a1ba6bbd5b94c7c39387627f12d29895e0ebddb1f793f518f186a7b06844fc`), frozen unchanged across all admissions.
- **Standard build check (matching `#968`/`#998` and [campaign admission](../workflows/campaign-admission.md)):** Default character-creation point pool, unmodified `8/8/8/8` baseline stats, zero extra pool points spent on starting skills beyond the chosen scenario and profession (pool points may go only to traits), and an observed editor build rating that is neither `Freeform` nor `Overpowered`, verified from Admission 1 creation frames and every ending save file.
- **Fresh-world user directory (`.runtime/user/`):** Currently holds `#998`'s `save/Francis Mills/`, `config/lastworld.json`, and `templates/Last Character.template` (all verified byte-identical to sealed `multi-day-standard-build-998-admission-04`). Before Admission 1 launch, the operator archives all three under `.runtime/archive/` so `.runtime/user/save/` is empty, and records the active autosave config from `.runtime/user/config/options.json` on the execution leaf. The same `.runtime/user/` persists across Admissions 1..N of this lineage.

### Campaign package (`campaign-run/14`), one per admission

| Field | Frozen value | Reason |
| --- | --- | --- |
| `schema` | `campaign-run/14` | Current contract with `player-source-index/1` and `player-agenda-continuation/1` |
| `labels` | `arm: "continuous-memory-validation"`, `start: "S1"`, `scenario: "Wilderness / Campground / Survivor"`, `world` & `lineage`: `"campground-continuous-memory-1056"`, `admission: 1..N` | Fresh independent world distinct from `#998` |
| `context` | `{"ruleset": "standard"}` | Standard build scope |
| `live_knowledge_updates` | `true` | Delivers `delivered-knowledge/4` publications and coverage during play |
| `route` (`player-host/13`) | `openai/gpt-6.1-terra` medium, `openai` -> `azure` allowlist, `service_tier: "default"`, `context_cut` `60000/20000/10` (`#1037` derived Tier-2 uncovered ceiling `100,000`), `recall` retired | Same player route as `#998` on `player-host/13` |
| `spend_limit_usd`, `ending_reserve.usd` | `"5.50"`, `"1.40"` (`unpriced_request_usd: "0.4096"`) | Same per-admission play ceiling as `#998` |
| `host_seconds`, `total_host_seconds`, `wall_seconds` | `3000`, `6600`, `7200` | Creates a nominal `~120 s` time-threshold interval inviting natural `001 -> 002` `player_handoff` inside an admission |
| `max_hosts` | `2` | Allows one `player_handoff` (`001 -> 002`) per admission |
| `ending_reserve` (non-USD) | `seconds: 180`, `inputs: 128`, `requests: 128`, `frames: 96`, `frame_bytes: 201326592` | Reserves `180 s` at actor end without preempting `host-timeout` wrap-up |
| `limits` | `max_inputs: 6000`, `max_requests: 10000`, `max_frames: 1500`, `max_bytes: 2147483648` | Proven safe in `#998` and offline preflight (`1,835,008,000` bytes / `1.835 GB` / `~1.709 GiB` remaining at ending checkpoint) |

**How `host_seconds: 3000` exercises natural multi-actor handoff (zero prompt nudge).**

- **Nominal threshold interval (`~120 s`):** With a full `3000 s` actor allowance, `tools/player_host/host.mjs` subtracts `1 s` for cleanup (`workMs = 2,999,000 ms`), making `wallWarningMs = min(max(workMs * 0.1, 60_000), workMs / 2) = 299.9 s`. The `host-timeout` wrap-up warning therefore becomes eligible at `~2,699.1 s` on the host clock and is attached on the next qualifying outgoing request. Separately, `tools/campaign_player.py` tracks its own actor-start clock and issues `orderly_stop` at `host_seconds - ending_reserve.seconds = 2,820 s` (or earlier if spend, frame, input, or request reserves trigger first); once `host.mjs` accepts `orderly_stop`, it refuses any subsequent `player_handoff` call.
- **Forecast usable handoff opportunity:** At `#998`'s `7.16–8.00 s`/decision pace, Actor `001` reaches `~2,700 s` after roughly `337–377` decisions and `$1.62–$2.15` of counted play spend (well below Actor `001`'s advisory spend notice at `~$3.49`, so `spendWarning` is still `false`). Accounting for host startup offset and the next outgoing request boundary, the usable window before `orderly_stop` is roughly `100–115 s` (~12–15 decisions), conditional on no earlier mechanical or spend reserve trigger.
- **Actor `002` budget, spend handshake and pacing:** If Actor `001` hands off at `$1.62–$2.15`, Actor `002` receives a remaining allocation of `$3.35–$3.88` (out of the shared `$5.50` `spend_limit_usd`), of which **`$1.54–$2.07`** is ordinary pre-reserve headroom before the shared `$1.40` `ending_reserve.usd` + `$0.4096` `unpriced_request_usd` triggers `spend-reserve-reached` at **`$3.6904` cumulative spend** (`host.mjs:1102`). Because `host.mjs:1179–1183` recomputes each actor's advisory spend warning from its own remaining `workBudget = allocation - $1.40` (`0.85 × workBudget`), Actor `002`'s nominal advisory spend notice moves to **`$3.7280–$3.8075` cumulative**—*after* the `$3.6904` `spend-reserve-reached` threshold. Actor `002` is therefore forecast to end on whichever arrives first: the **`spend-reserve-reached` handshake** after `~270–430` decisions (`$1.54–$2.07` at `$0.0048–$0.0057`/decision, `~1,930–3,440 s`) or its **`2,820 s` time reserve** (~350–390 decisions)—yielding `~600–750` total decisions per full admission (`~18–23` game hours, slightly lower if handoff prefix rebuild raises spend per decision). Actor `002` starts from the latest adopted `delivered-knowledge/4` and Actor `001`'s committed `agenda-final.json`, while the curator runner drains Actor `001`'s ended tail and moves to `002`. If Actor `001` chooses to save and quit instead of calling `player_handoff`, no external nudge is injected; the outcome is recorded faithfully.

**Frozen mission prompt forms, starting knowledge, source index and agenda:**

- **Admission 1:** Verbatim `#998` Admission 1 fresh-world prompt (`multi-day-standard-build-998-admission-01/run/prompt.txt`), which instructs the player to create one fresh `Wilderness / Campground / Survivor` world on the standard character build (`8/8/8/8`, default point pool, traits only, no Freeform/Overpowered) and establish sustainable camp/survival progress. Starts with empty `delivered-knowledge/4`, empty `player-source-index/1`, and empty `player-agenda-continuation/1`.
- **Admissions 2..N:** Verbatim `#998` Admission 2 continuation prompt template (`multi-day-standard-build-998-admission-02/run/prompt.txt`) with Admission 1's chosen world and survivor names substituted and target horizon set to the approved option (`three full elapsed in-game days (72 elapsed in-game hours)` for Recommended, or `continue sustained survival through this second admission` for Alternative). Built from the clean launch checkout with:
  - `tools.knowledge_export` from the lineage's latest confirmed `curator-knowledge/5` version (including post-admission grooming when run);
  - `tools.source_index --world campground-continuous-memory-1056 --lineage campground-continuous-memory-1056 --before-admission N --extra-run <closed-prior-run-dir>... --prior-agenda <prior-admission/agenda-final.json>` to freeze verified same-lineage ancestor `source_id`s from closed prior admission directories and carry committed `player_agenda` state (including `#1055`'s telemetry-reconstruction fallback if Pause ever interrupted `agenda-final.json`).

### Live curator runner (`curator-runner-config/2`), one file for the lineage

```json
{
  "schema": "curator-runner-config/2",
  "knowledge_root": ".runtime/knowledge/campground-continuous-memory-1056/cdda",
  "arm": "terra",
  "cap_usd": "4.50",
  "session_cap_usd": "1.50",
  "service_tier": "flex",
  "trigger_steps": 40,
  "ceiling_steps": 60,
  "poll_seconds": 15,
  "watch_seconds": 5,
  "hygiene": {
    "enabled": true,
    "min_windows": 5,
    "max_unexamined_steps": 10,
    "pass_cap_usd": "0.30",
    "max_spend_share": "0.10",
    "max_requests": 10,
    "wall_seconds": 90,
    "max_consecutive_failures": 2
  },
  "host": {
    "effort": "medium",
    "max_requests": 120,
    "max_output_tokens": 16384,
    "request_timeout_seconds": 960,
    "wall_seconds": 1800,
    "max_context_images": 16
  }
}
```

- **Automatic `openai/flex` pinning (`#1055`).** `service_tier: "flex"` resolves automatically through `data/curator/shadow-arms.json` (`flex_provider: "openai/flex"`) with `allow_fallbacks: false` and `require_parameters: true`—no manual `provider` override is needed.
- **Early wake remains deferred.** Early wake on `player_hint`, pause, or save stays deferred per `#1055` unless live telemetry here demonstrates need.
- **Watched live metric (`#1058` review note S1).** Interleaved hygiene runs text-only (`max_context_images: 0`) on `service_tier: "flex"` with `hygiene.wall_seconds: 90` (`60 s` host wall time after `30 s` close-out reserve). Whether `60 s` suffices under live `flex` queueing—or triggers hygiene wall timeouts and consecutive-failure shutoff (`max_consecutive_failures: 2`)—is explicitly logged during live validation.
- **Post-admission boundary grooming (`curator-boundary-grooming/2`).** Runs after an admission seals with `--cap-usd 1.50` on `service_tier: "flex"` when the repository's last published admission is that run. A skipped, refused, or cap-stopped grooming pass is recorded and does not block the next admission; a failed repository close-out blocks until the lead resolves it.

## Price, continuation rules and owner options

### Per-admission price basis

| Component | Forecast per full admission | Configured cap | What enforces it |
| --- | --- | --- | --- |
| Play (`player-host/13`, `default`, zero recall) | `$3.40` to `$4.25` | `$5.50` | `spend_limit_usd` (`spend-reserve-reached` near `$3.6904`; max in-flight overshoot `$0.4096`) |
| Live curator ingestion (`11–18` `40/60` `openai/flex` windows) | `$0.99` to `$2.52` | *(shared `$4.50`)* | Runner `cap_usd` (`session_cap_usd: "1.50"`) |
| Interleaved hygiene (`1–2` text-only `flex` passes, `<= 10%` share) | `$0.06` to `$0.28` (`$0` if untriggered) | *(shared `$4.50`)* | `pass_cap_usd: "0.30"`, `max_spend_share: "0.10"` |
| *Subtotal: Live curator runner* | *`$1.05` to `$2.80`* | *`$4.50`* | *Runner `cap_usd`* |
| Boundary grooming (`curator-boundary-grooming/2`, `openai/flex`) | `$0.06` to `$0.20` (`$0` if skipped) | `$1.50` | `--cap-usd` |
| **One full admission** | **`$4.51` to `$7.25`** (`$4.45` w/o grooming) | **`$11.50`** | **Planning bound: `$12.00`** (`$11.50 + $0.4096`, rounded up) |

- **Play derivation:** `#998` full admissions spent `$3.51–$3.53` (including retired recall). Allowing slightly lower spend with recall retired (`$3.40`) up to ~20% overhead for an Actor `001 -> 002` handoff prefix rebuild and slightly higher prompt tokens under `40/60` `flex` (`$4.25`) gives `$3.40–$4.25`.
- **Live curator derivation:** `#1047` measured `$0.0469`/window on `#998` Windows 1–2 (`-77.9%` vs. `#998`). At `40/60`, a `600–750`-decision full admission spans `11–18` windows; allowing `~2–3×` per-window growth (`$0.09–$0.14`/window) for wider `40–60`-step windows and larger multi-admission graphs gives **`11 × $0.09 = $0.99` to `18 × $0.14 = $2.52`** for ingestion. Adding `1–2` triggered text-only hygiene passes (`$0.06` low end for 1 light pass; `$0.28` high end bounded by `10%` of `$2.80` total runner spend and `$0.30`/pass) gives **`$1.05` to `$2.80`** total runner spend (well inside the `$4.50` hard cap and `$1.50` `session_cap_usd` vs. `#1047`'s `$0.1755` peak reservation).
- **Short finishing admission derivation (when 3 full admissions reach ~66–69 h):** Priced at ~25–35% of a full admission: Play `$0.90–$1.50` (matching `#998` Admission 4's `$0.93` for 177 decisions), Live curator **`$0.27–$0.92`** (`3–6` windows × `$0.09–$0.14` = `$0.27–$0.84` ingestion, plus `$0.00` hygiene below the 5-window cooldown at `3–4` windows or up to `$0.08` for `1` pass capped at `10%` of already-counted ingestion spend at `5–6` windows), Boundary grooming `$0.06–$0.20` -> **`$1.23` to `$2.62`**.
- **Campaign-level forecast totals:**
  - **3 full + 1 short admission (at `#998`'s ~23 game h/full admission):** `3 × ($4.51–$7.25) + ($1.23–$2.62)` = **`$14.76` to `$24.37`**.
  - **4 full admissions (if handoff overhead or Actor `002` spend/time limits yield ~18 game h/full admission):** `4 × ($4.51–$7.25)` = **`$18.04` to `$29.00`**.
  - **2 full admissions (Alternative):** `2 × ($4.51–$7.25)` = **`$9.02` to `$14.50`**.
- **Hard billing cap.** As in `#968`, the provider API key credit limit managed by the owner outside the repository is the only hard account-level billing cap; software allocations bound each process plus at most one in-flight player request (`$0.4096`).

### Accounting and continuation rule (applied before every admission)

Track three separate per-admission spend components:
1. **Player spend** from `data/evaluation/runs.jsonl` (`tools/run_ledger.py`):
   - A **missing or unreadable `receipt.json`** blocks all further admissions immediately until reconciled (never substituted silently).
   - A **readable `receipt.json` with `spend_complete: false`** is recorded in `data/evaluation/runs.jsonl` using `--record-upper-bound`, which records a **player-only** upper bound of `max(reported_usd, spend_limit_usd) + unpriced_request_usd` (ordinarily `$5.50 + $0.4096 = $5.9096`), and blocks further admissions until the admission's dated note records it.
2. **Live curator spend** from the runner's settled session ledgers (counting any unsettled curator reservation at its full configured allocation, up to `$4.50`).
3. **Boundary grooming spend** from the grooming session summary (counting any unsettled grooming reservation at its `$1.50` allocation).

Let `admission_total(i)` be the sum of those three components for completed admission `i`, `campaign_spent = sum(admission_total(i))` across completed admissions, `actual_provider_subtotal` be the sum of settled provider-reported charges across all three components, and `largest_admission_so_far` be initialized to **`$0.00`** before Admission 1 (then `max(admission_total(1..k))` after `k >= 1` admissions). Start Admission `k + 1` only if **no missing/incomplete-receipt block is active** and **both** inequalities hold:

1. `campaign_spent + max($12.00, largest_admission_so_far) <= envelope` (planning-bound rule; before Admission 1, `$0.00 + $12.00 <= envelope`); and
2. `actual_provider_subtotal + 2 * largest_admission_so_far <= envelope` ([actual-spend admission rule](../operator-permissions.md#finite-gameplay-budget-delegation); before Admission 1, `$0.00 + $0.00 <= envelope`).

### Options for the owner

| | Recommended: 3-day multi-admission validation | Alternative: 2-admission cross-admission validation |
| --- | --- | --- |
| Target | `259,200` game seconds (3 in-game days) on saved clock | `2` completed admissions (no 3-day clock target) |
| Most admissions | `4` | `2` |
| Hard envelope | **`$48.00`** (`4 × $12.00` planning bound; 40% below `#968`'s `$80.00`) | **`$28.00`** |
| Forecast spend | **`$14.76–$24.37`** (3 full + 1 short) or **`$18.04–$29.00`** (4 full) | **`$9.02–$14.50`** (2 full) |
| Continuation-rule reach (complete costs) | All 4 admissions fit under both inequalities if Admissions 1–3 each cost `<= $9.60` | Admission 2 fits under both inequalities if Admission 1 costs `<= $9.33` |
| Downstream lines served | **All four:** full stack + handoff (`#387`), post-wave 3-day survival evidence (`#136`), 3-day second-world `curator-knowledge/5` lineage for `#681`/`#677` gating check, 3-day routine recurrence (`#996`/`#177`), and `#336`/`#384`/`#1057`/`#164` watch | Batches 1–4 + handoff + cross-admission continuity (`#387`), shorter (~2-day) corpus; does **not** supply 3-day `#136` parity or 3-day recurrence span |

**Recommendation:** Approve the **3-day / 4-admission / `$48.00` envelope**. `#998` already established standard-build pace (~23 game hours per full admission), and `#1027` + `#1047` lowered the forecast cost of a full 3-day campaign to `$14.76–$29.00`—so one `$48.00` envelope gathers full 3-day data across all four downstream lines without paying for a second campaign later.

## Stop rules

No budget or admission count is renewed silently ([campaign review](../workflows/campaign-admission.md#campaign-review-and-finding-disposition)).

1. **Envelope, admission cap and receipt completeness.** Apply both continuation inequalities and the missing/incomplete-receipt block before every admission; never exceed the approved admission count.
2. **Preflight refusal.** Nothing launches and `$0` is spent; fix and re-run preflight (does not consume an admission).
3. **Custody, cleanup, or log-safety failure.** Halt immediately with zero relaunch.
4. **Provider account, credit, unknown, or sustained `flex` refusal.** Stop on account/credit refusal or unknown refusal; sustained `flex` `429` exhaustion that blocks live curation across a full admission pauses before the next admission for an owner disposition (do not silently fall back to `default` tier).
5. **Target reached.** Stop once the decompressed save clock reaches `259,200` game seconds past start (or after Admission 2 under the Alternative).
6. **Character death.** Operator watches spectator view and triggers Pause on observed death; death ends the lineage with no relaunch.
7. **Unverified save or operator Pause.** Counts as one approved admission; verify `#1055` Pause `agenda-final.json` reconstruction if triggered. For Admissions `N >= 2`, the next admission reloads the last verified save and reports game time lost. If **Admission 1** ends without a verified save, there is no saved world to reload, so **the lineage ends immediately with no automatic restart**; Admission 1's spend and admission count remain recorded, and starting a new fresh-world lineage (with a new world/lineage label, empty knowledge repository, empty `player-source-index/1`, and empty `player_agenda`) requires a separate owner decision.
8. **Between-admission lead review.** Inspect build (Admission 1), stop trigger, handoff telemetry (`001 -> 002`), save & clock (comparing the decompressed ending save clock against the next admission's first observed in-game clock under the measurable tolerance below), `curator-knowledge/5` publication chain, `flex` tier/billing/latency/429s, interleaved hygiene behavior (including `60 s` wall limit), `#1037` uncovered-cut count, and spend before admitting the next run.

## Pass, Partial and Fail criteria

Every admission retains its sealed store and receipt, character-creation frames (Admission 1), ending save file, curator and grooming ledgers, and an operator note (expected empty).

1. **Standard build.** Default point pool, unmodified `8/8/8/8` stats, zero extra pool points on starting skills beyond scenario/profession, and observed rating neither `Freeform` nor `Overpowered` verified from Admission 1 creation frames and ending saves.
2. **Horizon and normal endings.** Reaches the approved target (`259,200` game seconds for Recommended; `2` completed admissions for Alternative), with every admission ending in a verified save, separate quit, zero native exit, verified custody, and verified boundary clock continuity: the next admission's first observed in-game clock equals the prior admission's decompressed ending save clock (`0 s` delta on a normal Save-to-title -> Quit -> Load; any non-zero delta is reported explicitly, and `> 300` game seconds—or exceeding the autosave interval recorded from `.runtime/user/config/options.json` before Admission 1—fails this item).
3. **Continuous memory and `curator-knowledge/5` continuity.** Unbroken `curator-knowledge/5` publication chain across admissions (`v0 -> vN`) with zero Kind 6–7 or frameless `state` violations, zero empty substantive updates emitted, clean `player_agenda` carryover across cuts/handoffs/admissions, verified `player-source-index/1` freezing, and at least one cross-admission memory use (player reads a prior-admission record or ancestor source and acts on it).
4. **Natural multi-actor handoff.** At least one admission executes a real `001 -> 002` `player_handoff` inside the admission, verifying Actor `002` starts from the latest adopted `delivered-knowledge/4` and Actor `001`'s committed `player_agenda` while the curator runner drains Actor `001`'s ended tail cleanly.
5. **Non-real-time `flex` curation, observed interleaved hygiene and `#1037` stability.** `100%` of live curator and grooming requests bill on `applied_service_tier: "flex"` with zero unauthorized tier fallbacks and zero proxy breaches; **at least one observed, qualifying interleaved hygiene pass executes** (evidenced by a `curator-runner-examined/1` `end` row with `session_kind == "hygiene"`, `advanced == false`, `text_only == true`, `max_context_images == 0`, gate-confirmed clean outcome or clean no-op, obeying `$0.30`/pass, `<= 10%` share, and zero world-fact retirements) with **zero consecutive-failure hygiene shutoff** (`max_consecutive_failures: 2` never reached, including from `60 s` host wall timeouts); and `player-host/13` suffers zero `context-capacity` hard stops (with any `#1037` uncovered cuts preserving `player_agenda`, `recent_intents`, `source_ids`, and pinned `covered_through_operation_id`).
6. **Independence.** Every game input matches a hosted actor's tool result, zero manual knowledge edits, and empty operator notes.
7. **Downstream telemetry reported separately per gate.** The final run record reports: (a) `#136` post-wave survival assessment (Recommended 3-day option only; Alternative does not claim 3-day `#136` parity); (b) `#681` (recovery/use evidence) and `#677` (qualifying belief-revision cases) evaluated separately against their own issue gates rather than treating a second lineage alone as sufficient; (c) multi-day routine recurrence metrics informing `#996`/`#177`; and (d) explicit trigger status for `#336`, `#384`, `#1057`, `#164`, and `#1058` S1 hygiene wall time.

The first matching row determines the campaign outcome:

| Outcome | Condition | What follows |
| --- | --- | --- |
| **Fail** | Any custody, cleanup, log-safety, or `curator-knowledge/5` / proxy-cap invariant breach | Fix the defect before any further paid run |
| **Invalid** | Non-standard build, unauthorized tier fallback, or any input/hint/edit outside hosted actors | Retain as development data; require new owner approval before rerunning |
| **Incomplete (Unassessed)** | Required receipt, evidence, or item 7 downstream telemetry is missing or unreconciled | Reconcile missing evidence before grading or admitting any further run |
| **Stopped** | Provider account/credit refusal, unknown refusal, or sustained `flex` `429` exhaustion blocking live curation across a full admission before target (matching Stop Rule 4) | Report clock reached, cause, and spend; resuming is an owner decision |
| **Partial** | Envelope or admissions run out before target, or character dies, or Admission 1 ends with no verified save | Report clock reached, cause, and spend; no automatic relaunch |
| **Partial (Unexercised / Gap)** | Target reached, but item 2, 3, 4, or 5 does not hold (including `0` qualifying interleaved hygiene passes, hygiene consecutive-failure shutoff under `60 s` host wall, or `0` `player_handoff` transitions) | Record exact gap/unexercised mechanism and root cause; owner decides disposition for `#387` and downstream lines |
| **Pass** | All seven items hold for the approved option | Post-wave continuous-memory stack (`#387`) is live-verified; downstream readiness for `#136` (Recommended 3-day only), `#681`/`#677`, and `#996`/`#177` follows the separate gate reports in item 7 |

## Offline `$0` stand-in rehearsal and preflight

Executed on clean `main` at `b6ba747d01244cc04bc3ee2306dddc5876e72465` with `$0` spend, zero CDDA launches, and zero paid provider calls. Because no single offline harness runs live Seatbelt WAL curation, real `campaign_player` multi-actor handoff, and eligible interleaved hygiene inside one process, verification was run across four separate lanes retained in [`fresh-world-validation-preflight-1056`](../../data/evidence/fresh-world-validation-preflight-1056.sha256) and [`fresh-world-validation-rehearsal-1056`](../../data/evidence/fresh-world-validation-rehearsal-1056.sha256):

1. **Live Seatbelt WAL stand-in (`tests.live_curator_stand_in_run --output .runtime/live-curator-stand-in-runs/fresh-world-validation-1056-supp --pace 0.25 --steps 45 --actors 2 --poll-seconds 0.5`):** **PASS (`25/25` checks)** across both initial (`017a7bc0a95f4814b3ecfe6ec43bf903` in `preflight-1056`) and supplemental (`8ad6a1f025704bb18a7a3a1b21a588b3` in `rehearsal-1056`, retaining exact invocation, `host-config-terra.json`, and all 3 `proxy-ledger.jsonl` files in `results/proxy-ledgers.json`). Verified `40/60` default triggering across 3 accepted windows (`001` steps `1–41`, `001` ended-actor tail `42–46`, `002` steps `1–40`/`1–41`), automatic pinned `openai/flex` routing (`openRouterRouting.only == ["openai/flex"]` in `host-config-terra.json`), `requested_service_tier: "flex"` on all 9 requests and `prefix-suffix` reservation on requests 2–3 of every session (`results/proxy-ledgers.json`), `36/36` WAL snapshot polls (hold max `1.8–2.2 ms`, tx max `1.0–1.5 ms`, staging max `32.9–43.9 ms`), writer parity (`239.96` vs. `239.96` ops/min), zero live-viewer WAL/JSON errors, and post-run `player-host/13` replay of Actor `002` delivering `v2` (`v1` refused/superseded) over `delivered-knowledge/4`. *(Scope limit: this stand-in writes synthetic actor transitions rather than driving `campaign_player` `player_handoff`, and does not trigger interleaved hygiene.)*
2. **Admission 1 & Admission 2 `campaign-run/14` preflight & runner config check (`scripts/rehearse.py` in `preflight-1056`, `results/preflight.txt`, `results/read-config.txt`):**
   - Admission 1 fresh-world package (`session=6ae986cb98f5ed8ed4c7a6da1f30c306`, manifest `569821a4…edc4810f`) passed `tools.campaign_package --work-before-bytes 262144000 --ending-before-bytes 312475648` with `1,835,008,000` bytes (`1.835 GB` / `~1.709 GiB`) remaining at ending checkpoint.
   - Admission 2 continuation package (`session=3244c95c1ec0ab9f7f9fedea0be0f4ea`, manifest `3f24a3a2…3d9bb478c`) built from a closed synthetic Admission 1 store + stand-in `v3` `curator-knowledge/5` repository via `tools.knowledge_export` and `tools.source_index --extra-run --prior-agenda` passed `tools.campaign_package`, preserving committed `agenda.json` (`1` thread, `cut_count=2`) and serving a verified cross-admission `player-source-read/2` (`status="available"`, `clickable=False`, blinded `origin={"admission": "s01", "actor": "001", "step": None}`, SHA-256 PNG match).
   - `tools.curator_host.live_runner.read_config` accepted both the full `curator-runner-config/2` above and a minimal defaults-only file (`trigger_steps=40`, `ceiling_steps=60`, `service_tier="flex"`, `request_timeout_seconds=960`, `openRouterRouting.only=["openai/flex"]`), and verified interleaved hygiene configuration (`text_only=True`, `max_context_images=0`, `service_tier="flex"`, `host_wall_seconds=60`, zero-spend sub-cap gate).
3. **Python rehearsal suites (`pytest -v` in `rehearsal-1056/results/pytest-verbose.txt`, `220 passed` across 5 files):**
   - `tests/test_wave4c_combined_rehearsal.py`, `tests/test_campaign_player.py`, `tests/test_source_index.py`, `tests/test_curator_runner.py`, and `tests/test_campaign_package.py` — explicitly exercising `campaign_player` `001 -> 002` `player_handoff` + `agenda-final.json` carryover, Pause agenda telemetry reconstruction (`#1055`), eligible interleaved hygiene dispatch + cooldown + digest suppression + 2-failure shutoff (`test_interleaved_hygiene_respects_cooldown_backlog_digest_and_two_failure_shutoff`), and `flex` `429` deferral + hygiene sub-cap checks (`test_live_sessions_detect_flex_capacity_deferral_and_hygiene_subcaps`).
4. **Node host suites (`preflight-1056`, `427 passed`, `0` failed):**
   - `npm --prefix tools/player_host test` (`results/player-host-tests.txt`): **`359 passed`** (`player_agenda`, substantive deltas, `#1037` uncovered-cut fallback, `player_handoff`, `spend-reserve-reached`).
   - `npm --prefix tools/curator_host test` (`results/curator-host-tests.txt`): **`68 passed`** (`curator-host/2` zero-eviction 16-image cap, byte guard, `flex` `429` deferral, text-only hygiene).

- **Not covered offline:** Live CDDA save/reload across admissions; real provider `flex` queue latency and `429` rates over `40–60`-step windows and `60 s` hygiene passes; real model choice to call `player_handoff` inside the usable wrap-up window; end-to-end execution of `campaign_player` handoff + live Seatbelt WAL + triggered interleaved hygiene in a single combined process; and live gameplay quality under `#1037` uncovered cuts.

## Open owner decisions and execution checklist

Nothing runs until the owner explicitly approves a spending option in [owner-decisions.md](../decisions/owner-decisions.md) and settles: (1) envelope & horizon (**Recommended:** `$48.00` / 3 days / up to 4 admissions vs. **Alternative:** `$28.00` / up to 2 admissions); (2) named supervisor operator; and (3) whether this campaign serves as a post-wave `#136` deciding assessment or development validation evidence.

Once approved, open a dedicated execution leaf under `#387` and execute in order:

1. Verify the full diff from `b6ba747d` (`git diff --stat b6ba747d..HEAD`) touches only reviewed dated records, `docs/acceptance/index.md`, `data/evidence/`, and `data/evaluation/coding-agent-attempts.jsonl` (zero diff in `harness/`, `tools/`, `native/`, `data/curator/`, root dependency pins, or `docs/player-guide.md`). Pin the clean launch `HEAD` SHA, rebuilt `bridge.dylib` SHA-256, and `.runtime/user/config/options.json` autosave setting on the execution leaf before moving it to `Ready`. If designated formal `#136` acceptance, run exact-candidate full verification (`tools/check.py` full suite + `tools.evidence verify`) on that launch commit before Admission 1.
2. Create a separate bookkeeping worktree (e.g., `.runtime/worktrees/campaign-1056-bookkeeping`) branched from the launch commit so the main launch checkout stays clean and pinned across all admissions.
3. Verify `.runtime/user/save/Francis Mills/`, `.runtime/user/config/lastworld.json`, and `.runtime/user/templates/Last Character.template` against sealed `multi-day-standard-build-998-admission-04`, then archive all three under `.runtime/archive/` so `.runtime/user/save/` is empty.
4. Rebuild and qualify `bridge.dylib` at the frozen launch commit via `tools/build_computer.py`; build Admission 1's `campaign-run/14` package in the clean launch checkout with the frozen prompt and runner file; run both offline preflight commands (`tools.campaign_package` and `live_runner.read_config`); and complete a clean-context cross-family pre-launch package review (`codex / gpt-6.2-sol` Extra-high or `claude-code / claude-opus-5-5` High) checking every package value, hash, runner config, empty `.runtime/user/save/`, and continuation prompt template.
5. Run `tools.campaign_supervision` from the clean launch checkout with the Admission 1 package and frozen `curator-runner-config/2`.
6. After each admission seals, run `curator-boundary-grooming/2` (`--cap-usd 1.50`, `service_tier: "flex"`) where eligible; then inside the **bookkeeping worktree**, seal the admission's evidence (`tools.evidence seal`) and append its row to `data/evaluation/runs.jsonl`. Apply Stop Rule 8 and both continuation inequalities before building Admission `N+1` in the clean launch checkout with `tools.knowledge_export` and `tools.source_index --extra-run <closed-prior-run-dir>... --prior-agenda <prior-admission/agenda-final.json>`.
7. Publish one dated run record from the bookkeeping worktree under `docs/acceptance/` grading all seven criteria, the outcome table row, and separate downstream gate reports for `#136`, `#681`/`#677`, `#996`/`#177`, and `#336`/`#384`/`#1057`/`#164`.
