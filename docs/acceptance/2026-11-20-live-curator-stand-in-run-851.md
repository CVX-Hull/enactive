---
owner: lead
status: historical
kind: measurement
date: '2026-11-20'
scope: 'Zero-cost runs of the whole live curator arrangement: the real guardian, runner, snapshot reader, sandbox, curator host, proxy and gate beside a synthetic writer in the custodian''s place, with the loopback stand-in as the provider; no game, no provider, no spend; and the price of the paid live run proposed again from them (#851)'
---

# Zero-cost stand-in run of the live curator arrangement (#851)

## At a glance

- **Question.** Do the parts of the [live curator design](../design/live-curator-integration.md)
  work together before money is spent: does the guardian start and end the runner beside
  a writing custodian, are snapshots taken while the store grows, do windows get examined
  in order across a handoff, and does the finished session still seal?
- **Answer.** Yes, in two runs in a row on merged code, each with all seventeen required
  measures passing. In each, three windows were examined in admission order (actor `001`
  steps 1 to 31, its tail 32 to 46 after the handoff, then actor `002` steps 1 to 33),
  every session was accepted and every version confirmed, every snapshot held the read
  lock for at most 2.9 ms against a 2 s bound, the writer recorded no busy error, no read
  began after the closing marker, `sealed()` accepted the finished store with an empty
  log, and the guardian ended the runner at teardown.
