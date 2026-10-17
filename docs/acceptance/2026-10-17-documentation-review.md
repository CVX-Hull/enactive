---
owner: lead
status: historical
date: '2026-10-17'
scope: Documentation governance, lifecycle checks and visual-review increment on this Mac
---

# Documentation-review acceptance — 2026-10-17

[Brief 002](../changes/002-documentation-review.md) is implemented and verified.
Base: `548220c`. Scope: documentation, development checks, metadata and rendering
dependencies. No controller, server, viewer, native bridge, installed game or save
behavior changed. The Git checkpoint containing this report identifies delivered
source. The [consolidated goal](../goal.md) retains the full requested project scope;
previous [MVP](2026-10-17-mvp.md) and [engineering](2026-10-17-engineering-system.md)
acceptance remain dated evidence, not newly executed lanes.

## Executed verification

Environment: this macOS arm64 host, project Python 3.14 virtual environment,
existing Node runtime, locked Mermaid CLI 12.0.0 / Mermaid 12.2.0 / Puppeteer 25.14.0
and project-cached Chrome 155.0.8059.79. No fullscreen or game launch in this increment.

- Common command passed **84 Python tests and four production-viewer scenarios**,
  Python/JavaScript syntax, Ruff, two Import Linter contracts, local links, document
  metadata, governance/schema/lifecycle/protocol checks, generated-map freshness,
  three real diagram renders and input/output hash receipts, and Git whitespace.
  The final checkpoint is verified with the common pre-commit hook after staging
  the complete candidate; no partial-staging claim is made.
- Negative fixtures cover invalid metadata/status/references, inactive mappings,
  replacement cycles, review chronology/90-day bound, overdue dates, stale generated
  output, malformed Mermaid and missing SVG accessibility/style metadata. A real
  parse error is required: missing-browser or sandbox failures cannot count as the
  expected malformed-diagram result.
- A real Puppeteer configuration probe under hostile ambient version/browser/path
  settings selected the pinned browser and local cache/temp paths. The explicit
  install wrapper also selected cached Chrome 155.0.8059.79 despite an inherited
  version of 123.0.0.0 and an outside-cache override. Escaping SVG, receipt, config
  and cache symlinks were rejected before rendering/writing; outside sentinels
  remained unchanged. This does not claim protection against concurrent hostile
  filesystem mutations.
- Standalone forecast `--as-of 2027-01-16` failed as expected for the 12 reviews due
  2027-01-15, without renewing records. Due-day and retired-control behavior have
  isolated tests. Production records are evaluated against today's date by the
  common command; fixture dates do not prevent later legitimate renewals.
- Lead inspected context, action and recovery previews at 900-pixel content width
  in a 1000×800 viewport, with vertical scrolling for long diagrams. The independent
  reader reviewer inspected all three and found no required correction. The final
  recovery wording was clarified to cover startup without a pending request and
  re-rendered/reinspected. No clipping or color-only distinction was observed.
- Historical spectator screenshot bytes match the MVP manifest: 273741 bytes,
  SHA-256 `e37a42eba9b9a720c50905acdfb1027970e7e99e3637333e8ec9585723e4f995`.
  The small tracked copy is unchanged. The walkthrough labels it historical.

Local diagnostic log: `.runtime/evidence/documentation-check.log`. Preview PNGs:
`.cache/diagrams/preview/`. These are regenerable, ignored diagnostics, not the only
acceptance record. Editable sources, SVGs, receipts, tests and this report are tracked.

## Independent review and repaired failures

The lead retained design, integration and final verification. A bounded worker
implemented metadata/lifecycle checks in named paths; write ownership returned to
the lead before diagram/tooling integration. Independent reviewers read fresh
context for design, control implementation and reader comprehension.

Design review caused two clarifications: receipt freshness does not assume identical
SVG bytes on different hosts, and last-exercise evidence points to dated results,
not merely source code. Controls review found three P2 defects: live production
dates coupled to frozen test dates; inherited Puppeteer version overrides; and
output containment checked after publication. The lead fixed all three and added
meaningful regressions. Targeted independent re-review confirmed all resolved with
no remaining material issue. Reader review had no required correction; its optional
recovery-label clarification was adopted. The overview and immediate links expose
purpose, capabilities/limits, rationale, next work, evidence and maintenance duties.

Failed attempts were retained rather than treated as passes. Restricted DNS and
headless launch failed before permission-enabled runs. An initial npm command
specified the same null configuration file twice and was rejected; the corrected
command changed no global configuration. A Mermaid sequence semicolon caused a
parse error. The initial bare `action` SVG ID was absent from output, leaving scoped
styles ineffective; a project-prefixed ID and presence regression fixed the
observed failure without an upstream patch. The precise upstream cause is not claimed.

## Maintenance assessment and limits

The registry's 12 records distinguish defined controls, scoped exercises and
maintenance assessments. Existing native/runtime/setup exercises retain historical
MVP evidence. Portable controls have current negative-case evidence; reader review
is heuristic, and longitudinal maintenance effectiveness is unassessed. Next reviews
are recorded within 90 days, with earlier event triggers. No background scheduler,
automatic date renewal or deletion job exists.

New local dependencies are python-frontmatter 1.3.0 and PyYAML 6.0.3 (prior Python
pins preserved), 195 npm packages and one pinned browser. Roughly 1.1 MB of rendered
SVGs embed fonts with tracked notices. This cost buys established parsing/layout;
future reviews must assess upgrade burden, false alarms, duplicate edits, failed
procedures, escaped defects and repeated reader questions. Controls may be improved,
replaced or retired with evidence. Dates and hashes do not prove a review happened,
that prose is true or that a user understands it.

No new native build/gameplay, remote Linux CI, full global-filesystem audit,
assistive-technology test, user study or statistical effectiveness study was run.
The previously documented global-environment history is preserved in the
[environment ledger](../environment.md); it is not rewritten as a pristine-history
claim. No new global package installation, shell/profile edit or unrelated app
modification was requested here. Runtime limitations remain visible in the overview,
architecture and runbook. No unresolved material review finding or exception remains.
