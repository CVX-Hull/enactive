"""Setup failure boundaries; these tests do not build or launch CDDA."""
from contextlib import redirect_stdout
import hashlib
import fcntl
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

from harness.prepared_app import wrapper_source
from tools import check, prepare_game, setup


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

    def patch_fixture(self):
        """A source-only pinned fixture; no native code is compiled or launched."""
        repository = self.root / "repository"
        (repository / "native").mkdir(parents=True)
        (repository / "tools").mkdir()
        actual = Path(__file__).resolve().parents[1]
        shutil.copyfile(actual / "tools/patch_game.py", repository / "tools/patch_game.py")
        source = self.root / "source"
        names = json.loads((actual / "native/upstream.json").read_text())["source_files"]
        originals = {name: f"upstream {name}\n" for name in names}
        originals["Makefile"] = "-mmacosx-version-min=10.15\n" * 2
        for name, text in originals.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        pin = {"release": "fixture", "source_url": "source", "source_sha256": "source-pin",
               "macos_url": "app", "macos_sha256": "app-pin",
               "source_files": {name: hashlib.sha256(text.encode()).hexdigest()
                                for name, text in originals.items()}}
        (repository / "native/upstream.json").write_text(json.dumps(pin))
        return repository, source

    def run_patch(self, repository, source):
        return subprocess.run([sys.executable, str(repository / "tools/patch_game.py"), str(source)],
                              text=True, capture_output=True, check=False)

    def source_bytes(self, source):
        return {str(path.relative_to(source)): path.read_bytes()
                for path in source.rglob("*") if path.is_file()}

    def test_patch_only_changes_deployment_target_and_is_repeatable(self):
        repository, source = self.patch_fixture()
        original = self.source_bytes(source)
        expected = dict(original)
        expected["Makefile"] = original["Makefile"].replace(b"10.15", b"13.0")
        for _ in range(2):
            result = self.run_patch(repository, source)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.source_bytes(source), expected)
        self.assertFalse((source / ".harness-originals").exists())

    def test_patch_rejects_changed_pinned_sources_before_any_write(self):
        pin_path = Path(__file__).resolve().parents[1] / "native/upstream.json"
        for name in json.loads(pin_path.read_text())["source_files"]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                self.root = Path(temporary)
                repository, source = self.patch_fixture()
                (source / name).write_text("changed")
                before = self.source_bytes(source)
                result = self.run_patch(repository, source)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Upstream source differs", result.stderr)
                self.assertEqual(self.source_bytes(source), before)

    def test_patch_rejects_legacy_sources_without_restoring_them(self):
        for name, content in ((".harness-originals/Makefile", "old backup"),
                              ("src/cdda_harness.cpp", "legacy"),
                              ("src/extra.cpp", 'cdda_harness::poll();'),
                              ("src/extra.h", '#include "cdda_harness.h"'),
                              ("CMakeLists.txt", 'target_sources(game PRIVATE cdda_harness.cpp)')):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                self.root = Path(temporary)
                repository, source = self.patch_fixture()
                target = source / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
                before = self.source_bytes(source)
                result = self.run_patch(repository, source)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("fresh --extract", result.stderr)
                self.assertEqual(self.source_bytes(source), before)

    def test_patch_rejects_deployment_anchor_drift_even_with_matching_hash(self):
        repository, source = self.patch_fixture()
        target = source / "Makefile"
        target.write_text("-mmacosx-version-min=10.15\n")
        pin_path = repository / "native/upstream.json"
        pin = json.loads(pin_path.read_text())
        pin["source_files"]["Makefile"] = hashlib.sha256(target.read_bytes()).hexdigest()
        pin_path.write_text(json.dumps(pin))
        result = self.run_patch(repository, source)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("deployment target anchors changed", result.stderr)

    def app_fixture(self):
        runtime = self.root / ".runtime"
        resources = runtime / "Cataclysm.app/Contents/Resources"
        resources.mkdir(parents=True)
        (resources.parent / "MacOS").mkdir()
        (resources / "cataclysm-tiles").write_bytes(b"official")
        binary = self.root / "built-game"
        binary.write_bytes(b"built")
        return runtime, resources, binary

    def hold_game_lock(self, runtime):
        bridge = runtime / "bridge"
        bridge.mkdir(parents=True, exist_ok=True)
        lock = (bridge / "game.lock").open("a+")
        self.addCleanup(lock.close)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock

    def test_prepare_preserves_saves_other_options_and_original_binary(self):
        runtime, resources, binary = self.app_fixture()
        config = runtime / "user/config"
        config.mkdir(parents=True)
        options = [{"name": "ENABLE_MOUSE", "value": "false", "info": "keep"},
                   {"name": "CUSTOM", "value": "authentic"}]
        (config / "options.json").write_text(json.dumps(options))
        save = runtime / "user/save/character.sav"
        save.parent.mkdir()
        save.write_bytes(b"existing authentic save")
        with patch.object(prepare_game, "ROOT", self.root), \
                patch.object(prepare_game.subprocess, "check_output", return_value="binary:\n"), \
                patch.object(prepare_game.subprocess, "run"):
            prepare_game.prepare(binary)
            prepare_game.prepare(binary)
        values = {item["name"]: item for item in json.loads((config / "options.json").read_text())}
        self.assertEqual(values["ENABLE_MOUSE"], {"name": "ENABLE_MOUSE", "value": "true", "info": "keep"})
        for name, value in {"FULLSCREEN": "no", "TERMINAL_X": "120", "TERMINAL_Y": "40",
                            "TURN_DURATION": "0.0", "USE_LANG": "en", "CUSTOM": "authentic"}.items():
            self.assertEqual(values[name]["value"], value)
        self.assertEqual(save.read_bytes(), b"existing authentic save")
        self.assertEqual((resources / "cataclysm-tiles.official").read_bytes(), b"official")
        self.assertEqual((resources / "cataclysm-tiles").read_bytes(), b"built")
        self.assertEqual(sorted(path.name for path in (runtime / "bridge").iterdir()), ["game.lock"])
        wrapper = resources.parent / "MacOS/Cataclysm.sh"
        self.assertEqual(wrapper.read_text(), wrapper_source(self.root))
        self.assertTrue(wrapper.stat().st_mode & 0o111)

    def test_prepare_refuses_held_game_lock_before_mutations(self):
        runtime, resources, binary = self.app_fixture()
        lock = self.hold_game_lock(runtime)
        before = self.source_bytes(runtime)
        with patch.object(prepare_game, "ROOT", self.root), patch.object(prepare_game.subprocess, "run") as runner:
            with self.assertRaisesRegex(ValueError, "game.*lock|owns.*game"):
                prepare_game.prepare(binary)
        runner.assert_not_called()
        self.assertEqual(self.source_bytes(runtime), before)
        fcntl.flock(lock, fcntl.LOCK_UN)

    def test_direct_app_install_refuses_held_game_lock(self):
        runtime = self.root / ".runtime"
        self.hold_game_lock(runtime)
        before = self.source_bytes(runtime)
        with patch.object(setup.subprocess, "run") as runner:
            with self.assertRaisesRegex(ValueError, "game.*lock|owns.*game"):
                setup.install_app(self.root / "app.dmg", runtime)
        runner.assert_not_called()
        self.assertEqual(self.source_bytes(runtime), before)

    def test_wrapper_sets_injection_inside_shell_and_keeps_game_binding(self):
        root = self.root / "checkout with spaces"
        script = wrapper_source(root)
        self.assertNotIn("CDDA_HARNESS_DIR", script)
        self.assertIn('export DYLD_INSERT_LIBRARIES="$ENACTIVE_COMPUTER_LIBRARY"', script)
        self.assertIn('export DYLD_LIBRARY_PATH="$PWD" DYLD_FRAMEWORK_PATH="$PWD"', script)
        self.assertIn("SDL_MAC_BACKGROUND_APP=1 SDL_WINDOW_NO_ACTIVATION_WHEN_SHOWN=1", script)
        self.assertIn(str(root / ".runtime/Cataclysm.app/Contents/Resources"), script)
        self.assertIn(str(root / ".runtime/user") + "/", script)
        self.assertIn(str(root / ".runtime/logs/game.log"), script)
        result = subprocess.run(["/bin/sh", "-n"], input=script, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_setup_rejects_old_manifest_before_build_or_install(self):
        (self.root / "native").mkdir()
        (self.root / "native/upstream.json").write_text(json.dumps({
            "release": "test", "source_url": "source", "source_sha256": "pin",
            "macos_url": "app", "macos_sha256": "app-pin"}))
        runtime = self.root / ".runtime"
        runtime.mkdir()
        manifest = runtime / "build-manifest.json"
        setup.write_manifest(manifest, {"schema_version": 1})
        for flag in ("--build", "--install"):
            with self.subTest(flag=flag), patch.object(setup, "ROOT", self.root), \
                    patch.object(setup.platform, "system", return_value="Darwin"), \
                    patch.object(setup, "prepare_build") as build, \
                    patch.object(setup.subprocess, "run") as runner, \
                    patch.object(setup.subprocess, "check_output") as scan:
                with self.assertRaisesRegex(ValueError, "Unsupported build manifest format"):
                    setup.main([flag])
                build.assert_not_called()
                runner.assert_not_called()
                scan.assert_not_called()

    def test_setup_rejects_legacy_current_manifest_sources_before_build_or_install(self):
        repository, source = self.patch_fixture()
        (source / ".harness-originals").mkdir()
        value = {"source": str(source), "state": "built"}
        for flag in ("--build", "--install"):
            with self.subTest(flag=flag), patch.object(setup, "ROOT", repository), \
                    patch.object(setup.platform, "system", return_value="Darwin"), \
                    patch.object(setup, "load_manifest", return_value=value), \
                    patch.object(setup, "prepare_build") as build, \
                    patch.object(setup.subprocess, "run") as runner:
                with self.assertRaisesRegex(ValueError, "fresh --extract"):
                    setup.main([flag])
                build.assert_not_called()
                runner.assert_not_called()
        self.assertFalse((repository / ".runtime").exists())

    def test_extract_records_current_schema_and_owned_workspace(self):
        repository, source = self.patch_fixture()
        workspace = self.root / "cdda-player-build-extracted"
        workspace.mkdir()
        with patch.object(setup, "ROOT", repository), \
                patch.object(setup, "verify"), \
                patch.object(setup.tempfile, "mkdtemp", return_value=str(workspace)), \
                patch.object(setup, "extract_archive", side_effect=[workspace / "game/source", workspace / "headers/freetype"]), \
                patch.object(setup.subprocess, "run") as runner:
            self.assertEqual(setup.main(["--extract"]), 0)
        manifest = repository / ".runtime/build-manifest.json"
        value = json.loads(manifest.read_text())
        self.assertEqual(value["schema_version"], 2)
        self.assertEqual(value["state"], "extracted")
        self.assertEqual(value["workspace"], str(workspace.resolve()))
        self.assertEqual((workspace / ".cdda-player-owner").read_text(), str(repository))
        pin = json.loads((repository / "native/upstream.json").read_text())
        with patch.object(setup, "ROOT", repository):
            self.assertEqual(setup.load_manifest(manifest, pin), value)
        runner.assert_not_called()

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
        setup.write_manifest(manifest, {"schema_version": 2, "workspace": "/tmp/cdda-player-build-unowned"})
        with self.assertRaisesRegex(ValueError, "ownership"):
            setup.load_manifest(manifest, {})

    def test_manifest_requires_exact_current_version_without_rewriting(self):
        manifest = self.root / "manifest.json"
        for version in (None, 0, 1, 3, True, 2.0):
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
        value = {"schema_version": 2, "workspace": str(workspace),
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
