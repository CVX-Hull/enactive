"""Document stewardship checks validate metadata, not the truth of the prose."""
from pathlib import Path
import shutil
import tempfile
import unittest

from tools import documents

ROOT = Path(__file__).resolve().parents[1]


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "schemas").mkdir()
        shutil.copyfile(ROOT / "schemas/document.schema.json", self.root / "schemas/document.schema.json")
        (self.root / "docs/nested").mkdir(parents=True)
        self.active = "---\nowner: maintainer\nstatus: active\nreview_trigger: boundary change\n---\n# Page\n"
        for name in (*documents.ROOT_DOCUMENTS, "docs/nested/page.md"):
            (self.root / name).write_text(self.active)

    def test_valid_metadata_and_normal_checks_never_rewrite(self):
        path = self.root / "docs/nested/page.md"
        original = path.read_bytes()
        self.assertEqual(documents.check_metadata(self.root), [])
        self.assertEqual(path.read_bytes(), original)

    def test_missing_frontmatter_on_every_covered_surface_fails(self):
        for name in (*documents.ROOT_DOCUMENTS, "docs/nested/page.md"):
            with self.subTest(name=name):
                path = self.root / name
                path.write_text("# No metadata\n")
                self.assertIn(name, "\n".join(documents.check_metadata(self.root)))
                path.write_text(self.active)

    def test_missing_root_document_fails(self):
        (self.root / "NOTICE.md").unlink()
        self.assertIn("NOTICE.md", "\n".join(documents.check_metadata(self.root)))

    def test_invalid_fields_status_and_yaml_are_rejected(self):
        path = self.root / "docs/nested/page.md"
        for content in (self.active.replace("owner: maintainer\n", ""),
                        self.active.replace("status: active", "status: invented"),
                        self.active.replace("review_trigger: boundary change", "review_trigger: ''"),
                        "---\nowner: [bad\n---\n# Page\n",
                        self.active.replace("owner: maintainer", "owner: true")):
            with self.subTest(content=content):
                path.write_text(content)
                self.assertTrue(documents.check_metadata(self.root))

    def test_proposed_and_historical_have_distinct_requirements(self):
        path = self.root / "docs/nested/page.md"
        path.write_text(self.active.replace("active", "proposed"))
        self.assertEqual(documents.check_metadata(self.root), [])
        historical = "---\nowner: lead\nstatus: historical\ndate: 2026-10-17\nscope: dated observations\n---\n# Record\n"
        path.write_text(historical)
        self.assertEqual(documents.check_metadata(self.root), [])
        path.write_text(historical.replace("2026-10-17", '"2026-10-17"'))
        self.assertEqual(documents.check_metadata(self.root), [])
        for content in (historical.replace("date: 2026-10-17\n", ""),
                        historical.replace("2026-10-17", "2026-02-30"),
                        historical.replace("scope: dated observations\n", "")):
            path.write_text(content)
            self.assertTrue(documents.check_metadata(self.root))

    def test_superseded_requires_scope_and_safe_existing_local_replacement(self):
        path = self.root / "docs/nested/page.md"
        base = "---\nowner: lead\nstatus: superseded\nreplacement: README.md\nscope: old contract\n---\n# Old\n"
        path.write_text(base)
        self.assertEqual(documents.check_metadata(self.root), [])
        for reference in ("../outside.md", "/etc/passwd", "docs/missing.md", "https://example.com/page", "docs/nested/page.md"):
            with self.subTest(reference=reference):
                path.write_text(base.replace("README.md", reference))
                self.assertTrue(documents.check_metadata(self.root))
        (self.root / "docs/escape.md").symlink_to(self.root.parent / "outside.md")
        path.write_text(base.replace("README.md", "docs/escape.md"))
        self.assertTrue(documents.check_metadata(self.root))
        path.write_text(base.replace("scope: old contract\n", ""))
        self.assertTrue(documents.check_metadata(self.root))

    def test_non_yaml_front_matter_is_rejected(self):
        (self.root / "README.md").write_text(';;;\n{"owner":"lead","status":"active","review_trigger":"change"}\n;;;\nText\n')
        self.assertIn("YAML", "\n".join(documents.check_metadata(self.root)))

    def test_acceptance_records_cannot_be_current_guidance(self):
        directory = self.root / "docs/acceptance/nested"
        directory.mkdir(parents=True)
        path = directory / "2026-10-24-outcome.md"
        for status in ("active", "proposed"):
            path.write_text(self.active.replace("status: active", f"status: {status}"))
            self.assertIn("acceptance records must be historical", "\n".join(documents.check_metadata(self.root)))
        path.write_text("---\nowner: lead\nstatus: historical\ndate: 2026-10-24\n"
                        "scope: frozen source outcome, including failure\n---\n# Outcome\n")
        original = path.read_bytes()
        self.assertEqual(documents.check_metadata(self.root), [])
        self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
