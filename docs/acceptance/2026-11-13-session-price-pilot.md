---
owner: lead
status: historical
kind: run
date: '2026-11-13'
scope: 'The session price pilot of the memory screen (#460, protocol of 13 November 2026): ten curator sessions, each over a sealed window of 20 steps of the seven-day lineage''s last admission, continuing the store the brief gate built, to price curator sessions during play. Curator sessions only; no game launch'
---

# Session price pilot on the seven-day lineage (#460)

## At a glance

- **Result.** A curator session over 20 decisions cost a median of \$0.20 and took a
  median of 99 s. All ten sessions sealed with an accepted submission; none reached its
  cap or was re-run. The pilot spent \$2.34 of its \$20 stop.
- **For a 200-decision start** at those rates, ten sessions cost about \$2.34, against
  about \$3.30 for the play itself: the curator adds about 70% to the cost of play, not
  the three or four times the protocol estimated.
- **For the cut.** Play took 6 to 8 s a decision here, 120 to 170 s for 20. Sessions took
  57 to 153 s, so a session finishes before the next window fills. Coverage then trails
  play by the window plus the session's run time: 12 to 20 decisions when a session
  ends, up to about 40 just before the next one does. That is on either side of the
  about 24 decisions the cut needs.
- **The store keeps growing.** It went from 195 facts and 102,594 bytes to 279 facts and
  161,752 bytes over the ten windows, about 6,000 bytes for every 20 decisions.
- **Question.** What does a curator session over 20 new decisions cost, in dollars and
  seconds? That settles whether the cut, which needs the curator within about 24
  decisions of play, is affordable.
- **Stop.** \$20, taken from the curator proxy's ledger. It runs only because the
  [brief gate](2026-11-13-curator-brief-gate.md) passed.

## Frozen inputs

The code and the brief are `main` at `9d30790`, as for the brief gate. The windows and
this page are frozen on the branch `memory-screen-gates` before the first session.

| Input | Value | sha256 |
| --- | --- | --- |
| Protocol | `docs/design/memory-screen-protocol.md` at `9d30790` | `9aae71f86f2e4d5ad10b64cca3e018206a57a34472ebc7a0ea7432f26568de40` |
| Curator brief | `tools/curator_host/prompt.md` | `c5ca0ce7cc1c191360669b908e67e0d0c80471bf906ec77acbed6ef894360a6b` |
| Windows | `docs/acceptance/assets/2026-11-13-session-price-pilot-windows.json` | `4c189e3dbddf53754e231795b6fa654858346191bda7c09f22e13906adf6280f` |
| Arm and prices | as in the brief gate's record | |

- **Windows.** Ten consecutive windows of the last admission, `sd1a7`, which no gate
  session read. Its first actor has 156 operations (158 provider requests) and its
  second 53 (55 requests). The windows are the first actor's operations 1 to 156 in
  twenties (the eighth is 141 to 156, 16 operations, the actor's end), then the second
  actor's 1 to 40. A window counts operations, not requests; here 20 operations are
  about 20 to 21 requests, so a window is close to the protocol's 20 new decisions.
- **The runner's hash of a windows list** is of its canonical JSON, not of the file.
  The first window's file gives `b5fd5c53…` and the other nine's `c4006a23…`; each
  run's `summary.json` records it as `windows_sha256`.
- **No window gives a game time**, so each coverage stamp records it as null.
- **The store.** A copy of the brief gate's repository at `v6` (commit `d9ebd5f`, with
  the open draft `remaining-loot`), made before any pilot session, at
  `.runtime/knowledge/shadow-454/pilot-from-gate/terra/397/`. The gate's own repository
  is left as its check read it. Each window continues the store the previous one left.
- **Limits.** 120 requests, 1,800 s wall clock, 32,768 output tokens, 16 context images
  in blocks of 8, as for the gate.
- **Session cap.** \$8. The gate's largest single reservation was \$2.22. At \$8 the host
  tells the curator to write at \$3.40, refuses reading at \$5.44, and the proxy refuses
  a request from about \$5.78 spent, so the host's writing-only phase comes before the
  proxy's refusal.

### Stops, re-runs and continuing

- **What counts as a price sample.** Every session that seals counts, including one
  that finishes with no submission because its window had nothing new to store. Such
  a session is not re-run.
- **A session that does not seal or whose submission is rejected** stops the run
  (`--stop-on-abort`, `--stop-on-reject`). If the cause was its \$8 cap, it is re-run
  once at \$16 with `--double-session-cap`; otherwise it is re-run once as it was. A
  second stop of the same window ends the pilot.
- **A session cut by the \$20 stop**, whose cap was below \$8 because less remained, is
  reported as cut, is not re-run and is not counted as a price sample.
- **Continuing after a stop.** A re-run is one invocation with the one window. The
  windows after it follow in another invocation that takes the frozen list's remaining
  entries in order, unchanged, on the same `--knowledge-root`, with a new `--out`.
