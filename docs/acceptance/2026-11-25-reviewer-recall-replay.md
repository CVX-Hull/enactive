---
owner: lead
status: historical
kind: study
date: '2026-11-25'
scope: 'Replay of clean-context review on nine past commits of this repository that hold sixteen defects later fixed, for issue #973: five reviewer configurations from two model families given the same commit and brief, two blind judges; subscription quota only, no game launch, no game input'
---

# Reviewer recall replay

## At a glance

Five reviewer configurations each reviewed nine past commits that hold sixteen defects
fixed later. Counting a defect as found only when both judges said so, GPT-6.2 Sol at
Extra-high found 10, GPT-6.2 Astra at High 8, GPT-6.2 Astra at Medium 7, Claude Opus
5.5 at High 4 and Claude Opus 5.5 at Medium 2. Every defect an Opus configuration found
was also found by a GPT-6.2 configuration; six were found by GPT-6.2 configurations
only, and six by no configuration. The two judges gave the same verdict on 73 of 80
cells.

The counts do not rank the models as reviewers. Seven of the nine commits carry a
Claude co-author trailer, so for most of the set the Opus configurations reviewed work
their own family wrote, and every defect in the set had already passed this
repository's review once. The defect statements were written by GPT-6.2 Sol explorers.
Sixteen defects are a small sample.

Not known: who reviewed these commits originally; whether each review's other findings
are correct, since only the known defects were judged; and anything about a Gemini
configuration, because every Gemini start was refused on quota or returned nothing. No
owner decision is requested.

The scripts, the set, every review, the judges' packets and replies and the scoring
output are retained as
[`reviewer-recall-replay`](../../data/evidence/reviewer-recall-replay.sha256). The
figures below are from `results/agreement.txt` and `results/score-sol-judge.txt` in it.

## Method

