---
owner: lead
status: historical
kind: study
date: 2026-11-25
scope: "Read-only #896-b replay of bounded briefings, recall deduplication and cut hysteresis, and compact query serialization on the #924 v91 queries. English Porter2 comparison pending."
---

# Player host replay gates and compact query serialization (#949)

## At a glance

| Check | Result |
| --- | --- |
| Bounded actor-start briefing | All 12 actor starts fit. Projected JSON ranged from 100 to 20,042 UTF-16 code units against a 24,000-unit cap. |
| Bounded recall index | All 92 versions fit. Title-only JSON ranged from 12 to 17,738 units. The index with snippets reached 24,000 units. Every version listed all its eligible titles. |
| Recall deduplication | Placement filtering silenced 75 of 358 recall fetches (20.95%). Pre-fetch filtering skipped zero. Charged recall spend was $3.49635150, unchanged by this projection. |
| Cut hysteresis | Edge holds fell from 2,128 to 88 (95.86%) and the capacity gate did not pass. One continuous replay projected a hard capacity stop against zero observed. |
| Compact query hits | Canonical UTF-8 size fell 63.9% in total and 62.0% at the median across 20 queries. Serialization p95 fell from 0.0533 ms to 0.0188 ms in one run. |
| English Porter2 | The original fold missed all five pairs. The optional comparison across 30 queries is pending. |

The replay used [the sealed campaign lineage](2026-11-22-seven-day-campaign-896.md),
[the proposed host contract](../design/player-architecture-contract.md#83-verification-gates-offline-0-first-then-pre-merge-qualification)
and [the frozen retrieval queries and labels](2026-11-24-wave3-retrieval-baseline-and-curator-recount-936.md).
It cost $0.

## Briefings and recall

The observed actor-start briefing text grew from 178 to 51,601 units including
framing. Its JSON ranged from 79 to 51,502 units. The simulation compared
serialized JSON with the proposed cap, using the recorded recall selections and
counting omitted entries. On `v91`, the projected current and proposed cut
briefings each took 16,578 units. Both include standalone fact index rows.

The replay measured `v0` through `v91` using sealed runner and actor-start
exports, with seven gaps reconstructed from sealed curator tags using the
archived world selection and delivery rules. It kept title selection independent
of recall results. The trace supplied the order of surviving placements, and
the replay substituted the bounded briefings and current lead fingerprints.
Clipped briefing leads remained eligible for recall. The observed recall charges
fund every simulated fetch that still goes out. Placement silence cannot recover
a charge already incurred. Changes in prompt length, caching and recall choices
could change actual spend.

## Cut hysteresis and capacity

The projected cut history carried forward each selected cut against the
recorded coverage, adoption and control schedule. This kept the cut comparison
separate from simulated reminder removal. There were 77 recorded cuts, one
projected normal cut and zero projected strict-fit rescues. The previously cited
2,215 held-back checks cover twelve admissions. The 2,128 comparison baseline
covers the ten admissions in this replay. See the [wider census](../research-player-architecture.md#1-empirical-baseline-889-and-896-12-sealed-runs).

The replay reached 3,737 of 3,744 recorded request boundaries. It projected a
stop at admission 01, actor `001`, `request-584`, on `v15`. It estimated
246,026 input tokens against a strict limit of 245,760. Orderly stop had already
been accepted, so the three cut guards ruled out rescue even with eligible
coverage. The remaining seven recorded boundaries of that actor fall after the
projected stop.

The archive contains request-part digests and sizes. The replay reconstructs
tool arguments and results from their events, projects image eviction, and
estimates remaining text from the recorded part lengths. The reconstruction
differed from the recorded heuristic by up to 8,583 tokens on the archived
prefixes. The 266-token overshoot is inside that observed error range, so the
stop is a projection and the required zero-increase claim remains unverified.

## Compact query serialization

The two envelopes used the same hit order and were built before the timer
started. Each arm timed 1,000 canonical JSON serializations with UTF-8 encoding.
Timings are from one local run. The full-record arm reused the production result
envelope and exact archived records. The compact arm used as-of revision IDs,
empty article tags, projected fact kinds and scopes from the archived ontology,
and the first three distinct citing article IDs in sorted order.

| Envelope | Total bytes | Median bytes | Max bytes | Mean time | p95 time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full records | 232,144 | 10,946 | 15,193 | 0.0394 ms | 0.0533 ms |
| Compact hits | 83,921 | 4,155 | 4,507 | 0.0151 ms | 0.0188 ms |

## English Porter2 comparison

The baseline fold produced distinct forms for `zombie/zombies`,
`speed/speeds`, `focus/focused`, `spring/springs` and `bleed/bleeding`.
The `--porter2` arm reports exact folded forms and a Go/No-Go result against
the one-hop baseline, requiring all five pairs to conflate and zero Hit@5 or
Article MRR@5 regression on either corpus. The comparison is pending a run in
an isolated Python environment with the optional `snowballstemmer` package.

| Corpus | Baseline Hit@5 | Baseline Article MRR@5 | Porter2 Hit@5 | Porter2 Article MRR@5 |
| --- | ---: | ---: | ---: | ---: |
| `#896-b v91` | 1.000 | 0.917 | Pending | Pending |
| `#889 v17` | 1.000 | 1.000 | Pending | Pending |

## Reproduction

Both scripts read sealed evidence and print results. The default evidence path
is the main checkout's `.runtime/evidence`. Pass `--evidence DIR` to select
another copy and `--json` for per-case data. The replay exits with status 1 if
either cap or the projected capacity gate fails.

```sh
PY="$(git rev-parse --git-common-dir)/../.venv/bin/python"
"$PY" tools/player_host_replay_benchmark.py --markdown
"$PY" tools/knowledge_retrieval_benchmark.py --markdown
# Use the isolated environment's Python for the optional arm.
"$PORTER2_PY" tools/knowledge_retrieval_benchmark.py --porter2 --markdown
```
