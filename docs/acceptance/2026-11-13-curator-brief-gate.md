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
  clean-context reviewer who answers the question frozen below. Otherwise the gate
  fails and the work stops.
- **Stop.** \$45 for the whole gate, taken from the curator proxy's ledger.

## Frozen inputs

The code and the brief are `main` at `9d30790`. The patterns and this page are frozen
on the branch `memory-screen-gates`, in the commit that last changed the patterns file
before the first session.

| Input | Value | sha256 |
| --- | --- | --- |
| Protocol | `docs/design/memory-screen-protocol.md` | `9aae71f86f2e4d5ad10b64cca3e018206a57a34472ebc7a0ea7432f26568de40` |
| Curator brief | `tools/curator_host/prompt.md` | `c5ca0ce7cc1c191360669b908e67e0d0c80471bf906ec77acbed6ef894360a6b` |
| Check patterns | `docs/acceptance/assets/2026-11-13-curator-brief-gate-patterns.json` | `c04751ad3df45f22fb97eeb6c37346f8938d0af28c7f268dd0b042564589a458` |
| Arm | `terra` in `data/curator/shadow-arms.json`: `openai/gpt-6.1-terra`, provider pinned, effort medium | `4c67015c6265dff372dca2307e98922823d2b18045765503618af5b7525c27d0` |
| Prices | `data/curator/openrouter-prices-2026-11-08.json` | `36edf95cee93d8ebe6b74efbc498386f3f5ba3bb8c8f7e684e1cca1d45bbf197` |

Each run's `summary.json` records `host.prompt_sha256`; it must equal the brief's hash
above.

### The check

The patterns are matched case-insensitively against a fact's `subject` and `place`,
never against its `statement`. Only current facts of kind `place_with_goods` count, and
a fact that matches two labels counts for neither.

| Lost fact | `subject` | `place` | The reviewer's question |
| --- | --- | --- | --- |
| A tank of clean water on the roof | `tank\|clean water` | `roof` | Does the fact say there is a water tank on the shelter's roof? |
| Ration boxes in a cupboard | `ration\|cardboard box` | `cupboard\|cabinet` | Does the fact say the boxes of rations are in the cupboard? The three rations in a locker do not count |
| A fishing rod on the floor of the shelter | `fishing rod` | `shelter\|floor\|ground` | Does the fact say a fishing rod lies inside the shelter? A rod at the lake, or carried, does not count |
| Batteries in a locker | `batter` | `locker` | Does the fact say a battery is in a locker of the shelter? |

A label passes when at least one matching fact gets a yes from a clean-context reviewer
who is shown the fact and its cited frames and not the result wanted.

The first frozen version of the patterns was changed before any session ran, after the
pre-spend review showed honest facts it would miss (a subject such as "clean water" or
"small cardboard boxes") and one pattern that only added false matches (`\brod\b`).

### Sessions and money

- **Sessions.** One per admission, `sd1a1` to `sd1a6`, in order, on one fresh knowledge
  repository. 120 requests, 1,800 s wall clock, 16 context images in blocks of 8, and
  32,768 output tokens, twice the runner's default, because a submission is written in
  one call and this brief asks for more facts.
- **Session cap.** \$12. At the current price bounds one worst-case request reserves
  about \$1.6 to \$1.8, so the cap holds about six. The host tells the curator to start
  writing at \$5.10, refuses reading at \$8.16, and the proxy refuses a request from
  about \$10.3 spent. The dearest recorded session cost \$7.08 under no session cap.
- **A session that reaches its cap** is re-run once at \$24. A second cap stops the gate
  as failed.
- **A session that ends with no accepted submission for another reason** (the request
  limit, the wall clock, a provider error, an output-limit stop, or a rejected
  submission) is re-run once with the same inputs. A second such end stops the gate as
  failed. Every re-run is reported.
- **Run cap.** `--cap-usd` holds for one invocation, so each invocation after the first
  is given \$45 less what has been charged so far. The authority for that figure is the
  sum of `charged` over every `proxy-ledger.jsonl` under the gate's output directories,
  plus any `pending_reserved_usd` in a `proxy-close.json`.
- **Order.** `sd1a1` runs alone and is read end to end before the rest. Then `sd1a2` to
  `sd1a6` run in one invocation on the same repository.
- **The check runs once**, on the version published after `sd1a6`, before anything else
  touches the repository.

Commands, from the main checkout. The patterns file is read from this branch's
worktree:

```bash
.venv/bin/python -m tools.curator_host.shadow --arm terra --lineage 397 --sessions sd1a1 \
  --cap-usd 45 --session-cap-usd 12 --max-output-tokens 32768 --stop-on-reject --stop-on-abort \
  --out .runtime/curator-shadow/brief-gate-first
.venv/bin/python -m tools.curator_host.shadow --arm terra --lineage 397 \
  --sessions sd1a2 sd1a3 sd1a4 sd1a5 sd1a6 --cap-usd REMAINING --session-cap-usd 12 \
  --max-output-tokens 32768 --stop-on-reject --stop-on-abort \
  --knowledge-root .runtime/knowledge/shadow-454/brief-gate-first/terra/397 \
  --out .runtime/curator-shadow/brief-gate-rest
.venv/bin/python -m tools.memory_screen_checks brief-gate \
  .runtime/knowledge/shadow-454/brief-gate-first/terra/397/cdda \
  --patterns .runtime/worktrees/memory-gates/docs/acceptance/assets/2026-11-13-curator-brief-gate-patterns.json
```

A re-run is the second command with the one session named, a new `--out`, the same
`--knowledge-root`, and `--double-session-cap` when the cause was the cap.

## Deviations

None so far.
