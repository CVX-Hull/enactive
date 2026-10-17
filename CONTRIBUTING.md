---
owner: maintainer
review_trigger: Contributor workflow, validation or licensing changes
status: active
---

# Contributing

Start with the [overview](docs/overview.md), then the authoritative
[engineering standards](docs/engineering.md). The
[project workflow](docs/project-management.md) explains issue tracking and review;
[active work](docs/work.md) links the authoritative GitHub work and blockers.

## Propose a focused change

Search existing issues before opening a bug report or work proposal. Describe the
user-visible problem, intended outcome, scope, exclusions and acceptance evidence.
Discuss consequential boundary, dependency or guarantee changes before implementing
them. Routine fixes need a cohesive diff and relevant checks.

Use a normal Git branch in your checkout, or fork the repository and branch there.
Keep each PR small enough to review and link its issue with `Refs #123`. Split
independent outcomes; explain dependencies and uncertainty. Closing a duplicate or
cancelled issue does not mean its proposed outcome was delivered.

## Develop and verify

Follow [setup](docs/setup.md) for pinned, project-local dependencies and tools.
Keep new environments, caches, saves and build outputs project-local or in an
explicitly recorded owned temporary build; do not install global tools or profiles.

Run the common checks from the repository root in the prepared environment:

```sh
.venv/bin/python tools/check.py
```

Run relevant focused checks while developing. The common command and hosted CI
cover the portable lane; they do not establish native build or graphical gameplay
acceptance. Native bridge, input, renderer, compiler, source-pin or protocol changes
need the relevant [native acceptance](docs/runbook.md#native-acceptance-lane).
The current native scope is one tested macOS host; other hosts remain unverified.

Preserve real game behavior and player-visible observation boundaries. Never edit
saves or bypass engine validation to produce acceptance evidence. Launch only the
prepared windowed wrapper with an explicit project userdir. Coordinate shared game,
save, port and build resources before using them.

Update affected contracts, tests and user guidance in the same change. Link to
authoritative documents rather than copying their full requirements. See the
[control map](docs/controls.md) for check coverage and gaps.

## Submit and review

Explain the problem and resulting behavior, issue reference, exact checks actually
run and their results. Record candidate identity, environment and limitations when
relevant; distinguish portable tests, native builds and observed gameplay. Disclose
failures and unexecuted checks. Redact tokens, personal paths and private data from
logs and screenshots; do not upload saves by default.

Consequential changes need independent review with fresh context under the
engineering standards. Record who or what reviewed which candidate, material
findings and their disposition. An agent review is not human approval. Maintainers
verify the final candidate and its evidence before accepting the change.

## Licensing and security

Original project code uses the [MIT license](LICENSE). Preserve upstream and
third-party notices and applicable terms, including those for derived code and
assets; see [NOTICE](NOTICE.md). Include source and license provenance when adding
or adapting material.

Report suspected vulnerabilities through the [security policy](SECURITY.md),
without posting sensitive details in a public issue.
