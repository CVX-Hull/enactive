---
owner: lead
status: historical
kind: run
date: '2026-11-13'
scope: 'The session price pilot of the memory screen (#460, protocol of 13 November 2026): ten curator sessions, each over a sealed window of 20 steps of the seven-day lineage''s last admission, continuing the store the brief gate built, to price curator sessions during play. Curator sessions only; no game launch'
---

# Session price pilot on the seven-day lineage (#460)

## At a glance

- **Result.** Not run yet. This page holds the inputs frozen before spending.
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

## Deviations

- **The frozen inputs were revised before spending** after the pre-spend review: the
  eighth window's end (158 was a request count; the actor has 156 operations), the
  session cap (\$6 would have let the proxy refuse before the host's writing-only
  phase), and the rules for sessions with no submission, cut sessions and continuing.
