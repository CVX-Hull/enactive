---
owner: lead
status: active
date: 2026-11-26
scope: 'Outside evidence from 29 works beyond short-horizon game agents on stale memory precedence, evolving off-screen state, environmental tracking, active sensing, multi-session error carry-forward, scientific discovery and human-factors failure modes'
review_trigger: 'The owner decides #1020–#1027 or the boundary between built-in game tracking, external memory and active re-observation, or a study tests one of these questions in extended play'
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
before settling leaf owner decisions (`#1020`–`#1027`). Related research covers
[memory statement kinds](research-memory-statement-kinds.md),
[memory, ontology and oversight](research-curated-memory.md) and
[belief under conflict](research-belief-under-conflict.md).

## At a glance

- **Stale external instructions override live observation unless precedence is stated.**
  In a controlled coding-agent test, agents followed stale instruction files in
  90.1% of choices over live code; one model named the conflict in 79 of 80 runs
  and still followed the stale file on 86.2% of choices in those runs (L01). One
  precedence-and-reporting sentence flipped code-following from 4.2% to 91.4% (L01).
- **Extra context and complex curation often raise cost without beating verbatim evidence.**
  LLM-generated repository context files increased inference cost by 20%–23% while
  lowering task resolution in five of eight benchmark cells (L02). In a
  preregistered multi-session benchmark, verbatim event memory (45.6%) matched a
  typed-plus-raw hybrid (46.1%) that used roughly 79× the tokens and 12,655 judge
  calls, and trailed it less than it led on staleness in the earlier release (L03).
- **Accumulated bad state hurts multi-session work far more than missing chat history.**
  Across 100 sequential bug chains, carrying prior agent edits cut per-bug accuracy
  from 58.9% to 36.5%, whereas carrying full conversation history added only 0.4
  percentage points overall (L20). In a separate multi-step benchmark, 57% of
  unqualified completion reports failed independent verification (L19).
- **No outside game-agent study here isolates screenshot-only off-screen tracking.**
  Both the Factorio (L13) and Civilization (L26) studies exposed typed structured
  engine queries rather than screenshots alone, and the proactive computer-use
  watcher (L17) reacts only to visible-screen changes, giving no signal that a
  remembered off-screen fact has changed.
- **Perpetual ledgers drift without physical verification, and aids can induce bias or fatigue.**
  Warehouse simulations show unverified ledgers lose up to 45.8% of demand until
  verification capacity exceeds error generation (L08). Human-factors reviews find
  automation bias in 25/31 omission and 21/23 commission studies—worsened, not
  cured, by high aid accuracy—and show that high false-alarm volume burdens
  operators (L27, L28), while one preregistered test of a structured competing-hypotheses
  matrix failed to reduce allegiance bias over a simpler falsificationist control (L29).

## Brief and method

**Questions**

- What do non-gaming long-horizon domains—software engineering maintenance,
  scientific research and lab notebooks, high-stakes operations, and formal active
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
signal. The owner approved the 29-work shortlist (`L01`–`L29`) before full-text
reading began.

**Reading and reconciliation.** Primary full text was fetched for all 29 works
(21 arXiv HTML exports, 4 journal HTML articles and 4 PDFs converted to text).
The works were divided into seven batches and read independently by two model
families per batch (14 reading reports in total), testing pre-registered
abstract/snippet claims against full text and recording baselines, denominators,
counter-results and unread material. A separate reader reconciled each batch
against the extracted texts (seven reconciled digests), and the lead spot-checked
decisive figures directly in the extracts before drafting. During batch 2, both
readers discovered that a fetched PubMed Central identifier (`PMC3928254`) for
`L07` resolved to an unrelated RNA-seq paper; the lead verified the actual
*PLoS Medicine* DOI (`10.1371/journal.pmed.1001603`), fetched its text and ran a
full two-family reading and reconciliation in batch 7. The briefs, explorer
outputs, reading reports, reconciled digests, claims list and scripts are sealed
as evidence; downloaded source texts are not committed or sealed.
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
  recognition degraded diagrams, columns or glyphs in the PDFs `L09`, `L14` and
  `L21`. Appendix prompt bodies were absent from the HTML extracts of `L02`,
  `L18`, `L20` and `L23`, and `L26` omitted one rendered prompt example.
- **Drafts and external supplements.** The fetched copy of `L10` is an undated
  author draft manuscript. External linked supplements, code repositories, raw
  data or preregistration pages outside the fetched primary text were not read
  (notably `L03`, `L06`, `L11`, `L13`, `L27`, `L29`).
- **Scope and unfetched leads.** Only open-access primary texts were read;
  paywalled studies without an accessible full primary text were not imported as
  quantitative evidence. Strength ratings follow the reconciled digests and
  reflect each study's evidence for its tested claim, not transfer to screenshot-based
  gameplay.

## What the evidence says

### Stale instructions, context files and documentation rot

- **Stale instruction files prevailed over live code even when agents noticed the conflict.**
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
  rates from 89.4% (143/160) to 100% (160/160) (L01). The experiment leaves
  intentional migrations untested and bundles precedence with reporting (L01).
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
- **Documentation code references rot widely and linger for years.**
  Scanning 991 top-starred and 2,277 Google GitHub repositories by checking
  whether documented code identifiers disappeared from source history flagged
  stale references in 28.9% (265/918) and 5.4% (101/1,879) of matched projects
  at inspection, with mean ages of 4.7 and 4.2 years, and 82.3% (658/800) and
  29.7% (567/1,907) ever flagged in history (L06). Among already-fixed flags
  with positive timestamp differences, roughly 55% and 45% persisted longer than
  one month (L06). Detector precision and recall were unmeasured; outreach to 15
  active Google projects drew four positive responses, four false-positive
  reports, seven nonresponses and five fixes out of 19 reported instances (L06).

### Verbatim evidence, state tracing, living reviews and event sourcing

- **Verbatim evidence matched a much costlier curated hybrid on a preregistered audit.**
  In DreamBench-SWE's preregistered v2.1 audit (60 multi-session repository
  traps × 3 seeds = 180 scored cells per arm, Codex CLI/GPT-5.5 wake agent),
  pass rates were 11.67% (21/180) without memory, 45.56% (82/180) with verbatim
  event memory, 46.11% (83/180) with a typed-plus-raw hybrid and 53.89% (97/180)
  with pinned hosted literal storage (L03). The hybrid arm consumed roughly 79×
  verbatim's tokens (174.205M vs. 2.209M) and 12,655 judge calls versus zero;
  both preregistered mechanism contrasts failed construct or pre-evaluation
  repair gates (`p=1`), and hosted literal versus hybrid failed to separate
  (`p=.163` clustered, `.607` by trap majority) (L03). In the earlier v2 panel,
  hybrid scored lower than verbatim on staleness/supersession (8/21 vs. 13/21)
  and had lower useful-memory precision (0.264 vs. 0.556), while disabling
  contradiction repair descriptively raised typed-only passes from 80/180 to
  88/180 (L03).
