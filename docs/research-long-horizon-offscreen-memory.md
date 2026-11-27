---
owner: lead
status: active
date: 2026-11-26
scope: 'Outside evidence from 29 works beyond short-horizon game agents on stale memory precedence, evolving off-screen state, environmental tracking, active sensing, multi-session error carry-forward, scientific discovery and human-factors failure modes'
review_trigger: 'The owner settles findability, post-cut delivery and curation cadence, or a study tests keyed inertial state, kinematic anchors, grounded when/precedence, player_agenda or interleaved hygiene grooming in extended play'
---

# Research on long-horizon off-screen state, environmental tracking and non-gaming memory analogues

The search cutoff was **26 November 2026** (America/New_York). This page is a
companion to [what a player's memory should hold and who writes it](research-memory-statement-kinds.md).
That page drew mainly on short-horizon agent-memory benchmarks and brief game
trials. In extended, persistent, partially observable worlds such as CDDA,
Civilization, RimWorld or Minecraft, relevant state exceeds both active context
and what is visible on screen, so play resembles running a multi-week software
project, a laboratory programme or a warehouse operation as much as solving
isolated benchmark episodes.

The question arose during the [three-day campaign memory review (#1019)](https://github.com/CVX-Hull/enactive/issues/1019)
to inform memory design across `#1020`–`#1027`. Approved policy covers curator
scope ([Kinds 1–5 only](decisions/owner-decisions.md#curator-records-statement-kinds-one-to-five),
[strategist deferred](decisions/owner-decisions.md#separate-strategist-deferred-1024)),
[player working state](decisions/owner-decisions.md#player-working-state-agenda-1026),
[keyed inertial world state](decisions/owner-decisions.md#keyed-inertial-world-state-and-live-repair-1020),
[zero-model lookup](decisions/owner-decisions.md#zero-model-lexical-index-embeddings-deferred-1020),
[kinematic anchors and frame clock](decisions/owner-decisions.md#kinematic-anchors-frame-clock-and-on-demand-depictions-1021),
[statement kinds, grounded `when` and precedence](decisions/owner-decisions.md#statement-kinds-grounded-when-two-strength-deps-and-precedence-1022)
and [interleaved hygiene-only live grooming](decisions/owner-decisions.md#interleaved-hygiene-only-live-grooming-1027).
Empirical and design questions on record findability, post-cut delivery, live
curation cadence and extended-play grounding and precedence stay active here;
issue status lives on the [Project](https://github.com/users/CVX-Hull/projects/2).
Related research covers [memory statement kinds](research-memory-statement-kinds.md),
[memory, ontology and oversight](research-curated-memory.md) and
[belief under conflict](research-belief-under-conflict.md).

## At a glance

- **Stale external instructions usually prevailed over live code in tested conflicts.**
  In a controlled coding-agent test, agents followed stale instruction files in
  90.1% of choices over live code (4.2%); one model named the conflict in 79 of
  80 runs and still followed the stale file on 86.2% of choices in those runs
  (L01). One combined precedence-and-reporting sentence raised code-following to
  91.4% (L01).
- **Extra context and complex curation often raised cost without separating from verbatim evidence.**
  LLM-generated repository context files increased mean inference cost by 20%
  and 23% while lowering task resolution in five of eight benchmark cells (L02).
  In a preregistered multi-session benchmark, verbatim event memory (45.6%) and
  a typed-plus-raw hybrid (46.1%) were one pass apart while the hybrid used
  roughly 79× the tokens and 12,655 judge calls; verbatim led on the earlier
  release's small staleness stratum (13/21 vs. 8/21) (L03).
- **Prior agent edits carried a large penalty in one multi-bug benchmark, while transcript carryover added little under tested policies.**
  Across 100 selected sequential bug chains, replacing prior gold fixes and gold
  test patches with prior agent edits cut mean per-bug accuracy from 58.9% to
  36.5%, whereas carrying conversation history across three tested policies
  reached 36.9% (+0.4 points) (L20). In a separate multi-step benchmark without
  a reference-prefix control, 57% of unqualified completion reports failed
  independent verification, compared with 65% of all steps (weighted estimate
  from a stratified sample of 2,157 reports) (L19).
- **No outside game-agent study here isolates screenshot-only off-screen tracking.**
  Both the Factorio (L13) and Civilization (L26) studies exposed typed structured
  engine queries rather than screenshots alone, and the proactive computer-use
  watcher (L17) is limited to visible-screen state, giving no signal that a
  remembered off-screen fact has changed.
- **Unchecked inventory ledgers drift, and human-factors reviews document aid bias and reported alarm burden.**
  Warehouse simulations show unverified ledgers lose 4.6%–45.8% of annual demand
  across accuracy classes; partial cycle counting reduces losses before
  restoring starting accuracy (L08). Human-factors reviews count automation bias
  in 25/31 omission and 21/23 commission studies (study counts, not pooled rates;
  only 9/40 tested significance against manual control) and document
  nurse-reported nuisance-alarm burden (L27, L28), while one preregistered
  experiment detected no significant allegiance-bias reduction from a partial
  competing-hypotheses procedure against an already-falsificationist control (L29).

## Brief and method

**Questions**

- What do non-gaming long-horizon domains—software maintenance, scientific
  research and lab notebooks, high-stakes operations, and formal active
  sensing—show about tracking evolving off-screen state?
- What belongs in built-in game or environmental tracking versus external curated
  memory versus active re-observation?
- Where do extra notes, dashboards, structured matrices, alarms or long-horizon
  planners measurably fail or harm performance?

**Search and shortlist.** Multi-wave problem-shaped web searches ran on
26 November 2026 across software engineering, scientific discovery, distributed
cognition, stigmergy, inventory control, active sensing, task interruption and
human-factors failure studies. Every candidate's primary URL, publication or
revision date and identifier were checked directly against primary metadata APIs
rather than search snippets; snippet-mismatched leads (such as an unrelated
arXiv preprint returned under an Age-of-Information query) were dropped before
shortlisting. Two independent explorer passes from different model families
critiqued framing blind spots and screened candidates for decision-changing
signal. After owner approval of the 29-work shortlist (`L01`–`L29`), full-text
reading began.

**Reading and reconciliation.** Primary full text was fetched for all 29 works:
**19 arXiv HTML exports**, **5 journal HTML articles** and **5 PDFs converted to
text** (`L08`, `L09`, `L10`, `L14`, `L21`). The works were divided into seven
thematic batches, and two independent reading reports from distinct model
families covered each batch (14 reading reports in total), testing claims
recorded before full-text reading against the extracted texts and logging
baselines, denominators, counter-results and unread material. Most extracts were
read completely by both readers, while some long appendices or reference lists
in `L13`, `L23` and `L24` were read in full by only one reader. A separate
reader (from a different model tier within the same model family as one of the
two batch readers) reconciled each batch against the extracted texts (seven
reconciled digests), and the lead spot-checked decisive figures directly in the
extracts before drafting. During the documentation-rot and distributed-cognition
batch, both readers caught that a fetched PubMed Central identifier
(`PMC3928254`) for `L07` resolved to an unrelated RNA-seq paper; the lead
verified the actual *PLoS Medicine* DOI (`10.1371/journal.pmed.1001603`),
fetched its text and ran a full two-family reading and reconciliation in the
human-factors batch. The explorer critiques, reading briefs and reports,
reconciled digests, claims list and method scripts are sealed as evidence
(23 delegated attempts); downloaded source texts are not committed or sealed.
[Evidence seal](../data/evidence/long-horizon-offscreen-memory-research.sha256) ·
[Attempts ledger](../data/evaluation/coding-agent-attempts.jsonl)

**Read limits**

- **Missing figures and flattened tables.** HTML and PDF text extraction dropped
  plotted curves and visual panels in nearly all 29 works, leaving only captions
  and prose-reported coordinates. Tables lost cell formatting or merged-row
  structure in several works, and `Table 1` contents were missing altogether in
  the extracts of `L07`, `L10` and `L25`.
- **Degraded equations, OCR and missing prompts.** Mathematical notation was
  partially garbled in `L08`, `L12`, `L15` and `L16`. Optical character
  recognition degraded diagrams, columns or glyphs in PDFs `L09`, `L14` and
  `L21` (`L08` and `L10` were also PDF conversions). Appendix prompt bodies were
  absent from the HTML extracts of `L02`, `L04` (Appendix F.1), `L18`, `L20`
  and `L23`, and `L26` omitted one rendered prompt example.
- **Partial second-reader coverage, drafts and external supplements.** In `L13`,
  `L23` and `L24`, one reader covered the full extract while the second skipped
  repetitive schema fields, paper/reference lists or selected appendix prompts
  and rubrics (detailed in the source rows below). The fetched copy of `L10` is
  an undated author draft manuscript. External linked supplements, code
  repositories, raw data or preregistration pages outside the fetched primary
  text were not read (notably `L03`, `L06`, `L11`, `L13`, `L27`, `L29`).
- **Scope and unfetched leads.** Only open-access primary texts were read;
  paywalled studies without an accessible full primary text were not imported as
  quantitative evidence. Strength ratings follow the reconciled digests and
  reflect each study's evidence for its tested claim, not transfer to
  screenshot-based gameplay.

## What the evidence says

### Stale instructions, context files and documentation rot

- **Stale instruction files usually prevailed over live code even when agents noticed the conflict.**
  Across 40 counterbalanced synthetic Python projects (320 fresh runs; 720
  convention choices per condition), Claude Code and Codex CLI followed stale
  instruction files in 90.1% (649/720) of choices versus 4.2% following live
  code (L01). Claude Code named the conflict in 79 of 80 baseline replies yet
  still followed the stale file on 86.2% of choices in those 79 runs; Codex CLI
  named it in 2 of 80 replies and rewrote existing working code in 20 of 80 runs,
  causing 17 of those 20 runs to fail restored tests (L01). Adding one
  user-level sentence telling the agent to follow existing code and report
  inconsistencies raised code-following to 91.4% (658/720, +87.2 percentage
  points, 95% CI 83.6–90.9), eliminated Codex CLI rewrites and raised test pass
  rates from 89.4% (143/160) to 100% (160/160) (L01). Every tested conflict
  made the document stale by construction, leaving intentional migrations
  untested and bundling precedence with reporting (L01).
- **Repository context files raised cost more consistently than they changed success.**
  Across 300 SWE-bench Lite tasks and 138 CTXbench tasks over four model–agent
  pairs (single completions per instance), LLM-generated `AGENTS.md` files
  lowered task resolution in five of eight cells (−0.5 and −2.0 percentage
  points mean, `p=.87` and `.37`) while raising mean cost by 20% and 23% (+2.45
  and +3.92 steps; CTXbench cost `p=.00064`) (L02). Developer-committed context
  files gave +2.4 percentage points on CTXbench over no file (`p=.21`) and beat
  generated files (`p=.038`), at up to 19% extra mean cost and +3.34 steps (L02).
  Traces showed extra exploration and testing—including one model searching for
  and rereading instructions already in context—and no experimental arm isolated
  a minimal non-standard rules file (L02).
- **Flagged stale code references appeared across repository histories, with unmeasured detector accuracy.**
  Scanning 991 top-starred and 2,277 Google GitHub repositories by checking
  whether documented code identifiers disappeared from source history flagged
  stale references in 28.9% (265/918) and 5.4% (101/1,879) of matched projects
  at inspection, with mean ages at inspection of 4.7 and 4.2 years, and 82.3%
  (658/800) and 29.7% (567/1,907) ever flagged in history (L06). Among
  already-fixed flags with positive timestamp differences, roughly 55% and 45%
  persisted longer than one month (L06). Detector precision and recall were
  unmeasured; outreach to 15 active Google projects drew four positive
  responses, four false-positive reports, seven nonresponses and five fixes out
  of 19 reported instances (L06).

### Verbatim evidence, state tracing, living reviews and event sourcing

- **Verbatim evidence and a much costlier curated hybrid were one pass apart on a preregistered audit.**
  In DreamBench-SWE's preregistered v2.1 audit (60 multi-session repository
  traps × 3 seeds = 180 scored cells per arm, Codex CLI/GPT-5.5 wake agent),
  pass rates were 11.67% (21/180) without memory, 45.56% (82/180) with verbatim
  event memory, 46.11% (83/180) with a typed-plus-raw hybrid and 53.89% (97/180)
  with pinned hosted literal storage; all three scored memory arms separated
  from no memory after Holm correction (`p≤.0013`) (L03). The hybrid arm
  consumed roughly 79× verbatim's tokens (174.205M vs. 2.209M) and 12,655 judge
  calls versus zero; both preregistered mechanism contrasts were unavailable
  after failing construct or pre-evaluation repair gates (recorded as `p=1`
  placeholders for multiplicity accounting), and hosted literal versus hybrid
  failed to separate (`p=.163` clustered, `.607` by trap majority) (L03). In
  original v2, overall hybrid (95/180) and verbatim (89/180) did not separate
  (`p=.518`, Holm `p=1`; none of six registered contrasts rejected), while
  descriptively verbatim led on the small staleness/supersession stratum
  (13/21 vs. 8/21) with higher useful-memory precision (0.556 vs. 0.264) and
  disabling contradiction repair raised typed-only passes from 80/180 to 88/180
  (L03).
- **Answer-time state tracing helped when the update was already in the transcript, with model-dependent transfer and propagation trade-offs.**
  On a 60-probe frozen slice of StateMemBench (single runs, same-family judge,
  anti-traps overrepresented), an answer-time structured state-tracing wrapper
  beat a transcript-matched generic control by 15.0–31.7 percentage points
  across all 12 backend–model cells (`p≤.04`), while question-blind summaries
  fell below retrieval alone (L04). On LongMemEval, the same wrapper gained
  11.7–25.0 points on Qwen-3.5-9B but shifted DeepSeek-V4-Flash by −5 to +5
  points (L04). Across all 322 probes, persistent StateMem scored 0.363 on
  DeepSeek and 0.233 on Qwen (level with GraphRAG at 0.224, `p=.82`), leaving
  49.1% and 64.3% residual drift; dependency propagation helped its target
  modes but over-propagated on long anti-traps (−12.5 points), so removing it
  left DeepSeek slightly higher overall (0.373 vs. 0.363, single run) (L04).
- **Event sourcing verified workflow replay without baselines or off-screen grounding.**
  ESAA validated agent JSON intentions into an append-only log and projected a
  materialized roadmap across two uncontrolled single-run software case studies
  (9 tasks / 49 events, and 86 events over ~15 hours) (L05). Despite the abstract
  calling both successes, the second case study was a partial snapshot with
  31/50 tasks done (62%), the prose contradicts itself on whether events are
  logged before or after file writes (§3.2 vs. §4.2), and replay verifies only
  recorded workflow events—not silent world mutation (L05).
- **Living systematic reviews separate surveillance checks from full conclusion revision.**
  Elliott et al.'s conceptual biomedical workflow distinguishes three
  qualitative publication tiers after continuous screening: updating only the
  last-search date when no new eligible evidence appears, modest editorial
  review when estimate changes are negligible and conclusions remain unchanged,
  and rapid full peer review when estimates or conclusions shift meaningfully
  (L07). The paper has no controlled outcome trial, no quantitative update
  thresholds and—in the available prose—no review-retirement rule, and warns
  that frequent reanalysis can inflate false positives (L07).

### Off-screen drift, cycle counting and active sensing

- **Unchecked inventory ledgers degrade; partial counting reduces losses before restoring accuracy class.**
  In a 360-day Stella distribution-center simulation across five WERC accuracy
  classes, zero physical cycle counting caused annual lost demand ranging from
  4.60% in Best-in-Class (BIC) to 45.80% in Major Opportunity (MO), with picking
  productivity falling to 54.30% in MO because false presence wasted trips while
  false absence hid usable stock (L08). Partial daily cycle counting lowered
  demand losses even before restoring starting accuracy—five counters cut lost
  demand from 45.80% to 29.00% in MO and 36.40% to 17.81% in Disadvantage (DIS),
  yet left both classes worse than their starting inaccuracy (+1.9× and +1.7×)
  (L08). Recovering or maintaining class required higher staffing: 10–14
  counters for MO→DIS, 15+ for MO→Typical, and 2+ to stabilize BIC/ADV (L08).
  Unpriced counting labor, unverified constants and internal table/prose
  discrepancies prevent transferring counter counts outside the model (L08).
- **Animal caching shows selective search without supplying a universal decay rule.**
  Reviewing controlled laboratory trials with Western scrub-jays, Clayton et al.
  document preferential search of sites associated with non-devalued food after
  same-day or one-week delays (with caches removed prior to probe trials),
  reduced caching of worms after two to four trials of experimenter-induced
  degradation at 4-hour/100-hour or two-day intervals, and experience-dependent
  re-caching when observed (though watched birds still placed ~20%–25% of caches
  in risky lit or exposed sites) (L14). Because degradation was manipulated across
  trials rather than varied continuously to locate a natural spoilage cutoff,
  the review supplies no natural expiration threshold and leaves memory-mediated
  reinforcement open as an alternative to prospective planning (L14).
- **Formal active sensing prices observations against tracking error, with strong model limits.**
  In a finite-state Markov / Gaussian-observation POMDP calibrated to one
  individual's biometric sensor signals, belief-dependent myopic sensing saved
  60% energy versus static equal allocation at matched accuracy (12-sample cap,
  4% detection error reported in the abstract; plot unrecoverable), while
  offline CE–WWLB saved 7% and exact dynamic programming became computationally
  intractable above two samples per slot (L15). Threshold optimality in
  Corollary 3 applies only to one-step costs under narrow two-state scalar
  symmetry (L15). A model-free Observation-Constrained MDP (OCMDP) decoupling
  observation and control policies reported 71% higher expected cumulative
  reward over model-free baselines and 50% lower observation cost versus
  fixed/continuous observation on Diagnostic Chain, and approximately 75% higher
  episodic return than PPO on HeartPole (plus ~80%/90% over always/never
  observing within OCMDP), but lacks seed counts, price sweeps, a joint-training
  decomposition ablation and consistent latent-state supervision equations (L16).
- **Proactive visual watching cuts wait time on visible screens without tracking off-screen state.**
  NightWatch pairs a frozen 0.8B pixel-gated 10 Hz visual watcher (which also
  periodically probes static loading screens and can receive action text) with a
  computer-use actor to wake after settling, interrupt stale inference or void
  misaligned pending actions (L17). Across 100 OSWorld-Verified tasks × 3 for
  two actors (MiMo-V2.6-Flash and Qwen3.8-27B FP8), NightWatch cut non-reasoning
  time by 33% (`p=.026`) and 41% (`p=.016`) and total loop time by 8% and 11%,
  cut screen-change proxies for premature/stale steps (9.6%→2.6% / 17.4%→8.3%
  and 11.4%→1.9% / 17.2%→11.8%), and nudged avg@3 success from 66.3%→68.0% and
  56.3%→58.7% at near-equal API cost (excluding local watcher GPU) (L17). On 49
  audio-free DynaCU web tasks × 3, MiMo rose 39.5%→44.2% while Qwen stayed flat
  at 34.7%→34.7%, and removing wake, interrupt or void dropped MiMo to 38.1%,
  30.6% or 36.1% (removing void raised target mismatch 3.6%→15.9%) (L17). Yet
  MiMo regressed on transient notifications (36.7%→33.3%), Impress (58.3%→54.2%)
  and OS tasks (70.8%→62.5%), on the 21 DynaCU tasks that both methods failed in
  every repeat 53 of 63 NightWatch runs hit the time limit, no online
  false-interrupt rate is reported, and the watcher is limited to visible-screen
  state (L17).

### Built-in world tracking, epistemic actions and long-horizon game scaffolds

- **Physical actions and environmental markers support verification when live cues sit beside them.**
  In real-time Tetris, Kirsh and Maglio logged information-seeking physical
  actions—most cleanly a trip to the wall and back to verify alignment before
  ~1% of drops, occurring at significantly greater board heights for ordinary
  versus wall-routine drops across intermediate (13.18 vs. 19.04), advanced
  (13.69 vs. 19.33) and expert (15.65 vs. 20.05) players (`α=.05`)—though causal
  cognitive-load reduction during play was not directly measured and the 100 ms
  physical vs. 800–1,200 ms mental comparison mixes gameplay best-cases with a
  three-player pilot (L09). In an MD-80 cockpit, Hutchins describes how posted
  speed cards and movable airspeed bugs set 25–30 minutes before landing turn
  recall into perceptual comparison against a live airspeed needle—working
  because a live reading sits next to the stored marker, with no quantitative
  error-rate trial (L10).
- **World artifacts coordinate encounter and uptake, with mixed outcomes across invention, resilience and density.**
  In SwarmWorld (one model, `gpt-5.6-luna`, four seeds per comparison—minimum
  two-sided sign-flip `p=0.125`—where every shared arm kept structured local
  state and private memory), noncreator adoption (defined to include first
  observation as well as causal reference, programming or repair) reached 99.3%
  under full culture and 96.9% under no explicit culture, with ~95% of first
  encounters via physical observation (L11). At 3,200 ticks, full culture led on
  uptake speed (median 5 vs. 8 ticks), breadth (13.53 vs. 7.49 noncreators),
  total artifacts (277.5 vs. 238.5) and portfolio resilience (0.2474 vs. 0.2365),
  while descriptively trailing no explicit culture on validated inventions
  (5.75 vs. 7.00); the best-of-100 isolated-search envelope produced the
  strongest single artifact (0.3488 vs. 0.2380), and both shared arms completed
  zero valid assays in a single-seed Protein Realms pilot (L11). In a hand-coded
  Mesa foraging grid, environmental traces alone reached 90.1% exploration
  coverage on the sparse baseline but tied neither mechanism on composite score
  (910.18 vs. 927.23, `p=.65`) and trailed random movement (random +22.7% over
  traces, `p<.01`); in dense large grids traces led a memory comparator on
  composite score (103.64 vs. 77.11 at 625 agents) while trailing on food
  (19.71 vs. 22.62), and prose/table mismatches plus a 10× arithmetic error in
  Equation 34 (`0.20/0.0875 ≈ 0.23` printed instead of `2.286`) make its
  crossover threshold unreliable (L12).
- **Long-horizon strategy and factory benchmarks still struggle even with exact structured engine queries.**
  In Factorio Learning Environment (24 lab tasks × 4 runs; 8 open-play runs up
  to 5,000 steps per model), six models interacted through a typed Python REPL
  with `get_entities(radius=1000)` snapshots and `<STALE_ENTITY_DATA_OMITTED>`
  history masking—not screenshots (L13). Frontier models peaked at 21.9 ± 1.3%
  lab success (Claude 3.5 Sonnet), execution errors occurred on 56% of steps
  even in successful lab runs, agents fixed local machines while missing broken
  system links, and models looped (GPT-4o repeated one invalid call 78 times;
  GPT-4o-Mini issued 234 further reset appeals after an illustrated appeal)
  (L13). In CivRealm/FreeCiv 2.6 (150 turns, one 23×23 map seed, 10 first games
  per arm, structured fog-limited state and legal actions), SAGA averaged
  60.7 ± 14.0 Score versus CoS 47.8 ± 20.3 (`p=.064`) and HIMA 43.7 ± 22.3
  (`p=.096`), with a clear significant gain on Buildings (16.3 ± 10.5 vs. ≤7.5)
  and a 49% Score drop (to 30.9 ± 9.5) when on-demand same-turn query tools were
  removed (L26). Removing SAGA's scene graph raised Diplomacy (39.5→45.5) and
  removing its inner goal loop raised Military (59.3→67.5), its `<10 ms` figure
  covers only CPU graph construction, and under the paper's three-role planning
  accounting its reported token total exceeded CoS (367k vs. 281k; the 27%
  saving applied only to output tokens, with full controller cost unestablished)
  (L26).

### Execution state, multi-session error carry-forward and task interruptions

- **Structured execution-state trees beat Full Context and flat/graph baselines while retaining failed branches.**
  MAGE maintains a hierarchical active-path tree with `Compress`, `Maintain` and
  `Revise` operations on structured tool benchmarks (MemoryArena 701 tasks;
  DeepPlanning 240 tasks; no repeat/seed counts reported) (L18). On MemoryArena
  with Qwen3.6-27B, MAGE beat Full Context by +7.8 percentage points in success
  and +8.7 in subtask progress using 55.1% fewer tokens (outperforming flat and
  graph retrieval baselines by 7.8–20.4 points), with consistent gains on two
  further backends (+6.3–19.3 and +6.6–22.2 points) and DeepPlanning (L18).
  Removing any of `Compress`, `Maintain` or `Revise` lowered shopping and travel
  success, though three baselines beat MAGE on math success (0.4500 vs. 0.4250)
  and ReasoningBank used fewer tokens on three domains (L18). Crucially,
  `Revise` does not delete failed branches—it removes their summary from the
  active path while retaining children and diagnostic feedback—and undoing
  external side effects is unspecified (L18).
- **Prior agent edits carried a large penalty on selected bug chains, while verification caught optimistic handoffs.**
  In Multi-step SWE (69 tasks, 574 steps, 5–15 steps/task, 4 rollouts × 9
  models, no reference-prefix control or memory ablation), Claude Opus 5.5
  solved 18.5% of rollouts (31.9% of tasks at least once) while 38/69 tasks had
  zero passing rollouts across all nine models (L19). Pooled within-task
  on-track rate fell from 34.9% in the first fifth to 9.0% in the last fifth,
  step pass rate was 70.2% after a prior pass versus 14.1% after a failure, and
  57% of unqualified completion reports failed hidden verification versus 65% of
  all steps (weighted estimate from a stratified sample of 2,157 reports); the
  design cannot separate inherited errors from harder later steps or recall
  (L19). ChainSWE compared prior gold fixes and gold test patches (Oracle)
  against prior agent edits (Seq) and prior agent edits plus carried transcripts
  across three policies (raw, 50K summarization, delegation; Seq+Mem) on 100
  chronological chains selected for Oracle tractability (304 bugs, 7 models × 3
  harnesses): mean per-bug accuracy fell from 58.9% (Oracle) to 36.5% (Seq;
  −59% to −70% relative at bug 3 across the 97 three-bug chains), while Seq+Mem
  averaged 36.9% (+0.4 points overall; only GPT-5.5 gained materially,
  42.2%→46.8%, and its raw-history arm fell 49.0%→47.4%) (L20). Among traced
  shared-file errors, under-edits outnumbered over-edits ~9:1, though Appendix B
  subgroup tables show smaller Oracle→Seq gaps (2.0–9.9 points) unreconciled
  with the 22.4-point headline (L20).
- **Pre-interruption display visibility reached significance in only one of four separate experiments.**
  In Altmann and Trafton's randomized visual resource-allocation experiments (96
  undergraduates, 24 per warning duration), interruptions doubled time to the
  first action (3.8 s resumption lag vs. 1.9 s between-action baseline with
  intervals under 1 s excluded, `p<.0001` in each experiment) (L21). Keeping the
  entire primary display visible during a pre-interruption warning reached
  significance only in the separate 8-second experiment (`F(1,22)=5.7, p<.03`;
  6 s `p=.056`; 2 s and 4 s `F<1`; omnibus cue `F(1,88)=3.6, p=.060`; cue ×
  duration `p>.25`), while active-window and cursor return cues were deliberately
  removed, perceptual re-encoding remains an alternative explanation, and no
  compact note or summary cue was tested (L21).

### Scientific research agendas, periodic reflection and lab notebooks

- **Joint commitment enforcement and periodic meta-reflection aided open-ended rediscovery on one task.**
  Station ran 300-tick multi-agent research sessions (six agents from three
  model families, text/code workspace, three seeds per rediscovery task) and
  recovered 62.7 ± 2.8% equal-weight criteria (mean ± standard error) across
  three tasks versus 14.4%–20.6% for baselines at unmatched token budgets (L24).
  On the emergent-planning task, jointly removing the Supervisor (enforcing a
  60-tick commitment) and Periodic Meta-Reflection (three GPT-5.5 reflection
  turns every 50 ticks) reduced criteria recovery from 75.8% to 57.9% and mean
  project duration from 67.0 to 55.5 ticks (L24). Individual components were not
  ablated separately, myopic choices persisted (18/24 non-overlapping proposals
  rated 1–2/5 by an oracle author; RNN nonlinear-dynamics recovery fell from
  25.9% at tick 100 to 7.4% at tick 300), and exploratory findings required
  human screening (L24).
- **Schema-governed research memories and epistemic-state proposals lack controlled memory ablations.**
  AutoSci separated schema-governed Markdown project memory (`SciMem`) from
  workflow execution in two end-to-end case studies (157 GPU kernels at 1.18×
  non-degenerate speedup; a biomedical study whose perturbations did not clear
  noise), but included zero memory-removal or alternative-memory ablation (L22).
  Bisht et al. argue that autonomous discovery needs persistent mutable beliefs
  and shifting objectives, while their own experiment measures single-turn
  hypothesis cosine similarity across 12 models (24,480 hypotheses; cross-provider
  new-hypothesis similarity 0.64–0.69 vs. 0.30–0.39 across different papers);
  their widely cited 68% ignored-evidence and 26% refutation-revision rates come
  from a separate secondary study (L23).
- **A biomedical ELN pilot favored OneNote over a structured alternative without post-rollout retention data.**
  In the study's own 42-item technical feature audit, OneNote met 39/42 criteria
  versus 23/42 for structured Elements (L25). In a subsequent three-month
  selection pilot (28 volunteers across eight labs with uneven tool exposure—17
  OneNote-only, 5 Elements-only, 6 both—plus an 80-student two-day workshop),
  labs unanimously preferred OneNote after discussion (69% among students) and
  the study reported an 88% lab-group endorsement of possible paper replacement
  (missing figure prevents converting to a count out of 28) (L25). Post-rollout
  adoption and abandonment rates were not measured, the authors' explanation
  linking preference to nonstandard assays was tentative, and tablets were
  judged unsuitable for replacing daily bench scrap paper (L25).

### Human-factors negative results: automation bias, alarm fatigue and structured debiasing

- **Decision-aid studies frequently detected omission and commission errors, with limited manual-control testing.**
  Across 40 studies covering 17 experimental tasks (median sample 30, range
  5–181; reviewer verification-complexity ICC 0.763), automation bias appeared
  in 25 of 31 omission studies (81%) and 21 of 23 commission studies (91%),
  though only 9 of 40 reported significance tests against manual control (four
  omission, four commission, one null) and no pooled error rates were computed
  (L27). Consistently high aid accuracy produced more bias errors than
  alternating high/low accuracy in the cited comparisons; bias appeared across
  all complexity levels under multitasking and at medium–high complexity in
  rated single tasks; and performance feedback plus three forms of training
  showed no significant reduction, with accountability helping novices only
  mildly (L27).
- **Nurses reported high nuisance-alarm burden, though causal missed-event rates remain unquantified in the review.**
  A review of seven ICU nursing studies (389 nurses: four HTF surveys totaling
  308 respondents, one 48-nurse survey and two interview studies) found nurses
  ranked frequent false alarms reducing attention first among obstacles (mean
  rank 2.84 on a 1–9 scale), with 93% of one 48-nurse sample believing fatigue
  can lead to silencing or ignoring alarms (L28). Only one included study
  directly audited alarms (63.8% false of 2,184 alarms in 48 hours); the
  often-quoted 85%–99% non-actionable range and 80 US deaths are background
  citations without exposure denominators, and none of the seven studies
  estimates a causal missed-event rate (L28).
- **A partial competing-hypotheses procedure showed no significant advantage over a falsificationist control.**
  In a preregistered 2×3 online experiment (`N=159` psychologists and students
  evaluating one ambiguous case under defense, prosecution or court retention;
  planned power reduced from 0.90 to 0.80 during collection, first-time users
  guided through steps 2–5), Analysis of Competing Hypotheses (ACH) detected no
  significant reduction in adversarial allegiance relative to an active
  German-standard control that already considered alternatives—neither on
  credibility (`F(1,153)=.21, p=.649`; interaction `p=.328`) nor on evidence
  score (`F(1,153)=1.79, p=.183`; printed interaction `F(2,153)=.03, p=.804`,
  internally inconsistent with recalculated `p≈.970`) (L29). Retaining party
  shifted evidence selection (`p=.047`) but did not reach significance on
  credibility (`p=.060`), floor effects clustered ACH-defense scores at −1.00
  (all 11 evidence-score outliers occurred in ACH, descriptive only), and the
  null does not prove equivalence or worsening (L29).

## What the full reading corrected

The rightmost column records what the primary texts support after checking
initial discovery claims recorded before full-text reading (and common readings
tested alongside them).

| Source | Initial discovery claim tested | What full reading supports |
| --- | --- | --- |
| Evaluating `AGENTS.md` (L02) | Context files tend to cut success, raise cost >20%, and minimal non-standard rules help. | Cost rose 20% (SWE-bench Lite) and 23% (CTXbench) for generated files; resolution drops were non-significant (`p=.87/.37`), developer files gained +2.4 pp (`p=.21` vs. none, `.038` vs. generated), and **no arm isolated minimal non-standard rules**. |
| DreamBench-SWE (L03) | Preregistered audit compares verbatim (0.4556), hybrid (0.4611) and hosted literal (0.5389), with mechanism contrasts unavailable. | All four v2.1 rates and both unscored mechanism contrasts (recorded as `p=1` multiplicity placeholders) verified; hybrid used ~79× verbatim's tokens and 12,655 judge calls, while in v2 overall hybrid vs. verbatim did not separate (95 vs. 89/180, `p=.518`) and verbatim led the small staleness stratum (13/21 vs. 8/21). |
| StateMemBench (L04) | +15 to +32 point gains from state structure rather than added context. | Answer-time tracing beat transcript-matched controls on a 60-probe slice (+15.0 to +31.7 pp, single run) and gained +11.7 to +25.0 pp on LongMemEval Qwen, but shifted LongMemEval DeepSeek −5 to +5 pp; removing dependency propagation left full StateMem slightly higher on DeepSeek (0.373 vs. 0.363) because propagation cost 12.5 pp on long anti-traps (L04). |
| ESAA (L05) | Event sourcing + materialized views for SE agents; check whether controlled comparisons exist. | Two uncontrolled single-run case studies only; case study 2 was a partial snapshot (**31/50 tasks done, 62%**), §3.2 and §4.2 contradict on log-before-write order, and replay cannot detect silent off-screen world mutation. |
| Outdated Code References (L06) | Most projects accumulate stale code references that remain incorrect for years; verify precision/recall. | Only the most-starred *historical* cohort exceeded 50% (82.3%; current flags were 28.9% and 5.4%); years measure age at inspection, ~55%/45% of already-fixed positive-lag flags survived >1 month, and **precision and recall were unmeasured** (4/15 positive, 4/15 false-positive outreach replies). |
| Living Systematic Reviews (L07) | Continuous surveillance with explicit update triggers and governance for retiring reviews. | Initial PMCID (`PMC3928254`) was an unrelated trout RNA-seq paper. True *PLoS Medicine* text is conceptual with three qualitative publication tiers, **no quantitative triggers**, and **no review-retirement rule** in available prose (Table 1 missing). |
| SwarmWorld (L11) | Decentralized agents self-organize and reuse technology via physical stigmergy rather than direct communication. | "99.3%/96.9% adoption" and "95% physical" count mere observation, every shared arm kept private memory and structured state; full culture led uptake speed and portfolio resilience, while no explicit culture descriptively led validated inventions (7.00 vs. 5.75, `n=4` seeds, min `p=0.125`) and best-of-100 isolated search built the strongest single artifact. |
| Emergent Collective Memory (L12) | Environmental traces alone fail completely without internal memory, beating memory only at high density. | Traces reached **90.1% exploration** (refuting total failure) while tying no-memory on sparse composite score (`p=.65`) and trailing random movement; dense wins held only on composite score (trailing on food), and prose/table mismatches plus a 10× error in Eq. 34 (`0.20/0.0875 ≈ 0.23` vs. `2.286`) undermine the crossover threshold. |
| Factorio Learning Environment (L13) | Frontier LLMs fail at spatial error analysis and multi-step off-screen automation; check interface. | Agents used a **typed Python REPL** (`get_entities(radius=1000)`, `<STALE_ENTITY_DATA_OMITTED>` masking)—not screenshots; off-screen duration was not isolated from query-scoped spatial debugging. |
| Scrub-Jays Caching (L14) | Jays track what–where–when and abandon perishable food once elapsed time exceeds decay. | Devaluation probes measured selective *search* (food removed); degradation was experimenter-manipulated across trials (4 h / 100 h and 2-day schedules), **no natural spoilage cutoff** was tested, and memory-mediated reinforcement remains open. |
| NightWatch (L17) | Lightweight watcher monitors screens to interrupt/wake VLM agents; verify overhead, false-interrupt rate and screenshot-only conditions. | Actors kept trajectory/action text (and web observation text) and watcher probes static screens; **no online false-interrupt rate is reported** (1/201 = 0.5% is an offline premature-wake check at 0.3 s); DynaCU Qwen stayed flat (34.7%→34.7%), and monitoring is limited to visible screens (L17). |
| MAGE (L18) | Execution-state tree supporting active-path reconstruction, pruning and `Revise` to isolate flawed branches. | `Revise` removes summaries from the active view while **retaining failed branches and feedback as siblings** (permanent deletion refuted); repeat counts and external side-effect undo are unreported. |
| Multi-step SWE (L19) & ChainSWE (L20) | Multi-step SWE degrades up to 70% as chains lengthen; ChainSWE separates context loss from bad edits. | The 70% same-position loss belongs to **ChainSWE** (97 three-bug chains, bug 3 under summarization/delegation), not Multi-step SWE (no reference-prefix control); in ChainSWE, carrying chat across three tested policies added **+0.4 points** against a **−22.4-point** Oracle→Seq gap. |
| Task Interruption (L21) | Compact environmental/task resumption cues measurably reduce resumption lag. | The intervention kept the **entire primary display visible before interruption** (significant only in the separate 8 s experiment, `p<.03`; omnibus `p=.060`), deliberately removed return cues, and tested no compact note or summary cue. |
| AutoSci (L22) & Bisht et al. (L23) | AutoSci tests `SciMem` ablations; Bisht et al. check evidence vs. position arguments. | AutoSci has **zero memory ablation**; Bisht et al.'s own experiment measures single-turn hypothesis similarity, while the 68% ignored-evidence and 26% revision rates are secondary citations from Ríos-García et al. |
| Station (L24) | Tests Supervisors and Periodic Meta-Reflection to prevent myopic local optimization. | Both were removed **jointly** on one task (75.8%→57.9%, `n=3` seeds, unmatched tokens, structured code workspace), leaving individual effects unablated, and myopic proposals persisted. |
| Biomedical ELN (L25) | Empirical ELN evaluation; check adoption rates, abandonment reasons and workarounds. | Reports a **three-month selection pilot** preferring OneNote over Elements after a 42-item feature audit; **post-rollout adoption and abandonment rates are absent**, and daily bench scrap paper remained unreplaced. |
| SAGA in CivRealm (L26) | Selective state retrieval in strategy play; check interface, retrieval ablation and cost/latency match. | Uses same-turn structured FreeCiv queries (`<10 ms` is CPU graph build only); overall Score vs. CoS/HIMA was non-significant (`p=.064/.096`), **reported planning-role tokens exceeded CoS (367k vs. 281k)** (27% saving output-only), and retrieval was not matched-cost isolated. |
| Automation Bias (L27), Alarm Fatigue (L28) & ACH (L29) | Verify quantitative error/missed-event rates and ACH statistical outcomes. | L27 counts positive studies without pooled rates (only 9/40 tested significance vs. manual); L28's 85%–99% and 80 deaths are background citations with no causal missed-event rate; L29 confirmed no significant ACH benefit over a falsificationist control (under reduced power and steps 2–5) and contains a printed `F(2,153)=.03, p=.804` discrepancy vs. recalculated `p≈.970`. |

## What this implies here

The points below are **engineering inferences and testable hypotheses** for
Enactive's open memory questions—not owner decisions.

- **Test explicit observation-over-memory precedence for descriptive claims (`#1020`, `#1024`, `#1025`).**
  By analogy to L01's code-versus-instruction-file conflict (where agents often
  named the conflict yet still obeyed the stale file) and L27's finding that
  consistently high aid accuracy increased bias relative to alternating accuracy,
  Enactive should test giving a fresh player-visible observation explicit
  precedence whenever it resolves the same descriptive claim in the same scope,
  and verify whether the player's *action* follows the live observation rather
  than merely noting the discrepancy.
  [World-state facts (#1020)](https://github.com/CVX-Hull/enactive/issues/1020) ·
  [What the curator should record (#1024)](https://github.com/CVX-Hull/enactive/issues/1024) ·
  [Post-cut delivery (#1025)](https://github.com/CVX-Hull/enactive/issues/1025)
- **Test how built-in game displays, external curated memory and fresh checks should divide the work (`#1020`, `#1024`, `#1026`).**
  Three complementary roles emerge across the literature, with their boundary
  still to be tested head-to-head in Enactive:
  1. *Built-in game and environmental displays* (in-game map notes, zones,
     inventories, quest logs, visible landmarks) can expose live readings beside
     stored cues (L09, L10) and avoid duplicating volatile state in external
     prose that drifts (L02, L06); as an untested hypothesis for CDDA-class
     worlds, off-screen map notes or remembered resource locations can still go
     stale between visits.
  2. *External curated memory* is a candidate for cross-session, non-HUD or
     reasoned provenance—what was observed where and when, why a decision was
     taken, and which prior branches failed without deleting their diagnostic
     record (L03, L10, L14, L18)—kept compact and flexible rather than bloated
     with broad overviews or rigid forms that scored poorly in the ELN pilot
     (L02, L25).
  3. *Fresh player-visible evidence* (whether exposed by opening a live
     built-in screen such as inventory/map or by revisiting an off-screen
     location) is required to detect silent world changes that replay logs or
     visible-screen watchers cannot observe (L05, L08, L15, L17). A stored note
     can cue a targeted check, while the choice of when to pay the action cost
     remains open.
  [World-state facts (#1020)](https://github.com/CVX-Hull/enactive/issues/1020) ·
  [What the curator should record (#1024)](https://github.com/CVX-Hull/enactive/issues/1024) ·
  [Working state across cuts (#1026)](https://github.com/CVX-Hull/enactive/issues/1026)
- **Test verbatim evidence as a baseline before adding heavy curation or automatic propagation (`#1020`, `#1024`, `#1025`).**
  L03's preregistered audit and L02's cost penalty show that expensive write-time
  structuring and broad context files do not automatically beat compact,
  reachable verbatim records. L04 shows that automatic dependency propagation
  can hurt anti-traps where an earlier fact remains operative, and L06/L07
  suggest testing lightweight staleness cues (recording last-verified time
  separately from conclusion revision, or flagging disappeared referents for
  recheck rather than silent deletion).
- **Test prerequisite verification and active-path separation across context cuts (`#1021`, `#1022`, `#1026`).**
  L20's −22.4-point Oracle→Seq gap versus +0.4 points from tested transcript
  carryover policies, alongside L19's 57% verification failure rate on
  unqualified completion reports, motivates measuring whether the world still
  satisfies a prerequisite separately from whether the player remembers it. L18
  motivates separating the active working path from retained failed-attempt
  hints across cuts, while L21 suggests testing pre-cut grounding without
  assuming compact notes alone eliminate resumption lag.
  [Dated, anchored facts (#1021)](https://github.com/CVX-Hull/enactive/issues/1021) ·
  [Condition and confidence (#1022)](https://github.com/CVX-Hull/enactive/issues/1022) ·
  [Working state across cuts (#1026)](https://github.com/CVX-Hull/enactive/issues/1026)
- **Test selective lookup, periodic review and reminder noise against cost and missed events (`#1023`, `#1024`, `#1025`, `#1027`).**
  L24 motivates testing a joint commitment-and-reflection schedule—and
  separately isolating each component—against myopic local loops, while L26's
  tool-removal drop motivates testing compact on-demand lookup (`#1023`). L27
  and L28 warn that frequent non-actionable reminders or over-trusted advisory
  prompts can burden attention or induce bias errors (`#1025`), so proactive
  reminders or periodic reviews should be evaluated on false-alarm rate, missed
  actionable changes and total cost (`#1027`), not prompt volume alone.
  [Record findability (#1023)](https://github.com/CVX-Hull/enactive/issues/1023) ·
  [What the curator should record (#1024)](https://github.com/CVX-Hull/enactive/issues/1024) ·
  [Post-cut delivery and reminders (#1025)](https://github.com/CVX-Hull/enactive/issues/1025) ·
  [Live curation cost (#1027)](https://github.com/CVX-Hull/enactive/issues/1027)

## What is not known

- **Off-screen re-check policy under real action cost.** No study in this set
  measures when a screenshot-based player in a persistent world should spend
  in-game time and travel to re-verify a remembered off-screen fact versus act
  on stale memory or consult an in-game map/inventory screen.
- **Built-in game tracker versus external notes head-to-head.** No controlled
  study compares using a game's native tracking tools (such as CDDA map notes,
  zones and inventory screens) against external memory files or a hybrid on
  matched play budgets.
- **Long-horizon verification cadence and memory retirement.** Neither `L07`,
  `L08` nor `L14` supplies transferable checking intervals or expiration rules
  for CDDA-class worlds; empirical measurement on real extended runs is needed.
- **Intentional strategy shifts versus stale-note precedence.** `L01` tested
  only cases where the instruction file was wrong; how to give live observation
  precedence on descriptive world facts while still letting intentional long-term
  goal revisions stick remains an open design test.

## Sources

Two independent clean-context reviewers from other model families checked this
page against the reconciled digests and extracted primary texts before it
merged; their briefs, reviews and the lead's disposition are sealed as
[`long-horizon-offscreen-memory-research-review`](../data/evidence/long-horizon-offscreen-memory-research-review.sha256).

“Reading reports” counts independent reports on the extracted primary text from
distinct model families; all 29 works have two reading reports plus one
reconciled digest. Read limits and skipped sections are stated above and in
individual rows.

<!-- sources-table -->
| ID | Source and version read | Main result in the text read | Strength | Reading reports |
| --- | --- | --- | --- | ---: |
| L01 | [Stale Instruction Files Override the Code in Coding Agents](https://arxiv.org/abs/2610.30571v1), arXiv v1, 22 Oct 2026 | Agents followed stale files in 90.1% (649/720) of choices vs. 4.2% live code; Claude Code named the conflict in 79/80 runs yet followed the file on 86.2% of choices in those runs; one precedence-and-reporting sentence raised code-following to 91.4% and test passes 89.4%→100% (§§5.1–5.5). Lost: Figs. 1–8 captions only. | Strong | 2 |
| L02 | [Evaluating AGENTS.md](https://arxiv.org/abs/2602.11988v3), arXiv v3, 29 Sep 2026 | Generated context files lowered resolution in 5/8 cells (−0.5/−2.0 pp, p=.87/.37) and raised cost +20%/+23%; developer files gained +2.4 pp on CTXbench (p=.21 vs. none, p=.038 vs. generated) at ≤19% extra cost (§4.2, Tables 3–6). Lost: Figs. 1–15 captions only; App. E prompts absent. | Moderate | 2 |
| L03 | [DreamBench-SWE](https://arxiv.org/abs/2608.20664v1), arXiv v1, 21 Aug 2026 | Preregistered v2.1 (180 cells/arm): no memory 21/180 (.1167), verbatim 82/180 (.4556), hybrid 83/180 (.4611, ~79× tokens, 12,655 judge calls vs. 0), hosted literal 97/180 (.5389); all three beat no memory (Holm p≤.0013); mechanism contrasts unscored (p=1 placeholders); v2 hybrid vs. verbatim 95 vs. 89/180 (p=.518), staleness 8/21 vs. 13/21 (§6.6, Tables 7–13, 20). Lost/unread: Figs. 1–2 captions; external records unread. | Moderate | 2 |
| L04 | [Can Agent Memory Systems Track Evolving State? (StateMemBench)](https://arxiv.org/abs/2608.19652v1), arXiv v1, 20 Aug 2026 | Answer-time tracing beat transcript-matched control +15.0 to +31.7 pp on 60-probe slice (p≤.04), gained +11.7 to +25.0 pp on LongMemEval Qwen and shifted DeepSeek −5 to +5 pp; full StateMem scored .363/.233 on 322 probes and removing propagation left DeepSeek .373 (§§6.1–6.4, Tables 3–6). Lost: Figs. 1–2, boxed dialogues, App. F.1 prompt. | Moderate | 2 |
| L05 | [ESAA: Event Sourcing for Autonomous Agents](https://arxiv.org/abs/2602.23193v1), arXiv v1, 26 Feb 2026 | Two uncontrolled single-run SE case studies (9 tasks/49 events; 86 events with 31/50 tasks done, 62%) verified replay hashes; no baseline or ablation; §3.2 vs. §4.2 contradict on log-before-write order (§§3–6, Tables 2, 4). Lost: Fig. 1 caption; App. E excerpt only. | Weak | 2 |
| L06 | [Detecting Outdated Code Element References](https://arxiv.org/abs/2212.01479v1), arXiv v1, 2 Dec 2022 | Flagged stale refs in 28.9% (265/918) top-starred and 5.4% (101/1,879) Google projects (mean age 4.7/4.2 yrs; ever-flagged 82.3%/29.7%); ~55%/45% of fixed positive-lag flags survived >1 month; precision/recall unmeasured, 15-project outreach drew 4 positive, 4 false-positive, 7 nonresponses, 5/19 fixes (§§5.1–5.4, Table 6). Lost/unread: Figs. 1–15 captions; external appendix unread. | Moderate | 2 |
| L07 | [Living Systematic Reviews](https://doi.org/10.1371/journal.pmed.1001603), PLoS Medicine 11(2), 18 Feb 2014 | Conceptual workflow separating last-search-date updates, modest editorial updates (unchanged conclusions) and rapid peer review; cites 2.5–6.5 yr neurotrauma lags and manual title/abstract screening cuts up to 50% (new reviews) and >90% (updates); no trial, numeric triggers or retirement rule in prose. Lost: Figs. 1–2 and Table 1 cells missing. | Weak | 2 |
| L08 | [Inventory Record Inaccuracy and Cycle Counting](https://doi.org/10.1590/0103-6513.20220077), Production 33, 2023 | 360-day Stella simulation across five WERC classes: zero counting lost 45.80% (MO) to 4.60% (BIC) annual demand; 5 counters cut MO/DIS losses (to 29.00%/17.81%) while leaving inaccuracy above start; class recovery needed 10–14/15+ counters in MO and 2+ in BIC/ADV (§§4–5, Tables 3–4). Lost: Figs. 1–3 missing; App. B equations displaced. | Moderate | 2 |
| L09 | [On Distinguishing Epistemic from Pragmatic Action](https://adrenaline.ucsd.edu/kirsh/Articles/CogsciJournal/DistinguishingEpi_prag.pdf), Cognitive Science 18, 1994 | Tetris keystroke logs show wall-check routines before ~1% of drops at higher board heights (ordinary vs. wall-routine mean heights: intermediate 13.18 vs. 19.04, advanced 13.69 vs. 19.33, expert 15.65 vs. 20.05, α=.05); causal load reduction during play unmeasured (Table 1). Lost: OCR damaged Figs. 1–17 and piece glyphs. | Moderate | 2 |
| L10 | [How a Cockpit Remembers Its Speeds](https://pages.ucsd.edu/~johnson/COGS102B/Hutchins95.pdf), undated UCSD draft manuscript | Stylized MD-80 approach account (100+ observer flights across 6 years) showing speed cards and movable markers set 25–30 min pre-landing turn recall into perceptual comparison beside live needles; no experimental arms or error-rate effect size. Lost/unread: Table 1 missing; Figs. 1–4 degraded; published DOI text unverified. | Moderate | 2 |
| L11 | [SwarmWorld](https://arxiv.org/abs/2608.26081v1), arXiv v1, 26 Aug 2026 | Four-seed BioFoundry runs (private memory and structured state in all shared arms): 99.3%/96.9% noncreator adoption (including first observation) and ~95% first encounter via observation; at 3,200 ticks, full culture led resilience (0.2474 vs. 0.2365) and uptake speed while trailing no-explicit on validated inventions (5.75 vs. 7.00, min p=0.125); best-of-100 isolated envelope built top artifact (0.3488) (§§2.2–2.9). Lost/unread: plot-only values, §§S3.1–S3.4 graphics, external tables. | Moderate | 2 |
| L12 | [Emergent Collective Memory](https://arxiv.org/abs/2512.10166v1), arXiv v1, 10 Dec 2025 | Mesa foraging grids: traces alone reached 90.1% exploration while tying neither mechanism on sparse composite (p=.65) and trailing random movement (random +22.7%, p<.01); dense large-grid composite led (103.64 vs. 77.11 at 625 agents) while trailing on food (19.71 vs. 22.62); prose/table mismatches and Eq. 34 error weaken crossover claim (§6, Tables 1–3). Lost: Figs. 1–4; some math signs corrupted. | Weak | 2 |
| L13 | [Factorio Learning Environment](https://arxiv.org/abs/2503.09617v1), arXiv v1, 6 Mar 2025 | Six models via typed Python REPL (`get_entities(radius=1000)`, `<STALE_ENTITY_DATA_OMITTED>`—not screenshots): Claude 3.5 Sonnet peaked at 21.9±1.3% lab success; 56% step errors in passing lab runs; looping (78 repeated calls; 234 further reset appeals) (§4, Tables 1–2, Apps. F–G). Lost/skipped: plotted curves, maps and manual absent; one reader skipped middle references and repetitive App. J.2 schema fields. | Moderate | 2 |
| L14 | [Prospective Cognition of Food Caching by Western Scrub-Jays](https://doi.org/10.3819/ccbr.2008.10001), vol. 1, 2006 copyright | Review of controlled cage trials: preferential search for non-devalued food sites after same-day/1-week delays (food removed at test), reduced worm caching after 2–4 trials of manipulated degradation (4 h/100 h or 2-day), experience-dependent re-caching (~20%–25% still in risky sites); no natural spoilage cutoff tested. Lost: interleaved PDF columns, missing bar heights/graphics. | Moderate | 2 |
| L15 | [Nonlinear POMDPs for Active State Tracking with Sensing Costs](https://arxiv.org/abs/1405.5892v1), arXiv v1, 22 May 2014 | Known Markov/Gaussian model calibrated to one individual's biometric signals: myopic sensing saved 60% energy vs. equal allocation at matched accuracy (12-sample cap, 4% error in abstract), CE–WWLB saved 7%, exact DP intractable above 2 samples; Corollary 3 covers one-step costs under two-state symmetry (§VI). Lost: Figs. 1–8 captions; malformed equations. | Moderate | 2 |
| L16 | [OCMDP: Observation-Constrained MDP](https://arxiv.org/abs/2411.07087v4), arXiv v4, 23 Jan 2025 | Model-free decoupled learner reported +71% return over model-free baselines and −50% observation cost vs. fixed/continuous observation on Diagnostic Chain, and ~75% higher return than PPO on HeartPole (~80%/90% over always/never observing); no seed counts, price sweeps or joint-training ablation; latent-state supervision inconsistent (§§4–5). Lost: Figs. 1–6 captions; no numeric tables; malformed macros. | Weak | 2 |
| L17 | [Don't Sleep, Keep Watch (NightWatch)](https://arxiv.org/abs/2611.28947v1), arXiv v1, 21 Nov 2026 | Frozen 0.8B 10 Hz visual watcher cut OSWorld non-reasoning time 33%/41% (p=.026/.016) and screen-change stale proxies while raising avg@3 66.3%→68.0% and 56.3%→58.7%; DynaCU rose 39.5%→44.2% (MiMo) and stayed flat 34.7%→34.7% (Qwen); removing void raised target mismatch 3.6%→15.9%; visible screen only, no online false-interrupt rate (Tables 1–3). Lost: Figs. 1–5 panels and three App. B examples. | Strong | 2 |
| L18 | [Beyond Semantic Organization (MAGE)](https://arxiv.org/abs/2606.06090v2), arXiv v2, 15 Oct 2026 | Execution-state tree gained +7.8 pp success over Full Context on MemoryArena with 55.1% fewer tokens (Qwen3.6-27B) and improved DeepPlanning; removing `Compress`, `Maintain` or `Revise` lowered shopping and travel scores; `Revise` keeps failed branches as sibling hints; repeat counts and side-effect undo unreported (§4, Alg. 1, Tables 3–8). Lost: Figs. 1–4 graphics and App. B.1 prompts. | Moderate | 2 |
| L19 | [Multi-step SWE](https://arxiv.org/abs/2611.07166v1), arXiv v1, 4 Nov 2026 | 69 tasks (5–15 steps, 4 rollouts × 9 models): Claude Opus 5.5 solved 18.5% of rollouts (31.9% of tasks ≥1×); 38/69 tasks unsolved by all models; within-task on-track rate fell 34.9%→9.0%; 57% of unqualified completion reports failed verification vs. 65% of all steps (weighted, 2,157 reports); no reference-prefix control (§§3.2–3.3, Table 5). Lost: Figs. 1–4 captions. | Moderate | 2 |
| L20 | [ChainSWE](https://arxiv.org/abs/2607.02606v2), arXiv v2, 1 Sep 2026 | 100 Oracle-screened chains (304 bugs, 7 models × 3 harnesses): per-bug accuracy fell 58.9% Oracle → 36.5% Seq (−59% to −70% at bug 3 across 97 three-bug chains) → 36.9% Seq+Mem (+0.4 pp across three chat policies; GPT-5.5 42.2%→46.8%); under-edits outnumbered over-edits ~9:1; App. B gaps (2.0–9.9 pp) unreconciled (§5, Tables 2–4, 10–11). Lost: Figs. 1–4; App. C patches and App. D prompts. | Strong | 2 |
| L21 | [Task Interruption: Resumption Lag and the Role of Cues](https://escholarship.org/uc/item/18b4r661), CogSci 26, 2004 | Randomized visual-task experiments (N=96): resumption lag 3.8 s vs. 1.9 s between-action baseline (intervals <1 s excluded, p<.0001); keeping full primary display visible *before* interruption reached significance only in the separate 8 s experiment (F(1,22)=5.7, p<.03; omnibus p=.060, interaction p>.25); return cues removed, no compact note tested (pp. 44–48). Lost: interleaved PDF columns; Figs. 2–7. | Moderate | 2 |
| L22 | [AutoSci](https://arxiv.org/abs/2605.31468v1), arXiv v1, 29 May 2026 | Separates schema-governed Markdown memory (`SciMem`) from workflow in two case studies (157 GPU kernels, 1.18× non-degenerate speedup; biomedical perturbations within noise); zero memory-removal or alternative-memory ablation (§7). Lost: Figs. 1–11 graphics; some raw TeX in flattened tables. | Anecdote | 2 |
| L23 | [Agentic AI Scientists Are Not Built For Autonomous Scientific Discovery](https://arxiv.org/abs/2605.08956v3), arXiv v3, 6 Nov 2026 | Position paper proposing persistent mutable beliefs and shifting objectives; own experiment measures single-turn hypothesis similarity across 12 models (24,480 hypotheses; cross-provider 0.64–0.69 vs. 0.30–0.39 across papers); cited 68% ignored-evidence / 26% revision rates come from secondary work (§5, Table 3). Lost/skipped: Figs. 1–6 and App. A.7 prompt absent; one reader skipped part of references and App. A.8–A.9 paper lists. | Weak | 2 |
| L24 | [Evidence from Station](https://arxiv.org/abs/2610.08927v1), arXiv v1, 6 Oct 2026 | 300-tick multi-agent scientific discovery (3 seeds/task, unmatched tokens): 62.7±2.8% criteria recovery (mean ± SE) vs. 14.4%–20.6% baselines; jointly removing 60-tick Supervisor commitment and 50-tick Meta-Reflection cut planning recovery 75.8%→57.9% and project duration 67.0→55.5 ticks; components unablated individually (§6, Tables 3–4). Lost/skipped: Figs. 1–5 absent; one reader skipped Supervisor/Reflection/Consolidation/Codex prompts, App. C rubrics, parts of Tables 5–7 and part of references. | Moderate | 2 |
| L25 | [Implementation of an ELN in a Biomedical Research Institute](https://doi.org/10.1371/journal.pone.0160428), PLoS ONE 11(8), 1 Aug 2016 | Feature audit scored OneNote 39/42 vs. structured Elements 23/42; in a 3-month selection pilot (28 volunteers, plus 80-student workshop), labs unanimously preferred OneNote (69% students) with 88% lab-group endorsement of possible paper replacement, while bench scrap paper stayed unreplaced; no post-rollout adoption/abandonment data. Lost: Table 1 matrix and Figs. 1–3 missing. | Moderate | 2 |
| L26 | [SAGA: Scene-Aware, Goal-Evolving Agents](https://arxiv.org/abs/2606.29932v4), arXiv v4, 21 Jul 2026 | CivRealm/FreeCiv 2.6 (150 turns, seed 2025, 10 games/arm, structured same-turn state): SAGA Score 60.7±14.0 vs. CoS 47.8±20.3 (p=.064) and HIMA 43.7±22.3 (p=.096); clear Buildings gain (16.3 vs. ≤7.5); removing query tools cut Score 49% (to 30.9); reported planning-role tokens exceeded CoS (367k vs. 281k; 27% saving output-only) (Tables 1–2, 6, 8). Lost: Figs. 1–5 captions; one App. N example missing. | Moderate | 2 |
| L27 | [Automation Bias and Verification Complexity](https://doi.org/10.1093/jamia/ocw105), JAMIA 24(2), Mar 2017 (online Aug 2016) | Systematic review of 40 studies (17 tasks; verification-complexity ICC .763): bias occurred in 25/31 omission (81%) and 21/23 commission (91%) studies (study counts, no pooled rates; 9/40 tested significance vs. manual); consistently high accuracy exceeded alternating accuracy in bias errors; feedback and three training forms showed no significant reduction (Tables 1–2). Lost/unread: Fig. 1 and supplementary Apps. A–B absent. | Moderate | 2 |
| L28 | [Impact of Alarm Fatigue on ICU Nurses](https://doi.org/10.3390/ijerph17228409), IJERPH 17(22), 13 Nov 2020 | Review of 7 studies (389 nurses; 4 HTF surveys = 308): nurses ranked frequent false alarms reducing attention first (2.84/9); one alarm audit found 63.8% false of 2,184 alarms in 48 h; 85%–99% and 80 deaths are background citations, and no included study estimates causal missed-event rates (Tables 1–2). Lost: Fig. 1 and study-level Oxford grades missing. | Weak | 2 |
| L29 | [Analysis of Competing Hypotheses and Adversarial Allegiance](https://doi.org/10.1371/journal.pone.0346891), PLoS One 21(4), 20 Apr 2026 | Preregistered 2×3 online trial (N=159; planned power lowered .90→.80, first-time users on steps 2–5, one ambiguous case, floor effects): detected no significant ACH benefit vs. a falsificationist control on credibility (p=.649; interaction p=.328) or evidence score (p=.183; printed F(2,153)=.03, p=.804 vs. recalculated p≈.970); retaining party shifted evidence selection (p=.047) but not credibility (p=.060). Lost/unread: Tables 1–3, Figs. 1–4 and external preregistration unread. | Moderate | 2 |
