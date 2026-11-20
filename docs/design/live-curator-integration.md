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
priced in a [dated proposal](../acceptance/2026-11-20-live-curator-run-price-proposal-836.md).

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
  runner gets the viewer's treatment: its exit never counts as loss, and it is cleaned up
  on its own.
- **Its spend is capped before a request is sent.** Curator requests go through the
  curator proxy, as the shadow runner's do: the remaining budget is reserved before a
  request is forwarded, and the run stops on a breach, a revoked proxy, unsettled
  accounting or unconfirmed cleanup (`tools/curator_host/shadow.py`,
  `harness/curator/proxy.py`). The runner reuses that, with its own cap.

### The cursor

Published coverage cannot be the runner's only record of progress. A session can close
cleanly and submit nothing, a submission can be rejected, and a restore can bring back
an older stamp. So the runner keeps its own durable cursor in the run directory: for
each actor, in admission order, the last step it has examined.

- **It starts** before the first step of the first actor.
- **It advances** when a session closes, whatever it published: accepted, nothing
  submitted, or rejected. A rejection is recorded and counts as a failure. An aborted or
  interrupted session does not advance it.
- **Coverage** stays what the gate publishes with an accepted version, and may trail the
  cursor.

### The window

- **One window is one contiguous range of one actor**, because that is what a window can
  express (`harness/curator/window.py`).
- **The runner polls** on a wall-clock interval, proposed at 15 seconds. When the actor
  the cursor is in has at least *N* finished steps beyond it, the runner stages a
  snapshot and runs one session over them. The proposed *N* is 20, the window the
  [price pilot](../acceptance/2026-11-13-session-price-pilot.md) measured. Both values
  are proposals to be measured.
- **A ceiling of 40 steps.** If more are waiting, the window takes the oldest 40 of that
  actor and the rest wait. Nothing is skipped.
- **An actor's tail.** When an actor has handed over, its remaining steps form a window
  however few they are, and the cursor then moves to the next actor.
- **The end of the admission.** After the admission ends, the runner runs one last
  session over the remaining steps, on the sealed session, and stops. If its cap or its
  failure rule prevents that, the tail is recorded as not examined.
- **The lock.** One session runs at a time, and the repository lock refuses a second at
  once (`harness/curator/session.py`). The runner does not queue. On a refusal it does
  nothing, and at the next poll it computes the range again from the cursor.
- **Backpressure never reaches the player.** A growing backlog is recorded. It does not
  slow play.

## How a growing trace becomes readable

This is the central question. The custodian writes the session store in write-ahead-log
mode with no explicit checkpoint (`harness/computer/store.py`). The curator's projection
reads through `sealed()` (`harness/trace/stores.py`), which refuses a missing store or a
non-empty log and opens the rest as immutable. It cannot read a live store, and should
not: an immutable read of a changing file can be wrong. `sealed()` says nothing about
whether a writer is still present; it only refuses what it can see is unsafe.

One reader of the live store exists already. The viewer's evaluator opens it read-only
with a one-second busy timeout on every supervised run
(`harness/evaluation/core/sources.py`). So the choice is not whether anything may read
beside the custodian, but how the curator's projection gets a consistent, complete set
of evidence. Three ways were compared on that.

| Way | What it needs from the live store | What it costs |
| --- | --- | --- |
| **A short read of the finished rows into a fresh store** | One read-only, non-immutable connection, open for one read transaction | **Chosen.** It is the kind of read the viewer already makes. While the transaction is open it can hold back the log's checkpoint; it does not block the custodian's writes |
| A whole-database online backup | A read connection for the length of the copy, which restarts when the writer commits between steps | Not chosen: its length is not bounded by a busy timeout, and it copies rows the window will not use |
| The writer captures at set points | New work in the custodian's loop, and a hold on its writes | Not chosen as the first way: it puts curation's needs in the process that holds input custody. It is the fallback |

What is true of any reader beside the custodian, and is not designed away: it needs the
store's log and shared-memory files to exist, it takes part in SQLite's locking though it
writes no rows, and it adds disk work on the same machine. The custodian's own writes use
a quarter-second timeout, and a failed intent or terminal write can stop input. The
design's claim is narrow: **curation is not in the input path, and a failed runner stops
nothing**. It is not that play cannot be affected.

### The snapshot

The projection needs more than a database. A snapshot is a staged session directory,
under the session's own name so that windows, coverage and frame provenance use the name
they would for the sealed session:

- **A fresh store** built by the runner: the finished operations of the included actors
  and the rows they name, read in one transaction, written to a new file, and closed. The
  runner checks that the new file has no non-empty log before anything opens it with
  `sealed()`.
- **Finished means a terminal row exists.** An operation that has started and not ended
  is left out with its calls and frames. Without this the projection would emit it as a
  pending step and the window would count it. It is picked up by the first snapshot that
  sees its terminal row.
- **Each included actor's frozen inputs**, prompt and guide. An actor whose frozen
  manifest does not exist yet is not included.
- **The frames** the included operations name, linked or copied and checked against
  their recorded digests. A frame file is not rewritten once it exists.
- **The host's log, as a complete prefix:** cut at the last whole line, and at the last
  included operation.
- **The custody and route metadata** the projection uses to keep secrets out of the
  workspace. That guard runs as it does now, outside the curator's workspace.
- **Not the player's journal.** A restricted window drops it, and its writer does not use
  a write-ahead log, so reading it beside the custodian could delay a commit.
