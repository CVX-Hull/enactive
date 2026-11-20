---
owner: lead
status: proposed
date: '2026-11-20'
scope: 'How the curator runs during an ongoing admission: who starts a session and when, how a trace that is still being written becomes readable, publication and coverage, failure, grooming, delivery, the spectator view and the measures of a first bounded live run'
review_trigger: The live trace reader is built, a live run is priced or approved, or the delivery contract changes
---

# Running the curator during play

## At a glance

No curator runs during play today. Sessions read only sealed traces, and delivered
knowledge is frozen into a package before the admission starts. This page designs the
smallest change that lets a curator follow an admission as it is played, so that its lag,
cost and effect can be measured before anything depends on them.

**Designed, not built.** Nothing here is implemented and no run is approved. The
[curator session design](curator-session.md) owns sessions, the gate and the store; this
page owns only what is new for a session that runs beside play. A first live run is
priced in a [dated proposal](../acceptance/2026-11-20-live-curator-run-price-proposal-836.md).

The design in one paragraph: a **curator runner**, started by the guardian beside the
custodian, takes a **consistent copy** of the growing session store, runs an ordinary
windowed admission session over it, and publishes through the unchanged gate. Play never
waits for it. In the first live run the running actor does not receive the new
knowledge: the run measures how far curation trails play, not what the player does with
it.

## Who starts a session, and when

The guardian (`tools/campaign_supervision.py`) already starts the custodian, the viewer
and the gateway as separate children. The curator runner is one more child of the
guardian.

- **It is not part of the custodian.** The custodian (`tools/campaign_run.py`) holds
  input custody and the player's provider key, and its loop is the only thing between the
  player host and the game. Nothing is added to that loop.
- **It has its own key and its own cap.** Curator requests go through the curator proxy,
  which already keeps its own ledger. The runner's dollar cap is separate from the
  package's.
- **The trigger is steps not yet covered.** The runner polls on a wall-clock interval,
  takes a copy when the copy would add at least *N* finished steps beyond the last
  coverage stamp, and runs one session over those steps. The proposed *N* is 20, the
  window the [price pilot](../acceptance/2026-11-13-session-price-pilot.md) measured. It
  is a proposal to be measured, not a finding.
- **Coalescing.** One session runs at a time; the repository lock already refuses a
  second (`harness/curator/session.py`). The runner does not queue windows. When a session
  ends, the next covers every finished step since the stamp, up to a ceiling of 40 steps
  in one window.
- **Backpressure never reaches the player.** If the uncovered steps exceed the ceiling,
  the runner covers the oldest 40 and records the backlog. It does not skip steps and it
  does not slow play.

## How a growing trace becomes readable

This is the central question. The session store is written by the custodian in
write-ahead-log mode with no explicit checkpoint (`harness/computer/store.py`), and every
reader goes through `sealed()` in `harness/trace/stores.py`, which refuses a store whose
log is not empty and opens the rest as immutable. A live store is therefore refused, and
rightly: an immutable read of a file that is changing can be wrong.

Three ways to get a readable trace were compared.

| Way | What it needs | Why it is or is not chosen |
| --- | --- | --- |
| The reader takes a consistent copy with SQLite's online backup | A second, read-only connection to the live store for the length of the copy | **Chosen.** No change to the custodian. The copy has no log, so `sealed()` and the projection read it unchanged |
| The writer checkpoints and copies at set points | New work in the custodian's loop, and a brief hold on its writes | Not chosen: it puts curation's needs inside the process that holds input custody |
| The reader opens the live store as an ordinary log reader | Read connections kept open on the live store | Not chosen: the projection would read a moving store, and the refusal in `sealed()` would have to be weakened for every reader |

**The copy.** The runner opens the live `session.sqlite3` read-only, not immutable, with
a short busy timeout, and backs it up into its own directory under the run,
`curator/snapshots/<ordinal>/`. It copies the player's journal the same way, and links or
copies the frame files under `sources/` that the copied store names; a frame file is
never rewritten once it exists. The result has the layout of a sealed session directory.

