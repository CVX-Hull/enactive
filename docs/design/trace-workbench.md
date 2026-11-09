---
owner: lead
status: active
date: 2026-11-08
scope: 'Trace projection, sealed-memory evidence reader, workbench commands and sidecar container manifests over sealed traces (ADR 009 D6 and D17; #452)'
review_trigger: A change to what a trace projection may contain, to the session or memory store formats, to the workbench commands, or to the container manifest shape
---

# Trace projection and workbench

The curator, the probe protocol and the spectator need sealed traces in a safe, uniform
shape ([ADR 009](../decisions/009-curated-player.md#workbench-d6)). A session directory
mixes what the actor saw and did with custody tokens, routes, host configuration and
process records. The game-neutral package [`harness/trace`](../../harness/trace) builds
an allowlisted projection, reads sealed memory stores as evidence, provides workbench
commands and writes sidecar manifests. It imports nothing from the player, the computer,
evaluation or the curator, and it opens no network or process.

## Projection

[`projection.project`](../../harness/trace/projection.py) writes `trace-projection/1`.

**What it contains:**
- **Frames**, copied after their SHA-256 matches the sealed metadata. Frame IDs must
  belong to the session.
- **Steps per actor**: operation kind, input actions with named fields only (including
  wait durations), status and frame.
- **Tool calls**: the tool name, arguments allowlisted per tool, and the outcome's named
  fields. Refused and unfinished calls are included and marked.
- **What the actor was given and wrote**: its prompt, its working guide and its final
  report.
- **Sealed handoff packets.**
- **The memory store**, read through the evidence reader.

The manifest records a digest for every file, what is never projected, and what is
dropped.

**Fail-closed secret guard.** Some channels are free text an actor or service wrote:
reports, handoff summaries and knowledge, memory records and error reasons. No allowlist
can vet free text. So every projection is built in a sibling directory and scanned before
it is renamed into place. The scan looks for every credential- or address-like value in the
sessions' custody, route, MCP and process files, and for key-like patterns. On any hit, or
any other failure, nothing is published and no partial directory remains. Session and
actor IDs are excluded from the scan because the projection keeps them by design.

**Refused inputs.** A sealed input that is damaged or ambiguous is refused, not guessed.
That covers symbolic links, unreadable events or stores, an un-checkpointed write-ahead
log, frame IDs from another session, and actors without frozen inputs.

**What it never contains:** `actor.json` (custody token), `route.json` (provider route),
MCP and host configuration, process records, custodian, viewer and watch files, receipts,
raw `host.jsonl` and the raw session store. Session, actor and operation IDs stay, because
they grant nothing and are how frames are cited.

**Tests** ([`tests/test_trace_projection.py`](../../tests/test_trace_projection.py)):
- **Synthetic fixture.** It plants a token, a route key and the custodian URL in
  structured places a careless copy would carry: argument extras, result extras, unknown
  operation fields, process records and custodian output. None reaches the projection.
- **Guard.** Separate cases plant a secret in each free-text channel: the final report,
  handoff knowledge and summary, a memory record, an error reason, and a bearer string.
  Each projection is refused and leaves nothing behind.
- **Integrity.** A frame whose bytes differ from its sealed hash is refused.
- **Real lineages.** The sealed #397 lineage and the six sampled #372 runs are
  projected and scanned for every custody token, custodian URL and route value of
  their actors, plus key-like patterns ([result](../acceptance/2026-11-08-moved-measurements.md#trace-workbench-secret-scan-and-perceptual-hashes)).
  The tests skip when the evidence store is absent;
  `ENACTIVE_EVIDENCE_ROOT` points a worktree at a checkout's store.

The #382 traces are held out and are not projected. #452's secret-scan acceptance
covers #397 and #372 instead.

## Evidence reader

[`memory_reader.read`](../../harness/trace/memory_reader.py) reads a sealed
`player-memory/2` store as data: records with their supports and sources, programs, and
source metadata. It is not the player's memory contract. Sealed stores stay readable after
the live contract migrates. The reader accepts only `player-memory/2` and never writes
beside the store: it opens SQLite immutable, and a test proves this on a write-ahead-log
store. Immutable mode would silently ignore an un-checkpointed log, so a store with a
non-empty `-wal` is refused rather than read incomplete. What it read from the sealed #397
store is in [the moved results](../acceptance/2026-11-09-moved-results.md#trace-workbench-evidence-reader).

## Workbench

`python -m harness.trace.workbench` prints JSON lines:

| Command | Does |
| --- | --- |
| `steps` | An actor's operations by sequence range or kind |
| `frames` | Frame IDs and paths for a sequence range |
| `tools` | Tool calls, optionally of one tool |
| `diff` | Per-cell change between two frames on a grid ([`images.region_diff`](../../harness/trace/images.py)) |
| `similar` | Nearest frames by 64-bit difference hash |

**Perceptual-hash reliability is measured, not assumed** (ADR 009 research question R8;
its synthesis is #448).
On the sealed #397 frames, consecutive and random pairs' difference-hash distances overlap
heavily, so a difference hash separates "next frame" from "any frame" only weakly
([measurement](../acceptance/2026-11-08-moved-measurements.md#trace-workbench-secret-scan-and-perceptual-hashes)).
**The workbench reports distances and does not call two frames the same screen.** Any threshold has to be calibrated on labelled pairs from development lineages
first, as the research page recommends.

## Containers and sidecars

[`sidecar.py`](../../harness/trace/sidecar.py) defines `container-manifest/1`, one shape for
every container kind (ADR 009 D17). Its fields are identity, kind, owner role, inputs and
pinned versions, budgets, lifecycle state, provenance and retention. The kinds adopted so
far are actor sessions (sealed) and, for #453, curator sessions, submissions and drafts.

Sealed directories are never rewritten. Their manifests live in an index:
[`data/containers/397-seven-day.json`](../../data/containers/397-seven-day.json)
(`container-index/1`), generated with:

```bash
.venv/bin/python -m harness.trace.sidecar .runtime/evidence/397-seven-day --study 397-seven-day --out data/containers/397-seven-day.json
```

A test checks the tracked index against the sealed sessions. The index records what each
actor was given: the digests of its prompt and context. It records no digest of a file that
holds custody or routes.
