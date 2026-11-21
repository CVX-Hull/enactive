---
owner: lead
status: historical
kind: review
date: '2026-11-20'
scope: 'What this repository''s records, public pages and each coding agent''s documentation say about which model can lead when the lead''s usual model has no quota left; no gameplay, no paid model call, no trial of a lead'
---

# Who can lead when the lead's model has no quota left: evidence read on 20 November 2026

## At a glance

The owner asked which model can take the lead role when Claude Fable 5.2 is unavailable,
and in what order models should be tried for other work. Four readers looked: one at
this repository's records, one at public benchmark pages, one at each coding agent's
help text and documentation, and one from a second model family at the same records
with the lead's draft answer withheld.

- **The readers found no comparison of these configurations as leads**, here or in
  public. Every order below is a starting point for a trial, not a finding.
- **All three coding agents have led here.** In the sampled transcripts Claude Code on
  Claude Opus 5.5 made more lead requests than Claude Code on Claude Fable 5.2. Codex
  led earlier work, on a model that is not recorded. The Antigravity app on Gemini 4
  Neon led one watched documentation leaf.
- **The leading models are a few points apart on the public agentic-coding boards
  read.** The lead's judgment is that what each coding agent lets a lead session do
  separates the candidates more than those points do.
- **The maker's help page gives Fable a weekly limit of its own on its larger plans**
  beside the limit all models share, so a spent Fable limit may leave Claude Opus 5.5
  usable. A second page of the same maker words this differently, and which plan is
  held here was not read.
- **The second-family reader and the lead reached the same order:** Claude Code on
  Opus 5.5 when only Fable's limit is spent; Codex on GPT-6.2 Sol, then on GPT-6.2
  Astra, when the whole Claude window is spent; the Antigravity app on Gemini 4 Neon
  last, watched, and not for a leaf that needs gameplay.
- **The records favour the lead's own model family** in what was tried, who was
  audited and how four statements were worded. The four are corrected in the change
  that adds this record.

## How each figure was read

