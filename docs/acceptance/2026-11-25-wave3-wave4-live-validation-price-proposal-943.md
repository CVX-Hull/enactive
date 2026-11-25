---
owner: lead
status: historical
kind: measurement
date: '2026-11-25'
scope: 'Consolidated $0 Wave 3 + Wave 4 + Wave 4C end-to-end stand-in rehearsal results and frozen, priced bounded standard-build live-validation proposal (#943) for separate owner spend approval'
---

# Combined Wave 3 + Wave 4 stand-in rehearsal and standard-build live-validation price proposal (#943)

## At a glance

- **Spend and launch status:** **`$0` provider spend and `$0` gameplay spend** were incurred in `#943`. No CDDA process was launched, `.runtime/user/` was not touched, and nothing in this proposal is approved until the owner explicitly authorizes the run and dollar ceiling in [the owner decision log](../decisions/owner-decisions.md).
- **Consolidated `$0` stand-in rehearsal (PASS):** Exercised the merged Wave 3 (`curator-knowledge/4`, `curator-submission/2`, `curator-boundary-grooming/2`, `delivered-knowledge/3`, `campaign-run/13`, `spectator-view/3`), Wave 4 (`player-host/12`, `telemetry_version: 12`, `player-knowledge/3` with `_fold` and compact hits, best-effort `k = E` context cuts, `already_in_context` recall deduplication, halving `tail-notice`, `spend-reserve-reached` handshake), and Wave 4C viewer (`#464` read-only curator draft/gate views and JSON `404`/`405` envelopes, `#957` `cut_result`/`spend-reserve-reached`/`tail-notice`/compact-hit views) stack end-to-end across two `$0` verification lanes (`#958`'s `censor_reason: "budget"` classification for failed spend settlements is separately verified on `main` `32c676b2` by `tests/test_evaluation_core.py`):
  1. **Retained live macOS Seatbelt WAL stand-in rehearsal (`tests/live_curator_stand_in_run.py`):** Caught and fixed two integration defects (`write_manifest` still emitted `campaign-run/12` without `context`, which caused `live_runner.delivery_target` to disable live delivery; and `runner_ended_at_teardown` omitted the valid `'store-closed'` stop reason). After fixing both and adding a live WAL spectator probe (`ViewerProber` verifying `source_status == 'available'` and live runner progress `ordinal > 0`), **24 of 24 checks passed** (`3/3` accepted live windows, `30/30` WAL snapshot reads, max lock hold `2.8 ms`, max transaction `1.7 ms`, max staging `46.9 ms`, live delivery `v1`/`v2`/`v3`, real `player-host/12` replay delivery, and live WAL `spectator-view/3` `200`/`404`/`405` verification). Retained locally at `.runtime/live-curator-stand-in-runs/wave4c-943-final/report.json` (`sha256: d53ac5d890bd513d0fcb2ee282cca07668a307a91868f5599f3eb400f7e4845b`, session `3a2f65b34f9341b78bcbad5b0f1c668f`).
  2. **Automated combined end-to-end regression suite (`tests/test_wave4c_combined_rehearsal.py` + `tests/fixtures/combined_rehearsal_replay.mjs`):** **2 of 2 tests passed** (`9.18 s` locally on macOS; the portable Node `player-host/12` + `spectator-view/3` test runs in Ubuntu CI while the macOS Seatbelt `tools.curator_host.groom` test runs locally on macOS and skips cleanly when Seatbelt is absent). Verified `curator-submission/2` (`validate_submission`, `add_fact`, `add_article`, `supersede_fact`, `remap_citations`, `edit_article`), real macOS Seatbelt `tools.curator_host.groom` (`curator-boundary-grooming/2`, `stale_records: 0`, `proxy.settled: true`, `proxy.breaches: 0`, projected directly into `spectator-view/3`), `#918` proxy reservation bounds, two real in-place Node `player-host/12` actors over real Python MCP `player-knowledge/3` (with `player-host-inputs/4` `snapshot_status == 'verified'`, `_fold` morphological `bm25_1hop` compact hits, casefolded title read, structured `already_in_context` reminder recall exclusion check, `cut_result: "best_effort"` + `recent_intents`, halving `tail-notice`, `"undelivered"` + `"delivered"` live updates, and `spend-reserve-reached` -> `orderly_stop` -> `external_stop_complete`), `spectator-view/3` (`#464` + `#957` + `"undelivered"`), and `tools.host_analysis` roll-ups.
- **Proposed live validation run (for separate owner approval):** One bounded fresh `Wilderness / Campground / Survivor` admission (`S1`, `campaign-run/13`, `context: {"ruleset": "standard"}`) with a **standard non-`overpowered` CDDA character build** (`8/8/8/8` unmodified stats, default point pool spent on traits only per [campaign-driven improvement](../workflows/campaign-admission.md#campaign-driven-improvement)), live curator runner (`trigger_steps: 25`, `ceiling_steps: 45`), live knowledge updates (`live_knowledge_updates: true`), and one post-admission boundary-grooming session (`curator-boundary-grooming/2`):
  - **Expected spend forecast:** **`$6.49–$10.90`** (`$3.50–$4.20` play, `$2.80–$6.30` live curator across ~14–20 windows, `$0.19–$0.40` boundary grooming).
  - **Planning ceiling:** **`$24.00`** (`$5.50` play + `$12.00` live curator + `$5.00` boundary grooming + `$1.50` unallocated margin).
  - **`$24.00` is a planning ceiling, not a hard billing cap.** Roughly `$10.00` of the ceiling is worst-case proxy reservation headroom across the live curator runner and boundary grooming. The only hard billing cap is the credit limit on the provider API key, which the owner controls outside the codebase.

[Issue #943](https://github.com/CVX-Hull/enactive/issues/943) · [Owner decision: Wave 3 + Wave 4 consolidation](../decisions/owner-decisions.md#consolidate-wave-3-and-4-live-validation-943) · [Campaign admission workflow](../workflows/campaign-admission.md) · [Live validation #889](2026-11-22-live-validation-run-889.md) · [Seven-day campaign #896](2026-11-22-seven-day-campaign-896.md) · [Replay gates #949](2026-11-25-player-host-12-porter2-and-replay-gates-949.md) · [Pre-merge model check #950](2026-11-25-player-host-12-model-check-950.md)

## Consolidated `$0` stand-in rehearsal results

### 1. Retained live macOS Seatbelt WAL stand-in rehearsal (`tests/live_curator_stand_in_run.py`)

Run locally on macOS Seatbelt against loopback `tests.curator_stand_in.StandIn` (`--pace 0.3 --steps 32 --actors 2 --poll-seconds 0.5`, `$0` spend, zero CDDA launch; retained report `.runtime/live-curator-stand-in-runs/wave4c-943-final/report.json`, SHA-256 `d53ac5d890bd513d0fcb2ee282cca07668a307a91868f5599f3eb400f7e4845b`, session `3a2f65b34f9341b78bcbad5b0f1c668f`, branch `work/943-combined-rehearsal` after all `#943` fixes):

| Measure | Observed | Bound / expectation |
| --- | --- | --- |
| Overall verdict | **PASS (`24 / 24` checks)** | All required checks pass |
| Live curator windows | `3 / 3` accepted (`001` 1–20 in `1.313 s`, `001` 21–33 in `1.200 s`, `002` 1–20 in `1.253 s`) | `>= 2` windows in order, handoff tail covered |
| WAL snapshot reads | `30 / 30` reads; hold max `2.8 ms`, tx max `1.7 ms`, staging max `46.9 ms` | Hold `<= 2,000 ms`, tx `<= 1,500 ms` |
| Writer pace & SQLite contention | `199.99` ops/min with runner vs `199.96` ops/min alone; `0` busy errors; `0` WAL bytes at seal | Clean seal, zero busy contention |
| Live delivery (`delivered-knowledge/3`) | Runner left `v1`, `v2`, `v3`; listed `v1` on `001`, `v2`/`v3` on `002`; real `player-host/12` replay delivered `v1` | `player-host/12` (`telemetry_version: 12`), `delivered-knowledge/3` |
| Live WAL spectator inspection (`ViewerProber`) | `/api/view/runs`, `/api/view/run/<session>/summary`, `/api/view/frame/curator-runner` (`source_status == 'available'`, `live_ordinal == 1`), `404` & `405` JSON `spectator-view/3` envelopes all passed while WAL grew | `spectator-view/3`, `spectator-frame/1` |

**Integration defects surfaced and fixed in `#943`:**
1. `tests/live_curator_stand_in_run.py:write_manifest` still wrote `campaign-run/12` without `context`, causing `live_runner.delivery_target` to disable live knowledge delivery (`not a campaign-run/13 manifest`). Updated to `campaign-run/13` with `context: {"ruleset": "standard"}` and `labels.world: "stand-in-world"`.
2. `tests/live_curator_stand_in_run.py:measure` (`runner_ended_at_teardown`) rejected the valid `'store-closed'` runner stop reason when `receipt.json` arrived ahead of teardown. Added `'store-closed'` alongside `'store-closing'` and `'interrupted'`.

### 2. Automated end-to-end combined regression suite (`tests/test_wave4c_combined_rehearsal.py`)

Executed locally via `pytest -vv tests/test_wave4c_combined_rehearsal.py` (`2 passed in 9.18 s`, `$0` spend; the portable Node `player-host/12` + `spectator-view/3` test runs in Ubuntu CI while the macOS Seatbelt boundary-grooming test runs locally on macOS and skips when Seatbelt is unavailable):

- **`test_combined_wave3_wave4_player_host_and_spectator_rehearsal`:** Builds a `curator-knowledge/4` repository (`v0 -> v1 -> v2 -> v3`) with `add_fact`, `add_article`, `supersede_fact`, `remap_citations`, `edit_article`, and `from_drafts`; checks `#918` `Price.reservation` bounds; exports real `delivered-knowledge/3` (`v1` start + `v3` live update under `context: {"ruleset": "standard"}`); runs two real in-place Node `tools/player_host/host.mjs` actors (`actors/001` and `actors/002`, `player-host/12`, `telemetry_version: 12`) over real Python MCP (`player-knowledge/3`), exercising `_fold` morphological `bm25_1hop` compact `hits`, casefolded title read, structured `already_in_context` reminder recall exclusion (`water-purification` present in `already_in_context` and `0` overlap in reminder selections), `context_cut` hysteresis + `cut_result: "best_effort"` + ephemeral `recent_intents`, halving `tail-notice` (`spend-limit`), `"delivered"` (actor `001`) and `"undelivered"` (actor `002` on HTTP 500 `provider-error`) live updates, and `spend-reserve-reached` -> `orderly_stop` -> `external_stop_complete`; evaluates the resulting `campaign-run/13` run with real `player-host-inputs/4` frozen manifests (`snapshot_status == 'verified'`, `snapshot.version == 'v1'`) and verifies `spectator-view/3` (`#464` draft/gate views + `from_drafts` + JSON `404`/`405` envelopes + fixture grooming receipt projection, `#957` `cut_result`/`spend-reserve-reached`/`tail-notice`/compact `returned_hits`, `"undelivered"` update feed) and `tools.host_analysis` roll-ups.
- **`test_combined_wave3_boundary_grooming_closeout_with_seatbelt_stand_in`:** Runs real `tools.curator_host.groom` (`curator-boundary-grooming/2`) inside macOS Seatbelt against loopback `StandIn` over a sealed `campaign-run/13` store whose `v2` left 1 stale citation, verifying `validate_submission`, `remap_citations`, `edit_article`, `stale_records == 0`, `proxy.settled == true`, `proxy.breaches == 0`, positive proxy reservation accounting, and direct `spectator-view/3` projection of the real `grooming-summary.json` (`source_status == 'available'`, `status == 'completed'`, `published_after == 'v3'`).

## Empirical cost inputs for the proposed live run

| Reference | Decisions / ops | Player+recall USD (USD/dec) | Live curator USD (windows) | Boundary grooming USD (`max_reserved`) |
| --- | ---: | ---: | ---: | ---: |
| `#889` (`live-validation-run-889-a02d8069d043`, no context cutting) | `359` / `367` | `$4.2783` (`$0.01192`) | `$3.0131` (`17` windows, `20/40` steps, max res `$1.09`) | `$0.1874` (`$1.39`) |
| `#896-b A1` (`seven-day-896-b-a01`, `60k/20k/10` cutting) | `569` / `584` (`570` inputs, `14` obs) | `$3.6595` (`$0.00643`) | `$6.3352` (`16` windows, `35/60` steps) | `$0.2480` (`$1.32`) |
| `#896-b A1–A5` (`v0 -> v59`, all 5 admissions: range / median) | `313`–`569` / med `430` | `$0.0064`–`$0.0086`/dec (med `$0.0076`) | `$3.4534`–`$6.5370` / med `$6.3671` (`7`–`16` windows) | `$0.2224`–`$0.3996` / med `$0.3265` (`$1.32`–`$2.15`) |
| `#949` replay (`player-host/12` + `player-knowledge/3`) | `3,744` checks | `-63.9%` query bytes; `-96.01%` held-back checks | — | — |
| `#950` `C-MODEL-CHECK` (synthetic MCP) | `9` player / `5` recall | `$0.0190` total (`$0` gameplay) | — | — |

The forecast uses the full `#896-b A1–A5` sample (including `A2`'s early `313`-decision stop at `$3.4534` live curator spend) alongside `#889`'s fresh-start `$3.0131` live curator spend. With `#890`/`#950` context cutting active (`60k/20k/10` + best-effort `k = E` fallback) and compact `player-knowledge/3` query hits, a `$4.10` work budget (`spend_limit_usd: "5.50"`, `ending_reserve.usd: "1.40"`) is expected to fund **~400–550 decisions** (`~410–570` computer operations) before reaching the spend reserve, generating **~14–20 live curator windows** at `trigger_steps: 25`, `ceiling_steps: 45`.

## Proposed frozen configuration (pending owner approval)

### Standard character build rule (`docs/workflows/campaign-admission.md`)

- **Scenario & start:** Fresh `Wilderness / Campground / Survivor` (`S1`).
- **Build constraint:** Default CDDA point pool, unmodified baseline **`8/8/8/8`** stats, **zero extra pool points on starting skills** beyond the chosen scenario and profession (pool points may go only to traits; no `freeform` or `overpowered` rating).
- **Verification:** At the first segment-boundary review, record the exact starting build and game-displayed character rating from first observation (`R-FALSE-CLAIM`).

### Frozen package plan (`campaign-run/13`)

- **Labels & context:** `labels: {arm: "wave3-wave4-validation", start: "S1", scenario: "Wilderness / Campground / Survivor", world: "campground-wave34-validation", lineage: null, admission: null}`, `context: {"ruleset": "standard"}`, `live_knowledge_updates: true`.
- **Starting delivered knowledge (`delivered-knowledge/3`):** Exported empty (`version: null`, `0` articles, `0` facts) bound to `campground-wave34-validation` and `context: {"ruleset": "standard"}`:
  ```sh
  .venv/bin/python -m tools.knowledge_export --empty --world campground-wave34-validation --context ruleset=standard --package .runtime/computer-sessions/PACKAGE
  ```
- **Working guide (`context.txt`):** Current `docs/player-guide.md` (`sha256: 020633de79c3e01b4b899d9064ed3ec9257d36a92923be55eef22fc4dacd27d7`, 142 lines, 9,461 bytes).
- **Player route (`player-host/12`, `telemetry_version: 12`):** `openai/gpt-6.1-terra`, `effort: "medium"`, OpenRouter `["openai", "azure"]` allowlist (`allow_fallbacks: false`, `require_parameters: true`, `service_tier: "default"`), `contextWindow: 262144`, `maxTokens: 16384`, `max_context_images: 39`, `context_image_block: 20`, `context_reserve_tokens: 32768`, `context_cut: {high_mark: 60000, low_mark: 20000, min_free: 10}`, `request_timeout_seconds: 60`, `unpriced_request_usd: "0.4096"`.
- **Recall route (`player-host/12`):** `every: 10`, `openai/gpt-6.1-terra`, `effort: "medium"`, pinned `["openai"]`, `contextWindow: 32768`, `maxTokens: 4096`, `unpriced_request_usd: "0.06144"`. Combined player + recall unpriced bound is `$0.47104` (well inside `ending_reserve.usd: "1.40"`).
- **Package limits:** `spend_limit_usd: "5.50"`, `ending_reserve: {seconds: 600, usd: "1.40", inputs: 128, requests: 128, frames: 96, frame_bytes: 201326592}`, `max_hosts: 2`, `wall_seconds: 6300`, `host_seconds: 5700`, `total_host_seconds: 5700`, `limits: {max_inputs: 6000, max_requests: 10000, max_frames: 1500, max_bytes: 2147483648}`.
- **Offline preflight before launch:** Run `tools.campaign_package --run .runtime/computer-sessions/PACKAGE --work-before-bytes 262144000 --ending-before-bytes 312475648` and `live_runner.read_config` against the frozen package before starting supervision.

### Live curator runner (`curator-runner-config/1`) and post-admission boundary grooming

```json
{
  "schema": "curator-runner-config/1",
  "knowledge_root": ".runtime/knowledge/wave3-wave4-validation/cdda",
  "arm": "terra",
  "cap_usd": "12.00",
  "session_cap_usd": "5.00",
  "trigger_steps": 25,
  "ceiling_steps": 45,
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

After the store seals, run one `curator-boundary-grooming/2` session (`--cap-usd 5.00`, providing substantial proxy reservation headroom above `#896-b`'s `$2.15` peak single-request reservation — though not a guarantee against a larger multi-turn cumulative `spent + reserved + worst` total exceeding `$5.00`):

```sh
.venv/bin/python -m tools.curator_host.groom \
  --run .runtime/computer-sessions/PACKAGE \
  --config .runtime/wave3-wave4-validation/curator-runner-config.json \
  --out .runtime/wave3-wave4-validation/grooming \
  --cap-usd 5.00
```

## Price summary, stop rules, and combined Wave 3 + Wave 4 qualification checklist

| Component | Expected forecast | Planning limit & enforcement |
| --- | --- | --- |
| Play (`campaign-run/13`, `player-host/12`, `$4.10` work + `$1.40` reserve) | `$3.50–$4.20` | **`$5.50`** (`spend_limit_usd`; `spend-reserve-reached` handshake at `$1.40` reserve) |
| Live curator (`curator-knowledge/4`, ~14–20 windows at `25/45` steps) | `$2.80–$6.30` | **`$12.00`** run cap (`session_cap_usd: "5.00"`) |
| Post-admission boundary grooming (`curator-boundary-grooming/2`, 1 session) | `$0.19–$0.40` (`$0` if skipped) | **`$5.00`** (`--cap-usd 5.00`) |
| Unallocated margin | `$0.00` | **`$1.50`** |
| **Total** | **`$6.49–$10.90`** | **`$24.00` planning ceiling** (provider key credit limit is the sole hard billing cap) |

**Stop rules (no silent renewals):**
1. Stop immediately without retry if preflight fails, native custody fails to clean up, or an upstream HTTP `403`/account-credit error occurs.
2. Stop the live admission on natural death, `player_finish`, `spend-reserve-reached` -> orderly save & quit, or `wall_seconds` custody bound; never relaunch or extend budget without a fresh owner decision.
3. Run at most one post-admission boundary-grooming session (`--cap-usd 5.00`), skipped cleanly at `$0` if zero live windows published.

**Combined Wave 3 + Wave 4 qualification checklist (evaluated from sealed artifacts & `spectator-view/3`):**
1. **Standard build verified:** Starting stats `8/8/8/8`, default point pool (traits only), non-`overpowered` rating confirmed from first observation.
2. **Wave 3 curation & scoping (`curator-knowledge/4`, `curator-submission/2`, `delivered-knowledge/3`, `campaign-run/13`):** Multi-window live publication with `validate_submission`, `edit_article`/`remap_citations` where used, `context: {"ruleset": "standard"}` preserved end-to-end, world-scoped vs. game-scoped separation intact, and post-admission `curator-boundary-grooming/2` completing with `stale_records == 0`, `proxy.settled == true`, and `proxy.breaches == 0`.
3. **Wave 4 player runtime (`player-host/12`, `player-knowledge/3`):** `telemetry_version: 12`, bounded actor-start/cut briefings, `already_in_context` recall deduplication (`0` overlap), `context_cut` hysteresis + best-effort `k = E` fallback (`cut_result` recorded, `0` hard capacity stops, high cache share), halving `tail-notice`, `spend-reserve-reached` handshake -> orderly save & quit, and compact `player-knowledge/3` query hits (`bm25_1hop` with `_fold`).
4. **Wave 4C observability (`spectator-view/3`, `#464`, `#957`, `#958`):** Live WAL viewer displays `#464` draft/gate views (`from_drafts`) and JSON `404`/`405` envelopes cleanly, `#957` displays `cut_result`, `spend_reserve_reached`, `tail_notices`, and compact `returned_hits`, and `tools.evaluate` classifies any failed spend-limit settlement under `censor_reason: "budget"`.

**Ordered outcome table:**
1. **Custody or WAL safety failure** (snapshot over bound, non-empty WAL at seal, native cleanup failure) -> **FAIL**; fix defect before any further live run.
2. **Non-standard (`overpowered` / `freeform`) character build observed** -> **INVALID for standard-build comparison**; retain evidence honestly as development data and escalate before re-running.
3. **Early provider/account refusal or `0` live curator publications** -> **PARTIAL**; report exact cause and spend without relaunching.
4. **Live publication succeeds, but post-admission boundary grooming fails (`cap-reached` or `stale-citations-remain`)** -> **PARTIAL**; report exact `published_before`/`published_after`, `stale_records`, and reservation/spend figures, and escalate before any retry.
5. **All checklist items clear (`stale_records == 0`, `0` hard capacity stops, clean `spend-reserve-reached` or natural finish, spectator views verified)** -> **PASS**; opens Wave 5 (`#839` / `#944`) planning with fresh owner decision.
