"""Setup failure boundaries; these tests do not build or launch CDDA."""
from contextlib import redirect_stdout
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import subprocess
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
        setup.write_manifest(manifest, {"workspace": "/tmp/cdda-player-build-unowned"})
        with self.assertRaisesRegex(ValueError, "ownership"):
            setup.load_manifest(manifest, {})

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
