---
owner: lead
status: historical
kind: change
date: '2026-11-08'
scope: 'Outcome of ADR 010 (#498): the seven leaves L1-L7, measured CI times before and after, lines removed, deviations and what was deferred'
---

# ADR 010 outcome: streamlined delivery

[ADR 010](../decisions/010-streamlined-delivery.md) was carried out in seven leaves under
outcome [#498](https://github.com/CVX-Hull/enactive/issues/498), each merged on green main
after its CI profile passed; L1, L2, L4 and L7 had an independent clean-context review
first.

| Leaf | Issue | PR | What it changed |
| --- | --- | --- | --- |
| L1 CI and safety | #499 | #506 | No calendar failure; a missing evidence store fails once the clone held it; main pushes run structural checks only; pytest beside a browser lane; the power simulation skips an unneeded bootstrap; an injectable policy-step budget |
| L2 Controls | #500 | #507 | A hand-written controls page replaces the registry, its schema, generator and lifecycle checks; C-GOVERNANCE becomes C-DOCUMENTS |
| L3 Evidence and data | #501 | #509 | The #454 shadow evidence sealed; the data rule replaces the closed evidence-id list; the environment page complete; the [8 November retirement record](2026-11-08-retirement.md) |
| L4 Documentation | #502 | #512 | Native Mermaid replaces rendered diagrams; current pages stop narrating change or restating results; superseded contracts and anchor stubs removed; one authority statement |
| L5 Delivery | #503 | #511 | Four Project statuses, Priority on leaves, Horizon on outcomes, no hand-kept dates ([Project record](2026-11-08-project-simplification.md)) |
| L6 Code hygiene | #504 | #508 | One shared JSON and hash module; finished study scripts removed; the viewer's game coupling documented; the sandbox profile beside the workspace |
| L7 Provider names | #505 | #510 | A provider-neutral proxy with the providers in the curator host; the host-neutrality scan covers provider and model names; the curator sandbox reads only the Node host's files and its launcher |

## CI times, measured

From GitHub's run records ([`ci-times.json`](assets/adr010-outcome/ci-times.json): the
`controller` job's start-to-finish seconds for 88 successful runs from 7 November 22:48 UTC
to 9 November 03:54 UTC, split at L1's merge, 9 November 02:59 UTC).

Every run in the file is in one row.

| Run and profile | Before (median, range, n) | After (median, range, n) |
| --- | --- | --- |
| Pull request, full | 397 s (236–557), 29 | 283 s (233–347), 7 |
| Pull request, viewer | 231 s (230–232), 2 | none |
| Pull request, editorial | 85.5 s (61–97), 16 | 100 s, 1 |
| Push to main, full | 429.5 s (327–553), 12 | none (the profile no longer runs on main) |
| Push to main, main-smoke | 227 s (184–235), 3 | none (removed) |
| Push to main, viewer or editorial | 232 s, 1; 77 s (60–98), 11 | none (every main push runs `main`) |
| Push to main, main | none | 43 s (32–57), 6 |

A local full run took 160 s after L1. ADR 010 expected a full run of about 300 s and main
pushes in about a minute; both hold.

## Lines and files

From `git diff --shortstat` between ADR 010's merge (`f340a9a`) and L4's final commit:

| Area | Added | Removed |
| --- | ---: | ---: |
| Code and tests (`tools/`, `harness/`, `tests/`) | 1,195 | 2,148 |
| Current documentation (`docs/` without dated records and diagrams) | 665 | 3,075 |
| Schemas | 0 | 270 |
| Rendered diagrams (18 SVGs, about 6.7 MB, and their sources) | 0 | 4,200 |
| `package-lock.json` (the diagram renderer's dependencies) | 47 | 2,235 |

Dated records and assets added in the same span (this record, the retirement, Project,
environment-history and moved-measurements records, the Project export and the CI data)
are additions by purpose and are not counted above.

## Deviations

Each is recorded on its PR.
- **L1:** two lanes (pytest, browser) rather than separate lanes for the adapter suite and
  the power test, which already run in parallel inside pytest; main keeps the root
  `npm ci`, which the document heading check needs.
- **L2:** the evidence-id list moved to L3, with the data rule that replaced it.
- **L3:** the cache-diagnosis schema stays, validated by a test, because its file stays in
  `data/`.
- **L4:** image embeds in historical pages point to `?raw=true` commit permalinks so GitHub
  still displays them; measurements no other record held moved, unchanged, to the
  [moved-measurements record](2026-11-08-moved-measurements.md).
- **L7:** one historical record's link was repointed when a script moved; the review found
  the moved Python readable inside the curator sandbox, and the readable roots were narrowed
  before merge.

## Deferred

- `dist/seven-day-video/`, the 19 October recap video export, is an original no record cites
  and the store does not hold; keeping or removing it is the owner's decision.
- The local branches `aid-zoom-view`, `backup/p0-453-wip` and `p0-453-gate` hold commits
  that exist nowhere else and were kept.
- GitHub's rendering of the converted Mermaid diagrams is checked by preview on the PR, not
  by a local check.
