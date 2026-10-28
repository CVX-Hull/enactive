---
owner: integration maintainer
review_trigger: Controller/native ownership, visible observation, process custody, input or recovery changes
status: active
---

# Native control and visible observation

Parent: [system architecture](../architecture.md). This view answers: “What makes
an input eligible, and how can the user stop it?” The controller serializes
dispatch; the CDDA integration validates its receiver/custody at commit and the
engine decides outcomes. User Pause and native takeover remain independent of
the player's reasoning and the ordinary mission queue.

![One exact owner; competing input rejected and Pause revokes ownership.](../diagrams/run-ownership.svg)

This logical view shows acquisition, dispatch and revocation within the host.
It is not a process-isolation diagram. [Editable source](../diagrams/run-ownership.mmd).

## Internal responsibilities

| Block | Owned state/interface | Implementation |
| --- | --- | --- |
| Controller | Exact process-local lease, serialized ordinary/control slots, pending delivery, Pause/takeover generations | [controller.py](../../harness/controller.py) |
| Owned process adapter | Fixed prepared wrapper and retained child custody; no arbitrary command/PID adoption interface | [native_process.py](../../harness/native_process.py), [prepared_app.py](../../harness/prepared_app.py) |
| Native CDDA bridge | File inbox/receipt boundary, current receiver/token validation, actual SDL frame and visible metadata | [cdda_harness.cpp](../../native/cdda_harness.cpp), [header](../../native/cdda_harness.h) |
| Recovery composition | Separate paused control requests and original uncertain-dispatch evidence | [mission_recovery.py](../../harness/mission_recovery.py); [detailed native recovery design](../design/native-control.md) |
| Shared movement policy | Pure conservative visible-cell rules used by controller walk and movement skill | [movement.py](../../harness/movement.py) |

The process adapter owns bounded exceptional termination as well as launch/wait.
Only the settled mission writer invokes it after input revocation; a blocked writer
or lost handle yields unknown cleanup. Normal lifecycle exit and exceptional
termination have separate receipts and acceptance meanings. See the
[shutdown contract](../contracts/lifecycle-exit.md#exceptional-writer-shutdown) and
[controlled-child regressions](../../tests/test_mission_shutdown.py). Reopen cannot
adopt a native PID from those receipts.

Native7 visible rows preserve labels and focus while carrying a separate nullable
literal rendered marker. The CDDA binding records the actual inventory marker
cell only when visible, in the same row draw; null does not mean unmarked. Other
games need their own visible producer, without inheriting CDDA marker semantics.
The [protocol](../contracts/gameplay-evidence.md#passive-gameplay-records-and-evidence) owns current
wire/store migration and archival limits.

Native metadata is restricted to player-visible information, excluding saves,
unseen maps and hidden threats. Physical ordinary input and semantic shortcuts
have different applicability checks; neither bypasses custody, receiver or original
deadlines. A capture's historical integrity and its suitability for a current
semantic action are distinct. [Protocol](../contracts/controller-ownership.md#controller-run-ownership)
owns precise fences and [transport](../contracts/native-observations.md#native-request-lifecycle-and-unknown-outcomes) its wire shape.

## Pause, unknown effects and restart

Pause revokes subsequent remote dispatch; it cannot undo input already committed
or guarantee interruption of an engine-owned activity. Native keys/buttons latch
takeover. Expected internal rotations cannot erase an intervening user Pause.
One controller process lock covers ordinary/control writers; native validates
again at commit. Status describes ownership but cannot serialize the object lease.

Unknown delivery retains its identity and charge. Collect/reconcile through
supported evidence instead of replaying. Recovery cannot bypass interruptibility,
own an unrelated question or Resume ordinary gameplay. Restart restores history
and uncertainty, never an execution lease/private phase. Process exit alone does
not prove a normal Save, identity or successful lifecycle.

## Portability and verification

The bridge, menu metadata, lifecycle proofs, timing/coordinate units and portions
of mission contracts are CDDA-specific. Shared player/memory/orchestration design
must not silently treat those as universal game concepts. See the parent
[portability boundary](../architecture.md#game-family-portability).

Review responsibility/custody and failure flows, then host/native producer-consumer
contracts and source. Import/protocol checks detect selected drift.

## Assurance and evidence

These representative guards implement [C-RUNTIME](../controls.md#c-runtime--live-authority-and-input-guards-runtime).
[C-PORTABLE](../controls.md#c-portable--portable-regression-lane-automatic) runs
host fixtures and compiled component tests; it does not establish
[C-NATIVE](../controls.md#c-native--native-build-and-real-game-acceptance-manual)
actual-game qualification.

| User consequence | Invariant and contract | Mechanism, representative assertion and limit |
| --- | --- | --- |
| Rendering churn retargets an input or stale authority reaches dispatch | Keep the original non-image capture; reject changed session, revision or boundary. [Ownership contract](../contracts/controller-ownership.md#controller-run-ownership). | Controller preflight: [controller tests](../../tests/test_controller.py), selected by `assurance_freshness`, assert original capture binding across render churn and no action delivery after changed authority. A fake bridge exercises the host side, not SDL/game behavior. |
| An input commits to the wrong receiver or after user revocation | Native checks receiver/custody and Pause/takeover again at commit. [Ownership contract](../contracts/controller-ownership.md#controller-run-ownership). | Native poll/dispatch gates: [receiver tests](../../tests/test_native_receiver.py) `test_production_receiver_and_dispatch` (`assurance_native`) executes extracted production C++ with explicit doubles. Its [comparison-fence scenarios](../../tests/native_receiver_fixture.cpp) assert refusal/fault and zero input feeds after changed receiver, Pause or takeover. This compiled component is not a patched CDDA build or graphical acceptance. |
| A passing fixture is mistaken for safe input across every native condition | New support needs matching built source and actual affected native qualification. [Recovery contract](../contracts/operator-recovery.md#explicit-operator-recovery). | C-NATIVE's [capture report](../acceptance/2026-10-22-native-capture-preconditions.md) demonstrates scoped ordinary input and normal same-character lifecycle; persistent pixel drift and retained-A/newer-B timing remain unexercised there. [Local refusal](../acceptance/2026-10-22-native-local-refusal.md) demonstrates a separate ordinary refusal/cancellation path, not wider mouse, takeover or interruption coverage. |

Host-side queue and Pause coverage also includes [controller](../../tests/test_controller.py)
`test_walk_stop_revokes_queued_generation_and_pause_race`, which asserts the queued
action returns `pause_requested` and no action requests are sent. This remains
fake-bridge host evidence.

A full native build and actual gameplay are further separate lanes. The retained
reports qualify only their stated source/build/scenario; portability to another
real game remains with [#191](https://github.com/CVX-Hull/enactive/issues/191).
The [runbook](../runbook.md) owns operating/recovery steps; [evaluation](../evaluation.md)
owns acceptance definitions. Wider mouse/geometry and generic recovery remain
limited to their demonstrated scope.
