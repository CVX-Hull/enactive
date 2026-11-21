---
owner: lead
status: active
date: '2026-11-20'
scope: 'How the curator runs during an ongoing admission: who starts a session and when, how a trace that is still being written becomes readable, publication and coverage, failure, grooming, delivery, the spectator view and the measures of a first bounded live run'
review_trigger: The live trace reader is built, a live run is priced or approved, or the delivery contract changes
---

# Running the curator during play

## At a glance

No curator runs during play today. The curator's sessions read only sealed traces, and
delivered knowledge is frozen into a package before the admission starts. This page
designs the smallest change that lets a curator follow an admission as it is played, so
that its lag, cost and effect on play can be measured before anything depends on them.

**Designed, and built only in part.** The custodian's closing marker and wait
(`close_store` in `tools/campaign_run.py`), the snapshot reader
(`harness/trace/snapshot.py`) and the curator runner (its rules in
`harness/curator/runner.py`, its process in `tools/curator_host/live_runner.py`, started
by the guardian's `--curator-runner` option) are implemented and tested offline. Delivery
inside an admission is not. The owner has approved one paid live run
([decision log](../decisions/owner-decisions.md#one-paid-live-curator-run)); none has
been made. The
[curator session design](curator-session.md) owns sessions, the gate and the store; this
page owns only what is new for a session that runs beside play. The run's price is in
the [stand-in run's record](../acceptance/2026-11-20-live-curator-stand-in-run-851.md#the-price-of-the-paid-run-proposed-again),
which rests on a [dated proposal](../acceptance/2026-11-20-live-curator-run-price-proposal-836.md)
and its [corrections](../acceptance/2026-11-20-live-curator-run-price-correction-836.md).
This page settles the design; its [last section](#what-this-design-settles-and-what-it-leaves)
lists what the leaves that build it must settle first.

The design in one paragraph: a **curator runner**, started by the guardian beside the
custodian, stages a **snapshot** of the growing session, runs an ordinary windowed
admission session over it, and publishes through the gate as it is today. Curation is
never in the path of the player's input. In the first live run the running actor does
not receive the new knowledge: the run measures how far curation trails play, not what
the player does with it.

## Who starts a session, and when

The guardian (`tools/campaign_supervision.py`) starts the custodian, the viewer, the
gateway and a wake helper as separate children. The curator runner is one more.

- **It is not part of the custodian.** The custodian (`tools/campaign_run.py`) holds
  input custody and passes the player's credential to the host. Nothing is added to its
  loop.
- **It is not a supervised child.** The guardian treats the early exit of a supervised
  child as a failed launch, and keeps the viewer apart from them for that reason. The
  runner gets the viewer's treatment at launch: its exit never counts as loss.
- **It ends when the custodian ends.** The guardian begins teardown when the custodian
  terminates, and there is no period after that in which the runner may work. On
  cancellation the runner closes its session, its proxy and its read connection. It
  never delays the revoking of input. The custodian's closing of the store may wait,
  within the read's time bound, for a read already admitted
  ([below](#how-a-growing-trace-becomes-readable)). A session in flight is interrupted
  and leaves an aborted record.
- **Its spend is reserved before a request is sent.** Curator requests go through the
  curator proxy, as the shadow runner's do (`tools/curator_host/shadow.py`,
  `harness/curator/proxy.py`). The proxy reserves an estimated worst case for each
  request and revokes itself when a charge exceeds the reservation. When the next
  reservation is refused the runner stops, even if its counted spend is under its cap.

**Launch and cancellation.** The guardian's `--curator-runner CONFIG` names the runner's
configuration (`curator-runner-config/1`, whose fields the process module states: its
own knowledge repository under `.runtime/knowledge`, the arm, the spend caps, the
upstream, the trigger, ceiling and poll interval). Only with the option, and before it
launches the custodian, the guardian creates `curator-read.lock` exclusively and the
runner's directory `curator-runner/`, both in the run directory; a package that already
holds either is refused before the supervision reservation. That location passes
every check of the run directory: package preflight refuses only the named files of a
started run, the supervision markers are two named files, and the viewer, the evaluator
and the projection read named files or `actors/`. The evidence copy keeps the directory
with the run. The guardian starts the runner after the custodian, with the viewer's
treatment: in its own process group, not among the supervised children, with no route
credential, and a launch failure or early exit is recorded in `watch-terminal.json` and
never counted as loss. At teardown the runner is terminated with the viewer, after the
custodian's and the gateway's termination is requested, and its group is closed last,
after the custodian's bounded wait. On SIGTERM or SIGINT the runner interrupts a session
in flight (which seals its own aborted record), closes its proxy and any read, records
the interruption and exits with status 130; further signals do not cut that short.

### The cursor

Published coverage cannot be the runner's only record of progress. A session can close
cleanly and submit nothing, a submission can be rejected, and a restore can bring back
an older stamp. So the runner keeps its own durable record in the run directory: every
range it has examined, by actor, in admission order, with how the session over it ended.

- **It starts** before the first step of the first actor.
- **It advances** when a session closes, whatever it published: accepted, nothing
  submitted, or rejected. A rejection is recorded and counts as a failure. An aborted or
  interrupted session does not advance it.
- **Examined is not covered.** A range that was rejected, or that published nothing, was
  examined and is not knowledge. [Coverage](#publication-coverage-and-age) is a
  different record.
- **The record** is `curator-runner/examined.jsonl` (`curator-runner-examined/1`),
  append-only: a `start` row when a session begins and an `end` row when it returns, each
  with the window, the operations at its two ends, and `coverage`: the covered prefix,
  lag and backlog at that moment, so a finished run reports them over time. The `end`
  row names how the session ended, whether the cursor advanced and whether it failed,
  with the gate's verdicts. A sealed session is `rejected` if any submission was
  rejected, `unconfirmed` if a verdict is unknown, `accepted` if one was published and
  `nothing-submitted` otherwise; the cursor advances over all four, and the first two
  are failures. The other endings are listed under [Failure](#failure). A `start` row
  with no `end` was interrupted, so the record survives a restart of the runner, and the
  cursor of an actor is the last step of its advanced rows. On loading, each of the
  runner's append-only files is cut back to its last newline, so a row a killed runner
  left half written is dropped, never joined to the next.

### The window

- **One window is one contiguous range of one actor**, because that is what a window can
  express (`harness/curator/window.py`). Ranges are taken in admission order: an earlier
  actor's steps before a later actor's.
- **The runner polls** on a wall-clock interval, proposed at 15 seconds. The snapshot is
  its only read of the store, so it stages one at each poll, records from it the position
  play has reached, and removes it when the poll ends. When the actor the cursor is in
  has at least *N* finished steps beyond it, the runner runs one session over them on
  that snapshot. The proposed *N* is 20, the window the
  [price pilot](../acceptance/2026-11-13-session-price-pilot.md) measured. Both values
  are proposals to be measured.
- **A ceiling of 40 steps**, in every case, including at a handoff. If more are
  waiting, the window takes the oldest 40 of that actor and the rest wait their turn.
- **An actor's tail.** When an actor's handoff has been verified, as the driver does
  before starting its successor, its remaining steps are taken in windows of at most 40,
  however few are left. An empty tail is skipped. The cursor then moves to the next
  actor.
- **The end of the admission.** The runner does not work after the custodian ends, and
  cannot read then, so it cannot know the steps finished after its last read. It records
  as unexamined every range its last read saw and did not examine, states the position
  and wall time of that read (`as_of`), and marks what came after it as unknown
  (`after_last_read`). Steps finished after that read are counted afterwards from the
  sealed session. All of these are curated afterwards, over the sealed session, by an
  ordinary session between admissions, as all curation is today.
- **The lock.** One session runs at a time, and the repository lock refuses a second at
  once (`harness/curator/session.py`). The runner does not queue. On a refusal it does
  nothing, and at the next poll it computes the range again from its record.
- **Backpressure never reaches the player.** A growing backlog is recorded. It does not
  slow play.
- **This is the home of the trigger.** A session starts on finished operations beyond
  what was examined. That is not the same as starting on decisions not yet covered:
  after a rejected or empty window, decisions stay uncovered and no new session starts
  for them. What a cut depends on is enough published coverage, which the covered
  prefix, below, measures. The [context design](player-context.md) states that
  dependency and points here for the trigger.

## How a growing trace becomes readable

This is the central question. The custodian writes the session store in write-ahead-log
mode with no explicit checkpoint (`harness/computer/store.py`). The curator's projection
reads through `sealed()` (`harness/trace/stores.py`), which refuses a missing store or a
non-empty log and opens the rest as immutable. It cannot read a live store, and should
not: an immutable read of a changing file can be wrong. `sealed()` says nothing about
whether a writer is still present; it only refuses what it can see is unsafe.

One reader of the live store exists already. The viewer's evaluator opens it read-only
with a one-second busy timeout on every supervised run
(`harness/evaluation/core/sources.py`). Its separate queries do not show how the read
proposed here behaves; they show only that a second connection beside the custodian is
not new. Three architectures were compared.

| Architecture | What it needs | Why it is or is not chosen |
| --- | --- | --- |
| **The runner copies the finished rows into a fresh store** in one short read transaction | One read-only, non-immutable connection, open for that transaction | **Chosen.** The projection then reads a closed, stable file through `sealed()`, unchanged. The read is bounded and its cost can be tested |
| The projection reads the live store directly, as a log-aware reader | A read transaction held for the whole projection, and a second way into the stores beside `sealed()` | Not chosen: the read is as long as a projection, and every offline reader would share a code path that tolerates a live store |
| The writer seals at each window | The custodian checkpoints and yields a sealed prefix at set points | Not chosen as the first way: it puts curation's needs in the process that holds input custody. It is the fallback |

A whole-database online backup is a variant of the first and was set aside: its length
is not bounded by a busy timeout, it restarts when the writer commits between steps, and
it copies rows the window will not use.

**What a reader beside the custodian costs.** A read-only connection uses the store's
log and shared-memory files where they exist, and may create them where the directory
allows. A read transaction beside an established writer lets ordinary appends through.
While it is open it can hold back checkpoint progress, it adds disk work on the same
machine, and if it outlived the writer it could interfere with the checkpoint and cleanup
at close. The custodian's own quarter-second timeout does not bound the read, and does
not protect input from shared disk load or storage errors. So:

- the read has its own time bound, proposed at two seconds for the reader's whole hold
  of the admission lock described below, from taking it to releasing it. The read
  transaction inside it is cancelled a second and a half after the lock is taken, so
  that cancelling and closing fit within the two seconds;
- **the close needs the custodian's cooperation.** The custodian closes the store
  before it writes its terminal receipt and exits, and the guardian learns only of the
  exit, which is too late to stop a read. A read still open at that moment can keep the
  last connection from clearing the log, and `sealed()` would then refuse the finished
  session. So, in its close-out and after input authority is revoked, the custodian
  writes a closing marker and waits up to the read bound before it closes the store; the
  runner opens no read once the marker exists. This is the one change to the custodian
  (`close_store` in `tools/campaign_run.py`). It is in close-out, not in the input loop:
  input is revoked at once, and only the store's closing waits;
- **the admission protocol.** Both files are in the run directory, beside
  `session.sqlite3`. `curator-read.lock` is the read admission lock. It exists only
  when a reader is configured, is created before the custodian starts, is never
  created by the custodian, and is not removed or replaced while the session is live:
  a replaced file is a different file, and its locks would never meet. The marker is `store-closing.json`, created exclusively and
  never removed:
  `{"schema":"store-closing/1","session":<session>,"closing_wall":<wall seconds>}`.
  The runner admits a read in this order: it opens the existing lock file, takes a
  shared, non-blocking `flock` on it, checks that the marker does not exist, and only
  then opens its connection; it holds the shared lock until the connection is closed.
  Closed means every cursor is closed first and then the connection: a connection
  closed with a cursor still part-way through its results keeps its read transaction
  and its files open. A refused lock or an existing marker refuses the read. The custodian, only when the lock
  file exists, writes the marker, then polls an exclusive, non-blocking `flock` until it
  is acquired or the two-second bound has passed, and closes the store either way,
  holding the lock until the store is closed. Without the lock file there is no marker
  and no wait. Because a reader takes its lock before it checks for the marker, a read
  is either admitted before the marker exists, and holds the lock the custodian waits
  for, or it is refused: a reader held up between its check and its connection still
  holds the lock. What remains is a reader that holds its lock past the bound, or
  releases it with its connection not fully closed: the store is closed anyway and can
  keep a non-empty log. If a
  session's store still has a non-empty log after close, the sealed session cannot be
  read, and that is reported, whatever caused it;
- the claim this design makes is narrow: **curation is not in the input path, and a
  failed runner stops nothing**. It is not that play cannot be affected.

### The snapshot

The projection needs more than a database. A snapshot is a staged session directory,
under the session's own name so that windows, coverage and frame provenance use the name
they would for the sealed session.

- **A fresh store** built by the runner from one read transaction, written to a new
  file, and closed. The runner checks that the new file has no non-empty log before
  anything opens it with `sealed()`.
- **Every operation of an included actor from its first, not only the window's.** The
  projection numbers an actor's steps by sorting on wall time and operation identity. A
  snapshot that held only a window, or a later one that sorted differently, would number
  the same step differently. Each snapshot therefore carries the actor's whole finished
  prefix, and the numbering it yields must equal the sealed trace's.
- **The cutoff is by identity, across the store and the host's log.** The runtime
  commits an operation's terminal row before it returns to the host, and the host writes
  its tool result after that, or exits without writing it. An operation is included only
  when its terminal row exists *and* the host's log holds the matching result, or the
  actor has ended. A call in the log with no included operation is left out; it is not
  attached to a neighbouring step.
- **Collections.** A collection receipt can arrive after an operation's terminal row. An
  operation with a collection still outstanding is not included until the collection is
  recorded or the actor has ended.
- **Each included actor's frozen inputs**, prompt and guide. An actor whose frozen
  manifest does not exist yet is not included.
- **The frames** the included operations name, linked or copied and checked against
  their recorded digests. A frame file is not rewritten once it exists.
- **The host's log, cut to match:** whole lines only, up to the last included operation.
- **The custody and route metadata** the projection uses to keep secrets out of the
  workspace. That guard runs as it does now, outside the curator's workspace.
- **The campaign manifest and the supervisor's record of its digest.** Once the
  [field table](general-memory.md#provenance-and-the-checks-it-allows) is implemented,
  a session's world and lineage must be verified before its first publication, and a
  snapshot needs these two to do it. A first live run made before that migration is
  under the current contract, whose manifest has no `world` label, and verifies none.
- **Not the player's journal.** A restricted window drops it, and its writer does not use
  a write-ahead log, so reading it beside the custodian could delay a commit.

### Not yet shown

Nothing here has been tried against a running custodian or a real host. The reader
(`harness/trace/snapshot.py`, whose module text states the exact cutoff) is tested
offline with a synthetic writer process, at start, under sustained writes and at the
writer's close: the read returns a consistent prefix, the writer's timeout is not hit,
and the step numbers of a snapshot equal those of the sealed trace. The synthetic
writer closes its store through the custodian's own `close_store` and imitates the
host's log; it is not the custodian's loop and not the host.

Three things the reader cannot see are left as they are. Step numbers follow wall time,
so a wall clock that steps back between two operations of one actor renumbers them, in
the sealed trace as well. Two operations of one actor with identical wall times sort by
identity, so a later one can sort before one a snapshot had already numbered. And a
frame linked to an operation after its terminal row would change a step a snapshot had
already included.

**The fallback** has its own test, not this one's: at each window the custodian yields
a detached, stable copy of the prefix. Checkpointing the live file is not enough, since
the file stays live. If the first architecture fails its test, this page changes before
any run.

## Publication, coverage and age

Each thing measured has a named source. None changes `curator-coverage/2`.

- **Publication time.** The gate tags a version; a tag has no time of its own, and its
  commit's time precedes it. A session can publish several versions before it closes.
  A session call blocks until the session closes, and can publish several versions in
  its close-out. So the runner watches for tags on its own cadence: it looks once before
  the session starts, keeps looking while it runs, and looks once more after it returns.
  For each version it records when its last look without the tag began and when its
  first look with the tag ended. The version was published between those two times. A
  replay treats a version as available from the first request after the later one. The
  looks while a session runs are on a cadence, proposed at five seconds. Each version is
  a row of `curator-runner/versions.jsonl` (`curator-runner-version/1`) with the two
  times, its stamp and, for a restore, the version restored; versions present at the
  runner's first look are its baseline, from before the admission, and the first time of
  a version first seen after a restart of the runner is unknown.
- **Confirmed.** A version is confirmed when its tag was seen, an examined session's
  verdicts report it published, and its stamp is that session's window. A version
  reported but never seen, one whose stamp is not its window, an unknown verdict, and a
  tag no examined session reports are each recorded as unconfirmed.
- **Coverage.** Only an accepted publication carries a stamp: the session, the actor and
  the last step read. The stamp is the latest window's. It makes no claim about earlier
  windows.
- **The covered prefix.** What the cut needs is not the latest stamp but an unbroken run
  of covered steps from the admission's first. It is computed from the step ranges of
  confirmed tagged versions, and not from the record of examined ranges or the count of
  failures. A range is covered when at least one version published from it is
  confirmed. It stays covered if a later submission over it was rejected, was not
  confirmed, or failed in close-out, and it becomes covered if a retry publishes after a
  first attempt that published nothing or was aborted. The prefix is the longest run of
  covered ranges from the first step with no gap, actor by actor in admission order: it
  passes to the next actor only when an ended actor is covered to its last finished
  step. A range no confirmed version covers is a gap. A restore makes the prefix unknown
  from the restored point on, and it is reported as unknown: the runner counts only the
  versions up to the one restored, records the restore beside the prefix, and reports
  lag as unknown.
- **Lag.** Step numbers are local to an actor and cannot be subtracted across a handoff.
  Lag is counted over the admission's finished operations in order, by operation
  identity: the number after the last step of the covered prefix. The runner finds that
  step by the operation its window recorded there, in the latest snapshot, and reports
  lag as unknown when the snapshot does not hold it. It is reported beside the distance
  from the latest stamp, which is descriptive only.
- **The position play has reached.** The runner writes it at each poll: the identity of
  the latest finished operation and the time, which is the snapshot's store time: the
  wall times at which the snapshot call began and returned, between which it read the
  store. The viewer's evaluator and the curator
  number operations differently, so the two are joined by operation identity, not by
  number.
- **When a step happened.** A frame's metadata holds when it was received
  (`received_wall`, written by the native receipt path). The projection does not carry
  it today; the snapshot's store does, and it is read by frame identity. A step with no
  frame, such as a handoff, has no age.
- **Order of sighting.** A fact's `seen` is a position, not an age.

The gate is used as it is. The first run is under the current structural contract.

## Replaying a recorded schedule

A finished run's lag result is read by replaying the covered prefix, as the runner
recorded it, through the lag simulation (`tools/memory_screen_checks.py`, the `cut`
command). The runner and the simulation count different things, so the replay first
maps one to the other.

**The two units.** The runner records the covered prefix as an actor, a step and that
step's operation identity, with the wall time of the row that holds it. The simulation
works on one actor's player requests in order: its turn *k* holds the tool calls the
actor's *k*-th request made, with their results, and at each request it asks how many of
the actor's turns, counted from the first, are covered. A request can create no
operation, one or several, so a step number is never used as a turn number.

**From a prefix to covered turns.** All of it is read from the sealed run's host logs
and the schedule; the session store is not needed.

- **The operation finds the request.** The prefix's operation identity is the
  `operation_id` in the result of a call that creates an operation (an input, an
  observation, a handoff or a program run) in the actor's host log, and that call's
  request is the turn the prefix ends in. A call that only collects an earlier
  operation's result names that operation too and is not used.
- **A turn is covered only whole.** When the prefix ends at the last operation that
  request created, the turn it ends in is covered; when it ends at an earlier one, only
  the turns before it are.
- **A retried request is one turn**, and it starts when its first attempt starts: a
  retry sends the same context again, so a publication between attempts cannot change
  it.
- **Other actors.** Actors are in admission order, the sorted order of their
  directories. Every turn of an actor before the prefix's actor is covered, and no turn
  of an actor after it. An empty prefix covers nothing.
- **An operation no tool result names**, or one recorded as `unknown`, cannot be placed.
  That change is left out and the replay reports how many it left out. The earlier
  prefix stays in force, except that a change with a restore that cannot be placed
  leaves nothing covered from then on. The replay then covers less than the run did,
  never more.

**From a time to a request.** A change applies from the first request of an actor that
starts after the change's time. The time is the wall time of the first poll row that
shows the new prefix. No poll is written while a session runs, so that row is later
than the publication's first sighting by up to the rest of the session that published
it and one poll interval; the replay is late by that much and never early. A request
with no recorded start time takes the coverage of the request before it, and the first
request of an actor with none is covered by nothing. The host log, the store and the
runner use the same wall clock, in seconds since the epoch.

**A restore.** The runner counts only the versions up to the one restored and marks the
prefix with the restore. The replay uses the prefix so counted, and this is the only
case in which a prefix may move backwards. A restore takes coverage away, so it is
timed the other way round: by the last runner row that did not show it, and it applies
to a request that starts at that time or later. A cut already made is not undone.

**The schedule file** is the simulation's input, `curator-coverage-schedule/1`:

```json
{"schema": "curator-coverage-schedule/1",
 "changes": [
  {"wall": 1795212345.5, "end": null, "restore": false},
  {"wall": 1795212391.2, "end": {"actor": "001", "step": 20, "operation": "745118b6…"}, "restore": false}]}
```

Each change is the covered prefix from `wall` on: `end` is `null` for an empty prefix,
or the actor's directory name, the step and the operation identity (or `unknown`).
`python -m tools.memory_screen_checks schedule RUN` writes it, to standard output or to
`--output FILE`, from `RUN/curator-runner/polls.jsonl` and the final `status.json`, which it
only reads: one change for each row
whose covered prefix differs from the row before, timed by the poll's `ended_wall` and
the status file's `updated_wall`, or for a restore by the time of the row before it. It
refuses an output file inside `RUN`. `cut RUN --coverage schedule --schedule FILE`
replays it over that one run, in place of the lag rows.

**Refused.** A schedule is refused, with the change named, when its schema or a field
is missing or of the wrong type, when a step is below one, when its times decrease,
when a prefix moves backwards without a restore, by its steps or by the turns its
operations are placed in, when it names an actor the run does not have, or when it is
given with more than one run. Nothing is repaired or reordered. A runner that was
restarted and lost its last snapshot can record an earlier prefix with no restore; that
record is refused too, since nothing in it says what stayed covered.

## Failure

- **Publication is atomic for each version.** A session can publish one submission and
  then fail before a later one or before close-out, and the abort record is best effort.
  So the runner keeps the last version it confirmed, and records any publication it
  could not confirm for reconciliation after the admission.
- **Two failed sessions, or three failed snapshots, stop it.** After two consecutive
  failed sessions, or three consecutive snapshots that failed or passed their time
  bound, the runner stops for the rest of the admission and records why, in
  `curator-runner/stopped.json`, which a restarted runner honours. Curation resumes
  between admissions, as today. A refused read is not a failed snapshot: `closing` ends
  the runner with no further read, `no-store` waits for the next poll, and a missing
  read lock stops it.
- **The custodian's end without a marker.** A custodian that died writes no closing
  marker. So at each poll, before it reads, the runner checks for the custodian's
  `receipt.json` in the run directory, and ends with no further read if it exists.
- **Why it ends or stops** (the status file's `stop_reason`). It ends with
  `store-closing` (the closing marker refused its read), `store-closed` (the receipt
  exists) or `interrupted` (a signal). It stops for the rest of the admission with
  `2 consecutive failed sessions`; `3 consecutive snapshots failed or passed their
  bound`; `read refused: no-read-lock` (no reader is configured); `error: <type>` (an
  unexpected exception in the runner itself, recorded and raised); or a session's own
  reason: `proxy-revoked` (a charge passed its reservation, or the proxy revoked
  itself), `spend-reservation-refused`, `cap-reached` (the runner's whole cap is
  counted as spent), `proxy-unsettled` (the proxy closed with requests unsettled),
  `cleanup-unconfirmed` (host processes survived, or the host ran and the sandbox's
  result is missing) and `host-unavailable: <why>` (the curator host could not be
  resolved).
- **How a session ends** (an `end` row's `outcome`). `accepted`, `nothing-submitted`,
  `rejected` and `unconfirmed` close it and advance the cursor, the last two as
  failures. `aborted` fails without advancing; a session that aborted before its host
  ran is an ordinary failed session. `interrupted`, `lock-refused`, `not-started` (no
  spend left) and `host-unavailable` neither advance nor fail. An interruption that
  lands after a session returned and before its `end` row is written is recorded as
  `interrupted`, so coverage is understated, never overstated.
- **Spend** is counted from what each session's proxy leaves, whether or not the session
  returned: its closing snapshot, counting reservations it still held as spent, or else
  the charges in its ledger. A restarted runner counts it again the same way.
- **A host can outlive a killed runner.** The sandboxed curator host runs in its own
  process group. If the runner is killed outright, so that its sandbox cleanup never
  runs, the host can outlive it. It cannot spend once the runner's proxy is gone, since
  it holds only a session token for that proxy, and it is not covered by the guardian's
  `cleanup_verified`, which covers the groups the guardian created.
- **A snapshot that fails is discarded.** One is never used partly. The guardian also
  removes `curator-runner/snapshots/` after the runner's group is closed, since a runner
  killed mid-poll can leave one, and it holds custody copies.
- **What the runner shares with play.** No process, no lock on the repository and no
  place in the input path. It does share the machine's disk, a read connection to the
  session store, and possibly the provider account: the shadow runner can resolve the
  same credential as the campaign, so rate limits may be shared.

## Grooming

Grooming refuses a window and reads the sealed source of the last published admission,
and that stays. A handoff between actors inside an admission triggers no grooming.
During play the runner runs admission sessions only, which may leave facts unfiled.
Grooming runs between admissions, as now. If the live admission published nothing, the
last published admission is still the one before it, and grooming does not examine what
the runner missed.

A live run uses a knowledge repository of its own, for the one world the admission is
played in, in line with the owner's decision of 20 November 2026 that memory work starts
with facts about one world ([decision log](../decisions/owner-decisions.md)).

## Delivery to a running actor

Delivered knowledge is frozen: package preflight checks the hash of
`delivered-knowledge.json` (`tools/campaign_package.py`), and the driver copies those
bytes into each actor's frozen inputs (`tools/campaign_player.py`).

- **The first live run does not change that.** New versions are published, and the next
  admission's package can carry them. The run measures lag and cost, not uptake inside
  the admission.
- **Delivery inside an admission is a later migration,** and this page does not design
  it. It gives [the handoff leaf](https://github.com/CVX-Hull/enactive/issues/838) one
  invariant: a version is selected at a request boundary, and the briefing, the recall
  and the player's knowledge tools all answer from that one version for that request,
  with its identity recorded. Today the host and the application each load their own
  frozen copy. The [context design](player-context.md) lists the other readers that move
  with a version change, and the package, the export and a successor actor's inputs move
  in the same migration.

## The spectator view

Two things are shown, from two inputs, and kept apart.

- **What the actor was given:** the actor's frozen delivered version, which
  `harness/viewer/knowledge.py` already projects after verifying its digest.
- **What the curator has done since:** a status file the runner writes, holding the
  position play has reached, the ranges examined, the last confirmed version, its stamp
  and the covered prefix, shown in the Curator view as the
  [status contract](../contracts/evaluation.md#curator-runner-status) states.

The status file is `curator-runner/status.json` (`curator-runner-status/1`), replaced
atomically at each poll and at each session's start and end. It holds the runner's
state (`polling`, `in-session`, `stopped` or `ended`) and settings, the position, the
latest snapshot's hold, transaction and staging times and its store time, every
examined range with how it ended, the cursor, the session in flight, the covered prefix
(its last step, that step's operation and its place among the admission's finished
operations, and any restore), lag, the distance from the latest stamp, backlog, the last
confirmed version and its stamp, the unconfirmed publications, every version with its
two times, the consecutive failures, and, once the runner has stopped or ended, why and
the ranges left unexamined. Lag, backlog and the unexamined ranges count only what the
last successful read saw: `as_of` is that read's position and wall time, and
`after_last_read` is always `unknown`, because steps finished after it are not known to
the runner. So a final status never shows the admission as caught up; the steps after
its last read are counted from the sealed session. Each poll is also a row of
`curator-runner/polls.jsonl`, with its snapshot's timings or why there was none, the
position and the same `coverage`, with its `as_of`, as an examined row. `stopped.json` is written whole, by a rename, as the status file is.

A missing or unknown value is written as `unknown`, not guessed, and shown as such. How
the viewer reads the file and shows a missing or partly written one is the
[status contract](../contracts/evaluation.md#curator-runner-status)'s.

## What a first live run measures

Decisions, computer operations and game time are reported separately. They are three
units: a window counts operations, the run ledger counts decisions, and game time barely
moves in menus.

- **Lag and the covered prefix**, as defined above, when each session starts and ends.
- **Time to publication:** from a step's frame to the first sight of the version that
  covers it.
- **Backlog:** whether unexamined steps grow, and what was left unexamined at the end.
- **Cost:** curator dollars per session and per examined step, beside the player's.
- **Snapshots:** how long each read transaction holds, how long staging takes, and
  whether any failed.
- **Player pace:** operations and decisions a minute, beside the same figures for named
  sealed admissions of the same player. One admission cannot show that the runner did or
  did not slow play. A large difference is a reason to investigate, not a finding.
- **New facts:** how many are published per window, and how many are later superseded or
  retired.

It does not measure whether the knowledge helps the player.

## What this design settles, and what it leaves

It settles who runs the curator, the cursor and window rules, the architecture of the
read, what a snapshot contains, what each measure is read from, and what the first run
does and does not deliver. It is not an implementation. Before each is built:

- The reader is built: `harness/trace/snapshot.py` states the exact cutoff between the
  store and the host's log, and its tests cover a synthetic live writer and the
  equality of step numbers.
- The runner is built: `harness/curator/runner.py` states its record of examined ranges,
  its status file and the covered prefix, and the guardian launches and cancels it as
  [above](#who-starts-a-session-and-when). Its tests run its rules with injected parts,
  one runner beside the synthetic growing trace with a real session through the gate,
  the process's sessions through the proxy and the stand-in curator, and the guardian's
  launch and teardown. It has not run beside a real custodian.
- The schedule replay is built: `tools/memory_screen_checks.py` writes a run's recorded
  covered prefix as a schedule and replays it, as
  [above](#replaying-a-recorded-schedule).
- **The spend bounds** are settled by the owner's approval of one run
  ([decision log](../decisions/owner-decisions.md#one-paid-live-curator-run)). They are
  planning limits and not a hard cap, as the
  [price section](../acceptance/2026-11-20-live-curator-stand-in-run-851.md#the-price-of-the-paid-run-proposed-again)
  says.

A live run needs the owner's approval of its design, price and envelope
([operator permissions](../operator-permissions.md)). Source work stops while a deciding
actor or the real game is live ([S-AGENT](../standards/agents.md)).
