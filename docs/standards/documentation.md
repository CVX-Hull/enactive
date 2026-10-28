---
owner: maintainer
review_trigger: Changes to this standard, its controls or engineering constraints
status: active
---

# S-DOCS Useful maintained documentation

Update authoritative guidance with behavior in the same change. Active normative
docs identify owner, status and review trigger; historical reports identify date
and scope. A timestamp is not verification. Keep README/overview concise, with
progressively detailed links. Split by reader, authority, cohesion or change
frequency; no universal line/page count or documentation-volume target applies.
Use a diagram only when it clarifies a boundary or interaction. Generate mechanical
reference from an existing authoritative structure when it reduces duplication.
On a material documentation change, C-USABILITY walks the intended reader task:
find the current rule and owner, understand its consequence, and trace the needed
detail without reconstructing history. Mixed-purpose or oversized references that
prevent this focused review need decomposition; a table of links alone is insufficient.
Documentation generators and checks follow S-CODE's reuse decision and review
requirement; stewardship/schema rules do not justify rebuilding their parsers.

Stewardship metadata lives in YAML front matter, checked by `tools/documents.py`:
all Markdown in docs/ and README/AGENTS/NOTICE identifies owner and status. Active
or proposed material needs a review trigger; historical records need date and
scope; superseded material needs scope and a repository-relative replacement.
Proposals are not implemented contracts. Accepted ADRs are dated rationale;
architecture/protocol remain authoritative about current behavior. Metadata is
not a claim of accuracy. Review current guidance at C-MAINTENANCE's recorded due
date and earlier on its page-specific trigger; do not refresh dates without work.

Choose explanations for understanding, procedures for doing, reference for exact
contracts and walkthroughs for learning. Add these when a real reader need exists;
do not create empty categories. Significant change briefs show before/after user
consequences, affected boundaries, alternatives and evidence. Use capability tables,
dated screenshots or demonstrations when they convey more than additional prose.

Component assurance explanations follow the same review hierarchy. Keep one current
home for responsibility-level risks/evidence links; refer to contracts, control
definitions and native test metadata rather than mirror them. Maintain links and
limits with changed behavior/assertions, and simplify low-value mapping detail.
The [documentation map](../documentation.md) and [testing guide](../testing.md) own the
navigation and selection method, not a second live backlog or coverage database.

Development notes reference existing admissions, ledgers and artifacts. Consolidate
acceptance reports and selected public evidence at meaningful integration/acceptance
checkpoints; a stopped menu attempt needs a concise retained finding, not a new
report package. Current contracts change with behavior; historical observations
stay historical. Follow the workflow's evidence cadence without duplicating its
procedures here.

Respect the [documentation/GitHub authority split](../workflows/authority.md#authority-and-review-surfaces).
C-REVIEW checks that an updated summary links its authoritative source instead of
mirroring live fields or accumulating another run narrative. Retire obsolete
summaries through ordinary Git edits; retain dated evidence and owned action items.
Use the [documentation roles and lifecycle](../documentation.md) when deciding where
an artifact belongs. Dated acceptance/audit records are historical, even when their
observations remain relevant; the existing metadata check enforces that narrow
role rule. Incorporate adopted design into current architecture/contracts, transfer
remaining actions to GitHub and retain its brief as dated rationale. Partial
proposals identify their remaining proposal scope. No new attempt paragraph is
required in current architecture or the overview.

## Visual explanations

Each diagram must answer a named reader question at a stated scope, with a title
and current/proposed/historical status in its host page. Explain element types,
arrow meanings and abbreviations. Label relationships and authority boundaries;
separate logical responsibilities from actual process boundaries. Preserve relevant
failure/recovery paths and limits, including uncertainty. Never use color alone
to convey meaning. Provide a text equivalent and an authoritative contract link.

Use versioned Mermaid sources and generated SVGs, with accessible titles and
descriptions. Update source, rendering and explanatory text together. Render with
the pinned local tool; inspect the result at ordinary window width for readable
labels, clipping and ambiguity. For a changed boundary/flow, an independent reviewer
checks the visual against the contract and relevant implementation. The lead
records the inspection in acceptance; neither parsing nor hashes prove meaning.
Retire or supersede visuals with their parent document. Avoid duplicate copies of
the same diagram and extra detail that forces the user to reconstruct the big picture.

The user must be able to find purpose, current capabilities/limits, architectural
rationale, next change/tradeoffs and supporting evidence from the overview and
its immediate links. Preserve consequential limitations in plain language.
Retire inaccurate guidance; mark superseded decisions with replacements and keep
useful history. Archived plans/reports are not current instructions.

[Standards index](../engineering.md).
