---
owner: lead
review_trigger: A row is added to the attempts ledger for a configuration or role not described here, a coding agent's version or sandbox changes, or a limit below is found to have changed
status: active
---

# Delegate profiles

A lead reads this page before each delegation, to weigh the task against what each
coding agent and model has done in this repository
([choosing the delegate](../standards/agents.md#the-leads-duties)). It is a record, not
a ranking and not a rule: the observations are few and each is confounded by its task.
[Choosing a model](model-routing.md) keeps the public figures and advice by kind of
work; [coding-agent hosts](coding-agents.md#starting-a-delegate-on-any-coding-agent)
says how each delegate is started.

Every statement names its source: the attempts ledger
`data/evaluation/coding-agent-attempts.jsonl` (issue number and role), a dated record,
or the hosts page. Times are wall seconds from the brief to the hand-back. "Not
recorded" means nothing in this repository says.

## What to weigh

| Question about the task | What it points to |
| --- | --- |
| Does the brief pin the design, or leave some to the delegate? | A pinned, small change suits any worker below. Design left open has only the lead's model on record here. |
| How much code, and how risky? | The matched-run rows are the only code attempts compared here; both configurations passed. |
| Does it need the network, the whole test suite or a commit? | Inside its sandbox the Codex worker cannot run the whole suite or commit, and whether it reaches the network was not tried. The Antigravity worker runs no command at all. The Claude Code worker ran its checks and committed; its network use was not tried. |
| Must the reviewer be of a different model family than the author, and start clean? | Codex and Claude Code reviewers start clean, and only the Codex reviewer is held read-only by a sandbox. An Antigravity review is a second family's view only. |
| What quota is left? | Not readable through the delegate call on any of the three; a spent window comes back as `refused`. |
| What did the last attempts of this kind show? | The rows below, and the ledger itself for anything newer. |

## Codex

CLI 0.171.0. Models named to it: `gpt-6.2-sol`, `gpt-6.2-astra`, `gpt-6.1-terra`,
`gpt-6-luna`; efforts `low` to `xhigh`.

| | |
| --- | --- |
| Done well here | GPT-6.2 Sol at Extra-high, worker, bounded implementation (ledger, issue 834): passed the lead's rerun with no repair and was preferred blind for how its checks failed. Same configuration, standards prose (ledger, issue 811): passed with no repair. GPT-6.2 Astra at High, reviewer: gave the clean-context review of an Antigravity lead's documentation leaf and raised one finding, which the lead confirmed ([trial record](../acceptance/2026-11-19-antigravity-lead-trial-810.md), step 37). GPT-6.2 Sol at Extra-high, reviewer through the delegate call, a tool, its tests and its documents (ledger, issue 861): nine findings in 286 seconds, all nine confirmed against the tree, among them a stopped delegate's child left running and a read-only role that could write. |
| Done badly here | The same configuration's prose attempt was not preferred blind (ledger, issue 811). No false report is recorded. |
| Cannot do | As a worker it runs in a sandbox that denies loopback connections and process listing, so the whole test suite fails inside it, and it leaves its changes uncommitted; the delegate call's rerun and the lead's commit cover both ([hosts page](coding-agents.md#starting-a-delegate-on-any-coding-agent)). Whether the sandbox reaches the network was not tried through the call. It does not merge. Context size: not recorded. |
| How long | Sol at Extra-high: 635 seconds for the code leaf and 406 for the prose leaf (ledger); 502 more for one repair after review of the code leaf ([Choosing a model](model-routing.md#route-by-kind-of-work)). A one-word reply: 3 to 5 seconds ([evidence record](../acceptance/2026-11-19-coding-agent-model-evidence.md#measured-here)). |
| Remaining quota | Not recorded: how its remaining quota is read has not been read for this project. |

## Claude Code

Version 2.1.329. Models named to it: `claude-fable-5-2`, `claude-opus-5-5`,
`claude-sonnet-5-5`, `claude-haiku-5-5`; efforts `low` to `max`.

| | |
| --- | --- |
| Done well here | Claude Fable 5.2 at High, standards prose (ledger, issue 811): passed with no repair and was preferred blind. Claude Opus 5.5 at High, worker, bounded implementation (ledger, issue 834): passed with no repair. Same configuration through the delegate call, a pinned schema migration (ledger, issue 861): passed the rerun with no repair and committed through the hook. The host's own reviewer and synthesis explorer roles each ran as a sub-agent for pull requests #817 and #819 ([Choosing a model](model-routing.md#roles-and-their-default-models)). |
| Done badly here | Claude Opus 5.5 at High was not preferred blind on the code leaf (ledger, issue 834). As lead, its own requests were 72% to 74% of one session's token cost, about half of that re-reading its context ([token use](../acceptance/2026-11-20-coding-agent-token-use.md)). No false report is recorded. |
| Cannot do | No sandbox limit is recorded: a delegated worker ran the checks and committed. A delegated run loads the lead's user settings as well as the project's ([hosts page](coding-agents.md#starting-a-delegate-on-any-coding-agent)). It does not merge. Context size: no limit is recorded; one lead session's context reached 965,335 tokens and was summarized twice ([token use](../acceptance/2026-11-20-coding-agent-token-use.md)). |
| How long | Fable at High: 710 seconds for the prose leaf. Opus at High: 510 for the code leaf, 125 for the schema migration (ledger). A one-word reply: 3 seconds (20 November 2026, by hand). |
| Remaining quota | Not recorded: how its remaining quota is read has not been read for this project. |

## Antigravity

CLI 1.5.13. `agy models` lists what can be named; the call gives the model and the
effort separately, as in `gemini-4-neon` at `xhigh`.

| | |
| --- | --- |
| Done well here | Gemini 4 Neon at High as lead in the app carried one documentation leaf to a queued merge with the owner present ([trial record](../acceptance/2026-11-19-antigravity-lead-trial-810.md)). A print-mode review whose brief carried the diff returned twelve findings ([hosts page](coding-agents.md#starting-a-delegate-on-any-coding-agent)). Gemini 4 Neon at Extra-high, explorer through the delegate call (ledger, issue 861): read six named files by path and returned a cited summary; the four citations the lead checked held, and it found two statements on current pages that the records contradict. |
| Done badly here | The same lead session wrote that it had checked every quoted passage after reopening two of the files, and two claims in its final message went beyond its transcript ([trial record](../acceptance/2026-11-19-antigravity-lead-trial-810.md)). A print-mode review whose brief pointed at diff files ended with exit code 0 and no reply. No worker attempt on a real task is recorded. |
| Cannot do | In print mode it runs no shell command it was not granted, and a denied command ends the run with no reply and exit code 0, so a brief carries what the delegate needs and tells it to run nothing; a worker's check is run by the delegate call. Its exit code and status line are not evidence of what ran ([evidence record](../acceptance/2026-11-19-coding-agent-model-evidence.md#measured-here)). It keeps state between conversations, so its review is not the clean-context review. The brief travels as one command argument, within the shell's argument limit. The command-line tool is refused `gh pr merge` by a user-wide rule. Context size: not recorded. |
| How long | The lead session: 47 minutes for one documentation leaf, with eleven sandbox retries across the session; creating the pull request took 26 of those minutes ([trial record](../acceptance/2026-11-19-antigravity-lead-trial-810.md)). Neon at Extra-high: 598 seconds for the six-file exploration (ledger, issue 861). A one-word reply: 9 seconds (20 November 2026, by hand). |
| Remaining quota | Not recorded: how its remaining quota is read has not been read for this project. |

## Keeping this page current

The lead that adds a ledger row for a configuration, role or kind of work this page
does not yet describe adds the line here in the same pull request. A limit found to
have changed is corrected with its date. Nothing checks this page against the ledger.

[Operations index](../runbook.md).
