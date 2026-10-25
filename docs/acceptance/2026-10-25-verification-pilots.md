---
owner: lead
review_trigger: Interpreting or repeating the advisory verification pilots
status: historical
date: 2026-10-25
scope: Offline assurance navigation and finite test-impact experiment; PR owns protected publication receipts
---

# Verification pilots: useful trace, unsuitable selector

[#225](https://github.com/CVX-Hull/enactive/issues/225), with children
[#227](https://github.com/CVX-Hull/enactive/issues/227) and
[#228](https://github.com/CVX-Hull/enactive/issues/228), delivers two advisory
pilots. Keep the small pytest assurance trace for review navigation. Defer testmon
as a production CI selector: the declared CTracer trials each detected two of
seven independently confirmed faults and missed five. Production CI selection,
branch protection and gameplay behavior remain unchanged.

[Current testing guidance](../testing.md) owns use and upkeep;
[the earlier research](../research-engineering.md#risk-assurance-and-precise-test-selection--2026-10-25)
owns source assessment. This report and its [sanitized measured payload](2026-10-25-verification-pilots-measurements.json)
retain observations and limitations, not a new risk registry or delivery policy.

## Assurance trace

Three native pytest markers connect existing C-RUNTIME obligations to six original
tests covering context/copy isolation, durable memory/support and source loss, and
capture/input-authority freshness. The existing test bodies and assertions stayed
unchanged. Strict collection selected exactly six identities; executing them passed
six tests and four subtests. The generated trace contained all six, recognized
C-RUNTIME and reported no unknown control references. C-PORTABLE remains the test
executor, distinct from the runtime controls being exercised.

The integrated focused run passed 196 tests and 616 subtests before the adapter
regressions were added; the final focused pilot-tool run passed 11 tests and
11 subtests. Independent source review verified the six associations, unchanged
function bodies, optional-lock isolation and failure/status handling. These are
host-side fixtures, including real SQLite; they establish no actual-game outcome,
whole-repository semantic coverage or complete assurance case.

## Experiment and independent faults

The [versioned recipe](../../tools/testing_pilots.py) froze clean Git commits into
owned archived copies. Each fault used the same working path with pristine source,
supplemental files, generated state and a closed SQLite map restored independently.
Bytecode writes were disabled. Ordinary no-plugin execution first tested a frozen
expected target; testmon then selected from the fixed eleven-test cohort using
`--testmon-forceselect`. Ground truth did not come from the selector.

Local host: macOS 26.6.2 arm64, Python 3.14.7, pytest 9.1.1, testmon 2.2.0,
Coverage.py 7.17.0, Node 26.9.0 and Apple Clang 21.0.0. Optional packages lived
only in the separate project-local environment. Its lock retained all 44 normal
development pins and added only testmon/Coverage.py. Normal development and CI
environments received neither optional package. No third-party internals changed.

| Fault | Independent ordinary target | CTracer result in both trials | Fidelity |
| --- | --- | --- | --- |
| Remove context defensive copy | Original copy-isolation assertion fails | Detected; two context tests selected | Real Python function, synthetic records |
| Disable durable dependency-order check | Original cycle test still passes | Unconfirmed; excluded from recall | Later cycle rejection still preserves this observed contract; the mutation is not an established regression |
| Retarget original capture to current render | Original capture-binding assertion fails | Detected; two controller tests selected | Real Python input binding with fake native transport |
| Empty registry owner | Original governance-validity assertion fails | Missed; zero tests selected | Real JSON/schema input |
| Change native wire protocol | Original wire/source assertion fails | Missed; zero tests selected | Real C++ source read by a test with a compiled component fixture; no full native app |
| Change viewer protocol | Existing Node viewer oracle fails through wrapper | Missed; zero tests selected | Real JS/Node oracle, labelled supplemental pytest wrapper |
| Remove package re-export | Supplemental export assertion fails | Missed; zero tests selected | Constructed module/import boundary |
| Change subprocess output | Supplemental stdout assertion fails | Missed; zero tests selected | Constructed Python subprocess, not a dependency-upgrade qualification |

Each CTracer trial has eight attempted cases, seven confirmed comparisons, two
detections, five misses, one unconfirmed mutation and zero infrastructure errors.
The two trials are repeats of the same small cohort, not fourteen independent
faults. Selected-but-green or empty selection does not become a successful
detection; unrelated failures receive no credit. No full-source recall is known.

## Original failures and measured cost

The initial default-backend trial at `b18eaa6` exposed an adapter bug: testmon's
synthetic deselection objects lack `nodeid`. Warm/selected execution raised
`AttributeError`; all seven confirmed cases were unqualified, not misses. That
trial and its 18.179s cost remain retained. The adapter now counts anonymous
deselections without fabricating identities, with a regression check.

Coverage.py also warned `no-sysmon-context`: dynamic contexts are unsupported
with Python 3.14's default `sysmon` core. The corrected recipe captures that public
pytest warning and refuses to qualify the map, even though the cold tests pass.
Corrected default trials at `12c479c` and `cbaeb65` stopped before seed comparisons
in 4.168s and 4.631s. No automatic fallback or default-backend recall claim follows.
CTracer was explicitly requested as its own declared experiment.

| CTracer sample / source | Plain cohort | Cold instrumentation | Unchanged warm selection | Entire experiment |
| --- | ---: | ---: | ---: | ---: |
| First / `12c479c` | 1.903s | 2.547s | 0.675s, zero selected | 17.981s |
| Repeat / `cbaeb65` | 1.644s | 2.281s | 0.566s, zero selected | 17.880s |

These command timings include Python/pytest startup and fixture costs. In the
repeat, commands totalled 14.906s; 2.974s remained for aggregate archive/copy/map
reset/report work. That residual is not an isolated SQLite upkeep benchmark or
human maintenance estimate. Each pristine map occupied 69,632 bytes; each retained
CTracer experiment occupied approximately 89.2 MB, mainly archived/copied source
and logs. It contains no real saves. Successful setup used the existing cached
development packages plus two optional downloads; the initial DNS download
failure remains in private setup output, not a selector failure.

Ambient host load was not controlled; no other project test/render job overlapped
the final trials. Two local samples do not establish distributions, causality,
hosted CI speedup or total future upkeep. A faster unchanged sample cannot justify
discarding confirmed failures. Full-repository instrumentation, package-upgrade
effects and optional xdist compatibility were not exercised: the observed misses
already defeat adoption for the current broad boundary.

## Decision, maintenance and publication

Adopt the small review-navigation trace, with assertions and component contracts
remaining authoritative. Retain the opt-in recipe as reproducible evidence; defer
automatic testmon routing. Do not add bespoke dependency tracking, always-run
companions credited as selector recall, or a comprehensive risk database to repair
this result. Existing explicit CI scopes and the approximately four-minute full
test lane remain the current solution; no new gameplay review gate is introduced.

Maintainer/lead owns marker/recipe upkeep under C-REVIEW/C-MAINTENANCE. Reassess on
changed relevant contracts, assertions, tools/dependencies, escaped failures or
disproportionate cost. A future selection proposal needs independently confirmed
boundary coverage and full lifecycle cost evidence; no speculative implementation
is committed here. Retire the glue if maintained capabilities replace its useful
navigation/experiment value. [#26](https://github.com/CVX-Hull/enactive/issues/26)
retains broader control-effectiveness/research maintenance; this pilot does not
renew or complete that issue's unrelated obligations.

Independent review found the deselection bug and challenged unsupported mapping;
both were corrected and focused checks passed. The final reporting correction
distinguishes successful environment probes from pytest executions and attempted
from planned comparisons. Protected full PR/main validation is required for these
tooling/dependency changes; the linked implementation PR owns actual final check,
integration and cleanup receipts rather than predicting them here.

The first required full candidate run
[40214564731](https://github.com/CVX-Hull/enactive/actions/runs/40214564731)
failed an existing lifecycle fixture at final-exit: the accepted original operation
remained running after its three-second client wait. It passed 2,114 other tests
and 4,004 subtests in 340.20s; the checker took 376.56s. That is a failed gate,
not successful validation. Inspection found no established runtime defect or
explanation for this runner's timing. The fixture correction collects the original
identity through the existing bounded SDK API, with all lifecycle assertions
retained. An event-held writer regression requires original collection without
resubmission; it and the exact failed case passed locally. The initial local
loopback bind denial and a regression-helper mistake requiring `next_call` on
observe were retained and corrected. The full changed lifecycle fixture module
then passed 22 tests and 29 subtests in 149.46s, with two existing MiniRacer
deprecation warnings. Independent review approved the fix; subsequent
protected PR/main receipts remain in the PR. No runtime limit or latency standard
was relaxed, and no pilot detection result was relabelled.

Final ownership review also replaced SQLite transaction contexts around map
backups with standard `contextlib.closing`: transaction contexts alone do not
close connections. The backup API retains transaction ownership. All 11 focused
pilot-tool tests and 11 subtests passed afterward; the measured trial commits
remain explicit rather than claiming these timings describe a later source tree.

Final candidate `833e5f6` passed full PR run
[40215977477](https://github.com/CVX-Hull/enactive/actions/runs/40215977477):
2,116 tests and 4,004 subtests in 346.12s, checker 383.00s. Its identical-tree merge
`ee8834a` then failed main run
[40216755266](https://github.com/CVX-Hull/enactive/actions/runs/40216755266):
the same lifecycle scenario received an uncertain initial collection response for
`final-exit-yes`. Other 2,115 tests and 4,004 subtests passed; tests took 342.69s,
checker 379.50s. This is another failed gate, with no proven cause for the response
unavailability. The initial correction handled running delivery but still wrongly
required initial transport delivery before original collection.

The focused follow-up retains the original operation ID through initial uncertainty
and requires final delivered settlement through the same bounded API. A real-server
regression loses the accepted reply while causally holding the writer and proves
one submission plus exact original collection. The pending-response case, lost-reply
case and exact lifecycle scenario passed three focused tests in 14.43s; independent
review approved the correction. No request was replayed, uncertainty counted as
success, runtime behavior changed or failed run relabelled. Follow-up protected
publication receipts remain with the linked implementation PRs and #225.

Private original commands, hook reports, failures, maps and source copies remain
project-local in `.runtime/iterations/verification-pilots/`; the public payload
retains exact seed recipes, selected/failing identities, environment, costs and
hashes of the private reports without publishing local account paths. Git retains
recipe history. No game was launched, save modified, model benchmark run or
campaign acceptance claimed.
