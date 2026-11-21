---
owner: lead
status: historical
kind: measurement
date: '2026-11-20'
scope: 'Two zero-cost runs of the whole live curator arrangement: the real guardian, runner, snapshot reader, sandbox, curator host, proxy and gate beside a synthetic writer in the custodian''s place, with the loopback stand-in as the provider; no game, no provider, no spend (#851)'
---

# Zero-cost stand-in run of the live curator arrangement (#851)

## At a glance

- **Question.** Do the parts of the [live curator design](../design/live-curator-integration.md)
  work together before money is spent: does the guardian start and end the runner beside
  a writing custodian, are snapshots taken while the store grows, do windows get examined
  in order across a handoff, and does the finished session still seal?
- **Answer.** Yes, in two runs in a row, each with all sixteen required measures
  passing. In each, three windows were examined in admission order (actor `001` steps 1 to
  31, its tail 32 to 46 after the handoff, then actor `002` steps 1 to 34), every
  session was accepted and every version confirmed, every snapshot held the read lock for
  at most 2.1 ms against a 2 s bound, the writer recorded no busy error, no read began
  after the closing marker, `sealed()` accepted the finished store with an empty log, and
  the guardian ended the runner at teardown.
- **What it does not show.** Anything that needs a player or a real provider: the
  player's pace beside sealed admissions, decisions and game time, curator dollars,
  the length and output of a real session, and whether the knowledge helps. The custodian,
  the package preflight, the credential and the provider are substituted. The
  custodian's wait for a read in flight at close was not exercised: no read was in flight
  in either run.
- **Owner decisions needed.** None for this record. It is evidence for the price of the
  paid live run, which this record does not propose.

No game, no model request, $0 spent. The stand-in's cost figures are nominal and are not
money. [Live curator design](../design/live-curator-integration.md) ·
[Price proposal](2026-11-20-live-curator-run-price-proposal-836.md) ·
[Corrections](2026-11-20-live-curator-run-price-correction-836.md)

## What was run

