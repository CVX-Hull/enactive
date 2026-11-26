---
owner: lead
status: historical
kind: study
date: '2026-11-25'
scope: 'Replay of clean-context review on nine past commits of this repository that hold sixteen defects later fixed, for issue #973: eight reviewer configurations from three model families, each as tools/delegate.py starts it, given the same commit and brief, and two judges; subscription quota only, no game launch, no game input'
---

# Reviewer recall replay

## At a glance

Eight reviewer configurations were each started on nine past commits that hold sixteen
defects fixed later. Counting a defect as found only when both judges said so:

| Configuration, as started | Reviews handed back | Known defects found |
| --- | ---: | ---: |
| GPT-6.2 Sol at Extra-high | 9 of 9 | 10 of 16 |
| GPT-6.2 Astra at High | 9 of 9 | 8 of 16 |
| GPT-6.2 Astra at Medium | 9 of 9 | 7 of 16 |
| Claude Opus 5.5 at High, started without plan mode | 9 of 9 | 6 of 16 |
| Claude Opus 5.5 at High | 9 of 9 | 4 of 16 |
| Claude Opus 5.5 at Medium | 9 of 9 | 2 of 16 |
| Gemini 4 Carbon at High | 7 of 9 | 3 of the 14 it had a review for |
| Gemini 4 Neon at High | 1 of 9 | 2 of the 4 it had a review for |

Five defects were found by GPT-6.2 configurations only and five by no configuration.
Counting a defect found by either judge, one defect was found by Claude Opus 5.5
configurations only. The two judges gave the same verdict on 106 of 114 cells.

The counts do not rank the models as reviewers, for these reasons.

- The configurations were not started alike. The tracked Claude Code reviewer start
  uses plan mode, which gives the model a planning procedure that contradicts the
  brief, and loads the owner's output style. One added arm removed both and found 6
  where the tracked start found 4; each arm ran once, so the difference may be chance.
- Seven of the nine commits carry a Claude co-author trailer and none a GPT or Gemini
  trailer, so the design cannot separate the reviewer's family from the author's.
- Every defect in the set had already passed this repository's review once, and the
  defect statements were written by GPT-6.2 Sol explorers.
- The lead chose the nine commits by hand, and sixteen defects are a small sample.
- The judges could tell which reviews came from Claude Opus 5.5 under the tracked start.

Not known: whether a second run of any configuration finds the same defects; whether
each review's other findings are correct, since only the known defects were judged; who
reviewed seven of the nine commits originally; and how a Gemini reviewer does on the
commits where its start returned nothing. No owner decision is requested.

The first five configurations' scripts, reviews, judging and scores are retained as
[`reviewer-recall-replay`](../../data/evidence/reviewer-recall-replay.sha256). The three
added configurations, their judging, the combined scoring and two reviews of this study
are retained as
[`reviewer-recall-replay-added-arms`](../../data/evidence/reviewer-recall-replay-added-arms.sha256).
Every count below is printed by `scripts/combine.py` into `results/combined.txt` in the
second study, except where another source is named.

## Method

