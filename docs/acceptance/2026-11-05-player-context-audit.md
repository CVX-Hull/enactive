---
owner: lead
status: historical
kind: measurement
date: 2026-11-05
scope: Source and retained-context audit of the main player at faca1d099a49bef8894be50b509ca00344f6cfe4 and the closed Alex two-day diagnostic
---

# Player context and testing responsibilities

The current deciding model receives experiment instructions and resource
countdowns alongside its game assignment and player guide. The Alex run shows
why that boundary needs correction. The actor reached 48h26m32s alive, repeatedly
provided basic care, abandoned replenishment with ample capacity, and ended
dehydrated. Its public explanations repeatedly prioritized reaching the clock
target and conserving requests. This single trajectory supports investigating
the instructions and visual/planning failures together. It does not isolate their
causal contributions. [Reviewed outcome](https://github.com/CVX-Hull/enactive/issues/164#issuecomment-6649915517)

The owner asked for a distinction between the player system and the scaffolding
used for current tests. An eventual player may continue without a run quota until
the user asks it to stop or it signals completion. This record audits the current
construction paths and recommends that responsibility boundary. It changes no
runtime or supported contract.

## Responsibility boundary

These are logical roles. Several currently share the same process or module.

| Role | Responsibility | Context it supplies or consumes |
| --- | --- | --- |
| Deciding model | Interpret observations, choose and revise goals, act, verify effects, author useful knowledge/programs, and report completion or inability to proceed | User objective, actual observations, available tools, relevant player knowledge and current control state |
| Player system | Run the model/tool loop, manage context and player memory, execute bounded local programs, preserve game continuity and communicate user control | Working guide, tool affordances, observations, retrieval and explicit user lifecycle requests |
| Mechanical computer adapter and custody | Serialize input, correlate original results, enforce authority and safe local execution, retain provenance | Actual pixels/geometry and honest delivery/authority results |
| Testing scaffolding | Select/freeze finite trials, control test spending and observation windows, request checkpoints/ending, evaluate results and retain evidence | Operator configuration, test counters, independent observations and review records |
| Game | Determine effects, needs, time, death and any game-specific completion condition | Player-visible game output |

The provider host contains both a reusable adapter and experimental countdown
injection. Its filename or process boundary does not decide which responsibility
owns a behavior. Likewise, the computer adapter supplies real capabilities needed
by the player; its per-experiment quotas are a different concern.

An ongoing survival objective can remain active across an experiment's observation
boundary. The test may request a checkpoint and orderly stop under its finite
authorization. That request should be labelled as external control. The player
can also signal that it believes the task or game is complete, giving evidence
and uncertainty. Model settlement, saved state, process exit and game completion
need distinct meanings. Current main supports finite campaigns; continuous
operation and an explicit completion lifecycle are future design work.

## Scope and evidence

Audited source is main `faca1d099a49bef8894be50b509ca00344f6cfe4`,
with `player-host/2`, `campaign-run/3` and Pi packages pinned to 1.4.0.
The separate `adr7-candidate` implementation has different host contracts and
readers. It was excluded from this main-player audit.

The original case is session `3a0f33e2c0384fa0909b9f6f8522eb61`, actor
`5193ff493f164535b15b1166310236eb`. The local retained family is
`.runtime/iteration164/candidate-research-2026-11-05/alex-continuation-screen/`,
with the case under its `production-alex/.runtime/computer-sessions/alex164-two-day/`.
The package and actor copies were inspected and checked against the frozen files.

| Original actor artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `prompt.txt` | 2,153 | `30981696658f9cf0f1b95533705383264d444745e7d6a566efeb6ed9bc9d5094` |
| `context.txt` | 7,553 | `2bc7c17ec6fd37e128c9bb9712e6d1022a10eddba416dd30427a32508bf35803` |
| `mcp.json` | 927 | `251e26f5a9c3c38b55ebea279cb116dca8e9c0e1f48e61ea7dc855513fcef8e9` |
| `route.json` | 899 | `fec8533896c6a6880d686438a63948183e3901d30de22d09fc9e046e3abd7c85` |

All 99 original images were verified in the outcome audit. No gameplay, model
requests, private reasoning inspection, save-content inspection or prompt replay
was part of this audit. The original preserved case remains closed.

## Complete context construction

| Surface | What reaches the model | Current owner and evidence |
| --- | --- | --- |
| Frozen guide | The compact player guide, including interpretation/effect checks, tool procedures, optional memory/program use, lifecycle and ending reserves | Player guidance mixed with test ending policy. [Guide](../player-guide.md), [runner](../../tools/player_host/run.mjs) |
| MCP initialization | Server instructions are appended to the guide in the model's system context. They assign game interpretation to the player and describe input uncertainty, Pause, handoff and session/actor IDs | Player interface and custody. [MCP adapter](../../harness/player_mcp.py), [host](../../tools/player_host/host.mjs) |
| Tool declaration | The enabled names, descriptions and JSON input schemas are supplied to the SDK as tools | Player interface. The Alex table contains all 14 tools in [tool specifications](../../harness/player_tools.py) |
| Initial assignment | Package prompt plus the driver's software actor/resource note, submitted as the initial user message | Test driver. [Campaign player](../../tools/campaign_player.py), [CLI runner](../../tools/player_host/run.mjs) |
| Per-request addition | A new software-generated user message states attempts charged, allowance remaining, host seconds remaining and retry caveats | Test bookkeeping inside [host context construction](../../tools/player_host/host.mjs) |
| Conversation history | Prior user/system messages, assistant content and tool calls, returned results and provider-owned reasoning replay fields handled by the SDK | Player working context. The host supplies the configured context and tools to Pi; it loads no coding-agent application prompt |
| Tool text and images | Canonical result JSON, original images and explicit tool error status. Source IDs, geometry and delivery facts accompany observations | Player interface and computer adapter. [Client](../../harness/player_client.py), [MCP adapter](../../harness/player_mcp.py) |
| Image retention | Older images become explicit omitted-image markers with call/index/hash provenance. The latest tool batch is protected; an oversized protected batch stops inference | Player context management with a frozen test configuration. [Image projection](../../tools/player_host/host.mjs) |
| Validation feedback | SDK validation errors and MCP error results can reach the model. A specialised intent-discriminator rewrite exists in the host | Interface feedback. Current main's 14 tool schemas have no top-level `intent` argument, so that specialised rewrite does not apply to this table. [Feedback](../../tools/player_host/validation-feedback.mjs) |
| Explicit retrieval | Requested player records, source images, program lineage, context and original-result collections | Player-owned knowledge and provenance, described below |
| Handoff | The driver appends the selected immutable context to a successor's prompt after verified old-host closure | Player continuation combined with finite campaign allocation. [Driver](../../tools/campaign_player.py) |
| Ending and final report | The assignment/driver ask the final actor to Save and Quit. A final assistant report settles the host; EOF gives only a bounded reporting opportunity | Current campaign lifecycle. [Host contract](../contracts/player-host.md#settlement-and-handoff) |

The installed Pi source was read on 5 November 2026. The inspected paths were
`pi-agent-core/dist/agent.js`, `pi-ai/dist/utils/transcript.js` and
`pi-ai/dist/api/openai-completions.js` in the retained host's pinned
`node_modules/@earendil-works/` tree. The agent builds its initial system
message from the supplied guide/instructions and tool declarations. The default
conversion keeps system, user, assistant and tool-result messages. The selected
OpenRouter compatibility settings serialize the instruction as a system message.
Image-bearing tool results also produce a user message labelled
“Attached image(s) from tool result:”. The selected compatibility settings do not
enable the optional synthetic assistant bridge after tool results. No separate
stock coding-agent persona was found on this path.

The installed serializer can retain same-model thinking blocks/signatures and
return reasoning fields or structured reasoning details in subsequent requests.
That reachability was checked in the SDK source without inspecting the contents
of private reasoning. Public host narration omits those contents. An audit of
visible assistant text alone would therefore miss a possible context channel.

This is a construction-path audit, not a recovered byte-for-byte request archive.
Telemetry retains original payload hashes/counts, public narration and image
references, rather than the complete serialized body or private reasoning. It
cannot prove model attention or reconstruct an exact alternative replay.
Request 1 recorded three messages, 10,894 text bytes and zero images.
Request 102 recorded 235 messages, 236,693 text bytes and 30 images.
Tool declarations also occupy the provider's tool field. Message/text counts
alone do not measure the complete instruction or context cost.

## Tools, knowledge and local-program context

The actual enabled table comprises computer observe/input/result/stop, player
source, memory append/read/query/context, program save/read/run, player result,
and player handoff. The model receives their descriptions and schemas even when
it never invokes them.

Alex created no player memory or programs, so explicit retrieved knowledge and
program callbacks were available context paths rather than active inputs in that
case. The screenshots also include the loaded game's own prior message history.
An old pickup or save line visible after Load needs independent timing evidence
before it can support a claim about a new action.

| Context channel | Contents and useful responsibility | Experiment information currently included |
| --- | --- | --- |
| `computer-operation/1` and original collection | Operation/session/actor IDs, kind/status, receipts, source, reasons and handoff. These support safe correlation and uncertainty handling | Internal monotonic deadline and `remaining` custodian seconds, inputs, requests, frames and bytes |
| `computer-source/1` and `player_source` | Exact original image, hash, original presentation/receipt times, full-image/window/viewport geometry and session identity | No host HTTP quota. These facts support valid clicks and source interpretation |
| `player-record/1` | Player-authored claim/work/decision/procedure/correction/advice, data, sources, support and applicability, with stored author/time/ID | No automatic quota injection. A player can preserve previously exposed quotas in its own text |
| `player-program/1` | Player-authored code, parent revision, sources/support, applicability and immutable code identity | No automatic mission countdown in the stored program definition |
| `player-context/1` and handoff context | Selected complete records, corrections, program ancestry, source references and explicit omissions | Can carry old player-authored test assumptions. Selection grants no input authority |
| `program-view/3` | Actual selected RGB pixels, source geometry/provenance, sampling/omission notes and the player's own interpretation | The original mechanical `remaining` resource object enters each program step |
| Program result and `player_result` | State, elapsed execution, child operation/source IDs, reasons and bounded trace, with original collection available | Nested original computer operations expose their deadline/remaining fields on collection |
| Errors and refusals | Invalid arguments, unavailable images/records, execution faults, unavailable control and uncertain delivery | Raw bounded reasons may reveal deadline or resource exhaustion and implementation details |

Sources are the [computer-control contract](../contracts/computer-control.md),
[runtime](../../harness/computer/runtime.py),
[application](../../harness/application.py),
[memory](../../harness/player/memory.py),
[context builder](../../harness/player/context.py),
[program runner](../../harness/player/programs.py) and
[image view](../../harness/player/images.py). The store retains original computer
results independently of model-facing serialization.

Tool affordance limits remain distinct from a test's countdown. For example,
the player needs valid action names and coordinate rules to operate the interface.
A program needs its execution/state limits to produce a valid bounded step.
Input uncertainty and revoked authority must remain explicit so the player can
collect the original result safely. These are reusable player-system obligations.
They do not require making a campaign's remaining inference budget a survival goal.

## Operator information and excluded inputs

The spectator's status, recent activity, investigation and Pause paths are
operator surfaces. They are absent from the 14-tool actor table. Watching or
acknowledging a frame creates no new player observation or game instruction.
The deciding model has no direct shell, repository search, save editing, provider
credential, this engineering conversation, AGENTS.md, personal coding-agent
settings or independent reviewers' commentary through this launch path.

The provider credential reaches the host through its selected environment
variable. The MCP/native processes receive their bounded environments, and
credential values are excluded from prompts and telemetry. Route price/model
settings configure serialization/accounting rather than becoming a separate
player instruction. Provider-side hidden processing remains outside this audit.
[Player-host isolation](../contracts/player-host.md#isolation)

## Findings and next change

1. **The test supplies a terminal game objective.** The Alex assignment tells the
   actor to begin ending at 48 hours. Its public justifications show this target
   taking priority over replenishment. Keep future observation markers with the
   test controller and give the player the user's ongoing survival objective.
2. **Quota context reaches the actor through several paths.** Removing the
   assignment's numeric limits alone leaves the driver note, per-request user
   message, computer results, collection and program views. Review and migrate
   these boundaries together.
3. **The reusable guide includes campaign ending policy.** Move ending reserves
   and finite-trial reporting requirements to the test-controller contract. The
   player should respond to explicit external stop/checkpoint requests and report
   its own completion claim, with reasons and evidence.
4. **Continuous play is not implemented by hiding counters.** The existing
   `campaign-run/3` and `player-host/2` require finite limits and interpret
   terminal text as host completion. Design the player lifecycle separately from
   finite campaign admission, including user stop, player-reported completion,
   interrupted control and recovery/continuation. Main retains text history,
   has no compaction/session restore and permits at most two hosts per campaign.
   Continuous play also needs context turnover, relevant retrieval and actor
   succession, with source provenance and fallible knowledge preserved. No
   context-overflow failure is claimed for the Alex run.
5. **Observation and safe-control information still matter.** Preserve original
   accounting for operators, valid tool limits, source/geometry and delivery facts,
   honest missing evidence and permanent user Pause. A quota-free objective does
   not make a failed input safe to replay.
6. **Behavioral benefit remains to be tested.** The run also contains incorrect
   visual interpretations and abandoned searches. A revised context can remove
   the experimental incentive, while a prospective independent trajectory must
   establish any improvement in planning, replenishment or local-program use.

The smallest coordinated design should identify a single actor-facing view,
retain full original receipts for operators, cover nested collection and program
paths, and define an external lifecycle request without teaching game tactics.
Choose named current versions for changed actor-visible shapes under
[S-MIGRATION](../standards/migration.md). Changing a projection need not rewrite
native wire packets or preserved original evidence.

Verification should exercise quota absence across every delivered context path,
preserved source and uncertainty handling, explicit stop/completion semantics,
ending capacity in the finite test controller, retry charging, and cancellation
during both inference and local programs. Real play is needed to assess useful
outcomes. No further play or spending was performed for this audit. #164's
qualification criteria and #145's seven-day gate remain open.
[Current work and owner direction](https://github.com/CVX-Hull/enactive/issues/164)
