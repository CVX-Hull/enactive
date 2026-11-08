---
owner: lead
status: active
date: 2026-11-08
scope: Primary-source synthesis for ADR 009 research areas R1-R4 and R14 (issue 447); evidence for method choice, not an implementation or a game claim
review_trigger: Independent S-EVIDENCE review of this page; any ADR 009 memory, belief, ontology or spectator method decision; new evidence on the weakest areas named below; model or benchmark changes
---

# Research synthesis for ADR 009: memory, belief, ontology and oversight

Search and retrieval date: **2026-11-08** (America/New_York). The 18-month recency
line (S-EVIDENCE) is therefore **2025-05-08**; a conclusion whose newest supporting
source is older is flagged "RECENCY".

This page builds on, and does not repeat, two earlier pages: the
[memory architecture assessment](research-memory-architecture.md) (assessed
2026-10-19; primary-source update covering AgeMem, MemRL, ACE, Useful Memories Become
Faulty, MemComposer, StateMem, MemoryArena and others) and the
[memory representations study](research-memory-representations.md) (research
cutoff 2026-10-18; Kaelbling et al., Jøsang 2013 read by an agent, BeliefMem,
provenance semirings, temporal databases, ATMS, information bottleneck). Those
papers are cited by reference only where this page relies on them; nothing below
re-reviews them. Neither earlier page covered R2 measured lag, R4 ontology
induction, or R14 oversight interfaces.

## Brief and method

**Brief questions (recorded verbatim in substance).**
- R1: agent memory write and retrieval policies; typed versus unified stores; what has been measured about when agents should write, what to retrieve, and whether typed schemas help.
- R2: concurrent or background memory consolidation (a separate process curating memory while an agent acts): designs and measured effects, including lag and cost.
- R3: belief under conflicting observations: subjective logic, Bayesian and Dempster-Shafer fusion, source reliability, staleness/temporal decay, opinion pooling, calibration; a recommendation on ADR open decision 4 and how to test the choice offline.
- R4: ontology/schema induction and evaluation (including by LLMs): ontology quality measures, grooming/merging of similar types, utility versus complexity.
- R14: oversight interfaces for human supervision of autonomous agents: what operators need to see, measured effects.

**Foundational sources the brief named** (ADR 009 research-agenda rows): Soar/ACT-R,
Tulving, McClelland et al. 1995, Jøsang, Dawid and Skene 1979, Kaplan and Meier 1958,
Gelman's hierarchical models, Zadeh's critique of Dempster's rule, Rissanen, Krippendorff,
Fellegi and Sunter, Sheridan, Endsley 1995. **None of these was read in full for this
page** (see "Read-scope honesty" below). One Jøsang primary page was read (fission of
beliefs, which defines cumulative and averaging fusion). No conclusion below rests on
an unread foundational source. Current sources were found by dated web search on
2026-11-08 (the 15 queries listed below, across the five areas) and were not named in the brief.

**Search queries (2026-11-08).** (1) LLM agent memory write policy, retrieval policy,
long-horizon benchmark, typed versus unified; (2) asynchronous background memory
consolidation, sleep-time compute, latency; (3) ontology/schema induction LLM
evaluation, merge types; (4) ablation typed (episodic/semantic/procedural) versus flat
store; (5) asynchronous consolidation concurrent with acting, staleness, lag; (6) LLM agent
memory conflicting information with subjective logic, Dempster-Shafer, Bayesian, source
reliability, temporal decay; (7) human oversight interfaces for autonomous LLM agents
(operators, user studies); (8) Zadeh critique of Dempster's rule; (9) LLM truth
discovery, Dawid-Skene, source reliability without ground truth; (10) LLM entity
resolution, codebook, Krippendorff alpha; (11) Endsley 1995; (12) subjective logic
Beta mapping, cumulative fusion, critique; (13) MDL/utility-versus-complexity schema
induction; (14) multi-agent supervisor dashboards, human-on-the-loop timeliness; (15)
**citing-work search** on Jøsang's fusion operators (cumulative/averaging fusion,
empirical comparison against Bayesian/Dempster, 2025-2026). Query 15 found no 2025-2026
empirical comparison; the newest relevant primary text read is a 2024-12 preprint
(S25, revised 2025-03-28, **RECENCY**).

