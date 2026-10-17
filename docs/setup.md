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
# Install pinned development controls as described below, then:
.venv/bin/python tools/check.py
```

The optional `.venv/` starts without pip or third-party packages and uses the
interpreter that creates it; setup does not download Python. Existing environments
are preserved. Running the game/controller still needs only the standard library.
Development checks require the pinned tools below. See the [environment ledger](environment.md)
for this Mac's existing toolchain and installation history.

## Install development controls locally

Use an existing `uv` executable with an explicit project cache and interpreter:

```sh
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_DOWNLOADS=never uv pip install --no-config --default-index https://pypi.org/simple --python .venv/bin/python --require-hashes -r requirements-dev.lock
```

If uv is unavailable, use the standard library's local pip bootstrap:

```sh
.venv/bin/python -m ensurepip
.venv/bin/python -m pip --isolated install --index-url https://pypi.org/simple --cache-dir "$PWD/.cache/pip" --require-hashes -r requirements-dev.lock
```

Neither route installs global packages. Dependency installation needs network
access; running checks afterward is offline. Use the project interpreter explicitly.
Missing tools fail checks with a setup instruction; checks never install or upgrade
anything automatically. [Tool selection](decisions/003-development-controls.md)
explains reuse, scope and limitations. Direct requirements and all transitive
versions/hashes are in [requirements-dev.in](../requirements-dev.in) and
[requirements-dev.lock](../requirements-dev.lock).

For deliberate upgrades, review tool changelogs and regenerate the lock with the
same project cache, then install and run the full lane including negative fixtures:

```sh
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_DOWNLOADS=never uv pip compile --upgrade --no-config --default-index https://pypi.org/simple --python .venv/bin/python --generate-hashes --output-file requirements-dev.lock requirements-dev.in
```

The current resolution/install was verified on Python 3.14/macOS. CI defines a
Python 3.14/Linux install but has not run remotely. Other interpreter/host combinations
require their own validation before a support claim.

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
[MVP acceptance](acceptance/2026-10-17-mvp.md).

## Common checks and local hook

```sh
.venv/bin/python tools/check.py
```

The common lane also runs governance, dependency-boundary and protocol-version
checks described in the [control map](controls.md). To update the generated map
after changing its registry, run `.venv/bin/python tools/governance.py --write`; the normal
check fails on stale generated output. This does not establish native compatibility.

This compiles Python syntax in memory, runs selected Ruff correctness diagnostics,
checks Import Linter dependency contracts, checks browser JavaScript syntax with
Node.js, runs delayed-image viewer regressions, validates required documents and
local Markdown file/image targets using markdown-it-py, runs all unit tests
(including real loopback HTTP tests), and checks staged/unstaged Git diff whitespace. It fails if Node.js is unavailable, a link is broken, or a test
fails. Fragment anchors, raw HTML links and external web availability are not checked. HTTP
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

## Evidence and releases

Before a release/checkpoint, inspect the staged diff and candidate scope, run the
common lane against that candidate, and record exact commit/tree identity, tools,
results and unexecuted lanes in a dated acceptance report. If partially staging,
check an isolated export of the staged candidate rather than treating a working-tree
hook as proof. Native changes additionally follow the [native acceptance lane](runbook.md#native-acceptance-lane).
Hosted required checks are unconfigured until a remote is explicitly authorized.

Current [standards](engineering.md) define release scope; [operations](runbook.md)
own evidence retention and recovery. No release tag or publication is automatic.
