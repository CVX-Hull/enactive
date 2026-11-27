---
owner: lead
status: historical
kind: measurement
date: '2026-11-27'
scope: 'Pre-merge offline #998 82-update/81-cut and v94 785-ancestor-frame replays ($0) plus real-model C-MODEL-CHECK ($0.0100213 counted USD of $1.00 standing allowance, $0 gameplay spend, zero CDDA launches) for Batch 2 player continuity and post-cut delivery (#1025, #1026: campaign-run/14, player-host/13, player-host-inputs/5, player-source-index/1, player-source-read/2, player-agenda-continuation/1)'
---

# Batch 2 player continuity, post-cut delivery, and `C-MODEL-CHECK` (#1025, #1026)

## At a glance

- **Question.** Before merging the coordinated Batch 2 `S-MIGRATION` PR ([#1025](https://github.com/CVX-Hull/enactive/issues/1025), [#1026](https://github.com/CVX-Hull/enactive/issues/1026): `campaign-run/14`, `player-host/13`, `telemetry_version: 13`, `player-host-inputs/5`, `player-source-index/1`, `player-source-read/2`, `player-agenda-continuation/1`, and the 5-session `#963`+`#998` archive cutover), do `$0` offline replays on sealed `#998` data and a real-model `C-MODEL-CHECK` on pinned `openai/gpt-6.1-terra` confirm zero empty updates, claim-level visibility under unchanged leads, bounded cut-briefing plus `changes_since` envelopes, lossless same-lineage ancestor frame resolution, and real-model adherence to `player_agenda` and `player-source-read/2`?
- **Answer — All `$0` replays and the real-model `C-MODEL-CHECK` passed (`$0.0100213` counted provider spend of the `$1.00` standing `C-MODEL-CHECK` allowance, `$0` gameplay spend, zero CDDA launches).**
  - **`#998` 82-update / 81-cut replay (`$0`):** Across all `102` validated sealed `#998` snapshots (`v0`–`v101`, projected in-memory to `delivered-knowledge/4`) and the exact request-aligned history of `#998` Admissions 01–04, `player-host/13` folded `80/82` historical updates into `BEGIN CONTEXT CUT` (`changes_since`), delivered `2` genuinely substantive mid-segment updates (**`0` empty updates emitted**, down from `78/82` empty updates in `player-host/12`; mid-segment update bytes dropped from `27,905` to `4,398` bytes, `-84.2%`), surfaced **`316` claim-level updates under unchanged article leads** across `81` cuts (`317` across all `82` standalone pairs), and kept every combined briefing + `changes_since` envelope at or below `8,443` chars (`0` over the `24,000`-char cap, `0` deltas over `12,000` chars).
  - **`#998 v94` 785-ancestor-frame replay (`$0`):** Building `player-source-index/1` via `tools/source_index.py` over sealed `#998` Admissions 01–03 verified all `3` ancestor roots (`s01`–`s03`) and resolved all **`785/785`** ancestor frames cited in `#998` Admission 04's `v94` `delivered-knowledge.json` through `Application.read_player_source` (`player-source-read/2`, `status: "available"`, `clickable: false`, blinded `origin`, SHA-256 verified) while rejecting undisclosed or cross-lineage frames cleanly as `unavailable` without stopping input custody (`tests/test_source_index.py`).
  - **Real-model `C-MODEL-CHECK` (`$0.0100213` counted USD, `ok: true`, `reason: "task_complete"`):** On pinned `openai/gpt-6.1-terra` (Medium effort via OpenRouter) through real `tools/player_host/run.mjs` (`player-host/13`, zero recall) and real loopback Python `Application`/`Journal`/`SourceIndex`/MCP over `4` player requests (`0` unpriced, `0` recall requests), the model read the opening briefing orientation, created an active `player_agenda` thread (`verify-tank`, ref `evac-shelter-water`, persisted to `--agenda-out`), read `shelter-basement-tank` by `state_key`, retrieved its ancestor depiction via `player_source` (`player-source-read/2`, `origin: {"admission":"s01","actor":"001","step":7}`, `clickable: false`, `clock_label: "Day 2, 09:40 AM"`), and settled cleanly via `player_finish`.
- **What is not known.** These checks exercise offline `#998` replays and a short 4-request synthetic-MCP check without launching CDDA. They do not qualify live multi-day gameplay on `campaign-run/14` / `player-host/13`, a live multi-actor handoff, or causal survival benefit, which wait for post-wave fresh-world live validation after explicit owner approval.
- **Owner decisions needed.** None. Spend stayed within the standing `$1.00` per-change `C-MODEL-CHECK` allowance ([owner decision](../decisions/owner-decisions.md#one-dollar-for-prompt-and-parser-checks)).

[Issue #1025](https://github.com/CVX-Hull/enactive/issues/1025) · [Issue #1026](https://github.com/CVX-Hull/enactive/issues/1026) · [Player host contract](../contracts/player-host.md) · [Player ports contract](../contracts/player-ports.md)

## `$0` `#998` 82-update / 81-cut replay

Replayed all `102` sealed `#998` snapshots (`v0`–`v101`, projected to `delivered-knowledge/4` via `tools/knowledge_retrieval_benchmark._project_v3_to_v4`) against production `tools/player_host/knowledge.mjs` (`validateKnowledge`, `openingBriefing`, `cutBriefing`, `substantiveDelta`, `updateDelivery`, `cutMarker`) across `#998` Admissions 01–04:

| Metric | Historical `player-host/12` (`#998`) | Replayed `player-host/13` |
| --- | ---: | ---: |
| Validated `#998` snapshots (`v0`–`v101`) | `102` | `102` |
| Historical update deliveries / cuts | `82` / `81` | `80` folded into cuts, `2` mid-segment |
| Empty update messages emitted | `78` (`95.1%`) | **`0`** (`0.0%`) |
| Mid-segment update bytes | `27,905` | `4,398` (`-84.2%`) |
| Cut `changes_since` claim updates (unchanged lead) | `0` (invisible) | **`316`** (`317` across all `82` standalone pairs) |
| Cut `changes_since` bucket totals | — | `4` corrections, `113` state changes, `0` flag changes, `1` added fact, `342` claim updates, `21` article changes |
| Peak combined briefing + `changes_since` JSON chars | — | `8,443` (`0` over `24,000`-char cap; `0` deltas over `12,000` chars) |

## `$0` `#998 v94` 785-ancestor-frame replay

Executed inside `tests/test_source_index.py::test_998_v94_resolves_all_785_ancestor_frames_read_only`:

- `tools/source_index.build_source_index` indexed sealed `#998` Admissions 01–03 (`3` verified `sealed-evidence` roots, zero PNG copies, non-WAL read-only SQLite).
- All `785/785` ancestor frames cited in `#998` Admission 04's `v94` `delivered-knowledge.json` resolved through `Application.read_player_source` (`player-source-read/2`, `status: "available"`, `clickable: false`, blinded `origin`, verified SHA-256).
- Cross-world, cross-lineage, symlink escape, live-WAL, missing-file, digest-mismatch, and undisclosed ancestor probes returned clean `unavailable` responses with `0` `runtime.stop` calls.

## Real-model `C-MODEL-CHECK` (`$0.0100213` counted USD)

- **Route:** `openai/gpt-6.1-terra` through OpenRouter at Medium effort (`player-host/13`, zero recall, `$1.00` hard cap, `$0` gameplay spend, zero CDDA launches).
- **Initial local setup failure (`$0.00`, `0` provider requests):** First invocation exited before any HTTP request (`mcp-connection-closed`) because the worktree MCP config pointed to the worktree's absent `.venv` instead of the shared Python interpreter. Fixing `mcp.command` ran the real check on the first provider attempt.
- **Passing run (`$0.0100213` counted USD, `4` player requests, `0` recall requests, `0` unpriced):**
  - `settled`: `ok: true`, `reason: "task_complete"`, `requests: 4`, `player_requests: 4`, `spent_usd: "0.0100213"`, `unpriced_requests: 0`.
  - `player_agenda`: `1` committed `player-agenda` event (`op: "upsert"`, `id: "verify-tank"`, `refs: ["evac-shelter-water"]`), persisted atomically to `--agenda-out` as valid `player-agenda-continuation/1`.
  - `player_knowledge_read` + `player_source`: read `shelter-basement-tank` by `state_key`, then read ancestor `depiction_source_id` (`player-source-read/2`: `status: "available"`, `origin: {"admission":"s01","actor":"001","step":7}`, `clickable: false`, `clock_label: "Day 2, 09:40 AM"`).
  - `player_finish`: quoted `origin`, `clickable: false`, and `clock_label: "Day 2, 09:40 AM"` verbatim and confirmed retirement of background recall.
