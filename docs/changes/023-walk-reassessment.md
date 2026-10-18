---
owner: lead
date: 2026-10-18
scope: Walk correction design and first unexercised functional probe on candidate32bbae6
status: historical
---

# Walk outcome evidence and explicit reassessment

The implementation design below remains the rationale for the current contract.
Its first functional probe stopped after an unknown load receipt, before exercising
walk. The original wording and failure are retained; the separately prospective
[second probe](024-walk-reassessment-probe.md) does not amend this admission.

[#108](https://github.com/CVX-Hull/enactive/issues/108) addresses the actual
[stopped campaign](../acceptance/2026-10-18-seven-day-stop.md), published in PR109.
It does not resume that attempt or establish seven-day survival.

## Problem and decision

The player received a zero-step walk summary without the observation that caused
the stop. A later movement from an earlier image was rejected by automatic
approval review. Native command preflight cannot supply the model's missing
interpretation. Keep the conservative movement guards and make the boundary
explicit: retain actual walk evidence and require fresh observation after a stop.

Reuse the controller's existing frozen state, Pause sentinel, authority generation,
serialized command path, native response validation and atomic observation snapshot.
No dependency, second state machine, generic monitor or permission expansion is
needed. A guide-only fix would leave both missing evidence and an avoidable next
input path. A new planner/world-model framework has no demonstrated need here.
Maintainer owns this small boundary with the controller; revisit if a future
execution contract replaces public walk rather than keeping a parallel adapter.

## One current result and authority contract

For an admitted, syntactically valid walk that enters `_walk`, the aggregate keeps
`status`, credited `steps`, and `detail` or `error`, and always adds:

- `observation`: last schema-validated `ready` response returned by an exchange
  during this walk, or null. Never substitute an older global observation.
- `observation_phase`: `pre_step` or `post_step`, or null with no observation.
  Post-step means after the attempted input, not verified displacement.
- `observation_received_monotonic`: its original receipt clock from one atomic
  snapshot captured immediately after that exchange, only if the entire snapshot
  equals that response; otherwise null. Preserve locally; never renew age.
- `terminal_response`: exact last exchange return, including a controller-generated
  timeout/error, or null if no exchange occurred. It can differ from the last
  ready observation; a pre-action image cannot prove an uncertain action's result.

Malformed/rejected stale packets never become observations. A validated ready
menu or unavailable-frame response is evidence with its actual limitations, not
normal-play authority. Earlier ingress/admission failures remain ordinary
`controller_error`; they have not entered a walk and provide no walk envelope.
Request UUID, session, revision, frame, timestamp and boundary remain native fields
inside the retained response. The receipt clock is process-local evidence only.

Every stopped walk atomically freezes control, requests Pause, revokes its
generation and writes the sentinel before returning. Status reads and ordinary
command preflight cannot clear this hold. An explicit successful Observe reconciles
the transport; the player must inspect its actual image and stop reason, decide
again, then explicitly Resume before choosing another action. Old queued commands
retain their revoked generation. Complete walks add no new hold. No automatic
Observe, Resume, movement, guard relaxation or unknown-outcome resolution follows.
The controller enforces the Observe/Resume sequence; it cannot prove understanding.

Native wire3, input registration, per-exchange deadlines, displacement accounting,
all-creature/terrain guards and historical unknowns remain unchanged. CLI and HTTP
already transport result JSON; the viewer already gates controls on frozen/Pause.
Update their guidance and meaningful consumer tests together. Historical journals,
reports and frozen one-off capture helpers remain evidence, never runtime readers
or supported old result shapes. A later capture must retain the nested observation
image rather than treating an aggregate as a native packet. Stop affected writers,
deploy the coordinated controller/callers, restart paused; no persisted active task
or native format migration is needed. Rollback uses the earlier coherent Git tree
with its former behavior; it cannot revive the stopped campaign's authority.

## Allocation and evidence

Lead owns this design, docs, integration and shared runtime. One clean-context
worker owns only `harness/controller.py` and `tests/test_controller.py` in its
separate project-local worktree. Independent design review found no P1/P2 after
the clock identity, pre-admission boundary and atomic freeze were made explicit.
Lead verifies returned diff and checks; independent review inspects implementation
and tests. No source writes or competing executors during native acceptance.

Portable cases cover complete, zero/partial/final-step stop, no ready observation,
stale/conflicting snapshots, malformed response, native action timeout with retained
pre-action evidence, Pause/generation races, blocked status/preflight/Resume and
successful explicit Observe/Resume. Run common checks and protected exact/main CI.

After a committed candidate and passing relevant checks, the lead may separately
admit one windowed functional probe: normal-load preserved Ned Meyers/Belgium,
verify identity, exercise a conservative zero-step guarded stop if the visible
friendly creature remains, inspect retained and fresh images, verify the hold and
explicit Observe/Resume, then inspect inventory and normally Save/Quit. No replay
of the denied DOWN or survival progression claim. Before launching, record exact
source/binary and clocks locally. Limits: 40 charged inputs and45wall minutes
including load/review/cleanup, at most60elapsed game seconds; reserve12inputs/final
10minutes for normal cleanup. Ordinary requests5s; actual menu load confirmation
may use15s declared before dispatch. One attempt; stop investigation on actual
approval denial, unsupported/ambiguous state, identity mismatch, limit or need for
human rescue. Unknown receipts remain unknown, charged once and never replayed;
fresh reconciliation permits only explicitly justified normal cleanup. Existing
project-local capture/CLI/parser capabilities are preferred; no global installs.

The probe cannot amend protocol022, reroll a world or admit later campaign play.
Further survival needs an explicit prospective finite decision with preserved
attempt/cumulative lineage after actual repair evidence. The overall goal remains
the real seven-day outcome; a useful correction or probe is only a prerequisite.
