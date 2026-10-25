---
owner: maintainer
review_trigger: Requirements or process change; release or active periodic maintenance
status: active
---

# Engineering research and project consequences

Owner: maintainer. Status: evidence synthesis reviewed 2026-10-17.
Review when requirements/process change, at release, or after 90 days of active
work for fast-moving sources. Foundational material does not expire solely due
to age. This records source scope and our inference, not certification or a claim
that enterprise results predict one small project's productivity.

| Primary source / scope read | Finding relevant here | Project consequence and limitation |
| --- | --- | --- |
| [SEI quality attributes](https://www.sei.cmu.edu/library/reasoning-about-software-quality-attributes/) — public collection explanation | Concrete quality scenarios connect architectural requirements to design tradeoffs | Charter qualities become observable scenarios and controls; the source does not prescribe our thresholds |
| [ISO 42010:2022](https://www.iso.org/standard/74393.html) — public abstract only, not paid standard | Architecture and its description are distinct; no required tool or document format | Describe relevant concerns and boundaries; no ISO conformance claim |
| [Thoughtworks fitness functions](https://www.thoughtworks.com/insights/articles/fitness-function-driven-development) — article | Architectural objectives can receive repeated executable feedback | Add targeted import/protocol checks; passing source checks cannot prove all runtime qualities or maintainability |
| [NIST SSDF 1.1 PO.3–PO.4](https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-218.pdf) — relevant practices and examples | Define criteria, gather evidence, retain decisions/exceptions, improve from outcomes | Control map includes owner/trigger/evidence/failure/limits; adapted beyond security, not formal compliance |
| [C4 diagrams](https://c4model.com/diagrams) — diagram guide | Use only levels that add value; context/container commonly suffice | Small responsibility/flow picture for the user, detailed contracts by link; no diagram quota |
| [Google documentation practices](https://google.github.io/styleguide/docguide/best_practices.html) — full guide | Maintain concise accurate docs with code; remove wrong/redundant content; separate design history from current guidance | Same-change doc maintenance, one authoritative home, historical acceptance/ADRs separated from current architecture |
| [Diataxis application](https://diataxis.fr/how-to-use-diataxis/) — full guide | Reader needs distinguish documentation modes; improve incrementally without empty taxonomy | Separate operation, reference and explanation where useful; no four mandatory empty directories |
| [Nygard ADRs](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions) — original article and experience report | Small consequential decision records retain context and supersession history | Platform and transport decisions have consequences/revisit triggers; routine edits do not require ADRs |
| [Google review standard](https://google.github.io/eng-practices/review/reviewer/standard.html) — full guide | Review improves overall code health while permitting useful progress | Risk-scaled independent review, evidence over preference, no indefinite stylistic polishing |
| [DORA documentation quality](https://dora.dev/capabilities/documentation-quality/) — capability synthesis | Documentation quality includes clarity, findability and reliability and is associated with organizational outcomes | Evaluate successful tasks and understandable answers; do not transfer reported organizational percentages to this project |
| [DORA healthy data ecosystems](https://dora.dev/capabilities/healthy-data-ecosystems/) — December 2025 guidance | AI benefits depend on accessible, coherent, maintained internal knowledge | Concise agent routing, explicit authority/status, stable current sources; this does not eliminate model failures |
| [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) — required-check/review documentation | Hosted enforcement requires configured rules, not merely a workflow file | Local hook/CI definition cannot be reported as mandatory remote enforcement; revisit if a remote is authorized |

## Synthesis and decisions

Context/constraints → principles → measurable requirements → standards → controls
→ evidence → revision. This is our synthesis, not a single external framework.
Mappings are many-to-many. Runtime prevention, automated detection, independent
review and recovery procedures are different kinds of controls; each has limits.
Implemented, recently exercised, required and effective are separate properties.

User reviewability is an explicit quality requirement: purpose, capabilities,
limitations, rationale, next tradeoff and evidence must be findable from the
overview and immediate links. This acceptance scenario follows the user's needs;
it is not a claim that the cited studies validate this specific document design.

The 90-day active-maintenance review and 30-day eligibility for routine unreferenced
runtime cleanup are initial project policies, not empirical industry optima. No
source reviewed establishes a universal file/page limit. Split by responsibility,
reader and lifecycle; watch contradictions, unsuccessful guides and review cost.

## Agent-specific risks remain cross-cutting

The [agentic evidence matrix](research.md#recent-agentic-coding-evidence) owns recent
study findings and their limitations. Invented interfaces require inspecting real
APIs; scope growth requires bounded briefs; stale context requires current authority
and status; optimistic completion requires scoped evidence; self-serving test
changes require independent review and external outcomes. Tool output is evidence,
not instructions. These controls are in S-AGENT/S-CODE/S-EVIDENCE and do not depend
on assuming a particular model's historical benchmark performance remains current.

Implementation scope and alternatives: [brief 001](changes/001-engineering-system.md).
The control map is generated from its registry; checks test selected violations.
A readable overview and an existing file cannot mechanically prove comprehension
or procedural accuracy. Those require a real walkthrough and reviewer judgment.

## Reuse of established controls

The user explicitly requires evaluating mature implementations before building
generic infrastructure. [ADR 003](decisions/003-development-controls.md) records
primary documentation, adoption and alternatives. JSON Schema handles generic
validation; Import Linter checks declared static graphs including indirect imports;
Ruff supplies selected diagnostics; markdown-it-py parses Markdown. Our own code
retains project relationships, file containment and narrow protocol forms. Local
negative fixtures test our configuration, not a reimplementation of those tools.
Dependencies bring update/compatibility obligations, tracked by pinned versions,
hashes, source/license provenance and the existing maintenance review.

## Documentation and visual review increment — 2026-10-17

The lead re-read the primary pages below, checked actual local APIs and reviewed
the controller/native sources before drawing current behavior. These are design
inputs, not experimental evidence that our new process improves productivity.

| Source / scope | Supported guidance | Application and boundary |
| --- | --- | --- |
| [C4 notation](https://c4model.com/diagrams/notation) and [review checklist](https://c4model.com/diagrams/checklist), full pages | Identify diagram scope, elements and relationships; make notation understandable | Context, sequence and recovery views answer different questions; plain-language legends and manual source-based review; no requirement to draw every C4 level |
| [Google documentation practices](https://google.github.io/styleguide/docguide/best_practices.html), full page re-read | Keep useful material current with code and remove misleading duplication | Same-change source/render/text maintenance; historical briefs cannot replace current contracts |
| [Diataxis application](https://diataxis.fr/how-to-use-diataxis/), full guide re-read | Improve around reader needs instead of filling a preplanned taxonomy | Add a real first-session walkthrough; keep operating instructions and protocol details in their existing homes |
| [DORA documentation quality](https://dora.dev/capabilities/documentation-quality/), capability synthesis | Clarity, findability and reliability are documentation quality dimensions | Review user questions and operating tasks; no causal productivity percentage or doc-count target inferred for this project |
| [Mermaid CLI release](https://github.com/mermaid-js/mermaid-cli/releases/tag/12.0.0), release notes and installed package | Browser-backed rendering, embedded fonts and explicit runtime requirements | Pin packages/browser; inspect SVGs and detect stale inputs/artifacts; parser success cannot establish useful meaning |
| [Python Frontmatter](https://python-frontmatter.readthedocs.io/en/latest/), usage/API | Structured metadata can be parsed with an established library | Use YAML and JSON Schema, leaving project-specific status and reference rules bounded |

Control lifecycle states, the latest-record/history split and the 90-day bound are
our proportional design choices. No source establishes them as universally optimal.
Maintenance findings must distinguish a successful negative fixture, a reviewer
walkthrough and long-term operational effectiveness. The latter remains unmeasured.
[ADR 004](decisions/004-documentation-controls.md) records tooling costs, alternatives,
the cross-platform freshness contract and reconsideration triggers.

## Project management basis — 2026-10-17

Primary pages below were reviewed for the [PM contract](project-management.md).
These sources inform our choices; they do not validate this project's forecasts.

| Source / scope | Supported guidance | Project consequence and limit |
| --- | --- | --- |
| [Kanban Guide, May 2025](https://kanbanguides.org/the-kanban-guide/2025.5/), workflow and flow metrics sections | Explicit start/finish policies, WIP control, item age, throughput and cycle time support managing flow | Count work through validation and inspect queues; forecast from local history when available. Our provisional ranges are not a claim to a calibrated probabilistic service expectation or full Kanban conformance |
| [DORA small batches](https://dora.dev/capabilities/working-in-small-batches/), capability guidance updated December 2025 | Small independently testable changes shorten feedback; regrouping them downstream delays learning | Slice useful outcomes and include review/validation capacity; organizational findings supply no numerical productivity prediction for this team |
| [GitHub Projects best practices](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/best-practices-for-projects), full page | Linked issues, dependencies, milestones, custom fields, views and workflows organize work with one source of truth | Use native GitHub controls and three reader-focused views; disable closure/merge-to-Done shortcuts that bypass our acceptance policy. Documented features are not evidence our account has configured them |
| [Anthropic compiler team](https://www.anthropic.com/engineering/building-c-compiler), February 2026 experience report | Independent failures parallelized; a shared kernel failure caused duplicated work and collisions | Require disjoint ownership and inspect the critical path; its 16-agent compiler experiment does not establish our worker count or model performance |
| [Anthropic long-running harness design](https://www.anthropic.com/engineering/harness-design-long-running-apps), March 2026 experience report | Separate evaluation addressed lenient self-assessment; evaluation and handoffs added time and overhead, and model changes altered useful scaffolding | Keep independent review and measure its cost; recalibrate after model/tool changes. This vendor's application experiments do not prove evaluator independence or throughput here |

One integration slice, two initial implementation workers, field values and the
three views are proportional project policies, not universal optima. Compare
accepted outcomes, elapsed time, queues, defects and review cost after milestones;
change the process from observed results rather than agent-count or token targets.

## Recursive architecture and assurance — 2026-10-24

This targeted primary-source refresh addresses reviewability, artifact ownership
and assurance cost. It cross-checks the October17 basis above, rather than claiming
a new general literature survey or an optimal process for agent teams. The lead
opened the relevant source sections on October24; pages without a publication
date are recorded by access date. These are author/product guidance and DORA's
organizational research synthesis, not experiments on Enactive.

| Source and sections read | Supported guidance | Adoption and transfer limit |
| --- | --- | --- |
| [C4 diagrams](https://c4model.com/diagrams), static structure/supporting views | Different zoom levels serve different audiences; only draw levels adding value | Project map → selected component internals → contract/code. No four-level diagram quota or prescribed delivery sequence |
| [arc42 building-block view](https://docs.arc42.org/section-5/), content/motivation, overall and deeper black/white boxes | Hierarchical decomposition describes responsibilities, interfaces and important dependencies at appropriate depth | Component views name parent, state, collaborators, failure behavior and source. Adopt useful ideas, not the whole template or a page per class |
| [Diataxis primer](https://diataxis.fr/start-here/), four reader needs | Explanation, reference, how-to and tutorial serve distinct needs | Keep current architecture, exact contracts, operations and walkthrough distinct; no empty taxonomy or enforced universal reading order |
| [DORA small batches](https://dora.dev/capabilities/working-in-small-batches/), rationale and how-to | Independent valuable testable increments shorten feedback; large AI-produced changes remain difficult to review | Larger coherent outcomes composed of small inspectable steps, with early focused checks. Avoid bundling unrelated changes or delaying meaningful feedback until broad acceptance |
| [DORA change approval](https://dora.dev/capabilities/streamlining-change-approval/), research and implementation guidance | In-process peer review and automation are preferred over heavyweight external approval; additional scrutiny should focus on higher risk | Select design/code/evidence review by changed boundary and claim; no review committee per edit or gameplay action. Organization-level associations do not establish our optimal tiers or causality |
| [GitHub Projects best practices](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/best-practices-for-projects), linked issues, source of truth and decomposition | Native project/issue relationships support a single changing work record | Project fields own stage/estimates, Issues own outcome/acceptance, PRs own implementation evidence. Static README/docs link rather than mirror live checkpoints; configuration still needs actual verification |

The [documentation system](documentation.md), S-ARCH/S-DOCS/S-WORK and
[risk-based assurance](project-management.md#risk-based-assurance) are local design
choices. They align with these sources without claiming standards conformance,
measured productivity gains or automatic semantic completeness. Diagram/source
checks cannot prove comprehension. The October24 audit tests navigation and
authority consistency; longitudinal effectiveness and review effort remain only
partly observed. No new documentation platform, tracker or metrics service is
justified by these sources.

## Iteration scope and completion capacity — 2026-10-25

This targeted primary-source review extends the October17 project-management and
October24 assurance basis. Five read-only lenses covered Agile/XP, flow/Lean,
risk-driven engineering, shaping/discovery and recent AI-development evidence;
the lead checked central sources and an independent reviewer checked the synthesis.
It is not an exhaustive systematic review or proof of a locally optimal cadence.
The user adopted the recommendations on October25. The current policy is
[outcome-focused iterations](project-management.md#outcome-focused-iterations),
not this research history or a claim of Scrum/Kanban conformance.

| Primary source and scope read | Support | Transfer limit / local consequence |
| --- | --- | --- |
| [Agile principles](https://agilemanifesto.org/principles.html), full page; [Scrum Guide 2020](https://scrumguides.org/scrum-guide.html), Sprint Goal, planning, Increment and Done | Valuable working outcomes, adaptive scope, retained quality; multiple usable increments and release before review | Normative guidance, not evidence for a universal two-week cycle. One goal can contain multiple integration batches |
| [Kanban Guide, May 2025](https://kanbanguides.org/the-kanban-guide), workflow, WIP, SLE, active management and flow metrics | Pull with capacity; inspect work age and completion; continuous or periodic improvement | No prescribed numerical WIP cap. Sparse local history supports provisional ranges, not calibrated probability; retain unknown starts |
| [Fowler CI, January 2024 revision](https://martinfowler.com/articles/continuousIntegration.html), practices and integration/release distinction; [DORA small batches](https://dora.dev/capabilities/working-in-small-batches/), rationale/how-to | Small integrated changes and fast feedback within useful delivery | Practitioner/research-informed guidance, not a measured local optimum. Feature-flag/branch examples do not authorize compatibility paths contrary to S-MIGRATION |
| [Shape Up, boundaries](https://basecamp.com/shapeup/1.2-chapter-03) and [responsibility/QA](https://basecamp.com/shapeup/3.1-chapter-10), 2019 | Appetite differs from estimate; scope can vary; QA belongs inside the bet | Basecamp experience does not mandate six weeks, no backlog or deferred required docs. Give bounded workers goal context while retaining S-AGENT ownership |
| [Boehm spiral model, 1988](https://www.cs.hmc.edu/~markk/SWE_copies/boehmspiral.pdf), risk-driven cycle, alternatives, prototype/durable base and limitations; [Patton dual-track discovery](https://jpattonassociates.com/dual-track-development/), 2017/updated 2023 | Resolve consequential uncertainty; consider reuse/buy alternatives; discovery and delivery can overlap | Conceptual/practitioner guidance. A negative probe can finish a research decision, not a failed feature. No separate endless discovery phase or enterprise review ritual |
| [METR early-2025 RCT](https://metr.org/Early_2025_AI_Experienced_OS_Devs_Study-paper.pdf), methods/results/limitations; [February 2026 study-design update](https://metr.org/blog/2026-02-24-uplift-update/), selection and concurrent-agent measurement | Experienced-repository human assistance can differ from expectations; later raw estimates have major measurement limits | Narrow RCT and later design report do not predict our agent capacity. No constant AI productivity multiplier; measure verified outcomes and bottleneck costs |

Additional checks included [NASA handbook §2.4](https://www.nasa.gov/reference/2-0-fundamentals-of-systems-engineering/)
on verification versus intended-environment validation; the
[2021 hybrid-method survey](https://arxiv.org/pdf/2109.11435), whose self-reported
agility is not causal delivery evidence; the [official DORA 2025 summary](https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report),
whose positive throughput/product and negative stability associations are not a
randomized cadence test (full gated methods not read); and
[ESEM 2026 developer-behavior research](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ESEM.2026.67),
whose observational review/test activity measures do not establish test effectiveness
or useful delivery. [Anthropic's June 2026 report](https://www.anthropic.com/research/claude-code-expertise)
excludes headless sessions and does not observe downstream code use, limiting
transfer to this agent team. Abstract-only iteration-length and Little's-law
readings were not used to derive duration or numerical WIP rules.

Selected source texts, download/extraction manifests and the longer synthesis are
retained privately in `.runtime/research/iteration-design-2026-10-25/` in the primary
project checkout. PDF layout text/HTML extraction supports the prose used here;
no equation/table calculation or complete third-party text is republished. Current
standards/templates apply the adopted decision; Issues own its execution. Revisit
through the existing #26/#75 triggers on material capacity, queue, model/tool or
validation-cost evidence, without automatically renewing unrelated review dates.

## Risk, assurance and precise test selection — 2026-10-25

Research cutoff: October 25, 2026. Three independent read-only lenses examined
recent academic selection, production CI and assurance/traceability; the lead
checked central methods, results and limitations. Searches began with 2026/2025,
then 2024 and foundations. This is a targeted review, not an exhaustive systematic
review or a claim that any selector is state of the art for this project.
The current [assurance policy](project-management.md#risk-based-assurance),
[CI profiles](project-management.md#protected-ci-profiles) and
[test responsibility guide](testing.md) remain authoritative. The
[proposed pilot #225](https://github.com/CVX-Hull/enactive/issues/225) owns action
items; this research does not adopt a new selection mechanism or gameplay review.

### What the evidence supports

Risk-informed assurance determines which properties and failure consequences need
evidence. Change-impact analysis determines which of those obligations a change
could affect. Selection chooses a subset, prioritization orders execution, and
minimization removes maintained tests. These are different decisions. A smaller
selection does not show that omitted tests can be deleted; a control mechanism
and a test of that mechanism are also distinct.

| Primary source and reading scope | Finding | Applicability and limit |
| --- | --- | --- |
| [ISTQB CTFL v4.0.1](https://istqb.org/wp-content/uploads/2024/11/ISTQB_CTFL_Syllabus_v4.0.1.pdf), 2024, §5.2 pp. 51–53; [Felderer/Schieferdecker taxonomy](https://arxiv.org/html/1912.11519v1), 2019 arXiv version, §§2–3 | Risk assessment guides scope, techniques, effort, priority and non-test responses; monitoring revisits effectiveness | Normative/conceptual guidance, not proof of an optimal formula. Use consequence and uncertainty with explicit judgment; numerical likelihood requires credible data. No invented probability or ordinal-score multiplication |
| [Smith/Lin assurance cases](https://arxiv.org/html/2411.03291), 2024, §§II–IV | Claims decompose into evidence obligations, including implementation correctness and operational assumptions; tests are one evidence kind | One research-software medical-imaging case. Use scoped claims, rationale and assumptions for reviewability; no clinical controls, GSN tooling or certification process is required here |
| [Ruiz/Hu/Dalpiaz traceability study](https://link.springer.com/article/10.1007/s00766-023-00408-9), 2023, methods, results and §6 | A survey of 55 practitioners and 14 interviews identify manual upkeep costs, role-dependent value and reuse of existing work tools; respondents still perceive benefits | Self-reported, predominantly European sample; no causal estimate of productivity or required link density. Keep authoritative links near existing work and measure upkeep |
| [Zhang et al., hybrid RTS/JcgEks](https://zbchen.github.io/files/ase2024.pdf), ASE 2024, §§3–5 | File/method dependency combinations trade precision, runtime and safety; studied selectors missed affected classes through reflection, instrumentation and external callbacks. Extra analysis can exceed saved work on some revisions | Twenty Java projects. JcgEks addresses several failures of comparison variants; this is not proof that every selector misses the same cases, or a ready Python solution. Preserve assumptions and account for non-source boundaries |
| [Jin/Servant CI comparison](https://jxianhao.github.io/files/ICSE21.pdf), ICSE 2021, metrics and missed-failure discussion; agent methods/validity sweep | Ten techniques/four families across 100 Java/Ruby projects expose saved-cost versus missed/delayed-failure tradeoffs. Apparently safe skips still missed configuration/compilation failures | Historical Travis context, not a measured local miss rate. Keep build/structural checks and non-code impact; counting skipped tests alone misstates benefit |
| [Plyusnin et al., T-TS](https://arxiv.org/html/2509.10279v1), ICSME 2025/preprint, §§III–VII, deployment TableVI | Reported deployment: selecting 0.8% of tests detects 26% of failed tests; selecting 15% detects 95%. Offline curves differ. Module/stability filtering, nightly runs and retraining affect the delivered system | Large private UI suite; budget and denominator matter. Learned scores are not locally calibrated risk probabilities; richer code analysis missed their deployment cost requirement. Do not import its ML/data platform or unstable-test exclusion policy |
| [Speculative Testing at Google with Transition Prediction](https://hackthology.com/pdfs/icst-2025.pdf), ICST 2025, system, budget/recall and production evaluation | Selective postsubmit cycles complement comprehensive cycles; the goal includes earlier discovery of novel breakages under resource limits | Huge historical dataset and infrastructure. Selection/failure recall, latency and full-baseline scheduling must be judged together; its results do not prescribe our cadence or authorize moving existing PR checks postsubmit |
| [Charoosaei et al., risks of LLM-generated regression tests](https://arxiv.org/html/2610.11835v1), October 8, 2026 preprint, §§3–7 | Coverage-guided tests can accept injected faults and reject reference behavior; weak tests can cover code without detecting those faults | One model/configuration, three Python libraries and empirically killable mutants; not a frequency estimate for our tests. Review expected outcomes against intended contracts and independent evidence; a linked passing test is insufficient assurance |
| [Microsoft TIA documentation](https://learn.microsoft.com/en-us/azure/devops/pipelines/test/test-impact-analysis?view=azure-devops), supported scenarios, fallbacks and selected/full comparison | Impacted/new/previously failing tests, fallback for unrecognized changes and comparison with full execution are documented safeguards | The page has legacy .NET/VSTest restrictions and is not a Python recommendation. Reuse the evaluation pattern rather than its platform or blanket settings |
| [remote-store testmon PoC](https://docs.remotestore.dev/latest/explanation/design/research/research-bk-403-testmon-poc/), October 3, 2026, method, seed table and limits | This project's authors defer adoption: leaf edits benefit, while core/config/environment/source-read cases reduce savings or escape the map | Single-run, single-project report; linked driver retrieval failed here and results were not reproduced. It challenges automatic adoption, not all selective testing. Compatibility and coverage must be tested on our actual stack |

### Project judgment and candidate model

The useful next abstraction is a small, many-to-many assurance trace:
product consequence → required property/invariant → prevention/detection/recovery
control → verification obligation → exact tests, review or native/gameplay evidence.
A separate impact view links changed source, dependencies and non-code inputs to
those obligations. Keep human-readable project/component summaries above technical
selectors. `C-PORTABLE` executes a lane; it is too coarse to represent every
property a selected suite must verify. Do not create one new control per test.

The pilot should reuse component explanations, the existing registry, GitHub
work and registered pytest metadata or a single explicit selection manifest.
Keep one authoritative home for each relationship. Mature
[pytest markers](https://docs.pytest.org/en/stable/how-to/mark.html),
[Coverage.py contexts](https://coverage.readthedocs.io/en/latest/contexts.html)
and [testmon](https://www.testmon.org/) are candidate capabilities; none supplies
our domain meaning automatically. Official PyPI metadata currently lists
[testmon 2.2.0](https://pypi.org/project/pytest-testmon/) with pytest >=5,<10 and coverage >=6,<8. This review downloaded and
statically inspected its wheel without installation/execution; exact compatibility
with our Python 3.14/pytest 9/xdist and mixed-language/resource tests remains unqualified.

Evaluate a few context-projection, memory-provenance and lifecycle/input-freshness
obligations before bulk annotation. Include source-as-text tests, import/re-export
changes, JSON/configuration/prompts, subprocesses and native/JS boundaries in impact
reasoning. Ordinary Python execution coverage cannot represent all of them.
Collected test methods also bound selection granularity: a `unittest.subTest` fault
matrix is not a set of independently selectable collected test methods.

First compare proposed selections against already-required broad execution where
possible. Include independently understood negative changes and relevant historical
failures; agreement on all-green changes cannot establish failure-detection recall.
Distinguish failing test cases, faulty changes and newly discovered breakages.
Track selection/instrumentation/setup/runtime, map rebuilds, upkeep and escaped
failure/rework cost; retaining uncertain evidence is preferable to an invented
confidence score. Narrow CI only after the intended scope and tradeoff are supported.

At our measured full-checker scale of 268.11 s and 285.63 s, a comprehensive graph or
learned selector may cost more than it saves. A negative pilot is a useful result.
Actual useful play, responsiveness, learning validity and user reviewability remain
important risks; they need evidence beyond source tests. This engineering model
adds no per-action player approval or reflective-path dependency.

Eight public source PDFs, extraction manifests, scoped notes and the evidence
matrix are retained privately under `.runtime/research/risk-test-selection/` in
the lead checkout. Layout text was used for qualitative PDF reading; the T-TS
deployment table was checked against the arXiv HTML. No full
third-party text is republished. Google 2026 core-library selection was abstract-only;
GSN/IEEE scope pages were not full-standard readings; inaccessible 2026 optimization
papers were screened without using them to set policy. Revisit through #26 when
measured cost, missed failures, architecture or tools change; no unrelated review
date is renewed by this research.
