---
owner: lead
status: historical
date: 2026-10-18
scope: Cross-disciplinary memory study, frozen offline simulations, reproduction and research recommendation; no native gameplay or live memory migration
---

# Memory representation study evidence

The [research synthesis](../research-memory-representations.md) recommends source
identity, explicit applicability and rebuildable queries as the design basis,
starting with replay and exact filtering. It defers a persistent architecture
until a bounded player-visible trace benchmark demonstrates a need. This report
accepts a research result and reproducible experimental implementation, not an
improved CDDA player. No native game, save, model API or training was used here.

## Provenance and collection

The [brief](../changes/013-memory-representation-study.md),
[protocol](../design/memory-study-protocol.md),
[literal fixtures](../design/memory-study-cases.json) and
[exact matrix](../design/memory-study-matrix.json) define the scope. The initial
reviewed source/protocol checkpoint was published in
[PR68](https://github.com/CVX-Hull/cdda-player/pull/68), merged as
`a146e8a349cdd64217f79e7ad322509e6215b45c` with identical reviewed tree.
Its merged-main [CI](https://github.com/CVX-Hull/cdda-player/actions/runs/39102289621)
passed. Documented implementation clarifications, fair baseline query paths and
coverage/cost repairs precede final collection; **v1.1 is the only current
reader/fixture/matrix format**. Unsupported v1 rejects rather than falling back.

Accepted runs `final-r2` and `final-r3` use clean source
`6ccb3941550f20388ffca8ec2cfa4620e1cf8a32`, protocol `memory-study-v1.1`, Python
3.14.7, SQLite 3.53.4, Darwin arm64. Their manifests record all 16 experiment,
test and configuration hashes. The [selected results](../assets/memory-study-results.json)
retain these hashes and full-report digests. Later explanatory documentation does
not change these frozen experiment files.

| Suite | Raw seed aggregates | Scope |
| --- | ---: | --- |
| L | 129,280 | Lineage, event time, scope, retraction, retirement, replay/cache costs and diagnostic ablations |
| E | 41,472 | Duplicate/correlated evidence, point predictions, finite model envelopes and misspecification |
| C | 148,224 | Exact/FTS/recent/reservoir retrieval, explicit compaction, masked operation and counterexamples |
| D | 36,864 | Fixed/pooled/scoped/windowed prediction, drift, retention and causal non-identification |
| Total | 355,840 | 256 seeds, 10000–10255, per declared condition/method |

These rows are not 355,840 independent game episodes. Queries and configurations
within a seed are dependent. Reports aggregate by seed and retain paired
differences. Half-widths are `1.96 × sample standard deviation / sqrt(256)`:
descriptive seed Monte Carlo variation, without simultaneous coverage, game
population sampling or a model-calibration guarantee. L's fixture laws have no
Monte Carlo confidence interval.

Both fresh processes completed without a failed law/schema/coverage gate. Their
manifests, deterministic content and compressed raw bytes are identical:

| Artifact | SHA-256 |
| --- | --- |
| Deterministic content | `8e37b9dc2f0c35b7ae82f86ff829b9463ecf06a46fed247e1377099ae3e696ab` |
| Raw gzip, 17,766,160 bytes each | `573467daacade5b99455974caecddfa079ee38f82656da42dabf68c4fdfebc4e` |
| Versioned selected JSON | `f154205278447beefc4ed5bb3791d470ec401368c9d912d7b342da458a8a4394` |

Local complete reports, manifests and raw rows live under
`.runtime/research/memory-representations/runs/final-r2/` and `final-r3/`.
They are not available on a fresh public clone; the public source and recipes
recreate them. The selected JSON is an illustrative subset; all declared regimes
remain in the complete reports. No favorable subset was used to tune candidates.

## Findings and counter-results

**L: replay is a strong baseline.** Both complete methods meet every exact
lineage law. Across the 12 separate literal templates, summed work is 526/606
(replay/cache) for one query pass, 1,540/972 for four, and 5,596/2,436 for 16.
Their summed archive bytes are 5,838 each; additional retained-state JSON is
988/4,913 bytes. These are sums across separate examples, not one game heap.
Permuted-final comparisons also pass: work is 458/499, 1,229/793 and 4,313/1,969.
Work combines declared record inspections/index operations; it is neither CPU
time nor a universal cost ratio. Deliberately broken ablations exhibit each
targeted failure; they are not defects discovered in current TaskMemory.

**E: uncertainty must be tied to a model and a decision.** At independent
`q=.8`, four origins and 16 copies, deduplication's mean Brier loss is .05087 and
log loss .1680. Naive repeated evidence has slightly lower sampled Brier (.05078)
but higher log loss (.4321); it does not universally worsen every loss or change
the action. The finite envelope abstains on every seed in that condition and has
.71146 expected regret. At correlated `q=.6,rho=.75`, 12 origins and 16 copies,
deduplication still has .77960 expected regret and −.87109 realized utility;
the envelope abstains .875 of the time, has zero expected regret in this model
and .04688 realized utility. Deduplication removes replay, not shared error causes.
At `q=.8,rho=.75,n=12`, deduplicated decisions already have zero expected regret,
whereas envelope regret is .02016. Thus no envelope superiority is inferred.
At the intentional `q=.95,n=1` misspecification, containment of the true-model
posterior is **0/256**. In-class posterior containment is not binary-truth coverage
or a real-world confidence guarantee. Proper losses apply to point predictions,
not interval endpoints or a selected midpoint.

**C: a surviving citation can conceal a lost change.** With full operation
visibility, normal source/session and `k=4`, exact and FTS make 32/32 correct
answer-or-abstain decisions per seed. Missing keys correctly remain unknown;
mean known answers are 27.3203. Majority projection answers the changed key
correctly on 92/256 seeds, despite retaining its latest source lineage on all
256. It preserves the unique old rare key but often loses the rare latest change
among repeated earlier outcomes. Its repeated application is idempotent; the
separate truncation operator progressively loses information and is empty at
depth eight. These are specified operators, not measurements of LLM summaries.

For masked-operation, all-allow records, FTS `k=4` incurs .859375 ± .150899
avoidable abstentions **per 32 queries**; `k=8/16` and exact filtering incur zero.
FTS has a serialized SQLite cost of 40,960 bytes in the selected full-visibility
case, plus the canonical archive (about 13,628 bytes); construction includes
64 document and 64 metadata rows. No index is treated as free. Correct context
tags and source rendering are stipulated inputs; extraction accuracy is untested.
C answers archive questions, not L's stricter current-applicability queries and
not fresh controller guards. The same-bit control also disproves a universal
query-label-entropy memory requirement.

**D: retention and adaptation can conflict.** Brier loss after drift (phase 3)
is .25000 fixed, .22343 pooled, .33957 scoped all-history, and .21085/.23394/.28675
for windows 8/16/32. No window is declared universally best. The paired scoped
minus pooled difference is +.116134 ± .002910 after drift, but −.030300 ± .002189
on phase 4 return. In the context-irrelevant regime it is +.001683 ± .000494 at
phase 4: splitting can reduce useful shared evidence. In the no-drift untouched-A
probe after phase 3, scoped prediction error is .004407 with zero change since
phase 1; pooled error is .159524. Hidden-domain phase 2 gives identical pooled
and scoped loss (.341282). This is fixed-logger prediction, not learned policy
value. The zero-overlap control produces identical observed logs in two worlds
whose untried-action values are zero and one; the value stays unidentified.

## Review, controls and limitations

Three clean-context implementation reviews covered L/C, E/D and the runner.
They and lead inspection repaired missing FTS build accounting, unfair metadata
replay work, matrix checks that only counted rows, and law checks that could
accept a known broken complete method. Negative tests now reject renamed/missing
conditions, metrics and broken laws, preserving rejected rows/failure diagnostics.
The runner verifies unchanged source/config before and after collection.

An independent result reviewer expanded the matrix and streamed all 355,840 rows,
then recalculated 83,063 metric summaries including paired differences (498,378
scalar statistics): zero discrepancies at `1e-9` tolerance. They separately
reconstructed selected calculations without importing project modules: 1,026 E,
672 D, 25 C and eight L checks, all matching. They confirmed the latest-citation /
lost-answer counterexample independently. This adds algorithm checks, but is not
a complete independently reimplemented study replication.

Earlier full run `final-r1` preceded a **test-only** fresh-checkout runtime-directory
initialization repair. Its content/raw digests match r2/r3; algorithms, parameters
and protocol were unchanged. Historical smoke runs, review repairs and earlier
reports remain retained. No outcome tuning followed final seeds. Local common
checks passed 426 tests; seven runner tests also passed in an isolated checkout
starting without `.runtime`. Frozen-source hosted checks passed on
[push](https://github.com/CVX-Hull/cdda-player/actions/runs/39103347589) and
[PR](https://github.com/CVX-Hull/cdda-player/actions/runs/39103350435).

The new diagram was rendered with the existing pinned project-local Mermaid/
Chromium tools and inspected at 1000-pixel ordinary-window width. No global
package/profile/application change or fullscreen launch occurred. A clean-context
final review found no material issues in the synthesis, diagram and follow-up;
it reproduced all 56 selected groups byte for byte and verified the 16 frozen
hashes. It did not independently reread every paper or repeat the separate
exhaustive raw-statistic audit. The completed final-document common lane also
passed all 426 tests and viewer, boundary, governance and documentation checks.
An additional diagram-only check in the restricted sandbox could not launch
Chromium; repeating with the renderer's required local permissions passed. An
unrelated regenerated recovery SVG was restored to its existing valid receipt.
Final-candidate checks, protected publication and merged-tree verification are
recorded in [PR69](https://github.com/CVX-Hull/cdda-player/pull/69) and linked Issues;
earlier CI above is not substituted for those later checks.

## Reproduction and maintenance

After the normal project-local [setup](../setup.md), use a clean checkout and a
fresh, nonexistent output directory:

```sh
.venv/bin/python -m tools.memory_study.run --mode final --output-dir .runtime/research/memory-representations/runs/reproduction-1
```

Repeat in another fresh process/output directory. Compare `content_sha256`,
`raw_sha256`, matrix coverage, laws and source hashes, not report-file identity
(timings and source commit may differ). The accepted pair ran concurrently with
disjoint output directories and immutable inputs. Suite wall times include
generation/scoring/accounting/compression and CPU contention; they are not
candidate latency measurements. Cross-platform SQLite/Python byte identity is
unverified. Failures must stay failures; do not edit a report to match a digest.
The [selection recipe](../../tools/select_memory_study_results.py) records the
public illustrative projection; complete reports retain all conditions.

Retain raw reports, manifests, earlier attempts and primary-source corpus locally
until the next [#26](https://github.com/CVX-Hull/cdda-player/issues/26) review and
the trace benchmark's adoption decision. Later deduplication/archive needs verified
hashes and a recorded retention assessment; source/selected evidence remains in
Git. Do not commit full third-party papers. Follow the existing manual October 24
research review and earlier observer/model/engine or false-memory triggers. This
does not install a scheduler or renew control-maintenance dates.

The lead preserved and hash-verified the four original worker source handoffs in
a local archive, then removed the two completed worker worktrees/branches and the
clean cold-checkout worktree. Experiment evidence and project dependencies remain
retained. No save, global environment or unrelated process was changed.

| Requested outcome | Evidence and scope |
| --- | --- |
| Breadth and recent primary research | Six lenses and 19-source reading matrix, including Oct. 14–15 preprints, in the synthesis; limits and inaccessible leads disclosed |
| Mathematical assessment | Explicit assumptions and counterexamples; no provenance-as-probability, entropy-tax or cited-truth guarantee |
| Falsifiable simulation | Frozen protocol/matrix, strong baselines, development/final split, sensitivity and negative controls |
| Reproducibility and independent review | Source hashes, two identical full collections, raw-statistic recalculation and selected independent algorithms |
| Reviewable representation and elegance | Proposed advice/offline loops, existing-type mapping, qualitative invariants/costs, adopt/test/defer decisions |
| Staged follow-up | Bounded [visible-trace benchmark #70](https://github.com/CVX-Hull/cdda-player/issues/70); native efficacy #24/#56, monitors #40, maintenance #26 and conditional #27 remain separate |
| Publication and isolation | PR68 source/protocol and PR69 implementation/results; local-only dependencies/artifacts, no native/API/training/global changes |

There is no live schema migration in this increment. Offline v1.1 rejects obsolete
formats, and historical reports remain evidence rather than supported execution
paths. A later runtime representation needs a reviewed brief, all-caller/data
migration and native acceptance where authority or gameplay behavior changes.
