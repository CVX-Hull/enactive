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
| Windows | `docs/acceptance/assets/2026-11-13-session-price-pilot-windows.json` | `8e6aff8f15755095196df4e01c87150aa9d9554a04385094dde9ca261413f597` |
| Arm and prices | as in the brief gate's record | |

- **Windows.** Ten consecutive windows of the last admission, `sd1a7`, which no gate
  session read: its first actor's steps 1 to 158 in windows of 20 (the eighth is 18
  steps, the actor's end), then its second actor's steps 1 to 40. A window counts the
  actor's steps, its operations, not provider requests.
- **The store.** A copy of the brief gate's repository at `v6`, made before any pilot
  session, at `.runtime/knowledge/shadow-454/pilot-from-gate/terra/397/`. The gate's own
  repository is left as its check read it. Each window continues the store the previous
  one left.
- **Limits.** 120 requests, 1,800 s wall clock, 32,768 output tokens, 16 context images
  in blocks of 8, as for the gate.
- **Session cap.** \$6. The gate's largest single reservation was \$2.22, so the cap holds
  two. A session that reaches its cap is re-run once at \$12; a second cap stops the
  pilot. A session that ends with no accepted submission for another reason is re-run
  once; a second such end stops the pilot.
- **Run cap.** \$20 for one invocation; a re-run invocation gets \$20 less the ledger
  total so far.
- **The first window runs alone** and is read before the other nine.

```bash
.venv/bin/python -m tools.curator_host.shadow --arm terra --lineage 397 \
  --windows-file WINDOW_ONE --cap-usd 20 --session-cap-usd 6 --max-output-tokens 32768 \
  --stop-on-reject --stop-on-abort \
  --knowledge-root .runtime/knowledge/shadow-454/pilot-from-gate/terra/397 \
  --out .runtime/curator-shadow/pilot-first
.venv/bin/python -m tools.curator_host.shadow --arm terra --lineage 397 \
  --windows-file WINDOWS_TWO_TO_TEN --cap-usd REMAINING --session-cap-usd 6 \
  --max-output-tokens 32768 --stop-on-reject --stop-on-abort \
  --knowledge-root .runtime/knowledge/shadow-454/pilot-from-gate/terra/397 \
  --out .runtime/curator-shadow/pilot-rest
```

`WINDOW_ONE` and `WINDOWS_TWO_TO_TEN` are the frozen list's first entry and the other
nine, split without change.

## Deviations

None so far.
