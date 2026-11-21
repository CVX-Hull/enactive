---
owner: lead
status: proposed
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

**Designed, not built.** Nothing here is implemented and no run is approved. The
[curator session design](curator-session.md) owns sessions, the gate and the store; this
page owns only what is new for a session that runs beside play. A first live run is
priced in a [dated proposal](../acceptance/2026-11-20-live-curator-run-price-proposal-836.md),
with [corrections](../acceptance/2026-11-20-live-curator-run-price-correction-836.md).
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

### The window

- **One window is one contiguous range of one actor**, because that is what a window can
  express (`harness/curator/window.py`). Ranges are taken in admission order: an earlier
  actor's steps before a later actor's.
- **The runner polls** on a wall-clock interval, proposed at 15 seconds. When the actor
  the cursor is in has at least *N* finished steps beyond it, the runner stages a
  snapshot and runs one session over them. The proposed *N* is 20, the window the
  [price pilot](../acceptance/2026-11-13-session-price-pilot.md) measured. Both values
  are proposals to be measured.
- **A ceiling of 40 steps**, in every case, including at a handoff. If more are
  waiting, the window takes the oldest 40 of that actor and the rest wait their turn.
- **An actor's tail.** When an actor's handoff has been verified, as the driver does
  before starting its successor, its remaining steps are taken in windows of at most 40,
  however few are left. An empty tail is skipped. The cursor then moves to the next
  actor.
- **The end of the admission.** The runner does not work after the custodian ends.
  Every range it has not examined is recorded as unexamined. Those steps are curated
  afterwards, over the sealed session, by an ordinary session between admissions, as all
  curation is today.
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

- the read transaction has its own time bound, proposed at two seconds, and is cancelled
  when it passes it;
- **the close needs the custodian's cooperation.** The custodian closes the store
  before it writes its terminal receipt and exits, and the guardian learns only of the
  exit, which is too late to stop a read. A read still open at that moment can keep the
  last connection from clearing the log, and `sealed()` would then refuse the finished
  session. So, in its close-out and after input authority is revoked, the custodian
  writes a closing marker and waits for the read bound before it closes the store; the
  runner opens no read once the marker exists. This is the one change to the custodian
  (`close_store` in `tools/campaign_run.py`). It is in close-out, not in the input loop:
  input is revoked at once, and only the store's closing waits;
- **the admission protocol.** Both files are in the run directory, beside
  `session.sqlite3`. `curator-read.lock` is the read admission lock. It exists only
  when a reader is configured, is created before the custodian starts, and is never
  created by the custodian. The marker is `store-closing.json`, created exclusively and
  never removed:
  `{"schema":"store-closing/1","session":<session>,"closing_wall":<wall seconds>}`.
  The runner admits a read in this order: it opens the existing lock file, takes a
  shared, non-blocking `flock` on it, checks that the marker does not exist, and only
  then opens its connection; it holds the shared lock until the connection is closed. A
  refused lock or an existing marker refuses the read. The custodian, only when the lock
  file exists, writes the marker, then polls an exclusive, non-blocking `flock` until it
  is acquired or the two-second bound has passed, and closes the store either way,
  holding the lock until the store is closed. Without the lock file there is no marker
  and no wait. Because a reader takes its lock before it checks for the marker, a read
  is either admitted before the marker exists, and holds the lock the custodian waits
  for, or it is refused: a reader held up between its check and its connection still
  holds the lock. What remains is a reader that stalls past the bound with its
  connection open: the store is closed anyway and can keep a non-empty log. If a
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

Nothing here has been tried against a live writer.
[The reader leaf](https://github.com/CVX-Hull/enactive/issues/837) tests it offline with
a synthetic writer process, at start, under sustained writes and at the writer's close:
that the read returns a consistent prefix, how long it holds, that the writer's timeout
is not hit, and that the step numbers of a snapshot equal those of the sealed trace.

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
  replay treats a version as available from the first request after the later one.
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
  covered ranges from the first step with no gap. A range no confirmed version covers is
  a gap. A restore makes the prefix unknown from the restored point on, and it is
  reported as unknown.
- **Lag.** Step numbers are local to an actor and cannot be subtracted across a handoff.
  Lag is counted over the admission's finished operations in order, by operation
  identity: the number after the last step of the covered prefix. It is reported beside
  the distance from the latest stamp, which is descriptive only.
- **The position play has reached.** The runner writes it at each poll: the identity of
  the latest finished operation and the time. The viewer's evaluator and the curator
  number operations differently, so the two are joined by operation identity, not by
  number.
- **When a step happened.** A frame's metadata holds when it was received
  (`received_wall`, written by the native receipt path). The projection does not carry
  it today; the snapshot's store does, and it is read by frame identity. A step with no
  frame, such as a handoff, has no age.
- **Order of sighting.** A fact's `seen` is a position, not an age.

The gate is used as it is. The first run is under the current structural contract.

## Failure

- **Publication is atomic for each version.** A session can publish one submission and
  then fail before a later one or before close-out, and the abort record is best effort.
  So the runner keeps the last version it confirmed, and records any publication it
  could not confirm for reconciliation after the admission.
- **Two failed sessions, or three failed snapshots, stop it.** After two consecutive
  failed sessions, or three consecutive snapshots that failed or passed their time
  bound, the runner stops for the rest of the admission and records why. Curation
  resumes between admissions, as today.
- **A snapshot that fails is discarded.** One is never used partly.
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
  and the covered prefix. No existing input carries this; the viewer's curator options
  accept configured files only.

A missing or unknown value is shown as such. The view stays read-only and sends nothing
to the curator.

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

- [The reader leaf](https://github.com/CVX-Hull/enactive/issues/837) settles the exact
  cutoff between the store and the host's log, the test against a live writer, and the
  equality of step numbers.
- [The runner leaf](https://github.com/CVX-Hull/enactive/issues/845) settles its record
  of examined ranges, its status file, and how it is launched and cancelled by the
  guardian.
- [The schedule replay leaf](https://github.com/CVX-Hull/enactive/issues/846): the lag
  simulation accepts only a steady or a session-shaped coverage today, and reading a
  run's result needs it to accept the covered prefix as recorded.
- **The request to the owner** settles the spend bounds, which the
  [price proposal](../acceptance/2026-11-20-live-curator-run-price-proposal-836.md) shows
  are planning limits and not a hard cap.

A live run needs the owner's approval of its design, price and envelope
([operator permissions](../operator-permissions.md)). Source work stops while a deciding
actor or the real game is live ([S-AGENT](../standards/agents.md)).
