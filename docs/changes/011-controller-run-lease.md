---
owner: lead
status: active
review_trigger: Round 011 interfaces, ownership, acceptance or scope changes
---

# Controller run ownership

## Outcome and scope

From main `c1ba24480a73bdcf9dd8b48a54a2701c6038d1c2`, deliver the controller
lease portion, tracked in [#50](https://github.com/CVX-Hull/enactive/issues/50), of [#36](https://github.com/CVX-Hull/enactive/issues/36).
A trusted in-process caller can claim a reconciled controller for one run, send
one observed-state-bound action at a time, and relinquish it. Existing HTTP/CLI
inputs respect that owner. Pause immediately revokes ownership. This makes the
next supervisor integration possible; it does not connect a planner or start tasks.

No new HTTP lifecycle endpoints, model provider, receipt assembler, autonomous
loop, learned policy, viewer redesign or native wire change. Broad-objective task
formation remains a higher-level player responsibility, separately tracked.
Native v3 remains the only wire contract. The lease is an in-memory Python
capability, never a restored journal record or a client-supplied JSON token.

## Frozen API and arbitration

`RunLease` is a frozen controller-owned value with task ID, execution epoch,
owner and session. Its exact object identity is required; reconstructing its
public fields does not recreate authority. Bounded nonempty identifiers and a
nonnegative integer epoch are validated. A new acquisition always creates a new
capability, even when its descriptive fields repeat. Status exposes descriptive
ownership only, never an executable capability.

`Controller.acquire_run(task_id, execution_epoch, owner, *, expected_session,
expected_revision)` returns RunLease or raises ControlError. It never observes,
resumes or sends an input. Acquire command_lock then control_lock nonblocking,
then data_lock; release all before returning. Reject active/queued writer work,
existing lease, closed/frozen/paused state, pending native/control work or inboxes,
missing/stale/unsuccessful/non-normal frame, and a mismatched expected observation.
An explicitly reconciled past unknown remains historical uncertainty; acquisition
never resolves it or reconstructs an old task. Reject an outstanding pending effect.
Current state must have no future timestamp beyond existing evidence tolerance.
Rotate native authority and the command admission generation before publishing the
new lease so pre-acquisition admissions cannot execute afterward. Simultaneous
starts have one winner. Acquisition does not hold locks during model reasoning.

`Controller.execute_run(lease, *, action, expected_session, expected_revision,
timeout=None)` is the sole leased input entry point: one registered semantic
action, using the existing primitive path and return shape. It never invokes walk
or accepts arbitrary native payload fields. Validate the exact live capability,
its world/session and the entry admission generation before waiting, after
acquiring the command lock, after preflight Observe and at atomic native request
publication. A stale lease rejects before dispatch. Do not silently rebind the
expected observation or renew a generation inside a walk.

Existing `execute` remains the external operator path. While leased, external
key/action/walk/resume reject. Observe/status, record-only goal and Pause remain
available; recording goal text cannot replace a running task. Every queued writer
captures its admission generation before waiting and rechecks it after acquiring
the writer lock. Track admitted/waiting command work under data_lock so start
cannot race an invisible queue; preserve a command's original generation through
every walk step. Old queued input stays invalid even after lease release.

`Controller.release_run(lease)` requires exact live identity and pauses/revokes
before returning; stale release cannot revoke another owner. Pause, recovery
admission, native takeover/session change, close and transport failure invalidate
the lease through the common authority-revocation path. Native paused observations
must also revoke any live lease, including when no generation delta is available.
Transport Resume grants no lease and never resurrects one. A stopped controller
starts paused with no lease. No automatic retry of uncertain effects.

Existing native authority is still checked at the game-thread commit point. Host
revocation cannot undo an input already committed. Rejected host preflight must
not fabricate native delivery evidence. Status ownership is informational and
cannot substitute for admission. No lease API is exposed through ordinary HTTP
payloads, and guessed extra fields remain rejected.

## Ownership and sequence

Lead owns this design, issue/Project changes, authoritative docs/diagrams,
integration, native acceptance and protected publication. One clean-context worker
owns only `harness/controller.py` and `tests/test_controller.py`, on the reviewed
brief checkpoint in `.runtime/worktrees/round011-controller`, branch
`work/round011-controller`. Worker uses the existing project Python read-only,
PYTHONDONTWRITEBYTECODE=1 and isolated temporary test roots; no native runtime,
shared caches, dependency installation or server port. Lead owns server/CLI ingress regression additions and the existing viewer
owner badge/input gating in web/app.js and tests/test_viewer.cjs. This small
ownership disclosure does not implement #23 task/progress UI. A separate clean-context reviewer audits race
semantics and changed tests. Shared source writes remain single-threaded; a second
worker would compete at the same authority boundary and is intentionally omitted.

Worker handoff includes commit/diff, exact checks/failures and limitations. Escalate
after two unsuccessful repair attempts or ownership drift. Lead verifies the diff
and runs integrated checks; independent review precedes final acceptance.

## Acceptance and evidence

Portable tests: simultaneous acquisition; active and queued writers/recovery;
external key/action/walk/resume exclusion; old queued input after acquire/release;
stale/reconstructed lease; pause before publication and native commit; release of
wrong owner; fresh/stale/changed-session evidence; normal menu/activity rejection;
Observe/status/goal availability; timeout and malformed-result revocation;
shutdown/restart without restoration; Resume without acquisition; walk preserves
entry generation. Reuse deterministic thread barriers, not timing-only assertions.
HTTP regression proves existing ingress cannot pass a lease or bypass ownership.

Run `.venv/bin/python tools/check.py` plus focused controller/server tests. Record
all failures and review repairs. Lead reuses the unchanged native build only after
source/binary provenance checks, launches the prepared wrapper windowed, and
retains real frames and receipts for a leased cardinal step and return, blocked
external input, Pause/stale-capability rejection and explicit manual recovery.
Native timing races remain portable or previously scoped native evidence unless
actually exercised in this round. No model-performance claim follows.

Update architecture/protocol/overview/runbook and ownership visual together.
Record exact candidate and evidence lanes, inspect staged changes, verify protected
PR and merged-main CI, then close the child issue and clean owned worktree/branches.
Parent #36 stays open for native receipt assembly, lifecycle/provider and status
integration. No persisted/native format migration is needed; all changed local
callers and tests migrate together without fallback overloads or compatibility shims.

## Tradeoffs and maintenance

Controller ownership must precede repeated supervisor dispatch. Receipt assembly
alone would leave competing ingress uncontrolled. A distributed lock, agent
framework or separate service adds no capability for this single-process writer;
existing threading locks and process lock fit the requirement. Keep the API small
and process-local; reconsider only when a concrete multi-process caller is needed.

Provisional estimate: M / Medium, 2–3 focused sessions including design, review,
portable/native acceptance and publication, excluding external waiting. This is
not a calibrated delivery date. Review ownership semantics whenever another
input ingress, lifecycle adapter or authority path changes. Native validation,
portable tests and source review remain separate evidence lanes.