- **Answer-time state tracing helped when the update was already in the transcript, but propagation could backfire.**
  On a 60-probe frozen slice of StateMemBench (anti-traps overrepresented), an
  answer-time structured state-tracing wrapper beat a transcript-matched generic
  control by 15.0–31.7 percentage points across all 12 backend–model cells
  (`p≤.04`), but on LongMemEval it shifted DeepSeek-V4-Flash by −5 to +5 points
  and question-blind summaries fell below retrieval alone (L04). Across all 322
  probes, persistent StateMem scored 0.363 on DeepSeek and 0.233 on Qwen-3.5-9B
  (level with GraphRAG at 0.224, `p=.82`), leaving 49.1% and 64.3% residual
  drift; removing dependency propagation from full StateMem *raised* overall
  accuracy from 0.363 to 0.373 because propagation cost 12.5 points on long
  anti-traps where earlier facts remained operative (L04).
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
  review when estimates barely move, and rapid full peer review when estimates
  or conclusions shift meaningfully (L07). The paper has no controlled outcome
  trial, no quantitative update thresholds and—in the available prose—no
  review-retirement rule, and warns that frequent reanalysis can inflate false
  positives (L07).

### Off-screen drift, cycle counting and active sensing

- **Unchecked perpetual ledgers degrade until verification capacity exceeds error generation.**
  In a 360-day Stella distribution-center simulation across five WERC accuracy
  classes, zero physical cycle counting caused annual lost demand ranging from
  4.60% in Best-in-Class (BIC) to 45.80% in Major Opportunity (MO), with picking
  productivity falling to 54.30% in MO because false presence wasted trips while
  false absence hid usable stock (L08). Daily cycle counting restored accuracy
  only once capacity outpaced error creation: five counters still left MO and
  Disadvantage (DIS) worse than starting inaccuracy (+1.9× and +1.7×), whereas
  MO required 10–14 counters to reach DIS and 15+ to reach Typical, and BIC/ADV
  stabilized at 2+ counters (L08). Unpriced counting labor, unverified constants
  and internal table/prose discrepancies prevent transferring the counter counts
  outside the model (L08).
- **Animal caching shows item–place–outcome selectivity without supplying a universal decay rule.**
  Reviewing controlled laboratory trials with Western scrub-jays, Clayton et al.
  document selective recovery of non-devalued foods after afternoon or one-week
  delays, reduced caching of worms after two to four trials of experimenter-induced
  degradation at 4-hour/100-hour or two-day intervals, and experience-dependent
  re-caching when observed (though watched birds still placed ~20%–25% of caches
  in risky lit or exposed sites) (L14). Because degradation was manipulated across
  trials rather than varied continuously to locate a natural spoilage cutoff,
  the review supplies no natural expiration threshold and leaves memory-mediated
  reinforcement open as an alternative to prospective planning (L14).
- **Formal active sensing prices observations against tracking error, with strong model limits.**
  In a finite-state Markov / Gaussian-observation POMDP calibrated to biometric
  sensors, belief-dependent myopic sensing saved 60% energy versus static equal
  allocation at matched accuracy (4% detection error at a 12-sample cap, plot
  unrecoverable), while offline CE–WWLB saved 7% and exact dynamic programming
  became computationally intractable above two samples per slot (L15). Threshold
  optimality in Corollary 3 applies only to one-step costs under narrow
  two-state scalar symmetry (L15). A model-free Observation-Constrained MDP
  (OCMDP) decoupling observation and control policies reported ~71%–75% higher
  returns and 50% lower observation cost on two toy simulations (Diagnostic
  Chain and HeartPole), but lacks seed counts, price sweeps, a joint-training
  decomposition ablation and consistent latent-state supervision equations (L16).
- **Proactive visual watching cuts wait time on visible screens without tracking off-screen state.**
  NightWatch pairs a frozen 0.8B pixel-gated 10 Hz visual watcher with a
  computer-use actor to wake after settling, interrupt stale inference or void
  misaligned pending actions (L17). Across 100 OSWorld-Verified tasks × 3 for
  two actors (MiMo-V2.6-Flash and Qwen3.8-27B FP8), NightWatch cut non-reasoning
  time by 33% (`p=.026`) and 41% (`p=.016`) and total loop time by 8% and 11%,
  cut premature/stale steps (9.6%→2.6% / 17.4%→8.3% and 11.4%→1.9% / 17.2%→11.8%),
  and nudged avg@3 success from 66.3%→68.0% and 56.3%→58.7% at near-equal API
  cost (excluding local watcher GPU) (L17). On 49 audio-free DynaCU web tasks × 3,
  MiMo rose 39.5%→44.2% while Qwen stayed flat at 34.7%→34.7%, and removing
  wake, interrupt or void dropped MiMo to 38.1%, 30.6% or 36.1% (removing void
  raised target mismatch 3.6%→15.9%) (L17). Yet MiMo regressed on transient
  notifications (36.7%→33.3%), Impress (58.3%→54.2%) and OS tasks (70.8%→62.5%),
  53/63 failing web runs timed out, no online false-interrupt rate is reported,
  and the watcher monitors only the visible screen (L17).

### Built-in world tracking, epistemic actions and long-horizon game scaffolds

- **Physical actions and environmental markers offload recall when live cues sit beside them.**
  In real-time Tetris, Kirsh and Maglio logged information-seeking physical
  actions—most cleanly a trip to the wall and back to verify alignment before
  ~1% of drops, occurring at significantly greater heights across intermediate
  (13.18 vs. 19.04), advanced (13.69 vs. 19.33) and expert (15.65 vs. 20.05)
  players (`α=.05`)—though causal cognitive-load reduction during play was not
  directly measured and the 100 ms physical vs. 800–1,200 ms mental comparison
  mixes gameplay best-cases with a three-player pilot (L09). In an MD-80
  cockpit, Hutchins describes how posted speed cards and movable airspeed bugs
  set 25–30 minutes before landing turn memory recall into perceptual comparison
  against a live airspeed needle—working because a live reading sits next to the
  stored marker, with no quantitative error-rate trial (L10).
