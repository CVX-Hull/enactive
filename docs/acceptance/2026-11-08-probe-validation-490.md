---
owner: lead
status: historical
date: '2026-11-08'
scope: 'Blinded probe recall checked against independently found re-observations on #397 and the #372 sample, query probes written and re-checked, and the frozen scoring ledger (#490)'
review_trigger: None; dated record
---

# Probe validation (#490)

P0 found that blinded annotation recognised the four known #397 episodes only weakly
([#449 record](2026-11-08-probe-baseline-449.md)). Before any P1 arm is scored against
probes, this record checks blinded recall against re-observations that neither the lead
nor the annotators chose. It uses development data only: #397 and the six-run #372
sample. #382's held-out lineages were refused by the tool and never opened.

The method and both bars were fixed in the
[protocol](../design/probe-protocol.md#recall-check-against-independently-found-re-observations-490)
before each step was computed. They were committed as `c856008`, before the candidates,
and `bb029f7`, before the queries.
[`tools/probe_validation.py`](../../tools/probe_validation.py) reproduces every figure
from the tracked files in
[`data/evaluation/probes/validation/`](../../data/evaluation/probes/validation).

## How it was done

1. **Candidates.**
   - **Rule.** A new screen after a boundary is a candidate when it is within 16 of 256
     difference-hash bits of a frame from an earlier chunk.
   - **Found.** 197 in #397 and 25 in the #372 sample.
   - **Sample.** A seeded sample of 40 and 20.
2. **Pairwise judge.** Four blinded agents, each in a fresh context, saw only the two
   frames of each pair, in a seeded order. Each judged whether the frames show the same
   specific information. They confirmed **37 of the 60** pairs.
3. **Fact-label check.** For each confirmed pair, did the #449 blinded ledger (without
   adjudication) hold a need or re-observation event near the later frame, on a fact
   from an earlier chunk?
4. **Query probes.**
   - **Writers.** 19 blinded writers, one per chunk preceding a boundary, wrote **649
     queries** from their chunk's timeline and frames. Each query carries its answer
     and frame.
   - **Coverage judges.** Four further blinded judges each saw a confirmed pair's
     earlier frame and the queries written for that chunk. They judged whether any
     query's answer states the frame's information.

## Results

| Lineage | Confirmed | Fact labels captured | Queries covered | Either |
| --- | ---: | ---: | ---: | ---: |
| #397 | 24 | 16 (0.67) | 12 (0.50) | 20 (0.83) |
| #372 sample | 13 | 3 (0.23) | 3 (0.23) | 5 (0.38) |
| **Pooled** | **37** | **19 (0.51)** | **15 (0.41)** | 25 (0.68) |
| Informative pairs only | 21 | 12 | 13 (0.62) | 17 (0.81) |

**Both pre-registered bars were missed.** Fact labels reached 0.51 and queries 0.41,
against 0.6.

**The last two columns are post hoc and descriptive.**
- **"Either"** is the union of the two ledgers.
- **"Informative pairs only"** leaves out 16 confirmed pairs whose judge note marks a
  match without durable information: an empty recipe tab, a search prompt or a loading
  screen. Nine of the #372 sample's 13 confirmed pairs are of this kind, so the
  #372 figures say little.

**What the figures say, as development evidence.**
- **The ledgers are complementary.** Fact labels caught re-observations that queries
  missed, and the reverse. Together they cover about two thirds of the confirmed
  re-observations, and four fifths of the informative ones.
- **What each ledger missed.** Most misses were recipe and inventory screens with many
  details, or overmap descriptions. The writers mentioned the subject but did not state
  the specific contents.

## The owner's decision

On 8 November the owner chose to **freeze both ledgers together as P1's scoring
ledger**. The manifest is
[`data/evaluation/probes/ledger.json`](../../data/evaluation/probes/ledger.json), with a
digest for every fact chunk, the adjudication layer and every query file. Before relying
on it, #178:
- tightens the confirmation rule to exclude matches that carry no information;
- re-tests the combined ledger once on held-out data, with its bar fixed in advance.

## Cost

| Step | Agents | Tokens | Wall time |
| --- | ---: | ---: | ---: |
| Pairwise judges | 4 | 360,062 | 2.8 min |
| Query writers | 19 | 2,381,946 | 38.5 min |
| Coverage judges | 4 | 416,120 | 1.7 min |
| **Total** | 27 | **3,158,128** | 43 min |

These are development-agent tokens; no model proxy was used and nothing was spent
through it. Per-unit figures are in
[`costs.jsonl`](../../data/evaluation/probes/validation/costs.jsonl).

## Deviations

- **The goal's source of independent episodes does not exist.** The goal named
  "evaluator rediscovery events", but the evaluator records no such event. Near-duplicate
  frames across boundaries replaced them, a source equally independent of the lead and
  the annotators. The rule was fixed before computing.
- **One frame-count difference.** The tool's frame order matched #449's chunk frame
  counts, except `ceil05-001`, which has 84 frames against 85: a frame repeated across
  two operations is counted once.
- **Query writers.**
  - `sd1a1-001` keeps 17 queries: its reply was truncated in transit, and the writer no
    longer had the rest.
  - `sd1a2-002` wrote 43 queries, over the cap of 40. All are kept.
  - `sd1a5-001` viewed 19 frames, fewer than the coverage rule asks.
  - Several writers were resumed to write their output to a file after replies were
    truncated. The queries were not changed.
- **Unit tests corrected.** Two unit tests for the candidate rule initially expected
  fewer candidates than the frozen rule produces. The rule also keeps returns to the main
  view; the judge rejects those. The tests were corrected to the rule.

## Limitations

- **One judge per pair, and one writer per chunk.** There was no inter-rater check on
  the judges or the writers.
- **The confirmation rule admits trivial matches,** hence the descriptive "informative"
  figures.
- **The candidate rule finds only visual re-observations.** A fact re-learned through a
  different screen is not tested.
- **Small samples.** 37 confirmed pairs, 13 of them from short #372 runs.
