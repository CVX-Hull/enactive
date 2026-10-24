---
owner: harness maintainer
review_trigger: Mission ownership, phases, root limits, lifecycle, handoff or execution feedback change
status: active
---

# Mission execution: one writer, several bounded responsibilities

Parent: [system architecture](../architecture.md). This view answers: “Who owns
the next action and how does feedback change the plan?” The player chooses actions;
MissionRuntime is the sole mission writer. It composes existing phase handlers,
controller, evidence, memory and ledger. Logical blocks here share a process;
separate modules are not separate authorities.

![Intent and feedback through the current single writer.](../diagrams/action.svg)

The sequence shows actual dispatch and evidence flow, including unknown delivery.
[Editable diagram](../diagrams/action.mmd). An ACK proves delivery within its scope;
the player still interprets the effect. A menu is a valid returned outcome.

## Internal responsibility and state map

| Block | Owned responsibility/state | Source and deeper contract |
| --- | --- | --- |
| MissionRuntime | One queue/worker, admission, handles, active lease and phase composition, cached status; owned launch, exit phase and Finish | [runtime](../../harness/mission_runtime.py); [mission lifecycle](../protocol.md#integrated-mission-lifecycle) |
| Registered lifecycle | Create/load, visible identity/adoption, normal Save and associated private phase | [lifecycle](../../harness/mission_lifecycle.py); [preconditions](../protocol.md#lifecycle-action-preconditions) |
| Registered activity | Owned long activity and exact interruption/answer/resume composition | [activity](../../harness/mission_activity.py); [item/activity composition](../protocol.md#selected-item-inspection-and-activity-composition) |
| Registered recovery | Original uncertain dispatch custody and typed effect reconciliation; no replay | [recovery](../../harness/mission_recovery.py); [operator recovery](../protocol.md#explicit-operator-recovery) |
| Registered handoff | Quiescent player replacement, source/Work packet and epoch transition | [handoff](../../harness/mission_handoff.py); [replacement](../protocol.md#quiescent-player-replacement) |
| Skills/program evaluator | One ordinary proposal from current visible feedback; no controller/process capability | [gameplay package](../../harness/gameplay/); [program_input](../../harness/gameplay/program_input.py) |
| MissionLedger | Durable request/primitive/effect/memory records and original cumulative accounting | [ledger](../../harness/gameplay/mission_ledger.py); [memory/evidence view](memory-learning.md) |
| ObservedMap | Runtime-owned process-local lossy route-candidate cache, separate from evidence and memory Claims | [navigation](../../harness/gameplay/navigation.py); [evidence contract](../protocol.md#passive-gameplay-records-and-evidence) |

Admission is not Resume. A request must satisfy the current actor/epoch, custody,
source and original local/whole limits before dispatch. Durable intent precedes
publication. A private phase is not reconstructed from JSON/history on restart.
The exact controller object lease, not a serialized actor label, authorizes input.

ObservedMap keeps the current/cardinal footprint and evicts older candidate
coordinates using observed revisions. Forgotten routes become unavailable until
reobserved; eviction does not erase retained sources or memory. Every dispatched
step still checks current movement eligibility. This cache is not a persistent
world model or another navigation executor.

## Programs, feedback and organic discovery

Ordinary keys/text/clicks are the foundation; semantic navigation/item/activity
skills are optional shortcuts. The existing writer obtains feedback after each
primitive. A player-authored pinned JavaScript routine can branch on structured
visible data and propose inputs without an LLM call per step. It has no host I/O
or separate execution authority. Its current view excludes PNG pixels and unseen
map/inventory; missing facts require yield or player interpretation.

Local refusal with positively healthy custody preserves the scope for a new
explicit decision; actual integrity/authority loss or uncertain delivery stops it.
Observe can retain changed visible evidence under its declared observation bounds;
it does not replenish spent execution roots or prove task success. Exact behavior
is in [binding errors](../protocol.md#skill-request-binding-errors), not a menu
whitelist in this explanation. Repeated SDK calls must not silently mint a new
parent allowance. Generic autonomous strategy/inference overlap is not yet qualified.

A known native refusal also consumes an operation rotation even though it
commits no input. The writer retains its rejected receipt, then reuses the
existing custody/evidence/global-capacity proof before marking read-only Observe
needed. The next input remains a new player choice. Unknown delivery and actual
faults still stop. Stable predicate labels in the existing operation reason make
prompt failures diagnosable without another log or authority store. This small
ordered check remains with the writer: splitting four predicates into a new
service would add coordination without changing ownership. Reconsider extraction
when a demonstrated independent responsibility requires it, under
[#191](https://github.com/CVX-Hull/enactive/issues/191).

## Lifecycle and change review

Start cannot adopt an unrelated running game. First normal identity/adoption
establishes eligible game-time/map/memory lineage. Normal reload requires this
mission's own verified saved checkpoint and chronological continuity; historical
sources never restore consent. Handoff requires settled operations, paused custody,
required Work and the actual predecessor's exit before a new host is activated.
Source-read declarations are audit statements, not proof of model attention.

Lifecycle checkpoints follow the separately validated current capture; an ACK
remains immutable delivery evidence even when a newer capture arrives. Different
current evidence ends the batch for a new player decision. Confirmation-stage
consent survives only equivalent evidence, and an identity inspection retains its
exact completed ACK proof separately from the current checkpoint. Diagnostic
transitions still require their existing reconciliation and readmission.

Review a change from the owner/phase and flow down to shared limits, publication,
receipt/reopen readers and tests. The large runtime and ledger remain concentrated
implementation seams; this map does not claim they have been refactored. Extract
only a demonstrated responsibility with one retained writer/store, after scoped
design review. Focused runtime/lifecycle/handoff/activity/recovery/ledger tests
exercise source behavior; actual Save/reload, succession and independent survival
need their separate native/outcome evidence. [#136](https://github.com/CVX-Hull/enactive/issues/136)
and [#145](https://github.com/CVX-Hull/enactive/issues/145) own the full outcome.
