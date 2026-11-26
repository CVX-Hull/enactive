---
owner: lead
review_trigger: A served model is added, retired or repriced, a quota changes, a coding agent's version changes, a default effort changes, or a row is observed in this repository for the first time
status: active
---

# Choosing a model for engineering work

The lead chooses the engineering model for each task and names the delegate. The
table gives a starting point. The [delegate profiles](delegate-profiles.md) describe
the local evidence for each configuration. [S-AGENT](../standards/agents.md#the-leads-duties)
owns the decision. Gameplay, curator and judge models are frozen separately per run
under the [player host contract](../contracts/player-host.md).

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

Use [matched runs](matched-runs.md#matched-runs-on-this-repositorys-leaves) to compare candidates on
the same leaf. [Reading the ledger](#reading-the-ledger) gives the conditions for
changing a routing row.

## Route by kind of work

“Not read” marks an effort chosen by judgment. The [review workflow](../workflows/review.md)
determines which changes get reviewed and how many reviewers they get.

| Kind of work here | First choice | Substitutes, in order | Avoid | What it rests on |
| --- | --- | --- | --- | --- |
| Hard change across harness, protocol and bridge that must merge | Claude Fable 5.2 at High | Claude Fable 5.2 at Extra-high; Claude Opus 5.5 at Max; Gemini 4 Neon at Extra-high; GPT-6.2 Astra at Extra-high | Fable at Max; Haiku and Luna, read at Max; Argon, effort not read | Index 58 at High and Extra-high; patch score 49 at Extra-high only. Local ledger has 16 unmatched worker attempts (GPT-6.2 Sol at High/Extra-high, Claude Opus 5.5 at High, one failed Fable High attempt); defaults stay unchanged without matched runs. |
| Bounded implementation from a written brief | GPT-6.2 Sol at Extra-high | GPT-6.2 Astra at Extra-high, then Claude Opus 5.5 at High (not read) | Claude Sonnet 5.5 at Max as the first choice | Sol scores 50 on the public index and has the shortest time among the configurations examined. One local matched run (`#834`) favored Sol over Opus; defaults stay unchanged. |
| Exploration that needs synthesis across files | Gemini 4 Neon at Extra-high | Claude Opus 5.5 at Max; Claude Sonnet 5.5 at Max; Gemini 4 Carbon at High; Claude Sonnet 5.5 at Medium (not read) as a sub-agent | Claude Haiku 5.5 and GPT-6 Luna, both read at Max | Codebase question scores of 64 to 68 for the four of these that were read against 34 and 38; Sonnet at Medium was not read |
| Locating files and mechanical sweeps | the smallest model the host serves | none needed | a large model | Cost, and one local [lookup set](../acceptance/2026-11-26-locator-lookups-across-model-tiers.md): on fourteen lookups Claude Haiku 5.5 and GPT-6 Luna at High answer as exactly as GPT-6.2 Sol at Extra-high, in 17 to 32 seconds, GPT-6 Luna at Low misses one, and no configuration states a wrong location. |
| Shell, checks and Python tooling | one of the six models whose terminal scores overlap, at the effort read | whichever of them has quota | Claude Haiku 5.5; GPT-6 Luna; Gemini 3.8 Flash | Terminal task scores, six configurations. Two unmatched local worker passes (GPT-6.2 Sol at Extra-high on `#905`, GPT-6.2 Astra at Medium on `#914`). |
| Reading run ledgers, logs and tables | the synthesis explorer | none known | none known | The choice is judgment; no public evidence found. In a local [study](../acceptance/2026-11-26-run-evidence-diagnosis.md) of eight incidents already diagnosed here, no explorer configuration states a wrong cause; Claude Opus 5.5 and Gemini 4 Carbon state the recorded cause on all eight and the GPT-6.2 configurations on six. On the same incidents [across tiers](../acceptance/2026-11-26-diagnosis-and-frame-reading-across-model-tiers.md), Claude Fable 5.2 and Gemini 4 Argon state eight, Claude Sonnet 5.5 at Medium seven, and smaller models fewer; the lead judges one of 86 answers wrong. One local review observation (GPT-6.2 Astra at High on `#896`, 2 confirmed findings). |
| Reading retained game frames | a reviewer start the [delegate profiles](delegate-profiles.md#what-to-weigh) list as reading frames | another of those starts with quota | a start the profiles do not list | Local probes on nineteen configurations, cited in the profiles; seventeen answer all eight questions correctly |
| Standards and pull-request prose | the lead | GPT-6.2 Sol at Extra-high | none known | Judgment; one local matched run (`#811`) favored Fable over Sol. No public comparison for this work is recorded. |
| Acceptance and design records | the lead | none known | none known | Judgment; no public evidence found. Four unmatched local worker passes (Claude Opus 5.5 at High on `#925`). |
| Research on outside systems | a large model that fetches the page it cites | Gemini 4 Carbon or Argon where a wrong answer costs more than no answer | answering from memory | The first choice is judgment; wrong-answer rates were read for those two models only |
| Review of code | the host's reviewer role, clean context | another family's reviewer when the window is spent | acting on a quoted passage before checking it against the tree | The choice is judgment; reviewer products built on two Claude models were read, with no effort reported. In a local [replay](../acceptance/2026-11-25-reviewer-recall-replay.md) of five past code commits holding six later-fixed defects, each GPT-6.2 reviewer finds 3, and Claude Opus 5.5 finds 1 through the plan-mode start the reviewer used then and 3 through an experimental start without plan mode, each run once. The reviewer's current start has no such figure. The set is small and does not rank the models. |
| Review of documents | If the [review workflow](../workflows/review.md) selects a review, use the host's clean-context reviewer or a second family's clean-context reviewer with quota. | none known | none known | Judgment, with weak support from one preprint read second-hand. In a local [replay](../acceptance/2026-11-25-reviewer-recall-replay.md) of four past document commits holding ten later-fixed defects, GPT-6.2 reviewers find 4 to 7 and Claude Opus 5.5 reviewers 1 to 3, each run once; a GPT-6.2 reviewer finds defects that no Claude Opus 5.5 reviewer finds. Every one of the four commits has a Claude co-author, so this does not rank the models. |

Only two local matched comparisons exist (`#811` prose and `#834` bounded code), so no
row meets the [threshold for changing a default](#reading-the-ledger).

## Tiers by kind of work

This table groups configurations by what the cited evidence shows for each kind of
work. A group holds configurations the evidence does not separate. The route table
above stays the advice; a first choice there moves only under
[reading the ledger](#reading-the-ledger). Inside a group, choose by
[what each configuration costs](#what-each-configuration-costs-and-can-do): the quota
left, the wall time and what the start can do.

"Local" is a result on this repository, in the
[delegate profiles](delegate-profiles.md) or a dated record. "Public" is a figure in
the [re-read of 26 November 2026](../acceptance/2026-11-26-coding-agent-model-evidence-reread.md),
measured on other tasks, nearly always in the maker's own coding agent and at the
effort named. A local result from a leaf of
[the model-tier outcome](https://github.com/CVX-Hull/enactive/issues/987) informs the
row when it lands. A configuration in the "No figure for this work" column has no
local or public figure of the kind the row uses, which is not a finding against it. Gemini 4 Argon, Gemini 3.8 Flash and GPT-OSS 120B
leave Antigravity on 30 November 2026.

| Work | Strongest group | Middle group | Lowest group | No figure for this work | What the groups rest on |
| --- | --- | --- | --- | --- | --- |
| Checking a hand-back against its files | all three false facts caught and no plain-fact hand-back rejected: Claude Sonnet 5.5 at Medium; GPT-6.2 Astra at Medium; Claude Haiku 5.5 at High; Claude Opus 5.5 at High; Claude Fable 5.2 at High; Gemini 4 Neon, Argon and 3.8 Flash at High | all three caught, one or two plain-fact hand-backs rejected: GPT-6.2 Sol at Extra-high; Gemini 4 Hydrogen at High; GPT-6.1 Terra at Medium | two of three caught: GPT-6 Luna at High and Low. Does not finish: Gemini 4 Carbon at High, stopped at 900 seconds on three of nine checks. No use: GPT-OSS 120B, two verdicts in nine starts | other efforts | Local [verification set](../acceptance/2026-11-26-hand-back-verification-across-model-tiers.md): nine hand-backs, each verifier once. It measures one lead duty and not leading. The GPT-6.2 and GPT-6.1 verifiers reject a stated cause the files do not record; the lead's own key accepts two such hand-backs. |
| Leading a leaf | not separated | not separated | not separated | every configuration | No comparison of leads exists, locally or publicly. The lead is Claude Fable 5.2 at High and the [succession order](#when-the-leads-model-has-no-quota-left) names what follows it; both are judgment. |
| Hard change that must merge | index 55.5 to 58.6: Gemini 4 Neon at Extra-high; Claude Fable 5.2 at Extra-high, High and Max; Claude Opus 5.5 at Max; Claude Sonnet 5.5 at Max; Gemini 4 Carbon at High | index 47.5 to 53.5: GPT-6.2 Astra at Medium and above; Claude Fable 5.2 at Medium and Low; Gemini 4 Hydrogen at Extra-high; GPT-6.2 Sol at High and above; GPT-6.1 Terra at Max | index 25.9 to 45.5: Gemini 4 Argon at High; GPT-6.2 Sol at Medium and Low; GPT-6.2 Astra at Low; Claude Haiku 5.5 at Max; GPT-6 Luna at Max | Gemini 3.8 Flash; GPT-OSS 120B; the Claude models at efforts below Max, except Fable | Public index, each in its maker's agent. Fable at Max scores below Fable at High and takes four times as long, which is why the route avoids it. Local: nine hard changes by GPT-6.2 Sol workers at High and Extra-high all hand back. |
| Bounded implementation from a written brief | GPT-6.2 Sol at Extra-high, 17 of 17 handed back, and at High, 7 of 7 | Claude Opus 5.5 at High, 10 of 16 handed back; five of the six misses are time limits on one issue | none | every other configuration, GPT-6.2 Astra included: the hard-change row's public index is the nearest figure | Local worker attempts on this kind of work, and one matched run that favors Sol over Opus. A hand-back is not a pass. The route's substitute order, Astra before Opus, is judgment. A Gemini worker edits files and runs no command, so the lead runs its check. |
| Exploration that needs synthesis | codebase questions 59.9 to 67.7: Gemini 4 Neon at Extra-high; Claude Opus 5.5 at Max; Claude Sonnet 5.5 at Max; Gemini 4 Carbon at High; Claude Fable 5.2 at every effort; Gemini 4 Hydrogen at Extra-high | 50.3 to 55.1: GPT-6.2 Astra at Medium and above; Gemini 4 Argon at High; GPT-6.1 Terra at Max; GPT-6.2 Sol at Medium to Extra-high | 33.9 to 46.2: GPT-6.2 Sol at Max and Low; GPT-6 Luna at Max; GPT-6.2 Astra at Low; Claude Haiku 5.5 at Max | GPT-OSS 120B; Gemini 3.8 Flash on this board, which scores 47.0 on an older board in another agent | Public codebase questions. Local: four explorations by Gemini 4 Neon at Extra-high are all used, and on this kind of work explorers on Claude Opus 5.5, GPT-6.2 Sol and GPT-6.2 Astra hand back 49 of 50. |
| Reading run ledgers, logs and tables | states the recorded cause on 8 of 8 incidents: Claude Opus 5.5 at High and Medium; Claude Fable 5.2 at High; Gemini 4 Carbon at High; Gemini 4 Argon at High | on 6 or 7: Claude Sonnet 5.5 at High and Medium; GPT-6.2 Sol at Extra-high; GPT-6.2 Astra at High and Medium; GPT-6 Luna at High; Gemini 4 Neon at High, with two starts that return nothing | on 5 or fewer: GPT-6.1 Terra at High and Medium; Claude Haiku 5.5 at High, with one wrong cause; Gemini 4 Hydrogen at High; Gemini 3.8 Flash; GPT-6 Luna at Low; GPT-OSS 120B; a Claude model through Antigravity | other efforts | Local, the lead's verdicts on eight incidents each run once ([first study](../acceptance/2026-11-26-run-evidence-diagnosis.md), [across tiers](../acceptance/2026-11-26-diagnosis-and-frame-reading-across-model-tiers.md)). A second judge differs on four of 88 answers. The re-read reports no public figure for this work. |
| Locating files and mechanical sweeps | 14 of 14 lookups in 17 to 32 seconds: Claude Haiku 5.5 at Low and High; GPT-6.1 Terra at Medium and High; Claude Sonnet 5.5 at Medium and High; GPT-6 Luna at High; GPT-6.2 Sol at Extra-high | 13 of 14, one existing thing reported as not found: GPT-6 Luna at Low, in 22 seconds | 13 of 14 in 355 to 509 seconds: Gemini 4 Neon and Hydrogen at High. 8 of 14, with six existing things reported as not found: Gemini 3.8 Flash at Low. No answers: Gemini 3.8 Flash at High, which does not finish in 900 seconds, and GPT-OSS 120B, which hands back a plan | Claude Fable 5.2; Claude Opus 5.5; GPT-6.2 Astra; Gemini 4 Carbon and Argon | Local [lookup set](../acceptance/2026-11-26-locator-lookups-across-model-tiers.md): fourteen lookups with one searchable name each, every configuration once. None states a wrong location; the misses are a "not found" for a class in a test file. An Antigravity locator has no shell to search with. |
| Shell, checks and Python tooling | terminal tasks 61.2% to 65.8%: Claude Opus 5.5, Claude Fable 5.2, Claude Sonnet 5.5, GPT-6.2 Astra and GPT-6.2 Sol at Max; Gemini 4 Carbon at High; Gemini 4 Neon at Extra-high | 53.3% to 56.4%: Gemini 4 Hydrogen at High; Gemini 4 Argon at High; GPT-6.1 Terra at Max | 15.2% to 40.0%: Claude Haiku 5.5 at Max; Gemini 3.8 Flash at High, in another maker's agent; GPT-6 Luna at Max | GPT-OSS 120B | Public terminal tasks, intervals near 3 points; Neon's and Hydrogen's intervals overlap. The route's six overlapping models are the first group without Neon, whose row is newer. An Antigravity delegate runs no command, so a Gemini model does this work only as an app lead. |
| Reading retained game frames | all eight answers in under 20 seconds: Claude Sonnet 5.5 at High and Medium; GPT-6.1 Terra at High and Medium; GPT-6 Luna at Low; Claude Haiku 5.5 at High; GPT-6.2 Sol at Extra-high; GPT-6.2 Astra at Medium; Claude Opus 5.5 at High; Gemini 4 Hydrogen at High; Claude Sonnet 5.5 through Antigravity | all eight in 21 to 152 seconds: GPT-6 Luna at High; Claude Fable 5.2 at High; Gemini 4 Argon, Neon and Carbon at High; Gemini 3.8 Flash at High | no answers: GPT-OSS 120B, which reports no tool that renders an image; Claude Opus 5.5 through Antigravity, cause unknown | other efforts | Local probes on text and a highlighted button, one start each; Gemini 4 Neon's is its second, after a quota refusal. Comparing two frames and reading a map are untested. |
| Standards and pull-request prose | Claude Fable 5.2 at High as a worker, preferred in the one matched run | GPT-6.2 Sol at Extra-high, the other side of that run | none | every other configuration | Local: one matched run between two workers; that the lead writes this work itself is judgment. The re-read reports no public evidence for this work. |
| Acceptance and design records | not separated | not separated | not separated | every configuration except the two observed | Two unmatched local observations as workers: four passes by Claude Opus 5.5 at High on one issue, and one dated record that Gemini 4 Neon at High writes from given sources and the lead merges unchanged. Neither separates configurations; that the lead writes records itself is judgment. |
| Research on outside systems | not separated: the route's choice is a large model that fetches the page it cites | not separated | not separated | every configuration, for research with sources | No figure measures research with sources across these models. Two narrower public figures: answering from memory, the share of non-correct answers that are wrong guesses is 4% to 14% for the Gemini 4 models, 34% to 59% for the Claude and GPT-6 models and 79% for GPT-6 Luna, so a Gemini 4 model suits a question where a wrong answer costs more than none; and in summaries of a given source, unsupported content is 9.9% for Claude Opus 5.5, 12.1% for Gemini 4 Argon and 14.2% for GPT-OSS 120B. |
| Review of code | 3 of 6 known defects: GPT-6.2 Sol at Extra-high; GPT-6.2 Astra at High and Medium; Claude Opus 5.5 at High started without plan mode | 2 of 6: Claude Sonnet 5.5 at High through the current start; GPT-6.1 Terra at High | 1 of 6: Claude Opus 5.5 at High and Medium through the plan-mode start the reviewer used then | no local recall figure: Claude Opus 5.5 through the current start; Claude Fable 5.2; Claude Haiku 5.5; GPT-6 Luna; Gemini 4 Hydrogen and Argon; Gemini 3.8 Flash; GPT-OSS 120B; Gemini 4 Neon at High, which returns no code review in 15 starts made before the call told it to run no command. Partly covered: Gemini 4 Carbon at High finds 2 of the 4 defects in the commits it reviews, and hands back 3 of 13 code-review starts | Local [replay](../acceptance/2026-11-25-reviewer-recall-replay.md) of five code commits, counted when two judges agree; each configuration reviews a commit once, and a Gemini start refused on quota is started again. Hand-back counts are availability, not recall. Public, inside other makers' reviewers: Claude Opus 5.5 recalls 55% to 61% of high-severity issues and Claude Sonnet 5.5 44% to 48%. The two middle models are in the [added reviewers](../acceptance/2026-11-26-reviewer-recall-replay-added-reviewers.md) record: each finds four of the sixteen defects, and a different four. As a second reviewer Claude Sonnet 5.5 adds one to three defects to a GPT-6.2 reviewer, GPT-6.1 Terra adds none to one and three to Claude Opus 5.5; its nine reviews take 565 seconds, the shortest total here. |
| Review of documents | 4 to 7 of 10 known defects: GPT-6.2 Sol at Extra-high, 7; GPT-6.2 Astra at High, 5, and at Medium, 4 | 2 or 3 of 10: Claude Opus 5.5 at High, with or without plan mode; Claude Sonnet 5.5 at High; GPT-6.1 Terra at High | 1 of 10: Claude Opus 5.5 at Medium; Gemini 4 Carbon at High | the same configurations as for code, Gemini 4 Carbon apart. Partly covered: Gemini 4 Neon at High finds 2 of 4 in its one returned review | Local replay of four document commits. Every one of them has a Claude co-author, so part of the gap may be the second family and not the model. An Antigravity review counts as a second family's view, not as the clean-context review. |
| Judging answers against written criteria | the two reference judges, GPT-6.2 Sol at Extra-high and Claude Opus 5.5 at High, which agree on 106 of 114 verdicts; and the judges that give 101 to 106 of their 106 shared verdicts: GPT-6.1 Terra at Medium and High, Claude Sonnet 5.5 at Medium and, with 102 of 104 judged, at High, GPT-6.2 Astra at Medium and High, Gemini 4 Neon at High, Claude Fable 5.2 at High | 97 of 105 or 106: Gemini 4 Hydrogen at High; Claude Haiku 5.5 at High | 86 of 92 and 68 of 85, with unreadable replies: GPT-6 Luna at High and at Low | Gemini 4 Carbon, stopped for its time; the models leaving Antigravity | Local agreement between judges, which is not accuracy against independent labels. Pairing judges from two families is judgment. Public: one vendor post gives Claude Opus 5.5 both 94.7% and 94.4% on one judging benchmark and Claude Haiku 5.5 a rank correlation of 0.442 on another. The groups are from [judging across model tiers](../acceptance/2026-11-26-judging-across-model-tiers.md): eighteen packets, each judge once. GPT-6.1 Terra at Medium matches all 106 in 873 seconds and Claude Sonnet 5.5 at Medium 104 in 703; Gemini 4 Neon takes 3,391. On the eight cells the reference judges dispute, the Codex judges together lean to GPT-6.2 Sol and the Claude judges to Claude Opus 5.5, with exceptions in both. |

The role files' defaults are in [the table below](#roles-and-their-default-models).
For bounded implementation the Codex worker default, GPT-6.2 Sol at Extra-high, is in
the strongest group and the Claude Code default, Claude Opus 5.5 at High, in the middle.
The synthesis-explorer defaults, Claude Sonnet 5.5 and GPT-6.1 Terra at
Medium, are in the middle and lowest groups for reading run evidence, so the lead names
a stronger configuration in the delegate call when a cause must be read from run
evidence.

## What each configuration costs and can do

Speed is the public output speed in tokens a second across efforts, measured on the
maker's own service except where noted; time to a first answer grows steeply with
effort. Local hand-backs are counts from the
[attempts ledger](../../data/evaluation/coding-agent-attempts.jsonl) through the
delegate call, all roles and kinds of work together. List price is a signal of relative
cost only; no page gives the share of a subscription window a model uses, and the
limits named are those of the plans the pages describe.

| Configuration | Limit it draws on | Relative cost | Speed | Local hand-backs | Notes |
| --- | --- | --- | --- | --- | --- |
| Claude Fable 5.2, Claude Code | a separate weekly Fable limit on larger plans, and the limits Claude models share | list price twice Opus | 109 to 113 | 10 of 12 | See [quota and spending](#quota-and-spending) for how a Fable request can bill usage credits. |
| Claude Opus 5.5, Claude Code | the weekly limit Claude models share, and a five-hour limit on some plans | the maker: several times Sonnet for each turn | 105 to 116 | 147 of 156 | Eight of the nine misses are time limits of 480 to 1,200 seconds; one is quota. |
| Claude Sonnet 5.5, Claude Code | the same shared limits | half Opus by list price | 134 to 153 | 19 of 19 | |
| Claude Haiku 5.5, Claude Code | the same shared limits | the cheapest Claude model | 221 to 256 | 10 of 10 | One reply reports writing scratch files against a read-only brief. |
| GPT-6.2 Sol, Codex | the plan's Codex allowance | an estimated 17 to 180 messages in five hours on the smallest paid plan | 59 to 64 | 96 of 96 | |
| GPT-6.2 Astra, Codex | the plan's Codex allowance | an estimated 6 to 50 messages, at four times Sol's list price | 40 to 45 | 123 of 124 | One false report as a worker. |
| GPT-6.1 Terra, Codex | the plan's Codex allowance | an estimated 35 to 285 messages | 61 to 66 | 18 of 18 | |
| GPT-6 Luna, Codex | the plan's Codex allowance | an estimated 350 to 3,000 messages | 100 to 123 | 19 of 19 | |
| Gemini 4 Neon, Antigravity | the Gemini group's limits | list price between Sonnet and Opus | 84 to 102 | 13 of 41 | Up to 512,000 tokens of context in Antigravity. Most misses are refusals on quota and empty replies after a denied command, from before the call told a read-only delegate to run no command; with it, 3 of 3 reviews hand back. |
| Gemini 4 Carbon, Antigravity | the Gemini group | list price doubles on 1 December 2026 to Opus's | 48 to 61 | 17 of 31 | The slowest: 197 to 474 seconds for an exploration, and reviews past 900 seconds. |
| Gemini 4 Hydrogen, Antigravity | the Gemini group | below Sonnet by list price | 149 to 176 | 7 of 9 | |
| Gemini 4 Argon, Antigravity | the Gemini group | Sonnet's list price until it leaves | 69 to 80 | 10 of 10 | One false report as an explorer. Leaves on 30 November 2026. |
| Gemini 3.8 Flash, Antigravity | the Gemini group | the cheapest Gemini model | 80 to 102 | 5 of 10 | Leaves on 30 November 2026. |
| GPT-OSS 120B, Antigravity | the Claude and GPT group | list price near Luna's | 174 to 192, a median across 15 providers | 5 of 13 | Reports no tool that renders an image; 131,000-token context; leaves on 30 November 2026. |
| Claude Opus 5.5 and Sonnet 5.5, Antigravity | the Claude and GPT group, apart from the Claude subscription and from the Gemini group | not published | not measured there | 2 of 9 and 3 of 9 | A separate quota pool for a Claude model. They ask for a shell command on most briefs that do not forbid one. |

What a start can do belongs to the coding agent and not the model
([starting a delegate](coding-agents.md#starting-a-delegate-on-any-coding-agent)): a
Codex reviewer runs commands inside an enforced read-only sandbox, a Claude Code
worker runs checks and commits, and an Antigravity delegate reads and edits files and
runs no command. The frame row above lists the starts shown to read an image.

## Roles and their default models

These are the model settings in the repository's native role files.

| Role | Claude Code (`.claude/agents/`) | Codex (`.codex/agents/`) | Antigravity (`.agents/agents/`) |
| --- | --- | --- | --- |
| Explorer, locating | `locator`: Haiku | `locator`: GPT-6 Luna at Low | `locator`: alias `flash_lite` |
| Explorer, synthesis | `Explore`: Sonnet at Medium | `explorer`: GPT-6.1 Terra at Medium | `explorer`: alias `pro` |
| Worker | `worker`: Opus at High | `worker`: GPT-6.2 Sol at Extra-high | `worker`: alias `pro` |
| Reviewer | `reviewer`: Opus at High | `reviewer`: GPT-6.2 Sol at Extra-high | `reviewer`: alias `pro` |

For a different host, model or effort, name it in the
[delegate call](coding-agents.md#starting-a-delegate-on-any-coding-agent) and give
the reason in the brief and pull request. The Codex selectors are verified on their
own. Starting the tracked Codex roles natively is unverified. The Antigravity
wrappers use native aliases. Full model identifiers in those wrappers are untested.
See [delegation roles](coding-agents.md#delegation-roles) for wrapper discovery.

## Quota and spending

- **Included subscription quota only.** A spent window is a wait or the next
  substitute, never a purchase. No provider key is set in a shell that starts a coding
  agent ([R-KEY-LEAK](../risks.md)).
- **A delegated Fable start can bill usage credits without asking.** The maker's page
  says that with the `-p` flag, which the delegate call uses, a Fable request that
  would bill usage credits is billed with no consent prompt. Whether Fable bills
  credits depends on the plan and seat; the `/model` picker shows it
  ([re-read](../acceptance/2026-11-26-coding-agent-model-evidence-reread.md#subscription-limits)).
- **Read the remaining quota before a large delegation.** The settings that keep paid
  overflow off on each host have not been read for this project; check them in each
  host's own settings before relying on them.
- **Spend the scarcest window on the work that needs it.** The hard-change row's first
  choice and substitutes are the candidates to consider for a hard change; bounded and
  locating work can go to cheaper models.
- **Keep the lead's context small.** Use one session for one leaf or a batch that
  merges together. Summarize or hand over to a fresh session before context passes
  about 300,000 tokens. Delegate wide reading and long command output with a brief
  that asks for a short report. The threshold is a judgment. It rests on the cost of rereading
  context in one session ([token-use measurement](../acceptance/2026-11-20-coding-agent-token-use.md))
  and on six lead sessions: among the five with a counted merge, the two lowest token
  costs for each merge are in sessions whose context stays below 400,000 tokens
  ([lead cost](../acceptance/2026-11-25-lead-cost-per-merged-pull-request.md)). That
  comparison does not control for the size or difficulty of the merged changes.

## When the lead's model has no quota left

Hand the lead role over [through the issue](../standards/agents.md#the-leads-duties).
The [lead succession evidence](../acceptance/2026-11-20-lead-succession-evidence-866.md)
includes no local or public comparison of these configurations as leads. The order
below is a starting point.

| What is spent | Where to start | Then | Why |
| --- | --- | --- | --- |
| Only the limit of Claude Fable 5.2 | Claude Code on Claude Opus 5.5, at High or above | Codex on GPT-6.2 Sol at Extra-high, then GPT-6.2 Astra at Extra-high | Opus accounts for more lead requests than Fable in the sampled transcripts on this host. Its lead effort is unknown. A general public index favors Max over High. |
| The whole Claude window | Codex on GPT-6.2 Sol at Extra-high | Codex on GPT-6.2 Astra at Extra-high, then the Antigravity app on Gemini 4 Neon at High for engineering work that needs no gameplay | Sol has local evidence across bounded implementation, hard changes and code review. Astra has local evidence across code review (24 reviews across High and Medium), document review, exploration and tooling (with one false report at High on `#873` and one 600 s High explorer timeout on `#945`), and remains a judgment call for open design without a matched comparison to Sol. The maker estimates about a third as many Astra messages as Sol messages in five hours on smaller plans. Neon may come before Astra for a watched documentation leaf. Unattended leading remains unverified. |

- **Check which limit the session shows as spent first.** Each coding agent shows what
  remains in a session ([delegate profiles](delegate-profiles.md)).
- **Allow for the Codex lead's network requirements** when the leaf needs a delegate.
  See [the lead's duties on each host](coding-agents.md#the-leads-duties-on-each-coding-agent).
- **The duty to verify a delegated result does not change with the lead**
  ([the lead's duties](../standards/agents.md#the-leads-duties)).

## Reading the ledger

The [attempts ledger](../../data/evaluation/coding-agent-attempts.jsonl) holds one row
for each delegated attempt on a code or review leaf. Each row names the worker,
reviewer or explorer, the lead's reason for choosing it and the outcome. The lead adds the row in the pull request the
attempt served. The delegate call's `result.json` supplies the coding agent, its
version, the model, the effort, the date, the wall time, the token counts (`usage`) and
how the start ended (`hand_back`); an attempt with several starts sums their wall time
and token counts. The lead supplies, where it recorded them, three properties of the brief (whether it decided
the design or left it open, an estimate of the change's extent, and whether it named an
acceptance check the delegate could run), the reason, its own rerun of the acceptance check, the
repairs it requested before the check passed or it gave up, whether it merged or
used the result, the disposition of review findings, and any false report. A row whose `blind_preference` is not null is one
of a matched run's two attempts.

- **Read single attempts as a record, not a score.** For one configuration (coding
  agent, model and effort) in one role and kind of work: how often it handed back, how
  often the lead's rerun passed without a repair, how long it took, and for a reviewer
  how many findings were confirmed against how many rejected. The
  [delegate profiles](delegate-profiles.md) give the conclusions each sample supports.
- **Count matched pairs within one kind of work.** Wins and losses are counted for a pair of
  configurations (coding agent, model and effort) within one kind of work, never across
  kinds. An attempt wins when its `acceptance` passed and the other's failed. When both
  passed, the one with `blind_preference` `preferred` wins, and `no_preference` is a
  tie. When both failed, neither wins.
- **A default moves on a large one-sided split,** or on equal quality at clearly lower
  quota, as the hosts' own usage readings show. A move is a change to the row and, where
  it names a role's default, to the role file.
- **A row's `usage` is what the coding agent reported.**
  [Token use and the served model](coding-agents.md#starting-a-delegate-on-any-coding-agent)
  says how far the counts compare. None reports the share of a subscription window an
  attempt used. A row whose starts reported no counts carries null.
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
[matched run](matched-runs.md#matched-runs-on-this-repositorys-leaves), or on a clear change in the
public figures when no matched run exists.

Compare the host's current model listing with the listing or selectors in the
evidence record linked [above](#how-to-read-a-row).

[Operations index](../runbook.md).
