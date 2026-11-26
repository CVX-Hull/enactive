---
owner: lead
status: historical
kind: measurement
date: '2026-11-25'
scope: 'Token use, context size, merges, delegations and check commands in the six Claude Code lead sessions retained for this repository, 31 October to 21 November 2026, read from the coding agent''s local transcripts for issue #974; counts only, no model call, no game'
---

# Lead cost per merged pull request

## At a glance

The three lead sessions whose context stayed under 400,000 tokens used 5.3 and 8.6
million tokens for each pull request they merged; the third merged none. The three
whose context passed 600,000 tokens used 12.0, 23.8 and 39.4 million. In the first
group at most 47% of a session's tokens were spent in requests whose context was above
300,000 tokens; in the second group 77% to 91% were.

Not known: how large or hard each merged change was, which differs between sessions and
is not controlled; the effort each lead ran at, which the transcripts do not record;
how many repairs a lead asked for; and anything about leads on Codex or Antigravity,
whose sessions were not read. Six sessions are six observations. No owner decision is
requested.

The script and its output are retained as
[`lead-cost-per-merged-pull-request`](../../data/evidence/lead-cost-per-merged-pull-request.sha256).
Every figure below is from that output.

## Method

- **What was read.** The Claude Code lead transcripts for this repository that hold at
  least 20 model requests, six sessions. The session that ran this measurement is left
  out. The script read usage figures, model names, tool names and the text of the
  lead's own shell commands, and kept none of the text.
- **Tokens** are, for each request counted once by its message identifier, the request's
  context (uncached input, cache read and cache write) plus its output.
- **Merges** are the distinct pull request numbers in the lead's own merge commands
  (`gh pr merge N` or a merge call on a numbered pull request). A merge made another
  way is not counted, and a queued merge that did not complete is.
- **Delegations** are the larger of the session's sub-agent starts and its sub-agent
  transcript files, plus its `tools/delegate.py` calls.
- **Check commands** are the lead's own shell commands that ran `pytest`,
  `tools/check.py` or a Node test command. They stand in for the lead rerunning a
  delegated result's acceptance check; the transcripts do not say which check answered
  which delegation.

## The six sessions

| Started | Models, by requests | Requests | Tokens | Largest context | Median context | Summarized | Tokens above 300,000 context | Merges | Tokens per merge |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 21 November | Fable 5.2: 106 | 106 | 26.3 M | 382,000 | 252,000 | 0 | 47% | 5 | 5.3 M |
| 21 November | Fable 5.2: 106 | 106 | 25.9 M | 353,000 | 246,000 | 0 | 41% | 3 | 8.6 M |
| 21 November | Opus 5.5: 97 | 97 | 18.0 M | 271,000 | 187,000 | 2 | 0% | 0 | none |
| 20 November | Fable 5.2: 1,127 | 1,127 | 433.1 M | 965,000 | 339,000 | 10 | 77% | 36 | 12.0 M |
| 31 October | Opus 5.5: 268 | 268 | 95.1 M | 632,000 | 365,000 | 0 | 80% | 4 | 23.8 M |
| 10 November | Fable 5.2: 574, Opus 5.5: 230 | 804 | 394.3 M | 963,000 | 482,000 | 4 | 91% | 10 | 39.4 M |

The two sessions of 21 November on Fable 5.2 each made 106 requests; they are distinct
transcripts.

## Delegation and the lead's own checks

| Started | Delegations | Lead's check commands | Check commands per delegation |
| --- | ---: | ---: | ---: |
| 21 November (5 merges) | 11 | 9 | 0.82 |
| 21 November (3 merges) | 6 | 16 | 2.67 |
| 21 November (no merge) | 6 | 0 | 0 |
| 20 November | 89 | 172 | 1.93 |
| 31 October | 5 | 29 | 5.8 |
| 10 November | 112 | 69 | 0.62 |

## What this supports

- In these six sessions the two with the smallest tokens per merge kept their context
  under 400,000 tokens, and the two with the largest had a median context of 365,000
  and 482,000 tokens.
- The session of 20 November reached 965,000 tokens and was summarized ten times; its
  median context was 339,000 and it used 12.0 million tokens per merge, between the two
  groups.
- Two sessions ran fewer than one check command for each delegation, and one ran none.
  That is a count of commands, not a finding that a result went unverified.