- **The set.** Three explorers on Codex GPT-6.2 Sol at Extra-high traced the defects
  repaired by `ea2dfbcb` (#946), `b8c41ec9` (#923), `30332789` (#918), `dff250b9`
  (#844), `fdbf3f12` (#867) and `b1c2a926` (#820) to the single commit that introduced
  each, and wrote each defect down without reference to its fix
  (`defect-tracing/`). The lead kept the nine introducing commits whose diff is at most
  2,231 added lines and checked every quoted defective line against the introducing
  commit (`scripts/build_set.py`; six multi-line quotations were checked by hand).
  `results/set.json` is the set.
- **Isolation.** Each commit was reviewed in a standalone shallow clone holding that
  commit and its parent only, so its fix is not in the history. The clone also held the
  current reviewer role file and glossary where the old tree lacked them, and the
  commit's diff as a file.
- **The reviews.** Every configuration got the same brief (`scripts/replay.py`): review
  the commit as before a merge, quote each finding's passage, mark it confirmed or
  suspicion. Each start ran once through `tools/delegate.py` with a 1,500-second limit.
- **Judging.** For each commit a judge read the known defects and the five reviews under
  shuffled neutral labels and gave each cell `found`, `partial` or `not_found`
  (`scripts/judge.py`). A review found a defect when a finding was about the same
  passage or behaviour and said what was wrong in a way that matched. The first judge
  was Codex GPT-6.2 Sol at Extra-high and the second Claude Code Claude Opus 5.5 at
  High, on the same packets. The lead read three verdicts against the review texts and
  agreed with each.
- **One lead error.** Three older clones lacked the explorer role file the judges are
  told to read, and six judge starts stopped there; the lead added the file and started
  them again. No review was affected.

## The set

| Commit | Kind | Added lines | Known defects | Co-author trailer |
| --- | --- | ---: | ---: | --- |
| `40960889` (#842) | documents | 311 | 3 | Claude Fable 5.2 |
| `4dde98e0` (#843) | documents | 504 | 4 | Claude Fable 5.2 |
| `db98f7cf` (#827) | documents | 190 | 1 | Claude Fable 5.2 |
| `3942ae55` (#865) | documents | 917 | 2 | Claude Fable 5.2, Claude Opus 5.5 |
| `c3133466` (#380) | code | 122 | 1 | Claude Opus 5.5 |
| `89951f37` (#856) | code | 2,231 | 2 | Claude Fable 5.2, Claude Opus 5.5 |
| `749e7cc6` (#542) | code | 298 | 1 | none |
| `909ca9dd` (#416) | code | 893 | 1 | Claude Opus 5.5 |
| `305cecc5` (#902) | code | 1,446 | 1 | none |

The trailers are read with `git log -1 --format=%b COMMIT`.

## Known defects found

Found by both judges, with found by at least one judge in brackets.

| Configuration | Of 16 | Documents, of 10 | Code, of 6 | Findings in all | Wall time, nine reviews |
| --- | ---: | ---: | ---: | ---: | ---: |
| GPT-6.2 Sol at Extra-high | 10 (10) | 7 (7) | 3 (3) | 80 | 2,758 s |
| GPT-6.2 Astra at High | 8 (9) | 5 (6) | 3 (3) | 98 | 2,021 s |
| GPT-6.2 Astra at Medium | 7 (7) | 4 (4) | 3 (3) | 79 | 1,105 s |
| Claude Opus 5.5 at High | 4 (7) | 3 (5) | 1 (2) | 76 | 3,979 s |
| Claude Opus 5.5 at Medium | 2 (3) | 1 (2) | 1 (1) | 58 | 2,478 s |

All 45 reviews handed back. Token counts as each coding agent reported them, which
compare within a coding agent only: Claude Opus 5.5 at High 35.9 million cached input,
1.17 million cache write and 331,000 output, and at Medium 18.0 million, 0.85 million
and 199,000; GPT-6.2 Astra at High 19.1 million input and 63,000 output, and at Medium
9.2 million and 34,000; GPT-6.2 Sol at Extra-high 17.0 million and 123,000.

## By defect

B is found by both judges, 1 by one judge only, a dash by neither.

| Defect | Kind | Opus High | Opus Medium | Astra High | Astra Medium | Sol Extra-high |
| --- | --- | :-: | :-: | :-: | :-: | :-: |
| K01 | documents | B | B | B | - | B |
| K02 | documents | - | - | B | B | B |
| K03 | documents | - | - | B | - | B |
| K04 | documents | B | - | B | B | B |
| K05 | documents | - | - | B | B | B |
| K06 | documents | 1 | 1 | - | - | - |
| K07 | documents | B | - | - | - | B |
| K08 | documents | - | - | - | - | - |
| K09 | documents | 1 | - | 1 | B | B |
| K10 | documents | - | - | - | - | - |
| K11 | code | 1 | - | B | B | B |
| K12 | code | - | - | - | - | - |
| K13 | code | - | - | B | B | B |
| K14 | code | - | - | - | - | - |
| K15 | code | B | B | B | B | B |
| K16 | code | - | - | - | - | - |

`results/set.json` gives each defect's statement and place.

## Pairs and families

Counting found by both judges: ten of the sixteen defects were found by at least one
configuration, four by both families, six by GPT-6.2 configurations only and none by
Opus configurations only.

| Pair | Found by either | First alone | Second alone |
| --- | ---: | ---: | ---: |
| Opus High and Astra High | 9 | 4 | 8 |
| Opus High and Astra Medium | 9 | 4 | 7 |
| Opus High and Sol Extra-high | 10 | 4 | 10 |
| Opus High and Opus Medium | 4 | 4 | 2 |
| Astra High and Astra Medium | 9 | 8 | 7 |
| Astra High and Sol Extra-high | 10 | 8 | 10 |
| Astra Medium and Sol Extra-high | 10 | 7 | 10 |

## The judges

The two judges gave the same verdict on 73 of 80 cells: 31 found by both, 39 not found
by both, 3 partial by both. In the other seven the Opus judge was the more generous in
six and the Sol judge in one. The judges disagreed about quotations: the Sol judge
counted 65 of 74 quotations by Claude Opus 5.5 at High as present in the tree and the
Opus judge 72 of 72, so the quotation counts are not used here.

## The Gemini starts

Gemini 4 Neon at High was started on all nine commits: six were refused on quota and
three returned an empty reply after 35 to 62 seconds. Gemini 4 Carbon at High, added
when Neon was refused, was refused on all nine. The
[probe record](2026-11-25-delegate-start-probes.md#the-quota-refusal) describes the
refusal.

## What this supports

- On these nine commits a reviewer from the GPT-6.2 family found defects that a
  reviewer on Claude Opus 5.5 did not, and not the reverse. Most of the commits were
  written under a Claude lead, so this is evidence about reviewing another family's
  work as much as about the reviewers.
- Adding Claude Opus 5.5 at Medium to Claude Opus 5.5 at High added no known defect.
- Within each model the higher effort found more known defects and took longer: Astra
  8 against 7 in 2,021 against 1,105 seconds, Opus 4 against 2 in 3,979 against 2,478.
- Six of sixteen defects were found by no configuration.
