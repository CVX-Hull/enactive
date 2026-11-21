---
owner: lead
review_trigger: A served model is added, retired or repriced, a quota changes, a coding agent's version changes, a default effort changes, or a row is observed in this repository
status: active
---

# Choosing a model for engineering work

A lead on any [coding-agent host](coding-agents.md) reads this page to choose the model
for a piece of engineering work. The choice is the lead's judgment for each task
([choosing the delegate](../standards/agents.md#the-leads-duties)): this page advises by
kind of work, the [delegate profiles](delegate-profiles.md) say how each coding agent
and model has done in this repository, and neither is a rule. No tool or check chooses a
delegate from the table below, and the [delegate call](coding-agents.md#starting-a-delegate-on-any-coding-agent)
starts whatever the lead names. It concerns the lead's own model and delegation only: the playing actor's, curator's
and judges' models are frozen per run under the
[player host contract](../contracts/player-host.md).

## How to read a row

The figures behind the table are in the
[dated evidence record](../acceptance/2026-11-19-coding-agent-model-evidence.md), each
with its source, model version, effort, date and how it was read. Three things hold for
every row:

- **A figure belongs to the model version and effort it was read on.** When a model is
  replaced, its rows read "inherited, not re-observed" until someone observes the
  successor.
- **A public score is a coding agent and a model together**, nearly always the model in
  its maker's own agent, on tasks that are not this repository's. A gap of a few points
  is treated here as too small to act on.
- **Effort was read across its range for one model only.** On Claude Fable 5.2 the score
  moved ten points between Low and High, and the highest setting scored lower at
  several times the cost. Starting at High is a judgment carried from that one model to
  the others.

One session's work as lead on a documentation leaf is in the
[trial record](../acceptance/2026-11-19-antigravity-lead-trial-810.md). A row changes on our own evidence
through a [matched run](#matched-runs-on-this-repositorys-leaves), the same leaf on two
coding agents, not on a public board alone. Every delegated attempt on a code or review
leaf, matched or not, is a row of `data/evaluation/coding-agent-attempts.jsonl`
([reading the ledger](#reading-the-ledger)).

## Route by kind of work

Every choice here is provisional advice with its reason, for the lead to weigh with the
task in front of it; a first choice is where to start thinking, not what must be used.
A cell names an effort only where a figure was read at
that effort; "not read" marks a setting chosen by judgment. Which changes get a review,
and how many, is owned by [review](../workflows/review.md); this page only says which
model to give it.

| Kind of work here | First choice | Substitutes, in order | Avoid | What it rests on |
| --- | --- | --- | --- | --- |
| Hard change across harness, protocol and bridge that must merge | Claude Fable 5.2 at High | Claude Fable 5.2 at Extra-high; Claude Opus 5.5 at Max; Gemini 4 Neon at Extra-high; GPT-6.2 Astra at Extra-high | Fable at Max; Haiku and Luna, read at Max; Argon, effort not read | Index 58 at High and at Extra-high; the patch score of 49 was read at Extra-high only |
| Bounded implementation from a written brief | GPT-6.2 Sol at Extra-high | GPT-6.2 Astra at Extra-high; Claude Opus 5.5 at High (not read) | Claude Sonnet 5.5 at Max as the first choice | Sol's index of 50 at 12.6 minutes, the least time read; no figure isolates work from a brief. One [matched run](#matched-runs-on-this-repositorys-leaves) here, on 20 November 2026 (issue 834): both attempts passed acceptance with no repair; GPT-6.2 Sol at Extra-high was preferred blind over Claude Opus 5.5 at High for how its checks failed, and took 635 seconds against 510, then 502 more for one repair after review. One observation moves no default |
| Exploration that needs synthesis across files | Gemini 4 Neon at Extra-high | Claude Opus 5.5 at Max; Claude Sonnet 5.5 at Max; Gemini 4 Carbon at High; Claude Sonnet 5.5 at Medium (not read) as a sub-agent | Claude Haiku 5.5 and GPT-6 Luna, both read at Max | Codebase question scores of 64 to 68 for the four of these that were read against 34 and 38; Sonnet at Medium was not read |
| Locating files and mechanical sweeps | the smallest model the host serves | none needed | a large model | Cost only; no figure read |
| Shell, checks and Python tooling | one of the six models whose terminal scores overlap, at the effort read | whichever of them has quota | Claude Haiku 5.5; GPT-6 Luna; Gemini 3.8 Flash | Terminal task scores, six configurations |
| Reading run ledgers, logs and tables | the synthesis explorer | none known | none known | Judgment; no public evidence found |
| Standards and pull-request prose | the lead | GPT-6.2 Sol at Extra-high | none known | Judgment; no public evidence found. One [matched run](#matched-runs-on-this-repositorys-leaves) here, on 20 November 2026 (issue 811): both attempts passed acceptance with no repair; the lead's model, Claude Fable 5.2 at High, was preferred blind over GPT-6.2 Sol at Extra-high, which took 406 seconds against 710. One observation moves no default |
| Acceptance and design records | the lead | none known | none known | Judgment; no public evidence found |
| Research on outside systems | a large model that fetches the page it cites | Gemini 4 Carbon or Argon where a wrong answer costs more than no answer | answering from memory | The first choice is judgment; wrong-answer rates were read for those two models only |
| Review of code | the host's reviewer role, clean context | another family's reviewer when the window is spent | acting on a quoted passage before checking it against the tree | The choice is judgment; reviewer products built on two Claude models were read, with no effort reported |
| Review of documents | one clean-context reviewer: the host's reviewer role, or a second family's where one has quota and its run starts from a clean context | none known | none known | The choice is judgment; one preprint, read second-hand, is weak support |

The rows that rest on judgment are most of what this repository merges.

## Roles and their default models

Role definitions are tracked in this repository, so a change to a role applies to this
project alone and every host is given the same instruction text. One shared instruction per role lives
in `.agents/roles/`; each host has a thin wrapper that names the model and points to it.

| Role | Claude Code (`.claude/agents/`) | Codex (`.codex/agents/`) | Antigravity (`.agents/agents/`) |
| --- | --- | --- | --- |
| Explorer, locating | `locator`: Haiku | `locator`: GPT-6 Luna at Low | `locator`: alias `flash_lite` |
| Explorer, synthesis | `Explore`: Sonnet at Medium | `explorer`: GPT-6.1 Terra at Medium | `explorer`: alias `pro` |
| Worker | `worker`: Opus at High | `worker`: GPT-6.2 Sol at Extra-high | `worker`: alias `pro` |
| Reviewer | `reviewer`: Opus at High | `reviewer`: GPT-6.2 Sol at Extra-high | `reviewer`: alias `pro` |

These are what each host's own role file runs when the lead starts the role natively.
They are not eligibility rules and not the lead's default choice: through the
[delegate call](coding-agents.md#starting-a-delegate-on-any-coding-agent) the lead
names the coding agent, model and effort for the task, and states them with its reason
on the brief's Role line and in the pull request.

- **Claude Code** reads the project's `.claude/agents/` ahead of a user's own
  definitions of the same name. The lead names another model for one task with the
  delegation call's model override. Sub-agents of all four roles ran in the one lead
  session measured on 19 and 20 November 2026: 20 explorers, 6 reviewers, 4 workers and 1
  locator ([token use](../acceptance/2026-11-20-coding-agent-token-use.md)).
- **Codex** reads `.codex/agents/` in a checkout the user trusts. All four model
  selectors answered a one-word prompt on CLI 0.171.0, twice; the role files themselves
  were not exercised as sub-agents.
- **Antigravity** role files use its native aliases; a full model identifier in a
  role file was not tested. `agy agents` (CLI 1.5.13) listed all four files from the
  main checkout, and none from a worktree of it, from a scratch copy, or from that copy
  after `git init`; nothing else was tried. The one recorded trial did not use them: it
  started its explorer as the host's `research` type and defined its own `worker` type
  ([trial record](../acceptance/2026-11-19-antigravity-lead-trial-810.md)).

## Quota and spending

- **Included subscription quota only.** A spent window is a wait or the next
  substitute, never a purchase. No provider key is set in a shell that starts a coding
  agent ([R-KEY-LEAK](../risks.md)).
- **Read the remaining quota before a large delegation.** The settings that keep paid
  overflow off on each host have not been read for this project; check them in each
  host's own settings before relying on them.
- **Spend the scarcest window on the work that needs it.** The hard-change row's first
  choice and substitutes are the candidates to consider for a hard change; bounded and
  locating work can go to cheaper models.
- **Keep the lead's context small.** The lead's context is sent again on every
  request. In the one lead session measured here the lead's own requests were 72% to
  74% of the tokens' list-price equivalent, and about half of the lead's part was
  re-reading a context whose median was 325,920 to 743,067 tokens in each quarter of
  the session ([token use](../acceptance/2026-11-20-coding-agent-token-use.md)). No
  session with a smaller context was measured beside it. So: one lead
  session for one leaf or one batch that merges together; summarize the session or hand
  the role to a fresh session before the context passes about 300,000 tokens; and send
  wide reading and long command output to a sub-agent that returns a short report. This
  is guidance and nothing checks it. The 300,000 figure is a judgment from that one
  session, not a measured optimum.

## When the lead's model has no quota left

The lead role passes to another session or coding agent
([handing over through the issue](../standards/agents.md#the-leads-duties)). The
readers found no comparison of these configurations as leads, here or in public, so
this is where to start thinking, with its reasons, and not a default
([evidence read on 20 November 2026](../acceptance/2026-11-20-lead-succession-evidence-866.md)):

| What is spent | Where to start | Then | Why |
| --- | --- | --- | --- |
| Only the limit of Claude Fable 5.2 | Claude Code on Claude Opus 5.5, at High or above | Codex on GPT-6.2 Sol at Extra-high, then GPT-6.2 Astra at Extra-high | Opus made more lead requests than Fable in the transcripts sampled here, on the coding agent whose lead workflow is in use. Its effort as lead was not recorded; one public index that is not specific to coding puts it seven points lower at High than at Max |
| The whole Claude window | Codex on GPT-6.2 Sol at Extra-high | Codex on GPT-6.2 Astra at Extra-high; the Antigravity app on Gemini 4 Neon at High with the owner present, for engineering work that needs no gameplay | Sol has the local record of the work a lead does: code preferred blind and nine confirmed review findings. Trying Astra first for a hard change with open design is judgment: no local attempt compares it with Sol, and the maker estimates about a third as many Astra messages as Sol messages in five hours on its smaller plans. The one Antigravity lead session needed the owner and a second session to finish; for a watched documentation leaf it may come before Astra |

- **Check which limit the session shows as spent first.** Each coding agent shows what
  remains in a session ([delegate profiles](delegate-profiles.md)).
- **A Codex lead has gaps to route around.** The delegate call has not been run from
  one, and its sandbox denies the network by default
  ([hosts page](coding-agents.md#starting-a-delegate-on-any-coding-agent)).
- **The duty to verify a delegated result does not change with the lead**
  ([the lead's duties](../standards/agents.md#the-leads-duties)).

## Matched runs on this repository's leaves

A matched run gives one leaf to two coding agents and keeps both results, so a row can
change on how its models did on this repository's own work. It is the control
C-MATCHED-RUNS on the [controls page](../controls.md), which owns its risk and cost.

### When and on what

A [trigger](#keeping-this-page-current) may start a matched run on the rows it changes,
and so may a routing row never observed here; the lead names the row and decides
whether the run is worth its cost. It applies to rows whose leaf ends in a diff that
can merge, not to review, research or reading rows. The lead picks one Ready leaf
([work items](../workflows/work-items.md#ready-brief-and-execution-capacity)) of that
row's kind of work that needs no game runtime and no paid model call. At most three
leaves are run per trigger. Where a row's first choice is a role and not one model, the
first choice is the model that role runs on in the lead's session.

### Running it

1. The leaf goes to the row's first choice and to one challenger the lead names. These
   are the two implementation workers
   [work items](../workflows/work-items.md#ready-brief-and-execution-capacity) allows,
   under its exception for a matched run: the two share owned paths and one merges.
2. Both get the same brief and the same base commit, each in its own worktree on its own
   branch ([environment facts](coding-agents.md#environment-facts-for-agents)). The
   branch name says the leaf, not the coding agent.
3. The lead reruns the brief's acceptance check on both final commits, whatever each
   attempt reported, and counts the repairs it had to ask for.
4. A clean-context reviewer compares the two diffs under neutral labels, such as "left"
   and "right", that name no model or coding agent. It gets the diffs as files
   (`git diff <base> <head>`) outside the checkout, and its brief forbids reading
   branches or history, because commit trailers and branch logs name the model. The lead
   alone keeps the mapping from label to attempt.
5. The lead merges one attempt and discards the other. When neither passes, the lead
   discards both and takes the leaf back.
6. In the pull request that merges the chosen attempt, or in the lead's own pull request
   for the leaf when both are discarded, the lead adds one row per attempt to
   `data/evaluation/coding-agent-attempts.jsonl`, in the shape of
   `schemas/coding-agent-attempt.schema.json`, each with its `blind_preference`. The
   kind of work is the table's first cell. `tests/test_coding_agent_attempts.py`
   refuses a row the reading rules below cannot use.

## Reading the ledger

`data/evaluation/coding-agent-attempts.jsonl` holds one row for each delegated attempt
on a code or review leaf: the worker, reviewer or explorer the lead chose, the reason
it gave, and how the attempt went. The lead adds the row in the pull request the
attempt served. The delegate call's `result.json` supplies the coding agent, its
version, the model, the effort, the date, the wall time and how the start ended
(`hand_back`); the lead supplies the reason, its own rerun of the acceptance check, the
repairs it asked for, whether it merged or used the result, a reviewer's findings as
dispositioned, and any false report. A row whose `blind_preference` is not null is one
of a matched run's two attempts.

- **Read single attempts as a record, not a score.** For one configuration (coding
  agent, model and effort) in one role and kind of work: how often it handed back, how
  often the lead's rerun passed without a repair, how long it took, and for a reviewer
  how many findings were confirmed against how many rejected. The
  [delegate profiles](delegate-profiles.md) summarize these.
- **Count matched pairs within one kind of work.** Wins and losses are counted for a pair of
  configurations (coding agent, model and effort) within one kind of work, never across
  kinds. An attempt wins when its `acceptance` passed and the other's failed. When both
  passed, the one with `blind_preference` `preferred` wins, and `no_preference` is a
  tie. When both failed, neither wins.
- **A default moves on a large one-sided split,** or on equal quality at clearly lower
  quota, as the hosts' own usage readings show. A move is a change to the row and, where
  it names a role's default, to the role file.
- **One false report is enough to record.** A timeout reported as success, or quoted text
  that exists nowhere in the tree or its cited source, is written into that attempt's
  `false_report` field in the ledger, which carries its date and issue, whatever the
  count.
- **Few observations, confounded by the task.** The rows are evidence of fit here, never a
  ranking of models or coding agents.

## Keeping this page current

There is no calendar pass. A row is re-read when one of these happens:

- a model is added, retired or repriced on a host;
- a quota or plan changes;
- a coding agent's version changes;
- a default effort changes;
- a row is observed here for the first time.

On a trigger the lead re-reads the affected sources, adds a new dated record, and marks
rows whose model was replaced as inherited. A default in a role file moves on a
[matched run](#matched-runs-on-this-repositorys-leaves), or on a clear change in the
public figures when no matched run exists.

What was read of each host's models on 19 November 2026 is in the
[evidence record](../acceptance/2026-11-19-coding-agent-model-evidence.md#measured-here):
a full listing for one host, the delegation selectors for another and four selectors that
answered for the third. A trigger compares the host's current listing with it.

[Operations index](../runbook.md).
