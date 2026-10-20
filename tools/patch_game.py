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
    if text.count(old) != 1:
        raise SystemExit(f"Pinned source anchor changed: {path}: {old[:70]!r}")
    path.write_text(text.replace(old, new))

for name in ("cdda_harness.h", "cdda_harness.cpp"):
    shutil.copyfile(ROOT / "native" / name, source / "src" / name)
for name in ("input_context.cpp", "sdltiles.cpp", "main.cpp", "handle_action.cpp", "do_turn.cpp", "debug.cpp", "game.cpp", "action.cpp", "ui_iteminfo.cpp", "game_inventory.cpp", "output.cpp", "bodygraph.cpp", "uilist.cpp", "inventory_ui.cpp", "ui_manager.cpp", "cata_imgui.cpp"):
    path = source / "src" / name
    text = path.read_text()
    if '#include "cdda_harness.h"' not in text:
        path.write_text('#include "cdda_harness.h"\n' + text)

# Reuse ImGui's steady-caret setting only in this harness-owned SDL context.
# Cosmetic blinking must not invalidate unchanged exact-PNG editor decisions.
# Input behavior, game options and non-harness rendering retain upstream defaults.
replace_once(source / "src/cata_imgui.cpp",
    '    ImGuiIO &io = ImGui::GetIO();\n'
    '    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;     // Enable Keyboard Controls',
    '    ImGuiIO &io = ImGui::GetIO();\n'
    '    if( cdda_harness::enabled() ) { io.ConfigInputTextCursorBlink = false; }\n'
    '    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;     // Enable Keyboard Controls')

# Only the last/topmost redraw callback may attest UI. An unsupported overlay
# clears a lower supported menu even when the overlay has no harness hooks.
replace_once(source / "src/ui_manager.cpp",
    '                    if( ui.redraw_cb ) {\n'
    '                        ui.default_cursor();\n'
    '                        ui.redraw_cb( ui );',
    '                    if( ui.redraw_cb ) {\n'
    '                        ui.default_cursor();\n'
    '                        cdda_harness::ui_redraw( ui.is_on_top );\n'
    '                        ui.redraw_cb( ui );')

# The ImGui clipper can force an offscreen selected entry into DisplayStart/End.
# Attest only text within the actual window/column clip rectangle. Partial glyphs
# and multiline labels are omitted; a clipped right suffix is never exported.
replace_once(source / "src/uilist.cpp",
    'void uilist_impl::draw_controls()\n{',
    'void uilist_impl::draw_controls()\n{\n'
    '    cdda_harness::ui_begin( "uilist", "UILIST", "" );\n'
    '    const auto harness_label = []( const std::string &text, const ImVec2 &pos ) {\n'
    '        const ImRect clip = ImGui::GetCurrentWindow()->ClipRect;\n'
    '        std::string label = remove_color_tags( text );\n'
    '        if( pos.x < clip.Min.x || pos.x >= clip.Max.x || pos.y < clip.Min.y ||\n'
    '            pos.y + ImGui::GetTextLineHeight() > clip.Max.y ||\n'
    '            label.find_first_of( "\\r\\n" ) != std::string::npos ) { return std::string(); }\n'
    '        while( !label.empty() && pos.x + ImGui::CalcTextSize( label.c_str() ).x > clip.Max.x ) {\n'
    '            size_t end = label.size() - 1;\n'
    '            while( end > 0 && ( static_cast<unsigned char>( label[end] ) & 0xc0 ) == 0x80 ) { --end; }\n'
    '            label.resize( end );\n'
    '        }\n'
    '        return label;\n'
    '    };')
replace_once(source / "src/uilist.cpp",
    '                        ImGui::TableSetColumnIndex( 1 );\n'
    '                        cataimgui::draw_colored_text( str1, color );',
    '                        ImGui::TableSetColumnIndex( 1 );\n'
    '                        const std::string harness_text = harness_label( str1, ImGui::GetCursorScreenPos() );\n'
    '                        cataimgui::draw_colored_text( str1, color );\n'
    '                        if( !harness_text.empty() ) {\n'
    '                            cdda_harness::ui_row( harness_text, entry.enabled, "", is_selected );\n'
    '                        }')

