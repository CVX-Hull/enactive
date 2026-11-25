---
owner: lead
status: historical
kind: study
date: 2026-11-25
scope: "Read-only #896-b replay of bounded briefings, recall deduplication and cut hysteresis (Ballot 4 literal gate FAILED with best-effort k=E diagnostic PASS), compact query serialization on #924 v91 queries, and English Porter2 (snowballstemmer==3.1.1) retrieval gate NO-GO."
---

# Player host replay gates, compact query serialization and Porter2 benchmark (#949)

## At a glance

| Check | Result |
| --- | --- |
| Bounded actor-start briefing | **PASS.** All 12 actor starts fit. Projected JSON ranged from 100 to 20,042 UTF-16 code units against a 24,000-unit cap. |
| Bounded recall index | **PASS.** All 92 versions fit. Title-only JSON ranged from 12 to 17,738 units. The index with snippets reached 24,000 units. Every version listed all its eligible titles. |
| Recall deduplication | **MEASURED.** Placement filtering silenced 75 of 358 recall fetches (20.95%). Pre-fetch filtering skipped zero. Charged recall spend was $3.49635150, unchanged by this projection. |
| Cut hysteresis (Ballot 4 literal) | **FAIL (escalate before `#950`).** Edge holds fell from 2,128 to 88 (95.86%), but `insufficient-cover` refused 76 of 77 healthy cuts (normal cuts dropped 77 → 1) and projected 1 hard capacity stop against 0 observed (`-266` tokens headroom at `A01 request-584`). |
| Cut hysteresis (diagnostic best-effort `k = E` fallback) | **PASS.** Preserves all 77 cuts, cuts edge holds from 2,128 to 85 (96.01% reduction), projects 0 hard capacity stops across all 3,744 checks, and keeps `+112,444` tokens minimum uncut headroom. |
| Compact query hits | **PASS.** Canonical UTF-8 size fell 63.9% in total (`232,144` → `83,921` B) and 62.0% at the median (`10,946` → `4,155` B) across 20 `v91` queries. Serialization p95 fell from `0.0472` ms to `0.0156` ms. |
| English Porter2 (`snowballstemmer==3.1.1`) | **NO-GO.** Conflated 5/5 folding pairs and tied `#889 v17` (`1.000` / `1.000`), but regressed `#896-b v91` Article MRR@5 from `0.917` to `0.908` (`Q13` dropped rank `2` → `3`). `requirements.in` and `requirements-dev.lock` stay unchanged; `_fold` stays in `#950`. |

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
estimates remaining text from the recorded part lengths. Across every archived
prefix of all 12 actors, the reconstruction was at or below the recorded
heuristic (`0` overestimate, up to `8,583` tokens underestimate; printed by
`tools/player_host_replay_benchmark.py --markdown`). Because the estimator errs
strictly downward, the projected `266`-token overflow at Admission 01
`request-584` is conservative rather than a replay artifact, and Admission 03's
`338`-token minimum headroom is likely a second hard stop.

The underlying failure is structural: in `#896-b`, live curator
`trigger_steps: 35` leaves `9–35` uncovered tail turns (median `17`) at the `76`
literal `insufficient-cover` holds, where the `k = E` candidate still carried
`20,107–62,483` post-cut tokens above briefing (median `34,475`; `76/76`
exceeding `low_mark: 20,000`) and exceeded `M - B = 19` images on `29/76` holds
(all emitted directly by `tools/player_host_replay_benchmark.py --markdown`).
Because Ballot 4 refuses the cut whenever either `T_k > low_mark` or
`I_k > M - B`, the token condition alone blocked 76 of 77 healthy cuts, letting
prompts grow into the 245,760-token hard limit.

A paired diagnostic arm (`cut_best_effort`, keeping Ballot 4's arm/edge-hold
hysteresis and strict-fit rescue, preferring the smallest `k in [min_free, E]`
meeting `T_k <= L`, `I_k <= M - B` and `fits(R_k)`, and falling back to the
largest strictly-reducing fitting prefix `k = E` when the uncovered tail alone
exceeds `L` or `M - B`) restores all 77 cuts, reduces edge holds from 2,128 to
85 (`96.01%` reduction), projects `0` hard capacity stops across all `3,744`
boundaries, and keeps `+112,444` tokens minimum uncut headroom. Amending Ballot 4
to adopt this best-effort `k = E` fallback is escalated to the owner before
implementing `#950`.

## Compact query serialization

The two envelopes used the same hit order and were built before the timer
started. Each arm timed 1,000 canonical JSON serializations with UTF-8 encoding.
Timings are from one local run. The full-record arm reused the production result
envelope and exact archived records. The compact arm used as-of revision IDs,
empty article tags, projected fact kinds and scopes from the archived ontology,
and the first three distinct citing article IDs in sorted order.

| Envelope | Total bytes | Median bytes | Max bytes | Mean time | p95 time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full records | 232,144 | 10,946 | 15,193 | 0.0367 ms | 0.0472 ms |
| Compact hits | 83,921 | 4,155 | 4,507 | 0.0136 ms | 0.0156 ms |

## English Porter2 comparison (NO-GO)

Measured in an isolated temporary Python 3.14 virtual environment with pure-Python
BSD-3 `snowballstemmer==3.1.1` (`EnglishStemmer`) against the sealed `#896-b v91`
and `#889 v17` corpora (`tools/knowledge_retrieval_benchmark.py --porter2 --markdown`).
The baseline `_fold` produced distinct forms for all five pairs (`zombie/zombies`,
`speed/speeds`, `focus/focused`, `spring/springs`, `bleed/bleeding`), whereas
Porter2 conflated all five (`zombi`, `speed`, `focus`, `spring`, `bleed`).

However, on `#896-b v91`, `bm25_1hop_porter2` regressed **Article MRR@5** from
`0.917` to `0.908` (`-0.009`), caused by query `Q13` (`safe indoor heat source to
purify drinking supply without smoke`) dropping its gold article from rank `2` to
rank `3`. Under the owner's zero-regression gate
([`#pin-snowballstemmer-for-player-knowledge`](../decisions/owner-decisions-archive.md#pin-snowballstemmer-for-player-knowledge)),
the verdict is **NO-GO**: `snowballstemmer` is **not** pinned in `requirements.in`
or `requirements-dev.lock`, the temporary environment was deleted, and `#950`
retains `_fold`.

| Corpus | Baseline Hit@5 | Baseline Article MRR@5 | Porter2 Hit@5 | Porter2 Article MRR@5 | Gate |
| --- | ---: | ---: | ---: | ---: | --- |
| `#896-b v91` | `1.000` | `0.917` | `1.000` | `0.908` | **FAIL** (`Q13`: `2` → `3`) |
| `#889 v17` | `1.000` | `1.000` | `1.000` | `1.000` | PASS |

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
