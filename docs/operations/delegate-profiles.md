---
owner: lead
review_trigger: A row is added to the attempts ledger for a configuration, role or kind of work not described here, a coding agent's version or sandbox changes, or a limit below is found to have changed
status: active
---

# Delegate profiles

Before each delegation, the lead weighs the task against what each configuration
has shown here. The [attempts ledger](../../data/evaluation/coding-agent-attempts.jsonl)
holds individual outcomes, elapsed times, repairs and findings. Each sample is small
and depends on the task. [S-AGENT](../standards/agents.md#the-leads-duties) owns the
choice, and [model routing](model-routing.md#route-by-kind-of-work) gives advice by
kind of work.

## What to weigh

| Question about the task | What the lead can rely on |
| --- | --- |
| How much design or risk does the worker take on? | The only matched comparisons cover one bounded code leaf and one prose leaf. No delegated worker has a recorded result on a brief with open design. |
| Does the task need network access, the whole suite, a commit or an enforced read-only review? | Network access by a Codex or Claude Code worker is unverified through the call. For a worker that can run checks and commit, see the Claude Code [worker start](coding-agents.md#starting-a-delegate-on-any-coding-agent). The same table identifies the reviewer with enforced read-only access. |
| What quota and context are available? | Read quota in the host's session. The delegate call exposes no remaining balance. The profiles below use the [subscription evidence](../acceptance/2026-11-20-lead-succession-evidence-866.md), which does not identify the owner's plans. No context-size limit is recorded for these configurations. |
| How reliable is the hand-back? | The ledger has no recorded false report by a delegate. Only the Antigravity app has a lead session audited against its transcript. |

## Codex

Recorded selectors include `gpt-6.2-sol`, `gpt-6.2-astra`, `gpt-6.1-terra` and
`gpt-6-luna`. Efforts range from `low` to `xhigh`. The
[selector measurements](../acceptance/2026-11-19-coding-agent-model-evidence.md#measured-here)
cover these four selectors and leave the full model list unknown.

| Role and configuration | What the evidence supports |
| --- | --- |
| Worker, GPT-6.2 Sol at Extra-high | The bounded code change passed the lead's checks without repair and needed one repair after review, which the ledger's repair count does not hold. Of three documentation attempts, two passed without repair and one broke a link from another page and was finished by the lead. Blind review favors Sol on code and Fable on prose. |
| Worker, GPT-6.2 Astra at Extra-high | One documentation cut that needed judgment about which limits to keep passed without repair; the lead restored two decision citations it dropped. |
| Reviewer, GPT-6.2 Sol at Extra-high | Confirmed code-review findings cover a tool and its tests and documentation. The sample is one change. |
| Explorer, GPT-6.2 Sol at Extra-high | One exploration supports synthesis across named records. Verification covers a sample of the returned statements. |
| Reviewer, GPT-6.2 Astra at High | Repeated document reviews yield confirmed findings on factual accuracy and missing conditions. The sample includes a bias check on a brief and excludes code review. |
| Lead | The owner's account of 19 November 2026 in the [decision log](../decisions/owner-decisions.md) establishes prior use. The model, effort, work and verification are unknown. |

Read remaining quota with `/status` or on the account's usage page.

## Claude Code

Recorded models include `claude-fable-5-2`, `claude-opus-5-5`, `claude-sonnet-5-5`
and `claude-haiku-5-5`. Efforts range from `low` to `max`.

| Role and configuration | What the evidence supports |
| --- | --- |
| Worker, Claude Fable 5.2 at High | The evidence for standards prose is one leaf that passes without repair and is preferred blind. |
| Worker, Claude Opus 5.5 at High | Checks pass without repair on two bounded tasks, including a pinned schema migration with a commit through the hook. Only one has a blind comparison, which favors Sol. |
| Reviewer, Claude Opus 5.5 at High | The delegate call supports document review with confirmed findings. Its sample covers decision-log changes. |
| Native roles | The [session measurement](../acceptance/2026-11-20-coding-agent-token-use.md) shows use of the host's locator, synthesis explorer, worker and reviewer. It measures token use, leaving their relative quality unknown. |
| Lead, Claude Opus 5.5 and Claude Fable 5.2 | The sample covers two lead transcripts. Lead effort is unrecorded. The cost of rereading a large context is measured for one Fable session. |

Read remaining quota with `/usage`. The maker describes a separate weekly Fable limit
on larger plans, but its help pages differ on which limits are shared.

## Antigravity

Use `agy models` for the available models. The delegate call takes model and effort
separately, as in `gemini-4-neon` at `xhigh`.

| Role and configuration | What the evidence supports |
| --- | --- |
| Worker | No real worker task is recorded through the delegate call. A print-mode worker can edit and reply when asked to run no command (observed by hand, no retained record). The app's own worker edited two files on one watched documentation leaf using the lead's model. |
| Explorer, Gemini 4 Neon at Extra-high | One exploration supports cited synthesis from files named in the brief. Verification covers a sample of the citations. |
| Reviewer, Gemini 4 Carbon at High | The delegate call supports a bias check on a brief and its scoring sheet, with findings the lead confirmed. For review requiring clean context, use the [host guidance](coding-agents.md#delegation-roles). |
| Reviewer, print mode | A reviewer can use a diff supplied in the brief (no retained review report). |
| App lead, Gemini 4 Neon at High | The [watched documentation leaf](../acceptance/2026-11-19-antigravity-lead-trial-810.md) supports leading as far as a queued merge with the owner present. Verification was partial, the report overstated what was checked, and another lead completed the merge. There is no comparable evidence for source work. |

Quota is per model. The CLI changelog places `/usage`, `/quota` and `/credits` in an
interactive session. They return exit code 2 in print mode.

## Keeping this page current

Add attempts to the ledger. Change this page in the same pull request only when the
evidence changes a conclusion about a configuration, role, kind of work or limit.

[Operations index](../runbook.md).
