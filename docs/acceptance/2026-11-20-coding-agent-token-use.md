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
tokens and its 37 sub-agents used 98 million. At list prices that is about $150 to $172,
of which the lead is 72% to 74%. Of the lead's tokens, 98.9% were re-reads of its own
earlier context, and those re-reads are about half of the lead's price equivalent. Over
603 requests the lead's context had a median of 325,920 to 743,067 tokens in each
quarter of the session and a largest size of 965,335, and it was summarized twice. In
this session the sub-agents were not the main cost.

Over the eight days, sub-agents on Claude Opus 5.5 made 14,540 requests against 1,777
on Claude Fable 5.2, and 1,247 of the 1,306 general-purpose runs were on Opus.

The work was done on subscription quota, so no money was spent; the dollar figure is an
equivalent at list prices and is a way to compare, not a bill. One session is one
observation.

## What was read

- **Claude Code transcripts** for this repository: every file changed on or after
  13 November 2026, with every qualifying response in each such file, whatever its own
  time. That is two lead sessions and 1,478 sub-agent files. Only responses that carry
  a model and usage figures were counted. Each was counted once by its message
  identifier, or by its request or line identifier where it has none: within a file the
  line with the largest token sum was kept, and across files the first occurrence. No
  such identifier appeared in two files.
- **Codex CLI session files** changed from 13 November whose working directory is at or
  under this checkout: 126 sessions, 106 of them sub-threads. A session was counted from
  its last cumulative total and attributed to the model of its last turn. 98 sessions
  had such a total and are in the table; the other 28 are not counted.
- The script read usage figures, model names, identifiers and the types of content
  blocks. It kept no transcript text, and none is in this record or the retained files.

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
to $48 for the sub-agents, $150 to $172 together; the range is the two cache-write
prices, since the transcripts' top-level fields do not say which applied. The lead's
share is 74% at the five-minute price and 72% at the one-hour price. The lead's part
divides into about $56 of cache reads, $22 to $36 of cache writes and $32 of output.
Uncached input is left out, and the Haiku price above 100,000 prompt tokens is applied
to all 31 Haiku requests although their sizes were not read one by one.

## What this supports

- In this one lead session the lead's own requests were most of the price equivalent,
  and re-reading its context was about half of the lead's part. No session with a
  smaller context or with less delegation was measured beside it, so this does not show
  how much a smaller context would save.
- Which model each sub-agent ran on is in the tables. Why is not: the transcripts do
  not say whether a role file or the lead chose it. One explorer ran on Haiku although
  the explorer role file names Sonnet.
- Among the 98 Codex sessions with a total, the automatic approval reviewer is the
  largest group by tokens.

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
