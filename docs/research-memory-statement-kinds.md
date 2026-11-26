---
owner: lead
status: active
date: 2026-11-26
scope: 'Outside evidence from 79 works on what statements player memory can hold, who writes them, and how stale entries are found and retired'
review_trigger: 'The owner decides what the curator records beyond observations, what survives removal of earlier context or whether to add a separate long-horizon planner, or a study tests one of these questions in extended play'
---

# Research on what a player's memory should hold and who writes it

The search cutoff was **26 November 2026** (America/New_York). The curator can
record `strategy` claims and `inferred` evidence. Which supported statements
the curator should routinely write is open. The owner prioritized world facts
and deferred procedures and belief calculus. [Curator contract](contracts/curator.md#facts-curator-fact5) ·
[Owner decision](decisions/owner-decisions.md#world-memory-first)

The question arose in the [three-day campaign memory review (#1019)](https://github.com/CVX-Hull/enactive/issues/1019).
Related research covers [memory, ontology and oversight](research-curated-memory.md)
and [belief under conflict](research-belief-under-conflict.md).

## At a glance

- **Different statements need different support.** An outcome documents an
  occasion. A causal claim needs evidence for the link. A recommendation also
  needs a goal and conditions.
- **Average gains can coexist with failures on previously solved tasks** (S01).
  Some tests favored raw records, others distilled lessons or both (S07, S30,
  S59, S72). Procedures helped in some settings and hurt in others (S02, S74, S79).
- **Studies used several ways to preserve continuity.** A *context cut* removes
  earlier material from the player's active context. *Working state* is what
  the player needs to resume its task, such as progress, commitments and next
  steps. Results varied across tests of player notes, harness state and auxiliary
  writers (S12, S13, S61, S64).
- **The benefit of an Enactive strategist is open.** A *strategist* is a
  separate agent that sets or revises longer-horizon plans for the player.
  Planner gains varied with training, architecture and task (S23, S38).
- **The closest gameplay comparison ran for 24 hours** and tested bundled
  changes with an emulator-derived map (S16).

## Brief and method

**Questions**

- What should memory hold beyond observations?
- Who should write each kind of statement?
- How are stale or wrong entries found and retired?

**Search.** Three rounds ran on 26 November 2026. The first found nothing newer
than March 2026. The second searched April through November 2026 by date. Two
independent searches in the third round included proceedings and reviewer sites,
found about 25 further sources and confirmed nine snippet leads. Six of the nine
went into reading batches.

**Reading.** Each of 79 works was fetched as text. 66 have two reading reports
and 12 have three, each report from a different model family. One paper was read
in two versions and has five. Reports recorded comparisons, figures, limits and
checks of abstract claims. A separate reader reconciled each batch, accepting
agreed figures and consulting extracts for disagreements. Some digests relied
on the reports. The lead's review covered every digest. The seal covers the briefs, reports,
digests and claims tested. [Evidence seal](../data/evidence/memory-statement-kinds-research.sha256) ·
[Attempts ledger](../data/evaluation/coding-agent-attempts.jsonl)

**Read limits**

- Extraction dropped plots and sometimes lost or garbled tables, equations,
  prompts, examples, lists or footnotes. Some files had text recognition errors.
  Readers recovered figure values where captions, labels or prose supplied them.
- Some readings skipped references, detailed results or appendix material.
  Examples include *Generative Agents*, *Why Do Multi-Agent LLM Systems Fail?*,
  *JARVIS-1* and the appendix dumps in *Useful Memories Become Faulty* (S40–S42,
  S60). Some linked supplements and the primary studies summarized by *Handoffs*
  went unread (S49–S51). *The Utility Problem in Case-Based Reasoning* is a
  one-page abstract (S48).
- Three September 2026 submissions could not be fetched. *The Compliance Trap*
  bears on conflicting advice, *Auto-Dreamer* on offline consolidation of
  procedures, and *SEEM²* on revision of scoped facts and failure lessons.
- Three confirmed leads went unread. A second *MemForest* paper covers merging
  event memories (arXiv 2609.08273), a review covers externalization
  (arXiv 2604.08224), and *MineNPC-Task* concerns memory during human-agent co-play
  (arXiv 2601.05215).
- The reconciler assigned the strength labels and the lead checked them. Most
  are moderate or weak, often because runs were single or counts unreported.

## Kinds of statement

The lead proposes this vocabulary from *Instrumental Rationality*,
*Defeasible Reasoning*, *Epistemological Problems of Testimony* and *Knowledge How*
(S49, S50, S53, S54). The examples are illustrative.

| Kind | Example | What evidence can support | What the reader needs |
| --- | --- | --- | --- |
| Observation | “At 6:10 the battery showed 0%.” | The display reading. | The time. |
| Off-screen state | “The north toilet was empty on day 63.” | The last check. | Its date and whether the result still applies. |
| Observed outcome | “Water boiled over the fire with the battery flat.” | Success on this occasion. | The conditions. |
| Causal inference | “The fire supplied the heat that boiled the water.” | The link between the heat source and outcome. | The conditions and basis for inference. |
| Measure against a standard | “The oil supplies 14 days of food at 2,000 kcal per day.” | The inputs and calculation. | The standard. |
| Conditional recommendation | “To boil water with the battery flat, use the fire if there is fuel.” | Support for the method under those conditions. | The goal and conditions. |
| Directive, plan or goal | “Fish next.” | Evidence of feasibility and fit. | The goal, commitments and situation. |

- **Evidence can support a recommendation under a stated goal.** One success
  leaves causation and repeatability open. Other actions and their costs bear
  on the choice (S49).
- **Advice can stop applying while its evidence remains valid.** A changed goal
  or new equipment can make advice obsolete (S49, S50).
- **Stating and using a rule are distinct.** In BALROG an agent could say rotten
  food was dangerous and still ate it (S37).

## What the evidence says

### Stored lessons help and harm

- **WikiTrace measured gains and regressions.** Across eight suites, mean
  scores were 90.2 with lessons, sources and a prompt to consult them, 87.0 with
  lessons alone, and 79.5 without memory. Among tasks solved in a majority of
  three no-memory trials, failures ran at 4.5%, 6.5% and 9.7%, respectively. The
  last rate uses three additional trials. In a baseline audit of failures on
  tasks solved in all three initial no-memory trials, a judge linked 52% to a
  followed item and 20% to an item that was wrong (S01).
- **An add-all bank trailed a fixed bank.** In *How Memory Management Impacts LLM
  Agents*, adding every query and execution pair did worse for all four agents
  than a fixed bank of valid demonstrations (13.05% versus 16.75% for one).
  Admission using task ground truth improved results. Uncalibrated model judges
  often trailed the fixed bank (S34).
- **Two compaction tests illustrate losses.** In a Dynamic Cheatsheet trace
  reported by *Agentic Context Engineering*, rewriting 18,282 tokens to 122
  dropped accuracy from 66.7 to 57.1 versus a 63.7 baseline (S31, S32). In *The
  Compaction Cliff*, the Claude Code `/compact` prompt with Sonnet 4.6 retained
  53% of classifier-labelled constraints after one round and 10% after five (S65).

### Keeping the evidence

- **Disposable guidance led in seven of nine settings.** *More Memory, Worse
  Agents* averaged 59.9% for raw records and disposable guidance, 53.5% for raw
  records alone, 49.0% for persistent guidance and 49.3% for raw records with
  persistent guidance (S59).
- **Task-time briefing gains varied with training.** JitMem builds briefings
  from successful trajectories. Its trained curator led the strongest write-time
  baseline by 6.0–16.2 points on ALFWorld and 9.2–16.3 on WebShop across three
  executors. The largest gains compare trained JitMem and SkillOS with Qwen3-8B,
  where trained SkillOS beat untrained JitMem (S07). On simulated service tasks,
  prompted GPT-5.4 JitMem led ReasoningBank by 3.9 points across tasks and 3.0
  across equally weighted domains, with clear gains in one of three domains (S07).
- **Rewriting results varied by store.** At step 400 in *Useful Memories Become
  Faulty*, forced rewrites scored 43.2%, adding and deleting 64.0%, and raw
  trajectories 76.6%. Other comparisons in the paper include exceptions (S60).
  SimplEvo rewrote a bounded task-specific store. Hippo favored selective
  replacement in a cross-task bank (S04, S05). MemSIF gained by promoting facts
  when writing and recovering evidence when answering (S77).
- **Richer gameplay history helped in two comparisons.** PRO-LONG using GPT-5.6
  averaged 24.5% best progression over five NetHack episodes with a complete log
  versus 13.5% without it (S15). It still summarized plans. The value of a
  distilled store remains open. AgentOdyssey's long-context baseline beat its
  compressed and retrieval variants in all six games, with much higher token
  use and mostly single runs (S21).
- **Distilled guidance sometimes beat trajectories.** ReMe's 8-billion-parameter
  executor passed function-call tasks on at least one of four attempts at 65.77%
  with keypoints and 60.00% with trajectories (S72). *Environment-Probing Curation*
  scored 70% with indexed memory, 73% with probing and 61% with full trajectories
  prepended (S08). ExpeL scored 36% with insights, 31% with retrieved trajectories
  and 39% with both on HotpotQA. Its combined arm also led on ALFWorld (S30).
  MemP's combination scored 77.86% versus 74.29% for trajectories on ALFWorld (S79).
- **A governed reducer passed all obligations in a small pilot.** In *Always-On Agents*, three raw
  stores passed 7 of 15 obligations each. Extracted-fact stores that dropped
  governance metadata passed 4 and 3. A deterministic reducer applying governance
  rules passed all 15. Extracted facts with governance metadata went untested (S56).
- **Search led on synthetic questions requiring derived state.** In MemDerive,
  four memory systems scored 30% to 48% in one run with one answer model. Keyword
  search over session documents scored 58% (S67).

### Procedures with conditions and tests

- **Falsification probes reduced harmful updates.** *Falsification-Gated
  Self-Evolution* stored a precondition, proposed behavior, expected effect and
  verifier. Removing the probes while retaining other checks raised harmful
  committed updates from 3.6% to 10.6% (S02).
- **Hippo replaced conflicting conditional decisions.** At 400 tasks in one
  software repair task ordering, scores were 86% on revisited and 82% on unseen
  tasks, versus 72% and 66% with append-only memory (S05).
- **Transfer and direct use gave mixed results.** SimplEvo and MemP reported
  transfer to weaker models without run counts (S04, S79). AgenticSTS had uneven
  transfer in five-game probes. Skills won 6 of 10 games in each of three
  conditions, versus 3 without a scaffold and 4 with prompts alone. Adding
  episodes produced no further wins (S18).
- **Procedural memory could lower scores.** AdMem's procedural-only arm solved
  4–6 of 20 Jericho tasks across epochs, versus 8 for ReAct (S74). With GPT-4o,
  MemP raised ALFWorld success from 42.14% to 77.86% while lowering TravelPlanner's
  hard-constraint score from 12.88 to 9.76 (S79).

### Lessons from failure

- **Recovery and transfer differed.** In *Repair failures, struggle to
  generalize*, failure-only updates partly repaired tasks with limited or
  negative held-out gains across three frameworks and ten models. The main
  recovery test lacked matched memory-free retries. A separate test compared
  full, manually verified and no experience. Filtering modestly improved
  recovery in all five configurations across two models and two frameworks.
  Held-out scores stayed at or below no-experience levels in four. Successful
  trajectories transferred better in tests with one model, two frameworks and
  separately selected task streams (S06).
- **ReasoningBank gained on one subset.** Including failures raised shopping
  success from 46.5% to 49.7%. The workflow baseline fell from 44.4% to 42.2% (S33).

### State and staleness

- **Transient screen state went stale in one case report.** In *The components
  of agent memory*, one model recorded visible money and map position, wrote
  413 files and earned one badge. Another wrote nine files plus a dashboard
  and earned four. Both model and note style varied across the two runs (S24).
- **Some systems preserve superseded values.** On STALE's synthetic implicit conflicts,
  CUPMem scored 68.0%, versus 8.7% for GPT-4o-mini with truncated context (S69).
  CUPMem tracks active, stale and unresolved facts (S69). DISCERN tracks when
  a value applied and when it was learned (S70). On hard questions in the pilot
  of *When Does Memory Help?*, structured overwriting beat embedding retrieval
  (S68).
- **Auditing the text map reduced deaths relative to unchecked memory.** In *When Memory
  Lies*, GPT-4o's death rate in the text test with clustered map changes was
  74.4% with unchecked memory, 31.6% with auditing and 28.0% without memory
  (S66). With screenshots, audit quality fell sharply for three of four models.
  F1, which combines precision and recall, ranged from 0.067 to 0.887 (S66).

### Finding and retiring stale entries

- **Implicit changes were harder to catch.** MemDerive's stores refreshed
  82.4% of explicit changes and 41.1% of implicit ones (S67). A change may
  require rechecking dependent statements or deferring advice on unresolved
  facts. CUPMem tracked those conflicts and scored 32% on direct advice and
  43% on indirect advice (S69).
- **Deletion had mixed effects.** With ground-truth evaluation in *How Memory
  Management Impacts LLM Agents*, outcome-based deletion raised one agent's
  success from 38.67% to 42.06% and lowered the regression-task agent's success
  from 70.95% to 69.80%. With a coarse evaluator, driving success fell from
  36.92% to 34.00% (S34). *Epistemics of Agent Memory* missed its full criterion.
  It initially deleted needed records. Its revised gate averaged 0.61 deletions
  per seed, down from about 30 (S11). Retrieval frequency alone can miss records
  that matter to later decisions.
- **Selective retention helped in some configurations.** ReMe's utility-based
  deletion raised best-of-four function-call success for its 8-billion-parameter
  executor from 64.66% to 68.00%. Mean success per attempt rose from 45.00% to
  45.17% (S72). In *How Much Should an Agent Remember?*, one model scored 55.4%
  with about 29 retrieved guidelines versus 51.2% with all 199. The 55.4% is a
  two-run mean for a configuration selected on the test set. Another model
  improved from 79.8% with none to 89.3% with all 191 of its guidelines (S73).

### Working state across a context reset

- **Task-state results varied by benchmark.** In *How Strongly Should Task State
  Influence an LLM Agent?*, a self-written ledger beat a shown checklist on
  one benchmark. On the prospective-memory benchmark, showing the record beat
  the ledger and every enforcement variant. Blocking invalid airline writes
  raised single-attempt success from 0.39 to 0.54 for a model that often attempted
  them. Results were inconclusive for a model with few catchable errors (S12).
- **A commitment store changed an internal measure.** In *The LLM Proposes, the
  Executive Disposes*, removing the store raised abandonment from 0.00 to 1.00
  against an internal reference. It was defined for two of three removal seeds.
  No level was completed in 52 runs (S13).
- **HyMem carried structured notes across refreshes.** An auxiliary writer
  recorded milestones, verified facts, objectives and next steps. Table 2 reports that
  removing memory management cost DeepSeek-V4 9.0 points on BrowseComp-Plus
  and Qwen3-32B 18.6 on GAIA (S64). The paper's tables disagree (S64).
- **AutoMem improved a file-memory scaffold.** Offline schema and code revisions
  reached about two to four times initial progression in Crafter, MiniHack and
  NetHack. Specialist training added a smaller gain. Revisions bundled actor
  notes, harness-synced status and inventory, and game-specific guards. File
  types were untested individually, and memory reset between episodes (S61).
- **Continual Harness is the closest gameplay comparison.** In 24-hour Pokémon
  runs, a separate refiner could edit memory, skills, subagents and prompts
  during play. Most authored entries went unused. One player believed a tool was working
  while repeating a failing call 842 times. The harness supplied an emulator-derived
  map. The comparisons measure the bundle, and Red results conflict within the
  paper (S16).

### Who writes memory

- **Two bundles beat memory-free controls.** *Environment-Probing Curation*
  used a sole post-task writer. Indexed and probed memory scored 70% and 73%
  with overlapping intervals, versus 39% without memory. *Proactive Memory
  Agent* added a parallel writer and reminders, gaining 8.3 and 6.8 points for
  one actor with one attempt per task and condition (S08, S09).
- **A skill bank could hurt an unadapted actor.** COS-PLAY trained actor and
  writer together. Giving the final bank to an actor with only supervised
  training lowered mean single-player reward from 409.5 without skills to 359.5 (S62).
- **An agent's own notes can help.** Selected self-written guidelines helped
  on AppWorld (S73). A transcript check corrected a player's wrong location
  note in *The components of agent memory* (S24).
- **Writer effects varied.** In *Can LLM Agents Organize Their Own Memory?*,
  three writers scored 92.34%, 91.95% and 92.01% with one dialogue reader.
  The paper reports one led with most readers (S75). With ReMe's executor
  fixed, a larger summarizer raised mean success per attempt from 44.50% to 47.83% and
  best-of-four success from 65.77% to 68.00% (S72). ExpeL's weaker insights
  writer scored 32.0% versus 39% on HotpotQA (S30).
- **The writer comparison remains open.** No study compares subsequent play
  after giving matched evidence to an actor and a separate writer.

### A separate strategist

- **Plan-and-Act's gains depended on training.** An untuned planner raised
  the base executor from 9.85% to 14.21% and lowered two trained executors
  from 36.36% and 36.97% to 17.16% and 23.63%. Targeted planner training
  reached 42.42% and 43.63%. Adding dynamic replanning reached 48.48% and
  53.94% (S38).
- **Architecture and task both varied.** In *Towards a Science of Scaling Agent
  Systems*, centralized coordination scored 0.631 versus a single agent's
  0.349 on decomposable finance (+80.8% relative). Independent agents scored
  0.170 versus 0.568 on sequential planning (−70.0% relative) (S23).
- **One shop deployment found little use for a manager.** *Project Vend: Phase
  two* had no manager-free comparison (S26).
- **SPIKE tested a short-horizon controller.** It issues a fixed subgoal,
  refreshed at events or every four steps. The full system scored 18% versus
  CRADLE's 13% (S17).
- **Classical examples address timing and replanning.** *On Three-Layer
  Architectures* argues that the world can change during deliberation (S46).
  In *Commitment and Effectiveness of Situated Agents*, infrequent replanning
  led when planning was costly. With cheap planning and replanning on target
  loss, the most committed agent led across tested change rates. In a separate
  test, adding a nearer-target trigger improved results (S47). *Actions,
  Policies, Values, and the Basal Ganglia* distinguishes cached values from
  goal-directed evaluation by sensitivity to reward devaluation (S44).

## What the full reading corrected

The last column gives the result after checking claims from abstracts or summaries.

| Source | Initial claim | What the text supports |
| --- | --- | --- |
| Useful Memories Become Faulty (S60) | The model failed on 54% of previously solved tasks. | On 19 ARC-AGI grid puzzles GPT-5.4 first solved without memory, accuracy fell from 100% to 54%, or about 46% failures (S60). |
| Hippo (S05) | Its accumulation baseline falls below no memory. | Two other methods show that trajectory in one task stream. |
| JitMem (S07) | It beats reflections, workflows, skills and strategies. | It tests three implemented baselines, ReasoningBank, MemP and SkillOS. |
| Proactive Memory Agent (S09) | Selective reminders beat always-on reminders. | Always-on leads by 0.3 points when averaging over tasks. Selective reminders lead when domains are weighted equally. |
| PRO-LONG (S15) | A full log replaces summaries. | Plans are still summarized. The study compares the full log with no log. |
| SPIKE (S17) | The actor can override a stale plan. | The actor has to follow the controller's subgoal. |
| Anchor (S03) | Each memory is replayed with and without its decision. | The study toggles a hint at a saved decision and measures the change in action probability. |
| COS-PLAY (S62) | Reward rose over 25.1% against four frontier models in six games. | The reported 25.1% over GPT-5.4 is the mean of four per-game relative gains in single-player games (S62). |
| MemDerive (S67) | Plain search over raw events scored 58.28%. | The search was over session documents. |
| Why Do Multi-Agent LLM Systems Fail? (S41) | The study finds minimal gains from multiple agents. | The claim comes from earlier work cited by the paper. |
| Commitment and Effectiveness of Situated Agents (S47) | Infrequent replanners do worse as the world changes faster. | Scores fell as change accelerated. With low planning cost (1), normal commitment beat bold commitment in dynamic worlds. Bold commitment led at higher cost (4). |
| Production Compilation (S45) | Compiled rules were shown to overgeneralize. | The paper gives an untested example of overgeneralization from reusing old experience. |

## What this implies here

The following are engineering inferences for the open questions.

- **Checkable statements are candidates for curation.** Dated off-screen state,
  causal inferences with conditions, and recommendations with a named goal give
  a reader something to check. [World-state facts (#1020)](https://github.com/CVX-Hull/enactive/issues/1020) ·
  [What the curator should record (#1024)](https://github.com/CVX-Hull/enactive/issues/1024)
- **Reachable evidence is a design hypothesis.** A reader could consult the record
  when a lesson fails or its scope is unclear (S01). [Evidence access (#1025)](https://github.com/CVX-Hull/enactive/issues/1025)
- **The player already owns live plans.** How to carry working state across a
  context cut is open. The curator remains responsible for writing the long-term
  knowledge store under the owner decision. [Player interface](components/player-interface.md) ·
  [Working state across cuts (#1026)](https://github.com/CVX-Hull/enactive/issues/1026) ·
  [Owner decision](decisions/owner-decisions.md#actor-plays-and-curator-maintains-memory)
- **A comparison here could measure regressions alongside gains.** WikiTrace
  offers one measure (S01). The project's withholding study left harm untested.
  [Withholding decision](decisions/owner-decisions.md#curator-and-memory-phase-adopted)
- **A strategist's value here is unknown.** Whether the player's planning
  limits play, and whether a second planner would help, remain open (S17, S23, S38).

## What is not known

- Whether results from mostly short, scored tasks hold in days-long play with
  Enactive's context cuts and player-visible observations.
- Which writer produces more useful memory for subsequent play on matched evidence.
- How often lessons go stale in extended play and which retirement signals work.

## Sources

Two reviewers from other model families checked this page against the digests
and the extracted texts before it merged; their reviews and the correction
hand-back are sealed as
[`memory-statement-kinds-research-review`](../data/evidence/memory-statement-kinds-research-review.sha256).

“Reading reports” counts independent reports on the extracted text, including
reports on both versions of one paper. Read limits are given above and in individual rows.

<!-- sources-table -->
| ID | Source and version read | Main result in the text read | Strength | Reading reports |
| --- | --- | --- | --- | ---: |
| S01 | [WikiTrace](https://arxiv.org/abs/2611.14320), arXiv v1, 10 Nov 2026 | Mean scores: WikiTrace 90.2, lessons alone 87.0, no memory 79.5 (Table 1). Regression: 4.5%, 6.5%, and 9.7% rerun baseline (§4.3). Not read or lost in extraction: Both report full text; figure contents missing from export. | Moderate | 2 |
| S02 | [Falsification-Gated Self-Evolution](https://arxiv.org/abs/2611.14326), arXiv v1, 10 Nov 2026 | DeepSeek-V3.1 scored 39.8 on WebArena and 78.8 on AppWorld; harmful updates were 3.6%, rising to 10.6% without falsification (Tables 1, 5–6). Not read or lost in extraction: Both report full text; several figures’ values are missing from export. | Weak | 2 |
| S03 | [Anchor](https://arxiv.org/abs/2611.10382), arXiv v4, 24 Nov 2026 | ALFWorld Qwen2.5: 87.06% versus 72.64%; Qwen3.5: 96.27% versus 92.54%. The latter retained 41% fewer cards than writing every candidate (§5.2). Not read or lost in extraction: Both report full text; figures 2, 3 and 5 lack image contents. | Weak | 2 |
| S04 | [SimplEvo](https://arxiv.org/abs/2611.11509), 8 November 2026, v1 | EBench success rose 46.7% → 81.7%; text and text-plus-replay both scored 47.5%. Transferred memory raised Gemini Flash 23.8% → 53.8% and DeepSeek Flash 0.8% → 13.1% (Tables 1, 4, 7). Not read or lost in extraction: Both read the text; one skimmed references. Plotted values unavailable. | Moderate | 2 |
| S05 | [Hippo](https://arxiv.org/abs/2610.24453), 29 October 2026, v2 | GPT-5.6 Sol improved 64.2% → 72.9% on WebArena and 81.5% → 88.5% on SWE-bench (Tables 1–2). At 400 tasks, full Hippo scored 86%/82% revisited/unseen versus append-only 72%/66% (Table 11). Not read or lost in extraction: Both read the text; one skimmed references. Figure 3 values unavailable. | Moderate | 2 |
| S06 | [Repair failures, struggle to generalize](https://arxiv.org/abs/2610.22984), 16 October 2026, v1 | For Qwen3.5-27B memory on ALFWorld, four error types occurred in 41.3%, 46.5%, 32.6% and 35.5% of reviewed updates (Table 1). Verified experience improved recovery in five configurations, but held-out results were at or below baseline in four. Not read or lost in extraction: Both read the text; one skimmed references. Most plotted scores were unavailable. | Moderate | 2 |
| S07 | [JitMem](https://arxiv.org/abs/2609.27334), v1, 23 September 2026 | Qwen JitMem versus SkillOS: 77.4% vs 61.2% and 32.8% vs 16.5%; prompted JitMem versus ReasoningBank on τ²: 75.6% vs 71.7%. Tables 1–2. | Moderate | 2 |
| S08 | [Environment-Probing Curation](https://arxiv.org/abs/2609.11060), v1, 10 September 2026 | CLBench pass rates 39±4%, 61±11%, 70±16%, 73±5%; probing versus ordinary memory reduced queries 5.6→4.7. Table 1. | Moderate | 2 |
| S09 | [Proactive Memory Agent](https://arxiv.org/abs/2607.08716), v1 header 9 July; manuscript 24 August 2026 | Sonnet 37.6→45.9% and 55.0→61.8%. Selective reminders scored 64.3/61.2 macro/micro versus forced reminders 63.5/61.5. Tables 1–2. | Weak | 2 |
| S10 | [MemoWM](https://arxiv.org/abs/2610.10778), v1, 7 October 2026 | Mean accuracy 42.42% vs MemGPT’s 39.80%; storage 6.0 vs MIRIX’s 13.1 kbit/observation (Table 1). Omitted-code exact recovery 14.2%, semantic agreement 97.0% (§4.6). | Moderate | 2 |
| S11 | [Epistemics of Agent Memory](https://arxiv.org/abs/2609.33013), v1, 26 September; manuscript June 2026 | +22.7% relative success, 7.17× compression, CI +1.89 to +11.34 points (§3.1). Revised forgetting precision 0.932/0.833 came with about 0.61 forgets per seed, versus about 30 (§3.2). External validity: ρ=−0.24, CI [−0.79,+0.49] (§5.4). | Weak | 2 |
| S12 | [How Strongly Should Task State Influence an LLM Agent?](https://arxiv.org/abs/2609.25686), 22 September 2026, v1 | At 235B, ten-step success was 0.38/0.55/0.84/0.98 across transcript/checklist/directive/enforcement (Table 2). Airline pass¹ rose 0.390→0.540; 35B’s change was inconclusive (Table 20). Not read or lost in extraction: Both report full text; figures unreadable as images. | Moderate | 2 |
| S13 | [The LLM Proposes, the Executive Disposes](https://arxiv.org/abs/2608.04066), 4 August 2026, v1 | Removing the commitment store changed measured abandonment from 0.00 to 1.00, with binding error 0.00; abandonment was defined for two of three removal seeds (§4.1). All 52 runs, including baselines, had zero level completions (§5, line 273). Not read or lost in extraction: Both report full text; figures unreadable as images. | Weak | 2 |
| S14 | [Push Your Agent](https://arxiv.org/abs/2605.23574), 22 May 2026, v1 | State tracking achieved 69.4–77.8% RepoScan success and 0.000 duplicate submissions (Table 1). On DataOps-lite, it achieved 25–50%; Letta reached 50.0% and 45.8% for two stronger models (Table 3). Not read or lost in extraction: Both report full text; figures unreadable as images. | Moderate | 2 |
| S15 | [PRO-LONG](https://arxiv.org/abs/2607.20064), v3, 12 October 2026 | NetHack mean best-of-five progression with and without the log: 24.5% vs 13.5% for one model and 11.3% vs 5.1% for another; ARC tool ladder 23.1%, 27.2%, 38.3%, 41.2% (§§3.2–3.3). Not read or lost in extraction: Both report full reading; appendix prompts and most figures lack content in the supplied text. | Moderate | 2 |
| S16 | [Continual Harness](https://arxiv.org/abs/2605.09998), v1, 11 May 2026 | Emerald Pro: 100% milestones at $130 vs 98% at $215; Flash-Lite adaptive: 3–13% vs 20%. (§4.4) Not read or lost in extraction: Both report full reading; figures 5–8 values and numeric refinement intervals are absent from text. | Moderate | 2 |
| S17 | [SPIKE](https://arxiv.org/abs/2605.18636), v1, 18 May 2026; cover 24 August 2026 | SPIKE vs CRADLE: 18.0% vs 13.0% success; 168.1k vs 372.5k tokens/task. Global memory alone: 12.3%; removing bank: 15.0%; graph: 14.3%. (Tables 2, 5) | Moderate | 2 |
| S18 | [AgenticSTS](https://arxiv.org/abs/2607.02255), v1, 2 July 2026; manuscript 24 August 2026 | Wins were 3/10 without scaffold, 4/10 prompt-only and 6/10 in each of three skill conditions. Fisher test for 3/10 vs 6/10: p≈0.37. (Table 2, §6.2) | Weak | 2 |
| S19 | [EmbodiedMemory-Bench](https://arxiv.org/abs/2609.28236), v1, 23 September 2026 | GPT-5.4-mini rose from 35.3% to 58.9% with EMem; removing event memory reduced interaction-failure success from 44.1% to 27.4%. Tables 2, 4 Not read or lost in extraction: Both report full text; figures were unavailable to one reader. | Moderate | 2 |
| S20 | [AMA-Bench](https://arxiv.org/abs/2602.22769), v4, 27 May 2026 | AMA-Agent scored 0.5722; EMem 0.4610; MemoRAG 0.4606. GPT-5.2 long context scored 0.7226. Tables 4–5 Not read or lost in extraction: Both report full text; figures were unavailable to one reader. | Moderate | 2 |
| S21 | [AgentOdyssey](https://arxiv.org/abs/2606.24893), v3, 23 November 2026 | Mean quest completion: long context 47.7%, retrieval plus short-term memory 30.0%, short-term memory alone 24.1%, fine-tuning plus short-term memory 19.3%. Table 2 Not read or lost in extraction: Both report full text; one could not read a frontier-model figure. | Weak | 2 |
| S22 | [The PokéAgent Challenge](https://arxiv.org/abs/2603.15563), arXiv v2, 17 March 2026 | Six entrants completed all 15 milestones; the two fastest entrant teams finished in 40:13 and 1:14:43 (§5.2). Not read or lost in extraction: Both reported full text; figures were unavailable beyond captions. | Moderate | 2 |
| S23 | [Towards a Science of Scaling Agent Systems](https://arxiv.org/abs/2512.08296), arXiv v3, 8 April 2026 | Finance centralized: 0.349→0.631; PlanCraft independent: 0.568→0.170. Trace amplification was 17.2× independent versus 4.4× centralized (§4.2, Table 5). Not read or lost in extraction: Both reported full text; figures unavailable beyond captions. | Moderate | 2 |
| S24 | [The components of agent memory](https://www.anthropic.com/engineering/components-of-agent-memory), 6 November 2026 | Sonnet wrote 413 files and earned one badge; Fable wrote nine files plus global.md and earned four. Wiki scores rose 13%→48%; search plus wiki reached 61%, versus 53% search alone (lines 39–41, 65–67). Not read or lost in extraction: Both reported full text; figures unavailable beyond captions. | Moderate | 2 |
| S25 | [Agent harness design: 3 patterns](https://claude.com/blog/harnessing-claudes-intelligence), 2 April 2026 | BrowseComp: Sonnet 4.5 stayed at 43%, Opus 4.5 reached 68%, Opus 4.6 reached 84%. A memory folder raised Sonnet 4.5 from 60.4% to 67.2% on BrowseComp-Plus (lines 39–45). Not read or lost in extraction: Both reported full text; figures unavailable beyond captions. | Weak | 2 |
| S26 | [Project Vend: Phase two](https://www.anthropic.com/news/project-vend-2), 18 December 2025 | Discounts fell about 80% and giveaways halved; the CEO denied over 100 requests but approved them about eight times as often. Refunds tripled and credits doubled (“The CEO”). Not read or lost in extraction: Both reported full text; figures unavailable beyond captions. | Anecdote | 2 |
| S27 | [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents), 26 November 2025 | The example feature checklist contained over 200 initially failing features (“Feature list”). Not read or lost in extraction: Both reported full text; figures unavailable beyond captions. | Anecdote | 2 |
| S28 | [Building multi-agent systems](https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them), 23 January 2026 | Multi-agent systems reportedly use 3–10× the tokens; in the role-split experiment coordination exceeded task work (“Parallelization,” “Context-centric decomposition”). Not read or lost in extraction: Both reported full text; figures unavailable beyond captions. | Anecdote | 2 |
| S29 | [Reflexion](https://arxiv.org/abs/2303.11366), v4, 10 October 2023 | ALFWorld solved 130/134 tasks (§4.1). HumanEval Python rose 80.1%→91.0%; MBPP Python fell 80.1%→77.1% (Table 1). Not read or lost in extraction: Three readers report full text; figure values were unavailable in extracted text. | Moderate | 3 |
| S30 | [ExpeL](https://arxiv.org/abs/2308.10144), v3, 20 December 2024 | Insights/retrieval scored 36%/31% on HotpotQA and 50%/55% on ALFWorld; combined, 39% and 59% (§5.2). Insights from a weaker writer scored 32.0±0.4%; adding reflections to the trajectory evidence scored 29.0±0.4% (Table 3). Not read or lost in extraction: Three readers report full text; some figure values were unavailable in extracted text. | Moderate | 3 |
| S31 | [Agentic Context Engineering](https://arxiv.org/abs/2510.04618), v3, 29 March 2026 | AppWorld averages: baseline 42.4, offline ACE 59.4 with labels and 57.2 without (Table 1). Test-normal full rewrite versus incremental update: 67.3→76.2 TGC, or 56.9→70.3 average (Table 18). | Moderate | 3 |
| S32 | [Dynamic Cheatsheet](https://arxiv.org/abs/2504.07952), v1, 10 April 2025 | Game of 24 GPT-4o baseline/empty/curated/retrieval-synthesis: 10%/19%/93%/99%; Sonnet baseline→retrieval-synthesis: 12%→14% (Table 1). | Moderate | 3 |
| S33 | [ReasoningBank](https://arxiv.org/abs/2509.25140), v2, 16 March 2026 | WebArena success was 40.5%, 42.1%, 44.1% and 48.8% for no memory, raw trajectories, workflows and the method (Table 1). On the Shopping subset, success-only versus including failures: 46.5→49.7%; workflows 44.4→42.2% (§5). | Moderate | 3 |
| S34 | [How Memory Management Impacts LLM Agents: Experience-Following Behavior](https://arxiv.org/abs/2505.16067), arXiv v2, 10 October 2025, and the [ACL 2026 version](https://aclanthology.org/2026.acl-long.27/) | Fixed bank versus add-all success: 67.53/55.48, 16.75/13.05, 40.11/32.32 and 71.50/59.90% (Table 1). History-based deletion with a ground-truth evaluator: 38.67%→42.06% with 1,012→784 records for one agent, and 70.95%→69.80% for the regression-task agent; with a coarse evaluator one agent fell 36.92%→34.00% (Table 2). Not read or lost in extraction: All reported full readings; Appendix A0.2–A0.4 prompt contents are absent from the extracted text. | Moderate | 5 |
| S35 | [Agent Workflow Memory](https://arxiv.org/abs/2409.07429), v1, 11 September 2024 | WebArena AWM 35.5% versus BrowserGym 23.5% and accessibility-tree baseline 15.0% (Table 1). Mind2Web step success: 34.6% versus Synapse 30.6% (Table 3). | Moderate | 3 |
| S36 | [Self-Correction of Reasoning](https://arxiv.org/abs/2310.01798), v2, 14 March 2024 | GPT-4 GSM8K 95.5→89.0%, CommonSenseQA 82.0→80.0%, HotpotQA 49.0→43.0% after two intrinsic rounds; oracle stopping reaches 97.5/85.5/59.0% (Tables 2–3). | Moderate | 3 |
| S37 | [BALROG](https://arxiv.org/abs/2411.13543), v2, 1 April 2025 | NetHack o1-preview scored 1.57 ± 0.40% progression; the best individual run reached dungeon level 3 and experience level 4. Not read or lost in extraction: All three readings report full text; figures are absent from the text. | Moderate | 3 |
| S38 | [Plan-and-Act](https://arxiv.org/abs/2503.09572), v3, 22 April 2025 | Untuned planner: 17.16/23.63% versus 36.36/36.97% without one. Targeted augmentation: 42.42/43.63%; dynamic replanning: 48.48/53.94%. | Moderate | 3 |
| S39 | [Voyager](https://arxiv.org/abs/2305.16291), v2, 19 October 2023 | 63 items; fresh-world success 12/12 with the library versus 11/12 without it. Random curriculum reduced item count 93%; removing self-verification reduced it 73% (§§3.3–3.4). | Moderate | 3 |
| S40 | [Generative Agents](https://arxiv.org/abs/2304.03442), v2, 6 August 2023 | TrueSkill means of rated interview answers: full 29.89, no reflection 26.88, no reflection or planning 25.64, human-written 22.95, no memory, reflection or planning 21.21 (§6.5.1). | Moderate | 2 |
| S41 | [Why Do Multi-Agent LLM Systems Fail?](https://arxiv.org/abs/2503.13657), v3, 26 October 2025 | Human agreement κ=0.88; judge κ=0.77. ChatDev ProgramDev success rose 25.0% → 34.4% → 40.6% (Table 2, Table 5). | Moderate | 2 |
| S42 | [JARVIS-1](https://arxiv.org/abs/2311.05997), v3, 30 November 2023 | Diamond-group success was 8.99±2.68% versus DEPS’s 2.42±1.01% (Table 2); memory held 425 trajectories after four epochs (Fig. 7). | Moderate | 2 |
| S43 | [Introduction to the Soar Cognitive Architecture](https://arxiv.org/abs/2205.03854), May 8, 2022, Soar 9.6 | §10 reports roughly 50 ms decision cycles, runs of 30 days, and 8 yes, 5 partial and 2 no self-ratings. Appendix A reports RAT fit \(R^2=0.98\), MSE 0.29, for work under review. | Weak | 2 |
| S44 | [Actions, Policies, Values, and the Basal Ganglia](https://nivlab.princeton.edu/wp-content/uploads/sites/938/2024/02/dawnivdayan2006.pdf), February 11, 2005 manuscript | Table 1 qualitatively contrasts habitual and goal-directed responses; no new numerical results. Devaluation sensitivity can persist in complex tasks or near reward (§3). Not read or lost in extraction: Both report full text; one says plotted curves were unavailable. | Moderate | 2 |
| S45 | [Production Compilation](https://www.ai.rug.nl/~niels/publications/HF-published.pdf), 2003 | Human–model fits: planes landed \(r^2=0.97\), land time 0.98, queue time 0.91, and land keystrokes 0.87; move time was slower, with no fit reported (Figs. 4–6). | Moderate | 2 |
| S46 | [On Three-Layer Architectures](https://u.cs.biu.ac.il/~galk/teach/current/intsys/readings/on-three-layer-arch-tla-1998.pdf), undated chapter | Alfred placed second in one 1993 event and alone completed another; its contest code took three days by one person (§4). | Anecdote | 2 |
| S47 | [Commitment and Effectiveness of Situated Agents](https://ijcai.org/proceedings/1991/0013.pdf), undated proceedings text | With planning cost 4, bold commitment wins; with cost 1, normal commitment wins in dynamic worlds and cautious matches bold. At cost 1, replanning on loss of the target makes the bold agent best across tested rates, and adding a nearer-target trigger does better still (§§3.3–3.4, Figs. 8–10). Not read or lost in extraction: Plotted curves were unreadable. | Moderate | 2 |
| S48 | [The Utility Problem in Case-Based Reasoning](https://cdn.aaai.org/Workshops/1993/WS-93-01/WS93-01-026.pdf), 1993 | No experimental results. The abstract cites a theoretical parallel-selection bound of \(\Omega(\lg n)\) and distinguishes matching costs from search-space costs (paragraphs 2–3). | Weak | 2 |
| S49 | [Instrumental Rationality](https://plato.stanford.edu/entries/rationality-instrumental/), revised 2023-02-05 | Means may help bring about ends in several ways; coherence concerns an intended end and a believed necessary means (§§2–3). No experimental figures. Not read or lost in extraction: Both report the file read in full; linked supplement unread. | Weak | 2 |
| S50 | [Defeasible Reasoning](https://plato.stanford.edu/entries/reasoning-defeasible/), revised 2025-06-13 | A Ramsey-test conditional added to AGM trivializes revision; one proposed approach separates foundational from inferred beliefs (§4.3, lines 680–733). No empirical figures. Not read or lost in extraction: Both report the file read in full; supplements unread. | Moderate | 2 |
| S51 | [Handoffs](https://psnet.ahrq.gov/primer/handoffs), 2024-06-15 | The primer reports that one structured handoff bundle reduced preventable adverse events and that results for another mnemonic were mixed; it gives no effect sizes. Not read or lost in extraction: The primary studies the primer summarizes were not read. | Weak | 2 |
| S52 | [Postmortem Culture](https://sre.google/sre-book/postmortem-culture/), 2017 | One release caused a four-minute outage; its engineer received two peer bonuses (line 111). The claimed reduction in outages has no figure (line 116). Not read or lost in extraction: Both report the file read in full; external example postmortem unread. | Anecdote | 2 |
| S53 | [Epistemological Problems of Testimony](https://plato.stanford.edu/entries/testimony-episprob/), 2021 | Non-reductionism proposes a defeasible presumptive right (§1.2). A group report can assert a composite claim that no individual member previously believed or had evidence for (§6, lines 1244–1267). Not read or lost in extraction: Both reported full text. One noted referenced footnotes were absent from the downloaded text. | Weak | 2 |
| S54 | [Knowledge How](https://plato.stanford.edu/entries/knowledge-how/), 2021 | The entry recounts a patient who improved at mirror tracing over 10 trials while needing a reminder of the task at each trial (§7.1). | Weak | 2 |
| S55 | [Cognitive Architectures for Language Agents](https://arxiv.org/abs/2309.02427), v3, 15 Mar 2024 | SayCan has 551 grounding skills (§5). Table 2 lists no agent combining writable long-term memory with propose–evaluate–select planning. Not read or lost in extraction: Both reported reading the text; one said figures 1–5 and Table 1 mathematics were garbled or missing. | Weak | 2 |
| S56 | [Always-On Agents](https://arxiv.org/abs/2606.30306), arXiv v1, 29 Jun 2026 | Governed reducer passed 15/15 obligations; raw stores 7/15; extracted stores 4/15 and 3/15; no memory 0/15 (Table 18). Retrieval appeared in 269 works, rollback in 27 (Table 9). | Moderate | 2 |
| S57 | [Memory in the Age of AI Agents](https://arxiv.org/abs/2512.13564), v2, 13 Jan 2026 | Three forms, three functions and three dynamics; tables catalog benchmarks and frameworks rather than report the survey’s own performance results (abstract; Tables 1–7). Not read or lost in extraction: Both report reading the full text; figures were unavailable and some converted lists were missing. | Weak | 2 |
| S58 | [Cradle](https://arxiv.org/abs/2403.03186), arXiv v3, 2 July 2024 | Cultivation: Cradle 4/5, comparison methods 0/5 (Table 6). OSWorld: 7.81% versus GPT-4o’s 5.03% (Table 4). Not read or lost in extraction: Both report full text; rendered figure details and Table 5 content were unavailable in the extracted text. | Weak | 2 |
| S59 | [More Memory, Worse Agents](https://arxiv.org/abs/2610.27406), v1, 19 October 2026 | Discarding guidance beat persistence by 3.3–28.0 points in four cells (Table 2). Not read or lost in extraction: All three read the full text; extracted prompt blocks and figure data are missing. | Moderate | 3 |
| S60 | [Useful Memories Become Faulty When Continuously Updated by LLMs](https://arxiv.org/abs/2605.12978), v2, 29 August 2026 | At step 400, forced rewriting scored 43.2%, add/delete 64.0%, raw trajectories 76.6% (Table 5). Not read or lost in extraction: All read full text; one did not analyze appendix prompt/grid dumps; extracted plots and boxes are missing. | Moderate | 3 |
| S61 | [AutoMem](https://arxiv.org/abs/2607.01224), v1, 1 July 2026 | Base files → revised scaffold → specialist: Crafter 25.00 → 47.27 → 51.36; MiniHack 7.5 → 27.5 → 30.0; NetHack 0.42 → 1.57 → 1.85. Table 1 Not read or lost in extraction: Both report full text; exported figures are missing. | Moderate | 2 |
| S62 | [COS-PLAY](https://arxiv.org/abs/2604.20987), v1, 22 April 2026 | Mean single-player reward was 924.4 versus GPT-5.4’s 717.4; Avalon 39.0% versus 65.0%, Diplomacy 2.96 versus 4.70. SFT with the final bank averaged 359.5 versus 409.5 without skills. Table 1 Not read or lost in extraction: Both report full text; case-study figures are missing. | Moderate | 2 |
| S63 | [PokeGym / G-EvoMAC](https://arxiv.org/abs/2604.08340), v2, 3 August 2026 | Success was 60.18%, versus Voyager 48.42% and zero-shot GPT-5.4 37.19%. Without visual, strategy or action evolution: 39.82%, 47.02% and 50.35%. Tables 2–3 Not read or lost in extraction: Both report full text; example strategies, macros and prompts are missing from the export. | Moderate | 2 |
| S64 | [HyMem](https://arxiv.org/abs/2608.15703), v1, 16 August 2026 | 66.7% on GAIA and 61.3% on BrowseComp-Plus for one backbone; another fell from 32.0% to 25.3% on BrowseComp-Plus. Removing memory cost 9.0 points (BrowseComp-Plus, first backbone) and 18.6 points (GAIA, second backbone) (Tables 1–2). Not read or lost in extraction: Both report full text; case-study and prompt table bodies are missing. | Weak | 2 |
| S65 | [The Compaction Cliff](https://arxiv.org/abs/2608.22752), v1, 24 Aug 2026 | /compact constraint recall fell from 0.53 to 0.10 over five rounds; TypeCompact stabilized at 0.96 (§4.3). Retail pass rates were 37.7% versus 28.6% for full policy (§4.5). Not read or lost in extraction: Both reported full text; intermediate Figure 3 values are unavailable in the text. | Moderate | 2 |
| S66 | [When Memory Lies](https://arxiv.org/abs/2608.04574), v1, 5 Aug 2026 | GPT-4o L2 deaths fell from 74.4% without filtering to 31.6% with OMCD; no memory had 28.0% deaths (Table 3). Vision detection F1 ranged from 0.067 to 0.887 (§5.2). | Moderate | 2 |
| S67 | [MemDerive](https://arxiv.org/abs/2610.25373), v1, 18 Oct 2026 | Memory systems scored 30.41–48.30% versus BM25’s 58.28% (§5.2). Explicit changes refreshed 82.4% versus 41.1% for implicit changes (§5.4). Not read or lost in extraction: Both reported full text; individual values shown only in the Q1 plot were unavailable in the text. | Moderate | 2 |
| S68 | [When Does Memory Help?](https://arxiv.org/abs/2609.05441), preprint v1.1, 26 Jul 2026 | Pilot hard-tier fact store scored 0.75–1.00 versus retrieval’s 0.35–0.70 (Table 1). Across the main grid, retrieval scored 0.30–0.95 and fact store 0.70–1.00 (§5.7). | Moderate | 2 |
| S69 | [STALE](https://arxiv.org/abs/2605.06527), v1, 7 May 2026 | CUPMem scored 68.0%, plain GPT-4o-mini 8.7%; CUPMem’s direct/indirect advice scores were 32%/43%. Table 2 | Moderate | 2 |
| S70 | [DISCERN](https://arxiv.org/abs/2611.15729), v1, 11 November 2026 | Equal-pillar macro 0.861 versus 0.806; entity resolution 0.800 versus at most 0.400; abstention F1 0.924 versus 0.802. Tables 1–2 | Moderate | 2 |
| S71 | [TraceRetain](https://arxiv.org/abs/2606.29178), v1, 28 June 2026 | Under synthetic noise, CEM solved 97/100, FIFO 94/100; Precision@5 changed 16.9%→16.6% for CEM and 15.8%→3.8% for FIFO. Table 2, §5.2 | Weak | 2 |
| S72 | [ReMe](https://arxiv.org/abs/2512.10696), v2, 15 April 2026 | BFCL 8B Pass@4: keypoints 65.77%, trajectories 60.00%; deletion raised 64.66%→68.00%, while Avg@4 rose 45.00%→45.17%. Tables 2–3 Not read or lost in extraction: Both report full text; one notes prompt tables are empty and figures unavailable in the text. | Moderate | 2 |
| S73 | [How Much Should an Agent Remember?](https://arxiv.org/abs/2611.26361), v1, 19 November 2026 | gpt-oss: 39.9% without memory, 51.2% with 199 guidelines, 55.4% with about 29 retrieved; DeepSeek: 79.8% to 89.3% (Table 2). Not read or lost in extraction: Both report full text; one saw figure captions only. | Moderate | 2 |
| S74 | [AdMem](https://arxiv.org/abs/2611.20605), v1, 16 November 2026 | AdMem 441/707, ReAct 388, AWM 312; PDDL alone survives domain-level correction (Table 2; §3.3). Jericho procedural-only: 4–6/20 versus ReAct 8/20 across epochs (Table 3). | Moderate | 2 |
| S75 | [Can LLM Agents Organize Their Own Memory?](https://arxiv.org/abs/2611.11929), v1, 9 November 2026 | Scores 88.96%, 54.02%, 76.50%; gains over strongest baselines 2.66, 3.10, 2.00 points (Tables 2–4). Removing Source costs 8.64 points (Table 9). | Moderate | 2 |
| S76 | [R²-Mem](https://arxiv.org/abs/2605.13486), v1, 13 May 2026 | Qwen-7B LoCoMo F1: GAM 45.77, external evaluator 51.35, Self-Evo 49.76 (Table 10). Low-quality-only advice beats high-quality-only in four categories (Table 4). Not read or lost in extraction: Both report full extracted text; prompt and case sections lack their promised contents. | Weak | 2 |
| S77 | [MemSIF](https://arxiv.org/abs/2608.01742), v2, 5 August 2026 | LoCoMo/Qwen3-4B accuracy: full 75.62%, query-local only 73.09%, no ActiveFact 67.43% (Table 4). Low-salience evidence appeared in 430/1,035 critical pairs (Table 8). | Moderate | 2 |
| S78 | [MemForest](https://arxiv.org/abs/2605.23986), v4, 23 November 2026 | On one benchmark and model, 81.80% versus 71.00% for the strongest baseline (Table 2). Tree versus fact-log point accuracy stayed within 1.1 points, p ≥ 0.18; on the full history, range recall was 0.42 for the tree and 0.18 for the log (§8.4). | Moderate | 2 |
| S79 | [MemP](https://aclanthology.org/2026.findings-acl.866/), ACL 2026 | GPT-4o ALFWorld test success rose 42.14%→77.86%; TravelPlanner hard-constraint score fell 12.88→9.76 (Table 1). GPT-4o-to-Qwen2.5-14B transfer raised delivery 91.4→96.6 (Fig. 5a). Not read or lost in extraction: Both report full text; figure values are mostly missing or scrambled in the extraction. | Moderate | 2 |
