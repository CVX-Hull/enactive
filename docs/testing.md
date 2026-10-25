---
owner: maintainer
review_trigger: Test responsibility, scope or runner changes
status: active
---

# Testing: responsibilities, selection and overlap

Start from the affected [component responsibility](architecture.md), then its
contract and tests. [Engineering](engineering.md#s-code-maintainable-implementation)
owns test requirements; [delivery policy](project-management.md#protected-ci-profiles)
owns checkpoint and protected CI decisions. This guide explains how to choose and
review coverage. It is neither a test inventory nor a record of passing runs.
The adopted source contract below does not establish that any particular hosted
candidate, merged main tree, native build or campaign has qualified.

## What the test families add

The links are representative entry points, not an exhaustive execution manifest.
A fixture's own assumptions and each assertion determine the supported claim.

| Responsibility and parent view | Concrete entry points | Added evidence and limits |
| --- | --- | --- |
| Passive contracts and retained observations — [mission execution](components/mission-execution.md) | [gameplay contracts](../tests/test_gameplay_contracts.py), [evidence](../tests/test_gameplay_evidence.py), [timeline](../tests/test_gameplay_timeline.py), [ordinary evidence](../tests/test_ordinary_evidence.py) | Schema, provenance, retained files, chronology and malformed-data boundaries. Synthetic observations and PNGs establish no real game identity or reload. |
| Pure request composition — [player interface](components/player-interface.md) | [producer](../tests/test_mission_request_producer.py), [producer integration](../tests/test_mission_request_producer_integration.py), [bindings](../tests/test_mission_request_bindings.py) | The pure producer preserves explicit intent and binds selected sources/limits without mutation. Integration checks those products against the actual writer/controller/storage with synthetic native UI; fixture adoption assumptions still apply. |
| SDK, player tools and presentation — [player interface](components/player-interface.md) | [client](../tests/test_mission_client.py), [PlayerTools](../tests/test_player_tools.py), [MCP](../tests/test_player_mcp.py), [image presentation](../tests/test_player_image_presentation.py), [decision view](../tests/test_player_view.py) | Staging, original collection, transport uncertainty, selected snapshots, framing and image/view projection. Some fixtures use real local HTTP/runtime; controlled clients and hosts remain doubles. Actual loaded host schemas, visible images and useful player continuation require separate qualification. |
| Mission writer, phase and authority composition — [mission execution](components/mission-execution.md) | [runtime](../tests/test_mission_runtime.py), [HTTP](../tests/test_mission_http.py), [creation](../tests/test_mission_creation.py), [handoff](../tests/test_mission_handoff.py), [activities](../tests/test_mission_activities.py), [recovery](../tests/test_mission_recovery_collection.py) | Queue/phase transitions, original budgets, Pause, lifecycle and uncertain delivery. HTTP tests exercise real sockets/server/core, with a synthetic native bridge; some core scenarios explicitly pre-adopt identity. They do not qualify actual character creation, Save or succession. |
| Durable accounting and receipts — [mission execution](components/mission-execution.md) | [mission ledger](../tests/test_mission_ledger.py), [ordinary ledger](../tests/test_ordinary_ledger.py), [request receipts](../tests/test_request_receipts.py), [delivery evidence](../tests/test_mission_delivery_evidence.py) | Real SQLite/filesystem integration, constraints, rollback, reopening, cumulative counts and unknown effects. Persistence assertions cannot establish native dispatch or game success. |
| Controller and owned-process boundary — [native control](components/native-control.md) | [controller](../tests/test_controller.py), [ordinary input](../tests/test_controller_ordinary_input.py), [process](../tests/test_native_process.py), [activity control](../tests/test_mission_activity_control.py) | Real controller/file transport and ownership/revocation logic against a fake bridge; process tests use controlled subprocess handles. These detect host-side regressions without launching or qualifying CDDA. |
| Native receiver/capture component — [native control](components/native-control.md) | [receiver](../tests/test_native_receiver.py), [capture](../tests/test_native_capture.py), [input data](../tests/test_native_input.py) | Receiver/capture tests compile extracted production C++ bodies with explicit renderer/JSON/input doubles and execute fault scenarios. Source-anchor and Python input-validation assertions add narrower drift/data checks. This is not a full patched CDDA build or SDL/graphical acceptance; unavailable compilers produce explicit skips. |
| Visible policy, navigation and ordinary interfaces — [native control](components/native-control.md) | [movement](../tests/test_movement.py), [navigation](../tests/test_navigation.py), [skills](../tests/test_gameplay_skills.py), [ordinary loop](../tests/test_ordinary_input.py), [item selectors](../tests/test_gameplay_interactions.py) | Pure eligibility/planning and observation-conditioned feedback over visible fixtures, including an independently shaped ordinary interface. Synthetic unfamiliar labels do not qualify a second real game or general survival strategy. |
| Memory, advice and executable procedures — [memory/learning](components/memory-learning.md) | [memory](../tests/test_gameplay_memory.py), [procedures](../tests/test_procedures.py), [program execution](../tests/test_program_execution.py), [reflection ledger](../tests/test_reflection_ledger.py), [advisory preflight](../tests/test_advisory_preflight.py), [library](../tests/test_procedure_library.py) | Provenance, revisions, retrieval, advisory bookkeeping, archive closure and real JavaScript execution through a writer with synthetic transport. They do not prove useful organic learning, causal benefit or model/game efficacy. |
| Host operation and evaluation tooling — [observer operations](components/observer-operations.md) | [campaign host](../tests/test_campaign_player.py), [host status](../tests/test_host_status.py), [evaluation](../tests/test_evaluation.py), [study runner](../tests/test_memory_study_runner.py) | Mechanical host continuity, passive status, metric/report integrity and controlled studies. Fake processes and synthetic accounting are not independent host or campaign outcomes. |
| Spectator and server presentation — [observer operations](components/observer-operations.md) | [server](../tests/test_server.py), [viewer](../tests/test_viewer.cjs) | HTTP presentation/authentication and production viewer JavaScript under controlled DOM/image decoding and delayed responses. The Node viewer fixture does not prove real browser rendering, accessibility or physical display latency. |
| Engineering controls and preparation — [delivery policy](project-management.md#protected-ci-profiles) | [CI selection](../tests/test_ci.py), [governance](../tests/test_governance.py), [documents](../tests/test_documents.py), [diagrams](../tests/test_diagrams.py), [setup](../tests/test_setup.py), [tool configuration](../tests/test_devtools.py) | Selector evidence, failure handling, metadata, bounded source forms, rendered-output freshness and setup/configuration boundaries. Passing metadata or source checks does not prove prose truth; setup fixtures do not build or launch the game. |

True game qualification starts with matching prepared native source/build and
finite [native/operator procedures](runbook.md), then retained visible outcomes
against [evaluation criteria](evaluation.md). A source test, compiled component,
full native build and real gameplay are separate evidence lanes. Preserve failed
runs and unexercised branches; passing another lane cannot relabel them.

## Select checks from the changed responsibility

Use the [development checkpoint](project-management.md#minimum-checks-and-escalation)
for fast structural checks plus focused behavioral and failure cases. Follow the
flow across changed producer/consumer boundaries, rather than selecting only the
module with the edited line. A local focused pass supports its named scope.

The executable selection source is [tools/ci.py](../tools/ci.py):
`ROOT_DOCUMENTS`, `COMPONENT_PATHS`, `COMPONENT_TESTS` and `SMOKE_TESTS` define the
closed sets. [tools/check.py](../tools/check.py) executes them;
[check.yml](../.github/workflows/check.yml) supplies hosted events and the required
job. Change those manifests together with the relevant selector/behavior tests;
this guide deliberately does not copy their exact test target lists.

| Selected scope | Responsibility and boundary |
| --- | --- |
| Editorial | The five root Markdown documents in `ROOT_DOCUMENTS`, all Markdown under `docs/`, and the existing permitted report/diagram assets. Strict structure, current-date governance and diagram checks still run; prose meaning and changed behavioral claims still need review. Arbitrary new asset classes are not implicitly eligible. |
| Movement or viewer component | Only a complete comparison contained in one explicit component boundary, with permitted editorial changes, selects its component suite plus representative boundary smoke. This is a maintained allowlist, not inferred dependency analysis. |
| Full | Broad/shared source, state/authority, CI, dependencies, schema, unknown paths or changes outside an admitted component boundary require full PR regression. Unknown or incomplete selection evidence falls back to full; execution failures fail the job. |
| Main-smoke | Only separately proven applicable full PR coverage for the same candidate tree permits this bounded post-merge lane under the delivery policy. It does not rerun full regression. Eligible editorial/component changes have their own selection rules. |

The portable runner uses the existing `unittest` cases through pytest **9.1.1**
and pytest-xdist **3.8.0**, pinned in [requirements-dev.lock](../requirements-dev.lock).
Full/component profiles use four workers: full uses built-in `worksteal` to
balance heterogeneous cases, while components use `loadfile`. Main-smoke uses
zero workers. Work stealing can repeat class setup on different workers; the
compiled native fixtures allocate unique temporary builds. File grouping preserves
within-file locality, not isolation of shared runtime resources. Worker restart is disabled, so a crash
remains visible. The viewer command remains a separate Node check. Native build
and real gameplay are outside these profiles. Exact commands and worker settings
belong in the runner, and hosted qualification requires actual candidate results.

## Advisory assurance trace pilot

Three registered pytest markers link a small source-test sample to existing
[C-RUNTIME](controls.md#c-runtime--live-authority-and-input-guards-runtime)
obligations. [C-PORTABLE](controls.md#c-portable--portable-regression-lane-automatic)
remains the regression executor. These markers support review navigation and
opt-in selection; they do not change production CI routing or define whole-source
coverage. The table follows risk → invariant → control → verification marker.

| Product risk | Invariant and parent contract | Control → marker |
| --- | --- | --- |
| Context projection erases authored evidence or mutates retained detail | Project only known binding slots; preserve authored values and isolate copies. [Player interface](components/player-interface.md#context-and-failure-boundaries). | C-RUNTIME → `assurance_context` |
| Invalid durable support or lost evidence revives an old possession claim | Reject forward/cyclic dependencies; unavailable newest evidence stays unknown after SQLite reopen. [Memory/learning](components/memory-learning.md#failure-bounds-and-ownership), [memory contract](protocol.md#ordinary-discovery-and-procedure-data). | C-RUNTIME → `assurance_memory` |
| A refreshed render retargets input, or changed authority permits dispatch | Keep the original non-image capture; reject changed session, revision or boundary at preflight. [Native control](components/native-control.md#internal-responsibilities), [ownership contract](protocol.md#controller-run-ownership). | C-RUNTIME → `assurance_freshness` |

The six existing cases retain their original assertions. Context cases use
synthetic records and a controlled client; memory cases exercise real SQLite and
retained files with synthetic observations; controller cases use a fake native
bridge. These assumptions bound the claim to those host-side contracts. Passing
them establishes no actual-game outcome, loaded host schema, native capture or
whole-repository semantic coverage. The component contracts own the detailed rules.

Use pytest's registered metadata and strict marker validation directly:

```sh
.venv/bin/python -m pytest --markers
.venv/bin/python -m pytest --strict-markers --collect-only -q tests/test_player_view.py tests/test_campaign_memory.py tests/test_controller.py -m 'assurance_context or assurance_memory or assurance_freshness'
.venv/bin/python -m pytest --strict-markers -q tests/test_player_view.py tests/test_campaign_memory.py tests/test_controller.py -m 'assurance_context or assurance_memory or assurance_freshness'
```

Collection lists actual node identities; it does not prove an invariant was
exercised. Review marker membership against assertions when these contracts or
fixtures change under existing [C-REVIEW/C-MAINTENANCE](controls.md) ownership.

For a machine-readable inventory of actual node identities, registered marker
descriptions and known control references, use the opt-in adapter:

```sh
.venv/bin/python tools/testing_pilots.py trace --out .runtime/iterations/verification-pilots/trace
```

`trace.json` joins existing pytest metadata with the existing control registry.
It does not infer semantic coverage or supply an independent test oracle. The
maintainer owns marker membership; reassess on changed contracts/assertions and
retire this glue if a maintained tool supplies the same useful navigation.

## Advisory test-impact experiment

[The research synthesis](research-engineering.md#risk-assurance-and-precise-test-selection--2026-10-25)
separates assurance traceability from dependency selection. The opt-in
[pilot recipe](../tools/testing_pilots.py) freezes a clean committed tree through
Git archive. Its fixed cohort combines original Python, governance and compiled
native-component tests with labelled module/re-export, subprocess and viewer
wrappers. The actual Node viewer oracle runs through a supplemental pytest
wrapper; this does not qualify real rendering or whole-repository selection.

Install the [separate locked environment](setup.md), then run each backend as an
independent trial with a fresh output directory:

```sh
.venv/bin/python tools/testing_pilots.py evaluate --python .runtime/tooling/verification-pilots-venv/bin/python --backend default --out .runtime/iterations/verification-pilots/default
.venv/bin/python tools/testing_pilots.py evaluate --python .runtime/tooling/verification-pilots-venv/bin/python --backend ctrace --out .runtime/iterations/verification-pilots/ctrace
```

The recipe retains commands, environment, exact faults/expected targets, public
pytest hook reports, plain/cold/warm costs, map size and per-fault results. It
restores source, generated state and a pristine SQLite map at the same path before
each independent fault. Ordinary execution must first confirm the expected
test-call failure; setup/collection errors, skips and timeouts remain unqualified.
An omitted confirmed failing target is a miss, even when nothing is selected.
Do not credit unrelated failures or all-green agreement as detection recall.

These are single, cohort-only measurements. Full-source instrumentation,
dependency upgrades and actual gameplay remain outside their claim. Preserve
backend failures without silently changing coverage mode or third-party code.
Maintainer/lead reviews misses and total setup/execution/map-upkeep cost under
existing C-REVIEW/C-MAINTENANCE; reassess on tool/dependency/contract changes or
cost regressions and retire uneconomic glue. Production CI still uses its existing
explicit scopes; any adoption needs a separate evidence-supported decision.

The [2026-10-25 pilot assessment](acceptance/2026-10-25-verification-pilots.md)
adopts the small assurance trace and defers testmon routing after observed misses.
The CLI exits unsuccessfully on unsupported maps or unconfirmed cases even when
other comparisons are valid; inspect the retained denominators and results.

## Review overlap by failure responsibility

“No duplicate test IDs” means discovery found distinct identities. It says nothing
about whether different tests assert the same behavior. Conversely, matching
inputs or error names do not make tests redundant. Discovery counts, parametrized
case counts and passing totals are not semantic coverage measures.

For example, the producer can reject a malformed selected source before staging;
PlayerTools must preserve the chosen snapshot through SDK/HTTP collection; the
runtime must reject stale authority at admission or dispatch. Similar source or
limit data at those three boundaries exercise different obligations. The
[producer integration cases](../tests/test_mission_request_producer_integration.py)
check that independently valid pieces compose. Removing all but one would leave
boundary wiring, authority timing or transport uncertainty untested.

Put exhaustive malformed-data and deterministic fault matrices at the lowest
responsible layer. Keep representative successful, refusal and uncertainty flows
across consequential boundaries. Before adding or removing a case, identify the
regression it detects, the component that owns it, what other cases already prove,
and whether the same failure can escape at another boundary. Consolidate only
when setup, stimulus, observed contract and failure boundary are equivalent.
Retain a regression for an escaped defect at its actual failure boundary.

## Keep state, clocks and cost honest

Each test and each independent fault mutation needs fresh mutable state. Reuse
immutable builders or fixture code through ordinary `unittest`, `tempfile` and
`shutil`; do not share writable ledgers, source copies, ports, process handles or
authority across cases/workers. Close writers, join owned threads and release
handles through cleanup. A collected result alone does not establish quiescence.
Copy only files the exercised path reads, while retaining real required source,
schemas, referenced-file checks and baseline validity assertions.

The [governance fixture change](https://github.com/CVX-Hull/enactive/issues/223)
is one bounded example: it retained all 28 original test bodies, copied only
required files and isolated single-manifest faults from unrelated archive
validation. Full-corpus CLI/fresh-clone checks remain. Its measured local saving
is evidence for that cohort, not a CI speed promise or permission to skip checks.

Separate deterministic clock logic from actual scheduling. Use a controlled
component clock for expiry arithmetic and events/barriers for causal ordering;
keep real bounded watchdogs and selected real thread/socket/lock checks. See
[activity control](../tests/test_mission_activity_control.py) and
[client collection](../tests/test_mission_client.py). Do not let unrelated fixture
setup consume the deadline being tested, replace a concurrency guarantee with a
sleep, or relax a deadline merely to hide contention under parallel execution.
Real elapsed-time performance measurements need their declared host, load,
cohort, conditions and retained failures; a fake-clock pass is not a latency result.

An asynchronous SDK's initial wait is a convenience, not a settlement guarantee.
Functional fixtures must collect the same original operation through its supported
bounded API before asserting its terminal state; never resubmit input to finish
it. Exercise an intentionally pending writer with causal synchronization. Keep
explicit latency acceptance separate from fixture polling allowances, and retain
real watchdog failures for diagnosis instead of increasing them without evidence.

Review slow setup, repeated unchanged archive validation, excessive sleeps and
repeated high-level fault matrices against the value they add. Measure the bounded
cohort before/after; retain failure assertions and identify omitted coverage.
Existing [C-REVIEW and C-MAINTENANCE](controls.md) cover new tests, removal,
responsibility/runner changes, recurring failures and disproportionate cost.
Update the affected component view and executable scope where needed, and record
findings in the existing issue/PR. No second coverage registry, duplication
framework or passing-result cache is required.
