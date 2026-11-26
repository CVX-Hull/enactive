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
| Locating files and mechanical sweeps | the smallest model the host serves | none needed | a large model | Cost only; no figure read |
| Shell, checks and Python tooling | one of the six models whose terminal scores overlap, at the effort read | whichever of them has quota | Claude Haiku 5.5; GPT-6 Luna; Gemini 3.8 Flash | Terminal task scores, six configurations. Two unmatched local worker passes (GPT-6.2 Sol at Extra-high on `#905`, GPT-6.2 Astra at Medium on `#914`). |
| Reading run ledgers, logs and tables | the synthesis explorer | none known | none known | The choice is judgment; no public evidence found. In a local [study](../acceptance/2026-11-26-run-evidence-diagnosis.md) of eight incidents already diagnosed here, no explorer configuration states a wrong cause; Claude Opus 5.5 and Gemini 4 Carbon state the recorded cause on all eight and the GPT-6.2 configurations on six. On the same incidents [across tiers](../acceptance/2026-11-26-diagnosis-and-frame-reading-across-model-tiers.md), Claude Fable 5.2 and Gemini 4 Argon state eight, Claude Sonnet 5.5 at Medium seven, and smaller models fewer; the lead judges one of 86 answers wrong. One local review observation (GPT-6.2 Astra at High on `#896`, 2 confirmed findings). |
| Reading retained game frames | a reviewer start the [delegate profiles](delegate-profiles.md#what-to-weigh) list as reading frames | another of those starts with quota | a start the profiles do not list | Local probes on nineteen configurations, cited in the profiles; seventeen answer all eight questions correctly |
| Standards and pull-request prose | the lead | GPT-6.2 Sol at Extra-high | none known | Judgment; one local matched run (`#811`) favored Fable over Sol. No public comparison for this work is recorded. |
| Acceptance and design records | the lead | none known | none known | Judgment; no public evidence found. Four unmatched local worker passes (Claude Opus 5.5 at High on `#925`). |
| Research on outside systems | a large model that fetches the page it cites | Gemini 4 Carbon or Argon where a wrong answer costs more than no answer | answering from memory | The first choice is judgment; wrong-answer rates were read for those two models only |
| Review of code | the host's reviewer role, clean context | another family's reviewer when the window is spent | acting on a quoted passage before checking it against the tree | The choice is judgment; reviewer products built on two Claude models were read, with no effort reported. In a local [replay](../acceptance/2026-11-25-reviewer-recall-replay.md) of five past code commits holding six later-fixed defects, each GPT-6.2 reviewer finds 3, and Claude Opus 5.5 finds 1 through the tracked plan-mode start and 3 when started without plan mode, each run once. The set is small and does not rank the models. |
| Review of documents | If the [review workflow](../workflows/review.md) selects a review, use the host's clean-context reviewer or a second family's clean-context reviewer with quota. | none known | none known | Judgment, with weak support from one preprint read second-hand. In a local [replay](../acceptance/2026-11-25-reviewer-recall-replay.md) of four past document commits holding ten later-fixed defects, GPT-6.2 reviewers find 4 to 7 and Claude Opus 5.5 reviewers 1 to 3, each run once; a GPT-6.2 reviewer finds defects that no Claude Opus 5.5 reviewer finds. Every one of the four commits has a Claude co-author, so this does not rank the models. |

Only two local matched comparisons exist (`#811` prose and `#834` bounded code), so no
row meets the [threshold for changing a default](#reading-the-ledger).

## Tiers by kind of work

A tier groups the configurations the evidence does not separate for that work. The
first choice in the table above is one member of the top tier. Inside a tier, choose
by [what each configuration costs](#what-each-configuration-costs-and-can-do): the
quota left, the wall time and what the start can do. Effort is the one read; where
none is given the model was read at one effort only.

Each tier says what it rests on. "Local" is a result on this repository, in the
[delegate profiles](delegate-profiles.md) or a dated record. "Public" is a figure in
the [re-read of 26 November 2026](../acceptance/2026-11-26-coding-agent-model-evidence-reread.md),
on tasks that are not this repository's; a local result replaces it when a leaf of
[the model-tier outcome](https://github.com/CVX-Hull/enactive/issues/987) lands.
Gemini 4 Argon, Gemini 3.8 Flash and GPT-OSS 120B leave Antigravity on 30 November
2026 and are listed for the days that remain.

| Work | Top tier | Middle tier | Low tier | Do not use | What the tiers rest on |
| --- | --- | --- | --- | --- | --- |
| Leading a leaf | Claude Fable 5.2 at High | Claude Opus 5.5 at High or above; GPT-6.2 Sol at Extra-high; GPT-6.2 Astra at Extra-high; Gemini 4 Neon at High in the app, watched | Claude Sonnet 5.5; Gemini 4 Carbon | the small models: Claude Haiku 5.5, GPT-6 Luna, GPT-6.1 Terra, Gemini 4 Hydrogen | Judgment and the [succession order](#when-the-leads-model-has-no-quota-left). No local or public comparison of leads exists; the low tier is public index only. |
| Hard change that must merge | Claude Fable 5.2 at High or Extra-high; Claude Opus 5.5; Gemini 4 Neon at Extra-high; Claude Sonnet 5.5; Gemini 4 Carbon at High | GPT-6.2 Astra at High or above; Gemini 4 Hydrogen; Claude Fable 5.2 at Medium; GPT-6.2 Sol at High or Extra-high; GPT-6.1 Terra | Gemini 4 Argon; GPT-6.2 Sol at Medium | Claude Haiku 5.5; GPT-6 Luna; Fable at Max; any Low effort | Public index: 55.5 to 58.6 for the top tier, 47.5 to 53.5 for the middle, 45.4 and 45.5 below, 29.6 and 25.9 for the two excluded. Claude Opus 5.5, Sonnet 5.5 and Terra were read at Max only. Local: GPT-6.2 Sol workers handed back all 43 attempts, 9 of them hard changes, which the public index does not rank first. |
| Bounded implementation from a written brief | GPT-6.2 Sol at Extra-high or High; Claude Opus 5.5 at High | GPT-6.2 Astra; Claude Sonnet 5.5; Gemini 4 Neon; Gemini 4 Carbon; GPT-6.1 Terra; Gemini 4 Hydrogen | Gemini 4 Argon | Claude Haiku 5.5; GPT-6 Luna; Gemini 3.8 Flash; GPT-OSS 120B | Top tier is local: 43 of 43 and 25 of 31 worker attempts handed back, and one matched run favored Sol. Astra has 3 local attempts and one false report. The rest of the middle tier is public index and terminal scores with no local worker attempt; a Gemini worker edits files and runs no command, so the lead runs its check. |
| Exploration that needs synthesis, and reading run evidence | Claude Opus 5.5 at High or Medium; Claude Fable 5.2 at High; Gemini 4 Carbon at High; Gemini 4 Argon at High | Claude Sonnet 5.5 at Medium or High; Gemini 4 Neon at High or Extra-high; GPT-6.2 Sol; GPT-6.2 Astra at High or Medium; GPT-6 Luna at High | GPT-6.1 Terra; Claude Haiku 5.5; Gemini 4 Hydrogen | GPT-6 Luna at Low; Gemini 3.8 Flash; GPT-OSS 120B; a Claude model through Antigravity | Local: recorded causes stated on eight incidents, 8 for the top tier, 6 or 7 for the middle, 4 or 5 below with the one wrong cause from Haiku, 1 for Luna at Low ([first study](../acceptance/2026-11-26-run-evidence-diagnosis.md), [across tiers](../acceptance/2026-11-26-diagnosis-and-frame-reading-across-model-tiers.md)). Public codebase questions agree on the ends and put Neon first at 67.7 and Sol lower at 42.5 to 51.3. |
| Locating files and mechanical sweeps | Claude Haiku 5.5; GPT-6 Luna at Low; GPT-6.1 Terra at Medium; Claude Sonnet 5.5 at Medium | any larger model, at more quota | none | GPT-OSS 120B | Cost and speed only: the public output speed is 221 to 256 tokens a second for Haiku and 100 to 123 for Luna, against 40 to 66 for the GPT-6.2 models. No accuracy figure exists, locally or publicly; [the locator leaf](https://github.com/CVX-Hull/enactive/issues/990) measures it. |
| Shell, checks and Python tooling | Claude Opus 5.5; Claude Fable 5.2; Gemini 4 Carbon; Claude Sonnet 5.5; GPT-6.2 Astra; GPT-6.2 Sol; Gemini 4 Neon | Gemini 4 Hydrogen; Gemini 4 Argon; GPT-6.1 Terra | Claude Haiku 5.5 | Gemini 3.8 Flash; GPT-6 Luna | Public terminal tasks: 61.2% to 65.8% with intervals near 3 points for the top tier, 53.3% to 56.4% for the middle, 40.0% for Haiku, 18.2% and 15.2% for the excluded. An Antigravity delegate runs no command, so a Gemini model does this work only as an app lead. |
| Reading retained game frames | any configuration that answers the frame probe, chosen for speed: Claude Sonnet 5.5 at Medium, GPT-6.1 Terra, GPT-6 Luna at Low, Claude Haiku 5.5, Gemini 4 Hydrogen | the larger models, slower for the same answers | none | GPT-OSS 120B | Local: 17 of 19 configurations answer all eight questions; the fastest take 9 to 19 seconds. |
| Standards, pull-request prose, acceptance and design records | the lead | GPT-6.2 Sol at Extra-high; Claude Opus 5.5 at High | not separated | none known | Judgment, one local matched run that favored Fable over Sol on prose, and four local Opus worker passes on records. No public evidence for this work. |
| Research on outside systems | Gemini 4 Carbon; Gemini 4 Neon; Gemini 4 Hydrogen; Gemini 4 Argon | GPT-6.1 Terra; Claude Haiku 5.5; Claude Sonnet 5.5 | Claude Opus 5.5; GPT-6.2 Sol; GPT-6.2 Astra; Claude Fable 5.2 | GPT-6 Luna, answering from memory | Public closed-book recall: of the answers a model does not get right, the share that are wrong guesses is 4% to 14% for the Gemini 4 models, 34% to 43% for the middle tier, 50% to 59% for the low tier and 79% for Luna. Fable has the highest accuracy, 79%, and guesses when it does not know. A model that fetches the page it cites is not measured by this. |
| Review of code | GPT-6.2 Sol at Extra-high; GPT-6.2 Astra at High | GPT-6.2 Astra at Medium; Claude Opus 5.5 at High; Gemini 4 Carbon at High, which hands back 9 of 23 starts | not measured: Claude Fable 5.2, Claude Sonnet 5.5, GPT-6.1 Terra, Gemini 4 Hydrogen | Gemini 4 Neon through the delegate call, which hands back 2 of 28 starts; Claude Haiku 5.5; GPT-6 Luna | Local [replay](../acceptance/2026-11-25-reviewer-recall-replay.md): 16 known defects, found by both judges 10 and 8 for the top tier and 7, 4 to 6 and 3 of 14 for the middle. Public: inside other makers' reviewers, Opus recalls 55% to 61% of high-severity issues and Sonnet 44% to 48%, at 93% to 96% precision; no public row for the others. [The review leaf](https://github.com/CVX-Hull/enactive/issues/991) measures the unmeasured. |
| Review of documents | GPT-6.2 Sol at Extra-high; GPT-6.2 Astra at High or Medium | Claude Opus 5.5 at High or Medium | not measured: the same four as for code | the same as for code | Local replay: of ten known defects in four document commits, 4 to 7 for the top tier and 1 to 3 for Opus. Every one of those commits has a Claude co-author, so part of the gap may be a second family and not the model. |
| Judging answers against written criteria | GPT-6.2 Sol at Extra-high; GPT-6.2 Astra at High; Claude Opus 5.5 at High; the lead on Claude Fable 5.2 | not separated | not measured: every other configuration | a judge from the family that wrote the answers, alone | Local: Sol and Opus agree on 106 of 114 verdicts in the reviewer replay, and Astra agrees with the lead on 56 of 56 and 84 of 88 in the two diagnosis studies. Public: one vendor post gives Opus 94.7% on one judging benchmark; nothing for the others. [The judge leaf](https://github.com/CVX-Hull/enactive/issues/993) measures the small models. |

## What each configuration costs and can do

Speed is the public output speed on the maker's own service, in tokens a second across
efforts; time to a first answer grows steeply with effort. Local hand-backs are counts
from the [attempts ledger](../../data/evaluation/coding-agent-attempts.jsonl) through
the delegate call, all roles together. List price is a signal of relative quota cost
only; no page gives the share of a subscription window a model uses.

| Configuration | Limit it draws on | Relative cost | Speed | Local hand-backs | Notes |
| --- | --- | --- | --- | --- | --- |
| Claude Fable 5.2, Claude Code | a separate weekly Fable limit, and the session and weekly limits all Claude models share | list price twice Opus | 109 to 113 | 10 of 12 | With the `-p` flag, which the delegate call uses, a Fable request that would bill usage credits is billed without asking. Start Fable as a delegate only with extra usage turned off. |
| Claude Opus 5.5, Claude Code | the shared session and weekly limits | the maker: several times Sonnet for each turn | 105 to 116 | 144 of 153 | Six of the nine misses are 600-second time limits. |
| Claude Sonnet 5.5, Claude Code | shared | half Opus by list price | 134 to 153 | 19 of 19 | |
| Claude Haiku 5.5, Claude Code | shared | the cheapest Claude model | 221 to 256 | 10 of 10 | One reply reports writing scratch files against a read-only brief. |
| GPT-6.2 Sol, Codex | the plan's Codex allowance | 17 to 180 messages in five hours on the smallest paid plan | 59 to 64 | 95 of 95 | |
| GPT-6.2 Astra, Codex | the same allowance | 6 to 50 messages: about a third of Sol's, at four times its list price | 40 to 45 | 122 of 123 | One false report as a worker. |
| GPT-6.1 Terra, Codex | the same allowance | 35 to 285 messages | 61 to 66 | 18 of 18 | |
| GPT-6 Luna, Codex | the same allowance | 350 to 3,000 messages | 100 to 123 | 19 of 19 | |
| Gemini 4 Neon, Antigravity | the Gemini group's five-hour and weekly limits | list price between Sonnet and Opus | 84 to 102 | 12 of 40 | 512,000-token context in Antigravity. Most misses are empty replies after a denied command, and refusals on quota. |
| Gemini 4 Carbon, Antigravity | the Gemini group | list price doubles on 1 December 2026 to Opus's | 48 to 61 | 17 of 31 | The slowest: 197 to 474 seconds for an exploration, and reviews past 900 seconds. |
| Gemini 4 Hydrogen, Antigravity | the Gemini group | below Sonnet by list price | 149 to 176 | 7 of 9 | |
| Gemini 4 Argon, Antigravity | the Gemini group | Sonnet's list price until it leaves | 69 to 80 | 9 of 9 | Leaves on 30 November 2026. |
| Gemini 3.8 Flash, Antigravity | the Gemini group | the cheapest Gemini model | 80 to 102 | 5 of 10 | Leaves on 30 November 2026. |
| GPT-OSS 120B, Antigravity | the Claude and GPT group | the cheapest listed | 174 to 192 | 5 of 13 | Reads no image; 131,000-token context; leaves on 30 November 2026. |
| Claude Opus 5.5 and Sonnet 5.5, Antigravity | the Claude and GPT group, apart from the Claude subscription and from the Gemini group | not published | not measured there | 2 of 9 and 3 of 9 | A third quota pool for a Claude model when the Claude window is spent. They ask for a shell command on most briefs that do not forbid one. |

What a start can do belongs to the coding agent and not the model
([starting a delegate](coding-agents.md#starting-a-delegate-on-any-coding-agent)): a
Codex reviewer runs commands inside an enforced read-only sandbox, a Claude Code
worker runs checks and commits, and an Antigravity delegate reads and edits files and
runs no command. Every start reads an image except on GPT-OSS 120B.

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
