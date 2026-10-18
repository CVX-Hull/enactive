---
owner: lead
status: active
review_trigger: Round010 implementation, acceptance or publication claims change
---

# Passive waypoint supervision — round 010

This round delivers the passive coordination boundary for
[#35](https://github.com/CVX-Hull/cdda-player/issues/35). One explicit task keeps its
original route and budgets, requests a fresh return plan at the waypoint, and
offers at most one intent awaiting a correlated result. The service still does
not instantiate it. Real controller ownership, lifecycle, native receipt assembly
and provider integration remain #36. No native/model effectiveness is claimed.
The [brief](../changes/010-passive-supervisor.md) records reviewed decisions;
[protocol](../protocol.md#passive-waypoint-supervision) owns current behavior.

## Implementation and review evidence

Base main: `cc5691ccd6574d723e57b9c9ffe2224f95d20511`. Lead shared checkpoint:
`650fb58b048c310ce1cfa618d6e7a6b11d463fa6`.
It replaces the full-leg/count-only API with cardinal skill version 2 and validated
settled route history. No compatibility constructor or old descriptor fallback
remains. No persisted gameplay/evaluation record shape changed. Historical native
drivers/evidence retain their original version and are not current execution tools.

Two independent source sweeps and objective review preceded the detailed brief.
Independent brief review found complete-leg zero-distance planning and detached
non-delivery ambiguities; both were resolved before implementation. Shared migration
review found no code blockers and one stale documentation sentence, now corrected.
Shared checks passed 27 skill tests and 267 total Python tests with the existing
viewer, import, document, diagram and governance controls.

One clean-context worker used an isolated project-local worktree at that shared
checkpoint, owning only supervisor.py and its tests. Lead retained shared modules,
design, documentation, integration and final verification. No game or provider was
launched. Lead inspection added pending-intent expiry and first-revocation-only
operator exemption, then required unresolved attempts in evaluation export.
Documentation review caught an omitted non-delivery readmission rule; it was fixed.
Independent final documentation/visual review found no remaining defects. Lead and
reviewer inspected the final 1000-pixel diagram: readable labels, distinct arrows,
post-step stops and the future production boundary are visible.

Two independent integrated code reviews reproduced five defects: pause at expiry
could grant the wrong retry exception; completed status could reopen; another
world's turn counter could replenish reported turns; fresh verification-only
completion evidence was omitted; and a sticky-disputed original start could reach
the planner. Lead fixed each and added direct regressions. Both independent
rereviews found no remaining blockers. The review-fix test run initially lacked
a deepcopy import in two new fixtures; the import was restored and all passed.

Integrated checks pass **73 focused tests** (46 supervisor, 27 skill) and **313
Python tests** with viewer, four import contracts, document/diagram/governance and
whitespace checks. Source and test review support the following bounded outcomes:

| Boundary | Portable evidence |
| --- | --- |
| Both legs and original history | Complete four-tile outbound/return, eight attempts, nine retained sources; partial continuation on both legs preserves progress and counts |
| Stage decisions | Fresh exact return plan; complete-leg verification bypasses zero-distance planning and retains its fresh final frame |
| Applicability | Stale/replaced/cancelled candidates, A→B→A generations, wrong skill version, session replacement and disputed originals stop |
| Pending effects | Exact/duplicate/conflicting settlement, wait expiry before every mutating API, late non-delivery, unknown/returned late results, pause and abandonment |
| Readmission | First zero stops; equivalent and irrelevant-change signatures cannot retry; first revocation determines the operator exception |
| Budgets and accounting | Original task/leg/turn/wall/planner/spend ceilings; turn overshoot retains progress, wall-overdue effects remain unknown; unresolved attempts export as unknown |
| Evidence and status | Real memory/store bounds, sticky disputes before planning, immutable completed outcome with later integrity diagnostic, no foreign-world turn replenishment |
| Evaluation | One original-port snapshot plus bounded events validates in the real RunRecorder; missing measurements stay unknown |

Protected exact-head PR and merged-main CI remain publication gates at this source
checkpoint. GitHub issue/Project records will record their verified completion.

## Evidence lanes and limitations

Portable tests use synthetic frames retained by the real EvidenceStore, the actual
TaskMemory, asynchronous injected PlannerPort, MovementStage and RunRecorder.
They exercise identity, geometry, counters, cancellations and failure decisions.
They do not execute CDDA, a live model or a production dispatch adapter. Original
native acceptance remains the separate [round009 report](2026-10-17-bounded-skills.md).
No native engine, service, UI, dependency, global configuration or save changed.

Unsuccessful development checks remain distinguishable: a new dispute fixture
first tried to overwrite a deliberately read-only retained frame and was corrected
to explicitly chmod its own temporary fixture; a worker fixture first used a
rejected native-frame basename; a preview command used an unsupported renderer
width flag and was rerun with the installed tool's supported size option. None was
reported as native acceptance. Logs/previews are local under
`.runtime/evidence/round010/`; they are not required to run a fresh checkout.

Remaining limits: a trusted serialized caller supplies native result attribution;
the supervisor cannot prove it. Python provider cancellation is cooperative and
the original physical slot stays occupied until return. Observable signature
changes are a conservative movement policy, not proof of semantic recovery.
Unknown late effects remain unresolved. Decisions have a bounded audit ring;
external Codex/operator effort is not automatically measured.
