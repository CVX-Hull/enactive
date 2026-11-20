---
owner: lead
status: historical
date: '2026-11-19'
kind: run
scope: 'Approved Wilderness / Campground acquisition with verified setup, one timed-out player request and restored custody'
---

# Talty Campground acquisition stopped on a player request (#794)

## At a glance

The approved initial admission created Talty and verified Wilderness, Campground and Survivor before Morgan Reed entered play at 08:00:00 on spring day 61. The last retained in-play frame showed 08:01:31. The player collected tablets, matches and food. No natural wake, eligible delayed decision, or named effect packet was observed. The result qualifies this setup as a development start and describes a stream failure. Memory efficacy remains open.

The confirmed initial slot used one native lane and no operator game inputs. The owner approved $90 for this fresh world and up to five conditional reloads, with 105 custody minutes and 95 actor minutes including ten for ending per admission. Each slot had a $12 provider-reported stop threshold and $1.50 ending reserve. The ordinary pinned OpenRouter OpenAI Terra medium route and its full context, v18 knowledge and recall were retained. Source was `9839c592ca5044463dc499dcc2c6364ffa9af819`, manifest `1482a107ec57159d3f44f41cee8893b8b69d0becf1f178a24e698c47102242e5`, approval inventory `e280cc01a6742c69b3416d441b527a88d2fd101f3dbe9474f7c23d0b8f483a2b`, and reload/scoring procedure `82c843500bbb80b41fdf8919b28391e1958063bc16ab0ff9cf7a612320b061d2`.

## Observed setup and stop

| Source suffix | Rendered evidence |
| --- | --- |
| 83 and 138 | The Talty creation confirmation shows default settings. The New Game submenu separately highlights Custom Character before confirmation. |
| 324 and 325 | Description shows Wilderness, Campground, Survivor and Morgan Reed before the separate confirmation. |
| 408 | Morgan Reed is named in play at Campground on spring day 61 at 08:00:00. |
| 500, 666 and 816 | The tablet pickup, matchbook location and multiple murky-water sources are early observations. These supply no delayed decision. |
| 1149 | Morgan is in Campground at 08:01:31, with the cheese pickup in the recent log. This is the last observed game clock. |

Player request 57 sent a projected context with 36 images. The response reached HTTP 200 and its first chunk arrived about 3.37 seconds after fetch. The host hit the configured 60-second request timer without a complete turn, tool dispatch from that request, or reported charge. The timeout stopped the deciding host. The terminal watcher verified its coverage and the custodian revoked input. The native process exited after forced cleanup. No ordinary Save or separate normal Quit qualified the checkpoint, so zero reloads were admitted. The location of the upstream stall remains unknown. [Offline recovery follow-up #795](https://github.com/CVX-Hull/enactive/issues/795).

## Accounting and cleanup

The [receipt-derived run ledger](../../data/evaluation/runs.jsonl) contains one #794 admission. The accounting trace settled and one player request remains unpriced. The unused authority expired. Use `python -m tools.run_ledger totals --study 794` to reproduce the exact provider subtotal, custody time and attempt counts.

The [metrics snapshot](../../data/evaluation/run-metrics.jsonl) comes from the maintained CDDA evaluator on the settled admission. Its observation windows are distinct from the visible game clock. Replay the evaluator with the original run basename and the sealed `player-journal.sqlite3` to reproduce the snapshot.

The operator verified all six owned process groups absent, all three loopback listeners closed, and the game lock idle. Restoration archived the closed 19-file study userdir and returned the original 82-file userdir with identical content hashes. The separate original recovery archive remains. The [private evidence index](../../data/evidence/index.json) binds `talty-campground-stream-stop-794` to the exact admission, its original receipts and operator records, and the study userdir and fresh configuration archives.

[Approval and terminal result #794](https://github.com/CVX-Hull/enactive/issues/794).
