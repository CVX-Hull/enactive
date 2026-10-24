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
# Retained original-file pins also restore retired per-menu hooks on reapplication.
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
for name in ("input_context.cpp", "sdltiles.cpp", "main.cpp", "handle_action.cpp", "do_turn.cpp", "debug.cpp", "game.cpp", "uilist.cpp", "inventory_ui.cpp", "ui_manager.cpp", "cata_imgui.cpp"):
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

# Preserve upstream's byte limit and end cursor/selection policy while using
# ImGui's edit API to keep the buffer, terminator and reported length consistent.
replace_once(source / "src/input_popup.cpp",
    '        if( max > 0 && data->BufTextLen > max ) {\n'
    '            data->BufTextLen = max;\n'
    '            data->SelectionStart = data->BufTextLen;\n'
    '            data->SelectionEnd = data->BufTextLen;\n'
    '            data->CursorPos = data->BufTextLen;\n'
    '            data->BufDirty = true;\n'
    '        }',
    '        if( max > 0 && data->BufTextLen > max ) {\n'
    '            data->DeleteChars( max, data->BufTextLen - max );\n'
    '            data->SelectionStart = data->BufTextLen;\n'
    '            data->SelectionEnd = data->BufTextLen;\n'
    '            data->CursorPos = data->BufTextLen;\n'
    '        }')

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

# This renderer rewrites NoMouse dynamically after keyboard input. Preserve
# synthetic pointer consumption consistently, without changing physical options.
replace_once(source / "src/uilist.cpp", '    if( mouse.hidekb && !cursor_shown ) {',
    '    if( !cdda_harness::enabled() && mouse.hidekb && !cursor_shown ) {')

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
# Use the engine's selecting predicate to omit the cosmetic selected-items column.
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
    '                if( allows_selecting() && cell_index == 0 && entry.is_item() && text_x >= 0 &&\n'
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
    '    cdda_harness::scope harness_input( category, registered_actions, this );')
replace_once(source / "src/handle_action.cpp",
    'input_context game::get_player_input( std::string &action )\n{',
    'input_context game::get_player_input( std::string &action )\n{\n'
    '    cdda_harness::scope harness_player( uquit == QUIT_WATCH ?\n'
    '        cdda_harness::boundary_kind::unsupported : cdda_harness::boundary_kind::normal_play );')
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
    '        if( cdda_harness::enabled() && ( ev.type == SDL_MOUSEMOTION ||\n'
    '            ev.type == SDL_MOUSEBUTTONDOWN || ev.type == SDL_MOUSEBUTTONUP ||\n'
    '            ev.type == SDL_MOUSEWHEEL ) ) { continue; }\n'
    '        imclient->process_input( &ev );')
# ImGui must consume the queued synthetic pointer consistently across frames,
# including when the wrapper's physical mouse option is disabled.
replace_once(source / "src/sdltiles.cpp", '    if( mouse.enabled ) {\n'
    '        ImGui::GetIO().ConfigFlags &= ~ImGuiConfigFlags_NoMouse;',
    '    if( mouse.enabled || cdda_harness::enabled() ) {\n'
    '        ImGui::GetIO().ConfigFlags &= ~ImGuiConfigFlags_NoMouse;')
replace_once(source / "src/sdltiles.cpp",
    '    SDL_GetMouseState( &last_input.mouse_pos.x, &last_input.mouse_pos.y );',
    '    if( !cdda_harness::enabled() ) {\n'
    '        SDL_GetMouseState( &last_input.mouse_pos.x, &last_input.mouse_pos.y );\n'
    '    }')
# Suppress backend polling/capture/warp/cursor manipulation and physical window
# enter/leave pointer resets. Non-harness behavior uses the original code.
backend = source / "src/third-party/imgui/imgui_impl_sdl2.cpp"
replace_once(backend, '#include "imgui.h"',
    '#include "../../cdda_harness.h"\n#include "imgui.h"')
for function in ('ImGui_ImplSDL2_UpdateMouseData(float x_scale, float y_scale)',
                 'ImGui_ImplSDL2_UpdateMouseCursor()'):
    replace_once(backend, 'static void ' + function + '\n{',
        'static void ' + function + '\n{\n    if (cdda_harness::enabled()) return;')
replace_once(backend,
    '            if (window_event == SDL_WINDOWEVENT_ENTER)',
    '            if (cdda_harness::enabled() && (window_event == SDL_WINDOWEVENT_ENTER ||\n'
    '                window_event == SDL_WINDOWEVENT_LEAVE)) return true;\n'
    '            if (window_event == SDL_WINDOWEVENT_ENTER)')
replace_once(backend,
    '    if (bd->MouseLastLeaveFrame && bd->MouseLastLeaveFrame >= ImGui::GetFrameCount() && bd->MouseButtonsDown == 0)',
    '    if (!cdda_harness::enabled() && bd->MouseLastLeaveFrame && bd->MouseLastLeaveFrame >= ImGui::GetFrameCount() && bd->MouseButtonsDown == 0)')
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
receiver_anchor = 'input_event input_manager::get_input_event( const keyboard_mode preferred_keyboard_mode )\n{'
receiver = receiver_anchor + '\n    cdda_harness::input_receiver harness_receiver;'
if 'cdda_harness::input_receiver harness_receiver;' not in section:
    if section.count(receiver_anchor) != 1:
        raise SystemExit('Pinned source anchor changed: SDL input receiver')
    section = section.replace(receiver_anchor, receiver)
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
#include "third-party/imgui/imgui_internal.h"
#include "third-party/imgui/imgui_impl_sdl2.h"

