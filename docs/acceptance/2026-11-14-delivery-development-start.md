---
owner: lead
status: historical
kind: run
date: '2026-11-14'
scope: 'The delivery development start (#635): one start of about 200 decisions from the reusable start seven-day-end-08, with the groomed store v18 of the curator scoring delivered and nothing withheld, read end to end before the withholding pilot (#619); approved by the owner on 13 November 2026 ("One dev start, $10 cap")'
---

# The delivery development start (#635)

## At a glance

- **Question.** Does delivery (#461) work in real play: the briefing, the reminders,
  the recall model's cost, the burden on the player, and which reminder cadence `N` the
  pilot should freeze?
- **Result: delivery did not deliver.** Each actor's briefing recall request was answered
  (stop reason `stop`) but the host rejected the answer with the generic reason
  `recall-failed`. Each briefing therefore carried the index alone (32 lines) and **no
  leads**, recall was disabled for the actor, and **no reminder was ever made**: actor
  001 logged 21 reminders as `not-made` (`disabled`). The reply text is not in the trace,
  but the code narrows the cause: a reply that parses as JSON of the wrong shape is logged
  `invalid-recall-selection`, and only a reply that is not parseable JSON at all gives the
  generic `recall-failed`. Both replies stopped normally with their cost reported (72
  output tokens for actor 001's, 21 of them reasoning), which fits a fenced or annotated
  JSON reply; the text itself is not recorded. The fault is its own issue,
  [#642](https://github.com/CVX-Hull/enactive/issues/642).
- **`N` is not chosen.** No reminder was requested, so the run says nothing about the
  cadence. The provisional `N = 10` stated before spend stands unmeasured; the pilot does
  not freeze it from this run.
- **What did work.** The player read the delivered knowledge by itself: seven
  `player_knowledge_read` calls (four by title from the index for actor 001, three by id
  for actor 002), each returning its article with `grants_authority: false`; the index
  lines, the knowledge tools, the delivery telemetry, the handoff and the spend accounting
  behaved as the [delivery boundary](../design/player-context.md#the-delivery-boundary)
  states. One of the articles read was *Open-fire safety*, the lesson of the lineage's
  recorded death by fire four game minutes after the save; the player then built a fire
  ring and kept the fire in it. That is one start, read by the lead, and is not a measure
  of benefit.
- **Play.** The survivor (Morgan Hale, Whitethorn) was alive when the run stopped, **4.05
  game hours** after the load, past the lineage's recorded death; censored by the attempt
  allowance (the orderly stop was requested when 10 attempts, the finish reserve,
  remained). The last frame shows the fire burning inside the ring beside evac shelter
  B-19, with the companion nearby.
- **Spend.** Well inside the \$10 cap and all provider-reported (no request counted at the
  bound); the total and the attempts are the [run ledger](../../data/evaluation/runs.jsonl)
  row (study 635). The ledger does not split play from recall: from the sealed host
  traces, recall was \$0.0058 (two briefing requests) and the rest was play.
- **Owner decision needed.** Whether delivery is checked in play again after #642 is
  fixed, before the pilot, and at what price (asked with this record).

## Method

Frozen before spend and stated on [#635](https://github.com/CVX-Hull/enactive/issues/635#issuecomment-6871740981):

- **Package** `delivery-dev-635` (`campaign-run/7`), session
  `88c9ddd4262c4518808a73c1982904fe`, source `7d02ffb4`; route GPT-6.1 Terra through
  OpenRouter pinned to openai, medium effort, default tier, 39 images in blocks of 20,
  240 HTTP attempts for player and recall together, at most 2 hosts, \$10 limit and a
  \$1.00 finish reserve (the player and recall bounds of \$0.4096 each).
- **Start** `seven-day-end-08` (manifest sha256 `7fc079d1…2cdc6`), installed with
  `tools/starts.py`; it is a byte-identical copy of the save whose copies all loaded
  ([load checks](2026-11-14-start-load-checks.md)). The copied #397 lineage is not held out.
- **Delivered knowledge** `v18` of the [curator scoring](2026-11-13-curator-scoring.md)
  store (commit `ea9f7097`, sealed in `curator-scoring-618`), exported with
  `tools/knowledge_export.py` and nothing withheld: 32 articles, 77 facts, 32 units, 22
  shared facts; `delivered-knowledge.json` sha256 `dad85102…3dbb`.
- **Recall model** the same Terra route, up to 30 requests; **provisional `N = 10`**
  completed input operations per reminder.
- **Mission** the seven-day lineage's last mission without its predecessor's report (so
  the report could not stand in for the store): load the existing world, continue the
  existing survivor, survive indefinitely.
- **Reading.** The lead read both actors' host traces (every briefing, recall and
  reminder event, every knowledge and memory call, the handoff), the receipt, the
  evaluator's record and the last frames; response times are from `tools.evaluate
  host-summary` (`tools/host_analysis.py`'s reader).

## Results

<!-- evaluate-table study=635 core=2 binding=cdda:2 -->
| Run | Arm | Start | End | Game h | Decisions | Setup | Routine pace | Long activities | Out of play | Longest stall | $ / decision | Large rewrites |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| delivery-dev-635 | delivery-dev | S1 | budget | 4.05 | 218 | 4 | 6.0 | 3 · 2.90 h | 67% | 10 | 0.0072 | 36% |
<!-- /evaluate-table -->

**The briefing as delivered.** Both actors received the same block: the coverage stamp
(`curator-coverage/2`, session `sd1a7`), `leads: []` and 32 index lines, labelled
fallible knowledge that grants no authority. The empty leads are the fault above, not a
recall choice: a choice of nothing is logged `silence`, and these were logged `failure`.

**Reminders and silences.** None made. Actor 001 (222 player requests, 215 inputs) logged
21 reminder opportunities as `not-made` with the reason `disabled`, about one per ten
completed inputs, so the cadence counter itself ran as designed. Actor 002 made 7 player
requests (8 with its recall) and ended before its first opportunity.

**Recall requests and their cost.** Two, one per actor's briefing: \$0.001873 and
\$0.003962 (\$0.005835 together), provider-reported; neither read from the cache, and the
second prompt was larger (11,040 against 5,158 text bytes) because actor 002's first
message carries the handoff. The recall prompt puts the actor's first message before the
index, so a cache could not reuse the index across actors; at two requests this costs
nothing worth counting, but reminders reuse the same layout. Neither request counted at
the \$0.4096 bound.

**Time per decision.** Over 229 player responses, p50 6.3 s and p95 9.8 s; 2% within 2 s
and 21% within 5 s. Prompts stayed under 100,000 tokens (24 under 20,000, 99 from 20,000
to 60,000, 106 from 60,000 to 100,000), as the short tool results intend; the seven-day
lineage's median was 7.0 s ([cadence plan](../design/cadence-plan.md#what-the-sealed-traces-show)).
The interval from one request's first tool result to the next was p50 7.0 s.

**Burden on the player.** Small, because almost nothing was pushed: the index block added
about 5 KB (4,900 bytes) to each actor's first message, and seven reads returned whole articles. No
reminder entered the context. Whether reminders burden play is unmeasured.

**The player's own memory tools.** Actor 001 wrote one `work` record just before its
handoff (identity, the fire ring, supplies, threats last seen) and handed off with it;
actor 002 read three articles by id and stopped on the ending request without saving.
Two thirds of the decisions were out of play (the table's "Out of play"): menus for
crafting, construction, cooking and eating.

**Anything that looked wrong.**
- The recall fault (#642): the reply text is not recorded, so the inference above cannot be
  confirmed from the evidence; one failed briefing request silences every reminder.
- The custodian's `ready.json` gives the viewer URL on the run's own port (53894), which
  answered a page request with `{"error":"Unknown current route"}` during the run; the page
  was served on the supervisor's gateway port, 53912 (`gateway_url` in
  `watch-terminal.json`; the viewer behind it is on 53911, `viewer_port` in
  `watch-start.json`). Watching works through the gateway; the field is only misleading.
- The native game was ended by the cleanup's SIGTERM after the orderly stop; the player
  reported no save. The start's final userdir is sealed in `delivery-dev-635-start`.

## Deviations

- **The provider balance was not read before spend.** The [campaign
  procedure](../operations/campaign-run.md#spend-limit) asks for it; the project has no
  tool that reads it without the lead handling the key. Stated before spend. The key's
  credit limit stayed the hard cap and no request was refused.
- **`N` not set**, against the issue's acceptance: the run gave no evidence on the cadence
  because of #642.
- **Not an invalid start.** Inputs reached the game and the copy loaded, so the
  replace-once rule did not apply; the run stands as recorded.

## Removed after sealing

- The package `.runtime/computer-sessions/delivery-dev-635` and its evaluation record
  `.runtime/evaluations/88c9ddd4262c4518808a73c1982904fe` (267 files), each identical to
  `delivery-dev-635` by path and content, after a full verification of the store. Their
  SQLite sidecar files were empty (the write-ahead logs held nothing) and were removed
  before sealing; both stores pass an integrity check.
- The start `seven-day-end-08`, disposed of by `tools/starts.py` into
  `delivery-dev-635-start`.
- The userdir archive `.runtime/archive/userdir-20261114T043016706855Z`, after the
  restored `.runtime/user/` matched it file for file (526 files).

## Evidence

Sealed: `delivery-dev-635` (the package with both actors' traces, frames, receipt and
evaluation record) and `delivery-dev-635-start` (the start's working copy after the run),
in the [evidence index](../../data/evidence/index.json). A replacement start
`seven-day-end-14` was made from the same sealed save, so the pilot again has six fresh
starts (`-09` to `-14`).
