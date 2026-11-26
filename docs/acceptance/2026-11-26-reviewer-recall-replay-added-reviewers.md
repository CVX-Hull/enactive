---
owner: lead
status: historical
kind: study
date: '2026-11-26'
scope: 'Two more reviewers on the nine commits of the reviewer recall replay, for issue #991: Claude Sonnet 5.5 at High on Claude Code and GPT-6.1 Terra at High on Codex, each reviewing each commit once on the replay''s brief, scored by the replay''s two judges and rule; subscription quota only, no game launch, no game input'
---

# Reviewer recall replay: two added reviewers

## At a glance

The [reviewer recall replay](2026-11-25-reviewer-recall-replay.md) reviewed nine past
commits that hold 16 defects found and fixed later, with the largest models of each
family. This study adds a middle model from two families on the same commits, brief,
judges and rule.

| Reviewer, as started | Found by both judges, of 16 | Documents, of 10 | Code, of 6 | Wall time, nine reviews |
| --- | ---: | ---: | ---: | ---: |
| GPT-6.2 Sol at Extra-high, first study | 10 | 7 | 3 | 2,758 s |
| GPT-6.2 Astra at High, first study | 8 | 5 | 3 | 2,021 s |
| GPT-6.2 Astra at Medium, first study | 7 | 4 | 3 | 1,105 s |
| Claude Opus 5.5 at High, plan-mode start, first study | 4 | 3 | 1 | 3,979 s |
| **Claude Sonnet 5.5 at High** | **4** | **2** | **2** | **2,131 s** |
| **GPT-6.1 Terra at High** | **4** | **2** | **2** | **565 s** |
| Claude Opus 5.5 at Medium, plan-mode start, first study | 2 | 1 | 1 | 2,478 s |

- **Each finds four defects, and not the same four.** Together they find eight.
- **Claude Sonnet 5.5 finds one defect that none of the five reviewers in the table
  above it finds:** the host decided whether a knowledge update fit before applying the
  context cut. Two of the first study's added arms did find it. Sonnet adds one defect
  to GPT-6.2 Sol and three to GPT-6.2 Astra at High.
- **GPT-6.1 Terra adds nothing to a GPT-6.2 reviewer.** All four of its defects are
  among those GPT-6.2 Sol, Astra at High and Astra at Medium find. It adds three to a
  Claude Opus 5.5 reviewer. Its nine reviews take 565 seconds, about half the time of
  the next shortest.
- **As a first reviewer neither replaces a GPT-6.2 reviewer,** which finds seven to ten.

The table does not rank the models: nine commits, each reviewed once, and every
document commit has a Claude co-author. The Claude Sonnet 5.5 reviews used the
`dontAsk` start; the first study's Claude Opus 5.5 reviews used plan mode, so the two
Claude rows differ in start as well as model. No owner decision is requested.

The scripts, the reviews, both judges' packets and replies and the table are retained
as
[`reviewer-recall-replay-added-reviewers`](../../data/evidence/reviewer-recall-replay-added-reviewers.sha256).
The four lower-tier reviewers' reviews, judging and table are retained as
[`reviewer-recall-replay-lower-tier-reviewers`](../../data/evidence/reviewer-recall-replay-lower-tier-reviewers.sha256).
The figures are printed by `scripts/tabulate.py` into `results/table.txt`.

## Method

