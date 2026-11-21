---
owner: maintainer
review_trigger: Contributor workflow, validation or licensing changes
status: active
---

# Contributing

Start with the [overview](docs/overview.md) and [engineering standards](docs/engineering.md).
Find work in the [public Project](https://github.com/users/CVX-Hull/projects/2) and
its issues. The [project workflow](docs/project-management.md) explains issue tracking
and review.

## Propose a focused change

Search existing issues before opening one. Describe the user-visible problem,
intended outcome, scope, exclusions and acceptance evidence. Use the
[documentation map](docs/documentation.md) to identify affected responsibilities,
contracts and callers. Discuss consequential boundary, dependency or guarantee
changes before implementation under the [review workflow](docs/workflows/review.md#risk-based-assurance).

Branch in your checkout or in a fork. Keep each pull request focused on one
reviewable outcome.

## Develop and verify

Follow [setup](docs/setup.md) for pinned, project-local dependencies, tools and builds.

For a development checkpoint, run the fast check and the relevant focused tests
from the [testing guide](docs/testing.md).

```sh
.venv/bin/python tools/check.py --fast
```

The [CI profiles](docs/workflows/ci-profiles.md) explain hosted scope and the required
`controller` check. Follow [development-first delivery](docs/workflows/development.md#development-first-delivery)
for real development runs and formal qualification. Use the
[native acceptance procedure](docs/operations/native-acceptance.md) for changes to the
native boundary.

Preserve real game behavior and player-visible observation boundaries. Never edit
saves or bypass engine validation to produce acceptance evidence. Launch only the
prepared windowed wrapper with an explicit project userdir.

Update affected contracts, tests and guidance in the same change. Follow the
[documentation checklist](docs/documentation.md#before-writing-or-changing-a-document).

## Submit and review

Use the [pull request template](.github/pull_request_template.md) to describe the
result, link the issue with `Refs #123`, and record exact checks, outcomes and gaps.
Report portable tests, native builds and observed gameplay separately. Redact
tokens, personal paths and private data from logs and screenshots. Saves stay local
by default.

Follow the [review workflow](docs/workflows/review.md) for independent review and
record the reviewed candidate and finding dispositions. The lead merges under the
[standing delegation](docs/operator-permissions.md#engineering-decision-and-merge-delegation).

## Licensing and security

Original project code uses the [MIT license](LICENSE). Preserve upstream and
third-party notices and applicable terms, including those for derived code and
assets; see [NOTICE](NOTICE.md). Include source and license provenance when adding
or adapting material.

Report suspected vulnerabilities through the [security policy](SECURITY.md),
without posting sensitive details in a public issue.
