---
owner: lead
status: historical
kind: measurement
date: '2026-11-25'
scope: 'Pre-merge C-MODEL-CHECK for player-host/12 and player-knowledge/3 (#950, merged in PR #956 at 95f06058): 3 bounded runs, $0.0190479 total counted provider spend of $1.00 allowance, $0 gameplay spend (zero CDDA launch), verifying compact query hits, exact read, best-effort context cut with recent_intents, and reminder recall already_in_context deduplication.'
---

# Pre-merge real-model check for `player-host/12` and `player-knowledge/3` (#950)

## At a glance

- **Question.** Before merging the coordinated `player-host/12`, `telemetry_version: 12`, and `player-knowledge/3` migration ([#950](https://github.com/CVX-Hull/enactive/issues/950), merged in [PR #956](https://github.com/CVX-Hull/enactive/pull/956) at `95f06058` with `6/6` protected CI green), do real player and recall requests on the pinned route correctly parse and act on `player-knowledge/3` compact query hits (Ballot 8), exact-first reads (Ballot 9), best-effort context cuts with ephemeral `recent_intents` (Ballot 4 / Ballot 6), and reminder recall `already_in_context` deduplication (Ballot 2)?
- **Answer — PASS across 3 bounded runs (`$0.0190479` total counted provider spend of the `$1.00` `C-MODEL-CHECK` allowance, `$0` gameplay spend, zero CDDA launches).**
  - **Run 1 (initial attempt, `$0.005666`):** `recall-1` selected `["water-purification", "shelter-heating"]` (`$0.001218`), and `request-1` called `computer_observe` and `player_knowledge_query("purify water")` (`$0.004448`), after which the synthetic 1×1 PNG was rejected at upstream stream-start.
  - **Run 2 (Ballot 6 + Ballot 8 verification, `$0.0049125`, `ok: true`, `reason: "task_complete"`):** Across `3` player requests and `1` recall request, `recall-1` selected `["water-purification", "shelter-heating"]` (`$0.001268`), `request-1` called `player_knowledge_query("purify water")` and received `player-knowledge/3` compact `hits`, `request-2` called `player_knowledge_read("water-purification")` and accurately extracted crafting key `&` and `5 minutes per serving`, and `request-3` applied a real context cut (`cut_result: "best_effort"`, `removed_turns: 1`, `6,682 -> 4,897` tokens) after which the model quoted `recent_intents` (`["Inspect the evac shelter before boiling water", "Search knowledge for water purification"]`) verbatim in `player_finish`.
  - **Run 3 (Ballot 2 reminder recall `already_in_context` verification, `$0.0084694`, `ok: true`, `reason: "task_complete"`):** Across `3` player requests and `3` recall requests (`0` invalid recall selections, `0` overlap with `already_in_context`), `recall-1` (`briefing`) selected `["water-purification", "shelter-heating", "bandage-bleeding"]`, `recall-2` (`reminder`) returned `{"articles":[]}` (`silence`), and `recall-3` (`reminder`) selected only the unshown standalone fact `["shelter-basement-water-heater"]`.
- **What is not known.** These three short synthetic-MCP checks verify prompt/schema parsing and real-model adherence on the pinned route without launching CDDA; they do not measure sustained gameplay behavior, long-horizon multi-cut cache behavior, or live curator interaction, which wait for the consolidated live validation ([#943](https://github.com/CVX-Hull/enactive/issues/943)).
- **Owner decisions needed.** None. Spend stayed within the standing `$1.00` per-change `C-MODEL-CHECK` allowance ([owner decision](../decisions/owner-decisions.md#one-dollar-for-prompt-and-parser-checks)), and `#950` merged in PR #956 (`95f06058`).

[Issue #950](https://github.com/CVX-Hull/enactive/issues/950) · [PR #956](https://github.com/CVX-Hull/enactive/pull/956) · [Player host contract](../contracts/player-host.md) · [Porter2 and replay gates (#949)](2026-11-25-player-host-12-porter2-and-replay-gates-949.md)

## Run summary

All three runs used the real player host on the pinned route with a synthetic MCP fixture, a `$1.00` hard cap, and zero CDDA launches (`$0` gameplay spend). Counted provider spend summed to **`$0.0190479` USD**:

| Run | Focus | Outcome | Player / recall requests | Counted USD | Observed behavior |
| --- | --- | --- | --- | ---: | --- |
| 1 | Initial attempt | Upstream stream-start rejected 1×1 PNG | `1` / `1` | `$0.0056660` | `recall-1` selected `["water-purification", "shelter-heating"]` (`$0.001218`); `request-1` called `computer_observe` and `player_knowledge_query("purify water")` (`$0.004448`). |
| 2 | Ballot 6 + Ballot 8 | `ok: true`, `reason: "task_complete"` | `3` / `1` | `$0.0049125` | `recall-1` selected `["water-purification", "shelter-heating"]` (`$0.001268`); `request-1` queried `"purify water"` (`player-knowledge/3` compact `hits`); `request-2` read `"water-purification"` and extracted crafting key `&` and `5 minutes per serving`; `request-3` ran a real cut (`cut_result: "best_effort"`, `removed_turns: 1`, `6,682 -> 4,897` tokens) and `player_finish` quoted `recent_intents` verbatim. |
| 3 | Ballot 2 (`already_in_context`) | `ok: true`, `reason: "task_complete"` | `3` / `3` | `$0.0084694` | `0` invalid recall selections, `0` overlap with `already_in_context`: `recall-1` (`briefing`) selected `["water-purification", "shelter-heating", "bandage-bleeding"]`; `recall-2` (`reminder`) returned `{"articles":[]}` (`silence`); `recall-3` (`reminder`) selected only unshown standalone fact `["shelter-basement-water-heater"]`. |
| **Total** | — | — | `7` / `5` | **`$0.0190479`** | `1.90%` of the `$1.00` `C-MODEL-CHECK` allowance; `$0` gameplay spend. |

## Detailed checks

### Run 1 — Initial attempt (`$0.005666`)

- `recall-1` selected `["water-purification", "shelter-heating"]` at `$0.001218`.
- `request-1` called `computer_observe` and `player_knowledge_query("purify water")` at `$0.004448`.
- The fixture's synthetic 1×1 PNG was rejected by upstream stream-start before completing the turn; Runs 2 and 3 replaced the 1×1 PNG with a valid image fixture.

### Run 2 — Compact query hits, exact read, and best-effort cut with `recent_intents` (`$0.0049125`)

- Settled cleanly (`ok: true`, `reason: "task_complete"`) across `3` player requests and `1` recall request.
- `recall-1` selected `["water-purification", "shelter-heating"]` (`$0.001268`).
- `request-1` called `player_knowledge_query("purify water")`, receiving the `player-knowledge/3` compact `hits` envelope.
- `request-2` called `player_knowledge_read("water-purification")` and accurately extracted crafting key `&` and `5 minutes per serving` from the full article.
- `request-3` triggered a real context cut (`cut_result: "best_effort"`, `removed_turns: 1`, reducing estimated context from `6,682` to `4,897` tokens), and the model quoted `recent_intents` (`["Inspect the evac shelter before boiling water", "Search knowledge for water purification"]`) verbatim in `player_finish`.

### Run 3 — Reminder recall `already_in_context` deduplication (`$0.0084694`)

- Settled cleanly (`ok: true`, `reason: "task_complete"`) across `3` player requests and `3` recall requests, with `0` invalid recall selections and `0` overlap with `already_in_context`.
- `recall-1` (`briefing`) selected `["water-purification", "shelter-heating", "bandage-bleeding"]`.
- `recall-2` (`reminder`) returned `{"articles":[]}` (`silence`) when no unshown eligible item remained.
- `recall-3` (`reminder`) selected only the unshown standalone fact `["shelter-basement-water-heater"]`.

## Merge provenance

- **Pull request:** [PR #956](https://github.com/CVX-Hull/enactive/pull/956) (merged at commit `95f06058`, `6/6` protected CI checks green).
- **Gameplay spend:** `$0` (zero CDDA launch).
- **Provider check spend:** `$0.0190479` counted USD under the `$1.00` `C-MODEL-CHECK` standing allowance.
