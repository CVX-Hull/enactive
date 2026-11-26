---
owner: lead
status: historical
kind: study
date: '2026-11-26'
scope: 'Defect recall of the current Claude Code reviewer start on the nine commits of the reviewer recall replay, for issue #1013: Claude Opus 5.5 at High reviewing each commit once through the tracked delegate call, scored by the replay''s two judges and rule; subscription quota only, no game launch, no game input'
---

# Reviewer recall replay: the current Claude Code reviewer start

## At a glance

The [reviewer recall replay](2026-11-25-reviewer-recall-replay.md) scored Claude Opus
5.5 at High through the plan-mode start the Claude Code reviewer used then, and through
an experimental start without plan mode. The reviewer has since moved to a third start
([start check](2026-11-26-reviewer-start-check.md)). This study runs that current start
on the same nine commits, brief, judges and rule.

| Claude Opus 5.5 at High, as started | Found by both judges, of 16 | By either judge | Documents, of 10 | Code, of 6 | Wall time, nine reviews |
| --- | ---: | ---: | ---: | ---: | ---: |
| Plan-mode start, first study | 4 | 7 | 3 | 1 | 3,979 s |
| Experimental start without plan mode, first study | 6 | 6 | 3 | 3 | 3,753 s |
| **Current start** | **6** | **8** | **4** | **2** | **4,424 s** |

- **The current start finds six of the sixteen defects,** as many as the experimental
  start and two more than the plan-mode start. It finds every defect the plan-mode
  start found.
- **It differs from the experimental start by one defect each way.** It finds a wrong
  attribution in a document that the experimental start missed, and misses the code
  defect in which the host decided whether a knowledge update fit before applying the
  context cut.
- **It adds nothing to GPT-6.2 Sol at Extra-high,** which finds ten, all six among
  them. It adds two defects to GPT-6.2 Astra at High and two to Astra at Medium; each
  of those adds three or four to it.
- **The start refuses twelve shell commands in the nine reviews** and every review is
  handed back. Whether a refused command cost a finding is not measured.

One run of nine commits does not separate six from four: the three Claude Opus rows
differ by two defects, and the two judges disagree on two of this row's sixteen
verdicts. No routing first choice moves. No owner decision is requested.

The scripts, the nine reviews, both judges' packets and replies and the table are
retained as
[`reviewer-recall-current-claude-code-start`](../../data/evidence/reviewer-recall-current-claude-code-start.sha256).
The figures are printed by `scripts/tabulate_current.py` into `results/table.txt`.

## Method

- **What is reused.** The commit set, the review brief, the 16 known defects, the
  judging brief and the rule are the first study's
  ([method](2026-11-25-reviewer-recall-replay.md#method)), taken from its sealed
  evidence. The nine commit trees were rebuilt from the commit set by the first study's
  own prepare step: each holds the commit and its parent only, with the current
  reviewer role file and glossary added where the old tree lacks them.
- **The reviewer.** Claude Opus 5.5 at High on Claude Code 2.1.329, started by
  `tools/delegate.py` at commit `7c4bec87` with the tracked reviewer start:
  `--permission-mode dontAsk`, the read, search and file-listing tools allowed, the
  editing tools disallowed, and the default output style. Each commit is reviewed once,
  three commits at a time, with a 1,500-second limit.
- **The judges.** GPT-6.2 Sol at Extra-high on Codex CLI 0.171.0 and Claude Opus 5.5 at
  High on Claude Code 2.1.329, as in the first study. A defect counts as found when
  both judges say found.
- **The earlier rows** are the first study's sealed verdicts, read by the same script.

## Results

| Defect | Kind | Current start | Plan-mode start | Experimental start | GPT-6.2 Sol at Extra-high |
| --- | --- | --- | --- | --- | --- |
| K01 | documents | both | both | both | both |
| K04 | documents | both | both | both | both |
| K05 | documents | one judge | neither | neither | both |
| K06 | documents | one judge | one judge | neither | neither |
| K07 | documents | both | both | both | both |
| K09 | documents | both | one judge | neither | both |
| K11 | code | both | one judge | both | both |
| K15 | code | both | both | both | both |
| K16 | code | neither | neither | both | neither |

The other seven defects (K02, K03, K08, K10, K12, K13, K14) are found by neither judge
in any of the three Claude Opus rows. GPT-6.2 Sol finds K02, K03 and K13 of them.

- **Pairs, by both judges.** With the plan-mode start the union is 6: the current
  start adds K09 and K11 and the plan-mode start adds nothing. With the experimental
  start the union is 7. With GPT-6.2 Sol the union is 10, with Astra at High 10 and
  with Astra at Medium 9.
- **Findings.** The nine reviews hold 72 numbered findings by the first judge's count,
  against 70 for the experimental start. Findings other than the sixteen known defects
  were not checked, so precision is not measured.
- **Judges.** The two judges give the same verdict on 14 of the 16 defects. On K05 and
  K06 the first judge says partial and the second says found.
- **Time and tokens.** Reviews take 286 to 755 seconds, 4,424 seconds in all. Tokens
  reported: 710 input, 46.0 million read from cache, 1.33 million written to cache and
  352,000 output.
- **Refused commands.** The start reports twelve refused shell commands across eight of
  the nine reviews: searches with `grep` piped or chained, `git` calls, and short
  Python, `jq` and Node scripts. The reviewer went on with the allowed tools each time.

## Attempts

Every start is a row in the
[attempts ledger](../../data/evaluation/coding-agent-attempts.jsonl): nine reviews and
twenty-four judging starts.

- **Six judging starts returned no verdict.** The judging start tells the judge to read
  the explorer role file, and three of the rebuilt trees, from commits older than that
  file, did not hold it. Both judges stopped on those three packets and said why. The
  role file was added to the three trees and the six starts were made again; the first
  six are kept and marked not used. The first study's trees held the file, so this is a
  fault of the rebuild and not of the judges.

## Limits

- **One run.** Each commit is reviewed once. The first study's rows for the same model
  differ from this one by start, by day and by chance, and the set cannot say how much
  of the two-defect difference each accounts for.
- **A judge sees one review in a packet.** The first study's packets held two to five
  reviews under shuffled labels. Here each packet holds the one review, so the judge
  is not comparing reviews, and a judge from the reviewer's own family scores it.
- **The set is the first study's:** nine commits, sixteen defects found later, and
  every document commit has a Claude co-author
  ([limits](2026-11-25-reviewer-recall-replay.md#limits)).
- **Quota.** Before the starts the Claude Code week stood at 52% used and the Codex
  week at 60% used. No paid overflow was used.