- **World artifacts can coordinate reuse, but stale traces and unguided proliferation carry trade-offs.**
  In SwarmWorld (one model, `gpt-5.6-luna`, four seeds per comparison, where
  every shared arm retained structured local state and private memory), 99.3% of
  artifacts under full culture and 96.9% under no explicit culture had
  noncreator reuse, with ~95% of first encounters occurring via physical
  observation (defined to include mere observation) (L11). At 3,200 ticks,
  removing explicit culture actually beat full culture on validated inventions
  (7.00 vs. 5.75) despite fewer total artifacts (238.5 vs. 277.5), while
  isolated search produced the strongest single artifact (0.3488 vs. 0.2380),
  and both shared arms completed zero valid assays in a single-seed Protein
  Realms pilot (L11). In a hand-coded Mesa foraging grid, environmental traces
  alone did not fail completely—reaching 90.1% exploration coverage—and beat a
  memory comparator on composite score in dense large grids (e.g., 103.64 vs.
  77.11 at 625 agents) while still trailing on food (19.71 vs. 22.62), though
  internal prose/table mismatches and an arithmetic error in Equation 34
  (`0.20/0.0875 ≈ 0.23` printed instead of `2.286`) make its crossover threshold
  unreliable (L12).
- **Long-horizon strategy and factory benchmarks still struggle even with exact structured engine queries.**
  In Factorio Learning Environment (24 lab tasks × 4 runs; 8 open-play runs up
  to 5,000 steps per model), six models interacted through a typed Python REPL
  with `get_entities(radius=1000)` snapshots and `<STALE_ENTITY_DATA_OMITTED>`
  history masking—not screenshots (L13). Frontier models peaked at 21.9 ± 1.3%
  lab success (Claude 3.5 Sonnet), execution errors occurred on 56% of steps
  even in successful lab runs, agents fixed local machines while missing broken
  system links, and models looped (GPT-4o repeated one invalid call 78 times;
  GPT-4o-Mini issued 234 reset appeals in an illustrated episode) (L13). In
  CivRealm/FreeCiv 2.6 (150 turns, one 23×23 map seed, 10 first games per arm,
  structured fog-limited state and legal actions), SAGA averaged 60.7 ± 14.0
  Score versus CoS 47.8 ± 20.3 (`p=.064`) and HIMA 43.7 ± 22.3 (`p=.096`), with
  a clear significant gain on Buildings (16.3 ± 10.5 vs. ≤7.5) and a 49% Score
  drop (to 30.9 ± 9.5) when on-demand same-turn query tools were removed (L26).
  Removing SAGA's scene graph raised Diplomacy (39.5→45.5) and removing its
  inner goal loop raised Military (59.3→67.5), its `<10 ms` figure covers only
  CPU graph construction, and total token cost was higher than CoS (367k vs.
  281k total; the 27% saving applied only to output tokens) (L26).

### Execution state, multi-session error carry-forward and task interruptions

- **Structured execution-state trees beat flat retrieval while keeping failed branches as sibling hints.**
  MAGE maintains a hierarchical active-path tree with `Compress`, `Maintain` and
  `Revise` operations on structured tool benchmarks (MemoryArena 701 tasks;
  DeepPlanning 240 tasks; no repeat/seed counts reported) (L18). On MemoryArena
  with Qwen3.6-27B, MAGE beat Full Context by +7.8 percentage points in success
  and +8.7 in subtask progress using 55.1% fewer tokens, with consistent gains
  on two further backends (+6.3–19.3 and +6.6–22.2 points) and DeepPlanning
  (L18). Removing any of `Compress`, `Maintain` or `Revise` lowered shopping and
  travel success, though three baselines still beat MAGE on math success (0.4500
  vs. 0.4250) and ReasoningBank used fewer tokens on three domains (L18).
  Crucially, `Revise` does not delete failed branches—it removes their summary
  from the active path while retaining children and diagnostic feedback—and
  undoing external side effects is unspecified (L18).
- **Accumulated errors in the workspace dwarf missing conversation history across multi-session coding.**
  In Multi-step SWE (69 tasks, 574 steps, 5–15 steps/task, 4 rollouts × 9
  models), the best model (Claude Opus 5.5) solved 18.5% of rollouts (31.9% of
  tasks at least once) while 38/69 tasks had zero passing rollouts across all
  nine models (L19). Pooled within-task on-track rate fell from 34.9% in the
  first fifth to 9.0% in the last fifth, step pass rate was 70.2% after a prior
  pass versus 14.1% after a failure, and 57% of unqualified completion reports
  failed hidden verification (L19). ChainSWE isolated prior bad state from chat
  history across 100 chronological chains (304 bugs, 7 models × 3 harnesses):
  mean per-bug accuracy dropped from 58.9% in Oracle (clean prior fixes) to
  36.5% in Seq (agent-edited repo, fresh chat; −59% to −70% relative at bug 3
  across harnesses), while Seq+Mem (carrying full chat history) reached 36.9%
  (+0.4 points overall; only GPT-5.5 gained materially, 42.2%→46.8%, and its
  raw-history arm fell 49.0%→47.4%) (L20). Among traced shared-file errors,
  under-edits outnumbered over-edits ~9:1, though Appendix B's subgroup tables
  show smaller Oracle→Seq gaps (2.0–9.9 points) that the paper does not
  reconcile with the 22.4-point headline (L20).
- **Pre-interruption display visibility, not compact return cues, drove one classic resumption result.**
  In Altmann and Trafton's randomized visual resource-allocation experiments (96
  undergraduates, 24 per warning duration), interruptions doubled time to the
  first action (3.8 s resumption lag vs. 1.9 s baseline, `p<.0001` in each
  experiment) (L21). Keeping the entire primary display visible during a warning
  before the secondary task reduced resumption lag reliably only at an 8-second
  warning (`F(1,22)=5.7, p<.03`; 6 s `p=.056`; 2 s and 4 s `F<1`; omnibus cue
  `F(1,88)=3.6, p=.060`; cue × duration `p>.25`), while active-window and cursor
  return cues were deliberately removed and no compact note or summary cue was
  tested (L21).

### Scientific research agendas, periodic reflection and lab notebooks

