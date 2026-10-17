# Environment ledger

Owner: lead. Updated: 2026-10-17. Review whenever setup or cleanup changes.

## Project isolation

New installations live in `.runtime/`; Python dependencies will live in `.venv/`.
Game launch must pass the absolute `.runtime/user/` path via `--userdir` and use
`FULLSCREEN=no`. Existing Xcode/Clang, Python, uv and read-only system libraries
may be used. New tooling is installed locally. No shell profile or global
service configuration is authorized by the project workflow.

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
