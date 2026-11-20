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
[live integration design](../design/live-curator-integration.md) describes, is forecast
at about **$3.50**: about $1.50 of play and about $2.00 for ten curator sessions. The
proposed ceiling is **$10.00**. It is a planning ceiling made of two limits the software
enforces, not a hard cap: the only hard cap is the credit limit on the provider key.
Nothing here is approved, and the run cannot be made until the live trace reader and the
runner exist.

The figures are existing measurements read again, not new ones. The pilot's sessions ran
over sealed windows, one after another; a session beside live play has never been priced,
and that is what the run would measure.

No game, no model request, $0 spent.
[Session price pilot](2026-11-13-session-price-pilot.md) · [Free checks](2026-11-13-memory-screen-free-checks.md) · [Live integration design](../design/live-curator-integration.md)

## The inputs, and how each was read

| Input | Figure | Source |
| --- | --- | --- |
| Cost of a curator session | median $0.20, from $0.11 to $0.57 | the price pilot's ten sessions; nine over 20 operations and one over 16 |
| Time of that session | median 99 s over all ten, 107 s over the nine full windows; from 57 to 153 s | the price pilot |
| Lag in the pilot | inferred from the sealed player's pace, not observed beside play: 8 to 20 decisions behind when a session ended, about 23 averaged over a cycle | the price pilot |
| Size of a recent run | median 199 decisions, 1,532.5 s | the run ledger, below |
| Cost of that play | median $1.49; the largest, $5.37 | the run ledger |
| Player pace | median 7.69 decisions a minute | the run ledger |

**The ledger figures.** They come from the last 60 rows, in file order, of
`data/evaluation/runs.jsonl` as it stands at this change, joined on `run` with
`data/evaluation/run-metrics.jsonl`, keeping the 46 rows that have a positive
`wall_seconds` and at least 50 `decisions`. Ordering the ledger by its `ended` field
selects a slightly different set and changes the medians. No tracked command produces
them; the join was a short read-only script.

**A forecast, not a measurement.** At 7.69 decisions a minute, 20 decisions take about
156 seconds. The median pilot session took 99 seconds, so a session over one window
would end before the next window fills; the slowest took 153 seconds, which is on the
edge. A window counts an actor's computer operations and the ledger counts decisions,
and the two are not the same unit.

## The lag simulation, run again

The simulation removes covered turns from recorded requests and reports the prompt sizes
that result. With `--coverage sessions` the number given is the **length of a session in
player request turns**, and coverage then trails play by one to two sessions. It is not
a lag the curator is held to.

```
.venv/bin/python -m tools.memory_screen_checks cut .runtime/evidence/397-seven-day/computer-sessions --lags 10 20 23 47 --coverage sessions
```

Run on 20 November 2026 over the sealed seven-day lineage, sessions `sd1a1` to `sd1a7`:
seven runs, 14 actors, 1,978 requests.

| Session length in turns | Median prompt | 95th percentile | Requests held back | Image blocks dropped | Share under 40,000 tokens | Cache writes against recorded |
| --- | --- | --- | --- | --- | --- | --- |
| 10 | 29,200 | 40,600 | 0 | 0 | 0.93 | 0.13 |
| 20 | 30,342 | 40,600 | 0 | 0 | 0.921 | 0.151 |
| 23 | 36,042 | 46,440 | 68 | 68 | 0.69 | 0.245 |
| 47 | 40,884 | 55,126 | 61 | 76 | 0.472 | 0.198 |

The rows for 10, 20 and 47 match the free checks' table. The row for 23 is new here. The
rows are from the simulation's model, not measured, and the model has no briefing in it.
A session length of 20 holds back no request and drops no image block; 23 already does.
The lengths differ in prompt size and cache writes even where neither does.

## The run proposed

- **One admission** of the current player, of about 200 decisions, in one world, with
  the curator runner following it as the design says: one actor's range at a time, 20
  finished steps to start a session, a ceiling of 40, one session at a time. The runner
  ends with the custodian; what it has not examined is recorded.
- **No delivery inside the admission.** The player receives the package's frozen
  knowledge, as today.
- **It measures** what the design lists: lag at the start and end of each session, time
  from a step to the version covering it, backlog, the curator's dollars beside the
  player's, how long each snapshot's read holds, and the player's pace beside named
  sealed admissions.

## Price and its bounds

| Part | Forecast | Planning limit, and what enforces it |
| --- | --- | --- |
| Play, one admission | $1.49 | **$3.00**: the package's `spend_limit_usd`. The player host checks the reported total, plus an allowance for a pending recall, before each request |
| Curator, ten sessions | $2.00 at the pilot's median | **$6.00**: the runner's run cap, with a cap for each session. The curator proxy reserves an estimated worst case before it forwards a request |
| Not allocated | | $1.00 |
| **Total** | **about $3.50** | **$10.00** |

