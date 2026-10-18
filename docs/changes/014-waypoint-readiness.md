---
owner: lead
status: historical
date: 2026-10-18
scope: Round014 frozen design, implementation allocation and gated readiness decision; current contracts and GitHub own behavior and live work
---

# Waypoint evaluation readiness

The user selected this iteration on 2026-10-18 under
[#16](https://github.com/CVX-Hull/cdda-player/issues/16): policy #53, CI maintenance
#13 and experiment preparation #56. Base: `c79856708371fb5563493a8377baca99c3d67130`.
The [current protocol](../protocol.md) is authoritative. This brief records the
consequential boundaries fixed before worker dispatch and the resulting
[acceptance](../acceptance/2026-10-18-waypoint-readiness.md).

## User consequence and policy decision

An exact move to a waypoint currently stops if the next tile beyond that waypoint
is a cupboard. The step is credited, but the leg cannot complete or request a
return plan. [Round012](../acceptance/2026-10-18-integrated-player.md) retains that
real failure. Choose a narrow repair: **verify the reached target separately from
eligibility to move again**. No new native observation, wire format or permission
is needed. This does not claim unseen terrain, trap safety or general survival.

The shared movement module has two distinct predicates, not two contract versions:

| Predicate | Meaning and consumers |
| --- | --- |
| `current_guard` | Validate direction, unpaused/unfrozen state, current normal-play frame/freshness, known absence of visible creatures and valid current position |
| `guard` | Compose `current_guard` with the existing visible, empty, allowlisted next-neighbor requirement; public walk and every further skill step keep this policy |

The skill additionally requires its registered cardinal action even at completion.
Retained-source integrity, checkpoint/generation, same-session route continuity,
correlated receipt, exact displacement, revision/turn ordering and original budgets
remain mandatory. A source dispute, stale/unknown current frame, threat, pause,
freeze, wrong/unresolved action or overshot budget cannot become completion.
`current_guard` takes the same arguments as `guard`; the latter composes it with
next-tile validation. No weaker mode flag or alternate version is introduced.

Skill proposal and settlement first validate the current boundary. At an exact
fully credited target they may return completed without inspecting a further
neighbor or dispatching another input. Before any remaining step they still run
the full next-neighbor guard. Unknown/blocked *future* terrain is irrelevant to
target verification; unknown current observation/creature visibility still stops.
Evidence ingestion still requires its complete eight-cell schema. A valid
invisible neighbor has `visible=False` and omits its hidden terrain/name/furniture;
a literally absent cell remains invalid evidence, even at a completed target.
The supervisor applies the same distinction when freshly verifying a complete leg
or whole task. Beginning a return leg still checks the actual return direction
before requesting its plan. Public `walk` retains its documented conservative
post-step policy and its existing regression; it is a different operation, not a
fallback implementation of the new skill contract.

## One current skill contract

Advance `cardinal_movement` from descriptor version 2 to **3**, with explicit
current-boundary-at-target and next-neighbor-before-further-step predicates.
Migrate all actual cardinal candidate producers/fixtures, accepted descriptor
consumers and current guidance together. Generic record/descriptor tests for
independently supplied capabilities are not old cardinal runtime readers.
Test that an old version-2 cardinal candidate rejects; no alias, flag or adapter.
Task/plan record shape, native-v3, evidence-store v2 and evaluation/1 do not change.
Stop active writers before deployment; no task, lease or journal is restored.
Preserve historical v2 acceptance and unknown outcomes as evidence. No save format
changes or source deletion. Reversal needs a coherent reviewed deployment and
fresh acceptance, never mixed descriptor versions or an old-reader fallback.

## Hosted workflow maintenance

Use the current official releases, verified against GitHub commit identities and
immutable `action.yml` runtime declarations on 2026-10-18:

| Action / official release | Full commit pin |
| --- | --- |
| [checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1) | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| [setup-node v7.1.0](https://github.com/actions/setup-node/releases/tag/v7.1.0) | `949feb2413d6458794dcd2491c4babbbce0c15c1` |
| [setup-python v7.0.0](https://github.com/actions/setup-python/releases/tag/v7.0.0) | `5fda3b95a4ea91299a34e894583c3862153e4b97` |

All declare Node24 action runtime. This is separate from the project's Node22 and
Python3.14 selections, which stay unchanged. Keep ubuntu-24.04, `controller`,
push/pull_request triggers, read-only permissions, project-local setup/caches and
Chromium confinement setup. Do not opt out of migration or weaken checks. Hosted
runner minimum and observed warning resolution are verified in CI, not assumed
from local tests. No new global Mac setup or application-language upgrade.

## Implementation allocation

At most two workers are allowed; this slice needs one. Three verified workflow-pin
replacements are mechanical, so the lead performs them rather than adding a second
writer. Read-only research has already run in parallel. One integrator owns all
shared docs/contracts, runtime scheduling and final acceptance.

| Owner | Exclusive paths / responsibility | Check |
| --- | --- | --- |
| Movement worker | `harness/movement.py`, `harness/gameplay/skills.py`, `tests/test_movement.py`, `tests/test_gameplay_skills.py` in a separate project-local worktree | Target-before-wall/cupboard/schema-valid invisible neighbor; intermediate blocked/unknown still stops; current threat/stale/paused/frozen/action/source/displacement/budget guards; all cardinal directions; no extra proposal |
| Lead | Supervisor current-versus-next predicate, actual cardinal fixture migration, workflow, current docs/control records and readiness brief | Integration/regression checks; v2 candidate rejection; exact native and hosted evidence |
| Clean-context reviewers | Read-only design/diff/changed tests and readiness decisions | Challenge guard weakening, version migration, authority and unsupported efficacy claims |

Worker receives exact reviewed base, worktree, interface and commands at dispatch;
read-only root interpreter with private worktree caches/output. No native/runtime,
dependency or shared-doc edits. After two failed repairs/ownership drift, hand back.

## Evaluation preparation and bounded exit

#56 inventories real primitive/skill paths, recorder export, timing, model identity
and missing costs; schema condition names alone are insufficient. Preserve the
[round007 protocol](007-recovery-evaluation-monitoring.md#waypoint-experiment-protocol)
until a reviewed explicit revision. It implies at least 40 arm-runs for two
conditions, or 60 with an optional third, before feasibility changes. Do not run
that experiment here. Inspect legitimate visible starts, failed/censored attempts,
development/held-out separation and acquisition/stop rules; do not edit saves or
manufacture native resets. External chat identity/usage remains unmeasured.

Publish a reviewed execution-ready OR explicitly gated gap decision, with bounded
true blocker children and a revised #24 estimate. No new paid provider or spending
is selected. Readiness work can finish with unresolved implementation/configuration
gates; #24 cannot become Ready or claim same-model/cost superiority from that result.

## Execution-readiness decision

**Gated: the deciding experiment is not executable yet.** Inspection on 2026-10-18
found the following boundaries. This is an implementation inventory, not an
efficacy result or a new experiment protocol.

| Area | Implemented evidence | Remaining gate |
| --- | --- | --- |
| Bounded skill arm | `harness/runtime.py` connects external requests, supervisor, lease, native receipts and retained evidence; this increment exercises actual round trips | Native functional probes do not constitute comparative trials |
| Matched primitive arm | `controller.py` exposes registered primitives; `evaluation.py` accepts condition labels | No integrated primitive-choice arm with matched admission, budgets, outcomes and provider interface; public `walk` is not that baseline |
| Recording | Controller events, supervisor accounting and standalone `RunRecorder` exist | Runtime does not assemble a complete evaluation manifest, physical cutoff/final outcome and validated exclusive export |
| Trial acquisition | Real visible starts and failures are retained | No frozen four-family/five-repeat catalog, development/held-out acquisition procedure or feasible matching evidence |
| Model and measurement | Active chat can author bounded functional proposals | Actual identity/token/subscription cost is unreported; no verified same-model configuration or complete cost measurement lane |

Three bounded blockers are tracked under #24:
[#72 matched-arm contract/execution parity](https://github.com/CVX-Hull/cdda-player/issues/72)
(M/Low, provisional 2–4 focused sessions);
[#73 runtime evaluation adapter](https://github.com/CVX-Hull/cdda-player/issues/73)
(M/Medium, 2–3 sessions); and
[#74 trial catalog/model-measurement decision](https://github.com/CVX-Hull/cdda-player/issues/74)
(M/Low, 2–4 sessions).
Each includes review, integration and its own validation; these are planning ranges,
not elapsed commitments or additive team forecasts. Freeze interfaces and acceptance
before dispatch; keep the runtime writer serial. The catalog decision may proceed
in parallel with source work, but trial release must inspect the final arms/export.
Unavailable families require a prospective reviewed protocol revision, never a
passing fixture substitution or deletion after observing outcomes.

#24 remains L/Low and blocked. Its previous numeric estimate is superseded by these
preparation ranges plus an unestimated native acquisition/trial phase: at least
40 arm-runs, or 60 with the optional third condition, plus failed/censored attempts
and review. Measure pilot throughput before forecasting elapsed trial time. Preserve
round007's limits, family separation, harms/success thresholds and gain criterion;
this decision changes none of them. No deciding trial is authorized by readiness.

The future measurement decision must verify common model/configuration identity
and observation/action access, and disclose imperfect starts and missingness. A
paid API needs a separately authorized provider/model and spending ceiling. A
prospective latency-only revision is possible if justified and reviewed before
trials, with no cost-superiority claim. Missing usage is not zero cost; replay cannot
label an unexecuted action. Same-model role separation remains optional and gated.

## Acceptance and maintenance

Run focused movement/supervisor/runtime/CLI tests, common checks, independent
guard/test/workflow review and staged-diff inspection. Separately run real windowed
target-near-cupboard completion/return and an intermediate-obstacle stop on the
ordinary service, plus an operator pause/stale-proposal boundary if feasible.
Record unavailable native cases; fixtures cannot substitute for a failed probe.
No engine rebuild is expected because the native source/binary is unchanged;
verify its installed hash. Save/quit normally, preserve failures and cleanup only
identified owned processes. The initial UI lock report was contradicted by the user;
subsequent actual browser access worked. Record automation-access failures separately
from desktop state or native gameplay failures.

Verify exact PR and merged-main CI, warning resolution, active required checks and
merged-tree identity. Record scoped maintenance effectiveness without renewing
unrelated due dates. Track the next owner/trigger before closing #13; research
review remains #26's October24/event trigger. Update GitHub acceptance only after
all required lanes pass; merge alone is not Done. Cleanup owned worktrees/branches
after preserving handoffs and evidence. Proposed M/Medium 3–6 sessions includes
review/integration/rework/validation, excludes elapsed waits and full trial runtime.
Stop/split/re-estimate for native protocol redesign, unavailable acceptance or
comparison implementation exceeding preparation scope. No memory #70/#71, generic
monitor, new model tier or training is added to this iteration.
