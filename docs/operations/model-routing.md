---
owner: lead
review_trigger: A served model is added, retired or repriced, a quota changes, a coding agent's version changes, a default effort changes, or a row is observed in this repository
status: active
---

# Choosing a model for engineering work

A lead on any [coding-agent host](coding-agents.md) reads this page to choose the model
for a piece of engineering work. The choice is by kind of work, not by model family and
not by role. It concerns the lead's own delegation only: the playing actor's, curator's
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
- **A public score is a coding agent and a model together**, each model in its maker's
  own agent, on tasks that are not this repository's. A gap of a few points is a tie.
- **Effort matters as much as the model.** On the one model read at every setting, the
  score moved ten points between Low and High, and the highest setting scored lower at
  several times the cost: start at High.

No row has been observed in this repository yet. A row changes on our own evidence
through [the same leaf run on two coding agents](https://github.com/CVX-Hull/enactive/issues/813),
not on a public board alone.

## Route by kind of work

Every choice here is provisional. A cell names an effort only where a figure was read at
that effort; "not read" marks a setting chosen by judgment. Which changes get a review,
and how many, is owned by [review](../workflows/review.md); this page only says which
model to give it.

| Kind of work here | First choice | Substitutes, in order | Avoid | What it rests on |
| --- | --- | --- | --- | --- |
| Hard change across harness, protocol and bridge that must merge | Claude Fable 5.2 at High | Claude Fable 5.2 at Extra-high; Claude Opus 5.5 at Max; Gemini 4 Neon at Extra-high; GPT-6.2 Astra at Extra-high | Fable at Max; Haiku, Luna and Argon | Index 58 at High and at Extra-high; the patch score of 49 was read at Extra-high only |
| Bounded implementation from a written brief | GPT-6.2 Sol at Extra-high | GPT-6.2 Astra at Extra-high; Claude Opus 5.5 at High (not read) | Claude Sonnet 5.5 at Max as the first choice | Sol's index of 50 at 12.6 minutes, the least time read; no figure isolates work from a brief |
| Exploration that needs synthesis across files | Gemini 4 Neon at Extra-high | Claude Opus 5.5 at Max; Claude Sonnet 5.5 at Max; Gemini 4 Carbon at High; Claude Sonnet 5.5 at Medium (not read) as a sub-agent | Claude Haiku 5.5; GPT-6 Luna | Codebase question scores of 64 to 68 against 34 and 38 |
| Locating files and mechanical sweeps | the smallest model the host serves | none needed | a large model | Cost only; no figure read |
| Shell, checks and Python tooling | one of the six models whose terminal scores overlap, at the effort read | whichever of them has quota | Claude Haiku 5.5; GPT-6 Luna; Gemini 3.8 Flash | Terminal task scores, six configurations |
| Reading run ledgers, logs and tables | the synthesis explorer | none known | none known | Judgment; no public evidence found |
| Standards and pull-request prose | the lead | none known | none known | Judgment; no public evidence found |
| Acceptance and design records | the lead | none known | none known | Judgment; no public evidence found |
| Research on outside systems | a large model that fetches the page it cites | Gemini 4 Carbon or Argon where a wrong answer costs more than no answer | answering from memory | Wrong-answer rates read for those two models only |
| Review of code | the host's reviewer role, clean context | another family's reviewer when the window is spent | acting on a quoted passage before checking it against the tree | Reviewer products on one model, with no effort reported |
| Review of documents | the host's reviewer role, or a second family's where one has quota | none known | none known | One preprint, read second-hand; weak |

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

These are defaults, not eligibility rules. The lead overrides the model for one task
when the table above says so, and states the coding agent, model and effort it used in
the pull request.

- **Claude Code** reads the project's `.claude/agents/` ahead of a user's own
  definitions of the same name. The lead names another model for one task with the
  delegation call's model override. The `reviewer` and `Explore` files have each run
  once as a sub-agent; `locator` and `worker` have not.
- **Codex** reads `.codex/agents/` in a checkout the user trusts. All four model
  selectors answered a one-word prompt on CLI 0.171.0, twice; the role files themselves
  were not exercised as sub-agents.
- **Antigravity** role files use its native aliases; a full model identifier in a
  role file was not tested. `agy agents` (CLI 1.5.13) listed all four files from the
  main checkout, and none from a worktree of it or from a scratch copy; no other place
  was tried. They have not run as sub-agents: the one Antigravity lead session so far
  started its explorer as the host's `research` type and defined its own `worker` type
  ([trial record](../acceptance/2026-11-19-antigravity-lead-trial-810.md)).

## Quota and spending

- **Included subscription quota only.** A spent window is a wait or the next
  substitute, never a purchase. No provider key is set in a shell that starts a coding
  agent ([R-KEY-LEAK](../risks.md)).
- **Read the remaining quota before a large delegation.** The settings that keep paid
  overflow off on each host have not been read for this project; check them in each
  host's own settings before relying on them.
- **Spend scarce windows where they lead.** The lead's own model does the hard changes;
  bounded and locating work goes to cheaper models.

## Keeping this page current

There is no calendar pass. A row is re-read when one of these happens:

- a model is added, retired or repriced on a host;
- a quota or plan changes;
- a coding agent's version changes;
- a default effort changes;
- a row is observed here for the first time.

On a trigger the lead re-reads the affected sources, adds a new dated record, and marks
rows whose model was replaced as inherited. A default in a role file moves on our own
paired observation, or on a clear change in the public figures when no observation
exists.

The models each host served on 19 November 2026 are listed in the
[evidence record](../acceptance/2026-11-19-coding-agent-model-evidence.md#measured-here);
a trigger compares the host's current listing with it.

[Operations index](../runbook.md).
