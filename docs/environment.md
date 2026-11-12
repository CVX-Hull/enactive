---
owner: lead
review_trigger: Setup, dependency installation, owned resources or cleanup changes
status: active
---

# Environment ownership and retained evidence

Use [setup](setup.md) for installation, [evidence cleanup](operations/evidence-cleanup.md#evidence-retention-and-cleanup)
for retention and removal, and the [overview](overview.md) for supported scope.
This page maps every owned local resource: what it holds, who writes it and when it
goes. Dated records own individual build, run and cleanup receipts; the
[environment history](acceptance/2026-11-08-environment-history.md) holds the earlier
dated exceptions.

## Owned resources

| Resource | What it holds, and its lifecycle |
| --- | --- |
| `.venv/`, `.cache/` | Project Python environment, development tools and caches (pip, npm, Ruff, Puppeteer's browser). Dependency locks and setup own versions and install steps. No global package installation. |
| `.runtime/Cataclysm.app`, `.runtime/downloads/` | The prepared Tiles app and the pinned downloads setup builds it from (`tools/setup.py --download` refetches them). Use the wrapper with an explicit project userdir and windowed mode. |
| `.runtime/build-manifest.json` and its owned temporary workspace | Current build provenance, exact source and configuration, and the ownership marker. The recorded workspace may be outside the checkout because upstream Make does not reliably accept spaces. Verify the marker before removal; do not infer ownership from a path prefix. |
| `.runtime/user/` | Project configuration and saves. Preserve accepted checkpoints; archive and member-hash verify stale failed or technical worlds before removing active copies. No save editing or restoration to manufacture success. |
| `.runtime/computer-sessions/`, `.runtime/evaluations/`, `.runtime/bridge/` | Where current runs write frozen admissions, immutable PNGs, original ledgers and host traces, and evaluator records; `bridge/game.lock` is the shared game lock. Sealed into the evidence store before removal when a record cites them. Closed stores never restore authority. |
| `.runtime/curator-shadow/`, `.runtime/knowledge/` | Created by [curator shadow sessions](operations/curator-hosts.md): session summaries and host configurations, and the knowledge repositories they curate. Sealed into the evidence store before removal when a record cites them. |
| `.runtime/computer-builds/` | Owned native adapter builds and their receipts, built fresh per [setup](setup.md). |
| `.runtime/logs/` | The prepared wrapper's game log (`game.log`), and earlier setup, build and check logs, kept by the [retirement record](acceptance/2026-11-07-runtime-retirement.md). |
| `.runtime/credentials.json` | The operator's credential reference: the name of a keychain item or environment variable, never a key. |
| `.runtime/worktrees/<leaf>` | One worktree per implementation leaf, with its own npm installs ([work items](workflows/work-items.md#ready-brief-and-execution-capacity)). Removed with its local branch when the leaf is Done and `git status` shows nothing uncommitted. |
| `.runtime/evidence/` | The sealed, read-only evidence store, the only copy; [evidence cleanup](operations/evidence-cleanup.md) owns sealing, verification and removal. This clone's local Git configuration records that it holds the store. |
| `.runtime/archive/` | Owned by the lead. Tarballs, a Git bundle and a patch of material removed from the checkout that was neither merged nor sealed, so these files are its only copy; each tarball has a `.sha256` beside it. The dated records name what each holds: the [8 November retirement](acceptance/2026-11-08-retirement.md) and the [12 November workspace cleanup](acceptance/2026-11-12-control-review-and-names.md#workspace-cleanup). Deleted only on the owner's direction. |
| `.runtime/check-logs/`, `.runtime/spectator-shots/` | Each checker run's full command output, and the spectator suites' screenshots (rewritten by each run); routine local output, prunable whenever no check runs. |
| `dist/` | Git-ignored local export output; seal an export into the evidence store when a record cites it. |
| `tools/player_host/node_modules/`, `tools/curator_host/node_modules/` | Locked dependencies of the player and curator host adapters; the npm cache stays in `.cache/npm`. No model or API credential belongs here. [Host setup](setup.md#install-the-generic-gameplay-host) and [curator hosts](operations/curator-hosts.md) own install and support limits. |
| `.codex/`, `.claude/`, `CLAUDE.md`, repository-local Git configuration and hooks | Reviewed project coding-agent tool and permission configuration, and public identity. Generated `.codex/config.toml`, `.mcp.json` and `.claude/settings.local.json` are machine-local and ignored. [Operator permissions](operator-permissions.md) separates rule matching, host activation and gameplay authority; [coding-agent hosts](operations/coding-agents.md) maps each host. |

A new run writes only to the locations above or to a path its admission names.

Existing Python, Node, Xcode/Clang, uv and ffmpeg may be reused without modifying
their installations. New dependencies, caches and outputs remain project-local or in
explicitly recorded owned temporary builds. No broad Homebrew or cache cleanup,
profile edits, unrelated process termination or global service configuration.
A manifest describes a recorded artifact; inspect live state before cleanup.
Private runtime artifacts are ignored by Git and are verified only where the evidence
store holds them.
