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
| [Trace projection](../../harness/trace/projection.py) | `trace-projection/3`: an allowlisted, secret-guarded copy of sealed sessions (frames, steps, received text, handoffs) for a curator workspace. [Design](../design/trace-workbench.md) |
| [Sealed readers](../../harness/trace/stores.py), [memory reader](../../harness/trace/memory_reader.py) | Immutable SQLite opens that refuse a non-empty write-ahead log; a read-only current journal reader and explicit data-only historical readers |
| [Workbench](../../harness/trace/workbench.py), [images](../../harness/trace/images.py) | Steps, frames, region diffs and similar frames, run inside the workspace |
| [Sidecars](../../harness/trace/sidecar.py) | `container-manifest/1` and `container-index/1` beside sealed evidence (`data/containers/`), which is never rewritten |
| [Sandbox](../../harness/curator/sandbox.py) | Default-deny Seatbelt profile and polling supervisor: writes only in the workspace's writable directories, one loopback port, and bounded memory, processes, time and size of the session's own files. It does not watch or protect the rest of the disk ([what is bounded](../operations/curator-hosts.md#what-the-sandbox-bounds)). [Research and residual risks](../research-curator-sandbox.md) |
| [Model proxy](../../harness/curator/proxy.py) | Holds the provider key and allowlists requests through a provider-neutral `Provider` value. Reserves the worst case, settles at reported usage, and revokes on any surprise |
| [Providers](../../tools/curator_host/providers.py) (an adapter) | Model service adapters define routes, key and forwarding headers, request validation and conversion of reported usage to dollars. Provider and model identities stay in the curator host's adapters; the proxy receives them from its caller. |
| [Knowledge repository](../../harness/curator/knowledge.py), [gate](../../harness/curator/gate.py) | One Git repository per game. The gate writes the repository through validated submissions, under the [session publication rules](../design/curator-session.md#gate-v0), and through the [operator restore](../design/curator-session.md#minimum-first-slice-operator-restore) of a compatible snapshot. |
| [Windows](../../harness/curator/window.py) | A range of one actor's steps as the whole of a session's trace, and the coverage stamp the gate publishes with each version. Decision-window and citations-only views remove the entire journal JSON; only filtered in-window calls can carry hints. [Design](../design/curator-session.md#windows-of-decisions-and-the-coverage-stamp) |
| [Drafts](../../harness/curator/containers.py), [sessions](../../harness/curator/session.py) | Draft lifecycle (open, stale, abandoned, promoted) and ephemeral sandboxed sessions whose close-out never follows a link |
| [Curator host](../../tools/curator_host) (an adapter) | Workspace-only tools, budget phases and a frozen prompt with no game knowledge. [Operations](../operations/curator-hosts.md) |
| [Shadow runner](../../tools/curator_host/shadow.py) | Replays the seven-day development lineage (#397) and the development-loop sample (#372) under a dollar cap. The runner refuses the held-out lineages (#382, #522) by name. The lead knows #382's from operating them and reviewing admission summaries. The [curator memory study](../design/p1-study-3.md#limitations) records that exposure. |
| [Curator runner](../../harness/curator/runner.py) | Window triggers, the durable record of examined ranges, publication watching, covered prefix and lag, stops, and status. [Design](../design/live-curator-integration.md) |
| [Runner process](../../tools/curator_host/live_runner.py) (an adapter) | The process the guardian starts with `--curator-runner`: its `curator-runner-config/1` file, sessions through the shadow runner's proxy under the runner's cap, its own knowledge repository, and signal handling |

The runner stages at most one temporary snapshot per poll in a bounded read of the live
store, uses one actor's finished steps when a session is due, and discards the snapshot
when the poll ends ([snapshot reader](../../harness/trace/snapshot.py)). It tracks
examined ranges separately from coverage confirmed by publication and reports steps
after its last read as unknown ([runner source](../../harness/curator/runner.py)).

## Failure, bounds and ownership

- **Close-out and the gate.** Execution failure, unknown cleanup or surviving processes
  prevents gating. Handled failures record an abort where writable; a later close-out error
  cannot undo an earlier atomic publication. Each gate publishes atomically or not at all.
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
[general memory](../design/general-memory.md#the-format-curator-fact3) owns the
`curator-fact/3` field meanings.

The [session design](../design/curator-session.md#admission-and-grooming) owns what
admission and grooming sessions read and do, their briefs and publication rules, and
the [operator restore](../design/curator-session.md#minimum-first-slice-operator-restore)
of a compatible snapshot. [Host operations](../operations/curator-hosts.md) owns adapter
configuration and the zero-spend stand-in lane.