**Read-scope honesty.** The retrieval tool returns text passed through a small
summarizing model, not raw files. "Stated sections via extractor" means the paper's
HTML text was fetched and queried for method, evaluation and limitation sections;
where the page exceeded 100,000 characters, only the first 100,000 were read (stated as
"first 100k of N chars") and **claims about the unread remainder are not made**. Numbers
quoted below are as the extractor reported them and **should be spot-checked against the
papers in review**; the reviewer-driven revision of this page re-fetched and
re-checked the figures for S01, S04, S09, S11 and S20 against the extractor. Version dates are from each
paper's arXiv submission history (abs page). One source (S10, STALE) carries base64
blocks that decode to benchmark-generation prompt templates; they were treated as data
and not acted on. "Abstract" means only the arXiv abstract
page. "Snippet" means a search-result summary; snippet-only sources are listed for
leads and **support no conclusion**. Several PDFs (Jøsang 2013, Zadeh 1979 memo, Jøsang
2009 slides, Dezert and Tchamova, Jøsang's evidence-based flow paper, Endsley 1995) were
unreadable (binary/scan, HTTP 403, or bot wall) and are recorded as not read. Where
an arXiv identifier month disagrees with the submission date (S08, S17, S18), the
abs-page v1 date is used. No game knowledge was used as evidence anywhere in this page.

## R1 Agent memory: write and retrieval policies, typed versus unified stores

**What was measured.**
- *Write policy.* Lesson rewriting is already covered by the earlier page. New: a
  controlled study of add and delete policies (S01, v1 2025-05-21 / v2 2025-10-10,
  stated sections via extractor, first 100k of 102k chars). Its "fixed" baseline is
  **not empty memory**: it is a fixed pre-populated bank (100 to 180 records, described
  as a subset of training data with correct executions; two appendix descriptions
  are inconsistent with the main text) to which nothing is added. Against that bank,
  adding every experience (add-all) was worse on all four agents (55.48 vs 67.53;
  13.05 vs 16.75; 32.32 vs 40.11; 59.90 vs 71.50). LLM-judged addition was mixed and
  depended on the judge: the fine-tuned judge C3 beat the bank on 3 of 4
  agents (34.66 vs 16.75; 47.37 vs 40.11; 79.50 vs 71.50; not RegAgent, 67.35 vs
  67.53), C1 on 2 of 4, C2 on 1 of 4, and the ground-truth ("strict") policy on 4 of 4
  (70.95; 38.50; 51.00; 85.40). History-based deletion slightly improved three of four
  agents under strict addition. Errors in retrieved records propagate into new
  executions ("experience-following"). Baselines: fixed bank, add-all, coarse judges,
  an oracle; GPT-4o-mini main backbone; one of four agents synthetic; seed or repeat
  count not stated in the text read. Result is an effect of *unfiltered* writes on a
  bank that already works, not a statement that memory beats no memory.
- *Retention under noise.* TraceRetain (S02, abstract + extractor): on clean ALFWorld
  bounded retention policies were **not separable** within Wilson 95% intervals
  (gpt-5-mini, two seeds); a synthetic 75%-distractor write condition separated them
  (unbounded Precision@5 20.2% to 12.4%; FIFO-K50 15.8% to 3.8%; scorer 16.9% to
  16.6%). Noise is synthetic, one model.
- *Learned read/write policy.* Memex(RL) (S03, stated sections via extractor; v1 2026-03-04, the only version): RL-trained indexed
  memory raised success 24.22% to 85.61% and cut peak context 16,934 to 9,634 tokens
  on a modified ALFWorld, one model (Qwen3-30B-A3B), **compared only with itself
  before training**, no external baselines, no seeds, no write-versus-read
  ablation, cost and latency not reported. Weak evidence that "write summaries,
  read by index" is learnable; no evidence it beats a plain retrieval policy at
  matched budget.
- *Memory stale-trust.* Over-trust of stale memory (S10, S11) is covered under R3.
- *Typed versus unified.* No source found a controlled comparison of a typed store
  against a flat store with the retriever, backbone and token budget held fixed.
  Closest: PlugMem (S08, v1 2026-02-06, first 100k of 187,298 chars) uses episodic, semantic and
  procedural graphs; its "No Structuring" ablation fell from 75.1 to 62.8 accuracy on
  LongMemEval and from 61.4 to 51.4 EM on HotpotQA, but the extractor could not
  confirm what replaces structuring, baselines come from different LLM pairings and
  prior work, and the memory-token reduction (362.6 vs 3,742.5 tokens) mixes typing
  with an LLM condensing step. TOKI (S12) reports removing its "typed memory layer"
  costs 0.49 accuracy on 1,444 LoCoMo questions, but states that cross-system
  comparison is underpowered and its excerpt does not define the ablation. The
  anatomy study (S05, v1 2026-02-22 / v2 2026-05-20, first 100k of 120k chars) reports
  no controlled flat-versus-structured ablation, but measures that structured systems
  are format-fragile: Nemori format error 17.91% (gpt-4o-mini) and 30.38%
  (Qwen-2.5-3B) against 1.20% and 4.82% for SimpleMem (which I, not the paper, describe
  as flat/append-only; the paper's taxonomy places it under lightweight semantic
  memory), and Nemori's answer score fell from 0.781 to 0.447 on the small backbone
  while SimpleMem's fell from 0.289 to 0.102. The independent system characterization
  (S04, v1 2026-06-04 / v2 2026-09-22) ran nine systems on one benchmark (table below).
  Accuracies of the top four (BM25 47.0, GraphRAG 46.0, HippoRAG v2 44.3, A-Mem 42.7)
  **are not separable**: one run, five histories, n=300 queries, no seeds or intervals
  stated; a binomial interval at 47% and n=300 is about +-5.6 points before accounting
  for the clustering by only five histories. What is separable is cost: BM25 matched
  the leading accuracies at about 1/40 of A-Mem's wall time (16.3 min vs 11.76 h) and
  about 1/25 of its energy; the agentic/consolidating systems lower down (Letta, MIRIX,
  Mem0, SimpleMem) scored below the top four and ran slower, though not all of them are
  separable from each other (SimpleMem 36.0 against A-Mem 42.7, for example). Adapted, non-budget-matched native
  settings.

**Weaknesses and flags.** Apart from S01 (v1 2025-05-21, revised 2025-10-10) and
S06, the memory results here are 2026 preprints; most are single backbone, few or no
seeds, many LLM-judged. Benchmarks are conversational QA
or ALFWorld, not partially observable action games. S01's strict policy needs a
ground-truth oracle that play does not have; its lesson is *what a good write gate
must approximate*, not that one exists.

**Memory-product comparison (optional; evidence is thin).** Only one independent
source measured several products (S04, its Table 3, all nine systems printed). One
benchmark (LongMemEval), one local model (Qwen3-32B), n=300 queries over five
histories, one run, products adapted, not budget-matched; vendor-reported numbers were
not used. Differences of a few points among the first four rows are within noise.

| System (paradigm per S04) | Acc. (%) | Wall | LLM calls | Energy (kJ) |
| --- | --- | --- | --- | --- |
| BM25 (flat RAG) | 47.0 | 16.3 min | 300 | 582 |
| GraphRAG (append-only structure) | 46.0 | 1.83 h | 3,215 | 2,082 |
| HippoRAG v2 (append-only structure) | 44.3 | 44.2 min | 2,743 | 1,339 |
| A-Mem (agentic) | 42.7 | 11.76 h | 19,230 | 14,864 |
| embedRAG (flat RAG) | 39.8 | 14.4 min | 610 | 495 |
| SimpleMem (consolidating) | 36.0 | 3.92 h | 4,447 | 5,481 |
| Mem0 (consolidating) | 32.0 | 4.02 h | 4,538 | 4,878 |
| Letta (agentic) | 27.7 | 14.36 h | 18,394 | 15,429 |
| MIRIX (agentic) | 20.0 | 6.03 h | 7,655 | 8,678 |

Source: S04 Table 3 (a tenth system, long-context passthrough, is not in this table).
Paradigm labels follow S04's grouping as extracted. No cross-product ranking beyond
"expensive consolidators were not better here" is justified.

**Recommendation for ADR 009 (R1).**
1. Keep the gate as the write policy and make it **evidence-checked**. S01 shows
   that unfiltered writes (add-all) degraded a pre-populated, already-working bank on
   all four agents, that errors compound, and that judge-filtered writes were mixed
   (a strict LLM judge beat the bank on 3 of 4 agents, a looser one on 1 to 2), while
   an oracle-checked policy beat it on all four. It does *not* show that memory beats
   an empty store, nor that self-judging is useless. The gate's re-observation checks
   are the available analogue of S01's oracle; test in P0 whether they approximate it.
2. Keep every episode retrievable and add a **history-based demotion** (low realized
   utility after repeated retrieval) as a candidate grooming signal; S01 supports it
   modestly (four tasks).
3. Do **not** claim typed schemas help. Treat the ontology as a hypothesis with a
   mandatory flat/lexical arm in every P1 comparison (BM25-class retrieval over raw
   episodes plus epistemic-core fields), at matched calls and tokens, where the
   report states the budget beside the outcome whenever it cannot be matched. S04
   supports BM25-class retrieval as a **cheap baseline that heavier designs must beat**
   (it matched the leading accuracies at about 1/40 of the wall time), not as evidence
   it is best. The only
   defensible argument for typing is the epistemic core's explicit supersession and
   provenance fields (R3), not domain types.
4. Budget for **format-failure** in curator-written structure on the model actually
   used (S05), and count it as a gate-reject cause.
5. Weakness: no source tests memory under partial observability in an action game.

## R2 Concurrent or background consolidation

**What was measured.**
- *Staleness and lag.* The system characterization (S04) defines staleness as the
  number of prior sessions not yet persisted at query time. Under asynchronous
  construction, consolidating and agentic systems (SimpleMem, MIRIX, Letta, Mem0,
  A-Mem) accumulate staleness; BM25 and dense RAG stay fresh. Per-session write
  latency spans about five orders of magnitude (sub-millisecond to tens of seconds;
  about 10 s for Mem0 and MIRIX, tails over 100 s). Synchronous writes remove staleness
  but add the construction time to the timeline. Measured accuracy was lower for the
  heavy consolidators on this benchmark (see the R1 table; v1 2026-06-04, v2
  2026-09-22). Caveats: single node and GPU, adapted systems, one run, no seeds or
  intervals; MemoryArena physics split (20 tasks) used for freshness.
- *Cost of consolidation.* The anatomy study (S05, six memory systems plus LoCoMo
  and full-context rows): offline build time 0.60 h (MemSkill) to 15.00 h (A-Mem), 1,308k
  to 7,044k construction tokens; per-turn read latency 0.306 s to 32.372 s, the
  slowest being MemoryOS (31.2 s of it retrieval). (An earlier draft of this page
  mislabelled generation latency and build time; corrected from Table 5.) Run counts and variance not stated.
- *Background design with a lag claim.* EngramRAG (S13, extractor): a six-hourly
  "dreaming" cycle off the read path; on a simulated 90-day deployment it kept 100%
  of scaffolding facts versus 60% for standard decay. Single evaluations, ten
  dialogues, simulated or synthetic mutation episodes, **no compute matching**, its
  7B reader showed no clear gain on LoCoMo token F1 (17.29 vs dense 18.34). Not
  evidence that background consolidation helps real tasks.
- *Offline compute.* Sleep-time compute (S06, abstract only, v1 2025-04-17,
  **RECENCY**): precomputing about a context before the query reduced test-time
  compute for equal accuracy by about 5x on stateful math benchmarks and gains
  correlate with query predictability. Synthetic stateful variants, no live acting
  agent, and the baseline was not visible beyond the abstract. "Do Language Models Need
  Sleep?" (S07, abstract only) moves compute into fast weights during a pause;
  synthetic and math tasks; parametric, not applicable to a frozen-model player.
- *Parametric consolidation.* S14 (extractor): writes only 2.4 to 2.6 events per 200
  into an adapter and beats RAG on a goal metric but loses on short facts; synthetic
  protocol, four seeds; no latency or staleness measured; stale-memory deletion
  stated as unsolved.
- *Consistency.* TOKI (S12) treats contradiction resolution as write-time concurrency
  control with isolation requirements and an audit row preserving losing facts. It is
  a single-process, theory-led design whose cross-system comparison is stated to be
  underpowered. No study measured agent-curator concurrency consistency in a closed
  loop.

**Recommendation for ADR 009 (R2).**
1. The ADR's design (immutable versioned snapshots, labelled "as of decision N",
   actor never blocked) matches what S04 says is necessary when per-session
   consolidation time can exceed arrival intervals. Keep it, and **adopt S04's
   staleness definition** (sessions or boundaries not yet reflected in the published
   snapshot) as the lag metric in P0 curator shadow sessions, reporting the
   distribution of curator write time and its tail, not the mean.
