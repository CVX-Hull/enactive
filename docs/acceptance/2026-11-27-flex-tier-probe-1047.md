---
owner: lead
status: historical
kind: measurement
date: '2026-11-27'
scope: 'Owner-approved #1047 Step B1 2-window #998 curator flex-tier probe on openai/gpt-6.1-terra (medium effort, pinned openai/flex, curator-host/2) verifying applied tier, exact 50% cache-write billing, latency, 429 rate, prefix-suffix proxy reservation, and curator-knowledge/5 publication quality'
---

# `#1047` Step B1: 2-window `#998` `flex`-tier curator probe

## At a glance

- **Question.** On top of `#1027` Phase A (`curator-host/2`, targeted workspace reads, zero-eviction 16-image cap, prefix-suffix proxy reservation) and `#1037` (`player-host/13` uncovered-cut fallback), does `openai/gpt-6.1-terra` medium on pinned `openai/flex` (`service_tier: "flex"`, fallbacks disabled) apply the `flex` tier, bill at exact 50% rates (`$0.625/M` cache write), avoid `429` instability, and publish clean `curator-knowledge/5` facts on sealed `#998` windows?
- **Result: verified (`$0.0938` total spend, `-77.9%` vs. `#998` `default` baseline).**
  - **Tier & billing:** `20/20` requests returned HTTP `200` with `applied_service_tier: "flex"` in both host telemetry and proxy ledger. All 20 requests fell in the base (`< 272,000` prompt-token) tier and matched the OpenRouter `openai/flex` rate card (`$0.50` input / `$2.50` output / `$0.025` cache read / `$0.625` cache write per MTok) with **`$0.0000000` billing discrepancy**—an exact `0.5000×` of `default`-tier pricing (`$0.18758720` default-equivalent -> `$0.09379360` settled).
  - **Comparison with the `#998` baseline:** Repricing the probe's observed token usage at `default` rates gives `$0.18758720`, which is `-55.7%` below `#998`'s historical `$0.42384950` on the same two step windows (observed alongside targeted workspace reads, `83.3%–85.8%` cache-read shares, and zero mid-session image eviction; this historical comparison does not isolate individual `#1027` Phase A levers because the baseline ran on an earlier store/host with different starting state on Window 2 and different request/completion counts). Applying `service_tier: "flex"` halved `$0.18758720` to `$0.09379360` (`-77.9%` combined, `4.52×` lower).
  - **End-to-end latency & stability:** Total wall time was `132.11 s` (`41.22 s` + `90.89 s`) vs. `256.03 s` (`137.06 s` + `118.98 s`) in `#998`'s recorded `default` run (`-48.4%`), with median end-to-end request duration `3.03 s` / `2.98 s` (max `16.37 s` / `36.90 s`), `0` HTTP `429`s, `0` retries, `0` proxy breaches, and `0` cap refusals. OpenRouter does not expose a separate provider queue timer, so queue wait time inside end-to-end request duration was not measured separately.
  - **Store quality:** Both windows sealed cleanly and published `v1` (`10` active facts) and `v2` (`24` active facts, `1` ended) through the `curator-knowledge/5` gate (`2/2` accepted, `0` rejected, `0` stale citations, `10` keyed states, `3` anchored facts, `9` frame clocks, zero Kind 6–7 or frameless `state` facts).
- **Step B2 disposition:** Deferred as unnecessary. `#1047` gates optional Step B2 (parity-gated shadow replay of cheaper or successor async tiers) on needing further savings or OpenAI retiring `flex`; verified `-77.9%` combined savings and exact `0.5000×` `flex` billing on the current curator model remove any immediate need for a model switch.
- **What is not known.** This probe covers two sequential windows (`54` steps) from one admission (host execution window `2026-11-28T02:09:29Z–02:11:39Z`; provider load was not measured, and provider queue time was not separately instrumented). All 20 requests stayed below `272,000` prompt tokens, so the long-prompt `flex` tier was not exercised. End-to-end latency and `429` frequency under heavier provider contention, longer `40–60`-step windows, interleaved hygiene passes, and multi-admission live campaigns on `curator-knowledge/5` + `player-host/13` + `flex` remain to be measured in a separately approved live validation run.