- **Joint commitment enforcement and periodic meta-reflection aided open-ended rediscovery on one task.**
  Station ran 300-tick multi-agent research sessions (six agents from three
  model families, text/code workspace, three seeds per rediscovery task) and
  recovered 62.7 ± 2.8% equal-weight criteria across three tasks versus 14.4%–20.6%
  for baselines (at unmatched token budgets) (L24). On the emergent-planning
  task, jointly removing the Supervisor (enforcing a 60-tick commitment) and
  Periodic Meta-Reflection (three GPT-5.5 reflection turns every 50 ticks)
  reduced criteria recovery from 75.8% to 57.9% and mean project duration from
  67.0 to 55.5 ticks (L24). Individual components were not ablated separately,
  myopic choices persisted (18/24 non-overlapping proposals rated 1–2/5 by an
  oracle author; RNN nonlinear-dynamics recovery fell from 25.9% at tick 100 to
  7.4% at tick 300), and exploratory findings required human screening (L24).
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
- **A biomedical ELN pilot showed preference for flexible search over rigid templates without post-rollout retention data.**
  In a three-month selection pilot (28 volunteers across eight labs, plus an
  80-student two-day workshop), scientists rated OneNote highest on technical
  criteria (39/42 vs. 23/42 for structured Elements), unanimously preferred
  OneNote after discussion (69% among students) and 88% endorsed possible paper
  replacement (L25). However, the study reports no post-implementation adoption
  or abandonment rates, unequal tool exposure prevented clean comparison (17
  OneNote-only, 5 Elements-only, 6 both), and the authors judged tablets
  unsuitable for replacing daily bench scrap paper (L25).

### Human-factors negative results: automation bias, alarm fatigue and structured debiasing

- **Decision aids reliably induce omission and commission errors, especially when usually accurate.**
  Across 40 studies covering 17 experimental tasks (median sample 30, range
  5–181; reviewer verification-complexity ICC 0.763), automation bias appeared
  in 25 of 31 omission studies (81%) and 21 of 23 commission studies (91%),
  though only 9 of 40 reported significance tests against manual control (four
  omission, four commission, one null) and no pooled error rates were computed
  (L27). Consistently high aid accuracy produced *more* bias errors than
  alternating accuracy; bias appeared across all complexity levels under
  multitasking and at medium–high complexity in rated single tasks; and
  performance feedback plus three forms of training showed no significant
  reduction, with accountability helping novices only mildly (L27).
- **High nuisance-alarm volume burdens operators, though causal missed-event rates remain unquantified in the review.**
  A review of seven ICU nursing studies (389 nurses: four HTF surveys totaling
  308 respondents, one 48-nurse survey and two interview studies) ranked
  frequent false alarms reducing attention first among obstacles (mean rank 2.84
  on a 1–9 scale), with 93% of one 48-nurse sample believing fatigue can lead to
  silencing or ignoring alarms (L28). Only one included study directly audited
  alarms (63.8% false of 2,184 alarms in 48 hours); the often-quoted 85%–99%
  non-actionable range and 80 US deaths are background citations without
  exposure denominators, and none of the seven studies estimates a causal
  missed-event rate (L28).
- **A formal competing-hypotheses matrix did not beat a simpler falsificationist control.**
  In a preregistered 2×3 online experiment (`N=159` psychologists and students
  evaluating one ambiguous case under defense, prosecution or court retention),
  Analysis of Competing Hypotheses (ACH) showed no significant reduction in
  adversarial allegiance relative to an active German-standard control that
  already considered alternatives—neither on credibility (`F(1,153)=.21, p=.649`;
  interaction `p=.328`) nor on evidence score (`F(1,153)=1.79, p=.183`; printed
  interaction `F(2,153)=.03, p=.804`, internally inconsistent with recalculated
  `p≈.970`) (L29). Retaining party shifted evidence selection (`p=.047`), and
  all 11 evidence-score outliers occurred in the ACH arm (descriptive only) (L29).

## What surprised us and what full reading corrected

The rightmost column records what the primary texts actually support after
checking initial Phase 1 claims from abstracts, snippets or prior expectations.

