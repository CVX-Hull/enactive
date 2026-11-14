---
owner: lead
review_trigger: The selected outcome or the open outcomes change
status: active
---

# Work and evidence navigation

The [public Project](https://github.com/users/CVX-Hull/projects/2) and GitHub Issues own
live work: scope, status, owners, blockers and decisions. This page only routes to them
and to the evidence; it is not a second backlog. The [overview](overview.md) owns
capabilities and limits; [work items](workflows/work-items.md) own how work flows.

## Open outcomes

| Outcome | Where it is tracked | Governing design |
| --- | --- | --- |
| Player-owned campaigns without engineering gameplay assistance, the parent of the two outcomes below | [#136](https://github.com/CVX-Hull/enactive/issues/136) | [Mission ownership](operations/mission-ownership.md) |
| A fresh seven-day campaign without engineering gameplay assistance, the north star | [#145](https://github.com/CVX-Hull/enactive/issues/145) | [Development runs](development-runs.md) |
| Useful apparent responsiveness of the complete player; an aim that does not gate present work | [#164](https://github.com/CVX-Hull/enactive/issues/164) | [Development runs](development-runs.md) |
| The curated player: actor, curator, ontology and programs, in phases. Memory comes first: short tool results are built; the memory screen's gates have reported; the game-neutral curator with articles and grooming, and the judges, are built; [general memory](design/general-memory.md) and the [context design](design/player-context.md) are the working description: a game-neutral curator writing articles over facts, delivery chosen by a recall model, and judges as the standing measure | [#445](https://github.com/CVX-Hull/enactive/issues/445); the curator and memory phase in [#387](https://github.com/CVX-Hull/enactive/issues/387), the programs and monitor phase in [#177](https://github.com/CVX-Hull/enactive/issues/177), the practice instance phase in [#472](https://github.com/CVX-Hull/enactive/issues/472) | [ADR 009](decisions/009-curated-player.md) (proposed) and the [owner decision log](decisions/owner-decisions.md) |
| Evaluation follow-ons: stated intent on tool calls, judged measures of how play went beyond memory, reusable starts | [#384](https://github.com/CVX-Hull/enactive/issues/384), [#620](https://github.com/CVX-Hull/enactive/issues/620), [#388](https://github.com/CVX-Hull/enactive/issues/388) | [ADR008](decisions/008-evaluation-and-spectator.md), [general memory](design/general-memory.md#3-measurement) |
| Reusable expectation evaluation and read-only outcome monitoring | [#42](https://github.com/CVX-Hull/enactive/issues/42) | [Evaluation contract](contracts/evaluation.md) |
| Spectator views | [#143](https://github.com/CVX-Hull/enactive/issues/143) | [Observer operations](components/observer-operations.md) |
| CDDA-class portability | [#191](https://github.com/CVX-Hull/enactive/issues/191) | [ADR006](decisions/006-computer-control-boundary.md) |

Every other open issue is a sub-issue of one of the outcomes above. The Project's Ready
column is the queue of work that can start; it is not repeated here.

The [risk register](risks.md) and [controls](controls.md) own the current answers
about controls.

Current contracts govern the running system; a proposed ADR changes nothing until a
phase is adopted on study evidence.

## Evidence

- The [acceptance index](acceptance/index.md) lists every dated record, newest first,
  with its scope. Records own results and limits; later repairs never change an
  earlier outcome.
- The [development-run method](development-runs.md) owns the benchmark and metrics; the
  tracked run ledger (`data/evaluation/runs.jsonl`, `run-metrics.jsonl`) holds per-run
  quantities.
- Raw evidence lives in the sealed store under
  [evidence retention](operations/evidence-cleanup.md#evidence-retention-and-cleanup),
  and may be absent from a fresh checkout.

## Delivery path

[Development-first delivery](workflows/development.md#development-first-delivery) and
[risk-based assurance](workflows/review.md#risk-based-assurance) govern feedback, review
and acceptance. Cadence (#164), learning (#177), independent survival (#145) and
portability (#191) remain separate claims.
