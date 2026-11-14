---
owner: lead
status: historical
kind: run
date: '2026-11-14'
scope: 'The recall fix (#642) checked in real play before merge: a real-model recall check from seven-day-end-09 (limit $1) and a check start of about 200 decisions from seven-day-end-10 (limit $8.43, within #635''s approved $10), both with v18 of the curator scoring delivered and nothing withheld, which set the reminder cadence N the withholding pilot (#619) freezes; owner decisions of 14 November 2026'
---

# The recall fix checked in play (#642)

## At a glance

- **Question.** With the recall fix, do the recall model's replies parse, and does
  delivery work in play: the briefing's leads, the reminders, their cost and burden; and
  which cadence `N` should the withholding pilot (#619) freeze?
- **Result: delivery works.** All 31 recall replies across both runs parsed, all of them
  bare JSON objects; there was no `invalid-recall-selection` and no `recall-failed`. In
  the check start every briefing carried leads (22 articles for actor 001, 12 for
  actor 002) and all 19 reminder opportunities at `N = 10` were made and delivered. In
  the delivery development start (#635) no lead and no reminder reached the player.
- **`N = 10` is frozen for the pilot**, the lead's choice on this evidence. Observed: at
  that cadence no opportunity was lost to a recall still in flight (in the recall check
  at `N = 1`, six of fifteen were, at a faster pace than a full start's: 2.7 s median
  player response on smaller prompts), the recall model cost \$0.073 against \$1.486 of play for actor 001
  (5%), the delivered text was 35,760 characters over 203 player requests, and the
  median prompt was 3% larger than in #635 with response time no slower. Not measured,
  only expected: a shorter cadence would cost more recall requests (the run's allowance
  is 30) and repeat more; a longer one would follow play less closely.
- **What the recall model does.** It selects generously and repeats itself. A briefing
  names most of the index (22 of 32 articles), and the reminders follow the phases of
  play (travel and safe mode early and late; fire, tinder and cooking while the player
  made fire), but "Open-fire safety" was sent in 13 of 19 reminders.
- **Spend.** \$1.70 in all: \$0.111 for the recall check (\$0.030 recall, \$0.081 play)
  and \$1.590 for the check start (\$0.080 recall, \$1.509 play). Every attempt
  carried a provider-reported cost.
- **For the pilot: its price is far below what the simulation assumed.** The
  [withholding simulation](2026-11-13-withholding-simulation.md) priced a 200-decision
  start at \$3.58 of play, and ×1.67 to ×2.0 of that with recall (\$6.0 to \$7.2). This
  start of 197 decisions cost \$1.51 of play and \$0.08 of recall, \$1.59 in all. The
  pilot's six starts would cost about \$10 against its \$70 cap, and the full study's
  price falls with them. Nothing found calls for a change to the pilot's design.
  Neither run withheld anything, so neither shows recall or its cost when half the
  units are withheld. Because briefings name most of the index, "delivered" in the
  pilot will mostly mean "named in the briefing".
- **Not known.** Whether the leads and reminders changed play (nothing here compares);
  whether repeating one article matters; what `N` below 10 would lose in a full-length
  start.
- **Owner decision needed.** What the pilot does with the lower price: put to the owner
  with this record.

## What was run

Both runs used the pull request's reviewed head `6da93dfbeadbd130eb50ae02be72be231578070f`,
checked out in the main checkout, and delivered `v18` of the
[curator scoring](2026-11-13-curator-scoring.md) store (sealed in `curator-scoring-618`)
with nothing withheld: 32 articles, 77 facts, `delivered-knowledge.json` sha256
`dad85102…3dbb`, the same file as #635. Both statements were posted on the pull request
before spend.

- **Player.** GPT-6.1 Terra through OpenRouter pinned to openai, medium effort, default
  tier, as in #635.
- **Recall model.** The same pinned route, declaring a 32,768-token window and 4,096
  output tokens, so its bound for a request without a cost record is \$0.06144 (#635
  declared the player's 262,144-token window, \$0.4096). A recall request was 1,200 to
  5,200 prompt tokens before images in these runs and #635.
- **The recall check** (`recall-check-642`, session `ad4c2d86f4014c1da755d21b33c18c1e`,
  start `seven-day-end-09`): recall at every completed input, up to 16 recall requests,
  30 attempts in all, 8 images in blocks of 4, one host, limit \$1, finish reserve \$0.48.
- **The check start** (`delivery-check-642`, session `d073e0e4acac4303841bf92e0e3155c8`,
  start `seven-day-end-10`): `N = 10`, up to 30 recall requests, 240 attempts in all,
  39 images in blocks of 20, at most two hosts, limit \$8.43, finish reserve \$1.00.

## The recall check

It ended in an orderly stop on the attempt reserve, with all 30 attempts charged: 20
player requests and 10 recall requests. Of the 15 reminder opportunities before the stop,
9 were requested and 6 were not made because another recall was in flight. A
`player_knowledge_read` the player called during the stop was refused (not dispatched).

| Recall | Count | Detail |
| --- | ---: | --- |
| Briefing, selected | 1 | 27 of 32 articles, 70 facts; 6,358 characters with `request-1` |
| Reminders, selected and delivered | 7 | 6 to 11 articles each |
| Reminders, silence | 2 | `{"articles":[]}` |
| Not made: another recall in flight | 6 | |
| Not made: orderly stop | 2 | at the end of the run |

## Results

<!-- evaluate-table study=642 core=2 binding=cdda:2 -->
| Run | Arm | Start | End | Game h | Decisions | Setup | Routine pace | Long activities | Out of play | Longest stall | $ / decision | Large rewrites |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| delivery-check-642 | recall-fix-start | S1 | budget | 2.86 | 197 | 4 | 5.7 | 3 · 1.85 h | 72% | 14 | 0.0081 | 33% |
<!-- /evaluate-table -->

The survivor was alive when the run ended (censored, `budget`). Actor 001 played 203
requests and handed off. Actor 002 played 9; the attempt reserve's orderly stop was
requested with ten attempts left, and a `computer_input` it called during the stop was
refused (not dispatched). 233 of the 240 attempts were used.

## The check start, read end to end

- **Briefing.** Actor 001's briefing recall chose 22 articles (6,176 characters of leads
  and index), actor 002's 12 (5,593 characters). Each was sent with the actor's first
  request.
- **Reminders.** Actor 001 had 191 `computer_input` results; every tenth asked for a
  reminder, 19 in all, and each was selected (4 to 9 articles, 1,085 to 2,185
  characters) and delivered with the next player request (`request-13` to
  `request-201`, about every 10 requests). There was no silence and no opportunity
  lost to a recall in flight.
- **What the reminders named.** Travel, terrain, water travel and safe mode at the
  start and the end; evacuation-shelter salvage and roof water early; fire-making,
  tinder, the bow drill, open-fire safety and cooking cattails through the middle,
  while the player made a fire. Articles repeat: "Open-fire safety" in 13 reminders,
  "Cooking cattails" in 10, "Safe mode" and "Tinder" in 9 each.
- **The player's own reads.** Actor 001 made seven `player_knowledge_read` calls (#635:
  seven over its two actors, without leads, and no query) and one `player_knowledge_query`, "brazier fire containment
  fireplace" (`request-178`), which found no record: the store has no article on
  containing a fire.
- **Fire, and what the handoff carried.** The player lit an outdoor fire on a road and
  recorded it as dangerous, then planned a stone fire ring (and noted that a brazier
  needs a bucket it had not found); its handoff to actor 002 names "dangerous outdoor fire, and
  tentative contained-fire plan". The reminders sent "Open-fire safety" through that
  stretch. Whether that helped is for the judges, not for this record.
- **Recall cost.** Actor 001: 20 recall requests, \$0.0731 (\$0.0037 each), median
  3.7 s; play \$1.486. Actor 002: 1 request, \$0.0072.
- **Time per decision.** 7.1 s of wall time per player request for actor 001 (7.2 s in
  #635); player response median 6.1 s, 95th percentile 9.6 s (6.4 s and 9.8 s in
  #635).
- **Burden.** Actor 001's prompts: median 60,271 tokens (58,349 in #635), last
  103,172; cache share 94.7% (the same in #635); \$0.00732 per player request (\$0.00697). The
  reminders stay where they were first sent, so the cache holds.

**Method.** The results table is `tools/evaluate evaluate-table` over the evaluation
records; spend is from the receipts and the [run ledger](../../data/evaluation/runs.jsonl).
The other readings are from the sealed `host.jsonl` events, read by a one-off script:
response time is `response-complete` minus `request-start` per request, split by
`request_role`, with nearest-rank percentiles as in `tools/host_analysis.py`; prompt
tokens are input plus cache read plus cache write from each player response's usage, and
the cache share is cache read over that sum; cost per request is the counted cost.

## Deviations

- **The recall model declares a smaller window than the player.** This sets its bound,
  and so the finish reserve, to what a recall request can use; with the player's window
  a \$1 check would have refused most reminders on the reserve rule. The model and
  route are the player's.
- **The recall check is not in the run ledger.** It is a diagnostic package, like the
  [start load checks](2026-11-14-start-load-checks.md); its spend is stated here. The
  check start is study 642's one row.
- **The check start was capped by attempts, not by decisions.** 197 decisions against
  about 200 asked; the attempt reserve stopped actor 002 after 9 player requests. Recall
  requests count against the same 240 attempts (21 here, 2 in #635), which is most of the
  difference from #635's 218 decisions; pilot starts under the same allowance will land
  near 200.
- **The recall model's output limit is 4,096 tokens**, against the player's 16,384; the
  largest recall reply used 299, and every reply stopped normally.
- **Replacement starts are not load-checked.** `seven-day-end-15` and `-16` were made
  from the same sealed save as the starts the load checks loaded, byte for byte.
- **The provider balance was not read before spend**, as in #635; the key's credit
  limit stays the hard cap.

## Evidence

- `recall-check-642`: the recall check's package and evaluation record (56 files).
- `delivery-check-642`: the check start's package, both actors' traces, frames, receipt,
  session store and evaluation record (247 files).
- `recall-check-642-start` and `delivery-check-642-start`: the final userdirs of
  `seven-day-end-09` and `-10`, which were disposed of and replaced by
  `seven-day-end-15` and `-16`. The six fresh starts are `seven-day-end-11` to `-16`.
