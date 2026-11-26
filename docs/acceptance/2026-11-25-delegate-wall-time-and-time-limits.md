---
owner: lead
status: historical
kind: measurement
date: '2026-11-25'
scope: 'Wall time of the 244 delegated attempts in the attempts ledger at commit 7873720f, by role, configuration and the size of the merged change for the same issue, and the nine attempts that reached their time limit; a reading of existing rows for issue #976, with no new delegate run'
---

# Delegate wall time, change size and time limits

## At a glance

The attempts that reached their time limit were given limits inside the usual range of
their configuration, and the size of the change explains little. A reviewer on Claude
Opus 5.5 at High hands back in a median of 361 seconds and in 552 seconds at the 90th
percentile; the three such reviewers that timed out were stopped at 600 seconds. A
worker on the same model takes 735 seconds at the median and 1,658 at the 90th
percentile, repairs included; the five that timed out were stopped at 480 to 1,200
seconds. Across change sizes a reviewer's median wall time stays between 137 and 304
seconds. The one explorer that timed out had ten files to audit in 600 seconds; the
same audit as two briefs took 94 and 181 seconds.

The script and its output are retained as
[`delegate-wall-time-by-change-size`](../../data/evidence/delegate-wall-time-by-change-size.sha256).
Every figure below is from that output.

## Method and its limits

- **The rows** are the [attempts ledger](../../data/evaluation/coding-agent-attempts.jsonl)
  at commit `7873720f`: 244 rows, of which 80 worker, 144 reviewer and 14 explorer rows
  have a wall time.
- **Brief size is not recorded.** Briefs are not retained, so the merged change stands
  in: the files changed and lines added by every commit on main whose subject names the
  row's issue. 53 worker rows, 114 reviewer rows and 6 explorer rows have one. The
  stand-in is the whole issue's change, which is larger than one brief when an issue had
  several delegations.
- **A worker row's wall time includes its repairs**, so it is longer than one start.
- **The rows were not designed as an experiment.** The lead chose each configuration and
  each limit for the task, so configuration, task and limit are confounded.

## Wall time by size of the merged change

| Role | Added lines | Rows | Median | Largest | Timed out |
| --- | --- | ---: | ---: | ---: | ---: |
| Worker | under 150 | 5 | 446 s | 701 s | 0 |
| Worker | 150 to 499 | 10 | 577 s | 1,255 s | 0 |
| Worker | 500 to 1,499 | 11 | 764 s | 1,762 s | 0 |
| Worker | 1,500 and over | 27 | 822 s | 2,939 s | 5 |
| Reviewer | under 150 | 11 | 137 s | 504 s | 0 |
| Reviewer | 150 to 499 | 35 | 148 s | 705 s | 0 |
| Reviewer | 500 to 1,499 | 11 | 304 s | 699 s | 0 |
| Reviewer | 1,500 and over | 57 | 183 s | 600 s | 3 |

Six explorer rows have a merged change, too few to bin.

## Wall time by configuration, attempts that handed back

| Role and configuration | Rows | Median | 90th percentile | Largest |
| --- | ---: | ---: | ---: | ---: |
| Reviewer, Claude Opus 5.5 at High | 44 | 361 s | 552 s | 705 s |
| Reviewer, Claude Opus 5.5 at Medium | 10 | 193 s | 418 s | 418 s |
| Reviewer, GPT-6.2 Astra at High | 38 | 196 s | 417 s | 495 s |
| Reviewer, GPT-6.2 Astra at Medium | 36 | 118 s | 253 s | 282 s |
| Reviewer, GPT-6.2 Sol at Extra-high | 9 | 287 s | 529 s | 529 s |
| Worker, Claude Opus 5.5 at High | 24 | 735 s | 1,658 s | 2,939 s |
| Worker, GPT-6.2 Sol at High | 14 | 917 s | 1,109 s | 1,255 s |
| Worker, GPT-6.2 Sol at Extra-high | 29 | 518 s | 789 s | 1,311 s |

## The nine attempts that timed out

Eight are on issue #937, whose merged change is 13,780 added lines in 170 files. All
eight ran on Claude Opus 5.5 at High: three reviewers stopped at 600 seconds and five
workers stopped at 480, 480, 900, 1,200 and 1,200 seconds. On the same issue three
reviewers and four workers on that configuration handed back, in at most 466 and 822
seconds, and nine GPT-6.2 Astra reviewers at High handed back in at most 414 seconds.
The ninth is an explorer on GPT-6.2 Astra at High, stopped at 600 seconds on an audit
of ten files for issue #945.

## What this supports

- A time limit set near a configuration's 90th percentile stops attempts that would
  have handed back. The limits that were reached sit at or below it.
- Change size alone does not predict a reviewer's wall time in these rows.
- For an audit across many files, two briefs finished where one did not. That is one
  observation.
