---
owner: maintainer
review_trigger: Dependencies, source pins, licenses or distributed assets change
status: active
---

# Third-party provenance

## License scope

Original standalone harness/viewer code, tooling, tests and documentation are
provided under the [MIT license](LICENSE). This does not relicense upstream material. The upstream
Makefile modification applied by `tools/patch_game.py` is distributed under CDDA's
CC BY-SA 3.0 terms; the standalone SDL adapter in `harness/computer/native/` uses
no engine code; third-party
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
records exact versions and artifact hashes. Original license files remain in their
distributions.

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
No third-party package is vendored in Git. Preserve the original notices when
redistributing packages.
Licenses of the SDK's resolved dependencies: MCP/MCP-types, AnyIO, annotated-types, h11,
Pydantic/Pydantic-core, PyJWT, Truststore and typing-inspection are MIT; CFFI is
MIT-0; HTTPX2/HTTPCore2, IDNA, pycparser, Starlette, SSE-Starlette and Uvicorn are
BSD-3-Clause; OpenTelemetry API and python-multipart are Apache-2.0; cryptography
offers Apache-2.0 OR BSD-3-Clause. The local adapter installs no telemetry exporter
and disables the SDK's optional telemetry middleware. The SDK's transitive packages
stay in the project `.venv`.

## Optional Pi deciding host

The project-local host uses [Pi](https://github.com/earendil-works/pi) agent-core,
AI and MCP packages 1.4.0 under MIT. Its separate
[package](tools/player_host/package.json) and [lock](tools/player_host/package-lock.json)
record exact direct/transitive versions, integrity and license metadata. Original
notices remain in those installed distributions; no upstream code or binary is
vendored in Git. Pi MCP includes notices for its SDK-derived OAuth code, which
this stdio-only integration does not invoke. Preserve upstream notices before
redistributing a bundled installation. The Python MCP server remains a separate
dependency. The [player host procedure](docs/operations/player-host.md) names the selected host and
its activation; the [host brief](docs/changes/controllable-player-host.md) records
why it was chosen and when to reassess it.

## Player image decoding

Pillow 13.0.0 decodes player-visible PNGs for interpretive evaluation and fixtures. Its package metadata
identifies MIT-CMU; its installed `licenses/LICENSE` also retains notices for
bundled image libraries. Exact artifacts/hashes are in the development lock.
The bundled-library license review is incomplete. Preserve the upstream notice
when redistributing the wheel. No image codec source is vendored here.

## Test runner

pytest, pytest-xdist, execnet, pluggy and iniconfig use MIT licenses. Packaging
uses Apache-2.0 OR BSD-2-Clause. Exact versions and hashes are in the development
lock; their original notices remain with the project-local installed packages.
The maintained runner collects the project's unittest-style tests with their assertions
unchanged; [testing](docs/testing.md) describes selection and limits.

## Documentation assets and tools

python-frontmatter and PyYAML are MIT licensed; their exact versions and hashes
are in the Python lock. Puppeteer is Apache-2.0; npm's lock records all resolved
package versions/integrity and license metadata. Original package notices stay in
project-local node_modules; Chrome for Testing keeps its upstream notices in the
downloaded browser directory. Diagrams are Mermaid text that GitHub renders; the
repository distributes no rendered diagram or font.

The tracked spectator example is an unchanged CDDA/UltiCa screenshot with the
upstream game and art attribution above. Its source identity and date are in the
[walkthrough](docs/walkthrough.md) and MVP manifest.
UltiCa attribution: the I-am-Erk/CDDA-Tilesets contributors; the bundled tileset
credits filler trees to Yar (original) and I-am-Erk (edits), with per-tile credits
in the [upstream tileset](https://github.com/I-am-Erk/CDDA-Tilesets/tree/dfd8d69f388e6b9c2719b250845e51d8d30eb2cb/gfx/UltimateCataclysm).
The [upstream license notice](https://github.com/I-am-Erk/CDDA-Tilesets/blob/dfd8d69f388e6b9c2719b250845e51d8d30eb2cb/LICENSE.txt)
identifies CC BY-SA 3.0. The depicted game artwork retains
[CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) and is not covered
by the project's MIT grant.

The additional [seven-day endpoint image](docs/assets/seven-day-endpoint-2026-10-19.png)
is an unchanged actual CDDA/UltiCa capture from 2026-10-19. Its source and byte identity
are recorded in the [campaign report](docs/acceptance/2026-10-19-seven-day-survival.md)
and manifest. It retains the same upstream game and art attribution and CC BY-SA 3.0
terms, and is not covered by the project's MIT grant.

The CDDA evaluation binding's glyph atlas (`harness/evaluation/cdda/atlas.json`) is derived from the
Terminus font (SIL OFL 1.1) as rendered by Cataclysm: DDA at 8x16 pixels. Each glyph is a 128-pixel ink
mask learned from recorded frames and checked against the font, so it is a derivative of Terminus. Its
text crops under `tests/fixtures/evaluation/cdda` are unaltered sidebar and menu text regions of CDDA
screenshots containing no tileset art. The font keeps its upstream licence and copyright notice;
reproducing it needs the OFL text, available at https://openfontlicense.org/.

## Spectator page libraries

The spectator page ([ADR 008](docs/decisions/008-evaluation-and-spectator.md))
vendors three browser libraries in `web/vendor/` with no build step and no network use at
run time: Preact 11.2.0 (MIT), htm 3.1.1 (Apache-2.0) and Apache ECharts 5.5.1
(Apache-2.0). Their tarball URLs, integrity hashes, per-file digests and the one
rewritten import specifier are in [web/vendor/PROVENANCE.md](web/vendor/PROVENANCE.md);
each library's `LICENSE` (and ECharts' `NOTICE`) sits beside it and must travel with
any redistribution. The viewer's survival statistics use numpy 2.5.4 and scipy 1.18.1
(BSD-3-Clause), pinned in [requirements.in](requirements.in) and the shared lock and
installed only in the project environment; nothing from them is vendored in Git.
