---
owner: lead
status: historical
kind: review
date: '2026-11-26'
scope: 'Re-reading of the public figures behind model choice for engineering work across every model the three coding agents offer, with speed, subscription limits and capabilities; no gameplay and no paid model call'
---

# Coding-agent model evidence re-read on 26 November 2026

## At a glance

This record re-reads the public evidence behind model choice for engineering work across every model offered by Claude Code, Codex and Antigravity, adding speed, context limits, image input, list prices and subscription metering. On the Artificial Analysis Coding Agent Index, the top configurations sit close together: Gemini 4 Neon at Xhigh (58.6), Claude Fable 5.2 at Xhigh (58.5) and High (58.2), and Claude Opus 5.5 at Max (58.2). On Terminal-Bench 4.1, Copilot Fusion leads at 71.2% ± 2.9%, while the leading Claude Code, Codex and Antigravity rows fall between 61.2% ± 2.8% and 65.8% ± 3.1%. Effort settings shift both score and wait time: Fable 5.2 at Max scores below Fable 5.2 at High while taking 129.5 minutes per task against 31.3 minutes, and GPT-6.2 Astra and Sol drop sharply at Low. The smallest models, Claude Haiku 5.5 and GPT-6 Luna, trail far behind on patches, codebase questions and terminal tasks. Two subscription facts matter right away: Gemini 4 Argon, Gemini 3.8 Flash and GPT-OSS-120b leave Antigravity on November 30, 2026, and Claude Code's `-p` flag bills Fable requests to usage credits without asking when a plan requires credits. No public evidence was found for house-style documents, dated records, reading run ledgers or C++ in a large codebase, and almost none covers code review or judging by Fable 5.2, GPT-6.x or Gemini 4 models. Nothing here was measured on this repository, and this record requests no owner decision.

## How each figure was read

All sources were read on 26 November 2026 between 05:50 and 06:25 UTC, read-only, without viewing rendered charts in a browser, without spending money and without gameplay. Every figure carries one of these marks:

- **Raw fetch:** the page or data file was downloaded directly by HTTP and read as text, or the page's own embedded data was parsed by a script with no model in between.
- **Summariser:** fetched through WebFetch, where a small model summarised the page from markdown; a row could be transposed unless a raw fetch also checked it.
- **Snippet:** seen only in a search result summary.
- **Second-hand:** a third party's write-up of someone else's figures.

The three research files this record is written from, the raw page downloads and the
extraction scripts are retained as
[`coding-agent-model-evidence-reread`](../../data/evidence/coding-agent-model-evidence-reread.sha256).

A public coding-agent score measures the coding agent and model together, usually in the model maker's own agent. Pay-per-token API cost is not consumer subscription billing; it appears here only as a relative signal of token volume.

## Coding-agent index

