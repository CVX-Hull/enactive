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
            "src/ui_manager.cpp": ('                    if( ui.redraw_cb ) {\n'
                '                        ui.default_cursor();\n'
                '                        ui.redraw_cb( ui );\n}\n'),
            "src/uilist.cpp": ('void uilist_impl::draw_controls()\n{\n'
                '                    for( int i = clipper.DisplayStart; i < clipper.DisplayEnd; i++ ) {\n'
                '                        auto entry = parent.entries[parent.fentries[i]];\n'
                '                        bool is_selected = i == parent.fselected;\n'
                '                        ImGui::TableSetColumnIndex( 1 );\n'
                '                        cataimgui::draw_colored_text( str1, color );\n'
                '                        ImGui::TableSetColumnIndex( 2 );\n}\n}\n'),
            "src/inventory_ui.cpp": ('void inventory_selector::refresh_window()\n{\n'
                '    cata_assert( w_inv );\n'
                '                }\n            }\n\n            x1 = x2;\n        }\n\n'
                '        if( entry.is_item() ) {\n            int xx = p.x;\n}\n}\n'
                'void unrelated() { trim_and_print( win, point( 0, 0 ), 10, c_white, hidden ); }\n'),

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
            "src/sdltiles.cpp": ("    while( SDL_PollEvent( &ev ) ) {\n        imclient->process_input( &ev );\n}\n"
                "    SDL_RenderPresent( renderer.get() );\n"
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

    def test_native_v4_patch_is_repeatable_and_scopes_exact_input_paths(self):
        repository, source = self.patch_fixture()
        first = self.run_patch(repository, source)
        self.assertEqual(first.returncode, 0, first.stderr)
        expected = {path.relative_to(source): path.read_bytes()
                    for path in source.rglob("*") if path.is_file()}
        for name in ("ui_iteminfo.cpp", "game_inventory.cpp", "output.cpp", "bodygraph.cpp"):
            (source / "src" / name).write_text("stale patched contents")
        second = self.run_patch(repository, source)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(expected, {path.relative_to(source): path.read_bytes()
                                    for path in source.rglob("*") if path.is_file()})
        self.assertIn("harness_input( category, registered_actions )", (source / "src/input_context.cpp").read_text())
        self.assertIn("harness_player( uquit == QUIT_WATCH", (source / "src/handle_action.cpp").read_text())
        direction = (source / "src/action.cpp").read_text()
        self.assertIn('input_context ctxt( "DEFAULTMODE", keyboard_mode::keycode );', direction)
        self.assertEqual(direction.count('menu_query harness_menu( "DEFAULTMODE" )'), 1)
        self.assertIn('return ctxt.handle_input();\n        }();\n'
                      '        if( std::optional<tripoint_rel_ms> vec', direction)
        for name, callback in (("ui_iteminfo.cpp", 'data.handle_scrolling && data.arrow_scrolling && action == "UP"'),
                               ("game_inventory.cpp", 'action == "UP"')):
            with self.subTest(owner=name):
                text = (source / "src" / name).read_text()
                self.assertIn('#include "cdda_harness.h"', text)
                self.assertEqual(text.count('menu_query harness_menu( "default" )'), 1)
                self.assertIn('return ctxt.handle_input();\n        }();\n\n'
                              f'        if( {callback} )', text)
                self.assertIn('void unrelated() { std::string action = ctxt.handle_input(); }', text)
        self.assertIn('has_button_action() ? get_button_action() : [&]() {',
                      (source / "src/game_inventory.cpp").read_text())
        item_info = (source / "src/output.cpp").read_text()
        self.assertIn('input_context ctxt( "default", keyboard_mode::keychar );', item_info)
        self.assertEqual(item_info.count('menu_query harness_menu( "default" )'), 1)
        self.assertIn('return ctxt.handle_input();\n        }();\n'
                      '        std::optional<point> coord = ctxt.get_coordinates_text( catacurses::stdscr );', item_info)
        self.assertIn('void unrelated() { action = ctxt.handle_input(); }', item_info)
        body = (source / "src/bodygraph.cpp").read_text()
        self.assertIn('#include "cdda_harness.h"', body)
        self.assertEqual(body.count('menu_query harness_menu( "BODYGRAPH" )'), 1)
        self.assertIn('return ctxt.handle_input();\n        }();\n'
                      '        if( action == "QUIT" || ( action == "LEFT" && id != bodygraph_full_body ) ) {', body)
        self.assertIn('void unrelated() { std::string action = ctxt.handle_input(); }', body)
        self.assertIn("boundary_kind::activity_poll", (source / "src/do_turn.cpp").read_text())
        self.assertIn("boundary_kind::debug_prompt", (source / "src/debug.cpp").read_text())
        activity = (source / "src/do_turn.cpp").read_text()
        self.assertIn("activity_interruptible( ( has_unfinished_activity || u.has_destination() ) &&", activity)
        self.assertIn("cdda_harness::interrupt_owner harness_interrupt;", activity)
        self.assertEqual((source / "src/game.cpp").read_text().count("interrupt_query harness_query"), 2)
        distraction = (source / "src/game.cpp").read_text()
        self.assertEqual(distraction.count('menu_query harness_menu( "CANCEL_ACTIVITY_OR_IGNORE_QUERY" )'), 1)
        self.assertIn('const std::string action = [&]() {\n'
                      '        cdda_harness::menu_query harness_menu( "CANCEL_ACTIVITY_OR_IGNORE_QUERY" );\n'
                      '        return query_popup()', distraction)
        self.assertIn('.action;\n    }();\n    if( action == "YES" )', distraction)
        for action in ("YES", "NO", "MANAGER", "IGNORE"):
            self.assertEqual(distraction.count(f'.option( "{action}", allow_key )'), 1)
        self.assertIn('void unrelated() { query_popup().context( "OTHER_QUERY" ).query(); }', distraction)
        sdl = (source / "src/sdltiles.cpp").read_text()
        self.assertEqual(sdl.count("cdda_harness::poll("), 3)
        self.assertLess(sdl.index("cdda_harness::capture_frame();"), sdl.index("SDL_RenderPresent("))
        self.assertIn("frame_presented( static_cast<bool>( harness_presented_frame ) )", sdl)

    def test_visible_ui_hooks_are_at_actual_clipped_and_paged_renderers(self):
        repository, source = self.patch_fixture()
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
        self.assertIn('cell_index == 0 && entry.is_item()', inventory)
        self.assertIn('remove_color_tags( trim_by_length( text, text_width ) )', inventory)
        self.assertIn('yy >= 0 && yy < getmaxy( win )', inventory)
        self.assertIn('void unrelated() { trim_and_print( win, point( 0, 0 ), 10, c_white, hidden ); }', inventory)
        manager = (source / "src/ui_manager.cpp").read_text()
        self.assertIn('cdda_harness::ui_redraw( ui.is_on_top );\n                        ui.redraw_cb( ui );', manager)

    def test_native_v4_commit_and_presented_ui_guards(self):
        # Source-lane checks establish executable guard placement, not C++ execution.
        native = (Path(__file__).resolve().parents[1] / "native/cdda_harness.cpp").read_text()
        self.assertIn('out.member( "protocol", 4 )', native)
        self.assertNotIn(r'\"protocol\":3', native)
        self.assertIn('out.member( "pause_origin", pause_origin )', native)
        self.assertIn('out.member( "takeover_generation", takeover_generation )', native)
        self.assertIn('request.get_string( "boundary_id" ) != boundary_id', native)
        self.assertIn('integer_member( request, "takeover_generation" ) != takeover_generation', native)
        poll = native[native.index('bool poll( keyboard_mode'):]
        self.assertEqual(poll.count('ordinary_gate( request );'), 3)
        self.assertLess(poll.rindex('ordinary_gate( request );'), poll.index('pending = id;'))
        human = native[native.index('void human_input()'):native.index('void boundary()')]
        self.assertIn('++takeover_generation;', human)
        world = native[native.index('void playing('):native.index('void frame_presented(')]
        self.assertNotIn('takeover_generation =', world)
        self.assertIn('pause_origin != "human"', world)
        self.assertIn('staged_ui.reset();', native)
        self.assertIn('ui_boundary == boundary_id && ui_session == session && ui_revision == revision', native)
        self.assertIn('if( next_ui != presented_ui )', native)
        self.assertIn('if( !ui_top || !staged_ui || staged_ui->rows.size() >= 32 )', native)

    def test_patch_rejects_changed_render_owner_hashes_and_anchors(self):
        for name in ("src/uilist.cpp", "src/inventory_ui.cpp", "src/ui_manager.cpp"):
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

    def test_patch_rejects_missing_and_ambiguous_item_owner_anchors(self):
        for name in ("src/ui_iteminfo.cpp", "src/game_inventory.cpp", "src/output.cpp", "src/bodygraph.cpp"):
            for change in ("missing", "duplicate"):
                with self.subTest(owner=name, change=change), tempfile.TemporaryDirectory() as temporary:
                    self.root = Path(temporary)
                    repository, source = self.patch_fixture()
                    path = source / name
                    original = path.read_text()
                    altered = (original.replace("ctxt.handle_input()", "ctxt.handle_input( 5 )")
                               if change == "missing" else original * 2)
                    path.write_text(altered)
                    pin_path = repository / "native/upstream.json"
                    pin = json.loads(pin_path.read_text())
                    pin["source_files"][name] = hashlib.sha256(altered.encode()).hexdigest()
                    pin_path.write_text(json.dumps(pin))
                    result = self.run_patch(repository, source)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(f"Pinned source anchor changed: {path.resolve()}", result.stderr)

    def test_patch_rejects_missing_or_duplicate_distraction_wait_anchors(self):
        for anchor in ('CANCEL_ACTIVITY_OR_IGNORE_QUERY', '.option( "IGNORE", allow_key )'):
            for change in ("missing", "duplicate"):
                with self.subTest(anchor=anchor, change=change), tempfile.TemporaryDirectory() as temporary:
                    previous = self.root
                    self.root = Path(temporary)
                    try:
                        repository, source = self.patch_fixture()
                        path = source / "src/game.cpp"
                        original = path.read_text()
                        altered = original.replace(anchor, "CHANGED") if change == "missing" else original * 2
                        path.write_text(altered)
                        pin_path = repository / "native/upstream.json"
                        pin = json.loads(pin_path.read_text())
                        pin["source_files"]["src/game.cpp"] = hashlib.sha256(altered.encode()).hexdigest()
                        pin_path.write_text(json.dumps(pin))
                        result = self.run_patch(repository, source)
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn(f"Pinned source anchor changed: {path.resolve()}", result.stderr)
                    finally:
                        self.root = previous

    def test_patch_rejects_ambiguous_normal_and_poll_anchors(self):
        for flags, message in (({"duplicate_normal": True}, "Pinned source anchor changed"),
                               ({"duplicate_direction": True}, "Pinned source anchor changed"),
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
