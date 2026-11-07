"""Current component documents outside the root and docs/ trees need stewardship metadata."""
from pathlib import Path
import shutil
import tempfile
import unittest

from tools import documents

ROOT = Path(__file__).resolve().parents[1]
PAGE = "tools/player_host/README.md"


class ComponentDocumentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "schemas").mkdir()
        shutil.copyfile(ROOT / "schemas/document.schema.json", self.root / "schemas/document.schema.json")
        (self.root / "docs").mkdir()
        (self.root / "tools/player_host").mkdir(parents=True)
        for name in documents.ROOT_DOCUMENTS:
            (self.root / name).write_text("---\nowner: lead\nstatus: active\nreview_trigger: change\n---\n# Page\n")

    def test_player_host_readme_without_front_matter_fails(self):
        (self.root / PAGE).write_text("# No metadata\n")
        self.assertIn(PAGE, "\n".join(documents.check_metadata(self.root)))
        (self.root / PAGE).write_text("---\nowner: lead\nstatus: active\nreview_trigger: change\n---\n# Page\n")
        self.assertEqual(documents.check_metadata(self.root), [])

    def test_the_checked_in_player_host_readme_is_covered_and_valid(self):
        self.assertIn(PAGE, documents.COMPONENT_DOCUMENTS)
        self.assertEqual(documents.check_metadata(ROOT), [])
