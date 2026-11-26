---
owner: lead
status: historical
kind: measurement
date: '2026-11-25'
scope: 'Wall time of the 244 delegated attempts in the attempts ledger at commit 7873720f, by role, configuration and the size of the merged change for the same issue, and the nine attempts that reached their time limit; a reading of existing rows for issue #976, with no new delegate run'
---

# Delegate wall time, change size and time limits

## At a glance

Eight of the nine attempts that reached their time limit ran on Claude Opus 5.5 at
High, with limits that other attempts on that configuration have exceeded and still
handed back. Its reviewers were stopped at 600 seconds, and its longest review that
handed back took 705. Its workers were stopped at 480 to 1,200 seconds, and its worker
rows run to 1,658 seconds at the 90th percentile, repairs included. A reviewer's median
wall time does not rise steadily with the size of the merged change (137, 148, 304 and
183 seconds across four size bins); a worker's does (446 to 822 seconds). The ninth
timeout is an explorer given ten files to audit in 600 seconds.

Not known: the size of any brief, since briefs are not retained and the merged change
for the issue stands in; and whether a stopped attempt would have handed back with more
time. No owner decision is requested.

The script and its output are retained as
[`delegate-wall-time-by-change-size`](../../data/evidence/delegate-wall-time-by-change-size.sha256).
The tables are from that output. The explorer figures are from the ledger rows for
issue #945.

## Method and its limits

- **The rows** are the [attempts ledger](../../data/evaluation/coding-agent-attempts.jsonl)
  at commit `7873720f`: 244 rows, of which 80 worker, 144 reviewer and 14 explorer rows
  have a wall time.
- **Brief size is not recorded.** The merged change stands in: the files changed and
  lines added by every commit on main whose subject names the row's issue. 53 worker
  rows, 114 reviewer rows and 6 explorer rows have one. The stand-in is the whole
  issue's change, shared by every attempt on that issue.
- **A worker row's wall time includes its repairs**, so it is longer than one start.
- **Two medians.** The size table gives the ordinary median. The configuration table
  gives the upper median, the higher of the two middle values when the count is even,
  and the 90th percentile as the value at nine tenths of the way through the sorted
  rows.
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

| Role and configuration | Rows | Upper median | 90th percentile | Largest |
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

The ninth is an explorer on GPT-6.2 Astra at High, stopped at 600 seconds on issue
#945. Its ledger reason names a ten-file audit. Two explorers on GPT-6.2 Astra at
Medium then handed back in 94 and 181 seconds on briefs that split the audit. The split
changed the effort as well as the size of each brief, and the two briefs name nine
files between them.

## What this supports

- A 600-second limit is shorter than some reviews on Claude Opus 5.5 at High that hand
  back, and 480 to 1,200 seconds is shorter than many of its worker rows.
- 900 seconds is longer than every recorded review that handed back, and 2,400 seconds
  is longer than every recorded worker row but two (2,666 and 2,939 seconds, the
  second in the table above, the first read from the ledger).
- A reviewer's median wall time does not rise steadily with the merged change's size in
  these rows.
- One audit that timed out as a single brief finished as two, at a lower effort.