| Source | Initial claim or expectation | What full reading supports |
| --- | --- | --- |
| Evaluating `AGENTS.md` (L02) | Context files cut success, raise cost >20%, and minimal non-standard rules help. | Cost rose 20% (SWE-bench Lite) and 23% (CTXbench) for generated files; resolution drops were non-significant (`p=.87/.37`), developer files gained +2.4 pp (`p=.21` vs. none, `.038` vs. generated), and **no arm isolated minimal non-standard rules**. |
| DreamBench-SWE (L03) | Curated typed-plus-raw memory improves over raw events across sessions. | In preregistered v2.1, verbatim (45.6%) and hybrid (46.1%) were nearly identical while hybrid used ~79× tokens and 12,655 judge calls; both registered mechanism contrasts failed gates (`p=1`), and in v2 hybrid trailed verbatim on staleness (8/21 vs. 13/21). |
| StateMemBench (L04) | Structured state tracking and dependency propagation consistently beat raw transcripts. | Answer-time tracing beat transcript-matched controls on a 60-probe slice (+15.0 to +31.7 pp) but shifted LongMemEval DeepSeek by −5 to +5 pp, and **removing dependency propagation raised full StateMem accuracy (0.363→0.373)** because propagation hurt long anti-traps by 12.5 pp (L04). |
| ESAA (L05) | Two successful event-sourced SE case studies prove append-before-effect durability. | No baseline or ablation exists; case study 2 was a partial snapshot (**31/50 tasks done, 62%**), §3.2 and §4.2 contradict each other on log-before-write order, and replay cannot detect silent off-screen world mutation. |
| Outdated Code References (L06) | Most repos have stale docs that stay wrong for years, validated by precision/recall. | Only the most-starred *historical* cohort exceeded 50% (82.3%; current flags were 28.9% and 5.4%); years reflect age at inspection while recoverable time-to-fix covers one month; **precision and recall were unmeasured** (4/15 positive, 4/15 false-positive outreach replies). |
| Living Systematic Reviews (L07) | Provides explicit update triggers and governance for retiring reviews. | Initial PMCID (`PMC3928254`) was an unrelated trout RNA-seq paper. True *PLoS Medicine* text is conceptual with three qualitative publication tiers, **no quantitative triggers**, and **no review-retirement rule** in the available prose (Table 1 missing). |
| SwarmWorld (L11) | Stigmergy alone drives independent technology reuse without explicit culture. | First-encounter "95% physical" counts mere observation, every shared arm kept private memory and structured state, and at 3,200 ticks **no explicit culture beat full culture on validated inventions (7.00 vs. 5.75)** while isolated search built the single strongest artifact. |
| Emergent Collective Memory (L12) | Environmental traces fail completely in sparse grids and beat memory cleanly above a threshold. | Traces reached **90.1% exploration** and collected food in sparse grids; dense wins held only on composite score (trailing on food), and prose/table mismatches plus a 10× division error in Eq. 34 (`0.20/0.0875 ≈ 0.23` vs. `2.286`) undermine the crossover claim. |
| Factorio Learning Environment (L13) | Demonstrates screenshot-level off-screen automation failures in frontier models. | Agents used a **typed Python REPL** with `get_entities(radius=1000)` and `<STALE_ENTITY_DATA_OMITTED>` masking—not screenshots; off-screen duration was not isolated from query-scoped spatial debugging. |
| Scrub-Jays Caching (L14) | Establishes a natural elapsed-time threshold where birds abandon spoiled caches. | Degradation was experimenter-manipulated across trials (4 h / 100 h and 2-day schedules); **no natural spoilage cutoff** was tested, and memory-mediated reinforcement remains an open alternative to prospective planning. |
| NightWatch (L17) | Strictly screenshot-only watcher with 0.5% false interrupts. | Actors retained trajectory/action text (and web observation text); **no online false-interrupt rate is reported** (1/201 = 0.5% is an offline premature-wake check at 0.3 s); DynaCU Qwen stayed flat (34.7%→34.7%), and the watcher sees only the visible screen (L17). |
| MAGE (L18) | Prunes/deletes flawed branches from an execution-state tree. | `Revise` removes summaries from the active view while **retaining failed branches and feedback as siblings**; permanent deletion is refuted, repeat counts are unreported, and external side-effect undo is unspecified. |
| Multi-step SWE (L19) & ChainSWE (L20) | Multi-step SWE shows up to 70% degradation as chains lengthen; ChainSWE tests whether chat loss drives failure. | The 70% same-position loss belongs to **ChainSWE** (at bug 3 under summarization/delegation), not Multi-step SWE (which lacks a reference-prefix control); in ChainSWE, carrying full chat added **+0.4 points** overall against a **−22.4-point** penalty from prior bad edits. |
| Task Interruption (L21) | Compact resumption cues measurably cut post-interruption lag. | The intervention kept the **entire primary display visible before interruption** (significant only at 8 s warning, `p<.03`; omnibus `p=.060`), deliberately removed return cues, and tested no compact note or summary cue. |
| AutoSci (L22) & Bisht et al. (L23) | AutoSci validates `SciMem`; Bisht et al. show 68% ignored evidence / 26% revision empirically. | AutoSci has **zero memory ablation**; Bisht et al.'s own experiment measures single-turn hypothesis similarity, while the 68% and 26% figures are secondary citations from Ríos-García et al. |
| Station (L24) | Supervisor and Meta-Reflection each prevent myopic optimization. | Both were removed **jointly** on one task (75.8%→57.9%, `n=3` seeds, unmatched tokens, structured code workspace), leaving individual effects unablated, and myopic proposals still persisted. |
| Biomedical ELN (L25) | Quantifies post-rollout ELN adoption, abandonment and workarounds. | Reports a **three-month selection pilot** preferring flexible OneNote over structured Elements; **post-rollout adoption and abandonment rates are absent**, and daily bench scrap paper remained unreplaced. |
| SAGA in CivRealm (L26) | Matches token cost and isolates selective retrieval for long-horizon strategy. | Uses same-turn structured FreeCiv queries (`<10 ms` is CPU graph build only); overall Score vs. CoS/HIMA was non-significant (`p=.064/.096`), **total tokens exceeded CoS (367k vs. 281k)** (27% saving was output-only), and retrieval was not matched-cost isolated. |
| Automation Bias (L27), Alarm Fatigue (L28) & ACH (L29) | Reviews give sharp error-rate / missed-event curves; ACH debiasing is well-supported or backfires. | L27 counts positive studies without pooled error rates (high accuracy *worsened* bias); L28's 85%–99% and 80 deaths are background citations with no causal missed-event rate; L29 found **no significant ACH benefit** over a simpler falsificationist control (not proven worsening) and contains a printed `F`/`p` inconsistency. |

## What this implies here

The points below are **engineering inferences** for Enactive's open memory
questions—not owner decisions. Each maps directly to `#1020`–`#1027` and to the
boundary between built-in game tracking, external curated memory and active
re-observation.

- **State explicit observation-over-memory precedence (`#1020`, `#1024`, `#1025`).**
  L01 shows that an agent can spot a conflict between live reality and an
  external note yet still obey the stale note unless precedence is explicit, and
  L27 shows that high historical reliability of an aid *increases* uncritical
  compliance. Any memory briefing or curator note presented to the player should
  carry explicit precedence for fresh player-visible observation over stored
  claims, and tests should check whether the player's *action* follows fresh
  observation rather than merely whether its prose notes the discrepancy.
- **Separate three distinct tracking layers instead of collapsing them into external memory (`#1020`, `#1024`, `#1026`).**
  Across `L08`, `L09`, `L10`, `L11`, `L13`, `L15`, `L17` and `L26`, three
  mechanisms play different roles and fail differently:
  1. *Built-in game and environmental state* (in-game map notes, zones,
     inventories, quest logs, visible landmarks) is cheap to consult when
     co-located with live HUD cues (L09, L10) and avoids duplicate external
     prose that drifts (L02, L06), but can still go stale when the player has
     not revisited an off-screen tile or resource (L12, L13).
  2. *External curated memory* is best reserved for cross-session, non-HUD or
     reasoned provenance—what was observed where and when, why a decision was
     taken, and which prior branches failed without deleting their diagnostic
     record (L03, L10, L14, L18)—kept compact and flexible rather than bloated
     with broad overviews or rigid low-adoption forms (L02, L25, L29).
  3. *Active re-observation* (spending turns/actions to open a menu, walk back
     to check a cache or verify a prerequisite) is the only mechanism that
     detects silent off-screen change (L05, L08, L15, L17, L19, L20). Replaying
     recorded logs or watching the visible screen cannot substitute for it.
