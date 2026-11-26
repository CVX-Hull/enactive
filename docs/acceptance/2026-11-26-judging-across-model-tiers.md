---
owner: lead
status: historical
kind: study
date: '2026-11-26'
scope: 'Twelve more configurations as judges on the eighteen blind packets of the reviewer recall replay, for issue #993: each decides which known defects each review found, and is compared with the verdicts the replay''s two judges share; subscription quota only, no game launch, no game input'
---

# Judging across model tiers

## At a glance

The [reviewer recall replay](2026-11-25-reviewer-recall-replay.md) had two judges,
GPT-6.2 Sol at Extra-high and Claude Opus 5.5 at High, decide which of 16 known defects
each review found. They gave the same verdict on 106 of 114 cells. This study gives
the same eighteen packets and brief to twelve more configurations and compares each
with those 106 shared verdicts.

| Judge, as started | Same as the shared verdict | Finds a defect the review did not find | Misses one it did | Wall time, 18 packets |
| --- | ---: | ---: | ---: | ---: |
| GPT-6.1 Terra at Medium | 106 of 106 | 0 | 0 | 873 s |
| Claude Sonnet 5.5 at Medium | 104 of 106 | 1 | 1 | 703 s |
| GPT-6.2 Astra at Medium | 104 of 106 | 2 | 0 | 1,032 s |
| Gemini 4 Neon at High | 104 of 106 | 0 | 2 | 3,391 s |
| GPT-6.1 Terra at High | 103 of 106 | 0 | 0 | 1,031 s |
| Claude Sonnet 5.5 at High | 102 of 104 | 1 | 0 | 884 s |
| Claude Fable 5.2 at High | 102 of 106 | 4 | 0 | 1,183 s |
| GPT-6.2 Astra at High | 101 of 106 | 2 | 0 | 1,216 s |
| Gemini 4 Hydrogen at High | 97 of 105 | 3 | 2 | 1,566 s |
| Claude Haiku 5.5 at High | 97 of 106 | 3 | 2 | 2,364 s |
| GPT-6 Luna at High | 86 of 92 | 4 | 0 | 1,437 s |
| GPT-6 Luna at Low | 68 of 85 | 3 | 5 | 842 s |

- **Eight configurations agree with the shared verdict on 101 or more of 106 cells,**
  about as closely as the two first judges agree with each other.
- **A cheap model judges as well as a large one here.** GPT-6.1 Terra at Medium matches
  every shared verdict and Claude Sonnet 5.5 at Medium departs on two, each in under
  fifteen minutes for the eighteen packets.
- **Errors lean toward crediting a review.** Where a judge departs from the shared
  verdict it more often finds a defect the review did not find; only GPT-6 Luna at Low
  more often misses one.
- **GPT-6 Luna does not hold up:** at Low it departs on 17 of 85 cells and three of its
  replies cannot be read; at High, six of 92 with one unreadable.

The shared verdicts are two models agreeing, not the truth: a judge that departs from
them is not shown to be wrong. Eighteen packets from nine commits, each judge run
once. No owner decision is requested.

The scripts, every brief, reply and result and the table are retained as
[`judging-across-model-tiers`](../../data/evidence/judging-across-model-tiers.sha256).
The figures are printed by `scripts/tabulate.py` into `results/table.txt`.

## Method

