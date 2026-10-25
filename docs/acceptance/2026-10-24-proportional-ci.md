---
owner: lead
review_trigger: Interpreting or repeating the proportional CI qualification
status: historical
date: 2026-10-24
scope: Offline CI and test-maintenance evidence; linked PRs own final publication receipts
---

# Proportional CI qualification

This evaluates [#203](https://github.com/CVX-Hull/enactive/issues/203) with gameplay
and native game probes paused. [Current profile policy](../project-management.md#protected-ci-profiles)
owns eligibility; [brief 065](../changes/065-proportional-ci.md) retains the adopted
rationale and research assessment. This report records observations, not another
copy of the selector contract or a live task queue.

## What was exercised

[PR #204](https://github.com/CVX-Hull/enactive/pull/204) changes the checker, workflow,
selection logic and current control guidance. It therefore requires full portable
validation on both PR and main. [PR #205](https://github.com/CVX-Hull/enactive/pull/205)
changes only one regression fixture; it requires full PR validation and can reuse
that coverage on main only when normal Git/GitHub evidence establishes eligibility.

| Hosted check | Actual profile | Unittest cases / reported seconds | Checker seconds |
| --- | --- | --- | ---: |
| [Migration PR](https://github.com/CVX-Hull/enactive/actions/runs/40141947529) | full | 2,065 / 1,086.294 | 1,116.07 |
| [Migration main](https://github.com/CVX-Hull/enactive/actions/runs/40143315104) | full | 2,065 / 1,131.408 | 1,168.75 |
| [Fixture PR](https://github.com/CVX-Hull/enactive/actions/runs/40143345371) | full | 2,065 / 1,081.024 | 1,118.09 |
| [Fixture main](https://github.com/CVX-Hull/enactive/actions/runs/40144661223) | main-smoke | 111 / 3.550 | 41.30 |

The fixture merge 9f5c822 has the same Git tree as candidate 462b4e0. The actual
main selector chose main-smoke and linked full PR run 40143345371; its native
`Run strict main-smoke validation` step completed successfully. The migration's
native full steps succeeded on both PR and main. These are observed hosted
selections, not only selector fixtures.

The publication PR for this historical report owns its subsequent strict editorial
PR/main receipts; #203 links those actual results. Editorial success does not claim
runtime/viewer regression. Main-smoke explicitly reports full regression as unrun
on main and links the qualifying full PR run. Every strict profile retains
current-date governance, structural/document checks and diagram validation.

## Measured fixture improvement

The original integration regression sent 188 synthetic inputs to cross the default
512-node map boundary. Its PR #204 case duration was 66.657s, the largest reported
case. The replacement sends 38 inputs at the existing supported 32-node capacity,
using the real ObservedMap and unchanged runtime/controller/evidence/SQLite path.
It still crosses eviction, retains every per-input ACK/evidence/accounting and map
identity check, and performs useful guarded navigation afterward. It additionally
asserts that the cache reaches its exact configured capacity. The separate map
regression still exceeds 512 coordinates with the production default and verifies
retained frame bytes, forgotten/current routes and reobservation.

Sequential local single-case samples on the existing project environment were
29.455s before and 4.936s after, about 83% lower. All 71 runtime cases passed in 31.314s;
all 46 navigation cases passed in 1.532s, including default 512 coverage. No other
project test/render job overlapped the paired samples; ambient host load was not
controlled. These are development measurements, not a latency distribution or a
causal suite-wide speedup estimate. Earlier loaded samples 26.965s and 28.375s are
retained but excluded from this pair. The hosted replacement case took 7.230s in
PR #205; this is a separate runner observation, not a controlled host comparison.

## Review, limits and maintenance

Independent clean-context boundary/code review challenged same-head wrong-base
coverage, an editorial success masquerading as full coverage, skipped/cancelled
steps, changed package/bootstrap context and wrong checkout identity. The final
selector requires a native successful full-profile step for source-main reuse;
wrong checkout fails rather than pretending full checks validate another source.
Real temporary Git histories and bounded API fixtures exercise complete diffs,
rename/delete/modes, source/base/tree mismatch, missing/latest failed evidence and
profile failure propagation. Those negative cases are source tests; they are not
claims that every fault was injected into hosted Actions.

Official checksum-verified actionlint 1.7.12 validated the workflow. Existing Git,
GitHub, unittest, pinned dependencies and the checker provide the machinery; no
custom success cache, test-impact graph, provenance service, new test framework
or global installation was introduced. Main still requires the Actions-owned
controller (app 15368), strict up-to-date checks and protected squash integration.
Control maintenance/exercise dates were not automatically renewed.

The final local editorial check initially could not launch the project-owned
headless Chrome inside the execution sandbox. Retrying the same command outside
that sandbox passed in 14.80s, without changing browser flags or global settings.
Both logs are retained; neither attempt claims runtime or gameplay coverage.

PR #202's earlier full PR/main pair reported 2,325.879s of unittest execution, excluding
other checks. Different hosts, source and scope prevent attributing aggregate timing
differences here to faster test execution. Reduced profiles intentionally execute
less work under declared eligibility; their success is not equivalent to running
all tests again. [Maintenance #26](https://github.com/CVX-Hull/enactive/issues/26)
retains subsequent effectiveness review and measured lifecycle-fixture candidates.
No broad optimization, sharding or clock-mocking campaign is implied.

Private logs and native API receipts remain project-local under
`.runtime/iterations/proportional-ci-203/`. Public run links above own the hosted
results. No CDDA save, world, engine behavior, player interface, model configuration,
full-campaign acceptance or apparent gameplay responsiveness was changed or qualified.
