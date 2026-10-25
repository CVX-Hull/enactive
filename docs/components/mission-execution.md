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

## Local feedback cost

Evidence capacity queries reuse an exact canonical metadata byte length, invalidated
on serialized state changes and refreshed after successful atomic persistence.
They still scan actual files with standard `os.scandir`; selected-source integrity,
freshness/custody, reservations, atomic writes and fsync retain their contracts.
This is a derived scalar, not cached authority or a second evidence store.
The [offline measurement](../acceptance/2026-10-24-execution-first-offline.md)
separates retained-scale dispatch improvement from unqualified graphical cadence.

Each original admitted semantic work item now has a machine-only settlement event
in the existing controller journal. It brackets durable admission and ends after
the writer's post-commit/finally publication and handle cleanup. Row state, writer
finalization and mission phase are distinct; a completed Finish report can coexist
with a withheld terminal transition. Cached result reads do not create another
sample, and program primitives retain their existing separate lane.

The event carries existing operation/boot/source identities and labelled process
monotonic clocks with a wall-anchor sampling bracket. It does not infer model
time, useful effect or physical display, nor enter default model/recent UI context.
Missing/censored telemetry stays explicit; failure of this new append alone cannot
rewrite a committed result or pause healthy play. Required domain persistence
faults retain their existing behavior. [Evaluation](../evaluation.md#request-settlement-clocks)
defines interpretation and limits.

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
design review.

## Assurance and evidence

These selected risks follow the writer's responsibilities, rather than listing
every phase test. [C-RUNTIME](../controls.md#c-runtime--live-authority-and-input-guards-runtime)
is the admission/accounting mechanism; [C-PORTABLE](../controls.md#c-portable--portable-regression-lane-automatic)
executes its fixture regressions.

| User consequence | Invariant and contract | Mechanism, representative assertion and limit |
| --- | --- | --- |
| A recent status view hides spent inputs or uncertain effects | Original cumulative charges and unknowns survive reopening. [Mission lifecycle](../protocol.md#integrated-mission-lifecycle). | MissionLedger counters: [ledger tests](../../tests/test_mission_ledger.py) `test_measured_counts_use_cumulative_rows_and_preserve_unknowns_across_reopen` asserts counts beyond recent history, preserved unknowns and isolated returned copies. Real SQLite/filesystem evidence does not prove native input or useful effect. |
| A crash resumes an unfinished phase with fresh authority | Reopen preserves history and charge, pauses the mission and restores no private phase/lease. [Ownership](../protocol.md#controller-run-ownership) and [lifecycle](../protocol.md#integrated-mission-lifecycle). | Ledger crash transition: [ledger tests](../../tests/test_mission_ledger.py) `test_phase_crash_preserves_unknown_cost_and_does_not_restore_authority` asserts paused/unknown state, retained costs, no authority and refused activation. Together these two cases form `assurance_execution`; simulated reopening does not exercise a native crash. |
| Successful phase bookkeeping is mistaken for a successful campaign or ending | Save/reload, identity continuity and succession need their actual proofs; ACK and task success remain distinct. [Lifecycle preconditions](../protocol.md#lifecycle-action-preconditions) and [handoff](../protocol.md#quiescent-player-replacement). | Registered composition: [handoff tests](../../tests/test_mission_handoff.py) `test_quiescent_bound_context_claim_and_separately_charged_resume` asserts no lease after Claim and a separately charged readmission, using a fake bridge. [C-NATIVE](../controls.md#c-native--native-build-and-real-game-acceptance-manual)'s [capture qualification](../acceptance/2026-10-22-native-capture-preconditions.md) demonstrates scoped same-character Save/reload/ending; [useful-play readiness](../acceptance/2026-10-25-useful-play-readiness.md) retains an incomplete ending. Neither qualifies independent seven days. |

Focused runtime/lifecycle/handoff/activity/recovery tests add boundary cases;
source tests, compiled components, actual native qualification and campaign
outcomes remain separate lanes. [#136](https://github.com/CVX-Hull/enactive/issues/136)
and [#145](https://github.com/CVX-Hull/enactive/issues/145) own the full outcome.