- **Tracing.** Three explorers on Codex GPT-6.2 Sol at Extra-high traced the defects
  repaired by `ea2dfbcb` (#946), `b8c41ec9` (#923), `30332789` (#918), `dff250b9`
  (#844), `fdbf3f12` (#867) and `b1c2a926` (#820) to the single commit that introduced
  each, and wrote each defect down without reference to its fix (`defect-tracing/` in
  the first study). They traced defects to nineteen commits.
- **The set.** The lead chose nine of the nineteen by hand; `scripts/build_set.py`
  names them. Four of the ten left out add between 2,564 and 34,206 lines
  (`git show --shortstat`), more than any commit kept. The other six add 62 to 2,035
  lines (`b9f2c38c`, `637e8ba9`, `c4866275`, `b88d1aa3`, `faa5256f`, `64abd314`), and
  the reason each was left out was not written down. The lead checked every quoted defective line against the
  introducing commit with the same script and six multi-line quotations by hand.
  `results/set.json` in the first study is the set.
- **Isolation.** Each commit was reviewed in a standalone shallow clone holding that
  commit and its parent only, so its fix is not in the history. The clone also held the
  current reviewer role file and glossary where the old tree lacked them, and the
  commit's diff as a file.
- **The reviews.** Every configuration got the same brief (`scripts/replay.py`): review
  the commit as before a merge, quote each finding's passage, mark it confirmed or
  suspicion. Each start ran once through `tools/delegate.py` with a 1,500-second limit.
  Within a commit the first five configurations ran at the same time, as did the two
  Gemini configurations, so wall times include whatever the shared subscriptions and
  machine cost each other.
- **How each was started.** The brief was the same and the start was not.
  `.agents/delegates.json` starts a Codex reviewer with `-s read-only`, an Antigravity
  reviewer in its read-only print mode, and a Claude Code reviewer with
  `--permission-mode plan` and the editing tools disallowed. Plan mode adds
  instructions to explore with sub-agents, write a plan file and finish by leaving plan
  mode; the Claude Code start also loaded the owner's output style, which asks for
  boxed explanatory notes. Fourteen of the eighteen reviews by Claude Opus 5.5 under
  this start mention the plan file or plan mode, and all eighteen carry the notes
  (`grep -l` over the replies).
- **The arm without plan mode.** `scripts/delegates-no-plan-mode.json` differs from the
  tracked file in the Claude Code reviewer's arguments only: `--permission-mode auto`
  in place of `plan`, and `--settings '{"outputStyle":"default"}'`. The editing tools
  stay disallowed. None of its nine reviews mentions a plan file or carries the notes.
  This start is not read-only by enforcement and is not the tracked start.
- **Judging.** For each commit a judge read the known defects and the reviews under
  shuffled neutral labels and gave each cell `found`, `partial` or `not_found`
  (`scripts/judge.py`). A review found a defect when a finding was about the same
  passage or behaviour and said what was wrong in a way that matched. The first judge
  was Codex GPT-6.2 Sol at Extra-high and the second Claude Code Claude Opus 5.5 at
  High. The first five configurations were judged in one packet for each commit and
  the three added ones in a second packet, by the same judges under the same rule.
  The labels hid the configuration's name only: in the first packets the explanatory
  notes mark the two Claude Opus 5.5 reviews. The lead read three verdicts against the
  review texts and agreed with each, and the design reviewer below agreed with every
  verdict it read.
- **One lead error.** Three older clones lacked the explorer role file the judges are
  told to read, and six judge starts of the first judging stopped there; the lead added
  the file and started them again. Their results were not kept, so their time and
  tokens are in no figure here and in no ledger row. No review was affected.

## The set

| Commit | Kind | Added lines | Known defects | Co-author trailer | Reviewers recorded for its issues |
| --- | --- | ---: | ---: | --- | --- |
| `40960889` (#842) | documents | 311 | 3 | Claude Fable 5.2 | none |
| `4dde98e0` (#843) | documents | 504 | 4 | Claude Fable 5.2 | none |
| `db98f7cf` (#827) | documents | 190 | 1 | Claude Fable 5.2 | none |
| `3942ae55` (#865) | documents | 917 | 2 | Claude Fable 5.2, Claude Opus 5.5 | GPT-6.2 Sol at Extra-high, once |
| `c3133466` (#380) | code | 122 | 1 | Claude Opus 5.5 | none |
| `89951f37` (#856) | code | 2,231 | 2 | Claude Fable 5.2, Claude Opus 5.5 | none |
| `749e7cc6` (#542) | code | 298 | 1 | none | none |
| `909ca9dd` (#416) | code | 893 | 1 | Claude Opus 5.5 | none |
| `305cecc5` (#902) | code | 1,446 | 1 | none | GPT-6.2 Sol at Extra-high once, Claude Opus 5.5 at High twice |

The trailers are read with `git log -1 --format=%b COMMIT`. A trailer shows that a
Claude model co-wrote the commit; it does not show which model led the work or which
delegates wrote parts of it. The last column lists reviewer rows in the
[attempts ledger](../../data/evaluation/coding-agent-attempts.jsonl) whose issue the
commit message references. A ledger row names an issue and not the commit reviewed, and "none"
means none recorded there.

## Known defects found

Found by both judges, with found by at least one judge in brackets.

| Configuration | Reviews handed back | Defects it had a review for | Found | Documents | Code | Findings in all | Wall time of the reviews handed back |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GPT-6.2 Sol at Extra-high | 9 | 16 | 10 (10) | 7 (7) of 10 | 3 (3) of 6 | 80 | 2,758 s |
| GPT-6.2 Astra at High | 9 | 16 | 8 (9) | 5 (6) of 10 | 3 (3) of 6 | 98 | 2,021 s |
| GPT-6.2 Astra at Medium | 9 | 16 | 7 (7) | 4 (4) of 10 | 3 (3) of 6 | 79 | 1,105 s |
| Claude Opus 5.5 at High, without plan mode | 9 | 16 | 6 (6) | 3 (3) of 10 | 3 (3) of 6 | 70 | 3,753 s |
| Claude Opus 5.5 at High | 9 | 16 | 4 (7) | 3 (5) of 10 | 1 (2) of 6 | 76 | 3,979 s |
| Claude Opus 5.5 at Medium | 9 | 16 | 2 (3) | 1 (2) of 10 | 1 (1) of 6 | 58 | 2,478 s |
| Gemini 4 Carbon at High | 7 | 14 | 3 (3) | 1 (1) of 10 | 2 (2) of 4 | 73 | 8,114 s |
| Gemini 4 Neon at High | 1 | 4 | 2 (2) | 2 (2) of 4 | none reviewed | 8 | 713 s |

"Findings in all" is the first judge's count of each review's numbered findings.

Token counts as each coding agent reported them compare within a coding agent only.
For nine reviews: Claude Opus 5.5 at High 35.9 million cached input, 1.17 million cache
write and 331,000 output; without plan mode 37.1 million, 1.13 million and 315,000; at
Medium 18.0 million, 0.85 million and 199,000. GPT-6.2 Astra at High 19.1 million input
and 63,000 output, and at Medium 9.2 million and 34,000; GPT-6.2 Sol at Extra-high 17.0
million and 123,000. For the nine final starts of each Gemini configuration: Carbon 4.5
million input, 25.7 million cached and 716,000 output; Neon 1.4 million, 6.1 million
and 110,000.

## By defect

B is found by both judges, 1 by one judge only, a dash by neither, and n means the
configuration handed back no review of that commit.

| Defect | Kind | Sol Extra-high | Astra High | Astra Medium | Opus High, no plan mode | Opus High | Opus Medium | Carbon High | Neon High |
| --- | --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| K01 | documents | B | B | - | B | B | B | - | n |
| K02 | documents | B | B | B | - | - | - | - | n |
| K03 | documents | B | B | - | - | - | - | - | n |
| K04 | documents | B | B | B | B | B | - | - | B |
| K05 | documents | B | B | B | - | - | - | - | - |
| K06 | documents | - | - | - | - | 1 | 1 | - | - |
| K07 | documents | B | - | - | B | B | - | B | B |
| K08 | documents | - | - | - | - | - | - | - | n |
| K09 | documents | B | 1 | B | - | 1 | - | - | n |
| K10 | documents | - | - | - | - | - | - | - | n |
| K11 | code | B | B | B | B | 1 | - | n | n |
| K12 | code | - | - | - | - | - | - | - | n |
| K13 | code | B | B | B | - | - | - | - | n |
| K14 | code | - | - | - | - | - | - | n | n |
| K15 | code | B | B | B | B | B | B | B | n |
| K16 | code | - | - | - | B | - | - | B | n |

`results/set.json` in the first study gives each defect's statement and place.

## Families and pairs

Counting found by both judges, eleven of the sixteen defects were found by at least one
configuration. Five were found by GPT-6.2 configurations only (K02, K03, K05, K09,
K13), none by Claude Opus 5.5 configurations only and none by Gemini configurations
only. K16 was found by Claude Opus 5.5 without plan mode and by Gemini 4 Carbon, and by
no GPT-6.2 configuration. Five were found by none (K06, K08, K10, K12, K14).

Counting found by either judge, twelve were found by at least one configuration: K06
was found by the two plan-mode Claude Opus 5.5 configurations only, and four by GPT-6.2
configurations only (K02, K03, K05, K13).

The table counts found by both judges. Each row is a first reviewer and a second, with
what each found alone, what the two found together and what the second added.

| First and second reviewer | First found | Second found | Together | Second adds |
| --- | ---: | ---: | ---: | ---: |
| Opus High and Opus Medium | 4 | 2 | 4 | 0 |
| Opus High and Opus High without plan mode | 4 | 6 | 6 | 2 |
| Opus High and Astra Medium | 4 | 7 | 9 | 5 |
| Opus High and Astra High | 4 | 8 | 9 | 5 |
| Opus High and Sol Extra-high | 4 | 10 | 10 | 6 |
| Opus High without plan mode and Astra Medium | 6 | 7 | 10 | 4 |
| Opus High without plan mode and Sol Extra-high | 6 | 10 | 11 | 5 |
| Astra Medium and Astra High | 7 | 8 | 9 | 2 |
| Astra Medium and Sol Extra-high | 7 | 10 | 10 | 3 |
| Astra High and Sol Extra-high | 8 | 10 | 10 | 2 |
| Sol Extra-high and Opus High without plan mode | 10 | 6 | 11 | 1 |
| Sol Extra-high and Opus High | 10 | 4 | 10 | 0 |
| Sol Extra-high and Carbon High | 10 | 3 | 11 | 1 |

## The judges

The two judges gave the same verdict on 106 of 114 cells: 42 found by both, 57 not
found by both and 7 partial by both. On the first five configurations they agreed on
73 of 80 cells. In the other seven the Opus judge was the more generous in six, four of
them cells of a Claude Opus 5.5 review (K03, K06 twice, K09) and two of GPT-6.2 Astra
at High (K06, K09), and the Sol judge was the more generous in one (Claude Opus 5.5 at
High, K11). On the three added configurations they agreed on 33 of 34 cells; the Opus
judge gave Gemini 4 Carbon a partial on K12 where the Sol judge gave not found.

The judges disagreed about quotations: the Sol judge counted 65 of 74 quotations by
Claude Opus 5.5 at High as present in the tree and the Opus judge 72 of 72
(`results/score-sol-judge.txt` and `results/score-opus-judge.txt` in the first study),
so the quotation counts are not used here.

## The Gemini starts

| Configuration | Starts | Refused on quota | Empty reply | Handed back |
| --- | ---: | ---: | ---: | ---: |
| Gemini 4 Neon at High, first day | 9 | 6 | 3 | 0 |
| Gemini 4 Carbon at High, first day | 9 | 9 | 0 | 0 |
| Gemini 4 Neon at High, after the quota returned | 17 | 0 | 16 | 1 |
| Gemini 4 Carbon at High, after the quota returned | 12 | 0 | 5 | 7 |

After the quota returned each configuration was started once on every commit, and each
empty reply was started once more with the same brief. Every one of the 24 empty
replies has the same detail in its result file: the model asked to run a command, the
read-only print mode cannot ask for that permission and denied it, and the run ended
with exit code 0 and no reply, after 19 to 164 seconds. Neon returned an empty reply on
eight of nine commits twice over. Carbon returned one on three commits, all of them
code, and on the second start reviewed one of the three. The reviews Carbon handed back
took 636 to 1,471 seconds each. The
[host page](../operations/coding-agents.md#starting-a-delegate-on-any-coding-agent)
advises telling an Antigravity delegate to run no command and putting the diff in the
brief; this study's brief gave every configuration the diff as a file and did not say
to run no command, so these figures are for a brief written without that advice. The
[probe record](2026-11-25-delegate-start-probes.md#the-quota-refusal) describes the
quota refusal.

## Reviews of this study

Two clean-context reviewers read the first version of this record, which covered the
first five configurations, and its evidence. Codex GPT-6.2 Astra at Medium reported six
defects of fact and wording, and Claude Code Claude Opus 5.5 at High reported six
defects of design; the lead confirmed all twelve against the files. They are corrected
in this text: the selection of the set, what a co-author trailer shows, the recorded
original reviewers, the judges' sight of the output style, the restarted judge starts,
the pair table, the unequal starts, the both-judges qualifier, the effort and
wall-time wording, and the claim about the author's family. The arm without plan mode
and its judging were added in answer to the design review. `study-reviews/` in the
second study holds both briefs and replies.

## What this supports

Every statement is about these nine commits, each configuration as started here and
run once.

- GPT-6.2 reviewers found known defects that no Claude Opus 5.5 reviewer found: five of
  sixteen by both judges, four by either judge. In the other direction there is one
  defect by either judge (K06) and, with Gemini 4 Carbon, one by both judges (K16).
- The Claude Code reviewer start matters to the count. Under the tracked plan-mode
  start Claude Opus 5.5 at High found 4 (7 by either judge), and without plan mode and
  the output style it found 6 (6), including three of six code defects against one
  (two). One run of each does not show how much of the difference is the start.
- A second Claude Opus 5.5 reviewer at Medium added no known defect to the first at
  High. A GPT-6.2 reviewer added four to eight to a Claude Opus 5.5 reviewer, and Claude
  Opus 5.5 without plan mode added one to GPT-6.2 Sol at Extra-high.
- For the two models run at two efforts, the higher effort found more and took longer
  on this set: GPT-6.2 Astra 8 against 7 in 1.8 times the wall time, and Claude Opus
  5.5 4 against 2 in 1.6 times.
- Through the tracked Antigravity reviewer start, Gemini 4 Neon at High handed back
  one review in seventeen starts once quota was available and Gemini 4 Carbon at High
  seven in twelve, and Carbon's reviews took the longest of any configuration.
- Five of sixteen defects were found by no configuration.

It does not support a statement about which family reviews another family's work
better, because the set holds no commit written by a GPT-6.2 or Gemini model.
