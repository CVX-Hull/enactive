---
owner: lead
status: historical
date: '2026-10-17'
scope: Accepted design-round intent and implementation handoff ownership; not runtime capability
---

# Gameplay foundation — review brief

Round: #6 and #17. Base: `806c0ba60141ce5601f734865720d6c87047afc4`.
Owner: lead; accountable maintainer: @CVX-Hull. This round delivers design and
implementation readiness. Native cancellation, planner execution, API spending and
new graphical gameplay acceptance remain downstream work.

[Design acceptance](../acceptance/2026-10-17-gameplay-design.md) records source evidence,
independent findings and repairs, diagram inspection, checks and unexecuted lanes.

## Before and intended after

Today the harness knows input categories but cannot positively distinguish normal
play from activity polling, has no remote recovery for raw debug prompts, and records
goals without a model service. The owner needs a precise, reviewable next increment.

After this round: a source-grounded [native recovery design](../design/native-control.md),
the [waypoint-and-return gameplay contract](../design/gameplay.md), a documented
[reuse decision](../decisions/005-gameplay-foundation.md), and bounded GitHub handoffs.
The current architecture/protocol retain their existing behavior claims. Implementation
will later deliver explicit user recovery and verified two-stage gameplay, with separate
portable, native and model-evaluation evidence.

## Allocation and sequence

Three read-only explorers inspect native source, current gameplay interfaces and
maintained reuse candidates. The lead verifies their claims, chooses boundaries and
writes the integrated design. A clean-context reviewer checks cross-document consistency,
actual source fit, implementability and missing acceptance conditions. No parallel
writers are needed for this design round.

Implementation handoffs below define ownership units. GitHub issues own their actual
IDs, estimates, readiness and dependency stages. Downstream parents #7, #19 and #22
remain open; decomposing them does not deliver their capabilities.

| Handoff / parent | Named source ownership | Dependencies and required checks |
| --- | --- | --- |
| Native boundary identity / #7 | `native/cdda_harness.{h,cpp}`, `tools/patch_game.py`, `native/upstream.json`, controller/server version readers, `tools/governance.py`, related controller/governance/setup tests | Accepted #6; v2 producer/consumers, scope stack and world-session rotation first. Common checks, pinned patch anchoring and native build; real boundary probes before closing the slice, full recovery remains #8. |
| Operator recovery transport / #7 | Same native files plus `harness/controller.py`, `tests/test_controller.py` | Native boundary identity; serialized after it, not a second concurrent writer. Exercise durable revocation before/after claim, expiry/duplicates, both pending channels, takeover and nested prompts; native build/targeted probes and #8. |
| Recovery UI and ingress / #7 | `harness/server.py`, `harness/__main__.py`, `web/*`, `tests/test_server.py`, `tests/test_viewer.cjs` | Accepted recovery transport/envelopes. Token/origin, matching frame and prompt ownership tests; visual ordinary/stale/unknown checks; #8 real operator recovery. |
| Evidence adapter / #19 | `harness/gameplay/contracts.py`, `harness/gameplay/evidence.py`, new focused contract/evidence tests | Accepted #17; stub-native records in portable tests, native boundary identity for integration. No new hidden-state export. Missing/stale/contradictory/session-reset tests. |
| Observation acceptance / #19 | Dated acceptance manifest, protocol/overview updates only after verification | Evidence adapter + native boundary identity + accepted #8; lead owns real windowed positive/negative observations. Document supported predicates and absence of broader guarantees. |
| Planner port / #22 | `harness/gameplay/planner.py`, planner adapter tests | Contracts/evidence records and #18 evaluation interface; typed candidate/result validation, deadlines, cost reservations and late results. Fixtures are not real-model acceptance. Provider choice/budget must be resolved before any live adapter is Ready. |
| Supervisor / #22 | `harness/gameplay/supervisor.py`, supervisor tests | #20 skills, #21 memory, #18 telemetry and planner port. Exercise all transitions, revocation, budgets, non-progress and honest outcomes. No broad controller rewrite. |
| Run lifecycle integration / #22 | `harness/gameplay/status.py`, `harness/controller.py`, `harness/server.py`, `harness/__main__.py`, lifecycle/controller tests | Supervisor; serialized with recovery ingress and #23 viewer integration. Atomic run lease on every ingress, explicit start/continue/stop, no startup replay, common checks; real gameplay stays #24. |

The contract/evidence implementation is the sole initial owner of shared record schemas;
#20/#21 consume them and request changes through the lead. Avoid two workers editing
`contracts.py` or the controller. Native boundary work and Python evidence records may
run in parallel after review because their agreed schema is fixed and sources disjoint.
Cap implementation at two project-local worktrees; one integrator and one shared-runtime
owner. Version agreement/control-registry updates are integrated by the lead with
native v2; do not leave C-PROTOCOL falsely describing a v1 implementation. For example `.runtime/worktrees/native-boundaries` and
`.runtime/worktrees/gameplay-evidence`, each with a named branch and the exact accepted
design commit as base. These are reserved paths, not worktrees created by this round.

At dispatch, record the then-current base SHA and actual worktree in the issue brief;
workers commit only owned paths, use isolated test output directories and report their
diff/checks/risks. Only the lead installs dependencies, builds/runs CDDA, touches saves
or uses shared caches/ports. Native and controller recovery are sequential because
they share code and protocol semantics. A worker stops after two unsuccessful repairs
or scope drift. No future live run is implied by a Ready issue.

## Acceptance and decisions

Close #6 only after verified pinned-source facts, explicit supported/unsupported cases,
identity/concurrency/error/recovery contract, negative/real-native probe matrix and
bounded implementation ownership are independently reviewed. Native execution remains
unproven and tracked by #8.

Close #17 only after the task, evidence/outcome/skill interfaces, fresh authority,
budgets, model/reuse decisions, evaluation handoff and downstream decomposition are
reviewed together. Model/provider/spend selection remains an explicit gated follow-up;
no credential or financial commitment is silently assumed. No change to the user's
windowed operation, local environment or player-visible-only constraints is requested.

Run `.venv/bin/python tools/check.py`; render and inspect any changed diagram at ordinary
window width. Inspect the staged diff and publish via protected PR/CI. Record candidate,
review findings/resolutions, actual checks and unexecuted lanes in dated acceptance.
Verify live GitHub fields/dependencies after publication; close only #6/#17 when accepted,
record finish dates, and leave implementation/native outcomes open. Re-estimate unknown
work explicitly while preserving the original estimates for learning.
