---
owner: lead
status: historical
kind: measurement
date: '2026-11-19'
scope: 'One Antigravity session leading one small documentation leaf from brief to a reviewed pull request with auto-merge queued, watched read-only, and the merge completed by the watcher; no gameplay and no paid model call'
---

# Antigravity as lead on one watched leaf (#810)

## At a glance

An Antigravity session on Gemini 4 Neon at High led the pull-request record leaf
([#809](https://github.com/CVX-Hull/enactive/issues/809)) from its brief to an open,
reviewed pull request with a green check and auto-merge queued. Five of the seven duties
it was asked to show were observed. Two were observed in part: it checked the reviewer's
quoted passages in two of the files the reviewer quoted, and it queued the merge against
a commit its reviewer had not named. Its source edits stayed inside
its two owned files and its worktree; it wrote working files only in its own scratch
folder and the reviewer's output in `/tmp`. It launched no game and used no provider
key.

It did not run unattended. The app's terminal sandbox blocked every git write, every
network call and one read outside the project, and each was retried outside the
sandbox: eleven retries in 47 minutes. The owner reports approving several by hand, and
creating the pull request took 26 minutes. The session queued the merge and ended; the
branch was behind `main`, so the watching lead merged `main` into it and completed the
merge. The result shows one Antigravity session leading one small documentation leaf
with the owner present, as far as a green pull request with the merge queued. It does
not show unattended leading, and it is one leaf.

## What ran

| Item | Value |
| --- | --- |
| Started and ended | 04:07:55Z to 04:54:43Z on 20 November 2026 (the evening of 19 November local time); 100 transcript steps, 50 tool calls |
| Coding agent | The Antigravity app, opened on the main checkout by the owner. Its version is not in the transcript |
| Model and effort | `gemini-4-neon-high` on every response. Effort is read from that selector; the transcript has no separate effort field |
| Mode | Not recorded. Read from behaviour: commands ran in a terminal sandbox, and a blocked command was retried with a request for the owner's explicit approval |
| Brief | One pasted message: the leaf's brief in the [brief template](../standards/agents.md#brief-template) shape and seven numbered steps |
| Leaf | #809. Two files changed; the brief also allowed the controls page, only if a control row had to change, and it was not touched |
| Watcher | A second session on another coding agent, read-only until the trial session ended |

The evidence is the session's own local transcript, read by a read-only explorer after
the session ended, together with the watcher's observations of the worktree, the
branch, the pull request and its check runs. "Step" below is the transcript's step
index for the lead session.

## The seven duties

| Duty | Result | Evidence |
| --- | --- | --- |
| Delegate to an explorer and a worker with clean context | Observed | Step 17: a read-only explorer sub-agent started with a brief in the template's shape; it returned its findings at 04:10:59Z. Step 23: a worker sub-agent defined with write tools and no sub-agent tools, started with its own brief; it handed back at 04:14:04Z and again after one repair at 04:19:13Z. Each ran as its own conversation whose first message was the brief. Both inherited the lead's model |
| Worker in its own worktree | Observed | The worker edited only `.github/pull_request_template.md` and `docs/workflows/review.md` under `.runtime/worktrees/pull-request-model-record`. The main checkout's working tree was not edited |
| Verify the worker's result itself | Observed | Step 28 to 31: the lead read the diff and ran `tools/check.py --fast` ("Fast checkpoint checks passed") and the document tests ("17 passed, 16 subtests passed"). It repeated both after the repair, at steps 49 to 53 |
| One reviewer from a second model family, each quoted passage checked | Observed in part | Step 37: `codex exec --ignore-rules --ephemeral -s read-only`, on GPT-6.2 Astra at High by the command's own header. The reviewer raised one finding. The lead read the template and the review page before marking it confirmed and sending the worker a repair. After the review it reopened those two files only; it did not reopen the controls page or the host-neutrality test, which the reviewer also quoted. Its brief to the reviewer listed claims to test, and one of them asserted that the diff satisfied the issue |
| Commit through the hook and open a pull request on the template | Observed | Commit `21677a5d`, recorded by git at 04:21:22Z, with the hook's fast check passing, under the repository's configured identity. The push completed by 04:22:48Z. The request to create pull request [#818](https://github.com/CVX-Hull/enactive/pull/818) returned at 04:49:01Z on the new template, with its own `Models:` line, `Refs #809` and a statement that agent review is not human approval |
| Wait on CI with one watch command | Observed | Step 85: the run found by commit. Step 89: `gh run watch 44676906546 --exit-status`; it ended with `controller` green after about two minutes |
| Ask the owner one structured question | Observed | Step 93: one question with three options and a recommendation. The owner chose the recommended one: the `Models:` line names only the author, noting a sub-agent only when a worker used a different model or effort |
| Merge, or stop before it | Observed in part, then completed by the watcher | Step 97: `gh pr merge 818 --auto --squash --match-head-commit 21677a5d…` was allowed and queued the merge. The brief asked for the commit the review named; the reviewer had examined an uncommitted diff over `44a5ef14` and never named `21677a5d`, which adds the repair and was checked by the lead only. It did not merge: three other pull requests had merged since the branch was cut, and main's ruleset requires a head that contains main's tip. The session ended there |

## What needed the owner

The transcript records no approval decision, only a blocked operation followed by that
operation retried outside the sandbox and succeeding; one retry split a chained command
in two. Separately, the owner reports
approving several `gh` commands and a write to `/tmp` by hand. Which retries were
approved by hand and which the app allowed by itself is not recorded.

| Blocked in the sandbox | Times | What the block said |
| --- | --- | --- |
| `gh` calls to GitHub | 6 | No connection to `api.github.com` |
| git writes: `worktree add`, `add`, `commit`, `push` | 4 | "Operation not permitted" on the repository's `.git`, or no route to `github.com` |
| The second-family reviewer | 1 | Its own configuration file outside the project could not be read; its output went to `/tmp` |

No refusal is recorded. Creating the pull request took 26 minutes between the retried
command and its result. The transcript does not say why; the watcher saw the branch
pushed and nothing further in that time. Wall time was 47 minutes, of which that step
was 26.

## What the session's own report claimed

The session's final message matches the evidence on the branch, commit, pull request,
check result, the owner's answer and "refused or denied: none". Two of its claims go
beyond its transcript:

- **"Completed all seven steps for issue #809 (trial #810)."** The review step was
  complete only in part. In the
  session, at step 45, the lead wrote that it had checked every quoted passage; it had
  reopened two of the quoted files, the pull-request template and the review page.
- **"Every unsandboxed command elevation was approved."** The transcript shows the
  retries succeeding and logs no approval.

Its "main checkout untouched" is fair for the working tree; creating the worktree and
committing wrote to the main repository's `.git`, as any worktree does. It gave its
sub-agents' effort as "Inherited (High)" and marked that as an assumption; both
sub-agents' transcripts show the same High selector, and how it was inherited is not
recorded.

## After the session

The watching lead took the leaf back for the last step. It merged `main` into the
branch at `bca211ac` without a force-push. The diff against `main` was identical to
the one committed at `21677a5d`, which is the diff the second family reviewed plus the
one repair that review asked for. The fast check and the document, link, index and
host-neutrality tests passed (22 passed), the protected check passed on the new head
and #818 merged as `9ac200c3`.

## Other measurements the same evening

- **Role files.** Once the tracked role files were on `main`, `agy agents` run from the
  main checkout listed all four: `explorer`, `locator`, `reviewer` and `worker`. Earlier
  the same command listed none from a worktree, from a scratch copy, or from that copy
  after `git init`. Only those four places were tried, and why they differ was not
  established. The trial session did not use these files, which were not yet merged: it
  started its explorer as the host's `research` type and defined a `worker` type itself.
- **Second coding agent's version.** The Codex CLI updated itself from 0.167.1 to
  0.171.0 during the evening; the 0.171.0 install is dated 22:16 local. The trial's
  reviewer ran on 0.171.0. On 0.171.0 the selectors `gpt-6-luna`, `gpt-6.1-terra`,
  `gpt-6.2-sol` and `gpt-6.2-astra` each answered a one-word prompt, at 23:09 and again
  after midnight. No selector check ran on 0.167.1. The reviewer's own text gave its model only as "GPT-6",
  while the command header gave `gpt-6.2-astra` at High; the header is the record.

## What this supports

- On one watched documentation leaf, an Antigravity session delegated with written
  briefs, kept the worker in a worktree, verified from files and tests, obtained and
  acted on a second family's review, opened a pull request on the template, waited on
  the required check and asked the owner a structured question. It checked the
  reviewer's passages in part, and the watcher completed the merge.
- It was not shown to do that unattended. Git writes, GitHub calls and a tool outside
  the project were each blocked by the app's sandbox and retried outside it, and the
  owner reports approving several by hand.
- A lead's report is still checked against files: two of this one's claims went
  beyond its transcript.
- A branch that sits open while other work merges falls behind `main` and cannot merge
  by itself. The lead that queued the merge had ended; someone has to bring the branch
  up to date.

## Limits

One session, one small documentation leaf, one model at one effort. No source code, no
native lane, no game. The explorer read the transcript and tails of the task logs, not
every log in full, and did not interpret two event files the app wrote for the
conversation. The app's version and approval mode are not recorded. Nothing here shows
how the same session behaves headless from the CLI, with allow rules that cover git and
GitHub, or on a larger leaf.
