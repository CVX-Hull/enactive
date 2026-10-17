---
date: '2026-10-17'
owner: maintainer
scope: ADR 003 — Reuse established development controls
status: historical
---

# ADR 003 — Reuse established development controls

Owner: maintainer. Status: accepted after local integrated verification, 2026-10-17.
Review when control needs, tool support, licenses or maintenance costs change.

## Context and decision

The user requires reuse of mature tooling where it fits. Generic schema validation,
import-graph analysis, Python diagnostics and Markdown parsing already have maintained
implementations. Adopt jsonschema, Import Linter, Ruff and markdown-it-py as development
only dependencies. Exact versions and transitive artifact hashes are in
[requirements-dev.lock](../../requirements-dev.lock); direct intents are in
[requirements-dev.in](../../requirements-dev.in). Runtime game/controller dependencies
remain unchanged. Install into .venv, cache under .cache and never auto-install on check.

Use JSON Schema for record shape/type/date/hash formats, Import Linter for declared
static dependency contracts, Ruff for selected correctness diagnostics, and
markdown-it-py for Markdown link parsing. Configure existing capabilities before
writing plugins. Keep custom code only for our standard/principle/control relationships,
repository containment, readable control-map generation, and narrowly recognized
native/Python protocol-version representations. Matching source versions is not
native behavioral verification. Dynamic imports remain a review concern.

## Alternatives and maintenance

The initial custom validator/import-walker draft avoided packages but duplicated
well-established infrastructure and covered fewer cases. Replacing it adds pinned
dev dependencies and update work while reducing responsibility for generic parsing
and graph analysis. A full documentation portal or enterprise policy platform is
not needed for current readers. Format/type expansion can use existing tools when
appropriate, without inventing a project linter or silently reformatting unrelated code.

Updates are deliberate: regenerate the lock, review changes/licenses, install into
a project environment, run negative integration fixtures and the full common lane.
No global install or background updater. Reconsider a tool if its maintenance,
platform compatibility or coverage becomes unsuitable; preserve meaningful control
acceptance cases when replacing it. Setup documents reproducible local and CI use.

## Primary sources

[JSON Schema validation](https://python-jsonschema.readthedocs.io/en/stable/validate/)
requires explicit format checking for dates.
[Import Linter forbidden contracts](https://import-linter.readthedocs.io/en/stable/contract_types/forbidden/)
cover indirect imports and configured external packages; external internals and
dynamic imports are not a complete runtime dependency model.
[Ruff configuration](https://docs.astral.sh/ruff/configuration/) supports declarative
rule selection. [markdown-it-py](https://markdown-it-py.readthedocs.io/en/latest/)
provides tokenized CommonMark parsing; project containment and local file existence
remain project rules. These tools do not replace semantic or operator review.
