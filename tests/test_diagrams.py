"""Real renderer rejection and source/artifact drift, distinct from visual review."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import diagrams

ROOT = Path(__file__).resolve().parents[1]


class DiagramTests(unittest.TestCase):
    def test_escaping_destinations_are_rejected_before_render_or_write(self):
        for name in ("docs/diagrams/context.svg", str(diagrams.RECEIPT),
                     *diagrams.CACHES, "docs/diagrams/config.json"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "project"
                source = root / diagrams.DIRECTORY / "context.mmd"
                source.parent.mkdir(parents=True)
                source.write_text("flowchart TD\n A-->B\n")
                outside = Path(directory) / "outside"
                outside.mkdir()
                sentinel = outside / "sentinel"
                sentinel.write_text("unchanged")
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.symlink_to(outside if name in diagrams.CACHES else sentinel)
                with patch.object(diagrams, "render") as render:
                    with self.assertRaisesRegex(ValueError, "escapes repository"):
                        diagrams.check_or_write(root, write=True)
                    render.assert_not_called()
                self.assertEqual(sentinel.read_text(), "unchanged")
                self.assertEqual(list(outside.iterdir()), [sentinel])

    def test_real_puppeteer_ignores_ambient_browser_overrides(self):
        script = """
import puppeteer from 'puppeteer';
import {PUPPETEER_REVISIONS} from 'puppeteer-core/internal/revisions.js';
const config = await puppeteer.configuration();
console.log(JSON.stringify({version: await puppeteer.browserVersion(),
  pinned: PUPPETEER_REVISIONS.chrome, cache: config.cacheDirectory,
  temporary: config.temporaryDirectory, browser: config.defaultBrowser,
  executable: config.executablePath ?? null,
  downloadURL: config.chrome?.downloadBaseUrl ?? null}));
"""
        with patch.dict(os.environ, {"PUPPETEER_CHROME_VERSION": "123.0.0.0",
                                     "PUPPETEER_BROWSER": "firefox",
                                     "PUPPETEER_EXECUTABLE_PATH": "/outside/browser",
                                     "PUPPETEER_CACHE_DIR": "/outside/cache",
                                     "PUPPETEER_TMP_DIR": "/outside/tmp",
                                     "PUPPETEER_CHROME_DOWNLOAD_BASE_URL": "https://invalid.example"}):
            result = subprocess.run(["node", "--input-type=module", "-e", script],
                                    cwd=ROOT, env=diagrams.renderer_environment(ROOT),
                                    check=True, capture_output=True, text=True, timeout=20)
        actual = json.loads(result.stdout)
        self.assertEqual(actual["version"], actual["pinned"])
        self.assertEqual(actual["browser"], "chrome")
        self.assertEqual(actual["cache"], str(ROOT / ".cache/puppeteer"))
        self.assertEqual(actual["temporary"], str(ROOT / ".cache/puppeteer-tmp"))
        self.assertIsNone(actual["executable"])
        self.assertIsNone(actual["downloadURL"])

    def test_changed_inputs_outputs_and_source_set_fail_without_rewriting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in [*(ROOT / name for name in diagrams.CONFIGURATION),
                         *list((ROOT / diagrams.DIRECTORY).glob("*.mmd")),
                         *list((ROOT / diagrams.DIRECTORY).glob("*.svg")), ROOT / diagrams.RECEIPT]:
                target = root / path.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
            diagrams.check_receipt(root)
            baseline = (root / diagrams.RECEIPT).read_bytes()
            for name in ("docs/diagrams/context.mmd", "docs/diagrams/context.svg",
                         "docs/diagrams/config.json", "package-lock.json"):
                with self.subTest(name=name):
                    path = root / name
                    before = path.read_bytes()
                    path.write_bytes(before + b"\nchanged\n")
                    with self.assertRaisesRegex(ValueError, "changed"):
                        diagrams.check_receipt(root)
                    self.assertEqual((root / diagrams.RECEIPT).read_bytes(), baseline)
                    path.write_bytes(before)
            extra = root / diagrams.DIRECTORY / "new.mmd"
            extra.write_text("flowchart TD\n A-->B\n")
            with self.assertRaises(ValueError):
                diagrams.check_receipt(root)
            extra.unlink()
            (root / diagrams.DIRECTORY / "context.mmd").unlink()
            with self.assertRaisesRegex(ValueError, "changed"):
                diagrams.check_receipt(root)
            (root / diagrams.RECEIPT).unlink()
            with self.assertRaisesRegex(ValueError, "Missing"):
                diagrams.check_receipt(root)

    def test_missing_accessible_description_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "no-description.svg"
            path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><title>Title</title></svg>')
            with self.assertRaisesRegex(ValueError, "desc"):
                diagrams.check_accessibility(path)
            path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><title>T</title><desc>D</desc></svg>')
            with self.assertRaisesRegex(ValueError, "SVG ID"):
                diagrams.check_accessibility(path)

    def test_real_renderer_rejects_invalid_mermaid(self):
        cache = ROOT / ".cache/diagrams"
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="negative-", dir=cache) as directory:
            path = Path(directory) / "invalid.mmd"
            path.write_text("flowchart TD\n  A[Unclosed\n")
            with self.assertRaises(subprocess.CalledProcessError) as caught:
                diagrams.render(ROOT, path, path.with_suffix(".svg"))
            # A missing browser or sandbox denial is not a successful negative case.
            self.assertIn("Parse error", caught.exception.stderr)


if __name__ == "__main__":
    unittest.main()
