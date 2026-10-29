---
owner: maintainer
review_trigger: Dependencies, source pins, licenses or distributed assets change
status: active
---

# Third-party provenance

## License scope

Original standalone harness/viewer code, tooling, tests and documentation are
provided under the [MIT license](LICENSE), selected by the project owner on
2026-10-17. This does not relicense upstream material. The CDDA integration
`native/cdda_harness.cpp`, `native/cdda_harness.h` and upstream modifications in
`tools/patch_game.py` are distributed under CDDA's CC BY-SA 3.0 terms; third-party
artwork, embedded fonts and notices retain their own terms below. Source release
does not distribute the downloaded application or its bundled libraries.

This project modifies and runs Cataclysm: Dark Days Ahead by the Cataclysm and
CleverRaven contributors. The separately downloaded official release is 0.I-1,
source commit `7b2efa5cea38e4d4d97dd0e63b28b9148623da59`. Exact URLs, archive
hashes, and original source-file hashes are in `native/upstream.json`.

The game is licensed under Creative Commons Attribution-ShareAlike 3.0
Unported. Upstream's complete component notice is preserved in
[LICENSE-CDDA.txt](LICENSE-CDDA.txt). Original notices remain in the downloaded
source and application. The native bridge/patch is a modification of that game;
its changes and patch recipe are provided in `native/` and `tools/patch_game.py`.
No ownership of upstream game code or artwork is claimed.

The demonstration uses the bundled UltimateCataclysm (UltiCa) tileset and fonts.
SDL2, SDL_image, SDL_ttf, SDL_mixer, FreeType, fonts, tilesets, and other bundled
components retain their individual upstream licenses and attribution files.
The setup recipe downloads FreeType 2.14.3 headers from its official release;
its license files remain in the extracted source. No third-party game binary,
complete source tree, or library is vendored into Git. Preserve the original
notices and review the applicable licenses before redistributing a built app.

## Development tooling

Development-only Python tools are installed locally from PyPI; none are vendored
in Git or required by the runtime controller. [requirements-dev.lock](requirements-dev.lock)
records exact versions and artifact hashes. Installed distribution metadata was
reviewed on 2026-10-17; original license files remain in their distributions.

- jsonschema, jsonschema-specifications, attrs, referencing, rpds-py, Ruff,
  markdown-it-py, mdurl and Rich: MIT.
- Import Linter, Grimp and Pygments: BSD-2-Clause.
- Click: BSD-3-Clause.
- typing_extensions: PSF-2.0.

Preserve upstream license files when redistributing these packages. Tool choice
and primary project links are recorded in [ADR 003](docs/decisions/003-development-controls.md).

## Structured player tool dependencies

The optional project-local MCP process uses the official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk),
version 2.3.0, under MIT. Its exact runtime requirements and all transitive artifact
hashes are in [requirements.in](requirements.in) and [the shared lock](requirements-dev.lock).
No third-party package is vendored in Git. Installed distribution metadata was
checked on 2026-10-20; preserve the original notices when redistributing packages.
New resolved dependency licenses: MCP/MCP-types, AnyIO, annotated-types, h11,
Pydantic/Pydantic-core, PyJWT, Truststore and typing-inspection are MIT; CFFI is
MIT-0; HTTPX2/HTTPCore2, IDNA, pycparser, Starlette, SSE-Starlette and Uvicorn are
BSD-3-Clause; OpenTelemetry API and python-multipart are Apache-2.0; cryptography
offers Apache-2.0 OR BSD-3-Clause. The local adapter installs no telemetry exporter
and disables the SDK's optional telemetry middleware. The existing dependency
pins were retained; the SDK's transitive packages stay in the project `.venv`.

## Optional Pi deciding host

