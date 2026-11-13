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
not a claim of accuracy. Review a current page when its own review trigger fires.

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
role rule. Active pages hold method, contracts and current state, not dated run
records: run outcomes and result tables, dated owner decisions and admission
procedures go in a dated acceptance record, and the active page keeps the method,
one line per checkpoint and a link. Per-run quantities live in tracked data
(S-EVIDENCE), and generated indexes list every dated acceptance record and change
brief from its front matter, with a staleness check. C-REVIEW applies this rule to
changed pages. Incorporate adopted design into current architecture/contracts, transfer
remaining actions to GitHub and retain its brief as dated rationale. Partial
proposals identify their remaining proposal scope. No new attempt paragraph is
required in current architecture or the overview.

## Names

A name says what the thing is, in words a reader can understand without a lookup
table. This covers everything the project names: phases, studies, protocols, runs and
their arms, files, modules, schemas, branches, issue titles, Project field values,
risks and controls. It guards [R-UNREADABLE-DOCS](../risks.md#development-risks): a
label such as `P1` tells a reader nothing, and the same label came to mean four
different things.

- **No bare ordinals or position codes.** Not `P1`, `phase 2`, `study 3`, `arm B` or
  `L4`. Name a phase by what it delivers ("curator and memory"), a study by its
  question ("curator memory study"), an arm by what differs ("no-curator arm"), a
  priority by its meaning ("Urgent").
- **Numbers are for versions, references and dates.** A version follows a descriptive
  name (`player-host/3`). An issue, pull request or ADR number is a reference; give
  its title or subject the first time a page uses it. A repeated attempt is numbered
  after its name ("seven-day campaign, attempt 4").
- **A kind prefix with a descriptive word is a name.** `P-TRUTH`, `S-DOCS`,
  `C-RUNTIME` and `R-OVERSPEND` comply: the letter gives the kind (principle,
  standard, control, risk) and the word says which one. A prefix with a number does not.
- **Abbreviate only what the page defines** where it is first used.
- **A key defined in the page that uses it is a reference, not a name.** A source
  list's "S3" or a decision record's own "decision 14" may be cited inside that page.
  Outside it, write what the key refers to and link the page.
- **Branches** are named for what they change, optionally after the issue number:
  `552-curator-memory-study-report`, not `p1-552`.
- **Renaming something persisted** (a schema ID, a stored field, a module other code
  imports) is a migration under [S-MIGRATION](migration.md): every reader and writer
  changes together and the old name is not kept as an alias.

Historical records keep the labels of their time, because their content is not
edited. The [name mapping](../acceptance/2026-11-12-control-review-and-names.md#names) translates
each retired label to its current name. Review (C-REVIEW) rejects a new name that
breaks this rule; no lexical check is kept, because a pattern cannot tell a version
from an ordinal.

## Visual explanations

A diagram answers one reader question, stated beside it, at a stated scope. Give it
a title and a one-paragraph description of what it shows (`accTitle` and `accDescr`
in the block serve as both), and say what its boxes and arrows mean. Label
relationships and authority boundaries; separate logical responsibilities from
actual process boundaries. Link the contract that owns the detail.

Write each diagram as one fenced `mermaid` block in its host page; GitHub renders it
and the block is the only copy. Update the block and its explanatory text together,
and preview a changed diagram on GitHub, because GitHub's Mermaid version decides how
it draws. A diagram of a changed boundary is reviewed with that change, as part of
its ordinary review. Retire a diagram with its parent page, and link to one diagram
instead of copying it.

The user must be able to find purpose, current capabilities/limits, architectural
rationale, next change/tradeoffs and supporting evidence from the overview and
its immediate links. Preserve consequential limitations in plain language.
Archived plans and reports are not current instructions.
Retire inaccurate guidance; mark superseded decisions with replacements and keep
useful history.

[Standards index](../engineering.md).
