---
owner: lead
review_trigger: Setup, dependency installation or cleanup changes
status: active
---

# Environment ledger

Recorded setup and maintenance history; this is not live environment status.

## User-directed stale-save cleanup, 2026-10-22

With no native game or controller listener running, retired 36 closed test/failed
worlds containing 20 saved characters from the project userdir's active save
directory. All 1,363 files (33,647,175 bytes) were verified against the ordinary
local archive `.runtime/save-retirement/2026-10-22/stale-worlds.tar.gz` before
removing their active copies. Archive: 22,149,842 bytes, SHA-256
`09bb362a5f57a9ac7ca76e5b1bee4a2ff39c394bd904c4b2d164bfaf659086f0`.
The adjacent private `manifest.json` records each file hash, retired world,
retained file and restoration instructions; no new backup service was installed.

The remaining active worlds are `Belgium` (Ned Meyers, first seven-day campaign),
`Enactive Twenty Four` (Alex Enactive, accepted supply/shelter checkpoint) and
`EnactiveLearningSix` (Casey, current normally closed learning checkpoint). Every
retained file was verified unchanged. Mission ledgers, journals, frames, host
traces and acceptance artifacts were untouched; archived failed campaigns remain
failed and closed. Saves and the archive remain local and excluded from Git.

After native001's two normal exits and controller shutdown, separately retired its
closed `EnactiveSaveRefreshOne` / Robin technical world. The ordinary archive
`.runtime/save-retirement/2026-10-22-native001/closed-technical-world.tar.gz`
is 459,025 bytes, SHA-256
`a063c4d701e2ab846962a716cf110ce165f2e51857f7f292e98acca5dc553294`;
its adjacent manifest verifies every archived file. All 191 files in the three
accepted worlds above remained byte-identical. Native001's mission evidence and
original host traces remain intact; the active menu again contains those three
accepted worlds only.

After failed independent campaign006's actors and owned processes stopped,
separately archived its closed `EnactiveSevenDaySix` world at
`.runtime/save-retirement/2026-10-22-campaign006/closed-failed-world.tar.gz`.
Archive: 2,269,996 bytes, SHA-256
`7f9e955a289df2c95858f720c37bcade55063aa648dc8c285b23e5da49d2ea0b`.
All 88 archived files were verified before removing the active world; all 191
accepted-world files remained unchanged. The adjacent manifest records restoration
instructions. Its mission evidence remains intact, and exceptional cleanup does
not establish a normal ending or reusable failed-campaign authority.

## Structured player SDK, 2026-10-20

