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
On a material change to the overview or the navigation, C-USABILITY walks the
intended reader task: find the current rule and owner, understand its consequence,
and trace the needed detail without reconstructing history. No count makes a page too
large. A page is too large when a reader cannot do that walk on it, because it mixes
purposes or holds what has another home; it is then decomposed, and a table of links
alone is insufficient.
Documentation generators and checks follow S-CODE's reuse decision and review
requirement; stewardship/schema rules do not justify rebuilding their parsers.

Stewardship metadata lives in YAML front matter, checked by `tools/documents.py`. The
pages that carry it are the root documents (README, AGENTS, CONTRIBUTING, NOTICE,
SECURITY), every Markdown file under `docs/` and `tools/player_host/README.md`; each
names its owner and status. Other Markdown in the tree is not a page and carries no
stewardship metadata: role files and their wrappers are configuration a coding agent
loads, prompts are inputs a program reads, and a provenance file sits beside what it
describes. Active or proposed pages need a review trigger. Historical and superseded
pages carry none, because nobody reviews them against current behavior. A historical
page needs date and scope; a superseded one needs scope and a repository-relative
replacement. A historical page that a later one replaces only in part stays historical
and may name that page as its replacement. Proposals are not implemented contracts. Accepted ADRs are dated rationale;
architecture/protocol remain authoritative about current behavior. Metadata is
not a claim of accuracy. Review a current page when its own review trigger fires.

Choose explanations for understanding, procedures for doing, reference for exact
contracts and walkthroughs for learning. Add these when a real reader need exists;
do not create empty categories. A significant change's design note or pull request
shows before/after user consequences, affected boundaries, alternatives and evidence.
Use capability tables,
dated screenshots or demonstrations when they convey more than additional prose.

Component assurance explanations follow the same review hierarchy. Keep one current
home for responsibility-level risks/evidence links; refer to contracts, control
definitions and native test metadata rather than mirror them. Maintain links and
limits with changed behavior/assertions, and simplify low-value mapping detail.
The [documentation map](../documentation.md) and [testing guide](../testing.md) own the
navigation and selection method, not a second live backlog or coverage database.

Development notes reference existing admissions, ledgers and artifacts. Related
results in one piece of work share one dated record; a stopped menu attempt needs a
concise retained finding, not a new record. Current contracts change with behavior; historical observations
stay historical. Follow the workflow's evidence cadence without duplicating its
procedures here.

