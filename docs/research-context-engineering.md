---
owner: lead
review_trigger: Player context, tools, memory, model configuration or a new performance claim
status: active
---

# Context, prompts and ergonomics for fast gameplay models

Research cutoff: **October 26, 2026**. The user's direction is to make faster,
less flagship gameplay models effective through better context and interfaces.
This review informs [#251](https://github.com/CVX-Hull/enactive/issues/251) under
[#164](https://github.com/CVX-Hull/enactive/issues/164). It does not implement a
context policy, select a new serving model or qualify gameplay responsiveness.
The mandatory generic Pi host and existing execution authority remain unchanged.

The [30 October spatial-grounding follow-up](research-spatial-grounding.md) separates
visual detail, camera/reference-frame reasoning and propagated task state using
new primary research and actual gameplay errors. It owns the later focused candidate
judgment; the source-bound measurements below retain their original date/scope.

## Conclusion and limits

Treat context as part of the player interface: give the model the information
and valid choices needed for its **current decision**, with exact older evidence
available on demand. Favor a compact stable core, a fresh decision packet,
selectively retrieved procedures and recoverable history. Software should own
mechanical bindings and bookkeeping; the player still owns interpretation,
applicability, goals, evidence selection and learning. This is an engineering
recommendation, supported by the evidence below, not a demonstrated speedup.

Smaller models can benefit substantially from examples and familiar tool schemas,
but correct formatting does not establish correct decisions. Meta-Tool's small-model
study is mostly single-turn; PA-Tool's schema results depend on the tested models
and include abstention tradeoffs. Neither establishes independent CDDA competence.
[Meta-Tool](https://aclanthology.org/2026.findings-acl.492/),
[PA-Tool](https://aclanthology.org/2026.acl-long.948/).

Do not equate better context with longer context, or compression with improvement.
Continuous Context Management reduced input usage but lowered success for three
of four inference-only terminal agents. Bud's coding benefit disappeared with a
session time limit because summarization itself was slow. These are direct
counterexamples to optimizing token count in isolation.
[CCM](https://arxiv.org/html/2609.35540v1),
[Bud ContextCompact 2.0](https://arxiv.org/html/2610.25516v1).

The deployment target is a **fast, sufficiently capable complete player**, not
a parameter-count class. Less flagship need not mean a tiny dense model or a
short context window. Serving route, vision, tool serialization, reasoning mode,
output length, cache behavior and recovery all affect the result. Better context
can reduce avoidable burdens; it cannot guarantee missing visual, programming
or planning capability. The SLM position paper motivates specialization but is
an argument, not a controlled demonstration that arbitrary agents can be replaced.
[Belcak et al., revised September 2026](https://arxiv.org/html/2506.02153v3).

## Review method

The review began with current-year and late-2025 searches across arXiv, ACL
Anthology, conference proceedings, original research sites and official provider
documentation, then followed references for foundations. Central methods,
experimental setups, ablations and limitations were read in full-text sections;
the tables record the scope. Recent preprints, vendor guidance and established
conference papers have different evidential weight. No benchmark was replicated,
no exhaustive or current-SOTA claim is made, and unavailable or abstract-only
leads are not used as experimental support.

Public PDFs and extracted text are retained project-locally under
`.runtime/research-context-2026-10-26/`. The existing literature skill's downloader
and extractor were used, with installed `pdftotext`/HTML fallback and no dependency
installation. Extraction flattens tables and mathematics; claims below do not
depend on reproducing unverified table arithmetic. The official CompactionBench
PDF was read through the web tool after its direct local download failed.
The corpus manifest distinguishes that failure from reading access. Mutable
official pages were checked on the cutoff date; their model-specific applicability
still needs verification before a later run.

The broader research requested after grooming is separate from #251's two-hour
discovery appetite. Issues own subsequent scope and fit; this document is not
another execution backlog or permission to spend on model experiments.

## What the current player actually receives

Inspected source: `2de297a967d0189526a839581fb19e51638b7f84`. The
[host](../tools/player_host/host.mjs) starts from explicit context plus optional
MCP instructions and the frozen user mission. It loads the selected live MCP
schemas, runs tools sequentially, retains text/reasoning/tool pairing, and
projects only older image pixels under the declared image allowance. It has no
text compaction or model-specific context policy. Source details belong in the
[player component](components/player-interface.md), not this research account.

Actual run009 request bodies establish the following baseline:

| Lane | Request1 | Request60 | Meaning and limit |
| --- | --- | --- | --- |
| System context | 41,270 characters; 5,378 whitespace words | Unchanged | Character/word counts are not tokenizer counts. |
| Tools | 16; compact serialized definitions 50,581 bytes | Unchanged | A stable schema prefix already exists; smaller is not automatically clearer. |
| Recorded text parts | 45,811 bytes | 427,039 bytes | Growing history; not a measurement of model attention. |
| Constructed request body | 97,095 bytes | 3,829,339 bytes | Includes serialization/images; not wire bytes or upload time. |
| Reported total input | 27,078 tokens, uncached | 189,701 tokens: 188,288 cached plus1,413 uncached | This serving route's usage, not a universal tokenizer or effective-context limit. |

The selected model had a large declared window. The same unmodified workload
would consume substantial headroom in a smaller window; that is a capacity
consideration, not proof that context caused any particular mistake.

The [published run009 evidence](acceptance/2026-10-25-program-breadth.md#009-program-assisted-useful-lighting-and-normal-ending)
shows a useful learned four-input local application, ordinary final completion
under its original root, and normal Save/owned exit/Finish. The matching browser
intervals were267.135s from first item-list display to bright display and49.670s
from phone submenu to bright display. The local program tool interval was889.872ms;
the exact useful frame's capture-to-DOM proxy was141ms. These are distinct lanes,
not interchangeable useful-decision clocks or a causal comparison.

Acquisition and recovery included SDK schema refusals28/29 before MCP dispatch,
an unrelated-support memory refusal30, an open-prompt refusal32, omitted input
modifiers34, unavailable parent35, explicit retrieval36 and reauthoring37, then
another open-prompt refusal40. The SDK refusals appear in subsequent retained
provider histories rather than `tool-start` events. Missing tool-start is not
evidence that the model made no tool attempt. This gives #251 concrete cases;
it does not establish an executor defect or isolate inference, upload or cache cost.

Existing authoring projections already derive canonical metadata. Existing
`enactive_context`, `enactive_detail`, source reads and indexed advice already
provide progressive access. The current gap is how economically a less capable
player can recognize, select and use these facilities, not the absence of a
memory store or generic program executor.

## Evidence: context selection, memory and compaction

Each row separates the source's result from our transfer judgment. “Read” means
the named full-text sections, not every reference or appendix. Quantitative
headlines are deliberately not treated as expected gameplay gains.

| Source / status | Reading scope and evidence | Transfer and important limitation |
| --- | --- | --- |
| [Context Compression for LLM Agents](https://aclanthology.org/2026.emnlp-main.2396/), Yifei Wang et al., EMNLP2026; survey | Taxonomy, failure analysis and evaluation sections. Separates compression target/mechanism/control and errors before compression, information loss during it, and access failures afterward. | Useful diagnostic taxonomy; a survey does not establish an optimal policy or effect size for this player. |
| [Context Length Alone Hurts LLM Performance Despite Perfect Retrieval](https://aclanthology.org/2025.findings-emnlp.1264/), Yufeng Du et al., Findings EMNLP2025; read | Synthetic construction, experiments and limitations. Problem-solving can degrade with length despite retrieval checks. Five models/four tasks and missing setting combinations limit scope. | Test effective usable context, not merely whether a fact can be retrieved or a prompt fits. Synthetic padding does not predict our gameplay effect size. |
| [How Memory Management Impacts LLM Agents](https://aclanthology.org/2026.acl-long.27/), Zidi Xiong et al., ACL2026; read | Addition/deletion policies, experience-following experiments and limitations. Accumulated flawed experience and evaluator quality affect long-run behavior. | Preserve fallible status, provenance and negative evidence; retrieval frequency alone is not truth. Do not implement an automatic forgetting rule from one benchmark. |
| [ACE](https://arxiv.org/html/2510.04618v3), Qizheng Zhang et al., October2025/March2026 revision; read | §§3–5 and reflection/cost appendices. Incremental playbook updates avoid repeated full rewrites; AppWorld/domain results and reflection ablations support the mechanism. | Prefer bounded, source-linked updates over recurrently rewriting all memory. No universal long-playbook rule: results depend on task and reflection quality; some tasks need little added context. Our current procedures/advice already cover part of this role. |
| [Self-Compacting Language Model Agents](https://arxiv.org/html/2606.23525v2), Tianjian Li et al.,2026; read, [Apple NeurIPS listing](https://machinelearning.apple.com/research/self-compacting-language-agents) | Methods, math/search evaluation, trigger/tool ablations and limitations. A compaction tool plus a timing rubric works better than relying on unprompted self-management in tested settings, including small Qwen models. | Test triggers at completed subtasks and protect active derivations. It is inference-time evidence, but neither a game experiment nor proof a weak player can summarize every required obligation. |
| [Bud ContextCompact2.0](https://arxiv.org/html/2610.25516v1), Jithin VG and Ditto PS, October18,2026; recent preprint, read | Recall experiments, coding study, threshold study and time/cost discussion. Recall uses1.2B/9B models; end-to-end coding uses a27B reasoning model. Coding gains disappeared under the45-minute condition; summaries took a median161s. The8B threshold study often never compacted. | Measure whether a trigger fires and whether summary wait defeats the benefit. Recall scores, unconstrained-time results and a small model that exits early cannot establish useful fast interactive compaction. |
| [Continuous Context Management](https://arxiv.org/html/2609.35540v1), William Hoy et al., September28,2026; recent preprint, read | Inference-only TerminalBench-2, trained WebShop/Endless Terminals, capability/serving limitations. Per-turn memory reduces prompt size but hurts most tested inference-only agents; caching can make full history cheaper. Small-model gains use GRPO/full-history distillation and vary by size/task. | Strong negative baseline against default per-turn summarization. Training results cannot be obtained by adding a summarization prompt. Count output, lost task success and cache effects. |
| [CompactionBench/APEC](https://www.microsoft.com/en-us/research/wp-content/uploads/2026/10/CompactionBench_preprint.pdf), Banruo Liu et al., October2026; preprint, read | Production characterization, dependent-task benchmark, progressive background compaction and evaluation. Synchronous compaction disrupts prefix reuse; studied frontier coding agents differ from small gameplay models. | Evaluate cache rebuilding and foreground stalls as well as summary quality. Background summarization has its own actor, resource and staleness costs; it is not automatically admitted here. |
| [TokenPilot](https://aclanthology.org/2026.findings-emnlp.899/), Buqiang Xu et al., Findings EMNLP2026; read | Ingestion, eviction, cache-preserving design, benchmark/ablation and limitations. Combines stable-prefix handling, recoverable output reduction and utility-based delayed eviction. | Structural reduction before semantic summarization is a candidate. Its estimator and homogeneous task streams limit transfer. Never remove our authority/freshness fields merely because another system calls metadata volatile. |
| [Recursive Language Models](https://arxiv.org/html/2512.24601v3), Alex L. Zhang, Tim Kraska and Omar Khattab, May2026 revision; read | §§2–5, limitations and negative results. Code-addressable context plus recursive model queries supports long-context tasks; weak coding models struggle, prompts do not transfer unchanged, and sub-call costs can expand. The8B result includes training. | Reuse our exact addressable history and deterministic filtering. Do not adopt a recursive REPL/model hierarchy or infer trained-small-model gains for our unchanged player. |

The apparent disagreement is informative. ACE warns that aggressive brevity can
erase valuable knowledge, while long-context studies warn that irrelevant volume
hurts. These findings address different information distributions. The objective
is **sufficient relevant information with recoverable detail**, not minimum or
maximum tokens. Retrieval quality, reasoning over retrieved evidence and future
access to omitted evidence are separate responsibilities.

## Evidence: prompting and agent-computer ergonomics

| Source / status | Reading scope and evidence | Transfer and important limitation |
| --- | --- | --- |
| [Meta-Tool](https://aclanthology.org/2026.findings-acl.492/), Sachin Kumar, Findings ACL2026; read | Methods, documentation/example/hypernetwork ablations, error analysis and limitations. Few-shot examples and documentation help the tested3B Llama; the hypernetwork adds no measured benefit. Residual syntax versus semantic failures differ by task. | Try a small clean example set before a new adaptation subsystem. One model family, small samples, English and single-turn evaluation; its latency headline compares different deployment paths and does not qualify multi-turn gameplay. |
| [PA-Tool](https://aclanthology.org/2026.acl-long.948/), Jonggeun Lee et al., ACL2026; read | Naming alignment, model/benchmark comparisons, constraints and limitations. Familiar names can reduce invented components. Constrained generation can remove format errors yet worsen some no-applicable-tool decisions. | Test naming, shallow variants and abstention separately. Do not introduce per-model alias/compatibility trees; any selected interface change must migrate the one current contract. These older model-family results are not a current DeepSeek guarantee. |
| [When Tools Fail/ToolMaze](https://arxiv.org/abs/2606.05806), Dongsheng Zhu et al.,2026; preprint, read | Generated dependency tasks, explicit/implicit failures, prompting and recovery analysis. Failure-aware prompting helps but does not eliminate cascading recovery errors. | Include refusal and wrong-result recovery, not just clean calls. Generated DAGs do not establish ordinary game discovery or our native control behavior. |
| [MM-ToolSandBox](https://arxiv.org/abs/2607.11818v2), Kaixin Ma et al., August2026 revision; preprint, read | Stateful visual tasks, progressive observations, registry ablations and failure analysis. Image extraction can fail despite otherwise correct workflow; larger tool registries do not yield a uniform success trend. | Score visual grounding separately and preserve the newest relevant image. Synthetic visual domains do not justify automatic OCR, aggressive resizing or a CDDA menu catalogue. |
| [SWE-agent](https://arxiv.org/html/2405.15793v3), John Yang et al., NeurIPS2024; foundational, read | ACI design, interface ablations, behavior and limitations. Search/edit/result design changes agent effectiveness without changing weights. | Design for recognition and concise actionable feedback, not a human API manual. Coding-domain tools and2024 model limitations are not current VLM or game benchmarks. |
| [GEPA](https://arxiv.org/abs/2507.19457), Lakshya A. Agrawal et al., ICLR2026; read | Reflective prompt evolution, held-out tasks, optimizer/search-cost and robustness appendices. Optimizes textual programs using execution traces without updating target weights. | Offline prompt search is a candidate after a reliable evaluator exists. Include teacher/search cost and validation selection; benchmark gains do not promise a faster hot path or justify unbounded prompt evolution. |
| [Optimizing Instructions and Demonstrations](https://arxiv.org/abs/2406.11695), Krista Opsahl-Ong et al., EMNLP2024; foundational, read | MIPRO instruction/demo search, experiments and limits. Demonstration selection matters; instruction and grounding effects are task-dependent. | Compare a few diverse protocol examples with explicit rules; extra examples consume prompt budget. No need to install a prompt-optimization framework before establishing a baseline. |
| [When Punctuation Matters](https://aclanthology.org/2025.findings-emnlp.1109/), Mikhail Seleznyov et al., Findings EMNLP2025; read | Prompt-format comparisons over52 instruction tasks, model families, methods and limitations. Robustness varies with format/model/distribution. Some remedies require weight updates. | Hold out formatting and composition variants. A selected prompt's gain is not robust if minor harmless presentation changes defeat it; LoRA improvements are not prompt-only evidence. |
| [When Reflective Prompt and Skill Optimization Helps](https://arxiv.org/html/2610.26020v1), Andrea Giummarra et al., October19,2026; recent preprint, read | Two locally served reasoning models, optimizer gates, QA/math outcomes and extensive limitations. Effects differ by task; a validation-selected verbosity change need not improve test quality. Reported math gains include answer completion/format alignment. | Do not interpret optimization as newly acquired reasoning. Different serving stacks, small selection sets, reused study-level test identifiers and some timeout/recovery lanes limit causal and transfer claims. |
| [Small Language Models are the Future of Agentic AI](https://arxiv.org/html/2506.02153v3), Peter Belcak et al., September2026 revision; position, read | Position, alternative views, adoption barriers and conversion outline. Argues many repeated agent subfunctions can use smaller specialized models. | Supports investigating the user's direction; it is not an end-to-end comparison proving a tiny general player suffices. A heterogeneous-model system is an option, not a prerequisite. |
| [AgentDojo](https://arxiv.org/html/2406.13352v3), Edoardo Debenedetti et al., NeurIPS2024; foundational, read | Stateful task/attack construction, utility/security evaluation and defense limits. Tool-returned data can redirect a model; prompt defenses have utility tradeoffs. | Keep observed text, retrieved advice and examples distinct from operator instructions. Existing software authority checks stay outside model judgment; a shorter prompt is not a security boundary. |

## Current official guidance and portability

These are implementation contracts or vendor experience, not controlled CDDA
evidence. “Current” here means checked on the cutoff date.

| Source / read scope | Usable guidance and boundary |
| --- | --- |
| [Anthropic context engineering](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents), anatomy/retrieval/compaction/notes | Select high-signal context and reconstructable detail. Its examples and frontier-agent experience do not establish an optimal small-model budget. |
| [Anthropic tool ergonomics](https://www.anthropic.com/research/writing-tools-for-agents), workflow tools/evaluation/results/errors | Test meaningful results, descriptions, names and held-out outcomes. Consolidate deterministic plumbing without silently making the player's semantic decisions. |
| [OpenAI prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering), roles/model choice/examples/relevant context | Precise instructions, diverse examples, pinned versions and evaluations. Recommendations depend on model type/snapshot; OpenAI message roles are not automatically another endpoint's contract. |
| [OpenAI reasoning guidance](https://developers.openai.com/api/docs/guides/reasoning-best-practices), model distinction/prompting | Simple explicit goals can suit reasoning models; a request for narrated step-by-step reasoning can be unnecessary. Its o-series framing is not a universal prompt or a prescription for every current model. |
| [OpenAI latency guidance](https://developers.openai.com/api/docs/guides/latency-optimization), output/work/request choices | Avoid unnecessary generation and deterministic round trips. Our useful visible outcomes and exposed waits remain primary, not API completion alone. |
| [DeepSeek tool calls](https://api-docs.deepseek.com/guides/tool_calls/), call/result/history and strict mode | Direct API strict mode is beta with a particular base URL and supported schema subset. Do not assume DeepInfra inherits that support or that strict JSON implies correct action selection. |
| [DeepSeek thinking mode](https://api-docs.deepseek.com/guides/thinking_mode/), effort/history/parameter behavior | The direct API currently maps requested medium to high and documents mode-specific ignored sampling parameters/history requirements. This does **not** attest what DeepInfra did in009. Verify the exact endpoint rather than treating effort labels or OpenAI compatibility as universal semantics. |
| [Qwen3 concepts/template](https://github.com/QwenLM/Qwen3/blob/main/docs/source/getting_started/concepts.md), tool-message template/context concepts | A checkpoint's chat template/tool serialization is part of its model interface. Mutable main is not an immutable checkpoint or proof of the selected serving stack's parity. |
| [DeepInfra prefix caching](https://docs.deepinfra.com/chat/prompt-caching), operation/usage/best practices | Automatic matching of repeated prefixes favors stable leading context/tools. Cached input is still context the model must use correctly; cache share does not prove useful latency. |
| [DeepInfra retention](https://docs.deepinfra.com/chat/prompt-cache-retention), options/model applicability | Explicit paid retention is separately model-dependent; schema presence is not support. The checked table does not list our selected DeepSeek route. Recheck before any future use. |
| [DeepInfra gzip](https://docs.deepinfra.com/request-compression), supported request/streaming behavior | Standard request compression is available. Its utility depends on actual upload contribution and compression CPU; it does not reduce the model's semantic context. |

Preserve required tool-call/result pairing and reasoning-history fields for the
**selected route**. A generic instruction to delete all thinking/history can
break a provider contract. Verify actual serialized requests and schema support
with the existing host seam before any changed live configuration. This is not
permission to send arbitrary internal reasoning to another provider.

## Proposed context design to test

This is a proposed presentation, not a new protocol or implemented architecture.
Use existing Pi hooks, player projections, snapshot/detail handles, memory and
evidence storage. Do not add another planner, executor, context database or
mandatory model tier merely to resemble a paper.

| Layer | What belongs there | What must not happen |
| --- | --- | --- |
| Compact stable core | Role/goal ownership, non-negotiable authority/unknown-delivery rules, ordinary-input foundation, concise tool contracts and a few generic protocol examples. Keep stable leading bytes where practical. | A giant engineering manual, repeated warnings or a hand-written game strategy. Do not remove essential rules to hit a token target. |
| Fresh decision packet | Current goal/progress, actual selected observation/image, phase, unresolved delivery/effects, remaining mission versus local scope, next collection/choice information and relevant invalidators. | A guessed budget, old screenshot presented as current, automatic Resume/reconciliation or a derived candidate masquerading as authority. |
| Relevant memory | Small task-relevant set of fallible procedures/claims, applicability, invalidators, status, sources and explicit eligible parent/revision handles. | Automatic promotion of advice to fact, imported old-world inventory, attention inferred from storage, or silent support selection. |
| Exact detail/history | Full retained originals, code, results and images available through existing deliberate reads; active obligations and latest result group remain recoverable. | Destructive forgetting, phantom read receipts, rewritten original requests, broken tool pairing, or rejuvenated authority after compaction/restart. |

Give the player recognition tasks where software already knows mechanical facts:
what happened, what is still uncertain, which exact selected record is available,
and where the needed detail can be read. A current parent handle returned by a
write and one qualified through a context read may differ under today's contract;
test that friction before changing eligibility. Software may format known facts,
but must not invent applicability, a successful effect or support the player did
not select. Schema validation and semantic/evidence refusal are separate cases.

For model-facing tools, compare clear shallow authoring forms and concise
branch-specific errors against the current union. Keep one canonical producer
and one current contract; do not create a permissive small-model backdoor.
Measure all schema/description bytes and the cost of a larger tool registry.
With only16 selected tools, dynamic tool search is not automatically worthwhile.
First improve the descriptions/examples and the actual confusing branches.

Use a bounded set of **protocol** demonstrations: successful authoring/use,
unavailable parent followed by deliberate retrieval, a known unsubmitted refusal,
unknown delivery collected without replay, and a healthy yield to ordinary
image-informed input. Examples must be clearly fictional and never usable as
current evidence. Do not teach the player's chosen item, key sequence or game
solution. Hold out labels, row order, formatting and phase combinations.

Prefer concise externally necessary decisions over mandatory narration per key.
Do not impose one universal chain-of-thought prompt, output cap or reasoning
effort across model families. Too little output may truncate valid program/tool
arguments; too much can spend the latency budget on avoidable explanation.
Freeze and evaluate the complete prompt/template/decoding combination.

## Memory, compaction, vision and cache decisions

Start with relevance and structural reduction. Keep durable procedure knowledge
distinct from current episode facts, unresolved effects and pending Work. Use
bounded query/byte budgets, exact read handles, explicit uncertainty and known
negative examples. The existing memory system already has these seams. Measure
whether the player retrieves a needed record and can continue correctly; an
accurate summary or retrieval hit alone is insufficient.

Do not enable per-turn summarization by default. If history pressure is observed,
compare completed-segment structural eviction against a bounded summary with
an exact recoverable tail. Protect unfinished derivations, active phases, pending
tool results, original unknown dispatches and cleanup obligations. Test that a
fresh continuation can act correctly and retrieve omitted evidence. A summary
is fallible data, never reconstruction of a live lease. No unsupported context
transformation should be slipped into an existing frozen run.

Cache-aware context reduction is a joint optimization. A large stable prefix
may be cheap to ingest repeatedly yet still distract the model; a small prompt
may require uncached generation and lose useful evidence. Preserve stable tool
order/core first and append fresh state, rather than moving timestamps into the
prefix. Do not blindly delete/normalize identity, source or freshness metadata.
Count cold/warm calls, summary generation, cache rebuilds, output/reasoning,
host projection/serialization/trace work and actual display correspondence.

For vision, retain the latest relevant native frame and preserve its identity
and geometry. Compare image-history choices only with a grounding test: older
images can confuse a small VLM, but removing the needed previous observation can
also break comparison. Cropping/resizing/OCR, if selected later, must preserve
coordinates/provenance and expose uncertainty; OCR is not hidden engine truth.
Program-view currently has structured visible state without pixels. Image-only
conditions must return to the deciding player rather than become invented fields.

A stronger model may help produce or critique generic examples offline. That
does not require a flagship call on every action. Prompt optimization and
distillation need verified targets, held-out situations, teacher/search cost and
retraining/maintenance accounting. Fine-tuning, KV compression and trained
compactors are deferred choices, not benefits available through a prompt edit.

## Evidence matrix and proposed experiment order

| Decision hypothesis | Supporting and limiting evidence | Confidence / next test |
| --- | --- | --- |
| Reduce mechanical authoring burden before adding model power | Actual009 refusals; Meta-Tool/PA-Tool/ACI evidence. Remaining semantic and visual errors may dominate after formatting is fixed. | Medium priority; no measured gain yet. Reproduce the exact failed/correct drafts, then evaluate model choices as well as acceptance. |
| Use selective task context rather than full growing transcript | Long-context degradation and memory-management studies. ACE shows useful detail must survive; retrieval itself can fail. | Medium; compare sufficient packets with exact detail access on held-out continuation tasks. |
| A few examples may be worth their prefix cost | Meta-Tool, MIPRO and official guidance. Format sensitivity, small samples and prompt-budget growth limit generalization. | Medium; compare no examples with a small diverse set, preserving total prompt/headroom and abstention. |
| Default aggressive summarization is premature | CCM/Bud negative results; SelfCompact supplies a more promising trigger; CompactionBench/TokenPilot add cache/system constraints. | High confidence to test before adoption; low confidence in a universal best trigger. |
| Higher cache share means faster useful play | Provider contract supports prefill reuse, but our97.4766% cached run still had long exposed waits; compression papers show tradeoffs. | Unsupported as a causal claim. Separate cache/output/quality and useful-effect endpoints. |
| A small fast model can replace the current complete player | Position papers and narrow tool studies motivate it; RLM/coding/vision/recovery limitations contradict a blanket claim. | Unproved. Exact checkpoint/template/provider and complete held-out behavior must qualify. |

The initial comparison should be small enough to interpret, rather than a
combinatorial model/prompt benchmark. Candidate arms below are **proposals**;
select and freeze the smallest useful subset in #251/#164 before execution.

| Experiment | Controlled change | Required outcome and failure checks |
| --- | --- | --- |
| Authoring/feedback | Current interface versus one minimal description/example/branch-feedback or authoring-form change | Correct intended record/use, explicit supports/parent, no phantom collection; malformed draft, unavailable parent and known-refusal recovery. Real SDK/MCP checks establish contract behavior, not that a model became better. |
| Decision packet | Current working presentation versus compact sufficient packet plus exact detail access | Correct next decision and continuation with unfinished obligations, stale state and missing information; report omissions and retrieval cost. |
| Examples | No added demonstrations versus a small diverse protocol set | Semantic success, valid abstention, transfer across labels/order/layout/format and exact model/template; no tactical demonstration leakage. |
| History | Current retention versus one completed-segment reduction policy, only if pressure is demonstrated | Useful continuation, exact source retrieval, no lost unknowns/Work, total foreground and cache-rebuild cost. Compare summary timing only if compaction actually triggers. |
| Model/configuration | One pinned fast candidate after the context baseline is interpretable | Actual vision/tool/history/effort support, output completeness, useful outcomes and tails. Do not change model, context, prompt and runtime together and attribute the result to one factor. |
| Continuous gameplay | Selected configuration in one coherent bounded player-owned mission | Useful learned full-workflow advancement, honest yield/recovery and normal Save/owned exit/Finish. No filler goals or standalone games for each technical checkbox. |

Separate development examples and retained009 tuning cases from held-out model
evaluation. Hold out situation and UI/format compositions, not merely random
rows from the same trajectory. Reusing a recorded screenshot to compare next
decisions cannot simulate the environment after a different action. Use real
component fixtures for contract negatives, truthful retained situations for
decision screening and separately frozen real play for actual effects.

Where sampling/serving varies, use repeated paired situations and report
uncertainty, failures and timeouts. A seed is not proof of provider determinism.
Cap optimizer/model calls and retain failed candidates; do not repeatedly tune
against a declared held-out set. A reward for parseability, short text or teacher
agreement alone can select a worse player.

Primary metrics remain sufficient visible evidence to meaningful visible effect,
exposed idle/stalls and yield→player reasoning→resumed useful progress, including
acquisition and rework. Record semantic success, grounding, program applicability,
schema refusals, authority/integrity failures and normal ending separately.
TTFT, model/API completion, tokens, cache hit share and call count are diagnostics.
Supported local program decisions may avoid repeated inference; cursor motion
and program `done` are not independent useful outcomes. Keep
[the existing latency definitions](evaluation.md#latency-budgets-for-interactive-play).

#164 retains its20 genuine useful decisions, p95≤2s new-decision→visible-effect,
unexplained routine stall≤5s and supported local useful effects≤500ms. This
research neither weakens those criteria nor fabricates a cohort from one small
success. #145 remains no-go until its actual readiness dependencies are met.

## Reconciliation with prior work and delivery ownership

The [responsive-gameplay review](research-responsive-gameplay.md) already called
for high-signal context, ergonomic tools and whole-player costs. The
[multi-rate review](research-multirate-agents.md) and
[executable-policy review](research-executable-policies.md) already support
local conditional execution with current feedback. The
[memory review](research-memory-architecture.md) already separates fallible
knowledge from execution authority. Retain those conclusions; this review adds
fresh small-model/schema evidence, October compaction counterexamples, explicit
provider-semantic checks and the current generic-host inventory. It does not
revive obsolete host options or repeat their proposals as implemented behavior.

| Existing owner | Research consequence / completion boundary |
| --- | --- |
| [#251](https://github.com/CVX-Hull/enactive/issues/251) | First bounded decision: exact authoring/recovery cases, one minimal context/ergonomic/configuration choice and an implementable assessment brief. Include fast-model compatibility and an example/task-packet option; no need to implement every research idea. Its discovery Done is not a latency claim. |
| [#164](https://github.com/CVX-Hull/enactive/issues/164) / [#143](https://github.com/CVX-Hull/enactive/issues/143) | Complete-player comparison, context/cache/output/quality accounting and truthful measurement lanes; no separate telemetry framework without a demonstrated gap. |
| [#177](https://github.com/CVX-Hull/enactive/issues/177) / [#178](https://github.com/CVX-Hull/enactive/issues/178) | Relevant source-linked procedures, explicit correction/parent access, negative experience and optional off-path candidates. No mandatory synchronous critic or automatic lesson promotion. |
| [#176](https://github.com/CVX-Hull/enactive/issues/176) / [#191](https://github.com/CVX-Hull/enactive/issues/191) | Preserve ordinary fallback and existing custody contracts; representation/vision changes need an actual missing seam. Portability is a design constraint, not a claim from another benchmark. |
| [#26](https://github.com/CVX-Hull/enactive/issues/26) | Own this currency review, contrary evidence, endpoint-specific prompting/history/effort assumptions and revisit at model/context/provider redesign or a new performance claim. |
| [#25](https://github.com/CVX-Hull/enactive/issues/25) | An additional persistent model tier stays conditional on measured net benefit. The user's fast single-player direction does not depend on that separate tier experiment. |

Select one improvement with a credible whole-outcome fit. If source contracts
change, migrate every affected caller/format/docs under S-MIGRATION, independently
review and run the appropriate protected PR/main lanes. A frozen run cannot be
quietly edited. This research starts no provider/game process, accesses no key,
changes no dependency or Save, and grants no replay or renewed runtime allowance.
