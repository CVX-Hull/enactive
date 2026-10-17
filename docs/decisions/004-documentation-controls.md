---
owner: maintainer
status: historical
date: '2026-10-17'
scope: Documentation metadata, lifecycle records and visual tooling selection for brief 002
---

# ADR 004 — Local metadata and visual documentation controls

Decision adopted for the documentation increment; execution results belong in its
dated acceptance. Current requirements live in [engineering](../engineering.md).

## Choice and reason

Extend the existing registry, JSON Schema and generated map with control lifecycle,
last exercise, maintenance findings and due dates. Keep dated reports as history;
there is no separate database or silently renewed verification badge. Local checks
detect overdue reviews when invoked. Event-triggered reviews and truth/comprehension
still require accountable people or agents; no background job is installed.

Use python-frontmatter 1.3.0 with PyYAML 6.0.3 for conventional YAML document metadata,
validated by existing jsonschema. Keep stewardship beside content, avoiding another
catalog of copied owners and titles. The [library documentation](https://python-frontmatter.readthedocs.io/en/latest/)
provides parsing instead of a project-written YAML parser. Its use does not establish
whether a declared owner acted or whether prose matches behavior.

Use [Mermaid CLI 12.0.0](https://github.com/mermaid-js/mermaid-cli/releases/tag/12.0.0)
with locked Mermaid 12.2.0, Puppeteer 25.14.0 and its Chrome 155.0.8059.79. The CLI
ships and embeds fonts; Open Sans is selected for readable portable SVGs. Node
22.13+ is required. Packages, npm cache, browser download and temporary profiles
stay in this checkout. Install package scripts disabled, then explicitly download
the pinned browser through `tools/diagrams.py --install-browser`, which invokes
Puppeteer's local CLI. The wrapper clears ambient Puppeteer overrides for both
install and render, and preflights output/receipt/cache containment before writes.
These guards address ordinary configuration drift and existing escaping symlinks,
not malicious concurrent filesystem changes. No global browser is modified.

Each .mmd has accessible title/description and a host-page text equivalent.
[Mermaid accessibility support](https://mermaid.js.org/config/accessibility.html)
supplies SVG title/description markup; human inspection checks their usefulness.
SVG IDs use a project prefix: the initial `action` ID was missing from a rendered
sequence, leaving its scoped styling unapplied. The corrected render and an ID
presence regression guard this observed failure without patching upstream code.

Normal checks verify a receipt over all Mermaid sources, renderer configuration,
wrapper and package lock plus output bytes, then render all sources again locally.
They do not compare layout bytes between hosts: font/browser/platform differences
could otherwise cause false drift failures. A receipt detects changed inputs or
outputs without regeneration; it is not proof against deliberate falsification.
Generation and checks never certify diagram semantics. Remote Linux CI remains
configured but unexecuted; this Mac is the verified rendering environment.

## Alternatives, maintenance and reversal

Prose-only metadata cannot reliably expose missing fields or elapsed dates. A full
documentation portal or policy platform adds another system to maintain. Vale and
Markdown style linting could address repeated prose/style defects, but do not solve
our present lifecycle and semantic review needs. No such lint gate is claimed.

Mermaid costs a browser download and 195 installed npm packages at this resolution,
plus generated SVG/font bytes. This buys a mature parser, layout engine, accessible
output and inspectable text sources. Custom drawing/validation would shift that
maintenance onto us. Stable text sources and checked-in SVGs preserve access if
we replace the renderer; keep useful failure cases when migrating tools.

At tool upgrades, review upstream release notes, compatibility and notices; update
locks deliberately, regenerate SVGs/receipt, run real-renderer negative cases and
inspect all changed renders. [Puppeteer configuration](https://pptr.dev/guides/configuration)
supports explicit local browser cache and temporary directories. Reconsider the
toolchain if rendering instability, install burden or readability outweighs its
benefits. Review findings and cost observations go into C-VISUAL/C-MAINTENANCE.
