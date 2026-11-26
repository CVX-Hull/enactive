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
| Reading run ledgers, logs and tables | the synthesis explorer | none known | none known | Judgment; no public evidence found. One local review observation (GPT-6.2 Astra at High on `#896`, 2 confirmed findings). |
| Reading retained game frames | a reviewer start the [delegate profiles](delegate-profiles.md#what-to-weigh) list as reading frames | another of those starts with quota | a start the profiles do not list | One local probe, cited in the profiles |
| Standards and pull-request prose | the lead | GPT-6.2 Sol at Extra-high | none known | Judgment; one local matched run (`#811`) favored Fable over Sol. No public comparison for this work is recorded. |
| Acceptance and design records | the lead | none known | none known | Judgment; no public evidence found. Four unmatched local worker passes (Claude Opus 5.5 at High on `#925`). |
| Research on outside systems | a large model that fetches the page it cites | Gemini 4 Carbon or Argon where a wrong answer costs more than no answer | answering from memory | The first choice is judgment; wrong-answer rates were read for those two models only |
| Review of code | the host's reviewer role, clean context | another family's reviewer when the window is spent | acting on a quoted passage before checking it against the tree | The choice is judgment; reviewer products built on two Claude models were read, with no effort reported |
| Review of documents | If the [review workflow](../workflows/review.md) selects a review, use the host's clean-context reviewer or a second family's clean-context reviewer with quota. | none known | none known | Judgment, with weak support from one preprint read second-hand. |

Only two local matched comparisons exist (`#811` prose and `#834` bounded code), so no
row meets the [threshold for changing a default](#reading-the-ledger).

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
