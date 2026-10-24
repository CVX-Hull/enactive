---
owner: lead
review_trigger: Repeating this local execution experiment or interpreting its scope
status: historical
date: 2026-10-24
scope: Offline source experiment only, without native or campaign acceptance
---

# Execution-first source and offline measurement

This is an **offline source experiment**, with gameplay and native probes paused.
It evaluates the [boundary064](../changes/064-execution-first-learning.md) under
[#164](https://github.com/CVX-Hull/enactive/issues/164),
[#177](https://github.com/CVX-Hull/enactive/issues/177) and
[#178](https://github.com/CVX-Hull/enactive/issues/178). The PR owns final review,
check receipts and publication state. Those outcome issues retain graphical,
organic-learning and campaign acceptance. Normal human-visible CDDA mechanics
and ordinary input remain unchanged.

## Question and method

[Fresh024's review](2026-10-24-fresh024-execution-review.md) found multi-second
local program intervals without an intervening model turn. Its historical timing
does not identify a single cause. Read-only helper measurements at its final
3,617-entry scale found canonical manifest building/encoding around56ms, physical
usage scans around20ms and primitive-history reads around28ms. These overlapping
component measurements must not be summed into a historical explanation.

The dispatch experiment uses the actual Python controller, MissionRuntime,
EvidenceStore and SQLite with the existing synthetic `VisibleBridge` transport
and test-only trusted identity fixture from `tests/test_mission_runtime.py`.
It seeds 3,617 synthetic historical entries from the retained observation shapes,
rewrites them into coherent chronological metadata in the fixture's same session,
recomputes identities/digests and writes synthetic marker frames matching the
original frame byte sizes. These are not genuine game images or a gameplay replay.
The retained seed contained495,696,911frame bytes and11,628,738canonical metadata
bytes. Original evidence is read only; all fixture files are owned temporary
directories removed by test cleanup.

Each sample is one ordinary synthetic direct-input request through settlement.
Three unprofiled samples precede one cProfile sample. Baseline source is457d704;
after source9aa92e2 changes only the evidence cache/scan boundary. The later
authoring/scheduling changes are outside this measured comparison. Timings are
on the existing Mac/project virtual environment, without new global tooling.

| Unprofiled wall seconds | Baseline | Metadata cache / scandir |
| --- | ---: | ---: |
| Sample1 | 1.053728 | 0.459357 |
| Sample2 | 1.057498 | 0.452441 |
| Sample3 | 1.052751 | 0.461662 |
| Median | 1.053728 | 0.459357 |

Median settlement was **56.4% lower**, about2.3times faster in this fixture.
Profile call counts show full manifest construction falling from12 to4; physical
usage scans remain8. Instrumented cProfile time was1.400022s before and0.566625s
after and is excluded from the wall comparison. The profiles contain recursive/
threading attribution artifacts; do not sum cumulative values or infer an exact
historical causal decomposition. Three samples are a development signal, not a
tail-latency qualification or a statistically powered benchmark.

## Evidence and negative observations

Private experiment files are in
`.runtime/iterations/execution-first-2026-10-24/`: `profile_components.py`,
`profile_dispatch.py`, `component-baseline.json`, `dispatch-baseline.json`,
`dispatch-after-metadata-cache.json`, corresponding text/profiles and test logs.
The scripts use standard cProfile/pstats/timing and existing test seams; they are
experiment evidence, not a maintained profiling service. Dispatch script SHA256:
`00c5e8f694e39722675b8178ede17495005851863e9f0c1ed564be96f971d990`.
The private script and source archives are not distributed by this public report.

The first synthetic history attempt used an inconsistent session chronology and
correctly refused input; `dispatch-fixture-rejected.log` retains it. The corrected
same-session fixture produced the samples above. A first profiler used an object
shared across threads; its file is retained separately and excluded. An early
fake-clock adviser-wait test stalled because its timer could not advance; that
owned test process was terminated and the fixture corrected. These are experiment
or test-fixture limitations, not relabeled passing gameplay evidence.

Focused source checks cover exact canonical size after reopen/mutation/failed
persistence; selected tamper/missing/orphan/nonfile failures; semantic authoring
and parent/support closure; snapshot-bound candidate selection and immutable SDK
staging; horizon capacities1/2, urgency, age, pending work, omission/byte trimming;
finite idle waits and cancellation. No threshold assertion replaces the reported
wall samples. Required full CI and independent review belong to the linked PR.

## Interpretation and remaining gates

The repair removes avoidable repeated serialization while preserving selected
source verification, actual physical accounting, reservations and durable intent/
receipt writes. It does not prove the remaining0.46s is minimal. Future local
profiling should follow measured costs before changing persistence or bookkeeping.

Candidate ergonomics, finite scheduling and idle waiting are source capabilities.
They do not establish that a learner will author useful routines, that a player
will choose them well, or that a new host actually loads the changed profile.
No twenty-decision graphical cohort, complete player/model latency distribution,
fresh-successor test, causal learning comparison or independent seven-day campaign
was run. CDDA native behavior, engine speed and public historical failure outcomes
were not changed. A future user-authorized run must qualify the complete frozen
configuration through normal human-visible play.
