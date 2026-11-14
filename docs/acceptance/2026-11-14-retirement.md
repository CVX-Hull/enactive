---
owner: lead
status: historical
kind: review
date: '2026-11-14'
scope: 'Removal of the curator scoring run''s original directories (#618), second copies of the sealed curator-scoring-618 study, after its record merged'
---

# Retirement of the curator scoring run's originals, 14 November 2026

## At a glance

- **What.** The five directories the curator scoring run (#618) wrote, sealed as the
  `curator-scoring-618` study ([evidence index](../../data/evidence/index.json)) and cited
  by its [record](2026-11-13-curator-scoring.md), were removed as second copies.
- **Why it loses nothing.** Every file of each original matched the sealed manifest by
  path and hash before removal (562 files), and `python -m tools.evidence verify --full`
  passed.
- **What stays.** The six reusable starts under `.runtime/starts/` are working copies for
  the delivery development start (#635) and the withholding pilot (#619), not second
  copies; the pilot's store is read from the sealed study's `knowledge/`.

## Removed

| Original | Files | Matched in the study as |
| --- | ---: | --- |
| `.runtime/curator-shadow/scoring-618-first` | 10 | `curator-shadow-first/` |
| `.runtime/curator-shadow/scoring-618-rest` | 50 | `curator-shadow-rest/` |
| `.runtime/knowledge/shadow-454/scoring-618-first` | 198 | `knowledge/` |
| `.runtime/memory-measure/scoring-618` | 271 | `memory-measure/` |
| `.runtime/memory-measure/scoring-618-inputs` | 33 | `judging-inputs/` |

Nothing that exists in only one place was deleted.
