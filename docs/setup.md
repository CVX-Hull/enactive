# Local setup and checks

The controller uses Python's standard library. Use Python 3.12 or newer and an
existing Node.js runtime for JavaScript syntax checks. Native builds require
macOS, existing Xcode command-line tools (`clang++`, `make`, `hdiutil`, `ditto`,
`otool`, `install_name_tool`, `codesign`), and enough disk space for roughly 1 GB
of unpacked game source plus several GB of compiler output. Setup never installs
global packages or launches CDDA.

Run from the repository root. No flags prints read-only status:

```sh
python3 tools/setup.py
python3 tools/setup.py --help
python3 tools/setup.py --venv
.venv/bin/python tools/check.py
```

The optional `.venv/` has no pip or third-party dependencies. It uses the Python
interpreter that creates it; it does not download Python. Existing environments
are preserved. See [the environment ledger](environment.md) for this Mac's
existing toolchain and earlier feasibility build.

## Explicit native stages

```sh
.venv/bin/python tools/setup.py --download
.venv/bin/python tools/setup.py --extract
.venv/bin/python tools/setup.py --app
.venv/bin/python tools/setup.py --build --jobs 6
# Quit the game normally before installing a completed build.
.venv/bin/python tools/setup.py --install
```

Stages can be combined, and run in the order above. `--venv` runs after download
and before extraction. Each stage is opt-in: extraction does not download,
building does not install, and installing does not launch. `--app` refuses to
replace any existing `.runtime/Cataclysm.app`; skip it if the official project
app is already present. `--install` refuses while a CDDA Tiles process is running.
It delegates to [prepare_game.py](../tools/prepare_game.py), which installs the
binary, signs it locally, preserves the original binary, writes the launch
wrapper, and forces the project user directory and windowed options. Launch
only that prepared wrapper; do not launch an unprepared stock app. Normal game
saves remain managed through CDDA's UI.

The game source and official macOS app URLs and SHA-256 values come from
[native/upstream.json](../native/upstream.json). Downloads are cached in
`.runtime/downloads/`, verified before reuse or extraction, and atomically
published only after checksum verification. A corrupt cache is an error; remove
only the named corrupt file before downloading again. An interrupted download
may leave a uniquely named `.part` file; it is never treated as a verified input.
The app image is mounted read-only at a unique temporary mount point, copied
with `ditto`, and detached in a cleanup block, including copy failures. No other
mounted image is detached.

FreeType 2.14.3 source provides only local headers; the official app supplies its
matching bundled runtime. The pinned source is
[freetype-2.14.3.tar.xz](https://download.savannah.gnu.org/releases/freetype/freetype-2.14.3.tar.xz),
SHA-256 `36bc4f1cc413335368ee656c42afca65c5a3987e8768cc28cf11ba775e785a5f`.
No pkgconf or Homebrew installation is needed. A generated local `pkg-config`
wrapper accepts only the pinned Makefile's `--cflags freetype2` and `--libs
freetype2` queries and fails on others.

`--extract` creates a unique `/tmp/cdda-player-build-*` workspace because the
upstream Makefile does not reliably support paths with spaces. The project
`.runtime/build-manifest.json` records the exact directory, source and header
checksums, build command, state, and completed binary checksum. An ownership
marker binds the workspace to this checkout. Extraction rejects path traversal,
escaping links, special files, and existing destinations. No current
`/tmp/cdda-source` or running app is changed by setup extraction/building.

The native recipe uses the official app's SDL2 frameworks through a path without
spaces, local FreeType headers, and the bundled FreeType dylib. It retains the
observed successful flags: `NATIVE=osx CLANG=1 TILES=1 SOUND=1 RELEASE=1 LOCALIZE=0
FRAMEWORK=1 OPTLEVEL=-O1 RELEASE_FLAGS=-Wno-error=missing-noreturn`. The pinned
patch raises upstream's deployment target to macOS 13 for current libc++.
Only that upstream missing-noreturn diagnostic is downgraded. The recipe builds
the host architecture, not a new universal binary. The manifest records a build
as complete only after `make` succeeds and the resulting binary is hashed.

Use a fresh extraction after changing build/compiler flags; do not reuse old
precompiled headers. For a clean retry, preserve any needed evidence, read the
manifest's exact workspace path and ownership marker, remove only that owned
workspace and `.runtime/build-manifest.json`, then run `--extract` again. Source
is not retained across system cleanup of `/tmp`; re-extract if it disappears.
Setup does not delete previous research/build trees or clean global caches.

The local-header recipe passed a full native rebuild in a fresh workspace on
2026-10-17, followed by installation, two normal save/reloads, text entry, travel,
and a hostile-creature interruption. This validates this Mac's toolchain, not
all macOS versions. Unit checks alone do not establish native build or gameplay
success. Exact acceptance is tracked in
[work.md](work.md).

## Common checks and local hook

```sh
.venv/bin/python tools/check.py
```

This compiles Python syntax in memory, checks browser JavaScript syntax with
Node.js, runs delayed-image viewer regressions, validates required documents and local Markdown file targets, runs all
unit tests (including real loopback HTTP tests), and checks staged/unstaged Git
diff whitespace. It fails if Node.js is unavailable, a link is broken, or a test
fails. Fragment anchors and external web availability are not checked. HTTP
tests require permission to bind loopback; a sandbox denial is a failed check,
not permission to skip those tests.

The same command is used by `.githooks/pre-commit` and
[the portable CI job](../.github/workflows/check.yml). CI tests only the
controller/setup/documentation lane on Linux; it makes no native compilation or
real-game claim. The hook is opt-in and setup does not change Git configuration.
To enable it for this repository, run:

```sh
git config --local core.hooksPath .githooks
```

The hook checks the current working tree; review staged paths and diff before
committing, especially when partially staging changes. It is convenience
enforcement, not a security boundary. Native and graphical acceptance remain
separate, as specified in [engineering.md](engineering.md).