Respect the [documentation/GitHub authority split](../workflows/authority.md#authority-and-review-surfaces).
C-REVIEW checks that an updated summary links its authoritative source instead of
mirroring live fields or accumulating another run narrative. Retire obsolete
summaries through ordinary Git edits; retain dated evidence and owned action items.
Use the [documentation roles and lifecycle](../documentation.md) when deciding where
an artifact belongs. Dated acceptance/audit records are historical, even when their
observations remain relevant; the existing metadata check enforces that narrow
role rule. Per-run quantities live in tracked data (S-EVIDENCE), and generated indexes
list every dated acceptance record, change brief and numbered decision record from its
front matter, with a staleness check. Incorporate adopted design into current architecture/contracts,
transfer remaining actions to GitHub and retain its brief as dated rationale. Partial
proposals identify their remaining proposal scope.

## Current pages, records and decisions

Each kind of fact has one home, listed in the
[documentation map](../documentation.md#one-authoritative-home-per-kind-of-fact), so
that a reader finds the current rule without reading history
([R-UNREADABLE-DOCS and R-STALE-DOCS](../risks.md#development-risks)). The cost is one
log row per owner decision and a reviewer's attention to tense; no check enforces it.

- **Current pages** state rules, contracts and procedures as they are. A date appears
  only where a reader needs it now: beside a measured figure, a pinned version or a
  source. Where a rule rests on a decision or a result, the page links the log row or
  the record once.
- **A dated record is for evidence a diff cannot hold**: a run, a study, a measurement
  or a review. Related results in one piece of work share one record. Everything else
  that is written down has another home and gets no record:
  - what a change did, a cleanup or removal included, why, and which checks ran: its
    pull request, which is what S-EVIDENCE asks to be recorded. An inventory or hash
    check of removed material that the diff cannot show is a measurement;
  - where work stands, a backlog grooming, or the choice of what to do next: the issue
    and the Project;
  - a design awaiting an owner decision: a `proposed` note under `docs/design/`; a
    proposal or plan for work: its issue;
  - a reading of outside sources: a research page;
  - an owner decision: a row in the log.
- **The owner decision log** is the one list of owner decisions: date, question, the
  owner's words, what it settles, and a link to the evidence. A decision is added in
  the change that acts on it, or in a change of its own when it alters nothing else
  (an approval of spend, a limit set outside the repository). An issue or pull request
  may also carry the agreement. Current pages cite the specific row. The log groups
  [in-force decisions](../decisions/owner-decisions.md#in-force) by subject. The archive's
  [Replaced](../decisions/owner-decisions-archive.md#replaced) section holds decisions a later
  decision replaces. Its [Used approvals and rulings on finished work](../decisions/owner-decisions-archive.md#used-approvals-and-rulings-on-finished-work)
  section holds approvals and rulings that no longer grant permission. Rows are retained.
- **A dated record names its kind** in its front matter. The generated index shows it,
  so a reader can find the runs without reading past the reviews, and the document
  check requires it. A new record is one of four kinds:
  - `run`: what real play, a campaign, a lineage or a native acceptance session did;
  - `study`: a designed comparison and its result, gates or stops;
  - `measurement`: a measurement of the system or its evidence that is not a study;
  - `review`: an independent assessment of work, a design or evidence, including the
    evidence that an issue's outcome is met.

  Two more kinds, `decision` and `change`, label records written before
  14 November 2026; the check refuses them on a later record, because a decision is a
  log row and a change is a pull request.
- **A research page is current only while its question is open.** When the decision it
  informs is made, the page becomes `historical` and its conclusion is stated, with a
  link, on the page that owns the resulting rule.
- **An ADR states a decision and its reasons and then stops changing.** It does not
  track the standing of the work it proposes. A design note is `proposed` while its
  owner decisions are open. When they are made it becomes `historical`, unless it is
  the working description of something being built, in which case it is `active` until
  that is built and described in components and contracts. The change that adds the
  deciding row to the log changes the note's status.
- **An issue has one current description**, replaced when things change
  ([work items](../workflows/work-items.md#status-fields-and-dates)). GitHub keeps its
  edit history.

- **A historical page's body does not change after it merges**
  ([decision](../decisions/owner-decisions.md#historical-pages-metadata-may-be-fixed-content-never)).
  This holds for dated records, change briefs, historical decision records, design
  notes and research pages, and superseded pages. Their front matter may be corrected
  (a wrong status, date, scope or replacement, or a review trigger), and a link in them
  is repointed when its target moves or is removed. A correction of what a record says is a new
  record that names the one it corrects.

Records and briefs that existed when these rules were adopted, on 13 November 2026,
are not edited to fit them. Four records dated 19 November 2026 were edited on
20 November 2026, after they merged and before the owner's decision of 21 November 2026
restated the rule; they stay as they are: the
[lead trial](../acceptance/2026-11-19-antigravity-lead-trial-810.md), the
[model evidence](../acceptance/2026-11-19-coding-agent-model-evidence.md), the
[lookup effort study](../acceptance/2026-11-19-lookup-effort-at-retained-resource-choices-804.md)
and the [request deadline record](../acceptance/2026-11-19-request-deadline-during-provider-backoff-805.md).
C-REVIEW applies these rules to changed pages.

## Writing for a reviewer

A person reviewing has little attention to spend and an agent pays for every word it
reads ([R-UNREADABLE-DOCS](../risks.md#development-risks)).

- **A design note and a dated record open with "At a glance"**: the question, the
  answer, what is not known, and the owner decisions needed, each in a line or two. A
  reader who trusts the page stops there; the rest is the evidence.
- **Define a term where a reader starts.** Terms the project uses throughout are in the
  [glossary](../glossary.md); a page links it or defines its own terms at first use.
- **Write sentences.** A rule is stated as a sentence with a subject and a verb, not as
  a string of nouns. When a change touches a section written in compressed form, it
  rewrites that section; pages are not rewritten for style alone.
- **Say where a number comes from** ([S-EVIDENCE](evidence.md)).

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
  name (`player-host/4`). An issue, pull request or ADR number is a reference; give
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
breaks these rules; no lexical check is kept for ordinals, because a pattern cannot
tell a version from an ordinal.

### Coding agents, providers and models

A current page outside `docs/operations/` names no coding agent, provider or model
([decision](../decisions/owner-decisions.md#no-agent-provider-or-model-named-outside-operations)).
It says what the thing does or which role it holds: "the lead's coding agent", "a
reviewer from another model family", "the model provider". The pages under
`docs/operations/` map roles to the coding agents, providers and models that hold them.
A current page is one whose status is `active` or `proposed`.

The rule does not reach:

- dated records and historical or superseded pages, which are evidence of what ran and
  are not reworded; a generated index reproduces their titles and front matter as they
  stand;
- attribution that a licence requires;
- the title, author or publisher of a cited source, and the coding agent, provider or
  model that a cited outside source studied
  ([decision](../decisions/owner-decisions.md#a-page-may-name-what-a-cited-source-studied));
- an adapter reference under `tools/`, which is the one page that specifies its player
  host and may name it and its route; apart from attribution a licence requires, no other
  current page outside `docs/operations/` names a player host
  ([decision](../decisions/owner-decisions.md#the-adapter-reference-may-name-its-player-host));
- the names of files and directories in the tree;
- a literal identifier inside a code block or schema example that the page's job is to
  specify.

The owner decision log quotes the owner's words with a bracketed description in place
of a name: "[the coding agent tried on 19 November]". Review (C-REVIEW) applies the
rule. `tests/test_host_neutrality.py` refuses coding-agent and player-host names on
current pages, except those under `docs/operations/` and `docs/design/` and a few
setup and operator pages it lists; it does not yet refuse provider or model names on
pages.

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
