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
