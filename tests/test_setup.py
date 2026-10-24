"""Setup failure boundaries; these tests do not build or launch CDDA."""
from contextlib import redirect_stdout
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import subprocess
import shutil
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from tools import check, setup


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def archive(self, entries):
        path = self.root / "source.tar.gz"
        with tarfile.open(path, "w:gz") as bundle:
            for name, data, link in entries:
                member = tarfile.TarInfo(name)
                if link is not None:
                    member.type = tarfile.SYMTYPE
                    member.linkname = link
                    bundle.addfile(member)
                else:
                    member.size = len(data)
                    bundle.addfile(member, BytesIO(data))
        return path

    def patch_fixture(self, *, extra_poll=False, duplicate_normal=False, duplicate_direction=False):
        """Small pinned-source fixture tests patch mechanics, never native behavior."""
        repository = self.root / "repository"
        (repository / "native").mkdir(parents=True)
        (repository / "tools").mkdir()
        actual = Path(__file__).resolve().parents[1]
        for name in ("cdda_harness.h", "cdda_harness.cpp"):
            shutil.copyfile(actual / "native" / name, repository / "native" / name)
        shutil.copyfile(actual / "tools/patch_game.py", repository / "tools/patch_game.py")
        originals = {
            "Makefile": "-mmacosx-version-min=10.15\n-mmacosx-version-min=10.15\n",
            "src/cata_imgui.cpp": ('    ImGuiIO &io = ImGui::GetIO();\n'
                '    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;     // Enable Keyboard Controls\n'),
            "src/ui_manager.cpp": ('                    if( ui.redraw_cb ) {\n'
                '                        ui.default_cursor();\n'
                '                        ui.redraw_cb( ui );\n}\n'),
            "src/uilist.cpp": ('void uilist_impl::draw_controls()\n{\n'
                '    if( mouse.hidekb && !cursor_shown ) {\n'
                '        ImGui::GetIO().ConfigFlags |= ImGuiConfigFlags_NoMouse;\n'
                '    } else {\n'
                '        ImGui::GetIO().ConfigFlags &= ~ImGuiConfigFlags_NoMouse;\n    }\n'
                '                    for( int i = clipper.DisplayStart; i < clipper.DisplayEnd; i++ ) {\n'
                '                        auto entry = parent.entries[parent.fentries[i]];\n'
                '                        bool is_selected = i == parent.fselected;\n'
                '                        ImGui::TableSetColumnIndex( 1 );\n'
                '                        cataimgui::draw_colored_text( str1, color );\n'
                '                        ImGui::TableSetColumnIndex( 2 );\n}\n}\n'),
            "src/inventory_ui.cpp": ('void inventory_selector::refresh_window()\n{\n'
                '    cata_assert( w_inv );\n'
                '}\n'
                'void inventory_column::draw()\n{\n'
                '    if( !visible() ) {\n        return;\n    }\n'
                '    for( size_t index = page_offset, line = 0; index < entries.size() &&\n'
                '         line < entries_per_page; ++index, ++line ) {\n'
                '        inventory_entry &entry = entries[index];\n'
                '        const bool selected = active && is_highlighted( entry );\n'
                '        size_t count = denial.empty() ? cells.size() : 1;\n'
                '        for( size_t cell_index = 0; cell_index < count; ++cell_index ) {\n'
                '            if( !cells[cell_index].visible() ) {\n                continue;\n            }\n'
                '            if( text_width > 0 ) {\n'
                '                if( entry.is_item() && ( selected || !entry.is_selectable() ) ) {\n'
                '                    trim_and_print( win, point( text_x, yy ), text_width, c_dark_gray, text );\n'
                '                } else {\n'
                '                    trim_and_print( win, point( text_x, yy ), text_width, entry_cell_cache.color, text );\n'
                '                }\n            }\n\n            x1 = x2;\n        }\n\n'
                '        if( entry.is_item() ) {\n            int xx = p.x;\n        }\n    }\n}\n'
                'void unrelated() { trim_and_print( win, point( 0, 0 ), 10, c_white, hidden ); }\n'),

            "src/input_popup.cpp": ('    if( data->EventFlag == ImGuiInputTextFlags_CallbackEdit ) {\n'
                '        int max = popup->get_max_input_length();\n'
                '        if( max > 0 && data->BufTextLen > max ) {\n'
                '            data->BufTextLen = max;\n'
                '            data->SelectionStart = data->BufTextLen;\n'
                '            data->SelectionEnd = data->BufTextLen;\n'
                '            data->CursorPos = data->BufTextLen;\n'
                '            data->BufDirty = true;\n'
                '        }\n    }\n'),
            "src/input_context.cpp": "const std::string &input_context::handle_input( const int timeout )\n{\n        next_action = inp_mngr.get_input_event( preferred_keyboard_mode );\n}",
            "src/handle_action.cpp": "input_context game::get_player_input( std::string &action )\n{\n}",
            "src/bodygraph.cpp": ('    bool done = false;\n'
                '    while( !done ) {\n        ui_manager::redraw();\n'
                '        std::string action = ctxt.handle_input();\n'
                '        if( action == "QUIT" || ( action == "LEFT" && id != bodygraph_full_body ) ) {\n}\n}\n'
                'void unrelated() { std::string action = ctxt.handle_input(); }\n'),
            "src/action.cpp": ('    input_context ctxt( "DEFAULTMODE", keyboard_mode::keycode );\n'
                '        action = ctxt.handle_input();\n'
                '        if( std::optional<tripoint_rel_ms> vec = ctxt.get_direction_rel_ms( action ) ) {\n}\n'),
            "src/ui_iteminfo.cpp": ('void iteminfo_window::execute()\n{\n'
                '    if( data.without_getch ) {\n        ui_manager::redraw();\n        return;\n    }\n\n'
                '    while( true ) {\n        ui_manager::redraw();\n'
                '        std::string action = ctxt.handle_input();\n\n'
                '        if( data.handle_scrolling && data.arrow_scrolling && action == "UP" ) {\n}\n}\n}\n'
                'void unrelated() { std::string action = ctxt.handle_input(); }\n'),
            "src/game_inventory.cpp": ('bool game_menus::inv::compare_item_menu::show()\n{\n'
                '    while( true ) {\n        ui_manager::redraw();\n\n'
                '        std::string action = has_button_action() ? get_button_action() : ctxt.handle_input();\n\n'
                '        if( action == "UP" ) {\n}\n}\n}\n'
                'void unrelated() { std::string action = ctxt.handle_input(); }\n'),
            "src/output.cpp": ('input_event draw_item_info( const std::function<catacurses::window()> &init_window,\n'
                '                            item_info_data &data )\n{\n'
                '    input_context ctxt( "default", keyboard_mode::keychar );\n'
                '    while( true ) {\n        ui_manager::redraw();\n'
                '        action = ctxt.handle_input();\n'
                '        std::optional<point> coord = ctxt.get_coordinates_text( catacurses::stdscr );\n}\n}\n'
                'void unrelated() { action = ctxt.handle_input(); }\n'),
            "src/do_turn.cpp": 'void handle_key_blocking_activity()\n{\n    if( has_unfinished_activity || u.has_destination() ) {\n                g->cancel_activity_query( _( "Confirm:" ) );\n}\n}',
            "src/game.cpp": ('    if( query_yn( _( "%s Cancel auto move?" ), text ) )  {\n}\n'
                '    if( query_yn( "%s %s", text, u.activity.get_stop_phrase() ) ) {\n}\n'
                '    const std::string &action = query_popup()\n'
                '                                .preferred_keyboard_mode( keyboard_mode::keycode )\n'
                '                                .context( "CANCEL_ACTIVITY_OR_IGNORE_QUERY" )\n'
                '                                .option( "YES", allow_key )\n'
                '                                .option( "NO", allow_key )\n'
                '                                .option( "MANAGER", allow_key )\n'
                '                                .option( "IGNORE", allow_key )\n'
                '                                .query()\n'
                '                                .action;\n'
                '    if( action == "YES" ) { u.cancel_activity(); }\n'
                'void unrelated() { query_popup().context( "OTHER_QUERY" ).query(); }\n'),
            "src/debug.cpp": "    for( bool stop = false; !stop; ) {\n        ui_manager::redraw();\n}",
            "src/main.cpp": "        while( !do_turn() ) {}",
            "src/third-party/imgui/imgui_impl_sdl2.cpp": (
                '#include "imgui.h"\n'
                'static void ImGui_ImplSDL2_UpdateMouseData(float x_scale, float y_scale)\n{\n}\n'
                'static void ImGui_ImplSDL2_UpdateMouseCursor()\n{\n}\n'
                '            if (window_event == SDL_WINDOWEVENT_ENTER) {}\n'
                '    if (bd->MouseLastLeaveFrame && bd->MouseLastLeaveFrame >= ImGui::GetFrameCount() && bd->MouseButtonsDown == 0) {}\n'),
            "src/sdltiles.cpp": ("    while( SDL_PollEvent( &ev ) ) {\n        imclient->process_input( &ev );\n}\n"
                "    SDL_RenderPresent( renderer.get() );\n"
                "    if( mouse.enabled ) {\n"
                "        ImGui::GetIO().ConfigFlags &= ~ImGuiConfigFlags_NoMouse;\n}\n"
                "    SDL_GetMouseState( &last_input.mouse_pos.x, &last_input.mouse_pos.y );\n"
                "input_event input_manager::get_input_event( const keyboard_mode preferred_keyboard_mode )\n{\n"
                "    if( inputdelay < 0 ) {\n        do {\n" + "CheckMessages();\n" * (4 if extra_poll else 3) +
                "}\n}\nbool gamepad_available() {}"),
        }
        if duplicate_normal:
            originals["src/handle_action.cpp"] *= 2
        if duplicate_direction:
            originals["src/action.cpp"] *= 2
        source = self.root / "source"
        for name, data in originals.items():
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(data)
        (repository / "native/upstream.json").write_text(json.dumps({"source_files": {
            name: hashlib.sha256(data.encode()).hexdigest() for name, data in originals.items()}}))
        return repository, source

    def run_patch(self, repository, source):
        return subprocess.run([sys.executable, str(repository / "tools/patch_game.py"), str(source)],
                              text=True, capture_output=True, check=False)

    def test_native_v6_patch_is_repeatable_and_scopes_exact_input_paths(self):
        repository, source = self.patch_fixture()
        first = self.run_patch(repository, source)
        self.assertEqual(first.returncode, 0, first.stderr)
        expected = {path.relative_to(source): path.read_bytes()
                    for path in source.rglob("*") if path.is_file()}
        for name in ("ui_iteminfo.cpp", "game_inventory.cpp", "output.cpp", "bodygraph.cpp", "cata_imgui.cpp", "inventory_ui.cpp", "input_popup.cpp",
                     "third-party/imgui/imgui_impl_sdl2.cpp"):
            (source / "src" / name).write_text("stale patched contents")
        second = self.run_patch(repository, source)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(expected, {path.relative_to(source): path.read_bytes()
                                    for path in source.rglob("*") if path.is_file()})
        imgui = (source / "src/cata_imgui.cpp").read_text()
        self.assertIn('#include "cdda_harness.h"', imgui)
        self.assertEqual(imgui.count('if( cdda_harness::enabled() ) { io.ConfigInputTextCursorBlink = false; }'), 1)
        self.assertLess(imgui.index('ImGuiIO &io = ImGui::GetIO();'), imgui.index('io.ConfigInputTextCursorBlink = false;'))
        popup = (source / "src/input_popup.cpp").read_text()
        self.assertEqual(popup.count('data->DeleteChars( max, data->BufTextLen - max );'), 1)
        self.assertNotIn('data->BufTextLen = max;', popup)
        self.assertNotIn('data->BufDirty = true;', popup)
        # Retain upstream's end cursor/selection policy after ImGui truncates.
        for field in ("SelectionStart", "SelectionEnd", "CursorPos"):
            self.assertIn(f'data->{field} = data->BufTextLen;', popup)
        self.assertIn("harness_input( category, registered_actions, this )", (source / "src/input_context.cpp").read_text())
        self.assertIn("harness_player( uquit == QUIT_WATCH", (source / "src/handle_action.cpp").read_text())
        for name in ("action.cpp", "bodygraph.cpp", "ui_iteminfo.cpp", "game_inventory.cpp", "output.cpp"):
            self.assertEqual((source / "src" / name).read_bytes(),
                             (source / ".harness-originals/src" / name).read_bytes())
        self.assertIn("boundary_kind::activity_poll", (source / "src/do_turn.cpp").read_text())
        self.assertIn("boundary_kind::debug_prompt", (source / "src/debug.cpp").read_text())
        activity = (source / "src/do_turn.cpp").read_text()
        self.assertIn("activity_interruptible( ( has_unfinished_activity || u.has_destination() ) &&", activity)
        self.assertIn("cdda_harness::interrupt_owner harness_interrupt;", activity)
        self.assertEqual((source / "src/game.cpp").read_text().count("interrupt_query harness_query"), 2)
        distraction = (source / "src/game.cpp").read_text()
        self.assertNotIn('menu_query', distraction)
        for action in ("YES", "NO", "MANAGER", "IGNORE"):
            self.assertEqual(distraction.count(f'.option( "{action}", allow_key )'), 1)
        self.assertIn('void unrelated() { query_popup().context( "OTHER_QUERY" ).query(); }', distraction)
        sdl = (source / "src/sdltiles.cpp").read_text()
        self.assertEqual(sdl.count("cdda_harness::poll("), 3)
        self.assertEqual(sdl.count("cdda_harness::input_receiver harness_receiver;"), 1)
        receive = sdl[sdl.index('input_event input_manager::get_input_event('):sdl.index('bool gamepad_available()')]
        self.assertLess(receive.index('input_receiver harness_receiver;'), receive.index('cdda_harness::boundary();'))
        self.assertIn('harness_input( category, registered_actions, this )',
                      (source / 'src/input_context.cpp').read_text())
        self.assertLess(sdl.index("cdda_harness::capture_frame();"), sdl.index("SDL_RenderPresent("))
        self.assertIn("frame_presented( static_cast<bool>( harness_presented_frame ) )", sdl)
        encoder = sdl[sdl.index('bool cdda_harness::write_frame('):sdl.index('void cdda_harness::feed_imgui(')]
        self.assertIn('IMG_SavePNG( harness_presented_frame.get(), filename.c_str() )', encoder)
        self.assertNotIn('capture_frame(', encoder)
        self.assertNotIn('SDL_RenderReadPixels(', encoder)

    def test_native_direct_schema_translation_and_commit_guards(self):
        native = (Path(__file__).resolve().parents[1] / "native/cdda_harness.cpp").read_text()
        self.assertIn('integer_member( request, "protocol" ) != 6', native)
        self.assertNotIn('integer_member( request, "protocol" ) != 4', native)
        direct = native[native.index('direct_input direct_event('):native.index('bool uuid_id(')]
        for guard in ('input.size() != 3', 'input.size() != 2', 'input.size() != 5',
                      'modifiers.size() > 3', '!explicit_modifiers.insert(',
                      'single_printable_scalar( text )', 'geometry != saved_geometry',
                      'x >= geometry->output_width', 'y >= geometry->output_height',
                      'MouseInput::LeftButtonReleased', 'MouseInput::RightButtonReleased'):
            self.assertIn(guard, direct)
        for forbidden in ('sdl_keysym_to_curses(', 'SDL_GetKeyboardState(', 'handle_arrow_combo(',
                          'feed_imgui(', 'process_input(', 'LeftButtonPressed', 'RightButtonPressed'):
            self.assertNotIn(forbidden, direct)
        poll = native[native.index('bool poll( keyboard_mode'):]
        self.assertLess(poll.index('direct = direct_event('), poll.index('ordinary_commit_gate( request, false, direct && direct->type == direct_input::kind::click );'))
        self.assertLess(poll.index('ordinary_commit_gate( request, false, direct && direct->type == direct_input::kind::click );'), poll.index('feed_direct_imgui( *direct );'))
        self.assertIn('kind == "direct" && request.get_bool( "require_exact_frame" )', poll)
        gate = native[native.index('void ordinary_commit_gate('):native.index('input_event action_event(')]
        self.assertIn('current_frame_geometry() != saved_geometry', gate)
        self.assertIn('cached_frame_geometry() != saved_geometry', gate)
        self.assertLess(gate.index('current_frame_geometry() != saved_geometry'), gate.index('exact_frame_gate();'))
        self.assertLess(gate.index('exact_frame_gate();'), gate.rindex('current_frame_geometry() != saved_geometry'))
        self.assertIn('out.member( "frame_geometry" )', native)
        scalar = native[native.index('int single_printable_scalar('):native.index('std::optional<frame_geometry> input_geometry(')]
        for guard in ('text.size() > 4', 'UTF8_getch( text )', 'code > 0x10ffff',
                      'code >= 0xd800 && code <= 0xdfff', 'code < 32', 'code >= 127 && code <= 159',
                      'code == 0x2028', 'code == 0x2029', 'utf32_to_utf8( code ) != text',
                      'code > IM_UNICODE_CODEPOINT_MAX'):
            self.assertIn(guard, scalar)
        self.assertIn('x * geometry->window_width / geometry->output_width', direct)
        self.assertIn('y * geometry->window_height / geometry->output_height', direct)
        self.assertIn('event.widget_position = point( static_cast<int>( x ), static_cast<int>( y ) )', direct)
        self.assertIn('event.widget_modifiers = event.engine.modifiers', direct)
        self.assertIn("event.widget_key - 'a' + 1", direct)
        self.assertIn('arrow && ( ctrl || shift )', direct)

    def test_direct_widget_completion_is_bounded_and_failure_stays_unknown(self):
        repository, source = self.patch_fixture()
        result = self.run_patch(repository, source)
        self.assertEqual(result.returncode, 0, result.stderr)
        sdl = (source / "src/sdltiles.cpp").read_text()
        legacy = sdl[sdl.index('void cdda_harness::feed_imgui('):sdl.index('void cdda_harness::feed_direct_imgui(')]
        self.assertNotIn('feed_direct_imgui(', legacy)
        self.assertNotIn('ConfigInputTrickleEventQueue', legacy)
        direct = sdl[sdl.index('void cdda_harness::feed_direct_imgui('):]
        for guard in ('restore_on_out_of_scope restore_trickle( io.ConfigInputTrickleEventQueue )',
                      'io.ConfigInputTrickleEventQueue = true', 'attempt < 8',
                      'ui_manager::redraw();', 'refresh_display();',
                      'observed.EventId == terminal.EventId', 'GImGui->InputEventsQueue.empty()',
                      'pressed_frame < consumed_frame', '!io.MouseDown[terminal.MouseButton.Button]',
                      '!ImGui::GetKeyData( terminal.Key.Key )->Down'):
            self.assertIn(guard, direct)
        self.assertNotIn('ImGui::NewFrame(', direct)
        self.assertNotIn('ClearInput', direct)
        self.assertIn('if( !cdda_harness::enabled() && mouse.hidekb && !cursor_shown )',
                      (source / "src/uilist.cpp").read_text())
        native = (Path(__file__).resolve().parents[1] / "native/cdda_harness.cpp").read_text()
        poll = native[native.index('bool poll( keyboard_mode'):]
        self.assertLess(poll.index('input_committed = true;'), poll.index('feed_direct_imgui( *direct );'))
        fault = poll[poll.index('if( input_committed )'):poll.index('publish( id, "rejected", e.what() );')]
        for guard in ('fault_pause();',
                      'publish( id, "dispatched", e.what(), false )', 'return false;'):
            self.assertIn(guard, fault)

    def test_semantic_modifier_release_and_direct_click_text_normalization(self):
        repository, source = self.patch_fixture()
        result = self.run_patch(repository, source)
        self.assertEqual(result.returncode, 0, result.stderr)
        sdl = (source / "src/sdltiles.cpp").read_text()
        legacy = sdl[sdl.index('void cdda_harness::feed_imgui('):sdl.index('void cdda_harness::feed_direct_imgui(')]
        release = legacy[legacy.index('key.type = SDL_KEYUP;'):]
        self.assertLess(release.index('key.key.keysym.mod = KMOD_NONE;'), release.index('imclient->process_input( &key );'))
        direct = sdl[sdl.index('void cdda_harness::feed_direct_imgui('):]
        for modifier in ('Ctrl', 'Alt', 'Shift', 'Super'):
            self.assertIn(f'io.AddKeyEvent( ImGuiMod_{modifier}, false )', direct)
            self.assertIn(f'!io.Key{modifier}', direct)
        self.assertLess(direct.index('io.AddKeyEvent( ImGuiMod_Shift, false )'), direct.index('SDL_Event mouse = {}'))
        self.assertIn('empty() && released && modifiers_released', direct)
        self.assertNotIn('SDL_GetKeyboardState(', direct)

    def test_native_pointer_geometry_and_physical_filtering(self):
        repository, source = self.patch_fixture()
        result = self.run_patch(repository, source)
        self.assertEqual(result.returncode, 0, result.stderr)
        sdl = (source / "src/sdltiles.cpp").read_text()
        self.assertLess(sdl.index('cdda_harness::human_input();'), sdl.index('ev.type == SDL_MOUSEMOTION'))
        self.assertIn('if( !cdda_harness::enabled() )', sdl)
        self.assertIn('if( mouse.enabled || cdda_harness::enabled() )', sdl)
        capture = sdl[sdl.index('void cdda_harness::capture_frame()'):sdl.index('bool cdda_harness::write_frame(')]
        for guard in ('SDL_GetRenderTarget( renderer.get() ) != nullptr', '16777216',
                      'geometry->output_width, geometry->output_height', 'frame_presented('):
            self.assertIn(guard, capture)
        self.assertIn('SDL_WINDOW_MINIMIZED', sdl)
        self.assertIn('16384', sdl)
        self.assertIn('SDL_SetRenderTarget( renderer.get(), target )', sdl)
        direct = sdl[sdl.index('void cdda_harness::feed_direct_imgui('):]
        for event in ('SDL_MOUSEMOTION', 'SDL_MOUSEBUTTONDOWN', 'SDL_MOUSEBUTTONUP'):
            self.assertIn(event, direct)
        self.assertIn('event.widget_position.x', direct)
        self.assertIn('key.key.keysym.mod = KMOD_NONE', sdl)
        backend = (source / "src/third-party/imgui/imgui_impl_sdl2.cpp").read_text()
        for function in ('ImGui_ImplSDL2_UpdateMouseData(float x_scale, float y_scale)',
                         'ImGui_ImplSDL2_UpdateMouseCursor()'):
            self.assertIn(function + '\n{\n    if (cdda_harness::enabled()) return;', backend)
        self.assertIn('!cdda_harness::enabled() && bd->MouseLastLeaveFrame', backend)
        restored = backend.replace('#include "../../cdda_harness.h"\n', '').replace(
            '\n    if (cdda_harness::enabled()) return;', '').replace(
            '            if (cdda_harness::enabled() && (window_event == SDL_WINDOWEVENT_ENTER ||\n'
            '                window_event == SDL_WINDOWEVENT_LEAVE)) return true;\n', '').replace(
            '!cdda_harness::enabled() && bd->MouseLastLeaveFrame', 'bd->MouseLastLeaveFrame')
        original = source / ".harness-originals/src/third-party/imgui/imgui_impl_sdl2.cpp"
        self.assertEqual(restored, original.read_text())

    def test_visible_ui_hooks_are_at_actual_clipped_and_paged_renderers(self):
        repository, source = self.patch_fixture()
        original_inventory = (source / "src/inventory_ui.cpp").read_text()
        result = self.run_patch(repository, source)
        self.assertEqual(result.returncode, 0, result.stderr)
        uilist = (source / "src/uilist.cpp").read_text()
        self.assertIn('cdda_harness::ui_begin( "uilist", "UILIST", "" )', uilist)
        self.assertLess(uilist.index('clipper.DisplayStart'), uilist.index('cdda_harness::ui_row('))
        self.assertIn('ImGui::GetCurrentWindow()->ClipRect', uilist)
        self.assertIn('pos.y + ImGui::GetTextLineHeight() > clip.Max.y', uilist)
        self.assertIn('ImGui::CalcTextSize( label.c_str() ).x', uilist)
        self.assertIn('label.resize( end )', uilist)
        inventory = (source / "src/inventory_ui.cpp").read_text()
        self.assertIn('cdda_harness::ui_begin( "inventory", "INVENTORY", "" )', inventory)
        # Only cosmetic columns are excluded: disabled rows, hotkeys and exact
        # active focus retain their renderer-derived payload and clipping guards.
        inventory_hook = (
            '                if( allows_selecting() && cell_index == 0 && entry.is_item() && text_x >= 0 &&\n'
            '                    text_x + static_cast<int>( text_width ) <= getmaxx( win ) &&\n'
            '                    yy >= 0 && yy < getmaxy( win ) ) {\n'
            '                    const std::string label = remove_color_tags( trim_by_length( text, text_width ) );\n'
            '                    const char invlet = entry.get_invlet();\n'
            '                    const std::string hotkey = p.x >= 0 && p.x < getmaxx( win ) &&\n'
            '                        invlet >= 32 && invlet <= 126 ? std::string( 1, invlet ) : std::string();\n'
            '                    cdda_harness::ui_row( label, entry.is_selectable(), hotkey, selected );\n'
            '                }\n')
        self.assertEqual(inventory.count(inventory_hook), 1)
        self.assertEqual(inventory.count('cdda_harness::ui_row('), 1)
        self.assertIn('text_width, entry_cell_cache.color, text );\n                }\n' + inventory_hook, inventory)
        # Removing only the two attestation hooks/include recovers the original
        # renderer, including visible-column/page/cell fences and disabled draws.
        self.assertEqual(inventory.replace(inventory_hook, '').replace(
            '    cdda_harness::ui_begin( "inventory", "INVENTORY", "" );\n', '').replace(
            '#include "cdda_harness.h"\n', ''), original_inventory)
        self.assertIn('void unrelated() { trim_and_print( win, point( 0, 0 ), 10, c_white, hidden ); }', inventory)
        manager = (source / "src/ui_manager.cpp").read_text()
        self.assertIn('cdda_harness::ui_redraw( ui.is_on_top );\n                        ui.redraw_cb( ui );', manager)

    def test_native_v6_commit_and_presented_ui_guards(self):
        # Source-lane checks establish executable guard placement, not C++ execution.
        native = (Path(__file__).resolve().parents[1] / "native/cdda_harness.cpp").read_text()
        self.assertIn('out.member( "protocol", 6 )', native)
        self.assertNotIn(r'\"protocol\":3', native)
        self.assertIn('out.member( "pause_origin", pause_origin )', native)
        self.assertIn('out.member( "takeover_generation", takeover_generation )', native)
        self.assertIn('request.get_string( "boundary_id" ) != boundary_id', native)
        self.assertIn('integer_member( request, "takeover_generation" ) != takeover_generation', native)
        poll = native[native.index('bool poll( keyboard_mode'):]
        self.assertEqual(poll.count('ordinary_gate( request );'), 1)
        self.assertLess(poll.rindex('ordinary_commit_gate( request, false, direct && direct->type == direct_input::kind::click );'), poll.index('pending = id;'))
        human = native[native.index('void human_input()'):native.index('void boundary()')]
        self.assertIn('++takeover_generation;', human)
        world = native[native.index('void playing('):native.index('void frame_presented(')]
        self.assertNotIn('takeover_generation =', world)
        self.assertIn('pause_origin != "human"', world)
        self.assertIn('staged_ui.reset();', native)
        self.assertIn('ui_boundary == boundary_id && ui_session == session && ui_revision == revision', native)
        self.assertIn('if( next_ui != presented_ui )', native)
        self.assertIn('if( !ui_top || !staged_ui || staged_ui->rows.size() >= 32 )', native)

    def test_ordinary_requests_require_saved_frame_and_exact_flag(self):
        # These source checks do not establish native PNG or input behavior.
        native = (Path(__file__).resolve().parents[1] / "native/cdda_harness.cpp").read_text()
        poll = native[native.index('bool poll( keyboard_mode'):]
        self.assertIn('kind == "resume" ? 11 : 12', poll)
        self.assertIn('kind == "observe" || kind == "pause" ? 4', poll)
        gate = native[native.index('void ordinary_gate('):native.index('input_event action_event(')]
        for guard in ('require_current_frame && source != frame_name', 'frame_name.empty()',
                      '!saved_frame_ok', 'frame_boundary != boundary_id', 'frame_session != session',
                      'frame_revision != revision', 'checked_ms - frame_ms > 3000',
                      'presented_boundary != boundary_id', 'presented_session != session',
                      'presented_revision != revision', 'checked_ms - presented_ms > 3000',
                      'issued == retained_frames.end()', 'checked_ms - issued->timestamp_ms > 3000',
                      'issued->metadata != capture_metadata( cached_frame_geometry() )',
                      'integer_member( request, "deadline_ms" ) < now_ms()', 'authority_gate( request );'):
            self.assertIn(guard, gate)
        self.assertIn('request.get_bool( "require_exact_frame" )', gate)
        self.assertNotIn('request.get_bool( "require_exact_frame",', gate)

    def test_exact_png_comparison_is_bounded_and_preserves_owned_files(self):
        native = (Path(__file__).resolve().parents[1] / "native/cdda_harness.cpp").read_text()
        comparison = native[native.rindex('bool same_frame_png('):native.index('void ordinary_commit_gate(')]
        self.assertIn('maximum_frame_bytes = 32 * 1024 * 1024', comparison)
        self.assertIn('std::array<char, 32 * 1024>', comparison)
        self.assertEqual(comparison.count('O_RDONLY | O_NOFOLLOW | O_NONBLOCK'), 2)
        for guard in ('S_ISREG( saved_info.st_mode )', 'S_ISREG( latest_info.st_mode )',
                      'saved_info.st_size > 0', 'saved_info.st_size <= maximum_frame_bytes',
                      'saved_info.st_size == latest_info.st_size', 'latest_info.st_dev == owned.st_dev',
                      'latest_info.st_ino == owned.st_ino', 'saved_read == amount', 'latest_read == amount',
                      'std::equal(', 'read( saved_fd, &trailing, 1 ) == 0',
                      'read( latest_fd, &trailing, 1 ) == 0', 'close( saved_fd )', 'close( latest_fd )'):
            self.assertIn(guard, comparison)
        temporary = comparison[comparison.index('void exact_frame_gate('):]
        self.assertIn('const std::string saved = path( frame_name );', temporary)
        self.assertIn('O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600', temporary)
        self.assertLess(temporary.index('if( descriptor < 0 )'), temporary.index('write_frame( latest )'))
        for guard in ('fstat( descriptor, &owned ) == 0', 'current.st_dev == owned.st_dev',
                      'current.st_ino == owned.st_ino', 'unlink( latest.c_str() ) == 0',
                      'close( descriptor ) == 0', 'if( !removed || !closed )', 'if( !same )'):
            self.assertIn(guard, temporary)
        self.assertNotIn('unlink( saved', temporary)
        for forbidden in ('capture_frame(', 'refresh_display(', 'ui_manager::redraw(', 'sync_scope('):
            self.assertNotIn(forbidden, comparison)

    def test_exact_png_comparison_runs_once_at_final_commit_with_revocation_checks(self):
        native = (Path(__file__).resolve().parents[1] / "native/cdda_harness.cpp").read_text()
        gate = native[native.index('void ordinary_commit_gate('):native.index('input_event action_event(')]
        self.assertIn('click || request.get_bool( "require_exact_frame" )', gate)
        self.assertEqual(gate.count('exact_frame_gate();'), 1)
        self.assertEqual(gate.count('ordinary_gate( request, require_current_frame );'), 2)
        self.assertEqual(gate.count('!resuming && ( paused || fs::exists( path( "pause" ) ) )'), 2)
        self.assertLess(gate.index('ordinary_gate( request, require_current_frame );'), gate.index('exact_frame_gate();'))
        self.assertLess(gate.index('request.get_bool( "require_exact_frame" )'), gate.index('exact_frame_gate();'))
        self.assertLess(gate.index('exact_frame_gate();'), gate.rindex('ordinary_gate( request, require_current_frame );'))
        self.assertLess(gate.index('exact_frame_gate();'), gate.rindex('fs::exists( path( "pause" ) )'))
        for guard in ('!waiting_interrupt.empty()', 'fs::exists( path( "control.json" ) )',
                      'fs::exists( path( "control-claimed.json" ) )',
                      'integer_member( request, "deadline_ms" ) < now_ms()'):
            self.assertLess(gate.index('exact_frame_gate();'), gate.index(guard))
        self.assertLess(gate.rindex('ordinary_gate( request, require_current_frame );'), gate.rindex('fs::exists( path( "pause" ) )'))
        poll = native[native.index('bool poll( keyboard_mode'):]
        resume = poll[poll.index('if( kind == "resume" )'):poll.index('if( paused ||')]
        self.assertLess(resume.index('ordinary_commit_gate( request, true, false );'),
                        resume.index('fs::remove( path( "pause" ) );'))
        self.assertLess(resume.index('fs::remove( path( "pause" ) );'), resume.index('paused = false;'))
        self.assertLess(poll.index('event = *binding;'), poll.index('ordinary_commit_gate( request, false, direct && direct->type == direct_input::kind::click );'))
        self.assertLess(poll.index('ordinary_commit_gate( request, false, direct && direct->type == direct_input::kind::click );'), poll.index('++revision;\n        pending = id;'))

    def test_patch_rejects_changed_patched_owner_hashes_and_anchors(self):
        for name in ("src/uilist.cpp", "src/inventory_ui.cpp", "src/ui_manager.cpp", "src/cata_imgui.cpp",
                     "src/input_popup.cpp", "src/third-party/imgui/imgui_impl_sdl2.cpp"):
            for change in ("hash", "missing", "duplicate"):
                with self.subTest(owner=name, change=change), tempfile.TemporaryDirectory() as temporary:
                    self.root = Path(temporary)
                    repository, source = self.patch_fixture()
                    path = source / name
                    original = path.read_text()
                    altered = original * 2 if change == "duplicate" else "changed"
                    path.write_text(altered)
                    if change != "hash":
                        pins = repository / "native/upstream.json"
                        pin = json.loads(pins.read_text())
                        pin["source_files"][name] = hashlib.sha256(altered.encode()).hexdigest()
                        pins.write_text(json.dumps(pin))
                    result = self.run_patch(repository, source)
                    self.assertNotEqual(result.returncode, 0)
                    message = "Upstream source differs" if change == "hash" else "Pinned source anchor changed"
                    self.assertIn(message, result.stderr)

    def test_patch_rejects_changed_upstream_hash(self):
        repository, source = self.patch_fixture()
        (source / "src/handle_action.cpp").write_text("changed")
        result = self.run_patch(repository, source)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Upstream source differs", result.stderr)

    def test_patch_rejects_changed_item_owner_hashes(self):
        for name in ("src/ui_iteminfo.cpp", "src/game_inventory.cpp", "src/output.cpp", "src/bodygraph.cpp"):
            with self.subTest(owner=name), tempfile.TemporaryDirectory() as temporary:
                self.root = Path(temporary)
                repository, source = self.patch_fixture()
                (source / name).write_text("changed")
                result = self.run_patch(repository, source)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"Upstream source differs from pinned release: {name}", result.stderr)

    def test_patch_rejects_ambiguous_normal_and_poll_anchors(self):
        for flags, message in (({"duplicate_normal": True}, "Pinned source anchor changed"),
                               ({"extra_poll": True}, "SDL poll anchors changed")):
            with self.subTest(flags=flags), tempfile.TemporaryDirectory() as temporary:
                previous = self.root
                self.root = Path(temporary)
                try:
                    repository, source = self.patch_fixture(**flags)
                    result = self.run_patch(repository, source)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(message, result.stderr)
                finally:
                    self.root = previous

    def test_default_status_is_read_only(self):
        (self.root / "native").mkdir()
        (self.root / "native/upstream.json").write_text('{"release": "test"}')
        with patch.object(setup, "ROOT", self.root), redirect_stdout(StringIO()):
            self.assertEqual(setup.main([]), 0)
        self.assertFalse((self.root / ".runtime").exists())
        self.assertFalse((self.root / ".venv").exists())

    def test_corrupt_cached_download_is_rejected_without_network(self):
        path = self.root / "source.tar.gz"
        path.write_bytes(b"corrupt")
        with patch.object(setup.urllib.request, "urlopen") as network:
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                setup.download("https://example.invalid/source", path, "0" * 64)
        network.assert_not_called()
        self.assertEqual(path.read_bytes(), b"corrupt")

    def test_download_never_publishes_bad_hash(self):
        target = self.root / "source.tar.gz"
        with patch.object(setup.urllib.request, "urlopen", return_value=BytesIO(b"bad")):
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                setup.download("https://example.invalid/source", target, "0" * 64)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_download_verifies_and_reuses_cache(self):
        target = self.root / "source.tar.gz"
        data = b"pinned release"
        digest = hashlib.sha256(data).hexdigest()
        with patch.object(setup.urllib.request, "urlopen", return_value=BytesIO(data)) as network:
            setup.download("https://example.invalid/source", target, digest)
            setup.download("https://example.invalid/source", target, digest)
        self.assertEqual(target.read_bytes(), data)
        self.assertEqual(network.call_count, 1)

    def test_archive_allows_internal_source_symlink(self):
        archive = self.archive([("release/src/file", b"data", None),
                                ("release/doc/link", b"", "../src/file")])
        tree = setup.extract_archive(archive, self.root / "out")
        self.assertEqual((tree / "doc/link").read_bytes(), b"data")

    def test_archive_rejects_traversal_before_writing(self):
        for name in ("../escaped", "/tmp/escaped"):
            with self.subTest(name=name):
                archive = self.archive([("release/good", b"data", None), (name, b"bad", None)])
                with self.assertRaisesRegex(ValueError, "Unsafe archive path"):
                    setup.extract_archive(archive, self.root / "out")
                self.assertFalse((self.root / "out").exists())

    def test_archive_rejects_escaping_symlinks(self):
        archive = self.archive([("release/link", b"", "../../outside")])
        with self.assertRaisesRegex(ValueError, "Unsafe archive link"):
            setup.extract_archive(archive, self.root / "out")
        self.assertFalse((self.root / "out").exists())

    def test_archive_rejects_devices_and_existing_destination(self):
        archive = self.root / "device.tar"
        with tarfile.open(archive, "w") as bundle:
            member = tarfile.TarInfo("release/device")
            member.type = tarfile.CHRTYPE
            bundle.addfile(member)
        with self.assertRaisesRegex(ValueError, "Unsupported archive entry"):
            setup.extract_archive(archive, self.root / "out")
        (self.root / "out").mkdir()
        with self.assertRaisesRegex(ValueError, "already exists"):
            setup.extract_archive(archive, self.root / "out")

    def test_manifest_rejects_unowned_workspace(self):
        manifest = self.root / "manifest.json"
        setup.write_manifest(manifest, {"schema_version": 1, "workspace": "/tmp/cdda-player-build-unowned"})
        with self.assertRaisesRegex(ValueError, "ownership"):
            setup.load_manifest(manifest, {})

    def test_manifest_requires_exact_current_version_without_rewriting(self):
        manifest = self.root / "manifest.json"
        for version in (None, 0, 2, True, 1.0):
            with self.subTest(version=version):
                value = {} if version is None else {"schema_version": version}
                setup.write_manifest(manifest, value)
                before = manifest.read_bytes()
                with self.assertRaisesRegex(ValueError, "Unsupported build manifest format"):
                    setup.load_manifest(manifest, {})
                self.assertEqual(manifest.read_bytes(), before)

    def test_current_manifest_retains_ownership_and_pin_checks(self):
        workspace = self.root / "cdda-player-build-current"
        workspace.mkdir()
        (workspace / ".cdda-player-owner").write_text(str(setup.ROOT))
        value = {"schema_version": 1, "workspace": str(workspace),
                 "source": str(workspace / "source"), "freetype": str(workspace / "headers"),
                 "source_sha256": "pin", "freetype_sha256": setup.FREETYPE_SHA256}
        manifest = self.root / "manifest.json"
        setup.write_manifest(manifest, value)
        self.assertEqual(setup.load_manifest(manifest, {"source_sha256": "pin"}), value)
        with self.assertRaisesRegex(ValueError, "pinned source"):
            setup.load_manifest(manifest, {"source_sha256": "different"})

    def test_mount_is_detached_when_app_copy_fails(self):
        def run(command, **kwargs):
            if command[0] == "hdiutil" and command[1] == "attach":
                mount = Path(command[command.index("-mountpoint") + 1])
                (mount / "Cataclysm.app").mkdir()
            if command[0] == "ditto":
                raise subprocess.CalledProcessError(1, command)

        with patch.object(setup.subprocess, "run", side_effect=run) as runner:
            with self.assertRaises(subprocess.CalledProcessError):
                setup.install_app(self.root / "app.dmg", self.root)
        self.assertEqual(runner.call_args_list[-1].args[0][:2], ["hdiutil", "detach"])
        self.assertFalse((self.root / "Cataclysm.app").exists())

    def test_existing_app_is_never_overwritten(self):
        (self.root / "Cataclysm.app").mkdir()
        with patch.object(setup.subprocess, "run") as runner:
            with self.assertRaisesRegex(ValueError, "refusing to replace"):
                setup.install_app(self.root / "app.dmg", self.root)
        runner.assert_not_called()

    def test_build_recipe_retains_native_flags(self):
        command = setup.build_command({"workspace": "/tmp/work", "source": "/tmp/work/game"}, 6)
        for flag in ("SOUND=1", "LOCALIZE=0", "FRAMEWORK=1", "OPTLEVEL=-O1",
                     "RELEASE_FLAGS=-Wno-error=missing-noreturn", "PKG_CONFIG=/tmp/work/pkg-config"):
            self.assertIn(flag, command)
        self.assertEqual(command[-1], "cataclysm-tiles")

    def test_document_check_rejects_missing_and_escaping_links(self):
        for name in check.REQUIRED_DOCS:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        (self.root / "README.md").write_text("[ok](docs/setup.md) [missing](gone.md) [escape](../elsewhere.md)")
        errors = check.check_documents(self.root)
        self.assertEqual(len(errors), 2)
        self.assertTrue(all("Broken local link" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