2. Because the ADR makes the next admission wait for a covering snapshot, the cost of
   a slow curator falls on wall-clock only at boundaries; the staleness metric tells
   whether in-admission snapshots lag far enough to matter. Measure before adding
   machinery.
3. Preserve the loser: keep superseded assertions (S12's audit-row idea, already in
   the ADR's "what it supersedes") rather than overwriting.
4. Weakest area: no measured effect of consolidation on acting-agent task outcomes at
   matched cost exists in the sources read; treat P0's shadow-session lag/cost study
   as the first real evidence.

## R3 Belief under conflicting observations (ADR open decision 4)

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
- *Contradiction operators* (S12): see R2; four write-time operators (LWW,
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
  This is neural multimodal classification, not agent memory; it supports only the
  design caution that a fusion operator's independence assumption and conflict behavior
  must be tested, not assumed. The Beta/Dirichlet equivalence of opinions was
  *not verified from a readable primary text* (S25 states evidence e = alpha - 1,
  belief = e/S, uncertainty = K/S for the Dirichlet case, which is the multinomial form;
  the binomial/Beta statement and base-rate weight W are unverified). Dezert and
  Tchamova's critique and Jøsang 2013 are **unread**. I found no source that applies
  subjective logic to LLM agent memory (prior page: BeliefMem uses noisy-OR merging).
- *Dempster-Shafer.* I could not read Zadeh's 1979 memorandum (scanned PDF). S25
  supplies a neural-network example of the same pathology (above). Snippets only, no
  conclusion: the controversy is whether the conflict-normalizing rule is flawed or the
  example's modelling is (Haenni). No source read supports choosing Dempster's rule.
- *Source reliability without ground truth (Dawid-Skene family), staleness as survival
  analysis, hierarchical pooling, calibration.* No primary text was read for any of
  these: Dawid-Skene and Kaplan-Meier were not retrieved; Gelman not retrieved; a
  2024 workshop paper extending Dawid-Skene to LLM annotators appeared only as a snippet. No
  LLM-agent paper in this sweep estimates per-type staleness rates by survival
  analysis, and S09 explicitly leaves decay unexercised. **These sub-questions remain
  unanswered by evidence in this page.** The project's own synthetic Brier numbers
  (pooled .223 vs scoped .340, scoped better on return) are internal development
  data, not external evidence.

**Recommendation on open decision 4 (belief model).**
1. **Do not adopt subjective-logic fusion as a decided model.** No source read compares
   subjective logic with Beta counts, last-write-wins or Dempster's rule on agent
   memory, and the only primary operator text (S16) and the one empirical user found by
   query 15 (S25, neural classifiers) are older than the 18-month line or off-domain. I cannot
   verify from a readable primary text that a binomial opinion reduces to a Beta
   distribution (S25 gives the Dirichlet form only); treat any equivalence as a
   hypothesis to check when the model is specified.
2. **Adopt a staged model.** *Stage 0 (default, a design default and not an
   evidence-backed choice):* explicit supersession with provenance (the epistemic core
   already has it), plus stored positive and negative re-observation counts and
   timestamps per assertion; aging as a monotone reduction in evidence weight, with an
   aging-off ablation and a tuned rate in the offline test (no source supports a
   particular decay form; S09 never exercised its decay on real data).
   *Stage 1 (candidate, test offline; **RECENCY**: it rests only on S16, a 2007 working
   paper, and the 2024-25 S25):* evidence-count opinions with a fusion rule chosen by
   dependence: observations from the same source frames or the same asserter count once
   (averaging/idempotent behavior), distinct re-observations at distinct times may add
   (cumulative). S25 warns that cumulative fusion lowers uncertainty even under
   conflict, so the offline test must include conflict cases. *Alternatives held for the
   offline test:* (A) LWW with supersession (S09 shows it is hard to beat on real
   conversational data and under constant reliability), (B) Beta counts with learned
   reliability (S09's design), (C) subjective logic opinions, (D) Dempster-Shafer (not
   recommended for the first test: no supporting source read; S25 shows the full-
   confidence-under-conflict pathology), (E) write-time adjudication labels
   KEEP/STALE/REPLACE/UNKNOWN (S10's CUPMem, the authors' own fix on their own benchmark).
3. **Resolve conflict at the gate, but keep disputes visible.** S10 and S11 both found
   models fail to apply updates even when they detect them, and S11's oracle that
   removes the stale item restored accuracy to 0.95 to 1.00. That shows only that
   **correct** resolution helps; no source measured the cost of a wrong resolution, and
   S09's provenance cap cost accuracy (100% to 54%) on legitimate corrections. So the
   actor receives a resolved, labelled value with provenance, and an assertion the gate
   cannot resolve keeps a visible disputed/UNKNOWN label rather than being silently
   resolved. S11 also found metadata exposure helped even the 0.6B model (+0.30), so
   labels are not useless at small scale. Keep "current screen overrides" as the ADR
   states.
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
   - *Arms.* A, B, C-with-averaging, C-with-cumulative, E, Stage 0 alone, and a flat
     raw-episode retrieval arm. **Hold one extracted assertion set fixed across arms**, so
     differences are in the belief rule and not in LLM extraction. Arms without a native
     probability (A, E, D and Stage 0) get a pre-registered mapping to a probability
     stated before running; for Stage 0, for example, a Beta posterior mean under a
     pre-registered prior. Otherwise they are scored on accuracy only and excluded from
     the Brier and ECE comparison.
   - *Budget.* Calls and tokens **cannot be matched** (B's reliability and E's
     adjudication make LLM calls per write); report calls, tokens and wall time beside
     each outcome and state that the comparison is not budget-matched.
   - *Outcomes.* Accuracy of the predicted current value at later re-observation;
     where a probability exists, Brier or log score with a reliability diagram and ECE
     with intervals; retrieval-miss rate; a double-counting stress (replay one
     observation n times; the score must not rise); legitimate-correction cost
     (S09's 100% to 54%); and **wrong-resolution cost** (inject wrong resolutions and
     measure actor error), which no source measured.
   - *Statistics.* The independent unit is the lineage, and every variant tried is
     reported. The holdout is #382's three day-scale lineages (ADR 009, Evaluation).
     - **Trace lane.** With n=3 clusters a cluster bootstrap has only 10 distinct
       resamples, so its bound means nothing. Report the trace lane per lineage,
       descriptively, and do not gate on an interval there.
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
6. Weakest-evidence area overall: decay/staleness estimation, pooling and
   calibration have no primary support in this page.

## R4 Ontology/schema induction and evaluation

**What was measured.**
- *SCION/SCOPE* (S17, v1 2026-05-20, stated sections via extractor, first 100k of 182,621 chars; claims about the remaining appendices are not made): LLM "schema engineer" names,
  merges and filters mined candidates, never authoring items freely; strict JSON
  contract with evidence pointers; deterministic validation and fallback. 24 text
  sources. Evaluation is by schema-graph F1 (literal, fuzzy, continuous, graph) against
  released schemas, plus downstream fixed-extractor instance F1: released schemas
  0.5633, matched extract-then-aggregate 0.6523, SCION-lite 0.6800, with fusion
  0.6900. One run per source in main tables (variance in an appendix not read),
  contamination of public IE sources not excluded, no schema-metric to downstream
  correlation visible in the part read.
- *Generative Ontology Induction* (S18, extractor): coverage score is the fraction of
  ontology nodes appearing in generated documents (presence only), a generic
  three-field template as baseline, one generation per system, no judge, **no
  downstream task**; a proxy only. v1 2026-05-01 (the abs page date; the identifier
  month disagrees).
- *GrOIL* (S19, extractor): embedding clustering for deduplication then bounded
  LLM naming, provenance on every term, deterministic compilation. Evaluated by
  competency-question coverage (SPARQL and RAG) against direct and multi-agent LLM
  baselines (SPARQL coverage 0.8527 vs 0.6304 on one set; RAG results mixed, trailing
  the multi-agent baseline on one set), five LLM judges whose agreement was low for
  redundancy (alpha 0.57); one insurance domain, synthetic 100-contract corpus; LLMs
  generate and judge the questions; no run variance.
- *Agreement and entity resolution.* Search snippets only (support nothing): a 2026
  paper reports Krippendorff's alpha as a robustness check on LLM-versus-human
  annotation, a codebook-ambiguity workshop paper, and two LLM entity-resolution papers
  treat it as clustering. No source read connected agreement, MDL, or Fellegi-Sunter
  style identity scoring to downstream utility. No source on MDL for induced
  schemas was found. No source studied merge/split decisions of induced types as
  their own task, nor induction inside an agent memory loop.

**Recommendation for ADR 009 (R4).**
1. Keep **task utility as the primary criterion**, computed by the gate on trace that
   arrived after the submission (as the ADR specifies). The two sources that tie
   schema quality to something downstream (S17 fixed-extractor F1, S19 CQ coverage) do
   so by task outcome; presence- or label-similarity metrics alone (S18, schema-graph F1)
   are proxies.
2. The accepted mechanism pattern in S17 and S19 (LLM only names and chooses among
   mined or retrieved candidates, with evidence pointers and deterministic validation)
   supports the ADR's "nearest types, explicit reuse/specialize/create" gate. Treat
   embedding-based nearest-type suggestion as a candidate and test its threshold on
   development lineages only.
3. Do **not** use an LLM judge for redundancy or merge quality: S19's judges disagreed
   most there. Use the gate's measured retrieval-miss and duplicate/wrong-merge rates.
4. Compression (MDL), Krippendorff's alpha and Fellegi-Sunter-style identity scores
   remain secondary diagnostics with **no evidence they predict utility**. P0 should
   record them alongside utility and report their correlation on the lineage set before
   any is allowed to gate an edit.
5. Weakest area: no measured evidence on utility versus complexity or on grooming
   (merge/split) for LLM-induced types in agent memory.

## R14 Oversight interfaces

**What was measured.**
- *Oversight strategy experiment* (S20; **v1 2026-04-06 / v2 2026-09-12, results
  revised**; v2 stated sections via extractor, first 100k of 201,935 chars; v1 figures
  below are superseded and kept only as a record): N=48, 192 live sessions,
  within-subjects, four bundled strategies, one agent (Gemini 3.1 Flash-Lite), six
  web tasks with planted risks.
  *v2 results.* Plan-based strategies had lower odds of encountering a problematic
  action (OR 0.24, 95% CI [0.14, 0.42], p<.001; occurrence: Action Confirmation 83.3%,
  Risk-Gated 87.5%, Supervisory Co-Execution 56.2%, Structurally Enriched 60.4%).
  **Conditional intervention success did not differ reliably by strategy** (chi2(3)=3.17,
  p=.366; 22.5%, 26.2%, 7.4%, 24.1%; 29 of 138 problematic actions that reached
  execution, 21%, were stopped). **Final (uncorrected) attack success did differ**
  (joint Wald chi2(3)=10.02, p=.018): Action Confirmation 64.6%, Risk-Gated 64.6%,
  Supervisory Co-Execution 52.1%, Structurally Enriched 45.8% (lowest). Higher- versus
  lower-consequence tasks: intervention 13.3% vs 30.2% (p=.012), failure 67.7% vs 45.8%,
  confounded with scenario and risk type. *v1 (superseded):* OR 0.25 [0.13, 0.49];
  intervention success p=.407; final attack success p=.162 (not significant); 12.8% vs
  29.4%. The revision changes the R14 conclusion: strategy did change final failure,
  though not conditional intervention.
  *What Structurally Enriched is* (v2): plan inspection and revision before execution;
  non-blocking display during execution of the agent's current focus, rationale,
  execution trace and localized risk labels; approval prompts only for flagged risks
  (with an "Approve Similar" shortcut shared with Risk-Gated); pausing reopens full
  plan inspection. It bundles these mechanisms (not factorial), and the authors state
  that plan-based protection partly comes from the approved plan being injected into the
  agent's own prompt, i.e. it changes the agent, not only human vigilance; the model was
  chosen partly because it produced problematic actions reliably; two participants per
  ordering. Qualitative: people needed cues that mark a moment as needing judgment,
  clear delegation boundaries, and *enough* context to judge a step; rationalization of
  risky actions was common; the abstract says intervention often came too early or too
  late and users judged correctness of the action rather than safety. Limits: scenario
  confounded with risk type; intervention observable only when a problem surfaced;
  short sessions; one platform.
- *Observing and steering interface* (S21; the figures below are from the v1 text
  (2026-07-28); **v2 2026-08-04 and v3 2026-10-23 exist and were not re-read**, so the
  numbers may have been revised): N=8 students, within-participant,
  new GUI against a baseline dashboard, questions about trajectories: about 90 s vs 145 s
  per question and 93% vs 80% accuracy (one low baseline score may inflate), lower
  workload. This measures **comprehension of traces**, not timely intervention; tiny,
  homogeneous sample; the automated "manager" steering result (N=50 runs per model, small
  local models) is a separate, quantitative-completion-only study.
- *Developer oversight practice* (S22, extractor, first 100k chars): 17 developers
  interviewed; real-time monitoring was rare, stated reasoning often diverged from
  action, post hoc review relied on heuristics that fail ("the plan is a faithful
  proxy", "passing tests means correct"). Exploratory, mostly one employer, small tasks.
- *Reviewer capacity* (S23, abstract only): modeling plus 125 hand-labelled actions with
  Fleiss' kappa 0.52; fatigue-driven inverted-U between escalation load and safety is
  a modeling result "motivating a human study", not measured on humans.
- *Detection timing* (S24, extractor): 9,429 synthetic model-generated code-agent
  trajectories; an LLM monitor reached early-intervention 0.89 vs 0.23 for regex rules
  (random about 0.24); cascading cheap-to-LLM reduced monitor cost about 74%.
  Synthetic, labels by the authors, code agents only; automated, not human oversight.
- Snippet-only leads (no conclusions): a CHI 2026 workshop dashboard for multi-agent
  research oversight evaluated reflectively by its authors, a military test
  framework stressing time-to-act, and a policy consensus listing oversight modes.
- Foundational: Sheridan and Endsley were not read.

**Recommendation for ADR 009 (R14).**
1. The Spectator's **intent, expectation and outcome side-by-side** view is supported
   by S22 (reasoning/plans are unreliable proxies for action) and S20 (judgment cues
   matter); keep outcomes, not just narration.
2. Prefer **triage over streams**: flagged moments with the reason and a short, linked
   context (S20), and a capped alert rate (S23's modeled saturation, unconfirmed). The
   S20 v2 evidence is mixed: strategy changed exposure and final failure (the bundled
   plan-plus-visibility-plus-risk-label strategy was lowest, 45.8%), but not conditional
   intervention success (p=.366). Because the bundle is not factorial and part of its
   protection came from changing the agent's own prompt, **no Spectator feature can be
   credited**; the Spectator is read-only and cannot change the agent's prompt, so the
   plan-injection route does not transfer. What may transfer is the risk-label and
   "needs your decision" cue; test it as one factor, not as the bundle.
3. Evaluate the Spectator on **detection tests**: injected faults or sealed incident
   replays with time-to-detect and miss rate, not on viewer comprehension or
   satisfaction alone (S21 measured only comprehension).
4. Because the viewer is read-only and the Pause path independent (ADR), the controls
   evidence (S20's approval and plan editing, S21's steering) is largely out of scope; the open question is whether
   operators of a four-role system notice failures in time. **No source studies
   supervision of multi-role or game-playing agents.**
5. Weakest area: small samples (N=8, N=17), planted-risk web tasks, no long-duration
   supervision data.

## Weakest-evidence summary

| Area | Strength | Why |
| --- | --- | --- |
| R3 decay, pooling, calibration, reliability without ground truth | Very thin | No primary text read for the foundations; no LLM-agent source estimates staleness rates; one benchmark with built-in reliability signal |
| R4 utility versus complexity, grooming | Very thin | Induction papers measure proxies; no merge/split utility study; no MDL source |
| R14 multi-role supervision | Thin | N=8 to 48 web/coding tasks; no game or multi-role agents |
| R2 acting-agent outcomes under consolidation | Thin | Lag measured for QA ingestion, outcomes unmatched |
| R1 typed vs unified | Thin | No matched-budget flat-versus-typed ablation found |
| R1 write-gate evidence | Moderate (small) | One controlled study, four tasks, includes a synthetic agent |

General: nearly all LLM evidence is 2026 preprints, single backbone, often LLM-judged
and often author-built benchmarks; none involves a CDDA-class partially observable
game. Sources outside the 18-month window (before 2025-05-08): sleep-time compute
(S06), the 2007 Jøsang page (S16) and the 2025-03 belief-fusion paper (S25); S01
(v1 2025-05-21) is inside it. Conclusions resting only on them are flagged RECENCY.

## Sources

All retrieved 2026-11-08. Dates are the arXiv abs-page submission history. "Extractor" =
text retrieved through the fetch tool and queried for stated sections (see Read-scope
honesty); "first 100k of N" means the remainder was not read and no claim rests on it.
"Budget matched" = whether compute, calls or tokens were matched across compared arms.

| ID | Source | Date (v1 / revised) | Read scope | Measured / baseline / budget matched / flags |
| --- | --- | --- | --- | --- |
| S01 | How Memory Management Impacts LLM Agents (experience-following), arXiv 2505.16067 | v1 2025-05-21 / v2 2025-10-10 | Stated sections via extractor, first 100k of 102,435 chars (Table 1, deletion, errors) | Four agents (one synthetic), GPT-4o-mini; fixed pre-populated bank, add-all, judges C1-C3, oracle; budget not matched; repeats not stated in text read |
| S02 | Selective Memory Retention (TraceRetain), arXiv 2606.29178 | v1 2026-06-28 | Abstract + extractor summary | ALFWorld, gpt-5-mini, 2 seeds; synthetic noise; bounded policies unseparable on clean data |
| S03 | Memex(RL), arXiv 2603.04257 | v1 2026-03-04 (only version) | Stated sections via extractor (HTML) | Modified ALFWorld, Qwen3-30B-A3B; only before/after own training; no seeds, ablation, cost; **single-environment, unreplicated** |
| S04 | Agent Memory: Characterization and System Implications, arXiv 2606.06448 | v1 2026-06-04 / v2 2026-09-22 | Stated sections via extractor; staleness and cost text from v1, **Table 3 re-read in v2** (nine systems); v2 text for the staleness section not re-read | 10 systems (9 in Table 3), LongMemEval n=300 over 5 histories, one run, no seeds/intervals; independent; not budget matched; single node |
| S05 | Anatomy of Agentic Memory, arXiv 2602.19320 | v1 2026-02-22 / v2 2026-05-20 | Stated sections via extractor: v1 first 100k of 119,242; Table 5 from v2 (first 100k of 120,387) | Six memory systems plus LoCoMo/full-context rows, two backbones, one judge; LoCoMo ranking only; run counts unreported |
| S06 | Sleep-time Compute, arXiv 2504.13171 | v1 2025-04-17 (only version) | Abstract only | Stateful math benchmarks; **RECENCY (older than 2025-05-08)**; baselines not visible |
| S07 | Do Language Models Need Sleep?, arXiv 2605.26099 | v1 2026-05-25 / v2 2026-05-27 / v3 2026-06-05 | Abstract only | Synthetic and math tasks; parametric |
| S08 | PlugMem, arXiv 2603.03296 | v1 2026-02-06 (only version; identifier month differs) | Stated sections via extractor, first 100k of 187,298 chars | LongMemEval, HotpotQA, WebArena; baselines from mixed LLM pairings and prior work; no stated seeds |
| S09 | When Does Belief-Based Agent Memory Help? (Nous), arXiv 2606.22030 | v1 2026-06-20 / v2 2026-07-16 (page byline 2026-08-24 is not a version date) | Stated sections via extractor (v2) | Single author; one backbone; three separate results (LoCoMo, belief-layer micro-benchmark, five-regime synthetic); not budget matched; no calibration |
| S10 | STALE, arXiv 2605.06527 | v1 2026-05-07 (only version) | Stated sections via extractor: first 100k of 186,845 chars plus text from 100k onward (appendices); middle not claimed | 400 LLM-generated expert-validated scenarios; authors' own benchmark and fix; LLM judge; page includes base64 prompt templates, treated as data |
| S11 | The Memory Trust Gap, arXiv 2609.01852 | v1 2026-09-01 (only version) | Stated sections via extractor | Synthetic frozen benchmark, small models; oracle pre-resolution arm; exploratory factorials; RGB/MisBench external check |
| S12 | TOKI, arXiv 2606.06240 | v1 2026-06-04 (only version) | Stated sections via extractor, first 100k of 269,356 chars | Operator algebra, LoCoMo; ablation definitions and data provenance in the unread appendix; cross-system comparison underpowered |
| S13 | EngramRAG, arXiv 2609.32049 | v1 2026-09-25 (only version) | Stated sections via extractor | LoCoMo plus simulated 90-day; no compute matching; single evaluations |
| S14 | Memory Depth, Not Memory Access, arXiv 2606.26806 | v1 2026-06-25 (only version) | Stated sections via extractor | Synthetic protocol, 4 seeds; no latency |
| S15 | Single and Multi Truth Data Fusion using LLMs, arXiv 2606.28062 | v1 2026-06-26 (only version) | Stated sections via extractor | Three tabular datasets vs classical truth discovery; single runs; model variance |
| S16 | Jøsang, Cumulative and Averaging Fission of Beliefs, arXiv 0712.1182 | v1 2007-12-07 (only version) | Stated sections via ar5iv extractor | Definitions only; **RECENCY** |
| S17 | SCOPE and SCION, arXiv 2607.21610 | v1 2026-05-20 (only version; identifier month differs) | Stated sections via extractor, first 100k of 182,621 chars | 24 sources, one run per source in main tables; contamination not excluded |
| S18 | Generative Ontology Induction, arXiv 2607.16201 | v1 2026-05-01 (only version; identifier month differs) | Stated sections via extractor | Presence-only metric; generic-template baseline; single generation |
| S19 | GrOIL, arXiv 2608.22135 | v1 2026-08-22 (only version) | Stated sections via extractor | One domain, synthetic corpus, LLM-generated and LLM-judged questions |
| S20 | Comparing Human Oversight Strategies for Computer-Use Agents, arXiv 2604.04918 | v1 2026-04-06 / v2 2026-09-12 (**results revised**) | v2 stated sections via extractor, first 100k of 201,935 chars (Section 6.5 and Appendix I.3 unread); v1 numbers from an earlier read, superseded | N=48, 192 sessions, one agent; strategies are bundles, not factorial |
| S21 | AgentGUI, arXiv 2607.26300 | v1 2026-07-28 / v2 2026-08-04 / v3 2026-10-23; accepted to EMNLP 2026 System Demonstrations | v1 text via extractor; **v2 and v3 not re-read** | N=8 comprehension study; steering experiment N=50 runs per model |
| S22 | Human oversight of agentic systems in practice, arXiv 2606.05391 | v1 2026-06-03 (only version; interviews 2025-07 to 08) | Stated sections via extractor, first 100k of 157,810 chars | 17 interviews; qualitative |
| S23 | Oversight Has a Capacity, arXiv 2606.08919 | v1 2026-06-08 | Abstract only | Modeling; kappa 0.52 on 125 labelled actions |
| S24 | StepShield, arXiv 2601.22136 | v1 2026-01-29 / v2 2026-07-07 | Stated sections via extractor (v2) | Synthetic trajectories; automated monitors |
| S25 | Multimodal Learning with Uncertainty Quantification based on Discounted Belief Fusion, arXiv 2412.18024 | v1 2024-12-23 / v2 2025-03-28; AISTATS 2025 (PMLR 258), peer-reviewed; **RECENCY** | Stated sections via extractor | Five small datasets, 10 seeds per experiment; neural classifiers; hyperparameters tuned on one baseline |
| X1 | Memory for Autonomous LLM Agents (survey), arXiv 2603.07670 | v1 2026-03-08 | **PDF unreadable; not read** | Leads only |
| X2 | Search-snippet leads: Mem-T, AdaMem, AutoSchemaKG, 2609.22133, quallmer, CLARIFY, 2506.02509, 2401.03426, Yao et al. 2024, Haenni, Dezert-Tchamova, CHI 2026 dashboard, 2608.20597, Singapore Consensus, Letta/vendor blogs, Jøsang-Pope 2012, 1805.01388 | various | Snippet only (1805.01388 PDF unreadable) | **Support no conclusion**; vendor items excluded |
| X3 | Unreadable or unretrieved named foundations: Jøsang 2013 (HTTP 403 from the redirect target), Zadeh 1979 memo (scan), Jøsang 2009 slides, Dezert-Tchamova, evidence-based SL flow paper, Dawid-Skene, Kaplan-Meier, Gelman, Rissanen, Krippendorff, Fellegi-Sunter, Sheridan, Endsley, McClelland, Soar/ACT-R, Tulving | various | **Not read** | No conclusion rests on them |

Earlier-page sources relied on by reference only (not re-reviewed): AgeMem, MemRL, ACE,
Useful Memories Become Faulty, BeliefMem and the other sources listed in the two
earlier pages above, with their stated dates.

Revision record. A first draft of this page was reviewed independently. This revision
corrected: S20 (v2 results replaced v1 and the R14 recommendation changed); S04 (nine
systems printed, noise statement, "BM25 best" withdrawn); S01 ("fixed" is a populated
bank, judge-filtered results mixed); S09 (three results separated; adversarial regime
reported); S11 (pre-resolution is an oracle; metadata helped at 0.6B); S05 (build time
and latency misreadings); read-scope tags; version dates; the unverified
subjective-logic/Beta equivalence (now flagged unverified); and the offline-test
design. Remaining reviewer checks: spot-check all quoted numbers against the papers
(extractor risk); S21 v2 and v3 and the unread parts of S10, S12, S17 and S20 were not
read.
