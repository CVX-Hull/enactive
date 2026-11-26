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
| Does the task need a game frame read? | The reviewer starts on Claude Opus 5.5, GPT-6.2 Sol, GPT-6.2 Astra and Gemini 4 Carbon ([probes](../acceptance/2026-11-25-delegate-start-probes.md#frame-reading)) and on Gemini 4 Neon ([later start](../acceptance/2026-11-26-run-evidence-diagnosis.md#frame-reading-on-gemini-4-neon)) read text and a highlighted button from a retained frame correctly. So does every smaller model started on the same frames, in 9 to 52 seconds: Claude Fable 5.2, Sonnet 5.5 and Haiku 5.5, GPT-6.1 Terra, GPT-6 Luna at High and Low, and Gemini 4 Hydrogen, Gemini 4 Argon and Gemini 3.8 Flash. GPT-OSS 120B reports no tool that renders an image, and Claude Opus 5.5 through Antigravity returns no answers ([across tiers](../acceptance/2026-11-26-diagnosis-and-frame-reading-across-model-tiers.md#frame-reading)). Comparing two frames and reading a map are untested for a reviewer start. |
| Does the task only need a location? | On fourteen lookups with answers fixed from the tree, Claude Haiku 5.5, Claude Sonnet 5.5, GPT-6.1 Terra, GPT-6 Luna at High and GPT-6.2 Sol at Extra-high each answer all fourteen in 17 to 32 seconds. No configuration states a wrong location. GPT-6 Luna at Low and Gemini 4 Neon and Hydrogen at High report one class in a test file as not found, and the two Gemini starts take 355 and 509 seconds ([lookup set](../acceptance/2026-11-26-locator-lookups-across-model-tiers.md)). |
| Does the task need a cause read from run evidence? | On eight incidents this repository had already diagnosed, every explorer configuration that replies names the failing step and none states a wrong cause. Where the evidence shows a failure and not its reason, Claude Opus 5.5 and Gemini configurations infer the reason and GPT-6.2 configurations stop at the failing step. A start on GPT-6.2 Astra at Medium takes 13 to 36 seconds and on Gemini 4 Carbon at High 197 to 474. Gemini 4 Neon at High returns no reply on two of eight starts ([diagnosis study](../acceptance/2026-11-26-run-evidence-diagnosis.md)). |
| Can a smaller model read the cause? | On the same eight incidents, Claude Fable 5.2 and Gemini 4 Argon state all eight recorded causes; Claude Sonnet 5.5 seven at High and at Medium, a Medium start taking 9 to 33 seconds; GPT-6 Luna at High six; Claude Haiku 5.5 five, with the one wrong cause the lead finds in 86 answers; GPT-6.1 Terra four or five; GPT-6 Luna at Low one. An answer that misses the cause usually stops at the failing step. On the one incident whose cause is inside a session database, only Fable and Argon of these state it. Through Antigravity without "run no command" in the brief, Claude Opus 5.5 and Sonnet 5.5 answer 0 and 1 of 8, Gemini 3.8 Flash 3 and GPT-OSS 120B 4 ([across tiers](../acceptance/2026-11-26-diagnosis-and-frame-reading-across-model-tiers.md)). |
| What quota and context are available? | Read quota in the host's session. The delegate call reports the token counts a run printed and exposes no remaining balance. The profiles below use the [subscription evidence](../acceptance/2026-11-20-lead-succession-evidence-866.md), which does not identify the owner's plans. The routing page lists, for each configuration, the limit it draws on, its relative cost, speed and hand-back count ([what each configuration costs](model-routing.md#what-each-configuration-costs-and-can-do)). The makers publish context windows of about a million tokens for these models, up to 512,000 for Gemini 4 Neon in Antigravity and 131,000 for GPT-OSS 120B; none is verified on this host, and none is published for a Claude model in Antigravity. |
| What time limit, and one brief or several? | A suggested allowance is 900 seconds for a reviewer and 2,400 seconds for a worker: 900 is longer than every review that handed back in the wall-time record, and 2,400 is longer than every recorded worker row but two. 600 seconds is shorter than some reviews on Claude Opus 5.5 at High, and 900 is shorter than six of seven reviews by Gemini 4 Carbon at High (see the reviewer rows below). Splitting a wide audit into several briefs is an option; one audit finished that way. The record gives the figures for each configuration ([wall time and time limits](../acceptance/2026-11-25-delegate-wall-time-and-time-limits.md)). |
| What does a second reviewer add? | On nine past commits holding 16 later-fixed defects, each configuration reviewing each commit once as the delegate call starts it and counting defects two judges both accept, GPT-6.2 Sol at Extra-high finds 10, GPT-6.2 Astra at High 8 and at Medium 7, and Claude Opus 5.5 at High 4 and at Medium 2. A GPT-6.2 reviewer adds four to eight defects to a Claude Opus 5.5 reviewer, and Claude Opus 5.5 at Medium adds none after Claude Opus 5.5 at High. Claude Opus 5.5 at High started without plan mode and without the session owner's output style finds 6; these reviews used the plan-mode start, which the Claude Code reviewer no longer uses ([start check](../acceptance/2026-11-26-reviewer-start-check.md)). Five defects are found by no reviewer. Who wrote each commit is known only in part, so the set does not show which family reviews another's work better ([reviewer recall replay](../acceptance/2026-11-25-reviewer-recall-replay.md)). |
| Does a cheaper second reviewer add anything? | On the same nine commits, Claude Sonnet 5.5 at High and GPT-6.1 Terra at High each find 4 of the 16 defects, and not the same four. Sonnet adds one defect to GPT-6.2 Sol at Extra-high and three to GPT-6.2 Astra at High. Terra's four are all found by each GPT-6.2 reviewer; it adds three to Claude Opus 5.5 at High. Nine Terra reviews take 565 seconds against 1,105 to 3,979 for the others ([added reviewers](../acceptance/2026-11-26-reviewer-recall-replay-added-reviewers.md)). |
| Which model can judge? | On the reviewer replay's eighteen packets, where its two judges share 106 verdicts, GPT-6.1 Terra at Medium gives all 106, and Claude Sonnet 5.5 at Medium, GPT-6.2 Astra at Medium and Gemini 4 Neon at High 104; eight configurations give 101 or more. Claude Haiku 5.5 and Gemini 4 Hydrogen at High give 97, and GPT-6 Luna departs on one cell in fifteen at High and one in five at Low. Of the departures that cross "found", 23 credit a review with a defect and 12 deny one. The shared verdicts are agreement between two models, not independent labels ([judging across model tiers](../acceptance/2026-11-26-judging-across-model-tiers.md)). |
| Can a cheaper model check a hand-back? | On nine past hand-backs with the files they describe, three stating a fact the files contradict, eight of ten verifiers catch all three: Claude Sonnet 5.5 and GPT-6.2 Astra and GPT-6.1 Terra at Medium, Claude Haiku 5.5 at High, Gemini 4 Neon and Hydrogen at High, and the two references. GPT-6 Luna accepts a misread frame at either effort. The GPT verifiers also reject a stated cause the files do not record, where the Claude and Gemini verifiers accept more of those. Nine checks take 155 to 502 seconds, and 1,577 on Gemini 4 Neon. This is one lead duty, not leading ([verification across tiers](../acceptance/2026-11-26-hand-back-verification-across-model-tiers.md)). |
| How reliable is the hand-back? | The ledger records two false reports: `#873`, 2026-11-21, Codex `gpt-6.2-astra` at High, worker, claims an unbriefed status edit was briefed, and the lead reverts it; `#968`, 2026-11-26, Antigravity `gemini-4-argon` at High, explorer, cites a constant and a stop reason that exist nowhere in the tree, in a passage the lead does not use. Only the Antigravity app has a lead session audited against its transcript. |

## Codex

Recorded selectors include `gpt-6.2-sol`, `gpt-6.2-astra`, `gpt-6.1-terra` and
`gpt-6-luna`. Efforts range from `low` to `xhigh`. The
[selector measurements](../acceptance/2026-11-19-coding-agent-model-evidence.md#measured-here)
cover these four selectors and leave the full model list unknown.

| Role and configuration | What the evidence supports |
| --- | --- |
| Worker, GPT-6.2 Sol at Extra-high | 28 attempts across bounded implementation (16), prose (9), hard changes (2) and tooling (1). All 28 handed back: 25 passed acceptance (17 without repair, 11 repairs total), 2 failed, 26 merged and 2 discarded. Matched runs favor Sol on code (`#834`) and Fable on prose (`#811`). |
| Worker, GPT-6.2 Sol at High | 14 attempts across hard changes (7, including `#918`, `#921`, `#922`, `#937`) and bounded implementation (7, including `#949` with 0 repairs, `#950` with 2 repairs, and `#464`, `#957` and `#944` with 1 repair each). All 14 handed back: 13 passed (4 without repair, 10 repairs total), 13 merged and 1 discarded (`#919`). |
| Worker, GPT-6.2 Astra at Extra-high, High and Medium | 3 attempts (1 Extra-high prose, 1 High prose, 1 Medium Python tooling on `#914`). All 3 handed back and passed without repair; Extra-high dropped two citations the lead restored, and High recorded one false report (`#873`, unbriefed edit reverted by the lead). |
| Reviewer, GPT-6.2 Sol at Extra-high | 8 reviews (5 code, 3 document). All 8 handed back, yielding 47 confirmed and 0 rejected findings. |
| Reviewer, GPT-6.2 Astra at High | 38 reviews across documents (23), code (14, including 11 on `#936`/`#937` plus `#913`, `#920`, `#923`) and run ledgers (1, `#896`). All 38 handed back, yielding 225 confirmed and 4 rejected findings (71 confirmed, 0 rejected on code reviews). |
| Reviewer, GPT-6.2 Astra at Medium | 35 reviews (25 document, including two on `#963`, three design rounds on `#839`, and `#967`; 10 code, including `#958` and `#943`). All 35 handed back, yielding 165 confirmed and 1 rejected findings. The two `#963` rows record `wall_seconds: 0` because elapsed time was not captured in PR `#965`/`#966`; exclude those two rows from wall-time averages. |
| Explorer, GPT-6.2 Sol at Extra-high | 3 synthesis explorations; all 3 handed back and used. |
| Explorer, GPT-6.2 Astra at High and Medium | 2 High synthesis explorations (1 handed back on `#873`; 1 timed out at 600 s on a 10-file audit for `#945`) and 2 Medium split explorations on `#945` (both handed back and used in 94–181 s). |
| Lead | The owner's account of 19 November 2026 in the [decision log](../decisions/owner-decisions.md) establishes prior use. The model, effort, work and verification are unknown. |

Read remaining quota with `/status` or on the account's usage page.

## Claude Code

Recorded models include `claude-fable-5-2`, `claude-opus-5-5`, `claude-sonnet-5-5`
and `claude-haiku-5-5`. Efforts range from `low` to `max`. Name the full identifier in
the delegate call
([token use and the served model](coding-agents.md#starting-a-delegate-on-any-coding-agent)).

| Role and configuration | What the evidence supports |
| --- | --- |
| Worker, Claude Fable 5.2 at High | 3 attempts: 1 matched prose leaf (`#811`) passed without repair and was preferred blind; 1 hard change (`#838`) failed acceptance and was finished by the lead; 1 prose attempt (`#903`) failed immediately on weekly Fable quota and was discarded. |
| Worker, Claude Opus 5.5 at High | 30 attempts across bounded implementation (16), hard changes (6), acceptance/design records (4) and prose (4, including `#967` with 0 repairs): 24 handed back and passed (11 without repair, 14 repairs total), 5 timed out on `#937` after editing files (lead verified and merged), and 1 returned `unavailable` on weekly quota (`#950`, discarded). Matched code run `#834` favored Sol. |
| Worker, Claude Opus 5.5 at Medium | 1 prose attempt (`#906`); handed back and passed after 1 repair. |
| Reviewer, Claude Opus 5.5 at High | 45 reviews (24 document, 21 code): 42 handed back with 271 confirmed and 5 rejected findings; 3 code reviews on `#937` timed out at 600 s. |
| Reviewer, Claude Opus 5.5 at Medium | 10 reviews (8 code, 2 document); all 10 handed back with 40 confirmed and 1 rejected findings. |
| Reviewer, Claude Sonnet 5.5 at High | 1 code review (`#873`); handed back with 4 confirmed and 0 rejected findings. |
| Explorer, Claude Opus 5.5 at High | 3 synthesis explorations; all 3 handed back and used. |
| Native roles | The [session measurement](../acceptance/2026-11-20-coding-agent-token-use.md) shows use of the host's locator, synthesis explorer, worker and reviewer. It measures token use, leaving their relative quality unknown. |
| Lead, Claude Opus 5.5 and Claude Fable 5.2 | The sample covers two lead transcripts. Lead effort is unrecorded. The cost of rereading a large context is measured for one Fable session. |

Read remaining quota with `/usage`. The maker's pages describe a weekly limit shared by
all Claude models, a five-hour limit on some plans and a separate weekly Fable limit on
larger plans. A delegated Fable start can bill usage credits without asking
([quota and spending](model-routing.md#quota-and-spending)).

## Antigravity

Use `agy models` for the available models. The delegate call takes model and effort
separately, as in `gemini-4-neon` at `xhigh`.

| Role and configuration | What the evidence supports |
| --- | --- |
| Worker | No real worker task is recorded through the delegate call. A print-mode worker can edit and reply when asked to run no command (observed by hand, no retained record). The app's own worker edited two files on one watched documentation leaf using the lead's model. |
| Explorer, Gemini 4 Neon at Extra-high | 4 synthesis explorations (`#861`, `#873`); all 4 handed back and used. Verification covers a sample of the citations. |
| Reviewer, Gemini 4 Carbon at High | The delegate call supports a bias check on a brief and its scoring sheet, with findings the lead confirmed. For review requiring clean context, use the [host guidance](coding-agents.md#delegation-roles). |
| Reviewer, print mode | A reviewer can use a diff supplied in the brief (no retained review report). On a brief that leaves the reviewer to open the diff and source itself, and with quota available, Gemini 4 Carbon at High hands back 7 reviews in 12 starts, at 636 to 1,471 seconds each, and Gemini 4 Neon at High 1 in 17; the rest end empty on a denied command ([replay](../acceptance/2026-11-25-reviewer-recall-replay.md#the-gemini-starts)). Those starts did not tell the reviewer to run no command. The call now adds that instruction, and on three of the same commits Neon hands back 3 of 3 and Carbon 2 of 3, with one stopped at 1,500 seconds ([start check](../acceptance/2026-11-26-reviewer-start-check.md)). |
| App lead, Gemini 4 Neon at High | The [watched documentation leaf](../acceptance/2026-11-19-antigravity-lead-trial-810.md) supports leading as far as a queued merge with the owner present. Verification was partial, the report overstated what was checked, and another lead completed the merge. There is no comparable evidence for source work. |

Antigravity has two quota groups, each with a weekly limit and, on the paid plans its
pages describe, a five-hour limit: the Gemini
models share one, so a refusal on Gemini 4 Neon can be followed by the same refusal on
Gemini 4 Carbon, and the Claude and GPT models it serves share the other. Gemini 4
Argon, Gemini 3.8 Flash and GPT-OSS 120B leave on 30 November 2026. The CLI changelog places `/usage`, `/quota` and `/credits` in an
interactive session. They return exit code 2 in print mode.

## Keeping this page current

Add attempts to the ledger. Change this page in the same pull request only when the
evidence changes a conclusion about a configuration, role, kind of work or limit.

[Operations index](../runbook.md).
