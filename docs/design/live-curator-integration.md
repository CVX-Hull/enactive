---
owner: lead
status: active
scope: 'How the curator runs during an ongoing admission: who starts a session and when, how a trace that is still being written becomes readable, publication and coverage, failure, grooming, delivery, the spectator view and the measures of a first bounded live run'
review_trigger: Live-run evidence changes the reader or runner assumptions, or the delivery contract changes
---

# Running the curator during play

## At a glance

- **Question.** How can a curator follow a running admission, and how far does it
  trail play?
- **Answer.** A runner stages snapshots, curates one actor's window at a time and
  publishes through the gate. The snapshot reader, runner and schedule replay
  operate offline, and delivery within an admission belongs to a separate design.
  [Curator component](../components/curator.md)
- **Unknown.** Lag, cost, snapshot timing and player pace beside a real custodian
  are unmeasured. Curation stays outside the input path and shares disk work.
- **Decisions needed.** None for this design. The paid live run's conditions are in
  the [owner decision log](../decisions/owner-decisions.md#one-paid-live-curator-run).

## Who starts a session, and when

The guardian runs the curator alongside the custodian as an unsupervised child.
The runner's exit does not stop play. The launch configuration and run directory
setup are part of [campaign supervision](../operations/campaign-supervision.md#freeze-launch-and-inspect).

The runner's work ends with the custodian. At cancellation it interrupts the session
and closes the proxy and any read. Input revocation proceeds independently. The
custodian can wait for an admitted read during store close.
[Runner process](../../tools/curator_host/live_runner.py)

### The cursor

The cursor records what the runner has examined, actor by actor in admission order.
An accepted, empty, rejected or unconfirmed session advances it. An aborted or
interrupted session leaves it at the previous position. Rejected and unconfirmed
outcomes count as failures.

The durable `curator-runner/examined.jsonl` records each window's start and end,
operation endpoints, outcome and coverage at those times. A rejected or empty
window advances the cursor without contributing to confirmed coverage.
[Runner file formats and outcomes](../../harness/curator/runner.py)

### The window

A window is one contiguous range of one actor's finished operations. The runner
stages one snapshot per poll and chooses the oldest range beyond the cursor that
meets the configured trigger. The ceiling applies at a handoff too. An ended actor's
verified, nonempty tail can run below the trigger, and a successor's range follows it.
The defaults are a 15-second poll, 20 steps to trigger and a ceiling of 40 steps.
[Runner settings and selection](../../harness/curator/runner.py)

The repository lock admits one session at a time. On refusal the runner recomputes
the range at its next poll. Backlog is recorded without blocking player input.
The [context cut design](player-context.md#3-one-cut-tied-to-what-the-store-covers)
depends on confirmed coverage. The session trigger depends on examined steps.

## How a growing trace becomes readable

The custodian appends to a SQLite store in write-ahead-log mode.
[`sealed()`](../../harness/trace/stores.py) opens a stable store in immutable mode and
refuses a non-empty log. A short live read stages a separate, stable store for that
reader.

| Architecture | Consequence |
| --- | --- |
| Copy finished rows in one bounded read transaction | The projection uses its sealed reader. The transaction holds the read only while collecting rows. |
| Read the live store in the projection | The read transaction spans the projection, and the offline readers share an entry point that accepts a live store. |
| Have the custodian yield a stable copy at each window | The input custodian takes on snapshot work. This is the fallback if staging fails its live test. |
| Back up the whole database online | The busy timeout does not bound the backup's duration. Concurrent writes can restart it, and it copies rows outside the selected prefix. |

A live read adds disk work and can hold back checkpoint progress. The runner admits a
read under the shared lock, checks the closing marker and closes its cursors and
connection before releasing the lock. After revoking input, the custodian marks the
store as closing and waits up to the read bound for an admitted reader before closing
its connection. A reader that overruns or leaves the connection open can leave a log
that the sealed reader refuses.
[Read admission, bounds and staging](../../harness/trace/snapshot.py) and
[custodian close-out](../../tools/campaign_run.py) define the protocol.

### The snapshot

The staged directory keeps the run's session name. Its fresh store carries each
included actor's finished prefix, which keeps step positions comparable to the
sealed trace. The cutoff joins terminal rows and matching host results by operation
identity. A pending result or collection keeps an operation out until the missing
record arrives or the actor has ended. Staging also keeps frozen actor inputs,
verified frame bytes, whole host-log lines and metadata for the projection's secret
guard. The window excludes the player's journal.
[Snapshot cutoff and staged files](../../harness/trace/snapshot.py)

The snapshot stages the campaign manifest and supervisor launch record when present.
The current `campaign-run/10` manifest has no `world` label. The
[trace projection](../../harness/trace/projection.py) verifies lineage and admission
position by checking both records against the staged store's session ID and checking
the manifest bytes against the supervisor's recorded digest. The
[world-scope design](general-memory.md#provenance-and-the-checks-it-allows) specifies
how publication uses a future manifest's `world` label.

Step numbering depends on wall time and operation identity. A backward clock step,
equal wall times or a late frame association can affect comparisons with a later
projection. The [stand-in run](../acceptance/2026-11-20-live-curator-stand-in-run-851.md)
supplies offline evidence for staging and runner timing.

## Publication, coverage and age

- **Publication time.** The runner watches tags before, during and after the session.
  A version is published between the beginning of the last look without its tag and
  the end of the first look with it. Versions already seen on the first look are the
  baseline. [Version records](../../harness/curator/runner.py)
- **Confirmed coverage.** A version is confirmed when the runner sees its tag, an
  examined session reports it published and its stamp matches that session's window.
  The covered prefix joins only confirmed ranges from the first step, in admission
  order. It reaches the next actor only after the ended actor's final step is covered.
  A current stamp describes one window. An examined window can still leave a gap.
- **Restore.** Only versions up through the restored version count. Coverage beyond
  that point and lag are unknown.
- **Lag.** The runner counts finished operations after the covered prefix, locating
  the endpoint by operation identity in the latest snapshot. The endpoint's ordinal
  can span actors. If the snapshot cannot place it, lag is unknown.
- **Age.** Match the evaluator's operations by identity, and read a frame's
  `received_wall` from the snapshot store to measure age. A step with no frame has no
  frame age. The fact's `seen` records sighting order.

## Replaying a recorded schedule

The schedule replays a sealed run's recorded covered prefix against player requests.
The replay joins operations in the runner's record to the host log, without reading
the session store. A request is covered when the prefix includes its last operation.
Retries count as one request. Earlier actors' requests are covered when the prefix
reaches a later actor. A change with an unplaceable operation is omitted. An
unplaceable restore clears coverage.

An advance applies at the first request starting after the row that shows it.
That can be later than publication. A restore is timed at the preceding row and
applies from that time. A request without a start time inherits the previous
request's coverage, or starts with none for its actor.

`python -m tools.memory_screen_checks schedule RUN` writes
`curator-coverage-schedule/1` from the poll rows and terminal status.
`cut RUN --coverage schedule --schedule FILE` replays it for that run. The
[schedule implementation](../../tools/memory_screen_checks.py) owns the file shape
and refusal rules.

## Failure

A session can publish a version and fail later. The runner retains the last confirmed
version and records publications that need reconciliation after the admission. A
failed snapshot is discarded. The [runner's stop and outcome rules](../../harness/curator/runner.py)
cover repeated failures, read refusals, interruption, spend and cleanup.

An outright kill can leave a sandboxed host outside the guardian's process groups.
The host's session token cannot spend once the runner's proxy is gone.
[Campaign cleanup](../operations/campaign-supervision.md#failure-and-owned-cleanup)
covers the guardian's owned processes and snapshot cleanup.

## Grooming

The live runner uses admission sessions and a repository of its own for the run's
world. Handoffs do not trigger grooming. The
[session publication rules](curator-session.md#admission-and-grooming) govern when
grooming runs and which sealed source it reads. If the live admission published
nothing, the last published admission is still the one before it, and grooming does
not examine what the runner missed.

## Delivery to a running actor

The first live run uses each actor's frozen knowledge. A later admission can receive
newly published versions through its package. The
[within-admission delivery migration (#838)](https://github.com/CVX-Hull/enactive/issues/838)
selects one recorded version at a request boundary. The briefing, recall and
knowledge tools use that version for the request. The
[context design](player-context.md#the-delivery-boundary) owns the current delivery
interfaces.

## The spectator view

The viewer keeps the actor's frozen delivered version and the curator's recorded
progress distinct. The [status contract](../contracts/evaluation.md#curator-runner-status)
defines the viewer fields. The [runner](../../harness/curator/runner.py) owns
`curator-runner/status.json`, its fields and its write cadence.

Lag, backlog and terminal unexamined ranges count only what the last successful read
saw. `as_of` identifies that read's position and wall time. `after_last_read` is
always `unknown` in runner status. The sealed trace supplies the later steps after
the admission ends.

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