**What does not change.** `sealed()` keeps its refusal. Nothing but the runner's copy
step opens the live store, and the projection only ever sees copies.

**What does change.**

- The projection must accept an actor who has not finished: no final report, and
  possibly an operation that has started and not ended. A window ends at the last
  *finished* step. The coverage stamp then names the last step actually read, which is
  what `curator-coverage/2` already means.
- A window may end inside an admission that is still running. The window code already
  clamps to the steps that exist.

**Not yet shown.** Whether the online backup works while the custodian holds the store
open has not been tried; no code here uses it. It is the first thing
[the reader leaf](https://github.com/CVX-Hull/enactive/issues/837) tests, offline, with a
synthetic writer. If it does not hold, the second row of the table is the fallback, and
this page changes before any run.

## Publication and coverage

Three clocks stay separate, and none is new.

- **Publication** is the knowledge version the gate tags, with its wall time.
- **Coverage** is the stamp published with each version: the session, the actor and the
  last step read. Lag is the distance from that step to the step play has reached.
- **Observation order** is each fact's `seen`. It says which sighting is later, not how
  long ago it was.

The gate, its atomic publication and the one-writer lock are unchanged.

## Failure

- A failed, capped or interrupted session leaves the store at its last version. The
  existing close-out seals an `aborted` record and releases the lock.
- The player is unaffected in every case: the runner shares no process, no key and no
  lock with the custodian.
- After two consecutive failed sessions the runner stops for the rest of the admission
  and records why. Curation then resumes between admissions, as today.
- A copy that fails is retried at the next poll. A copy is never used partly.

## Grooming

Grooming needs whole admissions and refuses a window, and that stays. During play the
runner runs admission sessions only, which may leave facts unfiled. Grooming runs between
admissions, over the sealed admission, as it does now.

## Delivery to a running actor

Delivered knowledge is frozen: the package hashes `delivered-knowledge.json`
(`tools/campaign_package.py`), and the driver copies those bytes into each actor's
frozen inputs (`tools/campaign_player.py`). A running actor never sees a newer version.

- **The first live run does not change that.** New versions are published and the next
  admission's package can carry them, as today. The run measures lag and cost. It cannot
  measure uptake inside the admission.
- **Delivery inside an admission is a later migration.** A newer version would reach the
  host as its own labelled message, with its version and coverage in telemetry, and never
  block input. That moves the host, the frozen-input contract, the package binding, the
  evaluator's readers and the viewer together
  ([the handoff leaf](https://github.com/CVX-Hull/enactive/issues/838)). It follows the
  fact schema migration and is shared with the ontology card, so those contracts migrate
  once.

## The spectator view

The viewer already accepts curator results and sessions as read-only inputs, and
`harness/viewer/knowledge.py` projects delivered knowledge. A live run adds one thing a
spectator needs: the lag, shown as the coverage stamp's last step beside the step play
has reached. Candidate, base and target identifiers are added only when something
produces them. The view stays read-only and sends nothing to the curator.

## What a first live run measures

Decision counts and game time are reported separately; game time barely moves in menus.

- **Lag:** the distribution of uncovered steps when each session starts and ends, with
  its tail.
- **Time to publication:** wall time from a step to the version that covers it.
- **Backlog:** whether uncovered steps grow across the admission.
- **Cost:** curator dollars per session and per covered step, beside the player's.
- **Player pace:** decisions a minute, with and without the runner, to show play is not
  slowed.
- **Copies:** how long each copy takes and whether any failed.
- **New facts:** how many are published per window, and how many are later superseded or
  retired.

It does not measure whether the knowledge helps the player, and it says nothing about
cutting context: both wait for delivery inside an admission.

## What this depends on

- [The reader leaf](https://github.com/CVX-Hull/enactive/issues/837) builds the copy and
  the projection of an unfinished actor.
- The runner itself is not yet a registered leaf. It is small once the reader exists: a
  child of the guardian with a poll, the window rule above and a cap.
- A live run needs the owner's approval of its design, price and envelope
  ([operator permissions](../operator-permissions.md)). Source work stops while a
  deciding actor or the real game is live ([S-AGENT](../standards/agents.md)).
