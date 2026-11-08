---
owner: lead
review_trigger: A change to ADR 009's program, slot, monitor, expectation, offline-evaluation, practice-instance or study sections; the P1 or P2 pre-registration; new primary evidence on any area below
status: active
date: 2026-11-08
scope: 'Dated primary-source synthesis for ADR 009 research areas R5-R12 (#448): program libraries, model slots, supervision, novelty, expectations, offline evaluation, practice environments and study design, with study-design guidance for #178 and #470. R13 (#451) is out of scope. No implementation.'
---

# Programs, supervision, evaluation and study design: evidence for ADR 009 (R5-R12)

Search and retrieval date: **2026-11-08** (all sources below were retrieved that day).
The 18-month recency line is therefore **2025-05-08**; a conclusion whose newest
supporting source is older is flagged "STALE-FLAG".

## Brief, questions and method

**Brief (#448, lead).** Produce the S-EVIDENCE synthesis for R5-R12 of
[ADR 009](decisions/009-curated-player.md#research-agenda), with recommendations per
area and study-design guidance for #178 (P1 offline study) and #470 (P2 study).
The brief named only foundational sources (below) and no current source. Questions,
copied from the ADR's agenda table:

| Area | Questions | Foundational sources the brief named |
| --- | --- | --- |
| R5 Program induction and libraries | What makes induced skills help rather than hurt (verification by execution, granularity, retrieval, curation, drift)? | Options framework (Sutton, Precup and Singh 1999); DreamCoder; programming by demonstration |
| R6 Programs with model calls | Cascades, routing and distillation to replace slow calls with fast or specialized models; caching and replay for evaluation | Model cascades; knowledge distillation (Hinton et al. 2015) |
| R7 Supervision and interruption | Asynchronous human-on-the-loop supervision, preemption, risk-gated autonomy and runtime shields | Safe interruptibility (Orseau and Armstrong 2016); shielding (Alshiekh et al. 2018); sliding autonomy |
| R8 Novelty and anomaly detection | Detecting unfamiliar screens and anomalies from pixels for yield and monitor triggers; perceptual hashing reliability | Out-of-distribution detection basics |
| R9 Expectations and prediction error | Do agents that state expectations act better or learn faster? How are self-predictions calibrated? | Predictive processing; temporal-difference prediction error |
| R10 Offline evaluation of policies | Evaluating programs from logged play: agreement metrics, off-policy evaluation and their limits | Importance sampling and doubly robust estimators |
| R11 Practice environments | Forked environments for testing policies; determinism and replay in interactive software | Record and replay debugging |
| R12 Study design | Power and design for lineage-level process metrics; sequential testing to cap spend | Cluster-randomized design; sequential analysis (Wald) |

Named foundations that I did **not** read (Sutton et al. 1999, DreamCoder, Hinton
2015, Orseau and Armstrong 2016, sliding autonomy, Wald, predictive processing, TD
error) support no conclusion here. Those I read only at abstract level are tagged.

**Method and honest limits.** Dated web searches (about 35 queries, 2026-11-08) found
leads; **search-result summaries are not evidence and no conclusion rests on them**.
I then fetched each cited source. The fetch tool returns an extraction made by a
small model, not verbatim text. "Full text (extracted)" below means the paper body
was fetched and summarized against my questions, often truncated (noted); "abstract"
means the arXiv listing only. Decisive numbers should be re-verified from the PDF by
the reviewer before they enter a pre-registration. Sources seen only as search
snippets are listed in the last table as **not relied on**.

**Prior work not repeated.** I skimmed (tables and headings only):
[executable policies](research-executable-policies.md) (research cutoff 2026-10-23,
archived 2026-10-29, historical; RAX, MetaSkill, SEAR, AtomSearch, SkillNEO, py_trees,
Wasmtime), [multirate agents](research-multirate-agents.md) (cutoff 2026-10-24,
dated 2026-11-07, historical; CodeHack, Recuris, PACT-VLA, anti-persistence) and
[outcome monitoring](research-outcome-monitoring.md) (cutoff 2026-10-17, dated
2026-11-07, historical; RoboMonitor, UniPred, Sentry, cost-aware protocol routing
[2608.14927], correlated errors). I did not re-read their sources. The findings
below add to them; they cite those pages where a point overlaps.

**Transfer warning common to every area.** Almost all current agent evidence is on
coding, web, office, terminal or QA benchmarks with structured text state. Evidence
for a real-time, screenshot-only, keyboard-driven game with a text-heavy interface
is **thin or absent** in every area; I say so per area. Nothing here relies on
knowledge of any particular game.

## R5 Program induction and libraries

**Evidence read.**
- *Self-written skills do not help (current revision).* SkillsBench ([2602.12670](https://arxiv.org/html/2602.12670v4),
  **v4, 14 Jun 2026**; v1 13 Feb, v2 7 Mar, v3 13 Mar 2026; the v4 abstract page and
  the v4 body were re-read on 2026-11-08, first 100k of 175,714 characters of the body,
  extracted): 87 tasks in 8 domains, 18 model-harness configurations in four harnesses,
  3 selected public trials per configuration, task and condition. Curated skills +16.6 pp
  (33.9% to 50.5%; per-configuration +4.1 to +25.7); **self-generated skills were
  evaluated on only 3 of the 18 configurations and fell below no skills on all three**:
  Anthropic's agent + Opus 4.7 -8.1 pp, OpenAI's agent + GPT-5.5 -11.3 pp, Google's agent + Gemini 3.1
  Pro -11.5 pp (curated skills +18.2, +19.7, +24.8 on the same three); 13 of 87
  tasks negative with curated skills; 1 skill +18.0, 2-3 skills +19.0, 4+ skills +10.1;
  compact +19.0, standard +21.5, detailed +14.5, "comprehensive" +0.7 pp. **No
  length-matched or irrelevant-text control** (the authors list it as future work), so
  context length is not ruled out. Terminal tasks only. My earlier draft cited
  superseded v1 (84 tasks, 7 configurations, 5 repeats, curated +16.2, self-generated
  -1.3 as I extracted it; the v1 table reportedly says -1.8, which I did not
  re-check); none of those v1 figures is used now.
- *Net gains hide regressions.* The Regression Tax ([2607.22520](https://arxiv.org/html/2607.22520),
  24 Jul 2026; full text extracted): 486 tasks per stack, 3 model-harness stacks, 18
  library conditions, **one run per task per condition**, no token-matched control;
  553 gains vs 324 regressions (regressions cancel 59% of gross gains); McNemar with
  Bonferroni leaves 3 of 18 conditions significant. Three mechanisms: a skill alters
  behaviour merely by being in context, overrides input grounding, and displaces
  the agent's own output checks. Office and spreadsheet tasks; single-author coding
  of mechanisms; harness and model coupled.
- *Retrieval-conditional effect.* Skill Following ([2609.00549](https://arxiv.org/abs/2609.00549),
  1 Sep 2026, EMNLP Findings 2026; **abstract only**): 17 LLMs on coding and math;
  positive aggregate "retrieval lift" can coexist with negative same-task effect on
  the tasks where retrieval occurred (selection bias). No numbers read.
- *Drift and retirement.* Ratchet ([2605.22148](https://arxiv.org/html/2605.22148),
  v1 21 May 2026, v2 29 Jul 2026 and v3 7 Aug 2026 per the arXiv listing; abstract plus body, first 100k of 135,608 characters, extracted):
  a judge that scores failures as passes at rate at or above (1-tau)/2 retires
  nothing at any sample size; unmaintained libraries drift to worse than no skill.
  Its own result is a rolling gain of +0.328 held-out pass@1 (last ten rounds minus
  first ten) on a 100-task MBPP+ slice filtered to tasks the base model (Anthropic's Opus
  4.7) fails on at least one probe seed, 100 rounds, 3 seeds; the control with injection withheld gains +0.002;
  six other model families single-seed; SWE-bench preliminary; no budget-matched
  baseline; eviction signal associational. **The "LLM-written +0.0 pp, human-written
  +16.2 pp" figures in its abstract are cited from SkillsBench, not measured by Ratchet,
  and are not independent corroboration** (and the 16.2 is the superseded SkillsBench
  v1 figure).
- *Specification-versus-verification gap.* SpecBench ([2605.21384](https://arxiv.org/abs/2605.21384),
  v1 20 May 2026, v2 9 Sep 2026; **abstract only**): 30 coding tasks scored on visible
  tests and held-out tests; frontier agents saturate the visible suite while the
  held-out gap persists and grows with code size (about 28 pp per tenfold; it
  reports a 2,900-line solution that memorizes test inputs). Relevance: visible-test
  acceptance of agent-written artifacts can be gamed, which supports the ADR's
  gate-owned tests the curator cannot see. How agents game pass/fail gates is
  R13's question (#451), which already uses this source; I do not extend it here.
- *Execution verification of induced programs.* ASI ([2504.06821](https://arxiv.org/html/2504.06821v2),
  v1 Apr 2025, v2 29 Aug 2025; full text extracted): induced Python skills are kept
  only if a re-run from the rewritten trajectory succeeds, a skill is called, and
  each call changes the environment. WebArena 812 tasks, one backbone: 40.4% vs
  vanilla 32.7% and text-memory AWM 36.3%. **Only 15.6% of induction turns passed
  verification**; a verified-text ablation scored higher than programs-in-memory;
  scaled-up and cross-site tests have about 5-10 tasks each; budget matching not
  stated; LM-judged success is part of the check.
- *Library curation.* SkillBrew ([2605.29440](https://arxiv.org/abs/2605.29440),
  28 May 2026; abstract only) argues append-only banks keep redundant, outdated or
  harmful entries and proposes multi-objective curation; no results read.
- *Game-like settings.* MMSkills ([2605.13527](https://arxiv.org/abs/2605.13527),
  May 2026) and SCALAR ([2603.09036](https://arxiv.org/abs/2603.09036), Mar 2026,
  Craftax, 88.2% diamond rate) were read at **abstract level only** with no
  baselines, budgets or limitations; they support no conclusion. The human-written
  code-skill result on NetHack/MiniHack is in [multirate agents](research-multirate-agents.md).

**Restates earlier work (my assessment; the named foundations and Voyager were
not read, so this is a hypothesis, not a source finding).** Skills with preconditions,
bodies and termination look like options/macro-actions; induction from traces
resembles programming by demonstration and Voyager-style libraries; "execution
verification" resembles test-based acceptance. The newer content is the measurement
of harm (regressions, drift), not the mechanism.

**Gaps.** No source found measures induced-program libraries on a real-time game from
screenshots. Verification strictness (15.6% pass) and judge noise are measured only
in coding/web settings.

**Recommendation for ADR 009 (R5).**
1. Keep gate-side execution verification, probation, per-program statistics and
   retirement; they match the mitigations the evidence supports. Do not state or
   expect that induced programs help: in the one controlled comparison, self-
   generated skills scored **below** the no-skill baseline on all three configurations
   where they were tested (-8.1 to -11.5 pp, 3 of 18 configurations, terminal tasks,
   3 trials), while curated skills helped (+16.6 pp). That is harm, not merely null,
   in that benchmark; whether it transfers to a game library is untested, and the
   supporting game evidence is abstract-only. Ratchet's rolling gain shows a
   governed library can improve on one coding slice but is a single-benchmark result
   with a filtered task set.
2. Make **paired gains and regressions** (situation-level: no-program succeeded and
   program failed, and the reverse) a required P2 metric beside delegation share, as
   in the Regression Tax. A matched failure rate hides offsetting gains and losses.
3. Add a **"library visible, delegation disabled"** control arm to the P2 study. The
   evidence says merely having skill text in context can change behaviour (not
   length-controlled in any source read, so this is a hypothesis to test).
4. Treat model-judged success predicates as noisy: before a judge-based predicate may
   retire or promote a program, measure its false-pass and false-fail rates on a
   labelled set held out from development (Ratchet's condition is on the false-pass
   direction). Prefer deterministic predicates from expectations where they exist.
5. Surface few candidates per decision (SkillsBench's 1 and 2-3 skills beat 4+, and
   compact/standard beat comprehensive; not length-controlled, so a hypothesis);
   include a text-procedure ablation (ASI's text beat programs in memory).
6. Report retrieval-conditional effect (outcome when the program was actually
   offered or selected vs matched situations where it was not), not only aggregate lift.
   STALE-FLAG: none for items 1-6 (newest sources Jul-Sep 2026), but all are
   coding/office/web evidence; game transfer unsupported.

## R6 Programs with model calls

**Evidence read.**
- *Cascades.* Bouchard ([2605.06350](https://arxiv.org/abs/2605.06350), 7 May 2026,
  v2 5 Oct 2026; **abstract only**): two-model cascades beat single-model selection
  by 2.1-8.2 pp; deeper cascades gave no mean gain in 118 of 135 comparisons;
  simulated high-AUROC scores helped deeper cascades only when they ignored query
  difficulty shared across models. Five benchmarks, eight-model pool, single author.
  UCCI ([2605.18796](https://arxiv.org/html/2605.18796v1), 11 May 2026; full text
  extracted): a calibrated (isotonic) deferral cut cost 31% (95% CI 27-35%) at equal
  F1 on 75,000 photo-search NER queries between a 4B and a 12B model; ECE 0.12 to
  0.03; one domain, one model pair, independent researcher, no seeds, static
  calibration.
- *Agent-step routing.* TwinRouterBench ([2605.18859](https://arxiv.org/html/2605.18859),
  v5 24 Oct 2026; full text extracted, last 18k characters unread): labels from
  execution-verified greedy downgrade search; on 100 locked SWE-bench instances a
  trained router resolved 75 vs 74 (unrouted) at 53% lower API cost; **a frontier
  model used as router chose high for 7 of 147 verified-high steps and passed 0 of
  40 trajectories** (the router was Anthropic's Opus 4.6 under **one** prompt template,
  one diagnostic run; 300 valid rows of 336, 36 malformed, covering 147 verified-high
  steps in 40 SWE-bench trajectories); one rule-based router cost 3x more. No repeats
  reported; labels depend on the model pool and price snapshot. The first-listed
  affiliation is Gradient and the repository sits under the organization of one
  compared baseline, so I treat this as one vendor-built benchmark: guidance resting
  on it is weak, and this recommendation does not rest on it alone.
- *Replay with swapped outputs is invalid.* The Replay Gap ([2608.08239](https://arxiv.org/html/2608.08239),
  8 Aug 2026; see R10/R11 for venue and numbers). Swapping a recorded action from
  another model (upgrade or downgrade) rewrote 61-94% of later actions.
- *Distillation.* Kang et al. ([2505.17612](https://arxiv.org/abs/2505.17612), v1
  23 May 2025, v2 5 Nov 2025, NeurIPS 2025; **abstract only**): 0.5-3B students
  trained on agent trajectories, competitive with larger CoT-distilled models on
  eight factual/math tasks. No GUI, screen reading or latency evidence.
- *GUI small models.* WinDOM and LiteGUI appeared only in snippets; a 7B-to-2B
  screenshot-description distillation appeared only in a blog. **No source read
  tests a small model replacing a large model for text reading or classification of
  screen regions.**
- *Caching and replay.* vCache ([2502.03771](https://arxiv.org/abs/2502.03771),
  v1 Feb 2025, v5 21 Feb 2026, ICLR 2026; **abstract only**): per-prompt thresholds
  for semantic caches; reports up to 12.5x hit rate and 26x lower error vs static
  thresholds (text prompts; reported by authors). It concerns similarity caches;
  an exact key (frame hash, slot, prompt, binding) is a different, replay-style cache.
  Nondeterminism: Tamba ([2606.26185](https://arxiv.org/abs/2606.26185), 24 Jun 2026,
  v2 24 Oct 2026; abstract only): at default settings borderline judge items flipped
  across identical runs (up to about 50% disagreement over 20 runs); temperature 0
  reduced but did not remove flips; 690 calls, 7 items, single author; newer
  Anthropic model versions no longer expose temperature. The Replay Gap measured 90-96% of
  FP8-served 4B control forks diverging at temperature 0 against near-identical
  AWQ-served 14B controls: determinism depends on the serving stack and/or the model
  (the paper says quantization confounds model size with serving configuration).

**Restates earlier work (my assessment; FrugalGPT, router training, distillation
sources and memoization were not read).** Cascades, router training, knowledge
distillation and memoization look like older ideas; the agent-specific content is
step-level substitution effects and nondeterminism.

**Recommendation for ADR 009 (R6).**
1. Keep the record-and-replay design: store model **outputs with request, binding
   and response metadata** and replay from the record. Do not assume re-querying at
   temperature 0 reproduces an output. Use an **exact** content key for evaluation
   replay; do not use a similarity cache anywhere an evaluation result depends on it.
2. A slot swap is a model change. Accept it on **cases held out from those used to
   choose the candidate** (S-EVIDENCE), reporting accuracy at a stated operating
   point with an interval, the escalation rate and cost, not "matches accuracy" on
   the same recorded set. Stratify cases by difficulty for the slow model too
   (shared difficulty removed cascade gains in Bouchard's counterfactual).
3. Limit to **two bindings per slot** (fast, slow) unless a measured gap justifies a
   third; escalate only on a calibrated uncertainty signal whose calibration set is
   held out and re-checked after any binding or prompt change. A frontier model prompted
   as a step router (one model, one prompt) chose the high tier for 7 of 147
   verified-high steps and passed 0 of 40 trajectories, in one vendor-built benchmark:
   weak support.
4. Because slot errors compound downstream (R10), add a **closed-loop check** (program
   run with the swapped binding against the same fixture states) before adoption, and
   count variance across repeated live calls on the same input.
5. Pin binding, route, prompt and (where exposed) serving details in the run package.
   No distillation or training is supported by evidence for this domain; defer.
   No STALE-FLAG here (Kang v1 23 May 2025 is inside the window). Evidence for game
   screens: absent.

## R7 Supervision and interruption

**Evidence read.**
- Async Control ([2512.13526](https://arxiv.org/abs/2512.13526), 15 Dec 2025;
  **abstract only**; UK AISI-affiliated authors): after-the-fact monitors add no
  runtime latency; an ensemble reached 6% false negatives at 1% false positives on
  a held-out coding environment against a red team built on Anthropic's Opus 4.1; risk
  extrapolation can be invalid. Latency-to-harm not reported on the page.
- Reduced-Supervision Paradox ([2609.29547](https://arxiv.org/abs/2609.29547),
  28 Aug 2026; abstract page plus its listing summary only, no body): audit of 63 public artifacts; checkpoint
  placement visible in 6, recovery in 2. Public-disclosure counts, conceptual
  framework, not an effectiveness study.
- VIGIL ([2606.26524](https://arxiv.org/abs/2606.26524), 25 Jun 2026; abstract):
  trace checking against specs reports over 95% recall and under 10% false
  positives on agent runs; run counts and baselines not on the page.
- Shielding ([1708.08611](https://arxiv.org/abs/1708.08611), 2017; abstract): a
  shield enforces a temporal-logic specification before or after the learner.
  STALE-FLAG; it requires a formal safety specification, which a game-neutral
  player does not have.
- Interruption mechanics: Sema Code ([2604.11045](https://arxiv.org/abs/2604.11045),
  Apr 2026; abstract): an architecture paper with **no interruption evaluation**.
  Framework documentation seen in snippets (cancel at safe points, finish in-flight
  tool calls) is not evidence.
- Overlapping prior page: [outcome monitoring](research-outcome-monitoring.md)
  (Sentry detection plus repair; monitors triggered only on detected cases cannot
  measure undetected failures; same-model monitor errors correlate).

**Restates earlier work (my assessment; runtime-verification, sliding-autonomy and
safe-interruptibility sources were not read).** Runtime verification, shielding,
sliding autonomy and safe-point preemption look like the older ideas. No source read evaluates
preemption of a running policy in a real-time interactive environment.

**Recommendation for ADR 009 (R7).**
1. Keep the monitor as a **stop-only asynchronous detector** and describe it as
   such: a model monitor offers no guarantee. The guarantee-bearing parts are the
   deterministic runner checks (budgets, preconditions, risk class, batch-boundary
   preemption, refusal of stale-frame input); say this in the ADR so no one reads
   monitor detection as a safety bound.
2. Measure the monitor as **detection rate at a fixed false-alarm rate per program
   hour** on blind-labelled recorded runs, with both rates' intervals and the share
   of anomalies it saw after the damaging input (Async Control's own caveat on
   extrapolation applies: do not extrapolate from a recorded set to unseen programs).
3. Treat **risk-class verification as a classification problem** with its own
   recorded-case error rate; report misclassified high-risk steps separately.
4. Measure preemption directly (request to input-sender change latency; fraction
   of preemptions with unknown delivery) as a guard, since no source gives numbers.
5. Evidence level: thin. Everything above is coding-agent or formal-methods
   evidence; none addresses supervising a keyboard-control policy. STALE-FLAG for
   the shielding-based statements.

## R8 Novelty and anomaly detection

**Evidence read.**
- GEM ([2505.12842](https://arxiv.org/html/2505.12842v4), v4 22 Nov 2025, AAAI 2026;
  full text extracted): uses encoder-layer embeddings of a fine-tuned Qwen2-VL-7B GUI
  agent, a Gaussian-mixture on centroid distances, one in-distribution set (AITZ).
  Best baselines misclassified 31.75-48.92% of OOD inputs (FPR95); GEM reports 89.5-100%
  accuracy across eight sets; **OOD is mostly instruction-level** (unsupported
  tasks/apps), weak on some other backbones. Requires internal model access.
- Representation dependence: Janiak et al. ([2510.15202](https://arxiv.org/abs/2510.15202),
  v3 3 Mar 2026; abstract) and Claros Olivares and Brockmeier ([2511.11934](https://arxiv.org/abs/2511.11934),
  v3 17 May 2026; abstract; CIFAR/TinyImageNet scale): the best OOD detector depends
  on the learned representation more than on the score. No numbers read.
- NovelCraft ([2206.11736](https://arxiv.org/abs/2206.11736), 2022, TMLR 2023;
  abstract): in a Minecraft-like world, methods best by AUC can be beaten by simpler
  ones when false positives are controlled. STALE-FLAG; the one game-like finding.
- Perceptual hashing: McKeown and Buchanan ([2212.08035](https://arxiv.org/abs/2212.08035),
  Dec 2022; abstract): a million-image study of Hamming-distance distributions
  between unrelated images and edited variants; authors note public evaluations are
  limited; findings not on the page. STALE-FLAG. Recommended thresholds seen in
  web guides are vendor/blog material and are not evidence.

**Restates earlier work (my assessment; classical OOD and image-forensics hashing
sources not read).** Classical OOD and novelty detection and image-forensics
hashing look like the origin; the representation-dependence results suggest OOD
scores need calibration on the deployment representation.

**Recommendation for ADR 009 (R8).**
1. Do **not** adopt a perceptual-hash threshold from outside sources. The ADR already
   makes unrecognized screens a yield trigger; add a pre-study (P0, $0 gameplay) that
   builds labelled screen pairs (same screen and different state; different screen)
   from sealed traces, picks the threshold on development lineages and reports
   the hash's false-match and false-miss rates on held-out lineages, separately for
   whole frames and the text-heavy regions a program actually reads. Prior evidence
   covers photos and doc images, not interface screenshots.
2. Report novelty triggers as **true-positive rate at a stated false-trigger rate per
   hour** (NovelCraft: AUC ranking can reverse under false-positive control). A false
   yield costs delegation share; a miss lets a program act on an unfamiliar screen:
   report both.
3. Hash recurrence ("seen before") and anomaly judgment are different signals;
   keep the actor's `flags` emission and the monitor slot as the model-judged route
   and compare them with the hash on the same labelled set rather than assuming
   either is better. Embedding-distance methods (GEM-style) need internal access to
   an open-weight model and are not available for hosted routes.
4. Evidence level: thin (no source tests screenshot-only novelty detection for
   games from this decade).

## R9 Expectations and prediction error

**Evidence read.**
- PreAct ([2402.11534](https://arxiv.org/abs/2402.11534), v1 Feb 2024, v2 5 Dec 2024,
  COLING 2025; **abstract only**): adding predictions to ReAct-style reasoning
  reportedly beats ReAct; no benchmarks, numbers or token matching were readable.
  **STALE-FLAG**, abstract only.
- RWML ([2602.05842](https://arxiv.org/abs/2602.05842), Feb 2026, v3 1 Nov 2026,
  NeurIPS 2026; abstract): trains action-conditioned next-state prediction with an
  embedding-similarity reward; with task reward it beats task-reward RL by 6.9 pp
  (ALFWorld) and 5.7 pp (tau2-bench). This is **training**, not prompting an agent to
  state expectations; model-weight access is not available here.
- Self-prediction: "Reading the Plan" (NeurIPS 2026 workshop poster; [listing](https://neurips.cc/virtual/2026/168165);
  abstract; no arXiv version found): a probe on hidden states predicts the agent's
  next tool calls 12-30 points better than its verbalized predictions with 3-shot
  chain of thought. Open-weight internals, tool-call identity not environment outcome,
  models unnamed.
- Calibration: Last Step Matters ([2608.29685](https://arxiv.org/html/2608.29685),
  30 Aug 2026; full text extracted, 13k characters unread): five open-weight models,
  three deep-research benchmarks, eight rollouts per task; at 50% progress mean verbal
  confidence 77.05% vs success 30.77% (ECE 0.46); at completion 64.99% (ECE 0.34);
  final-step verbal-confidence AUROC 0.85 but no early signal above 0.60. BrowseConf
  ([2510.23458](https://arxiv.org/abs/2510.23458), Oct 2025; abstract): near-zero
  accuracy at low stated confidence in search agents.
- Surprise as a memory signal: Worth Remembering ([2606.03787](https://arxiv.org/abs/2606.03787),
  Jun 2026; abstract): Bayesian surprise in a video-model latent gates robot episodic
  memory (claims at least 12% better QA); baselines unreadable; robotics.

**Restates earlier work (my assessment; predictive-processing, TD and curiosity
sources not read).** Surprise gating looks like the novelty/curiosity literature.

**Finding.** I found **no study** that compares an agent required to state an
expectation before each action against an otherwise identical agent that does not,
at matched tokens, on long-horizon play. What exists: prediction-conditioned
prompting (abstract only, Dec 2024), trained world models (needs weights), and
calibration studies showing stated confidence ranks outcomes late but is
miscalibrated. Expectation as a **side effect on the actor's behaviour** is untested
(the Regression Tax's displacement mechanisms suggest a possible cost, but it was
measured for skills, not expectations).

**Recommendation for ADR 009 (R9).**
1. Keep expectations required (owner decision D10) but state in the ADR that benefit
   to the **actor's** play is unproven; their justified role is as a measurable
   signal for the curator and program predicates. Test the actor-side effect in the
   P0 emission feasibility run: same-seed short runs with and without required
   expectations, matched tokens, reporting pace, survival and variance across repeated
   calls, as development evidence only.
2. Score expectations automatically wherever the claim can be checked against the
   next observation (the expectation hit rate); score free text with a judge only
   after measuring judge agreement and false-pass rate on a labelled set.
3. Use `confidence` as a **ranking signal**, evaluated by AUROC or rank correlation
   with outcomes; report calibration (Brier, ECE) per bin with counts, and never as
   probability (consistent with ADR R3 language). Do not use early-episode confidence
   to predict failure.
4. Before using prediction error as the curator's attention signal, show on
   P0 development data that low-expectation-match steps are enriched for the
   forgetting episodes' retrieval misses; otherwise drop it from the brief.
5. Evidence level: thin; newest relevant primary text is Aug 2026, but the sources
   are open-weight/deep-research or abstract-only.

## R10 Offline evaluation of policies

**Evidence read.**
- The Replay Gap ([2608.08239](https://arxiv.org/abs/2608.08239), v1 8 Aug 2026;
  body extracted, and Table 1 re-read from the PDF text): forking SWE-bench
  trajectories at 30% and 70% and swapping in another model, in **both directions**
  (small-to-large "up" and large-to-small "down"), rewrote 61-94% of later actions.
  Table 1 "replay validity" (fraction of post-fork states a replay evaluator would
  score against the correct world): swap@early **3.2% (up) and 8.0% (down)**, swap@late
  34.4% (up) and 39.4% (down); control forks 27.3-85.8% by arm. The abstract's "only
  3%" is the up@early cell, not a pooled figure. A log-stitching evaluator got 0 of 5
  decisive calls right, worse than the constant "predict failure" evaluator (2 of
  5); six seed-matched run pairs, about 900 rollouts, 717 scored branch pairs,
  resolution rates 0-3%, one scaffold, one benchmark, one model family, quantized
  models. **Venue:** the PDF says "Accepted at the Efficient Reasoning Workshop,
  COLM 2026"; the page I fetched described it as a COLM paper; I treat it as a workshop
  paper. The authors frame replay as a
  degenerate off-policy estimator and note importance sampling's effective sample size
  collapses over long horizons and unbounded text actions violate coverage.
- ADWM ([2606.05558](https://arxiv.org/abs/2606.05558), Jun 2026, v3 5 Nov 2026;
  abstract): a learned diffusion world model for off-policy evaluation of LLM agents;
  no baselines, numbers or limitations readable; supports no conclusion.
- Doubly robust ([1103.4601](https://arxiv.org/abs/1103.4601), 2011; abstract):
  accurate value estimates if either a reward model or a behaviour-policy model is
  good; contextual bandits. STALE-FLAG as to LLM agents; it needs action
  probabilities under the logging policy, which an LLM actor does not expose.
- Behaviour-cloning metrics: the claim that held-out action error is a weak
  predictor of closed-loop success came from search summaries; the one abstract I
  read (ABC, [2606.27375](https://arxiv.org/abs/2606.27375), Jun 2026) says the
  opposite for a simulator-real co-training recipe. **No supported conclusion either
  way** from my reading.

**Restates earlier work.** The Replay Gap's authors themselves call replay a
degenerate off-policy estimator. That agreement with logged actions is behaviour-
cloning accuracy, and that DR/IS are older tools, are my assessments (behaviour-
cloning and importance-sampling sources not read).

**Recommendation for ADR 009 (R10).**
1. Keep "filter, not proof" (the ADR already says it). Add the reasons, both my
   inference rather than a source finding: an LLM actor as run here logs no action
   probabilities, and a deterministic program's actions may often differ from the
   actor's (unmeasured; this is a prediction to check), so overlap may fail; the
   Replay Gap's authors name long-horizon effective-sample-size collapse and uncovered
   text actions as obstacles to IS/DR. Do not report IS/DR estimates. Any future
   offline estimator must be validated against **branched live ground truth** (the
   practice instance, R11) as the Replay Gap does, before use.
2. Report agreement against baselines: a trivial predictor (repeat last input,
   majority input) and the **actor's own run-to-run agreement on the same frame**
   (repeated LLM calls), so "agreement" is read against its noise ceiling.
3. Where program and actor disagree, disagreement is not failure: audit a blind
   sample of disagreements by frames, report the labelled rates.
4. Keep the P1 offline claim restricted to **what would have been placed in front of
   the actor** (the ADR's definition); the evidence shows replay misjudges downstream
   behaviour once actions differ, so no P1 offline result may be phrased as a
   behavioural or outcome gain.

## R11 Practice environments

**Evidence read.**
- The Replay Gap (above): prefix re-execution in containers verified 99.99%
  return-code agreement; paired **same-model control forks** isolate sampling/replay
  noise (FP8-served 4B controls diverged on 90-96% of forks, AWQ-served 14B controls
  near-identical: serving stack and/or model size, which the paper says are
  confounded; 359 control forks had no outcome flips); forking and swapping has
  live-rollout ground truth.
- Crab ([2604.28138](https://arxiv.org/abs/2604.28138), 30 Apr 2026; abstract):
  Linux agent sandboxes; chat-history-only recovery 8% correct vs 100% with
  OS-state checkpointing; over 75% of turns produce no recovery-relevant state.
  Eval on two workload types; "up to 87%" traffic reduction.
- Shepherd ([2605.10913](https://arxiv.org/html/2605.10913), v3 24 Jun 2026; full
  text extracted, 132k characters unread): copy-on-write forks in 134-143 ms vs
  Docker commit 660-725 ms on Terminal-Bench images; authors' own hardware and
  baselines; authors call supervision results a "proof of existence".
- rr ([1705.05937](https://arxiv.org/abs/1705.05937), 2017; abstract): user-space
  record and replay works only on CPUs and kernels meeting non-obvious constraints
  (stated for modern Intel and Linux). STALE-FLAG.
- CAR ([2606.08275](https://arxiv.org/html/2606.08275), 6 Jun 2026; full text
  extracted): counterfactual step attribution by resampling; validated on synthetic
  causal models only; says it reports action-match rate for replay but gives none;
  real tools with side effects out of scope.

**Restates earlier work (my assessment; classical checkpoint/VM-snapshot sources not read).**
Record and replay, checkpoint/restore and VM snapshots look like the origin.

**Gap.** Every source read is on Linux containers or processes. **None covers
forking or replaying a native macOS graphical application with real-time input.**
Whether the target games react to focus loss or are deterministic given a save and
an input sequence is unmeasured (the ADR already says so).

**Recommendation for ADR 009 (R11).**
1. Make P3's determinism measurement the first deliverable and specify it as: from one
   boundary save, run the same input sequence N times and report, by input-prefix
   length, the fraction of runs matching on a pre-registered outcome set and on frame
   hashes (with the R8 hash calibration); include the clock and input-timing path in
   the report, because real-time input relative to frames is a plausible
   nondeterminism source (inference, not a source finding).
2. Use **same-program control forks** in every practice experiment (the Replay
   Gap's design) so the noise floor is measured, not assumed; a practice result is
   compared against its control, never against a lone run.
3. Do not cite fork or restore speed figures as transferable: they are Linux/
   container numbers; measure fork cost for the real app copy.
4. Counterfactual attribution (CAR-style resampling) is not supported for stateful
   real tools; limit practice use to program trials, slot benchmarks and determinism.
5. Evidence level: thin for the platform; adequate only for the general design pattern.

## R12 Study design

**Evidence read.**
- Cluster-count limits: Canay, Santos and Shaikh ([Rev. Econ. Stat. 103(2), 2021](https://home.uchicago.edu/amshaikh/webfiles/wild.pdf);
  abstract and introduction read from the PDF text): wild-bootstrap validity with a
  small, fixed number of clusters holds only under conditions (homogeneity-like
  restrictions on covariates for the unstudentized test; the studentized test may
  over-reject by an amount that shrinks with cluster count). The introduction (read in
  PDF text, 2026-11-08) states that the analysis relies on the wild-bootstrap test's
  resemblance to a randomization test based on the **group of sign changes**, that its
  limiting rejection probability equals that of a level-alpha randomization test, and
  that this equivalence is "delicate" and depends on the specific implementation
  (and the studentized form does not enjoy it). So the sign-change granularity limit
  below also bounds the wild bootstrap at small cluster counts. The introduction also
  notes earlier simulations found good behaviour with as few as five clusters, and
  common methods "behave poorly" with few clusters. STALE-FLAG (published 2021,
  accepted 2019); econometrics, not LLM agents.
- Evaluation as experiment: Miller ([2411.00640](https://arxiv.org/abs/2411.00640),
  1 Nov 2024; abstract only): treats evals as samples from a super-population and
  gives formulas for differences and planning; clustering/power content not readable.
  STALE-FLAG.
- LLM-agent variance: the Replay Gap (control forks diverge 90-96% on quantized small
  models), Tamba (identical-run flips at default settings), the Regression Tax (one
  run per task, paired design, McNemar with Bonferroni), and SkillsBench v4 (3
  selected public trials per cell; no variance across trials read) show that run-level
  and call-level noise are large and often unreported.
- Sequential methods: Ramdas et al. ([2210.01948](https://arxiv.org/abs/2210.01948),
  Oct 2022, v2 Jun 2023; abstract): e-processes and confidence sequences remain valid at
  any stopping time. STALE-FLAG. Zampieri ([2512.04366](https://arxiv.org/abs/2512.04366),
  Dec 2025, v9 10 May 2026; abstract): randomization-based e-value sequential tests
  whose validity comes from the randomization, not asymptotics; the abstract
  reports simulations of calibration and power without numbers; single author.
  **No source I read covers group-sequential designs, alpha spending or futility
  stopping**, so recommendation 3 below is an unsupported hypothesis.

Not read, so supporting no conclusion (moved out of evidence): the Johari, Pekelis and
Walsh always-valid-inference paper (1512.04922; known only from a search description) and
the cluster-trial design-effect formula 1 + (m-1) x ICC (seen only in search summaries
of a tutorial; verify against Hayes and Moulton 2017 or Campbell et al. BMJ 2012
before pre-registration).

**Restates earlier work (my assessment; none of these classical sources read).**
Cluster-randomized trial design, group-sequential and anytime-valid methods and the
clustered-error literature look classical. The LLM-specific content is only the size
of noise.

**Arithmetic that bounds the studies (derived here, not a source claim).** With k
paired lineages, an exact paired sign-flip test has 2^k equally likely sign patterns,
so the smallest attainable two-sided p-value is 2^(1-k): 0.25 for k = 3, 0.125 for
k = 4, 0.0625 for k = 5, 0.03125 for k = 6 (one-sided: 0.125, 0.0625, 0.03125 at
k = 3, 4, 5). Consequences, stated carefully:
- **No exact randomization (sign-flip or permutation) test can reject at 5% with
  k = 3.** A parametric paired t test with df = 2 can reject (|t| > 4.30 two-sided),
  but only through an untestable distributional assumption at n = 3.
- The minimum attainable p is **necessary, not sufficient**: at k = 5 one-sided the
  test rejects only if all five lineages favour B, and at k = 6 two-sided only if all
  six agree in sign.
- In a study where arms are **randomized to lineages** (#470), the sign-flip test's
  validity comes from the random assignment. In **#178's offline replay nothing is
  randomized**: both arms are replayed on the same fixed traces, so a sign-flip test
  there rests on a symmetry/exchangeability assumption under the null, not on a design.
- Per the Canay et al. introduction (verified above), the wild bootstrap behaves like a
  sign-change randomization test, so the same granularity limit applies to it.

**Recommendation for ADR 009 (R12).**
1. Say in the ADR that the independent unit is the lineage and compute, before each
   study, the minimum number of lineages at which its pre-registered test can reject
   (necessary, not sufficient).
2. Prefer **paired exact randomization tests** for lineage-level claims when arms are
   randomized; where nothing is randomized (offline replay) report the exchangeability
   assumption; use clustered/wild bootstrap only above the cluster counts the cited
   theory and simulations support, with sensitivity to the resampling scheme, and not at
   three or four clusters.
3. **Unsupported hypothesis (no source read):** for spend control, a fixed maximum lineage
   count with futility-only interim looks, or a group-sequential plan with
   alpha-spending if efficacy stopping is wanted, is my suggestion from general
   practice. The sources read (Ramdas abstract, Zampieri abstract) show only that
   anytime-valid and randomization-based sequential tests exist; they give no power
   figures. Efficacy stops at small k are fragile (inference). The dollar cap stays
   a hard limit independent of the statistics. The lead should obtain a primary source
   (e.g. a group-sequential reference) before pre-registering any interim rule.
4. Simulate power from a generative model with explicit lineage-level variance
   (below) and report the sensitivity grid, since development data have too few
   lineages to estimate it.

## Study-design guidance

### #178: P1 offline study (arm A root validation plus pushed working set, against arm B curator)

Facts from the ADR and issue: held-out lineages are #382's `lh1`-`lh3`; probes written
blind and before replay; B is replayed over the same traces; held-out traces predate
emissions; ablations only where power allows.

1. **Unit of analysis.** The lineage is the only independent unit: probes and facts
   within a lineage share state. With three lineages no exact randomization test can
   reject at 5% (arithmetic above), and in offline replay nothing is randomized, so
   any such test would rest on an exchangeability assumption. Choose one of:
   (a) add held-out lineages: at least 5 for a one-sided test and 6 for a two-sided
   one is only the necessary minimum (all lineages must agree), so more are needed
   for real power. Caveats: new live lineages would **carry emissions, unlike
   lh1-lh3**, making the held-out set heterogeneous, they are the lineages #441
   (deferred by the owner on 8 November) was to supply, and the ADR's cost gate
   prices them; or (b) pre-register an **estimation-and-consistency criterion**: per-
   lineage effect, direction in every lineage, and a within-lineage interval from
   resampling facts (not probes), with the claim scope stated as "these three
   worlds, this actor and these models". Present (b) as descriptive, not as
   generalization (S-EVIDENCE: scope not beyond held-out variation). **State (b)'s
   false-pass rate:** requiring B to be ahead in all three lineages passes with
   probability 1/8 under a symmetric null (no true difference, either sign equally
   likely), so it is weak evidence by itself and needs a minimum effect size and
   the noise-floor (A-versus-A') checks below. (#178's emission-bearing baseline
   answers a different problem, the missing emissions, and is covered in item 7.
   Only new held-out lineages could carry it into the deciding comparison; development
   lineages never can.)
2. **Probe design.** Probe = (decision time, fact, supporting frames), written by the
   lead or an independent reviewer **from frames with #449's protocol, never from
   evaluator readers (ADR008)**, blind to arm, from the baseline trace and before
   either arm is replayed.
   Include: positive probes (fact should be in front of the actor), **negative
   probes** (stale or other-world facts that should not be surfaced), and the four
   development episodes only as development fit tests. Two annotators label a stratified
   subset; report Krippendorff's alpha (ADR R4 criterion) and resolve before
   freezing. Group probes by underlying fact and episode; deduplicate in the
   pre-registration. Record annotation cost per lineage in P0.
3. **Scoring.** Score on what the actor would have received at the decision
   (snapshot or diff content), not each arm's query interface. Hold the **context
   budget** (snapshot tokens) equal across arms, or report both and state the
   comparison is not budget-matched. **Simulate curator lag**: arm B's snapshot as
   of time t is the latest published by t under the lag distribution from the P0
   shadow run; report lag = 0 only as an upper bound. Omitting this gives B a
   look-ahead arm A does not have.
4. **Primary metric and paired reporting.** One primary: probe recall at matched
   budget (or rediscovery rate per ADR). Report per-probe discordance: A-miss/B-hit
   gains and A-hit/B-miss **regressions** (the Regression Tax lesson) and the false-
   or wrong-scope fact rate; secondary metrics under Holm control and labelled
   secondary. Report cost per lineage for B.
5. **Arm-B repeat variance.** The curator is an LLM; run B several times per lineage
   (count set by the power simulation) with per-arm replay caches, and report
   variation across repeats and across host/model pairs. Temperature 0 is not a
   determinism guarantee (Tamba; the Replay Gap), so single-run B is a deviation to
   disclose.
6. **Power simulation (pre-registered, before spend).** **Proposed change to
   existing text:** ADR 009 (Evaluation and studies, "Gate before spend") and #178
   say power is simulated "from the variance in development data". Development data
   hold at most one day-scale lineage, so lineage-level variance cannot be
   estimated from it; I propose gridding it (and the fact-level ICC) as a
   sensitivity analysis, with development data bounding only probe/fact-level noise.
   This departs from the ADR/#178 wording and needs the lead's decision. Generative
   model: per-lineage random effect on the A-versus-B difference in probe-hit
   probability; probes nested in facts nested in lineages; B-run noise term. Output: for
   each (k lineages, probes per lineage, B repeats): (i) false-positive rate under the
   null, including an **A-versus-A' negative control** (arm A replayed with a
   perturbation that should not change content, e.g. snapshot order or rebuild
   timing) and a null in which B's content is shuffled across lineages; (ii) power at the
   smallest effect of interest; (iii) the minimum attainable p-value of the chosen
   test; (iv) dollar cost. Freeze the simulation code, seeds, inputs and decision
   rule with a hash.
7. **Limitations to record:** held-out traces lack emissions, so B runs without the
   expectation attention signal it would have live (consider a separate,
   development-only emission-bearing replay); offline replay does not model behaviour
   change (R10); lineages share an actor model, route and start-state family.
8. **Live guards afterwards** (survival, pace, cost) stay non-inferiority checks; with
   few lineages state the margin and the minimum lineage count at which the check can
   fail.

### #470: P2 study (delegation share at matched failure rate; monitor detection)

1. **Delegation share and failure.** Unit: lineage (each lineage forks its own
   repository, so the library differs). Decisions within a lineage are clustered;
   report the ratio with a lineage-level paired contrast. Define "failure" in
   advance (death, forced stop, yield-on-failure, harm outcomes, regression events)
   and test **non-inferiority on failure with a stated margin**, not equality;
   failure counts, not decision counts, set power, and rare events need many lineage-
   hours: estimate the expected event count from development data before spend.
2. **Arms and controls.** Programs-allowed versus actor-only at matched model route,
   prompt and wall/budget, plus the "library visible, delegation disabled" control
   (R5). Report spend per decision and per game hour, matched or beside the outcome.
3. **Paired situation-level gains and regressions** for each program (R5), and the
   monitor's stop events split into prevented/neutral/harmful where determinable.
4. **Monitor detection.** Unit: program run (clustered by program and lineage).
   Labels: blind, from frames by an independent reviewer, never by the monitor's own
   model. Report TPR at fixed false-stop rate per program hour; separate
   natural anomalies (rare, report counts) from injected or perturbed ones
   (synthetic; flag and report apart); report anomalies missed because the monitor
   acted after the damaging input. Do not extrapolate beyond the programs observed.
5. **Slot bindings.** Evaluate each binding swap on held-out recorded cases plus the
   closed-loop fixture check (R6); keep slot caches per arm; log repeated-call variance.
6. **Hash/novelty yields.** Report the hash threshold's rates from the R8 pre-study and
   the yield rate it produces in play.
7. **Preemption guards.** Preemption latency distribution and fraction with unknown
   delivery; any permanent stop from unknown delivery is a reported outcome.
8. **Power and spend.** Simulate with lineage-level variance in delegation share and
   failure rate over a grid (the same proposed departure as #178 item 6 if
   development variance cannot supply lineage-level values). **Recommendation:**
   randomize the arm order within each matched pair, so a paired sign-flip test has
   a randomization basis. Randomization validates a sharp null. For non-inferiority
   with margin δ, apply the test to differences shifted by δ under a constant-effect
   null (effect δ in every pair), or decide by the conservative bound of a
   pre-registered interval. Pick **one-sided non-inferiority on failure** (the
   decision the ADR needs): the necessary minimum is 5 matched pairs for a one-sided 5% exact test,
   and at 5 pairs it rejects only if all five favour programs-allowed, so plan more
   (the 6-pair figure is the two-sided minimum and is not used here). State
   cost per lineage from the actor's measured $/game hour (ADR: $0.80 in #397) plus
   curator and monitor spend. Interim looks: an unsupported hypothesis (R12 item 3);
   the hard dollar cap stands. If the
   gate cannot reach the pre-registered detection rate within the envelope the study
   does not run (ADR rule).
9. **Pre-registration contents** (S-EVIDENCE): evaluation split, baselines and
   ablations, budget matching plan, frozen hash, deviations log, pinned versions of
   model, route, prompt, code and data.

## Recommendations summary for ADR 009

| Area | Recommendation | Evidence level |
| --- | --- | --- |
| R5 | Keep gate verification, probation, retirement; require paired gains/regressions, a library-visible control arm, judge-error measurement, retrieval-conditional reporting; do not assume induced programs help | Moderate for coding/office; thin for games |
| R6 | Exact-key replay of recorded outputs; held-out cases for slot swaps; two bindings per slot; closed-loop check; no training | Thin for screens; moderate for routing text |
| R7 | Monitor stop-only and described as having no guarantee; measure TPR at fixed false-stop rate; measure preemption and risk-class error | Thin |
| R8 | No imported hash threshold; local labelled calibration; TPR at fixed FPR; compare hash with model flags | Thin |
| R9 | Expectations justified as a curator signal, actor benefit untested; test burden/effect in P0; confidence as ranking only | Thin |
| R10 | Agreement is a filter; no IS/DR; compare to noise ceiling; P1 claims limited to surfaced content | Moderate for replay validity; thin for programs |
| R11 | Determinism study first with control forks; no transferred timing numbers | Thin for the platform |
| R12 | Lineage unit; no exact randomization test can reject at 5% with three lineages; paired exact tests where arms are randomized; interim-look rule is an unsupported hypothesis (no source read) | Classical sources all STALE-FLAG (2021 and earlier except two 2025-26 single-author/abstract items); LLM-specific noise evidence moderate |

## Sources

All retrieved 2026-11-08. "Full (extr.)" = body fetched and summarized by the fetch tool
(some truncated); "Abstract" = arXiv listing only; "Snippet" = search result text only
(**not relied on**). Flags: V = vendor or authors' own system; S = synthetic; 1R =
single run or unreplicated; W = workshop; ST = STALE-FLAG (newest relevant
revision before 2025-05-08).

| Source | Published (revised) | Read scope | Measured / baseline / budget matched / restates | Flags |
| --- | --- | --- | --- | --- |
| SkillsBench 2602.12670 **v4** | v1 2026-02-13, v2 03-07, v3 03-13, v4 2026-06-14 | Abstract + body (extr.), 100k of 175.7k chars | Pass rate: no skills, curated, self-generated (3 of 18 configs); no length-matched control | terminal tasks; v1 numbers withdrawn from this page |
| Regression Tax 2607.22520 | 2026-07-24 | Full (extr.) | Paired gains/regressions vs no skills; not token-matched; skill-ablation lineage | 1R (one run per task); single coder |
| Skill Following 2609.00549 | 2026-09-01 | Abstract | Same-task effect where retrieved; matched pairs | no numbers read |
| Ratchet 2605.22148 | v1 2026-05-21, v3 2026-08-07 (v2 unconfirmed) | Abstract + body (extr.), 100k of 135.6k chars | Rolling held-out pass@1 gain +0.328, MBPP+/100, 3 seeds; +0.0/+16.2 are cited from SkillsBench | one benchmark; filtered tasks; not independent of SkillsBench |
| ASI 2504.06821 | 2025-04 (v2 2025-08-29) | Full (extr.) | WebArena success; vanilla and AWM; budget not stated | one backbone; small subtests |
| SkillBrew 2605.29440 | 2026-05-28 | Abstract | Skill-bank curation | no results read |
| MMSkills 2605.13527 | 2026-05-13 (v3 06-01) | Abstract | GUI/game visual skills | no numbers; not relied on for conclusions |
| SCALAR 2603.09036 | 2026-03-10 | Abstract | Craftax diamond rate | baselines not named; not relied on |
| Is Escalation Worth It 2605.06350 | 2026-05-07 (v2 10-05) | Abstract | Cascade accuracy vs single model | single author |
| UCCI 2605.18796 | 2026-05-11 | Full (extr.) | Cost at equal F1, NER; baselines incl. conformal | 1 domain; independent author |
| TwinRouterBench 2605.18859 | 2026-05 (v5 10-24) | Full (extr.), 18k unread | Step-level routing; resolved count and API cost | V (one vendor-built benchmark); router diagnostic = Opus 4.6, one prompt; no repeats; 100 locked instances |
| Replay Gap 2608.08239 | 2026-08-08 (v1) | Body (extr.) + Table 1 from PDF text | Branched live rollouts vs replay; same-model control forks; up and down swaps | W (PDF: Efficient Reasoning Workshop, COLM 2026; page said COLM); quantized models; small n |
| Kang et al. 2505.17612 | 2025-05-23 (v2 11-05) | Abstract | Agent distillation to 0.5-3B | no numbers; not stale |
| SpecBench 2605.21384 | 2026-05-20 (v2 09-09) | Abstract | Visible vs held-out test gap, 30 coding tasks | R13 owns gate gaming |
| vCache 2502.03771 | 2025-02-06 (v5 2026-02-21) | Abstract | Semantic cache hit/error | authors' numbers |
| Tamba 2606.26185 | 2026-06-24 (v2 10-24) | Abstract | Judge flips at temp 0 | single author; 7 items |
| CAR 2606.08275 | 2026-06-06 | Full (extr.) | Counterfactual replay attribution | S; no real tools |
| Async Control 2512.13526 | 2025-12-15 | Abstract | Monitor FNR at 1% FPR; red team | coding envs |
| Reduced Supervision 2609.29547 | 2026-08-28 | Abstract/summary | Audit of 63 artifacts | conceptual |
| VIGIL 2606.26524 | 2026-06-25 | Abstract | Recall, FPR on agent runs | baselines not read |
| Shielding 1708.08611 | 2017-08 | Abstract | Shield synthesis | ST |
| Sema Code 2604.11045 | 2026-04-13 | Abstract | Architecture; no interruption eval | not evidence |
| GEM 2505.12842 | 2025-05 (v4 2025-11-22) | Full (extr.) | GUI OOD with internal embeddings | one ID set; open weights |
| Janiak et al. 2510.15202 | 2025-10-17 (v3 2026-03-03) | Abstract | Mahalanobis OOD vs representation | no numbers |
| Claros Olivares 2511.11934 | 2025-11-14 (v3 2026-05-17) | Abstract | OOD scores, rank pipeline | CIFAR-scale |
| NovelCraft 2206.11736 | 2022-06 (v3 2023-03) | Abstract | Visual novelty, game-like | ST |
| McKeown 2212.08035 | 2022-12-15 | Abstract | Hash Hamming distributions | ST; findings not on page |
| PreAct 2402.11534 | 2024-02 (v2 2024-12-05) | Abstract | Prediction in planning vs ReAct | ST; no numbers |
| RWML 2602.05842 | 2026-02-05 (v3 2026-11-01) | Abstract | Trained world model reward | needs weights |
| Reading the Plan | 2026 (NeurIPS workshop) | Abstract (listing) | Probe vs verbalized self-prediction | W; models unnamed |
| Last Step Matters 2608.29685 | 2026-08-30 | Full (extr.), 13k unread | Verbal confidence calibration | open-weight, QA tasks |
| BrowseConf 2510.23458 | 2025-10-27 | Abstract | Confidence-guided test-time scaling | no numbers |
| Worth Remembering 2606.03787 | 2026-06-02 | Abstract | Surprise-gated memory, robotics | baselines unread |
| ADWM 2606.05558 | 2026-06-04 (v3 11-05) | Abstract | Model-based OPE | nothing readable |
| Dudik et al. 1103.4601 | 2011 | Abstract | Doubly robust estimator | ST |
| ABC 2606.27375 | 2026-06-25 | Abstract | BC stack; sim-real correlation | not relied on |
| Crab 2604.28138 | 2026-04-30 | Abstract | Agent sandbox checkpoint/restore | Linux; V |
| Shepherd 2605.10913 | 2026 (v3 06-24) | Full (extr.), 132k unread | Fork latency, meta-agents | V; authors' hardware |
| rr 1705.05937 | 2017-05-16 | Abstract | Record and replay | ST |
| Canay et al. (REStat 2021) | 2021 | Abstract and introduction | Wild bootstrap few clusters | ST; econometrics |
| Miller 2411.00640 | 2024-11-01 | Abstract | Eval error bars | ST |
| Ramdas et al. 2210.01948 | 2022-10 (v2 2023-06) | Abstract | Anytime-valid inference | ST |
| Zampieri 2512.04366 | 2025-12-04 (v9 2026-05-10) | Abstract | Sequential randomization e-tests | single author |

**Seen as snippets only; not relied on:** MIND-Skill 2605.08670; SkillForge 2608.24747;
CoEvoSkills 2604.01687; Scaling Laws of Skills 2605.16508; the large real-skills
study reported by a news site; RouteNLP 2604.23577; Cluster-Route-Escalate 2606.27457;
WinDOM 2606.25964; LiteGUI; AgentSpec 2503.18666; Agent-C 2512.23738; AgentFlow
2608.22868; multi-aspect runtime verification 2610.08928; Agents Explore but Agents
Ignore 2604.17609; Jain et al. 2106.09820 (hash false positives); Behavior Cloning
under PD control 2604.14484; UItron 2508.21767; Johari et al. 1512.04922 (fetched
nothing but a search description); design-effect tutorials; Wild Bootstrap
Randomization Inference for Few Treated Clusters; blog and vendor pages on hashing,
caching, sandboxes and sequential testing.
