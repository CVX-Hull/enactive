# Third-party provenance

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