namespace
{
SDL_Surface_Ptr harness_presented_frame;
std::optional<cdda_harness::frame_geometry> harness_presented_geometry;

std::optional<cdda_harness::frame_geometry> default_target_geometry()
{
    if( !window || !renderer || ( SDL_GetWindowFlags( window.get() ) & SDL_WINDOW_MINIMIZED ) ||
        SDL_GetRenderTarget( renderer.get() ) != nullptr ) { return std::nullopt; }
    cdda_harness::frame_geometry geometry;
    SDL_GetWindowSize( window.get(), &geometry.window_width, &geometry.window_height );
    if( SDL_GetRendererOutputSize( renderer.get(), &geometry.output_width, &geometry.output_height ) != 0 ) {
        return std::nullopt;
    }
    for( int dimension : { geometry.window_width, geometry.window_height,
                          geometry.output_width, geometry.output_height } ) {
        if( dimension <= 0 || dimension > 16384 ) { return std::nullopt; }
    }
    if( static_cast<long long>( geometry.output_width ) * geometry.output_height > 16777216 ) {
        return std::nullopt;
    }
    SDL_Rect viewport;
    SDL_RenderGetViewport( renderer.get(), &viewport );
    if( viewport.x < 0 || viewport.y < 0 || viewport.w <= 0 || viewport.h <= 0 ||
        static_cast<long long>( viewport.x ) + viewport.w > geometry.output_width ||
        static_cast<long long>( viewport.y ) + viewport.h > geometry.output_height ) { return std::nullopt; }
    geometry.viewport = { viewport.x, viewport.y, viewport.w, viewport.h };
    return geometry;
}
}

std::optional<cdda_harness::frame_geometry> cdda_harness::cached_frame_geometry()
{
    return harness_presented_geometry;
}

std::optional<cdda_harness::frame_geometry> cdda_harness::current_frame_geometry()
{
    if( !renderer ) { return std::nullopt; }
    SDL_Texture *target = SDL_GetRenderTarget( renderer.get() );
    if( target && SDL_SetRenderTarget( renderer.get(), nullptr ) != 0 ) { return std::nullopt; }
    const auto geometry = default_target_geometry();
    if( target && SDL_SetRenderTarget( renderer.get(), target ) != 0 ) { return std::nullopt; }
    return geometry;
}

void cdda_harness::capture_frame()
{
    if( !enabled() ) { return; }
    harness_presented_geometry.reset();
    // Capture only the full default output target. Its dimensions, not the
    // viewport dimensions, bound the allocation and the full-target read.
    const auto geometry = SDL_GetRenderTarget( renderer.get() ) != nullptr ?
                          std::nullopt : default_target_geometry();
    if( geometry && static_cast<long long>( geometry->output_width ) * geometry->output_height <= 16777216 ) {
        if( !harness_presented_frame || harness_presented_frame->w != geometry->output_width ||
            harness_presented_frame->h != geometry->output_height ) {
            harness_presented_frame = CreateRGBSurface( 0, geometry->output_width, geometry->output_height,
                                       32, 0, 0, 0, 0 );
        }
        if( harness_presented_frame && SDL_RenderReadPixels( renderer.get(), nullptr,
                harness_presented_frame->format->format, harness_presented_frame->pixels,
                harness_presented_frame->pitch ) == 0 ) {
            harness_presented_geometry = geometry;
        }
    }
    if( !harness_presented_geometry ) { harness_presented_frame.reset(); }
    cdda_harness::frame_presented( static_cast<bool>( harness_presented_frame ) );
}

bool cdda_harness::write_frame( const std::string &filename )
{
    return harness_presented_frame && harness_presented_geometry &&
           IMG_SavePNG( harness_presented_frame.get(), filename.c_str() ) == 0;
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
    // A semantic shortcut releases its logical modifiers with the key.
    key.key.keysym.mod = KMOD_NONE;
    imclient->process_input( &key );
}

