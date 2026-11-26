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
- **Claude Sonnet 5.5 finds one defect no first-study reviewer found:** the host
  decided whether a knowledge update fit before applying the context cut. It adds one
  defect to GPT-6.2 Sol and three to GPT-6.2 Astra at High.
- **GPT-6.1 Terra adds nothing to a GPT-6.2 reviewer.** All four of its defects are
  among those GPT-6.2 Sol, Astra at High and Astra at Medium find. It adds three to a
  Claude Opus 5.5 reviewer, in a fifth of the wall time of any other reviewer here.
- **As a first reviewer neither replaces a GPT-6.2 reviewer,** which finds seven to ten.

The table does not rank the models: nine commits, each reviewed once, and every
document commit has a Claude co-author. The Claude Sonnet 5.5 reviews used the
`dontAsk` start; the first study's Claude Opus 5.5 reviews used plan mode, so the two
Claude rows differ in start as well as model. No owner decision is requested.

The scripts, the reviews, both judges' packets and replies and the table are retained
as
[`reviewer-recall-replay-added-reviewers`](../../data/evidence/reviewer-recall-replay-added-reviewers.sha256).
The figures are printed by `scripts/tabulate.py` into `results/table.txt`.

## Method

- **What is reused.** The nine prepared commit trees, the review brief, the 16 known
  defects, the judging brief and the rule are the first study's
  ([method](2026-11-25-reviewer-recall-replay.md#method)). `scripts/reviews.py` calls
  the first study's start function with two more configurations.
- **The reviewers.** Claude Sonnet 5.5 at High on Claude Code 2.1.329 and GPT-6.1 Terra
  at High on Codex CLI 0.171.0, the two the leaf names. No further configuration is
  added: the leaf allows one only where the diagnosis study gives a reason, and it
  gives none that a review would test.
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

| Defect | Kind | Sonnet High | Terra High | Found in the first study by |
| --- | --- | --- | --- | --- |
| A check that could not catch a file moved between packages | document | no | both judges | Sol, Astra High, Astra Medium |
| The poll interval taken as the uncertainty on publication time | document | no | both judges | Sol, Astra High, Astra Medium |
| A run cap sized against expected charges and not reservations | document | both judges | no | Sol, Opus High |
| A measured share attributed to the wrong model | document | both judges | no | Sol, Astra Medium |
| An event-stream probe that mishandles split line endings | code | both judges | no | Sol, Astra High, Astra Medium |
| Charges in flight not counted on a runner restart | code | no | both judges | Sol, Astra High, Astra Medium |
| A ledger writer and reader that disagree on uniqueness | code | no | both judges | every first-study reviewer |
| A fit check made before the context cut | code | both judges | no | none |

Neither finds the other eight. One judge and not the other credits Claude Sonnet 5.5
with a ninth, a document defect.

- **Pairs.** With each first-study reviewer, by both judges:

| Paired with | Union with Sonnet High | Sonnet adds | Union with Terra High | Terra adds |
| --- | ---: | ---: | ---: | ---: |
| GPT-6.2 Sol at Extra-high, 10 alone | 11 | 1 | 10 | 0 |
| GPT-6.2 Astra at High, 8 alone | 11 | 3 | 8 | 0 |
| GPT-6.2 Astra at Medium, 7 alone | 9 | 2 | 7 | 0 |
| Claude Opus 5.5 at High, 4 alone | 7 | 3 | 7 | 3 |
| Claude Opus 5.5 at Medium, 2 alone | 6 | 4 | 5 | 3 |

- **Findings and time.** Claude Sonnet 5.5 writes 64 findings in nine reviews, at 106
  to 435 seconds a review. GPT-6.1 Terra writes 26, at 37 to 86 seconds.
- **Judges.** The two judges give the same verdict on 30 of 32 cells. They differ on
  one document defect for Claude Sonnet 5.5, partial against found, and one code defect
  for GPT-6.1 Terra, not found against partial.
- **Tokens,** as each coding agent reported them for nine reviews: Claude Sonnet 5.5
  15.4 million cached input and 267,000 output; GPT-6.1 Terra 4.1 million input and
  19,000 output. They compare within a coding agent only.

## What this supports

Every statement is about these nine commits, each configuration as started here and
run once.

- A second reviewer from another family adds defects here whichever tier it is from:
  Claude Sonnet 5.5 adds one to three to a GPT-6.2 reviewer, and GPT-6.1 Terra adds
  three to a Claude Opus 5.5 reviewer.
- A smaller model of the same family as the first reviewer adds nothing here: GPT-6.1
  Terra's four defects are all found by each GPT-6.2 reviewer.
- GPT-6.1 Terra is the cheapest review measured here by a wide margin, and finds a
  quarter of the known defects.
- One defect that five first-study configurations missed is found by a middle model,
  so a larger model is not a superset of a smaller one on this set.
