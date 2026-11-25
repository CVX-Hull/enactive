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
| How reliable is the hand-back? | The ledger records one false report (`#873`, 2026-11-21, Codex `gpt-6.2-astra` at High, worker: claimed an unbriefed status edit was briefed; the lead reverted it). Only the Antigravity app has a lead session audited against its transcript. |

## Codex

Recorded selectors include `gpt-6.2-sol`, `gpt-6.2-astra`, `gpt-6.1-terra` and
`gpt-6-luna`. Efforts range from `low` to `xhigh`. The
[selector measurements](../acceptance/2026-11-19-coding-agent-model-evidence.md#measured-here)
cover these four selectors and leave the full model list unknown.

| Role and configuration | What the evidence supports |
| --- | --- |
| Worker, GPT-6.2 Sol at Extra-high | 28 attempts across bounded implementation (16), prose (9), hard changes (2) and tooling (1). All 28 handed back: 25 passed acceptance (17 without repair, 11 repairs total), 2 failed, 26 merged and 2 discarded. Matched runs favor Sol on code (`#834`) and Fable on prose (`#811`). |
| Worker, GPT-6.2 Sol at High | 11 attempts across hard changes (7, including `#918`, `#921`, `#922`, `#937`) and bounded implementation (4, including `#949` with 0 repairs and `#950` with 2 repairs). All 11 handed back: 10 passed (4 without repair, 7 repairs total), 10 merged and 1 discarded (`#919`). |
| Worker, GPT-6.2 Astra at Extra-high, High and Medium | 3 attempts (1 Extra-high prose, 1 High prose, 1 Medium Python tooling on `#914`). All 3 handed back and passed without repair; Extra-high dropped two citations the lead restored, and High recorded one false report (`#873`, unbriefed edit reverted by the lead). |
| Reviewer, GPT-6.2 Sol at Extra-high | 8 reviews (5 code, 3 document). All 8 handed back, yielding 47 confirmed and 0 rejected findings. |
| Reviewer, GPT-6.2 Astra at High | 38 reviews across documents (23), code (14, including 11 on `#936`/`#937` plus `#913`, `#920`, `#923`) and run ledgers (1, `#896`). All 38 handed back, yielding 225 confirmed and 4 rejected findings (71 confirmed, 0 rejected on code reviews). |
| Reviewer, GPT-6.2 Astra at Medium | 27 reviews (19 document, 8 code). All 27 handed back, yielding 119 confirmed and 1 rejected findings. |
| Explorer, GPT-6.2 Sol at Extra-high | 3 synthesis explorations; all 3 handed back and used. |
| Explorer, GPT-6.2 Astra at High and Medium | 2 High synthesis explorations (1 handed back on `#873`; 1 timed out at 600 s on a 10-file audit for `#945`) and 2 Medium split explorations on `#945` (both handed back and used in 94–181 s). |
| Lead | The owner's account of 19 November 2026 in the [decision log](../decisions/owner-decisions.md) establishes prior use. The model, effort, work and verification are unknown. |

Read remaining quota with `/status` or on the account's usage page.

## Claude Code

Recorded models include `claude-fable-5-2`, `claude-opus-5-5`, `claude-sonnet-5-5`
and `claude-haiku-5-5`. Efforts range from `low` to `max`.

| Role and configuration | What the evidence supports |
| --- | --- |
| Worker, Claude Fable 5.2 at High | 3 attempts: 1 matched prose leaf (`#811`) passed without repair and was preferred blind; 1 hard change (`#838`) failed acceptance and was finished by the lead; 1 prose attempt (`#903`) failed immediately on weekly Fable quota and was discarded. |
| Worker, Claude Opus 5.5 at High | 29 attempts across bounded implementation (16), hard changes (6), acceptance/design records (4) and prose (3): 23 handed back and passed (10 without repair, 14 repairs total), 5 timed out on `#937` after editing files (lead verified and merged), and 1 returned `unavailable` on weekly quota (`#950`, discarded). Matched code run `#834` favored Sol. |
| Worker, Claude Opus 5.5 at Medium | 1 prose attempt (`#906`); handed back and passed after 1 repair. |
| Reviewer, Claude Opus 5.5 at High | 44 reviews (24 document, 20 code): 41 handed back with 264 confirmed and 5 rejected findings; 3 code reviews on `#937` timed out at 600 s. |
| Reviewer, Claude Opus 5.5 at Medium | 10 reviews (8 code, 2 document); all 10 handed back with 40 confirmed and 1 rejected findings. |
| Reviewer, Claude Sonnet 5.5 at High | 1 code review (`#873`); handed back with 4 confirmed and 0 rejected findings. |
| Explorer, Claude Opus 5.5 at High | 3 synthesis explorations; all 3 handed back and used. |
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
| Explorer, Gemini 4 Neon at Extra-high | 4 synthesis explorations (`#861`, `#873`); all 4 handed back and used. Verification covers a sample of the citations. |
| Reviewer, Gemini 4 Carbon at High | The delegate call supports a bias check on a brief and its scoring sheet, with findings the lead confirmed. For review requiring clean context, use the [host guidance](coding-agents.md#delegation-roles). |
| Reviewer, print mode | A reviewer can use a diff supplied in the brief (no retained review report). |
| App lead, Gemini 4 Neon at High | The [watched documentation leaf](../acceptance/2026-11-19-antigravity-lead-trial-810.md) supports leading as far as a queued merge with the owner present. Verification was partial, the report overstated what was checked, and another lead completed the merge. There is no comparable evidence for source work. |

Quota is per model. The CLI changelog places `/usage`, `/quota` and `/credits` in an
interactive session. They return exit code 2 in print mode.

## Keeping this page current

Add attempts to the ledger. Change this page in the same pull request only when the
evidence changes a conclusion about a configuration, role, kind of work or limit.

[Operations index](../runbook.md).
