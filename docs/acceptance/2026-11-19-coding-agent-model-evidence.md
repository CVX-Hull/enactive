---
owner: lead
status: historical
kind: review
date: '2026-11-19'
scope: 'Public figures and local measurements behind the choice of model for engineering work, with how each was read; no gameplay and no paid model call'
---

# Coding-agent model evidence read on 19 November 2026

## At a glance

Public benchmarks support three things for this repository's engineering work. The
leading configurations score within a few points of each other on hard changes,
codebase questions and terminal tasks. For the one model read at every setting, the
effort setting moved the score by ten points and the highest setting scored lower.
The two smallest models scored far below the leading configurations on codebase
questions and terminal tasks, and near the bottom on mergeable patches. No public
evidence was found for house-style documents, dated records, reading run ledgers or
C++ in a large codebase, which is most of what this repository merges. Nothing here was
observed on this repository's own work.

## How each figure was read

Every figure below carries one of these marks:

- **Read directly:** the lead read the maintainer's page in a browser.
- **Summariser:** a sub-agent fetched the maintainer's page through a page summariser.
  A small model read the page, so a row could be transposed; nobody rechecked it.
- **Snippet:** seen only in a search result or a third party's summary.
- **Vendor:** the model's own maker reported it.
- **Measured here:** run on this machine on the date given.