- **Late evidence.** A collection receipt can arrive after an operation's terminal row. A
  step already examined is not examined again; the later evidence is in later snapshots
  for anything that cites it.

### Not yet shown

Nothing here has been tried against a live writer. The first thing
[the reader leaf](https://github.com/CVX-Hull/enactive/issues/837) does is an offline
test with a synthetic writer process: that the read transaction returns a consistent
prefix, how long it holds, and that the writer's quarter-second timeout is not hit.

**The fallback** has its own test, not this one's: the custodian writes a capture at each
actor handoff, inside a stated time bound, and the runner reads only captures. If the
first way fails its test, this page changes before any run.

## Publication, coverage and age

Three things are measured, and each has a named source.

- **Publication time.** The gate tags a version; the tag has no time of its own, and the
  commit's time precedes it. The runner records the wall time at which it first sees the
  tag. That is the publication time.
- **Coverage.** Only an accepted publication carries a `curator-coverage/2` stamp: the
  session, the actor and the last step read. A session that publishes nothing leaves the
  stamp where it was.
- **Lag.** Step numbers are local to an actor and cannot be subtracted across a handoff.
  Lag is counted over the admission's finished steps in order, actors in admission order:
  the number of them after the last covered step. Where no stamp exists yet, or the two
  cannot be compared, the lag is shown as unknown, not as zero.
- **When a step happened.** An operation's recorded wall time is when it started; a
  frame's metadata has when it was received. Time to publication is measured from the
  latter.
- **Order of sighting.** A fact's `seen` is a position, not an age.

The gate is used as it is. The first run is under the current structural contract.

## Failure

- **Publication is atomic for each version.** A session can publish one submission and
  then fail before a later one or before close-out, and the abort record is best effort.
  So the runner keeps the last version it confirmed, and records any publication it
  could not confirm for reconciliation after the admission.
- **Two failures stop it.** After two consecutive failed sessions the runner stops for
  the rest of the admission and records why. Curation resumes between admissions, as
  today.
- **A snapshot that fails is discarded** and tried again at the next poll. One is never
  used partly.
- **What the runner shares with play.** No process, no lock on the repository and no
  place in the input path. It does share the machine's disk, a read connection to the
  session store, and possibly the provider account: the shadow runner can resolve the
  same credential as the campaign, so rate limits may be shared.

## Grooming

Grooming needs the sealed source of the last published admission and refuses a window,
and that stays. A handoff between actors inside an admission triggers no grooming. During
play the runner runs admission sessions only, which may leave facts unfiled. Grooming
runs between admissions, as now.

A live run's sessions and its knowledge repository belong to one world, as the
[field table](general-memory.md) requires of a fact about a world.

## Delivery to a running actor

Delivered knowledge is frozen: package preflight checks the hash of
`delivered-knowledge.json` (`tools/campaign_package.py`), and the driver copies those
bytes into each actor's frozen inputs (`tools/campaign_player.py`).

- **The first live run does not change that.** New versions are published, and the next
  admission's package can carry them. The run measures lag and cost, not uptake inside
  the admission.
- **Delivery inside an admission is a later migration,** and this page does not design
  it. The [context design](player-context.md) already says a difference arrives at the
  next request boundary. Two readers must agree on the version: the host, which builds
  the briefing and reminders, and the application, which answers the player's knowledge
  read and query tools from its own frozen copy. Which version each answers from, and
  when, is decided in [the handoff leaf](https://github.com/CVX-Hull/enactive/issues/838),
  with the frozen-input contract, telemetry, the evaluator's readers and the viewer.

## The spectator view

Two things are shown, from two inputs, and kept apart.

- **What the actor was given:** the actor's frozen delivered version, which
  `harness/viewer/knowledge.py` already projects after verifying its digest.
- **What the curator has published since:** the live coverage and the position play has
  reached. No existing input carries that join; the viewer's curator options accept
  configured files only. The runner writes a small status file with its cursor, the last
  confirmed version and its coverage, and the viewer reads it.

A missing or unknown value is shown as such. The view stays read-only and sends nothing
to the curator.

## What a first live run measures

Decision counts and game time are reported separately; game time barely moves in menus.

- **Lag:** as defined above, when each session starts and ends, with its tail.
- **Time to publication:** from a step's frame to the version that covers it.
- **Backlog:** whether unexamined steps grow across the admission.
- **Cost:** curator dollars per session and per examined step, beside the player's.
- **Snapshots:** how long each read transaction holds, how long staging takes, and
  whether any failed.
- **Player pace:** decisions a minute beside the same figure for named sealed admissions
  of the same player. One admission cannot show that the runner did or did not slow
  play; it can show a large difference.
- **New facts:** how many are published per window, and how many are later superseded or
  retired.

It does not measure whether the knowledge helps the player, and it says nothing by
itself about cutting context: the [price proposal](../acceptance/2026-11-20-live-curator-run-price-proposal-836.md)
says how the observed schedule would be turned into that.

## What this depends on

- [The reader leaf](https://github.com/CVX-Hull/enactive/issues/837) builds the snapshot
  and its test.
- The runner itself is not yet a registered leaf.
- A live run needs the owner's approval of its design, price and envelope
  ([operator permissions](../operator-permissions.md)). Source work stops while a
  deciding actor or the real game is live ([S-AGENT](../standards/agents.md)).
