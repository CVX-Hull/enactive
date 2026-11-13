---
owner: lead
status: historical
kind: measurement
date: '2026-11-08'
scope: 'Measurements that current design and operations pages held until 8 November 2026 and no other record holds, moved here unchanged when ADR 010 kept current pages free of dated results'
---

# Measurements moved from current pages

[ADR 010](../decisions/010-streamlined-delivery.md) keeps dated results out of current
pages. No other dated record, research page or data file held the measurements below, so
they are kept here, as the pages stated them. Each section names the page that now links
here.

## Trace workbench: secret scan and perceptual hashes

From [the trace workbench design](../design/trace-workbench.md).

The sealed #397 lineage and the six sampled #372 runs are projected and scanned for every
custody token, custodian URL and route value of their actors, plus key-like patterns.
There were no hits; #397 alone wrote 1,996 files in 0.8 s.

[`tools/phash_measure.py`](https://github.com/CVX-Hull/enactive/blob/e8b062df3275eb128f42f4b84161e651be632d13/tools/phash_measure.py)
was run over the sealed #397 frames: 7 sessions, 1,932 frames, 1,925 consecutive pairs,
and as many random pairs within each session (seed 452).

| Pairs | Median distance | p10 | p90 | Within 5 bits | Within 10 bits |
| --- | ---: | ---: | ---: | ---: | ---: |
| Consecutive | 20 | 2 | 34 | 17.7% | 28.3% |
| Random | 29 | 16 | 38 | 0.9% | 2.6% |

Only 2.8% of consecutive pairs were pixel-identical. The two distributions overlap
heavily, so on these screens a difference hash separates "next frame" from "any frame"
only weakly.

## Curator hosts: versions, footprint and body limit

From [curator hosts](../operations/curator-hosts.md).

- **Versions installed on this Mac:** Claude Code 2.1.319 and Codex CLI 0.162.1, on
  macOS 27.2.
- **Observed footprint** (no spend, local stand-in with three scripted requests, one frame
  image and one workbench call): about 0.35 s of host time, 93–98 MB peak, 0.13–0.15 s from
  process start to the first model request, no surviving process.
- **Body limit:** no request in the #454 runs reached the body limit; their only proxy
  refusals were spend-cap refusals.

## Campaign runs: the worst-case bound against billed cost

From [campaign runs](../operations/campaign-run.md).

The worst-case figure charges every attempt as if it filled the whole context window and
output limit, which overstated actual cost by more than an order of magnitude: about
$1066.80 against $30–40 billed.
