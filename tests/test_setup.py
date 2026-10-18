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
            "src/input_context.cpp": "const std::string &input_context::handle_input( const int timeout )\n{\n        next_action = inp_mngr.get_input_event( preferred_keyboard_mode );\n}",
            "src/handle_action.cpp": "input_context game::get_player_input( std::string &action )\n{\n}",
            "src/action.cpp": ('    input_context ctxt( "DEFAULTMODE", keyboard_mode::keycode );\n'
                '        action = ctxt.handle_input();\n'
                '        if( std::optional<tripoint_rel_ms> vec = ctxt.get_direction_rel_ms( action ) ) {\n}\n'),
            "src/do_turn.cpp": 'void handle_key_blocking_activity()\n{\n    if( has_unfinished_activity || u.has_destination() ) {\n                g->cancel_activity_query( _( "Confirm:" ) );\n}\n}',
            "src/game.cpp": '    if( query_yn( _( "%s Cancel auto move?" ), text ) )  {\n}\n    if( query_yn( "%s %s", text, u.activity.get_stop_phrase() ) ) {\n}',
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

    def test_native_v3_patch_is_repeatable_and_scopes_exact_input_paths(self):
        repository, source = self.patch_fixture()
        first = self.run_patch(repository, source)
        self.assertEqual(first.returncode, 0, first.stderr)
        expected = {path.relative_to(source): path.read_bytes() for path in source.rglob("*.cpp")}
        second = self.run_patch(repository, source)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(expected, {path.relative_to(source): path.read_bytes() for path in source.rglob("*.cpp")})
        self.assertIn("harness_input( category, registered_actions )", (source / "src/input_context.cpp").read_text())
        self.assertIn("harness_player( uquit == QUIT_WATCH", (source / "src/handle_action.cpp").read_text())
        direction = (source / "src/action.cpp").read_text()
        self.assertIn('input_context ctxt( "DEFAULTMODE", keyboard_mode::keycode );', direction)
        self.assertEqual(direction.count("direction_query harness_direction"), 1)
        self.assertIn('return ctxt.handle_input();\n        }();\n'
                      '        if( std::optional<tripoint_rel_ms> vec', direction)
        self.assertIn("boundary_kind::activity_poll", (source / "src/do_turn.cpp").read_text())
        self.assertIn("boundary_kind::debug_prompt", (source / "src/debug.cpp").read_text())
        activity = (source / "src/do_turn.cpp").read_text()
        self.assertIn("activity_interruptible( ( has_unfinished_activity || u.has_destination() ) &&", activity)
        self.assertIn("cdda_harness::interrupt_owner harness_interrupt;", activity)
        self.assertEqual((source / "src/game.cpp").read_text().count("interrupt_query harness_query"), 2)
        sdl = (source / "src/sdltiles.cpp").read_text()
        self.assertEqual(sdl.count("cdda_harness::poll("), 3)
        self.assertLess(sdl.index("cdda_harness::capture_frame();"), sdl.index("SDL_RenderPresent("))
        self.assertIn("frame_presented( static_cast<bool>( harness_presented_frame ) )", sdl)

    def test_patch_rejects_changed_upstream_hash(self):
        repository, source = self.patch_fixture()
        (source / "src/handle_action.cpp").write_text("changed")
        result = self.run_patch(repository, source)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Upstream source differs", result.stderr)

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
