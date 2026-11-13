---
owner: lead
review_trigger: Responsibility, supported behavior, interfaces or qualification change; a decision on ADR 009's curator and memory phase
status: active
---

# Curator and trace workbench (ADR 009 baseline and workbench phase)

This is shadow infrastructure for [ADR 009](../decisions/009-curated-player.md)'s
curator. It runs only over sealed traces. The running player does not use it, and
nothing in the player, the computer, evaluation or the viewer imports it: the
import contracts in `pyproject.toml` forbid it. The curator itself holds no custody and
no player access, and reads no evaluation records. Nothing here is
adopted; the baseline and workbench phase's
[outcome](../acceptance/2026-11-08-adr009-p0.md) is recorded separately.

## Internal responsibilities

| Part | Owned data and consequence |
| --- | --- |
| [Trace projection](../../harness/trace/projection.py) | `trace-projection/1`: an allowlisted, secret-guarded copy of sealed sessions (frames, steps, received text, handoffs) for a curator workspace. [Design](../design/trace-workbench.md) |
| [Sealed readers](../../harness/trace/stores.py), [memory reader](../../harness/trace/memory_reader.py) | Immutable SQLite opens that refuse a non-empty write-ahead log; a read-only `player-memory/2` reader |
| [Workbench](../../harness/trace/workbench.py), [images](../../harness/trace/images.py) | Steps, frames, region diffs and similar frames, run inside the workspace |
| [Sidecars](../../harness/trace/sidecar.py) | `container-manifest/1` and `container-index/1` beside sealed evidence (`data/containers/`), which is never rewritten |
| [Sandbox](../../harness/curator/sandbox.py) | Default-deny Seatbelt profile and polling supervisor: writes only in the workspace's writable directories, one loopback port, and bounded memory, processes, time and size of the session's own files. It does not watch or protect the rest of the disk ([what is bounded](../operations/curator-hosts.md#what-the-sandbox-bounds)). [Research and residual risks](../research-curator-sandbox.md) |
| [Model proxy](../../harness/curator/proxy.py) | Holds the provider key and allowlists requests through a provider-neutral `Provider` value. Reserves the worst case, settles at reported usage, and revokes on any surprise |
| [Providers](../../tools/curator_host/providers.py) (an adapter) | The concrete `Provider` values (Anthropic messages, OpenRouter chat completions): routes, key header, allowlists, extra refusals, forwarded headers and how usage becomes dollars. Provider and model names stay here |
| [Knowledge repository](../../harness/curator/knowledge.py), [gate](../../harness/curator/gate.py) | One Git repository per game. Only gate v0 commits to it, and it checks form, base version, scope and provenance. [Design](../design/curator-session.md) |
| [Drafts](../../harness/curator/containers.py), [sessions](../../harness/curator/session.py) | The draft lifecycle (open, stale, abandoned, promoted) and one ephemeral sandboxed session per run, with a close-out that never follows a link |
| [Curator host](../../tools/curator_host) (an adapter) | Workspace-only tools, budget phases and a frozen prompt with no game knowledge. [Operations](../operations/curator-hosts.md) |
| [Shadow runner](../../tools/curator_host/shadow.py) | Replays the #397 and #372 development lineages (never #382's held-out lineages) under a dollar cap |

## Failure, bounds and ownership

- **Close-out and the gate.** Execution failure, unknown cleanup or surviving processes
  prevents gating. Handled failures record an abort where writable; a later close-out error
  cannot undo an earlier atomic publication. Each gate publishes atomically or not at all.
- **The proxy.** It fails closed: missing usage keeps the whole reservation, and a
  charge above its reservation revokes the session. Malformed/unrepresentable accounting
  cannot release a reservation and leave admission usable. The runner closes admission
  separately from incident revocation, boundedly awaits settlement and ledger receipts,
  and stops on explicit unsettled exposure; a clean host exit alone is insufficient.
  [Shutdown receipts and limits](../operations/curator-hosts.md#pi-curator-host-the-shadow-session-host)
  distinguish a spent snapshot from a final charge. It also sets one session-affinity
  header per session. Prompt caching depends instead on the host keeping each budget note
  where it was first sent; a note rewritten at the tail defeats the cache
  ([#489 record](../acceptance/2026-11-08-context-stability-489.md#follow-up-the-cause-found)).
- **Knowledge and records.** Each run starts its own knowledge repository. Session
  records are kept, and workspaces are deleted.
- **Ownership.** The lead owns this code until the curator and memory phase assigns it.

## Assurance and evidence

- **Tests:**
  - `tests/test_trace_projection.py` and `tests/test_trace_images.py`;
  - `tests/test_curator_sandbox.py`, the escape suite against the real listeners
    (macOS lane);
  - `tests/test_curator_gate.py` and `tests/test_curator_session.py`;
  - `tests/test_curator_openrouter.py` and `tests/test_curator_host.py`.
- **Records:** the [probe baseline](../acceptance/2026-11-08-probe-baseline-449.md),
  the [shadow sessions](../acceptance/2026-11-08-curator-shadow-454.md), the
  [baseline and workbench phase outcome](../acceptance/2026-11-08-adr009-p0.md) and the
  curator memory study's
  [completion and registered no-go](../acceptance/2026-11-12-p1-descriptive-completion-178.md).
- **Standing:** the curator stays gated and does not run in live play. Any renewed
  claim that it benefits play needs a fresh written protocol and an owner decision
  ([completion record](../acceptance/2026-11-12-p1-descriptive-completion-178.md)). The
  owner kept it as the writer of the knowledge store
  ([owner decision log](../decisions/owner-decisions.md)); how its knowledge reaches
  the player is tracked in [#591](https://github.com/CVX-Hull/enactive/issues/591).
- **CI coverage:** Linux CI runs the portable tests. The Seatbelt-lane tests, sandbox
  and real-host sessions, run only on macOS.