A public agent score is a coding agent and a model together, nearly always the model in
its maker's own agent; one terminal-task row below is a model in another agent. This
record treats a gap of a few points as too small to act on. The reason
is a study of 60,000 runs on a different benchmark, where a single run's pass rate
swung by 2.2 to 6.0 points between identical runs
([Bjarnason and others](https://arxiv.org/abs/2602.07150), summariser); it is an
analogy, not a measurement of these boards.

## Coding-agent index

Artificial Analysis Coding Agent Index v2.1
([page](https://artificialanalysis.ai/agents/coding-agents)). It is the equal-weight
mean of three parts, each the mean of three attempts per task: mergeable patches
(FrontierCode-AA 2.0, 132 tasks), terminal tasks (Terminal-Bench 4.1, 66 tasks) and
codebase questions (SWE-Atlas-QnA-AA, 124 tasks). The tasks are private, no language
breakdown is published, and one entrant's model judges part of it.

Read directly on 19 November 2026 (the page lists one row per coding agent):

| Coding agent and model | Index | Minutes per task | Cost per task |
| --- | ---: | ---: | ---: |
| Antigravity CLI, Gemini 4 Neon at Extra-high | 59 | 30.5 | $6.86 |
| Claude Code, Claude Fable 5.2 at Extra-high | 58 | 53.3 | $15.47 |
| Codex, GPT-6.2 Astra at Max | 53 | 25.1 | $5.12 |

The cost is the pay-per-token price of the run, not what a subscription is charged. It
is used here only as a rough proxy for how much quota a setting consumes; no
subscription usage was measured.

By effort setting, from the same site's comparison pages (summariser, 19 November 2026):

| Coding agent and model | Index | Patches | Questions | Minutes | Cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| Claude Code, Fable 5.2 at Extra-high | 58 | 49 | | 53 | $15.47 |
| Claude Code, Fable 5.2 at High | 58 | | | 31 | $7.51 |
| Claude Code, Fable 5.2 at Max | 56 | | | 132 | $44.22 |
| Claude Code, Fable 5.2 at Medium | 53 | | 64 | | $2.89 |
| Claude Code, Fable 5.2 at Low | 48 | | | | |
| Claude Code, Opus 5.5 at Max | 58 | 44 | 66 | 66 | $12.61 |
| Claude Code, Sonnet 5.5 at Max | 56 | | 64 | 84 | $11.40 |
| Claude Code, Haiku 5.5 at Max | | 23 | 34 | 78 | $2.25 |
| Codex, GPT-6.2 Astra at Extra-high | 53 | 43 | | 16.5 | $3.20 |
| Codex, GPT-6.2 Astra, High to Max | 52 to 53 | | 54 to 55 | | $2.37 to $5.12 |
| Codex, GPT-6.2 Sol at Extra-high | 50 | | | 12.6 | $0.90 |
| Codex, GPT-6.2 Sol at Max | 49 | | | | |
| Codex, GPT-6 Luna at Max | | 24 | 38 | | $0.19 |
| Antigravity, Gemini 4 Neon at Extra-high | 59 | 43 | 68 | 30.5 | $6.86 |
| Antigravity, Gemini 4 Carbon at High | | | 64 | 33.6 | $9.75 |
| Antigravity, Gemini 4 Hydrogen at Extra-high | | | | 32.1 | $4.45 |
| Antigravity, Gemini 4 Argon | | 25 | | | |

An empty cell was not read. What the table supports:

- **Close at the top.** Neon at 59 leads Fable and Opus, both at 58, by one point.
- **Effort.** Fable at Max scores below Fable at High at about six times the cost and
  four times the time. Astra reads 52 to 53 from High to Max. Sol at Extra-high reads
  one point above Sol at Max. Fable at Low reads ten points below Fable at High; no
  other model was read at Low.
- **The smallest models.** Haiku and Luna, both read at Max, score 34 and 38 on
  codebase questions against 64 to 68, and 23 and 24 on mergeable patches against 43
  to 49.

## Terminal tasks

Terminal-Bench 4.1 leaderboard ([page](https://www.tbench.ai/leaderboard), summariser,
19 November 2026), with its own intervals:

| Coding agent and model | Score |
| --- | --- |
| Claude Code, Opus 5.5 at Max | 65.8% ±3.1 |
| Claude Code, Fable 5.2 at Max | 65.8% ±2.8 |
| Antigravity, Gemini 4 Carbon at High | 64.5% ±3.2 |
| Claude Code, Sonnet 5.5 at Max | 63.9% ±3.0 |
| Codex, GPT-6.2 Astra at Max | 62.1% ±2.3 |
| Codex, GPT-6.2 Sol at Max | 61.5% ±2.8 |
| Claude Code, Haiku 5.5 | 40.0% |
| Gemini 3.8 Flash, in another agent | 18.2% |
| Codex, GPT-6 Luna | 15.2% |

The intervals of the top six overlap.

## Review

- **Reviewer precision and recall.** ReviewBench ([page](https://review-bench.ai),
  summariser): reviewer products built on Opus 5.5 score 93% precision and 55% to 61%
  recall on high-severity issues; one built on Sonnet 5.5 scores 94% and 48%. No entry
  uses a GPT-6 or Gemini 4 model. The benchmark's maintainer did not verify the entries.
- **A second family.** One preprint ([Song](https://arxiv.org/abs/2610.01471), read
  through a third party's summary): on code, a fresh reviewer of the author's own model
  scored about the same as the best reviewer of another model; on prose, the other
  model scored 42% against 25%; a third reviewer added little. A single author and a
  second-hand reading: weak support.
- **Central verification.** One paper ([Kim and others](https://arxiv.org/abs/2512.08296),
  snippet): independent agents amplified errors 17.2 times against 4.4 times when one
  orchestrator checked their work, and every multi-agent form lost on sequential tasks.

## Wrong answers and stale assumptions

- **Wrong-answer rate.** Artificial Analysis factual-recall evaluation (summariser):
  Fable 5.2 has the highest net score, 64 to 67 across settings; Gemini 4 Carbon and
  Argon have the lowest wrong-answer rate listed, 4%.
- **Contamination.** One analysis (Endor Labs, summariser) removed 65 solutions that
  Fable 5.2 recalled from training and its pass rate fell from 94.4% to 63.7% on that
  benchmark. A public-repository score can overstate a model.
- **Harness effects.** A vendor's write-up
  ([Cursor](https://cursor.com/blog/reward-hacking-coding-benchmarks), summariser)
  found that sealing the environment moved one score from 87.1% to 73.0%. Vendor
  figures run rivals on the vendor's own setup.
- **Silent change.** A maker's postmortem of April 2026, read only in a news summary
  and not at its source, attributes a month of
  degraded results to a lowered default effort, a caching defect and one added
  system-prompt line. A coding agent's version and its default effort are therefore
  reasons to re-read a row.

## Measured here

On 19 November 2026 (20 November UTC), on the owner's machine:

- **Versions.** Claude Code 2.1.329, Codex CLI 0.167.1, Antigravity CLI 1.5.13.
  Correction of 20 November 2026: 0.167.1 was read early in the evening. The Codex
  CLI's 0.171.0 install is dated 22:16 local, before the selector check below at 23:09,
  so that check and every review that evening ran on 0.171.0.
- **Claude Code models.** The delegation call offers the selectors `fable`, `opus`,
  `sonnet` and `haiku`.
- **Codex selectors.** `gpt-6-luna`, `gpt-6.1-terra`, `gpt-6.2-sol` and `gpt-6.2-astra`
  each answered a one-word prompt through `codex exec` in three to five seconds. No
  full listing of Codex models was read. The tracked role files were not exercised as
  sub-agents on either host.
- **Antigravity models.** `agy models` listed Gemini 4 Neon and Hydrogen at Low,
  Medium, High and Extra-high; Gemini 4 Carbon and Argon at Low, Medium and High; three
  orchestrator models; Gemini 3.8 Flash at Low, Medium and High; Claude Opus 5.5 and
  Sonnet 5.5 at Low, Medium and High; and one open-weight model.
- **Antigravity role files.** `agy agents` listed none of the four tracked role files
  from the worktree, from a scratch copy, or from that copy after `git init`. The cause
  was not found.
- **Antigravity Auto mode.** With `--mode auto` the CLI printed that Auto is not
  available for the account, yet a shell command on no allow list ran unattended; with
  `--mode accept-edits` the same command was refused, while the result still read
  `SUCCESS` with exit zero and listed the refusal under `denied_actions`. One run each.
  An exit code or status line from that CLI is not evidence of what ran.

No model call was paid for: every run used an included subscription.

## No public evidence found

- Documents in a house style, and dated evidence records.
- Reading run ledgers, logs and tables. One public suite covers data analysis, but its
  page could not be read by the sub-agent.
- C++ against a large existing codebase.
- Fabricated quotations or citations in review reports.
- Long autonomous work: the one public time-horizon page a sub-agent read (METR,
  summariser) said it is no longer updated and listed none of these models.
- Code review by a GPT-6 or Gemini 4 model.
- Any measured ranking of models as leads or orchestrators.

## Limits

These are other people's tasks, in other people's harnesses, read on one day, mostly
through a summariser. They show which models to try and which to avoid; they do not
show which model is best on this repository. The rows that matter most here have no
public figure at all.