- **`REMAINING`** is \$20 less the sum of `charged` over every `proxy-ledger.jsonl` under
  the pilot's output directories, less any `pending_reserved_usd` in a
  `proxy-close.json`.
- **The first window runs alone** and is read before the other nine.

Commands, from the main checkout:

```bash
.venv/bin/python -m tools.curator_host.shadow --arm terra --lineage 397 \
  --windows-file WINDOW_ONE --cap-usd 20 --session-cap-usd 8 --max-output-tokens 32768 \
  --stop-on-reject --stop-on-abort \
  --knowledge-root .runtime/knowledge/shadow-454/pilot-from-gate/terra/397 \
  --out .runtime/curator-shadow/pilot-first
.venv/bin/python -m tools.curator_host.shadow --arm terra --lineage 397 \
  --windows-file WINDOWS_TWO_TO_TEN --cap-usd REMAINING --session-cap-usd 8 \
  --max-output-tokens 32768 --stop-on-reject --stop-on-abort \
  --knowledge-root .runtime/knowledge/shadow-454/pilot-from-gate/terra/397 \
  --out .runtime/curator-shadow/pilot-rest
```

`WINDOW_ONE` and `WINDOWS_TWO_TO_TEN` are the frozen list's first entry and the other
nine, split without change.

## Results

Read from each session's `summary.json` and its proxy ledger under
`.runtime/curator-shadow/pilot-first/` and `pilot-rest/`. Ledger totals equal the
summaries' costs; every proxy closed settled with nothing pending. Both runs recorded
the brief's hash `c5ca0ce7…`, and their `windows_sha256` are `b5fd5c53…` and
`c4006a23…` as frozen. The two invocations had run caps of \$20 and \$19.88.

| Window (`sd1a7`) | Requests | Charged | Wall clock | Largest reservation | Frames viewed | Version | Facts after | Bytes after |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| actor 001, 1–20 | 7 | \$0.11 | 80 s | \$1.15 | 4 | v7 | 199 | 105,446 |
| actor 001, 21–40 | 8 | \$0.20 | 92 s | \$1.12 | 8 | v8 | 214 | 115,654 |
| actor 001, 41–60 | 20 | \$0.57 | 153 s | \$1.31 | 15 | v9 | 225 | 123,202 |
| actor 001, 61–80 | 10 | \$0.15 | 64 s | \$1.23 | 6 | v10 | 229 | 125,932 |
| actor 001, 81–100 | 13 | \$0.20 | 141 s | \$1.31 | 8 | v11 | 242 | 134,995 |
| actor 001, 101–120 | 10 | \$0.22 | 120 s | \$1.20 | 9 | v12 | 256 | 144,723 |
| actor 001, 121–140 | 12 | \$0.19 | 107 s | \$1.23 | 7 | v13 | 263 | 149,639 |
| actor 001, 141–156 | 8 | \$0.14 | 75 s | \$1.24 | 4 | v14 | 271 | 155,629 |
| actor 002, 1–20 | 8 | \$0.20 | 57 s | \$1.30 | 6 | v15 | 275 | 158,458 |
| actor 002, 21–40 | 16 | \$0.36 | 119 s | \$1.41 | 11 | v16 | 279 | 161,752 |
| **All** | **112** | **\$2.34** | **1,007 s** | | | | | |

- **Per session:** mean \$0.23, median \$0.20, largest \$0.57; mean 101 s, median 99 s,
  longest 153 s.
- **Play's pace** in the same windows, from the sealed traces' request starts: 8.4 s a
  decision for the first actor and 5.9 s for the second.
- **Facts per window:** 4 to 15 added, 84 in all. The lead read the first window's four
  facts before the other nine ran: a travel control, a recipe, rocks north of the fire
  and a piglet to the east, each with citations.
- **Fact counts and bytes** are read with `git show <version>:facts.jsonl`. The
  `store` subcommand of `tools.memory_screen_checks` listed only the last two versions
  of this repository; that reader is not used for these figures.

## What this means for the cut

- **Affordable.** At \$0.20 a session, sessions every 20 decisions cost less than the
  play they serve. The protocol's estimate, about \$12 for ten sessions, was five times
  the measured \$2.34.
- **Close to the limit on lag.** The free checks found the cut helps only if the
  curator trails play by less than about 24 decisions. Measured here, it trails by 12 to
  40, about 26 on average. Windows of 10 decisions would roughly halve the trail if a
  session's price falls with its window; the pilot did not measure that.
- **The briefing the cut relies on is large and growing.** At 0.327 tokens a byte the
  store was about 33,500 tokens after the gate and 52,900 after these windows. A
  briefing of the whole store would be most of the 60,000 tokens the cut aims to stay
  under, so it must be a selection or an index, not the whole store.

## Deviations

- **The frozen inputs were revised before spending** after the pre-spend review: the
  eighth window's end (158 was a request count; the actor has 156 operations), the
  session cap (\$6 would have let the proxy refuse before the host's writing-only
  phase), and the rules for sessions with no submission, cut sessions and continuing.
