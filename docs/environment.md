---
owner: lead
review_trigger: Setup, dependency installation, owned resources or cleanup changes
status: active
---

# Environment ownership and retained evidence

Use [setup](setup.md) for installation, [runbook](operations/evidence-cleanup.md#evidence-retention-and-cleanup)
for operation/retirement, and the [overview](overview.md) for supported scope.
This page maps owned resources and exceptional environment changes. Dated reports
and adjacent private manifests own individual build, run and cleanup receipts;
this is not a process dashboard or attempt log.

## Owned resources

| Resource | Authority and maintenance |
| --- | --- |
| `.venv/`, `.cache/` | Project Python/runtime/development tools and caches; dependency locks and setup own versions/install steps. No global package installation. |
| `.runtime/Cataclysm.app`, `.runtime/downloads/`, `.runtime/toolchain/` | Prepared Tiles app, pinned downloads and local tooling. Use the wrapper with explicit project userdir and windowed mode. |
| `.runtime/build-manifest.json` and its owned temporary workspace | Current build provenance, exact source/configuration and ownership marker. The recorded workspace may be outside the checkout because upstream Make does not reliably accept spaces. Verify the marker before removal; do not infer ownership from a path prefix. |
| `.runtime/user/` | Project configuration and saves. Preserve accepted checkpoints; archive/member-hash verify stale failed/technical worlds before removing active copies. No save editing or restoration to manufacture success. |
| `.runtime/computer-sessions/`, `.runtime/player-stores/`, `.runtime/computer-build-*/` | Current frozen admissions, immutable PNGs, original ledgers/host traces, explicit player memory and owned native build receipts. Closed stores never restore authority. |
| `.runtime/missions/`, `.runtime/campaigns/` | Historical semantic-system evidence, not current runnable admissions or supported data readers. Closing a host or removing a world does not erase a failure. |
| `.runtime/save-retirement/` and per-campaign `closed-evidence/` | Existing archives and adjacent manifests own exact member hashes and restoration instructions. Restoration still requires a new admission and ordinary Load. |
| `.runtime/research/` | Owned experiments, including the executable-policy spike environment. Retain required evidence; remove superseded local tooling only after preservation. |
| `.runtime/tooling/verification-pilots-venv/`, `.runtime/iterations/verification-pilots/` | Historical testmon/source-map experiments; their executables and current installation route are retired. Preserve original result receipts before removing owned generated copies; no real saves are included. |
| `tools/player_host/node_modules/`, `.runtime/pi-host235/` | Locked mandatory generic-host dependencies and historical offline conformance/probe receipts; npm cache stays in project `.cache/npm`. No model/API credential belongs in these directories. [Host setup](setup.md#install-the-generic-gameplay-host) owns install and support limits. |
| `.codex/`, repository-local Git configuration/hooks | Reviewed project tool/permission configuration and public identity. [Operator permissions](operator-permissions.md) separates rule matching, host activation and gameplay authority. |

Existing Python, Node, Xcode/Clang, uv and ffmpeg may be reused without modifying
their installations. New dependencies/caches/outputs remain project-local or in
explicitly recorded owned temporary builds. No broad Homebrew/cache cleanup,
profile edits, unrelated process termination or global service configuration.
A manifest describes a recorded artifact; inspect live state before cleanup.

## Historical environment exceptions

The [cutover development record](acceptance/2026-10-29-computer-control-development.md)
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
external change ever occurred. Exact-project Codex trust setup is separately
recorded in [operator permissions](operator-permissions.md).

## Evidence navigation

The [pre-consolidation environment record](https://github.com/CVX-Hull/enactive/blob/de73b79b28a1aa61f1cb99fbf8642d62bc81d722/docs/environment.md)
preserves every original setup/build/archive path, hash and cleanup observation.
Git owns its history; the following existing records own interpretation:

- [Initial MVP](acceptance/2026-10-17-mvp.md), [engineering setup](acceptance/2026-10-17-engineering-system.md)
  and [consolidated acceptance](acceptance/2026-10-17-completion.md): original installation, reversals and verification.
- [First supervised survival](acceptance/2026-10-19-seven-day-survival.md): original campaign ending and preserved saves.
- [Native capture qualification](acceptance/2026-10-22-native-capture-preconditions.md),
  [local refusal](acceptance/2026-10-22-native-local-refusal.md) and
  [observation custody](acceptance/2026-10-22-native-observation-custody.md): scoped builds, normal/exceptional endings and technical-world retirement.
- [Fresh024 closeout](acceptance/2026-10-24-independent-seven-day-twenty-fourth-attempt.md): failed-world archive under `.runtime/campaign-closeout/independent-seven-day-024/`, adjacent member/restoration manifest and unchanged accepted saves.
- [Acceptance directory](acceptance/) and each admission's private preparation/closure manifests:
  individual failed campaigns and diagnostics, unknown exit codes and save comparisons.

Private runtime artifacts are ignored by Git and not wholly verified or backed
up merely because a public page names them. Existing tracked screenshots and
small evidence payloads remain alongside their reports; no bulk LFS migration,
new archive service or duplicate history database is justified by their current size.
