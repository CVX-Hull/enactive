---
owner: lead
status: historical
date: '2026-10-17'
scope: Implemented documentation lifecycle and visual-review increment
---

# Change brief 002 — Documentation that supports review

Owner: lead. Implemented and verified on 2026-10-17. This brief preserves design
intent; current guidance and the [acceptance report](../acceptance/2026-10-17-documentation-review.md)
own supported behavior and observed results.

## Problem and intended outcome

The overview gives direction, but visual explanations are sparse. Control definitions
have owners and triggers without a consistent lifecycle or evidence of maintenance.
The user should be able to review boundaries, action/recovery behavior, evidence,
decisions and maintenance obligations from the overview and immediate links.

Before: prose metadata, implicit active controls, manual periodic maintenance and
one text diagram. After: validated document metadata, explicit lifecycle and review
records, overdue detection on local checks, and rendered context/action/recovery
views with text equivalents. No game or runtime behavior changes.

## Design and ownership

Keep the existing ten standards; extend S-DOCS and S-EVIDENCE rather than introduce
another parallel governance hierarchy. The registry remains authoritative for
control definitions and their latest maintenance record; dated reports retain
history. Lifecycle states are proposed, active, deprecated and retired. Standards
may only rely on active controls. Replacement links must identify another control,
must not cycle, and retirement/deprecation require rationale. A new proposed control
may remain unmapped until adopted; inactive controls are retained for history.

Each control records last exercise (nullable, otherwise date/outcome/scope/evidence),
whose evidence must be a dated execution/review result with candidate, environment
and lane, not implementation source. A metadata review never advances native exercise.
latest maintenance review (nullable until reviewed; date/evidence/effectiveness/
findings/cost/follow-up), and next review date. Active/deprecated controls need a
review and a due date no more than 90 days after it. Checks fail after the due date,
not on the due date; event triggers can require review sooner. Future claimed
exercise/review dates and impossible chronology fail. A passing schema is not
proof the review happened. No background scheduler and no automatic date renewal.
Exceptions stay explicit in work; they do not silently suppress mechanical failures.

Use standard YAML front matter parsed by python-frontmatter and validated with
existing jsonschema. Cover all docs Markdown plus README/AGENTS/NOTICE: active and
proposed pages require owner/status/review_trigger; historical records require
owner/status/date/scope; superseded pages require owner/status/replacement/scope.
Metadata describes stewardship, not verified content. Generated controls include
metadata too. Do not duplicate full page contracts in a separate document catalog.

Mermaid CLI renders version-controlled .mmd sources to SVG. Keep packages and browser
cache local, pin versions/transitives, and generate with scoped stable IDs/config.
Normal checks validate a receipt of source/config/tool-lock and output byte hashes,
and render again to a project cache without changing tracked files. This detects
changed inputs/artifacts without assuming identical layout bytes across macOS/Linux.
Explicit regeneration updates SVGs and receipt. Receipts do not prove semantic truth
or defend against deliberately falsified artifacts. Remote CI remains unverified. Include readable titles/descriptions and text
equivalents in the host Markdown. Human review checks rendered legibility and meaning.
The common lane runs both document/governance and diagram checks. Tests demonstrate
invalid metadata, lifecycle/reference/date errors, stale output and invalid diagrams.

The lead owns design, source-based diagram semantics, integration, docs, dependency
selection and final verification. One bounded worker extends governance/metadata
code and tests; while it writes, the lead performs read-only source/research checks.
The lead then owns diagram/tooling/doc edits. A clean-context reviewer checks the
integrated result against this brief, standards and actual runtime sources.

## Alternatives, cost and reversibility

Prose-only checklists are cheaper initially but cannot expose missed metadata/dates.
A documentation portal, policy platform or comprehensive prose linter adds services
or upkeep without a demonstrated current need. Mermaid adds a browser-backed dev
dependency and render cost; keep only three useful views initially. Revisit if
install burden, instability or review cost outweighs comprehension benefits.
SVGs remain readable without tooling. YAML/JSON and text Mermaid sources are portable;
replacement tools must preserve meaningful negative tests and reader access.

## Acceptance and uncertainty

Verify relevant common checks, control negative cases, real renderer failure and
freshness cases, ordinary-window rendered inspection, and a user-question walkthrough.
Record source identity, tool versions, findings/fixes, limitations and unexecuted
lanes in dated acceptance. Verify the staged candidate before Git checkpoint.
No new native/gameplay claim: historical evidence stays explicitly dated. Long-term
effectiveness remains unmeasured; this increment can demonstrate only scoped checks
and reviewer understanding. No user decision is pending within the authorized scope.
