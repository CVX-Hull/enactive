---
owner: lead
review_trigger: Player host, context, model, control redesign or a new performance claim
status: active
---

# Responsive gameplay: context and control evidence

Cutoff: October 22, 2026. Searches prioritized 2026/2025 primary literature and
official implementation guidance, then followed references. Two independent
research slices read the named method/results/limitations sections through web
HTML/PDF; no local PDF corpus or benchmark replication is claimed. Recent
preprints are provisional. This is a targeted review, not an exhaustive survey
or model leaderboard. [Brief060](changes/060-responsive-player.md) owns the
proposed implementation consequences and local trace findings.

## Evidence and transfer limits

| Primary source and date | Reading scope; finding | What we can use and cannot infer |
| --- | --- | --- |
| [CodeHack: Up and Down the Abstraction Ladder](https://arxiv.org/html/2609.31076v1), September 25, 2026 | §§2–5, discussion, appendix A. Fourteen-model NetHack comparison; closed-loop code skills plus primitives improve the measured performance/cost frontier. | Strong roguelike motivation for fewer model decisions and primitive fallback. Human-built library and structured NLE observations do not establish autonomous skill discovery, our wall-clock performance or cross-game qualification. |
| [RTC](https://arxiv.org/html/2506.07339v2), June 9 / December 5, 2025 | Algorithm, timing, experiments and conclusions. Overlaps inference with committed continuous execution. | Transfer overlap and committed-prefix accounting. Action inpainting is a trained motor-policy technique, not a keyboard batching algorithm. |
| [REMAC](https://arxiv.org/html/2601.20130v1), January 27, 2026 | Method, deployment, experiments and appendix G. Asynchrony also creates observation/action mismatch within chunks. | Fresh local feedback matters beyond smooth boundaries. Requires finetuning and a delay envelope; its delay metric excludes observation latency. |
| [Acting While Understanding](https://arxiv.org/html/2606.15285v1), June 13, 2026 | §§3–5, runtime and ablations. Semantic caching needs current feedback and delay-aware training. | Cached plans alone do not produce responsive control; server throughput is not episode throughput. No directly reusable policy. |
| [World Action Models in Real Time](https://arxiv.org/html/2608.01880v2), August 3 / 11, 2026 | Deployment methods, temporal definitions and task discussion. Alignment precedes smoothing; abrupt changes can invalidate guidance. | Measure camera/observation through dispatch; invalidate unsuitable future actions. Do not interpolate discrete commands or preserve a harmful suffix. |
| [PACT-VLA](https://arxiv.org/html/2610.28019v1), October 20, 2026 | Method, experiments, appendices B/C and selector analysis. Later pre-commit observations rank candidate chunks. Verification has real hardware-dependent cost; shortest-delay LIBERO averages slightly worsen. | Candidate preparation may overlap, but selected action applicability still needs current evidence. Policy-consistency scores are not task success or authority checks; no speculative native inputs. |
| [Speculative Actions](https://arxiv.org/html/2510.04371v2), October 5, 2025 / April 23, 2026 | Assumptions, safety and implementation/results. Gains depend on reversible or sandboxed effects and commit validation. | Limit speculation to computation, retrieval and candidate preparation. CDDA's real inputs cannot be rolled back. |
| [LeRobot RTC](https://huggingface.co/docs/lerobot/main/rtc), accessed October 22, 2026, mutable main | Modes, scheduling, admission and waiting guidance. Configuration support is distinct from measured overlap/freshness. | Useful admission discipline, not a reason to adopt a robot runtime or claim a latency guarantee. |
| [OSWorld-Human](https://proceedings.mlsys.org/paper_files/paper/2026/file/5edb57c05c81d04beb716ef1d542fe9e-Paper-Conference.pdf), MLSys 2026 | §§3–6. Detailed timing of two agents on 39 tasks; planning/reflection/judging and growing context are substantial costs. | Measure roles, avoidable steps and whole outcomes. Dated agents, hardware/provider sensitivity and limited timing sample prevent extrapolating exact latency to our models. |
| [Effective context engineering](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents), September 29, 2025 | Anatomy, retrieval, compaction and note-taking. High-signal working context and reconstructable references. | Official engineering guidance, not a controlled game experiment. Preserve constraints and unfinished work when reducing context. |
| [Writing effective tools](https://www.anthropic.com/research/writing-tools-for-agents), September 11, 2025 | Evaluation, workflow-oriented tools, meaningful results and token efficiency. | Compact decision views and actionable errors are appropriate. Keep operational IDs required for authority/evidence; format gains require actual model evaluation. |
| [Advanced tool use](https://www.anthropic.com/research/advanced-tool-use), November 24, 2025 | Programmatic calls, search and applicability. Software can filter data and run deterministic dependent calls. | Automate plumbing. Our roughly twenty stable tools do not inherently need a tool-discovery service or execution framework. Provider internal evidence is not an independent comparison. |
| [AutoCompact](https://arxiv.org/html/2610.02163v1), October 1, 2026 | §§2–3.4. Trains compaction and continuation together on coding tasks. | Test whether a successor acts on retained obligations, not summary coverage alone. Trained-checkpoint gains do not transfer to a prompt-only summarizer. |
| [ARC](https://arxiv.org/html/2607.25066v1), July 27, 2026 | Method, guarantee, evaluation and limits. Bounded working context with addressable exact history. | Existing archive already supplies exact recall. Valid addresses do not guarantee correct retrieval choice or reasoning; no new history database needed. |
| [Agent JIT](https://arxiv.org/html/2605.21470v1), May 20, 2026 | §§3–6, appendix H. Reuses semantic tools and schedules work on five web applications. | Reduce deterministic model round trips. DOM assumptions, offline synthesis and multiple isolated browser workers do not transfer to parallel input on one game. |
| [Sleep-time Compute](https://arxiv.org/html/2504.13171v1), April 17, 2025 | §§3–7. Anticipatory computation depends on predicting reusable future queries. | Prioritize likely useful bounded jobs; count stale work and total cost. Does not justify a continuously polling/reflection model or guaranteed improvement. |
| [OpenAI session memory](https://developers.openai.com/cookbook/examples/agents_sdk/session_memory), accessed October 22, 2026 | Trimming and summarization examples/tradeoffs. | Existing SDK patterns can bound owned application context; trimming loses history and summaries add loss/latency. They do not grant control over the lead's coding agent's injected host context. |
| [OpenAI latency guidance](https://developers.openai.com/api/docs/guides/latency-optimization), accessed October 22, 2026 | Fewer-request guidance. | Combine deterministic work where intermediate model judgment is unnecessary. An SDK/provider change is not automatically faster and introduces configuration/cost choices. |
| [Codex event-export issue44126](https://github.com/openai/codex/issues/44126), September 9, 2026, and [current event implementation](https://github.com/openai/codex/blob/main/codex-rs/core/src/mcp_tool_call.rs), accessed October 22 | Issue and result/event paths read. Persisted events can contain a text-serialized MCP envelope while the original result goes to the tool/model path. | Local forwarded-output inspection confirms no nested MCP envelopes in260 parsed JSON text blocks. The earlier inference of model-visible nesting is retracted; issue/current-main versions do not prove exact installed-version parity. Measure the actual evidence layer before assigning model costs or changing framing. |

Dates with two entries distinguish first version and the inspected revision.
Publication venue labels do not establish replication. No paper supplies a
universal human-perceived latency threshold for CDDA-class games.

## Cross-check against existing design

| Prior artifact | Retain | Gap or correction |
| --- | --- | --- |
| [Tiered gameplay](research-tiered-gameplay.md) | Optional tiers, feedback and empirical routing | Slow reasoning still stalls the user in a turn-based game; enforce configuration responsiveness, not engine-clock safety alone. |
| [Asynchronous reflection](design/asynchronous-reflection.md) | Software jobs/feedback, bounded advice, lead outside play | Actual idle polling and host context must be measured; a designed background path does not prove useful overlap or efficient wakeup. |
| [Memory architecture](research-memory-architecture.md) and [representations](research-memory-representations.md) | Source-linked facts/procedures/Work, uncertainty, revision and exact recall | Historical code-baseline tables are historical. Add bounded working presentation and actual fresh continuation without another memory store. |
| [Organic discovery](design/organic-discovery.md) and [mixed input](design/mixed-input.md) | Primitive foundation, revisable abstractions and current feedback | Neither a larger hand-built menu catalogue nor blind key batches solves general discovery or pace. |
| [Structured tools051](changes/051-structured-player-tools.md) | Existing SDK, one writer, stable requests, retained evidence | Real host results are not as concise as intended; distinguish canonical machine records from actual model-facing representation. |
| [Evaluation](evaluation.md#latency-budgets-for-interactive-play) | Separate clocks, no inference from ACK alone | Closed host traces now supply scoped call gaps/tokens; isolated inference and full useful-progress cadence remain unmeasured. |

## Engineering judgment and uncertainty

The architecture is directionally consistent with recent work. Its execution
host, working context, result presentation and useful local execution do not yet
demonstrate acceptable responsiveness. Prioritize those concrete gaps over a new
memory framework or mandatory model hierarchy. Smaller/faster models, lower
reasoning effort, caching and learned procedures are candidates to measure,
not independent guarantees. Do not use a slow hot-path configuration merely
because it reasons well; useful overlap must satisfy the same quality and latency
requirements. Event-driven software waiting and automatic receipt attribution
leave model work for interpretation, planning and revisable learning.

Research refresh is triggered by redesign or a new performance claim. Keep
source/version/read scope and contrary evidence with each changed conclusion;
do not refresh current guidance by advancing a date alone. GitHub owns action
items; the brief links their owners and acceptance obligations.

## October23 executable-policy follow-through

The [new review](research-executable-policies.md) extends the abstraction question
from existing hand-authored skills to player-authored executable routines. It
starts from fresh recent searches, includes October19–20 evidence and explicitly
cross-checks the prior memory/tiered design. Current procedure/2 is advisory;
local branches/loops learned by the player require an additional declared runner
and artifact-update contract. Organic adoption and useful cadence stay coupled.