# These hooks run inside the existing visible-column/page/cell loops, after
# denial widths, hidden cells and trimming have been resolved by the renderer.
# Do not enumerate inventory locations, hidden children or latent entry caches.
replace_once(source / "src/inventory_ui.cpp",
    'void inventory_selector::refresh_window()\n{\n'
    '    cata_assert( w_inv );',
    'void inventory_selector::refresh_window()\n{\n'
    '    cata_assert( w_inv );\n'
    '    cdda_harness::ui_begin( "inventory", "INVENTORY", "" );')
replace_once(source / "src/inventory_ui.cpp",
    '                }\n            }\n\n            x1 = x2;\n        }\n\n'
    '        if( entry.is_item() ) {\n            int xx = p.x;',
    '                }\n'
    '                if( cell_index == 0 && entry.is_item() && text_x >= 0 &&\n'
    '                    text_x + static_cast<int>( text_width ) <= getmaxx( win ) &&\n'
    '                    yy >= 0 && yy < getmaxy( win ) ) {\n'
    '                    const std::string label = remove_color_tags( trim_by_length( text, text_width ) );\n'
    '                    const char invlet = entry.get_invlet();\n'
    '                    const std::string hotkey = p.x >= 0 && p.x < getmaxx( win ) &&\n'
    "                        invlet >= 32 && invlet <= 126 ? std::string( 1, invlet ) : std::string();\n"
    '                    cdda_harness::ui_row( label, entry.is_selectable(), hotkey, selected );\n'
    '                }\n'
    '            }\n\n            x1 = x2;\n        }\n\n'
    '        if( entry.is_item() ) {\n            int xx = p.x;')

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
# Preserve DEFAULTMODE and its local bindings; end permission before callbacks.
replace_once(source / "src/action.cpp",
    '        action = ctxt.handle_input();\n'
    '        if( std::optional<tripoint_rel_ms> vec = ctxt.get_direction_rel_ms( action ) ) {',
    '        action = [&]() {\n'
    '            cdda_harness::menu_query harness_menu( "DEFAULTMODE" );\n'
    '            return ctxt.handle_input();\n'
    '        }();\n'
    '        if( std::optional<tripoint_rel_ms> vec = ctxt.get_direction_rel_ms( action ) ) {')
# Body status keeps its native bindings; ownership ends before nested graphs.
replace_once(source / "src/bodygraph.cpp",
    '    bool done = false;\n'
    '    while( !done ) {\n        ui_manager::redraw();\n'
    '        std::string action = ctxt.handle_input();\n'
    '        if( action == "QUIT" || ( action == "LEFT" && id != bodygraph_full_body ) ) {',
    '    bool done = false;\n'
    '    while( !done ) {\n        ui_manager::redraw();\n'
    '        std::string action = [&]() {\n'
    '            cdda_harness::menu_query harness_menu( "BODYGRAPH" );\n'
    '            return ctxt.handle_input();\n'
    '        }();\n'
    '        if( action == "QUIT" || ( action == "LEFT" && id != bodygraph_full_body ) ) {')
# Generic lowercase default is admitted only at these exact item-menu waits.
# Include each owner in its unique anchor and end permission before callbacks.
replace_once(source / "src/ui_iteminfo.cpp",
    'void iteminfo_window::execute()\n{\n'
    '    if( data.without_getch ) {\n        ui_manager::redraw();\n        return;\n    }\n\n'
    '    while( true ) {\n        ui_manager::redraw();\n'
    '        std::string action = ctxt.handle_input();',
    'void iteminfo_window::execute()\n{\n'
    '    if( data.without_getch ) {\n        ui_manager::redraw();\n        return;\n    }\n\n'
    '    while( true ) {\n        ui_manager::redraw();\n'
    '        std::string action = [&]() {\n'
    '            cdda_harness::menu_query harness_menu( "default" );\n'
    '            return ctxt.handle_input();\n'
    '        }();')
