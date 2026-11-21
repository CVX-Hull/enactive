---
owner: lead
review_trigger: Curator trace access, session isolation, publication, restore or runner changes
status: active
---

# Curator and trace workbench

The curator reads projected traces and holds no custody or direct player access.
The player and computer do not import curator code. The runner supports windowed
sessions beside an admission. Its behavior in real play remains unverified. Evidence
comes from offline tests and the [stand-in run](../acceptance/2026-11-20-live-curator-stand-in-run-851.md).
Publications during an admission leave the running actor on its
[frozen knowledge export](../contracts/player-host.md#delivered-knowledge-and-recall).

## Internal responsibilities

| Part | Owned data and consequence |
| --- | --- |
| [Trace projection](../../harness/trace/projection.py) | `trace-projection/3`: an allowlisted, secret-guarded copy of sealed sessions (frames, steps, received text, handoffs) for a curator workspace. [Projection and evidence readers](#projection-and-evidence-readers) |
| [Sealed readers](../../harness/trace/stores.py), [memory reader](../../harness/trace/memory_reader.py) | Immutable SQLite opens that refuse a non-empty write-ahead log; a read-only current journal reader and explicit data-only historical readers |
| [Workbench](../../harness/trace/workbench.py), [images](../../harness/trace/images.py) | Read-only JSON lines from the [workbench commands](#workbench-and-sidecars) |
| [Sidecars](../../harness/trace/sidecar.py) | `container-manifest/1` and `container-index/1` beside sealed evidence (`data/containers/`), which is never rewritten |
| [Sandbox](../../harness/curator/sandbox.py) | Default-deny Seatbelt profile and polling supervisor: writes only in the workspace's writable directories, one loopback port, and bounded memory, processes, time and size of the session's own files. It does not watch or protect the rest of the disk ([what is bounded](../operations/curator-hosts.md#what-the-sandbox-bounds)). [Research and residual risks](../research-curator-sandbox.md) |
| [Model proxy](../../harness/curator/proxy.py) | Holds the provider key and allowlists requests through a provider-neutral `Provider` value. Reserves the worst case, settles at reported usage, and revokes on any surprise |
| [Providers](../../tools/curator_host/providers.py) (an adapter) | Model service adapters define routes, key and forwarding headers, request validation and conversion of reported usage to dollars. Provider and model identities stay in the curator host's adapters; the proxy receives them from its caller. |
| [Knowledge repository](../../harness/curator/knowledge.py), [gate](../../harness/curator/gate.py) | One Git repository per game. The gate writes the repository through validated submissions, under the [session publication rules](../design/curator-session.md#gate-v0), and through the [operator restore](../design/curator-session.md#minimum-first-slice-operator-restore) of a compatible snapshot. |
| [Windows](../../harness/curator/window.py) | A range of one actor's steps as the whole of a session's trace, and the coverage stamp the gate publishes with each version. Decision-window and citations-only views remove the entire journal JSON; only filtered in-window calls can carry hints. [Design](../design/curator-session.md#windows-of-decisions-and-the-coverage-stamp) |
| [Drafts](../../harness/curator/containers.py), [sessions](../../harness/curator/session.py) | Draft lifecycle (open, stale, abandoned, promoted) and ephemeral sandboxed sessions whose close-out never follows a link |
| [Curator host](../../tools/curator_host) (an adapter) | Workspace-only tools, budget phases and a frozen prompt with no game knowledge. [Operations](../operations/curator-hosts.md) |
| [Shadow runner](../../tools/curator_host/shadow.py) | Replays the seven-day development lineage (#397) and the development-loop sample (#372) under a dollar cap. The runner refuses the held-out lineages (#382, #522) by name. The lead knows #382's from operating them and reviewing admission summaries. The [curator memory study](../design/curator-memory-study-protocol-revised.md#limitations) records that exposure. |
| [Curator runner](../../harness/curator/runner.py) | Window triggers, the durable record of examined ranges, publication watching, covered prefix and lag, stops, and status. [Runner windows](#runner-windows) |
| [Runner process](../../tools/curator_host/live_runner.py) (an adapter) | The process the guardian starts with `--curator-runner`: its `curator-runner-config/1` file, sessions through the shadow runner's proxy under the runner's cap, its own knowledge repository, and signal handling |

## Projection and evidence readers

The workbench and the curator window require the same [projection format](../contracts/measurement-tools.md#trace-projection).
A sealed session and a closed staged snapshot use the same immutable reader.
The projection keeps evidence the actor could see or produce, with the public
identifiers needed to cite it. Raw custody, route, configuration and process files,
custodian and viewer records, receipts, raw host logs, run manifests and the raw
session database stay outside the projection.

The projector checks frame identifiers against the session and verifies PNG bytes
against sealed SHA-256 metadata before copying. It omits an unavailable, linked or
unindexed frame from its step. A digest mismatch, foreign frame identifier, unreadable
store or malformed host event fails projection. It skips linked actor directories
and requires a frozen manifest in each included actor directory. Optional label
evidence has its own [diagnostics](../contracts/measurement-tools.md#trace-projection).

Reports, handoffs, records and error reasons can contain free text. The projector
builds a sibling directory and scans its files for known custody and route values
from readable actor configuration and process files, and for key-like patterns.
Public session and actor IDs remain available for citations. Only a completed
projection that passes the scan is renamed into place. The [design rationale](../design/trace-workbench.md)
explains the choice of projection and read-only tools.

The [historical memory reader](../../harness/trace/memory_reader.py) reads sealed
`player-memory/2` records with supports and sources, programs and source metadata.
The projection can instead include the current public journal without image bytes.
The [sealed reader](../../harness/trace/stores.py) refuses a nonempty write-ahead log
because immutable mode would ignore it. [Reader evidence](../acceptance/2026-11-09-moved-results.md#trace-workbench-evidence-reader)

## Workbench and sidecars

The workbench emits JSON lines. `steps` filters by actor, sequence range and kind,
`frames` gives source IDs and paths for a range, and `tools` lists calls, optionally
by tool. `diff` measures per-cell change on a grid. `similar` ranks other frames by
64-bit difference-hash distance. A threshold for screen equivalence needs calibration
on labelled pairs. [Hash and secret-scan measurements](../acceptance/2026-11-08-moved-measurements.md#trace-workbench-secret-scan-and-perceptual-hashes)

The sidecar manifest describes actor sessions, curator sessions, submissions and drafts
by identity, kind, owner role, inputs, pinned versions, budgets, lifecycle, provenance
and retention. The actor-session index records frozen prompt and context digests
beside the sealed evidence and excludes custody and route files from those input
digests. [Tracked sidecar example](../../data/containers/397-seven-day.json)

## Runner windows

The guardian starts the runner alongside the custodian. Its exit leaves play running.
The [launch](../operations/campaign-supervision.md#freeze-launch-and-inspect) and [cleanup](../operations/campaign-supervision.md#failure-and-owned-cleanup) procedure
owns process setup and termination. The runner handles cancellation by interrupting
the session and closing the proxy and any active read. Input revocation proceeds independently.

The runner stages at most one snapshot per poll. In admission order, it selects the
oldest contiguous finished operations beyond one actor's examined cursor. Defaults
are a 15-second poll, a 20-step trigger and a 40-step ceiling. The ceiling also applies
at handoff. An ended actor's verified nonempty tail can run below the trigger before
the successor's range. A repository lock admits one session at a time. After a lock
refusal the next poll selects again. Backlog never blocks player input.

A sealed session advances the cursor on acceptance, no submission, rejection or an
unknown verdict. Rejection and an unknown verdict count as failures. An aborted or
interrupted session leaves the cursor in place. The [examined and publication records](../contracts/measurement-tools.md#runner-records-and-schedule-replay)
keep examination separate from confirmed coverage.

### Staging a growing trace

The [snapshot reader](../../harness/trace/snapshot.py) takes a shared read lock,
checks the closing marker and collects rows from the live write-ahead-log store in
one bounded read transaction. It closes the cursors and connection before releasing
the lock. After revoking input the custodian marks the store as closing and waits
up to the read bound for an admitted reader. Reads add disk work and can delay
checkpointing. An overrun can leave a log the sealed reader refuses.

The staged directory keeps the session name. Each included actor contributes its
longest finished prefix in creation-time and operation-ID order. Each operation needs
a terminal row. Until the actor ends it also needs a matching host result by operation
ID and settled native receipts or collections. Staging keeps frozen actor inputs,
whole host-log lines, verified frames, metadata for the secret scan and the package
and supervisor launch records when present. The window excludes the journal.
Clock reversals, wall-time ties and late frame associations can affect comparisons
with later snapshots. Failed snapshots are discarded, and a poll releases its staged copy.

### Publication and coverage

The runner watches version tags before, during and after a session. Tags present
on its first successful look form the baseline. For a newly seen tag, publication
falls between the start of the last look without it and the end of the first look
with it. Confirmation requires a seen tag, a recorded publication verdict and a
stamp matching the session's window. A session can publish and subsequently fail.
Its confirmed publications still count, and unresolved publications are recorded for
reconciliation. A stamp describes one window. The covered prefix joins contiguous
confirmed ranges from the first step and crosses actors only when the ended actor's
final step is covered.

Lag counts finished operations after that prefix. The runner locates its endpoint
by operation ID in the latest successful snapshot, across actors. An unplaceable
endpoint leaves lag unknown. At the first restore, the runner counts versions only through the restore target (through
the version preceding the restore if the target is unknown). Coverage beyond that
point and lag are unknown. The [spectator status contract](../contracts/spectator-view.md#curator-runner-status)
gives the read position, backlog, unexamined ranges and status fields. Later steps
must be counted from the sealed trace. The [schedule replay](../contracts/measurement-tools.md#runner-records-and-schedule-replay)
maps this prefix to player requests for the [proposed context cut](../design/coverage-gated-context-cut.md).

The live runner runs admission sessions only, against its configured knowledge
repository. Handoff does not start grooming. If nothing is published, grooming still
uses the last published admission, if one exists, under the [grooming rules](../design/curator-session.md#admission-and-grooming).
The [first-run rationale](../design/live-curator-integration.md#what-a-first-live-run-measures)
explains which lag, cost, staging and player-pace questions require real play.

## Failure, bounds and ownership

- **Close-out and the gate.** Execution failure, unknown cleanup or surviving processes
  prevents gating. Handled failures record an abort where writable; a later close-out error
  cannot undo an earlier atomic publication. Each gate publishes atomically or not at all.
- **Runner failure.** Two consecutive failed sessions or three consecutive failed or over-bound snapshots stop the runner. A missing store retries, a closing store ends the runner, and other read refusals stop it. Cap exhaustion, a refused reservation, proxy revocation, unsettled accounting or unconfirmed host cleanup also stop it. [Runner process](../../tools/curator_host/live_runner.py) and [guardian cleanup](../operations/campaign-supervision.md#failure-and-owned-cleanup)
- **The proxy.** Missing usage keeps the reservation except on a fully read HTTP
  refusal with no usage. An over-reservation charge revokes the session. The runner
  stops on unsettled exposure. See [accounting and shutdown](../operations/curator-hosts.md#pi-curator-host-the-shadow-session-host).
- **Knowledge and records.** Close-out retains session records and removes workspaces.
- **Ownership.** The lead owns this code.

## Assurance and evidence

- **Tests:** The sandbox escape suite checks the real listeners on macOS. The
  [documentation map](../documentation.md#from-code-to-its-documents) lists the suites.
- **Records:** the [probe baseline](../acceptance/2026-11-08-probe-baseline-449.md),
  the [shadow sessions](../acceptance/2026-11-08-curator-shadow-454.md), the
  [baseline and workbench outcome](../acceptance/2026-11-08-adr009-p0.md), the
  [prompt-cache stability record (#489)](../acceptance/2026-11-08-context-stability-489.md#follow-up-the-cause-found)
  and the curator memory study's
  [completion and registered no-go](../acceptance/2026-11-12-p1-descriptive-completion-178.md).
- **Standing:** Real play with the runner requires owner approval under the
  [live-run decision](../decisions/owner-decisions.md#one-paid-live-curator-run).
  Curator ownership of the store follows the
  [“Let's keep the dedicated curator” decision](../decisions/owner-decisions.md#curator-keeps-writing-memory).
  Any claim of benefit needs a fresh prospective protocol and owner decision and
  rests on campaign outcomes under the
  [“Live run, then campaigns” decision](../decisions/owner-decisions.md#memory-benefit-measured-in-campaigns).
- **CI coverage:** Linux CI runs the portable tests. The Seatbelt-lane tests, sandbox
  and real-host sessions, run only on macOS.

## Facts, articles and grooming

The [session design](../design/curator-session.md#submissions) states the record and
operation shapes the [gate](../../harness/curator/gate.py) accepts, the
[frozen submission instructions](../../tools/curator_host/prompt.md#submission-contract)
give the whole `curator-submission/1` envelope, and
[world-scoped memory](../design/world-scoped-memory.md#the-format-curator-fact3) owns the
`curator-fact/3` field meanings.

The [session design](../design/curator-session.md#admission-and-grooming) owns what
admission and grooming sessions read and do, their briefs and publication rules, and
the [operator restore](../design/curator-session.md#minimum-first-slice-operator-restore)
of a compatible snapshot. [Host operations](../operations/curator-hosts.md) owns adapter
configuration and the zero-spend stand-in lane.
