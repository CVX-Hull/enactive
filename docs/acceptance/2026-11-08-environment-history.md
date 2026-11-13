---
owner: lead
status: historical
kind: change
date: '2026-11-08'
scope: Environment exceptions and evidence navigation that the environment page held until 8 November 2026, moved here unchanged when ADR 010 kept current pages free of dated narrative
---

# Environment history (moved from the environment page)

[ADR 010](../decisions/010-streamlined-delivery.md) keeps current pages free of dated
narrative. The two sections below were on [the environment page](../environment.md)
until 8 November 2026 and are kept here unchanged. They are dated facts, not a fresh
machine audit.

## Historical environment exceptions

The [cutover development record](2026-10-29-computer-control-development.md)
retains an accidental browser export to Downloads, subsequently moved into the
project, and one dependency command whose global cache use cannot be excluded.
No global package/profile change or cleanup of unowned caches is claimed. The
current owned source-build manifest and adjacent native build receipts retain
their exact dirty/clean source provenance; matching input hashes do not rewrite it.

Initial feasibility, before isolation steering, launched the stock game into
`~/Library/Application Support/Cataclysm/`. Its fresh configuration contained no
pre-existing saves and was moved intact to the project userdir; absence of the
global directory was verified then. Subsequent launch uses the prepared wrapper.

Homebrew pkgconf3.0.8 was installed during that initial feasibility work, copied
locally and uninstalled globally. Homebrew automatically refreshed three tap
metadata repositories; no existing installed package was upgraded. That metadata
refresh was retained rather than rolled back into unknown pre-existing state.
The initial build used existing read-only Homebrew FreeType; the replacement
recipe uses local headers and the official app's bundled runtime. The historical
verification checked no remaining global pkgconf/pkg-config or Homebrew runtime
dependency. These are dated facts, not a fresh machine audit or a claim that no
external change ever occurred. Per-user coding-agent trust and approval steps are
recorded in [coding-agent hosts](../operations/coding-agents.md#per-user-activation).

All other run output under `.runtime` up to the 7 November 2026 retirement, cited or not,
was deleted on the owner's decision; [the retirement record](2026-11-07-runtime-retirement.md)
lists it.

## Evidence navigation

The [pre-consolidation environment record](https://github.com/CVX-Hull/enactive/blob/de73b79b28a1aa61f1cb99fbf8642d62bc81d722/docs/environment.md)
preserves every original setup/build/archive path, hash and cleanup observation.
Git owns its history; the following existing records own interpretation:

- [Initial MVP](2026-10-17-mvp.md), [engineering setup](2026-10-17-engineering-system.md)
  and [consolidated acceptance](2026-10-17-completion.md): original installation, reversals and verification.
- [First supervised survival](2026-10-19-seven-day-survival.md): original campaign ending and preserved saves.
- [Native capture qualification](2026-10-22-native-capture-preconditions.md),
  [local refusal](2026-10-22-native-local-refusal.md) and
  [observation custody](2026-10-22-native-observation-custody.md): scoped builds, normal/exceptional endings and technical-world retirement.
- [Fresh024 closeout](2026-10-24-independent-seven-day-twenty-fourth-attempt.md): failed-world archive and adjacent member/restoration manifest (retired with the old run output on 7 November 2026) and unchanged accepted saves.
- [Acceptance directory](index.md) and each admission's private preparation/closure manifests:
  individual failed campaigns and diagnostics, unknown exit codes and save comparisons.

Private runtime artifacts are ignored by Git and not wholly verified or backed
up merely because a public page names them. Existing tracked screenshots and
small evidence payloads remain alongside their reports; no bulk LFS migration,
new archive service or duplicate history database is justified by their current size.