void cdda_harness::feed_direct_imgui( const direct_input &event )
{
    ImGuiIO &io = ImGui::GetIO();
    restore_on_out_of_scope restore_trickle( io.ConfigInputTrickleEventQueue );
    io.ConfigInputTrickleEventQueue = true;
    if( event.type != direct_input::kind::key ) {
        // Click/text carry no modifiers. Queue normalization before their
        // effects, using normal ImGui consumption rather than physical state.
        io.AddKeyEvent( ImGuiMod_Ctrl, false );
        io.AddKeyEvent( ImGuiMod_Alt, false );
        io.AddKeyEvent( ImGuiMod_Shift, false );
        io.AddKeyEvent( ImGuiMod_Super, false );
    }
    const auto consume = [&]() {
        if( GImGui->InputEventsQueue.empty() ) {
            throw std::runtime_error( "direct widget input was not queued" );
        }
        const ImGuiInputEvent terminal = GImGui->InputEventsQueue.back();
        int pressed_frame = -1;
        int consumed_frame = -1;
        // The pinned backend can separate motion, key/modifier and text events.
        // Eight normal frames bound completion without a nested input loop.
        for( int attempt = 0; attempt < 8; ++attempt ) {
            const int before = ImGui::GetFrameCount();
            ui_manager::redraw();
            refresh_display();
            const int frame = ImGui::GetFrameCount();
            if( frame <= before ) { continue; }
            for( const ImGuiInputEvent &observed : GImGui->InputEventsTrail ) {
                if( terminal.Type == ImGuiInputEventType_MouseButton &&
                    observed.Type == terminal.Type && observed.MouseButton.Button == terminal.MouseButton.Button &&
                    observed.MouseButton.Down ) { pressed_frame = frame; }
                if( terminal.Type == ImGuiInputEventType_Key && observed.Type == terminal.Type &&
                    observed.Key.Key == terminal.Key.Key && observed.Key.Down ) { pressed_frame = frame; }
                if( observed.EventId == terminal.EventId ) { consumed_frame = frame; }
            }
            const bool text = terminal.Type == ImGuiInputEventType_Text;
            const bool modifiers_released = !io.KeyCtrl && !io.KeyAlt && !io.KeyShift && !io.KeySuper;
            const bool released = text ||
                ( terminal.Type == ImGuiInputEventType_MouseButton && !terminal.MouseButton.Down &&
                  !io.MouseDown[terminal.MouseButton.Button] ) ||
                ( terminal.Type == ImGuiInputEventType_Key && !terminal.Key.Down &&
                  !ImGui::GetKeyData( terminal.Key.Key )->Down );
            if( consumed_frame >= 0 && GImGui->InputEventsQueue.empty() && released && modifiers_released &&
                ( text || ( pressed_frame >= 0 && pressed_frame < consumed_frame ) ) ) { return; }
        }
        throw std::runtime_error( "normal widget frames did not consume balanced direct input" );
    };
    if( event.type == direct_input::kind::click ) {
        SDL_Event mouse = {};
        mouse.type = SDL_MOUSEMOTION;
        mouse.motion.windowID = SDL_GetWindowID( window.get() );
        mouse.motion.x = event.widget_position.x;
        mouse.motion.y = event.widget_position.y;
        ImGui_ImplSDL2_ProcessEvent( &mouse );
        mouse = {};
        mouse.type = SDL_MOUSEBUTTONDOWN;
        mouse.button.windowID = SDL_GetWindowID( window.get() );
        mouse.button.button = event.right_button ? SDL_BUTTON_RIGHT : SDL_BUTTON_LEFT;
        mouse.button.x = event.widget_position.x;
        mouse.button.y = event.widget_position.y;
        mouse.button.state = SDL_PRESSED;
        mouse.button.clicks = 1;
        ImGui_ImplSDL2_ProcessEvent( &mouse );
        mouse.type = SDL_MOUSEBUTTONUP;
        mouse.button.state = SDL_RELEASED;
        ImGui_ImplSDL2_ProcessEvent( &mouse );
        consume();
        return;
    }
    SDL_Event key = {};
    key.type = SDL_KEYDOWN;
    key.key.windowID = SDL_GetWindowID( window.get() );
    key.key.state = SDL_PRESSED;
    key.key.keysym.sym = event.widget_key;
    key.key.keysym.scancode = SDL_GetScancodeFromKey( event.widget_key );
    key.key.keysym.mod = event.widget_modifiers.count( keymod_t::shift ) ? KMOD_SHIFT : KMOD_NONE;
    if( event.widget_modifiers.count( keymod_t::ctrl ) ) {
        key.key.keysym.mod |= KMOD_CTRL;
    }
    if( event.widget_modifiers.count( keymod_t::alt ) ) {
        key.key.keysym.mod |= KMOD_ALT;
    }
    if( event.type == direct_input::kind::key ) { ImGui_ImplSDL2_ProcessEvent( &key ); }
    if( !event.widget_text.empty() ) {
        SDL_Event text = {};
        text.type = SDL_TEXTINPUT;
        text.text.windowID = SDL_GetWindowID( window.get() );
        SDL_strlcpy( text.text.text, event.widget_text.c_str(), sizeof( text.text.text ) );
        ImGui_ImplSDL2_ProcessEvent( &text );
    }
    key.type = SDL_KEYUP;
    key.key.state = SDL_RELEASED;
    // Release logical modifiers too, so a shortcut cannot leave ImGui's
    // queued Ctrl/Alt/Shift state held for a later text or click operation.
    key.key.keysym.mod = KMOD_NONE;
    if( event.type == direct_input::kind::key ) { ImGui_ImplSDL2_ProcessEvent( &key ); }
    consume();
}
'''
text = path.read_text()
if 'void cdda_harness::feed_imgui(' not in text:
    path.write_text(text + '\n' + adapter)
print(f'Applied harness integration to {source}')
