---
owner: lead
review_trigger: CI profile eligibility, required reporting or evidence reuse changes
status: historical
date: 2026-10-24
scope: Adopted proportional validation rationale; project-management and checker own current requirements
---

# Proportional portable validation

Parent: [project management](../project-management.md#risk-based-assurance) and
[S-DELIVERY](../engineering.md#s-delivery-reproducible-and-isolated-delivery).
[#203](https://github.com/CVX-Hull/enactive/issues/203) owns delivery;
[#26](https://github.com/CVX-Hull/enactive/issues/26) owns subsequent effectiveness
assessment. Current contracts remain authoritative until coordinated migration.
No game, native probe, campaign, global configuration or new test framework is
part of this change. One lead integrates; bounded workers own disjoint paths.

## Responsibility and reuse

The existing checker remains the executor. A small CI adapter chooses among
three named strict profiles from Git/GitHub facts; it is not a test-impact graph,
green cache, provenance journal or semantic classifier. Git owns objects/diffs,
GitHub owns PR/run/job state and required status, unittest owns discovery/duration
reporting, and Mermaid owns rendering. Current source/evidence integrity, ordinary
human-visible CDDA behavior and gameplay acceptance are unaffected.

Retained PR202/main measurements show 2,044 tests taking1191.477s and1134.402s.
Their sum38m45.879s excludes other checks. Buffered log gaps are not individual
test durations or causal attribution. Add standard unittest `--durations 20` and
command elapsed times to existing logs, not another metrics service. Optimize
observed expensive or redundant fixtures only when their actual failure coverage
can be retained; do not replace relevant real-component failures with mocks.

## Checker contract

`tools/check.py` defaults to full and keeps `--fast` as the local development
checkpoint, including its existing calendar-only warnings. A mutually exclusive
`--profile {full,editorial,main-smoke}` selects strict hosted validation. Every
strict profile runs syntax/Ruff/import/JavaScript checks, document metadata/links,
current-date governance without `--development`, whitespace and diagram rendering.

Full additionally runs complete unittest discovery with20 slowest durations and
the Node viewer suite. Editorial runs no runtime tests or viewer suite and says
so explicitly. Main-smoke runs the viewer suite plus these existing cases:

- `tests.test_gameplay_contracts`
- `tests.test_gameplay_evidence`
- `tests.test_mission_request_producer`
- `tests.test_mission_ledger.LedgerTests.test_measured_counts_use_cumulative_rows_and_preserve_unknowns_across_reopen`
- `tests.test_mission_ledger.LedgerTests.test_read_only_or_unadmitted_request_cannot_become_input`
- `tests.test_mission_ledger.LedgerTests.test_terminal_mission_cannot_restart_or_overwrite_result`
- `tests.test_mission_http.MissionHTTPTests.test_semantic_navigation_context_memory_and_single_ingress`

These exercise real temporary evidence/SQLite and synthetic HTTP; no native game
or player inference runs. They are a bounded smoke, never a full portable pass.
Measure their actual duration before freezing the hosted profile. Failure of any
selected check propagates. End messages state executed and unrun lanes accurately.

## CI adapter and editorial eligibility

One always-present `controller` job remains required, with its existing Actions
binding, strict base protection and PR-only cancellation of obsolete runs. PR
triggers explicitly target main, matching the sole protected branch; this makes
the base of a head-matched run unambiguous even when run.pull_requests is empty.
Non-main/unknown events cannot grant a reduced profile. There
is no workflow-level path filter, conditional required job or `continue-on-error`.
The adapter runs in the job and passes one closed profile to the checker; it
cannot turn a selector or execution error into success. Source/control changes
still receive full regression before merge. No arbitrary manual override or
label grants reduced validation.

Use native Git complete diffs, `--no-renames` and NUL-separated paths so both sides
of renames/deletions participate. PR selection compares the event's original
base/head via merge base, not merely the final commit; main compares the event's
before/after. A malformed/unavailable/empty/unsupported comparison selects full
or fails, never editorial. Missing proof is a reason for full, not new recovery
machinery. Symlink/submodule/nonregular changes do not qualify as editorial.

Initial editorial candidates are explicitly bounded: README.md; Markdown under
docs/research*, docs/acceptance/ and docs/changes/; .mmd/.svg and rendered.json in
docs/diagrams/; and ordinary image/video report assets in docs/assets/ or
docs/acceptance/. No Python/shell executable qualifies. All other paths select
full initially. In particular AGENTS, player/prompt guides, protocol, charter,
engineering/project-management/documentation, evaluation, setup/runbook,
configuration, schemas, dependencies, tooling and tests are not editorial by path.
Eligibility does not certify prose truth: the lead still reviews behavioral impact
and evidence. Expand this list only for demonstrated needs and reviewed coverage.

## Eligible main smoke

Only normal single-parent squash pushes to main can reuse full PR coverage. The
main event must add exactly that commit. Use existing GitHub API records to find
the unique merged PR whose merge_commit_sha equals HEAD. Require its recorded
main base SHA to equal HEAD's parent; that base must be an ancestor of its head.
Fetch the retained PR head object with Git and require its tree equal actual HEAD.
Under strict up-to-date protection and the unchanged default PR checkout, the
tested merge result has that same tree. This uses the platform's normal merge
contract rather than parsing checkout logs or manufacturing a check on another SHA.

Require the latest run of the expected check.yml workflow for that exact PR head
to be a completed successful pull_request run, with a completed successful
controller job and a unique completed successful native step named
`Run strict full validation`. The execution step's name includes the selected
profile. This distinguishes a real full run from an editorial success at the
same head whose earlier comparison had a different scope, without an artifact
cache or a new receipt store. Its original created_at must be strictly earlier than the PR's
merged_at; equality, malformed times or a later same-head run choose full. This
binds the main-only run to a base no later than the actual merged parent. GitHub
reruns retain the original SHA/ref, so the original creation timestamp is used.
A passing name or merely associated PR is insufficient. API
run.pull_requests may be empty after merge, as observed on202; head/workflow/event,
PR metadata and Git relationships establish the connection. Do not search past a
newer failed/cancelled/incomplete run for an older green one.

Changes to validation machinery/context force full main too: .github/, all tools/
initially, tests/__init__.py, pyproject.toml, dependency locks/manifests, renderer configuration,
AGENTS and current control/engineering/project-management/documentation policy.
The coarse engineering-tools boundary avoids maintaining a dependency graph of
future checker helpers; narrow it only for demonstrated benefit. Normal feature
regression tests do not by themselves change the workflow context;
they still receive full PR validation. Unknown main paths, nonstandard pushes,
missing/ambiguous API/Git records, source-tree mismatch or known changed validation
context fall back to full. Declare supported Python/Node/runner/dependency context
through existing pinned workflow and lock contracts; do not claim universal
environment equivalence or build an ambient-machine fingerprint service.

Print profile and eligibility reason in normal logs and the Actions job summary.
Main smoke reports that full regression was covered by the linked qualifying PR
run and was not rerun on main. It is a new honest main check, not a copied green
status or a full-main claim. An editorial main diff can independently run strict
editorial validation. The migration itself changes machinery and runs full on
both PR and main.

## Review, verification and maintenance

Review this eligibility boundary before worker implementation. Lead owns
tools/ci.py, its tests, workflow and integration. A checker worker owns only
tools/check.py and tests/test_devtools.py. After interfaces are fixed a separate
documentation worker may own current policy/control files, not CI/checker code.
Use existing managed worktrees, one integrator and at most two implementation
workers. No shared live runtime exists during this work.

Verify real temporary Git diffs/ancestry, closed profiles, complete rename/delete
coverage, strict governance, expired/failed/unknown evidence, latest-run selection,
expected workflow/job and actual command failure propagation. Exercise both cheap
profiles locally with real fixtures and inspect their scope reports. CI/control
migration requires coherent independent review and full protected candidate/main
checks. Hosted qualification must show actual profile execution/reporting and
editorial selection; eligible source-main reduction needs its normal GitHub/Git
qualification, not a fabricated old success or no-op game change.

Migrate AGENTS, S-DELIVERY, project-management/Done, setup, affected runbook and PR
guidance, C-PORTABLE registry/generated map, checker scope tests and workflow
together. CI receipts and live status stay in Issues/Project/PRs. A later dated
report can retain the experiment and limitations; this brief records rationale.
Compare saved time, false selection, failures and maintenance cost at existing
C-MAINTENANCE checkpoints. No new standing control or automatic review-date renewal.
