"""Document stewardship checks validate metadata, not the truth of the prose."""
from pathlib import Path
import shutil
import tempfile
import unittest

from tools import documents

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = "---\nowner: lead\nstatus: historical\ndate: 2026-10-17\nscope: dated observations\n---\n# Record\n"


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
        historical = HISTORICAL
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

    def test_historical_and_superseded_pages_cannot_carry_review_triggers(self):
        path = self.root / "docs/nested/page.md"
        for status in ("historical", "superseded"):
            with self.subTest(status=status):
                metadata = dict(owner="lead", status=status, date="2026-10-17",
                                scope="Old guidance", replacement="README.md", review_trigger="New guidance")
                self.assertTrue(documents.schema_errors(self.root, "document", metadata, "test page"))
                header = "".join(f"{key}: {value}\n" for key, value in metadata.items())
                path.write_text(f"---\n{header}---\n# Old guidance\n")
                errors = "\n".join(documents.check_metadata(self.root))
                self.assertIn("remove review_trigger from historical or superseded pages", errors)
                self.assertIn("docs/standards/documentation.md#s-docs-useful-maintained-documentation", errors)

    def test_historical_page_can_name_an_existing_replacement(self):
        path = self.root / "docs/nested/page.md"
        historical = ("---\nowner: lead\nstatus: historical\ndate: 2026-10-17\n"
                      "scope: Old guidance\nreplacement: {}\n---\n# Old guidance\n")
        for invalid in ("docs/missing.md", "docs/nested/page.md"):
            with self.subTest(reference=invalid):
                path.write_text(historical.format(invalid))
                self.assertIn("invalid or missing local replacement", "\n".join(documents.check_metadata(self.root)))
        path.write_text(historical.format("README.md"))
        self.assertEqual(documents.check_metadata(self.root), [])
        for status in ("active", "proposed"):
            with self.subTest(status=status):
                path.write_text(f"---\nowner: lead\nstatus: {status}\nreview_trigger: change\n"
                                "replacement: docs/missing.md\n---\n# Current guidance\n")
                self.assertIn("invalid or missing local replacement", "\n".join(documents.check_metadata(self.root)))

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
        path.write_text("---\nowner: lead\nstatus: historical\nkind: run\ndate: 2026-10-24\n"
                        "scope: frozen source outcome, including failure\n---\n# Outcome\n")
        original = path.read_bytes()
        self.assertEqual(documents.check_metadata(self.root), [])
        self.assertEqual(path.read_bytes(), original)

    def test_active_table_cells_at_or_below_both_caps_pass(self):
        path = self.root / "docs/nested/page.md"
        at_both_caps = "word " * 149 + "x" * 255
        path.write_text(self.active + f"\n| {at_both_caps} | short |\n| :{'-' * 1001} | ---: |\n| ok | ok |\n")
        self.assertEqual(documents.check_structure(self.root), [])

    def test_active_table_cells_over_either_cap_fail(self):
        path = self.root / "docs/nested/page.md"
        for cell, words, chars in (("x " * 150 + "x", "151", "301"), ("x" * 1001, "1", "1,001")):
            with self.subTest(words=words, chars=chars):
                path.write_text(self.active + f"\n| H1 | H2 |\n| --- | --- |\n| short | {cell} |\n")
                errors = documents.check_structure(self.root)
                self.assertEqual(len(errors), 1)
                for detail in ("docs/nested/page.md:10:", f"Word count {words}, cap 150.",
                               f"Character count {chars}, cap 1,000.", documents.REVIEWER_RULE):
                    self.assertIn(detail, errors[0])

    def test_table_pipe_escaping_matches_gfm_parser(self):
        path = self.root / "docs/nested/page.md"
        half = "word " * 80
        # On GitHub / GFM tables, a pipe preceded by one or two backslashes remains escaped inside one cell.
        for sep in (r"\|", r"\\|"):
            with self.subTest(sep=sep):
                path.write_text(self.active + f"\n| A | B |\n| --- | --- |\n| {half}{sep} {half}| ok |\n")
                errors = documents.check_structure(self.root)
                self.assertEqual(len(errors), 1)
                self.assertIn("Word count 161,", errors[0])

    def test_markdown_parser_handles_variants_and_non_tables(self):
        path = self.root / "docs/nested/page.md"
        big = "x" * 1001
        # Tables without outer pipes and blockquoted tables are checked.
        for snippet in (f"A | B\n--- | ---\n{big} | ok\n", f"> | A | B |\n> | --- | --- |\n> | {big} | ok |\n"):
            with self.subTest(snippet=snippet[:12]):
                path.write_text(self.active + "\n" + snippet)
                self.assertEqual(len(documents.check_structure(self.root)), 1)
        # Non-table paragraphs, HTML comments and indented code blocks are ignored.
        path.write_text(self.active + f"\n| {big} |\n\n<!--\n| A |\n| --- |\n| {big} |\n-->\n\n    | A |\n    | --- |\n    | {big} |\n")
        self.assertEqual(documents.check_structure(self.root), [])

    def test_structure_ignores_tables_and_headings_inside_fences(self):
        path = self.root / "docs/design/example.md"
        path.parent.mkdir()
        for fence, other in (("```", "~~~"), ("~~~", "```")):
            with self.subTest(fence=fence):
                path.write_text(self.active + f"\n{fence}markdown\n{other}\n"
                                f"| H |\n| --- |\n| {'x' * 1001} |\n## Proposed\n{fence}\n")
                self.assertEqual(documents.check_structure(self.root), [])

    def test_structure_ignores_front_matter_and_malformed_yaml(self):
        path = self.root / "docs/design/example.md"
        path.parent.mkdir()
        table = f"| H |\n| --- |\n| {'x' * 1001} |"
        header = self.active.replace("review_trigger: boundary change",
                                     f"review_trigger: |-\n  ## Proposed\n  | {'x' * 1001} |")
        path.write_text(header)
        self.assertEqual(documents.check_structure(self.root), [])
        path.write_text(self.active.replace("owner: maintainer", "owner: [broken") + f"\n{table}\n\n## Proposed\n")
        self.assertEqual(documents.check_structure(self.root), [])

    def test_table_cell_cap_exemptions(self):
        table = f"\n| H |\n| --- |\n| {'x' * 1001} |\n"
        path = self.root / "docs/nested/page.md"
        for header in (self.active.replace("active", "proposed"), HISTORICAL):
            path.write_text(header + table)
            self.assertEqual(documents.check_structure(self.root), [])
        for name in ("docs/decisions/owner-decisions.md", "docs/decisions/owner-decisions-archive.md", *documents.INDEXES):
            with self.subTest(name=name):
                path = self.root / name
                path.parent.mkdir(exist_ok=True)
                path.write_text(self.active + table)
                self.assertEqual(documents.check_structure(self.root), [])

    def test_table_cell_cap_covers_root_and_component_pages(self):
        table = f"\n| H |\n| --- |\n| {'x' * 1001} |\n"
        for name in ("README.md", "tools/player_host/README.md"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.active + table)
        errors = documents.check_structure(self.root)
        self.assertEqual(len(errors), 2)
        self.assertTrue(errors[0].startswith("README.md:10:"))
        self.assertTrue(errors[1].startswith("tools/player_host/README.md:10:"))

    def test_active_design_notes_reject_proposed_sections(self):
        path = self.root / "docs/design/example.md"
        path.parent.mkdir()
        for heading in ("## Proposed\n", "## pRoPoSeD next step\n", "Proposed\n--------\n"):
            with self.subTest(heading=heading.splitlines()[0]):
                path.write_text(self.active + f"\n{heading}")
                errors = documents.check_structure(self.root)
                self.assertEqual(len(errors), 1)
                for detail in ("docs/design/example.md:8:", "## Proposed", documents.RECORD_RULE):
                    self.assertIn(detail, errors[0])

    def test_proposed_heading_rule_only_checks_active_design_notes_and_level_two(self):
        design = self.root / "docs/design/example.md"
        design.parent.mkdir()
        for header in (self.active.replace("active", "proposed"), HISTORICAL):
            design.write_text(header + "\n## Proposed\n")
            self.assertEqual(documents.check_structure(self.root), [])
        design.write_text(self.active + "\n### Proposed\n## Proposedly\n\n<!--\n## Proposed\n-->\n\n    ## Proposed\n")
        (self.root / "docs/nested/page.md").write_text(self.active + "\n## Proposed\n")
        self.assertEqual(documents.check_structure(self.root), [])

    def test_main_runs_check_structure(self):
        from unittest import mock
        with (mock.patch.object(documents, "ROOT", self.root),
              mock.patch.object(documents, "check_metadata", return_value=[]),
              mock.patch.object(documents, "check_data", return_value=[]),
              mock.patch.object(documents, "check_risks", return_value=[]),
              mock.patch.object(documents, "check_indexes", return_value=[])):
            (self.root / "docs/nested/page.md").write_text(self.active + f"\n| H |\n| --- |\n| {'x' * 1001} |\n")
            self.assertEqual(documents.main([]), 1)


if __name__ == "__main__":
    unittest.main()
