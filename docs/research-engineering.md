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