- **What is reused.** The nine prepared commit trees, the review brief, the 16 known
  defects, the judging brief and the rule are the first study's
  ([method](2026-11-25-reviewer-recall-replay.md#method)). `scripts/reviews.py` calls
  the first study's start function with two more configurations.
- **The reviewers.** Claude Sonnet 5.5 at High on Claude Code 2.1.329 and GPT-6.1 Terra
  at High on Codex CLI 0.171.0, the two the leaf names. Four lower-tier reviewers were added later the same day, as
  the leaf asks for any lower-tier model that states no wrong cause in the diagnosis
  study: GPT-6 Luna at High, Gemini 4 Hydrogen at High, Gemini 3.8 Flash at High and
  GPT-OSS 120B at Medium, the last three on Antigravity CLI 1.5.18 with the call's note
  to run no command. They are reported in [their own section](#lower-tier-reviewers).
  Claude Haiku 5.5 stated a wrong cause there and is not added.
- **The start.** The Claude Sonnet 5.5 reviews ran through the Claude Code reviewer
  start in the `dontAsk` permission mode with the default output style, as of the
  [start check](2026-11-26-reviewer-start-check.md), before the file-reading tools were
  allowed outside the working directory; a review reads inside its tree only. None of
  the nine replies mentions plan mode or carries a note block.
- **Judging.** For each commit one packet holds the two reviews under shuffled labels.
  GPT-6.2 Sol at Extra-high and Claude Opus 5.5 at High each judge every packet with
  the first study's brief (`scripts/judge.py`). A defect counts as found when both
  judges say found.

## Results

| Defect | Kind | Sonnet High | Terra High | Found by, of the five first-study reviewers above |
| --- | --- | --- | --- | --- |
| A check that could not catch a file moved between packages | document | no | both judges | Sol, Astra High, Astra Medium |
| The poll interval taken as the uncertainty on publication time | document | no | both judges | Sol, Astra High, Astra Medium |
| A run cap sized against expected charges and not reservations | document | both judges | no | Sol, Opus High |
| A measured share attributed to the wrong model | document | both judges | no | Sol, Astra Medium |
| An event-stream probe that mishandles split line endings | code | both judges | no | Sol, Astra High, Astra Medium |
| Charges in flight not counted on a runner restart | code | no | both judges | Sol, Astra High, Astra Medium |
| A ledger writer and reader that disagree on uniqueness | code | no | both judges | all five |
| A fit check made before the context cut | code | both judges | no | none of the five |

Neither finds the other eight. One judge and not the other credits Claude Sonnet 5.5
with a ninth, a document defect. The last column covers the five reviewers of the
first study's main table. Its three added arms are not paired here: Claude Opus 5.5
at High started without plan mode and Gemini 4 Carbon both find the fit check, so
Sonnet adds nothing to the first study's eleven defects taken together.

- **Pairs.** With each of those five, by both judges:

| Paired with | Union with Sonnet High | Sonnet adds | It adds to Sonnet | Union with Terra High | Terra adds | It adds to Terra |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPT-6.2 Sol at Extra-high, 10 alone | 11 | 1 | 7 | 10 | 0 | 6 |
| GPT-6.2 Astra at High, 8 alone | 11 | 3 | 7 | 8 | 0 | 4 |
| GPT-6.2 Astra at Medium, 7 alone | 9 | 2 | 5 | 7 | 0 | 3 |
| Claude Opus 5.5 at High, 4 alone | 7 | 3 | 3 | 7 | 3 | 3 |
| Claude Opus 5.5 at Medium, 2 alone | 6 | 4 | 2 | 5 | 3 | 1 |

- **Findings and time.** Claude Sonnet 5.5 writes 64 findings in nine reviews, at 106
  to 435 seconds a review. GPT-6.1 Terra writes 26, at 37 to 86 seconds.
- **Judges.** The two judges give the same verdict on 30 of 32 cells. They differ on
  one document defect for Claude Sonnet 5.5, partial against found, and one code defect
  for GPT-6.1 Terra, not found against partial.
- **Tokens,** as each coding agent reported them for nine reviews: Claude Sonnet 5.5
  15.4 million cached input and 267,000 output; GPT-6.1 Terra 4.1 million input and
  19,000 output. They compare within a coding agent only.

## Lower-tier reviewers

Four more reviewers, on the same commits, brief, judges and rule.

| Reviewer, as started | Starts handed back, of 9 | Found by both judges, of 16 | Documents, of 10 | Code, of 6 | Findings in all | Wall time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Gemini 4 Hydrogen at High | 9 | 4 | 1 | 3 | 52 | 3,914 s |
| Gemini 3.8 Flash at High | 9 | 3 | 1 | 2 | 33 | 8,138 s |
| GPT-6 Luna at High | 9 | 1 | 1 | 0 | 10 | 1,146 s |
| GPT-OSS 120B at Medium | 5 | 0 | 0 | 0 | 25 | 338 s |

| Paired with | Hydrogen adds, it adds | Flash adds, it adds | Luna adds, it adds |
| --- | --- | --- | --- |
| GPT-6.2 Sol at Extra-high, 10 alone | 1, 7 | 0, 7 | 0, 9 |
| GPT-6.2 Astra at High, 8 alone | 1, 5 | 0, 5 | 0, 7 |
| GPT-6.2 Astra at Medium, 7 alone | 2, 5 | 0, 4 | 0, 6 |
| Claude Opus 5.5 at High, 4 alone | 2, 2 | 1, 2 | 1, 4 |
| Claude Opus 5.5 at Medium, 2 alone | 2, 0 | 2, 1 | 1, 2 |

- **Gemini 4 Hydrogen finds three of the six code defects,** as many as any reviewer
  in either study, among them the fit check made before the context cut. It finds one
  of ten document defects. Its nine reviews take 264 to 671 seconds each.
- **Gemini 3.8 Flash finds three,** none that a GPT-6.2 reviewer misses, at 535 to
  1,318 seconds a review.
- **GPT-6 Luna finds one of sixteen** and writes ten findings in nine reviews.
- **GPT-OSS 120B finds none.** Three of its nine starts fail on the server's capacity
  error and one returns nothing. Of the five replies it hands back, one is a plan that
  asks for direction and four are reviews, holding 25 findings; it is judged on three
  code defects and four document defects.
- **Judges.** The two judges give the same verdict on 52 of 55 cells for these four.
- **Tokens,** as Codex and Antigravity reported them for nine reviews: GPT-6 Luna 5.5
  million input and 49,000 output; Gemini 4 Hydrogen 4.8 million input, 37 million
  cached and 783,000 output; Gemini 3.8 Flash 3.0 million, 68 million and 931,000.

## What this supports

Every statement is about these nine commits, each configuration as started here and
run once.

- A middle model from another family adds defects as a second reviewer in the pairs
  shown: Claude Sonnet 5.5 adds one to three to a GPT-6.2 reviewer, and GPT-6.1 Terra
  adds three to a Claude Opus 5.5 reviewer.
- GPT-6.1 Terra adds nothing after a GPT-6.2 reviewer: its four defects are all found
  by each of them. The same is not true of Claude Sonnet 5.5 after Claude Opus 5.5
  through the plan-mode start, where it adds three or four.
- GPT-6.1 Terra has the shortest total wall time of any reviewer that returns all nine
  reviews, 565 seconds against 1,105 to 8,138, and finds a quarter of the known
  defects.
- One defect that the five reviewers of the first study's main table miss is found by
  a middle model, so none of those five is a superset of it on this set.