[Artificial Analysis Coding Agent Index](https://artificialanalysis.ai/agents/coding-agents) (raw fetch, 26 November 2026 06:18 UTC). The page heading carries no version number, and no "last updated" date appears on the page; each reward-hacking audit block carries `materializedAt` 2026-11-25T22:16:48 UTC. The index is the equal-weight mean of three benchmarks, averaged over three attempts per task: FrontierCode-AA 2.0 (software engineering tasks, 132 tasks, by Cognition, implemented by Artificial Analysis), Terminal-Bench 4.1 (agentic terminal use, 66 tasks, by Laude Institute; internal dataset id `terminal-bench-v4`) and SWE-Atlas-QnA-AA (technical Q&A, 124 tasks, by Scale AI, grading adjusted by Artificial Analysis).

The table includes every row for a model in its maker's own agent from the page's embedded `benchmarkRows` array. Raw 0 to 1 scores are multiplied by 100 and rounded to one decimal; wall-clock seconds per task are divided by 60 and rounded to one decimal; pay-per-token API dollars per task are rounded to cents.

| Coding agent | Model and effort | Index | Patch score (FrontierCode) | Codebase questions | Terminal tasks | Minutes per task | Dollars per task |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Claude Code | Claude Fable 5.2 (Max, Default Fallback) | 55.7 | 43.6 | 60.5 | 63.1 | 129.5 | $44.22 |
| Claude Code | Claude Fable 5.2 (Xhigh, Default Fallback) | 58.5 | 49.2 | 62.1 | 64.1 | 53.3 | $15.47 |
| Claude Code | Claude Fable 5.2 (High, Default Fallback) | 58.2 | 48.7 | 61.8 | 64.1 | 31.3 | $7.51 |
| Claude Code | Claude Fable 5.2 (Medium, Default Fallback) | 53.0 | 35.8 | 63.7 | 59.6 | 15.1 | $2.89 |
| Claude Code | Claude Fable 5.2 (Low, Default Fallback) | 48.0 | 30.9 | 59.9 | 53.0 | 13.4 | $2.49 |
| Claude Code | Claude Opus 5.5 (Max, Default Fallback) | 58.2 | 44.0 | 65.9 | 64.6 | 65.3 | $12.61 |
| Claude Code | Claude Sonnet 5.5 (Max, Default Fallback) | 56.3 | 39.1 | 64.2 | 65.7 | 86.8 | $11.40 |
| Claude Code | Claude Haiku 5.5 (Max) | 29.6 | 23.1 | 33.9 | 31.8 | 77.4 | $2.25 |
| Codex | GPT-6.2 Astra (Max) | 53.5 | 41.7 | 55.1 | 63.6 | 25.1 | $5.12 |
| Codex | GPT-6.2 Astra (Xhigh) | 53.1 | 43.5 | 53.8 | 62.1 | 16.5 | $3.20 |
| Codex | GPT-6.2 Astra (High) | 52.3 | 42.2 | 54.6 | 60.1 | 15.8 | $2.37 |
| Codex | GPT-6.2 Astra (Medium) | 49.1 | 39.9 | 53.8 | 53.5 | 11.6 | $1.20 |
| Codex | GPT-6.2 Astra (Low) | 35.6 | 26.5 | 36.3 | 43.9 | 7.8 | $0.70 |
| Codex | GPT-6.2 Sol (Max) | 48.6 | 41.5 | 46.2 | 58.1 | 17.5 | $1.22 |
| Codex | GPT-6.2 Sol (Xhigh) | 49.8 | 40.4 | 51.3 | 57.6 | 12.6 | $0.90 |
| Codex | GPT-6.2 Sol (High) | 47.5 | 38.3 | 50.5 | 53.5 | 10.6 | $0.76 |
| Codex | GPT-6.2 Sol (Medium) | 45.4 | 36.3 | 50.3 | 49.5 | 8.4 | $0.57 |
| Codex | GPT-6.2 Sol (Low) | 37.2 | 28.1 | 42.5 | 40.9 | 7.2 | $0.33 |
| Codex | GPT-6.1 Terra (Max) | 48.6 | 41.4 | 54.0 | 50.5 | 28.1 | $1.53 |
| Codex | GPT-6 Luna (Max) | 25.9 | 24.1 | 38.4 | 15.2 | 23.5 | $0.19 |
| Antigravity CLI | Gemini 4 Neon (Xhigh) | 58.6 | 43.0 | 67.7 | 65.2 | 30.5 | $6.86 |
| Antigravity CLI | Gemini 4 Carbon (High) | 55.5 | 38.0 | 63.7 | 64.6 | 33.6 | $9.75 |
| Antigravity CLI | Gemini 4 Hydrogen (Xhigh) | 52.3 | 36.6 | 60.2 | 60.1 | 32.1 | $4.45 |
| Antigravity CLI | Gemini 4 Argon (High) | 45.5 | 24.8 | 55.1 | 56.6 | 37.7 | $13.67 |

Across twelve other coding agents on the same page, GPT-6 Luna (Max) scores from 17.2 (Qwen Code) to 25.1 (mini-swe-agent) on the index and from 20.2 (Devin CLI) to 39.5 (Muse Code) on codebase questions, including 22.2 on the index and 34.4 on codebase questions in Claude Code. One third-party hybrid row also uses models from this lineup: Devin Fusion CLI with Claude Opus 5.5 Max + GPT-6 Luna High scores 58.4 on the index and 68.3 on codebase questions.

- **Missing rows and effort coverage:** Gemini 3.8 Flash (marked deprecated in the site's model list) and gpt-oss-120b have no benchmark row. Only Fable 5.2, GPT-6.2 Astra and GPT-6.2 Sol appear at all five efforts.
- **Labels and versions:** Claude Fable 5.2, Opus 5.5 and Sonnet 5.5 rows carry "Default Fallback", which the page does not explain. Recorded harness versions are Claude Code 2.1.280 to 2.1.291, Codex 0.154.0 to 0.166.0 and Antigravity CLI 1.2.10 to 1.5.8.
- **Timing, cost and grading caveats:** Execution time is whole-workflow wall-clock time per task and excludes environment startup, verifier or judge time and harness overhead (summariser). Cost is pay-per-token API cost, and prompt cache hit rates vary by provider routing (summariser). Terminal-Bench 4.1 and SWE-Atlas-QnA-AA are pass or fail; a FrontierCode-AA 2.0 attempt scores 0 or between 70% and 100%. The Terminal-Bench audit lists `judgeModel` "sonnet", so one entrant's model judges part of it. The page publishes no confidence intervals and no language breakdown.
- **Original Scale AI codebase Q&A board:** [Scale AI SWE Atlas Codebase QnA](https://labs.scale.com/leaderboard/sweatlas-qna) (summariser, updated 28 July 2026) predates the newer models and includes only one model of interest, Gemini 3.8 Flash in Mini-SWE-Agent at 47.04 ± 5.08 (rank 6; top row Opus 5 in Claude Code xHigh at 63.17 ± 5.01). It covers 124 tasks across 11 repositories in Go, Python, C and TypeScript, judged by Claude Opus 4.5, and its prose ("30%" and "35%" pass rates) conflicts with its table.

## Terminal tasks

[Terminal-Bench 4.1 leaderboard](https://www.tbench.ai/leaderboard) (raw fetch, 26 November 2026 06:18 UTC; leaderboard `updated_at` 2026-11-20T16:07:10 UTC). Every row runs 330 trials. Accuracy carries a ± 95% confidence interval, and Tokens and Cost are totals across all 330 trials rather than per task. Rank 1 appears for context alongside every row for a model of interest.

| Rank | Agent | Model | Effort | Accuracy | Release date | Tokens (330 trials) | Cost (330 trials) |
| ---: | --- | --- | --- | --- | --- | ---: | ---: |
| 1 | GitHub Copilot | Copilot Fusion | max | 71.2% ± 2.9% | Nov 17, 2026 | 3.3B | $1,987.33 |
| 2 | Claude Code | Opus 5.5 | max | 65.8% ± 3.1% | Sep 22, 2026 | 8.0B | $4,718.65 |
| 2 | Claude Code | Fable 5.2 | max | 65.8% ± 2.8% | Nov 9, 2026 | 15.7B | $16,492.76 |
| 4 | Antigravity CLI | Gemini 4 Carbon | high | 64.5% ± 3.2% | Oct 28, 2026 | 3.8B | $1,358.25 |
| 5 | Claude Code | Sonnet 5.5 | max | 63.9% ± 3.0% | Sep 28, 2026 | 19.4B | $7,333.64 |
| 6 | Codex | GPT-6.2 Astra | max | 62.1% ± 2.3% | Nov 17, 2026 | 1.1B | $1,409.14 |
| 7 | Codex | GPT-6.2 Sol | max | 61.5% ± 2.8% | Nov 17, 2026 | 1.1B | $349.16 |
| 8 | Antigravity CLI | Gemini 4 Neon | xhigh | 61.2% ± 2.8% | Nov 18, 2026 | 3.2B | $1,922.24 |
| 16 | Antigravity CLI | Gemini 4 Hydrogen | high | 56.4% ± 3.0% | Nov 12, 2026 | 3.6B | $784.24 |
| 17 | Antigravity CLI | Gemini 4 Argon | high | 55.5% ± 2.8% | Sep 30, 2026 | 2.8B | $1,108.98 |
| 21 | Codex | GPT-6.1 Terra | max | 53.3% ± 3.1% | Oct 26, 2026 | 8.5B | $874.44 |
| 32 | Claude Code | Haiku 5.5 | max | 40.0% ± 3.6% | Oct 7, 2026 | 12.1B | $952.47 |
| 50 | mini-SWE-agent | Gemini 3.8 Flash | high | 18.2% ± 3.4% | Sep 2, 2026 | 17.2B | $1,828.77 |
| 53 | Codex | GPT-6 Luna | max | 15.2% ± 2.7% | Sep 22, 2026 | 3.9B | $72.14 |

gpt-oss-120b has no row, and no model of interest has a row below its listed effort. The leaderboard states no task-type, language or harness caveats beyond its 95% confidence intervals and a training-corpus canary.

## Review

[ReviewBench](https://review-bench.ai) (raw fetch of `/leaderboard.md`, `/api/leaderboard`, `/methodology.md` and `/about.md`, 06:18 UTC; summariser matched). GitHub Inc. (a subsidiary of Microsoft Corporation) develops ReviewBench and also develops GitHub Copilot code review, one of the evaluated reviewers. Default high-severity grounded table (ranked by grounded F1, three rounds, profile `official-2026-09`), rows naming a model of interest:

| Rank | Agent | F1 | Precision | Recall | Date |
| ---: | --- | ---: | ---: | ---: | --- |
| 5 | Laude RevEngine · anthropic/claude-opus-5.5 | 73.3% | 92.8% | 60.6% | 2026-10-14 |
| 9 | Klaussy · claude-opus-5-5 · 1 | 69.3% | 93.3% | 55.2% | 2026-10-22 |
| 11 | block/review · sol-opus · off | 68.2% | 94.3% | 53.5% | 2026-10-14 |
| 19 | Klaussy · claude-sonnet-5-5 · 1 | 63.1% | 93.5% | 47.6% | 2026-10-13 |
| 21 | Klaussy · claude-sonnet-5-5 · default | 60.2% | 95.6% | 43.9% | 2026-10-13 |

- **ReviewBench configuration and other views:** Klaussy `· 1` is `include-nits=1`, `· default` is `effort=default`, and `block/review` is `panel=sol-opus · gate=off` (panel models are not named further). High-severity augmented scores from the API (raw fetch): Laude/Opus 5.5 95.3% precision and 74.0% recall; Klaussy/Opus 5.5 96.2% and 81.0%; Klaussy/Sonnet 5.5 (nits) 95.1% and 58.0%; Klaussy/Sonnet 5.5 (default) 96.6% and 54.1%. All-severity grounded precision and recall from the API (raw fetch, rounded to one decimal in source): Klaussy/Opus 5.5 80.2 / 58.1; Laude/Opus 5.5 83.6 / 46.3; block/review sol-opus 88.7 / 32.6; Klaussy/Sonnet 5.5 (nits) 84.1 / 29.8; Klaussy/Sonnet 5.5 (default) 86.5 / 22.6.
- **ReviewBench coverage and limits:** Every Codex entry uses a GPT-5.x model (best high-severity Codex row: Codex · GPT-5.6 Sol · Max at 96.3% precision and 55.3% recall). No entry uses Fable 5.2, Haiku 5.5, any GPT-6.x model, any Gemini 4 model, Gemini 3.8 Flash or GPT-OSS 120B. The set holds 219 public pull requests labelled by a Claude Sonnet 5 classifier audited by humans (96.6% agreement with human labels on true/false positive, 62.9% exact on severity, 79.7% on category). The maintainer states that the golden set is not exhaustive, scores depend on the classifier and an LLM matcher, augmented recall is not meant as the sole ranking basis, and results are not definitive measures of real-world performance.
- **Cross-model review (Song):** [Song](https://arxiv.org/html/2610.01471v2) (raw fetch of full text, 06:20 UTC; abstract at [arXiv](https://arxiv.org/abs/2610.01471), summariser; single author, v2 of 6 October 2026) studies 30 artifacts with 150 planted errors across 900 sessions. None of its models is in the current lineup (generator Claude Opus 4.6; reviewers GPT-5.4 in Codex CLI, Gemini 2.5 Pro and Gemini 2.5 Flash). Table 3 F1 percentages: Code: CCR 40.7, GePro-R 23.4, GPT 37.2, GPT-R 29.8; Document: 24.5, 38.1, 42.1, 40.7; Script: 20.7, 25.6, 15.4, 25.8. One same-model plus one cross-model review finds 56.7% of planted errors against 42.7% for two same-model reviews; a third reviewer reaches 58.0% recall (1.3 percentage points over the two-model union). Limits stated: model difference and reviewer capability are confounded, non-significance does not establish equivalence, one baseline run and 14 failed calls were excluded, baselines preceded cross-model runs, and records are available only on request.
- **Central verification (Kim and others):** [Kim and others](https://arxiv.org/html/2512.08296v3) (raw fetch of full text, 06:20 UTC; abstract at [arXiv](https://arxiv.org/abs/2512.08296), summariser) study 260 configurations across six benchmarks and three model families using 2025-generation models (GPT-5, mini, nano; Gemini 2.0 Flash, 2.5 Flash, 2.5 Pro; Claude Sonnet 3.7, 4, 4.5). Independent systems amplify trace-level errors 17.2×, while centralized coordination contains this to 4.4×. Cross-validated R² is 0.373 in controlled settings with standardized tools and prompts.

## Judging

- **Scale AI Labs blog post:** [Scale AI Labs](https://labs.scale.com/blog/to-jev-or-not-to-jev) (12 November 2026, Shreyas Subramanian; summariser, 06:22 UTC) evaluates Claude Opus 5.5 with thinking at 94.7% on JudgeBench (later giving "Opus alone: 94.4%", which conflicts), "above 90%" on LLMBar (91.7% in a routing passage), 88.5% on a 300-item sample of RewardBench 2 (full set 1,763), HelpSteer2 Spearman ρ 0.434 and quadratic-weighted κ 0.55, and AgentRewardBench AUROC 0.933. Claude Haiku 5.5 (effort not stated) scores HelpSteer2 ρ 0.442 and κ 0.50; its JudgeBench, LLMBar and RewardBench 2 accuracies appear only in an image table (Table 1) that the summariser could not read. No figure appears for Fable 5.2, Sonnet 5.5, any GPT-6.x model, any Gemini 4 model, Gemini 3.8 Flash or GPT-OSS 120B (the post uses GPT-5.6). Limits stated: small sets where only gaps of about 4 to 6 points are detectable, single pilot-scale runs, some strong models omitted, and the author sells competing judge models.
- **Lexometrica Ground Truth:** [Lexometrica Ground Truth](https://lexometrica.ru/bench) (summariser, 06:23 UTC) scores Russian legal reasoning over 30 closed cases with two LLM judges (Claude Opus 5.5 and Grok 4.7); neither page read mentions human expert grades. Per-judge scores: Fable 5.2 0.860 overall (Opus judge 0.866, Grok judge 0.854); Opus 5.5 0.816 (0.823, 0.809); Gemini 4 Carbon 0.850 (0.846, 0.855); GPT-6.2 Astra 0.795 (0.770, 0.819). A TechTimes article of 23 November 2026 (summariser, second-hand; full URL not recorded in the source file) reports Pearson correlation 0.953 between the two judges over 450 answers and an Anthropic-model shift (Opus minus Grok) of +0.040 (interval +0.020 to +0.060). Limits stated: 30 closed cases, intervals cover case sampling rather than judge variation, each judge ran once, both judges are also contestants, and results are self-reported and unverified.
- **Indirect evidence:** ReviewBench's Claude Sonnet 5 classifier (not a model in the current lineup) agrees with human labels 96.6% on true/false positive.
- **Missing leaderboards:** No official JudgeBench, RewardBench 2, Judge Arena or LLMBar leaderboard page was found with models from this lineup.

## Reading sources and wrong answers

- **Vectara hallucination leaderboard (grounded summarization):** [Vectara hallucination leaderboard](https://github.com/vectara/hallucination-leaderboard) (raw fetch of README, 06:19 UTC; summariser matched; last updated 24 November 2026; judge model HHEM-2.3). Three models of interest appear (hallucination rate, factual consistency, answer rate, average summary words): `anthropic/claude-opus-5-5` at 9.9 %, 90.1 %, 99.7 % and 192.1 words; `google/gemini-4-argon` at 12.1 %, 87.9 %, 99.1 % and 178.2 words; and `openai/gpt-oss-120b` at 14.2 %, 85.8 %, 99.9 % and 135.2 words. The lowest hallucination rate on the board is `antgroup/finix_s1_32b` at 1.8 %. Near-misses on the board are earlier models (`openai/gpt-6-sol` 6.5 %, `openai/gpt-6-astra` 8.7 %, `openai/gpt-5.6-sol` 12.4 %). No row appears for Fable 5.2, Sonnet 5.5, Haiku 5.5, GPT-6.2 Sol or Astra, GPT-6.1 Terra, GPT-6 Luna, Gemini 4 Neon, Carbon or Hydrogen, or Gemini 3.8 Flash. Limits stated: measures factual consistency rather than quality, judged by a model, English only, private dataset, and extractive summaries score well.
- **Artificial Analysis AA-Omniscience (closed-book factual recall):** [AA-Omniscience](https://artificialanalysis.ai/evaluations/omniscience) (raw fetch of embedded `omniscience` and `omniscienceBreakdown` data, 06:20 UTC; summariser matched the highlights text; v1.1, October 2026, 3,000 questions). This measures closed-book recall rather than reading sources. Net score runs from −100 to 100, rewarding correct answers, penalising wrong ones and not penalising refusals. Hallucination rate is `incorrect / (incorrect + partial + not attempted)`, the share of non-correct responses that were wrong guesses rather than the share of all answers.

| Model (effort) | Net score | Accuracy | Hallucination rate | Attempt rate |
| --- | ---: | ---: | ---: | ---: |
| Claude Fable 5.2 (Max) | 66.8 | 79.1% | 59.3% | 94.8% |
| Gemini 4 Neon (Xhigh) | 54.8 | 60.5% | 14.4% | 67.5% |
| Gemini 4 Carbon (High) | 53.5 | 58.3% | 11.4% | 64.3% |
| GPT-6.2 Astra (Max) | 50.0 | 68.6% | 59.1% | 89.9% |
| Claude Opus 5.5 (Max) | 48.1 | 65.5% | 50.3% | 86.7% |
| Gemini 4 Hydrogen (Xhigh) | 46.3 | 50.5% | 8.5% | 56.0% |
| GPT-6.2 Sol (Max) | 40.4 | 61.6% | 55.4% | 85.4% |
| Claude Sonnet 5.5 (Max) | 30.5 | 51.5% | 43.3% | 76.3% |
| GPT-6.1 Terra (Max) | 29.6 | 47.6% | 34.5% | 68.4% |
| Claude Haiku 5.5 (Max) | 12.3 | 34.7% | 34.2% | 60.0% |
| GPT-6 Luna (Max) | −8.3 | 39.6% | 79.3% | 90.4% |

Page highlight text (summariser) gives Fable 5.2 net scores of 67 (Max), 65 (Xhigh) and 64 (High), with accuracy 79%, 78% and 77%, and lists Gemini 4 Carbon (Medium) at 4% and Gemini 4 Argon (High) at 4% as the lowest hallucination rates; neither has a full record in the embedded data. Gemini 3.8 Flash and GPT-OSS 120B have no figure.

- **Artificial Analysis AA-LCR v1.1 (long-document reasoning):** [AA-LCR](https://artificialanalysis.ai/evaluations/artificial-analysis-long-context-reasoning) (raw fetch of embedded `lcr` field and summariser of text, 06:20 UTC; 100 questions over documents of 10k to 100k tokens, pass/fail graded by another LLM). Highlights text lists Kimi K3 (Max) 88.7%, Step 5 Preview 88.3% and Kimi K3.1 Pro 86.3%. Embedded `lcr` values (multiplied by 100 and rounded to one decimal in source): Claude Opus 5.5 (Max) 84.7, Gemini 3.8 Flash (Medium) 84.0, Claude Fable 5.2 (Max) 83.3, GPT-6 Luna (Max) 83.3, Claude Sonnet 5.5 (Max) 82.7, GPT-6.1 Terra (Max) 82.7 and Claude Haiku 5.5 (Max) 82.7. That the single `lcr` field holds the v1.1 score is an inference in the source file. On the Omniscience page, `lcr` is null for GPT-6.2 Astra, GPT-6.2 Sol and the Gemini 4 models, leaving no figure for them.
- **Unreadable or snippet-only grounding pages:** [Kaggle FACTS Grounding](https://www.kaggle.com/benchmarks/google/facts-grounding) returned no data to the summariser or raw HTML fetch because it is a JavaScript app; a snippet says GPT-6.1 Terra leads the 14 November 2026 update, with Gemini 4 Hydrogen fourth and Carbon seventh, with no scores. Fiction.LiveBench rendered no content to the summariser. Primary vendor system cards for hallucination and long-context tables were not found.

## Speed

Every speed figure below comes from each model's Artificial Analysis page (summariser, 26 November 2026, 05:50 to 06:22 UTC). Artificial Analysis publishes time to first answer token (TTFAT), which includes thinking time and rises steeply with effort; its time to first token field has no value for any of these models. Speeds are measured on each maker's own API rather than inside Claude Code, Codex or Antigravity, except GPT-OSS 120B, whose figures are the median across 15 providers. Each cell shows output tokens per second / TTFAT in seconds.

| Model | Max | Xhigh | High | Medium | Low |
| --- | --- | --- | --- | --- | --- |
| [Claude Fable 5.2](https://artificialanalysis.ai/models/claude-fable-5-2) | 113 / 262.88 | 112 / 76.49 | 111 / 29.90 | 109 / 12.54 | 111 / 9.33 |
| [Claude Opus 5.5](https://artificialanalysis.ai/models/claude-opus-5-5) | 116 / 356.07 | 111 / 88.14 | 109 / 23.50 | 105 / 14.72 | 107 / 5.99 |
| [Claude Sonnet 5.5](https://artificialanalysis.ai/models/claude-sonnet-5-5) | 153 / 270.32 | 148 / 41.45 | 141 / 13.75 | 143 / 5.27 | 134 / 4.33 |
| [Claude Haiku 5.5](https://artificialanalysis.ai/models/claude-haiku-5-5) | 256 / 162.31 | 237 / 52.03 | 230 / 20.97 | 221 / 10.49 | 221 / 7.51 |
| [GPT-6.2 Sol](https://artificialanalysis.ai/models/gpt-6-2-sol) | 64 / 117.98 | 62 / 52.31 | 61 / 19.54 | 62 / 4.31 | 59 / 1.96 |
| [GPT-6.2 Astra](https://artificialanalysis.ai/models/gpt-6-2-astra) | 45 / 172.56 | 44 / 57.95 | 44 / 27.96 | 45 / 3.43 | 40 / 2.95 |
| [GPT-6.1 Terra](https://artificialanalysis.ai/models/gpt-6-1-terra) | 66 / 197.46 | 64 / 37.98 | 63 / 14.12 | 63 / 5.75 | 61 / 2.80 |
| [GPT-6 Luna](https://artificialanalysis.ai/models/gpt-6-luna) | 123 / 68.52 | 117 / 17.49 | 119 / 10.61 | 109 / 5.93 | 100 / 2.23 |
| [Gemini 4 Neon](https://artificialanalysis.ai/models/gemini-4-neon) | no Max variant | 84 / 59.80 | 102 / 36.22 | 95 / 25.77 | 95 / 18.83 |
| [Gemini 4 Carbon](https://artificialanalysis.ai/models/gemini-4-carbon) | no Max variant | no Xhigh variant | 49 / 65.46 | 61 / 36.54 | 48 / 11.92 |
| [Gemini 4 Hydrogen](https://artificialanalysis.ai/models/gemini-4-hydrogen) | no Max variant | 173 / 53.49 | 176 / 18.42 | 168 / 12.43 | 149 / 6.20 |
| [Gemini 4 Argon](https://artificialanalysis.ai/models/gemini-4-argon) | no Max variant | no Xhigh variant | 80 / 37.55 | 69 / 10.40 | not found |
| [Gemini 3.8 Flash](https://artificialanalysis.ai/models/gemini-3-8-flash) | no Max variant | no Xhigh variant | 100 / 22.00 | 102 / 13.10 | 80 / 2.29 |
| [GPT-OSS 120B](https://artificialanalysis.ai/models/gpt-oss-120b) | no Max variant | no Xhigh variant | 192 / 9.93 | not found | 174 / 1.70 |
| Claude Opus 5.5 in Antigravity | not found | not found | not found | not found | not found |
| Claude Sonnet 5.5 in Antigravity | not found | not found | not found | not found | not found |

Non-reasoning variants listed on Artificial Analysis: GPT-6.1 Terra 62 / 2.28 and GPT-6 Luna 98 / 1.27 (summariser).

- **Anthropic speed labels:** The [Anthropic models overview](https://platform.claude.com/docs/en/about-claude/models/overview) (summariser) labels Fable 5.2 "Moderate", Opus 5.5 "Moderate", Sonnet 5.5 "Fast" and Haiku 5.5 "Fastest".
- **Google speed descriptions:** The [Google Gemini models page](https://aistudio.google.com/docs/models) (summariser) describes Neon as "fast end-to-end task completion", Hydrogen as "speed and efficiency", and Argon as having "faster responses and lower token spend per turn" than Carbon.
- **OpenAI speed modes:** The [OpenAI models page](https://developers.openai.com/api/docs/models) (summariser) gives no speed label. On the [Codex pricing page](https://learn.chatgpt.com/docs/pricing) (summariser), the Fast mode multiplier on included usage is 2x for GPT-6.2 Astra and Sol and 2.5x for GPT-6.1 Terra and GPT-6 Luna, and the Ultrafast multiplier is 6x for GPT-6.2 Astra and Sol. The [ChatGPT Pro plans page](https://help.openai.com/en/articles/9793128-about-chatgpt-pro-plans) (summariser) says Ultrafast on Pro 200 is "GPT-6.2 Sol in Codex only", is "Not included" on Pro 100, and is included on Pro 500.

## Context, images and list price

All figures below were read through the summariser on 26 November 2026 from the maker documentation pages above, the [Google Gemini pricing page](https://aistudio.google.com/docs/pricing), the [Claude Code model configuration page](https://code.claude.com/docs/en/model-config), the [Antigravity models page](https://antigravity.google/docs/models), the [Antigravity plans page](https://antigravity.google/docs/plans) and the Artificial Analysis model pages. List prices are per million tokens (input / output) and act only as a relative-cost signal.

| Model | Context window | Max output | Image input | List price (input / output) |
| --- | --- | --- | --- | --- |
| Claude Fable 5.2 | 1M tokens | 128K tokens | Yes | $8 / $40 |
| Claude Opus 5.5 | 1M tokens | 128K tokens | Yes | $4 / $20 |
| Claude Sonnet 5.5 | 1M tokens | 128K tokens | Yes | $2 / $10 |
| Claude Haiku 5.5 | 1M tokens | 128K tokens | Yes | From $0.10 / From $0.50 |
| GPT-6.2 Sol | 1.05M (AA: 1M) | 128K tokens | Yes | $2 / $10 |
| GPT-6.2 Astra | 1.05M (AA: 1M) | 128K tokens | Yes | $8 / $40 |
| GPT-6.1 Terra | 1.05M (AA: 1M) | 128K tokens | Yes | $1 / $5 |
| GPT-6 Luna | 1.05M (AA: 1M) | 128K tokens | Yes | $0.1 / $0.5 |
| Gemini 4 Neon | API: 1M tokens; Antigravity: up to 512K tokens | 64K / 1M tokens | Yes (text, image, audio, video, PDF) | $3.00 / $15.00 |
| Gemini 4 Carbon | 1M tokens | 64K / 1M tokens | Yes (text, image, audio, video, PDF) | $2.00 / $10.00 through November 30, 2026; $4.00 / $20.00 starting December 1, 2026 (AA: $4.00 / $20.00) |
| Gemini 4 Hydrogen | 1M tokens | 64K / 1M tokens | Yes (text, image, audio, video, PDF) | $1.50 / $7.50 |
| Gemini 4 Argon | 1M tokens | 64K / 1M tokens | Yes (text, image, audio, video, PDF) | $2.00 / $10.00 through November 30, 2026; $4.00 / $20.00 starting December 1, 2026 (AA: $4.00 / $20.00) |
| Gemini 3.8 Flash | AA: 1M tokens; Google page: not found | not found | AA: yes (text, image, speech, video); Google page: not found | $0.75 / $3.75 through December 31, 2026; $1.50 / $7.50 after |
| GPT-OSS 120B | 131k tokens | not found | No (text only) | AA median: $0.15 / $0.60 (High), $0.13 / $0.59 (Low) |
| Claude Opus 5.5 in Antigravity | not found | not found | Antigravity page: not found (model accepts images) | Antigravity price: not found |
| Claude Sonnet 5.5 in Antigravity | not found | not found | Antigravity page: not found (model accepts images) | Antigravity price: not found |

- **Anthropic notes:** Max output is the synchronous Messages API limit. The Claude Code model configuration page says Fable models, Sonnet 5 and later, and Haiku 5.5 run with the 1M window by default.
- **OpenAI note:** Image input comes from a general statement ("All latest OpenAI models support text and image input") rather than a per-model field; Artificial Analysis lists "text and image" for each.
- **Google and Antigravity notes:** Google's output limit appears verbatim as "64K / 1M tokens" without explanation. Antigravity lists Gemini 4 Neon as "Up to 512K tokens", half its API window, and says overage credits are charged "at standard Gemini Enterprise consumption pricing".

## Subscription limits

Antigravity's model page says "Gemini 4 Argon, Gemini 3.8 Flash, GPT-OSS-120b, and Claude 4.6 models are leaving on November 30, 2026." Claude Code's model configuration page says that with the `-p` flag "Claude Code never asks for consent. When a Fable request there would bill to usage credits, Claude Code bills it without asking." Both quotations are from the lead's second fetch of the two pages on 26 November 2026; their wording is retained in the worker's brief in the sealed evidence, and the research files record the same facts in other words.

Other subscription facts below were read through the summariser on 26 November 2026 from the Codex pricing page, the ChatGPT Pro plans page, the Antigravity models and plans pages, the Claude Code model configuration page, and four Anthropic support articles: [Using Claude Code with your Pro or Max plan](https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan), [Understanding usage and length limits](https://support.claude.com/en/articles/11647753-understanding-usage-and-length-limits), [Models, usage and limits (Max plan)](https://support.claude.com/en/articles/11049741-models-usage-and-limits) (each "Updated over 3 weeks ago") and [Models, usage and limits in Claude Code](https://support.claude.com/en/articles/14552983-models-usage-and-limits-in-claude-code) ("Updated over a month ago"; does not mention Fable).

| Coding agent and model | Limit it draws on | Published weights or message estimates | Shared or per-model pool |
| --- | --- | --- | --- |
| Claude Code, Claude Fable 5.2 | Max and Ultra: separate weekly limit for Fable (one page says "some plans"). Depending on plan and seat, can bill to usage credits instead of included limits (`/model` picker shows "Requires usage credits"). | not found | Separate weekly Fable limit; five-hour session limit and general weekly limit are shared with other models. |
| Claude Code, Claude Opus 5.5 | Five-hour session limit (Pro and Max; verified Ultra has none) and general weekly limit across all models. | Costs several times more per turn than Sonnet; no numeric figure. Max gives five times Pro usage every five hours and every week. | Shared across models and across claude.ai, Claude Code and Claude Desktop. |
| Claude Code, Claude Sonnet 5.5 | Same as Opus 5.5. | Costs more than Haiku 5.5; described as fast, capable and cost-efficient; no numeric figure. | Shared. |
| Claude Code, Claude Haiku 5.5 | Same as Opus 5.5. | Fastest and cheapest option; no numeric figure. | Shared. |
| Codex, GPT-6.2 Sol | Plan Codex allowance. Plus and Standard Business give five-hour estimates; weekly limits may apply. Pro plans have no five-hour limit. | 17 to 180 local messages per five hours on Plus and Standard Business (not fixed limits). | Explicit statement not found. Local messages and cloud chats share the plan allowance, and a model may become unavailable at its limit. |
| Codex, GPT-6.2 Astra | Same as Sol. | 6 to 50 local messages per five hours on Plus and Standard Business. | Same as Sol. |
| Codex, GPT-6.1 Terra | Same as Sol. | 35 to 285 local messages per five hours on Plus and Standard Business. | Same as Sol. |
| Codex, GPT-6 Luna | Same as Sol. | 350 to 3,000 local messages per five hours on Plus and Standard Business. | Same as Sol. |
| Antigravity, Gemini 4 Neon | Pro: five-hour refresh until the weekly limit is reached. Ultra: refreshed every five hours with the highest weekly rate limits. | not found; limits correlate with work done by the agent. | Gemini Models group, within shared Gemini quota, with its own weekly and five-hour limits. |
| Antigravity, Gemini 4 Carbon | Same as Neon. | not found | Gemini Models group. |
| Antigravity, Gemini 4 Hydrogen | Same as Neon; also on Free and Plus with a weekly quota. | not found | Gemini Models group. |
| Antigravity, Gemini 4 Argon | Same as Neon; leaving on November 30, 2026. | not found | Gemini Models group. |
| Antigravity, Gemini 3.8 Flash | All plans; Free and Plus access ends and model leaves on November 30, 2026. | not found | Gemini Models group. |
| Antigravity, GPT-OSS 120B | Free, Plus, Pro and Ultra (not Enterprise); leaving on November 30, 2026. | not found | Claude and GPT models group, with its own weekly and five-hour limits. |
| Antigravity, Claude Opus 5.5 | Pro (non-trial only), Ultra and Enterprise; selector lists Low, Medium, High and Thinking. | not found | Claude and GPT models group. |
| Antigravity, Claude Sonnet 5.5 | Pro (non-trial only), Ultra and Enterprise; selector lists Thinking. | not found | Claude and GPT models group. |

- **Codex extras:** Cloud tasks may use more of the allowance than local messages. Pro 100 and Pro 500 include twice their previous Work and Codex allowance; on Pro 200, only the lower allowance doubled. The overage rate for GPT-6.2 Astra and Sol is 3x through February 28, 2027, and 6x from March 1, 2027.
- **Antigravity extras:** Pro and Ultra plans can buy AI credits under a setting with options "Never" and "Always". Bring-your-own-key is not supported.

## What changed since 19 November

Compared against [the 19 November record](2026-11-19-coding-agent-model-evidence.md):

- **Artificial Analysis minutes per task:** The 19 November record (through a summariser) gives 132 minutes for Fable 5.2 at Max, 84 minutes for Sonnet 5.5 at Max, 66 minutes for Opus 5.5 at Max and 78 minutes for Haiku 5.5 at Max. The embedded data on 26 November gives 129.5, 86.8, 65.3 and 77.4 minutes. Every other recorded index, patch, codebase-question, minute and cost figure matches when rounded the same way.
- **Index heading and additional rows:** The 19 November record names "Coding Agent Index v2.1"; the page heading now carries no version number. The 26 November raw fetch exposes the Terminal-Bench component for every row plus rows absent from the 19 November record: Haiku 5.5 (Max) index (29.6), Astra at Low (35.6) and Medium (49.1), Sol at Low (37.2), Medium (45.4) and High (47.5), GPT-6.1 Terra (Max) (48.6), GPT-6 Luna (Max) in Codex (25.9) and twelve other agents, Fable 5.2 codebase questions at Low, High, Xhigh and Max, Hydrogen (60.2) and Argon (55.1) codebase questions, and Devin Fusion CLI (58.4). It is not known which rows appeared after 19 November and which the earlier summariser missed.
- **Terminal-Bench 4.1:** The top six rows recorded on 19 November match with their intervals. The 26 November raw fetch supplies effort and confidence intervals for Haiku 5.5 (max, 40.0% ± 3.6%), GPT-6 Luna (max, 15.2% ± 2.7%) and Gemini 3.8 Flash (high, in mini-SWE-agent, 18.2% ± 3.4%), plus rows absent on 19 November: Copilot Fusion (71.2% ± 2.9%, row updated 17 November), Gemini 4 Neon (61.2% ± 2.8%, row updated 20 November), Gemini 4 Hydrogen (56.4% ± 3.0%), Gemini 4 Argon (55.5% ± 2.8%) and GPT-6.1 Terra (53.3% ± 3.1%).
- **ReviewBench:** Opus 5.5 and Sonnet 5.5 scores match, with Sonnet 5.5 at default effort (95.6% precision, 43.9% recall) now recorded. Correction: the 19 November statement "The benchmark's maintainer did not verify the entries" does not appear on any ReviewBench page read on 26 November; the maintainer is GitHub, which also builds one of the reviewers it ranks.
- **Song and Kim and others:** Both papers are now read from full text. Song's "42% against 25%" on prose is document F1 (42.1% against 24.5%), and its models are Claude Opus 4.6, GPT-5.4 and Gemini 2.5, none in the current lineup. Kim and others' 17.2× and 4.4× figures are confirmed on 2025-generation models.
- **AA-Omniscience:** Fable 5.2 net scores (64 to 67) and the 4% lowest hallucination rates (Carbon at Medium, Argon at High) match. Clarification: the page's hallucination rate is wrong answers as a share of non-correct responses rather than of all questions; on that measure Fable 5.2 (Max) is 59.3% while the Gemini 4 rows with a full record are 8.5% to 14.4%; Carbon at Medium and Argon at High have only the rounded 4%.
- **Subjects absent on 19 November:** Vectara (24 November 2026), AA-LCR, Scale AI's original SWE Atlas QnA board, Scale AI Labs' judge post, Lexometrica, per-effort API speed and TTFAT, context windows, image support, list prices and subscription metering appear here for the first time.

## No public evidence found

- **House-style documentation and dated evidence records:** no public benchmark found.
- **Reading run ledgers, logs and tables:** no public per-model benchmark found.
- **C++ in a large existing codebase:** neither Artificial Analysis nor Terminal-Bench 4.1 publishes a language breakdown, and Scale AI's July SWE Atlas QnA covers Go, Python, C and TypeScript only.
- **Code review for most of the lineup:** no ReviewBench entry uses Fable 5.2, Haiku 5.5, any GPT-6.x model, any Gemini 4 model, Gemini 3.8 Flash or GPT-OSS 120B.
- **Judging against human labels:** none for Fable 5.2, Sonnet 5.5, any GPT-6.x model, any Gemini 4 model, Gemini 3.8 Flash or GPT-OSS 120B; no official JudgeBench, RewardBench 2, Judge Arena or LLMBar leaderboard was found for the current models.
- **File localization or code retrieval as a separate measure:** no per-model figure for the current lineup was found in search summaries (CORE-Bench, Agent Retrieval Bench and RepoNav/LocBench were not opened).
- **Source-grounded hallucination and long-document reasoning gaps:** Vectara covers only Opus 5.5, Gemini 4 Argon and GPT-OSS 120B; AA-LCR has no figure for GPT-6.2 Astra, GPT-6.2 Sol or any Gemini 4 model; Kaggle FACTS Grounding and Fiction.LiveBench could not be read; vendor system cards were not found as primary pages.
- **In-agent speed, Antigravity Claude limits and numeric quota weights:** no Artificial Analysis speed figure exists inside Claude Code, Codex or Antigravity; Antigravity's pages do not state context limits, max output, image support or prices for Claude models inside Antigravity; Anthropic and Google publish no numeric per-model quota weights or message counts.
- **Missing models and lower efforts on coding boards:** Gemini 3.8 Flash and GPT-OSS 120B have no Artificial Analysis Coding Agent Index row, GPT-OSS 120B has no Terminal-Bench 4.1 row, and most models have no row at lower efforts.

## Limits

These figures come from outside tasks in outside harnesses, read on 26 November 2026 without viewing rendered charts in a browser. Speed, context, image, list-price and subscription sections came through a page summariser rather than raw fetches, apart from the two quotations the lead re-fetched directly.

Artificial Analysis notes that benchmark methodology can evolve and that scores reflect specific evaluated agent variants and execution configurations rather than timeless rankings. Several boards rely on model judges or classifiers (Claude Sonnet on Artificial Analysis Terminal-Bench audits, Claude Sonnet 5 on ReviewBench, Claude Opus 4.5 on Scale AI's SWE Atlas QnA, HHEM-2.3 on Vectara and another LLM on AA-LCR), and both GitHub and Scale AI Labs build products in the area they evaluate. Pay-per-token API costs and list prices are not consumer subscription billing, and prompt cache hit rates vary by provider routing. Public figures show which models and effort settings to test or avoid; they do not measure performance on this repository's own C++, Python, review or documentation work.