Ten sessions at the pilot's largest displayed cost, $0.57, would be $5.70, under the
curator's cap.

**Why $10.00 is not a hard cap.** Each limit counts what the provider reports.

- The player's reported total can pass its limit by the charges of the final in-flight
  player and recall requests. An attempt that returns no usable cost is recorded as
  unpriced and may still be billed; the host can retry after one, and the driver gives a
  successor actor the limit less the *reported* spend only.
- The curator's proxy reserves an estimate. It revokes itself after a charge exceeds
  the reservation, which is after that charge exists.
- The $1.00 not allocated is a margin for those cases. It is not shown to cover them.

A hard $10.00 needs a billing cap that belongs to this run: a provider key whose credit
limit the owner sets to $10.00 for it. The owner manages that key and its limit; the
code cannot read it. The request to the owner states which of the two is on offer: the
planning ceiling above under the existing key, or a key limited for the run.

**To be shown before the owner is asked:** the frozen routes of the player and the
curator, the player's and the recall's in-flight bounds from the package, and the
curator's cap for one session.

**Stop rules.**

- The player host stops the admission at the package's limit, on a successful response
  with no usable cost, and on its time and mechanical ceilings, as now.
- The runner stops for the admission when its run cap is reached; when the proxy refuses
  the next reservation, even with counted spend under the cap; when the proxy is
  revoked, breached or unsettled; when cleanup of a session is not confirmed; when a
  charge is unknown; after two consecutive failed sessions; or after three consecutive
  failed snapshots. Play continues without it.
- The runner makes at most twelve sessions, and ends when the custodian ends.
- The run is one admission and is not repeated on its own result.

## What each result would change

The run does not by itself answer whether the cut is affordable. Its lag is in the
curator's operations, and the simulation is in player request turns. So the first step
after a run is offline and free: map the covered prefix, as the design defines it, to
the request turn at which each part would have applied, and **replay that observed
schedule through the simulation**. The simulation accepts only a steady or a
session-shaped coverage today, so this needs a small addition to it, which is not yet a
registered leaf. The replay keeps the context design's minimum of ten turns for a cut
and states whether it includes a briefing.

The rows are read in order, and the first that applies decides. A stop or an
inconclusive result comes before a favourable replay.

| Result | Reading | Next |
| --- | --- | --- |
| The run stops early, or the covered prefix cannot be established | Partial figures are reported as partial | The owner is asked before another run |
| Snapshots fail or pass their time bound | The read is not safe beside the custodian as designed | The design falls back to the writer sealing each window, and the run is repeated only after that |
| The player's pace is far from the named sealed admissions' | A reason to look, not a finding: one admission cannot show cause | The snapshot timings and the host's log are read before anything is concluded |
| No version is published | Nothing can be said about lag | The sessions are read before anything else is tried |
| The backlog grows across the admission | A session cannot keep up with play at this window | Live curation at this price is not workable; curation stays between admissions |
| Cost and lag disagree: close behind and far over the forecast, or cheap and far behind | The window and the model are wrong for each other | The owner is shown both figures before another run |
| The replay holds back requests | Curation follows play, too far behind for the cut at this window | A smaller window or a faster model, in a second priced run, before any work on the cut |
| The replay holds back no request and drops image blocks | The cut would keep its token target and lose images | The image policy is looked at before the cut is proposed |
| The replay holds back no request and drops no image block | Curation is close enough for the cut to free what the simulation says | Delivery inside an admission becomes worth building, and the cut can be put to the owner with these figures |

The cutoff for "far from" is fixed with the named admissions before the run. None of
these says whether the knowledge helps the player.

## What must exist first

- [The live trace reader](https://github.com/CVX-Hull/enactive/issues/837), with its
  offline test against a writer that holds the store.
- The curator runner, which is not yet a registered leaf.
- The addition to the lag simulation that replays a recorded schedule.
- The frozen routes and bounds listed above, and the choice between the planning
  ceiling and a key limited for the run.
- The owner's approval of the design, this price and the envelope
  ([operator permissions](../operator-permissions.md)). No envelope is open.

## Limits

- Every figure is from sealed play and sessions run one after another. None is from a
  curator beside live play, and the pilot's lag was inferred from pace.
- The pilot's sessions used one model at one effort over one lineage's last admission.
- The simulation models prompt size only. It prices no curator dollars, has no
  briefing, and its unit is player request turns.
- The price assumes ten sessions. A slower player or a faster curator changes the count.
- One admission cannot show that the runner did not slow play.
