---
owner: maintainer
review_trigger: Toolchain, dependency pins, setup stages or checks change
status: active
---

# Local setup and checks

The controller uses Python's standard library. The passive gameplay records/evidence
module also uses the already-pinned `jsonschema` package from the project lock.
Use Python 3.12 or newer and an
existing Node.js 22.13+ runtime for JavaScript and diagram checks. Native builds require
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
Using `harness.gameplay` and running development checks require the pinned tools below. See the [environment ledger](environment.md)
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

The current resolution/install was verified on Python 3.14/macOS. Hosted CI uses
Python 3.14 and Node 22 on Ubuntu 24.04; its first run exposed a Chrome sandbox
startup failure, repaired and verified in [public workflow acceptance](acceptance/2026-10-17-public-workflow.md).
Required checks must pass before integration. Other interpreter/host combinations
require their own validation before a support claim.

## Install and maintain visual documentation tools

From this repository root, using the existing Node.js 22.13+ and npm:

```sh
npm --userconfig /dev/null --cache "$PWD/.cache/npm" ci --ignore-scripts --no-audit --no-fund
.venv/bin/python tools/diagrams.py --install-browser
```

`package-lock.json` pins packages/integrity; the pinned Puppeteer version selects
Chrome 155.0.8059.79. `.puppeteerrc.cjs` keeps browser downloads and temporary profiles
under `.cache/`. Package install scripts are disabled; the second command is the
explicit browser download through the local Puppeteer CLI. The wrapper clears
ambient Puppeteer overrides for both installation and rendering, and rejects
symlinks that send outputs, receipts or caches outside the checkout before writing.
The local macOS recipe needs no global npm packages, system browser changes, OS
package installation or background service. Keep runtime caches local;
checks never fetch dependencies. Headless rendering may need permission in a
restricted execution sandbox. A denied launch is a failed check, not a passed render.

On the disposable GitHub Ubuntu runner only, the workflow installs a path-specific
AppArmor profile allowing the downloaded Chrome to create its sandbox namespaces.
Chrome sandboxing stays enabled; no global user-namespace sysctl is changed. This
follows [Chromium's scoped profile guidance](https://chromium.googlesource.com/chromium/src/+/main/docs/security/apparmor-userns-restrictions.md).
The runner is discarded after the job. This is not a local setup instruction or
permission to modify the operator's host.

```sh
# Change .mmd sources or render config, then regenerate and inspect the SVGs:
.venv/bin/python tools/diagrams.py --write
# Read-only with respect to tracked files: checks hashes and renders into .cache
.venv/bin/python tools/diagrams.py
# Forecast maintenance without modifying records:
.venv/bin/python tools/governance.py --as-of 2027-01-16
```

The forecast deliberately fails if the chosen date is after a control's due date;
it does not replace today's common check. Review the control and record evidence
before updating its due date. The generated maintenance table is in [controls](controls.md#maintenance).

For a deliberate renderer upgrade, edit exact direct versions in `package.json`,
run the same local npm command with `install` instead of `ci`, review lock changes
and upstream notices, install the selected browser, regenerate/inspect diagrams,
and run the common lane including real-renderer rejection. Avoid global installs
or an unpinned `npx` fallback. Other hosts must be verified before support claims.
See [ADR 004](decisions/004-documentation-controls.md) for costs and limits.

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
check fails on stale generated output. It also validates document YAML metadata,
control lifecycle/references/review dates and diagram receipts, and renders all
Mermaid sources with the local browser. Neither metadata nor rendering establishes
semantic truth or native compatibility. SVG byte equality across hosts is not
required: the receipt checks source/config/tool-lock and output identity, while
rendering verifies the local renderer can process the current source.

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

## Build metadata migration

The active `.runtime/build-manifest.json` requires exact integer `schema_version: 1`.
Setup rejects unversioned, old or future manifests without rewriting them. Fresh
`--extract` writes the current format; preserve an existing manifest/build before
recreating it. A one-time verified offline conversion follows the
[runbook](runbook.md#coordinated-migration). There is no automatic legacy reader.

## Evidence and releases

Before a release/checkpoint, inspect the staged diff and candidate scope, run the
common lane against that candidate, and record exact commit/tree identity, tools,
results and unexecuted lanes in a dated acceptance report. If partially staging,
check an isolated export of the staged candidate rather than treating a working-tree
hook as proof. Native changes additionally follow the [native acceptance lane](runbook.md#native-acceptance-lane).
The public repository requires a PR and the Actions-bound `controller` check on
main, with resolved conversations and no configured bypass. These rules do not
prove native gameplay; verify their current configuration at publication. See
[project management](project-management.md) for the single-maintainer review limit.

Current [standards](engineering.md) define release scope; [operations](runbook.md)
own evidence retention and recovery. No release tag or publication is automatic.
