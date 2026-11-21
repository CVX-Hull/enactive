---
owner: lead
status: active
date: 2026-11-08
scope: Evidence for comparing belief representations on matched observations
review_trigger: New matched-case evidence changes the choice of a belief representation
---

# Research on belief under conflict

This review examines how agent memory handles conflicting observations and what evidence
could decide between qualitative revision and a numerical representation. It shares the
[search method and read limits](research-curated-memory.md#brief-and-method) of the
8 November review and includes the targeted recheck of 16 November.

## Brief and method

- Belief under conflict covers subjective logic, Bayesian and Dempster-Shafer fusion, source reliability, staleness, opinion pooling, calibration and how to test the choice offline. The production choice is open under the [decision to compare belief representations on matched cases](decisions/owner-decisions.md#compare-belief-representations-on-matched-cases).

The 8 November search read stated sections
of Jøsang's fission paper on cumulative and averaging fusion (S16). The 16 November
recheck covers selected sections of the sources named under belief and in the source
list. Unread foundations support no conclusion.

Query 15 was the
**citing-work search** on Jøsang's fusion operators (cumulative/averaging fusion,
empirical comparison against Bayesian/Dempster, 2025-2026). Query 15 found no 2025-2026
empirical comparison; the newest relevant primary text read is a 2024-12 preprint
(S25, revised 2025-03-28, **RECENCY**).

## Belief under conflicting observations

The production representation remains open. The
[belief comparison decision](decisions/owner-decisions.md#compare-belief-representations-on-matched-cases)
calls for replaying matched cases with source-linked qualitative revision and a
specified numerical belief model.

**Evidence on LLM-agent belief and conflict.**
- *Bayesian updating with reliability* (S09, Nous; v1 2026-06-20 / v2 2026-07-16;
  single author; stated sections via extractor). Per entity-attribute categorical
  posterior; reliability r from an LLM reading epistemic markers. Three separate
  results, not to be merged:
  (a) **Real data (LoCoMo, 385-question subset):** the Bayesian update is described
  as "effectively inert": full engine 69.62 judge / 36.77 token-F1 versus
  last-write-wins 72.46 / 36.27. Bayesian updating adds little over latest-write-wins
  on conversational data. Also a 27.5-point gap between strict token-F1 and
  LLM-judge scores on identical outputs, and the A-MEM and MemGPT baseline scores come
  from another paper on a different backbone (gemini-2.5-flash here), so comparison with
  those is indicative.
  (b) **No-LLM belief-layer micro-benchmark:** with constant reliability LWW beat the
  Bayesian rule (73.5 vs 67.1); with varying reliability Bayesian 100, LWW 74.3,
  frequency 48.2.
  (c) **60-scenario, five-regime synthetic benchmark** (the "realistic" macro averages
  only the first four regimes and excludes the adversarial one): reliability-aware
  100, LWW 67, frequency 46, append-and-retrieve 90; in the adversarial regime
  reliability-aware scored **0**, versus LWW 42, frequency 50, append-and-retrieve 17.
  Stated limits: the confidence-correctness link is built in for four of five regimes,
  reliability estimates are near-binary and rubric-based, provenance tiers in the
  poisoning defense are oracle-assigned, entropy decay is never exercised by the real
  benchmark, one backbone, **no calibration metric reported**. Provenance-capped
  poisoning defense: 0% attack success against 100% for LWW in a simulation (400
  trials per cell), but a legitimate low-tier correction cost accuracy (100% to 54%).
- *Detection is not application* (S10, STALE, v1 2026-05-07 only, stated sections
  via extractor: first 100k of 186,845 chars plus an appendix read from 100k onward;
  the CUPMem results table sits in the first part, the unread middle was not used). 400
  expert-validated, LLM-generated implicit-conflict scenarios and 1,200 queries; best
  model 55.2% overall; one model detected stale state 92.0% (Type I) but rejected a
  premise built on the stale state only 30.0%; propagated (Type II) conflicts harder.
  A write-time adjudication step (KEEP, STALE, REPLACE, UNKNOWN) plus propagation-aware
  search plus constrained readout lifted GPT-4o-mini from 8.7% to 68.0% on the
  authors' own benchmark, with an LLM judge (95.8% agreement with humans), a
  predefined state schema, one-shot transitions only. Vendor-neutral but
  **author-built benchmark and author-built fix**; not independently replicated.
- *Over-trust of stale memory* (S11, extractor). Synthetic frozen benchmark, 300
  templated scenarios, Qwen3 0.6B to 8B plus Llama; stale-value reliance 0.92 to 1.00;
  a stale note dated newer fooled larger models more; exposing metadata helped at every
  size (+0.30 [0.17, 0.42] at 0.6B, +0.28 at 1.7B, +0.53 at 4B, +0.54 at 8B), more
  at the larger sizes. The **pre-resolved arm is an oracle that removes the stale item
  entirely** (gains +0.46 to +0.63, accuracy 0.95 to 1.00); it shows what *correct*
  resolution is worth, not that any real resolver achieves it. An external check on
  RGB and MisBench reproduced stale reliance on RGB (Delta-memory negative at 4B and
  8B) and sat near the floor on MisBench because models do not know the facts.
  Exploratory factorial analyses, action-scored with no judge, measured at
  consumption time only; one author team (PayPal AI), v1 only (2026-09-01).
- *LLM as truth-discovery component* (S15, extractor). On three tabular fusion
  datasets GPT-4o-mini beat majority vote, source-reliability voting, a Bayesian latent
  truth model and a domain-aware method (F1 0.78 to 0.91 vs best baseline 0.70 to 0.82),
  but another model scored 0.3362 on one dataset, single runs, no variance, possible
  memorization of public data; the LLM method did not model source reliability
  explicitly. Fusion of web tables, not of agent observations.
- *Contradiction operators* (S12): see [concurrent consolidation](research-curated-memory.md#concurrent-or-background-consolidation); four write-time operators (LWW,
  evidence-weighted merge, await-confirmation, per-rule policy) with isolation
  preconditions; evidence thin and underpowered.

**Evidence on formalisms.**
- *Subjective logic.* Jøsang's fission page (S16, arXiv v1 2007-12-07, working paper,
  stated sections via ar5iv extractor, **RECENCY**) states: cumulative fusion is for
  independent evidence (e.g. observations from disjoint time periods; non-idempotent),
  averaging fusion is for dependent evidence (idempotent, non-associative); fission
  removes a contribution. The page does not discuss double counting explicitly. A
  citing-work search (query 15) found one primary text that evaluates these operators
  empirically, S25 (Bezirganyan et al., arXiv 2412.18024, **v1 2024-12-23, v2
  2025-03-28, published at AISTATS 2025 (PMLR 258), RECENCY**; stated sections via
  extractor): multimodal
  deep-learning classifiers on five small datasets, 10 seeds, in which the fusion
  operators' behavior under conflict is compared. It reports, as the authors' own
  analysis, that a Dempster-style constraint fusion can assign full confidence to a class
  both sources considered unlikely, that cumulative fusion treats views as independent
  so uncertainty falls when a view is added even under conflict, and that averaging
  fusion is non-associative and does not raise uncertainty for conflicting views.
  It proposes discounting by pairwise conflict and reports better conflict detection;
  the size of that gain per dataset was not verified here.
  This neural multimodal classification study supports testing a fusion operator's
  independence assumptions and its behavior under conflict. Its domain does not
  establish utility for agent memory. BeliefMem uses noisy-OR merging.
- *Dempster-Shafer.* I could not read Zadeh's 1979 memorandum (scanned PDF). S25
  supplies a neural-network example of the same pathology (above). Snippets only, no
  conclusion: the controversy is whether the conflict-normalizing rule is flawed or the
  example's modelling is (Haenni). No source read supports choosing Dempster's rule.
- *Source reliability, staleness, pooling and calibration.* Dawid–Skene and
  Kaplan–Meier were unread. The [targeted primary-source recheck](design/belief-method-comparison.md#primary-foundations-and-what-they-support)
  covers provenance, proper scoring rules, censoring and partial pooling. No agent
  study read estimates per-type staleness rates, and S09 leaves decay unexercised
  on real data. The [synthetic Brier comparison](research-memory-representations.md#what-the-experiments-changed)
  is internal development evidence.

**Recommendation on the ADR's open decision on the belief model.**
1. **Keep explicit provenance, supersession and visible disputes.** The project uses
   no numerical belief calculus. The 2026-11-16 recheck of Jøsang (2013, §§3.1.1–3.1.3
   and §4.7) verifies the binomial-opinion/Beta mapping and the fusion assumptions.
   With matched evidence and priors their projected probabilities agree, so use the
   mapping as an equivalence control. No source read compares subjective-logic fusion,
   Beta counts, last-write-wins or Dempster–Shafer on agent memory. Independence in
   curator observations needs testing before cumulative fusion is justified (S16, S25).
2. **Test numerical updates, staleness and partial pooling offline.** Compare on
   matched extractions against the provenance-aware qualitative baseline. Candidate
   evidence models retain positive and negative re-observations and timestamps, count
   duplicate origins once, and test whether distinct re-observations add support.
   Include aging-off and no-pooling controls. S25 motivates explicit conflict cases
   because cumulative fusion can lower uncertainty under conflict. Other comparators
   include last-write-wins with supersession (S09) and write-time adjudication labels
   KEEP/STALE/REPLACE/UNKNOWN (S10). The proposed
   [CDDA belief-method comparison](design/belief-method-comparison.md) specifies the
   matched-evidence tests and separates replay from live decision benefit.
3. **Resolve conflict at the gate, but keep disputes visible.** S10 and S11 both found
   models fail to apply updates even when they detect them, and S11's oracle that
   removes the stale item restored accuracy to 0.95 to 1.00. That shows only that
   **correct** resolution helps; no source measured the cost of a wrong resolution, and
   S09's provenance cap cost accuracy (100% to 54%) on legitimate corrections. So the
   proposed gate supplies a labelled value with provenance where it can adjudicate
   the dispute and leaves an explicit disputed/UNKNOWN label otherwise. S11 also
   found metadata exposure helped the 0.6B model (+0.30). The current screen takes
   precedence over stored assertions.
4. **Calibration is reported offline; whether to hide probabilities from the actor is
   a design choice, not an evidenced one.** The ADR's rule that uncalibrated scores are
   not labelled probabilities stands; no source read validates a calibration approach
   or tests how an agent uses a probability for this setting.
5. **Offline test of the choice (pre-register per S-EVIDENCE before running).**
   - *Two data lanes, reported separately.* (i) Trace-based: sealed traces split by
     lineage, development versus a frozen holdout. Re-observation conflates staleness
     (the world changed) with refutation (the earlier assertion was wrong), so
     trace-based scores are not read as staleness or reliability estimates. (ii)
     Generator-based: a synthetic generator with regimes for constant reliability,
     varying reliability, adversarial/poisoned sources, duplicated observations
     (dependence) and drift. S09 shows the winner flips across regimes and loses
     entirely in its adversarial one, so no single regime decides. Pre-register
     regime weights from development-lane rates and report every regime separately,
     never only the weighted macro.
   - *Arms.* Compare last-write-wins, learned-reliability Beta counts, averaging and
     cumulative fusion, write-time adjudication, the qualitative baseline and flat
     raw-episode retrieval. Hold one extracted assertion set fixed across arms.
     Score calibration only for methods that produce probabilities.
   - *Budget.* Report calls, tokens and wall time beside each outcome. Account for
     extra calls from reliability estimation and adjudication when comparing costs.
   - *Outcomes.* Accuracy of the predicted current value at later re-observation;
     where a probability exists, Brier or log score with a reliability diagram and ECE
     with intervals; retrieval-miss rate; a double-counting stress (replay one
     observation n times; the score must not rise); legitimate-correction cost
     (S09's 100% to 54%); and **wrong-resolution cost** (inject wrong resolutions and
     measure actor error), which no source measured.
   - *Statistics.* The independent unit is the lineage, and every variant tried is
     reported. Lineages the [curator memory study](acceptance/2026-11-12-p1-descriptive-completion-178.md)
     inspected are development data. Freeze a separate
     whole-lineage holdout for the trace lane.
     - **Trace lane.** With three clusters a cluster bootstrap has only 10 distinct
       resample compositions. At that size report each lineage descriptively and
       avoid gating on an interval.
     - **Generator lane.** Interval-based gating is used only here, where the clusters
       are many. **Compute and report the minimum detectable difference by simulation
       before spending.**
     - **Before running, freeze and hash two things.** The generator, with its regime
       weights. And a rule for when the lanes disagree, for example "adopt only if the
       generator lane passes and no held-out lineage reverses the direction".
     - **Claim scope.** The decision claim is scoped to the generator's regimes. The
       trace lane is the only held-out check of whether those regimes resemble play
       (S-EVIDENCE: generality needs held-out support).
   - Any rule or threshold chosen on development lineages is not evaluated on them.
6. Staleness, pooling and calibration have mathematical foundations. Their validity
   and utility for curator memory need evidence from play traces.

## Weakest-evidence summary

| Area | Strength | Why |
| --- | --- | --- |
| Belief under conflict: decay, pooling, calibration, reliability without ground truth | Very thin for agent memory | The primary foundations establish methods. No LLM-agent source estimates per-type staleness rates, and one benchmark builds in its reliability signal |

## Sources

The table covers the **2026-11-08 literature search**. The **2026-11-16 targeted
recheck** covers Jøsang, Green et al., Gneiting and Raftery, the NIST censoring
guidance and Gelman. Their specific read scopes and transfer limits are in the
[belief-method comparison](design/belief-method-comparison.md#primary-foundations-and-what-they-support).

Dates are the arXiv abs-page submission history. "Extractor" =
text retrieved through the fetch tool and queried for stated sections (see the [read scope](research-curated-memory.md#brief-and-method)); "first 100k of N" means the remainder was not read and no claim rests on it.
"Budget matched" = whether compute, calls or tokens were matched across compared arms.

| ID | Source | Date (v1 / revised) | Read scope | Measured / baseline / budget matched / flags |
| --- | --- | --- | --- | --- |
| S09 | When Does Belief-Based Agent Memory Help? (Nous), arXiv 2606.22030 | v1 2026-06-20 / v2 2026-07-16 (page byline 2026-08-24 is not a version date) | Stated sections via extractor (v2) | Single author; one backbone; three separate results (LoCoMo, belief-layer micro-benchmark, five-regime synthetic); not budget matched; no calibration |
| S10 | STALE, arXiv 2605.06527 | v1 2026-05-07 (only version) | Stated sections via extractor: first 100k of 186,845 chars plus text from 100k onward (appendices); middle not claimed | 400 LLM-generated expert-validated scenarios; authors' own benchmark and fix; LLM judge; page includes base64 prompt templates, treated as data |
| S11 | The Memory Trust Gap, arXiv 2609.01852 | v1 2026-09-01 (only version) | Stated sections via extractor | Synthetic frozen benchmark, small models; oracle pre-resolution arm; exploratory factorials; RGB/MisBench external check |
| S12 | TOKI, arXiv 2606.06240 | v1 2026-06-04 (only version) | Stated sections via extractor, first 100k of 269,356 chars | Operator algebra, LoCoMo; ablation definitions and data provenance in the unread appendix; cross-system comparison underpowered |
| S15 | Single and Multi Truth Data Fusion using LLMs, arXiv 2606.28062 | v1 2026-06-26 (only version) | Stated sections via extractor | Three tabular datasets vs classical truth discovery; single runs; model variance |
| S16 | Jøsang, Cumulative and Averaging Fission of Beliefs, arXiv 0712.1182 | v1 2007-12-07 (only version) | Stated sections via ar5iv extractor | Definitions only; **RECENCY** |
| S25 | Multimodal Learning with Uncertainty Quantification based on Discounted Belief Fusion, arXiv 2412.18024 | v1 2024-12-23 / v2 2025-03-28; AISTATS 2025 (PMLR 258), peer-reviewed; **RECENCY** | Stated sections via extractor | Five small datasets, 10 seeds per experiment; neural classifiers; hyperparameters tuned on one baseline |
| X2 | Search-snippet leads: Mem-T, AdaMem, AutoSchemaKG, 2609.22133, quallmer, CLARIFY, 2506.02509, 2401.03426, Yao et al. 2024, Haenni, Dezert-Tchamova, CHI 2026 dashboard, 2608.20597, Singapore Consensus, Letta/vendor blogs, Jøsang-Pope 2012, 1805.01388 | various | Snippet only (1805.01388 PDF unreadable) | **Support no conclusion**; vendor items excluded |
| X3 | Unreadable or unretrieved foundations: Zadeh 1979 memo (scan), Jøsang 2009 slides, Dezert-Tchamova, evidence-based subjective logic flow paper, Dawid–Skene, Kaplan–Meier, Rissanen, Krippendorff, Fellegi-Sunter, Sheridan, Endsley, McClelland, Soar/ACT-R, Tulving | various | **Not read** | No conclusion rests on them |
