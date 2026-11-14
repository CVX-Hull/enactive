---
owner: lead
status: historical
kind: change
date: '2026-11-13'
scope: 'Removal of the memory screen gates'' original run directories, second copies of the sealed memory-screen-gates-460-386 study, after #386 and #460 merged; with the backlog grooming of the same day'
---

# Retirement of the memory screen gates' originals, 13 November 2026

## At a glance

- **What.** The three directories the memory screen's gates ran in, sealed on 13 November
  2026 as the `memory-screen-gates-460-386` study ([evidence index](../../data/evidence/index.json)),
  were removed as second copies.
- **Why it loses nothing.** Every file of each original matched the sealed manifest by
  path and hash before removal, and `python -m tools.evidence verify --full` passed.
- **What changed for users of the evidence.** The anchor check reads the sealed gate
  (`.runtime/evidence/memory-screen-gates-460-386/memory-measure`); its dry run against
  the sealed copy passed (6 packets, 30 owner-labelled pairs, the frozen prompt's hash).

## Removed

| Original | Files | Matched in the study as |
| --- | ---: | --- |
| `.runtime/memory-measure/seven-day-measure-gate` | 919 | `memory-measure/` |
| `.runtime/knowledge/shadow-454` | 292 | `knowledge/` |
| `.runtime/curator-shadow` (`brief-gate-first`, `brief-gate-rest`, `pilot-first`, `pilot-rest`) | 72 | `curator-shadow/` |

The study's `sources` keep where each came from (`@a4810c9`). Routine checker logs under
`.runtime/check-logs/` were also pruned. Nothing that exists in only one place was
deleted; `.runtime/logs/` is younger than the 30-day rule and stays.