`tests/live_curator_stand_in_run.py`, at source commit `6bcd15fb` (the runner branch of
pull request #856), from its worktree with the main checkout's Python:

```
python -m tests.live_curator_stand_in_run --output .runtime/live-curator-stand-in-runs/2026-11-20-213027
python -m tests.live_curator_stand_in_run --output .runtime/live-curator-stand-in-runs/2026-11-20-213328
```

Both exited 0. The outputs are git-ignored, in the main checkout's
`.runtime/live-curator-stand-in-runs/`: each directory holds `report.json` (every
measure below), `summary.txt`, the run directory `run/stand-in-admission/`, the sampled
status file `status-samples.jsonl`, the writer's records and a copy of the knowledge
repository. A trial run before them, `trial-212642`, also passed; the script then gained
the measure of what was left unexamined against the sealed store, and nothing else.

Settings: two actors of 45 input steps each, one step a second, with a handoff between
them; the runner's defaults for the trigger (20 steps), the ceiling (40), the poll (15 s)
and the look at the tags while a session runs (5 s). The runner's knowledge repository was
new for each run. Each run took about 91 s with the runner and 90 s more for the writer
alone.

**Real.** `run_supervised` with its `supervise` loop, teardown and `watch-terminal.json`;
its `--curator-runner` path (the read lock created before the custodian, the runner
started after it outside supervision, its termination); the gateway, the viewer and the
keep-awake helper as the guardian starts them, since none needs the game; the runner
process `tools.curator_host.live_runner` with `stage`, the sandbox, the Node curator host,
the proxy and the gate; the custodian's own close-out, `close_store`, and a real
`SessionStore`.

**Substituted.**

| Part | Substitute | Why |
| --- | --- | --- |
| The custodian's process | The guardian's `popen` is wrapped so the custodian's argv starts the script's `writer`. It writes `started.json`, `ready.json` and a `campaign-receipt/7` receipt as the custodian does, appends finished operations through `tests.curator_trace`'s writer (frames, host log, a handoff that seals the actor), starts and reaps a stand-in native process so the receipt's native fields are true of a real process, and closes the store through `close_store` | No game and no player host |
| Package preflight | A fixed profile and a route naming a dummy credential variable | No frozen package, clean tree or game |
| The route credential | A dummy value in that variable | No provider |
| The provider | `tests/curator_stand_in.py`'s `StandIn` on loopback. In this process its submission gets a fact identity from the first frame it cites, and adds the `control` type only while the base version lacks it | As it is, the stand-in submits fact `f1` and type `control` each time; the gate rejects the second window as a duplicate, and two consecutive rejections stop the runner by its own rule |

Before running, the script checks that the runner's configuration names only the loopback
stand-in, that the runner would present only the fixed loopback key, and that the
configuration is refused with any other upstream; it removes the provider key's variable
from its own environment.

## The measures

Each figure is from the files a live run writes, named in the last column; the two runs
are given as first run / second run where they differ.

| Measure | Result | Source |
| --- | --- | --- |
| Guardian's verdict | `custodian_terminal`, terminal coverage verified, cleanup verified, manifest unchanged, custodian exit 0 | `watch-terminal.json` |
| Windows examined, in order | `001` 1–31, `001` 32–46 (the tail after the handoff; 14 frames, the handoff has none), `002` 1–34; all accepted; first and last operation of each equal the sealed trace's step numbering | `curator-runner/examined.jsonl`, the sealed store |
| Session time (runner's start row to end row) | 1.2, 1.6, 1.6 s / 1.8, 1.6, 1.7 s | `examined.jsonl` |
| Status at each session's start → end: lag, backlog, covered prefix end (ordinal) | `001` 1–31: 31, 31, none → 0, 0, 31. `001` 32–46: 17, 17, 31 → 2, 2, 46. `002` 1–34: 34, 34, 46 → 0, 0, 80 | `curator-runner/status.json`, sampled every 50 ms |
| Lag over time (s from start: position, lag) | 0.2: 1, 1; 15.2: 16, 16; 30.3: 31, 31; 31.4: 31, 0; 46.5: 48, 17; 48.1: 48, 2; 63.1: 64, 18; 78.2: 80, 34; 79.8: 80, 0 (first run; the second differs by under 1 s and one step) | `status.json` samples |
| Left unexamined at the end | Runner's status: none, lag 0. Against the sealed store: `002` 35–45, 11 steps, lag 11 of 91 operations | `status.json`, the sealed store |
| Snapshots | 6 polls, 6 reads, none failed, over bound or refused; 4.6 reads a minute; 5 of 6 reads saw more operations than the one before | `curator-runner/polls.jsonl` |
| Snapshot hold (bound 2 s) | median 0.6 / 0.7 ms, max 2.1 / 0.8 ms | `polls.jsonl` |
| Read transaction (bound 1.5 s) | median 0.4 / 0.4 ms, max 1.2 / 0.5 ms | `polls.jsonl` |
| Staging | median 22 / 23 ms, max 51 / 36 ms | `polls.jsonl` |
| Time to publication (first sight of the version, after the window's newest frame and oldest frame) | v1: 1.3–31.3 / 2.0–32.0 s; v2: 4.0–17.0 / 4.7–17.7 s; v3: 1.6–34.6 / 2.4–35.4 s | `curator-runner/versions.jsonl`, frame `received_wall` in the sealed store |
| Writer busy errors | 0 with the runner, 0 alone | the writer's record |
| Writer pace with the runner / alone | 60.0 / 60.0 operations a minute in both runs (set at one a second) | the writer's record |
| Writer step time with the runner / alone | median 3.8 / 2.8 ms, max 11.2 / 11.0 ms (first run); median 1.5 / 3.5 ms, max 5.1 / 10.8 ms (second run) | the writer's record |
| Steps that overlapped a snapshot | 1 in each run, 1.1 / 1.0 ms | the writer's record against `polls.jsonl` |
| Closing marker | written; no read began after it; the last read ended 12.0 / 11.3 s before it; the close waited 1.3 / 1.1 ms (no read held the lock) | `store-closing.json`, `polls.jsonl`, the writer's record |
| Finished store | `sealed()` accepts it; log empty; 91 operations (46 and 45) | `session.sqlite3` |
| Runner at teardown | terminated by the guardian while it slept between polls: state `ended`, reason `interrupted`, exit 130, process and group absent, no further signal needed; the guardian's whole teardown took 0.15 s | `watch-terminal.json`, `status.json`, `curator-runner/stderr.txt` |
| Curator cost as the proxy counted it (nominal) | $0.0036 a session (3 requests at the stand-in's $0.0012), $0.0108 a run, $0.000135 an examined step; largest reservation for one request $0.131–$0.134 | session `summary.json`, `proxy-ledger.jsonl` |
| Upstream | 9 requests, all to the stand-in's route; the proxies forwarded 9 | the stand-in's request list, `summary.json` |
| New facts per window | 1, 1, 1 (`f-1`, `f-32`, `f-46` in the first run) | the knowledge repository's versions |

**What one comparison shows.** With the writer at one step a second, its pace and step
times with the runner and alone are the same within a few milliseconds, and only one step
in each run overlapped a snapshot. That is no more than the design says one run can show:
it does not show that the runner cannot slow play, and the writer is not the custodian's
loop.

### Not measured

| Measure the design lists | Why not here |
| --- | --- |
| Player pace in operations and decisions a minute beside sealed admissions of the same player | No player; the writer appends at a set pace |
| Decisions and game time | No player and no game |
| Curator dollars beside the player's | The stand-in's cost is nominal, and there is no player spend |
| Length, requests and output of a real curator session | The stand-in answers at once with a scripted three-request session |
| Facts later superseded or retired | No grooming runs, and the stand-in never revises a fact |
| Whether the knowledge helps the player | The design does not measure it |
| The custodian's wait for a read in flight at close | No read was in flight at close in either run; the reader's own tests cover it |
| Rate limits shared with the campaign | No provider account is used |

## Failures and anomalies

No required measure failed. Five things are worth the lead's attention.

- **The runner's final status says nothing is unexamined when 11 finished steps were
  never examined.** Its `unexamined`, `lag` and `backlog` count only what its last
  snapshot saw. The steps actor `002` finished after the last poll, 35 to 45, appear
  nowhere in the runner's files; the status file ends with lag 0 and an empty
  `unexamined`. The runner's module text states this ("steps finished after it are
  unexamined too and not counted"), and the runner cannot read after the marker. The
  design page says every range not examined is recorded as unexamined, and a spectator
  reading the status file would take lag 0 as caught up. Reproduce: run the script;
  compare `final_status` with `left_at_end_against_sealed_store` in `report.json`.
- **The guardian starts the runner without `--runtime-root`**, so the runner's runtime
  root is the code checkout's own `.runtime/`. The knowledge repository must be inside
  it, so in this run it was made under the worktree's `.runtime/knowledge/` and copied
  into the output directory afterwards. For a paid run started from a worktree, the
  runner would also look for the credential map in the worktree's `.runtime/` and,
  finding none, exit at start (status 2), which the guardian records and play ignores.
  From the main checkout the default is right. Reproduce: `tools/campaign_supervision.py`
  builds the runner's argv with `--run`, `--directory` and `--config` only, and
  `live_runner.parser()` defaults `--runtime-root` to the code root's `.runtime`.
- **The viewer writes its evaluations under the code checkout's
  `.runtime/evaluations/<session>`**, outside the output directory, because the guardian
  passes it that root. Nothing browsed the viewer in these runs.
- **The runner never saw the closing marker.** In both runs the writer closed about 12 s
  after the last poll, inside the 15 s interval, and the guardian's termination ended the
  runner first. The other ending, `refused:closing`, is covered by the runner's tests.
- **In the trial run the closed store left an empty `-wal` and a `-shm` file**;
  `sealed()` accepted it, since the log was empty. The two counted runs left neither, and
  the cause was not found.

## What it means for pricing a paid run

Facts this run supports; no price or ceiling is proposed here.

- **Window size follows the poll, not only the trigger.** A window starts at the first
  poll at which at least 20 steps wait. At 15 steps a poll, that was the second poll after
  the cursor, so the windows held 31 and 34 steps, and the handoff tail 15. Three
  sessions examined 80 steps: one session for every 26.7 examined steps. At a different
  pace the window is the smallest number of polls' growth that reaches 20, up to 40.
- **One snapshot a poll, 4.6 a minute** at the default 15 s poll, each holding the read
  lock for milliseconds over a store of up to 80 operations. A real admission's store is
  larger and its frames are real; staging time at that size is not measured.
- **The end of an admission leaves work for the session after it.** Here the last 11 of
  91 operations, those finished after the last poll, were not examined live. The last
  actor does not hand off, so its remainder is taken live only as a full window.
- **The proxy reserved about $0.13 for each request** at the `terra` arm's frozen price
  with `max_output_tokens` 4096, against a charge of $0.0012. A paid run's reservations
  depend on its own host settings and are not measured here.
- **The runner adds nothing measurable to teardown** in this arrangement: the guardian's
  whole teardown took 0.15 s.
