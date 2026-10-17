# Environment ledger

Owner: lead. Updated: 2026-10-17. Review whenever setup or cleanup changes.

## Project isolation

New installations live in `.runtime/`; Python dependencies will live in `.venv/`.
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
