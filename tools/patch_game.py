"""Apply explicit, count-checked integration anchors to pinned CDDA 0.I-1."""
from pathlib import Path
import hashlib
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
source = Path(sys.argv[1]).resolve()

pin = json.loads((ROOT / "native" / "upstream.json").read_text())
originals = source / ".harness-originals"
for name, checksum in pin["source_files"].items():
    target = source / name
    original = originals / name
    data = original.read_bytes() if original.exists() else target.read_bytes()
    if hashlib.sha256(data).hexdigest() != checksum:
        raise SystemExit(f"Upstream source differs from pinned release: {name}; extract a fresh source tree")
    original.parent.mkdir(parents=True, exist_ok=True)
    if not original.exists():
        original.write_bytes(data)
    target.write_bytes(data)

# Current Xcode no longer supports upstream's 10.15 libc++ deployment target.
makefile = source / "Makefile"
make_text = makefile.read_text()
if make_text.count("-mmacosx-version-min=10.15") != 2:
    raise SystemExit("Pinned deployment target anchors changed")
makefile.write_text(make_text.replace("-mmacosx-version-min=10.15", "-mmacosx-version-min=13.0"))

def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if new in text:
        return
    if text.count(old) != 1:
        raise SystemExit(f"Pinned source anchor changed: {path}: {old[:70]!r}")
    path.write_text(text.replace(old, new))

for name in ("cdda_harness.h", "cdda_harness.cpp"):
    shutil.copyfile(ROOT / "native" / name, source / "src" / name)
for name in ("input_context.cpp", "sdltiles.cpp", "main.cpp", "handle_action.cpp", "do_turn.cpp", "debug.cpp"):
    path = source / "src" / name
    text = path.read_text()
    if '#include "cdda_harness.h"' not in text:
        path.write_text('#include "cdda_harness.h"\n' + text)

# The guard spans handle_input, including retries and nested keybinding UI.
replace_once(source / "src/input_context.cpp",
    'const std::string &input_context::handle_input( const int timeout )\n{',
    'const std::string &input_context::handle_input( const int timeout )\n{\n'
    '    cdda_harness::scope harness_input( category, registered_actions );')
replace_once(source / "src/handle_action.cpp",
    'input_context game::get_player_input( std::string &action )\n{',
    'input_context game::get_player_input( std::string &action )\n{\n'
    '    cdda_harness::scope harness_player( uquit == QUIT_WATCH ?\n'
    '        cdda_harness::boundary_kind::unsupported : cdda_harness::boundary_kind::normal_play );')
replace_once(source / "src/do_turn.cpp", 'void handle_key_blocking_activity()\n{',
    'void handle_key_blocking_activity()\n{\n'
    '    cdda_harness::scope harness_activity( cdda_harness::boundary_kind::activity_poll );')
replace_once(source / "src/debug.cpp",
    '    for( bool stop = false; !stop; ) {\n        ui_manager::redraw();',
    '    cdda_harness::scope harness_debug( cdda_harness::boundary_kind::debug_prompt );\n'
    '    for( bool stop = false; !stop; ) {\n        ui_manager::redraw();')
replace_once(source / "src/main.cpp", '        while( !do_turn() ) {}',
    '        cdda_harness::playing( true );\n        while( !do_turn() ) {}\n'
    '        cdda_harness::playing( false );')
replace_once(source / "src/sdltiles.cpp",
    '    while( SDL_PollEvent( &ev ) ) {\n        imclient->process_input( &ev );',
    '    while( SDL_PollEvent( &ev ) ) {\n'
    '        if( ev.type == SDL_KEYDOWN || ev.type == SDL_TEXTINPUT ||\n'
    '            ev.type == SDL_MOUSEBUTTONDOWN || ev.type == SDL_MOUSEWHEEL ||\n'
    '            ev.type == SDL_CONTROLLERBUTTONDOWN ) {\n'
    '            cdda_harness::human_input();\n        }\n'
    '        imclient->process_input( &ev );')
replace_once(source / "src/sdltiles.cpp", '    if( inputdelay < 0 ) {\n        do {',
    '    cdda_harness::boundary();\n\n    if( inputdelay < 0 ) {\n        do {')
