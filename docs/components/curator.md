---
owner: lead
review_trigger: Responsibility, supported behavior, interfaces or qualification change; a P1 decision under ADR 009
status: active
---

# Curator and trace workbench (ADR 009 P0)

This is shadow infrastructure for [ADR 009](../decisions/009-curated-player.md)'s
curator. It runs only over sealed traces. The running player does not use it, and
nothing in the player, the computer, evaluation or the viewer imports it: the
import contracts in `pyproject.toml` forbid it. The curator itself holds no custody and
no player access, and reads no evaluation records. P0's
[outcome](../acceptance/2026-11-08-adr009-p0.md) is recorded. Nothing is adopted.

## Internal responsibilities

| Part | Owned data and consequence |
| --- | --- |
| [Trace projection](../../harness/trace/projection.py) | `trace-projection/1`: an allowlisted, secret-guarded copy of sealed sessions (frames, steps, received text, handoffs) for a curator workspace. [Design](../design/trace-workbench.md) |
| [Sealed readers](../../harness/trace/stores.py), [memory reader](../../harness/trace/memory_reader.py) | Immutable SQLite opens that refuse a non-empty write-ahead log; a read-only `player-memory/2` reader |
| [Workbench](../../harness/trace/workbench.py), [images](../../harness/trace/images.py) | Steps, frames, region diffs and similar frames, run inside the workspace |
| [Sidecars](../../harness/trace/sidecar.py) | `container-manifest/1` and `container-index/1` beside sealed evidence (`data/containers/`), which is never rewritten |
| [Sandbox](../../harness/curator/sandbox.py) | Default-deny Seatbelt profile and polling supervisor: writes only in the workspace's writable directories, one loopback port, bounded resources. [Research and residual risks](../research-curator-sandbox.md) |
| [Model proxy](../../harness/curator/proxy.py) | Holds the provider key and allowlists requests (Anthropic, OpenAI Responses, OpenRouter). Reserves the worst case, settles at reported usage, and revokes on any surprise |
| [Knowledge repository](../../harness/curator/knowledge.py), [gate](../../harness/curator/gate.py) | One Git repository per game. Only gate v0 commits to it, and it checks form, base version, scope and provenance. [Design](../design/curator-session.md) |
| [Drafts](../../harness/curator/containers.py), [sessions](../../harness/curator/session.py) | The draft lifecycle (open, stale, abandoned, promoted) and one ephemeral sandboxed session per run, with a close-out that never follows a link |
| [Curator host](../../tools/curator_host) (an adapter) | Workspace-only tools, budget phases and a frozen prompt with no game knowledge. [Operations](../operations/curator-hosts.md) |
| [Shadow runner](../../tools/curator_shadow.py), [report](../../tools/curator_shadow_report.py) | Replays the #397 and #372 development lineages (never #382's held-out lineages) under a dollar cap, and derives the measurements |

## Failure, bounds and ownership

- **Close-out and the gate.** A session that breaches a limit, errs or leaves a
  surviving process is sealed `aborted`, and nothing it wrote is gated. The gate
  publishes atomically or not at all.
- **The proxy.** It fails closed: missing usage keeps the whole reservation, and a
  charge above its reservation revokes the session.
- **Knowledge and records.** Each run starts its own knowledge repository. Session
  records are kept, and workspaces are deleted.
- **Ownership.** The lead owns this code until P1 assigns it.

## Assurance and evidence

- **Tests:**
  - `tests/test_trace_projection.py` and `tests/test_trace_images.py`;
  - `tests/test_curator_sandbox.py`, the escape suite against the real listeners
    (macOS lane);
  - `tests/test_curator_gate.py` and `tests/test_curator_session.py`;
  - `tests/test_curator_openrouter.py`, `tests/test_curator_host.py` and
    `tests/test_curator_shadow_report.py`.
- **Records:** the [probe baseline](../acceptance/2026-11-08-probe-baseline-449.md),
  the [shadow sessions](../acceptance/2026-11-08-curator-shadow-454.md) and the
  [P0 outcome](../acceptance/2026-11-08-adr009-p0.md).
- **CI coverage:** Linux CI runs the portable tests. The Seatbelt-lane tests, sandbox
  and real-host sessions, run only on macOS.
