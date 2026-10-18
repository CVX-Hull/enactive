---
owner: lead
review_trigger: Monitor implementation, new primary evidence, model or observer changes, active weekly research review
status: proposed
---

# Evidence for outcome monitoring and escalation

Review cutoff: **2026-10-17**. This focused extension of the
[tiered-gameplay research](research-tiered-gameplay.md) supports the
[proposed monitor contract](design/outcome-monitoring.md). Robotics results are
not CDDA results. No weights or training dependencies were installed and no paper
result was reproduced locally.

Two read-only research sweeps covered monitoring and escalation; the lead checked
decisive primary-source methods, results and limits against their summaries.
The matrix states read depth. Exact revisions identify the evidence reviewed,
not a promise that a future revision preserves the same findings.

## Evidence matrix

| Primary source and revision | Method and evidence read | Limits and project consequence |
| --- | --- | --- |
| [RoboMonitor](https://arxiv.org/html/2609.30715v1), v1, 2026-09-25 | Full methods/results/conclusion, §§IV–VII. Instruction and causal camera windows produce separate phase, failure and completion estimates. With 52 labeled episodes, phase accuracy was 93.09% but failure AP 45.87%; at 100 episodes failure AP was 72.01% | Four-task offline benchmark, one real integrated task, predefined recoveries. Calibration/abstention is future work. Evaluate each ability separately; recognizing progress does not establish failure-detection reliability |
| [UniPred](https://arxiv.org/html/2512.17992v2), v2, 2026-09-25 | Full method/experiments/discussion, §§III–VI. Model-proposed predicate effects guide transition-supervised classifiers; learning feedback refines proposals. V2 includes five simulated and two real domains, updating the earlier v1-specific reading | Fixed controllers, demonstrations/transition data and deterministic, fully observable assumptions; partial observation remains open. Derived predicates extend expressiveness without removing per-controller operator assumptions. Reuse the composition idea; ground proposed predicates in evidence |
| [SAFE](https://arxiv.org/html/2506.09937v2), v2, 2025-10-30 | Full method/results/calibration limits, §§3–7 and appendix. Learns failure scores from VLA hidden features and trajectory outcomes; calibrates functional conformal thresholds using successful rollouts | Requires policy internals and labeled domain data. False-positive bounds depend on exchangeability; unseen-task experiments can violate it. Low alarm scores neither prove success nor bound missed failures |
| [Foresight](https://arxiv.org/html/2606.23085v1), v1, 2026-06-22 | Full methods/results/limits, §§3–6 and calibration appendix. A causal detector consumes projected action-conditioned predicted world-model latents, trained with trajectory outcomes | Not an observed-minus-predicted residual. Calibration shift and inference cost matter. Forecasts are risk signals, not observed effects; defer such machinery until a simpler monitor has a measured gap |
| [ContextFlow](https://arxiv.org/html/2605.19314v1), v1, 2026-05-19 | Full methods/results/limits, §§2–4 and 7. Stage contracts and evidence packets align planner, memory and executor; updates include refine, transfer and repair of unsupported suffixes. Two fixed 30-episode navigation subsets | Mechanism-oriented navigation evidence depends on perception and monitor quality. Preserve verified history, but executor termination cannot establish task completion |
| [When Should a Failing Robot Ask?](https://arxiv.org/html/2609.21942v1), v1, 2026-09-18 | Full method/sensor audit/results/limits, §§III–VII. Diagnostic information can reside in an unused sensor; explicit act/sense/ask costs and observed competence inform intervention. Tested confidence did not track correctness | Three scripted simulated failure families, small test sets and scripted human answers. Separate information acquisition from stronger reasoning and operator interruption |
| [Cost-aware protocol routing](https://arxiv.org/html/2608.14927v1), v1, 2026-08-14 | Full paired-protocol method/results/limits, §§2–7. Failure-risk prediction is more useful for coarse escalation than selecting the particular expensive protocol that pays off | Main router comparison uses one solver/math benchmark and one realized result per problem/protocol. Retrospective oracle is not deployable. Measure intervention-specific value, over/under-escalation and total routing cost |
| [Correlated Errors in Large Language Models](https://proceedings.mlr.press/v267/kim25e.html), ICML/PMLR 2025 | Primary publication summary/results checked for correlated errors across models; no embodied experiment reproduced | Benchmark and resume-screening results are not a CDDA detector guarantee. Agreement from another model is not independent evidence without measuring residual error correlation |
| [Sentry](https://arxiv.org/html/2610.02994v1), v1, 2026-10-02 | Full methods/results/limits, §§3–6 and paired-repair appendix. Detects action/progress/grounding failures, retrieves relevant repair lessons and checks local recovery; paired forks from 200 detected intervention points show benefit | Same model is actor/detector/verifier by default. Local recovery and final task outcome are separate measures; triggered cases cannot measure undetected failures. Supports selective repair, not endless repeated model criticism or runtime guard changes |
| [AdaRSI](https://arxiv.org/html/2610.20474v1), v1, 2026-10-14 | Full methods/results/limits, §§4–6. Refines the harness before training persistently unreliable executor substeps on 50 simulated tasks | Uses privileged simulator state for training-data generation/labeling; development improvements can hurt test performance. Borrow failure attribution and held-out discipline, not privileged access, online self-modification or mandatory training |

[Sentinel's official PMLR page](https://proceedings.mlr.press/v270/agia25a.html)
was read only at abstract level in this refresh: the researcher could not retrieve
the linked full PDF. Its stated combination of action consistency and semantic
progress motivates complementary signals; detailed inputs, training requirements
and guarantees are not credited here.

## Adjudicated design consequences

These are project inferences, not demonstrated CDDA results:

1. Keep exact authority and factual checks small; represent semantic judgments as
   replaceable, fallible records. None of these studies makes arbitrary screenshot
   task completion deterministic.
2. Start with declarative composition and a capable-model monitor. Robotics
   policies are not drop-in keyboard-game components; closed providers may not
   expose features required by trained failure detectors.
3. Separate progress, failure and completion, preserving unknown observations and
   partial progress. Validate recovery as well as detection.
4. Choose more information, more reasoning, a revised approach or a targeted human
   question. No reviewed paper establishes CDDA benefit from repeating the same
   strongest-model call with unchanged evidence.
5. Measure domain-specific calibration and full cost, including failed calls,
   monitor overhead and recovery. A second model's agreement is not ground truth.
6. Inspect observation/harness deficiencies before blaming model capacity.
   Training needs a demonstrated gap, permitted data, a resource budget and
   separate acceptance through #27.

## Gap map and maintenance

| State | Scope |
| --- | --- |
| Implemented before this round | Guarded cardinal walk, native/controller recovery, passive provenance-aware evidence and memory |
| Existing designed follow-on | Waypoint planner, supervisor, skills and live model comparisons |
| This proposed design | Composable expectations, read-only semantic reports, information-aware escalation and monitor evaluation |
| Not implemented by this research | Learned monitor, calibrated router, inventory observer, model service, training or broad autonomous gameplay |

#26 owns the active review trigger (2026-10-24, or before resuming if dormant).
Refresh revisions before implementation if this evidence is older than one week;
also review on model/prompt/observer changes, false-success incidents and drift.
Record which decision changes, exact versions and an accountable follow-up.
No scheduler or automatic date renewal is installed. Research currency cannot
substitute for task-specific recalibration. Runtime acceptance remains #42–#44;
[the round brief](changes/007-recovery-evaluation-monitoring.md) fixes this round.
