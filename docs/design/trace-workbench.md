---
owner: lead
status: historical
date: '2026-11-21'
scope: 'Trace projection, sealed-memory evidence reader, workbench commands and sidecar container manifests'
replacement: docs/components/curator.md
---

# Trace projection and workbench

## At a glance

- **Question.** How do trace readers examine player-visible evidence without
  receiving custody data?
- **Answer.** The [trace package](../../harness/trace) projects an allowlisted,
  secret-checked copy and provides read-only evidence and frame tools.
- **Unknown.** A missing or unverifiable label is unknown. A visual distance measures
  similarity and needs calibration for a same-screen claim.
- **Owner decisions.** This reference identifies no pending owner decision.

## Projection

[`projection.project`](../../harness/trace/projection.py) writes `trace-projection/3`.
The workbench and curator window require this version. The projection reads sealed
sessions and closed [staged snapshots](live-curator-integration.md#the-snapshot)
through the same immutable store reader.

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

The manifest records a digest for every projected file, the exclusions, and one
entry per session. Each entry pairs the session's directory `name` with its sealed
`session_id`. Both are unique within a projection. The entry records `world`,
`lineage` and `admission` (position within the lineage), each of which can be null.

For a sealed session or staged snapshot, the projection checks `manifest.json` and
`watch-start.json`. It requires supported package and launch record schemas, matching
session IDs in both records and the store, and a manifest SHA-256 matching the digest
in the supervisor's `campaign-watch-start/4` launch record.
If a record is missing or a check fails, all three labels are null. `label_check`
identifies the failed check as `manifest-schema` for the package file, schema or
label shape, `manifest-session` for the package's session identifier, or
`supervisor-digest` for the supervisor record and its digest. `label_error` gives a
fixed explanation without quoting either record. With verified evidence and valid
labels, both diagnostic fields are null.
The trace reads these files directly without the campaign tooling.

The projection verifies lineage and admission position for `campaign-run/10` and
leaves `world` null. An unsupported manifest version leaves all labels null with a
diagnostic. A save path cannot establish a game-neutral world label.
[World-scope field table](world-scoped-memory.md#world-and-lineage)

The curator window carries the directory name, world, lineage, admission position
and label diagnostics keyed by sealed session identifier. The map is available in
`positions(...).sessions` or through `session_labels(manifest)`. Frame positions
retain their four keys `session`, `actor`, `step` and `order`.

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
raw run package manifests, raw `host.jsonl` and the raw session store. Session, actor and operation IDs stay, because
they grant nothing and are how frames are cited.

The [projection tests](../../tests/test_trace_projection.py) cover credential
omission, free-text refusal, frame integrity and label diagnostics. The
[window tests](../../tests/test_curator_window.py) cover the label map and version
refusal. [Retained secret-scan evidence](../acceptance/2026-11-08-moved-measurements.md#trace-workbench-secret-scan-and-perceptual-hashes)

## Evidence reader

[`memory_reader.read`](../../harness/trace/memory_reader.py) reads sealed
`player-memory/2` stores as data. It returns records with supports and sources,
programs and source metadata. It opens SQLite in immutable mode and refuses a
non-empty write-ahead log because that mode would ignore the log.
[Retained reader evidence](../acceptance/2026-11-09-moved-results.md#trace-workbench-evidence-reader)

## Workbench

`python -m harness.trace.workbench` prints JSON lines:

| Command | Does |
| --- | --- |
| `steps` | An actor's operations by sequence range or kind |
| `frames` | Frame IDs and paths for a sequence range |
| `tools` | Tool calls, optionally of one tool |
| `diff` | Per-cell change between two frames on a grid ([`images.region_diff`](../../harness/trace/images.py)) |
| `similar` | Nearest frames by 64-bit difference hash |

The workbench reports hash distance. A threshold for asserting screen equivalence
needs calibration on labelled frame pairs.
[Perceptual-hash measurement](../acceptance/2026-11-08-moved-measurements.md#trace-workbench-secret-scan-and-perceptual-hashes)

## Containers and sidecars

[`sidecar.py`](../../harness/trace/sidecar.py) defines `container-manifest/1` for
actor sessions, curator sessions, submissions and drafts. It records identity, kind,
owner role, inputs and pinned versions, budgets, lifecycle, provenance and retention.

A `container-index/1` records manifests beside the sealed evidence. Its input digests
cover the actor's prompt and context and exclude files that hold custody or routes.
[Tracked sidecar example](../../data/containers/397-seven-day.json)
