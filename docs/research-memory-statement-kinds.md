---
owner: lead
status: active
date: 2026-11-26
scope: 'Outside evidence on what kinds of statement an agent''s long-term memory should hold (observations, state, cause and effect, lessons, procedures, plans), who should write each, and whether a separate long-horizon planner is warranted; 80 sources read in full by readers from two or three model families'
review_trigger: 'The owner decides what the curator records beyond observations (#1024), what survives a context cut (#1026) or whether to add a strategist; or a study appears that tests memory in a days-long game with context cuts, or compares a separate memory writer with the acting agent head to head'
---

# Research on what a player's memory should hold and who writes it

The literature search cutoff is **2026-11-26** (America/New_York). This page reports
outside evidence and its limits. It decides nothing: the current rule is that the
[curator](components/curator.md) writes the knowledge store and the player does not
maintain it ([owner decision](decisions/owner-decisions.md#actor-plays-and-curator-maintains-memory)).

It builds on, and does not repeat, the
[memory, ontology and oversight synthesis](research-curated-memory.md) and the
[belief review](research-belief-under-conflict.md). The question came from the lead's
review of the three-day campaign's memory
([#1019](https://github.com/CVX-Hull/enactive/issues/1019)): the store held accurate
observations and almost no conclusions, and nothing in the project's documents says
whether that is right.

## At a glance

- **"Is or ought" is the wrong cut.** Statements differ in what they need from the
  reader. An observation, a cause-and-effect claim and a recommendation that names
  its goal can each be checked against recorded evidence. A directive, a plan and a
  goal are only right for a reader with that goal in that situation.
- **Stored lessons help on average and also break tasks.** In the studies that
  measure it, memory turned some successes into failures, and agents followed wrong
  memory readily.
- **Keeping the evidence beats keeping only the lesson.** Four 2026 studies find that
  raw records, or lessons linked to their records, do as well as or better than
  distilled lessons alone, and that repeated rewriting loses information.
- **Procedures that state their conditions and were tested do best** among stored
  lessons. Lessons drawn from failures repair the failed task and transfer poorly.
- **Working state belongs with the actor.** The studies of task state, commitments
  and context resets favour state the acting agent or the harness keeps, checked
  against evidence, over state reconstructed from a history.
- **A separate strategist is not supported by what was read.** An untuned planner
  made trained executors worse, the one deployment with a manager agent found it
  unhelpful, and gains from splitting roles depend on the task.
- **No source tests our setting.** Nothing read studies memory in a days-long,
  partially observed game with context cuts, and nothing compares a separate memory
  writer with the acting agent on the same task.

## Brief and method

**Questions.**

- Should memory hold only descriptive statements, or also lessons, procedures, plans
  and goals?
- Who should write each kind: the acting agent, a separate memory writer, or a
  separate long-horizon planner?
- How are stale or wrong entries found and retired?

**Search.** Three rounds on 26 November 2026. The first, by one model family, reached
no source newer than March 2026, because a model recalls titles from before its own
training cutoff. The second searched by date from April to November 2026. In the
third, readers from two other model families searched independently, confirmed nine
leads the second round had seen only as search snippets, and found about 25 further
sources. Conference proceedings and reviewer sites were searched in the third round
only.

**Reading.** Each source was fetched as full text and read from first character to
last by readers from two or three model families, on one brief that asked for the
comparisons run, the figures with their section, the limits, and a verdict on each
claim made about the source from its abstract. A fourth reader reconciled the
readings of each batch and settled every disagreement against the source text. The
lead read every reconciled digest. The briefs, the readings, the reconciled digests
and the list of claims tested are sealed as
[`memory-statement-kinds-research`](../data/evidence/memory-statement-kinds-research.sha256);
the source texts are not kept. The delegated starts are rows in the
[attempts ledger](../data/evaluation/coding-agent-attempts.jsonl).

**Read limits.**

- The text extraction keeps formulas and table cells and drops figure images, so a
  value shown only in a plot was not read.
- Three sources were not read at all, because their files could not be fetched:
  "The Compliance Trap", "Auto-Dreamer" and "SEEM²" (reviewer-site submissions of
  September 2026). They are leads, not evidence, and are named where they would bear.
- One classical source (Francis and Ram, 1993) is a one-page abstract.
- Strength labels are the reconciler's, checked by the lead: most sources are
  **moderate** or **weak**, usually for unreported or single runs.

## Kinds of statement

This table is the lead's inference from the philosophy sources (instrumental
rationality, defeasible reasoning, testimony, knowledge-how). It is a vocabulary, not
a finding.

| Kind | Example | Can the writer check it from recorded evidence? | What it needs from the reader |
| --- | --- | --- | --- |
| Observation | "At 6:10 the battery showed 0%" | Yes | Nothing |
| State that changes slowly and is off screen | "The northern toilet is empty since day 63" | Yes, until it changes | Its date |
| Cause and effect | "Boiling at the fire worked with the battery flat" | Yes | The conditions it was seen under |
| Measure against a stated standard | "The oil is about 14 days of food at 2,000 kcal a day" | Yes; the standard is in the sentence | Nothing |
| Conditional recommendation | "To boil water with the battery flat, use the fire" | Its causal part, yes | To hold the named goal |
| Directive, plan, goal | "Fish next" | No | Its goal and present situation |

- **A goal plus facts yields an action; facts alone do not.** "If you want X, do Y"
  contains the claim "Y helps bring about X", which is true or false whatever the
  reader wants.
- **Advice can stop applying while its facts stay true.** A new goal or new equipment
  undercuts the recommendation and leaves the observation standing.
- **A written procedure is not the ability to perform it.** One game benchmark
  (BALROG) reports a "knowing-doing gap": a model that can say rotten food is deadly
  still eats it.

## What the evidence says

### Stored lessons help and harm

- **Memory breaks some tasks it did not help.** WikiTrace (November 2026) measures
  the rate at which memory turns a success into a failure: 4.5% for lessons linked to
  their evidence, 6.5% for lessons alone, against 9.7% for a rerun with no memory. A
  judge traced 52% of degraded cases to a memory item the agent followed.
- **Adding everything is worse than adding nothing new.** In the experience-following
  study, storing every experience scored below a fixed memory on all four agents
  (for example 13.05% against 16.75%), and strict admission did far better.
- **Rewriting loses detail.** In one ACE trace a context of 18,282 tokens was
  rewritten to 122 and accuracy fell from 66.7 to 57.1, below the 63.7 baseline.
  "The Compaction Cliff" finds model-written compaction keeps 53% of constraints
  after one round and 10% after five.
- **Unread lead.** "The Compliance Trap" reportedly finds that agents adopt
  conflicting memory at the first decision point in most cases.

### Keeping the evidence

- **Records plus guidance built on demand beat stored abstractions.** "More Memory,
  Worse Agents" (October 2026; three benchmarks, three models, three seeds) scores
  59.9% for raw records with disposable guidance, 53.5% for records alone, 49.0% for
  persistent abstractions and 49.3% for both.
- **Curating when the task is known beats curating when writing.** JitMem keeps raw
  trajectories and builds a briefing at read time; it leads the strongest write-time
  baseline by 16.2 and 16.3 points on two benchmarks and 3.9 on a third.
- **Repeated consolidation can fall below keeping episodes.** In "Useful Memories
  Become Faulty", at step 400 forced rewriting scores 43.2%, add-and-delete 64.0% and
  raw trajectories 76.6%. This holds in that table and not in every one.
- **A full searchable log helps in a long game.** PRO-LONG reaches 24.5% against
  13.5% on NetHack with a complete interaction log. It has no comparison with
  distilled memory, and its plans are still summaries.
- **A survey's own pilot points the same way.** In "Always-On Agents" a store that
  keeps raw records passed 7 of 15 governance obligations and two stores of
  extracted statements passed 4 and 3. The pilot is small.
- **Derived state is where memory systems fail.** On MemDerive, four memory systems
  score 30% to 48% on questions that need derived state, below 58% for plain search
  over session documents.

### Procedures with conditions and tests

- **Lessons stated as testable hypotheses.** Falsification-gated self-evolution
  stores a precondition, a behaviour change, an expected effect and a verifier;
  harmful committed updates are 3.6%, and 10.6% without the test.
- **Decisions with their conditions.** Hippo stores decisions with the conditions
  they apply under and replaces conflicting entries; at 400 tasks it scores 86% and
  82% on revisited and unseen tasks against 72% and 66% for append-only.
- **Selection and retirement by use.** ReMe's utility-based deletion raises one score
  from 64.66% to 68.00%. In "How Much Should an Agent Remember?", about 29 selected
  guidelines (55.4%) beat all 199 (51.2%).
- **Procedures transfer between models.** In SimplEvo and MemP, procedures written
  with a stronger model raise a weaker one.

### Lessons from failure

- **They repair and do not generalize.** Across three frameworks and ten models,
  failure-derived experience improved recovery on the failed tasks in five
  configurations and left held-out tasks at or below baseline in four; successful
  trajectories transferred better. The study has no matched no-memory retry control.
- **A counter-result.** ReasoningBank's own ablation gains from adding failures
  (46.5% to 49.7% on one subset), so the finding depends on how the failure is
  distilled.

### State and staleness

- **State readable from the screen should not be stored.** In a vendor case report,
  one model wrote 413 memory files and earned one badge in a game; its "detailed
  record was continuously going out of date". Another wrote nine files and earned
  four. These are single runs, and the model and the note style change together.
- **Keep superseded values; mark what is current.** STALE marks earlier facts stale
  at write time and keeps them as history (68.0% against 8.7% on implicit
  conflicts). DISCERN keeps superseded values with two time axes. Structured
  overwriting of facts beat embedding retrieval on updated-fact tasks in a synthetic
  study.
- **Check remembered state against the present.** In a text grid, auditing stored map
  facts against current observations cut deaths from 74.4% to 31.6%. With
  screenshots the audit was unreliable.

### Working state across a context reset

- **State the agent keeps for itself.** In a study of task state, an unverified
  ledger the agent writes beats an accurate checklist it is shown, and the result
  reverses on a second benchmark. Enforcing state through the harness helped a large
  model (0.39 to 0.54) and not a small one.
- **Commitments.** Removing a commitment store changed measured goal abandonment
  from 0.00 to 1.00 in a study where no run completed a level.
- **Structured handoff across resets.** HyMem carries milestones, verified facts,
  objectives and next steps across context refreshes; removing it costs 9.0 and 18.6
  points. Its tables are inconsistent, so the evidence is weak.
- **Survival games.** AutoMem (Crafter, MiniHack, NetHack) improves a base agent
  about two to four times with files the actor, the harness and an offline model
  each write. Its parts are not separated, and memory resets between episodes.

### Who writes memory

- **Separate writers help in the studies that use them**: a post-task curator that is
  the only writer (39% to 73% against no memory), a memory agent beside the actor
  (+8.3 and +6.8 points, single attempts), and a skill-bank agent for a small actor
  in games.
- **Self-written lessons also help** when selected, and a transcript check can
  correct an agent's own wrong note (one vendor case).
- **Writer identity matters little in one test.** With the reader fixed, three writer
  models scored 92.34%, 91.95% and 92.01% on a dialogue benchmark.
- **Nobody compares the two.** No source gives the same evidence to a separate writer
  and to the acting agent and compares the play that follows.

### A separate strategist

- **An untuned planner hurts.** In Plan-and-Act, adding an untuned planner dropped
  trained executors from about 36% to 17% and 24%; a trained planner with replanning
  reached 53.94%, with training and inference changed together.
- **Role splitting depends on the task.** A study of 260 configurations finds +80.8%
  on a decomposable task and −70.0% on sequential planning.
- **One deployment.** A manager agent set goals for a shop-running agent; its authors
  judged it "wasn't much help, and might even have been a hindrance". There was no
  manager-free control.
- **A game planner.** SPIKE's planner refreshes at events and every four steps, and
  its actor cannot change the subgoal; it gains 5 points on short tasks.
- **Classical results.** Deliberation takes long enough for the world to change
  before it returns (Gat). Whether an agent that rarely reconsiders its plan does
  worse in a changing world depends on what planning costs; when it replans only on
  losing its target, it is best at every tested rate of change (Kinny and Georgeff).
  Cached values do not follow a changed goal until re-experienced (Daw, Niv and
  Dayan).

## What the full reading corrected

The abstract-level search made these claims; the full text says otherwise.

| Source | Claim from the abstract or a summary | What the text says |
| --- | --- | --- |
| Useful Memories Become Faulty | A model fails 54% of previously solved tasks | 54% is the accuracy; about 46% fail |
| Hippo | Its accumulation baseline falls below no memory | That trajectory is two other methods in one task stream |
| JitMem | It beats reflections, workflows, skills and strategies | Its three baselines are ReasoningBank, MemP and SkillOS |
| Proactive Memory Agent | Selective reminders beat always-on reminders | Always-on leads one of two averages by 0.3 |
| PRO-LONG | A full log replaces summaries | Plans are still summarized; no summary-memory comparison |
| SPIKE | The actor can override a stale plan | The actor cannot change the subgoal |
| Anchor | Each memory is replayed with and without its decision | A hint is toggled at a saved decision; no alternative run |
| COS-PLAY | Over 25.1% against four frontier models in six games | 25.1% over one model across four single-player games |
| MemDerive | Plain search over raw events scores 58.28% | The search is over session documents |
| Multi-agent failure taxonomy | It finds multi-agent gains are minimal | It cites that from earlier work and does not test it |
| Kinny and Georgeff | Agents that rarely reconsider do worse as the world changes faster | Only when planning is cheap; at a higher planning cost they do better |
| Production compilation (ACT-R) | Compiled rules can overgeneralize | An untested illustration, attributed to reusing old experience |

## What this implies here

These are engineering inferences, not adopted rules.

- **The curator's safest additions are checkable ones**: slow off-screen state with
  its date, cause-and-effect with its conditions, and recommendations that name their
  goal and cite their evidence ([#1020](https://github.com/CVX-Hull/enactive/issues/1020),
  [#1024](https://github.com/CVX-Hull/enactive/issues/1024)).
- **Evidence must stay reachable.** The results above depend on the reader being
  able to open the record behind a lesson
  ([#1025](https://github.com/CVX-Hull/enactive/issues/1025)).
- **Plans and working state fit the player better than the curator**, with the
  curator in a checking role
  ([#1026](https://github.com/CVX-Hull/enactive/issues/1026)). The current owner
  decision says otherwise, so this needs a decision.
- **Measure harm as well as benefit.** The project's withholding study did not test
  harm; the regression measure used in 2026 work is the missing half.
- **A strategist is not indicated** before the player keeps its own plan and that
  plan is shown to be the limit.

## What is not known

- Whether any of this holds in a days-long, partially observed game with context
  cuts. Almost every comparison uses short scored tasks with outcome feedback, which
  a long game gives rarely.
- Whether a separate curator writes better memory than the acting agent from the same
  evidence.
- How often lessons go stale in play, as opposed to in synthetic benchmarks.
- What the three unread sources show.

## Sources

Every source below was read in full unless its row says otherwise. "Readings" is the
number of independent full-text readings that were reconciled.

<!-- sources-table -->
| Source and version read | Main result in the full text | Strength | Readings |
| --- | --- | --- | ---: |
| [WikiTrace](https://arxiv.org/abs/2611.14320), arXiv v1, 10 Nov 2026 | Mean scores: WikiTrace 90.2, lessons alone 87.0, no memory 79.5 (Table 1). Regression: 4.5%, 6.5%, and 9.7% rerun baseline (§4.3). | Moderate | 2 |
| [Falsification-Gated Self-Evolution](https://arxiv.org/abs/2611.14326), arXiv v1, 10 Nov 2026 | DeepSeek-V3.1 scored 39.8 on WebArena and 78.8 on AppWorld; harmful updates were 3.6%, rising to 10.6% without falsification (Tables 1, 5–6). | Weak | 2 |
| [Anchor](https://arxiv.org/abs/2611.10382), arXiv v4, 24 Nov 2026 | ALFWorld Qwen2.5: 87.06% versus 72.64%; Qwen3.5: 96.27% versus 92.54%. The latter retained 41% fewer cards than writing every candidate (§5.2). | Weak | 2 |
| [SimplEvo](https://arxiv.org/abs/2611.11509), 8 November 2026, v1 | EBench success rose 46.7% → 81.7%; text and text-plus-replay both scored 47.5%. Transferred memory raised Gemini Flash 23.8% → 53.8% and DeepSeek Flash 0.8% → 13.1% (Tables 1, 4, 7). Read scope: Both read the text; one skimmed references. Plotted values unavailable. | Moderate | 2 |
| [Hippo](https://arxiv.org/abs/2610.24453), 29 October 2026, v2 | GPT-5.6 Sol improved 64.2% → 72.9% on WebArena and 81.5% → 88.5% on SWE-bench (Tables 1–2). At 400 tasks, full Hippo scored 86%/82% revisited/unseen versus append-only 72%/66% (Table 11). Read scope: Both read the text; one skimmed references. Figure 3 values unavailable. | Moderate | 2 |
| [Repair failures, struggle to generalize](https://arxiv.org/abs/2610.22984), 16 October 2026, v1 | For Qwen3.5-27B memory on ALFWorld, four error types occurred in 41.3%, 46.5%, 32.6% and 35.5% of reviewed updates (Table 1). Verified experience improved recovery in five configurations, but held-out results were at or below baseline in four. Read scope: Both read the text; one skimmed references. Most plotted scores were unavailable. | Moderate | 2 |
| [JitMem](https://arxiv.org/abs/2609.27334), v1, 23 September 2026 | Qwen JitMem versus SkillOS: 77.4% vs 61.2% and 32.8% vs 16.5%; prompted JitMem versus ReasoningBank on τ²: 75.6% vs 71.7%. Tables 1–2. | Moderate | 2 |
| [Environment-Probing Curation](https://arxiv.org/abs/2609.11060), v1, 10 September 2026 | CLBench pass rates 39±4%, 61±11%, 70±16%, 73±5%; probing versus ordinary memory reduced queries 5.6→4.7. Table 1. | Moderate | 2 |
| [Proactive Memory Agent](https://arxiv.org/abs/2607.08716), v1 header 9 July; manuscript 24 August 2026 | Sonnet 37.6→45.9% and 55.0→61.8%. Selective reminders scored 64.3/61.2 macro/micro versus forced reminders 63.5/61.5. Tables 1–2. | Weak | 2 |
| [MemoWM](https://arxiv.org/abs/2610.10778), v1, 7 October 2026 | Mean accuracy 42.42% vs MemGPT’s 39.80%; storage 6.0 vs MIRIX’s 13.1 kbit/observation (Table 1). Omitted-code exact recovery 14.2%, semantic agreement 97.0% (§4.6). | Moderate | 2 |
| [Epistemics of Agent Memory](https://arxiv.org/abs/2609.33013), v1, 26 September; manuscript June 2026 | +22.7% relative success, 7.17× compression, CI +1.89 to +11.34 points (§3.1). Revised forgetting precision 0.932/0.833 came with about 0.61 forgets per seed, versus about 30 (§3.2). External validity: ρ=−0.24, CI [−0.79,+0.49] (§5.4). | Weak | 2 |
| [How Strongly Should Task State Influence an LLM Agent?](https://arxiv.org/abs/2609.25686), 22 September 2026, v1 | At 235B, ten-step success was 0.38/0.55/0.84/0.98 across transcript/checklist/directive/enforcement (Table 2). Airline pass¹ rose 0.390→0.540; 35B’s change was inconclusive (Table 20). | Moderate | 2 |
| [The LLM Proposes, the Executive Disposes](https://arxiv.org/abs/2608.04066), 4 August 2026, v1 | Removing the commitment store changed measured abandonment from 0.00 to 1.00, with binding error 0.00; abandonment was defined for two of three removal seeds (§4.1). All 52 runs, including baselines, had zero level completions (§5, line 273). | Weak | 2 |
| [Push Your Agent](https://arxiv.org/abs/2605.23574), 22 May 2026, v1 | State tracking achieved 69.4–77.8% RepoScan success and 0.000 duplicate submissions (Table 1). On DataOps-lite, it achieved 25–50%; Letta reached 50.0% and 45.8% for two stronger models (Table 3). | Moderate | 2 |
| [PRO-LONG](https://arxiv.org/abs/2607.20064), v3, 12 October 2026 | NetHack mean best@5: 24.5% vs 13.5% and 11.3% vs 5.1%; ARC tool ladder: 23.1%, 27.2%, 38.3%, 41.2%. (§§3.2–3.3) | Moderate | 2 |
| [Continual Harness](https://arxiv.org/abs/2605.09998), v1, 11 May 2026 | Emerald Pro: 100% milestones at $130 vs 98% at $215; Flash-Lite adaptive: 3–13% vs 20%. (§4.4) | Moderate | 2 |
| [SPIKE](https://arxiv.org/abs/2605.18636), v1, 18 May 2026; cover 24 August 2026 | SPIKE vs CRADLE: 18.0% vs 13.0% success; 168.1k vs 372.5k tokens/task. Global memory alone: 12.3%; removing bank: 15.0%; graph: 14.3%. (Tables 2, 5) | Moderate | 2 |
| [AgenticSTS](https://arxiv.org/abs/2607.02255), v1, 2 July 2026; manuscript 24 August 2026 | Wins were 3/10 without scaffold, 4/10 prompt-only and 6/10 in each of three skill conditions. Fisher test for 3/10 vs 6/10: p≈0.37. (Table 2, §6.2) | Weak | 2 |
| [EmbodiedMemory-Bench](https://arxiv.org/abs/2609.28236), v1, 23 September 2026 | GPT-5.4-mini rose from 35.3% to 58.9% with EMem; removing event memory reduced interaction-failure success from 44.1% to 27.4%. Tables 2, 4 | Moderate | 2 |
| [AMA-Bench](https://arxiv.org/abs/2602.22769), v4, 27 May 2026 | AMA-Agent scored 0.5722; EMem 0.4610; MemoRAG 0.4606. GPT-5.2 long context scored 0.7226. Tables 4–5 | Moderate | 2 |
| [AgentOdyssey](https://arxiv.org/abs/2606.24893), v3, 23 November 2026 | Mean quest completion: long context 47.7%, retrieval plus short-term memory 30.0%, short-term memory alone 24.1%, fine-tuning plus short-term memory 19.3%. Table 2 Read scope: Both report full text; one could not read a frontier-model figure. | Weak | 2 |
| [The PokéAgent Challenge](https://arxiv.org/abs/2603.15563), arXiv v2, 17 March 2026 | Six completed all 15 milestones; Heatz finished in 40:13, Hamburg in 1:14:43 (§5.2). | Moderate | 2 |
| [Towards a Science of Scaling Agent Systems](https://arxiv.org/abs/2512.08296), arXiv v3, 8 April 2026 | Finance centralized: 0.349→0.631; PlanCraft independent: 0.568→0.170. Trace amplification was 17.2× independent versus 4.4× centralized (§4.2, Table 5). | Moderate | 2 |
| [The components of agent memory](https://www.anthropic.com/engineering/components-of-agent-memory), 6 November 2026 | Sonnet wrote 413 files and earned one badge; Fable wrote nine files plus global.md and earned four. Wiki scores rose 13%→48%; search plus wiki reached 61%, versus 53% search alone (lines 39–41, 65–67). | Moderate | 2 |
| [Agent harness design: 3 patterns](https://claude.com/blog/harnessing-claudes-intelligence), 2 April 2026 | BrowseComp: Sonnet 4.5 stayed at 43%, Opus 4.5 reached 68%, Opus 4.6 reached 84%. A memory folder raised Sonnet 4.5 from 60.4% to 67.2% on BrowseComp-Plus (lines 39–45). | Weak | 2 |
| [Project Vend: Phase two](https://www.anthropic.com/news/project-vend-2), 18 December 2025 | Discounts fell about 80% and giveaways halved; the CEO denied over 100 requests but approved them about eight times as often. Refunds tripled and credits doubled (“The CEO”). | Anecdote | 2 |
| [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents), 26 November 2025 | The example feature checklist contained over 200 initially failing features (“Feature list”). | Anecdote | 2 |
| [Building multi-agent systems](https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them), 23 January 2026 | Multi-agent systems reportedly use 3–10× the tokens; in the role-split experiment coordination exceeded task work (“Parallelization,” “Context-centric decomposition”). | Anecdote | 2 |
| [Reflexion](https://arxiv.org/abs/2303.11366), v4, 10 October 2023 | ALFWorld solved 130/134 tasks (§4.1). HumanEval Python rose 80.1%→91.0%; MBPP Python fell 80.1%→77.1% (Table 1). | Moderate | 3 |
| [ExpeL](https://arxiv.org/abs/2308.10144), v3, 20 December 2024 | Insights/retrieval scored 36%/31% on HotpotQA and 50%/55% on ALFWorld; combined, 39% and 59% (§5.2). GPT-3.5-written insights scored 32.0±0.4%; adding reflections scored 29.0±0.4% (Table 3). | Moderate | 3 |
| [Agentic Context Engineering](https://arxiv.org/abs/2510.04618), v3, 29 March 2026 | AppWorld averages: baseline 42.4, offline ACE 59.4 with labels and 57.2 without (Table 1). Test-normal full rewrite versus incremental update: 67.3→76.2 TGC, or 56.9→70.3 average (Table 18). | Moderate | 3 |
| [Dynamic Cheatsheet](https://arxiv.org/abs/2504.07952), v1, 10 April 2025 | Game of 24 GPT-4o baseline/empty/curated/retrieval-synthesis: 10%/19%/93%/99%; Sonnet baseline→retrieval-synthesis: 12%→14% (Table 1). | Moderate | 3 |
| [ReasoningBank](https://arxiv.org/abs/2509.25140), v2, 16 March 2026 | Flash success was 40.5/42.1/44.1/48.8%, respectively (Table 1). Shopping success-only versus including failures: 46.5→49.7%; AWM 44.4→42.2% (§5). | Moderate | 3 |
| [Experience-Following Behavior](https://arxiv.org/abs/2505.16067), v2, 10 October 2025 | Fixed versus add-all: 67.53/55.48, 16.75/13.05, 40.11/32.32 and 71.50/59.90% (Table 1). Strict-history deletion improves three agents but reduces regression from 70.95 to 69.80% (Table 2). | Moderate | 3 |
| [Agent Workflow Memory](https://arxiv.org/abs/2409.07429), v1, 11 September 2024 | WebArena AWM 35.5% versus BrowserGym 23.5% and accessibility-tree baseline 15.0% (Table 1). Mind2Web step success: 34.6% versus Synapse 30.6% (Table 3). | Moderate | 3 |
| [Self-Correction of Reasoning](https://arxiv.org/abs/2310.01798), v2, 14 March 2024 | GPT-4 GSM8K 95.5→89.0%, CommonSenseQA 82.0→80.0%, HotpotQA 49.0→43.0% after two intrinsic rounds; oracle stopping reaches 97.5/85.5/59.0% (Tables 2–3). | Moderate | 3 |
| [BALROG](https://arxiv.org/abs/2411.13543), v2, 1 April 2025 | NetHack o1-preview scored 1.57 ± 0.40% progression; the best individual run reached dungeon level 3 and experience level 4. | Moderate | 3 |
| [Plan-and-Act](https://arxiv.org/abs/2503.09572), v3, 22 April 2025 | Untuned planner: 17.16/23.63% versus 36.36/36.97% without one. Targeted augmentation: 42.42/43.63%; dynamic replanning: 48.48/53.94%. | Moderate | 3 |
| [Voyager](https://arxiv.org/abs/2305.16291), v2, 19 October 2023 | 63 items; fresh-world success 12/12 with the library versus 11/12 without it. Random curriculum reduced item count 93%; removing self-verification reduced it 73% (§§3.3–3.4). | Moderate | 3 |
| [Generative Agents](https://arxiv.org/abs/2304.03442), v2, 6 August 2023 | TrueSkill means: full 29.89, no reflection 26.88, observations only 25.64, human 22.95, no memory 21.21 (§6.5.1). | Moderate | 2 |
| [Why Do Multi-Agent LLM Systems Fail?](https://arxiv.org/abs/2503.13657), v3, 26 October 2025 | Human agreement κ=0.88; judge κ=0.77. ChatDev ProgramDev success rose 25.0% → 34.4% → 40.6% (Table 2, Table 5). | Moderate | 2 |
| [JARVIS-1](https://arxiv.org/abs/2311.05997), v3, 30 November 2023 | Diamond-group success was 8.99±2.68% versus DEPS’s 2.42±1.01% (Table 2); memory held 425 trajectories after four epochs (Fig. 7). | Moderate | 2 |
| [Introduction to the Soar Cognitive Architecture](https://arxiv.org/abs/2205.03854), May 8, 2022, Soar 9.6 | §10 reports roughly 50 ms decision cycles, runs of 30 days, and 8 yes, 5 partial and 2 no self-ratings. Appendix A reports RAT fit \(R^2=.98\), MSE.29, for work under review. | Weak | 2 |
| [Actions, Policies, Values, and the Basal Ganglia](https://nivlab.princeton.edu/wp-content/uploads/sites/938/2024/02/dawnivdayan2006.pdf), February 11, 2005 manuscript | Table 1 qualitatively contrasts habitual and goal-directed responses; no new numerical results. Devaluation sensitivity can persist in complex tasks or near reward (§3). | Moderate | 2 |
| [Production Compilation](https://www.ai.rug.nl/~niels/publications/HF-published.pdf), 2003 | Human–model fits: planes landed \(r^2=.97\), land time.98, queue time.91, and land keystrokes.87; move time was slower, with no fit reported (Figs. 4–6). | Moderate | 2 |
| [On Three-Layer Architectures](https://u.cs.biu.ac.il/~galk/teach/current/intsys/readings/on-three-layer-arch-tla-1998.pdf), undated chapter | Alfred placed second in one 1993 event and alone completed another; its contest code took three days by one person (§4). | Anecdote | 2 |
| [Commitment and Effectiveness of Situated Agents](https://ijcai.org/proceedings/1991/0013.pdf), undated proceedings text | At planning cost \(p=4\), bold commitment wins; at \(p=1\), normal wins in dynamic worlds and cautious matches bold. Target-loss replanning makes bold best across tested rates; reacting to any new hole is worse than blind commitment except at high change rates when \(p=2\) (§§3.3–3.4, Figs. 8–10). | Moderate | 2 |
| [The Utility Problem in Case-Based Reasoning](https://cdn.aaai.org/Workshops/1993/WS-93-01/WS93-01-026.pdf), 1993 | No experimental results. The abstract cites a theoretical parallel-selection bound of \(\Omega(\lg n)\) and distinguishes matching costs from search-space costs (paragraphs 2–3). | Weak | 2 |
| [Instrumental Rationality](https://plato.stanford.edu/entries/rationality-instrumental/), revised 2023-02-05 | Means may help bring about ends in several ways; coherence concerns an intended end and a believed necessary means (§§2–3). No experimental figures. | Weak | 2 |
| [Defeasible Reasoning](https://plato.stanford.edu/entries/reasoning-defeasible/), revised 2025-06-13 | A Ramsey-test conditional added to AGM trivializes revision; one proposed approach separates foundational from inferred beliefs (§4.3, lines 680–733). No empirical figures. | Moderate | 2 |
| [Handoffs](https://psnet.ahrq.gov/primer/handoffs), 2024-06-15 | I-PASS reduced preventable adverse events; SBAR results were mixed; Traffic Light was more accurate, faster and preferred. No effect sizes are supplied (lines 104, 116–117). Read scope: Both report the file read in full; primary studies not read. I checked disputed passages. | Weak | 2 |
| [Postmortem Culture](https://sre.google/sre-book/postmortem-culture/), 2017 | One release caused a four-minute outage; its engineer received two peer bonuses (line 111). The claimed reduction in outages has no figure (line 116). | Anecdote | 2 |
| [Epistemological Problems of Testimony](https://plato.stanford.edu/entries/testimony-episprob/), 2021 | Non-reductionism proposes a defeasible presumptive right (§1.2). A group report can assert a composite claim that no individual member previously believed or had evidence for (§6, lines 1244–1267). | Weak | 2 |
| [Knowledge How](https://plato.stanford.edu/entries/knowledge-how/), 2021 | HM improved mirror star tracing over 10 trials but needed a task reminder at each trial (§7.1, lines 1166–1193). | Weak | 2 |
| [Cognitive Architectures for Language Agents](https://arxiv.org/abs/2309.02427), v3, 15 Mar 2024 | SayCan has 551 grounding skills (§5). Table 2 lists no agent combining writable long-term memory with propose–evaluate–select planning. Read scope: Both reported reading the text; one said figures 1–5 and Table 1 mathematics were garbled or missing. | Weak | 2 |
| [Always-On Agents](https://arxiv.org/abs/2606.30306), arXiv v1, 29 Jun 2026 | Governed reducer passed 15/15 obligations; raw stores 7/15; extracted stores 4/15 and 3/15; no memory 0/15 (Table 18). Retrieval appeared in 269 works, rollback in 27 (Table 9). | Moderate | 2 |
| [Memory in the Age of AI Agents](https://arxiv.org/abs/2512.13564), v2, 13 Jan 2026 | Three forms, three functions and three dynamics; tables catalog benchmarks and frameworks rather than report the survey’s own performance results (abstract; Tables 1–7). | Weak | 2 |
| [Cradle](https://arxiv.org/abs/2403.03186), arXiv v3, 2 July 2024 | Cultivation: Cradle 4/5, comparison methods 0/5 (Table 6). OSWorld: 7.81% versus GPT-4o’s 5.03% (Table 4). | Weak | 2 |
| [More Memory, Worse Agents](https://arxiv.org/abs/2610.27406), v1, 19 October 2026 | Discarding guidance beat persistence by 3.3–28.0 points in four cells (Table 2). | Moderate | 3 |
| [Useful Memories Become Faulty When Continuously Updated by LLMs](https://arxiv.org/abs/2605.12978), v2, 29 August 2026 | At step 400, forced rewriting scored 43.2%, add/delete 64.0%, raw trajectories 76.6% (Table 5). | Moderate | 3 |
| [AutoMem](https://arxiv.org/abs/2607.01224), v1, 1 July 2026 | Base files → revised scaffold → specialist: Crafter 25.00 → 47.27 → 51.36; MiniHack 7.5 → 27.5 → 30.0; NetHack 0.42 → 1.57 → 1.85. Table 1 | Moderate | 2 |
| [COS-PLAY](https://arxiv.org/abs/2604.20987), v1, 22 April 2026 | Mean single-player reward was 924.4 versus GPT-5.4’s 717.4; Avalon 39.0% versus 65.0%, Diplomacy 2.96 versus 4.70. SFT with the final bank averaged 359.5 versus 409.5 without skills. Table 1 | Moderate | 2 |
| [PokeGym / G-EvoMAC](https://arxiv.org/abs/2604.08340), v2, 3 August 2026 | Success was 60.18%, versus Voyager 48.42% and zero-shot GPT-5.4 37.19%. Without visual, strategy or action evolution: 39.82%, 47.02% and 50.35%. Tables 2–3 | Moderate | 2 |
| [HyMem](https://arxiv.org/abs/2608.15703), v1, 16 August 2026 | DeepSeek-V4 scored 66.7% on GAIA and 61.3% on BrowseComp-Plus; Qwen BrowseComp-Plus fell from ReAct’s 32.0% to 25.3%. Removing memory cost 9.0 and 18.6 points in the respective ablations. Tables 1–2 | Weak | 2 |
| [The Compaction Cliff](https://arxiv.org/abs/2608.22752), v1, 24 Aug 2026 | /compact constraint recall fell from 0.53 to 0.10 over five rounds; TypeCompact stabilized at 0.96 (§4.3). Retail pass rates were 37.7% versus 28.6% for full policy (§4.5). | Moderate | 2 |
| [When Memory Lies](https://arxiv.org/abs/2608.04574), v1, 5 Aug 2026 | GPT-4o L2 deaths fell from 74.4% without filtering to 31.6% with OMCD; no memory had 28.0% deaths (Table 3). Vision detection F1 ranged from 0.067 to 0.887 (§5.2). | Moderate | 2 |
| [MemDerive](https://arxiv.org/abs/2610.25373), v1, 18 Oct 2026 | Memory systems scored 30.41–48.30% versus BM25’s 58.28% (§5.2). Explicit changes refreshed 82.4% versus 41.1% for implicit changes (§5.4). | Moderate | 2 |
| [When Does Memory Help?](https://arxiv.org/abs/2609.05441), preprint v1.1, 26 Jul 2026 | Pilot hard-tier fact store scored 0.75–1.00 versus retrieval’s 0.35–0.70 (Table 1). Across the main grid, retrieval scored 0.30–0.95 and fact store 0.70–1.00 (§5.7). | Moderate | 2 |
| [STALE](https://arxiv.org/abs/2605.06527), v1, 7 May 2026 | CUPMem scored 68.0%, plain GPT-4o-mini 8.7%; CUPMem’s direct/indirect advice scores were 32%/43%. Table 2 | Moderate | 2 |
| [DISCERN](https://arxiv.org/abs/2611.15729), v1, 11 November 2026 | Equal-pillar macro 0.861 versus 0.806; entity resolution 0.800 versus at most 0.400; abstention F1 0.924 versus 0.802. Tables 1–2 | Moderate | 2 |
| [TraceRetain](https://arxiv.org/abs/2606.29178), v1, 28 June 2026 | Under synthetic noise, CEM solved 97/100, FIFO 94/100; Precision@5 changed 16.9%→16.6% for CEM and 15.8%→3.8% for FIFO. Table 2, §5.2 | Weak | 2 |
| [ReMe](https://arxiv.org/abs/2512.10696), v2, 15 April 2026 | BFCL 8B Pass@4: keypoints 65.77%, trajectories 60.00%; deletion raised 64.66%→68.00%, while Avg@4 rose 45.00%→45.17%. Tables 2–3 | Moderate | 2 |
| [How Much Should an Agent Remember?](https://arxiv.org/abs/2611.26361), v1, 19 November 2026 | gpt-oss: 39.9% without memory, 51.2% with 199 guidelines, 55.4% with about 29 retrieved; DeepSeek: 79.8% to 89.3% (Table 2). | Moderate | 2 |
| [AdMem](https://arxiv.org/abs/2611.20605), v1, 16 November 2026 | AdMem 441/707, ReAct 388, AWM 312; PDDL alone survives domain-level correction (Table 2; §3.3). Jericho procedural-only: 4–6/20 versus ReAct 8/20 across epochs (Table 3). | Moderate | 2 |
| [Can LLM Agents Organize Their Own Memory?](https://arxiv.org/abs/2611.11929), v1, 9 November 2026 | Scores 88.96%, 54.02%, 76.50%; gains over strongest baselines 2.66, 3.10, 2.00 points (Tables 2–4). Removing Source costs 8.64 points (Table 9). | Moderate | 2 |
| [R²-Mem](https://arxiv.org/abs/2605.13486), v1, 13 May 2026 | Qwen-7B LoCoMo F1: GAM 45.77, external evaluator 51.35, Self-Evo 49.76 (Table 10). Low-quality-only advice beats high-quality-only in four categories (Table 4). | Weak | 2 |
| [MemSIF](https://arxiv.org/abs/2608.01742), v2, 5 August 2026 | LoCoMo/Qwen3-4B accuracy: full 75.62%, query-local only 73.09%, no ActiveFact 67.43% (Table 4). Low-salience evidence appeared in 430/1,035 critical pairs (Table 8). | Moderate | 2 |
| [MemForest](https://arxiv.org/abs/2605.23986), v4, 23 November 2026 | Qwen3-30B LongMemEval-S: 81.80% versus Zep Local’s 71.00% (Table 2). Tree versus fact-log point accuracy stayed within 1.1 points, *p* ≥ 0.18; range recall was 0.42 versus 0.18 across 499 constructed requests (§8.4). | Moderate | 2 |
| [MemP](https://aclanthology.org/2026.findings-acl.866/), ACL 2026 | GPT-4o ALFWorld test success rose 42.14%→77.86%; TravelPlanner hard-constraint score fell 12.88→9.76 (Table 1). GPT-4o-to-Qwen2.5-14B transfer raised delivery 91.4→96.6 (Fig. 5a). | Moderate | 2 |
| [Memory Management](https://aclanthology.org/2026.acl-long.27/), ACL 2026 | Strict EHR history-based deletion: 38.67%→42.06%, with 1,012→784 records. With a coarse evaluator, driving success fell 36.92%→34.00% (Table 2). | Moderate | 2 |
