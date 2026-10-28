---
owner: maintainer
review_trigger: Changes to this standard, its controls or engineering constraints
status: active
---

# S-DELIVERY Reproducible and isolated delivery

Keep code, pins, patches, recipes, checks and docs in Git. New tooling, caches,
outputs and saves stay project-local or in a recorded owned temporary build.
No global packages/profiles/hooks; no unrequested remote or publication. Preserve
source/license provenance; checksum inputs; review upstream changes before
upgrading. Launch only the prepared windowed wrapper with explicit userdir.
A new game/compiler/patch build needs relevant native acceptance before a release
claim. Inspect the staged diff and verify the exact candidate before checkpointing.
Use the [development-first checkpoints](../workflows/development.md#development-first-delivery):
fast checks plus applicable focused tests for a development commit, and the
appropriate protected CI profile for formal acceptance/merge. Broad source changes
require full regression before merge; reduced profiles retain their declared scope
under the [delivery policy](../workflows/ci-profiles.md#protected-ci-profiles). Git owns
tracked-source history and identity. Commit
the exact source before a native development or acceptance run; identify it by
commit/tree and PR, and use Git diffs to show later source changes. Do not maintain a parallel per-source hash/history inventory.
Checksums remain appropriate for downloaded inputs, built binaries and external
evidence; bounded generated-output freshness receipts are checks, not source history.

[Standards index](../engineering.md).
