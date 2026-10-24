---
owner: lead
review_trigger: Player action space, procedural learning, evidence or adaptation policy changes
status: proposed
---

# Organic discovery and player-learned procedures

The player should explore through ordinary game interaction, learn from its
outcomes and increasingly reuse its own abstractions. Higher-level skills save
work; their catalogue must not define everything the player is allowed to try.
The lead maintains the substrate and reviews engineering, while the player owns
game decisions, memory use, procedure proposals and ordinary correction.

This is a direction and cross-check, not an implemented input/learning contract.
Current [architecture](../architecture.md) and [protocol](../protocol.md) remain
authoritative. [Delivery057](../changes/057-discovery-learning-campaign.md) now
implements ordinary key/text/click transport, procedures and reflection; the
[learning004 report](../acceptance/2026-10-21-discovery-learning-fourth-attempt.md)
qualifies its bounded functional result and explicit learning/mouse limits.
This proposal's earlier “current” crosswalk describes its October20 baseline,
not absence of that later source. #190 repairs the failed002 prompt-loss case;
[#191](https://github.com/CVX-Hull/enactive/issues/191) owns systemic organic-input
and CDDA-class portability gaps. No failed admission resumes from this page.

The [charter's P-GENERALITY](../charter.md#p-generality-build-the-capacity-to-discover)
and game-family constraint now govern further design. Unseen or changing menus
must not require a new engineered gameplay handler just to permit ordinary input.
Procedures describe revisable hypotheses with game/configuration applicability;
they do not define the action space. The [Bitter Lesson cross-check](../research.md#generality-and-the-bitter-lesson)
records the primary argument, our application and limits. Preserve the existing
research distinctions below rather than treating this essay as an efficacy result.

## Intended loop and boundaries

Ordinary input → retained episodes → procedural candidates → closed-loop reuse →
observed outcomes and corrections. This extends the logical responsibilities in
the [tiered design](../research-tiered-gameplay.md); it does not require another
model tier, vector store, training service or input executor.

| Layer | Responsibility and limit |
| --- | --- |
| Interaction | Player chooses a bounded key, text operation or deliberate click from the current visible frame. The existing single writer retains provenance, limits, delivery and after-evidence. Unknown semantic effect is a result to interpret, not necessarily an engineering fault. |
| Episodes | Retain intent, observation/action/result IDs, scope, configuration, costs, uncertainty and interventions. Unknown delivery stays unknown until supported reconciliation; no blind replay. |
| Campaign memory | Facts, interpretations, corrections and unfinished Work about this world/character. Historical stock and map coordinates never become current authority or transferable facts. |
| Procedural candidates | Player proposes applicability, goal, steps/policy, observable progress/termination, source episodes, failures/counterexamples and unresolved assumptions. One success does not establish a universal rule. |
| Reusable procedures | Under an explicitly declared adaptation policy, the player may retrieve, test, revise and reuse procedure data without an engineer approving each procedure/action. Code, prompt-template, weight or substrate changes remain separate versioned engineering work; retrieved procedure content is data supplied under that policy. |
| Feedback | Compare actual visible outcomes with intended effects, revise memory/dependent plans and return to direct interaction when useful. A repeated failure calls for a different experiment, not identical retries. |

Execution integrity and semantic judgment remain distinct. The writer establishes
ownership, current source, budgets and delivery; the player judges usefulness and
game outcomes. A procedure cannot grant a lease or change Pause. Existing finite
limits continue across a skill/direct-interaction switch; no new root silently
renews a still-open phase. Research evidence and learned advice never authorize
input by themselves.

## Cross-check against prior work

Checked against current files and targeted primary-source sections on 2026-10-20.
This is not a new full literature survey or renewal of the October24 research
review. A conflict below remains explicit until a selected implementation migrates
the current contracts and guidance together.

| Prior source | Keep | Gap or proposed change |
| --- | --- | --- |
| [Tiered gameplay](../research-tiered-gameplay.md), including the [CodeHack mixed-control results](https://arxiv.org/html/2609.31076v1#S5.SS4) | Skills and primitives share feedback and input authority; model tiers need measured value. The paper finds benefits from mixed control under incomplete library coverage, with added inference cost. | Current player tooling exposes a restricted semantic catalogue. Restore the intended mixed action space. The paper's engineered skills/richer game observations do not prove player-generated CDDA skills or efficiency. |
| [Memory/learning review](../research-memory-learning.md) and [representation study](../research-memory-representations.md) | Evidence, interpretations, hypotheses, procedures and predictions have different roles. Keep source support, applicability, counterexamples, bounded retrieval and correction. | Existing proposals default reusable promotion to offline review. New product direction proposes autonomous procedure-data evolution under a frozen learner/update policy; executable code changes remain offline. Current admissions declaring no online promotion remain unchanged. |
| [Architecture assessment](../research-memory-architecture.md) | Player-local factual/provisional tactical adaptation already needs no PR or per-key critic. Preserve unfinished Work and fresh-context source retrieval; summaries do not replace evidence. | Functional procedural learning needs a bounded implementation beyond the current campaign fact store. It must retain transfer scope and retirement across fresh contexts, not silently rewrite a master narrative. |
| [STRATA methods](https://arxiv.org/html/2610.19386v1#S3) as reviewed in our memory survey | Separate atomic operations, workflows and abstractions; retain negative-transfer warnings. Its solved-episode procedures and failed-episode pitfalls motivate distinguishing what worked from what to avoid. | Use these as design hypotheses. Its benchmark feedback is stronger than uncertain CDDA observations; adopting its graph, embeddings, reflector roles or promotion thresholds is not implied. |
| [Outcome monitoring](../design/outcome-monitoring.md) and [mission design](player-owned-mission.md) | Delivery is distinct from task success; partial/refused work permits supported repair/replanning; unknown delivery requires reconciliation. | An unfamiliar semantic outcome should return control to the player. General ordinary UI interaction should not require a hand-coded parser for every menu; actual unsupported transport/ownership remains an explicit limit. |
| [Memory study protocol](memory-study-protocol.md) and [campaign improvement workflow](../project-management.md#campaign-driven-improvement) | Source-separated comparisons, actual failure traces, declared update policy and costs. Optional curator and advanced training are separate. | Functional autonomous proposal/reuse is a product capability; proving improvement requires separate transfer/retention/regression comparisons. Neither a successful demo nor more stored traces establishes learning benefit. |

## Interaction implementation questions

The [selected mixed-input design](mixed-input.md) resolves the selected ingress,
root/activity ownership, native geometry/mouse handling and migration/validation
lanes. Delivery057 implements that substrate. The questions below remain
qualification obligations; source support does not qualify every native boundary.

Reuse the existing key/action injection, mission writer, primitive ledger,
controller and official MCP adapter. The native bridge already constructs engine
keyboard events, and current mission/tool schemas now expose bounded ordinary
input alongside semantic skills. Mouse handling uses an ordinary engine event
and in-process widgets, not Mac pointer automation or another executor; its real
qualification remains separate from source implementation.

Before claiming clicks, prove capture-pixel to engine-window/widget coordinate
mapping, including viewport/scale; preserve injected coordinates instead of the
engine's physical-mouse overwrite. Distinguish deliberate actor events from
physical input/takeover and incidental hover. Keep background/windowed rendering,
user Pause and no global Mac changes. The existing mouse-disabled configuration
cannot simply be assumed to support synthetic clicks. Native event classification,
ImGui down/up handling and ordinary unknown menus need explicit qualification.

Decide and test skill-to-direct interaction ownership for normal play and owned
menus, plus the narrower creation/save/reload/identity and activity boundaries.
Record abandoned/partial semantic goals honestly. Do not add arbitrary host
commands, hidden state/save access, a transport escape route or per-action human
or automatic approval review. MCP catalogue/allowance activation is a setup gate,
not an approval loop during play.

Schema/native changes require the project's one-current-contract migration,
matching build and focused native proof. A small key-only prototype is not mouse
completion; a successful click is not autonomous skill learning. Current full
supply/shelter/memory/handoff/normal-lifecycle acceptance is preserved.

## Active play and background reflection

The [asynchronous-reflection proposal](asynchronous-reflection.md) develops the
active-player/background-learning split, two-way signals, eventual revision,
stale-advice and cost controls, and a focused primary-source cross-check. Software
owns the implemented exchange; the engineering lead is not the player's slow path.
Learning004 exercises actual concurrent player/adviser actors within its stated
scope. This design page grants no actor assignment or admission authority.

## Development, evaluation and maintenance

Use the [development-first workflow](../project-management.md#development-first-delivery)
and risk-selected reviews. First reproduce concrete gaps cheaply, then exercise
related unknown capabilities in coherent finite exploration. Existing normal
reload proves only its own mission's save; proposed cross-admission development
checkpoint reuse must establish a new starting baseline and ownership, preserve
old failures/costs and use ordinary CDDA Save/Load. It cannot restore a failed run.

For procedure learning, first demonstrate agent-authored applicability and
source-linked reuse, actual failure-driven revision, bounded retrieval and fresh
context continuity. Declare which data may evolve and which learner/library/code
versions are frozen before play. Independently observed outcomes ground candidate
status; self-agreement is not an external success label. An optional curator can
advise but is neither input owner nor mandatory approval authority.

Then evaluate useful progress, whole-skill/model/tool delay, costs, unsupported
promotion, transfer, forgetting/regression and stale/confusable applicability.
Compare against the simpler baseline before claiming benefit or adding training.
No per-key reflection, mandatory graph stack or hidden-state oracle follows.

Lead owns interface/design integration; one runtime owner and disjoint workers only
after interfaces are frozen. At integration and existing event/date reviews,
reconcile this proposal against implementation, the linked research/contracts and
campaign findings. Retire superseded assumptions; retain historical evidence in
Git and the existing ledgers. Research and control dates do not reset here.
