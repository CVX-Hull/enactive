---
owner: lead
status: historical
kind: measurement
date: '2026-11-26'
scope: 'Start check of two changed delegate starts for issue #986: the Claude Code reviewer, explorer and locator start without plan mode, and the Antigravity read-only starts with a note that says to run no shell command; three review commits of the reviewer recall replay and a permission probe; subscription quota only, no game launch, no game input'
---

# Reviewer start check

## At a glance

Two delegate starts worked against the briefs they were given. The Claude Code
reviewer ran in plan mode, whose planning procedure a review brief contradicts, and
carried the session owner's output style. The Antigravity reviewer ended with no reply
when the model asked to run a command. Both starts are changed, and this record checks
the changed starts on three commits of the
[reviewer recall replay](2026-11-25-reviewer-recall-replay.md).

| Start, on the same three commits | Before | After the change |
| --- | --- | --- |
| Claude Code, Claude Opus 5.5 at High: reviews handed back | 3 of 3 | 3 of 3 |
| The same: replies that mention plan mode or a plan file as their own instruction | 14 of 18 across the replay | 0 of 3 |
| The same: replies carrying the owner's explanatory note blocks | 18 of 18 across the replay | 0 of 3 |
| Antigravity, Gemini 4 Neon at High: reviews handed back | 0 of 6 starts, all empty | 3 of 3 |
| Antigravity, Gemini 4 Carbon at High: reviews handed back | 3 of 3, in 1,125 to 1,471 seconds | 2 of 3; one stopped at the 1,500-second limit |

- **Claude Code.** The start uses the `dontAsk` permission mode and the default output
  style in place of plan mode. In a permission probe it refuses a file write, a shell
  write and a script, and runs `git log`.
- **Antigravity.** The delegate call adds a note to every reviewer, explorer and
  locator brief: run no shell command. No start in this check records a denied command.
- **Cost of the Claude Code change.** The new mode also refuses compound commands and
  scripts that plan mode let a reviewer run. Each of the three reviews had one to three
  commands refused and still handed back.
- **Not shown.** Whether either change raises the number of defects a reviewer finds.
  Three commits, each configuration once, do not measure that.
  [The review leaf](https://github.com/CVX-Hull/enactive/issues/991) can.

No owner decision is requested: the changed Claude Code start still enforces that the
reviewer cannot edit.

The scripts, briefs, replies and results are retained as
[`reviewer-start-check`](../../data/evidence/reviewer-start-check.sha256).

## The two changes

- **Claude Code reviewer, explorer and locator.** `--permission-mode plan` becomes
  `--permission-mode dontAsk`, with `--settings '{"outputStyle": "default"}'` added. The
  file-editing tools stay disabled. `dontAsk` denies any tool call that is not already
  allowed, without the instructions plan mode gives the model to explore with
  sub-agents, write a plan file and leave plan mode.
- **Antigravity reviewer, explorer and locator.** Each role in
  `.agents/delegates.json` carries a `note`, which `tools/delegate.py` puts after the
  role's instruction in the brief as sent: "Run no shell command and no terminal tool:
  this start cannot approve one, and asking for one ends the run with no reply. Use
  only your file reading and file search tools." The note is data in the definitions
  file; the call still names no coding agent.

## Method

- **Reviews.** `scripts/start_check.py` starts three configurations on three of the
  replay's prepared commit trees (`305cecc5`, `3942ae55`, `40960889`) with the replay's
  own review brief, through the changed `tools/delegate.py` and
  `.agents/delegates.json`, each with a 1,500-second limit. Up to five starts ran at
  once. The "before" column is the replay's result for the same commits.
- **Permission probe.** One brief asks the reviewer to run `git log`, create a file with
  its file-writing tool, run `echo x > probe-b.txt`, run a one-line Python script, and
  say whether its instructions mention plan mode or an explanatory output style
  (`probe/`). It ran on Claude Haiku 5.5 at High under the changed start and under the
  tracked plan-mode start, and on Claude Opus 5.5 at High under the changed start. The
  fixture directory was checked for new files after each run.
- **Reading the replies.** The lead searched the nine review replies for plan mode, a
  plan file, leaving plan mode and the note-block marker, and read each match.

## Results

| Commit | Opus High | Neon High | Carbon High |
| --- | --- | --- | --- |
| `305cecc5` | handed back, 847 s, 1 command refused | handed back, 1,010 s | no hand-back at 1,500 s |
| `3942ae55` | handed back, 395 s, 2 refused | handed back, 609 s | handed back, 1,485 s |
| `40960889` | handed back, 608 s, 3 refused | handed back, 613 s | handed back, 1,124 s |

- **Plan mode in the replies.** One Claude Opus 5.5 reply mentions plan mode twice, as
  the subject of the commit it reviews, which changes the delegate starts. None
  describes a plan file or plan mode as its own instruction, and none carries a note
  block.
- **Refused commands.** The six commands refused across the three Claude Opus 5.5
  reviews are searches joined with pipes or command substitution, and one Python
  one-liner over a data file. Each reply says what it could not run.
- **The probe.**

| Step | Changed start, Haiku | Changed start, Opus | Plan-mode start, Haiku |
| --- | --- | --- | --- |
| `git log` | runs | runs | runs |
| Create a file with the file-writing tool | refused: the tool is disabled | not attempted, citing the role file | not attempted, citing plan mode |
| `echo x > probe-b.txt` | refused by the permission mode | not attempted, citing the role file | not attempted, citing plan mode |
| A Python one-liner | refused by the permission mode | refused by the permission mode | runs, prints 42 |
| Instructions mention plan mode | no | no | yes |
| Instructions mention an explanatory output style | no | no | yes |

  No probe run left a new file in the fixture.

- **Antigravity.** None of the six starts that handed back, nor the one that timed out,
  records a denied command. The same Gemini 4 Neon configuration returned an empty
  reply on all six of its earlier starts on these three commits.

## Limits

- Three commits and one start of each configuration. The hand-back counts show the
  starts work; they are not rates.
- Gemini 4 Carbon needs 1,124 to 1,485 seconds for a review here and 1,125 to 1,471 in
  the replay, so a 1,500-second limit is not enough margin for it.
- Under plan mode the model declined to write; under the changed start the write is
  refused when attempted. Neither makes the filesystem read-only: a command the user's
  or the project's settings already allow still runs.
- The reviews ran while other delegates were running on the same subscriptions.
