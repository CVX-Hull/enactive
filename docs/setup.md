---
owner: maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Local setup and checks

Run from the repository root. Keep dependencies, apps, saves, caches and evidence
project-local. Setup does not install global packages or launch a game. Use an
existing Python 3.12+ and Node.js 22.19+ runtime; the checked configuration uses
Python 3.14/macOS and hosted portable CI uses Python 3.14/Node22. Other hosts need
separate qualification. Native preparation requires macOS/Xcode command-line tools.

```sh
python3 tools/setup.py
python3 tools/setup.py --help
python3 tools/setup.py --venv
```

No flags prints read-only status. The optional `.venv` uses the selected existing
interpreter. [Requirements](../requirements.in) and the hashed
[development lock](../requirements-dev.lock) pin runtime/check dependencies,
including MCP, MiniRacer/V8 and Pillow image decoding.

## Install development controls locally

### Choose an explicit Git identity

Configure only this checkout with your intended public identity:

```sh
git config --local user.useConfigOnly true
git config --local user.name "YOUR_PUBLIC_NAME"
git config --local user.email "YOUR_GITHUB_NOREPLY_ADDRESS"
git var GIT_AUTHOR_IDENT
git var GIT_COMMITTER_IDENT
```

Never infer a public identity from the Mac account. Inspect author/committer and
full messages, including co-author trailers, before publication.

### Install pinned packages

With an existing `uv` executable:

```sh
UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_DOWNLOADS=never uv pip install --no-config --default-index https://pypi.org/simple --python .venv/bin/python --require-hashes -r requirements-dev.lock
```

Or bootstrap pip inside the local environment:

```sh
.venv/bin/python -m ensurepip
.venv/bin/python -m pip --isolated install --index-url https://pypi.org/simple --cache-dir "$PWD/.cache/pip" --require-hashes -r requirements-dev.lock
```

Installation needs network; checks never install dependencies. The optional
verification-pilot runner and memory-study tools are retired. Do not reconstruct
their old environments as current setup.

### Install the generic gameplay host

The mandatory [Pi host](../tools/player_host/README.md) uses its own pinned npm lock:

```sh
npm --userconfig /dev/null --cache "$PWD/.cache/npm" --prefix tools/player_host ci --ignore-scripts --no-audit --no-fund
```

It loads explicit frozen provider/MCP/context files, not coding-agent settings,
shell/file tools, personal sessions or global credentials. The selected finite
route is OpenRouter / explicitly pinned provider / DeepSeek Flash1017 at medium effort.
The [recorded BaseTen exception](changes/071-computer-control-cutover.md#explicit-endpoint-disposition-after-shared-pool-failures)
follows actual Fireworks shared-pool failures. Freeze
its actual endpoint tag, supported parameters, image allowance and configured
prices before each allocation. No route/model fallback is supported. A selected
route is not gameplay qualification or invoice evidence.

Supply only the configured credential environment variable to the dedicated host;
never write its value to files/argv/logs. MCP/native children receive no provider
secret. The host rejects ambient OpenAI SDK logging/header/org/project overrides;
clear those only for the dedicated invocation, without changing global profiles.

## Configure the structured player tools

Inspect the current schemas without creating a runtime:

```sh
.venv/bin/python -m tools.configure_player_tools --describe
```

The campaign driver creates each actor's current `player-adapter/1` and MCP
configuration. For a separately selected actor configuration, the generator uses
explicit project-local paths and refuses to overwrite the output:

```sh
.venv/bin/python -m tools.configure_player_tools --actor-config /absolute/project/actor.json --output /absolute/project/mcp.json
```

The old trust-table `--write` and mission-client configuration are unsupported.
[Player tools](../harness/player_tools.py) own tool arguments; the
[player guide](player-guide.md) explains use.

## Install and maintain visual documentation tools

```sh
npm --userconfig /dev/null --cache "$PWD/.cache/npm" ci --ignore-scripts --no-audit --no-fund
.venv/bin/python tools/diagrams.py --install-browser
.venv/bin/python tools/diagrams.py --write
.venv/bin/python tools/diagrams.py
```

The npm lock pins the renderer; the explicit browser install keeps downloads and
profiles under `.cache`. Render/inspect changed diagrams at ordinary window width.
A denied browser launch is a failed check. Do not use global installs or an
unpinned `npx` fallback. [Visual requirements](standards/documentation.md#visual-explanations)
separate parse/render evidence from semantic and independent visual review.

## Explicit native stages

Prepare the project-local CDDA application and pinned upstream source separately
from the mechanical SDL adapter:

```sh
.venv/bin/python tools/setup.py --download
.venv/bin/python tools/setup.py --extract
.venv/bin/python tools/setup.py --app
.venv/bin/python tools/setup.py --build --jobs 6
.venv/bin/python tools/setup.py --install
```

Stages are opt-in; install only after the owned game exits. Existing app/build
outputs are preserved/refused rather than silently replaced. The
[upstream manifest](../native/upstream.json) owns source/app checksums.
Extraction records a uniquely owned temporary build and manifest because the
upstream build does not reliably support paths with spaces. Preserve existing
binary bytes and build receipts before rebuilding; remove only a verified owned
workspace for a fresh extraction.

The [preparation tool](../tools/prepare_game.py) creates a fixed wrapper and explicit
project userdir with `FULLSCREEN=no` and normal `ENABLE_MOUSE=true`. The computer
layer does not know or override game input settings. Never launch fullscreen or
an unprepared stock app. The wrapper preserves the inherited lock/socket and
restores the selected library path across macOS shell launch.

Build the sole current adapter with the prepared local frameworks and a fresh
project-local output directory:

```sh
.venv/bin/python tools/build_computer.py --resources "$PWD/.runtime/Cataclysm.app/Contents/Resources" --output "$PWD/.runtime/computer-builds/SELECTED_FRESH_BUILD"
```

This builds `bridge.dylib` and the native fixture, retaining commands/source/output
hashes in `build.json`. It is not a gameplay pass. The old semantic native patch
and experimental computer backend are retired. Launch only through the frozen
[current campaign custodian](operations/campaign-run.md).

## Common checks and local hook

```sh
.venv/bin/python tools/check.py --fast
.venv/bin/python tools/check.py
```

`--fast` is a checkpoint check; run relevant focused tests before development
play. The default is full portable regression. Protected profiles and selection
are owned by [CI policy](workflows/ci-profiles.md#protected-ci-profiles), with exact
membership in [tools/ci.py](../tools/ci.py). [Testing](testing.md) explains scope.
Checks do not compile the adapter or qualify actual game behavior.

The optional `.githooks/pre-commit` runs the fast lane when explicitly enabled
with `git config --local core.hooksPath .githooks`. It checks the working tree;
inspect staged paths/diff separately before committing. Do not treat a partial
working-tree check as evidence about a different staged candidate.

## Build metadata migration

Setup build manifests and current campaign/session stores have separate versions.
Unsupported versions refuse without rewriting. Preserve old artifacts and choose
fresh explicit outputs; [migration](operations/migration.md) owns data treatment.

## Evidence and releases

Commit and inspect a coherent checkpoint before native/gameplay qualification.
Record exact source/tree, external inputs, binaries, configuration, limits,
outcomes and unrun lanes. Independent review and the appropriate protected CI
profile precede formal acceptance/merge; broad source changes require full
regression. No setup command authorizes paid calls, publication or another run.