- **Treat verbatim evidence as the baseline to beat, and guard derived propagation (`#1020`, `#1024`, `#1025`).**
  L03's preregistered audit and L02's cost penalty show that expensive write-time
  structuring and broad context files are not automatically better than compact,
  reachable verbatim observations. L04 shows that automatic dependency
  propagation can actively harm accuracy when an earlier fact stays valid, and
  L06/L07 suggest lightweight staleness cues (such as recording last-verified
  time separately from conclusion revision, or flagging disappeared referents
  for recheck rather than silent deletion).
- **Verify workspace/world prerequisites across cuts instead of trusting handoff prose (`#1026`, `#1021`, `#1022`).**
  L19 and L20 show that inherited broken state and optimistic completion reports
  ("done" without independent verification) dominate multi-session failure far
  more than dropped chat transcripts, while L18 supports separating the active
  working path from archived failed attempts. Working state carried across a
  context cut should separate *verified* prerequisites from unverified intentions
  and retain failed-attempt hints outside the active directive; L21 suggests
  testing whether a brief pre-cut grounding pass over the live screen helps
  resumption, without assuming a compact note alone closes resumption cost.
- **Price reminders, alarms and periodic review against noise and distraction (`#1023`, `#1024`, `#1027`).**
  L24 gives moderate support for testing periodic reflection against myopic
  local loops, and L26 supports on-demand selective queries over dumping full
  state, but neither isolates screenshot-only play or matched token cost. L27
  and L28 warn that frequent non-actionable reminders or over-trusted advisory
  prompts can degrade attention or induce omission/commission errors; any
  proactive reminder or separate reviewer/strategist should therefore be
  evaluated on false-alarm rate, missed actionable changes and total cost, not
  prompt volume or average reward alone.

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

“Reading reports” counts independent reports on the extracted primary text from
distinct model families; all 29 works have two reading reports plus one
reconciled digest. Read limits are stated above and in individual rows.