replace_once(source / "src/game_inventory.cpp",
    'bool game_menus::inv::compare_item_menu::show()\n{\n'
    '    while( true ) {\n        ui_manager::redraw();\n\n'
    '        std::string action = has_button_action() ? get_button_action() : ctxt.handle_input();',
    'bool game_menus::inv::compare_item_menu::show()\n{\n'
    '    while( true ) {\n        ui_manager::redraw();\n\n'
    '        std::string action = has_button_action() ? get_button_action() : [&]() {\n'
    '            cdda_harness::menu_query harness_menu( "default" );\n'
    '            return ctxt.handle_input();\n'
    '        }();')
# Nearby-list examination uses the current curses item-info renderer, not the
# separate iteminfo_window owner above. Mark only its wait, before coordinates.
replace_once(source / "src/output.cpp",
    '        action = ctxt.handle_input();\n'
    '        std::optional<point> coord = ctxt.get_coordinates_text( catacurses::stdscr );',
    '        action = [&]() {\n'
    '            cdda_harness::menu_query harness_menu( "default" );\n'
    '            return ctxt.handle_input();\n'
    '        }();\n'
    '        std::optional<point> coord = ctxt.get_coordinates_text( catacurses::stdscr );')
replace_once(source / "src/do_turn.cpp", 'void handle_key_blocking_activity()\n{',
    'void handle_key_blocking_activity()\n{\n'
    '    cdda_harness::scope harness_activity( cdda_harness::boundary_kind::activity_poll );')
# Eligibility is exactly the native keyboard-pause policy, never private activity data.
replace_once(source / "src/do_turn.cpp",
    '    if( has_unfinished_activity || u.has_destination() ) {',
    '    cdda_harness::activity_interruptible( ( has_unfinished_activity || u.has_destination() ) &&\n'
    '            u.activity.is_interruptible_with_kb() );\n'
    '    if( has_unfinished_activity || u.has_destination() ) {')
replace_once(source / "src/do_turn.cpp",
    '                g->cancel_activity_query( _( "Confirm:" ) );',
    '                cdda_harness::interrupt_owner harness_interrupt;\n'
    '                g->cancel_activity_query( _( "Confirm:" ) );')
# Lambdas restrict ownership to these exact calls; other cancel_auto_move callers
# execute the wrapper without an active interrupt owner and retain ordinary policy.
replace_once(source / "src/game.cpp",
    '    if( query_yn( _( "%s Cancel auto move?" ), text ) )  {',
    '    if( [&]() {\n'
    '        cdda_harness::interrupt_query harness_query;\n'
    '        return query_yn( _( "%s Cancel auto move?" ), text );\n'
    '    }() )  {')
replace_once(source / "src/game.cpp",
    '    if( query_yn( "%s %s", text, u.activity.get_stop_phrase() ) ) {',
    '    if( [&]() {\n'
    '        cdda_harness::interrupt_query harness_query;\n'
    '        return query_yn( "%s %s", text, u.activity.get_stop_phrase() );\n'
    '    }() ) {')
# Ordinary event distractions use a different owner from injected keyboard pause.
# End the exact-category marker before YES/NO/manager callbacks can open other UI.
replace_once(source / "src/game.cpp",
    '    const std::string &action = query_popup()\n'
    '                                .preferred_keyboard_mode( keyboard_mode::keycode )\n'
    '                                .context( "CANCEL_ACTIVITY_OR_IGNORE_QUERY" )',
    '    const std::string action = [&]() {\n'
    '        cdda_harness::menu_query harness_menu( "CANCEL_ACTIVITY_OR_IGNORE_QUERY" );\n'
    '        return query_popup()\n'
    '                                .preferred_keyboard_mode( keyboard_mode::keycode )\n'
    '                                .context( "CANCEL_ACTIVITY_OR_IGNORE_QUERY" )')
replace_once(source / "src/game.cpp",
    '                                .option( "IGNORE", allow_key )\n'
    '                                .query()\n'
    '                                .action;',
    '                                .option( "IGNORE", allow_key )\n'
    '                                .query()\n'
    '                                .action;\n'
    '    }();')
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