- **One defect was found and fixed in its own leaf.** In two earlier runs the runner's
  final status read as caught up while 11 finished steps had never been examined. The
  runner now states the read its counts are as of and marks later steps unknown
  ([#856](https://github.com/CVX-Hull/enactive/pull/856)); the runs reported here
  require it.
- **What it does not show.** Anything that needs a player or a real provider: the
  player's pace beside sealed admissions, decisions and game time, curator dollars,
  the length and output of a real session, and whether the knowledge helps. The custodian,
  the package preflight, the credential and the provider are substituted. The
  custodian's wait for a read in flight at close was not exercised: no read was in flight
  in any run. The stand-in was changed so that no submission is rejected, so a rejected
  window was not exercised here either.
- **Owner decision needed.** The price of the paid live run, proposed again in the
  [price section](#the-price-of-the-paid-run-proposed-again): forecast about $3.50 to
  $3.90, planning ceiling $18.50, which is $0.50 above the corrected proposal's because
  the forecast now allows twelve sessions. Nothing is approved by this record.

No game, no model request, $0 spent. The stand-in's cost figures are nominal and are not
money. [Live curator design](../design/live-curator-integration.md) ·
[Price proposal](2026-11-20-live-curator-run-price-proposal-836.md) ·
[Corrections](2026-11-20-live-curator-run-price-correction-836.md)

## What was run

`tests/live_curator_stand_in_run.py`, at commit `ad59e84a` of its branch, which is merged
main `89951f37` (the closing marker, the reader and the runner) plus the script, from
its worktree with the main checkout's Python:

```
python -m tests.live_curator_stand_in_run --output .runtime/live-curator-stand-in-runs/2026-11-20-merged-runner-first-run
python -m tests.live_curator_stand_in_run --output .runtime/live-curator-stand-in-runs/2026-11-20-merged-runner-second-run
```

Both exited 0. The outputs are git-ignored, in the main checkout's
`.runtime/live-curator-stand-in-runs/`: each directory holds `report.json` (every
measure below), `summary.txt`, the run directory `run/stand-in-admission/`, the sampled
status file `status-samples.jsonl`, the writer's records and a copy of the knowledge
repository.

Four earlier runs are kept beside them: `trial-212642`, `2026-11-20-213027` and
`2026-11-20-213328`, made on the runner before its review fixes (`6bcd15fb`), and
`2026-11-20-final-runner-head-a`, made on the runner's final head before the script
required the status's new fields. All four passed the measures the script had at the
time. All three runs on `6bcd15fb` have the status defect; it was measured in the two
dated ones, since the trial's script did not yet compare the status against the sealed
store.

Settings: two actors of 45 input steps each, one step a second, with a handoff between
them; the runner's defaults for the trigger (20 steps), the ceiling (40), the poll (15 s)
and the look at the tags while a session runs (5 s). The runner's knowledge repository was
new for each run. The runner's configuration: arm `terra`, `cap_usd` 1.00,
`session_cap_usd` 0.25, and for the host at most 10 requests, 4,096 output tokens and
120 s a session; a paid run's caps and host bounds differ. Each run took about 91 s with
the runner and 90 s more for the writer alone.

**Real.** `run_supervised` with its `supervise` loop, teardown and `watch-terminal.json`;
its `--curator-runner` path (the read lock created before the custodian, the runner
started after it outside supervision, its termination); the gateway, the viewer and the
keep-awake helper as the guardian starts them, since none needs the game (nothing
listens on the custodian's port, so the gateway's path to the custodian is not
exercised); the runner
process `tools.curator_host.live_runner` with `stage`, the sandbox, the Node curator host,
the proxy and the gate; the custodian's own close-out, `close_store`, and a real
`SessionStore`.

**Substituted.**

| Part | Substitute | Why |
| --- | --- | --- |
| The custodian's process | The guardian's `popen` is wrapped so the custodian's argv starts the script's `writer`. It writes `started.json`, `ready.json` and a `campaign-receipt/7` receipt as the custodian does, appends finished operations through `tests.curator_trace`'s writer (frames, host log, a handoff that seals the actor), starts and reaps a stand-in native process so the receipt's native fields are true of a real process, and closes the store through `close_store` | No game and no player host |
| Package preflight | A fixed profile and a route naming a dummy credential variable | No frozen package, clean tree or game |
| The package's manifest | A synthetic `campaign-run/10` manifest with no lineage or admission label and a field naming it a substitute | The guardian checks that the manifest is unchanged |
| Two fields of the receipt | The writer's receipt asserts that the deciding hosts are quiescent and input authority is revoked; the guardian's terminal coverage reads them | There are no hosts and no input authority here |
| The route credential | A dummy value in that variable | No provider |
| The provider | `tests/curator_stand_in.py`'s `StandIn` on loopback. In this process its submission gets a fact identity from the first frame it cites, and adds the `control` type only while the base version lacks it | As it is, the stand-in submits fact `f1` and type `control` each time; the gate rejects the second window as a duplicate, and two consecutive rejections stop the runner by its own rule |

Before running, the script checks that the runner's configuration names only the loopback
stand-in, that the runner would present only the fixed loopback key, and that the
runner's configuration reader refuses an upstream that is neither loopback nor the
provider's own origin (probed with one such address); it removes the provider key's
variable from its own environment.

## The measures

Each figure is from the files a live run writes, named in the last column; the two runs
are given as first run / second run where they differ.

| Measure | Result | Source |
| --- | --- | --- |
| Guardian's verdict | `custodian_terminal`, terminal coverage verified, cleanup verified, manifest unchanged | `watch-terminal.json` |
| Windows examined, in order | `001` 1–31, `001` 32–46 (the tail after the handoff; 14 frames, the handoff has none), `002` 1–33; all accepted; first and last operation of each equal the sealed trace's step numbering | `curator-runner/examined.jsonl`, the sealed store |
| Session time (runner's start row to end row) | 1.2, 1.0, 1.5 s / 1.2, 1.6, 1.6 s | `examined.jsonl` |
| Status at each session's start → end: lag, backlog, covered prefix end (ordinal) | `001` 1–31: 31, 31, none → 0, 0, 31. `001` 32–46: 17, 17, 31 → 2, 2, 46. `002` 1–33: 33, 33, 46 → 0, 0, 79 | `curator-runner/status.json`, sampled every 50 ms |
| Distance from the latest stamp at each session's start → end (descriptive only) | unknown → 0; 17 → 2; 33 → 0 | `status.json` samples |
| Lag over time (position, lag at each change) | 1, 1; 16, 16; 31, 31; 31, 0; 48, 17; 48, 2; 64, 18; 79, 33; 79, 0 (both runs) | `status.json` samples |
| Left unexamined at the end | Runner's final status: lag 0, backlog 0, nothing unexamined, as of operation 79, steps after it unknown. Against the sealed store: `002` 34–45, 12 steps, lag 12 of 91 operations | `status.json`, the sealed store |
| Snapshots | 6 polls, 6 reads, none failed, over bound or refused; 3.9 reads a minute, from the gaps between poll starts (the two reports' own figure, 4.65 and 4.62, counted six reads over five gaps; the script is corrected); 5 of 6 reads saw more operations than the one before | `curator-runner/polls.jsonl` |
| Snapshot hold (bound 2 s) | median 1.9 / 0.8 ms, max 2.8 / 2.9 ms | `polls.jsonl` |
| Read transaction (bound 1.5 s) | median 1.1 / 0.5 ms, max 1.7 / 1.7 ms | `polls.jsonl` |
| Staging | median 37 / 26 ms, max 49 / 55 ms | `polls.jsonl` |
| Time to publication (first sight of the version, after the window's newest frame and oldest frame) | v1: 1.3–31.3 / 1.3–31.3 s; v2: 3.4–16.4 / 3.9–16.9 s; v3: 2.1–34.1 / 2.6–34.6 s | `curator-runner/versions.jsonl`, frame `received_wall` in the sealed store |
| Writer busy errors | 0 with the runner, 0 alone | the writer's record |
| Writer pace with the runner / alone | 60.0 / 60.0 operations a minute in both runs (set at one a second) | the writer's record |
| Writer step time with the runner / alone | median 5.1 / 5.2 ms, max 14.7 / 11.2 ms (first run); median 4.7 / 5.5 ms, max 10.1 / 11.1 ms (second run) | the writer's record |
| Steps that overlapped a snapshot | 0 / 1, the one taking 0.9 ms | the writer's record against `polls.jsonl` |
| Closing marker | written; no read began after it; the last read ended 12.6 / 12.1 s before it; the close waited 1.4 / 1.2 ms (no read held the lock) | `store-closing.json`, `polls.jsonl`, the writer's record |
| Finished store | `sealed()` accepts it; log empty; 91 operations (46 and 45) | `session.sqlite3` |
| Runner at teardown | terminated by the guardian while it slept between polls: state `ended`, reason `interrupted`, exit 130, process and group absent, no further signal needed, its snapshots directory removed; the guardian's whole teardown took 0.20 / 0.15 s | `watch-terminal.json`, `status.json` |
| Curator cost as the proxy counted it (nominal) | $0.0036 a session (3 requests at the stand-in's $0.0012), $0.0108 a run, $0.000137 an examined step | session `summary.json`, `proxy-ledger.jsonl` |
| Upstream | 9 requests, all to the stand-in's route; the proxies forwarded 9 | the stand-in's request list, `summary.json` |
| New facts per window | 1, 1, 1 (`f-1`, `f-32`, `f-46`) | the knowledge repository's versions |

**What one comparison shows.** With the writer at one step a second, its pace and step
times with the runner and alone are the same within a few milliseconds, and at most one
step in a run overlapped a snapshot. That is no more than the design says one run can
show: it does not show that the runner cannot slow play, and the writer is not the
custodian's loop.

### Not measured

| Measure the design lists | Why not here |
| --- | --- |
| Player pace in operations and decisions a minute beside sealed admissions of the same player | No player; the writer appends at a set pace |
| Decisions and game time | No player and no game |
| Curator dollars beside the player's | The stand-in's cost is nominal, and there is no player spend |
| Length, requests and output of a real curator session | The stand-in answers at once with a scripted three-request session |
| Facts later superseded or retired | No grooming runs, and the stand-in never revises a fact |
| Whether the knowledge helps the player | The design does not measure it |
| The custodian's wait for a read in flight at close | No read was in flight at close in any run; the reader's own tests cover it |
| A rejected or unconfirmed window | The stand-in was changed so that every submission is accepted; the runner's own tests cover it |
| Rate limits shared with the campaign | No provider account is used |

## Failures and anomalies

No required measure failed in any run. Five things were found.

- **The runner's final status read as caught up when it was not.** In the two runs on the
  runner before its review fixes, the status ended with lag 0 and nothing unexamined while
  11 steps actor `002` finished after the last poll were never examined. The runner
  cannot read after the custodian ends, so it cannot count them. It was fixed in the
  runner's leaf: the status and the coverage in its rows now carry `as_of`, the position
  and time of the last read, and `after_last_read`, always `unknown`. The script
  requires both, and the two runs reported here show them.
- **The guardian starts the runner without `--runtime-root`**, so the runner's runtime
  root is the code checkout's own `.runtime/`. The knowledge repository must be inside
  it, so in these runs it was made under the worktree's `.runtime/knowledge/` and copied
  into the output directory afterwards. A paid run started from a worktree would look for
  the credential map in the worktree's `.runtime/` and, finding none, the runner would
  exit at start, which the guardian records and play ignores. From the main checkout the
  default is right. Not changed.
- **The viewer writes its evaluations under the code checkout's
  `.runtime/evaluations/<session>`**, outside the output directory, because the guardian
  passes it that root. Nothing browsed the viewer in these runs. Not changed.
- **The runner never saw the closing marker.** In every run the writer closed about 12 s
  after the last poll, inside the 15 s interval, and the guardian's termination ended the
  runner first. The other endings, a read refused as closing and the runner seeing the
  custodian's receipt, are covered by the runner's tests.
- **In the trial run the closed store left an empty `-wal` and a `-shm` file**;
  `sealed()` accepted it, since the log was empty. No later run left either. The cause
  was not found. A read-only connection opened after a clean close leaves exactly these
  two files, and the viewer's evaluator opens the store read-only; that was not shown to
  be what happened.

## What the run means for a paid run

- **Window size follows the poll, not only the trigger.** A window starts at the first
  poll at which at least 20 steps wait. At 15 steps a poll, that was the second poll after
  the cursor, so the windows held 31 and 33 steps, and the handoff tail 15. Three
  sessions examined 79 steps. At a different pace the window is the smallest number of
  polls' growth that reaches 20, up to 40.
- **Each handoff adds a session.** An actor's tail is taken as its own window however
  short.
- **One snapshot a poll, 3.9 a minute** at the default 15 s poll, each holding the read
  lock for milliseconds over a store of up to 79 operations. A real admission's store is
  larger and its frames are real; staging time at that size is not measured.
- **The end of an admission leaves work for the session after it.** Here the last 12 of
  91 operations, those finished after the last poll, were not examined live. The last
  actor does not hand off, so its remainder is taken live only as a full window.
- **The proxy reserves far more than it charges.** In every run it reserved from about
  $0.07 to $0.13 for a request, rising with the prompt within a session, at the `terra`
  arm's frozen price with `max_output_tokens` 4096, against a nominal charge of $0.0012. A paid run's reservations depend on its own host
  settings and are not measured here.
- **The runner adds nothing measurable to teardown** in this arrangement.

## The price of the paid run, proposed again

The owner decided on 20 November 2026 that the price is proposed again once the reader,
the closing marker and the runner are merged and this run has passed
([decision log](../decisions/owner-decisions.md)). They are, and it has. The figures are
those of the [corrected proposal](2026-11-20-live-curator-run-price-correction-836.md),
changed only where the build changed them: the count of sessions, and the run cap that
follows from it.

| Part | Forecast | Planning limit, and what enforces it |
| --- | --- | --- |
| Play, one admission of about 200 decisions | $1.49 | **$3.00**: the package's `spend_limit_usd` |
| Curator, ten to twelve sessions | $2.00 to $2.40 at the pilot's median of $0.20 | **$14.50** for the run (`cap_usd`), **$8.00** for a session (`session_cap_usd`), in the runner's configuration |
| Not allocated | | $1.00 |
| **Total** | **about $3.50 to $3.90** | **$18.50** |

**The count of sessions.** About 200 operations in windows of 20 to 22 steps is nine or
ten windows, and each handoff adds one tail session. Ten to twelve assumes at most two
handoffs; the last actor's remainder after the runner's last read is not examined live.

**The run cap.** The correction sized it so that the last session still has its $8.00
after every earlier one cost the pilot's largest, $0.57: for ten sessions, $13.13. For
twelve it is $8.00 + 11 × $0.57 = $14.27, so the cap rises from $14.00 to $14.50 and the
ceiling from $18.00 to $18.50. The forecast spend does not rise with it: the cap is
room to reserve. With more than two handoffs, or sessions dearer than the pilot's
largest, a late session starts with less than $8.00 and may be refused a reservation,
which stops the runner and not play.

**What the build changed.**

- **The count of sessions is a forecast, not a limit.** The proposal said the runner
  makes at most twelve sessions. The runner as built has no limit on the number of
  sessions: it is bounded by its run cap, by a refused reservation, and by its failure
  rules. The forecast rises from ten sessions to ten to twelve because each handoff
  adds a tail session, and the run cap rises with it, as above.
- **Windows can be larger than 20 steps.** At the ledger's median pace of 7.69 decisions
  a minute a 15 s poll adds about two steps, so a window is 20 to 22 steps if operations
  and decisions stay close to one to one. A faster player gives larger windows, up to 40,
  and fewer sessions, each reading more.
- **A request in flight when the runner is killed is not counted toward its cap.** It is
  one request, bounded by its reservation. It falls within the $1.00 not allocated only
  while one reservation is under $1.00, which depends on the paid run's
  `max_output_tokens`; that setting is shown with the runner's configuration before the
  run.
- **The last steps of the admission are not examined live.** The run's figures for lag
  and coverage end at the runner's last read, and its status says so.

**What is unchanged.** $18.50, like the $18.00 before it, is a planning ceiling made of limits the software enforces
on what the provider reports; it is not a hard cap. A hard cap needs a provider key whose
credit limit the owner sets for the run. The run is one admission, with no delivery
inside it, and is not repeated on its own result. The reading of each result is the
proposal's table as corrected.

**What a paid run still needs before it starts.** A frozen package for the admission and
the runner's configuration, shown to the owner with their routes and bounds; the run
started from the main checkout; and source work stopped while it is live. Reading the
result through the lag simulation needs the schedule replay
([#846](https://github.com/CVX-Hull/enactive/issues/846)), which costs nothing and is not
needed to make the run.

## Limits

- Two runs of one synthetic arrangement on one machine. The writer imitates the
  custodian's writes and the host's log; it is not the custodian's loop or the host.
- The stand-in's sessions take about a second and three requests. A real session took a
  median of 99 s in the pilot, during which play goes on and the tags are watched; that
  timing is not exercised here.
- Some of the script's required measures are weaker than their names, though none
  passed emptily in these runs: the check on the final status requires that it names a
  read, not that it names the last one (it did: operation 79); the check on reads after
  the marker counts successful reads only; and the check on the runner's ending does not
  accept the ending in which the runner sees the receipt. That the writer was never
  delayed rests on its busy count and on one overlapping step, which are reported and
  not required.
- The forecast is the pilot's and the ledger's figures read again. No curator session
  beside live play has been priced.