Added official MCP Python SDK 2.3.0 for the optional local stdio adapter. The shared
hashed lock resolves 37 packages; all pre-existing pins stayed unchanged and 21
new distributions were installed only in this checkout's `.venv`, using the
existing uv with `.cache/uv`, explicit PyPI index and Python downloads disabled.
The initial restricted-network resolution failed DNS; the authorized network
resolution/install succeeded. No global packages, shell profiles, global approval
defaults or network policy changed. The adapter disables optional SDK telemetry
middleware and installs no exporter. [Notices](../NOTICE.md#structured-player-tool-dependencies)
record the reviewed licenses. Project MCP configuration and active-host acceptance
are separate setup steps; these installations started no CDDA or controller.

## Project isolation

Game installations live in `.runtime/`; Python dependencies live in `.venv/`.
Game launch must pass the absolute `.runtime/user/` path via `--userdir` and use
`FULLSCREEN=no`. Existing Xcode/Clang, Python, uv and read-only system libraries
may be used. New tooling is installed locally. No shell profile or global
service configuration is authorized by the project workflow.

Created `.venv/` using the existing Python 3.14.7 interpreter with uv's cache
redirected to `.cache/uv`. At that initial MVP checkpoint the controller used only the standard
library and no Python packages had been installed into the environment. Development
tools were added later as recorded below; no global Python packages were installed.
Git was initialized locally with a `main` branch. The initial documentation
commit uses the explicit per-command identity `Codex <codex@localhost>`; no
global identity, hooks, remote, or credential configuration was changed.

## Initial feasibility check and reversals

- Downloaded the official 0.I-1 macOS universal graphical DMG into
  `.runtime/downloads/`. Verified SHA-256
  `8c169974d93762d1bedffee75c6847eb70a1d5b05e6448c1b829e314ba8bfaf6`.
- Copied the app into `.runtime/Cataclysm.app`. Installer image detached.
- Initial stock launch created `~/Library/Application Support/Cataclysm/`.
  It contained only fresh configuration, no existing saves. Moved it intact to
  `.runtime/user/`; verified the global directory no longer exists. Set windowed
  mode and 120x40 terminal dimensions there; no subsequent global launch allowed.
- Before project-isolation steering, installed Homebrew pkgconf 3.0.8. Copied it
  to `.runtime/toolchain/pkgconf`, then uninstalled the global package. Verified
  no global pkg-config command or pkgconf formula remains.
- Homebrew automatically refreshed three tap metadata repositories. No existing
  installed package was upgraded. Metadata is not rolled back: doing so could
  disturb pre-existing package-manager state. The new 14KB pkgconf manifest was
  moved into `.runtime/downloads/`. Its cached bottle predated this task and was
  left untouched.
- No global PATH, shell profile, credentials, accessibility permissions, Docker
  configuration, startup service, or system security setting was changed.

## Temporary material

`/tmp/cdda-source`, `/tmp/cdda-0.I-1-source.tar.gz`, `/tmp/cdda-release.json`
are task-owned research/build inputs. Keep required build and provenance data
in project setup scripts; remove only task-owned temporary material on final
cleanup. Never run broad system or Homebrew cleanup.

The first full native build succeeded on Xcode 26's Apple Clang 21 using the
official bundled SDL frameworks and existing read-only Homebrew freetype
headers/library. `/tmp/cdda-player-frameworks` and `/tmp/cdda-player-pkgconf`
are task-owned symlinks; `/tmp/cdda-player-pkg-config` is a wrapper that supplies
the copied pkgconf library path without changing the shell environment.
Upstream's macOS 10.15 deployment target was raised to 13.0 for current libc++.
One upstream missing-noreturn diagnostic in item_search.cpp is retained as a
warning rather than an error; no harness test or game behavior was weakened.
The linker notes that the existing freetype was built for macOS 26; this build
is validated only on this Mac, not advertised as supporting older macOS.

## Verified final setup and cleanup

The fresh recipe now uses local FreeType 2.14.3 headers plus the official app's
bundled FreeType runtime; no Homebrew headers/library or pkgconf are needed.
Build workspace: `/private/tmp/cdda-player-build-6jt343nd`, recorded with an
ownership marker in `.runtime/build-manifest.json`. It has no spaces because the
upstream Makefile cannot reliably build in a path containing spaces. Downloads,
app, saves, controller, Python environment, logs, screenshots and video are
project-local. Existing Python, Node, Xcode and ffmpeg executables were reused
without modifying their installations.

Fresh build and final incremental SPACE fix both compiled successfully. The
installed executable SHA-256 is
`7f83a0661ae4970dea890edceb516386950f0e2951b5adae66acf5d4ca3c62b7`.
`otool -L` confirms system libraries, SDL frameworks and the bundled
`@executable_path/libfreetype.6.dylib`; no Homebrew runtime dependency is present.
The prepared wrapper supplies only process-local DYLD paths and the explicit
project userdir. Both real save/reloads used this final executable.

Removed the superseded `/tmp/cdda-source` build, old source archive (a verified
copy is retained in project downloads), old framework/pkgconf symlinks and
pkg-config wrapper, and the unused project pkgconf copy. The fresh recorded
build is retained for reproducible incremental builds. Small release research
metadata in `/tmp/cdda-release.json` is task-owned and may be removed later.

Final audit: global `~/Library/Application Support/Cataclysm/` absent;
`/opt/homebrew/opt/pkgconf`, `bin/pkgconf` and `bin/pkg-config` absent;
Cataclysm DMG detached. The unrelated system Metal toolchain image was left
mounted. No global cache purge, tap rollback or unrelated process termination.
The only retained external change from feasibility is the Homebrew tap metadata
refresh described above. Repository-local `core.hooksPath=.githooks` enforces the
common checks; no global Git settings or remote were added.

The final user-facing processes are the windowed project game and the local
spectator on 127.0.0.1:8766. Port 8765 belonged to an existing service and was left
alone. Remote game control is paused; TURN_DURATION=0 means the visible zombie
does not advance while the game awaits input. No background scheduled agent or
startup service was installed.

## Engineering-system development tools, 2026-10-17

Reused existing uv 0.12.18, Python 3.14.7 and Node 26.9.0 read-only. Resolved
PyPI packages with `--no-config`, explicit public index, UV_PYTHON_DOWNLOADS=never
and UV_CACHE_DIR set to this checkout's `.cache/uv`; installed with artifact hashes
into this checkout's `.venv` only. The lock records all 14 transitive packages.
Direct tools: jsonschema 4.26.0, Import Linter 2.15, Ruff 0.17.1 and markdown-it-py
4.2.0. No game/runtime dependency or existing system installation changed.
Ruff cache is `.cache/ruff`; Import Linter runs without cache. CI's pip cache is
configured as `.cache/pip` within its checkout. No scheduler, cleanup job, global
hook/profile/package or remote was added. License provenance is in [NOTICE](../NOTICE.md).

Restricted-network resolution failed with DNS denial; the authorized network run
resolved and installed the lock successfully. Restricted loopback test runs failed
with EPERM; the full 60-test lane then passed with loopback permission, with no skips. These are distinct from game acceptance.

## Documentation-review increment

Added python-frontmatter 1.3.0 and PyYAML 6.0.3 to the existing project .venv,
preserving earlier lock versions. Installed Mermaid CLI 12.0.0 / Mermaid 12.2.0
and Puppeteer 25.14.0 in node_modules (195 packages in this resolution). npm cache
is .cache/npm; Chrome for Testing 155.0.8059.79 is in .cache/puppeteer; temporary
renderer profiles and render outputs stay under .cache. No global npm/Python
install, shell/profile change or system browser modification was requested.
Checks launch only a headless renderer, never fullscreen or the game.

The tracked SVGs and small historical screenshot copy support offline reading.
Render previews are disposable under .cache/diagrams; curated acceptance logs
stay in .runtime/evidence. Preserve source diagrams, receipt, font notices and
acceptance before removing local caches. A fresh checkout uses setup to reinstall
the pinned renderer; deleting a cache does not revoke historical acceptance.

## Consolidated acceptance audit, 2026-10-17

No packages, native build or global configuration changed. Reused the prepared
game and local environment. New primary-source extracts and gameplay receipts,
images and journal snapshots live under `.runtime/evidence/`; the normal game UI
created retained Day and tutorial saves in the project userdir. Existing H saves
were preserved. The old controller was stopped and one new local controller/game
session was started for the trial, ending saved/reloaded and remotely paused.

A native app lookup inadvertently launched a duplicate game at its main menu.
The bridge refused duplicate ownership; only the identified duplicate was stopped.
The runbook now warns against treating app lookup as a process check. One project
game and controller remained at audit handover. The earlier live journal remains
intact with its shutdown event; an exact snapshot of its accepted prefix preserves
the historical manifest. See the [completion report](acceptance/2026-10-17-completion.md)
for identities, failures and evidence limits. No save deletion or background
scheduler was used.

## Public workflow setup, 2026-10-17

Reused the existing GitHub CLI and authentication without changing global settings.
Two implementation worktrees were created under ignored `.worktrees/`; each had
disjoint file ownership and no game access or shared writable test environment.
Gitleaks 8.30.1 was downloaded from its official GitHub release into
`.runtime/toolchain/gitleaks/`; the Darwin arm64 archive SHA-256 was verified as
`b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5`.
Redacted scan results and GitHub setup/probe receipts stay in
`.runtime/evidence/publication/`. No system package, shell profile, credential
configuration, game process or save was changed by this setup.

## 2026-10-17 native-v2 foundation increment

Reused the pinned source/archive, existing project dependencies and compiler.
Fresh owned extraction/build: `/private/tmp/cdda-player-build-8vgf_363`; the prior
`/private/tmp/cdda-player-build-6jt343nd` manifest was preserved before replacement.
No global package, profile, Git identity or application configuration changed.
The existing GitHub no-reply identity was supplied per commit command.
The passive gameplay module reuses already-installed/pinned jsonschema; there was
no new dependency installation. Build and runtime provenance, local evidence
retention and cleanup are in the [foundation acceptance](acceptance/2026-10-17-foundation-implementation.md).

The final build binary SHA-256 was
`87de9bcda9ee8751704b8dc5016e7db6d4b43b9657e0cd5a72e66bad4963dd0b`;
installation/signing produced
`73105d7dfcf6c7d5120d08136186b90dca4bb94412027ec3c138a6658713454b`.
Only the prepared project app was launched, windowed with its explicit userdir.
Normal UI saves were retained. A tutorial-load diagnostic was preserved and the
failed load closed without saving; regular H/Day profiles supplied other probes.
The game was saved and quit normally, and both controller sessions were stopped.

## 2026-10-17 recovery and memory increment

Created two isolated implementation worktrees under `.runtime/worktrees/`; the lead
alone integrated source and owned all native runtime. Fresh owned extraction/build:
`/private/tmp/cdda-player-build-8cyhfag6`. Reused pinned dependencies and existing
project-local tools; no global installation, profile, Git identity or application
setting changed. The preceding build manifest and old bridge were archived before
cutover. No save was edited or removed. H and Day were saved normally; the existing
tutorial load error remains unresolved and its evidence is retained.

The [acceptance report](acceptance/2026-10-17-recovery-memory.md) records final build
and installed hashes, the offline wire-v3 cutover, temporary acceptance drivers,
real windowed probes and scope limits. One fault probe briefly suspended an exact
owned native PID, then resumed it before cleanup. All native and acceptance-server
processes were stopped after final probes. Logs/frames, unresolved admissions,
archived incident bytes and the useful current build remain local for retention.


## 2026-10-19 functional survival closeout

Unchanged native2095b718 and clean source40e9a4e supported normal same-process
reload, qualified day-two acceptance and the failed day-three water gate.
The publisher recovered before force-stop; no signal, rollback, native rebuild,
new dependency, global setting, permission expansion or fullscreen was used.
The [report](acceptance/2026-10-19-functional-survival.md) retains exact limits,
unknown acknowledgments and actual evidence.

Normal Save/Quit and main-menu Quit/confirmation exited native53355; the owned
controller27938 exited0 on ordinary interrupt, controller53338 and port8766 were
absent. Final save was not reloaded. Saves, evidence, caches and prepared app remain
project-local; no save was edited or removed. Temporary014–017 helpers/admissions
are closed and retained only as evidence. No live player/input queue remains.