replace_once(source / "src/sdltiles.cpp", '    SDL_RenderPresent( renderer.get() );',
    '    cdda_harness::capture_frame();\n    SDL_RenderPresent( renderer.get() );')
# Modify only get_input_event, excluding animation pump implementation.
path = source / "src/sdltiles.cpp"
text = path.read_text()
start = text.index('input_event input_manager::get_input_event( const keyboard_mode')
end = text.index('\nbool gamepad_available()', start)
section = text[start:end]
old = 'CheckMessages();'
new = ('CheckMessages();\n'
       '            if( last_input.type == input_event_t::gamepad ) {\n'
       '                cdda_harness::human_input();\n'
       '            }\n'
       '            if( last_input.type == input_event_t::error ) {\n'
       '                cdda_harness::poll( actual_keyboard_mode( preferred_keyboard_mode ), last_input );\n'
       '            }')
if 'cdda_harness::poll(' not in section:
    if section.count(old) != 3:
        raise SystemExit('SDL poll anchors changed')
    text = text[:start] + section.replace(old, new) + text[end:]
    path.write_text(text)

adapter = r'''
namespace
{
SDL_Surface_Ptr harness_presented_frame;
}

void cdda_harness::capture_frame()
{
    if( !enabled() ) {
        return;
    }
    SDL_Rect viewport;
    SDL_RenderGetViewport( renderer.get(), &viewport );
    if( !harness_presented_frame || harness_presented_frame->w != viewport.w ||
        harness_presented_frame->h != viewport.h ) {
        harness_presented_frame = CreateRGBSurface( 0, viewport.w, viewport.h, 32, 0, 0, 0, 0 );
    }
    if( harness_presented_frame && SDL_RenderReadPixels( renderer.get(), nullptr,
            harness_presented_frame->format->format, harness_presented_frame->pixels,
            harness_presented_frame->pitch ) != 0 ) {
        harness_presented_frame.reset();
    }
    cdda_harness::frame_presented( static_cast<bool>( harness_presented_frame ) );
}

bool cdda_harness::write_frame( const std::string &filename )
{
    return harness_presented_frame && IMG_SavePNG( harness_presented_frame.get(), filename.c_str() ) == 0;
}

void cdda_harness::feed_imgui( const input_event &event )
{
    int code = event.get_first_input();
    if( event.type == input_event_t::keyboard_char ) {
        const std::map<int, int> special = {
            { '\n', SDLK_RETURN }, { KEY_UP, SDLK_UP }, { KEY_DOWN, SDLK_DOWN },
            { KEY_LEFT, SDLK_LEFT }, { KEY_RIGHT, SDLK_RIGHT },
            { KEY_BACKSPACE, SDLK_BACKSPACE }, { KEY_PPAGE, SDLK_PAGEUP },
            { KEY_NPAGE, SDLK_PAGEDOWN }
        };
        const auto found = special.find( code );
        if( found != special.end() ) {
            code = found->second;
        }
    }
    SDL_Event key = {};
    key.type = SDL_KEYDOWN;
    key.key.windowID = SDL_GetWindowID( window.get() );
    key.key.state = SDL_PRESSED;
    key.key.keysym.sym = code;
    key.key.keysym.scancode = SDL_GetScancodeFromKey( code );
    key.key.keysym.mod = event.modifiers.count( keymod_t::shift ) ? KMOD_SHIFT : KMOD_NONE;
    if( event.modifiers.count( keymod_t::ctrl ) ) {
        key.key.keysym.mod |= KMOD_CTRL;
    }
    if( event.modifiers.count( keymod_t::alt ) ) {
        key.key.keysym.mod |= KMOD_ALT;
    }
    imclient->process_input( &key );
    if( !event.text.empty() ) {
        SDL_Event text = {};
        text.type = SDL_TEXTINPUT;
        text.text.windowID = SDL_GetWindowID( window.get() );
        SDL_strlcpy( text.text.text, event.text.c_str(), sizeof( text.text.text ) );
        imclient->process_input( &text );
    }
    key.type = SDL_KEYUP;
    key.key.state = SDL_RELEASED;
    imclient->process_input( &key );
}
'''
text = path.read_text()
if 'void cdda_harness::feed_imgui(' not in text:
    path.write_text(text + '\n' + adapter)
print(f'Applied harness integration to {source}')
