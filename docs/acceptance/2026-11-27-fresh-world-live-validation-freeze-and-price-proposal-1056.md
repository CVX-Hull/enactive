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
- **Frozen code and fresh-world rule.** Frozen on post-`#1055` `main` commit `b6ba747d01244cc04bc3ee2306dddc5876e72465` (`docs/player-guide.md`, 158 lines, 12,280 bytes, SHA-256 `25a1ba6bbd5b94c7c39387627f12d29895e0ebddb1f793f518f186a7b06844fc`). Following [`#archive-index-adds-963-and-998-sessions`](../decisions/owner-decisions.md#archive-index-adds-963-and-998-sessions), the campaign starts on a fresh `Wilderness / Campground / Survivor` world (`campground-continuous-memory-1056`, unmodified `8/8/8/8` standard build, zero `/4 -> /5` live converter) after archiving `#998`'s remaining user-directory files.
- **One bounded run serving four downstream lines:**
  1. **Batches 1–4 + `flex` + multi-actor handoff (`#387`, `#136`):** Live-verify `curator-knowledge/5`, `delivered-knowledge/4`, `player-host/13` (retired recall, substantive deltas, `player_agenda`, `player-source-index/1` / `player-source-read/2`, `#1037` uncovered-cut fallback), `curator-host/2` (`40/60` default cadence, automatic pinned `openai/flex` routing, interleaved text-only hygiene passes), and at least one natural inside-admission `player_handoff` (`001 -> 002`).
  2. **Second independent-world corpus (`#681`, `#677`):** Produce a fresh-world `curator-knowledge/5` multi-day lineage distinct from `#998`.
  3. **Routine recurrence measurement (`#996`, `#177`):** Measure multi-day routine recurrence on the continuous-memory stack to decide whether `#996`/`#177` activates next.
  4. **Parked trigger observation (`#336`, `#384`, `#1057`, `#164`):** Observe whether any parked trigger fires (including `#1058` review note S1 watching whether interleaved hygiene's `60 s` host wall cap hits `flex` queueing timeouts).
- **Price.** One full admission is forecast at **`$4.66` to `$7.05`**. Its three configured allocations sum to **`$11.50`**, and its planning bound (including `$0.4096` worst-case in-flight player request overshoot) is **`$12.00`**—35% below `#968`'s `$18.50` planning bound and ~40–50% below `#998`'s `$9.32–$12.07` actual full-admission cost. The recommended envelope is **`$48.00` for three in-game days (`259,200` game seconds, at most `4` admissions; forecast `$15`–`$26`)**.
- **`$0` stand-in rehearsal and offline preflight passed.** Verified on `b6ba747d`: `25/25` live Seatbelt WAL stand-in checks (2 actors, 3 windows at `40/60`, automatic `openai/flex` routing, `player-host/13` replay), Admission 1 fresh-world and Admission 2 continuation `campaign-run/14` preflights (agenda carryover, `player-source-index/1`, `player-source-read/2`), `live_runner.read_config` defaults + hygiene checks, and `647` automated Python + Node tests (`220` Python + `359` `player_host` + `68` `curator_host`). Retained as [`fresh-world-validation-preflight-1056`](../../data/evidence/fresh-world-validation-preflight-1056.sha256).
- **Owner decisions required before launch:** (1) spending approval and envelope/horizon option ([below](#options-for-the-owner)); (2) named supervisor operator; and (3) whether the campaign serves as the deciding `#136` assessment or development validation evidence.

[Issue #1056](https://github.com/CVX-Hull/enactive/issues/1056) · [Parent #387](https://github.com/CVX-Hull/enactive/issues/387) · [Outcome #136](https://github.com/CVX-Hull/enactive/issues/136) · [Prior `#968` proposal](2026-11-26-multi-day-standard-build-campaign-freeze-and-price-proposal-968.md) · [`#998` campaign record](2026-11-26-multi-day-standard-build-campaign-998.md) · [`#1047` flex probe](2026-11-27-flex-tier-probe-1047.md)

## Why this campaign runs now

Every Batches 1–4 engineering change (`#1020`–`#1023`, `#1025`–`#1026`, `#1037`, `#1027` Phase A, `#1047` Step B1, and `#1055` pre-validation defaults) is merged on `main` (`b6ba747d`) and verified offline or via `#1047`'s 2-window `flex` probe, but none has live multi-admission or multi-actor gameplay evidence.

| Evidence gap | What exists today | What `#1056` supplies |
| --- | --- | --- |
| Full Batches 1–4 stack in live play (`#387`) | Offline replays (`#1037`, `#1027`, Batch 1/2 checks) and 2-window `flex` probe (`#1047`, `$0.0938`) | Live multi-admission campaign on `campaign-run/14`, `player-host/13`, `curator-knowledge/5`, `delivered-knowledge/4`, `curator-host/2` |
| Multi-actor `player_handoff` inside an admission | Unit/rehearsal tests only; `#963` and `#998` ran 1 actor per admission (`7200 s` `host_seconds`) | `host_seconds: 3000` inside `total_host_seconds: 6600` creates a natural `120 s` wrap-up window for `001 -> 002` handoff |
| `flex` contention, `429` deferrals, `40/60` quality, and interleaved hygiene | `0` `429`s on 2 windows in `#1047`; hygiene config tested offline only | Live `40/60` `flex` windows + live interleaved text-only hygiene passes (`60 s` host wall watch) |
| Second independent-world `curator-knowledge/5` corpus (`#681`, `#677`) | Only `#998` (`curator-knowledge/4`) exists on a standard build | Fresh independent world (`campground-continuous-memory-1056`) under `curator-knowledge/5` |
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

### Code, guide and user directory

- **Launch commit (`source_commit`):** `b6ba747d01244cc04bc3ee2306dddc5876e72465` (clean `main` post-`#1055`, or the merge commit of `#1056` if unchanged in code; recorded verbatim in every package manifest). The native `bridge.dylib` is rebuilt and qualified at that exact commit with `tools/build_computer.py` before Admission 1.
- **Working guide:** `docs/player-guide.md` at `b6ba747d` (158 lines, 12,280 bytes, SHA-256 `25a1ba6bbd5b94c7c39387627f12d29895e0ebddb1f793f518f186a7b06844fc`), frozen unchanged across all admissions.
- **Fresh-world user directory (`.runtime/user/`):** Currently holds `#998`'s `save/Francis Mills/`, `config/lastworld.json`, and `templates/Last Character.template` (all already sealed in `multi-day-standard-build-998-admission-04`). After verifying byte parity against sealed `#998` Admission 04, the operator archives all three under `.runtime/archive/` before Admission 1 so `.runtime/user/save/` is empty. The same `.runtime/user/` persists across Admissions 1..N of this lineage.

### Campaign package (`campaign-run/14`), one per admission

| Field | Frozen value | Reason |
| --- | --- | --- |
| `schema` | `campaign-run/14` | Current contract with `player-source-index/1` and `player-agenda-continuation/1` |
| `labels` | `arm: "continuous-memory-validation"`, `start: "S1"`, `scenario: "Wilderness / Campground / Survivor"`, `world` & `lineage`: `"campground-continuous-memory-1056"`, `admission: 1..N` | Fresh independent world distinct from `#998` |
| `context` | `{"ruleset": "standard"}` | Unmodified standard build (`8/8/8/8`, no traits) |
| `live_knowledge_updates` | `true` | Delivers `delivered-knowledge/4` publications and coverage during play |
| `route` (`player-host/13`) | `openai/gpt-6.1-terra` medium, `openai` -> `azure` allowlist, `service_tier: "default"`, `context_cut` `60000/20000/10` (`#1037` derived Tier-2 uncovered ceiling `100,000`), `recall` retired | Same player route as `#998` on `player-host/13` |
| `spend_limit_usd`, `ending_reserve.usd` | `"5.50"`, `"1.40"` (`unpriced_request_usd: "0.4096"`) | Same per-admission play ceiling as `#998` |
| `host_seconds`, `total_host_seconds`, `wall_seconds` | `3000`, `6600`, `7200` | Exercises a natural `001 -> 002` `player_handoff` inside a single admission (see below) |
| `max_hosts` | `2` | Allows one `player_handoff` (`001 -> 002`) per admission |
| `ending_reserve` (non-USD) | `seconds: 180`, `inputs: 128`, `requests: 128`, `frames: 96`, `frame_bytes: 201326592` | Reserves `180 s` at actor end without preempting `host-timeout` wrap-up |
| `limits` | `max_inputs: 6000`, `max_requests: 10000`, `max_frames: 1500`, `max_bytes: 2147483648` | Proven safe in `#998` and offline preflight (`1.835 GiB` remaining at ending checkpoint) |

**How `host_seconds: 3000` exercises natural multi-actor handoff (zero prompt nudge).** In `tools/player_host/host.mjs`, `wallWarningMs = min(max(workMs * 0.1, 60_000), workMs / 2) = 300 s` at `host_seconds = 3000`. Actor `001` therefore receives the host's built-in `host-timeout` wrap-up notice at `t = 2,700 s` (~340–380 decisions, ~$1.80–$2.15 spent, well below the ~$3.49 advisory spend notice so `spendWarning === false`), while `ending_reserve.seconds = 180` does not emit `orderly_stop` until `t = 2,820 s`. That gives Actor `001` a clean `120 s` (~15-decision) window in which the host's built-in wrap-up prompt naturally invites `player_handoff`. Actor `002` then starts with `~3,000 s`, `~$3.35–$3.70` remaining play budget, the latest adopted `delivered-knowledge/4`, and Actor `001`'s committed `agenda-final.json` (while the curator runner drains Actor `001`'s ended tail and moves to `002`). If Actor `001` chooses to save and quit instead of handing off, no external nudge is injected; the outcome is recorded faithfully.

**Mission prompt, starting knowledge, source index and agenda by admission:**

- **Admission 1:** Fresh-world prompt matching `#963`/`#998` Admission 1 (unmodified standard `8/8/8/8` `Wilderness / Campground / Survivor`, target three in-game days / `259,200` game seconds, or `2` admissions if the Alternative option is chosen). Starts with empty `delivered-knowledge/4`, empty `player-source-index/1`, and empty `player-agenda-continuation/1`.
- **Admissions 2..N:** Continuation prompt naming the exact world and survivor chosen in Admission 1. Built with:
  - `tools.knowledge_export` from the lineage's latest confirmed `curator-knowledge/5` version (including post-admission grooming when run);
  - `tools.source_index --world campground-continuous-memory-1056 --lineage campground-continuous-memory-1056 --before-admission N --prior-agenda <prior-admission/agenda-final.json>` to freeze verified same-lineage ancestor `source_id`s and carry committed `player_agenda` state (including `#1055`'s telemetry-reconstruction fallback if Pause ever interrupted `agenda-final.json`).

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

| Component | Forecast per full admission | Configured cap | What enforces it |
| --- | --- | --- | --- |
| Play (`player-host/13`, `default`, zero recall) | `$3.40` to `$4.25` | `$5.50` | `spend_limit_usd` (advisory notice ~$3.49; finish-up near `$3.69`; max in-flight overshoot `$0.4096`) |
| Live curator (`curator-host/2`, `40/60`, `openai/flex` + interleaved hygiene) | `$1.20` to `$2.60` | `$4.50` | Runner `cap_usd` (`session_cap_usd: "1.50"`; hygiene sub-cap `$0.30`/pass and `<= 10%` cumulative share) |
| Boundary grooming (`curator-boundary-grooming/2`, `openai/flex`) | `$0.06` to `$0.20` (`$0` if skipped) | `$1.50` | `--cap-usd` |
| **One full admission** | **`$4.66` to `$7.05`** | **`$11.50`** | **Planning bound: `$12.00`** (`$11.50 + $0.4096`, rounded up) |

- **Play forecast basis:** `#998` full admissions spent `$3.51–$3.53` (including retired recall). Allowing up to ~20% overhead for an Actor `001 -> 002` handoff prefix rebuild and slightly higher prompt tokens under `40/60` `flex` yields `$3.40–$4.25`.
- **Live curator forecast basis:** `#1047` measured `$0.0469`/window on `#998` Windows 1–2 (`-77.9%` vs. `#998`). At `40/60`, a 620–730-decision admission produces ~11–18 windows plus 1–2 text-only hygiene passes (`<= $0.30` each). Allowing 2–3× per-window growth for `40–60`-step windows and larger multi-admission graphs (`$0.09–$0.14`/window) yields `$1.20–$2.60`, well inside the `$4.50` hard cap (`session_cap_usd: "1.50"` vs. `#1047` peak reservation `$0.1755`).
- **Hard billing cap.** As in `#968`, the provider API key credit limit managed by the owner outside the repository is the only hard account-level billing cap; software allocations bound each process plus at most one in-flight player request (`$0.4096`).

**Continuation rule (applied before every admission).** Sum all counted play, live-curator, and grooming spend from the ledgers (recording any unreadable or incomplete receipt at its `$12.00` planning upper bound via `--record-upper-bound`, and any unsettled curator reservation at its allocation). Start the next admission only if **both** conditions hold:

1. `spent + max($12.00, largest_admission_so_far) <= envelope` (planning-bound rule); and
2. `spent + 2 * largest_admission_so_far <= envelope` ([actual-spend admission rule](../operator-permissions.md#finite-gameplay-budget-delegation)).

### Options for the owner

| | Recommended: 3-day multi-admission validation | Alternative: 2-admission cross-admission validation |
| --- | --- | --- |
| Target | `259,200` game seconds (3 in-game days) on saved clock | `2` completed admissions (no 3-day clock target) |
| Most admissions | `4` | `2` |
| Hard envelope | **`$48.00`** (`4 × $12.00` planning bound; 40% below `#968`'s `$80.00`) | **`$28.00`** |
| Forecast spend | **`$15` to `$26`** (3–4 admissions at `#998`'s ~23 game h/full admission) | **`$9.30` to `$14.10`** |
| Continuation-rule reach | All 4 admissions fit under both rules up to `$9.60`/admission | Both admissions fit under both rules up to `$9.33` on Admission 1 |
| Downstream lines served | **All four:** full stack + handoff (`#387`/`#136`), full 3-day second-world `curator-knowledge/5` corpus (`#681`/`#677`), 3-day routine recurrence (`#996`/`#177`), and `#336`/`#384`/`#1057`/`#164` watch | Batches 1–4 + handoff + cross-admission continuity (`#387`), shorter (~2-day) corpus; defers 3-day `#136` / `#681` parity |

**Recommendation:** Approve the **3-day / 4-admission / `$48.00` envelope**. `#998` already established standard-build pace (~23 game hours per full admission, reaching 3 days in 3 full + 1 short admission), and `#1027` + `#1047` lowered the expected cost of a full 3-day campaign to `$15–$26`—so one `$48.00` envelope cleanly resolves all four downstream lines without paying for a second campaign later.

## Stop rules

No budget or admission count is renewed silently ([campaign review](../workflows/campaign-admission.md#campaign-review-and-finding-disposition)).

1. **Envelope and admission cap.** Apply both continuation rules before every admission; never exceed the approved admission count.
2. **Preflight refusal.** Nothing launches and `$0` is spent; fix and re-run preflight (does not consume an admission).
3. **Custody, cleanup, or log-safety failure.** Halt immediately with zero relaunch.
4. **Provider account, credit, or sustained `flex` refusal.** Stop on account/credit refusal or unknown refusal; sustained `flex` `429` exhaustion that blocks live curation across a full admission pauses before the next admission for an owner disposition (do not silently fall back to `default` tier).
5. **Target reached.** Stop once the decompressed save clock reaches `259,200` game seconds past start (or after Admission 2 under the Alternative).
6. **Character death.** Operator watches spectator view and triggers Pause on observed death; death ends the lineage with no relaunch.
7. **Unverified save or operator Pause.** Counts as one approved admission; verify `#1055` Pause `agenda-final.json` reconstruction if triggered; next admission reloads the last verified save and reports game time lost.
8. **Between-admission lead review.** Inspect build (Admission 1), stop trigger, handoff telemetry (`001 -> 002`), save & clock, `curator-knowledge/5` publication chain, `flex` tier/billing/latency/429s, interleaved hygiene behavior (including `60 s` wall limit), `#1037` uncovered-cut count, and spend before admitting the next run.

## Pass, Partial and Fail criteria

Every admission retains its sealed store and receipt, character-creation frames (Admission 1), ending save file, curator and grooming ledgers, and an operator note (expected empty).

1. **Standard build.** Unmodified `8/8/8/8` stats, zero traits, non-overpowered lifestyle verified from Admission 1 creation frames and ending saves.
2. **Horizon and normal endings.** Reaches the approved target (`259,200` game seconds for Recommended; 2 completed admissions for Alternative), with every admission ending in a verified save, separate quit, zero native exit, verified custody, and verified boundary clock continuity.
3. **Continuous memory and `curator-knowledge/5` continuity.** Unbroken `curator-knowledge/5` publication chain across admissions (`v0 -> vN`) with zero Kind 6–7 or frameless `state` violations, zero empty substantive updates emitted, clean `player_agenda` carryover across cuts/handoffs/admissions, verified `player-source-index/1` freezing and at least one cross-admission memory use (player reads a prior-admission record or ancestor source and acts on it).
4. **Natural multi-actor handoff.** At least one admission executes a real `001 -> 002` `player_handoff` inside the admission, verifying Actor `002` starts from the latest adopted `delivered-knowledge/4` and Actor `001`'s committed `player_agenda` while the curator runner drains Actor `001`'s ended tail cleanly.
5. **Non-real-time `flex` curation, hygiene and `#1037` stability.** `100%` of live curator and grooming requests bill on `applied_service_tier: "flex"` with zero unauthorized tier fallbacks and zero proxy breaches; interleaved hygiene obeys its sub-caps (`$0.30`/pass, `<= 10%` share, zero world-fact retirements); and `player-host/13` suffers zero `context-capacity` hard stops (with any `#1037` uncovered cuts preserving `player_agenda`, `recent_intents`, `source_ids`, and pinned `covered_through_operation_id`).
6. **Independence.** Every game input matches a hosted actor's tool result, zero manual knowledge edits, and empty operator notes.
7. **Downstream telemetry reported.** The final run record reports: (a) whether the resulting `curator-knowledge/5` corpus satisfies `#681`/`#677` gating; (b) multi-day routine recurrence metrics informing `#996`/`#177`; and (c) explicit trigger status for `#336`, `#384`, `#1057`, `#164`, and `#1058` S1 hygiene wall time.

The first matching row determines the campaign outcome:

| Outcome | Condition | What follows |
| --- | --- | --- |
| **Fail** | Any custody, cleanup, log-safety, or `curator-knowledge/5` / proxy-cap invariant breach | Fix the defect before any further paid run |
| **Invalid** | Non-standard build, unauthorized tier fallback, or any input/hint/edit outside hosted actors | Retain as development data; require new owner approval before rerunning |
| **Stopped** | Provider account/credit refusal, sustained `flex` refusal, or unknown refusal before target | Report clock reached, cause, and spend; resuming is an owner decision |
| **Partial** | Envelope or admissions run out before target, or character dies | Report clock reached, cause, and spend; no relaunch |
| **Partial** | Target reached, but item 2, 3, 4, or 5 does not fully hold (for example, Actor `001` saves and quits instead of calling `player_handoff`, or hygiene hits `60 s` wall shutoff) | Record exact gap and root cause; owner decides disposition for `#136`, `#681`/`#677`, and follow-ups |
| **Pass** | All seven items hold | Post-wave continuous-memory stack is live-verified (`#387`); `#136` deciding bar (if designated) and `#681`/`#677` second-world corpus gate are met; `#996`/`#177` activation is informed |

## Offline `$0` stand-in rehearsal and preflight

Executed on clean `main` at `b6ba747d01244cc04bc3ee2306dddc5876e72465` with `$0` spend, zero CDDA launches, and zero paid provider calls. All scripts, outputs, and test logs are sealed as [`fresh-world-validation-preflight-1056`](../../data/evidence/fresh-world-validation-preflight-1056.sha256):

- **Live Seatbelt WAL stand-in (`tests.live_curator_stand_in_run --pace 0.25 --steps 45 --actors 2 --poll-seconds 0.5`):** **PASS (`25/25` checks)**, session `017a7bc0a95f4814b3ecfe6ec43bf903` (`results/stand-in-summary.txt`, `results/stand-in-report.json`). Verified `40/60` default triggering across 3 accepted windows (`001` steps `1–41` in `1.392 s`, `001` ended-actor tail `42–46` in `1.225 s`, `002` steps `1–41` in `1.312 s`), automatic pinned `openai/flex` routing (`openRouterRouting.only == ["openai/flex"]`, `requested_service_tier: "flex"`, `prefix-suffix` reservation on reqs 2–3), `36/36` WAL snapshot polls (hold max `1.8 ms`, tx max `1.0 ms`, staging max `32.9 ms`), writer parity (`239.96` vs. `239.96` ops/min), zero live-viewer WAL/JSON errors, and `player-host/13` replay delivering `v2` (`v1` superseded) over `delivered-knowledge/4`.
- **Admission 1 + Admission 2 `campaign-run/14` preflight & hygiene check (`scripts/rehearse.py`, `results/preflight.txt`, `results/read-config.txt`):**
  - Admission 1 fresh-world package (`session=6ae986cb98f5ed8ed4c7a6da1f30c306`, manifest `569821a4…edc4810f`) passed `tools.campaign_package --work-before-bytes 262144000 --ending-before-bytes 312475648` with `1,835,008,000` bytes remaining at ending checkpoint.
  - Admission 2 continuation package (`session=3244c95c1ec0ab9f7f9fedea0be0f4ea`, manifest `3f24a3a2…3d9bb478c`) built from a closed synthetic Admission 1 store + stand-in `v3` `curator-knowledge/5` repository via `tools.knowledge_export` and `tools.source_index --prior-agenda` passed `tools.campaign_package`, preserving committed `agenda.json` (`1` thread, `cut_count=2`) and serving a verified cross-admission `player-source-read/2` (`status="available"`, `clickable=False`, blinded `origin={"admission": "s01", "actor": "001", "step": None}`, SHA-256 PNG match).
  - `tools.curator_host.live_runner.read_config` accepted both the full `curator-runner-config/2` above and a minimal defaults-only file (`trigger_steps=40`, `ceiling_steps=60`, `service_tier="flex"`, `request_timeout_seconds=960`, `openRouterRouting.only=["openai/flex"]`), and verified interleaved hygiene config (`text_only=True`, `max_context_images=0`, `service_tier="flex"`, `host_wall_seconds=60`, `<= 10%` spend-share gate).
- **Focused Python and Node rehearsal suites (`647` tests passed, `0` failed):**
  - Python (`results/python-rehearsal-tests.txt`): `tests/test_wave4c_combined_rehearsal.py`, `tests/test_campaign_player.py`, `tests/test_source_index.py`, `tests/test_curator_runner.py`, `tests/test_campaign_package.py` — **`220 passed`**.
  - Node `tools/player_host` (`results/player-host-tests.txt`): **`359 passed`** (covering `player_agenda`, substantive deltas, `#1037` uncovered-cut fallback, `player_handoff`, and `spend-reserve-reached`).
  - Node `tools/curator_host` (`results/curator-host-tests.txt`): **`68 passed`** (covering `curator-host/2` zero-eviction 16-image cap, byte guard, `flex` `429` deferral, and text-only hygiene).
- **Not covered offline:** Live CDDA save/reload across admissions; real provider `flex` queue latency and `429` rates over `40–60`-step windows and `60 s` hygiene passes; real model choice to call `player_handoff` inside the `120 s` wrap-up window; and live gameplay quality under `#1037` uncovered cuts.

## Open owner decisions and execution checklist

Nothing runs until the owner explicitly approves a spending option in [owner-decisions.md](../decisions/owner-decisions.md) and confirms: (1) envelope & horizon (**Recommended:** `$48.00` / 3 days / up to 4 admissions vs. **Alternative:** `$28.00` / up to 2 admissions); (2) named supervisor operator; and (3) whether this campaign serves as the deciding `#136` assessment or development validation evidence.

Once approved, open a dedicated execution leaf under `#387` and execute in order:

1. Verify `.runtime/user/save/Francis Mills/`, `.runtime/user/config/lastworld.json`, and `.runtime/user/templates/Last Character.template` against sealed `multi-day-standard-build-998-admission-04`, then archive all three under `.runtime/archive/` so `.runtime/user/save/` is empty.
2. Rebuild and qualify `bridge.dylib` at the frozen launch commit via `tools/build_computer.py`; build Admission 1's `campaign-run/14` package and run both offline preflight checks plus a clean-context pre-launch package review.
3. Run `tools.campaign_supervision` with the Admission 1 package and frozen `curator-runner-config/2`.
4. After each admission seals, run `curator-boundary-grooming/2` (`--cap-usd 1.50`, `service_tier: "flex"`) where eligible, seal the admission's evidence, append its row to `data/evaluation/runs.jsonl`, and apply Stop Rule 8 and both continuation rules before building Admission `N+1` with `tools.knowledge_export` and `tools.source_index --prior-agenda`.
5. Publish one dated run record under `docs/acceptance/` grading all seven criteria, the outcome table row, and downstream readiness for `#136`, `#681`/`#677`, `#996`/`#177`, and `#336`/`#384`/`#1057`/`#164`.