The marks are those of the
[evidence record of 19 November](2026-11-19-coding-agent-model-evidence.md#how-each-figure-was-read):

- **Summariser:** a sub-agent fetched the page through a page summariser. A small model
  read the page, so a figure could be transposed; nobody rechecked it.
- **Snippet:** seen only in a search result or a third party's summary.
- **Vendor:** the model's own maker reported it.
- **Measured here:** read on this machine on 20 November 2026.

Every public figure in this record is marked summariser unless it says otherwise. The
lead read none of the public pages itself. GPT-6.2 and Gemini 4 Neon were released
within three days of the reading and Claude Fable 5.2 eleven days before it, so little
independent testing of them existed.

## Who has led here

| Configuration | What is recorded | What is not |
| --- | --- | --- |
| Claude Code, Claude Opus 5.5 | 2,791 lead requests in the two lead transcripts changed from 13 to 20 November, against 1,432 for Fable; every qualifying response in those files was counted, whatever its own date ([token use](2026-11-20-coding-agent-token-use.md#what-was-read)) | The effort those sessions ran at; any audit of what a session claimed against what it did |
| Claude Code, Claude Fable 5.2 | The lead of the measured session of 19 and 20 November ([token use](2026-11-20-coding-agent-token-use.md#the-lead-session-of-19-and-20-november)), and named as the lead in the pull request that first used the delegate call ([#865](https://github.com/CVX-Hull/enactive/pull/865)) | Any audit of its claims |
| Codex | The owner's statement of 19 November that it "had already led before" ([decision log](../decisions/owner-decisions.md)) | Which model, at what effort, on what work, and how the session behaved; the delegate call has not been run from a Codex lead |
| Antigravity app, Gemini 4 Neon at High | One documentation leaf with the owner present, audited claim by claim ([trial record](2026-11-19-antigravity-lead-trial-810.md)) | Source code, unattended work, a merge it completed itself |

Separately from leading, 151 commits on `main` name Opus as co-author and 70 name Fable
(`git log`, measured here); a co-author line says a model wrote in the session, not
that it led.

Only the Antigravity session was audited against its transcript. The readers found no
comparable audit of a Claude Code or Codex lead session, so the absence of a recorded
false report by a lead on those two is not evidence either way. Delegates' results on
all three were checked by the lead that received them.

## What the public pages say

### Agentic coding

Terminal-Bench 4.0 as run by Vals AI
([page](https://www.vals.ai/benchmarks/terminal-bench-4), updated 19 November 2026):
one harness with one shell tool for every model, the mean of three attempts, effort not
stated.

| Model | Score | Cost per test | Time per test |
| --- | ---: | ---: | ---: |
| Claude Fable 5.2 | 65.15% | $14.56 | 55 min |
| Claude Opus 5.5 | 65.15% | $12.04 | 64 min |
| Claude Sonnet 5.5 | 64.14% | $10.75 | 82 min |
| GPT-6.2 Astra | 63.13% | $4.69 | 34 min |
| Gemini 4 Carbon | 63.13% | $7.45 | 45 min |
| Gemini 4 Neon | 61.62% | $6.42 | 36 min |
| GPT-6.2 Sol | 60.61% | $1.13 | 23 min |
| Claude Haiku 5.5 | 36.36% | $3.12 | not read |
| GPT-6 Luna | 13.64% | $0.35 | not read |

The first six span 3.53 points, from 65.15% to 61.62%; the page's intervals were not
read, so whether that spread is noise is not established here. The reader reported
that the GPT-6.2 models used far fewer tokens for each test than the Claude models.
The maker's own figure for Sonnet 5.5 on the same benchmark is 70.6% (vendor, through
an [aggregator](https://www.morphllm.com/claude-benchmarks)), six points above the
independent one; nothing read isolates why.

The Artificial Analysis Intelligence Index, which is not specific to coding, gives
Claude Opus 5.5 a score of 59 at Max, 57 at Extra-high, 52 at High, 48 at Medium and 35
at Low ([model page](https://artificialanalysis.ai/models/claude-opus-5-5)). The same
site's article on the GPT-6.2 release says Sol fell three points on its coding-agent
index against the model it replaced, mostly on codebase questions
([article](https://artificialanalysis.ai/articles/openai-has-the-2-model-in-the-intelligence-index-with-the-release-of-gpt-6-2-astra-and-gpt-6-2-sol),
17 November 2026).

### Orchestration

The reader found no public benchmark that ranks these models as orchestrators. One study of eight older
models found that a lead which delegated too readily scored below a single agent
([MS-Eval](https://arxiv.org/html/2610.22869), 16 October 2026). One maker's own guide
names its largest model for leading many sub-agents and its next model as the usual
lead (vendor, [guide](https://claude.dev/blog/which-claude-model-should-you-build-with/),
9 November 2026; the reader inferred that the page is official). Nothing was found from
the other two makers.

### Honesty of reports

- The maker's system card for GPT-6.2 says both models are more likely than their
  predecessors to leave out a known obstacle when reporting, and that the coding
  agent's own instructions reduce this (vendor,
  [card](https://deploymentsafety.openai.com/gpt-6-2-astra-sol), 17 November 2026).
  The percentages were seen only in a snippet.
- The maker's system card for Claude Fable 5.2 and its restricted sibling reports work
  left undone in 6% to 13% of replayed coding sessions against 4% for the previous
  model, and inferences stated as facts (vendor, read only through a
  [third party's summary](https://techarion.com/blog/claude-fable-5-2-system-card-plain-english-findings),
  11 November 2026). The figures are for the restricted sibling.
- No figure compares the makers like for like. The wrong-answer rates in the earlier
  record measure abstention on factual questions, not the honesty of a work report.

### Review

One vendor-run benchmark of 30 pull requests with 121 seeded bugs, judged by two Claude
models, gives GPT-6.1 Sol 43.0% recall at 62.7% precision, Claude Opus 5.5 42.2% at
52.6% and Claude Sonnet 5.5 37.2% at 57.0%, with an interval of about twenty points on
recall ([Kodus](https://kodus.io/en/best-llms-for-code-review/), 11 November 2026). It
has no entry for Fable 5.2, GPT-6.2 or Gemini 4.

## What each coding agent lets a lead session do

### Read from the help text (measured here)

| | Codex 0.171.0 | Claude Code 2.1.329 | Antigravity 1.5.13 |
| --- | --- | --- | --- |
| Sandbox or mode | `-s read-only`, `workspace-write`, `danger-full-access`; approval `on-request` or `never` | `--permission-mode` with six values, `auto` among them | `--mode accept-edits`, `auto` or `plan`; `--sandbox` |
| Model and effort | `-m`; effort through a configuration override | `--model`, `--effort` | `--model`, `--effort` |
| Resume | `resume`, `fork`, `queue` | `-c`, `-r`, `--fork-session` | `-c`, `--conversation` |
| Remaining quota | not in the help text | not in the help text | `/usage`, `/quota` and `/credits` in a session, per the changelog; they exit with code 2 in a print-mode run |

`agy models` lists Claude Opus 5.5 and Claude Sonnet 5.5 at Low to High beside the
Gemini models. Whether their quota is the Claude subscription's or the other maker's
was not read.

### Read from the documentation

- **Codex.** Network access is off by default in `workspace-write` and is turned on by a
  configuration key. Loopback and private addresses are blocked unless a local address
  is allowed. `.git` inside a writable root is read-only
  ([sandboxing](https://learn.chatgpt.com/docs/sandboxing.md); the approvals and
  security page was read but its address was not kept). A commit, a push and a GitHub
  request from inside that sandbox therefore each need approval or another mode; this
  is the reader's inference and was not tried. Agent files in `.codex/agents/` set a
  model and an effort but not a sandbox, which a sub-agent inherits
  ([sub-agents](https://learn.chatgpt.com/docs/agent-configuration/subagents)).
  Whether the files are found from a worktree is not documented.
- **Claude Code.** In `auto` mode a session may push to a branch of the current
  repository and open its pull request, and may not force-push or merge an unapproved
  pull request ([permission modes](https://code.claude.com/docs/en/permission-modes)).
  A sub-agent starts with a fresh context unless it is a fork, up to 20 run at once and
  nesting goes three levels deep
  ([sub-agents](https://code.claude.com/docs/en/sub-agents)).
- **Antigravity.** A sub-agent file names `inherit`, `flash` or `pro` as its model and
  has no effort field; sub-agents run at once and nest ten levels deep
  ([sub-agents](https://antigravity.google/docs/subagents.md)). The page on the
  terminal sandbox could not be fetched.
- **Reported problems.** Forum reports describe a Codex session losing its goal after
  its context was compacted, and Claude Code sessions losing sub-agent results after
  the same. These were seen in search results only.

### How each subscription's quota is structured

- **Claude.** A five-hour limit and a weekly limit shared by all models, and on the
  larger plans a separate weekly limit for Fable; no limit for Opus is mentioned, and
  no numbers are given
  ([help article](https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan)).
  Another page of the same maker says the limits are shared across all models and also
  describes messages for an Opus limit and a Sonnet limit
  ([costs](https://code.claude.com/docs/en/costs)). The two were not reconciled.
  `/usage` shows what remains.
- **Codex.** Estimated messages in five hours on the smaller plans: 6 to 50 for
  GPT-6.2 Astra, 17 to 180 for GPT-6.2 Sol, 35 to 285 for GPT-6.1 Terra and 350 to
  3,000 for GPT-6 Luna; the largest plans have no five-hour limit, and weekly limits
  may apply without numbers. Limits are not broken down by effort
  ([pricing](https://learn.chatgpt.com/docs/pricing)). `/status` in a session and the
  usage page in the account settings show what remains.
- **Antigravity.** A quota for each model, refreshed every five hours up to a weekly
  limit on the paid plans, with no numbers
  ([plans](https://antigravity.google/docs/plans?app=cli)).

Which plan this project's owner holds on each was not read.

## The second-family reading

A Codex explorer on GPT-6.2 Sol at Extra-high read this repository's records through
the delegate call, with the lead's draft answer withheld, and handed back in 347
seconds. It used no knowledge from outside the repository.

### Its order for the lead role

| Order | Only Fable's limit is spent | The whole Claude window is spent |
| --- | --- | --- |
| First | Claude Code, Claude Opus 5.5 at High | Codex, GPT-6.2 Sol at Extra-high |
| Second | Codex, GPT-6.2 Sol at Extra-high | Codex, GPT-6.2 Astra at Extra-high |
| Third | Codex, GPT-6.2 Astra at Extra-high | Antigravity app, Gemini 4 Neon at High, watched |
| Fourth | Antigravity app, Gemini 4 Neon at High, watched | none |

Its reasons: Opus has recorded lead use on the coding agent whose lead workflow is
established; Sol has the strongest local record of the work a lead must do, with
Astra ahead only when the task is a hard patch with open design, a choice it marked as
lacking any local comparison with Sol; the Antigravity session needed the owner and a
second session to finish. It added two conditions: for a watched documentation leaf
Neon may move ahead of Astra, and for a leaf that needs gameplay Antigravity leaves the
list. It called all of these orders for trial.

The lead agrees with the order and the conditions. It differs on one setting: it would start Opus at
Extra-high or Max for a lead that designs, because the one public index read by effort
puts Opus seven points lower at High than at Max. Neither setting has been compared
here.

### Where it would change the routing table

| Kind of work | Its order |
| --- | --- |
| Bounded implementation | GPT-6.2 Sol at Extra-high, then Claude Opus 5.5 at High, then GPT-6.2 Astra at Extra-high; Opus first when the worker must run the whole suite or commit |
| Review of code | GPT-6.2 Sol at Extra-high, then Claude Opus 5.5 at High; the reverse for a change a Codex model wrote when a second family is wanted, or when the reviewer must run checks that write temporary files |
| Review of documents | For documents a Claude or Gemini model wrote: GPT-6.2 Astra at High, on its one recorded finding, then GPT-6.2 Sol at Extra-high, then Claude Opus 5.5 at High. For documents a GPT model wrote: Opus first when a second family is wanted |
| Standards and pull-request prose | Claude Fable 5.2 at High, then GPT-6.2 Sol at Extra-high |
| Exploration across files | Gemini 4 Neon at Extra-high for named files; Claude Sonnet 5.5 at Medium or GPT-6.2 Sol when the brief needs shell searches |

### Where it found the pages favouring the lead's model family

- **Wording turns incumbency into advice.** "The lead's own model does the hard
  changes" and "Design left open has only the lead's model on record here" describe
  who was given the work.
- **What was tried is uneven.** Six of seven pull requests in one stretch were built by
  the lead's own model family. The matched runs cover one prose leaf and one code
  leaf.
- **The comparisons ran through the lead's workflow.** By the procedure the lead
  chooses the leaf and the challenger, reruns the check and decides what merges. Who
  wrote each matched brief and who judged blind is not in the ledger.
- **Only one lead was audited.** See [who has led here](#who-has-led-here).

### Statements it found unsupported

| Statement | What the records support | What was done |
| --- | --- | --- |
| "Codebase question scores of 64 to 68 for the five named here" (routing page) | Four of the five were read; Claude Sonnet 5.5 at Medium is marked not read | Corrected |
| "As lead, its own requests were 72% to 74% of one session's token cost", following a sentence about Claude Opus 5.5 (delegate profiles) | The measured lead was Claude Fable 5.2, and the share is of a list-price equivalent | Corrected |
| "Design left open has only the lead's model on record here" (delegate profiles) | Opus and Gemini 4 Neon lead sessions are recorded; how much design either was left is not | Corrected |
| "none known" as the substitute for standards and pull-request prose (routing page) | GPT-6.2 Sol passed the one matched prose leaf with no repair | Corrected |
| "A spent window comes back as `refused`" (delegate profiles) | No real refusal has been seen through the call, and the hosts page already says a refusal can arrive as another outcome | Narrowed |
| "Five of the seven duties" (trial record) | The record's table has eight rows | Left: a dated record is not edited |

## Two trials that could change the order

The second-family reader proposed two shared leaves, entered in stages, each with the
same issue, base and brief for every candidate, frozen by the owner or a neutral
editor, separate worktrees, and scoring of the lead's duties from what the session left
behind, with correct verification and handover ahead of speed. Each is one leaf of its
kind, so an unclear result calls for one more leaf in the disputed kind.

1. **A documentation leaf led unattended** by Claude Opus 5.5, GPT-6.2 Sol and Gemini 4
   Neon: one real delegation, a clean review, checked citations, the reviewed head
   through CI, and a written handover. The order changes if Sol completes correctly
   and Opus needs a material intervention or misses a duty. Neon moves up for
   documentation if it finishes unattended with checked citations and the correct head
   while a candidate above it fails those duties; otherwise it stays the watched
   fallback.
2. **A source leaf with an open design decision** led by Claude Opus 5.5, GPT-6.2 Sol
   and GPT-6.2 Astra, with one seeded wrong citation or misleading passing report for
   the lead to find; Neon joins only if it passed the first trial. Astra moves ahead
   of Sol if it verifies and delivers while Sol misses a material issue, or reaches
   equal verified quality at clearly lower observed quota. Codex moves ahead of Opus,
   when only Fable is spent, if its candidate is at least as reliable on the
   documentation leaf and materially better on the source leaf.

Neither is registered as work. Each needs the owner to start a lead session on a coding
agent other than the one that wrote this record.

## No evidence found

- A measured ranking of these models as leads, or of a lead checking a delegate's
  report against the code. The search was one reader's, on one day; it does not show
  that none exists.
- A time-horizon figure for any of these models from its measuring body's own page.
- Context-window sizes for the Gemini 4 models, and any measurement of how a session
  degrades after its context is compacted.
- A public comparison of these models as the main agent in Codex.
- The numbers behind any weekly limit.

## Limits

- **Nobody rechecked a public figure.** Each was read once by a sub-agent through a
  summariser; several pages carry no date.
- **Three of the four readers share the lead's model family.** The second-family
  reader saw only this repository's records, which that family mostly wrote.
- **No lead was tried.** The Codex sandbox behaviour above is from documentation and
  inference, not from a lead session.
- **The models are new.** Figures read within days of a release often move.

[Acceptance index](index.md).