<!-- sources-table -->
| ID | Source and version read | Main result in the text read | Strength | Reading reports |
| --- | --- | --- | --- | ---: |
| L01 | [Stale Instruction Files Override the Code in Coding Agents](https://arxiv.org/abs/2610.30571v1), arXiv v1, 22 Oct 2026 | Agents followed stale instruction files in 90.1% (649/720) of choices vs. 4.2% live code; Claude Code named the conflict in 79/80 runs yet followed the file on 86.2% of choices in those runs; one precedence-and-reporting sentence raised code-following to 91.4% (658/720) and test passes 89.4%→100% (§§5.1–5.5). Not read or lost in extraction: Figs. 1–8 captions only. | Strong | 2 |
| L02 | [Evaluating AGENTS.md](https://arxiv.org/abs/2602.11988v3), arXiv v3, 29 Sep 2026 | LLM-generated context files lowered resolution in 5/8 cells (−0.5/−2.0 pp, p=.87/.37) while raising cost +20%/+23% (+2.45/+3.92 steps); developer files gained +2.4 pp on CTXbench (p=.21 vs. none, p=.038 vs. generated) at ≤19% extra cost (§4.2, Tables 3–6). Not read or lost in extraction: Figs. 1–15 captions only; Appendix E prompts absent. | Moderate | 2 |
| L03 | [DreamBench-SWE](https://arxiv.org/abs/2608.20664v1), arXiv v1, 21 Aug 2026 | Preregistered v2.1 (180 cells/arm): no memory 21/180 (.1167), verbatim 82/180 (.4556), typed+raw hybrid 83/180 (.4611, ~79× tokens and 12,655 judge calls vs. 0), hosted literal 97/180 (.5389); registered mechanism contrasts failed gates (p=1); v2 hybrid trailed verbatim on staleness (8/21 vs. 13/21) (§6.6, Tables 7–13, 20). Not read or lost in extraction: Figs. 1–2 captions only; external manifests/records unread. | Moderate | 2 |
| L04 | [Can Agent Memory Systems Track Evolving State? (StateMemBench)](https://arxiv.org/abs/2608.19652v1), arXiv v1, 20 Aug 2026 | Answer-time tracing beat transcript-matched generic control by +15.0 to +31.7 pp on a 60-probe slice (p≤.04), shifted LongMemEval DeepSeek −5 to +5 pp; full StateMem scored .363/.233 across 322 probes (49.1%/64.3% drift) and removing dependency propagation raised DeepSeek accuracy to .373 (§§6.1–6.4, Tables 3–6, 14–15). Not read or lost in extraction: Figs. 1–2, boxed dialogues and Appendix F.1 prompt absent. | Moderate | 2 |
| L05 | [ESAA: Event Sourcing for Autonomous Agents](https://arxiv.org/abs/2602.23193v1), arXiv v1, 26 Feb 2026 | Two uncontrolled single-run SE case studies (9 tasks/49 events; 86 events with 31/50 tasks done, 62%) verified replay hashes; no baseline or ablation; §3.2 vs. §4.2 contradict on log-before-write order (§§3–6, Tables 2, 4). Not read or lost in extraction: Fig. 1 caption only; Appendix E shows excerpt only. | Weak | 2 |
| L06 | [Detecting Outdated Code Element References](https://arxiv.org/abs/2212.01479v1), arXiv v1, 2 Dec 2022 | Flagged stale code refs in 28.9% (265/918) top-starred and 5.4% (101/1,879) Google projects (mean age 4.7/4.2 yrs; ever-flagged 82.3%/29.7%); ~55%/45% of fixed positive-lag flags survived >1 month; precision/recall unmeasured, 15-project outreach drew 4 positive, 4 false-positive, 7 nonresponses, 5/19 fixes (§§5.1–5.4, Table 6). Not read or lost in extraction: Figs. 1–15 captions only; external appendix unread. | Moderate | 2 |
| L07 | [Living Systematic Reviews](https://doi.org/10.1371/journal.pmed.1001603), PLoS Medicine 11(2), 18 Feb 2014 | Conceptual publishing workflow separating last-search-date updates, modest editorial updates and rapid peer review; cites 2.5–6.5 yr neurotrauma incorporation lags and 50%–90%+ screening workload reductions; no controlled trial, quantitative triggers or retirement rule in available prose. Not read or lost in extraction: Figs. 1–2 and Table 1 cells missing. | Weak | 2 |
| L08 | [Inventory Record Inaccuracy and Cycle Counting](https://doi.org/10.1590/0103-6513.20220077), Production 33, 2023 | 360-day Stella simulation across five WERC classes: zero counting lost 45.80% (MO) to 4.60% (BIC) annual demand; daily cycle counts restored class only once capacity exceeded error generation (5 counters left MO/DIS worse than start; MO needed 10–14/15+) (§§4–5, Tables 3–4). Not read or lost in extraction: Figs. 1–3 missing; Appendix B equations displaced. | Moderate | 2 |
| L09 | [On Distinguishing Epistemic from Pragmatic Action](https://adrenaline.ucsd.edu/kirsh/Articles/CogsciJournal/DistinguishingEpi_prag.pdf), Cognitive Science 18, 1994 | Tetris keystroke logs show information-seeking wall-checks before ~1% of drops at higher board heights across intermediate (13.18 vs. 19.04), advanced (13.69 vs. 19.33) and expert (15.65 vs. 20.05) players (α=.05); causal cognitive-load reduction during play was not directly measured (Table 1). Not read or lost in extraction: OCR damaged Figs. 1–17 and piece glyphs. | Moderate | 2 |
| L10 | [How a Cockpit Remembers Its Speeds](https://pages.ucsd.edu/~johnson/COGS102B/Hutchins95.pdf), undated UCSD draft manuscript | Stylized MD-80 approach account (drawing on 100+ observer flights across 6 years) showing speed cards and movable markers set 25–30 min pre-landing turn recall into perceptual comparison beside live needles; no experimental arms or error-rate effect size. Not read or lost in extraction: Table 1 missing; Figs. 1–4 layout degraded; published DOI text unverified. | Moderate | 2 |
| L11 | [SwarmWorld](https://arxiv.org/abs/2608.26081v1), arXiv v1, 26 Aug 2026 | Four-seed BioFoundry runs (all shared arms kept structured local state and private memory): 99.3%/96.9% artifact reuse and ~95% first-encounter via physical observation; at 3,200 ticks, no explicit culture beat full culture on validated inventions (7.00 vs. 5.75) while isolated search built the strongest single artifact (0.3488 vs. 0.2380) (§§2.2–2.9). Not read or lost in extraction: plot-only values, §§S3.1–S3.4 graphics and external tables absent. | Moderate | 2 |
| L12 | [Emergent Collective Memory](https://arxiv.org/abs/2512.10166v1), arXiv v1, 10 Dec 2025 | Hand-coded Mesa foraging grids: traces alone reached 90.1% exploration (refuting total failure) and beat a memory comparator on dense large-grid composite score (103.64 vs. 77.11 at 625 agents) while trailing on food (19.71 vs. 22.62); prose/table mismatches and Eq. 34 arithmetic error (`0.20/0.0875 ≈ 0.23`) weaken crossover claims (§6, Tables 1–3, App. A.6). Not read or lost in extraction: Figs. 1–4 missing; some math signs corrupted. | Weak | 2 |
| L13 | [Factorio Learning Environment](https://arxiv.org/abs/2503.09617v1), arXiv v1, 6 Mar 2025 | Six models via typed Python REPL (`get_entities(radius=1000)`, `<STALE_ENTITY_DATA_OMITTED>` masking—not screenshots): Claude 3.5 Sonnet peaked at 21.9±1.3% lab success; 56% step error rate even in passing lab runs; looping (78 repeated calls; 234 reset appeals) (§4, Tables 1–2, Apps. F–G). Not read or lost in extraction: plotted open-play curves, maps and external manual unavailable. | Moderate | 2 |
| L14 | [Prospective Cognition of Food Caching by Western Scrub-Jays](https://doi.org/10.3819/ccbr.2008.10001), vol. 1, 2006 copyright | Review of controlled cage trials: selective recovery after afternoon/1-week delays, reduced worm caching after 2–4 trials of manipulated degradation (4 h/100 h or 2-day intervals), experience-dependent re-caching (~20%–25% still placed in risky sites); no natural spoilage cutoff tested. Not read or lost in extraction: interleaved PDF columns, missing graphics and bar heights. | Moderate | 2 |
| L15 | [Nonlinear POMDPs for Active State Tracking with Sensing Costs](https://arxiv.org/abs/1405.5892v1), arXiv v1, 22 May 2014 | Known Markov/Gaussian model: belief-dependent myopic sensing saved 60% energy vs. equal allocation at matched accuracy (12-sample cap, 4% error reported in abstract), CE–WWLB saved 7%, exact DP intractable above 2 samples; Corollary 3 covers one-step costs under two-state symmetry (§VI). Not read or lost in extraction: Figs. 1–8 captions only; several equations malformed. | Moderate | 2 |
| L16 | [OCMDP: Observation-Constrained MDP](https://arxiv.org/abs/2411.07087v4), arXiv v4, 23 Jan 2025 | Model-free decoupled observation/control learner reported +71%–75% return and −50% observation cost on two toy simulations (Diagnostic Chain, HeartPole); no seed counts, price sweeps or joint-training ablation, and latent-state supervision is inconsistent between Alg. 1 and prose (§§4–5). Not read or lost in extraction: Figs. 1–6 captions only; no numerical tables; malformed theorem macros. | Weak | 2 |
| L17 | [Don't Sleep, Keep Watch (NightWatch)](https://arxiv.org/abs/2611.28947v1), arXiv v1, 21 Nov 2026 | Frozen 0.8B 10 Hz visual watcher cut OSWorld non-reasoning time 33%/41% (p=.026/.016) and stale steps while raising avg@3 66.3%→68.0% and 56.3%→58.7%; DynaCU rose 39.5%→44.2% (MiMo) and stayed flat 34.7%→34.7% (Qwen); removing void raised target mismatch 3.6%→15.9%; visible screen only, no online false-interrupt rate (Tables 1–3). Not read or lost in extraction: Figs. 1–5 panels and three Appendix B examples missing. | Strong | 2 |
| L18 | [Beyond Semantic Organization (MAGE)](https://arxiv.org/abs/2606.06090v2), arXiv v2, 15 Oct 2026 | Execution-state tree gained +7.8 pp success over Full Context on MemoryArena with 55.1% fewer tokens (Qwen3.6-27B) and improved DeepPlanning; removing `Compress`, `Maintain` or `Revise` lowered scores; `Revise` keeps failed branches as sibling hints rather than deleting them; repeat counts and side-effect undo unreported (§4, Alg. 1, Tables 3–8). Not read or lost in extraction: Figs. 1–4 graphics and Appendix B.1 prompts absent. | Moderate | 2 |
| L19 | [Multi-step SWE](https://arxiv.org/abs/2611.07166v1), arXiv v1, 4 Nov 2026 | 69 tasks (5–15 steps, 4 rollouts × 9 models): Claude Opus 5.5 solved 18.5% of rollouts (31.9% of tasks ≥1×); 38/69 tasks unsolved by all models; within-task on-track rate fell 34.9%→9.0%; 57% of unqualified completion reports failed hidden verification; no reference-prefix control (§§3.2–3.3, Table 5). Not read or lost in extraction: Figs. 1–4 captions only. | Moderate | 2 |
| L20 | [ChainSWE](https://arxiv.org/abs/2607.02606v2), arXiv v2, 1 Sep 2026 | 100 chains (304 bugs, 7 models × 3 harnesses): per-bug accuracy fell 58.9% Oracle → 36.5% Seq (−59% to −70% at bug 3) → 36.9% Seq+Mem (+0.4 pp from chat carryover; only GPT-5.5 gained materially, 42.2%→46.8%); under-edits outnumbered over-edits ~9:1; Appendix B subgroup gaps (2.0–9.9 pp) unreconciled (§5, Tables 2–4, 10–11). Not read or lost in extraction: Figs. 1–4 graphics; App. C patches and App. D prompts absent. | Strong | 2 |
| L21 | [Task Interruption: Resumption Lag and the Role of Cues](https://escholarship.org/uc/item/18b4r661), CogSci 26, 2004 | Randomized visual-task experiments (N=96): resumption lag 3.8 s vs. 1.9 s baseline (p<.0001); keeping the full primary display visible *before* interruption reduced lag significantly only at 8 s warning (F(1,22)=5.7, p<.03; omnibus p=.060, interaction p>.25); return cues removed, no compact note tested (pp. 44–48). Not read or lost in extraction: interleaved PDF columns; Figs. 2–7 missing. | Moderate | 2 |
| L22 | [AutoSci](https://arxiv.org/abs/2605.31468v1), arXiv v1, 29 May 2026 | Separates schema-governed Markdown memory (`SciMem`) from workflow in two case studies (157 GPU kernels, 1.18× non-degenerate speedup; biomedical perturbations within noise); zero memory-removal or alternative-memory ablation (§7). Not read or lost in extraction: Figs. 1–11 graphics missing; some raw TeX in flattened tables. | Anecdote | 2 |
| L23 | [Agentic AI Scientists Are Not Built For Autonomous Scientific Discovery](https://arxiv.org/abs/2605.08956v3), arXiv v3, 6 Nov 2026 | Position paper proposing persistent mutable beliefs and shifting objectives; own experiment measures single-turn hypothesis cosine similarity across 12 models (24,480 hypotheses; cross-provider 0.64–0.69 vs. 0.30–0.39 across papers); cited 68% ignored-evidence / 26% revision rates come from secondary work (§5, Table 3). Not read or lost in extraction: Figs. 1–6 graphics and App. A.7 prompt absent. | Weak | 2 |
| L24 | [Evidence from Station](https://arxiv.org/abs/2610.08927v1), arXiv v1, 6 Oct 2026 | 300-tick multi-agent scientific discovery (3 seeds/task, unmatched tokens): 62.7±2.8% criteria recovery vs. 14.4%–20.6% baselines; jointly removing 60-tick Supervisor commitment and 50-tick Meta-Reflection cut planning recovery 75.8%→57.9% and project duration 67.0→55.5 ticks; components unablated individually (§6, Tables 3–4). Not read or lost in extraction: Figs. 1–5 graphics missing; one reader sampled appendices. | Moderate | 2 |
| L25 | [Implementation of an ELN in a Biomedical Research Institute](https://doi.org/10.1371/journal.pone.0160428), PLoS ONE 11(8), 1 Aug 2016 | Three-month selection pilot (28 volunteers, plus 80-student workshop): flexible OneNote scored 39/42 vs. structured Elements 23/42 and won unanimous lab preference (69% students; 88% endorsed possible paper replacement), while bench scrap paper remained unreplaced; no post-rollout adoption or abandonment data. Not read or lost in extraction: Table 1 matrix and Figs. 1–3 missing. | Moderate | 2 |
| L26 | [SAGA: Scene-Aware, Goal-Evolving Agents](https://arxiv.org/abs/2606.29932v4), arXiv v4, 21 Jul 2026 | CivRealm/FreeCiv 2.6 (150 turns, seed 2025, 10 games/arm, structured same-turn state): SAGA Score 60.7±14.0 vs. CoS 47.8±20.3 (p=.064) and HIMA 43.7±22.3 (p=.096); clear Buildings gain (16.3 vs. ≤7.5); removing query tools cut Score 49% (to 30.9); total tokens exceeded CoS (367k vs. 281k; 27% saving output-only) (Tables 1–2, 6, 8). Not read or lost in extraction: Figs. 1–5 captions only; one App. N example missing. | Moderate | 2 |
| L27 | [Automation Bias and Verification Complexity](https://doi.org/10.1093/jamia/ocw105), JAMIA 24(2), Mar 2017 (online Aug 2016) | Systematic review of 40 studies (17 tasks; verification-complexity ICC .763): bias occurred in 25/31 omission (81%) and 21/23 commission (91%) studies, only 9/40 tested significance vs. manual; high aid accuracy increased bias; feedback and three training forms showed no significant reduction (Tables 1–2). Not read or lost in extraction: Fig. 1 and supplementary appendices A–B absent. | Moderate | 2 |
| L28 | [Impact of Alarm Fatigue on ICU Nurses](https://doi.org/10.3390/ijerph17228409), IJERPH 17(22), 13 Nov 2020 | Review of 7 studies (389 nurses; 4 HTF surveys = 308): frequent false alarms reducing attention ranked first (2.84/9); one alarm audit found 63.8% false of 2,184 alarms in 48 h; 85%–99% and 80 deaths are background citations, and no included study estimates causal missed-event rates (Tables 1–2). Not read or lost in extraction: Fig. 1 and study-level Oxford grades missing. | Weak | 2 |
| L29 | [Analysis of Competing Hypotheses and Adversarial Allegiance](https://doi.org/10.1371/journal.pone.0346891), PLoS One 21(4), 20 Apr 2026 | Preregistered 2×3 online trial (N=159): ACH did not significantly reduce allegiance bias vs. a falsificationist active control on credibility (p=.649; interaction p=.328) or evidence score (p=.183; printed F(2,153)=.03, p=.804 inconsistent with recalculated p≈.970); retaining party shifted evidence selection (p=.047). Not read or lost in extraction: Tables 1–3, Figs. 1–4 and external preregistration unread. | Moderate | 2 |