The project-local host uses [Pi](https://github.com/earendil-works/pi) agent-core,
AI and MCP packages 1.4.0 under MIT. Published package metadata and exports were
inspected on 2026-10-25. Its separate
[package](tools/player_host/package.json) and [lock](tools/player_host/package-lock.json)
record exact direct/transitive versions, integrity and license metadata. Original
notices remain in those installed distributions; no upstream code or binary is
vendored in Git. Pi MCP includes notices for its SDK-derived OAuth code, which
this stdio-only integration does not invoke. Preserve upstream notices before
redistributing a bundled installation. This runtime does not replace MiniRacer
for player-authored programs or the Python MCP server. Selection and upkeep
conditions are in the [host brief](docs/changes/069-controllable-player-host.md).

## Player program runtime

Player-authored routines use [MiniRacer](https://bpcreech.com/PyMiniRacer/)
0.14.1 (ISC), hash-pinned in the shared Python lock and installed only in the
project environment. Its wheel embeds V8 and supporting code under their own
notices. The installed distribution's `licenses/LICENSE` contains MiniRacer's
ISC grant; `licenses/AUTHORS.md` retains its authors. Metadata and those files
were reviewed on 2026-10-23; they are not a complete V8 component-license audit.
This repository does not vendor or relicense the wheel. Review and preserve the
upstream V8/component notices before distributing a bundled binary. Runtime selection, limits
and rejected alternatives are in [the execution brief](docs/changes/061-player-program-execution.md).

## Player image decoding

Pillow 13.0.0 decodes bounded player-selected PNG views. Its package metadata
identifies MIT-CMU; its installed `licenses/LICENSE` also retains notices for
bundled image libraries. Exact artifacts/hashes are in the development lock.
Metadata and the installed notice were inspected on 2026-10-29; this is not a
complete bundled-library license audit. Preserve that upstream notice when
redistributing the wheel. No image codec source is vendored here.

## Test runner

pytest, pytest-xdist, execnet, pluggy and iniconfig use MIT licenses. Packaging
uses Apache-2.0 OR BSD-2-Clause. Exact versions and hashes are in the development
lock; their original notices remain with the project-local installed packages.
The maintained runner replaces serial unittest discovery without changing the
unittest assertions; [testing](docs/testing.md) describes selection and limits.

The retired assurance/impact pilot used pytest-testmon 2.2.0 (MIT) and
Coverage.py 7.17.0 (Apache-2.0). Its pinned requirements and executable readers
remain in [the historical source](https://github.com/CVX-Hull/enactive/tree/433ed973afe312d03f777d8b102a0cba528af746/tools).
Those optional packages are not current dependencies or CI selection.

## Documentation assets and tools

python-frontmatter and PyYAML are MIT licensed; their exact versions and hashes
are in the Python lock. Mermaid CLI/Mermaid are MIT and Puppeteer is Apache-2.0;
npm's lock records all resolved package versions/integrity and license metadata.
Original package notices stay in project-local node_modules; Chrome for Testing
keeps its upstream notices in the downloaded browser directory.

Generated SVGs embed Open Sans font data from Fontsource. Font packages use
OFL-1.1; retain [Open Sans notice](docs/assets/OFL-OpenSans.txt) and
[Recursive notice](docs/assets/OFL-Recursive.txt) with distributed diagram assets.
Recursive is supplied by the renderer although these diagrams select Open Sans.
The tracked spectator example is an unchanged historical CDDA/UltiCa screenshot;
it retains the upstream game/art attribution described above and is not original
project artwork. Its source identity and date are in the walkthrough and MVP manifest.
UltiCa attribution: the I-am-Erk/CDDA-Tilesets contributors; the bundled tileset
credits filler trees to Yar (original) and I-am-Erk (edits), with per-tile credits
in the [upstream tileset](https://github.com/I-am-Erk/CDDA-Tilesets/tree/dfd8d69f388e6b9c2719b250845e51d8d30eb2cb/gfx/UltimateCataclysm).
The [upstream license notice](https://github.com/I-am-Erk/CDDA-Tilesets/blob/dfd8d69f388e6b9c2719b250845e51d8d30eb2cb/LICENSE.txt)
identifies CC BY-SA 3.0. Game imagery in the screenshot retains
[CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/); it is not covered
by the project's MIT grant. The screenshot captures the historical renderer and
spectator, without alteration of the depicted game artwork.

The additional [seven-day endpoint image](docs/assets/seven-day-endpoint-2026-10-19.png)
is an unchanged actual CDDA/UltiCa capture from 2026-10-19. Its source and byte identity
are recorded in the [campaign report](docs/acceptance/2026-10-19-seven-day-survival.md)
and manifest. It retains the same upstream game/art attribution and CC BY-SA 3.0
terms above, and is not covered by the project's MIT grant.
