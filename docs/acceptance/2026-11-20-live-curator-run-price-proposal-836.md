---
owner: lead
status: historical
kind: measurement
date: '2026-11-20'
scope: 'A price proposal for one bounded live development run of the curator beside play, built at no spend from the session price pilot, the lag simulation and the run ledger (#836)'
---

# Price proposal for one live curator run (#836)

## At a glance

One admission of about 200 decisions, with the curator following play as the
[live integration design](../design/live-curator-integration.md) describes, should cost
about **$3.50**: about $1.50 of play and about $2.00 for ten curator sessions. The
proposed maximum is **$10.00**. Nothing here is approved, and the run cannot be made
until the live trace reader and the runner exist.

The figures are existing measurements read again, not a new one. The pilot's sessions
ran over sealed windows, one after another; a session beside live play has never been
priced, and that is what the run would measure.

No game, no model request, $0 spent.
[Session price pilot](2026-11-13-session-price-pilot.md) · [Free checks](2026-11-13-memory-screen-free-checks.md) · [Live integration design](../design/live-curator-integration.md)

## The inputs, and how each was read

| Input | Figure | Source |
| --- | --- | --- |
| Cost of a curator session over 20 steps | median $0.20, from $0.11 to $0.57 | the price pilot, ten sessions |
| Time of that session | median 99 s, from 57 to 153 s | the price pilot |
| Lag in the pilot | 8 to 20 decisions behind when a session ended; about 23 on average | the price pilot |
| Size of a recent run | median 199 decisions, 1,532 s | the run ledger, below |
| Cost of that play | median $1.49; the largest, $5.37 | the run ledger |
| Player pace | median 7.69 decisions a minute | the run ledger |

The ledger figures come from joining `data/evaluation/runs.jsonl` with
`data/evaluation/run-metrics.jsonl` on the run, over the 60 most recent ledger rows, and
keeping the 46 that have a wall time and at least 50 decisions. No tracked command
produces them; the join was a short read-only script.

At 7.69 decisions a minute, 20 decisions take about 156 seconds. The median pilot session
took 99 seconds, so a session over one window ends before the next window fills. The
slowest pilot session took 153 seconds, which is on the edge.

## What lag costs, from the simulation

The lag simulation removes covered turns from recorded requests and reports the prompt
sizes that result. It was run again on 20 November 2026 over the sealed seven-day
lineage, with coverage arriving in sessions:

```
.venv/bin/python -m tools.memory_screen_checks cut .runtime/evidence/397-seven-day/computer-sessions --lags 10 20 23 47 --coverage sessions
```

| Lag in decisions | Median prompt | 95th percentile | Requests held back | Image blocks dropped | Share under 40,000 tokens |
| --- | --- | --- | --- | --- | --- |
| 10 | 29,200 | 40,600 | 0 | 0 | 0.93 |
| 20 | 30,342 | 40,600 | 0 | 0 | 0.921 |
| 23 | 36,042 | 46,440 | 68 | 68 | 0.69 |
| 47 | 40,884 | 55,126 | 61 | 76 | 0.472 |

Seven runs, 14 actors, 1,978 requests. The rows are from the simulation's model, not
measured, and the model has no briefing in it. They agree with the free checks' tables.
The step between 20 and 23 is the point of the run: a curator that trails by 20 costs
the cut nothing, and one that trails by 23 already holds back requests.

## The run proposed

- **One admission** of the current player, of about 200 decisions, with the curator
  runner following it: windows of 20 finished steps, a ceiling of 40, one session at a
  time.
- **No delivery inside the admission.** The player receives the package's frozen
  knowledge, as today.
- **It measures** the lag at the start and end of each session and its tail, the time
  from a step to the version covering it, whether the backlog grows, the curator's
  dollars per session beside the player's, the player's pace, and how long each copy of
  the store takes.

## Price

| Part | Expected | Cap |
| --- | --- | --- |
| Play, one admission | $1.49 | $3.00, the package's dollar limit |
| Curator, ten sessions | $2.00 at the pilot's median | $6.00, above ten sessions at the pilot's largest, $5.70 |
| Margin for a charge in flight | | $1.00 |
| **Total** | **about $3.50** | **$10.00** |

**Stop rules.** The player host stops the admission at the package's limit, as it does
now. The runner stops for the admission when its own ledger reaches $6.00, or after two
consecutive failed sessions; play continues without it. The run is one admission and is
not repeated on its own result. A missing charge is recorded as unknown.

## What each result would change

| Result | Reading | Next |
| --- | --- | --- |
| Sessions keep within 20 decisions of play | Live curation is close enough for the cut to free what the simulation says | Delivery inside an admission becomes worth building, and the cut can be put to the owner with these figures |
| Lag settles between 20 and 47 | Curation follows play but too far behind for the cut at this window | Try a smaller window or a faster model in a second priced run, before any work on the cut |
| The backlog grows across the admission | A session cannot keep up with play at this window | Live curation at this price is not workable; curation stays between admissions |
| Copies fail or slow play | The reader is not safe beside the custodian | The design falls back to copies made by the writer, and the run is repeated only after that |
| The run stops early | Partial figures are reported as partial | The owner is asked before another run |

None of these says whether the knowledge helps the player.

## What must exist first

- [The live trace reader](https://github.com/CVX-Hull/enactive/issues/837), including the
  offline test that a copy can be taken while a writer holds the store.
- The curator runner, which is not yet a registered leaf.
- The owner's approval of the design, this price and the envelope
  ([operator permissions](../operator-permissions.md)). No envelope is open.

## Limits

- Every figure is from sealed play and sessions run one after another. None is from a
  curator beside live play.
- The pilot's sessions used one model at one effort over one lineage's last admission.
- The ledger's decisions and the curator's steps are not the same unit: a window counts
  an actor's computer operations. The run would report both.
- The simulation models prompt size only. It prices no curator dollars and has no
  briefing.
- The price assumes ten sessions. A slower player or a faster curator changes the count.