[Issue #1047](https://github.com/CVX-Hull/enactive/issues/1047) · [Owner approval](../decisions/owner-decisions-archive.md#flex-tier-probe-approved-1047) · [Curator hosts](../operations/curator-hosts.md#pi-curator-host-the-shadow-session-host) · [`#1027` cadence replay](2026-11-27-curation-cost-cadence-1027.md)

## Frozen setup

- **Codebase:** `main` at `8cf67ad389ab6fb65a4b48b5113e1327cc85a2ef` (post-`#1027` Phase A and `#1037`).
- **Owner approval:** Explicit owner approval on 27 November 2026 for Step B1 at a hard proxy cap of `$1.00` total / `$0.50` per window ([owner decision archive](../decisions/owner-decisions-archive.md#flex-tier-probe-approved-1047)).
- **Input trace:** Sealed `#998` Admission 01 (`multi-day-standard-build-998-admission-01/run`, actor `001`), Window 1 steps `1..28` and Window 2 steps `29..54`, matching the exact first two curator windows of `#998`.
- **Route & runtime:** Production `tools.curator_host.shadow.run_one` + Seatbelt sandbox + `ModelProxy`, `curator-host/2`, model `openai/gpt-6.1-terra`, `effort: "medium"`, `service_tier: "flex"`, pinned provider routing `{"only": ["openai/flex"], "order": ["openai/flex"], "allow_fallbacks": false, "require_parameters": true}`, `max_context_images: 16`, fresh knowledge repository initialized at `v0`.
- **Sealed evidence:** `flex-probe-1047` ([`data/evidence/flex-probe-1047.sha256`](../../data/evidence/flex-probe-1047.sha256)) holding the shadow session records, proxy ledgers, host logs, `probe-report.json`, and published `v0`–`v2` knowledge repository.

## Per-window results vs. `#998` `default` baseline

Baseline figures come from the sealed `#998` Admission 01 curator session summaries (`001-1-28-b2e40890` and `001-29-54-7f344ed1` in [`data/evidence/multi-day-standard-build-998-admission-01.sha256`](../../data/evidence/multi-day-standard-build-998-admission-01.sha256), `openai/gpt-6.1-terra` medium on `openai` `default` tier prior to `#1027` Phase A).

| Window | Run | Reqs | Wall (s) | Prompt Tok | Cached Tok (%) | Cache-Write Tok | Completion Tok | Settled USD | Default-Equiv USD | Cost vs. `#998` |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `1..28` | `#998` `default` baseline | 22 | 137.06 | 641,796 | 460,695 (71.8%) | 181,035 | 7,168 | `$0.2852345` | `$0.2852345` | — |
| `1..28` | **`#1047` `flex` probe** | **9** | **41.22** | **195,482** | **162,740 (83.3%)** | **32,715** | **3,400** | **`$0.0330289`** | **`$0.0660578`** | **`-88.4%`** |
| `29..54` | `#998` `default` baseline | 13 | 118.98 | 453,759 | 383,470 (84.5%) | 70,250 | 6,318 | `$0.1386150` | `$0.1386150` | — |
| `29..54` | **`#1047` `flex` probe** | **11** | **90.89** | **302,406** | **259,604 (85.8%)** | **42,769** | **11,011** | **`$0.0607647`** | **`$0.1215295`** | **`-56.2%`** |
| **Total** | `#998` `default` baseline | 35 | 256.03 | 1,095,555 | 844,165 (77.1%) | 251,285 | 13,486 | `$0.4238495` | `$0.4238495` | — |
| **Total** | **`#1047` `flex` probe** | **20** | **132.11** | **497,888** | **422,344 (84.8%)** | **75,484** | **14,411** | **`$0.0937936`** | **`$0.1875872`** | **`-77.9%`** |

## Rate-card, proxy, and workspace checks

- **OpenRouter `openai/flex` endpoint rate card (queried 27 November 2026 from `https://openrouter.ai/api/v1/models/openai/gpt-6.1-terra/endpoints`):**
  - Base tier (`< 272,000` prompt tokens, exercised on all 20 requests): `$0.50` input / `$2.50` output / `$0.025` cache read / `$0.625` cache write per MTok (exact 50% of `default` tier `$1.00 / $5.00 / $0.05 / $1.25`).
  - Long-prompt tier (`>= 272,000` prompt tokens, listed on the endpoint card and not exercised in this probe): `$1.00` input / `$3.75` output / `$0.05` cache read / `$1.25` cache write per MTok (exact 50% of `default` long-prompt tier `$2.00 / $7.50 / $0.10 / $2.50`).
- **Per-request billing audit:** Comparing `(uncached × 0.50 + completion × 2.50 + cached × 0.025 + cache_write × 0.625) / 1,000,000` against provider-reported `cost` and proxy ledger `charged` produced **`$0.0000000` max error** across all 9 requests in Window 1 (`$0.033028875`) and all 11 requests in Window 2 (`$0.060764725`).
- **End-to-end request durations & `429` behavior (provider queue wait unmeasured separately):**
  - Window 1 (`998-a01-001-1-28-9a6fe959`, `2026-11-28T02:09:29Z–02:10:08Z`): `9` requests, end-to-end durations `[2.02, 1.22, 3.09, 1.80, 4.10, 5.02, 16.37, 1.42, 3.03]` s (min `1.22 s`, median `3.03 s`, max `16.37 s`).
  - Window 2 (`998-a01-001-29-54-df3de903`, `2026-11-28T02:10:10Z–02:11:39Z`): `11` requests, end-to-end durations `[1.16, 1.15, 3.12, 1.87, 2.69, 2.98, 36.90, 2.53, 28.51, 4.05, 3.62]` s (min `1.15 s`, median `2.98 s`, max `36.90 s`).
  - Zero `429` responses, zero retries, zero timeouts (`20/20` HTTP `200`).
- **Proxy reservation & accounting (`curator-proxy-close/1`):** Both sessions closed `settled: true`, `revoked: false`, `breaches: 0`, `refusals: 0`, `usage_missing: 0`. Prefix-suffix reservation fired on `18/20` requests (`1` `full-bound` + `8` `prefix-suffix` in Window 1, peak reservation `$0.14038875`, min `$0.09343125`; `1` `full-bound` + `10` `prefix-suffix` in Window 2, peak reservation `$0.175515`, min `$0.09438125`).
- **Targeted workspace reads & zero-eviction image cap:**
  - Window 1 `read_file` succeeded on `knowledge/index.md`, `knowledge/knowledge.json`, and `trace/manifest.json`; Window 2 read `knowledge/index.md`, `trace/manifest.json`, and three individual record files (`knowledge/records/tent-groundsheet-sewing-kit.json`, `survivor-profession-starting-items.json`, `campground-start-tent-present.json`). Neither window attempted or had access to bulk `facts.jsonl` or `current-facts.jsonl`.
  - Both windows called `view_frame` in 4 batches of 4 (`16` distinct frames appended per window, `0` duplicates, `0` capped, zero mid-session image eviction).

## Published store quality (`curator-knowledge/5`)

| Version | Session ID | Gate Verdict | Total Facts | Active / Ended | Kinds (`obs / out / state`) | Keyed States | Anchored | World-Bound | Frame Clocks | Stale Citations |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| `v1` | `998-a01-001-1-28-9a6fe959` | published (`1/1`) | 10 | `10 / 0` | `3 / 2 / 5` | 5 | 1 | 5 | 2 | 0 |
| `v2` | `998-a01-001-29-54-df3de903` | published (`1/1`) | 25 | `24 / 1` | `8 / 6 / 10` | 10 | 3 | 13 | 9 | 0 |

Both submissions passed all `curator-knowledge/5` invariants on publication with zero rejected submissions, zero Kind 6–7 entries, zero frameless `state` entries, and clean lifecycle progression (`1` keyed state transitioned to `ended` in `v2`).