- **What is reused.** The eighteen packets, the judging brief and its rule are the
  replay's: a packet holds the known defects of one commit and the reviews of that
  commit under shuffled labels, and the judge gives each review a verdict of found,
  partial or not found for each defect
  ([replay method](2026-11-25-reviewer-recall-replay.md#method)). `scripts/judges.py`
  changes only the configuration named on the brief's Role line.
- **The reference.** A cell is one defect in one review of one packet. The reference
  is the 106 cells on which the replay's two judges gave the same verdict: 42 found, 7
  partial, 57 not found. The eight cells on which they differ are reported apart.
- **The judges.** Every model not used as a judge before, at High, and at its
  routing-default effort where that differs: GPT-6.2 Astra at High and Medium, GPT-6.1
  Terra at High and Medium, GPT-6 Luna at High and Low, Claude Fable 5.2 at High,
  Claude Sonnet 5.5 at High and Medium, Claude Haiku 5.5 at High, Gemini 4 Neon and
  Gemini 4 Hydrogen at High. Each ran once on each packet as an explorer through
  `tools/delegate.py` with a 900-second limit, on Codex CLI 0.171.0, Claude Code
  2.1.329 and Antigravity CLI 1.5.18.
- **Left out.** Gemini 4 Carbon was started and stopped: its starts take many minutes
  each, so eighteen of them cost more than a judge that slow is worth. The models
  leaving Antigravity on 30 November 2026 were not started.
- **The Claude Code starts.** A first set of 72 Claude Code starts handed back only a
  refusal: the start then denied a read outside the working directory, where the
  packets are. They are retained under `refused-read/` and not scored. The scored
  starts ran after the start
  [allowed the file-reading tools everywhere](2026-11-26-reviewer-start-check.md#limits).
- **Scoring.** `scripts/tabulate.py` reads the JSON object in each reply. A reply
  without a readable object leaves that packet's cells unjudged, which is why four rows
  have fewer than 106.

## Results

| Judge | Packets read | Same | Found where the reference is not found or partial | Not found or partial where it is found | Partial against not found | On the eight disputed cells: with Sol, with Opus, neither |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| GPT-6.1 Terra at Medium | 18 | 106 of 106 | 0 | 0 | 0 | 5, 3, 0 |
| Claude Sonnet 5.5 at Medium | 18 | 104 of 106 | 1 | 1 | 0 | 3, 4, 1 |
| GPT-6.2 Astra at Medium | 18 | 104 of 106 | 2 | 0 | 0 | 6, 2, 0 |
| Gemini 4 Neon at High | 18 | 104 of 106 | 0 | 2 | 0 | 7, 1, 0 |
| GPT-6.1 Terra at High | 18 | 103 of 106 | 0 | 0 | 3 | 6, 2, 0 |
| Claude Sonnet 5.5 at High | 17 | 102 of 104 | 1 | 0 | 1 | 1, 7, 0 |
| Claude Fable 5.2 at High | 18 | 102 of 106 | 4 | 0 | 0 | 1, 7, 0 |
| GPT-6.2 Astra at High | 18 | 101 of 106 | 2 | 0 | 3 | 6, 2, 0 |
| Gemini 4 Hydrogen at High | 18 | 97 of 105 | 3 | 2 | 3 | 2, 5, 0 of 7 |
| Claude Haiku 5.5 at High | 18 | 97 of 106 | 3 | 2 | 4 | 5, 3, 0 |
| GPT-6 Luna at High | 17 | 86 of 92 | 4 | 0 | 2 | 2, 5, 0 of 7 |
| GPT-6 Luna at Low | 15 | 68 of 85 | 3 | 5 | 9 | 1, 5, 1 of 7 |

- **Where the errors fall.** Across the twelve judges, 23 departures credit a review
  with a defect the reference says it did not find, and 12 deny one the reference says
  it found. Claude Fable 5.2 makes four of the first kind and none of the second.
- **The disputed cells follow the family.** On the eight cells where the first judges
  differ, the Codex judges mostly side with GPT-6.2 Sol and the Claude judges with
  Claude Opus 5.5. GPT-6.1 Terra at Medium splits five to three, and Gemini 4 Neon
  sides with Sol on seven.
- **Effort.** Medium agrees with the reference at least as often as High for GPT-6.1
  Terra, GPT-6.2 Astra and Claude Sonnet 5.5. No pair of efforts gives the same verdict
  on every cell.
- **Unreadable replies.** One reply each from Claude Sonnet 5.5 at High and GPT-6 Luna
  at High, and three from GPT-6 Luna at Low, hold no readable JSON object. Gemini 4
  Hydrogen leaves one cell without a verdict.
- **Time and tokens.** A packet takes 16 to 129 seconds for the Codex and Claude
  Sonnet judges, 30 to 99 for Claude Fable 5.2, up to 214 for Claude Haiku 5.5, which writes 545,000 output tokens
  across its eighteen, and 100 to 265 for Gemini 4 Neon. Token counts are in the table
  file and compare within one coding agent only.

## What this supports

Every statement is about these eighteen packets, each judge as started here and run
once.

- Judging which defects a review found against a written rule does not need the
  largest model: GPT-6.1 Terra at Medium and Claude Sonnet 5.5 at Medium agree with the
  two first judges' shared verdicts on 106 and 104 of 106 cells, in under fifteen
  minutes for all eighteen packets.
- A judge from each of the three families is available at that level of agreement:
  GPT-6.1 Terra, Claude Sonnet 5.5 and Gemini 4 Neon, the last at four times the wall
  time.
- GPT-6 Luna at Low and Claude Haiku 5.5 at High depart from the shared verdict on one
  cell in five and one in twelve.
- A judge tends to side with its own family on a disputed cell, which is a reason to
  pair judges from two families.
