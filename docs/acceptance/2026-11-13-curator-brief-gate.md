---
owner: lead
status: historical
kind: run
date: '2026-11-13'
scope: 'The brief gate of the memory screen (#460, protocol of 13 November 2026): the curator, with a brief for places and goods and the fact format curator-fact/2, run over the seven-day lineage''s admissions sd1a1 to sd1a6 on the actor''s model, and its store checked against frozen patterns for the four lost facts. Curator sessions only; no game launch'
---

# Curator brief gate on the seven-day lineage (#460)

## At a glance

- **Result.** Not run yet. This page holds the inputs frozen before spending.
- **Pass rule.** At least three of the four lost facts are stored as `place_with_goods`
  facts whose `subject` and `place` match the frozen patterns, each confirmed by a
  clean-context reviewer who reads it. Otherwise the gate fails and the work stops.
- **Stop.** \$45 for the whole gate, taken from the curator proxy's ledger.

## Frozen inputs

Frozen at commit `9d30790` of `main`, before any session ran.

| Input | Value | sha256 |
| --- | --- | --- |
| Protocol | `docs/design/memory-screen-protocol.md` | `9aae71f86f2e4d5ad10b64cca3e018206a57a34472ebc7a0ea7432f26568de40` |
| Curator brief | `tools/curator_host/prompt.md` | `c5ca0ce7cc1c191360669b908e67e0d0c80471bf906ec77acbed6ef894360a6b` |
| Check patterns | `docs/acceptance/assets/2026-11-13-curator-brief-gate-patterns.json` | `cb84395d317f3cb3048cecb512a35bcfb5f92f95865bbc3f59ca3222b4053e1d` |
| Arm | `terra` in `data/curator/shadow-arms.json`: `openai/gpt-6.1-terra`, provider pinned, effort medium | `4c67015c6265dff372dca2307e98922823d2b18045765503618af5b7525c27d0` |
| Prices | `data/curator/openrouter-prices-2026-11-08.json` | `36edf95cee93d8ebe6b74efbc498386f3f5ba3bb8c8f7e684e1cca1d45bbf197` |

The patterns, matched case-insensitively against a fact's `subject` and `place` and
never against its `statement`:

| Lost fact | `subject` | `place` |
| --- | --- | --- |
| A tank of clean water on the roof | `tank` | `roof` |
| Ration boxes in a cupboard | `ration` | `cupboard\|cabinet` |
| A fishing rod on the floor of the shelter | `fishing rod\|\brod\b` | `shelter\|floor` |
| Batteries in a locker | `batter` | `locker` |

- **Sessions.** One per admission, `sd1a1` to `sd1a6`, in order, on one fresh knowledge
  repository. Runner defaults otherwise: 120 requests, 16,384 output tokens, 1,800 s
  wall clock, 16 context images in blocks of 8.
- **Session cap.** \$9. The largest single reservation in the recorded shadow run was
  \$0.93, so the cap holds more than two worst-case requests; the dearest recorded
  session cost \$7.08. A session that reaches its cap is re-run once at \$18; a second
  cap stops the gate.
- **Run cap.** `--cap-usd` holds for one invocation, so each invocation after the first
  is given \$45 less the proxy ledger's total so far.
- **Order.** `sd1a1` runs alone and is read end to end before the rest. Then `sd1a2` to
  `sd1a6` run in one invocation on the same repository.
- **Stops.** `--stop-on-reject` and `--stop-on-abort`: a rejected submission or an
  aborted session stops the run, because a later session cannot recover that
  admission's facts.
- **The check runs once**, on the version published after `sd1a6`, before anything else
  touches the repository.

Commands, from the main checkout:

```bash
.venv/bin/python -m tools.curator_host.shadow --arm terra --lineage 397 --sessions sd1a1 \
  --cap-usd 45 --session-cap-usd 9 --stop-on-reject --stop-on-abort \
  --out .runtime/curator-shadow/brief-gate-first
.venv/bin/python -m tools.curator_host.shadow --arm terra --lineage 397 \
  --sessions sd1a2 sd1a3 sd1a4 sd1a5 sd1a6 --cap-usd REMAINING --session-cap-usd 9 \
  --stop-on-reject --stop-on-abort \
  --knowledge-root .runtime/knowledge/shadow-454/brief-gate-first/terra/397 \
  --out .runtime/curator-shadow/brief-gate-rest
.venv/bin/python -m tools.memory_screen_checks brief-gate \
  .runtime/knowledge/shadow-454/brief-gate-first/terra/397/cdda \
  --patterns docs/acceptance/assets/2026-11-13-curator-brief-gate-patterns.json
```

## Deviations

None so far.
