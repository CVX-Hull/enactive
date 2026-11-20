---
owner: lead
status: historical
kind: measurement
date: '2026-11-20'
scope: 'Token counts by model for the lead and its sub-agents, read from the coding agents'' own local transcripts for this repository over eight days; no game, no model call'
---

# Where the coding agents' tokens went, 13 to 20 November 2026

## At a glance

In the one lead session of 19 and 20 November, the lead's own requests used 283 million
tokens and its 62 sub-agents used 98 million. At list prices that is about $150 to $170,
of which the lead is about 72%. Nearly all of the lead's tokens (98.9%) were re-reads of
its own earlier context: the context sat between about 320,000 and 965,000 tokens for
603 requests, and was summarized twice. The sub-agents were not the main cost.

Over the eight days, a second, longer session led on Claude Opus 5.5 and its
general-purpose sub-agents on the same model account for most of the tokens: 14,540
sub-agent requests on that model against 1,777 on Claude Fable 5.2.

The work was done on subscription quota, so no money was spent; the dollar figure is an
equivalent at list prices and is a way to compare, not a bill. One session is one
observation.

## What was read

- **Claude Code transcripts** for this repository: every file changed on or after
  13 November 2026. That is two lead sessions and 1,478 sub-agent files. Each response
  was counted once by its message identifier; a response written on several lines was
  counted from the line with the largest token sum. No identifier appeared in two files.
- **Codex CLI session files** from 13 November whose working directory is at or under
  this checkout: 126 sessions, 106 of them sub-threads. Each was counted from its last
  cumulative total and attributed to the model of its last turn.
- Only counts were read. No transcript content is in this record or in the retained
  files.

The script and its output are retained as
[`coding-agent-token-use`](../../data/evidence/coding-agent-token-use.sha256). The
transcripts stay on the host and are not retained.

## The lead session of 19 and 20 November

| Who | Model | Requests | Cache write | Cache read | Output |
| --- | --- | ---: | ---: | ---: | ---: |
| Lead | Claude Fable 5.2 | 603 | 2,224,475 | 280,098,275 | 798,891 |
| Sub-agents | Claude Sonnet 5.5 | 464 | 2,524,875 | 49,305,236 | 433,264 |
| Sub-agents | Claude Opus 5.5 | 317 | 1,261,003 | 36,543,054 | 252,347 |
| Sub-agents | Claude Haiku 5.5 | 31 | 249,756 | 3,565,224 | 42,654 |
| Sub-agents | Claude Fable 5.2 | 25 | 180,973 | 3,162,770 | 57,463 |

Uncached input was under 1,300 tokens in every row.

The lead's context per request, as the median of each quarter of the session: 325,920,
then 617,297, then 388,904, then 743,067 tokens. The largest was 965,335. The context
was summarized twice.

Sub-agents by role in that session, with the tokens of one run summed over its requests:

| Role | Runs | Median | Largest | Models that ran |
| --- | ---: | ---: | ---: | --- |
| Explorer | 20 | 1,607,421 | 6,211,168 | Sonnet 19, Haiku 1 |
| Reviewer | 6 | 2,409,030 | 6,195,863 | Opus 6 |
| General-purpose | 6 | 950,003 | 1,545,641 | Opus 3, Sonnet 3 |
| Worker | 4 | 6,207,519 | 13,997,703 | Opus 2, Fable 1, Sonnet 1 |
| Locator | 1 | 265,896 | 265,896 | Haiku 1 |

## The eight days

| Who | Model | Requests | Cache write | Cache read | Output |
| --- | --- | ---: | ---: | ---: | ---: |
| Leads | Claude Opus 5.5 | 2,791 | 6,647,348 | 1,392,591,293 | 1,857,169 |
| Leads | Claude Fable 5.2 | 1,432 | 4,561,922 | 642,458,982 | 1,787,404 |
| Sub-agents | Claude Opus 5.5 | 14,540 | 102,780,756 | 1,279,235,337 | 15,218,401 |
| Sub-agents | Claude Fable 5.2 | 1,777 | 10,414,035 | 265,007,163 | 2,593,873 |
| Sub-agents | Claude Sonnet 5.5 | 1,250 | 5,326,855 | 180,659,299 | 1,210,397 |
| Sub-agents | Claude Haiku 5.5 | 85 | 677,443 | 8,670,187 | 142,545 |

Of the 1,478 sub-agent runs, 1,306 were general-purpose, 1,247 of them on Opus. The
other lead session had a context whose quarterly medians ran from 353,737 to 510,268
tokens and was summarized nine times.

Codex, by the model of each session's last turn:

| Model | Sessions | Input, cached included | Of which cached | Output |
| --- | ---: | ---: | ---: | ---: |
| The automatic approval reviewer | 54 | 114,353,532 | 106,593,536 | 101,254 |
| GPT-6.2 Astra | 1 | 81,683,538 | 80,818,304 | 130,756 |
| GPT-6.1 Sol | 19 | 80,550,592 | 78,711,040 | 496,374 |
| GPT-6.2 Sol | 11 | 41,351,431 | 40,010,496 | 110,611 |
| GPT-6 Luna | 10 | 18,605,192 | 17,677,184 | 89,931 |
| GPT-6.1 Terra | 3 | 3,724,511 | 3,543,936 | 30,590 |

## The price equivalent

The list prices used were read from the vendor's pricing page on 20 November 2026
through a tool that summarizes the page, and were not checked a second way. Per million
tokens, as cache write for five minutes or one hour, cache read, and output: Fable 5.2
$10 or $16, $0.20, $40; Opus 5.5 $5 or $8, $0.20, $20; Sonnet 5.5 $2.50 or $4, $0.10,
$10; Haiku 5.5 above 100,000 prompt tokens $0.625 or $1, $0.05, $2.50.

For the lead session of 19 and 20 November that gives $110 to $124 for the lead and $39
to $48 for the sub-agents; the range is the two cache-write prices, since the
transcripts' top-level fields do not say which applied. The lead's part divides into
about $56 of cache reads, $22 to $36 of cache writes and $32 of output.

## What this supports

- In a long lead session, the lead's own context is the main cost, and it is paid again
  on every request. Delegating reading to cheaper models saves little while that context
  stays large.
- The roles ran on the models their role files name in that session, apart from the
  workers and general-purpose runs the lead gave a model by hand.
- On Codex, the automatic approval reviewer used more tokens for this repository than
  any model the lead chose.

## Limits

- One lead session in detail; the eight-day totals are dominated by one other session.
- The price equivalent rests on prices that were not double-checked, and no money was
  charged. What a token costs against a subscription's quota windows was not found.
- The window is by file change time, so a sub-agent file rewritten later would be
  counted. Which lead started each general-purpose run was not traced.
- Whether a sub-agent ended at a turn limit or without a report cannot be read from the
  transcripts.
- A Codex session that changed model is counted under its last model. Sessions in
  worktrees outside the checkout's path are missed.
- Antigravity's usage was not measured.
